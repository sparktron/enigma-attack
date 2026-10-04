# Phase 2 crib experiment history

Phase 2 assembled a crib catalogue (`cribs.json`) and a network grouping
([research](phase2-research.md),
[artifact](../artifacts/phase2-network-cribs.json)). The experiments below
ask whether those cribs can feed a Bombe against the 1941-09-30 messages.

---

## phase2-crib-prior-v1 (preregistered)

Status: preregistered 2026-10-04. Nothing has been run beyond counting the
in-repository development set. This answers review finding P3
([review](code-review-2026-10-02.md)).

Question: is a crib-driven Bombe worth building for BYQMZ, FKQLZ and XFEDT,
compared with another crib-free body-direct sweep?

Configuration:
[experiments/phase2-crib-prior-v1/config.json](../experiments/phase2-crib-prior-v1/config.json).
Counts: `python3 scripts/count_crib_occurrences.py`.

### What the repository holds (fact)

The only solved 1941 Army plaintext in the repository is the five messages in
`data/phase5/army-plaintext-controls.json`, from CryptoCellar's modern
breaking page: 275 letters, 36 to 76 letters each. The repository does not
record their network. The long Army-style plaintext in the Phase 1 configs is
constructed, so it is excluded. The 1930, 1938 and ALQFI texts behind most of
the catalogue are present only as extracted cribs.

| crib (cribs.json) | in 5 solved messages | where |
|---|---:|---|
| the 13 enabled by default, as written | 0 each | — |
| `HARTJENSTEINX` as written | 0 | — |
| `HARTJENSTEIN` (trailing X dropped) | 2 | sign-off, the last 12 letters both times |
| `MELDUNG` (speculation, disabled) | 1 | other (inside ABENDMELDUNGEN) |
| the 2 metadata-derived (disabled) | 0 each | — |

Every message ends in a name or unit token (HARTJENSTEIN twice; ROEMEINSBERTA,
STEINECKE, SCHNEIDDR once each), and 1 of 5 has a trailing X. No opening word
recurs, and none of the five has an address group. Held out one message at a
time, "predict the token seen at least twice" scores 0 of 5. "Predict every
training sign-off" scores 2 of 5: 0.40, with an exact 95% interval of 0.05 to
0.85.

### Reading (inference, then speculation)

- Inference: the sign-off is the only crib class that repeats. It is also the
  best class for a Bombe: at most two placements per message, and unaffected
  by a dropped or inserted letter earlier in the message.
- Speculation: that any Batch C message ends in a name from this set. Nothing
  links the five messages' network to Batch C. The three targets have three
  addressees and at least two operators.
- Not verified: the cited held-out sources (CryptoCellar's 1941 Army messages,
  key E and BGAC pages). The preregistration container's network policy
  refused them on 2026-10-04.

### Method and decision rule (fixed now)

The held-out split is chronological, and it excludes the five messages above,
which were read while this was written. It trains on solved messages dated up
to 1941-09-15 and evaluates on messages dated 16 September to 31 October. The
prior gives each message a list of (crib, offset, p), and a placement that
fails no-self-encipherment gets zero. The probability the gates use is
measured directly on the held-out messages, as the fraction in which at least
one listed crib sits at a listed offset, rather than summed from per-crib
rates. The three target messages are combined with a bound that holds however
they are correlated: the best single message, never 1 − Π(1 − D_m). Address
blocks are annotated from each source's layout before counting, never guessed
from spelling. The Bombe is preferred only if all four gates pass:

- G1: the evaluate split holds at least 20 messages.
- G2: a cited source links that network to Batch C.
- G3: the campaign lower bound D_L = max over messages of D_m,L is at least
  0.29, so that a Bombe null is at least as informative as v3's (likelihood
  ratio 0.71).
- G4: detection per host-hour is at least the body-direct reference (0.013 per
  host-hour, v3 conditional on v2's null; v2 was 0.825 in 16.4 h).

### Verdict today

**No crib prior can be estimated yet, so the Bombe is not preferred.** On the
development set G1 and G2 fail, and G3 fails too even if G2 is waived and the
Bombe is assumed perfect: D_L = 0.169 against 0.29. The next
step is to read the held-out sources from a host that can reach them and run
the frozen procedure. Until then the crib-free route stays first, as in the
review's order.
