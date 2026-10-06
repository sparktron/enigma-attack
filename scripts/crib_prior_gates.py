#!/usr/bin/env python3
"""Evaluate phase2-crib-prior-v1's gates G1 to G4 on the held-out plaintexts.

Counting only: no search, no Enigma. Follows experiments/phase2-crib-prior-v1
as written. The train split (on or before 1941-09-15) supplies the candidate
list; the evaluate split (1941-09-16 to 1941-10-31) is only counted against it.

Candidates: every token that recurs in at least two training messages in the
same class (opening, address, sign-off), plus every catalogued crib. A token is
a run of letters between X separators. The opening token is the first one, the
sign-off token the last one (a trailing X is dropped), and address tokens are
those wholly inside an annotated address block. A truncated message gives no
sign-off token.

u is the fraction of evaluate messages in which at least one candidate occurs at
a listed placement. The prior lists opening, sign-off and annotated-address
placements and, for the 'other' class, every offset, so u is reported both
with and without 'other'. u_L80 is the one-sided 80% Clopper-Pearson lower
bound. G3 is checked with r = 1, the necessary condition the configuration
names; r has not been measured.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from count_crib_occurrences import count  # noqa: E402

TRAIN_END = "1941-09-15"
EVALUATE = ("1941-09-16", "1941-10-31")
CLASSES = ("opening", "address", "sign_off")
G3_THRESHOLD = 0.29
G1_MINIMUM = 20


def _tail(x: int, n: int, p: float) -> float:
    """P(X >= x) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x, n + 1))


def _solve(f, target: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return (lo + hi) / 2


def lower_bound(x: int, n: int, alpha: float) -> float:
    """Exact (Clopper-Pearson) lower confidence limit with tail probability alpha."""
    return 0.0 if x == 0 else _solve(lambda p: _tail(x, n, p), alpha)


def upper_bound(x: int, n: int, alpha: float) -> float:
    return 1.0 if x == n else _solve(lambda p: _tail(x + 1, n, p), 1 - alpha)


def tokens_by_class(row: dict[str, object]) -> dict[str, set[str]]:
    text = "".join(str(row["raw"]).split()).upper()
    pieces = text.split("X")
    found: dict[str, set[str]] = {"opening": set(), "address": set(), "sign_off": set()}
    if pieces[0]:
        found["opening"].add(pieces[0])
    last = pieces[-1] or (pieces[-2] if len(pieces) > 1 else "")
    if last and not row.get("truncated") and len(pieces) > 1:
        found["sign_off"].add(last)
    if row.get("address_end") is not None:
        offset = 0
        for piece in pieces:
            if piece and offset + len(piece) <= int(row["address_end"]):
                found["address"].add(piece)
            offset += len(piece) + 1
    return found


def candidates(train: list[dict[str, object]], catalogue: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: dict[tuple[str, str], int] = {}
    for row in train:
        for klass, toks in tokens_by_class(row).items():
            for tok in toks:
                seen[(klass, tok)] = seen.get((klass, tok), 0) + 1
    out = [
        {"id": f"train-{klass}-{tok}", "text": tok, "evidence_level": "train_recurring",
         "class": klass, "training_messages": n}
        for (klass, tok), n in sorted(seen.items())
        if n >= 2
    ]
    out += [dict(c, **{"class": None, "training_messages": None}) for c in catalogue]
    return out


def split(rows: list[dict[str, object]], excluded: set[str]) -> tuple[list, list]:
    rows = [r for r in rows if r["id"] not in excluded]
    train = [r for r in rows if r["date"] <= TRAIN_END]
    evaluate = [r for r in rows if EVALUATE[0] <= r["date"] <= EVALUATE[1]]
    return train, evaluate


def union_rate(counts: dict[str, object], evaluate_ids: list[str], classes: tuple[str, ...]) -> list[str]:
    hit: set[str] = set()
    for crib in counts["cribs"]:
        for variant in crib["by_variant"].values():
            for message_id, found in variant["hits"].items():
                if any(h["position_class"] in classes for h in found):
                    hit.add(message_id)
    return sorted(hit & set(evaluate_ids))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plaintexts", default=str(ROOT / "data/phase2/held-out-plaintexts.json"))
    parser.add_argument("--cribs", default=str(ROOT / "cribs.json"))
    parser.add_argument("--output", default=str(ROOT / "data/phase2/crib-prior-v1-result.json"))
    args = parser.parse_args(argv)
    doc = json.loads(pathlib.Path(args.plaintexts).read_text(encoding="utf-8"))
    catalogue = json.loads(pathlib.Path(args.cribs).read_text(encoding="utf-8"))["cribs"]
    train, evaluate = split(doc["plaintexts"], set(doc["source"]["excluded"]))
    cands = candidates(train, catalogue)
    cand_cribs = [{"id": c["id"], "text": c["text"], "evidence_level": c["evidence_level"]} for c in cands]
    train_counts = count(train, cand_cribs)
    eval_counts = count(evaluate, cand_cribs)
    ids = [r["id"] for r in evaluate]
    n = len(evaluate)
    u_all = union_rate(eval_counts, ids, ("opening", "address", "sign_off", "other"))
    u_listed = union_rate(eval_counts, ids, CLASSES)
    enabled = {c["id"] for c in catalogue if c.get("enabled_by_default")}
    enabled_counts = count(evaluate, [c for c in cand_cribs if c["id"] in enabled])
    u_enabled = union_rate(enabled_counts, ids, ("opening", "address", "sign_off", "other"))

    def rate(hits: list[str]) -> dict[str, object]:
        x = len(hits)
        return {"messages_hit": hits, "x": x, "n": n, "u": x / n if n else None,
                "u_L80": lower_bound(x, n, 0.20) if n else None,
                "interval_95_exact": [lower_bound(x, n, 0.025), upper_bound(x, n, 0.025)] if n else None}

    main_rate = rate(u_all)
    d_lower = main_rate["u_L80"] or 0.0
    result = {
        "schema": "enigma-attack.phase2-crib-prior-result/v1",
        "experiment_id": "phase2-crib-prior-v1",
        "split": {"train_end": TRAIN_END, "evaluate": list(EVALUATE),
                  "train_ids": [r["id"] for r in train], "evaluate_ids": ids},
        "messages_with_address_annotation": {"train": train_counts["messages_with_address_annotation"],
                                              "evaluate": eval_counts["messages_with_address_annotation"]},
        "candidates_from_train_only": [{k: c[k] for k in ("id", "text", "evidence_level", "class", "training_messages")} for c in cands],
        "train_counts": train_counts,
        "evaluate_counts": eval_counts,
        "union": {"all_catalogued_and_train_recurring_incl_other": main_rate,
                  "listed_classes_only_excluding_other": rate(u_listed),
                  "default_enabled_cribs_only_incl_other": rate(u_enabled)},
        "batch_c_linked_subset": {"messages": 0, "why": "no held-out message carries a callsign, frequency or operator; the source gives none"},
        "gates": {
            "G1": {"rule": f"evaluate split holds at least {G1_MINIMUM} solved messages", "n": n, "pass": n >= G1_MINIMUM},
            "G2": {"rule": "t established by a cited source", "pass": False,
                   "why": "Set by hand from the cited paper (Sullivan and Weierud 2005, footnote 42 to Figure 11): Batch C is from a different radio network than the other 1941 messages. No cited source links the solved messages to Batch C."},
            "G3": {"rule": "D_L = u_L80 * r_L >= 0.29, checked with r = 1", "D_L_with_r_1": d_lower,
                   "pass": d_lower >= G3_THRESHOLD, "r": "not measured; r = 1 is the necessary condition"},
            "G4": {"rule": "D / E_run >= 0.013 per host-hour", "pass": None, "why": "not evaluated: no Bombe exists to time"},
        },
    }
    result["verdict"] = ("Bombe not preferred" if not all(g["pass"] for g in result["gates"].values() if g["pass"] is not None)
                         or result["gates"]["G4"]["pass"] is None else "Bombe preferred")
    pathlib.Path(args.output).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"n_train": len(train), "n_evaluate": n, "u": main_rate["u"], "u_L80": main_rate["u_L80"],
                      "gates": {k: v["pass"] for k, v in result["gates"].items()}, "verdict": result["verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
