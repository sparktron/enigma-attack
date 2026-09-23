"""Source audit and independently checked 1941 Army n-gram experiment."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import platform
import random
import sys
from collections.abc import Mapping, Sequence
from typing import Any

import phase6

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "experiments/phase7-qtxma-source-and-scorer-v2/config.json"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def resolve_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else ROOT / path


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_counts(path: pathlib.Path, width: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        fields = line.split()
        if len(fields) != 2:
            raise ValueError(f"invalid frequency row at {path}:{number}")
        ngram, raw_count = fields
        if len(ngram) != width or any(letter not in ALPHABET for letter in ngram):
            raise ValueError(f"invalid n-gram at {path}:{number}")
        count = int(raw_count)
        if count <= 0 or ngram in counts:
            raise ValueError(f"invalid or duplicate count at {path}:{number}")
        counts[ngram] = count
    if not counts:
        raise ValueError(f"empty frequency table: {path}")
    return counts


class PublishedNgramScorer:
    """Smoothed log likelihood of adjacent Army-message bigrams and trigrams."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        alpha = float(config["additive_smoothing"])
        if alpha <= 0:
            raise ValueError("additive_smoothing must be positive")
        weights = {2: float(config["bigram_weight"]), 3: float(config["trigram_weight"])}
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("n-gram weights must be nonnegative and nonzero")
        self.tables: dict[int, dict[str, float]] = {}
        self.floors: dict[int, float] = {}
        self.weights = weights
        for width, key in ((2, "bigram_counts"), (3, "trigram_counts")):
            counts = load_counts(resolve_path(config[key]), width)
            denominator = sum(counts.values()) + alpha * (26**width)
            self.tables[width] = {
                ngram: math.log((count + alpha) / denominator)
                for ngram, count in counts.items()
            }
            self.floors[width] = math.log(alpha / denominator)

    def score(self, text: str) -> tuple[float, int]:
        normalized = text.upper()
        if any(character not in ALPHABET + "?" for character in normalized):
            raise ValueError("scorer accepts only A-Z and ?")
        total = 0.0
        for width in (2, 3):
            table = self.tables[width]
            floor = self.floors[width]
            weight = self.weights[width]
            for index in range(len(normalized) - width + 1):
                ngram = normalized[index : index + width]
                if "?" not in ngram:
                    total += weight * table.get(ngram, floor)
        return total, sum(character != "?" for character in normalized)


def audit_grouping(config: Mapping[str, Any], corpus_path: pathlib.Path) -> dict[str, Any]:
    source = config["source_form"]
    rows = source["rows"]
    if any(len(row) != 4 for row in rows):
        raise ValueError("source rows must have four groups")
    groups = [group for row in rows for group in row]
    if any(len(group) != 5 or any(c not in ALPHABET for c in group) for group in groups):
        raise ValueError("source groups must be five letters")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    target = next(message for message in corpus["messages"] if message["designator"] == "QTXMA")
    body = "".join(groups[1:])
    checks = {
        "designator_matches": groups[0] == target["designator"],
        "reported_group_count_matches": len(groups) == source["reported_groups"],
        "reported_total_matches": len("".join(groups)) == source["reported_total_letters"],
        "body_length_matches": len(body) == target["ciphertext_length"],
        "body_matches_corpus": body == target["ciphertext"],
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "groups": groups,
        "row_count": len(rows),
        "body_length": len(body),
        "body_sha256": hashlib.sha256(body.encode("ascii")).hexdigest(),
        "source_form": {key: source[key] for key in ("transcription_url", "facsimile_url", "facsimile_sha256")},
        "interpretation": "Published source grouping yields exactly the current 155-letter solver input; no new body boundary or character correction was found.",
    }


def validate_scorer(config: Mapping[str, Any], scorer: PublishedNgramScorer) -> dict[str, Any]:
    settings = config["validation"]
    results = []
    for item in settings["plaintexts"]:
        text = "".join(item["raw"].split()).upper()
        if len(text) < 25 or any(letter not in ALPHABET for letter in text):
            raise ValueError(f"invalid validation text: {item['id']}")
        authentic = scorer.score(text)[0] / len(text)
        shuffles = []
        for seed in settings["shuffle_seeds"]:
            letters = list(text)
            random.Random(seed).shuffle(letters)
            shuffled = "".join(letters)
            shuffles.append(round(scorer.score(shuffled)[0] / len(text), 9))
        results.append({
            "id": item["id"],
            "length": len(text),
            "authentic_score_per_letter": round(authentic, 9),
            "shuffled_scores_per_letter": shuffles,
            "margin_over_best_shuffle": round(authentic - max(shuffles), 9),
            "passed": authentic > max(shuffles),
        })
    passing = sum(result["passed"] for result in results)
    return {
        "source_url": settings["source_url"],
        "shuffle_seeds": settings["shuffle_seeds"],
        "messages": results,
        "passing_messages": passing,
        "required_messages": settings["minimum_messages_above_all_shuffles"],
        "passed": passing >= settings["minimum_messages_above_all_shuffles"],
    }


def run_experiment(config: Mapping[str, Any], config_path: pathlib.Path, arguments: Sequence[str]) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc)
    corpus_path = resolve_path(config["corpus"])
    form = audit_grouping(config, corpus_path)
    scorer = PublishedNgramScorer(config["scorer"])
    validation = validate_scorer(config, scorer)
    phase6_config_path = resolve_path(config["phase6_config"])
    baseline_path = resolve_path(config["phase6_artifact"])
    phase6_config = copy.deepcopy(phase6.load_config(phase6_config_path))
    phase6_config["experiment_id"] = config["experiment_id"]
    phase6_config["search"]["target_width_pairs"] = config["search"]["target_width_pairs"]
    phase6_config["search"]["seeds"] = config["search"]["seeds"]
    if "additional_positive_controls" in config:
        phase6_config["additional_positive_controls"] = config["additional_positive_controls"]
        phase6_config["positive_controls"] = phase6._normalize_positive_controls(phase6_config)
    acceptance = phase6_config["acceptance"]
    positive_results = [
        phase6.evaluate_positive_control(
            control,
            scorer,
            phase6_config["search"]["seeds"][0],
            phase6._search_options(phase6_config),
            phase6_config["split"]["training_fraction"],
            acceptance,
        )
        for control in phase6_config["positive_controls"]
    ]
    positive_passed = all(result["passed"] for result in positive_results)
    positive_result = {
        "controls": positive_results,
        "passed": positive_passed,
        "accuracy_rule": (
            "Best positional agreement over all cyclic rotations of the known "
            "plaintext; the exact-offset agreement is recorded per control."
        ),
    }
    search_result = None
    if form["passed"] and validation["passed"] and positive_passed:
        search_result = phase6.run_experiment(phase6_config, phase6_config_path, arguments, scorer=scorer)
        search_result["method"]["score"] = "Smoothed published 1941 Army plaintext bigram and trigram log likelihood; no monogram terms."
    status = (
        "source_audit_failed" if not form["passed"] else
        "scorer_validation_failed" if not validation["passed"] else
        "invalid_positive_control_failure" if not positive_passed else
        search_result["status"]
    )
    counts = {
        key: {"path": config["scorer"][key], "sha256": sha256(resolve_path(config["scorer"][key]))}
        for key in ("bigram_counts", "trigram_counts")
    }
    return {
        "schema": "enigma-attack.phase7-experiment/v1",
        "experiment_id": config["experiment_id"],
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "status": status,
        "hypothesis_supported": bool(search_result and search_result["hypothesis_supported"]),
        "accepted_break": False,
        "configuration": {"path": str(config_path), "sha256": sha256(config_path), "payload": config, "exact_arguments": list(arguments)},
        "code": {**phase6.code_version(), "branch": phase6._git_value("branch", "--show-current"), "phase7_runner_sha256": sha256(pathlib.Path(__file__))},
        "environment": {"python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(), "parallel_workers": 1, "determinism_note": "Each control shuffle uses its own fixed random.Random seed; the transposition search runs serially."},
        "inputs": {"corpus_sha256": sha256(corpus_path), "phase6_config_sha256": sha256(phase6_config_path), "phase6_baseline_sha256": sha256(baseline_path), "frequency_tables": counts},
        "source_audit": form,
        "scorer_validation": validation,
        "positive_control_preflight": positive_result,
        "search": search_result,
        "baseline": {"experiment_id": "phase6-qtxma-double-transposition-smoke-v1", "artifact": str(baseline_path), "median_held_out_delta": json.loads(baseline_path.read_text(encoding="utf-8"))["observed"]["median_held_out_delta"]},
        "limitations": config["limitations"],
        "interpretation": (
            "Inference: the new scorer passed external plaintext discrimination and the bounded search met its controls and held-out rule; a readable independently reproduced plaintext is still required."
            if search_result and search_result["hypothesis_supported"] else
            "Inference: the preregistered validation or held-out criterion failed; the tested model does not establish a QTXMA transposition break."
        ),
        "next_decision": (
            "Inspect key convergence and candidate plaintext; independently reproduce any readable result before enlarging the search."
            if search_result and search_result["hypothesis_supported"] else
            "Do not expand transposition widths from training gains; seek archival procedure evidence or a separately sourced, held-out Army plaintext model."
        ),
        "timing": {"started_at": started.isoformat(), "finished_at": dt.datetime.now(dt.timezone.utc).isoformat()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=pathlib.Path)
    arguments = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(arguments)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("schema") != "enigma-attack.phase7-config/v1":
        raise ValueError("unsupported Phase 7 configuration schema")
    output = args.output or resolve_path(config["output"])
    result = run_experiment(config, args.config, arguments)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output}; status={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
