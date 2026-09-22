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

    def test_failed_positive_control_stops_target_search(self) -> None:
        with mock.patch("phase7.phase6.run_experiment") as target_search:
            result = phase7.run_experiment(self.config, phase7.DEFAULT_CONFIG, ["--config", str(phase7.DEFAULT_CONFIG)])
        self.assertEqual(result["status"], "invalid_positive_control_failure")
        self.assertIsNone(result["search"])
        target_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
