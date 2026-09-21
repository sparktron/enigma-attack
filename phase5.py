"""Phase 5 ciphertext-only model triage for alternative cipher families.

This module does not identify a cipher from a short ciphertext.  It measures a
small set of transparent structural signals, calibrates them against a uniform
random null with deterministic Monte Carlo trials, and routes each message to
the next family-specific experiment.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import pathlib
import random
from typing import Any, Mapping, Sequence

from phase1 import load_corpus


ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CORPUS = ROOT / "corpus.json"
DEFAULT_CATALOG = ROOT / "cipher-families.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "phase5-model-triage.json"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
RANDOM_IC = 1.0 / len(ALPHABET)


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_text(text: str) -> str:
    text = text.upper()
    invalid = sorted(set(text) - set(ALPHABET) - {"?"})
    if invalid:
        raise ValueError(f"ciphertext contains invalid characters: {invalid}")
    return text


def index_of_coincidence(text: str) -> float:
    known = [character for character in _validated_text(text) if character != "?"]
    if len(known) < 2:
        return 0.0
    counts = collections.Counter(known)
    numerator = sum(count * (count - 1) for count in counts.values())
    return numerator / (len(known) * (len(known) - 1))


def uniform_chi_square(text: str) -> float:
    known = [character for character in _validated_text(text) if character != "?"]
    if not known:
        return 0.0
    expected = len(known) / len(ALPHABET)
    counts = collections.Counter(known)
    return sum(
        (counts[character] - expected) ** 2 / expected for character in ALPHABET
    )


def entropy_bits(text: str) -> float:
    known = [character for character in _validated_text(text) if character != "?"]
    if not known:
        return 0.0
    counts = collections.Counter(known)
    return -sum(
        (count / len(known)) * math.log2(count / len(known))
        for count in counts.values()
    )


def repeated_ngram_pairs(text: str, width: int = 3) -> int:
    text = _validated_text(text)
    if width < 1:
        raise ValueError("ngram width must be positive")
    counts = collections.Counter(
        text[index : index + width]
        for index in range(len(text) - width + 1)
        if "?" not in text[index : index + width]
    )
    return sum(count * (count - 1) // 2 for count in counts.values())


def lag_profile(text: str, max_lag: int = 30) -> list[dict[str, float | int]]:
    text = _validated_text(text)
    profile: list[dict[str, float | int]] = []
    for lag in range(1, min(max_lag, len(text) - 1) + 1):
        pairs = [
            (left, right)
            for left, right in zip(text[:-lag], text[lag:])
            if left != "?" and right != "?"
        ]
        eligible = len(pairs)
        matches = sum(left == right for left, right in pairs)
        expected = eligible * RANDOM_IC
        variance = eligible * RANDOM_IC * (1.0 - RANDOM_IC)
        z_score = (matches - expected) / math.sqrt(variance) if variance else 0.0
        profile.append(
            {
                "lag": lag,
                "eligible_pairs": eligible,
                "matches": matches,
                "rate": matches / eligible if eligible else 0.0,
                "z_score": z_score,
            }
        )
    return profile


def periodic_ic_profile(
    text: str, max_period: int = 20
) -> list[dict[str, float | int]]:
    text = _validated_text(text)
    profile: list[dict[str, float | int]] = []
    for period in range(2, min(max_period, len(text) // 2) + 1):
        numerator = 0
        denominator = 0
        for residue in range(period):
            column = [
                text[index]
                for index in range(residue, len(text), period)
                if text[index] != "?"
            ]
            counts = collections.Counter(column)
            numerator += sum(count * (count - 1) for count in counts.values())
            denominator += len(column) * (len(column) - 1)
        value = numerator / denominator if denominator else 0.0
        profile.append(
            {
                "period": period,
                "pooled_within_column_ic": value,
                "lift_over_global_ic": value - index_of_coincidence(text),
            }
        )
    return profile


def _feature_vector(text: str, max_period: int, max_lag: int) -> dict[str, Any]:
    lags = lag_profile(text, max_lag=max_lag)
    periods = periodic_ic_profile(text, max_period=max_period)
    best_lag = max(lags, key=lambda item: float(item["z_score"]), default=None)
    best_period = max(
        periods,
        key=lambda item: float(item["pooled_within_column_ic"]),
        default=None,
    )
    return {
        "index_of_coincidence": index_of_coincidence(text),
        "uniform_chi_square": uniform_chi_square(text),
        "entropy_bits": entropy_bits(text),
        "trigram_repeat_pairs": repeated_ngram_pairs(text, 3),
        "best_lag": best_lag,
        "best_period": best_period,
    }


def _trial_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _uniform_trial(template: str, rng: random.Random) -> str:
    return "".join(
        "?" if character == "?" else rng.choice(ALPHABET) for character in template
    )


def _upper_tail(observed: float, null_values: Sequence[float]) -> float:
    exceedances = sum(value >= observed for value in null_values)
    return (exceedances + 1) / (len(null_values) + 1)


def analyze_ciphertext(
    text: str,
    *,
    simulations: int = 4000,
    seed: int = 20260921,
    label: str = "message",
    max_period: int = 20,
    max_lag: int = 30,
    alpha: float = 0.01,
) -> dict[str, Any]:
    if simulations < 1:
        raise ValueError("simulations must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    text = _validated_text(text)
    observed = _feature_vector(text, max_period=max_period, max_lag=max_lag)
    rng = random.Random(_trial_seed(seed, label))
    null_vectors = [
        _feature_vector(
            _uniform_trial(text, rng),
            max_period=max_period,
            max_lag=max_lag,
        )
        for _ in range(simulations)
    ]

    def values(key: str) -> list[float]:
        return [float(vector[key]) for vector in null_vectors]

    observed_lag_z = (
        float(observed["best_lag"]["z_score"]) if observed["best_lag"] else 0.0
    )
    observed_period_ic = (
        float(observed["best_period"]["pooled_within_column_ic"])
        if observed["best_period"]
        else 0.0
    )
    p_values = {
        "ic_upper": _upper_tail(
            float(observed["index_of_coincidence"]),
            values("index_of_coincidence"),
        ),
        "chi_square_upper": _upper_tail(
            float(observed["uniform_chi_square"]), values("uniform_chi_square")
        ),
        "trigram_repeats_upper": _upper_tail(
            float(observed["trigram_repeat_pairs"]),
            values("trigram_repeat_pairs"),
        ),
        "max_lag_upper": _upper_tail(
            observed_lag_z,
            [
                float(vector["best_lag"]["z_score"])
                if vector["best_lag"]
                else 0.0
                for vector in null_vectors
            ],
        ),
        "max_periodic_ic_upper": _upper_tail(
            observed_period_ic,
            [
                float(vector["best_period"]["pooled_within_column_ic"])
                if vector["best_period"]
                else 0.0
                for vector in null_vectors
            ],
        ),
    }
    best_period = observed["best_period"]
    periodic_lift = (
        float(best_period["lift_over_global_ic"]) if best_period else 0.0
    )
    signals = {
        "frequency_preserving": (
            observed["index_of_coincidence"] > RANDOM_IC
            and p_values["ic_upper"] <= alpha
        ),
        "periodic_structure": (
            p_values["max_periodic_ic_upper"] <= alpha and periodic_lift >= 0.006
        ),
        "repeated_blocks": (
            observed["trigram_repeat_pairs"] > 0
            and p_values["trigram_repeats_upper"] <= alpha
        ),
        "lag_structure": p_values["max_lag_upper"] <= alpha,
    }
    signals["uniform_random_compatible"] = not any(signals.values())
    return {
        "length_total": len(text),
        "length_known": sum(character != "?" for character in text),
        "unknown_positions": [
            index for index, character in enumerate(text) if character == "?"
        ],
        "statistics": observed,
        "uniform_null": {
            "alphabet_size": len(ALPHABET),
            "expected_ic": RANDOM_IC,
            "simulations": simulations,
            "seed": _trial_seed(seed, label),
            "multiple_scan_note": (
                "Lag and period p-values compare the observed maximum with each "
                "trial maximum, accounting for the configured scan range."
            ),
            "p_values": p_values,
        },
        "alpha": alpha,
        "signals": signals,
    }


def load_family_catalog(path: pathlib.Path = DEFAULT_CATALOG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    families = payload.get("families")
    sources = payload.get("sources")
    if not isinstance(families, list) or not families:
        raise ValueError("family catalog must contain a non-empty families list")
    if not isinstance(sources, list) or not sources:
        raise ValueError("family catalog must contain a non-empty sources list")
    source_ids = {source["id"] for source in sources}
    family_ids: set[str] = set()
    valid_signatures = {"frequency_preserving", "periodic", "repeated_blocks", "randomizing"}
    for family in families:
        family_id = family["id"]
        if family_id in family_ids:
            raise ValueError(f"duplicate family id: {family_id}")
        family_ids.add(family_id)
        if family["screening_signature"] not in valid_signatures:
            raise ValueError(f"{family_id}: invalid screening signature")
        missing = sorted(set(family["source_ids"]) - source_ids)
        if missing:
            raise ValueError(f"{family_id}: unknown source ids {missing}")
    return payload


def assess_families(
    analysis: Mapping[str, Any], catalog: Mapping[str, Any]
) -> list[dict[str, Any]]:
    signals = analysis["signals"]
    assessments: list[dict[str, Any]] = []
    for family in catalog["families"]:
        signature = family["screening_signature"]
        if signature == "frequency_preserving":
            status = "supported_for_follow_up" if signals[signature] else "not_supported"
        elif signature == "periodic":
            status = "supported_for_follow_up" if signals["periodic_structure"] else "not_supported"
        elif signature == "repeated_blocks":
            status = "supported_for_follow_up" if signals["repeated_blocks"] else "inconclusive"
        else:
            status = (
                "ciphertext_only_compatible"
                if signals["uniform_random_compatible"]
                else "structural_tension"
            )
        assessments.append(
            {
                "family_id": family["id"],
                "label": family["label"],
                "screening_signature": signature,
                "status": status,
                "historical_prior": family["historical_prior"],
                "source_ids": family["source_ids"],
                "limits": family["limits"],
            }
        )
    status_rank = {
        "supported_for_follow_up": 0,
        "ciphertext_only_compatible": 1,
        "inconclusive": 2,
        "structural_tension": 3,
        "not_supported": 4,
    }
    return sorted(assessments, key=lambda item: (status_rank[item["status"]], item["family_id"]))


def route_message(signals: Mapping[str, bool]) -> str:
    if signals["frequency_preserving"]:
        return "frequency_preserving_manual"
    if signals["periodic_structure"]:
        return "periodic_polyalphabetic"
    if signals["repeated_blocks"] or signals["lag_structure"]:
        return "code_superencipherment_or_retransmission"
    return "randomizing_machine_or_combiner"


def _cohort_monogram(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    text = "".join(str(record["ciphertext"]) for record in records)
    return {
        "message_count": len(records),
        "known_letters": sum(character != "?" for character in text),
        "index_of_coincidence": index_of_coincidence(text),
        "uniform_chi_square": uniform_chi_square(text),
        "entropy_bits": entropy_bits(text),
        "scope_note": "Only pooled monographic statistics are valid across independently keyed messages.",
    }


def build_artifact(args: argparse.Namespace) -> dict[str, Any]:
    catalog = load_family_catalog(args.catalog)
    validated = {message.designator: message for message in load_corpus(args.corpus)}
    corpus_payload = json.loads(args.corpus.read_text(encoding="utf-8"))
    records = corpus_payload["messages"]
    analyses: list[dict[str, Any]] = []
    for record in records:
        designator = record["designator"]
        message = validated[designator]
        analysis = analyze_ciphertext(
            message.ciphertext,
            simulations=args.simulations,
            seed=args.seed,
            label=designator,
            max_period=args.max_period,
            max_lag=args.max_lag,
            alpha=args.alpha,
        )
        route = route_message(analysis["signals"])
        analyses.append(
            {
                "designator": designator,
                "date": record["date"],
                "current_status": record.get("current_status", "unknown"),
                "analysis": analysis,
                "route": route,
                "family_assessments": assess_families(analysis, catalog),
            }
        )

    routes = collections.Counter(item["route"] for item in analyses)
    current_unbroken = [
        record
        for record in records
        if str(record.get("current_status", "")).startswith("unbroken_as_of_")
    ]
    priority = sorted(
        analyses,
        key=lambda item: (
            item["route"] != "frequency_preserving_manual",
            item["route"] != "periodic_polyalphabetic",
            item["designator"],
        ),
    )
    return {
        "schema": "enigma-attack.phase5-model-triage/v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {
            "corpus": str(args.corpus),
            "corpus_sha256": _sha256(args.corpus),
            "catalog": str(args.catalog),
            "catalog_sha256": _sha256(args.catalog),
            "runner_sha256": _sha256(pathlib.Path(__file__)),
        },
        "research_boundary": {
            "question": catalog["question"],
            "research_date": catalog["research_date"],
            "sources": catalog["sources"],
            "fact": (
                "The catalog records documented cipher families and cryptanalytic "
                "properties from its cited sources."
            ),
            "inference": (
                "Per-message structural signals can route follow-up experiments but "
                "cannot identify a named cipher system."
            ),
            "speculation": (
                "Any mapping from one Batch C message to a non-Enigma family remains "
                "speculative until a key, plaintext, or archival procedure is found."
            ),
        },
        "method": {
            "null": "independent uniform A-Z symbols with source unknown positions preserved",
            "simulations_per_message": args.simulations,
            "base_seed": args.seed,
            "alpha": args.alpha,
            "max_period": args.max_period,
            "max_lag": args.max_lag,
            "tests": [
                "index of coincidence",
                "chi-square distance from uniform monograms",
                "repeated trigram pair count",
                "maximum lag coincidence z-score",
                "maximum pooled within-column IC over candidate periods",
            ],
            "warning": (
                "Statuses are diagnostic routing labels, not posterior probabilities "
                "or exclusions of a cipher family."
            ),
        },
        "cohorts": {
            "all_messages": _cohort_monogram(records),
            "currently_listed_unbroken": _cohort_monogram(current_unbroken),
        },
        "messages": analyses,
        "model_selection": {
            "route_counts": dict(sorted(routes.items())),
            "heterogeneous_routes": len(routes) > 1,
            "priority_order": [item["designator"] for item in priority],
        },
        "decision": {
            "accepted_break": False,
            "status": "phase5_structural_triage_complete",
            "next_experiment": (
                f"Run a family-specific, held-out-validated experiment for {priority[0]['designator']} "
                f"on route {priority[0]['route']}."
            ),
            "negative_claim": "None; short ciphertexts and a generic null do not exclude any family.",
            "unresolved": [
                "Original five-letter grouping and typography may contain model-selection evidence absent from normalized ciphertext.",
                "QTXMA and SZAEJ are absent from the current three-message unbroken list, but their disposition is not documented in the corpus sources.",
                "Random-like ciphertext cannot distinguish Enigma, cipher teleprinter, and strong superencipherment without traffic metadata or cribs.",
            ],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--catalog", type=pathlib.Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--simulations", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--max-period", type=int, default=20)
    parser.add_argument("--max-lag", type=int, default=30)
    parser.add_argument("--alpha", type=float, default=0.01)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_period < 2:
        raise SystemExit("--max-period must be at least 2")
    if args.max_lag < 1:
        raise SystemExit("--max-lag must be positive")
    artifact = build_artifact(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({len(artifact['messages'])} messages, {args.simulations} null trials each)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
