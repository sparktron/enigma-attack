#!/usr/bin/env python3
"""How much does end-to-end sweep power depend on the planted plaintext?

Exploratory measurement from docs/code-review-2026-10-11.md (B-1).  It is not a
preregistered experiment and writes no artifact under ``artifacts/``.

Every end-to-end power control in the repository plants its keys under one
167-letter constructed plaintext, so the stated powers carry no
plaintext-to-plaintext variance.  This script draws several plaintexts of the
same length from the repository's own published trigram counts, runs the
repository's own power harness (``phase1_stecker.py``, mode
``end_to_end_power``) on each with the *same* keys, and reports detection
against the plaintext's index of coincidence.

Detection is the harness's own rule: the best candidate in the slice recovers the
planted plugboard exactly and scores at least the harness's null threshold.  The
rate reported is conditional on the slice containing an exact equivalent of the
planted key, so coverage is not mixed in.

Examples
    # whole-message climb, past-notch rule (the v2 arm); about 30 s per text
    python3 scripts/review/plaintext_power.py --texts 16 --draws 60

    # the v5 climb (split-point, complete rule); needs the CUDA build
    python3 scripts/review/plaintext_power.py --base-config \\
        experiments/phase1-fault-power-v1/config.json --arm split_complete \\
        --texts 4 --draws 40 --jobs 1

Review results (167 letters, ten pairs, seed 424242, detection given an exact
equivalent in the slice):
    repository plaintext, IC 0.0792: whole-message 0.947 (90/95).
    16 Markov texts, IC 0.0514 to 0.0625 (mean 0.0574), whole-message arm:
        mean 0.359 (270/752), range 0.11 to 0.64, Pearson r with IC 0.87
    Corrected v5 rerun, 2026-10-12, 40 draws per text:
        repository IC 0.0792: 39/40 (0.975)
        Markov IC 0.0578: 8/40; 0.0574: 22/40; 0.0600: 15/40; 0.0625: 22/40
        pooled Markov detection 67/160 (0.419), mean IC 0.0594, Pearson r 0.39,
        slope +2.8 percentage points per +0.001 IC.
        Raw configs and outputs: data/review/plaintext-power-2026-10-12/.
        Detection only; companion confirmation and four-arm union not measured.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import random
import statistics
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import phase7  # noqa: E402


def ngram_tables(config: dict):
    scorer = config["scorer"]
    bigrams = phase7.load_counts(phase7.resolve_path(scorer["bigram_counts"]), 2)
    trigrams = phase7.load_counts(phase7.resolve_path(scorer["trigram_counts"]), 3)
    after_pair = collections.defaultdict(list)
    for gram, count in trigrams.items():
        after_pair[gram[:2]].append((gram[2], count))
    after_letter = collections.defaultdict(list)
    for gram, count in bigrams.items():
        after_letter[gram[0]].append((gram[1], count))
    return bigrams, after_pair, after_letter


def markov_text(generator: random.Random, tables, length: int) -> str:
    bigrams, after_pair, after_letter = tables
    starts = list(bigrams)
    text = list(generator.choices(starts, [bigrams[k] for k in starts])[0])
    while len(text) < length:
        options = after_pair.get("".join(text[-2:])) or after_letter[text[-1]]
        letters, weights = zip(*options)
        text.append(generator.choices(letters, weights)[0])
    return "".join(text)


def coincidence(text: str) -> float:
    counts = collections.Counter(text)
    return sum(v * (v - 1) for v in counts.values()) / (len(text) * (len(text) - 1))


def run_one(base: dict, plaintext: str, arm: str, draws: int, seed: int, jobs: int, workdir: pathlib.Path, tag: str):
    config = json.loads(json.dumps(base))
    power = config["end_to_end_power"]
    power["plaintext"] = plaintext
    # A configured list of plaintexts takes precedence over the singular field.
    power.pop("plaintexts", None)
    power["draws"] = draws
    power["seed"] = seed
    power["cells"] = [{"length": 167, "perturbation": "none"}]
    power["arms"] = [a for a in power["arms"] if a["id"] == arm]
    if not power["arms"]:
        raise SystemExit(f"no arm {arm!r} in the base configuration")
    power["headline_arm"] = arm
    power["predictions"] = []
    config["experiment_id"] = f"review-plaintext-power-{tag}"
    output = workdir / f"{tag}.json"
    config["output"] = str(output)
    config_path = workdir / f"{tag}.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "phase1_stecker.py"), "--config", str(config_path),
         "--output", str(output), "--jobs", str(jobs)],
        cwd=ROOT, check=True, capture_output=True,
    )
    result = json.loads(output.read_text(encoding="utf-8"))["result"]
    cell = result["cells"][0]
    # Windowed, split-point, repaired and first-plug arms calibrate their own null;
    # the others use the cell's pooled null.
    arm_record = next(a for a in cell["arms"] if a["arm"] == arm)
    threshold = (arm_record.get("null") or cell["null"])["detection_threshold_score_per_letter"]
    rows = [d["arms"][arm] for d in result["draws"]]
    equivalent = [r for r in rows if r["exact_equivalent_exists"]]
    # The harness's own rule: the planted plugboard is recovered exactly and the
    # score reaches the null threshold.
    detected = sum(
        1 for r in equivalent
        if r["top"]["plugboard_recovered_exactly"] and r["top"]["score_per_letter"] >= threshold
    )
    return detected, len(equivalent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-config", default="experiments/phase1-end-to-end-power-v1/config.json")
    parser.add_argument("--arm", default="middle_past_notch")
    parser.add_argument("--texts", type=int, default=8)
    parser.add_argument("--draws", type=int, default=60)
    parser.add_argument("--jobs", type=int, default=12)
    parser.add_argument("--seed", type=int, default=424242, help="key-draw seed, shared by every text")
    parser.add_argument("--text-seed", type=int, default=11)
    parser.add_argument("--no-repo-plaintext", action="store_true")
    parser.add_argument("--workdir", default=None, help="where harness outputs go (default: a temp dir)")
    arguments = parser.parse_args()

    base = json.loads((ROOT / arguments.base_config).read_text(encoding="utf-8"))
    workdir = pathlib.Path(arguments.workdir or tempfile.mkdtemp(prefix="plaintext-power-"))
    workdir.mkdir(parents=True, exist_ok=True)
    tables = ngram_tables(base)
    generator = random.Random(arguments.text_seed)
    texts: list[tuple[str, str]] = []
    if not arguments.no_repo_plaintext:
        texts.append(("repository", base["end_to_end_power"]["plaintext"][:167]))
    texts += [(f"markov-{i}", markov_text(generator, tables, 167)) for i in range(arguments.texts)]

    rows = []
    for tag, text in texts:
        detected, equivalent = run_one(
            base, text, arguments.arm, arguments.draws, arguments.seed, arguments.jobs, workdir, tag
        )
        rows.append((tag, coincidence(text), detected, equivalent))
        print(f"{tag:12s} IC {coincidence(text):.4f}  detected|exact-equivalent {detected}/{equivalent} = "
              f"{detected / max(1, equivalent):.2f}", flush=True)

    markov = [r for r in rows if r[0] != "repository"]
    if len(markov) >= 3:
        ics = [r[1] for r in markov]
        rates = [r[2] / max(1, r[3]) for r in markov]
        mi, mr = statistics.mean(ics), statistics.mean(rates)
        sxx = sum((x - mi) ** 2 for x in ics)
        sxy = sum((x - mi) * (y - mr) for x, y in zip(ics, rates))
        syy = sum((y - mr) ** 2 for y in rates)
        r = sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")
        print(f"markov texts: mean IC {mi:.4f}, mean detection {mr:.3f}, Pearson r {r:.2f}, "
              f"slope {sxy / sxx * 0.001 * 100:+.1f} points per +0.001 IC")
    print(f"harness outputs in {workdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
