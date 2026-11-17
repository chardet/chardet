"""Typographic restyling of training text.

Web corpora are mostly typed with straight quotes, hyphens, and three
dots, while word-processed text in a legacy code page carries the
typographic forms.  A model trained on the corpus as found has never
seen a curly apostrophe beside its own letters.  Restyling a share of
each language's documents gives every model the forms its encoding can
represent.

The quotation marks are each language's own, from CLDR (see
``quotation_marks.py``), so the restyled share reinforces a language's
convention instead of teaching every model every style.  The rest of
the corpus is left as found, which keeps its native punctuation the
dominant signal.  Forms a target encoding cannot represent fold back to
ASCII in ``substitutions.get_substitutions``.
"""

from __future__ import annotations

import re

from quotation_marks import QUOTATION_MARKS

#: Every Nth document of a language is restyled.  A quarter was picked on
#: held-out text: half gained little more and cost accuracy on longer
#: inputs, an eighth gave up part of the gain.
RESTYLE_EVERY = 4

_APOSTROPHE = "\u2019"
_EN_DASH = "\u2013"
_ELLIPSIS = "\u2026"

# A straight quote between two letters is an apostrophe.
_LETTER_APOSTROPHE = re.compile(r"(?<=[^\W\d_])'(?=[^\W\d_])")
# A straight quote opens when it starts a line or follows whitespace, an
# opening bracket, or a dash, and something other than whitespace follows.
_OPENS = r"(?:^|(?<=[\s(\[{\u2013\u2014-]))"
_OPEN_DOUBLE = re.compile(_OPENS + r'"(?=\S)', re.MULTILINE)
_OPEN_SINGLE = re.compile(_OPENS + r"'(?=\S)", re.MULTILINE)
_SPACED_HYPHEN = re.compile(r"(?<=\S) - (?=\S)")
_THREE_DOTS = re.compile(r"(?<!\.)\.\.\.(?!\.)")


def restyle(text: str, language: str) -> str:
    """Return *text* with its typewriter punctuation set typographically.

    Straight double and single quotes become *language*'s quotation
    marks, an apostrophe between letters becomes the curly one, a spaced
    hyphen becomes an en dash, and three dots become an ellipsis.  Text
    in a language CLDR has no marks for is returned unchanged.
    """
    marks = QUOTATION_MARKS.get(language)
    if marks is None:
        return text
    start, end, alternate_start, alternate_end = marks
    text = _LETTER_APOSTROPHE.sub(_APOSTROPHE, text)
    text = _OPEN_DOUBLE.sub(start, text).replace('"', end)
    text = _OPEN_SINGLE.sub(alternate_start, text).replace("'", alternate_end)
    text = _SPACED_HYPHEN.sub(f" {_EN_DASH} ", text)
    return _THREE_DOTS.sub(_ELLIPSIS, text)


def restyle_share(texts: list[str], language: str) -> list[str]:
    """Restyle every ``RESTYLE_EVERY``-th document and leave the rest as found."""
    return [
        restyle(text, language) if i % RESTYLE_EVERY == 0 else text
        for i, text in enumerate(texts)
    ]
