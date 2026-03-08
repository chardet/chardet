# tests/test_github_issues.py
"""Regression tests from chardet/chardet GitHub issues.

Each test corresponds to a specific bug report with a reproducible test case.
Tests are grouped by category: short UTF-8, emoji, wrong encoding, escape
sequences, CJK, UTF-16/32, and miscellaneous.

Issues marked xfail are known limitations (ambiguous short inputs, pipeline
ordering issues) documented for future improvement.
"""

from __future__ import annotations

import pytest

import chardet
from chardet.enums import EncodingEra
from chardet.equivalences import is_correct, is_equivalent_detection


def _assert_detection(
    data: bytes,
    expected: str,
    *,
    era: EncodingEra = EncodingEra.ALL,
) -> None:
    """Assert that chardet detects the expected encoding (or an equivalent)."""
    result = chardet.detect(data, encoding_era=era, should_rename_legacy=True)
    detected = result["encoding"]
    assert is_correct(expected, detected) or is_equivalent_detection(
        data, expected, detected
    ), f"expected={expected}, got={detected} (confidence={result['confidence']:.2f})"


# =========================================================================
# SHORT INPUT / SINGLE CHARACTER UTF-8 DETECTION
# These were the most commonly reported class of bug in original chardet.
# =========================================================================


class TestShortUtf8:
    """Short UTF-8 strings with one or two multi-byte characters."""

    def test_single_eacute(self) -> None:
        """Issue #37: Single e-acute (2 bytes) detected as windows-1252."""
        _assert_detection(b"\xc3\xa9", "utf-8")

    def test_double_eacute(self) -> None:
        """Issue #37: Two e-acute chars should also work."""
        _assert_detection(b"\xc3\xa9\xc3\xa9", "utf-8")

    def test_foo_eacute(self) -> None:
        """Issue #134: 'foo e-acute' detected as ISO-8859-1."""
        _assert_detection(b"foo \xc3\xa9", "utf-8")

    def test_degree_symbol(self) -> None:
        """Issue #305: UTF-8 degree symbol detected as ISO-8859-1."""
        _assert_detection(b"\xc2\xb0", "utf-8")

    def test_german_umlaut_in_sentence(self) -> None:
        """Issue #288: German text with o-umlaut detected as ISO-8859-9."""
        _assert_detection(b"Sch\xc3\xb6ne gesunde Pflanzen", "utf-8")

    def test_pokemon_slogan(self) -> None:
        """Issue #308: Mostly-ASCII UTF-8 with e-acute detected as MacRoman."""
        _assert_detection(b'___!" (Pok\xc3\xa9mon slogan)', "utf-8")

    def test_bullet_character(self) -> None:
        """Issue #61: UTF-8 bullet (U+2022) detected as windows-1252."""
        _assert_detection(b"FAHR\xe2\x80\xa2WERK", "utf-8")

    def test_right_single_quotation(self) -> None:
        """Issue #185: Right single quotation mark detected as windows-1252."""
        _assert_detection(b"Carter\xe2\x80\x99s Janitorial", "utf-8")

    def test_python_file_with_umlaut(self) -> None:
        """Issue #75: UTF-8 Python file with single u-umlaut."""
        _assert_detection(
            b"#!/usr/bin/env python3\n# coding: utf-8\n#\n"
            b"###############################################"
            b"#############################\n\n"
            b"__version__ = '1.0'\n__author__ = '\xc3\xbc'\n",
            "utf-8",
        )

    def test_csv_with_umlaut(self) -> None:
        """Issue #138: UTF-8 CSV with single a-umlaut detected as ISO-8859-1."""
        _assert_detection(
            b'"Companyname","Prename","Surename","Streetname","ZIP","City",'
            b'"Phone","Fax","Email","Website","Category"\n'
            b'"Whatever GmbH","Mike","H\xc3\xa4n","Burger Str 8C","39925",'
            b'"Bonn","+49 511 123432","+49 511 1234312",'
            b'"bonn@whatever.com","http://www.whatever.de","Business"\n',
            "utf-8",
        )

    def test_gebuehrenfrei(self) -> None:
        """Issue #28: 'gebuehrenfrei' with u-umlaut."""
        _assert_detection(b"geb\xc3\xbchrenfrei", "utf-8")

    def test_example_aacute(self) -> None:
        """Issue #28: 'example' with a-acute."""
        _assert_detection(b"ex\xc3\xa1mple", "utf-8")

    def test_naive_idiaeresis(self) -> None:
        """Issue #28: 'naive' with i-diaeresis."""
        _assert_detection(b"na\xc3\xafve", "utf-8")

    def test_sie_hoeren(self) -> None:
        """Issue #28: 'sie hoeren' with o-umlaut."""
        _assert_detection(b"sie h\xc3\xb6ren", "utf-8")

    def test_section_sign(self) -> None:
        """Issue #308: Section sign (U+00A7) detected as TIS-620."""
        _assert_detection(b"42 CFR \xc2\xa7 400.200\n", "utf-8")

    def test_cinecitt_agrave(self) -> None:
        """Issue #60: 'Cinecitt-a-grave Make' detected as ISO-8859-2."""
        _assert_detection(b"Cinecitt\xc3\xa0 Make", "utf-8")

    def test_utf8_extended_latin(self) -> None:
        """Issue #292: UTF-8 with extended Latin chars detected as Windows-1254."""
        _assert_detection(
            b"# test data with some utf-8 sequences\n"
            b"\xc4\x80\xc4\x81\xc4\x82\xc4\x83"
            b"\xc3\x90"
            b" some more ascii text here\n",
            "utf-8",
        )

    def test_utf8_abcapitalia(self) -> None:
        """Issue #160: UTF-8 'ab-Capital I with grave-a' misdetected."""
        _assert_detection(b"\x61\x62\xc3\x8f\x61", "utf-8")


# =========================================================================
# UTF-8 WITH EMOJI / 4-BYTE SEQUENCES
# =========================================================================


class TestUtf8Emoji:
    """UTF-8 with 4-byte emoji sequences."""

    def test_purple_heart_emoji(self) -> None:
        """Issue #128: Purple heart emoji breaks UTF-8 detection."""
        _assert_detection(
            b'scriptencoding utf-8\n" \xf0\x9f\x92\x9c\n'
            b'" set list listchars=tab:\xc2\xbb\xc2\xb7,trail:\xc2\xb7,'
            b"eol:\xc2\xac,nbsp:_,extends:\xe2\x9d\xaf,precedes:\xe2\x9d\xae\n",
            "utf-8",
        )

    def test_cat_emoji(self) -> None:
        """Issue #28: Cat emoji in UTF-8."""
        _assert_detection(b"This is a cat \xf0\x9f\x98\xb8", "utf-8")


# =========================================================================
# UTF-8 BOM
# =========================================================================


class TestUtf8Bom:
    """UTF-8 BOM (byte order mark) detection."""

    def test_bom_with_crlf(self) -> None:
        """Issue #34: UTF-8 BOM with Windows line endings."""
        _assert_detection(b"\xef\xbb\xbf\r\n#include <stdio.h>\r\n", "utf-8-sig")

    def test_bom_hello_world(self) -> None:
        """Issue #30: UTF-8 BOM should be detected as utf-8-sig."""
        _assert_detection(b"\xef\xbb\xbfHello World", "utf-8-sig")


# =========================================================================
# ESCAPE SEQUENCE / HZ-GB-2312 FALSE POSITIVES
# =========================================================================


class TestEscapeSequences:
    """Escape sequence and HZ-GB-2312 false positive prevention."""

    def test_tilde_brace_not_hz(self) -> None:
        """Issue #82: ASCII text with ~{ and ~} not falsely detected as HZ-GB-2312."""
        _assert_detection(b"~{,\n~},\n", "ascii")

    def test_tilde_brace_inline(self) -> None:
        """Issue #290: 'xxx~{xxx' should not trigger HZ-GB-2312."""
        _assert_detection(b"xxx~{xxx", "ascii")

    def test_esc_in_utf8(self) -> None:
        """Issue #65: UTF-8 with trailing ESC byte returns None."""
        _assert_detection(b"\xc8\x8d\x1b", "utf-8")

    def test_esc_in_ascii_long(self) -> None:
        """Issue #63: Long ASCII text with single trailing ESC byte."""
        # With enough ASCII bytes, the single ESC should not trigger binary
        _assert_detection(b"0" * 100 + b"\x1b", "ascii")


# =========================================================================
# UTF-16 / UTF-32 ISSUES
# =========================================================================


class TestUtf1632:
    """UTF-16 and UTF-32 detection edge cases."""

    def test_utf16_with_null_after_bom(self) -> None:
        """Issue #62: UTF-16 BOM + U+0000 + U+0030 misread as UTF-32-LE."""
        _assert_detection(b"\xff\xfe\x00\x000\x00", "utf-16")

    def test_utf16le_no_bom(self) -> None:
        """Issue #105: UTF-16LE without BOM detected via null-byte pattern."""
        _assert_detection(
            b"H\x00e\x00l\x00l\x00o\x00 \x00W\x00o\x00r\x00l\x00d\x00",
            "utf-16-le",
        )


# =========================================================================
# CJK ENCODING ISSUES (short inputs)
# =========================================================================


class TestCjkShortInputs:
    """CJK encoding detection with very short inputs.

    These are inherently ambiguous: a handful of high bytes can be valid
    in multiple single-byte AND multi-byte encodings.  Our CJK gating
    requires a minimum number of non-ASCII bytes to avoid false positives.
    """

    def test_single_chinese_char_gb2312(self) -> None:
        """Issue #219: Single Chinese char in GB2312 detected as Cyrillic."""
        _assert_detection(b"\xd6\xd0", "gb2312")

    def test_korean_name_euckr(self) -> None:
        """Issue #161: Korean name (6 bytes) in EUC-KR."""
        _assert_detection(b"\xb1\xe8\xbc\xba\xbd\xc4", "euc-kr")

    @pytest.mark.xfail(
        reason="Only 4 non-ASCII bytes in mostly-ASCII context — below "
        "CJK gating threshold (chardet/chardet#294)",
        strict=True,
    )
    def test_chinese_in_ascii_path(self) -> None:
        """Issue #294: Two Chinese chars in a file path."""
        _assert_detection(
            b"*file_import {D:/\xc9\xe8\xbc\xc6-1.step} {Step Files}",
            "gb2312",
        )

    def test_chinese_gb2312_text(self) -> None:
        """Issue #247: Chinese GB2312 text (10 bytes, enough signal)."""
        _assert_detection(b"\xb0\xb2\xbb\xd5\xb9\xe3\xcc\xb6\xb3\xa1", "gb2312")


# =========================================================================
# GB18030 / BOM ISSUES
# =========================================================================


class TestGb18030:
    """GB18030 detection."""

    def test_gb18030_with_bom(self) -> None:
        """Issue #178: GB18030 text with BOM detected as windows-1252."""
        _assert_detection(
            b"\x841\x953"  # GB18030 encoding of U+FEFF (BOM)
            b"\xce\xd2\xc3\xbb\xd3\xd0\xc2\xf1\xd4\xb9\xa3\xac"
            b"\xb4\xe8\xc5\xe8\xb5\xc4\xd6\xbb\xca\xc7\xd2\xbb"
            b"\xd0\xa9\xca\xb1\xbc\xe4\xa1\xa3",
            "gb18030",
        )


# =========================================================================
# WRONG ENCODING WITH MODERN_WEB ERA
# These pass with MODERN_WEB (the default) but may fail with ALL era.
# =========================================================================


class TestWrongEncodingModernWeb:
    """Detection failures that are fixed with the default MODERN_WEB era."""

    def test_portuguese_iso88591(self) -> None:
        """Issue #24: Portuguese ISO-8859-1 text detected as Cyrillic."""
        _assert_detection(
            b'"ULTIMA ATUALIZACAO";"17/03/2014 04:01"\r\n'
            b'"ANO";"MES";"SENADOR";"TIPO_DESPESA";"CNPJ_CPF";'
            b'"FORNECEDOR";"DOCUMENTO";"DATA";"DETALHAMENTO";'
            b'"VALOR_REEMBOLSADO"\r\n'
            b'"2011";"1";"ACIR GURGACZ";"Aluguel de im\xf3veis para '
            b"escrit\xf3rio pol\xedtico, compreendendo despesas "
            b'concernentes a eles.";"05.914.650/0001-66";"CERON - '
            b"CENTRAIS EL\xc9TRICAS DE ROND\xd4NIA "
            b'S.A.";"45216633";"11/01/11";"";"47,65"\r\n',
            "iso-8859-1",
        )

    def test_smart_apostrophe_win1252(self) -> None:
        """Issue #53: MS smart apostrophe (0x92) detected correctly."""
        _assert_detection(
            b"today\x92s research", "windows-1252", era=EncodingEra.MODERN_WEB
        )

    def test_latin1_accented_chars(self) -> None:
        """Issue #242: Latin-1 text with accented chars."""
        _assert_detection(
            b"latin-1 encoded string > \xe9\xe1\xfb",
            "iso-8859-1",
            era=EncodingEra.MODERN_WEB,
        )

    def test_subtitle_acute_apostrophes(self) -> None:
        """Issue #279: Subtitle text with acute accents as apostrophes."""
        _assert_detection(
            b"y!\r\n- We\xb4re going to get him.\r\n- He was here.\r\n"
            b"Don\xb4t worry, we\xb4ll find him.\r\n"
            b"I\xb4m sure he\xb4s around here somewhere.\r\n"
            b"Let\xb4s keep looking.\r\n",
            "iso-8859-1",
            era=EncodingEra.MODERN_WEB,
        )

    def test_iso88591_pound_middot(self) -> None:
        """Issue #170: ISO-8859-1 English with pound sign and middle dots."""
        _assert_detection(
            b"OTE up to \xa350K first year!. to emergency situations "
            b"\xb7 perform all activities with children, i.e. jump, "
            b"dance, walk, run, etc. for extended periods of time "
            b"\xb7 must possess acceptable hearing... . oh. "
            b"to emergency situations \xb7 perform all activities "
            b"with children, i.e. jump, dance, walk, run, etc. for "
            b"extended periods of time \xb7 both indoor and outdoor..."
            b" . ok. for the public including lectures, concerts, "
            b"recitals, dramatic productions, dance performances, "
            b"films, and art exhibits. laurens county renowned "
            b"quality of... . sc.",
            "iso-8859-1",
            era=EncodingEra.MODERN_WEB,
        )


# =========================================================================
# REMAINING KNOWN FAILURES
# =========================================================================


class TestKnownFailures:
    """Cases that still fail — documented for future improvement."""

    @pytest.mark.xfail(
        reason="French windows-1252 text with anonymized content — "
        "statistical model ranks windows-1251 higher due to mostly-'x' "
        "bigrams (chardet/chardet#96)",
        strict=True,
    )
    def test_french_win1252_anonymized(self) -> None:
        """Issue #96: French windows-1252 text detected as windows-1251."""
        _assert_detection(
            b"xxxx), xx xxxxxx xx xxxxxx xx\xe9\xe9x \xe0 xxxxx x xxxx \n"
            b"xxxxx\xe9 xx xx xxx xxxxxxx\xe9.\n\n*__*\n\n"
            b"xx *xxx, x. xxxxx*, xxxxx xxxxxxx xx xxxxxx xxxx "
            b"x\xe9xxxxxx \xe0 xxxxxxxx \n"
            b"xxxx xxx xxxxxxxxx xxxxxx\xe9xx xxx xxx "
            b"xxxxxxxxxxxxxxx xxxx xx xx xx xx \n"
            b"xxxxxxx xx\xe9x\xe9xxxxx :\n\n"
            b"- xx xxxxxx x\\xxxxxxxxxxxx xxxxxxxxxx \xe0 "
            b"x\\xxxxxxxxxxxxxx\xe9 xx xxxx xx xxxx : xxx \n"
            b"xx ; xxx (xxxx) / xxx (xxxx) xxxxxx.\n\n"
            b"- xxx x\xe9xxxxxx xxx xxxxxxxxxxxx xxxx xxxx : "
            b"xx xxxx\xe9xxxxxxx xxxxxxxxx \n"
            b"(xx xxx xxx \\xxxxx) / xxxxxxxxx (xx xxx xxx \\xxxxx) "
            b"xxx xxxxxxx x\\xxxxxxxx xxxxxxxxx\xe9 \n"
            b"xx xxx.\n\n"
            b"- xxx x\xe9xxxxxx xxx xxxxxx xx xxxxxxxxx xxxx xxxx : "
            b"xx xxxx\xe9xxxxx xxxxx \n"
            b"xxx x\xe9xxxxxx xxxx xx xxxxxxx (xx xxx xxx \\xxxxx) "
            b"xx xxxxxx xxxx xx xxxxxx (xx \n"
            b"xxx xxx \\xxxxx) x\\xxxxxxxxxxxxx xxx xx xx\xfbx xxxx "
            b"xxxxxxxxx xxx xxxxxx (xxxxxxxxx \n"
            b"xxxx xxxxxx, xxxxx xx xxxxxxxxx xxxx xxxxxxxxx ...) "
            b"xx x\\xxxxxxxxxxx xx \n"
            b"xxxxxxxxxx xxx\xe9xxxxxxx xxxx xxxxxxxx xxxxxxx.\n\n"
            b"- xxx xxxxxx x\\xxxxxxxxxxxxxxxx : xx xxxx\xe9xxxxx "
            b"xx xxxxxxxx xx\xe9xxxx xxxxx \n"
            b"xxxx xx xxxx xxxxxxx\xe9x xx xxxxxxx xxxxx\xe8",
            "windows-1252",
        )


# =========================================================================
# WINDOWS-1252 SPECIFIC BYTE DETECTION
# =========================================================================


class TestWindows1252Bytes:
    """Detection of bytes unique to windows-1252 (C1 range 0x80-0x9F)."""

    def test_euro_sign_win1252(self) -> None:
        """Issue #317: Single euro sign in windows-1252."""
        _assert_detection(b"\x80", "windows-1252")


# =========================================================================
# ISO-8859-7 (GREEK) ISSUES
# =========================================================================


class TestGreek:
    """ISO-8859-7 Greek text detection."""

    def test_nbsp_with_angle_bracket(self) -> None:
        """Issue #64: NBSP (0xa0) in short context."""
        _assert_detection(b"<\xa0", "iso-8859-7")

    def test_greek_text_omilia(self) -> None:
        """Issue #124: Greek text 'Me omilia tis' in ISO-8859-7."""
        _assert_detection(
            b"\xcc\xe5 \xef\xec\xe9\xeb\xdf\xe1 \xf4\xe7\xf2",
            "iso-8859-7",
        )


# =========================================================================
# NO-CRASH TESTS (issues that caused exceptions in original chardet)
# =========================================================================


class TestNoCrash:
    """Inputs that caused exceptions in original chardet."""

    def test_issue_67_no_crash(self) -> None:
        r"""Issue #67: b'\xfe\xcf' caused IndexError in original chardet."""
        result = chardet.detect(b"\xfe\xcf", encoding_era=EncodingEra.ALL)
        # Just verify it doesn't crash; any result is acceptable
        assert isinstance(result, dict)
        assert "encoding" in result
