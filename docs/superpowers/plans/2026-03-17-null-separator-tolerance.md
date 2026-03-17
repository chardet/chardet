# Null Separator Tolerance Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix ASCII text with null byte separators (`\x00`) being misdetected as `utf-16-be` (chardet/chardet#346).

**Architecture:** Two surgical fixes plus a pipeline reorder. (1) Add a guard in the UTF-16 detector to reject candidates where nulls look like separators rather than encoding artifacts. (2) Extend ASCII detection to tolerate sparse null bytes, returning confidence 0.99. (3) Compute the ASCII check before binary detection (as a precheck) so null-containing ASCII isn't falsely classified as binary.

**Tech Stack:** Python 3.10+, pytest, mypyc-compatible code for `utf1632.py`

**Spec:** `docs/superpowers/specs/2026-03-17-null-separator-tolerance-design.md`

---

### Task 1: UTF-16 null-separator guard — tests

**Files:**
- Modify: `tests/test_utf1632.py`

- [ ] **Step 1: Write failing test — null-separated ASCII rejected by UTF-16 detector**

Add to the end of `tests/test_utf1632.py`:

```python
# ---------------------------------------------------------------------------
# Null-separator guard: sparse nulls in ASCII should NOT trigger UTF-16
# ---------------------------------------------------------------------------


def test_null_separated_ascii_not_utf16() -> None:
    """ASCII with null byte separators should not be detected as UTF-16.

    Regression test for chardet/chardet#346.
    """
    data = (
        b"master:README.md\x002\x00For support slack to #kodiak-support\n"
        b"master:support.txt\x001\x00For support slack to #kodiak-support\n"
    )
    result = detect_utf1632_patterns(data)
    assert result is None


def test_null_separated_paths_not_utf16() -> None:
    """find -print0 style output should not be detected as UTF-16."""
    data = (
        b"/home/user/documents/report.txt\x00"
        b"/home/user/documents/notes.txt\x00"
        b"/home/user/downloads/image.png\x00"
        b"/home/user/music/song.mp3\x00"
    )
    result = detect_utf1632_patterns(data)
    assert result is None


def test_real_utf16_be_still_detected() -> None:
    """Real UTF-16-BE text must still be detected after the guard is added."""
    text = "The quick brown fox jumps over the lazy dog."
    data = text.encode("utf-16-be")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-be"
    assert result.confidence == DETERMINISTIC_CONFIDENCE


def test_real_utf16_le_cjk_still_detected() -> None:
    """CJK UTF-16-LE must still be detected (low null fraction but non-ASCII non-null bytes)."""
    text = "This document: \u4f60\u597d\u4e16\u754c\uff0c\u6b22\u8fce\u6765\u5230\u8fd9\u91cc\u3002"
    data = text.encode("utf-16-le")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_utf1632.py::test_null_separated_ascii_not_utf16 tests/test_utf1632.py::test_null_separated_paths_not_utf16 -v`

Expected: FAIL — `test_null_separated_ascii_not_utf16` returns a `DetectionResult` instead of `None`. `test_null_separated_paths_not_utf16` may also fail depending on null alignment. The two `_still_detected` tests should already pass.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_utf1632.py
git commit -m "test: add failing tests for null-separator UTF-16 false positive (#346)"
```

---

### Task 2: UTF-16 null-separator guard — implementation

**Files:**
- Modify: `src/chardet/pipeline/utf1632.py`

**Important**: This file is compiled with mypyc. Do NOT add `from __future__ import annotations`.

- [ ] **Step 1: Add the null-separator guard constant and helper**

Add after the `_MIN_PRINTABLE_FRACTION` constant (line 39) in `src/chardet/pipeline/utf1632.py`:

```python
# Maximum null fraction (in the candidate null-byte position) below which
# the data is checked for a null-separator pattern.  If the null fraction
# is below this AND all non-null bytes are printable ASCII, the candidate
# is rejected as a null-separator false positive rather than real UTF-16.
# Real Latin UTF-16 has ~50% nulls; CJK UTF-16 has fewer but non-ASCII
# non-null bytes.  15% is generous — separator data is typically 1-5%.
_NULL_SEPARATOR_MAX_FRACTION = 0.15

# Bytes allowed in the "all-ASCII remainder" check for the null-separator
# guard: printable ASCII (0x20-0x7E) plus tab, newline, carriage return.
_ASCII_TEXT_BYTES: frozenset[int] = frozenset(
    [0x09, 0x0A, 0x0D, *range(0x20, 0x7F)]
)


def _is_null_separator_pattern(data: bytes, null_frac: float) -> bool:
    """Return True if the data looks like ASCII with null byte separators.

    :param data: The raw byte sample to examine.
    :param null_frac: The positional null fraction for this UTF-16 candidate
        (i.e. fraction of null bytes in even positions for BE, or odd positions
        for LE) — not the total null fraction across all bytes.

    Checks two conditions:
    1. The positional null fraction is below ``_NULL_SEPARATOR_MAX_FRACTION``
    2. Every non-null byte is printable ASCII or common whitespace

    When both conditions are met, the nulls are likely field separators
    (e.g. ``find -print0``), not UTF-16 encoding artifacts.
    """
    if null_frac >= _NULL_SEPARATOR_MAX_FRACTION:
        return False
    return all(b == 0 or b in _ASCII_TEXT_BYTES for b in data)
```

- [ ] **Step 2: Apply the guard in the candidate-building loop of `_check_utf16`**

In `_check_utf16`, replace the candidate-building block (lines 151-155):

```python
    candidates: list[tuple[str, float]] = []
    if le_frac >= _UTF16_MIN_NULL_FRACTION:
        candidates.append(("utf-16-le", le_frac))
    if be_frac >= _UTF16_MIN_NULL_FRACTION:
        candidates.append(("utf-16-be", be_frac))
```

With:

```python
    candidates: list[tuple[str, float]] = []
    if le_frac >= _UTF16_MIN_NULL_FRACTION:
        if not _is_null_separator_pattern(data[:sample_len], le_frac):
            candidates.append(("utf-16-le", le_frac))
    if be_frac >= _UTF16_MIN_NULL_FRACTION:
        if not _is_null_separator_pattern(data[:sample_len], be_frac):
            candidates.append(("utf-16-be", be_frac))
```

- [ ] **Step 3: Run the new tests to verify they pass**

Run: `uv run python -m pytest tests/test_utf1632.py -v`

Expected: ALL tests pass, including the four new ones.

- [ ] **Step 4: Run the full unit test suite to check for regressions**

Run: `uv run python -m pytest -n auto tests/ --ignore=tests/test_accuracy.py --ignore=tests/test_benchmark.py -q`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/chardet/pipeline/utf1632.py
git commit -m "fix: reject null-separator false positives in UTF-16 detector (#346)"
```

---

### Task 3: Null-tolerant ASCII detection — tests

**Files:**
- Modify: `tests/test_ascii.py`

- [ ] **Step 1: Update existing test and add new failing tests**

The existing `test_null_byte_not_ascii` test (line 43-47) asserts that null bytes cause `None`. This needs to be updated: sparse nulls now return ASCII at 0.99 confidence, while dense nulls still return `None`.

Replace `test_null_byte_not_ascii` and add new tests at the end of `tests/test_ascii.py`:

```python
def test_null_byte_not_ascii():
    # A single null in a very short string exceeds the 10% threshold
    # (1 null / 11 bytes = 9.1%, but the string is short enough that
    # the null is still sparse — adjust test data to be clearly above threshold)
    # 2 nulls in 10 bytes = 20% → binary, not ASCII
    result = detect_ascii(b"Hello\x00\x00rld")
    assert result is None


def test_ascii_with_sparse_null_separators():
    """ASCII with null separators below 10% threshold → confidence 0.99."""
    data = (
        b"master:README.md\x002\x00For support slack to #kodiak-support\n"
        b"master:support.txt\x001\x00For support slack to #kodiak-support\n"
    )
    result = detect_ascii(data)
    assert result is not None
    assert result.encoding == "ascii"
    assert result.confidence == 0.99


def test_ascii_with_null_separated_paths():
    """find -print0 style output → ASCII at 0.99."""
    data = (
        b"/home/user/documents/report.txt\x00"
        b"/home/user/documents/notes.txt\x00"
        b"/home/user/downloads/image.png\x00"
        b"/home/user/music/song.mp3\x00"
    )
    result = detect_ascii(data)
    assert result is not None
    assert result.encoding == "ascii"
    assert result.confidence == 0.99


def test_ascii_with_null_at_boundary():
    """Exactly 10% nulls (1 in 10 bytes) is at the threshold — still ASCII."""
    result = detect_ascii(b"Hello\x00wrld")  # 1/10 = 10%
    assert result is not None
    assert result.encoding == "ascii"
    assert result.confidence == 0.99


def test_ascii_with_null_just_above_boundary():
    """Just above 10% nulls → not ASCII."""
    result = detect_ascii(b"Hell\x00wrld")  # 1/9 = 11.1%
    assert result is None


def test_ascii_with_high_null_fraction():
    """More than 10% null bytes → not ASCII."""
    # 5 nulls in 15 bytes = 33%
    data = b"ab\x00cd\x00ef\x00gh\x00ij\x00"
    result = detect_ascii(data)
    assert result is None


def test_ascii_with_nulls_and_high_bytes():
    """Nulls mixed with non-ASCII bytes → not ASCII."""
    data = b"Hello\x00\x80World"
    result = detect_ascii(data)
    assert result is None


def test_pure_ascii_still_confidence_1():
    """Pure ASCII without nulls still returns confidence 1.0."""
    result = detect_ascii(b"Hello, world!")
    assert result == DetectionResult("ascii", 1.0, None)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run python -m pytest tests/test_ascii.py -v`

Expected: `test_ascii_with_sparse_null_separators` and `test_ascii_with_null_separated_paths` FAIL (currently return `None`). Others should pass (the updated `test_null_byte_not_ascii` should still pass since current code rejects all nulls).

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_ascii.py
git commit -m "test: add failing tests for null-tolerant ASCII detection (#346)"
```

---

### Task 4: Null-tolerant ASCII detection — implementation

**Files:**
- Modify: `src/chardet/pipeline/ascii.py`

- [ ] **Step 1: Implement null-tolerant ASCII detection**

Replace the entire contents of `src/chardet/pipeline/ascii.py` with:

```python
"""Stage 1c: Pure ASCII detection (with null-separator tolerance)."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# Allowed ASCII bytes: tab (0x09), newline (0x0A), carriage return (0x0D),
# and printable ASCII (0x20-0x7E).  bytes.translate deletes these from the
# input; if anything remains, the data is not pure ASCII.
_ALLOWED_ASCII: bytes = bytes([0x09, 0x0A, 0x0D, *range(0x20, 0x7F)])

# Maximum fraction of null bytes to still classify data as ASCII.
# Null-separated CLI output (find -print0, git ls-tree -z) typically has
# 1-5% nulls.  10% provides margin while excluding genuinely binary data.
_MAX_NULL_FRACTION = 0.10


def detect_ascii(data: bytes) -> DetectionResult | None:
    """Return an ASCII result if all bytes are printable ASCII plus common whitespace.

    Tolerates sparse null bytes (``\\x00``) up to ``_MAX_NULL_FRACTION`` of
    the data, returning confidence 0.99 instead of 1.0 to distinguish from
    pure ASCII.

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` for ASCII, or ``None``.
    """
    if not data:
        return None
    remainder = data.translate(None, _ALLOWED_ASCII)
    if not remainder:
        return DetectionResult(encoding="ascii", confidence=1.0, language=None)
    # Check if the only non-allowed bytes are null separators
    if remainder.replace(b"\x00", b""):
        return None  # Non-null, non-ASCII bytes present
    # All non-allowed bytes are nulls — accept if sparse enough
    null_fraction = len(remainder) / len(data)
    if null_fraction <= _MAX_NULL_FRACTION:
        return DetectionResult(encoding="ascii", confidence=0.99, language=None)
    return None
```

- [ ] **Step 2: Run the ASCII tests to verify they pass**

Run: `uv run python -m pytest tests/test_ascii.py -v`

Expected: ALL tests pass.

- [ ] **Step 3: Run the full unit test suite**

Run: `uv run python -m pytest -n auto tests/ --ignore=tests/test_accuracy.py --ignore=tests/test_benchmark.py -q`

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/chardet/pipeline/ascii.py
git commit -m "feat: tolerate sparse null separators in ASCII detection (#346)"
```

---

### Task 5: Pipeline reorder — ASCII precheck before binary detection

**Files:**
- Modify: `src/chardet/pipeline/orchestrator.py`
- Modify: `tests/test_orchestrator.py` (if needed)

- [ ] **Step 1: Add an integration test via the public API**

Add a new test class to `tests/test_github_issues.py`:

```python
# =========================================================================
# NULL SEPARATOR ISSUES
# =========================================================================


class TestNullSeparators:
    """ASCII text with null byte separators."""

    def test_issue_346_null_separated_ascii(self) -> None:
        """Issue #346: Null-separated ASCII detected as utf-16-be."""
        data = (
            b"master:README.md\x002\x00For support slack to #kodiak-support\n"
            b"master:support.txt\x001\x00For support slack to #kodiak-support\n"
        )
        result = chardet.detect(data)
        assert result["encoding"] == "ascii"
        assert result["confidence"] == 0.99

    def test_find_print0_output(self) -> None:
        """find -print0 style output should be detected as ASCII."""
        data = (
            b"/home/user/documents/report.txt\x00"
            b"/home/user/documents/notes.txt\x00"
            b"/home/user/downloads/image.png\x00"
            b"/home/user/music/song.mp3\x00"
        )
        result = chardet.detect(data)
        assert result["encoding"] == "ascii"
        assert result["confidence"] == 0.99
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run: `uv run python -m pytest tests/test_github_issues.py::TestNullSeparators -v`

Expected: FAIL — the pipeline hasn't been reordered yet, so binary detection still rejects the data before ASCII runs.

- [ ] **Step 3: Reorder the pipeline in `_run_pipeline_core`**

In `src/chardet/pipeline/orchestrator.py`, modify `_run_pipeline_core` (starting at line 531). Replace:

```python
    # Pre-check UTF-8 to prevent false binary classification.  Valid UTF-8
    # with multi-byte sequences can contain control bytes (e.g. ESC for ANSI
    # codes) that would otherwise exceed the binary threshold.  We compute
    # the result now but return it at the normal pipeline position (after
    # markup) so that explicit charset declarations still take precedence.
    utf8_precheck = detect_utf8(data)

    # Stage 0: Binary detection (skip when data is valid multi-byte UTF-8)
    # Binary detection (encoding=None) is NOT gated by filters.
    if utf8_precheck is None and is_binary(data, max_bytes=max_bytes):
        return [_BINARY_RESULT]

    # Stage 1b: Markup charset extraction (before ASCII/UTF-8 so explicit
    # declarations like <?xml encoding="iso-8859-1"?> are honoured even
    # when the bytes happen to be pure ASCII or valid UTF-8).
    markup_result = detect_markup_charset(data)
    if markup_result is not None and markup_result.encoding in allowed:
        return [markup_result]

    # Stage 1c: ASCII
    ascii_result = detect_ascii(data)
    if ascii_result is not None and ascii_result.encoding in allowed:
        return [ascii_result]

    # Stage 1d: UTF-8 structural validation (use pre-computed result)
    if utf8_precheck is not None and utf8_precheck.encoding in allowed:
        return [utf8_precheck]
```

With:

```python
    # Pre-check UTF-8 to prevent false binary classification.  Valid UTF-8
    # with multi-byte sequences can contain control bytes (e.g. ESC for ANSI
    # codes) that would otherwise exceed the binary threshold.  We compute
    # the result now but return it at the normal pipeline position (after
    # markup) so that explicit charset declarations still take precedence.
    utf8_precheck = detect_utf8(data)

    # Pre-check ASCII to prevent false binary classification.  ASCII text
    # with null byte separators (e.g. find -print0 output) would exceed the
    # binary threshold due to the null bytes.  Like the UTF-8 precheck, we
    # compute the result now but return it at the normal position (after
    # markup) so explicit charset declarations still take precedence.
    ascii_precheck = detect_ascii(data)

    # Stage 0: Binary detection (skip when data is valid UTF-8 or ASCII)
    # Binary detection (encoding=None) is NOT gated by filters.
    if (
        utf8_precheck is None
        and ascii_precheck is None
        and is_binary(data, max_bytes=max_bytes)
    ):
        return [_BINARY_RESULT]

    # Stage 1b: Markup charset extraction (before ASCII/UTF-8 so explicit
    # declarations like <?xml encoding="iso-8859-1"?> are honoured even
    # when the bytes happen to be pure ASCII or valid UTF-8).
    markup_result = detect_markup_charset(data)
    if markup_result is not None and markup_result.encoding in allowed:
        return [markup_result]

    # Stage 1c: ASCII (use pre-computed result)
    if ascii_precheck is not None and ascii_precheck.encoding in allowed:
        return [ascii_precheck]

    # Stage 1d: UTF-8 structural validation (use pre-computed result)
    if utf8_precheck is not None and utf8_precheck.encoding in allowed:
        return [utf8_precheck]
```

- [ ] **Step 4: Run the integration tests to verify they pass**

Run: `uv run python -m pytest tests/test_github_issues.py::TestNullSeparators -v`

Expected: PASS

- [ ] **Step 5: Run the full unit test suite**

Run: `uv run python -m pytest -n auto tests/ --ignore=tests/test_accuracy.py --ignore=tests/test_benchmark.py -q`

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/chardet/pipeline/orchestrator.py tests/test_github_issues.py
git commit -m "fix: reorder pipeline so ASCII precheck prevents false binary classification (#346)"
```

---

### Task 6: Run accuracy tests and validate thresholds

**Files:** None (validation only)

- [ ] **Step 1: Run the full accuracy test suite**

Run: `uv run python -m pytest tests/test_accuracy.py -n auto -q`

Expected: All accuracy tests pass with zero regressions. If any fail, the thresholds (`_NULL_SEPARATOR_MAX_FRACTION` in `utf1632.py`, `_MAX_NULL_FRACTION` in `ascii.py`) need adjustment.

- [ ] **Step 2: Run the full test suite end-to-end**

Run: `uv run python -m pytest -n auto -q`

Expected: All tests pass (unit + accuracy, excluding benchmarks which are opt-in).

- [ ] **Step 3: Commit (no-op if no threshold changes needed)**

Only if thresholds were adjusted:

```bash
git add src/chardet/pipeline/utf1632.py src/chardet/pipeline/ascii.py
git commit -m "fix: tune null-separator thresholds based on accuracy validation (#346)"
```
