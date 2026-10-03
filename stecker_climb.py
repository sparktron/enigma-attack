"""The stecker hill-climb, in its body-direct and indicator-coupled forms.

See :mod:`phase1_stecker` for why the two formulations behave so differently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import enigma_fast
from stecker_scoring import FastNgramScorer, index_of_coincidence
from stecker_traffic import Traffic


@dataclass(frozen=True)
class ClimbOutcome:
    score_per_letter: float
    unsteckered_score_per_letter: float
    plugboard: tuple[int, ...]
    pair_count: int
    passes: int
    evaluations: int
    phases: tuple[dict[str, Any], ...] = ()


def coincidence_of_decryption(
    table: Sequence[int], body: Sequence[int], plugboard: Sequence[int]
) -> float:
    """Index of coincidence of a steckered decryption, fused like the scorer."""

    counts = [0] * 26
    total = 0
    offset = 0
    for value in body:
        if value < 0:
            offset += 26
            continue
        counts[plugboard[table[offset + plugboard[value]]]] += 1
        offset += 26
        total += 1
    if total < 2:
        return 0.0
    return sum(count * (count - 1) for count in counts) / (total * (total - 1))


def climb_stecker(
    evaluate,
    letters: int,
    max_pairs: int,
    max_passes: int,
    minimum_gain: float,
    initial: Sequence[int] | None = None,
) -> ClimbOutcome:
    """Best-improvement stecker search over all 325 pairs plus 26 unplug moves.

    Best improvement, not first improvement.  Measured on a 166-letter control:
    best improvement recovers the exact ten-pair plugboard; first improvement is
    1.4x faster, recovers the wrong plugboard, and collapses the separation from
    the wrong-setting null from z = +21 to z = +2.  Partial plugboards carry
    almost no signal, so the climb has to be run to convergence or not at all.
    """

    current = list(range(26)) if initial is None else list(initial)
    best = evaluate(current)
    starting = best
    evaluations = 1
    passes = 0
    while passes < max_passes:
        passes += 1
        pass_best = best
        chosen: list[int] | None = None
        for first in range(25):
            for second in range(first + 1, 26):
                trial = current.copy()
                partner_first = trial[first]
                partner_second = trial[second]
                if partner_first == second:
                    continue
                trial[partner_first] = partner_first
                trial[partner_second] = partner_second
                trial[first] = second
                trial[second] = first
                if sum(1 for x in range(26) if trial[x] > x) > max_pairs:
                    continue
                score = evaluate(trial)
                evaluations += 1
                if score > pass_best + minimum_gain:
                    pass_best = score
                    chosen = trial
        for letter in range(26):
            if current[letter] == letter:
                continue
            trial = current.copy()
            trial[trial[letter]] = trial[letter]
            trial[letter] = letter
            score = evaluate(trial)
            evaluations += 1
            if score > pass_best + minimum_gain:
                pass_best = score
                chosen = trial
        if chosen is None:
            break
        current = chosen
        best = pass_best
    return ClimbOutcome(
        score_per_letter=best / letters,
        unsteckered_score_per_letter=starting / letters,
        plugboard=tuple(current),
        pair_count=sum(1 for x in range(26) if current[x] > x),
        passes=passes,
        evaluations=evaluations,
    )


def run_climb_phases(
    phases: Sequence[str],
    objectives: Mapping[str, Any],
    letters: int,
    settings: Mapping[str, Any],
) -> tuple[list[int], list[dict[str, Any]], int]:
    """Run the configured objectives in order, each seeded by the previous one.

    Two phases, index of coincidence then n-grams, is the ordering Ostwald and
    Weierud describe, and the measurement behind it is stark: at 167 letters
    with a ten-pair stecker, climbing the n-gram score alone from the identity
    plugboard recovers the exact plugboard on 3 of 8 key draws, while seeding it
    with an index-of-coincidence climb recovers 8 of 8 for 1.6x the work.  With
    no steckers plugged the n-gram surface is nearly flat, because a single
    correct pair fixes too few letters to show up in bigrams; the index of
    coincidence responds to each correct pair restoring a slice of
    monoalphabetic structure.
    """

    plugboard = list(range(26))
    records: list[dict[str, Any]] = []
    evaluations = 0
    for objective in phases:
        if objective not in objectives:
            raise ValueError(f"unknown climb objective: {objective!r}")
        outcome = climb_stecker(
            objectives[objective],
            letters,
            int(settings["max_pairs"]),
            int(settings["max_passes"]),
            float(settings["minimum_gain"]),
            plugboard,
        )
        plugboard = list(outcome.plugboard)
        evaluations += outcome.evaluations
        records.append(
            {
                "objective": objective,
                "plugboard": enigma_fast.plugboard_pairs(plugboard),
                "plugboard_pairs": outcome.pair_count,
                "passes": outcome.passes,
                "evaluations": outcome.evaluations,
            }
        )
    return plugboard, records, evaluations


def body_direct_climb(
    traffic: Sequence[Traffic],
    rotor_order: Sequence[str],
    rings: Sequence[int],
    starts: Sequence[Sequence[int]],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    settings: Mapping[str, Any],
) -> tuple[ClimbOutcome, list[str]]:
    """Climb the stecker with the body start positions held fixed."""

    order = [enigma_fast.rotor_tables(name) for name in rotor_order]
    tables = [
        enigma_fast.position_permutations(order, rings, start, len(message.body), reflector)
        for message, start in zip(traffic, starts)
    ]
    bodies = [message.body for message in traffic]
    letters = sum(message.letters for message in traffic)
    score_decryption = scorer.score_decryption
    pairs = list(zip(tables, bodies))

    def ngram(plugboard: Sequence[int]) -> float:
        return sum(score_decryption(table, body, plugboard) for table, body in pairs)

    def coincidence(plugboard: Sequence[int]) -> float:
        # Pooled across the messages, weighted by length, so a date's messages
        # contribute in proportion to the evidence they carry.
        return sum(
            coincidence_of_decryption(table, body, plugboard) * len(body)
            for table, body in pairs
        ) / letters

    identity = list(range(26))
    plugboard, records, evaluations = run_climb_phases(
        settings["phases"],
        {"index_of_coincidence": coincidence, "ngram": ngram},
        letters,
        settings,
    )
    plaintexts = [
        enigma_fast.indices_to_text(
            enigma_fast.decrypt_with_tables(table, body, plugboard)
        )
        for table, body in pairs
    ]
    outcome = ClimbOutcome(
        score_per_letter=ngram(plugboard) / letters,
        unsteckered_score_per_letter=ngram(identity) / letters,
        plugboard=tuple(plugboard),
        pair_count=sum(1 for x in range(26) if plugboard[x] > x),
        passes=sum(record["passes"] for record in records),
        evaluations=evaluations,
        phases=tuple(records),
    )
    return outcome, plaintexts


def indicator_coupled_climb(
    traffic: Sequence[Traffic],
    ordering: str,
    rotor_order: Sequence[str],
    rings: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    settings: Mapping[str, Any],
) -> tuple[ClimbOutcome, list[str], list[str]]:
    """Climb the stecker with the message key re-derived at every evaluation.

    This is the formulation ``phase1.py`` implies.  It is implemented so the
    claim that it cannot be hill-climbed is a measurement rather than an
    assertion.
    """

    order = [enigma_fast.rotor_tables(name) for name in rotor_order]
    oriented = [message.oriented(ordering) for message in traffic]
    letters = sum(message.letters for message in traffic)

    def decrypt(plugboard: Sequence[int]) -> tuple[list[list[int]], list[tuple[int, ...]]]:
        plaintexts: list[list[int]] = []
        keys: list[tuple[int, ...]] = []
        for grundstellung, encrypted_key, body in oriented:
            recovered = enigma_fast.crypt_indices(
                order, rings, grundstellung, encrypted_key, plugboard, reflector
            )
            key = tuple(recovered)
            keys.append(key)
            plaintexts.append(
                enigma_fast.crypt_indices(order, rings, key, body, plugboard, reflector)
            )
        return plaintexts, keys

    def ngram(plugboard: Sequence[int]) -> float:
        return sum(scorer.score_indices(text) for text in decrypt(plugboard)[0])

    def coincidence(plugboard: Sequence[int]) -> float:
        counts = [0] * 26
        total = 0
        for text in decrypt(plugboard)[0]:
            for value in text:
                if value >= 0:
                    counts[value] += 1
                    total += 1
        return index_of_coincidence(counts, total)

    identity = list(range(26))
    # The coupled arm gets exactly the same two-phase climb as the direct arm,
    # so a failure here cannot be blamed on giving it a weaker optimiser.
    plugboard, records, evaluations = run_climb_phases(
        settings["phases"],
        {"index_of_coincidence": coincidence, "ngram": ngram},
        letters,
        settings,
    )
    outcome = ClimbOutcome(
        score_per_letter=ngram(plugboard) / letters,
        unsteckered_score_per_letter=ngram(identity) / letters,
        plugboard=tuple(plugboard),
        pair_count=sum(1 for x in range(26) if plugboard[x] > x),
        passes=sum(record["passes"] for record in records),
        evaluations=evaluations,
        phases=tuple(records),
    )
    plaintexts, keys = decrypt(outcome.plugboard)
    return (
        outcome,
        [enigma_fast.indices_to_text(text) for text in plaintexts],
        ["".join(chr(65 + value) for value in key) for key in keys],
    )
