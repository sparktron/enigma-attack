#!/usr/bin/env python3
"""Structure of the flat J-less group against five 25-letter cipher models.

Written for phase5-flat-structure-v1 and driven by its configuration. The six
flat J-less texts are scored on doubled letters, aligned doubles, aligned
digraph repeats and periodic IC, against simulated groups from five models:
uniform random, homophonic substitution (random or cyclic homophone choice),
Playfair, and a double two-square approximation of the Doppelkasten. A power
matrix records whether these statistics can tell the models apart at these
lengths at all.
"""

from __future__ import annotations

import argparse
import bisect
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from provenance import code_version, sha256_file  # noqa: E402

UNCERTAIN = "?"
ALPHABET = "ABCDEFGHIKLMNOPQRSTUVWXYZ"  # 25 letters, no J
PERIODS = range(2, 13)
PRIMARY = ("doubles", "min_aligned_doubles", "aligned_digraph_repeats", "periodic_ic_peak")
TAILS = {"doubles": "two", "min_aligned_doubles": "two", "aligned_digraph_repeats": "two",
         "periodic_ic_peak": "upper", "ic": "two"}
MODELS = ("uniform25", "homophonic_random", "homophonic_cyclic", "playfair", "two_square_double")


# --- statistics ---------------------------------------------------------------

def aligned_doubles(text: str, alignment: int) -> int:
    return sum(1 for i in range(alignment, len(text) - 1, 2)
               if text[i] == text[i + 1] and text[i] != UNCERTAIN)


def text_statistics(text: str) -> dict:
    even, odd = aligned_doubles(text, 0), aligned_doubles(text, 1)
    alignment = 0 if even <= odd else 1
    digraphs: dict[str, int] = {}
    for i in range(alignment, len(text) - 1, 2):
        pair = text[i:i + 2]
        if UNCERTAIN not in pair:
            digraphs[pair] = digraphs.get(pair, 0) + 1
    return {
        "doubles": even + odd,
        "min_aligned_doubles": min(even, odd),
        "aligned_digraph_repeats": sum(n - 1 for n in digraphs.values() if n > 1),
    }


def coincidence(columns: list[str]) -> tuple[int, int]:
    numerator = denominator = 0
    for column in columns:
        letters = [c for c in column if c != UNCERTAIN]
        counts: dict[str, int] = {}
        for c in letters:
            counts[c] = counts.get(c, 0) + 1
        numerator += sum(n * (n - 1) for n in counts.values())
        denominator += len(letters) * (len(letters) - 1)
    return numerator, denominator


def group_statistics(texts: list[str]) -> dict:
    per_text = [text_statistics(t) for t in texts]
    out = {name: sum(s[name] for s in per_text) for name in PRIMARY[:3]}
    by_period = {}
    for p in PERIODS:
        num = den = 0
        for t in texts:
            n, d = coincidence([t[k::p] for k in range(p)])
            num, den = num + n, den + d
        by_period[p] = num / den if den else 0.0
    out["periodic_ic_peak"] = max(by_period.values())
    out["periodic_ic_by_period"] = by_period
    num = den = 0
    for t in texts:
        n, d = coincidence([t])
        num, den = num + n, den + d
    out["ic"] = num / den
    return out


# --- plaintext and models -----------------------------------------------------

def monogram_frequencies(path: pathlib.Path) -> dict[str, float]:
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 2:
            first = parts[0][0].replace("J", "I")
            counts[first] = counts.get(first, 0) + int(parts[1])
    total = sum(counts.values())
    return {c: counts.get(c, 0) / total for c in ALPHABET}


def allocate_homophones(frequencies: dict[str, float]) -> list[dict]:
    """Classes of plaintext letters and their symbol counts, totalling 25."""
    classes = [{"letters": c, "f": f} for c, f in frequencies.items()]
    while True:
        for k in classes:
            k["symbols"] = max(1, round(25 * k["f"]))
        if sum(k["symbols"] for k in classes) <= 25:
            break
        classes.sort(key=lambda k: k["f"])
        a, b = classes[0], classes[1]
        classes = [{"letters": "".join(sorted(a["letters"] + b["letters"])), "f": a["f"] + b["f"]}] + classes[2:]
    while sum(k["symbols"] for k in classes) < 25:
        max(classes, key=lambda k: k["f"] / k["symbols"])["symbols"] += 1
    classes.sort(key=lambda k: -k["f"])
    return classes


def homophonic_tables(classes: list[dict], rng: random.Random) -> dict[str, list[str]]:
    symbols = list(ALPHABET)
    rng.shuffle(symbols)
    table, i = {}, 0
    for k in classes:
        mine = symbols[i:i + k["symbols"]]
        i += k["symbols"]
        for letter in k["letters"]:
            table[letter] = mine
    return table


def homophonic(plaintext: str, table: dict[str, list[str]], rng: random.Random, cyclic: bool) -> str:
    out, position = [], {}
    for c in plaintext:
        options = table[c]
        if cyclic:
            k = position.get(id(options), 0)
            out.append(options[k % len(options)])
            position[id(options)] = k + 1
        else:
            out.append(rng.choice(options))
    return "".join(out)


def random_square(rng: random.Random) -> str:
    letters = list(ALPHABET)
    rng.shuffle(letters)
    return "".join(letters)


def playfair_digraphs(plaintext: str) -> list[tuple[str, str]]:
    pairs, i = [], 0
    while i < len(plaintext):
        a = plaintext[i]
        b = plaintext[i + 1] if i + 1 < len(plaintext) else None
        if b is None or a == b:
            pairs.append((a, "Q" if a == "X" else "X"))
            i += 1
        else:
            pairs.append((a, b))
            i += 2
    return pairs


def playfair(plaintext: str, square: str, decrypt: bool = False) -> str:
    step = -1 if decrypt else 1
    where = {c: divmod(i, 5) for i, c in enumerate(square)}
    pairs = list(zip(plaintext[::2], plaintext[1::2])) if decrypt else playfair_digraphs(plaintext)
    out = []
    for a, b in pairs:
        (r1, c1), (r2, c2) = where[a], where[b]
        if r1 == r2:
            out += [square[r1 * 5 + (c1 + step) % 5], square[r2 * 5 + (c2 + step) % 5]]
        elif c1 == c2:
            out += [square[((r1 + step) % 5) * 5 + c1], square[((r2 + step) % 5) * 5 + c2]]
        else:
            out += [square[r1 * 5 + c2], square[r2 * 5 + c1]]
    return "".join(out)


def two_square_pass(text: str, left: str, right: str) -> str:
    if len(text) % 2:
        text += "Q" if text[-1] == "X" else "X"
    in_left = {c: divmod(i, 5) for i, c in enumerate(left)}
    in_right = {c: divmod(i, 5) for i, c in enumerate(right)}
    out = []
    for a, b in zip(text[::2], text[1::2]):
        (r1, c1), (r2, c2) = in_left[a], in_right[b]
        if r1 != r2:
            out += [right[r1 * 5 + c2], left[r2 * 5 + c1]]
        else:
            out += [right[r1 * 5 + (c2 + 1) % 5], left[r1 * 5 + (c1 + 1) % 5]]
    return "".join(out)


def two_square_unpass(text: str, left: str, right: str) -> str:
    in_left = {c: divmod(i, 5) for i, c in enumerate(left)}
    in_right = {c: divmod(i, 5) for i, c in enumerate(right)}
    out = []
    for x, y in zip(text[::2], text[1::2]):
        (r1, cx), (r2, cy) = in_right[x], in_left[y]
        if r1 != r2:
            out += [left[r1 * 5 + cy], right[r2 * 5 + cx]]
        else:
            out += [left[r1 * 5 + (cy - 1) % 5], right[r1 * 5 + (cx - 1) % 5]]
    return "".join(out)


class Models:
    def __init__(self, pool: str, classes: list[dict]):
        self.pool = pool
        self.classes = classes

    def window(self, length: int, rng: random.Random) -> str:
        start = rng.randrange(len(self.pool) - length + 1)
        return self.pool[start:start + length]

    def text(self, model: str, length: int, rng: random.Random) -> str:
        if model == "uniform25":
            return "".join(rng.choice(ALPHABET) for _ in range(length))
        plaintext = self.window(length, rng)
        if model in ("homophonic_random", "homophonic_cyclic"):
            table = homophonic_tables(self.classes, rng)
            return homophonic(plaintext, table, rng, cyclic=model == "homophonic_cyclic")
        if model == "playfair":
            return playfair(plaintext, random_square(rng))[:length]
        if model == "two_square_double":
            left, right = random_square(rng), random_square(rng)
            return two_square_pass(two_square_pass(plaintext, left, right), left, right)[:length]
        raise ValueError(model)

    def group(self, model: str, shapes: list[tuple[int, list[int]]], rng: random.Random) -> list[str]:
        out = []
        for length, mask in shapes:
            letters = list(self.text(model, length, rng))
            for i in mask:
                letters[i] = UNCERTAIN
            out.append("".join(letters))
        return out


# --- inference ----------------------------------------------------------------

class Null:
    def __init__(self, draws: list[dict]):
        self.n = len(draws)
        self.sorted = {s: sorted(d[s] for d in draws) for s in TAILS}

    def p(self, name: str, observed: float) -> float:
        values = self.sorted[name]
        lower = (1 + bisect.bisect_right(values, observed)) / (1 + self.n)
        upper = (1 + self.n - bisect.bisect_left(values, observed)) / (1 + self.n)
        if TAILS[name] == "upper":
            return upper
        return min(1.0, 2 * min(lower, upper))

    def summary(self, name: str) -> dict:
        v = self.sorted[name]
        return {"p2_5": v[int(0.025 * self.n)], "median": v[self.n // 2], "p97_5": v[min(self.n - 1, int(0.975 * self.n))]}


def judge(observed: dict, null: Null, alpha: float) -> dict:
    p = {name: null.p(name, observed[name]) for name in TAILS}
    return {"p_values": p, "inconsistent_on": [n for n in PRIMARY if p[n] < alpha]}


def simulate(models: Models, model: str, shapes, draws: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    return [group_statistics(models.group(model, shapes, rng)) for _ in range(draws)]


def shapes_of(texts: list[str]) -> list[tuple[int, list[int]]]:
    return [(len(t), [i for i, c in enumerate(t) if c == UNCERTAIN]) for t in texts]


def evaluate(texts, models, draws, seeds, offset, alpha) -> tuple[dict, dict]:
    observed = group_statistics(texts)
    shapes = shapes_of(texts)
    nulls, verdicts = {}, {}
    for m in MODELS:
        nulls[m] = Null(simulate(models, m, shapes, draws, seeds[m] + offset))
        verdicts[m] = {**judge(observed, nulls[m], alpha),
                       "null": {s: nulls[m].summary(s) for s in TAILS}}
        verdicts[m]["consistent"] = not verdicts[m]["inconsistent_on"]
    return {"observed": observed, "lengths": [len(t) for t in texts], "models": verdicts}, nulls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="experiments/phase5-flat-structure-v1/config.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--scale", type=float, default=None,
                        help="multiply every draw count, for smoke runs only; requires --output")
    arguments = parser.parse_args()
    if arguments.scale is not None and arguments.output is None:
        parser.error("--scale changes the experiment; pass --output so the committed artifact is not replaced")

    code = code_version()
    config_path = ROOT / arguments.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    nulls_config, decision, power = config["nulls"], config["decision"], config["power"]
    alpha = decision["alpha"]

    def scaled(n: int) -> int:
        return n if arguments.scale is None else max(2, int(n * arguments.scale))

    keyed_path = ROOT / "data/historical/keyed-messages.json"
    grey_path = ROOT / "data/phase5/grey-texts-ostwald-2023.json"
    corpus_path = ROOT / "corpus.json"
    bigram_path = ROOT / "data/phase7/BigramFrequency1941.txt"
    pool = "".join(m["raw_plaintext"].replace("-", "") for m in
                   json.loads(keyed_path.read_text(encoding="utf-8"))["messages"]).replace("J", "I")
    classes = allocate_homophones(monogram_frequencies(bigram_path))
    models = Models(pool, classes)

    grey = {t["first_group"]: t["text"] for t in json.loads(grey_path.read_text(encoding="utf-8"))["texts"]}
    corpus = {m["designator"]: m["designator"] + m["ciphertext"]
              for m in json.loads(corpus_path.read_text(encoding="utf-8"))["messages"]}
    full = {**grey, **{k: corpus[k] for k in ("FKQLZ", "XFEDT")}}
    group = config["group"]
    flat = [full[k] for k in group["flat"]]
    rough = [full[k] for k in group["rough_comparison"]]
    seeds, offsets = nulls_config["seeds"], nulls_config["seed_offsets"]

    primary, primary_nulls = evaluate(flat, models, scaled(nulls_config["draws"]), seeds, 0, alpha)
    sensitivity, _ = evaluate([t[5:] for t in flat], models, scaled(nulls_config["draws_sensitivity"]),
                              seeds, offsets["sensitivity"], alpha)
    rough_result, _ = evaluate(rough, models, scaled(nulls_config["draws_rough_comparison"]),
                               seeds, offsets["rough_comparison"], alpha)

    shapes = shapes_of(flat)
    matrix = {}
    for index, true_model in enumerate(MODELS):
        draws = simulate(models, true_model, shapes, scaled(power["draws"]), power["seed_base"] + index)
        matrix[true_model] = {
            tested: sum(1 for d in draws if judge(d, primary_nulls[tested], alpha)["inconsistent_on"]) / len(draws)
            for tested in MODELS
        }
    informative = (matrix["uniform25"]["two_square_double"] >= 0.5
                   and matrix["two_square_double"]["uniform25"] >= 0.5)

    verdicts = primary["models"]
    monographic = ("uniform25", "homophonic_random", "homophonic_cyclic")
    hypothesis_held = (verdicts["two_square_double"]["consistent"]
                       and any(not verdicts[m]["consistent"] for m in monographic))
    artifact = {
        "schema": "enigma-attack.phase5-flat-structure-result/v1",
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
        "homophone_allocation": classes,
        "flat_primary": primary,
        "flat_sensitivity_first_group_removed": sensitivity,
        "rough_comparison": rough_result,
        "power": {"rate_declared_inconsistent": matrix, "informative": informative},
        "decision": {
            "alpha": alpha,
            "consistent_models": [m for m in MODELS if verdicts[m]["consistent"]],
            "hypothesis": decision["hypothesis"],
            "hypothesis_held": informative and hypothesis_held,
            "informative": informative,
        },
    }
    output = ROOT / (arguments.output or config["artifact"])
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"informative": informative, "consistent": artifact["decision"]["consistent_models"],
                      "hypothesis_held": artifact["decision"]["hypothesis_held"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
