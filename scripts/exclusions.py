"""Build exclusion fingerprints from test data to prevent train/test overlap."""

from __future__ import annotations

import codecs
import hashlib
import re
from pathlib import Path


def fingerprint_text(text: str) -> str:
    r"""Compute a SHA-256 fingerprint of text after encoding-neutral normalization.

    Normalization: collapse ALL whitespace runs to a single space, strip
    leading/trailing whitespace, then truncate to the first 200 characters.
    This is encoding-neutral — no charset-specific substitutions are applied.

    Note: this uses ``\\s+`` (any whitespace to single space), NOT the
    ``(\\s)\\1+`` pattern from train.py's ``normalize_text()`` (which only
    collapses repeated identical whitespace chars). The difference is intentional:
    fingerprinting needs maximal normalization so the same source text produces
    the same fingerprint regardless of how whitespace was transformed during
    encoding/decoding round-trips.
    """
    # Collapse all whitespace runs to a single space
    normalized = re.sub(r"\s+", " ", text).strip()
    # Truncate to first 200 chars
    truncated = normalized[:200]
    return hashlib.sha256(truncated.encode("utf-8")).hexdigest()


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


def build_exclusion_set(test_data_dir: Path) -> frozenset[str]:
    """Scan test data for CulturaX files and return content fingerprints.

    Iterates directories matching ``{encoding}-{language}``, finds files
    matching ``culturax_*``, decodes them using the encoding from the
    directory name, and returns SHA-256 fingerprints of the decoded text.
    """
    fingerprints: set[str] = set()

    if not test_data_dir.is_dir():
        return frozenset()

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
            if not filepath.name.startswith("culturax_"):
                continue

            try:
                raw_bytes = filepath.read_bytes()
                text = raw_bytes.decode(codec)
            except (UnicodeDecodeError, LookupError):
                continue

            if not text or len(text) < 10:
                continue

            fingerprints.add(fingerprint_text(text))

    return frozenset(fingerprints)


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
    2. Content fingerprint: the article's fingerprint is checked against the
       exclusion set. This applies to all sources.
    """
    if not exclusions:
        return False

    # Fast path: CulturaX indices 0-19 are known test data sources
    if source == "culturax" and stream_index < _CULTURAX_TEST_DATA_MAX_INDEX:
        return True

    # Content fingerprint check (applies to all sources)
    return fingerprint_text(text) in exclusions
