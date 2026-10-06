"""Joining, strata and yield arithmetic of scripts/split_power.py."""

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "split_power.py"
SPEC = importlib.util.spec_from_file_location("split_power", SCRIPT)
sp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sp)

REF = ["past_notch_whole", "past_notch_w117"]


def draw(cell, draw_id, position, hits, arms):
    top = {a: {"top": {"plugboard_recovered_exactly": a in hits, "score_per_letter": -7.0}} for a in arms}
    fault = {"kind": "none"} if position is None else {"kind": "deletion", "position": position}
    return {"cell": cell, "draw": draw_id, "planted": {"perturbation": fault, "plugboard": "AB"}, "arms": top}


def result(draws, arms):
    cell = {"null": {"detection_threshold_score_per_letter": -8.0}, "arms": [{"arm": a} for a in arms]}
    return {"cells": [cell, cell], "draws": draws}


PLAN = {
    "reference_arms": REF, "middle_third": [56, 111], "minimum_stratum_size": 1,
    "candidates": {"complete": {"arm": "complete_w117", "cost_multiplier": 9.0},
                   "split": {"arm": "split", "cost_multiplier": 3.0}},
    "predictions": [
        {"id": "S1", "stratum": "indel_middle_third", "arm": "split", "kind": "rate_at_least", "value": 0.5},
        {"id": "S2", "stratum": "indel_elsewhere", "arm": "split", "kind": "rate_at_least", "value": 0.5}],
    "deciding_predictions": ["S1", "S2"],
    "yield_model": {"reference_host_hours": 10.0, "fault_priors_reported": [0.2], "nominal_fault_prior": 0.2},
}
NEW_ARMS = REF + ["split"]
OLD_ARMS = REF + ["complete_w117"]


class JoinTest(unittest.TestCase):
    def build(self, differ=False, replicate=True):
        rows = [
            (0, 0, None, ["past_notch_whole"], []),            # clean, covered
            (0, 1, None, [], ["complete_w117"]),                # clean, missed, rescued by complete
            (1, 0, 70, [], ["split"]),                          # middle, missed, split only
            (1, 1, 80, [], ["split", "complete_w117"]),         # middle, missed, both
            (1, 2, 20, [], ["complete_w117"]),                  # elsewhere, missed, complete only
            (1, 3, 130, ["past_notch_w117"], []),               # elsewhere, covered
        ]
        new = [draw(c, d, p, ref + new_hits, NEW_ARMS) for c, d, p, ref, new_hits in
               [(c, d, p, ref, [h for h in hits if h == "split"]) for c, d, p, ref, hits in rows]]
        old = [draw(c, d, p, ref + [h for h in hits if h == "complete_w117"], OLD_ARMS) for c, d, p, ref, hits in rows]
        if differ:
            old[0]["planted"]["plugboard"] = "CD"
        if not replicate:
            old[0]["arms"]["past_notch_whole"]["top"]["plugboard_recovered_exactly"] = False
        return result(new, NEW_ARMS), result(old, OLD_ARMS)

    def test_a_differently_planted_draw_stops_the_analysis(self):
        with self.assertRaises(ValueError):
            sp.analyse(*self.build(differ=True), PLAN)

    def test_a_past_notch_arm_that_does_not_reproduce_is_counted(self):
        report = sp.analyse(*self.build(replicate=False), PLAN)
        self.assertEqual(report["past_notch_arms_differing_from_the_control"]["past_notch_whole"], 1)

    def test_strata_rates_and_the_decision(self):
        report = sp.analyse(*self.build(), PLAN)
        self.assertEqual(report["past_notch_arms_differing_from_the_control"], {"past_notch_whole": 0, "past_notch_w117": 0})
        self.assertEqual(report["missed_by_both_reference_arms"],
                         {"clean": 1, "indel_middle_third": 2, "indel_elsewhere": 1})
        among = report["detection_among_missed"]
        self.assertEqual(among["indel_middle_third"]["split"]["detected"], 2)
        self.assertEqual(among["indel_middle_third"]["complete_w117"]["detected"], 1)
        self.assertEqual(among["indel_elsewhere"]["split"]["detected"], 0)
        verdicts = {p["id"]: p["verdict"] for p in report["predictions"]}
        self.assertEqual(verdicts, {"S1": "held", "S2": "refuted"})
        # m_clean = 1/2, m_indel = 3/4; q = 0.2 -> w_clean 0.4, w_indel 0.15.
        # complete: a_clean 1, a_indel 2/3 -> (0.4 + 0.1) / 0.55; split: a_clean 0, a_indel 2/3.
        row = report["yield_by_fault_prior"]["0.2"]
        self.assertAlmostEqual(row["complete"]["probability"], 0.5 / 0.55)
        self.assertAlmostEqual(row["split"]["probability"], 0.1 / 0.55)
        self.assertAlmostEqual(row["complete"]["per_host_hour"], (0.5 / 0.55) / 90.0)
        self.assertAlmostEqual(row["split"]["per_host_hour"], (0.1 / 0.55) / 30.0)
        self.assertEqual(report["next_step_per_decision_rule"], "complete_sweep")

    def test_both_deciding_predictions_refuted_drops_the_split_climb(self):
        plan = dict(PLAN, predictions=[dict(p, value=0.99) for p in PLAN["predictions"]])
        report = sp.analyse(*self.build(), plan)
        self.assertEqual(report["next_step_per_decision_rule"], "complete_sweep")


if __name__ == "__main__":
    unittest.main()
