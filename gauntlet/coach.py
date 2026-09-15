"""The post-attempt coach.

Two hard rules:

1. The coach is UNAVAILABLE during Timed Practical Mode. Not "discouraged" — the
   provider is not constructed, and `available_in()` returns False. Timed Practical
   Mode's whole value is that it measures unaided performance.
2. The coach is Socratic first. It asks the question that would have unblocked
   you before it shows you anything.

An AI provider is optional. With no provider configured the coach still works:
the offline path is a real analysis built from the failure classification, the
test evidence and the player's own history.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .config import MODE_INTERVIEW
from .grading import FAILURE_BLURB

SOCRATIC_LADDER = {
    "INEFFICIENT_ALGORITHM": [
        "What constraint in the problem makes your current approach expensive?",
        "Which operation are you repeating that you have already computed once?",
        "What structure would make that repeated lookup constant-time?",
        "Could you avoid restarting the scan from every position?",
    ],
    "WRONG_DATA_STRUCTURE": [
        "What question are you asking of your data on every single step?",
        "Is that a membership question, an ordering question, or a counting question?",
        "Which structure answers that exact question in O(1)?",
    ],
    "PATTERN_NOT_RECOGNIZED": [
        "Read the statement again. Which words describe the SHAPE of the answer?",
        "Is the answer contiguous, or may it skip elements?",
        "Does the answer need the whole input at once, or can it be built as you scan?",
        "Which family have you solved before that had those same properties?",
    ],
    "OFF_BY_ONE": [
        "Take the smallest input where it fails. What are the index bounds there?",
        "Does your loop include or exclude its final index?",
        "Trace the first and last iteration by hand. Which one is wrong?",
    ],
    "EDGE_CASE": [
        "What is the smallest possible input this function can receive?",
        "What does your code do when the input is empty?",
        "What does it do when every element is identical?",
    ],
    "STATE_MANAGEMENT": [
        "Which variable holds state that must survive the loop?",
        "Where is it initialised, and is that inside or outside the loop?",
        "When the loop condition changes, what should reset and what should not?",
    ],
    "RECURSION": [
        "What is the smallest input your function should handle without recursing?",
        "Is that base case reachable from every legal input?",
        "Does each recursive call receive a strictly smaller input?",
    ],
    "SYNTAX": [
        "What is the first line the interpreter complained about?",
        "Read that line and the one above it. What structure is unclosed or unindented?",
    ],
    "PYTHON_RECALL": [
        "Which exact Python expression were you reaching for?",
        "What type is the value at that point — and does that type support what you asked?",
    ],
    "WRONG_ALGORITHM": [
        "State in one sentence what your code computes.",
        "Now state in one sentence what the problem asked for.",
        "Where do those two sentences diverge?",
    ],
    "TIME_PRESSURE": [
        "Where did the time actually go — recognising, designing, typing, or debugging?",
        "Which of those four is the one you can shorten with practice this week?",
    ],
    "COMPLEXITY": [
        "How much work happens per element?",
        "How many elements does that work happen for?",
        "Multiply those. Is that what you claimed?",
    ],
}

DEFAULT_LADDER = [
    "What did you expect to happen on the failing input?",
    "What actually happened?",
    "At which line do those two stories first diverge?",
]


@dataclass
class CoachReply:
    available: bool
    questions: list
    analysis: str
    next_steps: list
    source: str          # "offline" | provider name
    reveal_solution: bool = False


def available_in(mode: str) -> bool:
    """Timed Practical Mode has no coach. This is enforced, not advised."""
    return mode != MODE_INTERVIEW


def provider_name() -> str | None:
    """AI is an optional accelerant, never a dependency. Core gameplay, code
    execution and deterministic scoring never call this."""
    if os.environ.get("GAUNTLET_AI_PROVIDER"):
        return os.environ["GAUNTLET_AI_PROVIDER"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def _history_note(history: list) -> str:
    if not history:
        return ""
    solved = [a for a in history if a["solved"]]
    if not solved:
        return (f"You have attempted this {len(history)} time(s) without a clear yet. "
                "That is information, not failure — it means the prerequisite is the "
                "thing to fix, not this problem.")
    best = min(a["seconds"] for a in solved)
    return (f"You have cleared this before, best time {int(best)}s. "
            "The knowledge is there; what is being trained now is retrieval speed.")


def coach(*, mode: str, analysis, problem, report, hints_used: int,
          seconds: float, history: list, attempts_on_problem: int,
          served_rung: int | None = None, evidence_kind: str | None = None) -> CoachReply:
    if not available_in(mode):
        return CoachReply(
            available=False, questions=[],
            analysis="The coach is sealed during Timed Practical Mode. It opens the moment "
                     "the attempt is scored.",
            next_steps=[], source="none")

    root = analysis.root_cause or ""
    questions = SOCRATIC_LADDER.get(root, DEFAULT_LADDER)[:]

    if not root:
        kind = str(evidence_kind or "unknown")
        encounter_kind = str(getattr(problem, "encounter_kind", ""))
        noncoding = {"PATTERN_ENCOUNTER", "COMPLEXITY_DUEL", "CODE_READING", "RUNE_ASSEMBLY",
                     "TRACE", "SPOT_THE_FLAW", "STATE_PREDICT", "BREAK_IT", "COMPLEXITY_MATCH", "DEBUG_BATTLE", "TEST_FORGE", "MINI_REPO"}
        if kind in {"reading", "puzzle", "debugging", "test_writing", "repository"} or encounter_kind in noncoding:
            support = f"{kind if kind != 'unknown' else 'reading/puzzle'} practice; this is not whole-function coding evidence"
        elif served_rung in (1, 2, 3):
            support = f"scaffold support at rung {served_rung}; this is supported practice"
        elif kind == "whole_function" and served_rung == 4:
            support = "whole-function coding practice"
        else:
            support = "support level not recorded; independence is unverified"
        text = (f"Clean clear in {int(seconds)}s against a target of "
                f"{problem.target_seconds}s"
                + f", with {support}"
                + (f" and {hints_used} spell(s) used." if hints_used
                   else " and no recorded spells."))
        steps = []
        if hints_used or kind != "whole_function" or served_rung != 4:
            steps.append("Try a whole-function version without scaffold support or spells "
                         "to check independent code production.")
        if seconds > problem.target_seconds:
            steps.append(f"Target time is {problem.target_seconds}s. The Chronomancer's "
                         "Arena trains exactly this gap.")
        steps.append("This pattern is now scheduled for a delayed retest — in disguise.")
        return CoachReply(available=True, questions=[], analysis=text,
                          next_steps=steps, source="offline")

    failed = [t for t in report.tests if not t.passed] if report.tests else []
    evidence = ""
    if failed:
        kinds = {t.kind for t in failed}
        if kinds == {"performance"}:
            evidence = ("Every correctness trial passed and only the large input failed. "
                        "Your algorithm is right; its cost is not. This is a very "
                        "different problem from being wrong, and it is worth saying so "
                        "out loud in a real timed practical.")
        elif kinds == {"edge"}:
            evidence = ("Only the edge trials failed. The main idea is sound — the "
                        "boundaries are not.")
        else:
            evidence = (f"{len(failed)} of {len(report.tests)} trials failed, "
                        f"starting with '{failed[0].name}'.")

    text = " ".join(filter(None, [
        FAILURE_BLURB.get(root, ""), analysis.narrative, evidence,
        _history_note(history),
    ]))

    steps = []
    if root == "INEFFICIENT_ALGORITHM":
        steps.append("Say the complexity of your approach out loud before you write it. "
                     "That habit catches this before the timeout does.")
    if root in ("SYNTAX", "PYTHON_RECALL"):
        steps.append("Python Village drills. Fluency failures are the cheapest kind to "
                     "eliminate and the most expensive to carry into a timed practical.")
    if root == "PATTERN_NOT_RECOGNIZED":
        steps.append("Pattern encounters, where the only task is naming the family. "
                     "Recognition is trainable separately from implementation.")
    if attempts_on_problem >= 3:
        steps.append("You have gone three rounds with this. Phoenix is available — take "
                     "the worked solution, then rebuild it from memory. A Learning "
                     "Clear still advances the story.")
    steps.append("A micro-drill on the root cause has been added to your quest log.")

    return CoachReply(available=True, questions=questions, analysis=text,
                      next_steps=steps, source="offline",
                      reveal_solution=attempts_on_problem >= 3)


def explanation_score(text: str, problem) -> dict:
    """Communication-topic coverage, with explicit unverified reasoning status."""
    from .communication import checklist
    return checklist(text, problem)
