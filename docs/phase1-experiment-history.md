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

> **Amended 2026-10-08, before the GPU run: engine `batched` → `cuda` (a
> disclosed deviation).** After the CUDA engine's build and benchmark, the
> maintainer decided to rerun v4 on the GPU. The configuration's `climb.engine`
> is now `cuda`, and its `amendments` field records the change. Nothing else
> changes: message, space, ring rule, climb, retention, companions, threshold,
> predictions and stated power are as preregistered. The deviation is expected
> to change no number. The cuda engine gave byte-identical records on all 150
> v4 chunks recomputed from the CPU checkpoint, and its preflight check against
> the batched climber must pass before any target search. The engine is part of
> the checkpoint fingerprint, so the GPU run starts from zero and does not read
> the CPU checkpoint. When this was committed, the CPU run held 200 of 1,560
> chunks and was still running; it was not stopped. Acceptance condition, fixed
> here before the run: every chunk the CPU run finished must have a record
> identical to the GPU run's for that chunk, apart from the fingerprint. Any
> difference voids the GPU result. Run command:
> `python3 phase1_stecker.py --config experiments/phase1-body-direct-sweep-v4/config.json --jobs 1`
> (the cuda engine ignores `--jobs`).

### Result (GPU run 2026-10-08)

Run: the maintainer launched it from a clean tree at `35c92d7` (branch
`claude/phase1-cuda-engine`, the amendment commit). It ran from 2026-10-08
22:52:30 to 23:25:33 UTC, 33 minutes in all, as one process on the RTX 3090.
No other compute process was on the GPU. The CPU run of the same sweep kept
running alongside on 10 cores. There was one invocation, with no stop or
resume. The artifact is
[artifacts/phase1-body-direct-sweep-v4.json](../artifacts/phase1-body-direct-sweep-v4.json).

Acceptance condition (fixed in the amendment): **met.** The CPU run had
finished 210 chunks when its checkpoint was copied (read-only, 23:25:54 UTC).
All 210 records (33,218,640 settings) are identical to the GPU run's records for
the same chunks, compared as JSON text without the fingerprint. None is missing
or different.

### Observed

- Preflight: every check passed, including `cuda_climb_matches_batched` (24 of
  24 whole-message and 24 of 24 W = 117 samples, worst score difference 0.0)
  and `batched_climb_matches_reference`. Both positive controls passed.
- Coverage: all 246,767,040 settings of the middle-complete space, in 1,560
  chunks. The sweep took 1,859 s (7.5 µs per setting) and the companion
  confirmation 90 s.
- Score distribution over every setting (better of two windows): mean −8.2870,
  sd 0.11475 per letter. The maximum is −7.5395 (z = 6.51), rank I-IV-II, rings
  ABF, start THF. Rank 100 is −7.6347. All 100 retained candidates won on the
  head window, as in v3 (BYQMZ's masked letter is in the head).
- Companion confirmation: **none confirmed.** The best minimum over FKQLZ and
  XFEDT is z = 4.69 at rank 65 (FKQLZ 4.96, XFEDT 4.69), against the threshold
  of 6. v3's best was 4.64.
- Indicator confirmation: 2 of 100 candidates have a compatible ring setting.
  The best pooled date score is −9.00 per letter.
- Duplicate settings, not anticipated in the preregistration. A start with the
  middle wheel at its notch double-steps on the first keystroke. From then on it
  is the start one letter later on both the left and middle wheels, which is the
  just-past-notch setting v3 swept. The exception is when the right wheel also
  starts at its notch: 1,906 of 2,000 random checks over 167 letters were
  identical, against the 25 in 26 expected. So about 1 in 9.4 of the space's
  settings exactly duplicate another. Among the retained, 12 candidates sit at a
  notch start, and each has its duplicate, with the same plugboard and score,
  also retained. The 100 rows are therefore 88 distinct machines.

Predictions:

| prediction | outcome |
|---|---|
| companion-confirmed-candidate (decides) | **failed**: no candidate confirmed |
| confirmed-candidate-is-rank-one | does not apply |
| confirmed-candidate-at-an-added-middle-start | does not apply |
| retained-v3-settings-reproduce | **held**: the 12 retained at settings v3 swept are all v3-retained, with the same plugboard and score (rank 5 is v3's rank 1, −7.573383084) |
| null-top-near-expected-maximum (z 5.5 to 7.5) | **held**: z = 6.51 |

### Interpretation (inference)

- The run is the preregistered sweep in every respect but the engine, and the
  engine changed nothing measurable. The 210 CPU-run chunks the GPU run
  reproduced exactly are 13% of the sweep, spread over the first wheel orders.
- The three checks agree again: the top score is the noise maximum, the
  companions see nothing, and the indicator sees nothing. The best companion z
  (4.69) sits where v3's (4.64) did, below the calibration's 240-null maximum
  of 4.60 plus what 100 more draws would add.
- Weight of the null. The preregistered stated power puts this null's odds
  multiplier at about 0.56 at q = 0.2. Combined with the v2 and v3 multipliers
  of 0.14 ungarbled and 0.48 with one indel, all three nulls multiply the odds
  of a standard Enigma I reading of BYQMZ by about 0.059 ungarbled (0.14 ×
  0.421) and 0.34 with one indel (0.48 × 0.714). At q = 0.2 that is about 0.12.
  The same caveats hold: one plaintext, a single indel, planted stand-ins for
  the earlier nulls, and wheels I–V as wired.
- The duplicates change no verdict. A duplicated setting is climbed twice to
  the same result. It adds a little weight to those settings in the score
  distribution, about 11% of settings, and costs retained slots: 12 of 100
  here. A later complete-rule sweep could drop the notch start whenever the
  right wheel is not also at its notch.

### Decision

v4 is null at its stated power. Phase 1's body-direct search of BYQMZ under
the standard Enigma I reading has now covered the past-notch space twice (whole
message and W = 117) and the complete space once, and none confirms.

> **CPU run stopped, 2026-10-09 00:23:18 UTC (maintainer's decision).** The
> CPU run of v4 (engine `batched`, PID 930616, started 2026-10-07 23:28:24 UTC
> from `31dfbcc`) was stopped with SIGTERM to its process group. It had
> finished 220 of 1,560 chunks. Its checkpoint ends on a complete record and
> was kept unchanged, so the run could resume from `31dfbcc`. **All 220 chunk
> records (34,800,480 settings) are identical to the GPU run's.** The per-chunk
> record hashes and statistics of that comparison are in
> [data/phase1/v4-cpu-gpu-chunk-comparison.json](../data/phase1/v4-cpu-gpu-chunk-comparison.json)
> (`scripts/cuda_parity.py compare`). Both checkpoints are kept, uncommitted,
> in the main checkout's `build/`: the CPU run's at its configured path, the
> GPU run's as `phase1-body-direct-sweep-v4.gpu-cuda.checkpoint.jsonl`, with
> their sha256 in that file. The CPU run wrote no artifact; the GPU run's is
> the record. The cited
paper's doubt about the wheel wiring for Batch C, the two-fault and
other-machine cases, and the crib-driven Bombe (still without a crib prior)
are what remain. Choosing among them is for a later entry.

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
it. The compiled library is built for the visible device's compute capability and
cached under `~/.cache/enigma-attack/cuda`. The cache key covers the source, the
nvcc version, the flags and that capability. On load, the library is checked to
hold a kernel image for the device. `pip install .[gpu]` adds only numpy. nvcc and
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

> **Update, 2026-10-09.** The split-point climb now has a GPU port; see
> [below](#cuda-split-point-climb-build-and-parity-2026-10-09).

---

## CUDA split-point climb: build and parity (2026-10-09)

Exploratory engineering, preregistered nowhere. It is the first step of the plan
recorded after v4's null. The three nulls leave a standard reading's odds at
about 0.059 ungarbled but 0.34 with one dropped or inserted letter. The
split-point climb is the method aimed at that case, and the GPU removes the cost
argument that dropped it. Nothing is decided about running it; that needs its
power re-measured and a preregistration.

What it is. `stecker_cuda.CudaSplitClimber` ports
`stecker_split.SplitClimber` and runs whenever `climb.engine = "cuda"` and
`climb.split` is set. That combination used to be refused. Each block climbs one
setting on a position table of n + 1 rows, built on the GPU. The move set,
acceptance rule and evaluation count are the windowed engine's. Both objectives
are reproduced exactly:

- **n-gram.** Each candidate decrypts three aligned streams: the head on row t,
  the stream after a dropped letter on row t + 1, and the stream after an
  inserted one on row t − 1. The kernel repeats numpy's arithmetic: sequential
  prefix sums (`cumsum`), each suffix as total minus prefix, and each hypothesis
  as ((prefix + bigram) + suffix) + mask. That needs each stream's total
  first, so a candidate costs two passes. During the climb only the best value
  matters, so the mask is added once to the maximum rather than to every
  position. Rounding is monotone, so that gives the same maximum. The final
  `best_hypothesis` adds it per position and keeps numpy's first-maximum
  tie-break.
- **Index of coincidence.** Exact integer counts. The two mixed count vectors
  are updated as the boundary moves across the grid, then put through the
  batched climber's three floating-point operations.

The preflight, when the engine is `cuda` and a configuration declares a split
(in `climb` or in a power arm), also checks the split climb against
`SplitClimber` on its seeded cases, hypothesis included. Bodies are limited to
4 to 255 letters, because the counts are bytes.

Fact: parity, against `SplitClimber`, on the 3090:

| check | compared | identical |
|---|---:|---:|
| random settings, grid 32 (`scripts/cuda_parity.py split --settings 2000 --seed 20261009`): clean / one indel / one indel + 1–5 masks / short (8–59 letters) | 500 / 500 / 500 / 500 | all |
| random settings, grid 16 (`--settings 500 --seed 20261010`) | 500 | all |
| development checks, grids 16 and 32, 6 to 167 letters | 744 | all |
| BYQMZ sweep slice, complete ring rule, grid 32: 10 wheel orders × middle offset 7 × left 0–3 × all right positions and rings, batched (10 CPU workers) against cuda | 10 chunks, 243,360 settings | 10 chunk records identical; ranked candidates and score distribution identical |

"Identical" means the same final plugboard, evaluation count, hypothesis (kind
and position) and score per letter, with a worst difference of exactly 0.0.
The sweep slice's two checkpoints were compared with
`scripts/cuda_parity.py compare`. Each body in the random checks was climbed at
its true setting and at nine random ones. The final
hypotheses over the 2,000 were 1,012 deletions, 981 insertions and 7 clean.
That is a property of the climb, the same on both engines: a masked hypothesis
usually wins on wrong-setting text, as the residual effect noted in the
split-point build entry predicts.

Fact: cost. `scripts/benchmark_sweep.py --v4-chunks 12 --split-grid 32` timed
12 v4-shaped chunks: BYQMZ, the complete ring rule, v4's climb without its
window plus `split.ic_grid` 32, 158,184 settings each. It took 0.02849 ms per
setting, 4.53 to 4.55 s a chunk, 3.8 times the windowed GPU climb. The run was
on 2026-10-09 at 00:49 UTC on the RTX 3090, with no other compute process on the
GPU. The batched CPU comparison was running on 10 cores at the time. A complete
246,767,040-setting split sweep would therefore take 1.95 h. The CPU figure is
derived, not measured here: the recorded split-to-windowed ratio of 2.89 times
v3's 2.22 ms gives 6.42 ms per setting on 10 workers, about 440 h, so the GPU is
about 225 times faster. The sweep slice above measured the CPU directly: 2,871 s
on 10 workers for 243,360 settings, 11.80 ms per setting, against 7.4 s on the
GPU (0.0303 ms), 390 times. That slice holds only 10 chunks of 24,336 settings,
one per worker, so the CPU figure includes no tail effects but is a small
sample. The kernel uses 69 registers per thread.

Inference. A complete split-point sweep of BYQMZ is now a two-hour job. What
decides whether to run one is its power conditional on v2, v3 and v4 being
null. That power is unmeasured. The split-point control
(`phase1-split-point-power-v1`) measured the climb conditional on the
past-notch arms missing, not on v4's complete rule also missing. That is the
next measurement, and with the GPU a control's sweeps cost minutes.

Limits. Bodies of 4 to 255 letters. Power-control null climbs and companion
checks still run on the CPU.

---

## phase1-split-point-power-v2 (preregistered)

Status: preregistered 2026-10-09; run 2026-10-09, T1 held ([result](#result-run-2026-10-09)). Configuration:
[experiments/phase1-split-point-power-v2/config.json](../experiments/phase1-split-point-power-v2/config.json),
with its analysis script `scripts/split_power_v2.py`, committed before any run.

Why this one. v4 is null, and with v2 and v3 the three nulls leave a standard
reading of BYQMZ at odds multipliers of about 0.059 ungarbled and 0.34 with one
dropped or inserted letter. The open case is a garbled message. The split-point
climb searches the position of one such fault and now runs on the GPU, so a
complete split-point sweep costs about 2 hours. Cost no longer decides anything.
What decides is whether such a sweep would find keys the three completed sweeps
miss. `phase1-split-point-power-v1` measured that only over the past-notch rule
and only given that the two past-notch climbs miss.

Design. Planted keys as in v1: one 167-letter plaintext, ten pairs, 400 draws
clean and 400 with one random dropped or inserted letter, each draw swept over
its own neighbourhood. The seed is new (20261109), so no draw has been seen by
any earlier analysis. There are five arms:

- `past_notch_whole`, `past_notch_w117` and `complete_w117`: the climbs of v2,
  v3 and v4. A draw none of them detects stands in for a key all three sweeps
  would miss.
- `split_complete`: the candidate sweep's climb over the space it would search
  (middle-complete rule, `ic_grid` 32, mask credit −8.66).
- `split_past_notch`: v1's split arm, rerun on these draws as the link to v1's
  numbers.

Every arm runs on the cuda engine. The preflight checks all of them against the
batched climbers before any draw, and the workers are spawned.

Hypothesis: among one-indel draws missed by all three reference arms,
`split_complete` detects at least 30%.

Predictions:

- **T1** (decides, scored by `scripts/split_power_v2.py` on a stratum of at
  least 25 draws): `split_complete` detects at least 30% of the one-indel draws
  missed by all three reference arms. The bar is v4's own conditional detection
  on one-indel draws (57 of 192, 29.7%): a further sweep is worth
  preregistering if it adds at least what the last one added on the cases left
  most open.
- T2: on those draws, `split_complete` detects at least as many as
  `split_past_notch`.
- Runner sanity checks: the whole-message past-notch arm detects at least 72%
  of clean draws, and the W = 117 past-notch arm at least 35% of indel draws.
  The earlier controls measured 79.0% and 42.5%; each bar is about three
  standard errors lower.

Decision rule. If T1 holds, a complete split-point sweep of BYQMZ is
preregistered next, with this run's conditional detection as its stated
power. The script reports that power at q = 0.05 to 0.5, nominal 0.2. The
companion check's joint rate is measured on these draws before that
preregistration and stated beside it, as for v3 and v4. If T1 is refuted, no
split-point sweep is run on this evidence. The standard-reading search of BYQMZ
then stops at three nulls, and the next question is the wheel wiring. If fewer
than 25 indel draws are missed by all three arms, nothing is decided.

Known before writing it (in `pre_run_facts`). On the 800 draws v1 shares with
`phase1-middle-complete-power-v1`, joined read-only on 2026-10-09, v1's
past-notch split arm detected 50 of the 135 one-indel draws missed by all three
reference arms (37%) and 6 of 23 such clean draws. That post hoc figure is the
reason for a new seed rather than a reason to expect a pass. It is a different
arm, on draws that informed earlier choices.

Checked before committing (exploratory, not part of the record): 3 and then 8
draws a cell through the runner with scratch output. Every preflight check
passed, including 24 of 24 split and 24 of 24 windowed climbs identical between
cuda and batched. Four spawned workers gave draws identical to one process, at
about 0.8 s a draw, which puts the full run at about 11 minutes.

Limits are in the configuration. The main ones:

- Missed by all three reference arms stands in for three null sweeps.
- Only a single fault is modelled.
- The rate is detection only, without the companion check.
- One plaintext.
- Wheels I–V are assumed as wired.

Run command, not run:

```bash
python3 phase1_stecker.py --config experiments/phase1-split-point-power-v2/config.json --jobs 4
python3 scripts/split_power_v2.py --output artifacts/phase1-split-point-power-v2-analysis.json
```

### Result (run 2026-10-09)

Run: the maintainer launched it from a clean tree at `28548d0` (the
preregistration commit) with `--jobs 4`, and it ran from 05:32:25 to 05:44:12 UTC
2026-10-09. The 800 draws took 685 s on four spawned workers and the RTX 3090.
LM Studio's llama-server was loaded during the run (18 GB of VRAM); nothing here
depends on its being idle. The artifact is
[artifacts/phase1-split-point-power-v2.json](../artifacts/phase1-split-point-power-v2.json),
and the analysis
[artifacts/phase1-split-point-power-v2-analysis.json](../artifacts/phase1-split-point-power-v2-analysis.json),
from `scripts/split_power_v2.py` unchanged.

### Observed

- Preflight: every check passed, including `cuda_climb_matches_batched` (24 of
  24 split and 24 of 24 windowed climbs identical, worst score difference 0.0).
  Both positive controls passed.
- Detection over all draws:

| arm | clean (400) | one indel (400) |
|---|---:|---:|
| past_notch_whole (v2's climb) | 303, 75.8% | 153, 38.3% |
| past_notch_w117 (v3's) | 294, 73.5% | 200, 50.0% |
| complete_w117 (v4's) | 355, 88.8% | 272, 68.0% |
| split_past_notch (v1's split arm) | 262, 65.5% | 211, 52.8% |
| **split_complete** | **351, 87.8%** | **306, 76.5%** |

- The runner's three predictions held. The whole-message arm on clean draws
  scored 75.8% against at least 72%. The W = 117 arm on indel draws scored
  50.0% against at least 35%. The complete split arm exceeded the past-notch
  split arm on indel draws by 23.8 points, against at least 0.
- Missed by all three reference arms: 20 clean draws (5.0%) and 111 one-indel
  draws (27.8%; 84 with the fault in letters 56 to 111, 27 elsewhere).
- Detection among them, with 95% intervals:

| stratum | split_complete | split_past_notch |
|---|---:|---:|
| **one indel, pooled (deciding)** | **69 of 111, 62.2% (53–71%)** | 41 of 111, 36.9% (29–46%) |
| one indel, middle third | 55 of 84, 65.5% (55–75%) | 36 of 84, 42.9% |
| one indel, elsewhere | 14 of 27, 51.9% (34–69%) | 5 of 27, 18.5% |
| clean | 8 of 20, 40% (22–61%) | 2 of 20, 10% |

- **T1 held** (62.2% against at least 30%) and T2 held (+25.2 points). The
  script's decision: `preregister_complete_split_sweep`.
- Conditional detection of a complete split-point sweep, given a standard
  reading and v2, v3 and v4 null: 0.450 at q = 0.05, 0.485 at 0.1, **0.529 at
  0.2**, 0.566 at 0.35 and 0.588 at 0.5. It is detection only, without the
  companion check.

### Interpretation (inference)

- The complete-rule split climb finds most of the garbled keys the three
  completed sweeps leave behind, about twice v4's 29.7% on the comparable cases.
  Its gain over v1's past-notch split arm (62% against 37%) comes from the ring
  coverage the complete rule adds. v1's arm, on these fresh draws, gives 36.9%,
  the same as the post hoc 37% on the old draws, so the old draws were not
  unusual.
- On clean draws the split climb gives up very little: 87.8% against 88.8% for
  v4's climb. The penalty v1 measured for searching the position (65.5% against
  75.8% here) is mostly a past-notch effect. So a complete split-point sweep is
  close to a superset of v4 on clean messages, as well as much stronger with
  one indel.
- If such a sweep is null, the odds multiplier of a standard reading would fall
  from about 0.12 after three nulls to about 0.054 at q = 0.2 (0.12 × (1 −
  0.529)). That is about 0.13 with one indel and, from a 20-draw clean
  stratum, about 0.035 ungarbled. Those are planted-draw figures with the usual
  stand-ins (pooled nulls for the sweeps, one plaintext, a single fault, wheels
  I–V as wired), and without the companion check.

### Decision

Per the preregistered rule, a complete split-point sweep of BYQMZ (the
middle-complete space, `climb.split` as `split_complete`, engine cuda, about 2
GPU hours) is preregistered next, with this run's conditional detection as its
stated power. The rule also requires the companion check's joint rate to be
measured on these draws first and stated beside it, as for v3 and v4. That
comes before the sweep's configuration is written. Nothing has been swept on
this evidence.

> **Joint rate measured, 2026-10-09 (the step the rule requires).** The
> maintainer ran `scripts/joint_power.py`, unchanged, on the `split_complete`
> arm from a clean tree at `9de3417`
> ([artifacts/phase1-joint-power-v4-split-complete.json](../artifacts/phase1-joint-power-v4-split-complete.json),
> 369 s). It ran the companion check (FKQLZ- and XFEDT-length companions, z ≥ 6)
> on every draw's top candidate. Its detection flags match this run's on all 800
> draws. Over all draws, 340 of 351 clean detections (96.9%) and 302 of 306
> one-indel detections (98.7%) are companion-confirmed. Joined read-only with the
> strata above (exploratory arithmetic, preregistered nowhere), detected and
> confirmed among the draws all three reference arms miss:
>
> | stratum | detected and confirmed |
> |---|---:|
> | one indel, pooled | 68 of 111, 61.3% (52–70%) |
> | one indel, middle third | 54 of 84, 64.3% |
> | one indel, elsewhere | 14 of 27, 51.9% |
> | clean | 8 of 20, 40% (22–61%) |
>
> So the joint conditional rate of a complete split-point sweep is 0.448 at
> q = 0.05, 0.481 at 0.1, **0.524 at 0.2**, 0.559 at 0.35 and 0.580 at 0.5,
> against 0.529 for detection alone at q = 0.2. The artifact's
> `v2_retention_cutoff` fields compare against v2's whole-message score scale
> and mean nothing for this arm.

---

## phase1-body-direct-sweep-v5 (preregistered)

Status: preregistered 2026-10-09; run 2026-10-10, **null** ([result](#result-run-2026-10-10)).
The configuration's own `status` field was left as committed, because its hash
is a claimed path of the artifact. Configuration:
[experiments/phase1-body-direct-sweep-v5/config.json](../experiments/phase1-body-direct-sweep-v5/config.json),
committed before any run.

Why this one. The rule of
[phase1-split-point-power-v2](#result-run-2026-10-09) chose it once T1 held.
Among one-indel planted keys the climbs of v2, v3 and v4 all miss, the
complete-rule split-point climb detects 62.2%, against a bar of 30%.

What changes from v4: only the climb. The W = 117 windowed climb becomes the
split-point climb, `split_complete` of the control exactly (`ic_grid` 32, mask
credit −8.66), run by `CudaSplitClimber` on the GPU. The message (BYQMZ), the
space (the middle-complete rule, 246,767,040 settings), retention (100),
companions (FKQLZ and XFEDT) and threshold (z ≥ 6) are v4's. The duplicate
notch-start settings v4 found are kept, so the space is exactly the one whose
power was measured. A duplicate is climbed to the identical result, and an
exact tie keeps the earlier setting.

Hypothesis. The three messages are Enigma I traffic under one daily key, and
BYQMZ's key is one v2, v3 and v4 could all miss, most plausibly because BYQMZ
carries one dropped or inserted letter. A complete split-point sweep then
retains a candidate that FKQLZ and XFEDT both confirm at best-start z ≥ 6.

Refuted by: no retained candidate companion-confirmed.

Stated power, conditional on v2, v3 and v4 null (planted draws all three
reference climbs miss, `phase1-split-point-power-v2`; the joint row from
`artifacts/phase1-joint-power-v4-split-complete.json`):

| | clean, 20 | one indel, 111 | q = 0.05 | q = 0.2 | q = 0.5 |
|---|---:|---:|---:|---:|---:|
| detected | 8, 40% | 69, 62.2% | 0.450 | **0.529** | 0.588 |
| detected and companion-confirmed | 8, 40% | 68, 61.3% | 0.448 | **0.524** | 0.580 |

So a null multiplies the remaining odds of a standard reading by about 0.48 at
q = 0.2. With the earlier nulls that comes to about 0.055 in all: 0.035
ungarbled, from a 20-draw stratum, and 0.13 with one indel.

Predictions (in the configuration):

- **companion-confirmed-candidate** (decides): at least one of the 100 retained
  candidates is companion-confirmed.
- confirmed-candidate-is-rank-one: a confirmed candidate is also rank 1 on BYQMZ.
- confirmed-candidate-names-a-fault: a confirmed candidate's best hypothesis
  is a dropped or inserted letter, which is about two thirds of the expected
  confirmations at q = 0.2.
- null-top-near-expected-maximum: with no confirmation, the top score lies
  between z = 5.5 and 7.5 over all 246.8 million scores. v4 reached 6.51.

Target data already seen, before this configuration, in engine work and the
smoke run below:

- a 243,360-setting parity slice of exactly this sweep (0.1%), top −7.9616 (z
  4.74 within the slice);
- 14 full chunks timed for the benchmark (0.9%), of which two top rows were
  printed;
- the smoke run's 158,184 settings.

Only the smoke run's five candidates were companion-checked: none confirmed,
best 4.18. The configuration's `pre_run_facts` record all of it. The sweep
recomputes these settings.

Checked before committing (exploratory, not part of the record): the smoke run
above. That is this configuration cut to wheel order I-II-III and left offset A
(26 chunks), retention 5, scratch output, run twice. It passed every preflight
check, including 24 of 24 split climbs identical to `SplitClimber`, and both
positive controls. It swept the slice in 4.4 s. The second invocation resumed
all 26 chunks with identical candidates and score distribution.

Limits, in the configuration. One plaintext and one fault only. The pooled
null stands in for 246.8 million scores, and the clean stratum is 20 draws.
The mask credit applies to BYQMZ's own masked letter only approximately.
Everything assumes wheels I to V as wired.

Cost: about 1.95 hours of sweep on the RTX 3090 at the measured 0.0285 ms per
setting, plus a few minutes of CPU gates and confirmations. It checkpoints in
1,560 chunks.

Run command:

```bash
python3 phase1_stecker.py --config experiments/phase1-body-direct-sweep-v5/config.json --jobs 1
```

### Result (run 2026-10-10)

Run: the maintainer launched it from a clean tree at `0de0c54` (master, with
pull requests 21 to 23 merged), as one process on the RTX 3090. It ran from
2026-10-10 05:12:50 to 07:09:27 UTC, 1 h 56 min 37 s in all. There was one
invocation, with no stop or resume (1,560 chunks run, none from the checkpoint).
The NVIDIA kernel module and user-space libraries were both 595.99.02 after the
machine's reboot at 05:08 UTC, which cleared a kernel-module/library version
mismatch (595.91 against 595.99) seen on 2026-10-09. 15 of 15 GPU tests passed on that driver before the launch. After the
run, `nvidia-smi` listed no compute process and no `llama-server` was running;
whether LM Studio held VRAM during the run was not recorded. The artifact is
[artifacts/phase1-body-direct-sweep-v5.json](../artifacts/phase1-body-direct-sweep-v5.json).

### Observed

- Preflight: every check passed, including `cuda_climb_matches_batched` (and so
  the 24 of 24 split climbs identical to `SplitClimber`). Both positive controls
  passed.
- Coverage: all 246,767,040 settings of the middle-complete space, in 1,560
  chunks. The sweep took 6,945 s (0.0281 ms per setting, against 0.0285 ms in
  the build benchmark) and the companion confirmation 42 s.
- Score distribution over every setting: mean −8.5040, sd 0.11443 per letter.
  The maximum is −7.8004 (z = 6.15): wheels III-II-I, rings AHP, start CDA, a
  deletion at 132. Rank 100 is −7.9301. The 100 retained are 53 deletions and 47
  insertions, and 84 distinct machines (the notch-start duplicates v4 found).
- Companion confirmation: **none confirmed.** The best minimum over FKQLZ and
  XFEDT is z = 4.84 at rank 33 (wheels IV-V-I, rings ARM, start DUB, a deletion at
  141; FKQLZ 4.95, XFEDT 4.84), against the threshold of 6. Rank 1's is 4.34. Of
  the 100, 3 exceed 4.6 and none exceeds 5. The mean of the 100 minima is 4.05.
  The calibration's nulls had a median near 3.98 and a maximum of 4.60 over 200
  random draws (4.54 over 40 corpus draws).
- Indicator confirmation: no candidate has a compatible ring setting. The best
  pooled date score is −9.36 per letter.
- Cross-check against the CPU, run afterwards and not part of the preregistered
  procedure: all 100 retained candidates were re-climbed from their reported
  wheel order, rings and start with `SplitClimber`. All 100 have the same
  plugboard, the same fault and position, and a score within the artifact's
  nine-decimal rounding (worst difference 5.0 × 10⁻¹⁰).

Predictions:

| prediction | outcome |
|---|---|
| companion-confirmed-candidate (decides) | **failed**: no candidate confirmed |
| confirmed-candidate-is-rank-one | does not apply |
| confirmed-candidate-names-a-fault | does not apply |
| null-top-near-expected-maximum (z 5.5 to 7.5) | **held**: z = 6.15 |

### Interpretation (inference)

- The run is the preregistered sweep. The top score is at the noise maximum for
  246.8 million scores (v4's was z 6.51 over the same count), and the
  companions and the indicator see nothing in the retained 100.
- The best companion z (4.84) is the highest of the four companion-checked
  sweeps (v2 4.47, v3 4.64, v4 4.69). It is above the calibration's 200-draw
  maximum of 4.60, but it is the maximum over 100 retained candidates and
  1.2 below the threshold. Three candidates above 4.6 out of 100 is consistent
  with a null tail slightly heavier than the calibration's; it is not what a
  correct key looks like, which the calibration puts at z ≥ 6 on both
  companions. No candidate stands apart from the rest.
- Weight of the null. The preregistered stated power gives this null an odds
  multiplier of about 0.48 at q = 0.2 (0.524 detected and confirmed). Taking
  the four nulls together, the odds of a standard Enigma I reading of BYQMZ fall
  to about 0.055 (0.035 ungarbled, from a 20-draw stratum, and 0.13 with one
  indel), as the configuration stated. The caveats are those stated: one
  plaintext, at most one dropped or inserted letter, planted stand-ins for the
  earlier nulls, and wheels I to V as wired. Nothing here tests two faults, a
  substituted letter, other reflectors, other wheel wirings, Naval wheels or other
  indicator procedures.
- This is the first sweep whose climb searches the fault, and it found no
  fault-bearing key. If BYQMZ carries one indel and a standard key, the stated
  power puts the chance of missing it at about 0.38 to 0.39 (1 − 0.613).

### Decision

v5 is null at its stated power. Phase 1's body-direct search of BYQMZ under the
standard Enigma I reading has now covered the past-notch space twice, the
complete space with the windowed climb, and the complete space with the
split-point climb, and none confirms. The record does not preregister anything
further. What remains is the case the cited paper raises, that the wheels are
wired differently for Batch C, then two faults or a substituted letter, other
machines, and the crib-driven Bombe. Choosing among them, and whether to stop
the standard-reading search here, is the maintainer's decision.

---

## phase1-fault-power-v1 (preregistered)

Status: preregistered 2026-10-10; run 2026-10-10, S1 held and D1 refuted
([result](#result-run-2026-10-10-1)). Configuration:
[experiments/phase1-fault-power-v1/config.json](../experiments/phase1-fault-power-v1/config.json),
with its analysis script `scripts/fault_power_v1.py`, committed before any run.

Why this one. v5 is null, which takes the odds of a standard reading of BYQMZ to
about 0.055 at q = 0.2. That figure assumes the only fault a message can carry is
one dropped or inserted letter. Nothing completed has measured a substituted
letter or two dropped or inserted letters against any of the four climbs. Before
building another climb or preregistering another sweep, this asks how much of
each the four sweeps already cover. The answer decides between stopping the
standard-reading search and building a substitution-tolerant or a two-split
climb.

Design. The v2 slice, arms and seed discipline, on a new seed (20261110): one
167-letter plaintext, ten pairs, 400 draws in each of three cells (clean, one
substituted letter, two independent dropped or inserted letters), each swept over
its own neighbourhood. The five arms are v2's. Four of them stand in for the
sweeps: `past_notch_whole` (v2), `past_notch_w117` (v3), `complete_w117` (v4) and
`split_complete` (v5). A draw is *covered* when any of those four detects it, and
one minus the covered fraction is the odds multiplier the four nulls leave for a
key with that fault. `stecker_power.perturb_ciphertext` gains the two fault kinds;
the `indel` draws are unchanged and a unit test pins them against the original
algorithm.

Predictions, with the author's guesses disclosed in the configuration:

| id | statement | decides |
|---|---|---|
| S1 | the union detects at least 60% of substitution draws | yes |
| D1 | the union detects less than 50% of double-indel draws | yes |
| runner | `split_complete` detects at least 80% of clean draws; at least 60% of substitution draws; at least as many double-indel draws as `complete_w117` | no |

Decision rule, fixed now. Detection is an upper bound on what the sweeps decide
on, which is companion confirmation, so "not covered" verdicts stand and
"covered" verdicts are provisional. S1 held and D1 held: cost a two-split climb.
S1 refuted and D1 held: cost both new climbs. S1 refuted and D1 refuted: cost a
substitution-tolerant climb. S1 held and D1 refuted: **no stop is decided**; both
kinds are covered by detection, and `scripts/joint_power.py --arm split_complete`
on this artifact measures the confirmed rates (a lower bound for the union) from
which any stop would be decided afterwards. A deciding cell under 100 draws is
not estimable. Nothing further is preregistered by this run.

Disclosed. A 6-draw smoke run of this configuration (draws 0 to 5 of each cell,
scratch output) found the union covering 6 of 6 clean, 5 of 6 substitution and 6
of 6 double-indel draws, against a guess of 30% to 45% for double indels. It is
weak evidence and nothing was changed after it. The full run recomputes those
draws.

Cost: about 20 minutes on the RTX 3090 (v2's 800 draws took 12 minutes).
Detection here is not companion confirmation, and the covered fraction is
reported as a lower bound on the odds multiplier for that reason.

Run command:

```bash
python3 phase1_stecker.py --config experiments/phase1-fault-power-v1/config.json --jobs 4
python3 scripts/fault_power_v1.py
```

### Result (run 2026-10-10)

Run: the maintainer launched it from a clean tree at `88855cd` (master with the
preregistration merged), 2026-10-10 19:49:48 to 20:03:32 UTC, 14 minutes, on 4
spawned workers and the RTX 3090. One invocation. Artifacts:
[the run](../artifacts/phase1-fault-power-v1.json), its
[analysis](../artifacts/phase1-fault-power-v1-analysis.json) from
`scripts/fault_power_v1.py`, and, as the decision rule's provisional branch
required, the [joint confirmation](../artifacts/phase1-joint-power-v5-fault-kinds.json)
from `scripts/joint_power.py --arm split_complete` (run afterwards from the same
commit, 9 minutes, CPU).

### Observed

- Preflight and both positive controls passed. The three runner predictions all
  held: `split_complete` detected 89.5% of clean draws (bar 80%) and 89.0% of
  substitution draws (bar 60%), and detected 23.3 points more double-indel draws
  than `complete_w117` (bar 0).
- Detection by arm, of 400 draws per cell:

| arm (sweep it stands in for) | clean | substitution | double indel |
|---|---|---|---|
| `past_notch_whole` (v2) | 309 (77.3%) | 309 (77.3%) | 83 (20.8%) |
| `past_notch_w117` (v3) | 315 (78.8%) | 306 (76.5%) | 93 (23.3%) |
| `complete_w117` (v4) | 371 (92.8%) | 360 (90.0%) | 136 (34.0%) |
| `split_past_notch` | 273 (68.3%) | 270 (67.5%) | 131 (32.8%) |
| `split_complete` (v5) | 358 (89.5%) | 356 (89.0%) | 229 (57.3%) |
| **any of the four sweep arms** | **393 (98.3%)** | **390 (97.5%)** | **260 (65.0%)** |

- **S1 held:** the union detects 97.5% of substitution draws (95% interval
  95.5 to 98.6%), against a bar of 60%.
- **D1 refuted:** the union detects 65.0% of double-indel draws (60.2 to 69.5%),
  against a bar of under 50%. The author's guess was 30% to 45%.
- Joint detection and confirmation for `split_complete` alone (confirmed by both
  companions at z ≥ 6): clean 346 of 400 (86.5%), substitution 352 (88.0%),
  double indel 225 (56.3%, 51.4 to 61.0%). Given a detection, confirmation held in
  96.6% (clean, 346 of 358), 98.9% (substitution) and 98.3% (double indel) of cases.
- The decision rule's outcome for S1 held and D1 refuted is provisional: no stop
  is decided by this run.

### Interpretation (inference)

- A substituted letter is covered about as well as a clean message. Every arm's
  substitution rate sits within three points of its clean rate. The confirmation step removes few detections. So the
  odds multiplier the four nulls leave for a substituted-letter key is between
  0.025 (union of detections) and 0.12 (`split_complete` alone, confirmed),
  against 0.018 to 0.135 for a clean one.
- Two dropped or inserted letters are covered much less: between 0.35 (union of
  detections) and 0.44 (`split_complete` alone, confirmed) is left. The split
  climb is the arm that matters here, at 57% against 34% for the next best, so it
  finds many of these keys by placing one fault and tolerating the other. The
  other four arms add 8 points to its detections (260 against 229). I have not
  isolated why the guess of 30% to 45% was too low; the planted faults are
  independent and uniformly placed, and some pairs lie so close together or so
  near an end that they are nearly one fault.
- The confirmed union is not measured: confirmation was run for `split_complete`
  only, so the true union multiplier for two faults lies between 0.35 and 0.44
  and for substitution between 0.025 and 0.12.
- What this does to the odds. The single-indel multiplier for the four nulls
  together was 0.13 and the clean one 0.035 (the v5 entry). The substitution case
  now sits between those. The two-fault case is the least excluded garble, at
  0.35 to 0.44, but a message with two independent faults is a priori rarer than
  one with a single fault (at an independent per-fault rate of 0.2 it is about a
  fifth as likely), so it contributes little to the remaining odds. Those
  caveats stand: one plaintext, planted stand-ins for the sweeps, faults uniform
  in position and independent, and wheels I to V as wired.

### Decision

No further sweep is preregistered by this run. By the rule fixed beforehand, the
stop is not decided here. The measurements it called for are in. In the
maintainer's hands: the standard-reading search of BYQMZ can be closed, leaving
odds multipliers of 0.035 (clean), 0.13 (one indel), 0.025 to 0.12 (a
substituted letter) and 0.35 to 0.44 (two indels), or a two-split climb can be costed to lift the last
figure. My inference is that the expected gain from the second is small, because
the case it targets is the least probable one, and that the wheel-wiring question
the cited paper raises is the larger open item. That is a recommendation, not a
result of this run.

---

## Closing the standard-reading search of BYQMZ (2026-10-10)

Status: a decision record, not an experiment. Nothing was run and nothing is
preregistered. The decision is the maintainer's, made 2026-10-10 after
[phase1-fault-power-v1](#result-run-2026-10-10-1).

### Facts

- Four sweeps of BYQMZ under the standard reading (Enigma I, reflector B, wheels
  I to V as wired, ten pairs) are complete and null: v2 and v3 (middle-past-notch,
  whole message and W = 117), v4 (middle-complete, W = 117) and v5 (middle-complete,
  split-point). Each retained 100 candidates and none was companion-confirmed.
  The best companion z across them is 4.84, against a threshold of 6.
- The planted-key stand-ins for those four climbs, taken together, detect by
  fault kind (400 draws each, one plaintext of 167 letters): 98.3% of clean
  messages, 97.5% with one substituted letter, 65.0% with two independent dropped
  or inserted letters. Companion confirmation was measured for the v5 climb alone
  (86.5%, 88.0%, 56.3%). The one-indel figure is from phase1-split-point-power-v2.
- The odds multiplier the four nulls leave, by kind of message (bounds, because the
  union's confirmed rate was not measured; the upper figure uses the v5 climb's
  confirmed rate alone):

| message | multiplier left |
|---|---|
| clean | 0.018 to 0.135 |
| one dropped or inserted letter | 0.13 |
| one substituted letter | 0.025 to 0.12 |
| two dropped or inserted letters | 0.35 to 0.44 |

### Interpretation (inference)

- The multiplier for a whole hypothesis is the prior-weighted sum of those rows,
  and the prior over fault kinds is not measured. Under an illustrative prior of
  70% clean, 20% one indel, 5% substitution and 5% two indels, the four nulls
  leave a multiplier of about 0.06 to 0.15. The two-indel row contributes 0.018
  to 0.022 of that (15% to 31%), so even a climb that found every two-indel key
  would lower the multiplier by at most about 0.02. If two faults were instead as
  likely as 20%, the row would contribute 0.07 to 0.09 (45% to 65% of a
  multiplier of 0.11 to 0.19), and the case for a two-split climb would be much
  stronger. The closure therefore rests on two-fault messages being rare, which
  is an assumption and not a measurement.
- A two-split climb is a large port: the hypothesis grid goes from one position
  and kind to a pair, about the square of the single-split grid, on top of the
  exact-parity work the split port needed.

### Decision (maintainer, 2026-10-10)

The standard-reading search of BYQMZ is closed. No further sweep of BYQMZ under
wheels I to V as wired, reflector B and ten pairs is planned, and no two-split
climb is to be built unless a reason below reopens it.

What the closure covers: one plaintext (BYQMZ, 167 letters), a clean message, one
dropped or inserted letter, one substituted letter, or two independent dropped or
inserted letters (the four fault kinds measured), the 246.8 million middle-complete settings, and the companion
check at z ≥ 6 against FKQLZ and XFEDT.

What it does not cover: any wiring other than wheels I to V as published, other
reflectors, other machines, FKQLZ or XFEDT searched on their own, faults that are
clustered or more than two, a substituted letter combined with another fault of any
kind, two substituted letters (none of these was measured), and transposition. The cited paper's doubt about the
wheel wiring for Batch C is untouched by it, and every null above would be
silent about a different wiring.

What would reopen it: a reply from the paper's authors, or a source, naming a
wiring or machine that can be added at a sourced wiring (about two GPU hours per
wheel set or reflector with the existing split-point climb); evidence that garbles
in this batch are multi-letter; or a reason to put more than a few percent of the
prior on two independent faults. The question to the authors was sent
2026-10-10.

---

## Reopening the question: power at typical plaintext (2026-10-11)

Status: a decision record and two preregistrations. The reasons are in
[code-review-2026-10-11.md](code-review-2026-10-11.md); the maintainer asked for
the v4 sweep to be rerun with the E-Stecker start set (2026-10-11).

### Facts

- Every power control above plants its keys under one 167-letter plaintext of
  index of coincidence 0.0792. German Army traffic averages about 0.061 (Ostwald
  and Weierud 2017; the repository's own published counts give a pooled 0.0593).
- Measured in the review, not preregistered, with the repository's harness and
  identical keys: detection falls steeply with plaintext IC. Over 16 plaintexts
  drawn from the published trigram counts (IC 0.0514 to 0.0625) the whole-message
  climb detected 35.8% of draws given an exact equivalent in the slice, r = 0.87
  with IC. The v5 split-point climb detected 97%, 57%, 20% and 3% at IC 0.0792,
  0.0625, 0.0578 and 0.0514. The failure is a trapped climb, so a failed key
  scores like a wrong setting and no second stage on the top slice can recover it.
- Known stale citation: `experiments/phase1-estecker-power-v1/config.json` (its
  hypothesis and its review note) and the artifact that embeds it still quote the
  withdrawn v5 curve of 0.03, 0.20 and 0.57 at IC 0.0514, 0.0578 and 0.0625. That
  curve used the pooled null threshold. The config is the preregistered record of
  what was believed when the experiment was set up, so it is left as written; the
  corrected figures are in `data/review/plaintext-power-2026-10-12/summary.json`.
- Partial exhaustion of the first plug (the E-Stecker method of the same paper)
  lifted the true-setting climb from 5/24 to 19/24 at IC 0.0578 and from 3/36 to
  14/36 (E) and 27/36 (R, 73 starts) at IC 0.0514. A unigram first-phase
  objective did not help.
- The closure above rests on detection rates measured on one plaintext of
  IC 0.0792. The review's typical-IC union multiplier was subsequently withdrawn
  after the corrected 2026-10-12 rerun; that union remains unmeasured.

### Decision (maintainer, 2026-10-11)

Add partial exhaustion of the first plug to the climb (`climb.first_plug`, all
three engines, parity-tested), measure it on typical-IC plaintexts, and rerun v4's
sweep with it. The closure of 2026-10-10 is not retracted by this entry; it is
conditional on the plaintext's IC, as its caveat "one plaintext" said without
measuring, and the rerun is how that condition is tested.

## phase1-estecker-power-v1 (preregistered)

Configuration:
[experiments/phase1-estecker-power-v1/config.json](../experiments/phase1-estecker-power-v1/config.json).

Hypothesis. On 24 plaintexts of typical letter statistics, partial exhaustion of
the first plug (E: the empty board plus the 25 boards that plug E to another
letter, best final n-gram score kept) lifts the detection rate of v4's climb (W =
117 head and tail, middle-complete) well above its rate without it, clean and with
one dropped or inserted letter.

Design. The fault-power slice (planted wheel order, left offsets within 1, middle
within 2, right within 1), 480 draws in each of two cells (clean, one indel), the
plaintext of draw d being plaintext d mod 24 of 24 Markov samples of the published
counts (seed 20261012, IC 0.0453 to 0.0641, mean 0.0579, listed in the
configuration), the keys the same whichever plaintext. Two arms on the same draws:
`complete_w117` (v4's climb) and `complete_w117_estecker` (the same with
`first_plug` E), each against its own wrong-setting null, detection at 6 null
standard deviations and the planted plugboard recovered exactly. The harness now
reports detection by plaintext and by terciles of plaintext IC.

| id | statement | decides |
|---|---|---|
| P1 | the baseline detects at most 60% of clean draws | the review's concern |
| P2 | the E arm detects at least 75% of clean draws | the sweep |
| P3 | the E arm detects at least 20 points more clean draws than the baseline | the sweep |
| P4 | the E arm detects at least as many one-indel draws as the baseline | no |

The guesses (baseline 35% to 55%, E arm 75% to 90%, gain 30 points or more) are
the author's, made before any measurement of this arm. Decision rule, fixed now:
the v6 sweep launches only if P2 and P3 hold. Its stated power is this run's E-arm
clean detection rate times 96.6% (the share of detections the v5 control
confirmed), recorded in the sweep's configuration by amendment before launch.

Not measured here: companion confirmation of the E arm, a substituted letter, two
faults. Disclosed: a 4-draw smoke run (draws 0 to 3, scratch output, 62 s) passed
every preflight check, including the new first-plug parity check, and showed the
baseline 2 of 4 and the E arm 4 of 4 on clean draws; nothing was changed after it.

Run command:

```bash
python3 phase1_stecker.py --config experiments/phase1-estecker-power-v1/config.json --jobs 8
```

## phase1-body-direct-sweep-v6 (preregistered)

Configuration:
[experiments/phase1-body-direct-sweep-v6/config.json](../experiments/phase1-body-direct-sweep-v6/config.json).

Hypothesis. BYQMZ's key is one v4 could miss because its plaintext has typical IC
(about 0.06) and the climb from the empty plugboard is trapped far more often than
the stated power assumed; the same sweep with the E-Stecker start set then retains
a candidate that the companion check (FKQLZ and XFEDT at z >= 6) confirms.

Design. v4's configuration exactly (BYQMZ, middle-complete, W = 117, 246,767,040
settings, 1,560 chunks, retention 100, companion threshold 6, cuda engine from the
start) plus `climb.first_plug = {letters: "E"}`: 26 start boards per climb. v4 took
33 minutes on the RTX 3090; the projection is about 14 hours (an inference,
replaced by the measured figure). Predictions: a confirmed candidate (deciding);
rank one if confirmed; the E start set never scores below v4 on v4's 100 retained
settings (a check that the implementation did not change the climb); all 100
retained candidates re-climb identically on the CPU batched climber; if null, the
top score lies between z 5.5 and 8.0. The original preregistration described a null as an additional odds multiplier.
The 2026-10-12 evidence amendment corrects this: conditional joint confirmed
power after the earlier four nulls is unmeasured, so no such multiplier is
calibrated. A smoke run through the runner on a 72-setting slice passed the
preflight and both positive controls.

Run command (after the power control's result and amendment are committed):

```bash
python3 phase1_stecker.py --config experiments/phase1-body-direct-sweep-v6/config.json --jobs 1
```

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


### Exploratory v5 plaintext-power rerun (2026-10-12)

Observed: the corrected `plaintext_power.py` rerun uses the split-complete arm's
own null threshold. Detection given an exact equivalent is 39/40 for the
repository plaintext (IC 0.0792), and 8/40, 22/40, 15/40 and 22/40 for four
Markov texts (IC 0.0578, 0.0574, 0.0600 and 0.0625). Pooled Markov detection is
67/160 (41.9%), mean IC 0.0594, Pearson r 0.39 and slope +2.8 percentage points
per +0.001 IC. The same 40 key draws are reused across all five texts.

The user ran the exploratory command recorded in
[data/review/plaintext-power-2026-10-12/summary.json](../data/review/plaintext-power-2026-10-12/summary.json).
All ten original config/output files are preserved there unchanged, with SHA-256
checksums. Outputs record clean commit `c2ae3a7cdf76662bde8fd57361c4cc8088463a71`,
CUDA engine and one worker. Key seed is 424242; text seed is the script default 11.
This is a retrospective record, not a new preregistration. Hypothesis and
refutation metadata inherited from the base fault-power configuration describe a
different experiment and are not tested by this single-arm clean-text run.

Interpretation (inference): the repository plaintext is easier than these four
model-generated texts. Four texts and one shared key seed do not establish power
on authentic Army traffic or isolate IC as the cause. Companion confirmation and
the four-arm union were not measured. The review's earlier integrated curve and
numerical typical-IC odds multipliers are withdrawn; the corrected measured table
replaces its pending figures. Next: measure plaintext-aware joint confirmed power
before deriving new closure multipliers.


## E-Stecker result recorded and v6 readiness amendment (2026-10-12)

### Observed

`artifacts/phase1-estecker-power-v1.json` was run on 2026-10-11 from clean
commit `4749bce`, 22:46:01-22:58:42 UTC, 760.314 seconds, CUDA, eight requested
workers (the GPU engine uses one driver process). Source config SHA-256
`51ac96a277b6564d2bf38326c05b3e05d225125173bf180dc624d00c138c79a1`
matches the committed config. Full artifact SHA-256:
`1bb126a60417e6b8caab5a177858f72bcfae2e7050047ebd2a21ff026f26bf11`.
The existing raw artifact and its frozen preregistration config are preserved
unchanged so their recorded hashes remain valid. Completion is recorded in
the artifact and this history. Preflight and positive
controls passed. There are 24 Markov plaintexts (seed 20261012) and 480 key
draws in each cell, with the configured key seed preserved in the artifact.

Clean baseline/E: 165/480 and 363/480, gain 198/480 (41.25 percentage points).
One-indel baseline/E: 72/480 and 240/480, gain 168/480 (35 points). P1-P4
passed. P2's 75% threshold was exceeded by three draws; the pooled key-draw
Wilson interval is 71.59-79.25%, and does not capture plaintext/model uncertainty.

A retrospective paired-count analysis finds no baseline-only detection:
clean both 165, E-only 198, neither 117; indel both 72, E-only 168, neither 240.
The E arm detects 198/315 (62.86%) of baseline clean misses and 168/408 (41.18%)
of baseline indel misses. This analysis was not preregistered and conditions
only on the baseline v4 arm, not on the four earlier arms or confirmations.

### Interpretation (inference)

E-Stecker meets the preregistered P2/P3 launch rule and warrants v6. Its gain
is evidence on this model-text distribution and search neighbourhood, rather
than a measured probability of decoding the actual challenge. The promised
borrowed v5 confirmation factor (0.966) yields projections 0.7305375 clean and
0.483 indel; these are inference and are not measured E-arm confirmation rates.
A further odds multiplier after v2-v5 null is not established.

### Amendment and next decision

Before v6 launch, its configuration now records the actual measured power,
labels the borrowed confirmation extrapolation, removes the uncalibrated
remaining-odds claim, and pins this control via `power_prerequisite`. The
runner verifies completed clean provenance, P2/P3, recomputed rates, source
config/input hashes, compatible climb, ring rule and target length before
search. Invalid first-plug starts at zero pair capacity are rejected.
The control is registered as long-running in `artifact_claims.json`.

The measured settings, scorer, 26 starts, retention 100 and companion threshold
6 are kept. No randomized restart budget, extra source wiring, or combined
E/split climb was added without a control. V6 remains unrun as of this entry;
LM Studio was using the GPU during readiness work and was not stopped.
Next: launch from a clean checkout on an available GPU, record all starts,
then verify CPU parity of all retained candidates and the v4 non-decrease
prediction. The tests and smoke-run evidence are recorded in the dated review.


Readiness smoke observed (2026-10-12): the separately recorded bounded config
`data/review/readiness-2026-10-12/smoke.config.json` kept the calibrated climb
and ring rule, but used one wheel order, one start on each axis, one right ring
and retention one. Its hypothesis and refutation were recorded before launch.
The runner completed all nine settings in 344.304 seconds in total, with all
seven preflight checks, both positive controls and the pinned power gate
passing. The review tree was dirty and its exact module hashes/status are in
`smoke.json`; no clean-source claim is made. LM Studio was concurrently on the
GPU, so this provides no idle-GPU speed estimate. The direct sweep API then
resumed the unchanged checkpoint, ran zero new settings and reproduced every
candidate; that API resume does not claim a second preflight/control run.
Raw preregistration and resume output are preserved alongside the smoke.

Final readiness verification (2026-10-12): the GPU-enabled suite passed all
305 tests, no skips; the affected-path suite passed 111. Independent simulation
agreed on 3,000 keys. Artifact drift and determinism each reported zero failing
artifacts, skipping long-running/superseded entries as declared. The completed
E control's 33 claim paths and pinned bytes were separately verified. Full v6
has not been launched; these fixes are saved on the review branch
`codex/readiness-review-2026-10-12`, based on `1703705`.

## Result: phase1-body-direct-sweep-v6 (run 2026-10-13)

Configuration:
[experiments/phase1-body-direct-sweep-v6/config.json](../experiments/phase1-body-direct-sweep-v6/config.json),
as amended 2026-10-12. Hypothesis and refutation criterion were fixed before the run
(see the preregistration above). Artifact:
[artifacts/phase1-body-direct-sweep-v6.json](../artifacts/phase1-body-direct-sweep-v6.json),
SHA-256 `0b46a9e4d8849ff7787f6b96845ee745413617b56b0c88744367447e972b2121`.

### Run record

Launched 2026-10-13 05:47:58 UTC from clean `master` at `ebeb9ef` (after PR #34
merged at 05:47:01), `--jobs 1`, cuda engine, one invocation, no resume; completed
17:59:25 UTC (43,887 s in all, 43,501 s of sweep, 0.176 ms per setting). RTX 3090,
CUDA 12.8, numpy 2.2.6, Python 3.10.12. The GPU was shared with an unrelated
LM Studio `llama-server` (about 10.7 GB, 34% utilisation at launch), which was not
stopped; this changes wall-clock time and not the result, because the cuda climb
is bit-exact. The runner's power gate (pinned artifact SHA-256 `1bb126a6...`) passed
before any search, as did all seven preflight checks including
`first_plug_climbs_match` and `cuda_climb_matches_batched`, and both positive
controls. The checkpoint is `build/phase1-body-direct-sweep-v6.checkpoint.jsonl`
(git-ignored and disposable; the artifact is the record).

### Observed

- All 1,560 chunks, 246,767,040 settings, 100 retained candidates (100 distinct
  machines).
- **No retained candidate is companion-confirmed**: `confirmed_candidate_ranks` is
  empty. The best minimum companion z over the 100 is 4.568 against the threshold 6;
  the median is 3.96, and ranks 1 to 3 are 3.72, 3.76 and 3.96.
- Sweep score distribution over all settings: mean -8.1186, sd 0.0807, maximum
  -7.5133 per letter, **top z 7.498**. For reference, v4: top z 6.51, best companion z
  4.69; v5: top z 6.15, best companion z 4.84.
- None of the 100 retained candidates has a ring setting compatible with the clear
  indicator under either ordering (`compatible_ring_settings` 0 for all 100).
- Predictions: the deciding one (a companion-confirmed candidate) was refuted.
  `null-top-near-expected-maximum` held: z 7.50 lies in the stated 5.5 to 8.0.
  The two checks below held.

### Post-run checks (run 2026-10-13, `scripts/v6_postrun_checks.py`, evidence in `data/review/v6-postrun-2026-10-13/summary.json`)

Run from `ebeb9ef` (tracked tree clean), 100 s, 16 workers. Before the checks the
comparison was shown to flag a deliberately wrong plugboard and a deliberately lower
score.

- `cuda-matches-reference-on-retained`: **held**. All 100 retained candidates
  re-climbed on the CPU with v6's own settings (W = 117, E starts) give the cuda
  record's plugboard, winning window and score, with the CPU batched climber
  (100 of 100) and with the pure-Python reference climb (100 of 100). The worst score
  difference is 4.98e-10, the artifact's nine-decimal rounding.
- `v4-retained-settings-do-not-fall`: **held**. Re-climbing v4's 100 retained
  settings with E starts gives a score at least v4's on all 100 (none fell by more
  than 1e-9): 98 are equal and 2 rose (largest gain 0.0227 per letter). As the control
  that the check can see a difference, the same rows climbed with v4's own settings
  reproduce v4's recorded plugboard, window and score in 100 of 100. The best E score
  on v4's rows is -7.5395, v4's own rank 1.
- Check C (not preregistered): v6 swept every setting v4 did, and no v4 retained
  setting scores above v6's 100th retained score (-7.5831) under E starts without being
  among v6's retained rows with the same score: no inconsistency.

### Interpretation (inference)

- The standard-Enigma-I reading of BYQMZ that this sweep could reach, at typical
  plaintext IC with at most the faults the head-and-tail climb tolerates, is not
  supported by this sweep: no candidate's wheel order, rings and plugboard decipher
  FKQLZ or XFEDT above noise. A top z of 7.50, higher than v4's 6.51 and v5's 6.15, is what
  the best of 26 climbs per setting would give over a noise-only distribution, so it
  need not indicate a near miss; the companion scores (best 4.57) and the absent
  indicator compatibility point the same way.
- It strengthens the case against the reading only as far as the stated power
  reaches, and that power is a projection: 75.6% clean detection measured on Markov
  plaintexts, times v5's confirmation factor 0.966, from a slice around a planted
  key and not the whole space. E-start companion confirmation and full-space retention
  were not measured. Conditional joint power on these plaintexts has not been
  measured, so no odds multiplier is claimed, and none follows for BYQMZ, whose
  plaintext IC is unknown.
- The check results say the cuda first-plug climb and the reference agree on every
  retained row and that adding E starts did not change v4's climb at v4's retained
  settings; they do not validate the climb outside those 200 rows (the preflight
  and `tests/test_first_plug.py` cover random settings).
- What a null leaves open is unchanged: other wheel wirings (the cited paper's doubt
  about Batch C), other reflectors, two faults, a substituted letter combined with
  another fault, other machines, and a message that is not Enigma output (the
  publishers say they are not sure these messages are).

### Next decision

Nothing further is preregistered. Candidates, for the maintainer: a conditional joint
power calibration of the E-Stecker arm (companion confirmation and retention, which
would convert the projection into a measured multiplier); a sourced alternative wiring
from the authors, if they reply; or stopping the standard-reading search again, now
with the typical-IC gap measured and covered. The reply to the 2026-10-10 question to
the authors, if any, is not recorded.

## phase1-estecker-joint-power-v1 (preregistered 2026-10-14)

Configuration:
[experiments/phase1-estecker-joint-power-v1/config.json](../experiments/phase1-estecker-joint-power-v1/config.json),
analysis `scripts/joint_power_estecker_v1.py`, both committed before the run. Draws 0 to 5
of each cell had been computed in a scratch smoke run before that commit and their outcomes
printed, so they were not unseen when the predictions were fixed; see the amendment to the
result below.

Why this one. v6 was launched on a stated power that was a projection: the measured
E-arm clean detection (75.6%) times v5's confirmation factor (0.966), measured on one
high-IC plaintext. Companion confirmation and retention in the sweep's top 100 were not
measured for the E climb at typical IC. This run measures the sweep's own decision rule,
retained and companion-confirmed, on planted keys.

Hypothesis. At typical plaintext IC, a planted standard Enigma I key with at most one
dropped or inserted letter is retained by v6's sweep (top candidate scoring at or
above v6's 100th-retained score, -7.583122342) and companion-confirmed through two
planted companions (107 and 97 letters, z >= 6) at a rate of at least 60% clean and
within 10 points of the 73.05% projection (E arm), and the E arm's clean success
exceeds v4's climb's by at least 20 points.

Design. A fresh `end_to_end_power` run, same slice and two arms as
`phase1-estecker-power-v1`, on new keys (seed 20261115) and 24 new Markov plaintexts
(seed 20261114, IC 0.0505 to 0.0744, mean 0.0598, none shared with the gate run), 480
draws in each of two cells (clean, one indel). The analysis then plants two fresh
Markov companions per draw under the planted key and runs the sweep's companion check
on each arm's top candidate; the retention cutoff for each arm is its own sweep's
lowest retained score (v4 -7.634712742, v6 -7.583122342). Fresh draws, because v6 was
launched on the gate run's P2 result, which cleared its bar by three draws, and rates
measured on those same draws carry that selection.

| id | statement | decides |
|---|---|---|
| R1 | the E arm detects at least 70% of clean draws (replication of P2) | no |
| R2 | the E arm detects at least 20 points more clean draws than v4's climb (replication of P3) | no |
| R3 | the E arm detects at least as many one-indel draws as v4's climb | no |
| J1 | E-arm clean sweep success (retained and confirmed) is at least 60% | yes |
| J2 | E-arm clean sweep success is within 10 points of the 73.05% projection | yes |
| J3 | confirmed given detected, E arm clean, is at least 90% (the borrowed factor was 96.6%) | yes, for the factor |
| J4 | E-arm clean sweep success exceeds v4's climb's by at least 20 points | yes |
| J5 | E-arm one-indel sweep success at least v4's climb's | no |
| J6 | retained given detected, E arm clean, is at least 90% | no |

The author's guesses, before any joint measurement: confirmation given detection 85%
to 97%, retention given detection above 90%, E-arm clean success 0.60 to 0.70, one
indel 0.35 to 0.45, gain over v4's climb 30 points or more. Decision rule, fixed now:
if J1 to J4 hold, v6's stated power becomes the measured E-arm sweep success, clean and
one indel, with its interval, replacing the projection; a refuted prediction is recorded
as such and the measured figure replaces the projection whichever way it differs. No
result here is a calibrated odds multiplier for BYQMZ: the prior over fault kinds and
over plaintext IC is unmeasured, and the earlier sweeps' union is not remeasured. No
sweep is launched or changed by this run.

Not measured: a substituted letter, two faults, several candidates retained near the
true key (the top candidate only is judged, which is conservative), real companions.
Disclosed: a 6-draw smoke run of the configuration and of the analysis on its scratch
artifact (scratch output) passed every preflight check; nothing was changed after it.
The same analysis on the gate run's 960 draws will be run after the primary result and
labelled post hoc.

Run command:

```bash
python3 phase1_stecker.py --config experiments/phase1-estecker-joint-power-v1/config.json --jobs 8
python3 scripts/joint_power_estecker_v1.py
```

### Result: phase1-estecker-joint-power-v1 (run 2026-10-14)

Run record. Power run from clean `c9409d8` (the preregistration commit), 04:51:48 to
05:04:31 UTC, 677.9 s, cuda engine, 8 requested workers, one invocation; preflight
(including `first_plug_climbs_match`) and both positive controls passed. RTX 3090,
CUDA 12.8, numpy 2.2.6, Python 3.10.12; the GPU showed about 1 GB in use by another
process at launch. The analysis ran afterwards from the same commit
(`scripts/joint_power_estecker_v1.py`, 189 s on 16 processes). Artifacts and SHA-256:
`artifacts/phase1-estecker-joint-power-v1.json` (`d11c4501...`, the raw power run),
`artifacts/phase1-estecker-joint-power-v1-joint.json` (`65b2477f...`, the preregistered
analysis) and `artifacts/phase1-estecker-joint-power-v1-same-draws.json`
(`65bf0392...`, secondary and post hoc). Seeds: keys 20261115, plaintexts 20261114,
companions 20261116.

#### Amendment (2026-10-15, after review of PR #36)

Two review findings, both correct, change how the results below are to be read.

1. *Pre-observed draws.* The 6-draw smoke run of the configuration and of the analysis
   covered draws 0 to 5 of each cell, and its printed outcomes (sweep success, J1 to J6) are in the
   configuration's `pre_run_facts.smoke_run`. The run recomputes those 12 draws, so the
   full sample was not unseen when the predictions were committed, and calling the
   all-draws artifact `preregistered` overstated it. (The configuration's clause that no joint
   analysis of any draw had been run referred to the gate run's 960 draws, which is still
   true; it does not cover these.) The primary result now leaves out draws 0 to 5 of each
   cell (474 draws per cell remain) and `result.all_draws` keeps the full 480 for comparison.
   No prediction changes: J1 to J6 all hold on the primary set.
2. *Repeated plaintexts.* The 480 draws per cell come from 24 plaintexts, 20 draws each, and the
   rates differ strongly between plaintexts (by IC tercile 56%, 84%, 95% for E's detection),
   so a binomial interval over pooled draws treats them as 480 independent samples of text and is too
   narrow for a claim about typical text. The analysis now also reports a percentile bootstrap
   that resamples plaintexts with replacement (10,000 resamples, seeded);
   `interval_95` is kept and is the draw-level one, `cluster_interval_95` is the one to quote.

Corrected headline figures (primary set, 474 draws per cell; the all-draws figures in the
tables below differ by at most a point):

| | clean | one indel |
|---|---|---|
| E sweep success | 363 / 474 = **76.6%**, plaintext-cluster interval 67.4 to 85.0 (draw-level 72.6 to 80.2) | 276 / 474 = **58.2%**, 50.8 to 65.8 (draw-level 53.7 to 62.6) |
| v4's climb | 161 / 474 = 34.0%, 24.6 to 43.5 | 105 / 474 = 22.2%, 14.8 to 30.6 |
| E minus v4, paired | +42.6 points, 36.6 to 48.7 (202 draws E only, 0 v4 only) | +36.1, 30.7 to 41.6 (172 E only, 1 v4 only) |
| confirmed given detected, E | 364 / 371 = 98.1%, 96.6 to 99.4 | 276 / 280 = 98.6%, 97.1 to 99.7 |
| retained given detected, E | 370 / 371 = 99.7%, 99.1 to 100 | 279 / 280 = 99.6%, 98.9 to 100 |

The same corrections apply to the post hoc same-draws analysis (no draws excluded, since
all of it is post hoc): E clean 357 / 480 = 74.4%, plaintext-cluster interval 66.3 to 81.5; one
indel 236 / 480 = 49.2%, 42.9 to 55.0.

What this changes in the reading: the point estimates and the predictions are as before, and
the intervals about typical text are about twice as wide as quoted. The measured
miss probability for a clean standard reading at typical text is therefore 15% to 33% (the
cluster interval of 1 minus E's success), not the 23% to 26% the interpretation below quotes
from point estimates; for one indel 34% to 49%, not 42% to 51%. The paired gain over
v4's climb is the sturdiest result, because plaintext variation cancels in a paired difference.

#### Observed

Power run, fresh draws (480 per cell), detection by the harness's rule:

| cell | v4's climb (`complete_w117`) | E-Stecker (`complete_w117_estecker`) |
|---|---|---|
| clean | 167 (34.8%) | 376 (78.3%) |
| one indel | 107 (22.3%) | 282 (58.8%) |

R1 held (78.3% against 70%), R2 held (gain 43.5 points against 20), R3 held (gain
36.5 against 0).

Joint analysis, preregistered, E arm (sweep success = retained and companion-confirmed):

| | clean | one indel |
|---|---|---|
| detected | 376 / 480 | 282 / 480 |
| retained (score at or above v6's 100th-retained, -7.5831) | 375 | 283 |
| companion-confirmed | 369 | 283 |
| **sweep success** | **368 / 480 = 76.7% (95% interval 72.7 to 80.2)** | **278 / 480 = 57.9% (53.5 to 62.3)** |
| confirmed given detected | 369 / 376 = 98.1% (96.2 to 99.1) | 278 / 282 = 98.6% |
| retained given detected | 375 / 376 = 99.7% | 281 / 282 = 99.6% |

v4's climb with its own sweep's cutoff (-7.6347): clean 163 / 480 = 34.0% (29.9 to
38.3), one indel 105 / 480 = 21.9%. Paired on the same draws, clean: both 163, E only
205, v4 only 0, neither 112; one indel: both 104, E only 174, v4 only 1, neither 201.

Predictions, all held: J1 (clean success 76.7% against at least 60%), J2 (3.6 points
from the 73.05% projection, within 10), J3 (confirmed given detected 98.1% against at
least 90%), J4 (gain 42.7 points against at least 20), J5 (one-indel gain 36.0
against at least 0), J6 (retained given detected 99.7% against at least 90%).

Detection by tercile of plaintext IC (8 plaintexts, 160 draws each), E arm clean:
IC 0.0505 to 0.0573: 89 / 160 (55.6%); 0.0579 to 0.0613: 135 / 160 (84.4%); 0.0614
to 0.0744: 152 / 160 (95.0%). One indel: 42.5%, 58.1%, 75.6%. v4's climb, clean:
14.4%, 36.3%, 53.8%.

Secondary, post hoc, the gate run's own 960 draws (selection applies): E-arm sweep
success clean 357 / 480 = 74.4% (70.3 to 78.1), one indel 236 / 480 = 49.2% (44.7 to
53.6); confirmed given detected 98.3%, retained given detected 100%; v4's climb clean
163 (34.0%), one indel 69 (14.4%). J1 to J6 also hold there.

#### Interpretation (inference)

- The projection was a fair stand-in for the clean case: measured sweep success 76.7%
  (fresh) and 74.4% (the gate's draws), against a projected 73.05%. For one indel the
  projection (48.3%) was low on the fresh draws (57.9%) and matched the gate's
  (49.2%). The difference between the two sets is larger than the sampling interval, so
  the plaintext set moves the rate: the fresh plaintexts have a higher mean IC (0.0598
  against 0.0579). The measured power is therefore a range over plaintext sets, about
  74% to 77% clean and 49% to 58% one indel, not a point.
- The power is limited by detection, not by what follows it: sweep success is within
  eight draws of detection in every cell, confirmation given detection is about 98%
  (the borrowed factor, 96.6%, was close) and retention given detection is at least
  99.6%. The concern that retention in the full space would cost power did not
  materialise at v6's measured cutoff, given that the noise tail at that cutoff is
  that of BYQMZ's own sweep.
- The gain over v4's climb survives confirmation and retention: 205 clean draws that
  only E-Stecker found, none that only v4's climb found.
- The average hides a strong dependence on plaintext IC: for plaintexts of IC below
  0.057 the E arm's clean success is about 56% (71 of its 104 clean misses lie
  there), against 95% above 0.061. If BYQMZ's plaintext is of low IC, v6's power for it
  is nearer 55% than 77%; its IC is unknown.
- What a v6 null therefore says: for a standard Enigma I reading with a clean or
  once-garbled message and plaintext of typical statistics, v6 would have missed the
  key about 23% to 26% (clean) or 42% to 51% (one indel) of the time, more for low-IC
  plaintexts. That is a measured miss probability for those two kinds, not a calibrated
  odds multiplier for BYQMZ: the prior over fault kinds and over plaintext IC is
  unmeasured, the earlier sweeps' union at typical IC was not remeasured here, and v6's
  own null has the caveats of its entry.

#### Not run, and the next decision

Not run: the union of v2 to v5 and v6 at typical IC (needed for a multiplier after all
five sweeps), a substituted letter or two faults for the E arm, several candidates
retained near the true key (only the top was judged, which is conservative), real
companions. v6's configuration is not amended: it is frozen with its run, and its
stated power is now this entry. Nothing further is preregistered. For the
maintainer: stop the standard-reading search with the measured, IC-dependent miss
probabilities on record; or measure the union at typical IC to state a combined
multiplier; or spend the next climb on low-IC plaintexts, where the E arm is weakest
(R-Stecker's 73 starts was 27 of 36 at IC 0.0514 in the review).

## First-stage climb for low-IC plaintexts: screen, implementation, control (2026-10-15)

Status: a screen (exploratory), an implementation, and a preregistration. Nothing in the
sweep path has run.

### Why

phase1-estecker-joint-power-v1 measured the E-Stecker climb at 56% clean detection in the
lowest IC tercile, 84% in the middle and 95% in the highest. The maintainer asked for a
stronger first-stage climb for low-IC plaintexts.

### Screen (not preregistered; `scripts/review/first_stage_screen.py`, evidence in `data/review/first-stage-screen-2026-10-14/`)

True-setting climbs on the 117-letter head window, ten plugs, 12 low-IC Markov plaintexts
(IC 0.0514 to 0.0575) of 30 draws each, 360 draws, each method calibrated against its own
wrong-setting null at 6 standard deviations. Detection and cost (evaluations on the null
climbs, relative to the empty-board climb):

| method | detected (95% interval) | cost |
|---|---|---:|
| base | 7.8% (5 to 11) | 1 |
| E-ngonly | 32.8% (28 to 38) | 13.0 |
| E-ic4 | 38.9% (34 to 44) | 16.8 |
| E (v6) | 36.7% (32 to 42) | 25.9 |
| screen-ic-k26 (score the 325 single plugs once, climb the best 26) | 41.1% (36 to 46) | 26.3 |
| R-ngonly | 48.3% (43 to 53) | 35.6 |
| R-ic4 | 52.5% (47 to 58) | 47.0 |
| I-ngonly | 58.9% (54 to 64) | 65.9 |
| R | 52.2% (47 to 57) | 72.7 |
| I-ic4 | 63.3% (58 to 68) | 87.5 |
| I | 59.4% (54 to 64) | 135.5 |
| solo-ngonly (all 325 single plugs) | 67.8% (63 to 72) | 157.6 |
| solo-ic4 | 73.6% (69 to 78) | 209.8 |

The first screen (base, E, R, I, solo, screen-ic and screen-ng at k = 8 and 26, and 26
random kicks) reproduced these rows' shared numbers exactly in the second. Screening and
kicks did not beat starting from more boards; the IC phase is about two thirds of a
start's work (3,746 of 5,912 evaluations for the empty board); capping it at four passes
or skipping it for the extra starts lost no power the paired counts could see (McNemar p
0.18 to 1.0 for ic4 against full, 0.21 to 0.93 for ngonly against full, at E, R and I).
R-ngonly against E, same draws: 84 detected only by R-ngonly, 42 only by E, p = 0.0002.

Cost on the GPU, measured afterwards on 16,384 random settings of BYQMZ with v6's window
and settings: E 0.1753 ms per setting (12.0 h for the 246.8 million of a v6-sized
sweep), E-ic4 0.1275 (8.7 h), R-ngonly 0.2931 (20.1 h, 1.67 times E), R-ic4 0.3556
(24.4 h), I-ngonly 0.5498 (37.7 h). The IC phase is cheaper per evaluation than the
n-gram phase, so ngonly saves less than its evaluation count and ic4 more.

### Decision (maintainer, 2026-10-15)

Implement R-ngonly: the E, N and R first-plug starts with the extra starts climbed by
n-gram score alone and the empty board climbed in full.

### Implementation (commit `15490a6`)

`climb.first_plug` gains two optional keys: `ic_passes` (cap on the IC phase wherever it
runs) and `start_phases: "ngram_only"` (the extra starts skip the IC phase). Both default
to the old behaviour, so no existing configuration or checkpoint fingerprint changes.
Reference, batched and CUDA climbs (the split-point kernel is untouched and still refuses
`first_plug`). Tests: the reference against a by-hand composition of `climb_stecker`
calls; batched against reference and CUDA against batched on plaintext, evaluations,
score and window, for three option combinations, whole and windowed, masked and short
bodies; a check that mismatched option pairs disagree (so the parity tests can fail);
the preflight and the config loader. Full suite 323 passed.

## phase1-rngonly-power-v1 (preregistered 2026-10-15)

Configuration:
[experiments/phase1-rngonly-power-v1/config.json](../experiments/phase1-rngonly-power-v1/config.json),
analysis `scripts/rngonly_power_v1.py`, both committed before the run. Draws 0 to 5 of each cell had been computed in a scratch smoke run before that commit and their outcomes printed, so they were not unseen when the predictions were fixed; see the amendment to the result below.

Hypothesis. On fresh keys and 24 fresh plaintexts stratified by IC, the R-ngonly climb
detects more planted keys than v6's E-Stecker climb where E is weakest and loses nothing
where it is strong: at least 8 points more clean draws in the lowest IC tercile, at least
4 points more overall, no more than 2 points fewer in the highest tercile, and at least
as many one-indel draws overall.

Design. The fault-power slice, three arms on the same draws (v4's climb, v6's E climb,
R-ngonly), 720 draws in each of two cells (clean, one indel), keys seed 20261123, 24
Markov plaintexts (seed 20261122) kept by rejection into three strata of 8 (IC 0.0529 to
0.0574, 0.0583 to 0.0614, 0.0633 to 0.0765; mean 0.0608), none shared with earlier
sets, 30 draws per plaintext, 240 per tercile per cell. Each arm against its own null,
detection at 6 null standard deviations with the planted plugboard recovered exactly.
The strata are a third each, so pooled rates weight low-IC plaintext more than Army
traffic does; the by-tercile results are primary.

| id | statement | decides |
|---|---|---|
| D1 | low tercile, clean: R-ngonly detects at least 8 points more than E (paired) | yes |
| D2 | overall, clean: R-ngonly at least 4 points more than E | yes |
| D3 | high tercile, clean: R-ngonly at most 2 points below E | yes |
| D4 | overall, one indel: R-ngonly at least as many as E | yes |
| S1 | the E arm detects at least 70% of clean draws overall (replication) | no |
| N1 | low tercile, clean: R-ngonly at least 65% | no |
| N2 | overall, clean: R-ngonly at least 80% | no |

The author's guesses, before any measurement of this arm: a gain of 10 to 15 points in the
lowest tercile, 3 to 6 in the middle, about 1 in the highest, 6 to 9 overall, and 6 to 9
on one indel. Decision rule, fixed now: if D1 to D4 hold, R-ngonly is adopted for the
next BYQMZ sweep (v7, about 20 hours on this GPU), which is then preregistered with this
control pinned as its power prerequisite, as v6 was; its stated power is a projection
(this control's detection times the E arm's measured confirmation, 0.98) until its own
joint power is measured. If D1 is refuted no v7 is preregistered on this basis; if only
D2 is refuted the maintainer decides whether the low-IC-only gain is worth 1.67 times
v6's cost; if D3 or D4 is refuted the loss is weighed against D1's gain first.

Not measured here: companion confirmation and retention (the R-ngonly climb's noise tail
is heavier, so its retention cutoff in a real sweep will be higher than v6's), a
substituted letter, two faults. Disclosed: a 6-draw smoke run (scratch output, 3 min 25
s) passed every preflight check including `first_plug_climbs_match` on both first-plug
arms (64 of 64 identical), and the analysis script's tercile counts equal the harness's
on an existing artifact; nothing was changed after it.

Run command:

```bash
python3 phase1_stecker.py --config experiments/phase1-rngonly-power-v1/config.json --jobs 8
python3 scripts/rngonly_power_v1.py
```

### Result: phase1-rngonly-power-v1 (run 2026-10-15)

Run record. From clean `3067143` (the preregistration commit), 13:59:21 to 14:37:20 UTC,
2,103 s, cuda engine, 8 requested workers, one invocation; preflight (including
`first_plug_climbs_match`, 64 of 64 identical, worst score difference 0.0) and both
positive controls passed. RTX 3090, CUDA 12.8, numpy 2.2.6, Python 3.10.12; about 0.8 GB of
the GPU was in use by another process at launch. Artifacts and SHA-256:
`artifacts/phase1-rngonly-power-v1.json` (`d7affdcb...`, the raw run) and
`artifacts/phase1-rngonly-power-v1-terciles.json` (`78770d5e...`, the preregistered
analysis). Seeds: keys 20261123, plaintexts 20261122.

#### Observed

Detection by the harness's rule, 720 draws per cell (240 per tercile), detection counts and
rates with the paired count against the E arm (R-ngonly only / E only) and the exact McNemar p:

| clean | v4's climb | E (v6) | R-ngonly | R-ngonly vs E |
|---|---|---|---|---|
| overall | 324 (45.0%) | 605 (84.0%, 81.2 to 86.5) | 628 (87.2%, 84.6 to 89.5) | 71 / 48, +3.2 points, p = 0.043 |
| low IC | 49 (20.4%) | 161 (67.1%) | 178 (74.2%, 68.3 to 79.3) | 41 / 24, +7.1, p = 0.046 |
| mid IC | 123 (51.2%) | 219 (91.2%) | 224 (93.3%) | 18 / 13, +2.1, p = 0.47 |
| high IC | 152 (63.3%) | 225 (93.8%) | 226 (94.2%) | 12 / 11, +0.4, p = 1.0 |

| one indel | v4's climb | E (v6) | R-ngonly | R-ngonly vs E |
|---|---|---|---|---|
| overall | 173 (24.0%) | 448 (62.2%) | 504 (70.0%, 66.6 to 73.2) | 134 / 78, +7.8, p = 0.0001 |
| low IC | 18 (7.5%) | 90 (37.5%) | 131 (54.6%) | 61 / 20, +17.1, p < 0.0001 |
| mid IC | 55 (22.9%) | 163 (67.9%) | 175 (72.9%) | 43 / 31, +5.0, p = 0.20 |
| high IC | 100 (41.7%) | 195 (81.2%) | 198 (82.5%) | 30 / 27, +1.3, p = 0.79 |

Strata IC: low 0.0529 to 0.0574, mid 0.0583 to 0.0614, high 0.0633 to 0.0765.

Predictions: **D1 refuted** (low-tercile clean gain +7.1 points against at least 8),
**D2 refuted** (overall clean gain +3.2 against at least 4), D3 held (high tercile +0.4
against at least -2), D4 held (one indel overall +7.8 against at least 0), S1 held (E clean
84.0% against at least 70%), N1 held (R-ngonly low tercile clean 74.2% against at least 65%),
N2 held (R-ngonly clean overall 87.2% against at least 80%). The author's guesses were a
gain of 10 to 15 points in the lowest tercile and 6 to 9 overall on clean draws (too high:
7.1 and 3.2) and 6 to 9 on one indel (7.8, inside).

#### Interpretation (inference)

- R-ngonly's gain over E on clean draws is real in the lowest tercile (p = 0.046) but
  smaller than predicted and confined there: +2.1 and +0.4 points in the middle and
  highest terciles, neither distinguishable from zero. It does not regress where E works (D3).
- On one-indel draws the gain is larger and clearer: +7.8 points overall and +17.1 in the
  lowest tercile (61 draws R-ngonly alone against 20), about 1.5 times as many detections as E
  there. Garbled low-IC messages are where v4's climb (7.5%) and E (37.5%) are weakest, so that
  is where the extra starts matter most. This was not a deciding prediction beyond D4.
- The screen overstated the clean low-IC gain (+11.6 points on true-setting head-window climbs
  against +7.1 here). Plausible reasons, untested: the sweep takes the better of the head and
  tail windows, so each key has two chances and E fails less often; and the E arm's
  low-tercile rate here (67.1%) is well above the 55.6% of phase1-estecker-joint-power-v1, so
  there is less headroom. The second is a plaintext-set effect (this low stratum has a mean IC
  near 0.0558 against 0.054 there) plus sampling; it is a reminder that absolute rates belong to
  a plaintext set.
- Cost: R-ngonly is 1.67 times E on the GPU (about 20 hours against 12 for a full sweep).
  For clean keys that buys +3.2 points overall (+7.1 at low IC); for one-indel keys +7.8
  (+17.1 at low IC).
- By the rule fixed beforehand, D1 refuted means **no v7 sweep is preregistered on this
  basis**. The rule's wording, that the gain "did not appear", is too strong: it appeared
  but fell below the 8-point bar. The rule stands as written.

#### Next decision

Nothing further is preregistered. For the maintainer: stop here, with v6 (E) as the last
standard-reading sweep and R-ngonly's measured gains on record; or accept the one-indel
and low-IC gain as a reason for a v7 sweep, which the preregistered rule does not support and
which would have to be argued and preregistered afresh, with the post hoc origin of that
argument disclosed; or look for a different lever for garbled low-IC messages, where the
gap to the clean case is widest. Companion confirmation and retention for R-ngonly were not
measured (its noise tail is heavier than E's).

#### Amendment (2026-10-15, after review of PR #36, whose two findings apply here)

1. *Pre-observed draws.* The 6-draw smoke run covered draws 0 to 5 of each cell and printed
   their detections and the tercile predictions (`pre_run_facts.smoke_run`), so those 12 draws
   were not unseen when the predictions were committed. The primary result now leaves them out
   (714 draws per cell remain, 234 in the lowest tercile) and `result.all_draws` keeps all 720.
   The harness's own overall predictions (S1, D2, D4, N2) were scored over all 720; the script
   now recomputes them over the primary draws too. **No verdict changes.**
2. *Repeated plaintexts.* Each plaintext supplies 30 draws per cell, so draw-level binomial
   intervals understate the uncertainty about typical text. Every rate and paired gain now also
   carries a bootstrap interval that resamples plaintexts within their IC tercile (the design
   fixes eight per tercile; `stecker_power.stratified_cluster_interval`, 10,000 seeded resamples).

Primary results (714 draws per cell; the all-draws figures in the tables above differ by at most
a point):

| clean | v4's climb | E (v6) | R-ngonly | R-ngonly vs E: only / only, gain (plaintext-cluster interval), McNemar p |
|---|---|---|---|---|
| all | 323 (45.2%) | 603 (84.5%, 81.3 to 87.6) | 626 (87.7%, 84.9 to 90.3) | 70 / 47, +3.2 points (0.4 to 6.3), p = 0.042 |
| low | 48 (20.5%) | 159 (67.9%, 61.4 to 75.3) | 176 (75.2%, 69.9 to 81.5) | 40 / 23, +7.3 points (2.6 to 14.6), p = 0.043 |
| mid | 123 (51.2%) | 219 (91.2%, 86.2 to 95.8) | 224 (93.3%, 89.2 to 96.7) | 18 / 13, +2.1 points (-1.2 to 5.8), p = 0.473 |
| high | 152 (63.3%) | 225 (93.8%, 90.0 to 97.5) | 226 (94.2%, 89.6 to 97.1) | 12 / 11, +0.4 points (-5.0 to 5.0), p = 1.000 |

| one indel | v4's climb | E (v6) | R-ngonly | R-ngonly vs E: only / only, gain (plaintext-cluster interval), McNemar p |
|---|---|---|---|---|
| all | 172 (24.1%) | 445 (62.3%, 57.8 to 67.3) | 502 (70.3%, 66.9 to 73.8) | 134 / 77, +8.0 points (3.5 to 12.6), p = 0.000 |
| low | 17 (7.3%) | 87 (37.2%, 28.9 to 48.5) | 129 (55.1%, 47.0 to 63.7) | 61 / 19, +17.9 points (9.1 to 27.5), p = 0.000 |
| mid | 55 (22.9%) | 163 (67.9%, 61.3 to 75.0) | 175 (72.9%, 67.1 to 78.3) | 43 / 31, +5.0 points (-2.5 to 13.8), p = 0.201 |
| high | 100 (41.7%) | 195 (81.2%, 73.8 to 88.3) | 198 (82.5%, 80.0 to 85.4) | 30 / 27, +1.2 points (-5.0 to 7.1), p = 0.791 |

Predictions on the primary set: D1 refuted (+7.3 points against at least 8), D2 refuted
(+3.2 against 4), D3 held (+0.4 against at least -2), D4 held (+8.0 against at least 0), S1
held (E clean 84.5%), N1 held (R-ngonly low tercile 75.2%), N2 held (87.7%).

What the intervals add (inference): the refutations are by point estimate, as preregistered,
and the plaintext-level intervals straddle both bars. The low-tercile clean gain is +7.3 with a
95% interval of +2.6 to +14.6, which contains D1's 8-point bar; the overall clean gain is +3.2
(+0.4 to +6.3), which contains D2's 4. So the data show R-ngonly's clean gain over E is
positive but do not show it is below the bar; with 8 plaintexts per tercile the size of the
low-IC gain is poorly pinned. The one-indel gain is clearly positive at every level that matters
(overall +8.0, +3.5 to +12.6; lowest tercile +17.9, +9.1 to +27.5). The preregistered rule is
applied as written, so no v7 sweep is preregistered on this basis, but the maintainer's
decision should not read D1 and D2 as showing the gain is small.

## phase1-body-direct-sweep-v7 (preregistered 2026-10-16)

Configuration:
[experiments/phase1-body-direct-sweep-v7/config.json](../experiments/phase1-body-direct-sweep-v7/config.json),
with `scripts/v7_marginal_power.py` (post hoc, run before the configuration was written) and
the post-run checks `scripts/v6_postrun_checks.py --target v7`.

**This run departs from a preregistered rule.** `phase1-rngonly-power-v1` fixed that a v7
sweep would be preregistered only if D1 to D4 all held. D1 and D2 were refuted by their point
estimates (+7.3 and +3.2 points; the plaintext-level intervals contain both bars). The
maintainer decided on 2026-10-16 to run v7 regardless, which the history had listed as an
option that would have to be argued afresh with its post hoc origin disclosed. This is that
preregistration. Its power gate therefore pins the control's artifact but requires only the
predictions that held (S1, D4, N2), and the configuration says so.

The case, computed post hoc from the control's own draws before the configuration existed
(`data/review/v7-prereg-2026-10-16/marginal.json`). v7 follows a null v6, so the relevant
power is conditional on v6 having missed the key. On the 714 primary draws per cell the
R-ngonly arm detects a key the E arm misses in 9.8% of clean draws (70; plaintext-level
interval 7.6 to 12.3) and 18.8% of one-indel draws (134; 15.4 to 22.4): 63.1% of the E arm's
clean misses (54.6 to 71.6) and 49.8% of its one-indel misses (43.3 to 56.4); in the
lowest IC tercile 53.3% and 41.5%. The two climbs fail on largely different keys: the E arm
detects 47 clean and 77 one-indel keys R-ngonly misses, which is why the net gain (+3.2, +8.0
points) understates what a second, different climb adds after the first. These are detection
rates. Companion confirmation and retention were not measured for the R-ngonly arm.

Hypothesis. BYQMZ's key is one v6 missed because its climb was trapped, and the R-ngonly
climb retains a candidate that the companion check (FKQLZ and XFEDT, z >= 6) confirms.

Design. v6's configuration exactly (BYQMZ, middle-complete, W = 117, 246,767,040 settings,
1,560 chunks, retention 100, companion threshold 6, cuda engine) with the first-plug start
set changed from E (two-phase extras) to E, N and R with n-gram-only extras: 73 start boards
per climb. Cost: 0.2931 ms per setting measured on the GPU, 20.1 hours projected (v6: 12.2).

| id | statement | decides |
|---|---|---|
| companion-confirmed-candidate | at least one retained candidate is companion-confirmed | yes |
| confirmed-candidate-is-rank-one | a confirmed candidate is the rank-1 candidate | no |
| v4-retained-settings-do-not-fall | v4's 100 retained settings score at least v4's under the R-ngonly climb (the empty board is the first start and is v4's climb) | no |
| cuda-matches-reference-on-retained | all 100 retained candidates re-climb identically on the CPU batched and reference climbers | no |
| null-top-in-band | if null, the top score lies at z 5.5 to 9.5 (the author expects 8 to 9; v4 6.51, v6 7.50) | no |
| cost-in-band | the recorded time is 18 to 24 hours | no |

Stated power (inference where marked): the conditional detection above, scaled by the E arm's
measured confirmation given detection (98%, not measured for the R-ngonly arm), projects about
62% of clean and 49% of one-indel keys that v6 missed. A null of v7 then leaves about 38% and
51% of the remaining standard-reading mass for those two fault kinds on typical-IC text, and
more for low-IC text. That is not a calibrated odds multiplier: the priors over fault kinds
and plaintext IC are unmeasured, the retention cutoff of a best-of-73 climb is unmeasured
(it will be higher than v6's), and BYQMZ's plaintext IC is unknown. v7 and v6 cover the same
settings and differ only in the climb's start boards, so a null of both says something about
the climbs' blind spots, not about unsearched settings.

Smoke run (scratch, 72 settings, 9 min 46 s): the gate, all seven preflight checks including
`first_plug_climbs_match` (32 of 32 identical) and both positive controls passed; nothing was
changed after it. `scripts/v6_postrun_checks.py` was generalised to `--target v7` and
reproduces v6's committed evidence exactly on its default target.

Run command (from a clean tree on a host with nvcc and the GPU; the GPU was shared with an
unrelated local model server for v6 and may be again, which changes wall-clock time only):

```bash
python3 phase1_stecker.py --config experiments/phase1-body-direct-sweep-v7/config.json --jobs 1
python3 scripts/v6_postrun_checks.py --target v7
```

### Result: phase1-body-direct-sweep-v7 (run 2026-10-16)

Configuration as preregistered above, unchanged. Artifact:
[artifacts/phase1-body-direct-sweep-v7.json](../artifacts/phase1-body-direct-sweep-v7.json),
SHA-256 `9b95bd71...`. Post-run evidence: `data/review/v7-postrun/` (`summary.json`, `checks.log`).

#### Run record

Launched 2026-10-16 02:37:55 UTC from clean `b3ad89f` (the preregistration commit),
`--jobs 1`, cuda engine, one invocation, no resume; completed 22:48:44 UTC (72,649 s in all,
72,030 s of sweep, 20.0 hours). RTX 3090, CUDA 12.8, numpy 2.2.6, Python 3.10.12. The GPU was
shared with an unrelated LM Studio server, which changes wall-clock time and not the result
(the cuda climb is bit-exact). The pinned power gate (control `phase1-rngonly-power-v1`, arm
`complete_w117_rngonly`, required S1, D4, N2) passed before any search and is recorded under
`result.power_prerequisite`, as did all seven preflight checks including
`first_plug_climbs_match` and both positive controls. The checkpoint
(`build/phase1-body-direct-sweep-v7.checkpoint.jsonl`) is git-ignored and disposable; the
artifact is the record.

#### Observed

- All 1,560 chunks, 246,767,040 settings, 100 retained candidates (100 distinct settings).
- **No retained candidate is companion-confirmed**: `confirmed_candidate_ranks` is empty. The best
  minimum companion z over the 100 is 4.63 against the threshold 6; the median is 4.05 and
  ranks 1 to 3 are 4.14, 4.14 and 3.91. None of the 100 has a ring setting compatible with the
  clear indicator.
- Sweep score distribution over all settings: mean -8.0705, sd 0.0669, maximum -7.4784 per
  letter, **top z 8.85**; the 100th retained score is -7.5734. For reference, v4: top z 6.51,
  best companion z 4.69; v5: 6.15, 4.84; v6: 7.50, 4.57.
- Ranks 1 and 2 are the same wheel order (IV II I), rings (AUQ) and plugboard with start positions
  one step apart (JET, KFT) and the same score and companion score: an equivalent pair, as the
  earlier sweeps' retained sets also held.
- 40 of the 100 retained settings are also among v6's 100, at identical scores (v6's rank 1 is
  v7's rank 9). v7's top setting is its own and did not confirm.
- Predictions: the deciding one (a companion-confirmed candidate) was refuted;
  `null-top-in-band` held (z 8.85 in 5.5 to 9.5, and in the 8 to 9 the author expected);
  `cost-in-band` held (20.0 hours in 18 to 24); `confirmed-candidate-is-rank-one` does not
  apply (nothing confirmed); the two checks below held.

#### Post-run checks (`scripts/v6_postrun_checks.py --target v7`, 191 s, 16 workers, from `b3ad89f`)

Before the checks the comparison was shown to flag a wrong plugboard and a lower score. Field
names in the summary that say `v6` refer to the target sweep (here v7).

- `cuda-matches-reference-on-retained`: **held**. All 100 retained candidates re-climbed on the
  CPU with v7's own settings give the cuda record's plugboard, winning window and score, with the
  CPU batched climber (100 of 100) and the pure-Python reference (100 of 100); worst score
  difference 4.8e-10, the artifact's nine-decimal rounding.
- `v4-retained-settings-do-not-fall`: **held**. Re-climbing v4's 100 retained settings with the
  R-ngonly climb gives a score at least v4's on all 100 (98 equal under E; here all 100 equal,
  none rose). Control: v4's own settings reproduce v4's record 100 of 100. Check C (not
  preregistered): no v4 retained setting scores above v7's 100th retained score without being
  among v7's retained rows.
- Informational, not a check: re-climbing v6's 100 retained settings with v7's climb gives 51 equal,
  0 higher and **49 lower**, the largest drop 0.574 per letter.

#### Interpretation (inference)

- The standard-Enigma-I reading of BYQMZ that v6 and v7 could reach, at typical plaintext IC with
  at most the faults the head-and-tail climb tolerates, is not supported: no candidate's wheel
  order, rings and plugboard decipher FKQLZ or XFEDT above noise (best z 4.63, with no candidate
  consistent with the indicator). A top z of 8.85 is what the best of 73 climbs per setting would
  give over noise, higher than v6's 7.50 for the reason the author expected, and is no sign of a
  near miss.
- v7 is not a superset of v6. 49 of v6's 100 retained settings score lower under the R-ngonly climb
  (E's two-phase climbs from its first-plug starts find boards that n-gram-only climbs from the same
  starts do not), matching the control's finding that the two climbs fail on different keys.
  That is why a second sweep added coverage: what the pair covers is the union.
- From the control's draws, the keys neither the E nor the R-ngonly climb detects (detection
  level, 714 draws per cell, plaintext-level intervals): clean 5.7% (4.1 to 7.3) overall, 15.0%
  (9.9 to 19.0) at low IC and 1.2% at mid and high IC; one indel 18.9% (15.6 to 22.3) overall,
  36.8% (28.1 to 45.5) at low IC, 14.2% and 6.2% at mid and high IC
  (`data/review/v7-prereg-2026-10-16/union_miss.json`). With the E arm's measured confirmation
  (98%) the miss rates would be slightly higher. So, for a standard reading with a clean or
  once-garbled message and a typical plaintext, v6 and v7 together would have missed the key
  about 6% or 19% of the time, and much more for a garbled low-IC message (37%). These are
  planted-key detection rates on 24 Markov plaintexts, not a calibrated odds multiplier: the
  priors over fault kinds and plaintext IC are unmeasured, BYQMZ's plaintext IC is unknown,
  R-ngonly's confirmation and retention were not measured, and v2 to v5 are not in the union.
- The decision to run v7 against its control's rule rested on the planted-key finding that the
  two climbs fail on different keys. This run does not test that finding (a null on the real key
  is what the finding predicts whether or not a standard-reading key exists), but the 49 lower
  v6 settings above are independent evidence that the climbs differ. v7 covered keys v6 could
  not, at the measured rate, and did not find one.

#### Not run, and the next decision

Not run: confirmation and retention of the R-ngonly climb on planted keys, two faults, a
substituted letter combined with another fault, other wirings. Nothing further is
preregistered. What a null of v6 and v7 leaves open is unchanged: other wheel wirings (the cited
paper's doubt about Batch C), other reflectors, two faults, other machines, and a message that
is not Enigma output (the publishers say they are not sure these messages are). For the
maintainer: the standard-reading search of BYQMZ is now covered to about 94% (clean) and 81%
(one indel) at typical IC by detection, with low-IC garbled keys the least covered; that and
the open wiring question are the decision. The reply to the 2026-10-10 question to the authors,
if any, is not recorded here.

#### Amendment (2026-10-16, after review of PR #38)

One finding, correct. Limitation 8 of the v7 configuration (index 7), "Companion confirmation for
the E arm has not been measured", is stale. It was inherited from v6's configuration, where it was
true when v6 launched. By the time v7 was preregistered, `phase1-estecker-joint-power-v1`
(run 2026-10-14) had measured it: confirmation given detection for the E arm is 98.1% on clean
draws and 98.6% on one-indel draws, and v7's `refuted_by` and
`stated_power.confirmation_extrapolation` use those measured rates. So the configuration
contradicted itself. The correct reading is that **only the R-ngonly arm's confirmation is
unmeasured**, as the configuration's last-but-two limitation already says. The projected 62% (clean)
and 49% (one-indel) power for keys v6 missed is therefore the R-ngonly arm's measured conditional
detection scaled by the E arm's measured confirmation, an extrapolation to the R-ngonly arm
and labelled as inference.

The configuration itself is left byte-identical: the finished artifact records its SHA-256
(`99e0f801...`, which matches the committed file), and a preregistered configuration is not
rewritten after its run. The amendment is this entry.

## phase1-low-ic-joint-v1 (preregistered 2026-10-20)

Fresh low-IC validation of the already implemented R-ngonly climb against E.
Hypothesis: retained-and-companion-confirmed clean success improves by at least
8 percentage points. Refuted by gain below 0.08. Exact configuration:
`experiments/phase1-low-ic-joint-v1/config.json`; analysis:
`scripts/low_ic_joint_v1.py`. Twelve new IC-selected texts (0.050–0.0575), 240
keys per clean/indel cell, seeds 202610201/202610202/202610203 for text/keys/companions.
No primary-draw smoke outcomes were inspected. Same companion pair for both arms.
Uncertainty intervals cluster by plaintext (12 independent clusters).

Retention uses each completed sweep's observed top-100 cutoff (v6 for E, v7 for
R-ngonly). This tests an observed-cutoff proxy, NOT complete-space retention rank
for every planted text. Results cannot claim the latter. No message sweep starts
from this experiment. Background and continuation: docs/runs/2026-10-20-low-ic-joint.md.

### Result: phase1-low-ic-joint-v1 (2026-10-21)

#### Observed

Raw artifacts: `artifacts/phase1-low-ic-joint-v1.json` and
`artifacts/phase1-low-ic-joint-v1-joint.json`. Power run: clean `19b220f`,
2310.9 seconds, all preflight checks and positive controls passed. Analysis:
`c324e4e`, 198.3 seconds; tracked code clean, dirty flag records only the newly
created untracked raw power artifact. An arm-name adapter bug was found on
synthetic data and fixed before any calibration outcomes were read; hypotheses,
seeds, draws and thresholds were unchanged. Machine: RTX 3090 and shared CPU;
eight power workers and eight analysis workers. All 34 GPU-enabled first-plug
parity tests passed; CPU suites passed 47 tests, six GPU-dependent skips.
Analysis adapter regression test passed. Logs: data/review/low-ic-joint-2026-10-21/.

All 240 draws per cell and 12 fresh low-IC texts were retained, no smoke exclusions.
Clean retained-and-confirmed success: E 165/240 (68.75%), R-ngonly 183/240
(76.25%). Plaintext-cluster 95% intervals: E [61.25%,76.67%], R [70.42%,81.67%].
One-indel success: E 95/240 (39.58%), R 125/240 (52.08%); cluster intervals
[31.25%,47.92%] and [46.67%,57.50%]. Clean gain 7.5 percentage points, indel
gain 12.5 points. **The preregistered clean gain >=8 points is refuted.**
R confirmation given detection: clean 184/186 (98.92%), indel 128/132 (96.97%).
R retention given detection: clean 185/186 (99.46%), indel 129/132 (97.73%).

#### Interpretation (inference)

R-ngonly improves the observed low-IC success rate in this sample, but the improvement
falls short of the fixed clean-gain decision bar. Individual intervals are
plaintext-cluster intervals, not evidence that the gain itself is significant.
This does not establish a new optimum among all screened methods: more expensive
capped-IC variants had higher screening recovery at higher cost. The already
implemented R-ngonly method remains the cost-oriented comparison chosen in prior
work; no duplicate implementation was needed.

Retention is measured against each completed sweep's fixed observed top-100 cutoff.
It is NOT a fresh full-space rank experiment on each planted message. Synthetic
Markov texts from scorer counts, 12 text clusters, a planted neighbourhood and
fault-free synthetic companions limit generalisation. No combined odds multiplier
is inferred. Under the preregistered rule this result does not justify another
message sweep. No new target sweep is launched or preregistered.

#### Maintainer decision, 2026-10-21

The maintainer accepts the measured 7.5-point gain as sufficient to proceed,
overriding the operational >=8-point launch rule. The preregistered hypothesis
remains refuted; its threshold and artifacts are unchanged. Before launching the
next search, verified that v7 already ran this exact R-ngonly method over BYQMZ's
complete declared space (246,767,040 settings, completed 2026-10-16, no confirmed
candidate). This fresh calibration supplies evidence for the already completed
v7; it does not create an unsearched slice. No duplicate run is launched.

#### Companion-free reading (2026-10-23, post-hoc analysis)

**Why.** The preregistered success measure, `sweep_success`, needs the planted
BYQMZ key to be retained *and* confirmed by the FKQLZ and XFEDT companions at
z ≥ 6. The planted companions are Enigma ciphertexts by construction.
`phase5-jless-flat-v1` (branch `claude/phase5-jless-flat-v1`, a disclosed
post-hoc test) finds the real FKQLZ and XFEDT J-less and flatter than Enigma
output, at joint p 0.000005 and 0.000015. If they are not Enigma, no real key
could ever be companion-confirmed. The question is whether this calibration,
and v7's null, still hold without the companions.

**Method.** `scripts/low_ic_joint_companion_free.py` reads the committed
joint artifact and the v7 artifact and reruns nothing. The result is
`artifacts/phase1-low-ic-joint-v1-companion-free.json`, generated from clean
`886c8c7`. It reports two companion-free measures per draw and arm:

- **`companion_free_success`:** detected and retained. This is the
  preregistered measure with the confirmation step removed.
- **`stands_out`:** the exact plugboard is recovered and the key's score lies
  above the ceiling of v7's preregistered noise band, z 9.5 over v7's score
  distribution (prediction `null-top-in-band`, about −7.435 per letter). This
  is the criterion that also applies to the real sweep, where the plugboard
  cannot be checked. The planted texts are scored against v7's BYQMZ
  distribution, which is an approximation: same length, different
  ciphertexts.

The detection threshold used on planted draws (about −7.76 per letter) comes
from a local null at the true setting. Every one of v7's 100 retained noise
candidates clears it, so it cannot serve as a companion-free decision rule
for the real sweep. That is why the band ceiling is used.

**Observed** (240 draws per cell; plain binomial Wilson 95% intervals, which
are narrower than the plaintext-cluster intervals above):

| Cell | Arm | Preregistered (with companions) | Companion-free: detected and retained | Companion-free: stands out above band |
|---|---|---|---|---|
| Clean | E | 165 (68.8%) | 166 (69.2%, 63.1–74.7) | 166 (69.2%) |
| Clean | R-ngonly | 183 (76.3%) | 185 (77.1%, 71.4–82.0) | 185 (77.1%) |
| One indel | E | 95 (39.6%) | 96 (40.0%, 34.0–46.3) | 93 (38.8%) |
| One indel | R-ngonly | 125 (52.1%) | 129 (53.8%, 47.4–60.0) | 128 (53.3%) |

- **Companion-free paired gain:** 7.9 points clean (47 draws R-ngonly only, 28
  E only) and 13.8 points with one indel (61 against 28). The clean gain
  remains below the preregistered 8-point bar, so the refutation and the
  maintainer's decision are unchanged.
- **How far a recovered key stands out:** a key with its exact plugboard
  recovered scores a median z of about 22 against v7's BYQMZ distribution,
  far above the band ceiling of 9.5.
- **v7 without companions:** its top retained candidate has z 8.85, inside
  the band, and **none of its 100 retained candidates lies above the
  ceiling**.

**Inference.**
- Companion confirmation removed only 1 to 4 of 240 draws per arm. These
  power figures are therefore limited by detection, not by the companions, so
  they stand whether or not FKQLZ and XFEDT are Enigma.
- v7's null also stands without the companions. A recovered true key would
  have stood out on BYQMZ's own letters, at about z 22 against a band ceiling
  of 9.5, in about 77% of clean and 53% of one-indel low-IC draws. Nothing in
  v7 did.
- What the companions' possible non-Enigma status removes is the *acceptance*
  step. A future hit could not be confirmed through FKQLZ or XFEDT, and would
  need another check, such as the indicator or a crib.
- The approximation, scoring planted texts against v7's distribution, is the
  main limitation of this reading.
