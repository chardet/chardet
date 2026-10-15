# tests/test_language.py
from __future__ import annotations

import pytest

import chardet
from chardet.models import RARE_LANGUAGES, score_best_language
from chardet.pipeline import DetectionResult, language
from chardet.pipeline.language import _to_utf8, fill_languages

#: See the note in tests/test_confusion.py: mypyc resolves a compiled
#: module's calls to functions imported into it at compile time, so patching
#: those names only takes effect on interpreted builds.
_needs_interpreted_build = pytest.mark.skipif(
    language.__file__.endswith((".so", ".pyd")),
    reason="patches a function the compiled module calls natively",
)

#: Plain French, ASCII-safe apart from the accents cp1252 carries.  Long
#: enough to score decisively, so the tier tests below turn on which tier
#: ran, not on how close the models came.
_FRENCH = (
    "Le chat noir de mon voisin traverse la cour chaque matin pour aller "
    "chercher un peu de lait chez la boulangère du village."
).encode("cp1252")


@_needs_interpreted_build
def test_fill_languages_tier1_fills_without_the_scored_tiers(
    monkeypatch: pytest.MonkeyPatch,
):
    """Tier 1 fills a single-language encoding on its own.

    Asserted with model scoring switched off, so only the hardcoded map can
    supply the answer.  A bare ``language is not None`` would pass here on
    the Tier-3 fallback alone and pin nothing.
    """
    monkeypatch.setattr(language, "has_model_variants", lambda _enc: False)
    filled = fill_languages(b"test data", [DetectionResult("koi8-r", 0.90, None)])
    assert filled[0].language == "ru"


@_needs_interpreted_build
def test_fill_languages_tier2_scores_the_encodings_own_variants(
    monkeypatch: pytest.MonkeyPatch,
):
    """Tier 2 labels a multi-language encoding without the utf-8 fallback."""
    monkeypatch.setattr(language, "has_model_variants", lambda enc: enc != "utf-8")
    filled = fill_languages(_FRENCH, [DetectionResult("cp1252", 0.90, None)])
    assert filled[0].language == "fr"


@_needs_interpreted_build
def test_fill_languages_tier3_falls_back_to_the_utf8_models(
    monkeypatch: pytest.MonkeyPatch,
):
    """Tier 3 labels a candidate whose own variants cannot be scored."""
    monkeypatch.setattr(language, "has_model_variants", lambda enc: enc == "utf-8")
    filled = fill_languages(_FRENCH, [DetectionResult("cp1252", 0.90, None)])
    assert filled[0].language == "fr"


@_needs_interpreted_build
def test_fill_languages_leaves_language_unset_when_no_tier_applies(
    monkeypatch: pytest.MonkeyPatch,
):
    """With every tier closed the field stays None rather than guessing."""
    monkeypatch.setattr(language, "has_model_variants", lambda _enc: False)
    filled = fill_languages(_FRENCH, [DetectionResult("cp1252", 0.90, None)])
    assert filled[0].language is None


def test_fill_languages_passes_through_existing_language():
    """fill_languages should not overwrite a language that's already set."""
    results = [DetectionResult("utf-8", 0.95, "fr")]
    filled = fill_languages(b"bonjour", results)
    assert filled[0].language == "fr"
    assert filled[0] is results[0]  # passthrough preserves identity


def test_fill_languages_passes_through_binary_results():
    """fill_languages should leave binary results (encoding=None) untouched."""
    results = [DetectionResult(None, 0.95, None)]
    filled = fill_languages(b"\x00\x01\x02", results)
    assert filled[0].language is None
    assert filled[0] is results[0]


def test_to_utf8_unknown_encoding():
    """_to_utf8 with an unknown encoding should return None."""
    assert _to_utf8(b"Hello world", "not-a-real-encoding") is None


def test_to_utf8_passthrough():
    """_to_utf8 with utf-8 encoding should return data unchanged."""
    data = b"Hello \xc3\xa9"
    assert _to_utf8(data, "utf-8") is data


#: The calibrated mislabel snippet: plain argmax fills it as Scottish
#: Gaelic (measured margin 0.039 over English in the language tiers'
#: weighted cosine).  Shared by every band test so they all certify the
#: same input.
_MISLABEL_SNIPPET = "It’s a lovely day, so let’s grab coffee and chat."


def test_thin_rare_band_demotes_short_english_snippet():
    """Apostrophe-rich English snippets must not fill as Scottish Gaelic.

    Curly apostrophes score well in the Celtic models, and on inputs this
    short the bigram cosine stops discriminating: this snippet wins as
    Gaelic by 0.039, inside the thin-rare band.
    """
    result = chardet.detect(_MISLABEL_SNIPPET.encode("utf-8"))
    assert result["language"] == "en"


def test_thin_rare_band_rechecks_statistically_attached_labels():
    """The band also covers labels the statistical stage attached.

    In a single-byte encoding the snippet's language arrives on the result
    already set (by ``pipeline.statistical``, with the band off by design),
    so ``fill_languages`` must re-derive thin rare labels rather than pass
    them through -- otherwise every ``detect_all`` tail result keeps the
    mislabel the changelog declares fixed.
    """
    for result in chardet.detect_all(_MISLABEL_SNIPPET.encode("cp1252")):
        assert result["language"] not in RARE_LANGUAGES, result


def test_thin_rare_band_keeps_genuine_celtic_snippets():
    """Genuine short Celtic text keeps its language: its margins are wide.

    Measured Scottish Gaelic and Welsh snippets win by 0.2+ at 60
    characters and Irish by 0.14, and this Breton snippet by 0.2 at 100,
    so the demotion must not fire on them.
    """
    gaelic = "Tha mi a’ dol dhan bhùth an-diugh còmhla ri mo charaid."
    welsh = "Mae’r tywydd yn braf heddiw ac rydw i’n mynd i’r traeth."
    breton = (
        "Deuet eo an amzer vrav ha me a ya da bourmen war an aod gant ma "
        "mignoned. Brav e vo an deiz, emezañ."
    )
    irish = "Is maith liom an aimsir bhreá agus téim ag siúl cois farraige."
    assert chardet.detect(gaelic.encode("utf-8"))["language"] == "gd"
    assert chardet.detect(welsh.encode("utf-8"))["language"] == "cy"
    assert chardet.detect(breton.encode("utf-8"))["language"] == "br"
    assert chardet.detect(irish.encode("utf-8"))["language"] == "ga"


def test_thin_rare_band_casualty_class_is_pinned():
    """The band's accepted casualty: thin-margin Irish at snippet length.

    This snippet is genuine Irish that the plain argmax labels ``ga`` by a
    margin of 0.053, under the 0.06 band, so the band demotes it -- the
    trade ADR-0005's addendum accepts on prevalence grounds.  Pinned so any
    widening of the band's margin or length bounds surfaces here as a
    deliberate decision instead of a silent shift in who gets demoted.
    """
    irish = "Beidh mé ar ais amárach agus tabharfaidh mé an leabhar duit ansin."
    data = irish.encode("utf-8")
    _, plain = score_best_language(data, "utf-8", language_weighting=True)
    assert plain == "ga"  # the models do recognize it ...
    assert chardet.detect(data)["language"] not in RARE_LANGUAGES  # ... band demotes


def test_thin_ascii_breton_snippet_is_a_known_casualty():
    """A 73-character Breton snippet with no accented letter reads as Indonesian.

    The weighted cosine charges each model for its rare bigrams, which on
    an all-ASCII input counts against an accent-bearing language for mass
    the snippet never shows.  The plain cosine gave this one to Breton by
    0.065; the weighted one gives it to Indonesian outright, not through
    the band.  Pinned per ADR-0005's addendum: the corpus's rare-language
    files are labeled better at every length under the weighted cosine, so
    the loss is accepted, and a fix that recovers it should show up here.
    """
    breton = "Deuet eo an amzer vrav ha me a ya da bourmen war an aod gant ma mignoned."
    data = breton.encode("utf-8")
    _, plain = score_best_language(data, "utf-8")
    assert plain == "br"  # the plain cosine still recognizes it ...
    assert chardet.detect(data)["language"] == "id"  # ... the weighted one does not


def test_thin_rare_band_is_opt_in_and_score_preserving():
    """Without the flag the rare label survives; with it only the label moves.

    The encoding-ranking caller (``pipeline.statistical``) relies on the
    default being a plain argmax, and on the returned score being the true
    best either way -- candidate ordering must stay byte-identical.
    """
    data = _MISLABEL_SNIPPET.encode("utf-8")
    plain_score, plain_lang = score_best_language(data, "utf-8")
    banded_score, banded_lang = score_best_language(
        data, "utf-8", demote_thin_rare=True
    )
    assert plain_lang in RARE_LANGUAGES
    assert banded_lang not in RARE_LANGUAGES
    assert banded_score == plain_score


def test_thin_rare_recheck_keeps_label_when_no_tier_can_score():
    """A rare label on thin input survives when the scored tiers yield nothing.

    The re-check's only authority is a demotion to a prevalent language;
    when neither Tier 2 nor Tier 3 produces a verdict (here: an encoding
    with no model variants that Tier 3 cannot transcode either), the
    original result must pass through unchanged rather than losing its
    label.
    """
    rare = min(RARE_LANGUAGES)
    result = DetectionResult("not-a-codec", 0.5, rare, "text/plain")
    filled = fill_languages(b"ab", [result])
    assert filled == [result]


# ---------------------------------------------------------------------------
# Language scoring in the IDF-weighted space
# ---------------------------------------------------------------------------

#: A French paragraph the plain cosine labels Hungarian.  The UTF-8 pair for
#: ``é`` carries about a hundred times the IDF weight of any common ASCII
#: bigram and sits near Hungarian's maximum weight, so it outvoted ``de``,
#: ``le`` and ``qu``.
_FRENCH_WITH_ACCENTS = (
    "Nous avons trouvé plusieurs vétérinaires près de la gare. Le plus "
    "proche est situé rue de la République, à côté de la pharmacie."
)


def test_french_paragraph_is_not_hungarian():
    """The language tiers score French as French under every Unicode encoding."""
    data = _FRENCH_WITH_ACCENTS.encode("utf-8")
    _, plain = score_best_language(data, "utf-8")
    assert plain == "hu"  # the plain cosine's verdict, kept for the record
    _, weighted = score_best_language(data, "utf-8", language_weighting=True)
    assert weighted == "fr"
    for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-32", "utf-7"):
        result = chardet.detect(_FRENCH_WITH_ACCENTS.encode(encoding))
        assert result["language"] == "fr", (encoding, result)


def test_language_weighting_leaves_the_encoding_ranking_alone():
    """Only the label moves: encoding and confidence are byte-identical.

    The encoding ranking scores in the plain cosine; the weighted space is
    the language tiers' alone.
    """
    data = _FRENCH_WITH_ACCENTS.encode("utf-8")
    result = chardet.detect(data)
    assert result["encoding"] == "utf-8"
    plain_score, _ = score_best_language(data, "utf-8")
    weighted_score, _ = score_best_language(data, "utf-8", language_weighting=True)
    assert plain_score != weighted_score
    # fill_languages derives the label; the statistical stage never sees the
    # weighted score, so the confidence is the one the plain ranking produced.
    ranked = chardet.detect_all(data)
    assert ranked[0]["confidence"] == result["confidence"]
