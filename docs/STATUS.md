# Project status

Updated: 2026-09-27

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
index-of-coincidence sweep, **has no detection power at a ten-pair stecker**,
at any length up to 800 letters, and that the indicator-coupled formulation
`phase1.py` implies **cannot be hill-climbed** because the plugboard sits
inside the indicator machine as well as the body. It also found that a
body-direct stecker climb (start position searched directly, indicator used
only as an independent check) recovers a known ten-pair plugboard and its exact
plaintext on every trial at 167 letters, once an index-of-coincidence phase
runs ahead of the n-gram phase. The complete indicator-coupled search
(2,109,120 daily keys, both indicator orderings) and a declared 0.15% slice of
the body-direct space on BYQMZ were both run to completion and found nothing,
exactly as the calibration predicted. See
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
  default outputs under the current working directory.
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
  pure Python; only 0.15% of it has been searched. Pure-Python speed is now the
  binding constraint, and the historically correct answer to exactly this
  problem — eliminating the plugboard algebraically instead of searching it —
  is a crib-driven Bombe, which Phase 2's crib network was assembled to feed.
- BYQMZ (167 letters) is the only message long enough for the body-direct
  climb to reliably find a 10-pair stecker on its own (8/8 known-key trials).
  XFEDT (97 letters) is below that threshold (1/8) and should not be attacked
  alone. FKQLZ (107 letters) was not measured directly.

## Validation

- `python3 -m unittest discover -q`: 125 tests passed locally on 2026-09-27.
- `python3 -m pip wheel . --no-deps --no-build-isolation`: wheel built. A clean
  virtual environment outside the checkout resolves its inputs from the
  installed share directory and its default outputs under the current working
  directory; `enigma-phase7` loads the corpus, both frequency tables and the
  Phase 6 and Phase 7 configurations before stopping at the conservation gate.
- Phase 1 stecker calibration, the complete indicator-coupled sweep, and the
  body-direct sweep are recorded in `artifacts/phase1-stecker-calibration-v1.json`,
  `artifacts/phase1-indicator-sweep-v1.json`, and
  `artifacts/phase1-body-direct-sweep-v1.json`. The fast kernel (`enigma_fast.py`)
  is checked against `enigma.py` on pseudorandom settings at the start of every
  run, and the fast n-gram scorer is checked against Phase 7's validated
  `PublishedNgramScorer` the same way. Both preflight checks and two
  preregistered known-key positive controls must pass before any target search
  runs; a failed check or control makes zero target-search calls.
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

## Next

Do not enlarge the transposition width search. It is closed for QTXMA by
conservation, not by a failed search, and reopening it needs a reason to think
the plaintext layer is not German Army text.

Do not enlarge the Phase 1 indicator-coupled sweep or spend more time on
IC-based stecker screening. Both are now closed on measurement grounds, not
coverage grounds: the statistic and the hill-climb have zero power at a
ten-pair stecker regardless of how much of the space is searched.

The highest-value move is now a **crib-driven Bombe** for Phase 1: eliminate
the plugboard algebraically through crib-derived menus instead of searching it,
which is the historically correct answer to exactly the bottleneck this phase
measured (rotor-setting enumeration, not stecker recovery). Phase 2's crib
network (`artifacts/phase2-network-cribs.json`) exists to feed it.

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
