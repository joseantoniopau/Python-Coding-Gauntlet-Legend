"""The Trial of the Architect — the opening diagnostic, disguised as a game.

The specification asks for a baseline assessment that is "integrated into gameplay
rather than a boring test". This is it: five short encounters framed as the
Architect proving they are worth training, which quietly establish where on the
chapter ladder to start.

The design constraint that matters: a diagnostic must be able to place a player
UP as well as down. Someone who already writes fluent Python should not be made to
sit through eighteen guided drills to prove it, and someone who freezes at a blank
screen should never be shown a tree. The trial answers that question in about four
minutes, and it is skippable — a skip simply starts you at the beginning, which is
the safe default.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from . import curriculum

# ---------------------------------------------------------------------------
# The five trials
# ---------------------------------------------------------------------------
#
# Each probes one thing, in rising order, and each is answerable in under a
# minute by someone who has the skill. They are deliberately NOT graded on speed:
# this is calibration, not a filter.

@dataclass
class Trial:
    id: str
    probes: str                  # what it measures, shown to the player afterwards
    kind: str                    # "mcq" | "code"
    prompt: str
    code: str = ""
    choices: tuple = ()
    answer: int = -1
    fn_name: str = ""
    starter: str = ""
    tests: tuple = ()
    weight_skill: str = "PYTHON"
    narration: str = ""


TRIALS: tuple = (
    Trial(
        id="t1-read",
        probes="Reading Python",
        kind="mcq",
        narration="The Archivist sets a slate in front of you. \"Before I teach you "
                  "anything, I need to know what you already see.\"",
        prompt="What does this print?",
        code="counts = {}\n"
             "for ch in 'hello':\n"
             "    counts[ch] = counts.get(ch, 0) + 1\n"
             "print(counts['l'])",
        choices=("2", "1", "0", "It raises KeyError"),
        answer=0,
        weight_skill="PYTHON",
    ),
    Trial(
        id="t2-write",
        probes="Writing Python from a blank screen",
        kind="code",
        narration="\"Now the other direction. Say it yourself.\"",
        prompt="Return the number of items in `values` that are greater than zero.",
        fn_name="count_positive",
        starter="def count_positive(values):\n    # your turn\n    pass\n",
        tests=(
            ("mixed", ([-1, 2, 3],), 2),
            ("none", ([-1, -2],), 0),
            ("empty", ([],), 0),
        ),
        weight_skill="PYTHON",
    ),
    Trial(
        id="t3-structure",
        probes="Choosing a data structure",
        kind="mcq",
        narration="\"A question with no code in it at all.\"",
        prompt="You must repeatedly ask \"have I seen this value before?\" over a "
               "stream of a million values. Which structure?",
        choices=("A set", "A list", "A sorted list with binary search",
                 "A string you keep appending to"),
        answer=0,
        weight_skill="HASH_MAP",
    ),
    Trial(
        id="t4-pattern",
        probes="Recognising an algorithm family",
        kind="mcq",
        narration="\"And now the thing most people get wrong before they write a "
                  "single line.\"",
        prompt="\"Find the longest contiguous stretch containing at most K distinct "
               "values.\" Which family is this?",
        choices=("Sliding window", "Binary search", "Dynamic programming",
                 "Depth-first search"),
        answer=0,
        weight_skill="SLIDING_WINDOW",
    ),
    Trial(
        id="t5-complexity",
        probes="Reasoning about cost",
        kind="mcq",
        narration="\"Last one. This is the question you will be asked out loud.\"",
        prompt="What is the time complexity of this function?",
        code="def first_unique(s):\n"
             "    for i, ch in enumerate(s):\n"
             "        if s.count(ch) == 1:\n"
             "            return i\n"
             "    return -1",
        choices=("O(n^2)", "O(n)", "O(n log n)", "O(1)"),
        answer=0,
        weight_skill="BIG_O",
    ),
)

TRIAL_BY_ID = {t.id: t for t in TRIALS}


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

@dataclass
class Placement:
    chapter_index: int
    chapter_title: str
    seed_mastery: dict = field(default_factory=dict)
    verdict: str = ""
    detail: list = field(default_factory=list)
    score: int = 0
    # Did the player write working code from a blank screen, here, in the real
    # sandbox, against real tests? That single fact is what the whole scaffold
    # band at the bottom of the ramp exists to establish, so it is recorded
    # rather than re-derived — see seed_skills.
    produced_code: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _verdict_for(score: int, wrote_code: bool) -> tuple:
    """(chapter index, prose). Placement is deliberately conservative: when in
    doubt it starts you lower, because being under-challenged for twenty minutes
    is recoverable and being over-faced on day one is not."""
    if score >= 5 and wrote_code:
        return 3, ("You read Python, you write it, you name the structure, you "
                   "recognise the family and you can price it. You do not need the "
                   "alphabet. We start at Counting and Membership — the pattern that "
                   "carries more interview questions than any other.")
    if score >= 4 and wrote_code:
        return 2, ("Strong reading, and you can produce code unaided. What is missing "
                   "is idiom and speed, not understanding. We start at the Idioms.")
    if score >= 3 and wrote_code:
        return 1, ("You can read it and you can write something that works. The gap "
                   "is knowing which structure to reach for before you start typing. "
                   "We start at the Four Vaults.")
    if wrote_code:
        return 1, ("You got working code onto the screen, which is further than most "
                   "people start. The patterns are unfamiliar and that is exactly what "
                   "this is for. We start at the Four Vaults.")
    if score >= 3:
        return 0, ("You read code well and reason about it well — that much is "
                   "obvious. The blank screen is the problem, and it is the most "
                   "fixable problem there is. We start at the beginning, and we will "
                   "move quickly.")
    return 0, ("We start at the beginning. Not because you lack judgement — you "
               "clearly have it — but because fluency is built, not recalled, and "
               "there is no shortcut worth taking here.")


# Mastery seeded per correct trial. Small on purpose: a diagnostic is weak evidence
# compared with a solved problem, and seeding too much would let someone skip a
# chapter they have not actually earned.
SEED_PER_CORRECT = {
    "PYTHON": 9.0,
    "HASH_MAP": 7.0,
    "SLIDING_WINDOW": 6.0,
    "BIG_O": 7.0,
    "RECALL": 5.0,
}


def evaluate(answers: dict) -> Placement:
    """`answers` maps trial id -> {"correct": bool}. Returns a placement."""
    score = 0
    detail = []
    seed: dict = {}

    for trial in TRIALS:
        result = answers.get(trial.id) or {}
        correct = bool(result.get("correct"))
        score += int(correct)
        detail.append({
            "id": trial.id,
            "probes": trial.probes,
            "correct": correct,
            "note": _note_for(trial, correct),
        })
        if correct:
            gain = SEED_PER_CORRECT.get(trial.weight_skill, 5.0)
            seed[trial.weight_skill] = seed.get(trial.weight_skill, 0.0) + gain
            if trial.kind == "mcq":
                seed["RECALL"] = seed.get("RECALL", 0.0) + 3.0

    wrote_code = bool((answers.get("t2-write") or {}).get("correct"))
    index, verdict = _verdict_for(score, wrote_code)
    return Placement(
        chapter_index=index,
        chapter_title=curriculum.CHAPTERS[index].title,
        seed_mastery=seed,
        verdict=verdict,
        detail=detail,
        score=score,
        produced_code=wrote_code,
    )


def _note_for(trial: Trial, correct: bool) -> str:
    if correct:
        return {
            "t1-read": "You read dictionary mutation correctly.",
            "t2-write": "You produced working code unaided. That is the skill this "
                        "whole game exists to make automatic.",
            "t3-structure": "You reached for the right structure without being "
                            "prompted.",
            "t4-pattern": "You named the family. Recognition is half of every "
                          "interview question.",
            "t5-complexity": "You spotted the hidden quadratic. Most people miss it "
                             "because the loop looks linear.",
        }.get(trial.id, "Correct.")
    return {
        "t1-read": "`.get(ch, 0) + 1` is the safe-increment idiom — we will drill it "
                   "until it is muscle memory.",
        "t2-write": "This is the gap, and it is the one worth closing. Everything "
                    "early in the game is built to close it.",
        "t3-structure": "Membership at scale is always a set. We start there.",
        "t4-pattern": "Contiguous, plus a constraint that can be broken and repaired, "
                      "is the sliding-window signature. You will learn to hear it.",
        "t5-complexity": "`s.count(ch)` is itself O(n), called once per character. "
                         "Hidden quadratics are their own chapter.",
    }.get(trial.id, "Not this time.")


def skip_placement() -> Placement:
    """Skipping is always allowed, and always safe: it starts you at chapter one."""
    return Placement(
        chapter_index=0,
        chapter_title=curriculum.CHAPTERS[0].title,
        seed_mastery={},
        verdict="Skipped. We start at the beginning, which is never the wrong answer.",
        detail=[],
        score=0,
    )


def seed_skills(skills: dict, placement: Placement) -> dict:
    """Apply the placement's seed mastery, and its one piece of hard evidence.

    This is the one place mastery moves without a graded attempt, and it is
    deliberately bounded: confidence stays low, so the readiness model continues
    to treat these numbers as weak evidence until real solves back them up.

    THE WRITING TRIAL IS NOT IN THAT CATEGORY. Four of the five trials are
    multiple choice and seed nothing but mastery, because picking the right
    answer out of four is exactly as weak as it looks. `t2-write` is a different
    animal: the player is handed `def count_positive(values): pass` and their
    code is run in the same sandbox as every other encounter, against three
    tests, with no hints available. That is an unaided clear on a blank screen —
    a real one, of EASY shape — and it is recorded as precisely that and nothing
    more. One clear, one attempt, one unaided clear, at one tier.

    It matters because it is the single fact the scaffold band turns on
    (curriculum.scaffold_target). Without it a fluent player is walked through
    the beginner chain; with it inflated, a beginner is dropped on a blank
    screen. One is what happened, so one is what gets written down.
    """
    for name, gain in placement.seed_mastery.items():
        state = skills.get(name)
        if state is None:
            continue
        state.mastery = min(35.0, state.mastery + gain)
        state.confidence = min(state.confidence, 18.0)
    if placement.produced_code:
        state = skills.get("PYTHON")
        if state is not None:
            state.attempts += 1
            state.clears += 1
            state.unaided_clears += 1
            tier = curriculum.PRODUCTION_TIER
            state.tier_clears[tier] = state.tier_clears.get(tier, 0) + 1
            state.tier_unaided[tier] = state.tier_unaided.get(tier, 0) + 1
            state.confidence = min(state.confidence, 18.0)
    return skills
