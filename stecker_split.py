"""A stecker climb that searches the position of one dropped or inserted letter.

One transcription fault at position p leaves the letters before it aligned with
the swept setting and the letters after it aligned with the same machine one
keystroke on (a dropped letter) or one keystroke back (an inserted one). The
position table of a single setting already holds those keystrokes, so no second
setting is needed: a letter at ciphertext index i is decrypted with row i
before the fault and with row i + 1 or i - 1 after it.

A hypothesis is (clean), (deletion at p) or (insertion at p). Each is scored as
the reference scorer scores the repaired message, with an uncertainty mask at
the fault so that no n-gram spans it: a dropped letter leaves a gap in the
plaintext, an inserted one is garbage, and the chain restarts after either. The
climb's objective is the best hypothesis for the plugboard being tried, so the
position is searched inside every evaluation instead of outside the climb.

A mask removes n-gram terms, and every term is negative, so a masked
hypothesis would beat the clean one by the size of what it dropped whatever the
plugboard, and a fault would be placed near an end for nothing. A dropped
letter costs one term; an inserted one costs two, since the garbage letter is
not scored and the chain restarts after it. Each masked hypothesis is therefore
credited ``split.mask_term`` per dropped term, the value of a term on
wrong-setting text (-8.66, the climbed wrong-setting null mean per letter of
phase1-middle-complete-power-v1), which makes a mask cost nothing on text that
is wrong anyway and cost something on text that is right. A message that
already carries masks of its own is credited the same, which is approximate.

The two phases are the ordinary climb's. The n-gram phase scores every position
exactly with prefix and suffix sums. The index-of-coincidence phase scores only
the boundaries of a grid of ``split.ic_grid`` letters, because a split costs a
26-letter count vector per boundary there and the phase only has to reach the
right basin. ``reference_*`` restate both objectives in the slow, direct way and
are what the tests check the batched code against.

numpy is required, as for ``stecker_batch``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import stecker_batch
from stecker_scoring import FastNgramScorer

np = stecker_batch.np


def hypotheses(length: int) -> list[tuple[str, int | None]]:
    """Every hypothesis of an ``length``-letter message, clean first."""

    return (
        [("clean", None)]
        + [("deletion", p) for p in range(1, length)]
        + [("insertion", p) for p in range(1, length - 1)]
    )


def hypothesis_inputs(
    flat_table: Sequence[int], body: Sequence[int], kind: str, p: int | None
) -> tuple[list[int], list[int]]:
    """The (flat table, body) the reference scorer needs for one hypothesis.

    A dropped letter is put back as a mask at ``p`` and the tail moves one
    position on, so the repaired message has one more letter and the table
    already holds its extra row. An inserted letter is masked in place and the
    tail keeps its index but takes the previous keystroke's row.
    """

    n = len(body)
    rows = [list(flat_table[26 * r : 26 * r + 26]) for r in range(len(flat_table) // 26)]
    if kind == "clean":
        return [v for r in rows[:n] for v in r], list(body)
    if kind == "deletion":
        return [v for r in rows[: n + 1] for v in r], list(body[:p]) + [-1] + list(body[p:])
    if kind == "insertion":
        chosen = [rows[i] if i <= p else rows[i - 1] for i in range(n)]
        return [v for r in chosen for v in r], list(body[:p]) + [-1] + list(body[p + 1 :])
    raise ValueError(f"unknown hypothesis: {kind!r}")


DEFAULT_MASK_TERM = -8.66
DEFAULT_BLOCK = 64
DROPPED_TERMS = {"deletion": 1, "insertion": 2}


def reference_ngram_objective(
    scorer: FastNgramScorer,
    flat_table: Sequence[int],
    body: Sequence[int],
    plugboard: Sequence[int],
    mask_term: float = DEFAULT_MASK_TERM,
) -> tuple[float, tuple[str, int | None]]:
    """The best hypothesis' n-gram score, by scoring every hypothesis directly."""

    best: tuple[float, tuple[str, int | None]] | None = None
    for kind, p in hypotheses(len(body)):
        table, masked = hypothesis_inputs(flat_table, body, kind, p)
        score = scorer.score_decryption(table, masked, plugboard)
        if kind != "clean":
            score += mask_term * DROPPED_TERMS[kind]
        if best is None or score > best[0]:
            best = (score, (kind, p))
    assert best is not None
    return best


def reference_coincidence_objective(
    flat_table: Sequence[int],
    body: Sequence[int],
    plugboard: Sequence[int],
    grid: int,
) -> float:
    """The best index of coincidence over the grid's hypotheses, counted directly.

    Letters before the boundary count with the head rows and letters after it
    with the shifted rows; a masked or garbage letter is left out of nothing
    but the n-gram score, so here every valid letter counts once, as the
    batched phase counts them. The weight is ``body_direct_climb``'s.
    """

    n = len(body)
    letters = sum(1 for v in body if v >= 0)

    def decrypt(i: int, row: int) -> int:
        return plugboard[flat_table[26 * row + plugboard[body[i]]]]

    def coincidence(counts: list[int]) -> float:
        return sum(c * (c - 1) for c in counts) / (letters * (letters - 1))

    best = -1.0
    clean = [0] * 26
    for i in range(n):
        if body[i] >= 0:
            clean[decrypt(i, i)] += 1
    best = max(best, coincidence(clean))
    for boundary in range(grid, n, grid):
        for shift in (+1, -1):
            counts = [0] * 26
            for i in range(n):
                if body[i] < 0:
                    continue
                row = i if i < boundary else min(max(i + shift, 0), len(flat_table) // 26 - 1)
                counts[decrypt(i, row)] += 1
            best = max(best, coincidence(counts))
    return best * n / letters


class SplitClimber(stecker_batch.BatchedClimber):
    """Both objectives of the split-point climb, batched over candidate plugboards.

    Built once per message like :class:`stecker_batch.BatchedClimber`, whose move
    set, move order and stopping rule it reuses. ``climb`` takes the position
    table of **n + 1** keystrokes, one more than the message has letters.
    """

    def __init__(
        self,
        bigram: Sequence[float],
        combined: Sequence[float],
        body: Sequence[int],
        settings: Mapping[str, Any],
    ) -> None:
        super().__init__(bigram, combined, body, settings)
        n = self.length
        valid = self.valid
        previous = np.r_[False, valid[:-1]]
        before = np.r_[False, False, valid[:-2]]
        self.gate_trigram = valid & previous & before
        self.gate_bigram_only = valid & previous & ~before
        self.gate_bigram_any = valid & previous
        grid = int((settings.get("split") or {}).get("ic_grid", 16))
        if grid < 2:
            raise ValueError(f"split.ic_grid must be at least 2, not {grid}")
        self.grid = grid
        self.block = int((settings.get("split") or {}).get("block", DEFAULT_BLOCK))
        self.mask_term = float((settings.get("split") or {}).get("mask_term", DEFAULT_MASK_TERM))
        self.segments = -(-n // grid)
        self.segment_of = np.arange(n) // grid
        self.all_valid = bool(self.valid.all())
        self.row_head = np.arange(n)
        self.row_after_deletion = np.minimum(np.arange(n) + 1, n)
        self.row_after_insertion = np.maximum(np.arange(n) - 1, 0)

    # -- decryption of the three alignments ---------------------------------

    def _streams(self, boards: "np.ndarray", table: "np.ndarray") -> list["np.ndarray"]:
        entering = boards[:, self.cipher]
        out = []
        for rows in (self.row_head, self.row_after_deletion, self.row_after_insertion):
            out.append(np.take_along_axis(boards, table[rows, entering], axis=1))
        return out

    # -- n-gram phase --------------------------------------------------------

    def _contributions(self, text: "np.ndarray") -> tuple["np.ndarray", "np.ndarray"]:
        """Per-position n-gram terms of one aligned stream, with chain restarts by mask.

        ``chain[:, t]`` is what the scorer adds at ``t`` when the stream is
        scored whole; ``bigram_any[:, t]`` is the bigram ending at ``t``
        whatever precedes it, which is what a chain restarted at ``t - 1`` adds.
        Both have one trailing zero column so slices up to ``n`` stay in range.
        """

        k, n = text.shape
        bigrams = self.bigram[text[:, :-1] * 26 + text[:, 1:]]
        trigrams = self.combined[text[:, :-2] * 676 + text[:, 1:-1] * 26 + text[:, 2:]]
        chain = np.zeros((k, n + 1))
        chain[:, 1:n] = bigrams * self.gate_bigram_only[1:]
        chain[:, 2:n] += trigrams * self.gate_trigram[2:]
        bigram_any = np.zeros((k, n + 1))
        bigram_any[:, 1:n] = bigrams * self.gate_bigram_any[1:]
        return chain, bigram_any

    def _ngram_hypotheses(self, boards: "np.ndarray", table: "np.ndarray"):
        n = self.length
        head, after_deletion, after_insertion = self._streams(boards, table)
        chain_h, _ = self._contributions(head)
        chain_d, any_d = self._contributions(after_deletion)
        chain_i, any_i = self._contributions(after_insertion)
        zero = np.zeros((boards.shape[0], 1))
        prefix_h = np.concatenate([zero, np.cumsum(chain_h[:, :n], axis=1)], axis=1)  # (K, n + 1)

        def suffix(chain: "np.ndarray") -> "np.ndarray":
            prefix = np.concatenate([zero, np.cumsum(chain[:, :n], axis=1)], axis=1)
            tail = prefix[:, n : n + 1] - prefix  # sum over t >= a, a in 0..n
            return np.concatenate([tail, zero], axis=1)  # (K, n + 2)

        suffix_d, suffix_i = suffix(chain_d), suffix(chain_i)
        clean = prefix_h[:, n]
        deletion = prefix_h[:, 1:n] + any_d[:, 2 : n + 1] + suffix_d[:, 3 : n + 2] + self.mask_term
        insertion = (
            prefix_h[:, 1 : n - 1]
            + any_i[:, 3 : n + 1]
            + suffix_i[:, 4 : n + 2]
            + 2 * self.mask_term
        )
        return clean, deletion, insertion

    def _ngram_block(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        clean, deletion, insertion = self._ngram_hypotheses(boards, table)
        return np.maximum(clean, np.maximum(deletion.max(axis=1), insertion.max(axis=1)))

    def _blocked(self, objective):
        """Apply an objective to at most ``split.block`` boards at a time.

        The arrays of one evaluation are several megabytes at 350 candidates,
        which is more than a core's cache once every worker of a sweep is
        running; a block that fits is the same arithmetic with less traffic.
        """

        def run(boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
            block = self.block
            if not block or boards.shape[0] <= block:
                return objective(boards, table)
            return np.concatenate(
                [objective(boards[i : i + block], table) for i in range(0, boards.shape[0], block)]
            )

        return run

    def _ngram(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        return self._blocked(self._ngram_block)(boards, table)

    def best_hypothesis(
        self, plugboard: Sequence[int], table: "np.ndarray"
    ) -> tuple[float, tuple[str, int | None]]:
        clean, deletion, insertion = self._ngram_hypotheses(
            np.asarray(plugboard, dtype=np.int64)[None, :], table
        )
        best = (float(clean[0]), ("clean", None))
        d, i = int(deletion[0].argmax()), int(insertion[0].argmax())
        if deletion[0, d] > best[0]:
            best = (float(deletion[0, d]), ("deletion", d + 1))
        if insertion[0, i] > best[0]:
            best = (float(insertion[0, i]), ("insertion", i + 1))
        return best

    # -- index-of-coincidence phase -----------------------------------------

    def _counts(self, text: "np.ndarray") -> "np.ndarray":
        k = text.shape[0]
        s = self.segments
        if self.all_valid:
            keep, segment = text, self.segment_of
        else:
            keep, segment = text[:, self.valid], self.segment_of[self.valid]
        flat = (np.arange(k)[:, None] * s + segment[None, :]) * 26 + keep
        return np.bincount(flat.ravel(), minlength=k * s * 26).reshape(k, s, 26)

    def _coincidence(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        return self._blocked(self._coincidence_block)(boards, table)

    def _coincidence_block(self, boards: "np.ndarray", table: "np.ndarray") -> "np.ndarray":
        head, after_deletion, after_insertion = self._streams(boards, table)
        counts_h, counts_d, counts_i = (
            self._counts(t) for t in (head, after_deletion, after_insertion)
        )
        total_h = counts_h.sum(axis=1)
        squares = [np.einsum("kl,kl->k", total_h, total_h)]
        for other in (counts_d, counts_i):
            # Letters before boundary b come from the head stream and the rest
            # from the other one, so the mixed count is the head's cumulative
            # count minus the other's, plus the other's total.
            gap = np.cumsum(counts_h - other, axis=1)[:, :-1]
            total = other.sum(axis=1)
            mixed = (
                np.einsum("kbl,kbl->kb", gap, gap)
                + 2 * np.einsum("kbl,kl->kb", gap, total)
                + np.einsum("kl,kl->k", total, total)[:, None]
            )
            squares.append(mixed.max(axis=1))
        best = np.max(np.stack(squares), axis=0)
        n = self.letters
        return (best - n) / (n * (n - 1)) * self.length / self.letters

    # -- the climb -----------------------------------------------------------

    def climb(self, flat_table: Sequence[int]) -> tuple[list[int], int, float, tuple[str, int | None]]:
        """Run the configured phases at one setting.

        ``flat_table`` is ``enigma_fast.position_permutations`` for ``n + 1``
        keystrokes. Returns the plugboard, the plugboards evaluated, the best
        hypothesis' n-gram score per letter and that hypothesis.
        """

        table = np.asarray(flat_table, dtype=np.int64).reshape(self.length + 1, 26)
        objectives = {"index_of_coincidence": self._coincidence, "ngram": self._ngram}
        plugboard: list[int] = list(range(26))
        evaluations = 0
        for phase in self.settings["phases"]:
            if phase not in objectives:
                raise ValueError(f"unknown climb objective: {phase!r}")
            plugboard, used = self._climb(objectives[phase], table, plugboard)
            evaluations += used
        score, hypothesis = self.best_hypothesis(plugboard, table)
        return plugboard, evaluations, score / self.letters, hypothesis
