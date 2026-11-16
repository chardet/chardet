"""Tests for the typographic restyling of training text."""

from __future__ import annotations

import pytest
from quotation_marks import QUOTATION_MARKS
from typography import RESTYLE_EVERY, restyle, restyle_share

from chardet.registry import REGISTRY


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        (
            "en",
            'He said "it\'s fine" - then left... \'really\' (see "notes").',
            "He said \u201cit\u2019s fine\u201d \u2013 then left\u2026 \u2018really\u2019 (see \u201cnotes\u201d).",
        ),
        ("de", 'Er sagte "das geht".', "Er sagte \u201edas geht\u201c."),
        ("fr", 'Il a dit "c\'est bon".', "Il a dit \u00abc\u2019est bon\u00bb."),
        ("sv", 'Han sa "ja".', "Han sa \u201dja\u201d."),
        ("ru", '"Da" - skazal on.', "\u00abDa\u00bb \u2013 skazal on."),
        (
            "cy",
            "Mae enw'r ferch yn f'atgoffa.",
            "Mae enw\u2019r ferch yn f\u2019atgoffa.",
        ),
    ],
)
def test_restyle_uses_the_languages_own_marks(
    language: str, text: str, expected: str
) -> None:
    assert restyle(text, language) == expected


@pytest.mark.parametrize(
    "text",
    [
        "well-known and re-use keep their hyphens",
        "four dots.... stay",
        "x = a-b",
        "no punctuation to change here",
    ],
)
def test_restyle_leaves_other_punctuation_alone(text: str) -> None:
    assert restyle(text, "en") == text


def test_restyle_ignores_a_language_without_marks() -> None:
    text = '"quoted" - it\'s...'
    assert restyle(text, "zxx") == text


def test_restyle_share_restyles_every_nth_document() -> None:
    texts = ['say "x"'] * (RESTYLE_EVERY * 2)
    restyled = restyle_share(texts, "en")
    changed = [i for i, text in enumerate(restyled) if text != texts[i]]
    assert changed == [0, RESTYLE_EVERY]
    assert len(restyled) == len(texts)


def test_every_trained_language_has_quotation_marks() -> None:
    """Only the art pseudo-language has no CLDR entry."""
    trained = {lang for info in REGISTRY.values() for lang in info.languages}
    assert trained - set(QUOTATION_MARKS) <= {"zxx"}
