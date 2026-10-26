# Low-IC joint calibration

The requested implementation already exists in this checkout: first_plug.ic_passes
and start_phases are implemented in reference, numpy and CUDA. R-ngonly was selected
in intervening work and v7 ran null. Do not duplicate or relaunch that work.

Preregistration (2026-10-20): fresh 12 low-IC Markov texts, 240 random keys per
clean/indel cell, compare E to R-ngonly. Seeds: text 202610201, keys 202610202,
companions 202610203. Hypothesis: clean retained-and-confirmed gain >= 8 points.
Refutation: gain below 8 points. Configuration is experiments/phase1-low-ic-joint-v1/config.json.
No primary draws were inspected before this record. No primary-draw smoke run.

Retention is the observed v6/v7 cutoff proxy, NOT a full-space ranking calibration
on every planted text. Report this limitation with any result. Existing companion
scanner and plaintext-cluster summaries are reused. No new message sweep is launched.

Validation and run provenance/results will be appended after execution.

## Completed 2026-10-21

Power: clean 19b220f, 2310.9 s. Analysis: c324e4e, 198.3 s; dirty status is the
untracked raw power artifact only. Adapter fix on synthetic inputs before observing
results; no primary-draw outcomes used to tune. GPU first-plug parity: 34 passed;
CPU suites: 47 passed, six skipped. Adapter test passed.

Observed clean E/R success 165/240 vs 183/240, indel 95/240 vs 125/240.
Clean gain 7.5 points REFUTES >=8 point rule; indel gain 12.5 points.
No new sweep warranted by that rule. Raw artifacts and test/run logs are preserved;
see experiment history for intervals and interpretation. Full-space retention rank
on every planted text remains NOT RUN (fixed observed-cutoff proxy used instead).

## Maintainer decision (2026-10-21)

The maintainer accepts the measured 7.5-point clean gain as sufficient and asks to
continue. This supersedes the no-new-sweep decision based on the >=8-point bar;
it does not change the preregistration or its refuted result.

Before launching, verified the prospective next sweep already completed: v7 used
exactly first_plug={letters: ENR, start_phases: ngram_only}, BYQMZ, middle_complete,
all right rings and all starts. Artifact status complete, 246,767,040 settings,
completed 2026-10-16T22:48:44.714376+00:00, no companion-confirmed candidate.
The new calibration changes confidence in that completed search, not its method
or coverage. Repeating it with identical settings would add no search coverage.
No duplicate sweep launched. A further run needs a different declared target,
keyspace or method, with its own preregistration and applicable control.

## Companion-free reading (2026-10-23)

`scripts/low_ic_joint_companion_free.py`, generated from clean 886c8c7, with
the result in `artifacts/phase1-low-ic-joint-v1-companion-free.json`. Without
FKQLZ/XFEDT confirmation, clean success is E 166/240 and R-ngonly 185/240,
and one-indel success is 96 and 129. Confirmation removed only 1 to 4 draws
per arm, so the result does not depend on the companions being Enigma. The
companion-free gain is 7.9 points clean, still below the 8-point bar. v7:
none of its 100 retained candidates exceeds the preregistered noise-band
ceiling (z 9.5; its top is 8.85), whereas recovered planted keys score a
median z of about 22. So v7's null holds on BYQMZ's own score. This is a
post-hoc analysis; the preregistration is unchanged.
