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

Status: preregistered 2026-10-07; not run. Configuration:
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
