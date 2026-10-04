#!/usr/bin/env python3
"""Measure sweep detection and companion confirmation jointly, on the same draws.

``phase1-body-direct-sweep-v2`` stated its power as the end-to-end detection
rate times the companion check's exact-plugboard rate.  Those come from
separate experiments, and both depend on the planted ring geometry, so the
product assumes an independence nobody measured.  This script measures the
conjunction directly.

For every draw of ``artifacts/phase1-end-to-end-power-v1.json`` it takes the
planted daily key and the candidate the middle-past-notch sweep actually ranked
first, enciphers two companion messages under the planted key with
``enigma.EnigmaI``, and runs the companion check on that candidate exactly as the
v2 runner would.  A draw counts as jointly detected when the top candidate is
companion-confirmed and, separately, when it also scores above the lowest score
v2 retained on BYQMZ, the cutoff a true key had to beat to be checked at all.

Exploratory and post hoc: written after v2 ran, in answer to review, and
preregistered nowhere.  It costs about a minute.

    python3 scripts/joint_power.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import random
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import enigma_fast  # noqa: E402
import phase1_stecker as stecker  # noqa: E402
from enigma import EnigmaI  # noqa: E402
from provenance import code_version, sha256_file  # noqa: E402
from stecker_companion import confirm_through_companions  # noqa: E402
from stecker_power import wilson_interval  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_traffic import Traffic, normalize_plaintext  # noqa: E402

SCHEMA = "enigma-attack.phase1-joint-power/v1"
POWER = "artifacts/phase1-end-to-end-power-v1.json"
POWER_CONFIG = "experiments/phase1-end-to-end-power-v1/config.json"
SWEEP = "artifacts/phase1-body-direct-sweep-v2.json"
SWEEP_CONFIG = "experiments/phase1-body-direct-sweep-v2/config.json"
DEFAULT_OUTPUT = "artifacts/phase1-joint-power-v1.json"
SEED = 20261004
COMPANION_LENGTHS = (107, 97)
ARM = "middle_past_notch"


def companions_for(planted: dict[str, Any], source: str, generator: random.Random) -> list[Traffic]:
    rotors = tuple(planted["rotor_order_left_to_right"])
    machine = dict(rotors=rotors, rings=planted["rings"], plugboard=planted["plugboard"])
    messages = []
    for index, length in enumerate(COMPANION_LENGTHS):
        offset = generator.randrange(len(source) - length + 1)
        key = "".join(chr(65 + generator.randrange(26)) for _ in range(3))
        body = EnigmaI(**machine, positions=key).crypt(source[offset : offset + length])
        messages.append(Traffic(f"COMPANION-{index}", (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices(body)))
    return messages


def run() -> dict[str, Any]:
    power = json.loads(stecker.resolve_path(POWER).read_text(encoding="utf-8"))
    power_config = stecker.load_config(stecker.resolve_path(POWER_CONFIG))
    sweep = json.loads(stecker.resolve_path(SWEEP).read_text(encoding="utf-8"))
    sweep_config = stecker.load_config(stecker.resolve_path(SWEEP_CONFIG))
    threshold = float(sweep_config["body_direct_sweep"]["companion_confirmation"]["threshold_z"])
    cutoff = min(row["score_per_letter"] for row in sweep["result"]["top_candidates"])
    scorer = FastNgramScorer(sweep_config["scorer"])
    reflector = enigma_fast.reflector_table(sweep_config["machine"]["reflector"])
    source = normalize_plaintext(power_config["end_to_end_power"]["plaintext"])
    detection_threshold = {
        index: cell["null"]["detection_threshold_score_per_letter"]
        for index, cell in enumerate(power["result"]["cells"])
    }
    generator = random.Random(SEED)

    rows: list[dict[str, Any]] = []
    for draw in power["result"]["draws"]:
        top = draw["arms"][ARM]["top"]
        outcome = confirm_through_companions(
            companions_for(draw["planted"], source, generator),
            draw["planted"]["rotor_order_left_to_right"],
            tuple(ord(letter) - 65 for letter in top["rings"]),
            enigma_fast.plugboard_table(top["plugboard"]),
            scorer, reflector, threshold,
        )
        power_detected = (
            top["plugboard_recovered_exactly"]
            and top["score_per_letter"] >= detection_threshold[draw["cell"]]
        )
        rows.append(
            {
                "cell": draw["cell"],
                "draw": draw["draw"],
                "top_score_per_letter": top["score_per_letter"],
                "top_plugboard_exact": top["plugboard_recovered_exactly"],
                "power_detected": power_detected,
                "companion_best_z": [scan["best_z"] for scan in outcome["companions"]],
                "min_best_z": outcome["min_best_z"],
                "companion_confirmed": outcome["confirmed"],
                "above_v2_retention_cutoff": top["score_per_letter"] >= cutoff,
            }
        )

    cells = []
    for index, cell in enumerate(power["result"]["cells"]):
        draws = [row for row in rows if row["cell"] == index]
        n = len(draws)

        def rate(predicate):
            hits = sum(1 for row in draws if predicate(row))
            return {"count": hits, "rate": round(hits / n, 6), "interval_95": wilson_interval(hits, n)}

        cells.append(
            {
                "length": cell["length"],
                "perturbation": cell["perturbation"],
                "draws": n,
                "power_detected": rate(lambda row: row["power_detected"]),
                "companion_confirmed": rate(lambda row: row["companion_confirmed"]),
                "power_detected_and_confirmed": rate(
                    lambda row: row["power_detected"] and row["companion_confirmed"]
                ),
                "confirmed_and_above_v2_retention_cutoff": rate(
                    lambda row: row["companion_confirmed"] and row["above_v2_retention_cutoff"]
                ),
                "confirmed_given_power_detected": (
                    None
                    if not any(row["power_detected"] for row in draws)
                    else round(
                        sum(1 for row in draws if row["power_detected"] and row["companion_confirmed"])
                        / sum(1 for row in draws if row["power_detected"]),
                        6,
                    )
                ),
            }
        )
    return {
        "arm": ARM,
        "threshold_z": threshold,
        "v2_retention_cutoff_score_per_letter": cutoff,
        "companion_lengths": list(COMPANION_LENGTHS),
        "seed": SEED,
        "cells": cells,
        "draws": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    version = code_version()
    started_at = dt.datetime.now(dt.timezone.utc)
    result = run()
    payload = {
        "schema": SCHEMA,
        "experiment_id": "phase1-joint-power-v1",
        "preregistered": False,
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code": version,
        "inputs": {
            name: sha256_file(stecker.resolve_path(path))
            for name, path in (
                ("power_artifact_sha256", POWER), ("power_config_sha256", POWER_CONFIG),
                ("sweep_artifact_sha256", SWEEP), ("sweep_config_sha256", SWEEP_CONFIG),
            )
        },
        "result": result,
    }
    output = pathlib.Path(arguments.output)
    if not output.is_absolute():
        output = ROOT / output
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for cell in result["cells"]:
        print(
            f"{cell['length']} {cell['perturbation']}: power {cell['power_detected']['count']}/{cell['draws']}, "
            f"confirmed {cell['companion_confirmed']['count']}, "
            f"both {cell['power_detected_and_confirmed']['count']}, "
            f"confirmed+above cutoff {cell['confirmed_and_above_v2_retention_cutoff']['count']}, "
            f"P(confirm|detected) {cell['confirmed_given_power_detected']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
