"""End-to-end power of the Phase 1 body-direct sweep against planted keys."""

from __future__ import annotations

import concurrent.futures as futures
import math
import random
import statistics
import time
from collections.abc import Mapping, Sequence
from typing import Any

from enigma import EnigmaI
import enigma_fast
from stecker_climb import body_direct_climb
from stecker_scoring import FastNgramScorer
from stecker_space import RING_RULES, RingRule, reducible_space_size, rule_key_coverage
from stecker_sweeps import body_direct_sweep
from stecker_traffic import Traffic, normalize_plaintext, random_plugboard


# ``calibrate_climb_capability`` hands the climb the true rings and start, a
# setting the sweep never visits: it holds rings, so what it reaches is an
# *equivalent* setting whose wheels step at different letters.  The controls
# below plant keys with random rings, sweep a slice that contains what the
# sweep can reach, and count how often the sweep's best candidate is the key.


_POWER: dict[str, Any] = {}


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> list[float]:
    if trials == 0:
        return [0.0, 1.0]
    rate = successes / trials
    denominator = 1 + z * z / trials
    centre = (rate + z * z / (2 * trials)) / denominator
    margin = (
        z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials)) / denominator
    )
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def perturb_ciphertext(
    ciphertext: str, kind: str, generator: random.Random
) -> tuple[str, dict[str, Any]]:
    """A transcription fault: none, or one letter dropped or inserted."""

    if kind == "none":
        return ciphertext, {"kind": "none"}
    if kind == "indel":
        position = generator.randrange(1, len(ciphertext) - 1)
        if generator.random() < 0.5:
            return (
                ciphertext[:position] + ciphertext[position + 1 :],
                {"kind": "deletion", "position": position},
            )
        letter = chr(65 + generator.randrange(26))
        return (
            ciphertext[:position] + letter + ciphertext[position:],
            {"kind": "insertion", "position": position, "letter": letter},
        )
    raise ValueError(f"unknown perturbation: {kind!r}")


def table_agreement(left: Sequence[int], right: Sequence[int], length: int) -> float:
    """Fraction of letter positions at which two flattened tables are the same."""

    return (
        sum(1 for t in range(length) if left[26 * t : 26 * t + 26] == right[26 * t : 26 * t + 26])
        / length
    )


def _power_init(config: Mapping[str, Any], scorer: FastNgramScorer | None = None) -> None:
    _POWER["config"] = config
    _POWER["scorer"] = scorer or FastNgramScorer(config["scorer"])
    _POWER["reflector"] = enigma_fast.reflector_table(config["machine"]["reflector"])


def _power_draw(task: tuple[int, int]) -> dict[str, Any]:
    cell_index, draw = task
    config = _POWER["config"]
    scorer = _POWER["scorer"]
    reflector = _POWER["reflector"]
    settings = config["end_to_end_power"]
    cell = settings["cells"][cell_index]
    wheels = list(config["machine"]["wheel_set"])
    # One generator per draw, seeded from its coordinates, so a draw's key and
    # its result do not depend on how the draws are spread over workers.
    generator = random.Random(f"{settings['seed']}:{cell_index}:{draw}")
    order = tuple(generator.sample(wheels, 3))
    rings = tuple(generator.randrange(26) for _ in range(3))
    start = tuple(generator.randrange(26) for _ in range(3))
    plugboard = random_plugboard(generator, int(settings["stecker_pairs"]))
    text = normalize_plaintext(settings["plaintext"])[: int(cell["length"])]
    clean = EnigmaI(
        rotors=order,
        rings="".join(chr(65 + value) for value in rings),
        positions="".join(chr(65 + value) for value in start),
        plugboard=plugboard,
    ).crypt(text)
    ciphertext, perturbation = perturb_ciphertext(clean, cell["perturbation"], generator)
    message = Traffic(
        designator=f"POWER-{cell_index}-{draw}",
        first_trigram=(0, 0, 0),
        second_trigram=(0, 0, 0),
        body=enigma_fast.text_to_indices(ciphertext),
    )
    expected_plugboard = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard))
    order_tables = [enigma_fast.rotor_tables(name) for name in order]
    true_table = enigma_fast.position_permutations(
        order_tables, rings, start, len(clean), reflector
    )
    offsets = tuple((start[index] - rings[index]) % 26 for index in range(3))
    unperturbed = perturbation["kind"] == "none"

    arms: dict[str, Any] = {}
    for arm in settings["arms"]:
        right_a = arm["right_ring"] == "A"
        right_rings = (0,) if right_a else (rings[2],)
        right_base = offsets[2] if right_a else start[2]
        starts = [
            (
                (offsets[0] + left) % 26,
                (offsets[1] + middle) % 26,
                (right_base + right) % 26,
            )
            for left in range(-int(settings["left_neighbours"]), int(settings["left_neighbours"]) + 1)
            for middle in range(
                -int(settings["middle_neighbours"]), int(settings["middle_neighbours"]) + 1
            )
            for right in range(
                -int(settings["right_neighbours"]), int(settings["right_neighbours"]) + 1
            )
        ]
        rule = RingRule(arm["ring_rule"], (0, 0, 0), right_rings, len(message.body))
        swept = len(rule.settings(order, starts))
        ranked, evaluated, _ = body_direct_sweep(
            message, [order], rule, starts, config["scorer"], reflector, config["climb"], swept, 1
        )
        fractions: list[float | None] = []
        for row in ranked:
            if not unperturbed:
                fractions.append(None)
                continue
            swept_table = enigma_fast.position_permutations(
                order_tables,
                tuple(ord(letter) - 65 for letter in row["rings"]),
                tuple(ord(letter) - 65 for letter in row["start_position"]),
                len(clean),
                reflector,
            )
            fractions.append(table_agreement(swept_table, true_table, len(clean)))
        top = ranked[0]
        best = max((value for value in fractions if value is not None), default=None)
        arms[arm["id"]] = {
            "settings_evaluated": evaluated,
            "best_equivalent_fraction": None if best is None else round(best, 6),
            "exact_equivalent_exists": None if best is None else best == 1.0,
            "top": {
                "score_per_letter": top["score_per_letter"],
                "rings": top["rings"],
                "start_position": top["start_position"],
                "plugboard": top["plugboard"],
                "equivalent_fraction": None if fractions[0] is None else round(fractions[0], 6),
                "plugboard_recovered_exactly": top["plugboard"] == expected_plugboard,
            },
            "rank_of_exact_plugboard": next(
                (row["rank"] for row in ranked if row["plugboard"] == expected_plugboard), None
            ),
        }

    # Wrong settings drawn the same way the existing capability calibration
    # draws them, so the climb's score on a key it cannot recover has a
    # reference distribution to be separated from.
    null_scores: list[float] = []
    for _ in range(int(settings["null_trials"])):
        wrong_order = tuple(generator.sample(wheels, 3))
        while wrong_order == order:
            wrong_order = tuple(generator.sample(wheels, 3))
        wrong_rings = tuple(generator.randrange(26) for _ in range(3))
        wrong_start = tuple(generator.randrange(26) for _ in range(3))
        null_scores.append(
            body_direct_climb(
                [message], wrong_order, wrong_rings, [wrong_start], scorer, reflector,
                config["climb"],
            )[0].score_per_letter
        )
    return {
        "cell": cell_index,
        "draw": draw,
        "planted": {
            "rotor_order_left_to_right": list(order),
            "rings": "".join(chr(65 + value) for value in rings),
            "start_position": "".join(chr(65 + value) for value in start),
            "plugboard": expected_plugboard,
            "perturbation": perturbation,
        },
        "arms": arms,
        "null_scores": [round(value, 9) for value in null_scores],
    }


def evaluate_power_prediction(
    prediction: Mapping[str, Any], cells: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Score one preregistered prediction against the measured detection rates."""

    def rate(cell_index: int, arm: str) -> float:
        row = next(row for row in cells[cell_index]["arms"] if row["arm"] == arm)
        return row["detection_rate"]

    kind = prediction["kind"]
    cell, arm = int(prediction["cell"]), prediction["arm"]
    if kind == "rate_at_least":
        observed = rate(cell, arm)
        passed = observed >= prediction["value"]
    elif kind == "rate_at_most":
        observed = rate(cell, arm)
        passed = observed <= prediction["value"]
    elif kind == "rate_gain_at_least":
        observed = rate(cell, arm) - rate(cell, prediction["over"])
        passed = observed >= prediction["value"]
    elif kind == "rate_ratio_at_most":
        denominator = rate(int(prediction["over_cell"]), arm)
        observed = rate(cell, arm) / denominator if denominator else None
        passed = observed is not None and observed <= prediction["value"]
    elif kind == "measured_exact_within_analytic":
        row = next(row for row in cells[cell]["arms"] if row["arm"] == arm)
        observed = abs(row["measured_exact_equivalent_rate"] - row["analytic_exact_key_coverage"])
        passed = observed <= prediction["value"]
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    return {
        "id": prediction["id"],
        "statement": prediction["statement"],
        "kind": kind,
        "threshold": prediction["value"],
        "observed": None if observed is None else round(observed, 6),
        "passed": bool(passed),
    }


def run_end_to_end_power(
    config: Mapping[str, Any],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    jobs: int,
) -> dict[str, Any]:
    settings = config["end_to_end_power"]
    cells = settings["cells"]
    draws = int(settings["draws"])
    z_detect = float(settings["detection_z"])
    tasks = [(index, draw) for index in range(len(cells)) for draw in range(draws)]
    started = time.monotonic()
    if jobs > 1:
        with futures.ProcessPoolExecutor(
            max_workers=jobs, initializer=_power_init, initargs=(dict(config),)
        ) as pool:
            # ``map`` preserves input order, so the record does not depend on
            # which worker finished first.
            results = list(pool.map(_power_draw, tasks))
    else:
        _power_init(config, scorer)
        results = [_power_draw(task) for task in tasks]
    elapsed = time.monotonic() - started

    wheel_set = tuple(config["machine"]["wheel_set"])
    summary: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        mine = [row for row in results if row["cell"] == index]
        pooled = [value for row in mine for value in row["null_scores"]]
        null_mean, null_sd = statistics.fmean(pooled), statistics.pstdev(pooled)
        threshold = null_mean + z_detect * null_sd
        arm_rows: list[dict[str, Any]] = []
        for arm in settings["arms"]:
            per = [row["arms"][arm["id"]] for row in mine]
            recovered = [item["top"]["plugboard_recovered_exactly"] for item in per]
            detected = [
                item["top"]["plugboard_recovered_exactly"]
                and item["top"]["score_per_letter"] >= threshold
                for item in per
            ]
            exact = [item["exact_equivalent_exists"] for item in per]
            measured = [value for value in exact if value is not None]
            if measured:
                split = {
                    "detected_when_an_exact_equivalent_exists": [
                        sum(1 for flag, hit in zip(exact, detected) if flag and hit),
                        sum(1 for flag in exact if flag),
                    ],
                    "detected_when_no_exact_equivalent_exists": [
                        sum(1 for flag, hit in zip(exact, detected) if flag is False and hit),
                        sum(1 for flag in exact if flag is False),
                    ],
                }
            else:
                split = {}
            analytic = (
                None
                if arm["right_ring"] == "A"
                else round(rule_key_coverage(arm["ring_rule"], int(cell["length"]), wheel_set), 6)
            )
            arm_rows.append(
                {
                    "arm": arm["id"],
                    "ring_rule": arm["ring_rule"],
                    "right_ring": arm["right_ring"],
                    "draws": len(per),
                    "settings_evaluated_per_draw": per[0]["settings_evaluated"],
                    "plugboard_recovered_by_top_candidate": sum(recovered),
                    "detected": sum(detected),
                    "detection_rate": round(sum(detected) / len(per), 6),
                    "detection_rate_95_interval": wilson_interval(sum(detected), len(per)),
                    "plugboard_recovered_rate": round(sum(recovered) / len(per), 6),
                    "measured_exact_equivalent_rate": (
                        round(sum(1 for value in measured if value) / len(measured), 6)
                        if measured
                        else None
                    ),
                    "analytic_exact_key_coverage": analytic,
                    "median_best_equivalent_fraction": (
                        round(
                            statistics.median(
                                item["best_equivalent_fraction"]
                                for item in per
                                if item["best_equivalent_fraction"] is not None
                            ),
                            6,
                        )
                        if measured
                        else None
                    ),
                    **split,
                    "median_top_score_z_over_null": round(
                        statistics.median(
                            (item["top"]["score_per_letter"] - null_mean) / null_sd for item in per
                        ),
                        3,
                    ),
                }
            )
        summary.append(
            {
                "length": int(cell["length"]),
                "perturbation": cell["perturbation"],
                "null": {
                    "samples": len(pooled),
                    "mean_score_per_letter": round(null_mean, 9),
                    "sd_score_per_letter": round(null_sd, 9),
                    "detection_threshold_score_per_letter": round(threshold, 9),
                },
                "arms": arm_rows,
            }
        )

    headline = settings["headline_arm"]
    target = next(
        row
        for row in summary
        if row["length"] >= int(settings["target_length"]) and row["perturbation"] == "none"
    )
    headline_row = next(row for row in target["arms"] if row["arm"] == headline)
    indel = next(
        (
            next(row for row in cell["arms"] if row["arm"] == headline)
            for cell in summary
            if cell["length"] >= int(settings["target_length"]) and cell["perturbation"] == "indel"
        ),
        None,
    )
    predictions = [
        evaluate_power_prediction(prediction, summary) for prediction in settings["predictions"]
    ]
    return {
        "formulation": "end_to_end_power",
        "seed": settings["seed"],
        "draws_per_cell": draws,
        "stecker_pairs": int(settings["stecker_pairs"]),
        "detection_z": z_detect,
        "jobs": jobs,
        "seconds": round(elapsed, 3),
        "slice": {
            "wheel_orders": "the planted order only",
            "left_neighbours": int(settings["left_neighbours"]),
            "middle_neighbours": int(settings["middle_neighbours"]),
            "right_neighbours": int(settings["right_neighbours"]),
            "definition": (
                "Each draw plants a random wheel order, ring setting, start "
                "position and plugboard, then runs the sweep engine over the "
                "left and middle offsets within the stated neighbourhood of the "
                "planted ones. The right wheel's ring and position are taken at "
                "the planted values (or, for the held-ring arm, at the "
                "planted right offset with ring A), because the right wheel is "
                "an exact axis that the full sweep enumerates and so always "
                "visits. Every other wheel order and every distant start is "
                "absent, so a detection here is a detection against the "
                "planted key's own neighbourhood and the pooled wrong-setting "
                "null, not against the full space."
            ),
            "detection_rule": (
                "A draw is detected when the best-scoring candidate's plugboard "
                "is the planted plugboard exactly and its score is at least "
                "null mean + detection_z null standard deviations. The null is "
                "the pooled climb score at wrong settings in the same cell; "
                "detection_z is chosen above the extreme value expected from "
                "2.7e7 normal draws."
            ),
        },
        "cells": summary,
        "coverage_by_rule": {
            rule: {
                "length": int(target["length"]),
                "exact_key_coverage": round(
                    rule_key_coverage(rule, int(target["length"]), wheel_set), 6
                ),
                "reducible_space_settings": reducible_space_size(
                    rule, int(target["length"]), wheel_set
                ),
            }
            for rule in RING_RULES
        },
        "findings": {
            "headline_arm": headline,
            "end_to_end_detection_rate_at_target_scale": headline_row["detection_rate"],
            "end_to_end_detection_interval_95": headline_row["detection_rate_95_interval"],
            "end_to_end_detection_lower_bound_95": headline_row["detection_rate_95_interval"][0],
            "single_indel_detection_rate_at_target_length": (
                None if indel is None else indel["detection_rate"]
            ),
            "stecker_stage_upper_bound_reference": (
                "artifacts/phase1-stecker-calibration-v1.json, "
                "climb_capability_calibration: the climb is handed the true "
                "rings and start, so it bounds the stecker stage and not the sweep."
            ),
        },
        "predictions": predictions,
        "draws": results,
    }
