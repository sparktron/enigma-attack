import pathlib
import random
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from flat_models_v2 import (  # noqa: E402
    ALPHABET,
    Generator,
    closeness_to_uniform,
    fit,
    grid,
    human_random,
    without_replacement,
)
from flat_structure_v1 import group_statistics  # noqa: E402


class ModelTests(unittest.TestCase):
    def test_without_replacement_has_the_requested_length_and_no_j(self):
        rng = random.Random(1)
        stream = without_replacement(500, 1, rng)
        self.assertEqual(len(stream), 500)
        self.assertNotIn("J", stream)

    def test_without_replacement_is_flatter_than_uniform_for_small_k(self):
        flat = group_statistics([without_replacement(100, 1, random.Random(2))])["ic"]
        self.assertLess(flat, 1 / 25)

    def test_human_random_with_zero_weight_never_repeats_within_window(self):
        text = human_random(300, 3, 0.0, random.Random(3))
        self.assertTrue(all(text[i] not in text[max(0, i - 3):i] for i in range(len(text))))
        self.assertTrue(set(text) <= set(ALPHABET))

    def test_generator_masks_uncertain_positions(self):
        texts = Generator("without_replacement", {"k": 2}).group([(30, [4])], random.Random(4))
        self.assertEqual(texts[0][4], "?")
        self.assertEqual(len(texts[0]), 30)

    def test_grids_and_tie_break(self):
        self.assertEqual(len(grid({"w": [1, 2], "s": [0.0, 0.5]})), 4)
        self.assertLess(closeness_to_uniform({"k": 32}), closeness_to_uniform({"k": 1}))
        self.assertLess(closeness_to_uniform({"w": 1, "s": 0.75}), closeness_to_uniform({"w": 1, "s": 0.0}))

    def test_fit_picks_the_grid_point_nearest_the_target_ic(self):
        shapes = [(120, []), (110, [])]
        low = fit("without_replacement", {"k": [1, 32]}, shapes, 0.0, 50, 7)
        high = fit("without_replacement", {"k": [1, 32]}, shapes, 0.04, 50, 7)
        self.assertEqual(low["chosen"], {"k": 1})
        self.assertEqual(high["chosen"], {"k": 32})

    def test_scale_refuses_to_replace_the_committed_artifact(self):
        completed = subprocess.run([sys.executable, str(ROOT / "scripts/flat_models_v2.py"), "--scale", "0.01"],
                                   cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--output", completed.stderr)


if __name__ == "__main__":
    unittest.main()
