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
import signal
import struct
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

from confusion_training import (
    compute_distinguishing_maps,
    serialize_confusion_data,
)
from data_sources import (
    DOWNLOADABLE_SOURCES,
    TEXT_SOURCES,
    SourceStats,
    check_cache_validity,
    hash_exclusion_set,
    load_cached_articles,
    write_cache_sentinel,
)
from data_sources import get_texts as get_texts_multi
from exclusions import build_exclusion_set, content_hash, overlaps_exclusions
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

# Languages that have been reviewed for the rare-language arbitration set
# (``chardet.models.RARE_LANGUAGES``, see ADR-0005).  Training warns when a
# model is built for a language not in this list, so a newly added language
# gets a deliberate prevalence classification instead of silence.  After
# reviewing (add to the arbitration set or deliberately leave it out),
# record the language here.
_PREVALENCE_REVIEWED: frozenset[str] = frozenset(
    {
        _ART_PSEUDO_LANG,
        *[
            "ar",
            "be",
            "bg",
            "br",
            "cs",
            "cy",
            "da",
            "de",
            "el",
            "en",
            "eo",
            "es",
            "et",
            "fa",
            "fi",
            "fr",
            "ga",
            "gd",
            "he",
            "hr",
            "hu",
            "id",
            "is",
            "it",
            "ja",
            "kk",
            "ko",
            "lt",
            "lv",
            "mk",
            "ms",
            "mt",
            "nl",
            "no",
            "pl",
            "pt",
            "ro",
            "ru",
            "sk",
            "sl",
            "sr",
            "sv",
            "tg",
            "th",
            "tr",
            "uk",
            "ur",
            "vi",
            "zh",
        ],
    }
)


#: Status the atexit handler force-exits with.  HuggingFace streaming
#: iterators hold connections open and stop the interpreter shutting down
#: normally, so training force-exits — which, when it was hardcoded to 0,
#: reported success for every failure that reached shutdown, including
#: uncaught exceptions and Ctrl-C.  :func:`fail` bypasses this entirely;
#: the handler covers everything else.
_exit_status = 0


def fail(*lines: str) -> None:
    """Print an error and terminate the process non-zero.

    Force-exits rather than raising: HuggingFace streaming iterators leave
    non-daemon threads behind, and a normal ``SystemExit`` waits on them at
    shutdown, so an error message would be followed by a hang instead of an
    exit.
    """
    for line in lines:
        print(line)
    os._exit(1)


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
    for source in TEXT_SOURCES:
        d = cache_dir / source / lang
        if d.is_dir():
            total += sum(1 for f in d.iterdir() if f.suffix == ".txt")
    return min(total, max_samples)


def _read_metadata_blocks(path: Path) -> dict[str, list[str]]:
    """Parse an existing metadata YAML into per-model line blocks.

    The file is our own flat hand-emitted format: each model starts with a
    two-space-indented ``  key:`` line followed by deeper-indented fields.
    Returns ``{model_key: [block lines]}``; empty when the file is absent.
    """
    if not path.is_file():
        return {}
    blocks: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            current = []
            blocks[line[2:-1]] = current
            current.append(line)
        elif current is not None and line.startswith("    "):
            current.append(line)
    return blocks


#: Provenance of a set of bigram counts: the exclusion set they were
#: filtered against, and the test-data commit it came from (when known).
Provenance = tuple[str, str | None]

#: Raw-count cache format.  v1 was a bare ``{model_key: counts}`` mapping
#: with no record of the corpus it was built from; v2 stores per-model
#: provenance alongside, so a ``--from-raw-cache`` rebuild can report
#: honestly what its counts were filtered against.  ``version`` is safe as
#: a marker because a v1 mapping is keyed by encoding or ``lang/encoding``
#: names, and no encoding in the registry is called "version".
_RAW_CACHE_VERSION = 2


def _load_raw_cache(
    path: Path,
) -> tuple[dict[str, dict[tuple[int, int], int]], dict[str, Provenance | None]]:
    """Load the raw-count cache as ``(counts_by_key, provenance_by_key)``.

    A v1 (unversioned) file loads with no provenance, which is the honest
    reading: those counts record nothing about the corpus behind them.
    A file claiming an unknown version is an error rather than something
    to guess at — misreading it would put unrelated data into models.bin.
    """
    with path.open("rb") as f:
        blob = pickle.load(f)  # noqa: S301
    if not isinstance(blob, dict):
        msg = f"{path}: not a raw-count cache"
        raise TypeError(msg)
    if "version" not in blob:
        return blob, {}
    if blob["version"] != _RAW_CACHE_VERSION:
        msg = (
            f"{path}: unsupported raw-count cache version {blob['version']!r} "
            f"(this script writes v{_RAW_CACHE_VERSION}); delete it to rebuild"
        )
        raise ValueError(msg)
    if "counts" not in blob or "provenance" not in blob:
        msg = f"{path}: raw-count cache is missing its counts or provenance"
        raise ValueError(msg)
    return blob["counts"], blob["provenance"]


def _save_raw_cache(
    path: Path,
    counts: dict[str, dict[tuple[int, int], int]],
    provenance: dict[str, Provenance | None],
) -> None:
    """Write the raw-count cache with its per-model provenance."""
    blob = {
        "version": _RAW_CACHE_VERSION,
        "counts": counts,
        "provenance": provenance,
    }
    with path.open("wb") as f:
        pickle.dump(blob, f, protocol=pickle.HIGHEST_PROTOCOL)


def _provenance_for_run(
    args: argparse.Namespace,
    exclusions: frozenset[str],
    test_data_dir: Path | None,
    cache_dir: Path,
) -> Provenance | None:
    """Return the provenance that models built by *this run* carry.

    ``None`` means the models this run builds cannot be said to have been
    filtered against any particular test data:

    * ``--no-skip-test-overlap``, an empty exclusion set, or a missing
      test-data directory means nothing was excluded at all — and
      recording the empty set's hash would let it match another empty run
      and read as verified;
    * ``--keep-cache`` skips the filtering pass, so excluded articles may
      still be sitting in the corpus — unless the cache sentinel already
      records this exact exclusion set, which is direct evidence that a
      previous run filtered the corpus against it (and the reason the
      filtering pass would have been a no-op anyway).

    Subset retrains and ``--from-raw-cache`` are *not* disqualified here.
    What they build (or reuse) carries its own provenance, and whether the
    shipped models as a whole can be stamped is decided by
    :func:`_consensus_provenance` across every model in models.bin.
    """
    if not args.skip_test_overlap or not exclusions or test_data_dir is None:
        return None
    if args.keep_cache and not check_cache_validity(cache_dir, exclusions):
        return None
    return hash_exclusion_set(exclusions), _git_head(test_data_dir)


def _consensus_provenance(values: list[Provenance | None]) -> Provenance | None:
    """Return the provenance shared by *every* value, else ``None``.

    The metadata's record claims that every model in models.bin was
    filtered against one exclusion set, so a single unknown or dissenting
    model makes the whole set unverifiable.  Commits may legitimately
    differ where the hash agrees (two commits with identical test-data
    content), in which case the hash is recorded without a commit.
    """
    if not values or any(v is None for v in values):
        return None
    hashes = {v[0] for v in values}
    if len(hashes) != 1:
        return None
    # An unrecorded commit is missing information, not disagreement: keep a
    # commit the recorded ones agree on so the file list stays available.
    commits = {v[1] for v in values if v[1] is not None}
    return hashes.pop(), commits.pop() if len(commits) == 1 else None


def _read_metadata_header(path: Path, field: str) -> str | None:
    """Read a top-level quoted string field from an existing metadata file."""
    if not path.is_file():
        return None
    prefix = f"{field}:"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("models:"):
            break
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip('"') or None
    return None


def _git(path: Path, *args: str) -> str | None:
    """Run a git command in *path*, returning stdout or None on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _git_head(path: Path) -> str | None:
    """Return the git HEAD of the repository *rooted at* *path*, if any.

    ``git -C`` walks up to the enclosing repository, so a plain directory
    inside another checkout would otherwise report that parent's HEAD.
    The default test-data layout is exactly that (``scripts/utils.py``
    copies the clone's contents without its ``.git``), and recording the
    chardet SHA there would make the provenance check compare test data
    against chardet's own history.  Only a repository whose top level is
    *path* itself counts.
    """
    toplevel = _git(path, "rev-parse", "--show-toplevel")
    if toplevel is None or Path(toplevel).resolve() != path.resolve():
        return None
    return _git(path, "rev-parse", "HEAD")


def _write_training_metadata(  # noqa: PLR0913
    path: Path,
    models: dict[str, dict[tuple[int, int], int]],
    max_samples: int,
    cache_dir: Path,
    lang_stats: dict[str, SourceStats],
    *,
    retrained_encodings: set[str] | None = None,
    provenance: tuple[str, str | None] | None = None,
) -> None:
    """Write training metadata YAML alongside models.bin.

    The YAML is written manually (no PyYAML dependency) since the structure
    is flat enough to emit directly.

    On a subset retrain (*retrained_encodings* given), entries for models
    whose encoding was not retrained are carried over verbatim from the
    existing file: recomputing them would count the *current* article
    cache, which records ``samples_used: 0`` for every language whose
    corpus is no longer on disk even though the shipped model is unchanged.

    *provenance* is ``(exclusion_set_hash, test_data_commit_or_None)``,
    already reduced by :func:`_consensus_provenance` to a state that
    *every* model in *models* was filtered against — including models
    merged in from a previous models.bin, which inherit that file's
    record.  ``None`` means no such shared state exists and the fields are
    omitted, so the absence reads as unverifiable.  It is deliberately not
    carried forward from the existing file: a guard that over-claims is
    worse than none, since it would certify models as clean against test
    data they predate.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    previous = _read_metadata_blocks(path) if retrained_encodings else {}
    exclusion_hash, commit = provenance if provenance is not None else (None, None)

    lines: list[str] = [
        f'training_date: "{timestamp}"',
        f"max_samples: {max_samples}",
    ]
    if exclusion_hash is not None:
        lines.append(f'exclusion_set_hash: "{exclusion_hash}"')
    if commit is not None:
        lines.append(f'test_data_commit: "{commit}"')
    lines.append("models:")

    for model_key in sorted(models):
        if retrained_encodings is not None:
            enc_part = model_key.split("/", 1)[-1]
            if enc_part not in retrained_encodings and model_key in previous:
                lines.extend(previous[model_key])
                continue
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
        # The artpack corpus is not downloaded by get_texts, so its count
        # comes from the on-disk cache — otherwise samples_used (which
        # counts all TEXT_SOURCES) would attribute those samples to no
        # source.
        artpacks_dir = cache_dir / "artpacks" / lang
        artpacks_count = (
            sum(1 for f in artpacks_dir.iterdir() if f.suffix == ".txt")
            if artpacks_dir.is_dir()
            else 0
        )
        lines.append("    sources:")
        lines.append(f"      culturax: {stats.culturax}")
        lines.append(f"      madlad400: {stats.madlad400}")
        lines.append(f"      wikipedia: {stats.wikipedia}")
        lines.append(f"      artpacks: {artpacks_count}")
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
        for source in TEXT_SOURCES:
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
        """Kill all threads and subprocesses on exit, keeping the status."""
        os._exit(_exit_status)

    atexit.register(cleanup)
    # A signal or an uncaught exception is a failure: without these the
    # handler above would force-exit 0 and report a killed or crashed run
    # as a successful one.
    signal.signal(signal.SIGTERM, lambda _s, _f: os._exit(1))
    signal.signal(signal.SIGINT, lambda _s, _f: os._exit(1))

    def _crashed(exc_type, exc, tb):  # noqa: ANN001
        global _exit_status  # noqa: PLW0603 - process-wide exit status
        _exit_status = 1
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _crashed

    # Filter to requested encodings (or all)
    if args.encodings:
        unknown = [e for e in args.encodings if e not in ENCODING_LANG_MAP]
        if unknown:
            print(f"ERROR: Unknown encodings: {', '.join(unknown)}")
            print(f"Available: {', '.join(sorted(ENCODING_LANG_MAP))}")
            fail()
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
    unreviewed = sorted(all_langs - _PREVALENCE_REVIEWED)
    if unreviewed:
        print(
            f"WARNING: language(s) not yet reviewed for rare-language "
            f"arbitration (ADR-0005): {', '.join(unreviewed)} — classify "
            "them in chardet.models.RARE_LANGUAGES or record the decision "
            "in _PREVALENCE_REVIEWED"
        )
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
    test_data_path: Path | None = None
    if args.skip_test_overlap:
        candidate = Path(args.test_data_dir)
        if candidate.is_symlink():
            candidate = candidate.resolve()
        if candidate.is_dir():
            test_data_path = candidate
            print("=== Building test data exclusion set ===")
            exclusions = build_exclusion_set(test_data_path)
            print(f"  {len(exclusions)} unique fingerprints from test data")
            print()
        else:
            print(f"WARNING: test data dir not found: {candidate}")
            print("  Continuing without exclusion filtering.")
            print()

    # Sample provenance here, next to the exclusion set it describes, so the
    # recorded hash and commit cannot drift apart over a long run.
    run_provenance = _provenance_for_run(args, exclusions, test_data_path, cache_dir)

    # Check cache validity against exclusion set.  When the exclusion set
    # changes, filter every source cache in place — drop only articles
    # whose fingerprint is now excluded — rather than deleting the caches
    # wholesale.  A wholesale wipe once combined with a subset retrain to
    # lose models: the retrain re-downloads only its own languages, the
    # 600s download window cannot refill dozens of corpora, and the build
    # phase then consumed empty snapshots while the download threads were
    # still filling them.
    #
    # Deduplication is *not* gated on the exclusion set: duplicates are a
    # property of the corpus, not of the test data, so a valid sentinel
    # must not skip the pass.  It once did, and a retrain then ran on
    # 4,140 duplicate Breton articles.  Only the languages this run uses
    # are scanned, keeping a subset retrain cheap.
    if not args.keep_cache:
        filter_excluded = bool(exclusions) and not check_cache_validity(
            cache_dir, exclusions
        )
        # Exclusion filtering covers *every* language, not just this run's:
        # the sentinel written below records that the whole cache was
        # filtered against this test set, and a later run trusts it.  A
        # subset retrain that filtered only its own languages while
        # stamping the cache-wide sentinel would leave the rest permanently
        # unfiltered.  Deduplication is per-run-language because nothing
        # records it and the next run redoes it.
        deduped_langs = {*sorted_langs, _ART_PSEUDO_LANG}
        if filter_excluded:
            print("  Exclusion set changed — filtering article caches")
        print("  Checking article caches for duplicates")
        for source in (*DOWNLOADABLE_SOURCES, "artpacks"):
            source_dir = cache_dir / source
            if not source_dir.is_dir():
                continue
            removed = 0
            deduped = 0
            for lang_dir in sorted(source_dir.iterdir()):
                if not lang_dir.is_dir():
                    continue
                dedupe_here = lang_dir.name in deduped_langs
                if not (filter_excluded or dedupe_here):
                    continue
                kept: list[Path] = []
                # A corpus slice can hold the same document many times over
                # (one Breton article occurred 567 times), and every copy is
                # counted again in each bigram it feeds, pulling the model
                # toward whatever happens to be duplicated.
                seen: set[str] = set()
                for article in sorted(lang_dir.glob("*.txt")):
                    try:
                        text = article.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        # A corrupt or truncated cache file is as good as
                        # excluded; drop it and let the next download top
                        # the cache back up.
                        article.unlink()
                        removed += 1
                        continue
                    if filter_excluded and overlaps_exclusions(text, exclusions):
                        article.unlink()
                        removed += 1
                        continue
                    if dedupe_here:
                        digest = content_hash(text)
                        if digest in seen:
                            article.unlink()
                            deduped += 1
                            continue
                        seen.add(digest)
                    kept.append(article)
                # Renumber compactly: the download layer resumes at index
                # len(cached), so numbering gaps would make it overwrite
                # kept articles and permanently undercount the cache.  Each
                # target index is <= its source index, so replace() never
                # clobbers an unprocessed file.  The shortfall is topped up
                # by the next download pass.
                for i, article in enumerate(kept):
                    target = lang_dir / f"{i:06d}.txt"
                    if article != target:
                        article.replace(target)
            if removed:
                print(f"    {source}: removed {removed} newly-excluded articles")
            if deduped:
                print(f"    {source}: removed {deduped} duplicate articles")
        if exclusions:
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
    # What each of those count sets was filtered against.
    raw_provenance: dict[str, Provenance | None] = {}
    skipped: list[str] = []

    if args.from_raw_cache and raw_cache_path.is_file():
        print("=== Loading raw bigram counts from cache ===")
        try:
            raw_models, raw_provenance = _load_raw_cache(raw_cache_path)
        except Exception as exc:  # any unreadable cache
            print(f"ERROR: cannot read {raw_cache_path}: {exc}")
            fail()
        print(f"  Loaded {len(raw_models)} raw models from {raw_cache_path}")
        unrecorded = sum(1 for k in raw_models if raw_provenance.get(k) is None)
        if unrecorded:
            print(
                f"  {unrecorded} of them carry no record of which test set was "
                "excluded when they were built; the metadata will report "
                "unverified"
            )
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
                raw_provenance[key] = run_provenance
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
            failed: list[str] = []
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=args.build_workers,
            ) as pool:
                futures = {
                    pool.submit(_build_one_model, *item): f"{item[0]}/{item[1]}"
                    for item in work_items
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                    except Exception as exc:
                        key = futures[future]
                        print(f"  ERROR {key}: {exc}")
                        failed.append(key)
                        continue
                    record_result(*result)
            if failed:
                print()
                print(
                    f"ERROR: {len(failed)} model build(s) failed: "
                    f"{', '.join(sorted(failed))}"
                )
                print(
                    "A failed build would silently ship without these models "
                    "(a transient worker death cost uk/mac-cyrillic once); "
                    "re-run the training command."
                )
                fail()

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
            fail()

        # Cache raw counts for future --from-raw-cache runs.  On a subset
        # retrain, merge into whatever is already cached: replacing it
        # wholesale would leave the cache describing only this subset, and
        # a later --from-raw-cache run would rebuild models.bin from it
        # and silently drop (or, worse, resurrect superseded versions of)
        # every other model.
        cached_raw: dict[str, dict[tuple[int, int], int]] = {}
        cached_prov: dict[str, Provenance | None] = {}
        cache_readable = True
        if args.encodings and raw_cache_path.is_file():
            try:
                cached_raw, cached_prov = _load_raw_cache(raw_cache_path)
            except Exception as exc:  # any unreadable cache
                # Unpickling raises a wide and version-dependent set of
                # exceptions (ValueError and UnicodeDecodeError among them);
                # none of them should discard a completed build phase.
                print(f"  WARNING: unreadable raw cache ({exc})")
                cached_raw, cached_prov, cache_readable = {}, {}, False
            # Drop only the legacy flat-format keys that this run replaces.
            # Evicting every key for a retrained encoding up front would
            # delete a model that this build skipped, leaving nothing to put
            # back — and the lost-model guard below aborts only *after* this
            # file is written.
            for enc in args.encodings:
                if any(k.split("/", 1)[-1] == enc for k in raw_models):
                    cached_raw.pop(enc, None)
                    cached_prov.pop(enc, None)
        cached_raw.update(raw_models)
        cached_prov.update(raw_provenance)
        if cache_readable:
            print(f"\n  Caching raw bigram counts to {raw_cache_path}")
            _save_raw_cache(raw_cache_path, cached_raw, cached_prov)
            print(f"  Cached {len(cached_raw)} raw models")
        else:
            # Writing now would replace a whole (unreadable but possibly
            # recoverable) cache with just this subset, and a later
            # --from-raw-cache run would then ship a models.bin missing
            # everything else.  Leave it for inspection instead.
            print(
                f"\n  Leaving {raw_cache_path} untouched: overwriting it with "
                f"only this subset would lose every other model.  Delete it "
                f"and run a full retrain to rebuild."
            )
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
        removed_keys: list[str] = []
        for enc in args.encodings:
            if existing.pop(enc, None) is not None:  # old flat format
                removed_keys.append(enc)
            to_remove = [k for k in existing if k.endswith(f"/{enc}")]
            for k in to_remove:
                del existing[k]
            removed_keys.extend(to_remove)
        # A model that existed cannot silently become unbuildable: a SKIP
        # here means an empty/broken corpus cache or a preprocessing bug,
        # and merging would ship models.bin without the model (this lost
        # 11 models to a cache race once).  Legacy flat-format keys (bare
        # encoding names) are exempt: the rebuild replaces them with
        # lang/encoding keys by design, so they can never reappear
        # verbatim.
        lost = sorted(k for k in removed_keys if "/" in k and k not in models)
        if lost:
            print()
            print(
                f"ERROR: subset retrain produced no replacement for "
                f"{len(lost)} existing model(s): {', '.join(lost)}"
            )
            print(
                "Check the SKIP lines above — the corpus cache for those "
                "languages is likely empty or incomplete.  models.bin was "
                "not modified."
            )
            fail()
        existing.update(models)
        models = existing
        print(f"  Merged {len(models)} total models ({len(args.encodings)} retrained)")

    # Decide what provenance the shipped models.bin as a whole can claim.
    # Every model must have been filtered against the same exclusion set:
    # those built (or reloaded) this run carry their own record, and any
    # model merged in from the previous models.bin inherits that file's
    # recorded provenance — which is sound because only a run whose models
    # all agreed was allowed to write it in the first place.
    metadata_path = output_path.with_name("training_metadata.yaml")
    carried_provenance: Provenance | None = None
    carried_hash = _read_metadata_header(metadata_path, "exclusion_set_hash")
    if carried_hash is not None:
        carried_provenance = (
            carried_hash,
            _read_metadata_header(metadata_path, "test_data_commit"),
        )
    # Discriminate on membership in raw_models, not raw_provenance: a key
    # this run built or loaded but has no record for is *unknown*, and must
    # not silently inherit the previous file's stamp.  (Every v1 cache entry
    # is exactly that case.)
    provenance = _consensus_provenance(
        [
            raw_provenance.get(key) if key in raw_models else carried_provenance
            for key in models
        ]
    )
    if provenance is None:
        print(
            "  Provenance: unverified (the models were not all built with "
            "one known test set excluded)"
        )
    else:
        print(f"  Provenance: built with test set {provenance[0][:12]} excluded")

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

    _write_training_metadata(
        metadata_path,
        models,
        args.max_samples,
        cache_dir,
        lang_stats,
        retrained_encodings=set(args.encodings) if args.encodings else None,
        provenance=provenance,
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
