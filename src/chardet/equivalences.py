"""Encoding equivalences and legacy name remapping.

This module defines:

1. **Directional supersets** for accuracy evaluation: detecting a superset
   encoding when the expected encoding is a subset is correct (e.g., detecting
   UTF-8 when expected is ASCII), but not the reverse.

2. **Bidirectional equivalents**: groups of encodings where detecting any
   member when another member was expected is considered correct.  This
   includes UTF-16/UTF-32 endian variants (which encode the same text with
   different byte order) and ISO-2022-JP branch variants (which are
   compatible extensions of the same base encoding).

3. **Preferred superset mapping** for the ``should_rename_legacy`` API option:
   replaces detected ISO/subset encoding names with their Windows/CP superset
   equivalents that modern software actually uses.

4. **Legacy compatibility names** for the default ``should_rename_legacy=False``
   mode: maps canonical display-cased names back to the names chardet 5.x
   returned, preserving backward compatibility for callers that compare
   encoding strings directly.
"""

from __future__ import annotations

import codecs
import unicodedata

from chardet.pipeline import DetectionDict


def normalize_encoding_name(name: str) -> str:
    """Normalize encoding name for comparison.

    :param name: The encoding name to normalize.
    :returns: The canonical codec name, or a lowered/stripped fallback.
    """
    try:
        return codecs.lookup(name).name
    except LookupError:
        return name.lower().replace("-", "").replace("_", "")


# Directional superset relationships: detecting any of the supersets
# when the expected encoding is the subset counts as correct.
# E.g., expected=ascii, detected=utf-8 -> correct (utf-8 ⊃ ascii).
# But expected=utf-8, detected=ascii -> wrong (ascii ⊄ utf-8).
#
# Note: some subset keys (iso-8859-11) are not in the detection
# registry — the detector never returns them.  They appear here because
# chardet test-suite expected values use these names, so the superset
# mapping is needed for accuracy evaluation only.
SUPERSETS: dict[str, frozenset[str]] = {
    "ASCII": frozenset({"UTF-8", "Windows-1252"}),
    "TIS-620": frozenset({"ISO-8859-11", "CP874"}),
    "ISO-8859-11": frozenset({"CP874"}),
    "GB2312": frozenset({"GB18030"}),
    "GBK": frozenset({"GB18030"}),
    "Big5": frozenset({"Big5-HKSCS", "CP950"}),
    "Shift_JIS": frozenset({"CP932", "Shift-JIS-2004"}),
    "Shift-JISX0213": frozenset({"Shift-JIS-2004"}),
    "EUC-JP": frozenset({"EUC-JIS-2004"}),
    "EUC-JISX0213": frozenset({"EUC-JIS-2004"}),
    "EUC-KR": frozenset({"CP949"}),
    "CP037": frozenset({"CP1140"}),
    # ISO-2022-JP subsets: any branch variant is acceptable.
    # ISO2022-JP-1 and ISO2022-JP-3 use Python codec names (no hyphen between
    # "ISO" and "2022") because they appear as expected values in the test suite,
    # not as canonical chardet output.  They are consumed through
    # _NORMALIZED_SUPERSETS which normalizes via codecs.lookup().
    "ISO-2022-JP": frozenset({"ISO-2022-JP-2", "ISO-2022-JP-2004", "ISO-2022-JP-EXT"}),
    "ISO2022-JP-1": frozenset({"ISO-2022-JP-2", "ISO-2022-JP-EXT"}),
    "ISO2022-JP-3": frozenset({"ISO-2022-JP-2004"}),
    # ISO/Windows superset pairs
    "ISO-8859-1": frozenset({"Windows-1252"}),
    "ISO-8859-2": frozenset({"Windows-1250"}),
    "ISO-8859-5": frozenset({"Windows-1251"}),
    "ISO-8859-6": frozenset({"Windows-1256"}),
    "ISO-8859-7": frozenset({"Windows-1253"}),
    "ISO-8859-8": frozenset({"Windows-1255"}),
    "ISO-8859-9": frozenset({"Windows-1254"}),
    "ISO-8859-13": frozenset({"Windows-1257"}),
}

# Preferred superset name for each encoding, used by the ``should_rename_legacy``
# API option.  When enabled, detected encoding names are replaced with the
# Windows/CP superset that modern software actually uses (browsers, editors,
# etc. treat these ISO subsets as their Windows counterparts).
# Values use display-cased names (e.g. "Windows-1252") to match chardet 6.x output.
PREFERRED_SUPERSET: dict[str, str] = {
    "ASCII": "Windows-1252",
    "EUC-KR": "CP949",
    "ISO-8859-1": "Windows-1252",
    "ISO-8859-2": "Windows-1250",
    "ISO-8859-5": "Windows-1251",
    "ISO-8859-6": "Windows-1256",
    "ISO-8859-7": "Windows-1253",
    "ISO-8859-8": "Windows-1255",
    "ISO-8859-9": "Windows-1254",
    "ISO-8859-11": "CP874",
    "ISO-8859-13": "Windows-1257",
    "TIS-620": "CP874",
}


def apply_legacy_rename(
    result: DetectionDict,
) -> DetectionDict:
    """Replace the encoding name with its preferred Windows/CP superset.

    Modifies the ``"encoding"`` value in *result* in-place and returns *result*
    for fluent chaining.

    :param result: A detection result dict containing an ``"encoding"`` key.
    :returns: The same *result* dict, modified in-place.
    """
    enc = result.get("encoding")
    if isinstance(enc, str):
        result["encoding"] = PREFERRED_SUPERSET.get(enc, enc)
    return result


# Mapping from canonical display-cased names to the names chardet 5.x/6.x
# returned.  Only entries that differ are listed; unlisted names pass through
# unchanged (they are either new encodings with no legacy equivalent, or
# already match the old name exactly).
_LEGACY_NAMES: dict[str, str] = {
    # 5.x compat — these encodings existed in chardet 5.x with different names
    "ASCII": "ascii",
    "Big5-HKSCS": "Big5",
    "CP855": "IBM855",
    "CP866": "IBM866",
    "EUC-JIS-2004": "EUC-JP",
    "ISO-2022-JP-2": "ISO-2022-JP",
    "Mac-Cyrillic": "MacCyrillic",
    "Mac-Roman": "MacRoman",
    "Shift-JIS-2004": "SHIFT_JIS",
    "UTF-8": "utf-8",
    # 6.x compat — these encodings were new in 6.x with different names
    "KZ-1048": "KZ1048",
    "Mac-Greek": "MacGreek",
    "Mac-Iceland": "MacIceland",
    "Mac-Latin2": "MacLatin2",
    "Mac-Turkish": "MacTurkish",
}


def apply_compat_names(
    result: DetectionDict,
) -> DetectionDict:
    """Convert canonical encoding names to chardet 5.x/6.x compatible names.

    Modifies the ``"encoding"`` value in *result* in-place and returns *result*
    for fluent chaining.

    :param result: A detection result dict containing an ``"encoding"`` key.
    :returns: The same *result* dict, modified in-place.
    """
    enc = result.get("encoding")
    if isinstance(enc, str):
        result["encoding"] = _LEGACY_NAMES.get(enc, enc)
    return result


# Bidirectional equivalents -- groups where any member is acceptable for any other.
BIDIRECTIONAL_GROUPS: tuple[tuple[str, ...], ...] = (
    ("UTF-16", "UTF-16-LE", "UTF-16-BE"),
    ("UTF-32", "UTF-32-LE", "UTF-32-BE"),
    ("ISO-2022-JP-2", "ISO-2022-JP-2004", "ISO-2022-JP-EXT"),
)

# Bidirectional language equivalences — groups of ISO 639-1 codes for
# languages that are nearly indistinguishable by statistical detection.
# Detecting any member when another member of the same group was expected
# is considered acceptable.
LANGUAGE_EQUIVALENCES: tuple[tuple[str, ...], ...] = (
    ("sk", "cs"),  # Slovak / Czech — ~85% mutual intelligibility
    (
        "uk",
        "ru",
        "bg",
        "be",
    ),  # East Slavic + Bulgarian — shared Cyrillic, high written overlap
    ("ms", "id"),  # Malay / Indonesian — standardized variants of one language
    (
        "no",
        "da",
        "sv",
    ),  # Scandinavian — mutual intelligibility across the dialect continuum
)


def _build_language_equiv_index() -> dict[str, frozenset[str]]:
    """Build a lookup: ISO code -> frozenset of all equivalent ISO codes."""
    result: dict[str, frozenset[str]] = {}
    for group in LANGUAGE_EQUIVALENCES:
        group_set = frozenset(group)
        for code in group:
            result[code] = group_set
    return result


_LANGUAGE_EQUIV: dict[str, frozenset[str]] = _build_language_equiv_index()


def is_language_equivalent(expected: str, detected: str) -> bool:
    """Check whether *detected* is an acceptable language for *expected*.

    Returns ``True`` when *expected* and *detected* are the same ISO 639-1
    code, or belong to the same equivalence group in
    :data:`LANGUAGE_EQUIVALENCES`.

    :param expected: Expected ISO 639-1 language code.
    :param detected: Detected ISO 639-1 language code.
    :returns: ``True`` if the languages are equivalent.
    """
    if expected == detected:
        return True
    group = _LANGUAGE_EQUIV.get(expected)
    return group is not None and detected in group


# Pre-built normalized lookups for fast comparison.
_NORMALIZED_SUPERSETS: dict[str, frozenset[str]] = {
    normalize_encoding_name(subset): frozenset(
        normalize_encoding_name(s) for s in supersets
    )
    for subset, supersets in SUPERSETS.items()
}


def _build_bidir_index() -> dict[str, frozenset[str]]:
    """Build the bidirectional equivalence lookup index."""
    result: dict[str, frozenset[str]] = {}
    for group in BIDIRECTIONAL_GROUPS:
        normed = frozenset(normalize_encoding_name(n) for n in group)
        for name in group:
            result[normalize_encoding_name(name)] = normed
    return result


_NORMALIZED_BIDIR: dict[str, frozenset[str]] = _build_bidir_index()


def is_correct(expected: str | None, detected: str | None) -> bool:
    """Check whether *detected* is an acceptable answer for *expected*.

    Acceptable means:

    1. Exact match (after normalization), OR
    2. Both belong to the same bidirectional byte-order group, OR
    3. *detected* is a known superset of *expected*.

    :param expected: The expected encoding name, or ``None`` for binary files.
    :param detected: The detected encoding name, or ``None``.
    :returns: ``True`` if the detection is acceptable.
    """
    if expected is None:
        return detected is None
    if detected is None:
        return False
    norm_exp = normalize_encoding_name(expected)
    norm_det = normalize_encoding_name(detected)

    # 1. Exact match
    if norm_exp == norm_det:
        return True

    # 2. Bidirectional (same byte-order group)
    if norm_exp in _NORMALIZED_BIDIR and norm_det in _NORMALIZED_BIDIR[norm_exp]:
        return True

    # 3. Superset is acceptable (detected is a known superset of expected)
    return (
        norm_exp in _NORMALIZED_SUPERSETS
        and norm_det in _NORMALIZED_SUPERSETS[norm_exp]
    )


def _strip_combining(text: str) -> str:
    """NFKD-normalize *text* and strip all combining marks."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Pre-computed symbol pair lookups for O(1) equivalence checks.
# Both orderings are stored to avoid constructing temporaries per call.
_EQUIVALENT_SYMBOL_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("¤", "€"),
        ("€", "¤"),
    }
)


def _chars_equivalent(a: str, b: str) -> bool:
    """Return True if characters *a* and *b* are functionally equivalent.

    Equivalent means:
    - Same character, OR
    - Same base letter after stripping combining marks, OR
    - An explicitly listed symbol equivalence (e.g. ¤ ↔ €)
    """
    if a == b:
        return True
    if (a, b) in _EQUIVALENT_SYMBOL_PAIRS:
        return True
    # Compare base letters after stripping combining marks.
    return _strip_combining(a) == _strip_combining(b)


def is_equivalent_detection(
    data: bytes, expected: str | None, detected: str | None
) -> bool:
    """Check whether *detected* produces functionally identical text to *expected*.

    Returns ``True`` when:

    1. *detected* is not ``None`` and both encoding names normalize to the same
       codec, OR
    2. Decoding *data* with both encodings yields identical strings, OR
    3. Every differing character pair is functionally equivalent: same base
       letter after stripping combining marks, or an explicitly listed symbol
       equivalence (e.g. ¤ ↔ €).

    Returns ``False`` if *detected* is ``None``, either encoding is unknown,
    or either encoding cannot decode *data*.

    :param data: The raw byte data that was detected.
    :param expected: The expected encoding name, or ``None`` for binary files.
    :param detected: The detected encoding name, or ``None``.
    :returns: ``True`` if decoding with *detected* yields functionally identical
        text to decoding with *expected*.
    """
    if expected is None:
        return detected is None
    if detected is None:
        return False

    norm_exp = normalize_encoding_name(expected)
    norm_det = normalize_encoding_name(detected)

    if norm_exp == norm_det:
        return True

    try:
        text_exp = data.decode(norm_exp)
        text_det = data.decode(norm_det)
    except (UnicodeDecodeError, LookupError):
        return False

    if text_exp == text_det:
        return True

    if len(text_exp) != len(text_det):
        return False

    return all(_chars_equivalent(a, b) for a, b in zip(text_exp, text_det, strict=True))
