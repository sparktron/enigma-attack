# Phase 3 variant experiment history

Phase 3 asks whether a documented Enigma-family machine other than the Army's
steckered Enigma I explains the corpus. Until the experiment below, its only run
was a smoke screen:
[`artifacts/phase3-variant-smoke-v2.json`](../artifacts/phase3-variant-smoke-v2.json)
enciphered every message under a handful of daily keys per catalogued profile,
1,740 evaluations in all, with the rings at AAA, the reflector at A and no
plugboard. Its own `coverage_gaps` say it excludes nothing.

Why it matters now. The cited paper's authors suspect that Batch C used "an
Enigma machine with differently wired wheels". The
[challenge page](https://www.cryptocellar.org/bgac/ultimate-enigma.html) gives
their reasons: the operators' names differ from the other 1941 Army messages,
the operator comments are unusual, and the frequencies (323, 568 and 716 kHz)
are lower than German Army networks normally used. Every Phase 1 search assumes
wheels I–V. An unknown wiring cannot be recovered from three short messages:
the closest published attack, on Typex, needed about 50,000 letters to recover
one unknown rotor with every other wiring and the key known
([Chang, Low and Stamp](https://cryptomuseum.com/crypto/uk/typex/files/kelly_et_al.pdf)).
The documented machines without a plugboard, on the other hand, can be searched
completely and cheaply, because with no plugboard there is nothing to climb.

---

## phase3-unsteckered-sweep-v1 (preregistered)

Status: preregistered 2026-10-07; **run 2026-10-07, null, see
[Result](#result-run-2026-10-07)**. Configuration:
[experiments/phase3-unsteckered-sweep-v1/config.json](../experiments/phase3-unsteckered-sweep-v1/config.json);
runner `phase3_sweep.py`, kernel `variant_sweep.py`, tests
`tests/test_variant_sweep.py`, all committed before any run.

What it searches. Every catalogued profile without a plugboard except Enigma T,
which the catalog excludes: the Reichsbahn (railway) Enigma, the Swiss K, and
the Swiss K with the 1941 Swiss Army stepping (right wheel fixed, middle wheel
fast, the reflector stepped by the left wheel's notch). Each is swept
body-direct over BYQMZ, FKQLZ and XFEDT separately, so no indicator procedure
is assumed. QTXMA and SZAEJ are left out because their missing letters (no D, F,
G or U in QTXMA's 155, no D, F or U in SZAEJ's 51) are implausible for any
reflecting rotor machine's output.

How the space is enumerated. A wheel's effect on the signal depends only on its
offset (window letter minus ring); when it steps depends only on its window
letter. The kernel simulates the stepping from all 26³ window starts, keeps one
representative of each distinct schedule (218 per wheel order at 167 letters,
for each machine) and pairs each with all 26⁴ combinations of the three
offsets and the reflector position. That is every body-direct setting the
machine model can produce, about 6.0 × 10⁸ per machine at 167 letters. Every
setting is deciphered and scored with the published 1941 n-gram counts; there is
no hill-climb and no pruning.

Gates, as in Phase 1. Preflight: on random keys with a masked letter, the
kernel's letters, the representative key's reference decryption and the score
must equal `enigma.EnigmaMachine` and `FastNgramScorer` exactly. Positive
controls: one planted 97-letter message per machine, swept completely by the
same code, must come back exactly and reach the threshold. A failed check or
control makes zero target-search calls.

Hypothesis. At least one of the three messages was enciphered, as one continuous
body, on one of these machines with the catalogued wirings. A complete sweep of
that machine on that message then ranks first a setting at z ≥ 8 above the
sweep's own score distribution.

Refuted by: no (machine, message) sweep reaches top z ≥ 8.

Power, measured after the sweeps: 200 planted draws per machine and target, with
the target's length and masked position, judged against that target's own
distribution, clean and with one dropped or inserted letter. Predicted at least
95% for an ungarbled message on every machine and target. A faulted draw counts
the better of its head key and its tail key, both of which the sweep visits, so
the figure is a lower bound.

Predictions (in the configuration):

- **unsteckered-detection** (decides): some (machine, message) reaches z ≥ 8.
- companion-detected: a detecting machine also detects another of the three.
- clean-power-at-least-95pct: as above.
- null-top-in-noise-band: with no detection, every top z is between 5.0 and 7.5.

The threshold of 8 was set before any target was touched, from development runs
on random and planted bodies only:

| body | one wheel order | top z |
|---|---|---:|
| random, 97 letters | railway, two orders | 5.68, 6.22 |
| random, 167 letters | railway, two orders | 5.48, 5.61 |
| random, 97 letters | Swiss 1941, two orders | 5.71, 5.85 |
| random, 167 letters | Swiss 1941, two orders | 5.72, 6.36 |
| planted key, 97 letters | railway, its order | 14.14, the planted key at its exact score |
| planted key, 97 letters | Swiss 1941, its order | 14.46, likewise |

A full machine has six orders and nine sweeps run, so the largest noise maximum
is expected near 7.

Checked before committing, on a scratch corpus holding a planted 60-letter
railway message and a random one (not part of the record): the whole runner ran
end to end, the planted message was detected at z 11.1 with its plaintext, the
random one topped at z 6.18, and a second run reproduced every number.

Limits, in the configuration. Only these three machines with these wirings: a
null says nothing about the commercial Enigma D or K, the Abwehr Enigma G (not
modelled), or any rewired or undocumented wheel, and nothing about a machine
with a plugboard. The preflight checks the kernel against `enigma.py`, not
`enigma.py` against history, so a catalogue error makes that machine's null
uninformative. One dropped or inserted letter lowers the power; two are not
measured. The scorer is Army German; railway or Swiss traffic would be another
register or language, and the margin there is not measured. The catalog's
historical priors for these machines are low and very low; the search runs
because it is cheap and nearly conclusive, not because they are likely.

Cost: about 25 to 40 minutes on 10 workers. Scoring one left offset at a time
keeps the working arrays in cache; on the whole grid at once, eight workers
sharing memory bandwidth were four times slower.

Run command, not run:

```bash
python3 phase3_sweep.py --jobs 10
```

### Result (run 2026-10-07)

Status: completed; hypothesis **not supported**. No machine detects any of the
three messages. Three of the four predictions were scored: the deciding one
failed, the power and noise-band predictions held, and the companion prediction
does not apply.

Deviation, disclosed (review P1 on PR #18): the first run, at `c3a9076`,
counted each distinct stepping schedule once in the mean and standard deviation,
although a schedule stands for 26 to several hundred window starts; the
configuration defines the null over every machine setting. `4d09ab0` weights
each schedule by its window starts, and the configuration was rerun unchanged
from that clean commit (16:13 to 16:32 UTC, 1,157 s, host load about 7 from an
unrelated pytest and LM Studio). The committed artifact is the rerun. Against
the first run: every maximum and top candidate is identical, means and standard
deviations move in the fifth decimal, every z by at most 0.002, and every power
count, detection and prediction verdict is unchanged. The figures below are the
rerun's. Statistics now cover 48,190,861,056 machine settings per machine and
message (26^7 per wheel order); the settings column counts those deciphered.

First run record: `phase3_sweep.py --jobs 10`, 2026-10-07 15:42:34 to 15:59:32 UTC,
1,017 s by the runner's clock, about 2.6 CPU-hours, Python 3.10.12, numpy
2.2.6, 10 workers on the i9-10900K. Code `c3a9076` on
`claude/phase3-unsteckered-sweep`, **clean tree**. The host was lightly loaded
(load average 1.8 at the start, an LM Studio server using about half a core);
outcomes depend only on the seeds. Raw result:
[artifacts/phase3-unsteckered-sweep-v1.json](../artifacts/phase3-unsteckered-sweep-v1.json)
(long-running; its claim paths were checked against the artifact).

Gates. Preflight: 12 random keys per machine, 0 mismatches. Positive controls,
one planted 97-letter message per machine, each swept completely (179 s for the
three):

| machine | planted order | recovered | z |
|---|---|---|---:|
| railway | II-I-III | exact plaintext | 13.95 |
| Swiss K | II-I-III | exact plaintext | 14.36 |
| Swiss K, 1941 stepping | II-III-I | exact plaintext | 14.96 |

The recovered keys differ from the planted ones in rings and window letters
but decipher identically, as the parameterization says they must.

#### Observed

Every body-direct setting of each machine on each message, with the top of its
score distribution (score per letter, published 1941 counts):

| machine | message | settings | mean | sd | top z |
|---|---|---:|---:|---:|---:|
| railway | BYQMZ (166 read) | 597,724,608 | -9.587 | 0.158 | 6.09 |
| railway | FKQLZ (107) | 433,213,248 | -9.623 | 0.198 | 6.08 |
| railway | XFEDT (97) | 405,794,688 | -9.610 | 0.208 | 6.50 |
| Swiss K | BYQMZ | 597,724,608 | -9.586 | 0.157 | 6.38 |
| Swiss K | FKQLZ | 433,213,248 | -9.622 | 0.198 | 6.49 |
| Swiss K | XFEDT | 405,794,688 | -9.611 | 0.207 | 6.54 |
| Swiss K, 1941 | BYQMZ | 597,724,608 | -9.586 | 0.158 | 6.21 |
| Swiss K, 1941 | FKQLZ | 433,213,248 | -9.624 | 0.197 | 6.20 |
| Swiss K, 1941 | XFEDT | 405,794,688 | -9.611 | 0.207 | 6.03 |

No sweep reaches z = 8; the largest top is 6.54. The top candidates' plaintexts
are unreadable (for example `TRMECFIXWMXFZBGWKTRN...` for the railway Enigma on
BYQMZ), and every reported top candidate's score was reproduced by `enigma.py`.

Power, 200 planted draws per cell judged against that target's own
distribution (95% Wilson intervals):

| machine | message | clean | one deletion | one insertion |
|---|---|---:|---:|---:|
| railway | BYQMZ | 200/200 | 200/200 | 199/200 |
| railway | FKQLZ | 200/200 | 176 (88%) | 178 (89%) |
| railway | XFEDT | 200/200 | 167 (84%) | 168 (84%) |
| Swiss K | BYQMZ | 200/200 | 200/200 | 200/200 |
| Swiss K | FKQLZ | 200/200 | 182 (91%) | 176 (88%) |
| Swiss K | XFEDT | 200/200 | 173 (87%) | 168 (84%) |
| Swiss K, 1941 | BYQMZ | 200/200 | 199/200 | 199/200 |
| Swiss K, 1941 | FKQLZ | 200/200 | 185 (93%) | 167 (84%) |
| Swiss K, 1941 | XFEDT | 200/200 | 176 (88%) | 164 (82%) |

Every clean cell's interval is [0.981, 1.0]; the weakest clean draw anywhere
scored z 12.1. Every faulted cell's lower bound is at least 0.76.

| id | prediction | observed | |
|---|---|---|---|
| **unsteckered-detection** | some (machine, message) reaches z ≥ 8 | none; top z 6.03 to 6.54 | **refuted** |
| companion-detected | a detecting machine detects another message | no detection | not applicable |
| clean-power-at-least-95pct | clean power ≥ 95% everywhere | 100% everywhere | held |
| null-top-in-noise-band | with no detection, every top z in [5.0, 7.5] | 6.03 to 6.54 | held |

#### Interpretation (inference)

- Under the experiment's assumptions, none of the three catalogued unplugged
  machines enciphered any of BYQMZ, FKQLZ or XFEDT. Those assumptions are the
  catalogued wirings, one continuous body per message, at most one dropped or
  inserted letter, and German plaintext. For an ungarbled message the
  measured power is 1.0 (lower 95% bound 0.98) and the weakest planted key sat
  about 4 sd above the threshold, so this is close to an exclusion, not a
  modest test.
- With one dropped or inserted letter it is still strong: at least 82% for
  every machine and message, and 99.5% or more for BYQMZ. Together with the
  shared date and network, a reading in which all three messages were sent on
  one of these machines is excluded more firmly than any one message's figure
  says.
- The nine top scores sit where the development noise runs put them (6.0 to
  6.5). Nothing in the distribution is unusual.
- What this leaves of the paper's suspicion: an Enigma whose wheels are wired
  differently from every catalogued machine, the commercial D or K with their
  original wirings, the Abwehr G, a plugboard machine other than Phase 1's, or
  a message with more than one fault. The first cannot be searched; the second
  and third need sourced wirings and, for the G, a model of its stepping.
- It does not bear on Phase 1. A steckered Enigma I with wheels I-V is outside
  this search, and v4's power and preregistration are unchanged.

#### Decision

- The three catalogued unplugged machines are closed for these messages at the
  catalog's wirings. Reopening them needs a reason to doubt a catalogued wiring
  or a reason to expect several faults.
- Cheap next steps on the same question, in order: ask the paper's authors what
  their 2003-04 attempt covered and what the source documents say about the
  network; add the commercial Enigma D and K only with sourced wirings; and
  test reflector C with wheels I-V (a v2-shaped sweep, about 17 hours) only
  once its 1941 use is sourced.
- `accepted_break` stays false.
