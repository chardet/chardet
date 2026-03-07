"""Tests for Stage 2b: Multi-byte structural probing."""

from __future__ import annotations

from chardet.pipeline import PipelineContext
from chardet.pipeline.structural import (
    compute_lead_byte_diversity,
    compute_multibyte_byte_coverage,
    compute_structural_score,
)
from chardet.registry import REGISTRY


def _get_encoding(name: str):
    return REGISTRY[name]


def test_shift_jis_scores_high_on_shift_jis_data():
    data = "こんにちは世界".encode("shift_jis")
    score = compute_structural_score(
        data, _get_encoding("Shift-JIS-2004"), PipelineContext()
    )
    assert score > 0.7


def test_euc_jp_scores_high_on_euc_jp_data():
    data = "こんにちは世界".encode("euc-jp")
    score = compute_structural_score(
        data, _get_encoding("EUC-JIS-2004"), PipelineContext()
    )
    assert score > 0.7


def test_shift_jis_scores_low_on_euc_jp_data():
    ctx = PipelineContext()
    data = "こんにちは世界".encode("euc-jp")
    euc_score = compute_structural_score(data, _get_encoding("EUC-JIS-2004"), ctx)
    sjis_score = compute_structural_score(data, _get_encoding("Shift-JIS-2004"), ctx)
    assert euc_score > sjis_score


def test_euc_kr_scores_high_on_korean_data():
    data = "안녕하세요".encode("EUC-KR")
    score = compute_structural_score(data, _get_encoding("EUC-KR"), PipelineContext())
    assert score > 0.7


def test_gb18030_scores_high_on_chinese_data():
    data = "你好世界".encode("GB18030")
    score = compute_structural_score(data, _get_encoding("GB18030"), PipelineContext())
    assert score > 0.7


def test_big5_scores_high_on_big5_data():
    data = "你好世界".encode("big5")
    score = compute_structural_score(
        data, _get_encoding("Big5-HKSCS"), PipelineContext()
    )
    assert score > 0.7


def test_single_byte_encoding_returns_zero():
    data = b"Hello world"
    enc = _get_encoding("ISO-8859-1")
    score = compute_structural_score(data, enc, PipelineContext())
    assert score == 0.0


def test_empty_data_returns_zero():
    score = compute_structural_score(
        b"", _get_encoding("Shift-JIS-2004"), PipelineContext()
    )
    assert score == 0.0


def test_big5hkscs_scores_high_on_big5_data():
    data = "你好世界測試資料".encode("Big5-HKSCS")
    score = compute_structural_score(
        data, _get_encoding("Big5-HKSCS"), PipelineContext()
    )
    assert score > 0.7


def test_euc_jis_2004_scores_high_on_euc_jp_data():
    data = "こんにちは世界テスト".encode("EUC-JIS-2004")
    score = compute_structural_score(
        data, _get_encoding("EUC-JIS-2004"), PipelineContext()
    )
    assert score > 0.7


def test_shift_jis_2004_scores_high_on_shift_jis_data():
    data = "こんにちは世界テスト".encode("Shift-JIS-2004")
    score = compute_structural_score(
        data, _get_encoding("Shift-JIS-2004"), PipelineContext()
    )
    assert score > 0.7


def test_euc_jp_ss2_invalid_trail():
    """EUC-JP SS2 (0x8E) with invalid trail byte should not count as valid."""
    data = b"\x8e\x20"
    score = compute_structural_score(
        data, _get_encoding("EUC-JIS-2004"), PipelineContext()
    )
    assert score == 0.0


def test_euc_jp_ss3_valid():
    """EUC-JP SS3 (0x8F) with valid 3-byte JIS X 0212 sequence."""
    data = b"\x8f\xa1\xa1" * 5
    score = compute_structural_score(
        data, _get_encoding("EUC-JIS-2004"), PipelineContext()
    )
    assert score > 0.0


def test_euc_jp_ss3_invalid_trail():
    """EUC-JP SS3 (0x8F) with invalid trail bytes should not count as valid."""
    data = b"\x8f\xa1\x20"
    score = compute_structural_score(
        data, _get_encoding("EUC-JIS-2004"), PipelineContext()
    )
    assert score == 0.0


def test_multibyte_byte_coverage_all_ascii():
    """All-ASCII data should return 0.0 coverage for a multibyte encoding."""
    data = b"Hello world plain ASCII"
    enc = _get_encoding("Shift-JIS-2004")
    coverage = compute_multibyte_byte_coverage(
        data, enc, PipelineContext(), non_ascii_count=0
    )
    assert coverage == 0.0


def test_lead_byte_diversity_empty_data():
    """Empty data should return 0 diversity."""
    diversity = compute_lead_byte_diversity(
        b"", _get_encoding("Shift-JIS-2004"), PipelineContext()
    )
    assert diversity == 0


def test_coverage_no_analyzer_returns_zero():
    """An escape-protocol multibyte encoding with no analyzer returns 0.0."""
    enc = _get_encoding("HZ-GB-2312")
    coverage = compute_multibyte_byte_coverage(
        b"\x80\x81\x82", enc, PipelineContext(), non_ascii_count=3
    )
    assert coverage == 0.0


def test_diversity_no_analyzer_returns_256():
    """An escape-protocol multibyte encoding with no analyzer returns 256."""
    enc = _get_encoding("HZ-GB-2312")
    diversity = compute_lead_byte_diversity(b"\x80\x81", enc, PipelineContext())
    assert diversity == 256


def test_coverage_single_byte_encoding_returns_zero():
    """A single-byte encoding should return 0.0 coverage."""
    enc = _get_encoding("ISO-8859-1")
    coverage = compute_multibyte_byte_coverage(
        b"\xc0\xc1\xc2", enc, PipelineContext(), non_ascii_count=3
    )
    assert coverage == 0.0
