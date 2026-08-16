"""Contextual Arabic shaping into a presentation-form codec's repertoire.

cp864 stores Arabic as *presentation forms*: one byte per contextual
glyph, chosen by position in the word, in an IBM two-form layout where
dual-joining letters carry only ISOLATED and INITIAL glyphs.  Text for
it must therefore be shaped -- the old approach of mapping every letter
to its isolated form produces byte sequences no real system ever wrote,
and drops every letter whose chosen form the code page lacks.

``shape_for_codec`` runs the Unicode joining algorithm (ICU
``u_shapeArabic``) and then maps each shaped glyph into the target
codec's actual repertoire with the degradation order real two-form
renderers used: a missing MEDIAL falls back to INITIAL, a missing FINAL
to ISOLATED, and a missing ligature decomposes into its parts.  On the
Arabic MS-DOS 5.0 Manager corpus this encodes 98.7% of shaped
characters, verified three ways before landing (ICU vs arabic_reshaper
867/867 identical lines; a first-principles joining-class audit; exact
round-trip of the letter sequence).

Apple's ICU build trap, learned the hard way: pass ``LETTERS_SHAPE``
(0x0008) alone for logical-order input.  Adding
``U_SHAPE_TEXT_DIRECTION_LOGICAL`` (0x0004) on this build produces the
*mirrored* forms of visual-LTR interpretation.  Never verify shaped
output by eye in a terminal -- bidi rendering reverses what you think
you see; compare codepoints.

``SHAPED_VISUAL_ENCODINGS`` lists codecs whose training text is shaped
and then stored in visual order (see bidi_order.reorder_visual): cp864
belongs to IBM's Arabic line, where interchange data was display-order
-- the reason ICU's shaper defaults to visual-LTR input.  cp1006 also
stores presentation forms but is deliberately absent until its Urdu
shaping and storage order carry evidence.
"""

from __future__ import annotations

import codecs
import ctypes
import ctypes.util
import unicodedata

#: Codecs trained on contextually shaped text stored in visual order.
SHAPED_VISUAL_ENCODINGS: frozenset[str] = frozenset({"cp864"})


def is_shaped_visual(encoding_name: str) -> bool:
    """Return whether *encoding_name* trains on shaped visual-order text.

    The one membership test for :data:`SHAPED_VISUAL_ENCODINGS`: every
    consumer (training, exclusion indexing) must resolve names the same
    way, so membership is decided under stdlib codec canonicalization here
    rather than per-caller.  An unknown codec is not a member.
    """
    try:
        canonical = codecs.lookup(encoding_name).name
    except LookupError:
        return False
    return canonical in SHAPED_VISUAL_ENCODINGS


_PRES_LO = "ﭐ"
# U+FB50..U+FEFF: the Arabic Presentation Forms A+B blocks.  The upper
# bound is written as an escape on purpose — U+FEFF is the invisible
# ZWNBSP/BOM, and a bare literal is indistinguishable from an empty string
# to every reader and to BOM-stripping tools.
_PRES_HI = "\ufeff"
_FORMS = ("ISOLATED", "FINAL", "INITIAL", "MEDIAL")
#: Two-form degradation: the byte a missing form borrows, in order.
_FALLBACK: dict[str, tuple[str, ...]] = {
    "MEDIAL": ("INITIAL", "FINAL", "ISOLATED"),
    "FINAL": ("ISOLATED", "INITIAL"),
    "INITIAL": ("ISOLATED", "FINAL"),
    "ISOLATED": ("FINAL", "INITIAL"),
}

_shape_fn = None
_repertoire_cache: dict[str, dict] = {}


def _load_icu() -> None:
    global _shape_fn  # noqa: PLW0603
    path = ctypes.util.find_library("icucore")
    if path is None:
        msg = "contextual Arabic shaping needs macOS libicucore"
        raise RuntimeError(msg)
    icu = ctypes.CDLL(path)
    fn = icu.u_shapeArabic
    fn.restype = ctypes.c_int32
    fn.argtypes = [
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.c_int32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_int),
    ]

    def shape(text: str) -> str:
        units = text.encode("utf-16-le")
        n = len(units) // 2
        src = (ctypes.c_uint16 * n).from_buffer_copy(units)
        dest = (ctypes.c_uint16 * (n * 2 + 8))()
        err = ctypes.c_int(0)
        written = fn(src, n, dest, len(dest), 0x0008, ctypes.byref(err))
        if err.value > 0:
            msg = f"u_shapeArabic error {err.value}"
            raise RuntimeError(msg)
        return b"".join(u.to_bytes(2, "little") for u in dest[:written]).decode(
            "utf-16-le"
        )

    _shape_fn = shape


def _repertoire(codec: str) -> dict:
    """Map (base, form) -> replacement string for every glyph *codec* has."""
    cached = _repertoire_cache.get(codec)
    if cached is not None:
        return cached
    by_base_form: dict[tuple[str, str], str] = {}
    for byte in range(0x80, 0x100):
        try:
            ch = bytes([byte]).decode(codec)
        except UnicodeDecodeError:
            continue
        if not (_PRES_LO <= ch <= _PRES_HI):
            continue
        name = unicodedata.name(ch, "")
        base = unicodedata.normalize("NFKC", ch)
        for form in _FORMS:
            if form in name:
                by_base_form.setdefault((base, form), ch)
                break
    _repertoire_cache[codec] = by_base_form
    return by_base_form


def shape_for_codec(text: str, codec: str) -> str:
    """Shape *text* contextually, degraded into *codec*'s repertoire.

    Characters the codec encodes directly pass through; a shaped glyph
    the codec lacks borrows the nearest form it has; anything with no
    representable form at all is dropped (measured 1.3% on real text,
    all diacritics and rare ligature contexts).
    """
    if _shape_fn is None:
        _load_icu()
    repertoire = _repertoire(codec)
    out: list[str] = []
    for ch in _shape_fn(text):
        try:
            ch.encode(codec)
            out.append(ch)
            continue
        except (UnicodeEncodeError, LookupError):
            pass
        if not (_PRES_LO <= ch <= _PRES_HI):
            continue  # unencodable non-Arabic: same drop encode_text does
        name = unicodedata.name(ch, "")
        base = unicodedata.normalize("NFKC", ch)
        form = next((f for f in _FORMS if f in name), None)
        if form is None:
            continue
        replacement = None
        for alt in _FALLBACK[form]:
            replacement = repertoire.get((base, alt))
            if replacement is not None:
                break
        if replacement is None and len(base) == 2:
            # Unligated pair (e.g. a lam-alef context the page lacks).
            parts: list[str] = []
            for sub in base:
                piece = repertoire.get((sub, "ISOLATED"))
                if piece is None:
                    parts = []
                    break
                parts.append(piece)
            if parts:
                replacement = "".join(parts)
        if replacement is not None:
            out.append(replacement)
    return "".join(out)
