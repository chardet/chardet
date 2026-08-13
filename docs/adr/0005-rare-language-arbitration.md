# Rare-language arbitration

A Croatian `.po` file detected as Scottish Gaelic in iso-8859-14. Not because of bad data — an audit showed the gd model is clean and language-faithful — but because the models were being honest about the wrong question: Gaelic orthography (`th`, `ch`, `an`, `ai`) legitimately scores English-dominant text well, iso-8859-14's high bytes happen to read Croatian `š/ž/đ` as plausible Gaelic vowels, and the ranking treats a Scottish Gaelic web page as exactly as likely as a Croatian one. For a thin-margin, low-confidence win, that flat prior is wrong: the world produced vastly more Croatian bytes than Gaelic ones in legacy encodings.

The decision: **banded arbitration**, never an always-on prior. A new postprocess rank correction demotes a rare-language winner only when both gates open — its lead over the best prevalent-language candidate is under 0.02 *and* its absolute confidence is under 0.15. Language commonness is admissible exactly where the byte evidence has failed to discriminate. An always-on prior (prevalence weighting every score) was rejected: it changes confidence semantics and makes rare languages start behind everywhere, including on their own genuine files. Doing nothing was rejected because the measured equity cost of arbitration is nil — genuine Celtic files win by landslides (no prevalent rival in their top 8, or +0.28 margins) while the failure case sat at 0.007 — and the benefit accrues to the vastly more common real-world case.

The rare set is a **hand-audited frozenset** (`gd`, `cy`, `ga`, `br`), not a corpus-derived tier. Upstream corpus sizes measure 2020s crawl volume, which is the wrong quantity (Welsh has a healthy modern web and had ~zero Latin-8-era text; Tajik is the reverse), they shift silently across retrains, and they cannot encode the judgment that actually matters: *deployment*, not standardization. The deployment evidence for iso-8859-14, graded from strongest to weakest:

- A charset census over a Common Crawl index slice (test-data's `mine_common_crawl.py stats`) counted 72,305 pages declaring windows-1252, 1,245 declaring iso-8859-2, single digits for iso-8859-3/-4/-8, and exactly one page each for several DOS codepages — and **zero** declaring iso-8859-14. The census's sensitivity floor is a single page.
- The test-data mining program *targets* iso-8859-14 (it is in `mine_common_crawl.py`'s default charset list) and has produced zero wild specimens; the catalog's wild count for the encoding is 0.
- A period primary source explains *why* deployment never happened: Dyke, "Issues in Creating HTML Pages with Welsh or bilingual Content" (Open University Technical Report 2003/16). His browser matrix shows every Internet Explorer version 3–6 rendering Latin-8 as Latin-1 (``Ŵ`` displayed as ``Ð``); with IE above 92% of March-2003 browser share, Celtic-capable browsers totalled 2.52%. His conclusion: "Celtic encoding is not suitable for general use... might be an option on an Intranet site." Serving Latin-8 meant mojibake for ~97% of visitors, so the era's Welsh-language guidance was Latin-1 plus entities, or UTF-8.
- A targeted Wayback Machine hunt for this ADR fetched 123 raw (``id_``) snapshots from 17 Celtic-language domains of 1998–2010 — including evertype.com and egt.ie, the sites of the standard's own author — and found zero pages declaring the charset and zero using Latin-8-distinctive bytes as Celtic letters.
- The encoding was IANA-registered in 1999 and browsers implement it today (WHATWG), but its Wikipedia article carries no usage data at all — where sibling encodings' articles cite measurable percentages.
- The one genuine deployed niche found: Irish gettext catalogues natively declaring ISO-8859-14 (Scannell's vim/gettext translations, in the test suite, measured safely outside the arbitration gate).

Caveat honestly held: 123 sampled pages is a search, not a proof, and the early web is only reachable through the Wayback Machine's coverage. Hence the claim stays graded, and the **revision protocol**: any new genuine specimen goes into test-data and forces a re-audit of the set. cp861 and iso-8859-3 were genuinely deployed for Icelandic and Maltese, which is why `is` and `mt` are excluded from the set. Training warns when a model exists for a language the arbitration review hasn't classified.

The boundary is guarded by **sentinels, not memory**: eight short genuine Celtic files in test-data whose margins sit near the gate (the closest at margin 0.05, confidence 0.11). Widening the gate or drifting the models turns them red instead of quietly demoting real files.

Resist generalizing the rare set casually — every addition demotes a language's coin-flip wins, and the set's legitimacy rests on the deployment evidence being written down and revisable. If a pairing is merely *uncommon*, leave it alone; the gate exists for pairings with no documented population at all.

## Addendum (2026-08): re-measured after the dedup retrain; a fill-side band

The original thresholds were tuned on models trained with duplicated br/gd
corpora. Re-measured on the deduplicated models against the 3,121-file suite:
the gate fires exactly once, on the motivating Croatian `.po` (demoted
correctly, gd/iso8859-14 to hr/ISO-8859-2), with zero harmful firings. The
nearest genuine sentinel sits at margin 0.049, confidence 0.104, which is
2.5x outside the 0.02 margin bound. The 0.02/0.15 thresholds stand unchanged.

The same audit found that the language *fill* (`fill_languages`) had no
arbitration at all: `score_best_language` was a plain argmax, and on short
apostrophe-rich English input the gd/br UTF-8 models win by hair margins.
Measured mislabels ("It's a lovely day, so let's grab coffee and chat." with
curly apostrophes fills as gd) win by +0.002 to +0.021. No margin/score band
separates those from the genuine Irish gettext catalogues, which sit at
+0.007 to +0.023 when scored over their 2 KB window. Length does separate
them: the smallest genuine rare-language files in the corpus are 253 bytes
(a Breton file on the legacy path) and 560 bytes (Breton, on the fill path
the band governs), while the mislabels are snippet-length, and genuine
gd/cy snippets keep margins of 0.07+ even at 40 characters. The headroom
over the 128-byte gate is therefore 2x at its thinnest, not the comfortable
multiple a larger floor would suggest; raising the length bound needs those
two files re-measured first.

The fill therefore demotes a rare winner only when the *original* input is
under 128 bytes *and* its lead over the best prevalent-language variant is
under 0.03 (`demote_thin_rare` in `models.score_best_language`; the caller
judges length, because tier 3 transcodes to UTF-8 and curly punctuation
inflates 3x on the way). The flag is opt-in and the returned score is
unchanged, so the encoding-ranking caller in `pipeline.statistical` stays
byte-identical. Labels that stage already attached are not exempt:
`fill_languages` re-derives a rare label on a thin input through the same
banded scoring, and accepts the result only as a demotion, never as a swap
of one rare label for another. An encoding whose variant set is all-Celtic
(iso8859-14) can never offer the band a prevalent rival, so a thin rare
label there escalates to the UTF-8 models for the deciding vote. "zxx" is
excluded as a demotion target: the band must not convert a rare label into
"no linguistic content".

The measured casualty class is a sub-50-character Breton or Irish snippet
with a thin margin, accepted on the same prevalence grounds as the encoding
gate; Irish at that length was near coin-flip already. Corpus effect: zero
changed outcomes on the test suite, verified by an A/B recount. The audited
rare set now lives in `chardet.models.RARE_LANGUAGES`, imported by both
gates, so it cannot drift into two sets; `scripts/train.py` points its
review warning at that name.
