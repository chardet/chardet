# tests/test_orchestrator.py
from __future__ import annotations

import pytest

from chardet.enums import EncodingEra
from chardet.pipeline import DetectionResult
from chardet.pipeline.orchestrator import run_pipeline


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
    assert result[0].encoding == "utf-16-le"
    assert result[0].confidence == 1.0


def test_bom_utf16_be():
    data = b"\xfe\xff" + "Hello world".encode("utf-16-be")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-16-be"
    assert result[0].confidence == 1.0


def test_bom_utf32_le():
    data = b"\xff\xfe\x00\x00" + "Hello world".encode("utf-32-le")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-32-le"
    assert result[0].confidence == 1.0


def test_bom_utf32_be():
    data = b"\x00\x00\xfe\xff" + "Hello world".encode("utf-32-be")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding == "utf-32-be"
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


def test_demote_niche_latin():
    """iso-8859-10 at top should be demoted when no distinguishing bytes."""
    from chardet.pipeline.orchestrator import _demote_niche_latin

    results = [
        DetectionResult("iso8859-10", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    # Data with only bytes shared between iso-8859-10 and iso-8859-1
    data = bytes([0xE9, 0xF6, 0xFC])  # é ö ü in both encodings
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_demote_niche_latin_no_demote_when_distinguishing():
    """iso-8859-10 should NOT be demoted when distinguishing bytes are present."""
    from chardet.pipeline.orchestrator import _demote_niche_latin

    results = [
        DetectionResult("iso8859-10", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    # 0xA1 differs between iso-8859-10 and iso-8859-1
    data = bytes([0xA1, 0xE9, 0xF6])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "iso8859-10"


def test_promote_koi8t_with_tajik_bytes():
    """KOI8-T should be promoted when Tajik-specific bytes are present."""
    from chardet.pipeline.orchestrator import _promote_koi8t

    results = [
        DetectionResult("koi8-r", 0.90, "ru"),
        DetectionResult("koi8-t", 0.88, "tg"),
    ]
    # 0x80 is a Tajik-specific byte in KOI8-T
    data = bytes([0x41, 0x80, 0x42])
    promoted = _promote_koi8t(data, results)
    assert promoted[0].encoding == "koi8-t"


def test_promote_koi8t_no_promote_without_tajik_bytes():
    """KOI8-T should NOT be promoted when no Tajik-specific bytes are present."""
    from chardet.pipeline.orchestrator import _promote_koi8t

    results = [
        DetectionResult("koi8-r", 0.90, "ru"),
        DetectionResult("koi8-t", 0.88, "tg"),
    ]
    # Only Cyrillic-range bytes shared between KOI8-R and KOI8-T
    data = bytes([0xC0, 0xC1, 0xC2])
    promoted = _promote_koi8t(data, results)
    assert promoted[0].encoding == "koi8-r"


def test_promote_koi8t_returns_early_when_koi8t_absent():
    """When KOI8-R is first but KOI8-T is not in results, return unchanged."""
    from chardet.pipeline.orchestrator import _promote_koi8t

    results = [
        DetectionResult("koi8-r", 0.90, "ru"),
        DetectionResult("cp1251", 0.85, "ru"),
    ]
    data = bytes([0x80, 0xC0, 0xC1])  # 0x80 is Tajik-specific but KOI8-T absent
    returned = _promote_koi8t(data, results)
    assert returned is results  # same object, unchanged
    assert returned[0].encoding == "koi8-r"


def test_fill_metadata_produces_language():
    """_fill_metadata should fill in language for single-language encodings."""
    from chardet.pipeline.orchestrator import _fill_metadata

    results = [DetectionResult("koi8-r", 0.90, None)]
    filled = _fill_metadata(b"test data", results)
    assert filled[0].language is not None


def test_confidence_clamped_to_one():
    """run_pipeline should never return confidence > 1.0."""
    # Use a CJK text that triggers the byte-coverage boost
    data = "これは日本語のテストです。日本語の文章を検出できるかどうかを確認します。".encode(
        "euc-jis-2004"
    )
    result = run_pipeline(data, EncodingEra.ALL)
    for r in result:
        assert r.confidence <= 1.0


def test_to_utf8_unknown_encoding():
    """_to_utf8 with an unknown encoding should return None."""
    from chardet.pipeline.orchestrator import _to_utf8

    result = _to_utf8(b"Hello world", "not-a-real-encoding")
    assert result is None


def test_to_utf8_passthrough():
    """_to_utf8 with utf-8 encoding should return data unchanged."""
    from chardet.pipeline.orchestrator import _to_utf8

    data = b"Hello \xc3\xa9"
    result = _to_utf8(data, "utf-8")
    assert result is data


def test_demote_niche_latin_iso_8859_14():
    """iso-8859-14 at top should be demoted when no distinguishing bytes."""
    from chardet.pipeline.orchestrator import _demote_niche_latin

    results = [
        DetectionResult("iso8859-14", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    data = bytes([0xC0, 0xC1, 0xC2])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_demote_niche_latin_windows_1254():
    """windows-1254 at top should be demoted when no distinguishing bytes."""
    from chardet.pipeline.orchestrator import _demote_niche_latin

    results = [
        DetectionResult("cp1254", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    data = bytes([0xC0, 0xC1, 0xE9])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_fallback_when_no_valid_candidates(monkeypatch: pytest.MonkeyPatch):
    """When validity filtering eliminates all candidates, return fallback."""
    from chardet.pipeline import orchestrator

    monkeypatch.setattr(orchestrator, "filter_by_validity", lambda _data, _cands: ())
    # Data must bypass BOM, UTF-16/32, escape, binary, markup, ASCII, and UTF-8
    data = bytes(range(0x80, 0x100)) * 2
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding is not None  # fallback, not None


def test_fallback_when_cjk_gate_eliminates_all(monkeypatch: pytest.MonkeyPatch):
    """When CJK gating eliminates all candidates, return fallback."""
    from chardet.pipeline import orchestrator

    original_gate = orchestrator._gate_cjk_candidates

    def empty_gate(data: bytes, valid_candidates: object, ctx: object) -> tuple[()]:
        # Run the real gate to populate mb_scores, then return empty
        original_gate(data, valid_candidates, ctx)
        return ()

    monkeypatch.setattr(orchestrator, "_gate_cjk_candidates", empty_gate)
    data = bytes(range(0x80, 0x100)) * 2
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding is not None  # fallback
