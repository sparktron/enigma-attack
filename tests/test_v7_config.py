"""experiments/phase1-body-direct-sweep-v7: its gate and its difference from v6."""

import json
import pathlib
import unittest

import phase1_stecker as stecker

ROOT = pathlib.Path(__file__).resolve().parents[1]
V7 = ROOT / "experiments/phase1-body-direct-sweep-v7/config.json"
V6 = ROOT / "experiments/phase1-body-direct-sweep-v6/config.json"
R_NGONLY = {"letters": "ENR", "start_phases": "ngram_only"}


class V7ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v7 = stecker.load_config(V7)
        cls.v6 = json.loads(V6.read_text(encoding="utf-8"))

    def test_the_climb_is_r_ngonly_and_only_the_start_set_differs_from_v6(self):
        self.assertEqual(self.v7["climb"]["first_plug"], R_NGONLY)
        for key in ("phases", "max_pairs", "max_passes", "minimum_gain", "engine", "window"):
            self.assertEqual(self.v7["climb"][key], self.v6["climb"][key], key)
        for key in ("message", "rings", "start_left", "start_middle", "start_right", "keep", "ring_rule",
                    "right_ring", "companion_confirmation"):
            self.assertEqual(self.v7["body_direct_sweep"][key], self.v6["body_direct_sweep"][key], key)
        for key in ("machine", "scorer", "target", "indicator_orderings"):
            self.assertEqual(self.v7[key], self.v6[key], key)

    def test_it_does_not_share_a_checkpoint_or_an_output_with_v6(self):
        self.assertNotEqual(self.v7["body_direct_sweep"]["checkpoint"], self.v6["body_direct_sweep"]["checkpoint"])
        self.assertNotEqual(self.v7["output"], self.v6["output"])
        self.assertTrue(self.v7["body_direct_sweep"]["checkpoint"].startswith("build/"))

    def test_the_gate_pins_the_control_and_validates_against_the_committed_artifact(self):
        gate = self.v7["power_prerequisite"]
        self.assertEqual((gate["experiment_id"], gate["arm"]), ("phase1-rngonly-power-v1", "complete_w117_rngonly"))
        verified = stecker.validate_power_prerequisite(self.v7)
        self.assertTrue(verified["passed"])
        self.assertGreaterEqual(verified["clean_detection_rate"], gate["minimum_clean_detection"])

    def test_the_gate_requires_only_the_predictions_that_held_and_never_the_refuted_ones(self):
        gate = self.v7["power_prerequisite"]
        self.assertEqual(gate["required_predictions"], ["S1", "D4", "N2"])
        self.assertNotIn("D1", gate["required_predictions"])
        self.assertNotIn("D2", gate["required_predictions"])
        artifact = json.loads((ROOT / gate["artifact"]).read_text(encoding="utf-8"))
        held = {p["id"]: p["passed"] for p in artifact["result"]["predictions"]}
        self.assertFalse(held["D2"])  # the departure from the control's rule is real, and disclosed in the config
        self.assertIn("decision_departs_from_the_preregistered_rule", self.v7["pre_run_facts"])

    def test_a_changed_climb_or_artifact_breaks_the_gate(self):
        for mutate in (
            lambda c: c["climb"].__setitem__("first_plug", {"letters": "ENR"}),
            lambda c: c["climb"].__setitem__("first_plug", {"letters": "E", "start_phases": "ngram_only"}),
            lambda c: c["power_prerequisite"].__setitem__("sha256", "0" * 64),
            lambda c: c["power_prerequisite"].__setitem__("required_predictions", ["S1", "D2"]),
        ):
            config = json.loads(V7.read_text(encoding="utf-8"))
            mutate(config)
            with self.assertRaises(ValueError):
                stecker.validate_power_prerequisite(config)

    def test_the_stated_power_is_labelled_as_a_projection_where_it_is_one(self):
        power = self.v7["stated_power"]
        self.assertIn("inference", power["confirmation_extrapolation"]["classification"])
        self.assertEqual(power["conditional_on_v6_null_detection"]["clean"]["count"], [70, 111])


if __name__ == "__main__":
    unittest.main()
