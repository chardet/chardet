# Encoding Filter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `include_encodings`, `exclude_encodings`, `fallback_encoding`, and `empty_encoding` parameters to chardet's public API, enabling fine-grained control over which encodings are considered during detection.

**Architecture:** Four new keyword-only parameters are threaded through `detect()` / `detect_all()` / `UniversalDetector` -> `run_pipeline()` -> `get_candidates()`. Validation and normalization happen at the public API boundary. Early-exit pipeline stages (BOM, UTF-8, etc.) are gated against both include and exclude filters via a `_is_filtered_out()` helper. Fallback and empty results are customizable and respect the filters, emitting warnings when filtered out.

**Tech Stack:** Python 3.10+, pytest, ruff

**Spec:** `docs/plans/2026-03-14-encoding-filter-design.md`

---

## Chunk 1: Registry Layer

### Task 1: Add `normalize_encodings()` to registry

**Files:**
- Modify: `src/chardet/registry.py` (after `lookup_encoding()`, ~line 802)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for `normalize_encodings()`**

Add to `tests/test_api.py`:

```python
from chardet.registry import normalize_encodings


def test_normalize_encodings_none_returns_none():
    assert normalize_encodings(None, "include_encodings") is None


def test_normalize_encodings_valid_names():
    result = normalize_encodings(["utf-8", "cp1252"], "include_encodings")
    assert result == frozenset({"utf-8", "cp1252"})


def test_normalize_encodings_aliases():
    result = normalize_encodings(["windows-1252", "EUC-JP"], "include_encodings")
    assert result == frozenset({"cp1252", "euc_jis_2004"})


def test_normalize_encodings_unknown_raises():
    with pytest.raises(ValueError, match="Unknown encoding 'not-real'"):
        normalize_encodings(["utf-8", "not-real"], "include_encodings")


def test_normalize_encodings_empty_iterable():
    result = normalize_encodings([], "include_encodings")
    assert result == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_api.py::test_normalize_encodings_none_returns_none tests/test_api.py::test_normalize_encodings_valid_names tests/test_api.py::test_normalize_encodings_aliases tests/test_api.py::test_normalize_encodings_unknown_raises tests/test_api.py::test_normalize_encodings_empty_iterable -v`
Expected: FAIL with `ImportError` (function doesn't exist yet)

- [ ] **Step 3: Implement `normalize_encodings()`**

Add to `src/chardet/registry.py` after the `lookup_encoding()` function:

```python
from collections.abc import Iterable

def normalize_encodings(
    encodings: Iterable[str] | None,
    param_name: str,
) -> frozenset[str] | None:
    """Normalize an iterable of encoding names to canonical forms.

    :param encodings: Encoding names to normalize, or ``None``.
    :param param_name: Parameter name for error messages.
    :returns: A frozenset of canonical encoding names, or ``None``.
    :raises ValueError: If any encoding name is unknown.
    """
    if encodings is None:
        return None
    result: set[str] = set()
    for name in encodings:
        canonical = lookup_encoding(name)
        if canonical is None:
            msg = f"Unknown encoding {name!r} in {param_name}"
            raise ValueError(msg)
        result.add(canonical)
    return frozenset(result)
```

Also add `Iterable` to the imports at the top of the file:
```python
from collections.abc import Iterable
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_api.py::test_normalize_encodings_none_returns_none tests/test_api.py::test_normalize_encodings_valid_names tests/test_api.py::test_normalize_encodings_aliases tests/test_api.py::test_normalize_encodings_unknown_raises tests/test_api.py::test_normalize_encodings_empty_iterable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chardet/registry.py tests/test_api.py
git commit -m "feat: add normalize_encodings() to registry"
```

### Task 2: Extend `get_candidates()` with include/exclude filtering

**Files:**
- Modify: `src/chardet/registry.py:138-145` (the `get_candidates()` function)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for extended `get_candidates()`**

Add to `tests/test_api.py`:

```python
from chardet.registry import get_candidates
from chardet.enums import EncodingEra


def test_get_candidates_include_only():
    result = get_candidates(
        EncodingEra.ALL,
        include_encodings=frozenset({"utf-8", "cp1252"}),
    )
    names = {e.name for e in result}
    assert names == {"utf-8", "cp1252"}


def test_get_candidates_exclude_only():
    result = get_candidates(
        EncodingEra.ALL,
        exclude_encodings=frozenset({"utf-8"}),
    )
    names = {e.name for e in result}
    assert "utf-8" not in names
    assert len(names) > 50  # still has most encodings


def test_get_candidates_include_and_exclude():
    result = get_candidates(
        EncodingEra.ALL,
        include_encodings=frozenset({"utf-8", "cp1252", "cp1251"}),
        exclude_encodings=frozenset({"cp1252"}),
    )
    names = {e.name for e in result}
    assert names == {"utf-8", "cp1251"}


def test_get_candidates_include_intersects_era():
    """include_encodings={"cp1252", "iso8859-1"} with MODERN_WEB: only cp1252 survives."""
    result = get_candidates(
        EncodingEra.MODERN_WEB,
        include_encodings=frozenset({"cp1252", "iso8859-1"}),
    )
    names = {e.name for e in result}
    assert names == {"cp1252"}


def test_get_candidates_all_filtered_returns_empty():
    result = get_candidates(
        EncodingEra.ALL,
        include_encodings=frozenset({"cp1252"}),
        exclude_encodings=frozenset({"cp1252"}),
    )
    assert result == ()


def test_get_candidates_none_defaults_unchanged():
    """Default None for include/exclude returns same as era-only."""
    result_default = get_candidates(EncodingEra.MODERN_WEB)
    result_explicit = get_candidates(EncodingEra.MODERN_WEB, None, None)
    assert result_default == result_explicit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_api.py::test_get_candidates_include_only tests/test_api.py::test_get_candidates_exclude_only tests/test_api.py::test_get_candidates_include_and_exclude tests/test_api.py::test_get_candidates_include_intersects_era tests/test_api.py::test_get_candidates_all_filtered_returns_empty tests/test_api.py::test_get_candidates_none_defaults_unchanged -v`
Expected: FAIL with `TypeError` (unexpected keyword arguments)

- [ ] **Step 3: Extend `get_candidates()` signature and logic**

Replace the existing `get_candidates()` in `src/chardet/registry.py`:

```python
@functools.cache
def get_candidates(
    era: EncodingEra,
    include_encodings: frozenset[str] | None = None,
    exclude_encodings: frozenset[str] | None = None,
) -> tuple[EncodingInfo, ...]:
    """Return registry entries matching the given filters.

    Filters are applied in order: era, include, exclude.

    :param era: Bit flags specifying which encoding eras to include.
    :param include_encodings: If not ``None``, only return encodings in this set.
    :param exclude_encodings: If not ``None``, exclude encodings in this set.
    :returns: A tuple of matching :class:`EncodingInfo` entries.
    """
    candidates = (enc for enc in REGISTRY.values() if enc.era & era)
    if include_encodings is not None:
        candidates = (enc for enc in candidates if enc.name in include_encodings)
    if exclude_encodings is not None:
        candidates = (enc for enc in candidates if enc.name not in exclude_encodings)
    return tuple(candidates)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_api.py -k "get_candidates" -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `uv run python -m pytest -n auto -x`
Expected: All tests pass (existing callers pass `None` defaults)

- [ ] **Step 6: Commit**

```bash
git add src/chardet/registry.py tests/test_api.py
git commit -m "feat: extend get_candidates() with include/exclude filters"
```

---

## Chunk 2: Pipeline Orchestrator

### Task 3: Add `_is_filtered_out()` helper and thread params through orchestrator

**Files:**
- Modify: `src/chardet/pipeline/orchestrator.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for `_is_filtered_out()`**

Add to `tests/test_api.py`:

```python
from chardet.pipeline.orchestrator import _is_filtered_out


def test_is_filtered_out_none_encoding():
    assert _is_filtered_out(None, frozenset({"utf-8"}), None) is False


def test_is_filtered_out_in_include():
    assert _is_filtered_out("utf-8", frozenset({"utf-8"}), None) is False


def test_is_filtered_out_not_in_include():
    assert _is_filtered_out("cp1252", frozenset({"utf-8"}), None) is True


def test_is_filtered_out_in_exclude():
    assert _is_filtered_out("utf-8", None, frozenset({"utf-8"})) is True


def test_is_filtered_out_not_in_exclude():
    assert _is_filtered_out("cp1252", None, frozenset({"utf-8"})) is False


def test_is_filtered_out_both_none():
    assert _is_filtered_out("utf-8", None, None) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_api.py -k "is_filtered_out" -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `_is_filtered_out()` helper to orchestrator**

Add to `src/chardet/pipeline/orchestrator.py` after the `_KOI8_T_DISTINGUISHING` constant (around line 182):

```python
def _is_filtered_out(
    encoding: str | None,
    include_encodings: frozenset[str] | None,
    exclude_encodings: frozenset[str] | None,
) -> bool:
    """Check if an encoding should be filtered out by include/exclude sets."""
    if encoding is None:
        return False
    if include_encodings is not None and encoding not in include_encodings:
        return True
    if exclude_encodings is not None and encoding in exclude_encodings:
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_api.py -k "is_filtered_out" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chardet/pipeline/orchestrator.py tests/test_api.py
git commit -m "feat: add _is_filtered_out() helper to orchestrator"
```

### Task 4: Thread all four params through `run_pipeline()` and `_run_pipeline_core()`

**Files:**
- Modify: `src/chardet/pipeline/orchestrator.py:464-599` (both functions)
- Test: `tests/test_api.py`

This is the most complex task. The changes are:

1. Add params to `run_pipeline()` and `_run_pipeline_core()` signatures
2. Replace hardcoded `_EMPTY_RESULT` and `_FALLBACK_RESULT` with dynamic versions using `fallback_encoding`/`empty_encoding`
3. Gate all early-exit stages with `_is_filtered_out()`
4. Pass include/exclude to `get_candidates()`
5. Add warning when fallback/empty is filtered out

- [ ] **Step 1: Write failing integration tests**

Add to `tests/test_api.py`:

```python
import warnings


def test_detect_include_encodings_narrows():
    """include_encodings limits detection to specified encodings."""
    data = "Héllo wörld café résumé naïve".encode()
    result = chardet.detect(data, include_encodings=["cp1252"], compat_names=False)
    assert result["encoding"] == "cp1252"


def test_detect_exclude_encodings_removes():
    """exclude_encodings prevents specific encodings from being returned."""
    data = b"Hello world"
    result = chardet.detect(data, exclude_encodings=["ascii"], compat_names=False)
    assert result["encoding"] != "ascii"


def test_detect_exclude_bom_result():
    """Excluding utf-8-sig should suppress BOM detection and fall through."""
    data = b"\xef\xbb\xbfHello world"
    result = chardet.detect(data, exclude_encodings=["utf-8-sig"], compat_names=False)
    assert result["encoding"] != "utf-8-sig"


def test_detect_include_filters_bom():
    """include_encodings should filter BOM results too."""
    data = b"\xef\xbb\xbfHello world"
    result = chardet.detect(data, include_encodings=["cp1252"], compat_names=False)
    assert result["encoding"] != "utf-8-sig"


def test_detect_exclude_ascii_early_exit():
    """Excluding ascii should suppress ASCII early-exit."""
    data = b"Hello world"
    result = chardet.detect(data, exclude_encodings=["ascii"], compat_names=False)
    assert result["encoding"] != "ascii"


def test_detect_custom_fallback_encoding():
    """Custom fallback_encoding is used when no candidates survive."""
    data = b"\x80\x81\x82\x83\x84\x85"
    result = chardet.detect(
        data,
        include_encodings=["ascii"],
        fallback_encoding="ascii",
        compat_names=False,
    )
    # Data has non-ASCII bytes so ascii won't pass byte-validity;
    # pipeline falls back to the specified fallback_encoding.
    # "ascii" is in include_encodings so it is NOT filtered out.
    assert result["encoding"] == "ascii"


def test_detect_custom_empty_encoding():
    """Custom empty_encoding is used for empty input."""
    result = chardet.detect(b"", empty_encoding="ascii", compat_names=False)
    assert result["encoding"] == "ascii"


def test_detect_filtered_fallback_warns():
    """Warning emitted when fallback_encoding is filtered out."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = chardet.detect(
            b"",
            include_encodings=["cp1252"],
            compat_names=False,
        )
        # Default empty_encoding is utf-8, which is not in include_encodings
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) >= 1
        assert result["encoding"] is None
        assert result["confidence"] == 0.0


def test_detect_binary_unaffected_by_filters():
    """Binary detection (encoding=None) is not subject to filters."""
    # Data with lots of null bytes should be detected as binary
    data = b"\x00" * 100
    result = chardet.detect(
        data, include_encodings=["utf-8"], compat_names=False,
    )
    assert result["encoding"] is None


def test_detect_all_with_include():
    """detect_all respects include_encodings."""
    data = "Héllo wörld café résumé naïve".encode()
    results = chardet.detect_all(
        data,
        include_encodings=["cp1252", "cp1251"],
        ignore_threshold=True,
        compat_names=False,
    )
    encodings = {r["encoding"] for r in results}
    assert encodings <= {"cp1252", "cp1251", None}


def test_detect_unknown_include_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", include_encodings=["not-a-real-encoding"])


def test_detect_unknown_exclude_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", exclude_encodings=["not-a-real-encoding"])


def test_detect_unknown_fallback_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", fallback_encoding="not-real")


def test_detect_unknown_empty_raises():
    with pytest.raises(ValueError, match="Unknown encoding"):
        chardet.detect(b"Hello", empty_encoding="not-real")


def test_detect_all_with_exclude():
    """detect_all respects exclude_encodings."""
    data = "Héllo wörld café résumé naïve".encode()
    results = chardet.detect_all(
        data,
        exclude_encodings=["utf-8"],
        ignore_threshold=True,
        compat_names=False,
    )
    encodings = {r["encoding"] for r in results}
    assert "utf-8" not in encodings


def test_detect_include_exclude_overlap():
    """Overlapping include and exclude yields encoding=None."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = chardet.detect(
            b"Hello",
            include_encodings=["ascii"],
            exclude_encodings=["ascii"],
            compat_names=False,
        )
        assert result["encoding"] is None
        assert result["confidence"] == 0.0
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_api.py::test_detect_include_encodings_narrows tests/test_api.py::test_detect_exclude_encodings_removes tests/test_api.py::test_detect_unknown_include_raises -v`
Expected: FAIL with `TypeError` (unexpected keyword arguments)

- [ ] **Step 3: Modify `_run_pipeline_core()` to accept and use all four params**

In `src/chardet/pipeline/orchestrator.py`, replace the `_run_pipeline_core()` signature and body. Add `import warnings` at the top of the file.

New signature:
```python
def _run_pipeline_core(
    data: bytes,
    encoding_era: EncodingEra,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    include_encodings: frozenset[str] | None = None,
    exclude_encodings: frozenset[str] | None = None,
    fallback_encoding: str = "cp1252",
    empty_encoding: str = "utf-8",
) -> list[DetectionResult]:
```

Key changes in the body:
- Replace `return [_EMPTY_RESULT]` with a dynamic empty result using `empty_encoding`, gated through `_is_filtered_out()`, with a warning if filtered
- Gate every early-exit `return` through `_is_filtered_out()` — if filtered, fall through instead of returning
- Pass `include_encodings` and `exclude_encodings` to `get_candidates(encoding_era, include_encodings, exclude_encodings)`
- Replace `return [_FALLBACK_RESULT]` with a dynamic fallback using `fallback_encoding`, gated through `_is_filtered_out()`, with a warning if filtered
- When the fallback or empty encoding is filtered out, return `[DetectionResult(encoding=None, confidence=0.0, language=None)]`

Here is the full replacement for `_run_pipeline_core()`:

Also add `import warnings` at the top of the file and remove the now-dead
`_EMPTY_RESULT` and `_FALLBACK_RESULT` constants (lines 41-44).

```python
import warnings

_NONE_RESULT = DetectionResult(encoding=None, confidence=0.0, language=None)


def _make_fallback_or_none(
    encoding: str,
    include_encodings: frozenset[str] | None,
    exclude_encodings: frozenset[str] | None,
    param_name: str,
) -> list[DetectionResult]:
    """Return a low-confidence result for *encoding*, or None if filtered out.

    ``stacklevel=4`` targets the public caller: detect() -> run_pipeline()
    -> _run_pipeline_core() -> _make_fallback_or_none().
    """
    if _is_filtered_out(encoding, include_encodings, exclude_encodings):
        warnings.warn(
            f"{param_name} {encoding!r} is excluded by "
            f"include_encodings/exclude_encodings; returning encoding=None",
            UserWarning,
            stacklevel=4,
        )
        return [_NONE_RESULT]
    return [DetectionResult(encoding=encoding, confidence=0.10, language=None)]


def _run_pipeline_core(  # noqa: PLR0913, PLR0912
    data: bytes,
    encoding_era: EncodingEra,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    include_encodings: frozenset[str] | None = None,
    exclude_encodings: frozenset[str] | None = None,
    fallback_encoding: str = "cp1252",
    empty_encoding: str = "utf-8",
) -> list[DetectionResult]:
    """Core pipeline logic. Returns list of results sorted by confidence."""
    ctx = PipelineContext()
    data = data[:max_bytes]

    if not data:
        return _make_fallback_or_none(
            empty_encoding, include_encodings, exclude_encodings, "empty_encoding"
        )

    # Stage 1a: BOM detection (runs first — BOMs are definitive and
    # UTF-16/32 data looks binary due to null bytes)
    bom_result = detect_bom(data)
    if bom_result is not None and not _is_filtered_out(
        bom_result.encoding, include_encodings, exclude_encodings
    ):
        return [bom_result]

    # Stage 1a+: UTF-16/32 null-byte pattern detection (for files without
    # BOMs — must run before binary detection since these encodings contain
    # many null bytes that would trigger the binary check)
    utf1632_result = detect_utf1632_patterns(data)
    if utf1632_result is not None and not _is_filtered_out(
        utf1632_result.encoding, include_encodings, exclude_encodings
    ):
        return [utf1632_result]

    # Escape-sequence encodings (ISO-2022, HZ-GB-2312, UTF-7): must run
    # before binary detection (ESC is a control byte) and before ASCII
    # detection (HZ-GB-2312 uses only printable ASCII plus tildes).
    # Gate the result on encoding_era so that deprecated encodings like
    # UTF-7 (disabled by browsers since ~2020 as an XSS vector) are only
    # returned when the caller's era filter includes them.
    escape_result = detect_escape_encoding(data)
    if escape_result is not None and escape_result.encoding is not None:
        enc_info = REGISTRY.get(escape_result.encoding)
        if (enc_info is None or encoding_era & enc_info.era) and not _is_filtered_out(
            escape_result.encoding, include_encodings, exclude_encodings
        ):
            return [escape_result]

    # Pre-check UTF-8 to prevent false binary classification.  Valid UTF-8
    # with multi-byte sequences can contain control bytes (e.g. ESC for ANSI
    # codes) that would otherwise exceed the binary threshold.  We compute
    # the result now but return it at the normal pipeline position (after
    # markup) so that explicit charset declarations still take precedence.
    utf8_precheck = detect_utf8(data)

    # Stage 0: Binary detection (skip when data is valid multi-byte UTF-8)
    if utf8_precheck is None and is_binary(data, max_bytes=max_bytes):
        return [_BINARY_RESULT]

    # Stage 1b: Markup charset extraction (before ASCII/UTF-8 so explicit
    # declarations like <?xml encoding="iso-8859-1"?> are honoured even
    # when the bytes happen to be pure ASCII or valid UTF-8).
    markup_result = detect_markup_charset(data)
    if markup_result is not None and not _is_filtered_out(
        markup_result.encoding, include_encodings, exclude_encodings
    ):
        return [markup_result]

    # Stage 1c: ASCII
    ascii_result = detect_ascii(data)
    if ascii_result is not None and not _is_filtered_out(
        ascii_result.encoding, include_encodings, exclude_encodings
    ):
        return [ascii_result]

    # Stage 1d: UTF-8 structural validation (use pre-computed result)
    if utf8_precheck is not None and not _is_filtered_out(
        utf8_precheck.encoding, include_encodings, exclude_encodings
    ):
        return [utf8_precheck]

    # Stage 2a: Byte validity filtering
    candidates = get_candidates(encoding_era, include_encodings, exclude_encodings)
    valid_candidates = filter_by_validity(data, candidates)

    if not valid_candidates:
        return _make_fallback_or_none(
            fallback_encoding, include_encodings, exclude_encodings, "fallback_encoding"
        )

    # Gate: eliminate CJK multi-byte candidates that lack genuine
    # multi-byte structure.  Cache structural scores for Stage 2b.
    valid_candidates = _gate_cjk_candidates(data, valid_candidates, ctx)

    if not valid_candidates:
        return _make_fallback_or_none(
            fallback_encoding, include_encodings, exclude_encodings, "fallback_encoding"
        )

    # Stage 2b: Structural probing for multi-byte encodings
    # Reuse scores already computed during the CJK gate above.
    structural_scores: list[tuple[str, float]] = []
    for enc in valid_candidates:
        if enc.is_multibyte:
            score = ctx.mb_scores.get(enc.name)
            if score is None:  # pragma: no cover - gate always populates cache
                score = compute_structural_score(data, enc, ctx)
            if score > 0.0:
                structural_scores.append((enc.name, score))

    # If a multi-byte encoding scored very high, score all candidates
    # (CJK + single-byte) statistically.
    if structural_scores:
        structural_scores.sort(key=lambda x: x[1], reverse=True)
        _, best_score = structural_scores[0]
        if best_score >= _STRUCTURAL_CONFIDENCE_THRESHOLD:
            results = _score_structural_candidates(
                data, structural_scores, valid_candidates, ctx
            )
            return _postprocess_results(data, results)

    # Stage 3: Statistical scoring for all remaining candidates
    results = list(score_candidates(data, tuple(valid_candidates)))
    if not results:
        return _make_fallback_or_none(
            fallback_encoding, include_encodings, exclude_encodings, "fallback_encoding"
        )

    return _postprocess_results(data, results)
```

- [ ] **Step 4: Update `run_pipeline()` to accept and pass through all four params**

Replace the `run_pipeline()` function:

```python
def run_pipeline(  # noqa: PLR0913
    data: bytes,
    encoding_era: EncodingEra,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    include_encodings: frozenset[str] | None = None,
    exclude_encodings: frozenset[str] | None = None,
    fallback_encoding: str = "cp1252",
    empty_encoding: str = "utf-8",
) -> list[DetectionResult]:
    """Run the full detection pipeline.

    :param data: The raw byte data to analyze.
    :param encoding_era: Filter candidates to a specific era of encodings.
    :param max_bytes: Maximum number of bytes to process.
    :param include_encodings: If not ``None``, only consider these encodings.
    :param exclude_encodings: If not ``None``, exclude these encodings.
    :param fallback_encoding: Encoding for inconclusive detection.
    :param empty_encoding: Encoding for empty input.
    :returns: A list of :class:`DetectionResult` sorted by confidence descending.
    """
    results = _run_pipeline_core(
        data,
        encoding_era,
        max_bytes,
        include_encodings=include_encodings,
        exclude_encodings=exclude_encodings,
        fallback_encoding=fallback_encoding,
        empty_encoding=empty_encoding,
    )
    # Language scoring uses only the first 2 KB — bigrams converge quickly
    # and this keeps Tier 3 (language-model scoring) fast even on large inputs.
    results = _fill_language(data[:_LANG_SCORE_MAX_BYTES], results)
    if not results:  # pragma: no cover
        msg = "pipeline must always return at least one result"
        raise RuntimeError(msg)
    # Clamp confidence to [0.0, 1.0] at the public API boundary.  Internal
    # stages may boost confidence above 1.0 for ranking purposes (e.g.
    # CJK byte-coverage boost), but callers expect a probability-like value.
    return [
        DetectionResult(r.encoding, min(r.confidence, 1.0), r.language)
        if r.confidence > 1.0
        else r
        for r in results
    ]
```

- [ ] **Step 5: Run tests to verify the orchestrator changes work (tests will still fail because `detect()` doesn't pass params yet)**

Run: `uv run python -m pytest tests/test_api.py -k "is_filtered_out" -v`
Expected: PASS (helper tests pass)

- [ ] **Step 6: Commit**

```bash
git add src/chardet/pipeline/orchestrator.py tests/test_api.py
git commit -m "feat: thread include/exclude/fallback/empty through pipeline orchestrator"
```

---

## Chunk 3: Public API

### Task 5: Add params to `detect()` and `detect_all()`

**Files:**
- Modify: `src/chardet/__init__.py`
- Test: `tests/test_api.py` (tests from Task 4 step 1 should now pass)

- [ ] **Step 1: Update `detect()` signature and body**

In `src/chardet/__init__.py`, update `detect()`:

```python
def detect(  # noqa: PLR0913
    byte_str: bytes | bytearray,
    should_rename_legacy: bool = False,
    encoding_era: EncodingEra = EncodingEra.ALL,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    prefer_superset: bool = False,
    compat_names: bool = True,
    include_encodings: Iterable[str] | None = None,
    exclude_encodings: Iterable[str] | None = None,
    fallback_encoding: str = "cp1252",
    empty_encoding: str = "utf-8",
) -> DetectionDict:
```

Add imports at the top:
```python
from collections.abc import Iterable

from chardet.registry import lookup_encoding, normalize_encodings
```

Add validation and pass-through in the body, before `run_pipeline()`:
```python
    _warn_deprecated_chunk_size(chunk_size)
    _validate_max_bytes(max_bytes)
    prefer_superset = _resolve_prefer_superset(should_rename_legacy, prefer_superset)
    inc = normalize_encodings(include_encodings, "include_encodings")
    exc = normalize_encodings(exclude_encodings, "exclude_encodings")
    fb = lookup_encoding(fallback_encoding)
    if fb is None:
        msg = f"Unknown encoding {fallback_encoding!r} in fallback_encoding"
        raise ValueError(msg)
    em = lookup_encoding(empty_encoding)
    if em is None:
        msg = f"Unknown encoding {empty_encoding!r} in empty_encoding"
        raise ValueError(msg)
    data = byte_str if isinstance(byte_str, bytes) else bytes(byte_str)
    results = run_pipeline(
        data,
        encoding_era,
        max_bytes=max_bytes,
        include_encodings=inc,
        exclude_encodings=exc,
        fallback_encoding=fb,
        empty_encoding=em,
    )
    result = results[0].to_dict()
    if prefer_superset:
        apply_preferred_superset(result)
    if compat_names:
        apply_compat_names(result)
    return result
```

Update the docstring to document the new parameters (`:param include_encodings:`, etc.).

- [ ] **Step 2: Update `detect_all()` similarly**

Same pattern — add the four keyword-only params, validate, pass through.
Update the docstring to document the new parameters.

```python
def detect_all(  # noqa: PLR0913
    byte_str: bytes | bytearray,
    ignore_threshold: bool = False,
    should_rename_legacy: bool = False,
    encoding_era: EncodingEra = EncodingEra.ALL,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    prefer_superset: bool = False,
    compat_names: bool = True,
    include_encodings: Iterable[str] | None = None,
    exclude_encodings: Iterable[str] | None = None,
    fallback_encoding: str = "cp1252",
    empty_encoding: str = "utf-8",
) -> list[DetectionDict]:
```

Body validation and pass-through (same pattern as `detect()`):
```python
    _warn_deprecated_chunk_size(chunk_size)
    _validate_max_bytes(max_bytes)
    prefer_superset = _resolve_prefer_superset(should_rename_legacy, prefer_superset)
    inc = normalize_encodings(include_encodings, "include_encodings")
    exc = normalize_encodings(exclude_encodings, "exclude_encodings")
    fb = lookup_encoding(fallback_encoding)
    if fb is None:
        msg = f"Unknown encoding {fallback_encoding!r} in fallback_encoding"
        raise ValueError(msg)
    em = lookup_encoding(empty_encoding)
    if em is None:
        msg = f"Unknown encoding {empty_encoding!r} in empty_encoding"
        raise ValueError(msg)
    data = byte_str if isinstance(byte_str, bytes) else bytes(byte_str)
    results = run_pipeline(
        data,
        encoding_era,
        max_bytes=max_bytes,
        include_encodings=inc,
        exclude_encodings=exc,
        fallback_encoding=fb,
        empty_encoding=em,
    )
    dicts = [r.to_dict() for r in results]
    if not ignore_threshold:
        filtered = [d for d in dicts if d["confidence"] > MINIMUM_THRESHOLD]
        if filtered:
            dicts = filtered
    for d in dicts:
        if prefer_superset:
            apply_preferred_superset(d)
        if compat_names:
            apply_compat_names(d)
    return sorted(dicts, key=lambda d: d["confidence"], reverse=True)
```

- [ ] **Step 3: Run the integration tests from Task 4**

Run: `uv run python -m pytest tests/test_api.py -k "include_encodings or exclude_encodings or fallback_encoding or empty_encoding or unknown_include or unknown_exclude or unknown_fallback or unknown_empty" -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `uv run python -m pytest -n auto -x`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/chardet/__init__.py
git commit -m "feat: add include/exclude/fallback/empty params to detect() and detect_all()"
```

### Task 6: Add params to `UniversalDetector`

**Files:**
- Modify: `src/chardet/detector.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py`:

```python
def test_detector_include_encodings():
    from chardet.detector import UniversalDetector

    det = UniversalDetector(include_encodings=["cp1252"], compat_names=False)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    result = det.close()
    # ASCII is not in include_encodings, so it should fall through
    assert result["encoding"] != "ascii"


def test_detector_exclude_encodings():
    from chardet.detector import UniversalDetector

    det = UniversalDetector(exclude_encodings=["ascii"], compat_names=False)
    det.feed(b"Hello world, this is enough ASCII data for detection. " * 2)
    result = det.close()
    assert result["encoding"] != "ascii"


def test_detector_custom_empty_encoding():
    from chardet.detector import UniversalDetector

    det = UniversalDetector(empty_encoding="ascii", compat_names=False)
    result = det.close()  # no data fed
    assert result["encoding"] == "ascii"


def test_detector_unknown_include_raises():
    from chardet.detector import UniversalDetector

    with pytest.raises(ValueError, match="Unknown encoding"):
        UniversalDetector(include_encodings=["not-real"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_api.py::test_detector_include_encodings tests/test_api.py::test_detector_exclude_encodings tests/test_api.py::test_detector_custom_empty_encoding tests/test_api.py::test_detector_unknown_include_raises -v`
Expected: FAIL with `TypeError`

- [ ] **Step 3: Update `UniversalDetector.__init__()` and `close()`**

In `src/chardet/detector.py`, add imports:
```python
from collections.abc import Iterable

from chardet.registry import lookup_encoding, normalize_encodings
```

Update `__init__()` signature (add after `compat_names`):
```python
    def __init__(  # noqa: PLR0913
        self,
        lang_filter: LanguageFilter = LanguageFilter.ALL,
        should_rename_legacy: bool = False,
        encoding_era: EncodingEra = EncodingEra.ALL,
        max_bytes: int = DEFAULT_MAX_BYTES,
        *,
        prefer_superset: bool = False,
        compat_names: bool = True,
        include_encodings: Iterable[str] | None = None,
        exclude_encodings: Iterable[str] | None = None,
        fallback_encoding: str = "cp1252",
        empty_encoding: str = "utf-8",
    ) -> None:
```

Update the docstring to document the new parameters.

Add validation and storage in `__init__()` body (after existing setup, before `self._buffer`):
```python
        self._include_encodings = normalize_encodings(
            include_encodings, "include_encodings"
        )
        self._exclude_encodings = normalize_encodings(
            exclude_encodings, "exclude_encodings"
        )
        fb = lookup_encoding(fallback_encoding)
        if fb is None:
            msg = f"Unknown encoding {fallback_encoding!r} in fallback_encoding"
            raise ValueError(msg)
        self._fallback_encoding = fb
        em = lookup_encoding(empty_encoding)
        if em is None:
            msg = f"Unknown encoding {empty_encoding!r} in empty_encoding"
            raise ValueError(msg)
        self._empty_encoding = em
```

Update `close()` to pass params:
```python
    def close(self) -> DetectionDict:
        if not self._closed:
            self._closed = True
            data = bytes(self._buffer)
            results = run_pipeline(
                data,
                self._encoding_era,
                max_bytes=self._max_bytes,
                include_encodings=self._include_encodings,
                exclude_encodings=self._exclude_encodings,
                fallback_encoding=self._fallback_encoding,
                empty_encoding=self._empty_encoding,
            )
            self._result = results[0]
            self._done = True
        return self.result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_api.py -k "detector_include or detector_exclude or detector_custom_empty or detector_unknown_include" -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest -n auto -x`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/chardet/detector.py tests/test_api.py
git commit -m "feat: add include/exclude/fallback/empty params to UniversalDetector"
```

---

## Chunk 4: CLI and Final Tests

### Task 7: Add CLI flags

**Files:**
- Modify: `src/chardet/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_cli_include_encodings(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["-i", "utf-8,ascii", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out


def test_cli_exclude_encodings(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["-x", "ascii", "--minimal", str(f)])
    captured = capsys.readouterr()
    assert captured.out.strip().lower() != "ascii"


def test_cli_include_long_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["--include-encodings", "utf-8,ascii", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out


def test_cli_exclude_long_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["--exclude-encodings", "ascii", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out


def test_cli_fallback_encoding(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["--fallback-encoding", "ascii", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out


def test_cli_empty_encoding(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"")
    main(["--empty-encoding", "ascii", str(f)])
    captured = capsys.readouterr()
    assert "ascii" in captured.out.lower()


def test_cli_include_with_spaces(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Comma-separated values with spaces should be stripped."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["-i", "utf-8, ascii", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_cli.py::test_cli_include_encodings tests/test_cli.py::test_cli_exclude_encodings -v`
Expected: FAIL (unrecognized arguments)

- [ ] **Step 3: Add CLI arguments to `cli.py`**

In `src/chardet/cli.py`, add four new arguments after the `--encoding-era` argument:

```python
    parser.add_argument(
        "-i",
        "--include-encodings",
        default=None,
        help="Comma-separated list of encodings to consider",
    )
    parser.add_argument(
        "-x",
        "--exclude-encodings",
        default=None,
        help="Comma-separated list of encodings to exclude",
    )
    parser.add_argument(
        "--fallback-encoding",
        default="cp1252",
        help="Encoding to return when detection is inconclusive (default: cp1252)",
    )
    parser.add_argument(
        "--empty-encoding",
        default="utf-8",
        help="Encoding to return for empty input (default: utf-8)",
    )
```

Then parse the comma-separated values and pass to `chardet.detect()`. After the `era = ...` line, add:

```python
    include = (
        [s.strip() for s in args.include_encodings.split(",")]
        if args.include_encodings
        else None
    )
    exclude = (
        [s.strip() for s in args.exclude_encodings.split(",")]
        if args.exclude_encodings
        else None
    )
```

Update both `chardet.detect()` calls to pass the new params:

```python
                result = chardet.detect(
                    data,
                    encoding_era=era,
                    include_encodings=include,
                    exclude_encodings=exclude,
                    fallback_encoding=args.fallback_encoding,
                    empty_encoding=args.empty_encoding,
                )
```

(Same for the stdin path.)

- [ ] **Step 4: Run CLI tests**

Run: `uv run python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest -n auto -x`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/chardet/cli.py tests/test_cli.py
git commit -m "feat: add -i/-x/--fallback-encoding/--empty-encoding CLI flags"
```

### Task 8: Performance sanity check

**Files:**
- Test: `tests/test_api.py`

- [ ] **Step 1: Write a performance test**

Add to `tests/test_api.py`:

```python
import time


def test_detect_default_params_no_regression():
    """Default path (no include/exclude) should not be measurably slower."""
    data = "Héllo wörld café résumé naïve über straße".encode()
    # Warm up caches
    chardet.detect(data)
    chardet.detect(data)

    start = time.perf_counter()
    for _ in range(1000):
        chardet.detect(data)
    elapsed_default = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(1000):
        chardet.detect(data, include_encodings=None, exclude_encodings=None)
    elapsed_explicit_none = time.perf_counter() - start

    # Explicit None should be within 50% of default (same code path)
    assert elapsed_explicit_none < elapsed_default * 1.5
```

- [ ] **Step 2: Run the test**

Run: `uv run python -m pytest tests/test_api.py::test_detect_default_params_no_regression -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add performance sanity check for encoding filter params"
```

### Task 9: Lint and final validation

- [ ] **Step 1: Run linter**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 2: Run formatter**

Run: `uv run ruff format --check .`
Expected: No changes needed

- [ ] **Step 3: Run full test suite one final time**

Run: `uv run python -m pytest -n auto`
Expected: All tests pass

- [ ] **Step 4: Fix any lint/format/test issues and commit**

```bash
git add -u
git commit -m "style: fix lint/format issues"
```
