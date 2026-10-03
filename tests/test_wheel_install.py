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

    def run_installed(self, *command: str, cwd: pathlib.Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.binaries / command[0]), *command[1:]],
            cwd=cwd, env=self.environment_variables,
            capture_output=True, text=True,
        )

    def assert_installed_provenance(self, code: dict, *modules: str) -> None:
        """An installed copy is not a checkout, and must not pretend otherwise."""

        self.assertEqual(code["source"], "not_a_checkout")
        self.assertIsNone(code["commit"])
        self.assertIsNone(code["dirty"])
        for module in modules:
            self.assertIn(module, code["files_sha256"])

    def test_installed_phase1_stecker_reads_shipped_inputs_and_writes_under_the_cwd(self) -> None:
        """The default configuration ships, and a run lands in the cwd.

        The default calibration takes minutes, so the run uses the shipped
        indicator-sweep configuration with a wrong control key.  The positive
        control then fails after preflight has read the corpus and both
        frequency tables, and the gate stops the run before any target search.
        """

        working = self.temp / "stecker"
        working.mkdir()
        located = subprocess.run(
            [str(self.binaries / "python"), "-c",
             "import phase1_stecker; print(phase1_stecker.DEFAULT_CONFIG)"],
            cwd=working, env=self.environment_variables,
            check=True, capture_output=True, text=True,
        )
        self.assertTrue(pathlib.Path(located.stdout.strip()).is_file())

        share = pathlib.Path(located.stdout.strip()).parents[2]
        config = json.loads(
            (share / "experiments/phase1-indicator-sweep-v1/config.json").read_text(
                encoding="utf-8"
            )
        )
        config["positive_controls"][0]["key"]["rings"] = "AAA"
        (working / "wrong-control.json").write_text(json.dumps(config), encoding="utf-8")

        completed = self.run_installed(
            "enigma-phase1-stecker", "--config", "wrong-control.json", cwd=working
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        artifact = json.loads(
            (working / "artifacts/phase1-indicator-sweep-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(artifact["status"], "blocked_by_positive_control")
        self.assertIsNone(artifact["result"])
        self.assert_installed_provenance(
            artifact["code"], "phase1_stecker.py", "stecker_climb.py", "stecker_controls.py"
        )

    def test_installed_phase1_and_phase2_record_code_without_a_checkout(self) -> None:
        """Code is hashed where it is installed, not under the share directory."""

        working = self.temp / "phase1-phase2"
        working.mkdir()
        phase1 = self.run_installed(
            "enigma-phase1", "search", "--rings", "AAA", "--output", "phase1.json",
            cwd=working,
        )
        self.assertEqual(phase1.returncode, 0, phase1.stderr)
        certificate = json.loads((working / "phase1.json").read_text(encoding="utf-8"))
        self.assert_installed_provenance(
            certificate["implementation"]["code"], "enigma.py", "phase1.py"
        )

        phase2 = self.run_installed("enigma-phase2", "--output", "phase2.json", cwd=working)
        self.assertEqual(phase2.returncode, 0, phase2.stderr)
        network = json.loads((working / "phase2.json").read_text(encoding="utf-8"))
        self.assert_installed_provenance(network["code"], "phase2.py")

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
