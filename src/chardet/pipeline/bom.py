"""Stage 1a: BOM (Byte Order Mark) detection."""

from __future__ import annotations

from chardet._utils import decodes_without_error
from chardet.pipeline import DetectionResult

# Where two marks share a prefix, the longer must come first: UTF-32 is
# checked before UTF-16 because the UTF-32-LE BOM starts with the UTF-16-LE
# BOM.  The UTF-7 entries share no prefix with anything and sit last.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xfe\xff", "utf-16"),
    (b"\xff\xfe", "utf-16"),
    # UTF-7 signatures: U+FEFF encoded in UTF-7 ("+/v8-" and friends).
    # The fourth base64 character varies with what follows the BOM, giving
    # four prefixes (RFC 2152).  All four are ASCII bytes, so without these
    # marks a signed UTF-7 file reads as plain ASCII and the signature is
    # returned to the caller as literal text.  Unlike the other marks these
    # bytes occur in ordinary text ("+/v8/src/api.cc" in a diff), so a
    # UTF-7 match additionally requires the whole buffer to decode.
    (b"+/v8", "utf-7"),
    (b"+/v9", "utf-7"),
    (b"+/v+", "utf-7"),
    (b"+/v/", "utf-7"),
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
            # A UTF-7 signature is only believable if the data is UTF-7:
            # the prefix alone is ordinary ASCII (see the table comment).
            if encoding == "utf-7" and not decodes_without_error(data, "utf-7"):
                continue
            return DetectionResult(encoding=encoding, confidence=1.0, language=None)
    return None
