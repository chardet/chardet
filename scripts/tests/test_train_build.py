"""Test the extracted _build_one_model function."""

from __future__ import annotations

from pathlib import Path

from data_sources import load_cached_articles
from exclusions import build_exclusion_set, fingerprint_text
from train import _build_one_model, _worker_text_cache


def test_build_one_model_returns_tuple(tmp_path: Path) -> None:
    """_build_one_model returns a 4-tuple even with no cached texts."""
    _worker_text_cache.clear()
    result = _build_one_model(
        lang="xx",  # non-existent language
        enc_name="utf-8",
        codec="utf-8",
        cache_dir=tmp_path / "nonexistent_cache",
        max_samples=10,
        min_weight=1,
    )
    assert isinstance(result, tuple)
    assert len(result) == 4
    key, bigrams, _samples, _total_bytes = result
    assert key == "xx/utf-8"
    # No cached texts for "xx", so bigrams should be None
    assert bigrams is None


def test_build_one_model_with_real_texts(tmp_path: Path) -> None:
    """_build_one_model produces bigrams from actual text."""
    _worker_text_cache.clear()
    # Create a fake cache directory with some text files
    # get_texts uses _article_cache_dir which builds: {cache_dir}/culturax/{lang}/
    lang_dir = tmp_path / "culturax" / "fr"
    lang_dir.mkdir(parents=True)
    for i in range(50):
        (lang_dir / f"{i:06d}.txt").write_text(
            "Le président de la République française a prononcé un discours "
            "devant l'Assemblée nationale sur les questions économiques.",
            encoding="utf-8",
        )

    result = _build_one_model(
        lang="fr",
        enc_name="iso-8859-1",
        codec="iso-8859-1",
        cache_dir=tmp_path,
        max_samples=100,
        min_weight=1,
    )
    key, bigrams, samples, total_bytes = result
    assert key == "fr/iso-8859-1"
    assert bigrams is not None
    assert len(bigrams) > 0
    assert samples > 0
    assert total_bytes > 0


def test_load_cached_articles_does_not_filter(tmp_path: Path) -> None:
    """load_cached_articles returns all cached articles without exclusion filtering.

    Exclusion filtering happens during the download phase (in get_texts /
    _stream_from_hf), not when loading from cache. This test verifies that
    cached articles are returned as-is — the exclusion mechanism is tested
    in test_exclusions.py and test_data_sources.py.
    """
    lang_dir = tmp_path / "culturax" / "en"
    lang_dir.mkdir(parents=True)
    articles = [
        "This is article zero with lots of unique content for testing.",
        "This is article one with different unique content for testing.",
        "This is article two with more different unique content for test.",
    ]
    for i, text in enumerate(articles):
        (lang_dir / f"{i:06d}.txt").write_text(text, encoding="utf-8")

    # Even though article 1 matches an exclusion fingerprint, loading
    # from cache returns all articles (filtering is a download concern).
    fp = fingerprint_text(articles[1])
    _exclusions = frozenset([fp])

    texts = load_cached_articles(lang_dir, max_articles=10)
    assert len(texts) == 3


def test_build_exclusion_set_with_real_structure(tmp_path: Path) -> None:
    """build_exclusion_set works with realistic test data directory structure."""
    text = "Le président de la République française a prononcé un discours."

    for enc in ("utf-8", "iso-8859-1"):
        enc_dir = tmp_path / f"{enc}-fr"
        enc_dir.mkdir()
        (enc_dir / "culturax_00000.txt").write_bytes(text.encode(enc))

    result = build_exclusion_set(tmp_path)
    assert len(result) == 1
    assert fingerprint_text(text) in result
