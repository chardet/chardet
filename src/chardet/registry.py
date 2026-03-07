"""Encoding registry with metadata for all supported encodings."""

from __future__ import annotations

import codecs
import dataclasses
import threading
from types import MappingProxyType
from typing import Literal

from chardet.enums import EncodingEra

EncodingName = Literal[
    "ascii",
    "big5hkscs",
    "cp1006",
    "cp1026",
    "cp1125",
    "cp1140",
    "cp273",
    "cp424",
    "cp437",
    "cp500",
    "cp720",
    "cp737",
    "cp775",
    "cp850",
    "cp852",
    "cp855",
    "cp856",
    "cp857",
    "cp858",
    "cp860",
    "cp861",
    "cp862",
    "cp863",
    "cp864",
    "cp865",
    "cp866",
    "cp869",
    "cp874",
    "cp875",
    "cp932",
    "cp949",
    "euc-jis-2004",
    "euc-kr",
    "gb18030",
    "hp-roman8",
    "hz-gb-2312",
    "iso-2022-kr",
    "iso-8859-1",
    "iso-8859-10",
    "iso-8859-13",
    "iso-8859-14",
    "iso-8859-15",
    "iso-8859-16",
    "iso-8859-2",
    "iso-8859-3",
    "iso-8859-4",
    "iso-8859-5",
    "iso-8859-6",
    "iso-8859-7",
    "iso-8859-8",
    "iso-8859-9",
    "iso2022-jp-2",
    "iso2022-jp-2004",
    "iso2022-jp-ext",
    "johab",
    "koi8-r",
    "koi8-t",
    "koi8-u",
    "kz-1048",
    "mac-cyrillic",
    "mac-greek",
    "mac-iceland",
    "mac-latin2",
    "mac-roman",
    "mac-turkish",
    "ptcp154",
    "shift_jis_2004",
    "tis-620",
    "utf-16",
    "utf-16-be",
    "utf-16-le",
    "utf-32",
    "utf-32-be",
    "utf-32-le",
    "utf-7",
    "utf-8",
    "utf-8-sig",
    "windows-1250",
    "windows-1251",
    "windows-1252",
    "windows-1253",
    "windows-1254",
    "windows-1255",
    "windows-1256",
    "windows-1257",
    "windows-1258",
]

# Shared language tuples — used by multiple EncodingInfo entries below.
_WESTERN = (
    "en",
    "fr",
    "de",
    "es",
    "pt",
    "it",
    "nl",
    "da",
    "sv",
    "no",
    "fi",
    "is",
    "id",
    "ms",
)
_WESTERN_TR = (*_WESTERN, "tr")
_CYRILLIC = ("ru", "bg", "uk", "sr", "mk", "be")
_CENTRAL_EU = ("pl", "cs", "hu", "hr", "ro", "sk", "sl")
_CENTRAL_EU_NO_RO = ("pl", "cs", "hu", "hr", "sk", "sl")
_BALTIC = ("et", "lt", "lv")
_ARABIC = ("ar", "fa")


@dataclasses.dataclass(frozen=True, slots=True)
class EncodingInfo:
    """Metadata for a single encoding."""

    name: str
    aliases: tuple[str, ...]
    era: EncodingEra
    is_multibyte: bool
    python_codec: str
    languages: tuple[str, ...]


_CANDIDATES_CACHE: dict[int, tuple[EncodingInfo, ...]] = {}
_CANDIDATES_CACHE_LOCK = threading.Lock()


def get_candidates(era: EncodingEra) -> tuple[EncodingInfo, ...]:
    """Return registry entries matching the given era filter.

    :param era: Bit flags specifying which encoding eras to include.
    :returns: A tuple of matching :class:`EncodingInfo` entries.
    """
    key = int(era)
    result = _CANDIDATES_CACHE.get(key)
    if result is not None:
        return result
    with _CANDIDATES_CACHE_LOCK:
        result = _CANDIDATES_CACHE.get(key)
        if result is not None:  # pragma: no cover - double-checked locking
            return result
        result = tuple(enc for enc in REGISTRY.values() if enc.era & era)
        _CANDIDATES_CACHE[key] = result
        return result


# Era assignments match chardet 6.0.0's chardet/metadata/charsets.py
# python_codec values verified via codecs.lookup()

_REGISTRY_ENTRIES = (
    # === MODERN_WEB ===
    EncodingInfo(
        name="ascii",
        aliases=("us-ascii",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="ascii",
        languages=(),
    ),
    EncodingInfo(
        name="utf-8",
        aliases=("utf8",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-8",
        languages=(),
    ),
    EncodingInfo(
        name="utf-8-sig",
        aliases=("utf-8-bom",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-8-sig",
        languages=(),
    ),
    EncodingInfo(
        name="utf-16",
        aliases=("utf16",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-16",
        languages=(),
    ),
    EncodingInfo(
        name="utf-16-be",
        aliases=("utf-16be",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-16-be",
        languages=(),
    ),
    EncodingInfo(
        name="utf-16-le",
        aliases=("utf-16le",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-16-le",
        languages=(),
    ),
    EncodingInfo(
        name="utf-32",
        aliases=("utf32",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-32",
        languages=(),
    ),
    EncodingInfo(
        name="utf-32-be",
        aliases=("utf-32be",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-32-be",
        languages=(),
    ),
    EncodingInfo(
        name="utf-32-le",
        aliases=("utf-32le",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-32-le",
        languages=(),
    ),
    EncodingInfo(
        name="utf-7",
        aliases=("utf7",),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="utf-7",
        languages=(),
    ),
    # CJK - Modern Web
    EncodingInfo(
        name="big5hkscs",
        aliases=("big5", "big5-tw", "csbig5", "cp950"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="big5hkscs",
        languages=("zh",),
    ),
    EncodingInfo(
        name="cp932",
        aliases=("ms932", "mskanji", "ms-kanji"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="cp932",
        languages=("ja",),
    ),
    EncodingInfo(
        name="cp949",
        aliases=("ms949", "uhc"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="cp949",
        languages=("ko",),
    ),
    EncodingInfo(
        name="euc-jis-2004",
        aliases=("euc-jp", "eucjp", "ujis", "u-jis", "euc-jisx0213"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="euc_jis_2004",
        languages=("ja",),
    ),
    EncodingInfo(
        name="euc-kr",
        aliases=("euckr",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="euc-kr",
        languages=("ko",),
    ),
    EncodingInfo(
        name="gb18030",
        aliases=("gb-18030", "gb2312", "gbk"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="gb18030",
        languages=("zh",),
    ),
    EncodingInfo(
        name="hz-gb-2312",
        aliases=("hz",),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=True,
        python_codec="hz",
        languages=("zh",),
    ),
    EncodingInfo(
        name="iso2022-jp-2",
        aliases=("iso-2022-jp", "csiso2022jp", "iso2022-jp-1"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="iso2022_jp_2",
        languages=("ja",),
    ),
    EncodingInfo(
        name="iso2022-jp-2004",
        aliases=("iso2022-jp-3",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="iso2022_jp_2004",
        languages=("ja",),
    ),
    EncodingInfo(
        name="iso2022-jp-ext",
        aliases=(),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="iso2022_jp_ext",
        languages=("ja",),
    ),
    EncodingInfo(
        name="iso-2022-kr",
        aliases=("csiso2022kr",),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=True,
        python_codec="iso2022-kr",
        languages=("ko",),
    ),
    EncodingInfo(
        name="shift_jis_2004",
        aliases=("shift_jis", "sjis", "shiftjis", "s_jis", "shift-jisx0213"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="shift_jis_2004",
        languages=("ja",),
    ),
    # Windows code pages - Modern Web
    EncodingInfo(
        name="cp874",
        aliases=("windows-874",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp874",
        languages=("th",),
    ),
    EncodingInfo(
        name="windows-1250",
        aliases=("cp1250",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1250",
        languages=_CENTRAL_EU,
    ),
    EncodingInfo(
        name="windows-1251",
        aliases=("cp1251",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1251",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="windows-1252",
        aliases=("cp1252",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1252",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="windows-1253",
        aliases=("cp1253",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1253",
        languages=("el",),
    ),
    EncodingInfo(
        name="windows-1254",
        aliases=("cp1254",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1254",
        languages=("tr",),
    ),
    EncodingInfo(
        name="windows-1255",
        aliases=("cp1255",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1255",
        languages=("he",),
    ),
    EncodingInfo(
        name="windows-1256",
        aliases=("cp1256",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1256",
        languages=_ARABIC,
    ),
    EncodingInfo(
        name="windows-1257",
        aliases=("cp1257",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1257",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="windows-1258",
        aliases=("cp1258",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1258",
        languages=("vi",),
    ),
    # KOI8 - Modern Web
    EncodingInfo(
        name="koi8-r",
        aliases=("koi8r",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="koi8-r",
        languages=("ru",),
    ),
    EncodingInfo(
        name="koi8-u",
        aliases=("koi8u",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="koi8-u",
        languages=("uk",),
    ),
    # TIS-620 - Modern Web
    EncodingInfo(
        name="tis-620",
        aliases=("tis620", "iso-8859-11"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="tis-620",
        languages=("th",),
    ),
    # === LEGACY_ISO ===
    EncodingInfo(
        name="iso-8859-1",
        aliases=("latin-1", "latin1", "iso8859-1"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-1",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="iso-8859-2",
        aliases=("latin-2", "latin2", "iso8859-2"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-2",
        languages=_CENTRAL_EU,
    ),
    EncodingInfo(
        name="iso-8859-3",
        aliases=("latin-3", "latin3", "iso8859-3"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-3",
        languages=("eo", "mt", "tr"),
    ),
    EncodingInfo(
        name="iso-8859-4",
        aliases=("latin-4", "latin4", "iso8859-4"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-4",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="iso-8859-5",
        aliases=("iso8859-5", "cyrillic"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-5",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="iso-8859-6",
        aliases=("iso8859-6", "arabic"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-6",
        languages=_ARABIC,
    ),
    EncodingInfo(
        name="iso-8859-7",
        aliases=("iso8859-7", "greek"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-7",
        languages=("el",),
    ),
    EncodingInfo(
        name="iso-8859-8",
        aliases=("iso8859-8", "hebrew"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-8",
        languages=("he",),
    ),
    EncodingInfo(
        name="iso-8859-9",
        aliases=("latin-5", "latin5", "iso8859-9"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-9",
        languages=("tr",),
    ),
    EncodingInfo(
        name="iso-8859-10",
        aliases=("latin-6", "latin6", "iso8859-10"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-10",
        languages=("is", "fi"),
    ),
    EncodingInfo(
        name="iso-8859-13",
        aliases=("latin-7", "latin7", "iso8859-13"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-13",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="iso-8859-14",
        aliases=("latin-8", "latin8", "iso8859-14"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-14",
        languages=("cy", "ga", "br", "gd"),
    ),
    EncodingInfo(
        name="iso-8859-15",
        aliases=("latin-9", "latin9", "iso8859-15"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-15",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="iso-8859-16",
        aliases=("latin-10", "latin10", "iso8859-16"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-16",
        languages=("ro", "pl", "hr", "hu", "sk", "sl"),
    ),
    # Johab - Legacy ISO per chardet 6.0.0
    EncodingInfo(
        name="johab",
        aliases=(),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=True,
        python_codec="johab",
        languages=("ko",),
    ),
    # === LEGACY_MAC ===
    EncodingInfo(
        name="mac-cyrillic",
        aliases=("maccyrillic",),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-cyrillic",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="mac-greek",
        aliases=("macgreek",),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-greek",
        languages=("el",),
    ),
    EncodingInfo(
        name="mac-iceland",
        aliases=("maciceland",),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-iceland",
        languages=("is",),
    ),
    EncodingInfo(
        name="mac-latin2",
        aliases=("maclatin2", "maccentraleurope"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-latin2",
        languages=_CENTRAL_EU_NO_RO,
    ),
    EncodingInfo(
        name="mac-roman",
        aliases=("macroman", "macintosh"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-roman",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="mac-turkish",
        aliases=("macturkish",),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-turkish",
        languages=("tr",),
    ),
    # === LEGACY_REGIONAL ===
    EncodingInfo(
        name="cp720",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="cp720",
        languages=_ARABIC,
    ),
    EncodingInfo(
        name="cp1006",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="cp1006",
        languages=("ur",),
    ),
    EncodingInfo(
        name="cp1125",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="cp1125",
        languages=("uk",),
    ),
    EncodingInfo(
        name="koi8-t",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="koi8-t",
        languages=("tg",),
    ),
    EncodingInfo(
        name="kz-1048",
        aliases=("kz1048", "strk1048-2002", "rk1048"),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="kz1048",
        languages=("kk",),
    ),
    EncodingInfo(
        name="ptcp154",
        aliases=("pt154", "cp154"),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="ptcp154",
        languages=("kk",),
    ),
    EncodingInfo(
        name="hp-roman8",
        aliases=("roman8", "r8", "csHPRoman8"),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="hp-roman8",
        languages=_WESTERN,
    ),
    # === DOS ===
    EncodingInfo(
        name="cp437",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp437",
        languages=("en", "fr", "de", "es", "pt", "it", "nl", "da", "sv", "fi"),
    ),
    EncodingInfo(
        name="cp737",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp737",
        languages=("el",),
    ),
    EncodingInfo(
        name="cp775",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp775",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="cp850",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp850",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="cp852",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp852",
        languages=_CENTRAL_EU_NO_RO,
    ),
    EncodingInfo(
        name="cp855",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp855",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="cp856",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp856",
        languages=("he",),
    ),
    EncodingInfo(
        name="cp857",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp857",
        languages=("tr",),
    ),
    EncodingInfo(
        name="cp858",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp858",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="cp860",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp860",
        languages=("pt",),
    ),
    EncodingInfo(
        name="cp861",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp861",
        languages=("is",),
    ),
    EncodingInfo(
        name="cp862",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp862",
        languages=("he",),
    ),
    EncodingInfo(
        name="cp863",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp863",
        languages=("fr",),
    ),
    EncodingInfo(
        name="cp864",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp864",
        languages=("ar",),
    ),
    EncodingInfo(
        name="cp865",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp865",
        languages=("da", "no"),
    ),
    EncodingInfo(
        name="cp866",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp866",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="cp869",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp869",
        languages=("el",),
    ),
    # === MAINFRAME ===
    EncodingInfo(
        name="cp1140",
        aliases=("cp037",),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp1140",
        languages=_WESTERN_TR,
    ),
    EncodingInfo(
        name="cp424",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp424",
        languages=("he",),
    ),
    EncodingInfo(
        name="cp500",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp500",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="cp875",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp875",
        languages=("el",),
    ),
    EncodingInfo(
        name="cp1026",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp1026",
        languages=("tr",),
    ),
    EncodingInfo(
        name="cp273",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp273",
        languages=("de",),
    ),
)

REGISTRY: MappingProxyType[str, EncodingInfo] = MappingProxyType(
    {e.name: e for e in _REGISTRY_ENTRIES}
)

_LOOKUP_CACHE: dict[str, EncodingName] | None = None
_LOOKUP_CACHE_LOCK = threading.Lock()


def _build_lookup_cache() -> dict[str, EncodingName]:
    """Build a case-insensitive lookup table from all known encoding names."""
    cache: dict[str, EncodingName] = {}
    for entry in REGISTRY.values():
        cache[entry.name.lower()] = entry.name  # type: ignore[assignment]
    for entry in REGISTRY.values():
        for alias in entry.aliases:
            cache.setdefault(alias.lower(), entry.name)  # type: ignore[assignment]
    codec_to_name: dict[str, EncodingName] = {}
    for entry in REGISTRY.values():
        try:
            codec_name = codecs.lookup(entry.python_codec).name
            codec_to_name.setdefault(codec_name, entry.name)  # type: ignore[assignment]
        except LookupError:
            pass
    cache.update({k: v for k, v in codec_to_name.items() if k not in cache})
    return cache


def lookup_encoding(name: str) -> EncodingName | None:
    """Convert an encoding name string to the canonical EncodingName.

    Handles arbitrary casing, aliases, and Python codec names.

    :param name: Any encoding name string.
    :returns: The canonical :data:`EncodingName`, or ``None`` if unknown.
    """
    global _LOOKUP_CACHE  # noqa: PLW0603
    if _LOOKUP_CACHE is None:
        with _LOOKUP_CACHE_LOCK:
            if _LOOKUP_CACHE is None:
                _LOOKUP_CACHE = _build_lookup_cache()
    result = _LOOKUP_CACHE.get(name.lower())
    if result is not None:
        return result
    try:
        codec_name = codecs.lookup(name).name
        return _LOOKUP_CACHE.get(codec_name)
    except LookupError:
        return None
