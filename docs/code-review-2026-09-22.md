# REPOSITORY AUDIT: `enigma-attack`

Reviewed 2026-09-22 at commit `36399219ad02fc29091bffbe5b1eeef1a9ecdf4c`.
This review changes documentation only. Findings below remain unfixed.

## 1. Executive Summary

- **What it is:** A research package for the five historical Batch C messages, with Enigma simulation, traffic analysis, alternative-family screening, and bounded search experiments.
- **Stack:** Python 3.10+, standard library, setuptools, unittest, JSON evidence/configuration, text n-gram tables.
- **Maturity:** Research prototype. It records useful experiments but is not yet a validated codebreaking pipeline.
- **LOC:** Approximately 4,100 implementation lines across ten Python modules, plus tests. This is an estimate from indexed module outlines, not a coverage measurement.
- **Validation:** All 48 existing tests passed in 6.406 seconds. Targeted reproductions nevertheless found the defects below. A wheel built, but an isolated default-corpus load from that wheel failed.
- **Top five findings:**
  1. The Phase 7 control failure is substantially a boundary/objective problem: full-text scoring ranks the true plaintext first; prefix scoring ranks it fifth.
  2. The transposition suffix is not an independent held-out dataset because candidate permutations change which source characters enter training.
  3. Swiss K stepping omits the left rotor's double step and can advance the reflector repeatedly while the left rotor remains stationary.
  4. Phase 4's baseline was selected using messages later called held out.
  5. Phase 7 can audit one configured corpus but pass a different corpus into the target search.

No real challenge plaintext was recovered or accepted during this review. The most consequential new result concerns the synthetic control, not QTXMA.

## 2. Architecture & Codebase Assessment

The implementation is organized as sequential research phases:

- `enigma.py` supplies permutation/involution validation, rotor movement, and encryption.
- `phase1.py` supplies corpus loading, Army indicator handling, a bootstrap scorer, and fixed-plugboard key enumeration.
- `phase2.py` produces metadata networks, archive queries, and no-self-encryption crib placements.
- `phase3.py` runs known machine profiles from `variants.json`.
- `phase4.py` mutates shared wiring and date-specific keys through simulated annealing.
- `phase5.py` performs per-message statistical triage using uniform and conditional permutation nulls.
- `phase6.py` searches double columnar transpositions; `phase7.py` adds source grouping and published n-gram scoring.
- `recon.py` and `ic_null.py` are older standalone statistical utilities.

Strengths include explicit source uncertainty, checked permutation constraints, standard Enigma vectors, deterministic local RNGs in the newer experiments, raw search artifacts, and careful statements that smoke runs do not exclude whole cipher families. Phase 5's conditional null preserves letter frequencies and unknown positions, appropriately avoiding the earlier confound between nonuniform monograms and structural repetitions.

Weaknesses are experimental coupling and incomplete independent validation. Phase 7 calls Phase 6's private helpers; Phase 4 inherits a baseline selected by Phase 3; catalogs, corpus loading, resource paths, and evidence validation are distributed across runners. Structural reciprocity checks cannot validate a historically correct variant: the same incorrect permutation can encrypt and decrypt successfully.

Maintainability is reasonable for the current small package. Larger searches need a stable model/scorer/search interface, bounded candidate retention, and one validated effective experiment configuration.

Review scope covered all phase implementations, simulator behavior, representative tests, packaging, project status/history, and targeted execution. This was not an exhaustive key search, a fresh facsimile transcription of all five messages, or proof that every possible input is handled.

## 3. Confirmed Bugs

### F1 — P1: Prefix selection misdiagnoses the published scorer's recovery ability

- **Confidence:** Confirmed by exhaustive diagnostic over all 2,880 control keys.
- **Location:** `phase6.py:191` (`_exhaustive_pair`), `phase6.py:233` (`_anneal_pair`), `phase7.py:154` (`run_experiment`); diagnosis in `docs/phase7-experiment-history.md` and the previous `docs/STATUS.md`.
- **Description:** Selection scores only a candidate plaintext prefix. This rewards moving a more favorable text segment into that prefix. The Phase 7 gate then reports positionwise accuracy without diagnosing boundary displacement.
- **Reproduction:** The 148-character control produces a candidate with `candidate[:-4] == truth[4:]`: 144 consecutive characters are exactly correct, while the initial `DIEK` becomes terminal `KEDI`. Positionwise accuracy is only `0.060810811`. The true key ranks **5th** under prefix scoring, but **1st** under full-text scoring across all `4! × 5! = 2,880` keys. Full-text exhaustive selection recovers the exact plaintext and key for this control.
- **Why it matters:** The recorded failure was driving the project toward replacing a scorer that already solves this particular exhaustive control when given the appropriate objective. Increasing data or search effort alone would not fix the prefix boundary preference.
- **Fix:** Diagnose the objective before replacing the scorer. Retain top-k candidates, record exact recovery and displacement/edit diagnostics separately, and evaluate a preregistered full-text objective on independent known-key controls. Keep exact ciphertext/key reconstruction mandatory; do not accept a displaced near-recovery as a solved message. One successful control is not broad solver validation.

### F2 — P1: A key-dependent suffix is treated as independent validation

- **Confidence:** Confirmed methodological defect and source-index reproduction.
- **Location:** `phase6.py:191`, `phase6.py:233`, `phase6.py:384` (`evaluate_search`), `phase6.py:504` (`run_experiment`).
- **Description:** Different candidate transpositions move different ciphertext characters into the scored prefix. Characters in the winning candidate's suffix may already have participated in optimization under other keys. In addition, prefix optimization changes which letters remain in the suffix.
- **Reproduction:** Exhaustively searching widths `(2, 3)` over 20 uniquely labeled source characters with a 15-character training prefix exposes **all 20** source characters to the scorer across candidates. The test at `tests/test_phase6.py:37` checks only the length passed to the scorer, so it cannot detect this dependence.
- **Why it matters:** Suffix deltas can be useful descriptive statistics, but the acceptance rules cannot interpret them as independent generalization. The candidate suffix and original ciphertext suffix also need not contain the same letters.
- **Fix:** Calibrate the complete selection procedure on independent known-key messages and negative controls with identical search budgets. Run the entire optimizer for each null replicate and compare search-selected maxima. Use a truly separate message for validation only when a shared key/procedure is justified. Rename the present statistic to avoid an independence claim.

### F3 — P1: Swiss K 1941 stepping omits the slow-wheel double step

- **Confidence:** Confirmed against the mechanism described in the cited research and a local state trace.
- **Location:** `enigma.py:173` (`EnigmaMachine.step`); missing regression at `tests/test_phase3.py:40`.
- **Description:** The reflector advances at the left notch, but the left rotor advances only at the middle notch. Under the documented Enigma stepping of the left rotor, its own notch must also trigger its movement.
- **Reproduction:** Swiss profile, rotors I-II-III, initial positions `YAA`, reflector `A`: current states are `YAA/A → YBA/B → YCA/C → YDA/D`. Rotor I remains at its turnover while the reflector advances on successive keys. The existing test starts with both relevant rotors at their notches, masking the missing condition.
- **Why it matters:** The affected variant's ciphertexts and rankings are mechanically wrong around these states. Reciprocity does not catch this.
- **Fix:** Advance the left rotor on `middle_notch or left_notch`, and the reflector on `left_notch`. Add independent state traces before, during, and after turnover, including left-only notch and non-A ring settings. Reissue affected variant artifacts.
- **Source:** Hamer, Sullivan, and Weierud, [Enigma Variations](https://www.cryptocellar.org/pubs/enigvar.pdf), printed pp. 9–10, inspected 2026-09-22. The paper describes the stationary right wheel, fast middle wheel, and Enigma stepping of the left wheel.

### F4 — P1: Phase 4's baseline has already seen its held-out messages

- **Confidence:** Confirmed from the selection and baseline-validation paths.
- **Location:** `phase3.py:253` (`build_certificate`), `phase3.py:172` (`_search_profile_date`), `phase4.py:578` (`_verify_phase3_baseline`), `phase4.py:421` (`run_seed`).
- **Description:** Phase 3 ranks each daily key on every message for that date. Phase 4 requires its starting key to match the top Phase 3 candidate, then uses SZAEJ and XFEDT as held-out messages and measures improvement against that baseline.
- **Why it matters:** The baseline and initial search state were selected partly using those messages. Negative held-out deltas are confounded by regression away from a baseline favored on the same data. The within-loop test that held-out messages are not scored does not cover this earlier selection.
- **Fix:** Split first. Select the baseline and all hyperparameters on training data only, or use a genuinely prespecified baseline. Repeat the bounded experiment before describing its held-out deltas as evidence of unseen-message generalization. Preserve the historical run, marked as selection-contaminated.

### F5 — P2: Phase 7 audits one corpus and can search another

- **Confidence:** Confirmed with a mocked successful-control path.
- **Location:** `phase7.py:154` (`run_experiment`).
- **Description:** Phase 7 audits `config['corpus']`, then clones the Phase 6 config and replaces only experiment ID, widths, and seeds. It does not propagate the corpus path.
- **Reproduction:** Setting the Phase 7 corpus to a temporary `alternate.json` still forwards `corpus.json` to `phase6.run_experiment`. Successful controls were mocked solely to reach this normally gated branch.
- **Why it matters:** A corrected transcription could be audited and hashed while the target solver silently uses the older corpus. The checked-in defaults currently coincide, so the existing recorded run is not evidence of this mismatch occurring historically.
- **Fix:** Build and validate one effective config, propagate the selected corpus, and require upstream evidence hashes to match the actual search input. Add a success-path test with genuinely different corpus contents.

### F6 — P2: Built distribution omits required resources and Phase 7

- **Confidence:** Confirmed by wheel build and isolated execution.
- **Location:** `pyproject.toml:13`, `pyproject.toml:20`; default resource paths in `phase1.py:30` and the later runners.
- **Description:** The explicit module list excludes `phase7`; package configuration includes no corpus, catalogs, experiment configs, or n-gram tables. Phase 2 and Phase 7 also lack console entry points while neighboring phases have them.
- **Reproduction:** `python3 -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/enigma-review-wheel` succeeded. The wheel contained no project JSON/frequency resources and no `phase7.py`. Extracting it outside the checkout and calling `phase1.load_corpus()` raised `FileNotFoundError` for `corpus.json`.
- **Why it matters:** Installation success currently hides unusable default commands. Tests import from the checkout and cannot detect this.
- **Fix:** Package code and immutable resources explicitly, use package-resource APIs or explicit input paths, and write outputs outside installed resources. Add one wheel-install smoke test in a clean temporary environment. Alternatively, explicitly remove distribution support and document checkout-only operation.

### F7 — P2: Reconnaissance removes unknown positions before structural tests

- **Confidence:** Confirmed with synthetic inputs.
- **Location:** `recon.py:21` (`repeated_ngrams`), `recon.py:26` (`autocorrelation`).
- **Description:** Both functions call `letters_only`, deleting `?` and closing the gap. This fabricates adjacency and changes offsets after the uncertain BYQMZ character.
- **Reproduction:** `AB?CAB?C` reports repeated `ABC` twice, although no observed `ABC` exists. `AB?AB` reports two lag-2 matches with rate 1.0; the position-preserving Phase 5 implementation correctly reports zero lag-2 matches.
- **Why it matters:** Running the advertised reconnaissance utility can contradict the corrected Phase 5 analysis and suggest false cribs or periods.
- **Fix:** Delegate structural statistics to the position-preserving Phase 5 functions, or skip windows/pairs containing unknown symbols without deleting their positions. Add these two regression cases.

### F8 — P2: Zero-plugboard searches crash during mutation

- **Confidence:** Confirmed runtime failure.
- **Location:** `phase4.py:336` (`_mutate_plugboard`), `phase4.py:92` (`load_config`).
- **Description:** With no current pairs and `max_plugboard_pairs=0`, the available action list is empty, but the function calls `rng.choice` on it. The config loader does not reject or normalize this combination.
- **Reproduction:** `_mutate_plugboard((), random.Random(0), 0)` raises `IndexError`.
- **Why it matters:** A legitimate unsteckered-machine experiment fails if plugboard mutation retains a nonzero weight.
- **Fix:** Treat zero capacity as a no-op or remove that mutation from eligible moves. Validate bounds and weights together; also check trace intervals and finite temperatures.

### F9 — P2: Phase 6 searches the target after a failed positive control

- **Confidence:** Confirmed control-flow reproduction; already acknowledged in Phase 7 history.
- **Location:** `phase6.py:504` (`run_experiment`).
- **Description:** Positive-control acceptance is calculated only after the substitution and target searches. Phase 7 adds a preflight, but direct Phase 6 runs retain this behavior.
- **Reproduction:** Forcing a failed positive control still produces five search calls: positive, substitution, and three target seeds. The final status correctly says `invalid_positive_control_failure`, but all target candidates have already been generated and retained.
- **Why it matters:** It wastes the expensive search budget and exposes target results during a supposedly gated validation workflow.
- **Fix:** Move control evaluation before target search in the shared runner, emit an explicit skipped target result, and let Phase 7 reuse that gate rather than implement another copy.

## 4. Likely Bugs / Risk Areas

- **R1 — Confirmed validation gap, uncertain recovery impact:** `experiments/phase6-qtxma-double-transposition-smoke-v1/config.json:13` uses a 4×5 control (2,880 states, exhaustive) but 5×7, 7×5, and 7×7 target branches use annealing. Passing the control does not validate that optimizer. Add known-key controls on every deployed search branch and matched lengths, including ragged rows.
- **R2 — Possible historical mapping errors:** `enigma.py:195`, `phase3.py:53`, and `tests/test_phase3.py:23` do not establish independent commercial-profile known-answer vectors. Validate ETW direction, rotor orientation, reflector setting, and procedure separately. This review does not assert a confirmed ETW wiring bug.
- **R3 — Confirmed scaling risk:** `phase3.py:172` retains every candidate and its plaintext before sorting. Expanding to all rings gives 1,054,560 ordinary I–V settings per date before adding plugs or reflector positions. Replace the list with a bounded top-k heap before expansion; actual peak memory was not measured.
- **R4 — Possible false confidence from repeated seeds:** `phase6.py:313` ignores seeds in exhaustive branches, while `phase6.py:504` counts passing seeds. Identical exhaustive outcomes are not independent replication. Deduplicate and report effective independent stochastic runs; even distinct seeds on one ciphertext are not independent messages.
- **R5 — Confirmed evidence limitation:** `phase5.py:186` adjusts for scans within lag and period tests, but does not supply familywise calibration across messages, diagnostics, and successive research choices. Its uniform null is explicitly not an Enigma generator. Retain routing labels; do not convert QTXMA's monogram result into a machine exclusion. Add matched synthetic Enigma and manual-cipher controls.
- **R6 — Possible data leakage:** `phase7.py:121` uses published plaintexts whose overlap with the frequency-table training corpus is unknown. Existing documentation discloses this. Acquire a documented independent evaluation corpus before claiming out-of-sample scorer validation.
- **R7 — Reliability gap:** `phase6.py:478` checks the upstream schema and route, but does not verify that the Phase 5 artifact was computed from the current corpus. Bind artifacts to their input hashes and fail on stale evidence.

## 5. Test Coverage Gaps

### Critical

- `enigma.py:173`: independent Swiss turnover traces, including only the left rotor at its notch; unit and independent differential tests. The present one-step test misses F3.
- `phase6.py:191`, `phase7.py:154`: exact control recovery under full and partial objectives, retained true-key rank, displacement diagnostics, and search-level null calibration; integration/experiment tests. These distinguish scorer failure from objective failure.
- `phase4.py:578`: prove that baseline selection excludes held-out messages, not merely that the annealing loop does; integration test.
- `phase7.py:154`: successful gate with an alternative corpus and stale upstream artifact; integration test.

### Medium

- `pyproject.toml:20`: build/install/run outside the source checkout; packaging integration test.
- `phase6.py:233`: known-key recovery across multiple widths, ragged lengths, and fixed seeds; benchmark with a preregistered recovery target and budget, rather than a unit test expecting stochastic perfection.
- `phase6.py:504`: failed controls must make zero target calls; orchestration test.
- `recon.py:21`: masked adjacency/lag cases; unit tests.
- `phase4.py:336`: zero capacity and maximum capacity; unit tests.

### Long-tail

- `phase1.py:120`: empty/all-unknown messages, duplicate designators, malformed indicators; loader tests.
- `phase4.py:92`, `phase6.py:448`, `phase7.py:154`: zero trace intervals, non-finite numbers, empty/duplicate seeds, invalid weights, empty validation sets; configuration tests.
- `ic_null.py:7`: importing the module reseeds global randomness and executes 500,000 simulations. Add a main guard/local RNG before treating it as a library; no import-time run was performed in this review.

## 6. Improvement Opportunities

### Quick wins (less than one day each; estimates)

- **Shared control gate — high impact, low effort:** Fix F9 and remove duplicated Phase 7 preflight orchestration.
- **Mechanical and input fixes — high impact, low effort:** F3, F5, F7, and F8 with focused regression tests.
- **Diagnostic reporting — high impact, low effort:** Show exact recovery, longest matching substring/edit distance, true-key rank on controls, and selected candidate boundaries. Preserve strict final acceptance.

### Medium refactors (roughly one to three days each; estimates)

- **Effective experiment config and evidence manifest — high impact, medium effort:** A single source of truth for corpus, scorer, optimizer, partitions, hashes, and output paths.
- **Installable package — medium impact, medium effort:** Resource handling and clean-install smoke coverage for F6.
- **Top-k and batched scoring — high impact, medium effort:** Bounded storage, integer-coded n-grams, and precomputed transformations, verified against the readable reference implementation.

### Strategic upgrades (week or longer; estimates, not promised break dates)

- **Calibrated recovery benchmark — high impact, high effort:** Independent authentic messages, known keys, multiple cipher families, matched false-positive controls, and fixed budgets.
- **A real standard-Enigma attack — high impact, high effort:** Rotor/ring search plus stecker optimization or crib constraints. Phase 1 currently accepts only supplied plugboards; Phase 4's arbitrary-wiring optimizer does not complete that baseline.

## 7. Feature Recommendations

- **Candidate verification command — high priority:** Given an immutable candidate, independently re-encrypt its raw plaintext, report exact source mismatches/edits, and verify indicator handling. Benefits every branch; build this before accepting a break.
- **Search coverage ledger — high priority:** Track explicit rotor/ring/model coverage, heuristic plugboard budget, seeds, scorer version, runtime, and checkpoints. Benefits reproducibility and avoids equating unsuccessful heuristics with exhaustive exclusion.
- **Corpus partition experiments — high priority:** Run individual messages and historically justified shared-key groups as separate hypotheses. Benefits standard-Enigma and machine-inference work; same date alone must not force a shared key.
- **Substitution-family comparator — medium priority:** Give QTXMA a calibrated monoalphabetic-substitution attack alongside transposition, since its monogram signal cannot distinguish those families. Benchmark first; avoid adding speculative families without new evidence.

## 8. Security / Reliability / DX Findings

**Security:** No critical security vulnerability was established in the reviewed local CLI paths. An indexed search for shell execution/evaluation and obvious credential markers returned no matches; this is not a secret-history or supply-chain audit. Inputs are local research files, not an exposed service.

**Reliability:** F5–F9 and R7 affect corpus identity, installation, uncertainty, configuration, and experiment gating. Historical artifacts should remain immutable; corrected runs need new IDs and an explicit supersession note.

**Developer experience:** The standard-library runtime and short unittest suite make local development straightforward. No tracked GitHub workflow appeared in the repository metadata listing. The published wheel needs a clean-install check. `python3` is available on this host; `python` is not. Tests passing in the checkout do not establish CI or installed-package correctness.

## 9. Prioritized Action Plan

### Phase 1 — Fix now

1. Correct the scorer-failure diagnosis and implement the F1/F2 objective/calibration redesign in a new experiment, preserving old evidence.
2. Fix Swiss K stepping, corpus propagation, shared control gating, masked reconnaissance, and zero-plugboard handling.
3. Rebuild Phase 4 baselines from training-only inputs; mark the previous result's selection limitation.
4. Fix packaging and install-time resource handling; add targeted regressions and clean-checkout CI.

### Phase 2 — Next improvements

1. Validate exact control recovery and false-positive behavior across exhaustive and annealing branches, authentic messages, several keys, and target-like lengths.
2. Resolve the source-status discrepancy for QTXMA/SZAEJ through public evidence. The publisher's unbroken list dated 19 September 2026 lists BYQMZ, FKQLZ, and XFEDT only; absence alone does not prove the others solved. [Current list](https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html), checked 2026-09-22.
3. Complete an efficient standard-Enigma baseline for the currently listed messages; investigate QTXMA's frequency-preserving branch separately.
4. Use archive-derived cribs with actual consistency constraints, not just no-self placement counts.

### Phase 3 — Strategic upgrades

1. Expand only branches that recover held-out known-key benchmarks within an explicit budget.
2. Add supported historical variants with independent vectors and justified procedures.
3. Return to arbitrary machine wiring only after simpler branches, corpus partitions, and scorer/search controls are credible.
4. Require independent ciphertext reproduction and corroboration before declaring any challenge message solved.

Detailed work packages and exit criteria are in [ATTACK_PLAN.md](ATTACK_PLAN.md).

## 10. Top Patch Targets

1. `phase6.py` — objective, calibration, candidate retention, control gate, stale-evidence checks.
2. `phase7.py` — effective corpus/config propagation and richer control diagnostics.
3. `enigma.py` and `tests/test_phase3.py` — Swiss stepping and independent variant validation.
4. `phase4.py` — training-only baseline selection and zero-capacity mutation.
5. `pyproject.toml` — package resources, Phase 7, and installed-command tests.
6. `recon.py` — preserve unknown positions.
7. `phase1.py` — benchmarked standard-key/stecker attack after validation repairs.

## 11. Overall Verdict

- **What's solid:** Standard-Enigma reference behavior on the existing vectors, deterministic bounded runs, permutation constraints, explicit uncertainty in the newer phases, and cautious no-break reporting.
- **What's fragile:** Independent validation claims, the transposition objective/control diagnosis, Swiss variant stepping, pipeline input identity, and installed execution.
- **Production-ready today?** No. It is a useful research prototype, not a finished or broadly validated attack system.
- **Must change before broader use:** Repair the confirmed bugs, recalibrate experiments, validate the actual search branches on independent known-key cases, and implement the unfinished standard-Enigma attack.

The immediate opportunity is unusually concrete: the existing published scorer already ranks the exact synthetic control solution first when scoring the whole message. Fix that objective and its validation framework before buying more compute or abandoning the scorer. There is still no evidence here that any real challenge code has been cracked, and no defensible date by which a break can be guaranteed.
