"""Tests for Stage 2b: Multi-byte structural probing."""

from __future__ import annotations

import pytest

from chardet.pipeline import PipelineContext
from chardet.pipeline.structural import (
    compute_lead_byte_diversity,
    compute_multibyte_byte_coverage,
    compute_structural_score,
)
from chardet.registry import REGISTRY


@pytest.fixture
def pipe_ctx() -> PipelineContext:
    return PipelineContext()


def test_shift_jis_scores_high_on_shift_jis_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界".encode("shift_jis")
    score = compute_structural_score(data, REGISTRY["Shift-JIS-2004"], pipe_ctx)
    assert score > 0.7


def test_euc_jp_scores_high_on_euc_jp_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界".encode("euc-jp")
    score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    assert score > 0.7


def test_shift_jis_scores_low_on_euc_jp_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界".encode("euc-jp")
    euc_score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    sjis_score = compute_structural_score(data, REGISTRY["Shift-JIS-2004"], pipe_ctx)
    assert euc_score > sjis_score


def test_euc_kr_scores_high_on_korean_data(pipe_ctx: PipelineContext) -> None:
    data = "안녕하세요".encode("EUC-KR")
    score = compute_structural_score(data, REGISTRY["EUC-KR"], pipe_ctx)
    assert score > 0.7


def test_gb18030_scores_high_on_chinese_data(pipe_ctx: PipelineContext) -> None:
    data = "你好世界".encode("GB18030")
    score = compute_structural_score(data, REGISTRY["GB18030"], pipe_ctx)
    assert score > 0.7


def test_big5_scores_high_on_big5_data(pipe_ctx: PipelineContext) -> None:
    data = "你好世界".encode("big5")
    score = compute_structural_score(data, REGISTRY["Big5-HKSCS"], pipe_ctx)
    assert score > 0.7


def test_single_byte_encoding_returns_zero(pipe_ctx: PipelineContext) -> None:
    data = b"Hello world"
    score = compute_structural_score(data, REGISTRY["ISO-8859-1"], pipe_ctx)
    assert score == 0.0


def test_empty_data_returns_zero(pipe_ctx: PipelineContext) -> None:
    score = compute_structural_score(b"", REGISTRY["Shift-JIS-2004"], pipe_ctx)
    assert score == 0.0


def test_big5hkscs_scores_high_on_big5_data(pipe_ctx: PipelineContext) -> None:
    data = "你好世界測試資料".encode("Big5-HKSCS")
    score = compute_structural_score(data, REGISTRY["Big5-HKSCS"], pipe_ctx)
    assert score > 0.7


def test_euc_jis_2004_scores_high_on_euc_jp_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界テスト".encode("EUC-JIS-2004")
    score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    assert score > 0.7


def test_shift_jis_2004_scores_high_on_shift_jis_data(
    pipe_ctx: PipelineContext,
) -> None:
    data = "こんにちは世界テスト".encode("Shift-JIS-2004")
    score = compute_structural_score(data, REGISTRY["Shift-JIS-2004"], pipe_ctx)
    assert score > 0.7


def test_euc_jp_ss2_invalid_trail(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS2 (0x8E) with invalid trail byte should not count as valid."""
    data = b"\x8e\x20"
    score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    assert score == 0.0


def test_euc_jp_ss3_valid(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS3 (0x8F) with valid 3-byte JIS X 0212 sequence."""
    data = b"\x8f\xa1\xa1" * 5
    score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    assert score > 0.0


def test_euc_jp_ss3_invalid_trail(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS3 (0x8F) with invalid trail bytes should not count as valid."""
    data = b"\x8f\xa1\x20"
    score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    assert score == 0.0


def test_multibyte_byte_coverage_all_ascii(pipe_ctx: PipelineContext) -> None:
    """All-ASCII data should return 0.0 coverage for a multibyte encoding."""
    data = b"Hello world plain ASCII"
    coverage = compute_multibyte_byte_coverage(
        data, REGISTRY["Shift-JIS-2004"], pipe_ctx, non_ascii_count=0
    )
    assert coverage == 0.0


def test_lead_byte_diversity_empty_data(pipe_ctx: PipelineContext) -> None:
    """Empty data should return 0 diversity."""
    diversity = compute_lead_byte_diversity(b"", REGISTRY["Shift-JIS-2004"], pipe_ctx)
    assert diversity == 0


def test_coverage_no_analyzer_returns_zero(pipe_ctx: PipelineContext) -> None:
    """An escape-protocol multibyte encoding with no analyzer returns 0.0."""
    coverage = compute_multibyte_byte_coverage(
        b"\x80\x81\x82", REGISTRY["HZ-GB-2312"], pipe_ctx, non_ascii_count=3
    )
    assert coverage == 0.0


def test_diversity_no_analyzer_returns_256(pipe_ctx: PipelineContext) -> None:
    """An escape-protocol multibyte encoding with no analyzer returns 256."""
    diversity = compute_lead_byte_diversity(
        b"\x80\x81", REGISTRY["HZ-GB-2312"], pipe_ctx
    )
    assert diversity == 256


def test_coverage_single_byte_encoding_returns_zero(pipe_ctx: PipelineContext) -> None:
    """A single-byte encoding should return 0.0 coverage."""
    coverage = compute_multibyte_byte_coverage(
        b"\xc0\xc1\xc2", REGISTRY["ISO-8859-1"], pipe_ctx, non_ascii_count=3
    )
    assert coverage == 0.0


def test_euc_jp_ss2_valid_sequence(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS2 (0x8E) with valid trail byte (0xA1-0xDF) should score > 0."""
    # SS2 sequences: 0x8E followed by a byte in 0xA1-0xDF (half-width katakana)
    data = b"\x8e\xa1\x8e\xb0\x8e\xdf" * 3
    score = compute_structural_score(data, REGISTRY["EUC-JIS-2004"], pipe_ctx)
    assert score == 1.0  # all lead bytes have valid trails


def test_euc_jp_ss2_coverage(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS2 valid sequences should contribute to multibyte byte coverage."""
    data = b"\x8e\xa1\x8e\xb0\x8e\xdf"
    coverage = compute_multibyte_byte_coverage(
        data, REGISTRY["EUC-JIS-2004"], pipe_ctx, non_ascii_count=6
    )
    # 6 bytes total, all are non-ASCII or SS2 pairs: mb_bytes = 6 (2 per pair * 3)
    # non_ascii bytes: 0x8e, 0xa1, 0x8e, 0xb0, 0x8e, 0xdf = 6
    assert coverage == 1.0


def test_johab_lead_byte_invalid_trail(pipe_ctx: PipelineContext) -> None:
    """Johab lead byte with an invalid trail byte should fall through (i += 1)."""
    # Lead byte 0x84 (valid Johab lead) followed by 0x20 (not in 0x31-0x7E or 0x91-0xFE)
    # This should hit the fallthrough path at line 276
    data = b"\x84\x20\x84\x0f\x84\x7f"
    score = compute_structural_score(data, REGISTRY["Johab"], pipe_ctx)
    assert score == 0.0  # all trails are invalid


def test_johab_lead_byte_at_end_of_data(pipe_ctx: PipelineContext) -> None:
    """Johab lead byte at the very end of data should fall through."""
    # Lead byte 0x84 with no trail byte available
    data = b"\x84"
    score = compute_structural_score(data, REGISTRY["Johab"], pipe_ctx)
    assert score == 0.0
