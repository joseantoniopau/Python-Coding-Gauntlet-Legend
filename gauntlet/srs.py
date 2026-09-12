"""Spaced repetition over *patterns*, not over problems.

A problem solved once is not learned. The schedule returns the same underlying
algorithm wearing a different surface — a different element type, a different
story, a different output format — so the retest measures recognition rather
than memory of a specific prompt.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict

from .config import SRS_INTERVALS_DAYS
from .corpus import is_sealed

DAY = 86400.0


@dataclass
class ScheduleEntry:
    family: str                    # spaced_repetition_family, e.g. "window_k_distinct"
    stage: int = 0                 # index into SRS_INTERVALS_DAYS
    due_at: float = 0.0
    last_reviewed: float = 0.0
    lapses: int = 0
    reviews: int = 0
    ease: float = 1.0              # multiplies the interval; earned, not given
    seen_problem_ids: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def interval_days(stage: int, ease: float = 1.0) -> float:
    stage = max(0, min(stage, len(SRS_INTERVALS_DAYS) - 1))
    return SRS_INTERVALS_DAYS[stage] * max(0.6, min(ease, 2.2))


def schedule_after(entry: ScheduleEntry, *, solved: bool, hints_used: int,
                   now: float | None = None) -> ScheduleEntry:
    now = now or time.time()
    entry.reviews += 1
    entry.last_reviewed = now

    if not solved:
        entry.lapses += 1
        entry.stage = max(0, entry.stage - 2)
        entry.ease = max(0.6, entry.ease - 0.2)
        entry.due_at = now + 0.5 * DAY          # a lapse comes back tomorrow-ish
        return entry

    if hints_used == 0:
        entry.stage = min(entry.stage + 1, len(SRS_INTERVALS_DAYS) - 1)
        entry.ease = min(2.2, entry.ease + 0.1)
    elif hints_used <= 2:
        entry.stage = min(entry.stage + 1, len(SRS_INTERVALS_DAYS) - 1)
    else:
        # Heavy assistance: it counts as a clear, but the interval does not grow.
        entry.ease = max(0.6, entry.ease - 0.1)

    entry.due_at = now + interval_days(entry.stage, entry.ease) * DAY
    return entry


def due(entries: dict, *, now: float | None = None, limit: int = 20) -> list:
    now = now or time.time()
    ready = [e for e in entries.values() if e.due_at and e.due_at <= now]
    ready.sort(key=lambda e: (e.due_at, -e.lapses))
    return ready[:limit]


def overdue_days(entry: ScheduleEntry, *, now: float | None = None) -> float:
    now = now or time.time()
    if not entry.due_at or entry.due_at > now:
        return 0.0
    return (now - entry.due_at) / DAY


def days_since_review(entry: ScheduleEntry, *, now: float | None = None) -> float:
    now = now or time.time()
    if not entry.last_reviewed:
        return 0.0
    return (now - entry.last_reviewed) / DAY


def pick_disguised(entry: ScheduleEntry, candidates: list) -> object | None:
    """Prefer a problem in the family the player has NOT seen; prefer one whose
    surface differs most from what they last solved. Repeating the identical
    prompt tests recall of a prompt, which is not the skill being trained."""
    # The schedule exists to make an unfamiliar problem familiar, which is the
    # one thing that must never happen to hold-out content. Refused here as well
    # as at the caller, because this function is the last thing standing between
    # a candidate list and the player being shown it.
    candidates = [p for p in candidates if not is_sealed(p)]
    if not candidates:
        return None
    seen = set(entry.seen_problem_ids)
    fresh = [p for p in candidates if p.id not in seen]
    pool = fresh or candidates

    def surface_score(problem):
        score = 0
        if "disguised" in problem.tags:
            score += 3
        if problem.source_type in ("GENERATED_VARIANT", "SECURITY_VARIANT"):
            score += 2
        if problem.id not in seen:
            score += 4
        # later stages deserve harder disguises
        if entry.stage >= 2 and problem.difficulty in ("MEDIUM", "HARD"):
            score += 2
        return score

    return max(pool, key=surface_score)
