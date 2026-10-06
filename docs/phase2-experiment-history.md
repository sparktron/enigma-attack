# Phase 2 crib experiment history

Phase 2 assembled a crib catalogue (`cribs.json`) and a network grouping
([research](phase2-research.md),
[artifact](../artifacts/phase2-network-cribs.json)). The experiments below
ask whether those cribs can feed a Bombe against the 1941-09-30 messages.

---

## phase2-crib-prior-v1 (preregistered)

Status: preregistered 2026-10-04; **run 2026-10-06, hypothesis refuted**
([result below](#result-run-2026-10-06)). This answers review finding P3
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

### Verdict today (2026-10-04, superseded by the result below)

**No crib prior can be estimated yet, so the Bombe is not preferred.** On the
development set G1 and G2 fail, and G3 fails too even if G2 is waived and the
Bombe is assumed perfect: D_L = 0.169 against 0.29. The next
step is to read the held-out sources from a host that can reach them and run
the frozen procedure. Until then the crib-free route stays first, as in the
review's order.

---

### Result (run 2026-10-06)

Status: hypothesis **refuted**. G1, G2 and G3 fail and G4 is not evaluated. The
verdict is both "too sparse to estimate" and "no network link", and the Bombe
is not preferred. Predictions: one held, one not applicable, one held
numerically but uninformative.

Files, in commit order: [held-out-manifest.json](../data/phase2/held-out-manifest.json)
(committed alone, before any plaintext was read),
[held-out-plaintexts.json](../data/phase2/held-out-plaintexts.json),
[crib-prior-v1-result.json](../data/phase2/crib-prior-v1-result.json),
`scripts/crib_prior_gates.py` and its tests. The configuration was not edited.

#### What was fetched (fact)

| source | retrieved (UTC) | bytes | SHA-256 | holds |
|---|---|---:|---|---|
| `www.cryptocellar.org/bgac/g-army-messages.html` | 2026-10-06 05:06:37 | 28,242 | `0889dbb4…8e31f8` | ciphertext of 30 messages in 5-letter groups, 22 June to 3 October 1941, headers with callsigns; some tagged "Broken"; **no plaintext**. Includes BYQMZ, FKQLZ and XFEDT. |
| `cryptocellar.org/bgac/key-of-e.html` | 2026-10-06 05:06:37 | 6,742 | `d4312134…a8011` | six undated ciphertext challenge messages; **no plaintext** |
| `cryptocellar.org/pubs/bgac.pdf` | 2026-10-06 05:06:39 | 6,089,311 | `46baf5ff…9eb608` | Sullivan and Weierud 2005. Worked examples with plaintext fragments from July and August only, none read or transcribed; a message-count table |
| *added:* `cryptocellar.org/enigma/enigma-modern-breaking.html` | 2026-10-06 05:08:09 | 32,977 | `175a73cd…72c5a` | 13 solved messages with raw, transcribed, emended and translated plaintext |

All four returned HTTP 200 with no redirect. None had moved. The
preregistration container could not reach them; this host could.

Every full hash is in the manifest.

#### Deviation from the preregistration

The three listed sources hold ciphertext, not solved plaintext, which the
configuration had supposed ("transcriptions and solved plaintext"). Before
reading any plaintext I added the page the five development messages came from,
and recorded that in the manifest as a deviation. It lists 13 solved messages.
Five are the development set and are excluded. Eight are held out: six dated 8
July to 27 August and two dated 1 October. From the three listed sources alone
the solved-message count is zero, which fails G1 by a larger margin. The
manifest was committed with this inventory before the plaintext file existed.

The raw plaintext was extracted by script and checked by reproducing all five
development strings exactly. The candidate list was generated by script from the
train split only; it came out empty of recurring tokens, so the plaintext of
both evaluate messages was visible to me when it was written, but nothing in it
depends on them.

#### Counts (fact)

| | messages | letters | with address annotation |
|---|---:|---:|---:|
| train (on or before 1941-09-15) | 6 | 540 | 1 |
| evaluate (1941-09-16 to 1941-10-31) | 2 | 46 | 0 |
| development (excluded) | 5 | 275 | 0 |

- Candidates from the train split: no token recurs in two training messages in
  the opening, address or sign-off class, so the list is the 16 catalogued
  cribs only. One training message (233) carries three unrecorded letters, one
  (71) is truncated and gives no sign-off, and one (25) has an address block.
- Catalogued cribs in the train split: 0 of 6, none of the 16 as written or
  without a trailing X. HARTJENSTEIN, 0 of 6.
- Catalogued cribs in the evaluate split: only MELDUNG (`generic_meldung`,
  disabled, speculation) occurs, in 1 of 2, inside MORGENMELDUNGENTFAELCT, class
  other. The 13 enabled cribs occur in 0 of 2. HARTJENSTEIN, 0 of 2. The other
  message spells it ZWISNENMELDCNGENTFAELLTX, with two garbled letters.
- `scripts/count_crib_occurrences.py` run as a command on each split gives
  output identical to the counts `crib_prior_gates.py` embeds.
- Evaluate restricted to messages sharing a callsign, frequency or operator
  with Batch C: **not possible**. The source gives no callsign, frequency or
  operator for any held-out message, so `callsigns` and `network` are null.

Union rate u on the evaluate split, as the configuration defines it (every
catalogued crib at the opening, sign-off, address and other placements the prior
lists):

| listing | messages hit | u | one-sided 80% lower bound | exact 95% interval |
|---|---:|---:|---:|---|
| 16 catalogued cribs, all placements | 1 of 2 | 0.50 | 0.106 | [0.013, 0.987] |
| the same, excluding "other" placements | 0 of 2 | 0.00 | 0.000 | [0.000, 0.842] |
| the 13 enabled cribs only | 0 of 2 | 0.00 | 0.000 | [0.000, 0.842] |

#### Predictions

| id | prediction | result | |
|---|---|---|---|
| too-sparse (decides) | fewer than 20 solved evaluate messages from Batch C or a linked network, so G1 or G2 fails | 2 messages (0 from the listed sources); the paper places Batch C elsewhere | **held** |
| sign-off-is-the-only-repeating-class | if G1 passes, no other token or crib reaches q_L80 of 0.10 | G1 did not pass | not applicable |
| catalogued-cribs-absent | each of the 13 enabled cribs occurs in under 5% of evaluate messages | 0 of 2 each | held, uninformative: the 95% upper bound for 0 of 2 is 84% |

#### Gates (fact)

- **G1** (at least 20 solved evaluate messages): **fails**, 2.
- **G2** (t established by a cited source): **fails.** The cited paper's
  footnote 42 to Figure 11 says Batch C holds messages "from a different radio
  network than the other 1941 messages", and its table counts 5 Batch C
  Enigma messages, 577 letters, all 5 unbroken. No solved message belongs to
  Batch C, so t is not 1; the source argues against it. This gate was set by
  hand from reading the paper, not computed.
- **G3** (D_L at least 0.29, with r = 1): **fails.** D_L = 0.106 under the most
  generous reading of the table above and 0 under the other two. With 2
  messages this says little about cribs and much about sample size: even 2 of 2
  would give only 0.447.
- **G4**: not evaluated; no Bombe exists to time.

Verdict: **too sparse to estimate** (G1) and **no network link** (G2). The Bombe
is not preferred. The next crib-free body-direct step stays first, as in the
review's order.

#### Exploratory, not preregistered

Strings counted across all 13 solved messages in the repository (8 held out, 5
development), after the result above was fixed:

- ROEMEINSBERTA (the Ib staff section as addressee): 3 of 13, in messages 128
  and 203 (July) and 30 (22 August, the sign-off). 0 of 2 in the evaluate
  split.
- HARTJENSTEIN: 2 of 13, both development messages (2 and 14 September); 0 of
  8 held out.
- A report-cancelled formula: MELDUNG in 2 of 13, ENTFAEL in 2 of 13. The two
  1 October messages are both "morning/intermediate report cancelled".
- The two 1 October messages share one key-sheet line, the same wheel order,
  rings, start and Stecker, so they are one day's key and not two independent
  draws.

#### Interpretation (inference)

- The held-out check could not be run as designed, for a reason a better
  preregistration could not have known without reading the pages: the public
  1941 Army material is overwhelmingly ciphertext. The solved plaintext
  anyone has published is the 13 messages on the modern-breaking page, of which
  2 are in the evaluation window.
- No sign-off name recurs across the held-out messages. HARTJENSTEIN, which
  ended 2 of the 5 development messages, ends 0 of 8 held-out ones. That is the
  leave-one-out result the configuration reported (0 of 5 for the single-crib
  rule) turning up again, on 8 messages from a wider period. It is an
  exploratory observation, and with 8 messages it cannot show the name is rare.
- The short formulaic messages on the evaluate side are not like the targets.
  They run 22 to 24 letters; BYQMZ, FKQLZ and XFEDT are 167, 107 and 97.
- The footnote also bears on Phase 1, and is recorded in
  [STATUS](STATUS.md): its authors suspect differently wired wheels for Batch C.
  Whether that is right is not settled here. The page that lists the messages
  gives "too short messages" and "problematic Stecker connections" as the
  probable reasons they did not break.

#### Speculation

- That the 2026-09-30 targets belong to a network whose operators or procedures
  are not in any solved sample. Nothing in this run supports or excludes it.

#### Decision

- The Bombe stays deferred. The `decision_rule.bombe_detection` calibration was
  not written, because it applies only if G1 to G3 pass.
- Step three of the plan, the next Phase 1 experiment, is chosen in
  [Phase 1 history](phase1-experiment-history.md) without reference to a crib
  prior.

