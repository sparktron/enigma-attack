"""Check generated artifacts against the code that is supposed to produce them.

Two independent checks, because they catch different failures:

``drift``
    Regenerate each artifact and compare it with the committed copy over the
    paths declared in ``artifact_claims.json``.  A changed **value** is a hard
    failure: the recorded result no longer follows from the code, which is
    either a regression or an undocumented method change.  An added or removed
    **key** is reported but does not fail, because a deliberate shape change is
    normal and the remedy is simply to regenerate and recommit.

``determinism``
    Run each experiment twice in the same environment and require the declared
    paths to agree.  This says nothing about the committed artifacts; it
    catches nondeterminism entering the pipeline, such as an unseeded
    generator or an order-dependent traversal.

Artifacts embed timestamps, runtimes, git provenance, platform details and
absolute paths, so byte comparison is never possible.  The comparison is an
allowlist of claim paths rather than a denylist of volatile fields: an
unlisted field goes unchecked and stays visible, whereas an over-broad denylist
would silently stop checking a conclusion.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CLAIMS = ROOT / "artifact_claims.json"
MISSING = object()


def load_claims(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "enigma-attack.artifact-claims/v1":
        raise ValueError("unsupported artifact claims schema")
    return payload


def resolve(document: Any, path: str) -> Iterator[tuple[str, Any]]:
    """Yield ``(concrete_path, value)`` for every match of a claim path."""

    head, _, rest = path.partition(".")
    if head.endswith("[]"):
        key = head[:-2]
        node = document.get(key, MISSING) if isinstance(document, dict) else MISSING
        if not isinstance(node, list):
            yield f"{key}[]", MISSING
            return
        for index, item in enumerate(node):
            if rest:
                for sub, value in resolve(item, rest):
                    yield f"{key}[{index}].{sub}", value
            else:
                yield f"{key}[{index}]", item
        return
    if head == "*":
        if not isinstance(document, dict):
            yield "*", MISSING
            return
        for key in sorted(document):
            yield key, document[key]
        return
    node = document.get(head, MISSING) if isinstance(document, dict) else MISSING
    if not rest:
        yield head, node
        return
    if node is MISSING:
        yield head, MISSING
        return
    for sub, value in resolve(node, rest):
        yield f"{head}.{sub}", value


def compare(
    expected: Any, actual: Any, claim_paths: Sequence[str]
) -> tuple[list[str], list[str], list[str]]:
    """Return (value differences, shape differences, unmatched claim paths).

    A claim path present in neither copy is reported separately and treated as
    a hard failure by the callers.  That is the one way an allowlist fails
    open: a typo silently checks nothing, and the run stays green while the
    field it was supposed to guard goes unexamined.
    """

    values: list[str] = []
    shapes: list[str] = []
    unmatched: list[str] = []
    for claim in claim_paths:
        want = dict(resolve(expected, claim))
        have = dict(resolve(actual, claim))
        matched = False
        for key in sorted(set(want) | set(have)):
            a, b = want.get(key, MISSING), have.get(key, MISSING)
            if a is MISSING and b is MISSING:
                continue
            matched = True
            if a is MISSING:
                shapes.append(f"{key}: absent from the committed copy, present when regenerated")
            elif b is MISSING:
                shapes.append(f"{key}: present in the committed copy, absent when regenerated")
            elif a != b:
                values.append(f"{key}: committed {json.dumps(a)[:80]} != regenerated {json.dumps(b)[:80]}")
        if not matched:
            unmatched.append(claim)
    return values, shapes, unmatched


def regenerate(runner: Sequence[str], destination: pathlib.Path) -> dict[str, Any]:
    command = [sys.executable, *runner, "--output", str(destination)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"runner failed: {' '.join(command)}\n{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(destination.read_text(encoding="utf-8"))


def check_drift(claims: dict[str, Any], workspace: pathlib.Path) -> int:
    failures = 0
    for name, entry in claims["artifacts"].items():
        committed_path = ROOT / name
        if not committed_path.exists():
            print(f"FAIL {name}: declared artifact is not committed")
            failures += 1
            continue
        if entry.get("superseded"):
            # The pipeline now refuses to run this experiment, so it cannot be
            # regenerated by design.  The artifact is kept as the record of a
            # result that was real when it was produced.
            if not committed_path.exists():
                failures += 1
                print(f"FAIL {name}: superseded artifact is missing")
            else:
                print(f"skip {name}: superseded - {entry['superseded']}")
            continue
        committed = json.loads(committed_path.read_text(encoding="utf-8"))
        fresh = regenerate(entry["runner"], workspace / pathlib.Path(name).name)
        values, shapes, unmatched = compare(committed, fresh, entry["claim_paths"])
        if values or unmatched:
            failures += 1
            if values:
                print(f"FAIL {name}: {len(values)} claim value(s) changed")
                for line in values[:10]:
                    print(f"       {line}")
            if unmatched:
                print(f"FAIL {name}: {len(unmatched)} declared claim path(s) match nothing")
                for line in unmatched:
                    print(f"       {line}")
        elif shapes:
            print(f"WARN {name}: shape changed, values intact; regenerate and recommit")
        else:
            print(f"ok   {name}")
        for line in shapes[:10]:
            print(f"       note: {line}")
    return failures


def check_determinism(claims: dict[str, Any], workspace: pathlib.Path) -> int:
    failures = 0
    for name, entry in claims["artifacts"].items():
        if entry.get("superseded"):
            print(f"skip {name}: superseded - {entry['superseded']}")
            continue
        stem = pathlib.Path(name).stem
        first = regenerate(entry["runner"], workspace / f"{stem}-a.json")
        second = regenerate(entry["runner"], workspace / f"{stem}-b.json")
        values, shapes, unmatched = compare(first, second, entry["claim_paths"])
        if values or shapes or unmatched:
            failures += 1
            print(f"FAIL {name}: two runs in one environment disagree")
            for line in (values + shapes + unmatched)[:10]:
                print(f"       {line}")
        else:
            print(f"ok   {name}")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("drift", "determinism", "both"))
    parser.add_argument("--claims", type=pathlib.Path, default=DEFAULT_CLAIMS)
    arguments = parser.parse_args(argv)
    claims = load_claims(arguments.claims)

    failures = 0
    with tempfile.TemporaryDirectory() as directory:
        workspace = pathlib.Path(directory)
        if arguments.mode in ("drift", "both"):
            print("== drift: committed artifacts versus regenerated ones ==")
            failures += check_drift(claims, workspace)
        if arguments.mode in ("determinism", "both"):
            print("== determinism: two runs in one environment ==")
            failures += check_determinism(claims, workspace)
    print(f"\n{failures} failing artifact(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
