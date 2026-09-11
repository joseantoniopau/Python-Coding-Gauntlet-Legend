"""Corpus validation.

A problem earns its place only if its canonical solution passes every one of its
own tests inside the real sandbox. Two independent implementations — the build-time
reference that produced the expected values, and the canonical source shown to the
player — must agree. Anything else is rejected, not shipped.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .. import sandbox
from .schema import DIFFICULTIES, PATTERNS, Problem, SOURCE_TYPES


@dataclass
class Issue:
    problem_id: str
    severity: str      # error | warning
    message: str


@dataclass
class Report:
    checked: int = 0
    accepted: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _static_checks(p: Problem) -> list:
    out = []
    err = lambda m: out.append(Issue(p.id, "error", m))       # noqa: E731
    warn = lambda m: out.append(Issue(p.id, "warning", m))    # noqa: E731

    if not p.problem_statement.strip():
        err("empty problem statement")
    if p.difficulty not in DIFFICULTIES:
        err(f"unknown difficulty {p.difficulty!r}")
    if p.source_type not in SOURCE_TYPES:
        err(f"unknown source_type {p.source_type!r}")
    if p.pattern not in PATTERNS and p.pattern not in ("RECOGNITION", "REDACTED"):
        warn(f"pattern {p.pattern!r} is outside the declared vocabulary")

    kind = p.entry.get("kind")
    if kind == "mcq":
        choices = p.mcq.get("choices") or []
        if len(choices) < 2:
            err("multiple-choice encounter needs at least two choices")
        if not 0 <= p.mcq.get("answer", -1) < len(choices):
            err("multiple-choice answer index is out of range")
        if not p.mcq.get("explanation", "").strip():
            warn("multiple-choice encounter has no explanation")
        return out

    if kind == "test_forge":
        if not p.mutants:
            err("test forge encounter has no mutants")
        for i, mutant in enumerate(p.mutants):
            try:
                compile(mutant, f"<mutant {i}>", "exec")
            except SyntaxError as exc:
                err(f"mutant {i} does not compile: {exc}")
        try:
            compile(p.canonical_solution, "<correct>", "exec")
        except SyntaxError as exc:
            err(f"reference implementation does not compile: {exc}")
        return out

    # code / design encounters
    if len(p.visible_tests) < 2:
        warn("fewer than two visible tests")
    if len(p.hidden_tests) < 2:
        warn("fewer than two hidden tests")
    if not p.edge_cases and p.encounter_kind != "DEBUG_BATTLE":
        # debug encounters fold their boundary cases into the hidden set
        warn("no edge-case tests")
    if len(p.hint_tree) < 5:
        warn("hint tree does not reach the Phoenix rung")
    if not p.optimal_complexity.get("time"):
        warn("no stated time complexity")
    if not p.starter_code.strip():
        err("no starter code")
    if p.source_type == "REPORTED_INTERVIEW" and not p.provenance_note:
        err("reported-interview provenance must carry a disclaimer note")
    return out


def _run_canonical(p: Problem):
    """The canonical solution must pass every test the player will face."""
    kind = p.entry.get("kind")
    if kind in ("mcq", "test_forge"):
        return None
    tests = p.all_tests
    if not tests:
        return Issue(p.id, "error", "no tests at all")
    report = sandbox.run_tests(p.canonical_solution, p.entry, tests,
                              timeout_ms=4000, wall_seconds=25)
    if report.phase == "syntax":
        return Issue(p.id, "error",
                     f"canonical solution has a syntax error: {report.error}")
    if not report.ok:
        return Issue(p.id, "error", f"canonical solution failed to run: {report.error}")
    failures = [t for t in report.tests if not t.passed]
    if failures:
        first = failures[0]
        return Issue(p.id, "error",
                     f"canonical solution fails {len(failures)}/{len(tests)} tests; "
                     f"first: {first.name} [{first.status}] {first.message} "
                     f"got={first.got} expected={first.expected}")
    return None


def _run_broken(p: Problem):
    """A DEBUG_BATTLE whose starter code already passes has no bug to find."""
    if p.encounter_kind != "DEBUG_BATTLE":
        return None
    report = sandbox.run_tests(p.starter_code, p.entry, p.all_tests,
                              timeout_ms=1500, wall_seconds=15)
    if report.phase == "syntax":
        return None                        # a syntax bug is a legitimate defect
    if report.ok and all(t.passed for t in report.tests):
        return Issue(p.id, "error", "debug encounter's starter code already passes "
                                    "every test — there is no bug to find")
    return None


def validate(problems: list, *, workers: int = 8) -> Report:
    report = Report(checked=len(problems))

    seen = {}
    for p in problems:
        if p.id in seen:
            report.issues.append(Issue(p.id, "error", "duplicate problem id"))
        seen[p.id] = p
        report.issues.extend(_static_checks(p))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for issue in pool.map(_run_canonical, problems):
            if issue:
                report.issues.append(issue)
        for issue in pool.map(_run_broken, problems):
            if issue:
                report.issues.append(issue)

    bad = {i.problem_id for i in report.issues if i.severity == "error"}
    report.accepted = [p for p in problems if p.id not in bad]
    return report
