# Review measurement scripts

Exploratory measurements behind
[docs/code-review-2026-10-02.md](../../docs/code-review-2026-10-02.md). They are
**not preregistered experiments**. They write no artifacts under `artifacts/`,
are not packaged in the wheel, and are not run by CI. Any result used to change
the plan should be rerun as a proper experiment with its own config and
artifact.

Both scripts import the checkout's modules and read
`experiments/phase1-stecker-calibration-v1/config.json`. They can be run from
any directory.

## `reachable_settings.py` (review P1 and P2)

Measures whether a sweep that holds some ring settings fixed can reach a
setting equivalent to a random true daily key, and whether the stecker climb
recovers the plugboard there.

```bash
python3 scripts/review/reachable_settings.py --mode exact --draws 32
python3 scripts/review/reachable_settings.py --mode rings-aaa --draws 32
python3 scripts/review/reachable_settings.py --mode reducible --draws 48
python3 scripts/review/reachable_settings.py --mode per-offset-middle --draws 48
```

The modes are `exact` (the true key, which is what the calibration measures),
`rings-aaa` (all rings held at A), `reducible` (left and middle rings held at
A, the artifact's 60 × 26⁴ space), and `per-offset-middle` (the same size, but
the middle ring is chosen so the swept middle wheel cannot step the left wheel).
Add `--length`, `--pairs`, `--jobs` or `--output file.json` as needed.

## `batched_climb.py` (review R1, requires numpy)

A numpy reimplementation of the two-phase body-direct stecker climb. It is
benchmarked against `stecker_climb.body_direct_climb` on true and wrong
settings, and it requires identical final plugboards: it exits non-zero on any
divergence.

```bash
python3 scripts/review/batched_climb.py --cases 40
```

## Review of 2026-10-11

Behind [docs/code-review-2026-10-11.md](../../docs/code-review-2026-10-11.md).
The same rules apply: exploratory, no artifacts, not packaged, not in CI.
`independent_enigma.py` needs only the standard library; the other two use the
experiment configs under `experiments/phase1-end-to-end-power-v1/` (and, for
`--base-config`, `phase1-fault-power-v1/`).

### `independent_enigma.py` (review V-1, V-2)

An Enigma I written from the published description, sharing no code with the
repository's simulators. It compares itself with `enigma.EnigmaMachine`,
`enigma_fast.crypt_indices` and the table path on published vectors, the
double-step sequence and 3,000 random keys, then checks
`stecker_space.rule_key_coverage` against an empirical count. It exits non-zero
on any disagreement.

```bash
python3 scripts/review/independent_enigma.py
```

### `plaintext_power.py` (review B-1)

Runs the repository's own `end_to_end_power` harness on several plaintexts
(the repository's, plus Markov samples of the published trigram counts) with the
same planted keys, and reports detection against each plaintext's index of
coincidence. About 30 seconds per text for the whole-message arm.

```bash
python3 scripts/review/plaintext_power.py --texts 16 --draws 60
python3 scripts/review/plaintext_power.py --base-config experiments/phase1-fault-power-v1/config.json \
    --arm split_complete --texts 4 --draws 40 --jobs 1   # the v5 climb; needs the CUDA build
```

### `estecker_direct.py` (review S-1)

Climbs planted keys at the true setting from the empty plugboard and from the
first-plug start sets of Ostwald and Weierud's partial exhaustion (E-, R- and
I-Stecker), each calibrated against its own wrong-setting null. It patches
`stecker_climb.run_climb_phases` in its own process only.

```bash
python3 scripts/review/estecker_direct.py --text markov-0 --draws 36 --methods base,E
```
