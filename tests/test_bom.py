# tests/test_bom.py
from __future__ import annotations

from chardet.pipeline import DetectionResult
from chardet.pipeline.bom import detect_bom


def test_utf8_bom():
    data = b"\xef\xbb\xbfHello"
    result = detect_bom(data)
    assert result == DetectionResult("utf-8-sig", 1.0, None)


def test_utf16_le_bom():
    data = b"\xff\xfeH\x00e\x00l\x00l\x00o\x00"
    result = detect_bom(data)
    assert result == DetectionResult("utf-16", 1.0, None)


def test_utf16_be_bom():
    data = b"\xfe\xff\x00H\x00e\x00l\x00l\x00o"
    result = detect_bom(data)
    assert result == DetectionResult("utf-16", 1.0, None)


def test_utf32_le_bom():
    data = b"\xff\xfe\x00\x00" + b"\x48\x00\x00\x00"
    result = detect_bom(data)
    assert result == DetectionResult("utf-32", 1.0, None)


def test_utf32_be_bom():
    data = b"\x00\x00\xfe\xff" + b"\x00\x00\x00\x48"
    result = detect_bom(data)
    assert result == DetectionResult("utf-32", 1.0, None)


def test_no_bom():
    data = b"Hello, world!"
    result = detect_bom(data)
    assert result is None


def test_empty_input():
    assert detect_bom(b"") is None


def test_too_short_for_bom():
    assert detect_bom(b"\xef") is None
    assert detect_bom(b"\xef\xbb") is None


def test_utf32_le_checked_before_utf16_le():
    # UTF-32-LE BOM starts with \xff\xfe (same as UTF-16-LE) but has \x00\x00 after
    data = b"\xff\xfe\x00\x00" + b"\x48\x00\x00\x00"
    result = detect_bom(data)
    assert result is not None
    assert result.encoding == "utf-32"


def test_utf32_le_bom_only():
    # Bare UTF-32-LE BOM with no payload is valid (0 % 4 == 0)
    result = detect_bom(b"\xff\xfe\x00\x00")
    assert result is not None
    assert result.encoding == "utf-32"


def test_utf32_le_bom_falls_through_to_utf16_when_payload_not_aligned():
    # FF FE 00 00 30 00 looks like UTF-32-LE BOM, but the remaining
    # 2 bytes are not a valid UTF-32 code unit (need multiple of 4).
    # Should fall through to UTF-16-LE BOM instead.
    data = b"\xff\xfe\x00\x000\x00"
    result = detect_bom(data)
    assert result is not None
    assert result.encoding == "utf-16"


def test_utf32_be_bom_falls_through_when_payload_not_aligned():
    # Same logic for UTF-32-BE: payload must be a multiple of 4 bytes
    data = b"\x00\x00\xfe\xff\x00\x48"  # 2-byte payload, not aligned
    result = detect_bom(data)
    # No UTF-16-BE fallback here (00 00 FE FF doesn't start with FE FF)
    assert result is None
