# Phase 7 source and scorer experiment history

## phase7-qtxma-source-and-scorer-v1

Status: completed 2026-09-22; positive control failed, so no target search was
accepted or retained in the final artifact.

Hypothesis: published 1941 Army plaintext bigram and trigram counts will
discriminate separately published solved plaintexts from frequency-preserving
shuffles, recover a known double transposition, and then give QTXMA a held-out
gain beyond a monoalphabetic-substitution control over six preregistered width
pairs.

Refuted by: source inconsistency, fewer than four of five known plaintexts
scoring above all 16 shuffles, failure of the true-transposition control, or
failure of the Phase 6 held-out and substitution-control rules. The exact
configuration was recorded in
[config.json](../experiments/phase7-qtxma-source-and-scorer-v1/config.json)
before the experiment. Three target seeds were specified: 20260921, 20260922,
and 20260923. None was used in the final run because the control failed.

Sources: the [QTXMA transcription](https://cryptocellar.org/bgac/ultimate-enigma.html)
and [original form](https://cryptocellar.org/bgac/spruch/29091941-006-out.pdf),
the published [1941 Army frequency counts](https://cryptocellar.org/bgac/key-of-e.html),
and [solved-message plaintexts](https://cryptocellar.org/enigma/enigma-modern-breaking.html).
The original-form PDF was visually inspected. Its SHA-256, the source groups,
and the frequency-file hashes are recorded in the config or raw result.

Code: commit `876e24a398434f9f795f663978ed92edb3fe2a70` with a dirty tree;
the raw result records the exact `phase6.py` and `phase7.py` hashes. Python
3.10.12, serial execution. This uncommitted code state is less reproducible
than a clean commit; the file hashes preserve the tested version.

Baseline: [Phase 6](../artifacts/phase6-qtxma-double-transposition-smoke.json)
recovered its synthetic transposition control exactly, but QTXMA failed with
median held-out delta -0.026923077 under its bootstrap adjacency scorer.

Raw result: [Phase 7 artifact](../artifacts/phase7-qtxma-source-and-scorer.json).

Observed:

- The original form has 32 groups of five, including the `QTXMA` designator.
  Its remaining 31 groups concatenate to exactly the existing 155-letter
  solver input. The form audit found no new character or body boundary.
- All five published solved plaintexts scored above all 16 deterministic
  frequency-preserving shuffles under the new scorer. Margins over each
  message's best shuffle ranged from +0.955323 to +1.380316 score per letter.
- The true double-transposition control's recovered plaintext accuracy was
  0.060811, below the preregistered 0.95 requirement. Its held-out score rose
  by +2.455123 per letter, illustrating that a high score alone is not
  reliable recovery. The QTXMA target search was therefore skipped.

Interpretation (inference): the published counts distinguish ordinary Army
plaintext from a random ordering of the same letters, but they do not yet
rank the correct transposition key highly enough under this search and
control. The source grouping preserves the existing target string, so there
is no source-based reason to reinterpret the Phase 6 search input.

Boundary: the frequency count training messages are not enumerated by the
publisher, so overlap with the five validation messages cannot be excluded.
The test does not rule out double transposition for QTXMA. An early development
run exposed that the reused Phase 6 runner continued to search QTXMA even
after a failed positive control; that result was discarded, and Phase 7 now
gates target search on the positive control. No target claim uses that run.

Next decision: obtain additional independently sourced Army plaintext and
validate a stronger scorer against authentic held-out messages and several
known transposition keys before another QTXMA width search. Archival procedure
or status evidence could redirect this branch earlier.

## phase7-qtxma-source-and-scorer-v2

Status: completed 2026-09-23; both positive controls passed, the QTXMA search
ran, and the hypothesis was refuted on the held-out and substitution-control
rules. Supersedes the v1 reading of the control, not its source audit or
scorer validation.

Revision cause: the v1 run reported 6.1% positive-control recovery accuracy and
gated off the target search. Re-reading the v1 artifact showed the recovered
plaintext was the control plaintext rotated by four characters, agreeing at
97.3% at that offset. The 148-letter control is an exact multiple of its 4-wide
first stage, so an alternative second-stage key reads out the same text shifted
by one whole row. The v1 acceptance metric was strict positional agreement,
which scores such a recovery as a total failure. The recorded v1 conclusion —
that the scorer could not rank the correct key — was therefore a metric
artifact.

Changes from v1:

- `plaintext_agreement` reports exact positional agreement, the best agreement
  over all cyclic rotations, and the offset achieving it. The positive-control
  gate uses the rotation-aware number; the exact number is retained so a
  rotated recovery stays distinguishable from an exact one.
- A second positive control, `ragged-both-stages`, uses a 133-letter plaintext.
  133 is a multiple of neither 4 nor 5, so both stages have ragged final rows
  and no whole-row rotation is available. It separates the rotation artifact
  from genuine scorer or optimizer weakness.
- `evaluate_positive_control` is shared by `phase6.py` and `phase7.py`, which
  previously carried two copies of the control logic.

Hypothesis: with a rotation-aware recovery metric and a control that admits no
rotation, the published 1941 Army n-gram scorer will recover both known
transpositions and then give QTXMA a held-out gain beyond a substitution
control over six preregistered width pairs.

Code: commit `3b384f1b7febb5df00147753c10989091a4b8b2f` on branch
`claude/phase7-rotation-aware-controls`, clean tree. This is the first Phase 7
result produced from a non-dirty checkout; v1 and every earlier phase artifact
records `dirty: true`. Python 3.10.12, serial execution, about 15 s.

Determinism: the experiment was run three times — twice from a dirty tree and
once from the clean checkout above. Every scientific field was identical across
all three: both control agreements and keys, all three seed keys and
plaintexts, every training and held-out delta, the substitution control, the
scorer validation margins, and the source audit hashes. Only timestamps,
runtime, the recorded output path, and the code-provenance block differed. The
artifact's `parallel_workers: 1` serial-execution claim is now tested rather
than asserted.

Raw result: [Phase 7 v2 artifact](../artifacts/phase7-qtxma-source-and-scorer-v2.json).

Observed:

- Source audit and scorer validation reproduced v1 exactly: the 31 non-designator
  groups give the 155-letter solver input, and all five published plaintexts
  scored above all 16 shuffles.
- Primary control: exact agreement 0.060811, best-over-rotations 0.972973 at
  offset 4, held-out delta +2.455123. Passed. The first-stage key was recovered
  exactly; only the second-stage order differs.
- Ragged control: exact agreement 1.000000 at offset 0, both stage keys
  recovered exactly, held-out delta +1.474935. Passed. No rotation was
  available to it.
- QTXMA, three seeds: training gains of +0.643909, +0.622357 and +0.630738 per
  letter, against held-out deltas of -0.830167, -0.749779 and -0.760904. Zero
  seeds passed. The monoalphabetic substitution control scored +0.038152, so
  the median margin over it was -0.799056. The three seeds selected three
  different 5x7 key pairs and their plaintexts are incoherent.

Interpretation (inference): the scorer and the bounded optimizer do recover
known double transpositions, including one with no rotation degeneracy and no
ragged-row shortcut. The v1 scorer-weakness conclusion is withdrawn. Applied to
QTXMA under the same machinery, the search buys a large training-prefix gain
and pays for it on the untouched suffix, losing to a substitution control that
cannot be a transposition at all. That is the signature of fitting noise, and
it is now a clean negative result rather than an uninterpretable one.

Boundary: this refutes the preregistered widths and this scorer for QTXMA. It
does not exclude double transposition with other widths, a different ragged-row
convention, nulls, or a transposition applied to something other than the
literal 155-letter body. Both positive controls are constructed plaintexts, not
authentic held-out Army traffic, so they test the machinery and not corpus
representativeness. The published counts' training messages are still not
enumerated, so overlap with the five validation plaintexts remains unexcluded.

Next decision: do not enlarge the width search from training gains. The
transposition branch for QTXMA is now bounded by a trustworthy negative, so
the higher-value moves are archival — procedure or message-status evidence —
or a separately sourced held-out Army plaintext model that would let the
substitution control and the target be compared on authentic text.
