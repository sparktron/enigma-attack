import copy
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from phase6 import (
    DEFAULT_CONFIG,
    AdjacencyScorer,
    columnar_transpose,
    columnar_untranspose,
    double_columnar_transpose,
    double_columnar_untranspose,
    load_config,
    run_experiment,
    search_double_transposition,
)


class Phase6TranspositionTests(unittest.TestCase):
    def test_ragged_columnar_transposition_round_trip(self) -> None:
        text = "DIESISTEINUNGERADERTESTTEXT"
        order = (3, 0, 4, 1, 2)
        ciphertext = columnar_transpose(text, order)
        self.assertEqual(columnar_untranspose(ciphertext, order), text)

    def test_double_transposition_round_trip_preserves_unknowns(self) -> None:
        text = "DIES?ISTEINWEITERERTEST"
        first = (2, 0, 3, 1)
        second = (4, 1, 3, 0, 2)
        ciphertext = double_columnar_transpose(text, first, second)
        self.assertEqual(
            double_columnar_untranspose(ciphertext, first, second),
            text,
        )

    def test_search_scores_full_candidate(self) -> None:
        class RecordingScorer:
            def __init__(self) -> None:
                self.lengths: list[int] = []

            def score(self, text: str) -> tuple[float, int]:
                self.lengths.append(len(text))
                return float(text.count("ER")), len(text)

        scorer = RecordingScorer()
        text = "DIESISTEINDEUTSCHERTESTTEXT"
        ciphertext = double_columnar_transpose(text, (2, 0, 1), (3, 1, 0, 2))
        search_double_transposition(
            ciphertext,
            [(3, 4)],
            training_fraction=0.6,
            scorer=scorer,
            max_exhaustive_states=1000,
        )
        self.assertTrue(scorer.lengths)
        self.assertEqual(set(scorer.lengths), {len(text)})

    def test_exhaustive_control_considers_the_known_solution(self) -> None:
        plaintext = "DIEKOMMANDOSTELLEMELDETANGRIFFVONNORDOSTXENDE"
        ciphertext = double_columnar_transpose(
            plaintext,
            (2, 0, 3, 1),
            (4, 1, 3, 0, 2),
        )
        scorer = AdjacencyScorer()
        candidate = search_double_transposition(
            ciphertext,
            [(4, 5)],
            training_fraction=0.75,
            scorer=scorer,
            max_exhaustive_states=3000,
        )
        expected_raw, expected_known = scorer.score(plaintext)
        self.assertGreaterEqual(
            candidate.score_per_letter,
            expected_raw / expected_known,
        )


class Phase6ArtifactTests(unittest.TestCase):
    def test_preregistered_config_is_valid(self) -> None:
        config = load_config(DEFAULT_CONFIG)
        self.assertEqual(config["target_designator"], "QTXMA")
        self.assertEqual(config["split"]["training_fraction"], 1.0)
        self.assertIn([5, 7], config["search"]["target_width_pairs"])

    def test_smoke_artifact_preserves_scope_and_controls(self) -> None:
        config = copy.deepcopy(load_config(DEFAULT_CONFIG))
        config["experiment_id"] = "phase6-unit-smoke"
        config["search"]["target_width_pairs"] = [[3, 4]]
        config["search"]["seeds"] = [17]
        config["search"]["restarts"] = 1
        config["search"]["iterations"] = 3
        config["search"]["null_replicates"] = 1
        config["additional_positive_controls"] = []
        with tempfile.TemporaryDirectory() as directory:
            config_path = pathlib.Path(directory) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            artifact = run_experiment(config, config_path, ["--config", str(config_path)])

        self.assertEqual(artifact["schema"], "enigma-attack.phase6-experiment/v1")
        self.assertEqual(artifact["target"]["designator"], "QTXMA")
        self.assertFalse(artifact["accepted_break"])
        self.assertIn("positive_double_transposition", artifact["controls"])
        self.assertIn("monoalphabetic_substitution", artifact["controls"])
        self.assertEqual(
            artifact["controls"]["positive_double_transposition"]["diagnostics"]["known_key_rank"], 1
        )
        self.assertEqual(
            len(artifact["observed"]["search_calibration"]["replicate_maxima"]), 1
        )
        result = artifact["target"]["seed_results"][0]
        self.assertEqual(
            result["training_characters"] + result["held_out_characters"],
            result["ciphertext_length"],
        )

    def test_failed_control_makes_no_target_search_calls(self) -> None:
        config = copy.deepcopy(load_config(DEFAULT_CONFIG))
        config["search"]["target_width_pairs"] = [[3, 4]]
        config["search"]["null_replicates"] = 0
        class FlatScorer:
            def score(self, text):
                return 0.0, len(text)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with mock.patch("phase6.search_double_transposition", wraps=search_double_transposition) as search:
                result = run_experiment(config, path, [], scorer=FlatScorer())
        self.assertEqual(result["status"], "invalid_positive_control_failure")
        self.assertEqual(result["target"]["seed_results"], [])
        self.assertEqual(result["target"]["skipped_reason"], "positive_control_failed")
        self.assertEqual(search.call_count, 1)

    def test_stale_phase5_corpus_evidence_is_rejected(self) -> None:
        config = copy.deepcopy(load_config(DEFAULT_CONFIG))
        with tempfile.TemporaryDirectory() as directory:
            corpus = pathlib.Path(directory) / "alternate.json"
            data = json.loads(pathlib.Path(config["corpus"]).read_text())
            data["messages"][0]["ciphertext"] = "A" + data["messages"][0]["ciphertext"][1:]
            corpus.write_text(json.dumps(data), encoding="utf-8")
            config["corpus"] = str(corpus)
            path = pathlib.Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "corpus hash"):
                run_experiment(config, path, [])


if __name__ == "__main__":
    unittest.main()
