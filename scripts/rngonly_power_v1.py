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
from stecker_power import wilson_interval  # noqa: E402

SCHEMA = "enigma-attack.phase1-rngonly-power-terciles/v1"
CONFIG = "experiments/phase1-rngonly-power-v1/config.json"
POWER = "artifacts/phase1-rngonly-power-v1.json"
OUTPUT = "artifacts/phase1-rngonly-power-v1-terciles.json"
ARMS = ("complete_w117", "complete_w117_estecker", "complete_w117_rngonly")
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


def rate(hits: int, n: int) -> dict[str, Any]:
    return {"count": hits, "of": n, "rate": round(hits / n, 6), "interval_95": wilson_interval(hits, n)}


def analyse(power: dict[str, Any]) -> dict[str, Any]:
    flags = detected_flags(power)
    plaintext_of = {(d["cell"], d["draw"]): d["plaintext"]["index"] for d in power["result"]["draws"]}
    tercile = tercile_of(power)
    cells: dict[str, Any] = {}
    for index, cell in enumerate(power["result"]["cells"]):
        name = "clean" if cell["perturbation"] == "none" else cell["perturbation"]
        groups = {"all": sorted(flags[index][ARMS[0]])}
        for part in TERCILES:
            groups[part] = [d for d in groups["all"] if tercile[plaintext_of[(index, d)]] == part]
        out: dict[str, Any] = {}
        for group, draws in groups.items():
            arms = {arm: rate(sum(flags[index][arm][d] for d in draws), len(draws)) for arm in ARMS}
            paired = {}
            for arm, over in (("complete_w117_rngonly", "complete_w117_estecker"),
                              ("complete_w117_rngonly", "complete_w117"),
                              ("complete_w117_estecker", "complete_w117")):
                a = sum(1 for d in draws if flags[index][arm][d] and not flags[index][over][d])
                b = sum(1 for d in draws if flags[index][over][d] and not flags[index][arm][d])
                paired[f"{arm}_vs_{over}"] = {
                    "only_first": a, "only_second": b,
                    "gain": round((a - b) / len(draws), 6), "mcnemar_p": round(mcnemar_p(a, b), 6),
                }
            out[group] = {"draws": len(draws), "arms": arms, "paired": paired}
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=CONFIG)
    parser.add_argument("--power", default=POWER)
    parser.add_argument("--output", default=OUTPUT)
    arguments = parser.parse_args(argv)
    config = json.loads((ROOT / arguments.config).read_text(encoding="utf-8"))
    power_path = ROOT / arguments.power
    power = json.loads(power_path.read_text(encoding="utf-8"))
    started = dt.datetime.now(dt.timezone.utc)
    cells = analyse(power)
    predictions = score(config["tercile_analysis"]["predictions"], cells)
    payload = {
        "schema": SCHEMA, "experiment_id": config["experiment_id"] + "-terciles", "preregistered": True,
        "started_at": started.isoformat(), "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code": code_version(),
        "inputs": {"power_artifact_sha256": sha256_file(power_path),
                   "config_sha256": sha256_file(ROOT / arguments.config)},
        "result": {"cells": cells, "predictions": predictions},
    }
    out = ROOT / arguments.output
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for name, groups in cells.items():
        for group, g in groups.items():
            r = {a: g["arms"][a]["rate"] for a in ARMS}
            pr = g["paired"]["complete_w117_rngonly_vs_complete_w117_estecker"]
            print(f"{name:6s} {group:5s} n={g['draws']:4d}  v4 {r['complete_w117']:.3f}  E {r['complete_w117_estecker']:.3f}  "
                  f"R-ngonly {r['complete_w117_rngonly']:.3f}   R vs E: {pr['only_first']}/{pr['only_second']} p={pr['mcnemar_p']:.4f}")
    for p in predictions:
        print(p["id"], "held" if p["passed"] else "REFUTED", "observed", p["observed"], "threshold", p["threshold"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
