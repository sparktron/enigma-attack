# Project status

Updated: 2026-09-22

## Current state

Phases 1-6 provide bounded, reproducible baselines and negative-result
evidence. Phase 7 recovered the QTXMA source grouping and introduced a
published 1941 Army n-gram scorer. The source grouping yields exactly the
existing 155-letter ciphertext. The scorer passed five solved-plaintext
discrimination checks but failed the known double-transposition recovery
control, so the Phase 7 runner stopped before searching QTXMA.

No ciphertext break has been accepted. See
[Phase 7 history](phase7-experiment-history.md) and its linked raw artifact.

## Active work and known problems

- The current Army n-gram scorer does not recover the preregistered known
  transposition control, despite increasing its held-out score. It is not
  validated for another QTXMA transposition search.
- Original form grouping adds no new body boundary. QTXMA's present status in
  the source's unbroken list remains unresolved.
- The messages used to compile the published n-gram counts are not enumerated,
  so overlap with the solved-message validation set cannot be ruled out.

## Validation state

- `python3 -m unittest discover -q`: 48 tests passed locally on 2026-09-22.
- `git diff --check`: passed locally on 2026-09-22.
- Phase 7 original-form, scorer, and positive-control observations are recorded
  in `artifacts/phase7-qtxma-source-and-scorer.json`.
- CI on a clean checkout has not been checked for the Phase 7 changes.

## Next

Collect an independently sourced Army plaintext set with documented separation
from scorer training data. Validate a stronger scorer on several known
transposition keys and a substitution control. Preregister a new bounded
QTXMA run only if those controls pass. Archival evidence about the procedure
or message status could redirect the analysis sooner.
