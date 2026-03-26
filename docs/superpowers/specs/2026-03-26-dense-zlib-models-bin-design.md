# Dense zlib-compressed models.bin

**Goal:** Reduce first-detection latency from ~48ms to ~10ms by replacing the
sparse binary model format with a pre-expanded, zlib-compressed dense format.

## Problem

The current `models.bin` stores 352 bigram models in a sparse format: each
model lists only its non-zero `(b1, b2, weight)` triples (521K total entries).
At load time, `_parse_models_bin()` iterates every entry in Python, writing
each into a fresh `bytearray(65536)` table and accumulating the L2 norm.

This Python-level loop takes **~44ms** — the dominant cost in first-detection
latency. Everything else (disk I/O, IDF load, index build) totals <3ms.

## Solution

Store models pre-expanded as dense 65536-byte tables, then zlib-compress the
concatenated block. At load time: decompress (in C), slice via `memoryview` —
no Python iteration.

Norms are pre-computed at training time and stored in the header, eliminating
L2 norm computation at load time.

### Benchmarked results

| Metric | Current sparse | Dense + zlib-9 |
|---|---|---|
| File size | 1535 KiB | ~565 KiB |
| Parse time | ~44ms | ~6ms |
| Scoring speed | identical | identical |

The file is **63% smaller** and **7× faster to parse**.

## New binary format (v2)

```
[magic: 4 bytes "CMD2"]
[num_models: uint32 big-endian]
For each model:
    [name_len: uint32 big-endian]
    [name: UTF-8 bytes]
    [norm: float64 big-endian]
[compressed_tables: zlib-compressed blob, remainder of file]
```

The compressed blob contains `num_models × 65536` bytes: dense tables
concatenated in the same order as the header entries.

The `"CMD2"` magic distinguishes v2 from v1 (which starts with a uint32
model count — never a valid ASCII string).

After decompression, validate that `len(blob) == num_models * 65536`.
Catch `zlib.error` alongside existing `struct.error` / `UnicodeDecodeError`
handling.

## Changes

### `scripts/train.py` — `serialize_models()`

Replace the current sparse writer with:

1. Sort model names.
2. For each model, expand the sparse `{(b1,b2): weight}` dict to a
   65536-byte `bytes` table, and compute the L2 norm.
3. Concatenate all tables into one buffer.
4. zlib-compress the buffer at level 9.
5. Write the v2 header (magic, model count, names + norms), then the
   compressed blob.

### `scripts/train.py` — `deserialize_models()`

Update to handle both v1 and v2 formats (magic-byte sniffing). The
incremental retraining path (`--encodings`) loads existing models via
`deserialize_models()`, so it must read v2 files.

### `src/chardet/models/__init__.py` — `_parse_models_bin()`

Replace the current sparse parser with:

1. Check for `"CMD2"` magic. If absent, fall back to the current v1 parser
   (for development workflows where someone has an old `models.bin`).
2. Read model names and norms from the header.
3. `zlib.decompress()` the compressed blob.
4. Validate decompressed size equals `num_models * 65536`.
5. `memoryview`-slice the decompressed buffer into per-model views.
6. Return `dict[str, memoryview]` for models and `dict[str, float]` for norms.

The decompressed `bytes` object is stored as a module-level cached reference
via `_load_models_data()` (decorated with `@functools.cache`), ensuring all
`memoryview` slices remain valid for the process lifetime.

### Type annotation updates

The v2 parser returns `memoryview` slices; the v1 fallback returns
`bytearray`. Use `bytearray | memoryview` in model-related signatures:

- `_parse_models_bin()` return type
- `_load_models_data()` return type
- `load_models()` return type
- `_build_enc_index()` parameter and return types
- `get_enc_index()` return type
- `score_with_profile()` `model` parameter
- `_best_variant_score()` in `confusion.py` — both the `model` parameter
  (via the tuple type) and the `index` parameter type

All three types (`bytearray`, `bytes`, `memoryview`) support integer indexing
identically, so no scoring logic changes are needed. Benchmarked: no speed
difference.

### Backward compatibility

The v1 fallback in `_parse_models_bin()` ensures that:
- Existing installed packages continue to work until retrained.
- Development branches with stale `models.bin` still load.

The fallback can be removed in a future release.

## Testing

- Existing unit tests and accuracy tests validate correctness end-to-end.
- Add a focused test that round-trips: serialize → load → verify model keys
  match, all 65536 bytes per model are identical, and norms match to float
  precision.
- Test the v1 fallback path explicitly.
- Run `compare_detectors.py --mypyc` to confirm accuracy is unchanged and
  first-detection time drops.

## Out of scope

- Changing the IDF format (`idf.bin` stays as-is).
- Changing the confusion data format.
- Lazy/on-demand loading of individual models (not needed at ~6ms total).
- mypyc compilation changes (memoryview indexing works fine under mypyc).
