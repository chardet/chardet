"""Public-API encoding-name remapping.

Two output transforms applied to detection results before they cross the
public API:

* :func:`apply_preferred_superset` -- when the ``prefer_superset`` API option
  is enabled, replaces detected ISO/subset encoding names with their
  Windows/CP supersets that modern software actually uses
  (e.g., ISO-8859-1 -> Windows-1252).

* :func:`apply_compat_names` -- when the default ``compat_names=True`` mode
  is enabled, maps internal Python codec names to the names chardet 5.x/6.x
  returned, preserving backward compatibility for callers that compare
  encoding strings directly.

Both transforms operate in-place on a :class:`~chardet.pipeline.DetectionDict`
and return the same dict for fluent chaining.
"""

from __future__ import annotations

from chardet.pipeline import DetectionDict

# Preferred superset name for each encoding, used by the ``prefer_superset``
# API option.  When enabled, detected encoding names are replaced with the
# Windows/CP superset that modern software actually uses (browsers, editors,
# etc. treat these ISO subsets as their Windows counterparts).
# Values use display-cased names (e.g. "Windows-1252") to match chardet 6.x output.
PREFERRED_SUPERSET: dict[str, str] = {
    "ascii": "cp1252",
    "euc_kr": "cp949",
    "iso8859-1": "cp1252",
    "iso8859-2": "cp1250",
    "iso8859-5": "cp1251",
    "iso8859-6": "cp1256",
    "iso8859-7": "cp1253",
    "iso8859-8": "cp1255",
    "iso8859-9": "cp1254",
    "iso8859-11": "cp874",
    "iso8859-13": "cp1257",
    "tis-620": "cp874",
}


# Mapping from Python codec names to chardet 5.x/6.x compatible display names.
# Only entries where codec name differs from the compat output are listed.
# Encodings where codec name == compat name (e.g., "ascii", "utf-8") and
# encodings new to v7 have no entry — the codec name passes through unchanged.
_COMPAT_NAMES: dict[str, str] = {
    # 5.x compat — these encodings existed in chardet 5.x with different names
    "big5hkscs": "Big5",
    "cp855": "IBM855",
    "cp866": "IBM866",
    "cp874": "CP874",
    "cp932": "CP932",
    "cp949": "CP949",
    "euc_jis_2004": "EUC-JP",
    "euc_kr": "EUC-KR",
    "gb18030": "GB18030",
    "hz": "HZ-GB-2312",
    "iso2022_jp_2": "ISO-2022-JP",
    "iso2022_kr": "ISO-2022-KR",
    "iso8859-1": "ISO-8859-1",
    "iso8859-2": "ISO-8859-2",
    "iso8859-5": "ISO-8859-5",
    "iso8859-6": "ISO-8859-6",
    "iso8859-7": "ISO-8859-7",
    "iso8859-8": "ISO-8859-8",
    "iso8859-9": "ISO-8859-9",
    "iso8859-13": "ISO-8859-13",
    "johab": "Johab",
    "koi8-r": "KOI8-R",
    "mac-cyrillic": "MacCyrillic",
    "mac-roman": "MacRoman",
    "shift_jis_2004": "SHIFT_JIS",
    "tis-620": "TIS-620",
    "utf-16": "UTF-16",
    "utf-32": "UTF-32",
    "utf-8-sig": "UTF-8-SIG",
    "cp1250": "Windows-1250",
    "cp1251": "Windows-1251",
    "cp1252": "Windows-1252",
    "cp1253": "Windows-1253",
    "cp1254": "Windows-1254",
    "cp1255": "Windows-1255",
    "cp1256": "Windows-1256",
    "cp1257": "Windows-1257",
    # 6.x compat — new in chardet 6.x with different names
    "kz1048": "KZ1048",
    "mac-greek": "MacGreek",
    "mac-iceland": "MacIceland",
    "mac-latin2": "MacLatin2",
    "mac-turkish": "MacTurkish",
}


def _remap_encoding(result: DetectionDict, mapping: dict[str, str]) -> DetectionDict:
    """Replace the encoding name using *mapping*, modifying *result* in-place."""
    enc = result.get("encoding")
    if isinstance(enc, str):
        result["encoding"] = mapping.get(enc, enc)
    return result


def apply_preferred_superset(
    result: DetectionDict,
) -> DetectionDict:
    """Replace the encoding name with its preferred Windows/CP superset.

    Modifies the ``"encoding"`` value in *result* in-place and returns *result*
    for fluent chaining.

    :param result: A detection result dict containing an ``"encoding"`` key.
    :returns: The same *result* dict, modified in-place.
    """
    return _remap_encoding(result, PREFERRED_SUPERSET)


# Deprecated alias — kept for external consumers.
apply_legacy_rename = apply_preferred_superset


def apply_compat_names(
    result: DetectionDict,
) -> DetectionDict:
    """Convert internal codec names to chardet 5.x/6.x compatible names.

    Modifies the ``"encoding"`` value in *result* in-place and returns *result*
    for fluent chaining.

    :param result: A detection result dict containing an ``"encoding"`` key.
    :returns: The same *result* dict, modified in-place.
    """
    return _remap_encoding(result, _COMPAT_NAMES)
