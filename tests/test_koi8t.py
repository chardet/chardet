"""Test KOI8-T detection heuristic."""

from __future__ import annotations

from pathlib import Path

import pytest

import chardet
from chardet.enums import EncodingEra


def test_koi8t_with_tajik_bytes() -> None:
    """Data with Tajik-specific bytes should detect as KOI8-T, not KOI8-R."""
    test_dir = Path(__file__).parent / "data" / "koi8-t-tajik"
    if not test_dir.exists():
        pytest.skip("KOI8-T test data not available")
    test_file = next(test_dir.iterdir())
    data = test_file.read_bytes()
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "KOI8-T", (
        f"Expected KOI8-T but got {result['encoding']} "
        f"(confidence={result['confidence']:.2f})"
    )


def test_russian_text_stays_koi8r() -> None:
    """Pure Russian KOI8 text (no Tajik bytes) should remain KOI8-R."""
    test_dir = Path(__file__).parent / "data" / "koi8-r-russian"
    if not test_dir.exists():
        pytest.skip("KOI8-R test data not available")
    test_file = next(test_dir.iterdir())
    data = test_file.read_bytes()
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] != "KOI8-T", "Russian text should not detect as KOI8-T"
