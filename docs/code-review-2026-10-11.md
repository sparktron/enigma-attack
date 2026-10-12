# Code review: the code-breaking process, end to end

Reviewed 2026-10-11 at commit `fc33524` (master after #31). This review changes
documentation and adds measurement scripts only; nothing under the attack code or
the artifacts is modified. It follows the [2026-09-22 audit](code-review-2026-09-22.md)
and the [2026-10-02 review](code-review-2026-10-02.md), and asks a different
question: **does the process work as expected, and do the numbers it reports mean
what the closure of the BYQMZ search says they mean?**

The measurements below were run during the review. They are **not preregistered**
and are not experiment artifacts. Each is reproducible with the scripts in
[`scripts/review/`](../scripts/review/README.md), and any that is used to change
the plan should be rerun as a proper experiment. What is measured is marked as
such; what is inferred is marked as inference.

## Verdict

The machinery is correct. The simulator, the fast kernel, the table path, the
sweep-space generator, the climb, the scorer and the sweep merge all check out,
independently where that was possible (section 1). I found no defect in the
search code I read (the scope is in section 5).

The finding that matters is in the *measurement*, not the machine. Every
end-to-end power figure in the repository is measured on **one** plaintext, and
that plaintext is an outlier: its index of coincidence is 0.0792, against about
0.061 for German Army traffic. The climb's success varies with the
planted plaintext. The corrected v5 rerun detects **41.9%** across four
model-generated texts, versus **97.5%** on the repository plaintext. This raises
a concern about extending the closure's power figures to other plaintexts; the
confirmed four-arm power on typical plaintexts remains unmeasured (B-1). The published method has a standard remedy that the
repository does not implement, partial exhaustion of the first plug, and
a proof of concept recovers most of the loss (S-1).

## 1. What was checked and works

| id | claim | how it was checked | result |
|---|---|---|---|
| V-1 | `enigma.py`, `enigma_fast.py` and the table path simulate Enigma I correctly | An Enigma written independently from the published description ([`independent_enigma.py`](../scripts/review/independent_enigma.py)): two published vectors (AAAAA → BDZGO, and EWTYX with rings BBB), the textbook double-step sequence (KDO → KDP → KDQ → KER → LFS), and 3,000 random keys of up to 700 letters (notch crossings and double steps) | 3,000 of 3,000 agree across all four implementations. Rotor, reflector B and notch tables match the published wirings |
| V-2 | The `middle_complete` sweep space contains an exact equivalent of every key; the past-notch figures are right | For random true keys, build the settings `RingRule.settings` generates and compare per-letter wheel-offset trajectories, computed by the independent code | complete: 1.000 at 97, 107 and 167 letters (600 keys each). Past-notch: 0.818, 0.798, 0.722 against the repository's 0.820, 0.805, 0.716 (sampling error about ±0.02) |
| V-3 | The suite passes | `python3 -m unittest discover -q` | 272 tests, 138 s, OK (STATUS says 263, see B-4) |
| V-4 | The climb, scorer, sweep and procedure are implemented as documented | Read in full: `climb_stecker` (move set, pair limit, best-improvement tie-break), `FastNgramScorer` (the trigram cursor arithmetic gives n−1 bigram and n−2 trigram terms), `_worker_chunk` (top-k heap, Chan merge, deterministic tie-break), checkpoint fingerprinting, `decrypt_with_army_procedure` | No defect found |
| V-5 | The corpus matches the publisher | CryptoCellar's challenge page lists 160, 56, 172, 112, 102 characters including the 5-letter discriminator; the repository's 155, 51, 167, 107, 97 are those minus 5 | Consistent |

## 2. Bug report

### B-1 — High: power is measured on one atypical plaintext, and it decides the closure

- **Where:** `stecker_power.py:_power_draw` (`settings["plaintext"]`); every
  `end_to_end_power` configuration; the closure record in
  [phase1-experiment-history.md](phase1-experiment-history.md#closing-the-standard-reading-search-of-byqmz-2026-10-10).
- **What:** All 80 to 400 planted draws in each power control encipher the same
  167-letter constructed text. The 95% intervals therefore reflect key draws only.
  That text has IC **0.0792**. The repository's own published 1941 counts give a
  pooled Army IC of 0.0593; the cited paper puts the mean at 6.1% and notes that
  the plaintext's IC decides whether a short message breaks easily or is "nearly
  unbreakable"; the five authentic control plaintexts (36 to 76 letters, IC 0.049
  to 0.083) average 0.061 weighted by length. A 167-letter
  message drawn from the pooled counts reaches IC 0.0792 about 0.25% of the time.
  The climb's first phase is an index-of-coincidence climb, so its success should
  depend on exactly this.
- **Measured.** The same keys (seed 424242; 95 of 120 draws have an exact
  equivalent in the slice, for every plaintext), through the repository's own
  harness and detection rule (planted plugboard recovered exactly and the score at
  the null threshold). Rate is detection given an exact equivalent in the slice:

  | plaintext (167 letters) | IC | whole-message arm |
  |---|---:|---:|
  | repository's | 0.0792 | 0.947 (90/95) |
  | hand-written, Q-code traffic | 0.0779 | 0.916 |
  | hand-written, telegraphic | 0.0771 | 0.811 |
  | hand-written, number-heavy | 0.0647 | 0.568 |
  | hand-written, rare letters and place names | 0.0587 | 0.284 (27/95) |

  Then 16 plaintexts drawn from the repository's own trigram counts, which are
  typical of the scorer's training data by construction, 60 draws each:
  IC 0.0514 to 0.0625 (mean 0.0574), detection 0.11 to 0.62, **pooled 0.358
  (269/752)**, Pearson r between IC and detection **0.87**, about +4.7 points per
  +0.001 of IC.

  The corrected v5 rerun (2026-10-12, split-point climb, complete rule, CUDA,
  40 draws per text) uses the selected arm's own null threshold. It supersedes
  the earlier v5 table, which used the pooled threshold. The exact command,
  configs, raw outputs, environment, code version and checksums are preserved in
  [data/review/plaintext-power-2026-10-12/](../data/review/plaintext-power-2026-10-12/).

  | plaintext | IC | detection given an equivalent |
  |---|---:|---:|
  | repository | 0.0792 | 39/40 (97.5%) |
  | markov-0 | 0.0578 | 8/40 (20.0%) |
  | markov-1 | 0.0574 | 22/40 (55.0%) |
  | markov-2 | 0.0600 | 15/40 (37.5%) |
  | markov-3 | 0.0625 | 22/40 (55.0%) |

  Across the four Markov texts: **67/160 (41.9%)**, mean IC 0.0594,
  Pearson r 0.39 and slope +2.8 percentage points per +0.001 IC. The same
  key draws were reused across texts; these are not 160 independent key draws.
  With four texts, the correlation does not isolate IC from other text properties.
  The old 0.35 to 0.42 integrated curve is withdrawn: it was not recomputed.
- **Why it matters (inference):** The repository plaintext is substantially easier
  for this arm than these four model-generated texts. This supports measuring
  power across plaintexts, but does not estimate power for authentic Army traffic.
  The original closure figures remain conditional on their planted plaintext.
  This rerun measures neither companion confirmation nor the four-arm union, so
  the old typical-IC multipliers (about 0.6 and 0.5 to 0.65) are withdrawn rather
  than replaced by a detection-only estimate. BYQMZ's plaintext IC is unknown.
- **Fix:** Make every power control plaintext-aware (S-2). Until then, restate the
  closure as conditional on plaintext IC, and do not describe the standard-reading
  search as exhausted for typical messages.

### B-2 — Medium: the climb fails by trapping, so no cheap second stage can rescue it

- **Where:** `stecker_climb.climb_stecker` (single deterministic start from the empty plugboard).
- **Measured** (baseline climb at the *true* setting, z against that text's own
  wrong-setting null, 54 draws): at IC 0.0625 the true setting reaches z ≥ 6 in 57%
  of draws and the rest are noise; at IC 0.0578 median z is **1.7** and at IC 0.0514
  it is **0.5**. The outcome is bimodal. A failed climb scores like a wrong setting.
- **Why it matters:** A scheme that reclimbs only the top slice of baseline scores
  cannot recover these keys, because they are not in it. Any remedy has to change
  how the climb starts, on every setting. This is the cost driver for S-1.

### B-3 — Low: README says "every trial"; STATUS says 28 of 32

- **Where:** README.md, "Phase 1 stecker calibration and sweeps" ("recovers a
  known ten-pair plugboard and its exact plaintext on every trial at 167 letters")
  against STATUS ("28 of 32 trials (87.5%)"); the 28/32 figure is itself measured
  at the repository's IC-0.079 plaintext (B-1).
- **Fix:** Use the STATUS wording, and add the plaintext caveat.

### B-4 — Low: stale or contradicted documentation

- STATUS reports 263 passing tests; the suite has 272.
- `__pycache__/enigma.cpython-313.pyc` is still tracked although `.gitignore`
  lists `__pycache__/` (finding I3 of the 2026-10-02 review, never fixed).
  `git rm --cached __pycache__/enigma.cpython-313.pyc`.

### B-5 — Informational: new source facts the repository does not record

All from CryptoCellar pages fetched 2026-10-11; treat as dated external claims.

- The unbroken-message page (updated 30 Sep 2026) lists BYQMZ, FKQLZ and XFEDT
  with the note that the publishers are "not quite sure if these messages are
  Enigma messages or if they are messages enciphered with another machine or
  system". Neither it nor the 19 Sep status list contains QTXMA or SZAEJ, which
  the challenge page (27 Jul 2026) still presents as part of the set. This does not
  say why they left, but it extends the repository's "omitted from the 16 Sep list"
  to the 19, 22 and 30 Sep pages.
- The challenge page raises "a police network run by operators from the German
  Ordnungspolizei" as one reading of the odd operator names and remarks. STATUS
  records the unfamiliar operators but not this hypothesis.
- The publishers' stated reason for messages that never broke is "a combination of
  non-favorable plain text, problematic Stecker connections and, for some of them,
  too short messages". That is B-1 in the authors' own words.

## 3. Suggested changes

### S-1 — Add partial plugboard exhaustion to the climb (highest value)

The Ostwald–Weierud paper's answer to a failed IC phase is to start the climb
from every board with one plug on a frequent letter (E-Stecker: E with each of
the 25 other letters plus E self-steckered, 26 starts; R-Stecker: E, N, R, 73
starts; I-Stecker adds X, S, I, 136), keep the best, and not to trust the empty
board. The repository's climb has one start. A proof of concept, patched in
without touching the repository ([`estecker_direct.py`](../scripts/review/estecker_direct.py)),
climbing at the true setting with each method calibrated against its own null:

| text IC | baseline | E (26 starts) | R (73 starts) |
|---|---:|---:|---:|
| 0.0578 | 5/24 | 19/24 | — |
| 0.0514 | 3/36 | 14/36 | 27/36 |

Through the repository's own end-to-end harness (whole-message arm), the 0.0587
text went from 27/95 detected given an equivalent (120 draws) to 34/47 (the first
60 draws, with E-Stecker starts patched in). The null mean rises
(−8.67 to −8.51) and its spread falls, so the gain is not a threshold artifact.

I also tried the cheap alternative the paper's discussion suggests: replacing or
adding a unigram log-likelihood against the Army histogram in the first phase. It
does little (IC 0.0578: 13/36 baseline, 14/36 and 16/36 with the unigram phase;
IC 0.0514: 3/36, 3/36 and 4/36). First-plug exhaustion is the lever.

- **Cost.** The climb count scales with the number of starts. By the recorded
  timings that is roughly 13 GPU hours for a v4-sized whole-message complete-rule
  sweep with E-starts and about 50 for v5's split-point climb (inference from
  v4's 0.51 h and v5's 1.93 h; the CUDA kernels start from the identity board and
  need an initial-board input, which I have not written). Because of B-2, the
  starts cannot be applied selectively.
- **Order of work.** Do S-2 first so the gain is measured on a plaintext
  distribution, preregister the comparison, then decide whether the closed search
  is worth reopening. The maintainer closed it on a power figure that B-1 revises,
  so the decision is worth revisiting. It is the maintainer's to make.

### S-2 — Make power plaintext-aware

Let a power configuration take a list of plaintexts (or a generator seed), draw
one per key, and report power overall and by plaintext-IC tercile. Keep the
current single-plaintext figure, labelled as the favourable case. Use authentic
held-out Army plaintexts where lengths allow and model-typical samples
([`plaintext_power.py`](../scripts/review/plaintext_power.py) draws them from the
published counts) otherwise. Rerun the four climbs' joint power on the result and
restate the closure's multiplier from it.

### S-3 — Randomised restarts as a complement

Lasry's shotgun hill-climbing and simulated annealing are the usual alternatives
to a deterministic climb that gets trapped. A fixed budget of random restarts per
setting is the unstructured counterpart of S-1. I have not tested it. It is worth
a single comparison against E-Stecker at equal cost, because structured starts are
tied to the plaintext's letter frequencies and may be less robust on odd traffic.

### S-4 — Smaller items

- Fix B-3 and B-4 (a documentation commit).
- Record B-5 in STATUS, with the dates.
- Optional: the paper notes that wheels are never reused in the same position on
  adjacent days and that known adjacent-day keys cut the order space from 60 to
  about 24 to 32. That helps only if Batch C follows Army key rules, which the
  cited paper doubts, so it is a cost saver and not a priority.

## 4. What others do, and what the repository is missing

Sources are listed at the end; claims about those works are from the pages and the
paper's text as read on 2026-10-11, not from the implementations.

| technique | who | in the repository? | note |
|---|---|---|---|
| IC search over wheel orders and starts, then a plugboard hill-climb | Gillogly 1995 | yes | The foundation |
| Three-pass IC → bigram → trigram plug search; exhaust the right ring | Sullivan and Weierud 2005 | yes (two phases: IC, then a bigram-plus-trigram score) | The repository's calibration is the most careful measurement of this attack's limits I know of |
| **Partial plugboard exhaustion** (solo, duet, trio, quartet; E-, R-, I-Stecker) | Ostwald and Weierud 2017 | **no** | The authors' remedy for low-IC and short messages; S-1 |
| Splitting a message at a suspected left-wheel turnover; handling garbles | Ostwald and Weierud 2017 | yes, and extended (head/tail windows, split-point climb) | The repository goes beyond the paper here |
| Choosing the n-gram length (trigrams as the compromise; hexagrams only for clean text) | Ostwald and Weierud 2017 | yes (bigram + trigram) | Their argument against long n-grams for garbled text supports the current choice |
| GPU hill-climb with selectable fitness (IC, unigram, bigram, trigram) and exhaustion flags | enigma-cuda (VE3NEA) | partly (own CUDA engine; no exhaustion; one fitness mix) | Its default mixes IC, unigram and trigram. A unigram swap did not help here (S-1) |
| Brute-force settings plus a plugboard hill-climb, distributed | M4 Project, Enigma@home (Krah) | yes | Same structure, run for the Naval M4 |
| Randomised restarts, simulated annealing, genetic algorithms for the plugboard | Lasry; a 2020 Cryptologia genetic-algorithm paper | no | S-3 |
| Crib-driven Bombe, including constraint-programming and SAT formulations | Turing; a 2021 constraint-programming paper; a Dec 2025 paper by Downs, Sigmon and Klima (reported, not read) | deferred (Phase 2 gates G1 to G3) | See below |
| Related-message cribs after correcting the transcription | the MVUEH break, Sep 2026 | the idea is in Phase 2 | See below |

**MVUEH (2026).** The one recent break of a message that had resisted the
ciphertext-only tools since 2005 was a crib attack. By CryptoCellar's account it
used the repeated place name ROSENOW as a crib, found by relating the message to
a solved one (Nr. 173, SIPVX), in a message that had transcription errors, a
left-wheel turnover inside it (position 72 of 82) and a wheel order different
from that day's other messages. Three things transfer: relate unbroken messages
to solved traffic before searching; re-check the transcription against the form;
and do not assume that the day's wheel order applies. Phase 2's gates measured
that no crib prior can be quantified for this batch, which the MVUEH account does
not contradict, since its crib came from a specific related message and not from
routine formulae. CryptoCellar's account attributes the break to an AI model
(GPT-6 Astra) working with parallel agents; I did not verify that independently
and it does not bear on the technique.

## 5. Limits of this review

- B-1 and S-1 rest on **model-typical** plaintexts (Markov samples of the
  published counts) and four hand-written ones. Real messages differ from both. The
  Markov texts are fitted to the scorer and so flatter the n-gram phase; the
  hand-written ones were made up by me. Neither replaces held-out authentic
  plaintext of 167 letters, which the repository does not have.
- IC explains much of the variation but I did not isolate it from other text
  properties; the correlation (0.87 across 16 texts) and the paper's own account
  are the evidence.
- The v5 table has 40 draws per cell. The E-Stecker numbers are true-setting
  climbs with 18 to 36 draws, plus one harness run. All are small samples.
- The union and companion confirmation at typical IC were not measured. The
  earlier numerical multipliers are withdrawn after the corrected rerun.
- Scope. Read in full: `enigma.py`, `enigma_fast.py`, `stecker_climb.py`,
  `stecker_scoring.py`, `stecker_space.py` (the ring-rule code), the worker, merge
  and checkpoint code of `stecker_sweeps.py`, `stecker_power.py`'s draw routine,
  `phase1.py`'s procedure, and the confirmation code in `stecker_controls.py`.
  Not read: `stecker_cuda.py` internals (it was exercised through the harness
  only), `stecker_split.py`, `stecker_calibration.py`, `check_artifacts.py`, and
  Phases 2 to 7 beyond what STATUS and the histories say. I did not rerun any
  sweep or test CUDA parity.
- Works I cite from search summaries and did not read: the constraint-programming
  paper, the genetic-algorithm paper, Downs, Sigmon and Klima, and Lasry's thesis.

## 6. Reproducing

```bash
python3 -m unittest discover -q
python3 scripts/review/independent_enigma.py
python3 scripts/review/plaintext_power.py --texts 16 --draws 60
python3 scripts/review/plaintext_power.py --base-config experiments/phase1-fault-power-v1/config.json \
    --arm split_complete --texts 4 --draws 40 --jobs 1
python3 scripts/review/estecker_direct.py --text markov-0 --draws 24 --methods base,E
```

## 7. Resolution (same pull request)

| finding | status |
|---|---|
| B-1 power on one plaintext | Fixed in the harness and the record. `end_to_end_power` takes a `plaintexts` list (one per draw, keys unchanged) and reports detection by plaintext and by IC tercile. The closure is recorded as conditional on plaintext IC in the Phase 1 history. A preregistered control, `phase1-estecker-power-v1`, measures v4's climb with and without E-Stecker on 24 typical-IC plaintexts. The earlier power figures are not rewritten; they are labelled by what they were measured under |
| B-2 trapped climb | Addressed by S-1: the starts run at every setting |
| B-3 README "every trial" | Fixed |
| B-4 stale docs, tracked pyc | Fixed: `__pycache__/enigma.cpython-313.pyc` untracked; STATUS test count updated |
| B-5 source facts | Recorded in STATUS with dates |
| S-1 partial plugboard exhaustion | Implemented as `climb.first_plug` in the reference, batched and CUDA climbs, with identical plugboard, evaluation count, score and window checked by `tests/test_first_plug.py` and, before any run, by a new preflight check (`first_plug_climbs_match`). Not combined with the split-point climb, which refuses it |
| S-2 plaintext-aware power | Done, as B-1 |
| S-3 randomised restarts | Not done: untested alternative |
| S-4 wheel-order non-clashing rule | Not done: a cost saver that depends on Batch C following Army key rules |

The sweep the maintainer asked for next, v4 rerun with E-Stecker, is preregistered
as `phase1-body-direct-sweep-v6`, gated on the power control above.

## Sources

- Ostwald and Weierud, [*Modern Breaking of Enigma Ciphertexts*](https://www.cryptocellar.org/pubs/enigma-modern-breaking.pdf), Cryptologia 41(5), 2017 (author's version 5): sections 4 to 8 for IC and short messages, partial exhaustion, and left-wheel turnover.
- Sullivan and Weierud, [*Breaking German Army Ciphers*](https://cryptocellar.org/pubs/mcts.pdf), Cryptologia 2005.
- CryptoCellar, [The MVUEH Break](https://www.cryptocellar.org/bgac/the-mvueh-break.html); [Ultimate Enigma Challenge](https://www.cryptocellar.org/bgac/ultimate-enigma.html); [unbroken 1941 list](https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html); [unbroken Army messages](https://www.cryptocellar.org/bgac/g-army-messages.html).
- [enigma-cuda](https://github.com/VE3NEA/enigma-cuda) (VE3NEA).
- [M4 Project](https://ciphermachinesandcryptology.com/en/m4project.htm) and [Enigma@home](http://www.enigmaathome.net/).
- Lasry, work on hill climbing and simulated annealing for classical ciphers (see the [CrypTool overview](https://www.cryptool.org/media/post-contents/20-years-cryptool/CT20years_Modern_Cryptanalysis_of_Historical_Ciphers.pdf)).
- [On How Turing and Singleton Arc Consistency Broke the Enigma Code](https://drops.dagstuhl.de/opus/volltexte/2021/15304) (CP 2021).
- [Genetic algorithm attack on Enigma's plugboard](https://www.tandfonline.com/doi/full/10.1080/01611194.2020.1721617) (Cryptologia 2020).
