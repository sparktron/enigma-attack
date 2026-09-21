import copy
import json
import pathlib
import tempfile
import unittest

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

    def test_search_never_scores_the_held_out_suffix(self) -> None:
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
        self.assertEqual(set(scorer.lengths), {int(len(text) * 0.6)})

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
        train_end = int(len(plaintext) * 0.75)
        expected_raw, expected_known = scorer.score(plaintext[:train_end])
        self.assertGreaterEqual(
            candidate.train_score_per_letter,
            expected_raw / expected_known,
        )


class Phase6ArtifactTests(unittest.TestCase):
    def test_preregistered_config_is_valid(self) -> None:
        config = load_config(DEFAULT_CONFIG)
        self.assertEqual(config["target_designator"], "QTXMA")
        self.assertEqual(config["split"]["training_fraction"], 0.75)
        self.assertIn([5, 7], config["search"]["target_width_pairs"])

    def test_smoke_artifact_preserves_scope_and_controls(self) -> None:
        config = copy.deepcopy(load_config(DEFAULT_CONFIG))
        config["experiment_id"] = "phase6-unit-smoke"
        config["search"]["target_width_pairs"] = [[3, 4]]
        config["search"]["seeds"] = [17]
        config["search"]["restarts"] = 1
        config["search"]["iterations"] = 3
        config["acceptance"]["minimum_passing_seeds"] = 1
        with tempfile.TemporaryDirectory() as directory:
            config_path = pathlib.Path(directory) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            artifact = run_experiment(config, config_path, ["--config", str(config_path)])

        self.assertEqual(artifact["schema"], "enigma-attack.phase6-experiment/v1")
        self.assertEqual(artifact["target"]["designator"], "QTXMA")
        self.assertFalse(artifact["accepted_break"])
        self.assertIn("positive_double_transposition", artifact["controls"])
        self.assertIn("monoalphabetic_substitution", artifact["controls"])
        result = artifact["target"]["seed_results"][0]
        self.assertEqual(
            result["training_characters"] + result["held_out_characters"],
            result["ciphertext_length"],
        )


if __name__ == "__main__":
    unittest.main()
