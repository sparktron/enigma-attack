import json
import pathlib
import tempfile
import unittest

import enigma_fast
import phase1_stecker as stecker
from enigma import EnigmaI
from stecker_climb import body_direct_climb, coincidence_of_decryption, run_climb_phases
from stecker_controls import (
    compatible_ring_settings,
    confirm_against_date,
    evaluate_positive_control,
)
from stecker_scoring import FastNgramScorer, index_of_coincidence, letter_counts
from stecker_sweeps import (
    body_direct_sweep,
    indicator_ic_sweep,
    resolve_axis,
    ring_space,
    rotor_order_space,
)
from stecker_traffic import (
    Traffic,
    encipher_control,
    normalize_plaintext,
    traffic_from_corpus,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CALIBRATION_CONFIG = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"
INDICATOR_CONFIG = ROOT / "experiments/phase1-indicator-sweep-v1/config.json"
BODY_CONFIG = ROOT / "experiments/phase1-body-direct-sweep-v1/config.json"


def scorer_for(config):
    return FastNgramScorer(config["scorer"])


class ScorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(CALIBRATION_CONFIG)
        cls.scorer = scorer_for(cls.config)

    def test_fast_scorer_matches_phase7_and_the_fused_path(self):
        report = self.scorer.parity_report(20260924, 60, 1e-09)
        self.assertTrue(report["passed"], report["mismatches"][:1])
        self.assertLess(report["worst_absolute_difference_vs_phase7"], 1e-06)
        self.assertLess(report["worst_absolute_difference_fused_vs_split"], 1e-09)

    def test_uncertainty_mask_removes_only_the_ngrams_that_contain_it(self):
        # Scores are log likelihoods, so dropping terms raises the total. What
        # matters is that exactly the n-grams spanning the mask disappear.
        clean = self.scorer.score_text("MELDUNG")
        masked = self.scorer.score_text("MEL?UNG")
        self.assertGreater(masked, clean)
        self.assertAlmostEqual(
            masked,
            self.scorer.score_text("MEL") + self.scorer.score_text("UNG"),
            places=12,
        )

    def test_scorer_prefers_army_plaintext_to_its_shuffle(self):
        text = "FUNKSTELLEMELDETXFEINDLICHEAUFKLAERERUEBERDEMABSCHNITTNORDX"
        shuffled = "XDRONTTINHCSBAMEDREBEUREREALKFUAEHCILDNIEFXTEDLEMELLETSKNUF"
        self.assertGreater(self.scorer.score_text(text), self.scorer.score_text(shuffled))


class ClimbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(CALIBRATION_CONFIG)
        cls.scorer = scorer_for(cls.config)
        cls.reflector = enigma_fast.reflector_table("B")

    def test_body_direct_climb_recovers_a_ten_pair_plugboard_exactly(self):
        plaintext = normalize_plaintext(
            self.config["climb_capability_calibration"]["plaintext"], 167
        )
        plugboard = "AV BS CG DL FU HZ IN KM OW RX"
        ciphertext = EnigmaI(
            rotors=("II", "V", "III"), rings="KQL", positions="BNM", plugboard=plugboard
        ).crypt(plaintext)
        message = Traffic(
            designator="T",
            first_trigram=(0, 0, 0),
            second_trigram=(0, 0, 0),
            body=enigma_fast.text_to_indices(ciphertext),
        )
        outcome, plaintexts = body_direct_climb(
            [message],
            ("II", "V", "III"),
            (10, 16, 11),
            [enigma_fast.text_to_indices("BNM")],
            self.scorer,
            self.reflector,
            self.config["climb"],
        )
        self.assertEqual(enigma_fast.plugboard_pairs(outcome.plugboard), plugboard)
        self.assertEqual(plaintexts[0], plaintext)

    def test_climb_runs_the_configured_objectives_in_order(self):
        calls = []

        def make(name):
            def objective(plugboard):
                calls.append(name)
                return -sum(1 for x in range(26) if plugboard[x] > x)

            return objective

        plugboard, records, evaluations = run_climb_phases(
            ["index_of_coincidence", "ngram"],
            {"index_of_coincidence": make("ic"), "ngram": make("ngram")},
            100,
            {"max_pairs": 2, "max_passes": 1, "minimum_gain": 1e-09},
        )
        self.assertEqual([record["objective"] for record in records],
                         ["index_of_coincidence", "ngram"])
        self.assertGreater(evaluations, 0)
        self.assertEqual(calls.index("ngram") > calls.index("ic"), True)
        self.assertEqual(plugboard, list(range(26)))

    def test_unknown_objective_is_rejected(self):
        with self.assertRaises(ValueError):
            run_climb_phases(
                ["chi_square"], {}, 10, {"max_pairs": 1, "max_passes": 1, "minimum_gain": 0.0}
            )

    def test_climb_never_exceeds_the_configured_pair_budget(self):
        plaintext = normalize_plaintext(
            self.config["climb_capability_calibration"]["plaintext"], 167
        )
        ciphertext = EnigmaI(
            rotors=("I", "II", "III"), rings="AAA", positions="AAA",
            plugboard="AB CD EF GH IJ KL MN OP QR ST",
        ).crypt(plaintext)
        message = Traffic(
            designator="T",
            first_trigram=(0, 0, 0),
            second_trigram=(0, 0, 0),
            body=enigma_fast.text_to_indices(ciphertext),
        )
        settings = dict(self.config["climb"])
        settings["max_pairs"] = 3
        outcome, _ = body_direct_climb(
            [message], ("I", "II", "III"), (0, 0, 0),
            [enigma_fast.text_to_indices("AAA")], self.scorer, self.reflector, settings,
        )
        self.assertLessEqual(outcome.pair_count, 3)

    def test_coincidence_of_decryption_matches_the_split_path(self):
        order = [enigma_fast.rotor_tables(name) for name in ("IV", "I", "V")]
        body = enigma_fast.text_to_indices("QWERTZUIOPASDFGHJKLYXCVBNM" * 4)
        plugboard = enigma_fast.plugboard_table("AN BY CF DR GJ")
        table = enigma_fast.position_permutations(order, (1, 20, 11), (5, 5, 5), len(body))
        counts, total = letter_counts(
            enigma_fast.decrypt_with_tables(table, body, plugboard)
        )
        self.assertAlmostEqual(
            coincidence_of_decryption(table, body, plugboard),
            index_of_coincidence(counts, total),
            places=12,
        )


class ControlAndTrafficTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(CALIBRATION_CONFIG)
        cls.scorer = scorer_for(cls.config)
        cls.reflector = enigma_fast.reflector_table("B")

    def test_control_ciphertext_comes_from_the_reference_machine(self):
        spec = self.config["positive_controls"][0]
        traffic, truth = encipher_control(spec)
        key = spec["key"]
        for message, record, plaintext in zip(
            traffic, truth["truth"]["messages"], truth["plaintexts"]
        ):
            expected = EnigmaI(
                rotors=tuple(key["rotor_order"]),
                rings=key["rings"],
                positions=record["true_message_key"],
                plugboard=key["plugboard"],
            ).crypt(plaintext)
            self.assertEqual(enigma_fast.indices_to_text(message.body), expected)

    def test_both_preregistered_controls_recover_their_keys_exactly(self):
        for spec in self.config["positive_controls"]:
            with self.subTest(control=spec["id"]):
                result = evaluate_positive_control(
                    spec, self.config, self.scorer, self.reflector
                )
                self.assertTrue(result["passed"], result["checks"])
                self.assertTrue(result["checks"]["indicator_confirms_message_keys"])

    def test_indicator_orderings_swap_the_two_trigrams(self):
        message = Traffic(
            designator="T",
            first_trigram=(0, 1, 2),
            second_trigram=(3, 4, 5),
            body=(0,),
        )
        first = message.oriented("grundstellung_first")
        second = message.oriented("message_key_first")
        self.assertEqual((first[0], first[1]), ((0, 1, 2), (3, 4, 5)))
        self.assertEqual((second[0], second[1]), ((3, 4, 5), (0, 1, 2)))

    def test_corpus_traffic_preserves_the_uncertainty_mask(self):
        traffic = traffic_from_corpus(
            ROOT / "corpus.json", "1941-09-30", ["BYQMZ", "FKQLZ", "XFEDT"]
        )
        byqmz = traffic[0]
        self.assertEqual(byqmz.designator, "BYQMZ")
        self.assertEqual(len(byqmz.body), 167)
        self.assertEqual(byqmz.letters, 166)
        self.assertEqual(sum(1 for value in byqmz.body if value < 0), 1)

    def test_traffic_rejects_a_message_from_another_date(self):
        with self.assertRaises(ValueError):
            traffic_from_corpus(ROOT / "corpus.json", "1941-09-30", ["QTXMA"])


class IndicatorConfirmationRingTests(unittest.TestCase):
    """The confirmation has to recover the rings the sweep absorbed.

    The body-direct sweep holds the ring setting and searches the start
    position, so a retained candidate fixes the left and middle wheels' offset
    and not their ring setting.  The indicator is enciphered at the clear
    Grundstellung, which has no such freedom, so a confirmation that reuses the
    held rings deciphers a daily key the sweep never proposed and can throw
    away a genuine hit.
    """

    RINGS = "BCA"
    PLUGBOARD = "AV BS CG DL FU HZ IN KM OW RX"
    SPEC = {
        "id": "ring-recovery",
        "key": {
            "rotor_order": ["II", "V", "III"],
            "rings": RINGS,
            "plugboard": PLUGBOARD,
        },
        "indicator_ordering": "grundstellung_first",
        "messages": [
            {
                "designator": "RR-1",
                "grundstellung": "QWE",
                "message_key": "BNM",
                "plaintext": "ABENDMELDUNGENENTFALLENXHARTJENSTEIN",
            },
            {
                "designator": "RR-2",
                "grundstellung": "LDR",
                "message_key": "KPT",
                "plaintext": "WOGEFEQTSSTANDQUARTIERMEISTERABTXROEMEINSBERTA",
            },
            {
                "designator": "RR-3",
                "grundstellung": "ZUI",
                "message_key": "VCX",
                "plaintext": "DIVXNAQRXYUEHRERNIQTANWWSENDXSTEINECKEXSTEINECKE",
            },
        ],
    }

    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(CALIBRATION_CONFIG)
        cls.scorer = scorer_for(cls.config)
        cls.reflector = enigma_fast.reflector_table("B")
        cls.traffic, cls.truth = encipher_control(cls.SPEC)
        cls.plugboard = enigma_fast.plugboard_table(cls.PLUGBOARD)
        cls.order = [
            enigma_fast.rotor_tables(name)
            for name in cls.SPEC["key"]["rotor_order"]
        ]
        cls.rings = tuple(ord(letter) - 65 for letter in cls.RINGS)
        cls.held = (0, 0, 0)
        # The sweep would retain this candidate at the held rings: the ring and
        # the start shift together, so the body is identical.
        cls.true_key = tuple(
            ord(letter) - 65 for letter in cls.SPEC["messages"][0]["message_key"]
        )
        cls.swept_start = tuple(
            (key - ring) % 26 for key, ring in zip(cls.true_key, cls.rings)
        )

    def test_the_held_rings_reproduce_the_body_the_true_rings_produce(self):
        body = self.traffic[0].body
        under_truth = enigma_fast.crypt_indices(
            self.order, list(self.rings), self.true_key, body,
            self.plugboard, self.reflector,
        )
        under_held = enigma_fast.crypt_indices(
            self.order, list(self.held), self.swept_start, body,
            self.plugboard, self.reflector,
        )
        # If this ever fails the fixture has drifted into left-wheel stepping
        # and the rest of the class is testing nothing.
        self.assertEqual(under_truth, under_held)

    def test_compatible_ring_settings_recovers_the_true_rings(self):
        compatible = compatible_ring_settings(
            self.traffic[0], self.held, self.swept_start, self.plugboard,
            self.order, self.reflector, "grundstellung_first",
        )
        self.assertIn(self.rings, compatible)

    def test_recovered_rings_confirm_the_true_message_keys(self):
        expected = [
            record["true_message_key"] for record in self.truth["truth"]["messages"]
        ]
        recovered = confirm_against_date(
            self.traffic, self.plugboard,
            self.SPEC["key"]["rotor_order"], self.held, self.scorer,
            self.reflector, ["grundstellung_first"],
            swept_message=self.traffic[0], swept_start=self.swept_start,
        )
        self.assertTrue(recovered["best_rings_recovered"])
        self.assertEqual(recovered["best_rings"], self.RINGS)
        self.assertEqual(recovered["best_message_keys"], expected)

        # Reusing the held rings is the defect: the keys are wrong and the
        # pooled score is noise, so a genuine hit would be dismissed.
        held = confirm_against_date(
            self.traffic, self.plugboard,
            self.SPEC["key"]["rotor_order"], self.held, self.scorer,
            self.reflector, ["grundstellung_first"],
        )
        self.assertNotEqual(held["best_message_keys"], expected)
        self.assertGreater(
            recovered["best_pooled_score_per_letter"],
            held["best_pooled_score_per_letter"],
        )

    def test_an_inconsistent_candidate_is_flagged_rather_than_skipped(self):
        # A start position the indicator cannot produce under any ring setting
        # in the slice: the check still yields a score, marked unrecovered.
        wrong_start = tuple((value + 5) % 26 for value in self.swept_start)
        result = confirm_against_date(
            self.traffic, self.plugboard,
            self.SPEC["key"]["rotor_order"], self.held, self.scorer,
            self.reflector, ["grundstellung_first"],
            swept_message=self.traffic[0], swept_start=wrong_start,
        )
        self.assertEqual(result["compatible_ring_settings"], 0)
        self.assertFalse(result["best_rings_recovered"])
        self.assertEqual(result["best_rings"], "AAA")


class ConfigPathTests(unittest.TestCase):
    def test_a_config_outside_the_checkout_is_recorded_absolutely(self):
        # The record is assembled after the experiment, so raising here would
        # discard a run that can take hours.
        inside = stecker.describe_path(CALIBRATION_CONFIG)
        self.assertEqual(
            inside, "experiments/phase1-stecker-calibration-v1/config.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            outside = pathlib.Path(directory) / "config.json"
            outside.write_text("{}", encoding="utf-8")
            self.assertEqual(stecker.describe_path(outside), str(outside))


class SweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(INDICATOR_CONFIG)
        cls.reflector = enigma_fast.reflector_table("B")
        cls.traffic = traffic_from_corpus(
            ROOT / "corpus.json", "1941-09-30", ["BYQMZ", "FKQLZ", "XFEDT"]
        )

    def test_sweep_retains_the_highest_scoring_candidates_in_order(self):
        rings = ring = [(a, b, 0) for a in range(4) for b in range(4)]
        survivors, evaluated = indicator_ic_sweep(
            self.traffic,
            "grundstellung_first",
            [("I", "II", "III"), ("II", "IV", "V")],
            rings,
            self.reflector,
            5,
        )
        self.assertEqual(evaluated, 2 * len(rings))
        self.assertEqual(len(survivors), 5)
        statistics = [candidate.statistic for candidate in survivors]
        self.assertEqual(statistics, sorted(statistics, reverse=True))

    def test_sweep_survivors_do_not_depend_on_the_retention_limit(self):
        rings = [(a, b, 0) for a in range(6) for b in range(6)]
        orders = [("I", "II", "III"), ("II", "IV", "V"), ("V", "I", "III")]
        small, _ = indicator_ic_sweep(
            self.traffic, "grundstellung_first", orders, rings, self.reflector, 3
        )
        large, _ = indicator_ic_sweep(
            self.traffic, "grundstellung_first", orders, rings, self.reflector, 25
        )
        self.assertEqual(
            [(c.rotor_order, c.rings) for c in small],
            [(c.rotor_order, c.rings) for c in large[:3]],
        )

    def test_declared_ring_and_rotor_spaces_have_the_documented_sizes(self):
        self.assertEqual(len(ring_space("all")), 17576)
        self.assertEqual(
            len(
                rotor_order_space(
                    "all_permutations", ["I", "II", "III", "IV", "V"]
                )
            ),
            60,
        )
        self.assertEqual(resolve_axis("A"), [0])
        self.assertEqual(len(resolve_axis("all")), 26)

    def test_body_direct_sweep_finds_a_planted_key_inside_its_slice(self):
        plaintext = normalize_plaintext(
            stecker.load_config(CALIBRATION_CONFIG)["climb_capability_calibration"][
                "plaintext"
            ],
            167,
        )
        plugboard = "AN BY CF DR GJ HS IL KM PV QZ"
        ciphertext = EnigmaI(
            rotors=("I", "II", "III"), rings="AAA", positions="AEF", plugboard=plugboard
        ).crypt(plaintext)
        message = Traffic(
            designator="PLANT",
            first_trigram=(0, 0, 0),
            second_trigram=(0, 0, 0),
            body=enigma_fast.text_to_indices(ciphertext),
        )
        config = stecker.load_config(BODY_CONFIG)
        ranked, evaluated, distribution = body_direct_sweep(
            message,
            [("I", "II", "III")],
            (0, 0, 0),
            [(0, 4, right) for right in range(8)],
            config["scorer"],
            self.reflector,
            config["climb"],
            3,
            1,
        )
        self.assertEqual(evaluated, 8)
        self.assertEqual(ranked[0]["start_position"], "AEF")
        self.assertEqual(ranked[0]["plugboard"], plugboard)
        self.assertGreater(
            ranked[0]["score_per_letter"], distribution["mean_score_per_letter"]
        )


class RunnerTests(unittest.TestCase):
    def test_config_schema_and_mode_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(json.dumps({"schema": "wrong", "mode": "calibration"}))
            with self.assertRaises(ValueError):
                stecker.load_config(path)
            path.write_text(
                json.dumps({"schema": stecker.CONFIG_SCHEMA, "mode": "guessing"})
            )
            with self.assertRaises(ValueError):
                stecker.load_config(path)

    def test_unknown_indicator_ordering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": stecker.CONFIG_SCHEMA,
                        "mode": "calibration",
                        "indicator_orderings": ["reversed_middle"],
                    }
                )
            )
            with self.assertRaises(ValueError):
                stecker.load_config(path)

    def test_every_preregistered_config_declares_hypothesis_and_refutation(self):
        for path in (CALIBRATION_CONFIG, INDICATOR_CONFIG, BODY_CONFIG):
            with self.subTest(config=path.name):
                config = stecker.load_config(path)
                self.assertTrue(config["hypothesis"].strip())
                self.assertTrue(config["refuted_by"].strip())
                self.assertTrue(config["limitations"])
                self.assertEqual(config["climb"]["max_pairs"], 10)

    def test_all_configs_use_the_validated_phase7_scorer(self):
        phase7_config = json.loads(
            (
                ROOT / "experiments/phase7-qtxma-source-and-scorer-v2/config.json"
            ).read_text(encoding="utf-8")
        )
        for path in (CALIBRATION_CONFIG, INDICATOR_CONFIG, BODY_CONFIG):
            with self.subTest(config=path.name):
                self.assertEqual(
                    stecker.load_config(path)["scorer"], phase7_config["scorer"]
                )

    def test_a_failed_preflight_makes_zero_target_calls(self):
        config = dict(stecker.load_config(INDICATOR_CONFIG))
        config["kernel_parity"] = {"seed": 1, "samples": 1}
        broken = dict(config["scorer_validation"])
        broken["minimum_messages_above_all_shuffles"] = 99
        config["scorer_validation"] = broken
        result = stecker.run_experiment(config, INDICATOR_CONFIG, [], 1)
        self.assertEqual(result["status"], "blocked_by_preflight")
        self.assertIsNone(result["result"])
        self.assertEqual(result["positive_controls"]["evaluated"], [])

    def test_a_failed_control_makes_zero_target_calls(self):
        config = json.loads(INDICATOR_CONFIG.read_text(encoding="utf-8"))
        # Same plaintexts and indicators, wrong declared key: the pipeline is
        # then given traffic it cannot possibly recover.
        config["positive_controls"][0]["key"]["rings"] = "AAA"
        result = stecker.run_experiment(config, INDICATOR_CONFIG, [], 1)
        self.assertEqual(result["status"], "blocked_by_positive_control")
        self.assertIsNone(result["result"])
        self.assertFalse(result["positive_controls"]["passed"])

    def test_the_record_says_whether_the_code_was_committed(self):
        # A commit alone does not identify code that ran with uncommitted
        # edits, so the record has to carry the flag and the hashes of every
        # module the split runner actually used.
        config = json.loads(INDICATOR_CONFIG.read_text(encoding="utf-8"))
        config["positive_controls"][0]["key"]["rings"] = "AAA"
        code = stecker.run_experiment(config, INDICATOR_CONFIG, [], 1)["code"]
        self.assertIn("dirty", code)
        self.assertIn("status", code)
        for module in (
            "phase1_stecker.py",
            "stecker_calibration.py",
            "stecker_climb.py",
            "stecker_controls.py",
            "stecker_scoring.py",
            "stecker_sweeps.py",
            "stecker_traffic.py",
            "enigma_fast.py",
            "phase7.py",
        ):
            self.assertIn(module, code["files_sha256"])

    def test_calibration_artifact_records_every_declared_finding(self):
        artifact = json.loads(
            (ROOT / "artifacts/phase1-stecker-calibration-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(artifact["status"], "complete")
        self.assertFalse(artifact["accepted_break"])
        self.assertEqual(
            sorted(artifact["result"]["findings"]),
            [
                "cheap_screen_exists",
                "ic_stage_usable_at_target_scale",
                "indicator_coupling_is_climbable",
                "stecker_climb_recovers_at_target_scale",
            ],
        )


if __name__ == "__main__":
    unittest.main()
