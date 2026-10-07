# Project status

Updated: 2026-10-06

## Current state

The nine confirmed findings in the [repository audit](code-review-2026-09-22.md)
have engineering fixes on `master`. The [attack plan](ATTACK_PLAN.md) still
describes the broader research program. Historical Phase 3–7 artifacts and v1
configurations remain available; corrected runs use new v2 identifiers and
artifacts. No challenge plaintext has been accepted.

Phase 1 has now been run at scale for the first time. The method the
repository cites — Weierud and Sullivan's *Breaking German Army Ciphers* — was
implemented, calibrated against known keys, and then run to completion. The
calibration found that the cited method's first stage, an unsteckered
index-of-coincidence sweep, **has almost no detection power at a ten-pair
stecker**: averaged over 32 key draws, the true key reaches the top 200 of the
1,054,560 keys each indicator ordering ranks with probability 0% at 167
letters, 6% at 371 and 19% at 800 (`phase1-ic-rank-v1`, which replaces a single-draw z ≥ 3 table).
It also found that the indicator-coupled formulation
`phase1.py` implies **cannot be hill-climbed** because the plugboard sits
inside the indicator machine as well as the body. It also found that a
body-direct stecker climb (start position searched directly, indicator used
only as an independent check) recovers a known ten-pair plugboard and its exact
plaintext on 28 of 32 trials (87.5%, 95% interval 72–95%) at 167 letters when
handed the true setting, once an index-of-coincidence phase runs ahead of the
n-gram phase (the first 8 draws were 8 of 8; `phase1-fkqlz-length-calibration-v1`
re-measured it over 32). That is the stecker
stage alone: end to end, through the parameterization a sweep can actually
reach, a planted-key control detects 82.5% (95% interval 68–91%) at best.
With the neighbouring right positions a complete sweep also visits, that is
88.8% clean and 41% when one letter of the message is dropped or inserted
(`phase1-windowed-climb-power-v1`; the earlier 15% came from a slice that
held the planted right position). The complete indicator-coupled search
(2,109,120 daily keys, both indicator orderings) and a declared 0.15% slice of
the body-direct space on BYQMZ were both run to completion and found nothing,
exactly as the calibration predicted; the body-direct slice's retained
candidates were re-confirmed on 2026-10-03 with the ring-recovering
confirmation and still score below their own sweep scores. A head-and-tail
**windowed climb** (W = 117: the first and last 117 letters climbed
separately, the better kept) was calibrated in the preregistered
`phase1-windowed-climb-power-v1`: on one-indel draws it detects 56% against 41%
for the whole-message climb on the same draws, and 15 of 80 that the whole
message misses, at a cost of 10 points on clean draws (78.8% against 88.8%).
All three of its deciding predictions held, so the preregistered rule called
for a windowed sweep. `phase1-body-direct-sweep-v3` ran it over the same 27.4
million settings (16.95 h) and is also **null**: no retained candidate is
companion-confirmed (best z 4.64 against 6), and its top score is the noise
maximum (z 6.22). On planted draws v2 and v3 together confirm 73/80 clean keys
and 46/80 with one indel, so the two nulls multiply the odds of a standard
reading in this space by about 0.09 ungarbled and 0.43 with one indel. A companion-body confirmation (review R4) is
calibrated in `phase1-companion-calibration-v1`: at z ≥ 6 it accepts 39/40
exact-plugboard keys and none of 240 wrong candidates. The complete
middle-past-notch sweep of BYQMZ (27,418,560 settings, 16.4 hours) ran as the
preregistered `phase1-body-direct-sweep-v2`, with a stated detection probability
of about 0.80 for an ungarbled message; measured jointly on the same planted
draws afterwards (`phase1-joint-power-v1`) it is 0.825, and 0.875 clean and
0.40 with one indel once the neighbouring right positions are in the slice
(`phase1-joint-power-v2-middle-past-notch`). It is **null**: no retained candidate is
companion-confirmed (best z 4.47 against a threshold of 6), and the sweep's top
score is the expected noise maximum. See
[Phase 1 history](phase1-experiment-history.md) and its linked raw artifacts.

Phase 5 now carries a **conservation gate**, and it closes the transposition
branch for QTXMA on grounds that do not depend on any search.

A transposition permutes the plaintext and cannot change which letters are
present, so a frequency-preserving cipher over German Army plaintext must show
Army plaintext monograms. QTXMA shows nothing of the kind. It contains no D, F,
G or U in 155 characters, against published 1941 Army frequencies of 2.90% for
D and 4.47% for U, and its commonest letter is Y at 12.3% against a reference
0.89%. Its chi-square distance from Army monograms is 3.38 per letter, where
true transpositions of known Army plaintexts score 0.17 to 0.68.

`frequency_preserving` now requires elevated IC **and** compatibility with Army
plaintext monograms. QTXMA fails the second at `p = 0.0002`, is recorded as
`excluded_by_conservation`, and reroutes to `non_plaintext_alphabet_substitution`.
`phase6.py` and `phase7.py` refuse an excluded target outright.

This supersedes the Phases 6 and 7 reading of QTXMA. Those experiments were
sound in method and correctly recorded their refutations; the hypothesis they
tested was excluded by letter conservation before either ran, and one
`collections.Counter` call would have shown it. Their artifacts are retained as
the record of searches that were real when performed.

The Phase 7 v1 positive-control failure was a separate measurement artifact.
Its recovered plaintext was the control plaintext rotated by four characters —
97.3% agreement at that offset, reported as 6.1% by a strict positional metric —
because the 148-letter control is an exact multiple of its 4-wide first stage.
Phase 7 v2 measures recovery over the rotations the stage geometry can produce
and adds a 133-letter control that is a multiple of neither stage width.

That failure had a second, independent cause. v1 selected keys on a
training prefix, which ranked the true key fifth of all 2,880 controls; the
full-text objective ranks it first and recovers the 148-character 4×5 control
and its key exactly. Under both fixes two of the three v2 controls pass
exactly, the 133-letter ragged control recovering both stage keys, and the
independent solved-message 5×7 control still fails at 5.3% positional
agreement. That failure is a whole-message rotation rather than a scrambled
miss: the recovery agrees with the known plaintext completely at an offset of 75
of its 76 positions, which neither stage width can produce. It is an open
question about the ragged-row convention at that length, and it is now a
question about the search machinery rather than about QTXMA, which conservation
has already closed.

## Correctness and evidence repairs

- The conservation gate excludes a transposition of German Army *plaintext*. It
  does not exclude a transposition applied to an already-substituted or encoded
  layer, and it does not prove QTXMA is non-Enigma.
- The gate's Dirichlet concentration was chosen so known true transpositions
  pass with margin. This biases it against excluding, so a non-exclusion is
  weak evidence and only an exclusion carries weight.
- What maps plaintext onto QTXMA's 22-letter alphabet is unidentified. The
  signature — IC 0.0577, restricted alphabet, concentration on the wrong
  letters — is not yet matched to a sourced family, and adding one to
  `cipher-families.json` requires real provenance rather than a guess.
- QTXMA and SZAEJ are the two 29 September messages, both omitted from the
  2026-09-16 unbroken list, and they share the absent set {D, F, U}. That
  coincidence is unexplained.
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
- The wheel includes every phase command and the corpus, catalog,
  configuration, artifact, n-gram and Army-plaintext-control inputs they read.
  Installed commands read those from the installed share directory and write
  default outputs under the current working directory. `enigma-phase1 search`
  and `enigma-phase2` had hashed their own source under the share directory
  and failed when installed; they now run from a clean wheel, as
  `enigma-phase1-stecker` does since `edfa918`. A relative
  `enigma-phase1-stecker --config` is read from the working directory when the
  file is there, and from the shipped experiments otherwise.
- Every phase records one shared `code` block (`provenance.py`): commit,
  branch, `git status` lines, a `dirty` flag, and hashes of every project
  module the run imported, taken before the run starts. It replaces the stecker
  runner's `environment.git_dirty` (`edfa918`) and its fixed list of hashed
  files, and Phases 1, 2, 3 and 5, which recorded no checkout state at all, now
  record it too. Without a checkout `dirty` is `null`,
  not `false`, and a copy installed inside an unrelated repository does not
  report that repository's commit. Artifacts committed before this change keep
  their original provenance fields.
- `phase1_stecker.py` is now the runner only; scoring, traffic, the climbs,
  the search spaces and ring rules, the sweeps, the calibrations, the controls
  and the end-to-end power control are separate `stecker_*.py` modules. The
  split moved code without changing it: the regenerated calibration artifact
  matches every declared claim.
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
- The Phase 1 body-direct confirmation recovers the ring setting instead of
  reusing the one the sweep held. The sweep absorbs the left and middle rings
  into the start position it searches, and the indicator's fixed clear
  Grundstellung does not share that freedom, so confirming under the held rings
  tested a daily key the sweep never proposed and could have dismissed a
  genuine hit. A candidate with no compatible ring setting is flagged rather
  than skipped.
- The published-count scorer is validated for recovering known double
  transpositions; the earlier claim that it could not is withdrawn.
- Original form grouping adds no new body boundary. QTXMA's present status in
  the source's unbroken list remains unresolved.
- The messages used to compile the published n-gram counts are not enumerated,
  so overlap with the solved-message validation set cannot be ruled out. The
  same caveat applies to the unigram reference the gate derives from them.
- The known-key transposition controls are constructed or independently solved
  plaintexts, not authentic held-out Army traffic.
- Phase 1's indicator-coupled space is now completely searched (2,109,120 daily
  keys) and is a closed dead end: its IC statistic and its hill-climb both have
  zero power at a ten-pair stecker, not a coverage gap. The body-direct
  formulation works but its space is about 2.74 x 10^7 settings per message at
  a measured ~456 ms of CPU time per converged climb, a projected 3,472
  core-hours (about 8 days of wall-clock time on 18 cores) for one message in
  pure Python; only 0.15% of it has been searched, and that slice held every
  ring at A, so it could reach an exact equivalent of a true key for about 2.5%
  of keys. Under the right-ring-searched, middle-past-notch rule a complete
  sweep of that space reaches an exact equivalent for 71.6% of keys at 167
  letters and detects 82.5%; holding the middle ring at A gives 52.4% and
  67.5%. Pure-Python speed is now the binding constraint, and the historically correct answer to exactly this
  problem — eliminating the plugboard algebraically instead of searching it —
  is a crib-driven Bombe, which Phase 2's crib network was assembled to feed.
- BYQMZ (167 letters) is the only message long enough for the body-direct
  climb to find a 10-pair stecker on its own with good odds (28/32 known-key
  trials, 87.5%, when handed the true setting; 33/40 planted keys through the
  sweep's own parameterization). XFEDT (97 letters) recovered 12 of 32 (37.5%,
  95% interval 23–55%) when handed the true setting, and FKQLZ (107 letters)
  10 of 32 (31.3%, 18–49%), in `phase1-fkqlz-length-calibration-v1`. Both are
  below reliable, so neither is attacked alone; FKQLZ stays a companion. The
  earlier 1 of 8 at 97 letters was a low draw.
- The cited paper (Sullivan and Weierud 2005, footnote 42 to Figure 11) says
  Batch C is from a different radio network than the other 1941 messages, that
  all five of its messages are unbroken, and that its authors suspect "an
  Enigma machine with differently wired wheels". The repository did not record
  this. Every Phase 1 null and any Bombe assume wheels I–V as wired; the
  authors' own failure may equally reflect messages too few and too short for
  their method (the CryptoCellar page says the same of the messages it lists),
  so this is a reason for doubt about the standard reading, not evidence
  against it.

## Validation

- `python3 -m unittest discover -q`: 216 tests passed locally on 2026-10-06,
  with numpy installed; without it the five batched-climb tests skip. A test
  checks that `engine: auto` falls back to the reference climb and
  `engine: batched` fails loudly when numpy is missing.
- `python3 -m pip wheel . --no-deps --no-build-isolation`: wheel built. A clean
  virtual environment outside the checkout resolves its inputs from the
  installed share directory and its default outputs under the current working
  directory; `enigma-phase7` loads the corpus, both frequency tables and the
  Phase 6 and Phase 7 configurations before stopping at the conservation gate,
  `enigma-phase1-stecker` finds its shipped configurations and stops at its
  positive-control gate, and `enigma-phase1` and `enigma-phase2` complete. Each
  records `"source": "not_a_checkout"` with `"dirty": null`.
- Phase 1 stecker calibration, the complete indicator-coupled sweep, and the
  body-direct sweep are recorded in `artifacts/phase1-stecker-calibration-v1.json`,
  `artifacts/phase1-indicator-sweep-v1.json`, and
  `artifacts/phase1-body-direct-sweep-v1.json`. The fast kernel (`enigma_fast.py`)
  is checked against `enigma.py` on pseudorandom settings at the start of every
  run, and the fast n-gram scorer is checked against Phase 7's validated
  `PublishedNgramScorer` the same way. Both preflight checks and two
  preregistered known-key positive controls must pass before any target search
  runs; a failed check or control makes zero target-search calls.
- `artifacts/phase1-fkqlz-length-calibration-v1.json` (137 s single process, run
  from a clean tree at `03b8670`) is declared in `artifact_claims.json` like
  `phase1-stecker-calibration-v1` and is regenerated by CI. Run alone through
  `check_artifacts.py both`, drift and determinism pass and take about 8
  minutes here; CI-runner time was not measured, so flip it to `long_running`
  if the artifact job becomes too slow. Its copied stages match v1 on every
  declared claim path.
- `data/phase2/` holds the `phase2-crib-prior-v1` manifest, held-out plaintexts
  and result; `scripts/crib_prior_gates.py` regenerates the result file.
- `artifacts/phase1-end-to-end-power-v1.json` records the end-to-end power
  control (80 planted keys, 303 s on 18 workers). It is `long_running` in
  `artifact_claims.json` and its claim paths were checked against the
  artifact by hand. The tree was dirty when it ran (two untracked paths that
  the run does not import), which the artifact records.
- The two sweep artifacts are declared `long_running` in `artifact_claims.json`
  and checked for existence only in CI: the indicator sweep costs about 4
  minutes single-core and the body-direct sweep about 17 minutes wall-clock on
  18 cores (about 5.1 core-hours), more than a CI job should spend twice over
  per mode. Their code paths are covered by `tests/test_phase1_stecker.py` and
  by the calibration artifact, which CI does regenerate.
- Phase 5 conservation measurements, gate calibration and exclusions are
  recorded in `artifacts/phase5-model-triage.json` (schema v3).
- Gate calibration passes all five control plaintexts; worst control
  `p = 0.0947`, about 9.5x alpha.
- Corrected bounded artifacts: `artifacts/phase3-variant-smoke-v2.json`,
  `artifacts/phase4-joint-machine-smoke.v2.json`,
  `artifacts/phase6-qtxma-double-transposition-smoke.v2.json`, and
  `artifacts/phase7-qtxma-source-and-scorer.v2.json`. The v1 artifacts are
  retained as historical records; their positive-control verdicts and held-out
  readings are superseded.
- The Phase 6 and Phase 7 v2 artifacts are marked `superseded` in
  `artifact_claims.json`. They are checked for existence but no longer
  regenerated, because the pipeline now refuses those targets by design.
- CI runs the unit tests on Python 3.10 through 3.13, then two checks over the
  generated artifacts. Drift regenerates each artifact and fails the build when
  a value declared in `artifact_claims.json` changes, reporting an added or
  removed key as a warning instead. Determinism runs each experiment twice in
  one environment and requires the declared paths to agree.
- Every artifact that the current code can regenerate passes both checks; the
  two superseded and two long-running ones are checked for existence.

## Review of 2026-10-02: what is done

[The review](code-review-2026-10-02.md) lists five recommended steps.

1. Done: `enigma-phase1-stecker` reads its inputs from the share directory and
   writes to the working directory, with an installed smoke test, and Phase 1
   stecker artifacts record `git_dirty` (`edfa918`). Since superseded by the
   shared `code` block every phase now writes, phases 1 to 3 and 5 included.
2. Done: the sweep takes a ring rule and a right-ring axis, the runner reports
   exact key coverage, and the end-to-end power control is measured
   ([history](phase1-experiment-history.md#phase1-end-to-end-power-v1)). The
   coverage statements above are corrected to those figures.
3. Done: the optional batched numpy climb (`stecker_batch.py`, `climb.engine`
   = `reference`, `batched` or `auto`, `pip install .[fast]`) ends on the same
   plugboard after the same evaluation count as the reference climb on seeded
   samples, which the preflight checks whenever the engine is batched. It is
   9.1× faster in one process (16.9 against 153 ms per setting) and a full
   past-notch sweep is projected at about 20 hours with 9 to 10 workers
   ([measurements](phase1-experiment-history.md)). The sweep keeps a bounded
   top-k and streaming statistics per chunk, runs 1,560 chunks for a full sweep,
   and checkpoints to JSONL and resumes. Existing v1 configurations still run
   the reference climb.
4. Done: the preregistered full sweep (`phase1-body-direct-sweep-v2`) ran and
   is null; its power is now put at about 0.875 clean and 0.40 with one indel.
   The windowed-climb calibration followed (`phase1-windowed-climb-power-v1`)
   and its windowed sweep (`phase1-body-direct-sweep-v3`) ran and is null.
5. Answered 2026-10-06: `phase2-crib-prior-v1` ran on held-out traffic and the
   Bombe stays deferred, now on measured grounds. The evaluate split holds 2
   solved messages against the gate's 20 (G1), the cited paper places Batch C
   on a different network from the solved 1941 messages (G2), and even with a
   perfect Bombe the campaign lower bound is 0.106 against 0.29 (G3). See
   [Phase 2 history](phase2-experiment-history.md).

## Next

Do not enlarge the transposition width search. It is closed for QTXMA by
conservation, not by a failed search, and reopening it needs a reason to think
the plaintext layer is not German Army text.

Do not enlarge the Phase 1 indicator-coupled sweep or spend more time on
IC-based stecker screening. Both are now closed on measurement grounds, not
coverage grounds: the statistic and the hill-climb have zero power at a
ten-pair stecker regardless of how much of the space is searched.

Phase 1 next: calibrate the **split-point climb** that `phase1-middle-complete-power-v1`
selected. It is built (`stecker_split.py`): it searches the position of one dropped
or inserted letter inside every plugboard evaluation, and in the 10-worker sweep
it costs 2.89 times the windowed climb v3 used (about 49 host-hours projected for
a sweep, against 153 for the complete ring rule), after candidate blocking
halved a first measurement of 6.1. On 60 development draws at the true
setting it recovered 65% against 23% for the whole-message climb and 27% for the
windowed one, and 71% against 4% and 14% with the indel in the middle third. That is a stecker-stage figure.
`phase1-split-point-power-v1` is preregistered, not run (about 20 to 30
minutes): it reruns the control's draws and asks what the climb detects among the
keys both past-notch climbs miss, then which sweep pays more per host-hour at a
prior q = 0.2 on one dropped or inserted letter (unmeasured). Run it, then
`scripts/split_power.py`. The control found that the complete rule recovers
59.6% of the clean keys the past-notch climbs miss and the middle-third indels
only 20.3%, where an oracle that undoes the indel recovers 70.3%. The same run
puts v2's whole-message climb at 79.0% on clean draws and v3's windowed climb at
42.5% with one indel, below the 88.8% and 56.3% of the earlier 80-draw run, so the
two nulls multiply the odds of a standard reading by about 0.14 ungarbled and
0.48 with one indel, not 0.09 and 0.43. Both candidates assume wheels I to V as
wired, which the cited paper's authors doubt for Batch C.

A **crib-driven Bombe** would eliminate the plugboard algebraically through
crib-derived menus instead of searching it, the historically correct answer to
the rotor-setting enumeration this phase measured. It stays deferred, and a
crib prior for these messages cannot be quantified from what is published:
the cited pages hold ciphertext, the one page with solved plaintext gives 2
messages dated in the evaluation window, and the paper places Batch C on a
different network (`phase2-crib-prior-v1`, review finding P3). Phase 2's crib
network (`artifacts/phase2-network-cribs.json`) has nothing to feed it with.

Second: identify what produces QTXMA's restricted alphabet, starting with cheap
discriminators. Its length of 155 is odd, which argues against a pure bigram
cipher before any implementation work.

Third, unchanged: archival evidence about the procedure or about why QTXMA and
SZAEJ left the unbroken list.

Lower priority, and no longer on the QTXMA path: the Phase 6 and Phase 7 5×7
known-key control still fails, recovering the known plaintext rotated by one
position over 76 letters. The ragged-row filling convention at that length is
the thing to check. It is a defect in the transposition search machinery, which
conservation has made irrelevant to this corpus' target but would matter if
that machinery is reused.
