"""Known-key measurements of what the Phase 1 stecker attack can and cannot do.

Each calibration enciphers known plaintext under a drawn key with the reference
machine and asks one question of the attack's machinery: does the IC stage
separate, does the climb recover the plugboard, does a truncated climb screen,
and can the indicator-coupled formulation be climbed at all.
"""

from __future__ import annotations

import random
import statistics
import time
from collections.abc import Mapping, Sequence
from typing import Any

import enigma_fast
from enigma import EnigmaI
from provenance import sha256_text
from stecker_climb import body_direct_climb, indicator_coupled_climb
from stecker_scoring import FastNgramScorer, index_of_coincidence, letter_counts
from stecker_traffic import Traffic, encipher_control, normalize_plaintext, random_plugboard


def calibrate_ic_stage(
    config: Mapping[str, Any], reflector: Sequence[int]
) -> dict[str, Any]:
    """Measure whether the cited index-of-coincidence stage can work here.

    For each (length, stecker size) cell the true rotor setting's unsteckered
    IC is compared with the IC of many wrong settings on the same ciphertext.
    The stage is usable only where the true setting stands clear of that null.
    """

    settings = config["ic_stage_calibration"]
    plaintext = normalize_plaintext(settings["plaintext"])
    generator = random.Random(int(settings["seed"]))
    rows: list[dict[str, Any]] = []
    for length in settings["lengths"]:
        text = plaintext[:length]
        if len(text) < length:
            raise ValueError("calibration plaintext is too short for the requested length")
        for pairs in settings["stecker_pairs"]:
            rotors = tuple(generator.sample(["I", "II", "III", "IV", "V"], 3))
            rings = tuple(generator.randrange(26) for _ in range(3))
            start = tuple(generator.randrange(26) for _ in range(3))
            plugboard = random_plugboard(generator, pairs)
            ciphertext = EnigmaI(
                rotors=rotors,
                rings="".join(chr(65 + value) for value in rings),
                positions="".join(chr(65 + value) for value in start),
                plugboard=plugboard,
            ).crypt(text)
            body = enigma_fast.text_to_indices(ciphertext)
            order = [enigma_fast.rotor_tables(name) for name in rotors]
            true_ic = index_of_coincidence(
                *letter_counts(enigma_fast.crypt_indices(order, rings, start, body))
            )
            null = []
            for _ in range(int(settings["null_trials"])):
                wrong_order = [
                    enigma_fast.rotor_tables(name)
                    for name in generator.sample(["I", "II", "III", "IV", "V"], 3)
                ]
                wrong_rings = tuple(generator.randrange(26) for _ in range(3))
                wrong_start = tuple(generator.randrange(26) for _ in range(3))
                null.append(
                    index_of_coincidence(
                        *letter_counts(
                            enigma_fast.crypt_indices(
                                wrong_order, wrong_rings, wrong_start, body
                            )
                        )
                    )
                )
            mean = statistics.fmean(null)
            deviation = statistics.pstdev(null)
            rows.append(
                {
                    "length": length,
                    "stecker_pairs": pairs,
                    "true_setting_ic": round(true_ic, 9),
                    "wrong_setting_ic_mean": round(mean, 9),
                    "wrong_setting_ic_sd": round(deviation, 9),
                    "wrong_setting_ic_max": round(max(null), 9),
                    "z_score": round((true_ic - mean) / deviation, 6),
                    "separates": true_ic > max(null),
                }
            )
    threshold = float(settings["usable_z"])
    usable = [row for row in rows if row["z_score"] >= threshold]
    return {
        "method_reference": settings["method_reference"],
        "null_trials_per_cell": int(settings["null_trials"]),
        "usable_z": threshold,
        "cells": rows,
        "usable_cells": [
            {"length": row["length"], "stecker_pairs": row["stecker_pairs"]}
            for row in usable
        ],
        "usable_at_target_scale": any(
            row["length"] >= int(settings["target_length"])
            and row["stecker_pairs"] >= int(settings["target_stecker_pairs"])
            and row["z_score"] >= threshold
            for row in rows
        ),
        "interpretation": (
            "The index-of-coincidence stage separates the true rotor setting "
            "only in the cells listed as usable. Outside them the retained "
            "candidate list is uninformative however large it is made, because "
            "the statistic itself carries no signal."
        ),
    }


def calibrate_climb_capability(
    config: Mapping[str, Any], scorer: FastNgramScorer, reflector: Sequence[int]
) -> dict[str, Any]:
    """Measure body-direct stecker recovery against length and stecker size."""

    settings = config["climb_capability_calibration"]
    plaintext = normalize_plaintext(settings["plaintext"])
    generator = random.Random(int(settings["seed"]))
    draws = int(settings["draws"])
    rows: list[dict[str, Any]] = []
    for length in settings["lengths"]:
        text = plaintext[:length]
        for pairs in settings["stecker_pairs"]:
            # Several independent key draws per cell, because one draw cannot
            # distinguish "this length is above the recovery threshold" from
            # "this key happened to be easy".
            attempts: list[dict[str, Any]] = []
            for draw in range(draws):
                rotors = tuple(generator.sample(["I", "II", "III", "IV", "V"], 3))
                rings = tuple(generator.randrange(26) for _ in range(3))
                start = tuple(generator.randrange(26) for _ in range(3))
                plugboard = random_plugboard(generator, pairs)
                ciphertext = EnigmaI(
                    rotors=rotors,
                    rings="".join(chr(65 + value) for value in rings),
                    positions="".join(chr(65 + value) for value in start),
                    plugboard=plugboard,
                ).crypt(text)
                message = Traffic(
                    designator=f"CAL-{length}-{pairs}-{draw}",
                    first_trigram=(0, 0, 0),
                    second_trigram=(0, 0, 0),
                    body=enigma_fast.text_to_indices(ciphertext),
                )
                outcome, plaintexts = body_direct_climb(
                    [message], rotors, rings, [start], scorer, reflector, config["climb"]
                )
                null = []
                for _ in range(int(settings["null_trials"])):
                    wrong_rotors = tuple(generator.sample(["I", "II", "III", "IV", "V"], 3))
                    wrong_rings = tuple(generator.randrange(26) for _ in range(3))
                    wrong_start = tuple(generator.randrange(26) for _ in range(3))
                    null.append(
                        body_direct_climb(
                            [message],
                            wrong_rotors,
                            wrong_rings,
                            [wrong_start],
                            scorer,
                            reflector,
                            config["climb"],
                        )[0].score_per_letter
                    )
                mean = statistics.fmean(null)
                deviation = statistics.pstdev(null)
                expected_plugboard = enigma_fast.plugboard_pairs(
                    enigma_fast.plugboard_table(plugboard)
                )
                attempts.append(
                    {
                        "draw": draw,
                        "plaintext_recovered_exactly": plaintexts[0] == text,
                        "plugboard_recovered_exactly": enigma_fast.plugboard_pairs(
                            outcome.plugboard
                        )
                        == expected_plugboard,
                        "true_setting_score_per_letter": round(outcome.score_per_letter, 9),
                        "wrong_setting_score_mean": round(mean, 9),
                        "wrong_setting_score_max": round(max(null), 9),
                        "z_score": round((outcome.score_per_letter - mean) / deviation, 6),
                        "margin_over_best_wrong_setting": round(
                            outcome.score_per_letter - max(null), 9
                        ),
                        "climb_evaluations": outcome.evaluations,
                    }
                )
            recovered = sum(row["plaintext_recovered_exactly"] for row in attempts)
            rows.append(
                {
                    "length": length,
                    "stecker_pairs": pairs,
                    "draws": draws,
                    "plaintexts_recovered_exactly": recovered,
                    "plugboards_recovered_exactly": sum(
                        row["plugboard_recovered_exactly"] for row in attempts
                    ),
                    "recovered_every_draw": recovered == draws,
                    "median_z_score": round(
                        statistics.median(row["z_score"] for row in attempts), 6
                    ),
                    "attempts": attempts,
                }
            )
    return {
        "null_trials_per_cell_per_draw": int(settings["null_trials"]),
        "draws_per_cell": draws,
        "cells": rows,
        "recovers_at_target_scale": all(
            row["recovered_every_draw"]
            for row in rows
            if row["length"] >= int(settings["target_length"])
            and row["stecker_pairs"] >= int(settings["target_stecker_pairs"])
        ),
        "shortest_length_recovered_every_draw_at_target_stecker": min(
            (
                row["length"]
                for row in rows
                if row["stecker_pairs"] >= int(settings["target_stecker_pairs"])
                and row["recovered_every_draw"]
            ),
            default=None,
        ),
        "interpretation": (
            "Where the plaintext is recovered on every draw, the stecker stage is "
            "not the limiting factor and the cost of enumerating rotor settings is. "
            "Where it is not, no amount of rotor enumeration helps, because the "
            "objective does not identify the key even when the rotor setting is "
            "handed to it."
        ),
    }


def calibrate_screening_budget(
    config: Mapping[str, Any], scorer: FastNgramScorer, reflector: Sequence[int]
) -> dict[str, Any]:
    """Does a truncated climb separate, so a cheap pre-filter exists?

    Asked at each declared length, because the answer sets the cost of a
    body-direct sweep: with a screen, most rotor settings can be rejected after
    a couple of passes and only the survivors need a converged climb.
    """

    settings = config["screening_calibration"]
    plaintext = normalize_plaintext(settings["plaintext"])
    lengths: list[dict[str, Any]] = []
    for length in settings["lengths"]:
        generator = random.Random(int(settings["seed"]) + length)
        text = plaintext[:length]
        rotors = tuple(generator.sample(["I", "II", "III", "IV", "V"], 3))
        rings = tuple(generator.randrange(26) for _ in range(3))
        start = tuple(generator.randrange(26) for _ in range(3))
        plugboard = random_plugboard(generator, int(settings["stecker_pairs"]))
        ciphertext = EnigmaI(
            rotors=rotors,
            rings="".join(chr(65 + value) for value in rings),
            positions="".join(chr(65 + value) for value in start),
            plugboard=plugboard,
        ).crypt(text)
        message = Traffic(
            designator=f"SCREEN-{length}",
            first_trigram=(0, 0, 0),
            second_trigram=(0, 0, 0),
            body=enigma_fast.text_to_indices(ciphertext),
        )
        wrong = [
            (
                tuple(generator.sample(["I", "II", "III", "IV", "V"], 3)),
                tuple(generator.randrange(26) for _ in range(3)),
                tuple(generator.randrange(26) for _ in range(3)),
            )
            for _ in range(int(settings["null_trials"]))
        ]
        rows: list[dict[str, Any]] = []
        for passes in settings["max_passes"]:
            budget = dict(config["climb"])
            budget["max_passes"] = passes
            started = time.monotonic()
            true_outcome, true_plaintexts = body_direct_climb(
                [message], rotors, rings, [start], scorer, reflector, budget
            )
            true_seconds = time.monotonic() - started
            null = [
                body_direct_climb(
                    [message], names, wrong_rings, [wrong_start], scorer, reflector, budget
                )[0].score_per_letter
                for names, wrong_rings, wrong_start in wrong
            ]
            mean = statistics.fmean(null)
            deviation = statistics.pstdev(null)
            rows.append(
                {
                    "max_passes": passes,
                    "true_setting_score_per_letter": round(
                        true_outcome.score_per_letter, 9
                    ),
                    "wrong_setting_score_mean": round(mean, 9),
                    "wrong_setting_score_max": round(max(null), 9),
                    "z_score": round((true_outcome.score_per_letter - mean) / deviation, 6),
                    "separates": true_outcome.score_per_letter > max(null),
                    "plaintext_recovered_exactly": true_plaintexts[0] == text,
                    "seconds_per_setting": round(true_seconds, 6),
                }
            )
        separating = [row["max_passes"] for row in rows if row["separates"]]
        lengths.append(
            {
                "length": length,
                "rows": rows,
                "cheapest_separating_max_passes": min(separating, default=None),
            }
        )
    cheap = int(settings["cheap_passes"])
    return {
        "stecker_pairs": int(settings["stecker_pairs"]),
        "null_trials": int(settings["null_trials"]),
        "rationale": settings["rationale"],
        "lengths": lengths,
        "cheap_screen_exists": any(
            row["cheapest_separating_max_passes"] is not None
            and row["cheapest_separating_max_passes"] <= cheap
            for row in lengths
        ),
        "cheap_screen_at_target_length": next(
            (
                row["cheapest_separating_max_passes"] is not None
                and row["cheapest_separating_max_passes"] <= cheap
                for row in lengths
                if row["length"] == int(settings["target_length"])
            ),
            False,
        ),
        "interpretation": (
            "If no truncated climb separates at a length, every rotor setting in a "
            "body-direct sweep of a message that long costs a converged climb and "
            "the sweep cannot be made cheaper by pre-filtering."
        ),
    }


def measure_indicator_gradient(
    config: Mapping[str, Any], scorer: FastNgramScorer, reflector: Sequence[int]
) -> dict[str, Any]:
    """Climb the indicator-coupled formulation at a known key and see if it works.

    The plugboard sits inside the indicator machine, so a wrong stecker gives a
    wrong message key and a body of noise.  This records what the climb
    actually does when it is handed the true wheel order and ring setting.
    """

    spec = config["indicator_gradient_control"]
    traffic, truth = encipher_control(spec)
    expected = truth["truth"]
    rotors = tuple(expected["rotor_order_left_to_right"])
    rings = tuple(ord(letter) - 65 for letter in expected["rings"])
    outcome, plaintexts, keys = indicator_coupled_climb(
        traffic,
        expected["indicator_ordering"],
        rotors,
        rings,
        scorer,
        reflector,
        config["climb"],
    )
    starts = [
        enigma_fast.text_to_indices(message["true_message_key"])
        for message in expected["messages"]
    ]
    reference, reference_plaintexts = body_direct_climb(
        traffic, rotors, rings, starts, scorer, reflector, config["climb"]
    )
    return {
        "known_key": expected,
        "indicator_coupled": {
            "score_per_letter": round(outcome.score_per_letter, 9),
            "recovered_plugboard": enigma_fast.plugboard_pairs(outcome.plugboard),
            "recovered_plugboard_pairs": outcome.pair_count,
            "recovered_message_keys": keys,
            "true_message_keys": [m["true_message_key"] for m in expected["messages"]],
            "message_keys_recovered": keys
            == [m["true_message_key"] for m in expected["messages"]],
            "plaintexts_recovered": [
                sha256_text(text) for text in plaintexts
            ]
            == [m["plaintext_sha256"] for m in expected["messages"]],
            "climb_evaluations": outcome.evaluations,
        },
        "body_direct_reference": {
            "score_per_letter": round(reference.score_per_letter, 9),
            "recovered_plugboard": enigma_fast.plugboard_pairs(reference.plugboard),
            "plugboard_recovered_exactly": enigma_fast.plugboard_pairs(
                reference.plugboard
            )
            == expected["plugboard"],
            "plaintexts_recovered": [
                sha256_text(text) for text in reference_plaintexts
            ]
            == [m["plaintext_sha256"] for m in expected["messages"]],
            "climb_evaluations": reference.evaluations,
        },
        "indicator_coupling_is_climbable": (
            keys == [m["true_message_key"] for m in expected["messages"]]
        ),
        "interpretation": (
            "Both arms are handed the true wheel order and ring setting and the "
            "same climb. The body-direct arm is given the true start positions; "
            "the indicator-coupled arm must derive them through the plugboard it "
            "is searching for. A failure in the coupled arm beside a success in "
            "the direct arm isolates the coupling, not the climb, as the cause."
        ),
    }


def run_calibration(
    config: Mapping[str, Any], scorer: FastNgramScorer, reflector: Sequence[int]
) -> dict[str, Any]:
    ic_stage = calibrate_ic_stage(config, reflector)
    capability = calibrate_climb_capability(config, scorer, reflector)
    screening = calibrate_screening_budget(config, scorer, reflector)
    gradient = measure_indicator_gradient(config, scorer, reflector)
    findings = {
        "ic_stage_usable_at_target_scale": ic_stage["usable_at_target_scale"],
        "stecker_climb_recovers_at_target_scale": capability["recovers_at_target_scale"],
        "cheap_screen_exists": screening["cheap_screen_exists"],
        "indicator_coupling_is_climbable": gradient["indicator_coupling_is_climbable"],
    }
    return {
        "ic_stage_calibration": ic_stage,
        "climb_capability_calibration": capability,
        "screening_calibration": screening,
        "indicator_gradient_control": gradient,
        "findings": findings,
    }
