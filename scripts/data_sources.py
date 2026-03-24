"""Multi-source text data downloading for training.

Provides download functions for CulturaX, MADLAD-400, and Wikipedia,
each following the same pattern: check disk cache -> stream from
HuggingFace -> fingerprint-check -> cache accepted articles.
"""

from __future__ import annotations

import functools
import hashlib
from dataclasses import dataclass
from pathlib import Path

from exclusions import is_excluded

print = functools.partial(print, flush=True)  # noqa: A001

# ---------------------------------------------------------------------------
# Dataset identifiers
# ---------------------------------------------------------------------------

CULTURAX_DATASET = "uonlp/CulturaX"
MADLAD_DATASET = "allenai/MADLAD-400"
WIKIPEDIA_DATASET = "wikimedia/wikipedia"

# ---------------------------------------------------------------------------
# Language code mappings
# ---------------------------------------------------------------------------

# MADLAD-400 uses BCP-47 codes. Most match ISO 639-1 directly.
MADLAD_LANG_MAP: dict[str, str] = {
    "ar": "ar",
    "be": "be",
    "bg": "bg",
    "br": "br",
    "cs": "cs",
    "cy": "cy",
    "da": "da",
    "de": "de",
    "el": "el",
    "en": "en",
    "eo": "eo",
    "es": "es",
    "et": "et",
    "fa": "fa",
    "fi": "fi",
    "fr": "fr",
    "ga": "ga",
    "gd": "gd",
    "he": "he",
    "hr": "hr",
    "hu": "hu",
    "id": "id",
    "is": "is",
    "it": "it",
    "ja": "ja",
    "kk": "kk",
    "ko": "ko",
    "lt": "lt",
    "lv": "lv",
    "mk": "mk",
    "ms": "ms",
    "mt": "mt",
    "nl": "nl",
    "no": "no",
    "pl": "pl",
    "pt": "pt",
    "ro": "ro",
    "ru": "ru",
    "sk": "sk",
    "sl": "sl",
    "sr": "sr",
    "sv": "sv",
    "tg": "tg",
    "th": "th",
    "tr": "tr",
    "uk": "uk",
    "ur": "ur",
    "vi": "vi",
    "zh": "zh",
}

# Wikipedia uses "YYYYMMDD.{lang}" format configs.
# Pinned to November 2023 dump.
WIKIPEDIA_LANG_MAP: dict[str, str] = {
    "ar": "20231101.ar",
    "be": "20231101.be",
    "bg": "20231101.bg",
    "br": "20231101.br",
    "cs": "20231101.cs",
    "cy": "20231101.cy",
    "da": "20231101.da",
    "de": "20231101.de",
    "el": "20231101.el",
    "en": "20231101.en",
    "eo": "20231101.eo",
    "es": "20231101.es",
    "et": "20231101.et",
    "fa": "20231101.fa",
    "fi": "20231101.fi",
    "fr": "20231101.fr",
    "ga": "20231101.ga",
    "gd": "20231101.gd",
    "he": "20231101.he",
    "hr": "20231101.hr",
    "hu": "20231101.hu",
    "id": "20231101.id",
    "is": "20231101.is",
    "it": "20231101.it",
    "ja": "20231101.ja",
    "kk": "20231101.kk",
    "ko": "20231101.ko",
    "lt": "20231101.lt",
    "lv": "20231101.lv",
    "mk": "20231101.mk",
    "ms": "20231101.ms",
    "mt": "20231101.mt",
    "nl": "20231101.nl",
    "no": "20231101.no",
    "pl": "20231101.pl",
    "pt": "20231101.pt",
    "ro": "20231101.ro",
    "ru": "20231101.ru",
    "sk": "20231101.sk",
    "sl": "20231101.sl",
    "sr": "20231101.sr",
    "sv": "20231101.sv",
    "tg": "20231101.tg",
    "th": "20231101.th",
    "tr": "20231101.tr",
    "uk": "20231101.uk",
    "ur": "20231101.ur",
    "vi": "20231101.vi",
    "zh": "20231101.zh",
}


# ---------------------------------------------------------------------------
# Shared caching utilities
# ---------------------------------------------------------------------------


def load_cached_articles(cache_dir: Path, max_articles: int) -> list[str]:
    """Load cached articles from per-file storage."""
    if not cache_dir.is_dir():
        return []
    texts: list[str] = []
    for p in sorted(cache_dir.iterdir()):
        if p.suffix != ".txt":
            continue
        if len(texts) >= max_articles:
            break
        texts.append(p.read_text(encoding="utf-8"))
    return texts


def save_article(cache_dir: Path, index: int, text: str) -> None:
    """Save a single article to the per-file cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{index:06d}.txt").write_text(text, encoding="utf-8")


_SENTINEL_FILE = ".exclusion_set_hash"


def _hash_exclusion_set(exclusions: frozenset[str]) -> str:
    """Compute a deterministic hash of the exclusion set."""
    combined = "\n".join(sorted(exclusions))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def write_cache_sentinel(cache_dir: Path, exclusions: frozenset[str]) -> None:
    """Write the exclusion set hash to a sentinel file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / _SENTINEL_FILE).write_text(
        _hash_exclusion_set(exclusions) + "\n",
        encoding="utf-8",
    )


def check_cache_validity(cache_dir: Path, exclusions: frozenset[str]) -> bool:
    """Check if the cached data matches the current exclusion set."""
    sentinel = cache_dir / _SENTINEL_FILE
    if not sentinel.is_file():
        return False
    stored = sentinel.read_text(encoding="utf-8").strip()
    return stored == _hash_exclusion_set(exclusions)


# ---------------------------------------------------------------------------
# Source-specific download functions
# ---------------------------------------------------------------------------


def _stream_from_hf(  # noqa: PLR0913
    dataset: str,
    config: str | None,
    split: str,
    text_field: str,
    source_name: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
    start_index: int,
    resume_stream_index: int = 0,
    data_files: dict[str, str] | None = None,
) -> tuple[list[str], int]:
    """Stream articles from a HuggingFace dataset, filtering by exclusions.

    ``resume_stream_index`` is the HF dataset stream position to resume from
    (skip articles before this index). This avoids re-processing articles
    already in cache on incremental downloads.

    ``data_files`` overrides ``config`` when the dataset doesn't support
    per-language configs (e.g. MADLAD-400 requires data_files glob patterns).

    Returns ``(accepted_texts, skipped_count)`` where ``skipped_count`` is the
    number of articles excluded by fingerprint or index.
    """
    from datasets import load_dataset  # noqa: PLC0415

    try:
        if data_files is not None:
            ds = load_dataset(
                dataset, data_files=data_files, split=split, streaming=True
            )
        else:
            ds = load_dataset(dataset, config, split=split, streaming=True)
    except Exception as exc:
        print(f"  WARNING: Could not load {dataset} ({config}): {exc}")
        return [], 0

    new_texts: list[str] = []
    skipped = 0
    try:
        for stream_idx, example in enumerate(ds):
            if stream_idx < resume_stream_index:
                continue
            if len(new_texts) >= needed:
                break
            text = example.get(text_field, "")
            if not text or len(text) <= 100:
                continue
            if is_excluded(
                text, exclusions, source=source_name, stream_index=stream_idx
            ):
                skipped += 1
                continue
            save_article(cache_dir, start_index + len(new_texts), text)
            new_texts.append(text)
    except Exception as exc:
        print(f"  WARNING: Error streaming {dataset} ({config}): {exc}")

    if skipped:
        print(f"    Skipped {skipped} excluded articles from {source_name}")
    return new_texts, skipped


def _count_cached_files(cache_dir: Path) -> int:
    """Count .txt files in a cache directory (for resume_stream_index).

    Note: this is a lower bound on the actual HF stream position, because
    excluded articles and short articles (<100 chars) were streamed but not
    cached. On interrupted-and-resumed downloads, some articles may be
    re-streamed and re-excluded. This is a performance inefficiency, not a
    correctness issue — excluded articles are always re-skipped.
    """
    if not cache_dir.is_dir():
        return 0
    return sum(1 for f in cache_dir.iterdir() if f.suffix == ".txt")


def get_culturax_texts(
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> tuple[list[str], int]:
    """Download CulturaX texts, skipping excluded articles.

    Returns (texts, skipped_count).
    """
    source_cache = cache_dir / "culturax" / lang
    cached = load_cached_articles(source_cache, needed)
    if len(cached) >= needed:
        return cached[:needed], 0

    remaining = needed - len(cached)
    resume_idx = _count_cached_files(source_cache)
    print(f"  CulturaX ({lang}): have {len(cached)}, need {remaining} more...")

    new_texts, skipped = _stream_from_hf(
        dataset=CULTURAX_DATASET,
        config=lang,
        split="train",
        text_field="text",
        source_name="culturax",
        needed=remaining,
        cache_dir=source_cache,
        exclusions=exclusions,
        start_index=len(cached),
        resume_stream_index=resume_idx,
    )

    result = cached + new_texts
    if new_texts:
        print(
            f"  CulturaX ({lang}): cached {len(new_texts)} new (total: {len(result)})"
        )
    return result, skipped


def get_madlad_texts(
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> tuple[list[str], int]:
    """Download MADLAD-400 texts, skipping excluded articles.

    Returns (texts, skipped_count).
    """
    madlad_lang = MADLAD_LANG_MAP.get(lang)
    if madlad_lang is None:
        print(f"  MADLAD-400 ({lang}): no language mapping, skipping")
        return [], 0

    source_cache = cache_dir / "madlad400" / lang
    cached = load_cached_articles(source_cache, needed)
    if len(cached) >= needed:
        return cached[:needed], 0

    remaining = needed - len(cached)
    resume_idx = _count_cached_files(source_cache)
    print(f"  MADLAD-400 ({lang}): have {len(cached)}, need {remaining} more...")

    # MADLAD-400 doesn't support per-language configs; use data_files globs
    new_texts, skipped = _stream_from_hf(
        dataset=MADLAD_DATASET,
        config=None,
        split="clean",
        text_field="text",
        source_name="madlad400",
        needed=remaining,
        cache_dir=source_cache,
        exclusions=exclusions,
        start_index=len(cached),
        resume_stream_index=resume_idx,
        data_files={
            "clean": f"data/{madlad_lang}/{madlad_lang}_clean_*.jsonl.gz",
        },
    )

    result = cached + new_texts
    if new_texts:
        print(
            f"  MADLAD-400 ({lang}): cached {len(new_texts)} new (total: {len(result)})"
        )
    return result, skipped


def get_wikipedia_texts(
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> tuple[list[str], int]:
    """Download Wikipedia texts, skipping excluded articles.

    Returns (texts, skipped_count).
    """
    config = WIKIPEDIA_LANG_MAP.get(lang)
    if config is None:
        print(f"  Wikipedia ({lang}): no language mapping, skipping")
        return [], 0

    source_cache = cache_dir / "wikipedia" / lang
    cached = load_cached_articles(source_cache, needed)
    if len(cached) >= needed:
        return cached[:needed], 0

    remaining = needed - len(cached)
    resume_idx = _count_cached_files(source_cache)
    print(f"  Wikipedia ({lang}): have {len(cached)}, need {remaining} more...")

    new_texts, skipped = _stream_from_hf(
        dataset=WIKIPEDIA_DATASET,
        config=config,
        split="train",
        text_field="text",
        source_name="wikipedia",
        needed=remaining,
        cache_dir=source_cache,
        exclusions=exclusions,
        start_index=len(cached),
        resume_stream_index=resume_idx,
    )

    result = cached + new_texts
    if new_texts:
        print(
            f"  Wikipedia ({lang}): cached {len(new_texts)} new (total: {len(result)})"
        )
    return result, skipped


@dataclass
class SourceStats:
    """Track article counts per source for a language.

    Note: this is intentionally NOT frozen because fields are set incrementally
    in get_texts(). This is an exception to the project convention of frozen
    dataclasses — SourceStats is a mutable accumulator used only during training,
    not a domain data type.
    """

    culturax: int = 0
    madlad400: int = 0
    wikipedia: int = 0
    excluded: int = 0


def get_texts(
    lang: str,
    max_samples: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> tuple[list[str], SourceStats]:
    """Download texts from multiple sources, filling to max_samples.

    Priority order: CulturaX -> MADLAD-400 -> Wikipedia.
    Returns (texts, stats) where stats tracks per-source article counts.
    """
    stats = SourceStats()
    texts, skipped = get_culturax_texts(lang, max_samples, cache_dir, exclusions)
    stats.culturax = len(texts)
    stats.excluded += skipped
    if len(texts) < max_samples:
        madlad, skipped = get_madlad_texts(
            lang, max_samples - len(texts), cache_dir, exclusions
        )
        stats.madlad400 = len(madlad)
        stats.excluded += skipped
        texts += madlad
    if len(texts) < max_samples:
        wiki, skipped = get_wikipedia_texts(
            lang, max_samples - len(texts), cache_dir, exclusions
        )
        stats.wikipedia = len(wiki)
        stats.excluded += skipped
        texts += wiki
    return texts, stats
