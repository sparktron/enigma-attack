# Project status

Updated: 2026-09-23

## Current state

Phases 1-6 provide bounded, reproducible baselines and negative-result
evidence. Phase 7 recovered the QTXMA source grouping and introduced a
published 1941 Army n-gram scorer. The source grouping yields exactly the
existing 155-letter ciphertext.

The Phase 7 v1 positive-control failure was a measurement artifact. Its
recovered plaintext was the control plaintext rotated by four characters —
97.3% agreement at that offset, reported as 6.1% by a strict positional
metric — because the 148-letter control is an exact multiple of its 4-wide
first stage. Phase 7 v2 measures recovery over cyclic rotations and adds a
133-letter control that is a multiple of neither stage width. Both controls
pass, and the second recovers its plaintext and both stage keys exactly.

With the gate open, the bounded QTXMA transposition search ran and was
refuted: all three seeds gained about +0.63 score per letter on the training
prefix and lost about -0.76 on the untouched suffix, below the +0.038 scored
by the monoalphabetic substitution control.

No ciphertext break has been accepted. See
[Phase 7 history](phase7-experiment-history.md) and its linked raw artifacts.

## Active work and known problems

- The published-count scorer is validated for recovering known double
  transpositions; the earlier claim that it could not is withdrawn.
- Bounded double transposition over the preregistered widths is now refuted
  for QTXMA under this scorer. Other widths, ragged-row conventions, nulls,
  and non-literal bodies are untested.
- Original form grouping adds no new body boundary. QTXMA's present status in
  the source's unbroken list remains unresolved.
- The messages used to compile the published n-gram counts are not enumerated,
  so overlap with the solved-message validation set cannot be ruled out.
- Both positive controls are constructed plaintexts, not authentic held-out
  Army traffic.

## Validation state

- `python3 -m unittest discover -q`: 53 tests passed locally on 2026-09-23.
- Phase 7 v2 source, scorer, control, and target observations are recorded in
  `artifacts/phase7-qtxma-source-and-scorer-v2.json`.
- `artifacts/phase7-qtxma-source-and-scorer.json` is retained as the v1 record;
  its positive-control verdict is superseded.
- The Phase 7 v2 artifact was produced from a clean checkout at commit
  `3b384f1`, and the run reproduced bit-for-bit across three executions. Full
  CI on a fresh clone has still not been exercised.

## Next

Do not enlarge the transposition width search from training gains. The two
higher-value moves are archival evidence about the procedure or QTXMA's
message status, and an independently sourced Army plaintext set with
documented separation from the scorer's training data, which would let the
target and the substitution control be compared on authentic held-out text.
