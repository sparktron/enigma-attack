# Plan of attack

Prepared 2026-09-22 from the [code review](code-review-2026-09-22.md), at source commit `36399219ad02fc29091bffbe5b1eeef1a9ecdf4c`.

The engineering goal is a reproducible, validated attack pipeline. The research goal is a historically credible plaintext/key recovery. Completing the engineering work cannot guarantee the research result. Existing smoke runs are not exhaustive negative results.

## 1. Repair the evidence before expanding searches

**First work package: objective and control diagnostics.**

- Preserve the Phase 6/7 artifacts and add a new diagnostic experiment ID.
- Demonstrate the current result: the 148-character control is recovered exactly by exhaustive full-text scoring; its true key ranks first overall and fifth under prefix scoring. The previous winner contains the correct 144-character interior displaced by four positions.
- Retain top-k candidates and report exact match, correct-key rank on synthetic controls, positional accuracy, edit distance, and contiguous matching segments. Boundary diagnostics explain failures; they do not relax the exact-break criterion.
- Replace the claim of an independent candidate suffix with search-level calibration. A transposition changes the data included in the prefix. Score the full candidate and estimate significance by running the entire same-budget optimizer on negative controls.
- Use genuinely separate plaintexts/keys for development and final evaluation. Do not tune against QTXMA or repeatedly reuse a nominal holdout.

**Exit:** The original control recovers exactly; boundary-adversarial controls behave as expected; the planned acceptance rule measures exact recovery and a calibrated false-positive rate. The old 6.1% statistic is explained, not erased.

**Second work package: correctness and orchestration.**

- Fix Swiss K left-wheel double stepping, with independent multi-step vectors.
- Propagate one effective corpus/configuration throughout Phase 7 → Phase 6.
- Check input hashes when consuming prior-phase artifacts.
- Stop the shared runner immediately when mandatory controls fail.
- Preserve unknown positions in reconnaissance; support zero-plugboard mutation safely.
- Re-select Phase 4's baseline from training messages only. Do not reuse the Phase 3 all-message winner as an unseen-message baseline.
- Package resources and Phase 7, and run commands outside the checkout in CI.

**Exit:** Targeted regression tests pass; the 48 existing tests remain green; an installed wheel runs its bounded commands; failed gates make no target-search calls; corrected artifacts carry new IDs and provenance.

## 2. Validate the attack methods at the actual difficulty

Construct an immutable benchmark manifest with plaintext source, training/evaluation separation, message length, cipher family, key, corruption budget, and RNG seed.

- Include several authentic raw Army messages spanning approximately the target lengths, with operator conventions preserved.
- For transposition, include 4×5, 5×5, 5×7, 7×5, and 7×7, several independently selected keys, and incomplete rows. Force the annealing branch in its own controls: the old 4×5 exhaustive success says nothing about annealing recovery.
- For Enigma, include non-A rings, turnover crossings, ten-pair stecker, indicators, and independent published or second-implementation ciphertexts.
- Include uniformly random, shuffled natural-language, monoalphabetic-substitution, and known Enigma negative/alternative controls at matching lengths.
- Measure exact plaintext/key recovery, top-k true-key rank, time, candidate evaluations, and false acceptances. Repeated exhaustive searches count once; repeated RNG seeds are not independent messages.
- Predeclare the search budget and evaluation set. Record recovery proportions and uncertainty rather than a single favorable example.

**Exit:** Each deployed optimizer branch reaches a declared recovery target on unseen controls, and its full search has a measured false-positive rate. If not, profile scorer rankings versus search failures separately before changing either.

## 3. Re-establish corpus identity and current target status

- Preserve raw forms, grouped transcription, normalized text, alternative readings, and immutable hashes separately.
- Recheck all five indicators and bodies, focusing on the uncertain BYQMZ character and any plausible group/boundary error. Do not infer insertions/deletions merely to improve a score.
- Refresh the source ledger. The publisher's unbroken list dated **19 September 2026** names **BYQMZ, FKQLZ, XFEDT**, while the project retains QTXMA and SZAEJ from the original five-message challenge. Their omission needs a documented explanation; it is not proof of a break. [Publisher's list](https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html), checked 2026-09-22.
- Search public adjacent traffic, matching callsigns, retransmissions, times, and related plaintexts using the Phase 2 archive priorities. Do not send external inquiries without explicit authorization.
- Treat same-date and network membership as hypotheses about shared keys. Compare individual-message and justified multi-message partitions.

**Exit:** A versioned corpus with an evidence-backed status and uncertainty record for each message. A list of sourced cribs and explicit key-sharing hypotheses is ready for testing.

## 4. Complete the standard-Enigma branch

Prioritize BYQMZ, FKQLZ, and XFEDT as the currently listed unresolved set. Keep the original five-message experiments reproducible.

- Keep the readable Python simulator as the reference implementation and compare the fast search kernel against it.
- Enumerate the 60 I–V rotor orders and relevant ring settings under UKW-B, with indicator-derived body starts for that procedure. There are `60 × 26³ = 1,054,560` raw rotor/ring combinations per assumed daily key, before plugboard optimization.
- Implement a tested plugboard optimizer and/or genuine crib-menu constraints. Fixed supplied plugboards do not complete this branch. Preserve involution, pair limits, and indicator consistency.
- Search individually and then jointly only within justified daily/network groups. A high-IC message must not dominate or invalidate another message's baseline by assumption.
- Use versioned raw-Army scoring, multiple known-key recovery controls, top-k retention, deterministic checkpoints, and measured throughput before allocating long runs.
- Run the clean transcription first. Introduce only explicitly budgeted source alternatives afterward, recording ciphertext edits and penalties. Treat insertions/deletions separately because they alter rotor alignment.

**Exit:** Every run has auditable model and keyspace scope, empirical recovery performance, exact attempted budget, and re-encryptable finalists. An unsuccessful hill climb is a bounded unsuccessful search, not proof that Enigma has been excluded.

## 5. Pursue QTXMA with calibrated frequency-preserving attacks

QTXMA's monogram evidence makes this a reasonable branch, not a cipher identification.

- After work packages 1–2 pass, preregister a fresh bounded full-text transposition run. Keep old target results out of parameter tuning.
- Include equivalent boundary/order configurations and inspect top-k candidates; do not add arbitrary cyclic rotations or edits unless the transformation remains within the stated cipher model.
- Validate then run a monoalphabetic-substitution comparator under matched budgets. A substitution control merely demonstrates that transposition should not win on that input; it is not a substitution solver.
- Calibrate each complete search against matched negative controls, including selection across widths and seeds.
- Expand widths or add route/transposition conventions only when controls recover those conventions or archival evidence supports them. Five-letter grouping alone does not establish a key width.

**Exit:** Reproducible candidates with exact round-trip verification, readable substantial plaintext, and evidence exceeding search-calibrated noise. Otherwise issue a bounded negative result and choose the next experiment from new evidence.

## 6. Escalate historical models only when justified

- Repair and independently validate each known variant before comparing it.
- Apply a historically plausible indicator procedure or label the artificial procedure explicitly.
- Compare models with matched recovery calibration; a larger keyspace gets more chances for a high accidental score.
- Revisit unknown-wiring inference only after simpler key/procedure hypotheses and corpus partitioning have been tested credibly.
- Use training-only model/baseline selection and genuinely separate messages for validation. Fix the mechanism before estimating free wiring; penalize complexity and source edits.

**Exit:** A more complex hypothesis explains reproducible evidence the simpler alternatives cannot, rather than merely improving a training score.

## 7. Accept and independently reproduce a break

For each proposed solution, save raw plaintext, machine/cipher specification, complete key, indicator derivation, source alternatives, and code/data versions.

Require:

1. Exact re-encryption of the observed ciphertext, or an explicit minimal source-error ledger that is independently justified.
2. Correct indicator and body-boundary treatment.
3. Coherent German military text over substantial length, with no score-driven editorial rewriting.
4. Consistency across messages when a shared key or mechanism is claimed; allow a genuine single-message break when independence is appropriate.
5. Independent reproduction using another implementation, with historical corroboration where obtainable.

**Engineering completion:** Tested installed commands, validated simulators and search branches, immutable evidence manifests, checkpointable attacks, honest coverage reports, and an independent verifier.

**Research completion:** Verified plaintext/key recoveries for the messages still confirmed unresolved, or a clearly bounded research result if the surviving evidence remains insufficient. No forecast of a guaranteed cracking date is justified.
