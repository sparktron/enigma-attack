"""The optional CUDA climb engine: exact parity with the batched climb.

GPU tests skip when numpy, nvcc or a CUDA device is missing.  The engine
selection and fingerprint tests run everywhere.
"""

import json
import pathlib
import random
import unittest
from unittest import mock

import enigma_fast
import phase1_stecker as stecker
import stecker_batch
import stecker_cuda
from stecker_climb import climb_windows, windowed_climb
from stecker_controls import cuda_climb_parity_report, run_preflight
from stecker_scoring import FastNgramScorer
from stecker_space import RingRule, resolve_axis, rotor_order_space
from stecker_sweeps import _worker_chunk, _worker_init, resolve_engine, sweep_fingerprint, sweep_slice
from stecker_traffic import Traffic, traffic_from_corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
V4_CONFIG = ROOT / "experiments/phase1-body-direct-sweep-v4/config.json"
# The first line of a copy of the running v4 checkpoint
# (build/phase1-body-direct-sweep-v4.checkpoint.jsonl, copied read-only on
# 2026-10-08 after 150 chunks; the sweep started from 31dfbcc).
V4_CHECKPOINT_FINGERPRINT = "56cd4f962278e22c38dcac0cbade2d7aac8a3e5249a7e74673f1afcfae3e00d9"
GPU = stecker_cuda.available()
WINDOW = {"kind": "head_tail", "letters": 117}


def v4_message(config):
    traffic = traffic_from_corpus(
        stecker.resolve_path(config["corpus"]), config["target"]["date"],
        config["target"]["messages"],
    )
    return {message.designator: message for message in traffic}[
        config["body_direct_sweep"]["message"]
    ]


def v4_fingerprint(engine):
    config = stecker.load_config(V4_CONFIG)
    settings = config["body_direct_sweep"]
    message = v4_message(config)
    starts = [
        (left, middle, right)
        for left in resolve_axis(settings["start_left"])
        for middle in resolve_axis(settings["start_middle"])
        for right in resolve_axis(settings["start_right"])
    ]
    return sweep_fingerprint(
        message.body, config["scorer"], config["climb"],
        RingRule.from_config(settings, len(message.body)), starts, int(settings["keep"]),
        engine, enigma_fast.reflector_table(config["machine"]["reflector"]),
    )


class EngineSelectionTests(unittest.TestCase):
    def test_auto_never_picks_cuda(self):
        with mock.patch.object(stecker_cuda, "available", return_value=True):
            self.assertIn(resolve_engine({"engine": "auto"}), ("batched", "reference"))
            self.assertEqual(resolve_engine({"engine": "cuda"}), "cuda")
            self.assertEqual(resolve_engine({}), "reference")

    def test_cuda_fails_loudly_without_a_gpu_build(self):
        with mock.patch.object(stecker_cuda, "available", return_value=False):
            with self.assertRaises(RuntimeError):
                resolve_engine({"engine": "cuda"})

    def test_cuda_refuses_the_split_point_climb(self):
        with self.assertRaisesRegex(ValueError, "split-point"):
            resolve_engine({"engine": "cuda", "split": {"ic_grid": 32}})

    def test_v4_fingerprint_is_unchanged_so_the_cpu_sweep_can_resume(self):
        config = stecker.load_config(V4_CONFIG)
        if stecker_batch.available():
            self.assertEqual(resolve_engine(config["climb"]), "batched")
        self.assertEqual(v4_fingerprint("batched"), V4_CHECKPOINT_FINGERPRINT)
        checkpoint = ROOT / "build/phase1-body-direct-sweep-v4.checkpoint.jsonl"
        if checkpoint.exists():
            with checkpoint.open(encoding="utf-8") as handle:
                first = json.loads(handle.readline())
            self.assertEqual(first["fingerprint"], V4_CHECKPOINT_FINGERPRINT)
        # The engine is part of the identity: a GPU run never resumes a CPU checkpoint.
        self.assertNotEqual(v4_fingerprint("cuda"), V4_CHECKPOINT_FINGERPRINT)


@unittest.skipUnless(stecker_batch.available(), "numpy is not installed")
class PairwisePlanTests(unittest.TestCase):
    def test_the_plan_reproduces_numpy_row_sums_bit_for_bit(self):
        import numpy as np

        def leaf(values):
            if len(values) < 8:
                total = 0.0
                for value in values:
                    total += value
                return total
            r = list(values[:8])
            i, whole = 8, len(values) - len(values) % 8
            while i < whole:
                for j in range(8):
                    r[j] += values[i + j]
                i += 8
            total = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]))
            for value in values[i:]:
                total += value
            return total

        def planned(values):
            stack, at = [], 0
            for token in stecker_cuda.pairwise_plan(len(values)):
                if token < 0:
                    right, left = stack.pop(), stack.pop()
                    stack.append(left + right)
                else:
                    stack.append(leaf(values[at:at + token]))
                    at += token
            return stack[0]

        generator = np.random.default_rng(3)
        table = generator.normal(-8.0, 3.0, 17576)
        for count in [0, 1, 7, 8, 9, 115, 128, 129, 165, 300, 511]:
            rows = table[generator.integers(0, 17576, size=(5, count))]
            sums = rows.sum(axis=1)
            for row, expected in zip(rows, sums):
                self.assertEqual(planned([float(x) for x in row]), float(expected), count)


@unittest.skipUnless(GPU, f"cuda engine unavailable: {stecker_cuda.unavailable_reason()}")
class CudaEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = stecker.load_config(V4_CONFIG)
        cls.scorer = FastNgramScorer(cls.config["scorer"])
        cls.reflector = enigma_fast.reflector_table("B")
        cls.climb = {k: v for k, v in cls.config["climb"].items() if k != "window"}

    def test_gpu_position_tables_equal_enigma_fast(self):
        import numpy as np

        generator = random.Random(17)
        wheels = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
        for _ in range(12):
            names = generator.sample(wheels, 3)
            length = generator.randrange(1, 400)
            rows = [[generator.randrange(26) for _ in range(6)] for _ in range(40)]
            tables = stecker_cuda.position_tables(names, np.asarray(rows), length, self.reflector)
            order = [enigma_fast.rotor_tables(name) for name in names]
            for row, table in zip(rows, tables):
                expected = enigma_fast.position_permutations(
                    order, row[:3], row[3:], length, self.reflector
                )
                self.assertEqual(table.tolist(), expected)

    def test_the_library_cache_is_keyed_by_gpu_architecture(self):
        nvcc = stecker_cuda._nvcc()
        here = stecker_cuda.compute_capability()
        ampere = stecker_cuda.library_path(nvcc, (8, 6))
        turing = stecker_cuda.library_path(nvcc, (7, 5))
        self.assertNotEqual(ampere, turing)
        self.assertIn("sm75", turing.name)
        self.assertIn(f"sm{here[0]}{here[1]}", stecker_cuda.library_path(nvcc, here).name)

    def test_settings_array_is_rule_settings_in_order(self):
        names = ("II", "V", "I")
        starts = [(left, middle, right) for left in (0, 9) for middle in (2, 17) for right in (4, 25)]
        for rule in (
            RingRule("held", (3, 7, 0), (0, 5, 25), 167),
            RingRule("middle_past_notch", (1, 0, 0), tuple(range(26)), 167),
            RingRule("middle_complete", (0, 0, 0), tuple(range(26)), 167),
        ):
            expected = [list(rings) + list(start) for rings, start in rule.settings(names, starts)]
            self.assertEqual(stecker_cuda.settings_array(rule, names, starts).tolist(), expected)

    def climb_both(self, body, window, settings):
        climb = {**self.climb, "window": window} if window else self.climb
        gpu = stecker_cuda.CudaClimber(
            self.scorer.bigram, self.scorer.combined, body, climb, self.reflector
        )
        mismatches = []
        for names, row in settings:
            order = [enigma_fast.rotor_tables(name) for name in names]
            table = enigma_fast.position_permutations(order, row[:3], row[3:], len(body), self.reflector)
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

    def test_climbs_match_the_batched_climb_exactly(self):
        generator = random.Random(23)
        message = list(v4_message(self.config).body)
        masked = list(message)
        for position in (0, 1, 30, 31, 32, 90, 140):
            masked[position] = -1
        short = message[:83]
        for body in (message, masked, short):
            settings = [
                (tuple(generator.sample(["I", "II", "III", "IV", "V"], 3)),
                 [generator.randrange(26) for _ in range(6)])
                for _ in range(8)
            ]
            for window in (None, WINDOW):
                self.assertEqual(self.climb_both(body, window, settings), [], (len(body), window))

    def test_a_cuda_chunk_record_equals_the_batched_chunk_record(self):
        message = v4_message(self.config)
        rule = RingRule.from_config(self.config["body_direct_sweep"], len(message.body))
        names = ("IV", "II", "V")
        starts = [(left, 6, right) for left in (0, 13) for right in (2, 21)]
        records = {}
        for engine in ("batched", "cuda"):
            _worker_init(
                dict(self.config["scorer"]), list(message.body),
                {**self.config["climb"], "engine": engine}, list(self.reflector),
            )
            records[engine] = _worker_chunk((3, "IV-II-V/6", names, starts, rule, 25))
        _worker_init(dict(self.config["scorer"]), list(message.body), dict(self.config["climb"]),
                     list(self.reflector))
        self.assertEqual(records["cuda"]["evaluated"], 4 * 9 * 26)
        self.assertEqual(json.dumps(records["cuda"]), json.dumps(records["batched"]))

    def test_a_cuda_sweep_slice_equals_the_batched_sweep_slice(self):
        message = Traffic("S", (0, 0, 0), (0, 0, 0), tuple(v4_message(self.config).body[:150]))
        arguments = (
            message, [("I", "II", "III"), ("V", "III", "II")], (0, 0, 0),
            [(0, middle, right) for middle in (4, 20) for right in range(3)],
            self.config["scorer"], self.reflector,
        )
        for window in (None, WINDOW):
            climb = {**self.climb, **({"window": window} if window else {})}
            batched = sweep_slice(*arguments, {**climb, "engine": "batched"}, 5, 1)
            cuda = sweep_slice(*arguments, {**climb, "engine": "cuda"}, 5, 4)
            self.assertEqual(cuda[:3], batched[:3])
            self.assertEqual(cuda[3]["engine"], "cuda")

    def test_the_preflight_checks_cuda_against_batched_and_blocks_on_a_mismatch(self):
        config = {
            **self.config,
            "climb": {**self.config["climb"], "engine": "cuda"},
            "kernel_parity": {"seed": 1, "samples": 2},
            "scorer_parity": {**self.config["scorer_parity"], "samples": 2},
            "batched_climb_parity": {"seed": 3, "samples": 3},
        }
        report = run_preflight(config, self.scorer)
        self.assertTrue(report["checks"]["batched_climb_matches_reference"])
        self.assertTrue(report["checks"]["cuda_climb_matches_batched"])
        self.assertEqual(report["cuda_climb_parity"]["worst_absolute_score_difference"], 0.0)
        self.assertTrue(report["passed"])

        original = stecker_cuda.CudaClimber.climb_one

        def wrong(self, *arguments):
            plugboard, evaluations, score, window = original(self, *arguments)
            return plugboard, evaluations + 1, score, window

        with mock.patch.object(stecker_cuda.CudaClimber, "climb_one", wrong):
            broken = cuda_climb_parity_report(config, self.scorer, self.reflector)
        self.assertFalse(broken["passed"])
        self.assertEqual(broken["identical_evaluation_counts"], 0)

    def test_the_cuda_engine_refuses_what_it_does_not_implement(self):
        body = list(v4_message(self.config).body)
        with self.assertRaisesRegex(ValueError, "split-point"):
            stecker_cuda.CudaClimber(
                self.scorer.bigram, self.scorer.combined, body,
                {**self.climb, "split": {"ic_grid": 32}}, self.reflector,
            )
        with self.assertRaises(ValueError):
            stecker_cuda.CudaClimber(
                self.scorer.bigram, self.scorer.combined, [-1] * 20 + [3], self.climb, self.reflector
            )


if __name__ == "__main__":
    unittest.main()
