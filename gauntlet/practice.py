"""Advisory practice plans and evidence labels. Never selects sealed content."""
from __future__ import annotations

import copy
import time
import uuid

from . import scaffold, puzzles

STATE_KEY = "practice"
MINUTES = (10, 20, 40)
INTENTS = ("balanced", "review", "weakest", "new")
KINDS = ("expedition", "rehearsal")
IDLE_LEASE_SECONDS = 180
OPTIONS = {
    "minutes": list(MINUTES),
    "intents": [
        {"id": "balanced", "label": "Balanced", "description": "Follow the learning ramp with review and variety."},
        {"id": "review", "label": "Review", "description": "Revisit due or previously learned work."},
        {"id": "weakest", "label": "My weakest area", "description": "Prioritise a skill with room to improve."},
        {"id": "new", "label": "New ground", "description": "Prefer unseen work that your current skills support."},
    ],
    "kinds": [
        {"id": "expedition", "label": "Practice expedition", "description": "A short, resumable journey through ordinary learning encounters."},
        {"id": "rehearsal", "label": "Interview rehearsal", "description": "Practise explaining and solving with coaching. This is not a sealed assessment."},
    ],
}


def new_state() -> dict:
    return {"plan": None, "history": [], "notes": {}}


def begin(minutes: int, intent: str, kind: str, *, now=None) -> dict:
    now = time.time() if now is None else now
    return {"id": "practice-" + uuid.uuid4().hex, "minutes": minutes,
            "intent": intent, "kind": kind, "status": "active",
            "created_at": now, "resumed_at": now, "last_activity": now, "elapsed": 0.0,
            "current": None, "results": [], "completed": [], "retreated": 0,
            "coach": "Start with one manageable exercise. Say what it asks before you write."}


def elapsed(plan: dict, *, now=None) -> float:
    now = time.time() if now is None else now
    return max(0.0, float(plan.get("elapsed", 0))) + (
        max(0.0, min(now, float(plan.get("last_activity", plan.get("resumed_at", now)))
                         + IDLE_LEASE_SECONDS) - float(plan.get("resumed_at", now)))
        if plan.get("status") == "active" else 0.0)


def pause(plan: dict, *, now=None) -> None:
    if plan.get("status") != "active":
        return
    plan["elapsed"] = elapsed(plan, now=now)
    plan["status"] = "paused"


def resume(plan: dict, *, now=None) -> None:
    if plan.get("status") != "paused":
        return
    plan["resumed_at"] = time.time() if now is None else now
    plan["last_activity"] = plan["resumed_at"]
    plan["status"] = "active"


def heartbeat(plan: dict, *, now=None) -> None:
    if plan.get("status") != "active":
        return
    now = time.time() if now is None else now
    plan["elapsed"] = elapsed(plan, now=now)
    plan["resumed_at"] = plan["last_activity"] = now


def view(plan: dict | None, *, now=None) -> dict | None:
    if not plan:
        return None
    rows = plan.get("results", [])
    solved = [r for r in rows if r["solved"]]
    seconds = elapsed(plan, now=now)
    target = int(plan["minutes"]) * 60
    current = plan.get("current") or {}
    draft = (current.get("encounter") or {}).get("draft") or {}
    summary = {
        "attempts": len(rows), "solved": len(solved),
        "assisted": sum(r["hints_used"] > 0 or r["evidence_kind"] == "scaffolded" for r in solved),
        "independent": sum(r["evidence_kind"] == "whole_function" and not r["hints_used"] for r in solved),
        "reading": sum(r["evidence_kind"] == "reading" for r in solved),
        "retained": sum(r["retained"] for r in solved),
        "retreated": plan.get("retreated", 0), "coach": plan.get("coach", ""),
        "remaining_seconds": max(0, round(target - seconds)),
    }
    return {"id": plan["id"], "kind": plan["kind"], "minutes": plan["minutes"],
            "intent": plan["intent"], "status": plan["status"],
            "elapsed_seconds": round(seconds, 1), "target_seconds": target,
            "completed_count": len(plan.get("completed", [])),
            "phase": "reflection" if plan["status"] == "finished" else
                     "practice" if rows else "warmup",
            "summary": summary, "can_resume": plan["status"] != "finished",
            "active_problem_id": current.get("problem_id", ""),
            "draft_saved_at": draft.get("saved_at"),
            "idle_lease_seconds": IDLE_LEASE_SECONDS,
            "clock_note": "Advisory activity clock. Paused time is excluded; the clock stops after three minutes without activity or a visible-page heartbeat."}


def evidence(problem, enc) -> tuple:
    """Describe the actual response modality; absence of hints is not a rung."""
    if enc.repo_id:
        return None, "repository"
    if problem.entry.get("kind") == "mcq" or problem.encounter_kind in (
            "CODE_READING", "PATTERN_ENCOUNTER", "COMPLEXITY_DUEL"):
        return None, "reading"
    if problem.encounter_kind in puzzles.PUZZLE_KINDS:
        return None, "puzzle"
    if problem.entry.get("kind") == "test_forge" or problem.encounter_kind == "TEST_FORGE":
        return None, "test_writing"
    if problem.encounter_kind == "DEBUG_BATTLE":
        return None, "debugging"
    if scaffold.scaffoldable(problem):
        rung = int(enc.rung or 0)
        if rung in (1, 2, 3, 4):
            return rung, "whole_function" if rung == 4 else "scaffolded"
    return None, "unknown"


def record(plan: dict, enc, *, attempt_id: int, solved: bool,
           evidence_kind: str, rung, root_cause: str = "") -> None:
    if enc.practice_id != plan.get("id") or plan.get("status") == "finished":
        return
    heartbeat(plan)
    if any(row["attempt_id"] == attempt_id for row in plan["results"]):
        return
    plan["results"].append({"attempt_id": attempt_id, "problem_id": enc.problem_id,
        "task_id": enc.practice_task_id, "solved": bool(solved),
        "evidence_kind": evidence_kind, "served_rung": rung,
        "hints_used": enc.hints_used,
        "retained": bool(solved and enc.is_retest and rung == 4 and not enc.hints_used)})
    if solved and enc.practice_task_id not in plan["completed"]:
        plan["completed"].append(enc.practice_task_id)
        plan["current"] = None
    if solved:
        plan["coach"] = (
            "You produced the whole function without hints. Explain why it works, then name one edge case."
            if evidence_kind == "whole_function" and not enc.hints_used else
            "You completed a reading exercise. Next, try expressing the idea in your own code."
            if evidence_kind == "reading" else
            "You completed this exercise with support. Describe the idea, then revisit it with less help."
            if evidence_kind == "scaffolded" or enc.hints_used else
            "You completed this exercise. Explain your choices, then name an edge case that would challenge them.")
    else:
        plan["coach"] = "Before retrying, explain the failing case and change one thing at a time."
        if root_cause:
            plan["coach"] += " Review: " + root_cause.replace("_", " ").lower() + "."


def finish(block: dict, *, now=None) -> None:
    plan = block.get("plan")
    if not plan or plan.get("status") == "finished":
        return
    pause(plan, now=now)
    plan["status"] = "finished"
    plan["current"] = None
    snapshot = view(plan, now=now)
    # Finishing records a reflection; ordinary graded encounters already paid.
    # There is no separate currency grant to replay or farm.
    block["history"] = [copy.deepcopy(snapshot)] + [
        row for row in block.get("history", []) if row["id"] != plan["id"]][:19]
