#!/usr/bin/env python3
"""Phase 3: bounded comparison of documented three-wheel Enigma variants."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import pathlib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from enigma import EnigmaMachine
from phase1 import ArmyGermanScorer, CorpusMessage, DEFAULT_CORPUS, load_corpus
from resources import output_path, resource_root

ROOT = resource_root()
DEFAULT_CATALOG = ROOT / "variants.json"
DEFAULT_CERTIFICATE = output_path("phase3-variant-smoke-v2.json")


@dataclass(frozen=True)
class VariantProfile:
    id: str
    label: str
    enabled_by_default: bool
    rotor_pool: tuple[str, ...]
    rotor_wirings: Mapping[str, tuple[str, str]]
    reflector: str
    entry_wiring: str
    reflector_settable: bool
    stepping: str
    plugboard_practice: str
    procedure_compatibility: str
    historical_prior: str
    historical_note: str
    source_ids: tuple[str, ...]


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_trigram(value: str, label: str) -> str:
    value = value.upper()
    if len(value) != 3 or not value.isalpha() or not value.isascii():
        raise ValueError(f"{label} must be exactly three A-Z letters: {value!r}")
    return value


def load_variant_catalog(
    path: pathlib.Path = DEFAULT_CATALOG,
) -> tuple[dict[str, Any], list[VariantProfile]]:
    """Load and structurally validate the evidence-backed variant catalog."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported variant catalog schema")
    sources = payload.get("sources")
    raw_profiles = payload.get("profiles")
    if not isinstance(sources, dict) or not isinstance(raw_profiles, list):
        raise ValueError("catalog must contain sources and profiles")

    profiles: list[VariantProfile] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        profile_id = raw["id"]
        if profile_id in seen:
            raise ValueError(f"duplicate profile id: {profile_id}")
        seen.add(profile_id)
        source_ids = tuple(raw["source_ids"])
        unknown_sources = set(source_ids).difference(sources)
        if unknown_sources:
            raise ValueError(
                f"profile {profile_id} cites unknown sources: {sorted(unknown_sources)}"
            )
        rotor_pool = tuple(raw["rotor_pool"])
        rotor_wirings = {
            name: (spec[0], spec[1]) for name, spec in raw["rotor_wirings"].items()
        }
        if len(rotor_pool) < 3 or len(set(rotor_pool)) != len(rotor_pool):
            raise ValueError(f"profile {profile_id} needs at least three distinct rotors")
        if set(rotor_pool) != set(rotor_wirings):
            raise ValueError(f"profile {profile_id} rotor pool/wiring mismatch")
        profile = VariantProfile(
            id=profile_id,
            label=raw["label"],
            enabled_by_default=bool(raw["enabled_by_default"]),
            rotor_pool=rotor_pool,
            rotor_wirings=rotor_wirings,
            reflector=raw["reflector"],
            entry_wiring=raw["entry_wiring"],
            reflector_settable=bool(raw["reflector_settable"]),
            stepping=raw["stepping"],
            plugboard_practice=raw["plugboard_practice"],
            procedure_compatibility=raw["procedure_compatibility"],
            historical_prior=raw["historical_prior"],
            historical_note=raw["historical_note"],
            source_ids=source_ids,
        )
        # Validate every rotor and the profile's ETW/UKW before search.
        for rotor_name in rotor_pool:
            validation_order = (
                rotor_name,
                *tuple(name for name in rotor_pool if name != rotor_name)[:2],
            )
            EnigmaMachine(
                validation_order,
                rotor_wirings=rotor_wirings,
                reflector=profile.reflector,
                entry_wiring=profile.entry_wiring,
                stepping=profile.stepping,
            )
        profiles.append(profile)

    for unsupported in payload.get("unsupported", []):
        unknown_sources = set(unsupported["source_ids"]).difference(sources)
        if unknown_sources:
            raise ValueError(
                f"unsupported entry {unsupported['id']} cites unknown sources: "
                f"{sorted(unknown_sources)}"
            )
    return payload, profiles


def rotor_orders(profile: VariantProfile) -> Iterable[tuple[str, str, str]]:
    yield from itertools.permutations(profile.rotor_pool, 3)


def decrypt_with_profile(
    message: CorpusMessage,
    profile: VariantProfile,
    rotors: tuple[str, str, str],
    rings: str,
    reflector_position: str = "A",
    plugboard: str = "",
) -> tuple[str, str]:
    """Apply the corpus clear-indicator convention to one machine profile.

    For profiles marked mechanical_assumption_only this is a controlled
    cryptanalytic comparison, not a claim about their historical procedure.
    """

    common = {
        "rotors": rotors,
        "rings": rings,
        "plugboard": plugboard,
        "rotor_wirings": profile.rotor_wirings,
        "reflector": profile.reflector,
        "entry_wiring": profile.entry_wiring,
        "reflector_position": reflector_position,
        "stepping": profile.stepping,
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


def _search_profile_date(
    profile: VariantProfile,
    date: str,
    messages: Sequence[CorpusMessage],
    rings: Sequence[str],
    reflector_positions: Sequence[str],
    plugboards: Sequence[str],
    scorer: ArmyGermanScorer,
    keep: int,
) -> tuple[list[dict[str, Any]], int]:
    candidates: list[dict[str, Any]] = []
    evaluations = 0
    applicable_plugboards = plugboards if profile.plugboard_practice == "steckered" else ("",)
    applicable_reflector_positions = (
        reflector_positions if profile.reflector_settable else ("A",)
    )
    for order in rotor_orders(profile):
        for ring_setting in rings:
            for reflector_position in applicable_reflector_positions:
                for plugboard in applicable_plugboards:
                    evaluations += 1
                    message_results: list[dict[str, Any]] = []
                    total_score = 0.0
                    total_known = 0
                    for message in messages:
                        message_key, plaintext = decrypt_with_profile(
                            message,
                            profile,
                            order,
                            ring_setting,
                            reflector_position,
                            plugboard,
                        )
                        raw_score, known = scorer.score(plaintext)
                        total_score += raw_score
                        total_known += known
                        message_results.append(
                            {
                                "designator": message.designator,
                                "message_key": message_key,
                                "plaintext": plaintext,
                                "raw_score": round(raw_score, 6),
                                "known_letters": known,
                            }
                        )
                    score_per_letter = (
                        total_score / total_known if total_known else float("-inf")
                    )
                    candidates.append(
                        {
                            "date": date,
                            "rotors": list(order),
                            "rings": ring_setting,
                            "reflector_position": reflector_position,
                            "plugboard": plugboard,
                            "score_per_letter": round(score_per_letter, 9),
                            "messages": message_results,
                        }
                    )
    candidates.sort(key=lambda item: item["score_per_letter"], reverse=True)
    return candidates[:keep], evaluations


def _select_profiles(
    profiles: Sequence[VariantProfile],
    requested: Sequence[str],
    include_disabled: bool,
) -> list[VariantProfile]:
    by_id = {profile.id: profile for profile in profiles}
    if requested:
        unknown = set(requested).difference(by_id)
        if unknown:
            raise ValueError(f"unknown profile ids: {sorted(unknown)}")
        return [by_id[profile_id] for profile_id in requested]
    return [
        profile
        for profile in profiles
        if profile.enabled_by_default or include_disabled
    ]


def build_certificate(args: argparse.Namespace) -> dict[str, Any]:
    catalog_payload, all_profiles = load_variant_catalog(args.catalog)
    selected = _select_profiles(
        all_profiles,
        args.profile or (),
        args.include_disabled,
    )
    if not selected:
        raise ValueError("no variant profiles selected")

    rings = tuple(
        _validate_trigram(value, "ring setting") for value in (args.ring or ["AAA"])
    )
    reflector_positions = tuple(
        value.upper() for value in (args.reflector_position or ["A"])
    )
    if any(len(value) != 1 or value < "A" or value > "Z" for value in reflector_positions):
        raise ValueError("reflector positions must be single A-Z letters")
    plugboards = tuple(args.plugboard or [""])
    corpus = load_corpus(args.corpus)
    messages_by_date: dict[str, list[CorpusMessage]] = defaultdict(list)
    for message in corpus:
        messages_by_date[message.date].append(message)

    scorer = ArmyGermanScorer()
    results: list[dict[str, Any]] = []
    total_evaluations = 0
    for profile in selected:
        date_results: list[dict[str, Any]] = []
        for date, messages in sorted(messages_by_date.items()):
            top, evaluations = _search_profile_date(
                profile,
                date,
                messages,
                rings,
                reflector_positions,
                plugboards,
                scorer,
                args.keep,
            )
            total_evaluations += evaluations
            date_results.append(
                {
                    "date": date,
                    "messages": len(messages),
                    "evaluations": evaluations,
                    "top_candidates": top,
                }
            )
        best_score = max(
            candidate["score_per_letter"]
            for result in date_results
            for candidate in result["top_candidates"]
        )
        results.append(
            {
                "profile_id": profile.id,
                "label": profile.label,
                "historical_prior": profile.historical_prior,
                "procedure_compatibility": profile.procedure_compatibility,
                "historical_note": profile.historical_note,
                "source_ids": list(profile.source_ids),
                "rotor_order_count": len(tuple(rotor_orders(profile))),
                "best_score_per_letter": best_score,
                "dates": date_results,
            }
        )
    results.sort(key=lambda item: item["best_score_per_letter"], reverse=True)

    return {
        "schema": "enigma-attack.phase3-variant-smoke/v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {
            "corpus": str(args.corpus),
            "corpus_sha256": _sha256(args.corpus),
            "catalog": str(args.catalog),
            "catalog_sha256": _sha256(args.catalog),
            "runner_sha256": _sha256(pathlib.Path(__file__)),
        },
        "research_boundary": {
            "question": (
                "Which documented three-wheel Enigma-family configurations are "
                "plausible enough to screen before arbitrary rotor recovery?"
            ),
            "scope": "Documented, executable three-wheel variants only.",
            "unsupported": catalog_payload.get("unsupported", []),
            "sources": catalog_payload["sources"],
        },
        "search": {
            "profiles": [profile.id for profile in selected],
            "rings": list(rings),
            "reflector_positions": list(reflector_positions),
            "plugboards": list(plugboards),
            "top_candidates_kept": args.keep,
            "total_daily_key_evaluations": total_evaluations,
            "indicator_assumption": (
                "The corpus clear Grundstellung/encrypted message-key convention "
                "is applied uniformly; non-Army profiles are marked mechanical-only."
            ),
        },
        "results": results,
        "decision": {
            "accepted_break": False,
            "status": "screening_complete_no_validated_plaintext",
            "reason": (
                "Language-score ranking alone is not an acceptance test, and no "
                "candidate has external plaintext confirmation."
            ),
            "negative_claim": (
                "None. This smoke comparison does not exclude unsearched rings, "
                "plugboards, reflector positions, procedures, or arbitrary wirings."
            ),
            "coverage_gaps": [
                "Only explicitly supplied plugboards were tested; the default is no plugs. This does not exclude the historically normal steckered service keyspace.",
                "Only explicitly supplied reflector positions were tested; the default is A.",
                "Naval and commercial-family profiles are scored under a deliberately artificial Army-indicator assumption.",
                "Four-wheel and moving-reflector/geared machines are not approximated."
            ],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=pathlib.Path, default=DEFAULT_CATALOG)
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_CERTIFICATE)
    parser.add_argument("--profile", action="append", help="profile id; repeatable")
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="include profiles excluded by default on historical grounds",
    )
    parser.add_argument("--ring", action="append", help="ring trigram; repeatable")
    parser.add_argument(
        "--reflector-position",
        action="append",
        help="settable-reflector position; repeatable",
    )
    parser.add_argument(
        "--plugboard",
        action="append",
        help="plugboard pairs for steckered profiles; repeatable",
    )
    parser.add_argument("--keep", type=int, default=2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.keep < 1:
        raise SystemExit("--keep must be positive")
    certificate = build_certificate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(certificate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({certificate['search']['total_daily_key_evaluations']} evaluations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
