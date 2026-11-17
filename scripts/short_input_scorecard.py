#!/usr/bin/env python
"""Score chardet on short inputs built from the training-side text.

The accuracy suite is mostly whole documents.  This scorecard measures
the other end: a sentence, or a few delimited rows of names and words,
in every encoding the registry lists for a language.  It reports a
number and fails nothing.

The text comes from the training cache (``data/culturax``), not from
``tests/data``, so a rule can be developed against this scorecard without
being fitted to the test suite.  The bigram models were trained on the
same text, so the absolute score flatters the statistical stage; use it
to compare two builds, not as a measure of real-world accuracy.

Usage::

    uv run python scripts/short_input_scorecard.py
    uv run python scripts/short_input_scorecard.py --json before.json
    uv run python scripts/short_input_scorecard.py --compare before.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import chardet
from chardet.evaluation import is_acceptable
from chardet.registry import REGISTRY

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "culturax"
# Sentence ends: ASCII, plus the ideographic full stop and the fullwidth
# exclamation and question marks.
_SENTENCE_SPLIT = re.compile(r"[\r\n]+|(?<=[.!?\u3002\uff01\uff1f]) ")
_WORD = re.compile(r"[^\W\d_]{3,14}")
_MIN_NON_ASCII = 3
_PROSE_CHARS = (40, 200)
_ROWS = 3
_FIELDS = 3
_FILES_PER_LANGUAGE = 60
_ATTEMPTS_PER_SAMPLE = 40


def _non_ascii(text: str) -> int:
    return sum(ord(ch) > 0x7F for ch in text)


def _load_language(
    language: str,
    rng: random.Random,
    data_dir: Path,
    prose_chars: tuple[int, int],
) -> tuple[list[str], list[str]]:
    """Return sentences and words for *language* from *data_dir*."""
    files = sorted((data_dir / language).glob("*.txt"))
    if not files:
        return [], []
    sentences: list[str] = []
    words: set[str] = set()
    for path in rng.sample(files, min(_FILES_PER_LANGUAGE, len(files))):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw in _SENTENCE_SPLIT.split(text):
            sentence = raw.strip()
            if (
                prose_chars[0] <= len(sentence) <= prose_chars[1]
                and _non_ascii(sentence) >= _MIN_NON_ASCII
            ):
                sentences.append(sentence)
        words.update(_WORD.findall(text))
    return sentences, sorted(words)


def _rows(words: list[str], rng: random.Random) -> str:
    """Build a few semicolon-delimited rows, like a spreadsheet export."""
    lines = []
    for _ in range(_ROWS):
        fields = [rng.choice(words) for _ in range(_FIELDS - 1)]
        fields.append(f"{rng.randint(1, 9999)},{rng.randint(0, 99):02d}")
        lines.append(";".join(field.capitalize() for field in fields))
    return "\r\n".join(lines) + "\r\n"


def build_samples(
    per_pair: int,
    seed: int,
    data_dir: Path = _DATA_DIR,
    prose_chars: tuple[int, int] = _PROSE_CHARS,
) -> list[tuple[str, str, bytes]]:
    """Return ``(sample id, encoding, data)`` for every encoding-language pair.

    *data_dir* holds one directory of ``.txt`` files per language; the
    default is the training cache.
    """
    samples: list[tuple[str, str, bytes]] = []
    by_language: dict[str, tuple[list[str], list[str]]] = {}
    for encoding, info in sorted(REGISTRY.items()):
        for language in info.languages:
            rng = random.Random(f"{seed}/{encoding}/{language}")  # noqa: S311
            if language not in by_language:
                by_language[language] = _load_language(
                    language,
                    random.Random(f"{seed}/{language}"),  # noqa: S311
                    data_dir,
                    prose_chars,
                )
            sentences, words = by_language[language]
            if not sentences or not words:
                continue
            for kind in ("prose", "rows"):
                made = 0
                # A language with few usable sentences would otherwise fill
                # its samples with repeats of one line.
                used: set[str] = set()
                for _ in range(per_pair * _ATTEMPTS_PER_SAMPLE):
                    if made == per_pair:
                        break
                    text = (
                        rng.choice(sentences) if kind == "prose" else _rows(words, rng)
                    )
                    if text in used or _non_ascii(text) < _MIN_NON_ASCII:
                        continue
                    try:
                        data = text.encode(encoding)
                    except (UnicodeEncodeError, LookupError):
                        continue
                    used.add(text)
                    samples.append(
                        (f"{encoding}/{language}/{kind}/{made}", encoding, data)
                    )
                    made += 1
    return samples


def score(samples: list[tuple[str, str, bytes]]) -> dict[str, dict[str, object]]:
    """Run ``detect()`` on every sample and record the verdict."""
    results: dict[str, dict[str, object]] = {}
    for sample_id, encoding, data in samples:
        detected = chardet.detect(data, compat_names=False)["encoding"]
        results[sample_id] = {
            "expected": encoding,
            "detected": detected,
            "ok": is_acceptable(data, encoding, detected),
        }
    return results


def _report(results: dict[str, dict[str, object]]) -> None:
    total = len(results)
    right = sum(bool(r["ok"]) for r in results.values())
    print(f"right text: {right} of {total} ({right / total:.1%})")
    for kind in ("prose", "rows"):
        rows = [r for k, r in results.items() if k.split("/")[2] == kind]
        ok = sum(bool(r["ok"]) for r in rows)
        print(f"  {kind}: {ok} of {len(rows)} ({ok / len(rows):.1%})")
    by_era: Counter[str] = Counter()
    ok_by_era: Counter[str] = Counter()
    for r in results.values():
        era = REGISTRY[str(r["expected"])].era.name or "?"
        by_era[era] += 1
        ok_by_era[era] += bool(r["ok"])
    for era, n in sorted(by_era.items()):
        print(f"  era {era}: {ok_by_era[era]} of {n} ({ok_by_era[era] / n:.1%})")
    misses = Counter(
        (str(r["expected"]), str(r["detected"]))
        for r in results.values()
        if not r["ok"]
    )
    print("most common misses (expected -> detected):")
    for (expected, detected), n in misses.most_common(15):
        print(f"  {n:4d}  {expected} -> {detected}")


def _compare(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]
) -> None:
    shared = sorted(set(before) & set(after))
    fixed = [k for k in shared if not before[k]["ok"] and after[k]["ok"]]
    broken = [k for k in shared if before[k]["ok"] and not after[k]["ok"]]
    changed = [k for k in shared if before[k]["detected"] != after[k]["detected"]]
    print(
        f"compared {len(shared)} samples: {len(changed)} answers changed, "
        f"{len(fixed)} fixed, {len(broken)} broken"
    )
    for label, keys in (("fixed", fixed), ("broken", broken)):
        moves = Counter(
            (
                str(before[k]["expected"]),
                str(before[k]["detected"]),
                str(after[k]["detected"]),
            )
            for k in keys
        )
        for (expected, was, now), n in moves.most_common(12):
            print(f"  {label} {n:4d}  {expected}: {was} -> {now}")


def main() -> None:
    """Build the samples, score them, and print the scorecard."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--per-pair", type=int, default=10)
    parser.add_argument("--seed", type=int, default=434)
    parser.add_argument("--json", type=Path, help="write per-sample results here")
    parser.add_argument("--compare", type=Path, help="results file to compare against")
    args = parser.parse_args()
    if not _DATA_DIR.is_dir():
        sys.exit(f"no training cache at {_DATA_DIR}; run scripts/train.py first")
    samples = build_samples(args.per_pair, args.seed)
    results = score(samples)
    _report(results)
    if args.json:
        args.json.write_text(json.dumps(results))
    if args.compare:
        _compare(json.loads(args.compare.read_text()), results)


if __name__ == "__main__":
    main()
