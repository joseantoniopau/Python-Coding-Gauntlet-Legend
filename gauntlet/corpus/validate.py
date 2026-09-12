"""Corpus validation.

A problem earns its place only if its canonical solution passes every one of its
own tests inside the real sandbox. Two independent implementations — the build-time
reference that produced the expected values, and the canonical source shown to the
player — must agree. Anything else is rejected, not shipped.

Two kinds of check live here. Most are about one problem and reject that problem.
The last set is about the corpus as a whole — lineage and the sealed hold-out —
and it cannot reject anything, because there is no single problem to blame. It
fails the build instead. That is the right severity: a hold-out that overlaps
what the player was taught does not produce a slightly wrong transfer score, it
produces a confident one that is false, and shipping that is worse than shipping
nothing.
"""
from __future__ import annotations

import ast
import copy
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .. import puzzles, sandbox
from .schema import DIFFICULTIES, PATTERNS, Problem, SOURCE_TYPES


# What each grader in `puzzles` reads out of `mcq`. A puzzle missing one of
# these does not grade badly — it cannot grade at all, and the player meets a
# fight with no win condition. Validation used to skip every kind it did not
# recognise, which is how an encounter kind could ship entirely unchecked.
PUZZLE_REQUIRED = {
    "RUNE_ASSEMBLY":    ("runes",),
    "TRACE":            ("checkpoints", "code"),
    "SPOT_THE_FLAW":    ("flawed_line", "code", "reference_code"),
    "STATE_PREDICT":    ("final_state", "code", "probe"),
    "BREAK_IT":         ("flawed_code", "probes"),
    "COMPLEXITY_MATCH": ("snippets",),
}


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


def _puzzle_static(p: Problem) -> list:
    """Shape checks for the six puzzle kinds. Cheap, and they fail with a name."""
    out = []
    err = lambda m: out.append(Issue(p.id, "error", m))       # noqa: E731
    kind = p.encounter_kind
    spec = p.mcq

    for name in PUZZLE_REQUIRED[kind]:
        if not spec.get(name):
            err(f"{kind} is missing mcq[{name!r}], which its grader requires")
    if out:
        return out                     # the rest would only restate the absence

    if kind == "RUNE_ASSEMBLY":
        real = [r for r in spec["runes"] if not r.get("distractor")]
        if not real:
            err("rune assembly has no runes that belong in the solution")
        for i, rune in enumerate(spec["runes"]):
            if not str(rune.get("text", "")).strip():
                err(f"rune {i} is blank — a blank line cannot be dragged")
            if not isinstance(rune.get("indent"), int) or rune["indent"] < 0:
                err(f"rune {i} has no usable indent depth")
        if len(spec.get("shuffle", [])) != len(spec["runes"]):
            err("the shuffle does not cover every rune")
        # The runes are cut from the canonical solution, so putting them back in
        # order must reproduce it. If it does not, the two have drifted and the
        # intended answer is not the answer the tests grade.
        assembled = "\n".join("    " * r["indent"] + r["text"] for r in real)
        if assembled.strip() != p.canonical_solution.strip():
            err("the runes do not reassemble into the canonical solution")

    elif kind == "TRACE":
        count = len(spec["code"].split("\n"))
        for i, cp in enumerate(spec["checkpoints"]):
            if not 1 <= cp.get("after_line", 0) <= count:
                err(f"checkpoint {i} marks line {cp.get('after_line')}, "
                    f"which is outside the {count}-line spell")
            if not str(cp.get("variable", "")).strip():
                err(f"checkpoint {i} names no variable")
            if cp.get("expected") in (None, ""):
                err(f"checkpoint {i} has no expected value")

    elif kind == "SPOT_THE_FLAW":
        count = len(spec["code"].split("\n"))
        if not 1 <= spec["flawed_line"] <= count:
            err(f"the flawed line {spec['flawed_line']} is outside the "
                f"{count}-line spell")
        good = spec["reference_code"].split("\n")
        bad = spec["code"].split("\n")
        if spec["code"].strip() == spec["reference_code"].strip():
            err("the two spells are identical — there is no flaw to find")
        elif len(good) != len(bad):
            err(f"the spells are {len(good)} and {len(bad)} lines — a difference "
                f"that size is a rewrite, not a curse on one line")
        else:
            # "Near identical, cursed on exactly one line" is the whole premise.
            # If they differ anywhere else, the player can be right about a real
            # difference and still be marked wrong.
            differing = [i + 1 for i, (a, b) in enumerate(zip(good, bad)) if a != b]
            if differing != [spec["flawed_line"]]:
                err(f"the spells differ on lines {differing}, but the answer key "
                    f"says line {spec['flawed_line']}")

    elif kind == "BREAK_IT":
        try:
            compile(spec["flawed_code"], f"<{p.id} flawed>", "exec")
        except SyntaxError as exc:
            err(f"the flawed spell does not compile: {exc}")
        if not all(isinstance(probe, list) for probe in spec["probes"]):
            err("every probe must be an argument list")

    elif kind == "COMPLEXITY_MATCH":
        if len(spec["snippets"]) < 2:
            err("pricing one snippet alone can be done by counting `for` keywords")
        options = spec.get("options") or []
        for i, snippet in enumerate(spec["snippets"]):
            cost = str(snippet.get("complexity", "")).strip()
            if not cost:
                err(f"snippet {i} has no cost to match")
            elif options and cost not in options:
                # The interface offers `options` and nothing else. A cost that is
                # not among them is an answer the player cannot physically give.
                err(f"snippet {i} costs {cost}, which is not one of the options "
                    f"the player is offered")
            if not str(snippet.get("code", "")).strip():
                err(f"snippet {i} has no code")
    return out


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
        out.extend(_verify_forge(p))
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
    if p.source_type == "REPORTED_INTERVIEW":
        if not p.provenance_note:
            err("reported-interview provenance must carry a disclaimer note")
        if "not a guarantee" not in p.provenance_note.lower():
            err("reported-interview provenance must say it is not a guarantee")
        # This build is company-agnostic on purpose. REPORTED_INTERVIEW now means
        # "a shape the reporting record keeps producing", which is a claim we can
        # actually stand behind; naming an employer is a claim we cannot, since
        # nobody confirmed any particular question was asked anywhere. So the
        # disclaimer is the contract and the attribution is the thing we refuse.
        if (p.reported_company or "").strip():
            err("provenance names an employer; this build is company-agnostic")
    return out


def _verify_forge(p: Problem) -> list:
    """Prove the Forge can be won.

    `min_kills` defaults to every Mimic, so a Mimic that behaves exactly like the
    honest implementation makes the encounter unwinnable — no suite can reject it
    without also rejecting the correct code. Whether two implementations differ
    is not decidable in general, so the author supplies the witness: one input per
    Mimic on which it disagrees. This runs those witnesses. A missing or wrong one
    is an error, because an unprovable Forge and an unwinnable Forge look
    identical from the player's side of the screen.
    """
    out = []
    name = p.entry.get("name")
    witnesses = p.mcq.get("kill_inputs") or []
    if len(witnesses) < len(p.mutants):
        return [Issue(p.id, "error",
                      f"test forge declares {len(p.mutants)} mimic(s) but only "
                      f"{len(witnesses)} killing input(s); every mimic needs one, "
                      f"or there is no proof the encounter can be won")]

    def call(source, args, label):
        namespace: dict = {}
        exec(compile(source, f"<{p.id} {label}>", "exec"), namespace)
        return namespace[name](*copy.deepcopy(args))

    for i, mutant in enumerate(p.mutants):
        args = list(witnesses[i])
        try:
            honest = call(p.canonical_solution, args, "correct")
        except Exception as exc:
            out.append(Issue(p.id, "error",
                             f"the honest implementation raises on mimic {i}'s "
                             f"killing input {args!r}: {type(exc).__name__}: {exc}"))
            continue
        try:
            theirs = call(mutant, args, f"mimic {i}")
        except Exception:
            continue            # raising IS disagreeing, and a suite catches it
        if theirs == honest:
            out.append(Issue(p.id, "error",
                             f"mimic {i} agrees with the honest implementation on "
                             f"its own killing input {args!r} (both give "
                             f"{honest!r}) — no test suite can tell them apart"))
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


# ---------------------------------------------------------------------------
# The reading puzzles, checked against what Python actually does
# ---------------------------------------------------------------------------
#
# The two checks below are the ones the answer key cannot make. A TRACE whose
# checkpoint expects the wrong value is perfectly self-consistent: the key is
# the expected value, so grading it passes, and the player is marked wrong for
# being right. That is worse than an unsolvable puzzle — it teaches them to
# distrust correct reasoning. The only authority on what a variable holds is
# running the code, so that is what happens here.
#
# The authoring family does this too, at build time. It is repeated at the gate
# because the gate is what the whole corpus passes through: a puzzle authored
# somewhere else, or a solution edited without its checkpoints, must not be able
# to walk around it.

_TRACE_FILE = "<validate-trace>"


def _line_snapshots(code: str) -> dict:
    """Per line, the variables the code left behind on each visit to it.

    Consecutive events on one line collapse into a single visit, so a
    comprehension re-firing its own line is one moment rather than many, while a
    loop body genuinely revisited is many.
    """
    namespace: dict = {}
    visits: dict = {}
    current = {"line": None}

    def keep():
        line = current["line"]
        if line is None:
            return
        snapshot = {}
        for name, value in namespace.items():
            if name.startswith("__"):
                continue
            try:
                snapshot[name] = copy.deepcopy(value)
            except Exception:
                snapshot[name] = value
        visits.setdefault(line, []).append(snapshot)
        current["line"] = None

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != _TRACE_FILE:
            return None
        if event == "line":
            if frame.f_lineno != current["line"]:
                keep()
                current["line"] = frame.f_lineno
        elif event == "return":
            keep()
        return tracer

    previous = sys.gettrace()
    sys.settrace(tracer)
    try:
        exec(compile(code, _TRACE_FILE, "exec"), namespace)
    finally:
        sys.settrace(previous)
    keep()
    return visits


def _verify_trace(p: Problem) -> list:
    out = []
    if sys.gettrace() is not None:
        return out                  # a debugger or coverage tool owns the hook
    try:
        visits = _line_snapshots(p.mcq["code"])
    except Exception as exc:
        return [Issue(p.id, "error",
                      f"the traced spell will not run: {type(exc).__name__}: {exc}")]
    for i, cp in enumerate(p.mcq["checkpoints"]):
        seen = visits.get(cp.get("after_line"), [])
        if len(seen) != 1:
            out.append(Issue(p.id, "error",
                             f"checkpoint {i} marks line {cp.get('after_line')}, "
                             f"which runs {len(seen)} times — the question has "
                             f"{'no' if not seen else 'more than one'} honest answer"))
            continue
        variable = cp.get("variable")
        if variable not in seen[0]:
            out.append(Issue(p.id, "error",
                             f"checkpoint {i}: {variable!r} does not exist after "
                             f"line {cp.get('after_line')}"))
            continue
        actual = repr(seen[0][variable])
        if not puzzles._values_match(str(cp.get("expected", "")), actual):
            out.append(Issue(p.id, "error",
                             f"checkpoint {i}: after line {cp.get('after_line')}, "
                             f"{variable} is really {actual}, not "
                             f"{cp.get('expected')!r}"))
    return out


def _verify_state(p: Problem) -> list:
    """Replay the operations one statement at a time and read the probe."""
    spec = p.mcq
    namespace: dict = {}
    try:
        exec(compile(spec["code"], f"<{p.id} setup>", "exec"), namespace)
        for node in ast.parse(spec["operations"]).body:
            module = ast.Module(body=[node], type_ignores=[])
            exec(compile(module, f"<{p.id} ops>", "exec"), namespace)
        actual = repr(eval(spec["probe"], namespace))
    except Exception as exc:
        return [Issue(p.id, "error",
                      f"the operations will not run: {type(exc).__name__}: {exc}")]
    if not puzzles._values_match(str(spec["final_state"]), actual):
        return [Issue(p.id, "error",
                      f"the operations really leave {actual}, not "
                      f"{spec['final_state']!r}")]
    return []


def _run_puzzle(p: Problem):
    """Play the puzzle, twice, with the answers the corpus itself supplies.

    A puzzle has to clear two bars and the second one is the one that gets
    forgotten. Winnable: its own answer key must grade as solved, or the player
    meets a fight with no win condition and no amount of understanding gets them
    out of it. And not trivially winnable: an obviously wrong answer of the same
    shape must fail, or the encounter teaches that guessing works.
    """
    if p.encounter_kind not in puzzles.PUZZLE_KINDS:
        return None
    if any(i.severity == "error" for i in _puzzle_static(p)):
        return None                    # already reported; grading would only echo it

    try:
        outcome = puzzles.grade(p, puzzles.answer_key(p))
    except Exception as exc:           # a grader that raises is a dead encounter
        return Issue(p.id, "error",
                     f"{p.encounter_kind} grader raised on its own answer key: "
                     f"{type(exc).__name__}: {exc}")
    if not outcome.get("solved"):
        why = [line["message"] for line in outcome.get("lines", [])
               if line["status"] != "pass" and line["message"]]
        return Issue(p.id, "error",
                     f"{p.encounter_kind} is not winnable: its own answer key "
                     f"grades as unsolved ({outcome.get('passed')}/"
                     f"{outcome.get('total')}). {' '.join(why[:2])}")

    decoy = puzzles.decoy_answer(p)
    if decoy is None:
        # BREAK_IT: the honest wrong answer is an input the two spells agree on,
        # which is exactly what the visible tests are.
        if not p.visible_tests:
            return Issue(p.id, "error", "BREAK_IT has no visible test to use as "
                                        "an input the two spells agree on")
        decoy = list(p.visible_tests[0]["args"])
    try:
        if puzzles.grade(p, decoy).get("solved"):
            return Issue(p.id, "error",
                         f"{p.encounter_kind} is trivially winnable: the wrong "
                         f"answer {decoy!r} grades as solved")
    except Exception as exc:
        return Issue(p.id, "error",
                     f"{p.encounter_kind} grader raised on a wrong answer: "
                     f"{type(exc).__name__}: {exc}")
    return None


# ---------------------------------------------------------------------------
# The corpus as a whole: lineage and the sealed hold-out
# ---------------------------------------------------------------------------

CORPUS = "<corpus>"     # the problem_id for a finding that belongs to no problem


def _corpus_checks(problems: list) -> list:
    """The four rules the hold-out has to satisfy, checked on what shipped.

    Deliberately re-derived from the accepted problems rather than trusted from
    the selection code that produced them. The selector and the check agreeing
    by construction would make this decoration; they have to agree by evidence.
    """
    from . import (GENTLE, SEALED_BAND, SEALED_HARD_SHARE,
                   SEALED_ORDINARY_SHARE, STEEP, coverable_patterns,
                   named_in_source, reserved_ids, seal_holdout)

    out = []
    err = lambda m: out.append(Issue(CORPUS, "error", m))     # noqa: E731
    total = len(problems)
    if not total:
        return out

    unassigned = [p.id for p in problems if not p.lineage_id]
    if unassigned:
        err(f"{len(unassigned)} problem(s) carry no lineage_id, starting with "
            f"{unassigned[0]} — an unlineaged problem cannot be proven unseen")
        return out

    lineages = defaultdict(list)
    for problem in problems:
        lineages[problem.lineage_id].append(problem)
    sealed = [p for p in problems if p.sealed]
    teachable = [p for p in problems if not p.sealed]

    # RULE 1. Whole lineages or none of it.
    for lineage_id, group in sorted(lineages.items()):
        marked = [p for p in group if p.sealed]
        if marked and len(marked) != len(group):
            open_siblings = sorted(p.id for p in group if not p.sealed)
            err(f"lineage {lineage_id} is sealed in part: {len(marked)} of "
                f"{len(group)} held back while {open_siblings[0]} stays "
                f"teachable — the sealed ones are not unseen")

    # RULE 1b. And no teachable problem points AT the hold-out. `prerequisites`
    # and `variants` are lists of problem ids and player_view ships both, so a
    # single surviving reference hands a sealed id to a player in an ordinary
    # Adventure payload — which is enough to go and read it, and enough to stop
    # it ever being met cold. corpus.sever_references cuts these at build time;
    # this proves it on what shipped rather than trusting that it ran.
    sealed_ids = {p.id for p in sealed}
    for problem in teachable:
        for field_name in ("prerequisites", "variants"):
            for referenced in sorted(set(getattr(problem, field_name, ()) or ())
                                     & sealed_ids):
                err(f"{problem.id} names sealed problem {referenced} in "
                    f"{field_name}, so Adventure Mode ships a hold-out id to "
                    f"the player and points the ramp at a door that cannot open")

    # RULE 2. Every topic keeps a doorway. A topic that had no gentle rung to
    # begin with is not something sealing broke, so the rule is conditional on
    # the corpus having had one.
    for label, key in (("topic", lambda p: p.spaced_repetition_family),
                       ("pattern", lambda p: p.pattern)):
        had = {key(p) for p in problems if p.difficulty in GENTLE}
        left = {key(p) for p in teachable if p.difficulty in GENTLE}
        for name in sorted(had - left):
            err(f"{label} {name!r} has no GUIDED or TUTORIAL doorway left in the "
                f"teachable set — sealing it made the topic unlearnable")
    vanished = ({p.spaced_repetition_family for p in problems}
                - {p.spaced_repetition_family for p in teachable})
    for name in sorted(vanished):
        err(f"topic {name!r} is sealed in its entirety — nothing left to teach")

    # RULE 3. Spread. Every pattern that could be represented, is.
    missing = coverable_patterns(problems) - {p.pattern for p in sealed}
    for pattern in sorted(missing):
        err(f"pattern {pattern!r} has a sealable lineage but no sealed problem — "
            f"transfer readiness would be blind to it")

    # RULE 4. Ordinary difficulties, and enough of them to mean something.
    share = len(sealed) / total
    low, high = SEALED_BAND
    if not low <= share <= high:
        err(f"the sealed set is {len(sealed)}/{total} ({share:.1%}), outside the "
            f"{low:.0%}-{high:.0%} band")
    counts = Counter(p.difficulty for p in sealed)
    ordinary = counts["EASY"] + counts["MEDIUM"]
    if sealed and ordinary / len(sealed) < SEALED_ORDINARY_SHARE:
        err(f"only {ordinary}/{len(sealed)} sealed problems are EASY or MEDIUM; "
            f"the hold-out is meant to measure whether ordinary knowledge "
            f"transferred")
    steep = sum(counts[d] for d in STEEP)
    if sealed and steep / len(sealed) > SEALED_HARD_SHARE:
        err(f"{steep}/{len(sealed)} sealed problems are {'/'.join(STEEP)}; that "
            f"measures whether hard problems are hard")
    for difficulty in ("EASY", "MEDIUM"):
        if not counts[difficulty]:
            err(f"nothing sealed at {difficulty} — the mix is not representative")

    # The protected list has to keep up with the game that names those ids.
    # Under-protection is the error: a quest pointing at a sealed problem either
    # leaks the hold-out into Adventure Mode or dead-ends the quest.
    for problem_id in sorted(named_in_source(problems) - reserved_ids(problems)):
        err(f"{problem_id} is named elsewhere in the source but is not in "
            f"corpus.RESERVED, so the hold-out could seal content the game "
            f"already promised — add it to RESERVED")

    # The hold-out has to be a function of the content and nothing else. Run the
    # selection again over the same problems in the opposite order: a different
    # answer means something in there is reading a dict, a set or a clock.
    before = {p.id for p in sealed}
    seal_holdout(list(reversed(problems)))
    again = {p.id for p in problems if p.sealed}
    for problem in problems:        # put back exactly what was there, flag by flag
        problem.sealed = problem.id in before
    if again != before:
        err(f"the sealed set depends on the order problems arrive in: "
            f"{len(before ^ again)} problem(s) differ between two runs")
    return out


def validate(problems: list, *, workers: int = 8) -> Report:
    report = Report(checked=len(problems))

    seen = {}
    for p in problems:
        if p.id in seen:
            report.issues.append(Issue(p.id, "error", "duplicate problem id"))
        seen[p.id] = p
        report.issues.extend(_static_checks(p))
        # Additive: a puzzle still faces every check its entry kind faces. The
        # old behaviour was to recognise `mcq` and `test_forge` and silently wave
        # everything else through.
        if p.encounter_kind in puzzles.PUZZLE_KINDS:
            issues = _puzzle_static(p)
            # The execution checks read fields the shape check just proved are
            # there, so they only run once it is clean.
            if not issues and p.encounter_kind == "TRACE":
                issues = _verify_trace(p)
            elif not issues and p.encounter_kind == "STATE_PREDICT":
                issues = _verify_state(p)
            report.issues.extend(issues)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for issue in pool.map(_run_canonical, problems):
            if issue:
                report.issues.append(issue)
        for issue in pool.map(_run_broken, problems):
            if issue:
                report.issues.append(issue)
        for issue in pool.map(_run_puzzle, problems):
            if issue:
                report.issues.append(issue)

    bad = {i.problem_id for i in report.issues if i.severity == "error"}
    report.accepted = [p for p in problems if p.id not in bad]
    # Run last, and on what actually survived: the hold-out's guarantees are
    # about the corpus that ships, not the one that was proposed.
    report.issues.extend(_corpus_checks(report.accepted))
    return report
