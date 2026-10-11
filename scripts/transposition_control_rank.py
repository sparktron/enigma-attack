#!/usr/bin/env python3
"""Rank every key pair of the Phase 6 and Phase 7 5x7 known-key control.

The control (``independent-solved-army-text-1941-09-24-94``, 76 letters, widths
5 and 7) fails under the recorded search, which anneals 12,008 of its 604,800
key pairs and recovers the plaintext rotated by one character. This scores all
of them with the control's own scorer, to show what the objective prefers and
which keys read out a rotation of the plaintext. Read-only; it records nothing.
"""

from __future__ import annotations

import argparse
import itertools
import json
import multiprocessing as mp
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import phase6  # noqa: E402
from phase7 import PublishedNgramScorer  # noqa: E402

PHASE6 = ROOT / "experiments/phase6-qtxma-double-transposition-smoke-v2/config.json"
PHASE7 = ROOT / "experiments/phase7-qtxma-source-and-scorer-v2/config.json"
CONTROL = "independent-solved-army-text-1941-09-24-94"

_STATE: dict = {}


def _init(ciphertext: str, scorer_config: dict, first_width: int) -> None:
    _STATE["ciphertext"] = ciphertext
    _STATE["scorer"] = PublishedNgramScorer(scorer_config)
    _STATE["first_orders"] = list(itertools.permutations(range(first_width)))


def _rows(second_order: tuple[int, ...]) -> list[tuple[float, tuple[int, ...], tuple[int, ...], str]]:
    scorer = _STATE["scorer"]
    middle = phase6.columnar_untranspose(_STATE["ciphertext"], second_order)
    rows = []
    for first_order in _STATE["first_orders"]:
        text = phase6.columnar_untranspose(middle, first_order)
        raw, known = scorer.score(text)
        rows.append((raw / known, first_order, second_order, text))
    return rows


def analyse(jobs: int) -> dict:
    scorer_config = json.loads(PHASE7.read_text(encoding="utf-8"))["scorer"]
    config = phase6.load_config(PHASE6)
    control = next(c for c in phase6._normalize_positive_controls(config) if c["id"] == CONTROL)
    plaintext = control["plaintext"]
    first, second = tuple(control["first_order"]), tuple(control["second_order"])
    ciphertext = phase6.double_columnar_transpose(plaintext, first, second)
    rotations = {plaintext[k:] + plaintext[:k]: k for k in range(1, len(plaintext))}
    started = time.monotonic()
    with mp.Pool(jobs, initializer=_init, initargs=(ciphertext, scorer_config, len(first))) as pool:
        rows = [row for chunk in pool.imap_unordered(
            _rows, itertools.permutations(range(len(second))), chunksize=20) for row in chunk]
    rows.sort(key=lambda row: (-row[0], row[1], row[2]))
    rank = {(row[1], row[2]): index + 1 for index, row in enumerate(rows)}
    rotating = [
        {"rotation": rotations[row[3]], "first_order": list(row[1]), "second_order": list(row[2]),
         "rank": rank[(row[1], row[2])], "score_per_letter": row[0]}
        for row in rows if row[3] in rotations
    ]
    return {
        "control": CONTROL, "letters": len(plaintext), "key_pairs": len(rows),
        "known_key": {"first_order": list(first), "second_order": list(second),
                      "rank": rank[(first, second)], "score_per_letter": rows[rank[(first, second)] - 1][0]},
        "keys_reading_out_a_rotation_of_the_plaintext": rotating,
        "top": [{"rank": i + 1, "score_per_letter": row[0], "first_order": list(row[1]),
                 "second_order": list(row[2])} for i, row in enumerate(rows[:5])],
        "seconds": round(time.monotonic() - started, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=max(1, (mp.cpu_count() or 2) - 2))
    parser.add_argument("--output")
    arguments = parser.parse_args(argv)
    text = json.dumps(analyse(arguments.jobs), indent=2)
    if arguments.output:
        pathlib.Path(arguments.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
