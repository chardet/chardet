# tests/test_output_names.py
from __future__ import annotations

import codecs

import pytest

from chardet.output_names import (
    _COMPAT_NAMES,
    NARROWER_DISPLAY_NAMES,
    PREFERRED_SUPERSET,
    apply_compat_names,
    apply_legacy_rename,
    apply_preferred_superset,
    decodes_under_public_name,
    display_codec,
)
from chardet.registry import REGISTRY, lookup_encoding


def test_apply_preferred_superset_ascii():
    d = {"encoding": "ascii", "confidence": 1.0, "language": None}
    apply_preferred_superset(d)
    assert d["encoding"] == "cp1252"


def test_apply_preferred_superset_keeps_a_name_the_superset_cannot_decode():
    """0x81 is undefined in cp1252; ISO-8859-1 data holding it keeps its name."""
    result = {"encoding": "iso8859-1", "confidence": 0.9, "language": "fr"}
    assert apply_preferred_superset(result, b"caf\xe9 \x81")["encoding"] == "iso8859-1"
    assert apply_preferred_superset(result, b"caf\xe9")["encoding"] == "cp1252"


def test_apply_preferred_superset_without_data_remaps_unconditionally():
    """No data to check against: the remap is the caller's opt-in, as before."""
    result = {"encoding": "iso8859-1", "confidence": 0.9, "language": "fr"}
    assert apply_preferred_superset(result)["encoding"] == "cp1252"


def test_apply_preferred_superset_no_match():
    d = {"encoding": "utf-8", "confidence": 1.0, "language": None}
    apply_preferred_superset(d)
    assert d["encoding"] == "utf-8"


def test_apply_preferred_superset_none():
    d = {"encoding": None, "confidence": 0.0, "language": None}
    apply_preferred_superset(d)
    assert d["encoding"] is None


def test_apply_legacy_rename_is_alias_of_apply_preferred_superset():
    """``apply_legacy_rename`` is the deprecated alias for the same function."""
    assert apply_legacy_rename is apply_preferred_superset


def test_compat_names_maps_codec_to_display() -> None:
    """_COMPAT_NAMES maps codec names to 5.x/6.x display names."""
    # 5.x compat entries
    assert _COMPAT_NAMES["big5hkscs"] == "Big5"
    assert _COMPAT_NAMES["cp855"] == "IBM855"
    assert _COMPAT_NAMES["euc_jis_2004"] == "EUC-JP"
    assert _COMPAT_NAMES["iso2022_jp_2"] == "ISO-2022-JP"
    assert _COMPAT_NAMES["shift_jis_2004"] == "SHIFT_JIS"
    # Windows codepage entries
    assert _COMPAT_NAMES["cp1252"] == "Windows-1252"
    assert _COMPAT_NAMES["cp1251"] == "Windows-1251"
    # ISO entries
    assert _COMPAT_NAMES["iso8859-1"] == "ISO-8859-1"
    # Codec names that match 5.x output have no entry
    assert "ascii" not in _COMPAT_NAMES
    assert "utf-8" not in _COMPAT_NAMES


def test_compat_names_covers_windows_and_iso_families() -> None:
    """Regression guard for the seven previously missing entries.

    cp1250/1256/1257, cp874 and iso8859-2/6/13 were absent from _COMPAT_NAMES,
    so the default ``compat_names=True`` path leaked their internal codec
    spelling instead of the 5.x/6.x display name.
    """
    assert _COMPAT_NAMES["cp1250"] == "Windows-1250"
    assert _COMPAT_NAMES["cp1256"] == "Windows-1256"
    assert _COMPAT_NAMES["cp1257"] == "Windows-1257"
    assert _COMPAT_NAMES["cp874"] == "CP874"
    assert _COMPAT_NAMES["iso8859-2"] == "ISO-8859-2"
    assert _COMPAT_NAMES["iso8859-6"] == "ISO-8859-6"
    assert _COMPAT_NAMES["iso8859-13"] == "ISO-8859-13"


def test_compat_names_covers_cp932() -> None:
    """Regression guard for the previously missing cp932 entry.

    cp932 was absent from _COMPAT_NAMES, so the default ``compat_names=True``
    path leaked the internal ``cp932`` codec name instead of the 5.x/6.x
    display name ``CP932`` used by its siblings (e.g. shift_jis_2004).
    """
    assert _COMPAT_NAMES["cp932"] == "CP932"


def test_every_preferred_superset_target_has_compat_name() -> None:
    """Every ``prefer_superset`` target must have a ``_COMPAT_NAMES`` entry.

    Otherwise the superset remap leaves a raw codec name on the default path.
    """
    leaked = sorted(
        target for target in PREFERRED_SUPERSET.values() if target not in _COMPAT_NAMES
    )
    assert not leaked, f"prefer_superset targets missing compat names: {leaked}"


def test_narrower_display_names_match_codecs() -> None:
    """The set of narrowing renames is exactly what the codec registry says."""
    narrower = set()
    for internal, display in _COMPAT_NAMES.items():
        try:
            display_codec = codecs.lookup(display).name
        except LookupError:
            continue  # a display name that is not a Python codec cannot narrow
        if display_codec != codecs.lookup(internal).name:
            narrower.add(internal)
    assert narrower == set(NARROWER_DISPLAY_NAMES)


def test_compat_rename_skipped_when_display_codec_cannot_decode() -> None:
    jp = "日本語".encode("euc_jis_2004") + "①".encode("euc_jis_2004")
    result = apply_compat_names({"encoding": "euc_jis_2004"}, jp)
    assert result["encoding"] == "euc_jis_2004"
    jp.decode(result["encoding"])


def test_compat_rename_applied_when_display_codec_decodes() -> None:
    jp = "日本語".encode("euc_jp")
    assert apply_compat_names({"encoding": "euc_jis_2004"}, jp)["encoding"] == "EUC-JP"


def test_compat_rename_unconditional_without_data() -> None:
    assert apply_compat_names({"encoding": "euc_jis_2004"})["encoding"] == "EUC-JP"


def test_compat_rename_ignores_non_narrowing_names() -> None:
    assert (
        apply_compat_names({"encoding": "cp1252"}, b"\x81")["encoding"]
        == "Windows-1252"
    )


def test_preferred_superset_is_the_frozen_selection() -> None:
    """The ``prefer_superset`` selection is public via ``LEGACY_MAP``.

    Adding or dropping a pair changes ``prefer_superset=True`` output, so
    it is pinned here (ADR-0007).
    """
    assert PREFERRED_SUPERSET == {
        "ascii": "cp1252",
        "euc_kr": "cp949",
        "iso8859-1": "cp1252",
        "iso8859-2": "cp1250",
        "iso8859-5": "cp1251",
        "iso8859-6": "cp1256",
        "iso8859-7": "cp1253",
        "iso8859-8": "cp1255",
        "iso8859-9": "cp1254",
        "iso8859-11": "cp874",
        "iso8859-13": "cp1257",
        "tis-620": "cp874",
    }


@pytest.mark.parametrize(("subset", "superset"), sorted(PREFERRED_SUPERSET.items()))
def test_preferred_superset_agrees_with_registry(subset: str, superset: str) -> None:
    """Every selected pair is a superset fact the registry also states.

    ``iso8859-11`` is an alias, so the key goes through ``lookup_encoding``.
    """
    canonical = lookup_encoding(subset)
    assert canonical is not None
    assert REGISTRY[canonical].superset == superset


def test_display_codec_resolves_the_display_name() -> None:
    assert display_codec("shift_jis_2004") == "shift_jis"
    assert display_codec("euc_jis_2004") == "euc_jp"
    assert display_codec("euc_kr") == "euc_kr"
    assert display_codec("cp1252") == "cp1252"
    assert display_codec("utf-8") == "utf-8"


def test_public_name_check_skips_same_codec_display_names() -> None:
    """``Windows-1252`` is cp1252 under another spelling: no second decode."""
    assert decodes_under_public_name(b"\x81", "cp1252", complete=False)


def test_public_name_check_tolerant_ignores_the_internal_codec() -> None:
    """``complete=False`` trusts validity's tolerant check of the internal name."""
    assert decodes_under_public_name(b"\xff", "ascii", complete=False)


def test_public_name_check_rejects_a_narrower_display_codec() -> None:
    """``EUC-JP`` lacks the JIS X 0213 rows ``euc_jis_2004`` validated."""
    data = b"hello \xa2\xaf"
    assert not decodes_under_public_name(data, "euc_jis_2004", complete=False)
    assert not decodes_under_public_name(data, "euc_jis_2004", complete=True)


def test_public_name_check_complete_is_strict_on_both_names() -> None:
    jp = "日本語".encode("euc_jp")
    assert decodes_under_public_name(jp, "euc_jis_2004", complete=True)
    assert not decodes_under_public_name(jp[:-1], "euc_jis_2004", complete=True)
    assert decodes_under_public_name(jp[:-1], "euc_jis_2004", complete=False)
    assert not decodes_under_public_name(b"\xff", "ascii", complete=True)
