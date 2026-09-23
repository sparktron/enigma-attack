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
    degenerate_rotation_offsets,
    load_config,
    plaintext_agreement,
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
        self.assertEqual(result["held_out_characters"], 0)
        self.assertIsNone(result["candidate"]["suffix_descriptive"]["per_letter"])
        self.assertIsNone(result["delta"]["suffix_descriptive_score_per_letter"])
        self.assertFalse(any("first 75 percent" in note for note in artifact["limitations"]))
        json.dumps(artifact, allow_nan=False)

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


class PlaintextAgreementTests(unittest.TestCase):
    def test_exact_match_has_zero_offset(self) -> None:
        agreement = plaintext_agreement("ANGRIFFXENDE", "ANGRIFFXENDE")
        self.assertEqual(agreement["exact"], 1.0)
        self.assertEqual(agreement["best_over_allowed_rotations"], 1.0)
        self.assertEqual(agreement["rotation_offset"], 0)

    def test_rotated_recovery_is_credited_at_its_offset(self) -> None:
        expected = "DIEKOMMANDOSTELLEMELDETXENDE"
        agreement = plaintext_agreement(expected[4:] + expected[:4], expected)
        self.assertLess(agreement["exact"], 0.5)
        self.assertEqual(agreement["best_over_allowed_rotations"], 1.0)
        self.assertEqual(agreement["rotation_offset"], 4)

    def test_unrelated_text_stays_low_under_every_rotation(self) -> None:
        agreement = plaintext_agreement("QWERTZUIOPASDFGH", "DIEKOMMANDOSTELL")
        self.assertLess(agreement["best_over_allowed_rotations"], 0.3)

    def test_length_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            plaintext_agreement("ANGRIFF", "ANGRIFFX")

    def test_rotation_credit_needs_a_width_that_divides_the_length(self) -> None:
        # 20 is a multiple of 4, so one whole row of shift is reachable.
        widths, offsets = degenerate_rotation_offsets(20, [[4, 5]])
        self.assertEqual(widths, [4, 5])
        self.assertIn(4, offsets)
        # 133 divides neither width, so nothing but exact recovery is allowed.
        widths, offsets = degenerate_rotation_offsets(133, [[4, 5]])
        self.assertEqual(widths, [])
        self.assertEqual(offsets, [0])

    def test_inadmissible_shift_gets_no_credit(self) -> None:
        expected = "DIEKOMMANDOSTELLEMELDETXENDE"
        rotated = expected[4:] + expected[:4]
        _, offsets = degenerate_rotation_offsets(len(expected), [[4, 5]])
        credited = plaintext_agreement(rotated, expected, offsets)
        self.assertEqual(credited["best_over_allowed_rotations"], 1.0)

        # The same recovery against a control whose geometry admits no shift
        # scores its exact agreement, while the unexplained near-match stays
        # visible as a diagnostic.
        strict = plaintext_agreement(rotated, expected, [0])
        self.assertEqual(strict["best_over_allowed_rotations"], strict["exact"])
        self.assertLess(strict["best_over_allowed_rotations"], 0.5)
        self.assertEqual(strict["best_over_any_rotation"], 1.0)
        self.assertEqual(strict["unrestricted_rotation_offset"], 4)


if __name__ == "__main__":
    unittest.main()
