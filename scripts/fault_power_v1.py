#!/usr/bin/env python3
"""What the four completed BYQMZ sweeps' climbs cover, by kind of transcription fault.

Written for phase1-fault-power-v1 and driven by that configuration's
``end_to_end_power.fault_analysis``. The four sweep arms are the planted-key
stand-ins for sweeps v2, v3, v4 and v5 (whole-message and W = 117 past-notch,
W = 117 complete, and the complete split-point climb). A draw is "covered" when
at least one of them detects it, which is the planted-key analogue of a real key
of that kind showing up in at least one completed sweep. Each fault kind's
covered fraction is the power of the four nulls together against that kind, and
one minus it is the odds multiplier they leave.

Detection is recomputed exactly as the runner computes it, through
``conditional_power.detection_flags``.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from conditional_power import detection_flags, rate  # noqa: E402
from stecker_power import wilson_interval  # noqa: E402

NEXT_STEPS = {
    (True, True): "stop_the_standard_reading_search: both fault kinds are covered by the four nulls",
    (True, False): "cost_a_two_split_climb: two dropped or inserted letters are not covered",
    (False, True): "cost_a_substitution_tolerant_climb: a substituted letter is not covered",
    (False, False): "cost_a_substitution_tolerant_and_a_two_split_climb: neither fault kind is covered",
}


def analyse(result: dict, plan: dict) -> dict:
    flags = detection_flags(result)
    sweeps = plan["sweep_arms"]
    cells = plan["cells"]
    minimum = int(plan["minimum_draws"])
    arms = list(flags[0]["detected"])
    by_cell = {name: [d for d in flags if d["cell"] == index] for name, index in cells.items()}
    covered = {name: [d for d in rows if any(d["detected"][a] for a in sweeps)] for name, rows in by_cell.items()}
    table = {name: {arm: rate(rows, arm) for arm in arms} for name, rows in by_cell.items()}
    union = {}
    for name, rows in by_cell.items():
        hits, total = len(covered[name]), len(rows)
        union[name] = {
            "detected": hits, "n": total, "rate": hits / total if total else None,
            "interval_95": wilson_interval(hits, total),
            "odds_multiplier_left_by_four_nulls": (total - hits) / total if total else None,
        }
    scored = []
    for p in plan["predictions"]:
        cell = union[p["cell"]]
        if cell["n"] < minimum:
            verdict, observed = "not estimable", cell["rate"]
        elif p["kind"] == "rate_at_least":
            observed, verdict = cell["rate"], "held" if cell["rate"] >= p["value"] else "refuted"
        elif p["kind"] == "rate_below":
            observed, verdict = cell["rate"], "held" if cell["rate"] < p["value"] else "refuted"
        else:
            raise ValueError(f"unknown prediction kind: {p['kind']!r}")
        scored.append({"id": p["id"], "cell": p["cell"], "kind": p["kind"], "threshold": p["value"],
                       "draws": cell["n"], "observed": observed, "interval_95": cell["interval_95"],
                       "verdict": verdict})
    verdicts = {p["id"]: p["verdict"] for p in scored}
    substitution_covered = verdicts[plan["substitution_prediction"]] == "held"
    double_not_covered = verdicts[plan["double_indel_prediction"]] == "held"
    if "not estimable" in verdicts.values():
        step = "undecided: a deciding cell has too few draws"
    else:
        step = NEXT_STEPS[(substitution_covered, not double_not_covered)]
    return {
        "draws": {name: len(rows) for name, rows in by_cell.items()},
        "sweep_arms": sweeps,
        "detection_by_arm": table,
        "covered_by_any_sweep_arm": union,
        "predictions": scored,
        "next_step_per_decision_rule": step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default=str(ROOT / "artifacts/phase1-fault-power-v1.json"))
    parser.add_argument("--config", default=str(ROOT / "experiments/phase1-fault-power-v1/config.json"))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    artifact = json.loads(pathlib.Path(args.artifact).read_text(encoding="utf-8"))
    plan = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8"))["end_to_end_power"]["fault_analysis"]
    report = analyse(artifact["result"], plan)
    text = json.dumps(report, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
