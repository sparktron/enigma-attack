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
