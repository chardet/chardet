"""Encoding registry with metadata for all supported encodings."""

from __future__ import annotations

import codecs
import dataclasses
import threading
from types import MappingProxyType
from typing import Literal

from chardet.enums import EncodingEra

EncodingName = Literal[
    "ASCII",
    "Big5-HKSCS",
    "CP1006",
    "CP1026",
    "CP1125",
    "CP1140",
    "CP273",
    "CP424",
    "CP437",
    "CP500",
    "CP720",
    "CP737",
    "CP775",
    "CP850",
    "CP852",
    "CP855",
    "CP856",
    "CP857",
    "CP858",
    "CP860",
    "CP861",
    "CP862",
    "CP863",
    "CP864",
    "CP865",
    "CP866",
    "CP869",
    "CP874",
    "CP875",
    "CP932",
    "CP949",
    "EUC-JIS-2004",
    "EUC-KR",
    "GB18030",
    "HP-Roman8",
    "HZ-GB-2312",
    "ISO-2022-JP-2",
    "ISO-2022-JP-2004",
    "ISO-2022-JP-EXT",
    "ISO-2022-KR",
    "ISO-8859-1",
    "ISO-8859-10",
    "ISO-8859-13",
    "ISO-8859-14",
    "ISO-8859-15",
    "ISO-8859-16",
    "ISO-8859-2",
    "ISO-8859-3",
    "ISO-8859-4",
    "ISO-8859-5",
    "ISO-8859-6",
    "ISO-8859-7",
    "ISO-8859-8",
    "ISO-8859-9",
    "Johab",
    "KOI8-R",
    "KOI8-T",
    "KOI8-U",
    "KZ-1048",
    "Mac-Cyrillic",
    "Mac-Greek",
    "Mac-Iceland",
    "Mac-Latin2",
    "Mac-Roman",
    "Mac-Turkish",
    "PTCP154",
    "Shift-JIS-2004",
    "TIS-620",
    "UTF-16",
    "UTF-16-BE",
    "UTF-16-LE",
    "UTF-32",
    "UTF-32-BE",
    "UTF-32-LE",
    "UTF-7",
    "UTF-8",
    "UTF-8-SIG",
    "Windows-1250",
    "Windows-1251",
    "Windows-1252",
    "Windows-1253",
    "Windows-1254",
    "Windows-1255",
    "Windows-1256",
    "Windows-1257",
    "Windows-1258",
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

    name: EncodingName
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
        name="ASCII",
        aliases=("us-ascii",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="ascii",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-8",
        aliases=("utf-8", "utf8"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-8",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-8-SIG",
        aliases=("utf-8-bom",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-8-sig",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-16",
        aliases=("utf16",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-16",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-16-BE",
        aliases=("utf-16be",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-16-be",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-16-LE",
        aliases=("utf-16le",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-16-le",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-32",
        aliases=("utf32",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-32",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-32-BE",
        aliases=("utf-32be",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-32-be",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-32-LE",
        aliases=("utf-32le",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="utf-32-le",
        languages=(),
    ),
    EncodingInfo(
        name="UTF-7",
        aliases=("utf7",),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="utf-7",
        languages=(),
    ),
    # CJK - Modern Web
    EncodingInfo(
        name="Big5-HKSCS",
        aliases=("Big5HKSCS", "big5", "big5-tw", "csbig5", "cp950"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="big5hkscs",
        languages=("zh",),
    ),
    EncodingInfo(
        name="CP932",
        aliases=("ms932", "mskanji", "ms-kanji"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="cp932",
        languages=("ja",),
    ),
    EncodingInfo(
        name="CP949",
        aliases=("ms949", "uhc"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="cp949",
        languages=("ko",),
    ),
    EncodingInfo(
        name="EUC-JIS-2004",
        aliases=("euc-jp", "eucjp", "ujis", "u-jis", "euc-jisx0213"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="euc_jis_2004",
        languages=("ja",),
    ),
    EncodingInfo(
        name="EUC-KR",
        aliases=("euckr",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="euc-kr",
        languages=("ko",),
    ),
    EncodingInfo(
        name="GB18030",
        aliases=("gb-18030", "gb2312", "gbk"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="gb18030",
        languages=("zh",),
    ),
    EncodingInfo(
        name="HZ-GB-2312",
        aliases=("hz",),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=True,
        python_codec="hz",
        languages=("zh",),
    ),
    EncodingInfo(
        name="ISO-2022-JP-2",
        aliases=("iso-2022-jp", "csiso2022jp", "iso2022-jp-1"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="iso2022_jp_2",
        languages=("ja",),
    ),
    EncodingInfo(
        name="ISO-2022-JP-2004",
        aliases=("iso2022-jp-3",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="iso2022_jp_2004",
        languages=("ja",),
    ),
    EncodingInfo(
        name="ISO-2022-JP-EXT",
        aliases=(),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="iso2022_jp_ext",
        languages=("ja",),
    ),
    EncodingInfo(
        name="ISO-2022-KR",
        aliases=("csiso2022kr",),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=True,
        python_codec="iso2022-kr",
        languages=("ko",),
    ),
    EncodingInfo(
        name="Shift-JIS-2004",
        aliases=(
            "Shift_JIS_2004",
            "shift_jis",
            "sjis",
            "shiftjis",
            "s_jis",
            "shift-jisx0213",
        ),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=True,
        python_codec="shift_jis_2004",
        languages=("ja",),
    ),
    # Windows code pages - Modern Web
    EncodingInfo(
        name="CP874",
        aliases=("windows-874",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp874",
        languages=("th",),
    ),
    EncodingInfo(
        name="Windows-1250",
        aliases=("cp1250",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1250",
        languages=_CENTRAL_EU,
    ),
    EncodingInfo(
        name="Windows-1251",
        aliases=("cp1251",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1251",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="Windows-1252",
        aliases=("cp1252",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1252",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="Windows-1253",
        aliases=("cp1253",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1253",
        languages=("el",),
    ),
    EncodingInfo(
        name="Windows-1254",
        aliases=("cp1254",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1254",
        languages=("tr",),
    ),
    EncodingInfo(
        name="Windows-1255",
        aliases=("cp1255",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1255",
        languages=("he",),
    ),
    EncodingInfo(
        name="Windows-1256",
        aliases=("cp1256",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1256",
        languages=_ARABIC,
    ),
    EncodingInfo(
        name="Windows-1257",
        aliases=("cp1257",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1257",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="Windows-1258",
        aliases=("cp1258",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="cp1258",
        languages=("vi",),
    ),
    # KOI8 - Modern Web
    EncodingInfo(
        name="KOI8-R",
        aliases=("koi8r",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="koi8-r",
        languages=("ru",),
    ),
    EncodingInfo(
        name="KOI8-U",
        aliases=("koi8u",),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="koi8-u",
        languages=("uk",),
    ),
    # TIS-620 - Modern Web
    EncodingInfo(
        name="TIS-620",
        aliases=("tis620", "iso-8859-11"),
        era=EncodingEra.MODERN_WEB,
        is_multibyte=False,
        python_codec="tis-620",
        languages=("th",),
    ),
    # === LEGACY_ISO ===
    EncodingInfo(
        name="ISO-8859-1",
        aliases=("latin-1", "latin1", "iso8859-1"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-1",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="ISO-8859-2",
        aliases=("latin-2", "latin2", "iso8859-2"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-2",
        languages=_CENTRAL_EU,
    ),
    EncodingInfo(
        name="ISO-8859-3",
        aliases=("latin-3", "latin3", "iso8859-3"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-3",
        languages=("eo", "mt", "tr"),
    ),
    EncodingInfo(
        name="ISO-8859-4",
        aliases=("latin-4", "latin4", "iso8859-4"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-4",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="ISO-8859-5",
        aliases=("iso8859-5", "cyrillic"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-5",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="ISO-8859-6",
        aliases=("iso8859-6", "arabic"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-6",
        languages=_ARABIC,
    ),
    EncodingInfo(
        name="ISO-8859-7",
        aliases=("iso8859-7", "greek"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-7",
        languages=("el",),
    ),
    EncodingInfo(
        name="ISO-8859-8",
        aliases=("iso8859-8", "hebrew"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-8",
        languages=("he",),
    ),
    EncodingInfo(
        name="ISO-8859-9",
        aliases=("latin-5", "latin5", "iso8859-9"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-9",
        languages=("tr",),
    ),
    EncodingInfo(
        name="ISO-8859-10",
        aliases=("latin-6", "latin6", "iso8859-10"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-10",
        languages=("is", "fi"),
    ),
    EncodingInfo(
        name="ISO-8859-13",
        aliases=("latin-7", "latin7", "iso8859-13"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-13",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="ISO-8859-14",
        aliases=("latin-8", "latin8", "iso8859-14"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-14",
        languages=("cy", "ga", "br", "gd"),
    ),
    EncodingInfo(
        name="ISO-8859-15",
        aliases=("latin-9", "latin9", "iso8859-15"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-15",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="ISO-8859-16",
        aliases=("latin-10", "latin10", "iso8859-16"),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=False,
        python_codec="iso-8859-16",
        languages=("ro", "pl", "hr", "hu", "sk", "sl"),
    ),
    # Johab - Legacy ISO per chardet 6.0.0
    EncodingInfo(
        name="Johab",
        aliases=(),
        era=EncodingEra.LEGACY_ISO,
        is_multibyte=True,
        python_codec="johab",
        languages=("ko",),
    ),
    # === LEGACY_MAC ===
    EncodingInfo(
        name="Mac-Cyrillic",
        aliases=("MacCyrillic", "maccyrillic"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-cyrillic",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="Mac-Greek",
        aliases=("MacGreek", "macgreek"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-greek",
        languages=("el",),
    ),
    EncodingInfo(
        name="Mac-Iceland",
        aliases=("MacIceland", "maciceland"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-iceland",
        languages=("is",),
    ),
    EncodingInfo(
        name="Mac-Latin2",
        aliases=("MacLatin2", "maclatin2", "maccentraleurope"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-latin2",
        languages=_CENTRAL_EU_NO_RO,
    ),
    EncodingInfo(
        name="Mac-Roman",
        aliases=("MacRoman", "macroman", "macintosh"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-roman",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="Mac-Turkish",
        aliases=("MacTurkish", "macturkish"),
        era=EncodingEra.LEGACY_MAC,
        is_multibyte=False,
        python_codec="mac-turkish",
        languages=("tr",),
    ),
    # === LEGACY_REGIONAL ===
    EncodingInfo(
        name="CP720",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="cp720",
        languages=_ARABIC,
    ),
    EncodingInfo(
        name="CP1006",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="cp1006",
        languages=("ur",),
    ),
    EncodingInfo(
        name="CP1125",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="cp1125",
        languages=("uk",),
    ),
    EncodingInfo(
        name="KOI8-T",
        aliases=(),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="koi8-t",
        languages=("tg",),
    ),
    EncodingInfo(
        name="KZ-1048",
        aliases=("kz1048", "strk1048-2002", "rk1048"),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="kz1048",
        languages=("kk",),
    ),
    EncodingInfo(
        name="PTCP154",
        aliases=("pt154", "cp154"),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="ptcp154",
        languages=("kk",),
    ),
    EncodingInfo(
        name="HP-Roman8",
        aliases=("roman8", "r8", "csHPRoman8"),
        era=EncodingEra.LEGACY_REGIONAL,
        is_multibyte=False,
        python_codec="hp-roman8",
        languages=_WESTERN,
    ),
    # === DOS ===
    EncodingInfo(
        name="CP437",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp437",
        languages=("en", "fr", "de", "es", "pt", "it", "nl", "da", "sv", "fi"),
    ),
    EncodingInfo(
        name="CP737",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp737",
        languages=("el",),
    ),
    EncodingInfo(
        name="CP775",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp775",
        languages=_BALTIC,
    ),
    EncodingInfo(
        name="CP850",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp850",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="CP852",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp852",
        languages=_CENTRAL_EU_NO_RO,
    ),
    EncodingInfo(
        name="CP855",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp855",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="CP856",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp856",
        languages=("he",),
    ),
    EncodingInfo(
        name="CP857",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp857",
        languages=("tr",),
    ),
    EncodingInfo(
        name="CP858",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp858",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="CP860",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp860",
        languages=("pt",),
    ),
    EncodingInfo(
        name="CP861",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp861",
        languages=("is",),
    ),
    EncodingInfo(
        name="CP862",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp862",
        languages=("he",),
    ),
    EncodingInfo(
        name="CP863",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp863",
        languages=("fr",),
    ),
    EncodingInfo(
        name="CP864",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp864",
        languages=("ar",),
    ),
    EncodingInfo(
        name="CP865",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp865",
        languages=("da", "no"),
    ),
    EncodingInfo(
        name="CP866",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp866",
        languages=_CYRILLIC,
    ),
    EncodingInfo(
        name="CP869",
        aliases=(),
        era=EncodingEra.DOS,
        is_multibyte=False,
        python_codec="cp869",
        languages=("el",),
    ),
    # === MAINFRAME ===
    EncodingInfo(
        name="CP1140",
        aliases=("cp037",),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp1140",
        languages=_WESTERN_TR,
    ),
    EncodingInfo(
        name="CP424",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp424",
        languages=("he",),
    ),
    EncodingInfo(
        name="CP500",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp500",
        languages=_WESTERN,
    ),
    EncodingInfo(
        name="CP875",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp875",
        languages=("el",),
    ),
    EncodingInfo(
        name="CP1026",
        aliases=(),
        era=EncodingEra.MAINFRAME,
        is_multibyte=False,
        python_codec="cp1026",
        languages=("tr",),
    ),
    EncodingInfo(
        name="CP273",
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
        cache[entry.name.lower()] = entry.name
    for entry in REGISTRY.values():
        for alias in entry.aliases:
            cache.setdefault(alias.lower(), entry.name)
    codec_to_name: dict[str, EncodingName] = {}
    for entry in REGISTRY.values():
        try:
            codec_name = codecs.lookup(entry.python_codec).name
            codec_to_name.setdefault(codec_name, entry.name)
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
