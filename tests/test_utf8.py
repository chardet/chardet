# tests/test_utf8.py
from __future__ import annotations

from chardet.pipeline.utf8 import detect_utf8


def test_valid_utf8_with_multibyte():
    data = "Héllo wörld café".encode()
    result = detect_utf8(data)
    assert result is not None
    assert result.encoding == "UTF-8"
    assert result.confidence >= 0.9


def test_valid_utf8_chinese():
    data = "你好世界".encode()
    result = detect_utf8(data)
    assert result is not None
    assert result.encoding == "UTF-8"


def test_valid_utf8_emoji():
    data = "Hello 🌍🌎🌏".encode()
    result = detect_utf8(data)
    assert result is not None
    assert result.encoding == "UTF-8"


def test_pure_ascii_returns_none():
    result = detect_utf8(b"Hello world")
    assert result is None


def test_invalid_utf8():
    result = detect_utf8(b"\xc3\x00")
    assert result is None


def test_overlong_encoding():
    result = detect_utf8(b"\xc0\xaf")
    assert result is None


def test_invalid_start_byte():
    result = detect_utf8(b"\xff\xfe")
    assert result is None


def test_truncated_multibyte():
    result = detect_utf8(b"Hello \xc3")
    assert result is None


def test_empty_input():
    result = detect_utf8(b"")
    assert result is None


def test_latin1_is_not_valid_utf8():
    data = "Héllo".encode("latin-1")
    result = detect_utf8(data)
    assert result is None


def test_surrogate_pair_rejected():
    # U+D800 would encode as ED A0 80 in invalid UTF-8
    result = detect_utf8(b"Hello " + b"\xed\xa0\x80" + b" World")
    assert result is None


def test_overlong_3byte_rejected():
    """Overlong 3-byte sequence (E0 80 80) encoding U+0000 must be rejected."""
    result = detect_utf8(b"Hello " + b"\xe0\x80\x80" + b" World")
    assert result is None


def test_overlong_4byte_rejected():
    """Overlong 4-byte sequence (F0 80 80 80) encoding U+0000 must be rejected."""
    result = detect_utf8(b"Hello " + b"\xf0\x80\x80\x80" + b" World")
    assert result is None


def test_above_unicode_max_rejected():
    """Code point above U+10FFFF (F4 90 80 80 = U+110000) must be rejected."""
    result = detect_utf8(b"Hello " + b"\xf4\x90\x80\x80" + b" World")
    assert result is None
