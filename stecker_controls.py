"""Preflight checks, positive controls and the indicator confirmation.

These are the gates in front of every target number: a failed preflight check
or positive control makes zero target-search calls.  The indicator
confirmation is the independent check a body-direct sweep candidate has to
survive.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

from enigma import EnigmaI
import enigma_fast
import phase1
import phase7
from provenance import sha256_text
import stecker_batch
import stecker_cuda
from stecker_climb import body_direct_climb, climb_windows, windowed_climb
from stecker_scoring import FastNgramScorer
from stecker_sweeps import resolve_engine
from stecker_traffic import Traffic, encipher_control, normalize_plaintext, random_plugboard


def evaluate_positive_control(
    spec: Mapping[str, Any],
    config: Mapping[str, Any],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
) -> dict[str, Any]:
    """Require exact recovery of a known plugboard and its plaintexts.

    The control is body-direct and is given the true wheel order, ring setting
    and start positions, so what it certifies is precisely the stecker stage at
    the target message lengths.  It deliberately does not certify the rotor
    enumeration, which the sweeps and the calibrations cover separately.
    """

    traffic, truth = encipher_control(spec)
    expected = truth["truth"]
    rotors = tuple(expected["rotor_order_left_to_right"])
    rings = tuple(ord(letter) - 65 for letter in expected["rings"])
    starts = [
        enigma_fast.text_to_indices(message["true_message_key"])
        for message in expected["messages"]
    ]
    outcome, plaintexts = body_direct_climb(
        traffic, rotors, rings, starts, scorer, reflector, config["climb"]
    )
    recovered_plugboard = enigma_fast.plugboard_pairs(outcome.plugboard)
    checks = {
        "plugboard_recovered_exactly": recovered_plugboard == expected["plugboard"],
        "plaintexts_recovered_exactly": [sha256_text(text) for text in plaintexts]
        == [message["plaintext_sha256"] for message in expected["messages"]],
        "indicator_confirms_message_keys": indicator_confirms(
            traffic, expected, outcome.plugboard, reflector
        ),
    }
    windowed: dict[str, Any] = {}
    if config["climb"].get("window") is not None:
        windowed = {
            "windowed_climb": windowed_control_cases(
                traffic,
                [normalize_plaintext(m["plaintext"], m.get("length")) for m in spec["messages"]],
                starts, rotors, rings, scorer, reflector, config["climb"],
                config.get("windowed_control", {}),
            )
        }
        checks["windowed_climb_recovers_known_key"] = windowed["windowed_climb"]["passed"]
    return {
        "id": spec["id"],
        "source": spec.get("source"),
        "rationale": spec.get("rationale"),
        "known_key": expected,
        "recovered_plugboard": recovered_plugboard,
        "recovered_plugboard_pairs": outcome.pair_count,
        "score_per_letter": round(outcome.score_per_letter, 9),
        "unsteckered_score_per_letter": round(outcome.unsteckered_score_per_letter, 9),
        "climb_passes": outcome.passes,
        "climb_evaluations": outcome.evaluations,
        "recovered_plaintext_prefixes": [text[:60] for text in plaintexts],
        **windowed,
        "checks": checks,
        "passed": all(checks.values()),
    }


def windowed_control_cases(
    traffic: Sequence[Traffic],
    plaintexts: Sequence[str],
    starts: Sequence[Sequence[int]],
    rotors: Sequence[str],
    rings: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    settings: Mapping[str, Any],
    control: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the configured windowed climb on planted keys over a control message.

    ``body_direct_climb`` ignores ``climb.window``, so the ordinary control
    certifies the whole-message climb only.  For every control message at least
    ten letters longer than the window, this re-enciphers the message's
    plaintext under the control's wheel order, rings and start with ``draws``
    seeded random ten-pair plugboards, cycling through three forms: clean; one
    letter deleted at position W, which leaves the head window clean at the
    true setting; and one letter deleted at position n - 1 - W, read at the
    setting one keystroke later, which leaves the tail clean.  Each is climbed
    exactly as a sweep climbs a setting.

    One fixed key is a poor gate here: a W-letter window recovers a ten-pair
    plugboard only most of the time (phase1-windowed-climb-power-v1), so a sound
    climb would fail a single-key check by chance.  The gate is instead a floor
    on the number of planted keys recovered exactly, set far below the measured
    rate so a sound climb practically never misses it, while broken slicing or
    window selection recovers none.
    """

    size = int(settings["window"]["letters"])
    seed = int(control.get("seed", 20261006))
    draws = int(control.get("draws", 12))
    minimum = int(control.get("minimum_recovered", 3))
    order = [enigma_fast.rotor_tables(name) for name in rotors]
    rows: list[dict[str, Any]] = []
    for message, plaintext, start in zip(traffic, plaintexts, starts):
        length = len(message.body)
        if length < size + 10:
            continue
        generator = random.Random(f"{seed}:{message.designator}")
        rotor_names = tuple(rotors)
        table = enigma_fast.position_permutations(order, rings, start, length, reflector)
        forms = (
            ("clean", None, table),
            ("deletion_at_window", size, table),
            # After a deletion at p the letters from p on were enciphered one
            # keystroke later than their new index says, so the clean tail is
            # read with the table shifted by one position.
            ("deletion_before_tail", length - 1 - size, table[26:]),
        )
        for draw in range(draws):
            form, position, shifted = forms[draw % len(forms)]
            plugboard = random_plugboard(generator, 10)
            body = list(
                enigma_fast.text_to_indices(
                    EnigmaI(
                        rotors=rotor_names,
                        rings="".join(chr(65 + value) for value in rings),
                        positions="".join(chr(65 + value) for value in start),
                        plugboard=plugboard,
                    ).crypt(plaintext)
                )
            )
            if position is not None:
                del body[position]
            found, _, score, window = windowed_climb(
                shifted[: 26 * len(body)], body, scorer, settings
            )
            expected = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard))
            rows.append(
                {
                    "message": message.designator,
                    "draw": draw,
                    "form": form,
                    "deleted_position": position,
                    "window": window,
                    "plugboard_recovered_exactly": enigma_fast.plugboard_pairs(found) == expected,
                    "score_per_letter": round(score, 9),
                }
            )
    recovered = sum(1 for row in rows if row["plugboard_recovered_exactly"])
    messages = len({row["message"] for row in rows})
    return {
        "window": dict(settings["window"]),
        "seed": seed,
        "draws_per_message": draws,
        "minimum_recovered_per_message": minimum,
        "recovered": recovered,
        "attempted": len(rows),
        "draws": rows,
        "passed": all(
            sum(1 for row in rows if row["message"] == name and row["plugboard_recovered_exactly"])
            >= minimum
            for name in {row["message"] for row in rows}
        ),
        "note": (
            "No control message is long enough to split into windows, so the "
            "windowed climb is the whole-message climb certified above."
            if not messages
            else "Planted keys over the control plaintext at the control's setting; "
            "each message must recover at least the minimum."
        ),
    }


def indicator_confirms(
    traffic: Sequence[Traffic],
    expected: Mapping[str, Any],
    plugboard: Sequence[int],
    reflector: Sequence[int],
) -> bool:
    """Independent confirmation: does the clear indicator give the same keys?

    Once the plugboard is known the indicator stops being a search input and
    becomes a check that the body-direct answer is consistent with a datum the
    search never used.
    """

    order = [enigma_fast.rotor_tables(name) for name in expected["rotor_order_left_to_right"]]
    rings = [ord(letter) - 65 for letter in expected["rings"]]
    for message, record in zip(traffic, expected["messages"]):
        grundstellung, encrypted_key, _ = message.oriented(expected["indicator_ordering"])
        recovered = enigma_fast.crypt_indices(
            order, rings, grundstellung, encrypted_key, plugboard, reflector
        )
        if enigma_fast.indices_to_text(recovered) != record["true_message_key"]:
            return False
    return True


def pooled_date_score(
    traffic: Sequence[Traffic],
    order: Sequence[Any],
    rings: Sequence[int],
    plugboard: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    ordering: str,
) -> tuple[float, list[str]]:
    """Derive every message key from the clear indicator and score the date."""

    total = 0.0
    letters = 0
    keys: list[str] = []
    for message in traffic:
        grundstellung, encrypted_key, body = message.oriented(ordering)
        recovered = enigma_fast.crypt_indices(
            order, list(rings), grundstellung, encrypted_key, plugboard, reflector
        )
        keys.append(enigma_fast.indices_to_text(recovered))
        total += scorer.score_indices(
            enigma_fast.crypt_indices(
                order, list(rings), tuple(recovered), body, plugboard, reflector
            )
        )
        letters += message.letters
    return total / letters, keys


def compatible_ring_settings(
    message: Traffic,
    swept_rings: Sequence[int],
    swept_start: Sequence[int],
    plugboard: Sequence[int],
    order: Sequence[Any],
    reflector: Sequence[int],
    ordering: str,
) -> list[tuple[int, int, int]]:
    """Ring settings whose indicator-derived key reproduces the swept body.

    The sweep holds the ring setting and searches the start position, so a
    retained candidate pins down the left and middle wheels' *offset* — ring
    subtracted from position — and not their absolute ring setting: shifting a
    ring and its start position together leaves the body unchanged for as long
    as that wheel does not step.  The held ``AAA`` is therefore the sweep's
    parameterization and not a claim about the daily key.  The indicator is
    enciphered at the clear Grundstellung, where that freedom is gone, so
    deciphering it under the held rings uses a daily key the sweep never
    proposed and can dismiss a genuine plaintext hit as noise.

    The right-hand wheel's ring is not free — it moves the turnover inside the
    message, which is why the slice declares it — so only the left and middle
    are enumerated.  A ring setting qualifies only if the key it derives from
    the indicator reproduces the exact body the sweep scored.  That is a test
    against the machine rather than an offset identity, so a candidate whose
    left wheel did step during the message is not credited by accident.
    """

    grundstellung, encrypted_key, body = message.oriented(ordering)
    swept = enigma_fast.crypt_indices(
        order, list(swept_rings), tuple(swept_start), body, plugboard, reflector
    )
    compatible: list[tuple[int, int, int]] = []
    for left in range(26):
        for middle in range(26):
            rings = (left, middle, swept_rings[2])
            key = enigma_fast.crypt_indices(
                order, list(rings), grundstellung, encrypted_key, plugboard, reflector
            )
            reproduced = enigma_fast.crypt_indices(
                order, list(rings), tuple(key), body, plugboard, reflector
            )
            if reproduced == swept:
                compatible.append(rings)
    return compatible


def confirm_against_date(
    traffic: Sequence[Traffic],
    plugboard: Sequence[int],
    rotor_order: Sequence[str],
    rings: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    orderings: Sequence[str],
    swept_message: Traffic | None = None,
    swept_start: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Score a whole date under a candidate plugboard, keys from the indicator.

    ``swept_message`` and ``swept_start`` name the body-direct result being
    confirmed.  Given them, the ring setting is recovered instead of assumed:
    every setting that reproduces the swept body through the clear indicator is
    scored and the best is reported.  Without them the passed rings are scored
    as given, which is what a known-key control wants.

    When no ring setting reproduces the swept body, the candidate is
    inconsistent with the indicator under every ring setting the slice allows.
    That is evidence against the candidate rather than a reason to skip the
    check, so the held rings are scored as a floor and ``rings_recovered`` is
    false on those arms.
    """

    order = [enigma_fast.rotor_tables(name) for name in rotor_order]
    arms: list[dict[str, Any]] = []
    for ordering in orderings:
        if swept_message is None or swept_start is None:
            ring_options: list[tuple[int, ...]] = [tuple(rings)]
            recovered = True
        else:
            compatible = compatible_ring_settings(
                swept_message,
                rings,
                swept_start,
                plugboard,
                order,
                reflector,
                ordering,
            )
            recovered = bool(compatible)
            ring_options = list(compatible) or [tuple(rings)]
        for ring_setting in ring_options:
            score, keys = pooled_date_score(
                traffic, order, ring_setting, plugboard, scorer, reflector, ordering
            )
            arms.append(
                {
                    "indicator_ordering": ordering,
                    "rings": "".join(chr(65 + value) for value in ring_setting),
                    "rings_recovered": recovered,
                    "pooled_score_per_letter": round(score, 9),
                    "message_keys": keys,
                }
            )
    best = max(arms, key=lambda arm: arm["pooled_score_per_letter"])
    return {
        "arms": arms,
        "compatible_ring_settings": sum(1 for arm in arms if arm["rings_recovered"]),
        "best_indicator_ordering": best["indicator_ordering"],
        "best_rings": best["rings"],
        "best_rings_recovered": best["rings_recovered"],
        "best_pooled_score_per_letter": best["pooled_score_per_letter"],
        "best_message_keys": best["message_keys"],
    }


def configured_windows(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every climb window a configuration can run, in first-mention order."""

    windows: list[dict[str, Any]] = []
    candidates = [config["climb"].get("window")] + [
        arm.get("window") for arm in config.get("end_to_end_power", {}).get("arms", [])
    ]
    for window in candidates:
        if window is not None and dict(window) not in windows:
            windows.append(dict(window))
    return windows


def parity_sample_size(config: Mapping[str, Any]) -> tuple[int, int]:
    settings = config.get("batched_climb_parity", {})
    return int(settings.get("seed", 20261003)), int(settings.get("samples", 24))


def parity_cases(config: Mapping[str, Any], reflector: Sequence[int]):
    """The seeded climb-parity cases: ``(body, order, rings, start, table)``.

    Half climb at a wrong setting, because a sweep is almost entirely wrong
    settings, and some carry masked letters.  The batched and cuda parity
    reports draw the same cases from the same seed.
    """

    seed, samples = parity_sample_size(config)
    generator = random.Random(seed)
    wheels = list(config["machine"]["wheel_set"])
    source = "".join(
        normalize_plaintext(row["raw"]) for row in config["scorer_validation"]["plaintexts"]
    )
    for case in range(samples):
        length = generator.randrange(60, min(167, len(source)) + 1)
        order = tuple(generator.sample(wheels, 3))
        rings = tuple(generator.randrange(26) for _ in range(3))
        start = tuple(generator.randrange(26) for _ in range(3))
        ciphertext = EnigmaI(
            rotors=order,
            rings="".join(chr(65 + value) for value in rings),
            positions="".join(chr(65 + value) for value in start),
            plugboard=random_plugboard(generator, 10),
        ).crypt(source[:length])
        body = list(enigma_fast.text_to_indices(ciphertext))
        for position in generator.sample(range(length), case % 4):
            body[position] = -1
        if case % 5 == 0:
            body[0] = body[1] = -1
        if case % 2:
            order = tuple(generator.sample(wheels, 3))
            start = tuple(generator.randrange(26) for _ in range(3))
        table = enigma_fast.position_permutations(
            [enigma_fast.rotor_tables(name) for name in order], rings, start, length, reflector
        )
        yield body, order, rings, start, table


def batched_climb_parity_report(
    config: Mapping[str, Any], scorer: FastNgramScorer, reflector: Sequence[int]
) -> dict[str, Any]:
    """Check the batched climb against the reference on seeded random settings.

    The reference climb is the definition; the batched one is an optimisation of
    it, so the two have to end on the same plugboard after the same number of
    evaluations.  Half the samples climb at a wrong setting, because a sweep is
    almost entirely wrong settings, and some carry masked letters.
    """

    seed, samples = parity_sample_size(config)
    climb = config["climb"]
    windows = configured_windows(config)
    identical = same_evaluations = 0
    windowed_identical = 0
    for body, order, rings, start, table in parity_cases(config, reflector):
        reference, _ = body_direct_climb(
            [Traffic("PARITY", (0, 0, 0), (0, 0, 0), tuple(body))],
            order, rings, [start], scorer, reflector, climb,
        )
        plugboard, evaluations = stecker_batch.BatchedClimber(
            scorer.bigram, scorer.combined, body, climb
        ).climb(table)
        identical += list(reference.plugboard) == plugboard
        same_evaluations += reference.evaluations == evaluations
        # The windowed climb runs the same batched climber on each window's
        # letters; it has to pick the same window and end on the same
        # plugboard, after the same count, as the reference windowed climb.
        for window in windows:
            windowed = {**climb, "window": window}
            expected = windowed_climb(table, body, scorer, windowed)
            climbers = [
                stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body[first:stop], windowed)
                for _, first, stop in climb_windows(len(body), window)
            ]
            windowed_identical += windowed_climb(table, body, scorer, windowed, climbers) == expected
    report: dict[str, Any] = {
        "seed": seed,
        "samples": samples,
        "identical_final_plugboards": identical,
        "identical_evaluation_counts": same_evaluations,
    }
    passed = identical == samples and same_evaluations == samples
    if windows:
        report["windows"] = windows
        report["windowed_climbs_compared"] = samples * len(windows)
        report["windowed_climbs_identical"] = windowed_identical
        passed = passed and windowed_identical == samples * len(windows)
    report["passed"] = passed
    return report


def cuda_climb_parity_report(
    config: Mapping[str, Any], scorer: FastNgramScorer, reflector: Sequence[int]
) -> dict[str, Any]:
    """Check the cuda climb against the batched climb on the seeded parity cases.

    The batched climb is the specification the GPU reproduces, so every case has
    to end on the same plugboard after the same number of evaluations, with the
    same score per letter and, windowed, the same window.  The GPU sums in the
    batched climber's order, so the scores are expected to agree exactly; the
    report records the worst difference and fails above 1e-9.
    """

    seed, samples = parity_sample_size(config)
    climb = {key: value for key, value in config["climb"].items() if key != "window"}
    windows = configured_windows(config)
    identical = same_evaluations = 0
    windowed_identical = 0
    worst = 0.0
    tolerance = 1e-9
    for body, order, rings, start, table in parity_cases(config, reflector):
        letters = sum(1 for value in body if value >= 0)
        plugboard, evaluations = stecker_batch.BatchedClimber(
            scorer.bigram, scorer.combined, body, climb
        ).climb(table)
        expected_score = scorer.score_decryption(table, body, plugboard) / letters
        gpu = stecker_cuda.CudaClimber(scorer.bigram, scorer.combined, body, climb, reflector)
        got_plugboard, got_evaluations, got_score, _ = gpu.climb_one(order, rings, start)
        gpu.close()
        worst = max(worst, abs(got_score - expected_score))
        identical += got_plugboard == plugboard and abs(got_score - expected_score) <= tolerance
        same_evaluations += got_evaluations == evaluations
        for window in windows:
            windowed = {**climb, "window": window}
            climbers = [
                stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body[first:stop], windowed)
                for _, first, stop in climb_windows(len(body), window)
            ]
            expected = windowed_climb(table, body, scorer, windowed, climbers)
            gpu = stecker_cuda.CudaClimber(scorer.bigram, scorer.combined, body, windowed, reflector)
            got = gpu.climb_one(order, rings, start)
            gpu.close()
            worst = max(worst, abs(got[2] - expected[2]))
            windowed_identical += (
                got[0] == expected[0]
                and got[1] == expected[1]
                and got[3] == expected[3]
                and abs(got[2] - expected[2]) <= tolerance
            )
    passed = identical == samples and same_evaluations == samples
    report: dict[str, Any] = {
        "seed": seed,
        "samples": samples,
        "reference": "stecker_batch.BatchedClimber",
        "identical_final_plugboards": identical,
        "identical_evaluation_counts": same_evaluations,
        "worst_absolute_score_difference": worst,
        "score_tolerance": tolerance,
    }
    if windows:
        report["windows"] = windows
        report["windowed_climbs_compared"] = samples * len(windows)
        report["windowed_climbs_identical"] = windowed_identical
        passed = passed and windowed_identical == samples * len(windows)
    report["passed"] = passed
    return report


def run_preflight(config: Mapping[str, Any], scorer: FastNgramScorer) -> dict[str, Any]:
    simulator = phase1.published_vector_results()
    kernel = enigma_fast.parity_report(
        int(config["kernel_parity"]["seed"]), int(config["kernel_parity"]["samples"])
    )
    scorer_parity = scorer.parity_report(
        int(config["scorer_parity"]["seed"]),
        int(config["scorer_parity"]["samples"]),
        float(config["scorer_parity"]["relative_tolerance"]),
    )
    discrimination = phase7.validate_scorer(
        {"validation": config["scorer_validation"]}, scorer.reference
    )
    checks = {
        "published_simulator_vectors": all(row["passed"] for row in simulator),
        "fast_kernel_matches_reference": kernel["passed"],
        "fast_scorer_matches_phase7": scorer_parity["passed"],
        "scorer_discriminates_authentic_plaintext": discrimination["passed"],
    }
    report: dict[str, Any] = {
        "simulator_validation": simulator,
        "kernel_parity": kernel,
        "scorer_parity": scorer_parity,
        "scorer_discrimination": discrimination,
    }
    engine = resolve_engine(config["climb"])
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])
    if engine in ("batched", "cuda"):
        parity = batched_climb_parity_report(config, scorer, reflector)
        report["batched_climb_parity"] = parity
        checks["batched_climb_matches_reference"] = parity["passed"]
    if engine == "cuda":
        # The GPU reproduces the batched climb, which reproduces the reference;
        # a mismatch on either link blocks the run before any target search.
        gpu = cuda_climb_parity_report(config, scorer, reflector)
        report["cuda_climb_parity"] = gpu
        checks["cuda_climb_matches_batched"] = gpu["passed"]
    report["checks"] = checks
    report["passed"] = all(checks.values())
    return report
