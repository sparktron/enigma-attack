import unittest

from enigma import EnigmaI
import enigma_fast


class KernelParityTests(unittest.TestCase):
    def test_parity_report_passes_on_pseudorandom_settings(self):
        report = enigma_fast.parity_report(20260923, 40)
        self.assertTrue(report["passed"], report["mismatches"][:2])
        self.assertEqual(report["samples"], 40)

    def test_direct_kernel_matches_published_vector(self):
        order = [enigma_fast.rotor_tables(name) for name in ("I", "II", "III")]
        output = enigma_fast.crypt_indices(
            order, (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices("AAAAA")
        )
        self.assertEqual(enigma_fast.indices_to_text(output), "BDZGO")

    def test_precomputed_tables_match_the_direct_kernel(self):
        order = [enigma_fast.rotor_tables(name) for name in ("II", "IV", "V")]
        rings = (1, 20, 11)
        start = (22, 23, 2)
        plugboard = enigma_fast.plugboard_table("AV BS CG DL FU HZ IN KM OW RX")
        data = enigma_fast.text_to_indices("NIBLFMYMLLUFWCASCSSNVHAZ" * 4)
        direct = enigma_fast.crypt_indices(order, rings, start, data, plugboard)
        table = enigma_fast.position_permutations(order, rings, start, len(data))
        self.assertEqual(
            direct, enigma_fast.decrypt_with_tables(table, data, plugboard)
        )

    def test_uncertain_character_steps_the_machine_without_producing_output(self):
        order = [enigma_fast.rotor_tables(name) for name in ("I", "II", "III")]
        masked = enigma_fast.crypt_indices(
            order, (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices("A?AAA")
        )
        clean = enigma_fast.crypt_indices(
            order, (0, 0, 0), (0, 0, 0), enigma_fast.text_to_indices("AAAAA")
        )
        self.assertEqual(masked[1], -1)
        self.assertEqual([masked[0], *masked[2:]], [clean[0], *clean[2:]])

    def test_plugboard_round_trips_through_its_pair_rendering(self):
        pairs = "AV BS CG DL FU HZ IN KM OW RX"
        self.assertEqual(
            enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(pairs)), pairs
        )

    def test_plugboard_rejects_reused_and_self_paired_letters(self):
        with self.assertRaises(ValueError):
            enigma_fast.plugboard_table("AB AC")
        with self.assertRaises(ValueError):
            enigma_fast.plugboard_table("AA")

    def test_date_counts_match_the_reference_army_procedure(self):
        import phase1

        message = phase1.CorpusMessage(
            date="1941-01-01",
            designator="TEST",
            grundstellung="WXC",
            encrypted_message_key="KCH",
            ciphertext="NIBLFMYMLLUFWCASCSSNVHAZ",
        )
        key, plaintext = phase1.decrypt_with_army_procedure(
            message, rotors=("II", "IV", "V"), rings="BUL"
        )
        counts = [0] * 26
        recovered = enigma_fast.unsteckered_date_counts(
            [enigma_fast.rotor_tables(name) for name in ("II", "IV", "V")],
            (1, 20, 11),
            [
                (
                    enigma_fast.text_to_indices("WXC"),
                    enigma_fast.text_to_indices("KCH"),
                    enigma_fast.text_to_indices(message.ciphertext),
                )
            ],
            enigma_fast.reflector_table("B"),
            counts,
        )
        expected = [0] * 26
        for letter in plaintext:
            expected[ord(letter) - 65] += 1
        self.assertEqual("".join(chr(65 + v) for v in recovered[0]), key)
        self.assertEqual(counts, expected)

    def test_kernel_agrees_with_the_reference_on_a_steckered_message(self):
        expected = EnigmaI(
            rotors=("V", "I", "III"),
            rings="QEV",
            positions="LDP",
            plugboard="BQ CR DI EJ KW MT OS PX UZ GH",
        ).crypt("DIESISTEINTESTXDERANGRIFFISTIMNORDENX")
        order = [enigma_fast.rotor_tables(name) for name in ("V", "I", "III")]
        actual = enigma_fast.crypt_indices(
            order,
            (16, 4, 21),
            (11, 3, 15),
            enigma_fast.text_to_indices("DIESISTEINTESTXDERANGRIFFISTIMNORDENX"),
            enigma_fast.plugboard_table("BQ CR DI EJ KW MT OS PX UZ GH"),
        )
        self.assertEqual(enigma_fast.indices_to_text(actual), expected)


if __name__ == "__main__":
    unittest.main()
