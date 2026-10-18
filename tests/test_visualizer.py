"""The visualizer page is current and its JS agrees with the Python pipeline."""

from __future__ import annotations

import json
import pathlib
import random
import shutil
import subprocess
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_visualizer  # noqa: E402
import enigma  # noqa: E402
import enigma_fast  # noqa: E402
from provenance import sha256_text  # noqa: E402
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
const objectives = {
  index_of_coincidence: (pb) => C.coincidenceOfDecryption(table, c.body, pb),
  ngram: (pb) => scorer.scoreDecryption(table, c.body, pb),
};
// runClimbPhases drains climbPhases, the generator the page draws pass by pass.
out.climbs = c.settings.map((settings) => C.runClimbPhases(D.climb.phases, objectives, settings).records);
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

    def test_demo_is_the_recorded_control(self) -> None:
        demo = build_visualizer.page_data()["demo"]
        artifact = json.loads((ROOT / "artifacts" / f"{demo['experiment_id']}.json").read_text(encoding="utf-8"))
        control = next(c for c in artifact["positive_controls"]["evaluated"] if c["id"] == build_visualizer.DEMO_CONTROL)
        recorded = control["known_key"]
        message = next(m for m in recorded["messages"] if m["designator"] == demo["designator"])
        self.assertEqual(demo["rotors"], recorded["rotor_order_left_to_right"])
        self.assertEqual(demo["rings"], recorded["rings"])
        self.assertEqual(demo["plugboard"], recorded["plugboard"])
        self.assertEqual(control["recovered_plugboard"], recorded["plugboard"])
        self.assertEqual(sha256_text(demo["plaintext"]), message["plaintext_sha256"])
        self.assertEqual(demo["message_key"], message["true_message_key"])
        indicator = enigma.EnigmaI(demo["rotors"], demo["rings"], demo["grundstellung"], demo["plugboard"]).crypt(
            demo["message_key"]
        )
        self.assertEqual([demo["grundstellung"], indicator], message["indicator"])

    def test_prose_quotes_the_sources(self) -> None:
        data = build_visualizer.page_data()
        demo = data["demo"]
        facts = build_visualizer.measured(len(demo["plaintext"]), len(demo["plugboard"].split()))
        data["climb"].update(max_pairs=7, max_passes=19)
        facts["ic_rank"]["retention"] = 0.4375
        facts["climb_power"].update(recovered=17, draws=33)
        facts["indicator_sweep"]["daily_keys"] = 1234567
        with mock.patch.object(build_visualizer, "page_data", return_value=data), mock.patch.object(
            build_visualizer, "measured", return_value=facts
        ):
            page = build_visualizer.render_fragment()
        for text in ("at most 7 pairs and 19 passes per phase", "<b>44%</b>", "<b>17 / 33</b>", "<b>1,234,567</b>"):
            self.assertIn(text, page)
        self.assertNotRegex(page, r"\{\{\w+\}\}")

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
        capped = {**data["climb"], "max_passes": 3}  # stops the IC phase short of converging
        job = {
            "core": str(ROOT / "visualizer" / "enigma-core.js"),
            "data": data,
            "crypt": crypt_cases,
            "tables": table_cases,
            "sweep": sweep,
            "climb": {
                "rotors": demo["rotors"],
                "rings": demo["rings"],
                "positions": demo["message_key"],
                "body": body,
                "settings": [data["climb"], capped],
            },
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

        scorer = FastNgramScorer(json.loads(build_visualizer.CALIBRATION.read_text(encoding="utf-8"))["scorer"])
        table = enigma_fast.position_permutations(order, rings, [enigma.idx(c) for c in demo["message_key"]], len(body))
        for board, ngram, ic in zip(boards, result["ngram"], result["ic"]):
            self.assertAlmostEqual(ngram, scorer.score_decryption(table, body, board), places=7)
            self.assertAlmostEqual(ic, coincidence_of_decryption(table, body, board), places=12)

        objectives = {
            "index_of_coincidence": lambda pb: coincidence_of_decryption(table, body, pb),
            "ngram": lambda pb: scorer.score_decryption(table, body, pb),
        }
        for settings, got in zip(job["climb"]["settings"], result["climbs"]):
            _, records, _ = run_climb_phases(data["climb"]["phases"], objectives, len(body), settings)
            self.assertEqual(
                [(r["objective"], r["plugboard"], r["passes"]) for r in got],
                [(r["objective"], r["plugboard"], r["passes"]) for r in records],
            )
        full, short = result["climbs"]
        self.assertEqual(full[-1]["plugboard"], demo["plugboard"])
        self.assertTrue(all(r["converged"] for r in full))
        self.assertFalse(short[0]["converged"])


if __name__ == "__main__":
    unittest.main()
