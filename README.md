# Ultimate Enigma Challenge — Attack Package v0

## Objective
Reproduce the historical Batch C corpus faithfully, establish baselines, falsify easy hypotheses quickly, and only then escalate to unknown-wiring / alternate-machine inference.

## Corpus
CryptoCellar's September 1941 Batch C contains mixed traffic. Five messages are singled out as the unresolved Enigma-like set:

- 29 Sep: QTXMA (155), SZAEJ (51)
- 30 Sep: BYQMZ (167), FKQLZ (107), XFEDT (97)

Total ciphertext length: **577**, matching the 2005 CryptoCellar summary for the five unbroken Enigma message parts in Batch C.

Important: BYQMZ contains one uncertain source character. Keep uncertainty explicit rather than silently normalizing it.

## Working hypotheses

H0 — Standard Wehrmacht Enigma I, with one or more transcription/traffic errors.

H1 — Enigma-family machine or network with nonstandard rotor wiring, stepping, reflector, plugboard practice, or key procedure.

H2 — Another machine/system using Enigma-like indicators/traffic procedure.

H3 — The five-message set is not homogeneous; at least one message belongs to another mechanism or was transcribed incorrectly enough to distort statistics.

Do not collapse these hypotheses prematurely.

## Phase 0 — Corpus integrity and reconnaissance

1. Recheck every character against surviving message-form facsimiles.
2. Store ambiguous characters as alternatives with confidence, not as guessed literals.
3. Build a metadata graph: date/time, sender/operator, recipient callsign, frequency, indicator trigrams, designator.
4. Compute IC, entropy, repeated n-grams, lag coincidences, alphabet support, and pairwise structural tests.
5. Preserve exact raw transcription separately from normalized solver input.

Initial reconnaissance flags QTXMA as statistically anomalous relative to the other long messages. This is a classification clue, not proof of a different cipher.

## Phase 1 — Reproducible standard-Enigma baseline

1. Validate the included Enigma I simulator against published test vectors before using it analytically.
2. Reproduce the normal 1940+ Army message-key procedure: clear Grundstellung trigram + encrypted message-key trigram.
3. Exhaust ordinary I–V / UKW-B wheel orders, rings, starts and stecker via efficient hill-climbing / Bombe-style constraints.
4. Score with **raw German Army Enigma plaintext**, not newspaper German. Include X punctuation conventions, Q/CH conventions, number spelling, call-sign fragments, and military formulae.
5. Allow bounded source errors only after the clean baseline fails; penalize every edit.

Deliverable: a negative-result certificate describing exactly what standard keyspace was searched and with what error budget.

### Phase 1 execution status

The Phase 1 reference pipeline is now runnable. It validates the simulator,
implements the clear-Grundstellung/encrypted-message-key procedure, searches an
explicitly bounded I–V/UKW-B keyspace, preserves the `?` source uncertainty, and
writes a JSON certificate containing hashes, settings, counts, timings, top
candidates, and known gaps.

```bash
python3 -m unittest discover -v
python3 phase1.py validate
python3 phase1.py search --rings AAA --output artifacts/phase1-smoke-certificate.json
```

The checked-in smoke certificate covers all 60 I–V rotor orders for ring setting
`AAA`, with no stecker, independently for each date. It is a reproducible
restricted baseline, **not** the final Phase 1 negative result. A complete result
still requires a versioned Army-traffic language model and general stecker
hill-climbing/Bombe constraints. The second validation vector and procedure
example come from the [Py-Enigma user guide](https://py-enigma.readthedocs.io/en/latest/guide.html).

## Phase 2 — Network and archival crib generation

Treat archive research as part of the cryptanalytic loop.

1. Cluster by date/operator/frequency/callsign before assuming shared daily keys.
2. Search adjacent traffic and archival material for repeated situation reports, place names, unit names, routing phrases, acknowledgements, and retransmissions.
3. Rank cribs by historical plausibility *and* Bombe consistency rather than language plausibility alone.
4. Search specifically for duplicate/rephrased traffic, because the 2026 MVUEH break demonstrates how decisive a related plaintext can be.

### Phase 2 execution status

The Phase 2 pipeline is now runnable:

```bash
python3 phase2.py --output artifacts/phase2-network-cribs.json
```

It enriches the five message records with form/header times, operators,
callsigns, frequencies, remarks, sources, and current-status qualifiers. It then
builds a weighted traffic graph, generates archive-search priorities, and ranks
source-backed crib placements using Enigma's no-self-encryption property as a
cheap precheck. Inference-only and speculative cribs are disabled by default.

See `docs/phase2-research.md` for the dated fact/inference/speculation trail and
`cribs.json` for the machine-readable provenance catalog. The generated artifact
does not claim that a compatible placement is a valid Bombe menu or that all
five messages use one machine or key.

## Phase 3 — Known Enigma variants before free-form rotor recovery

Test historically documented alternate Enigma models, rotor sets, reflectors, plugboard practices and stepping behaviors before attempting arbitrary rotor permutations. Unknown rotor wiring is an enormous search space; historical priors are much cheaper than blind optimization.

### Phase 3 execution status

The Phase 3 catalog and bounded comparison are now runnable:

~~~bash
python3 phase3.py --output artifacts/phase3-variant-smoke.json
~~~

The default smoke run validates and compares eight executable profiles:
service Enigma with wide reflectors A/B/C, M3 with B/C and double-notch rotors,
Railway Enigma, and both documented Swiss K stepping modes. It evaluates 1,740
daily settings across the two corpus dates. Enigma T is cataloged but disabled
because the source says it appears not to have been used operationally.
Moving-reflector Abwehr machines and four-wheel M4 are recorded as unsupported
instead of being approximated with the wrong mechanism.

The highest raw score came from an M3 profile, but its plaintext is incoherent,
its Army-indicator treatment is explicitly artificial, and its larger rotor pool
creates a multiple-comparisons advantage. No plaintext was accepted. The run
fixes rings to AAA, the plugboard to empty, and settable reflectors to A; it is a
reproducible triage result, not an exclusion of these variants.

See docs/phase3-research.md for the dated evidence boundary and variants.json
for the source-linked machine catalog.

## Phase 4 — Joint machine inference

If H0/H1-known variants fail, solve at the **machine level** rather than message-by-message.

Unknowns may include rotor permutations, notch positions, reflector mapping, stepping behavior, ring offsets, stecker, and per-message starts. Jointly score all messages assigned to a candidate daily/network key.

Use alternating optimization:

1. machine hypothesis → optimize per-message key/start;
2. message solutions → update machine wiring / stecker;
3. rescore joint plaintext + indicator consistency;
4. mutate machine parameters while preserving involution/permutation constraints;
5. reject candidates that only explain one message.

### Phase 4 execution status

The first joint-machine experiment is implemented and recorded:

~~~bash
python3 phase4.py \
  --config experiments/phase4-joint-machine-smoke-v1/config.json \
  --output artifacts/phase4-joint-machine-smoke.json
~~~

The experiment was preregistered before execution. It optimized three messages
while withholding SZAEJ and XFEDT, used five fixed seeds, preserved rotor
permutations and fixed-point-free reflector involutions, and alternated shared
machine mutations with date-specific order/ring/plugboard mutations.

The hypothesis was refuted. All five seeds improved the visible training score
by roughly 0.19-0.22 per letter, but zero reached the required +0.02 held-out
improvement and the median held-out change was -0.1067. The result is a useful
overfitting demonstration, not an alternate-machine candidate. The recorded
decision is to avoid scaling blind wiring search until the corpus partition or
language model is strengthened.

See `docs/phase4-experiment-history.md` for the preregistration, observations,
interpretation, and next decision.

## Phase 5 — Alternative-cipher branch

If statistics or structural tests are incompatible with Enigma, run explicit model selection against likely contemporary manual/machine systems. Do not force an Enigma solution merely because the forms contain two trigrams.

### Phase 5 execution status

The first alternative-family triage is now runnable:

~~~bash
python3 phase5.py --output artifacts/phase5-model-triage.json
~~~

It analyzes each message separately, preserves the uncertain BYQMZ character at
its source position, calibrates monographic statistics against deterministic
uniform-random simulations, and calibrates repetition, lag, and candidate-period
statistics against frequency-preserving permutations of the observed message.
The output
routes messages toward frequency-preserving hand ciphers, periodic
polyalphabetic systems, code/superencipherment, or the still-indistinguishable
rotor/teleprinter branch. These are follow-up labels, not posterior probabilities
or cipher identifications.

In the checked-in 4,000-trial run, QTXMA is the only message routed away from
the randomizing control: its IC is 0.057729 (uniform-null upper-tail
`p = 1/4001`). Under the conditional permutation null, its maximum-lag
(`p = 0.0875`), maximum-period (`p = 0.1647`), and repeated-trigram
(`p = 0.0820`) tests are not significant at `alpha = 0.01`. SZAEJ, BYQMZ,
FKQLZ, and XFEDT remain uniform-random-compatible on the configured tests.
QTXMA therefore remains the frequency-preserving follow-up target, but there is
no separate evidence here for periodic, lag, or repeated-block structure. The
result does not distinguish double transposition from substitution or prove
that QTXMA is non-Enigma.

See `docs/phase5-research.md` for the fact/inference/speculation boundary and
`cipher-families.json` for the source-linked candidate catalog.

## Phase 6 — Frequency-preserving family experiment

Follow the Phase 5 routing decision with a family-specific experiment that can
falsify training-only improvements. The first branch tests bounded double
columnar transposition on QTXMA, because it was the sole message with a strong
frequency-preserving signal. Candidate keys must be selected without consulting
the held-out plaintext suffix, and a true-transposition positive control plus a
monoalphabetic-substitution control must bracket the result.

### Phase 6 execution status

The first preregistered smoke experiment is runnable:

~~~bash
python3 phase6.py \
  --config experiments/phase6-qtxma-double-transposition-smoke-v1/config.json \
  --output artifacts/phase6-qtxma-double-transposition-smoke.json
~~~

The positive control recovered its exact 4x5 double-transposition plaintext and
keys, while the substitution control gained nothing on its held-out suffix.
QTXMA did not pass: all three fixed seeds improved the visible training prefix
by about 0.037 score per letter but worsened the untouched suffix. The median
held-out change was -0.026923, zero seeds passed, and the selected keys did not
converge. This is evidence against the tested widths and scorer, not an
exclusion of double transposition generally and not a cipher identification.

See `docs/phase6-experiment-history.md` for the preregistration boundary,
controls, observations, interpretation, and next decision.

## Acceptance criteria

A credible break should satisfy most of these simultaneously:

- exact or minimally edited reproduction of ciphertext;
- historically plausible keying procedure;
- coherent German military plaintext over substantial length;
- one machine/key hypothesis explaining multiple compatible messages;
- no excessive free parameters or transcription edits;
- archival corroboration of names/events/routes where available;
- independent reproduction by a second implementation.

## Included files

- `corpus.json` — five-message working corpus and metadata
- `recon.py` — lightweight statistical reconnaissance
- `enigma.py` — transparent configurable three-wheel simulator and Enigma I wrapper
- `phase1.py` — reproducible Phase 1 reference search and certificate generator
- `phase2.py` — traffic graph, archive priorities, and provenance-aware crib ranker
- `phase3.py` — documented-variant comparison and certificate generator
- `phase4.py` — seeded joint machine/daily-key optimizer with held-out evaluation
- `phase5.py` — deterministic ciphertext-only alternative-family triage
- `phase6.py` — held-out-validated double-columnar-transposition smoke runner
- `cribs.json` — source-backed crib catalog with evidence levels
- `variants.json` — source-linked rotor, reflector, entry-wheel, and stepping catalog
- `cipher-families.json` — source-linked Phase 5 candidate-family catalog
- `docs/phase2-research.md` — dated Phase 2 evidence and recommendation trail
- `docs/phase3-research.md` — dated Phase 3 facts, inferences, gaps, and recommendation
- `docs/phase4-experiment-history.md` — preregistration and negative-result ledger
- `docs/phase5-research.md` — dated evidence boundary and Phase 5 recommendation
- `docs/phase6-experiment-history.md` — Phase 6 preregistration and negative-result ledger
- `experiments/phase4-joint-machine-smoke-v1/config.json` — exact Phase 4 experiment configuration
- `experiments/phase6-qtxma-double-transposition-smoke-v1/config.json` — exact Phase 6 experiment configuration
- `tests/` — simulator, procedure, corpus, scorer, and certificate tests
- `artifacts/phase1-smoke-certificate.json` — exact restricted baseline run record
- `artifacts/phase2-network-cribs.json` — generated network and crib ranking record
- `artifacts/phase3-variant-smoke.json` — bounded documented-variant comparison
- `artifacts/phase4-joint-machine-smoke.json` — raw multi-seed traces, states, and held-out result
- `artifacts/phase5-model-triage.json` — per-message structural tests and family routes
- `artifacts/phase6-qtxma-double-transposition-smoke.json` — raw Phase 6 controls, seeds, scores, keys, and candidates

## Primary references

- CryptoCellar, “The Ultimate Enigma Challenge” — https://www.cryptocellar.org/bgac/ultimate-enigma-challenge.html
- CryptoCellar, 1941 German Army Enigma message lists — https://www.cryptocellar.org/bgac/1941-msg-list.html
- CryptoCellar, unbroken 1941 list — https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html
- CryptoCellar, Enigma message procedures — https://www.cryptocellar.org/enigma/e-procedure.html
- CryptoCellar, Breaking German Army Ciphers — https://www.cryptocellar.org/pubs/mcts.pdf
