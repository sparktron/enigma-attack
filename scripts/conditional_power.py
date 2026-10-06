#!/usr/bin/env python3
"""Conditional power strata for a Phase 1 end-to-end power artifact.

Written for phase1-middle-complete-power-v1 and driven by that configuration's
``end_to_end_power.conditional_analysis``. A draw is "missed" when neither
reference arm (the whole-message and the W = 117 middle-past-notch climbs, the
planted-key stand-in for sweeps v2 and v3 both being null) detects it. The
question is what the other arms detect among the missed draws, and what that is
worth per host-hour under the configuration's yield model.

Detection is recomputed exactly as the runner computes it: the top candidate's
plugboard is the planted one and its score reaches the arm's own threshold.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stecker_power import wilson_interval  # noqa: E402


def detection_flags(result: dict) -> list[dict]:
    """One record per draw: its cell, indel position and which arms detected it."""
    thresholds = {}
    for index, cell in enumerate(result["cells"]):
        for row in cell["arms"]:
            own = row.get("null", {}).get("detection_threshold_score_per_letter")
            thresholds[(index, row["arm"])] = (
                own if own is not None else cell["null"]["detection_threshold_score_per_letter"]
            )
    out = []
    for draw in result["draws"]:
        detected = {
            arm: bool(
                item["top"]["plugboard_recovered_exactly"]
                and item["top"]["score_per_letter"] >= thresholds[(draw["cell"], arm)]
            )
            for arm, item in draw["arms"].items()
        }
        fault = draw["planted"]["perturbation"]
        out.append({"cell": draw["cell"], "position": fault.get("position"), "detected": detected})
    return out


def rate(draws: list[dict], arm: str) -> dict:
    hits = sum(1 for d in draws if d["detected"][arm])
    return {"detected": hits, "n": len(draws),
            "rate": hits / len(draws) if draws else None,
            "interval_95": wilson_interval(hits, len(draws))}


def analyse(result: dict, plan: dict) -> dict:
    flags = detection_flags(result)
    refs = plan["reference_arms"]
    lo, hi = (int(v) for v in plan["middle_third"])
    missed = [d for d in flags if not any(d["detected"][a] for a in refs)]
    clean_all = [d for d in flags if d["cell"] == 0]
    indel_all = [d for d in flags if d["cell"] == 1]
    strata = {
        "clean": [d for d in missed if d["cell"] == 0],
        "indel_middle_third": [d for d in missed if d["cell"] == 1 and lo <= d["position"] <= hi],
        "indel_elsewhere": [d for d in missed if d["cell"] == 1 and not lo <= d["position"] <= hi],
    }
    arms = [a for a in flags[0]["detected"]]
    table = {name: {arm: rate(rows, arm) for arm in arms} for name, rows in strata.items()}
    minimum = int(plan["minimum_stratum_size"])
    scored = []
    for prediction in plan["predictions"]:
        cell = table[prediction["stratum"]][prediction["arm"]]
        if cell["n"] < minimum:
            verdict = "not estimable"
        elif prediction["kind"] == "rate_at_least":
            verdict = "held" if cell["rate"] >= prediction["value"] else "refuted"
        else:
            verdict = "held" if cell["rate"] <= prediction["value"] else "refuted"
        scored.append({"id": prediction["id"], "stratum_size": cell["n"], "rate": cell["rate"],
                       "threshold": prediction["value"], "kind": prediction["kind"], "verdict": verdict})

    model = plan["yield_model"]
    ratio, hours = float(model["settings_ratio"]), float(model["reference_host_hours"])
    indel_missed = strata["indel_middle_third"] + strata["indel_elsewhere"]
    m_clean = len(strata["clean"]) / len(clean_all) if clean_all else 0.0
    m_indel = len(indel_missed) / len(indel_all) if indel_all else 0.0
    a_clean = rate(strata["clean"], "complete_w117")["rate"] or 0.0
    a_indel = rate(indel_missed, "complete_w117")["rate"] or 0.0
    o_indel = rate(indel_missed, "oracle_past_notch")["rate"] or 0.0
    by_prior = {}
    for q in model["fault_priors_reported"]:
        w_clean, w_indel = (1 - q) * m_clean, q * m_indel
        total = w_clean + w_indel
        p_complete = (w_clean * a_clean + w_indel * a_indel) / total if total else 0.0
        p_split = w_indel * o_indel / total if total else 0.0
        by_prior[str(q)] = {
            "p_complete": p_complete, "p_split_ceiling": p_split,
            "complete_per_host_hour": p_complete / (ratio * hours),
            "break_even_cost_multiplier_k_star": ratio * p_split / p_complete if p_complete else None,
        }
    nominal = by_prior[str(model["nominal_fault_prior"])]
    verdicts = {p["id"]: p["verdict"] for p in scored}
    c1, c3 = verdicts.get("C1"), verdicts.get("C3")
    if c1 == "refuted" and c3 == "refuted":
        next_step = "neither"
    elif c3 == "refuted":
        next_step = "complete_only"
    elif c1 == "refuted":
        next_step = "split_only"
    elif "not estimable" in (c1, c3):
        next_step = "undecided: a stratum is too small"
    else:
        k_star = nominal["break_even_cost_multiplier_k_star"]
        next_step = ("split_first" if k_star is not None and k_star >= float(model["assumed_split_cost_multiplier"])
                     else "complete_first")
    return {
        "draws": {"clean": len(clean_all), "indel": len(indel_all)},
        "missed_by_both_reference_arms": {k: len(v) for k, v in strata.items()},
        "missed_fraction": {"clean": m_clean, "indel": m_indel},
        "detection_among_missed": table,
        "conditional_predictions": scored,
        "yield_by_fault_prior": by_prior,
        "rates_used": {"a_clean": a_clean, "a_indel": a_indel, "o_indel": o_indel},
        "next_step_per_decision_rule": next_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default=str(ROOT / "artifacts/phase1-middle-complete-power-v1.json"))
    parser.add_argument("--config", default=str(ROOT / "experiments/phase1-middle-complete-power-v1/config.json"))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    artifact = json.loads(pathlib.Path(args.artifact).read_text(encoding="utf-8"))
    plan = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8"))["end_to_end_power"]["conditional_analysis"]
    report = analyse(artifact["result"], plan)
    text = json.dumps(report, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
