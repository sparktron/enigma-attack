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
    def test_installed_phase7_can_read_resources_and_write_output(self) -> None:
        project = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            wheels = temp / "wheels"
            subprocess.run(
                [sys.executable, "-m", "pip", "wheel", str(project),
                 "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheels)],
                check=True, capture_output=True, text=True,
            )
            environment = temp / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            executable = environment / "bin" / "python"
            subprocess.run(
                [str(executable), "-m", "pip", "install", "--no-deps",
                 str(next(wheels.glob("*.whl")))],
                check=True, capture_output=True, text=True,
            )
            output = temp / "phase7.json"
            clean_env = dict(os.environ)
            clean_env.pop("PYTHONPATH", None)
            subprocess.run(
                [str(environment / "bin" / "enigma-phase7"), "--output", str(output)],
                cwd=temp, env=clean_env, check=True, capture_output=True, text=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "invalid_positive_control_failure")
            self.assertTrue(result["source_audit"]["passed"])
            self.assertTrue(result["scorer_validation"]["passed"])
            self.assertIsNone(result["search"])


if __name__ == "__main__":
    unittest.main()
