"""Puzzle encounters: ways to engage with code that are not "type a function".

Every encounter in the first build reduced to the same interaction — blank editor,
write the whole thing, submit. That is the hardest possible interaction for someone
whose stated weakness is producing Python from a blank screen, and it is monotonous
besides.

These six puzzle types each demand real understanding through a different door.
Crucially, none of them is a quiz: every one is graded by running actual Python in
the sandbox, or by an exact structural match that a guess cannot fake.

  RUNE_ASSEMBLY   order shuffled lines into a working function (a Parsons problem)
  TRACE           predict the value of variables at marked checkpoints
  SPOT_THE_FLAW   two near-identical implementations; find the line that breaks one
  STATE_PREDICT   predict a data structure's exact state after an operation trace
  BREAK_IT        supply an input that makes plausible-looking code fail
  COMPLEXITY_MATCH  match several snippets to their costs at once

RUNE_ASSEMBLY deserves the special mention: line-ordering is the established
technique for exactly this player's bottleneck. It removes the typing and the
syntax recall, leaving nothing but the structure of the solution — which is the
thing actually being learned.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict

from . import sandbox

PUZZLE_KINDS = (
    "RUNE_ASSEMBLY", "TRACE", "SPOT_THE_FLAW",
    "STATE_PREDICT", "BREAK_IT", "COMPLEXITY_MATCH",
)


# ---------------------------------------------------------------------------
# Authoring structures
# ---------------------------------------------------------------------------

@dataclass
class Rune:
    """One line of a Parsons problem."""
    text: str                # the line, WITHOUT leading indentation
    indent: int              # required indent level, in units of four spaces
    distractor: bool = False # a plausible line that does not belong at all
    note: str = ""           # shown after grading, explaining this line's role

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Checkpoint:
    """One "what is this variable now?" question inside a TRACE puzzle."""
    after_line: int          # 1-based line number the player is asked about
    variable: str
    expected: str            # repr of the expected value
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def shuffle_runes(runes: list, seed: int) -> list:
    """Deterministic shuffle so the same puzzle presents the same way each visit —
    a puzzle that reshuffles on every glance feels broken rather than challenging."""
    order = list(range(len(runes)))
    random.Random(seed).shuffle(order)
    return order


# ---------------------------------------------------------------------------
# Graders. Each returns the standard result shape the engine already understands.
# ---------------------------------------------------------------------------

def _line(name, status, message="", got=None, expected=None, hidden=False):
    return {"name": name, "status": status, "hidden": hidden, "ms": 0,
            "message": message, "got": got, "expected": expected}


def grade_rune_assembly(problem, submitted: list) -> dict:
    """`submitted` is a list of {"index": int, "indent": int} in the player's order.

    Graded twice over: the assembled source must actually pass the problem's tests,
    AND we report which specific lines are misplaced so a near-miss teaches rather
    than merely failing.
    """
    runes = [Rune(**r) for r in problem.mcq.get("runes", [])]
    correct = [i for i, r in enumerate(runes) if not r.distractor]

    chosen = [entry.get("index") for entry in submitted]
    indents = {entry.get("index"): entry.get("indent", 0) for entry in submitted}

    lines = []
    used_distractors = [i for i in chosen if 0 <= i < len(runes) and runes[i].distractor]
    for i in used_distractors:
        lines.append(_line(f"rune {i + 1}", "fail",
                           "This rune does not belong in the spell at all. "
                           + (runes[i].note or "")))

    missing = [i for i in correct if i not in chosen]
    for i in missing:
        lines.append(_line("missing rune", "fail",
                           "A required rune was left out of the sequence."))

    # build the source the player actually assembled
    source_lines = []
    for entry in submitted:
        i = entry.get("index")
        if not (0 <= i < len(runes)):
            continue
        source_lines.append("    " * max(0, int(entry.get("indent", 0))) + runes[i].text)
    source = "\n".join(source_lines) + "\n"

    order_ok = chosen == correct
    indent_ok = all(indents.get(i) == runes[i].indent for i in correct if i in indents)

    lines.append(_line("sequence", "pass" if order_ok else "fail",
                       "" if order_ok else "The runes are not yet in a working order."))
    lines.append(_line("indentation", "pass" if indent_ok else "fail",
                       "" if indent_ok else "At least one rune sits at the wrong depth. "
                                            "In Python, depth is meaning."))

    report = sandbox.run_tests(source, problem.entry, problem.all_tests,
                               timeout_ms=2500, wall_seconds=15)
    if report.phase == "syntax":
        lines.append(_line("the spell compiles", "fail",
                           "The assembled runes do not form valid Python: "
                           + (report.error or {}).get("message", "")))
    else:
        for t in report.tests:
            lines.append(_line(t.name, t.status, t.message,
                               got=t.got if not t.hidden else None,
                               expected=t.expected if not t.hidden else None,
                               hidden=t.hidden))

    passed = sum(1 for line in lines if line["status"] == "pass")
    solved = report.all_passed and not used_distractors and not missing
    return {
        "solved": solved,
        "lines": lines,
        "passed": passed,
        "total": len(lines),
        "assembled_source": source,
        "report": report,
    }


def grade_trace(problem, answers: list) -> dict:
    """`answers` is a list of strings, one per checkpoint, in order."""
    checkpoints = [Checkpoint(**c) for c in problem.mcq.get("checkpoints", [])]
    lines = []
    correct = 0
    for i, checkpoint in enumerate(checkpoints):
        given = (answers[i] if i < len(answers) else "").strip()
        expected = checkpoint.expected.strip()
        ok = _values_match(given, expected)
        correct += ok
        lines.append(_line(
            f"line {checkpoint.after_line}: {checkpoint.variable}",
            "pass" if ok else "fail",
            "" if ok else (checkpoint.hint or
                           "Trace that line by hand and watch what changes."),
            got=None if ok else (given or "(blank)"),
            expected=None if ok else expected))
    return {"solved": bool(checkpoints) and correct == len(checkpoints),
            "lines": lines, "passed": correct, "total": len(checkpoints)}


def _values_match(given: str, expected: str) -> bool:
    """Forgiving about formatting, strict about value. '{1: 2}' and '{1:2}' are the
    same answer; '2' and '3' are not."""
    if given == expected:
        return True
    try:
        return json.loads(given.replace("'", '"')) == json.loads(expected.replace("'", '"'))
    except Exception:
        pass
    try:
        import ast
        return ast.literal_eval(given) == ast.literal_eval(expected)
    except Exception:
        return "".join(given.split()) == "".join(expected.split())


def grade_spot_the_flaw(problem, chosen_line: int) -> dict:
    spec = problem.mcq
    answer = spec.get("flawed_line")
    ok = chosen_line == answer
    return {
        "solved": ok,
        "lines": [_line("the flawed rune", "pass" if ok else "fail",
                        "" if ok else "That line is identical in both spells. "
                                      "Compare them again, line by line.")],
        "passed": int(ok), "total": 1,
        "explanation": spec.get("explanation", ""),
        "answer": answer,
    }


def grade_state_predict(problem, answer: str) -> dict:
    expected = problem.mcq.get("final_state", "")
    ok = _values_match((answer or "").strip(), expected.strip())
    return {
        "solved": ok,
        "lines": [_line("final state", "pass" if ok else "fail",
                        "" if ok else "Replay the operations one at a time. Write the "
                                      "structure down after each one.",
                        got=None if ok else (answer or "(blank)"),
                        expected=None if ok else expected)],
        "passed": int(ok), "total": 1,
        "explanation": problem.mcq.get("explanation", ""),
    }


def grade_break_it(problem, args) -> dict:
    """The player supplies an input. We run the flawed implementation AND the correct
    one on it. If the outputs differ — or the flawed one raises — the player has
    found the break, and proved they can reason about where code fails.

    This is the same skill as writing a good edge-case test, with none of the syntax.
    """
    spec = problem.mcq
    flawed = spec.get("flawed_code", "")
    correct = problem.canonical_solution
    entry = problem.entry

    probe = [{"name": "your input", "args": args, "expected": None,
              "cmp": "exact", "hidden": False}]

    # what the honest implementation does
    truth = sandbox.run_tests(
        correct + "\n\ndef __truth(*a):\n"
        f"    return {entry['name']}(*a)\n",
        {"kind": "function", "name": "__truth",
         "preamble": entry.get("preamble", "")},
        [{"name": "truth", "args": args, "expected": "__NEVER__",
          "cmp": "exact", "hidden": False}],
        timeout_ms=2000, wall_seconds=10)

    flaw = sandbox.run_tests(
        flawed + "\n\ndef __flaw(*a):\n"
        f"    return {entry['name']}(*a)\n",
        {"kind": "function", "name": "__flaw",
         "preamble": entry.get("preamble", "")},
        [{"name": "flaw", "args": args, "expected": "__NEVER__",
          "cmp": "exact", "hidden": False}],
        timeout_ms=2000, wall_seconds=10)

    if truth.phase != "tests" or not truth.tests:
        return {"solved": False, "passed": 0, "total": 1,
                "lines": [_line("your input", "fail",
                                "That input does not fit the function's signature. "
                                "Check the shape of the arguments.")]}

    truth_test = truth.tests[0]
    if truth_test.status in ("exception", "timeout"):
        # The honest spell falls over on this input too, so the input is outside
        # what the contract promises and proves nothing about the flaw. Without
        # this, `[]` — no arguments at all — "broke" every BREAK_IT in the corpus
        # by arity error, which is a way of winning that teaches nothing.
        return {"solved": False, "passed": 0, "total": 1,
                "lines": [_line("your input", "fail",
                                "The honest spell cannot handle that input "
                                "either, so it says nothing about the flaw. "
                                "Stay inside what the contract promises.")]}

    truth_value = truth_test.got
    flaw_test = flaw.tests[0] if flaw.tests else None

    if flaw.phase == "syntax":
        return {"solved": False, "passed": 0, "total": 1,
                "lines": [_line("the flawed spell", "fail",
                                "The flawed spell will not compile at all.")]}

    if flaw_test is None:
        broke, why = True, "the flawed spell could not even run on it"
    elif flaw_test.status in ("exception", "timeout"):
        broke, why = True, f"the flawed spell {flaw_test.status} on it"
    else:
        broke = flaw_test.got != truth_value
        why = ("the two spells disagree on it" if broke
               else "both spells agree on it — this input does not expose the flaw")

    detail = ""
    if broke and flaw_test is not None and flaw_test.status == "pass":
        detail = f"correct gives {truth_value}, the flawed one gives {flaw_test.got}"

    return {
        "solved": broke,
        "lines": [_line("your input", "pass" if broke else "fail",
                        f"You found it — {why}. {detail}" if broke
                        else f"Not this one: {why}. Think about what the code assumes.")],
        "passed": int(broke), "total": 1,
        "explanation": spec.get("explanation", "") if broke else "",
    }


def grade_complexity_match(problem, pairing: dict) -> dict:
    """`pairing` maps snippet index (as a string) to the chosen complexity."""
    spec = problem.mcq
    snippets = spec.get("snippets", [])
    lines = []
    correct = 0
    for i, snippet in enumerate(snippets):
        given = (pairing.get(str(i)) or pairing.get(i) or "").strip()
        expected = snippet.get("complexity", "")
        ok = given.replace(" ", "") == expected.replace(" ", "")
        correct += ok
        lines.append(_line(snippet.get("label", f"snippet {i + 1}"),
                           "pass" if ok else "fail",
                           "" if ok else snippet.get("why", ""),
                           got=None if ok else (given or "(unmatched)"),
                           expected=None if ok else expected))
    return {"solved": bool(snippets) and correct == len(snippets),
            "lines": lines, "passed": correct, "total": len(snippets)}


# ---------------------------------------------------------------------------
# Answer keys. Server-side only.
# ---------------------------------------------------------------------------
#
# Each of these is the exact inverse of the grader above it, read out of the
# same `mcq` fields. They exist so the corpus can be checked against itself: a
# puzzle whose own key does not grade as solved is an unwinnable fight, and the
# only way to know that before the player meets it is to play it at build time.
# Nothing here is ever sent to the client — `Problem.player_view` withholds the
# fields these read.

def answer_key(problem):
    """The correct submission for this puzzle."""
    kind = problem.encounter_kind
    spec = problem.mcq
    if kind == "RUNE_ASSEMBLY":
        return [{"index": i, "indent": r["indent"]}
                for i, r in enumerate(spec.get("runes", []))
                if not r.get("distractor")]
    if kind == "TRACE":
        return [c["expected"] for c in spec.get("checkpoints", [])]
    if kind == "SPOT_THE_FLAW":
        return spec.get("flawed_line")
    if kind == "STATE_PREDICT":
        return spec.get("final_state", "")
    if kind == "BREAK_IT":
        probes = spec.get("probes") or []
        return list(probes[0]) if probes else []
    if kind == "COMPLEXITY_MATCH":
        return {str(i): snippet.get("complexity", "")
                for i, snippet in enumerate(spec.get("snippets", []))}
    raise KeyError(f"no answer key for {kind}")


# A value no puzzle in the corpus can legitimately expect, so a grader that
# accepts it is accepting anything.
_NONSENSE = "__not_an_answer__"


def decoy_answer(problem):
    """A well-formed but obviously wrong submission.

    Winnable is only half of the contract. A puzzle that grades a guess as a
    solve teaches the player that guessing works, which is worse than an
    unwinnable one — so the corpus is checked from both directions.

    BREAK_IT is the exception and returns None: its decoy has to be an input the
    two spells genuinely agree on, which is a property of the problem's tests
    rather than of its `mcq`. The validator supplies it.
    """
    kind = problem.encounter_kind
    spec = problem.mcq
    if kind == "RUNE_ASSEMBLY":
        key = answer_key(problem)
        # Reversed, so the runes are all present and all in the wrong places. A
        # one-rune body cannot be reversed into a wrong order, so drop it
        # instead: a missing rune is the other thing that must not pass.
        return list(reversed(key)) if len(key) > 1 else []
    if kind == "TRACE":
        return [_NONSENSE] * len(spec.get("checkpoints", []))
    if kind == "SPOT_THE_FLAW":
        line = spec.get("flawed_line") or 1
        count = len(spec.get("code", "").split("\n"))
        return line + 1 if line + 1 <= count else max(1, line - 1)
    if kind == "STATE_PREDICT":
        return _NONSENSE
    if kind == "BREAK_IT":
        return None
    if kind == "COMPLEXITY_MATCH":
        # Off the top of the ladder, so it is wrong for every snippet at once.
        return {str(i): "O(n!)" for i in range(len(spec.get("snippets", [])))}
    raise KeyError(f"no decoy for {kind}")


GRADERS = {
    "RUNE_ASSEMBLY": grade_rune_assembly,
    "TRACE": grade_trace,
    "SPOT_THE_FLAW": grade_spot_the_flaw,
    "STATE_PREDICT": grade_state_predict,
    "BREAK_IT": grade_break_it,
    "COMPLEXITY_MATCH": grade_complexity_match,
}


def _payload_ok(kind: str, payload) -> bool:
    """Is this the shape the kind's grader reads?

    The payload comes off the wire, so it is whatever the client sent — and the
    engine also routes a plain `submit(code)` here when the active encounter
    turns out to be a puzzle. Either way a wrong shape is a wrong answer, not a
    traceback out of the server.
    """
    if kind == "RUNE_ASSEMBLY":
        return isinstance(payload, list) and all(isinstance(e, dict) for e in payload)
    if kind in ("TRACE", "BREAK_IT"):
        return isinstance(payload, list)
    if kind == "SPOT_THE_FLAW":
        return isinstance(payload, int) and not isinstance(payload, bool)
    if kind == "STATE_PREDICT":
        return isinstance(payload, str)
    if kind == "COMPLEXITY_MATCH":
        return isinstance(payload, dict)
    return True


def grade(problem, payload) -> dict:
    """Dispatch on the problem's encounter kind."""
    grader = GRADERS.get(problem.encounter_kind)
    if grader is None:
        raise KeyError(f"no grader for {problem.encounter_kind}")
    if not _payload_ok(problem.encounter_kind, payload):
        return {"solved": False, "passed": 0, "total": 1,
                "lines": [_line("your answer", "fail",
                                "That answer did not arrive in a shape this "
                                "puzzle can read. Nothing was graded.")]}
    return grader(problem, payload)


# ---------------------------------------------------------------------------
# What each puzzle type trains — used for skill crediting and for the UI blurb
# ---------------------------------------------------------------------------

PUZZLE_SKILL = {
    "RUNE_ASSEMBLY": "PYTHON",
    "TRACE": "DEBUGGING",
    "SPOT_THE_FLAW": "DEBUGGING",
    "STATE_PREDICT": "PYTHON",
    "BREAK_IT": "TESTING",
    "COMPLEXITY_MATCH": "BIG_O",
}

PUZZLE_BLURB = {
    "RUNE_ASSEMBLY": "The runes of this spell are scattered. Set them in working "
                     "order, at the right depth. No typing — only structure.",
    "TRACE": "Follow the spell as it casts. At each mark, say what the variable holds.",
    "SPOT_THE_FLAW": "Two spells, near identical. One is cursed. Find the line.",
    "STATE_PREDICT": "The operations are given. Say exactly what the structure holds "
                     "when they finish.",
    "BREAK_IT": "This spell looks correct. Find the single input that proves it is not.",
    "COMPLEXITY_MATCH": "Price each spell. All of them, at once.",
}
