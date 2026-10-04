import pathlib
import random
import unittest

import enigma_fast
import phase1_stecker as stecker
import stecker_companion
from enigma import EnigmaI
from stecker_companion import ALL_STARTS, companion_scan, confirm_through_companions, scan_starts
from stecker_scoring import FastNgramScorer
from stecker_traffic import Traffic, normalize_plaintext, traffic_from_corpus

ROOT = pathlib.Path(__file__).resolve().parent.parent
BODY_CONFIG = ROOT / "experiments/phase1-body-direct-sweep-v1/config.json"
PLAINTEXT = (
    "FUNKSTELLEMELDETXFEINDLICHEAUFKLAERERUEBERDEMABSCHNITTNORDXEIGENEVERLUSTE"
    "GERINGXMUNITIONFUERZWEITAGEVORHANDENXNEUEBEFEHLEERBETENX"
)


def planted(rotors, rings, plugboard, start, plaintext=PLAINTEXT):
    body = EnigmaI(rotors=rotors, rings=rings, positions=start, plugboard=plugboard).crypt(
        normalize_plaintext(plaintext)
    )
    return Traffic("PLANT", (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices(body))


class CompanionScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(BODY_CONFIG)
        cls.scorer = FastNgramScorer(cls.config["scorer"])
        cls.reflector = enigma_fast.reflector_table("B")

    @unittest.skipUnless(stecker_companion.available(), "numpy is not installed")
    def test_batched_scan_matches_the_reference_scan(self):
        generator = random.Random(5)
        message = traffic_from_corpus(ROOT / "corpus.json", "1941-09-30", ["BYQMZ"])[0]
        board = enigma_fast.plugboard_table("AQ BW CE DR FT GY HU IJ KO LP")
        for _ in range(3):
            rotors = generator.sample(["I", "II", "III", "IV", "V"], 3)
            rings = [generator.randrange(26) for _ in range(3)]
            starts = generator.sample(ALL_STARTS, 120)
            batched = scan_starts(message, rotors, rings, board, self.scorer, self.reflector, starts, "batched")
            reference = scan_starts(message, rotors, rings, board, self.scorer, self.reflector, starts, "reference")
            for left, right in zip(batched, reference):
                self.assertAlmostEqual(left, right, places=9)

    @unittest.skipUnless(stecker_companion.available(), "numpy is not installed")
    def test_the_true_key_puts_the_true_start_first_and_far_clear(self):
        plugboard = "AN BY CF DR GJ HS IL KM PV QZ"
        message = planted(("IV", "I", "V"), "BUL", plugboard, "TRE")
        result = companion_scan(
            message, ("IV", "I", "V"), (1, 20, 11),
            enigma_fast.plugboard_table(plugboard), self.scorer, self.reflector,
        )
        self.assertEqual(result["starts_scanned"], 26**3)
        # SQE double-steps into TRF on the first letter, exactly as TRE does,
        # so either may come first; the plaintext is what has to be right.
        self.assertIn(result["best_start"], {"TRE", "SQE"})
        self.assertGreater(result["best_z"], 8)
        self.assertTrue(result["best_plaintext_prefix"].startswith("FUNKSTELLE"))

    @unittest.skipUnless(stecker_companion.available(), "numpy is not installed")
    def test_a_wrong_wheel_order_is_not_confirmed(self):
        plugboard = "AN BY CF DR GJ HS IL KM PV QZ"
        message = planted(("IV", "I", "V"), "BUL", plugboard, "TRE")
        outcome = confirm_through_companions(
            [message], ("II", "III", "I"), (1, 20, 11),
            enigma_fast.plugboard_table(plugboard), self.scorer, self.reflector, 6.0,
        )
        self.assertFalse(outcome["confirmed"])
        self.assertLess(outcome["min_best_z"], 6.0)


class RunnerCompanionTests(unittest.TestCase):
    @unittest.skipUnless(stecker_companion.available(), "numpy is not installed")
    def test_the_runner_records_companion_confirmation_when_declared(self):
        config = stecker.load_config(BODY_CONFIG)
        config["machine"]["rotor_orders"] = [["I", "II", "III"]]
        config["body_direct_sweep"].update(
            {"ring_rule": "middle_past_notch", "right_ring": "A",
             "start_left": "A", "start_middle": "A", "start_right": "AB", "keep": 2,
             "companion_confirmation": {"companions": ["FKQLZ", "XFEDT"], "threshold_z": 6.0}}
        )
        traffic = traffic_from_corpus(ROOT / "corpus.json", "1941-09-30", ["BYQMZ", "FKQLZ", "XFEDT"])
        result = stecker.run_body_direct_sweep(
            config, FastNgramScorer(config["scorer"]), enigma_fast.reflector_table("B"), traffic, 1
        )
        summary = result["companion_confirmation"]
        self.assertEqual(summary["companions"], ["FKQLZ", "XFEDT"])
        for candidate in result["top_candidates"]:
            scans = candidate["companion_confirmation"]["companions"]
            self.assertEqual([scan["designator"] for scan in scans], ["FKQLZ", "XFEDT"])

    def test_the_runner_omits_it_when_not_declared(self):
        config = stecker.load_config(BODY_CONFIG)
        self.assertNotIn("companion_confirmation", config["body_direct_sweep"])


if __name__ == "__main__":
    unittest.main()
