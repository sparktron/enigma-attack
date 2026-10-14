#!/usr/bin/env python3
"""Conditional joint power of the v4 and v6 climbs: retention and companion confirmation.

Preregistered by ``experiments/phase1-estecker-joint-power-v1/config.json`` (its
``joint_analysis`` block).  It reads an ``end_to_end_power`` artifact that holds the
two arms ``complete_w117`` (v4's climb) and ``complete_w117_estecker`` (v6's), and
for every draw:

* plants two companion messages (107 and 97 letters, fresh Markov plaintexts of the
  published counts) under the draw's planted wheel order, rings and plugboard with a
  random start, seeded ``<companion seed>:<cell>:<draw>`` so both arms of one draw
  face the same companions and the result does not depend on worker order;
* runs ``stecker_companion.confirm_through_companions`` on each arm's top candidate
  (its wheel order, its rings, its plugboard), exactly as the sweep does;
* judges retention: the top candidate's score per letter is at least the lowest
  score among the 100 candidates the arm's real sweep retained on BYQMZ (v4's for
  ``complete_w117``, v6's for ``complete_w117_estecker``).

``sweep_success`` is retained and confirmed: the sweep's own decision rule, without
requiring the plugboard to be exact.  Detection (the harness's rule) is reported
alongside.  The predictions J1 to J6 are scored from the config.

    python3 scripts/joint_power_estecker_v1.py
    python3 scripts/joint_power_estecker_v1.py --power artifacts/phase1-estecker-power-v1.json \\
        --power-config experiments/phase1-estecker-power-v1/config.json \\
        --experiment-id phase1-estecker-joint-power-v1-same-draws \\
        --output artifacts/phase1-estecker-joint-power-v1-same-draws.json --secondary

``--secondary`` marks the run as post hoc and subject to selection (the gate's own
draws).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import multiprocessing as mp
import pathlib
import random
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "review"))

import enigma_fast  # noqa: E402
import phase1_stecker as stecker  # noqa: E402
import plaintext_power  # noqa: E402
from enigma import EnigmaI  # noqa: E402
from provenance import code_version, sha256_file  # noqa: E402
from stecker_companion import confirm_through_companions  # noqa: E402
from stecker_power import wilson_interval  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_traffic import Traffic  # noqa: E402

SCHEMA = "enigma-attack.phase1-joint-power-estecker/v1"
CONFIG = "experiments/phase1-estecker-joint-power-v1/config.json"
POWER = "artifacts/phase1-estecker-joint-power-v1.json"
SWEEPS = {
    "complete_w117": "artifacts/phase1-body-direct-sweep-v4.json",
    "complete_w117_estecker": "artifacts/phase1-body-direct-sweep-v6.json",
}
COMPANION_SEED = 20261116
COMPANION_LENGTHS = (107, 97)
THRESHOLD_Z = 6.0
_STATE: dict[str, Any] = {}


def init(config: dict) -> None:
    sweep_config = stecker.load_config(stecker.resolve_path("experiments/phase1-body-direct-sweep-v6/config.json"))
    _STATE.update(
        scorer=FastNgramScorer(sweep_config["scorer"]),
        reflector=enigma_fast.reflector_table(sweep_config["machine"]["reflector"]),
        tables=plaintext_power.ngram_tables(config),
    )


def companions_for(planted: dict[str, Any], generator: random.Random) -> list[Traffic]:
    machine = dict(
        rotors=tuple(planted["rotor_order_left_to_right"]), rings=planted["rings"], plugboard=planted["plugboard"]
    )
    out = []
    for index, length in enumerate(COMPANION_LENGTHS):
        text = plaintext_power.markov_text(generator, _STATE["tables"], length)
        start = "".join(chr(65 + generator.randrange(26)) for _ in range(3))
        body = EnigmaI(**machine, positions=start).crypt(text)
        out.append(Traffic(f"COMPANION-{index}", (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices(body)))
    return out


def one_draw(task: tuple[dict, dict, dict]) -> dict[str, Any]:
    draw, thresholds, cutoffs = task
    generator = random.Random(f"{COMPANION_SEED}:{draw['cell']}:{draw['draw']}")
    companions = companions_for(draw["planted"], generator)
    row: dict[str, Any] = {"cell": draw["cell"], "draw": draw["draw"], "arms": {}}
    if "plaintext" in draw:
        row["plaintext"] = draw["plaintext"]
    for arm, cutoff in cutoffs.items():
        top = draw["arms"][arm]["top"]
        outcome = confirm_through_companions(
            companions, draw["planted"]["rotor_order_left_to_right"],
            tuple(ord(c) - 65 for c in top["rings"]),
            enigma_fast.plugboard_table(top["plugboard"]),
            _STATE["scorer"], _STATE["reflector"], THRESHOLD_Z,
        )
        detected = bool(
            top["plugboard_recovered_exactly"]
            and top["score_per_letter"] >= thresholds[draw["cell"]][arm]
        )
        retained = top["score_per_letter"] >= cutoff
        row["arms"][arm] = {
            "score_per_letter": top["score_per_letter"],
            "plugboard_exact": top["plugboard_recovered_exactly"],
            "detected": detected,
            "retained": retained,
            "companion_best_z": [scan["best_z"] for scan in outcome["companions"]],
            "min_best_z": outcome["min_best_z"],
            "confirmed": bool(outcome["confirmed"]),
            "sweep_success": bool(retained and outcome["confirmed"]),
        }
    return row


def rate(rows: list[dict], arm: str, predicate) -> dict[str, Any]:
    hits = sum(1 for row in rows if predicate(row["arms"][arm]))
    n = len(rows)
    return {"count": hits, "of": n, "rate": round(hits / n, 6), "interval_95": wilson_interval(hits, n)}


def conditional(rows: list[dict], arm: str, given, event) -> dict[str, Any]:
    base = [row for row in rows if given(row["arms"][arm])]
    hits = sum(1 for row in base if event(row["arms"][arm]))
    return {"count": hits, "of": len(base), "rate": None if not base else round(hits / len(base), 6),
            "interval_95": wilson_interval(hits, len(base)) if base else None}


def score_predictions(spec: list[dict], cells: dict[str, dict]) -> list[dict]:
    out = []
    projection = None
    for prediction in spec:
        cell = cells[prediction["cell"]]
        arm = cell["arms"][prediction["arm"]]
        kind, value = prediction["kind"], prediction["value"]
        if kind == "sweep_success_at_least":
            observed = arm["sweep_success"]["rate"]
            passed = observed >= value
        elif kind == "sweep_success_within_of_projection":
            projection = 0.7305375 if prediction["cell"] == "clean" else 0.483
            observed = arm["sweep_success"]["rate"] - projection
            passed = abs(observed) <= value
        elif kind == "confirmed_given_detected_at_least":
            observed = arm["confirmed_given_detected"]["rate"]
            passed = observed is not None and observed >= value
        elif kind == "retained_given_detected_at_least":
            observed = arm["retained_given_detected"]["rate"]
            passed = observed is not None and observed >= value
        elif kind == "sweep_success_gain_at_least":
            observed = arm["sweep_success"]["rate"] - cell["arms"][prediction["over"]]["sweep_success"]["rate"]
            passed = observed >= value
        else:
            raise ValueError(f"unknown prediction kind: {kind!r}")
        out.append({"id": prediction["id"], "statement": prediction["statement"], "kind": kind,
                    "threshold": value, "observed": None if observed is None else round(observed, 6),
                    "passed": bool(passed)})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=CONFIG)
    parser.add_argument("--power", default=POWER)
    parser.add_argument("--power-config", default=CONFIG)
    parser.add_argument("--experiment-id", default="phase1-estecker-joint-power-v1")
    parser.add_argument("--output", default="artifacts/phase1-estecker-joint-power-v1-joint.json")
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--secondary", action="store_true", help="mark as post hoc (the gate run's own draws)")
    arguments = parser.parse_args(argv)

    config = json.loads(stecker.resolve_path(arguments.config).read_text(encoding="utf-8"))
    power = json.loads(stecker.resolve_path(arguments.power).read_text(encoding="utf-8"))
    cutoffs = {
        arm: min(r["score_per_letter"] for r in json.loads(stecker.resolve_path(path).read_text(encoding="utf-8"))["result"]["top_candidates"])
        for arm, path in SWEEPS.items()
    }
    thresholds = {
        index: {
            arm: (next(a for a in cell["arms"] if a["arm"] == arm).get("null") or cell["null"])["detection_threshold_score_per_letter"]
            for arm in cutoffs
        }
        for index, cell in enumerate(power["result"]["cells"])
    }
    started = dt.datetime.now(dt.timezone.utc)
    version = code_version()
    tasks = [(draw, thresholds, cutoffs) for draw in power["result"]["draws"]]
    with mp.Pool(arguments.jobs, initializer=init, initargs=(config,)) as pool:
        rows = pool.map(one_draw, tasks)

    names = ["clean" if c["perturbation"] == "none" else c["perturbation"] for c in power["result"]["cells"]]
    cells: dict[str, dict] = {}
    for index, name in enumerate(names):
        mine = [row for row in rows if row["cell"] == index]
        arms = {}
        for arm in cutoffs:
            arms[arm] = {
                "retention_cutoff_score_per_letter": cutoffs[arm],
                "detected": rate(mine, arm, lambda a: a["detected"]),
                "retained": rate(mine, arm, lambda a: a["retained"]),
                "confirmed": rate(mine, arm, lambda a: a["confirmed"]),
                "sweep_success": rate(mine, arm, lambda a: a["sweep_success"]),
                "detected_and_sweep_success": rate(mine, arm, lambda a: a["detected"] and a["sweep_success"]),
                "confirmed_given_detected": conditional(mine, arm, lambda a: a["detected"], lambda a: a["confirmed"]),
                "retained_given_detected": conditional(mine, arm, lambda a: a["detected"], lambda a: a["retained"]),
                "sweep_success_given_detected": conditional(mine, arm, lambda a: a["detected"], lambda a: a["sweep_success"]),
            }
        e, b = "complete_w117_estecker", "complete_w117"
        paired = {
            "both": sum(1 for r in mine if r["arms"][e]["sweep_success"] and r["arms"][b]["sweep_success"]),
            "estecker_only": sum(1 for r in mine if r["arms"][e]["sweep_success"] and not r["arms"][b]["sweep_success"]),
            "baseline_only": sum(1 for r in mine if not r["arms"][e]["sweep_success"] and r["arms"][b]["sweep_success"]),
            "neither": sum(1 for r in mine if not r["arms"][e]["sweep_success"] and not r["arms"][b]["sweep_success"]),
        }
        cells[name] = {"draws": len(mine), "arms": arms, "paired_sweep_success": paired}

    predictions = score_predictions(config["joint_analysis"]["predictions"], cells)
    payload = {
        "schema": SCHEMA,
        "experiment_id": arguments.experiment_id,
        "preregistered": not arguments.secondary,
        "secondary_post_hoc_same_draws_as_gate": bool(arguments.secondary),
        "started_at": started.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code": version,
        "inputs": {
            "power_artifact_sha256": sha256_file(stecker.resolve_path(arguments.power)),
            "config_sha256": sha256_file(stecker.resolve_path(arguments.config)),
            **{f"{arm}_sweep_sha256": sha256_file(stecker.resolve_path(path)) for arm, path in SWEEPS.items()},
        },
        "companion": {"seed": COMPANION_SEED, "lengths": list(COMPANION_LENGTHS), "threshold_z": THRESHOLD_Z},
        "result": {"cells": cells, "predictions": predictions, "draws": rows},
    }
    out = pathlib.Path(arguments.output)
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for name, cell in cells.items():
        for arm, a in cell["arms"].items():
            print(f"{name:6s} {arm:24s} detected {a['detected']['count']}/{a['detected']['of']} retained {a['retained']['count']} "
                  f"confirmed {a['confirmed']['count']} sweep_success {a['sweep_success']['count']} ({a['sweep_success']['rate']:.3f})")
    for p in predictions:
        print(p["id"], "held" if p["passed"] else "REFUTED", "observed", p["observed"], "threshold", p["threshold"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
