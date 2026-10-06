"""The split-point climb's objectives against a direct, hypothesis-by-hypothesis reference."""

import json
import pathlib
import random
import unittest

import enigma_fast
import stecker_batch
import stecker_split
from enigma import EnigmaI
from stecker_power import perturb_ciphertext
from stecker_scoring import FastNgramScorer
from stecker_traffic import normalize_plaintext, random_plugboard

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "experiments/phase1-middle-complete-power-v1/config.json").read_text(encoding="utf-8"))
SETTINGS = {**CONFIG["climb"], "engine": "batched", "split": {"ic_grid": 16}}
PLAINTEXT = normalize_plaintext(CONFIG["end_to_end_power"]["plaintext"])
WHEELS = ["I", "II", "III", "IV", "V"]


def planted(seed, length, fault, mask_at=None):
    """A planted key, its (possibly faulty) ciphertext and the n + 1 row position table."""
    gen = random.Random(seed)
    order = tuple(gen.sample(WHEELS, 3))
    rings = tuple(gen.randrange(26) for _ in range(3))
    start = tuple(gen.randrange(26) for _ in range(3))
    plugboard = random_plugboard(gen, 10)
    clean = EnigmaI(
        rotors=order,
        rings="".join(chr(65 + v) for v in rings),
        positions="".join(chr(65 + v) for v in start),
        plugboard=plugboard,
    ).crypt(PLAINTEXT[:length])
    text, perturbation = perturb_ciphertext(clean, fault, gen) if fault else (clean, {"kind": "none"})
    body = list(enigma_fast.text_to_indices(text))
    if mask_at is not None:
        body[mask_at] = -1
    reflector = enigma_fast.reflector_table("B")
    table = enigma_fast.position_permutations(
        [enigma_fast.rotor_tables(name) for name in order], rings, start, len(body) + 1, reflector
    )
    expected = enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard))
    return body, table, perturbation, expected, enigma_fast.plugboard_table(plugboard)


def random_boards(gen, count):
    boards = []
    for _ in range(count):
        board = list(range(26))
        for _ in range(gen.randrange(0, 11)):
            pool = [x for x in range(26) if board[x] == x]
            a, b = gen.sample(pool, 2)
            board[a], board[b] = b, a
        boards.append(board)
    return boards


@unittest.skipUnless(stecker_batch.available(), "needs numpy")
class ObjectiveParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = FastNgramScorer(CONFIG["scorer"])

    def climber(self, body):
        return stecker_split.SplitClimber(self.scorer.bigram, self.scorer.combined, body, SETTINGS)

    def check(self, body, table, seed, samples=4):
        import numpy as np

        climber = self.climber(body)
        grid = np.asarray(table, dtype=np.int64).reshape(len(body) + 1, 26)
        boards = random_boards(random.Random(seed), samples)
        batched = climber._ngram(np.asarray(boards, dtype=np.int64), grid)
        coincidence = climber._coincidence(np.asarray(boards, dtype=np.int64), grid)
        for index, board in enumerate(boards):
            reference, which = stecker_split.reference_ngram_objective(self.scorer, table, body, board)
            self.assertAlmostEqual(float(batched[index]), reference, places=6)
            self.assertAlmostEqual(
                float(coincidence[index]),
                stecker_split.reference_coincidence_objective(table, body, board, 16),
                places=9,
            )
            score, found = climber.best_hypothesis(board, grid)
            self.assertAlmostEqual(score, reference, places=6)
            self.assertEqual(found, which)

    def test_a_clean_message(self):
        body, table, *_ = planted(1, 60, None)
        self.check(body, table, 11)

    def test_a_message_with_a_dropped_letter(self):
        for seed in range(2, 40):
            body, table, fault, *_ = planted(seed, 60, "indel")
            if fault["kind"] == "deletion":
                return self.check(body, table, seed)
        self.fail("no deletion drawn")

    def test_a_message_with_an_inserted_letter(self):
        for seed in range(2, 40):
            body, table, fault, *_ = planted(seed, 60, "indel")
            if fault["kind"] == "insertion":
                return self.check(body, table, seed)
        self.fail("no insertion drawn")

    def test_a_message_that_already_carries_masks(self):
        body, table, *_ = planted(5, 60, None, mask_at=20)
        body[41] = -1
        self.check(body, table, 15)

    def test_the_hypothesis_count(self):
        self.assertEqual(len(stecker_split.hypotheses(10)), 1 + 9 + 8)


@unittest.skipUnless(stecker_batch.available(), "needs numpy")
class BlockingAndSweepTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = FastNgramScorer(CONFIG["scorer"])

    def test_blocking_candidates_changes_no_number(self):
        import numpy as np

        body, table, *_ = planted(7, 80, "indel")
        grid = np.asarray(table, dtype=np.int64).reshape(len(body) + 1, 26)
        boards = np.asarray(random_boards(random.Random(3), 150), dtype=np.int64)
        whole = stecker_split.SplitClimber(
            self.scorer.bigram, self.scorer.combined, body, {**SETTINGS, "split": {"ic_grid": 16, "block": 0}}
        )
        blocked = stecker_split.SplitClimber(
            self.scorer.bigram, self.scorer.combined, body, {**SETTINGS, "split": {"ic_grid": 16, "block": 37}}
        )
        self.assertTrue(np.array_equal(whole._ngram(boards, grid), blocked._ngram(boards, grid)))
        self.assertTrue(np.array_equal(whole._coincidence(boards, grid), blocked._coincidence(boards, grid)))

    def test_the_sweep_runs_the_split_climb_and_labels_the_hypothesis(self):
        from stecker_space import RingRule
        from stecker_sweeps import sweep_slice
        from stecker_traffic import Traffic

        body, _, perturbation, _, _ = planted(11, 60, "indel")
        message = Traffic("T", (0, 0, 0), (0, 0, 0), tuple(body))
        reflector = enigma_fast.reflector_table("B")
        ranked, evaluated, _, _ = sweep_slice(
            message, [("I", "II", "III")], (0, 0, 0), [(0, 0, 0), (0, 0, 1)],
            CONFIG["scorer"], reflector, SETTINGS, 2, 1,
        )
        self.assertEqual(evaluated, 2)
        self.assertEqual(len(ranked[0]["split"]), 2)
        self.assertIn(ranked[0]["split"][0], ("clean", "deletion", "insertion"))

    def test_a_window_and_a_split_cannot_be_combined(self):
        from stecker_sweeps import _worker_init

        with self.assertRaises(ValueError):
            _worker_init(
                CONFIG["scorer"], [0] * 30,
                {**SETTINGS, "window": {"kind": "head_tail", "letters": 20}}, [0] * 26,
            )


@unittest.skipUnless(stecker_batch.available(), "needs numpy")
class RecoveryTest(unittest.TestCase):
    """At the true setting the climb finds the plugboard and where the fault is."""

    @classmethod
    def setUpClass(cls):
        cls.scorer = FastNgramScorer(CONFIG["scorer"])

    def run_climb(self, seed, fault):
        body, table, perturbation, expected, _ = planted(seed, 167, fault)
        climber = stecker_split.SplitClimber(self.scorer.bigram, self.scorer.combined, body, SETTINGS)
        plugboard, evaluations, score, hypothesis = climber.climb(table)
        return perturbation, enigma_fast.plugboard_pairs(plugboard), expected, hypothesis, evaluations

    def test_it_recovers_clean_messages_and_labels_them_clean_away_from_the_ends(self):
        hits = 0
        for seed in range(6):
            _, found, expected, hypothesis, _ = self.run_climb(seed, None)
            hits += found == expected
            if found == expected and hypothesis != ("clean", None):
                # A fault hypothesis near an end swaps only a few correct terms
                # for wrong ones, so the best of ~330 noisy hypotheses can come
                # out ahead by chance there and nowhere else.
                self.assertTrue(hypothesis[1] <= 10 or hypothesis[1] >= 157, hypothesis)
        self.assertGreaterEqual(hits, 3)

    def test_it_recovers_a_middle_third_fault_and_locates_it(self):
        located = 0
        tried = 0
        for seed in range(100, 140):
            body, table, perturbation, expected, _ = planted(seed, 167, "indel")
            if not 70 <= perturbation["position"] <= 100:
                continue
            tried += 1
            climber = stecker_split.SplitClimber(self.scorer.bigram, self.scorer.combined, body, SETTINGS)
            plugboard, _, _, hypothesis = climber.climb(table)
            if enigma_fast.plugboard_pairs(plugboard) == expected:
                located += 1
                self.assertEqual(hypothesis[0], perturbation["kind"])
                self.assertLessEqual(abs(hypothesis[1] - perturbation["position"]), 3)
            if tried == 6:
                break
        self.assertGreaterEqual(located, 1)


if __name__ == "__main__":
    unittest.main()
