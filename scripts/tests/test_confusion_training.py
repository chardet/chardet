"""Tests for build-time confusion group computation and serialization."""

from __future__ import annotations

import tempfile
from pathlib import Path

from confusion_training import (
    compute_confusion_groups,
    compute_distinguishing_maps,
    deserialize_confusion_data,
    serialize_confusion_data,
)


def test_compute_confusion_groups_finds_ebcdic():
    """EBCDIC encodings (cp1140, cp500) should be in the same confusion group."""
    groups = compute_confusion_groups(threshold=0.80)
    cp1140_group = None
    for group in groups:
        if "CP1140" in group:
            cp1140_group = group
            break
    assert cp1140_group is not None, "CP1140 should be in a confusion group"
    assert "CP500" in cp1140_group, "CP500 should be in the same group as CP1140"


def test_compute_confusion_groups_finds_dos():
    """DOS encodings cp437 and cp865 differ by only 3 bytes — same group."""
    groups = compute_confusion_groups(threshold=0.80)
    cp437_group = None
    for group in groups:
        if "CP437" in group:
            cp437_group = group
            break
    assert cp437_group is not None
    assert "CP865" in cp437_group


def test_unrelated_encodings_not_grouped():
    """Unrelated encodings should not be in the same group."""
    groups = compute_confusion_groups(threshold=0.80)
    for group in groups:
        # KOI8-R (Cyrillic) should never be grouped with cp437 (DOS Latin)
        assert not ("KOI8-R" in group and "CP437" in group)


def test_distinguishing_map_cp1140_cp500():
    """cp1140 and cp500 should have exactly 8 distinguishing bytes."""
    maps = compute_distinguishing_maps(threshold=0.80)
    pair_key = (
        ("CP1140", "CP500") if ("CP1140", "CP500") in maps else ("CP500", "CP1140")
    )
    assert pair_key in maps
    diff_bytes, _categories = maps[pair_key]
    assert len(diff_bytes) == 8


def test_distinguishing_map_has_categories():
    """Each distinguishing byte should have Unicode category info."""
    maps = compute_distinguishing_maps(threshold=0.80)
    for diff_bytes, categories in maps.values():
        for byte_val in diff_bytes:
            assert byte_val in categories
            cat_a, cat_b = categories[byte_val]
            # Categories should be 2-char Unicode general category strings
            assert len(cat_a) == 2
            assert len(cat_b) == 2


def test_serialize_deserialize_roundtrip():
    """Serialization and deserialization should preserve all data."""
    maps = compute_distinguishing_maps(threshold=0.80)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        path = Path(f.name)
    try:
        serialize_confusion_data(maps, str(path))
        loaded = deserialize_confusion_data(str(path))
        assert len(loaded) == len(maps)
        for key in maps:
            assert key in loaded or (key[1], key[0]) in loaded
    finally:
        path.unlink(missing_ok=True)


def test_serialized_file_is_small():
    """Confusion data should be <10KB."""
    maps = compute_distinguishing_maps(threshold=0.80)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        path = Path(f.name)
    try:
        serialize_confusion_data(maps, str(path))
        assert path.stat().st_size < 10_000
    finally:
        path.unlink(missing_ok=True)
