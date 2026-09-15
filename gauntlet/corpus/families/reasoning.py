"""Reasoning encounters: the ones you win by reading, not by typing.

Three puzzle kinds live here, and not one of them starts from a blank screen:

  TRACE          the spell is already written. Say what a variable holds the
                 moment a marked line finishes. This is the habit that finds
                 bugs — running code in your head instead of hoping.
  SPOT_THE_FLAW  two near-identical spells; one is cursed on exactly one line.
                 Every curse in this file is a defect that ships in real code:
                 an off-by-one, a comparison the wrong way round, a visited mark
                 in the wrong place, a key that was never deleted at zero.
  STATE_PREDICT  a structure and a list of operations. Say exactly what the
                 structure holds when they finish.

Every expected value here is computed by running the code at build time and
compared against the value the author wrote down. When the two disagree the
build stops with the real value in the message. A trace puzzle with a wrong
answer teaches the player to distrust correct reasoning, which is worse than
teaching nothing at all, so it is not a thing this corpus is willing to ship.

The verification is in three pieces, one per kind:

  _snapshots   traces the TRACE code line by line and records what each line
               left behind, so "after line 7" is checked against what Python
               actually did.
  _replay      executes a STATE_PREDICT operation list one statement at a time,
               which both checks the final state and writes the worked replay.
  _divergence  runs the honest and the cursed spell on real inputs and finds an
               input they disagree on. A SPOT_THE_FLAW whose curse changes
               nothing is not a puzzle, and this refuses to build one.

Difficulty is weighted gentle on purpose. The player these are for reads well
and freezes at an empty editor; this family is where he earns mastery without
ever meeting one.
"""
from __future__ import annotations

import ast
import copy
import sys

from ..schema import Problem, TARGET_SECONDS, build_hint_tree

# The player this family exists for. Same weighting as onboarding: the selector
# should reach for reading work early and often.
Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 2.0}

VIZ = {"type": "array_scan", "caption": "One line at a time. Write down what changed."}

_TRACE_FILE = "<reasoning-trace>"

# Filled by the builders below and raised as one report at the end of build(),
# so a single run names every disagreement rather than only the first.
_AUDIT: list = []


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _code(text: str) -> str:
    """Dedent a snippet and drop the trailing newline: the front end numbers
    `code.split('\\n')`, and a trailing newline would add a phantom last line."""
    import textwrap
    return textwrap.dedent(text).strip("\n")


def _numbered(code: str) -> str:
    return "\n".join("%2d  %s" % (i + 1, line)
                     for i, line in enumerate(code.split("\n")))


def _block(text: str, lang: str = "") -> str:
    return "```" + lang + "\n" + text.rstrip() + "\n```"


def _same(given: str, expected: str) -> bool:
    """Same value, not necessarily the same text. Set and dict reprs order
    themselves by hash, which is not stable across runs for strings."""
    if given == expected:
        return True
    try:
        return ast.literal_eval(given) == ast.literal_eval(expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Build-time execution: three ways of asking Python what really happens
# ---------------------------------------------------------------------------

def _snapshots(code: str) -> dict:
    """Run `code` and record, per line, the variables it left behind each visit.

    Consecutive line events collapse into a single visit. A comprehension fires
    its own line repeatedly without the player ever seeing two statements, while
    a loop body line only comes back around after other lines have run. That
    distinction is exactly what makes "after line 7" one unambiguous moment.
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
    """Every checkpoint must name a line that runs exactly once — otherwise the
    question has more than one honest answer — and must match the real value."""
    if sys.gettrace() is not None:
        return                      # a debugger or coverage tool owns the hook
    visits = _snapshots(code)
    for line, variable, expected, _hint in marks:
        seen = visits.get(line, [])
        if len(seen) != 1:
            _AUDIT.append(f"{pid}: line {line} runs {len(seen)} times; a "
                          f"checkpoint there is ambiguous")
            continue
        if variable not in seen[0]:
            _AUDIT.append(f"{pid}: {variable!r} does not exist after line {line}")
            continue
        actual = repr(seen[0][variable])
        if not _same(expected, actual):
            _AUDIT.append(f"{pid}: after line {line}, {variable} is {actual}, "
                          f"not {expected}")


def _replay(code: str, operations: str, probe: str):
    """Execute the operations one top-level statement at a time, reporting the
    structure before anything happens and after each statement. This checks the
    answer, writes the worked replay and supplies the near-misses, so none of
    the three can drift away from the other two."""
    namespace: dict = {}
    exec(compile(code, "<reasoning-state>", "exec"), namespace)
    start = repr(eval(probe, namespace))
    source = operations.split("\n")
    steps = []
    for node in ast.parse(operations).body:
        text = "\n".join(source[node.lineno - 1:node.end_lineno])
        module = ast.Module(body=[node], type_ignores=[])
        exec(compile(module, "<reasoning-state>", "exec"), namespace)
        steps.append((text, repr(eval(probe, namespace))))
    return start, steps


def _call(source: str, fn_name: str, args: list) -> str:
    ns: dict = {}
    exec(compile(source, "<reasoning-spell>", "exec"), ns)
    try:
        return repr(ns[fn_name](*copy.deepcopy(args)))
    except Exception as exc:                       # a crash is a divergence too
        return "raises " + type(exc).__name__


def _divergence(honest: str, cursed: str, fn_name: str, probes: list):
    for args in probes:
        good, bad = _call(honest, fn_name, args), _call(cursed, fn_name, args)
        if good != bad:
            return args, good, bad
    return None


def _check_flaw(pid: str, honest: str, cursed: str, line: int):
    good, bad = honest.split("\n"), cursed.split("\n")
    if len(good) != len(bad):
        _AUDIT.append(f"{pid}: the two spells have different line counts")
        return
    differing = [i + 1 for i, (a, b) in enumerate(zip(good, bad)) if a != b]
    if differing != [line]:
        _AUDIT.append(f"{pid}: the spells differ on lines {differing}, "
                      f"but the answer is line {line}")


# ---------------------------------------------------------------------------
# Problem builders
#
# TRACE and STATE_PREDICT pass their own pattern to `build_hint_tree`, so the
# Oracle rung names the shape of the code being read. SPOT_THE_FLAW passes
# DEBUGGING instead: there the code's pattern is beside the point, and "the
# algorithm is already right, one mechanical detail is wrong" is exactly the
# first useful thing to say.
# ---------------------------------------------------------------------------

def _one_answer(pid: str, question: str, correct: str, wrong: list) -> dict:
    """The single-answer form of a puzzle, carried alongside the real one.

    Same reason the complexity family carries one: anything that cannot render
    the full interface still has a question with exactly one true answer, and it
    is what the corpus validator reads. No choice here is invented — each is
    either a value this very code really produces at some point in the run, or
    the value a named classic mistake produces.
    """
    choices = [correct]
    for value in wrong:
        if _same(value, correct):
            # `4` and `4.0` are the same answer written twice. A question with
            # two true answers is worse than no question.
            if value != correct:
                _AUDIT.append(f"{pid}: near-miss {value} is the same value as "
                              f"the answer {correct}")
            continue
        if value not in choices and len(choices) < 4:
            choices.append(value)
    if len(choices) < 2:
        _AUDIT.append(f"{pid}: the single-answer form has nothing to choose from")
    # Placed deterministically from the id rather than always first, so the
    # fallback cannot be won by pattern-matching the position.
    answer = sum(ord(c) for c in pid) % len(choices)
    choices[0], choices[answer] = choices[answer], choices[0]
    return {"question": question, "choices": choices, "answer": answer}

def _puzzle(pid, title, realm, pattern, difficulty, statement, kind, spec, *,
            family, hints, secondary=(), failures=(), tags=(), after="") -> Problem:
    return Problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        problem_statement=_code(statement),
        entry={"kind": "mcq", "name": pid, "signature": ""},
        canonical_solution="", encounter_kind=kind,
        secondary_patterns=list(secondary), source_type="GENERAL_INTERVIEW",
        mcq=spec, optimal_complexity={},
        common_failures=list(failures), hint_tree=hints,
        visualization=VIZ, spaced_repetition_family=family,
        prerequisites=[after] if after else [],
        estimated_seconds=TARGET_SECONDS[difficulty],
        target_seconds=TARGET_SECONDS[difficulty],
        profile_weight=Q, tags=["puzzle", "reading"] + list(tags),
    )


def _trace(pid, title, realm, pattern, difficulty, statement, code, marks, *,
           family, nudge, walkthrough, misreads, focus=-1, secondary=(),
           failures=(), tags=(), after="") -> Problem:
    """One TRACE puzzle. `marks` is [(line, variable, expected repr, hint)].

    `misreads` are the values the classic mistakes on this trace produce, and
    `focus` picks which mark the single-answer fallback asks about — usually the
    last, which is where the insight normally lands.
    """
    code = _code(code)
    _check_trace(pid, code, marks)
    lines = code.split("\n")

    def answered(subset):
        rows, last = [], None
        for line, variable, expected, _h in subset:
            if line != last:           # several marks can share one line
                rows.append("line %-3d %s" % (line, lines[line - 1].strip()))
                last = line
            rows.append("         %s is %s" % (variable, expected))
        return "\n".join(rows)

    hints = build_hint_tree(
        pattern,
        nudge=nudge,
        visual="Draw three columns on paper: the line number, the variable that "
               "changed, and its new value. One row per line executed. Nobody "
               "traces reliably in their head, and nobody is expected to.",
        pseudocode=_block(_numbered(code)) + "\n\nThe marked lines are the only "
                   "ones you are asked about, but you cannot reach them without "
                   "filling in every row above them.",
        fragment="The first mark, given to you so you can check your method:\n\n"
                 + _block(answered(marks[:1])),
        solution=_block(answered(marks)) + "\n\n" + walkthrough.strip(),
    )
    line, variable, expected, _hint = marks[focus]
    spec = {"code": code,
            "checkpoints": [{"after_line": line, "variable": variable,
                             "expected": expected, "hint": hint}
                            for line, variable, expected, hint in marks],
            "explanation": walkthrough.strip()}
    spec.update(_one_answer(
        pid, "After line %d, what does `%s` hold?" % (line, variable),
        expected, list(misreads) + [m[2] for m in marks]))
    return _puzzle(pid, title, realm, pattern, difficulty, statement, "TRACE",
                   spec, family=family, hints=hints, secondary=secondary,
                   failures=failures, tags=list(tags) + ["trace"], after=after)


def _flaw(pid, title, realm, pattern, difficulty, statement, honest, cursed,
          line, explanation, probes, *, family, bug, nudge, secondary=(),
          failures=(), tags=(), after="") -> Problem:
    """One SPOT_THE_FLAW puzzle. The curse must be real: the two spells are run
    against `probes` and must disagree on at least one of them."""
    honest, cursed = _code(honest), _code(cursed)
    _check_flaw(pid, honest, cursed, line)
    fn_name = honest.split("(")[0].replace("def ", "").strip()
    split = _divergence(honest, cursed, fn_name, probes)
    if split is None:
        _AUDIT.append(f"{pid}: the cursed spell agrees with the honest one on "
                      f"every probe — there is no flaw to find")
        args, good, bad = probes[0], "?", "?"
    else:
        args, good, bad = split

    call = "%s(%s)" % (fn_name, ", ".join(repr(a) for a in args))
    evidence = ("On `%s` the honest spell gives `%s`. The cursed one gives `%s`."
                % (call, good, bad))
    cursed_lines, honest_lines = cursed.split("\n"), honest.split("\n")
    low, high = max(1, line - 1), min(len(cursed_lines), line + 1)

    hints = build_hint_tree(
        "DEBUGGING",
        nudge=nudge,
        visual="Read the two spells in parallel, line against matching line. "
               "Do not read for sense — read for difference. Sense is what hides "
               "a one-character curse.",
        pseudocode=evidence + "\n\nNow work backwards: which line could possibly "
                   "produce that difference and no other?",
        fragment="The curse is in lines %d to %d of the cursed spell. Three "
                 "lines, one of them lying." % (low, high),
        solution="Line %d.\n\n" % line
                 + _block("cursed:  " + cursed_lines[line - 1].strip()
                          + "\nhonest:  " + honest_lines[line - 1].strip())
                 + "\n\n" + explanation.strip() + "\n\n" + evidence,
    )
    labelled = ["line %d: %s" % (i + 1, text.strip() or "(blank)")
                for i, text in enumerate(cursed_lines)]
    spec = {"code": cursed, "reference_code": honest, "flawed_line": line,
            "explanation": explanation.strip() + " " + evidence}
    spec.update(_one_answer(pid, "Which line is cursed?", labelled[line - 1],
                            [labelled[i] for i in (line - 2, line, line + 1,
                                                   line - 3)
                             if 0 <= i < len(labelled)]))
    return _puzzle(pid, title, realm, pattern, difficulty, statement,
                   "SPOT_THE_FLAW", spec, family=family, hints=hints,
                   secondary=list(secondary) + ["DEBUGGING"], failures=failures,
                   tags=list(tags) + ["flaw", "bug:" + bug], after=after)


def _state(pid, title, realm, pattern, difficulty, statement, code, operations,
           probe, final_state, explanation, *, family, nudge, walkthrough,
           misreads=(), secondary=(), failures=(), tags=(), after="") -> Problem:
    """One STATE_PREDICT puzzle. `probe` is the expression the player is being
    asked for, evaluated at build time after every operation."""
    code, operations = _code(code), _code(operations)
    start, steps = _replay(code, operations, probe)
    if not _same(final_state, steps[-1][1]):
        _AUDIT.append(f"{pid}: the operations leave {steps[-1][1]}, "
                      f"not {final_state}")

    def table(rows):
        out = []
        for text, value in rows:
            if "\n" in text:           # a loop is one operation, several lines
                out.append(text)
                out.append("    leaves " + value)
            else:
                out.append("%-38s %s" % (text, value))
        return "\n".join(out)

    shown = max(1, len(steps) - 1)
    hints = build_hint_tree(
        pattern,
        nudge=nudge,
        visual="Write the structure down after every single operation. The "
               "operation that catches people is never the complicated one — it "
               "is the third boring one, done from memory.",
        pseudocode="The first steps, done for you. Continue the column:\n\n"
                   + _block(table(steps[:2])),
        fragment=_block(table(steps[:shown])) + "\n\nOne operation left.",
        solution=_block(table(steps)) + "\n\nFinal state: " + final_state
                 + "\n\n" + explanation.strip() + "\n\n" + walkthrough.strip(),
    )
    # `probe` travels with the puzzle so the corpus validator can recompute the
    # final state for itself. Checking it only here would leave any future
    # STATE_PREDICT authored outside this family unverified.
    spec = {"code": code, "operations": operations, "probe": probe,
            "final_state": final_state, "explanation": explanation.strip()}
    # The near-misses are the states this structure really passed through on the
    # way, newest first: stopping one operation early is the mistake people
    # actually make, so those are the honest wrong answers.
    spec.update(_one_answer(
        pid, "What does the structure hold when the operations finish?",
        final_state,
        list(misreads) + [value for _t, value in reversed(steps[:-1])] + [start]))
    return _puzzle(pid, title, realm, pattern, difficulty, statement,
                   "STATE_PREDICT", spec, family=family, hints=hints,
                   secondary=secondary, failures=failures,
                   tags=list(tags) + ["state"], after=after)


# ---------------------------------------------------------------------------
# TRACE — from a two-line accumulator to a sliding window
# ---------------------------------------------------------------------------

def _traces() -> list:
    P = []

    P.append(_trace(
        "tr-assign-order", "Right Side First", "python_village", "ARRAY", "GUIDED",
        """
        A line like `score = score + 4` is not a statement of fact. It is an
        order: work out the right-hand side using the values that exist right
        now, then put the result in the name on the left. Say what `score` holds
        as each line finishes.
        """,
        """
        score = 3
        score = score + 4
        score = score * 2
        """,
        [(2, "score", "7", "The right side is worked out first, with the OLD value."),
         (3, "score", "14", "14, not 11: line 2 already replaced the 3 with a 7.")],
        family="python_basics",
        misreads=["6", "11"],
        nudge="Read each line right to left. The old value is used to build the "
              "new one, and then it is gone.",
        walkthrough="Line 1 puts 3 in the box called `score`. Line 2 computes "
                    "3 + 4 = 7 and replaces the contents. Line 3 computes "
                    "7 * 2 = 14 with the value line 2 left behind. The name is a "
                    "box, not an equation.",
        failures=["Treating `score = score + 4` as a claim rather than an order",
                  "Using the original value again on the third line"],
        tags=["concept:01"],
    ))

    P.append(_trace(
        "tr-lost-value", "The Value That Was Overwritten", "python_village",
        "ARRAY", "GUIDED",
        """
        This spell is trying to swap two names and does not manage it. Follow it
        exactly as written — not as intended — and say what each name holds.
        """,
        """
        a = 1
        b = 2
        a = b
        b = a
        """,
        [(3, "a", "2", "Line 3 replaces whatever `a` used to hold. It is not stored anywhere else."),
         (4, "b", "2", "By line 4, `a` is already 2. There is no 1 left to give back.")],
        family="python_basics",
        misreads=["1"],
        nudge="After line 3, is there anywhere in the program still holding a 1?",
        walkthrough="Line 3 overwrites `a` with 2, and the 1 is gone — no name "
                    "refers to it any more. Line 4 then copies that same 2 back "
                    "into `b`. A swap needs somewhere to put the value it is "
                    "about to lose: `a, b = b, a`, or a third name.",
        failures=["Assuming the two lines undo each other",
                  "Forgetting that assignment destroys the old value"],
        after="tr-assign-order",
        tags=["concept:01"],
    ))

    P.append(_trace(
        "tr-seconds-split", "Splitting the Clock", "python_village", "SIMULATION",
        "GUIDED",
        """
        `//` is division that throws away the remainder. `%` is the remainder it
        threw away. Together they take a number apart. Say what each name holds.
        """,
        """
        total_seconds = 3725
        hours = total_seconds // 3600
        rest = total_seconds % 3600
        minutes = rest // 60
        seconds = rest % 60
        """,
        [(2, "hours", "1", "3725 // 3600 keeps the whole hours and drops the rest."),
         (3, "rest", "125", "3725 - 3600. The seconds that did not make an hour."),
         (5, "seconds", "5", "125 % 60 — two minutes, five seconds left over.")],
        family="python_basics",
        misreads=["125", "2"],
        nudge="`//` keeps the whole part, `%` keeps what is left over. Together "
              "they account for every second.",
        walkthrough="3725 seconds is 1 hour (3600) with 125 left. 125 seconds is "
                    "2 minutes (120) with 5 left. `//` and `%` are the same "
                    "division read two different ways, which is why this pattern "
                    "shows up everywhere from clocks to hash buckets.",
        failures=["Using `/` and getting a float", "Dividing the original total by 60 twice"],
        after="tr-lost-value",
        tags=["concept:01"],
    ))

    P.append(_trace(
        "tr-slice-shapes", "Four Cuts", "python_village", "ARRAY", "GUIDED",
        """
        Slicing takes a piece of a list and leaves the original alone. `[a:b]`
        includes a and excludes b. A negative index counts from the end. A third
        number is a step. Say what each piece holds.
        """,
        """
        letters = [10, 20, 30, 40, 50]
        head = letters[:2]
        tail = letters[-2:]
        middle = letters[1:4]
        step = letters[::2]
        """,
        [(2, "head", "[10, 20]", "Stops BEFORE index 2. Two items, not three."),
         (3, "tail", "[40, 50]", "-2 is the second from the end, and the slice runs to the end."),
         (4, "middle", "[20, 30, 40]", "Indexes 1, 2 and 3. Index 4 is excluded."),
         (5, "step", "[10, 30, 50]", "Every second item, starting at index 0.")],
        family="python_basics",
        misreads=["[20, 40]", "[10, 20, 30, 40, 50]"],
        nudge="The end of a slice is always excluded. Count the items you expect "
              "before you count the indexes.",
        walkthrough="`[:2]` is 'up to but not including index 2'. `[-2:]` starts "
                    "two from the end. `[1:4]` is three items, because 4 - 1 = 3 "
                    "— a slice's length is end minus start whenever both are in "
                    "range. `[::2]` takes every second item. None of the four "
                    "touched `letters`; each one built a new list.",
        failures=["Including the end index", "Expecting a slice to modify the original"],
        after="tr-seconds-split",
        tags=["concept:02"],
    ))

    P.append(_trace(
        "tr-alias", "Two Names, One List", "python_village", "ARRAY", "TUTORIAL",
        """
        Assigning a list to a second name does not copy it. Both names point at
        the same list, and either one can change it. Say what `first` holds at
        each mark.
        """,
        """
        first = [1, 2]
        second = first
        second.append(3)
        copy_of = list(first)
        copy_of.append(4)
        """,
        [(3, "first", "[1, 2, 3]", "`second` and `first` are two labels on one list."),
         (5, "first", "[1, 2, 3]", "`list(first)` built a NEW list, so line 5 could not reach this one."),
         (5, "copy_of", "[1, 2, 3, 4]", "The copy was taken after line 3, so it starts with three items.")],
        family="python_basics",
        misreads=["[1, 2, 4]", "[1, 2, 3]"],
        nudge="Ask of each line: did this build a new list, or reach into an "
              "existing one? `append` never builds.",
        walkthrough="Line 2 makes a second label, not a second list — so line 3 "
                    "changes what `first` sees. Line 4 is different: `list(...)` "
                    "constructs a new list holding the same items, and line 5 "
                    "then changes only that new one. This is the single most "
                    "expensive misunderstanding in Python, and it costs real "
                    "money in production every year.",
        failures=["Assuming `=` copies a list",
                  "Assuming `list(x)` copies the items inside the items too"],
        after="tr-slice-shapes",
        tags=["concept:03"],
    ))

    P.append(_trace(
        "tr-accumulate", "The Accumulator", "python_village", "ARRAY", "TUTORIAL",
        """
        The accumulator is the most reused shape in this whole game: start a
        total at nothing, walk the input, fold each item in. Say what survives
        the loop.
        """,
        """
        values = [4, 1, 7]
        total = 0
        for value in values:
            total = total + value
        average = total / len(values)
        """,
        [(5, "total", "12", "Every item folded in: 4 + 1 + 7."),
         (5, "value", "7", "The loop variable outlives the loop, holding the LAST item."),
         (5, "average", "4.0", "Division always produces a float, even when it divides evenly.")],
        family="python_basics",
        misreads=["12", "3.0"],
        nudge="Three things exist after the loop, not one. The loop variable is "
              "still there, and it still holds something.",
        walkthrough="`total` is folded three times: 0+4=4, 4+1=5, 5+7=12. `value` "
                    "is not cleaned up when the loop ends — it keeps the last item "
                    "it was given, which is a fact worth knowing before you "
                    "accidentally rely on it. And `12 / 3` is `4.0`, not `4`: "
                    "`/` always returns a float. `//` is the one that returns an "
                    "integer.",
        failures=["Initialising the total inside the loop",
                  "Expecting `12 / 3` to be an int"],
        after="tr-alias",
        tags=["concept:09"],
    ))

    P.append(_trace(
        "tr-vowel-count", "Counting Inside a Word", "fields_of_syntax", "STRING",
        "TUTORIAL",
        """
        `in` asks a membership question, and for a string it means 'is this one
        of my characters'. Count with it, then say what the loop left behind.
        """,
        """
        word = "gauntlet"
        vowels = "aeiou"
        count = 0
        for letter in word:
            if letter in vowels:
                count = count + 1
        ratio = count / len(word)
        """,
        [(7, "count", "3", "a, u and e. The t, l and n are not in `vowels`."),
         (7, "ratio", "0.375", "3 / 8. Write it as Python would print it.")],
        family="python_basics",
        misreads=["0.5", "0.25"],
        nudge="Walk the eight letters of the word once, keeping a tally. Then "
              "divide by the length of the whole word, not by the tally.",
        walkthrough="g-a-u-n-t-l-e-t: the vowels are a, u and e, so `count` "
                    "reaches 3. `len(word)` is 8, and 3 / 8 is 0.375 exactly. The "
                    "shape — walk, test, tally — is the same accumulator as "
                    "before with a condition bolted on.",
        failures=["Counting the letter 'y'", "Dividing by the count instead of the length"],
        after="tr-accumulate",
        tags=["concept:02"],
    ))

    P.append(_trace(
        "tr-first-repeat", "The First One Seen Twice", "hashmap_highlands", "SET",
        "TUTORIAL",
        """
        A set remembers what it has seen and answers `in` immediately. This spell
        stops at the first repeat. Say what it knows at the moment it stops.
        """,
        """
        seen = set()
        first_repeat = None
        for value in [4, 7, 4, 7]:
            if value in seen:
                first_repeat = value
                break
            seen.add(value)
        """,
        [(6, "first_repeat", "4", "The first value that was ALREADY in the set when it came round again."),
         (6, "seen", "{4, 7}", "Only the values added before the break. The second 4 was never added.")],
        family="set_ops",
        misreads=["{4}", "{4, 7, 2}"],
        nudge="The break fires on the third item. What had been added to the set "
              "before that moment, and what had not?",
        walkthrough="4 is not in the set, so it is added. 7 is not in the set, so "
                    "it is added. The second 4 IS in the set, so `first_repeat` "
                    "becomes 4 and the loop breaks — the `seen.add` on line 7 "
                    "never runs for it, and the final 7 is never looked at. This "
                    "is 'have I seen this before' in its smallest honest form.",
        failures=["Adding to the set before the membership test",
                  "Expecting the whole input to be consumed after a break"],
        after="tr-vowel-count",
        tags=["concept:07"],
    ))

    P.append(_trace(
        "tr-counts-dict", "Tally Book", "hashmap_highlands", "HASH_MAP", "TUTORIAL",
        """
        `counts.get(key, 0)` reads a key that may not exist yet and answers 0
        instead of raising. That one call is what makes counting a one-liner.
        Say what the tally book holds.
        """,
        """
        words = ["ash", "elm", "ash", "oak"]
        counts = {}
        for word in words:
            counts[word] = counts.get(word, 0) + 1
        repeated = [w for w in counts if counts[w] > 1]
        total = sum(counts.values())
        """,
        [(5, "counts", "{'ash': 2, 'elm': 1, 'oak': 1}", "Three distinct words; one of them arrived twice."),
         (5, "repeated", "['ash']", "A list, with the string quoted as Python prints it."),
         (6, "total", "4", "The COUNTS add up to the number of words, not to the number of keys.")],
        family="counting",
        misreads=["3", "2"],
        nudge="The dict has one entry per distinct word. The values are how many "
              "times each arrived — so they add up to the length of the input.",
        walkthrough="ash arrives, missing, so `get` answers 0 and the entry "
                    "becomes 1. elm the same. ash again: `get` now answers 1, so "
                    "the entry becomes 2. oak becomes 1. Three keys, values "
                    "2 + 1 + 1 = 4, which is exactly how many words went in. "
                    "Iterating a dict walks its keys, which is why line 5 can "
                    "test `counts[w]` while looping over `counts`.",
        failures=["Using `counts[word] + 1` on a key that does not exist yet",
                  "Confusing the number of keys with the number of words"],
        after="tr-first-repeat",
        tags=["concept:06"],
    ))

    P.append(_trace(
        "tr-running-best", "The First Maximum", "array_caverns", "ARRAY", "EASY",
        """
        This spell keeps both the best value and where it was found. The input
        contains the maximum twice on purpose. Say what it decides.
        """,
        """
        nums = [3, 9, 2, 9, 4]
        best = nums[0]
        best_index = 0
        for i in range(1, len(nums)):
            if nums[i] > best:
                best = nums[i]
                best_index = i
        winner = nums[best_index]
        """,
        [(7, "best_index", "1", "The body runs exactly once — for the FIRST 9."),
         (7, "best", "9", "Set at the same moment as the index, from the same item."),
         (8, "winner", "9", "Both nines are 9; only the index tells them apart.")],
        family="python_basics",
        misreads=["3", "0"], focus=0,
        nudge="The comparison is strictly greater. When the second 9 arrives, is "
              "it greater than 9?",
        walkthrough="i=1: 9 > 3, so both `best` and `best_index` move. i=2: 2 is "
                    "not greater. i=3: 9 is not greater than 9 — strict `>` keeps "
                    "the earlier one, so the body does not run again. i=4: 4 is "
                    "not greater. Swap `>` for `>=` and `best_index` becomes 3: "
                    "the operator alone decides whether ties go to the first or "
                    "the last, and interviewers ask which you meant.",
        failures=["Assuming `>` and `>=` are interchangeable",
                  "Updating the value without the index"],
        after="tr-counts-dict",
        tags=["concept:04"],
    ))

    P.append(_trace(
        "tr-prefix-sum", "Totals Before You Need Them", "array_caverns",
        "PREFIX_SUM", "EASY",
        """
        A prefix array stores the running total up to each position, with a 0 in
        front. Any range sum is then one subtraction. Say what it builds.
        """,
        """
        nums = [2, 4, 1]
        prefix = [0]
        for n in nums:
            prefix.append(prefix[-1] + n)
        window = prefix[3] - prefix[1]
        """,
        [(5, "prefix", "[0, 2, 6, 7]", "One longer than the input: the leading 0 counts."),
         (5, "window", "5", "Everything up to index 3, minus everything up to index 1.")],
        family="prefix_sum",
        misreads=["7", "6"],
        nudge="`prefix[-1]` is the total so far. The leading 0 is what lets the "
              "first item be added the same way as every other item.",
        walkthrough="The array grows 0, 2, 6, 7 — each entry the total of "
                    "everything before it. `prefix[3] - prefix[1]` is 7 - 2 = 5, "
                    "which is the sum of `nums[1:3]`, that is 4 + 1. The leading "
                    "0 is not decoration: without it the first range would need "
                    "its own special case, and special cases are where bugs live.",
        failures=["Omitting the leading zero",
                  "Off-by-one when converting a range to prefix indexes"],
        after="tr-running-best",
        tags=["concept:09"],
    ))

    P.append(_trace(
        "tr-two-pointer", "Two Pointers Closing In", "twin_pointer_pass",
        "TWO_POINTER", "EASY",
        """
        The list is sorted, so a total that is too small can only be fixed from
        the left, and one that is too large only from the right. Say where the
        pointers are when the spell stops.
        """,
        """
        values = [1, 3, 5, 8]
        left = 0
        right = len(values) - 1
        target = 6
        while left < right:
            total = values[left] + values[right]
            if total == target:
                break
            if total < target:
                left = left + 1
            else:
                right = right - 1
        """,
        [(8, "left", "0", "The left pointer never had to move: only the right side was too big."),
         (8, "right", "2", "Moved once, from index 3 to index 2."),
         (8, "total", "6", "The break only fires when the total is exactly the target.")],
        family="converging",
        misreads=["9", "4"],
        nudge="Two passes at most. Compute the first total, decide which end is "
              "at fault, and move only that one.",
        walkthrough="First total: 1 + 8 = 9, larger than 6, so the right pointer "
                    "steps in to index 2. Second total: 1 + 5 = 6, which hits the "
                    "target and breaks with `left` still at 0. The sortedness is "
                    "doing the work — it is what makes 'too big' mean 'the right "
                    "end is wrong' and nothing else.",
        failures=["Moving both pointers on every step",
                  "Using `left <= right` and pairing an item with itself"],
        after="tr-prefix-sum",
        tags=["concept:10"],
    ))

    P.append(_trace(
        "tr-window", "The Window That Shrinks", "sliding_window_marsh",
        "SLIDING_WINDOW", "EASY",
        """
        The window grows on the right every step and shrinks from the left only
        when it has to. The counts dict is what tells it when it has to. Say what
        all three hold at the end.
        """,
        """
        values = [2, 1, 2, 3]
        window = {}
        left = 0
        best = 0
        for right in range(len(values)):
            value = values[right]
            window[value] = window.get(value, 0) + 1
            while window[value] > 1:
                window[values[left]] = window[values[left]] - 1
                left = left + 1
            best = max(best, right - left + 1)
        longest = best
        """,
        [(12, "window", "{2: 1, 1: 1, 3: 1}", "Inside a window with no repeats, every count is 1."),
         (12, "left", "1", "It moved exactly once, when the second 2 arrived."),
         (12, "longest", "3", "The window [1, 2, 3], which is three items wide.")],
        family="window_distinct",
        misreads=["2", "4"],
        nudge="Follow `left` alone. It moves only inside the while loop, and the "
              "while loop only runs when a count goes above 1.",
        walkthrough="right=0 admits 2. right=1 admits 1, width 2. right=2 admits "
                    "the second 2, which pushes its count to 2 — the while loop "
                    "then drops `values[0]`, putting the count back to 1 and "
                    "moving `left` to 1. right=3 admits 3, giving the window "
                    "[1, 2, 3] with width 3 - 1 + 1 = 3. Every count in the dict "
                    "is 1 because the while loop's whole job is to make that true "
                    "again before the width is measured.",
        failures=["Shrinking the window with an `if` instead of a `while`",
                  "Measuring the width before the shrink",
                  "Forgetting the +1 in `right - left + 1`"],
        after="tr-two-pointer",
        tags=["concept:10"],
    ))

    return P


# ---------------------------------------------------------------------------
# SPOT_THE_FLAW — one line apart, and every curse is a defect that ships
# ---------------------------------------------------------------------------

def _flaws() -> list:
    P = []

    P.append(_flaw(
        "sf-range-short", "One Short", "debugging_dungeon", "ARRAY", "GUIDED",
        """
        Both spells add up a list. One of them quietly leaves money on the table.
        Click the line that breaks it.
        """,
        """
        def total_of(values):
            total = 0
            for i in range(len(values)):
                total = total + values[i]
            return total
        """,
        """
        def total_of(values):
            total = 0
            for i in range(len(values) - 1):
                total = total + values[i]
            return total
        """,
        3,
        "`range(n)` already stops before n — it gives 0 up to n-1. Subtracting "
        "one more drops the last item entirely. The `- 1` belongs in the bound "
        "only when the body looks ahead to `values[i + 1]`, and this body does "
        "not.",
        [[[1, 2, 3]], [[5]]],
        family="python_basics", bug="off_by_one",
        nudge="Count how many times the loop body runs for a list of three "
              "items, then count how many items there are.",
        failures=["Writing `range(len(x) - 1)` out of habit",
                  "Testing only with an empty list, where both agree"],
        tags=["concept:04"],
    ))

    P.append(_flaw(
        "sf-at-least", "At Least", "debugging_dungeon", "ARRAY", "GUIDED",
        """
        The rule is 'a score of at least the cutoff passes'. One of these two
        spells enforces a different rule. Click the line.
        """,
        """
        def passing(scores, cutoff):
            count = 0
            for score in scores:
                if score >= cutoff:
                    count = count + 1
            return count
        """,
        """
        def passing(scores, cutoff):
            count = 0
            for score in scores:
                if score > cutoff:
                    count = count + 1
            return count
        """,
        4,
        "'At least' includes the boundary; `>` excludes it. Everyone who scored "
        "exactly the cutoff is thrown out by the cursed spell. In a detection "
        "rule that is a missed alert, and it is invisible on any test input that "
        "does not land exactly on the threshold.",
        [[[5, 7], 5], [[9], 9]],
        family="python_basics", bug="boundary",
        nudge="Find an input where the two spells could possibly differ. There "
              "is only one kind: a score sitting exactly on the cutoff.",
        failures=["Reading 'at least' as strictly greater",
                  "Choosing test data that never touches the boundary"],
        after="sf-range-short",
        tags=["concept:05"],
    ))

    P.append(_flaw(
        "sf-indent-escape", "A Line Too Far Left", "debugging_dungeon", "ARRAY",
        "GUIDED",
        """
        Both spells report the running total after each item. The two are
        identical character for character except for where one line sits. In
        Python, depth is meaning.
        """,
        """
        def running_totals(values):
            out = []
            total = 0
            for value in values:
                total = total + value
                out.append(total)
            return out
        """,
        """
        def running_totals(values):
            out = []
            total = 0
            for value in values:
                total = total + value
            out.append(total)
            return out
        """,
        6,
        "The append escaped the loop. Instead of recording a total per item it "
        "records one total, once, after everything has been added. The line is "
        "spelled correctly and does the right thing — at the wrong time.",
        [[[1, 2]], [[4]]],
        family="python_basics", bug="indentation",
        nudge="Do not read the words. Read the left edge: which lines belong to "
              "the loop in one spell and not in the other?",
        failures=["Reading indentation as formatting rather than as structure",
                  "Testing with a single-item list, where the two agree"],
        after="sf-at-least",
        tags=["concept:04"],
    ))

    P.append(_flaw(
        "sf-get-default", "The Wrong Starting Point", "hashmap_highlands",
        "HASH_MAP", "TUTORIAL",
        """
        Both spells find the first value that appears exactly once. One of them
        never finds anything. Click the line.
        """,
        """
        def first_unique(values):
            counts = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            for value in values:
                if counts[value] == 1:
                    return value
            return None
        """,
        """
        def first_unique(values):
            counts = {}
            for value in values:
                counts[value] = counts.get(value, 1) + 1
            for value in values:
                if counts[value] == 1:
                    return value
            return None
        """,
        4,
        "The second argument to `get` is what a key is worth before it has been "
        "seen, and a key that has not been seen has been seen zero times. "
        "Starting at 1 makes every count one too high, so nothing ever equals 1 "
        "and the function reports that nothing is unique.",
        [[[1, 2, 2]], [[3, 3]]],
        family="counting", bug="wrong_default",
        nudge="Work out what the count of a single, never-repeated item ends up "
              "being in each spell.",
        failures=["Confusing `get`'s default with the first increment",
                  "Assuming a bug this loud would be obvious in the output"],
        after="sf-indent-escape",
        tags=["concept:06"],
    ))

    P.append(_flaw(
        "sf-mutate-while-iterating", "Changing the Floor You Stand On",
        "debugging_dungeon", "ARRAY", "TUTORIAL",
        """
        Both spells remove every blank from a list in place. One of them skips
        some. Click the line.
        """,
        """
        def drop_blanks(items):
            for item in list(items):
                if item == "":
                    items.remove(item)
            return items
        """,
        """
        def drop_blanks(items):
            for item in items:
                if item == "":
                    items.remove(item)
            return items
        """,
        2,
        "A `for` over a list walks it by position. Removing an item shifts "
        "everything after it down one, but the position counter does not shift "
        "back — so the item that slid into the vacated slot is never looked at. "
        "`list(items)` iterates a snapshot, which is why the honest spell can "
        "safely modify the original.",
        [[["a", "", "", "b"]], [["", ""]]],
        family="python_basics", bug="mutate_while_iterating",
        nudge="Two blanks side by side is the input that shows it. Walk the "
              "positions by number, not by item.",
        failures=["Removing from the list being iterated",
                  "Testing only with non-adjacent duplicates"],
        after="sf-get-default",
        tags=["concept:03"],
    ))

    P.append(_flaw(
        "sf-reversed-subtraction", "Backwards Difference", "array_caverns",
        "ARRAY", "TUTORIAL",
        """
        Both spells measure the largest gap between neighbouring values once the
        list is sorted. One always reports zero. Click the line.
        """,
        """
        def largest_gap(values):
            ordered = sorted(values)
            gap = 0
            for i in range(1, len(ordered)):
                gap = max(gap, ordered[i] - ordered[i - 1])
            return gap
        """,
        """
        def largest_gap(values):
            ordered = sorted(values)
            gap = 0
            for i in range(1, len(ordered)):
                gap = max(gap, ordered[i - 1] - ordered[i])
            return gap
        """,
        5,
        "The operands are the wrong way round. In a sorted list the later value "
        "is the larger one, so the cursed subtraction is always negative or "
        "zero, and `max` against a starting gap of 0 keeps the 0 forever. A "
        "function that always returns its initial value is the signature of a "
        "reversed comparison or a reversed subtraction.",
        [[[1, 5, 6]], [[10, 2]]],
        family="python_basics", bug="reversed_operands",
        nudge="After `sorted`, which of `ordered[i]` and `ordered[i - 1]` is "
              "always the bigger one?",
        failures=["Subtracting in the order the indexes appear in the line",
                  "Not noticing that the result never leaves its initial value"],
        after="sf-mutate-while-iterating",
        tags=["concept:04"],
    ))

    P.append(_flaw(
        "sf-latest-not-best", "Latest, Not Longest", "array_caverns", "ARRAY",
        "EASY",
        """
        Both spells measure the longest run of equal neighbours. One reports the
        last run instead of the longest. Click the line.
        """,
        """
        def longest_run(values):
            best = 0
            run = 0
            previous = None
            for value in values:
                if value == previous:
                    run = run + 1
                else:
                    run = 1
                previous = value
                best = max(best, run)
            return best
        """,
        """
        def longest_run(values):
            best = 0
            run = 0
            previous = None
            for value in values:
                if value == previous:
                    run = run + 1
                else:
                    run = 1
                previous = value
                best = run
            return best
        """,
        11,
        "`run` is the current run and resets whenever the value changes. `best` "
        "is supposed to be a high-water mark, so it may only ever go up — and "
        "that is what `max` is for. Plain assignment throws away every earlier "
        "run, leaving the answer to whatever happened to come last.",
        [[[1, 1, 2]], [[5, 5, 5, 1]]],
        family="python_basics", bug="wrong_accumulator",
        nudge="Put the long run first in the input and the short run last. Which "
              "answer survives?",
        failures=["Overwriting a running best instead of maximising it",
                  "Testing with input whose longest run is also its last"],
        after="sf-reversed-subtraction",
        tags=["concept:09"],
    ))

    P.append(_flaw(
        "sf-zero-key", "The Key That Never Left", "hashmap_highlands", "HASH_MAP",
        "EASY",
        """
        Counts go up, counts come down, and a key whose count reaches zero is
        supposed to leave the dict. One of these spells lets it linger. Click the
        line.
        """,
        """
        def distinct_after(values, removed):
            counts = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            for value in removed:
                counts[value] = counts[value] - 1
                if counts[value] == 0:
                    del counts[value]
            return len(counts)
        """,
        """
        def distinct_after(values, removed):
            counts = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            for value in removed:
                counts[value] = counts[value] - 1
                if counts[value] < 0:
                    del counts[value]
            return len(counts)
        """,
        7,
        "A key mapped to 0 is still a key: `len(counts)` counts it and `in` "
        "finds it. The delete has to fire at zero, not below it. This is the "
        "exact bug that makes a sliding window report distinct-count answers "
        "that are too high, and it only shows once something has been fully "
        "removed.",
        [[[1, 1, 2], [2]], [[4], [4]]],
        family="counting", bug="missing_delete_at_zero",
        nudge="Remove the only copy of a value, then ask the dict how many keys "
              "it has.",
        failures=["Leaving zero-valued keys in a counts dict",
                  "Using `len(counts)` as a distinct-count without pruning"],
        after="sf-latest-not-best",
        tags=["concept:06"],
    ))

    P.append(_flaw(
        "sf-stack-leftovers", "What the Stack Kept", "stack_queue_mines", "STACK",
        "EASY",
        """
        Both spells check that brackets are balanced. One of them is happy with
        an opening bracket that never closes. Click the line.
        """,
        """
        def balanced(text):
            stack = []
            pairs = {")": "(", "]": "["}
            for ch in text:
                if ch in "([":
                    stack.append(ch)
                else:
                    if not stack or stack.pop() != pairs[ch]:
                        return False
            return not stack
        """,
        """
        def balanced(text):
            stack = []
            pairs = {")": "(", "]": "["}
            for ch in text:
                if ch in "([":
                    stack.append(ch)
                else:
                    if not stack or stack.pop() != pairs[ch]:
                        return False
            return True
        """,
        10,
        "Surviving the loop only proves that nothing closed wrongly. Anything "
        "still on the stack is an opener that was never answered, so the final "
        "verdict has to be `not stack`. Returning a bare True passes `(((`.",
        [["(("], ["()"], ["([)]"]],
        family="stack_matching", bug="unchecked_leftovers",
        nudge="Feed it a string that only opens. Where would the evidence of "
              "that be, at the moment the loop ends?",
        failures=["Forgetting the leftovers check at the end",
                  "Testing only with strings that close everything"],
        after="sf-zero-key",
        tags=["concept:03"],
    ))

    P.append(_flaw(
        "sf-binary-bound", "The Range That Closed Too Soon", "stack_queue_mines",
        "BINARY_SEARCH", "EASY",
        """
        Both spells binary-search a sorted list. One of them cannot find a value
        that ends up alone in the range. Click the line.
        """,
        """
        def find(values, target):
            lo = 0
            hi = len(values) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                if values[mid] == target:
                    return mid
                if values[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid - 1
            return -1
        """,
        """
        def find(values, target):
            lo = 0
            hi = len(values) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if values[mid] == target:
                    return mid
                if values[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid - 1
            return -1
        """,
        4,
        "`hi` is an inclusive bound here, so the range `lo == hi` still holds one "
        "unexamined candidate. Stopping at `lo < hi` throws that candidate away "
        "unseen. Inclusive bound, `<=`; exclusive bound (`hi = len(values)`), "
        "`<`. Mixing the two is the classic binary-search off-by-one.",
        [[[1, 3, 5], 5], [[2], 2]],
        family="binary_search", bug="off_by_one",
        nudge="Search for the last element. Watch what `lo` and `hi` are on the "
              "step where the answer is the only candidate left.",
        failures=["Mixing an inclusive bound with an exclusive loop condition",
                  "Never testing a search for the first or last element"],
        after="sf-stack-leftovers",
        tags=["concept:10"],
    ))

    P.append(_flaw(
        "sf-visited-on-pop", "Marked Too Late", "graph_wastes", "BFS", "EASY",
        """
        Both spells visit every node reachable from the start. One of them visits
        a node twice when two roads lead to it. Click the line.
        """,
        """
        def visit_order(graph, start):
            seen = {start}
            queue = [start]
            order = []
            while queue:
                node = queue.pop(0)
                order.append(node)
                for nxt in graph[node]:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
            return order
        """,
        """
        def visit_order(graph, start):
            seen = {start}
            queue = [start]
            order = []
            while queue:
                node = queue.pop(0)
                order.append(node)
                for nxt in graph[node]:
                    if nxt not in seen:
                        seen.add(node)
                        queue.append(nxt)
            return order
        """,
        10,
        "The mark must go on the node being enqueued, at the moment it is "
        "enqueued. Marking anything else — the node being expanded, or nothing "
        "at all until the node is popped — leaves a window in which a second "
        "road can push the same node into the queue again. Queued and visited "
        "have to mean the same thing.",
        [[{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}, "a"]],
        family="graph_traverse", bug="visited_marked_late",
        nudge="Draw a diamond: two roads out of the start, both arriving at the "
              "same node. Count how many times that node enters the queue.",
        failures=["Marking visited on pop instead of on push",
                  "Marking the wrong node inside the neighbour loop"],
        after="sf-binary-bound",
        tags=["concept:11"],
    ))

    return P


# ---------------------------------------------------------------------------
# STATE_PREDICT — stacks, queues, dicts, sets, deques, heaps
# ---------------------------------------------------------------------------

def _states() -> list:
    P = []

    P.append(_state(
        "sp-stack", "Last In, First Out", "stack_queue_mines", "STACK", "GUIDED",
        """
        A plain list is a stack: `append` puts on top, `pop` takes from the top.
        Write the list exactly as Python would print it, bottom of the stack
        first.
        """,
        "stack = []",
        """
        stack.append(1)
        stack.append(2)
        stack.append(3)
        stack.pop()
        stack.append(4)
        """,
        "stack", "[1, 2, 4]",
        "`pop()` with no argument takes from the END of the list, which is the "
        "top of the stack. The 3 is removed, so the 4 lands where it was.",
        family="python_basics",
        nudge="Only the last item is ever removed. Everything below it is "
              "untouched.",
        walkthrough="A list used as a stack costs nothing: `append` and `pop` are "
                    "both O(1) at the end. It is `pop(0)` — from the front — that "
                    "is slow, because every remaining item has to shuffle down.",
        failures=["Assuming `pop()` removes from the front",
                  "Losing track of order after a removal"],
        tags=["concept:03"],
    ))

    P.append(_state(
        "sp-queue", "Oldest Out", "stack_queue_mines", "QUEUE", "GUIDED",
        """
        A deque can be pushed and popped at both ends. Follow all four operations
        and write the contents as a list, front first.
        """,
        """
        from collections import deque
        queue = deque([1, 2, 3])
        """,
        """
        queue.append(4)
        queue.popleft()
        queue.appendleft(9)
        queue.pop()
        """,
        "list(queue)", "[9, 2, 3]",
        "`append`/`pop` work on the right, `appendleft`/`popleft` on the left. "
        "The 4 arrives on the right and is then removed from the right by the "
        "last operation; the 1 leaves from the left; the 9 joins the left.",
        family="python_basics",
        nudge="Four operations, two of them on each end. Track the two ends "
              "separately.",
        walkthrough="A deque exists so that both ends are O(1). A list can only "
                    "promise that at one end, which is why a queue built on "
                    "`list.pop(0)` quietly turns O(n) work into O(n squared).",
        failures=["Confusing `pop` with `popleft`",
                  "Assuming a deque keeps sorted order"],
        after="sp-stack",
        tags=["concept:12"],
    ))

    P.append(_state(
        "sp-dict-edits", "The Ledger", "hashmap_highlands", "HASH_MAP", "GUIDED",
        """
        Five edits to a dict, one of which does nothing at all. Write the final
        dict.
        """,
        'prices = {"axe": 5, "rope": 2}',
        """
        prices["axe"] = prices["axe"] + 3
        prices["torch"] = 1
        del prices["rope"]
        prices.setdefault("axe", 99)
        prices.setdefault("flint", 4)
        """,
        "prices", "{'axe': 8, 'torch': 1, 'flint': 4}",
        "`setdefault` writes only when the key is missing. On 'axe' it is a "
        "read and changes nothing; on 'flint' it inserts. Assigning to a missing "
        "key creates it, and `del` removes it outright.",
        family="counting",
        nudge="One of these five lines is a no-op. Work out which, and why the "
              "other setdefault is not.",
        walkthrough="`setdefault(k, v)` is 'give me the value at k, inserting v "
                    "first if k is missing'. It is the one-line form of the "
                    "check-then-insert dance, and the reason it exists is that "
                    "the hand-written version is where people put the race "
                    "condition.",
        failures=["Expecting `setdefault` to overwrite an existing key",
                  "Forgetting that a plain assignment to a new key inserts it"],
        after="sp-queue",
        tags=["concept:06"],
    ))

    P.append(_state(
        "sp-set", "What the Set Kept", "hashmap_highlands", "SET", "GUIDED",
        """
        A set holds each value at most once and has no order to speak of. Two of
        these four operations change nothing. Write the final set.
        """,
        "seen = {1, 2, 3}",
        """
        seen.add(2)
        seen.add(4)
        seen.discard(1)
        seen.discard(9)
        """,
        "seen", "{2, 3, 4}",
        "Adding something already present does nothing — that is the entire "
        "point of a set. `discard` of a value that is not there also does "
        "nothing, quietly; `remove` would have raised KeyError instead.",
        family="set_ops",
        nudge="Sets do not count. A value is in, or it is not.",
        walkthrough="Use `discard` when absence is fine and `remove` when absence "
                    "is a bug you want to hear about. Choosing between them on "
                    "purpose is a small thing that reads as experience.",
        failures=["Expecting a repeated `add` to store a second copy",
                  "Expecting `discard` to raise on a missing value"],
        after="sp-dict-edits",
        tags=["concept:07"],
    ))

    P.append(_state(
        "sp-slice-assign", "Surgery on a List", "array_caverns", "ARRAY",
        "TUTORIAL",
        """
        Four ways to change a list in place, including one that replaces a whole
        slice with fewer items than it removed. Write the final list.
        """,
        "items = [1, 2, 3, 4, 5]",
        """
        items[1:3] = [9]
        items.insert(0, 7)
        items.remove(4)
        items.pop()
        """,
        "items", "[7, 1, 9]",
        "Assigning to a slice replaces that whole stretch, and the replacement "
        "need not be the same length — two items become one and the list gets "
        "shorter. `remove` deletes by VALUE, `pop` by position (the last, here).",
        family="python_basics",
        nudge="Take them one at a time and rewrite the whole list after each. "
              "The first operation changes the length.",
        walkthrough="`items[1:3] = [9]` removes indexes 1 and 2 and splices a "
                    "single 9 into the gap. Then 7 goes on the front, the VALUE 4 "
                    "is removed — not index 4 — and `pop()` takes the last item. "
                    "`remove` by value and `pop` by index look alike and are not, "
                    "which is a favourite source of quiet damage.",
        failures=["Reading `remove(4)` as 'remove index 4'",
                  "Assuming a slice assignment keeps the length"],
        after="sp-set",
        tags=["concept:03"],
    ))

    P.append(_state(
        "sp-aliased-rows", "One Row, Twice", "array_caverns", "ARRAY", "TUTORIAL",
        """
        A grid built from a single row object. Write the final grid, as a list of
        lists.
        """,
        """
        row = [0, 0]
        grid = [row, row]
        """,
        """
        grid[0][0] = 1
        grid.append([0, 0])
        grid[2][1] = 5
        """,
        "grid", "[[1, 0], [1, 0], [0, 5]]",
        "`grid` holds the same row object twice, so writing through `grid[0]` "
        "shows up in `grid[1]`. The third row was built separately and is the "
        "only one that behaves the way the code looks like it behaves.",
        family="python_basics",
        nudge="Count the lists that actually exist. There are fewer than there "
              "are entries in `grid`.",
        walkthrough="This is `[[0] * w] * h` in disguise, and it is the reason "
                    "that idiom is a bug. Build rows with a comprehension — "
                    "`[[0] * w for _ in range(h)]` — so each row is its own list.",
        failures=["Assuming repeated references are independent copies",
                  "Building a grid with `[[0] * w] * h`"],
        after="sp-slice-assign",
        tags=["concept:03"],
    ))

    P.append(_state(
        "sp-counter", "A Zero Is Still a Key", "hashmap_highlands", "HASH_MAP",
        "EASY",
        """
        `Counter` is a dict that answers 0 for keys it has never seen. Write the
        final contents as a plain dict.
        """,
        """
        from collections import Counter
        counts = Counter("banana")
        """,
        """
        counts["a"] = counts["a"] - 1
        counts["z"] = counts["z"] + 0
        del counts["n"]
        """,
        "dict(counts)", "{'b': 1, 'a': 2, 'z': 0}",
        "Reading a missing key from a Counter gives 0 without inserting it — but "
        "ASSIGNING to it does insert, even when the value is 0. That is how "
        "zero-valued keys accumulate, and why `len(counts)` stops meaning "
        "'distinct things present'.",
        family="frequency",
        nudge="'banana' first. Then ask which of the three operations adds a key "
              "rather than changing one.",
        walkthrough="Counter('banana') is b:1, a:3, n:2. The first line takes 'a' "
                    "down to 2. The second reads 'z' as 0 and then assigns 0 "
                    "back, creating the key. The third deletes 'n' outright. "
                    "Deleting at zero is deliberate work — nothing does it for "
                    "you.",
        failures=["Assuming a zero count removes itself",
                  "Assuming reading a missing Counter key inserts it"],
        after="sp-aliased-rows",
        tags=["concept:12"],
    ))

    P.append(_state(
        "sp-defaultdict", "The Key That Reading Created", "hashmap_highlands",
        "HASH_MAP", "EASY",
        """
        A `defaultdict(list)` builds an empty list for any key you touch. Three
        of these four lines add something; the fourth only looks. Write the final
        contents as a plain dict.
        """,
        """
        from collections import defaultdict
        groups = defaultdict(list)
        """,
        """
        groups["a"].append(1)
        groups["b"].append(2)
        groups["a"].append(3)
        size = len(groups["c"])
        """,
        "dict(groups)", "{'a': [1, 3], 'b': [2], 'c': []}",
        "Reading `groups['c']` is not a read. A defaultdict creates the missing "
        "key on access, so merely asking how long it is leaves an empty list "
        "behind. Use `.get(k, [])` when you want to look without touching.",
        family="counting",
        nudge="Three keys go in, but only two lines say `append`.",
        walkthrough="`defaultdict` trades a KeyError for an insertion, which is "
                    "exactly what you want in the grouping loop and exactly what "
                    "you do not want when checking whether a key exists. The same "
                    "surprise bites `d[k] += 1` on a plain dict, just in the "
                    "other direction.",
        failures=["Treating a defaultdict read as harmless",
                  "Using `in` and indexing interchangeably"],
        after="sp-counter",
        tags=["concept:12"],
    ))

    P.append(_state(
        "sp-heap", "Not a Sorted List", "stack_queue_mines", "HEAP", "EASY",
        """
        A heap is a plain list kept under one rule: every item is smaller than
        its two children, at positions 2i+1 and 2i+2. That guarantees the
        smallest item sits at index 0 and promises nothing else. Write the list.
        """,
        """
        import heapq
        heap = []
        """,
        """
        heapq.heappush(heap, 5)
        heapq.heappush(heap, 1)
        heapq.heappush(heap, 3)
        heapq.heappop(heap)
        heapq.heappush(heap, 2)
        """,
        "heap", "[2, 5, 3]",
        "`heappop` takes index 0, moves the LAST item into the hole and sifts it "
        "down — it does not shuffle everything along. The result is ordered "
        "enough to answer 'smallest' and no more, which is why it costs "
        "O(log n) instead of O(n log n).",
        family="top_k",
        nudge="Do not sort. After each operation, check only that every item is "
              "smaller than the items at 2i+1 and 2i+2.",
        walkthrough="Pushes build 5, then [1, 5], then [1, 5, 3]. The pop removes "
                    "the 1, lifts the last item into index 0 and sifts it down. "
                    "The final push puts 2 at the end and sifts it UP past its "
                    "parent. Expecting a sorted list here is the mistake that "
                    "makes people call `sorted()` on a heap and lose the whole "
                    "advantage.",
        failures=["Expecting the heap list to be sorted",
                  "Assuming a pop shifts every remaining item along"],
        after="sp-defaultdict",
        tags=["concept:12"],
    ))

    P.append(_state(
        "sp-deque-window", "The Window That Drops Its Own", "sliding_window_marsh",
        "QUEUE", "EASY",
        """
        `maxlen` makes a deque forget: pushing into a full one silently drops the
        item at the far end. Write the contents as a list, front first.
        """,
        """
        from collections import deque
        window = deque([1, 2, 3], maxlen=3)
        """,
        """
        window.append(4)
        window.appendleft(0)
        window.rotate(1)
        """,
        "list(window)", "[3, 0, 2]",
        "Appending to a full deque drops from the opposite end — `append` "
        "evicts on the left, `appendleft` evicts on the right. `rotate(1)` then "
        "moves every item one place to the RIGHT, wrapping the last item around "
        "to the front.",
        family="queue_window",
        nudge="The deque is already full. Each push costs an eviction at the far "
              "end, before you get to the rotate.",
        walkthrough="[1,2,3] append 4 drops the 1, leaving [2,3,4]. appendleft 0 "
                    "drops the 4 from the right, leaving [0,2,3]. rotate(1) "
                    "shifts right by one and wraps the 3 to the front, giving "
                    "[3,0,2]. A maxlen deque is a fixed window that maintains "
                    "itself, and the eviction is silent — which is either the "
                    "feature or the bug, depending on whether you knew.",
        failures=["Expecting a full deque to grow", "Rotating in the wrong direction"],
        after="sp-heap",
        tags=["concept:12"],
    ))

    P.append(_state(
        "sp-rpn", "The Stack Does the Arithmetic", "stack_queue_mines", "STACK",
        "EASY",
        """
        Postfix notation needs no brackets: an operator consumes the two values
        most recently pushed and pushes its result. Run the loop and write what
        the stack holds at the end.
        """,
        """
        stack = []
        tokens = ["3", "4", "+", "2", "*"]
        """,
        """
        for token in tokens:
            if token.isdigit():
                stack.append(int(token))
            else:
                b = stack.pop()
                a = stack.pop()
                stack.append(a + b if token == "+" else a * b)
        """,
        "stack", "[14]",
        "`3 4 +` leaves 7, then `2 *` consumes the 7 and the 2 and leaves 14. "
        "The second pop is the LEFT operand — the order matters the moment the "
        "operator is `-` or `/`, which is the detail this puzzle exists to make "
        "you notice.",
        family="stack_eval",
        misreads=["[7, 2]", "[3, 4, 2]"],
        nudge="Push the digits, and whenever an operator arrives take the top "
              "two off before pushing anything back.",
        walkthrough="Push 3, push 4. The `+` pops 4 into `b` and 3 into `a` and "
                    "pushes 7. Push 2. The `*` pops 2 into `b` and 7 into `a` and "
                    "pushes 14. One value left on the stack is what a "
                    "well-formed expression should always end with — more than "
                    "one means the input was malformed, and that is worth "
                    "checking out loud in a timed practical.",
        failures=["Popping the operands in the wrong order",
                  "Forgetting that the result is pushed back on"],
        after="sp-deque-window",
        tags=["concept:03"],
    ))

    return P


def build() -> list:
    """Every reasoning puzzle, with every expected value checked against a real
    execution. Disagreements are collected rather than raised one at a time, so
    one build reports all of them."""
    _AUDIT.clear()
    problems = _traces() + _flaws() + _states()
    if _AUDIT:
        raise AssertionError(
            "reasoning corpus disagrees with Python:\n  " + "\n  ".join(_AUDIT))
    return problems
