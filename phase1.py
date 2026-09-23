#!/usr/bin/env python3
"""Reproducible Phase 1 reference baseline for the Batch C corpus.

This is deliberately a transparent reference implementation.  It validates the
simulator, applies the 1940+ Army message-key procedure, searches an explicitly
bounded standard-Enigma keyspace, and emits a certificate describing exactly
what was (and was not) tested.  It is not yet the optimized Bombe/stecker search
required to close Phase 1 completely.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import heapq
import itertools
import json
import math
import pathlib
import platform
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Sequence

from enigma import A, EnigmaI, ROTOR_WIRINGS
from resources import output_path, resource_root


ROOT = resource_root()
DEFAULT_CORPUS = ROOT / "corpus.json"
DEFAULT_CERTIFICATE = output_path("phase1-smoke-certificate.json")

# German monogram frequencies, adjusted slightly so X/Q conventions in raw
# Army traffic are not rejected as harshly as they would be in newspaper text.
GERMAN_FREQUENCIES = {
    "A": 0.0651, "B": 0.0189, "C": 0.0306, "D": 0.0508,
    "E": 0.1740, "F": 0.0166, "G": 0.0301, "H": 0.0476,
    "I": 0.0755, "J": 0.0027, "K": 0.0121, "L": 0.0344,
    "M": 0.0253, "N": 0.0978, "O": 0.0251, "P": 0.0079,
    "Q": 0.0060, "R": 0.0700, "S": 0.0727, "T": 0.0615,
    "U": 0.0435, "V": 0.0067, "W": 0.0189, "X": 0.0100,
    "Y": 0.0004, "Z": 0.0113,
}

# These bonuses intentionally target raw operator text rather than polished
# prose.  They are a bootstrap scorer, not a substitute for a trained Army
# traffic language model.
NGRAM_WEIGHTS = {
    "ER": 0.45, "EN": 0.45, "CH": 0.55, "DE": 0.40, "EI": 0.40,
    "TE": 0.35, "IN": 0.35, "ND": 0.35, "IE": 0.35, "GE": 0.35,
    "ST": 0.35, "NE": 0.30, "BE": 0.30, "ES": 0.30, "UN": 0.35,
    "EIN": 1.20, "DER": 1.20, "DIE": 1.20, "UND": 1.30,
    "NICHT": 2.50, "MELDUNG": 3.00, "ANGRIFF": 3.00,
    "KOMMANDO": 3.00, "UHR": 1.50, "NORD": 1.60, "SUED": 1.60,
    "WEST": 1.60, "OST": 1.20, "VON": 1.20, "AN": 0.40,
    "X": 0.10, "Q": 0.05,
}


@dataclass(frozen=True)
class CorpusMessage:
    date: str
    designator: str
    grundstellung: str
    encrypted_message_key: str
    ciphertext: str


@dataclass(frozen=True)
class MessageResult:
    designator: str
    message_key: str
    plaintext: str
    raw_score: float
    known_letters: int


@dataclass(frozen=True)
class Candidate:
    date: str
    rotors: tuple[str, str, str]
    rings: str
    plugboard: str
    score_per_letter: float
    messages: tuple[MessageResult, ...]


class ArmyGermanScorer:
    """Small, inspectable raw-German bootstrap scorer.

    Question marks are masks for unresolved source characters and do not
    contribute to the score.  This makes uncertainty explicit during search.
    """

    def __init__(self) -> None:
        total = sum(GERMAN_FREQUENCIES.values())
        self.log_frequency = {
            letter: math.log(frequency / total)
            for letter, frequency in GERMAN_FREQUENCIES.items()
        }

    def score(self, text: str) -> tuple[float, int]:
        text = text.upper()
        known = [c for c in text if c in A]
        raw = sum(self.log_frequency[c] for c in known)
        segments = text.split("?")
        for ngram, weight in NGRAM_WEIGHTS.items():
            raw += weight * sum(segment.count(ngram) for segment in segments)
        return raw, len(known)


def _validate_trigram(value: str, label: str) -> str:
    value = value.upper()
    if len(value) != 3 or any(c not in A for c in value):
        raise ValueError(f"{label} must be exactly three A-Z letters: {value!r}")
    return value


def load_corpus(path: pathlib.Path = DEFAULT_CORPUS) -> list[CorpusMessage]:
    data = json.loads(path.read_text(encoding="utf-8"))
    messages: list[CorpusMessage] = []
    for record in data["messages"]:
        ciphertext = record["ciphertext"].upper()
        if len(ciphertext) != record["ciphertext_length"]:
            raise ValueError(
                f"{record['designator']}: declared length "
                f"{record['ciphertext_length']} != {len(ciphertext)}"
            )
        invalid = sorted(set(ciphertext) - set(A) - {"?"})
        if invalid:
            raise ValueError(f"{record['designator']}: invalid ciphertext {invalid}")
        if len(record["indicator"]) != 2:
            raise ValueError(f"{record['designator']}: expected two indicator trigrams")
        messages.append(
            CorpusMessage(
                date=record["date"],
                designator=record["designator"],
                grundstellung=_validate_trigram(record["indicator"][0], "Grundstellung"),
                encrypted_message_key=_validate_trigram(
                    record["indicator"][1], "encrypted message key"
                ),
                ciphertext=ciphertext,
            )
        )
    return messages


def decrypt_with_army_procedure(
    message: CorpusMessage,
    rotors: tuple[str, str, str],
    rings: str,
    plugboard: str = "",
) -> tuple[str, str]:
    """Decrypt an indicator and body using the clear-start Army procedure."""

    indicator_machine = EnigmaI(
        rotors=rotors,
        rings=rings,
        positions=message.grundstellung,
        plugboard=plugboard,
    )
    message_key = indicator_machine.crypt(message.encrypted_message_key)
    body_machine = EnigmaI(
        rotors=rotors,
        rings=rings,
        positions=message_key,
        plugboard=plugboard,
    )
    plaintext: list[str] = []
    for symbol in message.ciphertext:
        if symbol == "?":
            # Stepping is independent of the key pressed.  Advance with a
            # placeholder but preserve the unknown output as a mask.
            body_machine.key("A")
            plaintext.append("?")
        else:
            plaintext.append(body_machine.key(symbol))
    return message_key, "".join(plaintext)


def published_vector_results() -> list[dict[str, object]]:
    """Run independent published/sanity vectors before analytical use."""

    results: list[dict[str, object]] = []

    actual = EnigmaI(
        rotors=("I", "II", "III"), rings="AAA", positions="AAA"
    ).crypt("AAAAA")
    results.append(
        {
            "name": "canonical_I_II_III_AAAAA",
            "source": "widely published Enigma-I simulator check",
            "expected": "BDZGO",
            "actual": actual,
            "passed": actual == "BDZGO",
        }
    )

    settings = {
        "rotors": ("II", "IV", "V"),
        "rings": "BUL",
        "plugboard": "AV BS CG DL FU HZ IN KM OW RX",
    }
    actual_key = EnigmaI(positions="WXC", **settings).crypt("KCH")
    actual_body = EnigmaI(positions="BLA", **settings).crypt(
        "NIBLFMYMLLUFWCASCSSNVHAZ"
    )
    results.append(
        {
            "name": "py_enigma_army_procedure_example",
            "source": "https://py-enigma.readthedocs.io/en/latest/guide.html",
            "expected_message_key": "BLA",
            "actual_message_key": actual_key,
            "expected_plaintext": "THEXRUSSIANSXAREXCOMINGX",
            "actual_plaintext": actual_body,
            "passed": (
                actual_key == "BLA" and actual_body == "THEXRUSSIANSXAREXCOMINGX"
            ),
        }
    )
    return results


def all_ring_settings() -> Iterable[str]:
    for setting in itertools.product(A, repeat=3):
        yield "".join(setting)


def standard_rotor_orders() -> Iterable[tuple[str, str, str]]:
    # Phase 1 is intentionally the ordinary Army/Air Force I-V search.  Naval
    # VI-VIII are introduced explicitly, with their own provenance, in Phase 3.
    yield from itertools.permutations(("I", "II", "III", "IV", "V"), 3)


def _search_date(
    date: str,
    messages: Sequence[CorpusMessage],
    rotor_orders: Sequence[tuple[str, str, str]],
    rings: Sequence[str],
    plugboards: Sequence[str],
    scorer: ArmyGermanScorer,
    keep: int,
) -> tuple[list[Candidate], int]:
    heap: list[tuple[float, int, Candidate]] = []
    serial = 0
    evaluated = 0
    for rotors, ring_setting, plugboard in itertools.product(
        rotor_orders, rings, plugboards
    ):
        results: list[MessageResult] = []
        total_score = 0.0
        total_known = 0
        for message in messages:
            message_key, plaintext = decrypt_with_army_procedure(
                message, rotors, ring_setting, plugboard
            )
            raw_score, known = scorer.score(plaintext)
            total_score += raw_score
            total_known += known
            results.append(
                MessageResult(
                    designator=message.designator,
                    message_key=message_key,
                    plaintext=plaintext,
                    raw_score=raw_score,
                    known_letters=known,
                )
            )
        score_per_letter = total_score / total_known
        candidate = Candidate(
            date=date,
            rotors=rotors,
            rings=ring_setting,
            plugboard=plugboard,
            score_per_letter=score_per_letter,
            messages=tuple(results),
        )
        entry = (score_per_letter, serial, candidate)
        serial += 1
        if len(heap) < keep:
            heapq.heappush(heap, entry)
        elif score_per_letter > heap[0][0]:
            heapq.heapreplace(heap, entry)
        evaluated += 1
    return [entry[2] for entry in sorted(heap, reverse=True)], evaluated


def _resolve_uncertainties(
    plaintext: str, scorer: ArmyGermanScorer
) -> tuple[str, list[dict[str, object]]]:
    text = list(plaintext)
    choices: list[dict[str, object]] = []
    for position, symbol in enumerate(text):
        if symbol != "?":
            continue
        best_letter = max(
            A,
            key=lambda letter: scorer.score(
                "".join(text[:position] + [letter] + text[position + 1 :])
            )[0],
        )
        text[position] = best_letter
        choices.append({"position_1_based": position + 1, "chosen_plaintext": best_letter})
    return "".join(text), choices


def _apply_bounded_source_errors(
    plaintext: str,
    scorer: ArmyGermanScorer,
    budget: int,
    penalty: float,
    protected_positions: set[int],
) -> tuple[str, list[dict[str, object]]]:
    """Greedily rerank a finalist with bounded substitution-equivalent edits.

    At a fixed rotor state Enigma is a permutation, so a single ciphertext
    substitution is equivalent to changing exactly one plaintext character.
    This finalist-only pass is explicitly reported as such in the certificate.
    """

    text = list(plaintext)
    edits: list[dict[str, object]] = []
    current, _ = scorer.score(plaintext)
    for _ in range(budget):
        best: tuple[float, int, str, float] | None = None
        for position, original in enumerate(text):
            if position in protected_positions:
                continue
            for replacement in A:
                if replacement == original:
                    continue
                trial = text.copy()
                trial[position] = replacement
                trial_score, _ = scorer.score("".join(trial))
                gain = trial_score - current - penalty
                if best is None or gain > best[0]:
                    best = (gain, position, replacement, trial_score)
        if best is None or best[0] <= 0:
            break
        gain, position, replacement, trial_score = best
        original = text[position]
        text[position] = replacement
        edits.append(
            {
                "position_1_based": position + 1,
                "plaintext_before": original,
                "plaintext_after": replacement,
                "penalized_gain": gain,
            }
        )
        current = trial_score
    return "".join(text), edits


def _finalize_candidate(
    candidate: Candidate,
    scorer: ArmyGermanScorer,
    error_budget: int,
    edit_penalty: float,
) -> dict[str, object]:
    message_rows: list[dict[str, object]] = []
    total_score = 0.0
    total_letters = 0
    for result in candidate.messages:
        resolved, uncertainty_choices = _resolve_uncertainties(result.plaintext, scorer)
        protected = {choice["position_1_based"] - 1 for choice in uncertainty_choices}
        edited, edits = _apply_bounded_source_errors(
            resolved, scorer, error_budget, edit_penalty, protected
        )
        raw_score, known = scorer.score(edited)
        total_score += raw_score - edit_penalty * len(edits)
        total_letters += known
        message_rows.append(
            {
                "designator": result.designator,
                "recovered_message_key": result.message_key,
                "plaintext": edited,
                "uncertainty_choices": uncertainty_choices,
                "source_error_equivalents": edits,
            }
        )
    return {
        "date": candidate.date,
        "rotors_left_to_right": list(candidate.rotors),
        "rings": candidate.rings,
        "plugboard": candidate.plugboard,
        "clean_score_per_letter": candidate.score_per_letter,
        "adjusted_score_per_letter": total_score / total_letters,
        "messages": message_rows,
    }


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settings_summary(values: Sequence[str]) -> object:
    if len(values) <= 100:
        return list(values)
    joined = "\n".join(values).encode("ascii")
    return {
        "count": len(values),
        "first": values[0],
        "last": values[-1],
        "sha256_of_newline_joined_settings": hashlib.sha256(joined).hexdigest(),
    }


def build_certificate(args: argparse.Namespace) -> dict[str, object]:
    vectors = published_vector_results()
    if not all(result["passed"] for result in vectors):
        raise RuntimeError("simulator validation failed; refusing to search")

    corpus_path = pathlib.Path(args.corpus).resolve()
    messages = load_corpus(corpus_path)
    if args.date:
        messages = [message for message in messages if message.date == args.date]
    if args.message:
        wanted = set(args.message)
        messages = [message for message in messages if message.designator in wanted]
    if not messages:
        raise ValueError("the date/message filters selected no corpus messages")

    rotor_orders = tuple(args.rotor_orders)
    rings = tuple(all_ring_settings()) if args.all_rings else tuple(args.rings)
    plugboards = tuple(args.plugboards)
    scorer = ArmyGermanScorer()
    by_date: dict[str, list[CorpusMessage]] = {}
    for message in messages:
        by_date.setdefault(message.date, []).append(message)

    started_at = dt.datetime.now(dt.timezone.utc)
    started_clock = time.monotonic()
    finalist_pool = max(args.top * (5 if args.error_budget else 1), args.top)
    evaluated_daily_keys = 0
    finalized: dict[str, list[dict[str, object]]] = {}
    for date, date_messages in sorted(by_date.items()):
        candidates, evaluated = _search_date(
            date,
            date_messages,
            rotor_orders,
            rings,
            plugboards,
            scorer,
            finalist_pool,
        )
        evaluated_daily_keys += evaluated
        rows = [
            _finalize_candidate(
                candidate, scorer, args.error_budget, args.edit_penalty
            )
            for candidate in candidates
        ]
        finalized[date] = sorted(
            rows,
            key=lambda row: row["adjusted_score_per_letter"],
            reverse=True,
        )[: args.top]

    completed_at = dt.datetime.now(dt.timezone.utc)
    # This reference runner accepts fixed plugboards but does not yet enumerate
    # or optimize the full stecker space, so it cannot issue the final Phase 1
    # negative result regardless of rotor/ring coverage.
    full_standard_keyspace = False
    return {
        "schema": "enigma-attack.phase1-search-certificate/v1",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": time.monotonic() - started_clock,
        "implementation": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "files_sha256": {
                "corpus": _sha256(corpus_path),
                "enigma.py": _sha256(ROOT / "enigma.py"),
                "phase1.py": _sha256(ROOT / "phase1.py"),
            },
        },
        "simulator_validation": vectors,
        "procedure": (
            "clear Grundstellung trigram; decrypt encrypted message-key trigram; "
            "reset to recovered message key; decrypt body"
        ),
        "search_space": {
            "reflector": "UKW-B",
            "rotor_orders_left_to_right": [list(order) for order in rotor_orders],
            "ring_settings": _settings_summary(rings),
            "plugboards": list(plugboards),
            "dates": sorted(by_date),
            "messages": [message.designator for message in messages],
            "uncertain_source_characters": (
                "masked during search and resolved only when rendering finalists"
            ),
            "bounded_source_error_budget_per_message": args.error_budget,
            "source_error_penalty": args.edit_penalty,
            "source_error_scope": (
                "finalist rerank after the clean search; not applied when budget is zero"
            ),
        },
        "counts": {
            "evaluated_daily_keys": evaluated_daily_keys,
            "evaluated_message_decryptions": sum(
                len(date_messages) * len(rotor_orders) * len(rings) * len(plugboards)
                for date_messages in by_date.values()
            ),
        },
        "scorer": {
            "name": "bootstrap raw German Army heuristic v1",
            "normalization": "none; scores raw A-Z operator text with X/Q conventions",
            "warning": (
                "bootstrap scorer only; replace with a trained, versioned Army-traffic "
                "language model before treating rankings as cryptanalytic evidence"
            ),
        },
        "result": {
            "status": "restricted_reference_search_complete",
            "full_phase_1_negative_result": full_standard_keyspace,
            "interpretation": (
                "This run is reproducible evidence for exactly the recorded keyspace. "
                "It is not a full Phase 1 negative result unless rings and stecker "
                "coverage are both complete."
            ),
            "top_candidates_by_date": finalized,
        },
        "known_gaps": [
            "No Bombe constraints or general stecker hill-climbing yet.",
            "Bootstrap scorer is not trained on a versioned German Army corpus.",
            "Bounded source-error reranking examines finalists, not every daily key.",
            "No independent second simulator is bundled; published vectors are used instead.",
        ],
    }


def _parse_rotor_order(value: str) -> tuple[str, str, str]:
    parts = tuple(part.upper() for part in value.replace(",", "-").split("-") if part)
    if len(parts) != 3 or len(set(parts)) != 3:
        raise argparse.ArgumentTypeError("rotor order must contain three distinct names")
    if any(part not in ROTOR_WIRINGS for part in parts):
        raise argparse.ArgumentTypeError(f"rotors must be selected from {sorted(ROTOR_WIRINGS)}")
    return parts  # type: ignore[return-value]


def _parse_ring_setting(value: str) -> str:
    try:
        return _validate_trigram(value, "ring setting")
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _write_json(path: pathlib.Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="run simulator validation vectors")

    search = subparsers.add_parser(
        "search", help="run a bounded standard-Enigma reference search"
    )
    search.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    search.add_argument("--date", help="search only one YYYY-MM-DD daily key")
    search.add_argument("--message", action="append", help="include one designator")
    search.add_argument(
        "--rotor-order",
        dest="rotor_orders",
        action="append",
        type=_parse_rotor_order,
        help="left-middle-right order, e.g. I-II-III; repeatable",
    )
    ring_group = search.add_mutually_exclusive_group()
    ring_group.add_argument(
        "--rings",
        action="append",
        type=_parse_ring_setting,
        help="ring setting such as AAA; repeatable (default: AAA)",
    )
    ring_group.add_argument(
        "--all-rings", action="store_true", help="search all 17,576 ring settings"
    )
    search.add_argument(
        "--plugboard",
        dest="plugboards",
        action="append",
        help="fixed space-separated stecker pairs; repeatable (default: none)",
    )
    search.add_argument("--top", type=int, default=3)
    search.add_argument("--error-budget", type=int, default=0)
    search.add_argument("--edit-penalty", type=float, default=5.0)
    search.add_argument("--output", default=str(DEFAULT_CERTIFICATE))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        results = published_vector_results()
        print(json.dumps(results, indent=2))
        return 0 if all(result["passed"] for result in results) else 1

    if args.top < 1:
        parser.error("--top must be positive")
    if args.error_budget < 0:
        parser.error("--error-budget cannot be negative")
    args.rotor_orders = args.rotor_orders or list(standard_rotor_orders())
    args.rings = args.rings or ["AAA"]
    args.plugboards = args.plugboards or [""]

    certificate = build_certificate(args)
    output = pathlib.Path(args.output).resolve()
    _write_json(output, certificate)
    print(
        f"wrote {output} after "
        f"{certificate['counts']['evaluated_daily_keys']} daily keys"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
