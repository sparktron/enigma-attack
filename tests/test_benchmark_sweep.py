"""The benchmark script's argument handling for the split-point climb."""

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "benchmark_sweep.py"
SPEC = importlib.util.spec_from_file_location("benchmark_sweep", SCRIPT)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class SplitArgumentsTest(unittest.TestCase):
    def test_split_grid_alone_does_not_ask_for_the_reference_engine(self):
        # parse only: a bad engine list would exit before any sweep ran
        with self.assertRaises(SystemExit) as stopped:
            bench.main(["--split-grid", "32", "--engines", "reference"])
        self.assertEqual(stopped.exception.code, 2)

    def test_compare_needs_a_split_grid(self):
        with self.assertRaises(SystemExit) as stopped:
            bench.main(["--compare"])
        self.assertEqual(stopped.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
