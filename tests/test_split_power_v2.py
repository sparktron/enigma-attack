"""Strata, the deciding prediction and the conditional arithmetic of scripts/split_power_v2.py."""

import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "split_power_v2.py"
SPEC = importlib.util.spec_from_file_location("split_power_v2", SCRIPT)
sp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sp)

ARMS = ["past_notch_whole", "past_notch_w117", "complete_w117", "split_past_notch", "split_complete"]
HIT = (True, -7.0)


def draw(cell, position=None, **scores):
    """scores: arm -> (exact plugboard, score per letter); anything unnamed fails."""
    arms = {a: {"top": {"plugboard_recovered_exactly": False, "score_per_letter": -9.0}} for a in ARMS}
    for arm, (exact, score) in scores.items():
        arms[arm] = {"top": {"plugboard_recovered_exactly": exact, "score_per_letter": score}}
    fault = {"kind": "none"} if position is None else {"kind": "insertion", "position": position}
    return {"cell": cell, "planted": {"perturbation": fault}, "arms": arms}


def result(draws):
    cell = {"null": {"detection_threshold_score_per_letter": -8.0}, "arms": [{"arm": a} for a in ARMS]}
    return {"cells": [cell, cell], "draws": draws}


def plan(minimum=2):
    config = json.loads((ROOT / "experiments/phase1-split-point-power-v2/config.json").read_text(encoding="utf-8"))
    return {**config["end_to_end_power"]["split_v2_analysis"], "minimum_stratum_size": minimum}


class SplitPowerV2Test(unittest.TestCase):
    def test_a_draw_any_reference_arm_detects_is_not_missed(self):
        draws = [
            draw(1, 60, complete_w117=HIT, split_complete=HIT),   # v4's climb finds it: not missed
            draw(1, 60, split_complete=HIT),                       # missed, split finds it
            draw(1, 10),                                           # missed, nothing finds it
            draw(0, past_notch_whole=HIT),                         # clean, found by v2's climb
            draw(0),                                               # clean, missed
        ]
        report = sp.analyse(result(draws), plan())
        self.assertEqual(report["missed_by_every_reference_arm"],
                         {"clean": 1, "indel": 2, "indel_middle_third": 1, "indel_elsewhere": 1})
        self.assertEqual(report["detection_among_missed"]["indel"]["split_complete"]["detected"], 1)

    def test_the_deciding_prediction_drives_the_next_step(self):
        held = [draw(1, 60, split_complete=HIT), draw(1, 70, split_complete=HIT), draw(1, 80)]
        self.assertEqual(sp.analyse(result(held), plan())["next_step_per_decision_rule"],
                         "preregister_complete_split_sweep")
        refuted = [draw(1, 60), draw(1, 70), draw(1, 80), draw(1, 90, split_complete=HIT)]
        self.assertEqual(sp.analyse(result(refuted), plan())["next_step_per_decision_rule"], "no_split_sweep")
        self.assertEqual(sp.analyse(result(refuted), plan(minimum=25))["next_step_per_decision_rule"],
                         "undecided: the deciding stratum is too small")

    def test_the_gain_prediction_and_the_conditional_mixture(self):
        draws = [
            draw(1, 60, split_complete=HIT, split_past_notch=HIT),
            draw(1, 70, split_complete=HIT),
            draw(1, 80), draw(1, 90),
            draw(0, split_complete=HIT), draw(0),
            draw(0, past_notch_whole=HIT), draw(0, past_notch_whole=HIT),
        ]
        report = sp.analyse(result(draws), plan())
        t2 = next(p for p in report["predictions"] if p["id"] == "T2")
        self.assertAlmostEqual(t2["observed"], 0.25)
        self.assertEqual(t2["verdict"], "held")
        # m_clean = 2/4, m_indel = 4/4; a_clean = 1/2, a_indel = 2/4.
        q = 0.2
        w_clean, w_indel = (1 - q) * 0.5, q * 1.0
        expected = (w_clean * 0.5 + w_indel * 0.5) / (w_clean + w_indel)
        self.assertAlmostEqual(report["conditional_detection_by_fault_prior"]["0.2"], expected)


if __name__ == "__main__":
    unittest.main()
