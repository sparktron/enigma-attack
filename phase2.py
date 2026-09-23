#!/usr/bin/env python3
"""Phase 2 network analysis and source-backed crib ranking.

The pipeline separates sourced facts, inferences, and speculation; builds a
message metadata graph; produces archive-search priorities; and ranks crib
placements with Enigma's no-self-encryption property as a cheap Bombe precheck.
It does not claim that a compatible placement is a valid Bombe menu or break.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Sequence

from enigma import A
from resources import output_path, resource_root


ROOT = resource_root()
DEFAULT_CORPUS = ROOT / "corpus.json"
DEFAULT_CRIBS = ROOT / "cribs.json"
DEFAULT_OUTPUT = output_path("phase2-network-cribs.json")

EVIDENCE_WEIGHTS = {"fact": 1.0, "inference": 0.5, "speculation": 0.15}
CONTEXT_WEIGHTS = {
    "same_archive_and_year": 1.0,
    "authentic_army_other_period": 0.65,
    "same_message_metadata_only": 0.45,
    "generic_military_vocabulary": 0.15,
}
CLUSTER_EDGE_THRESHOLD = 3.0


@dataclass(frozen=True)
class MessageMetadata:
    designator: str
    date: str
    number: int
    form_time: str
    header_time: str
    operator: str
    sender: str | None
    recipient: str | None
    frequency_khz: int | None
    remarks: str
    ciphertext: str
    current_status: str

    @property
    def timestamp(self) -> dt.datetime:
        return dt.datetime.fromisoformat(f"{self.date}T{self.header_time}:00")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_identity(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9]", "", value.lower())
    return normalized or None


def load_messages(path: pathlib.Path = DEFAULT_CORPUS) -> list[MessageMetadata]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    messages: list[MessageMetadata] = []
    for record in payload["messages"]:
        messages.append(
            MessageMetadata(
                designator=record["designator"],
                date=record["date"],
                number=int(record["number"]),
                form_time=record["time"],
                header_time=record.get("header_time", record["time"]),
                operator=record.get("operator", ""),
                sender=record.get("from"),
                recipient=record.get("to"),
                frequency_khz=record.get("frequency_khz"),
                remarks=record.get("remarks", ""),
                ciphertext=record["ciphertext"].upper(),
                current_status=record.get("current_status", "unknown"),
            )
        )
    return messages


def load_crib_catalog(path: pathlib.Path = DEFAULT_CRIBS) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = {source["id"]: source for source in payload["sources"]}
    seen: set[str] = set()
    for crib in payload["cribs"]:
        crib_id = crib["id"]
        if crib_id in seen:
            raise ValueError(f"duplicate crib id: {crib_id}")
        seen.add(crib_id)
        text = crib["text"].upper()
        if not text or any(symbol not in A for symbol in text):
            raise ValueError(f"{crib_id}: crib text must contain only A-Z")
        evidence = crib["evidence_level"]
        if evidence not in EVIDENCE_WEIGHTS:
            raise ValueError(f"{crib_id}: unknown evidence level {evidence!r}")
        source_id = crib.get("source_id")
        if evidence == "fact" and source_id not in sources:
            raise ValueError(f"{crib_id}: factual cribs require a catalogued source")
        if source_id is not None and source_id not in sources:
            raise ValueError(f"{crib_id}: unknown source {source_id!r}")
        if crib["source_context"] not in CONTEXT_WEIGHTS:
            raise ValueError(f"{crib_id}: unknown source context")
    return payload


def _edge_signals(
    left: MessageMetadata, right: MessageMetadata
) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    if left.date == right.date:
        signals.append({"kind": "same_date", "weight": 1.0})

    left_operator = _normalize_identity(left.operator)
    right_operator = _normalize_identity(right.operator)
    if left_operator and left_operator == right_operator:
        uncertain = "?" in left.operator or "?" in right.operator
        signals.append(
            {
                "kind": "same_operator",
                "weight": 2.0 if uncertain else 2.75,
                "uncertain": uncertain,
                "value": left.operator,
            }
        )

    if (
        left.frequency_khz is not None
        and left.frequency_khz == right.frequency_khz
    ):
        signals.append(
            {"kind": "same_frequency", "weight": 2.0, "value_khz": left.frequency_khz}
        )

    left_sender = _normalize_identity(left.sender)
    left_recipient = _normalize_identity(left.recipient)
    right_sender = _normalize_identity(right.sender)
    right_recipient = _normalize_identity(right.recipient)
    if left_recipient and left_recipient == right_sender:
        signals.append(
            {
                "kind": "recipient_to_later_sender",
                "weight": 3.5,
                "value": left.recipient,
            }
        )
    if right_recipient and right_recipient == left_sender:
        signals.append(
            {
                "kind": "recipient_to_later_sender",
                "weight": 3.5,
                "value": right.recipient,
            }
        )
    if left_recipient and left_recipient == right_recipient:
        signals.append(
            {"kind": "same_recipient", "weight": 1.25, "value": left.recipient}
        )

    if abs(left.number - right.number) == 1:
        signals.append({"kind": "adjacent_message_number", "weight": 0.75})

    gap_minutes = abs((right.timestamp - left.timestamp).total_seconds()) / 60
    if gap_minutes <= 90:
        signals.append(
            {"kind": "within_90_minutes", "weight": 1.5, "gap_minutes": gap_minutes}
        )
    elif gap_minutes <= 360:
        signals.append(
            {"kind": "within_6_hours", "weight": 0.5, "gap_minutes": gap_minutes}
        )
    return signals


def build_network(messages: Sequence[MessageMetadata]) -> dict[str, object]:
    edges: list[dict[str, object]] = []
    for left, right in itertools.combinations(sorted(messages, key=lambda item: item.timestamp), 2):
        signals = _edge_signals(left, right)
        if not signals:
            continue
        edges.append(
            {
                "source": left.designator,
                "target": right.designator,
                "score": sum(float(signal["weight"]) for signal in signals),
                "signals": signals,
            }
        )

    parent = {message.designator: message.designator for message in messages}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for edge in edges:
        if edge["score"] >= CLUSTER_EDGE_THRESHOLD:
            union(str(edge["source"]), str(edge["target"]))

    grouped: dict[str, list[str]] = {}
    for message in messages:
        grouped.setdefault(find(message.designator), []).append(message.designator)
    clusters = [
        {
            "id": f"cluster-{index + 1}",
            "messages": sorted(members),
            "basis": f"connected edges scoring at least {CLUSTER_EDGE_THRESHOLD}",
        }
        for index, members in enumerate(sorted(grouped.values(), key=lambda row: row[0]))
    ]
    return {
        "cluster_edge_threshold": CLUSTER_EDGE_THRESHOLD,
        "nodes": [
            {
                "designator": message.designator,
                "date": message.date,
                "number": message.number,
                "form_time": message.form_time,
                "header_time": message.header_time,
                "operator": message.operator,
                "from": message.sender,
                "to": message.recipient,
                "frequency_khz": message.frequency_khz,
                "remarks": message.remarks,
                "current_status": message.current_status,
            }
            for message in sorted(messages, key=lambda item: item.timestamp)
        ],
        "edges": sorted(edges, key=lambda edge: (-float(edge["score"]), edge["source"])),
        "clusters": clusters,
    }


def valid_crib_offsets(ciphertext: str, crib: str) -> list[int]:
    """Return zero-based offsets that satisfy Enigma's no-self property."""

    ciphertext = ciphertext.upper()
    crib = crib.upper()
    if not crib or any(symbol not in A for symbol in crib):
        raise ValueError("crib must contain only A-Z")
    if len(crib) > len(ciphertext):
        return []
    offsets: list[int] = []
    for offset in range(len(ciphertext) - len(crib) + 1):
        window = ciphertext[offset : offset + len(crib)]
        if all(cipher == "?" or cipher != plain for cipher, plain in zip(window, crib)):
            offsets.append(offset)
    return offsets


def rank_cribs(
    message: MessageMetadata,
    catalog: dict[str, object],
    include_disabled: bool = False,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for crib in catalog["cribs"]:  # type: ignore[index]
        if not include_disabled and not crib["enabled_by_default"]:
            continue
        targets = crib.get("target_designators", [])
        if targets and message.designator not in targets:
            continue
        text = crib["text"]
        possible = max(len(message.ciphertext) - len(text) + 1, 0)
        offsets = valid_crib_offsets(message.ciphertext, text)
        valid_fraction = len(offsets) / possible if possible else 0.0
        constraint_strength = min(len(text) / 24.0, 1.0)
        bombe_precheck_score = 0.55 * valid_fraction + 0.45 * constraint_strength
        historical_score = (
            0.65 * EVIDENCE_WEIGHTS[crib["evidence_level"]]
            + 0.35 * CONTEXT_WEIGHTS[crib["source_context"]]
        )
        if targets:
            historical_score = min(historical_score + 0.05, 1.0)
        combined = 0.65 * historical_score + 0.35 * bombe_precheck_score
        rows.append(
            {
                "crib_id": crib["id"],
                "text": text,
                "evidence_level": crib["evidence_level"],
                "source_id": crib.get("source_id"),
                "historical_score": historical_score,
                "bombe_precheck_score": bombe_precheck_score,
                "combined_score": combined,
                "valid_offset_count": len(offsets),
                "possible_offset_count": possible,
                "valid_offsets_1_based": [offset + 1 for offset in offsets],
                "rationale": crib["rationale"],
            }
        )
    return sorted(rows, key=lambda row: (-row["combined_score"], row["crib_id"]))


def build_archive_queries(messages: Sequence[MessageMetadata]) -> list[dict[str, object]]:
    queries: list[dict[str, object]] = []
    callsign_occurrences: dict[str, list[str]] = {}
    for message in messages:
        for callsign in (message.sender, message.recipient):
            normalized = _normalize_identity(callsign)
            if normalized:
                callsign_occurrences.setdefault(normalized, []).append(message.designator)
    for callsign, designators in callsign_occurrences.items():
        if len(set(designators)) > 1:
            queries.append(
                {
                    "priority": "high",
                    "query": f"callsign {callsign}, 29-30 September 1941, adjacent station logs",
                    "basis": sorted(set(designators)),
                    "reason": "Callsign appears as a recipient and/or sender across messages.",
                }
            )

    by_frequency: dict[int, list[str]] = {}
    for message in messages:
        if message.frequency_khz is not None:
            by_frequency.setdefault(message.frequency_khz, []).append(message.designator)
    for frequency, designators in sorted(by_frequency.items()):
        if len(designators) > 1:
            queries.append(
                {
                    "priority": "medium",
                    "query": f"{frequency} kHz traffic logs, 29-30 September 1941",
                    "basis": sorted(designators),
                    "reason": "Frequency is shared across different operators or recipients.",
                }
            )

    by_operator: dict[str, list[str]] = {}
    for message in messages:
        operator = _normalize_identity(message.operator)
        if operator:
            by_operator.setdefault(operator, []).append(message.designator)
    for operator, designators in sorted(by_operator.items()):
        if len(designators) > 1:
            queries.append(
                {
                    "priority": "medium",
                    "query": f"operator {operator}, Batch C message forms and counterpart copies",
                    "basis": sorted(designators),
                    "reason": "Operator identity links a consecutive run of messages.",
                }
            )

    if any("Spruch 2352" in message.remarks for message in messages):
        queries.append(
            {
                "priority": "high",
                "query": "message timed or numbered 2352 linked to BYQMZ and callsign ugn",
                "basis": ["BYQMZ", "FKQLZ"],
                "reason": "BYQMZ's clear remark references Spruch 2352; the next known sender is ugn.",
            }
        )
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(queries, key=lambda row: (priority_order[row["priority"]], row["query"]))


def build_artifact(
    corpus_path: pathlib.Path,
    cribs_path: pathlib.Path,
    top: int,
    include_disabled: bool,
) -> dict[str, object]:
    messages = load_messages(corpus_path)
    catalog = load_crib_catalog(cribs_path)
    network = build_network(messages)
    return {
        "schema": "enigma-attack.phase2-network-cribs/v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {
            "corpus": str(corpus_path),
            "corpus_sha256": _sha256(corpus_path),
            "cribs": str(cribs_path),
            "cribs_sha256": _sha256(cribs_path),
            "phase2_sha256": _sha256(ROOT / "phase2.py"),
        },
        "evidence_separation": {
            "facts": [
                "The July 2026 challenge page presents five unknown messages with unusual operators, remarks, and low frequencies.",
                "The 16 September 2026 unbroken list names only BYQMZ, FKQLZ, and XFEDT for Batch C.",
                "A 2026 archival counterpart enabled the ALQFI break and supplies authentic raw 1941 plaintext conventions.",
            ],
            "inferences": [
                "The ugn recipient-to-sender transition and repeated frequencies support treating the five forms as one traffic-analysis cluster.",
                "The omission of QTXMA and SZAEJ from the later unbroken list is a status discrepancy, not proof that either was solved.",
            ],
            "speculation": [
                "The challenge page suggests a possible Ordnungspolizei network but states that no confirming evidence was available."
            ],
        },
        "network": network,
        "archive_queries": build_archive_queries(messages),
        "crib_ranking": {
            "method": {
                "historical": "65% evidence level + 35% source-context proximity",
                "bombe_precheck": "55% valid-offset fraction + 45% crib-length constraint strength",
                "combined": "65% historical + 35% no-self-encryption precheck",
                "warning": "No-self compatibility is necessary but not sufficient for a Bombe menu.",
                "include_disabled": include_disabled,
            },
            "by_message": {
                message.designator: rank_cribs(message, catalog, include_disabled)[:top]
                for message in messages
            },
        },
        "sources": catalog["sources"],
        "unresolved": [
            "Why QTXMA and SZAEJ are absent from the 2026-09-16 unbroken list.",
            "Whether all five messages use Enigma or even one homogeneous cipher system.",
            "The identities of the network, callsigns, and abbreviated Q-code remarks.",
            "Counterpart message forms or cleartext copies for the Batch C traffic.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--cribs", default=str(DEFAULT_CRIBS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="include metadata-derived inference and unsupported speculative cribs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be positive")
    corpus_path = pathlib.Path(args.corpus).resolve()
    cribs_path = pathlib.Path(args.cribs).resolve()
    output_path = pathlib.Path(args.output).resolve()
    artifact = build_artifact(corpus_path, cribs_path, args.top, args.include_disabled)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    edge_count = len(artifact["network"]["edges"])
    print(f"wrote {output_path} with {edge_count} network edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
