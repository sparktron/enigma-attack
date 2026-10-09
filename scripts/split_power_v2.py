#!/usr/bin/env python3
"""The split-point climb's power given that sweeps v2, v3 and v4 are all null.

Written for phase1-split-point-power-v2 and driven by that configuration's
``end_to_end_power.split_v2_analysis``. A draw is "missed" when none of the
three reference arms detects it. Those arms are the planted-key stand-ins for
the three completed sweeps of BYQMZ: the whole-message and W = 117
middle-past-notch climbs (v2, v3) and the W = 117 middle-complete climb (v4).
The question is what the split-point arms detect among the missed draws, which
decides whether a complete split-point sweep is preregistered, and gives that
sweep's stated power.

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
from conditional_power import detection_flags, rate  # noqa: E402


def analyse(result: dict, plan: dict) -> dict:
    flags = detection_flags(result)
    refs = plan["reference_arms"]
    lo, hi = (int(v) for v in plan["middle_third"])
    missed = [d for d in flags if not any(d["detected"][a] for a in refs)]
    clean_all = [d for d in flags if d["cell"] == 0]
    indel_all = [d for d in flags if d["cell"] == 1]
    strata = {
        "clean": [d for d in missed if d["cell"] == 0],
        "indel": [d for d in missed if d["cell"] == 1],
        "indel_middle_third": [d for d in missed if d["cell"] == 1 and lo <= d["position"] <= hi],
        "indel_elsewhere": [d for d in missed if d["cell"] == 1 and not lo <= d["position"] <= hi],
    }
    arms = list(flags[0]["detected"])
    table = {name: {arm: rate(rows, arm) for arm in arms} for name, rows in strata.items()}
    minimum = int(plan["minimum_stratum_size"])
    scored = []
    for p in plan["predictions"]:
        stratum = strata[p["stratum"]]
        cell = table[p["stratum"]][p["arm"]]
        if cell["n"] < minimum:
            verdict, observed = "not estimable", cell["rate"]
        elif p["kind"] == "rate_at_least":
            observed = cell["rate"]
            verdict = "held" if observed >= p["value"] else "refuted"
        elif p["kind"] == "rate_gain_at_least":
            observed = cell["rate"] - rate(stratum, p["over"])["rate"]
            verdict = "held" if observed >= p["value"] else "refuted"
        else:
            raise ValueError(f"unknown prediction kind: {p['kind']!r}")
        scored.append({"id": p["id"], "stratum": p["stratum"], "stratum_size": cell["n"],
                       "arm": p["arm"], "kind": p["kind"], "threshold": p["value"],
                       "observed": observed, "verdict": verdict})

    m_clean = len(strata["clean"]) / len(clean_all) if clean_all else 0.0
    m_indel = len(strata["indel"]) / len(indel_all) if indel_all else 0.0
    headline = plan["headline_arm"]
    a_clean = rate(strata["clean"], headline)["rate"] or 0.0
    a_indel = rate(strata["indel"], headline)["rate"] or 0.0
    by_prior = {}
    for q in plan["fault_priors_reported"]:
        w_clean, w_indel = (1 - q) * m_clean, q * m_indel
        total = w_clean + w_indel
        by_prior[str(q)] = (w_clean * a_clean + w_indel * a_indel) / total if total else 0.0

    verdicts = {p["id"]: p["verdict"] for p in scored}
    deciding = verdicts[plan["deciding_prediction"]]
    if deciding == "not estimable":
        next_step = "undecided: the deciding stratum is too small"
    elif deciding == "held":
        next_step = "preregister_complete_split_sweep"
    else:
        next_step = "no_split_sweep"
    return {
        "draws": {"clean": len(clean_all), "indel": len(indel_all)},
        "reference_arms": refs,
        "missed_by_every_reference_arm": {k: len(v) for k, v in strata.items()},
        "missed_fraction": {"clean": m_clean, "indel": m_indel},
        "detection_among_missed": table,
        "predictions": scored,
        "headline_arm": headline,
        "headline_rates_among_missed": {"clean": a_clean, "indel": a_indel},
        "conditional_detection_by_fault_prior": by_prior,
        "next_step_per_decision_rule": next_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default=str(ROOT / "artifacts/phase1-split-point-power-v2.json"))
    parser.add_argument("--config", default=str(ROOT / "experiments/phase1-split-point-power-v2/config.json"))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    artifact = json.loads(pathlib.Path(args.artifact).read_text(encoding="utf-8"))
    plan = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8"))["end_to_end_power"]["split_v2_analysis"]
    report = analyse(artifact["result"], plan)
    text = json.dumps(report, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
