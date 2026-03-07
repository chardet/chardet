# tests/test_equivalences.py
from __future__ import annotations

from chardet.equivalences import (
    apply_legacy_rename,
    is_correct,
    is_equivalent_detection,
    is_language_equivalent,
)


def test_identical_decode_returns_true():
    """Pure ASCII data decoded as 'ascii' vs 'utf-8' is identical."""
    data = b"Hello, world!"
    assert is_equivalent_detection(data, "ascii", "utf-8") is True


def test_base_letter_match_returns_true():
    """Byte 0xC3 is A-tilde in iso-8859-1, A-breve in iso-8859-2.

    Both decompose to base letter 'A' after NFKD + strip combining.
    """
    data = b"\xc3"
    assert is_equivalent_detection(data, "iso-8859-1", "iso-8859-2") is True


def test_completely_different_decode_returns_false():
    """Latin accented letters vs Cyrillic letters have different base letters."""
    data = b"\xc0\xc1\xc2\xc3\xc4"
    assert is_equivalent_detection(data, "iso-8859-1", "iso-8859-5") is False


def test_none_detected_returns_false():
    """None detected encoding always returns False."""
    assert is_equivalent_detection(b"Hello", "utf-8", None) is False


def test_decode_error_returns_false():
    """Invalid bytes for the encoding cause decode failure -> False."""
    # 0x81 is not a valid lead byte in utf-8 by itself
    data = b"\x81\x82\x83"
    assert is_equivalent_detection(data, "iso-8859-1", "utf-8") is False


def test_empty_data_returns_true():
    """Empty bytes decode to empty string in any encoding -> identical."""
    assert is_equivalent_detection(b"", "utf-8", "iso-8859-1") is True


def test_ebcdic_pair_decodes_identically():
    """cp037 and cp500 decode 'Hello' bytes identically."""
    data = "Hello".encode("cp037")
    assert is_equivalent_detection(data, "cp037", "cp500") is True


def test_normalized_name_match_returns_true():
    """Encoding names that normalize to the same codec are considered equal."""
    data = b"Hello"
    assert is_equivalent_detection(data, "UTF-8", "utf8") is True


def test_unknown_encoding_returns_false():
    """Bogus encoding name that cannot be looked up returns False."""
    data = b"Hello"
    assert is_equivalent_detection(data, "utf-8", "not-a-real-encoding") is False


def test_currency_vs_euro_sign_accepted():
    """¤ (currency sign) vs € (euro sign) is an accepted symbol equivalence."""
    data = b"\xa4"
    assert is_equivalent_detection(data, "iso-8859-1", "iso-8859-15") is True


def test_symbol_vs_letter_difference_returns_false():
    """Symbol in one encoding vs letter in another should fail."""
    # 0xD7 = multiplication sign in iso-8859-1, Cyrillic letter in iso-8859-5
    data = b"\xd7"
    assert is_equivalent_detection(data, "iso-8859-1", "iso-8859-5") is False


def test_is_correct_exact_match():
    assert is_correct("utf-8", "utf-8") is True


def test_is_correct_none_detected():
    assert is_correct("utf-8", None) is False


def test_is_correct_superset():
    assert is_correct("ascii", "utf-8") is True


def test_is_correct_superset_reversed():
    assert is_correct("utf-8", "ascii") is False


def test_apply_legacy_rename_ascii():
    d = {"encoding": "ASCII", "confidence": 1.0, "language": None}
    apply_legacy_rename(d)
    assert d["encoding"] == "Windows-1252"


def test_apply_legacy_rename_no_match():
    d = {"encoding": "UTF-8", "confidence": 1.0, "language": None}
    apply_legacy_rename(d)
    assert d["encoding"] == "UTF-8"


def test_apply_legacy_rename_none():
    d = {"encoding": None, "confidence": 0.0, "language": None}
    apply_legacy_rename(d)
    assert d["encoding"] is None


def test_superset_equivalences_for_renamed_encodings() -> None:
    # big5 expected, big5hkscs detected -> correct (superset)
    assert is_correct("big5", "big5hkscs")
    # euc-jp expected, euc-jis-2004 detected -> correct
    assert is_correct("euc-jp", "euc-jis-2004")
    # shift_jis expected, shift_jis_2004 detected -> correct
    assert is_correct("shift_jis", "shift_jis_2004")
    # cp037 expected, cp1140 detected -> correct (cp1140 = cp037 + euro sign)
    assert is_correct("cp037", "cp1140")
    # iso-2022-jp expected, any branch -> correct
    assert is_correct("iso-2022-jp", "iso2022-jp-2")
    assert is_correct("iso-2022-jp", "iso2022-jp-2004")
    assert is_correct("iso-2022-jp", "iso2022-jp-ext")


def test_iso2022_jp_branches_bidirectional() -> None:
    # All three branches should be interchangeable
    assert is_correct("iso2022-jp-2", "iso2022-jp-2004")
    assert is_correct("iso2022-jp-2004", "iso2022-jp-ext")
    assert is_correct("iso2022-jp-ext", "iso2022-jp-2")


def test_is_correct_expected_none_detected_none():
    """Binary file: expected=None, detected=None -> correct."""
    assert is_correct(None, None) is True


def test_is_correct_expected_none_detected_encoding():
    """Binary file expected but encoding detected -> incorrect."""
    assert is_correct(None, "utf-8") is False


def test_is_equivalent_expected_none_detected_none():
    """Binary file: expected=None, detected=None -> equivalent."""
    assert is_equivalent_detection(b"\x00\x01", None, None) is True


def test_is_equivalent_expected_none_detected_encoding():
    """Binary file expected but encoding detected -> not equivalent."""
    assert is_equivalent_detection(b"\x00\x01", None, "utf-8") is False


# ---------------------------------------------------------------------------
# is_language_equivalent tests
# ---------------------------------------------------------------------------


def test_language_equivalent_exact_match():
    """Identical language codes are equivalent."""
    assert is_language_equivalent("ru", "ru") is True


def test_language_equivalent_east_slavic_group():
    """Languages in the East Slavic + Bulgarian group are equivalent."""
    assert is_language_equivalent("uk", "ru") is True
    assert is_language_equivalent("ru", "bg") is True
    assert is_language_equivalent("bg", "be") is True


def test_language_equivalent_scandinavian_group():
    """Scandinavian languages are equivalent."""
    assert is_language_equivalent("no", "da") is True
    assert is_language_equivalent("da", "sv") is True
    assert is_language_equivalent("sv", "no") is True


def test_language_equivalent_malay_indonesian():
    """Malay and Indonesian are equivalent."""
    assert is_language_equivalent("ms", "id") is True
    assert is_language_equivalent("id", "ms") is True


def test_language_equivalent_czech_slovak():
    """Czech and Slovak are equivalent."""
    assert is_language_equivalent("sk", "cs") is True
    assert is_language_equivalent("cs", "sk") is True


def test_language_equivalent_non_equivalent():
    """Languages in different groups are not equivalent."""
    assert is_language_equivalent("ru", "da") is False
    assert is_language_equivalent("sk", "sv") is False


def test_language_equivalent_unknown_language():
    """Unknown language code returns False."""
    assert is_language_equivalent("xx", "yy") is False
    assert is_language_equivalent("en", "fr") is False
