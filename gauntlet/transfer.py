"""Transfer readiness: does any of this survive contact with a problem you have
never seen?

Ordinary mastery in this game measures familiarity. It is built from problems
the player was taught on, coached through, hinted at and shown again by the
spaced repetition scheduler, and it is a perfectly good measure of exactly that
— the progression depends on it and nothing here touches it.

This module measures something else, from evidence that has nothing in common
with it. One number, from encounters that were all three of:

  SEALED         hold-out content, which the teaching side of the game has
                 never been allowed to show, hint at, schedule or explain.
  ZERO-ASSISTANCE  no hint, no probe, no companion, no consumable, no worked
                 solution. Under the hold-out seal none of those are even
                 offered, so this is a statement of fact rather than a hope.
  FIRST OF ITS LINEAGE   the first time this player ever met this exercise in
                 any of its clothes. Five siblings cleared is one unfamiliar
                 problem solved five times, and counting it five times is how a
                 transfer score turns back into a familiarity score.

Three rules keep the number honest, and all three are about refusing to say
more than the evidence supports.

  * IT REPORTS ITS SAMPLE. Always, next to the number, never in a footnote.
  * IT REFUSES TO PRINT A PERCENTAGE IT CANNOT SUPPORT. Below MIN_SAMPLE there
    is no percentage at all, in words instead — because "100%" from two
    attempts is not 100%, and a UI given that number will render it as one.
  * IT SHIPS A CONFIDENCE BAND. A Wilson interval, which is what you use for a
    proportion from a small sample; the naive interval says things like "104%"
    and puts zero-width bands around 0 and 1.

The hold-out is finite — 97 lineages, one measurement each, ever — so this
number grows slowly and cannot be farmed. That is the design, not a limitation:
an unfamiliar problem is only unfamiliar once.
"""
from __future__ import annotations

import math

# Below this many counted encounters there is no headline percentage. Ten is a
# tenth of the lifetime hold-out and still a wide band (10/10 has a 95% lower
# bound near 72%), which is the honest shape of this measurement early on.
MIN_SAMPLE = 10

# A per-skill rate is a smaller claim on a smaller sample, and some skills own
# only one or two sealed lineages in the entire corpus, so most of them will
# report counts and nothing else for the life of a save. That is the truth.
SKILL_MIN_SAMPLE = 3

# 95%. Named rather than inlined because the band and the wording that explains
# the band must never drift apart.
Z = 1.959964
CONFIDENCE = "95%"


def wilson(successes: int, total: int, *, z: float = Z) -> tuple:
    """The Wilson score interval, as a (low, high) pair of proportions.

    The textbook normal interval is wrong in exactly the situation this module
    lives in — small n, proportions near 0 or 1 — where it produces bounds
    outside [0, 1] and a zero-width interval around a perfect score. Wilson does
    not, and it is four lines of stdlib arithmetic.
    """
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    spread = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
    spread /= denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def _pct(value: float) -> int:
    return int(round(100.0 * value))


def _band(cleared: int, sample: int) -> dict:
    low, high = wilson(cleared, sample)
    return {"low": _pct(low), "high": _pct(high),
            "text": f"{_pct(low)}-{_pct(high)}%", "confidence": CONFIDENCE}


def counted_rows(ledger) -> list:
    """The encounters allowed to move the number: sealed (everything in this
    ledger is), resolved, unaided, and the first of their lineage."""
    return [r for r in ledger if r.get("resolved") and r.get("counted")]


def _skill_entry(skill: str, rows: list) -> dict:
    sample = len(rows)
    cleared = sum(1 for r in rows if r.get("solved"))
    entry = {
        "skill": skill,
        "sample": sample,
        "cleared": cleared,
        "band": _band(cleared, sample),
        "measured": sample >= SKILL_MIN_SAMPLE,
        "rate": _pct(cleared / sample) if sample >= SKILL_MIN_SAMPLE else None,
    }
    if entry["measured"]:
        entry["text"] = (f"{cleared} of {sample} cleared cold "
                         f"({entry['rate']}%, {entry['band']['text']})")
    else:
        entry["text"] = (f"{cleared} of {sample} cleared cold — too few for a rate")
    return entry


def by_skill(ledger) -> list:
    """What transferred, not just how much. Largest sample first, because that
    is the order of how much any of these lines can be believed."""
    groups: dict = {}
    for row in counted_rows(ledger):
        groups.setdefault(row.get("skill") or "PYTHON", []).append(row)
    entries = [_skill_entry(skill, rows) for skill, rows in groups.items()]
    entries.sort(key=lambda e: (-e["sample"], e["skill"]))
    return entries


def _headline(sample: int, cleared: int, rate, band: dict) -> str:
    if sample < MIN_SAMPLE:
        return "TRANSFER READINESS — not yet measurable"
    return (f"TRANSFER READINESS {rate}% "
            f"(n={sample}, {CONFIDENCE} confidence {band['text']})")


def _note(sample: int, cleared: int, remaining: int) -> str:
    if sample == 0:
        return ("No unfamiliar hold-out problem has been attempted unaided yet. "
                "This number comes only from sealed problems met cold in a "
                "measured run, and nothing you do in Adventure Mode can move it "
                f"— by design. {remaining} unfamiliar hold-out problems remain.")
    if sample < MIN_SAMPLE:
        short = MIN_SAMPLE - sample
        return (f"{cleared} of {sample} unfamiliar hold-out problems cleared cold. "
                f"That is too small a sample to be a percentage — {short} more "
                "first-encounter attempt" + ("s" if short != 1 else "") +
                " before this becomes a number instead of an anecdote.")
    if not remaining:
        return (f"{cleared} of {sample} sealed problems cleared on first sight, "
                "unaided. The hold-out is spent: there is no formulation left in "
                "this corpus you have never seen, so this number is now final "
                "until new content ships.")
    return (f"{cleared} of {sample} sealed problems cleared on first sight, "
            "unaided. Each of those lineages is now spent — the hold-out answers "
            f"this question once per exercise — and {remaining} unfamiliar ones "
            "are left.")


def _verdict(sample: int, rate, band: dict) -> str:
    if sample < MIN_SAMPLE:
        return ("Timed Practical Mode and the final practical are the only places this "
                "evidence comes from. Sit one.")
    if band["low"] >= 70:
        return ("Even the pessimistic end of that band clears 70%. On this "
                "evidence the knowledge is transferring to formulations you "
                "have never been shown, which is the thing a timed practical tests.")
    if band["low"] >= 45:
        return ("The band is still wide. What it rules out is more useful than "
                "what it claims: this is not a player who only performs on "
                "material they have already been taught.")
    if rate is not None and rate >= 60:
        return ("The point estimate looks healthy and the sample does not yet "
                "support it. Sit more measured runs before believing it.")
    return ("Cold problems are not landing yet. Mastery built on taught material "
            "is real, and it is not the same thing as this.")


def summarise(ledger, *, remaining: int = 0, holdout_total: int = 0,
              lineages_total: int = 0) -> dict:
    """The whole report, from the ledger and nothing else.

    Note what is not a parameter: mastery, level, readiness, the schedule. This
    number is not allowed to borrow their evidence and they are not allowed to
    borrow its. Two independent numbers, or one number pretending to be two.
    """
    ledger = list(ledger or ())
    counted = counted_rows(ledger)
    sample = len(counted)
    cleared = sum(1 for r in counted if r.get("solved"))
    band = _band(cleared, sample)
    measured = sample >= MIN_SAMPLE
    rate = _pct(cleared / sample) if measured else None

    spent_lineages = {r.get("lineage_id") for r in ledger if r.get("lineage_id")}
    return {
        # The number, and the two things that must always travel beside it.
        "measured": measured,
        "score": rate,
        "sample": sample,
        "cleared": cleared,
        "band": band,
        "min_sample": MIN_SAMPLE,

        # Everything else is context for the number, never an input to it.
        "headline": _headline(sample, cleared, rate, band),
        "note": _note(sample, cleared, remaining),
        "verdict": _verdict(sample, rate, band),
        "by_skill": by_skill(ledger),
        "served": len(ledger),
        "resolved": sum(1 for r in ledger if r.get("resolved")),
        "assisted": sum(1 for r in ledger
                        if r.get("resolved") and not r.get("unaided")),
        "repeat_lineage": sum(1 for r in ledger if not r.get("first_encounter")),
        "spent_lineages": len(spent_lineages),
        "remaining": remaining,
        "holdout_total": holdout_total,
        "lineages_total": lineages_total,
    }
