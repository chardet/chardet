# tests/test_accuracy.py
"""Accuracy evaluation against the chardet test suite.

Each test function is independently parametrized with its own xfail set.
Run with ``pytest -n auto`` for parallel execution.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from utils import collect_test_files, get_data_dir, normalize_language

import chardet
from chardet.detector import UniversalDetector
from chardet.enums import EncodingEra
from chardet.evaluation import (
    is_correct,
    is_equivalent_detection,
    is_language_equivalent,
)
from chardet.registry import REGISTRY, lookup_encoding

# ---------------------------------------------------------------------------
# Known accuracy failures — marked xfail so they don't block CI but are
# tracked for future improvement.  Kept sorted for easy diffing.
# ---------------------------------------------------------------------------

_KNOWN_FAILURES: frozenset[str] = frozenset(
    {
        "cp437-en/culturax_00001.txt",
        "cp500-es/culturax_mC4_87070.txt",
        "cp850-en/culturax_00001.txt",
        "cp850-fi/culturax_00001.txt",
        "cp850-ms/culturax_00000.txt",
        "cp858-en/culturax_00000.txt",
        "cp858-ms/culturax_00000.txt",
        "iso-8859-15-en/culturax_00002.txt",
    }
)

# Known failures when testing with era-filtered detection.
# Some overlap with _KNOWN_FAILURES (hard files that fail either way),
# some are unique (disambiguation is harder with fewer candidates),
# and many _KNOWN_FAILURES are absent (era filtering actually helps).
_KNOWN_ERA_FILTERED_FAILURES: frozenset[str] = frozenset(
    {
        "cp500-es/culturax_mC4_87070.txt",
        "cp850-fi/culturax_00001.txt",
        # Contains no u-double-acute bytes at all, so nothing in it can
        # separate iso8859-2 from iso8859-16 the way Hungarian normally
        # does.  Its only distinguishing bytes are five stray 0xA9/0xAB/
        # 0xBB, which read as capital S-caron, T-caron, and t-caron under
        # iso8859-2 but as copyright and guillemet punctuation under
        # iso8859-16, and Windows-1250 takes the file on the surrounding
        # prose regardless.
        "iso-8859-2-hu/torokorszag.blogspot.com.xml",
        # One 0xDD is the pair's whole distinguishing evidence, and the
        # rescore reads it under mac-turkish's Turkish model (a very
        # common dotless i) rather than mac-roman's Danish one — the pair
        # models disjoint languages, so the language restriction falls
        # back to comparing every variant.  The category vote does get it
        # right, but at (margin 4, 1 demotion event) it clears neither
        # half of the decisive-override gate, which needs margin 8 and 2
        # events.  Loosening either threshold to reach this file would
        # re-enable single-byte overrides across every in-band pair,
        # which is exactly what those constants exist to prevent.
        "macroman-da/culturax_mC4_83469.txt",
    }
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encoding_era(name: str | None) -> EncodingEra:
    """Look up the encoding era for a test-data encoding name."""
    if name is None:
        return EncodingEra.ALL
    canonical = lookup_encoding(name)
    if canonical is not None:
        return REGISTRY[canonical].era
    return EncodingEra.ALL


def _make_params(
    known_failures: frozenset[str],
) -> list[pytest.param]:
    """Build parametrize params from test data, marking known failures as xfail."""
    data_dir = get_data_dir()
    test_files = collect_test_files(data_dir)
    params = []
    for enc, lang, fp in test_files:
        test_id = f"{enc}-{lang}/{fp.name}"
        marks = []
        if test_id in known_failures:
            marks.append(pytest.mark.xfail(reason="known accuracy gap"))
        params.append(pytest.param(enc, lang, fp, marks=marks, id=test_id))
    return params


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expected_encoding", "language", "test_file_path"),
    _make_params(_KNOWN_FAILURES),
)
def test_detect(
    expected_encoding: str | None, language: str | None, test_file_path: Path
) -> None:
    """Detect encoding of a single test file and verify correctness."""
    data = test_file_path.read_bytes()
    result = chardet.detect(data, encoding_era=EncodingEra.ALL, prefer_superset=True)
    detected = result["encoding"]

    # Binary files: expect encoding=None
    if expected_encoding is None:
        assert detected is None, (
            f"expected binary (None), got={detected} "
            f"(confidence={result['confidence']:.2f}, file={test_file_path.name})"
        )
        return

    assert is_correct(expected_encoding, detected) or is_equivalent_detection(
        data, expected_encoding, detected
    ), (
        f"expected={expected_encoding}, got={detected} "
        f"(confidence={result['confidence']:.2f}, "
        f"language={language}, file={test_file_path.name})"
    )

    # Language accuracy: warn but don't fail
    detected_language = normalize_language(result["language"])
    expected_language = language.lower()
    if detected_language is None or not is_language_equivalent(
        expected_language, detected_language
    ):
        warnings.warn(
            f"Language mismatch: expected={expected_language}, got={detected_language} "
            f"(encoding={expected_encoding}, file={test_file_path.name})",
            stacklevel=1,
        )


@pytest.mark.parametrize(
    ("expected_encoding", "language", "test_file_path"),
    _make_params(_KNOWN_ERA_FILTERED_FAILURES),
)
def test_detect_era_filtered(
    expected_encoding: str | None, language: str | None, test_file_path: Path
) -> None:
    """Detect encoding using only the expected encoding's own era."""
    era = _encoding_era(expected_encoding)
    data = test_file_path.read_bytes()
    result = chardet.detect(data, encoding_era=era, prefer_superset=True)
    detected = result["encoding"]

    # Binary files: expect encoding=None
    if expected_encoding is None:
        assert detected is None, (
            f"expected binary (None), got={detected} "
            f"(era={era!r}, confidence={result['confidence']:.2f}, "
            f"file={test_file_path.name})"
        )
        return

    assert is_correct(expected_encoding, detected) or is_equivalent_detection(
        data, expected_encoding, detected
    ), (
        f"expected={expected_encoding}, got={detected} "
        f"(era={era!r}, confidence={result['confidence']:.2f}, "
        f"language={language}, file={test_file_path.name})"
    )


@pytest.mark.parametrize(
    ("expected_encoding", "language", "test_file_path"),
    _make_params(frozenset()),
)
def test_detect_streaming_parity(
    expected_encoding: str | None, language: str | None, test_file_path: Path
) -> None:
    """UniversalDetector.feed/close must match chardet.detect (GH-296)."""
    data = test_file_path.read_bytes()
    direct = chardet.detect(data, encoding_era=EncodingEra.ALL)

    detector = UniversalDetector()
    detector.feed(data)
    streaming = detector.close()

    assert direct == streaming, (
        f"detect() != UniversalDetector for {test_file_path.name}: "
        f"detect={direct}, streaming={streaming}"
    )
