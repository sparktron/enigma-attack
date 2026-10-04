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

Second, and cheaply: XFEDT at 97 letters is below the recovery threshold on its
own (1 of 8 draws) and should not be attacked alone. FKQLZ at 107 letters was
not measured directly and sits between the 97-letter and 167-letter cells.
