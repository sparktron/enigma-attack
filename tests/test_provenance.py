"""The shared code-provenance block every phase records."""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import provenance

SOURCE = pathlib.Path(provenance.__file__).resolve()
PROBE = "import json, provenance; print(json.dumps(provenance.code_version()))"


def git(directory: pathlib.Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *arguments],
        cwd=directory, check=True, capture_output=True, text=True,
    )


class CheckoutTests(unittest.TestCase):
    @unittest.skipUnless(
        (provenance.CODE_ROOT / ".git").exists(), "not running from a git checkout"
    )
    def test_this_checkout_reports_its_commit_and_whether_it_is_modified(self):
        version = provenance.code_version()
        self.assertEqual(version["source"], "git_checkout")
        self.assertRegex(version["commit"], r"^[0-9a-f]{40}$")
        self.assertIsInstance(version["dirty"], bool)
        self.assertEqual(version["dirty"], bool(version["status"]))
        self.assertEqual(
            version["files_sha256"]["provenance.py"], provenance.sha256_file(SOURCE)
        )


class IsolatedCopyTests(unittest.TestCase):
    """Run a copy of the module where the checkout state is under test control."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.temp = pathlib.Path(self._temporary.name)
        self.environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_") and key != "PYTHONPATH"
        }

    def tearDown(self):
        self._temporary.cleanup()

    def install(self, directory: pathlib.Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(SOURCE, directory / "provenance.py")
        (directory / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
        (directory / "unused.py").write_text("VALUE = 2\n", encoding="utf-8")

    def probe(self, directory: pathlib.Path, script: str = PROBE) -> dict:
        completed = subprocess.run(
            [sys.executable, "-c", script], cwd=directory, env=self.environment,
            check=True, capture_output=True, text=True,
        )
        return json.loads(completed.stdout)

    def test_a_clean_checkout_is_not_dirty_and_an_edit_makes_it_dirty(self):
        self.install(self.temp)
        # As in the real repository: importing the probe writes bytecode.
        (self.temp / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        git(self.temp, "init", "-q")
        git(self.temp, "add", ".")
        git(self.temp, "commit", "-q", "-m", "initial")

        clean = self.probe(self.temp)
        self.assertEqual(clean["source"], "git_checkout")
        self.assertFalse(clean["dirty"])
        self.assertEqual(clean["status"], [])

        (self.temp / "helper.py").write_text("VALUE = 3\n", encoding="utf-8")
        dirty = self.probe(self.temp)
        self.assertEqual(dirty["commit"], clean["commit"])
        self.assertTrue(dirty["dirty"])
        # The leading status column is a space for an unstaged edit; stripping
        # it would turn " M" into "M " and misreport the change as staged.
        self.assertEqual(dirty["status"], [" M helper.py"])

    def test_without_a_checkout_dirty_is_unknown_rather_than_false(self):
        self.install(self.temp)
        version = self.probe(self.temp)
        self.assertEqual(version["source"], "not_a_checkout")
        self.assertIsNone(version["commit"])
        self.assertIsNone(version["dirty"])

    def test_an_enclosing_unrelated_repository_is_not_reported(self):
        # A virtual environment created inside some other repository puts the
        # installed modules inside that work tree.  Its commit says nothing
        # about this code.
        git(self.temp, "init", "-q")
        (self.temp / "README").write_text("unrelated\n", encoding="utf-8")
        git(self.temp, "add", ".")
        git(self.temp, "commit", "-q", "-m", "unrelated")
        nested = self.temp / "venv" / "site-packages"
        self.install(nested)
        version = self.probe(nested)
        self.assertEqual(version["source"], "not_a_checkout")
        self.assertIsNone(version["commit"])
        self.assertIsNone(version["dirty"])

    def test_every_imported_project_module_is_hashed_and_nothing_else(self):
        self.install(self.temp)
        version = self.probe(
            self.temp,
            "import json, helper, provenance; print(json.dumps(provenance.code_version()))",
        )
        self.assertEqual(sorted(version["files_sha256"]), ["helper.py", "provenance.py"])
        self.assertEqual(
            version["files_sha256"]["helper.py"],
            provenance.sha256_file(self.temp / "helper.py"),
        )

    def test_a_runner_script_in_a_subdirectory_is_hashed_by_relative_path(self):
        self.install(self.temp)
        runner = self.temp / "scripts" / "runner.py"
        runner.parent.mkdir()
        runner.write_text(
            "import json, pathlib, sys\n"
            "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
            "import provenance\n"
            "print(json.dumps(provenance.code_version()))\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [sys.executable, str(runner)], cwd=self.temp, env=self.environment,
            check=True, capture_output=True, text=True,
        )
        hashes = json.loads(completed.stdout)["files_sha256"]
        self.assertEqual(sorted(hashes), ["provenance.py", "scripts/runner.py"])
        self.assertEqual(hashes["scripts/runner.py"], provenance.sha256_file(runner))


if __name__ == "__main__":
    unittest.main()
