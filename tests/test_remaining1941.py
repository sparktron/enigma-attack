import copy
import json
import unittest

from enigma import EnigmaI
from remaining1941_inventory import build, normalize
from remaining1941_pilot import DEFAULT, historical_allowed, masked_crypt, verify


class Remaining1941Tests(unittest.TestCase):
    def test_inventory_counts_positions_instead_of_trusting_header(self):
        inventory = build()
        rx = next(m for m in inventory["messages"] if m["id"] == "RXPSB")
        self.assertEqual((rx["declared_total_in_header"],rx["total_positions"],rx["body_positions"],rx["legible_letters"]),(114,112,107,105))
        self.assertEqual(rx["erasure_positions_1based"],[18,104])
        self.assertEqual(set(inventory["unresolved"]),{"EHSTQ","RXPSB","KLJBO","LXACA"})
        self.assertFalse(set(inventory["excluded"]) & {m["id"] for m in inventory["messages"]})

    def test_erasure_steps_and_roundtrips_with_independent_machine(self):
        key = dict(rotors=["I","II","III"],rings="XYZ",plugboard="AB CD EF GH IJ KL MN OP QR ST")
        clear = "A"*107
        encrypted=EnigmaI(rotors=key["rotors"],rings=key["rings"],positions="ADV",plugboard=key["plugboard"]).crypt(clear)
        masked=encrypted[:17]+"?"+encrypted[18:103]+"?"+encrypted[104:]
        recovered=masked_crypt(key,"ADV",masked)
        self.assertEqual(recovered,clear[:17]+"?"+clear[18:103]+"?"+clear[104:])
        self.assertEqual(recovered,masked_crypt(key,"ADV",masked,True))
        encoded=EnigmaI(rotors=key["rotors"],rings=key["rings"],positions="XYZ",plugboard=key["plugboard"]).crypt("ADV")
        result=verify(key,"ADV",masked,["XYZ",encoded],recovered)
        self.assertTrue(result["indicator_matches"])
        self.assertTrue(result["complete_observed_ciphertext_matches"])
        result=verify(key,"ADV",masked,["XYZ",encoded],"B"+recovered[1:])
        self.assertFalse(result["complete_observed_ciphertext_matches"])

    def test_failed_control_blocks_historical_gate(self):
        cfg=json.loads(DEFAULT.read_text())
        checks=dict(kernel=True,independent=True,batched_reference=True)
        self.assertTrue(historical_allowed(checks,4,4,cfg))
        for name in checks:
            broken={**checks,name:False}
            self.assertFalse(historical_allowed(broken,4,24,cfg))
        self.assertFalse(historical_allowed(checks,3,24,cfg))
        self.assertFalse(historical_allowed(checks,4,3,cfg))

    def test_unknowns_cannot_be_silently_deleted(self):
        self.assertEqual(normalize("AB-CD EF"),"AB?CDEF")
        with self.assertRaises(ValueError):
            normalize("AB1CD")
