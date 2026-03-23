# MIME Type Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `mime_type` field to chardet's detection results, identifying file types for both binary and text content via magic number prefix matching and pipeline stage annotations.

**Architecture:** Add `mime_type` to `DetectionResult` and `DetectionDict`. Create a new `pipeline/magic.py` module with a lookup table of binary format signatures. The markup stage sets `mime_type` for HTML/XML/Python. A `_fill_mime_types()` function at the API boundary defaults remaining `None` values to `"text/plain"` or `"application/octet-stream"` (same pattern as `_fill_language()`).

**Tech Stack:** Python 3.10+, dataclasses, pytest

**Spec:** `docs/superpowers/specs/2026-03-23-mime-type-detection-design.md`

**Branch:** All work on a feature branch `mime-type-detection`, not `main`.

**mypyc note:** Several pipeline modules (`escape.py`, `utf8.py`, `utf1632.py`, `statistical.py`, `structural.py`) are mypyc-compiled. Adding `mime_type` with a default value to `DetectionResult` is backward-compatible — existing construction sites (positional or keyword) continue to work because mypyc-compiled code sees the same Python-level API. No mypyc rebuild is needed for development/testing.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/chardet/pipeline/__init__.py` | Add `mime_type` field to `DetectionResult` and `DetectionDict` |
| Create | `src/chardet/pipeline/magic.py` | Magic number lookup table and `detect_magic()` |
| Modify | `src/chardet/pipeline/markup.py` | Set `mime_type` on markup detection results |
| Modify | `src/chardet/pipeline/orchestrator.py` | Integrate magic stage, add `_fill_mime_types()`, propagate `mime_type` through reconstruction sites |
| Modify | `tests/test_pipeline_types.py` | Update `to_dict()` assertions, add `mime_type` field tests |
| Modify | `tests/test_orchestrator.py` | Update `DetectionResult` comparisons for `mime_type` |
| Create | `tests/test_magic.py` | Unit tests for `detect_magic()` |
| Create | `tests/test_mime_type.py` | Integration tests for `mime_type` in `detect()`/`detect_all()`/`UniversalDetector` |

**Design decision:** Early pipeline stages (BOM, UTF-16/32, escape, ASCII, UTF-8) do NOT explicitly set `mime_type`. Instead, `_fill_mime_types()` handles the default at the API boundary, matching the same pattern used by `_fill_language()`. This keeps the diff small and avoids modifying 5+ mypyc-compiled modules.

---

### Task 1: Create Feature Branch

- [ ] **Step 1: Create and switch to feature branch**

```bash
git checkout -b mime-type-detection
```

- [ ] **Step 2: Verify branch**

Run: `git branch --show-current`
Expected: `mime-type-detection`

---

### Task 2: Add `mime_type` to `DetectionResult` and `DetectionDict`

**Files:**
- Modify: `src/chardet/pipeline/__init__.py:24-57`
- Modify: `tests/test_pipeline_types.py`

- [ ] **Step 1: Write failing tests for the new field**

Add to `tests/test_pipeline_types.py`:

```python
def test_detection_result_mime_type_default():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language="en")
    assert r.mime_type is None


def test_detection_result_mime_type_explicit():
    r = DetectionResult(encoding=None, confidence=1.0, language=None, mime_type="image/png")
    assert r.mime_type == "image/png"


def test_detection_result_to_dict_includes_mime_type():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language=None, mime_type="text/plain")
    d = r.to_dict()
    assert d == {"encoding": "UTF-8", "confidence": 0.99, "language": None, "mime_type": "text/plain"}


def test_detection_result_to_dict_mime_type_default():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language=None)
    d = r.to_dict()
    assert d == {"encoding": "UTF-8", "confidence": 0.99, "language": None, "mime_type": None}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_pipeline_types.py -v`
Expected: FAIL — `DetectionResult` does not have `mime_type` field, `to_dict()` output missing key

- [ ] **Step 3: Add `mime_type` field to `DetectionResult` and `DetectionDict`**

In `src/chardet/pipeline/__init__.py`:

Add `mime_type: str | None` to `DetectionDict`:
```python
class DetectionDict(TypedDict):
    encoding: str | None
    confidence: float
    language: str | None
    mime_type: str | None
```

Add `mime_type: str | None = None` to `DetectionResult` (after `language`):
```python
@dataclasses.dataclass(frozen=True, slots=True)
class DetectionResult:
    encoding: str | None
    confidence: float
    language: str | None
    mime_type: str | None = None

    def to_dict(self) -> DetectionDict:
        return {
            "encoding": self.encoding,
            "confidence": self.confidence,
            "language": self.language,
            "mime_type": self.mime_type,
        }
```

- [ ] **Step 4: Update existing `to_dict()` test assertions**

In `tests/test_pipeline_types.py`, update:

```python
def test_detection_result_to_dict():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language=None)
    d = r.to_dict()
    assert d == {"encoding": "UTF-8", "confidence": 0.99, "language": None, "mime_type": None}


def test_detection_result_none():
    r = DetectionResult(encoding=None, confidence=0.0, language=None)
    assert r.to_dict() == {"encoding": None, "confidence": 0.0, "language": None, "mime_type": None}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_pipeline_types.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/chardet/pipeline/__init__.py tests/test_pipeline_types.py
git commit -m "feat: add mime_type field to DetectionResult and DetectionDict"
```

---

### Task 3: Create `pipeline/magic.py` with Magic Number Detection

**Files:**
- Create: `src/chardet/pipeline/magic.py`
- Create: `tests/test_magic.py`

- [ ] **Step 1: Write failing tests for `detect_magic()`**

Create `tests/test_magic.py`:

```python
from __future__ import annotations

import pytest

from chardet.pipeline.magic import detect_magic


@pytest.mark.parametrize(
    ("data", "expected_mime"),
    [
        # Images
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png"),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 8, "image/jpeg"),
        (b"\xff\xd8\xff\xe1" + b"\x00" * 8, "image/jpeg"),
        (b"GIF87a" + b"\x00" * 8, "image/gif"),
        (b"GIF89a" + b"\x00" * 8, "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBP", "image/webp"),
        (b"BM" + b"\x00" * 12, "image/bmp"),
        (b"MM\x00\x2a" + b"\x00" * 8, "image/tiff"),
        (b"II\x2a\x00" + b"\x00" * 8, "image/tiff"),
        (b"\x00\x00\x01\x00" + b"\x00" * 8, "image/x-icon"),
        (b"\x00\x00\x00\x1cftyp" + b"avif" + b"\x00" * 4, "image/avif"),
        # Audio/Video
        (b"ID3" + b"\x00" * 10, "audio/mpeg"),
        (b"\x00\x00\x00\x1cftypMSNV", "video/mp4"),
        (b"\x00\x00\x00\x18ftypisom", "video/mp4"),
        (b"\x00\x00\x00\x18ftypmp42", "video/mp4"),
        (b"\x00\x00\x00\x20ftypM4A ", "audio/mp4"),
        (b"OggS" + b"\x00" * 10, "audio/ogg"),
        (b"fLaC" + b"\x00" * 10, "audio/flac"),
        (b"RIFF\x00\x00\x00\x00WAVE", "audio/wav"),
        (b"RIFF\x00\x00\x00\x00AVI ", "video/x-msvideo"),
        (b"\x1a\x45\xdf\xa3" + b"\x00" * 8, "video/webm"),
        # Archives
        (b"PK\x03\x04" + b"\x00" * 8, "application/zip"),
        (b"\x1f\x8b" + b"\x00" * 10, "application/gzip"),
        (b"BZh" + b"\x00" * 10, "application/x-bzip2"),
        (b"\xfd7zXZ\x00" + b"\x00" * 8, "application/x-xz"),
        (b"7z\xbc\xaf\x27\x1c" + b"\x00" * 8, "application/x-7z-compressed"),
        (b"Rar!\x1a\x07\x00" + b"\x00" * 8, "application/vnd.rar"),
        (b"Rar!\x1a\x07\x01\x00" + b"\x00" * 8, "application/vnd.rar"),
        (b"\x28\xb5\x2f\xfd" + b"\x00" * 8, "application/zstd"),
        # TAR at offset 257
        (b"\x00" * 257 + b"ustar\x00" + b"\x00" * 8, "application/x-tar"),
        (b"\x00" * 257 + b"ustar " + b"\x00" * 8, "application/x-tar"),
        # Documents
        (b"%PDF-" + b"\x00" * 8, "application/pdf"),
        (b"\x00asm" + b"\x00" * 8, "application/wasm"),
        (b"SQLite format 3\x00" + b"\x00" * 8, "application/x-sqlite3"),
        # Executables
        (b"\x7fELF" + b"\x00" * 8, "application/x-elf"),
        (b"\xfe\xed\xfa\xce" + b"\x00" * 8, "application/x-mach-binary"),
        (b"\xfe\xed\xfa\xcf" + b"\x00" * 8, "application/x-mach-binary"),
        (b"\xce\xfa\xed\xfe" + b"\x00" * 8, "application/x-mach-binary"),
        (b"\xcf\xfa\xed\xfe" + b"\x00" * 8, "application/x-mach-binary"),
        (b"MZ" + b"\x00" * 12, "application/vnd.microsoft.portable-executable"),
        # Fonts
        (b"wOFF" + b"\x00" * 8, "font/woff"),
        (b"wOF2" + b"\x00" * 8, "font/woff2"),
    ],
    ids=lambda p: p if isinstance(p, str) else None,
)
def test_detect_magic_known_formats(data: bytes, expected_mime: str) -> None:
    result = detect_magic(data)
    assert result is not None
    assert result.encoding is None
    assert result.confidence == 1.0
    assert result.language is None
    assert result.mime_type == expected_mime


def test_detect_magic_no_match() -> None:
    result = detect_magic(b"Hello, world! This is plain text.")
    assert result is None


def test_detect_magic_empty() -> None:
    result = detect_magic(b"")
    assert result is None


def test_detect_magic_truncated_png() -> None:
    """Partial PNG signature should not match."""
    result = detect_magic(b"\x89PN")
    assert result is None


def test_detect_magic_tar_too_short() -> None:
    """Data shorter than offset 257 + signature should not match TAR."""
    result = detect_magic(b"\x00" * 200 + b"ustar\x00")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_magic.py -v`
Expected: FAIL — `chardet.pipeline.magic` does not exist

- [ ] **Step 3: Implement `detect_magic()` in `src/chardet/pipeline/magic.py`**

```python
"""Magic number detection for binary file types."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# (offset, prefix_bytes, mime_type) — longest prefix first within each offset
# to avoid shorter prefixes shadowing longer ones.
_MAGIC_NUMBERS: tuple[tuple[int, bytes, str], ...] = (
    # Images
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"RIFF", ""),  # placeholder — resolved by RIFF sub-check below
    (0, b"MM\x00\x2a", "image/tiff"),
    (0, b"II\x2a\x00", "image/tiff"),
    (0, b"BM", "image/bmp"),
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x00\x00\x01\x00", "image/x-icon"),
    # Audio/Video
    (0, b"ID3", "audio/mpeg"),
    (0, b"OggS", "audio/ogg"),
    (0, b"fLaC", "audio/flac"),
    (0, b"\x1a\x45\xdf\xa3", "video/webm"),
    # Archives
    (0, b"PK\x03\x04", "application/zip"),
    (0, b"\x1f\x8b", "application/gzip"),
    (0, b"BZh", "application/x-bzip2"),
    (0, b"\xfd7zXZ\x00", "application/x-xz"),
    (0, b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (0, b"Rar!\x1a\x07\x01\x00", "application/vnd.rar"),
    (0, b"Rar!\x1a\x07\x00", "application/vnd.rar"),
    (0, b"\x28\xb5\x2f\xfd", "application/zstd"),
    # Documents
    (0, b"%PDF-", "application/pdf"),
    (0, b"\x00asm", "application/wasm"),
    (0, b"SQLite format 3\x00", "application/x-sqlite3"),
    # Executables
    (0, b"\x7fELF", "application/x-elf"),
    (0, b"\xfe\xed\xfa\xce", "application/x-mach-binary"),
    (0, b"\xfe\xed\xfa\xcf", "application/x-mach-binary"),
    (0, b"\xce\xfa\xed\xfe", "application/x-mach-binary"),
    (0, b"\xcf\xfa\xed\xfe", "application/x-mach-binary"),
    (0, b"MZ", "application/vnd.microsoft.portable-executable"),
    # Fonts
    (0, b"wOFF", "font/woff"),
    (0, b"wOF2", "font/woff2"),
)

# TAR archives have "ustar" at offset 257
_TAR_OFFSET = 257
_TAR_SIGNATURES: tuple[bytes, ...] = (b"ustar\x00", b"ustar ")

# RIFF container subtypes — determined by bytes 8-11
_RIFF_SUBTYPES: dict[bytes, str] = {
    b"WEBP": "image/webp",
    b"WAVE": "audio/wav",
    b"AVI ": "video/x-msvideo",
}

# MP4/MOV ftyp box — "ftyp" at offset 4
_FTYP_MARKER = b"ftyp"
_FTYP_OFFSET = 4
# Major brands that indicate audio rather than video
_AUDIO_FTYP_BRANDS: frozenset[bytes] = frozenset({b"M4A ", b"M4B ", b"F4A "})


def _make_result(mime: str) -> DetectionResult:
    return DetectionResult(encoding=None, confidence=1.0, language=None, mime_type=mime)


def detect_magic(data: bytes) -> DetectionResult | None:
    """Check *data* for known binary file magic numbers.

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` with ``encoding=None`` and the
        identified MIME type, or ``None`` if no magic number matches.
    """
    if not data:
        return None

    # Check ftyp box (MP4/MOV/M4A/AVIF) — "ftyp" at offset 4
    if len(data) >= 12 and data[_FTYP_OFFSET : _FTYP_OFFSET + 4] == _FTYP_MARKER:
        brand = data[8:12]
        if brand == b"avif":
            return _make_result("image/avif")
        if brand in _AUDIO_FTYP_BRANDS:
            return _make_result("audio/mp4")
        return _make_result("video/mp4")

    # Fixed-offset magic numbers
    for offset, prefix, mime in _MAGIC_NUMBERS:
        end = offset + len(prefix)
        if len(data) >= end and data[offset:end] == prefix:
            # RIFF container — need to check subtype at bytes 8-11
            if prefix == b"RIFF":
                if len(data) >= 12:
                    subtype = _RIFF_SUBTYPES.get(data[8:12])
                    if subtype is not None:
                        return _make_result(subtype)
                continue  # Unknown RIFF subtype — skip
            return _make_result(mime)

    # TAR archive — "ustar" at offset 257
    if len(data) >= _TAR_OFFSET + 6:
        tar_sig = data[_TAR_OFFSET : _TAR_OFFSET + 6]
        if tar_sig in _TAR_SIGNATURES:
            return _make_result("application/x-tar")

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_magic.py -v`
Expected: PASS

- [ ] **Step 5: Run linter**

Run: `uv run ruff check src/chardet/pipeline/magic.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/chardet/pipeline/magic.py tests/test_magic.py
git commit -m "feat: add magic number detection for binary file types"
```

---

### Task 4: Set `mime_type` on Markup Stage Results

**Files:**
- Modify: `src/chardet/pipeline/markup.py:49-53,75-88`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mime_type.py`:

```python
from __future__ import annotations

import pytest

import chardet
from chardet.detector import UniversalDetector
from chardet.pipeline.markup import detect_markup_charset


def test_markup_xml_mime_type() -> None:
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root/>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/xml"


def test_markup_html5_mime_type() -> None:
    data = b'<meta charset="utf-8"><html><body>Hello</body></html>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/html"


def test_markup_html4_mime_type() -> None:
    data = b'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/html"


def test_markup_pep263_mime_type() -> None:
    data = b"# -*- coding: utf-8 -*-\nprint('hello')\n"
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/x-python"


def test_markup_no_match_returns_none() -> None:
    result = detect_markup_charset(b"Hello, world!")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_mime_type.py -v`
Expected: FAIL — `mime_type` is `None` on all results

- [ ] **Step 3: Update `markup.py` to set `mime_type`**

In `src/chardet/pipeline/markup.py`, update `detect_markup_charset()` to track which pattern matched:

```python
    for pattern in (_XML_ENCODING_RE, _HTML5_CHARSET_RE, _HTML4_CONTENT_TYPE_RE):
        match = pattern.search(head)
        if match:
            try:
                raw_name = match.group(1).decode("ascii").strip()
            except (UnicodeDecodeError, ValueError):
                continue
            encoding = lookup_encoding(raw_name)
            if encoding is not None and _validate_bytes(data, encoding):
                mime_type = (
                    "text/xml" if pattern is _XML_ENCODING_RE else "text/html"
                )
                return DetectionResult(
                    encoding=encoding,
                    confidence=DETERMINISTIC_CONFIDENCE,
                    language=None,
                    mime_type=mime_type,
                )
```

Update `_detect_pep263()` return to include `mime_type="text/x-python"`:
```python
            return DetectionResult(
                encoding=encoding,
                confidence=DETERMINISTIC_CONFIDENCE,
                language=None,
                mime_type="text/x-python",
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_mime_type.py tests/test_pipeline_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chardet/pipeline/markup.py tests/test_mime_type.py
git commit -m "feat: set mime_type on markup detection results"
```

---

### Task 5: Integrate Magic Stage and `_fill_mime_types()` into Orchestrator

This task integrates the magic stage, adds the `_fill_mime_types()` function, fixes all `mime_type` propagation through reconstruction sites, and updates test assertions that break. All done in one task to keep the build green at each commit.

**Files:**
- Modify: `src/chardet/pipeline/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing integration tests**

Add to `tests/test_mime_type.py`:

```python
def test_detect_png_returns_mime_type() -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "image/png"


def test_detect_jpeg_returns_mime_type() -> None:
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "image/jpeg"


def test_detect_pdf_returns_mime_type() -> None:
    data = b"%PDF-1.4 " + b"\x00" * 100
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "application/pdf"


def test_text_result_defaults_to_text_plain() -> None:
    result = chardet.detect(b"Hello world")
    assert result["mime_type"] == "text/plain"


def test_binary_result_defaults_to_octet_stream() -> None:
    # Control bytes that trigger binary detection but don't match any magic number
    data = bytes(range(0, 8)) * 20
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "application/octet-stream"


def test_utf8_result_has_text_plain() -> None:
    data = "Héllo wörld café".encode()
    result = chardet.detect(data)
    assert result["mime_type"] == "text/plain"


def test_empty_input_has_text_plain() -> None:
    result = chardet.detect(b"")
    assert result["mime_type"] == "text/plain"


def test_detect_all_includes_mime_type() -> None:
    data = "Héllo wörld café résumé".encode()
    results = chardet.detect_all(data, ignore_threshold=True)
    for r in results:
        assert "mime_type" in r
        assert r["mime_type"] == "text/plain"


def test_detect_all_binary_mime_type() -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    results = chardet.detect_all(data)
    assert results[0]["mime_type"] == "image/png"


def test_universal_detector_mime_type() -> None:
    det = UniversalDetector()
    det.feed(b"Hello world")
    result = det.close()
    assert result["mime_type"] == "text/plain"


def test_universal_detector_binary_mime_type() -> None:
    det = UniversalDetector()
    det.feed(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    result = det.close()
    assert result["mime_type"] == "image/png"


def test_universal_detector_pre_close_mime_type() -> None:
    """Before close(), mime_type is None (placeholder result)."""
    det = UniversalDetector()
    assert det.result["mime_type"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_mime_type.py::test_detect_png_returns_mime_type tests/test_mime_type.py::test_text_result_defaults_to_text_plain -v`
Expected: FAIL

- [ ] **Step 3: Add `_fill_mime_types()` and integrate magic stage in orchestrator**

In `src/chardet/pipeline/orchestrator.py`:

Add `import dataclasses` at the top (after `import warnings`):
```python
import dataclasses
```

Add import for `detect_magic`:
```python
from chardet.pipeline.magic import detect_magic
```

Add `_fill_mime_types()` function (before `run_pipeline()`):
```python
def _fill_mime_types(results: list[DetectionResult]) -> list[DetectionResult]:
    """Fill in ``mime_type`` for results that don't have one set by a stage.

    Text results (``encoding is not None``) default to ``"text/plain"``.
    Binary results (``encoding is None``) default to ``"application/octet-stream"``.
    """
    filled: list[DetectionResult] = []
    for r in results:
        if r.mime_type is None:
            mime = "text/plain" if r.encoding is not None else "application/octet-stream"
            filled.append(dataclasses.replace(r, mime_type=mime))
        else:
            filled.append(r)
    return filled
```

In `_run_pipeline_core()`, add the magic number check after the escape sequence block and **before** the UTF-8 precheck. Insert right after the escape result return (after the `return [escape_result]` block):
```python
    # Magic number detection for known binary formats — runs before
    # UTF-8/ASCII prechecks to avoid unnecessary analysis on binary data.
    magic_result = detect_magic(data)
    if magic_result is not None:
        return [magic_result]
```

In `run_pipeline()`, add `_fill_mime_types()` call after `_fill_language()`:
```python
    results = _fill_language(data[:_LANG_SCORE_MAX_BYTES], results)
    results = _fill_mime_types(results)
```

- [ ] **Step 4: Fix `mime_type` propagation in confidence clamping**

In `run_pipeline()`, replace the confidence clamping list comprehension:

Replace:
```python
    return [
        DetectionResult(r.encoding, min(r.confidence, 1.0), r.language)
        if r.confidence > 1.0
        else r
        for r in results
    ]
```

With:
```python
    return [
        dataclasses.replace(r, confidence=min(r.confidence, 1.0))
        if r.confidence > 1.0
        else r
        for r in results
    ]
```

- [ ] **Step 5: Fix `mime_type` propagation in `_score_structural_candidates()`**

Replace:
```python
            boosted.append(
                DetectionResult(
                    encoding=r.encoding,
                    confidence=r.confidence * (1 + coverage),
                    language=r.language,
                )
            )
```

With:
```python
            boosted.append(
                dataclasses.replace(r, confidence=r.confidence * (1 + coverage))
            )
```

- [ ] **Step 6: Fix `mime_type` propagation in `_fill_language()`**

Replace:
```python
                filled.append(
                    DetectionResult(
                        encoding=result.encoding,
                        confidence=result.confidence,
                        language=lang,
                    )
                )
```

With:
```python
                filled.append(dataclasses.replace(result, language=lang))
```

- [ ] **Step 7: Update `_BINARY_RESULT` constant**

Update:
```python
_BINARY_RESULT = DetectionResult(
    encoding=None,
    confidence=DETERMINISTIC_CONFIDENCE,
    language=None,
    mime_type="application/octet-stream",
)
```

- [ ] **Step 8: Update test assertions in `tests/test_orchestrator.py`**

The `test_empty_input` test does exact list comparison. After `_fill_mime_types()`, the result will have `mime_type="text/plain"`. Update:

```python
def test_empty_input():
    result = run_pipeline(b"", EncodingEra.MODERN_WEB)
    assert result == [DetectionResult("utf-8", 0.10, None, "text/plain")]
```

Check for other exact `DetectionResult` comparisons in `test_orchestrator.py` and update them similarly. Any test that calls `run_pipeline()` directly and compares against `DetectionResult` objects will need `mime_type` added.

- [ ] **Step 9: Run all tests**

Run: `uv run python -m pytest tests/test_mime_type.py tests/test_pipeline_types.py tests/test_orchestrator.py tests/test_bom.py tests/test_api.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/chardet/pipeline/orchestrator.py tests/test_orchestrator.py tests/test_mime_type.py
git commit -m "feat: integrate magic stage, add _fill_mime_types(), fix mime_type propagation"
```

---

### Task 6: Integration Tests with Real Binary Test Data

**Files:**
- Modify: `tests/test_mime_type.py`

- [ ] **Step 1: Write tests using real test data files**

Add to `tests/test_mime_type.py`:

```python
from pathlib import Path

from utils import get_data_dir


def test_none_none_files_have_correct_mime_types() -> None:
    """Binary files in None-None folder should get specific MIME types."""
    data_dir = get_data_dir()
    none_dir = data_dir / "None-None"
    if not none_dir.exists():
        pytest.skip("test data not available")

    expected_mimes = {
        "sample-1.gif": "image/gif",
        "sample-1.jpg": "image/jpeg",
        "sample-1.mp4": "video/mp4",
        "sample-1.png": "image/png",
        "sample-1.webp": "image/webp",
        "sample-1.xlsx": "application/zip",
        "sample-2.png": "image/png",
        "sample-3.png": "image/png",
    }

    for filename, expected_mime in expected_mimes.items():
        filepath = none_dir / filename
        if not filepath.exists():
            continue
        data = filepath.read_bytes()
        result = chardet.detect(data)
        assert result["encoding"] is None, f"{filename}: expected binary"
        assert result["mime_type"] == expected_mime, (
            f"{filename}: expected mime_type={expected_mime}, got={result['mime_type']}"
        )
```

- [ ] **Step 2: Run the test**

Run: `uv run python -m pytest tests/test_mime_type.py::test_none_none_files_have_correct_mime_types -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_mime_type.py
git commit -m "test: add integration tests for binary file MIME type detection"
```

---

### Task 7: Full Test Suite Verification and Cleanup

- [ ] **Step 1: Run the full test suite**

Run: `uv run python -m pytest -n auto`
Expected: All tests pass (excluding known xfails)

- [ ] **Step 2: Run the linter**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Run the formatter**

Run: `uv run ruff format --check .`
Expected: No changes needed

- [ ] **Step 4: Fix any remaining issues**

If any tests fail or linter errors appear, fix them.

- [ ] **Step 5: Final commit if needed**

```bash
git add -A
git commit -m "fix: address test and lint issues from mime_type integration"
```
