# Run: complete pending changes and open a PR

**Started:** 2026-10-24 · **Repo:** `enigma-attack`
**Branch:** `codex/complete-transposition-controls` · **Status:** open
**PR base:** `8cf6e5e` (current `origin/master`)
**Tool / model:** Codex / GPT-6
**Skills loaded:** hub-repo-audit, session-closeout

## Goal

Finish and validate the incoming unstaged changes, commit them on a new branch,
and open a PR against current master. Preserve historical experiment evidence.

## Orientation

The initial checkout was `master` at `9a1dd88`, 157 commits behind origin/master,
with 13 modified tracked files and five untracked files; no unpushed commits.
No local AGENTS.md, CLAUDE.md, ARCHITECTURE.md, or NOW.md exists. User-supplied
instructions route to ai-hub/AGENTS.md. No enigma-attack registry entry exists.
The simulator, phase runners, resources and provenance modules, experiments,
artifacts, tests and CI supply the architecture. No cross-repo contracts change.

Invariants: gate target searches on all mandatory controls, preserve unknown
positions and historical evidence, use full precision for scientific decisions,
and record installed source provenance independently from resource paths.
Relevant tests are tests/test_phase6.py, tests/test_phase7.py,
tests/test_transposition_control.py and tests/test_wheel_install.py. CI gates
unit tests on Python 3.10–3.13 and artifact drift/determinism on Python 3.10.

## Plan

- [x] Review the incoming diff and obtain an independent read-only review.
- [x] Preserve incoming work, integrate with current master, resolve overlap.
- [x] Finish precision and historical-evidence integration repairs.
- [ ] Run unit/wheel tests and artifact drift/determinism checks.
- [ ] Review the final diff, commit, push and create/attach the PR.

## Decisions

- Keep an incoming-work stash as recovery evidence; apply it to a new branch
  from current master instead of publishing a branch 157 commits behind.
- Keep upstream's shared provenance and installed Phase 1/2 regression tests;
  they supersede the incoming per-module hashing edits and duplicate tests.
- Preserve the withdrawn October exhaustive Phase 7 v3 config at its existing
  path. Archive the distinct September rotation-control config unchanged at
  experiments/phase7-qtxma-source-and-scorer-rotation-v3/config.json. Both reused
  the same experiment identifier. Preserve both raw artifacts byte for byte,
  document the collision, and mark them superseded by the conservation gate.
- Keep raw values through Phase 6 null calibration and Phase 7 scorer-validation
  comparisons; round output only. A failing regression reproduced the second
  mixed-precision bug before it was fixed.
- Leave the separately documented Phase 4 nondefault-machine baseline defect
  (October 1 F3) open; it is outside the incoming changes. No unrelated refactor
  or new cipher model is included.

## Assumptions and limits

- Historical artifacts record dirty September code and have not been regenerated
  with the conservation gate bypassed. Their original provenance is retained.
- Exact rotation enumeration is suitable for the present small control widths;
  its factorial cost needs a bounded alternative before expanding those widths.
- Python 3.12 is available locally; the other CI versions have not been run yet.

## Delegation

- review_pending — independent read-only review of incoming changes and upstream
  compatibility. Found Phase 7's mixed-precision scorer validation, obsolete
  installed-provenance assertions and stale documentation. Verified historical
  config hashes and checked rotation enumeration against brute force in 21 small
  cases. A second review of the integrated diff found no correctness or packaging
  blockers. Main thread made every edit. Token and elapsed costs: unknown.

## Verification

- Incoming-tree targeted unit/wheel suite: 34 tests passed on Python 3.12.3.
- New Phase 7 precision regression: failed in three subcases before the fix.
- After integration and precision fix: `python3 -m unittest tests.test_phase6
  tests.test_phase7 tests.test_transposition_control tests.test_wheel_install -q`
  → 41 tests passed (6.226 s).
- Static evidence checks: both raw v3 artifacts are byte-identical to the
  incoming stash; archived config SHA-256 values and payloads match each artifact.
  The upstream withdrawn config is byte-identical to HEAD. All referenced local
  Markdown targets and all setuptools data-file paths exist.
- `python3 -m unittest discover -q > /tmp/enigma-pr-unit-tests.log 2>&1`
  → passed, 371 tests, 16 skips (117.959 s), Python 3.12.3 / numpy 1.26.4.
- `python3 check_artifacts.py both > /tmp/enigma-pr-artifacts.log 2>&1`
  → running; drift found 10 Phase 5 floating-point differences on Python 3.12.
  An isolated export of unchanged upstream `8cf6e5e` reproduced exactly the
  same 10 differences, and baseline versus PR regeneration agrees on every
  declared Phase 5 claim. These are preexisting; do not rewrite the artifact
  generated for CI's pinned Python 3.10.
- `python3 /tmp/enigma-pr-upstream-baseline/phase5.py --output
  /tmp/enigma-pr-upstream-baseline/phase5-regenerated.json` → completed.
  `check_artifacts.compare` confirmed the baseline differences above.
- `git diff --cached --check` → passed after staging merge resolutions.

## Cost

- measured-by: unknown
- main-tokens: unknown
- helper-tokens: unknown
- wall-clock-min: unknown

## Next

Finish local determinism and the PR CI checks; record the final results.

## Closed

Pending.
