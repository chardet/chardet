#!/usr/bin/env python
"""Score chardet on text its models were not trained on.

``short_input_scorecard.py`` draws on the training cache, which flatters
anything that asks what a model has seen.  This scorecard asks the same
questions of text from two public sources that are not training data:

* the Universal Declaration of Human Rights in each trained language,
  from the Unicode UDHR project, pinned to one commit;
* sentences from Tatoeba's per-language exports.

It builds six sets and reports, for each, how often the detected
encoding decodes to the right text and how often the language is right:

* ``typographic``: Tatoeba sentences whose only non-ASCII characters are
  quotation marks, dashes, and ellipses;
* ``tatoeba-short`` and ``udhr-short``: a sentence, or a few delimited
  rows of words, as in the short-input scorecard;
* ``tatoeba-paragraphs``: forty sentences joined;
* ``sparse-paragraphs``: twenty sentences joined, drawn without regard to
  their content and kept when the paragraph has one to five non-ASCII
  characters, which is what most Dutch, English, or Indonesian text
  looks like;
* ``udhr-documents``: each declaration whole.

The text is downloaded into ``data/heldout/`` (gitignored) on first use
and kept.  Tatoeba's exports change weekly, so numbers compare only
between runs over one download; use ``--json`` and ``--compare`` for
that.  It reports numbers and fails nothing.

Usage::

    uv run python scripts/heldout_scorecard.py
    uv run python scripts/heldout_scorecard.py --json before.json
    uv run python scripts/heldout_scorecard.py --compare before.json
"""

from __future__ import annotations

import argparse
import bz2
import io
import json
import random
import re
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from short_input_scorecard import build_samples

import chardet
from chardet.evaluation import is_acceptable
from chardet.registry import REGISTRY

_HELDOUT_DIR = Path(__file__).resolve().parent.parent / "data" / "heldout"
_UDHR_COMMIT = "588b3f4b2d0467aff54842a4b926551b69d5a66a"
_UDHR_URL = f"https://github.com/unicode-org/udhr/archive/{_UDHR_COMMIT}.zip"
_TATOEBA_URL = (
    "https://downloads.tatoeba.org/exports/per_language/{code}/{code}_sentences.tsv.bz2"
)
# Tatoeba names its exports by ISO 639-3 code.
_TATOEBA_CODES = {
    "ar": "ara", "be": "bel", "bg": "bul", "br": "bre", "cs": "ces",
    "cy": "cym", "da": "dan", "de": "deu", "el": "ell", "en": "eng",
    "eo": "epo", "es": "spa", "et": "est", "fa": "pes", "fi": "fin",
    "fr": "fra", "ga": "gle", "gd": "gla", "he": "heb", "hr": "hrv",
    "hu": "hun", "id": "ind", "is": "isl", "it": "ita", "ja": "jpn",
    "kk": "kaz", "ko": "kor", "lt": "lit", "lv": "lvs", "mk": "mkd",
    "ms": "zsm", "mt": "mlt", "nl": "nld", "no": "nob", "pl": "pol",
    "pt": "por", "ro": "ron", "ru": "rus", "sk": "slk", "sl": "slv",
    "sr": "srp", "sv": "swe", "tg": "tgk", "th": "tha", "tr": "tur",
    "uk": "ukr", "ur": "urd", "vi": "vie", "zh": "cmn",
}  # fmt: skip
_TYPOGRAPHIC = frozenset(
    "\u2018\u2019\u201a\u201c\u201d\u201e\u00ab\u00bb\u2039\u203a\u2013\u2014\u2026"
)
_SENTENCE_CHARS = (25, 200)
_MIN_NON_ASCII = 3
_MAX_SENTENCES = 4000
_MAX_TYPOGRAPHIC = 400
_MIN_UDHR_STAGE = 4
_MIN_DOCUMENT_NON_ASCII = 20
_PARAGRAPH_SENTENCES = 40
_SPARSE_SENTENCES = 20
_SPARSE_NON_ASCII = (1, 5)
_SEED = 434

Sample = tuple[str, str, bytes]


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "chardet-dev"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        return response.read()


def _non_ascii(text: str) -> list[str]:
    return [ch for ch in text if ord(ch) > 0x7F]


def udhr_texts(archive: bytes, languages: set[str]) -> dict[str, dict[str, str]]:
    """Return ``{language: {file stem: text}}`` from a UDHR repository zip.

    The text has one sentence per line, split after sentence punctuation,
    which is the shape the short-input sampler reads.
    """
    texts: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = {
            name.split("/", 1)[1]: name for name in bundle.namelist() if "/" in name
        }
        index = ET.fromstring(bundle.read(names["data/udhr/index.xml"]))  # noqa: S314
        for entry in index.iter("udhr"):
            language = entry.get("bcp47", "").split("-")[0]
            member = names.get(f"data/udhr/udhr_{entry.get('f')}.xml")
            stage = int(entry.get("stage", "0"))
            if language not in languages or member is None or stage < _MIN_UDHR_STAGE:
                continue
            root = ET.fromstring(bundle.read(member))  # noqa: S314
            text = " ".join(part.strip() for part in root.itertext() if part.strip())
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"(?<=[.;:!?。]) ", "\n", text)
            texts.setdefault(language, {})[str(entry.get("f"))] = text
    return texts


def tatoeba_sentences(export: bytes) -> tuple[list[str], list[str], list[str]]:
    """Split a Tatoeba export into ordinary, typographic-only, and all sentences.

    Ordinary sentences have at least three non-ASCII characters.  The
    typographic ones have non-ASCII characters, all of them quotation
    marks, dashes, or ellipses.  The third list is every sentence of a
    usable length, whatever it holds.  All three are sorted and
    deduplicated.
    """
    ordinary: set[str] = set()
    typographic: set[str] = set()
    plain: set[str] = set()
    for line in bz2.decompress(export).decode("utf-8", "replace").splitlines():
        fields = line.split("\t", 2)
        if len(fields) < 3:
            continue
        sentence = fields[2].strip()
        if not _SENTENCE_CHARS[0] <= len(sentence) <= _SENTENCE_CHARS[1]:
            continue
        plain.add(sentence)
        high = _non_ascii(sentence)
        if len(high) >= _MIN_NON_ASCII:
            ordinary.add(sentence)
        if high and all(ch in _TYPOGRAPHIC for ch in high):
            typographic.add(sentence)
    return sorted(ordinary), sorted(typographic), sorted(plain)


def fetch(root: Path, languages: set[str]) -> None:
    """Download and unpack whatever of the held-out text is missing."""
    udhr = root / "udhr"
    if not udhr.is_dir():
        print(f"downloading UDHR at {_UDHR_COMMIT[:12]}")
        for language, files in udhr_texts(_download(_UDHR_URL), languages).items():
            (udhr / language).mkdir(parents=True, exist_ok=True)
            for stem, text in files.items():
                (udhr / language / f"{stem}.txt").write_text(text, encoding="utf-8")
    for language in sorted(languages & set(_TATOEBA_CODES)):
        folders = {
            name: root / name / language for name in ("tatoeba", "typographic", "plain")
        }
        if all((folder / "sentences.txt").is_file() for folder in folders.values()):
            continue
        code = _TATOEBA_CODES[language]
        raw = root / "tatoeba-raw" / f"{code}.tsv.bz2"
        if not raw.is_file():
            print(f"downloading Tatoeba {code}")
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(_download(_TATOEBA_URL.format(code=code)))
        ordinary, typographic, plain = tatoeba_sentences(raw.read_bytes())
        for name, lines, cap in (
            ("tatoeba", ordinary, _MAX_SENTENCES),
            ("typographic", typographic, _MAX_TYPOGRAPHIC),
            ("plain", plain, _MAX_SENTENCES),
        ):
            target = folders[name] / "sentences.txt"
            if target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            rng = random.Random(f"{_SEED}/{name}/{language}")  # noqa: S311
            picked = rng.sample(lines, min(cap, len(lines)))
            target.write_text("\n".join(picked), encoding="utf-8")


def _encodable(text: str, encoding: str) -> bytes | None:
    try:
        return text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return None


def _pairs() -> list[tuple[str, str]]:
    return [
        (encoding, language)
        for encoding, info in sorted(REGISTRY.items())
        for language in info.languages
    ]


def typographic_samples(folder: Path, per_pair: int) -> list[Sample]:
    """Sentences whose only high bytes are typographic marks, per single-byte pair."""
    samples: list[Sample] = []
    for encoding, language in _pairs():
        path = folder / language / "sentences.txt"
        info = REGISTRY[encoding]
        if info.is_multibyte_cjk or encoding.startswith("utf") or not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        random.Random(f"typographic/{encoding}/{language}").shuffle(lines)  # noqa: S311
        made = 0
        for line in lines:
            data = _encodable(line, encoding)
            if data is None or data.isascii():
                continue
            samples.append(
                (f"{encoding}/{language}/typographic/{made}", encoding, data)
            )
            made += 1
            if made == per_pair:
                break
    return samples


def paragraph_samples(folder: Path, per_pair: int) -> list[Sample]:
    """Forty Tatoeba sentences joined, per encoding-language pair."""
    samples: list[Sample] = []
    for encoding, language in _pairs():
        path = folder / language / "sentences.txt"
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) < _PARAGRAPH_SENTENCES:
            continue
        rng = random.Random(f"paragraph/{encoding}/{language}")  # noqa: S311
        made = 0
        for _ in range(per_pair * 10):
            data = _encodable(
                " ".join(rng.sample(lines, _PARAGRAPH_SENTENCES)), encoding
            )
            if data is None:
                continue
            samples.append((f"{encoding}/{language}/paragraph/{made}", encoding, data))
            made += 1
            if made == per_pair:
                break
    return samples


def sparse_samples(folder: Path, per_pair: int) -> list[Sample]:
    """Twenty sentences joined, kept when only a few characters are non-ASCII."""
    low, high = _SPARSE_NON_ASCII
    samples: list[Sample] = []
    for encoding, language in _pairs():
        path = folder / language / "sentences.txt"
        info = REGISTRY[encoding]
        if info.is_multibyte_cjk or encoding.startswith("utf") or not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) < _SPARSE_SENTENCES:
            continue
        rng = random.Random(f"sparse/{encoding}/{language}")  # noqa: S311
        made = 0
        for _ in range(per_pair * 20):
            text = " ".join(rng.sample(lines, _SPARSE_SENTENCES))
            data = _encodable(text, encoding)
            if data is None or not low <= len(_non_ascii(text)) <= high:
                continue
            samples.append((f"{encoding}/{language}/sparse/{made}", encoding, data))
            made += 1
            if made == per_pair:
                break
    return samples


def document_samples(folder: Path) -> list[Sample]:
    """Each declaration whole, less the lines its encoding cannot represent."""
    samples: list[Sample] = []
    for encoding, language in _pairs():
        for path in sorted((folder / language).glob("*.txt")):
            lines = path.read_text(encoding="utf-8").splitlines()
            text = "\n".join(line for line in lines if _encodable(line, encoding))
            if len(_non_ascii(text)) >= _MIN_DOCUMENT_NON_ASCII:
                sample_id = f"{encoding}/{language}/document/{path.stem}"
                samples.append((sample_id, encoding, text.encode(encoding)))
    return samples


def build_sets(root: Path) -> dict[str, list[Sample]]:
    """Build the six held-out sets from the text under *root*."""
    return {
        "typographic": typographic_samples(root / "typographic", 15),
        "tatoeba-short": build_samples(20, _SEED, root / "tatoeba", _SENTENCE_CHARS),
        "udhr-short": build_samples(10, _SEED, root / "udhr"),
        "tatoeba-paragraphs": paragraph_samples(root / "tatoeba", 6),
        "sparse-paragraphs": sparse_samples(root / "plain", 10),
        "udhr-documents": document_samples(root / "udhr"),
    }


def score(samples: list[Sample]) -> dict[str, dict[str, object]]:
    """Run ``detect()`` on every sample and record both verdicts."""
    results: dict[str, dict[str, object]] = {}
    for sample_id, encoding, data in samples:
        result = chardet.detect(data, compat_names=False)
        results[sample_id] = {
            "expected": encoding,
            "detected": result["encoding"],
            "ok": bool(is_acceptable(data, encoding, result["encoding"])),
            "language_ok": result["language"] == sample_id.split("/")[1],
        }
    return results


def _report(name: str, results: dict[str, dict[str, object]]) -> None:
    total = len(results)
    if not total:
        print(f"{name}: no samples")
        return
    right = sum(bool(r["ok"]) for r in results.values())
    language = sum(bool(r["language_ok"]) for r in results.values())
    print(
        f"{name}: {total} samples, right text {right} ({right / total:.1%}), "
        f"right language {language} ({language / total:.1%})"
    )
    misses = Counter(
        (str(r["expected"]), str(r["detected"]))
        for r in results.values()
        if not r["ok"]
    )
    for (expected, detected), n in misses.most_common(5):
        print(f"  {n:4d}  {expected} -> {detected}")


def _compare(
    name: str,
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> None:
    shared = sorted(set(before) & set(after))
    for label, field in (("text", "ok"), ("language", "language_ok")):
        fixed = sum(not before[k][field] and bool(after[k][field]) for k in shared)
        broken = sum(bool(before[k][field]) and not after[k][field] for k in shared)
        print(f"  {name} {label}: {fixed} fixed, {broken} broken of {len(shared)}")


def main() -> None:
    """Fetch the held-out text if needed, score it, and print the scorecard."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--json", type=Path, help="write per-sample results here")
    parser.add_argument("--compare", type=Path, help="results file to compare against")
    args = parser.parse_args()
    languages = {language for _, language in _pairs()}
    fetch(_HELDOUT_DIR, languages)
    results = {
        name: score(samples) for name, samples in build_sets(_HELDOUT_DIR).items()
    }
    for name, rows in results.items():
        _report(name, rows)
    if args.json:
        args.json.write_text(json.dumps(results))
    if args.compare:
        before = json.loads(args.compare.read_text())
        for name, rows in results.items():
            _compare(name, before.get(name, {}), rows)


if __name__ == "__main__":
    main()
