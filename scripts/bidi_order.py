"""Visual-order reordering for encodings whose wild text used it.

Some right-to-left encodings were routinely written in *visual* order:
bytes stored in display order for a renderer with no bidi engine, so the
first byte of a Hebrew line is the rightmost character on screen.  A
detector model trained only on logical-order text has never seen the
byte bigrams such files actually contain -- they are all reversed.

``VISUAL_ORDER_DUAL_ENCODINGS`` lists the encodings whose training corpus
should carry *both* conventions, one sample each per article:

``iso8859-8``
    The one registry entry deliberately absorbs both IANA variants:
    ISO-8859-8(-E) declared visual order and dominated the 1990s Hebrew
    web, while ISO-8859-8-I declared logical order and won email and the
    later web (every wild iso-8859-8 file in the chardet test corpus is
    a logical-order 2003-era feed).  Training on both makes the reported
    name signal the storage convention, the behavior Mozilla's universal
    charset detector algorithm specified for Hebrew, obtained here from
    the statistics alone: visual input can only be explained by this
    model (windows-1255's is logical-only), and logical input prefers
    windows-1255.  Measured before landing: visual-only training instead
    dropped a small logical file to a Greek misread under era filtering
    and thinned every era-mode margin.

cp862 stays logical: both carved Hebrew MS-DOS 5.0 sources measure
logical order (final-form letters end words), because Microsoft's Hebrew
DOS shipped a bidi display engine.  cp864/cp1006 (presentation-form
Arabic) are expected to be visual when their shaped training lands;
extend the set with evidence when that happens.

Reordering is the Unicode Bidirectional Algorithm with an LTR base
paragraph -- exactly "what a dumb LTR renderer of the era displayed",
including mirrored brackets.  The backend is macOS libicucore via
ctypes, and deliberately ONLY that: python-bidi was measured and
rejected (its legacy module crashes on the isolate controls real corpus
text contains; its maintained Rust module omits bracket mirroring and
places zero-width spaces differently, diverging on 12% of corpus
lines), and retrained models must reproduce the shipped ones byte for
byte.  Do not substitute another UBA implementation without an
equivalence measurement, and never a hand-rolled reverser.
"""

from __future__ import annotations

import codecs

VISUAL_ORDER_DUAL_ENCODINGS: frozenset[str] = frozenset({"iso8859-8"})


def is_dual_order(encoding_name: str) -> bool:
    """Return whether *encoding_name* trains on both bidi storage orders.

    The one membership test for :data:`VISUAL_ORDER_DUAL_ENCODINGS`:
    every consumer (training, exclusion indexing) must resolve names the
    same way, so membership is decided under stdlib codec canonicalization
    here rather than per-caller.  An unknown codec is not a member.
    """
    try:
        canonical = codecs.lookup(encoding_name).name
    except LookupError:
        return False
    return canonical in VISUAL_ORDER_DUAL_ENCODINGS


_icu_shape = None


def _load_icu() -> None:
    import ctypes  # noqa: PLC0415
    import ctypes.util  # noqa: PLC0415

    global _icu_shape  # noqa: PLW0603
    path = ctypes.util.find_library("icucore")
    if path is None:
        msg = "visual-order reordering needs macOS libicucore"
        raise RuntimeError(msg)
    icu = ctypes.CDLL(path)
    ubidi_open = icu.ubidi_open
    ubidi_open.restype = ctypes.c_void_p
    ubidi_close = icu.ubidi_close
    ubidi_close.argtypes = [ctypes.c_void_p]
    ubidi_set_para = icu.ubidi_setPara
    ubidi_set_para.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.c_int32,
        ctypes.c_uint8,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    ubidi_write = icu.ubidi_writeReordered
    ubidi_write.restype = ctypes.c_int32
    ubidi_write.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.c_int32,
        ctypes.c_uint16,
        ctypes.POINTER(ctypes.c_int),
    ]
    do_mirroring = 2  # UBIDI_DO_MIRRORING

    def shape(line: str) -> str:
        units = line.encode("utf-16-le")
        n = len(units) // 2
        src = (ctypes.c_uint16 * n).from_buffer_copy(units)
        bidi = ubidi_open()
        try:
            err = ctypes.c_int(0)
            ubidi_set_para(bidi, src, n, 0, None, ctypes.byref(err))
            if err.value > 0:
                msg = f"ubidi_setPara error {err.value}"
                raise RuntimeError(msg)
            dest = (ctypes.c_uint16 * (n * 2 + 8))()
            err = ctypes.c_int(0)
            written = ubidi_write(
                bidi, dest, len(dest), do_mirroring, ctypes.byref(err)
            )
            if err.value > 0:
                msg = f"ubidi_writeReordered error {err.value}"
                raise RuntimeError(msg)
            return b"".join(u.to_bytes(2, "little") for u in dest[:written]).decode(
                "utf-16-le"
            )
        finally:
            ubidi_close(bidi)

    _icu_shape = shape


def reorder_visual(text: str) -> str:
    """Reorder logical-order *text* into visual order, line by line."""
    if _icu_shape is None:
        _load_icu()
    return "\n".join(_icu_shape(line) if line else line for line in text.split("\n"))
