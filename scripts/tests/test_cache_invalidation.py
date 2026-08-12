"""Tests for cache invalidation based on exclusion set changes."""

from __future__ import annotations

from pathlib import Path

from data_sources import check_cache_validity, write_cache_sentinel
from exclusions import ExclusionIndex


def _index(*texts: str) -> ExclusionIndex:
    index = ExclusionIndex()
    for text in texts:
        index.add(text)
    return index


_ONE = "A first indexed test article, long enough to carry its own sentence."
_TWO = "A second indexed test article, also long enough to be worth indexing."


def test_write_and_check_sentinel(tmp_path: Path) -> None:
    """Sentinel written and read back matches."""
    exclusions = _index(_ONE, _TWO)
    write_cache_sentinel(tmp_path, exclusions)
    assert check_cache_validity(tmp_path, exclusions)


def test_sentinel_mismatch(tmp_path: Path) -> None:
    """Changed exclusion set invalidates cache."""
    write_cache_sentinel(tmp_path, _index(_ONE))
    assert not check_cache_validity(tmp_path, _index(_ONE, _TWO))


def test_missing_sentinel(tmp_path: Path) -> None:
    """Missing sentinel means invalid cache."""
    assert not check_cache_validity(tmp_path, _index(_ONE))


def test_empty_exclusion_set(tmp_path: Path) -> None:
    """Empty exclusion set writes valid sentinel."""
    exclusions = ExclusionIndex()
    write_cache_sentinel(tmp_path, exclusions)
    assert check_cache_validity(tmp_path, exclusions)
