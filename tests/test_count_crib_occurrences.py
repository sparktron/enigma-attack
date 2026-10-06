"""Position classes reported by scripts/count_crib_occurrences.py."""

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "count_crib_occurrences.py"
SPEC = importlib.util.spec_from_file_location("count_crib_occurrences", SCRIPT)
counting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(counting)


class ClassifyTest(unittest.TestCase):
    def test_opening_sign_off_and_other(self):
        text = "ABENDMELDUNGXHARTJENSTEIN"
        self.assertEqual(counting.classify(text, 0, 5), "opening")
        self.assertEqual(counting.classify(text, 13, 12), "sign_off")
        self.assertEqual(counting.classify(text, 5, 7), "other")

    def test_sign_off_before_one_trailing_x(self):
        text = "UNTERWEGSXSCHNEIDDRX"
        self.assertEqual(counting.classify(text, 10, 9), "sign_off")

    def test_annotated_address_block_is_classed_as_address(self):
        text = "ANGRUPPEVONPANZERXVONABTXLAGEUNVERAENDERTXHARTJENSTEIN"
        end = 24  # the address block is letters 0-23, as annotated
        # Inside the annotated block, including at offset 0.
        self.assertEqual(counting.classify(text, 0, 8, end), "address")
        self.assertEqual(counting.classify(text, 21, 3, end), "address")
        # Body and sign-off are unaffected.
        self.assertEqual(counting.classify(text, 25, 4, end), "other")
        self.assertEqual(counting.classify(text, 42, 12, end), "sign_off")

    def test_no_address_without_annotation(self):
        # Spelling alone cannot tell AN GRUPPE from ANGRIFF, so nothing is
        # classed as address unless the message carries address_end.
        text = "ANGRIFFAUFHOEHEXMELDUNGFOLGT"
        self.assertEqual(counting.classify(text, 0, 7), "opening")

    def test_occurrence_straddling_the_address_block_is_not_address(self):
        text = "ANABTXLAGEXHARTJENSTEIN"
        self.assertEqual(counting.classify(text, 2, 5, 6), "other")

    def test_address_count_and_annotation_coverage_reach_the_output(self):
        result = counting.count(
            [
                {"id": "a", "raw": "ANABTEINSXLAGEXHARTJENSTEIN", "address_end": 10},
                {"id": "b", "raw": "LAGEXABTEINSXHARTJENSTEIN"},
            ],
            [{"id": "c", "text": "ABTEINS", "evidence_level": "fact"}],
        )
        self.assertEqual(result["messages_with_address_annotation"], 1)
        classes = result["cribs"][0]["by_variant"]["ABTEINS"]["occurrences_by_class"]
        self.assertEqual(classes["address"], 1)
        self.assertEqual(classes["other"], 1)

    def test_address_end_outside_the_message_is_rejected(self):
        with self.assertRaises(ValueError):
            counting.count(
                [{"id": "a", "raw": "ANABTXLAGE", "address_end": 11}],
                [{"id": "c", "text": "LAGE", "evidence_level": "fact"}],
            )


if __name__ == "__main__":
    unittest.main()
