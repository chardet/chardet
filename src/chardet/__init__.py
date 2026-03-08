"""Universal character encoding detector — MIT-licensed rewrite."""

from __future__ import annotations

from chardet._utils import (
    _DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_BYTES,
    MINIMUM_THRESHOLD,
    _validate_max_bytes,
    _warn_deprecated_chunk_size,
)
from chardet._version import __version__
from chardet.detector import UniversalDetector
from chardet.enums import EncodingEra, LanguageFilter
from chardet.equivalences import apply_compat_names, apply_legacy_rename
from chardet.pipeline import DetectionDict, DetectionResult
from chardet.pipeline.orchestrator import run_pipeline

__all__ = [
    "DEFAULT_MAX_BYTES",
    "MINIMUM_THRESHOLD",
    "DetectionDict",
    "DetectionResult",
    "EncodingEra",
    "LanguageFilter",
    "UniversalDetector",
    "__version__",
    "detect",
    "detect_all",
]


def detect(
    byte_str: bytes | bytearray,
    should_rename_legacy: bool = False,
    encoding_era: EncodingEra = EncodingEra.ALL,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> DetectionDict:
    """Detect the encoding of the given byte string.

    Parameters match chardet 5.x/6.x for backward compatibility.
    *chunk_size* is accepted but has no effect.

    :param byte_str: The byte sequence to detect encoding for.
    :param should_rename_legacy: If ``True``, use canonical display-cased
        encoding names and remap legacy ISO encodings to their modern Windows
        superset equivalents.  If ``False`` (the default), return names
        compatible with chardet 5.x/6.x.
    :param encoding_era: Restrict candidate encodings to the given era.
    :param chunk_size: Deprecated -- accepted for backward compatibility but
        has no effect.
    :param max_bytes: Maximum number of bytes to examine from *byte_str*.
    :returns: A dictionary with keys ``"encoding"``, ``"confidence"``, and
        ``"language"``.
    """
    _warn_deprecated_chunk_size(chunk_size)
    _validate_max_bytes(max_bytes)
    data = byte_str if isinstance(byte_str, bytes) else bytes(byte_str)
    results = run_pipeline(data, encoding_era, max_bytes=max_bytes)
    result = results[0].to_dict()
    if should_rename_legacy:
        apply_legacy_rename(result)
    else:
        apply_compat_names(result)
    return result


def detect_all(  # noqa: PLR0913
    byte_str: bytes | bytearray,
    ignore_threshold: bool = False,
    should_rename_legacy: bool = False,
    encoding_era: EncodingEra = EncodingEra.ALL,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[DetectionDict]:
    """Detect all possible encodings of the given byte string.

    Parameters match chardet 5.x/6.x for backward compatibility.
    *chunk_size* is accepted but has no effect.

    When *ignore_threshold* is False (the default), results with confidence
    <= MINIMUM_THRESHOLD (0.20) are filtered out.  If all results are below
    the threshold, the full unfiltered list is returned as a fallback so the
    caller always receives at least one result.

    :param byte_str: The byte sequence to detect encoding for.
    :param ignore_threshold: If ``True``, return all candidate encodings
        regardless of confidence score.
    :param should_rename_legacy: If ``True``, use canonical display-cased
        encoding names and remap legacy ISO encodings to their modern Windows
        superset equivalents.  If ``False`` (the default), return names
        compatible with chardet 5.x/6.x.
    :param encoding_era: Restrict candidate encodings to the given era.
    :param chunk_size: Deprecated -- accepted for backward compatibility but
        has no effect.
    :param max_bytes: Maximum number of bytes to examine from *byte_str*.
    :returns: A list of dictionaries, each with keys ``"encoding"``,
        ``"confidence"``, and ``"language"``, sorted by descending confidence.
    """
    _warn_deprecated_chunk_size(chunk_size)
    _validate_max_bytes(max_bytes)
    data = byte_str if isinstance(byte_str, bytes) else bytes(byte_str)
    results = run_pipeline(data, encoding_era, max_bytes=max_bytes)
    dicts = [r.to_dict() for r in results]
    if not ignore_threshold:
        filtered = [d for d in dicts if d["confidence"] > MINIMUM_THRESHOLD]
        if filtered:
            dicts = filtered
    _rename = apply_legacy_rename if should_rename_legacy else apply_compat_names
    for d in dicts:
        _rename(d)
    return sorted(dicts, key=lambda d: d["confidence"], reverse=True)
