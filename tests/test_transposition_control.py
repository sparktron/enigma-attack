"""The transposition machinery is exact at ragged lengths; the 5x7 control's failure was the search's."""

import json
import pathlib
import random
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import phase6  # noqa: E402
from phase7 import PublishedNgramScorer  # noqa: E402

CONTROL = "UMZUGGEPAEQTROSSUNDRESTKOMMANDOSTOPFENXSQRIFTLIQERBEFEHLUNTERWEGSXSCHNEIDDRX"
FIRST, SECOND = (3, 0, 4, 1, 2), (6, 1, 4, 0, 5, 2, 3)
ROTATING_FIRST = (4, 1, 0, 2, 3)


class RaggedTranspositionTest(unittest.TestCase):
    def test_untranspose_inverts_transpose_at_every_length(self):
        generator = random.Random(20261011)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for width in range(2, 8):
            for length in range(width, 80):
                text = "".join(generator.choice(letters) for _ in range(length))
                order = list(range(width))
                generator.shuffle(order)
                self.assertEqual(phase6.columnar_untranspose(phase6.columnar_transpose(text, order), order), text)

    def test_double_transposition_round_trips_the_5x7_control(self):
        ciphertext = phase6.double_columnar_transpose(CONTROL, FIRST, SECOND)
        self.assertEqual(phase6.double_columnar_untranspose(ciphertext, FIRST, SECOND), CONTROL)

    def test_one_other_key_reads_out_the_control_rotated_by_one_and_scores_lower(self):
        # The first-stage order with every column index moved one along, with the true
        # second stage, reads the plaintext with its last letter first: a different key,
        # not a filling disagreement. The history had said no key can do this.
        ciphertext = phase6.double_columnar_transpose(CONTROL, FIRST, SECOND)
        self.assertEqual(tuple((column + 1) % 5 for column in FIRST), ROTATING_FIRST)
        rotated = phase6.double_columnar_untranspose(ciphertext, ROTATING_FIRST, SECOND)
        self.assertEqual(rotated, CONTROL[-1] + CONTROL[:-1])
        config = json.loads((ROOT / "experiments/phase7-qtxma-source-and-scorer-v2/config.json").read_text(encoding="utf-8"))
        scorer = PublishedNgramScorer(config["scorer"])
        score = lambda text: (lambda raw, known: raw / known)(*scorer.score(text))
        self.assertGreater(score(CONTROL), score(rotated))
        self.assertLess(score(CONTROL) - score(rotated), 0.02)

    def test_exhaustive_search_dispatch_follows_the_state_limit(self):
        # 5 x 7 is 604,800 states: annealed under the recorded limit of 20,000,
        # exhaustive once the limit reaches it. Dispatch only; the full search is
        # in scripts/transposition_control_rank.py.
        class Exhaustive(Exception):
            pass

        for limit, exhaustive in ((20000, False), (604800, True)):
            with mock.patch.object(phase6, "_exhaustive_pair", side_effect=Exhaustive):
                call = lambda: phase6.search_double_transposition(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 3, [[5, 7]], training_fraction=0.75, seed=1,
                    max_exhaustive_states=limit, restarts=1, iterations=1,
                )
                if exhaustive:
                    with self.assertRaises(Exhaustive):
                        call()
                else:
                    self.assertEqual(call().method, "simulated_annealing")


if __name__ == "__main__":
    unittest.main()
