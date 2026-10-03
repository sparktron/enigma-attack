# Code review: process and implementation of the attack plan

Reviewed 2026-10-02 at commit `947ac21`. This review changes documentation
only; nothing below is fixed yet. It follows the
[2026-09-22 audit](code-review-2026-09-22.md), whose nine findings have fixes on
`master`, and concentrates on what has changed since: the Phase 1 stecker
attack (`phase1_stecker.py`, `enigma_fast.py`), its three experiments, and the
next step `STATUS.md` recommends.

The measurements quoted here were run during the review to test specific
claims. They were **not preregistered** and are not experiment artifacts. Each
one is described well enough to repeat, and any that is used to change the plan
should be rerun as a proper experiment.

## Verdict

The engineering discipline is good: preflight parity checks, known-key gates
that block target searches, preregistered hypotheses, and honest negative
results. The reference simulator, the fast kernel and the fast scorer agree with
each other, and the test suite passes (125 tests, 22 s). The Phase 5
conservation argument against transposing QTXMA is sound.

The weak point is the step between "the climb recovers a key it is handed" and
"the sweep will find the key." Every Phase 1 calibration and control hands the
climb the exact true ring setting and start. The sweep never visits that
setting. It visits an equivalent setting under held rings, and the review
measured that this equivalent often decrypts the message differently. As a
result the Phase 1 numbers overstate what a full sweep would detect. The coverage
denominator is also wrong, and the recommended next step depends on cribs that
nothing in this repository supports. Each of these can be fixed, and the
efficiency fix makes the main alternative affordable.

## 1. Process findings

### P1 — High: calibration certifies a setting the sweep cannot visit

- **Where:** `phase1_stecker.py:1063` (`calibrate_climb_capability`),
  `phase1_stecker.py:1358` (`evaluate_positive_control`),
  `tests/test_phase1_stecker.py:399` (planted key with rings `AAA`).
- **What:** Every measurement behind "8/8 exact at 167 letters" climbs at the
  true `(rings, start)`. The sweep holds rings fixed (`AAA` in the declared
  slice) and searches the start position. The equivalent setting it can reach
  has the same wheel offsets, but its right-wheel turnover and middle-wheel notch
  fall at different points in the message. After such a point the decryption
  diverges from the true one. The planted-key test uses rings `AAA`, so it
  cannot see this.
- **Measured** (167 letters, 10 pairs, random daily keys, best of the reachable
  neighbouring settings):

  | parameterization the sweep uses | exact equivalent exists | plugboard recovered |
  |---|---:|---:|
  | climb handed the true key (what the calibration measures) | — | 30/32 |
  | rings `AAA`, 60 × 26³ settings | 0/32 | 4/32 |
  | right ring searched, left and middle rings held at A, 60 × 26⁴ (the artifact's "reducible space") | 25/48 | 33/48 |
  | same size, middle ring chosen per offset (see P2) | 33/48 | 36/48 |

  When a reachable setting is only 50–80% equivalent, the climb usually fails
  outright. It does not degrade gracefully.
- **Why it matters:** At the target scale, a complete 60 × 26⁴ sweep would find
  a true BYQMZ key about 69% of the time, not "every draw." A null over the
  full space would be weaker evidence than the history implies. A future hit
  would also have to come from the equivalent setting, which no control
  exercises.
- **Fix:** Add an **end-to-end** control. Plant random keys with random rings,
  run the actual sweep machinery over a small slice that contains the reachable
  equivalent and its neighbours, and report the detection rate. Use that rate
  as the stated power of every sweep.

### P2 — High: the coverage denominator is mis-specified

- **Where:** `phase1_stecker.py:1812–1819`; repeated in `STATUS.md` and
  `docs/phase1-experiment-history.md`.
- **What:** The artifact says the 60 × 26⁴ space "assumes the left wheel does
  not step during the message, which holds for about three quarters of start
  positions." That accounts only for the true key's left-wheel step. Holding
  the middle ring at A gives the swept setting a left-wheel step of its own,
  independently, about 27% of the time. Both must be absent, so 0.73² ≈ 0.53.
  The review measured 25 of 48.
- **Free improvement:** For each wheel order and middle offset, choose the held
  middle ring so that the swept middle wheel starts just past its notch. It then
  cannot step the left wheel within 167 letters. The space stays the same size,
  and exact coverage rises from 25/48 to 33/48 (recovery from 33/48 to 36/48).
  To cover keys whose true left wheel does step, add the few middle phases that
  put the notch inside the message, and declare the extra cost.
- **Related:** `run_body_direct_sweep` takes a single `rings` string
  (`phase1_stecker.py:1711`), so the right-ring axis in the denominator cannot
  be expressed in one run. The 3,472 core-hour projection describes 26 separate
  runs that the code cannot schedule.

### P3 — High: the recommended next step rests on cribs with no evidence

- **Where:** `STATUS.md` "Next"; `docs/phase1-experiment-history.md` "What Phase 1
  now needs"; `cribs.json`; `artifacts/phase2-network-cribs.json`.
- **What:** The plan names a crib-driven Bombe as the highest-value move and
  says the Phase 2 crib network "exists to feed it." In `cribs.json`,
  `evidence_level: fact` means the phrase is attested in *other* traffic (1930
  and 1938 test messages, related 1941 traffic). Nothing indicates that any of
  them occurs in BYQMZ, FKQLZ or XFEDT. No-self-encipherment leaves about 70–80
  valid placements per crib per message (`valid_offset_count`). That makes
  roughly 1,000 crib-and-placement hypotheses per message, each with a low
  prior, before rotor enumeration starts.
- **Why it matters:** A Bombe is fast per setting, but it needs a correct crib
  at a correct position. Bletchley had routine, high-confidence cribs. Here the
  weakest input would decide the result, and a null from it would say little.
- **Fix:** Before building a Bombe, estimate the probability that the best
  cribs actually appear (for example, how often routine openings and sign-offs
  occur in solved 1941 traffic from this network). Compare that with the cost
  of a full body-direct sweep, which is crib-free, has deterministic coverage,
  and has measurable power (P1). R1 and R2 below bring that sweep to about a
  day on 18 cores.

### P4 — Medium: a long-running artifact is stale, and the docs cite its stale part

- **Where:** `artifacts/phase1-body-direct-sweep-v1.json`;
  `artifact_claims.json` (`long_running`); `phase1_stecker.py:1955`.
- **What:** The artifact records `phase1_stecker.py` sha256 `f608bc6e…`. The
  current file is `9c76e4ec…`. It was produced before 9c6bfb7 ("Recover the
  ring setting before the indicator confirmation") and has no
  `compatible_ring_settings` field. Its indicator confirmation therefore used the
  held rings, which that commit says "could have dismissed a genuine hit." The
  history still cites its confirmation scores (best −9.316, mean −9.550) as
  independent evidence. The slice's null conclusion still holds on the sweep
  scores alone: max −8.14 against about −6.6 to −7.7 for a real hit.
- **Provenance gap:** `git_commit` records `ffa9fdb`, a commit from before the
  stecker module existed. The run came from an uncommitted tree, and
  `git rev-parse HEAD` does not record that. `code_sha256` saved the record
  here.
- **Fix:** Record a dirty-tree flag (`git status --porcelain`) in every artifact.
  Re-run the confirmation stage on the retained top 40, which is cheap, or mark
  the field as superseded. Have `check_artifacts.py` compare a long-running
  artifact's recorded code hashes with the current files and warn on mismatch,
  instead of checking only that the file exists.

### P5 — Medium: the IC-stage calibration contradicts its own artifact and uses the wrong threshold

- **Where:** `phase1_stecker.py:938` (`calibrate_ic_stage`);
  `artifacts/phase1-stecker-calibration-v1.json`.
- **What:** The history says the ten-pair column "never separates." The
  artifact's `usable_cells` includes `{length: 97, stecker_pairs: 10}`
  (z = +3.30 ≥ `usable_z` 3.0). The ten-pair z values (3.3, 1.1, 0.5, 2.5)
  are not monotone in length, because each cell is one key draw. More
  importantly, z ≥ 3 is the wrong test for a statistic used to rank 2.1 million
  keys. What matters is the true key's rank against that many wrong ones, which
  needs z ≈ 5 or more for a top-k retention to work.
- **Conclusion still right:** the analytic argument (about 5% of letters survive
  two plugboard passes) supports "IC is unusable at ten pairs." The fix is to
  average over many draws and report expected rank against the sweep size.

### P6 — Medium (risk): a single dropped or inserted letter is not calibrated

The body-direct climb needs nearly all of the message aligned. The P1
measurements show it usually fails below about 80% equivalence. Intercepted
traffic often has garbles, and BYQMZ already carries a `?`. A substitution is
local, but one dropped or inserted letter misaligns everything after it, which
would hide a true key even under full coverage. Add one calibration cell with a
single indel at a random position. If it fails, plan for windowed climbs (first
and last ~120 letters) on BYQMZ.

## 2. Implementation findings

### I1 — High: the installed `enigma-phase1-stecker` cannot run

- **Where:** `phase1_stecker.py:63–64, 78–80, 2002`.
- **Reproduction:** Build and install the wheel in a clean venv, then run
  `enigma-phase1-stecker` from another directory. It raises `FileNotFoundError`
  for `…/site-packages/experiments/phase1-stecker-calibration-v1/config.json`.
  `resolve_path('corpus.json')` also points into `site-packages`.
- **Why:** This module uses `ROOT = Path(__file__).parent` instead of
  `resources.resource_root()` and `resources.resolve_output()`, which every
  other phase uses. That breaks the `STATUS.md` statement that installed
  commands read from the share directory. A relative `--output` would also
  write into `site-packages`. `tests/test_wheel_install.py` exercises only
  `enigma-phase7` and the resource helpers.
- **Fix:** Route inputs through `resource_root()` and outputs through
  `resolve_output()`. Add an installed smoke test that runs this command with a
  tiny config.

### I2 — High before any full sweep: the sweep engine does not scale

`body_direct_sweep` (`phase1_stecker.py:852`) has three problems that are
harmless for the 40,560-setting slice and fatal for 2.7 × 10⁷ settings:

- `collected` keeps a dict and a 26-entry plugboard for **every** setting:
  an estimated 15 GB at full scale. The earlier audit's R3 (use a bounded top-k)
  applies again.
- There is one chunk per wheel order, so 60 chunks for 18 workers. The last
  round keeps only 6 workers busy (about 83% efficiency), and the 3- to 8-day
  run has no checkpoint or resume. One crash loses everything.
- The right ring cannot be swept (P2).

### I3 — Low

- `climb_stecker` (`phase1_stecker.py:505`) evaluates each existing pair's
  unplug move twice, once from each letter (about 3% wasted evaluations).
- `body_direct_climb.coincidence` weights by `len(body)`, which includes masked
  positions, but divides by unmasked `letters`. The effect is tiny; use the same
  count in both places.
- `__pycache__/enigma.cpython-313.pyc` is tracked despite `.gitignore`.
- `check_artifacts.py:140` re-checks existence inside the superseded branch,
  which was already checked a few lines earlier. That branch is dead code.
- Helpers are duplicated across modules: `_sha256` appears in seven of them,
  git-provenance helpers in three, `load_config` in three, and
  `index_of_coincidence` in two.

## 3. Proposed refactors

### R1 — Batch-evaluate the climb's moves (efficiency, measured)

Each pass of `climb_stecker` scores about 350 candidate plugboards one at a time
in pure Python. A numpy version builds every candidate of a pass as one
`(K, 26)` array and decrypts and scores them all at once through the
precomputed `(n, 26)` position table. It keeps the same move set, order,
pair limit, minimum-gain rule and first-best tie-break. Prototype, 40
settings (half true, half wrong, a third with a `?` mask), single thread:

| | ms per converged two-phase climb | identical final plugboard |
|---|---:|---:|
| `phase1_stecker.body_direct_climb` | 141 | — |
| batched numpy climb | 16 | 40/40 |

That is about **8.7×**, which brings the projected 3,472 core-hours down to
roughly 400 (about 22 hours on 18 cores) with no change to the algorithm.
Batching several start positions per call should add more; a small C kernel
would add more again. Keep the pure-Python climb as the reference, and add
"batched climb matches reference climb" to `run_preflight`, the same pattern
the kernel and the scorer already follow. This adds numpy as the project's
first runtime dependency. Making it optional, with a pure-Python fallback, keeps
the stdlib-only install working.

### R2 — Rebuild the sweep engine before scaling

- Each worker keeps a bounded top-k heap plus streaming score statistics
  (count, mean, M2, max), and these are merged at the end.
- Chunk by wheel order × middle start (60 × 26 = 1,560 chunks). Write each
  finished chunk's top-k and statistics to a JSONL checkpoint, and resume by
  skipping chunks that are already recorded. Keep the existing order-independent
  merge.
- Make the right ring and the middle-ring rule (P2) explicit axes of the
  declared space, so coverage is computed from what actually ran.

### R3 — Use end-to-end power as the headline number (P1, P6)

Replace `calibrate_climb_capability`'s "hand it the true key" with "plant a key
with random rings (optionally with one garble or indel), sweep a slice that
contains its reachable equivalent and neighbours, and record the planted key's
rank." Keep the current measurement too, labelled as the stecker stage's
**upper bound**.

### R4 — Confirm through the companion messages' bodies, not only their indicators

The current confirmation derives FKQLZ's and XFEDT's keys through the
indicator, which only works with an exactly right plugboard and ring setting.
That is the same discontinuity finding (d) documented. For each retained
candidate, also decrypt each companion message at all 17,576 starts with the
candidate's plugboard and record the best score against its own null. A
mostly-right plugboard still lifts a companion message clear of noise. With R1
this takes seconds per candidate.

### R5 — Split `phase1_stecker.py` and share provenance (clarity)

At 2,010 lines the module mixes scoring, climbing, two sweeps, four
calibrations, confirmation and the runner. Proposed layout:

- `stecker_climb.py`: `FastNgramScorer`, objectives, `climb_stecker`, and the
  batched variant.
- `phase1_sweeps.py`: the indicator and body-direct sweeps, and the engine from
  R2.
- `phase1_calibration.py`: the calibrations and controls.
- `phase1_stecker.py`: the runner only, so the entry point stays the same.
- `provenance.py`, used by every phase: file and text hashes, a git commit
  **with a dirty flag**, the environment record, the standard result envelope,
  and path resolution through `resources`. This fixes I1 and P4's provenance gap
  together and removes the duplicated helpers in I3.

## 4. Recommended order

1. I1 and the provenance dirty flag: small and independent.
2. R3 with the P2 parameterization: measure end-to-end power before spending
   compute, and correct the coverage statements in `STATUS.md` and the
   history.
3. R1 and R2: make a full BYQMZ sweep (60 × 26⁴, about 22 hours on 18 cores at
   the measured speed-up) affordable, checkpointed and correctly declared.
4. Run that sweep as a preregistered experiment, with R4 confirmation and the
   power from step 2 stated in advance.
5. Reconsider the Bombe only with a quantified crib prior (P3), or if step 4 is
   null at known power.

## Appendix: how the review measurements were made

Both measurements can be rerun with the scripts in
[`scripts/review/`](../scripts/review/README.md): `reachable_settings.py`
(P1 and P2, one `--mode` per table row) and `batched_climb.py` (R1). Run
times vary by host; the parity and recovery counts should not.

All of these use the calibration config's plaintext, `EnigmaI` encryption, 10
random stecker pairs, and `phase1_stecker.body_direct_climb` with the
configured two-phase climb.

- **Reachable equivalence:** for each random key, build the candidate swept
  settings (held rings, wheel offsets equal to the true ones, left offset ±1,
  middle offset ±1 or ±2). Compare
  `enigma_fast.position_permutations` position by position with the true key's
  table to get the equivalent fraction. Climb the three most equivalent
  candidates and keep the best by score.
- **Batched climb:** apply the same move generation as `climb_stecker`, using
  `numpy.triu_indices` for pair order and `np.argmax` for the first-best
  tie-break. IC is pooled with the same weight as `body_direct_climb`. Final
  plugboards were compared exactly. Timing used one thread
  (`OMP_NUM_THREADS=1`) on the review host.
