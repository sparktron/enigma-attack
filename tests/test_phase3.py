import json
import pathlib
import tempfile
import unittest

from enigma import EnigmaI, EnigmaMachine, Rotor
from phase1 import standard_rotor_orders
from phase3 import DEFAULT_CATALOG, load_variant_catalog, main


class ConfigurableMachineTests(unittest.TestCase):
    def test_generic_machine_preserves_standard_vector(self) -> None:
        generic = EnigmaMachine(("I", "II", "III"))
        wrapped = EnigmaI(("I", "II", "III"))
        self.assertEqual(generic.crypt("AAAAA"), "BDZGO")
        self.assertEqual(wrapped.crypt("AAAAA"), "BDZGO")

    def test_double_notch_rotor_recognizes_both_turnovers(self) -> None:
        self.assertTrue(Rotor("VI", pos="Z").at_notch())
        self.assertTrue(Rotor("VI", pos="M").at_notch())
        self.assertFalse(Rotor("VI", pos="A").at_notch())

    def test_alternate_entry_and_settable_reflector_remain_reciprocal(self) -> None:
        _, profiles = load_variant_catalog()
        railway = next(profile for profile in profiles if profile.id == "railway_enigma")
        config = {
            "rotors": ("III", "I", "II"),
            "rings": "KCH",
            "positions": "RWD",
            "rotor_wirings": railway.rotor_wirings,
            "reflector": railway.reflector,
            "entry_wiring": railway.entry_wiring,
            "reflector_position": "M",
            "stepping": railway.stepping,
        }
        plaintext = "DIESISTEINREZIPROZITAETSTEST"
        ciphertext = EnigmaMachine(**config).crypt(plaintext)
        self.assertEqual(EnigmaMachine(**config).crypt(ciphertext), plaintext)

    def test_swiss_1941_stepping_moves_middle_left_and_reflector(self) -> None:
        _, profiles = load_variant_catalog()
        swiss = next(profile for profile in profiles if profile.id == "swiss_k_army_1941")
        machine = EnigmaMachine(
            ("I", "II", "III"),
            positions="YEA",
            rotor_wirings=swiss.rotor_wirings,
            reflector=swiss.reflector,
            entry_wiring=swiss.entry_wiring,
            stepping=swiss.stepping,
        )
        machine.step()
        self.assertEqual(machine.positions, "ZFA")
        self.assertEqual(machine.reflector_position, "B")

    def test_swiss_left_only_notch_advances_slow_wheel_once(self) -> None:
        _, profiles = load_variant_catalog()
        swiss = next(profile for profile in profiles if profile.id == "swiss_k_army_1941")
        machine = EnigmaMachine(
            ("I", "II", "III"), rings="BCA", positions="YAA",
            rotor_wirings=swiss.rotor_wirings, reflector=swiss.reflector,
            entry_wiring=swiss.entry_wiring, stepping=swiss.stepping,
        )
        states = []
        for _ in range(3):
            machine.step()
            states.append((machine.positions, machine.reflector_position))
        self.assertEqual(states, [("ZBA", "B"), ("ZCA", "B"), ("ZDA", "B")])


class VariantCatalogTests(unittest.TestCase):
    def test_catalog_is_valid_and_keeps_explicit_exclusions(self) -> None:
        payload, profiles = load_variant_catalog()
        self.assertEqual(len(profiles), 9)
        self.assertEqual(
            {entry["id"] for entry in payload["unsupported"]},
            {"abwehr_11_15_17", "abwehr_ggg_4j", "kriegsmarine_m4"},
        )
        tirpitz = next(profile for profile in profiles if profile.id == "tirpitz_t")
        self.assertFalse(tirpitz.enabled_by_default)
        self.assertEqual(tirpitz.historical_prior, "excluded")

    def test_phase1_default_stays_limited_to_service_rotors_i_v(self) -> None:
        orders = tuple(standard_rotor_orders())
        self.assertEqual(len(orders), 60)
        self.assertEqual(
            {rotor for order in orders for rotor in order},
            {"I", "II", "III", "IV", "V"},
        )

    def test_runner_writes_bounded_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "certificate.json"
            exit_code = main(
                [
                    "--catalog",
                    str(DEFAULT_CATALOG),
                    "--profile",
                    "railway_enigma",
                    "--keep",
                    "1",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(exit_code, 0)
            certificate = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(certificate["decision"]["accepted_break"])
        self.assertEqual(certificate["search"]["profiles"], ["railway_enigma"])
        self.assertEqual(certificate["results"][0]["rotor_order_count"], 6)
        self.assertIn("None.", certificate["decision"]["negative_claim"])


if __name__ == "__main__":
    unittest.main()
