"""The two Phase 1 rotor-setting sweeps and the search spaces they enumerate."""

from __future__ import annotations

import concurrent.futures as futures
import itertools
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import enigma_fast
from stecker_climb import coincidence_of_decryption, run_climb_phases
from stecker_scoring import FastNgramScorer, index_of_coincidence
from stecker_traffic import Traffic


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


def resolve_axis(specification: Any) -> list[int]:
    if specification == "all":
        return list(range(26))
    if isinstance(specification, str):
        return [ord(letter) - 65 for letter in specification.upper()]
    if isinstance(specification, list):
        return [ord(str(value).upper()) - 65 for value in specification]
    raise ValueError(f"unsupported start-position axis: {specification!r}")


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
