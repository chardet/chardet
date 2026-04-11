# tests/test_registry.py
from __future__ import annotations

import codecs
from types import MappingProxyType
from typing import get_args

import pytest

from chardet.enums import EncodingEra
from chardet.registry import (
    REGISTRY,
    EncodingInfo,
    EncodingName,
    get_candidates,
    lookup_encoding,
)


def test_encoding_info_is_frozen():
    info = REGISTRY["ascii"]
    assert isinstance(info, EncodingInfo)
    with pytest.raises(AttributeError):
        info.name = "something"  # type: ignore[misc]


def test_registry_is_mapping_proxy():
    assert isinstance(REGISTRY, MappingProxyType)


def test_registry_has_entries():
    assert len(REGISTRY) > 50


def test_registry_utf8_is_modern_web():
    assert EncodingEra.MODERN_WEB in REGISTRY["utf-8"].era


def test_registry_iso_8859_1_is_legacy_iso():
    assert EncodingEra.LEGACY_ISO in REGISTRY["iso8859-1"].era


def test_registry_cp037_is_mainframe():
    cp1140 = REGISTRY["cp1140"]
    assert EncodingEra.MAINFRAME in cp1140.era
    assert "cp037" in cp1140.aliases


def test_registry_macroman_is_legacy_mac():
    assert EncodingEra.LEGACY_MAC in REGISTRY["mac-roman"].era


def test_registry_cp437_is_dos():
    assert EncodingEra.DOS in REGISTRY["cp437"].era


def test_registry_kz1048_is_legacy_regional():
    assert EncodingEra.LEGACY_REGIONAL in REGISTRY["kz1048"].era


def test_get_candidates_filters_by_era():
    modern = get_candidates(EncodingEra.MODERN_WEB)
    for enc in modern:
        assert EncodingEra.MODERN_WEB in enc.era


def test_get_candidates_all_returns_everything():
    all_candidates = get_candidates(EncodingEra.ALL)
    assert len(all_candidates) == len(REGISTRY)


def test_get_candidates_combined_eras():
    combined = get_candidates(EncodingEra.MODERN_WEB | EncodingEra.LEGACY_ISO)
    names = {e.name for e in combined}
    assert "utf-8" in names
    assert "iso8859-1" in names


def test_multibyte_encodings_flagged():
    assert REGISTRY["shift_jis_2004"].is_multibyte is True
    assert REGISTRY["iso8859-1"].is_multibyte is False


def test_registry_cp273_is_mainframe():
    cp273 = REGISTRY["cp273"]
    assert EncodingEra.MAINFRAME in cp273.era
    assert cp273.is_multibyte is False
    assert cp273.name == "cp273"


def test_registry_hp_roman8_is_legacy_regional():
    hp = REGISTRY["hp-roman8"]
    assert EncodingEra.LEGACY_REGIONAL in hp.era
    assert hp.is_multibyte is False
    assert hp.name == "hp-roman8"


def test_name_is_valid_codec():
    for enc in REGISTRY.values():
        codec_info = codecs.lookup(enc.name)
        assert codec_info is not None, f"Invalid codec: {enc.name}"


def test_aliases_are_unique_across_entries():
    """No alias (or canonical name) may be claimed by two different entries.

    A collision would make ``lookup_encoding(alias)`` silently return the
    first entry in iteration order, leaving the second entry's intended
    routing dead.  Self-aliasing (an entry listing its own canonical name
    in its ``aliases`` tuple) is allowed and ignored.
    """
    claims: dict[str, set[str]] = {}
    for entry in REGISTRY.values():
        # Canonical names should be unique by definition (dict key) but
        # must also not collide with any other entry's alias.
        claims.setdefault(entry.name.lower(), set()).add(entry.name)
        for alias in entry.aliases:
            lowered = alias.lower()
            # Self-aliasing is redundant but not a collision.
            if lowered == entry.name.lower():
                continue
            claims.setdefault(lowered, set()).add(entry.name)

    collisions = {name: sorted(cs) for name, cs in claims.items() if len(cs) > 1}
    assert not collisions, (
        "Alias collisions: the same name is claimed by multiple registry "
        "entries, which would cause lookup_encoding() to silently route one "
        "of them the wrong way.\n"
        + "\n".join(
            f"  {name!r}: claimed by {owners}"
            for name, owners in sorted(collisions.items())
        )
    )


def test_languages_field_exists():
    """Every EncodingInfo has a languages tuple."""
    for enc in REGISTRY.values():
        assert isinstance(enc.languages, tuple), f"{enc.name} missing languages"
        for lang in enc.languages:
            assert isinstance(lang, str), f"{enc.name} has non-str language: {lang}"
            assert len(lang) == 2, f"{enc.name} has non-ISO-639-1 language: {lang}"


def test_single_language_encodings():
    """Spot-check single-language encodings."""
    assert REGISTRY["shift_jis_2004"].languages == ("ja",)
    assert REGISTRY["euc_kr"].languages == ("ko",)
    assert REGISTRY["gb18030"].languages == ("zh",)
    assert REGISTRY["cp273"].languages == ("de",)
    assert REGISTRY["koi8-r"].languages == ("ru",)


def test_multi_language_encodings():
    """Spot-check multi-language encodings."""
    assert "en" in REGISTRY["cp1252"].languages
    assert "fr" in REGISTRY["cp1252"].languages
    assert "ru" in REGISTRY["cp1251"].languages
    assert "bg" in REGISTRY["cp1251"].languages


def test_language_agnostic_encodings():
    """Unicode and ASCII encodings have empty languages tuple."""
    assert REGISTRY["ascii"].languages == ()
    assert REGISTRY["utf-8"].languages == ()
    assert REGISTRY["utf-7"].languages == ()
    assert REGISTRY["utf-16"].languages == ()


def test_utf7_in_registry():
    """utf-7 is in the registry as LEGACY_REGIONAL (disabled by browsers since ~2020)."""
    assert "utf-7" in REGISTRY
    assert EncodingEra.LEGACY_REGIONAL in REGISTRY["utf-7"].era
    assert EncodingEra.MODERN_WEB not in REGISTRY["utf-7"].era


# === Task 1: big5 -> big5hkscs ===


def test_big5_family_uses_broadest_superset():
    """big5hkscs is the primary name; big5 is an alias."""
    entry = REGISTRY["big5hkscs"]
    assert entry.name == "big5hkscs"
    assert "big5" in entry.aliases
    assert "big5-tw" in entry.aliases
    assert "csbig5" in entry.aliases
    assert "cp950" in entry.aliases
    assert entry.is_multibyte is True
    assert entry.languages == ("zh",)


# === Task 2: gb18030 gets gb2312/gbk aliases ===


def test_gb18030_has_subset_aliases():
    """gb18030 includes gb2312 and gbk as aliases."""
    entry = REGISTRY["gb18030"]
    assert "gb2312" in entry.aliases
    assert "gbk" in entry.aliases
    assert "gb-18030" in entry.aliases


# === Task 3: euc-jp -> euc-jis-2004 ===


def test_euc_jp_family_uses_broadest_superset():
    """euc-jis-2004 is the primary name; euc-jp is an alias."""
    entry = REGISTRY["euc_jis_2004"]
    assert entry.name == "euc_jis_2004"
    assert "euc-jp" in entry.aliases
    assert "eucjp" in entry.aliases
    assert "ujis" in entry.aliases
    assert "u-jis" in entry.aliases
    assert "euc-jisx0213" in entry.aliases
    assert entry.is_multibyte is True
    assert entry.languages == ("ja",)


# === Task 4: shift_jis -> shift_jis_2004 ===


def test_shift_jis_family_uses_broadest_superset():
    """shift_jis_2004 is the primary name; shift_jis is an alias."""
    entry = REGISTRY["shift_jis_2004"]
    assert entry.name == "shift_jis_2004"
    assert "shift_jis" in entry.aliases
    assert "sjis" in entry.aliases
    assert "shiftjis" in entry.aliases
    assert "s_jis" in entry.aliases
    assert "shift-jisx0213" in entry.aliases
    assert entry.is_multibyte is True
    assert entry.languages == ("ja",)


# === Task 5: iso-2022-jp split into 3 branches ===


def test_iso2022_jp_split_into_branches():
    """iso-2022-jp is split into jp-2, jp-2004, and jp-ext."""
    # iso-2022-jp should NOT be a primary name
    assert "iso-2022-jp" not in REGISTRY

    # iso2022-jp-2 is the multinational branch and gets the old alias
    jp2 = REGISTRY["iso2022_jp_2"]
    assert "iso-2022-jp" in jp2.aliases
    assert "csiso2022jp" in jp2.aliases
    assert "iso2022-jp-1" in jp2.aliases
    assert jp2.name == "iso2022_jp_2"
    assert jp2.is_multibyte is True
    assert jp2.languages == ("ja",)

    # iso2022-jp-2004 is the modern Japanese branch
    jp2004 = REGISTRY["iso2022_jp_2004"]
    assert "iso2022-jp-3" in jp2004.aliases
    assert jp2004.name == "iso2022_jp_2004"
    assert jp2004.is_multibyte is True
    assert jp2004.languages == ("ja",)

    # iso2022-jp-ext is the katakana branch
    jpext = REGISTRY["iso2022_jp_ext"]
    assert jpext.aliases == ("ISO-2022-JP-EXT",)
    assert jpext.name == "iso2022_jp_ext"
    assert jpext.is_multibyte is True
    assert jpext.languages == ("ja",)


# === Task 6a: cp037 -> cp1140 ===


def test_cp037_flipped_to_cp1140():
    """cp1140 is the primary name; cp037 is an alias (cp1140 = cp037 + euro sign)."""
    assert "cp1140" in REGISTRY
    entry = REGISTRY["cp1140"]
    assert "cp037" in entry.aliases
    assert entry.name == "cp1140"
    assert EncodingEra.MAINFRAME in entry.era
    # cp500 should still be its own entry (different EBCDIC variant)
    assert "cp500" in REGISTRY
    assert REGISTRY["cp500"].name == "cp500"


# === Task 6b: tis-620 gets iso-8859-11 alias ===


def test_tis620_has_iso8859_11_alias():
    """tis-620 includes iso-8859-11 as an alias."""
    entry = REGISTRY["tis-620"]
    assert "iso-8859-11" in entry.aliases
    assert "tis620" in entry.aliases


def test_encoding_name_literal_matches_registry():
    """Every registry key must be a valid EncodingName literal value."""
    literal_values = set(get_args(EncodingName))
    registry_keys = set(REGISTRY.keys())
    assert literal_values == registry_keys, (
        f"Mismatch: in Literal not in REGISTRY: {literal_values - registry_keys}, "
        f"in REGISTRY not in Literal: {registry_keys - literal_values}"
    )


def test_lookup_encoding_canonical():
    """lookup_encoding returns the canonical name for known encodings."""
    assert lookup_encoding("windows-1252") == "cp1252"
    assert lookup_encoding("WINDOWS-1252") == "cp1252"
    assert lookup_encoding("Windows-1252") == "cp1252"


def test_lookup_encoding_alias():
    """lookup_encoding resolves aliases to canonical names."""
    assert lookup_encoding("us-ascii") == "ascii"
    assert lookup_encoding("utf8") == "utf-8"
    assert lookup_encoding("big5") == "big5hkscs"
    assert lookup_encoding("gb2312") == "gb18030"


def test_lookup_encoding_by_name():
    """lookup_encoding resolves encoding names to canonical names."""
    assert lookup_encoding("cp1252") == "cp1252"


def test_lookup_encoding_unknown():
    """lookup_encoding returns None for unknown encodings."""
    assert lookup_encoding("not-a-real-encoding") is None


def test_lookup_encoding_uppercase_preserved():
    """Encodings use Python codec canonical names."""
    assert lookup_encoding("ASCII") == "ascii"
    assert lookup_encoding("UTF-8") == "utf-8"
    assert lookup_encoding("UTF-7") == "utf-7"


def test_lookup_encoding_codecs_fallback():
    """lookup_encoding falls back to codecs.lookup for Python-specific aliases."""
    # "latin_1" (with underscore) is not in our alias/name cache but Python's
    # codecs module knows it and maps it to "iso8859-1", which is in the cache.
    assert lookup_encoding("latin_1") == "iso8859-1"


def test_lookup_encoding_unknown_codec():
    """lookup_encoding returns None for unknown names."""
    assert lookup_encoding("no_such_codec_xyz") is None


def test_lookup_encoding_python_only_codec():
    """Names Python knows but chardet doesn't resolve to None.

    chardet intentionally doesn't claim every Python stdlib codec:
    ``mbcs``, ``idna``, ``punycode``, ``rot_13``, and the various
    text-transform codecs (``base64_codec``, ``hex_codec``, ...) are all
    valid Python codecs but are outside chardet's detection scope.
    ``lookup_encoding`` should return None for them rather than returning
    a bogus canonical.
    """
    for python_only in ("mbcs", "idna", "punycode", "rot_13"):
        assert lookup_encoding(python_only) is None, (
            f"{python_only!r} should return None (Python codec not in chardet registry)"
        )
