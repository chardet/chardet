"""Model loading and bigram scoring utilities.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import importlib.resources
import math
import struct
import threading
import warnings

from chardet.registry import REGISTRY

_unpack_uint32 = struct.Struct(">I").unpack_from
_iter_3bytes = struct.Struct(">BBB").iter_unpack

#: Weight applied to non-ASCII bigrams during profile construction.
#: Imported by pipeline/confusion.py for focused bigram re-scoring.
NON_ASCII_BIGRAM_WEIGHT: int = 8

_MODEL_CACHE: dict[str, bytearray] | None = None
_MODEL_NORMS: dict[str, float] | None = None
_MODEL_CACHE_LOCK = threading.Lock()
# Pre-grouped index: encoding name -> [(lang, model, model_key), ...]
_ENC_INDEX: dict[str, list[tuple[str | None, bytearray, str]]] | None = None
_ENC_INDEX_LOCK = threading.Lock()
# Encodings that map to exactly one language, derived from the registry.
# Includes aliases so that e.g. "big5" resolves the same as "big5hkscs".
_SINGLE_LANG_MAP: dict[str, str] = {}
for _enc in REGISTRY.values():
    if len(_enc.languages) == 1:
        _SINGLE_LANG_MAP[_enc.name] = _enc.languages[0]
        for _alias in _enc.aliases:
            _SINGLE_LANG_MAP[_alias] = _enc.languages[0]


def _parse_models_bin(
    data: bytes,
) -> tuple[dict[str, bytearray], dict[str, float]]:
    """Parse the binary models.bin format into model tables and L2 norms.

    :param data: Raw bytes of models.bin (must be non-empty).
    :returns: A ``(models, norms)`` tuple.
    :raises ValueError: If the data is corrupt or truncated.
    """
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


def load_models() -> dict[str, bytearray]:
    """Load all bigram models from the bundled models.bin file.

    Each model is a bytearray of length 65536 (256*256).
    Index: (b1 << 8) | b2 -> weight (0-255).

    Also computes and caches L2 norms for each model as a side-product of
    loading, since we already iterate over the sparse non-zero entries.

    :returns: A dict mapping model key strings to 65536-byte lookup tables.
    """
    global _MODEL_CACHE, _MODEL_NORMS  # noqa: PLW0603
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    with _MODEL_CACHE_LOCK:
        # No re-check: mypyc type-narrows _MODEL_CACHE to None after the
        # outer check, so a re-read here would hit a TypeError under mypyc.
        # Worst case two threads both build on first call (idempotent).
        ref = importlib.resources.files("chardet.models").joinpath("models.bin")
        data = ref.read_bytes()

        if not data:
            warnings.warn(
                "chardet models.bin is empty — statistical detection disabled; "
                "reinstall chardet to fix",
                RuntimeWarning,
                stacklevel=2,
            )
            _MODEL_NORMS = {}
            _MODEL_CACHE = {}
            return _MODEL_CACHE

        models, norms = _parse_models_bin(data)
        _MODEL_NORMS = norms
        _MODEL_CACHE = models
        return models


def get_enc_index() -> dict[str, list[tuple[str | None, bytearray, str]]]:
    """Return a pre-grouped index mapping encoding name -> [(lang, model, model_key), ...]."""
    global _ENC_INDEX  # noqa: PLW0603
    if _ENC_INDEX is not None:
        return _ENC_INDEX
    with _ENC_INDEX_LOCK:
        # No re-check: mypyc type-narrows _ENC_INDEX to None after the
        # outer check, so a re-read here would hit a TypeError under mypyc.
        models = load_models()
        index: dict[str, list[tuple[str | None, bytearray, str]]] = {}
        for key, model in models.items():
            lang, enc = key.split("/", 1)
            index.setdefault(enc, []).append((lang, model, key))

        # Resolve aliases: if a model key matches a registry alias but not
        # the primary name, copy the entry under the primary name.
        alias_to_primary: dict[str, str] = {}
        for entry in REGISTRY.values():
            for alias in entry.aliases:
                alias_to_primary[alias] = entry.name
        for alias, primary in alias_to_primary.items():
            if alias in index and primary not in index:
                index[primary] = index[alias]

        _ENC_INDEX = index
        return index


def infer_language(encoding: str) -> str | None:
    """Return the language for a single-language encoding, or None.

    :param encoding: The canonical encoding name.
    :returns: An ISO 639-1 language code, or ``None`` if the encoding is
        multi-language.
    """
    return _SINGLE_LANG_MAP.get(encoding)


def has_model_variants(encoding: str) -> bool:
    """Return True if the encoding has language variants in the model index.

    :param encoding: The canonical encoding name.
    :returns: ``True`` if bigram models exist for this encoding.
    """
    return encoding in get_enc_index()


def _get_model_norms() -> dict[str, float]:
    """Return cached L2 norms for all models, keyed by model key string."""
    # Norms are computed as a side-product of load_models(), so just ensure
    # models are loaded and return the cached norms.
    load_models()
    # _MODEL_NORMS is guaranteed non-None after load_models() returns.
    return _MODEL_NORMS  # type: ignore[return-value]


class BigramProfile:
    """Pre-computed bigram frequency distribution for a data sample.

    Computing this once and reusing it across all models reduces per-model
    scoring from O(n) to O(distinct_bigrams).

    Stores a single ``weighted_freq`` dict mapping bigram index to
    *count * weight* (weight is 8 for non-ASCII bigrams, 1 otherwise).
    This pre-multiplies the weight during construction so the scoring
    inner loop only needs a single dict traversal with no branching.
    """

    __slots__ = ("input_norm", "weight_sum", "weighted_freq")

    def __init__(self, data: bytes) -> None:
        """Compute the bigram frequency distribution for *data*.

        :param data: The raw byte data to profile.
        """
        total_bigrams = len(data) - 1
        if total_bigrams <= 0:
            self.weighted_freq: dict[int, int] = {}
            self.weight_sum: int = 0
            self.input_norm: float = 0.0
            return

        freq: dict[int, int] = {}
        w_sum = 0
        hi_w = NON_ASCII_BIGRAM_WEIGHT
        _get = freq.get
        for i in range(total_bigrams):
            b1 = data[i]
            b2 = data[i + 1]
            idx = (b1 << 8) | b2
            if b1 > 0x7F or b2 > 0x7F:
                freq[idx] = _get(idx, 0) + hi_w
                w_sum += hi_w
            else:
                freq[idx] = _get(idx, 0) + 1
                w_sum += 1
        self.weighted_freq = freq
        self.weight_sum = w_sum
        self.input_norm = math.sqrt(sum(v * v for v in freq.values()))

    @classmethod
    def from_weighted_freq(cls, weighted_freq: dict[int, int]) -> "BigramProfile":
        """Create a BigramProfile from pre-computed weighted frequencies.

        Computes ``weight_sum`` and ``input_norm`` from *weighted_freq* to
        ensure consistency between the three fields.

        :param weighted_freq: Mapping of bigram index to weighted count.
        :returns: A new :class:`BigramProfile` instance.
        """
        profile = cls(b"")
        profile.weighted_freq = weighted_freq
        profile.weight_sum = sum(weighted_freq.values())
        profile.input_norm = math.sqrt(sum(v * v for v in weighted_freq.values()))
        return profile


def score_with_profile(
    profile: BigramProfile, model: bytearray, model_key: str = ""
) -> float:
    """Score a pre-computed bigram profile against a single model using cosine similarity."""
    if profile.input_norm == 0.0:
        return 0.0
    norms = _get_model_norms()
    model_norm = norms.get(model_key) if model_key else None
    if model_norm is None:
        sq_sum = 0
        for i in range(65536):
            v = model[i]
            if v:
                sq_sum += v * v
        model_norm = math.sqrt(sq_sum)
    if model_norm == 0.0:
        return 0.0
    dot = 0
    for idx, wcount in profile.weighted_freq.items():
        dot += model[idx] * wcount
    return dot / (model_norm * profile.input_norm)


def score_best_language(
    data: bytes,
    encoding: str,
    profile: BigramProfile | None = None,
) -> tuple[float, str | None]:
    """Score data against all language variants of an encoding.

    Returns (best_score, best_language). Uses a pre-grouped index for O(L)
    lookup where L is the number of language variants for the encoding.

    If *profile* is provided, it is reused instead of recomputing the bigram
    frequency distribution from *data*.

    :param data: The raw byte data to score.
    :param encoding: The canonical encoding name to match against.
    :param profile: Optional pre-computed :class:`BigramProfile` to reuse.
    :returns: A ``(score, language)`` tuple with the best cosine-similarity
        score and the corresponding language code (or ``None``).
    """
    if not data and profile is None:
        return 0.0, None

    index = get_enc_index()
    variants = index.get(encoding)
    if variants is None:
        return 0.0, None

    if profile is None:
        profile = BigramProfile(data)

    best_score = 0.0
    best_lang: str | None = None
    for lang, model, model_key in variants:
        s = score_with_profile(profile, model, model_key)
        if s > best_score:
            best_score = s
            best_lang = lang

    return best_score, best_lang
