"""The adaptive learning engine: what should this player face next, and why.

Two rules govern everything here:

1. Difficulty rises on *evidence*, never on time spent playing.
2. Nobody ever dead-ends. If the player cannot progress, the engine's job is to
   find the prerequisite they are actually missing and route them to it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import curriculum
from . import puzzles
from . import skills as skillmod
from . import srs, world
from .config import SRS_INTERVALS_DAYS

DIFF_ORDER = ["GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS"]

# Variety targets. The six puzzle kinds exist because every encounter being
# "type a function" was both the hardest interaction for this player and the
# dullest. They are a change of pace, not the main course: roughly one encounter
# in four, mixed through the code battles rather than served in a block.
PUZZLE_SHARE = 0.25
VARIETY_WINDOW = 12
VARIETY_SEED = 4

# The puzzle families weight themselves toward this player's profile, which is
# right for choosing WHICH puzzle and a standing thumb on the scale for choosing
# WHETHER — it held the mix near a third. Paid back here so the share above is
# what actually decides, and measured rather than guessed: it is the gap between
# `2.0 * profile_weight` at their weighting and at the default.
PUZZLE_PROFILE_EDGE = 2.0

# Variety was steered for the puzzle GROUP and for nothing else, so the two
# largest families in the corpus — CODE_BATTLE and MISSING_RUNE — could and did
# take 46 of 60 encounters while nine kinds were never served at all. This
# spreads the same pressure across every kind: a kind over its fair share is
# pushed down, a kind that has not appeared is pulled up.
#
# KIND_SPREAD is set so the whole term stays inside one difficulty tier (5.0
# per step, below). Wanting a change of pace must never outrank what the
# curriculum has opened or what the player is ready for.
KIND_WINDOW = 24
KIND_SEED = 8              # denominator floor, so a short history is not evidence
KIND_FAIR_SHARE = 0.125    # twenty-four encounters should touch about eight kinds
KIND_SPREAD = 18.0
# Every variety term together is capped so that the SPREAD between any two
# candidates stays under one difficulty tier (5.0 per step, below) — which is
# what "worth less than one tier" has to mean if it is to hold. Uncapped, a kind
# served eight times running scored -15.75 against a starved one's +2.25, and
# that 18-point gap is three tiers of pull: enough for a change of pace to
# outrank what the player is actually ready for, which it did.
VARIETY_CAP = 2.4

# The share term above reshapes the mix but cannot cross a difficulty tier, and
# a kind whose only candidates sit one tier up therefore still never arrives —
# which is how BREAK_IT, COMPLEXITY_MATCH, PATTERN_ENCOUNTER and CODE_READING
# were all served zero times despite being unlocked. This is the explicit floor
# instead: any twenty consecutive encounters contain at least this many distinct
# kinds, and when they do not, the next encounter is one of the missing ones.
#
# The substitution is bounded twice over. It only ever chooses from the pool the
# curriculum has ALREADY opened, and only material within one difficulty tier of
# the player's target — so it cannot unlock anything and cannot skip a rung.
KIND_FLOOR_WINDOW = 20
KIND_FLOOR = 8
KIND_FLOOR_MAX_TIERS = 1

# --- within-session repetition ------------------------------------------------
# The SRS minimum interval is one day, so a first session contained no repetition
# whatsoever — 60 encounters, 60 distinct problems, nothing due. That is the
# opposite of the design. A family cleared earlier TODAY comes back today, in a
# different problem, after enough other work has passed to make it recall rather
# than a re-read.
SESSION_ECHO_GAP = 3       # encounters that must pass before a family returns
SESSION_ECHO_LIMIT = 2     # a family is met once and comes back once
SESSION_ECHO_BONUS = 40.0  # enough to beat the -45 "already solved" penalty
SESSION_ECHO_REACH = 8     # the gap at which the echo is worth full value

PROFILE_PATTERN_WEIGHT = {
    "PRACTICAL": {
        "ARRAY": 3.0, "STRING": 3.0, "HASH_MAP": 3.0, "SET": 2.5, "SORTING": 2.0,
        "SLIDING_WINDOW": 3.0, "TWO_POINTER": 3.0, "MATRIX": 2.5, "TREE": 2.5,
        "RECURSION": 2.5, "BFS": 2.5, "DFS": 2.5, "DESIGN": 2.5,
        "DEBUGGING": 2.0, "COMPLEXITY": 2.0, "TESTING": 2.0, "SIMULATION": 2.0,
        "PREFIX_SUM": 1.5, "HEAP": 1.5, "BINARY_SEARCH": 1.5, "DP": 1.5,
        "STACK": 1.5, "QUEUE": 1.5, "INTERVALS": 1.5, "GREEDY": 1.0,
        "RECOGNITION": 2.0,
    },
    "GENERAL_SWE": {p: 2.0 for p in skillmod.PATTERN_TO_SKILL},
    "SECURITY_ENGINEERING": {
        "HASH_MAP": 3.0, "SET": 3.0, "SLIDING_WINDOW": 3.0, "BFS": 2.5, "DFS": 2.5,
        "QUEUE": 2.5, "STACK": 2.0, "MATRIX": 2.0, "DESIGN": 2.5, "STRING": 2.0,
        "ARRAY": 2.0, "SORTING": 2.0, "DEBUGGING": 2.5, "TREE": 1.5,
        "RECURSION": 1.5, "DP": 1.0, "COMPLEXITY": 1.5, "TESTING": 2.0,
        "RECOGNITION": 2.0,
    },
    "CUSTOM": {},
}

# Training Camp: what a root cause routes you to.
CAMPS = {
    "SYNTAX": {"region": "python_village", "skill": "PYTHON",
               "name": "Syntax Drill", "mentor": "byte"},
    "PYTHON_RECALL": {"region": "python_village", "skill": "PYTHON",
                      "name": "Recall Drill", "mentor": "byte"},
    "WRONG_DATA_STRUCTURE": {"region": "hashmap_highlands", "skill": "HASH_MAP",
                             "name": "Hashmap Training Camp", "mentor": "archivist"},
    "PATTERN_NOT_RECOGNIZED": {"region": "fields_of_syntax", "skill": "RECALL",
                               "name": "Recognition Camp", "mentor": "scribe"},
    "INEFFICIENT_ALGORITHM": {"region": "complexity_tower", "skill": "BIG_O",
                              "name": "Complexity Tower", "mentor": "oracle"},
    "OFF_BY_ONE": {"region": "debugging_dungeon", "skill": "DEBUGGING",
                   "name": "Armorer's Forge", "mentor": "armorer"},
    "EDGE_CASE": {"region": "debugging_dungeon", "skill": "TESTING",
                  "name": "Testsmith Forge", "mentor": "testsmith"},
    "STATE_MANAGEMENT": {"region": "debugging_dungeon", "skill": "DEBUGGING",
                         "name": "Armorer's Forge", "mentor": "armorer"},
    "MUTABILITY": {"region": "python_village", "skill": "PYTHON",
                   "name": "Mutation Drill", "mentor": "byte"},
    "RECURSION": {"region": "recursive_forest", "skill": "RECURSION",
                  "name": "Recursive Forest Camp", "mentor": "druid"},
    "TREE_TRAVERSAL": {"region": "binary_tree_canopy", "skill": "TREE",
                       "name": "Canopy Camp", "mentor": "druid"},
    "GRAPH_TRAVERSAL": {"region": "graph_wastes", "skill": "GRAPH",
                        "name": "Cartographer's Camp", "mentor": "cartographer"},
    "WRONG_ALGORITHM": {"region": "fields_of_syntax", "skill": "RECALL",
                        "name": "Recognition Camp", "mentor": "scribe"},
    "TIME_PRESSURE": {"region": "coding_coliseum", "skill": "SPEED",
                      "name": "Chronomancer's Arena", "mentor": "chronomancer"},
    "COMPLEXITY": {"region": "complexity_tower", "skill": "BIG_O",
                   "name": "Complexity Tower", "mentor": "oracle"},
    "TESTING": {"region": "debugging_dungeon", "skill": "TESTING",
                "name": "Testsmith Forge", "mentor": "testsmith"},
    "DEBUGGING": {"region": "debugging_dungeon", "skill": "DEBUGGING",
                  "name": "Armorer's Forge", "mentor": "armorer"},
    "COMMUNICATION": {"region": "python_village", "skill": "COMMUNICATION",
                      "name": "The Scribe's Table", "mentor": "scribe"},
}


@dataclass
class Selection:
    problem: object
    reason: str
    is_retest: bool = False
    interval_days: float = 0.0
    encounter_kind: str = "CODE_BATTLE"
    tags: list = field(default_factory=list)


def _difficulty_target(state, fluency=None) -> str:
    """Where this skill should be pitched right now.

    A skill with no evidence at all starts on the scaffold rungs, not on a blank
    screen: GUIDED hands the player complete code with a blank in it. The band is
    narrow on purpose — it is an on-ramp, not a destination — and it ends where
    the EASY tier gate opens, so targeting and unlocking agree.
    """
    if state is None or state.attempts == 0:
        # An unfamiliar pattern still starts gently — but not from zero for someone
        # who already writes fluent Python. General fluency raises the floor, so a
        # capable player meeting their first graph problem gets a skeleton rather
        # than a fill-in-the-blank.
        if fluency is not None and fluency.mastery >= 55:
            return "EASY"
        if fluency is not None and fluency.mastery >= 30:
            return "TUTORIAL"
        return "GUIDED"
    m = state.mastery
    if m < 10:
        return "GUIDED"
    if m < 18:
        return "TUTORIAL"
    if m < 42:
        return "EASY"
    if m < 68:
        return "MEDIUM"
    if m < 85:
        return "HARD"
    return "ELITE"


def _difficulty_distance(problem_difficulty: str, target: str) -> int:
    try:
        return abs(DIFF_ORDER.index(problem_difficulty) - DIFF_ORDER.index(target))
    except ValueError:
        return 3


def _variety_bonus(problem, recent_kinds: list) -> float:
    """Steer the SHAPE of the sequence, not the quality of one problem.

    Everything on the opening rungs scores identically, and Python's sort is
    stable, so before this term existed every tie was won by whichever family
    happened to be built first. That served fourteen fill-in-the-blanks in a row
    and put exactly one rune assembly in sixty encounters — the monotony the six
    puzzle kinds were written to end.

    Every term here is worth less than one difficulty tier (5.0 per step, below).
    Wanting a change of pace must never be able to drag in material the
    curriculum has not opened or the player is not ready for.
    """
    kind = problem.encounter_kind
    window = list(recent_kinds[:VARIETY_WINDOW])
    bonus = 0.0

    if kind in puzzles.PUZZLE_KINDS:
        # A one-encounter history is not evidence of a 100% puzzle diet, so the
        # denominator never falls below a handful. It reaches the true window
        # size as soon as there is a real history to measure.
        seen = max(len(window), VARIETY_SEED)
        share = sum(1 for k in window if k in puzzles.PUZZLE_KINDS) / seen
        # Below the target this pulls puzzles in, above it pushes them back out,
        # so the sequence settles at the target rather than at either extreme.
        bonus += 12.0 * (PUZZLE_SHARE - share) - PUZZLE_PROFILE_EDGE
        if window[:1] and window[0] in puzzles.PUZZLE_KINDS:
            bonus -= 3.0          # a change of pace, not a second mode

    # Whatever just happened is the least interesting thing to do again. This is
    # what keeps the mix interleaved instead of arriving in blocks.
    if window[:1] == [kind]:
        bonus -= 3.0
    if len(window) > 1 and window[1] == kind:
        bonus -= 1.5

    # The same pressure, applied to every kind rather than to the puzzle group
    # alone. This is the term that ends a 24-in-a-row run of one encounter kind.
    wide = list(recent_kinds[:KIND_WINDOW])
    share = sum(1 for k in wide if k == kind) / max(len(wide), KIND_SEED)
    bonus += KIND_SPREAD * (KIND_FAIR_SHARE - share)
    return max(-VARIETY_CAP, min(VARIETY_CAP, bonus))


def _starved_kind(scored: list, recent_kinds: list, skills: dict,
                  recent_ids: list) -> object | None:
    """The best-scoring encounter of a kind the recent window is missing.

    Returns None unless the window is both full and genuinely narrow, so this
    never fires early and never fires when the mix is already varied.
    """
    window = list(recent_kinds[:KIND_FLOOR_WINDOW])
    if len(window) < KIND_FLOOR_WINDOW:
        return None
    seen = set(window)
    available = {p.encounter_kind for _, p in scored}
    # is_permitted() and permitted_patterns() do not agree on every problem, and
    # the second is the one the ramp tests read, so the floor honours both — a
    # variety pick must never be the one thing that walks past a chapter gate.
    allowed = curriculum.permitted_patterns(skills)
    if len(seen) >= min(KIND_FLOOR, len(available)):
        return None
    blocked = set(recent_ids[:12])
    for _, problem in scored:                  # already sorted best-first
        if problem.encounter_kind in seen or problem.id in blocked:
            continue
        if allowed and problem.pattern not in allowed:
            continue
        state = skills.get(
            skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"))
        target = _difficulty_target(state, skills.get("PYTHON"))
        if _difficulty_distance(problem.difficulty, target) > KIND_FLOOR_MAX_TIERS:
            continue
        return problem
    return None


def _session_echo(problem, session: list) -> float:
    """Bring back, later in the same sitting, a family cleared earlier in it.

    Interleaved recall inside one session is the single highest-value thing the
    selector can do and it was not happening at all. The rules are narrow on
    purpose: a DIFFERENT problem in the same family, only after enough other
    work has passed for it to be recall, and only a few times before the family
    is left alone and the spaced-repetition schedule takes over tomorrow.
    """
    if not session:
        return 0.0
    family = problem.spaced_repetition_family
    if not family:
        return 0.0
    rows = [i for i, row in enumerate(session)
            if row.get("family") == family and row.get("solved")]
    if not rows or len(rows) >= SESSION_ECHO_LIMIT:
        return 0.0
    if any(session[i].get("id") == problem.id for i in rows):
        return 0.0                     # the same problem again is a re-read
    since = len(session) - 1 - rows[-1]
    if since < SESSION_ECHO_GAP:
        return 0.0                     # too soon: it is still on the screen
    reach = max(1, SESSION_ECHO_REACH - SESSION_ECHO_GAP)
    return SESSION_ECHO_BONUS * min(1.0, (since - SESSION_ECHO_GAP + 1) / reach)


def score_problem(problem, *, skills: dict, profile: str, solved_ids: set,
                  recent_ids: list, region: str | None, now: float,
                  recent_kinds: list = (), session: list = ()) -> float:
    """Higher is a better next encounter. This is the whole selection policy."""
    skill_name = skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
    state = skills.get(skill_name)
    score = 0.0

    weights = PROFILE_PATTERN_WEIGHT.get(profile) or PROFILE_PATTERN_WEIGHT["GENERAL_SWE"]
    score += 4.0 * weights.get(problem.pattern, 1.0)
    score += 2.0 * problem.profile_weight.get(profile, 1.0)

    target = _difficulty_target(state, skills.get("PYTHON"))
    score -= 5.0 * _difficulty_distance(problem.difficulty, target)

    if state is not None:
        # Weakness attracts work, but only where we have evidence of weakness.
        if state.attempts:
            score += (100 - state.mastery) * 0.06
            score += state.error_rate * 0.04
            score += state.hint_dependence * 0.03
        else:
            score += 6.0                     # unexplored skills are worth probing

    if problem.id in solved_ids:
        score -= 45.0                        # strongly prefer unseen material
    if problem.id in recent_ids[:12]:
        score -= 60.0                        # never repeat what was just played
    if region and problem.realm == region:
        score += 12.0
    if problem.difficulty == "BOSS":
        score -= 25.0                        # bosses are entered deliberately
    if problem.encounter_kind in ("PATTERN_ENCOUNTER", "COMPLEXITY_DUEL",
                                  "CODE_READING", "EDGE_CASE_TRAP"):
        score -= 6.0                         # spice, not the main course
    # The six graded puzzle kinds are NOT spiced down with those. They are graded
    # by running real Python or by an exact structural match, they carry full
    # hint trees, and they move mastery — they are encounters, not flavour. Their
    # share is steered instead, so they arrive mixed in rather than never.
    score += _variety_bonus(problem, list(recent_kinds))
    # Deliberately added AFTER the solved/recent penalties rather than folded
    # into them: an echo is meant to overcome "you have seen this family", which
    # is exactly what those penalties say.
    score += _session_echo(problem, list(session))
    return score


def select_next(corpus: list, *, skills: dict, schedule: dict, profile: str,
                solved_ids: set, recent_ids: list, region: str | None = None,
                now: float | None = None, allow_retest: bool = True,
                recent_kinds: list | None = None,
                session: list | None = None) -> Selection:
    """Retests come first — a due pattern is the highest-value thing we can show.
    Otherwise pick the best-scoring fresh encounter."""
    now = now or time.time()

    if allow_retest:
        for entry in srs.due(schedule, now=now, limit=6):
            candidates = [p for p in corpus
                          if p.spaced_repetition_family == entry.family
                          and p.entry.get("kind") not in ("mcq",)]
            pick = srs.pick_disguised(entry, candidates)
            if pick is not None and pick.id not in recent_ids[:6]:
                days = srs.days_since_review(entry, now=now)
                return Selection(
                    problem=pick, reason="RETEST", is_retest=True,
                    interval_days=days, encounter_kind="MEMORY_AMBUSH",
                    tags=["retest", f"{int(days)}d"])

    # The curriculum gate is a guarantee, not a preference: a pattern or tier the
    # player has not unlocked must not appear at all. Scoring alone only made
    # advanced material unlikely, which is how tree recursion still reached a
    # chapter-one player. Retests above are exempt by design — retention outranks
    # sequencing — and an empty gate falls back to the whole corpus so that a
    # misconfigured chapter can never dead-end the player.
    eligible = [p for p in corpus
                if curriculum.is_permitted(
                    p, skills,
                    skill_state=skills.get(
                        skillmod.PATTERN_TO_SKILL.get(p.pattern, "PYTHON")))]
    if not eligible:
        eligible = corpus

    # The caller knows the whole corpus and can name the kinds it has just
    # served; falling back to this filtered slice is only for direct callers.
    if recent_kinds is None:
        kind_of = {p.id: p.encounter_kind for p in corpus}
        recent_kinds = [kind_of[i] for i in recent_ids if i in kind_of]

    session = list(session or ())
    scored = [(score_problem(p, skills=skills, profile=profile,
                             solved_ids=solved_ids, recent_ids=recent_ids,
                             region=region, now=now, recent_kinds=recent_kinds,
                             session=session), p)
              for p in eligible]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        raise ValueError("empty corpus")
    starved = _starved_kind(scored, list(recent_kinds), skills, recent_ids)
    if starved is not None:
        return Selection(problem=starved, reason="VARIETY",
                         encounter_kind=starved.encounter_kind,
                         tags=["variety", starved.encounter_kind])

    best = scored[0][1]
    # An echo is a different reason than "the best fresh thing", and the client
    # says so out loud — a returning pattern the player is not told is a return
    # reads as the engine repeating itself rather than as deliberate recall.
    if _session_echo(best, session) > 0:
        return Selection(problem=best, reason="SESSION_ECHO",
                         encounter_kind=best.encounter_kind,
                         tags=["echo", best.spaced_repetition_family])
    return Selection(problem=best, reason="ADAPTIVE",
                     encounter_kind=best.encounter_kind)


def training_camp(root_cause: str, skills: dict, failed_skill: str) -> dict:
    """Failure becomes navigation through the learning graph.

    If the player failed a sliding-window problem because their dictionary work
    is weak, do NOT reteach sliding window. Teach the dictionary.
    """
    prereq = skillmod.missing_prerequisite(skills, failed_skill)
    if prereq and prereq != failed_skill:
        camp_skill = prereq
        region = next((r["id"] for r in world.REGIONS if r["skill"] == prereq),
                      "python_village")
        return {
            "skill": camp_skill,
            "region": region,
            "name": f"{prereq.replace('_', ' ').title()} Training Camp",
            "mentor": world.REGION_BY_ID.get(region, {}).get("mentor", "byte"),
            "why": (f"You did not fail because of {failed_skill.replace('_', ' ').lower()}. "
                    f"You failed because {prereq.replace('_', ' ').lower()} is not yet "
                    "automatic — and that pattern is built on top of it."),
            "root_cause": root_cause,
        }

    camp = CAMPS.get(root_cause) or CAMPS["PYTHON_RECALL"]
    return {
        "skill": camp["skill"], "region": camp["region"], "name": camp["name"],
        "mentor": camp["mentor"], "root_cause": root_cause,
        "why": f"The first thing that went wrong was: {root_cause.replace('_', ' ').lower()}.",
    }


def remediation_plan(corpus: list, root_cause: str, problem, skills: dict) -> dict:
    """After every failure: one micro-drill, one related standard problem, one
    delayed variant. Never nothing."""
    camp = training_camp(root_cause, skills,
                         skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"))
    by_id = {p.id: p for p in corpus}

    def find(pred, limit=1):
        return [p for p in corpus if pred(p)][:limit]

    drill = find(lambda p: (p.difficulty == "TUTORIAL"
                            and skillmod.PATTERN_TO_SKILL.get(p.pattern) == camp["skill"]
                            and p.id != problem.id))
    if not drill:
        drill = find(lambda p: p.difficulty == "TUTORIAL" and p.realm == camp["region"])
    if not drill:
        drill = find(lambda p: p.difficulty == "TUTORIAL")

    simpler = find(lambda p: (p.spaced_repetition_family == problem.spaced_repetition_family
                              and p.id != problem.id
                              and DIFF_ORDER.index(p.difficulty)
                              < DIFF_ORDER.index(problem.difficulty)))
    if not simpler:
        simpler = find(lambda p: (p.pattern == problem.pattern and p.id != problem.id
                                  and p.difficulty in ("TUTORIAL", "EASY")))

    delayed = find(lambda p: (p.spaced_repetition_family == problem.spaced_repetition_family
                              and p.id != problem.id
                              and ("disguised" in p.tags
                                   or p.source_type in ("GENERATED_VARIANT",
                                                        "SECURITY_VARIANT"))))
    if not delayed:
        delayed = find(lambda p: (p.pattern == problem.pattern and p.id != problem.id))

    return {
        "camp": camp,
        "immediate": {"id": drill[0].id, "title": drill[0].title,
                      "why": "A micro-drill on the thing that actually broke."}
        if drill else None,
        "next": {"id": simpler[0].id, "title": simpler[0].title,
                 "why": "The same pattern, one rung easier."} if simpler else None,
        "delayed": {"id": delayed[0].id, "title": delayed[0].title,
                    "days": 3,
                    "why": "The same algorithm in disguise, three days from now."}
        if delayed else None,
    }


def daily_quests(*, skills: dict, schedule: dict, corpus: list, profile: str,
                 now: float | None = None) -> list:
    """Personalised to weakness, retention schedule and recent failures."""
    now = now or time.time()
    quests = []

    ready = srs.due(schedule, now=now, limit=5)
    if ready:
        entry = ready[0]
        quests.append({
            "kind": "RETEST", "id": "daily-retest",
            "title": f"{entry.family.replace('_', ' ').title()} is due for retest",
            "detail": f"A pattern you learned {int(srs.days_since_review(entry, now=now))} "
                      "days ago wants proving again — in disguise.",
            "count": min(2, len(ready)), "reward_xp": 60,
        })

    weak = skillmod.weakest(skills, limit=2)
    for name in weak:
        quests.append({
            "kind": "MENTOR", "id": f"daily-weak-{name.lower()}",
            "title": f"{name.replace('_', ' ').title()} training",
            "detail": "Your weakest area with real evidence behind it.",
            "count": 2, "reward_xp": 45,
        })

    python_state = skills.get("PYTHON")
    if python_state is None or python_state.mastery < 70:
        quests.append({
            "kind": "DAILY", "id": "daily-village",
            "title": "Python Village drills",
            "detail": "Three fluency drills. Syntax should cost you nothing.",
            "count": 3, "reward_xp": 30,
        })

    quests.append({
        "kind": "DAILY", "id": "daily-armor",
        "title": "Repair one piece of armour",
        "detail": "The Armorer has a broken program with your name on it.",
        "count": 1, "reward_xp": 35,
    })
    quests.append({
        "kind": "DAILY", "id": "daily-shrine",
        "title": "Visit a Memory Shrine",
        "detail": "Rapid recall. Fifteen seconds per question.",
        "count": 1, "reward_xp": 20,
    })

    speed = skills.get("SPEED")
    if speed and speed.attempts >= 5:
        quests.append({
            "kind": "BOUNTY", "id": "daily-bounty",
            "title": "Beat yesterday's median solve time",
            "detail": "Same knowledge. Less hesitation.",
            "count": 1, "reward_xp": 50,
        })
    return quests[:6]


# --- readiness ---------------------------------------------------------------

READINESS_DIMENSIONS = [
    ("Python Fluency", ["PYTHON"]),
    ("Pattern Recognition", ["RECALL"]),
    ("Algorithms", ["SLIDING_WINDOW", "TWO_POINTER", "BFS", "DFS", "DP",
                    "BINARY_SEARCH", "RECURSION"]),
    ("Data Structures", ["HASH_MAP", "SET", "STACK", "QUEUE", "HEAP", "TREE",
                         "MATRIX", "ARRAY"]),
    ("Debugging", ["DEBUGGING"]),
    ("Complexity", ["BIG_O"]),
    ("Testing", ["TESTING"]),
    ("Speed", ["SPEED"]),
    ("Communication", ["COMMUNICATION"]),
    ("Retention", None),          # computed from the schedule, not a skill
]

GATES = [
    {"id": "python_no_weakness", "label": "No major Python syntax weakness",
     "check": lambda ctx: ctx["skills"]["PYTHON"].mastery >= 65},
    {"id": "easy_independent", "label": "Common Easy problems solved independently",
     "check": lambda ctx: ctx["unaided_easy"] >= 8},
    {"id": "medium_independent", "label": "Representative Mediums solved independently",
     "check": lambda ctx: ctx["unaided_medium"] >= 6},
    {"id": "hashmap_automatic", "label": "Hash-map pattern is automatic",
     "check": lambda ctx: ctx["skills"]["HASH_MAP"].mastery >= 70
     and ctx["skills"]["HASH_MAP"].hint_dependence <= 30},
    {"id": "window_recognized", "label": "Sliding window recognised unprompted",
     "check": lambda ctx: ctx["skills"]["SLIDING_WINDOW"].mastery >= 60},
    {"id": "two_pointer_recognized", "label": "Two-pointer pattern recognised",
     "check": lambda ctx: ctx["skills"]["TWO_POINTER"].mastery >= 60},
    {"id": "traversal_functional", "label": "BFS and DFS basics functional",
     "check": lambda ctx: min(ctx["skills"]["BFS"].mastery,
                              ctx["skills"]["DFS"].mastery) >= 50},
    {"id": "tree_functional", "label": "Tree traversal functional",
     "check": lambda ctx: ctx["skills"]["TREE"].mastery >= 55},
    {"id": "bigo_explained", "label": "Can state and justify Big-O",
     "check": lambda ctx: ctx["skills"]["BIG_O"].mastery >= 60},
    {"id": "edge_tests", "label": "Can produce edge-case tests",
     "check": lambda ctx: ctx["skills"]["TESTING"].mastery >= 50},
    {"id": "debug_under_pressure", "label": "Can debug under pressure",
     "check": lambda ctx: ctx["skills"]["DEBUGGING"].mastery >= 60},
    {"id": "timed_performance", "label": "Performs with a timer running",
     "check": lambda ctx: ctx["skills"]["SPEED"].mastery >= 50
     or ctx["skills"]["SPEED"].speed >= 55},
    {"id": "retention", "label": "Retains major patterns after several days",
     "check": lambda ctx: ctx["retention"] >= 55},
]


def _avg(values: list) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def retention_score(schedule: dict, now: float | None = None) -> float:
    now = now or time.time()
    if not schedule:
        return 0.0
    scores = []
    for entry in schedule.values():
        if entry.reviews == 0:
            continue
        stage_score = 100.0 * entry.stage / max(len(SRS_INTERVALS_DAYS) - 1, 1)
        penalty = min(35.0, entry.lapses * 12.0)
        overdue = srs.overdue_days(entry, now=now)
        stale = min(25.0, overdue * 4.0)
        scores.append(max(0.0, stage_score - penalty - stale))
    return _avg(scores)


def readiness(*, skills: dict, schedule: dict, stats: dict,
              unaided_easy: int = 0, unaided_medium: int = 0,
              now: float | None = None) -> dict:
    ret = retention_score(schedule, now=now)
    dimensions = []
    for label, names in READINESS_DIMENSIONS:
        if names is None:
            dimensions.append({"label": label, "score": round(ret)})
            continue
        vals = []
        for name in names:
            state = skills.get(name)
            if state is None:
                continue
            # Confidence discounts mastery we have little evidence for.
            vals.append(state.mastery * (0.55 + 0.45 * state.confidence / 100.0))
        dimensions.append({"label": label, "score": round(_avg(vals))})

    ctx = {"skills": skills, "retention": ret, "stats": stats,
           "unaided_easy": unaided_easy, "unaided_medium": unaided_medium}
    gates = []
    for gate in GATES:
        try:
            passed = bool(gate["check"](ctx))
        except Exception:
            passed = False
        gates.append({"id": gate["id"], "label": gate["label"], "passed": passed})

    passed_gates = sum(1 for g in gates if g["passed"])
    # Never declare READY from an average alone: the gates are the real bar,
    # and the weakest dimension caps the headline number.
    avg = _avg([d["score"] for d in dimensions])
    weakest = min((d["score"] for d in dimensions), default=0)
    gate_ratio = passed_gates / len(gates)
    overall = round(min(avg, 40 + weakest * 0.7) * (0.4 + 0.6 * gate_ratio))

    return {
        "overall": overall,
        "dimensions": dimensions,
        "gates": gates,
        "gates_passed": passed_gates,
        "gates_total": len(gates),
        "ready": passed_gates == len(gates),
        "verdict": _verdict(overall, passed_gates, len(gates)),
    }


def _verdict(overall: int, passed: int, total: int) -> str:
    if passed == total:
        return ("Every readiness gate is met. On this evidence you are prepared for a "
                "demanding Python coding screen.")
    remaining = total - passed
    if overall >= 70:
        return (f"Strong overall, but {remaining} gate{'s' if remaining > 1 else ''} "
                "remain{'' if remaining > 1 else 's'} unmet. Averages do not pass "
                "interviews; the gates do.")
    if overall >= 45:
        return (f"Real progress. {remaining} gates still open — the open ones are "
                "exactly what to train next.")
    return ("Early days. The engine will keep routing you to whatever is actually "
            "blocking you.")
