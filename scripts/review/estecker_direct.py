#!/usr/bin/env python3
"""Does starting the climb from several first plugs (partial exhaustion) help?

Exploratory measurement from docs/code-review-2026-10-11.md (B-1, S-1).  It is
not a preregistered experiment and writes no artifact under ``artifacts/``.

Ostwald and Weierud (*Modern Breaking of Enigma Ciphertexts*, Cryptologia 2017,
section 7) answer the failure of the index-of-coincidence phase on short or
low-IC plaintexts by exhausting the first plug: start the hill-climb not only
from the empty plugboard but from every board with one plug on a frequent
letter, and keep the best result.  Their "E-Stecker" starts from the 25 E-X
pairs plus E self-steckered (26 starts); "R-Stecker" uses E, N and R (73
starts); "I-Stecker" adds X, S and I (136).  The repository's climb starts only
from the empty plugboard.

For random planted keys this script climbs at the **true** setting with each
start set and calibrates each method against its own null (the same method run
at random wrong settings of the same ciphertext), so extra starts cannot win by
raising the noise floor.  Detection is ``score >= null mean + 6 sd``, the
harness's rule.  It patches ``stecker_climb.run_climb_phases`` inside this
process only; nothing in the repository is modified.

    python3 scripts/review/estecker_direct.py --text markov-0 --draws 36 \\
        --methods base,E,R

Review results (167 letters, ten pairs, true-setting climb; text names are
those ``plaintext_power.py`` generates with its default text seed):
    markov-0  IC 0.0578:  base 5/24   E 19/24   (this script, 24 draws)
    markov-10 IC 0.0514:  base 3/36   E 14/36   R 27/36   (an earlier copy of this
                          script with different draw seeds, 36 draws)
Through the repository's own end-to-end harness (whole-message arm), a
hand-written text of IC 0.0587 went from 27/95 detected given an exact
equivalent (120 draws) to 34/47 (the first 60 draws) with E-Stecker starts
patched in.
Cost is the number of starts: 26 for E, 73 for R, 136 for I.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import pathlib
import random
import statistics
import sys
import json

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import enigma_fast  # noqa: E402
import plaintext_power  # noqa: E402
import stecker_climb  # noqa: E402
from enigma import EnigmaI  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_traffic import Traffic, random_plugboard  # noqa: E402

CONFIG = json.loads((ROOT / "experiments/phase1-end-to-end-power-v1/config.json").read_text(encoding="utf-8"))
SCORER = FastNgramScorer(CONFIG["scorer"])
REFLECTOR = enigma_fast.reflector_table("B")
CLIMB = CONFIG["climb"]
# Letter indices: E=4, N=13, R=17, X=23, S=18, I=8.
LETTERS = {"E": [4], "R": [4, 13, 17], "I": [4, 13, 17, 23, 18, 8]}


def start_boards(method: str) -> list[list[int]]:
    boards = [list(range(26))]
    if method == "base":
        return boards
    seen = set()
    for a in LETTERS[method]:
        for b in range(26):
            pair = (min(a, b), max(a, b))
            if a == b or pair in seen:
                continue
            seen.add(pair)
            board = list(range(26))
            board[a], board[b] = b, a
            boards.append(board)
    return boards


def climber_for(method: str):
    boards = start_boards(method)

    def run(phases, objectives, letters, settings):
        best = None
        used = 0
        for board in boards:
            plugboard, records = list(board), []
            for objective in phases:
                outcome = stecker_climb.climb_stecker(
                    objectives[objective], letters, int(settings["max_pairs"]),
                    int(settings["max_passes"]), float(settings["minimum_gain"]), plugboard,
                )
                plugboard = list(outcome.plugboard)
                used += outcome.evaluations
                records.append({
                    "objective": objective,
                    "plugboard": enigma_fast.plugboard_pairs(plugboard),
                    "plugboard_pairs": outcome.pair_count,
                    "passes": outcome.passes,
                    "evaluations": outcome.evaluations,
                })
            score = objectives["ngram"](plugboard)
            if best is None or score > best[0]:
                best = (score, plugboard, records)
        return best[1], best[2], used

    return run


def one_draw(task):
    text, seed, method = task
    generator = random.Random(seed)
    wheels = ["I", "II", "III", "IV", "V"]
    order = tuple(generator.sample(wheels, 3))
    rings = tuple(generator.randrange(26) for _ in range(3))
    start = tuple(generator.randrange(26) for _ in range(3))
    plugboard = random_plugboard(generator, 10)
    cipher = EnigmaI(
        rotors=order, rings="".join(chr(65 + x) for x in rings),
        positions="".join(chr(65 + x) for x in start), plugboard=plugboard,
    ).crypt(text)
    message = Traffic("REVIEW", (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices(cipher))
    stecker_climb.run_climb_phases = climber_for(method)
    expected = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard))
    outcome, _ = stecker_climb.body_direct_climb([message], list(order), list(rings), [list(start)], SCORER, REFLECTOR, CLIMB)
    exact = enigma_fast.plugboard_pairs(outcome.plugboard) == expected
    nulls = []
    for _ in range(6):
        wrong_order = list(generator.sample(wheels, 3))
        wrong_rings = [generator.randrange(26) for _ in range(3)]
        wrong_start = [generator.randrange(26) for _ in range(3)]
        result, _ = stecker_climb.body_direct_climb([message], wrong_order, wrong_rings, [wrong_start], SCORER, REFLECTOR, CLIMB)
        nulls.append(result.score_per_letter)
    return outcome.score_per_letter, exact, nulls


def resolve_text(name: str) -> str:
    if name == "repository":
        return CONFIG["end_to_end_power"]["plaintext"][:167]
    if name.startswith("markov-"):
        generator = random.Random(11)
        tables = plaintext_power.ngram_tables(CONFIG)
        index = int(name.split("-")[1])
        text = ""
        for _ in range(index + 1):
            text = plaintext_power.markov_text(generator, tables, 167)
        return text
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--text", default="markov-0", help="repository, markov-N, or literal A-Z text of 167 letters")
    parser.add_argument("--draws", type=int, default=36)
    parser.add_argument("--methods", default="base,E")
    parser.add_argument("--jobs", type=int, default=16)
    arguments = parser.parse_args()
    text = resolve_text(arguments.text)
    print(f"{arguments.text}: IC {plaintext_power.coincidence(text):.4f}, {len(text)} letters")
    with mp.Pool(arguments.jobs) as pool:
        for method in arguments.methods.split(","):
            tasks = [(text, f"estecker:{arguments.text}:{i}", method) for i in range(arguments.draws)]
            results = pool.map(one_draw, tasks)
            nulls = [x for r in results for x in r[2]]
            mean, sd = statistics.mean(nulls), statistics.pstdev(nulls)
            threshold = mean + 6 * sd
            detected = sum(1 for r in results if r[0] >= threshold)
            exact = sum(1 for r in results if r[1])
            print(f"  {method:5s} starts={len(start_boards(method)):3d}  exact plugboard {exact}/{arguments.draws}  "
                  f"score>=null+6sd {detected}/{arguments.draws}  (null mean {mean:.3f}, sd {sd:.3f})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
