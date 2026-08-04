"""Model loading and bigram scoring utilities.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import functools
import hashlib
import importlib.resources
import math
import struct
import warnings
import zlib

from chardet.registry import REGISTRY, lookup_encoding

_unpack_uint32 = struct.Struct(">I").unpack_from
_unpack_float64 = struct.Struct(">d").unpack_from
_V2_MAGIC = b"CMD2"
#: rowmax.bin format: magic + SHA-256 of the matching models.bin + one
#: 256-byte row-maxima table per model, in models.bin header order.
_ROWMAX_MAGIC = b"CRM1"

# Encodings that map to exactly one language, derived from the registry.
# Keyed by canonical name only — callers always use canonical names.
_SINGLE_LANG_MAP: dict[str, str] = {}
for _enc in REGISTRY.values():
    if len(_enc.languages) == 1:
        _SINGLE_LANG_MAP[_enc.name] = _enc.languages[0]


def _decompress_tables(
    data: bytes, offset: int, names: list[str], chunk_size: int = 262144
) -> dict[str, bytes]:
    """Decompress the model tables from ``data[offset:]``, one per name.

    Each model is stored as its own bytes object rather than a memoryview
    slice of one big blob: mypyc compiles bytes indexing in the scoring hot
    loop to a native C array access, while memoryview indexing goes through
    a boxed generic call.  Decompression is incremental, one 64 KB table at
    a time — materializing the whole multi-megabyte blob and slicing it
    would transiently double the allocation and strand the freed pages in
    process RSS.  Trailing compressed bytes are ignored, as with whole-blob
    ``zlib.decompress``; the decompressed size is validated instead.

    :raises ValueError: If the decompressed size is not exactly
        ``len(names) * 65536``.
    """
    num_models = len(names)
    expected_size = num_models * 65536
    decomp = zlib.decompressobj()
    models: dict[str, bytes] = {}
    table = bytearray()
    produced = 0
    pos = offset
    end = len(data)
    flushed = False
    while len(models) < num_models:
        need = 65536 - len(table)
        if decomp.unconsumed_tail:
            piece = decomp.decompress(decomp.unconsumed_tail, need)
        elif pos < end:
            chunk = data[pos : pos + chunk_size]
            pos += len(chunk)
            piece = decomp.decompress(chunk, need)
        elif not flushed:
            flushed = True
            piece = decomp.flush()
            if not piece:
                break  # stream exhausted early -> size mismatch below
        else:
            break  # stream exhausted early -> size mismatch below
        produced += len(piece)
        table += piece
        if len(table) == 65536:
            models[names[len(models)]] = bytes(table)
            table.clear()
        elif len(table) > 65536:
            break  # oversized flush -> size mismatch below
    if len(models) == num_models:
        # Drain any leftover decompressed output so extra data is caught,
        # including surplus tables in compressed input not yet fed to the
        # decompressor.  Bytes after the stream's end marker (decomp.eof)
        # are ignored, matching whole-blob zlib.decompress behavior.
        extra = b""
        if decomp.unconsumed_tail:
            extra = decomp.decompress(decomp.unconsumed_tail, 1)
        while not extra and not decomp.eof and pos < end:
            chunk = data[pos : pos + chunk_size]
            pos += len(chunk)
            extra = decomp.decompress(chunk, 1)
        if not extra and not decomp.eof and not flushed:
            extra = decomp.flush()
        produced += len(extra)
    if produced != expected_size or len(models) != num_models:
        msg = (
            f"corrupt models.bin: decompressed size {produced} "
            f"!= expected {expected_size}"
        )
        raise ValueError(msg)
    return models


def _parse_models_bin(
    data: bytes,
) -> tuple[dict[str, bytes], dict[str, float]]:
    """Parse the v2 dense zlib-compressed models.bin format.

    :param data: Raw bytes of models.bin (must be non-empty).
    :returns: A ``(models, norms)`` tuple.
    :raises ValueError: If the data is corrupt or truncated.
    """
    try:
        if data[:4] != _V2_MAGIC:
            msg = "corrupt models.bin: missing CMD2 magic"
            raise ValueError(msg)

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

        models = _decompress_tables(data, offset, names)

    except zlib.error as e:
        msg = f"corrupt models.bin: {e}"
        raise ValueError(msg) from e
    except (struct.error, UnicodeDecodeError) as e:
        msg = f"corrupt models.bin: {e}"
        raise ValueError(msg) from e

    return models, norms


@functools.cache
def _load_models_data() -> tuple[dict[str, bytes], dict[str, float]]:
    """Load and parse models.bin, returning (models, norms).

    Cached: only reads from disk on first call.
    """
    ref = importlib.resources.files("chardet.models").joinpath("models.bin")
    data = ref.read_bytes()

    if not data:
        warnings.warn(
            "chardet models.bin is empty — statistical detection disabled; "
            "reinstall chardet to fix",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}, {}

    return _parse_models_bin(data)


def load_models() -> dict[str, bytes]:
    """Load all bigram models from the bundled models.bin file.

    Each model is a bytes object of length 65536 (256*256).
    Index: (b1 << 8) | b2 -> weight (0-255).

    :returns: A dict mapping model key strings to 65536-byte lookup tables.
    """
    return _load_models_data()[0]


def _build_enc_index(
    models: dict[str, bytes],
) -> dict[str, list[tuple[str | None, bytes, str]]]:
    """Build a grouped index from a models dict.

    :param models: Mapping of ``"lang/encoding"`` keys to 65536-byte tables.
    :returns: Mapping of encoding name to ``[(lang, model, model_key), ...]``.
    """
    index: dict[str, list[tuple[str | None, bytes, str]]] = {}
    for key, model in models.items():
        lang, enc = key.split("/", 1)
        index.setdefault(enc, []).append((lang, model, key))

    # Resolve aliases: if a model key uses a non-canonical name,
    # copy the entry under the canonical name.
    for enc_name in list(index):
        canonical = lookup_encoding(enc_name)
        if canonical is not None and canonical not in index:
            index[canonical] = index[enc_name]

    return index


@functools.cache
def get_enc_index() -> dict[str, list[tuple[str | None, bytes, str]]]:
    """Return a pre-grouped index mapping encoding name -> [(lang, model, model_key), ...]."""
    return _build_enc_index(load_models())


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
    return _load_models_data()[1]


@functools.cache
def get_rowmax() -> dict[str, bytes]:
    """Return per-model row-maximum tables for upper-bound prescreening.

    For each model, entry ``b1`` of its 256-byte table holds the maximum
    weight in the model's row for lead byte ``b1``.  Because every bigram
    weight is bounded by its row maximum, a dot product against the row
    maxima (256 terms) upper-bounds the dot product against the full table
    (65536 terms) — statistical scoring uses this to rule out candidate
    models without scoring them fully.

    Loads the precomputed ``rowmax.bin`` (written by ``scripts/train.py`` in
    the same model order as ``models.bin``).  The file starts with a ``CRM1``
    magic and the SHA-256 of the ``models.bin`` it was derived from: a stale
    or mismatched file would silently under-estimate row maxima and break
    the upper bound that pruning depends on, so anything that does not match
    the *current* ``models.bin`` byte-for-byte is rejected and the tables
    are derived from the models directly (slower, but always correct).
    """
    models = load_models()
    files = importlib.resources.files("chardet.models")
    try:
        data = files.joinpath("rowmax.bin").read_bytes()
        models_digest = hashlib.sha256(
            files.joinpath("models.bin").read_bytes()
        ).digest()
    except (FileNotFoundError, OSError):
        data = b""
        models_digest = b""
    header_size = 4 + 32
    if (
        data[:4] == _ROWMAX_MAGIC
        and data[4:header_size] == models_digest
        and len(data) == header_size + len(models) * 256
    ):
        # models preserves models.bin header order, matching rowmax.bin.
        return {
            key: data[header_size + i * 256 : header_size + (i + 1) * 256]
            for i, key in enumerate(models)
        }
    if models:
        warnings.warn(
            "chardet rowmax.bin is missing or does not match models.bin; "
            "deriving row maxima from the models (slower startup)",
            RuntimeWarning,
            stacklevel=2,
        )
    return {
        key: bytes(max(table[start : start + 256]) for start in range(0, 65536, 256))
        for key, table in models.items()
    }


@functools.cache
def get_idf_weights() -> bytes:
    """Return a 65536-byte IDF weight table for bigram profile construction.

    Loads a precomputed table from ``idf.bin`` (generated at training time).
    For each bigram index, the weight reflects how discriminative that bigram
    is across all models:

    - Bigrams in every model (common ASCII) → weight 1 (minimal signal)
    - Bigrams in one model → weight 255 (maximum signal)
    - Bigrams not in any model → weight 1 (unknown, treat as neutral)
    """
    ref = importlib.resources.files("chardet.models").joinpath("idf.bin")
    data = ref.read_bytes()
    if len(data) != 65536:
        warnings.warn(
            f"chardet idf.bin has wrong size ({len(data)}), "
            "falling back to uniform weights",
            RuntimeWarning,
            stacklevel=2,
        )
        return b"\x01" * 65536
    return data


class BigramProfile:
    """Pre-computed bigram frequency distribution for a data sample.

    Computing this once and reusing it across all models reduces per-model
    scoring from O(n) to O(distinct_bigrams).

    Stores a dense ``freq`` list of length 65536 indexed by bigram index, plus
    a ``nonzero`` list of indices with non-zero frequency for fast iteration.
    Each bigram is weighted by its IDF (inverse document frequency) across all
    models — bigrams unique to few models get high weight, bigrams common to
    all models get weight 1.

    ``row_freq`` aggregates ``freq`` by lead byte (256 entries) and
    ``nonzero_rows`` lists the lead bytes with non-zero total; together with
    per-model row maxima (:func:`get_rowmax`) they let statistical scoring
    compute a cheap upper bound on a model's score.
    """

    __slots__ = (
        "freq",
        "input_norm",
        "nonzero",
        "nonzero_rows",
        "row_freq",
        "weight_sum",
    )

    def __init__(self, data: bytes) -> None:
        """Compute the bigram frequency distribution for *data*.

        Each bigram is weighted by its IDF (inverse document frequency) across
        all loaded models.  Bigrams unique to few models get high weight;
        bigrams common to all models get weight 1.

        :param data: The raw byte data to profile.
        """
        total_bigrams = len(data) - 1
        if total_bigrams <= 0:
            # Use empty lists (not [0]*65536) to avoid a 256KB allocation
            # for no-op profiles.  Safe because score_with_profile returns
            # early when input_norm == 0.0, so freq is never indexed.
            self.freq: list[int] = []
            self.nonzero: list[int] = []
            self.row_freq: list[int] = []
            self.nonzero_rows: list[int] = []
            self.weight_sum: int = 0
            self.input_norm: float = 0.0
            return

        idf = get_idf_weights()
        freq: list[int] = [0] * 65536
        nonzero: list[int] = []
        w_sum = 0
        for i in range(total_bigrams):
            idx = (data[i] << 8) | data[i + 1]
            w = idf[idx]
            if freq[idx] == 0:
                nonzero.append(idx)
            freq[idx] += w
            w_sum += w
        self._finish(freq, nonzero, w_sum)

    def _finish(self, freq: list[int], nonzero: list[int], weight_sum: int) -> None:
        """Store the frequency data and derive the norm and row aggregates.

        Single finalization path shared by both constructors so pruning
        fields cannot silently diverge between them.
        """
        self.freq = freq
        self.nonzero = nonzero
        self.weight_sum = weight_sum
        norm_sq = 0
        row_freq: list[int] = [0] * 256
        for idx in nonzero:
            v = freq[idx]
            norm_sq += v * v
            row_freq[idx >> 8] += v
        self.input_norm = math.sqrt(norm_sq)
        self.row_freq = row_freq
        self.nonzero_rows = [b1 for b1 in range(256) if row_freq[b1]]

    @classmethod
    def from_weighted_freq(cls, weighted_freq: dict[int, int]) -> "BigramProfile":
        """Create a BigramProfile from pre-computed weighted frequencies.

        Computes ``weight_sum`` and ``input_norm`` from *weighted_freq* to
        ensure consistency between the stored fields.

        :param weighted_freq: Mapping of bigram index to weighted count.
        :returns: A new :class:`BigramProfile` instance.
        """
        profile = cls(b"")
        freq: list[int] = [0] * 65536
        nonzero: list[int] = []
        w_sum = 0
        for idx, count in weighted_freq.items():
            freq[idx] = count
            if count:
                nonzero.append(idx)
                w_sum += count
        profile._finish(freq, nonzero, w_sum)
        return profile


def score_with_profile(
    profile: BigramProfile,
    model: "bytes | bytearray | memoryview",
    model_key: str = "",
) -> float:
    """Score a pre-computed bigram profile against a single model using cosine similarity.

    ``bytearray``/``memoryview`` tables are accepted for compatibility but
    copied to ``bytes`` first: the narrow type lets mypyc compile the
    dot-product loop with native byte indexing (and keeps compiled and
    pure-Python installs accepting the same argument types).
    """
    if not isinstance(model, bytes):
        model = bytes(model)
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
    freq = profile.freq
    for idx in profile.nonzero:
        dot += model[idx] * freq[idx]
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
