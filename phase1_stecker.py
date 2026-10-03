#!/usr/bin/env python3
"""Phase 1 standard-Enigma sweeps and the stecker hill-climb.

``phase1.py`` established the Army indicator procedure and emitted a scope
certificate, but its committed certificate covers 120 daily keys with fixed
plugboards, so the standard-Enigma baseline has effectively never been run.
This module supplies the missing machinery and, more importantly, measures what
it can and cannot do before pointing it at the corpus.

Two formulations of the same attack are implemented, because they behave
completely differently and only one of them works:

``indicator_coupled``
    The formulation ``phase1.py`` uses.  The clear Grundstellung deciphers the
    message key, which fixes the body start position, so a daily key is just
    (wheel order, ring setting): 60 x 26^3 = 1,054,560 per date, which is
    exhaustively searchable.  The plugboard, however, sits inside the indicator
    machine as well as the body machine, so a wrong plugboard yields a wrong
    message key and therefore a body that is pure noise.  The score is a
    discontinuous function of the stecker and a hill-climb has nothing to
    follow.

``body_direct``
    The formulation Gillogly and Ostwald/Weierud use.  The body start position
    is searched instead of derived, so the plugboard's effect on the plaintext
    is smooth and local and the hill-climb works.  The indicator is then an
    independent confirmation rather than a search input.  The price is that the
    search space gains the start position.

Every number this module reports about the corpus is gated behind preflight
checks and preregistered known-key controls that must be recovered exactly; a
failed control makes zero target-search calls.

Method reference: Weierud and Sullivan, *Breaking German Army Ciphers*,
https://cryptocellar.org/pubs/mcts.pdf.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import hashlib
import itertools
import json
import os
import pathlib
import platform
import random
import statistics
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import enigma_fast
import phase1
import phase7
from enigma import A, EnigmaI
from resources import resolve_output, resource_root

# Inputs (configs, corpus, n-gram counts) live in the checkout or, once
# installed, in the share directory.  The code hashes and the git record
# describe the modules actually running, which sit beside this file in either
# case.
ROOT = resource_root()
CODE_ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"
CONFIG_SCHEMA = "enigma-attack.phase1-stecker-config/v1"
RESULT_SCHEMA = "enigma-attack.phase1-stecker-result/v1"

# The indicator is two trigrams.  ``phase1.py:139`` fixes the first as the clear
# Grundstellung and the second as the enciphered message key.  That is the usual
# 1940+ Army convention, but a transcription could have recorded them the other
# way round, so both orderings are searched wherever the indicator is used.
INDICATOR_ORDERINGS = {
    "grundstellung_first": (0, 1),
    "message_key_first": (1, 0),
}


def resolve_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else ROOT / path


def describe_path(path: pathlib.Path) -> str:
    """Repo-relative when the path is inside the checkout, absolute otherwise.

    ``--config`` accepts any readable path, so a configuration outside the
    checkout is legitimate.  Recording it with ``relative_to`` would raise, and
    the record is assembled after the experiment, so the failure would land
    after a run that can take hours and leave no artifact at all.
    """

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class FastNgramScorer:
    """Flat-table restatement of :class:`phase7.PublishedNgramScorer`.

    The weighted bigram term is folded into the trigram table so a letter costs
    one list index and one add.  For a sequence ``x`` with no mask,

        sum_t w2*log2[x_t x_t+1] + sum_t w3*log3[x_t x_t+1 x_t+2]
      = w2*log2[x_0 x_1] + sum_t (w3*log3[x_t x_t+1 x_t+2] + w2*log2[x_t+1 x_t+2])

    which is the same set of n-grams in a different summation order.
    :meth:`parity_report` checks the restatement against Phase 7 rather than
    asserting it.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.reference = phase7.PublishedNgramScorer(config)
        bigram_weight = float(config["bigram_weight"])
        bigram_table = self.reference.tables[2]
        bigram_floor = self.reference.floors[2]
        trigram_weight = float(config["trigram_weight"])
        trigram_table = self.reference.tables[3]
        trigram_floor = self.reference.floors[3]

        self.bigram = [0.0] * 676
        for first in range(26):
            for second in range(26):
                key = chr(65 + first) + chr(65 + second)
                self.bigram[first * 26 + second] = bigram_weight * bigram_table.get(
                    key, bigram_floor
                )
        self.combined = [0.0] * 17576
        for first in range(26):
            for second in range(26):
                base = first * 676 + second * 26
                prefix = chr(65 + first) + chr(65 + second)
                for third in range(26):
                    key = prefix + chr(65 + third)
                    self.combined[base + third] = (
                        trigram_weight * trigram_table.get(key, trigram_floor)
                        + self.bigram[second * 26 + third]
                    )

    def score_indices(self, indices: Sequence[int]) -> float:
        """Score index data in which ``-1`` masks an unreadable source letter."""

        bigram = self.bigram
        combined = self.combined
        total = 0.0
        previous = -1
        cursor = -1
        for value in indices:
            if value < 0:
                previous = -1
                cursor = -1
                continue
            if previous < 0:
                previous = value
                continue
            if cursor < 0:
                total += bigram[previous * 26 + value]
                cursor = previous * 676 + value * 26
            else:
                total += combined[cursor + value]
                cursor = ((cursor % 676) + value) * 26
            previous = value
        return total

    def score_decryption(
        self, table: Sequence[int], body: Sequence[int], plugboard: Sequence[int]
    ) -> float:
        """Decrypt and score in one pass: the hill-climb's inner loop.

        ``table`` is the flattened per-position permutation from
        :func:`enigma_fast.position_permutations`, so this never re-runs the
        stepping.  Identical to ``score_indices(decrypt_with_tables(...))``,
        which :meth:`parity_report` checks.
        """

        bigram = self.bigram
        combined = self.combined
        total = 0.0
        previous = -1
        cursor = -1
        offset = 0
        for value in body:
            if value < 0:
                previous = -1
                cursor = -1
                offset += 26
                continue
            letter = plugboard[table[offset + plugboard[value]]]
            offset += 26
            if previous < 0:
                previous = letter
                continue
            if cursor < 0:
                total += bigram[previous * 26 + letter]
                cursor = previous * 676 + letter * 26
            else:
                total += combined[cursor + letter]
                cursor = ((cursor % 676) + letter) * 26
            previous = letter
        return total

    def score_text(self, text: str) -> float:
        return self.score_indices(enigma_fast.text_to_indices(text))

    def parity_report(self, seed: int, samples: int, tolerance: float) -> dict[str, Any]:
        """Check the fast scorer and the fused path against Phase 7."""

        generator = random.Random(seed)
        worst_reference = 0.0
        worst_fusion = 0.0
        mismatches: list[dict[str, Any]] = []
        for _ in range(samples):
            length = generator.randrange(3, 200)
            letters = [generator.choice(A) for _ in range(length)]
            for _ in range(generator.randrange(0, 3)):
                letters[generator.randrange(length)] = "?"
            text = "".join(letters)
            expected = self.reference.score(text)[0]
            actual = self.score_indices(enigma_fast.text_to_indices(text))
            worst_reference = max(worst_reference, abs(expected - actual))

            # The fused path must agree with the split path on real machine
            # output, not only on the table algebra.
            order = [
                enigma_fast.rotor_tables(name)
                for name in generator.sample(["I", "II", "III", "IV", "V"], 3)
            ]
            rings = tuple(generator.randrange(26) for _ in range(3))
            start = tuple(generator.randrange(26) for _ in range(3))
            body = enigma_fast.text_to_indices(text)
            plugboard = list(range(26))
            for index in range(0, 2 * generator.randrange(0, 11), 2):
                pool = [x for x in range(26) if plugboard[x] == x]
                if len(pool) < 2:
                    break
                first, second = generator.sample(pool, 2)
                plugboard[first], plugboard[second] = second, first
            table = enigma_fast.position_permutations(order, rings, start, len(body))
            split = self.score_indices(
                enigma_fast.decrypt_with_tables(table, body, plugboard)
            )
            fused = self.score_decryption(table, body, plugboard)
            worst_fusion = max(worst_fusion, abs(split - fused))

            if abs(expected - actual) > tolerance * max(1.0, abs(expected)) or abs(
                split - fused
            ) > tolerance * max(1.0, abs(split)):
                mismatches.append(
                    {
                        "text": text,
                        "phase7": expected,
                        "fast": actual,
                        "split": split,
                        "fused": fused,
                    }
                )
        return {
            "reference": "phase7.PublishedNgramScorer",
            "seed": seed,
            "samples": samples,
            "relative_tolerance": tolerance,
            "worst_absolute_difference_vs_phase7": worst_reference,
            "worst_absolute_difference_fused_vs_split": worst_fusion,
            "mismatches": mismatches,
            "passed": not mismatches,
            "note": (
                "The scorers sum the same n-gram terms in different orders, so "
                "they agree to floating-point association rather than bit for bit."
            ),
        }


def index_of_coincidence(counts: Sequence[int], total: int) -> float:
    if total < 2:
        return 0.0
    return sum(count * (count - 1) for count in counts) / (total * (total - 1))


def letter_counts(indices: Sequence[int]) -> tuple[list[int], int]:
    counts = [0] * 26
    total = 0
    for value in indices:
        if value >= 0:
            counts[value] += 1
            total += 1
    return counts, total


# ---------------------------------------------------------------------------
# Traffic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Traffic:
    """One message reduced to the index form the kernel consumes."""

    designator: str
    first_trigram: tuple[int, ...]
    second_trigram: tuple[int, ...]
    body: tuple[int, ...]

    def oriented(
        self, ordering: str
    ) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
        grund, encrypted = INDICATOR_ORDERINGS[ordering]
        trigrams = (self.first_trigram, self.second_trigram)
        return trigrams[grund], trigrams[encrypted], self.body

    @property
    def letters(self) -> int:
        return sum(1 for value in self.body if value >= 0)


def traffic_from_corpus(
    corpus_path: pathlib.Path, date: str, designators: Sequence[str]
) -> list[Traffic]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    by_designator = {record["designator"]: record for record in corpus["messages"]}
    traffic: list[Traffic] = []
    for designator in designators:
        record = by_designator[designator]
        if record["date"] != date:
            raise ValueError(f"{designator} is not from {date}")
        traffic.append(
            Traffic(
                designator=designator,
                first_trigram=enigma_fast.text_to_indices(record["indicator"][0]),
                second_trigram=enigma_fast.text_to_indices(record["indicator"][1]),
                body=enigma_fast.text_to_indices(record["ciphertext"]),
            )
        )
    return traffic


def normalize_plaintext(raw: str, length: int | None = None) -> str:
    text = "".join(raw.split()).upper()
    if any(letter not in A for letter in text):
        raise ValueError("control plaintext must be A-Z after whitespace removal")
    if length is not None:
        if len(text) < length:
            raise ValueError(f"control plaintext is shorter than the requested {length}")
        text = text[:length]
    return text


def random_plugboard(generator: random.Random, pairs: int) -> str:
    letters = generator.sample(list(A), 2 * pairs)
    return " ".join(letters[index] + letters[index + 1] for index in range(0, 2 * pairs, 2))


def encipher_control(spec: Mapping[str, Any]) -> tuple[list[Traffic], dict[str, Any]]:
    """Encipher known plaintexts under a known key with the reference machine.

    The control ciphertext is produced by ``enigma.EnigmaI`` while the attack
    runs on ``enigma_fast``.  A control that only round-trips through the fast
    kernel would pass even if the kernel and the search shared a fault.
    """

    key = spec["key"]
    rotors = tuple(name.upper() for name in key["rotor_order"])
    rings = key["rings"].upper()
    plugboard = key.get("plugboard", "")
    ordering = spec.get("indicator_ordering", "grundstellung_first")
    grund_index, encrypted_index = INDICATOR_ORDERINGS[ordering]

    traffic: list[Traffic] = []
    rendered: list[dict[str, Any]] = []
    plaintexts: list[str] = []
    for message in spec["messages"]:
        plaintext = normalize_plaintext(message["plaintext"], message.get("length"))
        grundstellung = message["grundstellung"].upper()
        message_key = message["message_key"].upper()
        encrypted_key = EnigmaI(
            rotors=rotors, rings=rings, positions=grundstellung, plugboard=plugboard
        ).crypt(message_key)
        ciphertext = EnigmaI(
            rotors=rotors, rings=rings, positions=message_key, plugboard=plugboard
        ).crypt(plaintext)
        transcribed = ["", ""]
        transcribed[grund_index] = grundstellung
        transcribed[encrypted_index] = encrypted_key
        traffic.append(
            Traffic(
                designator=message["designator"],
                first_trigram=enigma_fast.text_to_indices(transcribed[0]),
                second_trigram=enigma_fast.text_to_indices(transcribed[1]),
                body=enigma_fast.text_to_indices(ciphertext),
            )
        )
        plaintexts.append(plaintext)
        rendered.append(
            {
                "designator": message["designator"],
                "length": len(plaintext),
                "indicator": transcribed,
                "true_message_key": message_key,
                "plaintext_sha256": sha256_text(plaintext),
            }
        )
    truth = {
        "rotor_order_left_to_right": list(rotors),
        "rings": rings,
        "plugboard": enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard)),
        "plugboard_pairs": len(plugboard.split()),
        "indicator_ordering": ordering,
        "messages": rendered,
    }
    return traffic, {"truth": truth, "plaintexts": plaintexts}


# ---------------------------------------------------------------------------
# Stecker hill-climb
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Stage 1: the indicator-coupled index-of-coincidence sweep
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SweepCandidate:
    ordering: str
    rotor_order: tuple[str, ...]
    rings: tuple[int, int, int]
    statistic: float
    message_keys: tuple[tuple[int, ...], ...]

    def rings_text(self) -> str:
        return "".join(chr(65 + value) for value in self.rings)


def ring_space(specification: Any) -> list[tuple[int, int, int]]:
    if specification == "all":
        return list(itertools.product(range(26), repeat=3))
    if isinstance(specification, list):
        return [
            tuple(ord(letter) - 65 for letter in value.upper())  # type: ignore[misc]
            for value in specification
        ]
    raise ValueError(f"unsupported ring specification: {specification!r}")


def rotor_order_space(specification: Any, wheel_set: Sequence[str]) -> list[tuple[str, ...]]:
    if specification == "all_permutations":
        return [tuple(order) for order in itertools.permutations(wheel_set, 3)]
    if isinstance(specification, list):
        return [tuple(name.upper() for name in order) for order in specification]
    raise ValueError(f"unsupported rotor-order specification: {specification!r}")


def indicator_ic_sweep(
    traffic: Sequence[Traffic],
    ordering: str,
    rotor_orders: Sequence[tuple[str, ...]],
    rings: Sequence[tuple[int, int, int]],
    reflector: Sequence[int],
    keep: int,
) -> tuple[list[SweepCandidate], int]:
    """Rank indicator-coupled daily keys by the pooled index of coincidence.

    Messages from one date share a daily key, so their decryptions are pooled;
    that is the strongest form of the statistic available here.
    """

    oriented = [message.oriented(ordering) for message in traffic]
    total = sum(message.letters for message in traffic)
    retained: list[tuple[float, int, SweepCandidate]] = []
    threshold = float("-inf")
    serial = 0
    evaluated = 0
    for names in rotor_orders:
        order = [enigma_fast.rotor_tables(name) for name in names]
        for ring_setting in rings:
            counts = [0] * 26
            keys = enigma_fast.unsteckered_date_counts(
                order, ring_setting, oriented, reflector, counts
            )
            statistic = index_of_coincidence(counts, total)
            evaluated += 1
            serial += 1
            if len(retained) >= keep and statistic <= threshold:
                continue
            retained.append(
                (
                    statistic,
                    serial,
                    SweepCandidate(
                        ordering=ordering,
                        rotor_order=tuple(names),
                        rings=tuple(ring_setting),  # type: ignore[arg-type]
                        statistic=statistic,
                        message_keys=tuple(tuple(key) for key in keys),
                    ),
                )
            )
            if len(retained) >= 4 * keep:
                # Compacting on a fixed multiple keeps the survivor list a pure
                # function of the traversal order, which a heap of floats with
                # ties would not be.
                retained.sort(key=lambda item: (-item[0], item[1]))
                del retained[keep:]
                threshold = retained[-1][0]
    retained.sort(key=lambda item: (-item[0], item[1]))
    del retained[keep:]
    return [item[2] for item in retained], evaluated


# ---------------------------------------------------------------------------
# Stage 1 alternative: the body-direct sweep
# ---------------------------------------------------------------------------


_WORKER: dict[str, Any] = {}


def _worker_init(scorer_config: dict[str, Any], body: list[int], settings: dict[str, Any],
                 rings: list[int], reflector: list[int]) -> None:
    _WORKER["scorer"] = FastNgramScorer(scorer_config)
    _WORKER["body"] = body
    _WORKER["settings"] = settings
    _WORKER["rings"] = rings
    _WORKER["reflector"] = reflector


def _worker_chunk(chunk: tuple[tuple[str, ...], list[tuple[int, int, int]]]) -> list[dict[str, Any]]:
    names, starts = chunk
    scorer = _WORKER["scorer"]
    body = _WORKER["body"]
    settings = _WORKER["settings"]
    rings = _WORKER["rings"]
    reflector = _WORKER["reflector"]
    order = [enigma_fast.rotor_tables(name) for name in names]
    letters = sum(1 for value in body if value >= 0)
    phases = list(settings["phases"])
    results: list[dict[str, Any]] = []
    for start in starts:
        table = enigma_fast.position_permutations(order, rings, start, len(body), reflector)
        plugboard, _, evaluations = run_climb_phases(
            phases,
            {
                "index_of_coincidence": lambda pb: coincidence_of_decryption(table, body, pb),
                "ngram": lambda pb: scorer.score_decryption(table, body, pb),
            },
            letters,
            settings,
        )
        results.append(
            {
                "score_per_letter": scorer.score_decryption(table, body, plugboard) / letters,
                "rotor_order": list(names),
                "start": list(start),
                "plugboard": list(plugboard),
                "plugboard_pairs": sum(1 for x in range(26) if plugboard[x] > x),
                "evaluations": evaluations,
            }
        )
    return results


def body_direct_sweep(
    message: Traffic,
    rotor_orders: Sequence[tuple[str, ...]],
    rings: Sequence[int],
    starts: Sequence[tuple[int, int, int]],
    scorer_config: Mapping[str, Any],
    reflector: Sequence[int],
    settings: Mapping[str, Any],
    keep: int,
    jobs: int,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    """Full stecker climb at every rotor setting of a declared slice.

    There is no cheap pre-filter.  The index of coincidence does not separate
    the true setting under a ten-pair stecker at these lengths, and a truncated
    climb does not either, so every setting in the slice costs a converged
    climb.  That is the measured reason this sweep is expensive.
    """

    chunks = [(names, list(starts)) for names in rotor_orders]
    collected: list[dict[str, Any]] = []
    if jobs > 1:
        with futures.ProcessPoolExecutor(
            max_workers=jobs,
            initializer=_worker_init,
            initargs=(
                dict(scorer_config),
                list(message.body),
                dict(settings),
                list(rings),
                list(reflector),
            ),
        ) as pool:
            # ``map`` preserves input order, so the merged list does not depend
            # on which worker finished first.
            for block in pool.map(_worker_chunk, chunks):
                collected.extend(block)
    else:
        _worker_init(
            dict(scorer_config),
            list(message.body),
            dict(settings),
            list(rings),
            list(reflector),
        )
        for chunk in chunks:
            collected.extend(_worker_chunk(chunk))

    evaluated = len(collected)
    scores = [row["score_per_letter"] for row in collected]
    # Ranking ties break on generation order, so the retained list is a pure
    # function of the declared slice and not of worker scheduling.
    indexed = sorted(
        enumerate(collected), key=lambda item: (-item[1]["score_per_letter"], item[0])
    )[:keep]
    ranked = [
        {
            "rank": position + 1,
            "score_per_letter": round(row["score_per_letter"], 9),
            "rotor_order_left_to_right": row["rotor_order"],
            "rings": "".join(chr(65 + value) for value in rings),
            "start_position": "".join(chr(65 + value) for value in row["start"]),
            "plugboard": enigma_fast.plugboard_pairs(row["plugboard"]),
            "plugboard_pairs": row["plugboard_pairs"],
            "_plugboard": row["plugboard"],
        }
        for position, (_, row) in enumerate(indexed)
    ]
    distribution = {
        "mean_score_per_letter": round(statistics.fmean(scores), 9),
        "sd_score_per_letter": round(statistics.pstdev(scores), 9),
        "max_score_per_letter": round(max(scores), 9),
        "top_z_score": round(
            (max(scores) - statistics.fmean(scores)) / statistics.pstdev(scores), 6
        )
        if statistics.pstdev(scores) > 0
        else None,
    }
    return ranked, evaluated, distribution


# ---------------------------------------------------------------------------
# Calibrations
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Controls, preflight and nulls
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


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


def run_indicator_sweep(
    config: Mapping[str, Any],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    traffic: Sequence[Traffic],
) -> dict[str, Any]:
    rotor_orders = rotor_order_space(
        config["machine"]["rotor_orders"], config["machine"]["wheel_set"]
    )
    rings = ring_space(config["machine"]["ring_settings"])
    keep = int(config["sweep"]["keep"])
    climb_limit = int(config["sweep"]["climb_limit"])
    arms: list[dict[str, Any]] = []
    for ordering in config["indicator_orderings"]:
        started = time.monotonic()
        survivors, evaluated = indicator_ic_sweep(
            traffic, ordering, rotor_orders, rings, reflector, keep
        )
        sweep_seconds = time.monotonic() - started
        started = time.monotonic()
        climbed: list[dict[str, Any]] = []
        for candidate in survivors[:climb_limit]:
            outcome, plaintexts, keys = indicator_coupled_climb(
                traffic,
                ordering,
                candidate.rotor_order,
                candidate.rings,
                scorer,
                reflector,
                config["climb"],
            )
            climbed.append(
                {
                    "rotor_order_left_to_right": list(candidate.rotor_order),
                    "rings": candidate.rings_text(),
                    "index_of_coincidence": round(candidate.statistic, 9),
                    "score_per_letter": round(outcome.score_per_letter, 9),
                    "plugboard": enigma_fast.plugboard_pairs(outcome.plugboard),
                    "message_keys": keys,
                    "plaintext_prefixes": [text[:60] for text in plaintexts],
                }
            )
        climbed.sort(
            key=lambda row: (
                -row["score_per_letter"],
                row["rotor_order_left_to_right"],
                row["rings"],
            )
        )
        arms.append(
            {
                "indicator_ordering": ordering,
                "evaluated_daily_keys": evaluated,
                "sweep_seconds": round(sweep_seconds, 3),
                "climb_seconds": round(time.monotonic() - started, 3),
                "retained": len(survivors),
                "climbed": len(climbed),
                "top_index_of_coincidence": [
                    round(candidate.statistic, 9) for candidate in survivors[:10]
                ],
                "best_by_index_of_coincidence": {
                    "rotor_order_left_to_right": list(survivors[0].rotor_order),
                    "rings": survivors[0].rings_text(),
                    "index_of_coincidence": round(survivors[0].statistic, 9),
                    "message_keys": [
                        "".join(chr(65 + v) for v in key)
                        for key in survivors[0].message_keys
                    ],
                },
                "best_after_climb": climbed[0] if climbed else None,
            }
        )
    return {
        "formulation": "indicator_coupled",
        "space_is_complete": (
            len(rotor_orders) == 60
            and len(rings) == 17576
            and len(config["indicator_orderings"]) == 2
        ),
        "arms": arms,
        "evaluated_daily_keys": sum(arm["evaluated_daily_keys"] for arm in arms),
    }


def run_body_direct_sweep(
    config: Mapping[str, Any],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    traffic: Sequence[Traffic],
    jobs: int,
) -> dict[str, Any]:
    settings = config["body_direct_sweep"]
    by_designator = {message.designator: message for message in traffic}
    message = by_designator[settings["message"]]
    rotor_orders = rotor_order_space(
        config["machine"]["rotor_orders"], config["machine"]["wheel_set"]
    )
    rings = tuple(ord(letter) - 65 for letter in settings["rings"].upper())
    start_space = [
        (left, middle, right)
        for left in resolve_axis(settings["start_left"])
        for middle in resolve_axis(settings["start_middle"])
        for right in resolve_axis(settings["start_right"])
    ]
    started = time.monotonic()
    ranked, evaluated, distribution = body_direct_sweep(
        message,
        rotor_orders,
        rings,
        start_space,
        config["scorer"],
        reflector,
        config["climb"],
        int(settings["keep"]),
        jobs,
    )
    elapsed = time.monotonic() - started

    # Independent amplifier for the retained candidates.  The sweep climbs one
    # message; a candidate that is actually the daily key must also decipher the
    # other two messages of the date once its plugboard is fed back through the
    # clear indicator, which the sweep never used.  A wrong candidate gains
    # nothing from the extra letters, so the pooled score separates a real hit
    # from the best of the slice's noise far more sharply than the single-message
    # score can.
    #
    # The confirmation recovers the ring setting rather than reusing the held
    # one.  The sweep absorbs the left and middle rings into the start position
    # it searches, so the held value describes the parameterization and not the
    # daily key, and the indicator's fixed clear Grundstellung does not share
    # that freedom.  Deciphering the indicator under the held rings would test
    # the wrong key and could dismiss a genuine hit.
    for candidate in ranked:
        candidate["indicator_confirmation"] = confirm_against_date(
            traffic,
            candidate.pop("_plugboard"),
            candidate["rotor_order_left_to_right"],
            rings,
            scorer,
            reflector,
            config["indicator_orderings"],
            swept_message=message,
            swept_start=tuple(
                ord(letter) - 65 for letter in candidate["start_position"]
            ),
        )
    confirmation_scores = [
        candidate["indicator_confirmation"]["best_pooled_score_per_letter"]
        for candidate in ranked
    ]

    # Coverage is stated against the space that actually has to be searched,
    # not against the slice that was chosen, so the number cannot flatter the
    # run by redefining the denominator.
    relevant = 60 * 26**4
    return {
        "formulation": "body_direct",
        "message": message.designator,
        "message_length": len(message.body),
        "rings_held_at": settings["rings"].upper(),
        "rotor_orders": len(rotor_orders),
        "start_positions": len(start_space),
        "evaluated_settings": evaluated,
        "seconds": round(elapsed, 3),
        "seconds_per_setting": round(elapsed / max(evaluated, 1), 6),
        "jobs": jobs,
        "score_distribution_over_slice": distribution,
        "indicator_confirmation": {
            "best_pooled_score_per_letter": max(confirmation_scores),
            "mean_pooled_score_per_letter": round(
                statistics.fmean(confirmation_scores), 9
            ),
            "candidates_with_a_compatible_ring_setting": sum(
                1
                for candidate in ranked
                if candidate["indicator_confirmation"]["compatible_ring_settings"]
            ),
            "ring_recovery": (
                "The sweep absorbs the left and middle ring settings into the "
                "start position it searches, so the held AAA is the "
                "parameterization and not a claim about the daily key. The "
                "clear Grundstellung the indicator uses does not share that "
                "freedom, so for each candidate every left and middle ring "
                "setting that reproduces the swept body through the indicator "
                "is scored and the best is reported. The right-hand ring is "
                "fixed because it moves the turnover inside the message, which "
                "is what the declared slice holds."
            ),
            "method": (
                "For each retained candidate the recovered plugboard and a "
                "recovered ring setting are used with the clear indicator to "
                "derive all three message keys, and the whole date is scored. "
                "The sweep itself "
                "never reads the indicator, so this is an independent check."
            ),
        },
        "coverage": {
            "searched_settings": evaluated,
            "reducible_space_settings": relevant,
            "reducible_space_definition": (
                "60 wheel orders x 26^4, the parameters a message this short can "
                "distinguish: the left and middle wheel offsets, and the right "
                "wheel's offset and absolute position. It assumes the left wheel "
                "does not step during the message, which holds for about "
                "three quarters of start positions at this length."
            ),
            "fraction_searched": round(evaluated / relevant, 9),
            "measured_wall_seconds_per_setting_at_this_parallelism": round(
                elapsed / max(evaluated, 1), 6
            ),
            "jobs_used": jobs,
            "projected_wall_hours_for_reducible_space_at_this_parallelism": round(
                relevant * (elapsed / max(evaluated, 1)) / 3600, 1
            ),
            "projected_core_hours_for_reducible_space": round(
                # Wall-clock-per-setting already reflects ``jobs`` workers
                # sharing the run, so recovering true core-hours multiplies
                # back by the worker count rather than dividing by it. An
                # earlier version of this field named itself "core-hours"
                # while actually reporting wall-clock hours at this
                # parallelism, understating the true cost by the worker count.
                relevant * (elapsed / max(evaluated, 1)) * max(jobs, 1) / 3600,
                1,
            ),
        },
        "top_candidates": ranked,
    }


def resolve_axis(specification: Any) -> list[int]:
    if specification == "all":
        return list(range(26))
    if isinstance(specification, str):
        return [ord(letter) - 65 for letter in specification.upper()]
    if isinstance(specification, list):
        return [ord(str(value).upper()) - 65 for value in specification]
    raise ValueError(f"unsupported start-position axis: {specification!r}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_experiment(
    config: Mapping[str, Any],
    config_path: pathlib.Path,
    argv: Sequence[str],
    jobs: int,
) -> dict[str, Any]:
    started_at = dt.datetime.now(dt.timezone.utc)
    started_clock = time.monotonic()
    corpus_path = resolve_path(config["corpus"])
    scorer = FastNgramScorer(config["scorer"])
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])

    preflight = run_preflight(config, scorer)
    controls: list[dict[str, Any]] = []
    controls_passed = False
    if preflight["passed"]:
        for spec in config["positive_controls"]:
            controls.append(evaluate_positive_control(spec, config, scorer, reflector))
        controls_passed = bool(controls) and all(row["passed"] for row in controls)

    mode = config["mode"]
    body: dict[str, Any] | None = None
    if not preflight["passed"]:
        status = "blocked_by_preflight"
    elif not controls_passed:
        status = "blocked_by_positive_control"
    else:
        status = "complete"
        if mode == "calibration":
            body = run_calibration(config, scorer, reflector)
        else:
            traffic = traffic_from_corpus(
                corpus_path, config["target"]["date"], config["target"]["messages"]
            )
            if mode == "indicator_sweep":
                body = run_indicator_sweep(config, scorer, reflector, traffic)
            elif mode == "body_direct_sweep":
                body = run_body_direct_sweep(config, scorer, reflector, traffic, jobs)
            else:
                raise ValueError(f"unsupported mode: {mode!r}")

    return {
        "schema": RESULT_SCHEMA,
        "experiment_id": config["experiment_id"],
        "mode": mode,
        "status": status,
        "accepted_break": False,
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": time.monotonic() - started_clock,
        "configuration": {
            "path": describe_path(config_path),
            "sha256": sha256_file(config_path),
            "arguments": list(argv),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            **git_state(),
        },
        "inputs": {
            "corpus_sha256": sha256_file(corpus_path),
            "bigram_counts_sha256": sha256_file(
                resolve_path(config["scorer"]["bigram_counts"])
            ),
            "trigram_counts_sha256": sha256_file(
                resolve_path(config["scorer"]["trigram_counts"])
            ),
            "code_sha256": {
                name: sha256_file(CODE_ROOT / name)
                for name in (
                    "enigma.py",
                    "enigma_fast.py",
                    "phase1.py",
                    "phase1_stecker.py",
                    "phase7.py",
                )
            },
        },
        "preflight": preflight,
        "positive_controls": {
            "evaluated": controls,
            "passed": controls_passed,
            "gate": (
                "A failed control makes zero target-search calls, so a target "
                "number can never come from a pipeline that cannot recover a key "
                "it was handed."
            ),
        },
        "result": body,
        "limitations": config["limitations"],
    }


def _git_output(*arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=CODE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout


def git_state() -> dict[str, Any]:
    """The commit and whether the tree differs from it.

    ``git rev-parse HEAD`` alone names the last commit, not the code that ran: an
    artifact produced from uncommitted changes (or from a module that was not yet
    tracked) records a commit that never contained that code.  ``git status
    --porcelain`` lists modified and untracked entries, so ``git_dirty`` marks
    exactly the runs whose commit cannot be trusted to reproduce them.  Both are
    ``None`` when git is unavailable, which is distinct from a clean tree.
    """

    commit = _git_output("rev-parse", "HEAD")
    status = _git_output("status", "--porcelain")
    return {
        "git_commit": commit.strip() if commit is not None else "unavailable",
        "git_dirty": bool(status.strip()) if status is not None else None,
        "git_dirty_entry_count": (
            len(status.splitlines()) if status is not None else None
        ),
    }


def load_config(path: pathlib.Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"unsupported configuration schema: {config.get('schema')!r}")
    if config["mode"] not in {"calibration", "indicator_sweep", "body_direct_sweep"}:
        raise ValueError(f"unsupported mode: {config['mode']!r}")
    for ordering in config.get("indicator_orderings", []):
        if ordering not in INDICATOR_ORDERINGS:
            raise ValueError(f"unknown indicator ordering: {ordering!r}")
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="worker processes for the body-direct sweep; results are merged in "
        "input order, so the artifact does not depend on this value",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config_path = resolve_path(arguments.config).resolve()
    config = load_config(config_path)
    result = run_experiment(
        config, config_path, sys.argv[1:] if argv is None else argv, max(1, arguments.jobs)
    )
    output = resolve_output(arguments.output or config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} mode={result['mode']} status={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
