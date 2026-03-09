# tests/test_api.py
from __future__ import annotations

import warnings

import pytest

import chardet
from chardet.enums import EncodingEra, LanguageFilter


def test_detect_returns_dict():
    result = chardet.detect(b"Hello world")
    assert isinstance(result, dict)
    assert "encoding" in result
    assert "confidence" in result
    assert "language" in result


def test_detect_ascii():
    result = chardet.detect(b"Hello world")
    # Default should_rename_legacy=False returns chardet 5.x compat names.
    assert result["encoding"] == "ascii"
    assert result["confidence"] == 1.0


def test_detect_utf8_bom():
    result = chardet.detect(b"\xef\xbb\xbfHello")
    assert result["encoding"] == "UTF-8-SIG"


def test_detect_utf8_multibyte():
    data = "Héllo wörld café".encode()
    result = chardet.detect(data)
    assert result["encoding"] == "utf-8"


def test_detect_empty():
    result = chardet.detect(b"")
    assert result["encoding"] == "utf-8"
    assert result["confidence"] == 0.10


def test_detect_with_encoding_era():
    data = b"Hello world"
    result = chardet.detect(data, encoding_era=EncodingEra.MODERN_WEB)
    assert result["encoding"] is not None


def test_encoding_era_excludes_legacy():
    """MODERN_WEB excludes legacy encodings; ALL includes them."""
    # Greek text that should be detected as iso-8859-7 (Legacy ISO) when
    # legacy eras are enabled, but not when restricted to MODERN_WEB.
    data = (
        "Η Αθήνα είναι η πρωτεύουσα και μεγαλύτερη πόλη της Ελλάδας. "
        "Η πόλη έχει μακρά ιστορία που εκτείνεται πάνω από τρεις χιλιετίες."
    ).encode("iso-8859-7")
    modern = chardet.detect(
        data, encoding_era=EncodingEra.MODERN_WEB, should_rename_legacy=False
    )
    legacy = chardet.detect(
        data, encoding_era=EncodingEra.ALL, should_rename_legacy=False
    )
    # With ALL, iso-8859-7 should be detected
    assert legacy["encoding"] == "ISO-8859-7"
    # With MODERN_WEB only, iso-8859-7 is not a candidate so the result
    # must be a different encoding (windows-1253 is the modern Greek encoding)
    assert modern["encoding"] != "iso-8859-7"


def test_detect_with_max_bytes():
    data = b"Hello world" * 100_000
    result = chardet.detect(data, max_bytes=100)
    assert result["encoding"] is not None
    assert result["confidence"] > 0


def test_detect_all_returns_list():
    result = chardet.detect_all(b"Hello world")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_detect_all_sorted_by_confidence():
    data = "Héllo wörld".encode()
    results = chardet.detect_all(data)
    confidences = [r["confidence"] for r in results]
    assert confidences == sorted(confidences, reverse=True)


def test_detect_all_each_is_dict():
    results = chardet.detect_all(b"Hello world")
    for r in results:
        assert "encoding" in r
        assert "confidence" in r
        assert "language" in r


def test_version_exists():
    assert hasattr(chardet, "__version__")
    assert isinstance(chardet.__version__, str)
    assert len(chardet.__version__) > 0
    # Version should start with a digit (e.g., "7.0.0" or "7.0.1.dev3+g...")
    assert chardet.__version__[0].isdigit(), chardet.__version__


# --- should_rename_legacy tests ---


def test_rename_legacy_default():
    """Default (False) returns chardet 5.x compat name."""
    result = chardet.detect(b"Hello world")
    assert result["encoding"] == "ascii"


def test_rename_legacy_false():
    """Explicit False returns chardet 5.x compat name."""
    result = chardet.detect(b"Hello world", should_rename_legacy=False)
    assert result["encoding"] == "ascii"


def test_rename_legacy_true():
    """Explicit True renames regardless of era."""
    result = chardet.detect(
        b"Hello world",
        should_rename_legacy=True,
        encoding_era=EncodingEra.ALL,
    )
    assert result["encoding"] == "Windows-1252"


def test_rename_legacy_default_with_all_era():
    """Default (False) with ALL era returns compat name."""
    result = chardet.detect(b"Hello world", encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "ascii"


def test_rename_legacy_detect_all():
    """should_rename_legacy applies to detect_all() results too."""
    results = chardet.detect_all(b"Hello world", should_rename_legacy=True)
    assert results[0]["encoding"] == "Windows-1252"


def test_rename_legacy_detect_all_false():
    """should_rename_legacy=False returns chardet 5.x compat names in detect_all."""
    results = chardet.detect_all(b"Hello world", should_rename_legacy=False)
    assert results[0]["encoding"] == "ascii"


def test_rename_legacy_detector():
    """UniversalDetector applies rename on close()."""
    from chardet.detector import UniversalDetector

    det = UniversalDetector(should_rename_legacy=True)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    det.close()
    assert det.result["encoding"] == "Windows-1252"


def test_rename_legacy_detector_false():
    """UniversalDetector with False returns chardet 5.x compat name."""
    from chardet.detector import UniversalDetector

    det = UniversalDetector(should_rename_legacy=False)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    det.close()
    assert det.result["encoding"] == "ascii"


def test_compat_names_eucjp():
    """Compat mode maps EUC-JIS-2004 back to EUC-JP."""
    text = (
        "東京は日本の首都です。人口は約1400万人で、世界最大の都市圏を形成しています。"
    )
    data = text.encode("euc_jp")
    result = chardet.detect(data, should_rename_legacy=False)
    assert result["encoding"] == "EUC-JP"


# --- ignore_threshold tests ---


def test_ignore_threshold_false_filters():
    """Default ignore_threshold=False filters low-confidence results."""
    data = "Héllo wörld café résumé".encode()
    results_all = chardet.detect_all(data, ignore_threshold=True)
    results_filtered = chardet.detect_all(data, ignore_threshold=False)
    assert len(results_filtered) <= len(results_all)
    for r in results_filtered:
        assert r["confidence"] > 0.20


def test_ignore_threshold_true_returns_all():
    """ignore_threshold=True returns all candidates."""
    data = "Héllo wörld café résumé".encode()
    results = chardet.detect_all(data, ignore_threshold=True)
    assert len(results) >= 1


def test_ignore_threshold_fallback():
    """If all results filtered, fall back to top result."""
    results = chardet.detect_all(b"", ignore_threshold=False)
    assert len(results) >= 1


# --- lang_filter DeprecationWarning test ---


def test_lang_filter_warning():
    """Non-ALL lang_filter emits DeprecationWarning."""
    from chardet.detector import UniversalDetector

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        UniversalDetector(lang_filter=LanguageFilter.CJK)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "lang_filter" in str(w[0].message)


def test_lang_filter_all_no_warning():
    """ALL lang_filter does not warn."""
    from chardet.detector import UniversalDetector

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        UniversalDetector(lang_filter=LanguageFilter.ALL)
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 0


# --- max_bytes validation tests ---


def test_detect_max_bytes_bool_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        chardet.detect(b"Hello", max_bytes=True)


def test_detect_max_bytes_zero_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        chardet.detect(b"Hello", max_bytes=0)


def test_detect_max_bytes_negative_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        chardet.detect(b"Hello", max_bytes=-1)


def test_detect_all_max_bytes_zero_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        chardet.detect_all(b"Hello", max_bytes=0)


def test_detect_all_max_bytes_negative_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        chardet.detect_all(b"Hello", max_bytes=-1)


# --- chunk_size deprecation tests ---


def test_chunk_size_deprecation_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        chardet.detect(b"Hello", chunk_size=1024)
        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 1
        assert "chunk_size" in str(dep[0].message)


def test_default_chunk_size_no_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        chardet.detect(b"Hello")
        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 0


# --- bytearray input tests ---


def test_detect_bytearray_input():
    result = chardet.detect(bytearray(b"Hello world"))
    assert result["encoding"] is not None


def test_detect_all_bytearray_input():
    results = chardet.detect_all(bytearray(b"Hello world"))
    assert len(results) >= 1


# --- New encoding tests ---


def test_detect_utf7():
    data = "Hello, 世界!".encode("utf-7")
    result = chardet.detect(data)
    assert result["encoding"] == "UTF-7"


def test_detect_utf7_era_all():
    """UTF-7 should be detected with EncodingEra.ALL (includes LEGACY_REGIONAL)."""
    data = "Meeting notes: 日本語テスト and Ñoño.".encode("utf-7")
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "UTF-7"


def test_detect_utf7_era_modern_web_skipped():
    """UTF-7 should NOT be detected with MODERN_WEB (disabled by browsers since ~2020)."""
    data = "Hello, 世界!".encode("utf-7")
    result = chardet.detect(data, encoding_era=EncodingEra.MODERN_WEB)
    assert result["encoding"] != "UTF-7"


def test_detect_utf7_multi_paragraph():
    """Longer UTF-7 documents with multiple shifted sequences must still be detected."""
    text = (
        "From: user@example.com\r\n"
        "Subject: Réunion\r\n"
        "\r\n"
        "Bonjour à tous,\r\n"
        "La réunion aura lieu à 14h dans la salle côté jardin.\r\n"
        "Merci de préparer les données sur les résultats financiers.\r\n"
        "Cordialement,\r\n"
        "François\r\n"
    )
    data = text.encode("utf-7")
    result = chardet.detect(data)
    assert result["encoding"] == "UTF-7"


def test_detect_hz_gb_2312_era_all():
    """hz-gb-2312 should be detected with EncodingEra.ALL."""
    data = b"Hello ~{CEDE~} World"
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "HZ-GB-2312"


def test_detect_hz_gb_2312_era_modern_web_skipped():
    """hz-gb-2312 is WHATWG 'replacement' - should NOT be detected with MODERN_WEB."""
    data = b"Hello ~{CEDE~} World"
    result = chardet.detect(data, encoding_era=EncodingEra.MODERN_WEB)
    assert result["encoding"] != "hz-gb-2312"


def test_detect_iso_2022_kr_era_all():
    """iso-2022-kr should be detected with EncodingEra.ALL."""
    data = b"\x1b$)C\x0e\x21\x21\x0f"
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "ISO-2022-KR"


def test_detect_iso_2022_kr_era_modern_web_skipped():
    """iso-2022-kr is WHATWG 'replacement' - should NOT be detected with MODERN_WEB."""
    data = b"\x1b$)C\x0e\x21\x21\x0f"
    result = chardet.detect(data, encoding_era=EncodingEra.MODERN_WEB)
    assert result["encoding"] != "iso-2022-kr"


def test_detect_iso_2022_jp_era_modern_web_still_works():
    """ISO-2022-JP is NOT in WHATWG 'replacement' - should still be detected with MODERN_WEB."""
    data = b"Hello \x1b$B$3$s$K$A$O\x1b(B World"
    result = chardet.detect(data, encoding_era=EncodingEra.MODERN_WEB)
    assert result["encoding"] in {
        "ISO-2022-JP",
        "ISO-2022-JP-2",
        "ISO-2022-JP-2004",
        "ISO-2022-JP-EXT",
    }


def test_detect_cp273():
    data = "Grüße aus Deutschland".encode("cp273")
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] is not None
    # Should detect an EBCDIC encoding (cp273 or a close variant)
    assert result["encoding"].upper().startswith("CP")


def test_detect_hp_roman8():
    data = (
        "Les élèves français étudient la littérature européenne avec "
        "enthousiasme. Après les études, ils préfèrent dîner dans un "
        "café où ils discutent de philosophie et dégustent des crêpes "
        "flambées accompagnées de thé à la menthe."
    ).encode("hp-roman8")
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "HP-Roman8"
