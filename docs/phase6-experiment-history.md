# Phase 6 frequency-preserving experiment history

## phase6-qtxma-double-transposition-smoke-v1

Status: completed 2026-09-21; hypothesis not supported under the
preregistered bounded smoke metric

Hypothesis: QTXMA is compatible with a bounded double-columnar-transposition
model that generalizes from a training prefix to an unscored held-out suffix.
At least two of three fixed seeds must improve held-out adjacency score by
0.005 per letter, the median improvement must reach 0.01, and that median must
exceed the monoalphabetic-substitution control by 0.005. The true-transposition
positive control must first recover at least 95% of its plaintext and improve
its held-out score by at least 0.01 per letter.

Refuted by: failure of the positive control, fewer than two target seeds
reaching the per-seed threshold, a target median below 0.01, or a margin over
the substitution control below 0.005.

Exact configuration:
[experiments/phase6-qtxma-double-transposition-smoke-v1/config.json](../experiments/phase6-qtxma-double-transposition-smoke-v1/config.json)

Target: QTXMA, selected before the run because Phase 5 routed it to the
frequency-preserving/manual branch. The other four messages were not searched.
After the Phase 5 structural-null correction, the route remained unchanged:
QTXMA retains the frequency-preserving signal, while the lag, candidate-period,
and repeated-block signals are false. The experiment was rerun unchanged so its
recorded Phase 5 hash and signals match the corrected evidence.

Training boundary: the first 116 characters (75%) of each candidate plaintext.
The final 39 characters were never passed to the optimizer's scorer. Because a
transposition key acts on the complete message, the full candidate was
constructed during search, but its suffix score was computed only after key
selection.

Search: double columnar transposition with incomplete final rows. Width pairs
5x5, 5x7, 7x5, and 7x7 were searched with eight deterministic annealing
restarts and 1,500 iterations per restart for each of three seeds. The scorer
uses only length-two-or-longer n-grams from the Phase 1 bootstrap model;
monogram terms are excluded because transposition preserves letter counts.

Controls:

- The positive control was a known German-like plaintext enciphered with
  preregistered 4- and 5-column permutations. Exhaustive search over all 2,880
  key pairs recovered the exact plaintext and exact keys. Plaintext accuracy
  was 1.0 and held-out score improved by +0.198648649 per letter.
- The monoalphabetic-substitution control used the same source plaintext and a
  preregistered substitution alphabet. Exhaustive transposition search raised
  its visible training score by +0.034234235 per letter but changed its
  held-out score by 0.0. This demonstrates the intended overfitting control.

Raw result:
[artifacts/phase6-qtxma-double-transposition-smoke.json](../artifacts/phase6-qtxma-double-transposition-smoke.json).

Code: clean commit `0fa08da90533439968a9b3e204a6c6eda435aca5`. Runner SHA-256:
`82732006720c5600def5fa15575b434f2de9aaa18f5349685374f4a4d9d5e315`.
The corrected Phase 5 artifact SHA-256 is
`e308558cac92cae5060046479a1d4406489e09f111104c382dfc40914e56c701`.

Environment: Python 3.10.12, Linux 6.8.0-138-generic x86_64, 20 logical
CPUs reported, one serial worker. Rerun runtime: 51.870312 seconds.

Observed:

- Training-score improvements were +0.037068965, +0.036637931, and
  +0.037068965 per letter.
- Held-out changes were -0.026923077, -0.026923077, and -0.017948718.
- Zero of three seeds reached the preregistered +0.005 held-out threshold.
- Median held-out change: -0.026923077.
- Substitution-control held-out change: 0.0.
- Median margin over the substitution control: -0.026923077.
- The three candidate plaintexts are incoherent and the selected keys do not
  converge.

Interpretation (inference): the implementation can recover a known
double-transposition control, but the bounded QTXMA search only increased the
score it was allowed to see. Its failure on the untouched suffix, nonconvergent
keys, and negative margin over the substitution control are consistent with
training-score overfit, not with a double-transposition plaintext.

Boundary: this result does not exclude double transposition in general. It does
not test every width, disrupted rectangles, route transposition, nulls, original
five-letter grouping, or stronger language models.

Next decision: do not enlarge this search solely because its training score
rose. First recover the original form grouping/typography or introduce a
versioned, independently validated Army-traffic n-gram model; then preregister
any wider width or procedure search.
