import argparse
import json
import pathlib
import random
import tempfile
import unittest

from phase5 import (
    DEFAULT_CATALOG,
    DEFAULT_CORPUS,
    analyze_ciphertext,
    build_artifact,
    index_of_coincidence,
    load_family_catalog,
    periodic_ic_profile,
    repeated_ngram_pairs,
)


GERMAN_WEIGHTS = [
    0.0651, 0.0189, 0.0306, 0.0508, 0.1740, 0.0166, 0.0301,
    0.0476, 0.0755, 0.0027, 0.0121, 0.0344, 0.0253, 0.0978,
    0.0251, 0.0079, 0.0002, 0.0700, 0.0727, 0.0615, 0.0435,
    0.0067, 0.0189, 0.0003, 0.0004, 0.0113,
]
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Phase5StatisticTests(unittest.TestCase):
    def test_unknowns_are_excluded_without_changing_positions(self) -> None:
        self.assertEqual(index_of_coincidence("AAAA?"), 1.0)
        profile = periodic_ic_profile("AB?AAB?A", max_period=4)
        self.assertEqual([item["period"] for item in profile], [2, 3, 4])
        self.assertEqual(repeated_ngram_pairs("ABC?ABCABC", 3), 3)

    def test_frequency_preserving_signal_is_detected(self) -> None:
        rng = random.Random(7)
        text = "".join(rng.choices(ALPHABET, weights=GERMAN_WEIGHTS, k=1200))
        result = analyze_ciphertext(
            text,
            simulations=199,
            seed=11,
            label="frequency-test",
            max_period=12,
            max_lag=12,
            alpha=0.02,
        )
        self.assertTrue(result["signals"]["frequency_preserving"])

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
        self.assertTrue(result["signals"]["frequency_preserving"])
        self.assertFalse(result["signals"]["periodic_structure"])
        self.assertFalse(result["signals"]["lag_structure"])
        self.assertFalse(result["signals"]["repeated_blocks"])
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
            )
            artifact = build_artifact(args)
            output.write_text(json.dumps(artifact), encoding="utf-8")
        self.assertEqual(artifact["schema"], "enigma-attack.phase5-model-triage/v2")
        self.assertEqual(len(artifact["messages"]), 5)
        self.assertFalse(artifact["decision"]["accepted_break"])
        self.assertEqual(
            {message["designator"] for message in artifact["messages"]},
            {"QTXMA", "SZAEJ", "BYQMZ", "FKQLZ", "XFEDT"},
        )
        self.assertTrue(all(message["family_assessments"] for message in artifact["messages"]))


if __name__ == "__main__":
    unittest.main()
