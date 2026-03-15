# Encoding Filter Design

**Date:** 2026-03-14
**Issue:** [chardet/chardet#301](https://github.com/chardet/chardet/issues/301)
**Branch:** `filter-by-lister`

## Problem

Users need to constrain detection to a specific set of encodings or exclude
known-bad candidates. The existing `encoding_era` parameter provides coarse
filtering by era/family, but cannot express "only consider these three
encodings" or "never return EUC-KR." This causes false positives that users
cannot work around without post-hoc filtering of results.

## Design

### New Parameters

Four new keyword-only parameters on `detect()`, `detect_all()`, and
`UniversalDetector.__init__()`:

```python
include_encodings: Iterable[str] | None = None
exclude_encodings: Iterable[str] | None = None
fallback_encoding: str = "cp1252"
empty_encoding: str = "utf-8"
```

- **`include_encodings`** — whitelist. Only these encodings may be returned,
  both from early-exit stages and from candidate scoring. `None` (default)
  means no restriction beyond `encoding_era`.
- **`exclude_encodings`** — blacklist. These encodings are never returned,
  removed from both early-exit results and candidate scoring. `None`
  (default) means no exclusions.
- **`fallback_encoding`** — encoding returned when no candidates remain after
  all pipeline stages. Default is `"cp1252"` (the HTTP/1.1 default charset
  and most common single-byte web encoding).
- **`empty_encoding`** — encoding returned when the input is empty. Default
  is `"utf-8"` (the HTML5 default encoding).

`include_encodings` and `exclude_encodings` accept any `Iterable[str]`.
`fallback_encoding` and `empty_encoding` accept a single `str`. All names
are resolved through `lookup_encoding()` so aliases and arbitrary casing work
(e.g., `"windows-1252"`, `"cp1252"`, `"Windows-1252"` all resolve to the
canonical `"cp1252"`).

### Validation

A new `normalize_encodings()` function in `registry.py`:

```python
def normalize_encodings(
    encodings: Iterable[str] | None,
    param_name: str,
) -> frozenset[str] | None:
```

- Returns `None` if input is `None`.
- Calls `lookup_encoding()` on each name.
- Raises `ValueError` for unknown names:
  `"Unknown encoding 'foo' in {param_name}"`.
- Returns a `frozenset` of canonical `EncodingName` strings.

`fallback_encoding` and `empty_encoding` are validated individually via
`lookup_encoding()`, raising `ValueError` for unknown names.

Validation is called at the three public entry points (`detect`, `detect_all`,
`UniversalDetector.__init__`) so it happens once, early.

### Filter Semantics

**Intersection:** `encoding_era`, `include_encodings`, and
`exclude_encodings` are all applied. Era narrows the full registry,
`include_encodings` further narrows within that, and `exclude_encodings`
removes from whatever remains. To include encodings from multiple eras, use
`encoding_era=EncodingEra.ALL` (the default) and rely on
`include_encodings` alone.

Example: `encoding_era=MODERN_WEB, include_encodings={"cp1252", "iso8859-1"}`
returns only `cp1252` because `iso8859-1` is `LEGACY_ISO`, not `MODERN_WEB`.

**Overlap:** If `include_encodings` and `exclude_encodings` overlap, the
filters work naturally — the intersection produces no candidates and the
caller receives `DetectionResult(encoding=None, confidence=0.0,
language=None)`.

### Candidate Filtering (`get_candidates()`)

The existing `get_candidates()` in `registry.py` is extended:

```python
@functools.cache
def get_candidates(
    era: EncodingEra,
    include_encodings: frozenset[str] | None = None,
    exclude_encodings: frozenset[str] | None = None,
) -> tuple[EncodingInfo, ...]:
```

Filters are applied in order: era, include, exclude. The function stays
`@functools.cache`d — `frozenset` and `None` are both hashable, and users
calling `detect()` in a loop with the same filters will hit the cache.

### Early-Exit Stage Gating

Early pipeline stages (BOM, UTF-16/32 patterns, escape sequences, markup
charset, ASCII, UTF-8) return definitive results that bypass
`get_candidates()`. These are gated against **both** `include_encodings` and
`exclude_encodings`.

Rationale: when a user passes `include_encodings=["cp1252"]`, they are
saying "only return these encodings." Returning an encoding they did not
include — even if it's structurally definitive like a BOM — violates that
contract. Similarly, `exclude_encodings` is a "never return this" signal.

In `_run_pipeline_core()`, a helper checks each early-exit result:

```python
def _is_filtered_out(
    encoding: str | None,
    include_encodings: frozenset[str] | None,
    exclude_encodings: frozenset[str] | None,
) -> bool:
    if encoding is None:
        return False
    if include_encodings is not None and encoding not in include_encodings:
        return True
    if exclude_encodings is not None and encoding in exclude_encodings:
        return True
    return False
```

When an early-exit result is filtered out, the pipeline falls through to the
next stage rather than returning.

This applies to: BOM (1a), UTF-16/32 patterns (1a+), escape sequences (1b),
markup charset (1c), ASCII (1d), UTF-8 (1e).

**Binary detection** (`encoding=None, confidence=1.0`) is **not** subject to
encoding filters, as it represents the absence of text encoding rather than
a specific encoding.

### Fallback and Empty Results

The pipeline has two hardcoded results that are now customizable:

- **Empty result** — returned when input data is empty. Default:
  `DetectionResult(encoding="utf-8", confidence=0.10, language=None)`.
  Customizable via `empty_encoding`.
- **Fallback result** — returned when no candidates survive filtering.
  Default: `DetectionResult(encoding="cp1252", confidence=0.10,
  language=None)`. Customizable via `fallback_encoding`.

Both are subject to include/exclude filtering. If the fallback or empty
encoding is itself filtered out (not in `include_encodings` or in
`exclude_encodings`), the pipeline returns
`DetectionResult(encoding=None, confidence=0.0, language=None)` and issues
a `UserWarning`:

```
"fallback_encoding 'cp1252' is excluded by include_encodings/exclude_encodings; returning encoding=None"
```

This prevents silent surprises while respecting the filter contract.

### Parameter Flow

```
detect(
    data,
    include_encodings=["utf-8", "cp1252"],
    exclude_encodings=["euc-kr"],
    fallback_encoding="cp1252",
    empty_encoding="utf-8",
)
  |
  |-- normalize_encodings(["utf-8", "cp1252"]) -> frozenset({"utf-8", "cp1252"})
  |-- normalize_encodings(["euc-kr"])           -> frozenset({"euc_kr"})
  |   (canonical names may differ from user-supplied aliases,
  |    e.g. "euc-kr" resolves to "euc_kr")
  |-- lookup_encoding("cp1252")                 -> "cp1252"
  |-- lookup_encoding("utf-8")                  -> "utf-8"
  |
  +-- run_pipeline(data, era, include_encodings=..., exclude_encodings=...,
  |                fallback_encoding=..., empty_encoding=...)
       |
       |-- Empty check: return empty_encoding result (if not filtered out)
       |-- Early-exit stages: gated against include and exclude
       |
       +-- get_candidates(era, include_encodings, exclude_encodings)
            |-- era filter:     enc.era & era
            |-- include filter: enc.name in include_encodings
            +-- exclude filter: enc.name not in exclude_encodings
```

### CLI

Four new flags in `chardetect`:

```
-i, --include-encodings   Comma-separated list of encodings to consider
-x, --exclude-encodings   Comma-separated list of encodings to exclude
    --fallback-encoding   Encoding to return when detection is inconclusive
    --empty-encoding      Encoding to return for empty input
```

Examples:

```bash
chardetect -i utf-8,cp1252,cp1251 file.txt
chardetect -x euc-kr,big5 file.txt
chardetect -i utf-8,cp1252 -x cp1252 file.txt  # effectively only utf-8
chardetect --fallback-encoding ascii file.txt
```

`-i`/`-x` values are parsed by splitting on `,` and stripping whitespace.
All values are passed through to `chardet.detect()`.

### `UniversalDetector`

Constructor gains all four parameters:

```python
def __init__(
    self,
    ...,
    include_encodings: Iterable[str] | None = None,
    exclude_encodings: Iterable[str] | None = None,
    fallback_encoding: str = "cp1252",
    empty_encoding: str = "utf-8",
) -> None:
```

Normalized in `__init__` (iterables to frozensets, strings via
`lookup_encoding()`), stored as instance attributes, passed to
`run_pipeline()` in `close()`.

## Files Changed

| File | Change |
|------|--------|
| `src/chardet/registry.py` | Add `normalize_encodings()`, extend `get_candidates()` signature |
| `src/chardet/pipeline/orchestrator.py` | Thread all four params through `run_pipeline()` and `_run_pipeline_core()`, add `_is_filtered_out()` helper, apply gating to early-exit stages, use `fallback_encoding`/`empty_encoding` with filter checks and warnings |
| `src/chardet/__init__.py` | Add params to `detect()` and `detect_all()`, call `normalize_encodings()` and `lookup_encoding()` for validation |
| `src/chardet/detector.py` | Add params to `UniversalDetector.__init__()`, store and pass through |
| `src/chardet/cli.py` | Add `-i`/`--include-encodings`, `-x`/`--exclude-encodings`, `--fallback-encoding`, `--empty-encoding` flags |
| `tests/test_api.py` | Unit and integration tests |

## Testing

- **`normalize_encodings()`** — valid names, aliases, unknown names raise `ValueError`
- **`get_candidates()`** — include-only, exclude-only, both, interaction with era, empty result
- **`detect()` / `detect_all()` integration** — include narrows results, exclude removes specific encodings, both combined
- **Early-exit gating** — include filters BOM/UTF-8/ASCII results; exclude filters them too; both combined
- **Fallback/empty customization** — custom `fallback_encoding`, custom `empty_encoding`, filtered fallback emits warning and returns `None`
- **Binary detection** — unaffected by encoding filters
- **`detect_all()` behavior** — filtered candidate pool produces filtered result list; early-exit fallthrough to scoring when applicable
- **`UniversalDetector`** — all four parameters work through the streaming interface
- **CLI** — `-i`, `-x`, `--fallback-encoding`, `--empty-encoding` with comma-separated and single values
- **Error cases** — unknown encoding name raises `ValueError` for all four params
- **Performance** — default path (all `None`/defaults) shows no regression vs. current code

## Future Direction

Long-term, `include_encodings` becomes the primary filtering mechanism and
`encoding_era` becomes syntactic sugar — each era expands to the list of
encodings currently tagged with that era in the registry. Both parameters
coexist for backward compatibility in the near term.
