import json
import pathlib
import random
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from jless_flat_v1 import (  # noqa: E402
    ALPHABET_25,
    enigma_null,
    measure,
    score,
    uniform25_null,
)
from trigram_repeat_v1 import ngram_repeats  # noqa: E402


class JlessFlatTests(unittest.TestCase):
    def test_quadgram_repeats_skip_uncertain_windows(self):
        self.assertEqual(ngram_repeats("ABCDXABCD", 4), 1)
        self.assertEqual(ngram_repeats("ABCDXAB?D", 4), 0)
        self.assertEqual(ngram_repeats("AAAAAA", 4), 2)

    def test_measure_counts_j_and_ignores_uncertain_in_ic(self):
        j, ic, quad = measure("JJAB?")
        self.assertEqual(j, 2)
        self.assertAlmostEqual(ic, 2 / 12)
        self.assertEqual(quad, 0)

    def test_joint_p_counts_draws_both_j_poor_and_flat(self):
        null = [(0, 0.03, 0), (0, 0.05, 0), (1, 0.02, 0), (2, 0.06, 1)]
        p = score("ABCDEFGHIK", null)["p_values"]
        # Observed: no J, IC 0.0 -- no draw is as flat, so only the +1 counts.
        self.assertEqual(p["joint_noj_lowic"], 1 / 5)
        self.assertEqual(p["p_noj"], 3 / 5)

    def test_uniform25_null_never_produces_j(self):
        self.assertNotIn("J", ALPHABET_25)
        self.assertTrue(all(d[0] == 0 for d in uniform25_null(50, [], 200, random.Random(3))))

    def test_nulls_are_seeded_and_masked(self):
        pool = "DIESISTEINTEST" * 10
        a = enigma_null(pool, 30, [2], 4, random.Random(5))
        self.assertEqual(a, enigma_null(pool, 30, [2], 4, random.Random(5)))

    def test_control_expectation_names_existing_grey_texts(self):
        config = json.loads((ROOT / "experiments/phase5-jless-flat-v1/config.json").read_text(encoding="utf-8"))
        grey = json.loads((ROOT / "data/phase5/grey-texts-ostwald-2023.json").read_text(encoding="utf-8"))
        groups = {t["first_group"] for t in grey["texts"]}
        control = config["controls"]["grey_positive"]
        self.assertTrue(set(control["expected_flagged"]) <= groups)
        self.assertTrue(set(control["expected_not_flagged"]) <= groups)
        self.assertFalse(any("J" in t["text"] for t in grey["texts"]))

    def test_scale_refuses_to_replace_the_committed_artifact(self):
        completed = subprocess.run([sys.executable, str(ROOT / "scripts" / "jless_flat_v1.py"), "--scale", "0.01"],
                                   cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--output", completed.stderr)


if __name__ == "__main__":
    unittest.main()
