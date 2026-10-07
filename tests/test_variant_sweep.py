"""The unsteckered exhaustive sweep: kernel, schedules, planting and gates."""

from __future__ import annotations

import json
import pathlib
import random
import unittest
from unittest import mock

try:
    import numpy as np
except ImportError:  # pragma: no cover - the fast extra is optional
    np = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/phase3-unsteckered-sweep-v1/config.json"


@unittest.skipIf(np is None, "numpy is not installed")
class VariantSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import phase3
        import phase3_sweep
        from stecker_scoring import FastNgramScorer

        cls.sweep = phase3_sweep
        cls.config = phase3_sweep.load_config(CONFIG)
        cls.machines = phase3_sweep.load_machines(cls.config)
        cls.scorer = FastNgramScorer(cls.config["scorer"])
        cls.bigram = np.array(cls.scorer.bigram)
        cls.combined = np.array(cls.scorer.combined)
        _, cls.profiles = phase3.load_variant_catalog()

    def test_every_window_start_maps_to_the_schedule_enigma_py_steps_through(self) -> None:
        from variant_sweep import stepping_schedules

        generator = random.Random(1)
        for pid, (machine, profile) in self.machines.items():
            order = machine.orders()[generator.randrange(6)]
            schedules = stepping_schedules(machine, order, 70)
            for _ in range(40):
                key = self.sweep.random_key(generator)
                reference = self.sweep.reference_machine(profile, order, key)
                start = [rotor.pos for rotor in (reference.L, reference.M, reference.R)]
                start.append(reference.reflector_pos)
                index = (start[0] * 26 + start[1]) * 26 + start[2]
                counts = schedules.counts[schedules.of_start[index]]
                for keystroke in range(70):
                    reference.step()
                    now = [rotor.pos for rotor in (reference.L, reference.M, reference.R)]
                    now.append(reference.reflector_pos)
                    expected = [(now[i] - start[i]) % 26 for i in range(4)]
                    self.assertEqual(counts[keystroke].tolist(), expected, (pid, order, key, keystroke))

    def test_the_kernel_parity_preflight_passes_on_every_machine(self) -> None:
        report = self.sweep.kernel_parity(self.machines, self.scorer, {"seed": 3, "samples": 3, "length": 40})
        self.assertTrue(report["passed"], report)
        self.assertEqual(set(report["machines"]), set(self.machines))

    def test_scoring_in_blocks_changes_no_total(self) -> None:
        from variant_sweep import order_tables, score_grid, stepping_schedules

        machine, _ = self.machines["swiss_k_army_1941"]
        order = machine.orders()[2]
        generator = random.Random(4)
        body = [generator.randrange(26) for _ in range(30)]
        body[9] = -1
        schedules = stepping_schedules(machine, order, len(body))
        tables = order_tables(machine, order)
        whole = score_grid(tables, schedules.counts[5], body, self.bigram, self.combined, block=26)
        for block in (1, 3, 7):
            blocked = score_grid(tables, schedules.counts[5], body, self.bigram, self.combined, block=block)
            self.assertTrue(np.array_equal(whole, blocked), block)

    def test_a_planted_message_ranks_first_in_its_own_wheel_order(self) -> None:
        from variant_sweep import sweep_order

        machine, profile = self.machines["railway_enigma"]
        generator = random.Random(5)
        source = self.sweep.normalize_plaintext(self.config["control_plaintext"])
        planted = self.sweep.plant(profile, machine, source, [0] * 40, generator)
        result = sweep_order(machine, tuple(planted["order"]), planted["body"], self.bigram, self.combined, keep=3)
        top = result["top"][0]
        key = {k: top[k] for k in ("rings", "positions", "reflector_position")}
        decrypted = self.sweep.reference_decrypt(profile, planted["order"], key, planted["body"])
        self.assertEqual("".join(chr(65 + v) for v in decrypted), planted["plaintext"])
        self.assertEqual(result["evaluated"], result["schedules"] * 26**4)

    def test_a_faulted_plant_deciphers_head_and_tail_under_its_two_keys(self) -> None:
        machine, profile = self.machines["swiss_k_army_1941"]
        source = self.sweep.normalize_plaintext(self.config["control_plaintext"])
        generator = random.Random(6)
        template = [0] * 50
        template[20] = -1
        for fault in ("deletion", "insertion"):
            for _ in range(5):
                planted = self.sweep.plant(profile, machine, source, template, generator, fault)
                body, cut = planted["body"], planted["fault_position"]
                head = self.sweep.reference_decrypt(profile, planted["order"], planted["keys"][0], body)
                tail = self.sweep.reference_decrypt(profile, planted["order"], planted["keys"][1], body)
                plain = [ord(c) - 65 for c in planted["plaintext"]]
                shift = 1 if fault == "deletion" else -1
                for j in range(len(body)):
                    if body[j] < 0:
                        continue
                    if j < cut:
                        self.assertEqual(head[j], plain[j], (fault, j))
                    elif j > cut:
                        self.assertEqual(tail[j], plain[j + shift], (fault, j))
                self.assertEqual(len(body), 50)
                self.assertEqual(body[20], -1)

    def test_a_steckered_profile_is_refused(self) -> None:
        from variant_sweep import Machine

        steckered = next(p for p in self.profiles if p.plugboard_practice != "none")
        with self.assertRaises(ValueError):
            Machine.from_profile(steckered)

    def test_predictions_are_scored_and_inapplicable_ones_are_none(self) -> None:
        sweeps = [
            {"machine": "a", "message": "X", "detected": False, "score_distribution": {"top_z": 6.1}},
            {"machine": "a", "message": "Y", "detected": False, "score_distribution": {"top_z": 6.9}},
        ]
        power = [
            {"machine": "a", "message": "X", "fault": "none", "rate": 0.99},
            {"machine": "a", "message": "Y", "fault": "none", "rate": 0.97},
            {"machine": "a", "message": "Y", "fault": "deletion", "rate": 0.30},
        ]
        rows = {row["id"]: row for row in self.sweep.score_predictions(self.config, sweeps, power)}
        self.assertFalse(rows["unsteckered-detection"]["passed"])
        self.assertIsNone(rows["companion-detected"]["passed"])
        self.assertTrue(rows["clean-power-at-least-95pct"]["passed"])
        self.assertTrue(rows["null-top-in-noise-band"]["passed"])

        sweeps[0].update(detected=True, score_distribution={"top_z": 15.0})
        rows = {row["id"]: row for row in self.sweep.score_predictions(self.config, sweeps, power)}
        self.assertTrue(rows["unsteckered-detection"]["passed"])
        self.assertFalse(rows["companion-detected"]["passed"])
        self.assertIsNone(rows["null-top-in-noise-band"]["passed"])

    def test_a_failed_gate_makes_no_target_sweep(self) -> None:
        refused = mock.Mock(side_effect=AssertionError("a target was swept"))
        with mock.patch.object(self.sweep, "sweep_messages", refused):
            with mock.patch.object(self.sweep, "kernel_parity", return_value={"passed": False}):
                result = self.sweep.run_experiment(self.config, CONFIG, [], 1)
            self.assertEqual(result["status"], "blocked_by_preflight")
            self.assertIsNone(result["result"])
            with mock.patch.object(self.sweep, "kernel_parity", return_value={"passed": True}), \
                    mock.patch.object(self.sweep, "evaluate_positive_controls",
                                      return_value={"evaluated": [], "passed": False}):
                result = self.sweep.run_experiment(self.config, CONFIG, [], 1)
            self.assertEqual(result["status"], "blocked_by_positive_control")
            self.assertIsNone(result["result"])
        refused.assert_not_called()

    def test_the_configuration_is_preregistered_and_well_formed(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["mode"], "unsteckered_body_direct_sweep")
        self.assertEqual(
            [p["id"] for p in config["predictions"] if p["decides_hypothesis"]],
            ["unsteckered-detection"],
        )
        self.assertNotIn("tirpitz_t", config["profiles"])


if __name__ == "__main__":
    unittest.main()
