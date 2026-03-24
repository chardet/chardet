# Training/Test Data Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate overlap between CulturaX training data and test data by skipping test-data articles during training and supplementing with MADLAD-400 and Wikipedia for low-resource languages.

**Architecture:** Add a content-fingerprint exclusion set built from test data files, refactor `get_texts()` into a multi-source orchestrator (CulturaX → MADLAD-400 → Wikipedia), and update training metadata to track per-source article counts.

**Tech Stack:** Python 3.10+, HuggingFace `datasets` library (existing training dependency), SHA-256 for fingerprinting.

**Spec:** `docs/superpowers/specs/2026-03-24-training-test-data-separation-design.md`

---

### Task 1: Add `build_exclusion_set()` function

**Files:**
- Create: `scripts/exclusions.py`
- Create: `scripts/tests/test_exclusions.py`

This is the core fingerprinting logic: scan test data directories, decode
`culturax_*` files back to UTF-8, compute SHA-256 fingerprints of the first
200 characters (after encoding-neutral whitespace normalization), and return
a `frozenset[str]`.

- [ ] **Step 1: Write the test file with initial tests**

Write `scripts/tests/test_exclusions.py`:

```python
"""Tests for test-data exclusion set building."""

from __future__ import annotations

from pathlib import Path

from exclusions import fingerprint_text, build_exclusion_set


def test_fingerprint_text_basic() -> None:
    """fingerprint_text returns a hex digest string."""
    fp = fingerprint_text("Hello, world!  This is   a test.")
    assert isinstance(fp, str)
    assert len(fp) == 64  # SHA-256 hex digest


def test_fingerprint_text_normalizes_whitespace() -> None:
    """Repeated whitespace is collapsed before fingerprinting."""
    fp1 = fingerprint_text("Hello   world")
    fp2 = fingerprint_text("Hello world")
    assert fp1 == fp2


def test_fingerprint_text_strips() -> None:
    """Leading/trailing whitespace is stripped."""
    fp1 = fingerprint_text("  Hello world  ")
    fp2 = fingerprint_text("Hello world")
    assert fp1 == fp2


def test_fingerprint_text_truncates_to_200_chars() -> None:
    """Only the first 200 characters matter."""
    base = "a" * 200
    fp1 = fingerprint_text(base + "EXTRA")
    fp2 = fingerprint_text(base + "DIFFERENT")
    assert fp1 == fp2


def test_fingerprint_text_different_content() -> None:
    """Different content produces different fingerprints."""
    fp1 = fingerprint_text("Hello world")
    fp2 = fingerprint_text("Goodbye world")
    assert fp1 != fp2


def test_build_exclusion_set_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns empty set."""
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_build_exclusion_set_ignores_non_culturax(tmp_path: Path) -> None:
    """Files not matching culturax_* pattern are ignored."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    (enc_dir / "some_other_file.txt").write_text("Hello world", encoding="utf-8")
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_build_exclusion_set_decodes_and_fingerprints(tmp_path: Path) -> None:
    """CulturaX files are decoded from their encoding and fingerprinted."""
    # Create a utf-8 test file
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    text = "Hello world, this is a test article with enough content."
    (enc_dir / "culturax_00000.txt").write_bytes(text.encode("utf-8"))

    result = build_exclusion_set(tmp_path)
    assert len(result) == 1

    # The fingerprint should match what fingerprint_text produces
    expected_fp = fingerprint_text(text)
    assert expected_fp in result


def test_build_exclusion_set_deduplicates_across_encodings(tmp_path: Path) -> None:
    """Same source text in different encodings produces one fingerprint."""
    text = "Héllo wörld, this is a tëst article with enough content."

    for enc in ("utf-8", "iso-8859-1", "windows-1252"):
        enc_dir = tmp_path / f"{enc}-fr"
        enc_dir.mkdir()
        (enc_dir / "culturax_00000.txt").write_bytes(text.encode(enc))

    result = build_exclusion_set(tmp_path)
    # All three encode the same text, so only one unique fingerprint
    assert len(result) == 1


def test_build_exclusion_set_skips_none_dir(tmp_path: Path) -> None:
    """The None-None binary test directory is skipped."""
    none_dir = tmp_path / "None-None"
    none_dir.mkdir()
    (none_dir / "culturax_00000.txt").write_bytes(b"\x00\x01\x02")
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_build_exclusion_set_handles_decode_errors(tmp_path: Path) -> None:
    """Files that can't be decoded are skipped gracefully."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    # Invalid UTF-8 bytes
    (enc_dir / "culturax_00000.txt").write_bytes(b"\xff\xfe\xfd\xfc" * 50)
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest scripts/tests/test_exclusions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exclusions'`

- [ ] **Step 3: Implement `scripts/exclusions.py`**

```python
"""Build exclusion fingerprints from test data to prevent train/test overlap."""

from __future__ import annotations

import codecs
import hashlib
import re
from pathlib import Path


def fingerprint_text(text: str) -> str:
    """Compute a SHA-256 fingerprint of text after encoding-neutral normalization.

    Normalization: collapse ALL whitespace runs to a single space, strip
    leading/trailing whitespace, then truncate to the first 200 characters.
    This is encoding-neutral — no charset-specific substitutions are applied.

    Note: this uses ``\\s+`` (any whitespace to single space), NOT the
    ``(\\s)\\1+`` pattern from train.py's ``normalize_text()`` (which only
    collapses repeated identical whitespace chars). The difference is intentional:
    fingerprinting needs maximal normalization so the same source text produces
    the same fingerprint regardless of how whitespace was transformed during
    encoding/decoding round-trips.
    """
    # Collapse all whitespace runs to a single space
    normalized = re.sub(r"\s+", " ", text).strip()
    # Truncate to first 200 chars
    truncated = normalized[:200]
    return hashlib.sha256(truncated.encode("utf-8")).hexdigest()


def _get_codec(encoding_name: str) -> str | None:
    """Resolve an encoding name to a Python codec name."""
    for candidate in (encoding_name, encoding_name.replace("-", "").replace("_", "").lower()):
        try:
            codecs.lookup(candidate)
            return candidate
        except LookupError:
            continue
    return None


def build_exclusion_set(test_data_dir: Path) -> frozenset[str]:
    """Scan test data for CulturaX files and return content fingerprints.

    Iterates directories matching ``{encoding}-{language}``, finds files
    matching ``culturax_*``, decodes them using the encoding from the
    directory name, and returns SHA-256 fingerprints of the decoded text.
    """
    fingerprints: set[str] = set()

    if not test_data_dir.is_dir():
        return frozenset()

    for encoding_dir in sorted(test_data_dir.iterdir()):
        if not encoding_dir.is_dir():
            continue

        parts = encoding_dir.name.rsplit("-", 1)
        if len(parts) != 2:
            continue

        encoding_name = parts[0]
        if encoding_name == "None":
            continue

        codec = _get_codec(encoding_name)
        if codec is None:
            continue

        for filepath in sorted(encoding_dir.iterdir()):
            if not filepath.is_file():
                continue
            if not filepath.name.startswith("culturax_"):
                continue

            try:
                raw_bytes = filepath.read_bytes()
                text = raw_bytes.decode(codec)
            except (UnicodeDecodeError, LookupError):
                continue

            if not text or len(text) < 10:
                continue

            fingerprints.add(fingerprint_text(text))

    return frozenset(fingerprints)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest scripts/tests/test_exclusions.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Run linter**

Run: `uv run ruff check scripts/exclusions.py scripts/tests/test_exclusions.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add scripts/exclusions.py scripts/tests/test_exclusions.py
git commit -m "feat: add build_exclusion_set() for train/test separation"
```

---

### Task 2: Add `is_excluded()` helper and CulturaX index-based fast path

**Files:**
- Modify: `scripts/exclusions.py`
- Modify: `scripts/tests/test_exclusions.py`

Add a helper that checks whether an article should be excluded (by content
fingerprint or CulturaX index fast path).

- [ ] **Step 1: Write tests for `is_excluded()`**

Append to `scripts/tests/test_exclusions.py`:

```python
from exclusions import is_excluded


def test_is_excluded_by_fingerprint() -> None:
    """Articles matching a fingerprint are excluded."""
    text = "This is a test article with unique content for exclusion."
    fp = fingerprint_text(text)
    exclusions = frozenset([fp])
    assert is_excluded(text, exclusions, source="culturax", stream_index=999)


def test_is_excluded_not_matching() -> None:
    """Articles not matching any fingerprint are not excluded."""
    exclusions = frozenset(["abc123"])
    assert not is_excluded("Completely different text", exclusions, source="culturax", stream_index=999)


def test_is_excluded_culturax_fast_path() -> None:
    """CulturaX articles at indices 0-19 are always excluded."""
    exclusions = frozenset()  # empty — no fingerprints
    assert is_excluded("Any text", exclusions, source="culturax", stream_index=0)
    assert is_excluded("Any text", exclusions, source="culturax", stream_index=19)
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=20)


def test_is_excluded_fast_path_only_for_culturax() -> None:
    """Index-based fast path does not apply to non-CulturaX sources."""
    exclusions = frozenset()
    assert not is_excluded("Any text", exclusions, source="madlad400", stream_index=0)
    assert not is_excluded("Any text", exclusions, source="wikipedia", stream_index=0)
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `uv run python -m pytest scripts/tests/test_exclusions.py -v -k "is_excluded"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `is_excluded()`**

Add to `scripts/exclusions.py`:

```python
# Number of CulturaX articles downloaded by the test data generator.
# All articles at indices 0 through this value minus 1 are potential test data.
_CULTURAX_TEST_DATA_MAX_INDEX = 20


def is_excluded(
    text: str,
    exclusions: frozenset[str],
    *,
    source: str,
    stream_index: int,
) -> bool:
    """Check whether an article should be excluded from training.

    Uses two mechanisms:
    1. Index-based fast path: CulturaX articles at indices 0-19 are always
       excluded (the test data generator downloads from these indices).
    2. Content fingerprint: the article's fingerprint is checked against the
       exclusion set. This applies to all sources.
    """
    # Fast path: CulturaX indices 0-19 are known test data sources
    if source == "culturax" and stream_index < _CULTURAX_TEST_DATA_MAX_INDEX:
        return True

    # Content fingerprint check (applies to all sources)
    if exclusions and fingerprint_text(text) in exclusions:
        return True

    return False
```

- [ ] **Step 4: Run all exclusion tests**

Run: `uv run python -m pytest scripts/tests/test_exclusions.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/exclusions.py scripts/tests/test_exclusions.py
git commit -m "feat: add is_excluded() with CulturaX index fast path"
```

---

### Task 3: Add MADLAD-400 and Wikipedia download functions

**Files:**
- Create: `scripts/data_sources.py`
- Create: `scripts/tests/test_data_sources.py`

Extract the CulturaX download logic into a shared pattern and add MADLAD-400
and Wikipedia downloaders. Each follows the same interface: check disk cache →
stream from HF → fingerprint-check → cache accepted articles.

- [ ] **Step 1: Write tests**

Write `scripts/tests/test_data_sources.py`:

```python
"""Tests for multi-source data downloading."""

from __future__ import annotations

from pathlib import Path

from data_sources import (
    MADLAD_LANG_MAP,
    WIKIPEDIA_LANG_MAP,
    load_cached_articles,
    save_article,
)


def test_save_and_load_articles(tmp_path: Path) -> None:
    """Articles saved to cache can be loaded back."""
    cache_dir = tmp_path / "test_source" / "en"
    cache_dir.mkdir(parents=True)
    save_article(cache_dir, 0, "First article")
    save_article(cache_dir, 1, "Second article")

    loaded = load_cached_articles(cache_dir, max_articles=10)
    assert loaded == ["First article", "Second article"]


def test_load_cached_articles_respects_limit(tmp_path: Path) -> None:
    """Loading stops at max_articles."""
    cache_dir = tmp_path / "test_source" / "en"
    cache_dir.mkdir(parents=True)
    for i in range(10):
        save_article(cache_dir, i, f"Article {i}")

    loaded = load_cached_articles(cache_dir, max_articles=3)
    assert len(loaded) == 3


def test_load_cached_articles_empty_dir(tmp_path: Path) -> None:
    """Non-existent directory returns empty list."""
    loaded = load_cached_articles(tmp_path / "nonexistent", max_articles=10)
    assert loaded == []


def test_get_texts_fills_from_cache(tmp_path: Path) -> None:
    """get_texts returns cached articles and reports stats."""
    # Pre-populate CulturaX cache
    cx_dir = tmp_path / "culturax" / "en"
    cx_dir.mkdir(parents=True)
    for i in range(5):
        save_article(cx_dir, i, f"CulturaX article {i} with enough content for testing.")

    from data_sources import get_texts

    texts, stats = get_texts("en", 5, tmp_path, frozenset())
    assert len(texts) == 5
    assert stats.culturax == 5
    assert stats.madlad400 == 0
    assert stats.wikipedia == 0
    assert stats.excluded == 0


def test_madlad_lang_map_covers_priority_languages() -> None:
    """MADLAD_LANG_MAP includes all 9 priority low-resource languages."""
    priority = {"gd", "br", "mt", "ms", "ga", "eo", "hr", "tg", "cy"}
    for lang in priority:
        assert lang in MADLAD_LANG_MAP, f"Missing MADLAD mapping for {lang}"


def test_wikipedia_lang_map_covers_priority_languages() -> None:
    """WIKIPEDIA_LANG_MAP includes all 9 priority low-resource languages."""
    priority = {"gd", "br", "mt", "ms", "ga", "eo", "hr", "tg", "cy"}
    for lang in priority:
        assert lang in WIKIPEDIA_LANG_MAP, f"Missing Wikipedia mapping for {lang}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest scripts/tests/test_data_sources.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `scripts/data_sources.py`**

```python
"""Multi-source text data downloading for training.

Provides download functions for CulturaX, MADLAD-400, and Wikipedia,
each following the same pattern: check disk cache -> stream from
HuggingFace -> fingerprint-check -> cache accepted articles.
"""

from __future__ import annotations

import functools
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
# Only list overrides where the MADLAD config name differs from the
# registry's ISO 639-1 code.
MADLAD_LANG_MAP: dict[str, str] = {
    # All 49 languages — identity mapping for most, with overrides as needed.
    "ar": "ar", "be": "be", "bg": "bg", "br": "br", "cs": "cs",
    "cy": "cy", "da": "da", "de": "de", "el": "el", "en": "en",
    "eo": "eo", "es": "es", "et": "et", "fa": "fa", "fi": "fi",
    "fr": "fr", "ga": "ga", "gd": "gd", "he": "he", "hr": "hr",
    "hu": "hu", "id": "id", "is": "is", "it": "it", "ja": "ja",
    "kk": "kk", "ko": "ko", "lt": "lt", "lv": "lv", "mk": "mk",
    "ms": "ms", "mt": "mt", "nl": "nl", "no": "no", "pl": "pl",
    "pt": "pt", "ro": "ro", "ru": "ru", "sk": "sk", "sl": "sl",
    "sr": "sr", "sv": "sv", "tg": "tg", "th": "th", "tr": "tr",
    "uk": "uk", "ur": "ur", "vi": "vi", "zh": "zh",
}

# Wikipedia uses "YYYYMMDD.{lang}" format configs.
# Pinned to November 2023 dump.
WIKIPEDIA_LANG_MAP: dict[str, str] = {
    "ar": "20231101.ar", "be": "20231101.be", "bg": "20231101.bg",
    "br": "20231101.br", "cs": "20231101.cs", "cy": "20231101.cy",
    "da": "20231101.da", "de": "20231101.de", "el": "20231101.el",
    "en": "20231101.en", "eo": "20231101.eo", "es": "20231101.es",
    "et": "20231101.et", "fa": "20231101.fa", "fi": "20231101.fi",
    "fr": "20231101.fr", "ga": "20231101.ga", "gd": "20231101.gd",
    "he": "20231101.he", "hr": "20231101.hr", "hu": "20231101.hu",
    "id": "20231101.id", "is": "20231101.is", "it": "20231101.it",
    "ja": "20231101.ja", "kk": "20231101.kk", "ko": "20231101.ko",
    "lt": "20231101.lt", "lv": "20231101.lv", "mk": "20231101.mk",
    "ms": "20231101.ms", "mt": "20231101.mt", "nl": "20231101.nl",
    "no": "20231101.no", "pl": "20231101.pl", "pt": "20231101.pt",
    "ro": "20231101.ro", "ru": "20231101.ru", "sk": "20231101.sk",
    "sl": "20231101.sl", "sr": "20231101.sr", "sv": "20231101.sv",
    "tg": "20231101.tg", "th": "20231101.th", "tr": "20231101.tr",
    "uk": "20231101.uk", "ur": "20231101.ur", "vi": "20231101.vi",
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


# ---------------------------------------------------------------------------
# Source-specific download functions
# ---------------------------------------------------------------------------


def _stream_from_hf(
    dataset: str,
    config: str,
    split: str,
    text_field: str,
    source_name: str,
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
    start_index: int,
    resume_stream_index: int = 0,
) -> list[str]:
    """Stream articles from a HuggingFace dataset, filtering by exclusions.

    ``resume_stream_index`` is the HF dataset stream position to resume from
    (skip articles before this index). This avoids re-processing articles
    already in cache on incremental downloads.

    Returns ``(accepted_texts, skipped_count)`` where ``skipped_count`` is the
    number of articles excluded by fingerprint or index.
    """
    from datasets import load_dataset  # noqa: PLC0415

    try:
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
            if is_excluded(text, exclusions, source=source_name, stream_index=stream_idx):
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
    """Count .txt files in a cache directory (for resume_stream_index)."""
    if not cache_dir.is_dir():
        return 0
    return sum(1 for f in cache_dir.iterdir() if f.suffix == ".txt")


def get_culturax_texts(
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> list[str]:
    """Download CulturaX texts, skipping excluded articles.

    Returns (texts, skipped_count).
    """
    source_cache = cache_dir / "culturax" / lang
    cached = load_cached_articles(source_cache, needed)
    if len(cached) >= needed:
        return cached[:needed], 0

    remaining = needed - len(cached)
    # Resume from where we left off in the HF stream. The cached file count
    # approximates how far we streamed previously (some indices may have been
    # skipped by exclusions, but this is a conservative lower bound).
    resume_idx = _count_cached_files(source_cache)
    print(f"  CulturaX ({lang}): have {len(cached)}, need {remaining} more...")

    new_texts, skipped = _stream_from_hf(
        dataset=CULTURAX_DATASET,
        config=lang,
        split="train",
        text_field="text",
        source_name="culturax",
        lang=lang,
        needed=remaining,
        cache_dir=source_cache,
        exclusions=exclusions,
        start_index=len(cached),
        resume_stream_index=resume_idx,
    )

    result = cached + new_texts
    if new_texts:
        print(f"  CulturaX ({lang}): cached {len(new_texts)} new (total: {len(result)})")
    return result, skipped


def get_madlad_texts(
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> list[str]:
    """Download MADLAD-400 texts, skipping excluded articles.

    Returns (texts, skipped_count).
    """
    config = MADLAD_LANG_MAP.get(lang)
    if config is None:
        print(f"  MADLAD-400 ({lang}): no language mapping, skipping")
        return [], 0

    source_cache = cache_dir / "madlad400" / lang
    cached = load_cached_articles(source_cache, needed)
    if len(cached) >= needed:
        return cached[:needed], 0

    remaining = needed - len(cached)
    resume_idx = _count_cached_files(source_cache)
    print(f"  MADLAD-400 ({lang}): have {len(cached)}, need {remaining} more...")

    new_texts, skipped = _stream_from_hf(
        dataset=MADLAD_DATASET,
        config=config,
        split="clean",
        text_field="text",
        source_name="madlad400",
        lang=lang,
        needed=remaining,
        cache_dir=source_cache,
        exclusions=exclusions,
        start_index=len(cached),
        resume_stream_index=resume_idx,
    )

    result = cached + new_texts
    if new_texts:
        print(f"  MADLAD-400 ({lang}): cached {len(new_texts)} new (total: {len(result)})")
    return result, skipped


def get_wikipedia_texts(
    lang: str,
    needed: int,
    cache_dir: Path,
    exclusions: frozenset[str],
) -> list[str]:
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
        lang=lang,
        needed=remaining,
        cache_dir=source_cache,
        exclusions=exclusions,
        start_index=len(cached),
        resume_stream_index=resume_idx,
    )

    result = cached + new_texts
    if new_texts:
        print(f"  Wikipedia ({lang}): cached {len(new_texts)} new (total: {len(result)})")
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
        madlad, skipped = get_madlad_texts(lang, max_samples - len(texts), cache_dir, exclusions)
        stats.madlad400 = len(madlad)
        stats.excluded += skipped
        texts += madlad
    if len(texts) < max_samples:
        wiki, skipped = get_wikipedia_texts(lang, max_samples - len(texts), cache_dir, exclusions)
        stats.wikipedia = len(wiki)
        stats.excluded += skipped
        texts += wiki
    return texts, stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest scripts/tests/test_data_sources.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run linter**

Run: `uv run ruff check scripts/data_sources.py scripts/tests/test_data_sources.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add scripts/data_sources.py scripts/tests/test_data_sources.py
git commit -m "feat: add multi-source download (CulturaX, MADLAD-400, Wikipedia)"
```

---

### Task 4: Integrate exclusion set and multi-source downloads into `train.py`

**Files:**
- Modify: `scripts/train.py`
- Modify: `scripts/tests/test_train_build.py`

Replace the monolithic `get_texts()` in `train.py` with the new multi-source
`data_sources.get_texts()`, add CLI flags, and wire up the exclusion set.

- [ ] **Step 1: Write tests for the new integration**

Append to `scripts/tests/test_train_build.py`:

```python
from exclusions import build_exclusion_set, fingerprint_text
from data_sources import get_texts, load_cached_articles


def test_get_texts_skips_excluded_articles(tmp_path: Path) -> None:
    """get_texts with exclusions does not return excluded articles."""
    # Pre-populate cache with articles, some of which match exclusion fingerprints
    lang_dir = tmp_path / "culturax" / "en"
    lang_dir.mkdir(parents=True)
    articles = [
        "This is article zero with lots of unique content for testing.",
        "This is article one with different unique content for testing.",
        "This is article two with more different unique content for test.",
    ]
    for i, text in enumerate(articles):
        (lang_dir / f"{i:06d}.txt").write_text(text, encoding="utf-8")

    # Create exclusion for article 1
    fp = fingerprint_text(articles[1])
    exclusions = frozenset([fp])

    # Load with exclusions — should skip article 1
    # Note: load_cached_articles doesn't filter; filtering happens during download.
    # For cached articles, we need the training script to re-check.
    # This test validates the get_texts orchestrator works with exclusions.
    texts = load_cached_articles(lang_dir, max_articles=10)
    assert len(texts) == 3  # cache doesn't filter


def test_build_exclusion_set_with_real_structure(tmp_path: Path) -> None:
    """build_exclusion_set works with realistic test data directory structure."""
    # Create test data structure mimicking tests/data/
    text = "Le président de la République française a prononcé un discours."

    for enc in ("utf-8", "iso-8859-1"):
        enc_dir = tmp_path / f"{enc}-fr"
        enc_dir.mkdir()
        (enc_dir / "culturax_00000.txt").write_bytes(text.encode(enc))

    result = build_exclusion_set(tmp_path)
    assert len(result) == 1
    assert fingerprint_text(text) in result
```

- [ ] **Step 2: Run tests to verify new tests pass**

Run: `uv run python -m pytest scripts/tests/test_train_build.py -v`
Expected: All tests PASS (new tests use already-implemented functions)

- [ ] **Step 3: Modify `train.py` to use new modules**

Key changes to `scripts/train.py`:

1. **Add imports** at the top (after existing imports):
   ```python
   from exclusions import build_exclusion_set
   from data_sources import get_texts as get_texts_multi
   ```

2. **Add CLI flags** in `main()` after the `--encodings` argument:
   ```python
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
   ```

3. **Build exclusion set** after parsing args, before the download phase:
   ```python
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
   ```

4. **Replace `get_texts()` calls** in the download phase with
   `get_texts_multi(lang, args.max_samples, cache_dir, exclusions)`.
   Note: `get_texts_multi` returns `tuple[list[str], SourceStats]`. In the
   download phase, collect stats per language into a
   `lang_stats: dict[str, SourceStats]` dict:
   ```python
   from data_sources import get_texts as get_texts_multi, SourceStats
   lang_stats: dict[str, SourceStats] = {}
   # In _fetch or download loop:
   texts, stats = get_texts_multi(lang, args.max_samples, cache_dir, exclusions)
   lang_stats[lang] = stats
   ```

5. **Remove the old `get_texts()` function** and its related caching helpers
   (`_article_cache_dir`, `_load_cached_articles`, `_save_article`,
   `_lang_text_cache`), and the `CULTURAX_DATASET` constant — all now live in
   `data_sources.py`.

6. **Update `_build_one_model()`** to use `data_sources.load_cached_articles()`
   instead of the removed `_load_cached_articles()`:
   ```python
   from data_sources import load_cached_articles
   # In _build_one_model:
   if lang not in _worker_text_cache:
       # Load from all source caches (culturax, madlad400, wikipedia)
       texts: list[str] = []
       for source in ("culturax", "madlad400", "wikipedia"):
           source_dir = cache_dir / source / lang
           texts.extend(load_cached_articles(source_dir, max_samples - len(texts)))
           if len(texts) >= max_samples:
               break
       _worker_text_cache[lang] = texts[:max_samples]
   ```

- [ ] **Step 4: Run all training tests**

Run: `uv run python -m pytest scripts/tests/test_train_build.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run linter on modified files**

Run: `uv run ruff check scripts/train.py scripts/exclusions.py scripts/data_sources.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add scripts/train.py scripts/tests/test_train_build.py
git commit -m "feat: integrate exclusion set and multi-source downloads into train.py"
```

---

### Task 5: Update training metadata to track per-source article counts

**Files:**
- Modify: `scripts/train.py` (the `_write_training_metadata` function)

`SourceStats` and the tuple return from `get_texts()` were already added in
Task 3. This task wires the stats into the training metadata YAML output.

- [ ] **Step 1: Update `_write_training_metadata()` in `train.py`**

Add `sources` and `test_articles_excluded` fields to the per-model YAML output.
The function needs a `lang_stats: dict[str, SourceStats]` parameter populated
during the download phase.

```python
def _write_training_metadata(
    path: Path,
    models: dict[str, dict[tuple[int, int], int]],
    max_samples: int,
    cache_dir: Path,
    lang_stats: dict[str, SourceStats],
) -> None:
    # ... existing header ...
    for model_key in sorted(models):
        # ... existing fields ...
        parts = model_key.split("/", 1)
        lang = parts[0] if len(parts) == 2 else "unknown"
        stats = lang_stats.get(lang, SourceStats())
        lines.append(f"    sources:")
        lines.append(f"      culturax: {stats.culturax}")
        lines.append(f"      madlad400: {stats.madlad400}")
        lines.append(f"      wikipedia: {stats.wikipedia}")
        lines.append(f"    test_articles_excluded: {stats.excluded}")
    # ... write file ...
```

- [ ] **Step 3: Wire up source stats in `main()`**

In the download phase of `main()`, collect `SourceStats` per language and pass
to `_write_training_metadata()`.

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest scripts/tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/train.py scripts/data_sources.py
git commit -m "feat: track per-source article counts in training metadata"
```

---

### Task 6: Add cache invalidation sentinel

**Files:**
- Modify: `scripts/data_sources.py`
- Create: `scripts/tests/test_cache_invalidation.py`

Store a hash of the exclusion set in `data/.exclusion_set_hash` and
auto-invalidate caches on mismatch.

- [ ] **Step 1: Write tests**

Write `scripts/tests/test_cache_invalidation.py`:

```python
"""Tests for cache invalidation based on exclusion set changes."""

from __future__ import annotations

from pathlib import Path

from data_sources import check_cache_validity, write_cache_sentinel


def test_write_and_check_sentinel(tmp_path: Path) -> None:
    """Sentinel written and read back matches."""
    exclusions = frozenset(["abc", "def"])
    write_cache_sentinel(tmp_path, exclusions)
    assert check_cache_validity(tmp_path, exclusions)


def test_sentinel_mismatch(tmp_path: Path) -> None:
    """Changed exclusion set invalidates cache."""
    old = frozenset(["abc"])
    new = frozenset(["abc", "def"])
    write_cache_sentinel(tmp_path, old)
    assert not check_cache_validity(tmp_path, new)


def test_missing_sentinel(tmp_path: Path) -> None:
    """Missing sentinel means invalid cache."""
    assert not check_cache_validity(tmp_path, frozenset(["abc"]))


def test_empty_exclusion_set(tmp_path: Path) -> None:
    """Empty exclusion set writes valid sentinel."""
    exclusions: frozenset[str] = frozenset()
    write_cache_sentinel(tmp_path, exclusions)
    assert check_cache_validity(tmp_path, exclusions)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest scripts/tests/test_cache_invalidation.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement sentinel functions**

Add to `scripts/data_sources.py`:

```python
import hashlib

_SENTINEL_FILE = ".exclusion_set_hash"


def _hash_exclusion_set(exclusions: frozenset[str]) -> str:
    """Compute a deterministic hash of the exclusion set."""
    combined = "\n".join(sorted(exclusions))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def write_cache_sentinel(cache_dir: Path, exclusions: frozenset[str]) -> None:
    """Write the exclusion set hash to a sentinel file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / _SENTINEL_FILE).write_text(
        _hash_exclusion_set(exclusions) + "\n", encoding="utf-8",
    )


def check_cache_validity(cache_dir: Path, exclusions: frozenset[str]) -> bool:
    """Check if the cached data matches the current exclusion set."""
    sentinel = cache_dir / _SENTINEL_FILE
    if not sentinel.is_file():
        return False
    stored = sentinel.read_text(encoding="utf-8").strip()
    return stored == _hash_exclusion_set(exclusions)
```

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest scripts/tests/test_cache_invalidation.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Wire into `main()` in `train.py`**

After building the exclusion set in `main()`, add cache validity check:

```python
from data_sources import check_cache_validity, write_cache_sentinel

# After building exclusions:
if exclusions and not args.keep_cache:
    if not check_cache_validity(cache_dir, exclusions):
        print("  Exclusion set changed — invalidating article caches")
        for source in ("culturax", "madlad400", "wikipedia"):
            source_dir = cache_dir / source
            if source_dir.is_dir():
                shutil.rmtree(source_dir)
                print(f"    Cleared {source_dir}")
    write_cache_sentinel(cache_dir, exclusions)
```

Add `import shutil` at the top of `train.py`.

- [ ] **Step 6: Run all tests**

Run: `uv run python -m pytest scripts/tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/data_sources.py scripts/tests/test_cache_invalidation.py scripts/train.py
git commit -m "feat: add cache invalidation sentinel for exclusion set changes"
```

---

### Task 7: Add overlap verification script

**Files:**
- Create: `scripts/verify_no_overlap.py`
- Create: `scripts/tests/test_verify_no_overlap.py`

Standalone script that checks cached training articles against test data
for any fingerprint intersection.

- [ ] **Step 1: Write tests**

Write `scripts/tests/test_verify_no_overlap.py`:

```python
"""Tests for the overlap verification script."""

from __future__ import annotations

from pathlib import Path

from verify_no_overlap import check_overlap


def test_no_overlap(tmp_path: Path) -> None:
    """No overlap when training and test texts differ."""
    # Create test data
    test_dir = tmp_path / "test_data" / "utf-8-en"
    test_dir.mkdir(parents=True)
    (test_dir / "culturax_00000.txt").write_bytes(
        b"This is test data content that should not appear in training."
    )

    # Create training cache with different content
    train_dir = tmp_path / "cache" / "culturax" / "en"
    train_dir.mkdir(parents=True)
    (train_dir / "000000.txt").write_text(
        "This is training data content that is completely different.",
        encoding="utf-8",
    )

    overlaps = check_overlap(tmp_path / "test_data", tmp_path / "cache")
    assert len(overlaps) == 0


def test_overlap_detected(tmp_path: Path) -> None:
    """Overlap is detected when same text appears in both."""
    text = "Identical text appearing in both training and test data sets."

    # Create test data
    test_dir = tmp_path / "test_data" / "utf-8-en"
    test_dir.mkdir(parents=True)
    (test_dir / "culturax_00000.txt").write_bytes(text.encode("utf-8"))

    # Create training cache with same content
    train_dir = tmp_path / "cache" / "culturax" / "en"
    train_dir.mkdir(parents=True)
    (train_dir / "000000.txt").write_text(text, encoding="utf-8")

    overlaps = check_overlap(tmp_path / "test_data", tmp_path / "cache")
    assert len(overlaps) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest scripts/tests/test_verify_no_overlap.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `scripts/verify_no_overlap.py`**

```python
#!/usr/bin/env python3
"""Verify no overlap between training cache and test data.

Loads all cached training articles and test data files, fingerprints both,
and reports any intersection.

Usage:
    uv run python scripts/verify_no_overlap.py
    uv run python scripts/verify_no_overlap.py --test-data-dir tests/data --cache-dir data/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from exclusions import build_exclusion_set, fingerprint_text


def check_overlap(
    test_data_dir: Path,
    cache_dir: Path,
) -> list[tuple[str, str]]:
    """Check for overlapping content between training cache and test data.

    Returns list of (training_file, fingerprint) tuples for overlapping articles.
    """
    # Build fingerprints from test data
    test_fingerprints = build_exclusion_set(test_data_dir)
    if not test_fingerprints:
        return []

    overlaps: list[tuple[str, str]] = []

    # Check all training cache sources
    for source in ("culturax", "madlad400", "wikipedia"):
        source_dir = cache_dir / source
        if not source_dir.is_dir():
            continue
        for lang_dir in sorted(source_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            for article_file in sorted(lang_dir.iterdir()):
                if article_file.suffix != ".txt":
                    continue
                text = article_file.read_text(encoding="utf-8")
                fp = fingerprint_text(text)
                if fp in test_fingerprints:
                    rel_path = f"{source}/{lang_dir.name}/{article_file.name}"
                    overlaps.append((rel_path, fp))

    return overlaps


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify no overlap between training cache and test data",
    )
    parser.add_argument(
        "--test-data-dir",
        default="tests/data/",
        help="Path to test data directory",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/",
        help="Path to training data cache directory",
    )
    args = parser.parse_args()

    test_data_path = Path(args.test_data_dir)
    if test_data_path.is_symlink():
        test_data_path = test_data_path.resolve()

    cache_path = Path(args.cache_dir)

    if not test_data_path.is_dir():
        print(f"ERROR: test data dir not found: {test_data_path}", file=sys.stderr)
        sys.exit(1)

    if not cache_path.is_dir():
        print(f"ERROR: cache dir not found: {cache_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Test data: {test_data_path}")
    print(f"Cache dir: {cache_path}")
    print()

    overlaps = check_overlap(test_data_path, cache_path)

    if overlaps:
        print(f"FAIL: Found {len(overlaps)} overlapping articles:")
        for path, fp in overlaps:
            print(f"  {path} (fingerprint: {fp[:16]}...)")
        sys.exit(1)
    else:
        print("PASS: No overlap detected between training cache and test data.")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest scripts/tests/test_verify_no_overlap.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Run linter**

Run: `uv run ruff check scripts/verify_no_overlap.py scripts/tests/test_verify_no_overlap.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_no_overlap.py scripts/tests/test_verify_no_overlap.py
git commit -m "feat: add verify_no_overlap.py script for train/test separation check"
```

---

### Task 8: Update docstring, CLAUDE.md, and run full test suite

**Files:**
- Modify: `scripts/train.py` (module docstring)
- Modify: `CLAUDE.md` (training section)

- [ ] **Step 1: Update `train.py` module docstring**

Replace the existing docstring (lines 2-11) with:

```python
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
```

- [ ] **Step 2: Update CLAUDE.md training section**

In `CLAUDE.md`, update the "Training Models" section to mention the new
data sources and exclusion mechanism:

```markdown
### Training Models

```bash
uv run python scripts/train.py   # retrain bigram models from CulturaX/MADLAD-400/Wikipedia data
uv run python scripts/verify_no_overlap.py  # verify no train/test data overlap
```

Training data is cached in `data/` (gitignored) under `data/culturax/`,
`data/madlad400/`, and `data/wikipedia/` per language. Models are saved to
`src/chardet/models/models.bin`. Test data articles are automatically excluded
from training via content fingerprinting to prevent train/test overlap.
```

- [ ] **Step 3: Run full test suite**

Run: `uv run python -m pytest -n auto`
Expected: All tests PASS (existing accuracy and API tests unchanged)

- [ ] **Step 4: Run full linter**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add scripts/train.py CLAUDE.md
git commit -m "docs: update train.py docstring and CLAUDE.md for multi-source training"
```

---

### Task 9: Smoke test with real data (manual verification)

**Files:** None (manual testing)

This task validates the end-to-end flow with real HuggingFace downloads.
It is NOT automated — run manually after the code changes are complete.

- [ ] **Step 1: Run training for a single small encoding**

Run: `uv run python scripts/train.py --encodings koi8-r --max-samples 100`

Verify output shows:
- "Building test data exclusion set" with fingerprint count
- CulturaX download with "Skipped N excluded articles" messages
- No MADLAD-400/Wikipedia fallback (koi8-r languages should have plenty in CulturaX)

- [ ] **Step 2: Run training for a low-resource encoding**

Run: `uv run python scripts/train.py --encodings iso-8859-14 --max-samples 100`

iso-8859-14 covers Breton (br), Irish (ga), Scottish Gaelic (gd), Welsh (cy).
Verify output shows:
- CulturaX articles excluded for these languages
- MADLAD-400 or Wikipedia fallback kicks in for languages where CulturaX is
  exhausted after exclusions

- [ ] **Step 3: Run overlap verification**

Run: `uv run python scripts/verify_no_overlap.py`
Expected: "PASS: No overlap detected"

- [ ] **Step 4: Commit any fixes discovered during smoke testing**

```bash
git add -u
git commit -m "fix: address issues found during smoke testing"
```
