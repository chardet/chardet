"""Stage 1c: Pure ASCII detection."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# Allowed ASCII bytes: tab (0x09), newline (0x0A), carriage return (0x0D),
# and printable ASCII (0x20-0x7E).  bytes.translate deletes these from the
# input; if anything remains, the data is not pure ASCII.
_ALLOWED_ASCII: bytes = bytes([0x09, 0x0A, 0x0D, *range(0x20, 0x7F)])


def detect_ascii(data: bytes) -> DetectionResult | None:
    """Return an ASCII result if all bytes are printable ASCII plus common whitespace.

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` for ASCII, or ``None``.
    """
    if not data:
        return None
    if data.translate(None, _ALLOWED_ASCII):
        return None  # Non-allowed bytes remain
    return DetectionResult(encoding="ASCII", confidence=1.0, language=None)
