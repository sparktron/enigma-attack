"""Record which code produced an artifact, in a checkout or an installed wheel.

Every phase records the same block, so an artifact can always answer two
questions: which commit was it built from, and could that commit have been
modified when it ran.  The second is the one that matters for reproduction: a
commit with uncommitted edits does not identify the code that ran, and an
artifact that records only the commit cannot say so.

Code and research inputs live in different places once installed.  The modules
go to site-packages and the inputs to ``share/enigma-attack`` (see
:mod:`resources`), so code is hashed from this module's own directory and never
from the resource root.  Git is consulted only when that directory is the top
of a work tree: an installed copy is not a checkout, and a virtual environment
created inside some unrelated repository must not report that repository's
commit as this code's.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys
from typing import Any

CODE_ROOT = pathlib.Path(__file__).resolve().parent


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(*arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=CODE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    # Only the trailing newline: ``status --porcelain`` starts with a status
    # column that may be a space, and stripping it would misreport the change.
    return completed.stdout.rstrip("\n") if completed.returncode == 0 else None


def checkout_state() -> dict[str, Any]:
    """Commit, branch and uncommitted changes of the checkout, if there is one.

    ``dirty`` is ``None`` rather than ``False`` when there is no checkout to
    ask: absence of evidence about uncommitted edits is not evidence that
    there were none.  ``files_sha256`` from :func:`code_version` identifies the
    code either way.
    """

    toplevel = _git("rev-parse", "--show-toplevel")
    if toplevel is None or pathlib.Path(toplevel).resolve() != CODE_ROOT:
        return {
            "source": "not_a_checkout",
            "commit": None,
            "branch": None,
            "dirty": None,
            "status": [],
        }
    status = _git("status", "--porcelain")
    return {
        "source": "git_checkout",
        "commit": _git("rev-parse", "HEAD"),
        # Empty on a detached HEAD, which is a state rather than a failure.
        "branch": _git("branch", "--show-current") or None,
        "dirty": None if status is None else bool(status),
        "status": status.splitlines() if status else [],
    }


def loaded_code() -> dict[str, str]:
    """Hash every project module the running process has imported.

    Taken from ``sys.modules`` rather than a hand-kept list, so a module split
    out of a runner, or a helper it starts importing, is recorded without
    anyone remembering to add it.  The project has no third-party
    dependencies, so the modules found beside this one are its own.
    """

    files: set[pathlib.Path] = set()
    for module in list(sys.modules.values()):
        location = getattr(module, "__file__", None)
        if not location:
            continue
        path = pathlib.Path(location).resolve()
        if path.suffix == ".py" and path.parent == CODE_ROOT:
            files.add(path)
    return {path.name: sha256_file(path) for path in sorted(files)}


def code_version() -> dict[str, Any]:
    """The provenance block every phase writes under ``code``.

    Call it before the experiment does its work: a long run can outlast an
    edit to the checkout, and the state worth recording is the one the run
    started from.
    """

    return {**checkout_state(), "files_sha256": loaded_code()}
