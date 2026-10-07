"""Exhaustive body-direct sweep of unsteckered Enigma-family machines.

Phase 3's variant screen enciphered every message under a handful of daily keys
per profile, 1,740 evaluations in all, with the rings at AAA and the reflector at
A.  That is a smoke test.  For a machine without a plugboard nothing has to be
climbed: a setting's decryption is fixed, so every setting can be scored
directly, and a machine's whole body-direct space is small enough to enumerate.

Parameterization.  A wheel's effect on the signal depends only on its offset,
the window letter minus the ring setting.  When it steps depends only on its
window letter, because the notch is on the alphabet ring.  A body-direct setting
is therefore an offset for each wheel, the reflector's start position, and the
window starts of the wheels whose notches the stepping consults.  Those window
starts matter only through the stepping schedule they produce over the message,
so the sweep simulates the stepping from all 26^3 window starts, keeps one
representative of each distinct schedule, and pairs each schedule with all 26^4
combinations of offsets and reflector position.  Nothing is lost: two window
starts with the same schedule decipher every message identically at every
offset.  Mapping a representative back to a ring setting gives a concrete key
that :class:`enigma.EnigmaMachine` reproduces, which the preflight checks.

The body is searched directly, so no indicator procedure is assumed.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

STEPPINGS = ("pawl", "swiss_k_1941")
GRID = 26**4  # left offset x middle offset x reflector position x right offset


def _permutation(wiring: str) -> np.ndarray:
    values = np.array([ord(letter) - 65 for letter in wiring.upper()], dtype=np.intp)
    if sorted(values.tolist()) != list(range(26)):
        raise ValueError(f"not a permutation: {wiring!r}")
    return values


@dataclass(frozen=True)
class Machine:
    """One catalogued unsteckered machine, as :class:`enigma.EnigmaMachine` models it."""

    profile_id: str
    rotor_pool: tuple[str, ...]
    rotor_wirings: Mapping[str, tuple[str, str]]
    reflector: str
    entry_wiring: str
    stepping: str

    @classmethod
    def from_profile(cls, profile: Any) -> "Machine":
        if profile.plugboard_practice != "none":
            raise ValueError(f"{profile.id} has a plugboard; this sweep has no stecker search")
        if not profile.reflector_settable:
            raise ValueError(f"{profile.id}: a fixed reflector is not modelled here")
        if profile.stepping not in STEPPINGS:
            raise ValueError(f"{profile.id}: unsupported stepping {profile.stepping!r}")
        return cls(
            profile_id=profile.id,
            rotor_pool=tuple(profile.rotor_pool),
            rotor_wirings=dict(profile.rotor_wirings),
            reflector=profile.reflector,
            entry_wiring=profile.entry_wiring,
            stepping=profile.stepping,
        )

    def orders(self) -> list[tuple[str, str, str]]:
        return list(itertools.permutations(self.rotor_pool, 3))

    def notches(self, name: str) -> np.ndarray:
        table = np.zeros(26, dtype=bool)
        for letter in self.rotor_wirings[name][1].upper():
            table[ord(letter) - 65] = True
        return table


@dataclass(frozen=True)
class Schedules:
    """The distinct stepping schedules of one wheel order over one length.

    ``counts[s, i]`` holds, modulo 26, how far the left, middle and right wheels
    and the reflector have advanced once keystroke ``i`` has stepped the
    machine.  ``starts[s]`` is one window start (left, middle, right) that
    produces schedule ``s``, and ``of_start`` maps every one of the 26^3 window
    starts to its schedule.
    """

    counts: np.ndarray
    starts: np.ndarray
    of_start: np.ndarray

    def __len__(self) -> int:
        return int(self.counts.shape[0])


def stepping_schedules(machine: Machine, order: Sequence[str], length: int) -> Schedules:
    """Simulate the stepping from every window start, exactly as ``enigma.py`` steps."""

    grid = np.indices((26, 26, 26)).reshape(3, -1)
    left, middle, right = (axis.astype(np.intp) for axis in grid)
    notch_left, notch_middle, notch_right = (machine.notches(name) for name in order)
    advanced = np.zeros((4, left.size), dtype=np.intp)
    counts = np.zeros((left.size, length, 4), dtype=np.uint8)
    for keystroke in range(length):
        if machine.stepping == "pawl":
            # Both notches are read before anything moves: the double step.
            at_middle = notch_middle[middle]
            at_right = notch_right[right]
            step_left = at_middle
            step_middle = at_middle | at_right
            left = (left + step_left) % 26
            middle = (middle + step_middle) % 26
            right = (right + 1) % 26
            advanced[0] += step_left
            advanced[1] += step_middle
            advanced[2] += 1
        else:
            # Swiss Army 1941: right wheel fixed, middle wheel fast, the left
            # wheel's notch steps the reflector and the left wheel itself.
            at_left = notch_left[left]
            at_middle = notch_middle[middle]
            step_left = at_middle | at_left
            left = (left + step_left) % 26
            middle = (middle + 1) % 26
            advanced[0] += step_left
            advanced[1] += 1
            advanced[3] += at_left
        counts[:, keystroke, :] = (advanced % 26).T
    flat = counts.reshape(left.size, -1)
    _, first, inverse = np.unique(flat, axis=0, return_index=True, return_inverse=True)
    # np.unique orders schedules by content; renumber them by their first
    # window start so the numbering reads naturally and is still deterministic.
    order_of = np.argsort(first, kind="stable")
    renumber = np.empty_like(order_of)
    renumber[order_of] = np.arange(order_of.size)
    first = first[order_of]
    return Schedules(
        counts=counts[first],
        starts=np.stack([grid[0][first], grid[1][first], grid[2][first]], axis=1),
        of_start=renumber[np.asarray(inverse).reshape(-1)],
    )


@dataclass(frozen=True)
class OrderTables:
    """Per-offset permutations for one wheel order.

    ``inner[l, m, u, x]`` is the path from the right wheel's output through the
    middle and left wheels, the reflector and back, at left offset ``l``, middle
    offset ``m`` and reflector position ``u``.  ``into[r, c]`` takes a
    ciphertext letter through the entry wheel and the right wheel at right
    offset ``r``; ``out_of[r, z]`` takes the signal back out.
    """

    inner: np.ndarray
    into: np.ndarray
    out_of: np.ndarray


def order_tables(machine: Machine, order: Sequence[str]) -> OrderTables:
    offsets = np.arange(26)[:, None]
    letters = np.arange(26)[None, :]

    def wheel(name: str) -> tuple[np.ndarray, np.ndarray]:
        wiring = _permutation(machine.rotor_wirings[name][0])
        inverse = np.argsort(wiring)
        forward = (wiring[(letters + offsets) % 26] - offsets) % 26
        backward = (inverse[(letters + offsets) % 26] - offsets) % 26
        return forward, backward

    (left_f, left_b), (middle_f, middle_b), (right_f, right_b) = (wheel(n) for n in order)
    reflector = _permutation(machine.reflector)
    reflected = (reflector[(letters + offsets) % 26] - offsets) % 26
    entry = _permutation(machine.entry_wiring)
    entry_inverse = np.argsort(entry)

    l = np.arange(26)[:, None, None, None]
    m = np.arange(26)[None, :, None, None]
    u = np.arange(26)[None, None, :, None]
    x = np.arange(26)[None, None, None, :]
    signal = middle_f[m, x]
    signal = left_f[l, signal]
    signal = reflected[u, signal]
    signal = left_b[l, signal]
    signal = middle_b[m, signal]
    return OrderTables(
        inner=signal.astype(np.intp),
        into=right_f[:, entry].astype(np.intp),
        out_of=entry_inverse[right_b].astype(np.intp),
    )


def decrypt_grid(
    tables: OrderTables,
    counts: np.ndarray,
    body: Sequence[int],
    lefts: Sequence[int] | None = None,
) -> Iterator[np.ndarray | None]:
    """Yield each keystroke's plaintext letter at every offset, flattened.

    The grid is ordered left offset, middle offset, reflector position, right
    offset; ``lefts`` restricts it to those left offsets, in that order.  A
    masked ciphertext letter (``-1``) still steps the machine and yields
    ``None``, as ``enigma.py`` keys a placeholder for it.
    """

    axis = np.arange(26)
    lefts = axis if lefts is None else np.asarray(lefts)
    # 32-bit throughout: every index fits, and the per-keystroke gathers are
    # bound by memory traffic.
    flat_inner = tables.inner.reshape(-1).astype(np.int32)
    flat_out = tables.out_of.reshape(-1).astype(np.int32)
    base = (np.arange(17576, dtype=np.int32) * 26).reshape(26, 26, 26)
    lanes = (axis * 26).astype(np.int32)
    for keystroke, letter in enumerate(body):
        if letter < 0:
            yield None
            continue
        left, middle, right, reflector = (int(value) for value in counts[keystroke])
        right_offsets = (axis + right) % 26
        entered = tables.into[right_offsets, letter].astype(np.int32)
        shifted = base[np.ix_((lefts + left) % 26, (axis + middle) % 26, (axis + reflector) % 26)]
        returned = flat_inner[shifted[..., None] + entered]
        returned += lanes[right_offsets]
        yield flat_out[returned].reshape(-1)


def score_grid(
    tables: OrderTables,
    counts: np.ndarray,
    body: Sequence[int],
    bigram: np.ndarray,
    combined: np.ndarray,
    block: int = 1,
) -> np.ndarray:
    """Total n-gram score of every offset's decryption, as FastNgramScorer adds it.

    The terms are added in letter order in float64, exactly as
    :meth:`stecker_scoring.FastNgramScorer.score_indices` adds them, so the
    totals agree to the last bit.

    The grid is scored ``block`` left offsets at a time, every keystroke for one
    block before the next, so the working arrays stay in a core's cache.  With
    the whole grid at once, eight workers sharing memory bandwidth took 0.57 s
    of wall time per 167-letter schedule; one left offset at a time took 0.14 s,
    with identical totals.
    """

    parts = []
    for first in range(0, 26, block):
        lefts = range(first, min(26, first + block))
        total = np.zeros(len(lefts) * 26**3, dtype=np.float64)
        previous: np.ndarray | None = None
        cursor: np.ndarray | None = None
        for letters in decrypt_grid(tables, counts, body, lefts):
            if letters is None:
                previous = None
                cursor = None
                continue
            if previous is None:
                previous = letters
                continue
            if cursor is None:
                total += bigram[previous * 26 + letters]
                cursor = previous * 676 + letters * 26
            else:
                total += combined[cursor + letters]
                cursor %= 676
                cursor += letters
                cursor *= 26
                continue
            previous = letters
        parts.append(total)
    return np.concatenate(parts)


def merge_statistics(
    left: tuple[int, float, float], right: tuple[int, float, float]
) -> tuple[int, float, float]:
    """Combine two ``(count, mean, m2)`` summaries (Chan et al.)."""

    n_a, mean_a, m2_a = left
    n_b, mean_b, m2_b = right
    if n_a == 0:
        return right
    if n_b == 0:
        return left
    n = n_a + n_b
    delta = mean_b - mean_a
    return n, mean_a + delta * n_b / n, m2_a + m2_b + delta * delta * n_a * n_b / n


def grid_cell(flat: int) -> tuple[int, int, int, int]:
    """(left offset, middle offset, reflector position, right offset) of a grid index."""

    left, rest = divmod(int(flat), 17576)
    middle, rest = divmod(rest, 676)
    reflector, right = divmod(rest, 26)
    return left, middle, reflector, right


def key_of(schedules: Schedules, schedule: int, flat: int) -> dict[str, Any]:
    """A concrete key that deciphers the body as grid cell ``flat`` of ``schedule`` does."""

    left_o, middle_o, reflector, right_o = grid_cell(flat)
    window = [int(value) for value in schedules.starts[schedule]]
    offsets = (left_o, middle_o, right_o)
    rings = [(window[i] - offsets[i]) % 26 for i in range(3)]
    return {
        "positions": "".join(chr(65 + value) for value in window),
        "rings": "".join(chr(65 + value) for value in rings),
        "reflector_position": chr(65 + reflector),
        "offsets": "".join(chr(65 + value) for value in offsets),
        "schedule": int(schedule),
    }


def sweep_order(
    machine: Machine,
    order: Sequence[str],
    body: Sequence[int],
    bigram: np.ndarray,
    combined: np.ndarray,
    keep: int,
) -> dict[str, Any]:
    """Score every setting of one wheel order; keep the best and running statistics."""

    letters = sum(1 for value in body if value >= 0)
    schedules = stepping_schedules(machine, order, len(body))
    tables = order_tables(machine, order)
    statistics: tuple[int, float, float] = (0, 0.0, 0.0)
    best = -math.inf
    pool: list[tuple[float, int, int]] = []
    for schedule in range(len(schedules)):
        scores = score_grid(tables, schedules.counts[schedule], body, bigram, combined) / letters
        mean = float(scores.mean())
        statistics = merge_statistics(
            statistics, (scores.size, mean, float(((scores - mean) ** 2).sum()))
        )
        best = max(best, float(scores.max()))
        top = np.argpartition(-scores, keep - 1)[:keep]
        pool.extend((float(scores[i]), schedule, int(i)) for i in top)
        pool.sort(key=lambda row: (-row[0], row[1], row[2]))
        del pool[keep:]
    return {
        "order": list(order),
        "schedules": len(schedules),
        "evaluated": statistics[0],
        "mean": statistics[1],
        "m2": statistics[2],
        "max": best,
        "top": [
            {"score_per_letter": score, **key_of(schedules, schedule, flat)}
            for score, schedule, flat in pool
        ],
    }
