#!/usr/bin/env python3
"""How often does R-ngonly find a planted key that E-Stecker (v6) missed?

Post hoc analysis of ``artifacts/phase1-rngonly-power-v1.json``, run before
phase1-body-direct-sweep-v7 was preregistered and recorded in its configuration as a
pre-run fact.  v7 follows a null v6, so the relevant power is conditional: among keys the
E arm misses, the share the R-ngonly arm detects (detection only: confirmation and
retention are not measured for the R-ngonly arm).  Draws 0-5 of each cell were seen in a
smoke run, so the primary set leaves them out, as scripts/rngonly_power_v1.py does.  The
bootstrap resamples plaintexts within their IC terciles.

    python3 scripts/v7_marginal_power.py --output data/review/v7-prereg-2026-10-16/marginal.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import rngonly_power_v1 as rp  # noqa: E402
from stecker_power import stratified_cluster_interval  # noqa: E402

E, R = "complete_w117_estecker", "complete_w117_rngonly"


def analyse(power: dict, first_draw: int = 6) -> dict:
    flags = rp.detected_flags(power)
    plaintext = {(d["cell"], d["draw"]): d["plaintext"]["index"] for d in power["result"]["draws"]}
    tercile = rp.tercile_of(power)
    out = {}
    for index, cell in enumerate(power["result"]["cells"]):
        name = "clean" if cell["perturbation"] == "none" else cell["perturbation"]
        draws = [d for d in sorted(flags[index][E]) if d >= first_draw]
        groups = {"all": draws, **{t: [d for d in draws if tercile[plaintext[(index, d)]] == t] for t in rp.TERCILES}}
        out[name] = {}
        for group, ds in groups.items():
            def strata(value, denominator):
                by: dict[str, dict[int, list[int]]] = {}
                for d in ds:
                    cl = by.setdefault(tercile[plaintext[(index, d)]], {}).setdefault(plaintext[(index, d)], [0, 0])
                    cl[0] += value(d)
                    cl[1] += denominator(d)
                return [[(a, b) for _, (a, b) in sorted(g.items())] for _, g in sorted(by.items())]
            r_only = sum(1 for d in ds if flags[index][R][d] and not flags[index][E][d])
            e_miss = sum(1 for d in ds if not flags[index][E][d])
            e_only = sum(1 for d in ds if flags[index][E][d] and not flags[index][R][d])
            either = sum(1 for d in ds if flags[index][E][d] or flags[index][R][d])
            out[name][group] = {
                "draws": len(ds), "e_misses": e_miss, "r_only": r_only, "e_only": e_only,
                "r_only_per_draw": {
                    "rate": round(r_only / len(ds), 6),
                    "cluster_interval_95": stratified_cluster_interval(strata(lambda d: int(flags[index][R][d] and not flags[index][E][d]), lambda d: 1)),
                },
                "r_detects_given_e_misses": {
                    "count": r_only, "of": e_miss, "rate": None if not e_miss else round(r_only / e_miss, 6),
                    "cluster_interval_95": stratified_cluster_interval(strata(lambda d: int(flags[index][R][d] and not flags[index][E][d]), lambda d: int(not flags[index][E][d]))),
                },
                "union_detection": round(either / len(ds), 6),
            }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--power", default="artifacts/phase1-rngonly-power-v1.json")
    parser.add_argument("--output", default=None)
    arguments = parser.parse_args()
    power = json.loads((ROOT / arguments.power).read_text(encoding="utf-8"))
    result = analyse(power)
    for cell, groups in result.items():
        for group, g in groups.items():
            c = g["r_detects_given_e_misses"]
            print(f"{cell:5s} {group:5s} n={g['draws']:3d}  E misses {g['e_misses']:3d}  R-only {g['r_only']:3d} ({g['r_only_per_draw']['rate']*100:4.1f}% of draws, "
                  f"{g['r_only_per_draw']['cluster_interval_95']})  R finds {c['rate']*100:5.1f}% of E's misses {c['cluster_interval_95']}  E-only {g['e_only']}  union {g['union_detection']*100:.1f}%")
    if arguments.output:
        out = ROOT / arguments.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"power_artifact": arguments.power, "first_draw": 6, "result": result}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
