#!/usr/bin/env python3
"""Detection by plaintext-IC tercile, with paired counts, for phase1-rngonly-power-v1.

Preregistered by ``experiments/phase1-rngonly-power-v1/config.json`` (its
``tercile_analysis`` block).  It reads that run's ``end_to_end_power`` artifact, which
holds three arms on the same draws: ``complete_w117`` (v4's climb),
``complete_w117_estecker`` (v6's) and ``complete_w117_rngonly`` (the candidate), and
for each cell and each tercile of plaintext index of coincidence reports:

* each arm's detection by the harness's rule, recomputed per draw from its top
  candidate and its own null threshold (planted plugboard recovered exactly and score
  at or above the null mean plus ``detection_z`` standard deviations);
* paired counts against the E arm and against v4's climb: draws only one arm detects,
  and the two-sided exact McNemar p on the discordant draws;
* the predictions D1, D3 and N1.

The terciles are the harness's: plaintexts ordered by (IC, index), cut in thirds.

    python3 scripts/rngonly_power_v1.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from provenance import code_version, sha256_file  # noqa: E402
from stecker_power import stratified_cluster_interval, wilson_interval  # noqa: E402

SCHEMA = "enigma-attack.phase1-rngonly-power-terciles/v1"
CONFIG = "experiments/phase1-rngonly-power-v1/config.json"
POWER = "artifacts/phase1-rngonly-power-v1.json"
OUTPUT = "artifacts/phase1-rngonly-power-v1-terciles.json"
ARMS = ("complete_w117", "complete_w117_estecker", "complete_w117_rngonly")
SMOKE_DRAWS = 6  # draws 0-5 of each cell were run, and their outcomes printed, before the preregistration commit
TERCILES = ("low", "mid", "high")


def mcnemar_p(only_a: int, only_b: int) -> float:
    """Two-sided exact p for the discordant counts (binomial, p = 1/2)."""

    n = only_a + only_b
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(only_a, only_b) + 1)) / 2**n)


def detected_flags(power: dict[str, Any]) -> dict[int, dict[str, dict[int, bool]]]:
    """``{cell: {arm: {draw: detected}}}`` by the harness's rule."""

    flags: dict[int, dict[str, dict[int, bool]]] = {}
    for index, cell in enumerate(power["result"]["cells"]):
        thresholds = {
            row["arm"]: (row.get("null") or cell["null"])["detection_threshold_score_per_letter"]
            for row in cell["arms"]
        }
        flags[index] = {arm: {} for arm in ARMS}
        for draw in power["result"]["draws"]:
            if draw["cell"] != index:
                continue
            for arm in ARMS:
                top = draw["arms"][arm]["top"]
                flags[index][arm][draw["draw"]] = bool(
                    top["plugboard_recovered_exactly"] and top["score_per_letter"] >= thresholds[arm]
                )
    return flags


def tercile_of(power: dict[str, Any]) -> dict[int, str]:
    """Plaintext index -> tercile name, ordered by (IC, index) and cut in thirds."""

    ic: dict[int, float] = {}
    for draw in power["result"]["draws"]:
        ic[draw["plaintext"]["index"]] = draw["plaintext"]["index_of_coincidence"]
    ordered = sorted(ic, key=lambda index: (ic[index], index))
    names: dict[int, str] = {}
    for part, name in enumerate(TERCILES):
        for index in ordered[part * len(ordered) // 3 : (part + 1) * len(ordered) // 3]:
            names[index] = name
    return names


def rate(hits: int, n: int, strata=None) -> dict[str, Any]:
    out = {"count": hits, "of": n, "rate": round(hits / n, 6),
           # Wilson over pooled draws treats every draw as an independent sample; the draws share
           # 24 plaintexts, so this understates the uncertainty about typical text.
           "interval_95": wilson_interval(hits, n)}
    if strata is not None:
        out["cluster_interval_95"] = stratified_cluster_interval(strata)
    return out


def analyse(power: dict[str, Any], first_draw: int = 0) -> dict[str, Any]:
    """Detection per cell and tercile over the draws numbered ``first_draw`` or more.

    Each rate and each paired gain also carries a plaintext-level bootstrap interval,
    resampling plaintexts within their IC terciles (the design fixes eight per tercile).
    """

    flags = detected_flags(power)
    plaintext_of = {(d["cell"], d["draw"]): d["plaintext"]["index"] for d in power["result"]["draws"]}
    tercile = tercile_of(power)
    cells: dict[str, Any] = {}
    for index, cell in enumerate(power["result"]["cells"]):
        name = "clean" if cell["perturbation"] == "none" else cell["perturbation"]
        every = [d for d in sorted(flags[index][ARMS[0]]) if d >= first_draw]
        groups = {"all": every}
        for part in TERCILES:
            groups[part] = [d for d in every if tercile[plaintext_of[(index, d)]] == part]

        def strata(draws, value):
            """Per tercile, per plaintext: (sum of ``value`` over its draws, number of draws)."""
            by: dict[str, dict[int, list[int]]] = {}
            for d in draws:
                entry = by.setdefault(tercile[plaintext_of[(index, d)]], {}).setdefault(plaintext_of[(index, d)], [0, 0])
                entry[0] += value(d)
                entry[1] += 1
            return [[(a, b) for _, (a, b) in sorted(group.items())] for _, group in sorted(by.items())]

        out: dict[str, Any] = {}
        for group, draws in groups.items():
            arms = {arm: rate(sum(flags[index][arm][d] for d in draws), len(draws),
                              strata(draws, lambda d, arm=arm: int(flags[index][arm][d]))) for arm in ARMS}
            paired = {}
            for arm, over in (("complete_w117_rngonly", "complete_w117_estecker"),
                              ("complete_w117_rngonly", "complete_w117"),
                              ("complete_w117_estecker", "complete_w117")):
                a = sum(1 for d in draws if flags[index][arm][d] and not flags[index][over][d])
                b = sum(1 for d in draws if flags[index][over][d] and not flags[index][arm][d])
                paired[f"{arm}_vs_{over}"] = {
                    "only_first": a, "only_second": b,
                    "gain": round((a - b) / len(draws), 6), "mcnemar_p": round(mcnemar_p(a, b), 6),
                    "cluster_interval_95": stratified_cluster_interval(
                        strata(draws, lambda d, arm=arm, over=over: int(flags[index][arm][d]) - int(flags[index][over][d]))),
                }
            out[group] = {"draws": len(draws), "plaintexts": len({plaintext_of[(index, d)] for d in draws}),
                          "arms": arms, "paired": paired}
        cells[name] = out
    return cells


def score(predictions: list[dict[str, Any]], cells: dict[str, Any]) -> list[dict[str, Any]]:
    scored = []
    for p in predictions:
        group = cells[p["cell"]][p["tercile"]]
        if p["kind"] == "tercile_gain_at_least":
            observed = group["paired"][f"{p['arm']}_vs_{p['over']}"]["gain"]
        elif p["kind"] == "tercile_rate_at_least":
            observed = group["arms"][p["arm"]]["rate"]
        else:
            raise ValueError(f"unknown prediction kind: {p['kind']!r}")
        scored.append({"id": p["id"], "statement": p["statement"], "kind": p["kind"], "threshold": p["value"],
                       "observed": observed, "passed": bool(observed >= p["value"])})
    return scored


def score_overall(predictions: list[dict[str, Any]], cells: dict[str, Any], names: list[str]) -> list[dict[str, Any]]:
    """The harness's own overall predictions (S1, D2, D4, N2), recomputed over the same draws as the terciles."""

    scored = []
    for p in predictions:
        group = cells[names[int(p["cell"])]]["all"]
        if p["kind"] == "rate_at_least":
            observed = group["arms"][p["arm"]]["rate"]
            passed = observed >= p["value"]
        elif p["kind"] == "rate_gain_at_least":
            observed = group["arms"][p["arm"]]["rate"] - group["arms"][p["over"]]["rate"]
            passed = observed >= p["value"]
        else:
            raise ValueError(f"unknown prediction kind: {p['kind']!r}")
        scored.append({"id": p["id"], "statement": p["statement"], "kind": p["kind"], "threshold": p["value"],
                       "observed": round(observed, 6), "passed": bool(passed)})
    return scored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=CONFIG)
    parser.add_argument("--power", default=POWER)
    parser.add_argument("--output", default=OUTPUT)
    parser.add_argument("--exclude-first-draws", type=int, default=SMOKE_DRAWS,
                        help="leave draws 0..N-1 of each cell out of the primary result (the smoke run saw them)")
    arguments = parser.parse_args(argv)
    config = json.loads((ROOT / arguments.config).read_text(encoding="utf-8"))
    power_path = ROOT / arguments.power
    power = json.loads(power_path.read_text(encoding="utf-8"))
    started = dt.datetime.now(dt.timezone.utc)
    names = ["clean" if c["perturbation"] == "none" else c["perturbation"] for c in power["result"]["cells"]]
    # The primary result leaves out draws 0 to N-1 of each cell: the smoke run before the
    # preregistration commit computed them and printed their outcomes (config
    # pre_run_facts.smoke_run).  result.all_draws keeps every draw, labelled.
    cells = analyse(power, arguments.exclude_first_draws)
    everything = analyse(power, 0)
    spec, overall = config["tercile_analysis"]["predictions"], config["end_to_end_power"]["predictions"]
    predictions = score(spec, cells) + score_overall(overall, cells, names)
    predictions_all = score(spec, everything) + score_overall(overall, everything, names)
    payload = {
        "schema": SCHEMA, "experiment_id": config["experiment_id"] + "-terciles", "preregistered": True,
        "pre_observed_draws": {
            "excluded_from_primary_per_cell": arguments.exclude_first_draws,
            "reason": "draws 0 to 5 of each cell were run in a smoke test before the preregistration commit and their outcomes printed (config pre_run_facts.smoke_run); the primary result leaves them out and result.all_draws keeps them",
        },
        "started_at": started.isoformat(), "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code": code_version(),
        "inputs": {"power_artifact_sha256": sha256_file(power_path),
                   "config_sha256": sha256_file(ROOT / arguments.config)},
        "result": {"cells": cells, "predictions": predictions,
                   "all_draws": {"cells": everything, "predictions": predictions_all}},
    }
    out = ROOT / arguments.output
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for label, group, scored in (("primary (pre-observed draws excluded)", cells, predictions),
                                 ("all draws (includes the smoke-run draws)", everything, predictions_all)):
        print(f"== {label}")
        for name, groups in group.items():
            for g_name, g in groups.items():
                r = {a: g["arms"][a]["rate"] for a in ARMS}
                pr = g["paired"]["complete_w117_rngonly_vs_complete_w117_estecker"]
                print(f"{name:6s} {g_name:5s} n={g['draws']:4d}  v4 {r['complete_w117']:.3f}  E {r['complete_w117_estecker']:.3f}  "
                      f"R-ngonly {r['complete_w117_rngonly']:.3f}   R vs E: {pr['only_first']}/{pr['only_second']} gain {pr['gain']:+.3f} "
                      f"cluster {pr['cluster_interval_95']} p={pr['mcnemar_p']:.4f}")
        for p in scored:
            print(p["id"], "held" if p["passed"] else "REFUTED", "observed", p["observed"], "threshold", p["threshold"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
