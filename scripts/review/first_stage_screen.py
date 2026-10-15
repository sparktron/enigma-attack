#!/usr/bin/env python3
"""Screen first-stage climb variants on low-IC plaintexts (true-setting climbs).

Exploratory, not preregistered; writes no artifact under ``artifacts/``.  It asks, for
the climb unit v4 and v6 actually run (the 117-letter head window of a 167-letter
message, ten plugs), which way of choosing the climb's start plugboards recovers a
planted plugboard most often per unit of work, on plaintexts of low index of
coincidence, where E-Stecker (docs/code-review-2026-10-11.md,
docs/phase1-experiment-history.md) is weakest.

For each draw (a random wheel order, rings, start and plugboard under one plaintext)
every method climbs the true setting once and six random wrong settings of the same
ciphertext.  A method is calibrated against its own nulls (pooled over the set) and
detects a draw when it recovers the planted plugboard exactly and its score is at
least the null mean plus ``--z`` null standard deviations, the power harness's rule.
Cost is the mean number of plugboard evaluations on the null climbs (a sweep is nearly
all wrong settings), relative to the empty-board baseline.

Methods
    base          the repository's climb from the empty plugboard
    E, R, I       partial exhaustion of the first plug (26, 73, 136 starts)
    solo          every one of the 325 single-plug boards, plus the empty one
    screen-ic-kK  score the 325 single-plug boards once by index of coincidence, climb
                  the empty board and the K best
    screen-ng-kK  the same, screened by the n-gram score
    kick-K        climb the empty board, then K times remove three plugs of the
                  converged board at random and re-climb by n-gram, keeping the best

    python3 scripts/review/first_stage_screen.py --set low --draws-per-text 30
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import pathlib
import random
import statistics
import sys
import time
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "review"))

import enigma_fast  # noqa: E402
import plaintext_power  # noqa: E402
import stecker_batch  # noqa: E402
from enigma import EnigmaI  # noqa: E402
from stecker_climb import start_boards  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_traffic import random_plugboard  # noqa: E402

CONFIG = json.loads((ROOT / "experiments/phase1-estecker-joint-power-v1/config.json").read_text(encoding="utf-8"))
WINDOW = 117
NULLS = 6
TEXT_SEED = 20261120
KEY_SEED = "20261121"
_S: dict = {}
ACC = {"ic": 0, "ng": 0}


def climb(bc, kind, table, board):
    """One climb phase (``kind`` 'ic' or 'ng') with its evaluations booked by phase."""
    objective = bc._coincidence if kind == "ic" else bc._ngram
    out, n = bc._climb(objective, table, board)
    ACC[kind] += n
    return out, n


def init() -> None:
    _S["scorer"] = FastNgramScorer(CONFIG["scorer"])
    _S["reflector"] = enigma_fast.reflector_table("B")
    _S["settings"] = {k: CONFIG["climb"][k] for k in ("phases", "max_pairs", "max_passes", "minimum_gain")}


def solo_boards() -> list[list[int]]:
    boards = []
    for a in range(25):
        for b in range(a + 1, 26):
            board = list(range(26))
            board[a], board[b] = b, a
            boards.append(board)
    return boards


def two_phase(bc, table, board):
    """IC climb then n-gram climb from ``board``; returns (board, evaluations)."""
    used = 0
    for kind in ("ic", "ng"):
        board, n = climb(bc, kind, table, board)
        used += n
    return board, used


def best_of(bc, table, boards, extra=0):
    best, used = None, extra
    for board in boards:
        out, n = two_phase(bc, table, list(board))
        used += n
        score = bc._final_score(out, table)
        if best is None or score > best[0]:
            best = (score, out)
    return best[1], used


def capped_best_of(bc, table, boards, cap):
    """Each start: the IC phase limited to ``cap`` passes, then the full n-gram phase."""

    full = bc.settings
    best, used = None, 0
    for board in boards:
        bc.settings = {**full, "max_passes": cap}
        try:
            out, n = climb(bc, "ic", table, list(board))
        finally:
            bc.settings = full
        used += n
        out, n = climb(bc, "ng", table, out)
        used += n
        score = bc._final_score(out, table)
        if best is None or score > best[0]:
            best = (score, out)
    return best[1], used


def ng_only_extra(bc, table, boards):
    """The empty board two-phase as usual; every other start by n-gram climbing alone."""

    best, used = None, 0
    for index, board in enumerate(boards):
        if index == 0:
            out, n = two_phase(bc, table, list(board))
        else:
            out, n = climb(bc, "ng", table, list(board))
        used += n
        score = bc._final_score(out, table)
        if best is None or score > best[0]:
            best = (score, out)
    return best[1], used


def screened(bc, table, objective, k):
    import numpy as np

    trials = bc._candidates(np.arange(26), int(_S["settings"]["max_pairs"]))
    scores = objective(trials, table)
    ACC["ic" if objective == bc._coincidence else "ng"] += len(scores)
    order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), i))[:k]
    boards = [list(range(26))] + [trials[i].tolist() for i in order]
    return best_of(bc, table, boards, extra=len(scores))


def ic_all(bc, table, rank, k):
    """IC phase from every start (the empty board and all 325 single plugs); n-gram phase on the best k.

    ``rank`` is 'ic' (the converged index of coincidence) or 'ng' (the n-gram score of the
    IC-converged board).  The empty board's result is always kept, so the method is never
    worse than the baseline.
    """

    starts = [list(range(26))] + solo_boards()
    converged, used = [], 0
    for board in starts:
        out, n = climb(bc, "ic", table, board)
        used += n
        key = float(bc._coincidence(__import__("numpy").asarray(out)[None, :], table)[0]) if rank == "ic" \
            else float(bc._ngram(__import__("numpy").asarray(out)[None, :], table)[0])
        converged.append((key, out))
    order = sorted(range(1, len(converged)), key=lambda i: (-converged[i][0], i))[:k]
    best, best_score = None, None
    for i in [0] + order:
        out, n = climb(bc, "ng", table, list(converged[i][1]))
        used += n
        score = bc._final_score(out, table)
        if best is None or score > best_score:
            best, best_score = out, score
    return best, used


def kicked(bc, table, kicks, seed):
    generator = random.Random(seed)
    board, used = two_phase(bc, table, list(range(26)))
    best, best_score = board, bc._final_score(board, table)
    for _ in range(kicks):
        trial = list(best)
        plugged = [x for x in range(26) if trial[x] > x]
        for x in generator.sample(plugged, min(3, len(plugged))):
            partner = trial[x]
            trial[x], trial[partner] = x, partner
        out, n = climb(bc, "ng", table, trial)
        used += n
        score = bc._final_score(out, table)
        if score > best_score:
            best, best_score = out, score
    return best, used


def methods():
    ms = {
        "base": lambda bc, t, s: two_phase(bc, t, list(range(26))),
        "E": lambda bc, t, s: best_of(bc, t, start_boards({"first_plug": {"letters": "E"}})),
        "R": lambda bc, t, s: best_of(bc, t, start_boards({"first_plug": {"letters": "ENR"}})),
        "I": lambda bc, t, s: best_of(bc, t, start_boards({"first_plug": {"letters": "ENRXSI"}})),
        "solo": lambda bc, t, s: best_of(bc, t, [list(range(26))] + solo_boards()),
    }
    for k in (8, 26):
        ms[f"screen-ic-k{k}"] = (lambda k: lambda bc, t, s: screened(bc, t, bc._coincidence, k))(k)
        ms[f"screen-ng-k{k}"] = (lambda k: lambda bc, t, s: screened(bc, t, bc._ngram, k))(k)
    ms["kick-26"] = lambda bc, t, s: kicked(bc, t, 26, s)
    sets = {"E": lambda: start_boards({"first_plug": {"letters": "E"}}),
            "R": lambda: start_boards({"first_plug": {"letters": "ENR"}}),
            "I": lambda: start_boards({"first_plug": {"letters": "ENRXSI"}}),
            "solo": lambda: [list(range(26))] + solo_boards()}
    for tag, make in sets.items():
        ms[f"{tag}-ic4"] = (lambda make: lambda bc, t, s: capped_best_of(bc, t, make(), 4))(make)
        ms[f"{tag}-ngonly"] = (lambda make: lambda bc, t, s: ng_only_extra(bc, t, make()))(make)
    for rank in ("ic", "ng"):
        for k in (8, 26):
            ms[f"icall-{rank}-k{k}"] = (lambda rank, k: lambda bc, t, s: ic_all(bc, t, rank, k))(rank, k)
    return ms


def one_draw(task):
    text, seed, names = task
    generator = random.Random(seed)
    wheels = ["I", "II", "III", "IV", "V"]
    order = tuple(generator.sample(wheels, 3))
    rings = tuple(generator.randrange(26) for _ in range(3))
    start = tuple(generator.randrange(26) for _ in range(3))
    plug = random_plugboard(generator, 10)
    cipher = EnigmaI(rotors=order, rings="".join(chr(65 + x) for x in rings),
                     positions="".join(chr(65 + x) for x in start), plugboard=plug).crypt(text)
    body = list(enigma_fast.text_to_indices(cipher))[:WINDOW]
    scorer, reflector = _S["scorer"], _S["reflector"]
    bc = stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body, _S["settings"])
    expected = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plug))

    def table_for(o, r, s):
        return enigma_fast.position_permutations([enigma_fast.rotor_tables(n) for n in o], r, s, WINDOW, reflector)
    import numpy as np

    true_table = np.asarray(table_for(order, rings, start), dtype=np.int64).reshape(WINDOW, 26)
    wrong = []
    for _ in range(NULLS):
        wo = tuple(generator.sample(wheels, 3))
        wr = tuple(generator.randrange(26) for _ in range(3))
        ws = tuple(generator.randrange(26) for _ in range(3))
        wrong.append(np.asarray(table_for(wo, wr, ws), dtype=np.int64).reshape(WINDOW, 26))
    letters = len(body)
    result = {}
    all_methods = methods()
    for name in names:
        method = all_methods[name]
        board, _ = method(bc, true_table, zlib.crc32(seed.encode()))
        true_score = bc._final_score(board, true_table) / letters
        exact = enigma_fast.plugboard_pairs(board) == expected
        nulls, evals, ic_evals, ng_evals = [], [], [], []
        for table in wrong:
            ACC["ic"] = ACC["ng"] = 0
            b, n = method(bc, table, 7)
            nulls.append(bc._final_score(b, table) / letters)
            evals.append(n)
            ic_evals.append(ACC["ic"])
            ng_evals.append(ACC["ng"])
        result[name] = {"score": true_score, "exact": exact, "nulls": nulls, "evals": statistics.fmean(evals),
                        "ic_evals": statistics.fmean(ic_evals), "ng_evals": statistics.fmean(ng_evals)}
    return result


def make_texts(kind: str, count: int):
    generator = random.Random(TEXT_SEED + (0 if kind == "low" else 1))
    tables = plaintext_power.ngram_tables(CONFIG)
    lo, hi = (0.0, 0.0575) if kind == "low" else (0.0585, 0.0630)
    texts = []
    while len(texts) < count:
        text = plaintext_power.markov_text(generator, tables, 167)
        if lo <= plaintext_power.coincidence(text) <= hi:
            texts.append(text)
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--set", choices=("low", "mid"), default="low")
    parser.add_argument("--texts", type=int, default=12)
    parser.add_argument("--draws-per-text", type=int, default=30)
    parser.add_argument("--z", type=float, default=6.0)
    parser.add_argument("--methods", default=",".join(methods()))
    parser.add_argument("--jobs", type=int, default=18)
    parser.add_argument("--output", default=None)
    arguments = parser.parse_args()
    names = arguments.methods.split(",")
    texts = make_texts(arguments.set, arguments.texts)
    ics = [plaintext_power.coincidence(t) for t in texts]
    print(f"{arguments.set} set: {len(texts)} texts, IC {min(ics):.4f} to {max(ics):.4f}, mean {statistics.fmean(ics):.4f}")
    tasks = [(texts[i % len(texts)], f"{KEY_SEED}:{arguments.set}:{i}", names)
             for i in range(len(texts) * arguments.draws_per_text)]
    started = time.time()
    with mp.Pool(arguments.jobs, initializer=init) as pool:
        draws = pool.map(one_draw, tasks, chunksize=1)
    base_cost = statistics.fmean(d["base"]["evals"] for d in draws) if "base" in names else None
    rows = []
    for name in names:
        pooled = [x for d in draws for x in d[name]["nulls"]]
        mean, sd = statistics.fmean(pooled), statistics.pstdev(pooled)
        threshold = mean + arguments.z * sd
        detected = sum(1 for d in draws if d[name]["exact"] and d[name]["score"] >= threshold)
        exact = sum(1 for d in draws if d[name]["exact"])
        cost = statistics.fmean(d[name]["evals"] for d in draws)
        n = len(draws)
        lo = (detected / n + 1.96**2 / (2 * n) - 1.96 * math.sqrt(detected / n * (1 - detected / n) / n + 1.96**2 / (4 * n * n))) / (1 + 1.96**2 / n)
        hi = (detected / n + 1.96**2 / (2 * n) + 1.96 * math.sqrt(detected / n * (1 - detected / n) / n + 1.96**2 / (4 * n * n))) / (1 + 1.96**2 / n)
        ic_cost = statistics.fmean(d[name]["ic_evals"] for d in draws)
        ng_cost = statistics.fmean(d[name]["ng_evals"] for d in draws)
        flags = [bool(d[name]["exact"] and d[name]["score"] >= threshold) for d in draws]
        rows.append({"method": name, "flags": flags, "ic_evals": round(ic_cost), "ng_evals": round(ng_cost), "detected": detected, "of": n, "rate": round(detected / n, 4),
                     "ci95": [round(lo, 4), round(hi, 4)], "exact_plugboard": exact,
                     "null_mean": round(mean, 4), "null_sd": round(sd, 4), "evals_per_null_climb": round(cost),
                     "relative_cost": None if base_cost is None else round(cost / base_cost, 2)})
        print(f"{name:14s} detected {detected:3d}/{n} ({detected / n:.3f}, {lo:.2f}-{hi:.2f})  exact {exact:3d}  "
              f"null {mean:.3f}+-{sd:.3f}  cost x{cost / base_cost if base_cost else float('nan'):.1f}  (ic {ic_cost:.0f} + ng {ng_cost:.0f} evals)", flush=True)
    print(f"{time.time() - started:.0f} s")
    if arguments.output:
        out = pathlib.Path(arguments.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"set": arguments.set, "ic": {"min": min(ics), "max": max(ics), "mean": statistics.fmean(ics)},
                                   "z": arguments.z, "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
