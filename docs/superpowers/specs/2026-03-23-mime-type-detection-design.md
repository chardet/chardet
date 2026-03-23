# MIME Type Detection via Magic Numbers

## Summary

Add a `mime_type` field to chardet's detection results, identifying file types for both binary and text content. Binary files are identified via magic number prefix matching; text files get MIME types from the pipeline stage that identified them (markup, BOM, etc.) or default to `text/plain`.

## Data Model Changes

### `DetectionResult` (frozen dataclass)

Add `mime_type: str | None = None`. The default ensures all existing construction sites continue working.

### `DetectionDict` (TypedDict)

Add `mime_type: str | None`. The `to_dict()` method includes `mime_type` in its output.

## New Module: `pipeline/magic.py`

A lookup table of `(offset, prefix, mime_type)` tuples, ordered longest-prefix-first. The function `detect_magic(data: bytes) -> DetectionResult | None` checks the first ~16 bytes against the table.

When matched, returns `DetectionResult(encoding=None, confidence=1.0, language=None, mime_type="<mime_type>")`. When not matched, returns `None`.

### Supported Formats

All formats use fixed-offset prefix matching only — no deep analysis.

| Category | Formats |
|----------|---------|
| Images | PNG, JPEG, GIF, WebP, BMP, TIFF, ICO, AVIF |
| Audio/Video | MP3 (ID3), OGG, FLAC, WAV, AVI, WEBM/MKV |
| Archives | ZIP, GZIP, BZIP2, XZ, 7z, RAR, ZSTD, TAR (ustar at offset 257) |
| Documents | PDF, WASM, SQLite |
| Executables | ELF, Mach-O, PE (MZ) |
| Fonts | WOFF, WOFF2 |

## Pipeline Integration

The magic number check slots in between escape detection and the UTF-8/ASCII prechecks. Updated stage order:

1. **BOM** — `detect_bom()` (sets `mime_type="text/plain"`)
2. **UTF-16/32 patterns** — `detect_utf1632_patterns()` (sets `mime_type="text/plain"`)
3. **Escape sequences** — `detect_escape_encoding()` (sets `mime_type="text/plain"`)
4. **Magic numbers** — `detect_magic()` (**new**, returns binary MIME type or `None`)
5. **UTF-8 precheck** — (unchanged)
6. **ASCII precheck** — (unchanged)
7. **Binary detection** — `is_binary()` (sets `mime_type="application/octet-stream"`)
8. **Markup** — `detect_markup_charset()` (sets `mime_type="text/html"`, `"text/xml"`, or `"text/x-python"`)
9. All subsequent stages leave `mime_type=None`

At the API boundary in `run_pipeline()`: any result with `mime_type=None` gets filled with `"text/plain"` (when `encoding is not None`) or `"application/octet-stream"` (when `encoding is None`).

## Markup Stage Changes

`detect_markup_charset()` in `markup.py` sets `mime_type` based on which regex matched:

- `_XML_ENCODING_RE` → `mime_type="text/xml"`
- `_HTML5_CHARSET_RE` or `_HTML4_CONTENT_TYPE_RE` → `mime_type="text/html"`
- `_detect_pep263()` → `mime_type="text/x-python"`

## API Surface & Backward Compatibility

- **`detect()` / `detect_all()`**: The returned `DetectionDict` now always includes `"mime_type"`. This is additive — existing callers are unaffected.
- **`UniversalDetector`**: `result` property and `close()` return `DetectionDict`, so `mime_type` flows through via `to_dict()`.
- **No new parameters**: `mime_type` is always computed.
- **Feature branch**: All work done on a dedicated feature branch, not `main`.

## Testing Strategy

- **Unit tests for `detect_magic()`**: Known magic bytes for each format return correct MIME type. Partial/truncated magic bytes return `None`. Text data doesn't false-positive.
- **Unit tests for markup MIME types**: Verify `text/html`, `text/xml`, `text/x-python` are set correctly.
- **Integration tests via `detect()` / `detect_all()`**: `mime_type` key always present. Text defaults to `"text/plain"`. Unknown binary defaults to `"application/octet-stream"`.
- **Accuracy tests on `None-None` folder**: Existing binary test files (GIF, JPEG, MP4, PNG x3, WebP, XLSX) should all get correct MIME types. XLSX matches as `application/zip` (ZIP archive internally) — acceptable.
- **Existing test suite**: All tests continue passing. The new `mime_type` key is additive.
