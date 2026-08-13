# tests/test_orchestrator.py
from __future__ import annotations

import pytest

import chardet.pipeline.orchestrator as _orchestrator_mod
from chardet.enums import EncodingEra
from chardet.pipeline import DetectionResult
from chardet.pipeline.orchestrator import run_pipeline

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


def test_xml_charset_declaration():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root>Hello</root>'
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "iso8859-1"


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
