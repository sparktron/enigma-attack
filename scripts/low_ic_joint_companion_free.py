#!/usr/bin/env python3
"""Companion-free reading of phase1-low-ic-joint-v1.

The preregistered success measure, ``sweep_success``, requires the planted
BYQMZ key to be retained *and* confirmed by the FKQLZ and XFEDT companions.
The planted companions are Enigma ciphertexts by construction, but
phase5-jless-flat-v1 finds the real FKQLZ and XFEDT J-less and flatter than
Enigma output. If they are not Enigma, no real key can be companion-confirmed,
and the measure that applies to the real traffic is the companion-free one:
the planted key is detected (exact plugboard, score above the detection
threshold on BYQMZ's own null) and retained (score at or above the sweep's
kept-candidate cutoff).

Two companion-free measures are reported:

* ``companion_free_success``: detected and retained, the preregistered
  measure with the confirmation step removed;
* ``stands_out``: the exact plugboard is recovered and the planted key's score
  lies above the ceiling of v7's preregistered noise band (prediction
  ``null-top-in-band``, z 9.5 over v7's full score distribution). This is the
  criterion that also applies to the real sweep, where the plugboard cannot be
  checked: a retained candidate above the band would stand out on BYQMZ's own
  letters. The planted texts are scored against v7's BYQMZ distribution, which
  is an approximation: same length, different ciphertexts.

This reads the committed artifacts; it reruns nothing.
It is an analysis added after the result, not part of the preregistration,
whose decision is unchanged.
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from provenance import code_version, sha256_file  # noqa: E402
from stecker_power import wilson_interval  # noqa: E402

JOINT = ROOT / 'artifacts/phase1-low-ic-joint-v1-joint.json'
V7 = ROOT / 'artifacts/phase1-body-direct-sweep-v7.json'
# Upper end of v7's preregistered noise band (experiments/phase1-body-direct-sweep-v7/config.json,
# prediction null-top-in-band: 'between z = 5.5 and z = 9.5'). Stated there in prose only.
BAND_CEILING_Z = 9.5
OUTPUT = ROOT / 'artifacts/phase1-low-ic-joint-v1-companion-free.json'
E, R = 'complete_w117_estecker', 'complete_w117_rngonly'
CELLS = {0: 'clean', 1: 'indel'}


def companion_free(arm: dict) -> bool:
    return bool(arm['detected'] and arm['retained'])


def rate(hits: int, draws: int) -> dict:
    return {'count': hits, 'draws': draws, 'rate': hits / draws, 'interval_95': wilson_interval(hits, draws)}


def summarise(rows: list, ceiling: float) -> dict:
    cells = {}
    for index, name in CELLS.items():
        mine = [r for r in rows if r['cell'] == index]
        if not mine:
            continue
        arms = {}
        for arm in (E, R):
            free = sum(companion_free(r['arms'][arm]) for r in mine)
            confirmed = sum(bool(r['arms'][arm]['sweep_success']) for r in mine)
            stands = sum(bool(r['arms'][arm]['plugboard_exact'] and r['arms'][arm]['score_per_letter'] > ceiling)
                         for r in mine)
            arms[arm] = {
                'companion_free_success': rate(free, len(mine)),
                'stands_out': rate(stands, len(mine)),
                'sweep_success_preregistered': rate(confirmed, len(mine)),
            }
        # Paired over the same draws: discordant counts show where the arms differ.
        r_only = sum(companion_free(r['arms'][R]) and not companion_free(r['arms'][E]) for r in mine)
        e_only = sum(companion_free(r['arms'][E]) and not companion_free(r['arms'][R]) for r in mine)
        cells[name] = {
            'draws': len(mine),
            'arms': arms,
            'companion_free_gain': arms[R]['companion_free_success']['rate'] - arms[E]['companion_free_success']['rate'],
            'discordant': {'rngonly_only': r_only, 'estecker_only': e_only},
        }
    return cells


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    # check_artifacts.py regenerates into a temporary path with --output.
    parser.add_argument('--output', type=pathlib.Path, default=OUTPUT)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    output = parse_arguments(argv).output
    code = code_version()
    joint = json.loads(JOINT.read_text(encoding='utf-8'))
    v7 = json.loads(V7.read_text(encoding='utf-8'))['result']
    dist = v7['score_distribution_over_slice']
    mean, sd = dist['mean_score_per_letter'], dist['sd_score_per_letter']
    ceiling = mean + BAND_CEILING_Z * sd
    cells = summarise(joint['draws'], ceiling)
    v7_reading = {
        'band_ceiling_z': BAND_CEILING_Z,
        'band_ceiling_score_per_letter': ceiling,
        'top_z': dist['top_z_score'],
        'retained_above_ceiling': sum(1 for t in v7['top_candidates'] if t['score_per_letter'] > ceiling),
        'companion_confirmed': v7['companion_confirmation'].get('confirmed_candidate_ranks', []),
    }
    v7_reading['null_holds_companion_free'] = v7_reading['retained_above_ceiling'] == 0
    payload = {
        'schema': 'enigma-attack.phase1-low-ic-joint-companion-free/v1',
        'experiment_id': 'phase1-low-ic-joint-v1',
        'analysis': 'post_hoc_companion_free',
        'definition': 'detected AND retained, per draw and arm; companion confirmation not required',
        'code': code,
        'inputs': {'joint_artifact_sha256': sha256_file(JOINT), 'v7_artifact_sha256': sha256_file(V7)},
        'cells': cells,
        'v7_companion_free': v7_reading,
        'preregistered_decision_unchanged': {'hypothesis_passed': joint['hypothesis_passed'],
                                             'paired_gain': joint['paired_gain']},
    }
    output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({n: {'gain': c['companion_free_gain'],
                          'E': c['arms'][E]['companion_free_success']['count'],
                          'R': c['arms'][R]['companion_free_success']['count'],
                          'stands_out': {a: c['arms'][a]['stands_out']['count'] for a in (E, R)},
                          'discordant': c['discordant']} for n, c in cells.items()} | {'v7': v7_reading}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
