"""Run the preregistered Phase 6 double-transposition smoke experiment.

This stage follows the Phase 5 routing decision for QTXMA.  It deliberately
uses a bounded key-width search and a scorer that excludes monograms, because
columnar transposition preserves monographic frequencies.  Candidate keys are
selected on a plaintext prefix; the suffix is scored only after selection.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import itertools
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
from typing import Any, Protocol

from phase1 import NGRAM_WEIGHTS, load_corpus


ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = (
    ROOT / "experiments" / "phase6-qtxma-double-transposition-smoke-v1" / "config.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "phase6-qtxma-double-transposition-smoke.json"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class TextScorer(Protocol):
    def score(self, text: str) -> tuple[float, int]: ...


class AdjacencyScorer:
    """Score only order-sensitive n-grams from the Phase 1 bootstrap model."""

    def __init__(self) -> None:
        self.weights = {
            ngram: weight
            for ngram, weight in NGRAM_WEIGHTS.items()
            if len(ngram) >= 2
        }

    def score(self, text: str) -> tuple[float, int]:
        normalized = text.upper()
        known = sum(character in ALPHABET for character in normalized)
        raw = 0.0
        for segment in normalized.split("?"):
            for ngram, weight in self.weights.items():
                width = len(ngram)
                raw += weight * sum(
                    segment[index : index + width] == ngram
                    for index in range(len(segment) - width + 1)
                )
        return raw, known


@dataclasses.dataclass(frozen=True)
class SearchCandidate:
    plaintext: str
    first_order: tuple[int, ...]
    second_order: tuple[int, ...]
    train_score_per_letter: float
    method: str
    evaluations: int


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_path(path: str | pathlib.Path) -> pathlib.Path:
    candidate = pathlib.Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _git_value(*arguments: str) -> str | None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


def code_version() -> dict[str, Any]:
    status = _git_value("status", "--short")
    return {
        "commit": _git_value("rev-parse", "HEAD"),
        "dirty": bool(status),
        "status": status.splitlines() if status else [],
        "runner_sha256": _sha256(pathlib.Path(__file__)),
    }


def _validate_order(order: Sequence[int]) -> tuple[int, ...]:
    normalized = tuple(order)
    if len(normalized) < 2 or sorted(normalized) != list(range(len(normalized))):
        raise ValueError(f"invalid column permutation: {list(order)}")
    return normalized


def columnar_transpose(text: str, order: Sequence[int]) -> str:
    """Write row-wise and read columns in ``order``; ragged rows are allowed."""

    permutation = _validate_order(order)
    width = len(permutation)
    rows = [text[index : index + width] for index in range(0, len(text), width)]
    return "".join(
        row[column]
        for column in permutation
        for row in rows
        if column < len(row)
    )


def columnar_untranspose(text: str, order: Sequence[int]) -> str:
    """Invert :func:`columnar_transpose`, including incomplete final rows."""

    permutation = _validate_order(order)
    width = len(permutation)
    full_rows, remainder = divmod(len(text), width)
    column_lengths = [
        full_rows + (1 if column < remainder else 0) for column in range(width)
    ]
    columns = [""] * width
    cursor = 0
    for column in permutation:
        length = column_lengths[column]
        columns[column] = text[cursor : cursor + length]
        cursor += length
    return "".join(
        columns[column][row]
        for row in range(full_rows + bool(remainder))
        for column in range(width)
        if row < len(columns[column])
    )


def double_columnar_transpose(
    text: str, first_order: Sequence[int], second_order: Sequence[int]
) -> str:
    return columnar_transpose(columnar_transpose(text, first_order), second_order)


def double_columnar_untranspose(
    text: str, first_order: Sequence[int], second_order: Sequence[int]
) -> str:
    return columnar_untranspose(columnar_untranspose(text, second_order), first_order)


def _train_end(length: int, training_fraction: float) -> int:
    if length < 2:
        raise ValueError("search text must contain at least two characters")
    return max(1, min(length - 1, int(length * training_fraction)))


def _score_per_letter(scorer: TextScorer, text: str) -> float:
    raw, known = scorer.score(text)
    return raw / known if known else float("-inf")


def _is_better(candidate: SearchCandidate, incumbent: SearchCandidate | None) -> bool:
    if incumbent is None:
        return True
    if candidate.train_score_per_letter != incumbent.train_score_per_letter:
        return candidate.train_score_per_letter > incumbent.train_score_per_letter
    return (
        candidate.first_order,
        candidate.second_order,
        candidate.plaintext,
    ) < (
        incumbent.first_order,
        incumbent.second_order,
        incumbent.plaintext,
    )


def _exhaustive_pair(
    ciphertext: str,
    first_width: int,
    second_width: int,
    training_fraction: float,
    scorer: TextScorer,
) -> SearchCandidate:
    train_end = _train_end(len(ciphertext), training_fraction)
    best: SearchCandidate | None = None
    evaluations = 0
    first_orders = tuple(itertools.permutations(range(first_width)))
    for second_order in itertools.permutations(range(second_width)):
        intermediate = columnar_untranspose(ciphertext, second_order)
        for first_order in first_orders:
            plaintext = columnar_untranspose(intermediate, first_order)
            score = _score_per_letter(scorer, plaintext[:train_end])
            evaluations += 1
            candidate = SearchCandidate(
                plaintext=plaintext,
                first_order=first_order,
                second_order=second_order,
                train_score_per_letter=score,
                method="exhaustive",
                evaluations=evaluations,
            )
            if _is_better(candidate, best):
                best = candidate
    if best is None:  # pragma: no cover - widths are validated before dispatch
        raise RuntimeError("exhaustive search produced no candidates")
    return dataclasses.replace(best, evaluations=evaluations)


def _mutate_order(order: tuple[int, ...], rng: random.Random) -> tuple[int, ...]:
    mutated = list(order)
    left, right = sorted(rng.sample(range(len(mutated)), 2))
    if len(mutated) > 3 and rng.random() < 0.25:
        mutated[left : right + 1] = reversed(mutated[left : right + 1])
    else:
        mutated[left], mutated[right] = mutated[right], mutated[left]
    return tuple(mutated)


def _anneal_pair(
    ciphertext: str,
    first_width: int,
    second_width: int,
    training_fraction: float,
    scorer: TextScorer,
    *,
    seed: int,
    restarts: int,
    iterations: int,
    temperature_start: float,
    temperature_end: float,
) -> SearchCandidate:
    train_end = _train_end(len(ciphertext), training_fraction)
    rng = random.Random(seed)
    best: SearchCandidate | None = None
    evaluations = 0
    for restart in range(restarts):
        first = list(range(first_width))
        second = list(range(second_width))
        if restart:
            rng.shuffle(first)
            rng.shuffle(second)
        current_first = tuple(first)
        current_second = tuple(second)
        current_plaintext = double_columnar_untranspose(
            ciphertext, current_first, current_second
        )
        current_score = _score_per_letter(scorer, current_plaintext[:train_end])
        evaluations += 1
        initial = SearchCandidate(
            current_plaintext,
            current_first,
            current_second,
            current_score,
            "simulated_annealing",
            evaluations,
        )
        if _is_better(initial, best):
            best = initial

        for iteration in range(iterations):
            fraction = iteration / max(iterations - 1, 1)
            temperature = temperature_start * (
                temperature_end / temperature_start
            ) ** fraction
            if rng.random() < 0.5:
                proposal_first = _mutate_order(current_first, rng)
                proposal_second = current_second
            else:
                proposal_first = current_first
                proposal_second = _mutate_order(current_second, rng)
            proposal_plaintext = double_columnar_untranspose(
                ciphertext, proposal_first, proposal_second
            )
            proposal_score = _score_per_letter(
                scorer, proposal_plaintext[:train_end]
            )
            evaluations += 1
            delta = proposal_score - current_score
            if delta >= 0 or rng.random() < math.exp(delta / temperature):
                current_first = proposal_first
                current_second = proposal_second
                current_plaintext = proposal_plaintext
                current_score = proposal_score
            candidate = SearchCandidate(
                current_plaintext,
                current_first,
                current_second,
                current_score,
                "simulated_annealing",
                evaluations,
            )
            if _is_better(candidate, best):
                best = candidate
    if best is None:  # pragma: no cover - restarts are validated before dispatch
        raise RuntimeError("annealing search produced no candidates")
    return dataclasses.replace(best, evaluations=evaluations)


def search_double_transposition(
    ciphertext: str,
    width_pairs: Sequence[Sequence[int]],
    *,
    training_fraction: float,
    scorer: TextScorer | None = None,
    seed: int = 0,
    max_exhaustive_states: int = 20000,
    restarts: int = 8,
    iterations: int = 1500,
    temperature_start: float = 0.2,
    temperature_end: float = 0.002,
) -> SearchCandidate:
    """Select a candidate without ever passing the held-out suffix to the scorer."""

    if not 0 < training_fraction < 1:
        raise ValueError("training_fraction must be between zero and one")
    if restarts < 1 or iterations < 1:
        raise ValueError("search needs positive restarts and iterations")
    scorer = scorer or AdjacencyScorer()
    best: SearchCandidate | None = None
    total_evaluations = 0
    for pair_index, pair in enumerate(width_pairs):
        if len(pair) != 2 or min(pair) < 2:
            raise ValueError(f"invalid width pair: {pair}")
        first_width, second_width = pair
        state_count = math.factorial(first_width) * math.factorial(second_width)
        if state_count <= max_exhaustive_states:
            candidate = _exhaustive_pair(
                ciphertext,
                first_width,
                second_width,
                training_fraction,
                scorer,
            )
        else:
            pair_seed = int.from_bytes(
                hashlib.sha256(
                    f"{seed}:{pair_index}:{first_width}:{second_width}".encode()
                ).digest()[:8],
                "big",
            )
            candidate = _anneal_pair(
                ciphertext,
                first_width,
                second_width,
                training_fraction,
                scorer,
                seed=pair_seed,
                restarts=restarts,
                iterations=iterations,
                temperature_start=temperature_start,
                temperature_end=temperature_end,
            )
        total_evaluations += candidate.evaluations
        if _is_better(candidate, best):
            best = candidate
    if best is None:
        raise ValueError("at least one width pair is required")
    return dataclasses.replace(best, evaluations=total_evaluations)


def _rounded_score(scorer: TextScorer, text: str) -> dict[str, float | int]:
    raw, known = scorer.score(text)
    return {
        "raw": round(raw, 9),
        "known_letters": known,
        "per_letter": round(raw / known, 9) if known else float("-inf"),
    }


def evaluate_search(
    ciphertext: str,
    candidate: SearchCandidate,
    training_fraction: float,
    scorer: TextScorer,
) -> dict[str, Any]:
    """Score the held-out suffix only after the search has selected a key."""

    train_end = _train_end(len(ciphertext), training_fraction)
    baseline_train = _rounded_score(scorer, ciphertext[:train_end])
    baseline_held_out = _rounded_score(scorer, ciphertext[train_end:])
    candidate_train = _rounded_score(scorer, candidate.plaintext[:train_end])
    candidate_held_out = _rounded_score(scorer, candidate.plaintext[train_end:])
    return {
        "ciphertext_length": len(ciphertext),
        "training_characters": train_end,
        "held_out_characters": len(ciphertext) - train_end,
        "method": candidate.method,
        "evaluations": candidate.evaluations,
        "key": {
            "first_order": list(candidate.first_order),
            "second_order": list(candidate.second_order),
        },
        "baseline": {
            "training": baseline_train,
            "held_out": baseline_held_out,
        },
        "candidate": {
            "plaintext": candidate.plaintext,
            "training": candidate_train,
            "held_out": candidate_held_out,
        },
        "delta": {
            "training_score_per_letter": round(
                candidate_train["per_letter"] - baseline_train["per_letter"], 9
            ),
            "held_out_score_per_letter": round(
                candidate_held_out["per_letter"]
                - baseline_held_out["per_letter"],
                9,
            ),
        },
    }


def _substitute(text: str, cipher_alphabet: str) -> str:
    if sorted(cipher_alphabet) != sorted(ALPHABET):
        raise ValueError("substitution cipher_alphabet must permute A-Z")
    table = str.maketrans(ALPHABET, cipher_alphabet)
    return text.translate(table)


def _search_options(config: Mapping[str, Any]) -> dict[str, Any]:
    search = config["search"]
    return {
        "training_fraction": config["split"]["training_fraction"],
        "max_exhaustive_states": search["max_exhaustive_states"],
        "restarts": search["restarts"],
        "iterations": search["iterations"],
        "temperature_start": search["temperature_start"],
        "temperature_end": search["temperature_end"],
    }


def load_config(path: pathlib.Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "enigma-attack.phase6-config/v1":
        raise ValueError("unsupported Phase 6 configuration schema")
    if payload["search"]["algorithm"] != "bounded_exhaustive_or_annealing":
        raise ValueError("unsupported Phase 6 optimizer")
    fraction = payload["split"]["training_fraction"]
    if not 0 < fraction < 1:
        raise ValueError("training_fraction must be between zero and one")
    search = payload["search"]
    if not search["seeds"] or search["restarts"] < 1 or search["iterations"] < 1:
        raise ValueError("search needs seeds, positive restarts, and iterations")
    if not 0 < search["temperature_end"] <= search["temperature_start"]:
        raise ValueError("invalid annealing temperatures")
    for name in ("target_width_pairs", "control_width_pairs"):
        if not search[name]:
            raise ValueError(f"{name} cannot be empty")
        for pair in search[name]:
            if len(pair) != 2 or min(pair) < 2:
                raise ValueError(f"invalid width pair in {name}: {pair}")
    positive = payload["positive_control"]
    _validate_order(positive["first_order"])
    _validate_order(positive["second_order"])
    _substitute("A", payload["substitution_control"]["cipher_alphabet"])
    acceptance = payload["acceptance"]
    if acceptance["minimum_passing_seeds"] > len(search["seeds"]):
        raise ValueError("minimum_passing_seeds exceeds configured seeds")
    return payload


def _phase5_evidence(path: pathlib.Path, designator: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    supported_schemas = {
        "enigma-attack.phase5-model-triage/v1",
        "enigma-attack.phase5-model-triage/v2",
    }
    if payload.get("schema") not in supported_schemas:
        raise ValueError("unsupported Phase 5 artifact schema")
    try:
        message = next(
            item for item in payload["messages"] if item["designator"] == designator
        )
    except StopIteration as error:
        raise ValueError(f"Phase 5 artifact does not contain {designator}") from error
    if message["route"] != "frequency_preserving_manual":
        raise ValueError(
            f"Phase 5 did not route {designator} to frequency_preserving_manual"
        )
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "route": message["route"],
        "signals": message["analysis"]["signals"],
    }


def run_experiment(
    config: Mapping[str, Any],
    config_path: pathlib.Path,
    arguments: Sequence[str],
    scorer: TextScorer | None = None,
) -> dict[str, Any]:
    corpus_path = _resolve_path(config["corpus"])
    phase5_path = _resolve_path(config["phase5_artifact"])
    target_name = config["target_designator"]
    try:
        target = next(
            message for message in load_corpus(corpus_path) if message.designator == target_name
        )
    except StopIteration as error:
        raise ValueError(f"corpus does not contain {target_name}") from error
    phase5 = _phase5_evidence(phase5_path, target_name)
    scorer = scorer or AdjacencyScorer()
    search = config["search"]
    options = _search_options(config)
    training_fraction = config["split"]["training_fraction"]
    started_at = dt.datetime.now(dt.timezone.utc)
    started_clock = time.perf_counter()

    positive_plaintext = config["positive_control"]["plaintext"]
    positive_ciphertext = double_columnar_transpose(
        positive_plaintext,
        config["positive_control"]["first_order"],
        config["positive_control"]["second_order"],
    )
    positive_candidate = search_double_transposition(
        positive_ciphertext,
        search["control_width_pairs"],
        scorer=scorer,
        seed=search["seeds"][0],
        **options,
    )
    positive_result = evaluate_search(
        positive_ciphertext, positive_candidate, training_fraction, scorer
    )
    positive_accuracy = sum(
        observed == expected
        for observed, expected in zip(positive_candidate.plaintext, positive_plaintext)
    ) / len(positive_plaintext)
    positive_result["plaintext_accuracy"] = round(positive_accuracy, 9)
    positive_result["known_key"] = {
        "first_order": list(config["positive_control"]["first_order"]),
        "second_order": list(config["positive_control"]["second_order"]),
    }

    substitution_ciphertext = _substitute(
        positive_plaintext,
        config["substitution_control"]["cipher_alphabet"],
    )
    substitution_candidate = search_double_transposition(
        substitution_ciphertext,
        search["control_width_pairs"],
        scorer=scorer,
        seed=search["seeds"][0],
        **options,
    )
    substitution_result = evaluate_search(
        substitution_ciphertext,
        substitution_candidate,
        training_fraction,
        scorer,
    )

    target_results = []
    for seed in search["seeds"]:
        candidate = search_double_transposition(
            target.ciphertext,
            search["target_width_pairs"],
            scorer=scorer,
            seed=seed,
            **options,
        )
        result = evaluate_search(target.ciphertext, candidate, training_fraction, scorer)
        result["seed"] = seed
        target_results.append(result)

    acceptance = config["acceptance"]
    positive_passed = (
        positive_accuracy >= acceptance["minimum_positive_plaintext_accuracy"]
        and positive_result["delta"]["held_out_score_per_letter"]
        >= acceptance["minimum_positive_held_out_delta"]
    )
    held_out_deltas = [
        result["delta"]["held_out_score_per_letter"] for result in target_results
    ]
    passing_seeds = sum(
        delta >= acceptance["minimum_seed_held_out_delta"]
        for delta in held_out_deltas
    )
    median_delta = statistics.median(held_out_deltas)
    substitution_delta = substitution_result["delta"]["held_out_score_per_letter"]
    margin = median_delta - substitution_delta
    hypothesis_supported = (
        positive_passed
        and passing_seeds >= acceptance["minimum_passing_seeds"]
        and median_delta >= acceptance["minimum_median_held_out_delta"]
        and margin >= acceptance["minimum_margin_over_substitution_control"]
    )

    if not positive_passed:
        status = "invalid_positive_control_failure"
        interpretation = (
            "The bounded search failed its preregistered true-transposition control, "
            "so the target result is not interpretable."
        )
        next_decision = "Strengthen the scorer or optimizer before rerunning any target search."
    elif hypothesis_supported:
        status = "supported_under_preregistered_smoke"
        interpretation = (
            "The bounded transposition model improved an unscored target suffix and "
            "cleared the substitution-control margin. This is only model evidence, "
            "not an accepted plaintext."
        )
        next_decision = (
            "Require readable German, cross-seed key convergence, a wider key-length "
            "search, and independent scoring before treating the candidate as a break."
        )
    else:
        status = "not_supported_under_preregistered_smoke"
        interpretation = (
            "The true-transposition control passed, but the bounded QTXMA search did "
            "not satisfy the held-out and substitution-control criteria. This does "
            "not exclude widths or procedures outside the preregistered smoke search."
        )
        next_decision = (
            "Do not enlarge the search solely from training-score improvements; first "
            "recover original grouping or add a stronger independently validated scorer."
        )

    finished_at = dt.datetime.now(dt.timezone.utc)
    return {
        "schema": "enigma-attack.phase6-experiment/v1",
        "experiment_id": config["experiment_id"],
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "status": status,
        "hypothesis_supported": hypothesis_supported,
        "accepted_break": False,
        "configuration": {
            "path": str(config_path),
            "sha256": _sha256(config_path),
            "exact_arguments": list(arguments),
            "payload": config,
        },
        "code": code_version(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "parallel_workers": 1,
            "determinism_note": (
                "Each seed uses local random.Random instances; exhaustive branches "
                "and all seed runs execute serially."
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
            "phase5_evidence": phase5,
        },
        "method": {
            "cipher": "double columnar transposition with ragged final rows",
            "selection_boundary": (
                "Candidate keys are selected from the training prefix only; held-out "
                "suffix scores are computed after key selection."
            ),
            "score": (
                "Order-sensitive length-two-or-longer n-grams from the Phase 1 "
                "bootstrap model; monogram terms excluded."
            ),
        },
        "controls": {
            "positive_double_transposition": positive_result,
            "monoalphabetic_substitution": substitution_result,
            "positive_passed": positive_passed,
        },
        "target": {
            "designator": target_name,
            "seed_results": target_results,
        },
        "observed": {
            "held_out_deltas_by_seed": held_out_deltas,
            "passing_seed_count": passing_seeds,
            "seed_count": len(target_results),
            "median_held_out_delta": round(median_delta, 9),
            "substitution_control_held_out_delta": substitution_delta,
            "median_margin_over_substitution_control": round(margin, 9),
        },
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
    output = args.output or _resolve_path(config.get("output", DEFAULT_OUTPUT))
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
