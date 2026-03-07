"""Tests for runtime confusion group resolution."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest

from chardet.pipeline import DetectionResult
from chardet.pipeline.confusion import (
    load_confusion_data,
    resolve_by_bigram_rescore,
    resolve_by_category_voting,
    resolve_confusion_groups,
)


def test_load_confusion_data():
    """Loading confusion data from the bundled file should return valid maps."""
    maps = load_confusion_data()
    assert len(maps) > 0
    found_ebcdic = any(
        ("CP1140" in key[0] and "CP500" in key[1])
        or ("CP500" in key[0] and "CP1140" in key[1])
        for key in maps
    )
    assert found_ebcdic


def test_category_voting_prefers_letter_over_symbol():
    """Category voting should prefer letter (Ll) over symbol (So)."""
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "So")}
    data = bytes([0x41, 0xD5, 0x42])
    winner = resolve_by_category_voting(data, "enc_a", "enc_b", diff_bytes, categories)
    assert winner == "enc_a"


def test_category_voting_returns_none_on_no_distinguishing_bytes():
    """Category voting should return None when no distinguishing bytes are in data."""
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "So")}
    data = bytes([0x41, 0x42, 0x43])
    winner = resolve_by_category_voting(data, "enc_a", "enc_b", diff_bytes, categories)
    assert winner is None


def test_bigram_rescore_returns_valid_result():
    """Bigram re-scoring should return one of the encodings or None."""
    from chardet.models import load_models

    models = load_models()
    if not models:
        return
    diff_bytes = frozenset({0xD5})
    data = bytes([0x41, 0xD5, 0x42, 0xD5, 0x43])
    result = resolve_by_bigram_rescore(data, "CP850", "CP858", diff_bytes)
    assert result in ("CP850", "CP858", None)


def test_resolve_confusion_groups_no_change_when_unrelated():
    """Unrelated encodings should not be reordered by confusion resolution."""
    results = [
        DetectionResult(encoding="UTF-8", confidence=0.95, language=None),
        DetectionResult(encoding="KOI8-R", confidence=0.80, language="Russian"),
    ]
    resolved = resolve_confusion_groups(b"Hello world", results)
    assert resolved[0].encoding == "UTF-8"


def test_resolve_confusion_groups_preserves_all_results():
    """Confusion resolution should preserve all results, only reorder."""
    results = [
        DetectionResult(encoding="CP1140", confidence=0.95, language="English"),
        DetectionResult(encoding="CP500", confidence=0.94, language="English"),
        DetectionResult(encoding="Windows-1252", confidence=0.50, language="English"),
    ]
    resolved = resolve_confusion_groups(bytes(range(256)), results)
    assert len(resolved) == len(results)
    resolved_encs = {r.encoding for r in resolved}
    assert resolved_encs == {"CP1140", "CP500", "Windows-1252"}


def test_load_confusion_data_empty_file():
    """Empty confusion.bin should emit RuntimeWarning and return empty dict."""
    import chardet.pipeline.confusion as mod

    original = mod._CONFUSION_CACHE
    try:
        mod._CONFUSION_CACHE = None
        mock_ref = MagicMock()
        mock_ref.read_bytes.return_value = b""
        with (
            patch.object(
                mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
            ),
            pytest.warns(RuntimeWarning, match="confusion.bin is empty"),
        ):
            result = mod.load_confusion_data()
        assert result == {}
    finally:
        mod._CONFUSION_CACHE = original


def test_load_confusion_data_corrupt_file():
    """Corrupt confusion.bin should raise ValueError."""
    import chardet.pipeline.confusion as mod

    original = mod._CONFUSION_CACHE
    try:
        mod._CONFUSION_CACHE = None
        mock_ref = MagicMock()
        # Valid num_pairs=1 but truncated after that
        mock_ref.read_bytes.return_value = struct.pack("!H", 1)
        with (
            patch.object(
                mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
            ),
            pytest.raises(ValueError, match=r"corrupt confusion\.bin"),
        ):
            mod.load_confusion_data()
    finally:
        mod._CONFUSION_CACHE = original


def test_resolve_confusion_groups_single_result():
    """A single result should pass through unchanged."""
    results = [DetectionResult(encoding="UTF-8", confidence=0.95, language=None)]
    resolved = resolve_confusion_groups(b"Hello", results)
    assert resolved is results


def test_resolve_by_bigram_rescore_empty_freq():
    """When no bigrams contain distinguishing bytes, return None."""
    diff_bytes = frozenset({0xFE})
    data = b"Hello world, this is plain ASCII text without any high bytes at all."
    result = resolve_by_bigram_rescore(data, "enc_a", "enc_b", diff_bytes)
    assert result is None


def test_resolve_by_bigram_rescore_short_data():
    """Data shorter than 2 bytes cannot form any bigrams."""
    diff_bytes = frozenset({0xFE})
    result = resolve_by_bigram_rescore(b"x", "enc_a", "enc_b", diff_bytes)
    assert result is None


def test_resolve_confusion_groups_none_encoding():
    """When top result has encoding=None (binary), skip confusion resolution."""
    results = [
        DetectionResult(encoding=None, confidence=0.95, language=None),
        DetectionResult(encoding="UTF-8", confidence=0.90, language=None),
    ]
    resolved = resolve_confusion_groups(b"Hello", results)
    assert resolved is results
