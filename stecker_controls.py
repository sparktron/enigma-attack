"""Preflight checks, positive controls and the indicator confirmation.

These are the gates in front of every target number: a failed preflight check
or positive control makes zero target-search calls.  The indicator
confirmation is the independent check a body-direct sweep candidate has to
survive.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import enigma_fast
import phase1
import phase7
from provenance import sha256_text
from stecker_climb import body_direct_climb
from stecker_scoring import FastNgramScorer
from stecker_traffic import Traffic, encipher_control


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
        "checks": checks,
        "passed": all(checks.values()),
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
    return {
        "simulator_validation": simulator,
        "kernel_parity": kernel,
        "scorer_parity": scorer_parity,
        "scorer_discrimination": discrimination,
        "checks": checks,
        "passed": all(checks.values()),
    }
