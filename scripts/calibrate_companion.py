#!/usr/bin/env python3
"""Calibrate the companion-body confirmation against planted keys and real nulls.

Runs ``experiments/phase1-companion-calibration-v1/config.json`` and writes its
artifact.  Each draw plants a random daily key, enciphers a swept message and
its companions with ``enigma.EnigmaI``, and scores the candidate a complete
middle-past-notch sweep would return, with the exact plugboard and with some of
its pairs wrong.  Two null populations show where wrong candidates land: random
wheel orders, rings and plugboards against the planted companions, and the 40
candidates the v1 slice retained on BYQMZ against the real FKQLZ and XFEDT.

    python3 scripts/calibrate_companion.py

It takes about a minute, so the artifact check regenerates it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import random
import statistics
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import enigma_fast  # noqa: E402
import phase1_stecker as stecker  # noqa: E402
from enigma import A, EnigmaI  # noqa: E402
from provenance import code_version, sha256_file  # noqa: E402
from stecker_companion import confirm_through_companions  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_space import middle_start_phases  # noqa: E402
from stecker_traffic import Traffic, normalize_plaintext, random_plugboard, traffic_from_corpus  # noqa: E402

CONFIG_SCHEMA = "enigma-attack.phase1-companion-calibration-config/v1"
RESULT_SCHEMA = "enigma-attack.phase1-companion-calibration-result/v1"
DEFAULT_CONFIG = "experiments/phase1-companion-calibration-v1/config.json"


def text(values: Any) -> str:
    return "".join(chr(65 + value) for value in values)


def letters(value: str) -> tuple[int, ...]:
    return tuple(ord(letter) - 65 for letter in value)


def wrong_pairs(plugboard: str, wrong: int, generator: random.Random) -> str:
    """Re-pair the letters of ``wrong`` true pairs among themselves.

    The pair count is kept, so the only difference from the true plugboard is
    which letters are joined, the way a climb that converged on a near miss
    differs.  Two pairs AB, CD become AC, BD or AD, BC.
    """

    pairs = plugboard.split()
    if wrong == 0:
        return plugboard
    chosen = generator.sample(range(len(pairs)), wrong)
    loose = [letter for index in chosen for letter in pairs[index]]
    while True:
        generator.shuffle(loose)
        new = [loose[i] + loose[i + 1] for i in range(0, len(loose), 2)]
        if not {"".join(sorted(pair)) for pair in new} & {"".join(sorted(pairs[i])) for i in chosen}:
            break
    kept = [pair for index, pair in enumerate(pairs) if index not in chosen]
    return " ".join(kept + new)


def plant_draw(generator: random.Random, settings: dict[str, Any], wheel_set: list[str]):
    rotors = tuple(generator.sample(wheel_set, 3))
    rings = [generator.randrange(26) for _ in range(3)]
    plugboard = random_plugboard(generator, int(settings["stecker_pairs"]))
    source = normalize_plaintext(settings["plaintext"])
    lengths = [int(settings["swept_length"]), *(int(n) for n in settings["companion_lengths"])]
    offset = generator.randrange(len(source) - sum(lengths) + 1)
    messages: list[Traffic] = []
    keys: list[tuple[int, ...]] = []
    for index, length in enumerate(lengths):
        plaintext = source[offset : offset + length]
        offset += length
        grundstellung = text(generator.randrange(26) for _ in range(3))
        message_key = text(generator.randrange(26) for _ in range(3))
        machine = dict(rotors=rotors, rings=text(rings), plugboard=plugboard)
        indicator = EnigmaI(**machine, positions=grundstellung).crypt(message_key)
        body = EnigmaI(**machine, positions=message_key).crypt(plaintext)
        messages.append(
            Traffic(
                f"PLANT-{index}",
                enigma_fast.text_to_indices(grundstellung),
                enigma_fast.text_to_indices(indicator),
                enigma_fast.text_to_indices(body),
            )
        )
        keys.append(letters(message_key))
    # The rings a complete middle-past-notch sweep reports for this key: left
    # held at A, right as planted, middle chosen so the swept message's middle
    # wheel starts just past its notch with the true middle offset.
    phase = middle_start_phases(
        enigma_fast.rotor_tables(rotors[1]).notches, lengths[0], complete=False
    )[0]
    offset_middle = (keys[0][1] - rings[1]) % 26
    presented = (0, (phase - offset_middle) % 26, rings[2])
    return rotors, rings, plugboard, messages, presented


def run(config: dict[str, Any]) -> dict[str, Any]:
    settings = config["calibration"]
    wheel_set = list(config["machine"]["wheel_set"])
    scorer = FastNgramScorer(config["scorer"])
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])
    threshold = float(settings["threshold_z"])
    generator = random.Random(int(settings["seed"]))

    arms: dict[int, list[dict[str, Any]]] = {k: [] for k in settings["wrong_pair_arms"]}
    random_null: list[dict[str, Any]] = []
    planted: list[list[Traffic]] = []
    for draw in range(int(settings["draws"])):
        rotors, rings, plugboard, messages, presented = plant_draw(generator, settings, wheel_set)
        companions = messages[1:]
        planted.append(companions)
        for wrong in settings["wrong_pair_arms"]:
            board = wrong_pairs(plugboard, int(wrong), generator)
            outcome = confirm_through_companions(
                companions, rotors, presented, enigma_fast.plugboard_table(board),
                scorer, reflector, threshold,
            )
            arms[wrong].append(
                {
                    "draw": draw,
                    "rotor_order_left_to_right": list(rotors),
                    "planted_rings": text(rings),
                    "presented_rings": text(presented),
                    "wrong_pairs": int(wrong),
                    "companion_best_z": [row["best_z"] for row in outcome["companions"]],
                    "min_best_z": outcome["min_best_z"],
                    "confirmed": outcome["confirmed"],
                }
            )
    for trial in range(int(settings["random_null_candidates"])):
        companions = planted[trial % len(planted)]
        outcome = confirm_through_companions(
            companions,
            tuple(generator.sample(wheel_set, 3)),
            tuple(generator.randrange(26) for _ in range(3)),
            enigma_fast.plugboard_table(random_plugboard(generator, int(settings["stecker_pairs"]))),
            scorer, reflector, threshold,
        )
        random_null.append(
            {"companion_best_z": [row["best_z"] for row in outcome["companions"]],
             "min_best_z": outcome["min_best_z"], "confirmed": outcome["confirmed"]}
        )

    corpus = settings["corpus_null"]
    source_path = stecker.resolve_path(corpus["source_artifact"])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    real = traffic_from_corpus(stecker.resolve_path(config["corpus"]), corpus["date"], corpus["companions"])
    corpus_null: list[dict[str, Any]] = []
    for candidate in source["result"]["top_candidates"]:
        outcome = confirm_through_companions(
            real, candidate["rotor_order_left_to_right"], letters(candidate["rings"]),
            enigma_fast.plugboard_table(candidate["plugboard"]), scorer, reflector, threshold,
        )
        corpus_null.append(
            {"rank": candidate["rank"], "companions": outcome["companions"],
             "min_best_z": outcome["min_best_z"], "confirmed": outcome["confirmed"]}
        )

    def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        values = [row["min_best_z"] for row in rows]
        return {
            "trials": len(rows),
            "min_best_z_median": round(statistics.median(values), 6),
            "min_best_z_min": round(min(values), 6),
            "min_best_z_max": round(max(values), 6),
            "confirmed": sum(1 for row in rows if row["confirmed"]),
            "confirmed_rate": round(sum(1 for row in rows if row["confirmed"]) / len(rows), 6),
        }

    arm_summaries = [{"wrong_pairs": int(k), **summary(rows)} for k, rows in arms.items()]
    nulls = {"random": random_null, "corpus": corpus_null}
    scored: list[dict[str, Any]] = []
    for prediction in config["predictions"]:
        if prediction["kind"] == "rate_at_least":
            rows = arms[prediction["arm"]]
            rate = sum(1 for row in rows if row["min_best_z"] >= prediction["z"]) / len(rows)
            held = rate >= prediction["value"]
        elif prediction["kind"] == "null_rate_at_most":
            rows = nulls[prediction["null"]]
            rate = sum(1 for row in rows if row["min_best_z"] >= prediction["z"]) / len(rows)
            held = rate <= prediction["value"]
        else:
            raise ValueError(f"unknown prediction kind: {prediction['kind']!r}")
        scored.append({**prediction, "observed": round(rate, 6), "held": held})
    return {
        "threshold_z": threshold,
        "arms": arm_summaries,
        "random_null": summary(random_null),
        "corpus_null": {**summary(corpus_null), "source_artifact_sha256": sha256_file(source_path)},
        "predictions": scored,
        "all_predictions_held": all(row["held"] for row in scored),
        "draws": {str(k): rows for k, rows in arms.items()},
        "corpus_null_candidates": corpus_null,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output", default=None)
    arguments = parser.parse_args(argv)

    version = code_version()
    started_at = dt.datetime.now(dt.timezone.utc)
    config_path = stecker.resolve_config(arguments.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"unsupported configuration schema: {config.get('schema')!r}")
    result = run(config)
    payload = {
        "schema": RESULT_SCHEMA,
        "experiment_id": config["experiment_id"],
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "configuration": {"path": stecker.describe_path(config_path), "sha256": sha256_file(config_path)},
        "code": version,
        "inputs": {"corpus_sha256": sha256_file(stecker.resolve_path(config["corpus"]))},
        "result": result,
        "limitations": config["limitations"],
    }
    output = pathlib.Path(arguments.output or config["output"])
    if not output.is_absolute():
        output = ROOT / output
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for arm in result["arms"]:
        print(f"wrong pairs {arm['wrong_pairs']}: median min z {arm['min_best_z_median']}, "
              f"min {arm['min_best_z_min']}, confirmed {arm['confirmed']}/{arm['trials']}")
    for name in ("random_null", "corpus_null"):
        row = result[name]
        print(f"{name}: max min z {row['min_best_z_max']}, confirmed {row['confirmed']}/{row['trials']}")
    for row in result["predictions"]:
        print(f"{'HELD ' if row['held'] else 'FAILED'} {row['id']}: observed {row['observed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
