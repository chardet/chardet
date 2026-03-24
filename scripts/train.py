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
import os
import re
import shutil
import signal
import struct
import time
import unicodedata
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


# ---------------------------------------------------------------------------
# Legacy encoding substitutions
# ---------------------------------------------------------------------------

# Universal substitutions for all single-byte encodings: replace modern
# typographic punctuation with ASCII equivalents that would have been used
# historically in legacy encodings.
_UNIVERSAL_SUBSTITUTIONS: dict[str, str] = {
    # Dashes
    "\u2010": "-",  # HYPHEN
    "\u2011": "-",  # NON-BREAKING HYPHEN
    "\u2012": "-",  # FIGURE DASH
    "\u2013": "-",  # EN DASH
    "\u2014": "-",  # EM DASH
    "\u2015": "-",  # HORIZONTAL BAR
    # Quotes
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK
    "\u201a": "'",  # SINGLE LOW-9 QUOTATION MARK
    "\u201b": "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK
    "\u201e": '"',  # DOUBLE LOW-9 QUOTATION MARK
    "\u201f": '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    # Ellipsis
    "\u2026": "...",  # HORIZONTAL ELLIPSIS
    # Spaces
    "\u00a0": " ",  # NO-BREAK SPACE
    "\u2002": " ",  # EN SPACE
    "\u2003": " ",  # EM SPACE
    "\u2009": " ",  # THIN SPACE
    "\u200a": " ",  # HAIR SPACE
    # Other common punctuation
    "\u2022": "*",  # BULLET
    "\u2032": "'",  # PRIME
    "\u2033": '"',  # DOUBLE PRIME
    "\u2212": "-",  # MINUS SIGN
    # Zero-width and formatting characters (remove)
    "\u200b": "",  # ZERO WIDTH SPACE
    "\u200c": "",  # ZERO WIDTH NON-JOINER
    "\u200d": "",  # ZERO WIDTH JOINER
    "\u200e": "",  # LEFT-TO-RIGHT MARK
    "\u200f": "",  # RIGHT-TO-LEFT MARK
    "\ufeff": "",  # ZERO WIDTH NO-BREAK SPACE (BOM)
}

# Arabic-specific substitutions for limited code pages
_ARABIC_SUBSTITUTIONS: dict[str, str] = {
    "\u060c": ",",  # ARABIC COMMA
    "\u061b": ";",  # ARABIC SEMICOLON
    "\u066a": "%",  # ARABIC PERCENT SIGN
}

# CP866: Belarusian/Ukrainian workaround — historical substitution
_CP866_SUBSTITUTIONS: dict[str, str] = {
    "\u0456": "\u0438",  # і → и (Ukrainian/Belarusian I → Russian I)
    "\u0406": "\u0418",  # І → И (uppercase)
}

# Romanian: comma-below → cedilla for encodings without modern forms
_ROMANIAN_CEDILLA_SUBSTITUTIONS: dict[str, str] = {
    "\u021b": "\u0163",  # ț → ţ (comma-below → cedilla)
    "\u0219": "\u015f",  # ș → ş (comma-below → cedilla)
    "\u021a": "\u0162",  # Ț → Ţ (uppercase)
    "\u0218": "\u015e",  # Ș → Ş (uppercase)
}

# Vietnamese: Windows-1258 uses base letters + combining tone marks rather
# than precomposed characters.
_VIETNAMESE_DECOMPOSITION: dict[str, str] = {
    # Regular vowels + tones
    "à": "a\u0300",
    "á": "a\u0301",
    "ả": "a\u0309",
    "ã": "a\u0303",
    "ạ": "a\u0323",
    "è": "e\u0300",
    "é": "e\u0301",
    "ẻ": "e\u0309",
    "ẽ": "e\u0303",
    "ẹ": "e\u0323",
    "ì": "i\u0300",
    "í": "i\u0301",
    "ỉ": "i\u0309",
    "ĩ": "i\u0303",
    "ị": "i\u0323",
    "ò": "o\u0300",
    "ó": "o\u0301",
    "ỏ": "o\u0309",
    "õ": "o\u0303",
    "ọ": "o\u0323",
    "ù": "u\u0300",
    "ú": "u\u0301",
    "ủ": "u\u0309",
    "ũ": "u\u0303",
    "ụ": "u\u0323",
    "ỳ": "y\u0300",
    "ý": "y\u0301",
    "ỷ": "y\u0309",
    "ỹ": "y\u0303",
    "ỵ": "y\u0323",
    # â (circumflex) + tones
    "ấ": "â\u0301",
    "ầ": "â\u0300",
    "ẩ": "â\u0309",
    "ẫ": "â\u0303",
    "ậ": "â\u0323",
    # ê (circumflex) + tones
    "ế": "ê\u0301",
    "ề": "ê\u0300",
    "ể": "ê\u0309",
    "ễ": "ê\u0303",
    "ệ": "ê\u0323",
    # ô (circumflex) + tones
    "ố": "ô\u0301",
    "ồ": "ô\u0300",
    "ổ": "ô\u0309",
    "ỗ": "ô\u0303",
    "ộ": "ô\u0323",
    # ă (breve) + tones
    "ắ": "ă\u0301",
    "ằ": "ă\u0300",
    "ẳ": "ă\u0309",
    "ẵ": "ă\u0303",
    "ặ": "ă\u0323",
    # ơ (horn) + tones
    "ớ": "ơ\u0301",
    "ờ": "ơ\u0300",
    "ở": "ơ\u0309",
    "ỡ": "ơ\u0303",
    "ợ": "ơ\u0323",
    # ư (horn) + tones
    "ứ": "ư\u0301",
    "ừ": "ư\u0300",
    "ử": "ư\u0309",
    "ữ": "ư\u0303",
    "ự": "ư\u0323",
    # Uppercase variants
    "À": "A\u0300",
    "Á": "A\u0301",
    "Ả": "A\u0309",
    "Ã": "A\u0303",
    "Ạ": "A\u0323",
    "È": "E\u0300",
    "É": "E\u0301",
    "Ẻ": "E\u0309",
    "Ẽ": "E\u0303",
    "Ẹ": "E\u0323",
    "Ì": "I\u0300",
    "Í": "I\u0301",
    "Ỉ": "I\u0309",
    "Ĩ": "I\u0303",
    "Ị": "I\u0323",
    "Ò": "O\u0300",
    "Ó": "O\u0301",
    "Ỏ": "O\u0309",
    "Õ": "O\u0303",
    "Ọ": "O\u0323",
    "Ù": "U\u0300",
    "Ú": "U\u0301",
    "Ủ": "U\u0309",
    "Ũ": "U\u0303",
    "Ụ": "U\u0323",
    "Ỳ": "Y\u0300",
    "Ý": "Y\u0301",
    "Ỷ": "Y\u0309",
    "Ỹ": "Y\u0303",
    "Ỵ": "Y\u0323",
    "Ấ": "Â\u0301",
    "Ầ": "Â\u0300",
    "Ẩ": "Â\u0309",
    "Ẫ": "Â\u0303",
    "Ậ": "Â\u0323",
    "Ế": "Ê\u0301",
    "Ề": "Ê\u0300",
    "Ể": "Ê\u0309",
    "Ễ": "Ê\u0303",
    "Ệ": "Ê\u0323",
    "Ố": "Ô\u0301",
    "Ồ": "Ô\u0300",
    "Ổ": "Ô\u0309",
    "Ỗ": "Ô\u0303",
    "Ộ": "Ô\u0323",
    "Ắ": "Ă\u0301",
    "Ằ": "Ă\u0300",
    "Ẳ": "Ă\u0309",
    "Ẵ": "Ă\u0303",
    "Ặ": "Ă\u0323",
    "Ớ": "Ơ\u0301",
    "Ờ": "Ơ\u0300",
    "Ở": "Ơ\u0309",
    "Ỡ": "Ơ\u0303",
    "Ợ": "Ơ\u0323",
    "Ứ": "Ư\u0301",
    "Ừ": "Ư\u0300",
    "Ử": "Ư\u0309",
    "Ữ": "Ư\u0303",
    "Ự": "Ư\u0323",
}


def get_substitutions(charset_name: str, langs: list[str]) -> dict[str, str]:
    """Build the character substitution table for a given encoding."""
    subs = dict(_UNIVERSAL_SUBSTITUTIONS)

    upper = charset_name.upper()
    if upper in ("CP720", "CP864", "ISO-8859-6"):
        subs.update(_ARABIC_SUBSTITUTIONS)
    if upper == "CP866":
        subs.update(_CP866_SUBSTITUTIONS)
    # Romanian comma-below → cedilla for all encodings except ISO-8859-16
    if "ro" in langs and upper != "ISO-8859-16":
        subs.update(_ROMANIAN_CEDILLA_SUBSTITUTIONS)

    return subs


def normalize_text(text: str, charset_name: str) -> str:
    """Clean and normalize text for encoding into a legacy charset."""
    # Collapse repeated whitespace
    text = re.sub(r"(\s)\1+", r"\1", text)
    # Vietnamese decomposition for Windows-1258
    if charset_name.upper() == "WINDOWS-1258":
        nfc = unicodedata.normalize("NFC", text)
        text = "".join(_VIETNAMESE_DECOMPOSITION.get(c, c) for c in nfc)
    return text


def apply_substitutions(text: str, subs: dict[str, str]) -> str:
    """Apply character substitutions to make text encodable in legacy charsets."""
    for old, new in subs.items():
        if old in text:
            text = text.replace(old, new)
    return text


def encode_text(text: str, codec_name: str) -> bytes | None:
    """Encode text into the target encoding, skipping unencodable characters."""
    try:
        # Use 'ignore' for characters that still can't be encoded after
        # substitution — these are genuinely outside the charset's repertoire
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
        for i in range(len(data) - 1):
            counts[(data[i], data[i + 1])] += 1
    return dict(counts)


def normalize_and_prune(
    freqs: dict[tuple[int, int], int],
    min_weight: int,
) -> dict[tuple[int, int], int]:
    """Normalize frequency counts to 0-255 and prune low weights."""
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
    return result


def deserialize_models(
    input_path: Path,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load existing models from binary format."""
    if not input_path.is_file():
        return {}

    data = input_path.read_bytes()

    if not data:
        return {}

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


def serialize_models(
    models: dict[str, dict[tuple[int, int], int]],
    output_path: Path,
) -> int:
    """Serialize all models to binary format. Returns file size."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as f:
        # Number of encodings
        f.write(struct.pack("!I", len(models)))

        for name, bigrams in sorted(models.items()):
            name_bytes = name.encode("utf-8")
            f.write(struct.pack("!I", len(name_bytes)))
            f.write(name_bytes)
            f.write(struct.pack("!I", len(bigrams)))
            for (b1, b2), weight in sorted(bigrams.items()):
                f.write(struct.pack("!BBB", b1, b2, weight))

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


def _count_cached_texts(cache_dir: Path, lang: str) -> int:
    """Count the number of cached text files for a language across all sources."""
    total = 0
    for source in ("culturax", "madlad400", "wikipedia"):
        d = cache_dir / source / lang
        if d.is_dir():
            total += sum(1 for f in d.iterdir() if f.suffix == ".txt")
    return total


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

        samples_used = _count_cached_texts(cache_dir, lang)

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
# encodings.
_worker_text_cache: dict[str, list[str]] = {}


def _build_one_model(  # noqa: PLR0913
    lang: str,
    enc_name: str,
    codec: str,
    cache_dir: Path,
    max_samples: int,
    min_weight: int,
) -> tuple[str, dict[tuple[int, int], int] | None, int, int]:
    """Build a single bigram model in a (possibly forked) worker process.

    Returns
    -------
    tuple of (model_key, bigrams_or_None, sample_count, total_encoded_bytes)

    """
    model_key = f"{lang}/{enc_name}"

    # Load texts from disk cache only (never download in workers).
    # The download phase in main() must complete before workers start.
    if lang not in _worker_text_cache:
        # Load from all source caches (culturax, madlad400, wikipedia)
        texts: list[str] = []
        for source in ("culturax", "madlad400", "wikipedia"):
            source_dir = cache_dir / source / lang
            texts.extend(load_cached_articles(source_dir, max_samples - len(texts)))
            if len(texts) >= max_samples:
                break
        _worker_text_cache[lang] = texts[:max_samples]
    texts = _worker_text_cache[lang]

    if not texts:
        return (model_key, None, 0, 0)

    # Add HTML-wrapped samples
    html_samples = add_html_samples(texts, charset=enc_name)
    all_texts = list(texts) + html_samples

    # Prepare substitutions for this encoding
    subs = get_substitutions(enc_name, [lang])

    # Normalize, substitute, and encode all texts
    encoded: list[bytes] = []
    for text in all_texts:
        text = normalize_text(text, enc_name)
        text = apply_substitutions(text, subs)
        result = encode_text(text, codec)
        if result is not None:
            encoded.append(result)

    if not encoded:
        return (model_key, None, len(all_texts), 0)

    # Compute bigram frequencies
    freqs = compute_bigram_frequencies(encoded)
    bigrams = normalize_and_prune(freqs, min_weight)

    if not bigrams:
        return (model_key, None, len(encoded), sum(len(e) for e in encoded))

    total_bytes = sum(len(e) for e in encoded)
    return (model_key, bigrams, len(encoded), total_bytes)


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
        default=15000,
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
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    output_path = Path(args.output)

    start_time = time.time()

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

    # Collect all unique languages needed
    all_langs: set[str] = set()
    for langs in encoding_map.values():
        all_langs.update(langs)
    sorted_langs = sorted(all_langs)

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
        for future in concurrent.futures.as_completed(futures, timeout=600):
            lang, count, stats = future.result(timeout=60)
            lang_stats[lang] = stats
            print(f"  {lang}: {count} texts")
        pool.shutdown(wait=False, cancel_futures=True)
        print()

    # Build models for each encoding
    print(f"=== Building bigram models ({args.build_workers} workers) ===")
    models: dict[str, dict[tuple[int, int], int]] = {}
    skipped = []

    # Pre-verify codecs and collect work items
    work_items: list[tuple[str, str, str, Path, int, int]] = []
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
            (lang, enc_name, codec, cache_dir, args.max_samples, args.min_weight)
            for lang in langs
        )

    if args.build_workers == 1:
        # Sequential mode (useful for debugging)
        for item in work_items:
            key, bigrams, samples, total_bytes = _build_one_model(*item)
            if bigrams:
                models[key] = bigrams
                print(
                    f"  {key}: {len(bigrams)} bigrams from "
                    f"{samples} samples ({total_bytes:,} bytes)"
                )
            else:
                print(f"  SKIP {key}: no usable bigrams")
    else:
        # Parallel mode
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.build_workers,
        ) as pool:
            futures = {
                pool.submit(_build_one_model, *item): item[1]  # enc_name for error msg
                for item in work_items
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    key, bigrams, samples, total_bytes = future.result()
                except Exception as exc:
                    enc = futures[future]
                    print(f"  ERROR {enc}: {exc}")
                    continue
                if bigrams:
                    models[key] = bigrams
                    print(
                        f"  {key}: {len(bigrams)} bigrams from "
                        f"{samples} samples ({total_bytes:,} bytes)"
                    )
                else:
                    print(f"  SKIP {key}: no usable bigrams")

    print()

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

    # Register cleanup handler to kill all threads and subprocesses on exit

    def cleanup():
        """Kill all threads and subprocesses on exit."""
        # Force exit
        os._exit(0)

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())


if __name__ == "__main__":
    main()
