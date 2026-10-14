"""scripts/joint_power_estecker_v1.py: companions, retention, confirmation and the predictions."""

import json
import pathlib
import random
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import joint_power_estecker_v1 as joint  # noqa: E402

CONFIG = json.loads((ROOT / joint.CONFIG).read_text(encoding="utf-8"))
ARMS = ("complete_w117", "complete_w117_estecker")
PLANTED = {
    "rotor_order_left_to_right": ["II", "V", "III"],
    "rings": "TZH",
    "start_position": "CGK",
    "plugboard": "AS BN CF DY GI KW LM OQ RZ TU",
}


def draw(top_plugboard, score, exact):
    top = {"score_per_letter": score, "rings": PLANTED["rings"], "start_position": "CGK",
           "plugboard": top_plugboard, "plugboard_recovered_exactly": exact}
    return {"cell": 0, "draw": 0, "planted": PLANTED, "arms": {arm: {"top": dict(top)} for arm in ARMS}}


class OneDrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joint.init(CONFIG)
        cls.thresholds = {0: {arm: -7.7 for arm in ARMS}}
        cls.cutoffs = {"complete_w117": -7.63, "complete_w117_estecker": -7.58}

    def run_draw(self, *args):
        return joint.one_draw((draw(*args), self.thresholds, self.cutoffs))

    def test_the_planted_key_is_confirmed_retained_and_detected(self):
        row = self.run_draw(PLANTED["plugboard"], -6.8, True)
        for arm in ARMS:
            a = row["arms"][arm]
            self.assertTrue(a["confirmed"] and a["retained"] and a["detected"] and a["sweep_success"], a)
            self.assertGreaterEqual(a["min_best_z"], 6.0)

    def test_a_wrong_plugboard_is_not_confirmed(self):
        row = self.run_draw("AB CD EF GH IJ KL MN OP QR ST", -6.8, False)
        for arm in ARMS:
            a = row["arms"][arm]
            self.assertFalse(a["confirmed"] or a["sweep_success"] or a["detected"], a)
            self.assertTrue(a["retained"])  # retention is about the score alone

    def test_retention_uses_each_arms_own_cutoff(self):
        row = self.run_draw(PLANTED["plugboard"], -7.60, True)
        self.assertTrue(row["arms"]["complete_w117"]["retained"])
        self.assertFalse(row["arms"]["complete_w117_estecker"]["retained"])
        self.assertTrue(row["arms"]["complete_w117"]["sweep_success"])
        self.assertFalse(row["arms"]["complete_w117_estecker"]["sweep_success"])
        self.assertTrue(row["arms"]["complete_w117_estecker"]["detected"])

    def test_companions_depend_on_the_draw_only_and_both_arms_share_them(self):
        a = self.run_draw(PLANTED["plugboard"], -6.8, True)
        b = self.run_draw(PLANTED["plugboard"], -6.8, True)
        self.assertEqual(a, b)
        self.assertEqual(a["arms"]["complete_w117"]["companion_best_z"], a["arms"]["complete_w117_estecker"]["companion_best_z"])
        first = joint.companions_for(PLANTED, random.Random("20261116:0:0"))
        second = joint.companions_for(PLANTED, random.Random("20261116:0:0"))
        self.assertEqual([m.body for m in first], [m.body for m in second])
        self.assertEqual([len(m.body) for m in first], [107, 97])


class StatisticsTests(unittest.TestCase):
    def rows(self, flags):
        return [{"arms": {"x": dict(zip(("detected", "retained", "confirmed", "sweep_success"), f))}} for f in flags]

    def test_rate_and_conditional(self):
        rows = self.rows([(1, 1, 1, 1), (1, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 0)])
        self.assertEqual(joint.rate(rows, "x", lambda a: a["sweep_success"])["count"], 1)
        c = joint.conditional(rows, "x", lambda a: a["detected"], lambda a: a["confirmed"])
        self.assertEqual((c["count"], c["of"], c["rate"]), (2, 2, 1.0))
        none = joint.conditional(rows, "x", lambda a: a["detected"] and a["retained"] and False, lambda a: True)
        self.assertEqual((none["of"], none["rate"], none["interval_95"]), (0, None, None))

    def test_predictions_are_scored_from_the_cells(self):
        def arm(success, confirmed_given, retained_given):
            return {"sweep_success": {"rate": success}, "confirmed_given_detected": {"rate": confirmed_given},
                    "retained_given_detected": {"rate": retained_given}}

        cells = {
            "clean": {"arms": {"complete_w117_estecker": arm(0.70, 0.95, 0.97), "complete_w117": arm(0.30, 0.9, 0.9)}},
            "indel": {"arms": {"complete_w117_estecker": arm(0.40, 0.9, 0.9), "complete_w117": arm(0.10, 0.9, 0.9)}},
        }
        scored = {p["id"]: p for p in joint.score_predictions(CONFIG["joint_analysis"]["predictions"], cells)}
        self.assertTrue(all(scored[k]["passed"] for k in ("J1", "J2", "J3", "J4", "J5", "J6")))
        cells["clean"]["arms"]["complete_w117_estecker"] = arm(0.50, 0.80, 0.80)
        cells["clean"]["arms"]["complete_w117"] = arm(0.40, 0.9, 0.9)  # gain 0.10, clear of the 0.20 bar
        scored = {p["id"]: p for p in joint.score_predictions(CONFIG["joint_analysis"]["predictions"], cells)}
        self.assertEqual([k for k in scored if not scored[k]["passed"]], ["J1", "J2", "J3", "J4", "J6"])
        self.assertAlmostEqual(scored["J2"]["observed"], 0.50 - 0.7305375, places=6)

    def test_an_unknown_prediction_kind_is_refused(self):
        with self.assertRaises(ValueError):
            joint.score_predictions([{"id": "X", "statement": "", "kind": "nope", "cell": "clean",
                                      "arm": "complete_w117_estecker", "value": 0}],
                                    {"clean": {"arms": {"complete_w117_estecker": {}}}})


if __name__ == "__main__":
    unittest.main()
