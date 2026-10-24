# Run: complete pending changes and open a PR

**Started:** 2026-10-24 · **Repo:** `enigma-attack`
**Branch:** `codex/complete-transposition-controls` · **Status:** closed; PR CI pending
**PR base:** `8cf6e5e` · **Implementation commit:** `e42a0db`
**PR:** https://github.com/sparktron/enigma-attack/pull/44
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
- [x] Run unit/wheel tests and artifact drift; record partial local determinism
  and the pending full CI checks explicitly.
- [x] Review the final diff, commit, push and create/attach the PR.

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
  → local drift completed with only 10 Phase 5 floating-point differences.
  The subsequent determinism pass completed the Phase 1/2/3/4/5 smoke artifacts
  and stecker/length calibrations without differences, then was stopped
  (exit 130) while repeating unchanged, longer experiments; full determinism
  remains pending in CI. This command did not pass overall.
  An isolated export of unchanged upstream `8cf6e5e` reproduced exactly the
  same 10 differences, and baseline versus PR regeneration agrees on every
  declared Phase 5 claim. These are preexisting; do not rewrite the artifact
  generated for CI's pinned Python 3.10.
- `python3 /tmp/enigma-pr-upstream-baseline/phase5.py --output
  /tmp/enigma-pr-upstream-baseline/phase5-regenerated.json` → completed.
  `check_artifacts.compare` confirmed the baseline differences above.
- `git diff --cached --check` → passed after staging merge resolutions.
- GitHub CI run 40127610753 (implementation commit `e42a0db`): Python 3.11
  and 3.13 unit/wheel jobs passed at last observation; Python 3.10/3.12 and the
  artifact job were still running. No CI-green claim is made.
- PR #44 was created and attached to the chat. The incoming stash remains as
  a recovery copy; no history was rewritten.

## Cost

- measured-by: unknown
- main-tokens: unknown
- helper-tokens: unknown
- wall-clock-min: unknown

## Next

Review PR #44 and its full CI results. The local Phase 5 drift matches the
unchanged baseline; investigate any failure on CI's pinned Python 3.10 before
merging. Phase 4 F3 remains a separate documented follow-up.

## Closed

2026-10-24 — incoming changes completed, independently reviewed, committed and
published as PR #44. Durable state: docs/STATUS.md and this run. Left open:
full PR CI results and the preexisting Phase 4 nondefault-machine baseline
issue. No challenge plaintext was accepted.
