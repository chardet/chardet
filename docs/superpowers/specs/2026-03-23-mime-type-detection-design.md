# MIME Type Detection via Magic Numbers

## Summary

Add a `mime_type` field to chardet's detection results, identifying file types for both binary and text content. Binary files are identified via magic number prefix matching; text files get MIME types from the pipeline stage that identified them (markup, BOM, etc.) or default to `text/plain`.

## Data Model Changes

### `DetectionResult` (frozen dataclass)

Add `mime_type: str | None = None`. The default ensures all existing construction sites continue working.

**Propagation through reconstruction sites**: Several places in the orchestrator construct new `DetectionResult` objects from existing ones (confidence clamping in `run_pipeline()`, boosting in `_score_structural_candidates()`, language filling in `_fill_language()`, fallback results in `_make_fallback_or_none()`). Each of these must propagate `mime_type` from the source result. Use `dataclasses.replace()` where possible to avoid dropping fields.

### `DetectionDict` (TypedDict)

Add `mime_type: str | None`. The `to_dict()` method includes `mime_type` in its output.

This is additive at runtime — existing code indexing by key or iterating over results is unaffected. However, tests that do exact dict comparison will need the new key added.

## New Module: `pipeline/magic.py`

Uses `from __future__ import annotations` (not mypyc-compiled — it's a simple table lookup).

A lookup table of `(offset, prefix, mime_type)` tuples, ordered longest-prefix-first. The function `detect_magic(data: bytes) -> DetectionResult | None` checks the data against the table. Most entries match at offset 0 within the first 16 bytes; TAR is a special case matching `ustar` at offset 257 (requiring at least 262 bytes).

When matched, returns `DetectionResult(encoding=None, confidence=1.0, language=None, mime_type="<mime_type>")`. When not matched, returns `None`.

### Supported Formats

All formats use fixed-offset prefix matching only — no deep analysis.

| Category | Formats |
|----------|---------|
| Images | PNG, JPEG, GIF, WebP, BMP, TIFF, ICO, AVIF |
| Audio/Video | MP3 (ID3), MP4/MOV (ftyp at offset 4), OGG, FLAC, WAV, AVI, WEBM/MKV |
| Archives | ZIP, GZIP, BZIP2, XZ, 7z, RAR, ZSTD, TAR (ustar at offset 257) |
| Documents | PDF, WASM, SQLite |
| Executables | ELF, Mach-O, PE (MZ) |
| Fonts | WOFF, WOFF2 |

## Pipeline Integration

The magic number check runs after escape detection and **before** the UTF-8/ASCII prechecks are computed. This means binary files identified by magic numbers skip UTF-8/ASCII analysis entirely. Updated stage order in the orchestrator:

1. **BOM** — `detect_bom()` (sets `mime_type="text/plain"`)
2. **UTF-16/32 patterns** — `detect_utf1632_patterns()` (sets `mime_type="text/plain"`)
3. **Escape sequences** — `detect_escape_encoding()` (sets `mime_type="text/plain"`)
4. **Magic numbers** — `detect_magic()` (**new**, returns binary MIME type or `None`; short-circuits on match)
5. **UTF-8 precheck** — computed (unchanged)
6. **ASCII precheck** — computed (unchanged)
7. **Binary detection** — `is_binary()` (sets `mime_type="application/octet-stream"`)
8. **Markup** — `detect_markup_charset()` (sets `mime_type="text/html"`, `"text/xml"`, or `"text/x-python"`)
9. All subsequent stages leave `mime_type=None`

**MIME type fill at the API boundary**: A `_fill_mime_types()` function in `run_pipeline()` (alongside `_fill_language()`) sets `mime_type` for any result that still has `None`: `"text/plain"` when `encoding is not None`, `"application/octet-stream"` when `encoding is None`.

## Markup Stage Changes

`detect_markup_charset()` in `markup.py` sets `mime_type` based on which regex matched:

- `_XML_ENCODING_RE` → `mime_type="text/xml"`
- `_HTML5_CHARSET_RE` or `_HTML4_CONTENT_TYPE_RE` → `mime_type="text/html"`
- `_detect_pep263()` → `mime_type="text/x-python"` (only when a PEP 263 encoding declaration is found — Python files without declarations will not get this MIME type)

## API Surface & Backward Compatibility

- **`detect()` / `detect_all()`**: The returned `DetectionDict` now always includes `"mime_type"`. This is additive — existing callers indexing by key are unaffected.
- **`UniversalDetector`**: `result` property and `close()` return `DetectionDict`, so `mime_type` flows through via `to_dict()`. The pre-close sentinel (`_NONE_RESULT`) will have `mime_type=None` — this is acceptable since results before `close()` are placeholders.
- **`compat_names` / `apply_compat_names()` / `apply_preferred_superset()`**: These functions do not affect `mime_type`. MIME types are standardized strings and are not subject to encoding name remapping.
- **No new parameters**: `mime_type` is always computed.
- **Feature branch**: All work done on a dedicated feature branch, not `main`.

## Testing Strategy

- **Unit tests for `detect_magic()`**: Known magic bytes for each format return correct MIME type. Partial/truncated magic bytes return `None`. Text data doesn't false-positive.
- **Unit tests for markup MIME types**: Verify `text/html`, `text/xml`, `text/x-python` are set correctly.
- **Integration tests via `detect()` / `detect_all()`**: `mime_type` key always present. Text defaults to `"text/plain"`. Unknown binary defaults to `"application/octet-stream"`.
- **Accuracy tests on `None-None` folder**: Existing binary test files (GIF, JPEG, MP4, PNG x3, WebP, XLSX) should all get correct MIME types. XLSX matches as `application/zip` (ZIP archive internally) — acceptable.
- **Existing test suite**: All tests continue passing. Tests doing exact dict comparison will need the `mime_type` key added.
