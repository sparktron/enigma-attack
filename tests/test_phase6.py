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

    @staticmethod
    def _smoke_config() -> dict:
        config = copy.deepcopy(load_config(DEFAULT_CONFIG))
        config["experiment_id"] = "phase6-unit-smoke"
        config["search"]["target_width_pairs"] = [[3, 4]]
        config["search"]["seeds"] = [17]
        config["search"]["restarts"] = 1
        config["search"]["iterations"] = 3
        config["acceptance"]["minimum_passing_seeds"] = 1
        return config

    @staticmethod
    def _ungated_phase5(directory: pathlib.Path) -> pathlib.Path:
        """Copy the Phase 5 artifact with QTXMA's conservation gate suspended.

        The gate now blocks this search outright, which is the point of it.  The
        search machinery still has to work, so the fixture reproduces what Phase
        5 records when its gate is uncalibrated and therefore not applied.
        """
        source = pathlib.Path("artifacts/phase5-model-triage.json").resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        for message in payload["messages"]:
            if message["designator"] != "QTXMA":
                continue
            signals = message["analysis"]["signals"]
            signals["plaintext_unigram_compatible"] = True
            signals["frequency_preserving"] = True
            message["analysis"]["plaintext_conservation"]["gate"]["applied"] = False
            message["route"] = "frequency_preserving_manual"
        target = directory / "phase5-ungated.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    def test_conservation_gate_blocks_the_qtxma_search(self) -> None:
        """Phase 5 letter conservation must stop this search before it starts."""
        config = self._smoke_config()
        with tempfile.TemporaryDirectory() as directory:
            config_path = pathlib.Path(directory) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                run_experiment(config, config_path, ["--config", str(config_path)])
        message = str(caught.exception)
        self.assertIn("letter conservation", message)
        self.assertIn("QTXMA", message)

    def test_smoke_artifact_preserves_scope_and_controls(self) -> None:
        config = self._smoke_config()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            config["phase5_artifact"] = str(self._ungated_phase5(root))
            config_path = root / "config.json"
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
