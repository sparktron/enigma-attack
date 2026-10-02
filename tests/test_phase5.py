import argparse
import json
import pathlib
import random
import tempfile
import unittest

from phase5 import (
    DEFAULT_CATALOG,
    DEFAULT_CONTROL_PLAINTEXTS,
    DEFAULT_CORPUS,
    DEFAULT_UNIGRAM_SOURCE,
    UNIGRAM_NULL_CONCENTRATION,
    absence_surprisal,
    analyze_ciphertext,
    apply_conservation_gate,
    build_artifact,
    calibrate_conservation_gate,
    index_of_coincidence,
    load_army_unigrams,
    load_conservation_controls,
    load_family_catalog,
    periodic_ic_profile,
    reference_chi_square,
    repeated_ngram_pairs,
    route_message,
)


GERMAN_WEIGHTS = [
    0.0651, 0.0189, 0.0306, 0.0508, 0.1740, 0.0166, 0.0301,
    0.0476, 0.0755, 0.0027, 0.0121, 0.0344, 0.0253, 0.0978,
    0.0251, 0.0079, 0.0002, 0.0700, 0.0727, 0.0615, 0.0435,
    0.0067, 0.0189, 0.0003, 0.0004, 0.0113,
]
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class ConservationGateTests(unittest.TestCase):
    """The gate's job is to exclude by conservation without excluding truth."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = load_army_unigrams()
        cls.controls = load_conservation_controls()

    def test_reference_is_army_plaintext_not_newspaper_german(self) -> None:
        probabilities = self.reference["probabilities"]
        self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=9)
        # X marks punctuation and Q replaces CH in Army operator text, so both
        # are far commoner here than in ordinary German prose.
        self.assertGreater(probabilities["X"], 0.04)
        self.assertGreater(probabilities["Q"], 0.01)
        self.assertEqual(max(probabilities, key=probabilities.__getitem__), "E")
        for letter in ALPHABET:
            self.assertGreater(probabilities[letter], 0.0)

    def test_absence_surprisal_grows_with_the_rarity_of_what_is_missing(self) -> None:
        probabilities = self.reference["probabilities"]
        missing_common = "".join(c for c in ALPHABET if c != "E") * 4
        missing_rare = "".join(c for c in ALPHABET if c != "J") * 4
        self.assertGreater(
            absence_surprisal(missing_common, probabilities),
            absence_surprisal(missing_rare, probabilities),
        )
        self.assertEqual(absence_surprisal(ALPHABET, probabilities), 0.0)

    def test_chi_square_is_zero_for_the_reference_itself(self) -> None:
        probabilities = {letter: 1 / 26 for letter in ALPHABET}
        self.assertAlmostEqual(reference_chi_square(ALPHABET, probabilities), 0.0)

    def test_gate_passes_every_known_true_transposition(self) -> None:
        """A gate that excludes a real transposition is measuring the wrong thing."""
        calibration = calibrate_conservation_gate(
            self.reference,
            self.controls,
            simulations=400,
            seed=20260921,
            alpha=0.01,
        )
        self.assertTrue(calibration["calibrated"], calibration["failures"])
        self.assertEqual(calibration["failures"], [])
        self.assertGreater(calibration["margin_over_alpha"], 1.0)

    def test_gate_excludes_qtxma(self) -> None:
        corpus = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))
        target = next(
            m for m in corpus["messages"] if m["designator"] == "QTXMA"
        )
        result = analyze_ciphertext(
            target["ciphertext"],
            simulations=400,
            seed=20260921,
            label="QTXMA",
            unigram_reference=self.reference,
        )
        conservation = result["plaintext_conservation"]
        # D and U are common Army plaintext letters that QTXMA never uses, and
        # no reordering of a plaintext can remove a letter from it.
        self.assertIn("D", conservation["absences"]["absent_letters"])
        self.assertIn("U", conservation["absences"]["absent_letters"])
        self.assertFalse(result["signals"]["plaintext_unigram_compatible"])
        self.assertTrue(result["signals"]["ic_elevated"])
        self.assertFalse(result["signals"]["frequency_preserving"])
        self.assertEqual(
            route_message(result["signals"]), "non_plaintext_alphabet_substitution"
        )

    def test_closing_the_gate_does_not_make_a_message_look_random(self) -> None:
        """QTXMA departs from uniform whether or not the gate reroutes it."""
        corpus = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))
        target = next(
            m for m in corpus["messages"] if m["designator"] == "QTXMA"
        )
        result = analyze_ciphertext(
            target["ciphertext"],
            simulations=400,
            seed=20260921,
            label="QTXMA",
            unigram_reference=self.reference,
        )
        self.assertFalse(result["signals"]["uniform_random_compatible"])

    def test_suspended_gate_restores_pre_gate_routing(self) -> None:
        corpus = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))
        target = next(
            m for m in corpus["messages"] if m["designator"] == "QTXMA"
        )
        result = analyze_ciphertext(
            target["ciphertext"],
            simulations=400,
            seed=20260921,
            label="QTXMA",
            unigram_reference=self.reference,
        )
        suspended = apply_conservation_gate(result, False)
        self.assertFalse(suspended["plaintext_conservation"]["gate"]["applied"])
        self.assertTrue(suspended["signals"]["frequency_preserving"])
        self.assertEqual(
            route_message(suspended["signals"]), "frequency_preserving_manual"
        )
        # The measurement survives the suspension; only its effect is withdrawn.
        self.assertLess(
            suspended["plaintext_conservation"]["p_values"][
                "reference_chi_square_upper"
            ],
            0.01,
        )


class Phase5StatisticTests(unittest.TestCase):
    def test_unknowns_are_excluded_without_changing_positions(self) -> None:
        self.assertEqual(index_of_coincidence("AAAA?"), 1.0)
        profile = periodic_ic_profile("AB?AAB?A", max_period=4)
        self.assertEqual([item["period"] for item in profile], [2, 3, 4])
        self.assertEqual(repeated_ngram_pairs("ABC?ABCABC", 3), 3)

    def test_frequency_preserving_signal_is_detected(self) -> None:
        """Army-like monograms must both raise IC and clear the conservation gate."""
        reference = load_army_unigrams()
        rng = random.Random(7)
        weights = [reference["probabilities"][letter] for letter in ALPHABET]
        text = "".join(rng.choices(ALPHABET, weights=weights, k=1200))
        result = analyze_ciphertext(
            text,
            simulations=199,
            seed=11,
            label="frequency-test",
            max_period=12,
            max_lag=12,
            alpha=0.02,
            unigram_reference=reference,
        )
        self.assertTrue(result["signals"]["ic_elevated"])
        self.assertTrue(result["signals"]["plaintext_unigram_compatible"])
        self.assertTrue(result["signals"]["frequency_preserving"])

    def test_newspaper_german_is_not_army_plaintext(self) -> None:
        """The gate must reject ordinary German: Army text is full of X and Q."""
        rng = random.Random(7)
        text = "".join(rng.choices(ALPHABET, weights=GERMAN_WEIGHTS, k=1200))
        result = analyze_ciphertext(
            text,
            simulations=199,
            seed=11,
            label="newspaper-german",
            max_period=12,
            max_lag=12,
            alpha=0.02,
        )
        self.assertTrue(result["signals"]["ic_elevated"])
        self.assertFalse(result["signals"]["plaintext_unigram_compatible"])
        self.assertFalse(result["signals"]["frequency_preserving"])

    def test_high_ic_shuffle_does_not_create_structural_signals(self) -> None:
        rng = random.Random(29)
        text = list("A" * 240 + "B" * 160 + "C" * 100 + "D" * 60 + "E" * 40)
        rng.shuffle(text)
        result = analyze_ciphertext(
            "".join(text),
            simulations=499,
            seed=31,
            label="conditional-null-regression",
            max_period=12,
            max_lag=12,
            alpha=0.02,
        )
        # A five-letter alphabet raises IC without being plaintext.  This is the
        # exact confusion the gate exists to prevent, so the raw signal fires
        # and the gated one does not.
        self.assertTrue(result["signals"]["ic_elevated"])
        self.assertFalse(result["signals"]["plaintext_unigram_compatible"])
        self.assertFalse(result["signals"]["frequency_preserving"])
        self.assertFalse(result["signals"]["periodic_structure"])
        self.assertFalse(result["signals"]["lag_structure"])
        self.assertFalse(result["signals"]["repeated_blocks"])
        self.assertFalse(result["signals"]["uniform_random_compatible"])
        self.assertEqual(
            result["conditional_permutation_null"]["condition"],
            "exact observed known-letter multiset",
        )

    def test_periodic_polyalphabetic_signal_is_detected(self) -> None:
        rng = random.Random(17)
        plaintext = rng.choices(ALPHABET, weights=GERMAN_WEIGHTS, k=1600)
        shifts = (0, 5, 11, 17, 22)
        ciphertext = "".join(
            ALPHABET[(ALPHABET.index(character) + shifts[index % len(shifts)]) % 26]
            for index, character in enumerate(plaintext)
        )
        result = analyze_ciphertext(
            ciphertext,
            simulations=199,
            seed=19,
            label="periodic-test",
            max_period=12,
            max_lag=12,
            alpha=0.02,
        )
        self.assertTrue(result["signals"]["periodic_structure"])
        self.assertEqual(result["statistics"]["best_period"]["period"], 5)


class Phase5ArtifactTests(unittest.TestCase):
    def test_catalog_has_resolved_source_references(self) -> None:
        catalog = load_family_catalog(DEFAULT_CATALOG)
        self.assertEqual(catalog["schema"], "enigma-attack.phase5-cipher-families/v1")
        self.assertGreaterEqual(len(catalog["families"]), 5)

    def test_artifact_preserves_scope_and_routes_every_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "phase5.json"
            args = argparse.Namespace(
                corpus=DEFAULT_CORPUS,
                catalog=DEFAULT_CATALOG,
                output=output,
                simulations=49,
                seed=23,
                max_period=12,
                max_lag=12,
                alpha=0.05,
                unigram_source=DEFAULT_UNIGRAM_SOURCE,
                control_plaintexts=DEFAULT_CONTROL_PLAINTEXTS,
                concentration=UNIGRAM_NULL_CONCENTRATION,
            )
            artifact = build_artifact(args)
            output.write_text(json.dumps(artifact), encoding="utf-8")
        self.assertEqual(artifact["schema"], "enigma-attack.phase5-model-triage/v3")
        self.assertEqual(len(artifact["messages"]), 5)
        self.assertFalse(artifact["decision"]["accepted_break"])
        self.assertEqual(
            {message["designator"] for message in artifact["messages"]},
            {"QTXMA", "SZAEJ", "BYQMZ", "FKQLZ", "XFEDT"},
        )
        self.assertTrue(all(message["family_assessments"] for message in artifact["messages"]))
        self.assertIn("conservation_gate_calibration", artifact)
        self.assertIn(
            "unigram_reference_sha256", artifact["inputs"]
        )

    def test_artifact_records_the_conservation_exclusion(self) -> None:
        artifact = json.loads(
            (
                pathlib.Path(__file__).resolve().parents[1]
                / "artifacts"
                / "phase5-model-triage.json"
            ).read_text(encoding="utf-8")
        )
        calibration = artifact["conservation_gate_calibration"]
        self.assertTrue(calibration["calibrated"])
        self.assertEqual(calibration["failures"], [])
        exclusions = artifact["decision"]["conservation_exclusions"]
        self.assertTrue(exclusions["gate_applied"])
        self.assertIn("QTXMA", exclusions["routing_changed_by_gate"])
        qtxma = next(
            m for m in artifact["messages"] if m["designator"] == "QTXMA"
        )
        self.assertEqual(qtxma["route"], "non_plaintext_alphabet_substitution")
        transposition = next(
            f
            for f in qtxma["family_assessments"]
            if f["family_id"] == "double-transposition"
        )
        self.assertEqual(transposition["status"], "excluded_by_conservation")


if __name__ == "__main__":
    unittest.main()
