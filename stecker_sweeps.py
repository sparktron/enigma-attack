"""The two Phase 1 rotor-setting sweeps.

The indicator-coupled sweep ranks daily keys by a pooled index of
coincidence.  The body-direct sweep runs a converged stecker climb at every
setting of a declared slice, in chunks that are merged in a fixed order and
can be checkpointed, so its result depends neither on ``--jobs`` nor on a
resume.
"""

from __future__ import annotations

import concurrent.futures as futures
import heapq
import json
import math
import pathlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import enigma_fast
# The fingerprint hashes the count tables through the same resolver the scorer
# reads them with, so it names the files the climb actually scored against.
from phase7 import resolve_path
from provenance import sha256_file, sha256_text
import stecker_batch
from stecker_climb import (
    climb_windows,
    coincidence_of_decryption,
    run_climb_phases,
    windowed_climb,
)
from stecker_scoring import FastNgramScorer, index_of_coincidence
from stecker_space import RingRule, Setting
from stecker_traffic import Traffic


# ---------------------------------------------------------------------------
# The indicator-coupled index-of-coincidence sweep
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
# The body-direct sweep
# ---------------------------------------------------------------------------


_WORKER: dict[str, Any] = {}

CLIMB_ENGINES = ("reference", "batched", "auto")


def resolve_engine(settings: Mapping[str, Any]) -> str:
    """The climb implementation a configuration runs: ``reference`` or ``batched``.

    ``reference`` is the pure-Python climb and is the default, so a configuration
    that says nothing behaves as it always did.  ``auto`` takes the batched climb
    when numpy is installed and the reference otherwise.  ``batched`` demands
    numpy and fails loudly without it, because quietly running the slower climb
    on a sweep sized for the faster one is how a run goes unfinished.
    """

    engine = settings.get("engine", "reference")
    if engine not in CLIMB_ENGINES:
        raise ValueError(f"unknown climb engine: {engine!r}")
    if engine == "auto":
        return "batched" if stecker_batch.available() else "reference"
    if engine == "batched" and not stecker_batch.available():
        raise RuntimeError(
            "climb.engine is 'batched' but numpy is not installed; "
            "install it or use 'auto' or 'reference'"
        )
    return engine


def _worker_init(scorer_config: dict[str, Any], body: list[int], settings: dict[str, Any],
                 reflector: list[int]) -> None:
    # Building the scorer reads both count tables, which a caller sweeping many
    # small slices in one process would otherwise repeat for every slice.
    key = json.dumps(scorer_config, sort_keys=True)
    if _WORKER.get("scorer_key") != key:
        _WORKER["scorer"] = FastNgramScorer(scorer_config)
        _WORKER["scorer_key"] = key
    _WORKER["body"] = body
    _WORKER["settings"] = settings
    _WORKER["reflector"] = reflector
    scorer = _WORKER["scorer"]
    batched = resolve_engine(settings) == "batched"
    window = settings.get("window")
    _WORKER["climber"] = (
        stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body, settings)
        if batched and window is None
        else None
    )
    # A windowed climb needs one batched climber per window, each built on that
    # window's letters; ``None`` there means the reference windowed climb.
    _WORKER["window_climbers"] = (
        [
            stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body[first:stop], settings)
            for _, first, stop in climb_windows(len(body), window)
        ]
        if batched and window is not None
        else None
    )


def _worker_chunk(task: tuple[int, str, tuple[str, ...], list[Setting], int]) -> dict[str, Any]:
    """Climb every setting of one chunk and return only what the merge needs.

    The result is the chunk's ``keep`` best settings and the running count, mean,
    sum of squared deviations and maximum of every score, so a chunk's memory and
    the size of what crosses the process boundary do not grow with the chunk.
    """

    index, key, names, swept, keep = task
    scorer = _WORKER["scorer"]
    body = _WORKER["body"]
    settings = _WORKER["settings"]
    reflector = _WORKER["reflector"]
    climber = _WORKER["climber"]
    window_climbers = _WORKER["window_climbers"]
    windowed = settings.get("window") is not None
    order = [enigma_fast.rotor_tables(name) for name in names]
    letters = sum(1 for value in body if value >= 0)
    phases = list(settings["phases"])
    heap: list[tuple[float, int, dict[str, Any]]] = []
    count, mean, m2, best = 0, 0.0, 0.0, -math.inf
    for local, (rings, start) in enumerate(swept):
        table = enigma_fast.position_permutations(order, rings, start, len(body), reflector)
        window_name = None
        if windowed:
            plugboard, evaluations, score, window_name = windowed_climb(
                table, body, scorer, settings, window_climbers
            )
        elif climber is not None:
            plugboard, evaluations = climber.climb(table)
        else:
            plugboard, _, evaluations = run_climb_phases(
                phases,
                {
                    "index_of_coincidence": lambda pb: coincidence_of_decryption(table, body, pb),
                    "ngram": lambda pb: scorer.score_decryption(table, body, pb),
                },
                letters,
                settings,
            )
        if not windowed:
            score = scorer.score_decryption(table, body, plugboard) / letters
        count += 1
        delta = score - mean
        mean += delta / count
        m2 += delta * (score - mean)
        best = max(best, score)
        entry = (
            score,
            -local,
            {
                "local": local,
                "score_per_letter": score,
                "rotor_order": list(names),
                "rings": list(rings),
                "start": list(start),
                "plugboard": list(plugboard),
                "plugboard_pairs": sum(1 for x in range(26) if plugboard[x] > x),
                "evaluations": evaluations,
                **({"window": window_name} if windowed else {}),
            },
        )
        # Ordered by (score, earlier first); ``-local`` is unique, so the row
        # itself is never compared.
        if len(heap) < keep:
            heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)
    top = [row for _, _, row in sorted(heap, key=lambda item: (-item[0], -item[1]))]
    return {
        "index": index,
        "key": key,
        "evaluated": count,
        "mean": mean,
        "m2": m2,
        "max": best,
        "top": top,
    }


def merge_score_statistics(
    left: tuple[int, float, float], right: tuple[int, float, float]
) -> tuple[int, float, float]:
    """Combine two ``(count, mean, m2)`` summaries (Chan et al.)."""

    n_left, mean_left, m2_left = left
    n_right, mean_right, m2_right = right
    total = n_left + n_right
    if n_left == 0:
        return right
    if n_right == 0:
        return left
    delta = mean_right - mean_left
    return (
        total,
        mean_left + delta * n_right / total,
        m2_left + m2_right + delta * delta * n_left * n_right / total,
    )


def sweep_chunks(
    rule: "RingRule",
    rotor_orders: Sequence[tuple[str, ...]],
    starts: Sequence[tuple[int, int, int]],
) -> list[tuple[str, tuple[str, ...], list[Setting]]]:
    """Wheel order x middle start, in a fixed order.

    One chunk per wheel order leaves the last round of a pool with idle workers
    and loses a whole order to a crash.  Splitting each order by its middle axis
    gives 60 x 26 = 1,560 chunks for a full sweep, small enough to balance and to
    checkpoint, and a chunk is a pure function of its key.
    """

    chunks: list[tuple[str, tuple[str, ...], list[Setting]]] = []
    for names in rotor_orders:
        groups: dict[int, list[tuple[int, int, int]]] = {}
        for start in starts:
            groups.setdefault(start[1], []).append(start)
        for middle, group in groups.items():
            chunks.append(("-".join(names) + f"/{middle}", names, rule.settings(names, group)))
    return chunks


def sweep_fingerprint(
    body: Sequence[int],
    scorer_config: Mapping[str, Any],
    settings: Mapping[str, Any],
    rule: "RingRule",
    starts: Sequence[tuple[int, int, int]],
    keep: int,
    engine: str,
    reflector: Sequence[int],
) -> str:
    """Identity of a declared sweep, so a checkpoint is never reused for another.

    It covers everything that decides a chunk's result: the ciphertext, the
    reflector, the scorer's configuration *and the contents of the count tables
    it names* (a path alone does not change when the file does), the climb, the
    ring rule, the searched starts, the retention limit and the engine.
    """

    return sha256_text(
        json.dumps(
            {
                "body": list(body),
                "reflector": list(reflector),
                "scorer_tables": [
                    sha256_file(resolve_path(scorer_config[name]))
                    for name in ("bigram_counts", "trigram_counts")
                ],
                "scorer": scorer_config,
                "climb": settings,
                "rule": [rule.name, list(rule.held), list(rule.right_rings), rule.length],
                "starts": [list(start) for start in starts],
                "keep": keep,
                "engine": engine,
            },
            sort_keys=True,
        )
    )


def read_checkpoint(path: pathlib.Path, fingerprint: str) -> dict[str, dict[str, Any]]:
    """Chunk results already recorded for this sweep.

    A final line cut off by a crash is ignored.  A record from a different sweep
    is an error rather than something to skip, because resuming across it would
    merge two experiments into one result.
    """

    done: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("fingerprint") != fingerprint:
            raise ValueError(
                f"{path} holds a checkpoint from a different sweep; "
                "remove it or choose another path"
            )
        done[record["key"]] = record
    return done


def trim_partial_record(path: pathlib.Path) -> None:
    """Drop a final record that a crash cut off before its newline.

    Appending after such a fragment would glue the next complete record onto it,
    and a later resume would discard both as one unreadable line.
    """

    if not path.exists():
        return
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        path.write_bytes(data[: data.rfind(b"\n") + 1])


def body_direct_sweep(
    message: Traffic,
    rotor_orders: Sequence[tuple[str, ...]],
    rings: Sequence[int] | RingRule,
    starts: Sequence[tuple[int, int, int]],
    scorer_config: Mapping[str, Any],
    reflector: Sequence[int],
    settings: Mapping[str, Any],
    keep: int,
    jobs: int,
    checkpoint: pathlib.Path | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    """Full stecker climb at every rotor setting of a declared slice.

    There is no cheap pre-filter.  The index of coincidence does not separate
    the true setting under a ten-pair stecker at these lengths, and a truncated
    climb does not either, so every setting in the slice costs a converged
    climb.  That is the measured reason this sweep is expensive.

    ``rings`` is either a ring setting held for the whole slice, with ``starts``
    taken as visible positions, or a :class:`RingRule` that derives each
    setting's rings and positions from the searched axes.

    Each chunk keeps its ``keep`` best settings and streaming score statistics;
    these are merged in chunk order, so the result is a pure function of the
    declared slice and does not depend on ``jobs`` or on which worker finished
    first.  With a ``checkpoint`` path every finished chunk is appended to a JSONL
    file and a rerun skips the chunks already recorded.
    """

    ranked, evaluated, distribution, _ = sweep_slice(
        message, rotor_orders, rings, starts, scorer_config, reflector, settings,
        keep, jobs, checkpoint,
    )
    return ranked, evaluated, distribution


def sweep_slice(
    message: Traffic,
    rotor_orders: Sequence[tuple[str, ...]],
    rings: Sequence[int] | RingRule,
    starts: Sequence[tuple[int, int, int]],
    scorer_config: Mapping[str, Any],
    reflector: Sequence[int],
    settings: Mapping[str, Any],
    keep: int,
    jobs: int,
    checkpoint: pathlib.Path | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any], dict[str, Any]]:
    """:func:`body_direct_sweep` plus a record of how the run was executed."""

    rule = (
        rings
        if isinstance(rings, RingRule)
        else RingRule("held", tuple(rings), (rings[2],), len(message.body))  # type: ignore[arg-type]
    )
    engine = resolve_engine(settings)
    keep = max(1, int(keep))
    chunks = sweep_chunks(rule, rotor_orders, starts)
    fingerprint = sweep_fingerprint(
        message.body, scorer_config, settings, rule, starts, keep, engine, reflector
    )
    results: dict[str, dict[str, Any]] = {}
    if checkpoint is not None:
        results.update(read_checkpoint(checkpoint, fingerprint))
    resumed = sum(1 for key, _, _ in chunks if key in results)
    pending = [
        (index, key, names, swept, keep)
        for index, (key, names, swept) in enumerate(chunks)
        if key not in results
    ]

    sink = None
    if checkpoint is not None:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        trim_partial_record(checkpoint)
        sink = checkpoint.open("a", encoding="utf-8")

    def record(result: dict[str, Any]) -> None:
        results[result["key"]] = result
        if sink is not None:
            sink.write(json.dumps({"fingerprint": fingerprint, **result}) + "\n")
            sink.flush()

    try:
        initargs = (
            dict(scorer_config), list(message.body), dict(settings), list(reflector),
        )
        if jobs > 1 and pending:
            with futures.ProcessPoolExecutor(
                max_workers=jobs, initializer=_worker_init, initargs=initargs
            ) as pool:
                waiting = [pool.submit(_worker_chunk, task) for task in pending]
                for future in futures.as_completed(waiting):
                    record(future.result())
        else:
            _worker_init(*initargs)
            for task in pending:
                record(_worker_chunk(task))
    finally:
        if sink is not None:
            sink.close()

    order_of = {key: index for index, (key, _, _) in enumerate(chunks)}
    statistics_total: tuple[int, float, float] = (0, 0.0, 0.0)
    best_score = -math.inf
    candidates: list[tuple[float, int, int, dict[str, Any]]] = []
    for key in sorted(order_of, key=order_of.__getitem__):
        result = results[key]
        statistics_total = merge_score_statistics(
            statistics_total, (result["evaluated"], result["mean"], result["m2"])
        )
        best_score = max(best_score, result["max"])
        for row in result["top"]:
            candidates.append((-row["score_per_letter"], order_of[key], row["local"], row))
    evaluated, mean, m2 = statistics_total
    candidates.sort(key=lambda item: item[:3])
    ranked = [
        {
            "rank": position + 1,
            "score_per_letter": round(row["score_per_letter"], 9),
            "rotor_order_left_to_right": row["rotor_order"],
            "rings": "".join(chr(65 + value) for value in row["rings"]),
            "start_position": "".join(chr(65 + value) for value in row["start"]),
            "plugboard": enigma_fast.plugboard_pairs(row["plugboard"]),
            "plugboard_pairs": row["plugboard_pairs"],
            **({"window": row["window"]} if "window" in row else {}),
            "_plugboard": row["plugboard"],
        }
        for position, (_, _, _, row) in enumerate(candidates[:keep])
    ]
    deviation = math.sqrt(m2 / evaluated) if evaluated else 0.0
    distribution = {
        "mean_score_per_letter": round(mean, 9),
        "sd_score_per_letter": round(deviation, 9),
        "max_score_per_letter": round(best_score, 9),
        "top_z_score": round((best_score - mean) / deviation, 6) if deviation > 0 else None,
    }
    execution = {
        "engine": engine,
        "chunks": len(chunks),
        "chunks_resumed_from_checkpoint": resumed,
        "chunks_run": len(pending),
        "settings_run": sum(len(task[3]) for task in pending),
        "checkpoint_fingerprint": fingerprint,
    }
    return ranked, evaluated, distribution, execution
