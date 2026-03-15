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

Two new keyword-only parameters on `detect()`, `detect_all()`, and
`UniversalDetector.__init__()`:

```python
include_encodings: Iterable[str] | None = None
exclude_encodings: Iterable[str] | None = None
```

- **`include_encodings`** — whitelist. Only these encodings are considered as
  candidates in the statistical/validity pipeline stages. `None` (default)
  means no restriction beyond `encoding_era`.
- **`exclude_encodings`** — blacklist. These encodings are removed from
  candidates *and* suppressed in early-exit stages. `None` (default) means
  no exclusions.

Both accept any `Iterable[str]`. Names are resolved through
`lookup_encoding()` so aliases and arbitrary casing work (e.g.,
`"windows-1252"`, `"cp1252"`, `"Windows-1252"` all resolve to `"cp1252"`).

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

Called at the three public entry points (`detect`, `detect_all`,
`UniversalDetector.__init__`) so validation happens once, early.

### Filter Semantics

**Intersection:** `encoding_era`, `include_encodings`, and
`exclude_encodings` are all applied. Era narrows the full registry,
`include_encodings` further narrows within that, and `exclude_encodings`
removes from whatever remains.

Example: `encoding_era=MODERN_WEB, include_encodings={"cp1252", "iso8859-1"}`
returns only `cp1252` because `iso8859-1` is `LEGACY_ISO`.

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
`get_candidates()`. These are gated against `exclude_encodings` **only** —
not `include_encodings`.

Rationale: a BOM or structural detection is authoritative evidence.
`include_encodings` narrows the statistical candidate pool, but a BOM is
definitive. Excluding, however, is a deliberate "I know this encoding is
wrong for my data" signal that should be respected everywhere.

In `_run_pipeline_core()`, before returning any early-exit result:

```python
if exclude_encodings and result.encoding in exclude_encodings:
    pass  # fall through to next stage
```

This applies to all early-exit stages: BOM (1a), UTF-16/32 patterns (1a+),
escape sequences (1b), markup charset (1c), ASCII (1d), UTF-8 (1e).

### Fallback When Everything Is Filtered

If all candidates are eliminated (by era + include + exclude), or all
early-exit results are excluded and no statistical candidates remain, the
pipeline returns:

```python
DetectionResult(encoding=None, confidence=0.0, language=None)
```

This matches the existing binary-detection result format.

### Parameter Flow

```
detect(include_encodings=["utf-8", "cp1252"], exclude_encodings=["euc-kr"])
  │
  ├─ normalize_encodings(["utf-8", "cp1252"]) → frozenset({"utf-8", "cp1252"})
  ├─ normalize_encodings(["euc-kr"])           → frozenset({"euc_kr"})
  │
  └─ run_pipeline(data, era, include_encodings=..., exclude_encodings=...)
       │
       ├─ Early-exit stages: gated against exclude_encodings only
       │
       └─ get_candidates(era, include_encodings, exclude_encodings)
            ├─ era filter:     enc.era & era
            ├─ include filter: enc.name in include_encodings
            └─ exclude filter: enc.name not in exclude_encodings
```

### CLI

Two new flags in `chardetect`:

```
-i, --include-encodings   Comma-separated list of encodings to consider
-x, --exclude-encodings   Comma-separated list of encodings to exclude
```

Examples:

```bash
chardetect -i utf-8,cp1252,cp1251 file.txt
chardetect -x euc-kr,big5 file.txt
chardetect -i utf-8,cp1252 -x cp1252 file.txt  # effectively only utf-8
```

Parsed by splitting on `,` and stripping whitespace. Passed through to
`chardet.detect()`.

### `UniversalDetector`

Constructor gains the same two parameters:

```python
def __init__(
    self,
    ...,
    include_encodings: Iterable[str] | None = None,
    exclude_encodings: Iterable[str] | None = None,
) -> None:
```

Normalized to frozensets in `__init__`, stored as instance attributes, passed
to `run_pipeline()` in `close()`.

## Files Changed

| File | Change |
|------|--------|
| `src/chardet/registry.py` | Add `normalize_encodings()`, extend `get_candidates()` signature |
| `src/chardet/pipeline/orchestrator.py` | Thread `include_encodings`/`exclude_encodings` through `run_pipeline()` and `_run_pipeline_core()`, add early-exit gating, handle empty-candidate fallback |
| `src/chardet/__init__.py` | Add params to `detect()` and `detect_all()`, call `normalize_encodings()` |
| `src/chardet/detector.py` | Add params to `UniversalDetector.__init__()`, store and pass through |
| `src/chardet/cli.py` | Add `--include-encodings`/`-i` and `--exclude-encodings`/`-x` flags |
| `tests/test_api.py` | Unit and integration tests |

## Testing

- **`normalize_encodings()`** — valid names, aliases, unknown names raise `ValueError`
- **`get_candidates()`** — include-only, exclude-only, both, interaction with era, empty result
- **`detect()` / `detect_all()` integration** — include narrows results, exclude removes specific encodings, both combined
- **Early-exit exclusion** — exclude UTF-8 when data has UTF-8 BOM (falls through), exclude ASCII on pure-ASCII data
- **Fallback** — everything filtered out returns `encoding=None, confidence=0.0`
- **`UniversalDetector`** — same parameters work through the streaming interface
- **CLI** — `--include-encodings`, `--exclude-encodings`, `-i`, `-x` with comma-separated values
- **Error cases** — unknown encoding name raises `ValueError`
- **Performance** — default path (both `None`) shows no regression vs. current code

## Future Direction

Long-term, `include_encodings` becomes the primary filtering mechanism and
`encoding_era` becomes syntactic sugar — each era expands to the list of
encodings currently tagged with that era in the registry. Both parameters
coexist for backward compatibility in the near term.
