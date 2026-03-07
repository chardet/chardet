# Canonical Encoding Names Design

**Date:** 2026-03-07
**Issue:** [#337](https://github.com/chardet/chardet/issues/337) — inconsistent encoding name casing

## Problem

chardet returns encoding names with inconsistent casing. Plain ASCII text
detected as `windows-1252` via the statistical path gets renamed to
`Windows-1252` by `PREFERRED_SUPERSET`, while XML with
`charset="windows-1252"` returns lowercase `windows-1252` from the markup
stage. The root cause is two parallel naming systems: lowercase internal
registry names and display-cased names applied only at certain API exit points.

## Design

Replace the two-name system with a single canonical representation used
everywhere. The `EncodingName` Literal type defines the valid set of encoding
names in display casing, and all code paths — registry, pipeline stages,
equivalence mappings, model keys, and public API — use these canonical names.

### `EncodingName` Literal

Defined in `registry.py`. Contains all 86 canonical encoding names in display
casing (e.g., `"Windows-1252"`, `"KOI8-R"`, `"ISO-8859-7"`). Type checkers
flag invalid encoding name strings at check time.

All names use consistent uppercase display casing (e.g., `"ASCII"`, `"UTF-7"`,
`"UTF-8"`). No lowercase exceptions — a single consistent convention is simpler
than maintaining special cases. Compound names use hyphens as separators
(e.g., `"Big5-HKSCS"`, `"Shift-JIS-2004"`, `"Mac-Roman"`).

UTF-16/32 endian variants remain distinct entries (`"UTF-16-LE"`, `"UTF-16-BE"`,
etc.) since chardet 5.x returns endian-specific names for BOM-less detection.
`"UTF-16"` and `"UTF-32"` (without endian suffix) are separate entries used
only for BOM-detected input.

ISO-2022-JP branches remain distinct: `"ISO-2022-JP-2"`,
`"ISO-2022-JP-2004"`, `"ISO-2022-JP-EXT"`.

### Registry changes

- `EncodingInfo.name` uses display-cased values directly (e.g.,
  `name="Windows-1252"`).
- The `display_name` field added during exploration is removed — `name` IS
  the display name.
- `REGISTRY` dict is keyed by these display-cased names.

### `lookup_encoding()` function

New function in `registry.py`:

```python
def lookup_encoding(name: str) -> EncodingName | None:
```

Converts any encoding name string (arbitrary casing, aliases, Python codec
names) to the canonical `EncodingName`. Built lazily from:

1. Registry `name` values (case-insensitive match)
2. Registry `aliases` (case-insensitive match)
3. Python codec canonical names via `codecs.lookup()` → registry entry by
   `python_codec`

This replaces `markup.py`'s `_normalize_encoding()`. The markup stage calls
`lookup_encoding()` to convert charset declarations to canonical names.

### Pipeline stages

All `DetectionResult(encoding=...)` calls use display-cased string literals
matching the `EncodingName` Literal. Type checkers catch typos. Affected
modules:

- `pipeline/bom.py` — `"UTF-32-BE"`, `"UTF-32-LE"`, `"UTF-8-SIG"`,
  `"UTF-16-BE"`, `"UTF-16-LE"`
- `pipeline/escape.py` — `"ISO-2022-JP-2"`, `"ISO-2022-JP-2004"`,
  `"ISO-2022-JP-EXT"`, `"ISO-2022-KR"`, `"HZ-GB-2312"`, `"UTF-7"`
- `pipeline/ascii.py` — `"ASCII"`
- `pipeline/utf8.py` — `"UTF-8"`
- `pipeline/utf1632.py` — `"UTF-16-LE"`, `"UTF-16-BE"`, `"UTF-32-LE"`,
  `"UTF-32-BE"`
- `pipeline/orchestrator.py` — `"UTF-8"`, `"Windows-1252"`, string
  comparisons like `"KOI8-R"`, `"KOI8-T"`

### Equivalence mappings

All encoding name strings in `equivalences.py` switch to display-cased
canonical names:

- `SUPERSETS` keys and values
- `PREFERRED_SUPERSET` keys and values
- `BIDIRECTIONAL_GROUPS` members

`apply_display_names()` is removed — no longer needed since names are
canonical from the start.

### Model retraining

Model keys in `models.bin` use `"lang/encoding"` format where the encoding
part comes from `registry.name`. After the registry name change, retraining
via `scripts/train.py` produces display-cased model keys (e.g.,
`"French/Windows-1252"` instead of `"French/windows-1252"`). The
`get_enc_index()` alias resolution in `models/__init__.py` continues to work
unchanged.

### `DetectionResult.encoding` type

Changed from `str | None` to `EncodingName | None`. The `DetectionDict`
TypedDict's `encoding` field stays `str | None` since it's the public API
type and display names are already strings.

### Tests

All test assertions comparing encoding names update to display-cased values.
A validation test ensures the `EncodingName` Literal stays in sync with the
registry keys. The accuracy test suite's `equivalences.is_correct()` continues
to work via `normalize_encoding_name()` which uses `codecs.lookup()` for
comparison (casing-independent).

## Migration summary

| Component | Before | After |
|-----------|--------|-------|
| Registry `name` | `"windows-1252"` | `"Windows-1252"` |
| `EncodingName` Literal | lowercase | display-cased |
| `display_name` field | exists | removed |
| Pipeline string literals | lowercase | display-cased |
| Model keys | `"French/windows-1252"` | `"French/Windows-1252"` |
| `apply_display_names()` | exists | removed |
| `lookup_encoding()` | does not exist | new function |
| Markup `_normalize_encoding()` | local function | replaced by `lookup_encoding()` |
| `PREFERRED_SUPERSET` values | display-cased | display-cased (unchanged) |
| `SUPERSETS` keys/values | lowercase | display-cased |
