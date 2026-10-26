#!/usr/bin/env python3
"""Joint confirmation/observed-cutoff calibration of fresh low-IC power draws."""
import argparse
import concurrent.futures
import datetime
import json
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import joint_power_estecker_v1 as joint
from provenance import code_version, sha256_file
CONFIG = ROOT / 'experiments/phase1-low-ic-joint-v1/config.json'
POWER = ROOT / 'artifacts/phase1-low-ic-joint-v1.json'
OUTPUT = ROOT / 'artifacts/phase1-low-ic-joint-v1-joint.json'

def initialize(config):
    joint.init(config)
    joint.COMPANION_SEED = config['joint_analysis']['companion_seed']

def summarise(rows, names, cutoffs):
    result = {}
    for index, name in enumerate(names):
        mine = [r for r in rows if r['cell'] == index]
        arms = {}
        for arm, cutoff in cutoffs.items():
            record = {'retention_cutoff': cutoff}
            for metric in ('detected', 'retained', 'confirmed', 'sweep_success'):
                record[metric] = joint.rate(mine, arm, lambda a, metric=metric: a[metric])
            for metric in ('confirmed', 'retained', 'sweep_success'):
                record[metric + '_given_detected'] = joint.conditional(
                    mine, arm, lambda a: a['detected'], lambda a, metric=metric: a[metric])
            arms[arm] = record
        result[name] = {'draws': len(mine), 'arms': arms}
    return result


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    # check_artifacts.py regenerates into a temporary path with --output.
    parser.add_argument('--output', type=pathlib.Path, default=OUTPUT)
    return parser.parse_args(argv)


def main(argv=None):
    output = parse_arguments(argv).output
    config = json.loads(CONFIG.read_text())
    power = json.loads(POWER.read_text())
    spec = config['joint_analysis']
    cutoffs = {a: min(r['score_per_letter'] for r in json.loads((ROOT / p).read_text())['result']['top_candidates']) for a,p in spec['sweeps'].items()}
    thresholds = {i:{a:(next(x for x in c['arms'] if x['arm']==a).get('null') or c['null'])['detection_threshold_score_per_letter'] for a in cutoffs} for i,c in enumerate(power['result']['cells'])}
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    version = code_version()
    with concurrent.futures.ProcessPoolExecutor(max_workers=8, initializer=initialize, initargs=(config,)) as pool:
        rows = list(pool.map(joint.one_draw,[(d,thresholds,cutoffs) for d in power['result']['draws']]))
    names = ['clean' if c['perturbation']=='none' else c['perturbation'] for c in power['result']['cells']]
    cells = summarise(rows,names,cutoffs)
    gains = {n: cells[n]['arms']['complete_w117_rngonly']['sweep_success']['rate']-cells[n]['arms']['complete_w117_estecker']['sweep_success']['rate'] for n in names}
    payload = {'experiment_id':'phase1-low-ic-joint-v1','started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code':version,'inputs':{'config':sha256_file(CONFIG),'power':sha256_file(POWER),**{a:sha256_file(ROOT/p) for a,p in spec['sweeps'].items()}},'retention_limitation':spec['retention'],'cells':cells,'paired_gain':gains,'hypothesis_passed':gains['clean']>=spec['hypothesis_gain'],'draws':rows}
    output.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({'gains':gains,'passed':payload['hypothesis_passed']}))
if __name__=='__main__':main()
