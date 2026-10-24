# Code review and repair plan — 2026-10-01

**Started:** 2026-10-01 · **Repo:** `enigma-attack` · **Branch:** `master`
**Reviewed revision:** `2f50e9a450187422609b546f75dc6acdfe527362` plus the existing uncommitted Phase 6/7 v3 changes.
**Tool / model:** Codex / GPT-6
**Skills:** hub-repo-audit, session-closeout
**Status:** review complete; fixes proposed, not implemented.

## Goal and scope

Review the current code for bugs and errors, suggest justified refactors, and
order the repairs. Read the simulator, phase runners, resource resolver,
artifact checker, packaging/CI configuration, existing audit and representative
tests. Used indexed symbol outlines for navigation and live source reads to
include the uncommitted changes; the index does not contain all v3 files.

Repository orientation: 11 tracked files were modified before this review,
with four additional untracked artifact/configuration paths. There are zero
unpushed commits relative to the configured upstream. No local `AGENTS.md`,
`CLAUDE.md`, or `docs/ARCHITECTURE.md` exists; the supplied instruction routes
to `ai-hub/AGENTS.md`. `docs/STATUS.md` and the prior audit supply architecture
and state. No cross-repository interface changes are proposed. A literal
`enigma-attack` lookup found no matching entry in the hub project registry.

Invariants: preserve uncertain character positions, validate cipher
permutations and reciprocity, select baselines from training messages only,
block target searches after failed mandatory controls, and retain evidence
for historical experiments. No implementation, configuration, or artifact was
changed by this review. Existing edits belong to the incoming working tree.

## Confirmed findings

### F1 — P1: Rounding can turn tied scores into a significant result

**Locations:** `phase6.py:909`, `phase6.py:485`, `_rounded_score`.

`run_experiment` obtains its observed maximum from the serialized candidate
report, whose scores have already been rounded to nine decimals. Null maxima
retain full precision. The empirical upper-tail comparison therefore compares
different representations of the same statistic.

**Reproduced:** An order-independent scorer returning
`(len(text) * 1.0000000006, len(text))`, a passing all-A control, exhaustive
2×2 widths, one seed and 19 null replicates produce:

```text
observed = 1.000000001
every null maximum = 1.0000000006
empirical_p_value = 0.05
status = signal_under_search_calibrated_null
hypothesis_supported = True
```

Every candidate actually ties. The correct empirical p-value is 1.0. This is
a numerical correctness defect, not evidence that the recorded QTXMA result
has changed; the checked-in v3 result remains negative.

**Repair:** Retain raw selected scores for all comparisons and acceptance
decisions. Round only output intended for display. Test ties that round both
up and down, including negative log scores, and a genuine unequal-score case.

### F2 — P1: Installed Phase 1 search and Phase 2 crash

**Locations:** `phase1.py:477`, `phase2.py:394`, `resources.py:9`,
`tests/test_wheel_install.py:14`.

`ROOT` now points to installed research data, but Phase 1 still hashes
`ROOT / "enigma.py"` and `ROOT / "phase1.py"`; Phase 2 hashes
`ROOT / "phase2.py"`. The wheel installs Python modules into site-packages
and research inputs into `share/enigma-attack`. The latter has no source files.

**Reproduced:** Built the current wheel with
`python3 -m pip wheel . --no-deps --no-build-isolation`, installed it with
`--no-deps` in a disposable virtual environment, removed `PYTHONPATH`, and ran
these commands from outside the checkout:

```text
enigma-phase1 search --rotor-order I-II-III --message QTXMA --output /tmp/.../p1.json
  exit 1: FileNotFoundError: .../share/enigma-attack/enigma.py
enigma-phase2 --output /tmp/.../p2.json
  exit 1: FileNotFoundError: .../share/enigma-attack/phase2.py
```

The current wheel test exercises Phase 7 and misses these entry points.

**Repair:** Hash source using the owning module's `__file__`; reserve the
resource resolver for data. Extend the existing isolated wheel test with a
one-key Phase 1 search and an actual Phase 2 artifact build. Checking `--help`
or Phase 1 `validate` alone does not exercise this failure.

### F3 — P2: Phase 4 selects a baseline for a different machine

**Location:** `phase4.py:604–625`, `_training_only_baseline`.

The initial machine accepts reflector, entry wheel and stepping settings, but
baseline selection always uses the `wehrmacht_ukw_b` profile and changes only
its rotor pool. The selected key is then installed in the configured machine.
Changing the reflector to supported value C consequently selects and reports
a baseline using B, then optimizes and evaluates C.

**Reproduced:** Starting with the default Phase 4 config and changing only
`initial_machine.reflector` to `C`, enumerating the same six rotor orders on
the actual configured machine yields:

| Training date | Recorded selection score | Actual selected-key score | Best actual score |
|---|---:|---:|---:|
| 1941-09-29 | -3.554773132 | -3.780182414 | -3.691745788 |
| 1941-09-30 | -3.602396748 | -3.907419197 | -3.715465923 |

On September 29 the recorded order is III-II-V; the actual C-machine optimum
is V-III-II. On September 30 the C-machine optimum is II-V-III. The default
B configuration is unaffected by this particular reproduction.

**Repair:** Select keys by scoring clones of the actual `MachineState`, or
construct the complete profile from that state. Assert the selected score
equals a fresh evaluation and the chosen key wins the configured training
search. Exercise C, a nonidentity entry wheel and the alternate stepping mode.

### F4 — P2: Invalid recovery thresholds disable the mandatory control gate

**Locations:** `phase6.py:739–772`, `phase6.py:623–642`.

`validate_config` never validates `minimum_positive_plaintext_accuracy`,
although `recovery_verdict` uses it to decide whether target search is allowed.

**Reproduced:** A primary control with plaintext `ABCDEFGH`, first and second
orders `[1,0]`, a constant zero scorer and 2×2 search has 0.0 recovery accuracy.
Setting `acceptance.minimum_positive_plaintext_accuracy = -1` passes config
validation, marks controls passed and runs the target search. With the default
threshold the same primary control fails.

**Repair:** Validate that recovery thresholds are finite and in their intended
range, preferably `(0, 1]` for a mandatory recovery gate. If exact recovery is
the experiment's contract, require 1.0 explicitly. Validate integer counts,
widths and budget fields as well. Test rejection before any search call.

### F5 — P2: A failed primary control suppresses the remaining diagnostics

**Locations:** `phase6.py:851–858`,
`tests/test_phase6.py:test_failed_control_makes_no_target_search_calls`.

The additional-control loop is inside `if positive_passed`. It continues
after an *additional* control fails, but never starts after a *primary*
failure. That contradicts STATUS's claim that every configured known-key
control is evaluated even after a failure.

**Reproduced:** Configure the failing `ABCDEFGH` primary described above and
an independent all-A control. The result reports only one of two configured
controls, with one search call and an empty additional-control list. The
existing test's exact one-call assertion codifies this early exit.

**Repair:** Evaluate all mandatory controls, aggregate their verdicts, then
gate substitution/target/null work. Change the test to distinguish control
calls from target calls: every control must appear, and target/null calls
must remain zero when any control fails. Phase 7 already preserves additional
diagnostics nested in the primary result; it does not need a separate fix for
that aspect.

### F6 — P2: Nonfinite scorer parameters pass validation

**Location:** `phase7.py:58–74`, `PublishedNgramScorer.__init__`.

Comparisons such as `alpha <= 0` and `weight < 0` do not reject NaN. Python's
default JSON decoder also accepts the nonstandard `NaN` token. NaN smoothing
therefore builds NaN probability tables; validation and artifact serialization
subsequently operate on invalid numbers.

**Reproduced:** Load the default scorer configuration, replace
`additive_smoothing` with `float("nan")`, construct `PublishedNgramScorer`,
and call `score("ANGRIFF")`: construction succeeds and returns `(nan, 7)`.

**Repair:** Require finite smoothing and finite nonnegative weights with a
positive finite total before loading count tables. Reject nonfinite scorer
outputs at the search boundary as well. Test NaN and both infinities; errors
should identify the invalid field before expensive work starts.

## Refactors worth doing after the correctness repairs

1. **Separate computation from artifact rendering.** Keep raw scores in
   typed result objects and serialize at the edge. F1 is caused by consuming
   rounded presentation fields as internal computation inputs.
2. **Give Phase 6/7 one effective configuration and control runner.** Use
   public interfaces for validation, search options, provenance and control
   evaluation. Phase 7 currently reaches into several Phase 6 private helpers;
   primary and additional controls also follow different reporting paths.
3. **Avoid exhaustive rotation enumeration on the acceptance path.** The
   current v3 helper enumerates each plaintext rotation and every first-stage
   permutation, with a recursive second-stage feasibility check, independent
   of `max_exhaustive_states`. This is a growth risk inferred from the loops,
   not a measured current performance defect. A selected candidate that is a
   rotation can be validated by reencryption with its own searched key.
   Keep full reachable-offset enumeration as a bounded optional diagnostic
   and preserve historical artifacts when changing their fields.
4. **Strengthen evidence checking deliberately.** `check_artifacts.py`
   intentionally treats removed declared fields as warnings during drift.
   Consider making removal of an explicit acceptance/status/control claim a
   failure while continuing to permit additive metadata. This is a proposed
   policy improvement, not a claim that current code violates its stated
   policy.
5. **Make the legacy IC utility import-safe.** `ic_null.py` seeds global RNG
   state and runs 100,000 trials per message at import time. Move execution
   behind `main`, use a local RNG and the shared data resolver if retaining
   this installed utility. Its module-relative corpus path also assumes a
   checkout. This was inspected statically, not run as another experiment.

A wholesale package rewrite is unnecessary for the six confirmed repairs.

## Ordered repair plan

Each repair should include its failing regression test and the minimum code
change needed to pass it. Keep these steps independently reviewable.

1. **Fix calibration precision (F1).** Protect raw target/null comparison and
   tie handling first because these determine the scientific conclusion.
2. **Validate configuration and scorer numbers (F4, F6).** Reject invalid
   thresholds, counts and nonfinite values before running controls or searches.
3. **Unify mandatory-control execution (F5).** Evaluate all controls, retain
   their evidence, and make one aggregate gate govern subsequent work.
4. **Repair Phase 4 baseline selection (F3).** Use the actual configured
   machine; verify reported scores and exhaustive training-only key selection.
5. **Repair installed command provenance (F2).** Correct source/data path
   separation and extend the single existing wheel-install fixture with cheap
   Phase 1/2 executions.
6. **Apply focused refactors.** Separate raw results from rendering and expose
   shared control/configuration APIs. Bound rotation diagnostics before any
   wider control search. Keep evidence-check policy changes separate.
7. **Revalidate and version affected evidence.** Run the full unit/wheel suite
   on the supported Python matrix. Run drift and determinism on CI's pinned
   Python 3.10. Reproduce affected experiments under new identifiers if outputs
   or method change; preserve earlier artifacts, update claims and histories,
   and document which conclusions actually changed. Do not infer a new QTXMA
   result from the synthetic failure reproduction.

## Reproduction recipe for F1

Run from the repository root with Python 3.12.3:

```python
import json, pathlib, tempfile
import phase6

class FlatScorer:
    def score(self, text):
        return len(text) * 1.0000000006, len(text)

config = phase6.load_config()
config["search"].update(
    target_width_pairs=[[2, 2]], control_width_pairs=[[2, 2]],
    seeds=[1], restarts=1, iterations=1, null_replicates=19,
)
config["positive_control"] = {
    "plaintext": "AAAAAAAA", "first_order": [0, 1], "second_order": [0, 1],
}
config["additional_positive_controls"] = []
with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / "config.json"
    path.write_text(json.dumps(config))
    result = phase6.run_experiment(config, path, [], FlatScorer())
print(result["status"], result["observed"]["search_calibration"])
```

## Verification and limitations

- `python3 -m unittest discover -q`: **79 tests passed**, 156.612 seconds,
  Python 3.12.3. Includes the actual installed Phase 7 run.
- A second wheel build/install in a disposable venv succeeded. Actual
  installed Phase 1 search and Phase 2 failed as recorded in F2.
- Small deterministic Python reproductions confirmed F1, F3, F4, F5 and F6.
  F3 enumerated all six allowed rotor orders on the configured C machine;
  F5 wrapped the real search only to count calls. The F1/F4/F5 scorers are
  deliberately synthetic test doubles, not language-model experiments.
- Full artifact drift/determinism and Python 3.10/3.11/3.13 validation were
  **not run** in this review. No production code changed, and current STATUS
  already records Python 3.12 floating-point drift relative to pinned 3.10.
- Historical wiring provenance, source authenticity, corpus overlap and
  external historical claims were not revalidated. No claim of a recovered
  challenge plaintext is made.
- Sandbox process startup failed with `bwrap` network-namespace errors;
  commands used approved execution outside that sandbox. Temporary wheel
  environments and reproduction configs were confined to `/tmp`.
- `git diff --check` and review/STATUS local Markdown link checks passed.

## Decisions, delegation and cost

Review the incoming working tree rather than revert or stash existing work.
Record recommendations without adopting a new cipher model or experiment
design. No ADR is needed for proposals that have not been implemented.

Delegation: none.

- measured-by: unknown
- main-tokens: unknown
- helper-tokens: 0
- wall-clock-min: unknown

## Next and closed

Next implementation step: add the tied-score regression for F1, then retain
the raw target maximum through `_calibrate_search`.

Closed 2026-10-01: analysis and ordered plan delivered; all six findings remain
open. Durable summary added to `docs/STATUS.md`.

## Repair status — 2026-10-24

This review is the historical proposal; its original findings and reproductions
above are retained. F1, F4, F5 and F6 are implemented in the completion PR,
including a second mixed-precision fix in Phase 7 scorer validation. F2 was
already fixed upstream using `provenance.code_version` and isolated installed
command tests. F3 remains open and is outside the incoming changes. See
[completion and validation](2026-10-24-complete-pending-changes.md).
