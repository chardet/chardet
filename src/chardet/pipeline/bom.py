"""Stage 1a: BOM (Byte Order Mark) detection."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# Ordered longest-first so UTF-32 is checked before UTF-16
# (UTF-32-LE BOM starts with the same bytes as UTF-16-LE BOM)
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\x00\x00\xfe\xff", "UTF-32-BE"),
    (b"\xff\xfe\x00\x00", "UTF-32-LE"),
    (b"\xef\xbb\xbf", "UTF-8-SIG"),
    (b"\xfe\xff", "UTF-16-BE"),
    (b"\xff\xfe", "UTF-16-LE"),
)

_UTF32_BOMS: frozenset[bytes] = frozenset({b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00"})


def detect_bom(data: bytes) -> DetectionResult | None:
    """Check for a byte order mark at the start of *data*.

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` with confidence 1.0, or ``None``.
    """
    for bom_bytes, encoding in _BOMS:
        if data.startswith(bom_bytes):
            # UTF-32 BOMs overlap with UTF-16 BOMs (e.g. FF FE 00 00 starts
            # with the UTF-16-LE BOM FF FE).  Validate that the payload after
            # a UTF-32 BOM is a valid number of UTF-32 code units (multiple of
            # 4 bytes).  If not, skip to let the shorter UTF-16 BOM match.
            if bom_bytes in _UTF32_BOMS:
                payload_len = len(data) - len(bom_bytes)
                if payload_len % 4 != 0:
                    continue
            return DetectionResult(encoding=encoding, confidence=1.0, language=None)
    return None
