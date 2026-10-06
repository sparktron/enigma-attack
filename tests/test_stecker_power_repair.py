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
    def draw(self, cell, draw=0):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        settings = config["end_to_end_power"]
        plain = next(a for a in settings["arms"] if a["id"] == "middle_past_notch")
        settings["arms"] = [plain, {**plain, "id": "oracle", "repair": "oracle"}]
        settings["null_trials"] = 2
        stecker_power._power_init(config, FastNgramScorer(config["scorer"]))
        return config, stecker_power._power_draw((cell, draw))

    def test_on_an_unperturbed_draw_the_oracle_arm_equals_the_plain_arm(self):
        _, row = self.draw(0)  # cell 0 is unperturbed
        oracle = dict(row["arms"]["oracle"])
        # Repair is the identity here, so the oracle's own null is the pooled one.
        self.assertEqual(oracle.pop("null_scores"), row["null_scores"])
        self.assertEqual(row["arms"]["middle_past_notch"], oracle)

    def test_on_an_indel_draw_the_oracle_null_is_climbed_on_the_repaired_message(self):
        config, row = self.draw(1)  # cell 1 carries one indel
        fault = row["planted"]["perturbation"]
        self.assertIn(fault["kind"], ("deletion", "insertion"))
        oracle_null = row["arms"]["oracle"]["null_scores"]
        self.assertEqual(len(oracle_null), 2)
        self.assertNotIn("null_scores", row["arms"]["middle_past_notch"])
        # Recompute the first null from the repaired message at the same wrong
        # setting the runner drew, and check the runner used exactly that.
        settings = config["end_to_end_power"]
        generator = random.Random(f"{settings['seed']}:1:0")
        wheels = list(config["machine"]["wheel_set"])
        order = tuple(generator.sample(wheels, 3))
        for _ in range(6):
            generator.randrange(26)
        stecker_power.random_plugboard(generator, int(settings["stecker_pairs"]))
        text = stecker_power.normalize_plaintext(settings["plaintext"])[: int(settings["cells"][1]["length"])]
        clean = stecker_power.EnigmaI(
            rotors=order,
            rings=row["planted"]["rings"],
            positions=row["planted"]["start_position"],
            plugboard=row["planted"]["plugboard"],
        ).crypt(text)
        ciphertext, _ = stecker_power.perturb_ciphertext(clean, "indel", generator)
        wrong_order = tuple(generator.sample(wheels, 3))
        while wrong_order == order:
            wrong_order = tuple(generator.sample(wheels, 3))
        wrong_rings = tuple(generator.randrange(26) for _ in range(3))
        wrong_start = tuple(generator.randrange(26) for _ in range(3))
        repaired = stecker_power.Traffic(
            designator="R", first_trigram=(0, 0, 0), second_trigram=(0, 0, 0),
            body=stecker_power.enigma_fast.text_to_indices(
                stecker_power.repair_fault(ciphertext, fault)
            ),
        )
        expected = stecker_power.body_direct_climb(
            [repaired], wrong_order, wrong_rings, [wrong_start],
            stecker_power._POWER["scorer"], stecker_power._POWER["reflector"], config["climb"],
        )[0].score_per_letter
        self.assertAlmostEqual(oracle_null[0], expected, places=9)
        self.assertNotAlmostEqual(oracle_null[0], row["null_scores"][0], places=9)


if __name__ == "__main__":
    unittest.main()
