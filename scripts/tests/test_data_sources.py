"""Tests for multi-source data downloading."""

from __future__ import annotations

from pathlib import Path

from data_sources import (
    MADLAD_LANG_MAP,
    WIKIPEDIA_LANG_MAP,
    get_texts,
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
        save_article(
            cx_dir, i, f"CulturaX article {i} with enough content for testing."
        )

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
