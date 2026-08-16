#!/usr/bin/env python3
"""Measure what full-resolution model weights would change, before building CMD3.

The v2 model format quantizes bigram weights to 8-bit ints
(``round(count / max * 255)`` with a high-byte ``count >= 300`` rescue at
weight 1), and the rare-bigram study closed with the finding that this
flattening is what leaves the sparse-evidence xfails irreducible.  This
harness measures the ceiling directly: it rescores the whole corpus through
the real pipeline with float weights rebuilt from ``raw_bigram_counts.pkl``
on the exact shipped support set, so quantization resolution is the only
variable.  If nothing flips, no format change is warranted.

Arms:

* ``shipped``  — the stock pipeline, untouched.  The baseline.
* ``identity`` — float tables holding exactly the shipped integer values.
   Must be bit-identical to ``shipped``; validates the monkeypatch plumbing.
* ``zero``     — all-zero tables.  Must diverge from ``shipped`` on most
   non-ASCII files; proves the patch actually covers every scoring path
   (cosine similarity is scale-invariant, so a scaled probe would prove
   nothing).
* ``float``    — unrounded ``count / max * 255`` per bigram.  The ceiling.
* ``sqrt8``    — ``round(255 * sqrt(count / max))``, floored at 1: an 8-bit
   companding curve on the shipped support set.  Integer weights in the v2
   byte layout, so this arm is directly shippable via a train.py change
   alone.  sqrt lifts the low end enough to separate the rescued pairs
   without a rescue rule (count 300 -> weight 3).
* ``log8``     — ``round(255 * log1p(count) / log1p(max))``, floored at 1.
   The aggressive curve: a count-300 bigram lands near weight 99, so this
   measures what over-lifting the tail costs.

Usage::

    uv run python scripts/weight_resolution_study.py run --arm shipped
    uv run python scripts/weight_resolution_study.py run --arm float
    uv run python scripts/weight_resolution_study.py compare \
        data/weight_study/shipped.json data/weight_study/float.json

Results land in ``data/weight_study/<arm>.json`` (gitignored).
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
from array import array
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import collect_test_files, get_data_dir

import chardet
import chardet.models as m
import chardet.pipeline.confusion as conf
import chardet.pipeline.statistical as stat
from chardet.enums import EncodingEra
from chardet.evaluation import is_acceptable
from chardet.models import load_models
from chardet.registry import REGISTRY, lookup_encoding

REPO_ROOT = Path(__file__).resolve().parent.parent
PKL_PATH = REPO_ROOT / "data" / "raw_bigram_counts.pkl"
OUT_DIR = REPO_ROOT / "data" / "weight_study"
TOP_N = 8

#: The 12 currently-xfailed test ids plus the fragile-five near-tie watchlist.
WATCHLIST: tuple[str, ...] = (
    # _KNOWN_FAILURES (ALL-era mode)
    "cp437-en/culturax_00001.txt",
    "cp500-es/culturax_mC4_87070.txt",
    "cp850-en/culturax_00001.txt",
    "cp850-fi/culturax_00001.txt",
    "cp850-ms/culturax_00000.txt",
    "cp858-en/culturax_00000.txt",
    "cp858-ms/culturax_00000.txt",
    "iso-8859-15-en/culturax_00002.txt",
    # _KNOWN_ERA_FILTERED_FAILURES uniques
    "iso-8859-2-hu/torokorszag.blogspot.com.xml",
    "macroman-da/culturax_mC4_83469.txt",
    # fragile-five: green today, margins under 0.002 — watch for regressions
    "iso-8859-13-et/culturax_00000.txt",
    "iso-8859-13-et/culturax_00002.txt",
    "windows-1257-et/_enca_cp1257_et.txt",
    "kz1048-kk/useful-sentences.html",
    "ptcp154-kk/useful-sentences.html",
)


def _encoding_era(name: str | None) -> EncodingEra:
    """Mirror tests/test_accuracy.py: the era used for era-filtered detection."""
    if name is None:
        return EncodingEra.ALL
    canonical = lookup_encoding(name)
    if canonical is not None:
        return REGISTRY[canonical].era
    return EncodingEra.ALL


# ---------------------------------------------------------------------------
# Arm construction: float tables + norms + row maxima
# ---------------------------------------------------------------------------


def _check_raw_cache_matches_shipped(
    raw_counts: dict[str, dict[tuple[int, int], int]],
    shipped: dict[str, bytes],
) -> None:
    """Abort when the gitignored raw cache does not cover shipped models.bin.

    The cache carries no digest tying it to models.bin, and the float arms
    read it directly, so a cache from before a retrain would fail partly
    loudly (KeyError on new-support bigrams) and partly silently (stale
    counts poisoning arm conclusions).  Every shipped model key and every
    nonzero shipped bigram must exist in the cache before any arm scores.
    """
    stale_keys = sorted(k for k in shipped if k not in raw_counts)
    if stale_keys:
        msg = (
            f"{PKL_PATH} is stale: {len(stale_keys)} shipped model(s) missing "
            f"(e.g. {stale_keys[0]}).  Re-run scripts/train.py to rebuild the "
            f"raw cache from the current corpus before running the study."
        )
        raise SystemExit(msg)
    for key, table in shipped.items():
        counts = raw_counts[key]
        for i in range(65536):
            if table[i] and (i >> 8, i & 0xFF) not in counts:
                msg = (
                    f"{PKL_PATH} is stale: model {key} lacks a count for "
                    f"shipped bigram {(i >> 8, i & 0xFF)}.  Re-run "
                    f"scripts/train.py to rebuild the raw cache."
                )
                raise SystemExit(msg)


def _build_arm_data(
    arm: str,
) -> tuple[dict[str, array], dict[str, float], dict[str, array]]:
    """Build (tables, norms, rowmax) for a float arm from the shipped support set.

    Tables are ``array('d')`` of length 65536.  The support set (which bigrams
    are nonzero) is always exactly the shipped one, so resolution is the only
    variable between ``identity`` and ``float``.
    """
    shipped = load_models()
    if arm in ("float", "sqrt8", "log8"):
        with PKL_PATH.open("rb") as f:
            raw = pickle.load(f)  # noqa: S301
        if "counts" not in raw:
            msg = (
                f"{PKL_PATH} is the legacy flat-format raw cache; the study "
                f"needs the v2 cache with per-model counts.  Re-run "
                f"scripts/train.py to rebuild it."
            )
            raise SystemExit(msg)
        raw_counts = raw["counts"]
        _check_raw_cache_matches_shipped(raw_counts, shipped)

    tables: dict[str, array] = {}
    norms: dict[str, float] = {}
    rowmaxes: dict[str, array] = {}
    for key, table in shipped.items():
        t = array("d", [0.0]) * 65536
        if arm == "identity":
            for i in range(65536):
                if table[i]:
                    t[i] = float(table[i])
        elif arm == "float":
            counts = raw_counts[key]
            mx = max(counts.values())
            for i in range(65536):
                if table[i]:
                    t[i] = counts[(i >> 8, i & 0xFF)] / mx * 255.0
        elif arm == "sqrt8":
            counts = raw_counts[key]
            mx = max(counts.values())
            for i in range(65536):
                if table[i]:
                    c = counts[(i >> 8, i & 0xFF)]
                    t[i] = max(1.0, float(round(255.0 * math.sqrt(c / mx))))
        elif arm == "log8":
            counts = raw_counts[key]
            mx = max(counts.values())
            denom = math.log1p(mx)
            for i in range(65536):
                if table[i]:
                    c = counts[(i >> 8, i & 0xFF)]
                    t[i] = max(1.0, float(round(255.0 * math.log1p(c) / denom)))
        elif arm != "zero":
            msg = f"unknown arm {arm!r}"
            raise ValueError(msg)
        tables[key] = t
        norms[key] = math.sqrt(sum(v * v for v in t))
        rm = array("d", [0.0]) * 256
        for i in range(65536):
            v = t[i]
            row = i >> 8
            rm[row] = max(rm[row], v)
        rowmaxes[key] = rm
    return tables, norms, rowmaxes


def _apply_patch(
    tables: dict[str, array],
    norms: dict[str, float],
    rowmaxes: dict[str, array],
) -> None:
    """Reroute every model-weight consumer onto the float tables.

    Verified against the import map: ``score_with_profile`` is imported by
    value in ``statistical`` and ``confusion`` (rebound here);
    ``get_rowmax`` by value in ``statistical`` (rebound); everything else
    (``load_models``, ``get_enc_index``, ``_get_model_norms``,
    ``score_best_language``) resolves through ``chardet.models`` globals at
    call time, so patching the module and clearing caches suffices.  The
    ``zero`` arm exists to prove this list is complete.
    """
    m._load_models_data = lambda: (tables, norms)  # noqa: SLF001
    for cached in (m.get_enc_index, m._get_model_norms):  # noqa: SLF001
        if hasattr(cached, "cache_clear"):
            cached.cache_clear()

    def get_rowmax_float() -> dict[str, array]:
        return rowmaxes

    m.get_rowmax = get_rowmax_float
    stat.get_rowmax = get_rowmax_float

    def score_with_profile_float(
        profile: m.BigramProfile,
        model: array | bytes,
        model_key: str = "",
    ) -> float:
        if profile.input_norm == 0.0:
            return 0.0
        model_norm = norms.get(model_key) if model_key else None
        if model_norm is None:
            model_norm = math.sqrt(sum(v * v for v in model))
        if model_norm == 0.0:
            return 0.0
        nonzero = profile.nonzero
        values = profile.values
        dot = 0.0
        if values:
            for i in range(len(nonzero)):
                dot += model[nonzero[i]] * values[i]
        elif profile.freq:
            freq = profile.freq
            for idx in nonzero:
                dot += model[idx] * freq[idx]
        else:  # compiled-kernel install: dense freq dropped, packed kept
            idx_arr, val_arr = profile.idx_arr, profile.val_arr
            for i in range(len(idx_arr)):
                dot += model[idx_arr[i]] * val_arr[i]
        return dot / (model_norm * profile.input_norm)

    m.score_with_profile = score_with_profile_float
    stat.score_with_profile = score_with_profile_float
    conf.score_with_profile = score_with_profile_float


# ---------------------------------------------------------------------------
# Corpus run
# ---------------------------------------------------------------------------

_WORKER_ARM = "shipped"


def _worker_init(arm: str) -> None:
    global _WORKER_ARM  # noqa: PLW0603
    _WORKER_ARM = arm
    if arm != "shipped":
        _apply_patch(*_build_arm_data(arm))


def _rank_metrics(
    data: bytes,
    expected: str | None,
    era: EncodingEra,
) -> dict:
    """Detect in one mode; return verdict, ranking excerpt, and margin."""
    result = chardet.detect(data, encoding_era=era, prefer_superset=True)
    detected = result["encoding"]
    if expected is None:
        return {
            "detected": detected,
            "conf": result["confidence"],
            "ok": detected is None,
            "margin": None,
            "acc_rank": None,
            "top": [],
        }
    ok = is_acceptable(data, expected, detected)
    ranking = chardet.detect_all(
        data, ignore_threshold=True, encoding_era=era, prefer_superset=True
    )
    best_acc = None
    best_unacc = None
    acc_rank = None
    for rank, r in enumerate(ranking, start=1):
        enc = r["encoding"]
        r_ok = enc is not None and is_acceptable(data, expected, enc)
        if r_ok and best_acc is None:
            best_acc = r["confidence"]
            acc_rank = rank
        elif not r_ok and best_unacc is None:
            best_unacc = r["confidence"]
        if best_acc is not None and best_unacc is not None:
            break
    margin = None
    if best_acc is not None and best_unacc is not None:
        margin = best_acc - best_unacc
    return {
        "detected": detected,
        "conf": result["confidence"],
        "ok": ok,
        "margin": margin,
        "acc_rank": acc_rank,
        "top": [[r["encoding"], round(r["confidence"], 6)] for r in ranking[:TOP_N]],
    }


def _run_one(item: tuple[str | None, str | None, str]) -> tuple[str, dict]:
    expected, lang, path_str = item
    path = Path(path_str)
    test_id = f"{path.parent.name}/{path.name}"
    data = path.read_bytes()
    return test_id, {
        "expected": expected,
        "lang": lang,
        "all": _rank_metrics(data, expected, EncodingEra.ALL),
        "era": _rank_metrics(data, expected, _encoding_era(expected)),
    }


def cmd_run(args: argparse.Namespace) -> None:
    files = collect_test_files(get_data_dir())
    if args.limit:
        files = files[: args.limit]
    items = [(enc, lang, str(fp)) for enc, lang, fp in files]
    with ProcessPoolExecutor(
        max_workers=args.workers, initializer=_worker_init, initargs=(args.arm,)
    ) as pool:
        results: dict[str, dict] = dict(pool.map(_run_one, items, chunksize=16))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{args.arm}.json"
    with out_path.open("w") as f:
        json.dump(results, f, indent=1, sort_keys=True)

    n = len(results)
    for mode in ("all", "era"):
        ok = sum(1 for r in results.values() if r[mode]["ok"])
        print(f"{args.arm} [{mode}]: {ok}/{n} acceptable")
    print(f"wrote {out_path}")

    print("\nwatchlist:")
    for wid in WATCHLIST:
        row = results.get(wid)
        if row is None:
            print(f"  {wid}: NOT FOUND")
            continue
        cells = []
        for mode in ("all", "era"):
            r = row[mode]
            m = "None" if r["margin"] is None else f"{r['margin']:+.4f}"
            cells.append(
                f"{mode}: {'ok ' if r['ok'] else 'RED'} {r['detected']} "
                f"margin={m} rank={r['acc_rank']}"
            )
        print(f"  {wid}\n      {cells[0]}\n      {cells[1]}")


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def cmd_compare(args: argparse.Namespace) -> None:
    with Path(args.baseline).open() as f:
        base = json.load(f)
    with Path(args.candidate).open() as f:
        cand = json.load(f)
    if set(base) != set(cand):
        print(
            f"WARNING: file sets differ "
            f"(base {len(base)}, cand {len(cand)}); comparing intersection"
        )
    ids = sorted(set(base) & set(cand))
    identical_rankings = 0
    ranking_cells = 0
    for mode in ("all", "era"):
        fixed = [i for i in ids if not base[i][mode]["ok"] and cand[i][mode]["ok"]]
        broke = [i for i in ids if base[i][mode]["ok"] and not cand[i][mode]["ok"]]
        for i in ids:
            ranking_cells += 1
            if base[i][mode]["top"] == cand[i][mode]["top"]:
                identical_rankings += 1
        print(f"\n[{mode}] fixed: {len(fixed)}  broke: {len(broke)}")
        for label, group in (("FIXED", fixed), ("BROKE", broke)):
            for i in group:
                b, c = base[i][mode], cand[i][mode]
                print(
                    f"  {label} {i}: {b['detected']} -> {c['detected']} "
                    f"(margin {b['margin']} -> {c['margin']})"
                )
    print(f"\nidentical rankings: {identical_rankings}/{ranking_cells} file-mode cells")
    print("\nwatchlist margins (base -> cand):")
    for wid in WATCHLIST:
        if wid not in base or wid not in cand:
            continue
        for mode in ("all", "era"):
            b, c = base[wid][mode], cand[wid][mode]
            bm = "None" if b["margin"] is None else f"{b['margin']:+.4f}"
            cm = "None" if c["margin"] is None else f"{c['margin']:+.4f}"
            flag = ""
            if b["ok"] != c["ok"]:
                flag = "  <-- FLIP " + ("(fixed)" if c["ok"] else "(BROKE)")
            print(f"  {wid} [{mode}]: {bm} -> {cm}{flag}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run one arm over the corpus")
    p_run.add_argument(
        "--arm",
        choices=["shipped", "identity", "zero", "float", "sqrt8", "log8"],
        required=True,
    )
    p_run.add_argument("--workers", type=int, default=8)
    p_run.add_argument("--limit", type=int, default=0, help="first N files only")
    p_run.set_defaults(func=cmd_run)
    p_cmp = sub.add_parser("compare", help="diff two result JSONs")
    p_cmp.add_argument("baseline")
    p_cmp.add_argument("candidate")
    p_cmp.set_defaults(func=cmd_compare)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
