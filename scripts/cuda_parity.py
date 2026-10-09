#!/usr/bin/env python3
"""Check the cuda climb engine against the batched climb, beyond the preflight.

Exploratory engineering, not a preregistered experiment: it writes no artifact
and CI does not run it (it needs a GPU).

``random`` climbs seeded random settings with both engines, whole-message and
windowed, on clean bodies, bodies with masked letters and short bodies, and
requires the same final plugboard, evaluation count, window and score:

    python3 scripts/cuda_parity.py random --settings 2000 --seed 20261008

``split`` does the same for the split-point climb against
``stecker_split.SplitClimber``, on clean bodies, bodies with one dropped or
inserted letter (some also masked) and short bodies, and also requires the same
hypothesis:

    python3 scripts/cuda_parity.py split --settings 2000 --grid 32 --seed 20261009

``chunks`` recomputes finished chunks of a body-direct sweep from a copy of its
checkpoint with the cuda engine and the sweep's own configuration, and compares
each record field by field (the configuration's engine is replaced by cuda):

    python3 scripts/cuda_parity.py chunks --config experiments/phase1-body-direct-sweep-v4/config.json \\
        --checkpoint copy-of-checkpoint.jsonl --chunks 3

``compare`` needs no GPU: it compares two finished checkpoints of the same
sweep run with different engines (a CPU run and a GPU run), chunk by chunk,
as JSON text without the fingerprint, and records each chunk's hash and
statistics so the comparison can be checked later against either file:

    python3 scripts/cuda_parity.py compare --reference cpu.checkpoint.jsonl \\
        --candidate gpu.checkpoint.jsonl --output comparison.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import enigma_fast  # noqa: E402
import phase1_stecker as stecker  # noqa: E402
import stecker_batch  # noqa: E402
import stecker_cuda  # noqa: E402
from enigma import EnigmaI  # noqa: E402
import stecker_split  # noqa: E402
from stecker_climb import climb_windows, windowed_climb  # noqa: E402
from stecker_power import perturb_ciphertext  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402
from stecker_space import RingRule, resolve_axis, rotor_order_space  # noqa: E402
from stecker_sweeps import _worker_chunk, _worker_init, sweep_chunks  # noqa: E402
from stecker_traffic import normalize_plaintext, random_plugboard, traffic_from_corpus  # noqa: E402

V4 = ROOT / "experiments/phase1-body-direct-sweep-v4/config.json"
WHEELS = ["I", "II", "III", "IV", "V"]


def batched_outcome(scorer, body, table, climb):
    if climb.get("window") is not None:
        climbers = [
            stecker_batch.BatchedClimber(scorer.bigram, scorer.combined, body[first:stop], climb)
            for _, first, stop in climb_windows(len(body), climb["window"])
        ]
        return windowed_climb(table, body, scorer, climb, climbers)
    plugboard, evaluations = stecker_batch.BatchedClimber(
        scorer.bigram, scorer.combined, body, climb
    ).climb(table)
    letters = sum(1 for value in body if value >= 0)
    return plugboard, evaluations, scorer.score_decryption(table, body, plugboard) / letters, "whole"


def random_parity(arguments) -> dict:
    config = stecker.load_config(V4)
    scorer = FastNgramScorer(config["scorer"])
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])
    generator = random.Random(arguments.seed)
    source = "".join(
        normalize_plaintext(row["raw"]) for row in config["scorer_validation"]["plaintexts"]
    )
    calibration = stecker.load_config(ROOT / "experiments/phase1-stecker-calibration-v1/config.json")
    source += normalize_plaintext(calibration["climb_capability_calibration"]["plaintext"], 167)
    whole = {key: value for key, value in config["climb"].items() if key != "window"}
    climbs = {"whole": whole, "w117": {**whole, "window": {"kind": "head_tail", "letters": 117}}}
    kinds = ("clean", "masked", "short")
    per_body = arguments.per_body
    cells: dict[str, dict[str, int]] = {}
    worst = 0.0
    mismatches = []
    started = time.monotonic()
    for climb_name, climb in climbs.items():
        done = 0
        body_index = 0
        while done < arguments.settings:
            kind = kinds[body_index % 3]
            body_index += 1
            length = generator.randrange(150, 168) if kind != "short" else generator.randrange(30, 140)
            offset = generator.randrange(0, len(source) - length)
            order = tuple(generator.sample(WHEELS, 3))
            rings = [generator.randrange(26) for _ in range(3)]
            start = [generator.randrange(26) for _ in range(3)]
            ciphertext = EnigmaI(
                rotors=order,
                rings="".join(chr(65 + value) for value in rings),
                positions="".join(chr(65 + value) for value in start),
                plugboard=random_plugboard(generator, 10),
            ).crypt(source[offset:offset + length])
            body = list(enigma_fast.text_to_indices(ciphertext))
            if kind == "masked":
                for position in generator.sample(range(length), generator.randrange(1, 9)):
                    body[position] = -1
                if generator.random() < 0.3:
                    body[0] = -1
                if generator.random() < 0.3:
                    run = generator.randrange(2, length - 3)
                    body[run] = body[run + 1] = -1
            # Most settings are wrong, as in a sweep; the first of each body is the true one.
            rows = [(order, rings + start)] + [
                (tuple(generator.sample(WHEELS, 3)), [generator.randrange(26) for _ in range(6)])
                for _ in range(per_body - 1)
            ]
            gpu = stecker_cuda.CudaClimber(scorer.bigram, scorer.combined, body, climb, reflector)
            by_order: dict[tuple, list[int]] = {}
            for index, (names, _) in enumerate(rows):
                by_order.setdefault(names, []).append(index)
            got: dict[int, tuple] = {}
            for names, indices in by_order.items():
                boards, evaluations, scores, winner = gpu.climb_settings(
                    names, np.asarray([rows[i][1] for i in indices])
                )
                for slot, i in enumerate(indices):
                    got[i] = (
                        [int(x) for x in boards[slot]], int(evaluations[slot]),
                        float(scores[slot]), gpu.windows[int(winner[slot])][0],
                    )
            gpu.close()
            cell = cells.setdefault(f"{climb_name}/{kind}", {"settings": 0, "identical": 0})
            for index, (names, row) in enumerate(rows):
                table = enigma_fast.position_permutations(
                    [enigma_fast.rotor_tables(name) for name in names], row[:3], row[3:],
                    len(body), reflector,
                )
                expected = tuple(batched_outcome(scorer, body, table, climb))
                outcome = got[index]
                worst = max(worst, abs(outcome[2] - expected[2]))
                same = outcome[0] == list(expected[0]) and outcome[1] == expected[1] and (
                    outcome[3] == expected[3] and abs(outcome[2] - expected[2]) <= 1e-9
                )
                cell["settings"] += 1
                cell["identical"] += same
                if not same and len(mismatches) < 10:
                    mismatches.append({"climb": climb_name, "kind": kind, "body": body,
                                       "rotor_order": names, "setting": row,
                                       "cuda": outcome, "batched": expected})
            done += len(rows)
    total = sum(cell["settings"] for cell in cells.values())
    identical = sum(cell["identical"] for cell in cells.values())
    return {
        "mode": "random", "seed": arguments.seed, "settings_per_climb": arguments.settings,
        "settings_compared": total, "identical": identical, "cells": cells,
        "worst_absolute_score_difference": worst, "mismatches": mismatches,
        "seconds": round(time.monotonic() - started, 1), "passed": identical == total,
    }


def split_parity(arguments) -> dict:
    config = stecker.load_config(V4)
    scorer = FastNgramScorer(config["scorer"])
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])
    generator = random.Random(arguments.seed)
    power = stecker.load_config(ROOT / "experiments/phase1-split-point-power-v1/config.json")
    source = normalize_plaintext(power["end_to_end_power"]["plaintext"])
    climb = {key: value for key, value in config["climb"].items() if key != "window"}
    climb["split"] = {"ic_grid": arguments.grid, "block": 64, "mask_term": -8.66}
    kinds = ("clean", "indel", "masked_indel", "short")
    cells: dict[str, dict[str, int]] = {}
    hypotheses: dict[str, int] = {}
    worst = 0.0
    mismatches = []
    started = time.monotonic()
    done = body_index = 0
    while done < arguments.settings:
        kind = kinds[body_index % len(kinds)]
        body_index += 1
        length = generator.randrange(8, 60) if kind == "short" else generator.randrange(140, 168)
        offset = generator.randrange(0, len(source) - length)
        order = tuple(generator.sample(WHEELS, 3))
        rings = [generator.randrange(26) for _ in range(3)]
        start = [generator.randrange(26) for _ in range(3)]
        ciphertext = EnigmaI(
            rotors=order,
            rings="".join(chr(65 + value) for value in rings),
            positions="".join(chr(65 + value) for value in start),
            plugboard=random_plugboard(generator, 10),
        ).crypt(source[offset:offset + length])
        if kind != "clean" and (kind != "short" or generator.random() < 0.5):
            ciphertext = perturb_ciphertext(ciphertext, "indel", generator)[0]
        body = list(enigma_fast.text_to_indices(ciphertext))
        if kind == "masked_indel":
            for position in generator.sample(range(len(body)), generator.randrange(1, 6)):
                body[position] = -1
        rows = [(order, rings + start)] + [
            (tuple(generator.sample(WHEELS, 3)), [generator.randrange(26) for _ in range(6)])
            for _ in range(arguments.per_body - 1)
        ]
        cpu = stecker_split.SplitClimber(scorer.bigram, scorer.combined, body, climb)
        gpu = stecker_cuda.CudaSplitClimber(scorer.bigram, scorer.combined, body, climb, reflector)
        cell = cells.setdefault(kind, {"settings": 0, "identical": 0})
        for names, row in rows:
            table = enigma_fast.position_permutations(
                [enigma_fast.rotor_tables(name) for name in names], row[:3], row[3:],
                len(body) + 1, reflector,
            )
            expected = cpu.climb(table)
            got = gpu.climb_one(names, row[:3], row[3:])
            worst = max(worst, abs(got[2] - expected[2]))
            same = (got[0], got[1], got[2], tuple(got[3])) == (
                list(expected[0]), expected[1], expected[2], tuple(expected[3])
            )
            cell["settings"] += 1
            cell["identical"] += same
            hypotheses[expected[3][0]] = hypotheses.get(expected[3][0], 0) + 1
            if not same and len(mismatches) < 10:
                mismatches.append({"kind": kind, "body": body, "rotor_order": names, "setting": row,
                                   "cuda": got, "batched": expected})
        gpu.close()
        done += len(rows)
    total = sum(cell["settings"] for cell in cells.values())
    identical = sum(cell["identical"] for cell in cells.values())
    return {
        "mode": "split", "seed": arguments.seed, "ic_grid": arguments.grid,
        "settings_compared": total, "identical": identical, "cells": cells,
        "final_hypotheses": hypotheses, "worst_absolute_score_difference": worst,
        "mismatches": mismatches, "seconds": round(time.monotonic() - started, 1),
        "passed": identical == total,
    }


def chunk_parity(arguments) -> dict:
    config = stecker.load_config(pathlib.Path(arguments.config))
    settings = config["body_direct_sweep"]
    traffic = traffic_from_corpus(
        stecker.resolve_path(config["corpus"]), config["target"]["date"], config["target"]["messages"]
    )
    message = {m.designator: m for m in traffic}[settings["message"]]
    rule = RingRule.from_config(settings, len(message.body))
    starts = [
        (left, middle, right)
        for left in resolve_axis(settings["start_left"])
        for middle in resolve_axis(settings["start_middle"])
        for right in resolve_axis(settings["start_right"])
    ]
    orders = rotor_order_space(config["machine"]["rotor_orders"], config["machine"]["wheel_set"])
    chunks = {key: (index, names, group) for index, (key, names, group) in enumerate(sweep_chunks(orders, starts))}
    recorded = [json.loads(line) for line in pathlib.Path(arguments.checkpoint).read_text().splitlines() if line.strip()]
    if arguments.chunks:
        recorded = recorded[: arguments.chunks]
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])
    _worker_init(dict(config["scorer"]), list(message.body),
                 {**config["climb"], "engine": "cuda"}, list(reflector))
    fields = ("local", "rotor_order", "rings", "start", "plugboard", "plugboard_pairs", "evaluations", "window")
    rows = []
    started = time.monotonic()
    for want in recorded:
        key = want["key"]
        index, names, group = chunks[key]
        began = time.monotonic()
        got = _worker_chunk((index, key, names, group, rule, int(settings["keep"])))
        seconds = time.monotonic() - began
        top_identical = len(got["top"]) == len(want["top"]) and all(
            all(a.get(f) == b.get(f) for f in fields) for a, b in zip(got["top"], want["top"])
        )
        worst = max((abs(a["score_per_letter"] - b["score_per_letter"])
                     for a, b in zip(got["top"], want["top"])), default=0.0)
        relative = {name: abs(got[name] - want[name]) / max(abs(want[name]), 1e-300)
                    for name in ("mean", "m2", "max")}
        rows.append({
            "key": key, "evaluated": got["evaluated"],
            "evaluated_equal": got["evaluated"] == want["evaluated"],
            "top_rows_identical": top_identical, "worst_top_score_difference": worst,
            "relative_differences": relative,
            "record_identical": json.dumps(got) == json.dumps({k: v for k, v in want.items() if k != "fingerprint"}),
            "seconds": round(seconds, 3),
            "passed": got["evaluated"] == want["evaluated"] and top_identical and worst <= 1e-9
            and all(value <= 1e-9 for value in relative.values()),
        })
    return {
        "mode": "chunks", "config": arguments.config, "chunks_compared": len(rows),
        "settings_compared": sum(row["evaluated"] for row in rows),
        "chunks_passed": sum(row["passed"] for row in rows),
        "records_byte_identical": sum(row["record_identical"] for row in rows),
        "seconds": round(time.monotonic() - started, 1), "rows": rows,
        "passed": all(row["passed"] for row in rows),
    }


def read_records(path: pathlib.Path) -> tuple[dict, str]:
    import hashlib

    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:  # a final line cut off by a stop
            continue
        records[record["key"]] = record
    return records, hashlib.sha256(path.read_bytes()).hexdigest()


def record_digest(record: dict) -> str:
    import hashlib

    body = {key: value for key, value in record.items() if key != "fingerprint"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def compare_checkpoints(arguments) -> dict:
    reference, reference_sha = read_records(pathlib.Path(arguments.reference))
    candidate, candidate_sha = read_records(pathlib.Path(arguments.candidate))
    rows = []
    for key, record in sorted(reference.items(), key=lambda item: item[1]["index"]):
        other = candidate.get(key)
        rows.append({
            "key": key,
            "index": record["index"],
            "evaluated": record["evaluated"],
            "mean": record["mean"],
            "m2": record["m2"],
            "max": record["max"],
            "record_sha256": record_digest(record),
            "identical": other is not None and record_digest(other) == record_digest(record),
        })
    return {
        "mode": "compare",
        "comparison": "each reference chunk record against the candidate's record for the same chunk, "
                      "as canonical JSON without the checkpoint fingerprint",
        "reference": {"path": arguments.reference, "sha256": reference_sha, "chunks": len(reference),
                      "fingerprints": sorted({r["fingerprint"] for r in reference.values()})},
        "candidate": {"path": arguments.candidate, "sha256": candidate_sha, "chunks": len(candidate),
                      "fingerprints": sorted({r["fingerprint"] for r in candidate.values()})},
        "chunks_compared": len(rows),
        "settings_compared": sum(row["evaluated"] for row in rows),
        "chunks_identical": sum(row["identical"] for row in rows),
        "rows": rows,
        "passed": all(row["identical"] for row in rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="mode", required=True)
    random_mode = commands.add_parser("random")
    random_mode.add_argument("--settings", type=int, default=2000, help="settings per climb (whole, W = 117)")
    random_mode.add_argument("--per-body", type=int, default=20)
    random_mode.add_argument("--seed", type=int, default=20261008)
    split_mode = commands.add_parser("split")
    split_mode.add_argument("--settings", type=int, default=2000)
    split_mode.add_argument("--per-body", type=int, default=10)
    split_mode.add_argument("--grid", type=int, default=32)
    split_mode.add_argument("--seed", type=int, default=20261009)
    chunk_mode = commands.add_parser("chunks")
    chunk_mode.add_argument("--config", default=str(V4))
    chunk_mode.add_argument("--checkpoint", required=True)
    chunk_mode.add_argument("--chunks", type=int, default=0, help="first N records (0: all)")
    compare_mode = commands.add_parser("compare")
    compare_mode.add_argument("--reference", required=True, help="the checkpoint whose chunks are checked")
    compare_mode.add_argument("--candidate", required=True, help="the checkpoint they are checked against")
    for command in (random_mode, split_mode, chunk_mode, compare_mode):
        command.add_argument("--output", default=None, help="write the JSON report here")
    arguments = parser.parse_args(argv)
    if arguments.mode == "compare":
        report = compare_checkpoints(arguments)
        if arguments.output:
            pathlib.Path(arguments.output).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
        return 0 if report["passed"] else 1
    if not stecker_cuda.available():
        print(f"cuda engine unavailable: {stecker_cuda.unavailable_reason()}", file=sys.stderr)
        return 2
    report = {"random": random_parity, "split": split_parity, "chunks": chunk_parity}[arguments.mode](arguments)
    report["device"] = stecker_cuda.device_info()
    text = json.dumps(report, indent=2)
    if arguments.output:
        pathlib.Path(arguments.output).write_text(text + "\n", encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in ("rows", "mismatches")}
    print(json.dumps(summary, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
