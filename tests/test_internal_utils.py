# tests/test_internal_utils.py
"""Tests for the internal shared utilities in ``chardet._utils``."""

from __future__ import annotations

from chardet._utils import (
    _DECODE_CHUNK_SIZE,
    count_deleted,
    dangling_tail_with_ascii_prefix,
    decodes_completely,
    decodes_without_error,
)


def test_decodes_without_error_unknown_codec_is_false():
    assert decodes_without_error(b"hello", "not-a-codec") is False


def test_decodes_completely_unknown_codec_is_false():
    assert decodes_completely(b"hello", "not-a-codec") is False


def test_dangling_tail_unknown_codec_is_false():
    assert dangling_tail_with_ascii_prefix(b"hello", "not-a-codec") is False


def test_dangling_tail_invalid_bytes_is_false():
    """Genuine corruption before the tail is an error, not a deferred tail."""
    assert dangling_tail_with_ascii_prefix(b"\xff", "utf-8") is False


def test_count_deleted_chunked_matches_whole_pass():
    """Counting through bounded chunks must equal the one-shot count.

    Deletion is per-byte and carries no state across the chunk split, so a
    window larger than the chunk size counts identically.
    """
    data = b"a\x00" * (_DECODE_CHUNK_SIZE // 2 + 17)
    assert len(data) > _DECODE_CHUNK_SIZE
    assert count_deleted(data, b"\x00") == data.count(0)


def test_decodes_without_error_chunked_sequence_straddles_chunk_edge():
    """A multi-byte sequence crossing the chunk boundary decodes cleanly.

    The incremental decoder carries its state across chunks, so the split
    must be invisible even when it lands mid-character.
    """
    data = b"a" * (_DECODE_CHUNK_SIZE - 1) + "é".encode() + b"tail"
    assert len(data) > _DECODE_CHUNK_SIZE
    assert decodes_without_error(data, "utf-8") is True
