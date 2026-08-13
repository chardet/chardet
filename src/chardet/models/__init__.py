"""Model loading and bigram scoring utilities.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import array
import functools
import hashlib
import importlib.resources
import math
import struct
import warnings
import zlib

from chardet import _kernel
from chardet._kernel import dot_packed, pack_profile
from chardet.registry import REGISTRY, lookup_encoding

#: Shared empty packed buffers for profiles scored through another path.
#: Safe to share because nothing ever writes to a profile's packed
#: buffers --- dot_packed only reads them, and pack_profile always
#: returns fresh arrays.  Rebuilding these per profile allocated four
#: throwaway arrays on the focused-profile path, which the surrounding
#: code exists to keep allocation-free.
_EMPTY_PACKED = (array.array("i"), array.array("i"))

#: Whether _kernel was compiled into an extension for this install.
#: The packed buffers only pay off when it was: read from C they are two
#: contiguous int32 arrays, but read from the interpreter every element
#: access boxes an int, which is slower than the dense list it replaced.
#: A build with mypyc but no Cython would otherwise get the packed layout
#: with an interpreted loop -- measured 3.5x slower than either path
#: alone -- so profiles keep the dense table instead when it is absent.
#:
#: This flag makes two scoring paths and two storage shapes live in one
#: file, and **no single test run exercises both**: a compiled run never
#: takes the dense branch, an interpreted run never takes the packed one.
#: Running the suite against both builds is therefore load-bearing rather
#: than thorough --- it is the only thing standing between these branches
#: and silently diverging.  Change either one and check the other.
_KERNEL_COMPILED = _kernel.__file__.endswith((".so", ".pyd"))

_unpack_uint32 = struct.Struct(">I").unpack_from
_unpack_float64 = struct.Struct(">d").unpack_from

# 256-entry membership table for whitespace bytes whose runs training
# collapsed — native byte indexing under mypyc, used in the bigram-profile
# hot loop.  Covers the ASCII whitespace bytes (space, tab, LF, VT, FF, CR)
# plus NBSP (0xA0): training's run collapse operates on decoded text where
# regex \s matches all of these, so Latin models carry no run weight for
# them and an uncollapsed input run would match only unrelated models
# where the byte happens to be a letter.  0x85 (NEL in the ISO family) is
# deliberately absent: it decodes to the ellipsis in windows-1252, whose
# models legitimately carry ellipsis-run weight.
_ASCII_WHITESPACE_TABLE = bytes(
    1 if b in (0x20, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0xA0) else 0 for b in range(256)
)
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

    Each bigram is weighted by its IDF (inverse document frequency) across all
    models — bigrams unique to few models get high weight, bigrams common to
    all models get weight 1.  ``nonzero`` lists the indices carrying weight,
    in first-encounter order.

    The weights are reachable two ways, and which one a profile fills
    depends on how it was built:

    * ``idx_arr``/``val_arr`` — parallel ``array('i')`` buffers, what
      :func:`score_with_profile` reads for a streaming profile.  Filled by
      the streaming constructor only.
    * ``values`` — a plain list parallel to ``nonzero``, filled by
      :meth:`from_weighted_freq` for the small focused profiles confusion
      resolution builds, which are scored inline instead.
    ``row_freq`` aggregates the weights by lead byte (256 entries) and
    ``nonzero_rows`` lists the lead bytes with non-zero total; together with
    per-model row maxima (:func:`get_rowmax`) they let statistical scoring
    compute a cheap upper bound on a model's score.

    **Input limit.** Weights are packed as int32, which holds any value an
    input of at most 16 MB can produce (``255`` per occurrence against a
    2.1-billion ceiling).  Detection truncates to ``max_bytes`` long before
    that; construct a profile directly from a larger buffer and packing
    raises :exc:`OverflowError`.
    """

    __slots__ = (
        "freq",
        "idx_arr",
        "input_norm",
        "nonzero",
        "nonzero_rows",
        "row_freq",
        "val_arr",
        "values",
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
            # Empty lists, not [0]*65536: a no-op profile allocates nothing.
            self.freq: list[int] = []
            self.nonzero: list[int] = []
            self.values: list[int] = []
            self.idx_arr, self.val_arr = _EMPTY_PACKED
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
            b1 = data[i]
            b2 = data[i + 1]
            # Skip repeated-whitespace bigrams (equivalent to collapsing
            # whitespace runs, which training does before counting): padding
            # and indentation carry no encoding signal, and models trained
            # on lossy transcodes can carry spurious weight for them.
            if b1 == b2 and _ASCII_WHITESPACE_TABLE[b1]:
                continue
            idx = (b1 << 8) | b2
            w = idf[idx]
            if freq[idx] == 0:
                nonzero.append(idx)
            freq[idx] += w
            w_sum += w
        # No ``values``: this path already has the dense table, and
        # materializing a parallel list over every nonzero bigram costs
        # more than the sparse constructor's allocation saves.
        self._finish(freq, nonzero, [], w_sum)

    def _finish(
        self,
        freq: list[int],
        nonzero: list[int],
        values: list[int],
        weight_sum: int,
    ) -> None:
        """Store the frequency data and derive the norm and row aggregates.

        Single finalization path shared by both constructors so pruning
        fields cannot silently diverge between them.

        Exactly one of *freq* and *values* carries the weights, never both.
        The streaming constructor passes the dense *freq* table it had to
        build and leaves *values* empty; the sparse constructor fills
        *values* parallel to *nonzero* and passes no table, which is what
        lets it skip a 65536-entry allocation per call.

        Neither is retained.  *freq* is read here to derive the norm, the row
        aggregates and the packed buffers, and is then dropped -- scoring
        reads ``idx_arr``/``val_arr`` or ``values``, never the dense table,
        so keeping it alive would pin 512 KB per profile for nothing.
        """
        self.nonzero = nonzero
        self.values = values
        self.weight_sum = weight_sum
        norm_sq = 0
        row_freq: list[int] = [0] * 256
        if values:
            for i in range(len(nonzero)):
                v = values[i]
                norm_sq += v * v
                row_freq[nonzero[i] >> 8] += v
        else:
            for idx in nonzero:
                v = freq[idx]
                norm_sq += v * v
                row_freq[idx >> 8] += v
        self.input_norm = math.sqrt(norm_sq)
        self.row_freq = row_freq
        self.nonzero_rows = [b1 for b1 in range(256) if row_freq[b1]]
        # Dense profiles are scored through the packed kernel when it is
        # compiled; sparse ones (a median of eight bigrams) are scored inline
        # either way and skip the packing.
        if values or not _KERNEL_COMPILED:
            self.idx_arr, self.val_arr = _EMPTY_PACKED
        else:
            self.idx_arr, self.val_arr = pack_profile(nonzero, freq)
        # Retained only when scoring will read it -- see _KERNEL_COMPILED.
        self.freq = [] if (values or _KERNEL_COMPILED) else freq

    @classmethod
    def from_weighted_freq(cls, weighted_freq: dict[int, int]) -> "BigramProfile":
        """Create a BigramProfile from pre-computed weighted frequencies.

        Computes ``weight_sum`` and ``input_norm`` from *weighted_freq* to
        ensure consistency between the stored fields.

        Deliberately does not build the dense 65536-entry ``freq`` table
        the streaming constructor uses.  Callers here pass a handful of
        bigrams — confusion resolution's focused profiles hold a median of
        eight — and allocating a 65536-element list per call cost about
        24us, which measured as roughly 40% of the whole bigram-rescore
        stage.  Scoring reads ``nonzero``/``values``, so the table is
        never needed.

        :param weighted_freq: Mapping of bigram index to weighted count.
        :returns: A new :class:`BigramProfile` instance.
        """
        profile = cls(b"")
        nonzero: list[int] = []
        values: list[int] = []
        w_sum = 0
        for idx, count in weighted_freq.items():
            if count:
                nonzero.append(idx)
                values.append(count)
                w_sum += count
        profile._finish([], nonzero, values, w_sum)
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
    nonzero = profile.nonzero
    values = profile.values
    if values:
        # Focused confusion profiles hold a median of eight bigrams, so this
        # branch stays inline: a call into _kernel would cost about what the
        # loop does.  It measured 1.3% of compiled runtime.
        dot = 0
        for i in range(len(nonzero)):
            dot += model[nonzero[i]] * values[i]
    elif _KERNEL_COMPILED:
        dot = dot_packed(profile.idx_arr, profile.val_arr, model)
    else:
        # No compiled kernel: the dense table beats packed buffers here,
        # because a list returns a cached int where array('i') boxes a new one.
        dot = 0
        freq = profile.freq
        for idx in nonzero:
            dot += model[idx] * freq[idx]
    return dot / (model_norm * profile.input_norm)


#: ADR-0005's hand-audited rare-language set, shared with the encoding-side
#: arbitration gate in ``pipeline.postprocess``.  One set, two gates: the
#: deployment evidence that justifies membership is recorded in the ADR and
#: any new genuine specimen forces a re-audit of both.
RARE_LANGUAGES: frozenset[str] = frozenset({"gd", "cy", "ga", "br"})

#: The ANSI/ASCII-art pseudo-language.  Never a valid demotion target for
#: the thin-rare band: swapping a rare label for "zxx" would tell the
#: orchestrator the text has no linguistic content at all.
ART_LANGUAGE = "zxx"

#: The thin-margin band for ``demote_thin_rare``: inputs shorter than this
#: are where bigram cosines stop discriminating (apostrophe-rich English
#: snippets score as Gaelic).  The smallest genuine rare-language files in
#: the test corpus are 253 bytes (legacy path) and 560 bytes (fill path),
#: 2x and 4.4x above this gate; the callers in ``pipeline.language`` own
#: the length judgment because only they know the pre-transcoding size.
_THIN_RARE_MAX_BYTES = 128

#: Maximum lead over the best prevalent-language variant for a rare win on
#: a short input to count as noise.  Measured mislabels win by <= 0.021.
#: This is NOT a safety floor: genuine gd/cy snippets measure 0.07+ and the
#: nearest measured genuine escape is Welsh at 0.043, but short Breton and
#: Irish can sit inside the band and are the accepted casualty class per
#: ADR-0005's addendum — widening the margin widens that class.
_THIN_RARE_MARGIN = 0.03


def score_best_language(
    data: bytes,
    encoding: str,
    profile: BigramProfile | None = None,
    *,
    demote_thin_rare: bool = False,
) -> tuple[float, str | None]:
    """Score data against all language variants of an encoding.

    Returns (best_score, best_language). Uses a pre-grouped index for O(L)
    lookup where L is the number of language variants for the encoding.

    If *profile* is provided, it is reused instead of recomputing the bigram
    frequency distribution from *data*.

    :param data: The raw byte data to score.
    :param encoding: The canonical encoding name to match against.
    :param profile: Optional pre-computed :class:`BigramProfile` to reuse.
    :param demote_thin_rare: Pass true only when the caller has judged the
        *original* input thin (under :data:`_THIN_RARE_MAX_BYTES` before
        any transcoding).  A :data:`RARE_LANGUAGES` winner that leads the
        best prevalent-language variant by less than the measured noise
        band is then reported under the prevalent language instead.  The
        length judgment deliberately lives with the caller: this function
        may receive transcoded bytes or a profile without its source data,
        so ``len(data)`` here is not a reliable proxy for input size.
        Language-fill callers pass this; encoding-ranking callers must not,
        so that candidate ordering stays byte-identical.
    :returns: A ``(score, language)`` tuple.  The score is always the best
        cosine similarity across variants; the language matches it except
        when ``demote_thin_rare`` fires, in which case the label is the
        best prevalent-language variant's while the score remains the
        rare winner's.
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
    best_prevalent = 0.0
    best_prevalent_lang: str | None = None
    for lang, model, model_key in variants:
        s = score_with_profile(profile, model, model_key)
        if s > best_score:
            best_score = s
            best_lang = lang
        if (
            demote_thin_rare
            and lang not in RARE_LANGUAGES
            and lang != ART_LANGUAGE
            and s > best_prevalent
        ):
            best_prevalent = s
            best_prevalent_lang = lang

    if (
        demote_thin_rare
        and best_lang is not None
        and best_lang in RARE_LANGUAGES
        and best_prevalent_lang is not None
        and best_score - best_prevalent < _THIN_RARE_MARGIN
    ):
        best_lang = best_prevalent_lang

    return best_score, best_lang
