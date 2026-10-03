import json
import pathlib
import tempfile
import unittest
from unittest import mock

import phase1
from phase1 import (
    ArmyGermanScorer,
    CorpusMessage,
    decrypt_with_army_procedure,
    load_corpus,
    main,
    published_vector_results,
    standard_rotor_orders,
)


class Phase1Tests(unittest.TestCase):
    def test_published_vectors_pass(self):
        self.assertTrue(all(row["passed"] for row in published_vector_results()))

    def test_documented_army_message_procedure(self):
        message = CorpusMessage(
            date="1941-01-01",
            designator="TEST",
            grundstellung="WXC",
            encrypted_message_key="KCH",
            ciphertext="NIBLFMYMLLUFWCASCSSNVHAZ",
        )
        key, plaintext = decrypt_with_army_procedure(
            message,
            rotors=("II", "IV", "V"),
            rings="BUL",
            plugboard="AV BS CG DL FU HZ IN KM OW RX",
        )
        self.assertEqual(key, "BLA")
        self.assertEqual(plaintext, "THEXRUSSIANSXAREXCOMINGX")

    def test_corpus_preserves_uncertainty(self):
        messages = load_corpus()
        self.assertEqual(len(messages), 5)
        by_name = {message.designator: message for message in messages}
        self.assertEqual(by_name["BYQMZ"].ciphertext.count("?"), 1)
        self.assertEqual(sum(len(message.ciphertext) for message in messages), 577)

    def test_standard_rotor_orders_cover_i_through_v(self):
        orders = list(standard_rotor_orders())
        self.assertEqual(len(orders), 60)
        self.assertEqual(len(set(orders)), 60)

    def test_bootstrap_scorer_prefers_german_like_raw_text(self):
        scorer = ArmyGermanScorer()
        german, german_length = scorer.score("DIESISTEINTESTXDERANGRIFFISTIMNORDENX")
        noise, noise_length = scorer.score("QJYVPKZWOXQJYVPKZWOXQJYVPKZWOXQJYVPKZ")
        self.assertGreater(german / german_length, noise / noise_length)

    def test_restricted_search_writes_an_exact_scope_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "certificate.json"
            result = main(
                [
                    "search",
                    "--message",
                    "SZAEJ",
                    "--rotor-order",
                    "I-II-III",
                    "--rings",
                    "AAA",
                    "--top",
                    "1",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(result, 0)
            certificate = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(certificate["counts"]["evaluated_daily_keys"], 1)
            self.assertEqual(certificate["counts"]["evaluated_message_decryptions"], 1)
            self.assertFalse(certificate["result"]["full_phase_1_negative_result"])
            self.assertEqual(certificate["search_space"]["messages"], ["SZAEJ"])

    def test_code_provenance_is_captured_before_the_search_runs(self):
        # A long search can outlast an edit to the checkout; the record must
        # describe the code the search started from, not what is on disk at
        # the end.
        calls = []
        real_search = phase1._search_date

        def search(*args, **kwargs):
            calls.append("search")
            return real_search(*args, **kwargs)

        def version():
            calls.append("code_version")
            return {"sentinel": True}

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            phase1, "_search_date", search
        ), mock.patch.object(phase1, "code_version", version):
            output = pathlib.Path(directory) / "certificate.json"
            main(["search", "--message", "SZAEJ", "--rotor-order", "I-II-III",
                  "--rings", "AAA", "--top", "1", "--output", str(output)])
            certificate = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(calls[0], "code_version")
        self.assertEqual(calls.count("code_version"), 1)
        self.assertEqual(certificate["implementation"]["code"], {"sentinel": True})


if __name__ == "__main__":
    unittest.main()
