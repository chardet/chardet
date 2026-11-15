# tests/test_orchestrator.py
from __future__ import annotations

import pytest

import chardet.pipeline.orchestrator as _orchestrator_mod
from chardet.enums import EncodingEra
from chardet.pipeline import DetectionResult
from chardet.pipeline.markup import detect_markup_charset
from chardet.pipeline.orchestrator import run_pipeline
from chardet.registry import get_candidates

#: mypyc compiles a module's calls to functions defined in (or imported
#: into) that same module into direct native calls, so replacing those
#: names has no effect on a compiled build.  A test that mocks one to force
#: an otherwise-unreachable branch then runs the real path instead and
#: still passes, reporting coverage it does not have.  Audited: patching
#: module *data* attributes (e.g. confusion._DENSE_HIT_DIVISOR) and
#: attributes of uncompiled modules (e.g. importlib.resources.files) is
#: observed on both builds and needs no guard.
_needs_interpreted_build = pytest.mark.skipif(
    _orchestrator_mod.__file__.endswith((".so", ".pyd")),
    reason="patches a function the compiled module calls natively",
)


def test_empty_input():
    result = run_pipeline(b"", EncodingEra.MODERN_WEB)
    assert result == [DetectionResult("utf-8", 0.10, None, "text/plain")]


def test_bom_detected():
    data = b"\xef\xbb\xbfHello"
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-8-sig"
    assert result[0].confidence == 1.0


def test_bom_utf16_le():
    data = b"\xff\xfe" + "Hello world".encode("utf-16-le")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-16"
    assert result[0].confidence == 1.0


def test_bom_utf16_be():
    data = b"\xfe\xff" + "Hello world".encode("utf-16-be")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-16"
    assert result[0].confidence == 1.0


def test_bom_utf32_le():
    data = b"\xff\xfe\x00\x00" + "Hello world".encode("utf-32-le")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-32"
    assert result[0].confidence == 1.0


def test_bom_utf32_be():
    data = b"\x00\x00\xfe\xff" + "Hello world".encode("utf-32-be")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-32"
    assert result[0].confidence == 1.0


def test_utf16_le_no_bom():
    """UTF-16-LE without a BOM should be detected via null-byte patterns."""
    data = "Hello world, this is a test of UTF-16 detection.".encode("utf-16-le")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-16-le"
    assert result[0].confidence == 0.95


def test_utf16_be_no_bom():
    """UTF-16-BE without a BOM should be detected via null-byte patterns."""
    data = "Hello world, this is a test of UTF-16 detection.".encode("utf-16-be")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-16-be"
    assert result[0].confidence == 0.95


def test_utf32_le_no_bom():
    """UTF-32-LE without a BOM should be detected via null-byte patterns."""
    data = "Hello world, this is a test.".encode("utf-32-le")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-32-le"
    assert result[0].confidence == 0.95


def test_utf32_be_no_bom():
    """UTF-32-BE without a BOM should be detected via null-byte patterns."""
    data = "Hello world, this is a test.".encode("utf-32-be")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-32-be"
    assert result[0].confidence == 0.95


def test_pure_ascii():
    result = run_pipeline(b"Hello world 123", EncodingEra.ALL)
    assert result[0].encoding == "ascii"
    assert result[0].confidence == 1.0


def test_utf8_multibyte():
    data = "Héllo wörld café".encode()
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-8"
    assert result[0].confidence >= 0.9


def test_binary_content():
    data = b"\x00\x01\x02\x03\x04\x05" * 100
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding is None
    assert result[0].confidence == 0.95


def test_short_magic_signature_on_text_falls_through():
    """Text starting with a signature word is detected as text."""
    result = run_pipeline(b"BMW makes cars.\n", EncodingEra.ALL)
    assert result[0].encoding == "ascii"
    assert result[0].mime_type == "text/plain"


def test_short_magic_signature_cut_to_bare_signature_reads_as_text():
    """A window cut down to a bare short signature reads as text.

    Accepted on purpose: the same header is an executable when the window
    reaches its control bytes.
    """
    data = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    full = run_pipeline(data, EncodingEra.ALL)
    assert full[0].mime_type == "application/vnd.microsoft.portable-executable"
    cut = run_pipeline(data, EncodingEra.ALL, max_bytes=2)
    assert cut[0].encoding == "ascii"
    assert cut[0].mime_type == "text/plain"


def test_xml_charset_declaration():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root>Hello</root>'
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "iso8859-1"


@pytest.mark.parametrize(
    ("head", "expected", "mime_type"),
    [
        (b'<html><head><meta charset="utf-8"></head><body>', "utf-8", "text/html"),
        (
            b'<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">',
            "iso8859-1",
            "text/html",
        ),
        (b'<?xml version="1.0" encoding="UTF-8"?><r>', "utf-8", "text/xml"),
        (b"# -*- coding: utf-8 -*-\ns = '", "utf-8", "text/x-python"),
    ],
)
def test_declaration_beats_utf7_escape(head: bytes, expected: str, mime_type: str):
    """A declared charset is not re-read as UTF-7, which decodes to markup."""
    # "<script>alert(1)</script>" with the tags in UTF-7 shifted runs.
    payload = b"+ADwAcwBjAHIAaQBwAHQAPg-alert(1)+ADwALwBzAGMAcgBpAHAAdAA+-"
    assert payload.decode("utf-7") == "<script>alert(1)</script>"
    # Without a declaration the escape stage reads the payload as UTF-7.
    undeclared = run_pipeline(b"<p>" + payload + b"</p>", EncodingEra.ALL)
    assert undeclared[0].encoding == "utf-7"
    data = head + b"<p>" + payload + b"</p>"
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == expected
    assert result[0].mime_type == mime_type
    assert "<script>" not in data.decode(expected)


@pytest.mark.parametrize(
    ("tail", "smuggled"),
    [
        # The run has no closing "-": the window ends inside it.
        (b"+ADwAcwBjAHIAaQBwAHQAPg", "<script>"),
        # The window ends inside a character of the run.
        (b"+ADwAcwBj", "<sc"),
    ],
)
def test_declaration_beats_utf7_escape_cut_at_window_edge(tail: bytes, smuggled: str):
    """A smuggled tag the window cuts off still counts against UTF-7."""
    assert tail.decode("utf-7") == smuggled
    # The escape stage still reads the open run as UTF-7 ...
    undeclared = run_pipeline(b"<p>" + tail, EncodingEra.ALL)
    assert undeclared[0].encoding == "utf-7"
    # ... and the declaration still beats it.
    data = b'<html><head><meta charset="utf-8"></head><body><p>' + tail
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-8"
    assert result[0].mime_type == "text/html"


def test_declaration_beats_utf7_text():
    """UTF-7 that shifts only non-ASCII text still yields to a declaration."""
    body = "Héllo, 世界".encode("utf-7")
    assert run_pipeline(b"<r>" + body + b"</r>", EncodingEra.ALL)[0].encoding == "utf-7"
    data = b'<?xml version="1.0" encoding="utf-8"?><r>' + body + b"</r>"
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-8"
    assert result[0].mime_type == "text/xml"


_UTF8_HEAD = b'<html><head><meta charset="utf-8"></head><body>'


@pytest.mark.parametrize(
    ("stream", "smuggled"),
    [
        # One run per tag, and one run per character.
        (b"+/v8-<p>+ADwAcwBjAHIAaQBwAHQAPg-alert(1)", "<script>alert(1)"),
        (b"+/v8-<p>+ADw-script+AD4-alert(1)", "<script>alert(1)"),
        # The signature's own run carries on into the tag.
        (b"+/v8APABzAGMAcgBpAHAAdAA+-alert(1)", "<script>alert(1)"),
    ],
)
def test_declaration_beats_utf7_signature(stream: bytes, smuggled: str):
    """A UTF-7 signature does not carry a page past its declaration."""
    assert smuggled in stream.decode("utf-7")
    # Without a declaration the signature names the encoding.
    undeclared = run_pipeline(stream, EncodingEra.ALL)
    assert undeclared[0].encoding == "utf-7"
    assert undeclared[0].confidence == 1.0
    data = stream + _UTF8_HEAD
    assert smuggled in data.decode("utf-7")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-8"
    assert result[0].mime_type == "text/html"
    assert smuggled not in data.decode("utf-8")


def test_declaration_beats_utf7_signature_on_text():
    """Signed UTF-7 that shifts only non-ASCII text yields to a declaration too."""
    body = b"+/v8-" + "<p>Héllo, 世界</p>".encode("utf-7")
    undeclared = run_pipeline(body, EncodingEra.ALL)
    assert undeclared[0].encoding == "utf-7"
    assert undeclared[0].confidence == 1.0
    result = run_pipeline(body + _UTF8_HEAD, EncodingEra.ALL)
    assert result[0].encoding == "utf-8"


@pytest.mark.parametrize(
    ("body", "escape_encoding", "escape_reading"),
    [
        # HZ drops "~" plus a newline, joining the two halves of a tag.
        (
            b"<p>~{<:Ky2;~}</p><scr~\nipt>alert(1)</scr~\nipt>",
            "hz",
            "<script>alert(1)</script>",
        ),
        # A two-byte run that swallows the quote closing an attribute.
        (
            b'<p>~{<:Ky~}</p><img alt="~{0!"><p~}" onerror=alert(1) src=x>',
            "hz",
            '<img alt="啊⒕拣" onerror=alert(1) src=x>',
        ),
        (
            b'<img alt="\x1b$B!!"><p\x1b(B" onerror=alert(1) src=x>',
            "iso2022_jp_2",
            '<img alt="\u3000⊂腫" onerror=alert(1) src=x>',
        ),
        (
            b'\x1b$)C<img alt="\x0e0!"><p\x0f" onerror=alert(1) src=x>',
            "iso2022_kr",
            '<img alt="가♥숀" onerror=alert(1) src=x>',
        ),
        # JIS X 0201 Roman reads the backslash escaping a quote as a yen sign.
        (
            b"<script>var a='\x1b(J\\';alert(1)//\x1b(B';</script>",
            "iso2022_jp_2",
            "var a='\u00a5';alert(1)//",
        ),
    ],
)
@pytest.mark.parametrize(
    ("head", "expected", "mime_type"),
    [
        (_UTF8_HEAD, "utf-8", "text/html"),
        (
            b'<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">',
            "iso8859-1",
            "text/html",
        ),
        (b'<?xml version="1.0" encoding="UTF-8"?>', "utf-8", "text/xml"),
    ],
)
def test_declaration_beats_hz_and_iso2022_escape(  # noqa: PLR0913
    head: bytes,
    expected: str,
    mime_type: str,
    body: bytes,
    escape_encoding: str,
    escape_reading: str,
):
    """A declared charset is not re-read as HZ or ISO-2022."""
    # Without a declaration the escape stage answers, and its reading has
    # markup the bytes do not.
    undeclared = run_pipeline(body, EncodingEra.ALL)
    assert undeclared[0].encoding == escape_encoding
    assert escape_reading in body.decode(escape_encoding)
    data = head + body
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == expected
    assert result[0].mime_type == mime_type
    assert escape_reading not in data.decode(expected)


@pytest.mark.parametrize(
    ("label", "body", "declared", "expected"),
    [
        (
            "iso-2022-jp",
            "こんにちは世界".encode("iso2022_jp"),
            "iso2022_jp_2",
            "iso2022_jp_2",
        ),
        # Shift-out and shift-in make it JP-EXT, which the label's codec
        # also decodes: the designations name the variant, not the label.
        (
            "iso-2022-jp",
            "こんにちは".encode("iso2022_jp") + b" \x0e6@6E\x0f",
            "iso2022_jp_2",
            "iso2022_jp_ext",
        ),
        ("iso-2022-kr", "안녕하세요".encode("iso2022_kr"), "iso2022_kr", "iso2022_kr"),
    ],
)
def test_declared_iso2022_keeps_escape_answer(
    label: str, body: bytes, declared: str, expected: str
):
    """A page that declares ISO-2022 is answered by the escape stage."""
    data = f'<meta charset="{label}"><p>'.encode() + body + b"</p>"
    allowed = frozenset(e.name for e in get_candidates(EncodingEra.ALL))
    declaration = detect_markup_charset(data, allowed)
    assert declaration is not None
    assert declaration.encoding == declared
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == expected


def test_undeclared_hz_and_iso2022_unchanged():
    """With no declaration the escape stage still answers."""
    hz = "<p>你好世界</p>".encode("hz")
    assert run_pipeline(hz, EncodingEra.ALL)[0].encoding == "hz"
    jis = "<p>こんにちは世界</p>".encode("iso2022_jp")
    assert run_pipeline(jis, EncodingEra.ALL)[0].encoding == "iso2022_jp_2"


def test_filtered_declaration_leaves_escape_answer():
    """A declaration the caller's filters rule out does not replace the answer."""
    data = b"# coding: latin-1\ns = '" + "こんにちは".encode("iso2022_jp") + b"'\n"
    assert run_pipeline(data, EncodingEra.ALL)[0].encoding == "iso8859-1"
    assert run_pipeline(data, EncodingEra.MODERN_WEB)[0].encoding == "iso2022_jp_2"


# ---------------------------------------------------------------------------
# Markup superset promotion
# ---------------------------------------------------------------------------


def test_markup_superset_promotion_shift_jis_to_cp932():
    """Shift_JIS markup declaration should be promoted to CP932 when CP932-extended bytes are present."""
    # XML declaring Shift_JIS but containing CP932-only lead byte 0xF0
    data = (
        b'<?xml version="1.0" encoding="Shift_JIS"?><root>'
        + b"\xf0\x40" * 50
        + b"</root>"
    )
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "cp932"


def test_markup_superset_no_promotion_when_no_extended_bytes():
    """Shift_JIS markup declaration should NOT be promoted when data only uses standard Shift_JIS bytes."""
    # Pure standard Shift_JIS range (0x81-0x9F, 0xE0-0xEF leads)
    data = (
        b'<?xml version="1.0" encoding="Shift_JIS"?><root>'
        + b"\x82\xa0" * 50
        + b"</root>"
    )
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "shift_jis_2004"


def test_markup_superset_no_promotion_for_non_promotable_encoding():
    """Non-promotable markup declarations should pass through unchanged."""
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root>Hello</root>'
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "iso8859-1"


def test_markup_superset_promotion_respects_exclude():
    """Superset promotion should not promote to an excluded encoding."""
    data = (
        b'<?xml version="1.0" encoding="Shift_JIS"?><root>'
        + b"\xf0\x40" * 50
        + b"</root>"
    )
    result = run_pipeline(
        data,
        EncodingEra.ALL,
        exclude_encodings=frozenset({"cp932"}),
    )
    assert result[0].encoding == "shift_jis_2004"


def test_markup_superset_no_promotion_when_superset_cant_decode():
    """If superset can't decode the data, don't promote."""
    # 0x85 0x40 is valid shift_jis_2004 but invalid cp932
    data = (
        b'<?xml version="1.0" encoding="Shift_JIS"?><root>'
        + b"\x85\x40" * 50
        + b"</root>"
    )
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "shift_jis_2004"


def test_max_bytes_truncation():
    data = b"Hello" * 100_000
    result = run_pipeline(data, EncodingEra.ALL, max_bytes=100)
    assert result[0].encoding == "ascii"
    assert result[0].confidence == 1.0


def test_returns_list():
    result = run_pipeline(b"Hello", EncodingEra.ALL)
    assert isinstance(result, list)
    assert all(isinstance(r, DetectionResult) for r in result)


def test_single_high_byte_returns_encoding():
    """A single high byte should return an encoding, not None."""
    result = run_pipeline(b"\xe4", EncodingEra.MODERN_WEB)
    assert result[0].encoding is not None


def test_encoding_era_filtering():
    data = b"Hello world"
    for era in EncodingEra:
        result = run_pipeline(data, era)
        assert len(result) >= 1


def test_fallback_result_when_no_valid_encoding():
    """Data that no single-byte encoding can decode should return the fallback."""
    # Construct data with byte sequences invalid in most encodings but that
    # is not detected as UTF-8, ASCII, BOM, or binary.  A mix of high bytes
    # including overlong-invalid patterns that defeat UTF-8.
    data = bytes(range(0x80, 0x100)) * 2
    result = run_pipeline(data, EncodingEra.ALL)
    assert len(result) >= 1
    assert result[0].encoding is not None


def test_confidence_clamped_to_one():
    """run_pipeline should never return confidence > 1.0."""
    # Use a CJK text that triggers the byte-coverage boost
    data = "これは日本語のテストです。日本語の文章を検出できるかどうかを確認します。".encode(
        "euc-jis-2004"
    )
    result = run_pipeline(data, EncodingEra.ALL)
    for r in result:
        assert r.confidence <= 1.0


@_needs_interpreted_build
def test_fallback_when_no_valid_candidates(monkeypatch: pytest.MonkeyPatch):
    """When validity filtering eliminates all candidates, return fallback."""
    from chardet.pipeline import orchestrator  # noqa: PLC0415

    monkeypatch.setattr(orchestrator, "filter_by_validity", lambda _data, _cands: ())
    # Data must bypass BOM, UTF-16/32, escape, binary, markup, ASCII, and UTF-8
    data = bytes(range(0x80, 0x100)) * 2
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding is not None  # fallback, not None


@_needs_interpreted_build
def test_fallback_when_cjk_gate_eliminates_all(monkeypatch: pytest.MonkeyPatch):
    """When CJK gating eliminates all candidates, return fallback."""
    from chardet.pipeline import orchestrator  # noqa: PLC0415

    original_gate = orchestrator._gate_cjk_candidates

    def empty_gate(data: bytes, valid_candidates: object, ctx: object) -> tuple[()]:
        # Run the real gate to populate mb_scores, then return empty
        original_gate(data, valid_candidates, ctx)
        return ()

    monkeypatch.setattr(orchestrator, "_gate_cjk_candidates", empty_gate)
    data = bytes(range(0x80, 0x100)) * 2
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding is not None  # fallback


def test_fallback_when_structural_scores_high_but_statistical_empty():
    """Fall through to fallback when structural scores high but statistical empty.

    When structural scoring exceeds the threshold but statistical scoring
    returns no results (e.g. very short inputs), fall through to the
    no_match_encoding fallback instead of returning an empty list.

    Regression test for GitHub issue #367.
    """
    # b"\xf9\x92" is a valid cp932 multi-byte sequence that scores 1.0
    # structurally but yields no statistical bigram matches on 2 bytes.
    result = run_pipeline(b"\xf9\x92", EncodingEra.ALL)
    assert len(result) >= 1
    assert result[0].encoding is not None
