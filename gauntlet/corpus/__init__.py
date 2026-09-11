"""Corpus assembly: authored families plus generated variants, all validated."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from .schema import Problem

_FAMILIES = (
    "arrays_hashing", "sliding_window", "two_pointers", "stacks_queues",
    "trees", "matrix_graphs", "recursion_dp", "python_village",
    "binary_search", "design_oop", "debugging", "meta",
)


def build_all() -> list:
    """Every authored problem plus every generated variant, unvalidated."""
    import importlib
    from . import generator

    problems: list = []
    for name in _FAMILIES:
        module = importlib.import_module(f".families.{name}", __package__)
        problems.extend(module.build())
    problems.extend(generator.generate())
    return problems


def write(problems: list, path: Path | None = None) -> Path:
    path = path or config.corpus_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([p.to_dict() for p in problems], indent=1))
    return path


def load(path: Path | None = None) -> list:
    path = path or config.corpus_path()
    raw = json.loads(path.read_text())
    return [Problem(**entry) for entry in raw]


def ensure(path: Path | None = None, *, rebuild: bool = False) -> list:
    """Load the corpus, building and validating it first if necessary."""
    path = path or config.corpus_path()
    if rebuild or not path.exists():
        from .validate import validate
        problems = build_all()
        report = validate(problems)
        write(report.accepted, path)
        return report.accepted
    return load(path)
