"""Stage 1b: HTML/XML charset declaration extraction."""

from __future__ import annotations

import re

from chardet.pipeline import DETERMINISTIC_CONFIDENCE, DetectionResult
from chardet.registry import lookup_encoding

_SCAN_LIMIT = 4096

_XML_ENCODING_RE = re.compile(
    rb"""<\?xml[^>]+encoding\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE
)
_HTML5_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset\s*=\s*['"]?\s*([^\s'">;]+)""", re.IGNORECASE
)
_HTML4_CONTENT_TYPE_RE = re.compile(
    rb"""<meta[^>]+content\s*=\s*['"][^'"]*charset=([^\s'">;]+)""", re.IGNORECASE
)


def detect_markup_charset(data: bytes) -> DetectionResult | None:
    """Scan the first bytes of *data* for an HTML/XML charset declaration.

    Checks for:

    1. ``<?xml ... encoding="..."?>``
    2. ``<meta charset="...">``
    3. ``<meta http-equiv="Content-Type" content="...; charset=...">``

    :param data: The raw byte data to scan.
    :returns: A :class:`DetectionResult` with confidence 0.95, or ``None``.
    """
    if not data:
        return None

    head = data[:_SCAN_LIMIT]

    for pattern in (_XML_ENCODING_RE, _HTML5_CHARSET_RE, _HTML4_CONTENT_TYPE_RE):
        match = pattern.search(head)
        if match:
            try:
                raw_name = match.group(1).decode("ascii").strip()
            except (UnicodeDecodeError, ValueError):
                continue
            encoding = lookup_encoding(raw_name)
            if encoding is not None and _validate_bytes(data, encoding):
                return DetectionResult(
                    encoding=encoding,
                    confidence=DETERMINISTIC_CONFIDENCE,
                    language=None,
                )

    return None


def _validate_bytes(data: bytes, encoding: str) -> bool:
    """Check that *data* can be decoded under *encoding* without errors.

    Only validates the first ``_SCAN_LIMIT`` bytes to avoid decoding a
    full 200 kB input just to verify a charset declaration found in the
    header.
    """
    try:
        data[:_SCAN_LIMIT].decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return False
    return True
