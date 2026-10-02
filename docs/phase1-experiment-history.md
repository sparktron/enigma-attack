# Phase 1 standard-Enigma experiment history

Phase 1 is the ordinary steckered service Enigma: UKW-B, Army/Air Force wheels
I–V, and the 1940+ clear-Grundstellung indicator procedure. Until these
experiments it had never been run at scale. The committed
[`artifacts/phase1-smoke-certificate.json`](../artifacts/phase1-smoke-certificate.json)
covers 120 daily keys with fixed plugboards in 0.083 seconds, and its own
`known_gaps` says so: "No Bombe constraints or general stecker hill-climbing
yet."

The method is the one the repository already cites: Weierud and Sullivan,
[*Breaking German Army Ciphers*](https://cryptocellar.org/pubs/mcts.pdf), with
the two-phase stecker scoring described by Ostwald and Weierud. An unsteckered
sweep scored by index of coincidence, retention of the best daily keys, then a
stecker hill-climb on the survivors.

The three experiments below were preregistered and run in this order, and the
first one changed what the other two could claim.

---

## phase1-stecker-calibration-v1

Status: completed 2026-09-26; hypothesis **not supported** — three of its four
clauses were refuted and the fourth was refuted and then repaired.

Hypothesis: the two-stage attack is usable on 1941-09-30 traffic of 97 to 167
letters carrying a ten-pair stecker. Concretely, (a) the true rotor setting's
unsteckered IC will stand at least 3 standard deviations above the wrong-setting
null at the target length and stecker size, (b) the stecker hill-climb will
recover a known ten-pair plugboard and its plaintext exactly at those lengths,
(c) a truncated climb will separate well enough to serve as a cheap pre-filter,
and (d) the indicator-coupled formulation `phase1.py` implements will be
hill-climbable.

Refuted by: any clause failing at the target scale.

Exact configuration:
[experiments/phase1-stecker-calibration-v1/config.json](../experiments/phase1-stecker-calibration-v1/config.json).
Raw result:
[artifacts/phase1-stecker-calibration-v1.json](../artifacts/phase1-stecker-calibration-v1.json).

### (a) The index-of-coincidence stage does not work at ten pairs — refuted

For each (length, stecker size) cell, one known key is used to encipher Army
text and the true rotor setting's unsteckered IC is compared with 400 wrong
settings on the same ciphertext.

| letters | 0 pairs | 3 pairs | 6 pairs | 8 pairs | 10 pairs |
|--------:|--------:|--------:|--------:|--------:|---------:|
|      97 | z +11.1 |  z +7.1 |  z +3.0 |  z +2.4 |   z +3.3 |
|     167 | z +25.2 | z +16.4 |  z +6.6 |  z +6.7 |   z +1.1 |
|     371 | z +44.2 | z +25.2 | z +16.9 |  z +4.8 |   z +0.5 |
|     800 | z +93.3 | z +57.2 | z +26.5 |  z +9.8 |   z +2.5 |

The 10-pair column never separates, **not even at 800 letters**. A ten-pair
stecker is what 1941 Army practice used. The reason is arithmetic: decrypting
with the identity plugboard at the correct rotor setting yields
`E·P·E·P` applied to the plaintext, which reproduces a plaintext letter only
when both plugboard applications happen to miss, about `(6/26)² ≈ 5%` of the
time. The IC is then about `0.05·0.076 + 0.95·0.0385 ≈ 0.040` against a null
mean of 0.0385 — an elevation of 0.002 against a null standard deviation of
0.0018 at 167 letters. The signal is real and it is too small.

This refutes the first stage of the cited method for this corpus, and no
retention list is large enough to fix it: the statistic itself carries no signal.

### (b) The stecker hill-climb does work at the target length — supported after repair

First measured with an n-gram-only climb from the identity plugboard, which
recovered the exact plugboard on 3 of 8 key draws at 167 letters with ten pairs.
Adding an index-of-coincidence phase ahead of the n-gram phase — the ordering
Ostwald and Weierud describe — took that to 8 of 8 for 1.6× the work. With no
steckers plugged the n-gram surface is nearly flat, because one correct pair
fixes too few letters to register in bigrams; the IC responds to each correct
pair restoring a slice of monoalphabetic structure.

Body-direct climb, two phases, 8 key draws per cell, 8 wrong-setting nulls per
draw:

| letters | 6 pairs | 10 pairs |
|--------:|--------:|---------:|
|      97 | 7/8 exact, median z +13.4 | **1/8**, median z +2.9 |
|     167 | 8/8 exact, median z +26.3 | **8/8 exact, median z +22.0** |
|     371 | 8/8 exact, median z +38.9 | **8/8 exact, median z +42.8** |

So the stecker stage is not the limiting factor at 167 letters, which is the
length of BYQMZ. At 97 letters it is: XFEDT is too short to attack on its own.

### (c) A truncated climb screens at the target length, but barely — refuted as stated

At 167 letters with ten pairs, 3 passes separate at z +2.5 for 58 ms against
123 ms for convergence. At 371 letters, 2 passes separate at z +3.6. The screen
exists, but it saves only about a factor of two at the target length, because
the climb converges in few passes there anyway. It does not make a full sweep
affordable, so the sweeps below use converged climbs.

### (d) The indicator-coupled formulation cannot be hill-climbed — refuted

Both arms get the true wheel order, the true ring setting and the identical
two-phase climb. The body-direct arm is given the true start positions; the
indicator-coupled arm must derive them through the plugboard it is searching
for.

| arm | recovered plugboard | message keys | score/letter |
|---|---|---|---|
| body-direct | exact, all 10 pairs | n/a (given) | −6.666 |
| indicator-coupled | 8 pairs, none correct | wrong | −8.930 |

The coupled arm scores *below* the wrong-key mean. The plugboard sits inside the
indicator machine as well as the body machine, so until nearly every stecker is
right the recovered message key is wrong and the body is noise. The objective is
a discontinuous function of the stecker and there is no gradient to follow.

This is why `phase1.py` could not have been completed by bolting a stecker
climb onto it. `phase1.py:139` fixes `indicator[0]` as the Grundstellung and
`indicator[1]` as the enciphered message key; trying both orderings is a free
factor of two and both sweeps below do it, but the ordering was never the
obstacle.

---

## phase1-indicator-sweep-v1

Status: completed 2026-09-26; hypothesis **not supported**. Complete search of a
declared space with a stated detection limit of zero.

Hypothesis: an exhaustive search of the daily-key space `phase1.py` defines — 60
rotor orders × all 17,576 ring settings × both indicator orderings on BYQMZ,
FKQLZ and XFEDT, ranked by pooled IC and then stecker-hill-climbed — will
surface a daily key whose decryption reads as German Army plaintext.

Refuted by: no retained candidate producing readable German after the climb.

Exact configuration:
[experiments/phase1-indicator-sweep-v1/config.json](../experiments/phase1-indicator-sweep-v1/config.json).
Raw result:
[artifacts/phase1-indicator-sweep-v1.json](../artifacts/phase1-indicator-sweep-v1.json).

**2,109,120 daily keys evaluated**, the complete space, in 234 seconds. This is
17,576 times the coverage of the committed Phase 1 certificate.

| ordering | best pooled IC | best score/letter after climb |
|---|---|---|
| `grundstellung_first` | 0.04324 (II-V-III, JCP) | −8.918 (I-III-V, CRO) |
| `message_key_first` | 0.04439 (III-I-II, MQN) | −8.897 (IV-V-I, DGG) |

For comparison, the positive controls score −6.67 per letter on real German
Army plaintext, and the calibration's wrong-setting null sits near −8.9. Every
top candidate is indistinguishable from noise and its plaintext reads as noise.

The result is a completed, reproducible search of exactly the space
`phase1.py` defines. It is **not** evidence that these messages are not standard
Enigma, and the calibration says so in advance: this space's ranking statistic
has no detection power at ten pairs, and its hill-climb has no gradient. The
value of the run is that the space is now closed and the reason it could never
have worked is recorded with numbers.

---

## phase1-body-direct-sweep-v1

Status: completed 2026-09-26; hypothesis **not supported** over the declared
slice.

Hypothesis: a body-direct sweep over all 60 wheel orders × all 676 middle/right
start positions, left start held at A and rings at AAA, with a converged
two-phase stecker hill-climb at every setting, will surface a rotor setting for
BYQMZ whose climbed score stands clear of the rest of the slice.

Refuted by: no setting standing clear of the slice's own score distribution.

Exact configuration:
[experiments/phase1-body-direct-sweep-v1/config.json](../experiments/phase1-body-direct-sweep-v1/config.json).
Raw result:
[artifacts/phase1-body-direct-sweep-v1.json](../artifacts/phase1-body-direct-sweep-v1.json).

BYQMZ is chosen because it is the corpus's longest message at 167 letters, the
shortest length at which the calibration recovers a ten-pair plugboard on every
draw. The stecker stage is therefore capable here and the experiment is purely a
coverage question.

**40,560 settings evaluated** (60 wheel orders × 676 middle/right start
positions, left start held at A, rings at AAA) in 1,027 seconds wall-clock on
18 workers — 25.3 ms of wall-clock per setting at that parallelism, which is
about 456 ms of actual CPU time per converged two-phase climb (roughly 5.1
core-hours for the slice actually run). The declared slice is 0.148% of the
27,418,560-setting space that actually has to be searched (60 × 26⁴, the
parameters a 167-letter message can distinguish), so at the measured cost the
whole space is a projected **3,472 core-hours** (about 193 wall-clock hours,
just over 8 days, at this same 18-way parallelism).

| | score/letter |
|---|---:|
| slice mean | −8.593 |
| slice sd | 0.106 |
| slice max (rank 1) | −8.142 |
| rank 1's z-score within the slice | +4.24 |

A z of +4.24 sounds like a signal until it is compared with what pure noise
produces at this scale: the expected maximum of 40,560 independent standard
normal draws is z ≈ 4.08. Rank 1 is indistinguishable from the best of 40,560
nothings.

Each retained candidate is then re-scored independently: its recovered plugboard
and ring setting are fed back through the clear indicator to derive all three
message keys for the date, and the whole 371-letter date is scored. The sweep
never reads the indicator, so a candidate that is really the daily key gains the
other two messages' letters while a wrong candidate gains nothing. Every
retained candidate's confirmation score (best −9.316, mean −9.550 across the
top 40) is **worse** than its own single-message climbed score, which is what a
wrong plugboard applied to unrelated ciphertext looks like. None of the top 40
is the daily key.

The slice is a declared fraction of the space that actually has to be searched.
That space is 60 × 26⁴ ≈ 2.74 × 10⁷ settings — wheel order, the left and middle
wheel offsets, and the right wheel's offset and absolute position — which
assumes the left wheel does not step during the message, true for about three
quarters of start positions at this length. The artifact records the fraction
covered and the measured core-hours the whole space would need, rather than
redefining the space to flatter the run.

---

## What Phase 1 now needs

The two sweeps bound the problem from both sides.

* The **indicator-coupled** space is small enough to search exhaustively — and
  now has been — but its ranking statistic and its hill-climb both have zero
  power at a ten-pair stecker. Nothing more can be extracted from it.
* The **body-direct** formulation works: at 167 letters with ten pairs the
  climb recovers the exact plugboard and exact plaintext on every draw. Its
  space is about 2.74 × 10⁷ settings per message, measured at roughly 456 ms
  of CPU time per converged climb, so a complete search of one message is a
  projected 3,472 core-hours (about 8 days of wall-clock time on 18 cores),
  and the calibration shows no cheap pre-filter that cuts this by more than
  about 2×.

The gap is therefore neither the scorer nor the stecker search. It is the
enumeration of rotor settings, and the historically correct answer to exactly
that problem is the one Bletchley Park built: a **crib-driven Bombe**, which
eliminates the plugboard algebraically through the diagonal board instead of
searching it, and tests a rotor setting in microseconds rather than a tenth of a
second. Phase 2 already assembled a crib network
([docs/phase2-research.md](phase2-research.md),
[artifacts/phase2-network-cribs.json](../artifacts/phase2-network-cribs.json)),
and the no-self-encipherment property makes crib placement nearly free. That is
the next experiment, and the measurement above is the argument for it.

Second, and cheaply: XFEDT at 97 letters is below the recovery threshold on its
own (1 of 8 draws) and should not be attacked alone. FKQLZ at 107 letters was
not measured directly and sits between the 97-letter and 167-letter cells.
