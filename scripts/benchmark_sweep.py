#!/usr/bin/env python3
"""Time the body-direct sweep engine on a planted 167-letter message.

An exploratory measurement, not a preregistered experiment: it writes no
artifact and CI does not run it.  It sweeps whole wheel orders over the 676 middle and right
positions with each requested climb engine, reports seconds
per setting, and checks that the engines return the same retained candidates.

    python3 scripts/benchmark_sweep.py --settings 676 --jobs 1
    python3 scripts/benchmark_sweep.py --settings 20280 --jobs 18 --engines batched
    python3 scripts/benchmark_sweep.py --settings 6760 --jobs 10 --engines batched --window 117
    python3 scripts/benchmark_sweep.py --settings 6760 --jobs 10 --compare --split-grid 32 --repeats 2

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
    parser.add_argument(
        "--engines", nargs="+", default=None,
        help="climb engines to time (default: reference and batched, or only batched with --split-grid, "
        "which the split-point climb needs)",
    )
    parser.add_argument(
        "--window", type=int, default=None,
        help="climb the head and tail windows of this many letters instead of the whole message",
    )
    parser.add_argument(
        "--split-grid", type=int, default=None,
        help="climb with the split-point climb (index-of-coincidence grid of this many letters)",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="time the whole-message, W = 117 windowed and split-point climbs interleaved "
        "(needs --split-grid) and report each as a multiple of the windowed climb",
    )
    parser.add_argument("--repeats", type=int, default=1, help="rounds of --compare")
    arguments = parser.parse_args(argv)
    if arguments.engines is None:
        arguments.engines = ["batched"] if arguments.split_grid is not None else ["reference", "batched"]
    if arguments.split_grid is not None and arguments.engines != ["batched"] and not arguments.compare:
        parser.error("--split-grid needs the batched engine: use --engines batched")

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

    if arguments.compare:
        if arguments.split_grid is None:
            parser.error("--compare needs --split-grid")
        variants = {
            "whole": {},
            "windowed117": {"window": {"kind": "head_tail", "letters": 117}},
            "split": {"split": {"ic_grid": arguments.split_grid}},
        }
        seconds_per: dict[str, list[float]] = {name: [] for name in variants}
        for round_number in range(arguments.repeats):
            for name, extra in variants.items():
                settings = {**config["climb"], "engine": "batched", **extra}
                began = time.monotonic()
                _, evaluated, _, _ = sweep_slice(
                    message, orders, (0, 0, 0), starts, config["scorer"], reflector,
                    settings, 5, arguments.jobs,
                )
                took = time.monotonic() - began
                seconds_per[name].append(took)
                print(f"round {round_number + 1} {name:>12}: {evaluated} settings, {took:.1f} s, "
                      f"{1000 * took / evaluated:.2f} ms/setting (jobs {arguments.jobs})")
        mean = {name: sum(v) / len(v) for name, v in seconds_per.items()}
        for name in variants:
            print(f"{name:>12}: mean {1000 * mean[name] / evaluated:.2f} ms/setting, "
                  f"{mean[name] / mean['windowed117']:.2f} x windowed, {mean[name] / mean['whole']:.2f} x whole")
        return 0

    outcomes = {}
    for engine in arguments.engines:
        settings = {**config["climb"], "engine": engine}
        if arguments.window is not None:
            settings["window"] = {"kind": "head_tail", "letters": arguments.window}
        if arguments.split_grid is not None:
            settings["split"] = {"ic_grid": arguments.split_grid}
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
