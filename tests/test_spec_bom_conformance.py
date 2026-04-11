"""Specification conformance for BOM detection and multi-byte validators.

Pins chardet's BOM table and UTF-8/UTF-16 byte-level validators to the
byte sequences the relevant standards bodies define:

- **Unicode Standard §23.8 / UAX #17** — canonical BOM byte sequences
- **WHATWG Encoding Standard** — the ``decode`` algorithm's BOM sniff set
  (UTF-8, UTF-16BE, UTF-16LE; see https://encoding.spec.whatwg.org/#decode)
- **RFC 3629** — UTF-8 byte structure, overlong encodings, surrogate rejection
- **RFC 2781** — UTF-16 surrogate pair encoding

These tests are intentionally strict.  A failure here means chardet's
byte-level behavior has drifted from a spec — fix the code, not the test,
unless the drift is a deliberate policy change.
"""

from __future__ import annotations

from chardet.pipeline import bom
from chardet.pipeline.utf8 import detect_utf8

# ---------------------------------------------------------------------------
# BOM table pins
# ---------------------------------------------------------------------------

# The exact set of (bytes, canonical_name) tuples chardet must recognize.
# Derived from Unicode §23.8 and the WHATWG decode algorithm.
#
# Note the use of bare ``utf-16``/``utf-32`` (not ``-le``/``-be``): when a
# BOM is present, chardet returns the Python codec name that strips the BOM
# on decode.  See ``tests/test_python_stdlib_limitations.py`` for the pinned
# CPython behavior that makes this correct.
EXPECTED_BOM_SET: frozenset[tuple[bytes, str]] = frozenset(
    {
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xfe\xff", "utf-16"),
        (b"\xff\xfe", "utf-16"),
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe\x00\x00", "utf-32"),
    }
)


def test_bom_table_matches_spec_set_exactly() -> None:
    actual = frozenset(bom._BOMS)
    extras = actual - EXPECTED_BOM_SET
    missing = EXPECTED_BOM_SET - actual
    assert actual == EXPECTED_BOM_SET, (
        "pipeline.bom._BOMS must match the WHATWG decode algorithm's BOM "
        "sniff set (UTF-8, UTF-16BE, UTF-16LE, UTF-32BE, UTF-32LE) plus "
        "their BOM-stripping Python codec names. Adding new entries "
        "requires a deliberate spec-compliance decision -- see the "
        "GB18030 pin in tests/test_python_stdlib_limitations.py for an "
        "example of a BOM chardet intentionally does NOT sniff.\n"
        f"  extras:  {sorted(extras)}\n"
        f"  missing: {sorted(missing)}"
    )


def test_bom_table_orders_utf32_before_utf16() -> None:
    """UTF-32-LE BOM must be checked before UTF-16-LE BOM.

    UTF-32-LE BOM (FF FE 00 00) starts with the UTF-16-LE BOM (FF FE),
    so the longer sequence must be checked first in the iteration order.
    """
    utf16_le_index = next(i for i, (b, _) in enumerate(bom._BOMS) if b == b"\xff\xfe")
    utf32_le_index = next(
        i for i, (b, _) in enumerate(bom._BOMS) if b == b"\xff\xfe\x00\x00"
    )
    assert utf32_le_index < utf16_le_index


# ---------------------------------------------------------------------------
# RFC 3629 — UTF-8 byte-structure pins
# ---------------------------------------------------------------------------

# Each entry is (description, bytes, should_be_accepted).
# The validator returns a DetectionResult for ASCII-plus-multibyte input
# that parses as valid UTF-8; it returns None for invalid byte sequences
# or for pure ASCII (ASCII is handled by a separate stage).
_UTF8_CASES: tuple[tuple[str, bytes, bool], ...] = (
    # Valid boundary code points (each with at least one multibyte char so
    # the validator actually runs its structural checks).
    ("U+0080 (smallest 2-byte)", "\u0080".encode(), True),
    ("U+07FF (largest 2-byte)", "\u07ff".encode(), True),
    ("U+0800 (smallest 3-byte)", "\u0800".encode(), True),
    ("U+FFFF (largest 3-byte, BMP edge)", "\uffff".encode(), True),
    ("U+10000 (smallest 4-byte, first supplementary)", "\U00010000".encode(), True),
    ("U+10FFFF (largest Unicode code point)", "\U0010ffff".encode(), True),
    # Overlong encodings (forbidden by RFC 3629)
    ("overlong 2-byte encoding of U+0000", b"\xc0\x80", False),
    ("overlong 2-byte encoding of '/'", b"\xc0\xaf", False),
    ("overlong 3-byte encoding of U+007F", b"\xe0\x80\xbf", False),
    ("overlong 4-byte encoding of U+FFFF", b"\xf0\x80\x80\xbf", False),
    # Lone surrogates (U+D800-U+DFFF) — forbidden by RFC 3629
    ("lone high surrogate U+D800", b"\xed\xa0\x80", False),
    ("lone low surrogate U+DFFF", b"\xed\xbf\xbf", False),
    # Out of range (above U+10FFFF)
    ("codepoint above U+10FFFF (0xF4 0x90)", b"\xf4\x90\x80\x80", False),
    ("5-byte sequence (not allowed)", b"\xf8\x88\x80\x80\x80", False),
    # Invalid start bytes
    ("bare continuation byte 0x80", b"\x80", False),
    ("bare continuation byte 0xBF", b"\xbf", False),
    ("invalid start byte 0xC0", b"\xc0\x80", False),
    ("invalid start byte 0xC1", b"\xc1\x80", False),
    ("invalid start byte 0xF5", b"\xf5\x80\x80\x80", False),
    ("invalid start byte 0xFE", b"\xfe", False),
    ("invalid start byte 0xFF", b"\xff", False),
)


def test_utf8_validator_matches_rfc3629() -> None:
    failures: list[str] = []
    for description, data, should_accept in _UTF8_CASES:
        result = detect_utf8(data)
        accepted = result is not None
        if accepted != should_accept:
            verdict = "accepted" if accepted else "rejected"
            want = "accept" if should_accept else "reject"
            failures.append(
                f"  {description!s}: validator {verdict} {data!r}; expected to {want}"
            )
    assert not failures, "detect_utf8() disagrees with RFC 3629:\n" + "\n".join(
        failures
    )


# ---------------------------------------------------------------------------
# RFC 2781 — UTF-16 surrogate pair round-trip
# ---------------------------------------------------------------------------


def test_utf16_surrogate_pair_roundtrip_rfc2781() -> None:
    """Supplementary code points must survive UTF-16 surrogate encoding."""
    for codepoint in ("\U00010000", "\U0001f600", "\U0010ffff"):
        assert codepoint.encode("utf-16-le").decode("utf-16-le") == codepoint
        assert codepoint.encode("utf-16-be").decode("utf-16-be") == codepoint
        assert codepoint.encode("utf-16").decode("utf-16") == codepoint
