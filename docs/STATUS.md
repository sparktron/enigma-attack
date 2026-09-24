# Project status

Updated: 2026-09-23

## Current state

The nine confirmed findings in the [repository audit](code-review-2026-09-22.md)
have engineering fixes on `master`. The [attack plan](ATTACK_PLAN.md) still
describes the broader research program. Historical Phase 3–7 artifacts and v1
configurations remain available; corrected runs use new v2 identifiers and
artifacts. No challenge plaintext has been accepted.

Phase 7 recovered the QTXMA source grouping and introduced a published 1941
Army n-gram scorer; the source grouping yields exactly the existing 155-letter
ciphertext. The Phase 7 v1 positive-control failure had two independent causes,
and both are now fixed. Selecting keys on a training prefix ranked the true key
fifth of 2,880; the full-text objective ranks it first, recovering the
148-character 4×5 control and its key exactly. The v1 recovery was also the
control plaintext rotated by four characters — 97.3% agreement at that offset,
reported as 6.1% by a strict positional metric — because that control is an
exact multiple of its 4-wide first stage. Recovery is now measured only over
the whole-row rotations the stage geometry can produce, with the exact-offset
agreement and exact key recovery recorded beside it.

A third control was added whose 133-letter plaintext is a multiple of neither
stage width, so no rotation is available to it. It recovers its plaintext and
both stage keys exactly, which shows the scorer and optimizer work at that
length. The independent solved-message 5×7 control still fails, at 5.3%
positional agreement, so the shared control gate skips the QTXMA target and the
complete-search null calibration in the v2 Phase 7 run. That failure is a
whole-message rotation rather than a scrambled miss: the recovery agrees with
the known plaintext completely at an offset of 75 of its 76 positions, which
neither stage width can produce. This is an open question about the ragged-row
convention at that length, not a claim that the target or cipher family is
excluded.

## Correctness and evidence repairs

- Swiss K left-wheel double stepping now advances at either the middle or left
  notch; reflector movement still follows the left notch. The Phase 3 variant
  screen was reissued as `artifacts/phase3-variant-smoke-v2.json`.
- Phase 4 selects each daily-key baseline using training messages only. The v2
  experiment records the selected designators and leaves the Phase 3 artifact
  as a historical, selection-contaminated reference. Its median held-out score
  delta is -0.106713 under the bounded run.
- Phase 7 forwards its audited corpus to Phase 6. Phase 6 rejects a Phase 5
  artifact whose recorded corpus hash does not match that search input.
- Reconnaissance preserves unknown positions for repeated n-grams and lag
  matching. Zero-capacity plugboard mutation is safe and optimizer bounds are
  validated.
- The wheel includes Phase 7, Phase 2 and 7 commands, and required corpus,
  catalog, configuration, artifact, and n-gram resources. Installed commands
  write default outputs under the current working directory.
- Phase 6 selects on the full plaintext, reports top candidates, exact
  recovery, key rank, edit distance, and boundary displacement on its
  exhaustive control, and treats the candidate suffix as descriptive. The
  target acceptance rule uses matched complete-search shuffle nulls when the
  controls pass. A failed mandatory control makes zero target-search calls.
- Known-key control recovery is credited only over the whole-row rotations a
  stage width that divides the message length can produce. The exact-offset
  agreement, the exact key match, and the best agreement over every rotation
  are all recorded, so a near-match that the geometry cannot explain stays
  visible without being able to pass a control.
- Every configured known-key control is evaluated even after one fails, because
  a control whose geometry admits no rotation is what separates a genuine
  search failure from a metric artifact.
- The published-count scorer is validated for recovering known double
  transpositions; the earlier claim that it could not is withdrawn.
- Original form grouping adds no new body boundary. QTXMA's present status in
  the source's unbroken list remains unresolved.
- The messages used to compile the published n-gram counts are not enumerated,
  so overlap with the solved-message validation set cannot be ruled out.
- The known-key controls are constructed or independently solved plaintexts,
  not authentic held-out Army traffic.

## Validation

- `python3 -m unittest discover -q`: 77 tests passed locally on 2026-09-23.
- `python3 -m pip wheel . --no-deps --no-build-isolation`: wheel built.
- Clean virtual environment outside the checkout loaded all five corpus
  messages and the published scorer; Phase 2 and Phase 7 commands launched.
- Corrected bounded artifacts: `artifacts/phase3-variant-smoke-v2.json`,
  `artifacts/phase4-joint-machine-smoke.v2.json`,
  `artifacts/phase6-qtxma-double-transposition-smoke.v2.json`, and
  `artifacts/phase7-qtxma-source-and-scorer.v2.json`.
- The v1 artifacts are retained as historical records; their positive-control
  verdicts and held-out readings are superseded.
- CI runs the unit tests on Python 3.10 through 3.13, then two checks over the
  generated artifacts. Drift regenerates each artifact and fails the build when
  a value declared in `artifact_claims.json` changes, reporting an added or
  removed key as a warning instead. Determinism runs each experiment twice in
  one environment and requires the declared paths to agree.
- All seven declared artifacts currently pass both checks.

## Next

Resolve the 5×7 control failure before any QTXMA target run. Its recovery is
the known plaintext rotated by one position over 76 letters, which no stage
width there can produce, so the ragged-row filling convention for that message
is the first thing to check. Then validate the search on several further
independent known-key messages at the target lengths and width branches,
including ragged rows, run the configured complete-search null calibration, and
inspect exact round-trip candidates. Do not enlarge the transposition width
search from training gains. Confirm the source status of the remaining messages
before making present-day unresolved-set claims.
