#!/usr/bin/env python3
"""Compare the split-point climb with the complete rule on the control's draws.

Written for phase1-split-point-power-v1, which reruns the draws of
phase1-middle-complete-power-v1 (same seed, so the same planted keys and
faults) with the split-point climb as a new arm. This joins the two artifacts
draw by draw, refuses to go on if a draw differs, checks that the two
past-notch arms reproduce the control exactly, and then asks of the draws both
past-notch climbs miss what the split-point climb and the complete rule each
detect, and what each is worth per host-hour under the control's yield model.

Detection is recomputed as the runner computes it, per artifact, from the top
candidate's plugboard and each arm's own detection threshold.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from conditional_power import detection_flags, rate  # noqa: E402


def join(split_result: dict, control_result: dict, controls: list[str]) -> tuple[list[dict], dict]:
    """One record per draw with every arm's flag, from both artifacts."""

    mine, theirs = detection_flags(split_result), detection_flags(control_result)
    if len(mine) != len(theirs):
        raise ValueError(f"the artifacts hold {len(mine)} and {len(theirs)} draws")
    for a, b, da, db in zip(mine, theirs, split_result["draws"], control_result["draws"]):
        if (da["cell"], da["draw"], da["planted"]) != (db["cell"], db["draw"], db["planted"]):
            raise ValueError(f"draw {da['cell']}:{da['draw']} was planted differently in the two artifacts")
    differing = {
        arm: sum(1 for a, b in zip(mine, theirs) if a["detected"][arm] != b["detected"][arm])
        for arm in controls
    }
    merged = []
    for a, b in zip(mine, theirs):
        flags = dict(a["detected"])
        for arm, value in b["detected"].items():
            flags.setdefault(arm, value)
        merged.append({"cell": a["cell"], "position": a["position"], "detected": flags})
    return merged, differing


def analyse(split_result: dict, control_result: dict, plan: dict) -> dict:
    draws, differing = join(split_result, control_result, plan["reference_arms"])
    refs = plan["reference_arms"]
    lo, hi = (int(v) for v in plan["middle_third"])
    missed = [d for d in draws if not any(d["detected"][a] for a in refs)]
    clean_all = [d for d in draws if d["cell"] == 0]
    indel_all = [d for d in draws if d["cell"] == 1]
    strata = {
        "clean": [d for d in missed if d["cell"] == 0],
        "indel_middle_third": [d for d in missed if d["cell"] == 1 and lo <= d["position"] <= hi],
        "indel_elsewhere": [d for d in missed if d["cell"] == 1 and not lo <= d["position"] <= hi],
    }
    arms = list(draws[0]["detected"])
    table = {name: {arm: rate(rows, arm) for arm in arms} for name, rows in strata.items()}
    # Either of two arms, for the exploratory question of whether they overlap.
    either = {
        name: rate([dict(d, detected={"either": d["detected"][plan["candidates"]["split"]["arm"]]
                                      or d["detected"][plan["candidates"]["complete"]["arm"]]}) for d in rows], "either")
        for name, rows in strata.items()
    }
    minimum = int(plan["minimum_stratum_size"])
    scored = []
    for p in plan["predictions"]:
        cell = table[p["stratum"]][p["arm"]]
        if cell["n"] < minimum:
            verdict = "not estimable"
        elif p["kind"] == "rate_at_least":
            verdict = "held" if cell["rate"] >= p["value"] else "refuted"
        else:
            verdict = "held" if cell["rate"] <= p["value"] else "refuted"
        scored.append({"id": p["id"], "stratum_size": cell["n"], "rate": cell["rate"],
                       "threshold": p["value"], "kind": p["kind"], "verdict": verdict})

    model = plan["yield_model"]
    reference_hours = float(model["reference_host_hours"])
    indel_missed = strata["indel_middle_third"] + strata["indel_elsewhere"]
    m_clean = len(strata["clean"]) / len(clean_all) if clean_all else 0.0
    m_indel = len(indel_missed) / len(indel_all) if indel_all else 0.0

    def conditional(arm: str, q: float) -> float:
        w_clean, w_indel = (1 - q) * m_clean, q * m_indel
        total = w_clean + w_indel
        a_clean = rate(strata["clean"], arm)["rate"] or 0.0
        a_indel = rate(indel_missed, arm)["rate"] or 0.0
        return (w_clean * a_clean + w_indel * a_indel) / total if total else 0.0

    hours = {name: float(c["cost_multiplier"]) * reference_hours for name, c in plan["candidates"].items()}
    by_prior = {}
    for q in model["fault_priors_reported"]:
        row = {}
        for name, c in plan["candidates"].items():
            p = conditional(c["arm"], q)
            row[name] = {"probability": p, "host_hours": hours[name], "per_host_hour": p / hours[name]}
        row["better_per_host_hour"] = max(plan["candidates"], key=lambda n: row[n]["per_host_hour"])
        by_prior[str(q)] = row
    verdicts = {p["id"]: p["verdict"] for p in scored}
    deciding = [verdicts[i] for i in plan["deciding_predictions"]]
    if "not estimable" in deciding:
        next_step = "undecided: a stratum is too small"
    elif all(v == "refuted" for v in deciding):
        next_step = "complete_sweep"
    else:
        next_step = by_prior[str(model["nominal_fault_prior"])]["better_per_host_hour"] + "_sweep"
    return {
        "draws": {"clean": len(clean_all), "indel": len(indel_all)},
        "past_notch_arms_differing_from_the_control": differing,
        "missed_by_both_reference_arms": {k: len(v) for k, v in strata.items()},
        "missed_fraction": {"clean": m_clean, "indel": m_indel},
        "detection_among_missed": table,
        "either_candidate_among_missed_exploratory": either,
        "predictions": scored,
        "yield_by_fault_prior": by_prior,
        "next_step_per_decision_rule": next_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default=str(ROOT / "artifacts/phase1-split-point-power-v1.json"))
    parser.add_argument("--control", default=str(ROOT / "artifacts/phase1-middle-complete-power-v1.json"))
    parser.add_argument("--config", default=str(ROOT / "experiments/phase1-split-point-power-v1/config.json"))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    split = json.loads(pathlib.Path(args.artifact).read_text(encoding="utf-8"))
    control = json.loads(pathlib.Path(args.control).read_text(encoding="utf-8"))
    plan = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8"))["end_to_end_power"]["split_analysis"]
    report = analyse(split["result"], control["result"], plan)
    text = json.dumps(report, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
