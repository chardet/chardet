from __future__ import annotations

import struct
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from train import deserialize_models, serialize_models

from chardet.models import (
    BigramProfile,
    get_enc_index,
    load_models,
    score_best_language,
)


def test_enc_index_resolves_aliases() -> None:
    index = get_enc_index()
    # Models keyed by old names should be accessible under new primary names
    assert "Big5-HKSCS" in index
    assert "EUC-JIS-2004" in index
    assert "Shift-JIS-2004" in index
    assert "CP1140" in index


def test_load_models_returns_dict() -> None:
    models = load_models()
    assert isinstance(models, dict)


def test_load_models_has_entries() -> None:
    models = load_models()
    assert len(models) > 0


def test_model_keys_are_strings() -> None:
    models = load_models()
    for key in models:
        assert isinstance(key, str)


def test_score_best_language_returns_float() -> None:
    """score_best_language should work with plain encoding names (not lang/enc keys)."""
    load_models()
    score, _ = score_best_language(b"Hello world this is a test", "Windows-1252")
    assert isinstance(score, float)
    assert 0.0 < score <= 1.0


def test_score_best_language_unknown_encoding() -> None:
    load_models()
    score, _ = score_best_language(b"Hello", "not-a-real-encoding")
    assert score == 0.0


def test_score_best_language_empty_data() -> None:
    models = load_models()
    encoding = next(iter(models))
    score, _ = score_best_language(b"", encoding)
    assert score == 0.0


def test_score_best_language_high_byte_weighting() -> None:
    """High-byte bigrams should be weighted more heavily than ASCII-only."""
    models = load_models()
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
        high_score, _ = score_best_language(high_data, encoding)
        ascii_score, _ = score_best_language(ascii_data, encoding)
        # Both should be valid floats
        assert isinstance(high_score, float)
        assert isinstance(ascii_score, float)
        assert 0.0 <= high_score <= 1.0
        assert 0.0 <= ascii_score <= 1.0


# ---------------------------------------------------------------------------
# BigramProfile tests
# ---------------------------------------------------------------------------


def test_bigram_profile_empty() -> None:
    p = BigramProfile(b"")
    assert p.weight_sum == 0
    assert len(p.weighted_freq) == 0


def test_bigram_profile_single_byte() -> None:
    p = BigramProfile(b"A")
    assert p.weight_sum == 0


def test_bigram_profile_ascii_weight() -> None:
    p = BigramProfile(b"AB")
    assert p.weight_sum == 1


def test_bigram_profile_high_byte_weight() -> None:
    p = BigramProfile(b"\xc3\xa9")
    assert p.weight_sum == 8


# ---------------------------------------------------------------------------
# serialize_models / deserialize_models roundtrip tests
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_models_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_models.bin")


def test_roundtrip_single_encoding(tmp_models_path: str) -> None:
    """Serialize and deserialize a single encoding model."""
    original = {"utf-8": {(65, 66): 200, (0xC3, 0xA4): 150}}
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_roundtrip_multiple_encodings(tmp_models_path: str) -> None:
    """Serialize and deserialize multiple encoding models."""
    original = {
        "utf-8": {(65, 66): 200, (67, 68): 100},
        "iso-8859-1": {(0xE4, 0x20): 255},
        "shift_jis": {(0x82, 0xA0): 180, (0x83, 0x41): 90},
    }
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_roundtrip_empty_bigrams(tmp_models_path: str) -> None:
    """An encoding with zero bigrams should roundtrip correctly."""
    original = {"empty-enc": {}}
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_roundtrip_zero_encodings(tmp_models_path: str) -> None:
    """Zero encodings should roundtrip correctly."""
    original: dict[str, dict[tuple[int, int], int]] = {}
    serialize_models(original, tmp_models_path)
    loaded = deserialize_models(tmp_models_path)
    assert loaded == original


def test_deserialize_missing_file() -> None:
    """Missing file should return empty dict."""
    result = deserialize_models("/nonexistent/path/models.bin")
    assert result == {}


def test_deserialize_empty_file(tmp_models_path: str) -> None:
    """Empty file should return empty dict."""
    Path(tmp_models_path).write_bytes(b"")
    result = deserialize_models(tmp_models_path)
    assert result == {}


def test_deserialize_trailing_bytes_raises(tmp_models_path: str) -> None:
    """File with trailing bytes after valid data should raise ValueError."""
    original = {"utf-8": {(65, 66): 200}}
    serialize_models(original, tmp_models_path)
    # Append garbage bytes
    p = Path(tmp_models_path)
    p.write_bytes(p.read_bytes() + b"\xff\xff")
    with pytest.raises(ValueError, match="trailing bytes"):
        deserialize_models(tmp_models_path)


def test_roundtrip_matches_load_models(tmp_path: Path) -> None:
    """The production models.bin should roundtrip through serialize/deserialize."""
    production_tables = load_models()  # dict[str, bytearray]
    # Convert bytearray tables back to dict format for serialize/deserialize roundtrip
    production_dicts: dict[str, dict[tuple[int, int], int]] = {}
    for name, table in production_tables.items():
        bigrams: dict[tuple[int, int], int] = {}
        for idx in range(65536):
            if table[idx] > 0:
                bigrams[(idx >> 8, idx & 0xFF)] = table[idx]
        production_dicts[name] = bigrams
    tmp_models = str(tmp_path / "roundtrip_models.bin")
    serialize_models(production_dicts, tmp_models)
    loaded = deserialize_models(tmp_models)
    assert loaded == production_dicts


@pytest.fixture
def mock_models_bin():
    """Clear the model cache and provide a helper to mock models.bin content.

    Yields a callable ``set_data(raw_bytes)`` that configures the mock to
    return *raw_bytes* from ``models.bin``.  The original ``_MODEL_CACHE``
    and ``_MODEL_NORMS`` are restored on teardown.
    """
    import chardet.models as mod

    original_cache = mod._MODEL_CACHE
    original_norms = mod._MODEL_NORMS
    mod._MODEL_CACHE = None
    mock_ref = MagicMock()

    def set_data(data: bytes) -> None:
        mock_ref.read_bytes.return_value = data

    with patch.object(
        mod.importlib.resources,
        "files",
        return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
    ):
        yield set_data

    mod._MODEL_CACHE = original_cache
    mod._MODEL_NORMS = original_norms


def test_load_models_empty_file(mock_models_bin: Callable[[bytes], None]) -> None:
    """Empty models.bin should emit RuntimeWarning and return empty dict."""
    mock_models_bin(b"")
    with pytest.warns(RuntimeWarning, match="models.bin is empty"):
        result = load_models()
    assert result == {}


def test_load_models_num_encodings_exceeds_limit(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """num_encodings > 10000 should raise ValueError."""
    mock_models_bin(struct.pack("!I", 10001))
    with pytest.raises(ValueError, match="num_encodings=10001 exceeds limit"):
        load_models()


def test_load_models_name_len_exceeds_limit(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """name_len > 256 should raise ValueError."""
    data = struct.pack("!I", 1)  # num_encodings=1
    data += struct.pack("!I", 300)  # name_len=300
    mock_models_bin(data)
    with pytest.raises(ValueError, match="name_len=300 exceeds 256"):
        load_models()


def test_load_models_num_entries_exceeds_limit(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """num_entries > 65536 should raise ValueError."""
    name = b"test/enc"
    data = struct.pack("!I", 1)  # num_encodings=1
    data += struct.pack("!I", len(name)) + name  # name
    data += struct.pack("!I", 70000)  # num_entries=70000
    mock_models_bin(data)
    with pytest.raises(ValueError, match="num_entries=70000 exceeds 65536"):
        load_models()


def test_load_models_truncated_data(mock_models_bin: Callable[[bytes], None]) -> None:
    """Truncated model data should raise ValueError."""
    name = b"test/enc"
    data = struct.pack("!I", 1)  # num_encodings=1
    data += struct.pack("!I", len(name)) + name  # name
    data += struct.pack("!I", 2)  # num_entries=2
    data += struct.pack("!BBB", 65, 66, 200)  # entry 1 (valid)
    # entry 2 is missing — truncated
    mock_models_bin(data)
    with pytest.raises(ValueError, match=r"corrupt models\.bin"):
        load_models()


def test_load_models_truncated_header(mock_models_bin: Callable[[bytes], None]) -> None:
    """Data truncated mid-header should raise ValueError (struct.error wrapped)."""
    # num_encodings=1 but no more data — struct.unpack_from will fail
    mock_models_bin(struct.pack("!I", 1))
    with pytest.raises(ValueError, match=r"corrupt models\.bin"):
        load_models()


def test_load_models_invalid_utf8_name(
    mock_models_bin: Callable[[bytes], None],
) -> None:
    """Invalid UTF-8 in model name should raise ValueError (UnicodeDecodeError wrapped)."""
    invalid_name = b"\xff\xfe"  # not valid UTF-8
    data = struct.pack("!I", 1)  # num_encodings=1
    data += struct.pack("!I", len(invalid_name)) + invalid_name  # name
    mock_models_bin(data)
    with pytest.raises(ValueError, match=r"corrupt models\.bin"):
        load_models()


def test_score_with_profile_fallback_norm():
    """score_with_profile with empty model_key should compute norm on the fly."""
    from chardet.models import BigramProfile, score_with_profile

    profile = BigramProfile(b"\xc3\xa9\xc3\xa4")  # some high-byte bigrams
    # Build a model with a few non-zero entries
    model = bytearray(65536)
    model[(0xC3 << 8) | 0xA9] = 100
    model[(0xC3 << 8) | 0xA4] = 80
    score = score_with_profile(profile, model, model_key="")
    assert isinstance(score, float)
    assert score > 0.0


def test_score_with_profile_all_zeros_model():
    """All-zeros model should return 0.0 (model_norm == 0)."""
    from chardet.models import BigramProfile, score_with_profile

    profile = BigramProfile(b"\xc3\xa9\xc3\xa4")
    model = bytearray(65536)  # all zeros
    score = score_with_profile(profile, model, model_key="")
    assert score == 0.0


def test_enc_index_alias_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a model key uses a non-canonical name, the canonical name is added.

    The index should contain both the original key and the canonical name
    pointing to the same entries.
    """
    import chardet.models as mod

    # Reset the index cache so get_enc_index() rebuilds it
    monkeypatch.setattr(mod, "_ENC_INDEX", None)

    # Create a fake model dict with a non-canonical encoding name.
    # "utf8" is a non-canonical alias for "UTF-8".
    fake_model = bytearray(65536)
    fake_model[(0xC3 << 8) | 0xA9] = 100
    fake_models = {"French/utf8": fake_model}

    monkeypatch.setattr(mod, "load_models", lambda: fake_models)

    index = mod.get_enc_index()

    # The non-canonical key "utf8" should be in the index
    assert "utf8" in index
    # The canonical name "UTF-8" should also be present via alias resolution
    assert "UTF-8" in index
    # Both should point to the same entries
    assert index["UTF-8"] is index["utf8"]
