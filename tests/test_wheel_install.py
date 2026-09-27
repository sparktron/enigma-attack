"""Exercise installed defaults without importing modules from the checkout."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import venv


class WheelInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project = pathlib.Path(__file__).resolve().parents[1]
        cls._temporary = tempfile.TemporaryDirectory()
        cls.temp = pathlib.Path(cls._temporary.name)
        wheels = cls.temp / "wheels"
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", str(project),
             "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheels)],
            check=True, capture_output=True, text=True,
        )
        environment = cls.temp / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        subprocess.run(
            [str(environment / "bin" / "python"), "-m", "pip", "install", "--no-deps",
             str(next(wheels.glob("*.whl")))],
            check=True, capture_output=True, text=True,
        )
        cls.binaries = environment / "bin"
        cls.environment_variables = dict(os.environ)
        cls.environment_variables.pop("PYTHONPATH", None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_installed_phase7_reads_its_resources_and_stops_at_the_gate(self) -> None:
        """The gate fires only after every installed input has been read.

        ``phase7`` audits the corpus grouping and validates the published n-gram
        scorer before it reaches the Phase 5 conservation exclusion, so a run
        that stops there has already loaded the corpus, both frequency tables,
        and the Phase 6 and Phase 7 configurations out of the installed share
        directory.  That is what this test is for; the exclusion itself is
        covered by the Phase 5 and Phase 6 unit tests.
        """

        completed = subprocess.run(
            [str(self.binaries / "enigma-phase7"),
             "--output", str(self.temp / "phase7.json")],
            cwd=self.temp, env=self.environment_variables,
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("letter conservation", completed.stderr)
        self.assertIn("QTXMA", completed.stderr)

    def test_installed_default_outputs_resolve_under_the_cwd(self) -> None:
        """Inputs come from the installed share directory, outputs from the cwd."""

        working = self.temp / "elsewhere"
        working.mkdir()
        completed = subprocess.run(
            [str(self.binaries / "python"), "-c",
             "import json, resources;"
             "print(json.dumps({"
             "'root': str(resources.resource_root()),"
             "'default': str(resources.output_path('example.json')),"
             "'relative': str(resources.resolve_output('artifacts/example.json')),"
             "}))"],
            cwd=working, env=self.environment_variables,
            check=True, capture_output=True, text=True,
        )
        paths = json.loads(completed.stdout)
        self.assertTrue(pathlib.Path(paths["root"], "corpus.json").is_file())
        self.assertEqual(
            paths["default"], str(working / "artifacts" / "example.json")
        )
        self.assertEqual(
            paths["relative"], str(working / "artifacts" / "example.json")
        )


if __name__ == "__main__":
    unittest.main()
