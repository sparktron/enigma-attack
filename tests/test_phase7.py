import copy
import json
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

    def test_positive_controls_pass_under_rotation_aware_accuracy(self) -> None:
        with mock.patch("phase7.phase6.run_experiment") as target_search:
            target_search.return_value = {
                "status": "stubbed",
                "method": {},
                "hypothesis_supported": False,
                "controls": {},
                "target": {},
                "observed": {},
            }
            result = phase7.run_experiment(
                self.config, phase7.DEFAULT_CONFIG, ["--config", str(phase7.DEFAULT_CONFIG)]
            )
        preflight = result["positive_control_preflight"]
        self.assertTrue(preflight["passed"])
        controls = {control["id"]: control for control in preflight["controls"]}
        self.assertEqual(set(controls), {"primary", "ragged-both-stages"})
        target_search.assert_called_once()

        # The 148-letter control is an exact multiple of its 4-wide first stage,
        # so an alternative key reads out the same plaintext rotated by one row.
        primary = controls["primary"]["plaintext_agreement"]
        self.assertLess(primary["exact"], 0.1)
        self.assertGreaterEqual(primary["best_over_allowed_rotations"], 0.95)
        self.assertEqual(primary["rotation_offset"], 4)

        # The 133-letter control divides neither width, so no rotation is
        # available and the search must land on the exact key to pass.
        ragged = controls["ragged-both-stages"]
        self.assertEqual(ragged["plaintext_agreement"]["exact"], 1.0)
        self.assertEqual(ragged["rotation_degeneracy_possible"], [])
        self.assertEqual(ragged["plaintext_agreement"]["allowed_rotation_offsets"], 1)
        self.assertEqual(ragged["key"], ragged["known_key"])

    def test_failed_positive_control_stops_target_search(self) -> None:
        config = copy.deepcopy(self.config)
        config["additional_positive_controls"] = [
            {
                "id": "unrecoverable",
                "plaintext": "A" * 60 + "B" * 73,
                "first_order": [1, 3, 0, 2],
                "second_order": [2, 4, 0, 3, 1],
                "width_pairs": [[4, 5]],
            }
        ]
        with mock.patch("phase7.phase6.run_experiment") as target_search:
            result = phase7.run_experiment(config, phase7.DEFAULT_CONFIG, ["--config", "test"])
        self.assertEqual(result["status"], "invalid_positive_control_failure")
        self.assertIsNone(result["search"])
        target_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
