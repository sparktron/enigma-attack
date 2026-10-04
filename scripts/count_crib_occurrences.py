#!/usr/bin/env python3
"""Count where each catalogued crib occurs in solved plaintext.

Counting only: no search, no Enigma. Used by phase2-crib-prior-v1 to measure
the development set (the five solved 1941 Army plaintexts in
data/phase5/army-plaintext-controls.json) and, unchanged, any held-out set
supplied later with --plaintexts.

Each occurrence is classed by position: ``opening`` (starts at letter 0),
``sign_off`` (ends at the last letter, or one before a single trailing X),
or ``other``. The solved texts carry no address block (no AN/VON group), so
the ``address`` class is reported but can only be counted from a set that has
one. A crib ending in the X separator is also searched without that X, since a
terminal token is not followed by one.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def classify(text: str, start: int, length: int) -> str:
    end = start + length
    if start == 0:
        return "opening"
    if end == len(text) or (end == len(text) - 1 and text[-1] == "X"):
        return "sign_off"
    return "other"


def occurrences(text: str, crib: str) -> list[dict[str, object]]:
    found = []
    start = text.find(crib)
    while start >= 0:
        found.append({"offset": start, "position_class": classify(text, start, len(crib))})
        start = text.find(crib, start + 1)
    return found


def count(plaintexts: list[dict[str, str]], cribs: list[dict[str, object]]) -> dict[str, object]:
    texts = {row["id"]: "".join(row["raw"].split()).upper() for row in plaintexts}
    rows = []
    for crib in cribs:
        variants = [crib["text"]]
        if crib["text"].endswith("X") and len(crib["text"]) > 1:
            variants.append(crib["text"].rstrip("X"))
        by_variant = {}
        for variant in variants:
            hits = {
                message_id: found
                for message_id, text in texts.items()
                if (found := occurrences(text, variant))
            }
            classes: dict[str, int] = {"opening": 0, "address": 0, "sign_off": 0, "other": 0}
            for found in hits.values():
                for hit in found:
                    classes[hit["position_class"]] += 1
            by_variant[variant] = {
                "messages_containing": len(hits),
                "messages_total": len(texts),
                "occurrences_by_class": classes,
                "hits": hits,
            }
        rows.append(
            {
                "crib_id": crib["id"],
                "evidence_level": crib["evidence_level"],
                "by_variant": by_variant,
            }
        )
    return {
        "messages": len(texts),
        "letters": sum(len(text) for text in texts.values()),
        "terminal_letters": {message_id: text[-14:] for message_id, text in texts.items()},
        "cribs": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plaintexts", default=str(ROOT / "data/phase5/army-plaintext-controls.json")
    )
    parser.add_argument("--cribs", default=str(ROOT / "cribs.json"))
    args = parser.parse_args(argv)
    plaintexts = json.loads(pathlib.Path(args.plaintexts).read_text(encoding="utf-8"))
    cribs = json.loads(pathlib.Path(args.cribs).read_text(encoding="utf-8"))
    json.dump(count(plaintexts["plaintexts"], cribs["cribs"]), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
