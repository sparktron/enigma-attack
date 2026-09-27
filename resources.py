"""Locate immutable research inputs in a checkout or installed wheel."""

from __future__ import annotations

import pathlib
import sys


def resource_root() -> pathlib.Path:
    source = pathlib.Path(__file__).resolve().parent
    if (source / "corpus.json").is_file():
        return source
    installed = pathlib.Path(sys.prefix) / "share" / "enigma-attack"
    if (installed / "corpus.json").is_file():
        return installed
    raise FileNotFoundError("enigma-attack research resources are missing")


def output_path(name: str) -> pathlib.Path:
    source = pathlib.Path(__file__).resolve().parent
    base = source if (source / "corpus.json").is_file() else pathlib.Path.cwd()
    return base / "artifacts" / name


def resolve_output(value: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(value)
    if path.is_absolute():
        return path
    source = pathlib.Path(__file__).resolve().parent
    base = source if (source / "corpus.json").is_file() else pathlib.Path.cwd()
    return base / path
