#!/usr/bin/env python3
"""The J-less, flatter-than-Enigma signature of FKQLZ and XFEDT.

Written for phase5-jless-flat-v1 (a disclosed post-hoc test) and driven by its
configuration. Each target is scored against simulated Enigma I ciphertexts of
Army plaintext at its own length by a joint statistic: how often the null is at
least as J-poor *and* at least as flat. The null is calibrated on the 13
authentic keyed ciphertexts, and the ten grey texts without Enigma-type
indicators show what the statistic does on the J-less system itself.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from enigma import A, EnigmaI  # noqa: E402
from phase5 import index_of_coincidence  # noqa: E402
from provenance import code_version, sha256_file  # noqa: E402
from trigram_repeat_v1 import UNCERTAIN, ngram_repeats, random_key, summary  # noqa: E402

ALPHABET_25 = A.replace("J", "")


def measure(text: str) -> tuple[int, float, int]:
    return text.count("J"), index_of_coincidence(text), ngram_repeats(text, 4)


def masked(text: str, positions: list[int]) -> str:
    letters = list(text)
    for i in positions:
        letters[i] = UNCERTAIN
    return "".join(letters)


def enigma_null(pool: str, length: int, mask: list[int], draws: int, rng: random.Random) -> list[tuple]:
    out = []
    for _ in range(draws):
        start = rng.randrange(len(pool) - length + 1)
        out.append(measure(masked(EnigmaI(**random_key(rng)).crypt(pool[start:start + length]), mask)))
    return out


def uniform25_null(length: int, mask: list[int], draws: int, rng: random.Random) -> list[tuple]:
    return [measure(masked("".join(rng.choice(ALPHABET_25) for _ in range(length)), mask)) for _ in range(draws)]


def tail(count: int, draws: int) -> float:
    return (1 + count) / (1 + draws)


def score(text: str, null: list[tuple]) -> dict:
    j, ic, quad = measure(text)
    n = len(null)
    return {
        "observed": {"j_count": j, "index_of_coincidence": ic, "quadgram_repeats": quad},
        "p_values": {
            "joint_noj_lowic": tail(sum(1 for dj, dic, _ in null if dj <= j and dic <= ic), n),
            "p_noj": tail(sum(1 for dj, _, _ in null if dj <= j), n),
            "p_ic_lower": tail(sum(1 for _, dic, _ in null if dic <= ic), n),
            "quadgram_repeats": tail(sum(1 for _, _, dq in null if dq >= quad), n),
        },
        "null": {
            "draws": n,
            "j_count": summary([d[0] for d in null]),
            "index_of_coincidence": summary([d[1] for d in null]),
            "quadgram_repeats": summary([d[2] for d in null]),
            "fraction_without_j": sum(1 for d in null if d[0] == 0) / n,
        },
    }


def uncertain_positions(text: str) -> list[int]:
    return [i for i, c in enumerate(text) if c == UNCERTAIN]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="experiments/phase5-jless-flat-v1/config.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--scale", type=float, default=None,
                        help="multiply every draw count, for smoke runs only; requires --output")
    arguments = parser.parse_args()
    if arguments.scale is not None and arguments.output is None:
        parser.error("--scale changes the experiment; pass --output so the committed artifact is not replaced")

    code = code_version()
    config_path = ROOT / arguments.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    nulls, controls, decision = config["nulls"], config["controls"], config["decision"]
    threshold = decision["threshold"]

    def draws(count: int) -> int:
        return count if arguments.scale is None else max(1, int(count * arguments.scale))

    keyed_path = ROOT / "data" / "historical" / "keyed-messages.json"
    keyed = json.loads(keyed_path.read_text(encoding="utf-8"))["messages"]
    pool = "".join(m["raw_plaintext"].replace("-", "") for m in keyed)
    grey_path = ROOT / "data" / "phase5" / "grey-texts-ostwald-2023.json"
    grey = json.loads(grey_path.read_text(encoding="utf-8"))["texts"]
    corpus_path = ROOT / config["corpus"]
    corpus = {m["designator"]: m for m in json.loads(corpus_path.read_text(encoding="utf-8"))["messages"]}

    calibration_config = controls["enigma_calibration"]
    rng = random.Random(calibration_config["seed"])
    calibration = []
    for m in keyed:
        text = m["ciphertext"].replace("-", UNCERTAIN)
        null = enigma_null(pool, len(text), uncertain_positions(text), draws(calibration_config["draws"]), rng)
        calibration.append({"id": m["id"], "length": len(text), **score(text, null)})
    calibrated = all(c["p_values"]["joint_noj_lowic"] >= threshold for c in calibration)

    grey_config = controls["grey_positive"]
    enigma = nulls["enigma"]
    rng = random.Random(enigma["seed_controls"])
    grey_results = []
    for t in grey:
        null = enigma_null(pool, len(t["text"]), uncertain_positions(t["text"]), draws(enigma["draws_controls"]), rng)
        result = score(t["text"], null)
        grey_results.append({"id": t["id"], "first_group": t["first_group"], "length": len(t["text"]), **result,
                             "below_threshold": result["p_values"]["joint_noj_lowic"] < threshold})
    by_group = {g["first_group"]: g["below_threshold"] for g in grey_results}
    misses = ([f"{g} expected below threshold" for g in grey_config["expected_flagged"] if not by_group[g]]
              + [f"{g} expected not below threshold" for g in grey_config["expected_not_flagged"] if by_group[g]])
    control_met = not misses

    target_rng = random.Random(enigma["seed_targets"])
    uniform_rng = random.Random(nulls["uniform25"]["seed"])
    first_group_rng = random.Random(enigma["seed_first_group_variant"])
    targets = []
    for designator in config["targets"]:
        text = corpus[designator]["ciphertext"]
        mask = uncertain_positions(text)
        result = score(text, enigma_null(pool, len(text), mask, draws(enigma["draws_targets"]), target_rng))
        uniform = score(text, uniform25_null(len(text), mask, draws(nulls["uniform25"]["draws"]), uniform_rng))
        with_first = designator + text
        first_null = enigma_null(pool, len(with_first), uncertain_positions(with_first),
                                 draws(enigma["draws_first_group_variant"]), first_group_rng)
        first = score(with_first, first_null)
        p = result["p_values"]["joint_noj_lowic"]
        targets.append({
            "designator": designator,
            "length": len(text),
            **result,
            "uniform25": {"p_ic_lower": uniform["p_values"]["p_ic_lower"],
                          "index_of_coincidence": uniform["null"]["index_of_coincidence"]},
            "with_first_group": {"quadgram_repeats": first["observed"]["quadgram_repeats"],
                                 "p_quadgram_repeats": first["p_values"]["quadgram_repeats"]},
            "below_threshold": p < threshold,
            "flagged": calibrated and control_met and p < threshold,
        })

    flagged = [t["designator"] for t in targets if t["flagged"]]
    artifact = {
        "schema": "enigma-attack.phase5-jless-flat-result/v1",
        "experiment_id": config["experiment_id"],
        "framing": "disclosed_post_hoc",
        "code": code,
        "inputs": {
            "config_sha256": sha256_file(config_path),
            "corpus_sha256": sha256_file(corpus_path),
            "keyed_messages_sha256": sha256_file(keyed_path),
            "grey_texts_sha256": sha256_file(grey_path),
            "plaintext_pool_letters": len(pool),
        },
        "smoke": arguments.scale is not None,
        "seeds": {"calibration": calibration_config["seed"], "controls": enigma["seed_controls"],
                  "targets": enigma["seed_targets"], "uniform25": nulls["uniform25"]["seed"],
                  "first_group_variant": enigma["seed_first_group_variant"]},
        "calibration": {"requirement": calibration_config["requirement"], "passed": calibrated,
                        "messages": calibration},
        "grey_positive": {"expectation_met": control_met, "misses": misses, "texts": grey_results},
        "targets": targets,
        "decision": {
            "threshold": threshold,
            "flagged": flagged,
            "prediction": decision["prediction"],
            "prediction_held": calibrated and control_met and len(flagged) == len(config["targets"]),
            "valid": calibrated and control_met,
        },
    }
    output = ROOT / (arguments.output or config["artifact"])
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"calibrated": calibrated, "control_met": control_met, "misses": misses, "flagged": flagged},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
