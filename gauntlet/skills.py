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
PATTERN_TO_SKILL = {
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

    def to_dict(self) -> dict:
        return asdict(self)


def new_skills() -> dict:
    return {name: SkillState(name=name) for name in SKILLS}


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


DIFFICULTY_WEIGHT = {
    "GUIDED": 0.3, "TUTORIAL": 0.5, "EASY": 1.0, "MEDIUM": 1.8, "HARD": 2.6,
    "ELITE": 3.0, "BOSS": 3.4,
}


def apply_outcome(state: SkillState, *, solved: bool, difficulty: str,
                  hints_used: int, seconds: float, target_seconds: float,
                  first_try: bool, is_retest: bool, interval_days: float = 0.0,
                  mode: str = "adventure") -> SkillState:
    """Fold one graded attempt into a skill. This is the only place mastery moves."""
    now = time.time()
    weight = DIFFICULTY_WEIGHT.get(difficulty, 1.0)
    state.attempts += 1
    state.last_seen = now

    if solved:
        state.clears += 1
        if hints_used == 0:
            state.unaided_clears += 1
        if first_try:
            state.first_try_clears += 1
        state.solve_times.append(round(seconds, 1))
        state.solve_times = state.solve_times[-25:]
        state.median_solve_seconds = _median(state.solve_times)

        # Assistance sharply discounts the mastery credit, but never zeroes it:
        # a solve with help is still evidence, just weaker evidence.
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
