"""scripts/joint_power_estecker_v1.py: companions, retention, confirmation and the predictions."""

import json
import pathlib
import random
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import joint_power_estecker_v1 as joint  # noqa: E402
from stecker_power import cluster_interval, wilson_interval  # noqa: E402

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


class ClusterTests(unittest.TestCase):
    def test_plaintexts_that_differ_make_the_interval_wider_than_the_draw_level_one(self):
        # 12 plaintexts always detected, 12 never: 240 draws at a pooled rate of 0.5.
        heterogeneous = [(20, 20)] * 12 + [(0, 20)] * 12
        lo, hi = cluster_interval(heterogeneous)
        wilson = wilson_interval(240, 480)
        self.assertGreater(hi - lo, 2 * (wilson[1] - wilson[0]))
        self.assertLess(lo, 0.5 - 0.15)
        self.assertGreater(hi, 0.5 + 0.15)

    def test_plaintexts_that_agree_give_a_narrow_interval_and_a_constant_gives_a_point(self):
        homogeneous = [(10, 20)] * 24
        self.assertEqual(cluster_interval(homogeneous), [0.5, 0.5])
        lo, hi = cluster_interval([(10 + (i % 3) - 1, 20) for i in range(24)])
        self.assertLess(hi - lo, 0.05)

    def test_it_is_reproducible_empty_input_is_none_and_differences_work(self):
        clusters = [(i % 7, 20) for i in range(24)]
        self.assertEqual(cluster_interval(clusters), cluster_interval(clusters))
        self.assertNotEqual(cluster_interval(clusters, seed=1), cluster_interval(clusters, seed=2))
        self.assertIsNone(cluster_interval([]))
        self.assertIsNone(cluster_interval([(0, 0)]))
        lo, hi = cluster_interval([(-3, 20)] * 12 + [(5, 20)] * 12)  # paired differences may be negative
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)

    def test_the_interval_covers_the_point_estimate(self):
        clusters = [(i % 11, 20) for i in range(24)]
        estimate = sum(c[0] for c in clusters) / sum(c[1] for c in clusters)
        lo, hi = cluster_interval(clusters)
        self.assertLessEqual(lo, estimate)
        self.assertGreaterEqual(hi, estimate)


class SummariseTests(unittest.TestCase):
    ARMS = {"complete_w117": -7.6, "complete_w117_estecker": -7.58}

    def row(self, cell, draw, plaintext, e_success, b_success=False):
        def arm(success):
            return {"detected": success, "retained": success, "confirmed": success, "sweep_success": success,
                    "score_per_letter": -7.0, "plugboard_exact": success, "companion_best_z": [9, 9], "min_best_z": 9}
        return {"cell": cell, "draw": draw, "plaintext": {"index": plaintext},
                "arms": {"complete_w117": arm(b_success), "complete_w117_estecker": arm(e_success)}}

    def test_the_first_draws_are_left_out_of_the_primary_result_and_kept_in_the_full_one(self):
        rows = [self.row(0, d, d % 4, e_success=d >= 6) for d in range(40)]
        primary = joint.summarise(rows, ["clean"], self.ARMS, 6)["clean"]
        everything = joint.summarise(rows, ["clean"], self.ARMS, 0)["clean"]
        self.assertEqual((primary["draws"], everything["draws"]), (34, 40))
        self.assertEqual(primary["arms"]["complete_w117_estecker"]["sweep_success"]["count"], 34)
        self.assertEqual(everything["arms"]["complete_w117_estecker"]["sweep_success"]["count"], 34)
        self.assertEqual(everything["arms"]["complete_w117_estecker"]["sweep_success"]["of"], 40)
        self.assertEqual(primary["plaintexts"], 4)

    def test_every_rate_carries_both_kinds_of_interval_and_the_gain_a_cluster_one(self):
        rows = [self.row(0, d, d % 4, e_success=(d % 4) < 2) for d in range(40)]
        cell = joint.summarise(rows, ["clean"], self.ARMS, 0)["clean"]
        success = cell["arms"]["complete_w117_estecker"]["sweep_success"]
        self.assertEqual(success["rate"], 0.5)
        self.assertEqual(len(success["interval_95"]), 2)
        lo, hi = success["cluster_interval_95"]
        self.assertGreater(hi - lo, success["interval_95"][1] - success["interval_95"][0])
        gain = cell["paired_sweep_success"]["gain"]
        self.assertEqual(gain["rate"], 0.5)
        self.assertLessEqual(gain["cluster_interval_95"][0], 0.5)
        given = cell["arms"]["complete_w117_estecker"]["confirmed_given_detected"]
        self.assertEqual((given["count"], given["of"]), (20, 20))
        self.assertIn("cluster_interval_95", given)


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
