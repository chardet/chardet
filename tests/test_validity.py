# tests/test_validity.py
from __future__ import annotations

from chardet.enums import EncodingEra
from chardet.pipeline.validity import filter_by_validity
from chardet.registry import get_candidates


def test_utf8_text_valid_under_utf8():
    data = "Héllo wörld".encode()
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "UTF-8" in valid_names


def test_latin1_text_invalid_under_strict_multibyte():
    data = "Héllo".encode("latin-1")
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "ISO-8859-1" in valid_names


def test_shift_jis_text_valid_under_shift_jis():
    data = "こんにちは".encode("shift_jis")
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "Shift-JIS-2004" in valid_names


def test_eliminates_impossible_encodings():
    data = "Привет".encode("windows-1251")
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    assert len(valid) < len(candidates)


def test_empty_input_returns_all():
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    valid = filter_by_validity(b"", candidates)
    assert len(valid) == len(candidates)


def test_returns_tuple():
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    valid = filter_by_validity(b"Hello", candidates)
    assert isinstance(valid, tuple)
