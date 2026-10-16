#!/usr/bin/env python3
"""Post-run checks for phase1-body-direct-sweep-v6 and v7 (their two non-deciding predictions).

``--target v6`` (the default) is v6's run as recorded; ``--target v7`` runs the same checks
for the R-ngonly sweep (artifact and configuration of phase1-body-direct-sweep-v7), and in
addition re-climbs v6's retained rows with v7's climb for information only: v7's extra
starts are climbed by n-gram score alone, so a v6 setting may legitimately score lower
under it, and that is reported, not judged.  Below, "v6" in a docstring means the target.

``cuda-matches-reference-on-retained``
    Every one of v6's 100 retained candidates is re-climbed on the CPU, from its
    recorded wheel order, rings and start, with v6's own climb settings (W = 117
    head-and-tail windows, E first-plug starts).  The plugboard, the winning
    window and the score per letter (within 1e-9, the artifact stores nine
    decimals) must equal the cuda record.  Done twice: with the batched climber
    the cuda engine is specified against, and with the pure-Python reference
    climb that defines it.

``v4-retained-settings-do-not-fall``
    Each of v4's 100 retained settings is re-climbed with v6's settings.  The empty
    board is the first start and the climb from it is v4's, so the score must be
    at least v4's recorded score, to within 1e-9.  As a control that this check can
    see a difference, the same rows are also re-climbed with v4's own settings and
    must reproduce v4's recorded plugboard and score.

Also reported, not preregistered (check C): v6 swept every setting v4 did, so a v4
retained setting whose E-start score exceeds v6's 100th retained score must itself be
among v6's retained rows with that score.

Self-test: before the checks, the comparison is run against a deliberately wrong
plugboard and a deliberately lower score, and must flag both.

    python3 scripts/v6_postrun_checks.py --output data/review/v6-postrun-2026-10-13/summary.json
    python3 scripts/v6_postrun_checks.py --target v7 --output data/review/v7-postrun/summary.json
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import enigma_fast  # noqa: E402
import phase1_stecker as stecker  # noqa: E402
import stecker_batch  # noqa: E402
from stecker_climb import climb_windows, windowed_climb  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_traffic import traffic_from_corpus  # noqa: E402

TOLERANCE = 1e-9
TARGETS = {
    "v6": ("artifacts/phase1-body-direct-sweep-v6.json", "experiments/phase1-body-direct-sweep-v6/config.json"),
    "v7": ("artifacts/phase1-body-direct-sweep-v7.json", "experiments/phase1-body-direct-sweep-v7/config.json"),
}
V6 = ROOT / TARGETS["v6"][0]
V4 = ROOT / "artifacts/phase1-body-direct-sweep-v4.json"
V6_CONFIG = ROOT / TARGETS["v6"][1]
V4_CONFIG = ROOT / "experiments/phase1-body-direct-sweep-v4/config.json"
_STATE: dict = {}


def init(config_v6: dict, config_v4: dict) -> None:
    config = config_v6
    traffic = traffic_from_corpus(
        stecker.resolve_path(config["corpus"]), config["target"]["date"], config["target"]["messages"]
    )
    message = {m.designator: m for m in traffic}[config["body_direct_sweep"]["message"]]
    _STATE.update(
        scorer=FastNgramScorer(config["scorer"]),
        body=list(message.body),
        reflector=enigma_fast.reflector_table(config["machine"]["reflector"]),
        v6=config["climb"],
        v4=config_v4["climb"],
    )


def row_setting(row: dict):
    order = list(row["rotor_order_left_to_right"])
    return (
        order,
        tuple(ord(c) - 65 for c in row["rings"]),
        tuple(ord(c) - 65 for c in row["start_position"]),
    )


def climb_row(task: tuple[dict, str, str]) -> dict:
    """Re-climb one recorded setting. ``which`` is 'v6' or 'v4' (settings), ``engine`` 'batched' or 'reference'."""

    row, which, engine = task
    scorer, body, reflector = _STATE["scorer"], _STATE["body"], _STATE["reflector"]
    settings = _STATE[which]
    order, rings, start = row_setting(row)
    table = enigma_fast.position_permutations(
        [enigma_fast.rotor_tables(name) for name in order], rings, start, len(body), reflector
    )
    climbers = None
    if engine == "batched":
        climbers = [
            stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body[a:b], settings)
            for _, a, b in climb_windows(len(body), settings.get("window"))
        ]
    plugboard, evaluations, score, window = windowed_climb(table, body, scorer, settings, climbers)
    return {
        "plugboard": enigma_fast.plugboard_pairs(plugboard),
        "evaluations": evaluations,
        "score": score,
        "window": window,
    }


def matches(row: dict, got: dict) -> dict:
    """Compare a re-climb with a recorded row: plugboard, window, score (within TOLERANCE)."""

    delta = got["score"] - row["score_per_letter"]
    same_board = got["plugboard"] == row["plugboard"]
    same_window = got["window"] == row["window"]
    return {
        "plugboard_equal": same_board,
        "window_equal": same_window,
        "score_delta": delta,
        "score_within_tolerance": abs(delta) <= TOLERANCE,
        "identical": same_board and same_window and abs(delta) <= TOLERANCE,
    }


def self_test(row: dict, got: dict) -> dict:
    wrong_board = {**got, "plugboard": "AB CD"}
    lower = {**got, "score": got["score"] - 1e-6}
    flagged = (not matches(row, wrong_board)["identical"]) and (not matches(row, lower)["identical"])
    return {"real_row_identical": matches(row, got)["identical"], "wrong_plugboard_and_lower_score_flagged": flagged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target", choices=sorted(TARGETS), default="v6")
    parser.add_argument("--output", default=None)
    parser.add_argument("--jobs", type=int, default=16)
    arguments = parser.parse_args()

    target_artifact, target_config = (ROOT / path for path in TARGETS[arguments.target])
    output = arguments.output or (
        "data/review/v6-postrun-2026-10-13/summary.json" if arguments.target == "v6"
        else f"data/review/{arguments.target}-postrun/summary.json"
    )
    v6, v4 = json.loads(target_artifact.read_text(encoding="utf-8")), json.loads(V4.read_text(encoding="utf-8"))
    config_v6, config_v4 = stecker.load_config(target_config), stecker.load_config(V4_CONFIG)
    rows6, rows4 = v6["result"]["top_candidates"], v4["result"]["top_candidates"]
    started = time.time()
    init(config_v6, config_v4)
    with mp.Pool(arguments.jobs, initializer=init, initargs=(config_v6, config_v4)) as pool:
        test = self_test(rows6[0], climb_row((rows6[0], "v6", "batched")))
        if not test["real_row_identical"] or not test["wrong_plugboard_and_lower_score_flagged"]:
            print("SELF-TEST FAILED", test)
            return 2
        a_batched = pool.map(climb_row, [(r, "v6", "batched") for r in rows6])
        a_reference = pool.map(climb_row, [(r, "v6", "reference") for r in rows6])
        b_control = pool.map(climb_row, [(r, "v4", "batched") for r in rows4])
        b_e = pool.map(climb_row, [(r, "v6", "batched") for r in rows4])
        informational = None
        if arguments.target != "v6":
            rows_v6 = json.loads(V6.read_text(encoding="utf-8"))["result"]["top_candidates"]
            informational = (rows_v6, pool.map(climb_row, [(r, "v6", "batched") for r in rows_v6]))

    def tabulate(rows, got):
        return [matches(r, g) for r, g in zip(rows, got)]

    a1, a2, ctl = tabulate(rows6, a_batched), tabulate(rows6, a_reference), tabulate(rows4, b_control)
    deltas = [g["score"] - r["score_per_letter"] for r, g in zip(rows4, b_e)]
    fallen = [i for i, d in enumerate(deltas) if d < -TOLERANCE]
    # Check C: v4's rows against v6's retained set.
    key = lambda row: (tuple(row["rotor_order_left_to_right"]), row["rings"], row["start_position"])  # noqa: E731
    v6_keys = {key(r): r for r in rows6}
    floor = min(r["score_per_letter"] for r in rows6)
    inconsistent = []
    for r, g in zip(rows4, b_e):
        if g["score"] > floor + TOLERANCE:
            kept = v6_keys.get(key(r))
            if kept is None or abs(kept["score_per_letter"] - g["score"]) > TOLERANCE:
                inconsistent.append({"v4_rank": r["rank"], "e_score": g["score"], "in_v6_retained": kept is not None})
    summary = {
        "script": "scripts/v6_postrun_checks.py",
        "tolerance": TOLERANCE,
        "target": arguments.target,
        "target_artifact": str(target_artifact.relative_to(ROOT)),
        "v4_artifact": str(V4.relative_to(ROOT)),
        "target_code": v6["code"]["commit"],
        "seconds": round(time.time() - started, 1),
        "self_test": test,
        "cuda_matches_reference_on_retained": {
            "rows": len(rows6),
            "batched_identical": sum(x["identical"] for x in a1),
            "reference_identical": sum(x["identical"] for x in a2),
            "worst_abs_score_delta_batched": max(abs(x["score_delta"]) for x in a1),
            "worst_abs_score_delta_reference": max(abs(x["score_delta"]) for x in a2),
            "mismatches": [i for i, x in enumerate(a1) if not x["identical"]]
            + [100 + i for i, x in enumerate(a2) if not x["identical"]],
            "passed": all(x["identical"] for x in a1) and all(x["identical"] for x in a2),
        },
        "v4_retained_settings_do_not_fall": {
            "rows": len(rows4),
            "control_v4_settings_reproduce_v4_identical": sum(x["identical"] for x in ctl),
            "e_score_not_below_v4": len(rows4) - len(fallen),
            "fallen_rows": fallen,
            "rows_improved_by_e_starts": sum(1 for d in deltas if d > TOLERANCE),
            "rows_equal": sum(1 for d in deltas if abs(d) <= TOLERANCE),
            "largest_gain": max(deltas),
            "best_e_score_on_v4_rows": max(g["score"] for g in b_e),
            "passed": not fallen and all(x["identical"] for x in ctl),
        },
        "check_c_v4_rows_consistent_with_v6_retained": {
            "v6_100th_retained_score": floor,
            "inconsistent": inconsistent,
            "passed": not inconsistent,
        },
        "per_row": {
            "v6_batched": a1, "v6_reference": a2, "v4_control": ctl,
            "v4_e_scores": [{"v4_rank": r["rank"], "v4_score": r["score_per_letter"], "e_score": g["score"],
                             "delta": d, "window": g["window"]} for r, g, d in zip(rows4, b_e, deltas)],
        },
    }
    if informational is not None:
        rows_v6, got_v6 = informational
        deltas_v6 = [g["score"] - r["score_per_letter"] for r, g in zip(rows_v6, got_v6)]
        summary["informational_v6_retained_under_target_climb"] = {
            "note": "not a check: the target's extra starts are n-gram only, so a v6 setting may score lower here",
            "rows": len(rows_v6), "equal": sum(1 for d in deltas_v6 if abs(d) <= TOLERANCE),
            "higher": sum(1 for d in deltas_v6 if d > TOLERANCE), "lower": sum(1 for d in deltas_v6 if d < -TOLERANCE),
            "largest_gain": max(deltas_v6), "largest_drop": min(deltas_v6),
        }
    out = ROOT / output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    brief = {k: v for k, v in summary.items() if k != "per_row"}
    print(json.dumps(brief, indent=2))
    return 0 if all(summary[k]["passed"] for k in (
        "cuda_matches_reference_on_retained", "v4_retained_settings_do_not_fall",
        "check_c_v4_rows_consistent_with_v6_retained")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
