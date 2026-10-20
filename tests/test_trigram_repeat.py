import pathlib
import random
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from trigram_repeat_v1 import (  # noqa: E402
    enigma_null,
    index_of_coincidence,
    longest_repeat,
    measure,
    p_upper,
    random_key,
    repeats_listed,
)


class TrigramRepeatTests(unittest.TestCase):
    def test_repeats_count_every_extra_occurrence(self):
        # ABC three times, BCA twice, CAB twice: 2 + 1 + 1.
        stats = measure("ABCABCABC")
        self.assertEqual(stats["trigram_repeats"], 4)
        self.assertEqual(stats["repeated_trigrams"], 3)

    def test_uncertain_character_removes_its_windows(self):
        self.assertEqual(measure("ABCXABC")["trigram_repeats"], 1)
        self.assertEqual(measure("ABCX?BC")["trigram_repeats"], 0)

    def test_longest_repeat_allows_overlap_and_stops_at_uncertain(self):
        self.assertEqual(longest_repeat("AAAA"), 3)
        self.assertEqual(longest_repeat("ABCDE"), 0)
        self.assertEqual(longest_repeat("ABCD?ABCD"), 4)
        self.assertEqual(longest_repeat("AB?CAB?C"), 2)

    def test_index_of_coincidence_ignores_uncertain(self):
        self.assertAlmostEqual(index_of_coincidence("AABB"), 4 / 12)
        self.assertAlmostEqual(index_of_coincidence("AA?BB"), 4 / 12)

    def test_repeats_listed_gives_positions(self):
        self.assertEqual(repeats_listed("XYZQXYZ"), [{"trigram": "XYZ", "positions": [0, 4]}])

    def test_p_value_counts_ties_and_is_never_zero(self):
        null = [{"s": v} for v in (0, 1, 2, 3)]
        self.assertEqual(p_upper(2, null, "s"), 3 / 5)
        self.assertEqual(p_upper(9, null, "s"), 1 / 5)

    def test_random_key_is_a_legal_ten_pair_service_key(self):
        key = random_key(random.Random(1))
        self.assertEqual(len(set(key["rotors"])), 3)
        letters = key["plugboard"].replace(" ", "")
        self.assertEqual(len(letters), 20)
        self.assertEqual(len(set(letters)), 20)

    def test_null_masks_uncertain_positions_and_is_seeded(self):
        pool = "DIESISTEINTEST" * 10
        a = enigma_null(pool, 30, [5], 5, random.Random(7))
        b = enigma_null(pool, 30, [5], 5, random.Random(7))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)


    def test_draws_override_refuses_to_replace_the_committed_artifact(self):
        import subprocess

        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "trigram_repeat_v1.py"), "--draws", "5"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--output", completed.stderr)


if __name__ == "__main__":
    unittest.main()
