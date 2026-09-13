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
    # Set by a lapse, cleared by the next clear. It is the ONE thing that lets a
    # review carry a scaffold: the player has just shown they have forgotten
    # something, and the next sight of it should not be the same blank screen
    # they have just failed at. `curriculum.review_rung` reads it, and it is why
    # the expected mix puts 10% of MEDIUM on a scaffolded rung.
    recovering: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def interval_days(stage: int, ease: float = 1.0) -> float:
    stage = max(0, min(stage, len(SRS_INTERVALS_DAYS) - 1))
    return SRS_INTERVALS_DAYS[stage] * max(0.6, min(ease, 2.2))


# The lowest rung a serving may carry and still count as this family's review.
# A review measures retention; a half-written answer measures nothing, and
# `schedule_after` would grow the interval on the strength of it.
MIN_REVIEW_RUNG = 4

# THE ONE EXCEPTION, AND IT IS A PROPERTY OF THE ENTRY, NOT OF THE RUNG.
#
# Rung 3 was admitted here on the reasoning that a LAPSED review is deliberately
# served at rung 3 and that serving is the recovery review. The reasoning is
# right and the test was wrong: rung 3 is also EASY's own FLOOR
# (`scaffold.FLOOR["EASY"] == MANY_BLANKS`), so `rung >= 3` said yes to every
# ordinary EASY encounter at the bottom of the ramp as well. Measured: a
# non-lapsed rung-3 serving of `ob-keep-long-words` took the family from stage 0
# to stage 1, ease 1.00 to 1.10, and put the next sighting 3.3 days out; four
# such clears reached stage 4, ease 1.40 and +42.0 days — a month and a half
# bought with fill-in-the-blanks. 18 of the 36 EASY servings in a live
# 120-encounter career were rung 3.
#
# So the question is asked of the entry, which is the thing that knows whether
# this serving is a recovery.
#
# The consequence is deliberate and is named here rather than discovered later:
# A FAMILY WHOSE SERVINGS NEVER REACH RUNG 4 NEVER ACQUIRES A `due_at`, so it
# never enters `due()`. That is the correct reading. A review measures retention
# of something the player can produce; until an ordinary serving of that family
# has been the whole function, there is nothing to measure retention OF, and the
# climb off rung 3 is what enrols it. Non-editor encounters pass rung=0 and are
# unaffected — a multiple choice is answered whole or not at all.
RECOVERY_REVIEW_RUNG = 3


def counts_as_review(rung: int, *, recovering: bool = False) -> bool:
    """Does a serving at this rung measure what a review is asking about?"""
    rung = int(rung or MIN_REVIEW_RUNG)
    return rung >= MIN_REVIEW_RUNG or (rung == RECOVERY_REVIEW_RUNG and recovering)


def schedule_after(entry: ScheduleEntry, *, solved: bool, hints_used: int,
                   now: float | None = None, rung: int = 0) -> ScheduleEntry:
    now = now or time.time()
    # `entry.recovering` still holds what the LAST review said, which is exactly
    # the question: this serving is the recovery one when the previous one
    # lapsed. The clear below disarms it.
    if not counts_as_review(rung, recovering=bool(entry.recovering)):
        # A scaffolded serving of a family member is practice, not a review.
        # Growing the interval here would schedule the next sight of the idea on
        # the strength of the player having filled in one blank, which is the
        # measurement error the whole ramp is built to avoid.
        entry.last_reviewed = now
        return entry
    entry.reviews += 1
    entry.last_reviewed = now

    if not solved:
        entry.lapses += 1
        entry.recovering = True
        entry.stage = max(0, entry.stage - 2)
        entry.ease = max(0.6, entry.ease - 0.2)
        entry.due_at = now + 0.5 * DAY          # a lapse comes back tomorrow-ish
        return entry

    entry.recovering = False

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
    # A rung-2 serving must not count as this family's review. That guard is in
    # `schedule_after` rather than here, because the rung is decided when the
    # encounter is BUILT and this function runs before that — it chooses which
    # problem, not how much of it is already written. See `counts_as_review`.
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
