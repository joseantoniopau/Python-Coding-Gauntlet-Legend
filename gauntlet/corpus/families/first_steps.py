"""First Steps: the bottom of the ramp, for someone who has never written Python.

Every other gentle family in this corpus starts one rung too high. The current
gentlest problem in the game hands the player this:

    def twice(n):
        doubled = __BLANK__
        return doubled

which is a good problem and a bad first problem. Before it asks for anything it
has already assumed five things: that `def` means something, that `n` is a value
that will arrive from somewhere, that the indentation is load-bearing, that the
body is separate from the header, and that `return` is how a value leaves. Five
concepts presented as scenery. A step is only small if you already know the shape
of the thing you are stepping into.

So this family starts below that, at a single line of Python evaluated on its
own, and climbs in an order where nothing is used before it has been met:

     1  a value, and printing it
     2  a name for a value, and which side of the `=` it goes on
     3  text, numbers, and True/False — and why "2" + "2" is not 4
     4  calling something that already exists: len, str, int, and dot-calls
     5  what an indent means, and that Python is the only one who cares this much
     6  what `return` means, and how it differs from printing
     7  a parameter: a value that arrives from outside
     8  writing a whole function, from its scattered lines
     9  a condition, then a loop, then a list
    10  reading an error message on purpose, and what a traceback is telling you

FOUR AUTHORING RULES, all of them load-bearing.

1. THE FIRST TWENTY-TWO PROBLEMS CONTAIN NO FUNCTION AT ALL. They are
   CODE_READING questions about one expression, and TRACE puzzles over two to
   six lines of top-level code. The word `def` does not appear anywhere in the
   family — statement, code or starter — until problem 23, and when it does the
   statement says in plain words what the scaffolding around the blank is for.

2. EVERY STATEMENT TEACHES BEFORE IT ASKS. Two or three sentences explaining the
   one new idea, a worked example with its real output, then the ask. A beginner
   problem whose statement assumes its own answer is worse than no problem.

3. ONE NEW IDEA PER PROBLEM, and the problems are chained: `build` wires each
   one's `prerequisites` to the one before it, so the order survives leaving this
   file. Nothing here introduces two things at once.

4. THE EXPECTED VALUES ARE NOT TYPED FROM MEMORY. Every TRACE checkpoint and
   every STATE_PREDICT answer written below is run at build time and compared
   against what Python really does; a disagreement raises rather than ships. The
   author and the interpreter are the two independent implementations here, which
   is the same contract the code problems satisfy with a reference callable.

Patterns are LANGUAGE for most of it — the subject really is Python itself and
not a data structure — with ARRAY where a list is the point, SIMULATION where
state evolving over a loop is the point, and STRING where indexing into text is.
All four are permitted by chapter I, so every problem here is reachable by a
brand new player without the chapter ladder needing to learn a new word.

Difficulty is GUIDED for all but the last five, which are TUTORIAL: that is where
the scaffolding comes off and the player writes a whole function into an empty
body for the first time.

ON "THE FIRST FORTY MINUTES", which is the brief this was written to: at target
pace the first forty minutes lands around the end of concept 6, which is the
point where `return` has been met and the player has typed their first line. The
family as a whole is about ninety minutes of target time, and a genuine beginner
will take longer than target on nearly all of it. Trimming it to fit the number
would have meant dropping rungs, and the missing rungs were the entire complaint.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import sys
import textwrap

from ..schema import Problem, TARGET_SECONDS, build_hint_tree
from ._base import code_problem, debug_problem, dedent, mcq_problem
from ...puzzles import shuffle_runes

REALM = "python_village"

# The bottom of the ramp, and the selector has to reach for it before anything
# else. This was 2.0 — the weighting onboarding and reasoning use — which does
# not deliver that sentence: oop_language weights its GUIDED rungs at 2.5, so on
# a fresh save the highest-scoring encounter in the entire corpus was
# `oopl-repr-guided`, a fill-in-the-blank inside a `__repr__`. A player who has
# never written Python was being handed a dunder method as their first
# encounter, and the rung that says "here is one line of Python" sat 266th.
#
# `profile_weight` is the only dial the corpus has for "reach for this first",
# so it is set to a value that actually wins rather than to a value that matches
# the neighbours. It is deliberately the largest weight in the corpus, and it is
# pinned from the other end by tests/test_first_steps.py, which asserts on the
# real engine that a fresh save's first encounter is the root of this chain — so
# if some future family outbids it, that is a failing test and not a silent
# regression back to `__repr__`.
Q = {"PRACTICAL": 3.0, "GENERAL_SWE": 3.0, "SECURITY_ENGINEERING": 3.0}

VIZ = {"type": "array_scan",
       "caption": "One line at a time. Write down what changed."}

# Filled by the builders, raised as one report at the end of `build`, so a single
# run names every disagreement rather than only the first one.
_AUDIT: list = []

_TRACE_FILE = "<first-steps-trace>"

# Marks a problem whose `prerequisites` are preconditions rather than a
# suggested order: do the named problem first or this one cannot be read. Read
# by adaptive.gating_prerequisites; see the note at the end of `build`.
#
# Spelled out in both places rather than imported, because a corpus family
# importing the selector is the wrong direction for this dependency — content
# should not know what reads it. The two literals are held equal by
# tests/test_first_steps.py::test_the_declaration_travels_with_the_problem,
# which compares the set of tagged problems in the built corpus against this
# family, so a rename on one side is a failing test rather than a gate that
# silently stops gating.
ORDER_TAG = "order:strict"


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def _code(text: str) -> str:
    """Dedent and drop the trailing newline: the front end numbers
    `code.split('\\n')`, and a trailing newline would add a phantom last line."""
    return textwrap.dedent(text).strip("\n")


def _block(text: str, lang: str = "") -> str:
    return "```" + lang + "\n" + text.rstrip() + "\n```"


def _numbered(code: str) -> str:
    return "\n".join("%2d  %s" % (i + 1, line)
                     for i, line in enumerate(code.split("\n")))


def _same(given: str, expected: str) -> bool:
    if given == expected:
        return True
    try:
        return ast.literal_eval(given) == ast.literal_eval(expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Build-time execution: ask Python rather than remember
# ---------------------------------------------------------------------------

def _snapshots(code: str) -> dict:
    """Per line, the variables the code left behind on each visit to that line.

    Consecutive events on one line collapse into one visit, so "after line 4" is
    a single unambiguous moment for a line that runs once, and is refused
    outright for a line inside a loop.
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


def _check_trace(pid: str, code: str, marks: list) -> None:
    if sys.gettrace() is not None:
        return                      # a debugger or coverage tool owns the hook
    visits = _snapshots(code)
    for line, variable, expected, _hint in marks:
        seen = visits.get(line, [])
        if len(seen) != 1:
            _AUDIT.append(f"{pid}: line {line} runs {len(seen)} times; a "
                          f"checkpoint there has no single honest answer")
            continue
        if variable not in seen[0]:
            _AUDIT.append(f"{pid}: {variable!r} does not exist after line {line}")
            continue
        actual = repr(seen[0][variable])
        if not _same(expected, actual):
            _AUDIT.append(f"{pid}: after line {line}, {variable} is really "
                          f"{actual}, not {expected}")


def _replay(code: str, operations: str, probe: str):
    """Run the operations one top-level statement at a time, reading the probe
    before anything happens and after every statement."""
    namespace: dict = {}
    exec(compile(code, "<first-steps-state>", "exec"), namespace)
    start = repr(eval(probe, namespace))
    source = operations.split("\n")
    steps = []
    for node in ast.parse(operations).body:
        text = "\n".join(source[node.lineno - 1:node.end_lineno])
        module = ast.Module(body=[node], type_ignores=[])
        exec(compile(module, "<first-steps-state>", "exec"), namespace)
        steps.append((text, repr(eval(probe, namespace))))
    return start, steps


def _call(source: str, fn_name: str, args: list) -> str:
    """Run one version on one input. Output is swallowed: half the point of
    this family is that printing is not returning, so several of these versions
    print on purpose and a build log is not the place for it."""
    ns: dict = {}
    exec(compile(source, "<first-steps-spell>", "exec"), ns)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return repr(ns[fn_name](*copy.deepcopy(args)))
    except Exception as exc:                       # a crash is a divergence too
        return "raises " + type(exc).__name__


def _divergence(honest: str, cursed: str, fn_name: str, probes: list):
    for args in probes:
        good, bad = _call(honest, fn_name, args), _call(cursed, fn_name, args)
        if good != bad:
            return args, good, bad
    return None


# ---------------------------------------------------------------------------
# The single-answer fallback every puzzle carries
# ---------------------------------------------------------------------------
#
# `validate` reads `mcq["choices"]` and `mcq["answer"]` for any entry of kind
# `mcq`, and anything that cannot render the full puzzle interface still has a
# question with exactly one true answer. No wrong choice here is invented: each
# is a value the code really produces at some point, or the value a named
# beginner mistake produces.

def _one_answer(pid: str, question: str, correct: str, wrong: list) -> dict:
    choices = [correct]
    for value in wrong:
        if len(choices) >= 4 or value in choices:
            continue
        if _same(value, correct):
            if value != correct:
                _AUDIT.append(f"{pid}: near-miss {value} is the same value as "
                              f"the answer {correct}")
            continue
        choices.append(value)
    if len(choices) < 2:
        _AUDIT.append(f"{pid}: the single-answer form has nothing to choose from")
    answer = sum(ord(c) for c in pid) % len(choices)
    choices[0], choices[answer] = choices[answer], choices[0]
    return {"question": question, "choices": choices, "answer": answer}


# ---------------------------------------------------------------------------
# Problem builders
# ---------------------------------------------------------------------------

# `schema.PATTERN_ORACLE` and `PATTERN_STRUCTURE` have an entry per pattern and
# none yet for LANGUAGE, so `build_hint_tree` opens its first two rungs with two
# blank lines. These are those two missing sentences, applied to the tree after
# it is built. When the schema grows a LANGUAGE entry of its own, delete this and
# the patch below it — `_patch_oracle` only rewrites a rung that actually starts
# empty, so it becomes a no-op rather than a silent override.
_LANGUAGE_ORACLE = ("This is a LANGUAGE problem. The subject is Python itself — "
                    "a statement, an operator, a name — and not a data "
                    "structure. Swap the values for other values and the lesson "
                    "is unchanged.")
_LANGUAGE_STRUCTURE = ("Nothing to reach for. Read the line you are being asked "
                       "about and say what Python does with it, left to right.")


def _patch_oracle(problem):
    if problem.pattern != "LANGUAGE" or len(problem.hint_tree) < 2:
        return problem
    for index, text in ((0, _LANGUAGE_ORACLE), (1, _LANGUAGE_STRUCTURE)):
        rung = problem.hint_tree[index]
        if rung.get("body", "").startswith("\n\n"):
            rung["body"] = text + rung["body"]
    return problem


def _reading_hints(nudge: str, method: str, answer: str) -> list:
    """Three rungs. A reading question does not need five, and padding it with
    three near-identical restatements is how a hint tree stops being read."""
    return [
        {"level": 1, "spell": "ORACLE", "mana": 2, "rank_cost": "A",
         "title": "Oracle", "body": nudge.strip()},
        {"level": 2, "spell": "REVEAL_PATH", "mana": 3, "rank_cost": "A",
         "title": "Reveal Path", "body": method.strip()},
        {"level": 5, "spell": "PHOENIX", "mana": 8, "rank_cost": "LEARNING_CLEAR",
         "title": "Phoenix", "body": answer.strip()},
    ]


def _seed(pid: str) -> int:
    """A stable per-problem number. Used to place a multiple-choice answer and
    to shuffle a rune tray: both have to look arbitrary and neither may move
    between builds, or a player who comes back to a problem meets a different
    one."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(pid)) % 100000


def _place(pid: str, choices: list, answer: int):
    """Move the true answer to a position derived from the id.

    Written by hand, the right answer lands first far more often than chance —
    it is the one the author was thinking about. Twenty-five reading questions
    with a bias like that teach a player to pick the top option and move on,
    which is the opposite of reading. The position is a function of the id, so
    it is stable between builds and unguessable between problems.
    """
    choices = list(choices)
    target = _seed(pid) % len(choices)
    choices[target], choices[answer] = choices[answer], choices[target]
    return choices, target


def _read(pid, title, statement, code, choices, answer, explanation, *,
          family, nudge, method, pattern="LANGUAGE", seconds=60,
          tier="GUIDED", tags=()):
    """A CODE_READING question: here is the code, say what it does."""
    choices, answer = _place(pid, choices, answer)
    problem = mcq_problem(
        id=pid, title=title, realm=REALM, pattern=pattern, difficulty=tier,
        statement=statement, code=code, choices=choices, answer=answer,
        explanation=explanation, encounter="CODE_READING", family=family,
        seconds=seconds)
    problem.hint_tree = _reading_hints(nudge, method, explanation)
    problem.profile_weight = dict(Q)
    problem.visualization = dict(VIZ)
    problem.tags = ["first-steps", "reading", family] + list(tags)
    return problem


def _puzzle(pid, title, difficulty, statement, kind, spec, *, pattern, family,
            hints, failures=(), tags=(), seconds=None):
    seconds = seconds or TARGET_SECONDS[difficulty]
    return Problem(
        id=pid, title=title, realm=REALM, pattern=pattern, difficulty=difficulty,
        problem_statement=_code(statement), entry={"kind": "mcq", "name": pid,
                                                   "signature": ""},
        canonical_solution="", encounter_kind=kind,
        source_type="GENERAL_INTERVIEW", mcq=spec, optimal_complexity={},
        common_failures=list(failures), hint_tree=hints,
        visualization=dict(VIZ), spaced_repetition_family=family,
        estimated_seconds=seconds, target_seconds=seconds,
        profile_weight=dict(Q),
        tags=["first-steps", "puzzle", family] + list(tags))


def _trace(pid, title, statement, code, marks, *, family, nudge, walkthrough,
           misreads=(), pattern="LANGUAGE", tier="GUIDED", failures=(),
           tags=()):
    """A TRACE puzzle over top-level code. `marks` is
    [(line, variable, expected repr, hint)] and every one of them is checked
    against a real run before the problem is allowed to exist."""
    code = _code(code)
    _check_trace(pid, code, marks)
    lines = code.split("\n")

    def answered(subset):
        rows, last = [], None
        for line, variable, expected, _h in subset:
            if line != last:
                rows.append("line %-3d %s" % (line, lines[line - 1].strip()))
                last = line
            rows.append("         %s is %s" % (variable, expected))
        return "\n".join(rows)

    hints = build_hint_tree(
        pattern, nudge=nudge,
        visual="Two columns on paper: the line number, and what changed. One row "
               "per line executed. Nobody traces reliably in their head and "
               "nobody is expected to.",
        pseudocode=_block(_numbered(code)) + "\n\nYou are only asked about the "
                   "marked lines, but you cannot reach them without filling in "
                   "every row above them.",
        fragment="The first mark, answered, so you can check your method:\n\n"
                 + _block(answered(marks[:1])),
        solution=_block(answered(marks)) + "\n\n" + walkthrough.strip())

    line, variable, expected, _hint = marks[-1]
    spec = {"code": code,
            "checkpoints": [{"after_line": ln, "variable": var,
                             "expected": exp, "hint": hint}
                            for ln, var, exp, hint in marks],
            "explanation": walkthrough.strip()}
    spec.update(_one_answer(
        pid, "After line %d, what does `%s` hold?" % (line, variable),
        expected, list(misreads) + [m[2] for m in marks]))
    return _patch_oracle(
        _puzzle(pid, title, tier, statement, "TRACE", spec, pattern=pattern,
                family=family, hints=hints, failures=failures,
                tags=list(tags) + ["trace"]))


def _state(pid, title, statement, code, operations, probe, final_state,
           explanation, *, family, nudge, misreads=(), pattern="ARRAY",
           tier="GUIDED", failures=(), tags=()):
    """A STATE_PREDICT puzzle: the operations are given, say what is left."""
    code, operations = _code(code), _code(operations)
    start, steps = _replay(code, operations, probe)
    if not _same(final_state, steps[-1][1]):
        _AUDIT.append(f"{pid}: the operations really leave {steps[-1][1]}, "
                      f"not {final_state}")

    def table(rows):
        return "\n".join("%-34s %s" % (text, value) for text, value in rows)

    hints = build_hint_tree(
        pattern, nudge=nudge,
        visual="Write the structure down after every single operation. The one "
               "that catches people is never the clever operation. It is the "
               "third boring one, done from memory.",
        pseudocode="Before anything happens:\n\n" + _block(probe + "  ->  " + start)
                   + "\n\nNow take the operations one at a time.",
        fragment=_block(table(steps[:max(1, len(steps) - 1)]))
                 + "\n\nOne operation left.",
        solution=_block(table(steps)) + "\n\nFinal state: " + final_state
                 + "\n\n" + explanation.strip())

    spec = {"code": code, "operations": operations, "probe": probe,
            "final_state": final_state, "explanation": explanation.strip()}
    spec.update(_one_answer(
        pid, "What does it hold when the operations finish?", final_state,
        list(misreads) + [value for _t, value in reversed(steps[:-1])] + [start]))
    return _patch_oracle(
        _puzzle(pid, title, tier, statement, "STATE_PREDICT", spec,
                pattern=pattern, family=family, hints=hints,
                failures=failures, tags=list(tags) + ["state"]))


def _flaw(pid, title, statement, honest, cursed, line, explanation, probes, *,
          family, nudge, pattern="LANGUAGE", tier="GUIDED", tags=()):
    """A SPOT_THE_FLAW puzzle: two near-identical versions, one line cursed."""
    honest, cursed = _code(honest), _code(cursed)
    good_lines, bad_lines = honest.split("\n"), cursed.split("\n")
    if len(good_lines) != len(bad_lines):
        _AUDIT.append(f"{pid}: the two versions have different line counts")
    else:
        differing = [i + 1 for i, (a, b) in enumerate(zip(good_lines, bad_lines))
                     if a != b]
        if differing != [line]:
            _AUDIT.append(f"{pid}: the versions differ on lines {differing}, but "
                          f"the answer says line {line}")
    fn_name = honest.split("(")[0].replace("def ", "").strip()
    split = _divergence(honest, cursed, fn_name, probes)
    if split is None:
        _AUDIT.append(f"{pid}: the cursed version agrees with the honest one on "
                      f"every probe — there is no flaw to find")
        args, good, bad = probes[0], "?", "?"
    else:
        args, good, bad = split
    call = "%s(%s)" % (fn_name, ", ".join(repr(a) for a in args))
    evidence = ("On `%s` the honest version gives `%s`. The cursed one gives "
                "`%s`." % (call, good, bad))

    hints = build_hint_tree(
        "DEBUGGING", nudge=nudge,
        visual="Read the two side by side, line against matching line. Do not "
               "read for sense. Read for difference — sense is exactly what "
               "hides a one-character curse.",
        pseudocode=evidence + "\n\nNow work backwards: which single line could "
                   "produce that difference and nothing else?",
        fragment="The curse is in lines %d to %d of the cursed version. Three "
                 "lines, one of them lying."
                 % (max(1, line - 1), min(len(bad_lines), line + 1)),
        solution="Line %d.\n\n" % line
                 + _block("cursed:  " + bad_lines[line - 1].strip()
                          + "\nhonest:  " + good_lines[line - 1].strip())
                 + "\n\n" + explanation.strip() + "\n\n" + evidence)

    labelled = ["line %d: %s" % (i + 1, text.strip() or "(blank)")
                for i, text in enumerate(bad_lines)]
    spec = {"code": cursed, "reference_code": honest, "flawed_line": line,
            "explanation": explanation.strip() + " " + evidence}
    spec.update(_one_answer(pid, "Which line is cursed?", labelled[line - 1],
                            [labelled[i] for i in (line, line - 2, line + 1)
                             if 0 <= i < len(labelled)]))
    return _puzzle(pid, title, tier, statement, "SPOT_THE_FLAW", spec,
                   pattern=pattern, family=family, hints=hints,
                   tags=list(tags) + ["flaw"])


def _strike(canonical: str, blanks) -> str:
    """The canonical solution with the named targets struck out.

    `blanks` is an ordered sequence of (target, hint). The first line still
    carrying the target is rewritten with `__BLANK__` in its place and the hint
    appended as a numbered comment. A target that is not there is an error at
    build time rather than a scaffold with nothing missing in it — a fill-in
    with nothing to fill in grades as a free clear and teaches nothing.
    """
    lines = dedent(canonical).rstrip("\n").splitlines()
    for number, (target, hint) in enumerate(blanks, 1):
        for i, line in enumerate(lines):
            if target in line and "__BLANK__" not in line:
                lines[i] = line.replace(target, "__BLANK__", 1) \
                    + "  # %d. %s" % (number, hint)
                break
        else:
            raise ValueError("blank target %r is not in the canonical solution"
                             % target)
    return "\n".join(lines) + "\n"


FILL_NOTE = dedent("""

    Each `__BLANK__` is exactly one expression or one statement. Fill it in and
    change nothing else — the code around it is already correct, and is there to
    tell you what the missing piece has to do.
""")


def _fill(pid, title, statement, fn, params, ref, canonical, visible, hidden, *,
          blanks, family, nudge, pseudocode, edges=(), failures=(),
          pattern="LANGUAGE", tier="GUIDED", time="O(1)", space="O(1)",
          tags=(), visual=""):
    """A MISSING_RUNE encounter: working code with one hole struck out of it."""
    canonical = dedent(canonical)
    partial = _strike(canonical, list(blanks)[1:]) if len(blanks) > 1 else ""
    return _patch_oracle(code_problem(
        id=pid, title=title, realm=REALM, pattern=pattern, difficulty=tier,
        family=family, profile_weight=dict(Q), viz=dict(VIZ),
        statement=dedent(statement) + FILL_NOTE,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges,
        time_complexity=time, space_complexity=space,
        failures=list(failures), nudge=nudge, pseudocode=pseudocode,
        visual=visual or "The program already works. Read it top to bottom, "
                         "then fill the hole. You are finishing someone else's "
                         "sentence, not writing an essay.",
        fragment=_block(partial.rstrip(), "python") if partial else "",
        starter_code=_strike(canonical, blanks), encounter="MISSING_RUNE",
        tags=["first-steps", "fill-in", family] + list(tags)))


def _assemble(pid, title, statement, fn, params, ref, canonical, visible,
              hidden, *, distractors, notes=None, family, nudge, pseudocode,
              edges=(), failures=(), pattern="LANGUAGE", tier="GUIDED",
              time="O(1)", space="O(1)", tags=()):
    """A RUNE_ASSEMBLY encounter: the lines exist, scattered. Order them.

    The runes are cut from the canonical solution rather than typed a second
    time, so the intended ordering cannot drift away from the answer the tests
    actually grade.
    """
    canonical = dedent(canonical)
    problem = _patch_oracle(code_problem(
        id=pid, title=title, realm=REALM, pattern=pattern, difficulty=tier,
        family=family, profile_weight=dict(Q), viz=dict(VIZ),
        statement=dedent(statement), fn_name=fn, params=params, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden, edges=edges,
        time_complexity=time, space_complexity=space, failures=list(failures),
        nudge=nudge, pseudocode=pseudocode,
        visual="Find the two lines that anchor it — the `def` and the `return`. "
               "Everything else lives between them, indented one level in.",
        encounter="RUNE_ASSEMBLY",
        tags=["first-steps", "assembly", family] + list(tags)))
    notes = notes or {}
    runes = []
    for line in canonical.splitlines():
        if not line.strip():
            continue
        spaces = len(line) - len(line.lstrip(" "))
        if spaces % 4:
            raise ValueError("rune indentation must be a multiple of four: %r"
                             % line)
        runes.append({"text": line.strip(), "indent": spaces // 4,
                      "distractor": False, "note": notes.get(line.strip(), "")})
    seen = {r["text"] for r in runes}
    for text, indent, note in distractors:
        if text in seen:
            raise ValueError("distractor duplicates a real rune: %r" % text)
        runes.append({"text": text, "indent": indent, "distractor": True,
                      "note": note})
    problem.mcq = {"runes": runes, "shuffle": shuffle_runes(runes, _seed(pid))}
    return problem


def _write(pid, title, statement, fn, params, ref, canonical, visible, hidden, *,
           family, nudge, pseudocode, starter, edges=(), failures=(),
           pattern="LANGUAGE", tier="TUTORIAL", time="O(n)", space="O(1)",
           tags=()):
    """A CODE_BATTLE at TUTORIAL: a commented skeleton, one comment per line of
    code the player owes. Structure given, bodies theirs."""
    return _patch_oracle(code_problem(
        id=pid, title=title, realm=REALM, pattern=pattern, difficulty=tier,
        family=family, profile_weight=dict(Q), viz=dict(VIZ),
        statement=dedent(statement), fn_name=fn, params=params, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden, edges=edges,
        time_complexity=time, space_complexity=space, failures=list(failures),
        nudge=nudge, pseudocode=pseudocode,
        visual="One comment, one line of code. Write the first line, run it, "
               "then write the second. Do not write all four and hope.",
        starter_code=starter, encounter="CODE_BATTLE",
        tags=["first-steps", "handover", family] + list(tags)))


# ===========================================================================
# CONCEPT 1 - 5
# No function appears anywhere in this section. Every problem is one expression
# or a handful of top-level lines, read or traced.
# ===========================================================================

def _values() -> list:
    return [
        _read(
            "fs-see-a-value", "One Line, One Value",
            """
            Python works out an expression and produces a **value**. `print`
            takes a value and writes it on the screen. That is the whole job:
            nothing is stored and nothing is sent anywhere, the characters just
            appear.

                print(3 + 4)

            writes `7`. The arithmetic happens first; `print` shows what came
            out of it.

            **What appears on the screen when this runs?**
            """,
            "print(10 - 4)",
            ["10 - 4", "6", "4", "nothing — it was never stored anywhere"], 1,
            "Python works out `10 - 4` and gets `6`. `print` writes that value "
            "on the screen. What you see is the result, never the expression "
            "that produced it.",
            family="first_steps_values",
            nudge="Do the subtraction yourself. Whatever you get is what "
                  "appears.",
            method="`print(X)` shows the value of X. Work out X first, and that "
                   "is the answer.",
        ),

        _read(
            "fs-see-some-text", "Quotes Make It Text",
            """
            Quotation marks tell Python that what is between them is **text**
            rather than an instruction. `"root"` is a value in exactly the way
            `6` is a value. The quotes are punctuation for Python's benefit;
            they are not part of the text.

                print("scan complete")

            writes `scan complete` — no quotes on the screen.

            **What appears on the screen when this runs?**
            """,
            'print("root")',
            ['root', '"root"', 'print("root")',
             'the value stored under the name root'], 0,
            "The quotes mark where the text starts and stops, so Python knows "
            "`root` is four characters and not a name it should go looking up. "
            "`print` writes the characters, not the punctuation around them.",
            family="first_steps_values",
            nudge="The quotes are for Python, not for you. Ask what is left "
                  "once Python has read them and thrown them away.",
            method="Text between quotes is a value. `print` writes that value "
                   "and nothing else.",
        ),

        _read(
            "fs-two-lines", "Top to Bottom",
            """
            A program is a list of lines and Python runs them in order, one at a
            time, starting at the top. There is no cleverness about it. Each
            `print` writes its own line.

                print("first")
                print("second")

            writes `first`, then `second`, on two lines.

            **What appears on the screen when this runs?**
            """,
            """
            print("scan started")
            print(42)
            """,
            ['`scan started`, then `42`, on two lines',
             '`42`, then `scan started`, on two lines',
             '`scan started 42` on one line',
             'only `42` — the second line replaces the first'], 0,
            "Line 1 runs, then line 2 runs. Each `print` ends the line it wrote, "
            "so the two values land one above the other. Order on the screen is "
            "order in the file.",
            family="first_steps_values",
            nudge="Read the file downward and write down what each line puts on "
                  "the screen.",
            method="Two prints, two lines, in the order they appear.",
        ),

        # -- concept 2: a name for a value --------------------------------
        _trace(
            "fs-name-a-value", "A Name for a Value",
            """
            `=` gives a value a **name** so you can use it again later. It is
            not the equals sign from mathematics: it does not state that two
            things are equal, it points a name at a value.

                attempts = 5

            After that line, the name `attempts` refers to `5`. The name goes on
            the left, the value on the right, and never the other way around.

            **After line 1, what does `threat_level` hold?**
            """,
            "threat_level = 3",
            [(1, "threat_level", "3",
              "The value on the right of the `=`, under the name on the left.")],
            family="first_steps_names",
            nudge="Read it right to left: work out the value, then hang the "
                  "name on it.",
            walkthrough="Python evaluates `3`, which is already a value, and "
                        "binds the name `threat_level` to it. From here on, "
                        "writing `threat_level` is the same as writing `3`.",
            misreads=["'3'", "None"],
        ),

        _trace(
            "fs-name-then-use", "Using the Name",
            """
            Once a name exists, writing it anywhere means the value it refers
            to. Python swaps the name for its value before doing anything else.

                width = 5
                area = width * width

            On line 2 Python replaces `width` with `5` twice, multiplies, and
            binds `area` to `25`.

            **Work down the three lines. After line 3, what does `cells` hold?**
            """,
            """
            rows = 4
            columns = 3
            cells = rows * columns
            """,
            [(3, "cells", "12", "Two names, each replaced by its value, then "
                                "multiplied.")],
            family="first_steps_names",
            nudge="Substitute the values in by hand, then do the arithmetic.",
            walkthrough="`rows` is `4` and `columns` is `3`, so line 3 is "
                        "`cells = 4 * 3`. The name `cells` is then bound to "
                        "`12`. Nothing about `rows` or `columns` changed.",
            misreads=["7", "43"],
        ),

        _trace(
            "fs-name-on-the-left", "The Name Goes on the Left",
            """
            A name can be pointed at a new value whenever you like, including a
            value worked out from the name's own current value. This is the line
            that looks wrong to everybody at first:

                hits = hits + 1

            As an equation it is nonsense. As an instruction it is not: Python
            works out the **right** side first, using the current value, and
            then points the name at the result. Old value in, new value out.

            **Trace it. What does `hits` hold after line 2, and after line 3?**
            """,
            """
            hits = 1
            hits = hits + 1
            hits = hits + 1
            """,
            [(2, "hits", "2", "Right side first: 1 + 1."),
             (3, "hits", "3", "And again, with the value line 2 left behind.")],
            family="first_steps_names",
            nudge="Cover the left of the `=` with your thumb. Work out what is "
                  "left. That value is what the name becomes.",
            walkthrough="Line 1 binds `hits` to `1`. On line 2 the right side "
                        "is `1 + 1`, so `hits` becomes `2`. On line 3 the right "
                        "side is `2 + 1`, so `hits` becomes `3`. The name is a "
                        "label being moved, not a claim being made.",
            misreads=["1", "4"],
        ),

        _read(
            "fs-two-names", "A Copy, Not a Link",
            """
            `second = first` does not tie the two names together. It works out
            the value of `first` **at that moment** and binds `second` to that
            value. Changing `first` afterwards does not chase `second` down and
            update it.

                a = 1
                b = a
                a = 7

            leaves `b` as `1`.

            **What appears on the screen?**
            """,
            """
            first = 10
            second = first
            first = 99
            print(second)
            """,
            ["10", "99", "109", "nothing — `second` was used up on line 3"], 0,
            "Line 2 asked what `first` was worth right then: `10`. `second` was "
            "bound to `10` and has referred to `10` ever since. Line 3 moved "
            "`first`, and only `first`.",
            family="first_steps_names",
            nudge="Ask what `first` was worth on line 2, not what it is worth "
                  "at the end.",
            method="Write the value of each name after every line. Two columns, "
                   "four rows.",
        ),

        _read(
            "fs-name-rules", "What Counts as a Name",
            """
            A name may contain letters, digits and underscores, and may not
            start with a digit. No spaces, no hyphens — `a-b` already means
            *a minus b*. A short list of words are reserved by the language
            itself and cannot be used as names: `if`, `for`, `class`, `return`
            and a few others.

            Three of the four lines below are rejected before the program even
            starts.

            **Which one is a legal name?**
            """,
            """
            2nd_scan = 1
            scan-count = 1
            scan_count = 1
            class = 1
            """,
            ["`2nd_scan`", "`scan-count`", "`scan_count`", "`class`"], 2,
            "`2nd_scan` starts with a digit. `scan-count` reads as `scan` minus "
            "`count`, and Python will not accept a subtraction on the left of "
            "an `=`. `class` is a reserved word. `scan_count` is the ordinary "
            "form, and underscores between words are the usual convention.",
            family="first_steps_names",
            nudge="Read each one the way Python would: is there a character in "
                  "there that already means something else?",
            method="Letters, digits, underscores. Not first a digit. Not a word "
                   "the language already owns.",
        ),

        # -- concept 3: text, numbers, and True/False ----------------------
        _read(
            "fs-two-plus-two", "Why Two Plus Two Is Not Four",
            """
            `+` does not do one thing. Between two numbers it adds; between two
            pieces of text it joins them end to end. `"a" + "b"` is `"ab"`.
            Nothing is being added, because nothing there is a number — `"2"` is
            a character that happens to look like one.

                print("cat" + "fish")

            writes `catfish`.

            **What appears on the screen?**
            """,
            'print("2" + "2")',
            ["4", "22", '"22"', "TypeError"], 1,
            "Both sides are text, so `+` joins them: the character `2` followed "
            "by the character `2`, which is the two-character text `22`. It is "
            "not the number twenty-two either — it is text that reads like it.",
            family="first_steps_types",
            nudge="Look at the quotes. Are those numbers, or are they "
                  "characters that look like numbers?",
            method="`+` between text joins. Write the left, then the right, "
                   "with nothing between them.",
        ),

        _trace(
            "fs-text-repeat", "Text Times a Number",
            """
            `*` is the same story. Between two numbers it multiplies; between a
            piece of text and a number it repeats the text that many times.

                print("ab" * 2)

            writes `abab`. There are no spaces and no separators added — the
            copies sit directly against each other.

            **After line 2, what does `banner` hold? Give the text exactly, with
            its quotes.**
            """,
            """
            mark = "ab"
            banner = mark * 3
            """,
            [(2, "banner", "'ababab'",
              "Three copies of the two characters, run together.")],
            family="first_steps_types",
            nudge="Write out the copies side by side and count the characters. "
                  "You should end up with six.",
            walkthrough="`mark` is the two characters `ab`. `mark * 3` builds a "
                        "new piece of text, `ababab`, and binds `banner` to it. "
                        "`mark` itself is unchanged — repeating text produces a "
                        "new value rather than editing the old one.",
            misreads=["'ab ab ab'", "'ab3'", "6"],
        ),

        _read(
            "fs-text-plus-number", "Python Will Not Guess",
            """
            Text plus text joins. Number plus number adds. Text plus number is
            neither, and Python refuses to choose on your behalf: it stops and
            says so.

            The message it produces is not an accusation, it is a description:
            *can only concatenate str (not "int") to str*. `str` is text, `int`
            is a whole number, and `concatenate` is the joining that `+` was
            about to do.

            **What happens when this runs?**
            """,
            'print("2" + 2)',
            ["22", "4", 'TypeError: can only concatenate str (not "int") to str',
             "`2 2`"], 2,
            "There is no answer that is right for both readings, so Python "
            "raises a TypeError and the program stops at that line. This is the "
            "most common error of anyone's first week, and the fix is two "
            "problems away.",
            family="first_steps_types",
            nudge="One side is text and the other is a number. Which of the two "
                  "jobs of `+` is Python supposed to pick?",
            method="When the types do not fit, Python stops rather than "
                   "guessing. The error names both types.",
        ),

        _trace(
            "fs-same-symbol-two-jobs", "The Same Symbol, Two Jobs",
            """
            Whether `* 2` doubles a quantity or duplicates some characters
            depends entirely on what is to the left of it. This is why the
            difference between `12` and `"12"` matters, and why it is worth
            looking at the quotes before anything else.

            **Trace all four lines. What is `stretched` after line 3, and what
            is `scaled` after line 4?**
            """,
            """
            written = "12"
            counted = 12
            stretched = written * 2
            scaled = counted * 2
            """,
            [(3, "stretched", "'1212'", "Text repeated: two copies, joined."),
             (4, "scaled", "24", "Number multiplied.")],
            family="first_steps_types",
            nudge="Line 1 has quotes. Line 2 does not. That single difference "
                  "decides both answers.",
            walkthrough="`written` is text, so `written * 2` repeats it and "
                        "gives `'1212'`. `counted` is a number, so "
                        "`counted * 2` multiplies it and gives `24`. Same "
                        "symbol, same `2`, two different operations, chosen by "
                        "the type of the value on the left.",
            misreads=["'24'", "1212"],
        ),

        _read(
            "fs-yes-or-no", "A Third Kind of Value",
            """
            Besides text and numbers there is a third kind of value with exactly
            two members: `True` and `False`. You get one by asking a question.

            `==` — two equals signs — asks *are these the same?* and produces
            `True` or `False`. One `=` gives a name to a value; two `==` compare
            two values and change nothing. Mixing them up is a rite of passage.

                print(5 == 5)

            writes `True`.

            **What appears on the screen, on three lines?**
            """,
            """
            print("root" == "root")
            print("root" == "Root")
            print(3 == 3)
            """,
            ["`True`, `False`, `True`", "`True`, `True`, `True`",
             "`True`, `False`, `False`", "`yes`, `no`, `yes`"], 0,
            "The first compares identical text and gives `True`. The second "
            "differs in one character — capital R is not lowercase r, and "
            "Python compares character by character — so `False`. The third "
            "compares two equal numbers and gives `True`.",
            family="first_steps_types",
            nudge="Compare the second pair character by character, including "
                  "the capital letter.",
            method="`==` produces `True` or `False`, nothing else. Answer each "
                   "of the three lines separately.",
        ),

        # -- concept 4: calling something that already exists ---------------
        _trace(
            "fs-call-len", "Calling Something That Exists",
            """
            Python ships with a set of ready-made operations. You use one by
            writing its name, then parentheses, then the value you want it to
            work on. That is a **call**, and a call produces a value you can
            store like any other.

            `len` reports how many items are in something. For text, that is how
            many characters.

                size = len("abc")

            binds `size` to `3`.

            **After line 2, what does `size` hold?**
            """,
            """
            password = "hunter2"
            size = len(password)
            """,
            [(2, "size", "7", "Count the characters, including the digit.")],
            family="first_steps_calls",
            nudge="Count the characters of `hunter2` one at a time. The digit "
                  "is a character like any other.",
            walkthrough="`len(password)` looks at the seven characters of "
                        "`hunter2` and produces `7`. The parentheses are how "
                        "you hand a value to a call; the result comes back out "
                        "and line 2 binds `size` to it.",
            misreads=["6", "8", "'hunter2'"],
        ),

        _trace(
            "fs-call-str", "Making a Number Into Text",
            """
            `str` takes any value and produces the text version of it. That is
            the fix for the TypeError from earlier: you cannot join a number
            onto text, but you can join the **text of** a number onto text.

                "count: " + str(9)

            gives `'count: 9'`.

            **After line 2, what does `report` hold? Give the text with its
            quotes.**
            """,
            """
            failures = 3
            report = "failures: " + str(failures)
            """,
            [(2, "report", "'failures: 3'",
              "The space after the colon is inside the quotes already.")],
            family="first_steps_calls",
            nudge="`str(3)` is the one-character text `'3'`. Now join it on the "
                  "end.",
            walkthrough="`str(failures)` turns the number `3` into the text "
                        "`'3'`. Both sides of the `+` are now text, so it joins "
                        "them into `'failures: 3'`. Without `str` this line "
                        "would raise TypeError, which is exactly the error you "
                        "saw two problems ago.",
            misreads=["'failures: '", "'failures: failures'", "3"],
        ),

        _trace(
            "fs-call-int", "And Back Again",
            """
            `int` goes the other way: text that looks like a whole number
            becomes that number. This matters because anything typed by a person
            or read from a file arrives as text, even when it looks like a
            quantity.

                int("7") + 1

            gives `8`. Without the `int`, `"7" + 1` raises TypeError.

            **After line 2, what does `value` hold?**
            """,
            """
            typed = "41"
            value = int(typed) + 1
            """,
            [(2, "value", "42", "Convert first, then add.")],
            family="first_steps_calls",
            nudge="Two steps, inside out: the conversion happens first, then "
                  "the addition.",
            walkthrough="`int(typed)` reads the text `'41'` and produces the "
                        "number `41`. Adding `1` gives `42`. Had Python joined "
                        "instead, the answer would have been the text `'411'` — "
                        "which is why the conversion is not optional.",
            misreads=["'411'", "'42'"],
        ),

        _read(
            "fs-call-inside-call", "Inside Out",
            """
            The value handed to a call can itself be the result of a call.
            Python works from the inside out: the innermost call runs first, its
            result becomes the input to the next one, and so on.

                len(str(100))

            is `len("100")`, which is `3`.

            **What appears on the screen?**
            """,
            "print(len(str(70000)))",
            ["5", "70000", "4", "6"], 0,
            "`str(70000)` produces the text `'70000'`. `len` counts its "
            "characters and gets `5`. `print` writes `5`. Read nested calls "
            "from the middle outward, the same way you would nested "
            "parentheses in arithmetic.",
            family="first_steps_calls",
            nudge="Do the inner call first and write down what it produced. "
                  "Then do the outer one on that.",
            method="`str(70000)` first. Then `len` of whatever that was. Then "
                   "print.",
        ),

        _trace(
            "fs-dot-call", "A Call With a Dot",
            """
            Some calls attach to a value with a dot rather than taking it in
            parentheses. `user.upper()` means *upper, applied to user*. The
            parentheses are still there and still empty, because everything this
            call needs is the value in front of the dot.

            It produces a **new** piece of text. It does not modify the original
            — text in Python is never modified in place.

            **After line 2, what does `shouted` hold, and what does `user` hold?**
            """,
            """
            user = "Root"
            shouted = user.upper()
            """,
            [(2, "shouted", "'ROOT'", "Every character in upper case."),
             (2, "user", "'Root'",
              "Unchanged. The call produced a new value rather than editing "
              "this one.")],
            family="first_steps_calls",
            nudge="Answer the easy one first. Then ask whether anything "
                  "actually happened to `user` on line 2.",
            walkthrough="`user.upper()` builds a new piece of text, `'ROOT'`, "
                        "and line 2 binds `shouted` to it. `user` was only read "
                        "from, so it still refers to `'Root'`. If you want the "
                        "upper-case version kept under the old name you have to "
                        "say so: `user = user.upper()`.",
            misreads=["'root'", "None"],
        ),

        # -- concept 5: what an indent means --------------------------------
        _read(
            "fs-indent-belongs", "Lines That Belong to Other Lines",
            """
            `if` runs a group of lines only when something is true. The line
            ends with a colon, and the lines that belong to it are pushed in —
            **indented** — by four spaces. Where other languages use braces,
            Python uses that indentation, and it is not decoration: it is the
            only thing saying which lines are inside.

                if ready:
                    print("go")

            The indented line runs only when `ready` is true. A line back at the
            left margin is outside the `if` and runs either way.

            **What appears on the screen?**
            """,
            """
            ready = True
            if ready:
                print("go")
            print("done")
            """,
            ['`go`, then `done`', 'only `done`', 'only `go`',
             '`done`, then `go`'], 0,
            "`ready` is `True`, so the indented line runs and writes `go`. Line "
            "4 is back at the left margin, outside the `if` entirely, so it "
            "runs next and writes `done`.",
            family="first_steps_indent",
            nudge="Two lines print. Decide about each one separately: is it "
                  "inside the `if`, and if so, does the `if` run?",
            method="Indented under the colon means inside. Left margin means "
                   "outside, and outside always runs.",
        ),

        _read(
            "fs-indent-skipped", "The Same Program, One Value Changed",
            """
            This is the previous program with one value flipped. Nothing else
            about it moved, which is the point: the indentation decides *what
            could* be skipped, and the value decides whether it is.

            **What appears on the screen?**
            """,
            """
            ready = False
            if ready:
                print("go")
            print("done")
            """,
            ['`go`, then `done`', 'only `done`', 'only `go`',
             'nothing at all'], 1,
            "`ready` is `False`, so the whole indented block is skipped and "
            "`go` is never written. Line 4 sits outside the `if` and is "
            "untouched by the decision, so `done` appears exactly as before.",
            family="first_steps_indent",
            nudge="The indented line is the only one at risk. The other one was "
                  "never part of the decision.",
            method="Skipping an `if` skips its indented block and nothing else.",
        ),

        _trace(
            "fs-indent-two-lines", "A Block Is Any Number of Lines",
            """
            Everything indented under the colon belongs to the `if`, however
            many lines that is. The block ends where the indentation ends — the
            first line back at the left margin is outside again.

            **Trace it. What is `total` after line 5, and after line 6?**
            """,
            """
            total = 40
            discounted = True
            if discounted:
                total = total - 15
                total = total - 5
            total = total + 100
            """,
            [(5, "total", "20", "Both indented lines ran, in order."),
             (6, "total", "120",
              "Line 6 is at the left margin, so it runs regardless.")],
            family="first_steps_indent",
            nudge="Lines 4 and 5 are both inside. Line 6 is not. Apply them in "
                  "that order.",
            walkthrough="`discounted` is `True`, so the block runs: 40 - 15 is "
                        "25, then 25 - 5 is 20. Line 6 is back at the left "
                        "margin and therefore outside the `if`, so it runs no "
                        "matter what was decided above it: 20 + 100 is 120.",
            misreads=["125", "140", "25"],
        ),

        _read(
            "fs-indent-missing", "Python Is the Only One This Strict",
            """
            In most languages indentation is a courtesy to the next reader. In
            Python it is the syntax, and a missing indent is not a style
            complaint — the program will not start at all.

            The message says exactly what it wanted: an indented block, after
            the line that promised one with its colon.

            **What happens when this runs?**
            """,
            """
            ready = True
            if ready:
            print("go")
            """,
            ['`go` is written', 'nothing is written, but the program finishes',
              'IndentationError: expected an indented block',
              'SyntaxError: invalid syntax on line 1'], 2,
            "Line 2 ends in a colon, which promises a block. Line 3 is at the "
            "left margin, so there is no block. Python stops before running "
            "anything and says so by name. Four spaces on line 3 is the entire "
            "fix.",
            family="first_steps_indent",
            nudge="Line 2 made a promise with that colon. Look at line 3 and "
                  "ask whether it was kept.",
            method="A colon at the end of a line means the next line must be "
                   "indented. No indent, no program.",
        ),
    ]


# ===========================================================================
# CONCEPT 6 - 8
# `def` appears here for the first time, and only because `return`, indentation
# and a value arriving from outside have each been met separately by now.
# ===========================================================================

def _ref_slices():
    return 2 * 4


def _ref_seconds_in(minutes):
    return minutes * 6 * 10


def _ref_bill(amount):
    return "total: %s" % amount


def _ref_fits(capacity, used):
    return -(used - capacity)


def _ref_describe(name):
    return "user " + "".join(c.upper() for c in name)


def _ref_receipt(item, price):
    return "%s: %s" % (item, price)


def _functions() -> list:
    return [
        # -- concept 6: what return means -----------------------------------
        _read(
            "fs-return-vs-print", "Shown Versus Handed Back",
            """
            `def name():` gives a name to a block of lines so they can be run
            later, and running them is `name()` — the parentheses are what
            actually sets it going. The indented lines under the colon are its
            body, which is the same indentation rule you already met.

            Inside a body, `print` and `return` do different jobs. `print` writes
            on the screen and produces nothing. `return` hands a value back to
            whoever ran the function, and that value is what an assignment
            captures.

            **What appears on the screen?**
            """,
            """
            def answer():
                print("printed")
                return "returned"

            result = answer()
            print(result)
            """,
            ['`printed`, then `returned`', 'only `printed`', 'only `returned`',
             '`returned`, then `printed`'], 0,
            "Line 5 runs the body. The body's `print` writes `printed`. Its "
            "`return` hands `\"returned\"` back, which line 5 binds to `result` "
            "— that hands nothing to the screen by itself. Line 6 is what puts "
            "`returned` there.",
            family="first_steps_return",
            nudge="Two lines write to the screen: the one inside the body, and "
                  "line 6. Take them in the order they run.",
            method="`print` writes now. `return` hands a value back, and it "
                   "reaches the screen only if somebody prints it.",
            seconds=90,
        ),

        _read(
            "fs-no-return", "What a Function Hands Back When It Does Not Say",
            """
            A function always hands something back. If its body never says
            `return`, what it hands back is `None` — Python's word for *no value
            at all*.

            This is the trap underneath the previous problem. A function that
            prints looks like it is working, because you can see its output.
            Capture what it hands back and you find nothing there.

            **What appears on the screen?**
            """,
            """
            def shout():
                print("LOUD")

            result = shout()
            print(result)
            """,
            ['`LOUD`, then `None`', 'only `LOUD`', '`LOUD`, then `LOUD`',
             '`LOUD`, then a blank line'], 0,
            "`shout` writes `LOUD` and then ends without returning anything, so "
            "it hands back `None`. `result` is `None`, and line 5 prints it as "
            "the four characters `None`. The game grades the value a function "
            "returns, which is why a printed answer scores zero.",
            family="first_steps_return",
            nudge="The body has no `return` in it. Ask what `result` is worth "
                  "on line 5.",
            method="No `return` means `None` comes back. `print(None)` writes "
                   "`None`.",
            seconds=90,
        ),

        _read(
            "fs-return-first", "Return Also Means Stop",
            """
            `return` does two things at once: it hands a value back, and it ends
            the function there. Lines below it in the body never run.

            That is useful on purpose later — it is how a function answers early
            and gets out. Here it is worth seeing plainly, because a line that
            never runs looks exactly like a line that does.

            **What appears on the screen?**
            """,
            """
            def check():
                return "first"
                print("never")

            print(check())
            """,
            ['`first`', '`never`, then `first`', '`first`, then `never`',
             '`never`'], 0,
            "Line 2 hands `\"first\"` back and the function is over. Line 3 is "
            "real code, correctly indented and part of the body, and it is "
            "unreachable — nothing will ever run it. Line 5 prints the returned "
            "value.",
            family="first_steps_return",
            nudge="Read the body downward and stop where Python stops.",
            method="The first `return` reached ends the function. Everything "
                   "below it in that body is scenery.",
        ),

        _fill(
            "fs-return-a-constant", "Your First Line of Python",
            """
            Everything below is already written except one value. The `def` line
            names the function and the empty parentheses say it takes nothing
            from outside; the indented line is its body; `return` hands a value
            back. You have met all three.

            A pizza is cut into eight slices. Return that number — the digit on
            its own, no quotes, since it is a quantity rather than text.

            Every test calls this the same way, because there is no other way to
            call it. A function that takes nothing gives the same answer every
            time, which is exactly what makes it a safe first thing to write.
            """,
            "slices_per_pizza", "", _ref_slices,
            """
            def slices_per_pizza():
                return 8
            """,
            [("called once", []), ("called again", [])],
            [("and again", []), ("no arguments, ever", [])],
            edges=[("nothing to vary", [])],
            blanks=[("8", "the number to hand back")],
            family="first_steps_return",
            nudge="A bare number needs no quotes. `8` is the quantity eight; "
                  "`\"8\"` would be a character that looks like it.",
            pseudocode="return the number eight",
            failures=["Returning \"8\" as text, which is a different value from "
                      "the number 8",
                      "Printing the number instead of returning it"],
        ),

        # -- concept 7: a value that arrives from outside --------------------
        _read(
            "fs-parameter-read", "A Value That Arrives From Outside",
            """
            A name inside the parentheses of a `def` line is a **parameter**: a
            name with no value yet. It gets one when somebody runs the function
            and supplies it. That is what the value in `greet("root")` is doing
            — it is being handed in.

            One function, written once, then gives a different answer for every
            value handed to it.

            **What appears on the screen?**
            """,
            """
            def greet(who):
                return "hello " + who

            print(greet("root"))
            print(greet("ada"))
            """,
            ['`hello root`, then `hello ada`', '`hello who`, twice',
             '`hello root`, twice', 'TypeError: `who` has no value'], 0,
            "On line 4, `who` refers to `\"root\"` for the length of that run, "
            "so the body builds `hello root`. Line 5 runs the same body again "
            "with `who` referring to `\"ada\"`. The parameter is a name waiting "
            "to be filled in, and it is filled in afresh on every call.",
            family="first_steps_parameters",
            nudge="Run the body twice in your head, once per call, and write "
                  "down what `who` is worth each time.",
            method="The value in the call parentheses lands in the parameter "
                   "name on the def line.",
            seconds=90,
        ),

        _fill(
            "fs-parameter-blank", "Using What Arrived",
            """
            `minutes` is a parameter: on every call it refers to whatever number
            was handed in. You do not know which number, and you do not need to
            — you write the arithmetic once, using the name, and Python fills in
            the value.

            A minute is sixty seconds. Return how many seconds `minutes` minutes
            is.
            """,
            "seconds_in", "minutes", _ref_seconds_in,
            """
            def seconds_in(minutes):
                return minutes * 60
            """,
            [("two minutes", [2]), ("zero", [0])],
            [("ten", [10]), ("one", [1])],
            edges=[("a negative count", [-3])],
            blanks=[("minutes * 60",
                     "how many seconds that many minutes comes to")],
            family="first_steps_parameters",
            nudge="Write the sum you would do on paper for two minutes, then "
                  "replace the 2 with the parameter's name.",
            pseudocode="return minutes multiplied by sixty",
            failures=["Writing a specific number of minutes into the body, "
                      "which answers one call and fails the rest",
                      "Adding sixty instead of multiplying by it"],
        ),

        _fill(
            "fs-parameter-name", "You Choose the Name",
            """
            A parameter's name is yours to pick, and it is only a label — the
            value arrives the same way whatever you call it. What is not
            optional is agreement: the name on the `def` line and the name the
            body uses have to be the same word, or the body is talking about
            something that does not exist.

            The body below already refers to `amount`. Complete the `def` line
            so that is a name the function actually has.
            """,
            "bill", "amount", _ref_bill,
            """
            def bill(amount):
                return "total: " + str(amount)
            """,
            [("five", [5]), ("zero", [0])],
            [("a large total", [1250]), ("a refund", [-7])],
            edges=[("one", [1])],
            blanks=[("amount", "the name the body is already using")],
            family="first_steps_parameters",
            nudge="Read line 2 and write down every name it uses. One of them "
                  "has to come from outside.",
            pseudocode="def bill(<the name line 2 uses>):\n"
                       "    return \"total: \" joined to str(that name)",
            failures=["Naming the parameter something the body never mentions, "
                      "which raises NameError on the first call",
                      "Leaving the parentheses empty, which raises TypeError: "
                      "bill() takes 0 positional arguments but 1 was given"],
        ),

        _fill(
            "fs-two-parameters", "Two Values, In Order",
            """
            A function can take more than one value. The names are separated by
            commas on the `def` line, and the values are filled in left to
            right: in `fits(10, 4)`, `capacity` is `10` and `used` is `4`.
            Position is the whole of the rule. Swap the two values at the call
            and the function does not notice; it just answers the wrong
            question.

            Return how much room is left: the capacity, minus what has been
            used.
            """,
            "fits", "capacity, used", _ref_fits,
            """
            def fits(capacity, used):
                return capacity - used
            """,
            [("room left", [10, 4]), ("exactly full", [5, 5])],
            [("over capacity", [3, 8]), ("nothing used", [7, 0])],
            edges=[("both zero", [0, 0])],
            blanks=[("capacity - used", "what is left of the capacity")],
            family="first_steps_parameters",
            nudge="Subtraction is not symmetric. Decide which name goes first "
                  "before you type either of them.",
            pseudocode="return capacity minus used",
            failures=["Writing `used - capacity`, which is right in magnitude "
                      "and wrong in sign on every test but one"],
        ),

        # -- concept 8: a whole function, from its scattered lines -----------
        _assemble(
            "fs-assemble-describe", "Put the Function Back Together",
            """
            The three lines of this function exist, out of order. Set them in a
            working sequence and at the right depth — the `def` line sits at the
            left margin, and everything in its body is indented one level in.

            The function takes a name, makes an upper-case version of it, and
            returns that with `user ` in front. `describe("root")` gives
            `'user ROOT'`.

            There is no typing here. Order and depth are the entire puzzle, and
            they are the part that is actually being learned.
            """,
            "describe", "name", _ref_describe,
            """
            def describe(name):
                label = name.upper()
                return "user " + label
            """,
            [("root", ["root"]), ("mixed case", ["Ada"])],
            [("already upper", ["X"]), ("with a digit", ["u7"])],
            edges=[("empty name", [""])],
            distractors=[
                ("print(label)", 1,
                 "Printing is not returning. This writes the text on the "
                 "screen and still hands nothing back."),
                ("label = name", 1,
                 "Right shape, wrong step: this skips the upper-casing "
                 "entirely and leaves `label` as whatever arrived."),
            ],
            notes={"label = name.upper()":
                   "Build the new value first, under a name, so the last line "
                   "has something to hand back.",
                   "return \"user \" + label":
                   "The space is already inside the quotes."},
            family="first_steps_functions",
            nudge="Two lines anchor it: the `def` at the top and the `return` "
                  "at the bottom. Only one line can possibly go between them.",
            pseudocode="def describe(name):\n"
                       "    label = the upper-case version of name\n"
                       "    return \"user \" joined to label",
            failures=["Returning before the value exists",
                      "Leaving the body at the left margin, where it is no "
                      "longer part of the function"],
        ),

        _assemble(
            "fs-assemble-receipt", "Four Lines, One Order",
            """
            Same puzzle, one line longer, and this time the middle two lines
            genuinely depend on each other only by name rather than by order —
            which means you have to think about what the last line needs rather
            than pattern-matching the shape.

            `receipt("coffee", 3)` gives `'coffee: 3'`. Remember that `+` will
            not join a number onto text, which is why `str` is in there.
            """,
            "receipt", "item, price", _ref_receipt,
            """
            def receipt(item, price):
                line = item + ": "
                amount = str(price)
                return line + amount
            """,
            [("coffee", ["coffee", 3]), ("free", ["tea", 0])],
            [("expensive", ["rig", 1250]), ("a refund", ["refund", -5])],
            edges=[("empty item", ["", 7])],
            distractors=[
                ("return line", 1,
                 "Half an answer. The price never leaves the function."),
                ("amount = price", 1,
                 "Without `str`, the last line tries to join a number onto "
                 "text and raises TypeError."),
            ],
            notes={"amount = str(price)":
                   "The conversion has to happen before the join, not during "
                   "it.",
                   "return line + amount":
                   "Both sides are text by now, so `+` joins them."},
            family="first_steps_functions",
            nudge="Work backwards from the last line: it uses two names, and "
                  "both of them have to exist by the time it runs.",
            pseudocode="def receipt(item, price):\n"
                       "    line = item joined to \": \"\n"
                       "    amount = the text version of price\n"
                       "    return line joined to amount",
            failures=["Ordering the body so that `return` runs before one of "
                      "the names it needs exists",
                      "Indenting the `def` line, which puts the whole function "
                      "inside nothing"],
        ),

        _flaw(
            "fs-flaw-print-not-return", "One of These Hands Nothing Back",
            """
            Two versions of the same function, three lines each, identical
            except for one line. One of them is correct and the other is the
            single most common mistake of anyone's first week.

            They look equally plausible. Run them and one writes its answer on
            the screen and hands back `None`; the other says nothing and hands
            back the answer.

            **Which line of the cursed version is wrong?**
            """,
            """
            def label(count):
                text = str(count)
                return "n=" + text
            """,
            """
            def label(count):
                text = str(count)
                print("n=" + text)
            """,
            3,
            "Line 3 builds exactly the right text and then throws it at the "
            "screen instead of handing it back. The function ends without a "
            "`return`, so what reaches the caller is `None`. The output looks "
            "correct to a human watching the terminal, which is precisely what "
            "makes this one hard to see.",
            [[5], [0], [-2]],
            family="first_steps_functions",
            nudge="Both versions do the same work. Ask which one lets the "
                  "result leave the function.",
        ),
    ]


# ===========================================================================
# CONCEPT 9
# A condition, then a loop, then a list. In that order, because a loop with a
# condition in it is two new ideas and this family never spends two at once.
# ===========================================================================

def _ref_access(role):
    return "granted" if role in ("admin",) else "denied"


def _ref_band(score):
    for edge, name in ((90, "high"), (50, "middle")):
        if score >= edge:
            return name
    return "low"


def _ref_total_length(words):
    return len("".join(words))


def _ref_with_extra(items, value):
    return list(items) + [value]


def _ref_count_long(words, least):
    return len([w for w in words if not len(w) < least])


def _conditions() -> list:
    return [
        _trace(
            "fs-compare-trace", "Asking a Question in Code",
            """
            `==` was the first comparison you met. There are five more:
            `!=` (different), `>`, `<`, `>=` and `<=`. Every one of them
            produces `True` or `False` and nothing else, and the result is an
            ordinary value — you can store it under a name like any other.

            **After line 3, what does `over` hold? And after line 4, `same`?**
            """,
            """
            limit = 10
            used = 12
            over = used > limit
            same = used == limit
            """,
            [(3, "over", "True", "Is 12 greater than 10?"),
             (4, "same", "False", "Is 12 the same number as 10?")],
            family="first_steps_conditions",
            nudge="Read line 3 out loud as a question, then answer the "
                  "question. The answer is the value.",
            walkthrough="`used > limit` asks whether 12 is greater than 10. It "
                        "is, so `over` becomes `True`. `used == limit` asks "
                        "whether they are the same number. They are not, so "
                        "`same` becomes `False`. Note that neither line changed "
                        "`used` or `limit`: comparing reads, it never writes.",
            misreads=["'True'", "12"],
        ),

        _read(
            "fs-if-else-read", "The Other Branch",
            """
            `else:` supplies the block to run when the `if` condition is false.
            Both blocks are indented under their own colon line, exactly one of
            the two runs, and execution carries on below afterwards either way.

            There is no version of this where both run, and no version where
            neither does.

            **What appears on the screen?**
            """,
            """
            temperature = 3
            if temperature > 20:
                print("warm")
            else:
                print("cold")
            print("done")
            """,
            ['`cold`, then `done`', '`warm`, then `done`', 'only `cold`',
             '`warm`, `cold`, then `done`'], 0,
            "`3 > 20` is `False`, so the `if` block is skipped and the `else` "
            "block runs, writing `cold`. Line 6 is at the left margin, outside "
            "both blocks, so it runs next whichever branch was taken.",
            family="first_steps_conditions",
            nudge="Work out the condition first. It decides which of the two "
                  "indented blocks you are even reading.",
            method="One branch runs, then the code below the whole `if` runs.",
        ),

        _fill(
            "fs-if-blank", "A Condition Is Just a Value",
            """
            What sits between `if` and the colon is an ordinary expression that
            produces `True` or `False` — the same kind of expression you traced
            two problems ago. Python works it out, then decides.

            This function has no `else`. It does not need one: the `return`
            inside the `if` ends the function, so the last line is reached only
            when the condition was false.

            Return `"granted"` when `role` is exactly `"admin"`, and `"denied"`
            otherwise.
            """,
            "access", "role", _ref_access,
            """
            def access(role):
                if role == "admin":
                    return "granted"
                return "denied"
            """,
            [("the admin", ["admin"]), ("a guest", ["guest"])],
            [("wrong case", ["Admin"]), ("nobody", [""])],
            edges=[("nearly", ["admins"])],
            blanks=[("role == \"admin\"",
                     "the question: is this role the admin?")],
            family="first_steps_conditions",
            nudge="One `=` would try to give `role` a new value, which is not a "
                  "question and Python will not accept it here. You want the "
                  "one that asks.",
            pseudocode="if role is the same text as \"admin\":\n"
                       "    return \"granted\"\n"
                       "return \"denied\"",
            failures=["Writing `role = \"admin\"`, which is an assignment and a "
                      "SyntaxError in this position",
                      "Comparing against `Admin` or `ADMIN` — the comparison is "
                      "character by character and capitals count"],
        ),

        _fill(
            "fs-elif-blank", "The First Test That Matches Wins",
            """
            Tests are read top to bottom and the first one that succeeds ends
            the function. That is why the second test below can be as loose as
            it looks: anything at 90 or above already left on line 3, so by the
            time line 4 runs, the score is known to be under 90 and does not
            need saying again.

            A score of 50 or more, but under 90, is `"middle"`.
            """,
            "band", "score", _ref_band,
            """
            def band(score):
                if score >= 90:
                    return "high"
                if score >= 50:
                    return "middle"
                return "low"
            """,
            [("top", [95]), ("middle", [60])],
            [("bottom", [10]), ("exactly fifty", [50])],
            edges=[("exactly ninety", [90]), ("negative", [-5])],
            blanks=[("score >= 50", "the test for the middle band")],
            family="first_steps_conditions",
            nudge="`>=` is at least. Resist the urge to also write \"and under "
                  "90\" — line 3 has already taken those away.",
            pseudocode="if score is at least 90: return \"high\"\n"
                       "if score is at least 50: return \"middle\"\n"
                       "return \"low\"",
            failures=["Using `>` where `>=` is meant, which gets 50 wrong and "
                      "nothing else",
                      "Restating the upper bound, which is harmless here and "
                      "becomes wrong the moment the order changes"],
        ),

        _flaw(
            "fs-flaw-first-match", "Both Doors Lead the Same Way",
            """
            Two versions of a banding function, six lines each, identical except
            for one. The cursed one still returns `"high"` for a top score and
            still returns `"low"` for a bad one, which is most of a test suite
            passing.

            One whole band of scores comes out wrong, and it is the band in the
            middle.

            **Which line of the cursed version is wrong?**
            """,
            """
            def rank(score):
                if score >= 90:
                    return "high"
                if score >= 50:
                    return "middle"
                return "low"
            """,
            """
            def rank(score):
                if score >= 50:
                    return "high"
                if score >= 50:
                    return "middle"
                return "low"
            """,
            2,
            "With line 2 reading `>= 50`, every score from 50 upward matches "
            "the first test and returns `\"high\"`. Line 4 is still there, still "
            "correct, and can never be reached — the first matching test always "
            "wins, so a test that is too generous silently swallows everything "
            "below it.",
            [[60], [95], [10]],
            family="first_steps_conditions",
            nudge="Pick a score of 60 and walk it down both versions, line by "
                  "line. Notice which lines you never arrive at.",
        ),

        # -- a loop -----------------------------------------------------------
        _read(
            "fs-loop-read", "Once Per Item",
            """
            `for name in thing:` runs its indented block once for every item in
            `thing`, with `name` referring to a different item each time round.
            The block is indented under the colon, the same as an `if` block,
            and the line after it at the left margin runs once, at the end.

            **What appears on the screen?**
            """,
            """
            for animal in ["cat", "dog"]:
                print(animal)
            print("done")
            """,
            ['`cat`, `dog`, then `done`', '`animal`, twice, then `done`',
             '`cat`, `dog`, `done`, `cat`, `dog`, `done`',
             '`["cat", "dog"]`, then `done`'], 0,
            "The block runs twice. The first time `animal` refers to `\"cat\"`, "
            "the second time to `\"dog\"`. Then the loop is finished and line 3, "
            "which is outside it, runs once.",
            family="first_steps_loops",
            nudge="Two items means two trips through the indented line. The "
                  "unindented line is not part of the trip.",
            method="Write down what the loop name refers to on each pass, then "
                   "what the block does with it.",
            pattern="SIMULATION",
        ),

        _read(
            "fs-range-read", "Counting From Zero",
            """
            `range(n)` produces n numbers, starting at `0` and stopping
            *before* `n`. So `range(3)` gives `0`, `1`, `2` — three numbers,
            none of them 3.

            This is not a quirk to memorise so much as a convention that runs
            through the whole language: a list of three items has positions 0, 1
            and 2 for the same reason.

            **What appears on the screen?**
            """,
            """
            for i in range(3):
                print(i)
            """,
            ['`0`, `1`, `2`', '`1`, `2`, `3`', '`0`, `1`, `2`, `3`', '`3`'], 0,
            "Three numbers, starting at zero, stopping before three. Count the "
            "values rather than reading the `3` as a destination: `range(3)` "
            "says how many, not how far.",
            family="first_steps_loops",
            nudge="How many numbers, and what is the first one?",
            method="`range(n)` starts at 0 and stops before n. Always n values.",
        ),

        _trace(
            "fs-loop-trace", "A Total That Survives the Loop",
            """
            The commonest use of a loop is to build one value out of many. The
            shape is always the same three parts: a name set to a starting value
            **before** the loop, updated **inside** it, and read **after** it.

            Getting the first part inside the loop resets it every pass; getting
            the third part inside means reading it too early. The indentation is
            what says which is which.

            **Trace all four lines. After line 4, what do `total` and `answer`
            hold?**
            """,
            """
            total = 0
            for n in [4, 5, 6]:
                total = total + n
            answer = total * 10
            """,
            [(4, "total", "15", "Three passes: 0+4, then +5, then +6."),
             (4, "answer", "150", "Read once, after the loop has finished.")],
            family="first_steps_loops",
            nudge="Write the value of `total` after each pass. Three passes, "
                  "three rows.",
            walkthrough="`total` starts at `0`. The block runs three times: "
                        "`total` becomes 4, then 9, then 15. The loop is then "
                        "finished, and line 4 — at the left margin, so outside "
                        "the loop — multiplies the final total by ten and binds "
                        "`answer` to `150`.",
            misreads=["6", "60", "456"],
            pattern="SIMULATION",
        ),

        _fill(
            "fs-loop-blank", "Writing the Accumulator",
            """
            The same three-part shape, now yours to complete. `running` starts
            at zero, the loop visits each word in turn, and the line after the
            loop hands the finished total back.

            The only missing piece is what happens on each pass: `running` has
            to become itself plus the length of the current word.
            """,
            "total_length", "words", _ref_total_length,
            """
            def total_length(words):
                running = 0
                for word in words:
                    running = running + len(word)
                return running
            """,
            [("two words", [["ab", "cde"]]), ("one word", [["x"]])],
            [("several", [["a", "bb", "ccc", "dddd"]]),
             ("empty strings", [["", "", ""]])],
            edges=[("no words at all", [[]])],
            blanks=[("running + len(word)",
                     "the running total, plus this word's length")],
            family="first_steps_loops",
            nudge="The right side is worked out first, using the value "
                  "`running` has right now. That is the same rule as "
                  "`hits = hits + 1`.",
            pseudocode="running = 0\n"
                       "for each word:\n"
                       "    running = running + the length of that word\n"
                       "return running",
            failures=["Writing `len(word)` alone, which forgets every earlier "
                      "word and leaves the length of the last one",
                      "Returning inside the loop, which answers after one word"],
            pattern="SIMULATION", time="O(n)",
        ),

        _flaw(
            "fs-flaw-return-indent", "Depth Is Meaning",
            """
            Two versions of a summing function, five lines each. Every line is
            identical except one, and the difference on that line is four
            spaces — no word changed, no operator changed, nothing you would
            catch by reading for sense.

            The cursed version returns a number, confidently, on every input. It
            is the right number only when the list has exactly one item in it.

            **Which line of the cursed version is wrong?**
            """,
            """
            def total(values):
                running = 0
                for value in values:
                    running = running + value
                return running
            """,
            """
            def total(values):
                running = 0
                for value in values:
                    running = running + value
                    return running
            """,
            5,
            "In the cursed version line 5 is indented into the loop body, so it "
            "runs at the end of the first pass — and `return` ends the whole "
            "function, not just the pass. The loop never reaches a second item. "
            "Four spaces is the entire difference between summing a list and "
            "reading its first element.",
            [[[1, 2, 3]], [[5, 5]], [[7]]],
            family="first_steps_loops",
            nudge="Read the two versions for shape, not for words. Ask which "
                  "lines are inside the `for` in each one.",
            pattern="SIMULATION",
        ),

        # -- a list ------------------------------------------------------------
        _read(
            "fs-list-read", "Several Values Under One Name",
            """
            Square brackets build a **list**: several values, in order, under a
            single name. `ports[0]` is the first item, because positions are
            counted from zero — the same convention `range` follows. `len`
            counts the items, exactly as it counted characters in text.

                colours = ["red", "green"]

            `colours[0]` is `'red'` and `len(colours)` is `2`.

            **What appears on the screen?**
            """,
            """
            ports = [22, 80, 443]
            print(ports[0])
            print(len(ports))
            """,
            ['`22`, then `3`', '`80`, then `3`', '`22`, then `2`',
             '`[22, 80, 443]`, then `3`'], 0,
            "Position 0 is the first item, `22`. `len` reports how many items "
            "there are, which is `3` — the count and the last position are "
            "deliberately different numbers, and that gap is where beginners' "
            "off-by-one errors live.",
            family="first_steps_lists",
            nudge="Count the positions starting at zero, then count the items "
                  "starting at one.",
            method="`[0]` is the first item. `len` is how many there are.",
            pattern="ARRAY",
        ),

        _read(
            "fs-list-index-read", "The Last One",
            """
            Three items occupy positions 0, 1 and 2, so the last position is
            always one less than the length. Writing `ports[len(ports) - 1]`
            works and is tedious, so Python offers a shorthand: a negative
            position counts back from the end, and `-1` is the last item.

            **What appears on the screen?**
            """,
            """
            ports = [22, 80, 443]
            print(ports[2])
            print(ports[-1])
            """,
            ['`443`, then `443`', '`443`, then `22`', '`80`, then `443`',
             'IndexError: list index out of range'], 0,
            "There are three items, so the last one sits at position 2, and "
            "`-1` means that same item counted from the other end. Both lines "
            "print `443`. Position 3 would be one past the end and would raise "
            "IndexError, which you will meet by name shortly.",
            family="first_steps_lists",
            nudge="Write the three positions above the three values before "
                  "answering either line.",
            method="Last position is `len - 1`. `-1` is the same thing, said "
                   "shorter.",
            pattern="ARRAY",
        ),

        _state(
            "fs-list-state", "Lists Are Changed In Place",
            """
            Text is never modified — `user.upper()` built a new value and left
            the original alone. Lists are the opposite: `.append(value)` adds an
            item to the end of the list it is called on, and changes that list
            where it stands. Nothing is handed back to assign.

            `.pop()` is the other half: it removes the **last** item and hands
            that item back.

            The operations below are applied to `queue` in order.

            **What does `queue` hold when they finish? Write it as a list,
            including the brackets and the quotes.**
            """,
            'queue = ["a", "b"]',
            """
            queue.append("c")
            queue.append("d")
            queue.pop()
            """,
            "queue", "['a', 'b', 'c']",
            "Two appends put `\"c\"` and then `\"d\"` on the end, leaving four "
            "items. `.pop()` removes the last one, which is `\"d\"`, and hands "
            "it back — nothing here catches it, so it is discarded. Three items "
            "are left, in their original order.",
            family="first_steps_lists",
            nudge="Write the list out after each of the three operations. "
                  "Append adds at the end; pop removes from the end.",
            misreads=["['a', 'b', 'c', 'd']", "['b', 'c', 'd']"],
            pattern="ARRAY",
        ),

        _fill(
            "fs-list-append-blank", "A Copy, On Purpose",
            """
            Because `.append` changes the list it is given, a function that
            appends to its argument quietly edits the caller's list. Usually
            that is not what anyone wanted, and it is a genuinely difficult bug
            to find later.

            `list(items)` builds a fresh list with the same contents, so the
            append lands on the copy. Two pieces are missing: the copy, and the
            append itself.
            """,
            "with_extra", "items, value", _ref_with_extra,
            """
            def with_extra(items, value):
                out = list(items)
                out.append(value)
                return out
            """,
            [("numbers", [[1, 2], 3]), ("from empty", [[], 9])],
            [("text", [["a"], "b"]), ("a duplicate", [[5], 5])],
            edges=[("lists inside lists", [[[1]], [2]])],
            blanks=[("list(items)", "a fresh list holding the same items"),
                    ("out.append(value)", "put the new value on the end of it")],
            family="first_steps_lists",
            nudge="`out = items` would be two names for one list, which is the "
                  "bug this problem exists to avoid. You want a second list.",
            pseudocode="out = a copy of items\n"
                       "append value to out\n"
                       "return out",
            failures=["Writing `out = items`, which appends to the caller's "
                      "list as well as the returned one",
                      "Writing `out = out.append(value)`, which binds `out` to "
                      "`None` — append changes the list and returns nothing"],
            pattern="ARRAY", time="O(n)", space="O(n)",
        ),

        _fill(
            "fs-list-loop-blank", "All Three At Once",
            """
            A list, a loop over it, and a condition inside the loop. Nothing
            here is new; this is the first problem that asks for all three in
            one place.

            `found` counts. The loop visits every word. The `if` decides which
            words are worth counting — those whose length is at least `least`.
            """,
            "count_long", "words, least", _ref_count_long,
            """
            def count_long(words, least):
                found = 0
                for word in words:
                    if len(word) >= least:
                        found = found + 1
                return found
            """,
            [("mixed lengths", [["a", "abc", "abcd"], 3]),
             ("none long enough", [["a", "b"], 5])],
            [("all of them", [["abc", "abcd"], 2]),
             ("threshold of zero", [["", "a"], 0])],
            edges=[("no words", [[], 2]), ("empty strings", [["", ""], 1])],
            blanks=[("len(word) >= least",
                     "the test: is this word long enough?")],
            family="first_steps_lists",
            nudge="`word` is the word this pass is about. You need its length, "
                  "compared against `least`, with at-least rather than "
                  "strictly-greater.",
            pseudocode="found = 0\n"
                       "for each word:\n"
                       "    if that word is at least `least` characters:\n"
                       "        found = found + 1\n"
                       "return found",
            failures=["Comparing `word >= least`, which compares text against a "
                      "number and raises TypeError",
                      "Using `>` and losing every word of exactly the right "
                      "length"],
            pattern="ARRAY", time="O(n)",
        ),
    ]


# ===========================================================================
# CONCEPT 10, and the hand-over
# Errors are met on purpose rather than met by accident, and then the
# scaffolding comes off: five TUTORIAL problems with an empty body and a
# comment per line of code owed.
# ===========================================================================

def _ref_summary(name, count):
    return "%s: %s" % (name, count)


def _ref_banner(text):
    edge = "*" * len(text)
    return " ".join([edge, text, edge])


def _ref_positive_total(numbers):
    return sum(v for v in numbers if v > 0)


def _ref_longest(words):
    for word in sorted(words, key=lambda w: -len(w))[:1]:
        return word
    return ""


def _ref_initials(first, last):
    return "".join([first[:1], last[:1]])


def _errors() -> list:
    return [
        _read(
            "fs-nameerror", "A Name Python Has Never Heard Of",
            """
            When Python meets a name it looks up what that name refers to. If
            nothing ever bound it, there is nothing to look up, and it stops
            with a **NameError** naming the exact word it could not find.

            Nearly always this is one of two things: a typo, or a line that was
            supposed to create the name and did not run. Read the quoted word
            character by character before assuming anything clever.

            **What happens when this runs?**
            """,
            """
            attempts = 3
            print(attemps)
            """,
            ["NameError: name 'attemps' is not defined", "`3`",
             "nothing — `attemps` is empty",
             "SyntaxError: invalid syntax"], 0,
            "Line 1 created `attempts`. Line 2 asks for `attemps`, which has a "
            "letter missing and is therefore a completely different name as far "
            "as Python is concerned. It has no way to guess what you meant, so "
            "it says which word defeated it and stops.",
            family="first_steps_errors",
            nudge="Compare the name on line 1 with the name on line 2, letter "
                  "by letter.",
            method="NameError means: this word was never given a value. Check "
                   "the spelling first, then check whether the line that "
                   "defines it actually ran.",
        ),

        _read(
            "fs-indexerror", "One Past the End",
            """
            Three items sit at positions 0, 1 and 2. There is no position 3, and
            asking for one is an **IndexError: list index out of range**.

            This is the off-by-one error made visible. It is the same gap you
            saw between `len(ports)` being `3` and the last position being `2`,
            and it is worth being able to recognise on sight.

            **What happens when this runs?**
            """,
            """
            ports = [22, 80, 443]
            print(ports[3])
            """,
            ["`443`", "IndexError: list index out of range", "`None`",
             "`0`"], 1,
            "The three items are at 0, 1 and 2. Position 3 is one past the end, "
            "so Python stops rather than inventing a value. The last item is at "
            "`len(ports) - 1`, or more readably at `-1`.",
            family="first_steps_errors",
            nudge="Write the position above each of the three values, starting "
                  "at zero. Then look for position 3.",
            method="Valid positions run from 0 to len - 1. Anything else is an "
                   "IndexError.",
            pattern="ARRAY",
        ),

        _read(
            "fs-error-stops-everything", "An Error Ends the Program",
            """
            An error is not a warning that gets logged while the program carries
            on. Unless something is written to catch it, it stops execution at
            that line. Everything above it has already happened; nothing below
            it happens at all.

            That is useful information when you are reading output: whatever you
            can see on the screen is a record of how far it got.

            **What appears on the screen?**
            """,
            """
            print("start")
            print(1 / 0)
            print("end")
            """,
            ['`start`, then a ZeroDivisionError; `end` never appears',
             '`start`, then `end`',
             'only the ZeroDivisionError',
             '`start`, `end`, then the ZeroDivisionError'], 0,
            "Line 1 runs and writes `start`. Line 2 tries to divide by zero, "
            "which has no answer, so Python raises ZeroDivisionError and stops "
            "there. Line 3 is never reached. The output you can see tells you "
            "the failure happened after line 1 and before line 3.",
            family="first_steps_errors",
            nudge="Read downward and stop where Python stops. What had already "
                  "been written by then?",
            method="Output before the error is real. Everything after the "
                   "failing line never ran.",
        ),

        _read(
            "fs-traceback-shape", "Reading a Traceback on Purpose",
            """
            A traceback looks like a wall of text and is actually a short, fixed
            form. Read it **bottom up**.

            The last line is what went wrong, by name, with a description. The
            lines above it are where — file, line number, and the line itself —
            innermost last. Nothing in between is an accusation; it is a route.

            **What is the traceback below telling you?**
            """,
            """
            1  def area(width, height):
            2      return width * height
            3
            4  print(area(3))

            Traceback (most recent call last):
              File "scan.py", line 4, in <module>
                print(area(3))
            TypeError: area() missing 1 required positional argument: 'height'
            """,
            ["Line 4 called `area` with one value when the function needs two",
             "Line 2 multiplied two things that cannot be multiplied",
             "`height` is spelled wrong inside the function body",
             "The file `scan.py` could not be found"], 0,
            "The bottom line names the failure: an argument is missing, and it "
            "says which one — `height`. The line above points at the call site, "
            "line 4, and shows it. The function itself is fine; the call handed "
            "it one value where the `def` line asks for two. Bottom line for "
            "what, line above for where.",
            family="first_steps_errors",
            nudge="Start at the last line and work upward. Only two of those "
                  "lines carry information you need.",
            method="Last line: what went wrong. Line above: where. Read them in "
                   "that order and ignore the rest until you need it.",
            seconds=90,
        ),

        _fix(
            "fs-fix-the-error", "Fix the One That Raises",
            """
            The function below is three-quarters right, and the quarter that is
            wrong is the TypeError you met early on: `+` will not join a number
            onto text.

            Run it first. The failing test will show you the message, and the
            message names both types it was asked to combine. The fix is one
            call, in one place — you have used it before.

            `summary("errors", 2)` should give `'errors: 2'`.
            """,
            "summary", "name, count", _ref_summary,
            """
            def summary(name, count):
                return name + ": " + count
            """,
            """
            def summary(name, count):
                return name + ": " + str(count)
            """,
            [("two errors", ["errors", 2]), ("none", ["warnings", 0])],
            [("a negative delta", ["delta", -1]), ("a large count", ["hits", 4096])],
            nudge="`count` arrives as a number. The two things either side of "
                  "it are text. One of the three has to change kind, and it is "
                  "not the text.",
            failures=["Putting quotes around `count`, which returns the literal "
                      "word rather than the value",
                      "Converting `name` instead, which was already text and "
                      "changes nothing"],
        ),
    ]


def _handover() -> list:
    return [
        _write(
            "fs-write-banner", "Nothing Left Blank",
            """
            No blanks from here. The body is empty and the comments say what
            each line has to do — one comment, one line of code. Write the first
            line, run it, then write the second.

            `banner("hi")` gives `'** hi **'`: a row of stars as long as the
            text, then the text, then the same row again, single spaces between.

            Every piece of this is something you have already used: `*` on text,
            `len`, `+`, and `return`.
            """,
            "banner", "text", _ref_banner,
            """
            def banner(text):
                edge = "*" * len(text)
                return edge + " " + text + " " + edge
            """,
            [("two letters", ["hi"]), ("one letter", ["x"])],
            [("a word", ["root"]), ("with a space", ["a b"])],
            edges=[("empty text", [""])],
            starter="""
            def banner(text):
                # 1. build `edge`: a star for every character in `text`
                # 2. return edge, a space, the text, a space, and edge again
                pass
            """,
            family="first_steps_handover",
            nudge="Build the edge once and use the name twice. Writing the "
                  "repetition out twice works and is how you get two "
                  "different-length edges by accident later.",
            pseudocode="edge = \"*\" repeated len(text) times\n"
                       "return edge + \" \" + text + \" \" + edge",
            failures=["Counting the spaces into the edge length",
                      "Printing the banner instead of returning it"],
            pattern="STRING", time="O(n)",
        ),

        _write(
            "fs-write-positive-total", "A Loop With a Condition In It",
            """
            Add up only the numbers greater than zero, and return the total.
            Negatives and zero are skipped. `positive_total([3, -1, 4])` gives
            `7`, and an empty list gives `0`.

            This is the accumulator shape with an `if` inside it. The three
            parts still hold: start before the loop, update inside, return
            after. The indentation is what says which line is which.
            """,
            "positive_total", "numbers", _ref_positive_total,
            """
            def positive_total(numbers):
                running = 0
                for number in numbers:
                    if number > 0:
                        running = running + number
                return running
            """,
            [("mixed signs", [[3, -1, 4]]), ("all positive", [[1, 2]])],
            [("all negative", [[-5, -2]]), ("zeroes", [[0, 0, 7]])],
            edges=[("nothing at all", [[]])],
            starter="""
            def positive_total(numbers):
                # 1. start a running total at zero
                # 2. visit each number in turn
                # 3. if this number is greater than zero, add it to the total
                # 4. after the loop, return the total
                pass
            """,
            family="first_steps_handover",
            nudge="Four lines, at three different depths. Decide the depth of "
                  "each line before you type it.",
            pseudocode="running = 0\n"
                       "for number in numbers:\n"
                       "    if number > 0:\n"
                       "        running = running + number\n"
                       "return running",
            failures=["Returning inside the loop, which answers after the first "
                      "number",
                      "Starting the total inside the loop, which throws away "
                      "everything counted so far on every pass"],
            pattern="SIMULATION", time="O(n)",
        ),

        _write(
            "fs-write-longest", "Keeping the Best One So Far",
            """
            Return the longest word in the list. If two are equally long, return
            the one that appeared first. An empty list has no words in it, so
            return the empty text `""`.

            Same shape again, with one change worth noticing: what is being kept
            is not a running total but the best candidate so far. `best` starts
            as `""`, which is length zero, so the first real word always beats
            it.
            """,
            "longest", "words", _ref_longest,
            """
            def longest(words):
                best = ""
                for word in words:
                    if len(word) > len(best):
                        best = word
                return best
            """,
            [("clear winner", [["a", "abcd", "ab"]]),
             ("single word", [["only"]])],
            [("tie goes to the first", [["ab", "cd"]]),
             ("longest last", [["a", "bb", "ccc"]])],
            edges=[("no words", [[]]), ("empty strings", [["", ""]])],
            starter="""
            def longest(words):
                # 1. start `best` as the empty text ""
                # 2. visit each word in turn
                # 3. if this word is longer than `best`, make it the new best
                # 4. after the loop, return `best`
                pass
            """,
            family="first_steps_handover",
            nudge="Compare lengths, not words: `word > best` compares them "
                  "alphabetically, which is a different question.",
            pseudocode="best = \"\"\n"
                       "for word in words:\n"
                       "    if len(word) > len(best):\n"
                       "        best = word\n"
                       "return best",
            failures=["Using `>=`, which hands ties to the last word rather "
                      "than the first",
                      "Comparing the words themselves instead of their lengths"],
            pattern="ARRAY", time="O(n)",
        ),

        _write(
            "fs-write-initials", "One Character Out of a Word",
            """
            One genuinely new thing, and it is small: text is indexed the same
            way a list is. `"root"[0]` is `'r'` — the first character, counted
            from zero, exactly as `ports[0]` was the first item.

            Return the two initials joined together: `initials("ada",
            "lovelace")` gives `'al'`. Both names are guaranteed to have at
            least one character.
            """,
            "initials", "first, last", _ref_initials,
            """
            def initials(first, last):
                start = first[0]
                end = last[0]
                return start + end
            """,
            [("two names", ["ada", "lovelace"]),
             ("single letters", ["x", "y"])],
            [("capitals", ["Root", "Shell"]), ("digits", ["7up", "9lives"])],
            edges=[("the same name twice", ["sam", "sam"])],
            starter="""
            def initials(first, last):
                # 1. `start` is the character at position 0 of `first`
                # 2. `end` is the character at position 0 of `last`
                # 3. return the two of them joined
                pass
            """,
            family="first_steps_handover",
            nudge="Position 0, not position 1. The same counting as everywhere "
                  "else.",
            pseudocode="start = first[0]\nend = last[0]\nreturn start + end",
            failures=["Using position 1, which returns the second character of "
                      "each name",
                      "Returning `[start, end]`, a list of two characters, "
                      "where two joined characters were asked for"],
            pattern="STRING", time="O(1)",
        ),
    ]


def _fix(pid, title, statement, fn, params, ref, broken, canonical, visible,
         hidden, *, family="first_steps_errors", nudge, failures=(),
         pattern="LANGUAGE", tier="TUTORIAL", bug="type-mismatch",
         armor="boots", time="O(1)", space="O(1)"):
    """A DEBUG_BATTLE: the starter code is the broken version, and it really is
    broken — `validate._run_broken` runs it and rejects the problem if it
    passes. Reading an error message is the skill, so the encounter hands the
    player a program that produces one."""
    problem = debug_problem(
        id=pid, title=title, difficulty=tier, statement=statement,
        fn_name=fn, params=params, broken=broken, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden,
        bug_type=bug, armor_piece=armor, nudge=nudge, failures=list(failures),
        pattern=pattern, realm=REALM, family=family,
        time_complexity=time, space_complexity=space)
    problem.profile_weight = dict(Q)
    problem.visualization = dict(VIZ)
    problem.tags = ["first-steps", "debug", family] + list(problem.tags)
    return _patch_oracle(problem)


def build() -> list:
    """Every first-steps problem, in teaching order.

    `prerequisites` are wired here rather than typed per problem: the order is
    the whole design of this family and threading it by hand is exactly the sort
    of bookkeeping that drifts. Chaining them means the sequence survives
    leaving this file — anything reading the corpus can reconstruct it.
    """
    del _AUDIT[:]
    problems = _values() + _functions() + _conditions() + _errors() + _handover()
    if _AUDIT:
        raise AssertionError("first_steps disagrees with Python: "
                             + "; ".join(_AUDIT))
    for previous, current in zip(problems, problems[1:]):
        current.prerequisites = [previous.id]
    # Declare the chain as BINDING, not merely suggested. `prerequisites` is
    # used for both meanings across this corpus — parsons and reasoning thread
    # an `after=` that is a pleasant order, onboarding and oop_language point at
    # the full-dress version of an idea — and a selector cannot tell those apart
    # from a chain where the next rung is genuinely unreadable without the last
    # one. So the content says which it is rather than the engine guessing, the
    # same way `lineage:` tags declare what the lineage grouper may not infer.
    # adaptive.gating_prerequisites honours an edge only on a problem carrying
    # this tag; without it, holding every authored chain to a strict order took
    # parsons and reasoning down with it and flattened sixty encounters into a
    # run of seven code battles.
    for problem in problems:
        problem.tags = list(problem.tags) + [ORDER_TAG]
    return problems
