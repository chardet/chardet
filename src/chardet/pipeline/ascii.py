"""Stage 1c: Pure ASCII detection (with null-separator tolerance)."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# Allowed ASCII bytes: tab (0x09), newline (0x0A), carriage return (0x0D),
# and printable ASCII (0x20-0x7E).  bytes.translate deletes these from the
# input; if anything remains, the data is not pure ASCII.
_ALLOWED_ASCII: bytes = bytes([0x09, 0x0A, 0x0D, *range(0x20, 0x7F)])

# Maximum fraction of null bytes to still classify data as ASCII.
# Null-separated CLI output (find -print0, git ls-tree -z) typically has
# 1-5% nulls.  10% provides margin while excluding genuinely binary data.
_MAX_NULL_FRACTION = 0.10


def detect_ascii(data: bytes) -> DetectionResult | None:
    r"""Return an ASCII result if all bytes are printable ASCII plus common whitespace.

    Tolerates sparse null bytes (``\x00``) up to ``_MAX_NULL_FRACTION`` of
    the data, returning confidence 0.99 instead of 1.0 to distinguish from
    pure ASCII.

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` for ASCII, or ``None``.
    """
    if not data:
        return None
    remainder = data.translate(None, _ALLOWED_ASCII)
    if not remainder:
        return DetectionResult(encoding="ascii", confidence=1.0, language=None)
    # Check if the only non-allowed bytes are null separators
    if remainder.replace(b"\x00", b""):
        return None  # Non-null, non-ASCII bytes present
    # All non-allowed bytes are nulls — accept if sparse enough
    null_fraction = len(remainder) / len(data)
    if null_fraction <= _MAX_NULL_FRACTION:
        return DetectionResult(encoding="ascii", confidence=0.99, language=None)
    return None
