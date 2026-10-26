#!/usr/bin/env python3
"""Without-replacement and human-random models for the flat J-less group.

Written for phase5-flat-models-v2 and driven by its configuration. Each new
model's parameter is fitted on the four grey flat texts' pooled IC alone, then
the fitted model is tested on the held-out pair FKQLZ + XFEDT on all five
phase5-flat-structure-v1 statistics, IC included. The full six texts are
reported descriptively.
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
from flat_structure_v1 import (  # noqa: E402
    ALPHABET,
    UNCERTAIN,
    Models,
    Null,
    PRIMARY,
    allocate_homophones,
    group_statistics,
    monogram_frequencies,
    shapes_of,
)
from provenance import code_version, sha256_file  # noqa: E402

TESTED = PRIMARY + ("ic",)


def without_replacement(length: int, k: int, rng: random.Random) -> str:
    """A uniformly random window of a stream of shuffled stocks of k copies of each letter."""
    stock = len(ALPHABET) * k
    offset = rng.randrange(stock)
    stream: list[str] = []
    while len(stream) < offset + length:
        block = list(ALPHABET) * k
        rng.shuffle(block)
        stream += block
    return "".join(stream[offset:offset + length])


def human_random(length: int, window: int, weight: float, rng: random.Random) -> str:
    """Uniform letters, except that any of the previous `window` letters gets `weight` instead of 1."""
    out: list[str] = []
    for _ in range(length):
        recent = set(out[-window:])
        weights = [weight if c in recent else 1.0 for c in ALPHABET]
        if not any(weights):
            weights = [1.0] * len(ALPHABET)
        out.append(rng.choices(ALPHABET, weights)[0])
    return "".join(out)


class Generator:
    """One model at one parameter setting, producing masked groups of given shapes."""

    def __init__(self, name: str, params: dict, baselines: Models | None = None):
        self.name, self.params, self.baselines = name, params, baselines

    def text(self, length: int, rng: random.Random) -> str:
        if self.name == "without_replacement":
            return without_replacement(length, self.params["k"], rng)
        if self.name == "human_random_proxy":
            return human_random(length, self.params["w"], self.params["s"], rng)
        return self.baselines.text(self.name, length, rng)

    def group(self, shapes, rng: random.Random) -> list[str]:
        out = []
        for length, mask in shapes:
            letters = list(self.text(length, rng))
            for i in mask:
                letters[i] = UNCERTAIN
            out.append("".join(letters))
        return out

    def simulate(self, shapes, draws: int, seed: int) -> list[dict]:
        rng = random.Random(seed)
        return [group_statistics(self.group(shapes, rng)) for _ in range(draws)]


def judge(observed: dict, null: Null, alpha: float) -> dict:
    p = {name: null.p(name, observed[name]) for name in TESTED}
    failed = [name for name in TESTED if p[name] < alpha]
    return {"p_values": p, "inconsistent_on": failed, "consistent": not failed}


def grid(spec: dict) -> list[dict]:
    if "k" in spec:
        return [{"k": k} for k in spec["k"]]
    return [{"w": w, "s": s} for w in spec["w"] for s in spec["s"]]


def closeness_to_uniform(params: dict) -> tuple:
    """Tie-break: larger k; smaller w; larger s are closer to uniform letters."""
    if "k" in params:
        return (-params["k"],)
    return (params["w"], -params["s"])


def fit(name: str, spec: dict, shapes, target_ic: float, draws: int, seed: int) -> dict:
    rows = []
    for index, params in enumerate(grid(spec)):
        ics = sorted(d["ic"] for d in Generator(name, params).simulate(shapes, draws, seed + index))
        rows.append({"params": params, "median_ic": ics[len(ics) // 2]})
    best = min(rows, key=lambda r: (abs(r["median_ic"] - target_ic), closeness_to_uniform(r["params"])))
    return {"chosen": best["params"], "chosen_median_ic": best["median_ic"], "grid": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="experiments/phase5-flat-models-v2/config.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--scale", type=float, default=None,
                        help="multiply every draw count, for smoke runs only; requires --output")
    arguments = parser.parse_args()
    if arguments.scale is not None and arguments.output is None:
        parser.error("--scale changes the experiment; pass --output so the committed artifact is not replaced")

    code = code_version()
    config_path = ROOT / arguments.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    fit_config, test, power, texts = config["fit"], config["test"], config["power"], config["texts"]
    alpha = test["alpha"]

    def scaled(n: int) -> int:
        return n if arguments.scale is None else max(2, int(n * arguments.scale))

    keyed_path = ROOT / "data/historical/keyed-messages.json"
    grey_path = ROOT / "data/phase5/grey-texts-ostwald-2023.json"
    corpus_path = ROOT / "corpus.json"
    bigram_path = ROOT / "data/phase7/BigramFrequency1941.txt"
    pool = "".join(m["raw_plaintext"].replace("-", "") for m in
                   json.loads(keyed_path.read_text(encoding="utf-8"))["messages"]).replace("J", "I")
    baselines = Models(pool, allocate_homophones(monogram_frequencies(bigram_path)))
    grey = {t["first_group"]: t["text"] for t in json.loads(grey_path.read_text(encoding="utf-8"))["texts"]}
    corpus = {m["designator"]: m["designator"] + m["ciphertext"]
              for m in json.loads(corpus_path.read_text(encoding="utf-8"))["messages"]}
    full = {**grey, **{k: corpus[k] for k in ("FKQLZ", "XFEDT")}}
    fit_texts = [full[k] for k in texts["fit"]]
    test_texts = [full[k] for k in texts["test"]]
    six = [full[k] for k in texts["descriptive"]]

    fit_observed = group_statistics(fit_texts)
    fits = {name: fit(name, spec["parameter_grid"], shapes_of(fit_texts), fit_observed["ic"],
                      scaled(fit_config["draws_per_grid_point"]), fit_config["seed"] + 100 * i)
            for i, (name, spec) in enumerate((m, config["models"][m])
                                             for m in ("without_replacement", "human_random_proxy"))}

    generators = {
        "without_replacement": Generator("without_replacement", fits["without_replacement"]["chosen"]),
        "human_random_proxy": Generator("human_random_proxy", fits["human_random_proxy"]["chosen"]),
        **{b: Generator(b, {}, baselines) for b in config["models"]["baselines"]},
    }

    def evaluate(group_texts: list[str], offset: int) -> tuple[dict, dict]:
        observed = group_statistics(group_texts)
        shapes = shapes_of(group_texts)
        nulls, verdicts = {}, {}
        for name, generator in generators.items():
            nulls[name] = Null(generator.simulate(shapes, scaled(test["draws"]), test["seeds"][name] + offset))
            verdicts[name] = {**judge(observed, nulls[name], alpha),
                              "null": {s: nulls[name].summary(s) for s in TESTED}}
        return {"observed": observed, "lengths": [len(t) for t in group_texts], "models": verdicts}, nulls

    pair, pair_nulls = evaluate(test_texts, 0)
    descriptive, _ = evaluate(six, test["descriptive_seed_offset"])

    pair_shapes = shapes_of(test_texts)
    power_rows, informative = {}, {}
    for index, name in enumerate(("without_replacement", "human_random_proxy")):
        from_uniform = generators["uniform25"].simulate(pair_shapes, scaled(power["draws"]), power["seed_base"] + 2 * index)
        from_model = generators[name].simulate(pair_shapes, scaled(power["draws"]), power["seed_base"] + 2 * index + 1)
        model_rejected = sum(not judge(d, pair_nulls[name], alpha)["consistent"] for d in from_uniform) / len(from_uniform)
        uniform_rejected = sum(not judge(d, pair_nulls["uniform25"], alpha)["consistent"] for d in from_model) / len(from_model)
        power_rows[name] = {"model_rejected_when_truth_uniform": model_rejected,
                            "uniform_rejected_when_truth_model": uniform_rejected}
        informative[name] = model_rejected >= 0.5 or uniform_rejected >= 0.5

    verdicts = pair["models"]
    failed_informative = [m for m in informative if informative[m] and not verdicts[m]["consistent"]]
    hypothesis_held = (all(informative.values()) and not failed_informative
                       and not verdicts["uniform25"]["consistent"])
    artifact = {
        "schema": "enigma-attack.phase5-flat-models-result/v1",
        "experiment_id": config["experiment_id"],
        "code": code,
        "inputs": {
            "config_sha256": sha256_file(config_path),
            "keyed_messages_sha256": sha256_file(keyed_path),
            "grey_texts_sha256": sha256_file(grey_path),
            "corpus_sha256": sha256_file(corpus_path),
            "bigram_counts_sha256": sha256_file(bigram_path),
        },
        "smoke": arguments.scale is not None,
        "fit": {"observed_ic_fit_texts": fit_observed["ic"], **fits},
        "held_out_pair": pair,
        "descriptive_six_post_hoc": descriptive,
        "power": {"rates": power_rows, "informative": informative},
        "decision": {
            "alpha": alpha,
            "pair_consistent_models": [m for m in verdicts if verdicts[m]["consistent"]],
            "six_consistent_models_post_hoc": [m for m, v in descriptive["models"].items() if v["consistent"]],
            "hypothesis": config["decision"]["hypothesis"],
            "hypothesis_held": hypothesis_held,
        },
    }
    output = ROOT / (arguments.output or config["artifact"])
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hypothesis_held": hypothesis_held, "informative": informative,
                      "pair_consistent": artifact["decision"]["pair_consistent_models"],
                      "six_consistent": artifact["decision"]["six_consistent_models_post_hoc"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
