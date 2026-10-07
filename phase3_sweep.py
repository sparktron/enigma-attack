#!/usr/bin/env python3
"""Phase 3 exhaustive sweep of the catalogued unsteckered machines.

The cited paper's authors suspect that Batch C was enciphered on an Enigma with
differently wired wheels, and every Phase 1 search assumes Army wheels I-V.  A
machine with unknown wiring cannot be recovered from three short messages, but
the documented machines without a plugboard can be searched completely: with no
plugboard there is nothing to climb, so every body-direct setting is deciphered
and scored (see :mod:`variant_sweep`).

The run is gated as Phase 1's sweeps are.  The fast kernel must reproduce
:class:`enigma.EnigmaMachine` and the published-count scorer on random keys, and
a planted message per machine must be recovered exactly by the same full sweep
the targets get.  A failed check or control makes zero target-search calls.
After the targets, planted draws at each target's length and mask positions are
scored against that target's own score distribution, which states the power
each null actually had.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import platform
import random
import sys
import time
from collections.abc import Mapping, Sequence
from concurrent import futures
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only without the fast extra
    raise SystemExit(
        "phase3_sweep needs numpy: pip install 'enigma-attack[fast]' or pip install numpy"
    ) from None

import phase3
from enigma import EnigmaMachine
from provenance import code_version, sha256_file
from resources import resolve_output, resource_root
from stecker_power import wilson_interval
from stecker_scoring import FastNgramScorer
from stecker_traffic import normalize_plaintext, traffic_from_corpus
from variant_sweep import (
    Machine,
    decrypt_grid,
    key_of,
    merge_statistics,
    order_tables,
    score_grid,
    stepping_schedules,
    sweep_order,
)

ROOT = resource_root()
DEFAULT_CONFIG = ROOT / "experiments/phase3-unsteckered-sweep-v1/config.json"
CONFIG_SCHEMA = "enigma-attack.phase3-sweep-config/v1"
RESULT_SCHEMA = "enigma-attack.phase3-sweep-result/v1"


def resolve_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else ROOT / path


def resolve_config(value: str) -> pathlib.Path:
    """A relative ``--config`` is the caller's file if it exists, else a shipped one."""

    path = pathlib.Path(value)
    return (path if path.is_file() else resolve_path(value)).resolve()


def describe_path(path: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def load_config(path: pathlib.Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"unsupported configuration schema: {config.get('schema')!r}")
    if config.get("mode") != "unsteckered_body_direct_sweep":
        raise ValueError(f"unsupported mode: {config.get('mode')!r}")
    return config


def load_machines(config: Mapping[str, Any]) -> dict[str, tuple[Machine, Any]]:
    _, profiles = phase3.load_variant_catalog(resolve_path(config["catalog"]))
    by_id = {profile.id: profile for profile in profiles}
    return {pid: (Machine.from_profile(by_id[pid]), by_id[pid]) for pid in config["profiles"]}


def reference_machine(profile: Any, order: Sequence[str], key: Mapping[str, str]) -> EnigmaMachine:
    return EnigmaMachine(
        tuple(order),
        key["rings"],
        key["positions"],
        rotor_wirings=profile.rotor_wirings,
        reflector=profile.reflector,
        entry_wiring=profile.entry_wiring,
        reflector_position=key["reflector_position"],
        stepping=profile.stepping,
    )


def reference_decrypt(profile: Any, order: Sequence[str], key: Mapping[str, str], body: Sequence[int]) -> list[int]:
    """Decipher index data with ``enigma.py``; a masked letter steps and stays masked."""

    machine = reference_machine(profile, order, key)
    out: list[int] = []
    for value in body:
        if value < 0:
            machine.key("A")
            out.append(-1)
        else:
            out.append(ord(machine.key(chr(65 + value))) - 65)
    return out


def random_key(generator: random.Random) -> dict[str, str]:
    letters = lambda count: "".join(chr(65 + generator.randrange(26)) for _ in range(count))  # noqa: E731
    return {"rings": letters(3), "positions": letters(3), "reflector_position": letters(1)}


# --- preflight ---------------------------------------------------------------


def kernel_parity(
    machines: Mapping[str, tuple[Machine, Any]],
    scorer: FastNgramScorer,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Random keys through the grid kernel, the reference machine and the scorer.

    Each sample is placed in the grid through its window start's schedule and
    its offsets, so the check covers the schedule deduplication, the tables, the
    grid layout, the score and the representative key reported for a cell.
    """

    generator = random.Random(int(spec["seed"]))
    length = int(spec["length"])
    bigram, combined = np.array(scorer.bigram), np.array(scorer.combined)
    report: dict[str, Any] = {}
    for pid, (machine, profile) in machines.items():
        failures = 0
        for _ in range(int(spec["samples"])):
            order = generator.choice(machine.orders())
            body = [generator.randrange(26) for _ in range(length)]
            body[generator.randrange(1, length - 1)] = -1
            key = random_key(generator)
            window = [ord(c) - 65 for c in key["positions"]]
            rings = [ord(c) - 65 for c in key["rings"]]
            offsets = [(window[i] - rings[i]) % 26 for i in range(3)]
            reflector = ord(key["reflector_position"]) - 65
            schedules = stepping_schedules(machine, order, length)
            schedule = int(schedules.of_start[(window[0] * 26 + window[1]) * 26 + window[2]])
            cell = ((offsets[0] * 26 + offsets[1]) * 26 + reflector) * 26 + offsets[2]
            tables = order_tables(machine, order)
            kernel = [
                -1 if letters is None else int(letters[cell])
                for letters in decrypt_grid(tables, schedules.counts[schedule], body)
            ]
            expected = reference_decrypt(profile, order, key, body)
            represented = reference_decrypt(profile, order, key_of(schedules, schedule, cell), body)
            score = float(score_grid(tables, schedules.counts[schedule], body, bigram, combined)[cell])
            if kernel != expected or represented != expected or score != scorer.score_indices(expected):
                failures += 1
        report[pid] = {"samples": int(spec["samples"]), "failures": failures}
    return {
        "passed": all(row["failures"] == 0 for row in report.values()),
        "length": length,
        "seed": int(spec["seed"]),
        "machines": report,
        "method": (
            "Random wheel order, rings, window start and reflector position, a random "
            "body with one masked letter. The grid kernel's letter at the key's cell, "
            "the reference machine at the cell's representative key, and the kernel's "
            "total score must equal enigma.EnigmaMachine and "
            "FastNgramScorer.score_indices exactly."
        ),
    }


# --- the sweep ---------------------------------------------------------------

_WORKER: dict[str, Any] = {}


def _worker_init(config: dict[str, Any]) -> None:
    scorer = FastNgramScorer(config["scorer"])
    _WORKER["bigram"] = np.array(scorer.bigram)
    _WORKER["combined"] = np.array(scorer.combined)
    _WORKER["machines"] = load_machines(config)


def _worker_task(task: tuple[str, int, list[int], int]) -> dict[str, Any]:
    pid, order_index, body, keep = task
    machine, _ = _WORKER["machines"][pid]
    order = machine.orders()[order_index]
    return sweep_order(machine, order, body, _WORKER["bigram"], _WORKER["combined"], keep)


def sweep_messages(
    config: Mapping[str, Any],
    pairs: Sequence[tuple[str, str, Sequence[int]]],
    jobs: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Each (machine, label, body) swept completely, merged per (machine, label).

    One task is one wheel order of one machine on one body, and every pair's
    tasks share one pool.  Results are merged in a fixed order, so nothing
    depends on ``jobs``.
    """

    keep = int(config["sweep"]["keep"])
    machines = load_machines(config)
    tasks = [
        (pid, label, index, list(body))
        for pid, label, body in pairs
        for index in range(len(machines[pid][0].orders()))
    ]
    results: dict[tuple[str, str, int], dict[str, Any]] = {}
    started = time.monotonic()
    if jobs > 1:
        with futures.ProcessPoolExecutor(
            max_workers=jobs, initializer=_worker_init, initargs=(dict(config),)
        ) as pool:
            waiting = {
                pool.submit(_worker_task, (pid, index, body, keep)): (pid, label, index)
                for pid, label, index, body in tasks
            }
            for future in futures.as_completed(waiting):
                results[waiting[future]] = future.result()
    else:
        _worker_init(dict(config))
        for pid, label, index, body in tasks:
            results[(pid, label, index)] = _worker_task((pid, index, body, keep))
    elapsed = time.monotonic() - started

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for pid, label, body in pairs:
        machine, profile = machines[pid]
        statistics: tuple[int, float, float] = (0, 0.0, 0.0)
        best = -math.inf
        pool: list[tuple[float, int, int, dict[str, Any]]] = []
        schedules = []
        for index, order in enumerate(machine.orders()):
            row = results[(pid, label, index)]
            statistics = merge_statistics(statistics, (row["evaluated"], row["mean"], row["m2"]))
            best = max(best, row["max"])
            schedules.append(row["schedules"])
            pool.extend(
                (-cand["score_per_letter"], index, rank, {**cand, "rotor_order_left_to_right": list(order)})
                for rank, cand in enumerate(row["top"])
            )
        pool.sort(key=lambda item: item[:3])
        count, mean, m2 = statistics
        deviation = math.sqrt(m2 / count) if count else 0.0
        top = []
        for _, _, _, candidate in pool[:keep]:
            order = candidate["rotor_order_left_to_right"]
            key = {k: candidate[k] for k in ("rings", "positions", "reflector_position")}
            plain = reference_decrypt(profile, order, key, body)
            letters = sum(1 for value in body if value >= 0)
            top.append(
                {
                    "score_per_letter": round(candidate["score_per_letter"], 9),
                    "z": round((candidate["score_per_letter"] - mean) / deviation, 6),
                    "rotor_order_left_to_right": order,
                    **key,
                    "offsets": candidate["offsets"],
                    "schedule": candidate["schedule"],
                    "plaintext": "".join("?" if v < 0 else chr(65 + v) for v in plain),
                    "reference_reproduces_score": (
                        _scorer_for_check(config).score_indices(plain) / letters
                        == candidate["score_per_letter"]
                    ),
                }
            )
        merged[(pid, label)] = {
            "machine": pid,
            "message": label,
            "letters": sum(1 for value in body if value >= 0),
            "settings_evaluated": count,
            "schedules_per_order": schedules,
            "score_distribution": {
                "mean_score_per_letter": round(mean, 9),
                "sd_score_per_letter": round(deviation, 9),
                "max_score_per_letter": round(best, 9),
                "top_z": round((best - mean) / deviation, 6) if deviation > 0 else None,
            },
            "top_candidates": top,
            "_null": (mean, deviation),
        }
    merged[("__timing__", "")] = {"seconds": round(elapsed, 3), "tasks": len(tasks), "jobs": jobs}
    return merged


_CHECK_SCORER: dict[str, FastNgramScorer] = {}


def _scorer_for_check(config: Mapping[str, Any]) -> FastNgramScorer:
    if "scorer" not in _CHECK_SCORER:
        _CHECK_SCORER["scorer"] = FastNgramScorer(config["scorer"])
    return _CHECK_SCORER["scorer"]


# --- planted messages --------------------------------------------------------


def stepped_key(profile: Any, order: Sequence[str], key: Mapping[str, str]) -> dict[str, str]:
    """The key whose first keystroke is ``key``'s second: one letter later."""

    machine = reference_machine(profile, order, key)
    machine.step()
    return {"rings": key["rings"], "positions": machine.positions, "reflector_position": machine.reflector_position}


def plant(
    profile: Any,
    machine: Machine,
    source: str,
    template: Sequence[int],
    generator: random.Random,
    fault: str = "none",
) -> dict[str, Any]:
    """A planted body shaped like ``template``: same length, same masked positions.

    ``fault`` is ``none``, ``deletion`` (a cipher letter lost) or ``insertion``
    (a random letter added) at a uniformly random interior position.  For a
    fault the head deciphers under one key and the tail under the key one
    keystroke away; both are returned, since the sweep visits both.
    """

    length = len(template)
    order = generator.choice(machine.orders())
    first = random_key(generator)
    second = stepped_key(profile, order, first)
    sent = {"none": length, "deletion": length + 1, "insertion": length - 1}[fault]
    start = generator.randrange(len(source) - sent + 1)
    plaintext = source[start : start + sent]
    if fault == "insertion":
        enciphered = reference_machine(profile, order, second).crypt(plaintext)
        heads_and_tails = [second, first]
    else:
        enciphered = reference_machine(profile, order, first).crypt(plaintext)
        heads_and_tails = [first, second] if fault == "deletion" else [first]
    cipher = [ord(c) - 65 for c in enciphered]
    position = generator.randrange(1, length - 1) if fault != "none" else None
    if fault == "deletion":
        del cipher[position]
    elif fault == "insertion":
        cipher.insert(position, generator.randrange(26))
    body = [-1 if template[i] < 0 else cipher[i] for i in range(length)]
    return {
        "order": list(order),
        "keys": heads_and_tails,
        "plaintext": plaintext,
        "fault": fault,
        "fault_position": position,
        "body": body,
    }


def planted_score(config: Mapping[str, Any], profile: Any, planted: Mapping[str, Any]) -> float:
    """The best per-letter score over the planted keys; a lower bound on the sweep's max."""

    scorer = _scorer_for_check(config)
    body = planted["body"]
    letters = sum(1 for value in body if value >= 0)
    return max(
        scorer.score_indices(reference_decrypt(profile, planted["order"], key, body)) / letters
        for key in planted["keys"]
    )


def evaluate_positive_controls(config: Mapping[str, Any], jobs: int) -> dict[str, Any]:
    """One planted message per machine, swept completely, must come back exactly."""

    spec = config["positive_controls"]
    machines = load_machines(config)
    source = normalize_plaintext(config["control_plaintext"])
    threshold = float(config["detection"]["threshold_z"])
    generator = random.Random(int(spec["seed"]))
    template = [0] * int(spec["length"])
    planted = {pid: plant(profile, machine, source, template, generator) for pid, (machine, profile) in machines.items()}
    sweep = sweep_messages(config, [(pid, "control", planted[pid]["body"]) for pid in machines], jobs)
    rows = []
    for pid in machines:
        result = sweep[(pid, "control")]
        top = result["top_candidates"][0]
        exact = top["plaintext"] == planted[pid]["plaintext"]
        rows.append(
            {
                "machine": pid,
                "length": len(template),
                "planted_order": planted[pid]["order"],
                "planted_key": planted[pid]["keys"][0],
                "top_candidate": {k: top[k] for k in ("rotor_order_left_to_right", "rings", "positions", "reflector_position", "score_per_letter", "z")},
                "top_plaintext_exact": exact,
                "top_z": top["z"],
                "score_distribution": result["score_distribution"],
                "passed": exact and top["z"] >= threshold,
            }
        )
    return {
        "evaluated": rows,
        "seconds": sweep[("__timing__", "")]["seconds"],
        "passed": bool(rows) and all(row["passed"] for row in rows),
        "criterion": (
            "The complete sweep of the planted message's machine ranks first a key "
            "whose reference decryption is the planted plaintext exactly, at z at "
            "least the detection threshold."
        ),
        "gate": "A failed control makes zero target-search calls.",
    }


def measure_power(
    config: Mapping[str, Any],
    bodies: Mapping[str, Sequence[int]],
    nulls: Mapping[tuple[str, str], tuple[float, float]],
) -> list[dict[str, Any]]:
    """Planted draws shaped like each target, judged against that target's null."""

    spec = config["power"]
    machines = load_machines(config)
    source = normalize_plaintext(config["control_plaintext"])
    threshold = float(config["detection"]["threshold_z"])
    rows = []
    for pid, (machine, profile) in machines.items():
        for label, body in bodies.items():
            mean, deviation = nulls[(pid, label)]
            for fault in spec["faults"]:
                generator = random.Random(f"{spec['seed']}:{pid}:{label}:{fault}")
                zs = []
                for _ in range(int(spec["draws"])):
                    planted = plant(profile, machine, source, body, generator, fault)
                    zs.append((planted_score(config, profile, planted) - mean) / deviation)
                hits = sum(1 for z in zs if z >= threshold)
                rows.append(
                    {
                        "machine": pid,
                        "message": label,
                        "fault": fault,
                        "draws": len(zs),
                        "detected": hits,
                        "rate": round(hits / len(zs), 6),
                        "interval_95": wilson_interval(hits, len(zs)),
                        "z_median": round(float(np.median(zs)), 3),
                        "z_min": round(min(zs), 3),
                    }
                )
    return rows


def score_predictions(
    config: Mapping[str, Any], sweeps: Sequence[Mapping[str, Any]], power: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Score the configuration's predictions; ``passed`` is None where one does not apply."""

    detected = [row for row in sweeps if row["detected"]]
    rows = []
    for prediction in config["predictions"]:
        kind = prediction["kind"]
        if kind == "any_detection":
            observed: Any = [f"{row['machine']}:{row['message']}" for row in detected]
            passed: bool | None = bool(detected)
        elif kind == "companion_detection":
            by_machine: dict[str, list[str]] = {}
            for row in detected:
                by_machine.setdefault(row["machine"], []).append(row["message"])
            observed = by_machine or "no detection"
            passed = all(len(v) >= 2 for v in by_machine.values()) if by_machine else None
        elif kind == "clean_power_at_least":
            rates = {f"{r['machine']}:{r['message']}": r["rate"] for r in power if r["fault"] == "none"}
            observed = {"minimum": min(rates.values()), "by_sweep": rates}
            passed = min(rates.values()) >= float(prediction["value"])
        elif kind == "null_top_z_between":
            low, high = (float(v) for v in prediction["value"])
            tops = [row["score_distribution"]["top_z"] for row in sweeps]
            observed = {"minimum": min(tops), "maximum": max(tops)}
            passed = None if detected else (low <= min(tops) and max(tops) <= high)
        else:
            raise ValueError(f"unknown prediction kind: {kind!r}")
        rows.append(
            {
                "id": prediction["id"],
                "statement": prediction["statement"],
                "decides_hypothesis": bool(prediction.get("decides_hypothesis", False)),
                "observed": observed,
                "passed": passed,
            }
        )
    return rows


# --- the experiment ----------------------------------------------------------


def run_experiment(config: Mapping[str, Any], config_path: pathlib.Path, argv: Sequence[str], jobs: int) -> dict[str, Any]:
    started_at = dt.datetime.now(dt.timezone.utc)
    started_clock = time.monotonic()
    version = code_version()
    corpus_path = resolve_path(config["corpus"])
    scorer = FastNgramScorer(config["scorer"])
    machines = load_machines(config)

    preflight = {"kernel_parity": kernel_parity(machines, scorer, config["kernel_parity"])}
    preflight["passed"] = preflight["kernel_parity"]["passed"]
    controls: dict[str, Any] = {"evaluated": [], "passed": False}
    if preflight["passed"]:
        controls = evaluate_positive_controls(config, jobs)

    result: dict[str, Any] | None = None
    if not preflight["passed"]:
        status = "blocked_by_preflight"
    elif not controls["passed"]:
        status = "blocked_by_positive_control"
    else:
        status = "complete"
        traffic = traffic_from_corpus(corpus_path, config["target"]["date"], config["target"]["messages"])
        bodies = {message.designator: list(message.body) for message in traffic}
        swept = sweep_messages(
            config, [(pid, label, body) for pid in machines for label, body in bodies.items()], jobs
        )
        timing = swept.pop(("__timing__", ""))
        nulls = {key: value.pop("_null") for key, value in swept.items()}
        threshold = float(config["detection"]["threshold_z"])
        sweeps = []
        for (pid, label), row in swept.items():
            row["detected"] = (row["score_distribution"]["top_z"] or 0.0) >= threshold
            sweeps.append(row)
        power = measure_power(config, bodies, nulls)
        detections = [(row["machine"], row["message"]) for row in sweeps if row["detected"]]
        result = {
            "formulation": "body_direct_unsteckered",
            "threshold_z": threshold,
            "timing": timing,
            "sweeps": sweeps,
            "detections": [{"machine": m, "message": msg} for m, msg in detections],
            "power": power,
            "predictions": score_predictions(config, sweeps, power),
        }
    return {
        "schema": RESULT_SCHEMA,
        "experiment_id": config["experiment_id"],
        "mode": config["mode"],
        "status": status,
        "accepted_break": False,
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - started_clock, 3),
        "configuration": {
            "path": describe_path(config_path),
            "sha256": sha256_file(config_path),
            "arguments": list(argv),
        },
        "code": version,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "jobs": jobs,
        },
        "inputs": {
            "corpus_sha256": sha256_file(corpus_path),
            "catalog_sha256": sha256_file(resolve_path(config["catalog"])),
            "bigram_counts_sha256": sha256_file(resolve_path(config["scorer"]["bigram_counts"])),
            "trigram_counts_sha256": sha256_file(resolve_path(config["scorer"]["trigram_counts"])),
        },
        "preflight": preflight,
        "positive_controls": controls,
        "result": result,
        "limitations": config["limitations"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="worker processes; results are merged in a fixed order, so the artifact "
        "does not depend on this value",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config_path = resolve_config(arguments.config)
    config = load_config(config_path)
    result = run_experiment(config, config_path, sys.argv[1:] if argv is None else argv, max(1, arguments.jobs))
    output = resolve_output(arguments.output or config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} mode={result['mode']} status={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
