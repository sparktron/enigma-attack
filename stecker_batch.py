"""Batched numpy stecker climb, a drop-in for ``stecker_climb.climb_stecker``.

Each pass of the reference climb scores about 350 candidate plugboards one at a
time in pure Python.  Here every candidate of a pass is built as one ``(K, 26)``
array, then decrypted and scored at once through the precomputed ``(n, 26)``
position table.  The move set, the move order, the pair limit and the
minimum-gain rule are the reference's, and the candidate chosen at the end of a
pass is found by the same running-best scan, so the climb ends on the same
plugboard.  ``stecker_controls.run_preflight`` checks that on seeded samples
before any search, the way it checks the fast kernel and the fast scorer, and
the pure-Python climb stays the reference: this module is an optimisation of it,
not a second definition.

numpy is optional.  Without it ``available()`` is false and callers keep the
reference climb, so the stdlib-only install still works.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

try:  # the project has no runtime dependency; this one is optional
    import numpy as np
except ImportError:  # pragma: no cover - exercised by the fallback test
    np = None


def available() -> bool:
    return np is not None


class BatchedClimber:
    """Both climb objectives for one message, batched over candidate plugboards.

    Built once per message and reused for every rotor setting, since everything
    but the position table is a function of the ciphertext alone.
    """

    def __init__(
        self,
        bigram: Sequence[float],
        combined: Sequence[float],
        body: Sequence[int],
        settings: Mapping[str, Any],
    ) -> None:
        if np is None:
            raise RuntimeError("the batched climb needs numpy, which is not installed")
        self.settings = settings
        self.bigram = np.asarray(bigram, dtype=np.float64)
        self.combined = np.asarray(combined, dtype=np.float64)
        length = len(body)
        cipher = np.asarray(body, dtype=np.int64)
        valid = cipher >= 0
        self.valid = valid
        self.cipher = np.where(valid, cipher, 0)
        self.rows = np.arange(length)
        previous = np.r_[False, valid[:-1]]
        before = np.r_[False, False, valid[:-2]]
        # A '?' resets the n-gram chain exactly as ``FastNgramScorer`` does: the
        # first letter after it scores nothing, the second a bigram only.
        self.trigram_positions = np.nonzero(valid & previous & before)[0]
        self.bigram_positions = np.nonzero(valid & previous & ~before)[0]
        self.letters = int(valid.sum())
        self.length = length
        self.first, self.second = np.triu_indices(26, k=1)
        self.alphabet = np.arange(26)

    def _decrypt(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        stepped = table[self.rows, boards[:, self.cipher]]
        return np.take_along_axis(boards, stepped, axis=1)

    def _ngram(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        text = self._decrypt(boards, table)
        t = self.trigram_positions
        total = self.combined[text[:, t - 2] * 676 + text[:, t - 1] * 26 + text[:, t]].sum(axis=1)
        b = self.bigram_positions
        if len(b):
            total = total + self.bigram[text[:, b - 1] * 26 + text[:, b]].sum(axis=1)
        return total

    def _coincidence(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        text = self._decrypt(boards, table)[:, self.valid]
        k = text.shape[0]
        counts = np.bincount(
            (text + 26 * np.arange(k)[:, None]).ravel(), minlength=26 * k
        ).reshape(k, 26)
        n = self.letters
        coincidence = (counts * (counts - 1)).sum(axis=1) / (n * (n - 1))
        # The weight ``body_direct_climb`` applies when it pools messages.
        return coincidence * self.length / self.letters

    def _candidates(self, current: "np.ndarray", max_pairs: int) -> "np.ndarray":
        """Every move ``climb_stecker`` would try from ``current``, in its order."""

        keep = current[self.first] != self.second
        first, second = self.first[keep], self.second[keep]
        rows = np.arange(len(first))
        boards = np.tile(current, (len(first), 1))
        partner_first, partner_second = current[first], current[second]
        boards[rows, partner_first] = partner_first
        boards[rows, partner_second] = partner_second
        boards[rows, first] = second
        boards[rows, second] = first
        boards = boards[(boards > self.alphabet).sum(axis=1) <= max_pairs]

        plugged = self.alphabet[current != self.alphabet]
        unplug = np.tile(current, (len(plugged), 1))
        rows = np.arange(len(plugged))
        unplug[rows, current[plugged]] = current[plugged]
        unplug[rows, plugged] = plugged
        return np.vstack([boards, unplug])

    def _climb(self, objective, table: "np.ndarray", initial: Sequence[int]) -> tuple[list[int], int]:
        max_pairs = int(self.settings["max_pairs"])
        minimum_gain = float(self.settings["minimum_gain"])
        current = np.asarray(initial, dtype=np.int64)
        best = float(objective(current[None, :], table)[0])
        evaluations = 1
        for _ in range(int(self.settings["max_passes"])):
            trials = self._candidates(current, max_pairs)
            scores = objective(trials, table).tolist()
            evaluations += len(scores)
            # The reference keeps a running best and replaces it only by more
            # than the minimum gain, so the chosen move is the last one that
            # cleared the running best, not necessarily the global maximum.
            running, chosen = best, None
            for index, score in enumerate(scores):
                if score > running + minimum_gain:
                    running, chosen = score, index
            if chosen is None:
                break
            current, best = trials[chosen], running
        return current.tolist(), evaluations

    def climb(self, flat_table: Sequence[int]) -> tuple[list[int], int]:
        """Run the configured phases at one rotor setting.

        ``flat_table`` is the list ``enigma_fast.position_permutations`` returns.
        Returns the final plugboard and the number of plugboards evaluated, which
        equals the reference's count.
        """

        table = np.asarray(flat_table, dtype=np.int64).reshape(self.length, 26)
        objectives = {"index_of_coincidence": self._coincidence, "ngram": self._ngram}
        plugboard: list[int] = list(range(26))
        evaluations = 0
        for phase in self.settings["phases"]:
            if phase not in objectives:
                raise ValueError(f"unknown climb objective: {phase!r}")
            plugboard, used = self._climb(objectives[phase], table, plugboard)
            evaluations += used
        return plugboard, evaluations
