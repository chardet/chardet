"""WHATWG Encoding Standard compliance via markup end-to-end behavior.

Validates that ``chardet.detect()`` honors ``<meta charset="...">``
declarations whose label appears in the WHATWG Encoding Standard.  This
tests the **real user-facing path**: when chardet sees a web page with a
declared charset, does it route the label through to the correct decoder?

Direction is **one-way** (WHATWG → chardet).  For each WHATWG label this
test constructs a small HTML fragment:

    <meta charset="{label}">
    <body>Hello, world!</body>

feeds it to ``chardet.detect()``, and asserts the returned encoding maps
to WHATWG's group name through :data:`_WHATWG_TO_CHARDET`.

The equivalence map is **lenient**: WHATWG puts ``iso-8859-1``, ``ascii``,
``latin1``, and ``windows-1252`` all under the single group ``windows-1252``
(because browsers decode them as cp1252), but chardet keeps them as distinct
canonical entries (``iso8859-1``, ``ascii``, ``cp1252``) for detection
accuracy.  The map therefore accepts any chardet canonical that is in the
same character-set family.

Two WHATWG entries are deliberately skipped:

* ``replacement`` — a browser security mitigation that refuses to decode
  certain legacy labels (``iso-2022-kr``, ``hz-gb-2312``, etc.), returning
  U+FFFD.  Chardet is a detector, not a browser, and legitimately supports
  these encodings.
* ``x-user-defined`` — a browser-internal codec for binary data.

UTF-16/UTF-32 labels are also skipped because a ``<meta charset>``
declaration cannot sit inside a UTF-16/32 byte stream with ASCII tag syntax
the markup scanner recognises; those encodings are detected via BOM or
null-byte pattern detection in separate pipeline stages.
"""

from __future__ import annotations

import pytest

import chardet
from chardet.registry import REGISTRY, lookup_encoding

# Source: https://encoding.spec.whatwg.org/encodings.json
# Snapshot: 2026-04-10
# Last upstream change: 2020-05-06 (effectively frozen).
# Refresh = re-fetch encodings.json and paste the new labels/names here.
WHATWG_ENCODINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "UTF-8",
        (
            "unicode-1-1-utf-8",
            "unicode11utf8",
            "unicode20utf8",
            "utf-8",
            "utf8",
            "x-unicode20utf8",
        ),
    ),
    ("IBM866", ("866", "cp866", "csibm866", "ibm866")),
    (
        "ISO-8859-2",
        (
            "csisolatin2",
            "iso-8859-2",
            "iso-ir-101",
            "iso8859-2",
            "iso88592",
            "iso_8859-2",
            "iso_8859-2:1987",
            "l2",
            "latin2",
        ),
    ),
    (
        "ISO-8859-3",
        (
            "csisolatin3",
            "iso-8859-3",
            "iso-ir-109",
            "iso8859-3",
            "iso88593",
            "iso_8859-3",
            "iso_8859-3:1988",
            "l3",
            "latin3",
        ),
    ),
    (
        "ISO-8859-4",
        (
            "csisolatin4",
            "iso-8859-4",
            "iso-ir-110",
            "iso8859-4",
            "iso88594",
            "iso_8859-4",
            "iso_8859-4:1988",
            "l4",
            "latin4",
        ),
    ),
    (
        "ISO-8859-5",
        (
            "csisolatincyrillic",
            "cyrillic",
            "iso-8859-5",
            "iso-ir-144",
            "iso8859-5",
            "iso88595",
            "iso_8859-5",
            "iso_8859-5:1988",
        ),
    ),
    (
        "ISO-8859-6",
        (
            "arabic",
            "asmo-708",
            "csiso88596e",
            "csiso88596i",
            "csisolatinarabic",
            "ecma-114",
            "iso-8859-6",
            "iso-8859-6-e",
            "iso-8859-6-i",
            "iso-ir-127",
            "iso8859-6",
            "iso88596",
            "iso_8859-6",
            "iso_8859-6:1987",
        ),
    ),
    (
        "ISO-8859-7",
        (
            "csisolatingreek",
            "ecma-118",
            "elot_928",
            "greek",
            "greek8",
            "iso-8859-7",
            "iso-ir-126",
            "iso8859-7",
            "iso88597",
            "iso_8859-7",
            "iso_8859-7:1987",
            "sun_eu_greek",
        ),
    ),
    (
        "ISO-8859-8",
        (
            "csiso88598e",
            "csisolatinhebrew",
            "hebrew",
            "iso-8859-8",
            "iso-8859-8-e",
            "iso-ir-138",
            "iso8859-8",
            "iso88598",
            "iso_8859-8",
            "iso_8859-8:1988",
            "visual",
        ),
    ),
    ("ISO-8859-8-I", ("csiso88598i", "iso-8859-8-i", "logical")),
    (
        "ISO-8859-10",
        (
            "csisolatin6",
            "iso-8859-10",
            "iso-ir-157",
            "iso8859-10",
            "iso885910",
            "l6",
            "latin6",
        ),
    ),
    ("ISO-8859-13", ("iso-8859-13", "iso8859-13", "iso885913")),
    ("ISO-8859-14", ("iso-8859-14", "iso8859-14", "iso885914")),
    (
        "ISO-8859-15",
        (
            "csisolatin9",
            "iso-8859-15",
            "iso8859-15",
            "iso885915",
            "iso_8859-15",
            "l9",
        ),
    ),
    ("ISO-8859-16", ("iso-8859-16",)),
    ("KOI8-R", ("cskoi8r", "koi", "koi8", "koi8-r", "koi8_r")),
    ("KOI8-U", ("koi8-ru", "koi8-u")),
    ("macintosh", ("csmacintosh", "mac", "macintosh", "x-mac-roman")),
    (
        "windows-874",
        (
            "dos-874",
            "iso-8859-11",
            "iso8859-11",
            "iso885911",
            "tis-620",
            "windows-874",
        ),
    ),
    ("windows-1250", ("cp1250", "windows-1250", "x-cp1250")),
    ("windows-1251", ("cp1251", "windows-1251", "x-cp1251")),
    (
        "windows-1252",
        (
            "ansi_x3.4-1968",
            "ascii",
            "cp1252",
            "cp819",
            "csisolatin1",
            "ibm819",
            "iso-8859-1",
            "iso-ir-100",
            "iso8859-1",
            "iso88591",
            "iso_8859-1",
            "iso_8859-1:1987",
            "l1",
            "latin1",
            "us-ascii",
            "windows-1252",
            "x-cp1252",
        ),
    ),
    ("windows-1253", ("cp1253", "windows-1253", "x-cp1253")),
    (
        "windows-1254",
        (
            "cp1254",
            "csisolatin5",
            "iso-8859-9",
            "iso-ir-148",
            "iso8859-9",
            "iso88599",
            "iso_8859-9",
            "iso_8859-9:1989",
            "l5",
            "latin5",
            "windows-1254",
            "x-cp1254",
        ),
    ),
    ("windows-1255", ("cp1255", "windows-1255", "x-cp1255")),
    ("windows-1256", ("cp1256", "windows-1256", "x-cp1256")),
    ("windows-1257", ("cp1257", "windows-1257", "x-cp1257")),
    ("windows-1258", ("cp1258", "windows-1258", "x-cp1258")),
    ("x-mac-cyrillic", ("x-mac-cyrillic", "x-mac-ukrainian")),
    (
        "GBK",
        (
            "chinese",
            "csgb2312",
            "csiso58gb231280",
            "gb2312",
            "gb_2312",
            "gb_2312-80",
            "gbk",
            "iso-ir-58",
            "x-gbk",
        ),
    ),
    ("gb18030", ("gb18030",)),
    ("Big5", ("big5", "big5-hkscs", "cn-big5", "csbig5", "x-x-big5")),
    ("EUC-JP", ("cseucpkdfmtjapanese", "euc-jp", "x-euc-jp")),
    ("ISO-2022-JP", ("csiso2022jp", "iso-2022-jp")),
    (
        "Shift_JIS",
        (
            "csshiftjis",
            "ms932",
            "ms_kanji",
            "shift-jis",
            "shift_jis",
            "sjis",
            "windows-31j",
            "x-sjis",
        ),
    ),
    (
        "EUC-KR",
        (
            "cseuckr",
            "csksc56011987",
            "euc-kr",
            "iso-ir-149",
            "korean",
            "ks_c_5601-1987",
            "ks_c_5601-1989",
            "ksc5601",
            "ksc_5601",
            "windows-949",
        ),
    ),
)

# Chardet canonicals that are accepted for each WHATWG group.  This map
# is the *exact* set of canonicals chardet's markup stage returns for the
# labels in each group -- computed empirically and kept tight, so that if
# chardet's routing policy ever shifts, this test fails loudly.  Several
# WHATWG groups map to multiple chardet canonicals because WHATWG lumps
# character sets that chardet keeps split for detection accuracy
# (``windows-1252`` contains labels that chardet routes to any of
# ``cp1252``, ``iso8859-1``, or ``ascii``; ``EUC-KR`` splits between
# ``euc_kr`` and ``cp949`` depending on which label is used; etc.).
_WHATWG_TO_CHARDET: dict[str, frozenset[str]] = {
    "UTF-8": frozenset({"utf-8"}),
    "IBM866": frozenset({"cp866"}),
    "ISO-8859-2": frozenset({"iso8859-2"}),
    "ISO-8859-3": frozenset({"iso8859-3"}),
    "ISO-8859-4": frozenset({"iso8859-4"}),
    "ISO-8859-5": frozenset({"iso8859-5"}),
    "ISO-8859-6": frozenset({"iso8859-6"}),
    "ISO-8859-7": frozenset({"iso8859-7"}),
    "ISO-8859-8": frozenset({"iso8859-8"}),
    "ISO-8859-8-I": frozenset({"iso8859-8"}),
    "ISO-8859-10": frozenset({"iso8859-10"}),
    "ISO-8859-13": frozenset({"iso8859-13"}),
    "ISO-8859-14": frozenset({"iso8859-14"}),
    "ISO-8859-15": frozenset({"iso8859-15"}),
    "ISO-8859-16": frozenset({"iso8859-16"}),
    "KOI8-R": frozenset({"koi8-r"}),
    "KOI8-U": frozenset({"koi8-u"}),
    "macintosh": frozenset({"mac-roman"}),
    # WHATWG merges dos-874, iso-8859-11, tis-620, and windows-874 all
    # under "windows-874" (the Microsoft superset).  Chardet instead
    # routes the iso-8859-11 / tis-620 labels to its `tis-620` canonical
    # because Python's `tis-620` codec accepts undefined C1 bytes
    # (0x80-0x9F) without raising, whereas `cp874` can reject them --
    # routing the label the more permissive way is safer for decode.
    # The 0x80-0x9F range differs between the two (cp874 assigns e.g.
    # 0x85 -> U+2026 ...), but real-world Thai text rarely uses that
    # range, and the chardet accuracy corpus has no cp874/tis-620
    # regressions from this routing.
    "windows-874": frozenset({"cp874", "tis-620"}),
    "windows-1250": frozenset({"cp1250"}),
    "windows-1251": frozenset({"cp1251"}),
    # WHATWG lumps ascii + latin-1 + cp1252 into one group
    "windows-1252": frozenset({"ascii", "cp1252", "iso8859-1"}),
    "windows-1253": frozenset({"cp1253"}),
    # WHATWG puts iso-8859-9 under windows-1254
    "windows-1254": frozenset({"cp1254", "iso8859-9"}),
    "windows-1255": frozenset({"cp1255"}),
    "windows-1256": frozenset({"cp1256"}),
    "windows-1257": frozenset({"cp1257"}),
    "windows-1258": frozenset({"cp1258"}),
    "x-mac-cyrillic": frozenset({"mac-cyrillic"}),
    "GBK": frozenset({"gb18030"}),
    "gb18030": frozenset({"gb18030"}),
    "Big5": frozenset({"big5hkscs"}),
    "EUC-JP": frozenset({"euc_jis_2004"}),
    "ISO-2022-JP": frozenset({"iso2022_jp_2"}),
    # ms932 label routes to cp932 while shift_jis / sjis route to
    # shift_jis_2004 -- both are in WHATWG's Shift_JIS group.
    "Shift_JIS": frozenset({"cp932", "shift_jis_2004"}),
    # windows-949 / csksc56011987 route to cp949; euc-kr routes to euc_kr.
    "EUC-KR": frozenset({"cp949", "euc_kr"}),
}


def test_whatwg_equivalence_map_references_real_canonicals() -> None:
    """Every chardet canonical listed in ``_WHATWG_TO_CHARDET`` must exist.

    Guards against silent drift if a registry canonical is ever renamed
    without updating this map -- the markup test would otherwise fail with
    a misleading "chardet returned X but expected {nothing recognising X}"
    message instead of pointing at the stale reference.
    """
    unknown: list[tuple[str, str]] = []
    for whatwg_name, canonicals in _WHATWG_TO_CHARDET.items():
        for canonical in canonicals:
            if canonical not in REGISTRY:
                unknown.append((whatwg_name, canonical))
    assert not unknown, (
        "_WHATWG_TO_CHARDET references canonicals not in chardet.registry:\n"
        + "\n".join(f"  {whatwg!r} -> {canon!r}" for whatwg, canon in unknown)
    )


def _html_with_meta_charset(label: str) -> bytes:
    """Return an HTML fragment with a ``<meta charset>`` declaration.

    The markup scanner in ``src/chardet/pipeline/markup.py`` will recognise
    the declaration and call ``lookup_encoding(label)``.
    """
    # The markup scanner looks in the first ~1024 bytes.  Pure ASCII body
    # text validates under any ASCII-compatible charset (which is every
    # WHATWG single-byte + Chinese/Japanese/Korean encoding).
    return (
        f'<!DOCTYPE html><html><head><meta charset="{label}"></head>'
        f"<body>Hello, world! This is sample text.</body></html>"
    ).encode("ascii")


# Flatten WHATWG table to (primary_name, label) pairs for parametrisation.
_LABEL_PARAMS: list[tuple[str, str]] = [
    (name, label) for name, labels in WHATWG_ENCODINGS for label in labels
]


@pytest.mark.parametrize(
    ("whatwg_name", "label"),
    _LABEL_PARAMS,
    ids=[f"{name}:{label}" for name, label in _LABEL_PARAMS],
)
def test_markup_honours_whatwg_label(whatwg_name: str, label: str) -> None:
    """``<meta charset>`` must route to the expected chardet canonical.

    This exercises ``src/chardet/pipeline/markup.py``, which uses
    ``lookup_encoding()`` internally.  If the label does not resolve in
    chardet's alias tables *and* Python's codec registry does not know it
    either, the markup stage falls through to statistical detection and
    returns an unrelated encoding -- the assertion below will flag that.
    """
    html = _html_with_meta_charset(label)
    result = chardet.detect(html, compat_names=False)
    detected = result["encoding"]
    assert detected is not None, f"{whatwg_name}:{label}: detect returned no encoding"
    expected = _WHATWG_TO_CHARDET[whatwg_name]
    if detected not in expected:
        # Query the intermediate state so the failure message points at the
        # actual cause rather than guessing.  Three diagnostic cases:
        #   (a) lookup_encoding returns None -> label missing from registry
        #   (b) lookup_encoding returns a canonical not in the expected set
        #       -> existing alias points at the wrong chardet canonical
        #   (c) lookup_encoding is correct but markup _validate_bytes
        #       rejected it -> sample bytes don't decode under the label
        intermediate = lookup_encoding(label)
        pytest.fail(
            f"WHATWG {whatwg_name!r} label {label!r}: "
            f"chardet.detect -> {detected!r}, "
            f"lookup_encoding({label!r}) -> {intermediate!r}, "
            f"expected one of {sorted(expected)}.\n"
            f"  (a) if intermediate is None: add {label!r} as an alias\n"
            f"  (b) if intermediate is a wrong canonical: fix the existing "
            f"alias routing\n"
            f"  (c) if intermediate is correct but detect differs: the "
            f"markup stage's _validate_bytes rejected the sample under that "
            f"encoding and fell through to statistical detection"
        )
