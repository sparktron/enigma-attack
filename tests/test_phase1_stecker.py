import json
import pathlib
import tempfile
import unittest
from unittest import mock

import enigma_fast
import phase1_stecker as stecker
import stecker_batch
import stecker_power
from enigma import EnigmaI
from stecker_climb import body_direct_climb, coincidence_of_decryption, run_climb_phases
from stecker_controls import (
    batched_climb_parity_report,
    compatible_ring_settings,
    confirm_against_date,
    evaluate_positive_control,
    run_preflight,
)
from stecker_power import evaluate_power_prediction, perturb_ciphertext, wilson_interval
from stecker_scoring import FastNgramScorer, index_of_coincidence, letter_counts
from stecker_space import (
    RingRule,
    middle_start_phases,
    reducible_space_size,
    resolve_axis,
    ring_space,
    rotor_order_space,
    rule_key_coverage,
    stepping_pattern,
)
from stecker_sweeps import (
    body_direct_sweep,
    indicator_ic_sweep,
    merge_score_statistics,
    resolve_engine,
    sweep_chunks,
    sweep_fingerprint,
    sweep_slice,
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
POWER_CONFIG = ROOT / "experiments/phase1-end-to-end-power-v1/config.json"


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


WHEELS = ("I", "II", "III", "IV", "V")


class RingRuleTests(unittest.TestCase):
    """The sweep's parameterization decides which true keys it can reach."""

    LENGTH = 167

    def test_the_middle_phase_past_the_notch_keeps_the_notch_out_of_the_message(self):
        notches = enigma_fast.rotor_tables("II").notches  # E
        phases = middle_start_phases(notches, self.LENGTH, False)
        self.assertEqual(phases, [(next(iter(notches)) + 1) % 26])
        for phase in phases:
            reached = {(phase + step) % 26 for step in range(-(-self.LENGTH // 26) + 1)}
            self.assertFalse(reached & notches)

    def test_the_complete_rule_adds_exactly_the_starts_that_reach_the_notch(self):
        notches = enigma_fast.rotor_tables("II").notches
        past = middle_start_phases(notches, self.LENGTH, False)
        complete = middle_start_phases(notches, self.LENGTH, True)
        self.assertEqual(complete[0], past[0])
        self.assertEqual(len(set(complete)), len(complete))
        advances = -(-self.LENGTH // 26)
        self.assertEqual(len(complete), 1 + advances + 1)

    def test_a_held_rule_with_the_old_arguments_reproduces_the_old_settings(self):
        rule = RingRule("held", (0, 0, 0), (0,), self.LENGTH)
        starts = [(0, 4, right) for right in range(3)]
        self.assertEqual(
            rule.settings(("I", "II", "III"), starts),
            [((0, 0, 0), start) for start in starts],
        )

    def test_the_right_ring_axis_multiplies_the_settings(self):
        rule = RingRule("held", (0, 0, 0), (0, 5, 9), self.LENGTH)
        settings = rule.settings(("I", "II", "III"), [(1, 2, 3)])
        self.assertEqual([rings[2] for rings, _ in settings], [0, 5, 9])
        self.assertTrue(all(start == (1, 2, 3) for _, start in settings))

    def test_the_middle_ring_is_derived_so_the_wiring_offset_is_the_searched_one(self):
        rule = RingRule("middle_past_notch", (0, 0, 0), (7,), self.LENGTH)
        (rings, positions), = rule.settings(("I", "II", "III"), [(3, 11, 20)])
        self.assertEqual((positions[0] - rings[0]) % 26, 3)
        self.assertEqual((positions[1] - rings[1]) % 26, 11)
        self.assertEqual(positions[2], 20)
        self.assertEqual(rings[2], 7)

    def test_the_stepping_pattern_decides_whether_an_equivalent_decrypts_the_message(self):
        order = ("II", "V", "III")
        tables = [enigma_fast.rotor_tables(name) for name in order]
        reflector = enigma_fast.reflector_table("B")
        generator = __import__("random").Random(20261002)
        for _ in range(40):
            rings = tuple(generator.randrange(26) for _ in range(3))
            start = tuple(generator.randrange(26) for _ in range(3))
            truth = enigma_fast.position_permutations(
                tables, rings, start, self.LENGTH, reflector
            )
            true_pattern = stepping_pattern(
                tables[1].notches, tables[2].notches, start[1], start[2], self.LENGTH
            )
            offsets = tuple((start[i] - rings[i]) % 26 for i in range(3))
            for name in ("held", "middle_past_notch", "middle_complete"):
                rule = RingRule(name, (0, 0, 0), (rings[2],), self.LENGTH)
                exact = False
                predicted = False
                for swept_rings, swept_start in rule.settings(order, [(*offsets[:2], start[2])]):
                    swept = enigma_fast.position_permutations(
                        tables, swept_rings, swept_start, self.LENGTH, reflector
                    )
                    exact = exact or swept == truth
                    predicted = predicted or true_pattern == stepping_pattern(
                        tables[1].notches, tables[2].notches,
                        swept_start[1], swept_start[2], self.LENGTH,
                    )
                self.assertEqual(exact, predicted, (name, rings, start))
                if name == "middle_complete":
                    self.assertTrue(exact)

    def test_coverage_is_the_fraction_of_keys_whose_left_wheel_does_not_step(self):
        held = rule_key_coverage("held", self.LENGTH, WHEELS)
        past = rule_key_coverage("middle_past_notch", self.LENGTH, WHEELS)
        complete = rule_key_coverage("middle_complete", self.LENGTH, WHEELS)
        # Independent of the equivalence search: count true keys whose left
        # wheel never steps.
        quiet = total = 0
        for middle in WHEELS:
            for right in WHEELS:
                if middle == right:
                    continue
                for position_middle in range(26):
                    for position_right in range(26):
                        total += 1
                        pattern = stepping_pattern(
                            enigma_fast.rotor_tables(middle).notches,
                            enigma_fast.rotor_tables(right).notches,
                            position_middle, position_right, self.LENGTH,
                        )
                        quiet += all(value < 2 for value in pattern)
        self.assertAlmostEqual(past, quiet / total, places=9)
        self.assertEqual(complete, 1.0)
        self.assertLess(held, past)
        self.assertAlmostEqual(held, 0.524, places=2)

    def test_complete_rule_multiplies_the_reducible_space_and_the_others_do_not(self):
        self.assertEqual(
            reducible_space_size("held", self.LENGTH, WHEELS), 60 * 26**4
        )
        self.assertEqual(
            reducible_space_size("middle_past_notch", self.LENGTH, WHEELS), 60 * 26**4
        )
        self.assertEqual(
            reducible_space_size("middle_complete", self.LENGTH, WHEELS), 60 * 26**4 * 9
        )

    def test_an_unknown_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            RingRule("surprise", (0, 0, 0), (0,), 10)


class BodyDirectRunnerRuleTests(unittest.TestCase):
    def test_the_runner_declares_its_rule_its_axes_and_the_coverage_they_give(self):
        config = stecker.load_config(BODY_CONFIG)
        config["machine"]["rotor_orders"] = [["I", "II", "III"]]
        config["body_direct_sweep"].update(
            {"ring_rule": "middle_past_notch", "right_ring": "AB",
             "start_left": "A", "start_middle": "AB", "start_right": "A", "keep": 2}
        )
        scorer = scorer_for(config)
        traffic = traffic_from_corpus(
            ROOT / "corpus.json", "1941-09-30", ["BYQMZ", "FKQLZ", "XFEDT"]
        )
        result = stecker.run_body_direct_sweep(
            config, scorer, enigma_fast.reflector_table("B"), traffic, 1
        )
        self.assertEqual(result["ring_rule"], "middle_past_notch")
        self.assertEqual(result["right_rings_searched"], 2)
        self.assertEqual(result["start_positions"], 2)
        self.assertEqual(result["evaluated_settings"], 4)
        coverage = result["coverage"]
        self.assertEqual(coverage["reducible_space_settings"], 60 * 26**4)
        self.assertEqual(
            coverage["exact_key_coverage_of_reducible_space"],
            round(rule_key_coverage("middle_past_notch", 167, WHEELS), 6),
        )
        for candidate in result["top_candidates"]:
            self.assertEqual(len(candidate["rings"]), 3)
            self.assertIn("indicator_confirmation", candidate)


class EndToEndPowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(POWER_CONFIG)
        cls.config["end_to_end_power"].update(
            {"left_neighbours": 0, "middle_neighbours": 0, "right_neighbours": 0,
             "null_trials": 1}
        )
        stecker_power._power_init(cls.config)

    def test_a_draw_is_a_pure_function_of_its_coordinates(self):
        self.assertEqual(stecker_power._power_draw((0, 3)), stecker_power._power_draw((0, 3)))
        self.assertNotEqual(
            stecker_power._power_draw((0, 3))["planted"], stecker_power._power_draw((0, 4))["planted"]
        )

    def test_the_complete_arm_always_contains_an_exact_equivalent_of_the_planted_key(self):
        for draw in range(3):
            result = stecker_power._power_draw((0, draw))
            arm = result["arms"]["middle_complete"]
            self.assertTrue(arm["exact_equivalent_exists"], draw)
            self.assertEqual(arm["best_equivalent_fraction"], 1.0)
            self.assertEqual(result["arms"]["rings_held_AAA"]["settings_evaluated"], 1)
            self.assertEqual(
                result["arms"]["middle_complete"]["settings_evaluated"], 9
            )

    def test_a_perturbed_draw_makes_no_equivalence_claim(self):
        result = stecker_power._power_draw((1, 0))
        self.assertIn(result["planted"]["perturbation"]["kind"], {"deletion", "insertion"})
        for arm in result["arms"].values():
            self.assertIsNone(arm["exact_equivalent_exists"])
            self.assertIsNone(arm["best_equivalent_fraction"])

    def test_an_indel_changes_the_length_by_one_and_none_changes_nothing(self):
        generator = __import__("random").Random(1)
        text = "ABCDEFGHIJKLMNOP"
        self.assertEqual(perturb_ciphertext(text, "none", generator)[0], text)
        lengths = {
            len(perturb_ciphertext(text, "indel", __import__("random").Random(seed))[0])
            for seed in range(20)
        }
        self.assertEqual(lengths, {len(text) - 1, len(text) + 1})
        with self.assertRaises(ValueError):
            perturb_ciphertext(text, "garble", generator)

    def test_wilson_interval_is_sane(self):
        self.assertEqual(wilson_interval(0, 0), [0.0, 1.0])
        low, high = wilson_interval(5, 10)
        self.assertAlmostEqual(low + high, 1.0, places=3)
        self.assertLess(low, 0.5)
        self.assertEqual(wilson_interval(10, 10)[1], 1.0)

    def test_predictions_are_scored_from_the_measured_rates(self):
        cells = [
            {"arms": [{"arm": "a", "detection_rate": 0.7,
                       "measured_exact_equivalent_rate": 0.7, "analytic_exact_key_coverage": 0.6},
                      {"arm": "b", "detection_rate": 0.5}]},
            {"arms": [{"arm": "a", "detection_rate": 0.2}]},
        ]
        def score(kind, **extra):
            return evaluate_power_prediction(
                {"id": "x", "statement": "s", "kind": kind, "cell": 0, "arm": "a", **extra}, cells
            )
        self.assertTrue(score("rate_at_least", value=0.7)["passed"])
        self.assertFalse(score("rate_at_least", value=0.71)["passed"])
        self.assertTrue(score("rate_at_most", value=0.7)["passed"])
        self.assertTrue(score("rate_gain_at_least", over="b", value=0.19)["passed"])
        self.assertTrue(score("measured_exact_within_analytic", value=0.11)["passed"])
        self.assertFalse(score("measured_exact_within_analytic", value=0.05)["passed"])
        ratio = score("rate_ratio_at_most", cell=1, over_cell=0, value=0.3)
        self.assertTrue(ratio["passed"])
        self.assertAlmostEqual(ratio["observed"], 0.285714, places=6)
        with self.assertRaises(ValueError):
            score("telepathy", value=1)


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


def planted_message(plugboard="AN BY CF DR GJ HS IL KM PV QZ", positions="AEF", length=167):
    plaintext = normalize_plaintext(
        stecker.load_config(CALIBRATION_CONFIG)["climb_capability_calibration"]["plaintext"],
        length,
    )
    ciphertext = EnigmaI(
        rotors=("I", "II", "III"), rings="AAA", positions=positions, plugboard=plugboard
    ).crypt(plaintext)
    return Traffic(
        designator="PLANT",
        first_trigram=(0, 0, 0),
        second_trigram=(0, 0, 0),
        body=enigma_fast.text_to_indices(ciphertext),
    )


@unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
class BatchedClimbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(BODY_CONFIG)
        cls.scorer = scorer_for(cls.config)
        cls.reflector = enigma_fast.reflector_table("B")

    def test_the_batched_climb_ends_where_the_reference_climb_ends(self):
        report = batched_climb_parity_report(
            {**self.config, "batched_climb_parity": {"seed": 7, "samples": 10}},
            self.scorer,
            self.reflector,
        )
        self.assertEqual(report["identical_final_plugboards"], 10)
        self.assertEqual(report["identical_evaluation_counts"], 10)
        self.assertTrue(report["passed"])

    def test_masked_letters_reset_the_ngram_chain_in_both_climbs(self):
        message = planted_message()
        body = list(message.body)
        for position in (0, 1, 2, 40, 41, 120):
            body[position] = -1
        order = [enigma_fast.rotor_tables(name) for name in ("I", "II", "III")]
        table = enigma_fast.position_permutations(
            order, (0, 0, 0), (0, 4, 5), len(body), self.reflector
        )
        reference, _ = body_direct_climb(
            [Traffic("M", (0, 0, 0), (0, 0, 0), tuple(body))],
            ("I", "II", "III"), (0, 0, 0), [(0, 4, 5)], self.scorer, self.reflector,
            self.config["climb"],
        )
        plugboard, evaluations = stecker_batch.BatchedClimber(
            self.scorer.bigram, self.scorer.combined, body, self.config["climb"]
        ).climb(table)
        self.assertEqual(list(reference.plugboard), plugboard)
        self.assertEqual(reference.evaluations, evaluations)

    def test_a_batched_sweep_finds_the_planted_key_and_matches_the_reference_sweep(self):
        message = planted_message()
        arguments = (
            message, [("I", "II", "III")], (0, 0, 0), [(0, 4, right) for right in range(6)],
            self.config["scorer"], self.reflector,
        )
        reference = body_direct_sweep(
            *arguments, {**self.config["climb"], "engine": "reference"}, 6, 1
        )
        batched = body_direct_sweep(
            *arguments, {**self.config["climb"], "engine": "batched"}, 6, 1
        )
        self.assertEqual(batched[0], reference[0])
        self.assertEqual(batched[1], reference[1])
        self.assertEqual(batched[0][0]["start_position"], "AEF")
        self.assertEqual(batched[0][0]["plugboard"], "AN BY CF DR GJ HS IL KM PV QZ")

    def test_the_preflight_adds_the_parity_check_only_when_the_engine_is_batched(self):
        config = {
            **self.config,
            "kernel_parity": {"seed": 1, "samples": 2},
            "scorer_parity": {**self.config["scorer_parity"], "samples": 2},
            "batched_climb_parity": {"seed": 3, "samples": 4},
        }
        batched = run_preflight(
            {**config, "climb": {**config["climb"], "engine": "batched"}}, self.scorer
        )
        self.assertTrue(batched["checks"]["batched_climb_matches_reference"])
        reference = run_preflight(config, self.scorer)
        self.assertNotIn("batched_climb_matches_reference", reference["checks"])


class EngineSelectionTests(unittest.TestCase):
    def test_reference_is_the_default_and_unknown_engines_are_rejected(self):
        self.assertEqual(resolve_engine({}), "reference")
        with self.assertRaises(ValueError):
            resolve_engine({"engine": "gpu"})

    def test_without_numpy_auto_falls_back_and_batched_fails_loudly(self):
        with mock.patch.object(stecker_batch, "np", None):
            self.assertFalse(stecker_batch.available())
            self.assertEqual(resolve_engine({"engine": "auto"}), "reference")
            self.assertEqual(resolve_engine({"engine": "reference"}), "reference")
            with self.assertRaises(RuntimeError):
                resolve_engine({"engine": "batched"})
            with self.assertRaises(RuntimeError):
                stecker_batch.BatchedClimber([0.0] * 676, [0.0] * 17576, [0], {})

    def test_a_configuration_with_an_unknown_engine_is_rejected_on_load(self):
        config = json.loads(BODY_CONFIG.read_text(encoding="utf-8"))
        config["climb"]["engine"] = "gpu"
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                stecker.load_config(path)

    @unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
    def test_with_numpy_auto_is_batched(self):
        self.assertEqual(resolve_engine({"engine": "auto"}), "batched")


class SweepEngineTests(unittest.TestCase):
    """What the rebuilt sweep promises: bounded memory, no scheduling dependence, resumability."""

    ORDERS = [("I", "II", "III"), ("II", "IV", "V")]
    STARTS = [(0, middle, right) for middle in (3, 4, 5) for right in range(3)]

    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(BODY_CONFIG)
        cls.reflector = enigma_fast.reflector_table("B")
        cls.message = planted_message()

    def sweep(self, keep=5, jobs=1, checkpoint=None, orders=None):
        return sweep_slice(
            self.message, orders or self.ORDERS, (0, 0, 0), self.STARTS,
            self.config["scorer"], self.reflector, self.config["climb"], keep, jobs, checkpoint,
        )

    def test_chunks_are_one_per_wheel_order_and_middle_start(self):
        rule = RingRule("held", (0, 0, 0), (0,), 167)
        chunks = sweep_chunks(rule, self.ORDERS, self.STARTS)
        self.assertEqual(len(chunks), 6)
        self.assertEqual(len({key for key, _, _ in chunks}), 6)
        self.assertEqual(sum(len(settings) for _, _, settings in chunks), 18)
        orders = rotor_order_space("all_permutations", ["I", "II", "III", "IV", "V"])
        full = sweep_chunks(rule, orders, [(0, m, 0) for m in range(26)])
        self.assertEqual(len(full), 60 * 26)

    def test_result_does_not_depend_on_the_worker_count(self):
        serial = self.sweep(jobs=1)
        parallel = self.sweep(jobs=2)
        self.assertEqual(serial[0], parallel[0])
        self.assertEqual(serial[1:3], parallel[1:3])

    def test_the_retained_candidates_do_not_depend_on_the_retention_limit(self):
        small = self.sweep(keep=3)[0]
        large = self.sweep(keep=12)[0]
        self.assertEqual(small, large[:3])

    def test_streaming_statistics_match_a_direct_computation(self):
        import statistics

        ranked, evaluated, distribution, _ = self.sweep(keep=100)
        scores = [row["score_per_letter"] for row in ranked]
        self.assertEqual(evaluated, 18)
        self.assertEqual(len(scores), 18)
        self.assertAlmostEqual(distribution["mean_score_per_letter"], statistics.fmean(scores), places=7)
        self.assertAlmostEqual(distribution["sd_score_per_letter"], statistics.pstdev(scores), places=7)
        self.assertEqual(distribution["max_score_per_letter"], max(scores))

    def test_merging_summaries_equals_summarising_the_union(self):
        import statistics

        left, right = [1.0, 4.0, 9.0], [2.0, 2.5, 30.0, 7.0]

        def summary(values):
            mean = statistics.fmean(values)
            return len(values), mean, sum((value - mean) ** 2 for value in values)

        count, mean, m2 = merge_score_statistics(summary(left), summary(right))
        self.assertEqual(count, 7)
        self.assertAlmostEqual(mean, statistics.fmean(left + right))
        self.assertAlmostEqual(m2, summary(left + right)[2])
        self.assertEqual(merge_score_statistics((0, 0.0, 0.0), summary(left)), summary(left))

    def test_a_checkpoint_records_every_chunk_and_a_rerun_skips_them_all(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "sweep.jsonl"
            first = self.sweep(checkpoint=path)
            self.assertEqual(len(path.read_text().splitlines()), 6)
            self.assertEqual(first[3]["chunks_run"], 6)
            second = self.sweep(checkpoint=path)
            self.assertEqual(second[3]["chunks_run"], 0)
            self.assertEqual(second[3]["chunks_resumed_from_checkpoint"], 6)
            self.assertEqual(second[3]["settings_run"], 0)
            self.assertEqual(first[:3], second[:3])

    def test_a_crashed_run_resumes_from_what_was_recorded_and_ends_identically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "sweep.jsonl"
            whole = self.sweep(checkpoint=path)
            lines = path.read_text().splitlines()
            # Two chunks lost, and the last surviving record cut off mid-write.
            path.write_text("\n".join(lines[:3]) + "\n" + lines[3][:25])
            resumed = self.sweep(checkpoint=path, jobs=2)
            self.assertEqual(resumed[3]["chunks_resumed_from_checkpoint"], 3)
            self.assertEqual(resumed[3]["chunks_run"], 3)
            self.assertEqual(resumed[:3], whole[:3])
            # The cut-off fragment was removed before appending, so every line is
            # a whole record and a further resume has nothing left to run.
            for line in path.read_text().splitlines():
                json.loads(line)
            self.assertEqual(len(path.read_text().splitlines()), 6)
            self.assertEqual(self.sweep(checkpoint=path)[3]["chunks_run"], 0)

    def test_the_fingerprint_covers_the_reflector_and_the_scorer_table_contents(self):
        message = self.message
        rule = RingRule("held", (0, 0, 0), (0,), len(message.body))
        arguments = (
            message.body, self.config["scorer"], self.config["climb"], rule, self.STARTS,
            5, "reference",
        )
        base = sweep_fingerprint(*arguments, self.reflector)
        self.assertEqual(base, sweep_fingerprint(*arguments, self.reflector))
        self.assertNotEqual(
            base, sweep_fingerprint(*arguments, enigma_fast.reflector_table("C"))
        )
        with tempfile.TemporaryDirectory() as directory:
            bigram = pathlib.Path(directory) / "bigram.txt"
            bigram.write_text(
                stecker.resolve_path(self.config["scorer"]["bigram_counts"]).read_text() + "\n",
                encoding="utf-8",
            )
            changed = {**self.config["scorer"], "bigram_counts": str(bigram)}
            self.assertNotEqual(
                base,
                sweep_fingerprint(
                    message.body, changed, self.config["climb"], rule, self.STARTS, 5,
                    "reference", self.reflector,
                ),
            )

    def test_a_checkpoint_from_another_sweep_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "sweep.jsonl"
            self.sweep(checkpoint=path)
            with self.assertRaises(ValueError):
                self.sweep(checkpoint=path, orders=[("I", "II", "III")], keep=4)
            with self.assertRaises(ValueError):
                sweep_slice(
                    planted_message(positions="AAA"), self.ORDERS, (0, 0, 0), self.STARTS,
                    self.config["scorer"], self.reflector, self.config["climb"], 5, 1, path,
                )

    def test_the_runner_resumes_through_its_declared_checkpoint(self):
        config = stecker.load_config(BODY_CONFIG)
        config["machine"]["rotor_orders"] = [["I", "II", "III"]]
        with tempfile.TemporaryDirectory() as directory:
            config["body_direct_sweep"].update(
                {"start_left": "A", "start_middle": "AB", "start_right": "A", "keep": 2,
                 "checkpoint": str(pathlib.Path(directory) / "run.jsonl")}
            )
            traffic = traffic_from_corpus(
                ROOT / "corpus.json", "1941-09-30", ["BYQMZ", "FKQLZ", "XFEDT"]
            )
            scorer = scorer_for(config)
            first = stecker.run_body_direct_sweep(config, scorer, self.reflector, traffic, 1)
            second = stecker.run_body_direct_sweep(config, scorer, self.reflector, traffic, 1)
        self.assertEqual(first["execution"]["chunks_run"], 2)
        self.assertEqual(second["execution"]["chunks_resumed_from_checkpoint"], 2)
        self.assertIsNone(second["seconds_per_setting"])
        self.assertEqual(first["top_candidates"], second["top_candidates"])
        self.assertEqual(second["execution"]["engine"], first["execution"]["engine"])


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
        for path in (CALIBRATION_CONFIG, INDICATOR_CONFIG, BODY_CONFIG, POWER_CONFIG):
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
        for path in (CALIBRATION_CONFIG, INDICATOR_CONFIG, BODY_CONFIG, POWER_CONFIG):
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
            "stecker_power.py",
            "stecker_scoring.py",
            "stecker_space.py",
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
