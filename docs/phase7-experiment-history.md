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

Status: completed 2026-09-23; two of three known-key controls passed, the third
failed, and the QTXMA target search was therefore not run. Supersedes the v1
reading of the control, not its source audit or scorer validation.

Revision cause: the v1 run reported 6.1% positive-control recovery accuracy and
gated off the target search. Two independent defects produced that reading, and
both are fixed here.

The first is the selection objective. v1 selected keys on a 75% training prefix.
Ranking the complete 2,880-key control space on that objective puts the true key
fifth, and the key it prefers reads out the same text displaced by four
positions. Scoring the full candidate instead puts the true key first.

The second is the acceptance metric. The recovered v1 plaintext was the control
plaintext rotated by four characters, agreeing at 97.3% at that offset. The
148-letter control is an exact multiple of its 4-wide first stage, so an
alternative second-stage key reads out the same text shifted by one whole row.
Strict positional agreement scores such a recovery as a total failure. The
recorded v1 conclusion — that the scorer could not rank the correct key — was
therefore an artifact of both defects together.

Changes from v1:

- Key selection scores the full candidate plaintext rather than a training
  prefix, and the candidate suffix is descriptive rather than a holdout, because
  different keys move source letters across its boundary. The target acceptance
  rule is a matched complete-search shuffle null.
- `plaintext_agreement` reports exact positional agreement, the best agreement
  over the rotations the stage geometry can actually produce, and the offset
  achieving it. Credit is restricted to multiples of a stage width that divides
  the message length; a control with no such width admits offset zero alone and
  is held to exact recovery. The best agreement over every shift is still
  reported, but only as a diagnostic that cannot pass a control, so an
  unexplained near-match stays visible.

  The first version of this metric credited any cyclic shift, which would have
  let the ragged control pass on a shift no key could produce — defeating the
  exactness that control exists to enforce. The Codex review bot raised this on
  pull request #6 and the restriction was added before the result was recorded.
- Exact plaintext recovery and exact key recovery are recorded separately from
  the rotation-aware verdict, so a control passed on a reachable rotation stays
  distinguishable from one that landed on the known key itself.
- A third control, `ragged-both-stages`, uses a 133-letter plaintext. 133 is a
  multiple of neither 4 nor 5, so both stages have ragged final rows and no
  whole-row rotation is available. It separates the rotation artifact from
  genuine scorer or optimizer weakness.
- Phase 7 adds its controls to those the Phase 6 configuration already declares
  rather than replacing them, and the control logic lives in `phase6.py` alone;
  the two runners previously carried separate copies.
- Every configured control is evaluated even after one fails. Stopping at the
  first failure would have hidden the ragged control's result, which is the
  evidence that separates a search failure from a metric artifact.

Hypothesis: source and scorer checks, plus exact known-key recovery on controls
that include one whose length is a multiple of neither stage width, permit a
calibrated full-text transposition search of QTXMA.

Refuted by: source or scorer checks fail, a known-key control fails recovery
under the rotation-aware accuracy rule, or the target maximum fails matched
complete-search calibration. The exact configuration was recorded in
[config.json](../experiments/phase7-qtxma-source-and-scorer-v2/config.json)
before the experiment. Three target seeds were specified: 20260921, 20260922,
and 20260923. None was used, because the control gate closed.

Code: the merge of `claude/phase7-rotation-aware-controls` into `master`.
Python 3.10.12, serial execution, about 2 s. The artifact records the exact
`phase6.py` and `phase7.py` hashes and the commit it was produced from.

Raw result: [Phase 7 v2 artifact](../artifacts/phase7-qtxma-source-and-scorer.v2.json).

Observed:

- Source audit and scorer validation reproduced v1 exactly: the 31
  non-designator groups give the 155-letter solver input, and all five
  published plaintexts scored above all 16 shuffles, by +0.955323 to +1.380316
  score per letter.
- Primary control, 148 letters over 4×5, exhaustive over 2,880 keys: exact
  agreement 1.000000, both stage keys recovered exactly, full-text delta
  +1.916222 per letter. The known key ranks first in the complete control
  space with edit distance zero. Its length is a multiple of the 4-wide first
  stage, so rotations by multiples of four were admissible and none was needed.
  Passed.
- Ragged control, 133 letters over 4×5, exhaustive over 2,880 keys: exact
  agreement 1.000000, both stage keys recovered exactly. Its geometry admits a
  single offset, zero, so it was held to exact recovery and met it. Passed.
- Independent solved-message control, 76 letters over 5×7, simulated annealing
  over 12,008 evaluations: exact agreement 0.052632. 76 is a multiple of
  neither 5 nor 7, so no rotation is admissible and the rotation-aware verdict
  equals the exact one. Failed.
- That failure is not a scrambled miss. The same recovery agrees with the known
  plaintext completely — 1.000000 — at an offset of 75 of its 76 positions,
  which is a rotation by one character. The second-stage key was recovered
  exactly and only the first-stage order differs. No stage width at this length
  can produce that shift, so it is reported as a diagnostic and given no credit.
- The control gate therefore skipped the QTXMA target search and the
  complete-search null calibration. No seed result and no calibration appear in
  the artifact.

Interpretation (inference): the scorer and the bounded optimizer do recover
known double transpositions exactly, including one with no rotation degeneracy
and no ragged-row shortcut, at 148 and 133 letters. The v1 scorer-weakness
conclusion is withdrawn. The 5×7 control's whole-message one-character rotation
is the signature of a row-filling disagreement between the control's construction
and the search's untransposition at a length that divides neither width, not of
a scorer that cannot rank the key: it ranked the second-stage key exactly.
Until that is resolved, no QTXMA search under this machinery would be
interpretable, which is why the gate is where it is.

Boundary: this says nothing about whether QTXMA is a double transposition. The
preregistered widths remain untested against the target under the corrected
objective, because the search never ran. Two of the three controls are
constructed plaintexts rather than authentic held-out Army traffic, so they test
the machinery and not corpus representativeness. The published counts' training
messages are still not enumerated, so overlap with the five validation
plaintexts remains unexcluded.

Next decision: resolve the 5×7 control failure before any QTXMA target run.
The one-character rotation points at the ragged-row filling convention for a
76-letter message over widths 5 and 7; comparing the control's construction with
the search's untransposition at that length is the first check. Then validate
the search on further independent known-key messages at the target lengths and
width branches, including ragged rows, and only then run the configured
complete-search null calibration.
