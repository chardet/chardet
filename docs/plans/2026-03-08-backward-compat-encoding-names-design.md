# Backward-Compatible Encoding Names

**Date:** 2026-03-08
**Status:** Implemented

## Problem

The `canonical-encoding-names` branch renamed all internal encoding registry
names from mixed-case (e.g., `ascii`, `windows-1252`, `SHIFT_JIS`) to
display-cased canonical names (e.g., `ASCII`, `Windows-1252`, `Shift-JIS-2004`).
This accidentally changed the output of `detect()` and `detect_all()`, breaking
backward compatibility with chardet 5.x/6.x.

Many downstream projects compare `result["encoding"]` against string literals
like `"ascii"`, `"utf-8"`, or `"windows-1252"`. Changing these names in a minor
version bump would break those comparisons silently.

## Solution: Name-Only Compat Mapping (Option 3)

Keep the canonical display-cased names internally but map them back to chardet
5.x names in the public API output by default.

### How it works

- `should_rename_legacy` defaults to `False` (backward-compatible).
- When `False`: `apply_compat_names()` maps canonical names → chardet 5.x names
  via the `_LEGACY_NAMES` dict in `equivalences.py`.
- When `True`: `apply_legacy_rename()` maps ISO encodings → Windows superset
  equivalents via `PREFERRED_SUPERSET`.
- Applied in `detect()`, `detect_all()`, and `UniversalDetector.result`/`close()`.

### Name mapping (`_LEGACY_NAMES`)

Only entries that differ from the canonical name are listed. Unlisted names pass
through unchanged.

| Canonical (internal) | Chardet 5.x (output) |
|---------------------|---------------------|
| `ASCII`             | `ascii`             |
| `Big5-HKSCS`        | `Big5`              |
| `EUC-JIS-2004`      | `EUC-JP`            |
| `ISO-2022-JP-2`     | `ISO-2022-JP`       |
| `Mac-Cyrillic`      | `MacCyrillic`       |
| `Mac-Greek`         | `MacGreek`          |
| `Mac-Iceland`       | `MacIceland`        |
| `Mac-Latin2`        | `MacLatin2`         |
| `Mac-Roman`         | `MacRoman`          |
| `Mac-Turkish`       | `MacTurkish`        |
| `Shift-JIS-2004`    | `SHIFT_JIS`         |
| `UTF-7`             | `utf-7`             |
| `UTF-8`             | `utf-8`             |
| `UTF-16-BE`         | `utf-16be`          |
| `UTF-16-LE`         | `utf-16le`          |
| `UTF-32-BE`         | `utf-32be`          |
| `UTF-32-LE`         | `utf-32le`          |
| `Windows-125x`      | `windows-125x`      |

Bare `"UTF-16"` and `"UTF-32"` are NOT in the mapping because (a) our pipeline
never produces them (it always returns with endianness), and (b) chardet 5.x
returned them uppercase, which matches our canonical names already.

### Accepted behavioral differences from chardet 5.x

These are detection quality improvements, not naming changes:

1. **UTF-16/32 endianness**: chardet 5.x returned `"UTF-16"` for BOM-detected
   files; chardet 7 returns `"utf-16le"` or `"utf-16be"`. This is more precise
   and both decode correctly with `data.decode(result["encoding"])`.

2. **GB2312 → GB18030**: chardet 5.x had a GB2312 prober; chardet 7 uses
   GB18030 (a strict superset). All valid GB2312 data decodes correctly as
   GB18030.

## Files Changed

- `src/chardet/equivalences.py` — Added `_LEGACY_NAMES`, `apply_compat_names()`
- `src/chardet/__init__.py` — Wired compat/legacy rename into `detect()`,
  `detect_all()`
- `src/chardet/detector.py` — Wired into `UniversalDetector.result` and
  `close()`
- `docs/usage.rst` — Documented `should_rename_legacy` parameter
- `tests/test_api.py` — Tests for both `should_rename_legacy=True` and `False`
- `tests/test_detector.py` — Tests for compat names in detector output
- `tests/test_cli.py` — CLI tests use case-insensitive assertions
