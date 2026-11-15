# tests/test_unicode_scripts.py
"""Tests for the generated Unicode Script table."""

from __future__ import annotations

import pytest

from chardet._unicode_scripts import BMP_SCRIPT_RUNS, SCRIPTS, UNICODE_VERSION


def _script(code_point: int) -> str:
    name = SCRIPTS[0]
    for first, index in BMP_SCRIPT_RUNS:
        if first > code_point:
            break
        name = SCRIPTS[index]
    return name


def test_runs_cover_the_bmp_in_order() -> None:
    starts = [first for first, _ in BMP_SCRIPT_RUNS]
    assert starts[0] == 0
    assert starts == sorted(set(starts))
    assert starts[-1] < 0x10000


def test_adjacent_runs_differ() -> None:
    indexes = [index for _, index in BMP_SCRIPT_RUNS]
    assert all(a != b for a, b in zip(indexes, indexes[1:], strict=False))
    assert all(0 <= index < len(SCRIPTS) for index in indexes)


def test_script_names_are_unique_and_unknown_is_first() -> None:
    assert SCRIPTS[0] == "Unknown"
    assert len(set(SCRIPTS)) == len(SCRIPTS)
    assert UNICODE_VERSION.count(".") == 2


@pytest.mark.parametrize(
    ("code_point", "script"),
    [
        (0x0041, "Latin"),
        (0x00E9, "Latin"),
        (0xFF21, "Latin"),  # fullwidth A
        (0x0020, "Common"),
        (0x2014, "Common"),  # em dash
        (0x0301, "Inherited"),  # combining acute
        (0x0391, "Greek"),
        (0x0416, "Cyrillic"),
        (0x05D0, "Hebrew"),
        (0x0627, "Arabic"),
        (0x0E01, "Thai"),
        (0x10D4, "Georgian"),
        (0x3042, "Hiragana"),
        (0x30A2, "Katakana"),
        (0x3105, "Bopomofo"),
        (0x4E00, "Han"),
        (0xAC00, "Hangul"),
        (0x20FC, "Unknown"),  # unassigned
        (0xD800, "Unknown"),  # surrogate
        (0xE000, "Unknown"),  # private use
        (0xFDD0, "Unknown"),  # noncharacter
        (0xFFFF, "Unknown"),
    ],
)
def test_known_code_points(code_point: int, script: str) -> None:
    assert _script(code_point) == script
