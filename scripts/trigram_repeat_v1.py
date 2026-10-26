#!/usr/bin/env python3
"""Weierud's trigram-repeat test on the five Batch C messages.

Written for phase5-trigram-repeat-v1 and driven by its configuration. Each
target is scored against simulated Enigma I ciphertexts of Army plaintext at
its own length, with its uncertain positions masked the same way. The null is
calibrated on the 13 authentic keyed ciphertexts in
``data/historical/keyed-messages.json``, and length-matched windows of their
plaintext show where a pattern-keeping cipher would land.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enigma import A, EnigmaI  # noqa: E402
from phase5 import index_of_coincidence  # noqa: E402
from provenance import code_version, sha256_file  # noqa: E402

WHEELS = ("I", "II", "III", "IV", "V")
UNCERTAIN = "?"
STATISTICS = ("trigram_repeats", "repeated_trigrams", "index_of_coincidence", "longest_repeat")


def ngram_positions(text: str, n: int) -> dict[str, list[int]]:
    """Start positions of each n-gram, skipping windows with an uncertain letter."""
    positions: dict[str, list[int]] = {}
    for i in range(len(text) - n + 1):
        window = text[i:i + n]
        if UNCERTAIN not in window:
            positions.setdefault(window, []).append(i)
    return positions


def ngram_repeats(text: str, n: int) -> int:
    """Extra occurrences of repeated n-grams: the sum of (count - 1) over n-grams seen twice or more."""
    return sum(len(p) - 1 for p in ngram_positions(text, n).values() if len(p) >= 2)


def trigram_positions(text: str) -> dict[str, list[int]]:
    return ngram_positions(text, 3)


def longest_repeat(text: str) -> int:
    best = 0
    length = 1
    while True:
        seen: set[str] = set()
        found = False
        for i in range(len(text) - length + 1):
            window = text[i:i + length]
            if UNCERTAIN in window:
                continue
            if window in seen:
                found = True
                break
            seen.add(window)
        if not found:
            return best
        best = length
        length += 1


def measure(text: str) -> dict:
    counts = [len(p) for p in trigram_positions(text).values()]
    return {
        "trigram_repeats": sum(k - 1 for k in counts if k >= 2),
        "repeated_trigrams": sum(1 for k in counts if k >= 2),
        "index_of_coincidence": index_of_coincidence(text),
        "longest_repeat": longest_repeat(text),
    }


def repeats_listed(text: str) -> list[dict]:
    return [
        {"trigram": t, "positions": p}
        for t, p in sorted(trigram_positions(text).items(), key=lambda item: (-len(item[1]), item[1][0]))
        if len(p) >= 2
    ]


def random_key(rng: random.Random) -> dict:
    letters = list(A)
    rng.shuffle(letters)
    return {
        "rotors": tuple(rng.sample(WHEELS, 3)),
        "rings": "".join(rng.choice(A) for _ in range(3)),
        "positions": "".join(rng.choice(A) for _ in range(3)),
        "plugboard": " ".join(letters[i] + letters[i + 1] for i in range(0, 20, 2)),
    }


def enigma_null(pool: str, length: int, masked: list[int], draws: int, rng: random.Random) -> list[dict]:
    out = []
    for _ in range(draws):
        start = rng.randrange(len(pool) - length + 1)
        text = list(EnigmaI(**random_key(rng)).crypt(pool[start:start + length]))
        for i in masked:
            text[i] = UNCERTAIN
        out.append(measure("".join(text)))
    return out


def p_upper(observed: float, null: list[dict], name: str) -> float:
    return (1 + sum(1 for d in null if d[name] >= observed)) / (1 + len(null))


def summary(values: list[float]) -> dict:
    ordered = sorted(values)

    def point(q: float) -> float:
        return ordered[min(len(ordered) - 1, int(q * len(ordered)))]

    return {"median": statistics.median(ordered), "p2_5": point(0.025), "p97_5": point(0.975),
            "max": ordered[-1]}


def score(text: str, null: list[dict]) -> dict:
    observed = measure(text)
    return {
        "observed": observed,
        "p_values": {name: p_upper(observed[name], null, name) for name in STATISTICS},
        "enigma_null": {name: summary([d[name] for d in null]) for name in STATISTICS},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="experiments/phase5-trigram-repeat-v1/config.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--draws", type=int, default=None, help="override, for smoke runs only")
    arguments = parser.parse_args()

    code = code_version()
    config_path = ROOT / arguments.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    null_config = config["enigma_null"]
    if arguments.draws is not None and arguments.output is None:
        parser.error("--draws changes the experiment; pass --output so the committed artifact is not replaced")
    draws = null_config["draws_per_target"] if arguments.draws is None else arguments.draws
    threshold = config["decision"]["threshold"]

    keyed_path = ROOT / "data" / "historical" / "keyed-messages.json"
    keyed = json.loads(keyed_path.read_text(encoding="utf-8"))["messages"]
    pool = "".join(m["raw_plaintext"].replace("-", "") for m in keyed)
    corpus_path = ROOT / config["corpus"]
    corpus = {m["designator"]: m for m in json.loads(corpus_path.read_text(encoding="utf-8"))["messages"]}

    # Calibration first: a miscalibrated null decides nothing.
    calibration_seed = config["controls"]["authentic_enigma_ciphertexts"]["seed"]
    rng = random.Random(calibration_seed)
    calibration = []
    for m in keyed:
        text = m["ciphertext"].replace("-", UNCERTAIN)
        masked = [i for i, c in enumerate(text) if c == UNCERTAIN]
        result = score(text, enigma_null(pool, len(text), masked, draws, rng))
        calibration.append({"id": m["id"], "length": len(text), **result})
    calibrated = all(c["p_values"]["trigram_repeats"] >= threshold for c in calibration)

    rng = random.Random(null_config["seed"])
    targets = []
    for designator in config["targets"]:
        text = corpus[designator]["ciphertext"]
        masked = [i for i, c in enumerate(text) if c == UNCERTAIN]
        result = score(text, enigma_null(pool, len(text), masked, draws, rng))
        windows = [measure(pool[i:i + len(text)]) for i in range(len(pool) - len(text) + 1)]
        p = result["p_values"]["trigram_repeats"]
        targets.append({
            "designator": designator,
            "length": len(text),
            "uncertain_positions": masked,
            **result,
            "repeats": repeats_listed(text),
            "army_plaintext_windows": {
                "windows": len(windows),
                **{name: summary([w[name] for w in windows]) for name in STATISTICS},
            },
            "flagged": calibrated and p < threshold,
            "secondary_below_threshold": [n for n in STATISTICS[1:] if result["p_values"][n] < threshold],
        })

    flagged = [t["designator"] for t in targets if t["flagged"]]
    artifact = {
        "schema": "enigma-attack.phase5-trigram-repeat-result/v1",
        "experiment_id": config["experiment_id"],
        "code": code,
        "inputs": {
            "config_sha256": sha256_file(config_path),
            "corpus_sha256": sha256_file(corpus_path),
            "keyed_messages_sha256": sha256_file(keyed_path),
            "plaintext_pool_letters": len(pool),
        },
        "draws_per_null": draws,
        "seeds": {"calibration": calibration_seed, "targets": null_config["seed"]},
        "smoke": draws != null_config["draws_per_target"],
        "calibration": {
            "requirement": config["controls"]["authentic_enigma_ciphertexts"]["calibration_requirement"],
            "passed": calibrated,
            "messages": calibration,
        },
        "targets": targets,
        "decision": {
            "threshold": threshold,
            "flagged": flagged,
            "prediction_under_weierud": config["decision"]["prediction_under_weierud"],
            "prediction_held": calibrated and bool(flagged),
        },
    }
    output = ROOT / (arguments.output or config["artifact"])
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"calibrated": calibrated, "flagged": flagged,
                      "p": {t["designator"]: t["p_values"] for t in targets}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
