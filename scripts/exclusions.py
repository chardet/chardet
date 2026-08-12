"""Build exclusion fingerprints from test data to prevent train/test overlap."""

from __future__ import annotations

import codecs
import hashlib
import re
from pathlib import Path

#: Characters a transcode is most likely to have replaced.  A test file is
#: fingerprinted from its *decoded* bytes, after the generator substituted
#: whatever its target encoding could not represent, while a corpus article
#: is fingerprinted raw.  Folding both sides removes that asymmetry — an
#: ISO-8859-14 test file holding an ASCII apostrophe still matches the
#: source article's typographic one.
_CANONICAL_FOLD = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u2026": "...",
        "\u00a0": " ",
        "\u2002": " ",
        "\u2003": " ",
        "\u2009": " ",
        "\u200a": " ",
    }
)

#: Sentence boundaries are *content*-defined, which is what makes them
#: usable here: two copies of a document yield the same units even when one
#: carries different chrome around them, so their fingerprints still line
#: up.  Fixed-offset windows cannot do this — the pair that prompted this
#: work differed by 576 characters in length, so evenly spaced windows
#: landed on different text in each copy and matched nothing.
_UNIT_SPLIT = re.compile(r"(?<=[.!?\u3002\uff01\uff1f\u061f\u06d4])\s*")

#: Shortest unit worth fingerprinting, measured in UTF-8 bytes.  Short
#: fragments are the stuff of navigation chrome and template lines, which
#: recur across unrelated documents; a long sentence recurring is evidence
#: of the same document.  Bytes rather than characters because scripts
#: differ enormously in how much they say per character: at 60 *characters*
#: every Japanese sentence fell below the bar, so CJK documents kept
#: collapsing to a single whole-document unit with no partial matching at
#: all.  A CJK character is three UTF-8 bytes, which is about the right
#: weighting against Latin text.
_MIN_UNIT = 60

#: Fraction of a candidate's units that must appear in the exclusion set
#: before it counts as the same document.  Shared site furniture (a wiki's
#: interface strings, a template paragraph) lands a unit or two; a
#: duplicate lands most of them.  Measured against the real corpus: the
#: Breton Wikipedia chrome shared by ~30 legitimate articles stays far
#: below this, while the article that genuinely duplicated a test file
#: shared 90% of its content.
_OVERLAP_FRACTION = 0.30

#: Least shared text that can count as reproducing a test file.  Without
#: it, a test file made mostly of site chrome is "fully contained" in every
#: page of that site: one 215-character Breton test file consisting of wiki
#: interface strings matched 150 legitimate articles at 100% of itself.
#: Measured against the real corpus — chrome matches contribute about 165
#: characters, while every genuine duplicate contributes 277 or more.  A
#: test file with less unique prose than this gets only the opening-hash
#: floor, which is a test-data quality problem rather than a detection one.
_MIN_MATCH_CHARS = 200

_WS_RUN = re.compile(r"\s+")


def _normalize(text: str) -> str:
    r"""Collapse whitespace and fold transcode-sensitive characters.

    Uses ``\s+`` (any whitespace run to a single space), NOT the
    ``(\s)\1+`` pattern from train.py's ``normalize_text()`` (which only
    collapses repeated identical whitespace chars). The difference is
    intentional: fingerprinting needs maximal normalization so the same
    source text produces the same fingerprint regardless of how whitespace
    was transformed during encoding/decoding round-trips.
    """
    return _WS_RUN.sub(" ", text.translate(_CANONICAL_FOLD)).strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _weight(text: str) -> int:
    """Size of *text* in UTF-8 bytes.

    Every length in this module is measured this way so that coverage
    ratios mean the same thing in every script.
    """
    return len(text.encode("utf-8"))


def content_hash(text: str) -> str:
    """Hash a document's entire normalized content.

    Used for deduplication: two articles with the same value are the same
    text, however they were whitespace-formatted or punctuated.
    """
    return _hash(_normalize(text))


def fingerprint_text(text: str) -> str:
    """Compute a SHA-256 fingerprint of a document's normalized opening.

    Retained for callers that need one value per document.  Overlap
    detection uses :func:`fingerprint_windows`, because an opening alone
    misses a duplicate whose first characters were altered in transcoding
    or came from a different crawl of the same page.
    """
    return _hash(_normalize(text)[:200])


def _content_units(normalized: str) -> list[str]:
    """Split normalized text into the units overlap is measured over.

    Sentence terminators are listed for every script the corpus covers:
    CJK and Arabic use their own, and omitting them left 11% of the test
    set (every Japanese and Chinese file) with no internal structure at
    all, so overlap could only be detected by whole-document equality.
    """
    units = [
        unit for unit in _UNIT_SPLIT.split(normalized) if _weight(unit) >= _MIN_UNIT
    ]
    return units or [normalized]


def fingerprint_windows(text: str) -> frozenset[str]:
    """Fingerprint the substantial sentences of *text*.

    Covering the whole document rather than only its opening is what makes
    a duplicate detectable no matter where it diverges: the case that
    prompted this hashed differently in its first 200 characters (a
    substituted apostrophe, then different wiki chrome) while 90% of the
    body was identical.
    """
    normalized = _normalize(text)
    if not normalized:
        return frozenset()
    return frozenset(_hash(unit) for unit in _content_units(normalized))


class ExclusionIndex:
    """Test-set content, indexed for overlap detection.

    Coverage is judged from *both* sides.  Measuring only the candidate
    article lets a long article that reproduces a whole test file escape:
    a Breton article carrying a 277-character test file verbatim scored
    19% of its own 1,430 characters and stayed in the corpus, which the
    200-character prefix rule this replaced had actually caught.  Coverage
    is also tracked per test file rather than against the union of all of
    them, so unrelated documents cannot pool their shared boilerplate into
    a false match.

    The opening fingerprints are kept as a floor: whatever else changes,
    detection is never weaker than the prefix rule it replaced.
    """

    __slots__ = ("_file_total", "_prefixes", "_unit_files", "_unit_length")

    def __init__(self) -> None:
        self._unit_files: dict[str, set[int]] = {}
        self._unit_length: dict[str, int] = {}
        self._file_total: list[int] = []
        self._prefixes: set[str] = set()

    def add(self, text: str) -> None:
        """Index one test file."""
        normalized = _normalize(text)
        if not normalized:
            return
        file_id = len(self._file_total)
        for unit in _content_units(normalized):
            digest = _hash(unit)
            self._unit_files.setdefault(digest, set()).add(file_id)
            self._unit_length[digest] = _weight(unit)
        # The whole document, not just the units long enough to index: a
        # test file whose body is short lines would otherwise be "covered"
        # in full by one shared boilerplate sentence.
        self._file_total.append(_weight(normalized))
        self._prefixes.add(_hash(normalized[:200]))

    def __bool__(self) -> bool:
        """Return whether any test content is indexed."""
        return bool(self._unit_files or self._prefixes)

    def __len__(self) -> int:
        """Return the number of distinct indexed units."""
        return len(self._unit_files)

    def digest(self) -> str:
        """Stable hash of the indexed content, for training provenance."""
        return _hash("\n".join(sorted(self._unit_files) + sorted(self._prefixes)))

    def overlaps(self, text: str) -> bool:
        """Return ``True`` when *text* substantially reproduces a test file."""
        normalized = _normalize(text)
        if not normalized:
            return False
        if _hash(normalized[:200]) in self._prefixes:
            return True

        # Distinct units only: a candidate that repeats one shared sentence
        # must not accumulate credit for it.
        matched_per_file: dict[int, int] = {}
        matched_total = 0
        for unit in set(_content_units(normalized)):
            digest = _hash(unit)
            files = self._unit_files.get(digest)
            if files is None:
                continue
            length = self._unit_length[digest]
            matched_total += length
            for file_id in files:
                matched_per_file[file_id] = matched_per_file.get(file_id, 0) + length

        if matched_total < _MIN_MATCH_CHARS:
            return False
        # The denominator is the whole document, not just the units that
        # survived the length filter, so an article of short lines plus one
        # shared sentence cannot score 100%.
        if matched_total / _weight(normalized) >= _OVERLAP_FRACTION:
            return True
        return any(
            self._file_total[file_id]
            and matched / self._file_total[file_id] >= _OVERLAP_FRACTION
            for file_id, matched in matched_per_file.items()
        )


def _get_codec(encoding_name: str) -> str | None:
    """Resolve an encoding name to a Python codec name."""
    for candidate in (
        encoding_name,
        encoding_name.replace("-", "").replace("_", "").lower(),
    ):
        try:
            codecs.lookup(candidate)
            return candidate
        except LookupError:
            continue
    return None


def build_exclusion_set(test_data_dir: Path) -> ExclusionIndex:
    """Scan test data and index the content of every test file.

    Iterates directories matching ``{encoding}-{language}`` and decodes
    each file using the encoding from the directory name.  All files are
    indexed — not just ``culturax_*`` — so any training source (web
    corpora, artpacks) is protected from test overlap.
    """
    index = ExclusionIndex()

    if not test_data_dir.is_dir():
        return index

    for encoding_dir in sorted(test_data_dir.iterdir()):
        if not encoding_dir.is_dir():
            continue

        parts = encoding_dir.name.rsplit("-", 1)
        if len(parts) != 2:
            continue

        encoding_name = parts[0]
        if encoding_name == "None":
            continue

        codec = _get_codec(encoding_name)
        if codec is None:
            continue

        for filepath in sorted(encoding_dir.iterdir()):
            if not filepath.is_file():
                continue

            try:
                raw_bytes = filepath.read_bytes()
                text = raw_bytes.decode(codec)
            except (UnicodeDecodeError, LookupError):
                continue

            if not text or len(text) < 10:
                continue

            index.add(text)

    return index


def overlaps_exclusions(text: str, exclusions: ExclusionIndex) -> bool:
    """Return ``True`` when *text* substantially reproduces a test file."""
    return exclusions.overlaps(text)


# Number of CulturaX articles downloaded by the test data generator.
# All articles at indices 0 through this value minus 1 are potential test data.
_CULTURAX_TEST_DATA_MAX_INDEX = 20


def is_excluded(
    text: str,
    exclusions: frozenset[str],
    *,
    source: str,
    stream_index: int,
) -> bool:
    """Check whether an article should be excluded from training.

    When *exclusions* is empty (``--no-skip-test-overlap``), no filtering
    is performed at all — both the index fast path and content fingerprinting
    are skipped.

    Otherwise uses two mechanisms:
    1. Index-based fast path: CulturaX articles at indices 0-19 are always
       excluded (the test data generator downloads from these indices).
    2. Content overlap: enough of the article's windows appear in the
       exclusion set to make it the same document.  This applies to all
       sources.
    """
    if not exclusions:
        return False

    # Fast path: CulturaX indices 0-19 are known test data sources
    if source == "culturax" and stream_index < _CULTURAX_TEST_DATA_MAX_INDEX:
        return True

    # Content overlap check (applies to all sources)
    return overlaps_exclusions(text, exclusions)
