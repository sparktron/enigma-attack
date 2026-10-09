"""End-to-end power of the Phase 1 body-direct sweep against planted keys."""

from __future__ import annotations

import concurrent.futures as futures
import multiprocessing
import math
import random
import statistics
import time
from collections.abc import Mapping, Sequence
from typing import Any

from enigma import EnigmaI
import enigma_fast
import stecker_batch
import stecker_split
from stecker_climb import body_direct_climb, climb_windows, windowed_climb
from stecker_scoring import FastNgramScorer
from stecker_space import RING_RULES, RingRule, reducible_space_size, rule_key_coverage
from stecker_sweeps import body_direct_sweep, resolve_engine
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


def repair_fault(ciphertext: str, perturbation: Mapping[str, Any]) -> str:
    """The faulty message with its fault undone at the true position.

    An oracle: no search can know where the fault is. A dropped letter gets an
    uncertainty mask (``?``) back at its position and an inserted letter is
    removed, so the result has the unperturbed length and every letter after
    the fault is aligned with the swept setting again. It bounds what a climb
    that searched the fault's position could achieve, from above.
    """

    position = perturbation.get("position")
    if perturbation["kind"] == "deletion":
        return ciphertext[:position] + "?" + ciphertext[position:]
    if perturbation["kind"] == "insertion":
        return ciphertext[:position] + ciphertext[position + 1 :]
    return ciphertext


def arm_message(message: Traffic, ciphertext: str, perturbation: Mapping[str, Any], arm: Mapping[str, Any]) -> Traffic:
    """The message an arm sweeps: as received, or with the fault undone if the arm says so.

    An arm without ``repair`` gets ``message`` itself, so a configuration
    written before repairs existed runs exactly as it did.
    """

    kind = arm.get("repair")
    if kind is None:
        return message
    if kind != "oracle":
        raise ValueError(f"unknown repair: {kind!r}")
    return Traffic(
        designator=message.designator,
        first_trigram=message.first_trigram,
        second_trigram=message.second_trigram,
        body=enigma_fast.text_to_indices(repair_fault(ciphertext, perturbation)),
    )


def table_agreement(left: Sequence[int], right: Sequence[int], length: int) -> float:
    """Fraction of letter positions at which two flattened tables are the same."""

    return (
        sum(1 for t in range(length) if left[26 * t : 26 * t + 26] == right[26 * t : 26 * t + 26])
        / length
    )


def arm_climb(config: Mapping[str, Any], arm: Mapping[str, Any]) -> Mapping[str, Any]:
    """The climb settings an arm sweeps with: the configured climb, windowed if the arm says so.

    An arm without a ``window`` gets ``config['climb']`` itself, so a
    configuration written before windows existed runs exactly as it did.
    """

    if arm.get("split") is not None:
        if arm.get("window") is not None:
            raise ValueError(f"arm {arm['id']!r} sets both window and split")
        return {**config["climb"], "split": dict(arm["split"])}
    if arm.get("window") is None:
        return config["climb"]
    return {**config["climb"], "window": dict(arm["window"])}


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
        swept_message = arm_message(message, ciphertext, perturbation, arm)
        rule = RingRule(arm["ring_rule"], (0, 0, 0), right_rings, len(swept_message.body))
        swept = len(rule.settings(order, starts))
        ranked, evaluated, _ = body_direct_sweep(
            swept_message, [order], rule, starts, config["scorer"], reflector, arm_climb(config, arm),
            swept, 1,
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
            **({"top_window": top["window"]} if "window" in top else {}),
            **({"top_hypothesis": top["split"]} if "split" in top else {}),
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
    # An arm whose score is not distributed like the pooled whole-message null
    # is compared with its own null: the same climb on the same message the arm
    # sweeps, at the same wrong settings. A windowed arm scores the better of
    # two shorter windows. A repaired arm scores the repaired message, whose
    # mask breaks the n-gram chain after a deletion and whose length is one
    # shorter after an insertion.
    own_null_arms = [
        arm
        for arm in settings["arms"]
        if arm.get("window") is not None
        or arm.get("repair") is not None
        or arm.get("split") is not None
    ]
    own_null_messages = {
        arm["id"]: arm_message(message, ciphertext, perturbation, arm) for arm in own_null_arms
    }
    window_climbers: dict[str, Any] = {}
    split_climbers: dict[str, Any] = {}
    for arm in own_null_arms:
        climb = arm_climb(config, arm)
        if climb.get("split") is not None:
            split_climbers[arm["id"]] = stecker_split.SplitClimber(
                scorer.bigram, scorer.combined, own_null_messages[arm["id"]].body, climb
            )
            continue
        if climb.get("window") is None:
            continue
        body = own_null_messages[arm["id"]].body
        window_climbers[arm["id"]] = (
            [
                stecker_batch.BatchedClimber(
                    scorer.bigram, scorer.combined, body[first:stop], climb
                )
                for _, first, stop in climb_windows(len(body), climb["window"])
            ]
            # The cuda engine climbs sweeps; single null climbs take the batched
            # climber it is checked against.
            if resolve_engine(climb) in ("batched", "cuda")
            else None
        )
    null_scores: list[float] = []
    arm_null_scores: dict[str, list[float]] = {arm["id"]: [] for arm in own_null_arms}
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
        wrong_tables: dict[int, Sequence[int]] = {}
        for arm in own_null_arms:
            arm_body = own_null_messages[arm["id"]]
            climb = arm_climb(config, arm)
            if climb.get("split") is not None:
                length = len(arm_body.body) + 1
                if length not in wrong_tables:
                    wrong_tables[length] = enigma_fast.position_permutations(
                        [enigma_fast.rotor_tables(name) for name in wrong_order],
                        wrong_rings, wrong_start, length, reflector,
                    )
                score = split_climbers[arm["id"]].climb(wrong_tables[length])[2]
            elif climb.get("window") is None:
                if arm_body.body == message.body and climb is config["climb"]:
                    # Repair was the identity (no fault): the pooled score is this score.
                    score = null_scores[-1]
                else:
                    score = body_direct_climb(
                        [arm_body], wrong_order, wrong_rings, [wrong_start], scorer, reflector,
                        climb,
                    )[0].score_per_letter
            else:
                length = len(arm_body.body)
                if length not in wrong_tables:
                    wrong_tables[length] = enigma_fast.position_permutations(
                        [enigma_fast.rotor_tables(name) for name in wrong_order],
                        wrong_rings, wrong_start, length, reflector,
                    )
                score = windowed_climb(
                    wrong_tables[length], arm_body.body, scorer, climb,
                    window_climbers[arm["id"]],
                )[2]
            arm_null_scores[arm["id"]].append(score)
    for arm in own_null_arms:
        arms[arm["id"]]["null_scores"] = [round(value, 9) for value in arm_null_scores[arm["id"]]]
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
        # CUDA does not survive fork once the parent has used it (the preflight
        # does), so under the cuda engine the workers are spawned.
        context = (
            multiprocessing.get_context("spawn")
            if resolve_engine(config["climb"]) == "cuda"
            else None
        )
        with futures.ProcessPoolExecutor(
            max_workers=jobs, initializer=_power_init, initargs=(dict(config),),
            mp_context=context,
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
            arm_null: dict[str, Any] = {}
            arm_mean, arm_sd, arm_threshold = null_mean, null_sd, threshold
            if (
                arm.get("window") is not None
                or arm.get("repair") is not None
                or arm.get("split") is not None
            ):
                own = [value for item in per for value in item["null_scores"]]
                arm_mean, arm_sd = statistics.fmean(own), statistics.pstdev(own)
                arm_threshold = arm_mean + z_detect * arm_sd
                arm_null = {
                    "null": {
                        "samples": len(own),
                        "mean_score_per_letter": round(arm_mean, 9),
                        "sd_score_per_letter": round(arm_sd, 9),
                        "detection_threshold_score_per_letter": round(arm_threshold, 9),
                    },
                }
                if arm.get("window") is not None:
                    arm_null = {
                        "window": dict(arm["window"]),
                        **arm_null,
                        "top_window_counts": {
                            name: sum(1 for item in per if item.get("top_window") == name)
                            for name in ("head", "tail", "whole")
                        },
                    }
            recovered = [item["top"]["plugboard_recovered_exactly"] for item in per]
            detected = [
                item["top"]["plugboard_recovered_exactly"]
                and item["top"]["score_per_letter"] >= arm_threshold
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
                    **({"repair": arm["repair"]} if arm.get("repair") else {}),
                    **({"split": dict(arm["split"])} if arm.get("split") is not None else {}),
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
                            (item["top"]["score_per_letter"] - arm_mean) / arm_sd for item in per
                        ),
                        3,
                    ),
                    **arm_null,
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
