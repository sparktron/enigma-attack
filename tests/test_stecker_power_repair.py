"""The oracle repair option of the end-to-end power runner."""

import json
import pathlib
import random
import unittest

import stecker_power
from stecker_scoring import FastNgramScorer

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/phase1-windowed-climb-power-v1/config.json"


class RepairFaultTest(unittest.TestCase):
    clean = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def perturbed(self, seed):
        return stecker_power.perturb_ciphertext(self.clean, "indel", random.Random(seed))

    def test_a_dropped_letter_comes_back_as_a_mask_at_its_position(self):
        for seed in range(40):
            text, fault = self.perturbed(seed)
            if fault["kind"] != "deletion":
                continue
            repaired = stecker_power.repair_fault(text, fault)
            p = fault["position"]
            self.assertEqual(repaired, self.clean[:p] + "?" + self.clean[p + 1 :])
            return
        self.fail("no deletion drawn")

    def test_an_inserted_letter_is_removed(self):
        for seed in range(40):
            text, fault = self.perturbed(seed)
            if fault["kind"] != "insertion":
                continue
            self.assertEqual(stecker_power.repair_fault(text, fault), self.clean)
            return
        self.fail("no insertion drawn")

    def test_no_fault_is_left_alone(self):
        self.assertEqual(stecker_power.repair_fault(self.clean, {"kind": "none"}), self.clean)

    def test_an_arm_without_repair_gets_the_message_itself(self):
        marker = object()
        self.assertIs(stecker_power.arm_message(marker, "A", {"kind": "none"}, {}), marker)

    def test_unknown_repair_is_refused(self):
        with self.assertRaises(ValueError):
            stecker_power.arm_message(object(), "A", {"kind": "none"}, {"repair": "guess"})


class OracleArmDrawTest(unittest.TestCase):
    def test_on_an_unperturbed_draw_the_oracle_arm_equals_the_plain_arm(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        settings = config["end_to_end_power"]
        plain = next(a for a in settings["arms"] if a["id"] == "middle_past_notch")
        settings["arms"] = [plain, {**plain, "id": "oracle", "repair": "oracle"}]
        settings["null_trials"] = 1
        stecker_power._power_init(config, FastNgramScorer(config["scorer"]))
        row = stecker_power._power_draw((0, 0))  # cell 0 is unperturbed
        self.assertEqual(row["arms"]["middle_past_notch"], row["arms"]["oracle"])


if __name__ == "__main__":
    unittest.main()
