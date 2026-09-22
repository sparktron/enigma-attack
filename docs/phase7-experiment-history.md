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
