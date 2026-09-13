"""The skill model: what the player can actually do, and how confident we are.

Mastery is never granted for viewing content. Every number here moves only on
*evidence* — a submission, a retest, an explanation, a timed clear.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, asdict

SKILLS = [
    "PYTHON", "HASH_MAP", "STRING", "ARRAY", "SLIDING_WINDOW", "TWO_POINTER",
    "STACK", "QUEUE", "MATRIX", "RECURSION", "TREE", "GRAPH", "BFS", "DFS",
    "DP", "DEBUGGING", "BIG_O", "TESTING", "SPEED", "RECALL", "COMMUNICATION",
    "BINARY_SEARCH", "HEAP", "PREFIX_SUM", "SORTING", "SIMULATION", "DESIGN",
    "SET", "INTERVALS", "GREEDY",
]

# Which pattern a solved problem credits, and what it partially credits.
#
# LANGUAGE credits PYTHON, which is the whole reason the pattern exists. A
# fill-in-the-blank whose content is `doubled = n * 2` used to be filed under
# STRING and therefore credited the STRING skill, so the ramp measured a
# beginner's grasp of strings out of evidence about assignment. The engine
# already patched around it by paying PYTHON a second time for every GUIDED and
# TUTORIAL clear (engine._apply_outcome); with an honest label that patch is a
# top-up rather than a correction.
PATTERN_TO_SKILL = {
    "LANGUAGE": "PYTHON",
    "HASH_MAP": "HASH_MAP", "SET": "SET", "SLIDING_WINDOW": "SLIDING_WINDOW",
    "TWO_POINTER": "TWO_POINTER", "STACK": "STACK", "QUEUE": "QUEUE",
    "BFS": "BFS", "DFS": "DFS", "TREE": "TREE", "RECURSION": "RECURSION",
    "BINARY_SEARCH": "BINARY_SEARCH", "MATRIX": "MATRIX", "HEAP": "HEAP",
    "PREFIX_SUM": "PREFIX_SUM", "SORTING": "SORTING", "SIMULATION": "SIMULATION",
    "DP": "DP", "STRING": "STRING", "ARRAY": "ARRAY", "DESIGN": "DESIGN",
    "GREEDY": "GREEDY", "INTERVALS": "INTERVALS", "DEBUGGING": "DEBUGGING",
    "COMPLEXITY": "BIG_O", "TESTING": "TESTING", "RECOGNITION": "RECALL",
}

GRAPH_SKILLS = {"BFS", "DFS"}

STAGES = ["UNKNOWN", "EXPOSED", "UNDERSTOOD", "ASSISTED", "INDEPENDENT",
          "RETAINED", "FAST", "MASTERED"]

STAGE_BLURB = {
    "UNKNOWN": "not yet met",
    "EXPOSED": "you have seen it explained",
    "UNDERSTOOD": "you can explain the idea",
    "ASSISTED": "you solved it with help",
    "INDEPENDENT": "you solved it unaided",
    "RETAINED": "you solved a disguised variant days later",
    "FAST": "you solved it unaided, under target time",
    "MASTERED": "boss defeated and retained across intervals",
}

# The learning graph: what a skill depends on. Failure analysis walks this
# downward to find the real prerequisite rather than reteaching the surface.
PREREQUISITES = {
    "SLIDING_WINDOW": ["HASH_MAP", "PYTHON"],
    "TWO_POINTER": ["ARRAY", "PYTHON"],
    "HASH_MAP": ["PYTHON"],
    "SET": ["PYTHON"],
    "STACK": ["PYTHON", "ARRAY"],
    "QUEUE": ["PYTHON", "ARRAY"],
    "BFS": ["QUEUE", "SET"],
    "DFS": ["RECURSION", "SET"],
    "TREE": ["RECURSION"],
    "GRAPH": ["BFS", "DFS"],
    "RECURSION": ["PYTHON"],
    "DP": ["RECURSION", "ARRAY"],
    "MATRIX": ["ARRAY"],
    "BINARY_SEARCH": ["ARRAY"],
    "HEAP": ["PYTHON", "SORTING"],
    "PREFIX_SUM": ["ARRAY", "HASH_MAP"],
    "INTERVALS": ["SORTING"],
    "DESIGN": ["HASH_MAP", "QUEUE"],
    "STRING": ["PYTHON"],
    "ARRAY": ["PYTHON"],
    "DEBUGGING": ["PYTHON"],
    "TESTING": ["PYTHON"],
    "BIG_O": [],
    "PYTHON": [],
}


class SkillBook(dict):
    """A skills mapping that can also carry where the player was PLACED.

    The diagnostic can say "you do not need the alphabet, start at Counting".
    That is a statement about the chapter ladder, and the ladder is computed
    from mastery — which a diagnostic deliberately cannot move very far,
    because a diagnostic is weak evidence. So the placement travels beside the
    mastery rather than inside it: `placement_floor` is the lowest chapter the
    player starts on, and `curriculum.frontier` floors its answer with it.

    It is a dict subclass rather than an extra argument threaded through
    twenty-odd call sites because every one of those call sites already
    receives this exact object from `Game.skills`. Anything that rebuilds a
    plain dict loses the floor and falls back to zero, which is the safe
    direction: a lost floor under-places, it never over-places.
    """

    placement_floor: int = 0

    def with_floor(self, floor: int) -> "SkillBook":
        self.placement_floor = max(0, int(floor or 0))
        return self


@dataclass
class SkillState:
    name: str
    mastery: float = 0.0          # 0-100, evidence-weighted
    confidence: float = 0.0       # how sure we are the mastery number is real
    speed: float = 0.0            # 0-100 vs target time
    retention: float = 0.0        # survives delayed retests
    recency: float = 0.0          # decays with time
    error_rate: float = 0.0
    hint_dependence: float = 0.0
    attempts: int = 0
    clears: int = 0
    unaided_clears: int = 0
    first_try_clears: int = 0
    median_solve_seconds: float = 0.0
    pattern_recognition_ms: float = 0.0
    debugging_seconds: float = 0.0
    stage: str = "UNKNOWN"
    last_seen: float = 0.0
    solve_times: list = field(default_factory=list)
    # Clears broken out by the tier they were earned at. `clears` alone cannot
    # answer "has the scaffolding come off?", because eight fill-in-the-blanks
    # and eight blank screens are the same number. The ramp needs to tell them
    # apart, so the evidence is recorded at the grain the question is asked at.
    # Absent on a save written before this existed, which is not the same as
    # zero — see curriculum.scaffold_target.
    tier_clears: dict = field(default_factory=dict)
    tier_unaided: dict = field(default_factory=dict)
    # And the same evidence filed by RUNG of the ramp — which rung of the
    # scaffold the player was actually shown when they cleared it. The tier
    # record above cannot answer "has the scaffolding come off?" either, because
    # the band is not the rung: 21 EASY problems ship a two-blank scaffold, and
    # clearing one of those used to satisfy `has_produced_code` outright. Filing
    # by rung makes a scaffolded clear arithmetically incapable of counting as
    # evidence of writing a function, rather than merely discouraged from it.
    # Keys are the ints 1-4; see gauntlet/scaffold.py. Absent on a save written
    # before this existed, which is not the same as zero — see
    # curriculum.has_produced_code.
    rung_clears: dict = field(default_factory=dict)
    rung_unaided: dict = field(default_factory=dict)
    # Unaided clears that were BOTH the whole function AND at EASY or harder.
    # Two conditions, because either one alone is satisfiable without having
    # done the thing: a rung-4 GUIDED problem is a two-line body on a blank
    # screen, and an EASY problem can be served with three blanks in it. The
    # escape hatch out of the scaffold band was always meant to mean "produced
    # working code on a blank screen", and this is the only tally that says so.
    production_unaided: int = 0
    # How many of the unaided EASY-or-harder clears were filed WITH a rung at
    # all. The difference between this and `tier_unaided` at EASY-and-above is
    # the evidence that predates rungs being recorded, and it is the number
    # `has_produced_code` has to ask about. Asking instead whether the rung
    # record was empty would make the exemption last exactly one encounter —
    # the same trap `curriculum._tier_record_missing` documents, one layer up,
    # and measured here: a fluent player who skipped the beginner chain met six
    # rungs of it after their first scaffolded clear landed.
    production_seen: int = 0
    # Misses in a row, reset by any clear. The ramp gives support back one rung
    # per consecutive miss, so a slip costs a little help and a collapse costs
    # all of it — incantation.tier_for has done this for combat lines since the
    # gradient shipped, and it is the same evidence question here.
    miss_streak: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def new_skills() -> SkillBook:
    return SkillBook({name: SkillState(name=name) for name in SKILLS})


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _median(values: list) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


# The two halves of "produced working code on a blank screen", spelled out here
# rather than imported, because `curriculum` imports this module and not the
# other way round.
WRITE_IT_ALL_RUNG = 4
PRODUCTION_TIERS = frozenset({"EASY", "MEDIUM", "HARD", "ELITE", "BOSS"})

DIFFICULTY_WEIGHT = {
    "GUIDED": 0.3, "TUTORIAL": 0.5, "EASY": 1.0, "MEDIUM": 1.8, "HARD": 2.6,
    "ELITE": 3.0, "BOSS": 3.4,
}


def apply_outcome(state: SkillState, *, solved: bool, difficulty: str,
                  hints_used: int, seconds: float, target_seconds: float,
                  first_try: bool, is_retest: bool, interval_days: float = 0.0,
                  mode: str = "adventure", rung: int = 0) -> SkillState:
    """Fold one graded attempt into a skill. This is the only place mastery moves."""
    now = time.time()
    weight = DIFFICULTY_WEIGHT.get(difficulty, 1.0)
    state.attempts += 1
    state.last_seen = now

    if solved:
        state.clears += 1
        state.miss_streak = 0
        state.tier_clears[difficulty] = state.tier_clears.get(difficulty, 0) + 1
        # The rung is what the player was SHOWN, passed down from the encounter
        # that served it. Recording it here, in the same breath as the clear, is
        # what makes "eight fill-in-the-blanks" and "eight blank screens"
        # different numbers instead of the same one.
        if rung:
            key = str(int(rung))
            state.rung_clears[key] = state.rung_clears.get(key, 0) + 1
            if hints_used == 0:
                state.rung_unaided[key] = state.rung_unaided.get(key, 0) + 1
                if (difficulty in PRODUCTION_TIERS
                        and int(rung) >= WRITE_IT_ALL_RUNG):
                    state.production_unaided += 1
        if hints_used == 0:
            state.unaided_clears += 1
            state.tier_unaided[difficulty] = \
                state.tier_unaided.get(difficulty, 0) + 1
            # THE TALLY OF WHAT HAS BEEN SEEN IS NOT GATED ON A RUNG.
            #
            # `production_seen` and `tier_unaided` are the two halves of
            # `curriculum.untracked_production`, whose docstring says it counts
            # "unaided EASY-or-harder clears this skill holds that carry no
            # rung" — clears from a save written before rungs were recorded.
            # Incrementing the left half unconditionally and the right half only
            # inside `if rung:` made every ordinary encounter look like one of
            # those. `engine.py` deliberately passes rung=0 for every non-editor
            # encounter, so one correct answer to an EASY multiple choice — a
            # CODE_READING, a SPOT_THE_FLAW, a RUNE_ASSEMBLY, a DEBUG_BATTLE, a
            # BREAK_IT, a REFACTOR_QUEST or a TEST_FORGE — grew the difference by
            # one and `has_produced_code` read it as legacy production.
            #
            # Measured on a fresh save: answering `cr-mutable-default`, an EASY
            # CODE_READING multiple choice, flipped `has_produced_code` False ->
            # True, `scaffold_cleared` False -> True, and moved the difficulty
            # target from GUIDED to EASY. On the live selector, ARRAY's
            # production evidence was minted by `sf-latest-not-best`.
            #
            # So it counts every unaided EASY-or-harder clear, which is what the
            # tally it is differenced against counts, and the difference means
            # what it says again.
            if difficulty in PRODUCTION_TIERS:
                state.production_seen += 1
        if first_try:
            state.first_try_clears += 1
        state.solve_times.append(round(seconds, 1))
        state.solve_times = state.solve_times[-25:]
        state.median_solve_seconds = _median(state.solve_times)

        # Assistance sharply discounts the mastery credit, but never zeroes it:
        # a solve with help is still evidence, just weaker evidence.
        #
        # THE RUNG IS DELIBERATELY NOT CHARGED HERE, and the reason is measured
        # rather than assumed. Treating each rung below the whole function as
        # one more hint is the obvious move — it is assistance, on the same
        # scale — and it was tried: rung 2 paid 0.48 of the credit, rung 1 paid
        # 0.38. It broke the beginner chain. `test_ramp` measures that a
        # beginner meets at least twelve of the fifty-seven first-steps rungs in
        # their first forty encounters, and under the discount they met eight
        # and the chain stalled at fifteen, because mastery is what carries a
        # player along the chain and slowing it moved them off it.
        #
        # The farm it was guarding against is closed elsewhere, and closed
        # harder: a scaffolded clear cannot produce rung-4 evidence
        # (`curriculum.has_produced_code`), cannot grow an SRS interval
        # (`srs.counts_as_review`), and cannot be a second piece of evidence
        # about its own idea, because it is the same problem with the same id in
        # the same lineage. And it is not a state a player can sit in: clearing
        # a rung is what promotes them off it.
        assistance = 1.0 / (1.0 + 0.55 * hints_used)
        gain = 7.5 * weight * assistance
        if is_retest:
            # Delayed recall is the strongest evidence we ever collect.
            gain *= 1.4 + min(interval_days, 30) / 60.0
        if mode == "interview":
            gain *= 1.25
        state.mastery = _clamp(state.mastery + gain * (1 - state.mastery / 130.0))

        if seconds <= target_seconds:
            state.speed = _clamp(state.speed + 6.0 * weight)
        else:
            overrun = seconds / max(target_seconds, 1.0)
            state.speed = _clamp(state.speed + max(0.0, 4.0 - overrun))

        if is_retest:
            state.retention = _clamp(state.retention + 9.0 + min(interval_days, 30) / 3.0)
    else:
        # A failure costs less than a success gains. The system must never make
        # the player feel that trying was a mistake.
        state.miss_streak += 1
        state.mastery = _clamp(state.mastery - 2.2 * weight)
        state.retention = _clamp(state.retention - 1.5)

    state.error_rate = _clamp(100.0 * (1 - state.clears / max(state.attempts, 1)))
    if state.clears:
        # Exponential moving average so recent independence counts most.
        target = 100.0 * (1 - state.unaided_clears / state.clears)
        state.hint_dependence = _clamp(0.7 * state.hint_dependence + 0.3 * target)
    state.confidence = _clamp(100.0 * (1 - math.exp(-state.attempts / 6.0)))
    state.recency = 100.0
    state.stage = derive_stage(state)
    return state


def decay(state: SkillState, *, now: float | None = None) -> SkillState:
    """Recency fades; mastery does not evaporate, but our confidence in it does."""
    now = now or time.time()
    if not state.last_seen:
        return state
    days = (now - state.last_seen) / 86400.0
    state.recency = _clamp(100.0 * math.exp(-days / 12.0))
    if days > 21:
        state.confidence = _clamp(state.confidence * 0.9)
    return state


def derive_stage(state: SkillState) -> str:
    if state.attempts == 0:
        return "UNKNOWN"
    if state.clears == 0:
        return "EXPOSED" if state.mastery < 12 else "UNDERSTOOD"
    if state.unaided_clears == 0:
        return "ASSISTED"
    if state.retention >= 55 and state.mastery >= 70 and state.speed >= 60:
        return "MASTERED" if state.mastery >= 85 else "FAST"
    if state.speed >= 60 and state.mastery >= 60:
        return "FAST"
    if state.retention >= 35:
        return "RETAINED"
    return "INDEPENDENT"


def weakest(skills: dict, *, limit: int = 5, floor_attempts: int = 1) -> list:
    """Skills with evidence of weakness, worst first. Untouched skills rank by
    absence of evidence, not by pretending they are zero-mastery."""
    scored = []
    for state in skills.values():
        if state.attempts < floor_attempts:
            continue
        pain = (100 - state.mastery) * 0.5 + state.error_rate * 0.3 \
            + state.hint_dependence * 0.2
        scored.append((pain, state.name))
    scored.sort(reverse=True)
    return [name for _, name in scored[:limit]]


def missing_prerequisite(skills: dict, skill: str) -> str | None:
    """When a skill fails, find the weakest thing it stands on. This is what
    routes the player to the right Training Camp instead of reteaching the
    surface pattern they just failed."""
    best = None
    best_mastery = 101.0
    for prereq in PREREQUISITES.get(skill, []):
        state = skills.get(prereq)
        if state is None:
            continue
        if state.mastery < 55 and state.mastery < best_mastery:
            best, best_mastery = prereq, state.mastery
    return best
