"""Grading, failure analysis, and the rank a battle earns.

Combat feedback never says "WRONG". It says which category of input broke the
spell, because that is the sentence that makes debugging possible.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RANKS = ["S", "A", "B", "C", "LEARNING_CLEAR"]

FAILURE_CATEGORIES = [
    "SYNTAX", "PYTHON_RECALL", "PATTERN_NOT_RECOGNIZED", "WRONG_DATA_STRUCTURE",
    "WRONG_ALGORITHM", "INEFFICIENT_ALGORITHM", "OFF_BY_ONE", "EDGE_CASE",
    "STATE_MANAGEMENT", "MUTABILITY", "RECURSION", "TREE_TRAVERSAL",
    "GRAPH_TRAVERSAL", "DEBUGGING", "COMPLEXITY", "TESTING", "TIME_PRESSURE",
    "COMMUNICATION", "UNKNOWN",
]

FAILURE_BLURB = {
    "SYNTAX": "The spell would not compile.",
    "PYTHON_RECALL": "You knew the algorithm; the Python got in the way.",
    "PATTERN_NOT_RECOGNIZED": "The wrong family of spell was chosen.",
    "WRONG_DATA_STRUCTURE": "The structure you reached for cannot answer this cheaply.",
    "WRONG_ALGORITHM": "The approach does not compute what was asked.",
    "INEFFICIENT_ALGORITHM": "Correct, but too slow to survive the real input.",
    "OFF_BY_ONE": "A boundary is one step out of place.",
    "EDGE_CASE": "It works on the ordinary case and breaks on the unusual one.",
    "STATE_MANAGEMENT": "A variable is being reset, kept, or shared at the wrong moment.",
    "MUTABILITY": "Something was mutated that should not have been.",
    "RECURSION": "The base case or the shrinking step is wrong.",
    "TREE_TRAVERSAL": "The node relationships are not being visited correctly.",
    "GRAPH_TRAVERSAL": "Visited-state or frontier handling is wrong.",
    "DEBUGGING": "The defect was not located.",
    "COMPLEXITY": "The cost of the approach was misjudged.",
    "TESTING": "The test suite did not probe the failure.",
    "TIME_PRESSURE": "Correct, but not within the time the interview allows.",
    "COMMUNICATION": "The explanation did not match the implementation.",
    "UNKNOWN": "Something went wrong that we could not classify.",
}

# Category -> the skill that most needs work. Feeds Training Camp routing.
CATEGORY_TO_SKILL = {
    "SYNTAX": "PYTHON", "PYTHON_RECALL": "PYTHON",
    "PATTERN_NOT_RECOGNIZED": "RECALL", "WRONG_DATA_STRUCTURE": "HASH_MAP",
    "INEFFICIENT_ALGORITHM": "BIG_O", "OFF_BY_ONE": "DEBUGGING",
    "EDGE_CASE": "TESTING", "STATE_MANAGEMENT": "DEBUGGING",
    "MUTABILITY": "PYTHON", "RECURSION": "RECURSION",
    "TREE_TRAVERSAL": "TREE", "GRAPH_TRAVERSAL": "GRAPH",
    "DEBUGGING": "DEBUGGING", "COMPLEXITY": "BIG_O", "TESTING": "TESTING",
    "TIME_PRESSURE": "SPEED", "COMMUNICATION": "COMMUNICATION",
}

_EXC_TO_CATEGORY = {
    "IndexError": "OFF_BY_ONE",
    "KeyError": "STATE_MANAGEMENT",
    "TypeError": "PYTHON_RECALL",
    "ValueError": "EDGE_CASE",
    "AttributeError": "PYTHON_RECALL",
    "ZeroDivisionError": "EDGE_CASE",
    "RecursionError": "RECURSION",
    "NameError": "PYTHON_RECALL",
    "UnboundLocalError": "STATE_MANAGEMENT",
    "StopIteration": "STATE_MANAGEMENT",
    "MemoryError": "INEFFICIENT_ALGORITHM",
}


@dataclass
class Analysis:
    root_cause: str = "UNKNOWN"
    categories: list = field(default_factory=list)
    narrative: str = ""
    failing_kind: str = ""
    hint_pointer: str = ""


def _describe_failure(test) -> str:
    """Say what class of input broke, never the expected output. The player has
    to be left something to debug."""
    name = (test.name or "").lower()
    if test.status == "timeout":
        return "Your spell works, but it is too slow — the enemy outlasts it."
    if test.status == "exception":
        return f"Your spell raised {test.message.split(':')[0]} on a hidden input."
    for needle, phrase in (
        ("empty", "The enemy survives when the input is empty."),
        ("single", "It breaks on an input with exactly one element."),
        ("duplicate", "Your spell breaks when duplicate values appear."),
        ("dupe", "Your spell breaks when duplicate values appear."),
        ("negative", "It fails once negative values are involved."),
        ("zero", "Zero is not handled the way the seal expects."),
        ("k zero", "A limit of zero is not handled."),
        ("boundary", "The boundary case is off."),
        ("large", "It holds on small inputs and collapses on large ones."),
        ("exceed", "It fails when the parameter exceeds the input size."),
    ):
        if needle in name:
            return phrase
    if test.hidden:
        return "A hidden trial found an input your spell mishandles."
    return "The visible trial did not produce the expected result."


def analyse(report, problem, *, hints_used: int, seconds: float,
            declared_pattern: str | None = None) -> Analysis:
    """Identify the FIRST CAUSAL failure, not merely the last symptom."""
    categories: list = []

    if report.phase == "syntax":
        return Analysis(root_cause="SYNTAX", categories=["SYNTAX"],
                        narrative="The spell would not compile. "
                                  + (report.error or {}).get("message", ""),
                        failing_kind="syntax",
                        hint_pointer="Python Village: syntax drills")

    if report.phase in ("toplevel", "infra"):
        exc = (report.error or {}).get("type", "")
        cat = _EXC_TO_CATEGORY.get(exc, "PYTHON_RECALL")
        if exc == "Timeout":
            cat = "INEFFICIENT_ALGORITHM"
        return Analysis(root_cause=cat, categories=[cat],
                        narrative=(report.error or {}).get("message", "It did not run."),
                        failing_kind="toplevel")

    failures = [t for t in report.tests if not t.passed]
    if not failures:
        if seconds > problem.target_seconds * 1.75:
            return Analysis(root_cause="TIME_PRESSURE", categories=["TIME_PRESSURE"],
                            narrative="Correct — but well over the target time.",
                            failing_kind="slow")
        return Analysis(root_cause="", categories=[], narrative="Flawless.",
                        failing_kind="")

    first = failures[0]
    perf_failures = [t for t in failures if t.kind == "performance"]
    edge_failures = [t for t in failures if t.kind == "edge"]

    if perf_failures and len(perf_failures) == len(failures):
        categories.append("INEFFICIENT_ALGORITHM")
        root = "INEFFICIENT_ALGORITHM"
        narrative = ("Every correctness trial passed. Only the large input defeated "
                     "you — the algorithm is right, its cost is not.")
    elif first.status == "timeout":
        categories.append("INEFFICIENT_ALGORITHM")
        root = "INEFFICIENT_ALGORITHM"
        narrative = _describe_failure(first)
    elif first.status == "exception":
        exc = getattr(first, "exc_type", None) or first.message.split(":")[0].strip()
        root = _EXC_TO_CATEGORY.get(exc, "PYTHON_RECALL")
        categories.append(root)
        narrative = _describe_failure(first)
    elif edge_failures and len(edge_failures) == len(failures):
        root = "EDGE_CASE"
        categories.append("EDGE_CASE")
        narrative = _describe_failure(edge_failures[0])
    elif len(failures) == len(report.tests):
        # Nothing passed at all: the approach itself is wrong, not a detail.
        root = "WRONG_ALGORITHM"
        categories.append("WRONG_ALGORITHM")
        narrative = ("Nothing passed, including the simplest trial. This is not a "
                     "small slip — the approach itself is not computing what was asked.")
    else:
        root = "OFF_BY_ONE" if len(failures) <= 2 else "WRONG_ALGORITHM"
        categories.append(root)
        narrative = _describe_failure(first)

    if declared_pattern and declared_pattern != problem.pattern:
        categories.insert(0, "PATTERN_NOT_RECOGNIZED")
        root = "PATTERN_NOT_RECOGNIZED"
        narrative = (f"You named the family as {declared_pattern}. That choice sent the "
                     "implementation down the wrong road before the first line was "
                     "written.") + " " + narrative

    if hints_used >= 4 and root not in ("SYNTAX",):
        categories.append("PATTERN_NOT_RECOGNIZED")

    return Analysis(root_cause=root, categories=categories, narrative=narrative,
                    failing_kind=first.kind,
                    hint_pointer=FAILURE_BLURB.get(root, ""))


def rank_for(*, solved: bool, hints_used: int, seconds: float,
             target_seconds: float, used_phoenix: bool, first_try: bool) -> str:
    if not solved:
        return ""
    if used_phoenix:
        return "LEARNING_CLEAR"
    if hints_used == 0 and seconds <= target_seconds and first_try:
        return "S"
    if hints_used == 0:
        return "S" if seconds <= target_seconds * 1.4 else "A"
    if hints_used <= 2:
        return "A" if hints_used == 1 else "B"
    return "C"


def xp_for(*, difficulty: str, rank: str, combo: float, is_retest: bool) -> int:
    base = {"TUTORIAL": 12, "EASY": 25, "MEDIUM": 60, "HARD": 110,
            "ELITE": 140, "BOSS": 200}.get(difficulty, 25)
    rank_mult = {"S": 1.6, "A": 1.3, "B": 1.0, "C": 0.75,
                 "LEARNING_CLEAR": 0.5}.get(rank, 0.4)
    retest_mult = 1.35 if is_retest else 1.0
    return int(round(base * rank_mult * combo * retest_mult))


def combo_multiplier(streak: int) -> float:
    if streak >= 10:
        return 1.5
    if streak >= 5:
        return 1.25
    if streak >= 3:
        return 1.1
    return 1.0


def battle_feedback(report, problem) -> dict:
    """Turn a test report into combat language plus honest damage numbers."""
    total = max(len(report.tests), 1)
    passed = report.passed_count
    visible = [t for t in report.tests if not t.hidden]
    hidden = [t for t in report.tests if t.hidden]
    lines = []

    for t in visible:
        lines.append({
            "name": t.name, "status": t.status, "hidden": False, "ms": t.ms,
            "message": t.message,
            "got": t.got if t.status == "fail" else None,
            "expected": t.expected if t.status == "fail" else None,
        })
    for t in hidden:
        # Hidden trials never reveal the expected value — only the category.
        lines.append({
            "name": "hidden trial" if not t.reveal else t.name,
            "status": t.status, "hidden": True, "ms": t.ms,
            "message": _describe_failure(t) if not t.passed else "",
            "got": None, "expected": None,
        })

    return {
        "damage": passed,
        "enemy_hp_total": total,
        "passed": passed,
        "total": total,
        "cleared": passed == total,
        "lines": lines,
        "slowest_ms": report.slowest_ms,
    }
