import json
import copy
import pathlib
import tempfile
import unittest
from unittest import mock

import phase7


class Phase7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(phase7.DEFAULT_CONFIG.read_text(encoding="utf-8"))

    def test_original_grouping_matches_solver_input(self) -> None:
        audit = phase7.audit_grouping(self.config, phase7.resolve_path(self.config["corpus"]))
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["row_count"], 8)
        self.assertEqual(audit["body_length"], 155)

    def test_published_scorer_discriminates_known_plaintexts(self) -> None:
        scorer = phase7.PublishedNgramScorer(self.config["scorer"])
        validation = phase7.validate_scorer(self.config, scorer)
        self.assertTrue(validation["passed"])
        self.assertEqual(len(validation["messages"]), 5)

    def test_unknown_character_breaks_ngrams(self) -> None:
        scorer = phase7.PublishedNgramScorer(self.config["scorer"])
        score, known = scorer.score("AB?CD")
        self.assertEqual(known, 4)
        self.assertAlmostEqual(score, scorer.score("AB")[0] + scorer.score("CD")[0])

    def test_full_objective_fixes_control_boundary_displacement(self) -> None:
        phase6_config = phase7.phase6.load_config(
            phase7.resolve_path(self.config["phase6_config"])
        )
        known = phase6_config["positive_control"]
        scorer = phase7.PublishedNgramScorer(self.config["scorer"])
        ciphertext = phase7.phase6.double_columnar_transpose(
            known["plaintext"], known["first_order"], known["second_order"]
        )
        full = phase7.phase6._control_diagnostics(
            ciphertext, known["plaintext"], known["first_order"],
            known["second_order"], scorer,
        )
        prefix = phase7.phase6._control_diagnostics(
            ciphertext, known["plaintext"], known["first_order"],
            known["second_order"], scorer, prefix_fraction=0.75,
        )
        self.assertEqual(full["known_key_rank"], 1)
        self.assertTrue(full["exact_plaintext"])
        self.assertEqual(prefix["known_key_rank"], 5)
        self.assertEqual(prefix["longest_matching_segment"], 144)
        self.assertEqual(prefix["segment_offsets"], {"candidate": 0, "truth": 4})

    def test_ragged_control_extends_the_inherited_gate(self) -> None:
        failed = {"status": "invalid_positive_control_failure",
                  "controls": {"positive_double_transposition": {"passed": False}}}
        with mock.patch("phase7.phase6.run_experiment", return_value=failed) as search:
            phase7.run_experiment(self.config, phase7.DEFAULT_CONFIG, [])
        forwarded = phase7.phase6._normalize_positive_controls(search.call_args.args[0])
        identifiers = [control["id"] for control in forwarded]
        self.assertEqual(identifiers[0], "primary")
        self.assertIn("independent-solved-army-text-1941-09-24-94", identifiers)
        self.assertIn("ragged-both-stages", identifiers)

        # The ragged control is 133 letters over 4- and 5-wide stages, so no
        # whole-row rotation is reachable and only exact recovery can pass it.
        ragged = next(c for c in forwarded if c["id"] == "ragged-both-stages")
        widths, offsets = phase7.phase6.degenerate_rotation_offsets(
            len(ragged["plaintext"]), ragged["width_pairs"]
        )
        self.assertEqual(widths, [])
        self.assertEqual(offsets, [0])

    def test_duplicate_control_identifier_is_rejected(self) -> None:
        config = copy.deepcopy(self.config)
        config["additional_positive_controls"] = [
            {**config["additional_positive_controls"][0],
             "id": "independent-solved-army-text-1941-09-24-94"}
        ]
        with self.assertRaisesRegex(ValueError, "duplicate positive control id"):
            phase7.run_experiment(config, phase7.DEFAULT_CONFIG, [])

    def test_failed_positive_control_stops_target_search(self) -> None:
        failed = {"status": "invalid_positive_control_failure",
                  "controls": {"positive_double_transposition": {"passed": False}}}
        with mock.patch("phase7.phase6.run_experiment", return_value=failed) as target_search:
            result = phase7.run_experiment(self.config, phase7.DEFAULT_CONFIG, ["--config", str(phase7.DEFAULT_CONFIG)])
        self.assertEqual(result["status"], "invalid_positive_control_failure")
        self.assertIsNone(result["search"])
        self.assertIn("known-key transposition control failed", result["interpretation"])
        self.assertNotIn("held-out", result["interpretation"])
        json.dumps(result, allow_nan=False)
        target_search.assert_called_once()

    def test_audited_corpus_is_forwarded_to_search(self) -> None:
        config = copy.deepcopy(self.config)
        with tempfile.TemporaryDirectory() as directory:
            alternate = pathlib.Path(directory) / "alternate.json"
            original = json.loads(phase7.resolve_path(config["corpus"]).read_text())
            original["messages"][0]["ciphertext"] = "A" + original["messages"][0]["ciphertext"][1:]
            alternate.write_text(json.dumps(original), encoding="utf-8")
            config["corpus"] = str(alternate)
            baseline = json.loads(phase7.resolve_path(config["phase6_artifact"]).read_text())
            baseline["inputs"]["corpus_sha256"] = phase7.sha256(alternate)
            baseline_path = pathlib.Path(directory) / "baseline.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            config["phase6_artifact"] = str(baseline_path)
            failed = {"status": "invalid_positive_control_failure",
                      "controls": {"positive_double_transposition": {"passed": False}}}
            with mock.patch("phase7.audit_grouping", return_value={"passed": True}), \
                 mock.patch("phase7.validate_scorer", return_value={"passed": True}), \
                 mock.patch("phase7.phase6.run_experiment", return_value=failed) as search:
                phase7.run_experiment(config, phase7.DEFAULT_CONFIG, [])
            self.assertEqual(search.call_args.args[0]["corpus"], str(alternate))

    def test_stale_baseline_corpus_is_rejected(self) -> None:
        config = copy.deepcopy(self.config)
        with tempfile.TemporaryDirectory() as directory:
            alternate = pathlib.Path(directory) / "alternate.json"
            alternate.write_text('{"messages": []}', encoding="utf-8")
            config["corpus"] = str(alternate)
            with mock.patch("phase7.audit_grouping", return_value={"passed": True}), \
                 mock.patch("phase7.validate_scorer", return_value={"passed": True}):
                with self.assertRaisesRegex(ValueError, "baseline corpus hash"):
                    phase7.run_experiment(config, phase7.DEFAULT_CONFIG, [])


if __name__ == "__main__":
    unittest.main()
