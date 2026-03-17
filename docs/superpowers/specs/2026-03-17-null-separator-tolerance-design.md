# Null Separator Tolerance

**Date**: 2026-03-17
**Issue**: https://github.com/chardet/chardet/issues/346
**Branch**: `null-separator-tolerance`

## Problem

ASCII text containing null byte (`\x00`) separators — common in Unix CLI output (`find -print0`, `git ls-tree -z`, `xargs -0`) — is misdetected as `utf-16-be` with confidence 0.95.

The root cause is a two-stage failure:

1. **False UTF-16 match**: The UTF-16 detector (`utf1632.py`) runs early in the pipeline and has a low null-fraction threshold (`_UTF16_MIN_NULL_FRACTION = 0.03`) to catch CJK-heavy UTF-16. Null separators at 3-5% of data clear this threshold, and the decoded text passes `_looks_like_text()` because the non-null bytes are valid ASCII.

2. **No fallback to ASCII**: Even if UTF-16 were rejected, the data would hit binary detection next (`is_binary()`), since null bytes are in `_BINARY_DELETE` and 3.5% > the 1% binary threshold. ASCII detection never runs.

## Design

Two targeted fixes plus a pipeline reorder.

### Site 1: UTF-16 guard — reject separator-like null patterns

**File**: `src/chardet/pipeline/utf1632.py`

In `_check_utf16`, for each candidate identified by null-fraction, add a guard before decode/accept:

- If the null fraction in the candidate position is below a threshold (target: ~15%) AND the non-null bytes are all printable ASCII plus common whitespace (`\t`, `\n`, `\r`), reject the UTF-16 candidate.

This guard must apply in **both** code paths of `_check_utf16`: the single-candidate path (lines 161-173) and the dual-candidate path (lines 176-197). The cleanest approach is to filter candidates in the candidate-building loop (lines 151-155) before the branching logic.

**Rationale**: Real UTF-16 of Latin text has ~50% nulls in alternating positions. CJK UTF-16 has fewer nulls but the non-null bytes are NOT printable ASCII (CJK characters have non-zero bytes in both positions of each code unit). The combined check (low null fraction + all-ASCII remainder) uniquely identifies null-separator data without affecting real UTF-16 detection.

**Threshold**: Start at 15%. Real UTF-16 of mixed Latin/CJK text with the lowest null fraction we've seen in the test suite is ~4.5% (CJK-heavy), but that data has non-ASCII non-null bytes. The guard only fires when non-null bytes are all ASCII, so the threshold can be generous.

**Note**: This module is compiled with mypyc. Any new helper functions must be mypyc-compatible, and `from __future__ import annotations` must NOT be added.

### Site 2: Null-tolerant ASCII detection

**File**: `src/chardet/pipeline/ascii.py`

Extend `detect_ascii` to handle data where the only non-standard bytes are `\x00`:

1. First, try the existing fast path: `data.translate(None, _ALLOWED_ASCII)`. If nothing remains, return pure ASCII at confidence 1.0 (unchanged behavior).
2. If non-allowed bytes remain, check whether they are ALL `\x00`. The existing `_ALLOWED_ASCII` table does not include `\x00`, so this is a simple check on the remainder bytes.
3. If the only non-allowed bytes are nulls and the null fraction is below a threshold (target: ~10%), return `DetectionResult(encoding="ascii", confidence=0.99, language=None)`.
4. Otherwise return `None` — the data has non-ASCII bytes or too many nulls.

**Confidence 0.99**: Distinguishes "ASCII with null separators" from "pure ASCII" (confidence 1.0), giving consumers a signal that something slightly unusual is present without undermining the detection.

**Threshold**: Start at 10%. Null-separated CLI output typically has nulls at 1-5% of data. A 10% ceiling provides margin while excluding data that is likely binary or structured differently.

### Pipeline reorder: ASCII precheck before binary detection

**File**: `src/chardet/pipeline/orchestrator.py`

Compute the ASCII result before binary detection so it can prevent false binary rejection, paralleling the existing UTF-8 precheck pattern.

**Rationale**: Just as valid UTF-8 with control bytes (e.g., ANSI escape codes) would be falsely rejected by binary detection, valid ASCII with null separators would be falsely rejected. The precheck pattern already exists for UTF-8; extending it to ASCII is a clean parallel.

**Implementation**: Compute `ascii_precheck = detect_ascii(data)` alongside the existing `utf8_precheck = detect_utf8(data)`, before the binary detection call. The binary detection guard becomes:

```python
if utf8_precheck is None and ascii_precheck is None and is_binary(data, ...):
    return [_BINARY_RESULT]
```

The ASCII precheck result is **returned** at the same position ASCII currently occupies (after markup), so explicit charset declarations still take precedence. The computation order and the return order are different — this matches the existing UTF-8 precheck pattern exactly.

**Note**: `UniversalDetector` delegates to `run_pipeline()`, so these changes propagate to the streaming interface automatically. No changes needed in `detector.py`.

## Thresholds to validate experimentally

| Threshold | Location | Starting value | Purpose |
|-----------|----------|---------------|---------|
| UTF-16 null-fraction ceiling | `utf1632.py` | 15% | Max null fraction to trigger separator guard |
| ASCII null-fraction ceiling | `ascii.py` | 10% | Max null fraction to still call it ASCII |

Both thresholds must be validated against the full accuracy test suite (`test_accuracy.py`) to confirm zero regressions.

## Testing

- **Unit test**: the exact byte string from issue #346 should return `encoding="ascii"` with `confidence=0.99` (the public API converts `language=None` to `""` in the dict)
- **Unit test**: `find -print0` style output (null-separated file paths) should return ASCII
- **Unit test**: real UTF-16-BE data (with and without BOM) should still be detected correctly
- **Unit test**: data with high null fraction (>10%) should NOT return ASCII
- **Unit test**: data mixing nulls with non-ASCII high bytes should not be affected
- **Accuracy tests**: full suite must pass with no regressions

## Out of scope

- Tolerating other control codes (SOH, STX, etc.) in ASCII detection — different problem, different solution
- Changing binary detection thresholds — the ASCII precheck sidesteps binary detection entirely for this case
- Null tolerance in non-ASCII single-byte encodings (e.g., windows-1252 with null separators) — possible future extension but not needed for the reported issue
