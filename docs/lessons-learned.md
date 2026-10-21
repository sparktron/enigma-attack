# Lessons learned: enigma-attack

**Purpose of this document.** It lists the lessons from building `enigma-attack`, an attempt to break five unsolved 1941 German Army messages (Batch C: QTXMA, SZAEJ, BYQMZ, FKQLZ, XFEDT). They are written as rules that carry over to other code-breaking, cryptanalysis, search, and mathematical-proof projects. The document is meant to be given to an LLM, or a person, as operating instructions for a new project of that kind.

**How to read it.** Each lesson has the same parts:
- **Rule:** what to do, stated as an instruction.
- **Why:** the failure in this project that taught it, with dates and figures where they are on record.
- **How:** concrete mechanics.
- **Check:** a test that shows whether the rule is being followed.

Terms are defined in section 0. Section 11 gives a reusable project skeleton, and section 12 a short instruction block to paste into an LLM's context.

**Project outcome, for context.**
- None of the five messages was broken.
- The project ran seven complete or partial sweeps of BYQMZ under the standard Enigma I assumption, all null, each with measured detection power.
- A statistical gate excluded QTXMA from the transposition family on letter-conservation grounds.
- A trigram-repeat test found QTXMA inconsistent with any rotor machine.
- In October 2026 one of the original researchers said he now believes none of the five is Enigma.

The lessons are mostly about how a search-heavy research project goes wrong without anyone noticing, and how to make it go right on purpose.

---

## 0. Vocabulary

- **Target:** the object the project is trying to solve, here a ciphertext. In a proof project: the conjecture, or the theorem to formalize.
- **Hypothesis family:** a class of explanations for the target, such as "Enigma I with reflector B" or "double transposition". In a proof project: a proof strategy, or a class of counterexamples.
- **Search:** a procedure that enumerates or optimizes over a hypothesis family's parameters, here a key space.
- **Positive control (planted control):** an input built so that the right answer is known, run through the identical pipeline. Here: Army plaintext enciphered under a known random key. In a proof project: a known theorem, a known counterexample, or a known-satisfiable instance.
- **Negative control / null:** an input on which the search should find nothing, used to measure how good a score looks by chance.
- **Power (detection probability):** the fraction of positive controls the full pipeline finds and accepts.
- **Null result:** a completed search that accepted nothing. It is informative only in proportion to its power.
- **Odds multiplier:** after a null with power P against a hypothesis, that hypothesis's prior odds are multiplied by about (1 − P).
- **Preregistration:** a committed configuration that fixes the hypothesis, the statistic, the threshold, the controls and the predicted outcome before the decisive data is looked at.
- **Artifact:** the machine-readable result file a run produces, carrying provenance.
- **Claim paths:** the fields of an artifact that make up its scientific claim, as opposed to timestamps and paths.
- **Gate:** a cheap test that must pass before an expensive stage is allowed to run.

---

## 1. Triage before search: run the cheap tests first

### 1.1 Rule: before any expensive search, run every cheap statistical test that could exclude the hypothesis family.

**Why.**
- The project spent weeks on QTXMA as a double transposition: Phase 6 and Phase 7 searches, scorer validation and controls, all preregistered and all refuted.
- A transposition only permutes letters, so its ciphertext must keep plaintext letter frequencies. QTXMA has no D, F, G or U in 155 letters, where German Army plaintext has 2.90% D and 4.47% U. Its commonest letter, Y, is at 12.3% against a reference 0.89%.
- One frequency count would have excluded the hypothesis before either phase ran. The project's own write-up says so: "one `collections.Counter` call would have shown it."
- Later, the trigram-repeat test, a 99-second computation, found QTXMA inconsistent with any rotor machine (p = 0.001 against a length-matched Enigma null). That fact also predates months of rotor-machine reasoning about the batch.

**How.**
- For every hypothesis family, list the **invariants** it must preserve and the **signatures** it must show. Examples:
  - Transposition preserves letter counts.
  - A monoalphabetic substitution preserves repeat structure and IC.
  - A rotor machine gives near-flat letters and near-chance repeats.
  - Enigma never enciphers a letter to itself.
  - A 25-letter Playfair-like system never produces J.
- Compute each one on the target against a reference distribution and a length-matched null. Record a **routing decision** per target: excluded, consistent, or untestable at this length.
- Put the result in code as a gate. The search runner must refuse a target the gate excluded. This project's `phase6.py` and `phase7.py` were changed to refuse QTXMA.

**Check.** For each expensive search, can you point to the cheap tests that were run first, and to a committed gate result showing the target was not already excluded?

### 1.2 Rule: a test must check *which* property the hypothesis needs, not a nearby property that correlates with it.

**Why.** QTXMA was routed to "frequency-preserving" on an elevated index of coincidence alone. IC measures how concentrated a distribution is, not which letters carry the concentration. A substitution onto a non-plaintext alphabet raises IC too. The routing never tested the property transposition actually requires, which is the plaintext's letter identities.

**How.** For each routing rule, write down the property it is supposed to establish and the statistic that establishes it, and confirm the statistic is sufficient as well as necessary. Two-part gates such as "elevated IC **and** compatible with Army monograms" are usually right.

**Check.** Could a hypothesis the gate is meant to exclude still pass it? Build such an input and try.

---

## 2. Calibrate the whole pipeline, end to end, on the exact path the real run takes

### 2.1 Rule: measure power with positive controls that go through every stage the real search uses, at the parameters the real search can actually reach.

**Why.**
- The stecker hill-climb was first calibrated by handing it the *true* wheel setting. It recovered the plugboard in 8 of 8 trials, later 28 of 32.
- The real sweep could not visit that exact setting, because it fixes some parameters and searches others. End-to-end, through the parameterization the sweep reaches, detection was 82.5% at best (review of 2026-10-02, finding P1).
- A calibration that certifies a setting the search never visits overstates power.

**How.**
- Plant random keys with *all* parameters random, including the ones the search treats as fixed or reduced.
- Run the identical search code and the identical acceptance rule.
- Count a planted draw as detected only if the pipeline would have accepted it in the real run.
- Report power with an interval (the project used Wilson 95% intervals) and the number of draws.

**Check.** Diff the code path the control runs against the code path the target run uses. Every difference is either justified in writing or removed.

### 2.2 Rule: measure power on inputs that are typical of the target, not on one convenient example.

**Why.**
- Every power control in Phase 1 enciphered one constructed plaintext with IC 0.0792, which is unusually easy. The closure of the standard-Enigma search rested on those figures.
- On four Markov plaintexts of typical IC, the same pipeline detected 67 of 160 (41.9%), against 39 of 40 (97.5%) on the easy text (review of 2026-10-11, B-1).
- The odds multipliers quoted for the four nulls were therefore valid only for that one plaintext, and had to be restated.

**How.**
- Draw control inputs from a distribution, such as many real plaintexts or a Markov model fitted to real ones. Report power as a function of the input's difficulty (here IC) as well as a single number.
- If the decision depends on power, the power must be measured on the input distribution the target plausibly comes from.

**Check.** How many distinct control inputs does the power figure rest on? If it is one, the figure is an anecdote.

### 2.3 Rule: validate the core model against real historical data, not only against data you generated with the same model.

**Why.**
- For most of the project the Enigma simulator was tested against published test vectors and against keys the repository planted itself. Planted-key controls cannot catch a shared modelling error: the same wrong machine both enciphers and attacks.
- On 2026-10-20 the 13 authentic 1941 messages from Ostwald and Weierud's companion page were added with their recovered keys. All 13 decipher letter for letter, which validates the model on real traffic.
- The check also found an error in the *source*: the page prints the wrong start position for one message (DEI, copied from the previous message). Exhaustive search showed ZAQ to be the only one of 17,576 positions that reproduces the published plaintext (24 of 24 letters; the next best agrees on 10).

**How.**
- Collect real solved instances with their published solutions. Turn each into a test that runs the model and compares the result exactly.
- When a real instance fails, search for the correction, such as a nearby parameter, before blaming the model. Then record both the published value and the corrected one, with the evidence.

**Check.** Is there at least one test where the input came from outside the project and the expected output was published by someone else?

### 2.4 Rule: run the positive control before the target, and refuse to search the target if the control fails.

**Why.** An early Phase 6 run searched the target after its positive control had failed (review of 2026-09-22, F9). A search whose control fails cannot produce an interpretable null or an interpretable hit.

**How.** In the runner, the control comes first and its pass/fail is checked in code before the target loop starts. Record the control's result in the same artifact.

**Check.** Make the control fail on purpose. Does the target search refuse to run?

---

## 3. Separate selection from evaluation

### 3.1 Rule: data used to choose anything is not held out.

**Why.**
- Phase 3 ranked daily keys on every message from the date. Phase 4 then started from the top Phase 3 key and reported SZAEJ and XFEDT as "held out", although they had helped choose that key (2026-09-22, F4).
- Separately, the transposition search scored a prefix of each candidate. Because each permutation moves different ciphertext letters into the prefix, all 20 source characters reached the scorer across candidates, so the "held-out suffix" was not independent (F2).

**How.**
- Split the data first, before any ranking, tuning or baseline selection.
- When the hypothesis itself permutes the data, as transposition does, a prefix/suffix split is not a split. Calibrate the whole selection procedure on independent known-answer instances and on nulls with identical search budgets.
- For proof work: lemmas or heuristics tuned on a problem set cannot be evaluated on that set.

**Check.** For each "held-out" item, trace every decision upstream of the evaluation and confirm the item influenced none of them.

### 3.2 Rule: score with the objective you actually care about; test the objective before replacing the scorer.

**Why.**
- Phase 7's positive control failed, and the project moved toward replacing the n-gram scorer. The real cause was the objective. Keys were selected on a training prefix, which ranked the true key fifth of 2,880. The full-text objective ranks it first and recovers the control exactly.
- Separately, the recovered text was the right plaintext rotated by four characters: 97.3% agreement at that offset, reported as 6.1% by a strict positional metric. The 148-letter control is an exact multiple of the 4-wide first stage.

**How.**
- When a control fails, first diagnose *where* in the pipeline the truth was lost: the score, the ranking, the selection or the acceptance metric.
- Use acceptance metrics that are invariant to the symmetries of the hypothesis family, such as rotation, reflection or relabelling, or report the best alignment explicitly.
- Choose control sizes that do not align with the structure being searched. This project added a 133-letter control that is a multiple of neither stage width.

**Check.** For each failed control, is there a written diagnosis that names the stage that lost the truth?

---

## 4. Preregister decisions, and treat deviations as data

### 4.1 Rule: before running a decisive experiment, commit a configuration that fixes the question, the statistic, the null, the controls, the threshold, the decision rule and the prediction.

**Why.** With many possible statistics, thresholds and subsets, a motivated analyst can find "something" in any null result. The project preregistered every sweep and power control. When a result disappointed, as with the split-point climb falling short of both deciding thresholds on 2026-10-07, the rule decided the next step. Opinion did not.

**How.** A configuration file under `experiments/<id>/config.json`, committed before the run, containing:
- `question`: what is being decided, in one or two sentences.
- `statistics.primary`: an exact definition, with edge cases such as uncertain characters.
- `statistics.secondary`: reported, but not decisive.
- The null: how simulated draws are made, how many, and the seed.
- `controls`: what the calibration requirement is, and what happens if it fails.
- `decision.threshold`, with its rationale (for example 0.01 Bonferroni-corrected over five targets gives 0.002).
- `decision.rule` and `decision.prediction`.
- `what_it_does_not_decide`: the limits, stated in advance.

**Check.** `git log` shows the configuration committed strictly before the runner produced its artifact. The artifact records the configuration's SHA-256.

### 4.2 Rule: every departure from the preregistration is recorded as a dated, explained amendment. A rule broken on purpose is disclosed as a decision, not hidden.

**Why.**
- v4's engine was changed from `batched` to `cuda` before its run. This was disclosed as a deviation after the CUDA engine reproduced the batched climb bit for bit.
- v7 was launched against its own power control's rule, on the maintainer's explicit, recorded decision.
- After the trigram run, a code review found the calibration seed hard-coded in the runner rather than read from the config. The fix added it to the config as an amendment with `after_run: true` and a note that the value was unchanged.
- In each case, a later reader can still tell exactly what was decided in advance.

**How.**
- Keep an `amendments` list in the config: `date`, `after_run`, `change`, `reason`.
- Never edit a preregistered field silently. If a change could affect results, rerun and show that the claim fields are unchanged, or record that they changed.
- Edit the file as text so the diff shows only the amendment. Re-serializing JSON reformats the whole file and hides the change; this happened once in this project and was reverted.

**Check.** `git diff` of the config between preregistration and now shows only additions under `amendments`, or changes each of which an amendment explains.

### 4.3 Rule: label exploratory findings as exploratory. Turn the interesting ones into a new preregistered test; do not promote them in place.

**Why.** The trigram test found that FKQLZ and XFEDT are *flatter* than Enigma output (lower-tail IC p of about 0.001 and 0.004) and contain no J. That was not the question asked, and the lower tail was not preregistered. It was recorded under "Speculation (exploratory, not preregistered)", and a follow-up test was recommended. Shortly afterwards an independent source, Ostwald's 2023 note, marked the same two messages as J-less, which supports the lead without converting it into a result.

**How.** Keep separate headings in every write-up: **Fact** (measured, preregistered), **Inference** (reasoning from the facts), **Speculation** (post hoc), **Unresolved**, **Recommendation**. A finding moves up a heading only after a new preregistered test.

**Check.** Does any sentence in a "Fact" section depend on a statistic chosen after the data was seen?

---

## 5. Make a null result mean something

### 5.1 Rule: a null result is reported with its power and the odds multiplier it implies. "We found nothing" without power is not reported at all.

**Why.**
- The first IC-stage sweep at a ten-pair stecker had almost no power: averaged over 32 key draws, the true key reached the top 200 of 1,054,560 with probability 0% at 167 letters. A null from that stage says nothing.
- The later sweeps reported, for example, clean detection 88.8% and one-indel detection 41%, so a reader could compute what each null excluded.

**How.**
- For every completed search, state the detection probability against each fault model: clean, one substitution, one dropped or inserted letter, two indels.
- Multiply the prior odds of the hypothesis by (1 − P) for each independent null, and say which input distribution the P values were measured on.
- Check the top score against the expected noise maximum. If the best candidate scores like the best of the null, say so explicitly.

**Check.** Could a reader compute, from the write-up alone, how much the null should change their belief?

### 5.2 Rule: model the faults the real input may contain, and measure power under each.

**Why.**
- Historical ciphertexts contain transcription errors: dropped, inserted or substituted letters, and one uncertain character, '?', in BYQMZ.
- One dropped letter desynchronizes a rotor machine for the rest of the message. The whole-message climb's power fell from about 88% clean to about 41% with one indel.
- That drove the windowed climb (the first and last 117 letters climbed separately) and a split-point climb that searches the position of one indel.

**How.**
- Enumerate the fault models of the source. Plant faults into controls at their realistic rates and positions, and measure power per model.
- For uncertain source characters, step the machine but do not score that position. Apply the same masking to every null draw, at the same index.

**Check.** Is there a power figure for each fault model the source plausibly contains?

### 5.3 Rule: stop at a stated point. Write down in advance what result closes a line of work, and close it when the result arrives.

**Why.**
- After four nulls and a fault-power study, the maintainer closed the standard-reading search of BYQMZ on 2026-10-10, with the remaining odds recorded.
- Further sweeps were preregistered only for new, specific reasons, such as a new stecker-start strategy shown by its own control to raise power. They were not run hoping that one more sweep would hit.

**How.** In each preregistration, state what the next step will be for each outcome, and which outcome ends the line. Record closures in the history with the evidence that justified them and the conditions that would reopen them, such as "a reply naming a sourced wiring reopens the search at that wiring".

**Check.** Is there a written condition under which this line of work stops?

---

## 6. Provenance and reproducibility

### 6.1 Rule: every artifact records the code version, a dirty-tree flag, the hashes of every input, the seeds, and the configuration hash. Decisive runs are made from a clean tree.

**Why.** An early long-running artifact recorded a git commit from *before* the code that produced it, and a module hash that matched neither (2026-10-02, P4). Without a dirty flag there was no way to know what had actually run.

**How.**
- At the start of a run, before the work, record:
  - `git rev-parse HEAD` and the branch;
  - `git status --porcelain`, as `dirty: true/false` plus the list;
  - the SHA-256 of every project module the process imported, taken from `sys.modules` rather than a hand-kept list;
  - the SHA-256 of each input file and of the configuration;
  - every seed.
- Commit the runner, then run, then commit the artifact. If the code changes after review, regenerate from the new clean commit and show that the claim fields are unchanged.

**Check.** For a randomly chosen artifact: does checking out its recorded commit and rerunning reproduce its claim fields?

### 6.2 Rule: keep an allowlist of each artifact's claim fields, and run an automated check that regenerates artifacts and compares those fields.

**Why.** Code changes silently invalidate old results. Byte-for-byte comparison is useless, because artifacts embed timestamps, paths and git state. A *denylist* of volatile fields fails dangerously: forgetting one field silently stops checking a conclusion.

**How.**
- `artifact_claims.json` maps each artifact to the command that regenerates it and to a list of claim paths, such as `targets[].p_values.*` or `decision.*`.
- `check_artifacts.py drift` regenerates each artifact and compares only the claim paths. A changed value is a hard failure; an added or removed key is a warning.
- `check_artifacts.py determinism` runs twice and compares, which catches unseeded randomness.

**Check.** Change a constant that affects a result. Does the drift check fail?

### 6.3 Rule: every external input is fetched once, hashed, recorded with its URL, retrieval date and licence, and turned into data by a committed, rerunnable script.

**Why.** The keyed-message data file was first built by a parser kept in a scratch directory. Review flagged that the transcription, and the DEI→ZAQ correction search, could not be reproduced from the repository. The extraction script was then committed, and it rebuilds the file byte for byte from the saved page.

**How.**
- Store the source's URL, retrieval timestamp, SHA-256 and licence beside the data.
- Commit the extraction code, including any correction search, so the data file is a build product.
- Freeze a manifest *before* reading held-out content. Phase 2's held-out manifest was committed before any held-out plaintext was read, and it lists what each page contains by structural inspection, with long capital runs masked.
- Note encoding traps. The companion page indents its plaintext with non-breaking spaces (U+00A0), and the first parse silently dropped every plaintext line because of it.

**Check.** Delete the data file and rebuild it from the recorded sources with committed code. Is it identical?

### 6.4 Rule: dry-run the real entry point with the real configuration before handing a configuration over or launching a long run.

**Why.** A Phase 7 v3 configuration was preregistered and withdrawn the same day, never run, because the runner refuses that target. A smoke run of the real entry point would have shown it before the preregistration.

**How.**
- Every runner accepts a small-budget mode, such as `--draws 200` or a nine-setting slice.
- Smoke mode must not be able to overwrite the committed artifact. The trigram runner now refuses `--draws` unless `--output` is also given.
- The smoke artifact is marked `smoke: true`.

**Check.** Before any long run, has the exact command been run at small scale in this checkout, and has the output been inspected?

---

## 7. Independent implementations and parity

### 7.1 Rule: every fast implementation (vectorized, GPU, compiled) is checked bit for bit against a slow, readable reference before it is used, and the parity check is part of every run's preflight.

**Why.**
- The project has a readable reference machine (`enigma.py`), a fast kernel (`enigma_fast.py`) and a CUDA stecker climb.
- The CUDA engine was used for the v4 sweep only after it reproduced the batched climb bit for bit. All 220 chunks of a concurrent CPU run of the same sweep then matched exactly.
- The 2026-09-22 audit found the Swiss K variant's stepping wrong around turnover in the reference itself, and reciprocity tests did not catch it.

**How.**
- Keep the reference simple and close to the published description of the mechanism.
- Generate pseudorandom settings and compare outputs between the implementations at the start of every run (`kernel_parity`, `scorer_parity`, with seeds and sample counts in the config).
- Test mechanisms with state traces before, during and after edge events such as notch turnover and double stepping, not only with end-to-end properties like reciprocity.

**Check.** Does every run artifact contain a parity section that passed?

### 7.2 Rule: positive controls are produced by the reference, not by the fast path under test.

**Why.** If the fast kernel both enciphers the control and attacks it, a shared fault passes. `stecker_traffic.encipher_control` deliberately builds control ciphertext with `enigma.EnigmaI` while the attack runs on `enigma_fast`.

**How.** In code, make the control generator import only the reference.

**Check.** grep the control-generation path for imports of the fast modules.

---

## 8. Engineering mechanics that kept results honest

### 8.1 Rule: enforce prerequisites in code, not in prose.

**Why.** v6's power prerequisite existed only in the documentation until a review (2026-10-12) made the runner check a hash-pinned power artifact, its measured counts and the configuration hashes before the target search. A prerequisite in prose is skipped as soon as someone is in a hurry.

**How.** The runner loads the prerequisite artifact, checks its hash against the value pinned in the config, checks the specific fields, and exits non-zero before doing work if anything fails.

**Check.** Corrupt the prerequisite artifact. Does the runner refuse to start?

### 8.2 Rule: make long runs checkpointed and resumable, and make resumption refuse incompatible checkpoints.

**Why.** Sweeps ran 13 to 20 hours. A black-box test verified that changing a search parameter (`first_plug`) makes the runner reject a prior checkpoint, while an unchanged run resumes with zero settings rerun and identical candidates.

**How.** A checkpoint stores the configuration hash and the code hashes. Resumption compares them and refuses on mismatch. Resuming is the same command as launching.

**Check.** Change one config value and resume. Is the run refused?

### 8.3 Rule: read seeds and parameters from the configuration. Never hard-code a value the configuration claims to set.

**Why.** The trigram runner hard-coded its calibration seed while the configuration mentioned it only in prose, so the two could drift apart unnoticed. Found in review and fixed with a disclosed amendment.

**How.** Every number that affects the result lives in the config and is read from it. The artifact echoes the values used.

**Check.** grep the runner for numeric literals, and justify each one.

### 8.4 Rule: when changing code that consumes randomness, preserve the random stream or rerun the experiment.

**Why.** Review suggested reusing an existing plugboard generator in the trigram runner. It was declined, because that generator draws from the RNG differently and would change every simulated draw of a preregistered experiment.

**How.** Treat the sequence of RNG calls as part of the experiment's definition. If it must change, bump the experiment version.

**Check.** After a refactor, does the drift check pass with unchanged claim values?

### 8.5 Rule: avoid duplicate implementations of the same statistic.

**Why.** The trigram runner re-implemented an IC function that Phase 5 already had, and its trigram-window scan existed twice in one file. If the copies drift, two parts of the project report different numbers for the same text, and write-ups compare those numbers directly.

**How.** One implementation per statistic, in a shared module, imported everywhere.

**Check.** Search for the statistic's formula in more than one place.

### 8.6 Rule: write tests that can fail for the reason that matters, and avoid tests that couple unrelated data.

**Why.**
- The trigram experiment's calibration requirement was that none of 13 authentic ciphertexts be flagged. Seven of them cannot be flagged at all: at 18 to 48 letters they have no repeats, so p = 1.0. Only two are as long as the targets. The control passed, but it was weaker than its count suggested, and the write-up now says so.
- Separately, a test required two unrelated data files to contain exactly the same message set. Any legitimate addition to either would have broken a test about the Enigma engine. It now checks only the shared entries.

**How.**
- For each control or test, ask: what wrong state of the world would make this fail? If the answer is "almost nothing", strengthen it or label it as weak.
- Use length-matched or difficulty-matched controls.

**Check.** Mutation-test the important checks: break the thing on purpose and confirm the test fails.

---

## 9. Working with sources, experts and the outside world

### 9.1 Rule: ask the domain experts early, and read what they send in full.

**Why.**
- The 2005 paper's footnote said its authors suspected "an Enigma machine with differently wired wheels". The project treated that as a lead for a long time.
- When asked directly on 2026-10-10, Frode Weierud replied the next day:
  - the footnote came only from the failure of their own 2003-04 runs;
  - no logs of those runs survive;
  - he now believes none of the five messages is Enigma at all.
- That reply was unread for nine days.
- The 2023 note attached to it, by Olaf Ostwald, contained facts that directly sharpen the project's open questions:
  - FKQLZ and XFEDT are marked J-less, like the 25-letter non-Enigma texts;
  - shared radio frequencies;
  - operator and handwriting assignments;
  - an argument that only four-letter repeats, not trigram repeats, are telling at these lengths.
- The note also partly corrected the expert's own summary. Weierud's email said trigram repeats, while Ostwald's note says trigram repeats are expected by chance and quadgram repeats are the evidence.

**How.**
- Before building on a published claim, find out what it rests on. Ask the authors, specifically, which tests their claim came from.
- Check the inbox, or other incoming channels, before reporting status or planning the next step.
- Read attachments in full, translating if needed. Record every point that bears on the project in the history, marked by source, and do not commit private material without permission.
- When an expert summary and the expert's underlying notes disagree, test both.

**Check.** For each assumption the project leans on, is there a named source, and has that source been asked what the assumption rests on?

### 9.2 Rule: published sources contain errors. Verify them computationally where possible, and report corrections back.

**Why.**
- The companion page printed the wrong start position for one message. The repository's corpus and Ostwald's table disagree on two metadata readings: operator "Otor. ?" against "Stor.", and addressee "g19" against "912".
- Ostwald's own note has a divisor typo in one calculation, and its "70.6%" trigram figure is an upper-bound approximation; the exact Poisson value is about 51%.

**How.** Keep the published value next to every correction, with the evidence and the method. Draft corrections to the source's maintainers; send them only with the owner's approval.

**Check.** Does every corrected datum retain its published value?

### 9.3 Rule: anything sent outside the project (email, issue, PR comment) is drafted for the owner and sent only with explicit approval. Check its current state before editing a draft.

**Why.** In this session a reply draft was sent by the owner while further edits to it were being prepared. The edit attempt failed with "Message not a draft". The correct response was to check the thread, confirm what had already gone out, and draft a follow-up containing only the new material.

**How.** Before editing any outward-facing draft, re-read its current state. Never resend content that has already been sent.

**Check.** Before each outward action: what has the recipient already received?

---

## 10. Translating these lessons to mathematical-proof projects

The structure of a code-breaking project maps closely onto proof and conjecture work. The mapping and the lessons that follow from it:

| Code breaking | Proof / conjecture work |
|---|---|
| Target ciphertext | Conjecture, open problem, or theorem to formalize |
| Hypothesis family (Enigma, transposition) | Proof strategy, or class of counterexamples |
| Key-space search | Counterexample search, SAT/SMT search, tactic search, case enumeration |
| Cheap invariant gate (letter conservation, IC) | Necessary conditions, parity/modular obstructions, small-case checks, known bounds |
| Planted-key positive control | Run the search or prover on known theorems and known counterexamples of the same shape and size |
| Null distribution | How often the heuristic "succeeds" on random or false instances |
| Power | Probability the search finds a counterexample if one of the targeted kind exists, measured on planted counterexamples |
| Reference vs fast kernel parity | Kernel-checked proof vs. tactic output; brute-force checker vs. optimized search; two independent solvers |
| Real historical traffic test | Reproduce published results and known values (OEIS terms, known Ramsey numbers) before trusting the code |
| Fault models (indels) | Mis-specified definitions, off-by-one indexing, wrong conventions such as 0- or 1-based or inclusive bounds |
| Preregistration | State exactly the lemma, the search space and what result counts as a proof or a refutation before running |
| Artifact claim paths | Certificates: the counterexample itself, the SAT proof (DRAT), the formal proof term, verifiable independently |

**Specific carry-overs:**
1. **Check necessary conditions first.** Before a large counterexample search, check every cheap obstruction the conjecture implies. The QTXMA lesson is that one count can save weeks.
2. **Plant known answers.** Before trusting a "no counterexample up to N" result, plant counterexamples into similar structures, measure how often the search finds them, and report the search's power.
3. **Reproduce known values first.** Run the code on every published known case and require exact agreement. The project found an error in a published source this way, so expect to find some.
4. **Use independent checkers.** A fast search finds candidates; a slow, simple, separately written checker verifies each one. Better still, emit a certificate checkable by a third tool (a formal kernel, or a DRAT checker for SAT).
5. **State the search space exactly.** "Searched all cases up to N" must say which symmetries were quotiented out and which parameters were fixed. The 2026-10-02 review found the project's coverage denominator mis-specified.
6. **Separate exploration from proof.** Numerical patterns found while exploring are conjectures. Promote them only through a stated test, and keep "Fact / Inference / Speculation" headings in notes.
7. **Bound a null result.** "No counterexample found" must say up to what size, under which assumptions, and with what power against counterexamples of the targeted form.
8. **Ask what the literature's claim rests on.** "It is believed that..." in a paper may rest on one failed attempt, as the wheel-wiring footnote did.

---

## 11. Reusable project skeleton

```
project/
  README.md                  What the project is, how to run each phase, current status in one paragraph.
  AGENTS.md                  Operating rules for agents (this document's section 12, adapted).
  docs/
    STATUS.md                Dated current state: what is closed, what is open, what is next, and why.
    ATTACK_PLAN.md           The hypothesis families, ordered by cost and prior, with their gates.
    <phase>-experiment-history.md   One section per experiment: Cause, Method, Fact, Inference,
                             Speculation, Unresolved, Recommendation. Deviations and withdrawals stay in.
    code-review-<date>.md    Periodic audits: findings with location, reproduction, impact, fix.
  data/<source>/             External inputs + README (URL, retrieval date, SHA-256, licence, extraction).
  experiments/<id>/config.json   Preregistered configuration, with an amendments list.
  scripts/<id>.py            Runner for that experiment; writes artifacts/<id>.json.
  artifacts/<id>.json        Result with provenance (commit, dirty flag, module hashes, input hashes, seeds).
  artifact_claims.json       Claim-path allowlist + regeneration command per artifact.
  check_artifacts.py         drift / determinism checks over the claim paths.
  provenance.py              code_version(): commit, branch, dirty flag, imported-module hashes.
  <reference model>.py       Slow, readable, close to the published mechanism.
  <fast model>.py            Optimized; parity-tested against the reference in every run's preflight.
  tests/                     Unit tests, mechanism state traces, real-solved-instance tests,
                             gate-refusal tests, smoke-mode-cannot-overwrite tests.
```

**Experiment lifecycle (each step a separate commit):**
1. Cheap gates on the target: record the routing.
2. Write the preregistered configuration, then commit it.
3. Write the runner and tests, smoke-run the real entry point at small scale, then commit.
4. Run from a clean tree and inspect the artifact (`dirty: false`).
5. Register the claim paths and run the drift check.
6. Write the history entry, keeping Fact, Inference and Speculation separate, and update STATUS.
7. After review, fix, regenerate from the new clean commit, and confirm the claim values are unchanged.

---

## 12. Instruction block for an LLM working on a similar project

Paste the following into the system prompt or AGENTS.md of a new code-breaking, search or proof project.

```
You are working on a research project that searches a large hypothesis space for a solution
(a key, a decipherment, a proof, or a counterexample). Follow these rules.

TRIAGE
1. Before any expensive search, list the invariants and signatures the hypothesis family
   implies and test each cheaply on the target against a length- or size-matched null.
   Record a routing decision. Refuse in code to search a target a gate has excluded.
2. A routing test must establish the property the hypothesis needs, not a correlated one.

CONTROLS AND POWER
3. Measure power with planted positive controls that pass through the identical pipeline
   and acceptance rule as the real run, with every parameter randomized as in reality.
4. Draw controls from a realistic input distribution; never rest power on one input.
5. Validate the core model on real, externally published solved instances with exact
   comparison. When one fails, search for a correction before blaming the model, and keep
   both the published and corrected values.
6. Run the positive control first; abort the target search if it fails.
7. Measure power under each fault model the real input may contain.

SELECTION VS EVALUATION
8. Data used to choose anything is not held out. If the hypothesis permutes the data, a
   prefix/suffix split is not a split.
9. When a control fails, find the stage that lost the truth (score, ranking, selection,
   acceptance metric) before replacing any component. Use symmetry-invariant metrics.

PREREGISTRATION
10. Before a decisive run, commit a config fixing question, statistic, null, controls,
    threshold with rationale, decision rule, prediction, and what it does not decide.
11. Record every deviation as a dated amendment (date, after_run, change, reason). Edit
    the config as text so the diff shows only the amendment.
12. Label post-hoc findings "exploratory"; promote them only through a new preregistered
    test. Keep Fact / Inference / Speculation / Unresolved / Recommendation separate.

NULL RESULTS
13. Report every null with its power per fault model, the input distribution that power
    was measured on, the implied odds multiplier, and whether the top score matches the
    null's expected maximum. State in advance what result closes a line of work.

PROVENANCE
14. Every artifact records commit, dirty flag, imported-module hashes, input hashes,
    config hash and seeds, captured before the work starts. Run decisive experiments from
    a clean tree.
15. Maintain a claim-path allowlist per artifact and a drift check that regenerates and
    compares those paths.
16. Every external input: URL, retrieval date, SHA-256, licence, and a committed
    extraction script that rebuilds the data file exactly.
17. Smoke-run the real entry point before preregistering or launching; smoke mode must not
    be able to overwrite committed artifacts.

IMPLEMENTATION
18. Check fast implementations bit for bit against a slow reference in every run's
    preflight. Generate positive controls with the reference only.
19. Test mechanisms with state traces around edge events, not only global properties.
20. Enforce prerequisites in code (hash-pinned artifacts checked before work), not prose.
21. Checkpoint long runs; refuse to resume a checkpoint whose config or code hash differs.
22. Read every result-affecting value from the config. Treat the RNG call sequence as part
    of the experiment: a refactor that changes it requires a new experiment version.
23. One implementation per statistic. Write tests that fail for the reason that matters;
    label weak controls as weak.

SOURCES AND OUTSIDE CONTACT
24. Ask domain experts what published claims rest on. Check for replies before reporting
    status. Read attachments in full; record relevant points by source; do not commit
    private material without permission.
25. Draft outward communication for the owner; send only with explicit approval; re-read a
    draft's current state before editing it.
```

---

## Appendix: key numbers from this project, for calibration of expectations

| Quantity | Value | Where it came from |
|---|---|---|
| Body-direct stecker climb at the true setting, 167 letters, 10 pairs | 28/32 exact (87.5%, 95% CI 72–95%) | `phase1-fkqlz-length-calibration-v1` |
| End-to-end planted-key detection, reachable parameterization | 82.5% (68–91%) | `phase1-joint-power-v1` |
| Detection with neighbouring right positions, clean / one indel | 88.8% / 41% | `phase1-windowed-climb-power-v1` |
| Same pipeline, easy plaintext vs four typical plaintexts | 39/40 (97.5%) vs 67/160 (41.9%) | review 2026-10-11 |
| Companion confirmation at z ≥ 6 | accepts 39/40 true keys, 0/240 wrong | `phase1-companion-calibration-v1` |
| Complete-ring-rule sweep size and GPU time | 246.8 million settings, 33 min | `phase1-body-direct-sweep-v4` |
| QTXMA vs Army monograms | chi-square 3.38/letter vs 0.17–0.68 for real transpositions; p = 0.0002 | Phase 5 conservation gate |
| QTXMA trigram repeats vs Enigma null (155 letters) | 5 vs 97.5% point 3; p = 0.001 | `phase5-trigram-repeat-v1` |
| Random-text quadgram repeat rate at 160 letters | about 1 in 40 | Ostwald 2023, one-million-text experiment |
| Authentic 1941 messages deciphered exactly | 13/13 (one with a corrected start position) | `tests/test_historical_messages.py` |
