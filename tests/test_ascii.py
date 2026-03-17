from __future__ import annotations

from chardet.pipeline import DetectionResult
from chardet.pipeline.ascii import detect_ascii


def test_pure_ascii():
    result = detect_ascii(b"Hello, world! 123")
    assert result == DetectionResult("ascii", 1.0, None)


def test_ascii_with_common_whitespace():
    result = detect_ascii(b"Hello\n\tworld\r\n")
    assert result == DetectionResult("ascii", 1.0, None)


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
    assert result == DetectionResult("ascii", 1.0, None)


def test_all_printable_ascii():
    data = bytes(range(0x20, 0x7F))
    result = detect_ascii(data)
    assert result == DetectionResult("ascii", 1.0, None)


def test_null_byte_not_ascii():
    # 2 nulls in 10 bytes = 20% → above threshold, not ASCII
    result = detect_ascii(b"Hello\x00\x00rld")
    assert result is None


def test_ascii_with_sparse_null_separators():
    """ASCII with null separators below 5% threshold → confidence 0.99."""
    data = (
        b"master:README.md\x002\x00For support slack to #kodiak-support\n"
        b"master:support.txt\x001\x00For support slack to #kodiak-support\n"
    )
    result = detect_ascii(data)
    assert result is not None
    assert result.encoding == "ascii"
    assert result.confidence == 0.99


def test_ascii_with_null_separated_paths():
    """Find -print0 style output → ASCII at 0.99."""
    data = (
        b"/home/user/documents/report.txt\x00"
        b"/home/user/documents/notes.txt\x00"
        b"/home/user/downloads/image.png\x00"
        b"/home/user/music/song.mp3\x00"
    )
    result = detect_ascii(data)
    assert result is not None
    assert result.encoding == "ascii"
    assert result.confidence == 0.99


def test_ascii_with_null_at_boundary():
    """Exactly 5% nulls (1 in 20 bytes) is at the threshold — still ASCII."""
    result = detect_ascii(b"abcdefghij\x00klmnopqrs")  # 1/20 = 5%
    assert result is not None
    assert result.encoding == "ascii"
    assert result.confidence == 0.99


def test_ascii_with_null_just_above_boundary():
    """Just above 5% nulls → not ASCII."""
    result = detect_ascii(b"abcdefghij\x00klmnopqr")  # 1/19 = 5.26%
    assert result is None


def test_ascii_with_high_null_fraction():
    """More than 5% null bytes → not ASCII."""
    # 5 nulls in 15 bytes = 33%
    data = b"ab\x00cd\x00ef\x00gh\x00ij\x00"
    result = detect_ascii(data)
    assert result is None


def test_ascii_with_nulls_and_high_bytes():
    """Nulls mixed with non-ASCII bytes → not ASCII."""
    data = b"Hello\x00\x80World"
    result = detect_ascii(data)
    assert result is None


def test_pure_ascii_still_confidence_1():
    """Pure ASCII without nulls still returns confidence 1.0."""
    result = detect_ascii(b"Hello, world!")
    assert result == DetectionResult("ascii", 1.0, None)
