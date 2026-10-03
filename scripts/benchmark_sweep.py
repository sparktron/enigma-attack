#!/usr/bin/env python3
"""Time the body-direct sweep engine on a planted 167-letter message.

An exploratory measurement, not a preregistered experiment: it writes no
artifact and CI does not run it.  It sweeps whole wheel orders over the 676 middle and right
positions with each requested climb engine, reports seconds
per setting, and checks that the engines return the same retained candidates.

    python3 scripts/benchmark_sweep.py --settings 676 --jobs 1
    python3 scripts/benchmark_sweep.py --settings 20280 --jobs 18 --engines batched

``--settings`` is rounded up to a whole number of wheel orders (676 settings each).

``--jobs`` is the worker count the engine is given.  Timing includes the
Python work of building every position table, which the batched climb does not
remove.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import enigma_fast  # noqa: E402
import phase1_stecker as stecker  # noqa: E402
from enigma import EnigmaI  # noqa: E402
from stecker_space import rotor_order_space  # noqa: E402
from stecker_sweeps import sweep_slice  # noqa: E402
from stecker_traffic import Traffic, normalize_plaintext  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--settings", type=int, default=2000)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--engines", nargs="+", default=["reference", "batched"])
    arguments = parser.parse_args(argv)

    config = stecker.load_config(ROOT / "experiments/phase1-body-direct-sweep-v1/config.json")
    calibration = stecker.load_config(ROOT / "experiments/phase1-stecker-calibration-v1/config.json")
    plaintext = normalize_plaintext(
        calibration["climb_capability_calibration"]["plaintext"], 167
    )
    plugboard = "AN BY CF DR GJ HS IL KM PV QZ"
    message = Traffic(
        "BENCH", (0, 0, 0), (0, 0, 0),
        enigma_fast.text_to_indices(
            EnigmaI(rotors=("I", "II", "III"), rings="AAA", positions="AEF", plugboard=plugboard).crypt(plaintext)
        ),
    )
    # The 676 middle and right positions of one wheel order, repeated over as many
    # wheel orders as it takes to reach the requested count, so the slice splits
    # into one chunk per (order, middle) as a full sweep does.
    starts = [(0, middle, right) for middle in range(26) for right in range(26)]
    orders = rotor_order_space("all_permutations", ["I", "II", "III", "IV", "V"])
    orders = orders[: max(1, -(-arguments.settings // len(starts)))]
    reflector = enigma_fast.reflector_table("B")

    outcomes = {}
    for engine in arguments.engines:
        settings = {**config["climb"], "engine": engine}
        began = time.monotonic()
        ranked, evaluated, _, execution = sweep_slice(
            message, orders, (0, 0, 0), starts, config["scorer"], reflector,
            settings, 5, arguments.jobs,
        )
        seconds = time.monotonic() - began
        outcomes[engine] = [(row["start_position"], row["plugboard"]) for row in ranked]
        print(
            f"{engine:>9}: {evaluated} settings, {execution['chunks']} chunks, "
            f"{seconds:.2f} s wall, {1000 * seconds / evaluated:.2f} ms/setting "
            f"(jobs {arguments.jobs}), best {ranked[0]['start_position']} "
            f"{ranked[0]['score_per_letter']:.4f}"
        )
    if len(outcomes) > 1:
        first = next(iter(outcomes.values()))
        same = all(rows == first for rows in outcomes.values())
        print(f"retained candidates identical across engines: {same}")
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
