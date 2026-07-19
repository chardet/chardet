from __future__ import annotations

import chardet
from chardet.output_names import _COMPAT_NAMES

# Per docs/usage.rst "Encoding names by parameter combination", compat_names=True
# (the default) must map every detected ISO-8859-N codec to its display name.
_EXPECTED = {
    "iso8859-2": "ISO-8859-2",
    "iso8859-6": "ISO-8859-6",
    "iso8859-13": "ISO-8859-13",
}


def test_compat_names_iso8859_2_6_13_display_cased() -> None:
    for codec, display in _EXPECTED.items():
        assert _COMPAT_NAMES[codec] == display


def test_detect_iso8859_6_returns_display_name() -> None:
    """Arabic ISO-8859-6 text detects with the compat display name by default."""
    data = ("هذا نص عربي طويل لاختبار كشف الترميز داخل المكتبة بشكل واقعي." * 3).encode(
        "iso8859-6"
    )
    assert chardet.detect(data)["encoding"] == "ISO-8859-6"


def test_include_encodings_iso8859_family_display_cased() -> None:
    """Forcing each codec via include_encodings yields the display name."""
    samples = {
        "iso8859-2": "Příliš žluťoučký kůň úpěl ódy",
        "iso8859-6": "هذا نص عربي طويل للاختبار",
        "iso8859-13": "Lietuvių ir latviešu valoda šeit",
    }
    for codec, display in _EXPECTED.items():
        data = samples[codec].encode(codec)
        got = chardet.detect(data, include_encodings=[codec])["encoding"]
        assert got == display, f"{codec}: expected {display!r}, got {got!r}"
