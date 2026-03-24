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
