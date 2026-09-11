"""Corpus assembly: authored families plus generated variants, all validated."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from .schema import Problem

_FAMILIES = (
    "onboarding", "scaffolds", "parsons", "breaking",
    "arrays_hashing", "sliding_window", "two_pointers", "stacks_queues",
    "trees", "matrix_graphs", "recursion_dp", "python_village",
    "binary_search", "design_oop", "debugging", "meta", "reasoning",
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


def fingerprint() -> str:
    """A hash of everything that can change the corpus.

    Without this, a player who started before new content shipped would keep
    their original corpus forever: the old ensure() only checked whether the
    file existed. Content is part of the program, so it has to invalidate the
    way code does.
    """
    import hashlib
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    sources = sorted(here.glob("families/*.py")) + [
        here / "generator.py", here / "schema.py", here / "validate.py",
    ]
    for source in sources:
        if source.exists():
            digest.update(source.name.encode())
            digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def _stamp_path(path: Path) -> Path:
    return path.with_suffix(".stamp")


def ensure(path: Path | None = None, *, rebuild: bool = False) -> list:
    """Load the corpus, rebuilding and revalidating whenever the content that
    produces it has changed."""
    path = path or config.corpus_path()
    stamp = _stamp_path(path)
    current = fingerprint()
    stale = True
    if path.exists() and stamp.exists():
        try:
            stale = stamp.read_text().strip() != current
        except OSError:
            stale = True

    if rebuild or not path.exists() or stale:
        from .validate import validate
        problems = build_all()
        report = validate(problems)
        write(report.accepted, path)
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(current)
        return report.accepted
    return load(path)
