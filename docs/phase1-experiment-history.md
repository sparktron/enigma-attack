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

The first three experiments below were preregistered and run in this order, and
the first one changed what the other two could claim. A fourth, added on
2026-10-02, measures what a sweep can detect end to end and corrects claims the
first three made.

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

> **Correction, 2026-10-03.** This table contradicts its own artifact, whose
> `usable_cells` lists 97 letters with ten pairs (z +3.30 against `usable_z`
> 3.0), and "never separates" is wrong as written. Each cell is one key draw,
> which is why the ten-pair column is not monotone in length, and z ≥ 3 against
> 400 wrong settings is the wrong test for a statistic that ranks a million keys
> per indicator ordering: at that population the true key needs z ≈ 3.6 just to
> expect a place in the top 200 and z ≈ 4.8 to expect first place. "The statistic carries no
> signal" is also too strong. Re-measured over 32 draws per cell as expected rank
> against the sweep ([phase1-ic-rank-v1](#phase1-ic-rank-v1) below), the
> ten-pair true key is retained in the top 200 with probability 0% at 167
> letters, 6% at 371 and 19% at 800. The conclusion stands as "almost no power"
> rather than "none".

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

> **Scope correction, 2026-10-02.** Every cell above hands the climb the true
> rings and start position, which the body-direct sweep never visits. The
> table bounds the stecker stage and not the sweep. The end-to-end figure is in
> [phase1-end-to-end-power-v1](#phase1-end-to-end-power-v1) below: 82.5% for
> the best single-phase parameterization, not "every draw".

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
has almost no detection power at ten pairs (corrected figures in
[phase1-ic-rank-v1](#phase1-ic-rank-v1)), and its hill-climb has no gradient. The
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

> **Coverage correction, 2026-10-02.** "About three quarters" counts only the
> true key's left wheel not stepping. Holding the middle ring at A gives the
> swept setting a left-wheel step of its own, so both must be absent. Counting
> stepping patterns exactly at 167 letters, the held-ring parameterization has
> an exact equivalent for **52.4%** of true keys, not about 73%. The slice this
> run searched also fixed the right ring at A, so it could reach an exact
> equivalent for about 2.5% of keys (1 of 40 planted draws below). A null from
> it is therefore weaker evidence than this section reads. The confirmation
> scores quoted above came from a run made before the confirmation stage
> recovered the ring setting (commit 9c6bfb7), so they are superseded; the
> slice's null conclusion rests on the sweep scores alone.
>
> **Re-confirmation, 2026-10-03.** The artifact's recorded `phase1_stecker.py`
> hash (`f608bc6e…`) is not the module after 9c6bfb7, and its recorded commit
> `ffa9fdb` predates the stecker module, because the run came from an
> uncommitted tree and nothing then recorded that (every phase now records a
> `dirty` flag in its `code` block). `scripts/reconfirm_body_direct.py` re-scores
> the 40 retained candidates exactly as recorded with the current,
> ring-recovering confirmation:
> [artifacts/phase1-body-direct-sweep-v1-reconfirmation.json](../artifacts/phase1-body-direct-sweep-v1-reconfirmation.json).
> Best −9.102, mean −9.541; 1 of 40 has a ring setting compatible with the
> indicator, and none scores above its own single-message sweep score (best
> gain −0.96 per letter). The superseded figures were −9.316 and −9.550. The
> confirmation therefore agrees with the sweep scores: none of the top 40 is the
> daily key. `check_artifacts.py` now warns when a long-running artifact's
> recorded code differs from the checkout.

---

## phase1-end-to-end-power-v1

Status: completed 2026-10-02; five of six preregistered predictions held and
one was refuted.

Hypothesis: under the parameterization a full body-direct sweep would actually
use, a sweep over the neighbourhood of a planted random-ring, random-start,
ten-pair key on a 167-letter message detects the key in at least 60% of 40
draws, exceeds the middle-ring-held-at-A parameterization by at least 5
points, and holding every ring at A detects at most 25%.

Refuted by: the middle-past-notch arm below 60%, or not 5 points above the
held-middle arm, or the all-rings-at-A arm above 25%. Six predictions were
written into the config and scored by the runner.

Configuration:
[experiments/phase1-end-to-end-power-v1/config.json](../experiments/phase1-end-to-end-power-v1/config.json)
(sha256 `7c223a57…`), committed in `0c71a86` before the run. Raw result:
[artifacts/phase1-end-to-end-power-v1.json](../artifacts/phase1-end-to-end-power-v1.json),
which keeps every draw's planted key, per-arm top candidate and null scores.

Run record: seed 20261002, each draw seeded from its (cell, draw) coordinates so
it does not depend on worker scheduling; Python 3.10.12, Linux 6.8, 20 CPUs,
`--jobs 18`, 302.6 s wall-clock. Code `0c71a86`, tree **dirty** with two
untracked entries, `docs/code-review-2026-10-02.md` and `scripts/review/`, neither
imported by the run; the five code hashes it recorded are in the artifact. The
whole artifact was run once and not repeated; only a draw's purity is covered
by a unit test.

What it measures. Each draw plants a random wheel order, ring setting, start
position and ten-pair plugboard, enciphers 167 letters, and runs the sweep
engine over the planted order with left offsets within 1 and middle offsets
within 2 of the planted ones. The right wheel is taken at its planted values.
A draw is *detected* when the best candidate's plugboard is exactly the planted
one and its score is at least 6 standard deviations above a pooled null of 320
wrong-setting climbs (threshold −8.043 per letter). Four parameterizations
sweep the same keys:

### Observed

| arm | climbs per draw | exact equivalent in slice (measured / analytic) | detected | rate, 95% interval |
|---|---:|---:|---:|---:|
| all rings held at A, right ring not searched | 15 | 1/40 (2.5%) / — | 11/40 | 27.5% [16.1, 42.8] |
| right ring searched, middle ring held at A | 15 | 20/40 (50.0%) / 52.4% | 27/40 | 67.5% [52.0, 79.9] |
| right ring searched, middle ring past its notch | 15 | 29/40 (72.5%) / 71.6% | 33/40 | **82.5% [68.1, 91.3]** |
| as above plus every middle start that reaches the notch | 135 | 40/40 / 100% | 39/40 | 97.5% [87.1, 99.6] |

Detection split by whether the slice held an exact equivalent: past-notch
28/29 with one, 5/11 without; held-middle 19/20 and 8/20; all-rings-at-A 1/1 and
10/39. The median best agreement with the true machine, over letter positions,
was 0.98 for the held-middle arm.

One dropped or inserted letter at a random interior position, 40 draws:

| arm | detected | rate |
|---|---:|---:|
| all rings held at A | 1/40 | 2.5% |
| middle ring held at A | 6/40 | 15.0% |
| middle past notch | 6/40 | 15.0% |
| every middle start | 11/40 | 27.5% (plugboard recovered 12/40) |

Exploratory, not preregistered: for the past-notch arm the six detections were
4 of the 10 draws with the indel within 30 letters of an end, and 2 of the 30
draws with it farther in.

Predictions: past-notch at least 60% (82.5%, held); at least 5 points above the
held-middle arm (+15.0, held); all-rings-at-A at most 25% (**27.5%, refuted**);
measured exact-equivalent rate within 0.15 of analytic (0.009, held); complete
phases at least 80% (97.5%, held); one indel at most half the unperturbed rate
(0.18, held).

### Baseline

The stecker-stage calibration in `phase1-stecker-calibration-v1` (8/8 at 167
letters, ten pairs) is the upper bound: the climb is handed the true key. The
review's unpreregistered measurement (36/48 plugboards recovered for the
past-notch rule, 33/48 for the held rule) is consistent with 33/40 and 27/40
here. The all-rings-at-A figure is above the review's 4/32.

### Interpretation (inference)

- The stepping-pattern model of what a swept setting can reach is right: its
  analytic coverage (52.4% held, 71.6% past notch) matches the measured exact
  equivalents (50.0%, 72.5%) to within a draw.
- The stated power of a complete body-direct sweep of BYQMZ-like traffic, with
  the right ring searched and the middle ring chosen past its notch, is about 0.83
  (lower 95% bound 0.68) when the message is transcribed without faults. Using
  the held-ring parameterization it is about 0.68. The history's earlier "every
  draw" belongs to the stecker stage alone.
- A null over a full sweep is therefore weaker evidence than the earlier
  record implied, by roughly the 17% of keys that this parameterization misses.
  The 40,560-setting slice already run held the right ring at A and could
  reach an exact equivalent for about 2.5% of keys, so its null says little.
- Partial equivalents rescue more than the review concluded: 5 of 11 and 8 of 20
  draws without an exact equivalent still gave the right plugboard. The
  counts are small and the slice always contained the neighbouring offsets, so
  this is an estimate, not a rate to plan on.
- Covering the keys whose left wheel steps costs nine times as many settings
  (246.8 million instead of 27.4 million) and buys about 15 points here. At
  the observed rates the past-notch rule spends about 18 climbs per detected
  key and the complete rule about 138. That favours the single-phase rule
  unless the missing 17% matters.
- A single transcription fault is the larger risk than the parameterization.
  One indel cuts detection to 15%, and even the complete rule reaches only 27.5%.
  The exploratory split suggests the loss is smaller when the indel is near an
  end, which fits the aligned segment carrying the signal, but 10 and 30 draws
  do not establish it. If it holds, windowed climbs over the first and last part
  of a message are the repair.
- The 25% prediction for the all-rings-at-A arm was set from the review's 4 of 32
  and was too low. The interval [16.1, 42.8] contains 25%, so one run
  refutes the prediction without establishing the true rate.
- Limits: the slice holds the planted wheel order and the planted right wheel,
  so a detection here is a detection against the planted key's neighbourhood and
  the pooled null, not against 2.7 × 10⁷ settings. The 6σ threshold stands in
  for the extreme of that many draws and assumes a near-normal null. One
  plaintext prefix and 40 draws per cell leave arms a few points apart
  unresolved. The indel cell tests one random letter only.

### Decision

- Any full BYQMZ sweep uses the `middle_past_notch` rule with the right ring as
  an axis. Its stated power is 0.83 [0.68, 0.91] with no transcription fault and
  0.15 with one indel.
- Before that sweep, add a windowed-climb calibration cell, because the
  indel result says a single fault hides the key from a whole-message climb.
- STATUS.md's coverage statements are corrected to the exact figures above.
  The efficiency work (review R1 and R2) is still needed to make the sweep
  affordable.
- The v1 body-direct artifact stays as the record of a slice whose rings
  were all held at A.

---

## phase1-ic-rank-v1

Status: completed 2026-10-03; hypothesis **not supported** — one of its three
clauses was refuted, narrowly.

Hypothesis: averaged over 32 key draws per cell, the true rotor setting's
unsteckered IC under a ten-pair stecker is retained in the top 200 of the 1,054,560
daily keys its own indicator ordering ranks with mean probability below 5% at 167 letters and at 371
letters, while with no stecker it is retained with mean probability above 95% at
167 letters. It replaces the single-draw, z ≥ 3 criterion of clause (a) above
(review 2026-10-02, P5).

Refuted by: a ten-pair mean retention probability of 5% or more at 167 or 371
letters, or a zero-pair one of 95% or less at 167.

Configuration:
[experiments/phase1-ic-rank-v1/config.json](../experiments/phase1-ic-rank-v1/config.json),
committed in `921504b` before the run. Raw result:
[artifacts/phase1-ic-rank-v1.json](../artifacts/phase1-ic-rank-v1.json),
regenerated by the drift check.

Run record: seed 20261003, Python 3.10.12, Linux 6.8, single process, 38 s.
Code `d7a8175`, clean tree.

Deviation from the preregistration: the committed config set the ranked
population to 2,109,120, both indicator orderings together. The indicator
sweep ranks and keeps 200 per ordering, so the true key competes only with its
own ordering's 1,054,560 keys. The PR review caught this after the first run
(code `889c7ff`), and the population was corrected in `d7a8175`. The draws,
seed and thresholds did not change. Every expected rank halved, and the ten-pair
retention at 371 letters moved from 6.19% to 6.25%, so no prediction changed
outcome. The first run is reproducible from `889c7ff`.

What it measures. Each draw takes a random 1-of-60 wheel order, ring setting,
start, plugboard and stretch of the calibration plaintext, and computes the true
setting's unsteckered IC. That IC becomes a tail probability under the
uniform-letter null (chi-square with 25 degrees of freedom, Wilson–Hilferty),
then an expected number of wrong keys above it among 1,054,560 (the sweep ranks
and retains each indicator ordering separately), then the Poisson
chance that fewer than 200 outrank it. 500 empirical wrong settings per draw
check the null model: in every cell their mean and sd agree with the analytic
ones to within 1%, and a unit test checks the model's 1% tail on random text.

### Observed

Mean probability of top-200 retention (median expected rank in brackets):

| letters | 0 pairs | 3 pairs | 6 pairs | 8 pairs | 10 pairs |
|--------:|--------:|--------:|--------:|--------:|---------:|
|      97 | 1.00 (1) | 0.66 (6) | 0.09 (6.5 × 10⁴) | 0.00 (1.5 × 10⁵) | **0.00** (3.4 × 10⁵) |
|     167 | 1.00 (1) | 1.00 (1) | 0.53 (105) | 0.16 (1.3 × 10⁴) | **0.00** (4.0 × 10⁵) |
|     371 | 1.00 (1) | 1.00 (1) | 1.00 (1) | 0.56 (63) | **0.06** (3.8 × 10⁴) |
|     800 | 1.00 (1) | 1.00 (1) | 1.00 (1) | 1.00 (1) | **0.19** (4.7 × 10³) |

Ten-pair z across the 32 draws: median +0.36, +0.26, +2.01 and +3.10 at 97,
167, 371 and 800 letters, with draw-to-draw sd 1.1 to 2.2 and maxima +2.4,
+3.8, +5.8 and +10.5. Draws at z ≥ 3: 0, 2, 6 and 18 of 32.

Predictions: ten-pair retention below 5% at 167 (0.0%, held) and at 371
(**6.25%, refuted**); zero-pair retention above 95% at 167 (100%, held).

### Interpretation (inference)

- The single-draw table in (a) understated the ten-pair signal at 371 and 800
  letters and overstated it at 97. Its 97-letter z +3.3 was a lucky draw: none
  of 32 draws reaches z 3 there.
- The ten-pair IC is not signal-free. It is weak on average and very variable
  across plugboards, presumably because it depends on whether the commonest
  letters happen to be left unplugged. The useful number is retention: about
  1 in 16 keys at the date's pooled 371 letters and none at 167.
- For the indicator sweep this is an upper bound. That sweep also derived the
  message keys through the unknown plugboard, so its true-key IC is degraded
  further, and it pooled three separately keyed messages rather than one
  371-letter message.
- The conclusion of (a) holds in practice: a first stage that keeps the true key
  about 6% of the time cannot carry a search whose null is meant to be evidence.
  The 8-pair column shows where the method would start to work (56% at 371).

### Decision

- Clause (a)'s wording is corrected above. Its single-draw table stays as the
  record of what was run.
- No retention size rescues the stage at 167 letters: the median true key sits
  near rank 4 × 10⁵ of 1.05 × 10⁶.

---

## phase1-companion-calibration-v1

Status: completed 2026-10-03; hypothesis **not supported**. Both null
predictions held and both power predictions failed.

Hypothesis: a body-direct candidate can be confirmed without the indicator by
deciphering each companion message at all 17,576 starts under the candidate's
wheel order, reported rings and plugboard. With the exact plugboard every
companion's best start is at z ≥ 8 against its own start distribution. With
two of ten pairs wrong it still reaches z = 6. No wrong candidate reaches z = 6.
This is review R4.

Refuted by: any of the four predictions failing. A failed null prediction would
have forced a higher threshold before any sweep relied on it.

Configuration:
[experiments/phase1-companion-calibration-v1/config.json](../experiments/phase1-companion-calibration-v1/config.json),
committed in `9bcb697` before the run, together with the z = 6 threshold. Raw
result:
[artifacts/phase1-companion-calibration-v1.json](../artifacts/phase1-companion-calibration-v1.json),
from `scripts/calibrate_companion.py` and regenerated by the drift check.

Run record: seed 20261003, single process, 155 s.

Method: 40 planted daily keys with random wheel orders, rings and ten-pair
plugboards. Each key enciphers a 167-letter swept message and companions of
107 and 97 letters with `enigma.EnigmaI`. Each candidate is presented the way a
complete middle-past-notch sweep would report it: true wheel order and right
ring, left ring A, and the middle ring the rule derives. There are two null
populations. The first is 200 random wheel orders, rings and plugboards against
the planted companions. The second is the 40 candidates the v1 slice retained on
BYQMZ, run against the real FKQLZ and XFEDT.

### Observed

| arm | min over companions of best-start z: median (min) | confirmed at z ≥ 6 |
|---|---:|---:|
| exact plugboard | 13.3 (5.83) | 39/40 |
| 2 of 10 pairs wrong | 6.76 (3.77) | 26/40 |
| 4 of 10 pairs wrong | 4.18 (3.79) | 0/40 |
| random nulls | max 4.60 | 0/200 |
| v1 retained candidates on FKQLZ/XFEDT | max 4.54 | 0/40 |

Predictions: exact plugboard at z ≥ 8 in ≥ 95% (**87.5%, refuted**); two wrong
pairs at z ≥ 6 in ≥ 80% (**65%, refuted**); no random null at z ≥ 6 (held); no
corpus null at z ≥ 6 (held).

### Interpretation (inference)

- The threshold is safe. Across 240 nulls the highest is 4.6, which is about
  where the best of 17,576 near-Gaussian scores is expected, so z = 6 is
  1.4 sd clear of any null seen.
- The check catches an exact key 39 times in 40. The five exact-plugboard
  draws below z = 8 are all held down by one companion, mostly the 97-letter
  one. Draw 23 (5.83) is the one miss. Two causes are plausible: the
  parameterization's middle ring, which deciphers a companion exactly only
  until its left wheel steps, and a short plaintext segment that scores poorly.
  The artifact does not separate them.
- It degrades with the plugboard, not abruptly: two wrong pairs still confirm
  two thirds of the time, which the indicator check cannot do at all.

### Decision

- The z = 6 threshold stands as preregistered and is used by
  `phase1-body-direct-sweep-v2`. It was not tuned on these results.
- Follow-up, not run: scanning the middle ring as well as the start would
  remove the left-step mismatch at 26 times the cost and a slightly higher null
  maximum.

---

## phase1-body-direct-sweep-v2

Status: completed 2026-10-03; hypothesis **not supported** — no retained
candidate is companion-confirmed.

Hypothesis: the 1941-09-30 messages are Enigma I traffic (UKW-B, wheels I–V,
ten pairs) under one daily key with an exact or near equivalent in the
middle-past-notch body-direct space. A complete sweep of that space on BYQMZ
then retains a candidate that the companion-body confirmation accepts:
FKQLZ and XFEDT both at best-start z ≥ 6.

Refuted by: no retained candidate companion-confirmed. The power was stated in
advance: about 0.80 for an ungarbled BYQMZ, which is 82.5% end-to-end power
times 39/40 confirmation, and about 0.15 with one dropped or inserted letter.

Correction after the run (PR review): that product assumed the sweep and the
companion check fail independently, which neither experiment measured, and
both depend on the planted ring geometry. `scripts/joint_power.py` measures
the conjunction instead. It is exploratory, written after the run and
preregistered nowhere. For each end-to-end power draw it enciphers two
companions (107 and 97 letters) under the planted key and runs the companion
check on the candidate the middle-past-notch sweep actually ranked first.
Result
([artifacts/phase1-joint-power-v1.json](../artifacts/phase1-joint-power-v1.json)):
the top candidate is companion-confirmed in exactly the draws the sweep
detected, 33/40 unperturbed (82.5%, 95% interval 68–91%) and 6/40 with one
indel (15%). Confirmation given detection is 1.0 in both cells. Every
confirmed winner also scores above the lowest score v2 retained on BYQMZ
(−8.085), so it would have been checked. The events are positively
correlated, not independent: the draws the check misses with an exact
plugboard are not draws the sweep detects. The joint power is therefore
0.825 rather than 0.80.

Configuration:
[experiments/phase1-body-direct-sweep-v2/config.json](../experiments/phase1-body-direct-sweep-v2/config.json),
committed in `57f679c` before the run. Raw result:
[artifacts/phase1-body-direct-sweep-v2.json](../artifacts/phase1-body-direct-sweep-v2.json).
It is long-running and not regenerated by the drift check.

Run record: code `57f679c`, clean tree. Batched engine, 10 workers on an
i9-10900K. Started 06:43 UTC, finished 23:05 UTC, 16.4 h for 27,418,560
settings (2.15 ms per setting). 1,560 chunks, none resumed. Preflight and both
positive controls passed.

### Observed

- Coverage: 100% of the middle-past-notch reducible space (60 × 26⁴), which
  holds an exact equivalent of 71.6% of daily keys at 167 letters.
- Sweep score distribution over every setting: mean −8.592, sd 0.1068 per
  letter. The maximum is −7.948 (z = 6.03), and rank 2 is −7.952. The top is
  not separated from the rest, and z ≈ 6 is about where the best of 2.7 × 10⁷
  climbs is expected to land. Planted true keys in the end-to-end power run sat
  clear of their nulls by ≥ 6 null sd. Known-key controls score about −6.7.
- Companion confirmation over the 100 retained candidates: none confirmed. The
  best minimum over FKQLZ and XFEDT is z = 4.47 (rank 86). Every candidate lies
  inside the calibration's null range, whose maximum is 4.60.
- Indicator confirmation: 5 of 100 candidates have a compatible ring setting.
  The best pooled date score is −8.80, below every candidate's own sweep score,
  so no candidate is lifted by the other two messages.

Predictions: the deciding prediction failed (no confirmed candidate). The two
conditional predictions (a confirmed candidate is rank 1; it also passes the
indicator check) do not apply.

### Interpretation (inference)

- Under the measured joint power (0.825; lower 95% bound 0.68), a null
  multiplies the odds of the hypothesis by about 0.18 for an ungarbled BYQMZ,
  and by no less favourable than 0.32 at the interval's lower bound. It
  multiplies them by about 0.85 if BYQMZ carries
  one dropped or inserted letter, so most of the remaining standard-Enigma
  probability now sits in a garbled BYQMZ, a key outside the past-notch space's
  reach, or a machine or procedure outside the declared assumptions.
- The three checks agree. The sweep's top is the noise maximum, the companions
  see nothing, and the indicator sees nothing. No candidate looks like a
  near-miss worth a closer look.
- This does not show the date is non-Enigma. Other reflectors, Naval wheels,
  other indicator conventions and a garbled BYQMZ are untested.

### Decision

- The crib-free body-direct route on BYQMZ is exhausted at this rule. The next
  candidates, in order of cost: the windowed climb for a dropped or inserted
  letter (the calibrated weak spot, 15%); the middle-complete rule (nine times
  the cost) for the 28% of keys with no exact equivalent here; and, per the
  review's order, a Bombe only once a crib prior (P3) is quantified.
- `accepted_break` stays false.

> **Correction, 2026-10-03 ([phase1-windowed-climb-power-v1](#phase1-windowed-climb-power-v1)).**
> The 0.15 indel power above came from a slice that held the planted right
> position, and this sweep visited every right position, including the one a
> keystroke away at which everything after an early indel decrypts. Measured with
> the neighbouring positions in the slice, the whole-message climb detects and
> companion-confirms 40% of single-indel draws (32/80) and 87.5% of clean ones
> (70/80). The null therefore multiplies the odds of a standard Enigma I reading
> with a once-garbled BYQMZ by about 0.60, not 0.85, and of an ungarbled one by
> about 0.13. The sweep itself is unchanged.

---

## phase1-windowed-climb-power-v1

Status: completed 2026-10-03; hypothesis **supported** — its three clauses
held. Six of eight predictions held and two were refuted.

Hypothesis: through the middle-past-notch sweep parameterization, on
167-letter messages with a ten-pair stecker, a head-and-tail windowed climb
with W = 117 detects at least 30% of messages carrying one dropped or inserted
letter, at least 10 points more than the whole-message climb on the same draws,
and still detects at least 60% of unperturbed messages.

Refuted by: the W = 117 arm below 30% on the 80 indel draws, or under 10 points
above the whole-message arm on them, or below 60% on the 80 unperturbed draws.

Configuration:
[experiments/phase1-windowed-climb-power-v1/config.json](../experiments/phase1-windowed-climb-power-v1/config.json),
committed in `ebdc233` with the code before the run, together with a rule for
whether a windowed sweep follows. Raw result:
[artifacts/phase1-windowed-climb-power-v1.json](../artifacts/phase1-windowed-climb-power-v1.json).

Run record: seed 20261004, each draw seeded from its (cell, draw) coordinates;
Python 3.10.12, Linux 6.8, i9-10900K, `--jobs 10`, batched engine, 147 s for the
draws and 169 s in all. Code `ebdc233`, clean tree. Preflight passed, including
96 of 96 batched-against-reference windowed climbs (24 samples × 4 window
sizes), and both positive controls passed.

What it measures. The windowed climb (`climb.window`, `stecker_climb.windowed_climb`)
climbs the first and the last W letters separately, each from the identity
plugboard with the usual two phases, and keeps the window with the better score
per letter. One indel at position p leaves the prefix clean under the swept
setting and the suffix clean under the setting one keystroke away, which a
complete sweep visits as the neighbouring right position. Any window inside
either clean stretch fits inside the head or the tail of the same size, so for a
single indel a sliding window adds nothing over these two. The draws are those
of `phase1-end-to-end-power-v1` with three changes: 80 draws per cell, a new
seed, and the right position swept over the planted value and both neighbours,
for every arm, because the tail window needs the shifted setting. Each windowed
arm is judged against its own null (the same windowed climb at the same wrong
settings) at 6 null sd; the whole-message arm against the whole-message null.

### Observed

| arm | unperturbed, 80 draws | one indel, 80 draws | windowed null threshold |
|---|---:|---:|---:|
| whole message (middle past notch) | 71 (88.8%) [80.0, 94.0] | 33 (41.3%) [31.1, 52.2] | −8.04 (whole) |
| head and tail, W = 84 | 32 (40.0%) | 22 (27.5%) | −7.26 |
| W = 100 | 38 (47.5%) | 30 (37.5%) | −7.52 |
| **W = 117 (headline)** | **63 (78.8%) [68.6, 86.3]** | **45 (56.3%) [45.3, 66.6]** | −7.72 |
| W = 134 | 72 (90.0%) | 48 (60.0%) | −7.84 |

Every detection is also the top candidate's exact plugboard, and no arm
recovered an exact plugboard that it then failed to detect.

Paired on the indel draws, whole message against W = 117: both 30, whole only
3, windowed only 15, neither 32. On unperturbed draws: both 60, whole only 11,
windowed only 3, neither 6.

Predictions: W = 117 indel at least 30% (56.3%, held); W = 117 at least 10
points above the whole message on indel draws (+15.0, held); W = 117 clean at
least 60% (78.8%, held); W = 117 loses at most 25 points on clean draws (−10.0,
held); whole-message clean at least 68% (88.8%, held); whole-message indel at
most 30% (**41.3%, refuted**); W = 84 indel at most 15% (**27.5%, refuted**);
W = 134 clean at least 70% (90.0%, held).

Exploratory, not preregistered, by indel position (25, 32 and 23 draws):
before letter 50 the whole message detects 14 and W = 117 18; between 50 and
117, 2 and 8; from 117 on, 17 and 19. W = 134 detects 19, 6 and 23.

Exploratory, not preregistered: `scripts/joint_power.py`, now parameterized by
power artifact and arm, ran the companion check on the top candidate of every
draw, with companions drawn from one seed so the two arms see the same ones
([whole](../artifacts/phase1-joint-power-v2-middle-past-notch.json),
[W = 117](../artifacts/phase1-joint-power-v2-head-tail-117.json)). Detected and
companion-confirmed:

| | unperturbed | one indel |
|---|---:|---:|
| whole message | 70/80, 87.5% [78.5, 93.1] | 32/80, 40.0% [30.0, 51.0] |
| W = 117 | 62/80, 77.5% [67.2, 85.3] | 43/80, 53.8% [42.9, 64.3] |
| W = 117 confirmed where the whole message was not | 3 of 10 | 14 of 48, 29% [18, 43] |

Confirmation given detection is 0.96 to 0.99 in every cell: one or two detected
draws per cell fall short of z = 6 at a companion, as the companion
calibration's 39/40 predicted.

### Interpretation (inference)

- The windowed climb works for one indel. At W = 117 it finds the key in
  about 54% of garbled messages against 40% for the whole message, and in 29% of
  the garbled messages the whole message misses. It costs about 10 points on
  clean messages, most of which the whole-message sweep has already covered.
- **The v1 indel figure was a slice artifact, and v2's stated indel power was
  too low.** v1 swept the planted right position only; a complete sweep visits
  every right position, including the one a keystroke away at which everything
  after an early indel decrypts. With the neighbours in the slice the
  whole-message climb detects 41% of indel draws, not 15%, and 40% jointly with
  the companion check. Most of the gain is for indels before letter 50, where
  the shifted setting decrypts more than two thirds of the message. The v2
  sweep visited those settings, so 0.40 is the better estimate of its power for
  one indel, and its null multiplies the odds of a once-garbled standard
  Enigma reading by about 0.60, not 0.85.
- The same widening raised the clean whole-message rate from 82.5% to 88.8%
  (87.5% jointly), within v1's interval, so v2's clean power is better put at
  about 0.85 to 0.875 than 0.825.
- An indel in the middle third is the remaining hole: 2 of 32 for the whole
  message and 8 of 32 at W = 117, because neither clean stretch is long enough
  for ten pairs.
- W = 84 did better than predicted (27.5%) and W = 134 did best of all on indel
  draws (60.0%). The preregistered rule fixes W = 117 for a sweep, so W = 134's
  lead is a hypothesis for a future calibration with a fresh seed, not a
  choice made here; W = 117 and W = 134 are within each other's intervals.
- The windowed null threshold is higher per letter than the whole-message one
  (−7.72 against −8.04 at W = 117), as expected from scoring fewer letters and
  taking the better of two windows.
- Limits: one planted plaintext, single indels only, 80 draws per cell. The
  joint figures are post hoc. The 6σ threshold stands in for the extreme of a
  full sweep, which for a windowed sweep is the extreme of twice as many window
  scores.

### Decision

- The preregistered sweep rule is met (all three of its predictions held), so
  `phase1-body-direct-sweep-v3`, a complete middle-past-notch sweep of BYQMZ
  with the W = 117 windowed climb, is preregistered next with this run's W = 117
  rates as its power.
- The v2 entry's stated indel power is corrected below; the v1 decision's
  "0.15 with one indel" is superseded by 0.40.
- Gate added after review (PR #12), while v3 was running: the positive
  controls called `body_direct_climb`, which ignores `climb.window`, so they
  certified only the whole-message climb. With a window configured each control
  message at least ten letters longer than the window now also runs the windowed
  climb, exactly as a sweep does, on 12 seeded planted plugboards at the
  control's setting (clean, a deletion at letter W, and a deletion before the
  tail read one keystroke later), and must recover at least 3 exactly. A single
  fixed key would be a coin-flip gate: at the true setting neither 117-letter
  window recovers control B1's own key, while 134 letters and more do, and on
  the planted keys 7 of 12 were recovered. A broken slicing or window choice
  recovers none (unit-tested). v3's chunks were computed at `6b6ad2f`, whose
  sweep path this change does not touch; once they finish the runner is
  rerun at the commit carrying the gate, which re-runs the preflight and every
  control, resumes all 1,560 chunks from the checkpoint (its fingerprint is
  unchanged) and confirms the candidates. A failed windowed control there
  withholds the v3 result.
- Benchmark, exploratory (`scripts/benchmark_sweep.py --window`, 13,520
  settings, 10 workers): 3.41 ms per setting windowed against 2.97 ms whole
  message in the same run, 1.15×. Scaled from v2's measured 2.15 ms the
  windowed sweep takes about 19 hours; at the benchmark's own rate, 26 hours.

---

## phase1-body-direct-sweep-v3

Status: completed 2026-10-04; hypothesis **not supported** — no retained
candidate is companion-confirmed.

Hypothesis: the 1941-09-30 messages are Enigma I traffic (UKW-B, wheels I–V,
ten pairs) under one daily key with an exact or near equivalent in the
middle-past-notch space, and BYQMZ's key is one the whole-message sweep v2
could miss, most plausibly because one letter of BYQMZ was dropped or
inserted. A complete sweep of the same space with the W = 117 head-and-tail
windowed climb then retains a candidate that FKQLZ and XFEDT both confirm at
best-start z ≥ 6.

Refuted by: no retained candidate companion-confirmed. Stated power, from
[phase1-windowed-climb-power-v1](#phase1-windowed-climb-power-v1) and its
post hoc joint check: 0.54 with one indel and 0.78 clean; conditional on v2's
null, about 0.29 with one indel and 3 of 10 clean.

Configuration:
[experiments/phase1-body-direct-sweep-v3/config.json](../experiments/phase1-body-direct-sweep-v3/config.json),
committed in `6b6ad2f` before the run. Raw result:
[artifacts/phase1-body-direct-sweep-v3.json](../artifacts/phase1-body-direct-sweep-v3.json),
long-running and not regenerated by the drift check.

Run record: the sweep ran from a clean checkout at `6b6ad2f`, batched engine,
10 workers on the i9-10900K, from 02:13 to 19:10 UTC on 2026-10-04: 16.95 h for
27,418,560 settings (2.22 ms per setting, 1.03 times v2's rate; the benchmark
had projected 1.15). 1,560 chunks, none resumed. Preflight (96 windowed parity
climbs) and both whole-message positive controls passed.

Deviation from the preregistration: during the run a PR review pointed out
that the positive controls never exercised the windowed climb, and a windowed
known-key gate was added in `7ae72f8` (see the decision list of
[phase1-windowed-climb-power-v1](#phase1-windowed-climb-power-v1)). After the
sweep finished, the runner was rerun at `7ae72f8` from a clean tree. It re-ran
the preflight and every control, and the windowed control recovered 7 of 12
planted keys against a floor of 3. It resumed all 1,560 chunks from the
checkpoint with the same fingerprint, ran none, and repeated both
confirmations. Its retained candidates and score distribution are identical to
the first run's; the committed artifact is the re-gated one, so its timing
fields describe the 226-second resume, not the sweep. The first run's
artifact is kept outside the repository and differs only in the controls and
the timing.

### Observed

- Coverage: 100% of the middle-past-notch reducible space, as in v2.
- Sweep score distribution over every setting (better of two windows): mean
  −8.287, sd 0.1147 per letter. The maximum is −7.573 (z = 6.22), rank 2 is
  −7.586 (z = 6.11), and the scores below fall off smoothly. Planted true keys
  scored about −6.5 per letter in the calibration.
- All 100 retained candidates won on the head window. BYQMZ's single masked
  letter is at position 28, inside the head window only; it breaks the n-gram
  chain, so the head scores fewer and therefore fewer negative terms per letter
  and sits slightly higher on noise. Planted calibration draws had no masked
  letters. A true key scoring near −6.6 in either window would still be
  retained, since the lowest retained score is −7.699.
- None of the 100 retained plugboards is one v2 retained.
- Companion confirmation: none confirmed. The best minimum over FKQLZ and XFEDT
  is z = 4.64 (rank 27; FKQLZ 4.79, XFEDT 4.64), against a threshold of 6 and a
  calibration null maximum of 4.60.
- Indicator confirmation: 7 of 100 candidates have a compatible ring setting;
  the best pooled date score is −8.94 per letter.

Predictions: the deciding prediction failed (no confirmed candidate). The two
conditional ones (a confirmed candidate is rank 1; its plugboard is new to v2)
do not apply. The top score lies between z = 5 and z = 7 (6.22, held).

### Interpretation (inference)

- The three checks agree again: the sweep's top is the noise maximum, the
  companions see nothing, and the indicator sees nothing. Rank 27's 4.64 is a
  hair above the calibration's 240-null maximum of 4.60, which 100 more draws
  would be expected to reach; it is 1.4 sd short of the threshold.
- On the planted draws, a key was confirmed by v2's climb or v3's in 73 of 80
  clean messages and 46 of 80 with one indel. Taken together the two nulls
  multiply the odds of a standard Enigma I reading in this space by about 0.09
  for an ungarbled BYQMZ and about 0.43 for one with a single dropped or inserted
  letter. Both figures reuse post hoc joint measurements and one planted
  plaintext.
- What is left for a standard reading is mostly a BYQMZ indel in its middle
  third (8 of 32 windowed, 2 of 32 whole on planted draws), two or more faults,
  a key with no exact equivalent in the past-notch space, or a machine or
  procedure outside the declared assumptions.
- The masked letter's head-window bias is a property of this message, not of
  the method. It did not cost power here, but a windowed score compared across
  windows should correct for scored n-grams, not only letters, if it is reused.

### Decision

- The windowed body-direct route on BYQMZ is done at this rule. Remaining
  candidates, in order of cost: the middle-complete rule (nine times v2's cost)
  for keys with no exact equivalent; a climb that can see a middle-third indel,
  which would have to use both the head setting and the shifted tail setting
  at once (two tables per candidate, a split point searched); and, per the
  review, a Bombe only once a crib prior (P3) is quantified.
- `accepted_break` stays false.

---

## phase1-fkqlz-length-calibration-v1

Status: completed 2026-10-06; hypothesis **supported** — at 107 letters the
climb recovers fewer than 24 of 32 plugboards, at 10 of 32. Five of seven
predictions held and two were refuted.

Hypothesis: FKQLZ, at 107 letters, is below the length at which the body-direct
stecker climb reliably recovers a ten-pair plugboard. Handed the true wheel
order, rings and start position, with the same two-phase climb and the same
constructed plaintext prefix as [phase1-stecker-calibration-v1](#phase1-stecker-calibration-v1),
it recovers the exact plaintext in fewer than 24 of 32 draws (75%) at 107
letters.

Refuted by: 24 or more of 32 draws recovered exactly at 107 letters. The climb
is handed the true setting, so the rate bounds the stecker stage and not an
end-to-end sweep.

Configuration:
[experiments/phase1-fkqlz-length-calibration-v1/config.json](../experiments/phase1-fkqlz-length-calibration-v1/config.json),
preregistered 2026-10-04 and not edited since. Raw result:
[artifacts/phase1-fkqlz-length-calibration-v1.json](../artifacts/phase1-fkqlz-length-calibration-v1.json).

Run record: `python3 phase1_stecker.py --config experiments/phase1-fkqlz-length-calibration-v1/config.json`,
single process, 2026-10-06 05:06:19 to 05:08:36 UTC (136.8 s), Python 3.10.12,
Linux 6.8, 20 CPUs. Code `03b8670` on `claude/phase1-fkqlz-and-crib-prior`,
**clean tree** (`code.dirty` is false, no status lines). Preflight and both
positive controls passed. Nothing else was running on the host (load average
about 2 before the run).

### Predictions

Scored before any reading of the result.

| id | prediction | measured | |
|---|---|---|---|
| fkqlz-below-reliable (decides) | 107 letters: fewer than 24 of 32 | 10 of 32 | **held** |
| fkqlz-above-xfedt | 107 letters: at least 4 of 32 | 10 of 32 | held |
| fkqlz-interval | 107 letters: between 4 and 20 of 32 | 10 of 32 | held |
| anchor-97 | 97 letters: at most 8 of 32 | 12 of 32 | **refuted** |
| anchor-167 | 167 letters: at least 30 of 32 | 28 of 32 | **refuted** |
| plugboard-matches-plaintext | exact plugboards equal exact plaintexts in every cell | 12/12, 10/10, 28/28 | held |
| other-stages-reproduce | the three copied stages reproduce v1 exactly | see below | held, on a reading stated below |

Prediction 7. `ic_stage_calibration` and `indicator_gradient_control` are
identical to v1's. `screening_calibration` is identical except for
`seconds_per_setting`, which differs in all 10 rows (for example 0.018689
against 0.020205) because it is measured wall-clock time on this host at this
load. On all 18 claim paths that `artifact_claims.json` declares for those
three stages, the repository's own `check_artifacts.compare` finds no
difference. I scored it held on the reading that a timing is not a calibration
value, and that no value changed is what "code drift" would mean here. That
reading is mine. On the literal reading, whole-dictionary equality, the
prediction is refuted by the timing field alone.

### Observed

| letters | recovered exactly (plaintext and plugboard) | rate, Wilson 95% | median z over wrong settings |
|---:|---:|---:|---:|
| 97 | 12 of 32 | 37.5% [22.9, 54.7] | 3.13 |
| **107** | **10 of 32** | **31.3% [18.0, 48.6]** | 1.57 |
| 167 | 28 of 32 | 87.5% [71.9, 95.0] | 21.76 |

Ten pairs, 32 key draws per cell, 8 wrong-setting nulls per draw, the same
plaintext cut to each length as a prefix. `recovers_at_target_scale` is false
and no length recovers every draw.

Branch of `decision_rule`: 10 of 32 falls in **8 to 23 of 32**. FKQLZ is a
companion only, as before: it confirms BYQMZ candidates and is not swept alone.
The count is not 24 or more, so no end-to-end power control at 107 letters was
written. The STATUS line saying FKQLZ was not measured directly is replaced by
this rate.

Exploratory, not preregistered: 97 against 107 letters, 12 of 32 against 10 of
32, Fisher exact two-sided p = 0.79.

### Interpretation (inference)

- Ten more letters over 97 do not show a measurable gain here. The 107 count is
  below the 97 count, with heavily overlapping intervals and a lower median z.
  The preregistered "helps measurably" prediction held only in the weak sense
  the threshold of 4 of 32 allowed.
- The v1 figure for 97 letters, 1 of 8, was a low draw. Its interval
  (about 2 to 47%) contains 12 of 32. XFEDT's handed-setting rate is nearer
  four in ten than one in eight. It is still far from reliable, and an
  end-to-end sweep would do no better.
- The v1 figure for 167 letters, 8 of 8, was a small sample. At 32 draws the
  rate is 87.5%, not 100%. STATUS and the earlier entries that say the climb
  recovers the key "on every trial" at 167 letters describe the 8 draws, not the
  rate. The windowed-climb run measured clean whole-message detection through
  the sweep at 71 of 80 (88.8%, [80.0, 94.0]); that is the same size as this
  handed-setting rate on different draws. It would be a mistake to read the
  handed rate as a strict cap: phase1-end-to-end-power-v1 detected 39 of 40
  draws when a sweep visited many near-equivalent settings, each a fresh climb.
- Limits: one plaintext, cut as prefixes, so the 97 and 107 cells share their
  first 97 letters and their results are not independent of what those letters
  say; one key draw per (cell, draw); the climb is handed the true setting.

### Decision

- FKQLZ is not swept alone. Its companion role is unchanged.
- XFEDT and FKQLZ both remain below the length at which a body-direct climb is
  reliable (31% and 38% handed, against 88% at 167 letters).

---

## Choosing the next Phase 1 experiment (2026-10-06)

Written after [phase1-fkqlz-length-calibration-v1](#phase1-fkqlz-length-calibration-v1)
and [phase2-crib-prior-v1](phase2-experiment-history.md#result-run-2026-10-06),
which decide what is on the list. Nothing in this section was run.

### What the two results leave

- The Bombe is not a candidate: G1 to G3 fail on the held-out check, and no
  crib prior can be built from published plaintext.
- An FKQLZ sweep is not a candidate: 10 of 32 at 107 letters is under the
  24-of-32 line, and a handed-setting rate is an upper bound.
- Two crib-free steps are left for BYQMZ, after v2 and v3 were both null:
  **A**, the middle-complete ring rule, and **B**, a climb that sees a
  middle-third indel by using the head setting, the shifted tail setting and a
  searched split point.

### Facts the comparison rests on

- A's cost. The complete rule has 246.8 million reducible settings against 27.4
  million, a ratio of 9.0. At v3's measured 2.22 ms per setting on 10 workers
  that is 152.6 host-hours; the earlier "150 to 230" brackets it.
- A's power is not unmeasured, contrary to the v3 decision list and the
  phase2-crib-prior-v1 configuration. `phase1-end-to-end-power-v1` ran a
  `middle_complete` arm: 39 of 40 clean (97.5%, interval 87.1 to 99.6) and 11
  of 40 with one indel (27.5%), against 33 of 40 and 6 of 40 for
  `middle_past_notch` on the same draws, whole-message climb. That slice held
  the planted right position only; adding the neighbouring right positions
  raised the past-notch indel rate from 15% to 41%, so A's indel figure is
  probably low too. What has not been measured is A on the keys v2 and v3
  already missed, with the W = 117 climb, which is the only thing that matters
  for choosing it.
- What v2 and v3 already cover on planted draws: 73 of 80 clean and 46 of 80
  one-indel keys are confirmed by one or the other.
- B's headroom. A middle-third indel (letters 56 to 111) is the hole: on planted
  draws the whole-message past-notch climb gets 2 of 32 and W = 117 gets 8 of
  32 (exploratory split by position, 32 draws between letters 50 and 117). B's
  code and cost do not exist.
- The stecker stage, handed the true setting, recovers 28 of 32 at 167 letters.

### Comparison

Expected detection per host-hour, in the convention of G4 (conditional
probability given a standard reading and both nulls, divided by host-hours;
v3's was 0.29 in about 22 host-hours, 0.013). The comparison needs three inputs
the repository does not have: A's and B's detection among the keys v2 and v3
missed, B's cost, and q, the prior that BYQMZ carries one dropped or inserted
letter. The control below measures the first and bounds the second. Nothing
measures q.

Illustration with **placeholder inputs, not measurements**: 9% of clean and 42%
of indel keys missed (from 73/80 and 46/80), A detecting 60% of the clean and
15% of the indel keys it is given, an oracle for B detecting 75% of the indel
keys, B costing 4 times v3:

| q (P of one indel) | A, per host-hour | B ceiling, per host-hour | break-even B cost, in multiples of v3 |
|---:|---:|---:|---:|
| 0.05 | 0.0034 | 0.0022 | 2.6 |
| 0.10 | 0.0029 | 0.0038 | 5.2 |
| 0.20 | 0.0023 | 0.0060 | 10.2 |
| 0.35 | 0.0018 | 0.0079 | 17.4 |
| 0.50 | 0.0015 | 0.0091 | 24.2 |

Inference from the illustration, to be checked by the control: with these
inputs the choice turns on q and on B's cost, B is ahead above about q = 0.1,
and both are well under v3's 0.013 per host-hour. That is expected, since each
step now buys detection only among keys two sweeps already missed.
Speculation: that q is large. BYQMZ carries a masked letter at position 28,
which says its transcription is imperfect and says nothing about a dropped
letter.

### What the choice does not cover

Every number above assumes a standard Enigma I with wheels I to V as wired.
The cited paper's authors suspect that Batch C used differently wired wheels
([STATUS](STATUS.md); their method also fails on short messages generally). If
that is so, both A and B search a space that does not contain the key, and the
better use of host time is a test of the assumption. The preregistered
decision rule has a branch for it; no cheap test is designed here.

---

## phase1-middle-complete-power-v1 (preregistered)

Status: preregistered 2026-10-06; **run 2026-10-06, see [Result](#result-run-2026-10-06-1)**. Configuration:
[experiments/phase1-middle-complete-power-v1/config.json](../experiments/phase1-middle-complete-power-v1/config.json).
Code committed before it in `b8f1c3a` (an `oracle` repair option for the power
runner, and `scripts/conditional_power.py`), unit-tested on synthetic draws and,
for existing arms, compared against the previous runner on six draws with
identical results.

Why this one. It is the cheapest control that separates A from B, about 30 to
40 minutes on 10 workers against 150 hours for A's sweep, and it needs no new
climb. It runs the two past-notch climbs (v2's and v3's), the complete rule
with each, and an oracle that undoes the indel at its true position, on 400
clean and 400 one-indel draws at 167 letters with ten pairs. The draws neither
past-notch climb detects are the planted-key stand-in for both sweeps being
null; the experiment asks what A and the oracle detect among them.

Hypothesis. (i) The complete rule with the W = 117 climb detects at least half
of the clean draws both past-notch climbs miss (C1). (ii) On one-indel draws
with the indel in letters 56 to 111 that both miss, it detects at most 20%
(C2), while the oracle detects at least 60% (C3): the rings and the split
point address different keys.

Refuted by: C1 below 50%, C2 above 20%, or C3 below 60%, each scored on strata
of at least 25 draws; a smaller stratum is reported as not estimable. Six
marginal predictions are also scored by the runner (replications of the
earlier past-notch rates, the complete rule's clean rate, and the oracle's
indel rate), each refuting only itself.

Decision rule, fixed now. The script reports, for fault priors 0.05, 0.1, 0.2,
0.35 and 0.5, A's conditional detection per host-hour and B's ceiling, and the
break-even cost k* in multiples of v3 at which a split-point sweep ties the
complete-rule sweep.

- C1 and C3 both refuted: neither is built; the next step tests the
  standard-reading assumption.
- Only C3 refuted: the complete-rule sweep is preregistered at its measured
  conditional rate.
- Only C1 refuted: a split-point climb is built, calibrated on this control's
  draws and benchmarked before any sweep.
- Neither refuted: B first if k* at q = 0.2 is at least 4, else A first.
  q = 0.2 and a cost of 4 are values declared now so the rule is fixed; neither is
  measured, and the k* at every q is printed so another belief can be applied
  without a rerun.

Limits, in the configuration: "missed by both" is defined on the same draws
that score the other arms; the oracle is an upper bound that is handed the
position; 400 draws leave about 36 clean missed draws, so a stratum rate
carries an interval about 0.3 wide; only a single indel is modelled.

> **Amended 2026-10-06, before any run (PR review).** As first committed, the
> oracle arm was judged against the cell's pooled whole-message null, which is
> climbed on the unrepaired message. A repaired deletion carries a mask that
> breaks the n-gram chain and a repaired insertion is one letter shorter, so
> that null does not fit the oracle's score, and C3 could misclassify. A
> repaired arm now gets its own null, as a windowed arm does: the same climb,
> at the same wrong settings, on the repaired message. On clean draws repair
> is the identity and the two nulls coincide. The other arms are bit-identical
> to the previous runner on clean, deletion and insertion draws. The cost is
> eight more whole-message climbs per indel draw, small beside the sweeps.

Run command, not run:

```bash
python3 phase1_stecker.py --config experiments/phase1-middle-complete-power-v1/config.json --jobs 10
python3 scripts/conditional_power.py
```

### Result (run 2026-10-06)

Status: completed; hypothesis **refuted by C2, by 0.3 points**. C1 and C3 held.
Four of six marginal predictions held and two were refuted. The
preregistered decision rule selects the split-point climb at q = 0.2.

Run record: `phase1_stecker.py --config experiments/phase1-middle-complete-power-v1/config.json --jobs 10`
(started in the terminal pane by the maintainer), 2026-10-06 13:39:16 to
14:22:37 UTC, 2,601 s, Python 3.10.12, 10 workers. Code `68b0fa3` on `master`,
**clean tree**. Preflight and both positive controls passed. Raw result:
[artifacts/phase1-middle-complete-power-v1.json](../artifacts/phase1-middle-complete-power-v1.json)
(long-running); conditional analysis:
[artifacts/phase1-middle-complete-power-v1-conditional.json](../artifacts/phase1-middle-complete-power-v1-conditional.json),
from `scripts/conditional_power.py`, regenerated by CI.

Amendment before the run, disclosed in the configuration: after PR review, two
commits (`c2b4923`, `3c8960c`) made the oracle arm be judged against its own
null, because the repaired message's mask or shorter length does not fit the
unrepaired message's null. Predictions, strata and decision rule did not
change. The two past-notch arms give identical results before and after
the runner change on 8 draws, so it does not explain the replication shortfall
below.

#### Predictions

Scored by the runner (marginal) and by `scripts/conditional_power.py`
(conditional), before any reading of the result.

| id | prediction | observed | |
|---|---|---|---|
| past-notch-whole-clean-replicates | whole-message past-notch, clean, at least 80% | 79.0% | **refuted** |
| past-notch-w117-indel-replicates | W = 117 past-notch, one indel, at least 45% | 42.5% | **refuted** |
| complete-whole-clean-replicates-v1 | complete rule, whole, clean, at least 90% | 95.3% | held |
| complete-w117-clean-at-least-85pct | complete rule, W = 117, clean, at least 85% | 89.8% | held |
| oracle-indel-at-least-60pct | oracle, one indel, at least 60% | 77.0% | held |
| oracle-beats-w117-on-indel | oracle at least 15 points above past-notch W = 117, indel | +34.5 | held |
| **C1** | complete W = 117 detects at least 50% of clean draws both past-notch climbs miss | 34 of 57, 59.6% | **held** |
| **C2** | complete W = 117 detects at most 20% of middle-third indel draws both miss | 24 of 118, 20.3% | **refuted** (by 0.3 points) |
| **C3** | oracle detects at least 60% of the same draws | 83 of 118, 70.3% | **held** |

Strata were all above the 25-draw minimum. The hypothesis is refuted by C2
alone, under the rule as written; C2's miss is 24 draws against 23.6 allowed.

#### Observed

400 draws per cell, 167 letters, ten pairs. Detected, with 95% Wilson interval:

| arm | settings per draw | clean | one indel |
|---|---:|---:|---:|
| past_notch_whole (v2's climb) | 45 | 316, 79.0% [74.7, 82.7] | 147, 36.8% [32.2, 41.6] |
| past_notch_w117 (v3's climb) | 45 | 303, 75.8% [71.3, 79.7] | 170, 42.5% [37.8, 47.4] |
| complete_whole | 405 | 381, 95.3% [92.7, 96.9] | 222, 55.5% [50.6, 60.3] |
| complete_w117 | 405 | 359, 89.8% [86.4, 92.4] | 258, 64.5% [59.7, 69.0] |
| oracle_past_notch | 45 | 316 (the repair is the identity) | 308, 77.0% [72.6, 80.9] |

Draws neither past-notch climb detects (the planted-key stand-in for v2 and v3
both null): 57 of 400 clean (14.3%), and 192 of 400 with one indel (48.0%),
of which 118 have the indel in letters 56 to 111 and 74 elsewhere. What each arm
detects among them:

| stratum | complete_whole | complete_w117 | oracle |
|---|---:|---:|---:|
| clean, 57 | 44 (77.2%) | 34 (59.6% [46.7, 71.4]) | 0, by construction |
| indel, middle third, 118 | 6 (5.1%) | 24 (20.3% [14.1, 28.5]) | 83 (70.3% [61.6, 77.8]) |
| indel, elsewhere, 74 | 37 (50.0%) | 33 (44.6% [33.8, 55.9]) | 39 (52.7% [41.5, 63.7]) |

Decision rule: C1 and C3 both held, so the "both" branch applies. At the nominal
q = 0.2 the break-even cost k* is 5.69, at least the assumed split-point cost
of 4, so the **split-point climb is built and benchmarked first**.

Yield model (the script prints these, none is a prediction). Conditional
detection per host-hour for the complete rule at 152.6 host-hours, and the
oracle ceiling for a split-point climb:

| q | complete rule, probability | per host-hour | split-point ceiling, probability | k* |
|---:|---:|---:|---:|---:|
| 0.05 | 0.551 | 0.0036 | 0.096 | 1.56 |
| 0.10 | 0.515 | 0.0034 | 0.173 | 3.02 |
| 0.20 | 0.460 | 0.0030 | 0.291 | 5.69 |
| 0.35 | 0.403 | 0.0026 | 0.410 | 9.14 |
| 0.50 | 0.366 | 0.0024 | 0.490 | 12.07 |

Exploratory, not preregistered: the paired comparison with the earlier past-notch
measurements. The whole-message clean rate is 79.0% on 400 draws against 88.8%
on 80 (phase1-windowed-climb-power-v1), 2.4 standard errors lower; the W = 117
indel rate is 42.5% against 56.3%, 2.3 standard errors lower.

#### Interpretation (inference)

- The complete rule does what its extra settings are for. Among clean draws
  both past-notch climbs miss it recovers about 60%; among the indel draws they
  miss it recovers 30% overall (57 of 192, [23.7, 36.5]), mostly where the
  indel is outside the middle third (45% there, 20% in it).
- The two remedies address different keys. In the middle third, where the
  past-notch climbs miss 118 of 143 indel draws, rings add 20% and an oracle
  repair 70%. That is the headroom C3 was written to find, and it is a ceiling:
  a real search for the split point pays for finding it in its null and will do
  worse than 70%.
- **The choice is sensitive to q.** The rule picks the split-point climb at q =
  0.2 with k* 5.69 against an assumed cost of 4. By interpolation k* crosses 4
  at q of about 0.14, so for a prior on a dropped or inserted letter under about
  one in seven the complete-rule sweep comes first. Neither q nor the cost of 4
  is measured. If the climb costs more than 5.7 times v3, the rule's own
  break-even reverses it at q = 0.2.
- Neither is cheap per host-hour. The complete rule yields about 0.003 per
  host-hour at q = 0.2 (46% conditional probability over 153 hours), the
  split-point ceiling about 0.004 at the assumed cost, against v3's 0.013 (0.017
  at its measured 16.95 hours). The same G4 reference now has a measured crib-free
  rate to replace 0.013 with, 0.003 to 0.004.
- The earlier past-notch figures were probably optimistic. This control puts
  v2's climb at 79% clean and v3's windowed climb at 42.5% with an indel, and
  the draws missed by both at 14.3% clean and 48.0% with an indel, where 80-draw
  runs gave about 9% and 42%. Taken together, the two nulls multiply the odds of a
  standard reading by about 0.14 ungarbled and 0.48 with one indel, not the 0.09
  and 0.43 stated after v3. The cause is not identified: the amended runner
  reproduces the old results on the unchanged arms, the plaintext and slice
  are the same, and the draws are new, so sampling in the 80-draw runs is the
  simplest reading, at a 2.3 to 2.4 standard error gap it is not a comfortable one.
- Limits as preregistered: "missed by both" is defined on the same draws that
  score the other arms; one plaintext; single indel only; the oracle is handed
  the position; a pooled wrong-setting null stands in for the sweep's 27.4
  million.

#### Decision

- Per the preregistered rule: build a split-point climb, calibrate it on
  this control's draws, and benchmark its cost before any sweep. The benchmark
  decides, because it replaces the assumed multiplier of 4 and the sweep
  goes to whichever of the two is cheaper at the maintainer's q.
- `accepted_break` stays false.
- The stated powers of v2 and v3, and the odds multipliers in STATUS, are
  corrected by the figures above.
- Both candidates assume wheels I to V as wired, which the cited paper's
  authors doubt for Batch C.

---

## Split-point climb: build and benchmark (2026-10-06)

Exploratory engineering and measurement, preregistered nowhere. It carries out
the decision of [phase1-middle-complete-power-v1](#phase1-middle-complete-power-v1-preregistered):
build a split-point climb and benchmark its cost before any sweep.

What it is (`stecker_split.py`). One dropped or inserted letter at position p
leaves the letters before it aligned with the swept setting and the letters
after it aligned with the same machine one keystroke on (a dropped letter) or one
back (an inserted one). The position table of a single setting holds those
keystrokes, so the shifted setting needs no sweep of its own. The climb scores
`max` over (clean, a dropped letter at p, an inserted letter at p) of the
repaired message, with a mask at the fault, and climbs the plugboard against that
best hypothesis, so the position is searched inside every evaluation. The
n-gram phase scores every p with prefix and suffix sums; the
index-of-coincidence phase, which a climb from the identity plugboard needs, scores a
grid of 32 letters. Phases, move set and stopping rule are `BatchedClimber`'s.

Fact: tests. The batched objectives equal a brute-force reference that scores
every hypothesis through the existing scorer on a custom table and a masked
body, to six places for the n-gram objective and nine for the coincidence
objective, with the same best hypothesis, on clean, dropped-letter and
inserted-letter messages and on a message that already carries masks. Existing
power arms are bit-identical before and after the change (6 and 8 draws against
the previous runner). A clean-wheel install needed `stecker_split` declared in
`pyproject.toml`; the install test caught that.

Fact: a design correction. A mask drops n-gram terms, every term is negative, and
so a masked hypothesis beat the clean one at the true plugboard and a fault was
placed near an end for nothing. Crediting each masked hypothesis the value of a
term on wrong-setting text (-8.66, the control's climbed null mean per letter),
one term for a dropped letter and two for an inserted one, removed the bias. A
residual effect is expected and tested for: a fault hypothesis within about 10
letters of an end swaps few correct terms for wrong ones, so the best of about
330 noisy hypotheses sometimes wins there by chance.

Fact: development result. 60 planted one-indel 167-letter draws from seeds not
used by any control, climbed at the true setting (a stecker-stage measure, not
a sweep): split 39 of 60 (65%), whole-message 14 of 60, W = 117 16 of 60. With
the indel in letters 56 to 111: 20 of 28 against 1 and 4. Elsewhere: 19 of 32
against 13 and 12. In the 7 successes among the first 12 of these draws it named the
fault's kind correctly and placed it within 3 letters; the other 48 draws were
not checked for that.

Fact: cost. Single process, at the true setting, the split climb was 4.3 times the
windowed climb (74 against 17 ms). In the 10-worker sweep first measured it was
22.0 ms per setting against 3.59 for windowed, **6.1 times**, because its arrays,
several megabytes per evaluation, do not fit a core's cache once every worker
runs: a worker took 199 ms per climb against 67.5 ms alone. Processing the
candidates 64 at a time changes no number and took it to 101 ms. Final,
`scripts/benchmark_sweep.py --settings 6760 --jobs 10 --compare --split-grid 32
--repeats 2`, interleaved on this host:

| climb | ms per setting | against windowed | against whole message |
|---|---:|---:|---:|
| whole message | 2.90 | 0.80 | 1.00 |
| W = 117 (v3's) | 3.62 | 1.00 | 1.25 |
| **split point** | **10.44** | **2.89** | **3.59** |

Applied to v3's 16.95 host-hours the ratio projects about 49 host-hours for a
split-point sweep of the same 27.4 million settings, against about 153 for the
complete rule. The benchmark's absolute rates include process start-up on a
small slice (v3's real rate was 2.22 ms), so the ratio, not 10.44 ms, is the
figure to carry. The 2.89 replaces the control's assumed multiplier of 4.

Inference. The control's break-even said a split-point sweep beats the complete
rule on cost at the nominal q = 0.2 if it costs less than 5.7 times v3, and at q =
0.1 if it costs less than 3.0. At 2.9 it is under both. That says nothing yet
about whether it detects what its oracle ceiling promises end to end; the
development rates are a stecker-stage figure on a different set of draws.
`phase1-split-point-power-v1` is preregistered to measure that and has not run.

> **Update, 2026-10-07.** It has run, and its deciding predictions were both
> refuted; the preregistered rule drops the climb. See
> [its result](#result-run-2026-10-07).

---

## phase1-split-point-power-v1 (preregistered)

Status: preregistered 2026-10-06; **run 2026-10-07, see [Result](#result-run-2026-10-07)**. Configuration:
[experiments/phase1-split-point-power-v1/config.json](../experiments/phase1-split-point-power-v1/config.json),
analysis `scripts/split_power.py`, both committed before any run.

It reruns the control's 800 draws (same seed, so the same planted keys and
faults) with the split-point climb as an arm, rerunning the two past-notch arms
and the oracle so the artifact stands alone. The complete-rule outcomes come
from the control's artifact; the script refuses to go on if any draw was
planted differently and counts any past-notch arm that does not reproduce the
control exactly.

Hypothesis. The split-point climb detects at least 45% of the middle-third-indel
draws both past-notch climbs miss (the control: complete rule 20.3%, oracle
70.3%, 118 draws) and at least 30% of the elsewhere-indel ones (44.6% and 52.7%,
74 draws), at about 2.9 times v3's cost against 9 for the complete rule. S1 and
S2 decide it; S3 (at most 40% of the clean draws both miss, where the complete
rule's 59.6% is ring coverage) and four marginal predictions refute only
themselves.

Decision rule, fixed now: both S1 and S2 refuted drops the climb and the
complete-rule sweep is preregistered; otherwise the sweep with the higher
conditional detection per host-hour at q = 0.2 is preregistered next, with its
measured rate as its stated power. No sweep is run on this evidence.

Disclosed in the configuration: the development result above, the three
changes made after looking at development draws, and that the thresholds were
chosen against the control's published complete-rule and oracle figures; the
split-point climb itself had not been run on any of the control's draws.

Run command, not run:

```bash
python3 phase1_stecker.py --config experiments/phase1-split-point-power-v1/config.json --jobs 10
python3 scripts/split_power.py
```

### Result (run 2026-10-07)

Status: completed; hypothesis **refuted by both deciding predictions**. S1
missed by two draws and S2 by five; S3 held. Two of four marginal predictions
held (the replications) and two were refuted. The preregistered rule drops the
split-point climb and preregisters the complete-rule sweep next.

Run record: `phase1_stecker.py --config experiments/phase1-split-point-power-v1/config.json --jobs 10`,
then `scripts/split_power.py --output artifacts/phase1-split-point-power-v1-split.json`,
2026-10-07 05:59:45 to 06:19:58 UTC, 1,198 s by the runner's clock, 3.3
CPU-hours, Python 3.10.12, numpy 2.2.6, 10 workers on the i9-10900K. Code
`c54f42a` on `claude/phase1-split-point-power-result` (`master` with no new
commit), **clean tree**. Preflight and both positive controls passed.

The host was not idle: an LM Studio `llama-server` and an unrelated `pytest`
run were using CPU during it. The run constraint asked for an idle host. The
runner reads the clock only to record elapsed time, and every outcome is fixed
by the seed, so this affects the 1,198 s and nothing else; the cost figure the
analysis uses is the benchmark's 2.89, measured before this run.

Raw result:
[artifacts/phase1-split-point-power-v1.json](../artifacts/phase1-split-point-power-v1.json)
(long-running); split analysis:
[artifacts/phase1-split-point-power-v1-split.json](../artifacts/phase1-split-point-power-v1-split.json),
from `scripts/split_power.py`, regenerated by CI. Both are declared in
`artifact_claims.json`; the analysis passes drift and determinism locally.

Replication. All three rerun arms reproduce the control draw by draw: 0 of 800
draws differ for `past_notch_whole`, for `past_notch_w117` (both checked by the
script) and for `oracle_past_notch` (checked by hand). The draws, the runner and
the strata are the control's.

Configuration defect, disclosed and left in place: `end_to_end_power.sweep_decision_rule`
in this configuration, as in `phase1-middle-complete-power-v1`'s, is a stale
copy of the windowed-climb control's rule and names `windowed-117-*`
predictions neither configuration has. No code reads the field. The rule that
governs this run is `split_analysis.decision_rule`. The configuration is not
edited, because the artifact records its hash.

#### Predictions

Scored by the runner (marginal) and by `scripts/split_power.py` (conditional),
before any reading of the result.

| id | prediction | observed | |
|---|---|---|---|
| past-notch-whole-clean-reproduces | whole-message past-notch, clean, at least 79.0% | 316 of 400, 79.0% | held |
| past-notch-w117-indel-reproduces | W = 117 past-notch, one indel, at least 42.5% | 170 of 400, 42.5% | held |
| split-clean-at-least-70pct | split point, clean, at least 70% | 278 of 400, 69.5% | **refuted** (two draws short) |
| split-indel-at-least-60pct | split point, one indel, at least 60% | 213 of 400, 53.3% | **refuted** |
| **S1** | split point detects at least 45% of middle-third indel draws both past-notch climbs miss | 52 of 118, 44.1% [35.4, 53.1] | **refuted** (54 needed) |
| **S2** | split point detects at least 30% of elsewhere indel draws both miss | 18 of 74, 24.3% [16.0, 35.2] | **refuted** (23 needed) |
| S3 | split point detects at most 40% of clean draws both miss | 13 of 57, 22.8% [13.8, 35.2] | held |

Every stratum is above the 25-draw minimum. Both deciding predictions are
refuted under the rule as written. Each 95% interval also contains its
threshold, so neither is a statistical rejection of the threshold.

#### Observed

400 draws per cell, 167 letters, ten pairs, 45 settings per draw for every arm
here. Detected, with 95% Wilson interval, and each arm's null threshold in score
per letter (the whole-message arm is judged against the cell's null, -8.024 clean
and -8.017 with one indel):

| arm | clean | one indel | null threshold, clean / indel |
|---|---:|---:|---:|
| past_notch_whole (v2's climb) | 316, 79.0% [74.7, 82.7] | 147, 36.8% [32.2, 41.6] | cell's |
| past_notch_w117 (v3's climb) | 303, 75.8% [71.3, 79.7] | 170, 42.5% [37.8, 47.4] | -7.689 / -7.708 |
| oracle_past_notch | 316, 79.0% | 308, 77.0% [72.6, 80.9] | -8.024 / -7.918 |
| **split** | 278, 69.5% [64.8, 73.8] | 213, 53.3% [48.4, 58.1] | -7.887 / -7.885 |

Among the draws neither past-notch climb detects (the same 57 clean, 118
middle-third and 74 elsewhere as the control), with the complete-rule figures
taken from the control's artifact:

| stratum | split | complete_w117 | complete_whole | oracle |
|---|---:|---:|---:|---:|
| clean, 57 | 13 (22.8%) | 34 (59.6%) | 44 (77.2%) | 0, by construction |
| indel, middle third, 118 | 52 (44.1%) | 24 (20.3%) | 6 (5.1%) | 83 (70.3%) |
| indel, elsewhere, 74 | 18 (24.3%) | 33 (44.6%) | 37 (50.0%) | 39 (52.7%) |
| indel, pooled, 192 | 70 (36.5%) | 57 (29.7%) | 43 (22.4%) | 122 (63.5%) |

Decision rule: S1 and S2 are both refuted, so the script returns
`complete_sweep`: the split-point climb is dropped and the complete-rule sweep
is preregistered next.

Yield model (printed by the script, none of it a prediction, and under this rule
not consulted). Conditional detection given a standard reading and v2 and v3
null, for the complete rule with the W = 117 climb at 152.6 host-hours and the
split-point climb at 49.0:

| q | complete, probability | per host-hour | split, probability | per host-hour |
|---:|---:|---:|---:|---:|
| 0.05 | 0.551 | 0.0036 | 0.249 | 0.0051 |
| 0.10 | 0.515 | 0.0034 | 0.265 | 0.0054 |
| 0.20 | 0.460 | 0.0030 | 0.290 | 0.0059 |
| 0.35 | 0.403 | 0.0026 | 0.316 | 0.0065 |
| 0.50 | 0.365 | 0.0024 | 0.333 | 0.0068 |

Exploratory, not preregistered:

- Overlap among the missed draws, split against complete_w117: clean 6 split
  only, 27 complete only, 7 both; middle third 40, 12 and 12; elsewhere 10, 25
  and 8. Either of the two detects 70.2% of the clean missed draws, 54.2% of the
  middle-third and 58.1% of the elsewhere ones.
- Over every indel draw, not only the missed: with the indel in the middle third
  (143 draws) split detects 70, complete_w117 49 and the oracle 103; elsewhere
  (257 draws) 143, 209 and 205.
- Of the 343 clean draws a past-notch climb detects, split misses 78 and
  complete_w117 18.

#### Interpretation (inference)

- The climb finds the fault but pays for looking. Among the middle-third misses
  it reaches 44% against the oracle's 70%, about five eighths of the ceiling,
  and twice the complete rule's 20%. Its null sits about 0.14 per letter above
  the whole-message null, which is the best-of-330-hypotheses inflation the
  configuration expected, and that is the likeliest reason it loses 78 clean
  draws the past-notch climbs find and gets only 24% of the elsewhere misses,
  where the indel is near an end and the gain from repairing it is smallest.
- Elsewhere the complete rule's advantage is ring coverage, not repair: it
  recovers 45% to 50% of those misses with no knowledge of the fault, as it does
  of the clean ones.
- **The rule and the yield model point opposite ways.** The rule drops the
  climb on S1 (two draws short) and S2. The yield model, which the rule consults
  only when S1 or S2 holds, favours the split-point sweep at every prior: 0.0059
  against 0.0030 per host-hour at q = 0.2, because it costs 2.89 times v3 against
  9. The complete rule has the higher absolute probability, 0.46 against 0.29 at q
  = 0.2, and is the better single sweep if host-hours are not the constraint. The
  two are largely complementary: among the missed draws 56 are found by split
  only and 64 by complete only.
- The two near-threshold refutations are rule verdicts. S1's interval runs from
  35% to 53%, so a rerun on fresh draws could land either side of 45%. A
  different rule written now would be a post-hoc choice, and that is what
  preregistration is for.
- The development figure of 71% at the true setting on middle-third indels
  became 44% among missed draws in a sweep-shaped control. That is the gap
  between a stecker-stage measure and a detection against a null, and a reason
  to read the next stecker-stage figure the same way.
- This run does not move the odds multipliers stated after
  `phase1-middle-complete-power-v1` (0.14 ungarbled, 0.48 with one indel): the
  reference arms reproduce it exactly.
- Limits as preregistered: one plaintext; a single indel only; a pooled
  wrong-setting null stands in for 27.4 million settings; "missed by both" is
  defined on the same draws; the right ring and position are taken at the
  planted values; wheels I to V as wired.

#### Decision

- Per the preregistered rule: the split-point climb is **dropped**, and the
  complete-rule sweep of BYQMZ (`middle_complete` ring rule, W = 117 climb, about
  246.8 million settings, about 153 host-hours at v3's rate) is preregistered
  next, with its measured conditional rate as its stated power: 0.460 at q =
  0.2, given a standard reading and v2 and v3 null. No sweep is run on this
  evidence; the sweep needs its own preregistration and a checkpointed run.
  Done: [phase1-body-direct-sweep-v4](#phase1-body-direct-sweep-v4-preregistered).
- Running the split-point sweep first instead, as the yield model would, is a
  deviation from the rule and needs the maintainer's explicit, disclosed
  decision.
- `accepted_break` stays false.
- Both candidates assume wheels I to V as wired, which the cited paper's
  authors doubt for Batch C.

---

## phase1-body-direct-sweep-v4 (preregistered)

Status: preregistered 2026-10-07; not run. Configuration:
[experiments/phase1-body-direct-sweep-v4/config.json](../experiments/phase1-body-direct-sweep-v4/config.json),
committed before any run.

Why this one. The rule of
[phase1-split-point-power-v1](#result-run-2026-10-07) chose it once S1 and S2
were both refuted. That rule did not consult the yield model, which favoured a
split-point sweep per host-hour. The maintainer delegated the choice, and this
follows the rule as written: it is the more powerful single sweep (0.46
against 0.29 detection at q = 0.2), not the more efficient one.

What changes from v3: only the ring rule, `middle_past_notch` to
`middle_complete`. Message (BYQMZ), climb (W = 117, batched), retention (100),
start axes, right-ring axis, companions (FKQLZ, XFEDT) and threshold (z ≥ 6)
are v3's. The space is 246,767,040 settings, nine times v3's: at each middle
offset, the start just past the notch and the eight from which the notch falls
inside 167 letters. It contains v3's 27,418,560 settings exactly. They are swept
again rather than skipped, so the sweep is the arm the control measured and its
score distribution covers the whole space.

Hypothesis. The three 1941-09-30 messages are Enigma I traffic (UKW-B, wheels
I–V, ten pairs) under one daily key, and BYQMZ's key is one both past-notch
sweeps could miss, most plausibly because it has no exact equivalent in their
space, with or without one dropped or inserted letter. A complete sweep of the
middle-complete space then retains a candidate that FKQLZ and XFEDT both
confirm at best-start z ≥ 6.

Refuted by: no retained candidate companion-confirmed.

Stated power, conditional on v2 and v3 null (planted draws both past-notch
climbs miss, from `phase1-middle-complete-power-v1`):

| | clean, 57 | one indel, 192 | at q = 0.05 | q = 0.2 | q = 0.5 |
|---|---:|---:|---:|---:|---:|
| detected (the rule's stated power) | 34, 59.6% | 57, 29.7% | 0.551 | **0.460** | 0.365 |
| detected and companion-confirmed | 33, 57.9% | 55, 28.6% | 0.535 | **0.445** | 0.353 |

The joint row is from
[artifacts/phase1-joint-power-v3-middle-complete-w117.json](../artifacts/phase1-joint-power-v3-middle-complete-w117.json):
`scripts/joint_power.py`, unchanged, on the control's `complete_w117` arm, run
2026-10-07 from a clean tree at `6dc6611` (7 minutes), after the split-point
result and before this configuration. It is post hoc and preregistered nowhere,
like the v2 and v3 joint figures. Its detection flags match the control's on all
800 draws, and the companion check confirms 97% of detected draws in both
cells. Within the indel row, 23 of 118 middle-third and 32 of 74 elsewhere are
jointly found.

So a null multiplies the remaining odds of a standard reading by about 0.56 at
q = 0.2. That is a moderate test, not a decisive one.

Predictions (in the configuration):

- **companion-confirmed-candidate** (decides): at least one of the 100 retained
  candidates is companion-confirmed.
- confirmed-candidate-is-rank-one: a confirmed candidate is also rank 1 on BYQMZ.
- confirmed-candidate-at-an-added-middle-start: a confirmed candidate's middle
  start is one of the eight the complete rule adds. v3's settings are a subset
  and the climb and companion check are deterministic, so a confirmed setting v3
  swept would have been confirmed by v3.
- retained-v3-settings-reproduce: every retained candidate at a setting v3
  swept is one v3 retained, with the same plugboard and score within 1e-6. A
  failure means the climb changed since `7ae72f8`.
- null-top-near-expected-maximum: with no confirmation, the top score is
  between z = 5.5 and 7.5 over all 246.8 million scores. v2 and v3 reached 6.03
  and 6.22 over 27.4 million, and a normal tail adds about 0.4 for nine times as
  many settings.

Checked before committing (exploratory, not part of the record): a 108-setting
slice of this rule (wheel order I-II-III, scratch output) ran through the
runner. It passed the preflight and both positive controls, swept nine settings
per start and right ring, and resumed both chunks from its checkpoint on a
second invocation with identical candidates.

Limits, in the configuration. One plaintext; a single indel only; "missed by
both" is the planted stand-in for two null sweeps. The 6σ pooled-null threshold
stands in for retention in the top 100 of 246.8 million scores. A normal null
puts that cutoff near 4.9σ, but v2's and v3's maxima sat about 0.7σ above the
normal expectation, so the far tail is heavier than normal and not measured. The
companion calibration used past-notch candidates; the joint figure covers the
complete rule's on planted draws. q is unmeasured. Everything assumes wheels I
to V as wired, which the cited paper's authors doubt for Batch C. If they are
right, the power is zero and a null says nothing about these messages.

Cost. At v3's 2.22 ms per setting on 10 workers, about 152 hours (6.3 days) on
an idle host. The 1,560 chunks hold 158,184 settings each, about an hour of one
worker. The checkpoint under `build/` lets the sweep stop and resume; a resumed
run repeats the gates and both confirmations, and its artifact times only the
last invocation, so record each start, stop and resume here.

> **Amended 2026-10-07, before any chunk ran (engineering, no number changes).**
> The first launch, from a clean tree at `fba1b74` (2026-10-07 22:31:15 UTC,
> detached, 10 workers), was stopped at 22:37:58 UTC during start-up. No worker had
> started, no checkpoint existed, and the log was empty. The parent process had
> reached 8.5 GB and was growing while the host ran out of memory. The cause:
> `sweep_chunks` expanded every chunk's settings into Python tuples in the parent
> before the pool started, about 192 bytes per setting. That was 5.3 GB for v3's
> 27.4 million settings and would be about 47 GB for this sweep's 246.8 million,
> against 31 GB of RAM. The 108-setting pre-commit check above could not show
> this.
>
> The fix gives each chunk its starts instead of its settings, and the worker
> expands them with the same `RingRule.settings` call. `RingRule.setting_count`
> gives `settings_run` without building them. The parent now holds about 0.5 MB for
> the full chunk list. A complete-rule slice with this configuration's climb and
> scorer (2 wheel orders, 12 starts, 5,616 settings, 4 workers) gives identical
> retained candidates, score statistics, execution record, checkpoint lines and
> checkpoint fingerprint under `fba1b74` and under the fix. A unit test checks that
> expanded chunks equal the slice's settings in order, and that the count matches
> for every ring rule. Nothing about the sweep's definition, predictions or stated
> power changes.

Run command, not run:

```bash
python3 phase1_stecker.py --config experiments/phase1-body-direct-sweep-v4/config.json --jobs 10
```

> **Run log, recorded 2026-10-08 (the run is unfinished).** Started 2026-10-07
> 23:28:24 UTC from a clean tree at `31dfbcc`, detached, 10 workers, with this
> configuration unchanged (engine `batched`). The checkpoint gets records only
> once the preflight and both positive controls have passed, and it held 160 of
> 1,560 chunks at 2026-10-08 17:48 UTC, about 9 an hour. Nothing has stopped or
> resumed it. The [CUDA engine](#cuda-climb-engine-build-and-benchmark-2026-10-08)
> built since then does not touch this run: its checkpoint fingerprint is
> unchanged, which a test checks.

---

## CUDA climb engine: build and benchmark (2026-10-08)

Exploratory engineering and measurement, preregistered nowhere. No experiment
configuration changed. The running v4 sweep was neither stopped nor switched
(see its run log above).

What it is (`stecker_cuda.py`). A new climb engine, `climb.engine = "cuda"`, is
an exact port of `BatchedClimber` for the whole-message and head-and-tail
windowed climbs. It runs a whole sweep chunk in one call. Each CUDA thread block
climbs one (setting, window) pair with 352 threads: 325 swap slots, 26 unplug
slots and one for the current board. The block builds the setting's position
table itself, by the stepping and composition of
`enigma_fast.position_permutations`, which costs the CPU sweep a Python loop per
setting. The table and the plugboard sit in shared memory. The move order, pair
limit and evaluation count are `_candidates`'. The acceptance rule is exact
without a serial scan over all ~335 scores. A move can replace the running best
only if it beats every earlier score and the starting best plus the gain, because
the running best never falls below either. So one warp finds those few moves
with a prefix-maximum scan and applies the rule to them in order. `auto` never
picks `cuda`. The split-point climb is refused with an error. Under `cuda` the
preflight runs a new cuda-against-batched parity report as well as the existing
batched-against-reference one. A mismatch in either blocks the run before any
target search.

Choice of build: the kernel is compiled by `nvcc` on first use and loaded with
ctypes, not run as a CuPy `RawKernel`. The CUDA 12.8 toolchain was already on the
host and CuPy was not installed, so ctypes adds no package. The kernel source is
a string in `stecker_cuda.py`, so the provenance hash of imported modules covers
it. The compiled library is cached under `~/.cache/enigma-attack/cuda`, keyed by
source, nvcc version and flags. `pip install .[gpu]` adds only numpy. nvcc and
the driver are host requirements, and without them the engine reports itself
unavailable and the GPU tests skip.

Fact: the scores are bit-identical, not merely close. numpy adds a row's terms by
pairwise summation: eight accumulators, blocks of up to 128, larger blocks split
at half rounded down to a multiple of eight. An emulation of that order matched
`ndarray.sum(axis=1)` bit for bit on 124,124 random rows of 1 to 1,000 terms with
numpy 2.2.6. The kernel adds its n-gram terms in that order in FP64, so every
candidate score, and therefore every acceptance decision, is the batched
climber's. The coincidence objective is integer counts and the same three
floating-point operations. The window score repeats
`FastNgramScorer.score_decryption`'s sequential sum. The chunk statistics repeat
the sweep's streaming update in C, with floating-point contraction off.
Measured differences are therefore 0.0, not a value under 1e-9.

Fact: parity, against `BatchedClimber`, all on the 3090:

| check | compared | identical |
|---|---:|---:|
| position tables against `position_permutations` (2,000 on wheels I–V, 1 to 299 letters; 480 in the tests on I–VIII, 1 to 399) | 2,480 settings | all |
| v4's preflight samples (seed 20261005), whole message | 24 | 24 |
| v4's preflight samples, W = 117 | 24 | 24 |
| random settings, whole message: clean / masked / short bodies | 680 / 660 / 660 | all |
| random settings, W = 117: clean / masked / short bodies | 680 / 660 / 660 | all |
| v4 chunks recomputed from a checkpoint copy | 150 chunks, 23,727,600 settings | 150 records byte-identical |

"Identical" means the same final plugboard, evaluation count and (windowed) the
same window, with a score difference of exactly 0.0. The random run was
`scripts/cuda_parity.py random --settings 2000 --seed 20261008` (114 s). It drew 3
to 10 settings per body: the true setting first, the rest random. Clean and
masked bodies are 150 to 167 letters; masked ones carry 1 to 8 masked letters,
sometimes at position 0 or as a two-letter run. Short bodies are 30 to 139 letters,
so W = 117 meets both the single-window fallback and overlapping windows. The
chunk check was `scripts/cuda_parity.py chunks` over every record in a read-only
copy of the running v4 checkpoint, taken at 150 chunks. Each record compared equal
as JSON text: `evaluated`; the 100 `top` rows in order (setting, plugboard,
window, evaluations, score); and mean, m2 and max. A test asserts that v4's
fingerprint, recomputed from its configuration, equals the one on the
checkpoint's first line, so the CPU sweep can still resume after this change.
Another test asserts that a cuda chunk record equals the batched one as JSON
text.

Fact: the runner end to end. A scratch copy of v4's configuration set the engine
to `cuda` and was cut to wheel order I-II-III and left start A: 26 chunks,
158,184 settings. It passed every preflight check, including the new
`cuda_climb_matches_batched` (24 of 24 samples, worst difference 0.0), and both
positive controls. It swept in 1.29 s and wrote its checkpoint. A second
invocation resumed all 26 chunks, ran none, and reported identical top
candidates and score distribution. Each invocation took about 110 s in all,
mostly CPU work that does not grow with the sweep: the preflight, the controls
and the companion confirmation of the 100 retained candidates (about 80 s).

Fact: cost. `scripts/benchmark_sweep.py --v4-chunks 12 --repeats 2
--remaining-chunks 1400` timed whole v4 chunks: BYQMZ, v4's W = 117 climb and
complete ring rule, 158,184 settings each. The 12 chunks spread over wheel orders
and middle offsets, and each ran twice. The run was on 2026-10-08 at about 17:42
UTC, on an RTX 3090 (driver 595.91, CUDA 12.8). LM Studio's model had been
unloaded at the maintainer's request, and no other compute process held the GPU.
The CPU v4 sweep was running on all 10 physical cores throughout.

| engine | ms per setting | against batched on 10 CPU workers (2.22 ms, recorded) |
|---|---:|---:|
| **cuda** | **0.00741** (1.14 to 1.23 s per chunk) | **299×** |

At that rate v4's 1,400 unfinished chunks take 0.46 h, against 137 h for the CPU
at its recorded rate. A full 246,767,040-setting sweep takes 0.51 h against
152 h. Each run adds the fixed CPU minutes above. An earlier three-chunk check,
with LM Studio's model still loaded and idle, took 1.15 s per chunk, so the
loaded model made no measurable difference while idle. The kernel uses 80
registers and about 26 KB of shared memory per block, two blocks per SM. The
display watchdog is on for this GPU, so a chunk call issues launches of 8,192
settings. The benchmark's older planted-message path also accepts `--engines
cuda`. Its chunks are 26 settings, so per-call overhead dominates there (0.32 ms
per setting) and that figure is not the engine's rate.

Inference. The engine changes the cost of a Phase 1 sweep from days of host time
to under an hour. Its output cannot be told apart from the batched engine's on
every comparison made: 23.7 million settings of the actual v4 sweep, plus 4,000
random and 48 preflight climbs. A cuda run of v4 would therefore produce the
same retained candidates, plugboards, scores and statistics. It would differ
only in the engine field, the checkpoint fingerprint and the timings. That rests
on parity measured on this host with numpy 2.2.6. The bit-exact agreement
depends on numpy's summation order. A different numpy could change the batched
scores in the last bits, which the preflight would catch as a failed check, not
let through as a quiet difference. Whether to stop the running CPU sweep and
redo it on the GPU is the maintainer's decision. Doing so is a disclosed
deviation from v4's preregistered engine, and it restarts from zero because the
engine is part of the fingerprint. This entry does not decide it.

Limits. The split-point climb (`stecker_split.SplitClimber`) has no GPU port.
Bodies are limited to 512 letters. One GPU climbs one chunk at a time, so under
`cuda` the sweep ignores `--jobs`. The power control's single null climbs still
use the batched climber when its arms ask for `cuda`.

---

## What Phase 1 now needs

The two sweeps bound the problem from both sides.

* The **indicator-coupled** space is small enough to search exhaustively — and
  now has been — but its ranking statistic has almost no power at a ten-pair
  stecker (top-200 retention 0% at 167 letters, at most 6% at the pooled 371;
  [phase1-ic-rank-v1](#phase1-ic-rank-v1)) and its hill-climb has none. Nothing more can be extracted from it.
* The **body-direct** formulation works: at 167 letters with ten pairs the
  climb recovers the exact plugboard and exact plaintext on every draw. Its
  space is about 2.74 × 10⁷ settings per message, measured at roughly 456 ms
  of CPU time per converged climb, so a complete search of one message is a
  projected 3,472 core-hours (about 8 days of wall-clock time on 18 cores),
  and the calibration shows no cheap pre-filter that cuts this by more than
  about 2×.

> **Update, 2026-10-02.** The 2.74 × 10⁷ figure stands as a setting count, but
> the claim that a full search "finds the key" does not: a complete sweep under
> the best single-phase rule detects about 83% of planted keys without faults and
> 15% with one indel ([above](#phase1-end-to-end-power-v1)). The Bombe argument
> below also depends on cribs whose presence in these three messages nothing in
> the repository supports (review finding P3), which this entry does not
> address.

> **Engine update, 2026-10-02.** The sweep engine was rebuilt (review R1 and R2)
> and measured with `scripts/benchmark_sweep.py`, which is exploratory and
> preregistered nowhere. On this host (i9-10900K, 10 cores, 20 threads) the
> batched numpy climb takes 16.9 ms per setting in one process against 153 ms
> for the pure-Python climb (676 settings, identical retained candidates), about
> 9.1×. Parallel throughput peaks at 9 to 10 workers and falls with more:
> 2.64 to 2.65 ms per setting at 9 and 10 workers, 3.56 at 12, 5.29 at 18, so
> `--jobs` should be the physical core count, not the thread count. The
> reference climb at 18 workers took 20.0 ms per setting. At 2.65 ms per
> setting the 27.4 × 10⁶ settings of the past-notch space take about 20 hours,
> against about 152 hours for the reference climb at 18 workers. The earlier
> "3,472 core-hours" multiplied a wall-clock time measured with 18 workers
> contending by 18; one uncontended reference climb is 153 ms, about 1,160
> core-hours for the same space, and what a host can deliver is set by its
> physical cores either way.
>
> The sweep now keeps each chunk's best settings and streaming score statistics
> instead of every setting, splits each wheel order by its middle axis (1,560
> chunks for the full space), appends each finished chunk to a JSONL
> checkpoint, and resumes by skipping recorded chunks. The merge is in chunk
> order, so the result does not depend on `--jobs`.

The gap is therefore neither the scorer nor the stecker search. It is the
enumeration of rotor settings, and the historically correct answer to exactly
that problem is the one Bletchley Park built: a **crib-driven Bombe**, which
eliminates the plugboard algebraically through the diagonal board instead of
searching it, and tests a rotor setting in microseconds rather than a tenth of a
second. Phase 2 already assembled a crib network
([docs/phase2-research.md](phase2-research.md),
[artifacts/phase2-network-cribs.json](../artifacts/phase2-network-cribs.json)),
and the no-self-encipherment property makes crib placement nearly free.

> **Superseded ordering, 2026-10-03.** This paragraph was written before the
> engine rebuild and named the Bombe as the next experiment. It is not. A Bombe
> needs a correct crib at a correct offset, and no crib prior for these three
> messages has been quantified (review finding P3). With the batched engine a
> complete middle-past-notch sweep of BYQMZ costs about 20 hours, has measured
> power (82.5%) and needs no crib, so it runs first, as the preregistered
> `phase1-body-direct-sweep-v2` below. The Bombe is reconsidered only if that
> sweep is null at its stated power, or once a crib prior exists.

> **Crib prior, 2026-10-04.** The preregistered
> [phase2-crib-prior-v1](phase2-experiment-history.md#phase2-crib-prior-v1-preregistered)
> finds that 15 of the 16 catalogued cribs occur in none of the five solved
> 1941 plaintexts in the repository. The one exception is HARTJENSTEIN, which
> ends 2 of the 5. Nothing links those five to Batch C, so no prior can be
> estimated yet and the Bombe stays deferred.

Second, and cheaply: XFEDT at 97 letters is below the recovery threshold on its
own (1 of 8 draws) and should not be attacked alone. FKQLZ at 107 letters was
not measured directly and sits between the 97-letter and 167-letter cells.
Its measurement is preregistered and queued, not run:
[phase1-fkqlz-length-calibration-v1](../experiments/phase1-fkqlz-length-calibration-v1/config.json)
(32 draws at 97, 107 and 167 letters, predicting fewer than 24 of 32 recovered
at 107).

> **Measured, 2026-10-06.** [phase1-fkqlz-length-calibration-v1](#phase1-fkqlz-length-calibration-v1)
> ran: 12 of 32 at 97 letters, 10 of 32 at 107, 28 of 32 at 167. FKQLZ stays a
> companion. The "not run" and "queued" wording above is the 2026-10-04 text.
