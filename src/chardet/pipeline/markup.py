"""Stage 1b: charset declaration extraction (HTML/XML/PEP 263)."""

from __future__ import annotations

import re

from chardet._utils import decodes_without_error
from chardet.enums import EncodingEra
from chardet.pipeline import DETERMINISTIC_CONFIDENCE, DetectionResult, PipelineContext
from chardet.pipeline.structural import compute_structural_score
from chardet.registry import REGISTRY, lookup_encoding

# Markup charset declarations that commonly refer to a Windows superset
# encoding rather than the strict standard encoding.  Japanese web content
# almost universally declares "Shift_JIS" but actually uses CP932 extensions;
# similarly, Korean web content declares "EUC-KR" but uses CP949/UHC.
# When the declared encoding resolves to the base (key), we check whether
# the superset (second element) is a better answer.  The first element is
# the codec that the *reported* encoding name resolves to for callers:
# shift_jis_2004 is displayed as "SHIFT_JIS", which standard codec lookup
# resolves to plain shift_jis, so that is the codec whose decode must not
# break for the un-promoted name to be safe to report.
_MARKUP_SUPERSET_PROMOTIONS: dict[str, tuple[str, str]] = {
    "shift_jis_2004": ("shift_jis", "cp932"),
    "euc_kr": ("euc_kr", "cp949"),
}

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

# PEP 263: encoding declaration in the first two lines of a Python file.
# https://peps.python.org/pep-0263/
_PEP263_RE = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)", re.MULTILINE)

# Charset declarations in EBCDIC-encoded markup, matched against a cp037
# decode of the head.  Letters, digits, and the anchor characters ``<``,
# ``>``, ``?``, ``=``, and ``/`` sit at the same code points in every
# supported EBCDIC code page, so the ``<meta``/``<?xml`` tag anchor, the
# ``charset=``/``encoding=`` label, and the encoding name itself decode
# correctly through cp037 regardless of which EBCDIC variant the data
# actually uses.  The tag anchor is required so plain EBCDIC prose that
# merely mentions ``encoding=NAME`` is not treated as a declaration; the
# tag span and the declaration tokens are matched by separate regexes so
# a bogus earlier ``encoding=`` token inside the same tag cannot consume
# the anchor away from the genuine ``charset=`` that follows it.  Quote
# characters are NOT invariant (e.g. cp1026 moves ``"``), so an optional
# single junk character stands in for the opening quote.
_EBCDIC_TAG_RE = re.compile(r"<(?:meta|\?xml)[^>]*", re.IGNORECASE)
_EBCDIC_DECL_RE = re.compile(
    r"(?:charset|encoding)\s*=\s*[^\sA-Za-z0-9._-]?\s*([A-Za-z][A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

# High bytes: EBCDIC text is dominated by bytes >= 0x80 (Latin lowercase
# letters all sit at 0x81+; other scripts likewise), while ASCII-compatible
# markup is dominated by bytes < 0x80.
_MARKUP_HIGH_BYTES = bytes(range(0x80, 0x100))

# Minimum fraction of high bytes in the head for an EBCDIC scan to be
# worth attempting.
_EBCDIC_SCAN_MIN_HIGH_FRACTION = 0.25


def _detect_ebcdic_declaration(head: bytes) -> DetectionResult | None:
    """Look for a charset declaration in EBCDIC-encoded markup.

    The ASCII regexes cannot see declarations in EBCDIC bytes, so when the
    head looks like EBCDIC text (dominated by high bytes), decode it through
    cp037 — the EBCDIC page whose letter and digit positions are shared by
    all variants — and scan the decoded text.  Only declarations naming a
    MAINFRAME-era encoding are honoured, and the declared encoding must
    actually decode the head.
    """
    high_count = len(head) - len(head.translate(None, _MARKUP_HIGH_BYTES))
    if high_count < len(head) * _EBCDIC_SCAN_MIN_HIGH_FRACTION:
        return None
    decoded = head.decode("cp037", errors="replace")
    # Scan every declaration token inside every anchor tag: an unrelated
    # earlier ``charset=``/``encoding=`` token (a query string in an href,
    # a bogus attribute in the same tag) must not mask a genuine EBCDIC
    # declaration after it.
    for tag in _EBCDIC_TAG_RE.finditer(decoded):
        for match in _EBCDIC_DECL_RE.finditer(tag.group(0)):
            encoding = lookup_encoding(match.group(1).strip())
            if (
                encoding is not None
                and REGISTRY[encoding].era & EncodingEra.MAINFRAME
                and decodes_without_error(head, encoding)
            ):
                return DetectionResult(
                    encoding=encoding,
                    confidence=DETERMINISTIC_CONFIDENCE,
                    language=None,
                    mime_type="text/html",
                )
    return None


def _detect_pep263(data: bytes) -> DetectionResult | None:
    """Check the first two lines of *data* for a PEP 263 encoding declaration.

    PEP 263 declarations (e.g. ``# -*- coding: utf-8 -*-``) are only valid
    on line 1 or line 2 of a Python source file.

    :param data: The raw byte data to scan.
    :returns: A :class:`DetectionResult` with confidence 0.95, or ``None``.
    """
    # PEP 263 requires a '#' comment marker on line 1 or 2.
    if b"#" not in data[:200]:
        return None
    # Extract first two lines only.
    first_two_lines = b"\n".join(data.split(b"\n", 2)[:2])
    match = _PEP263_RE.search(first_two_lines)
    if match:
        try:
            raw_name = match.group(1).decode("ascii").strip()
        except (UnicodeDecodeError, ValueError):
            return None
        encoding = lookup_encoding(raw_name)
        if encoding is not None and _validate_bytes(data, encoding):
            return DetectionResult(
                encoding=encoding,
                confidence=DETERMINISTIC_CONFIDENCE,
                language=None,
                mime_type="text/x-python",
            )
    return None


def detect_markup_charset(data: bytes) -> DetectionResult | None:
    """Scan the first bytes of *data* for a charset declaration.

    Checks for:

    1. ``<?xml ... encoding="..."?>``
    2. ``<meta charset="...">``
    3. ``<meta http-equiv="Content-Type" content="...; charset=...">``
    4. PEP 263 ``# -*- coding: ... -*-`` (first two lines only)

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
                mime_type = "text/xml" if pattern is _XML_ENCODING_RE else "text/html"
                return DetectionResult(
                    encoding=encoding,
                    confidence=DETERMINISTIC_CONFIDENCE,
                    language=None,
                    mime_type=mime_type,
                )

    ebcdic_result = _detect_ebcdic_declaration(head)
    if ebcdic_result is not None:
        return ebcdic_result

    return _detect_pep263(data)


def promote_markup_superset(
    data: bytes,
    markup_result: DetectionResult,
    allowed: frozenset[str],
) -> DetectionResult:
    """Promote a markup-declared encoding to its superset when structural evidence supports it.

    If the declared encoding has a known superset (per
    :data:`_MARKUP_SUPERSET_PROMOTIONS`), the superset validates the data,
    and the superset's structural score is materially better, return a new
    result using the superset encoding.  Otherwise return *markup_result*
    unchanged.
    """
    if markup_result.encoding is None:
        return markup_result
    promotion = _MARKUP_SUPERSET_PROMOTIONS.get(markup_result.encoding)
    if promotion is None:
        return markup_result
    reported_codec, superset_name = promotion
    if superset_name not in allowed:
        return markup_result
    superset_info = REGISTRY[superset_name]
    # Validate: superset must be able to decode the data
    if not decodes_without_error(data, superset_name):
        return markup_result
    # Decode-safety: if the codec the reported name resolves to cannot
    # decode the data (e.g. a declared-Shift_JIS page using CP932 NEC/IBM
    # extensions), the superset is the only answer a caller can actually
    # use with ``.decode()`` -- promote unconditionally.
    if not decodes_without_error(data, reported_codec):
        return DetectionResult(
            superset_name,
            markup_result.confidence,
            markup_result.language,
            markup_result.mime_type,
        )
    # Compare structural scores
    ctx = PipelineContext()
    base_score = compute_structural_score(data, REGISTRY[markup_result.encoding], ctx)
    superset_score = compute_structural_score(data, superset_info, ctx)
    if superset_score > base_score:
        return DetectionResult(
            superset_name,
            markup_result.confidence,
            markup_result.language,
            markup_result.mime_type,
        )
    return markup_result


def _validate_bytes(data: bytes, encoding: str) -> bool:
    """Check that *data* can be decoded under *encoding* without errors.

    Only validates the first ``_SCAN_LIMIT`` bytes to avoid decoding a
    full 200 kB input just to verify a charset declaration found in the
    header.
    """
    return decodes_without_error(data[:_SCAN_LIMIT], encoding)
