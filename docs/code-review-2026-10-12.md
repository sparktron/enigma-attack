# REPOSITORY AUDIT: `enigma-attack`

Review date: 2026-10-12. Scope: changes and evidence dated October 5-12, from
`a752223` through `1703705`, followed by the local readiness patches. This is
a focused review before v6, not an exhaustive audit of every module. The
jCodemunch session budget ended broad exploration; remaining checks were
performed against public runner APIs and recorded artifacts.

## 1. Executive Summary

- **What it is:** A reproducible, calibrated attack on the Ultimate Enigma
  Challenge, preserving negative results and experimental provenance.
- **Stack:** Python 3.10+, standard library, optional NumPy and CUDA; this host
  has an RTX 3090. No challenge plaintext has been accepted.
- **Maturity:** Research software with substantial simulator, parity and
  calibration checks. Its scientific coverage remains bounded.
- **LOC:** Not independently counted in this review. The indexed snapshot has
  75 Python files and 2,595 symbols across 160 indexed files.
- **Top 5 findings:**
  1. The completed E-Stecker control supports the preregistered v6 launch:
     75.625% clean detection versus 34.375%, and 50% one-indel versus 15%.
  2. First-plug starts violated `max_pairs=0`; fixed with a regression.
  3. V6's power prerequisite existed only in prose; now enforced and pinned.
  4. Its evidence amendment and artifact registration were missing; completed.
  5. An additional remaining-odds multiplier was unsupported by conditional
     confirmed power; removed and the uncertainty recorded.

## 2. Architecture & Codebase Assessment

The reference simulator and fast rotor kernel are separate from the scorer,
traffic parser, ring rules, climbs, checkpointed sweeps, controls and power
harness. NumPy and CUDA accelerate the same deterministic climb, while the
runner records input and code provenance. The unchanged historical configs
remain reproducible through their existing interfaces.

Strengths demonstrated here: independent simulator agreement on 3,000 random
keys; explicit exact-key coverage; CPU/CUDA parity gates; own-arm nulls; known-key
controls; checkpoint rejection when first-plug settings change. The main
weakness is extending calibration beyond the plaintexts, faults and machine
assumptions actually tested. Long-running artifacts receive existence checks
in routine CI rather than full numerical regeneration.

No root `AGENTS.md`, `CLAUDE.md`, or `docs/ARCHITECTURE.md` exists in this
checkout. The user's supplied jCodemunch policy governed code navigation;
README layout and STATUS provided orientation. No cross-repository interface
is changed.

The week's evidence changes the next action as follows:

- Phase 2's held-out crib-prior gates failed; a generic crib campaign remains
  unsupported. FKQLZ's known-setting calibration recovered 10/32 keys at
  107 letters, supporting its use as a companion rather than a reliable solo
  ciphertext-only target.
- The complete catalogued unplugged-machine sweeps were null. Their reported
  planted-key controls have high power; unspecified wirings remain outside
  those searches. This review read the result records rather than rerunning
  those large sweeps.
- Lazy worker-side expansion removed the full sweep's approximately 47 GB
  parent allocation. CUDA provided the principal throughput improvement:
  the recorded v4 run covered 246.8 million settings in about 33 minutes,
  with CPU/GPU parity evidence. Its null and v5's split-point null stand as
  observations; their earlier power interpretation is bounded by plaintext.
- Fault controls exposed incomplete two-indel coverage. E-Stecker addresses
  trapping on ordinary plaintexts; it does not newly certify two faults.
- The 5x7 transposition control's apparent convention bug was a search-budget
  failure: the known key ranks first exhaustively. The proposed v3 was
  withdrawn because the QTXMA conservation gate rejects the target before
  controls. Neither wider plaintext-transposition searches nor another v3
  launch is justified by that resolved control issue.
- The corrected v5 typical-text rerun and the completed E-Stecker control
  supersede the earlier recommendation to stop the standard-Enigma path.
  They support amended v6 while leaving joint confirmed power unresolved.

## 3. Confirmed Bugs

**B1: Illegal one-pair starts when zero pairs were allowed — fixed.**

- Confidence: Confirmed.
- Location: `stecker_climb.py:start_boards`, line 137 after the patch.
- Reproduction: the reference and batched sweep APIs, with `first_plug=E`
  and `max_pairs=0`, both returned plugboard `EZ` on the same one-setting
  BYQMZ test. No legal improvement forced removal of the illegal seed.
- Impact: an ostensibly unplugged experiment could silently use a plug.
- Fix: reject first-plug exhaustion when capacity is below one; ordinary
  zero-pair identity searches remain supported. V6 uses ten pairs and is not
  affected by this edge case.

**B2: V6's mandatory power gate was not executable — fixed.**

- Confidence: Confirmed.
- Location: `phase1_stecker.py:run_body_direct_sweep`, line 286 after the patch;
  `experiments/phase1-body-direct-sweep-v6/config.json:power_prerequisite`.
- The previous runner passed directly from settings to `sweep_slice`;
  preflight checked simulation/scoring/parity, not the P2/P3 prerequisite.
- Impact: a missing, stale, or failing power control could precede a costly
  run despite the documented decision rule.
- Fix: validate a hash-pinned complete control, clean provenance, input and
  calibration hashes, deciding predictions, recomputed counts, compatible
  climb/ring rule and target length. Validate before preflight via config
  loading and again before direct API target search. Record the verified gate
  in the result. Ungated historical configurations retain their behavior.

**B3: The control result was not registered or reflected in current status — fixed.**

- Confidence: Confirmed.
- Locations: `artifact_claims.json`, `docs/STATUS.md`,
  `docs/phase1-experiment-history.md`, and v6's config.
- The committed control was complete, while its result entry, evidence
  amendment and corresponding claim registration were missing.
- Fix: preserve its raw bytes, register 33 claim paths as long-running,
  record its actual rates, and replace stale pending facts.

**B4: Unconditional power was presented as a multiplier after earlier nulls — fixed.**

- Confidence: Confirmed measurement interpretation error.
- Locations: v6 `refuted_by` and the v6 entry in the Phase 1 history.
- The control measures E-arm detection on new planted draws. It does not
  measure confirmed detection conditional on all four prior arms missing.
- Fix: remove that additional odds claim. Preserve the originally promised
  0.966 confirmation-factor extrapolation, explicitly labelled as inference.

## 4. Likely Bugs / Risk Areas

- **Unmeasured confirmation and retention, confirmed evidence gap:** v6's
  companion check uses both FKQLZ and XFEDT at z >= 6, but E-arm detection
  in the planted neighbourhood is not full-space top-100 retention or
  companion-confirmed power. Target: `stecker_companion.py` and v6
  `stated_power`. Measure the joint rule on representative texts before
  deriving a new closure multiplier.
- **Marginal launch threshold, sampling uncertainty:** P2 passes at 363/480,
  only three draws above 75%; its pooled Wilson interval is 71.59-79.25%.
  There are 24 repeated model-generated plaintexts, not 480 independent texts.
  Target: the E-control `result.cells` and `limitations`. Follow the
  preregistered point-estimate rule, while reporting this uncertainty.
- **Shared daily key, possible limitation:** companion failure can reject a
  legitimate single-message lead if these messages used different keys.
  Target: v6 `hypothesis` and companion acceptance. Preserve and manually
  read strong BYQMZ candidates even when the shared-key hypothesis fails;
  do not change acceptance thresholds after seeing the run.
- **Unknown machine remains unresolved:** the publisher still expresses
  uncertainty about the system. No newly sourced wiring was established in
  this review. A standard-Enigma null cannot exclude an unspecified machine.

## 5. Test Coverage Gaps

- **Critical:** plaintext-aware joint companion-confirmed power, conditional
  on the earlier four arms missing, remains unmeasured. This is an experiment
  gap in `stecker_power.py` and the joint-power analyses, not a unit-test claim.
- **Medium:** full-space top-100 retention and the E-start null's extreme tail
  are not measured by the planted neighbourhood control. Preserve sweep
  distribution and ranks; compare them after v6.
- **Long-tail:** this focused review did not inspect every CUDA kernel branch
  or independently regenerate every long-running artifact. Full GPU tests,
  parity preflight and bounded smoke checks provide narrower evidence.

New regressions cover gate failures, stale evidence and inputs, changed climb
settings, recomputed threshold failures, historical ungated behavior and the
zero-capacity bug. Raw validation logs and the bounded smoke config/result
are under `data/review/readiness-2026-10-12/`.

## 6. Improvement Opportunities

**Quick wins (<1 day):**

- **High impact, low effort:** execute the amended, checkpointed v6 rather
  than repeat v2-v5 unchanged. E-Stecker already demonstrated its gain.
- **Medium impact, low effort:** use an available GPU. LM Studio was occupying
  the RTX 3090 during this review; contention makes an idle-GPU runtime
  projection unsuitable for this session's smoke measurements.

**Medium refactors (1-3 days):**

- **High impact, medium effort:** a separately preregistered typical-plaintext
  joint confirmation control would repair the inference boundary and prevent
  another overconfident closure.
- **Medium impact, medium effort:** compare structured and random restarts at
  an equal measured compute budget, without changing v6 mid-run.

**Strategic upgrades (week+):**

- **Potentially high impact, high effort:** combine E-Stecker with the
  split-point climb only after implementing parity and an equal-cost control.
  The current code refuses that combination. Its gain is unmeasured.
- New machine searches or a crib Bombe need sourced wirings or a concrete
  related-message crib. Existing measured crib-prior gates do not establish
  an effective generic Bombe campaign.

## 7. Feature Recommendations

- **Priority high:** launch the already-built E-Stecker v6 with its measured
  gate and post-run retained-candidate checks. This is the evidenced search
  improvement for the maintainer.
- **Priority medium:** build conditional joint confirmation measurement
  before making a new odds statement. It benefits future research decisions.
- **Priority low pending control:** broader R-/I-Stecker starts or random
  restarts. These require more compute and are not demonstrated replacements
  for this run.

## 8. Security / Reliability / DX Findings

**Security:** no new critical issue was confirmed within this focused scope;
this is not a security certification.

**Reliability:** gate enforcement and invalid start rejection are fixed.
Black-box testing completed a one-setting checkpoint, resumed with zero new
settings, and rejected a checkpoint after changing only `first_plug`.
Preserve the full v6 checkpoint until completion and record every invocation;
existing timing fields cover only the latest invocation.

**Developer Experience:** the stale control status and obsolete recommendations
are corrected. The E-control is registered for CI existence checks. Source and
config hashes, raw logs and smoke inputs are preserved for continuation.

## 9. Prioritized Action Plan

**Phase 1 — Fix now:** completed zero-capacity rejection, executable power
gate, v6 evidence amendment, artifact registration and inference corrections.

**Phase 2 — Next improvements:** finish local validation, then run v6 from a
clean checkout on an available GPU. After completion, re-climb every retained
candidate on the CPU and verify the v4 score non-decrease prediction. Record
all launch/resume times and preserve readable single-message leads.

**Phase 3 — Strategic upgrades:** measure typical-text conditional confirmed
power, then compare equal-cost alternatives. Reopen machine or crib paths
only when supporting source evidence appears.

## 10. Top Patch Targets

1. `phase1_stecker.py` — enforce evidence before expensive target search.
2. `stecker_climb.py` — prevent illegal first-plug starts.
3. `experiments/phase1-body-direct-sweep-v6/config.json` — pin actual evidence
   and state its scientific limits.
4. `artifact_claims.json` — register the completed control.
5. `docs/STATUS.md` and Phase 1 history — leave accurate continuation context.

## 11. Overall Verdict

- **What's solid:** simulator agreement, complete-ring key coverage, deterministic
  engine parity, own-arm nulls and the measured E-Stecker improvement.
- **What's fragile:** generalization to authentic traffic, different keys or
  machines, retention in the full space, and conditional confirmed power.
- **Production-ready today?** Suitable for a controlled research run after the
  recorded local checks. No guarantee of decoding or exhaustive code health.
- **Must change before broader use:** measure the joint confirmed decision
  rule before treating additional nulls as precise probability statements.

### Sources and evidence

Internal evidence: `artifacts/phase1-estecker-power-v1.json`, the original v4/v5
artifacts, `data/review/plaintext-power-2026-10-12/summary.json`, and this review's
raw logs/config/result under `data/review/readiness-2026-10-12/`.

Primary pages rechecked on 2026-10-12:

- [Ultimate Enigma Challenge](https://cryptocellar.org/bgac/ultimate-enigma.html),
  page dated 27 July 2026: unknown wiring/system and the police-network
  hypothesis remain unresolved.
- [Unbroken 1941 list](https://cryptocellar.org/bgac/1941-msg-list-unbroken.html),
  status dated 19 September 2026: BYQMZ, FKQLZ and XFEDT remain listed;
  absence of QTXMA/SZAEJ does not establish a break.
- [German Army messages](https://cryptocellar.org/bgac/g-army-messages.html),
  updated 30 September 2026: the Batch C note explicitly questions whether
  these are Enigma messages. No new explanation was found here.
- [The MVUEH break](https://cryptocellar.org/bgac/the-mvueh-break.html),
  updated 24 September 2026: related-message cribs, transcription corrections
  and a different same-day key mattered. This motivates preserving leads;
  it does not supply a crib or key for Batch C.
- [Ostwald and Weierud, Modern Breaking](https://cryptocellar.org/pubs/enigma-modern-breaking.pdf),
  author version 5, March 2017, section 7: E-Stecker uses 26 starts;
  R-Stecker 73 and I-Stecker 136. Additional starts have an explicit compute cost.

### Local validation completed after the code fixes

- Full GPU-enabled unit/integration suite: **305 passed, no skips**, 229.665 s.
- Affected-path suite (runner, first-plug and new regressions): **111 passed**.
- Independent simulator: **3,000/3,000** random keys agreed across four
  implementations; published vectors, double-step and ring coverage passed.
- Artifact drift: **0 failing artifacts**; historical source-version warnings
  remain visible in the saved log and do not certify historical long runs on
  today's source. The new E-control's 33 declared claim paths were checked.
- Amended runner CUDA smoke: **complete**, nine settings, 344.304 s in total;
  all seven preflight checks, both positive controls and the pinned power gate
  passed. This run explicitly records its dirty review tree.
- Direct CUDA API checkpoint resume: **zero settings run, identical candidates**.
  It rechecked the power gate, but does not claim another preflight/control run.
- `git diff --check`: passed. Remote CI and the complete v6 target search
  were not run. Artifact determinism also completed with **0 failing artifacts**;
  long-running and superseded results were skipped according to the registry.

Next full command, from the committed review branch and with the GPU available:

```bash
python3 phase1_stecker.py --config experiments/phase1-body-direct-sweep-v6/config.json --jobs 1
```

The roughly 14-hour idle-GPU estimate is the preregistered projection from v4,
not a runtime measured in this review. LM Studio was left running.

