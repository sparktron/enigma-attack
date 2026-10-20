import json
import pathlib
import unittest

from enigma import EnigmaI

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEYED = ROOT / "data" / "historical" / "keyed-messages.json"


def decipher(message: dict) -> str:
    machine = EnigmaI(
        rotors=message["rotors"],
        rings=message["rings"],
        positions=message["start_position"],
        plugboard=message["plugboard"],
        reflector=message["reflector"],
    )
    out = []
    for c in message["ciphertext"]:
        if c == "-":
            # An illegible letter on the form: the machine still stepped.
            machine.step()
            out.append("-")
        else:
            out.append(machine.key(c))
    return "".join(out)


class HistoricalMessageTests(unittest.TestCase):
    """Real 1941 Army traffic, deciphered under its recovered key."""

    @classmethod
    def setUpClass(cls):
        cls.messages = json.loads(KEYED.read_text(encoding="utf-8"))["messages"]

    def test_corpus_is_the_articles_thirteen_messages(self):
        self.assertEqual(len(self.messages), 13)
        self.assertEqual(len({m["id"] for m in self.messages}), 13)

    def test_each_message_deciphers_to_its_published_raw_plaintext(self):
        for message in self.messages:
            with self.subTest(message["id"]):
                self.assertEqual(len(message["ciphertext"]), len(message["raw_plaintext"]))
                self.assertEqual(decipher(message), message["raw_plaintext"])

    def test_corrected_start_position_is_recorded_against_the_published_one(self):
        message = next(m for m in self.messages if m["id"] == "1941-10-01-2")
        self.assertEqual(message["start_position_as_published"], "DEI")
        published = dict(message, start_position="DEI")
        self.assertNotEqual(decipher(published), message["raw_plaintext"])

    def test_raw_plaintexts_agree_with_the_other_copies_of_this_source(self):
        copies = {}
        for path in (
            ROOT / "data" / "phase2" / "held-out-plaintexts.json",
            ROOT / "data" / "phase5" / "army-plaintext-controls.json",
        ):
            for entry in json.loads(path.read_text(encoding="utf-8"))["plaintexts"]:
                copies[entry["id"]] = entry["raw"]
        self.assertEqual(
            {m["id"]: m["raw_plaintext"] for m in self.messages}, copies
        )


if __name__ == "__main__":
    unittest.main()
