"""Tests for scripts/generate_unicode_scripts.py."""

from __future__ import annotations

import pytest
from generate_unicode_scripts import parse, render

from chardet._unicode_scripts import BMP_SCRIPT_RUNS, SCRIPTS, UNICODE_VERSION

_SAMPLE = """# Scripts-99.0.0.txt
# Date: 2099-01-01

0000..0040    ; Common # Cc  [65] <control>..COMMERCIAL AT
0041..005A    ; Latin # L&  [26] LATIN CAPITAL LETTER A..LATIN CAPITAL LETTER Z
0061          ; Latin # L&       LATIN SMALL LETTER A
4E00..9FFF    ; Han # Lo [20992] CJK UNIFIED IDEOGRAPH-4E00..CJK UNIFIED IDEOGRAPH-9FFF
FFF0..1000F   ; Common # made-up range that crosses out of the BMP
20000..2A6DF  ; Han # Lo [42720] CJK UNIFIED IDEOGRAPH-20000..CJK UNIFIED IDEOGRAPH-2A6DF
"""


def test_parse_reads_the_version_and_the_bmp_ranges() -> None:
    version, scripts = parse(_SAMPLE)
    assert version == "99.0.0"
    assert len(scripts) == 0x10000
    assert scripts[0x40] == "Common"
    assert scripts[0x41] == scripts[0x5A] == scripts[0x61] == "Latin"
    assert scripts[0x5B] == scripts[0x60] == "Unknown"
    assert scripts[0x4E00] == scripts[0x9FFF] == "Han"
    assert scripts[0xFFEF] == "Unknown"
    assert scripts[0xFFFF] == "Common"


def test_parse_rejects_another_file() -> None:
    with pytest.raises(ValueError, match="not a Scripts.txt file"):
        parse("0041..005A ; Latin\n")


def test_render_writes_a_module_that_round_trips() -> None:
    version, scripts = parse(_SAMPLE)
    namespace: dict[str, object] = {}
    exec(render(version, scripts), namespace)  # noqa: S102
    assert namespace["UNICODE_VERSION"] == "99.0.0"
    names = namespace["SCRIPTS"]
    assert names == ("Unknown", "Common", "Han", "Latin")
    assert namespace["BMP_SCRIPT_RUNS"] == (
        (0x0000, 1),
        (0x0041, 3),
        (0x005B, 0),
        (0x0061, 3),
        (0x0062, 0),
        (0x4E00, 2),
        (0xA000, 0),
        (0xFFF0, 1),
    )


def test_checked_in_table_is_what_render_writes() -> None:
    """The committed module has not been edited by hand."""
    scripts = ["Unknown"] * 0x10000
    for j, (first, index) in enumerate(BMP_SCRIPT_RUNS):
        end = BMP_SCRIPT_RUNS[j + 1][0] if j + 1 < len(BMP_SCRIPT_RUNS) else 0x10000
        scripts[first:end] = [SCRIPTS[index]] * (end - first)
    namespace: dict[str, object] = {}
    exec(render(UNICODE_VERSION, scripts), namespace)  # noqa: S102
    assert namespace["SCRIPTS"] == SCRIPTS
    assert namespace["BMP_SCRIPT_RUNS"] == BMP_SCRIPT_RUNS
