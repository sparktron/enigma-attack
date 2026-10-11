# Open items after the BYQMZ closure (2026-10-11)

A review, not an experiment: nothing was run beyond the letter counts in item 2,
and nothing is preregistered. It lists what is still open once the
standard-reading search of BYQMZ is closed (the decision record is in the
[Phase 1 history](phase1-experiment-history.md), in the closing entry of
2026-10-10), ranks it, and says what each item would cost. Sources are
[STATUS](STATUS.md) and the phase histories.

## Facts

- BYQMZ, under Enigma I, reflector B, wheels I to V as wired and ten pairs, has
  four null sweeps and a measured fault coverage. That path is closed.
- The cited paper's doubt about the wheel wiring for Batch C is untouched by any of
  it. A question to the authors was sent 2026-10-10 through the Crypto Cellar
  contact address. No reply is recorded.
- `phase2-crib-prior-v1` measured the crib-driven Bombe's prospects and deferred
  it on three gates: 2 solved messages in the evaluation split against 20
  needed (G1), Batch C on a different network from the solved 1941 messages
  (G2), and a campaign lower bound of 0.106 against 0.29 even with a perfect
  Bombe (G3).
- Letter counts, computed from `corpus.json` for this review (alphabetic
  characters only), with the probability of at least that many absent letters if
  the letters were independent and uniform:

| message | letters | absent letters | IC | probability under uniform |
|---|---|---|---|---|
| QTXMA | 155 | D F G U (4) | 0.0577 | 8.4 × 10⁻⁸ |
| SZAEJ | 51 | D F I L Q R U (7) | 0.0525 | 0.023 |
| BYQMZ | 166 | none | 0.0395 | 1 |
| FKQLZ | 107 | J (1) | 0.0326 | 0.33 |
| XFEDT | 97 | J (1) | 0.0329 | 0.46 |

  QTXMA and SZAEJ share the absent letters D, F and U. Given QTXMA's absences,
  the chance that a uniform 51-letter message also lacks those three is about
  0.002 ((25/26)^51 cubed).

## Interpretation (inference)

- QTXMA's absence of four letters in 155 is far outside what near-uniform
  output gives, so its letters do not look like Enigma output; the other three
  messages' counts are unremarkable. Enigma output is not exactly iid uniform, but
  its deviation (no letter encrypts to itself) does not empty letters out. SZAEJ is
  milder (p = 0.023 alone) and it shares QTXMA's three absences. That agrees with
  the existing finding that QTXMA has a restricted alphabet and does not mean the
  two messages share a cause. The "unexplained coincidence" in STATUS is a
  coincidence of about 0.002 under a uniform null, which is small, not zero.
- So the unresolved set splits: BYQMZ, FKQLZ and XFEDT have Enigma-like letter
  statistics and have been searched, and QTXMA and SZAEJ do not and need a
  different explanation.

## Open items, ranked

1. **The wheel-wiring question.** Blocked on the authors' reply, which only the
   maintainer can chase. No compute until it names a wiring or machine. A
   sourced wiring costs about 2 GPU hours per wheel set or reflector with the
   existing split-point climb.
2. **What produces QTXMA's and SZAEJ's restricted alphabets.** This is the next
   item in STATUS ("Second"), costs no compute for the first step, and is where
   the letter counts above point. The constraints already recorded stand: the
   length 155 is odd, which argues against a pure bigram cipher, and adding a
   family to `cipher-families.json` needs real provenance, not a guess. A first
   step would be searching for sourced systems with a reduced alphabet in the
   2003 to 2005 literature, which is archival work.
3. **Archival evidence** on the procedure and on why QTXMA and SZAEJ left the
   unbroken list. Maintainer-side, like item 1, and the same email could have
   asked it. No compute.
4. **The 5×7 known-key control of Phase 6 and Phase 7** still fails, recovering
   the known plaintext rotated by one position over 76 letters. The thing to
   check is the ragged-row filling convention at that length. It is a defect in
   the transposition search machinery, which conservation has made irrelevant to
   this corpus, and it matters only if that machinery is reused. A few hours of
   engineering with a definite deliverable.
5. **The crib-driven Bombe** stays deferred. Reopen it only with a solved
   plaintext source from the target network, which G1 and G2 say does not
   exist in what is published.
6. **FKQLZ or XFEDT searched alone** is not recommended: handed the true
   setting, the climb recovers 31% (FKQLZ) and 37.5% (XFEDT) of keys, so a sweep
   would have little power.

## Recommendation (inference)

Nothing here is worth building before information arrives, so do not start a new
sweep. The best use of the interim is item 4 if the transposition machinery is
worth keeping correct, and otherwise to wait for items 1 and 3. If the authors
reply with a wiring, item 1 becomes a preregistered sweep with a power control
first, as for the standard reading. If they reply that the wheels were never in
doubt, items 1 and 3 close and item 2 is what is left.
