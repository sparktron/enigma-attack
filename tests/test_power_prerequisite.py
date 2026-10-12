"""A failed or stale power control must never launch a target sweep."""

import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import phase1_stecker as runner
from stecker_climb import start_boards


class PowerPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = pathlib.Path(self.directory.name)
        self.inputs = {}
        for name in ("corpus", "bigram", "trigram"):
            path = root / name
            path.write_text(name)
            self.inputs[name] = str(path)
        self.calibration = root / "calibration.json"
        self.calibration.write_text(json.dumps({
            "experiment_id": "control", "mode": "end_to_end_power",
            "climb": {"phases": ["ngram"], "max_pairs": 10,
                      "max_passes": 30, "minimum_gain": 1e-9},
            "end_to_end_power": {"arms": [
                {"id": "baseline", "ring_rule": "middle_complete",
                 "window": {"kind": "head_tail", "letters": 117}},
                {"id": "E", "ring_rule": "middle_complete",
                 "window": {"kind": "head_tail", "letters": 117},
                 "first_plug": {"letters": "E"}},
            ]},
        }))
        self.artifact_path = root / "control.json"
        self.artifact = {
            "schema": runner.RESULT_SCHEMA, "experiment_id": "control",
            "mode": "end_to_end_power", "status": "complete",
            "code": {"dirty": False},
            "configuration": {"sha256": runner.sha256_file(self.calibration)},
            "preflight": {"passed": True},
            "positive_controls": {"passed": True},
            "inputs": {
                "corpus_sha256": runner.sha256_file(pathlib.Path(self.inputs["corpus"])),
                "bigram_counts_sha256": runner.sha256_file(pathlib.Path(self.inputs["bigram"])),
                "trigram_counts_sha256": runner.sha256_file(pathlib.Path(self.inputs["trigram"])),
            },
            "result": {
                "predictions": [{"id": "P2", "passed": True},
                                {"id": "P3", "passed": True}],
                "cells": [{"length": 167, "perturbation": "none", "arms": [
                    {"arm": "baseline", "draws": 480, "detected": 165},
                    {"arm": "E", "draws": 480, "detected": 363},
                ]}],
            },
        }
        self.config = {
            "corpus": self.inputs["corpus"],
            "scorer": {"bigram_counts": self.inputs["bigram"],
                       "trigram_counts": self.inputs["trigram"]},
            "climb": {"phases": ["ngram"], "max_pairs": 10,
                      "max_passes": 30, "minimum_gain": 1e-9,
                      "window": {"kind": "head_tail", "letters": 117},
                      "first_plug": {"letters": "E"}},
            "body_direct_sweep": {"ring_rule": "middle_complete"},
            "power_prerequisite": {
                "artifact": str(self.artifact_path), "config": str(self.calibration),
                "experiment_id": "control", "arm": "E", "baseline_arm": "baseline",
                "length": 167, "minimum_clean_detection": 0.75,
                "minimum_clean_gain": 0.2, "required_predictions": ["P2", "P3"],
            },
        }
        self.write_artifact()

    def write_artifact(self):
        self.artifact_path.write_text(json.dumps(self.artifact))
        self.config["power_prerequisite"]["sha256"] = runner.sha256_file(self.artifact_path)

    def reject(self):
        with patch.object(runner, "sweep_slice") as sweep:
            with self.assertRaises(ValueError):
                runner.run_body_direct_sweep(self.config, None, (), (), 1)
            sweep.assert_not_called()

    def test_valid_control_records_recomputed_rates(self):
        result = runner.validate_power_prerequisite(self.config)
        self.assertEqual(result["clean_detection_rate"], 363 / 480)
        self.assertEqual(result["clean_detection_gain"], 198 / 480)

    def test_ungated_historical_config_is_unchanged(self):
        self.assertIsNone(runner.validate_power_prerequisite({}))

    def test_missing_or_changed_artifact_cannot_search(self):
        self.artifact_path.unlink()
        self.reject()
        self.write_artifact()
        self.artifact_path.write_text("{}")
        self.reject()

    def test_stale_configuration_cannot_search(self):
        self.calibration.write_text("{}")
        self.reject()

    def test_failed_missing_or_incomplete_control_cannot_search(self):
        original = copy.deepcopy(self.artifact)
        for field, value in [("status", "blocked_by_positive_control"),
                             ("preflight", {"passed": False}),
                             ("positive_controls", {"passed": False}),
                             ("code", {"dirty": True})]:
            with self.subTest(field=field):
                self.artifact = copy.deepcopy(original)
                self.artifact[field] = value
                self.write_artifact()
                self.reject()
        self.artifact = copy.deepcopy(original)
        self.artifact["result"]["predictions"] = [{"id": "P2", "passed": True}]
        self.write_artifact()
        self.reject()

    def test_changed_input_cannot_search(self):
        pathlib.Path(self.inputs["trigram"]).write_text("changed")
        self.reject()

    def test_rates_are_checked_even_if_prediction_flags_say_passed(self):
        self.artifact["result"]["cells"][0]["arms"][1]["detected"] = 350
        self.write_artifact()
        self.reject()
        self.artifact["result"]["cells"][0]["arms"][1]["detected"] = 363
        self.artifact["result"]["cells"][0]["arms"][0]["detected"] = 300
        self.write_artifact()
        self.reject()

    def test_changed_climb_or_ring_rule_cannot_reuse_power(self):
        original = copy.deepcopy(self.config)
        for field, value in [("first_plug", {"letters": "ENR"}),
                             ("window", {"kind": "head_tail", "letters": 100}),
                             ("max_passes", 1)]:
            with self.subTest(field=field):
                self.config = copy.deepcopy(original)
                self.config["climb"][field] = value
                self.reject()
        self.config = copy.deepcopy(original)
        self.config["body_direct_sweep"]["ring_rule"] = "held"
        self.reject()


class FirstPlugCapacityTests(unittest.TestCase):
    def test_zero_capacity_cannot_start_from_a_one_pair_board(self):
        with self.assertRaisesRegex(ValueError, "max_pairs"):
            start_boards({"first_plug": {"letters": "E"}, "max_pairs": 0})

    def test_zero_capacity_without_exhaustion_keeps_the_identity(self):
        self.assertEqual(start_boards({"max_pairs": 0}), [list(range(26))])
