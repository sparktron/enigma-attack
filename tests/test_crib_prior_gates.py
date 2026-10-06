"""Bounds, candidate rule and split of scripts/crib_prior_gates.py."""

import importlib.util
import math
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "crib_prior_gates.py"
SPEC = importlib.util.spec_from_file_location("crib_prior_gates", SCRIPT)
gates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gates)


class ClopperPearsonTest(unittest.TestCase):
    def test_one_of_two_lower_bound_has_a_closed_form(self):
        # P(X >= 1) = 1 - (1 - p)^2 = 0.2
        self.assertAlmostEqual(gates.lower_bound(1, 2, 0.2), 1 - math.sqrt(0.8), places=9)

    def test_zero_of_two_upper_bound_has_a_closed_form(self):
        # P(X <= 0) = (1 - p)^2 = 0.025
        self.assertAlmostEqual(gates.upper_bound(0, 2, 0.025), 1 - math.sqrt(0.025), places=9)

    def test_edges(self):
        self.assertEqual(gates.lower_bound(0, 5, 0.2), 0.0)
        self.assertEqual(gates.upper_bound(5, 5, 0.025), 1.0)
        self.assertAlmostEqual(gates.lower_bound(2, 2, 0.2), math.sqrt(0.2), places=9)


class CandidateRuleTest(unittest.TestCase):
    def row(self, raw, **extra):
        return dict({"id": raw[:4], "date": "1941-08-01", "raw": raw}, **extra)

    def test_tokens_by_class(self):
        found = gates.tokens_by_class(self.row("ANXPANZXGRUPPEXVIERXLAGEXKDRX", address_end=19))
        self.assertEqual(found["opening"], {"AN"})
        self.assertEqual(found["sign_off"], {"KDR"})
        self.assertEqual(found["address"], {"AN", "PANZ", "GRUPPE", "VIER"})

    def test_truncated_message_gives_no_sign_off(self):
        self.assertEqual(gates.tokens_by_class(self.row("ZWOXSTAFFEL", truncated=True))["sign_off"], set())

    def test_a_token_must_recur_in_two_messages(self):
        train = [self.row("EINSXLAGEXHARTJENSTEIN"), self.row("ZWOXLAGEXHARTJENSTEIN"), self.row("DREIXLAGEXSTEINECKE")]
        got = {(c["class"], c["text"]) for c in gates.candidates(train, []) if c["evidence_level"] == "train_recurring"}
        self.assertEqual(got, {("sign_off", "HARTJENSTEIN")})

    def test_split_dates_and_exclusions(self):
        rows = [
            {"id": "a", "date": "1941-09-15"}, {"id": "b", "date": "1941-09-16"},
            {"id": "c", "date": "1941-10-31"}, {"id": "d", "date": "1941-11-01"},
            {"id": "e", "date": "1941-09-20"},
        ]
        train, evaluate = gates.split(rows, {"e"})
        self.assertEqual([r["id"] for r in train], ["a"])
        self.assertEqual([r["id"] for r in evaluate], ["b", "c"])


if __name__ == "__main__":
    unittest.main()
