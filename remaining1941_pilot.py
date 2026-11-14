#!/usr/bin/env python3
"""Bounded, companion-free feasibility pilot. No full-keyspace power claim."""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import sys
import time

from enigma import EnigmaI
import enigma_fast as ef
from provenance import code_version
from remaining1941_inventory import build
from scripts.review.independent_enigma import independent_crypt
from stecker_batch import BatchedClimber
from stecker_climb import run_climb_phases, coincidence_of_decryption
from stecker_scoring import FastNgramScorer

ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / "experiments/remaining-1941-pilot-v1/config.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def masked_crypt(key, start, value, independent=False):
    """Advance through every unknown position; never pass '?' to EnigmaI.crypt."""
    raw = value.replace("?", "A")
    if independent:
        out = independent_crypt(key["rotors"], key["rings"], start, key["plugboard"], raw)
    else:
        out = EnigmaI(rotors=key["rotors"], rings=key["rings"], positions=start,
                      plugboard=key["plugboard"], reflector="B").crypt(raw)
    return "".join("?" if c == "?" else p for c, p in zip(value, out))


def verify(key, start, ciphertext, indicator, plaintext):
    independent = masked_crypt(key, start, ciphertext, True)
    reencryption = masked_crypt(key, start, plaintext, True)
    expected = EnigmaI(rotors=key["rotors"], rings=key["rings"], positions=indicator[0],
                       plugboard=key["plugboard"]).crypt(indicator[1])
    return dict(independent_plaintext_matches=independent == plaintext,
                complete_observed_ciphertext_matches=reencryption == ciphertext,
                indicator_start=expected, indicator_matches=expected == start,
                unknown_positions_not_verified=ciphertext.count("?"))


def climb(scorer, body, key, settings):
    values = ef.text_to_indices(body)
    table = ef.position_permutations([ef.rotor_tables(x) for x in key["rotors"]],
                                    ef.text_to_indices(key["rings"]), ef.text_to_indices(key["start"]), len(body))
    board, count = BatchedClimber(scorer.bigram, scorer.combined, values, settings).climb(table)
    plain = ef.indices_to_text(ef.decrypt_with_tables(table, values, board))
    return dict(plugboard=ef.plugboard_pairs(board), plaintext=plain,
                score=scorer.score_text(plain)/sum(c != "?" for c in body), evaluations=count)


def random_key(rng, order=None):
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    rng.shuffle(letters)
    return dict(rotors=list(order or rng.sample(["I","II","III","IV","V"], 3)),
                rings="".join(rng.choices(letters, k=3)), start="".join(rng.choices(letters, k=3)),
                plugboard=" ".join("".join(sorted(letters[i:i+2])) for i in range(0,20,2)))


def all_starts(scorer, body, key):
    """Known daily key only: enumerate all 26^3 starts and retain raw scores."""
    values = ef.text_to_indices(body)
    order = [ef.rotor_tables(x) for x in key["rotors"]]
    rings = ef.text_to_indices(key["rings"])
    board = ef.plugboard_table(key["plugboard"])
    scores = []
    for pos in itertools.product(range(26), repeat=3):
        plain = ef.crypt_indices(order, rings, pos, values, board)
        scores.append(scorer.score_indices(plain)/sum(c >= 0 for c in values))
    ranked = sorted(range(17576), key=lambda i: (-scores[i], i))
    top = []
    for i in ranked[:10]:
        start = ef.indices_to_text((i//676, (i//26)%26, i%26))
        top.append(dict(start=start, score=scores[i], plaintext=masked_crypt(key, start, body)))
    return scores, top


def historical_allowed(preflight, known_start_successes, exact_masked, cfg):
    return (all(preflight.values()) and known_start_successes == cfg["fixed_key_controls"]
            and exact_masked >= cfg["minimum_masked_recoveries_for_pilot"])


def run(config_path=DEFAULT):
    cfg = json.loads(Path(config_path).read_text())
    output = ROOT / cfg["output"]
    if output.exists():
        raise ValueError("Refusing to overwrite a run: use a new output path/config version")
    output.mkdir(parents=True)
    start_time = time.monotonic()
    inventory = build()
    target = next(m for m in inventory["messages"] if m["id"] == cfg["target"])
    if target["status"] != "unresolved" or cfg["target"] in inventory["excluded"]:
        raise ValueError("Target is solved or excluded")
    scorer = FastNgramScorer(cfg["scorer"])
    records = []
    def record(kind, **values):
        row = dict(kind=kind, **values)
        records.append(row)
        with (output/"raw.jsonl").open("a") as f:
            f.write(json.dumps(row, sort_keys=True)+"\n")
        print(kind, values.get("draw", values.get("index", "")), flush=True)
    def within_budget():
        return time.monotonic()-start_time < cfg["wall_budget_seconds"]
    inputs = [config_path, ROOT/"data/remaining-1941/inventory.json",
              ROOT/"data/remaining-1941/sources/manifest.json", ROOT/cfg["plaintext_source"],
              ROOT/cfg["scorer"]["bigram_counts"], ROOT/cfg["scorer"]["trigram_counts"]]
    pre = dict(code=code_version(), config=cfg,
               inputs={str(Path(p).relative_to(ROOT)):digest(p) for p in inputs},
               environment=dict(python=sys.version, platform=platform.platform(),
                                logical_cpus=os.cpu_count(), workers=1,
                                numpy=__import__("numpy").__version__, cpu=platform.processor(),
                                cpu_model=next((x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')), 'unknown'),
                                thread_environment={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}),
               started_utc=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
    (output/"prerun.json").write_text(json.dumps(pre, indent=2)+"\n")
    kernel = ef.parity_report(cfg["parity_seed"], cfg["parity_samples"])
    # Use explicit fresh parity checks, including erasures and an independent wheel path.
    rng = random.Random(cfg["parity_seed"])
    passed = kernel.get("passed", kernel.get("ok", False))
    independent_ok = True
    batch_ok = True
    for i in range(cfg["independent_parity_samples"]):
        key = random_key(rng)
        pt = "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=target["body_positions"]))
        body = masked_crypt(key, key["start"], pt)
        body = "".join("?" if j+1 in target["erasure_positions_1based"] else c for j,c in enumerate(body))
        independent_ok &= masked_crypt(key,key["start"],body) == masked_crypt(key,key["start"],body,True)
        if i < cfg["batch_reference_samples"]:
            values=ef.text_to_indices(body)
            table=ef.position_permutations([ef.rotor_tables(x) for x in key["rotors"]],ef.text_to_indices(key["rings"]),ef.text_to_indices(key["start"]),len(body))
            settings=cfg["climb"]
            reference, _, n=run_climb_phases(settings["phases"],
                {"index_of_coincidence":lambda b:coincidence_of_decryption(table,values,b),
                 "ngram":lambda b:scorer.score_decryption(table,values,b)},len(body)-body.count("?"),settings)
            batch=climb(scorer,body,key,settings)
            batch_ok &= batch["plugboard"] == ef.plugboard_pairs(reference) and batch["evaluations"] == n
    checks=dict(kernel=bool(passed), independent=bool(independent_ok), batched_reference=bool(batch_ok))
    record("preflight", checks=checks, kernel=kernel)
    if not all(checks.values()):
        raise RuntimeError("Preflight failed; no historical search")
    source=json.loads((ROOT/cfg["plaintext_source"]).read_text())["messages"]
    texts=[]
    for spec in cfg["plaintext_windows"]:
        entry=next(m for m in source if m["id"]==spec["id"])
        pt=entry["raw_plaintext"][spec["offset"]:spec["offset"]+target["body_positions"]]
        if len(pt)!=target["body_positions"] or re_nonletters(pt):
            raise ValueError("invalid planted plaintext window")
        texts.append(pt)
    fixed_key=cfg["fixed_key_hypothesis"]["key"]
    fixed_success=0
    for i in range(cfg["fixed_key_controls"]):
        rng=random.Random(cfg["plant_seed"]+i)
        key=copy.deepcopy(fixed_key)
        position="".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ",k=3))
        ct=masked_crypt(key,position,texts[i%len(texts)])
        ct="".join("?" if j+1 in target["erasure_positions_1based"] else c for j,c in enumerate(ct))
        scores,top=all_starts(scorer,ct,key)
        rank=next(j+1 for j,n in enumerate(sorted(range(17576),key=lambda n:(-scores[n],n))) if ef.indices_to_text((n//676,(n//26)%26,n%26))==position)
        fixed_success += top[0]["start"]==position
        record("fixed_key_control",draw=i,start=position,rank=rank,top=top,all_scores=scores)
        if not within_budget():
            raise RuntimeError("budget exhausted in controls; no historical search")
    masked_success=0
    successes={"baseline_clean":0,"baseline_masked":0,"E_clean":0,"E_masked":0}
    for i in range(cfg["plant_draws"]):
        rng=random.Random(cfg["plant_seed"]+1000+i)
        key=random_key(rng)
        pt=texts[i%len(texts)]
        ct=masked_crypt(key,key["start"],pt)
        for fault in ("clean","masked"):
            body=ct if fault=="clean" else "".join("?" if j+1 in target["erasure_positions_1based"] else c for j,c in enumerate(ct))
            truth=masked_crypt(key,key["start"],body)
            for arm in ("baseline","E"):
                settings=cfg["baseline_climb"] if arm=="baseline" else cfg["climb"]
                recovered=climb(scorer,body,key,settings)
                exact_pt=recovered["plaintext"]==truth
                exact_pb=ef.plugboard_table(recovered["plugboard"])==ef.plugboard_table(key["plugboard"])
                recovered_key={**key,"plugboard":recovered["plugboard"]}
                grund="".join(random.Random(cfg["plant_seed"]+2000+i).choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ",k=3))
                encoded=EnigmaI(rotors=key["rotors"],rings=key["rings"],positions=grund,plugboard=key["plugboard"]).crypt(key["start"])
                verification=verify(recovered_key,key["start"],body,[grund,encoded],recovered["plaintext"])
                successes[arm+"_"+fault] += exact_pt and exact_pb and verification["indicator_matches"] and verification["complete_observed_ciphertext_matches"] and verification["independent_plaintext_matches"]
                record("plant",draw=i,text_index=i%len(texts),fault=fault,arm=arm,key=key,
                       plaintext=pt,ciphertext=body,indicator=[grund,encoded],recovered=recovered,
                       exact_plaintext=exact_pt,exact_plugboard=exact_pb,verification=verification)
        if not within_budget():
            raise RuntimeError("budget exhausted in controls; no historical search")
    masked_success=successes["E_masked"]
    allowed=historical_allowed(checks,fixed_success,masked_success,cfg)
    record("gate", allowed=allowed, fixed_key_recovered=fixed_success, recoveries=successes,
           note="Plugboard recovery conditional on supplied true mechanics. Not end-to-end full-key search power.")
    candidates=[]
    if allowed:
        # Known published decrypts are controls, never new breaks.
        for message in inventory["messages"]:
            if "published_key" not in message:
                continue
            key=message["published_key"]
            pt=masked_crypt(key,key["start"],message["ciphertext"])
            record("published_key_reproduction",id=message["id"],plaintext=pt,
                   verification=verify(key,key["start"],message["ciphertext"],message["indicator"],pt))
        scores,top=all_starts(scorer,target["ciphertext"],fixed_key)
        indicated=EnigmaI(rotors=fixed_key["rotors"],rings=fixed_key["rings"],positions=target["indicator"][0],plugboard=fixed_key["plugboard"]).crypt(target["indicator"][1])
        record("historical_fixed_key",id=target["id"],all_scores=scores,top=top,
               indicator_start=indicated, indicator_plaintext=masked_crypt(fixed_key,indicated,target["ciphertext"]))
        rng=random.Random(cfg["pilot_seed"])
        for order in ef.standard_rotor_orders():
            for j in range(cfg["settings_per_order"]):
                if not within_budget():
                    break
                key=random_key(rng,order)
                # The random plugboard is discarded: every climb starts from its declared boards.
                result=climb(scorer,target["ciphertext"],key,cfg["climb"])
                key["plugboard"]=result["plugboard"]
                row=dict(key=key,**result)
                row["verification"]=verify(key,key["start"],target["ciphertext"],target["indicator"],result["plaintext"])
                candidates.append(row)
                record("pilot_setting",index=len(candidates)-1,**row)
            if not within_budget():
                break
    summary=dict(experiment_id=cfg["experiment_id"],controls=successes,
                 fixed_key_controls_recovered=fixed_success, historical_gate=allowed,
                 settings_completed=len(candidates), settings_planned=60*cfg["settings_per_order"],
                 complete_space_mechanical_recovery_probability="unmeasured",
                 raw_parameter_space_mechanical_points=60*26**6,
                 raw_parameter_fraction=len(candidates)/(60*26**6),
                 sampled_plugboard_search="heuristic; at most ten pairs; not exhaustive",
                 top=sorted(candidates,key=lambda r:-r["score"])[:10],
                 elapsed_seconds=time.monotonic()-start_time,
                 accepted_new_plaintexts=[],
                 status="bounded_pilot_complete" if allowed and len(candidates)==60*cfg["settings_per_order"] else "stopped_or_gated")
    (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="top"},indent=2))
    return summary


def re_nonletters(value):
    return any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in value)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=DEFAULT)
    run(parser.parse_args().config)
