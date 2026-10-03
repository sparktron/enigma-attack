#!/usr/bin/env python3
"""Prototype numpy stecker climb, checked against ``stecker_climb``.

Exploratory measurement from docs/code-review-2026-10-02.md (R1). It is not
wired into the pipeline and needs numpy, which the project does not depend on.

Each pass of ``stecker_climb.climb_stecker`` scores about 350 candidate
plugboards one at a time in pure Python.  Here every candidate of a pass is
built as one ``(K, 26)`` array and decrypted and scored at once through the
precomputed ``(n, 26)`` position table.  The move set, move order, pair limit,
minimum-gain rule and first-best tie-break are the same, so the final
plugboard should match the reference exactly; the benchmark checks that.

Review result (``--cases 40 --seed 11``, one thread): 40/40 identical final
plugboards, 141 ms vs 16 ms per converged two-phase climb, about 8.7x.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import sys
import time
from collections.abc import Sequence

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import enigma_fast  # noqa: E402
import stecker_climb  # noqa: E402
import stecker_scoring  # noqa: E402
import stecker_traffic  # noqa: E402
from enigma import EnigmaI  # noqa: E402

CONFIG_PATH = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"

# Pair moves in the reference's nested-loop order: (0,1), (0,2), ..., (24,25).
FIRST, SECOND = np.triu_indices(26, k=1)
LETTERS = np.arange(26)


class BatchedObjectives:
    """Both climb objectives for one message at one rotor setting, batched."""

    def __init__(self, scorer: stecker_scoring.FastNgramScorer, table: Sequence[int], body: Sequence[int]):
        n = len(body)
        self.bigram = np.asarray(scorer.bigram)
        self.combined = np.asarray(scorer.combined)
        self.table = np.asarray(table, dtype=np.int64).reshape(n, 26)
        cipher = np.asarray(body, dtype=np.int64)
        self.valid = cipher >= 0
        self.cipher = np.where(self.valid, cipher, 0)
        self.rows = np.arange(n)
        previous = np.r_[False, self.valid[:-1]]
        before = np.r_[False, False, self.valid[:-2]]
        # A '?' resets the n-gram chain exactly as FastNgramScorer does: the
        # first letter after it scores nothing, the second a bigram only.
        self.trigram_positions = np.nonzero(self.valid & previous & before)[0]
        self.bigram_positions = np.nonzero(self.valid & previous & ~before)[0]
        self.letters = int(self.valid.sum())
        self.length = n

    def decrypt(self, boards: np.ndarray) -> np.ndarray:
        stepped = self.table[self.rows, boards[:, self.cipher]]
        return np.take_along_axis(boards, stepped, axis=1)

    def ngram(self, boards: np.ndarray) -> np.ndarray:
        text = self.decrypt(boards)
        t = self.trigram_positions
        total = self.combined[text[:, t - 2] * 676 + text[:, t - 1] * 26 + text[:, t]].sum(axis=1)
        b = self.bigram_positions
        if len(b):
            total = total + self.bigram[text[:, b - 1] * 26 + text[:, b]].sum(axis=1)
        return total

    def coincidence(self, boards: np.ndarray) -> np.ndarray:
        text = self.decrypt(boards)[:, self.valid]
        k = text.shape[0]
        counts = np.bincount(
            (text + 26 * np.arange(k)[:, None]).ravel(), minlength=26 * k
        ).reshape(k, 26)
        n = self.letters
        ic = (counts * (counts - 1)).sum(axis=1) / (n * (n - 1))
        # Same pooling weight as stecker_climb.body_direct_climb.coincidence.
        return ic * self.length / self.letters


def candidate_boards(current: np.ndarray, max_pairs: int) -> np.ndarray:
    """Every move ``climb_stecker`` would try from ``current``, in its order."""

    keep = current[FIRST] != SECOND
    first, second = FIRST[keep], SECOND[keep]
    rows = np.arange(len(first))
    boards = np.tile(current, (len(first), 1))
    partner_first, partner_second = current[first], current[second]
    boards[rows, partner_first] = partner_first
    boards[rows, partner_second] = partner_second
    boards[rows, first] = second
    boards[rows, second] = first
    boards = boards[(boards > LETTERS).sum(axis=1) <= max_pairs]

    plugged = LETTERS[current != LETTERS]
    unplug = np.tile(current, (len(plugged), 1))
    rows = np.arange(len(plugged))
    unplug[rows, current[plugged]] = current[plugged]
    unplug[rows, plugged] = plugged
    return np.vstack([boards, unplug])


def climb(objective, max_pairs: int, max_passes: int, minimum_gain: float, initial: Sequence[int]) -> list[int]:
    current = np.asarray(initial, dtype=np.int64)
    best = float(objective(current[None, :])[0])
    for _ in range(max_passes):
        trials = candidate_boards(current, max_pairs)
        scores = objective(trials)
        index = int(np.argmax(scores))  # first maximum, like the reference's strict '>' scan
        if not scores[index] > best + minimum_gain:
            break
        current, best = trials[index], float(scores[index])
    return current.tolist()


def batched_body_direct_climb(scorer, table, body, settings) -> list[int]:
    objectives = BatchedObjectives(scorer, table, body)
    by_name = {"index_of_coincidence": objectives.coincidence, "ngram": objectives.ngram}
    plugboard = list(range(26))
    for phase in settings["phases"]:
        plugboard = climb(
            by_name[phase],
            int(settings["max_pairs"]),
            int(settings["max_passes"]),
            float(settings["minimum_gain"]),
            plugboard,
        )
    return plugboard


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=int, default=40)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--length", type=int, default=167)
    parser.add_argument("--pairs", type=int, default=10)
    args = parser.parse_args(argv)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    settings = config["climb"]
    scorer = stecker_scoring.FastNgramScorer(config["scorer"])
    text = stecker_traffic.normalize_plaintext(config["climb_capability_calibration"]["plaintext"])[: args.length]
    reflector = enigma_fast.reflector_table("B")
    generator = random.Random(args.seed)
    wheels = ["I", "II", "III", "IV", "V"]

    identical = 0
    reference_seconds = batched_seconds = 0.0
    for case in range(args.cases):
        rotors = tuple(generator.sample(wheels, 3))
        rings = tuple(generator.randrange(26) for _ in range(3))
        start = tuple(generator.randrange(26) for _ in range(3))
        ciphertext = EnigmaI(
            rotors=rotors,
            rings="".join(chr(65 + v) for v in rings),
            positions="".join(chr(65 + v) for v in start),
            plugboard=stecker_traffic.random_plugboard(generator, args.pairs),
        ).crypt(text)
        body = list(enigma_fast.text_to_indices(ciphertext))
        if case % 3 == 0 and len(body) > 28:
            body[28] = -1  # exercise the uncertainty mask, as in BYQMZ
        if case % 2:
            # Half the cases climb at a wrong setting: the sweep is almost all wrong settings.
            rotors = tuple(generator.sample(wheels, 3))
            start = tuple(generator.randrange(26) for _ in range(3))
        order = [enigma_fast.rotor_tables(name) for name in rotors]
        table = enigma_fast.position_permutations(order, rings, start, len(body))

        began = time.perf_counter()
        reference, _ = stecker_climb.body_direct_climb(
            [stecker_traffic.Traffic("CASE", (0, 0, 0), (0, 0, 0), tuple(body))],
            rotors, rings, [start], scorer, reflector, settings,
        )
        middle = time.perf_counter()
        batched = batched_body_direct_climb(scorer, table, body, settings)
        ended = time.perf_counter()

        reference_seconds += middle - began
        batched_seconds += ended - middle
        if list(reference.plugboard) == batched:
            identical += 1
        else:
            print(
                f"case {case}: reference {enigma_fast.plugboard_pairs(reference.plugboard)} "
                f"| batched {enigma_fast.plugboard_pairs(batched)}"
            )

    print(f"identical final plugboard: {identical}/{args.cases}")
    print(
        f"reference {1000 * reference_seconds / args.cases:.1f} ms/climb | "
        f"batched {1000 * batched_seconds / args.cases:.1f} ms/climb | "
        f"speed-up x{reference_seconds / batched_seconds:.1f}"
    )
    return 0 if identical == args.cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
