# tests/test_utf8_equivalence.py
"""Differential tests: the decode-based detect_utf8 vs the old validator.

The rewrite (ADR-0006) claims exact equivalence — same verdicts, same
confidences — on every input.  These tests hold it to that against the
verbatim copy of the old implementation in ``utf8_oracle.py``.
"""

from __future__ import annotations

import random

import pytest

from chardet.pipeline.utf8 import _CHUNK_SIZE, detect_utf8

from .utf8_oracle import oracle_detect_utf8

# Byte snippets that probe every branch of the old validator: valid sequences
# of each length, boundary leads, overlong/surrogate/out-of-range prefixes,
# invalid start bytes, bare continuations, and truncated tails.
SNIPPETS = [
    b"",
    b"a",
    b"hello world",
    b"\x00",
    b"\x7f",
    # Valid 2/3/4-byte sequences, including range boundaries
    b"\xc2\x80",
    b"\xdf\xbf",
    b"\xe0\xa0\x80",
    b"\xe0\xbf\xbf",
    b"\xed\x80\x80",
    b"\xed\x9f\xbf",
    b"\xef\xbf\xbf",
    b"\xf0\x90\x80\x80",
    b"\xf4\x8f\xbf\xbf",
    "héllo".encode(),
    "你好".encode(),
    "🌍".encode(),
    # Invalid start bytes
    b"\x80",
    b"\xbf",
    b"\xc0\xaf",
    b"\xc1\x80",
    b"\xf5\x80\x80\x80",
    b"\xff",
    b"\xfe",
    # Overlong / surrogate / out-of-range second bytes
    b"\xe0\x80\x80",
    b"\xe0\x9f\xbf",
    b"\xed\xa0\x80",
    b"\xed\xbf\xbf",
    b"\xf0\x80\x80\x80",
    b"\xf0\x8f\xbf\xbf",
    b"\xf4\x90\x80\x80",
    # Broken continuations
    b"\xc3\x00",
    b"\xc3q",
    b"\xe3\x81\x00",
    b"\xe3\xff\x81",
    b"\xf0\x9f\x92\xff",
    b"\xf0\x9f\xff\x96",
    # Truncated tails (valid prefixes)
    b"\xc3",
    b"\xe3",
    b"\xe3\x81",
    b"\xf0",
    b"\xf0\x9f",
    b"\xf0\x9f\x92",
    # Truncated tails the old validator never examined (garbage inside the
    # overrun) — the rewrite must tolerate these identically
    b"\xe3\xff",
    b"\xf0\xff",
    b"\xf0\xff\xff",
    b"\xed\xbf",
    b"\xe0\x80",
    b"\xf4\x90",
    b"\xf0\x9f\xff",
]


def assert_equivalent(data: bytes) -> None:
    expected = oracle_detect_utf8(data)
    actual = detect_utf8(data)
    if expected is None:
        assert actual is None, data
    else:
        assert actual is not None, data
        assert actual.encoding == expected[0], data
        assert actual.confidence == expected[1], data


@pytest.mark.parametrize("snippet", SNIPPETS)
def test_snippets(snippet: bytes) -> None:
    assert_equivalent(snippet)


@pytest.mark.parametrize("snippet", SNIPPETS)
@pytest.mark.parametrize(
    "prefix",
    [b"", b"x", b"abc ", "valid ütf8 ".encode(), "日本語".encode()],
)
def test_snippet_after_valid_prefix(prefix: bytes, snippet: bytes) -> None:
    """Every snippet again, preceded by valid text.

    Exercises mid-data and end-of-data positions with nonzero counts.
    """
    assert_equivalent(prefix + snippet)


def test_snippet_pairs() -> None:
    """All ordered pairs of snippets.

    Probes sequences straddling snippet joins, garbage after valid tails,
    tails after garbage, etc.
    """
    for a in SNIPPETS:
        for b in SNIPPETS:
            assert_equivalent(a + b)


def test_random_fuzz() -> None:
    """Seeded random buffers across byte distributions."""
    rng = random.Random(0x5EED)  # noqa: S311 - deterministic fuzz, not crypto
    distributions = [
        range(256),  # uniform garbage
        range(0x80),  # pure ASCII
        [*range(0x20, 0x7F), *range(0xC2, 0xF5), *range(0x80, 0xC0)],  # utf8-ish
        [0x41, 0xC3, 0xA9, 0xE3, 0x81, 0x82, 0xF0, 0x9F, 0x92, 0x96, 0xFF],
    ]
    for dist in distributions:
        pool = list(dist)
        for _ in range(500):
            n = rng.randrange(0, 40)
            data = bytes(rng.choice(pool) for _ in range(n))
            assert_equivalent(data)


def test_mutated_valid_text() -> None:
    """Valid UTF-8 text with random single-byte mutations."""
    rng = random.Random(0xD1FF)  # noqa: S311 - deterministic fuzz, not crypto
    base = ("héllo wörld — 日本語のテキスト 🎉 " * 8).encode()
    for _ in range(2000):
        buf = bytearray(base)
        for _ in range(rng.randrange(1, 4)):
            buf[rng.randrange(len(buf))] = rng.randrange(256)
        assert_equivalent(bytes(buf[: rng.randrange(1, len(buf) + 1)]))


def test_every_truncation_of_valid_text() -> None:
    data = "abç 日本語 🎉x".encode()
    for i in range(len(data) + 1):
        assert_equivalent(data[:i])


@pytest.mark.parametrize(
    "tail",
    [b"", b"\xc3", b"\xe3\x81", b"\xf0\x9f\x92", b"\xe3\xff", b"\xf0\xff\xff"],
)
@pytest.mark.parametrize("straddle", [b"", "é".encode(), "🎉".encode()])
def test_chunk_boundary(tail: bytes, straddle: bytes) -> None:
    """Sequences straddling the incremental-decode chunk boundary.

    With and without tolerated tails, at ASCII-fast-path and non-ASCII
    first chunks.
    """
    for lead_in in (b"a", "é".encode()):
        for offset in (-2, -1, 0):
            filler = b"a" * (_CHUNK_SIZE + offset - len(lead_in))
            assert_equivalent(lead_in + filler + straddle + tail)


def test_error_reported_in_chunk_after_lead() -> None:
    """Lead byte at the end of one chunk, invalid continuation in the next.

    The absolute error offset must account for the decoder's pending bytes.
    """
    data = b"a" * (_CHUNK_SIZE - 1) + b"\xe3" + b"\xff" + b"z"
    assert_equivalent(data)
    # And the tolerated variant: overrun starts in chunk 1, garbage in chunk 2.
    data = b"a" * (_CHUNK_SIZE - 1) + b"\xf0" + b"\xff\xff"
    assert_equivalent(data)
