"""N-gram and index-of-coincidence scoring for the Phase 1 stecker search.

:class:`FastNgramScorer` is the hill-climb's inner loop.  It restates Phase 7's
validated published-count scorer as flat tables and checks the restatement
against Phase 7 rather than asserting it.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

import enigma_fast
import phase7
from enigma import A


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
