"""The visualizer page is current and its JS agrees with the Python pipeline."""

from __future__ import annotations

import json
import pathlib
import random
import shutil
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_visualizer  # noqa: E402
import enigma  # noqa: E402
import enigma_fast  # noqa: E402
from stecker_climb import coincidence_of_decryption, run_climb_phases  # noqa: E402
from stecker_scoring import FastNgramScorer  # noqa: E402

NODE = shutil.which("node")

# Run with node -e, so nothing is written into the checkout.
HARNESS = r"""
const job = JSON.parse(require("fs").readFileSync(0, "utf8"));
const C = require(job.core);
const D = job.data;
const out = {};
out.crypt = job.crypt.map((c) => new C.Machine(D, c).crypt(c.text));
out.tables = job.tables.map((t) => Array.from(C.positionTable(D, t.rotors, t.rings, t.positions, t.length)));
out.sweep = Array.from(C.sweepStarts(D, job.sweep.rotors, job.sweep.rings, job.sweep.body, job.sweep.from, job.sweep.to));
const scorer = new C.NgramScorer(D.scorer);
const c = job.climb;
const table = C.positionTable(D, c.rotors, c.rings, c.positions, c.body.length);
out.ngram = job.ngram_boards.map((pb) => scorer.scoreDecryption(table, c.body, pb));
out.ic = job.ngram_boards.map((pb) => C.coincidenceOfDecryption(table, c.body, pb));
const result = C.runClimbPhases(D.climb.phases, {
  index_of_coincidence: (pb) => C.coincidenceOfDecryption(table, c.body, pb),
  ngram: (pb) => scorer.scoreDecryption(table, c.body, pb),
}, D.climb);
out.climb = C.plugPairs(result.plugboard);
process.stdout.write(JSON.stringify(out));
"""


class VisualizerTest(unittest.TestCase):
    def test_committed_page_is_current(self) -> None:
        committed = build_visualizer.OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(
            committed,
            build_visualizer.render_standalone(),
            "visualizer/enigma-visualizer.html is stale; run python3 scripts/build_visualizer.py",
        )

    def test_page_embeds_the_repository_sources(self) -> None:
        data = build_visualizer.page_data()
        for name, spec in data["rotors"].items():
            self.assertEqual(tuple(spec), enigma.ROTOR_WIRINGS[name])
        self.assertEqual(data["reflector"], enigma.REFLECTOR_B)
        demo = data["demo"]
        self.assertEqual(len(demo["plaintext"]), 167)
        self.assertEqual(len(demo["plugboard"].split()), 10)

    @unittest.skipIf(NODE is None, "node is not installed")
    def test_javascript_matches_the_python_pipeline(self) -> None:
        data = build_visualizer.page_data()
        rng = random.Random(1941)
        letters = enigma.A

        crypt_cases = [
            {"rotors": ["I", "II", "III"], "rings": "AAA", "positions": "AAA", "plugboard": "", "text": "AAAAA"},
            {"rotors": ["II", "IV", "V"], "rings": "BUL", "positions": "WXC", "plugboard": "AV BS CG DL FU HZ IN KM OW RX", "text": "KCH"},
        ]
        for _ in range(12):
            pool = list(letters)
            rng.shuffle(pool)
            crypt_cases.append(
                {
                    "rotors": rng.sample(build_visualizer.ARMY_WHEELS, 3),
                    "rings": "".join(rng.choice(letters) for _ in range(3)),
                    "positions": "".join(rng.choice(letters) for _ in range(3)),
                    "plugboard": " ".join(pool[2 * i] + pool[2 * i + 1] for i in range(rng.randint(0, 13))),
                    "text": "".join(rng.choice(letters) for _ in range(700)),  # crosses every turnover
                }
            )
        table_cases = [
            {"rotors": case["rotors"], "rings": case["rings"], "positions": case["positions"], "length": 400}
            for case in crypt_cases[2:6]
        ]

        demo = data["demo"]
        ciphertext = enigma.EnigmaI(demo["rotors"], demo["rings"], demo["message_key"], demo["plugboard"]).crypt(
            demo["plaintext"]
        )
        body = list(enigma_fast.text_to_indices(ciphertext))
        sweep = {"rotors": demo["rotors"], "rings": demo["rings"], "body": body, "from": 13000, "to": 13400}
        boards = [list(range(26)), list(enigma_fast.plugboard_table(demo["plugboard"]))]
        for _ in range(4):
            pool = list(range(26))
            rng.shuffle(pool)
            board = list(range(26))
            for i in range(0, 20, 2):
                board[pool[i]], board[pool[i + 1]] = pool[i + 1], pool[i]
            boards.append(board)
        job = {
            "core": str(ROOT / "visualizer" / "enigma-core.js"),
            "data": data,
            "crypt": crypt_cases,
            "tables": table_cases,
            "sweep": sweep,
            "climb": {"rotors": demo["rotors"], "rings": demo["rings"], "positions": demo["message_key"], "body": body},
            "ngram_boards": boards,
        }
        completed = subprocess.run(
            [NODE, "-e", HARNESS],
            input=json.dumps(job),
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        result = json.loads(completed.stdout)

        self.assertEqual(result["crypt"][0], "BDZGO")
        self.assertEqual(result["crypt"][1], "BLA")
        for case, got in zip(crypt_cases, result["crypt"]):
            expected = enigma.EnigmaI(case["rotors"], case["rings"], case["positions"], case["plugboard"]).crypt(case["text"])
            self.assertEqual(got, expected, case)

        for case, got in zip(table_cases, result["tables"]):
            order = [enigma_fast.rotor_tables(name) for name in case["rotors"]]
            rings = [enigma.idx(c) for c in case["rings"]]
            positions = [enigma.idx(c) for c in case["positions"]]
            self.assertEqual(got, list(enigma_fast.position_permutations(order, rings, positions, case["length"])))

        order = [enigma_fast.rotor_tables(name) for name in demo["rotors"]]
        rings = [enigma.idx(c) for c in demo["rings"]]
        identity = list(range(26))
        for offset, got in enumerate(result["sweep"]):
            start = sweep["from"] + offset
            positions = [start // 676, start // 26 % 26, start % 26]
            table = enigma_fast.position_permutations(order, rings, positions, len(body))
            self.assertAlmostEqual(got, coincidence_of_decryption(table, body, identity), places=12)

        scorer = FastNgramScorer(json.loads(build_visualizer.SCORER.read_text(encoding="utf-8"))["scorer"])
        table = enigma_fast.position_permutations(order, rings, [enigma.idx(c) for c in demo["message_key"]], len(body))
        for board, ngram, ic in zip(boards, result["ngram"], result["ic"]):
            self.assertAlmostEqual(ngram, scorer.score_decryption(table, body, board), places=7)
            self.assertAlmostEqual(ic, coincidence_of_decryption(table, body, board), places=12)

        plugboard, _, _ = run_climb_phases(
            data["climb"]["phases"],
            {
                "index_of_coincidence": lambda pb: coincidence_of_decryption(table, body, pb),
                "ngram": lambda pb: scorer.score_decryption(table, body, pb),
            },
            len(body),
            data["climb"],
        )
        self.assertEqual(result["climb"], enigma_fast.plugboard_pairs(plugboard))
        self.assertEqual(result["climb"], demo["plugboard"])


if __name__ == "__main__":
    unittest.main()
