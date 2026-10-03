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
benchmarked against `phase1_stecker.body_direct_climb` on true and wrong
settings, and it requires identical final plugboards: it exits non-zero on any
divergence.

```bash
python3 scripts/review/batched_climb.py --cases 40
```
