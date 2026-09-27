#!/usr/bin/env python3
"""Phase 4: preregistered joint machine-and-daily-key inference experiment."""
from __future__ import annotations

import argparse
import copy
import dataclasses
import datetime as dt
import hashlib
import json
import math
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

from enigma import A, EnigmaMachine, REFLECTOR_WIRINGS, ROTOR_WIRINGS
from phase1 import ArmyGermanScorer, CorpusMessage, load_corpus
import phase3
from resources import resolve_output, resource_root

ROOT = resource_root()
DEFAULT_CONFIG = ROOT / "experiments" / "phase4-joint-machine-smoke-v2" / "config.json"


@dataclass(frozen=True)
class DailyKey:
    rotors: tuple[str, str, str]
    rings: str
    plugboard_pairs: tuple[str, ...] = ()

    @property
    def plugboard(self) -> str:
        return " ".join(self.plugboard_pairs)


@dataclass
class MachineState:
    rotor_wirings: dict[str, tuple[str, str]]
    reflector: str
    entry_wiring: str
    stepping: str
    daily_keys: dict[str, DailyKey]

    def clone(self) -> "MachineState":
        return copy.deepcopy(self)


@dataclass(frozen=True)
class ScoreResult:
    raw_score: float
    known_letters: int
    score_per_letter: float
    messages: tuple[dict[str, Any], ...]


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_path(path: str | pathlib.Path) -> pathlib.Path:
    result = pathlib.Path(path)
    return result if result.is_absolute() else ROOT / result


def _git_value(arguments: Sequence[str]) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip() if process.returncode == 0 else "unavailable"


def code_version() -> dict[str, Any]:
    status = _git_value(["status", "--porcelain"])
    return {
        "commit": _git_value(["rev-parse", "--short", "HEAD"]),
        "branch": _git_value(["branch", "--show-current"]),
        "dirty": bool(status),
        "dirty_entry_count": len(status.splitlines()) if status else 0,
        "runner_sha256": _sha256(pathlib.Path(__file__)),
    }


def load_config(path: pathlib.Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "enigma-attack.phase4-config/v1":
        raise ValueError("unsupported Phase 4 configuration schema")
    optimizer = payload["optimizer"]
    if optimizer["algorithm"] != "alternating_simulated_annealing":
        raise ValueError("unsupported optimizer")
    if optimizer["iterations"] < 1 or not optimizer["seeds"]:
        raise ValueError("optimizer needs positive iterations and at least one seed")
    if (not 0 < optimizer["temperature_end"] <= optimizer["temperature_start"]
            or not all(math.isfinite(optimizer[key]) for key in ("temperature_start", "temperature_end"))):
        raise ValueError("invalid annealing temperatures")
    if optimizer["trace_every"] < 1:
        raise ValueError("trace_every must be positive")
    if not 0 <= optimizer["max_plugboard_pairs"] <= 13:
        raise ValueError("max_plugboard_pairs must be between zero and 13")
    for date, key in payload["initial_daily_keys"].items():
        if len(key.get("plugboard", "").split()) > optimizer["max_plugboard_pairs"]:
            raise ValueError(f"initial plugboard exceeds pair capacity for {date}")
    for name in ("machine_mutation_weights", "daily_mutation_weights", "complexity_penalty"):
        weights = optimizer[name]
        if not weights or any(not math.isfinite(value) or value < 0 for value in weights.values()):
            raise ValueError(f"invalid {name}")
        if name != "complexity_penalty" and sum(weights.values()) <= 0:
            raise ValueError(f"{name} must have positive total weight")
    train = set(payload["split"]["train_designators"])
    held_out = set(payload["split"]["held_out_designators"])
    if not train or not held_out or train.intersection(held_out):
        raise ValueError("train and held-out splits must be nonempty and disjoint")
    acceptance = payload["acceptance"]
    if acceptance["minimum_passing_seeds"] > len(optimizer["seeds"]):
        raise ValueError("minimum passing seeds exceeds configured seeds")
    return payload


def _canonical_pairs(pairs: Sequence[str]) -> tuple[str, ...]:
    canonical = tuple(sorted("".join(sorted(pair)) for pair in pairs))
    used: set[str] = set()
    for pair in canonical:
        if len(pair) != 2 or pair[0] == pair[1] or any(letter not in A for letter in pair):
            raise ValueError(f"invalid plugboard pair: {pair!r}")
        if used.intersection(pair):
            raise ValueError(f"plugboard letter reused: {pair!r}")
        used.update(pair)
    return canonical


def initial_state(config: Mapping[str, Any]) -> MachineState:
    machine = config["initial_machine"]
    rotor_sources = tuple(machine["rotor_sources"])
    if len(rotor_sources) != 3 or len(set(rotor_sources)) != 3:
        raise ValueError("initial_machine.rotor_sources must contain three distinct rotors")
    wirings = {name: ROTOR_WIRINGS[name] for name in rotor_sources}
    daily_keys: dict[str, DailyKey] = {}
    for date, raw in config["initial_daily_keys"].items():
        rotors = tuple(raw["rotors"])
        if len(rotors) != 3 or set(rotors) != set(rotor_sources):
            raise ValueError(f"daily rotor order mismatch for {date}")
        rings = raw["rings"].upper()
        if len(rings) != 3 or any(letter not in A for letter in rings):
            raise ValueError(f"invalid daily rings for {date}")
        daily_keys[date] = DailyKey(
            rotors=rotors,
            rings=rings,
            plugboard_pairs=_canonical_pairs(raw.get("plugboard", "").split()),
        )
    reflector_name = machine["reflector"].upper()
    if reflector_name not in REFLECTOR_WIRINGS:
        raise ValueError(f"unknown initial reflector: {reflector_name}")
    return MachineState(
        rotor_wirings=wirings,
        reflector=REFLECTOR_WIRINGS[reflector_name],
        entry_wiring=machine["entry_wiring"],
        stepping=machine["stepping"],
        daily_keys=daily_keys,
    )


def state_to_dict(state: MachineState) -> dict[str, Any]:
    return {
        "rotor_wirings": {
            name: {"wiring": wiring, "notches": notches}
            for name, (wiring, notches) in sorted(state.rotor_wirings.items())
        },
        "reflector": state.reflector,
        "entry_wiring": state.entry_wiring,
        "stepping": state.stepping,
        "daily_keys": {
            date: {
                "rotors": list(key.rotors),
                "rings": key.rings,
                "plugboard": key.plugboard,
            }
            for date, key in sorted(state.daily_keys.items())
        },
    }


def state_signature(state: MachineState) -> str:
    encoded = json.dumps(state_to_dict(state), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decrypt_message(message: CorpusMessage, state: MachineState) -> tuple[str, str]:
    key = state.daily_keys[message.date]
    common = {
        "rotors": key.rotors,
        "rings": key.rings,
        "plugboard": key.plugboard,
        "rotor_wirings": state.rotor_wirings,
        "reflector": state.reflector,
        "entry_wiring": state.entry_wiring,
        "stepping": state.stepping,
    }
    indicator_machine = EnigmaMachine(
        positions=message.grundstellung,
        **common,
    )
    message_key = indicator_machine.crypt(message.encrypted_message_key)
    body_machine = EnigmaMachine(positions=message_key, **common)
    plaintext: list[str] = []
    for symbol in message.ciphertext:
        if symbol == "?":
            body_machine.key("A")
            plaintext.append("?")
        else:
            plaintext.append(body_machine.key(symbol))
    return message_key, "".join(plaintext)


def score_state(
    state: MachineState,
    messages: Sequence[CorpusMessage],
    scorer: ArmyGermanScorer,
) -> ScoreResult:
    rows: list[dict[str, Any]] = []
    raw_total = 0.0
    known_total = 0
    for message in messages:
        message_key, plaintext = decrypt_message(message, state)
        raw_score, known = scorer.score(plaintext)
        raw_total += raw_score
        known_total += known
        rows.append(
            {
                "date": message.date,
                "designator": message.designator,
                "message_key": message_key,
                "plaintext": plaintext,
                "raw_score": raw_score,
                "known_letters": known,
                "score_per_letter": raw_score / known if known else float("-inf"),
            }
        )
    return ScoreResult(
        raw_score=raw_total,
        known_letters=known_total,
        score_per_letter=raw_total / known_total if known_total else float("-inf"),
        messages=tuple(rows),
    )


def complexity(state: MachineState, baseline: MachineState) -> dict[str, int]:
    rotor_positions = 0
    changed_notches = 0
    for name, (wiring, notches) in state.rotor_wirings.items():
        base_wiring, base_notches = baseline.rotor_wirings[name]
        rotor_positions += sum(left != right for left, right in zip(wiring, base_wiring))
        changed_notches += notches != base_notches
    reflector_positions = sum(
        left != right for left, right in zip(state.reflector, baseline.reflector)
    )
    plugboard_pairs = sum(
        len(key.plugboard_pairs) for key in state.daily_keys.values()
    )
    return {
        "rotor_wiring_changed_positions": rotor_positions,
        "reflector_changed_positions": reflector_positions,
        "changed_notches": changed_notches,
        "plugboard_pairs": plugboard_pairs,
    }


def complexity_penalty(
    state: MachineState,
    baseline: MachineState,
    weights: Mapping[str, float],
) -> tuple[float, dict[str, int]]:
    counts = complexity(state, baseline)
    penalty = (
        counts["rotor_wiring_changed_positions"]
        * weights["rotor_wiring_changed_position"]
        + counts["reflector_changed_positions"]
        * weights["reflector_changed_position"]
        + counts["changed_notches"] * weights["changed_notch"]
        + counts["plugboard_pairs"] * weights["plugboard_pair"]
    )
    return penalty, counts


def _weighted_choice(rng: random.Random, weights: Mapping[str, float]) -> str:
    names = tuple(weights)
    return rng.choices(names, weights=tuple(weights.values()), k=1)[0]


def _mutate_rotor_wiring(state: MachineState, rng: random.Random) -> None:
    name = rng.choice(tuple(state.rotor_wirings))
    wiring, notches = state.rotor_wirings[name]
    first, second = rng.sample(range(26), 2)
    values = list(wiring)
    values[first], values[second] = values[second], values[first]
    state.rotor_wirings[name] = ("".join(values), notches)


def _mutate_reflector(state: MachineState, rng: random.Random) -> None:
    partners = [ord(letter) - 65 for letter in state.reflector]
    first = rng.randrange(26)
    first_partner = partners[first]
    choices = [
        value for value in range(26) if value not in {first, first_partner}
    ]
    second = rng.choice(choices)
    second_partner = partners[second]
    if rng.random() < 0.5:
        new_pairs = ((first, second), (first_partner, second_partner))
    else:
        new_pairs = ((first, second_partner), (first_partner, second))
    for left, right in new_pairs:
        partners[left] = right
        partners[right] = left
    state.reflector = "".join(chr(value + 65) for value in partners)


def _mutate_notch(state: MachineState, rng: random.Random) -> None:
    name = rng.choice(tuple(state.rotor_wirings))
    wiring, notches = state.rotor_wirings[name]
    choices = [letter for letter in A if letter not in notches]
    state.rotor_wirings[name] = (wiring, rng.choice(choices))


def mutate_machine(
    state: MachineState,
    rng: random.Random,
    weights: Mapping[str, float],
) -> tuple[MachineState, str]:
    candidate = state.clone()
    mutation = _weighted_choice(rng, weights)
    if mutation == "rotor_wiring_swap":
        _mutate_rotor_wiring(candidate, rng)
    elif mutation == "reflector_pair_rewire":
        _mutate_reflector(candidate, rng)
    elif mutation == "notch_move":
        _mutate_notch(candidate, rng)
    else:
        raise ValueError(f"unknown machine mutation: {mutation}")
    return candidate, mutation


def _mutate_plugboard(
    pairs: tuple[str, ...],
    rng: random.Random,
    max_pairs: int,
) -> tuple[str, ...]:
    if not 0 <= max_pairs <= 13 or len(pairs) > max_pairs:
        raise ValueError("invalid plugboard pair capacity")
    if max_pairs == 0:
        return pairs
    pair_list = list(pairs)
    used = set("".join(pair_list))
    available_actions = ["edit"] if pair_list else []
    if pair_list:
        available_actions.append("remove")
    if len(pair_list) < max_pairs and len(used) <= 24:
        available_actions.append("add")
    action = rng.choice(available_actions)
    if action == "add":
        first, second = rng.sample([letter for letter in A if letter not in used], 2)
        pair_list.append(first + second)
    elif action == "remove":
        pair_list.pop(rng.randrange(len(pair_list)))
    elif len(pair_list) >= 2:
        first_index, second_index = rng.sample(range(len(pair_list)), 2)
        a, b = pair_list[first_index]
        c, d = pair_list[second_index]
        if rng.random() < 0.5:
            pair_list[first_index], pair_list[second_index] = a + c, b + d
        else:
            pair_list[first_index], pair_list[second_index] = a + d, b + c
    else:
        old_pair = pair_list[0]
        replacement = rng.choice([letter for letter in A if letter not in used])
        if rng.random() < 0.5:
            pair_list[0] = replacement + old_pair[1]
        else:
            pair_list[0] = old_pair[0] + replacement
    return _canonical_pairs(pair_list)


def mutate_daily_key(
    state: MachineState,
    rng: random.Random,
    weights: Mapping[str, float],
    max_plugboard_pairs: int,
) -> tuple[MachineState, str]:
    candidate = state.clone()
    date = rng.choice(tuple(candidate.daily_keys))
    key = candidate.daily_keys[date]
    mutation = _weighted_choice(rng, weights)
    if mutation == "rotor_order_swap":
        first, second = rng.sample(range(3), 2)
        order = list(key.rotors)
        order[first], order[second] = order[second], order[first]
        key = DailyKey(tuple(order), key.rings, key.plugboard_pairs)
    elif mutation == "ring_move":
        position = rng.randrange(3)
        rings = list(key.rings)
        delta = rng.choice((-3, -1, 1, 3))
        rings[position] = A[(A.index(rings[position]) + delta) % 26]
        key = DailyKey(key.rotors, "".join(rings), key.plugboard_pairs)
    elif mutation == "plugboard_edit":
        key = DailyKey(
            key.rotors,
            key.rings,
            _mutate_plugboard(key.plugboard_pairs, rng, max_plugboard_pairs),
        )
    else:
        raise ValueError(f"unknown daily mutation: {mutation}")
    candidate.daily_keys[date] = key
    return candidate, f"{mutation}:{date}"


def _rounded_score(result: ScoreResult) -> dict[str, Any]:
    return {
        "raw_score": round(result.raw_score, 9),
        "known_letters": result.known_letters,
        "score_per_letter": round(result.score_per_letter, 9),
        "messages": [
            {
                **row,
                "raw_score": round(row["raw_score"], 9),
                "score_per_letter": round(row["score_per_letter"], 9),
            }
            for row in result.messages
        ],
    }


def run_seed(
    config: Mapping[str, Any],
    baseline: MachineState,
    train_messages: Sequence[CorpusMessage],
    held_out_messages: Sequence[CorpusMessage],
    scorer: ArmyGermanScorer,
    seed: int,
) -> dict[str, Any]:
    optimizer = config["optimizer"]
    rng = random.Random(seed)
    current = baseline.clone()
    current_train = score_state(current, train_messages, scorer)
    current_penalty, current_complexity = complexity_penalty(
        current,
        baseline,
        optimizer["complexity_penalty"],
    )
    current_objective = current_train.score_per_letter - current_penalty
    best = current.clone()
    best_train = current_train
    best_penalty = current_penalty
    best_complexity = current_complexity
    best_objective = current_objective
    trace: list[dict[str, Any]] = []
    best_updates: list[dict[str, Any]] = []
    mutation_stats: dict[str, dict[str, int]] = {}
    iterations = optimizer["iterations"]
    started = time.perf_counter()

    for iteration in range(1, iterations + 1):
        if iteration % 2:
            candidate, mutation = mutate_machine(
                current,
                rng,
                optimizer["machine_mutation_weights"],
            )
        else:
            candidate, mutation = mutate_daily_key(
                current,
                rng,
                optimizer["daily_mutation_weights"],
                optimizer["max_plugboard_pairs"],
            )
        name = mutation.split(":", 1)[0]
        stats = mutation_stats.setdefault(
            name,
            {"attempted": 0, "accepted": 0, "improved_best": 0},
        )
        stats["attempted"] += 1
        candidate_train = score_state(candidate, train_messages, scorer)
        candidate_penalty, candidate_complexity = complexity_penalty(
            candidate,
            baseline,
            optimizer["complexity_penalty"],
        )
        candidate_objective = candidate_train.score_per_letter - candidate_penalty
        progress = (iteration - 1) / max(iterations - 1, 1)
        temperature = optimizer["temperature_start"] * (
            optimizer["temperature_end"] / optimizer["temperature_start"]
        ) ** progress
        delta = candidate_objective - current_objective
        accepted = delta >= 0 or rng.random() < math.exp(delta / temperature)
        if accepted:
            current = candidate
            current_train = candidate_train
            current_penalty = candidate_penalty
            current_complexity = candidate_complexity
            current_objective = candidate_objective
            stats["accepted"] += 1
        if candidate_objective > best_objective:
            best = candidate.clone()
            best_train = candidate_train
            best_penalty = candidate_penalty
            best_complexity = candidate_complexity
            best_objective = candidate_objective
            stats["improved_best"] += 1
            best_updates.append(
                {
                    "iteration": iteration,
                    "mutation": mutation,
                    "objective": round(best_objective, 9),
                    "train_score_per_letter": round(best_train.score_per_letter, 9),
                    "complexity_penalty": round(best_penalty, 9),
                    "state_signature": state_signature(best),
                }
            )
        if iteration == 1 or iteration % optimizer["trace_every"] == 0:
            trace.append(
                {
                    "iteration": iteration,
                    "temperature": round(temperature, 9),
                    "last_mutation": mutation,
                    "last_mutation_accepted": accepted,
                    "current_objective": round(current_objective, 9),
                    "current_train_score_per_letter": round(
                        current_train.score_per_letter, 9
                    ),
                    "best_objective": round(best_objective, 9),
                    "best_train_score_per_letter": round(
                        best_train.score_per_letter, 9
                    ),
                    "current_complexity": current_complexity,
                }
            )

    held_out_result = score_state(best, held_out_messages, scorer)
    baseline_train = score_state(baseline, train_messages, scorer)
    baseline_held_out = score_state(baseline, held_out_messages, scorer)
    threshold = config["acceptance"]["minimum_held_out_delta_per_seed"]
    held_out_delta = held_out_result.score_per_letter - baseline_held_out.score_per_letter
    return {
        "seed": seed,
        "iterations": iterations,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "best_iteration": best_updates[-1]["iteration"] if best_updates else 0,
        "best_state_signature": state_signature(best),
        "best_state": state_to_dict(best),
        "complexity": best_complexity,
        "complexity_penalty": round(best_penalty, 9),
        "objective": round(best_objective, 9),
        "train": _rounded_score(best_train),
        "held_out": _rounded_score(held_out_result),
        "delta_from_baseline": {
            "train_score_per_letter": round(
                best_train.score_per_letter - baseline_train.score_per_letter, 9
            ),
            "held_out_score_per_letter": round(held_out_delta, 9),
        },
        "passes_preregistered_seed_threshold": held_out_delta >= threshold,
        "mutation_stats": mutation_stats,
        "best_updates": best_updates,
        "trace": trace,
    }


def _split_messages(
    messages: Sequence[CorpusMessage],
    config: Mapping[str, Any],
) -> tuple[list[CorpusMessage], list[CorpusMessage]]:
    train_names = set(config["split"]["train_designators"])
    held_out_names = set(config["split"]["held_out_designators"])
    corpus_names = {message.designator for message in messages}
    requested = train_names | held_out_names
    if requested != corpus_names:
        missing = requested.difference(corpus_names)
        omitted = corpus_names.difference(requested)
        raise ValueError(
            f"split must cover corpus exactly; missing={sorted(missing)}, "
            f"omitted={sorted(omitted)}"
        )
    train = [message for message in messages if message.designator in train_names]
    held_out = [
        message for message in messages if message.designator in held_out_names
    ]
    return train, held_out


def _training_only_baseline(
    config: Mapping[str, Any], train_messages: Sequence[CorpusMessage],
    scorer: ArmyGermanScorer,
) -> tuple[MachineState, dict[str, Any]]:
    """Select each daily key using training messages before evaluating holdouts."""
    baseline = initial_state(config)
    _, profiles = phase3.load_variant_catalog()
    profile = next(item for item in profiles if item.id == "wehrmacht_ukw_b")
    profile = dataclasses.replace(profile, rotor_pool=tuple(baseline.rotor_wirings))
    selections = []
    for date, old_key in baseline.daily_keys.items():
        training = [message for message in train_messages if message.date == date]
        if not training:
            raise ValueError(f"no training message for baseline date {date}")
        top, evaluations = phase3._search_profile_date(
            profile, date, training, (old_key.rings,), ("A",),
            (old_key.plugboard,), scorer, 1,
        )
        winner = top[0]
        baseline.daily_keys[date] = DailyKey(
            tuple(winner["rotors"]), winner["rings"], old_key.plugboard_pairs,
        )
        selections.append({
            "date": date,
            "train_designators": [message.designator for message in training],
            "evaluations": evaluations,
            "score_per_letter": winner["score_per_letter"],
            "daily_key": {"rotors": winner["rotors"], "rings": winner["rings"],
                          "plugboard": winner["plugboard"]},
        })
    return baseline, {
        "selection": "training_only",
        "catalog_sha256": _sha256(phase3.DEFAULT_CATALOG),
        "dates": selections,
    }


def run_experiment(
    config: Mapping[str, Any],
    config_path: pathlib.Path,
    arguments: Sequence[str],
) -> dict[str, Any]:
    corpus_path = _resolve_path(config["corpus"])
    phase3_path = _resolve_path(config["phase3_baseline_artifact"])
    messages = load_corpus(corpus_path)
    train_messages, held_out_messages = _split_messages(messages, config)
    scorer = ArmyGermanScorer()
    baseline, baseline_selection = _training_only_baseline(
        config, train_messages, scorer
    )
    phase3_comparison = {
        "artifact": str(phase3_path), "sha256": _sha256(phase3_path),
        "role": "historical_reference_only_selection_contaminated",
    }
    baseline_train = score_state(baseline, train_messages, scorer)
    baseline_held_out = score_state(baseline, held_out_messages, scorer)
    started_at = dt.datetime.now(dt.timezone.utc)
    started_clock = time.perf_counter()
    version = code_version()

    seed_results = [
        run_seed(
            config,
            baseline,
            train_messages,
            held_out_messages,
            scorer,
            seed,
        )
        for seed in config["optimizer"]["seeds"]
    ]
    held_out_deltas = [
        result["delta_from_baseline"]["held_out_score_per_letter"]
        for result in seed_results
    ]
    passing_seeds = sum(
        result["passes_preregistered_seed_threshold"] for result in seed_results
    )
    median_delta = statistics.median(held_out_deltas)
    acceptance = config["acceptance"]
    hypothesis_supported = (
        passing_seeds >= acceptance["minimum_passing_seeds"]
        and median_delta >= acceptance["minimum_median_held_out_delta"]
    )
    finished_at = dt.datetime.now(dt.timezone.utc)

    observed = {
        "baseline_train_score_per_letter": round(
            baseline_train.score_per_letter, 9
        ),
        "baseline_held_out_score_per_letter": round(
            baseline_held_out.score_per_letter, 9
        ),
        "held_out_deltas_by_seed": held_out_deltas,
        "passing_seed_count": passing_seeds,
        "seed_count": len(seed_results),
        "median_held_out_delta": round(median_delta, 9),
        "best_held_out_delta": max(held_out_deltas),
        "worst_held_out_delta": min(held_out_deltas),
    }
    if hypothesis_supported:
        interpretation = (
            "Inference: the bounded optimizer generalized under the preregistered "
            "language-score metric. This does not establish readable plaintext or "
            "historical correctness; independent confirmation is still required."
        )
        next_decision = (
            "Inspect cross-seed state convergence and plaintext, then reproduce the "
            "result with an independent scorer before expanding the search."
        )
        status = "supported_under_preregistered_metric"
    else:
        interpretation = (
            "Inference: this bounded joint-machine search did not generalize "
            "reliably to unseen messages; training improvements are consistent "
            "with scorer overfitting or a false shared-machine assumption."
        )
        next_decision = (
            "Do not enlarge arbitrary-wiring search from this result. Test corpus "
            "partitioning or a stronger held-out language model first."
        )
        status = "refuted_under_preregistered_metric"

    return {
        "schema": "enigma-attack.phase4-experiment/v1",
        "experiment_id": config["experiment_id"],
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "status": status,
        "hypothesis_supported": hypothesis_supported,
        "configuration": {
            "path": str(config_path),
            "sha256": _sha256(config_path),
            "exact_arguments": list(arguments),
            "payload": config,
        },
        "code": version,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "parallel_workers": 1,
            "determinism_note": (
                "Each seed uses one local random.Random instance and runs serially."
            ),
        },
        "timing": {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "runtime_seconds": round(time.perf_counter() - started_clock, 6),
        },
        "inputs": {
            "corpus": str(corpus_path),
            "corpus_sha256": _sha256(corpus_path),
            "phase3_baseline": phase3_comparison,
            "baseline_selection": baseline_selection,
        },
        "baseline": {
            "state_signature": state_signature(baseline),
            "state": state_to_dict(baseline),
            "train": _rounded_score(baseline_train),
            "held_out": _rounded_score(baseline_held_out),
        },
        "seed_results": seed_results,
        "observed": observed,
        "interpretation": interpretation,
        "next_decision": next_decision,
        "limitations": list(config["notes"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="override the output path recorded in the config",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parsed_arguments = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(parsed_arguments)
    config = load_config(args.config)
    output = args.output or resolve_output(config["output"])
    artifact = run_experiment(config, args.config, parsed_arguments)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {output}; status={artifact['status']}; "
        f"median held-out delta={artifact['observed']['median_held_out_delta']:+.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
