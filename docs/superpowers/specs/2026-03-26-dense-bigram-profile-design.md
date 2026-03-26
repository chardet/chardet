# Dense BigramProfile with tracked nonzero indices

**Goal:** Speed up statistical scoring by 43% (1767us → 1008us per detection
under mypyc) by replacing the dict-based BigramProfile with a dense
list + tracked nonzero index.

## Problem

`BigramProfile.__init__()` iterates 16K bytes, accumulating weighted bigram
frequencies into a `dict[int, int]`. Under mypyc, the dict operations
(hash, lookup, resize) account for most of the loop cost. The profile is
built once per detection and scored against ~244 model variants.

## Solution

Replace the `dict[int, int]` with a `list[int]` of length 65536 (one slot
per possible bigram index). Track which indices are non-zero in a parallel
`list[int]` during construction. This avoids all dict hashing and lets
mypyc compile the `freq[idx] += w` as a direct indexed store.

### Benchmarked results (mypyc-compiled, 16KB input)

| Metric | Current (dict) | Dense + tracked |
|---|---|---|
| Build phase | 1428us | 548us (**62% faster**) |
| Full build + score (244 variants) | 1767us | 1008us (**43% faster**) |

At small sizes (<1KB), the dense approach is ~28% slower due to the
`[0] * 65536` allocation. But files <1KB rarely reach statistical scoring
— they're typically resolved by earlier pipeline stages (ASCII, UTF-8, BOM).

## Changes

### `src/chardet/models/__init__.py`

**BigramProfile class:**

Change `__slots__` to replace `weighted_freq` with `freq` (dense list) and
`nonzero` (index list):

```python
__slots__ = ("freq", "input_norm", "nonzero", "weight_sum")
```

Update `__init__`:
- `self.freq: list[int] = [0] * 65536`
- `self.nonzero: list[int] = []` — indices appended on first occurrence
- Loop: `if freq[idx] == 0: nonzero.append(idx)` before `freq[idx] += w`
- Norm: iterate `nonzero` instead of `freq.values()`

Update `from_weighted_freq()` to accept `dict[int, int]` and populate the
dense list + nonzero index.

**`score_with_profile()`:**

Change iteration from `for idx, wcount in profile.weighted_freq.items()`
to `for idx in profile.nonzero` with `profile.freq[idx]` lookup.

**`score_best_language()`:** No changes needed (calls `score_with_profile`).

### `src/chardet/pipeline/confusion.py`

No changes — `_best_variant_score()` calls `score_with_profile()` which
handles the new structure internally.

### `src/chardet/pipeline/orchestrator.py`

**`_fill_metadata()`** — Check if it accesses `weighted_freq` directly. If
so, update to use `freq` + `nonzero`.

## Testing

- Existing unit tests and accuracy tests validate correctness end-to-end.
- Update `test_bigram_profile_*` tests for the new attribute names.
- Update `test_score_with_profile_*` tests if they construct profiles manually.
- Run `compare_detectors.py --mypyc --no-memory` to confirm speedup.

## Out of scope

- Changing the IDF format or model format.
- Optimizing the validity filtering stage.
- Pure Python performance (this optimization specifically targets mypyc).
