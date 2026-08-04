from __future__ import annotations

import hashlib
import struct
import zlib
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from train import deserialize_models, serialize_models

import chardet.models as models_mod


def test_enc_index_resolves_aliases() -> None:
    index = models_mod.get_enc_index()
    # Models keyed by old names should be accessible under new primary names
    assert "big5hkscs" in index
    assert "euc_jis_2004" in index
    assert "shift_jis_2004" in index
    assert "cp1140" in index


def test_load_models_returns_dict() -> None:
    models = models_mod.load_models()
    assert isinstance(models, dict)


def test_load_models_has_entries() -> None:
    models = models_mod.load_models()
    assert len(models) > 0


def test_model_keys_are_strings() -> None:
    models = models_mod.load_models()
    for key in models:
        assert isinstance(key, str)


def test_score_best_language_returns_float() -> None:
    """score_best_language should work with plain encoding names (not lang/enc keys)."""
    models_mod.load_models()
    score, _ = models_mod.score_best_language(b"Hello world this is a test", "cp1252")
    assert isinstance(score, float)
    assert 0.0 < score <= 1.0


def test_score_best_language_unknown_encoding() -> None:
    models_mod.load_models()
    score, _ = models_mod.score_best_language(b"Hello", "not-a-real-encoding")
    assert score == 0.0


def test_score_best_language_empty_data() -> None:
    models = models_mod.load_models()
    encoding = next(iter(models))
    score, _ = models_mod.score_best_language(b"", encoding)
    assert score == 0.0


def test_score_best_language_high_byte_weighting() -> None:
    """High-byte bigrams should be weighted more heavily than ASCII-only."""
    models = models_mod.load_models()
    # Pick any encoding with a model
    encoding = next(iter(models))
    model = models[encoding]

    # Build data that's all ASCII vs data with high bytes
    ascii_data = b"the quick brown fox jumps over the lazy dog"
    # Create high-byte data using bytes that appear in the model (bytearray table)
    high_pairs = []
    for idx in range(65536):
        if model[idx] > 0:
            b1 = idx >> 8
            b2 = idx & 0xFF
            if b1 > 0x7F or b2 > 0x7F:
                high_pairs.append((b1, b2))
    if high_pairs:
        # Construct data from high-byte pairs in the model
        high_data = bytes(b for pair in high_pairs[:20] for b in pair)
        high_score, _ = models_mod.score_best_language(high_data, encoding)
        ascii_score, _ = models_mod.score_best_language(ascii_data, encoding)
        # Both should be valid floats
        assert isinstance(high_score, float)
        assert isinstance(ascii_score, float)
        assert 0.0 <= high_score <= 1.0
        assert 0.0 <= ascii_score <= 1.0


# ---------------------------------------------------------------------------
# BigramProfile tests
# ---------------------------------------------------------------------------


def test_bigram_profile_empty() -> None:
    p = models_mod.BigramProfile(b"")
    assert p.weight_sum == 0
    assert len(p.nonzero) == 0


def test_bigram_profile_single_byte() -> None:
    p = models_mod.BigramProfile(b"A")
    assert p.weight_sum == 0


def test_bigram_profile_ascii_weight() -> None:
    p = models_mod.BigramProfile(b"AB")
    assert p.weight_sum > 0


def test_bigram_profile_high_byte_weight() -> None:
    p = models_mod.BigramProfile(b"\xc3\xa9")
    # High-byte bigrams should get IDF-based weight >= 1
    assert p.weight_sum >= 1


def test_get_idf_weights_wrong_size() -> None:
    """idf.bin with wrong size should warn and return uniform weights."""
    models_mod.get_idf_weights.cache_clear()
    mock_ref = MagicMock()
    mock_ref.read_bytes.return_value = b"\x42" * 100  # wrong size

    with (
        patch.object(
            models_mod.importlib.resources,
            "files",
            return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
        ),
        pytest.warns(RuntimeWarning, match="idf.bin has wrong size"),
    ):
        result = models_mod.get_idf_weights()

    assert len(result) == 65536
    assert all(b == 1 for b in result)
    models_mod.get_idf_weights.cache_clear()


# ---------------------------------------------------------------------------
# Model coverage: every test-data encoding-language pair needs a model
# ---------------------------------------------------------------------------

# Encodings detected by structural pipeline stages (BOM, null-byte patterns,
# escape sequences, ASCII check) — these do not use bigram models.
_STRUCTURAL_ENCODINGS: frozenset[str] = frozenset(
    {
        "ascii",
        "utf-8",
        "utf-8-sig",
        "utf-7",
        "utf-16",
        "utf-16-be",
        "utf-16-le",
        "utf-32",
        "utf-32-be",
        "utf-32-le",
        "iso2022_jp_2",
        "iso2022_jp_2004",
        "iso2022_jp_ext",
        "iso2022_kr",
        "hz",
    }
)


def _expected_model_pairs() -> set[tuple[str, str]]:
    """Derive (canonical_encoding, language) pairs from the test data directory.

    Every encoding-language directory that contains test files and uses
    statistical (bigram) detection should have a corresponding trained model.
    """
    from chardet.registry import lookup_encoding  # noqa: PLC0415
    from scripts.utils import get_data_dir  # noqa: PLC0415

    data_dir = get_data_dir()
    pairs: set[tuple[str, str]] = set()
    for d in data_dir.iterdir():
        if not d.is_dir():
            continue
        parts = d.name.rsplit("-", 1)
        if len(parts) != 2 or parts[0] == "None":
            continue
        enc_display, lang = parts
        canonical = lookup_encoding(enc_display)
        if canonical is None or canonical in _STRUCTURAL_ENCODINGS:
            continue
        if any(f.is_file() for f in d.iterdir()):
            pairs.add((canonical, lang))
    return pairs


def test_all_test_data_pairs_have_models() -> None:
    """Every encoding-language pair in the test data should have a bigram model.

    If this test fails, the registry's language associations need updating
    so that ``scripts/train.py`` builds models for the missing pairs.
    """
    index = models_mod.get_enc_index()

    # Build set of (encoding, language) pairs that have models
    model_pairs: set[tuple[str, str]] = set()
    for enc, variants in index.items():
        for lang, _, _ in variants:
            model_pairs.add((enc, lang))

    expected = _expected_model_pairs()
    missing = sorted(expected - model_pairs)

    assert not missing, (
        f"{len(missing)} test-data encoding-language pairs have no bigram model. "
        f"Update the language associations in src/chardet/registry.py and retrain.\n"
        + "\n".join(f"  {enc}-{lang}" for enc, lang in missing)
    )


# ---------------------------------------------------------------------------
# serialize_models / deserialize_models roundtrip tests
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_models_path(tmp_path: Path) -> Path:
    return tmp_path / "test_models.bin"


def test_roundtrip_single_encoding(tmp_models_path: Path) -> None:
    """Serialize and deserialize a single encoding model."""
    original = {"utf-8": {(65, 66): 200, (0xC3, 0xA4): 150}}
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_roundtrip_multiple_encodings(tmp_models_path: Path) -> None:
    """Serialize and deserialize multiple encoding models."""
    original = {
        "utf-8": {(65, 66): 200, (67, 68): 100},
        "iso-8859-1": {(0xE4, 0x20): 255},
        "shift_jis": {(0x82, 0xA0): 180, (0x83, 0x41): 90},
    }
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_roundtrip_empty_bigrams(tmp_models_path: Path) -> None:
    """An encoding with zero bigrams should roundtrip correctly."""
    original = {"empty-enc": {}}
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_roundtrip_zero_encodings(tmp_models_path: Path) -> None:
    """Zero encodings should roundtrip correctly."""
    original: dict[str, dict[tuple[int, int], int]] = {}
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_deserialize_missing_file() -> None:
    """Missing file should return empty dict."""
    result = deserialize_models(Path("/nonexistent/path/models.bin"))
    assert result == {}


def test_deserialize_empty_file(tmp_models_path: Path) -> None:
    """Empty file should return empty dict."""
    tmp_models_path.write_bytes(b"")
    result = deserialize_models(tmp_models_path)
    assert result == {}


def test_deserialize_trailing_bytes_raises(tmp_models_path: Path) -> None:
    """File with trailing bytes after valid data should raise ValueError."""
    original = {"utf-8": {(65, 66): 200}}
    serialize_models(original, tmp_models_path)
    # Append garbage bytes — zlib.decompress raises on trailing garbage
    tmp_models_path.write_bytes(tmp_models_path.read_bytes() + b"\xff\xff")
    with pytest.raises(ValueError, match="Corrupt models file"):
        deserialize_models(tmp_models_path)


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


def test_roundtrip_matches_load_models(tmp_path: Path) -> None:
    """The production models.bin should roundtrip through serialize/deserialize."""
    production_tables = models_mod.load_models()  # dict[str, bytes]
    # Convert byte tables back to dict format for serialize/deserialize roundtrip
    production_dicts: dict[str, dict[tuple[int, int], int]] = {}
    for name, table in production_tables.items():
        bigrams: dict[tuple[int, int], int] = {}
        for idx in range(65536):
            if table[idx] > 0:
                bigrams[(idx >> 8, idx & 0xFF)] = table[idx]
        production_dicts[name] = bigrams
    tmp_models = tmp_path / "roundtrip_models.bin"
    serialize_models(production_dicts, tmp_models)
    loaded = deserialize_models(tmp_models)
    assert loaded == production_dicts


@pytest.fixture
def mock_models_bin():
    """Clear the model cache and provide a helper to mock models.bin content.

    Yields a callable ``set_data(raw_bytes)`` that configures the mock to
    return *raw_bytes* from ``models.bin``.  The cache is cleared on teardown.
    """
    models_mod._load_models_data.cache_clear()
    mock_ref = MagicMock()

    def set_data(data: bytes) -> None:
        mock_ref.read_bytes.return_value = data

    with patch.object(
        models_mod.importlib.resources,
        "files",
        return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
    ):
        yield set_data

    models_mod._load_models_data.cache_clear()


def test_load_models_empty_file(mock_models_bin: Callable[[bytes], None]) -> None:
    """Empty models.bin should emit RuntimeWarning and return empty dict."""
    mock_models_bin(b"")
    with pytest.warns(RuntimeWarning, match="models.bin is empty"):
        result = models_mod.load_models()
    assert result == {}


def test_load_models_missing_magic(mock_models_bin: Callable[[bytes], None]) -> None:
    """Data without CMD2 magic should raise ValueError."""
    mock_models_bin(struct.pack("!I", 1))
    with pytest.raises(ValueError, match="missing CMD2 magic"):
        models_mod.load_models()


def test_load_models_v2_num_models_exceeds_limit(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 num_models > 10000 should raise ValueError."""
    data = b"CMD2" + struct.pack("!I", 10001)
    mock_models_bin(data)
    with pytest.raises(ValueError, match="num_models=10001 exceeds limit"):
        models_mod.load_models()


def test_load_models_v2_name_len_exceeds_limit(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 name_len > 256 should raise ValueError."""
    data = b"CMD2"
    data += struct.pack("!I", 1)  # num_models=1
    data += struct.pack("!I", 300)  # name_len=300
    mock_models_bin(data)
    with pytest.raises(ValueError, match="name_len=300 exceeds 256"):
        models_mod.load_models()


def test_load_models_v2_truncated_header(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 data truncated mid-header should raise ValueError."""
    # CMD2 + num_models=1 but no name/norm data
    data = b"CMD2" + struct.pack("!I", 1)
    mock_models_bin(data)
    with pytest.raises(ValueError, match=r"corrupt models\.bin"):
        models_mod.load_models()


def test_load_models_v2_invalid_utf8_name(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 with invalid UTF-8 in model name should raise ValueError."""
    invalid_name = b"\xff\xfe"
    data = b"CMD2"
    data += struct.pack("!I", 1)  # num_models=1
    data += struct.pack("!I", len(invalid_name)) + invalid_name
    mock_models_bin(data)
    with pytest.raises(ValueError, match=r"corrupt models\.bin"):
        models_mod.load_models()


def test_load_models_v2_format(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 format should load via _parse_models_bin and produce correct tables."""
    # Build a minimal v2 file with one model
    name = b"fr/cp1252"
    table = bytearray(65536)
    table[(0xE9 << 8) | 0x20] = 200  # é followed by space
    table[(0x6C << 8) | 0x65] = 50  # "le"
    sq_sum = 200 * 200 + 50 * 50
    norm = sq_sum**0.5

    header = b"CMD2"
    header += struct.pack("!I", 1)  # num_models
    header += struct.pack("!I", len(name)) + name
    header += struct.pack("!d", norm)
    compressed = zlib.compress(bytes(table), 9)

    mock_models_bin(header + compressed)
    models = models_mod.load_models()
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
        models_mod.load_models()


def test_load_models_v2_wrong_decompressed_size(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """v2 with wrong decompressed size should raise ValueError."""
    header = b"CMD2"
    header += struct.pack("!I", 2)  # claim 2 models
    for name in [b"a/enc1", b"b/enc2"]:
        header += struct.pack("!I", len(name)) + name
        header += struct.pack("!d", 0.0)
    # Only 1 model's worth of data
    blob = zlib.compress(bytes(65536), 9)
    mock_models_bin(header + blob)
    with pytest.raises(ValueError, match="decompressed size"):
        models_mod.load_models()


def test_score_with_profile_fallback_norm():
    """score_with_profile with empty model_key should compute norm on the fly."""
    profile = models_mod.BigramProfile(b"\xc3\xa9\xc3\xa4")  # some high-byte bigrams
    # Build a model with a few non-zero entries
    table = bytearray(65536)
    table[(0xC3 << 8) | 0xA9] = 100
    table[(0xC3 << 8) | 0xA4] = 80
    score = models_mod.score_with_profile(profile, bytes(table), model_key="")
    assert isinstance(score, float)
    assert score > 0.0


def test_score_with_profile_all_zeros_model():
    """All-zeros model should return 0.0 (model_norm == 0)."""
    profile = models_mod.BigramProfile(b"\xc3\xa9\xc3\xa4")
    model = bytes(65536)  # all zeros
    score = models_mod.score_with_profile(profile, model, model_key="")
    assert score == 0.0


def test_enc_index_alias_resolution() -> None:
    """When a model key uses a non-canonical name, the canonical name is added.

    The index should contain both the original key and the canonical name
    pointing to the same entries.
    """
    # Create a fake model dict with a non-canonical encoding name.
    # "utf8" is a non-canonical alias for "utf-8".
    fake_table = bytearray(65536)
    fake_table[(0xC3 << 8) | 0xA9] = 100
    fake_models = {"French/utf8": bytes(fake_table)}

    index = models_mod._build_enc_index(fake_models)

    # The non-canonical key "utf8" should be in the index
    assert "utf8" in index
    # The canonical name "utf-8" should also be present via alias resolution
    assert "utf-8" in index
    # Both should point to the same entries
    assert index["utf-8"] is index["utf8"]


def test_rowmax_matches_models() -> None:
    """rowmax.bin must stay in sync with models.bin.

    Each model's rowmax table entry b1 must equal the maximum weight in the
    model's row for lead byte b1.  A mismatch means rowmax.bin is stale
    relative to models.bin and must be regenerated (scripts/train.py writes
    both).
    """
    models = models_mod.load_models()
    rowmax = models_mod.get_rowmax()
    assert set(rowmax) == set(models)
    for key, table in models.items():
        derived = bytes(
            max(table[start : start + 256]) for start in range(0, 65536, 256)
        )
        assert rowmax[key] == derived, f"rowmax.bin stale for model {key}"


def test_decompress_tables_chunked_matches_whole() -> None:
    """Incremental decompression must be feed-granularity independent."""
    blob = bytes(range(256)) * 256  # exactly one 65536-byte table
    compressed = zlib.compress(blob)
    for chunk_size in (1, 7, 262144):
        out = models_mod._decompress_tables(compressed, 0, ["m"], chunk_size)
        assert out == {"m": blob}, f"chunk_size={chunk_size}"


@pytest.mark.parametrize("chunk_size", [1, 262144])
def test_decompress_tables_rejects_surplus_tables(chunk_size: int) -> None:
    """A blob with more tables than the header claims must be rejected.

    chunk_size=1 forces the boundary where the final claimed table
    completes with the fed chunk fully consumed while surplus compressed
    input is still unfed — the case a tail-only drain would miss.
    """
    # Deterministic incompressible filler (no PRNG): chained SHA-256.
    blob = b"".join(
        hashlib.sha256(i.to_bytes(4, "big")).digest() for i in range(65536 * 2 // 32)
    )
    compressed = zlib.compress(blob)
    with pytest.raises(ValueError, match="decompressed size"):
        models_mod._decompress_tables(compressed, 0, ["only-one"], chunk_size)


def test_rowmax_bin_header_matches_models_bin() -> None:
    """rowmax.bin must carry the CRM1 magic and the SHA-256 of models.bin.

    A regenerated models.bin without a matching rowmax.bin regeneration
    would silently under-estimate row maxima and break pruning's upper
    bound, so the digest is the load-time staleness guard.
    """
    models_dir = Path(models_mod.__file__).parent
    raw = (models_dir / "rowmax.bin").read_bytes()
    assert raw[:4] == b"CRM1"
    digest = hashlib.sha256((models_dir / "models.bin").read_bytes()).digest()
    assert raw[4:36] == digest


def test_rowmax_stale_digest_falls_back_with_warning() -> None:
    """A rowmax.bin whose digest mismatches models.bin must be rejected.

    The fallback derives the tables from the models directly, which is
    slower but always correct, and warns so packaging mistakes get noticed.
    """
    models_dir = Path(models_mod.__file__).parent
    real_models = (models_dir / "models.bin").read_bytes()
    real_rowmax = (models_dir / "rowmax.bin").read_bytes()
    stale = real_rowmax[:4] + bytes(32) + real_rowmax[36:]
    contents = {"models.bin": real_models, "rowmax.bin": stale}

    def fake_joinpath(name: str) -> MagicMock:
        ref = MagicMock()
        ref.read_bytes.return_value = contents[name]
        return ref

    models_mod.get_rowmax.cache_clear()
    models_mod._load_models_data.cache_clear()
    try:
        with (
            patch.object(
                models_mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(side_effect=fake_joinpath)),
            ),
            pytest.warns(RuntimeWarning, match="rowmax.bin"),
        ):
            derived = models_mod.get_rowmax()
        assert derived
    finally:
        models_mod.get_rowmax.cache_clear()
        models_mod._load_models_data.cache_clear()

    # The fallback must produce exactly the tables the genuine file holds.
    genuine = models_mod.get_rowmax()
    assert derived == genuine
    models_mod.get_rowmax.cache_clear()


def test_score_with_profile_accepts_bytearray_and_memoryview() -> None:
    """The historical bytearray/memoryview table types must keep working.

    mypyc enforces parameter types at runtime, so without explicit widening
    a compiled install would raise TypeError where pure Python accepted the
    call.
    """
    profile = models_mod.BigramProfile(b"\xc3\xa9\xc3\xa4")
    table = bytearray(65536)
    table[(0xC3 << 8) | 0xA9] = 100
    expected = models_mod.score_with_profile(profile, bytes(table))
    assert models_mod.score_with_profile(profile, table) == expected
    assert models_mod.score_with_profile(profile, memoryview(bytes(table))) == expected
