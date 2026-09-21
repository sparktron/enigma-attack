import unittest

from enigma import EnigmaI, plugmap


class EnigmaTests(unittest.TestCase):
    def test_canonical_vector(self):
        machine = EnigmaI(rotors=("I", "II", "III"), rings="AAA", positions="AAA")
        self.assertEqual(machine.crypt("AAAAA"), "BDZGO")

    def test_py_enigma_army_procedure_vector(self):
        settings = {
            "rotors": ("II", "IV", "V"),
            "rings": "BUL",
            "plugboard": "AV BS CG DL FU HZ IN KM OW RX",
        }
        self.assertEqual(EnigmaI(positions="WXC", **settings).crypt("KCH"), "BLA")
        self.assertEqual(
            EnigmaI(positions="BLA", **settings).crypt("NIBLFMYMLLUFWCASCSSNVHAZ"),
            "THEXRUSSIANSXAREXCOMINGX",
        )

    def test_middle_rotor_double_steps(self):
        machine = EnigmaI(rotors=("I", "II", "III"), positions="ADU")
        machine.key("A")
        self.assertEqual(machine.positions, "ADV")
        machine.key("A")
        self.assertEqual(machine.positions, "AEW")
        machine.key("A")
        self.assertEqual(machine.positions, "BFX")

    def test_reciprocity(self):
        settings = {
            "rotors": ("II", "V", "III"),
            "rings": "HMF",
            "positions": "RWD",
            "plugboard": "AC BE DG FH KN MO PR SU TV XZ",
        }
        plaintext = "DIESISTEINTEST"
        ciphertext = EnigmaI(**settings).crypt(plaintext)
        self.assertEqual(EnigmaI(**settings).crypt(ciphertext), plaintext)

    def test_plugboard_must_be_an_involution(self):
        with self.assertRaisesRegex(ValueError, "reused"):
            plugmap("AB AC")
        with self.assertRaisesRegex(ValueError, "itself"):
            plugmap("AA")

    def test_rotors_must_be_distinct(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            EnigmaI(rotors=("I", "I", "III"))


if __name__ == "__main__":
    unittest.main()
