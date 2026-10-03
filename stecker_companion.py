"""Confirm a body-direct candidate through the companion messages' bodies.

The indicator confirmation (``stecker_controls.confirm_against_date``) derives
each companion message's key through the clear indicator, which only works when
the candidate's plugboard and ring setting are exactly right: one wrong stecker
pair in the indicator letters gives a wrong message key and a body that is pure
noise.  That is the same discontinuity that makes the indicator-coupled search
unclimbable.

This check does not read the indicator.  It holds the candidate's wheel order,
ring setting and plugboard and deciphers each companion message at every one of
its 17,576 start positions, then asks whether the best start stands clear of the
other 17,575.  A mostly-right plugboard still lifts the right start well above
the noise, so the check degrades gracefully where the indicator check fails
outright, and it costs a fraction of a second per candidate.

The candidate's ring setting is the sweep's parameterization, not necessarily
the daily key's: the left and middle rings are absorbed into the start position
the scan searches, so a companion is deciphered exactly as by the true key for as
long as its middle wheel does not step its left wheel at a different letter.  The
right ring is a searched axis of the sweep and is taken as recovered.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from typing import Any

import enigma_fast
from stecker_scoring import FastNgramScorer
from stecker_traffic import Traffic

try:  # optional, as for the batched climb
    import numpy as np
except ImportError:  # pragma: no cover - exercised by the fallback test
    np = None

ALL_STARTS = tuple(
    (left, middle, right) for left in range(26) for middle in range(26) for right in range(26)
)


def available() -> bool:
    return np is not None


def _offset_permutations(order: Sequence[Any], reflector: Sequence[int]) -> "np.ndarray":
    """Unsteckered permutation for every wheel offset, as a ``(26**3, 26)`` array.

    Row ``(left * 26 + middle) * 26 + right`` is the permutation
    ``enigma_fast.position_permutations`` builds for those offsets.
    """

    left, middle, right = order
    left_forward, left_reverse = np.asarray(left.forward), np.asarray(left.reverse)
    middle_forward, middle_reverse = np.asarray(middle.forward), np.asarray(middle.reverse)
    right_forward, right_reverse = np.asarray(right.forward), np.asarray(right.reverse)
    reflect = np.asarray(reflector)
    offset_left = np.arange(26)[:, None, None]
    offset_middle = np.arange(26)[None, :, None]
    letters = np.arange(26)[None, None, :]
    core = middle_forward[offset_middle, letters]
    core = left_forward[offset_left, core]
    core = reflect[core]
    core = left_reverse[offset_left, core]
    core = middle_reverse[offset_middle, core]  # (26, 26, 26)
    offset_right = np.arange(26)[None, None, :, None]
    inner = right_forward[offset_right, np.arange(26)[None, None, None, :]]
    full = core[
        np.arange(26)[:, None, None, None], np.arange(26)[None, :, None, None], inner
    ]
    return right_reverse[offset_right, full].reshape(26**3, 26)


def _scan_batched(
    message: Traffic,
    order: Sequence[Any],
    rings: Sequence[int],
    plugboard: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    starts: Sequence[tuple[int, int, int]],
) -> list[float]:
    table = _offset_permutations(order, reflector)
    positions = np.asarray(starts, dtype=np.int64)
    position_left, position_middle, position_right = (positions[:, axis].copy() for axis in range(3))
    middle_notches = np.asarray(sorted(order[1].notches))
    right_notches = np.asarray(sorted(order[2].notches))
    ring_left, ring_middle, ring_right = (int(value) for value in rings)
    length = len(message.body)
    index = np.empty((len(starts), length), dtype=np.int64)
    # Stepping exactly as ``crypt_indices``: the machine steps before every
    # letter, masked ones included.
    for step in range(length):
        at_notch = np.isin(position_middle, middle_notches)
        position_left = (position_left + at_notch) % 26
        position_middle = (position_middle + (at_notch | np.isin(position_right, right_notches))) % 26
        position_right = (position_right + 1) % 26
        index[:, step] = (
            ((position_left - ring_left) % 26) * 26 + (position_middle - ring_middle) % 26
        ) * 26 + (position_right - ring_right) % 26

    board = np.asarray(plugboard, dtype=np.int64)
    cipher = np.asarray(message.body, dtype=np.int64)
    valid = cipher >= 0
    text = board[table[index, board[np.where(valid, cipher, 0)]]]
    previous = np.r_[False, valid[:-1]]
    before = np.r_[False, False, valid[:-2]]
    trigrams = np.nonzero(valid & previous & before)[0]
    bigrams = np.nonzero(valid & previous & ~before)[0]
    combined = np.asarray(scorer.combined)
    bigram = np.asarray(scorer.bigram)
    total = combined[text[:, trigrams - 2] * 676 + text[:, trigrams - 1] * 26 + text[:, trigrams]].sum(axis=1)
    if len(bigrams):
        total = total + bigram[text[:, bigrams - 1] * 26 + text[:, bigrams]].sum(axis=1)
    return total.tolist()


def _scan_reference(
    message: Traffic,
    order: Sequence[Any],
    rings: Sequence[int],
    plugboard: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    starts: Sequence[tuple[int, int, int]],
) -> list[float]:
    return [
        scorer.score_indices(
            enigma_fast.crypt_indices(order, list(rings), start, message.body, plugboard, reflector)
        )
        for start in starts
    ]


def scan_starts(
    message: Traffic,
    rotor_order: Sequence[str],
    rings: Sequence[int],
    plugboard: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    starts: Sequence[tuple[int, int, int]] = ALL_STARTS,
    engine: str = "auto",
) -> list[float]:
    """Total n-gram score of ``message`` deciphered at each start in ``starts``.

    ``engine`` is ``reference`` (pure Python, the definition), ``batched``
    (numpy) or ``auto``.  The two agree exactly up to float summation order,
    which the tests check.
    """

    order = [enigma_fast.rotor_tables(name) for name in rotor_order]
    if engine == "auto":
        engine = "batched" if available() else "reference"
    scan = _scan_batched if engine == "batched" else _scan_reference
    return scan(message, order, rings, plugboard, scorer, reflector, starts)


def companion_scan(
    message: Traffic,
    rotor_order: Sequence[str],
    rings: Sequence[int],
    plugboard: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    engine: str = "auto",
) -> dict[str, Any]:
    """Best start of one companion message against its own 17,575 alternatives."""

    scores = [total / message.letters for total in scan_starts(
        message, rotor_order, rings, plugboard, scorer, reflector, engine=engine
    )]
    ranked = sorted(range(len(scores)), key=lambda position: (-scores[position], position))
    mean = statistics.fmean(scores)
    deviation = statistics.pstdev(scores, mu=mean)
    best, runner_up = ranked[0], ranked[1]
    start = ALL_STARTS[best]
    order = [enigma_fast.rotor_tables(name) for name in rotor_order]
    plaintext = enigma_fast.indices_to_text(
        enigma_fast.crypt_indices(order, list(rings), start, message.body, plugboard, reflector)
    )
    z = (lambda value: (value - mean) / deviation if deviation > 0 else math.inf)
    return {
        "designator": message.designator,
        "letters": message.letters,
        "starts_scanned": len(scores),
        "best_start": "".join(chr(65 + value) for value in start),
        "best_score_per_letter": round(scores[best], 9),
        "mean_score_per_letter": round(mean, 9),
        "sd_score_per_letter": round(deviation, 9),
        "best_z": round(z(scores[best]), 6),
        "runner_up_z": round(z(scores[runner_up]), 6),
        "best_plaintext_prefix": plaintext[:60],
    }


def confirm_through_companions(
    companions: Sequence[Traffic],
    rotor_order: Sequence[str],
    rings: Sequence[int],
    plugboard: Sequence[int],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    threshold_z: float,
    engine: str = "auto",
) -> dict[str, Any]:
    """Scan every companion message and apply the preregistered threshold.

    A candidate is confirmed when every companion's best start reaches
    ``threshold_z`` standard deviations above that companion's own start
    distribution.  ``min_best_z`` is reported so a near miss stays visible.
    """

    scans = [
        companion_scan(message, rotor_order, rings, plugboard, scorer, reflector, engine)
        for message in companions
    ]
    minimum = min(scan["best_z"] for scan in scans) if scans else None
    return {
        "companions": scans,
        "threshold_z": threshold_z,
        "min_best_z": minimum,
        "confirmed": minimum is not None and minimum >= threshold_z,
    }


def confirm_candidates(
    candidates: Sequence[Mapping[str, Any]],
    companions: Sequence[Traffic],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    threshold_z: float,
    engine: str = "auto",
) -> list[dict[str, Any]]:
    """:func:`confirm_through_companions` for each rendered sweep candidate."""

    return [
        confirm_through_companions(
            companions,
            candidate["rotor_order_left_to_right"],
            tuple(ord(letter) - 65 for letter in candidate["rings"]),
            enigma_fast.plugboard_table(candidate["plugboard"]),
            scorer,
            reflector,
            threshold_z,
            engine,
        )
        for candidate in candidates
    ]
