#!/usr/bin/env python3
"""Can the body-direct sweep reach a setting equivalent to the true daily key?

Exploratory measurement from docs/code-review-2026-10-02.md (P1, P2). It is
not a preregistered experiment and writes no artifact under ``artifacts/``.

The Phase 1 calibration climbs at the exact true ``(rings, start)``.  A sweep
holds some rings fixed and searches start positions, so what it can visit is a
setting with the same wheel offsets but a different right-wheel turnover and/or
middle-wheel notch phase.  For each random key this script builds the settings
a given parameterization can reach (the offset-matched one and its left/middle
neighbours), measures position by position how much of each is equivalent to
the true machine, climbs the most equivalent ones and keeps the best by score.

Modes
    exact              climb at the true key (what the calibration measures)
    rings-aaa          all rings held at A; 60 x 26^3 space
    reducible          left/middle rings held at A, right ring searched;
                       the artifact's 60 x 26^4 "reducible space"
    per-offset-middle  as ``reducible``, but the held middle ring is chosen per
                       middle offset so the swept middle wheel starts just past
                       its notch and cannot step the left wheel in the message

Review results (167 letters, 10 pairs, ``--seed-base 9000``):
    exact 32 draws: 30/32 recovered
    rings-aaa 32 draws: 0/32 exact equivalent, 4/32 recovered
    reducible 48 draws: 25/48 exact equivalent, 33/48 recovered
    per-offset-middle 48 draws: 33/48 exact equivalent, 36/48 recovered
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import enigma_fast  # noqa: E402
import phase1_stecker  # noqa: E402
from enigma import EnigmaI  # noqa: E402

CONFIG_PATH = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
PLAINTEXT = phase1_stecker.normalize_plaintext(
    CONFIG["climb_capability_calibration"]["plaintext"]
)
REFLECTOR = enigma_fast.reflector_table("B")
WHEELS = ["I", "II", "III", "IV", "V"]
MODES = ("exact", "rings-aaa", "reducible", "per-offset-middle")

_SCORER: phase1_stecker.FastNgramScorer | None = None


def scorer() -> phase1_stecker.FastNgramScorer:
    global _SCORER
    if _SCORER is None:
        _SCORER = phase1_stecker.FastNgramScorer(CONFIG["scorer"])
    return _SCORER


def draw_key(draw: int, seed_base: int, pairs: int):
    """One random daily key and message start, reproducible from the draw index."""

    generator = random.Random(seed_base + draw)
    rotors = tuple(generator.sample(WHEELS, 3))
    rings = tuple(generator.randrange(26) for _ in range(3))
    start = tuple(generator.randrange(26) for _ in range(3))
    plugboard = phase1_stecker.random_plugboard(generator, pairs)
    return rotors, rings, start, plugboard


def equivalent_fraction(order, rings_a, start_a, rings_b, start_b, length: int) -> float:
    """Fraction of positions at which two settings apply the same permutation."""

    a = enigma_fast.position_permutations(order, rings_a, start_a, length)
    b = enigma_fast.position_permutations(order, rings_b, start_b, length)
    return sum(a[26 * t : 26 * t + 26] == b[26 * t : 26 * t + 26] for t in range(length)) / length


def reachable_settings(mode: str, order, rings, start):
    """The (rings, start) settings ``mode`` can visit that lie near the true key."""

    left_offset = (start[0] - rings[0]) % 26
    middle_offset = (start[1] - rings[1]) % 26
    right_offset = (start[2] - rings[2]) % 26
    if mode == "rings-aaa":
        return [
            ((0, 0, 0), (left_offset, (middle_offset + dm) % 26, right_offset))
            for dm in (0, 1, -1)
        ]
    settings = []
    notch = min(order[1].notches)
    for dl in (0, 1, -1):
        for dm in (0, 1, -1, 2, -2):
            left = (left_offset + dl) % 26
            middle = (middle_offset + dm) % 26
            if mode == "reducible":
                settings.append(((0, 0, rings[2]), (left, middle, start[2])))
            else:  # per-offset-middle
                position = (notch + 1) % 26
                settings.append(((0, (position - middle) % 26, rings[2]), (left, position, start[2])))
    return settings


def run(task: tuple[str, int, int, int, int, int]) -> dict:
    mode, draw, length, pairs, seed_base, climbs = task
    rotors, rings, start, plugboard = draw_key(draw, seed_base, pairs)
    text = PLAINTEXT[:length]
    ciphertext = EnigmaI(
        rotors=rotors,
        rings="".join(chr(65 + v) for v in rings),
        positions="".join(chr(65 + v) for v in start),
        plugboard=plugboard,
    ).crypt(text)
    message = phase1_stecker.Traffic(
        f"DRAW-{draw}", (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices(ciphertext)
    )
    order = [enigma_fast.rotor_tables(name) for name in rotors]
    truth = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard))

    if mode == "exact":
        candidates = [(1.0, rings, start)]
    else:
        candidates = sorted(
            (
                (equivalent_fraction(order, rings, start, r, s, length), r, s)
                for r, s in reachable_settings(mode, order, rings, start)
            ),
            reverse=True,
        )
    best = None
    for fraction, r, s in candidates[:climbs]:
        outcome, plaintexts = phase1_stecker.body_direct_climb(
            [message], rotors, r, [s], scorer(), REFLECTOR, CONFIG["climb"]
        )
        found = enigma_fast.plugboard_pairs(outcome.plugboard)
        row = {
            "score_per_letter": round(outcome.score_per_letter, 4),
            "plugboard_recovered": found == truth,
            "correct_pairs": len(set(truth.split()) & set(found.split())),
            "plaintext_agreement": round(sum(a == b for a, b in zip(plaintexts[0], text)) / length, 3),
            "equivalent_fraction": round(fraction, 3),
            "rings": "".join(chr(65 + v) for v in r),
            "start": "".join(chr(65 + v) for v in s),
        }
        if best is None or row["score_per_letter"] > best["score_per_letter"]:
            best = row
    return {
        "draw": draw,
        "true_rings": "".join(chr(65 + v) for v in rings),
        "exact_equivalent_reachable": candidates[0][0] == 1.0,
        "best": best,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=MODES, default="reducible")
    parser.add_argument("--draws", type=int, default=48)
    parser.add_argument("--length", type=int, default=167)
    parser.add_argument("--pairs", type=int, default=10)
    parser.add_argument("--seed-base", type=int, default=9000)
    parser.add_argument("--climbs", type=int, default=3, help="most-equivalent settings climbed per draw")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--output", type=pathlib.Path, default=None, help="optional JSON with every draw")
    args = parser.parse_args(argv)

    started = time.monotonic()
    tasks = [
        (args.mode, draw, args.length, args.pairs, args.seed_base, args.climbs)
        for draw in range(args.draws)
    ]
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(run, tasks))
    else:
        results = [run(task) for task in tasks]

    for row in results:
        best = row["best"]
        print(
            f"draw {row['draw']:3d} rings={row['true_rings']} "
            f"equiv={best['equivalent_fraction']:.2f} pairs={best['correct_pairs']:2d}/{args.pairs} "
            f"agree={best['plaintext_agreement']:.2f} score={best['score_per_letter']:.3f} "
            f"recovered={best['plugboard_recovered']}"
        )
    n = len(results)
    print(f"\nmode={args.mode} length={args.length} pairs={args.pairs} draws={n}")
    print(f"exact equivalent reachable: {sum(r['exact_equivalent_reachable'] for r in results)}/{n}")
    print(f"plugboard recovered:        {sum(r['best']['plugboard_recovered'] for r in results)}/{n}")
    print(f"median best score/letter:   {statistics.median(r['best']['score_per_letter'] for r in results):.3f}")
    print(f"elapsed {time.monotonic() - started:.1f}s")
    if args.output:
        args.output.write_text(json.dumps({"arguments": vars(args) | {"output": str(args.output)}, "draws": results}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
