"""Pinned CPython standard-library behaviors that chardet depends on.

These tests do **not** exercise chardet's own code.  They codify upstream
invariants so that if CPython ever changes one of them, the chardet test
suite turns red and forces a deliberate response.  When a test here starts
failing, the right action is usually *not* to update this file — it is to
re-evaluate the chardet design decision that relied on the old behavior.
"""

from __future__ import annotations


def test_python_gb18030_bom_leak_still_present() -> None:
    r"""CPython's gb18030 codec does NOT strip the 0x84 0x31 0x95 0x33 BOM.

    This byte sequence is GB18030's encoding of U+FEFF (the byte-order-mark
    code point).  Python's ``gb18030`` codec decodes it to a literal
    ``"\\ufeff"`` character, and CPython ships no ``gb18030-sig`` variant.

    WHATWG's decode algorithm also does not sniff the GB18030 BOM — only
    UTF-8, UTF-16BE, and UTF-16LE.  Chardet follows that consensus and
    intentionally does not detect this byte sequence as a BOM
    (see ``tests/test_spec_bom_conformance.py``).

    If this test ever starts failing — i.e., CPython starts stripping the
    BOM — revisit that decision: chardet may then be able to safely return
    a bare ``gb18030`` for BOM-prefixed input without leaking U+FEFF.  Until
    then, users who encounter real-world BOM-prefixed GB18030 content must
    strip the leading ``\\ufeff`` themselves after decoding.
    """
    assert b"\x84\x31\x95\x33hello".decode("gb18030") == "\ufeffhello"


def test_python_utf16_strips_bom_on_decode() -> None:
    """CPython's ``utf-16`` codec strips a leading BOM on decode.

    This is the specific behavior commit 2a54c68 relies on: when a BOM is
    present, chardet returns the bare ``"utf-16"`` / ``"utf-32"`` names
    (not ``"-le"`` / ``"-be"``) so Python will consume the BOM for the
    user.  If this ever changes upstream, the BOM-detection stance in
    ``src/chardet/pipeline/bom.py`` must be revisited.
    """
    assert "Hello".encode("utf-16").decode("utf-16") == "Hello"
    assert "Hello".encode("utf-32").decode("utf-32") == "Hello"


def test_python_utf16_le_be_do_not_strip_bom() -> None:
    """CPython's ``utf-16-le``/``-be`` codecs do NOT strip a leading BOM.

    This is the bug class commit 2a54c68 closed: returning these names for
    BOM-prefixed input leaks a leading U+FEFF into the decoded string.
    """
    assert "Hello".encode("utf-16").decode("utf-16-le") == "\ufeffHello"
    assert "Hello".encode("utf-32").decode("utf-32-le") == "\ufeffHello"


def test_python_utf8_does_not_strip_bom_but_utf8_sig_does() -> None:
    """``utf-8`` leaks the BOM as U+FEFF; ``utf-8-sig`` strips it.

    Chardet returns ``"utf-8-sig"`` when a UTF-8 BOM is detected, relying
    on this distinction.
    """
    bom_prefixed = b"\xef\xbb\xbfHello"
    assert bom_prefixed.decode("utf-8") == "\ufeffHello"
    assert bom_prefixed.decode("utf-8-sig") == "Hello"
