"""scripts/rngonly_power_v1.py: detection by IC tercile, paired counts and predictions."""

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rngonly_power_v1 as rp  # noqa: E402

CONFIG = json.loads((ROOT / rp.CONFIG).read_text(encoding="utf-8"))


def artifact(per_plaintext, ics, detect):
    """``detect(arm, plaintext, k)`` -> whether that arm's top candidate detects draw k of the plaintext."""

    draws, number = [], 0
    for plaintext in range(len(ics)):
        for k in range(per_plaintext):
            arms = {}
            for arm in rp.ARMS:
                hit = detect(arm, plaintext, k)
                arms[arm] = {"top": {"plugboard_recovered_exactly": hit, "score_per_letter": -7.0 if hit else -9.0}}
            draws.append({"cell": 0, "draw": number, "plaintext": {"index": plaintext, "index_of_coincidence": ics[plaintext]}, "arms": arms})
            number += 1
    cell = {"perturbation": "none", "null": {"detection_threshold_score_per_letter": -8.0},
            "arms": [{"arm": arm} for arm in rp.ARMS]}
    return {"result": {"cells": [cell], "draws": draws}}


class AnalysisTests(unittest.TestCase):
    ICS = [0.07 - 0.001 * i for i in range(24)]  # plaintext 0 has the highest IC, 23 the lowest

    def test_terciles_follow_ic_not_index(self):
        names = rp.tercile_of(artifact(1, self.ICS, lambda *a: False))
        self.assertEqual([names[i] for i in (23, 16)], ["low", "low"])
        self.assertEqual([names[i] for i in (15, 8)], ["mid", "mid"])
        self.assertEqual([names[i] for i in (7, 0)], ["high", "high"])
        self.assertEqual(sorted(set(names.values())), ["high", "low", "mid"])

    def test_detection_rule_needs_exact_plugboard_and_score_above_the_null_threshold(self):
        power = artifact(1, self.ICS, lambda arm, p, k: True)
        power["result"]["draws"][0]["arms"]["complete_w117"]["top"]["score_per_letter"] = -8.5  # below threshold
        power["result"]["draws"][1]["arms"]["complete_w117"]["top"]["plugboard_recovered_exactly"] = False
        flags = rp.detected_flags(power)[0]["complete_w117"]
        self.assertEqual([flags[0], flags[1], flags[2]], [False, False, True])

    def test_paired_counts_rates_and_mcnemar(self):
        # R-ngonly detects every low-IC draw E misses half of; v4 detects nothing.
        def detect(arm, plaintext, k):
            low = plaintext >= 16
            if arm == "complete_w117":
                return False
            if arm == "complete_w117_estecker":
                return (k % 2 == 0) if low else True
            return True
        cells = rp.analyse(artifact(10, self.ICS, detect))["clean"]
        low = cells["low"]
        self.assertEqual(low["draws"], 80)
        self.assertEqual(low["arms"]["complete_w117_estecker"]["count"], 40)
        pair = low["paired"]["complete_w117_rngonly_vs_complete_w117_estecker"]
        self.assertEqual((pair["only_first"], pair["only_second"], pair["gain"]), (40, 0, 0.5))
        self.assertLess(pair["mcnemar_p"], 1e-9)
        high = cells["high"]["paired"]["complete_w117_rngonly_vs_complete_w117_estecker"]
        self.assertEqual((high["only_first"], high["only_second"], high["gain"], high["mcnemar_p"]), (0, 0, 0.0, 1.0))
        self.assertEqual(cells["all"]["draws"], 240)

    def test_mcnemar_exact_values(self):
        self.assertEqual(rp.mcnemar_p(0, 0), 1.0)
        self.assertAlmostEqual(rp.mcnemar_p(5, 5), 1.0)
        self.assertAlmostEqual(rp.mcnemar_p(0, 5), 2 / 32)
        self.assertAlmostEqual(rp.mcnemar_p(84, 42), 0.0002, places=4)

    def test_predictions_are_scored_and_a_regression_is_refuted(self):
        def detect(arm, plaintext, k):
            if arm == "complete_w117_rngonly":
                return plaintext >= 16 or k % 2 == 0  # loses half of E's high-IC detections
            return True if arm == "complete_w117_estecker" and plaintext < 16 else (k % 2 == 0)
        cells = rp.analyse(artifact(10, self.ICS, detect))
        scored = {p["id"]: p for p in rp.score(CONFIG["tercile_analysis"]["predictions"], cells)}
        self.assertEqual(set(scored), {"D1", "D3", "N1"})
        self.assertTrue(scored["D1"]["passed"])      # low IC: R all, E half
        self.assertFalse(scored["D3"]["passed"])     # high IC: R loses half of E's
        self.assertAlmostEqual(scored["D3"]["observed"], -0.5)
        self.assertTrue(scored["N1"]["passed"])

    def test_an_unknown_prediction_kind_is_refused(self):
        cells = rp.analyse(artifact(2, self.ICS, lambda *a: True))
        with self.assertRaises(ValueError):
            rp.score([{"id": "X", "statement": "", "kind": "nope", "cell": "clean", "tercile": "low", "arm": "complete_w117", "value": 0}], cells)


if __name__ == "__main__":
    unittest.main()
