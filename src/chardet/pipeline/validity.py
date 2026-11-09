"""Stage 2a: Byte sequence validity filtering.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import codecs
import sys

from chardet._utils import decodes_without_error
from chardet.registry import EncodingInfo

#: Bytes each single-byte charmap codec cannot decode, keyed by encoding
#: name; ``None`` marks a codec that is not a charmap codec.
_UNDEFINED_BYTES: dict[str, bytes | None] = {}


def _charmap_undefined_bytes(encoding: str) -> bytes | None:
    """Return the bytes a single-byte charmap codec cannot decode.

    The stdlib's single-byte codecs (``cp1252``, ``koi8_r``, ``mac_roman``
    and the like) decode through a 256-character ``decoding_table`` in which
    ``U+FFFE`` marks an undefined byte.  Such a codec has no state and no
    multi-byte sequences, so data decodes strictly exactly when it contains
    none of the undefined bytes; most of these codecs define all 256.

    :param encoding: Name of the codec.
    :returns: The undefined bytes (possibly empty), or ``None`` when
        *encoding* is not a charmap codec and has to be decoded instead.
    """
    if encoding in _UNDEFINED_BYTES:
        return _UNDEFINED_BYTES[encoding]
    try:
        decoder_class = codecs.getincrementaldecoder(encoding)
    except LookupError:
        # Not cached, so bogus names cannot grow the cache.
        return None
    module = sys.modules.get(getattr(decoder_class, "__module__", ""))
    table = getattr(module, "decoding_table", None)
    undefined: bytes | None = None
    if isinstance(table, str) and len(table) == 256:
        undefined = bytes(b for b in range(256) if table[b] == "\ufffe")
    _UNDEFINED_BYTES[encoding] = undefined
    return undefined


def _decodes(data: bytes, encoding: str) -> bool:
    """Return ``True`` if *data* decodes cleanly under *encoding*.

    Answers :func:`~chardet._utils.decodes_without_error`'s question, but
    for a single-byte charmap codec it looks for the codec's undefined bytes
    instead of decoding the whole window.
    """
    undefined = _charmap_undefined_bytes(encoding)
    if undefined is None:
        return decodes_without_error(data, encoding)
    return not any(b in data for b in undefined)


def filter_by_validity(
    data: bytes, candidates: tuple[EncodingInfo, ...]
) -> tuple[EncodingInfo, ...]:
    """Filter candidates to only those where *data* decodes without errors.

    :param data: The raw byte data to test.
    :param candidates: Encoding candidates to validate.
    :returns: The subset of *candidates* that can decode *data*.
    """
    if not data:
        return candidates

    return tuple(enc for enc in candidates if _decodes(data, enc.name))
