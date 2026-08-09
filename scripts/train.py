#!/usr/bin/env python3
"""Training script for chardet bigram models.

Downloads text from CulturaX, MADLAD-400, and Wikipedia via Hugging Face,
encodes text into target encodings, computes byte-pair bigram frequencies, and
serializes the results into models.bin.

Test data articles are automatically excluded from training via content
fingerprinting (see scripts/exclusions.py). CulturaX is the primary data
source; MADLAD-400 and Wikipedia fill gaps for low-resource languages.

Usage:
    uv run python scripts/train.py
    uv run python scripts/train.py --max-samples 50000 --encodings koi8-r cp866
    uv run python scripts/train.py --no-skip-test-overlap  # disable exclusions
"""

from __future__ import annotations

import argparse
import atexit
import codecs
import collections
import concurrent.futures

# Ensure progress output is visible when piped through tee.
import functools
import hashlib
import itertools
import math
import os
import pickle
import shutil
import signal
import struct
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

from confusion_training import (
    compute_distinguishing_maps,
    serialize_confusion_data,
)
from data_sources import (
    SourceStats,
    check_cache_validity,
    load_cached_articles,
    write_cache_sentinel,
)
from data_sources import get_texts as get_texts_multi
from exclusions import build_exclusion_set
from substitutions import (
    apply_substitutions,
    collapse_whitespace_runs,
    get_substitutions,
    normalize_text,
    transliterate_serbian_to_latin,
)

from chardet.registry import REGISTRY

print = functools.partial(print, flush=True)  # noqa: A001

# ---------------------------------------------------------------------------
# Encoding -> language mapping (derived from registry)
# ---------------------------------------------------------------------------

# Build encoding → language map from the registry.  Language associations are
# based on the historical usage of each encoding and stored in
# ``EncodingInfo.languages``.
ENCODING_LANG_MAP: dict[str, list[str]] = {
    enc.name: list(enc.languages) for enc in REGISTRY.values() if enc.languages
}
# utf-8 is language-agnostic but we train it on ALL languages for
# language detection (Tier 3 fallback in the pipeline).
_ALL_LANGS = sorted({lang for enc in REGISTRY.values() for lang in enc.languages})
ENCODING_LANG_MAP["utf-8"] = _ALL_LANGS

# Train-time pseudo-language for the ANSI-art model (ISO 639 "zxx" = no
# linguistic content).  Prose models carry no signal for box-drawing and
# shading bytes, so art files land on arbitrary winners; a model trained on
# real artpacks (fetched by scripts/fetch_artpacks.py) makes art ordinary
# statistical detection.  Deliberately NOT in the registry — the pipeline
# maps zxx back to language=None at the API boundary.
_ART_PSEUDO_LANG = "zxx"
ENCODING_LANG_MAP["cp437"] = [*ENCODING_LANG_MAP["cp437"], _ART_PSEUDO_LANG]


def encode_text(text: str, codec_name: str) -> bytes | None:
    """Encode text into the target encoding.

    Unencodable characters are silently dropped.  This is appropriate for the
    ASCII-normalized form where substitutions have already handled most
    characters.
    """
    try:
        result = text.encode(codec_name, errors="ignore")
        return result if len(result) > 10 else None
    except (LookupError, UnicodeEncodeError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# HTML sample generation
# ---------------------------------------------------------------------------


def add_html_samples(
    texts: list[str], count: int = 20, charset: str = "utf-8"
) -> list[str]:
    """Wrap some text samples in HTML to train on markup patterns."""
    html_samples = []
    for i, text in enumerate(texts[:count]):
        snippet = text[:500]
        html = (
            f"<!DOCTYPE html>\n<html>\n<head>\n"
            f'<meta charset="{charset}">\n<title>Article {i}</title>\n'
            f"</head>\n<body>\n<h1>Article {i}</h1>\n"
            f"<p>{snippet}</p>\n</body>\n</html>"
        )
        html_samples.append(html)
    return html_samples


# ---------------------------------------------------------------------------
# Bigram computation and serialization
# ---------------------------------------------------------------------------


def compute_bigram_frequencies(
    encoded_samples: list[bytes],
) -> dict[tuple[int, int], int]:
    """Count byte bigram frequencies across all samples."""
    counts: dict[tuple[int, int], int] = collections.Counter()
    for data in encoded_samples:
        for b1, b2 in itertools.pairwise(data):
            counts[(b1, b2)] += 1
    return dict(counts)


def normalize_and_prune(
    freqs: dict[tuple[int, int], int],
    min_weight: int,
) -> dict[tuple[int, int], int]:
    """Normalize frequency counts to 0-255 and prune low weights.

    High-byte bigrams (at least one byte >= 0x80) with raw count >= 300 are
    preserved at minimum weight 1 even when global normalization rounds them
    to 0.  A count of 300 across ~15K training articles indicates a real
    language pattern, not noise.  This recovers encoding-diagnostic signal
    that global normalization crushes because ASCII bigrams dominate by
    orders of magnitude.
    """
    if not freqs:
        return {}

    max_count = max(freqs.values())
    if max_count == 0:
        return {}

    result: dict[tuple[int, int], int] = {}
    for pair, count in freqs.items():
        weight = int(round(count / max_count * 255))
        if weight >= min_weight:
            result[pair] = weight
        elif (pair[0] >= 0x80 or pair[1] >= 0x80) and count >= 300:
            result[pair] = 1
    return result


def deserialize_models(
    input_path: Path,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load existing models from binary format (v1 or v2)."""
    if not input_path.is_file():
        return {}

    data = input_path.read_bytes()

    if not data:
        return {}

    # Detect format version by magic bytes
    if data[:4] == b"CMD2":
        return _deserialize_v2(data)
    return _deserialize_v1(data)


def _deserialize_v1(
    data: bytes,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load models from v1 sparse binary format."""
    models: dict[str, dict[tuple[int, int], int]] = {}
    try:
        offset = 0
        (num_encodings,) = struct.unpack_from("!I", data, offset)
        offset += 4

        if num_encodings > 10_000:
            msg = f"Corrupt models file: num_encodings={num_encodings} exceeds limit"
            raise ValueError(msg)

        for _ in range(num_encodings):
            (name_len,) = struct.unpack_from("!I", data, offset)
            offset += 4
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            (num_entries,) = struct.unpack_from("!I", data, offset)
            offset += 4

            bigrams: dict[tuple[int, int], int] = {}
            for _ in range(num_entries):
                b1, b2, weight = struct.unpack_from("!BBB", data, offset)
                offset += 3
                bigrams[(b1, b2)] = weight
            models[name] = bigrams
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"Corrupt models file: {e}"
        raise ValueError(msg) from e

    if offset != len(data):
        msg = f"Corrupt models file: {len(data) - offset} trailing bytes"
        raise ValueError(msg)

    return models


def _deserialize_v2(
    data: bytes,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load models from v2 dense zlib-compressed format."""
    try:
        offset = 4  # skip "CMD2" magic
        (num_models,) = struct.unpack_from("!I", data, offset)
        offset += 4

        if num_models > 10_000:
            msg = f"Corrupt models file: num_models={num_models} exceeds limit"
            raise ValueError(msg)

        names: list[str] = []
        for _ in range(num_models):
            (name_len,) = struct.unpack_from("!I", data, offset)
            offset += 4
            if name_len > 256:
                msg = f"Corrupt models file: name_len={name_len} exceeds 256"
                raise ValueError(msg)
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            offset += 8  # skip norm (float64), not needed for sparse dict output
            names.append(name)

        dobj = zlib.decompressobj()
        blob = dobj.decompress(data[offset:])
        if dobj.unused_data:
            msg = f"Corrupt models file: {len(dobj.unused_data)} trailing bytes"
            raise ValueError(msg)
        expected_size = num_models * 65536
        if len(blob) != expected_size:
            msg = (
                f"Corrupt models file: decompressed size {len(blob)} "
                f"!= expected {expected_size}"
            )
            raise ValueError(msg)

        models: dict[str, dict[tuple[int, int], int]] = {}
        for i, name in enumerate(names):
            base = i * 65536
            bigrams: dict[tuple[int, int], int] = {}
            for idx in range(65536):
                weight = blob[base + idx]
                if weight > 0:
                    bigrams[(idx >> 8, idx & 0xFF)] = weight
            models[name] = bigrams

    except zlib.error as e:
        msg = f"Corrupt models file: {e}"
        raise ValueError(msg) from e
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"Corrupt models file: {e}"
        raise ValueError(msg) from e

    return models


def serialize_models(
    models: dict[str, dict[tuple[int, int], int]],
    output_path: Path,
) -> int:
    """Serialize all models to v2 binary format (dense + zlib). Returns file size."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_names = sorted(models.keys())

    # Build header: magic + num_models + per-model name and norm
    header = b"CMD2"
    header += struct.pack("!I", len(sorted_names))

    tables = bytearray()
    for name in sorted_names:
        bigrams = models[name]
        name_bytes = name.encode("utf-8")

        # Expand sparse dict to dense 65536-byte table and compute L2 norm
        table = bytearray(65536)
        sq_sum = 0
        for (b1, b2), weight in bigrams.items():
            table[(b1 << 8) | b2] = weight
            sq_sum += weight * weight
        norm = math.sqrt(sq_sum)

        header += struct.pack("!I", len(name_bytes)) + name_bytes
        header += struct.pack("!d", norm)
        tables.extend(table)

    compressed = zlib.compress(bytes(tables), 9)

    with output_path.open("wb") as f:
        f.write(header)
        f.write(compressed)

    return output_path.stat().st_size


def verify_codec(codec_name: str) -> bool:
    """Verify a Python codec exists and can encode."""
    try:
        codecs.lookup(codec_name)
        return True
    except LookupError:
        return False


# ---------------------------------------------------------------------------
# Training metadata
# ---------------------------------------------------------------------------


def _count_cached_texts(cache_dir: Path, lang: str, max_samples: int) -> int:
    """Count the number of cached text files for a language across all sources.

    Capped at *max_samples* to reflect what training actually uses.
    """
    total = 0
    for source in ("culturax", "madlad400", "wikipedia"):
        d = cache_dir / source / lang
        if d.is_dir():
            total += sum(1 for f in d.iterdir() if f.suffix == ".txt")
    return min(total, max_samples)


def _write_training_metadata(
    path: Path,
    models: dict[str, dict[tuple[int, int], int]],
    max_samples: int,
    cache_dir: Path,
    lang_stats: dict[str, SourceStats],
) -> None:
    """Write training metadata YAML alongside models.bin.

    The YAML is written manually (no PyYAML dependency) since the structure
    is flat enough to emit directly.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = [
        f'training_date: "{timestamp}"',
        f"max_samples: {max_samples}",
        "models:",
    ]

    for model_key in sorted(models):
        bigram_count = len(models[model_key])
        # Model keys use "lang/encoding" format
        parts = model_key.split("/", 1)
        if len(parts) == 2:
            lang, encoding = parts
        else:
            # Fallback for old flat-format keys (just encoding name)
            lang = "unknown"
            encoding = parts[0]

        samples_used = _count_cached_texts(cache_dir, lang, max_samples)

        lines.append(f"  {model_key}:")
        lines.append(f"    language: {lang}")
        lines.append(f"    encoding: {encoding}")
        lines.append(f"    samples_used: {samples_used}")
        lines.append(f"    bigram_entries: {bigram_count}")
        stats = lang_stats.get(lang, SourceStats())
        lines.append("    sources:")
        lines.append(f"      culturax: {stats.culturax}")
        lines.append(f"      madlad400: {stats.madlad400}")
        lines.append(f"      wikipedia: {stats.wikipedia}")
        lines.append(f"    test_articles_excluded: {stats.excluded}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Parallel model building
# ---------------------------------------------------------------------------

# Per-worker text cache. Each worker process lazily loads language texts from
# the disk cache (populated by the download phase) and caches them here to
# avoid redundant disk reads when the same language is used across multiple
# encodings.  This relies on ProcessPoolExecutor (fork-based) — each forked
# worker gets its own copy of this dict.
_worker_text_cache: dict[str, list[str]] = {}

# Per-worker cache of which characters each codec can encode, keyed by codec
# name.  Corpus alphabets are small, so each character is probed once.
_worker_encodable_cache: dict[str, dict[str, bool]] = {}


def _filter_encodable(
    text: str, codec: str, cache: dict[str, bool]
) -> tuple[str, int, int]:
    """Drop characters *codec* cannot encode and count alphabetic retention.

    Dropping happens explicitly in text space (rather than via
    ``errors="ignore"`` at encode time) so whitespace collapsing can run
    *after* the drop — otherwise removed characters leave freshly adjacent
    whitespace behind as fake bigram signal (see ADR-0004).

    Returns ``(filtered_text, kept_alpha, total_alpha)``.
    """
    counts = collections.Counter(text)
    kept = 0
    total = 0
    drop: list[str] = []
    for ch, n in counts.items():
        ok = cache.get(ch)
        if ok is None:
            try:
                ok = ch.encode(codec, errors="ignore") != b""
            except UnicodeEncodeError:
                ok = False
            cache[ch] = ok
        if ch.isalpha():
            total += n
            if ok:
                kept += n
        if not ok:
            drop.append(ch)
    if drop:
        text = text.translate({ord(c): None for c in drop})
    return text, kept, total


def _is_latin_target(codec: str) -> bool:
    """Return True if *codec* cannot represent Cyrillic text."""
    try:
        return "абвгд".encode(codec, errors="ignore") == b""
    except UnicodeEncodeError:
        return True


def _build_one_model(
    lang: str,
    enc_name: str,
    codec: str,
    cache_dir: Path,
    max_samples: int,
) -> tuple[str, dict[tuple[int, int], int] | None, int, int, float | None]:
    """Build a single bigram model in a (possibly forked) worker process.

    Returns
    -------
    tuple of (model_key, bigrams_or_None, sample_count, total_encoded_bytes,
    alpha_retention_or_None)

    ``alpha_retention`` is the fraction of alphabetic characters across all
    samples that survived encoding into the target, or ``None`` when the
    corpus contained no alphabetic characters.

    """
    model_key = f"{lang}/{enc_name}"

    # Load texts from disk cache only (never download in workers).
    # The download phase in main() must complete before workers start.
    if lang not in _worker_text_cache:
        # Keep only the current language.  utf-8 alone spans every
        # language, so an unbounded cache has each worker accumulating
        # dozens of 25k-article text lists — enough to get the whole
        # process group OOM-killed near the end of a full retrain.
        _worker_text_cache.clear()
        # Load from all source caches.  The artpacks source only ever holds
        # the zxx pseudo-language (populated by scripts/fetch_artpacks.py).
        texts: list[str] = []
        for source in ("culturax", "madlad400", "wikipedia", "artpacks"):
            source_dir = cache_dir / source / lang
            texts.extend(load_cached_articles(source_dir, max_samples - len(texts)))
            if len(texts) >= max_samples:
                break
        _worker_text_cache[lang] = texts[:max_samples]
    texts = _worker_text_cache[lang]

    if not texts:
        return (model_key, None, 0, 0, None)

    # Add HTML-wrapped samples (not for art — artpacks are not web pages)
    if lang == _ART_PSEUDO_LANG:
        all_texts = list(texts)
    else:
        all_texts = list(texts) + add_html_samples(texts, charset=enc_name)

    # Prepare substitutions for this encoding
    subs = get_substitutions(enc_name, [lang])

    # Serbian is digraphic: for Latin-script targets, transliterate the
    # (predominantly Cyrillic) corpus to Gaj's Latin alphabet (ADR-0004).
    # Note: uppercase augmentation for MAINFRAME models was tried here and
    # removed — doubling every sample with an uppercased copy flattened the
    # separation between EBCDIC sibling models on ordinary prose without
    # rescuing the all-caps fixed-width records it targeted.
    transliterate = lang == "sr" and _is_latin_target(codec)

    enc_cache = _worker_encodable_cache.setdefault(codec, {})

    # Normalize, substitute, filter, and encode all texts
    encoded: list[bytes] = []
    kept_alpha = 0
    total_alpha = 0
    for text in all_texts:
        if transliterate:
            text = transliterate_serbian_to_latin(text)
        text = normalize_text(text, enc_name)
        text = apply_substitutions(text, subs)
        filtered, kept, total = _filter_encodable(text, codec, enc_cache)
        kept_alpha += kept
        total_alpha += total
        result = encode_text(collapse_whitespace_runs(filtered), codec)
        if result is not None:
            encoded.append(result)

    retention = kept_alpha / total_alpha if total_alpha else None

    if not encoded:
        return (model_key, None, len(all_texts), 0, retention)

    # Compute raw bigram frequencies (normalization happens later in main)
    freqs = compute_bigram_frequencies(encoded)

    if not freqs:
        return (model_key, None, len(encoded), sum(len(e) for e in encoded), retention)

    total_bytes = sum(len(e) for e in encoded)
    return (model_key, freqs, len(encoded), total_bytes, retention)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Train chardet bigram models")
    parser.add_argument(
        "--output",
        default="src/chardet/models/models.bin",
        help="Output path for models.bin",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/",
        help="Directory to cache downloaded data",
    )
    parser.add_argument(
        "--min-weight",
        type=int,
        default=1,
        help="Minimum weight threshold for pruning",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=25000,
        help="Maximum number of text samples per language",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=8,
        help="Number of parallel threads for downloading",
    )
    parser.add_argument(
        "--build-workers",
        type=int,
        default=os.cpu_count(),
        help="Number of parallel processes for building models (default: all CPUs)",
    )
    parser.add_argument(
        "--encodings",
        nargs="+",
        default=None,
        help="Specific encodings to retrain (default: all). "
        "When specified, existing models for other encodings are preserved.",
    )
    parser.add_argument(
        "--test-data-dir",
        default="tests/data/",
        help="Path to test data directory for building exclusion set",
    )
    parser.add_argument(
        "--skip-test-overlap",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip training articles that overlap with test data (default: on)",
    )
    parser.add_argument(
        "--keep-cache",
        action="store_true",
        default=False,
        help="Keep existing cache even if exclusion set has changed",
    )
    parser.add_argument(
        "--from-raw-cache",
        action="store_true",
        default=False,
        help="Skip download and model building; load raw bigram counts from "
        "cache and re-run normalization and serialization only",
    )
    parser.add_argument(
        "--min-alpha-retention",
        type=float,
        default=0.7,
        help="Abort if any (language, encoding) pair keeps less than this "
        "fraction of its corpus's alphabetic characters after encoding "
        "(see ADR-0004)",
    )
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    output_path = Path(args.output)

    start_time = time.time()

    # Register cleanup handler early so it covers the download and build phases.
    # HuggingFace streaming iterators can hold connections open and prevent
    # normal Python shutdown, so we force-exit via os._exit as a last resort.
    def cleanup():
        """Kill all threads and subprocesses on exit."""
        os._exit(0)

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())

    # Filter to requested encodings (or all)
    if args.encodings:
        unknown = [e for e in args.encodings if e not in ENCODING_LANG_MAP]
        if unknown:
            print(f"ERROR: Unknown encodings: {', '.join(unknown)}")
            print(f"Available: {', '.join(sorted(ENCODING_LANG_MAP))}")
            raise SystemExit(1)
        encoding_map = {e: ENCODING_LANG_MAP[e] for e in args.encodings}
    else:
        encoding_map = ENCODING_LANG_MAP

    # Collect all unique languages needed.  The art pseudo-language is not
    # downloadable from HuggingFace — scripts/fetch_artpacks.py populates
    # its cache — so it is excluded from the download phase.
    all_langs: set[str] = set()
    for langs in encoding_map.values():
        all_langs.update(langs)
    all_langs.discard(_ART_PSEUDO_LANG)
    sorted_langs = sorted(all_langs)
    art_cache = cache_dir / "artpacks" / _ART_PSEUDO_LANG
    if (
        _ART_PSEUDO_LANG in {lang for langs in encoding_map.values() for lang in langs}
        and not art_cache.is_dir()
    ):
        print(
            f"WARNING: no artpack cache at {art_cache} — run "
            "scripts/fetch_artpacks.py first to train the art model"
        )

    # Build exclusion set from test data
    exclusions: frozenset[str] = frozenset()
    if args.skip_test_overlap:
        test_data_path = Path(args.test_data_dir)
        if test_data_path.is_symlink():
            test_data_path = test_data_path.resolve()
        if test_data_path.is_dir():
            print("=== Building test data exclusion set ===")
            exclusions = build_exclusion_set(test_data_path)
            print(f"  {len(exclusions)} unique fingerprints from test data")
            print()
        else:
            print(f"WARNING: test data dir not found: {test_data_path}")
            print("  Continuing without exclusion filtering.")
            print()

    # Check cache validity against exclusion set
    if exclusions and not args.keep_cache:
        if not check_cache_validity(cache_dir, exclusions):
            print("  Exclusion set changed — invalidating article caches")
            for source in ("culturax", "madlad400", "wikipedia"):
                source_dir = cache_dir / source
                if source_dir.is_dir():
                    shutil.rmtree(source_dir)
                    print(f"    Cleared {source_dir}")
        write_cache_sentinel(cache_dir, exclusions)

    print(f"Training bigram models for {len(encoding_map)} encodings")
    print(f"Languages needed: {sorted_langs}")
    print(f"Max samples per language: {args.max_samples}")
    print()

    lang_stats: dict[str, SourceStats] = {}

    if args.download_workers == 1:
        print("=== Downloading texts (single-threaded) ===")
        for lang in sorted_langs:
            texts, stats = get_texts_multi(
                lang, args.max_samples, cache_dir, exclusions
            )
            lang_stats[lang] = stats
            print(f"  {lang}: {len(texts)} texts")
        print()
    else:
        # Pre-download all language texts (parallel — I/O-bound).
        # HuggingFace streaming iterators can hold connections open and cause the
        # thread pool to hang on shutdown, so we use cancel_futures=True and a
        # per-future timeout to ensure we don't block forever.
        print(f"=== Downloading texts ({args.download_workers} threads) ===")

        def _fetch(lang: str) -> tuple[str, int, SourceStats]:
            texts, stats = get_texts_multi(
                lang, args.max_samples, cache_dir, exclusions
            )
            return lang, len(texts), stats

        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=args.download_workers,
        )
        futures = {pool.submit(_fetch, lang): lang for lang in sorted_langs}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=600):
                try:
                    lang, count, stats = future.result(timeout=60)
                except Exception as exc:
                    lang = futures[future]
                    print(f"  ERROR downloading {lang}: {exc}")
                    continue
                lang_stats[lang] = stats
                print(f"  {lang}: {count} texts")
        except concurrent.futures.TimeoutError:
            pending = {futures[f] for f in futures if not f.done()}
            print(f"  WARNING: download timed out for: {', '.join(sorted(pending))}")
        pool.shutdown(wait=False, cancel_futures=True)
        print()

    # Build raw bigram frequency models (or load from cache)
    raw_cache_path = cache_dir / "raw_bigram_counts.pkl"

    # raw_models: model_key -> raw frequency dict (not yet normalized)
    raw_models: dict[str, dict[tuple[int, int], int]] = {}
    skipped: list[str] = []

    if args.from_raw_cache and raw_cache_path.is_file():
        print("=== Loading raw bigram counts from cache ===")
        with raw_cache_path.open("rb") as f:
            raw_models = pickle.load(f)  # noqa: S301
        print(f"  Loaded {len(raw_models)} raw models from {raw_cache_path}")
        print()
    else:
        print(f"=== Building bigram models ({args.build_workers} workers) ===")

        # Pre-verify codecs and collect work items
        work_items: list[tuple[str, str, str, Path, int]] = []
        for enc_name, langs in sorted(encoding_map.items()):
            codec = None
            codec_candidates = [enc_name]
            normalized = enc_name.replace("-", "").replace("_", "").lower()
            codec_candidates.append(normalized)

            for candidate in codec_candidates:
                if verify_codec(candidate):
                    codec = candidate
                    break

            if codec is None:
                print(f"  SKIP {enc_name}: codec not found")
                skipped.append(enc_name)
                continue

            work_items.extend(
                (lang, enc_name, codec, cache_dir, args.max_samples) for lang in langs
            )

        retention_by_key: dict[str, float] = {}

        def record_result(
            key: str,
            freqs: dict[tuple[int, int], int] | None,
            samples: int,
            total_bytes: int,
            retention: float | None,
        ) -> None:
            if retention is not None:
                retention_by_key[key] = retention
            r_str = (
                f", {retention:.1%} alpha retention" if retention is not None else ""
            )
            if freqs:
                raw_models[key] = freqs
                print(
                    f"  {key}: {len(freqs)} raw bigrams from "
                    f"{samples} samples ({total_bytes:,} bytes{r_str})"
                )
            else:
                print(f"  SKIP {key}: no usable bigrams{r_str}")

        if args.build_workers == 1:
            # Sequential mode (useful for debugging)
            for item in work_items:
                record_result(*_build_one_model(*item))
        else:
            # Parallel mode
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=args.build_workers,
            ) as pool:
                futures = {
                    pool.submit(_build_one_model, *item): item[1] for item in work_items
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                    except Exception as exc:
                        enc = futures[future]
                        print(f"  ERROR {enc}: {exc}")
                        continue
                    record_result(*result)

        # Retention guard (ADR-0004): a registry-declared (language, encoding)
        # pair whose corpus mostly fails to encode is a config or
        # preprocessing bug — abort before anything is cached or shipped.
        low_retention = {
            key: r
            for key, r in sorted(retention_by_key.items())
            if r < args.min_alpha_retention
        }
        if low_retention:
            print()
            print(
                f"ERROR: alphabetic retention below "
                f"{args.min_alpha_retention:.0%} for "
                f"{len(low_retention)} model(s):"
            )
            for key, r in low_retention.items():
                print(f"  {key}: {r:.1%}")
            print(
                "A registry-declared (language, encoding) pair must be able "
                "to represent its corpus; fix the registry languages or the "
                "preprocessing (substitutions/transliteration). See ADR-0004."
            )
            # os._exit, not SystemExit: the atexit cleanup handler exits 0
            # unconditionally, which would swallow the failure code.
            os._exit(1)

        # Cache raw counts for future --from-raw-cache runs
        print(f"\n  Caching raw bigram counts to {raw_cache_path}")
        with raw_cache_path.open("wb") as f:
            pickle.dump(raw_models, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  Cached {len(raw_models)} raw models")
        print()

    # Normalize and prune raw counts into final models
    print("=== Normalizing and pruning ===")
    models: dict[str, dict[tuple[int, int], int]] = {}
    for key, freqs in sorted(raw_models.items()):
        bigrams = normalize_and_prune(freqs, args.min_weight)
        if bigrams:
            models[key] = bigrams
    print(f"  {len(models)} models after normalization")

    # Merge with existing models when retraining a subset
    if args.encodings:
        print("=== Merging with existing models ===")
        existing = deserialize_models(output_path)
        # Remove old models for retrained encodings (both formats)
        for enc in args.encodings:
            existing.pop(enc, None)  # old flat format
            to_remove = [k for k in existing if k.endswith(f"/{enc}")]
            for k in to_remove:
                del existing[k]
        existing.update(models)
        models = existing
        print(f"  Merged {len(models)} total models ({len(args.encodings)} retrained)")

    # Serialize
    print("=== Serializing models ===")
    file_size = serialize_models(models, output_path)

    # Compute and serialize IDF weights for bigram profile construction.
    # This is a 65536-byte table where each byte is a quantized IDF weight
    # for the corresponding bigram index.
    print("=== Computing IDF weights ===")
    idf_path = output_path.parent / "idf.bin"
    num_models = len(models)
    doc_freq = [0] * 65536
    for bigrams in models.values():
        for b1, b2 in bigrams:
            doc_freq[(b1 << 8) | b2] += 1
    max_idf = math.log(num_models) if num_models > 1 else 1.0
    scale = 254.0 / max_idf if max_idf > 0 else 0.0
    idf_table = bytearray(65536)
    for idx in range(65536):
        df = doc_freq[idx]
        if df > 0:
            idf_val = math.log(num_models / df)
            idf_table[idx] = max(1, round(idf_val * scale) + 1)
        else:
            idf_table[idx] = 1
    idf_path.write_bytes(idf_table)
    print(f"IDF weights:  {idf_path} ({len(idf_table):,} bytes)")

    # Serialize per-model row maxima for upper-bound prescreening in
    # statistical scoring.  Format: CRM1 magic, SHA-256 of the models.bin
    # just written (so a stale rowmax.bin is detected at load time), then
    # one 256-byte table per model (entry b1 = max weight in that model's
    # row for lead byte b1), concatenated in the same sorted-name order as
    # models.bin.
    print("=== Computing row-max tables ===")
    rowmax_path = output_path.parent / "rowmax.bin"
    rowmax_blob = bytearray(b"CRM1")
    rowmax_blob.extend(hashlib.sha256(output_path.read_bytes()).digest())
    for name in sorted(models.keys()):
        rm = [0] * 256
        for (b1, _b2), weight in models[name].items():
            rm[b1] = max(rm[b1], weight)
        rowmax_blob.extend(rm)
    rowmax_path.write_bytes(rowmax_blob)
    print(f"Row maxima:   {rowmax_path} ({len(rowmax_blob):,} bytes)")

    print("=== Computing confusion groups ===")
    confusion_maps = compute_distinguishing_maps(threshold=0.80)
    confusion_size = serialize_confusion_data(
        confusion_maps, output_path.parent / "confusion.bin"
    )
    print(f"Confusion groups: {len(confusion_maps)} pairs")
    print(
        f"Confusion data:   {confusion_size:,} bytes ({confusion_size / 1024:.1f} KB)"
    )

    metadata_path = output_path.with_name("training_metadata.yaml")
    _write_training_metadata(
        metadata_path, models, args.max_samples, cache_dir, lang_stats
    )
    print(f"Metadata written: {metadata_path}")

    elapsed = time.time() - start_time

    # Print summary
    print()
    print("=" * 60)
    print(f"Models trained: {len(models)}")
    print(f"Models skipped: {len(skipped)}")
    if skipped:
        print(f"  Skipped: {', '.join(skipped)}")
    print(f"Output file:    {output_path}")
    print(f"File size:      {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    print(f"Elapsed time:   {elapsed:.1f}s")
    print()

    # Per-model stats
    print("Per-model sizes:")
    for name in sorted(models):
        n = len(models[name])
        # 4 (name_len) + len(name) + 4 (num_entries) + 3*n (entries)
        model_bytes = 4 + len(name.encode("utf-8")) + 4 + 3 * n
        print(f"  {name:20s}: {n:6d} bigrams ({model_bytes:,} bytes)")


if __name__ == "__main__":
    main()
