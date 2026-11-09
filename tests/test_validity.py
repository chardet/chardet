# tests/test_validity.py
from __future__ import annotations

import dataclasses

from chardet._utils import decodes_without_error
from chardet.enums import EncodingEra
from chardet.pipeline import validity
from chardet.pipeline.validity import filter_by_validity
from chardet.registry import get_candidates


def test_utf8_text_valid_under_utf8():
    data = "Héllo wörld".encode()
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "utf-8" in valid_names


def test_latin1_text_invalid_under_strict_multibyte():
    data = "Héllo".encode("latin-1")
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "iso8859-1" in valid_names


def test_shift_jis_text_valid_under_shift_jis():
    data = "こんにちは".encode("shift_jis")
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "shift_jis_2004" in valid_names


def test_eliminates_impossible_encodings():
    data = "Привет".encode("windows-1251")
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    assert len(valid) < len(candidates)


def test_empty_input_returns_all():
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    valid = filter_by_validity(b"", candidates)
    assert len(valid) == len(candidates)


def test_eliminates_specific_encoding():
    """Invalid UTF-8 bytes should eliminate UTF-8 from the candidate list."""
    data = b"\xc3\x28"  # invalid UTF-8 (bad continuation byte)
    candidates = get_candidates(EncodingEra.ALL)
    valid = filter_by_validity(data, candidates)
    valid_names = {e.name for e in valid}
    assert "utf-8" not in valid_names


def test_all_eliminated_returns_empty():
    """When no candidate can decode the data, return an empty tuple."""
    data = b"\xff\xfe"  # invalid under UTF-8
    utf8_only = tuple(e for e in get_candidates(EncodingEra.ALL) if e.name == "utf-8")
    assert len(utf8_only) == 1
    valid = filter_by_validity(data, utf8_only)
    assert valid == ()


def test_returns_tuple():
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    valid = filter_by_validity(b"Hello", candidates)
    assert isinstance(valid, tuple)


def test_agrees_with_a_full_decode_for_every_candidate():
    """The undefined-byte shortcut for single-byte codecs matches decoding."""
    candidates = get_candidates(EncodingEra.ALL)
    samples = [
        *(bytes([b]) for b in range(256)),
        bytes(range(256)),
        "Привет, мир".encode("cp1251") + b"\x98",
        "Grüße".encode("cp1252") + b"\x81",
        b"plain ascii " * 100 + b"\x9d",
    ]
    for data in samples:
        expected = tuple(e for e in candidates if decodes_without_error(data, e.name))
        assert filter_by_validity(data, candidates) == expected, data


def test_unknown_codec_is_filtered_out():
    """A candidate whose codec cannot be looked up never survives."""
    candidate = dataclasses.replace(
        get_candidates(EncodingEra.ALL)[0], name="no-such-codec"
    )
    assert filter_by_validity(b"Hello", (candidate,)) == ()
    assert "no-such-codec" not in validity._UNDEFINED_BYTES
