# Dense zlib-compressed models.bin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sparse models.bin format with a dense zlib-compressed format to cut first-detection latency from ~48ms to ~10ms.

**Architecture:** The v2 format stores 352 pre-expanded 65536-byte tables concatenated and zlib-compressed. A `"CMD2"` magic prefix distinguishes v2 from v1. At load time, `zlib.decompress()` (C-level) replaces the Python iteration loop, and `memoryview` slicing avoids copies. Norms are pre-computed at training time and stored in the header.

**Tech Stack:** Python stdlib only (zlib, struct, memoryview). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-26-dense-zlib-models-bin-design.md`

---

### Task 1: Update `serialize_models()` and `deserialize_models()` in `scripts/train.py` for v2 format

Both functions must be updated together — changing serialize alone would break existing roundtrip tests.

**Files:**
- Modify: `scripts/train.py:155-221` (`deserialize_models` and `serialize_models`)
- Modify: `tests/test_models.py` (add v2-specific tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_models.py` after the existing roundtrip tests (~line 265):

```python
def test_serialize_v2_magic(tmp_models_path: Path) -> None:
    """v2 format should start with CMD2 magic bytes."""
    original = {"test/enc": {(65, 66): 200, (0xC3, 0xA4): 150}}
    serialize_models(original, tmp_models_path)
    data = tmp_models_path.read_bytes()
    assert data[:4] == b"CMD2"


def test_roundtrip_v2_multiple_encodings(tmp_models_path: Path) -> None:
    """v2 serialize -> deserialize roundtrip with multiple encodings."""
    original = {
        "en/utf-8": {(65, 66): 200, (67, 68): 100},
        "fr/iso-8859-1": {(0xE4, 0x20): 255},
        "ja/shift_jis": {(0x82, 0xA0): 180, (0x83, 0x41): 90},
    }
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_deserialize_v2_corrupt_zlib(tmp_models_path: Path) -> None:
    """Corrupt zlib data in v2 format should raise ValueError."""
    import zlib

    name = b"test/enc"
    header = b"CMD2"
    header += struct.pack("!I", 1)
    header += struct.pack("!I", len(name)) + name
    header += struct.pack("!d", 0.0)
    tmp_models_path.write_bytes(header + b"\xff\xff\xff")  # invalid zlib
    with pytest.raises(ValueError, match="Corrupt models file"):
        deserialize_models(tmp_models_path)


def test_deserialize_v2_wrong_decompressed_size(tmp_models_path: Path) -> None:
    """v2 with decompressed size != num_models * 65536 should raise ValueError."""
    import zlib

    name = b"test/enc"
    header = b"CMD2"
    header += struct.pack("!I", 2)  # claim 2 models
    header += struct.pack("!I", len(name)) + name
    header += struct.pack("!d", 0.0)
    name2 = b"test/enc2"
    header += struct.pack("!I", len(name2)) + name2
    header += struct.pack("!d", 0.0)
    # Only 1 model's worth of data
    blob = zlib.compress(bytes(65536), 9)
    tmp_models_path.write_bytes(header + blob)
    with pytest.raises(ValueError, match="decompressed size"):
        deserialize_models(tmp_models_path)
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `uv run python -m pytest tests/test_models.py::test_serialize_v2_magic tests/test_models.py::test_roundtrip_v2_multiple_encodings -v`
Expected: FAIL

- [ ] **Step 3: Implement v2 `serialize_models()` and `deserialize_models()`**

Replace `serialize_models()` in `scripts/train.py:202-221`:

```python
def serialize_models(
    models: dict[str, dict[tuple[int, int], int]],
    output_path: Path,
) -> int:
    """Serialize all models to v2 binary format (dense + zlib). Returns file size."""
    import zlib

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_names = sorted(models.keys())

    # Build header: magic + num_models + per-model name and norm
    header = b"CMD2"
    header += struct.pack("!I", len(sorted_names))

    tables = bytearray()
    for name in sorted_names:
        bigrams = models[name]
        name_bytes = name.encode("utf-8")

        # Expand sparse dict to dense 65536-byte table and compute L2 norm
        table = bytearray(65536)
        sq_sum = 0
        for (b1, b2), weight in bigrams.items():
            table[(b1 << 8) | b2] = weight
            sq_sum += weight * weight
        norm = math.sqrt(sq_sum)

        header += struct.pack("!I", len(name_bytes)) + name_bytes
        header += struct.pack("!d", norm)
        tables.extend(table)

    compressed = zlib.compress(bytes(tables), 9)

    with output_path.open("wb") as f:
        f.write(header)
        f.write(compressed)

    return output_path.stat().st_size
```

Replace `deserialize_models()` in `scripts/train.py:155-199` with format-sniffing dispatcher and v1/v2 helpers:

```python
def deserialize_models(
    input_path: Path,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load existing models from binary format (v1 or v2)."""
    if not input_path.is_file():
        return {}

    data = input_path.read_bytes()

    if not data:
        return {}

    # Detect format version by magic bytes
    if data[:4] == b"CMD2":
        return _deserialize_v2(data)
    return _deserialize_v1(data)


def _deserialize_v1(
    data: bytes,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load models from v1 sparse binary format."""
    models: dict[str, dict[tuple[int, int], int]] = {}
    try:
        offset = 0
        (num_encodings,) = struct.unpack_from("!I", data, offset)
        offset += 4

        if num_encodings > 10_000:
            msg = f"Corrupt models file: num_encodings={num_encodings} exceeds limit"
            raise ValueError(msg)

        for _ in range(num_encodings):
            (name_len,) = struct.unpack_from("!I", data, offset)
            offset += 4
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            (num_entries,) = struct.unpack_from("!I", data, offset)
            offset += 4

            bigrams: dict[tuple[int, int], int] = {}
            for _ in range(num_entries):
                b1, b2, weight = struct.unpack_from("!BBB", data, offset)
                offset += 3
                bigrams[(b1, b2)] = weight
            models[name] = bigrams
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"Corrupt models file: {e}"
        raise ValueError(msg) from e

    if offset != len(data):
        msg = f"Corrupt models file: {len(data) - offset} trailing bytes"
        raise ValueError(msg)

    return models


def _deserialize_v2(
    data: bytes,
) -> dict[str, dict[tuple[int, int], int]]:
    """Load models from v2 dense zlib-compressed format."""
    import zlib

    try:
        offset = 4  # skip "CMD2" magic
        (num_models,) = struct.unpack_from("!I", data, offset)
        offset += 4

        if num_models > 10_000:
            msg = f"Corrupt models file: num_models={num_models} exceeds limit"
            raise ValueError(msg)

        names: list[str] = []
        for _ in range(num_models):
            (name_len,) = struct.unpack_from("!I", data, offset)
            offset += 4
            if name_len > 256:
                msg = f"Corrupt models file: name_len={name_len} exceeds 256"
                raise ValueError(msg)
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            offset += 8  # skip norm (float64), not needed for sparse dict output
            names.append(name)

        blob = zlib.decompress(data[offset:])
        expected_size = num_models * 65536
        if len(blob) != expected_size:
            msg = (
                f"Corrupt models file: decompressed size {len(blob)} "
                f"!= expected {expected_size}"
            )
            raise ValueError(msg)

        models: dict[str, dict[tuple[int, int], int]] = {}
        for i, name in enumerate(names):
            base = i * 65536
            bigrams: dict[tuple[int, int], int] = {}
            for idx in range(65536):
                weight = blob[base + idx]
                if weight > 0:
                    bigrams[(idx >> 8, idx & 0xFF)] = weight
            models[name] = bigrams

    except zlib.error as e:
        msg = f"Corrupt models file: {e}"
        raise ValueError(msg) from e
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"Corrupt models file: {e}"
        raise ValueError(msg) from e

    return models
```

Also update `test_deserialize_trailing_bytes_raises` to handle v2's different error behavior — v2 files use zlib which validates its own stream boundaries:

```python
def test_deserialize_trailing_bytes_raises(tmp_models_path: Path) -> None:
    """File with trailing bytes after valid data should raise ValueError."""
    original = {"utf-8": {(65, 66): 200}}
    serialize_models(original, tmp_models_path)
    # Append garbage bytes — zlib.decompress raises on trailing garbage
    tmp_models_path.write_bytes(tmp_models_path.read_bytes() + b"\xff\xff")
    with pytest.raises(ValueError, match="Corrupt models file"):
        deserialize_models(tmp_models_path)
```

- [ ] **Step 4: Run all roundtrip tests**

Run: `uv run python -m pytest tests/test_models.py -k "roundtrip or v2 or trailing" -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/train.py tests/test_models.py
git commit -m "feat: v2 dense zlib-compressed format for serialize/deserialize_models"
```

---

### Task 2: Update `_parse_models_bin()` in `src/chardet/models/__init__.py` for v2 format

This is the core performance change: the runtime parser that loads models for detection.

**Files:**
- Modify: `src/chardet/models/__init__.py:1-81` (add `import zlib` at top, refactor `_parse_models_bin`)
- Modify: `tests/test_models.py` (add v2-specific load tests)

- [ ] **Step 1: Write failing tests**

Add tests to `tests/test_models.py`:

```python
def test_load_models_v2_format(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 format should load via _parse_models_bin and produce correct tables."""
    import zlib

    # Build a minimal v2 file with one model
    name = b"fr/cp1252"
    table = bytearray(65536)
    table[(0xE9 << 8) | 0x20] = 200  # é followed by space
    table[(0x6C << 8) | 0x65] = 50   # "le"
    sq_sum = 200 * 200 + 50 * 50
    norm = sq_sum ** 0.5

    header = b"CMD2"
    header += struct.pack("!I", 1)  # num_models
    header += struct.pack("!I", len(name)) + name
    header += struct.pack("!d", norm)
    compressed = zlib.compress(bytes(table), 9)

    mock_models_bin(header + compressed)
    models = load_models()
    assert "fr/cp1252" in models
    assert models["fr/cp1252"][(0xE9 << 8) | 0x20] == 200
    assert models["fr/cp1252"][(0x6C << 8) | 0x65] == 50


def test_load_models_v2_corrupt_zlib(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """Corrupt zlib data in v2 should raise ValueError."""
    name = b"test/enc"
    header = b"CMD2"
    header += struct.pack("!I", 1)
    header += struct.pack("!I", len(name)) + name
    header += struct.pack("!d", 0.0)
    mock_models_bin(header + b"\xff\xff\xff")
    with pytest.raises(ValueError, match=r"corrupt models\.bin"):
        load_models()


def test_load_models_v2_wrong_decompressed_size(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 with wrong decompressed size should raise ValueError."""
    import zlib

    header = b"CMD2"
    header += struct.pack("!I", 2)  # claim 2 models
    for name in [b"a/enc1", b"b/enc2"]:
        header += struct.pack("!I", len(name)) + name
        header += struct.pack("!d", 0.0)
    # Only 1 model's worth of data
    blob = zlib.compress(bytes(65536), 9)
    mock_models_bin(header + blob)
    with pytest.raises(ValueError, match="decompressed size"):
        load_models()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_models.py::test_load_models_v2_format tests/test_models.py::test_load_models_v2_corrupt_zlib tests/test_models.py::test_load_models_v2_wrong_decompressed_size -v`
Expected: FAIL

- [ ] **Step 3: Implement v2 parsing in `_parse_models_bin()`**

First, add `import zlib` to the top-level imports in `src/chardet/models/__init__.py` (alongside `import struct`). This must be top-level, not inside the function — mypyc compiles this module and handles top-level imports more reliably, especially for exception types like `zlib.error`.

Then rename the current `_parse_models_bin` to `_parse_models_bin_v1` and add the v2 parser. Replace lines 27-81:

```python
_V2_MAGIC = b"CMD2"
_unpack_float64 = struct.Struct(">d").unpack_from


def _parse_models_bin(
    data: bytes,
) -> tuple[dict[str, bytearray | memoryview], dict[str, float]]:
    """Parse models.bin (v1 or v2) into model tables and L2 norms.

    :param data: Raw bytes of models.bin (must be non-empty).
    :returns: A ``(models, norms)`` tuple.
    :raises ValueError: If the data is corrupt or truncated.
    """
    if data[:4] == _V2_MAGIC:
        return _parse_models_bin_v2(data)
    return _parse_models_bin_v1(data)


def _parse_models_bin_v2(
    data: bytes,
) -> tuple[dict[str, memoryview], dict[str, float]]:
    """Parse v2 dense zlib-compressed format."""
    try:
        offset = 4  # skip magic
        (num_models,) = _unpack_uint32(data, offset)
        offset += 4

        if num_models > 10_000:
            msg = f"corrupt models.bin: num_models={num_models} exceeds limit"
            raise ValueError(msg)

        names: list[str] = []
        norms: dict[str, float] = {}
        for _ in range(num_models):
            (name_len,) = _unpack_uint32(data, offset)
            offset += 4
            if name_len > 256:
                msg = f"corrupt models.bin: name_len={name_len} exceeds 256"
                raise ValueError(msg)
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            (norm,) = _unpack_float64(data, offset)
            offset += 8
            names.append(name)
            norms[name] = norm

        blob = zlib.decompress(data[offset:])
        expected_size = num_models * 65536
        if len(blob) != expected_size:
            msg = (
                f"corrupt models.bin: decompressed size {len(blob)} "
                f"!= expected {expected_size}"
            )
            raise ValueError(msg)

        # memoryview slices avoid copies; the blob bytes object is kept
        # alive by the functools.cache on _load_models_data().
        mv = memoryview(blob)
        models: dict[str, memoryview] = {}
        for i, name in enumerate(names):
            start = i * 65536
            models[name] = mv[start : start + 65536]

    except zlib.error as e:
        msg = f"corrupt models.bin: {e}"
        raise ValueError(msg) from e
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"corrupt models.bin: {e}"
        raise ValueError(msg) from e

    return models, norms


def _parse_models_bin_v1(
    data: bytes,
) -> tuple[dict[str, bytearray], dict[str, float]]:
    """Parse v1 sparse format (backward compatibility)."""
    models: dict[str, bytearray] = {}
    norms: dict[str, float] = {}
    _sqrt = math.sqrt
    _unpack_u32 = _unpack_uint32
    _iter_bbb = _iter_3bytes
    try:
        offset = 0
        (num_encodings,) = _unpack_u32(data, offset)
        offset += 4

        if num_encodings > 10_000:
            msg = f"corrupt models.bin: num_encodings={num_encodings} exceeds limit"
            raise ValueError(msg)

        for _ in range(num_encodings):
            (name_len,) = _unpack_u32(data, offset)
            offset += 4
            if name_len > 256:
                msg = f"corrupt models.bin: name_len={name_len} exceeds 256"
                raise ValueError(msg)
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            (num_entries,) = _unpack_u32(data, offset)
            offset += 4
            if num_entries > 65536:
                msg = f"corrupt models.bin: num_entries={num_entries} exceeds 65536"
                raise ValueError(msg)

            table = bytearray(65536)
            sq_sum = 0
            expected_bytes = num_entries * 3
            chunk = data[offset : offset + expected_bytes]
            if len(chunk) != expected_bytes:
                msg = f"corrupt models.bin: truncated entry data for {name!r}"
                raise ValueError(msg)
            offset += expected_bytes
            for b1, b2, weight in _iter_bbb(chunk):
                table[(b1 << 8) | b2] = weight
                sq_sum += weight * weight
            models[name] = table
            norms[name] = _sqrt(sq_sum)
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"corrupt models.bin: {e}"
        raise ValueError(msg) from e

    return models, norms
```

- [ ] **Step 4: Run the v2 load tests**

Run: `uv run python -m pytest tests/test_models.py::test_load_models_v2_format tests/test_models.py::test_load_models_v2_corrupt_zlib tests/test_models.py::test_load_models_v2_wrong_decompressed_size -v`
Expected: PASS

- [ ] **Step 5: Run all model tests to verify v1 fallback still works**

Run: `uv run python -m pytest tests/test_models.py -v`
Expected: All PASS — existing tests use v1 mocked data and exercise the fallback path.

- [ ] **Step 6: Commit**

```bash
git add src/chardet/models/__init__.py tests/test_models.py
git commit -m "feat: add v2 dense zlib parser to _parse_models_bin with v1 fallback"
```

---

### Task 3: Update type annotations throughout the codebase

The model type changes from `bytearray` to `bytearray | memoryview`. This affects type signatures in `models/__init__.py` and `confusion.py`.

**Files:**
- Modify: `src/chardet/models/__init__.py` (multiple function signatures)
- Modify: `src/chardet/pipeline/confusion.py:224`

**Note:** Both modules are mypyc-compiled and must NOT use `from __future__ import annotations`. Use inline union syntax `bytearray | memoryview` directly.

- [ ] **Step 1: Update signatures in `src/chardet/models/__init__.py`**

Update these function signatures (the return type of `_parse_models_bin` was already updated in Task 2):

```python
# _load_models_data return type
def _load_models_data() -> tuple[dict[str, bytearray | memoryview], dict[str, float]]:

# load_models return type
def load_models() -> dict[str, bytearray | memoryview]:

# _build_enc_index parameter and return types
def _build_enc_index(
    models: dict[str, bytearray | memoryview],
) -> dict[str, list[tuple[str | None, bytearray | memoryview, str]]]:

# index variable type annotation inside _build_enc_index
    index: dict[str, list[tuple[str | None, bytearray | memoryview, str]]] = {}

# get_enc_index return type
def get_enc_index() -> dict[str, list[tuple[str | None, bytearray | memoryview, str]]]:

# score_with_profile model parameter
def score_with_profile(
    profile: BigramProfile, model: bytearray | memoryview, model_key: str = ""
) -> float:
```

- [ ] **Step 2: Update `_best_variant_score` in `src/chardet/pipeline/confusion.py`**

Update the `index` parameter type:

```python
def _best_variant_score(
    profile: BigramProfile,
    index: dict[str, list[tuple[str | None, bytearray | memoryview, str]]],
    enc: str,
) -> float:
```

- [ ] **Step 3: Run linting**

Run: `uv run ruff check src/chardet/models/__init__.py src/chardet/pipeline/confusion.py`
Expected: No errors.

- [ ] **Step 4: Verify mypyc compilation succeeds**

Run: `HATCH_BUILD_HOOK_ENABLE_MYPYC=true uv build`
Expected: Build succeeds. This verifies mypyc handles the `bytearray | memoryview` union type.

- [ ] **Step 5: Run the full test suite**

Run: `uv run python -m pytest -n auto`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chardet/models/__init__.py src/chardet/pipeline/confusion.py
git commit -m "chore: update model type annotations from bytearray to bytearray | memoryview"
```

---

### Task 4: Retrain models.bin in v2 format and verify

This regenerates the production `models.bin` in v2 format. Full retraining downloads data from Hugging Face and takes 30-60 minutes. If training data is already cached in `data/`, it's faster.

**Files:**
- Regenerate: `src/chardet/models/models.bin`

- [ ] **Step 1: Retrain models**

Run: `uv run python scripts/train.py`

This will write `models.bin` in v2 format (since `serialize_models` now writes v2).

- [ ] **Step 2: Verify v2 magic in the output file**

```bash
xxd -l 4 src/chardet/models/models.bin
```

Expected: `434d 4432` (ASCII `CMD2`)

- [ ] **Step 3: Run the full test suite with the new v2 models.bin**

Run: `uv run python -m pytest -n auto`
Expected: All tests pass.

- [ ] **Step 4: Run accuracy tests specifically**

Run: `uv run python -m pytest tests/test_accuracy.py -n auto`
Expected: Same pass rate as before (2499/2517).

- [ ] **Step 5: Commit the regenerated models.bin**

```bash
git add src/chardet/models/models.bin
git commit -m "feat: regenerate models.bin in v2 dense zlib format (63% smaller)"
```

---

### Task 5: End-to-end performance verification

Verify the first-detection latency improvement with `compare_detectors.py`.

**Files:** None (verification only)

- [ ] **Step 1: Run compare_detectors with mypyc and no-memory**

Run: `uv run python scripts/compare_detectors.py --mypyc --no-memory`

Expected: First-detection time drops from ~48ms to ~10ms. Accuracy unchanged at 99.3%.

- [ ] **Step 2: Run cold-start profiling**

Write `/tmp/verify_coldstart.py`:

```python
import subprocess
import sys
import tempfile
from pathlib import Path

inner = Path(tempfile.gettempdir()) / "chardet_coldstart_inner.py"
inner.write_text(
    "import time\n"
    "t = time.perf_counter_ns()\n"
    "import chardet\n"
    "chardet.detect(b'hello world')\n"
    "print(f'{(time.perf_counter_ns() - t) / 1e6:.1f}ms')\n"
)
result = subprocess.run(
    [sys.executable, str(inner)],
    capture_output=True, text=True,
)
print(result.stdout.strip())
```

Run: `uv run python /tmp/verify_coldstart.py`
Expected: Under 15ms total (import + first detect).

- [ ] **Step 3: Verify file size reduction**

```bash
ls -la src/chardet/models/models.bin
```

Expected: ~565 KiB (down from 1535 KiB).
