# Canonical Encoding Names Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **Implementation note:** During implementation, the naming convention was
> refined beyond this plan. All encoding names now use consistent uppercase
> display casing with no lowercase exceptions (`"ASCII"`, `"UTF-7"`, `"UTF-8"`
> instead of the originally planned lowercase). Compound names use hyphens
> as separators (`"Big5-HKSCS"`, `"Shift-JIS-2004"`, `"Mac-Roman"` instead of
> `"Big5HKSCS"`, `"Shift_JIS_2004"`, `"MacRoman"`). See the updated design
> document for the final convention.

**Goal:** Replace chardet's two-name system (lowercase internal + display-cased external) with a single canonical display-cased representation used everywhere, fixing issue #337 (inconsistent encoding name casing).

**Architecture:** Define an `EncodingName` Literal type in `registry.py` with all 86 canonical display-cased names. Change every `EncodingInfo.name` to display casing. Add `lookup_encoding()` to convert arbitrary input to canonical names. Update all pipeline stages, equivalence mappings, model keys, and tests to use canonical names.

**Tech Stack:** Python 3.10+, `typing.Literal`, `codecs.lookup()`, pytest

---

## Display Casing Reference

These are the canonical display-cased names for all 86 encodings. Names that stay lowercase: `ascii`, `utf-7`, `utf-8`. All others get display casing.

| Current lowercase | Canonical display-cased |
|---|---|
| `ascii` | `ascii` |
| `utf-8` | `utf-8` |
| `utf-8-sig` | `UTF-8-SIG` |
| `utf-16` | `UTF-16` |
| `utf-16-be` | `UTF-16-BE` |
| `utf-16-le` | `UTF-16-LE` |
| `utf-32` | `UTF-32` |
| `utf-32-be` | `UTF-32-BE` |
| `utf-32-le` | `UTF-32-LE` |
| `utf-7` | `utf-7` |
| `big5hkscs` | `Big5HKSCS` |
| `cp932` | `CP932` |
| `cp949` | `CP949` |
| `euc-jis-2004` | `EUC-JIS-2004` |
| `euc-kr` | `EUC-KR` |
| `gb18030` | `GB18030` |
| `hz-gb-2312` | `HZ-GB-2312` |
| `iso2022-jp-2` | `ISO-2022-JP-2` |
| `iso2022-jp-2004` | `ISO-2022-JP-2004` |
| `iso2022-jp-ext` | `ISO-2022-JP-EXT` |
| `iso-2022-kr` | `ISO-2022-KR` |
| `shift_jis_2004` | `Shift_JIS_2004` |
| `cp874` | `CP874` |
| `windows-1250` | `Windows-1250` |
| `windows-1251` | `Windows-1251` |
| `windows-1252` | `Windows-1252` |
| `windows-1253` | `Windows-1253` |
| `windows-1254` | `Windows-1254` |
| `windows-1255` | `Windows-1255` |
| `windows-1256` | `Windows-1256` |
| `windows-1257` | `Windows-1257` |
| `windows-1258` | `Windows-1258` |
| `koi8-r` | `KOI8-R` |
| `koi8-u` | `KOI8-U` |
| `tis-620` | `TIS-620` |
| `iso-8859-1` | `ISO-8859-1` |
| `iso-8859-2` | `ISO-8859-2` |
| `iso-8859-3` | `ISO-8859-3` |
| `iso-8859-4` | `ISO-8859-4` |
| `iso-8859-5` | `ISO-8859-5` |
| `iso-8859-6` | `ISO-8859-6` |
| `iso-8859-7` | `ISO-8859-7` |
| `iso-8859-8` | `ISO-8859-8` |
| `iso-8859-9` | `ISO-8859-9` |
| `iso-8859-10` | `ISO-8859-10` |
| `iso-8859-13` | `ISO-8859-13` |
| `iso-8859-14` | `ISO-8859-14` |
| `iso-8859-15` | `ISO-8859-15` |
| `iso-8859-16` | `ISO-8859-16` |
| `johab` | `Johab` |
| `mac-cyrillic` | `MacCyrillic` |
| `mac-greek` | `MacGreek` |
| `mac-iceland` | `MacIceland` |
| `mac-latin2` | `MacLatin2` |
| `mac-roman` | `MacRoman` |
| `mac-turkish` | `MacTurkish` |
| `cp720` | `CP720` |
| `cp1006` | `CP1006` |
| `cp1125` | `CP1125` |
| `koi8-t` | `KOI8-T` |
| `kz-1048` | `KZ-1048` |
| `ptcp154` | `PTCP154` |
| `hp-roman8` | `HP-Roman8` |
| `cp437` | `CP437` |
| `cp737` | `CP737` |
| `cp775` | `CP775` |
| `cp850` | `CP850` |
| `cp852` | `CP852` |
| `cp855` | `CP855` |
| `cp856` | `CP856` |
| `cp857` | `CP857` |
| `cp858` | `CP858` |
| `cp860` | `CP860` |
| `cp861` | `CP861` |
| `cp862` | `CP862` |
| `cp863` | `CP863` |
| `cp864` | `CP864` |
| `cp865` | `CP865` |
| `cp866` | `CP866` |
| `cp869` | `CP869` |
| `cp1140` | `CP1140` |
| `cp424` | `CP424` |
| `cp500` | `CP500` |
| `cp875` | `CP875` |
| `cp1026` | `CP1026` |
| `cp273` | `CP273` |

---

### Task 1: Add `EncodingName` Literal and `lookup_encoding()` to registry.py

**Files:**
- Modify: `src/chardet/registry.py`
- Test: `tests/test_registry.py`

**Step 1: Write failing tests for `EncodingName` and `lookup_encoding()`**

Add to `tests/test_registry.py`:

```python
from chardet.registry import lookup_encoding


def test_encoding_name_literal_matches_registry():
    """Every registry key must be a valid EncodingName literal value."""
    from typing import get_args
    from chardet.registry import EncodingName
    literal_values = set(get_args(EncodingName))
    registry_keys = set(REGISTRY.keys())
    assert literal_values == registry_keys, (
        f"Mismatch: in Literal not in REGISTRY: {literal_values - registry_keys}, "
        f"in REGISTRY not in Literal: {registry_keys - literal_values}"
    )


def test_lookup_encoding_canonical():
    """lookup_encoding returns the canonical name for known encodings."""
    assert lookup_encoding("windows-1252") == "Windows-1252"
    assert lookup_encoding("WINDOWS-1252") == "Windows-1252"
    assert lookup_encoding("Windows-1252") == "Windows-1252"


def test_lookup_encoding_alias():
    """lookup_encoding resolves aliases to canonical names."""
    assert lookup_encoding("us-ascii") == "ascii"
    assert lookup_encoding("utf8") == "utf-8"
    assert lookup_encoding("big5") == "Big5HKSCS"
    assert lookup_encoding("gb2312") == "GB18030"


def test_lookup_encoding_python_codec():
    """lookup_encoding resolves Python codec names to canonical names."""
    assert lookup_encoding("cp1252") == "Windows-1252"


def test_lookup_encoding_unknown():
    """lookup_encoding returns None for unknown encodings."""
    assert lookup_encoding("not-a-real-encoding") is None


def test_lookup_encoding_lowercase_preserved():
    """Encodings that stay lowercase keep their casing."""
    assert lookup_encoding("ASCII") == "ascii"
    assert lookup_encoding("UTF-8") == "utf-8"
    assert lookup_encoding("UTF-7") == "utf-7"
```

**Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_registry.py::test_encoding_name_literal_matches_registry tests/test_registry.py::test_lookup_encoding_canonical tests/test_registry.py::test_lookup_encoding_alias tests/test_registry.py::test_lookup_encoding_python_codec tests/test_registry.py::test_lookup_encoding_unknown tests/test_registry.py::test_lookup_encoding_lowercase_preserved -v`
Expected: FAIL (ImportError for `EncodingName` and `lookup_encoding`)

**Step 3: Implement `EncodingName` Literal and `lookup_encoding()`**

At the top of `src/chardet/registry.py`, after imports, add:

```python
import codecs
from typing import Literal

EncodingName = Literal[
    "ascii",
    "utf-8",
    "UTF-8-SIG",
    "UTF-16",
    "UTF-16-BE",
    "UTF-16-LE",
    "UTF-32",
    "UTF-32-BE",
    "UTF-32-LE",
    "utf-7",
    "Big5HKSCS",
    "CP932",
    "CP949",
    "EUC-JIS-2004",
    "EUC-KR",
    "GB18030",
    "HZ-GB-2312",
    "ISO-2022-JP-2",
    "ISO-2022-JP-2004",
    "ISO-2022-JP-EXT",
    "ISO-2022-KR",
    "Shift_JIS_2004",
    "CP874",
    "Windows-1250",
    "Windows-1251",
    "Windows-1252",
    "Windows-1253",
    "Windows-1254",
    "Windows-1255",
    "Windows-1256",
    "Windows-1257",
    "Windows-1258",
    "KOI8-R",
    "KOI8-U",
    "TIS-620",
    "ISO-8859-1",
    "ISO-8859-2",
    "ISO-8859-3",
    "ISO-8859-4",
    "ISO-8859-5",
    "ISO-8859-6",
    "ISO-8859-7",
    "ISO-8859-8",
    "ISO-8859-9",
    "ISO-8859-10",
    "ISO-8859-13",
    "ISO-8859-14",
    "ISO-8859-15",
    "ISO-8859-16",
    "Johab",
    "MacCyrillic",
    "MacGreek",
    "MacIceland",
    "MacLatin2",
    "MacRoman",
    "MacTurkish",
    "CP720",
    "CP1006",
    "CP1125",
    "KOI8-T",
    "KZ-1048",
    "PTCP154",
    "HP-Roman8",
    "CP437",
    "CP737",
    "CP775",
    "CP850",
    "CP852",
    "CP855",
    "CP856",
    "CP857",
    "CP858",
    "CP860",
    "CP861",
    "CP862",
    "CP863",
    "CP864",
    "CP865",
    "CP866",
    "CP869",
    "CP1140",
    "CP424",
    "CP500",
    "CP875",
    "CP1026",
    "CP273",
]
```

Then add the `lookup_encoding()` function (after the `REGISTRY` definition):

```python
_LOOKUP_CACHE: dict[str, EncodingName] | None = None
_LOOKUP_CACHE_LOCK = threading.Lock()


def _build_lookup_cache() -> dict[str, EncodingName]:
    """Build a case-insensitive lookup table from all known encoding names."""
    cache: dict[str, EncodingName] = {}
    # 1. Registry primary names (case-insensitive)
    for entry in REGISTRY.values():
        cache[entry.name.lower()] = entry.name  # type: ignore[assignment]
    # 2. Registry aliases (case-insensitive)
    for entry in REGISTRY.values():
        for alias in entry.aliases:
            cache.setdefault(alias.lower(), entry.name)  # type: ignore[assignment]
    # 3. Python codec canonical names → registry entry
    codec_to_name: dict[str, EncodingName] = {}
    for entry in REGISTRY.values():
        try:
            codec_name = codecs.lookup(entry.python_codec).name
            codec_to_name.setdefault(codec_name, entry.name)  # type: ignore[assignment]
        except LookupError:
            pass
    cache.update({k: v for k, v in codec_to_name.items() if k not in cache})
    return cache


def lookup_encoding(name: str) -> EncodingName | None:
    """Convert an encoding name string to the canonical EncodingName.

    Handles arbitrary casing, aliases, and Python codec names.

    :param name: Any encoding name string.
    :returns: The canonical :data:`EncodingName`, or ``None`` if unknown.
    """
    global _LOOKUP_CACHE  # noqa: PLW0603
    if _LOOKUP_CACHE is None:
        with _LOOKUP_CACHE_LOCK:
            if _LOOKUP_CACHE is None:
                _LOOKUP_CACHE = _build_lookup_cache()
    # Direct case-insensitive match
    result = _LOOKUP_CACHE.get(name.lower())
    if result is not None:
        return result
    # Try via codecs.lookup() for codec aliases we didn't pre-map
    try:
        codec_name = codecs.lookup(name).name
        return _LOOKUP_CACHE.get(codec_name)
    except LookupError:
        return None
```

**Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_registry.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/chardet/registry.py tests/test_registry.py
git commit -m "feat: add EncodingName Literal and lookup_encoding() function"
```

---

### Task 2: Change all 86 registry `name` values to display casing

**Files:**
- Modify: `src/chardet/registry.py` (lines 74-775, all `name=` values)

**Step 1: Update all `name=` values in `_REGISTRY_ENTRIES`**

Change each `name=` to the display-cased canonical value per the reference table above. For example:
- `name="ascii"` stays `name="ascii"`
- `name="utf-8"` stays `name="utf-8"`
- `name="utf-8-sig"` → `name="UTF-8-SIG"`
- `name="utf-16"` → `name="UTF-16"`
- `name="utf-16-be"` → `name="UTF-16-BE"`
- `name="utf-16-le"` → `name="UTF-16-LE"`
- `name="utf-32"` → `name="UTF-32"`
- `name="utf-32-be"` → `name="UTF-32-BE"`
- `name="utf-32-le"` → `name="UTF-32-LE"`
- `name="utf-7"` stays `name="utf-7"`
- `name="big5hkscs"` → `name="Big5HKSCS"`
- `name="cp932"` → `name="CP932"`
- `name="cp949"` → `name="CP949"`
- `name="euc-jis-2004"` → `name="EUC-JIS-2004"`
- `name="euc-kr"` → `name="EUC-KR"`
- `name="gb18030"` → `name="GB18030"`
- `name="hz-gb-2312"` → `name="HZ-GB-2312"`
- `name="iso2022-jp-2"` → `name="ISO-2022-JP-2"`
- `name="iso2022-jp-2004"` → `name="ISO-2022-JP-2004"`
- `name="iso2022-jp-ext"` → `name="ISO-2022-JP-EXT"`
- `name="iso-2022-kr"` → `name="ISO-2022-KR"`
- `name="shift_jis_2004"` → `name="Shift_JIS_2004"`
- `name="cp874"` → `name="CP874"`
- `name="windows-1250"` → `name="Windows-1250"` through `name="windows-1258"` → `name="Windows-1258"`
- `name="koi8-r"` → `name="KOI8-R"`, `name="koi8-u"` → `name="KOI8-U"`
- `name="tis-620"` → `name="TIS-620"`
- `name="iso-8859-1"` through `name="iso-8859-16"` → `name="ISO-8859-1"` through `name="ISO-8859-16"`
- `name="johab"` → `name="Johab"`
- `name="mac-cyrillic"` → `name="MacCyrillic"`, etc.
- `name="cp720"` → `name="CP720"`, etc.
- `name="koi8-t"` → `name="KOI8-T"`
- `name="kz-1048"` → `name="KZ-1048"`
- `name="ptcp154"` → `name="PTCP154"`
- `name="hp-roman8"` → `name="HP-Roman8"`
- All remaining `cp*` entries → `CP*`

**Step 2: Update test_registry.py assertions for display-cased keys**

All tests that do `REGISTRY["lowercase-name"]` must change to `REGISTRY["Display-Name"]`. Examples:

```python
# test_encoding_info_is_frozen: REGISTRY["ascii"] stays (ascii is lowercase)
# test_registry_utf8_is_modern_web: REGISTRY["utf-8"] stays
# test_registry_iso_8859_1_is_legacy_iso: REGISTRY["iso-8859-1"] → REGISTRY["ISO-8859-1"]
# test_registry_cp037_is_mainframe: REGISTRY["cp1140"] → REGISTRY["CP1140"], "cp037" alias stays
# test_registry_macroman_is_legacy_mac: REGISTRY["mac-roman"] → REGISTRY["MacRoman"]
# test_registry_cp437_is_dos: REGISTRY["cp437"] → REGISTRY["CP437"]
# test_registry_kz1048_is_legacy_regional: REGISTRY["kz-1048"] → REGISTRY["KZ-1048"]
# test_get_candidates_combined_eras: "utf-8" stays, "iso-8859-1" → "ISO-8859-1"
# test_multibyte_encodings_flagged: REGISTRY["shift_jis_2004"] → REGISTRY["Shift_JIS_2004"],
#                                    REGISTRY["iso-8859-1"] → REGISTRY["ISO-8859-1"]
# test_registry_cp273_is_mainframe: REGISTRY["cp273"] → REGISTRY["CP273"]
# test_registry_hp_roman8_is_legacy_regional: REGISTRY["hp-roman8"] → REGISTRY["HP-Roman8"]
# test_single_language_encodings: all need display casing
# test_multi_language_encodings: all need display casing
# test_language_agnostic_encodings: "ascii" and "utf-8" stay, "utf-7" stays,
#                                    "utf-16" → "UTF-16"
# test_utf7_in_registry: REGISTRY["utf-7"] stays (utf-7 is lowercase)
# test_big5_family_uses_broadest_superset: REGISTRY["big5hkscs"] → REGISTRY["Big5HKSCS"]
# test_gb18030_has_subset_aliases: REGISTRY["gb18030"] → REGISTRY["GB18030"]
# test_euc_jp_family_uses_broadest_superset: REGISTRY["euc-jis-2004"] → REGISTRY["EUC-JIS-2004"]
# test_shift_jis_family_uses_broadest_superset: REGISTRY["shift_jis_2004"] → REGISTRY["Shift_JIS_2004"]
# test_iso2022_jp_split_into_branches: "iso-2022-jp" not in REGISTRY stays,
#                                       REGISTRY["iso2022-jp-2"] → REGISTRY["ISO-2022-JP-2"], etc.
# test_cp037_flipped_to_cp1140: REGISTRY["cp1140"] → REGISTRY["CP1140"],
#                                REGISTRY["cp500"] → REGISTRY["CP500"]
# test_tis620_has_iso8859_11_alias: REGISTRY["tis-620"] → REGISTRY["TIS-620"]
```

**Step 3: Run tests to verify**

Run: `uv run python -m pytest tests/test_registry.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add src/chardet/registry.py tests/test_registry.py
git commit -m "feat: change all registry names to display-cased canonical values"
```

---

### Task 3: Update pipeline stages to use display-cased names

**Files:**
- Modify: `src/chardet/pipeline/bom.py` (lines 10-15)
- Modify: `src/chardet/pipeline/escape.py` (lines 213, 220, 226, 234, 243, 253)
- Modify: `src/chardet/pipeline/ascii.py` (line 23)
- Modify: `src/chardet/pipeline/utf8.py` (line 97)
- Modify: `src/chardet/pipeline/utf1632.py` (lines 93, 110, 153, 155, 162, 164, 188)
- Modify: `src/chardet/pipeline/markup.py` (replace `_normalize_encoding` with `lookup_encoding`)
- Modify: `src/chardet/pipeline/structural.py` (lines 287-296)
- Test: multiple test files

**Step 1: Update `bom.py`**

Change `_BOMS` encoding names:
```python
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\x00\x00\xfe\xff", "UTF-32-BE"),
    (b"\xff\xfe\x00\x00", "UTF-32-LE"),
    (b"\xef\xbb\xbf", "UTF-8-SIG"),
    (b"\xfe\xff", "UTF-16-BE"),
    (b"\xff\xfe", "UTF-16-LE"),
)
```

**Step 2: Update `escape.py`**

Change all `encoding=` string literals:
- `"iso2022-jp-2004"` → `"ISO-2022-JP-2004"`
- `"iso2022-jp-ext"` → `"ISO-2022-JP-EXT"`
- `"iso2022-jp-2"` → `"ISO-2022-JP-2"`
- `"iso-2022-kr"` → `"ISO-2022-KR"`
- `"hz-gb-2312"` → `"HZ-GB-2312"`
- `"utf-7"` stays `"utf-7"` (lowercase canonical)

**Step 3: Update `ascii.py`**

`encoding="ascii"` stays (lowercase canonical).

**Step 4: Update `utf8.py`**

`encoding="utf-8"` stays (lowercase canonical).

**Step 5: Update `utf1632.py`**

Change all encoding string literals:
- `"utf-32-be"` → `"UTF-32-BE"`
- `"utf-32-le"` → `"UTF-32-LE"`
- `"utf-16-le"` → `"UTF-16-LE"`
- `"utf-16-be"` → `"UTF-16-BE"`

**Step 6: Update `markup.py`**

Replace `_normalize_encoding` with `lookup_encoding`:

```python
"""Stage 1b: HTML/XML charset declaration extraction."""

from __future__ import annotations

import re

from chardet.pipeline import DETERMINISTIC_CONFIDENCE, DetectionResult
from chardet.registry import lookup_encoding

_SCAN_LIMIT = 4096

_XML_ENCODING_RE = re.compile(
    rb"""<\?xml[^>]+encoding\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE
)
_HTML5_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset\s*=\s*['"]?\s*([^\s'">;]+)""", re.IGNORECASE
)
_HTML4_CONTENT_TYPE_RE = re.compile(
    rb"""<meta[^>]+content\s*=\s*['"][^'"]*charset=([^\s'">;]+)""", re.IGNORECASE
)


def detect_markup_charset(data: bytes) -> DetectionResult | None:
    """Scan the first bytes of *data* for an HTML/XML charset declaration.

    Checks for:

    1. ``<?xml ... encoding="..."?>``
    2. ``<meta charset="...">``
    3. ``<meta http-equiv="Content-Type" content="...; charset=...">``

    :param data: The raw byte data to scan.
    :returns: A :class:`DetectionResult` with confidence 0.95, or ``None``.
    """
    if not data:
        return None

    head = data[:_SCAN_LIMIT]

    for pattern in (_XML_ENCODING_RE, _HTML5_CHARSET_RE, _HTML4_CONTENT_TYPE_RE):
        match = pattern.search(head)
        if match:
            try:
                raw_name = match.group(1).decode("ascii").strip()
            except (UnicodeDecodeError, ValueError):
                continue
            encoding = lookup_encoding(raw_name)
            if encoding is not None and _validate_bytes(data, encoding):
                return DetectionResult(
                    encoding=encoding,
                    confidence=DETERMINISTIC_CONFIDENCE,
                    language=None,
                )

    return None


def _validate_bytes(data: bytes, encoding: str) -> bool:
    """Check that *data* can be decoded under *encoding* without errors."""
    try:
        data[:_SCAN_LIMIT].decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return False
    return True
```

**Step 7: Update `structural.py`**

Change `_ANALYZERS` keys:
```python
_ANALYZERS: dict[str, Callable[[bytes], tuple[float, int, int]]] = {
    "Shift_JIS_2004": _analyze_shift_jis,
    "CP932": _analyze_shift_jis,
    "EUC-JIS-2004": _analyze_euc_jp,
    "EUC-KR": _analyze_euc_kr,
    "CP949": _analyze_euc_kr,
    "GB18030": _analyze_gb18030,
    "Big5HKSCS": _analyze_big5,
    "Johab": _analyze_johab,
}
```

**Step 8: Update test files for pipeline stages**

Update all test assertions to use display-cased names:

- `tests/test_bom.py`: `"utf-8-sig"` → `"UTF-8-SIG"`, `"utf-16-le"` → `"UTF-16-LE"`, `"utf-16-be"` → `"UTF-16-BE"`, `"utf-32-le"` → `"UTF-32-LE"`, `"utf-32-be"` → `"UTF-32-BE"`
- `tests/test_escape.py`: `"iso2022-jp-2"` → `"ISO-2022-JP-2"`, `"iso-2022-kr"` → `"ISO-2022-KR"`, `"hz-gb-2312"` → `"HZ-GB-2312"`, `"utf-7"` stays, `"iso2022-jp-2004"` → `"ISO-2022-JP-2004"`, `"iso2022-jp-ext"` → `"ISO-2022-JP-EXT"`
- `tests/test_markup.py`: `"iso-8859-1"` → `"ISO-8859-1"`, `"windows-1252"` → `"Windows-1252"`, `"shift_jis"` → canonical name via lookup (this will become `"Shift_JIS_2004"` since shift_jis is an alias)
- `tests/test_utf1632.py`: `"utf-16-le"` → `"UTF-16-LE"`, `"utf-16-be"` → `"UTF-16-BE"`, `"utf-32-le"` → `"UTF-32-LE"`, `"utf-32-be"` → `"UTF-32-BE"`
- `tests/test_api.py`: `"utf-8-sig"` → `"UTF-8-SIG"`, `"iso-8859-7"` → `"ISO-8859-7"`, `"hz-gb-2312"` → `"HZ-GB-2312"`, `"iso-2022-kr"` → `"ISO-2022-KR"`, `"hp-roman8"` → `"HP-Roman8"`, `result["encoding"].startswith("cp")` → `result["encoding"].startswith("CP")`
- `tests/test_orchestrator.py`: `"utf-8-sig"` → `"UTF-8-SIG"`, `"utf-16-le"` → `"UTF-16-LE"`, `"utf-16-be"` → `"UTF-16-BE"`, `"utf-32-le"` → `"UTF-32-LE"`, `"utf-32-be"` → `"UTF-32-BE"`
- `tests/test_detector.py`: `"utf-8-sig"` → `"UTF-8-SIG"`
- `tests/test_github_issues.py`: `"utf-8-sig"` → `"UTF-8-SIG"`, `"utf-16-le"` → `"UTF-16-LE"`, `"iso-8859-7"` → `"ISO-8859-7"`
- `tests/test_structural.py`: `"hz-gb-2312"` → `"HZ-GB-2312"`
- `tests/test_cjk_gating.py`: `"hz-gb-2312"` → `"HZ-GB-2312"`, `"iso-2022-kr"` → `"ISO-2022-KR"`
- `tests/test_koi8t.py`: `"koi8-t"` → `"KOI8-T"`

**Step 9: Run all tests**

Run: `uv run python -m pytest tests/ -x -v --ignore=tests/test_accuracy.py`
Expected: ALL PASS

**Step 10: Commit**

```bash
git add src/chardet/pipeline/ tests/
git commit -m "feat: update all pipeline stages to use display-cased encoding names"
```

---

### Task 4: Update orchestrator.py to use display-cased names

**Files:**
- Modify: `src/chardet/pipeline/orchestrator.py`

**Step 1: Update all encoding name string literals in orchestrator.py**

Change:
- Line 41: `encoding="utf-8"` stays (lowercase canonical)
- Line 45: `encoding="windows-1252"` → `encoding="Windows-1252"`
- Lines 56-62: `_COMMON_LATIN_ENCODINGS` values: `"iso-8859-1"` → `"ISO-8859-1"`, `"iso-8859-15"` → `"ISO-8859-15"`, `"windows-1252"` → `"Windows-1252"`
- Line 174: `"iso-8859-10"` → `"ISO-8859-10"`
- Line 175: `"iso-8859-14"` → `"ISO-8859-14"`
- Line 176: `"windows-1254"` → `"Windows-1254"`
- Line 373: `"koi8-r"` → `"KOI8-R"`
- Line 378: `"koi8-t"` → `"KOI8-T"`
- Line 405: `"utf-8"` stays
- Line 437: `"utf-8"` stays
- Line 440: `"utf-8"` stays

**Step 2: Run tests**

Run: `uv run python -m pytest tests/ -x -v --ignore=tests/test_accuracy.py`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add src/chardet/pipeline/orchestrator.py
git commit -m "feat: update orchestrator to use display-cased encoding names"
```

---

### Task 5: Update equivalences.py to use display-cased names

**Files:**
- Modify: `src/chardet/equivalences.py`
- Test: `tests/test_equivalences.py`

**Step 1: Update `SUPERSETS` keys and values**

Change all keys and values to display-cased:
```python
SUPERSETS: dict[str, frozenset[str]] = {
    "ascii": frozenset({"utf-8", "Windows-1252"}),
    "TIS-620": frozenset({"ISO-8859-11", "CP874"}),
    "ISO-8859-11": frozenset({"CP874"}),
    "GB2312": frozenset({"GB18030"}),
    "GBK": frozenset({"GB18030"}),
    "Big5": frozenset({"Big5HKSCS", "CP950"}),
    "Shift_JIS": frozenset({"CP932", "Shift_JIS_2004"}),
    "Shift-JISX0213": frozenset({"Shift_JIS_2004"}),
    "EUC-JP": frozenset({"EUC-JIS-2004"}),
    "EUC-JISX0213": frozenset({"EUC-JIS-2004"}),
    "EUC-KR": frozenset({"CP949"}),
    "CP037": frozenset({"CP1140"}),
    "ISO-2022-JP": frozenset({"ISO-2022-JP-2", "ISO-2022-JP-2004", "ISO-2022-JP-EXT"}),
    "ISO2022-JP-1": frozenset({"ISO-2022-JP-2", "ISO-2022-JP-EXT"}),
    "ISO2022-JP-3": frozenset({"ISO-2022-JP-2004"}),
    "ISO-8859-1": frozenset({"Windows-1252"}),
    "ISO-8859-2": frozenset({"Windows-1250"}),
    "ISO-8859-5": frozenset({"Windows-1251"}),
    "ISO-8859-6": frozenset({"Windows-1256"}),
    "ISO-8859-7": frozenset({"Windows-1253"}),
    "ISO-8859-8": frozenset({"Windows-1255"}),
    "ISO-8859-9": frozenset({"Windows-1254"}),
    "ISO-8859-13": frozenset({"Windows-1257"}),
}
```

Note: SUPERSETS keys include subset names that are NOT primary registry entries (e.g., `"GB2312"`, `"Big5"`, `"Shift_JIS"`, `"ISO-2022-JP"`, `"CP037"`). These are test-suite expected values, not detection outputs. Use display casing for consistency but they don't need to be `EncodingName` members.

**Step 2: Update `PREFERRED_SUPERSET` keys to display-cased**

```python
PREFERRED_SUPERSET: dict[str, str] = {
    "ascii": "Windows-1252",
    "EUC-KR": "CP949",
    "ISO-8859-1": "Windows-1252",
    "ISO-8859-2": "Windows-1250",
    "ISO-8859-5": "Windows-1251",
    "ISO-8859-6": "Windows-1256",
    "ISO-8859-7": "Windows-1253",
    "ISO-8859-8": "Windows-1255",
    "ISO-8859-9": "Windows-1254",
    "ISO-8859-11": "CP874",
    "ISO-8859-13": "Windows-1257",
    "TIS-620": "CP874",
}
```

**Step 3: Update `apply_legacy_rename()` to use case-insensitive key lookup**

```python
def apply_legacy_rename(result: DetectionDict) -> DetectionDict:
    enc = result.get("encoding")
    if isinstance(enc, str):
        result["encoding"] = PREFERRED_SUPERSET.get(enc, enc)
    return result
```

Note: Since encoding names are now canonical display-cased, the `.lower()` call is no longer needed — keys already match the detection output casing.

**Step 4: Update `BIDIRECTIONAL_GROUPS`**

```python
BIDIRECTIONAL_GROUPS: tuple[tuple[str, ...], ...] = (
    ("UTF-16", "UTF-16-LE", "UTF-16-BE"),
    ("UTF-32", "UTF-32-LE", "UTF-32-BE"),
    ("ISO-2022-JP-2", "ISO-2022-JP-2004", "ISO-2022-JP-EXT"),
)
```

**Step 5: Run tests**

Run: `uv run python -m pytest tests/test_equivalences.py tests/test_api.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/chardet/equivalences.py
git commit -m "feat: update equivalences to use display-cased encoding names"
```

---

### Task 6: Update detector.py and confusion tests

**Files:**
- Modify: `src/chardet/detector.py` (if needed — check PREFERRED_SUPERSET usage)
- Modify: `tests/test_confusion.py` (encoding name assertions)

**Step 1: Update test_confusion.py assertions**

```python
# test_resolve_confusion_groups_preserves_all_results:
#   "cp1140" → "CP1140", "cp500" → "CP500", "windows-1252" → "Windows-1252"
# test_load_confusion_data: "cp1140" → "CP1140", "cp500" → "CP500"
```

Note: `confusion.bin` stores encoding names from model training. After retraining (Task 8), the names in the binary will be display-cased. Until then, these test assertions may need to check for lowercase names from the existing binary. **Update these tests after retraining.**

**Step 2: Run tests**

Run: `uv run python -m pytest tests/test_confusion.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_confusion.py
git commit -m "test: update confusion test assertions for display-cased names"
```

---

### Task 7: Retrain models with display-cased names

**Files:**
- Modify: `scripts/train.py` (no changes needed — it reads `enc.name` from registry, which is now display-cased)
- Output: `src/chardet/models/models.bin` (new model keys like `French/Windows-1252`)
- Output: `src/chardet/models/confusion.bin` (updated confusion group data)

**Step 1: Verify train.py reads from registry**

`scripts/train.py` line 48-49 builds `ENCODING_LANG_MAP` from `enc.name`. Since registry names are now display-cased, model keys will automatically be display-cased. No code changes needed.

**Step 2: Retrain models**

Run: `uv run python scripts/train.py`

**Step 3: Retrain confusion data (if separate script)**

Check if confusion training is separate:
Run: `ls scripts/confusion_training.py` — if it exists, run it too.

**Step 4: Run full test suite**

Run: `uv run python -m pytest tests/ -x -v --ignore=tests/test_accuracy.py`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/chardet/models/models.bin src/chardet/models/confusion.bin scripts/
git commit -m "feat: retrain models with display-cased encoding name keys"
```

---

### Task 8: Update remaining test files and run full suite

**Files:**
- Modify: any remaining test files with encoding name mismatches

**Step 1: Run the full test suite including accuracy tests**

Run: `uv run python -m pytest tests/ -x -v`

**Step 2: Fix any remaining assertion failures**

Update any test assertions that still use lowercase encoding names. Common patterns to check:

- `result["encoding"] == "koi8-t"` → `result["encoding"] == "KOI8-T"`
- `result["encoding"] == "koi8-r"` → `result["encoding"] == "KOI8-R"`
- Any `result["encoding"]` comparisons in test files

**Step 3: Verify `is_correct()` still works for accuracy tests**

`equivalences.is_correct()` uses `normalize_encoding_name()` which calls `codecs.lookup()` — this is casing-independent, so accuracy tests should work unchanged.

**Step 4: Run full suite one more time**

Run: `uv run python -m pytest tests/ -x -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tests/
git commit -m "test: update all test assertions for display-cased encoding names"
```

---

### Task 9: Clean up — remove unused code and verify

**Files:**
- Modify: `src/chardet/pipeline/markup.py` (verify `_normalize_encoding` is removed — done in Task 3)
- Modify: `src/chardet/pipeline/__init__.py` (optionally change `DetectionResult.encoding` type annotation to `EncodingName | None`)

**Step 1: Optionally update DetectionResult type annotation**

In `src/chardet/pipeline/__init__.py`, change:
```python
encoding: str | None
```
to:
```python
encoding: EncodingName | None
```

Add import: `from chardet.registry import EncodingName`

Note: `DetectionDict.encoding` stays `str | None` since it's the public API TypedDict.

**Step 2: Run linting**

Run: `uv run ruff check .`
Run: `uv run ruff format .`

**Step 3: Run full test suite**

Run: `uv run python -m pytest tests/ -x -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add src/chardet/ tests/
git commit -m "refactor: final cleanup for canonical encoding names"
```

---

### Task 10: Drop stashed WIP and verify clean state

**Step 1: Drop the stashed intermediate work**

```bash
git stash list
git stash drop  # drop the stash from the old two-name approach
```

**Step 2: Final verification**

Run: `uv run python -m pytest tests/ -v`
Run: `uv run ruff check .`

**Step 3: Verify issue #337 is fixed**

Write a test script to `/tmp/test_337.py`:
```python
import chardet

# Plain ASCII — goes through statistical path
r1 = chardet.detect(b"Hello world")
print(f"ASCII text: {r1['encoding']}")

# XML with charset declaration — goes through markup path
r2 = chardet.detect(b'<?xml version="1.0" encoding="windows-1252"?><root>text</root>')
print(f"XML markup: {r2['encoding']}")

# Both should return "Windows-1252"
assert r1["encoding"] == r2["encoding"] == "Windows-1252", (
    f"Mismatch! ASCII={r1['encoding']}, XML={r2['encoding']}"
)
print("Issue #337 FIXED: both paths return consistent casing")
```

Run: `uv run python /tmp/test_337.py`
Expected: `Issue #337 FIXED: both paths return consistent casing`
