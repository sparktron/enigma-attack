import pathlib
import random
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from flat_structure_v1 import (  # noqa: E402
    ALPHABET,
    Models,
    Null,
    allocate_homophones,
    group_statistics,
    homophonic,
    homophonic_tables,
    monogram_frequencies,
    playfair,
    playfair_digraphs,
    random_square,
    text_statistics,
    two_square_pass,
    two_square_unpass,
)

PLAIN = "ANPANZERGRUPPEVIERXSIEGFRIEDSIEGFRIEDTONIXDIVXSTEHTSEITXEINSZWO"


class StatisticsTests(unittest.TestCase):
    def test_doubles_and_alignment(self):
        s = text_statistics("AABDDC")  # doubles at 0 (even) and 3 (odd)
        self.assertEqual(s["doubles"], 2)
        self.assertEqual(s["min_aligned_doubles"], 1)
        self.assertEqual(text_statistics("ABBC")["min_aligned_doubles"], 0)

    def test_uncertain_pairs_are_skipped(self):
        self.assertEqual(text_statistics("A??B")["doubles"], 0)

    def test_aligned_digraph_repeats_use_the_alignment_with_fewer_doubles(self):
        # Even alignment: AB AB CC -> one double, repeats 1; odd alignment: BA BC -> no double, no repeat.
        self.assertEqual(text_statistics("ABABCC")["aligned_digraph_repeats"], 0)
        self.assertEqual(text_statistics("ABABCD")["aligned_digraph_repeats"], 1)

    def test_periodic_ic_detects_a_period(self):
        periodic = group_statistics(["ABCDE" * 20])
        self.assertEqual(periodic["periodic_ic_by_period"][5], 1.0)
        self.assertEqual(periodic["periodic_ic_peak"], 1.0)


class ModelTests(unittest.TestCase):
    def test_playfair_round_trips_and_never_doubles_within_a_digraph(self):
        rng = random.Random(1)
        square = random_square(rng)
        prepared = "".join(a + b for a, b in playfair_digraphs(PLAIN.replace("J", "I")))
        cipher = playfair(PLAIN.replace("J", "I"), square)
        self.assertEqual(playfair(cipher, square, decrypt=True), prepared)
        self.assertEqual(text_statistics(cipher)["min_aligned_doubles"], 0)
        self.assertTrue(all(a != b for a, b in zip(cipher[::2], cipher[1::2])))

    def test_two_square_round_trips(self):
        rng = random.Random(2)
        left, right = random_square(rng), random_square(rng)
        once = two_square_pass(PLAIN, left, right)  # PLAIN has odd length: one X pad
        self.assertEqual(two_square_unpass(once, left, right), PLAIN + "X")
        twice = two_square_pass(once, left, right)
        self.assertEqual(two_square_unpass(two_square_unpass(twice, left, right), left, right), PLAIN + "X")

    def test_homophone_allocation_uses_25_symbols_and_covers_every_letter(self):
        classes = allocate_homophones(monogram_frequencies(ROOT / "data/phase7/BigramFrequency1941.txt"))
        self.assertEqual(sum(k["symbols"] for k in classes), 25)
        self.assertEqual("".join(sorted("".join(k["letters"] for k in classes))), ALPHABET)

    def test_homophonic_cyclic_rotates_and_every_output_letter_is_a_symbol_of_its_class(self):
        classes = allocate_homophones(monogram_frequencies(ROOT / "data/phase7/BigramFrequency1941.txt"))
        table = homophonic_tables(classes, random.Random(3))
        cipher = homophonic("EEEEEE", table, random.Random(4), cyclic=True)
        self.assertTrue(all(c in table["E"] for c in cipher))
        self.assertEqual(len(set(cipher[:len(table["E"])])), len(table["E"]))

    def test_models_produce_the_requested_length_and_masks(self):
        models = Models(PLAIN * 4, allocate_homophones(
            monogram_frequencies(ROOT / "data/phase7/BigramFrequency1941.txt")))
        for name in ("uniform25", "homophonic_random", "homophonic_cyclic", "playfair", "two_square_double"):
            texts = models.group(name, [(41, [3]), (30, [])], random.Random(5))
            self.assertEqual([len(t) for t in texts], [41, 30])
            self.assertEqual(texts[0][3], "?")
            self.assertNotIn("J", "".join(texts))


class InferenceTests(unittest.TestCase):
    def test_p_values_follow_the_stated_tails(self):
        draws = [{"doubles": v, "min_aligned_doubles": 0, "aligned_digraph_repeats": 0,
                  "periodic_ic_peak": v, "ic": 0.0} for v in range(10)]
        null = Null(draws)
        self.assertAlmostEqual(null.p("periodic_ic_peak", 9), 2 / 11)
        self.assertAlmostEqual(null.p("doubles", 0), 4 / 11)
        self.assertEqual(null.p("doubles", 5), 1.0)

    def test_scale_refuses_to_replace_the_committed_artifact(self):
        completed = subprocess.run([sys.executable, str(ROOT / "scripts/flat_structure_v1.py"), "--scale", "0.01"],
                                   cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--output", completed.stderr)


if __name__ == "__main__":
    unittest.main()
