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

## Phase 2 — Network and archival crib generation

Treat archive research as part of the cryptanalytic loop.

1. Cluster by date/operator/frequency/callsign before assuming shared daily keys.
2. Search adjacent traffic and archival material for repeated situation reports, place names, unit names, routing phrases, acknowledgements, and retransmissions.
3. Rank cribs by historical plausibility *and* Bombe consistency rather than language plausibility alone.
4. Search specifically for duplicate/rephrased traffic, because the 2026 MVUEH break demonstrates how decisive a related plaintext can be.

## Phase 3 — Known Enigma variants before free-form rotor recovery

Test historically documented alternate Enigma models, rotor sets, reflectors, plugboard practices and stepping behaviors before attempting arbitrary rotor permutations. Unknown rotor wiring is an enormous search space; historical priors are much cheaper than blind optimization.

## Phase 4 — Joint machine inference

If H0/H1-known variants fail, solve at the **machine level** rather than message-by-message.

Unknowns may include rotor permutations, notch positions, reflector mapping, stepping behavior, ring offsets, stecker, and per-message starts. Jointly score all messages assigned to a candidate daily/network key.

Use alternating optimization:

1. machine hypothesis → optimize per-message key/start;
2. message solutions → update machine wiring / stecker;
3. rescore joint plaintext + indicator consistency;
4. mutate machine parameters while preserving involution/permutation constraints;
5. reject candidates that only explain one message.

## Phase 5 — Alternative-cipher branch

If statistics or structural tests are incompatible with Enigma, run explicit model selection against likely contemporary manual/machine systems. Do not force an Enigma solution merely because the forms contain two trigrams.

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
- `enigma.py` — transparent standard Enigma I baseline simulator

## Primary references

- CryptoCellar, “The Ultimate Enigma Challenge” — https://www.cryptocellar.org/bgac/ultimate-enigma-challenge.html
- CryptoCellar, 1941 German Army Enigma message lists — https://www.cryptocellar.org/bgac/1941-msg-list.html
- CryptoCellar, unbroken 1941 list — https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html
- CryptoCellar, Enigma message procedures — https://www.cryptocellar.org/enigma/e-procedure.html
- CryptoCellar, Breaking German Army Ciphers — https://www.cryptocellar.org/pubs/mcts.pdf
