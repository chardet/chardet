"""Tests for CJK multi-byte gating in the pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

import chardet
from chardet.enums import EncodingEra
from chardet.pipeline.orchestrator import run_pipeline

_CJK_ENCODINGS = frozenset(
    {
        "GB18030",
        "Big5-HKSCS",
        "CP932",
        "CP949",
        "EUC-JIS-2004",
        "EUC-KR",
        "Shift-JIS-2004",
        "Johab",
        "HZ-GB-2312",
        "ISO-2022-JP-2",
        "ISO-2022-KR",
    }
)


def test_ebcdic_not_detected_as_gb18030():
    """EBCDIC text (cp037) should not be misdetected as gb18030."""
    data = "Hello World, this is a test of EBCDIC encoding.".encode("cp037")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding != "GB18030"


def test_latin_text_not_detected_as_cp932():
    """Western European text should not be misdetected as cp932/Shift_JIS."""
    data = "Héllo wörld, tëst dàta wïth äccénts.".encode("iso-8859-1")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding != "CP932"


def test_real_cjk_still_detected():
    """Real CJK text should still be detected as a CJK encoding."""
    data = "これはテストです。日本語のテキストです。".encode("shift_jis")
    result = run_pipeline(data, EncodingEra.ALL)
    assert result[0].encoding in {"Shift-JIS-2004", "CP932"}


def test_real_chinese_still_detected():
    """Real Chinese text should still be detected as a CJK encoding (not gated out)."""
    data = "这是一个测试。中文文本应该被正确检测。".encode("GB18030")
    result = run_pipeline(data, EncodingEra.ALL)
    # The gate should not eliminate CJK candidates when data has real multi-byte
    # sequences.  Exact CJK differentiation (gb18030 vs cp949 vs big5) is a
    # separate concern handled by Stage 3 statistical scoring.
    assert result[0].encoding in _CJK_ENCODINGS


def test_real_korean_still_detected():
    """Real Korean text should still be detected as a CJK encoding (not gated out)."""
    data = "이것은 테스트입니다. 한국어 텍스트입니다.".encode("euc-kr")
    result = run_pipeline(data, EncodingEra.ALL)
    # The gate should not eliminate CJK candidates when data has real multi-byte
    # sequences.  Exact CJK differentiation is a separate concern.
    assert result[0].encoding in _CJK_ENCODINGS


def test_german_macroman_not_detected_as_cjk() -> None:
    """German mac-roman text must not be detected as cp932."""
    test_file = (
        Path(__file__).parent / "data" / "macroman-german" / "culturax_mC4_83756.txt"
    )
    if not test_file.exists():
        pytest.skip("Test data not available")
    data = test_file.read_bytes()
    result = chardet.detect(data, encoding_era=EncodingEra.ALL)
    assert result["encoding"] not in _CJK_ENCODINGS, (
        f"European text falsely detected as {result['encoding']}"
    )
