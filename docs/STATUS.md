# Project status

Updated: 2026-09-23

## Current state

Phases 1-6 provide bounded, reproducible baselines and negative-result
evidence. Phase 7 recovered the QTXMA source grouping and introduced a
published 1941 Army n-gram scorer. The source grouping yields exactly the
existing 155-letter ciphertext.

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

No ciphertext break has been accepted. See
[Phase 7 history](phase7-experiment-history.md) and its linked raw artifacts.

## Active work and known problems

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
- The published-count scorer is validated for recovering known double
  transpositions; the earlier claim that it could not is withdrawn.
- The messages used to compile the published n-gram counts are not enumerated,
  so overlap with the solved-message validation set cannot be ruled out. The
  same caveat applies to the unigram reference the gate derives from them.
- Phase 1 remains the largest unclosed gap. Its certificate records 120 daily
  keys and 300 message decryptions. Rotor orders against meaningful ring
  settings is about 40,560 daily keys per date, roughly 40 seconds on the
  bundled simulator, and stecker hill-climbing is not implemented at all.
  BYQMZ, FKQLZ and XFEDT are flat, full-alphabet, Enigma-compatible and have
  never actually been attacked.

## Validation state

- `python3 -m unittest discover -q`: 75 tests passed locally on 2026-09-23.
- Phase 5 conservation measurements, gate calibration and exclusions are
  recorded in `artifacts/phase5-model-triage.json` (schema v3).
- Gate calibration passes all five control plaintexts; worst control
  `p = 0.0947`, about 9.5x alpha.
- `artifacts/phase7-qtxma-source-and-scorer.json` is retained as the v1 record;
  its positive-control verdict is superseded.
- The Phase 6 and Phase 7 v2 artifacts are marked `superseded` in
  `artifact_claims.json`. They are checked for existence but no longer
  regenerated, because the pipeline now refuses those targets by design.
- CI runs the unit tests on Python 3.10 through 3.13, then two checks over the
  generated artifacts. Drift regenerates each artifact and fails the build when
  a value declared in `artifact_claims.json` changes, reporting an added or
  removed key as a warning instead. Determinism runs each experiment twice in
  one environment and requires the declared paths to agree.

## Next

Do not enlarge the transposition width search. It is closed for QTXMA by
conservation, not by a failed search, and reopening it needs a reason to think
the plaintext layer is not German Army text.

The highest-value move is now Phase 1, which has never been run at scale. The
method is the one this repository already cites: an unsteckered sweep over
rotor orders and ring settings scored by IC, top candidates retained, then
stecker hill-climbing with the validated n-gram scorer. Both indicator
orderings should be tried; `phase1.py` currently fixes the Grundstellung as the
first trigram.

Second: identify what produces QTXMA's restricted alphabet, starting with cheap
discriminators. Its length of 155 is odd, which argues against a pure bigram
cipher before any implementation work.

Third, unchanged: archival evidence about the procedure or about why QTXMA and
SZAEJ left the unbroken list.
