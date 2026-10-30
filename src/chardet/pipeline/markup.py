"""Stage 1b: charset declarations (HTML/XML/PEP 263) and the answer they give.

The module has two seams.  :func:`iter_declarations` is the parser: it
reads the head of the data and yields every charset declaration it finds,
resolved to a registry name, without decoding the window.
:func:`detect_markup_charset` is the stage: it walks those declarations
and decides which one, if any, is the answer, including any promotion to
a Windows superset.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import re
from collections.abc import Iterator
from typing import NamedTuple

from chardet._utils import decodes_without_error
from chardet.enums import EncodingEra
from chardet.output_names import display_codec
from chardet.pipeline import DETERMINISTIC_CONFIDENCE, DetectionResult, PipelineContext
from chardet.pipeline.structural import compute_structural_score
from chardet.registry import CJK_SUPERSETS, REGISTRY, lookup_encoding

# Markup charset declarations that commonly refer to a Windows superset
# encoding rather than the strict standard encoding.  Japanese web content
# almost universally declares "Shift_JIS" but actually uses CP932 extensions;
# similarly, Korean web content declares "EUC-KR" but uses CP949/UHC.
# When the declared encoding resolves to the base (key), we check whether
# ``superset`` is a better answer.  ``reported_codec`` is the codec that the
# *reported* encoding name resolves to for callers: shift_jis_2004 is
# displayed as "SHIFT_JIS", which standard codec lookup resolves to plain
# shift_jis, so that is the codec whose decode must not break for the
# un-promoted name to be safe to report.  The pairs come from the
# registry's superset fact, limited to the multi-byte CJK encodings
# (ADR-0007).


class _Promotion(NamedTuple):
    """The two names a declared CJK encoding can be reported under."""

    reported_codec: str
    superset: str


_MARKUP_SUPERSET_PROMOTIONS: dict[str, _Promotion] = {
    name: _Promotion(display_codec(name), superset)
    for name, superset in CJK_SUPERSETS.items()
}
_SCAN_LIMIT = 4096

# Labels that cannot describe a document whose declaration was read as
# ASCII bytes: UTF-16 and UTF-32 text would have put null bytes between the
# letters of the tag.  The WHATWG prescan reads such a label as UTF-8, and
# ``x-user-defined`` as windows-1252, so the declared page still has a
# chance of decoding under the name it is given.
_SELF_CONTRADICTING_LABELS = frozenset(
    {"utf-16", "utf-16-be", "utf-16-le", "utf-32", "utf-32-be", "utf-32-le"}
)

# Labels a browser never decodes the page under: ``utf-7`` is not a WHATWG
# label at all, and ``hz-gb-2312`` maps to the replacement encoding.  Both
# decoders turn ASCII that is not markup (``+ADw-script+AD4-``,
# ``<~{~}script>``) into tags, which is why browsers dropped them, so the
# prescan's answer is to ignore the declaration.  The PEP 263 cookie
# follows the same rule, so a label alone never names either encoding.  A
# genuine UTF-7 or HZ stream is still found from its own bytes by the
# escape stage.
_IGNORED_LABELS = frozenset({"utf-7", "hz"})

# A tag scan stops at the next ``<`` as well as at ``>``.  A tag that never
# closes is not a declaration either way, but with ``[^>]`` every unclosed
# ``<meta`` ran to the end of the head before failing, and a head made of
# nothing else cost a thousand times a normal one.  The price is a literal
# ``<`` inside an attribute value, which hides that one tag.
_XML_ENCODING_RE = re.compile(
    rb"""<\?xml\s[^<>]*encoding\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE
)
_META_TAG_RE = re.compile(rb"<meta\b([^<>]*)>", re.IGNORECASE)
# DOTALL so a quoted value may span lines.
_ATTR_RE = re.compile(
    rb"""([^\s=/>]+)(?:\s*=\s*(?:(["'])(.*?)\2|([^\s>"']+)))?""",
    re.IGNORECASE | re.DOTALL,
)
_CONTENT_CHARSET_RE = re.compile(
    rb"""charset[\t\n\f\r ]*=[\t\n\f\r ]*(?:(["'])([^"']+)\1|([^\s;"']+))""",
    re.IGNORECASE,
)

# PEP 263: encoding declaration in the first two lines of a Python file.
# https://peps.python.org/pep-0263/
_PEP263_RE = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")
_PEP263_BLANK_RE = re.compile(rb"^[ \t\f]*(?:[#\r]|$)")

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
# single junk character stands in for the opening quote.  That junk
# character is grouped with its own trailing whitespace rather than left
# between two ``\s*`` runs: ``\s*X?\s*`` lets a whitespace byte land in
# either run, so a value that never arrives (``charset=`` followed by a
# long space run) backtracks over every split and makes the match
# quadratic in the whitespace length.  ``\s*(?:X\s*)?`` matches the same
# strings with one way to place each space.
_EBCDIC_TAG_RE = re.compile(r"<(?:meta|\?xml)[^<>]*", re.IGNORECASE)
_EBCDIC_DECL_RE = re.compile(
    r"(?:charset|encoding)\s*=\s*(?:[^\sA-Za-z0-9._-]\s*)?([A-Za-z][A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

# High bytes: EBCDIC text is dominated by bytes >= 0x80 (Latin lowercase
# letters all sit at 0x81+; other scripts likewise), while ASCII-compatible
# markup is dominated by bytes < 0x80.
_MARKUP_HIGH_BYTES = bytes(range(0x80, 0x100))

# Minimum fraction of high bytes in the head for an EBCDIC scan to be
# worth attempting.
_EBCDIC_SCAN_MIN_HIGH_FRACTION = 0.25


class Declaration(NamedTuple):
    """One charset declaration found in the head of the data.

    :ivar encoding: The registry name the label resolves to under its
        scanner's rule, or ``None`` when no codec answers to the label.
    :ivar mime_type: ``text/xml`` for an XML prolog, ``text/html`` for a
        meta tag, ``text/x-python`` for a PEP 263 coding cookie.
    """

    encoding: str | None
    mime_type: str


def _ascii_label(raw: bytes) -> str | None:
    """Return *raw* as a stripped ASCII string, or ``None`` if it is not ASCII."""
    try:
        return raw.decode("ascii").strip()
    except UnicodeDecodeError:
        return None


def _iter_ebcdic_declarations(data: bytes) -> Iterator[Declaration]:
    """Yield the charset declarations in EBCDIC-encoded markup.

    The ASCII regexes cannot see declarations in EBCDIC bytes, so when the
    head looks like EBCDIC text (dominated by high bytes), decode it through
    cp037, the EBCDIC page whose letter and digit positions are shared by
    all variants, and scan the decoded text.  Only declarations naming a
    MAINFRAME-era encoding are yielded.  The MIME type follows the tag the
    declaration sits in.
    """
    head = data[:_SCAN_LIMIT]
    high_count = len(head) - len(head.translate(None, _MARKUP_HIGH_BYTES))
    if high_count < len(head) * _EBCDIC_SCAN_MIN_HIGH_FRACTION:
        return
    decoded = head.decode("cp037", errors="replace")
    # Scan every declaration token inside every anchor tag: an unrelated
    # earlier ``charset=``/``encoding=`` token (a query string in an href,
    # a bogus attribute in the same tag) must not mask a genuine EBCDIC
    # declaration after it.
    for tag in _EBCDIC_TAG_RE.finditer(decoded):
        for match in _EBCDIC_DECL_RE.finditer(tag.group(0)):
            encoding = lookup_encoding(match.group(1).strip())
            if encoding is not None and REGISTRY[encoding].era & EncodingEra.MAINFRAME:
                is_xml = tag.group(0)[1] == "?"
                yield Declaration(encoding, "text/xml" if is_xml else "text/html")


def _pep263_encoding(raw_name: str) -> str | None:
    """Resolve a coding cookie the way :func:`tokenize.detect_encoding` does.

    Python folds the ``utf-8-*`` spellings to UTF-8 and ``latin-1``,
    ``iso-8859-1``, and ``iso-latin-1`` (with or without a suffix) to
    Latin-1 before it consults the codec registry, so ``iso-latin-1`` is a
    valid cookie even though no codec answers to it, and ``utf-8-sig``
    names plain UTF-8 rather than a file that starts with a mark.
    """
    name = raw_name[:12].lower().replace("_", "-")
    if name == "utf-8" or name.startswith("utf-8-"):
        return "utf-8"
    if name in ("latin-1", "iso-8859-1", "iso-latin-1") or name.startswith(
        ("latin-1-", "iso-8859-1-", "iso-latin-1-")
    ):
        return "iso8859-1"
    encoding = lookup_encoding(raw_name)
    if encoding in _IGNORED_LABELS:
        return None
    return encoding


def _pep263_declaration(data: bytes) -> Declaration | None:
    """Return the PEP 263 coding cookie in the first two lines of *data*.

    PEP 263 declarations (e.g. ``# -*- coding: utf-8 -*-``) are only valid
    on line 1 or line 2 of a Python source file.  Both lines have to start
    inside the first :data:`_SCAN_LIMIT` bytes, the same bound the markup
    scan uses.
    """
    head = data[:_SCAN_LIMIT]
    # PEP 263 requires a '#' comment marker on line 1 or 2.
    if b"#" not in head:
        return None
    # Python only examines line 2 when line 1 is a comment or blank.
    lines = head.split(b"\n", 2)
    match = _PEP263_RE.match(lines[0])
    if match is None and len(lines) > 1 and _PEP263_BLANK_RE.match(lines[0]):
        match = _PEP263_RE.match(lines[1])
    if match is None:
        return None
    raw_name = _ascii_label(match.group(1))
    if raw_name is None:
        return None
    return Declaration(_pep263_encoding(raw_name), "text/x-python")


def _strip_comments(head: bytes) -> bytes:
    """Return *head* without its ``<!-- -->`` comments.

    A declaration inside a comment is not a declaration, and the WHATWG
    prescan skips comments for that reason.  As in the prescan, the dashes
    that open a comment may also close it (``<!-->`` is a whole comment),
    and a comment that never closes runs to the end of the head.
    """
    start = head.find(b"<!--")
    if start < 0:
        return head
    parts: list[bytes] = []
    pos = 0
    while start >= 0:
        parts.append(head[pos:start])
        # Keep a tag boundary: deleting the comment must not manufacture
        # a tag, attribute name or encoding label from adjacent fragments.
        parts.append(b"<>")
        end = head.find(b"-->", start + 2)
        if end < 0:
            return b"".join(parts)
        pos = end + 3
        start = head.find(b"<!--", pos)
    parts.append(head[pos:])
    return b"".join(parts)


def _markup_encoding(raw_name: str) -> str | None:
    """Resolve a charset label found in ASCII-compatible markup."""
    if raw_name.lower() == "x-user-defined":
        return "cp1252"
    encoding = lookup_encoding(raw_name)
    if encoding in _SELF_CONTRADICTING_LABELS:
        return "utf-8"
    if encoding in _IGNORED_LABELS:
        return None
    return encoding


def _meta_attributes(body: bytes) -> dict[bytes, bytes]:
    """Return the attributes of one meta tag, lowercased by name."""
    attrs: dict[bytes, bytes] = {}
    for match in _ATTR_RE.finditer(body):
        name = match.group(1).lower()
        if name in attrs:
            continue
        value = match.group(3)
        if value is None:
            value = match.group(4)
        if value is not None:
            attrs[name] = value
    return attrs


def _iter_html_charsets(head: bytes) -> Iterator[bytes]:
    """Yield charset labels from real meta declarations, in document order.

    ``charset=`` inside some other attribute (a refresh URL, a description)
    is not a declaration. A declaration is a ``charset`` attribute, or the
    ``charset`` parameter of an ``http-equiv="content-type"`` tag.
    ``name="content-type"`` is wrong by the spec but common enough in the
    wild that it counts too.
    """
    for tag in _META_TAG_RE.finditer(head):
        attrs = _meta_attributes(tag.group(1))
        charset = attrs.get(b"charset")
        if charset is not None and charset.strip():
            yield charset
            continue
        equiv = attrs.get(b"http-equiv")
        if equiv is None:
            equiv = attrs.get(b"name")
        content = attrs.get(b"content")
        if (
            equiv is not None
            and content is not None
            and equiv.strip().lower() == b"content-type"
        ):
            found = _CONTENT_CHARSET_RE.search(content)
            if found:
                yield found.group(2) if found.group(1) else found.group(3)


def iter_declarations(data: bytes) -> Iterator[Declaration]:
    """Yield every charset declaration in the head of *data*, in scan order.

    The scan order is the order a reader honors them in:

    1. ``<?xml ... encoding="..."?>``
    2. ``<meta charset="...">`` and ``<meta http-equiv="Content-Type"
       content="...; charset=...">`` (also with ``name`` in place of
       ``http-equiv``), in document order
    3. declarations inside EBCDIC-encoded markup, when the head is
       dominated by high bytes
    4. PEP 263 ``# -*- coding: ... -*-`` (first two lines only)

    Markup inside ``<!-- -->`` comments is not scanned.  A UTF-16 or UTF-32
    label is read as UTF-8 and ``x-user-defined`` as windows-1252, as in the
    WHATWG prescan, since a declaration found in ASCII bytes cannot be
    describing UTF-16 text.  A ``utf-7`` or ``hz-gb-2312`` label resolves
    to ``None`` in every scanner, the PEP 263 cookie included, since the
    prescan never decodes a page under either.  A label that is not ASCII
    is skipped.

    This is parsing only: nothing here decodes the window, so whether a
    declaration is believable is left to :func:`detect_markup_charset`.
    The scans run lazily, so a consumer that stops at the first answer
    never pays for the EBCDIC or PEP 263 scan.

    :param data: The raw byte data to scan.
    :returns: An iterator of :class:`Declaration`.
    """
    if not data:
        return

    head = _strip_comments(data[:_SCAN_LIMIT])

    match = _XML_ENCODING_RE.search(head)
    if match:
        raw_name = _ascii_label(match.group(1))
        if raw_name is not None:
            yield Declaration(
                _markup_encoding(raw_name) if raw_name else None, "text/xml"
            )

    for raw in _iter_html_charsets(head):
        raw_name = _ascii_label(raw)
        if raw_name is not None:
            yield Declaration(_markup_encoding(raw_name), "text/html")

    yield from _iter_ebcdic_declarations(data)

    pep263 = _pep263_declaration(data)
    if pep263 is not None:
        yield pep263


class _Verdict(NamedTuple):
    """What one declaration says about the window.

    :ivar answer: The name to report, or ``None``.
    :ivar settled: Whether the declared encoding or its Windows superset
        decodes the window, allowed or not.  A settled declaration ends
        the scan even when it has no answer to give: the page named an
        encoding that fits its bytes, and when the caller's filters rule
        that out, a later declaration is not more trustworthy for it.
        Often the later one is a Latin-1 default that decodes any bytes.
    """

    answer: str | None
    settled: bool


_UNSETTLED = _Verdict(None, settled=False)


def _declared_answer(data: bytes, encoding: str, allowed: frozenset[str]) -> _Verdict:
    """Return what a declaration of *encoding* says about *data*.

    A declaration is an answer only if the declared encoding, or its Windows
    superset, decodes the whole of *data*, and only if that name is in
    *allowed*.  (When the declared encoding decodes but the narrower codec
    its display name resolves to does not, the superset is preferred; if
    that fails too, the declared name stands and rendering keeps the
    internal name, which decodes.)  The decoder stops at the first bad
    sequence, so a declaration that lies about the header fails as fast as
    a head-only check would, and a cut multi-byte sequence at the very end
    is tolerated as everywhere else.  A declaration that decodes but names
    nothing in *allowed* is settled without an answer (see :class:`_Verdict`).

    For a declared CJK encoding with a Windows superset in *allowed*
    (Shift_JIS and CP932, EUC-KR and CP949), the superset is reported when
    its structural score on the head is strictly higher and it decodes, or
    when it decodes and the name the caller would see for the declared
    encoding does not (a declared Shift_JIS page using NEC extensions, a
    declared EUC-KR page whose first CP949-only hangul sits past the
    header).  The decode checks read the whole window: what a caller can
    ``.decode()`` is a fact about their entire input.  The structural
    comparison reads only the first :data:`_SCAN_LIMIT` bytes, since
    multi-byte structure is uniform enough that the ranking has converged
    by then.  It runs first because it is cheap and settles which decode
    the answer needs: a 200 kB window decodes in a few hundred
    microseconds, and every declared page of a promotable encoding comes
    through here.
    """
    promotion = _MARKUP_SUPERSET_PROMOTIONS.get(encoding)
    if promotion is None or promotion.superset not in allowed:
        if decodes_without_error(data, encoding):
            return _Verdict(encoding if encoding in allowed else None, settled=True)
        # A failed subset is still settled when the superset the caller
        # ruled out decodes, as a declared EUC-KR page with CP949 hangul is.
        settled = promotion is not None and decodes_without_error(
            data, promotion.superset
        )
        return _Verdict(None, settled)
    reported_codec, superset = promotion
    if encoding not in allowed:
        # The declared name cannot be reported.  The superset stands in for
        # it only when the declared encoding itself fails the window; a
        # declaration that decodes is an answer, just not an allowed one.
        if decodes_without_error(data, encoding):
            return _Verdict(None, settled=True)
        if decodes_without_error(data, superset):
            return _Verdict(superset, settled=True)
        return _UNSETTLED
    head = data[:_SCAN_LIMIT]
    # The orchestrator's context cannot be shared: its structural cache is
    # keyed by encoding name only, and this scores a different slice.
    ctx = PipelineContext()
    base_score = compute_structural_score(head, REGISTRY[encoding], ctx)
    superset_score = compute_structural_score(head, REGISTRY[superset], ctx)
    if superset_score > base_score:
        # The superset fits the structure better; take it if it decodes.
        if decodes_without_error(data, superset):
            return _Verdict(superset, settled=True)
        if decodes_without_error(data, encoding):
            return _Verdict(encoding, settled=True)
        return _UNSETTLED
    # The reported codec is a subset of the declared one: plain shift_jis
    # decodes nothing that shift_jis_2004 cannot, and euc_kr reports as
    # itself.  So when the reported codec decodes the window, the declared
    # encoding does too, and a clean declared page costs this one decode.
    if decodes_without_error(data, reported_codec):
        return _Verdict(encoding, settled=True)
    # Decode-safety: if the reported name cannot decode the data, the
    # superset is the only answer a caller can actually use with
    # ``.decode()``, regardless of the structural tie.
    if decodes_without_error(data, superset):
        return _Verdict(superset, settled=True)
    # Neither the reported codec nor the superset decodes.  The declared
    # encoding is still the answer if it decodes (a JIS X 0213 character
    # that only shift_jis_2004 maps); when the reported codec is the same
    # codec, its failure above already settled that it does not.
    if reported_codec != encoding and decodes_without_error(data, encoding):
        return _Verdict(encoding, settled=True)
    return _UNSETTLED


def detect_markup_charset(
    data: bytes,
    allowed: frozenset[str],
    utf8_precheck: DetectionResult | None = None,
) -> DetectionResult | None:
    """Return the answer the charset declarations in *data* give, if any.

    Runs before the ASCII and UTF-8 stages so explicit declarations like
    ``<?xml encoding="iso-8859-1"?>`` are honored even when the bytes
    happen to be pure ASCII.  Declarations from :func:`iter_declarations`
    are tried in order.  One counts only if the name it resolves to, or its
    Windows superset (see :func:`_declared_answer`), decodes the whole of
    *data* and is in *allowed*.  A declaration that fails to decode is
    skipped and the next one is tried, so a stale prolog does not hide a
    correct meta.  A declaration that decodes but is filtered out ends the
    scan with no answer, leaving the page to the later stages, the same as
    a page without one.  Each failed encoding is decoded once: the head can
    repeat one label hundreds of times, and every try reads the window.

    A declaration is honored over pure ASCII, since the declared encoding
    decodes those bytes identically, but not over genuine UTF-8 structure:
    data containing valid multi-byte UTF-8 sequences is UTF-8 regardless of
    what the (frequently stale) declaration claims, and decoding it as the
    declared encoding would produce mojibake.  So when *utf8_precheck* is
    a UTF-8 result in *allowed* and the first accepted declaration names
    something else, that UTF-8 result is returned instead, keeping the
    declaration's MIME type; only the encoding wins.

    :param data: The raw byte data to scan.
    :param allowed: The encoding names the caller's filters permit.
    :param utf8_precheck: The UTF-8 stage's result for *data*, if any.
    :returns: A :class:`DetectionResult` with confidence 0.95 (or the UTF-8
        precheck's), or ``None`` when no declaration is accepted.
    """
    rejected: set[str] = set()
    for declaration in iter_declarations(data):
        encoding = declaration.encoding
        if encoding is None or encoding in rejected:
            continue
        answer, settled = _declared_answer(data, encoding, allowed)
        if answer is None:
            if settled:
                return None
            rejected.add(encoding)
            continue
        if (
            utf8_precheck is not None
            and utf8_precheck.encoding != answer
            and utf8_precheck.encoding in allowed
        ):
            return DetectionResult(
                utf8_precheck.encoding,
                utf8_precheck.confidence,
                utf8_precheck.language,
                declaration.mime_type,
            )
        return DetectionResult(
            encoding=answer,
            confidence=DETERMINISTIC_CONFIDENCE,
            language=None,
            mime_type=declaration.mime_type,
        )
    return None
