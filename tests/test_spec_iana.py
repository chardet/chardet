"""IANA Character Sets registry compliance.

Verifies that chardet recognises the IANA-preferred MIME name and key
aliases for every encoding chardet's registry claims to support.  This
pins interoperability with the IANA / RFC / MIME side of the charset
ecosystem (IANA is the authority cited by HTTP ``Content-Type`` headers,
MIME part declarations, email, etc.).

Direction is **one-way** (IANA → chardet).  The test only covers the
intersection of IANA's registry and chardet's registry — IANA has ~257
registered charsets and chardet intentionally supports only ~86 of them.
Encodings chardet supports that are not in IANA's registry (e.g. the
mac-* variants, KOI8-T, HP-Roman8, the DOS codepages beyond the common
few) are out of scope for this file; they are covered by
``tests/test_spec_decode_roundtrip.py``.
"""

from __future__ import annotations

import codecs

import pytest

from chardet.registry import REGISTRY, lookup_encoding

# Source: https://www.iana.org/assignments/character-sets/character-sets.xhtml
# Snapshot: 2026-04-10
# Last upstream change: 2024-06-06.
# Refresh = re-fetch the registry and update the rows below.
#
# Each row is (iana_preferred_name, expected_chardet_canonical, aliases_to_test)
# where aliases_to_test is a tuple of IANA-listed aliases that must also
# resolve to the same chardet canonical.  The csXxx names are IANA's
# "charset name" identifiers and are the primary interop requirement.
IANA_ENTRIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("UTF-8", "utf-8", ("csUTF8",)),
    (
        "US-ASCII",
        "ascii",
        (
            "iso-ir-6",
            "ANSI_X3.4-1968",
            "ANSI_X3.4-1986",
            "ISO_646.irv:1991",
            "ISO646-US",
            "us",
            "IBM367",
            "cp367",
            "csASCII",
        ),
    ),
    ("UTF-16", "utf-16", ("csUTF16",)),
    ("UTF-16BE", "utf-16-be", ("csUTF16BE",)),
    ("UTF-16LE", "utf-16-le", ("csUTF16LE",)),
    ("UTF-32", "utf-32", ("csUTF32",)),
    (
        "ISO-8859-1",
        "iso8859-1",
        (
            "iso-ir-100",
            "ISO_8859-1",
            "latin1",
            "l1",
            "IBM819",
            "CP819",
            "csISOLatin1",
        ),
    ),
    (
        "ISO-8859-2",
        "iso8859-2",
        ("iso-ir-101", "ISO_8859-2", "latin2", "l2", "csISOLatin2"),
    ),
    (
        "ISO-8859-3",
        "iso8859-3",
        ("iso-ir-109", "ISO_8859-3", "latin3", "l3", "csISOLatin3"),
    ),
    (
        "ISO-8859-4",
        "iso8859-4",
        ("iso-ir-110", "ISO_8859-4", "latin4", "l4", "csISOLatin4"),
    ),
    (
        "ISO-8859-5",
        "iso8859-5",
        ("iso-ir-144", "ISO_8859-5", "cyrillic", "csISOLatinCyrillic"),
    ),
    (
        "ISO-8859-6",
        "iso8859-6",
        (
            "iso-ir-127",
            "ISO_8859-6",
            "ECMA-114",
            "ASMO-708",
            "arabic",
            "csISOLatinArabic",
        ),
    ),
    (
        "ISO-8859-7",
        "iso8859-7",
        (
            "iso-ir-126",
            "ISO_8859-7",
            "ELOT_928",
            "ECMA-118",
            "greek",
            "greek8",
            "csISOLatinGreek",
        ),
    ),
    (
        "ISO-8859-8",
        "iso8859-8",
        ("iso-ir-138", "ISO_8859-8", "hebrew", "csISOLatinHebrew"),
    ),
    (
        "ISO-8859-9",
        "iso8859-9",
        ("iso-ir-148", "ISO_8859-9", "latin5", "l5", "csISOLatin5"),
    ),
    (
        "ISO-8859-10",
        "iso8859-10",
        ("iso-ir-157", "l6", "csISOLatin6", "latin6"),
    ),
    ("ISO-8859-13", "iso8859-13", ("csISO885913",)),
    (
        "ISO-8859-14",
        "iso8859-14",
        ("iso-ir-199", "latin8", "l8", "csISO885914"),
    ),
    ("ISO-8859-15", "iso8859-15", ("Latin-9", "csISO885915")),
    (
        "ISO-8859-16",
        "iso8859-16",
        ("iso-ir-226", "latin10", "l10", "csISO885916"),
    ),
    ("windows-1250", "cp1250", ("cswindows1250",)),
    ("windows-1251", "cp1251", ("cswindows1251",)),
    ("windows-1252", "cp1252", ("cswindows1252",)),
    ("windows-1253", "cp1253", ("cswindows1253",)),
    ("windows-1254", "cp1254", ("cswindows1254",)),
    ("windows-1255", "cp1255", ("cswindows1255",)),
    ("windows-1256", "cp1256", ("cswindows1256",)),
    ("windows-1257", "cp1257", ("cswindows1257",)),
    ("windows-1258", "cp1258", ("cswindows1258",)),
    ("KOI8-R", "koi8-r", ("csKOI8R",)),
    ("KOI8-U", "koi8-u", ("csKOI8U",)),
    ("IBM866", "cp866", ("cp866", "866", "csIBM866")),
    # Big5 and Big5-HKSCS both collapse into chardet's big5hkscs superset
    ("Big5", "big5hkscs", ("csBig5",)),
    ("Big5-HKSCS", "big5hkscs", ("csBig5HKSCS",)),
    ("GB18030", "gb18030", ("csGB18030",)),
    # GBK is an IANA charset in its own right; chardet collapses it into
    # gb18030 because gb18030 is a strict superset.
    ("GBK", "gb18030", ("CP936", "MS936", "windows-936", "csGBK")),
    # Shift_JIS and EUC-JP collapse into the 2004 revisions in chardet.
    ("Shift_JIS", "shift_jis_2004", ("MS_Kanji", "csShiftJIS")),
    ("EUC-JP", "euc_jis_2004", ("csEUCPkdFmtJapanese",)),
    ("EUC-KR", "euc_kr", ("csEUCKR",)),
    ("macintosh", "mac-roman", ("mac", "csMacintosh")),
    ("TIS-620", "tis-620", ("csTIS620", "ISO-8859-11")),
    ("IBM437", "cp437", ("cp437", "437", "csPC8CodePage437")),
    ("IBM850", "cp850", ("cp850", "850", "csPC850Multilingual")),
    ("IBM855", "cp855", ("cp855", "855", "csIBM855")),
    # IBM862 is not in chardet's registry (it's cp862 in Python codecs,
    # which chardet does not currently expose) — skipped.
    ("IBM1026", "cp1026", ("CP1026", "csIBM1026")),
    # IANA calls cp1140 "IBM01140" (with a leading zero); chardet uses the
    # no-zero form to match Python's codec name.
    ("IBM01140", "cp1140", ("CP01140", "csIBM01140")),
    # UTF variants not covered above
    ("UTF-7", "utf-7", ("UNICODE-1-1-UTF-7", "csUTF7")),
    ("UTF-32BE", "utf-32-be", ("csUTF32BE",)),
    ("UTF-32LE", "utf-32-le", ("csUTF32LE",)),
    # High-value CJK encodings
    ("windows-31J", "cp932", ("csWindows31J",)),
    ("HZ-GB-2312", "hz", ()),
    ("ISO-2022-JP-2", "iso2022_jp_2", ("csISO2022JP2",)),
    ("ISO-2022-KR", "iso2022_kr", ("csISO2022KR",)),
    # Regional
    ("hp-roman8", "hp-roman8", ("roman8", "r8", "csHPRoman8")),
)


def test_iana_entries_reference_real_canonicals() -> None:
    """Every chardet canonical listed in ``IANA_ENTRIES`` must exist.

    Guards against silent drift if a registry canonical is ever renamed
    without updating this table -- the parametrised tests would otherwise
    fail with a misleading resolution message instead of pointing at the
    stale reference.
    """
    unknown: list[tuple[str, str]] = []
    for iana_name, expected_chardet, _ in IANA_ENTRIES:
        if expected_chardet not in REGISTRY:
            unknown.append((iana_name, expected_chardet))
    assert not unknown, (
        "IANA_ENTRIES references canonicals not in chardet.registry:\n"
        + "\n".join(f"  {iana!r} -> {canon!r}" for iana, canon in unknown)
    )


@pytest.mark.parametrize(
    ("iana_name", "expected_chardet", "_aliases"),
    IANA_ENTRIES,
    ids=[row[0] for row in IANA_ENTRIES],
)
def test_iana_preferred_name_resolves(
    iana_name: str, expected_chardet: str, _aliases: tuple[str, ...]
) -> None:
    """The IANA-preferred MIME name must resolve to the expected chardet canonical."""
    resolved = lookup_encoding(iana_name)
    assert resolved == expected_chardet, (
        f"IANA {iana_name!r} resolved to {resolved!r}, expected {expected_chardet!r}"
    )
    # And the resolved canonical must be a valid Python codec.
    codecs.lookup(resolved)


_ALIAS_PARAMS: list[tuple[str, str, str]] = [
    (iana_name, expected_chardet, alias)
    for iana_name, expected_chardet, aliases in IANA_ENTRIES
    for alias in aliases
]


@pytest.mark.parametrize(
    ("iana_name", "expected_chardet", "alias"),
    _ALIAS_PARAMS,
    ids=[f"{iana}:{alias}" for iana, _, alias in _ALIAS_PARAMS],
)
def test_iana_alias_resolves(iana_name: str, expected_chardet: str, alias: str) -> None:
    """Every IANA-listed alias must resolve to the same chardet canonical.

    Chardet is allowed to have extra aliases IANA does not list
    (e.g. Python stdlib names like ``latin_1``, WHATWG labels like
    ``x-cp1252``) — those are tested in ``tests/test_spec_whatwg.py`` and
    ``tests/test_spec_decode_roundtrip.py``.  Here we only assert the
    reverse direction: every IANA alias must land on the expected canonical.
    """
    resolved = lookup_encoding(alias)
    assert resolved == expected_chardet, (
        f"IANA alias {alias!r} (listed under {iana_name!r}) resolved to "
        f"{resolved!r}, expected {expected_chardet!r}"
    )
