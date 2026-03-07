from __future__ import annotations

from chardet.pipeline import DetectionResult
from chardet.pipeline.ascii import detect_ascii


def test_pure_ascii():
    result = detect_ascii(b"Hello, world! 123")
    assert result == DetectionResult("ASCII", 1.0, None)


def test_ascii_with_common_whitespace():
    result = detect_ascii(b"Hello\n\tworld\r\n")
    assert result == DetectionResult("ASCII", 1.0, None)


def test_high_byte_not_ascii():
    result = detect_ascii(b"Hello \x80 world")
    assert result is None


def test_utf8_multibyte_not_ascii():
    result = detect_ascii("Héllo".encode())
    assert result is None


def test_empty_input():
    result = detect_ascii(b"")
    assert result is None


def test_single_ascii_byte():
    result = detect_ascii(b"A")
    assert result == DetectionResult("ASCII", 1.0, None)


def test_all_printable_ascii():
    data = bytes(range(0x20, 0x7F))
    result = detect_ascii(data)
    assert result == DetectionResult("ASCII", 1.0, None)


def test_null_byte_not_ascii():
    # Null bytes should have been caught by binary detection (Stage 0),
    # but ASCII check should still reject them
    result = detect_ascii(b"Hello\x00world")
    assert result is None
