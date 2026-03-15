# tests/test_api.py
from __future__ import annotations

import warnings

import pytest

import chardet
from chardet.detector import UniversalDetector
from chardet.enums import EncodingEra, LanguageFilter
from chardet.registry import get_candidates, normalize_encodings


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
    det = UniversalDetector(should_rename_legacy=True)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    det.close()
    assert det.result["encoding"] == "Windows-1252"


def test_rename_legacy_detector_false():
    """UniversalDetector with False returns chardet 5.x compat name."""
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
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        UniversalDetector(lang_filter=LanguageFilter.CJK)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "lang_filter" in str(w[0].message)


def test_lang_filter_all_no_warning():
    """ALL lang_filter does not warn."""
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
    assert result["encoding"] == "utf-7"


def test_detect_utf7_era_all():
    """UTF-7 should be detected with EncodingEra.ALL (includes LEGACY_REGIONAL)."""
    data = "Meeting notes: 日本語テスト and Ñoño.".encode("utf-7")
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] == "utf-7"


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
    assert result["encoding"] == "utf-7"


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
        "iso2022_jp_2004",
        "iso2022_jp_ext",
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
    assert result["encoding"] == "hp-roman8"


# --- PEP 263 encoding declaration tests ---


def test_detect_pep263_emacs_style():
    """PEP 263 Emacs-style declaration on line 1."""
    data = b"# -*- coding: iso-8859-1 -*-\nx = '\xe9l\xe8ve'\n"
    result = chardet.detect(data, compat_names=False)
    assert result["encoding"] == "iso8859-1"
    assert result["confidence"] == 0.95


def test_detect_pep263_bare_form():
    """PEP 263 bare form: # coding=<encoding>."""
    data = b"# coding=utf-8\nx = 'hello'\n"
    result = chardet.detect(data, compat_names=False)
    assert result["encoding"] == "utf-8"
    assert result["confidence"] == 0.95


def test_detect_pep263_line2_with_shebang():
    """PEP 263 on line 2 after a shebang."""
    data = b"#!/usr/bin/env python\n# -*- coding: iso-8859-1 -*-\nx = '\xe9'\n"
    result = chardet.detect(data, compat_names=False)
    assert result["encoding"] == "iso8859-1"
    assert result["confidence"] == 0.95


def test_detect_pep263_line3_ignored():
    """PEP 263 on line 3 should be ignored (only lines 1-2 are valid)."""
    data = b"#!/usr/bin/env python\n# a comment\n# -*- coding: iso-8859-1 -*-\n"
    result = chardet.detect(data)
    # Should NOT return iso-8859-1 from PEP 263 — line 3 is too late.
    # The data is pure ASCII, so expect ascii.
    assert result["encoding"] == "ascii"


def test_detect_pep263_invalid_encoding_ignored():
    """PEP 263 with an unknown encoding name should fall through."""
    data = b"# -*- coding: not-a-real-encoding -*-\nhello world\n"
    result = chardet.detect(data)
    assert result["encoding"] == "ascii"


# --- compat_names and prefer_superset tests ---


def test_detect_compat_names_true_returns_display_names() -> None:
    """compat_names=True (default) returns 5.x/6.x display names."""
    result = chardet.detect(b"Hello world", compat_names=True)
    assert result["encoding"] == "ascii"


def test_detect_compat_names_false_returns_codec_names() -> None:
    """compat_names=False returns raw internal names (currently display-cased)."""
    result = chardet.detect(b"Hello world", compat_names=False)
    # With compat_names=False, the internal name passes through.
    # Currently internal name is "ASCII" (display-cased).
    # After the full refactor it will be "ascii" (codec name).
    assert result["encoding"] is not None


def test_detect_prefer_superset_remaps() -> None:
    """prefer_superset=True remaps ASCII to Windows-1252."""
    result = chardet.detect(b"Hello world", prefer_superset=True)
    assert result["encoding"] == "Windows-1252"


def test_detect_prefer_superset_false_no_remap() -> None:
    """prefer_superset=False (default) does not remap."""
    result = chardet.detect(b"Hello world", prefer_superset=False)
    assert result["encoding"] == "ascii"


def test_detect_prefer_superset_with_raw_codec_names() -> None:
    """prefer_superset=True with compat_names=False returns raw codec superset names."""
    result = chardet.detect(b"Hello world", prefer_superset=True, compat_names=False)
    assert result["encoding"] == "cp1252"


def test_detect_should_rename_legacy_deprecation() -> None:
    """should_rename_legacy emits DeprecationWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        chardet.detect(b"Hello world", should_rename_legacy=True)
        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 1
        assert "should_rename_legacy" in str(dep[0].message)


def test_detect_all_compat_names() -> None:
    """detect_all respects compat_names parameter."""
    results = chardet.detect_all(b"Hello world", compat_names=True)
    assert results[0]["encoding"] == "ascii"


def test_detect_all_prefer_superset() -> None:
    """detect_all respects prefer_superset parameter."""
    results = chardet.detect_all(b"Hello world", prefer_superset=True)
    assert results[0]["encoding"] == "Windows-1252"


# --- UniversalDetector compat_names / prefer_superset tests ---


def test_detector_compat_names() -> None:
    """UniversalDetector respects compat_names parameter."""
    det = UniversalDetector(compat_names=True)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    det.close()
    assert det.result["encoding"] == "ascii"


def test_detector_prefer_superset() -> None:
    """UniversalDetector respects prefer_superset parameter."""
    det = UniversalDetector(prefer_superset=True)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    det.close()
    assert det.result["encoding"] == "Windows-1252"


def test_detector_should_rename_legacy_deprecation() -> None:
    """UniversalDetector's should_rename_legacy emits DeprecationWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        UniversalDetector(should_rename_legacy=True)
        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 1
        assert "should_rename_legacy" in str(dep[0].message)


def test_universaldetector_compat_import() -> None:
    """chardet.universaldetector re-exports UniversalDetector for 6.x compat."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from chardet.universaldetector import UniversalDetector as CompatUD

        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 1
        assert "universaldetector" in str(dep[0].message)

    assert CompatUD is UniversalDetector


def test_normalize_encodings_none_returns_none():
    assert normalize_encodings(None, "include_encodings") is None


def test_normalize_encodings_valid_names():
    result = normalize_encodings(["utf-8", "cp1252"], "include_encodings")
    assert result == frozenset({"utf-8", "cp1252"})


def test_normalize_encodings_aliases():
    result = normalize_encodings(["windows-1252", "EUC-JP"], "include_encodings")
    assert result == frozenset({"cp1252", "euc_jis_2004"})


def test_normalize_encodings_unknown_raises():
    with pytest.raises(ValueError, match="Unknown encoding 'not-real'"):
        normalize_encodings(["utf-8", "not-real"], "include_encodings")


def test_normalize_encodings_empty_iterable():
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_encodings([], "include_encodings")


def test_detect_empty_include_raises():
    with pytest.raises(ValueError, match="must not be empty"):
        chardet.detect(b"Hello", include_encodings=[])


def test_get_candidates_include_only():
    result = get_candidates(
        EncodingEra.ALL,
        include_encodings=frozenset({"utf-8", "cp1252"}),
    )
    names = {e.name for e in result}
    assert names == {"utf-8", "cp1252"}


def test_get_candidates_exclude_only():
    result = get_candidates(
        EncodingEra.ALL,
        exclude_encodings=frozenset({"utf-8"}),
    )
    names = {e.name for e in result}
    assert "utf-8" not in names
    assert len(names) > 50


def test_get_candidates_include_and_exclude():
    result = get_candidates(
        EncodingEra.ALL,
        include_encodings=frozenset({"utf-8", "cp1252", "cp1251"}),
        exclude_encodings=frozenset({"cp1252"}),
    )
    names = {e.name for e in result}
    assert names == {"utf-8", "cp1251"}


def test_get_candidates_include_intersects_era():
    result = get_candidates(
        EncodingEra.MODERN_WEB,
        include_encodings=frozenset({"cp1252", "iso8859-1"}),
    )
    names = {e.name for e in result}
    assert names == {"cp1252"}


def test_get_candidates_all_filtered_returns_empty():
    result = get_candidates(
        EncodingEra.ALL,
        include_encodings=frozenset({"cp1252"}),
        exclude_encodings=frozenset({"cp1252"}),
    )
    assert result == ()


def test_get_candidates_none_defaults_unchanged():
    result_default = get_candidates(EncodingEra.MODERN_WEB)
    result_explicit = get_candidates(EncodingEra.MODERN_WEB, None, None)
    assert result_default == result_explicit


# --- include/exclude/fallback/empty integration tests ---


def test_detect_include_encodings_narrows():
    """include_encodings limits detection to specified encodings."""
    data = "Héllo wörld café résumé naïve".encode()
    result = chardet.detect(data, include_encodings=["cp1252"], compat_names=False)
    assert result["encoding"] == "cp1252"


def test_detect_exclude_encodings_removes():
    """exclude_encodings prevents specific encodings from being returned."""
    data = b"Hello world"
    result = chardet.detect(data, exclude_encodings=["ascii"], compat_names=False)
    assert result["encoding"] == "cp1252"


def test_detect_exclude_bom_result():
    """Excluding utf-8-sig should suppress BOM detection and fall through."""
    data = b"\xef\xbb\xbfHello world"
    result = chardet.detect(data, exclude_encodings=["utf-8-sig"], compat_names=False)
    assert result["encoding"] == "utf-8"


def test_detect_include_filters_bom():
    """include_encodings should filter BOM results too."""
    data = b"\xef\xbb\xbfHello world"
    result = chardet.detect(data, include_encodings=["cp1252"], compat_names=False)
    assert result["encoding"] == "cp1252"


def test_detect_custom_no_match_encoding():
    """Custom no_match_encoding is used when no candidates survive."""
    data = b"\x80\x81\x82\x83\x84\x85"
    result = chardet.detect(
        data,
        include_encodings=["ascii"],
        no_match_encoding="ascii",
        compat_names=False,
    )
    # Data has non-ASCII bytes so ascii won't pass byte-validity;
    # pipeline falls back to the specified no_match_encoding.
    # "ascii" is in include_encodings so it is NOT filtered out.
    assert result["encoding"] == "ascii"


def test_detect_custom_empty_input_encoding():
    """Custom empty_input_encoding is used for empty input."""
    result = chardet.detect(b"", empty_input_encoding="ascii", compat_names=False)
    assert result["encoding"] == "ascii"


def test_detect_filtered_no_match_warns():
    """Warning emitted when no_match_encoding is filtered out."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = chardet.detect(
            b"",
            include_encodings=["cp1252"],
            compat_names=False,
        )
        # Default empty_input_encoding is utf-8, which is not in include_encodings
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) >= 1
        assert result["encoding"] is None
        assert result["confidence"] == 0.0


def test_detect_binary_unaffected_by_filters():
    """Binary detection (encoding=None) is not subject to filters."""
    data = b"\x00" * 100
    result = chardet.detect(
        data,
        include_encodings=["utf-8"],
        compat_names=False,
    )
    assert result["encoding"] is None


def test_detect_all_with_include():
    """detect_all respects include_encodings."""
    data = "Héllo wörld café résumé naïve".encode()
    results = chardet.detect_all(
        data,
        include_encodings=["cp1252", "cp1251"],
        ignore_threshold=True,
        compat_names=False,
    )
    assert len(results) >= 1
    encodings = {r["encoding"] for r in results}
    assert encodings <= {"cp1252", "cp1251", None}


def test_detect_unknown_include_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", include_encodings=["not-a-real-encoding"])


def test_detect_unknown_exclude_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", exclude_encodings=["not-a-real-encoding"])


def test_detect_unknown_no_match_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", no_match_encoding="not-real")


def test_detect_unknown_empty_input_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", empty_input_encoding="not-real")


def test_detect_all_with_exclude():
    """detect_all respects exclude_encodings."""
    data = "Héllo wörld café résumé naïve".encode()
    results = chardet.detect_all(
        data,
        exclude_encodings=["utf-8"],
        ignore_threshold=True,
        compat_names=False,
    )
    encodings = {r["encoding"] for r in results}
    assert "utf-8" not in encodings


def test_detect_include_exclude_overlap():
    """Overlapping include and exclude yields encoding=None."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = chardet.detect(
            b"Hello",
            include_encodings=["ascii"],
            exclude_encodings=["ascii"],
            compat_names=False,
        )
        assert result["encoding"] is None
        assert result["confidence"] == 0.0
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) >= 1


# --- UniversalDetector include/exclude/fallback/empty tests ---


def test_detector_include_encodings():
    det = UniversalDetector(include_encodings=["cp1252"], compat_names=False)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    result = det.close()
    assert result["encoding"] == "cp1252"


def test_detector_exclude_encodings():
    det = UniversalDetector(exclude_encodings=["ascii"], compat_names=False)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    result = det.close()
    assert result["encoding"] == "cp437"


def test_detector_custom_empty_input_encoding():
    det = UniversalDetector(empty_input_encoding="ascii", compat_names=False)
    result = det.close()
    assert result["encoding"] == "ascii"


def test_detector_unknown_include_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        UniversalDetector(include_encodings=["not-real"])


def test_detector_unknown_exclude_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        UniversalDetector(exclude_encodings=["not-real"])


def test_detector_unknown_no_match_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        UniversalDetector(no_match_encoding="not-real")


def test_detector_unknown_empty_input_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        UniversalDetector(empty_input_encoding="not-real")


def test_detect_all_custom_empty_input_encoding():
    """detect_all respects empty_input_encoding."""
    result = chardet.detect_all(b"", empty_input_encoding="ascii", compat_names=False)
    assert result[0]["encoding"] == "ascii"


def test_detect_all_custom_no_match_encoding():
    """detect_all respects no_match_encoding."""
    data = b"\x80\x81\x82\x83\x84\x85"
    results = chardet.detect_all(
        data,
        include_encodings=["ascii"],
        no_match_encoding="ascii",
        ignore_threshold=True,
        compat_names=False,
    )
    assert results[0]["encoding"] == "ascii"
