"""Internal shared utilities for chardet."""

from __future__ import annotations

import codecs
import warnings
from collections.abc import Callable

#: Default maximum number of bytes to examine during detection.
DEFAULT_MAX_BYTES: int = 200_000

#: Default minimum confidence threshold for filtering results.
MINIMUM_THRESHOLD: float = 0.20

#: Default chunk_size value (deprecated, kept for backward-compat signatures).
_DEFAULT_CHUNK_SIZE: int = 65_536

#: Cache of incremental-decoder classes, keyed by encoding name.
#:
#: :func:`decodes_without_error` is called once per candidate encoding per
#: detection -- roughly 86 times for :attr:`~chardet.enums.EncodingEra.ALL` --
#: and the factory lookup is a sixth of each call.  The class is immutable and
#: shared; only the per-call *instance* carries decoder state, so caching the
#: class is thread-safe while caching an instance would not be.
#:
#: Only successful lookups are cached, which bounds the cache by the number of
#: installed codecs.  A failed lookup returns ``False`` without storing
#: anything, so an unbounded stream of bogus names (a charset declaration in
#: markup is attacker-controlled) cannot grow it.
_INCREMENTAL_DECODERS: dict[str, Callable[..., codecs.IncrementalDecoder]] = {}


def _warn_deprecated_chunk_size(chunk_size: int, stacklevel: int = 3) -> None:
    """Emit a deprecation warning if *chunk_size* differs from the default."""
    if chunk_size != _DEFAULT_CHUNK_SIZE:
        warnings.warn(
            "chunk_size is not used in this version of chardet and will be ignored",
            DeprecationWarning,
            stacklevel=stacklevel,
        )


def _incremental_decoder(
    encoding: str,
) -> codecs.IncrementalDecoder | None:
    """Return a fresh incremental decoder for *encoding*, or ``None``.

    The class lookup is cached; ``None`` means the codec does not exist.
    Every decode below catches ``UnicodeError`` rather than
    ``UnicodeDecodeError`` because the utf-16/utf-32 incremental decoders
    raise a bare ``UnicodeError`` when the stream does not start with a BOM.
    """
    decoder_class = _INCREMENTAL_DECODERS.get(encoding)
    if decoder_class is None:
        try:
            decoder_class = codecs.getincrementaldecoder(encoding)
        except LookupError:
            return None
        _INCREMENTAL_DECODERS[encoding] = decoder_class
    return decoder_class()


def decodes_without_error(data: bytes, encoding: str) -> bool:
    """Return ``True`` if *data* decodes cleanly under *encoding*.

    Equivalent to ``data.decode(encoding, errors="strict")`` except that an
    incomplete multi-byte sequence at the *end* of *data* is accepted instead of
    raising.

    Detection input is nearly always a prefix of a larger whole.  Callers pass
    the first N bytes of a file, and chardet slices further on its own.
    For a two-byte encoding any of those cuts lands mid-character roughly half
    the time.

    A one-shot strict decode cannot tell a truncated tail from corrupt data: it
    raises either way, so the candidate is discarded and every CJK encoding can
    disappear from the candidate set over a single dangling lead byte. An
    incremental decoder with ``final=False`` defers the partial tail instead,
    while still raising on genuine corruption anywhere before it.

    :param data: The raw byte data to test.
    :param encoding: Name of the codec to test *data* against.
    :returns: ``True`` if *data* decodes without error, ``False`` otherwise.
    """
    decoder = _incremental_decoder(encoding)
    if decoder is None:
        return False
    try:
        decoder.decode(data, final=False)
    except UnicodeError:
        return False
    return True


def decodes_completely(data: bytes, encoding: str) -> bool:
    """Return ``True`` if *data* decodes under *encoding* with nothing deferred.

    The strict sibling of :func:`decodes_without_error`: ``final=True`` makes
    an incomplete multi-byte sequence at the end of *data* an error rather
    than a deferred tail.  This is the question that matters when *data* is
    the caller's entire input --- ``data.decode(encoding)`` will make exactly
    this judgment.

    :param data: The raw byte data to test.
    :param encoding: Name of the codec to test *data* against.
    :returns: ``True`` if *data* decodes completely, ``False`` otherwise.
    """
    decoder = _incremental_decoder(encoding)
    if decoder is None:
        return False
    try:
        decoder.decode(data, final=True)
    except UnicodeError:
        return False
    return True


def dangling_tail_with_ascii_prefix(data: bytes, encoding: str) -> bool:
    """Return ``True`` if *data* is ASCII text plus an incomplete tail.

    One decode pass answers both halves of the decode-safety question:
    the tolerant (``final=False``) decode yields the text before any
    deferred tail, and flushing the decoder afterwards raises exactly when
    a deferred tail existed.  True means the candidate decoded real ASCII
    characters and then hit an incomplete multi-byte sequence at the end
    --- its only *non-ASCII* evidence is the undecodable tail itself.

    Deliberately False when the tolerant decode yields nothing at all
    (the entire input is one dangling sequence): that candidate has zero
    decoded evidence, not ASCII evidence, and a clipped multi-byte
    fragment is better served by the ranking's own judgment.

    :param data: The raw byte data to test.
    :param encoding: Name of the codec to decode *data* with.
    :returns: ``True`` if *data* decodes to non-empty pure ASCII with an
        incomplete sequence deferred at the end.
    """
    decoder = _incremental_decoder(encoding)
    if decoder is None:
        return False
    try:
        text = decoder.decode(data, final=False)
    except UnicodeError:
        return False
    if not text or not text.isascii():
        return False
    try:
        decoder.decode(b"", final=True)
    except UnicodeError:
        return True
    return False


def _validate_max_bytes(max_bytes: int) -> None:
    """Raise ValueError if *max_bytes* is not a positive integer."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        msg = "max_bytes must be a positive integer"
        raise ValueError(msg)


def _resolve_prefer_superset(
    should_rename_legacy: bool, prefer_superset: bool, stacklevel: int = 3
) -> bool:
    """Resolve the deprecated *should_rename_legacy* into *prefer_superset*."""
    if should_rename_legacy:
        warnings.warn(
            "should_rename_legacy is deprecated, use prefer_superset instead",
            DeprecationWarning,
            stacklevel=stacklevel,
        )
        return True
    return prefer_superset


#: Mapping from ISO 639-1 language codes to English names.
#: Includes ``"und"`` (ISO 639-3 "Undetermined") for use when language is unknown.
ISO_TO_LANGUAGE: dict[str, str] = {
    "ar": "arabic",
    "be": "belarusian",
    "bg": "bulgarian",
    "br": "breton",
    "cs": "czech",
    "cy": "welsh",
    "da": "danish",
    "de": "german",
    "el": "greek",
    "en": "english",
    "eo": "esperanto",
    "es": "spanish",
    "et": "estonian",
    "fa": "farsi",
    "fi": "finnish",
    "fr": "french",
    "ga": "irish",
    "gd": "gaelic",
    "he": "hebrew",
    "hr": "croatian",
    "hu": "hungarian",
    "id": "indonesian",
    "is": "icelandic",
    "it": "italian",
    "ja": "japanese",
    "kk": "kazakh",
    "ko": "korean",
    "lt": "lithuanian",
    "lv": "latvian",
    "mk": "macedonian",
    "ms": "malay",
    "mt": "maltese",
    "nl": "dutch",
    "no": "norwegian",
    "pl": "polish",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sk": "slovak",
    "sl": "slovene",
    "sr": "serbian",
    "sv": "swedish",
    "tg": "tajik",
    "th": "thai",
    "tr": "turkish",
    "uk": "ukrainian",
    "und": "undetermined",
    "ur": "urdu",
    "vi": "vietnamese",
    "zh": "chinese",
}
