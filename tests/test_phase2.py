import json
import pathlib
import tempfile
import unittest

from phase2 import (
    build_archive_queries,
    build_artifact,
    build_network,
    load_crib_catalog,
    load_messages,
    main,
    rank_cribs,
    valid_crib_offsets,
)


class Phase2Tests(unittest.TestCase):
    def test_enriched_metadata_preserves_header_and_form_times(self):
        messages = {message.designator: message for message in load_messages()}
        self.assertEqual(messages["QTXMA"].form_time, "22:50")
        self.assertEqual(messages["QTXMA"].header_time, "22:40")
        self.assertEqual(messages["FKQLZ"].sender, "ugn")

    def test_network_links_all_five_messages_without_claiming_same_key(self):
        network = build_network(load_messages())
        self.assertEqual(len(network["clusters"]), 1)
        self.assertEqual(
            network["clusters"][0]["messages"],
            ["BYQMZ", "FKQLZ", "QTXMA", "SZAEJ", "XFEDT"],
        )
        transition = next(
            edge
            for edge in network["edges"]
            if edge["source"] == "BYQMZ" and edge["target"] == "FKQLZ"
        )
        self.assertIn(
            "recipient_to_later_sender",
            {signal["kind"] for signal in transition["signals"]},
        )

    def test_no_self_encryption_precheck(self):
        self.assertEqual(valid_crib_offsets("ABCDEF", "BCD"), [0, 2, 3])
        self.assertEqual(valid_crib_offsets("?CD", "ABC"), [0])

    def test_factual_cribs_have_sources_and_disabled_items_are_separate(self):
        catalog = load_crib_catalog()
        sources = {source["id"] for source in catalog["sources"]}
        for crib in catalog["cribs"]:
            if crib["evidence_level"] == "fact":
                self.assertIn(crib["source_id"], sources)
                self.assertTrue(crib["enabled_by_default"])
        self.assertTrue(
            all(
                crib["evidence_level"] == "fact"
                for crib in catalog["cribs"]
                if crib["enabled_by_default"]
            )
        )

    def test_ranked_offsets_all_pass_the_precheck(self):
        message = next(item for item in load_messages() if item.designator == "BYQMZ")
        catalog = load_crib_catalog()
        for row in rank_cribs(message, catalog):
            for offset in row["valid_offsets_1_based"]:
                window = message.ciphertext[offset - 1 : offset - 1 + len(row["text"])]
                self.assertTrue(
                    all(
                        cipher == "?" or cipher != plain
                        for cipher, plain in zip(window, row["text"])
                    )
                )

    def test_archive_queries_prioritize_callsign_chain(self):
        queries = build_archive_queries(load_messages())
        callsign = next(row for row in queries if "callsign ugn" in row["query"])
        self.assertEqual(callsign["priority"], "high")
        self.assertEqual(callsign["basis"], ["BYQMZ", "FKQLZ"])

    def test_artifact_keeps_status_discrepancy_as_inference(self):
        artifact = build_artifact(
            pathlib.Path("corpus.json").resolve(),
            pathlib.Path("cribs.json").resolve(),
            top=3,
            include_disabled=False,
        )
        discrepancy = " ".join(artifact["evidence_separation"]["inferences"])
        self.assertIn("not proof", discrepancy)
        self.assertEqual(
            artifact["crib_ranking"]["method"]["include_disabled"], False
        )

    def test_cli_writes_phase2_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "phase2.json"
            self.assertEqual(main(["--top", "2", "--output", str(output)]), 0)
            artifact = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema"], "enigma-attack.phase2-network-cribs/v1")
            self.assertEqual(
                len(artifact["crib_ranking"]["by_message"]["BYQMZ"]), 2
            )


if __name__ == "__main__":
    unittest.main()
