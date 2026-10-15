"""Partial exhaustion of the first plug (Ostwald and Weierud's E-Stecker).

``climb.first_plug`` starts the climb from the empty board and from every board
with one plug on the named letters, and keeps the best final n-gram score.  The
reference climb defines it; the batched and CUDA climbs must end on the same
plugboard after the same number of evaluations.  GPU tests skip without a GPU.
"""

import copy
import json
import pathlib
import random
import tempfile
import unittest

import enigma_fast
import phase1_stecker as stecker
import stecker_batch
import stecker_cuda
import stecker_controls
import stecker_power
from stecker_climb import (
    body_direct_climb, climb_stecker, climb_windows, coincidence_of_decryption, first_plug_options,
    start_boards, windowed_climb,
)
from stecker_scoring import FastNgramScorer
from stecker_traffic import Traffic, traffic_from_corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
V4_CONFIG = ROOT / "experiments/phase1-body-direct-sweep-v4/config.json"
POWER_CONFIG = ROOT / "experiments/phase1-end-to-end-power-v1/config.json"
GPU = stecker_cuda.available()
E = {"letters": "E"}


class StartBoardTests(unittest.TestCase):
    def test_without_first_plug_the_only_start_is_the_empty_board(self):
        self.assertEqual(start_boards({}), [list(range(26))])
        self.assertEqual(start_boards({"first_plug": None}), [list(range(26))])

    def test_the_published_start_set_sizes(self):
        self.assertEqual(len(start_boards({"first_plug": {"letters": "E"}})), 26)
        self.assertEqual(len(start_boards({"first_plug": {"letters": "ENR"}})), 73)
        self.assertEqual(len(start_boards({"first_plug": {"letters": "ENRXSI"}})), 136)

    def test_boards_are_the_empty_board_then_one_pair_each_without_repeats(self):
        boards = start_boards({"first_plug": {"letters": "ENR"}})
        self.assertEqual(boards[0], list(range(26)))
        seen = set()
        for board in boards[1:]:
            pairs = [(x, board[x]) for x in range(26) if board[x] > x]
            self.assertEqual(len(pairs), 1)
            self.assertEqual([x for x in range(26) if board[board[x]] != x], [])
            self.assertTrue({4, 13, 17} & set(pairs[0]))
            self.assertNotIn(pairs[0], seen)
            seen.add(pairs[0])
        # E's partners first, in letter order.
        self.assertEqual([b[4] for b in boards[1:5]], [0, 1, 2, 3])

    def test_bad_letters_are_rejected(self):
        for letters in ("", "EE", "e1", "E N"):
            with self.assertRaises(ValueError):
                start_boards({"first_plug": {"letters": letters}})
        with self.assertRaises(ValueError):
            start_boards({"first_plug": {"letters": "ENRXSIT"}})

    def test_lowercase_letters_are_accepted(self):
        self.assertEqual(start_boards({"first_plug": {"letters": "e"}}), start_boards({"first_plug": E}))


class ConfigTests(unittest.TestCase):
    def load(self, climb):
        config = json.loads(V4_CONFIG.read_text(encoding="utf-8"))
        config["climb"] = {**config["climb"], **climb}
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            return stecker.load_config(path)

    def test_a_valid_first_plug_loads(self):
        self.assertEqual(self.load({"first_plug": E})["climb"]["first_plug"], E)

    def test_first_plug_refuses_the_split_point_climb(self):
        with self.assertRaisesRegex(ValueError, "split"):
            self.load({"first_plug": E, "split": {"ic_grid": 32, "block": 64, "mask_term": -8.66}})

    def test_first_plug_needs_the_ngram_phase(self):
        with self.assertRaisesRegex(ValueError, "n-gram"):
            self.load({"first_plug": E, "phases": ["index_of_coincidence"]})

    def test_first_plug_with_bad_letters_is_refused_at_load(self):
        with self.assertRaises(ValueError):
            self.load({"first_plug": {"letters": "EE"}})


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(V4_CONFIG)
        cls.scorer = FastNgramScorer(cls.config["scorer"])
        cls.reflector = enigma_fast.reflector_table("B")
        target = cls.config["target"]
        traffic = traffic_from_corpus(
            stecker.resolve_path(cls.config["corpus"]), target["date"], target["messages"]
        )
        cls.body = list({m.designator: m for m in traffic}[cls.config["body_direct_sweep"]["message"]].body)
        cls.climb = {k: v for k, v in cls.config["climb"].items() if k not in ("window", "engine")}

    def table(self, names, row, body=None):
        order = [enigma_fast.rotor_tables(name) for name in names]
        body = self.body if body is None else body
        return enigma_fast.position_permutations(order, row[:3], row[3:], len(body), self.reflector)


class ReferenceTests(Fixture):
    def test_the_best_of_the_starts_is_never_worse_than_the_empty_board(self):
        generator = random.Random(5)
        message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(self.body[:90]))
        for _ in range(2):
            names = generator.sample(["I", "II", "III", "IV", "V"], 3)
            row = [generator.randrange(26) for _ in range(6)]
            args = (
                [message], names, row[:3], [row[3:]], self.scorer, self.reflector,
            )
            base, _ = body_direct_climb(*args, self.climb)
            multi, _ = body_direct_climb(*args, {**self.climb, "first_plug": E})
            self.assertGreaterEqual(multi.score_per_letter, base.score_per_letter)
            self.assertGreater(multi.evaluations, 20 * base.evaluations // 2)


@unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
class BatchedParityTests(Fixture):
    def test_batched_ends_on_the_reference_plugboard_after_the_same_evaluations(self):
        generator = random.Random(11)
        for length in (167, 60):
            body = self.body[:length]
            if length == 60:
                body = list(body)
                body[7] = body[20] = -1
            message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(body))
            for _ in range(2):
                names = generator.sample(["I", "II", "III", "IV", "V"], 3)
                row = [generator.randrange(26) for _ in range(6)]
                settings = {**self.climb, "first_plug": E}
                outcome, _ = body_direct_climb(
                    [message], names, row[:3], [row[3:]], self.scorer, self.reflector, settings
                )
                plugboard, evaluations = stecker_batch.BatchedClimber(
                    self.scorer.bigram, self.scorer.combined, body, settings
                ).climb(self.table(names, row, body))
                self.assertEqual(tuple(plugboard), outcome.plugboard, (length, names, row))
                self.assertEqual(evaluations, outcome.evaluations)

    def test_without_first_plug_the_batched_climb_is_unchanged(self):
        names, row = ("II", "V", "III"), [3, 1, 4, 1, 5, 9]
        plugboard, evaluations = stecker_batch.BatchedClimber(
            self.scorer.bigram, self.scorer.combined, self.body, self.climb
        ).climb(self.table(names, row))
        message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(self.body))
        outcome, _ = body_direct_climb(
            [message], names, row[:3], [row[3:]], self.scorer, self.reflector, self.climb
        )
        self.assertEqual((tuple(plugboard), evaluations), (outcome.plugboard, outcome.evaluations))


@unittest.skipUnless(GPU and stecker_batch.available(), "needs numpy, nvcc and a CUDA device")
class CudaParityTests(Fixture):
    WINDOW = {"kind": "head_tail", "letters": 117}

    def climb_both(self, body, window, settings_rows, first_plug):
        climb = {**self.climb, "first_plug": first_plug} if first_plug else dict(self.climb)
        if window:
            climb["window"] = window
        gpu = stecker_cuda.CudaClimber(self.scorer.bigram, self.scorer.combined, body, climb, self.reflector)
        mismatches = []
        for names, row in settings_rows:
            table = self.table(names, row, body)
            if window:
                climbers = [
                    stecker_batch.BatchedClimber(self.scorer.bigram, self.scorer.combined, body[a:b], climb)
                    for _, a, b in climb_windows(len(body), window)
                ]
                expected = windowed_climb(table, body, self.scorer, climb, climbers)
            else:
                plugboard, evaluations = stecker_batch.BatchedClimber(
                    self.scorer.bigram, self.scorer.combined, body, climb
                ).climb(table)
                letters = sum(1 for value in body if value >= 0)
                expected = (
                    plugboard, evaluations,
                    self.scorer.score_decryption(table, body, plugboard) / letters, "whole",
                )
            got = gpu.climb_one(names, row[:3], row[3:])
            if tuple(got) != tuple(expected):
                mismatches.append((names, row, got, expected))
        gpu.close()
        return mismatches

    def test_first_plug_climbs_match_the_batched_climb_exactly(self):
        generator = random.Random(29)
        masked = list(self.body)
        for position in (0, 1, 30, 31, 32, 90, 140):
            masked[position] = -1
        for body in (self.body, masked, self.body[:83]):
            rows = [
                (tuple(generator.sample(["I", "II", "III", "IV", "V"], 3)),
                 [generator.randrange(26) for _ in range(6)])
                for _ in range(5)
            ]
            for window in (None, self.WINDOW):
                for first_plug in (E, {"letters": "ENR"}):
                    self.assertEqual(
                        self.climb_both(body, window, rows, first_plug), [],
                        (len(body), window, first_plug),
                    )

    def test_a_single_start_is_unchanged_by_the_multi_start_kernel(self):
        # A planted key the climb recovers: the empty-board path must still find it.
        from enigma import EnigmaI
        from stecker_traffic import normalize_plaintext, random_plugboard

        generator = random.Random(3)
        text = normalize_plaintext(
            "FUNKSTELLEMELDETXFEINDLICHEAUFKLAERERUEBERDEMABSCHNITTNORDXEIGENEVERLUSTEGERINGXMUNITIONFUERZWEITAGEVORHANDENXNEUEBEFEHLEERBETENXENDEABTEILUNGMELDETXANGRIFFAUFHOEHEZWO"
        )
        order, rings, start = ("II", "V", "III"), (3, 4, 5), (6, 7, 8)
        plug = random_plugboard(generator, 10)
        cipher = EnigmaI(
            rotors=order, rings="".join(chr(65 + x) for x in rings),
            positions="".join(chr(65 + x) for x in start), plugboard=plug,
        ).crypt(text)
        body = list(enigma_fast.text_to_indices(cipher))
        expected = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plug))
        for first_plug in (None, E):
            climb = {**self.climb, **({"first_plug": first_plug} if first_plug else {})}
            gpu = stecker_cuda.CudaClimber(self.scorer.bigram, self.scorer.combined, body, climb, self.reflector)
            board, _, _, _ = gpu.climb_one(order, rings, start)
            gpu.close()
            self.assertEqual(enigma_fast.plugboard_pairs(board), expected, first_plug)

    def test_the_cuda_split_climber_refuses_first_plug(self):
        climb = {**self.climb, "first_plug": E, "split": {"ic_grid": 32, "block": 64, "mask_term": -8.66}}
        with self.assertRaisesRegex(ValueError, "split"):
            stecker_cuda.CudaSplitClimber(
                self.scorer.bigram, self.scorer.combined, self.body[:100], climb, self.reflector
            )


class PowerControlTests(unittest.TestCase):
    TEXTS = [
        "FUNKSTELLEMELDETXFEINDLICHEAUFKLAERERUEBERDEMABSCHNITTNORDXEIGENEVERLUSTEGERINGXMUNITIONFUERZWEITAGEVORHANDENXNEUEBEFEHLEERBETENXENDEABTEILUNGMELDETXANGRIFFAUFHOEHEZWO",
        "KOMPCHEFXANKOMPFUEHRERXQSLXRUFZEICHENXBERICHTEXVORPOSTENXAMXWEGEXNACHXKRASNYXFEINDXSCHWACHXKEINEXPANZERXERBITTEXWEISUNGXWEITERERXMARSCHXNACHSCHUBXFEHLTXBENZINXOELXSTOPXGRUSSX",
    ]

    def config(self, **extra):
        config = stecker.load_config(POWER_CONFIG)
        settings = config["end_to_end_power"]
        settings.update({"left_neighbours": 0, "middle_neighbours": 0, "right_neighbours": 0,
                         "null_trials": 1, "cells": [{"length": 167, "perturbation": "none"}]})
        settings.update(extra)
        return config

    def test_a_plaintext_list_changes_no_key_and_each_draw_takes_its_plaintext_in_turn(self):
        plain = self.config()
        stecker_power._power_init(plain)
        before = [stecker_power._power_draw((0, d))["planted"] for d in range(3)]
        listed = self.config(plaintexts=self.TEXTS)
        listed["end_to_end_power"]["arms"] = [
            arm for arm in listed["end_to_end_power"]["arms"] if arm["id"] == "rings_held_AAA"
        ]
        stecker_power._power_init(listed)
        draws = [stecker_power._power_draw((0, d)) for d in range(3)]
        self.assertEqual([d["planted"] for d in draws], before)
        self.assertEqual([d["plaintext"]["index"] for d in draws], [0, 1, 0])
        self.assertNotEqual(draws[0]["plaintext"]["index_of_coincidence"],
                            draws[1]["plaintext"]["index_of_coincidence"])
        stecker_power._power_init(plain)
        self.assertNotIn("plaintext", stecker_power._power_draw((0, 0)))

    def test_a_short_plaintext_is_refused(self):
        config = self.config(plaintexts=["ABC"])
        stecker_power._power_init(config)
        with self.assertRaisesRegex(ValueError, "shorter"):
            stecker_power._power_draw((0, 0))

    def test_an_arm_can_add_or_remove_the_first_plug_starts(self):
        config = self.config()
        config["climb"] = {**config["climb"], "first_plug": E}
        self.assertEqual(stecker_power.arm_climb(config, {"id": "x"})["first_plug"], E)
        self.assertNotIn("first_plug", stecker_power.arm_climb(config, {"id": "x", "first_plug": None}))
        config["climb"].pop("first_plug")
        self.assertEqual(
            stecker_power.arm_climb(config, {"id": "x", "first_plug": {"letters": "ENR"}})["first_plug"],
            {"letters": "ENR"},
        )
        with self.assertRaises(ValueError):
            stecker_power.arm_climb(config, {"id": "x", "first_plug": E, "split": {"ic_grid": 32}})

    def test_a_first_plug_arm_gets_its_own_null(self):
        config = self.config()
        settings = config["end_to_end_power"]
        settings["arms"] = [
            {"id": "base", "ring_rule": "held", "right_ring": "planted"},
            {"id": "estecker", "ring_rule": "held", "right_ring": "planted", "first_plug": E},
        ]
        settings["predictions"] = []
        settings["headline_arm"] = "base"
        stecker_power._power_init(config)
        draw = stecker_power._power_draw((0, 0))
        self.assertNotIn("null_scores", draw["arms"]["base"])
        self.assertEqual(len(draw["arms"]["estecker"]["null_scores"]), 1)

    def test_detection_is_split_by_plaintext_and_by_ic_tercile(self):
        def draw(index, ic):
            return {"plaintext": {"index": index, "index_of_coincidence": ic}}

        draws = [draw(i % 3, (0.05, 0.06, 0.08)[i % 3]) for i in range(9)]
        detected = [i % 3 == 2 or i == 3 for i in range(9)]
        exact = [True] * 9
        report = stecker_power.detection_by_plaintext(draws, [{}] * 9, detected, exact)
        self.assertEqual([g["detected"] for g in report["by_plaintext"]], [1, 0, 3])
        self.assertEqual([t["detection_rate"] for t in report["by_ic_tercile"]], [round(1 / 3, 6), 0.0, 1.0])
        self.assertEqual(report["by_ic_tercile"][2]["detected_given_equivalent"], [3, 3])


@unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
class PreflightTests(Fixture):
    def variant(self, engine):
        config = copy.deepcopy(self.config)
        config["climb"] = {**self.climb, "engine": engine}
        config["batched_climb_parity"] = {"seed": 7, "samples": 2}
        config["end_to_end_power"] = {"arms": [
            {"id": "e", "ring_rule": "held", "right_ring": "A", "first_plug": E,
             "window": {"kind": "head_tail", "letters": 117}},
        ]}
        return config

    def test_the_preflight_declares_and_checks_a_first_plug_arm(self):
        config = self.variant("batched")
        self.assertEqual(stecker_controls.configured_first_plugs(config), [E])
        report = stecker_controls.first_plug_parity_report(config, self.scorer, self.reflector, "batched")
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["climbs_compared"], 2 * (1 + 1))  # whole + one window, two cases

    @unittest.skipUnless(GPU, "needs nvcc and a CUDA device")
    def test_the_cuda_engine_adds_the_gpu_comparisons(self):
        config = self.variant("cuda")
        report = stecker_controls.first_plug_parity_report(config, self.scorer, self.reflector, "cuda")
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["climbs_compared"], 2 * 4)

    def test_a_configuration_without_first_plug_adds_no_check(self):
        config = copy.deepcopy(self.config)
        self.assertEqual(stecker_controls.configured_first_plugs(config), [])


OPTION_SPECS = (
    {"letters": "E", "ic_passes": 4},
    {"letters": "ENR", "start_phases": "ngram_only"},  # R-ngonly
    {"letters": "E", "ic_passes": 2, "start_phases": "ngram_only"},
)


class OptionTests(unittest.TestCase):
    def test_defaults_and_parsing(self):
        self.assertEqual(first_plug_options({}), (None, False))
        self.assertEqual(first_plug_options({"first_plug": E}), (None, False))
        self.assertEqual(first_plug_options({"first_plug": {"letters": "E", "ic_passes": 4}}), (4, False))
        self.assertEqual(first_plug_options({"first_plug": {"letters": "E", "start_phases": "ngram_only"}}), (None, True))
        self.assertEqual(first_plug_options({"first_plug": {"letters": "E", "start_phases": "two_phase"}}), (None, False))

    def test_options_never_change_the_start_boards(self):
        plain = start_boards({"first_plug": {"letters": "ENR"}})
        for spec in OPTION_SPECS:
            self.assertEqual(start_boards({"first_plug": {**spec, "letters": "ENR"}}), plain)

    def test_bad_options_are_rejected_everywhere_a_spec_is_read(self):
        for bad in ({"letters": "E", "ic_passes": 0}, {"letters": "E", "ic_passes": -1}, {"letters": "E", "ic_passes": 2.5},
                    {"letters": "E", "ic_passes": True}, {"letters": "E", "ic_passes": "4"},
                    {"letters": "E", "start_phases": "none"}, {"letters": "E", "extra": 1}):
            with self.assertRaises(ValueError, msg=bad):
                first_plug_options({"first_plug": bad})
            with self.assertRaises(ValueError, msg=bad):
                start_boards({"first_plug": bad, "max_pairs": 10})

    def test_options_are_rejected_by_the_config_loader(self):
        config = json.loads(V4_CONFIG.read_text(encoding="utf-8"))
        config["climb"] = {**config["climb"], "first_plug": {"letters": "E", "ic_passes": 0}}
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                stecker.load_config(path)
            config["climb"]["first_plug"] = {"letters": "ENR", "start_phases": "ngram_only"}
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(stecker.load_config(path)["climb"]["first_plug"]["start_phases"], "ngram_only")


class OptionSemanticsTests(Fixture):
    """The reference climb against a by-hand composition of climb_stecker calls."""

    def by_hand(self, body, order, rings, start, spec):
        table = self.table(order, rings + start, body)
        letters = sum(1 for v in body if v >= 0)
        ngram = lambda pb: self.scorer.score_decryption(table, body, pb)  # noqa: E731
        ic = lambda pb: coincidence_of_decryption(table, body, pb) * len(body) / letters  # noqa: E731
        settings = {**self.climb, "first_plug": spec}
        ic_passes, ngram_only = first_plug_options(settings)
        best, used = None, 0
        for index, board in enumerate(start_boards(settings)):
            plugboard = list(board)
            if not (ngram_only and index > 0):
                passes = int(self.climb["max_passes"]) if ic_passes is None else min(int(self.climb["max_passes"]), ic_passes)
                outcome = climb_stecker(ic, letters, int(self.climb["max_pairs"]), passes, float(self.climb["minimum_gain"]), plugboard)
                plugboard, used = list(outcome.plugboard), used + outcome.evaluations
            outcome = climb_stecker(ngram, letters, int(self.climb["max_pairs"]), int(self.climb["max_passes"]),
                                    float(self.climb["minimum_gain"]), plugboard)
            plugboard, used = list(outcome.plugboard), used + outcome.evaluations
            score = ngram(plugboard)
            if best is None or score > best[0]:
                best = (score, plugboard)
        return tuple(best[1]), used

    def test_the_reference_climb_is_the_by_hand_composition(self):
        generator = random.Random(41)
        message_body = self.body[:90]
        message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(message_body))
        for spec in ({"letters": "E", "ic_passes": 3}, {"letters": "E", "start_phases": "ngram_only"},
                     {"letters": "EN", "ic_passes": 2, "start_phases": "ngram_only"}):
            for _ in range(2):
                order = generator.sample(["I", "II", "III", "IV", "V"], 3)
                rings = tuple(generator.randrange(26) for _ in range(3))
                start = tuple(generator.randrange(26) for _ in range(3))
                outcome, _ = body_direct_climb(
                    [message], order, rings, [list(start)], self.scorer, self.reflector, {**self.climb, "first_plug": spec}
                )
                expected = self.by_hand(message_body, order, rings, start, spec)
                self.assertEqual((outcome.plugboard, outcome.evaluations), expected, (spec, order, rings, start))

    def test_a_cap_that_does_not_bind_changes_nothing_and_a_binding_one_saves_work(self):
        message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(self.body[:100]))
        args = ([message], ["II", "V", "III"], (3, 4, 5), [[6, 7, 8]], self.scorer, self.reflector)
        full, _ = body_direct_climb(*args, {**self.climb, "first_plug": E})
        loose, _ = body_direct_climb(*args, {**self.climb, "first_plug": {**E, "ic_passes": 10_000}})
        tight, _ = body_direct_climb(*args, {**self.climb, "first_plug": {**E, "ic_passes": 1}})
        self.assertEqual((loose.plugboard, loose.evaluations), (full.plugboard, full.evaluations))
        self.assertLess(tight.evaluations, full.evaluations)

    def test_ngram_only_starts_save_the_ic_phase_and_never_lose_to_the_empty_board(self):
        message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(self.body[:100]))
        args = ([message], ["II", "V", "III"], (3, 4, 5), [[6, 7, 8]], self.scorer, self.reflector)
        base, _ = body_direct_climb(*args, self.climb)
        full, _ = body_direct_climb(*args, {**self.climb, "first_plug": E})
        only, _ = body_direct_climb(*args, {**self.climb, "first_plug": {**E, "start_phases": "ngram_only"}})
        self.assertLess(only.evaluations, full.evaluations)
        self.assertGreater(only.evaluations, base.evaluations)
        self.assertGreaterEqual(only.score_per_letter, base.score_per_letter)


@unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
class OptionBatchedParityTests(Fixture):
    def test_batched_ends_on_the_reference_plugboard_after_the_same_evaluations(self):
        generator = random.Random(53)
        for length in (167, 60):
            body = list(self.body[:length])
            if length == 60:
                body[7] = body[20] = -1
            message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(body))
            for spec in OPTION_SPECS:
                names = generator.sample(["I", "II", "III", "IV", "V"], 3)
                row = [generator.randrange(26) for _ in range(6)]
                settings = {**self.climb, "first_plug": spec}
                outcome, _ = body_direct_climb([message], names, row[:3], [row[3:]], self.scorer, self.reflector, settings)
                plugboard, evaluations = stecker_batch.BatchedClimber(
                    self.scorer.bigram, self.scorer.combined, body, settings
                ).climb(self.table(names, row, body))
                self.assertEqual((tuple(plugboard), evaluations), (outcome.plugboard, outcome.evaluations), (length, spec, names, row))


@unittest.skipUnless(GPU and stecker_batch.available(), "needs numpy, nvcc and a CUDA device")
class OptionCudaParityTests(CudaParityTests):
    """The CUDA kernel against the batched climb for every option combination."""

    # Inherited only for climb_both; the parent's own tests run once, in CudaParityTests.
    test_first_plug_climbs_match_the_batched_climb_exactly = None
    test_a_single_start_is_unchanged_by_the_multi_start_kernel = None
    test_the_cuda_split_climber_refuses_first_plug = None

    def test_option_climbs_match_the_batched_climb_exactly(self):
        generator = random.Random(67)
        masked = list(self.body)
        for position in (0, 1, 30, 31, 32, 90, 140):
            masked[position] = -1
        for body in (self.body, masked, self.body[:83]):
            rows = [
                (tuple(generator.sample(["I", "II", "III", "IV", "V"], 3)), [generator.randrange(26) for _ in range(6)])
                for _ in range(4)
            ]
            for window in (None, self.WINDOW):
                for spec in OPTION_SPECS:
                    self.assertEqual(self.climb_both(body, window, rows, spec), [], (len(body), window, spec))

    def test_the_cuda_kernel_agrees_when_the_cap_exceeds_max_passes(self):
        rows = [(("II", "V", "III"), [3, 4, 5, 6, 7, 8])]
        spec = {"letters": "E", "ic_passes": 10_000}
        self.assertEqual(self.climb_both(self.body, None, rows, spec), [])
        self.assertEqual(self.climb_both(self.body, None, rows, E), [])


@unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
class OptionPreflightTests(Fixture):
    def test_the_preflight_checks_every_declared_option_spec(self):
        config = copy.deepcopy(self.config)
        config["climb"] = {**self.climb, "engine": "batched"}
        config["batched_climb_parity"] = {"seed": 9, "samples": 2}
        config["end_to_end_power"] = {"arms": [
            {"id": "r", "ring_rule": "held", "right_ring": "A", "first_plug": {"letters": "ENR", "start_phases": "ngram_only"}},
            {"id": "e4", "ring_rule": "held", "right_ring": "A", "first_plug": {"letters": "E", "ic_passes": 4}},
        ]}
        self.assertEqual(len(stecker_controls.configured_first_plugs(config)), 2)
        report = stecker_controls.first_plug_parity_report(config, self.scorer, self.reflector, "batched")
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["climbs_compared"], 2 * 2)


if __name__ == "__main__":
    unittest.main()
