# Phase 4 joint-machine experiment history

## phase4-joint-machine-smoke-v1

Status: completed 2026-09-21; hypothesis refuted under the preregistered metric

Hypothesis: A shared nonstandard three-rotor machine plus date-specific daily
keys can generalize beyond the optimized messages. At least three of five fixed
seeds must improve held-out score per known letter by at least 0.02 over the
frozen standard-machine baseline, and the median held-out improvement must be
at least 0.02.

Refuted by: fewer than three seeds reach the per-seed threshold, or the median
held-out improvement is below 0.02.

Exact configuration:
[experiments/phase4-joint-machine-smoke-v1/config.json](../experiments/phase4-joint-machine-smoke-v1/config.json)

Training messages: QTXMA, BYQMZ, FKQLZ.

Held-out messages, never consulted by the optimizer: SZAEJ, XFEDT.

Baseline: standard rotors III-II-V, standard UKW B, rings AAA, empty plugboard,
and the corpus clear-Grundstellung/encrypted-message-key procedure on both
dates. These settings are frozen before the run and match the top UKW-B smoke
candidate recorded in the Phase 3 artifact.

Seeds: 104729, 130363, 155921, 196613, 2147483647.

Raw result:
[artifacts/phase4-joint-machine-smoke.json](../artifacts/phase4-joint-machine-smoke.json).

Code: commit `301a2aa` on branch `master`, dirty tree with 15 status
entries. Runner SHA-256:
`e5b68b4b4600669ea9358de140668bdb7c7157f0c92a6070c0c4eb2d9c12ec84`.

Environment: Python 3.10.12, Linux 6.8.0-138-generic x86_64, 20 logical
CPUs reported, one serial worker. Each seed used one local
`random.Random` instance.

Observed:

- Baseline training score per known letter: -3.585149878.
- Baseline held-out score per known letter: -3.699445134.
- Training improvements by seed ranged from +0.191348521 to +0.219991007.
- Held-out changes by seed were +0.004766989, +0.001971538, -0.273625333,
  -0.169031009, and -0.106712593.
- Zero of five seeds reached the preregistered +0.02 held-out threshold.
- Median held-out change: -0.106712593.
- The best states changed 48-57 of 78 rotor-wiring positions, 20-26 reflector
  positions, two or three notches, and four to eight date-specific plugboard
  pairs.
- Runtime: 16.099664 seconds. Full traces, mutation counts, best-state
  histories, states, and plaintexts are preserved in the raw artifact.

Interpretation (inference): the optimizer consistently raised the score it was
allowed to see while failing on unseen messages. Together with the large
machine changes and incoherent held-out plaintext, this is consistent with
language-scorer overfitting or a false assumption that all five messages share
this machine family. It is not evidence for an alternate wiring.

Baseline comparison: the frozen baseline used the same UKW-B III-II-V / AAA /
empty-plugboard settings recorded as the top UKW-B smoke candidate in Phase 3.
Phase 4 therefore compares against the same configuration under its
preregistered train/held-out split rather than against an unrelated score.

Next decision: do not expand blind arbitrary-wiring optimization from this
result. First test evidence-backed corpus partitions, or replace the bootstrap
scorer with a versioned Army-traffic model and repeat the same held-out design.
