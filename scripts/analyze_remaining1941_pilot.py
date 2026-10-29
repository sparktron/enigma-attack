#!/usr/bin/env python3
"""Post-run descriptive analysis; does not rerun or tune any search."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from remaining1941_pilot import verify  # noqa: E402


def analyze(root):
    rows = [json.loads(line) for line in (root / "raw.jsonl").read_text().splitlines()]
    summary = json.loads((root / "summary.json").read_text())
    prerecord = json.loads((root / "prerun.json").read_text())
    cfg = prerecord["config"]
    inventory = json.loads((ROOT / "data/remaining-1941/inventory.json").read_text())
    target = next(x for x in inventory["messages"] if x["id"] == cfg["target"])
    pilot = [x for x in rows if x["kind"] == "pilot_setting"]
    plants = [x for x in rows if x["kind"] == "plant"]
    bytext = {}
    for i in range(len(cfg["plaintext_windows"])):
        bytext[i] = {
            arm + "_" + fault: sum(x["exact_plaintext"] and x["exact_plugboard"]
                                   for x in plants if x["text_index"] == i
                                   and x["arm"] == arm and x["fault"] == fault)
            for arm in ("baseline", "E") for fault in ("clean", "masked")
        }
    rechecks = [verify(x["key"], x["key"]["start"], target["ciphertext"],
                       target["indicator"], x["plaintext"]) == x["verification"] for x in pilot]
    analysis = dict(
        raw_sha256=hashlib.sha256((root/"raw.jsonl").read_bytes()).hexdigest(),
        row_counts=dict(Counter(x["kind"] for x in rows)),
        prerecord_input_hashes_still_match=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in prerecord["inputs"].items()),
        per_text_recoveries=bytext, keys_per_text=cfg["plant_draws"]//len(cfg["plaintext_windows"]),
        all_pilot_verifications_reproduced=all(rechecks),
        pilot_indicator_consistent=sum(x["verification"]["indicator_matches"] for x in pilot),
        points_per_order=dict(Counter("-".join(x["key"]["rotors"]) for x in pilot)),
        mechanical_points_unique=len({(tuple(x["key"]["rotors"]),x["key"]["rings"],x["key"]["start"]) for x in pilot}),
        pilot_plugboard_evaluations=sum(x["evaluations"] for x in pilot),
        all_control_and_pilot_plugboard_evaluations=sum(x["recovered"]["evaluations"] for x in plants)+sum(x["evaluations"] for x in pilot),
        all_start_decryptions=sum(len(x["all_scores"]) for x in rows if "all_scores" in x),
        timing_context="Local unit-suite and legacy artifact-validation processes overlapped the pilot. Elapsed time is descriptive, not an idle-host throughput benchmark.",
        main_hypothesis_met=summary["controls"]["E_masked"]>=18,
        larger_blind_search_justified=False,
        interpretation="Inference: conditional plugboard control falls below preregistered75% threshold. Sparse mechanical sampling and single unproven daily-key transfer have unmeasured full-space sensitivity; no cryptographic exclusion follows.")
    (root/"analysis.json").write_text(json.dumps(analysis,indent=2)+"\n")
    return analysis


if __name__ == "__main__":
    analysis = analyze(ROOT/"data/remaining-1941/pilot-v1")
    print(json.dumps({k:v for k,v in analysis.items() if k!="points_per_order"},indent=2))
