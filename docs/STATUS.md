# Project status

Updated: 2026-09-22

## Current state

The nine confirmed findings in the [repository audit](code-review-2026-09-22.md)
have engineering fixes in the `codex/fix-nine-audit-findings` branch. The
[attack plan](ATTACK_PLAN.md) still describes the broader research program.
Historical Phase 3–7 artifacts and v1 configurations remain available; corrected
runs use new v2 identifiers and artifacts. No challenge plaintext has been
accepted.

The full-text published n-gram objective recovers the original 148-character
4×5 control exactly, including its key (rank 1 of 2,880). A legacy-objective
diagnostic reproduces the earlier prefix result: the known key ranks fifth,
and the selected plaintext has a 144-character matching segment displaced by
four positions. The independent solved-message 5×7 control fails under the
deployed annealing budget: its best
candidate has 5.3% positional accuracy with the published scorer. The shared
control gate therefore skips the QTXMA target and the complete-search null
calibration in the v2 Phase 7 run. This is an optimizer/control failure, not a
claim that the target or cipher family is excluded.

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

## Validation

- `python3 -m unittest discover -q`: 59 tests passed.
- `python3 -m pip wheel . --no-deps --no-build-isolation`: wheel built.
- Clean virtual environment outside the checkout loaded all five corpus
  messages and the published scorer; Phase 2 and Phase 7 commands launched.
- Corrected bounded artifacts: `artifacts/phase3-variant-smoke-v2.json`,
  `artifacts/phase4-joint-machine-smoke.v2.json`,
  `artifacts/phase6-qtxma-double-transposition-smoke.v2.json`, and
  `artifacts/phase7-qtxma-source-and-scorer.v2.json`.

## Next

Validate annealing on several independent known-key messages at the target
lengths and width branches, including ragged rows, before any QTXMA target run.
When those controls pass, run the configured complete-search null calibration
and inspect exact round-trip candidates. Confirm the source status of the
remaining messages before making present-day unresolved-set claims.
