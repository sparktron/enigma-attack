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
    SearchCandidate,
    load_config,
    plaintext_agreement,
    reachable_rotation_offsets,
    recovery_verdict,
    run_experiment,
    search_double_transposition,
    validate_config,
)

SOLVED_1941_09_24_94 = (
    "UMZUGGEPAEQTROSSUNDRESTKOMMANDOSTOPFENXSQRIFTLIQERBEFEHLUNTERWEGSXSCHNEIDDRX"
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

    def test_search_rejects_nonfinite_scorer_output(self) -> None:
        class NonfiniteScorer:
            def score(self, text):
                return float("nan"), len(text)

        with self.assertRaisesRegex(ValueError, "nonfinite raw score"):
            search_double_transposition(
                "ABCDEFGH", [(2, 2)], training_fraction=1.0,
                scorer=NonfiniteScorer(),
            )

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

    def test_invalid_acceptance_and_search_numbers_fail_validation(self) -> None:
        cases = (
            ("acceptance", "minimum_positive_plaintext_accuracy", -1),
            ("acceptance", "minimum_positive_plaintext_accuracy", float("nan")),
            ("acceptance", "maximum_empirical_p_value", float("inf")),
            ("acceptance", "minimum_passing_seeds", -1),
            ("search", "null_replicates", 1.5),
            ("search", "max_exhaustive_states", 0),
            ("search", "restarts", True),
            ("search", "target_width_pairs", [[2.5, 2]]),
        )
        for section, field, value in cases:
            with self.subTest(section=section, field=field, value=value):
                config = copy.deepcopy(load_config(DEFAULT_CONFIG))
                config[section][field] = value
                with self.assertRaisesRegex(ValueError, field):
                    validate_config(config)

    def test_invalid_recovery_gate_stops_before_search(self) -> None:
        config = self._smoke_config()
        config["acceptance"]["minimum_positive_plaintext_accuracy"] = -1
        with mock.patch("phase6.search_double_transposition") as search:
            with self.assertRaisesRegex(ValueError, "minimum_positive_plaintext_accuracy"):
                run_experiment(config, pathlib.Path("unused.json"), [])
        search.assert_not_called()

    @staticmethod
    def _smoke_config() -> dict:
        config = copy.deepcopy(load_config(DEFAULT_CONFIG))
        config["experiment_id"] = "phase6-unit-smoke"
        config["search"]["target_width_pairs"] = [[3, 4]]
        config["search"]["seeds"] = [17]
        config["search"]["restarts"] = 1
        config["search"]["iterations"] = 3
        config["search"]["null_replicates"] = 1
        config["additional_positive_controls"] = []
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
            root = pathlib.Path(directory)
            # The conservation gate would refuse this target before any control
            # ran, which is a different test; this one is about the control.
            config["phase5_artifact"] = str(self._ungated_phase5(root))
            path = root / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with mock.patch("phase6.search_double_transposition", wraps=search_double_transposition) as search:
                result = run_experiment(config, path, [], scorer=FlatScorer())
        self.assertEqual(result["status"], "invalid_positive_control_failure")
        self.assertEqual(result["target"]["seed_results"], [])
        self.assertEqual(result["target"]["skipped_reason"], "positive_control_failed")
        self.assertEqual(search.call_count, 1 + len(config["additional_positive_controls"]))
        self.assertEqual(
            [control["id"] for control in result["controls"]["additional_known_key"]],
            [control["id"] for control in config["additional_positive_controls"]],
        )

    def test_tied_raw_scores_do_not_become_a_signal_when_rounded(self) -> None:
        config = self._smoke_config()
        config["search"].update(
            target_width_pairs=[[2, 2]], control_width_pairs=[[2, 2]],
            seeds=[1], null_replicates=19,
        )
        config["positive_control"] = {
            "plaintext": "AAAAAAAA", "first_order": [0, 1], "second_order": [0, 1],
        }
        for per_letter in (1.0000000006, 1.0000000004, -1.0000000006):
            class FlatScorer:
                def score(self, text):
                    return len(text) * per_letter, len(text)
            with self.subTest(per_letter=per_letter):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    config["phase5_artifact"] = str(self._ungated_phase5(root))
                    path = root / "config.json"
                    path.write_text(json.dumps(config), encoding="utf-8")
                    result = run_experiment(config, path, [], FlatScorer())
                calibration = result["observed"]["search_calibration"]
                self.assertEqual(calibration["empirical_p_value"], 1.0)
                self.assertFalse(result["hypothesis_supported"])

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

    def test_one_letter_ragged_row_admits_an_equivalent_rotation(self) -> None:
        # 76 = 15 * 5 + 1: the lone final-row letter lets a different first
        # stage key encipher the plaintext rotated by one to the same text.
        plaintext = SOLVED_1941_09_24_94
        first, second = [3, 0, 4, 1, 2], [6, 1, 4, 0, 5, 2, 3]
        ciphertext = double_columnar_transpose(plaintext, first, second)
        offsets = reachable_rotation_offsets(plaintext, ciphertext, [[5, 7]])
        self.assertEqual(offsets, [0, 75])
        rotated = plaintext[75:] + plaintext[:75]
        self.assertEqual(
            double_columnar_transpose(rotated, [4, 1, 0, 2, 3], second), ciphertext
        )

    def test_divisibility_neither_implies_nor_excludes_rotation(self) -> None:
        text = "DIEKOMMANDOSTELLEMELDETANGRIFFVONNORDOSTXENDE"
        def offsets(length: int) -> list[int]:
            plaintext = text[:length]
            ciphertext = double_columnar_transpose(plaintext, [2, 0, 3, 1], [4, 1, 3, 0, 2])
            return reachable_rotation_offsets(plaintext, ciphertext, [[4, 5]])
        self.assertEqual(offsets(20), [0, 4, 8, 12, 16])
        # 24 and 40 are multiples of 4, yet no alternative key reproduces
        # either ciphertext from a rotated plaintext.
        self.assertEqual(offsets(24), [0])
        self.assertEqual(offsets(40), [0])

    def test_equivalent_rotation_passes_and_stays_distinguishable(self) -> None:
        plaintext = SOLVED_1941_09_24_94
        control = {"id": "c", "plaintext": plaintext, "first_order": [3, 0, 4, 1, 2],
                   "second_order": [6, 1, 4, 0, 5, 2, 3], "width_pairs": [[5, 7]]}
        rotated = plaintext[75:] + plaintext[:75]
        candidate = SearchCandidate(rotated, (4, 1, 0, 2, 3), (6, 1, 4, 0, 5, 2, 3),
                                    -1.0, "test", 1)
        verdict = recovery_verdict(control, candidate, {}, AdjacencyScorer())
        self.assertTrue(verdict["passed"])
        self.assertFalse(verdict["exact_plaintext"])
        self.assertFalse(verdict["exact_key"])
        self.assertEqual(verdict["plaintext_agreement"]["rotation_offset"], 75)
        self.assertEqual(verdict["reachable_rotation_offsets"], [0, 75])

    def test_inadmissible_shift_gets_no_credit(self) -> None:
        expected = "DIEKOMMANDOSTELLEMELDETXENDE"
        rotated = expected[4:] + expected[:4]
        credited = plaintext_agreement(rotated, expected, [0, 4])
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
