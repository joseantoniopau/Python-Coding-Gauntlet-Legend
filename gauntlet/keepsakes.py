"""Cosmetic colors earned from recorded practice; no effects or scoring hooks."""
from __future__ import annotations

CATALOG = (
    {"id": "equipment", "name": "Roadworn colors", "requirement": "Your equipment's original colors.", "palette": {}},
    {"id": "copper", "name": "First Light", "requirement": "Pass one whole-function coding encounter without hints.",
     "palette": {"cloak": "#a45438", "tunic": "#485878", "trim": "#e8bb70"}},
    {"id": "indigo", "name": "Memory Keeper", "requirement": "Pass delayed reviews of three different problems without hints, writing whole functions.",
     "palette": {"cloak": "#535090", "tunic": "#385858", "trim": "#a8c8cf"}},
    {"id": "ember", "name": "Mender's Ember", "requirement": "Repair three different debugging problems without hints.",
     "palette": {"cloak": "#793b42", "tunic": "#53534c", "trim": "#dfae72"}},
    {"id": "verdigris", "name": "Workshop Patina", "requirement": "Complete one repository investigation without hints.",
     "palette": {"cloak": "#356e65", "tunic": "#605047", "trim": "#d1bd81"}},
)


def view(state: dict, attempts) -> dict:
    records = [dict(row) for row in attempts]
    clear = [r for r in records if r.get("solved") and not r.get("hints_used")
             and r.get("mode") == "adventure"]
    independent = [r for r in clear if r.get("evidence_kind") == "whole_function"]
    earned = {"equipment"}
    if independent:
        earned.add("copper")
    if len({r.get("problem_id") for r in independent if r.get("is_retest")}) >= 3:
        earned.add("indigo")
    if len({r.get("problem_id") for r in clear if r.get("evidence_kind") == "debugging"}) >= 3:
        earned.add("ember")
    if any(r.get("evidence_kind") == "repository" for r in clear):
        earned.add("verdigris")
    selected = (state.get("appearance") or {}).get("selected", "equipment")
    if selected not in earned:
        selected = "equipment"
    return {"available": True, "selected": selected, "options": [
        {**row, "unlocked": row["id"] in earned} for row in CATALOG]}


def select(state: dict, attempts, identifier: str) -> dict:
    card = view(state, attempts)
    if not any(r["id"] == identifier and r["unlocked"] for r in card["options"]):
        return {"error": "That appearance has not been earned yet."}
    state.setdefault("appearance", {})["selected"] = identifier
    return view(state, attempts)


def palette(state: dict, attempts) -> dict:
    card = view(state, attempts)
    return dict(next(r["palette"] for r in card["options"] if r["id"] == card["selected"]))
