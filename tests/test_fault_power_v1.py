"""Fault kinds of stecker_power and the coverage rule of scripts/fault_power_v1.py."""

import importlib.util
import pathlib
import random
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import stecker_power  # noqa: E402

SPEC = importlib.util.spec_from_file_location("fault_power_v1", ROOT / "scripts" / "fault_power_v1.py")
fp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fp)

ARMS = ["past_notch_whole", "past_notch_w117", "complete_w117", "split_complete"]
TEXT = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 6


def draw(cell, *detecting):
    arms = {a: {"top": {"plugboard_recovered_exactly": False, "score_per_letter": -9.0}} for a in ARMS}
    for arm in detecting:
        arms[arm] = {"top": {"plugboard_recovered_exactly": True, "score_per_letter": -7.0}}
    return {"cell": cell, "planted": {"perturbation": {"kind": "x"}}, "arms": arms}


def result(draws):
    cell = {"null": {"detection_threshold_score_per_letter": -8.0}, "arms": [{"arm": a} for a in ARMS]}
    return {"cells": [cell, cell, cell], "draws": draws}


def plan(minimum=2):
    return {
        "sweep_arms": ARMS, "cells": {"clean": 0, "substitution": 1, "double_indel": 2},
        "minimum_draws": minimum, "substitution_prediction": "S1", "double_indel_prediction": "D1",
        "predictions": [
            {"id": "S1", "cell": "substitution", "kind": "rate_at_least", "value": 0.6},
            {"id": "D1", "cell": "double_indel", "kind": "rate_below", "value": 0.5},
        ],
    }


class FaultKindsTest(unittest.TestCase):
    def test_indel_draws_are_what_they_were(self):
        # The original algorithm, inline: a configuration written for "indel" must keep its draws.
        def original(ciphertext, generator):
            position = generator.randrange(1, len(ciphertext) - 1)
            if generator.random() < 0.5:
                return ciphertext[:position] + ciphertext[position + 1 :], {"kind": "deletion", "position": position}
            letter = chr(65 + generator.randrange(26))
            return (ciphertext[:position] + letter + ciphertext[position:],
                    {"kind": "insertion", "position": position, "letter": letter})

        for seed in range(200):
            self.assertEqual(stecker_power.perturb_ciphertext(TEXT, "indel", random.Random(seed)),
                             original(TEXT, random.Random(seed)))

    def test_substitution_changes_exactly_one_letter(self):
        for seed in range(50):
            out, fault = stecker_power.perturb_ciphertext(TEXT, "substitution", random.Random(seed))
            self.assertEqual(len(out), len(TEXT))
            changed = [i for i in range(len(TEXT)) if out[i] != TEXT[i]]
            self.assertEqual(changed, [fault["position"]])
            self.assertEqual((fault["was"], fault["letter"]), (TEXT[changed[0]], out[changed[0]]))

    def test_double_indel_applies_two_faults_in_turn(self):
        for seed in range(50):
            out, fault = stecker_power.perturb_ciphertext(TEXT, "double_indel", random.Random(seed))
            first, second = fault["faults"]
            self.assertEqual(fault["position"], first["position"])
            self.assertEqual(len(out), len(TEXT) + sum(1 if f["kind"] == "insertion" else -1 for f in (first, second)))
        with self.assertRaises(ValueError):
            stecker_power.repair_fault(TEXT, fault)
        with self.assertRaises(ValueError):
            stecker_power.perturb_ciphertext(TEXT, "swap", random.Random(0))


class CoverageRuleTest(unittest.TestCase):
    def test_union_counts_any_sweep_arm(self):
        draws = [draw(1, "split_complete"), draw(1, "past_notch_whole"), draw(1), draw(1),
                 draw(2, "complete_w117"), draw(2), draw(2), draw(2), draw(0), draw(0)]
        report = fp.analyse(result(draws), plan())
        self.assertEqual(report["covered_by_any_sweep_arm"]["substitution"]["detected"], 2)
        self.assertEqual(report["covered_by_any_sweep_arm"]["double_indel"]["odds_multiplier_left_by_four_nulls"], 0.75)

    def test_decision_rule_covers_all_four_outcomes(self):
        sub_hit, sub_miss = [draw(1, "split_complete")] * 4, [draw(1)] * 4
        dbl_hit, dbl_miss = [draw(2, "split_complete")] * 4, [draw(2)] * 4
        step = lambda s, d: fp.analyse(result(s + d), plan())["next_step_per_decision_rule"].split(":")[0]
        self.assertEqual(step(sub_hit, dbl_miss), "cost_a_two_split_climb")
        self.assertEqual(step(sub_hit, dbl_hit), "stop_the_standard_reading_search")
        self.assertEqual(step(sub_miss, dbl_miss), "cost_a_substitution_tolerant_and_a_two_split_climb")
        self.assertEqual(step(sub_miss, dbl_hit), "cost_a_substitution_tolerant_climb")
        self.assertTrue(fp.analyse(result(sub_hit + dbl_miss), plan(minimum=25))["next_step_per_decision_rule"]
                        .startswith("undecided"))


if __name__ == "__main__":
    unittest.main()
