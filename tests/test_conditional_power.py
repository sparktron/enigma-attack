"""Strata, thresholds and the yield arithmetic of scripts/conditional_power.py."""

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "conditional_power.py"
SPEC = importlib.util.spec_from_file_location("conditional_power", SCRIPT)
cp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cp)

ARMS = ["past_notch_whole", "past_notch_w117", "complete_whole", "complete_w117", "oracle_past_notch"]


def draw(cell, position=None, **scores):
    """scores: arm -> (exact plugboard, score per letter); anything unnamed fails."""
    arms = {a: {"top": {"plugboard_recovered_exactly": False, "score_per_letter": -9.0}} for a in ARMS}
    for arm, (exact, score) in scores.items():
        arms[arm] = {"top": {"plugboard_recovered_exactly": exact, "score_per_letter": score}}
    fault = {"kind": "none"} if position is None else {"kind": "deletion", "position": position}
    return {"cell": cell, "planted": {"perturbation": fault}, "arms": arms}


def result(draws):
    cell = {"null": {"detection_threshold_score_per_letter": -8.0},
            "arms": [{"arm": a} for a in ARMS]}
    cell["arms"][1] = {"arm": "past_notch_w117", "null": {"detection_threshold_score_per_letter": -7.5}}
    cell["arms"][3] = {"arm": "complete_w117", "null": {"detection_threshold_score_per_letter": -7.5}}
    return {"cells": [cell, cell], "draws": draws}


PLAN = {
    "reference_arms": ["past_notch_whole", "past_notch_w117"],
    "middle_third": [56, 111], "minimum_stratum_size": 2,
    "predictions": [
        {"id": "C1", "stratum": "clean", "arm": "complete_w117", "kind": "rate_at_least", "value": 0.5},
        {"id": "C2", "stratum": "indel_middle_third", "arm": "complete_w117", "kind": "rate_at_most", "value": 0.2},
        {"id": "C3", "stratum": "indel_middle_third", "arm": "oracle_past_notch", "kind": "rate_at_least", "value": 0.6}],
    "yield_model": {"settings_ratio": 9.0, "reference_host_hours": 17.0, "fault_priors_reported": [0.2],
                    "nominal_fault_prior": 0.2, "assumed_split_cost_multiplier": 4},
}


class DetectionTest(unittest.TestCase):
    def test_exact_plugboard_and_the_arm_own_threshold_are_both_required(self):
        rows = cp.detection_flags(result([
            draw(0, past_notch_whole=(True, -8.1), past_notch_w117=(True, -7.6), complete_w117=(True, -7.4)),
        ]))
        got = rows[0]["detected"]
        self.assertFalse(got["past_notch_whole"])   # -8.1 is under the cell threshold -8.0
        self.assertFalse(got["past_notch_w117"])    # -7.6 is under its own threshold -7.5
        self.assertTrue(got["complete_w117"])
        self.assertFalse(got["oracle_past_notch"])  # not exact

    def test_a_high_score_with_the_wrong_plugboard_is_not_a_detection(self):
        rows = cp.detection_flags(result([draw(0, complete_whole=(False, -1.0))]))
        self.assertFalse(rows[0]["detected"]["complete_whole"])


class StrataTest(unittest.TestCase):
    def build(self):
        covered = dict(past_notch_whole=(True, -7.0))
        return result([
            draw(0, **covered), draw(0), draw(0, complete_w117=(True, -7.0)),   # clean: 2 missed, 1 rescued
            draw(1, 56), draw(1, 111, oracle_past_notch=(True, -7.0)),            # middle third, missed
            draw(1, 55, oracle_past_notch=(True, -7.0)), draw(1, 112),            # elsewhere, missed
            draw(1, 80, **covered),                                              # covered, not missed
        ])

    def test_boundaries_and_the_missed_definition(self):
        report = cp.analyse(self.build(), PLAN)
        self.assertEqual(report["missed_by_both_reference_arms"],
                         {"clean": 2, "indel_middle_third": 2, "indel_elsewhere": 2})
        self.assertEqual(report["draws"], {"clean": 3, "indel": 5})

    def test_rates_and_verdicts(self):
        report = cp.analyse(self.build(), PLAN)
        verdicts = {p["id"]: p["verdict"] for p in report["conditional_predictions"]}
        self.assertEqual(verdicts, {"C1": "held", "C2": "held", "C3": "refuted"})  # 1/2, 0/2, 1/2
        self.assertEqual(report["detection_among_missed"]["clean"]["complete_w117"]["detected"], 1)

    def test_a_small_stratum_is_not_estimable(self):
        report = cp.analyse(self.build(), dict(PLAN, minimum_stratum_size=3))
        self.assertTrue(all(p["verdict"] == "not estimable" for p in report["conditional_predictions"]))
        self.assertEqual(report["next_step_per_decision_rule"], "undecided: a stratum is too small")


class YieldTest(unittest.TestCase):
    def test_break_even_multiplier_by_hand(self):
        # m_clean = 0.5, m_indel = 0.5; a_clean = 0.5, a_indel = 0.25, o_indel = 0.75; q = 0.2.
        # w_clean = 0.4, w_indel = 0.1 -> total 0.5.
        # p_complete = (0.4 * 0.5 + 0.1 * 0.25) / 0.5 = 0.45; p_split = 0.1 * 0.75 / 0.5 = 0.15.
        # k* = 9 * 0.15 / 0.45 = 3.0, and complete per host-hour = 0.45 / (9 * 17).
        draws = []
        draws += [draw(0, complete_w117=(True, -7.0)), draw(0), draw(0, past_notch_whole=(True, -7.0)), draw(0, past_notch_whole=(True, -7.0))]
        draws += [draw(1, 70, complete_w117=(True, -7.0), oracle_past_notch=(True, -7.0)),
                  draw(1, 71, oracle_past_notch=(True, -7.0)), draw(1, 72, oracle_past_notch=(True, -7.0)),
                  draw(1, 73),
                  draw(1, 90, past_notch_whole=(True, -7.0)), draw(1, 91, past_notch_whole=(True, -7.0)),
                  draw(1, 92, past_notch_whole=(True, -7.0)), draw(1, 93, past_notch_whole=(True, -7.0))]
        report = cp.analyse(result(draws), dict(PLAN, minimum_stratum_size=1))
        # clean: 2 of 4 missed; its two missed draws: one rescued -> a_clean = 0.5.
        # indel: 4 of 8 missed; complete rescues 1 -> 0.25; oracle rescues 3 -> 0.75.
        self.assertAlmostEqual(report["missed_fraction"]["clean"], 0.5)
        self.assertAlmostEqual(report["missed_fraction"]["indel"], 0.5)
        row = report["yield_by_fault_prior"]["0.2"]
        self.assertAlmostEqual(row["p_complete"], 0.45)
        self.assertAlmostEqual(row["p_split_ceiling"], 0.15)
        self.assertAlmostEqual(row["break_even_cost_multiplier_k_star"], 3.0)
        self.assertAlmostEqual(row["complete_per_host_hour"], 0.45 / (9 * 17))
        self.assertEqual(report["next_step_per_decision_rule"], "complete_first")  # k* 3.0 < assumed 4


if __name__ == "__main__":
    unittest.main()
