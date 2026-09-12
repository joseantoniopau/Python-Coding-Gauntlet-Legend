"""The Finale: the index under the castle, the roll call, and the freeze frame.

The last thing the Null King did with the people you pulled out of boss chambers
was not kill them. It filed them. There is a room under the castle — under the
room the castle was built on top of in order to stop being able to see it — and
it is shelves rather than cells, because the King never kept a prisoner in his
life. He kept entries, and an entry does not need a door. Every person you freed
is standing in a niche with their name taken off the front, and the small green
sphere you have been finding in other people's hands since the second chapter is
on a shelf in each niche, at chest height, pointing.

This module is the scene that happens when that stops being true. Four
commitments hold it together, and all four are load-bearing.

1. IT DOES NOT TOUCH THE MEASUREMENT. `gauntlet/finalexam.py` is the sealed
practical and it is exactly as it was. Nothing here is a prerequisite for
sitting it, nothing here is consulted while it runs, and nothing here can change
its verdict. A player who rescued nobody sits the same exam, on the same clock,
and can pass it. The only capability question asked anywhere in this file is
`finalexam.sealed`, the same one every other module asks, and it is asked in
order to REFUSE to speak during a measured run.

2. IT FIRES ON SITTING THE THING, NOT ON PASSING IT. The index exists to answer
on your behalf. That is the whole of what it is for and it is the reason it was
built. For the length of the practical, in the room above, nothing answered on
your behalf — so the index is a lookup with nothing on the other end of it, and
it has been that since you sat down. It is only now finding out. Pass or fail,
the shelves empty. What the pass buys you is a different sentence at the end of
the freeze frame, and that sentence is printed from your own numbers.

3. IT SCALES TO THE ROLL CALL. The whole campaign's side work arrives at the
last door as a number: how many people are standing behind you in the frame.
The camera pulls back further, the chorus stands deeper, the ribbon on the title
card says a different thing, and an empty gallery is allowed to be empty. The
game does not invent a crowd for a player who did not go and find one.

4. TRIUMPH FIRST, THEN HONESTY, IN THAT ORDER. docs/09-story-bible.md §5 is a
eucatastrophe followed by the long defeat, and the order is the whole point. The
freeze frame is real and is not undercut. The coda comes afterwards, says that
most of what was erased stays erased, and hands the player a child with a box of
loose lines in it. Both are true. Neither is allowed to interrupt the other.

The scene is DATA. `cutscene()` returns a list of beats with absolute timings,
camera moves from a fixed vocabulary, who is on screen, which music track is
playing, where the guitar hit falls to the millisecond and what the title card
says. Another pass draws it and does not have to guess at any of it. What this
module never returns is a problem, a hint, a solution or a number it did not
receive from something that measured it.
"""
from __future__ import annotations

import builtins
import keyword
import re
from dataclasses import dataclass

from . import config, finalexam, transfer, world

# ---------------------------------------------------------------------------
# 0. State, and the one capability question
# ---------------------------------------------------------------------------

STATE_KEY = "finale"

# The cutscene is a named voice speaking to the player, which is precisely what
# the MENTOR crutch is, so it travels the same road as every other refusal in
# the game rather than inventing a second one. During a measured run this module
# says nothing at all. See WIRING §5.
FINALE_CAPABILITY = "MENTOR"


def new_state() -> dict:
    """Bookkeeping only. Nothing in here is evidence and nothing in here gates
    anything: a save that loses it replays a cutscene."""
    return {
        "seen": False,            # the freeze frame has played at least once
        "plays": 0,               # how many times (re-sits replay it)
        "best_verdict": "",       # the best exam verdict this save has reached
        "last_verdict": "",       # the most recent one
        "freed_at_finale": 0,     # roll call size the last time it played
        "coda_seen": False,       # the honest half was reached, not skipped
    }


def ensure(state: dict) -> dict:
    """Forward-fill for a save written before this module existed."""
    block = state.setdefault(STATE_KEY, new_state())
    for key, value in new_state().items():
        block.setdefault(key, value)
    return block


# ---------------------------------------------------------------------------
# 1. The room
# ---------------------------------------------------------------------------
#
# world.py owns the geography of the final trial and finalexam.py owns the
# animal standing in it. This is the room BEFORE that room, and it is the only
# piece of world this module is allowed to own, because nothing else in the game
# needs to know it is there until the scene plays.

THE_INDEX_FLOOR = {
    "id": "the_index_floor",
    "name": "THE STANDING INDEX",
    "region": world.FINAL_TRIAL["region"],
    "where": "One floor below the practical, reached by a stair that is not on "
             "any map because nobody who drew a map was ever shown it.",
    "blurb": "Shelves. Not cells — shelves, cut into the rock in rows, each one "
             "the size of a person standing up. The Null King never kept a "
             "prisoner in his life. He kept entries, and an entry does not need "
             "a door, a guard or a lock. It needs a place to be looked up from.",
    "law": "A person in a niche here has had their name taken off the front of "
           "them and filed somewhere that is not them. They are not asleep and "
           "they are not enchanted. They are simply no longer the thing their "
           "name points at, and the small green sphere on the shelf at chest "
           "height is what it points at instead.",
    "sprite": "index_floor",
    "colour": "#2a2f36",
    "accent": "#6ee08a",          # the Green Index, and the only green in here
    "palette": world.REGION_BY_ID[world.FINAL_TRIAL["region"]]["palette"],
}


def gallery_view() -> dict:
    """The room, for a client that wants to draw it before the scene runs."""
    return dict(THE_INDEX_FLOOR)


# ---------------------------------------------------------------------------
# 2. The roll call
# ---------------------------------------------------------------------------
#
# THE CAPTIVES ARE NOT OWNED HERE. Another pass owns the people: their names,
# their trades, their opinions and what they do for the player afterwards. This
# module receives them and stages them, and it is deliberately tolerant about
# the shape it receives, because a finale that crashes when a sibling module
# renames a field is a finale nobody ships.
#
# The only field that is genuinely required is a name. Everything else degrades
# to something the scene can still play.

_ALIASES = {
    "id": ("id", "captive_id", "npc_id", "key"),
    "name": ("name", "display_name", "who"),
    "trade": ("trade", "role", "job", "craft", "occupation"),
    "region": ("region", "region_id", "home", "from_region"),
    "boss": ("boss", "boss_id", "taken_by", "held_by"),
    "sprite": ("sprite", "portrait", "art"),
    "line": ("finale_line", "line", "says", "greeting", "first_words"),
    "boon": ("boon", "afterwards", "service", "help", "consequence"),
    "order": ("order", "freed_order", "rescued_order", "index", "sequence"),
    "freed_at": ("freed_at", "rescued_at", "timestamp", "when"),
}


def _pick(record, key: str, default=""):
    """Read one field out of a dict or an object, by any of its known names."""
    for alias in _ALIASES[key]:
        if isinstance(record, dict):
            if alias in record and record[alias] not in (None, ""):
                return record[alias]
        else:
            value = getattr(record, alias, None)
            if value not in (None, ""):
                return value
    return default


def _region_name(region_id: str) -> str:
    region = world.REGION_BY_ID.get(region_id)
    return region["name"] if region else ""


def _boss_name(boss_id: str) -> str:
    boss = world.BOSS_BY_ID.get(boss_id)
    return boss["name"] if boss else ""


def normalise(record) -> dict:
    """One freed person, in the shape the scene stages.

    A record with nothing in it but a name still produces a usable row. A record
    carrying everything produces a row that says who this person is, where they
    are from, who took them, what they think about it and what they are going to
    do for the player now that they are out.
    """
    name = str(_pick(record, "name") or "").strip()
    region_id = str(_pick(record, "region") or "")
    boss_id = str(_pick(record, "boss") or "")
    return {
        "id": str(_pick(record, "id") or name.lower().replace(" ", "_")),
        "name": name,
        "trade": str(_pick(record, "trade") or ""),
        "region": region_id,
        "region_name": _region_name(region_id),
        "boss": boss_id,
        "boss_name": _boss_name(boss_id),
        "sprite": str(_pick(record, "sprite") or "villager"),
        "line": str(_pick(record, "line") or ""),
        "boon": str(_pick(record, "boon") or ""),
        "order": _pick(record, "order", default=None),
        "freed_at": _pick(record, "freed_at", default=None),
    }


def _sorted_rows(freed) -> list:
    """Rescue order, as well as it can be known.

    An explicit `order` wins, then a timestamp, then the order the caller handed
    them over in — which is usually already rescue order, because that is the
    order a save appends them in.
    """
    rows = [normalise(r) for r in (freed or ())]
    rows = [r for r in rows if r["name"]]
    decorated = []
    for position, row in enumerate(rows):
        order = row["order"]
        stamp = row["freed_at"]
        primary = float(order) if isinstance(order, (int, float)) else None
        if primary is None and isinstance(stamp, (int, float)):
            primary = float(stamp)
        decorated.append((0 if primary is not None else 1,
                          primary if primary is not None else 0.0,
                          position, row))
    decorated.sort(key=lambda t: (t[0], t[1], t[2]))
    seen: set = set()
    out = []
    for _, _, _, row in decorated:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append(row)
    return out


# How big the scene is, and what the size changes. Five tiers, because the thing
# that actually differs between "some people" and "all of them" is how far the
# camera has to go to fit them in frame.

@dataclass(frozen=True)
class Scale:
    id: str
    label: str
    ranks: int                # how many rows deep the chorus stands
    pullback: float           # camera distance multiplier at the freeze frame
    ribbon: str               # the lower ribbon on the title card
    narration: str            # one line, said as they form up


SCALES = (
    Scale("NONE", "an empty gallery", 0, 1.0,
          "ONE ARCHITECT. NO WITNESSES.",
          "There is nobody behind you. There were people down there to be found "
          "and you went past the doors they were behind, and they are still in "
          "the niches, and the frame is still yours. All three of those are "
          "true at once and the game is not going to pick one for you."),
    Scale("A_FEW", "a few of them", 1, 1.25,
          "{count} FREED. THE OTHER SHELVES ARE STILL FULL.",
          "They come up the stair behind you and there is room on the stair, "
          "which there would not have been if you had gone through every door "
          "you walked past."),
    Scale("A_CROWD", "a crowd", 2, 1.6,
          "{count} FREED. EVERY ONE OF THEM IS STANDING BEHIND YOU.",
          "They come up the stair behind you in no order at all, the stair is "
          "not wide enough, and nobody minds."),
    Scale("THE_WHOLE_GALLERY", "the whole gallery", 3, 2.1,
          "{count} FREED. THE SHELVES ARE EMPTY.",
          "The shelves behind them are dark all the way to the back wall, which "
          "is the first time anyone alive has seen the back wall."),
    Scale("EVERY_LAST_ONE", "every last one of them", 4, 2.6,
          "EVERY LAST ONE. {count} OF {total}.",
          "Nobody is left in the rock. Not one niche, not one sphere still "
          "pointing, not one name filed anywhere it does not belong. You went "
          "and got all of them, and the stair is going to take a while."),
)

SCALE_BY_ID = {s.id: s for s in SCALES}


def scale_for(count: int, total: int = 0) -> str:
    """Which tier a roll call of this size plays at.

    With a known total it is a share, because "most of them" is a statement
    about the world. Without one it falls back to absolute counts and never
    claims completeness, because a denominator this module was not given is a
    denominator it does not get to invent.
    """
    if count <= 0:
        return "NONE"
    if total > 0:
        share = count / total
        if count >= total:
            return "EVERY_LAST_ONE"
        if share >= 0.66:
            return "THE_WHOLE_GALLERY"
        if share >= 0.33:
            return "A_CROWD"
        return "A_FEW"
    if count >= 20:
        return "THE_WHOLE_GALLERY"
    if count >= 8:
        return "A_CROWD"
    return "A_FEW"


# Speaking parts. At most four people get a line of their own, chosen by their
# position in the story rather than at random, so the same run always stages the
# same four and a client can cache the portraits.
#
# A person's OWN line always wins. These are the stage business for somebody the
# captives pass gave a name and nothing else, and every one of them is about the
# person rather than about the player, which is the rule.

POSITION_BUSINESS = {
    "first": "{name} reaches the stair before anybody else and then stops on the "
             "bottom step, because it turns out {name} had not planned any "
             "further ahead than the stair.",
    "last": "{name}'s name is the last one read out and {name} has therefore had "
            "the longest wait of anyone in the room. {name} intends to describe "
            "that wait. {name} describes it for the entire climb.",
    "useful": "{name} is talking about the work before the room has finished "
              "emptying — what needs doing first, who needs telling, and in "
              "which order, with a degree of certainty nobody else in the stair "
              "currently has about anything.",
    "home": "{name} asks whether {region} is still there. Nobody on the stair "
            "has the answer. {name} decides that this means going and looking.",
}

POSITION_LABEL = {
    "first": "the first one you freed",
    "last": "the last one you freed",
    "useful": "the one who is already back at work",
    "home": "the one asking after home",
}


def _speakers(rows: list, *, weak_regions=()) -> list:
    """Up to four, by position, never duplicated.

    `weak_regions` is the player's thinnest evidence, which is where the "asking
    after home" slot comes from: the region this player has least to show for is
    the one whose survivor gets to ask whether it is still standing.
    """
    if not rows:
        return []
    chosen: dict = {}

    def take(key: str, candidates) -> None:
        """First candidate not already cast. A person speaks once."""
        if key in chosen:
            return
        spoken = {r["id"] for r in chosen.values()}
        for row in candidates:
            if row and row["id"] not in spoken:
                chosen[key] = row
                return

    take("first", rows[:1])
    take("last", reversed(rows))
    take("useful", [r for r in rows if r["boon"]])
    take("home", [r for r in rows if r["region"] in set(weak_regions or ())])

    out = []
    for key in ("first", "last", "useful", "home"):
        row = chosen.get(key)
        if not row:
            continue
        text = row["line"] or POSITION_BUSINESS[key].format(
            name=row["name"], region=row["region_name"] or "the region")
        out.append({**row, "position": key, "position_label": POSITION_LABEL[key],
                    "speaks": text, "own_words": bool(row["line"])})
    return out


# The roll call has a ceiling. Beyond SPOKEN_MAX the names still all get read —
# every single one, that is the entire point of the scene — but they scroll
# rather than landing one at a time, because a list of forty names at nine
# hundred milliseconds each is four minutes of a player watching a list.
SPOKEN_ROW_MS = 900
FAST_ROW_MS = 260
SPOKEN_MAX = 12
ROLL_CALL_CAP_MS = 30000


def roll_call(freed, *, total: int = 0, weak_regions=()) -> dict:
    """Everyone the player freed, in rescue order, staged for the scene."""
    rows = _sorted_rows(freed)
    count = len(rows)
    total = max(int(total or 0), count)
    scale = SCALE_BY_ID[scale_for(count, total)]

    spoken = rows[:SPOKEN_MAX]
    scrolled = rows[SPOKEN_MAX:]
    duration = len(spoken) * SPOKEN_ROW_MS + len(scrolled) * FAST_ROW_MS
    duration = min(duration, ROLL_CALL_CAP_MS)
    if count:
        duration = max(duration, SPOKEN_ROW_MS)

    by_region: dict = {}
    for row in rows:
        by_region.setdefault(row["region"] or "", []).append(row["name"])

    return {
        "count": count,
        "total": total,
        "share": round(count / total, 3) if total else 0.0,
        "scale": scale.id,
        "scale_label": scale.label,
        "ranks": scale.ranks,
        "pullback": scale.pullback,
        "rows": rows,
        "spoken": spoken,
        "scrolled": scrolled,
        "speakers": _speakers(rows, weak_regions=weak_regions),
        "by_region": {k: v for k, v in by_region.items() if k},
        "regions": len([k for k in by_region if k]),
        "duration_ms": duration,
        "ribbon": scale.ribbon.format(count=count, total=total),
        "narration": scale.narration,
    }


# ---------------------------------------------------------------------------
# 3. The evidence
# ---------------------------------------------------------------------------
#
# The send-off is only worth saying if it is true, so every number in it is
# lifted from something that measured it and nothing in here computes a number
# of its own. Four sources, all of them already in the engine's hands at the
# moment this scene fires:
#
#   finalexam.debrief(...)      the practical just sat: solved, total, verdict,
#                               within the clock, and the drills
#   adaptive.readiness(...)     the thirteen gates
#   transfer.summarise(...)     cold, unfamiliar, hold-out problems cleared
#                               unaided, with its sample and its band
#   the cleared boss set        how many rungs of the crutch ladder were taken
#                               before the player ever reached the last room
#
# Anything missing degrades to silence about that fact rather than a guess.

VERDICT_ORDER = {"": 0, "NOT_READY": 1, "CLOSE": 2, "READY": 3}


def _ladder_evidence(cleared_bosses) -> dict:
    """How much of the apparatus was already gone before the last door."""
    cleared = set(cleared_bosses or ())
    rungs = [seal for seal in finalexam.BOSS_LADDER if seal.boss_id in cleared]
    taken: list = []
    for seal in rungs:
        for crutch_id in seal.takes:
            crutch = finalexam.CRUTCH_BY_ID[crutch_id]
            taken.append({"id": crutch.id, "name": crutch.name,
                          "boss": seal.label, "rung": seal.rung})
    return {
        "rungs_cleared": len(rungs),
        "rungs_total": len(finalexam.BOSS_LADDER),
        "crutches_taken": taken,
        "crutches_taken_count": len(taken),
        "crutches_total": len(finalexam.CRUTCHES),
    }


def evidence(*, exam_report: dict | None = None, readiness: dict | None = None,
             transfer_summary: dict | None = None, cleared_bosses=()) -> dict:
    """Every number the send-off is allowed to use, in one place."""
    report = exam_report or {}
    verdict = (report.get("verdict") or {}).get("code", "")
    gates = readiness or {}
    cold = transfer_summary or {}
    open_gates = [g["label"] for g in gates.get("gates", ()) if not g.get("passed")]

    return {
        "measured": bool(report),
        "verdict": verdict,
        "solved": report.get("solved"),
        "total": report.get("total"),
        "score": report.get("score"),
        "within_clock": report.get("within_clock"),
        "clock": report.get("clock", ""),
        "format_label": report.get("format_label", ""),
        "drills": list(report.get("drills", ()))[:3],
        "dominant_signal": report.get("dominant_signal", ""),
        "signal_note": report.get("signal_note", ""),

        "gates_passed": gates.get("gates_passed"),
        "gates_total": gates.get("gates_total"),
        "gates_open": open_gates[:4],

        "transfer_measured": bool(cold.get("measured")),
        "transfer_score": cold.get("score"),
        "transfer_sample": cold.get("sample"),
        "transfer_cleared": cold.get("cleared"),
        "transfer_band": (cold.get("band") or {}).get("text", ""),
        "transfer_confidence": transfer.CONFIDENCE,
        "transfer_min_sample": transfer.MIN_SAMPLE,

        **_ladder_evidence(cleared_bosses),
    }


def _cold_clause(ev: dict) -> str:
    """What the hold-out has to say, if it has earned the right to say it."""
    if ev["transfer_measured"]:
        return (f"You have also cleared {ev['transfer_cleared']} of "
                f"{ev['transfer_sample']} problems you had never seen in any "
                f"form, cold, with nothing switched on — {ev['transfer_score']}%, "
                f"{ev['transfer_confidence']} confidence {ev['transfer_band']}. "
                "That is the number that answers the question an interview is "
                "actually asking.")
    sample = ev["transfer_sample"]
    if sample:
        return (f"The hold-out has seen {ev['transfer_cleared']} of {sample} "
                "cleared cold so far, which is too small a sample to be a "
                "percentage and is reported as a count for exactly that reason.")
    return ""


def _ladder_clause(ev: dict) -> str:
    if not ev["crutches_taken_count"]:
        return ""
    return (f"{ev['crutches_taken_count']} of the {ev['crutches_total']} things "
            "this game gives you were taken off you one at a time by things you "
            f"beat, across {ev['rungs_cleared']} of {ev['rungs_total']} rungs, "
            "before you ever walked down that stair.")


# The line itself. Said over the freeze frame, by the narrator, in the register
# the whole ending is in — and never the same sentence twice, because the four
# branches are four genuinely different pieces of news.

def _celebration(roll: dict | None) -> str:
    """The win, stated first, in the size it actually was.

    Every branch except the pass opens on this, because the win is real and is
    not conditional on the result. It is also not allowed to describe a crowd
    that is not there.
    """
    count = (roll or {}).get("count", 0)
    if count >= 2:
        return ("Everyone on this stair is on this stair because of you. That "
                "part is finished and nothing below it is a condition on it.")
    if count == 1:
        return ("There is one person walking up that stair who was a filed "
                "entry an hour ago. That part is finished and nothing below it "
                "is a condition on it.")
    return ("You sat the last practical in the world with every single thing "
            "switched off, and you finished it. That happened, it counts, and "
            "nothing under this sentence takes it back.")


def readiness_line(ev: dict, roll: dict | None = None) -> dict:
    """The send-off, from the numbers, in as many words.

    READY says the thing plainly and proudly, because by that point it is a
    statement backed by evidence and hedging it would be a lie in the other
    direction. The other three celebrate the win first — the win is real and it
    is not conditional on the result — and then say the honest thing, with the
    shortest route attached.
    """
    verdict = ev["verdict"]
    solved, total = ev["solved"], ev["total"]
    cold = _cold_clause(ev)
    ladder = _ladder_clause(ev)

    if verdict == "READY":
        body = [
            "You are ready to sit a real Python interview.",
            "Not nearly. Not with a bit more practice. Ready.",
            f"You sat a timed practical with every one of the "
            f"{ev['crutches_total']} crutches removed and solved {solved} of "
            f"{total} inside the clock, with no hint, no probe, no companion, no "
            "pattern label and nobody standing behind you.",
        ]
        if ladder:
            body.append(ladder)
        if cold:
            body.append(cold)
        if ev["gates_total"]:
            body.append(f"{ev['gates_passed']} of {ev['gates_total']} readiness "
                        "gates are met, and gates do not move on exposure.")
        body.append("That is not encouragement. It is a measurement, taken by "
                    "something with no ability to flatter you, and it says you "
                    "can do this. Go and book the interview.")
        return {"code": "READY", "headline": "GO AND BOOK IT",
                "lines": body, "celebrates": True,
                "drills": [], "honest": ""}

    if verdict == "CLOSE":
        body = [
            _celebration(roll),
            "Now the measurement, plainly, because you have not been lied to "
            "yet and this would be a poor place to start.",
            f"You solved {solved} of {total} unaided. That is the band where "
            "people pass one week and fail the next, which is not yet a result "
            "you can plan around.",
        ]
        if cold:
            body.append(cold)
        body.append("Sit it again after the drills below, on a set you have "
                    "never seen, and look for the same number twice. Two results "
                    "a fortnight apart is readiness. One is a good day.")
        return {"code": "CLOSE", "headline": "CLOSE, AND NOT YET TWICE",
                "lines": body, "celebrates": True,
                "drills": ev["drills"],
                "honest": "The knowledge is largely there. The reliability is "
                          "the thing still being measured, because it is the "
                          "thing the interview measures too."}

    if verdict == "NOT_READY":
        body = [
            _celebration(roll),
            "And you are not ready to sit this format yet. Plainly, because the "
            "alternative is a game that tells you what you want to hear and then "
            "lets a stranger tell you on a Tuesday.",
            f"You solved {solved} of {total} with nothing to lean on.",
        ]
        if ev["signal_note"]:
            body.append(ev["signal_note"])
        body.append("None of that is a verdict on whether you can do the job. "
                    "All of it moves, all of it is listed below with what to do "
                    "about it, and the practical recomposes — the next one is a "
                    "different set of questions, not this one again.")
        return {"code": "NOT_READY", "headline": "NOT YET, AND HERE IS THE ROUTE",
                "lines": body, "celebrates": True,
                "drills": ev["drills"],
                "honest": "The gap is not effort and it is not talent. It is "
                          "evidence: specific skills failed in specific ways and "
                          "every one of them has a drill with a number on it."}

    # No practical on record. The scene can still be reached by a client that
    # plays it out of order, and it is not going to invent a result.
    body = [
        _celebration(roll),
        "There is no practical on record for this save, so there is no line "
        "here about whether you could sit an interview tomorrow — that sentence "
        "is only worth saying when something measured it.",
        "The practical is under the castle, it takes about two hours, and it is "
        "the one capability check in this entire game. Nothing else here counts "
        "and nothing else here claims to.",
    ]
    if ladder:
        body.insert(1, ladder)
    return {"code": "UNMEASURED", "headline": "THE MEASUREMENT IS STILL OPEN",
            "lines": body, "celebrates": True, "drills": [],
            "honest": "Sit it. Pass or fail, this scene plays again with a "
                      "sentence in it that is about you."}


# ---------------------------------------------------------------------------
# 4. The title card
# ---------------------------------------------------------------------------
#
# Chrome bevel, drop shadow, too many spikes — docs/09-story-bible.md §8, which
# specifies the boss title cards, and this is the last one and therefore the
# biggest. It slams in on the same frame as the guitar hit and the freeze, all
# three on one millisecond, because that is how the records did it.
#
# The transformation phrase earned in Chapter IV is BY THE SOURCE — I NAME IT.
# The card is its completed form, said by the world instead of by the player.
#
# THE ONE EXCLAMATION MARK IN THIS FILE IS ON THIS CARD. It is here because an
# 80s end-card shout is the one place in this project that has ever earned one,
# and `validate()` fails if a second one appears anywhere in this module.

TITLE_CARD = {
    "eyebrow": "THE LONG COMPILE",
    "slab": "BY THE SOURCE — IT IS NAMED",
    "shout": "AND THE WORLD ANSWERED!",
    "stinger": "A PRODUCTION OF THE GREY REPOSITORY",
    "style": {
        "bevel": "chrome",
        "bevel_steps": 5,              # bone, chrome, mid, shadow, near-black
        "drop_shadow": {"dx": 6, "dy": 8, "colour": "#0a0a0c"},
        "spikes": 11,                  # too many, deliberately
        "outline": "#0a0a0c",
        "faces": ["#f2ead8", "#cfd4dc", "#8f98a6", "#4a5260"],
        "rim": "#ff8a2b",              # the one hot rim light, from below
        "slam_ms": 90,                 # how long the card takes to arrive
        "overshoot": 1.08,             # and how far past its mark it goes first
        "letterbox": True,
    },
}


def title_card(roll: dict, ev: dict) -> dict:
    """The card, with the ribbon the roll call earned.

    Only the ribbon changes. The slab and the shout are the same for every
    player who reaches this room, because what they are shouting about is the
    thing the player did rather than the size of the audience for it.
    """
    card = {k: v for k, v in TITLE_CARD.items() if k != "style"}
    card["style"] = dict(TITLE_CARD["style"])
    card["ribbon"] = roll["ribbon"]
    card["verdict"] = ev["verdict"] or "UNMEASURED"
    return card


# ---------------------------------------------------------------------------
# 5. The names that answer back
# ---------------------------------------------------------------------------
#
# docs/09-story-bible.md §5: the turn comes when every name the player gave
# anything, all game, answers back. That is the player's own identifiers, out of
# their own submissions, which the engine already stores.
#
# Two rules, and the second one is not optional. First, identifiers only —
# nothing that is not a bare Python name gets near this rail, so no fragment of
# anybody's code can arrive on screen by accident. Second, nothing from a
# hold-out problem, ever: the caller filters those out, and this filter is a
# second gate rather than the first one. See WIRING §6.

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{1,23}$")

# Names the player did not choose. Reading `self` back to somebody as a thing
# they named is both untrue and faintly insulting.
_NOT_YOURS = frozenset({
    "self", "cls", "args", "kwargs", "i", "j", "k", "n", "x", "y", "z", "_",
    "main", "test", "solution", "result", "res", "tmp", "temp", "foo", "bar",
    "data", "value", "val", "item", "out", "ret", "ans",
}) | frozenset(keyword.kwlist) | frozenset(dir(builtins))

NAME_RAIL_MAX = 24


def clean_names(names) -> list:
    """The identifiers worth reading back, deduplicated, order preserved."""
    out: list = []
    seen: set = set()
    for raw in names or ():
        text = str(raw).strip()
        if not _IDENT.match(text):
            continue
        if text.lower() in _NOT_YOURS or text in _NOT_YOURS:
            continue
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
        if len(out) >= NAME_RAIL_MAX:
            break
    return out


# ---------------------------------------------------------------------------
# 6. The cutscene, as data
# ---------------------------------------------------------------------------
#
# A renderer drives this and never has to guess. Three closed vocabularies —
# camera, stage, fx — plus absolute timings in milliseconds from the first
# frame. `validate()` fails if a beat uses a word that is not in one of them,
# which is the difference between a specification and a suggestion.

CAMERA_MOVES = (
    "HOLD",          # locked, no movement
    "PUSH_IN",       # dolly toward the subject
    "PULL_BACK",     # dolly away, revealing
    "TRACK_LEFT",    # lateral, along the niches
    "CRANE_UP",      # rise, tilting down
    "WHIP_PAN",      # fast horizontal, motion-blurred, used once
    "LOCK_OFF",      # settle hard onto the tableau and stop
    "FREEZE",        # the frame stops. the only beat that uses it
    "AERIAL",        # high and slow, over the world
    "CUT",           # no move; a hard cut to a new subject
)

STAGE_ROLES = (
    "architect",     # the player
    "freed",         # everyone on the roll call, in ranks
    "niches",        # the shelves, lit or dark
    "interpreter",   # THE LAST INTERPRETER, coiled through the floor
    "mentors",       # the surviving mentors, silhouetted at the back
    "companions",    # companion sprites, same rank as the mentors
    "llama",         # PLAIN, who is in shot far more than is reasonable
    "pel",           # the child in the village square, in the coda
    "world",         # the regions, from above
    "black",         # nothing. a field of near-black and one cursor
)

FX = (
    "rim_light_low",     # the one hot rim light, from a low source
    "green_index_lit",   # the spheres, still pointing
    "green_index_out",   # the spheres go dark, one per name read
    "name_rail",         # the player's own identifiers, scrolling in chrome
    "palette_blowout",   # drop to four colours on the freeze
    "letterbox",
    "title_card",
    "sunglasses",
    "wind_from_below",
    "dust",
    "dawn",
    "cursor_blink",
    "guitar_hit",        # the flash that lands on the same frame as the sound
)

# Music is a track name from web/js/audio.js TRACKS, or "cut" for silence, or ""
# to leave whatever is playing alone. No new music is required by this scene.
MUSIC_FINAL = "final"
MUSIC_VICTORY = "victory"
MUSIC_CLEAN = "town"

# The guitar hit. web/js/audio.js has no cue for this yet, so the contract is
# explicit: add ONE case to its `sfx` switch. Until it exists, a client falls
# back to `crit`, which is a pinch harmonic over a chord stab and is the closest
# thing already in the rig. WIRING §7 carries the recipe.
GUITAR_HIT_CUE = "finale_hit"
GUITAR_HIT_FALLBACK = "crit"

ACT_INDEX = "I. The Standing Index"
ACT_ROLL = "II. The Roll Call"
ACT_FRAME = "III. The Freeze Frame"
ACT_CODA = "IV. The Long Defeat"


@dataclass
class Beat:
    id: str
    act: str
    duration_ms: int
    camera: dict
    stage: tuple = ()
    lines: tuple = ()
    fx: tuple = ()
    music: str = ""
    sfx: tuple = ()
    note: str = ""
    rows: tuple = ()               # roll-call rows, when the beat has them
    skippable: bool = True
    at_ms: int = 0                 # filled in by the builder

    def to_dict(self) -> dict:
        return {
            "id": self.id, "act": self.act, "at_ms": self.at_ms,
            "duration_ms": self.duration_ms, "camera": dict(self.camera),
            "stage": list(self.stage), "lines": [dict(l) for l in self.lines],
            "fx": list(self.fx), "music": self.music, "sfx": list(self.sfx),
            "note": self.note, "rows": [dict(r) for r in self.rows],
            "skippable": self.skippable,
        }


def _say(text: str, *, who: str = "narrator", name: str = "",
         kind: str = "prose") -> dict:
    """One line. `kind` is prose, code or stage — the renderer sets type in the
    monospace face for code and in italics for stage business."""
    return {"speaker": who, "name": name, "text": text, "kind": kind}


def _interpreter(text: str, *, kind: str = "code") -> dict:
    who = finalexam.examiner()
    return _say(text, who=who.id, name=who.name, kind=kind)


def _pel_line() -> str:
    """Her own line, from the module that owns her, or the literal if that
    module is not importable from here."""
    try:                                     # pragma: no cover - import shape
        from . import quests
        return quests.NPCS["pel"]["line"]
    except Exception:                        # pragma: no cover
        return "I am not lost. I am doing a route."


def _closing_line() -> str:
    """The last line of the game is the Interpreter's own last line, quoted
    back. finalexam owns it; this module does not keep a second copy."""
    closing = finalexam.examiner().closing
    return closing[-1] if closing else ""


def _act_one(roll: dict) -> list:
    return [
        Beat(
            id="index_floor", act=ACT_INDEX, duration_ms=3400,
            camera={"move": "HOLD", "subject": "niches", "angle": "low",
                    "lens": "wide"},
            stage=("architect", "niches"),
            fx=("rim_light_low", "green_index_lit", "dust"),
            music=MUSIC_FINAL,
            note="Rows of niches cut into rock, receding past the light. One "
                 "figure at the near end, small in frame. Nothing moves.",
            lines=(
                _say("The room under the room is shelves. Not cells — shelves, "
                     "cut in rows, each one the size of a person standing up."),
                _say("The Null King never kept a prisoner in his life. He kept "
                     "entries, and an entry does not need a door, a guard or a "
                     "lock. It needs somewhere to be looked up from."),
                _say("Everyone you carried out of a boss chamber is standing in "
                     "one of these. Upright. Awake. Unable to tell you their own "
                     "name, because their name is not on them any more."),
            ),
        ),
        Beat(
            id="the_green_shelf", act=ACT_INDEX, duration_ms=2800,
            camera={"move": "PUSH_IN", "subject": "niches", "to": "one_sphere",
                    "ease": "slow"},
            stage=("niches",),
            fx=("green_index_lit", "rim_light_low"),
            note="Push in until a single sphere fills a third of the frame. It "
                 "is the only green in the palette and it is lit from inside.",
            lines=(
                _say("The small green sphere you have been finding in other "
                     "people's hands since the second chapter is on a shelf in "
                     "every niche, at chest height, pointing."),
                _say("It was always a pointer. It started as an off-by-one joke "
                     "in a quest about a miscounted convoy, and it stopped being "
                     "funny somewhere around the seventh region."),
            ),
        ),
        Beat(
            id="nothing_answered", act=ACT_INDEX, duration_ms=3600,
            camera={"move": "PULL_BACK", "subject": "interpreter",
                    "reveal": "the floor is not the floor", "ease": "slow"},
            stage=("architect", "niches", "interpreter"),
            fx=("rim_light_low", "green_index_lit"),
            note="The pull-back reveals the coils running under the whole room. "
                 "Same read as the practical's arrival: the floor resolves into "
                 "the animal a beat later than the player expects.",
            lines=(
                _say("An index exists to answer on your behalf. That is the "
                     "whole of what it is for and it is the entire reason "
                     "anybody built one."),
                _say("For the last two hours, in the room directly above this "
                     "one, nothing answered on your behalf."),
                _say("So this is a lookup with nothing on the other end of it, "
                     "and it has been that since you sat down. It is only "
                     "finding out now."),
            ),
        ),
    ]


# The nouns the rail's own sentence already uses. Reading one of them back as
# "the one you called X" makes the line stutter, so the pick steps over them.
_RAIL_ECHOES = frozenset({"counter", "counters", "frontier", "frontiers",
                          "left", "right"})


def _rail_pick(rail: list) -> str:
    """One identifier to say out loud, chosen not to collide with the sentence
    that is about to say it."""
    for name in rail:
        if name.lower() not in _RAIL_ECHOES:
            return name
    return rail[0]


def _act_two(roll: dict, names: list) -> list:
    beats = [
        Beat(
            id="the_prompt", act=ACT_ROLL, duration_ms=2600,
            camera={"move": "CUT", "subject": "interpreter", "framing": "head",
                    "note": "past the fourth turn. the hat is in shot."},
            stage=("interpreter",),
            fx=("rim_light_low",),
            music=MUSIC_FINAL,
            lines=(
                _interpreter(">>> for name in index: print(name)"),
                _say("It is not a rescue and it would not accept the word. It is "
                     "the only kind of sentence it knows how to make, and it has "
                     "been holding these in memory for nine hundred years, "
                     "because that is what a process does while it is still "
                     "running."),
            ),
        ),
    ]

    if roll["count"]:
        beats.append(Beat(
            id="roll_call", act=ACT_ROLL, duration_ms=roll["duration_ms"],
            camera={"move": "TRACK_LEFT", "subject": "niches",
                    "rows": len(roll["spoken"]), "then": "scroll",
                    "speed": "one niche per row"},
            stage=("niches", "freed"),
            fx=("green_index_out", "rim_light_low"),
            rows=tuple(roll["rows"]),
            skippable=False,
            note="One row per person, in rescue order. On each row: the name "
                 "prints in the monospace face, that niche's sphere goes dark, "
                 "and the person in it steps down. The first "
                 f"{SPOKEN_MAX} land one at a time at {SPOKEN_ROW_MS}ms; the "
                 f"rest scroll at {FAST_ROW_MS}ms. Every name is read. That is "
                 "the point of the beat and it is not allowed to be summarised.",
            lines=(_say("It prints them."),),
        ))
    else:
        beats.append(Beat(
            id="roll_call_empty", act=ACT_ROLL, duration_ms=4600,
            camera={"move": "TRACK_LEFT", "subject": "niches",
                    "note": "the whole track, to the back wall, at full length. "
                            "do not shorten it because it is empty."},
            stage=("niches",),
            fx=("rim_light_low", "dust"),
            skippable=False,
            note="The camera makes the same move it would have made for forty "
                 "people. There is nothing in any of the niches.",
            lines=(
                _say("The loop runs. The loop is correct."),
                _say("It terminates immediately, because the index is empty, "
                     "because you did not go and get anybody, and an empty "
                     "sequence is not an error."),
                _interpreter(">>> "),
            ),
        ))

    if roll["speakers"]:
        beats.append(Beat(
            id="the_speakers", act=ACT_ROLL,
            duration_ms=2200 * len(roll["speakers"]),
            camera={"move": "CUT", "subject": "freed",
                    "shots": len(roll["speakers"]), "framing": "portrait"},
            stage=("freed",),
            fx=("rim_light_low",),
            rows=tuple(roll["speakers"]),
            note="One portrait per speaker, in the order given. Each row "
                 "carries `speaks` — say that and nothing else. `own_words` "
                 "is True when the line was written for that person by the "
                 "module that owns them, which is most of them.",
            lines=tuple(
                _say(row["speaks"], who=row["id"], name=row["name"])
                for row in roll["speakers"]),
        ))

    rail = tuple(names)
    beats.append(Beat(
        id="the_names_answer", act=ACT_ROLL, duration_ms=4200,
        camera={"move": "WHIP_PAN", "subject": "world",
                "note": "up and out through the castle, every region in one "
                        "move. the only whip pan in the scene."},
        stage=("world",),
        fx=("name_rail", "rim_light_low") if rail else ("rim_light_low",),
        rows=tuple({"name": n} for n in rail),
        music=MUSIC_FINAL,
        note="The turn. Story bible §5: every name the player gave anything "
             "answers back. The rail is the player's own identifiers, out of "
             "their own submissions, set in chrome and moving fast enough to "
             "be a texture rather than a list.",
        lines=(
            _say("And then the other names arrive. Not people. The ones you "
                 "wrote."),
            _say("Every name you gave anything in this language, in every room "
                 "of this world, all of them at once, answering to themselves — "
                 "because a name that points at the right thing has never "
                 "needed anybody's permission to go on doing it."
                 if not rail else
                 "Every name you gave anything in this language, in every room "
                 "of this world — the counters, the frontiers, the left and "
                 "the right, the one you called " + _rail_pick(rail) + ", which "
                 "is still pointing at exactly the thing you pointed it at — "
                 "all of them at once, answering to themselves."),
            _say("This is the part the Null King could not do. It could return "
                 "anything it had already been handed. It could not name one "
                 "new thing, not once, not in nine hundred years, and you have "
                 "done it in every room you have walked into since the fence."),
        ),
    ))
    return beats


def _route_count(n: int) -> str:
    """The drill list, counted honestly. finalexam hands back at most four and
    this scene shows at most three, so the sentence has to be able to say one."""
    if n == 1:
        return ("One thing. It is countable, which is the only reason it is "
                "worth writing down.")
    return (f"{n} things, in this order. All of them are countable, which is "
            "why they are worth reading twice.")


def _act_three(roll: dict, ev: dict, send_off: dict, card: dict) -> list:
    scale = SCALE_BY_ID[roll["scale"]]
    verdict_lines = finalexam.examiner_view(ev["verdict"])["verdict"]

    beats = [
        Beat(
            id="forming_up", act=ACT_FRAME, duration_ms=3200,
            camera={"move": "CRANE_UP", "subject": "architect",
                    "pullback": scale.pullback,
                    "note": "rise and back until the whole formation is in "
                            "frame. the pullback multiplier is the roll call's; "
                            "an empty gallery does not pull back at all."},
            stage=(("architect", "freed", "mentors", "companions", "llama")
                   if roll["count"] else
                   ("architect", "mentors", "companions", "llama")),
            fx=("rim_light_low", "dust"),
            music=MUSIC_FINAL,
            note="Formation: the Architect alone at the front. Behind, in "
                 f"{scale.ranks} rank(s), everyone on the roll call, in rescue "
                 "order left to right. Behind them, silhouetted and unlit, the "
                 "surviving mentors and the companions — they were never taken "
                 "and they do not stand in the freed ranks. PLAIN is somewhere "
                 "in shot it should not be able to have reached.",
            lines=(_say(scale.narration),),
        ),
        Beat(
            id="the_turn", act=ACT_FRAME, duration_ms=1300,
            camera={"move": "LOCK_OFF", "subject": "architect",
                    "framing": "hero", "note": "settle hard and stop moving."},
            stage=(("architect", "freed", "mentors", "companions", "llama")
                   if roll["count"] else
                   ("architect", "mentors", "companions", "llama")),
            fx=("wind_from_below", "rim_light_low", "letterbox"),
            note="Everyone turns to face front on the same frame. Nobody "
                 "rehearsed it. Cloaks and hair go up, not sideways, because "
                 "the wind is coming from the stair.",
            lines=(),
        ),
        Beat(
            # The frame stops, the card lands and the guitar hits, all three on
            # this millisecond. Do not stagger them. The whole effect is that
            # they are simultaneous.
            id="freeze", act=ACT_FRAME, duration_ms=120,
            camera={"move": "FREEZE", "subject": "architect",
                    "note": "the frame stops. it does not slow down first."},
            stage=(("architect", "freed", "mentors", "companions", "llama")
                   if roll["count"] else
                   ("architect", "mentors", "companions", "llama")),
            fx=("guitar_hit", "palette_blowout", "title_card", "letterbox"),
            music="cut",
            sfx=(GUITAR_HIT_CUE,),
            skippable=False,
            note="Palette drops to four colours on this frame: near-black, "
                 "bone, chrome, hot orange. The title card slams in over the "
                 "top with an overshoot and settles. Music cuts dead — the "
                 "guitar hit is the only sound in the room.",
            lines=(),
        ),
        Beat(
            id="the_sunglasses", act=ACT_FRAME, duration_ms=1600,
            camera={"move": "FREEZE", "subject": "architect",
                    "note": "still frozen. nothing else may move."},
            stage=("architect", "llama"),
            fx=("sunglasses", "title_card", "palette_blowout", "letterbox"),
            music=MUSIC_VICTORY,
            note="One element animates inside a frozen frame, which is the "
                 "entire joke and it is played straight.",
            lines=(
                _say("Nothing in the frame moves, because the frame has "
                     "stopped. One thing moves anyway."),
                _say("The sunglasses come down. They were not there a moment "
                     "ago, there is nowhere on an Architect's kit to have kept "
                     "them, and nobody is going to explain them. They are not, "
                     "on any reading, load-bearing.", kind="stage"),
                _say("PLAIN has a pair as well. PLAIN has had a pair the entire "
                     "time.", kind="stage"),
            ),
        ),
    ]

    if verdict_lines:
        beats.append(Beat(
            id="the_value", act=ACT_FRAME, duration_ms=3000,
            camera={"move": "FREEZE", "subject": "interpreter",
                    "note": "inset, lower left, over the held frame."},
            stage=("interpreter",),
            fx=("title_card", "letterbox"),
            note="The examiner's own three lines for this verdict, owned by "
                 "finalexam.examiner_view and quoted here rather than copied. "
                 "First two are code, the third is prose.",
            lines=tuple(
                _interpreter(text, kind="code" if index < 2 else "prose")
                for index, text in enumerate(verdict_lines)),
        ))

    beats.append(Beat(
        id="the_readiness_line", act=ACT_FRAME, duration_ms=6500,
        camera={"move": "FREEZE", "subject": "architect",
                "note": "held frame, card still up, ribbon reading "
                        + card["ribbon"]},
        stage=("architect", "freed") if roll["count"] else ("architect",),
        fx=("title_card", "palette_blowout", "letterbox"),
        music=MUSIC_VICTORY,
        note="The send-off. Every number in it came from something that "
             "measured it; nothing here was computed by the finale. Render "
             "`headline` on the card's lower slab and the lines beneath.",
        lines=tuple(_say(text) for text in send_off["lines"]),
    ))

    if send_off["drills"]:
        beats.append(Beat(
            id="the_route", act=ACT_FRAME, duration_ms=4500,
            camera={"move": "FREEZE", "subject": "architect",
                    "note": "the card lifts; the drill list takes the lower "
                            "two thirds."},
            stage=("architect",),
            fx=("letterbox",),
            rows=tuple(send_off["drills"]),
            note="Straight off finalexam's debrief: cause, skill, where to go, "
                 "and a countable thing to do. Three at most, worst first. This "
                 "beat does not appear on a pass.",
            lines=(
                _say(send_off["honest"]),
                _say(_route_count(len(send_off["drills"]))),
            ),
        ))
    return beats


def _act_four(roll: dict, ev: dict) -> list:
    """The coda. It runs AFTER the triumph, it never interrupts it, and it is
    the part the story bible says the ending is actually about."""
    return [
        Beat(
            id="unfreeze", act=ACT_CODA, duration_ms=2400,
            camera={"move": "PULL_BACK", "subject": "architect",
                    "note": "the frame starts again. palette resolves back up "
                            "from four colours to the full ramp over 1200ms."},
            stage=(("architect", "freed") if roll["count"] else ("architect",)),
            fx=("dust",),
            music=MUSIC_CLEAN,
            note="Clean channel, no distortion. The record's last track always "
                 "does this and it is the reason anyone remembers the record.",
            lines=(
                _say("And then the frame starts again, which is the part they "
                     "never showed you, because a record ends and a world does "
                     "not."),
            ),
        ),
        Beat(
            id="the_world_is_not_restored", act=ACT_CODA, duration_ms=5200,
            camera={"move": "AERIAL", "subject": "world", "ease": "very slow",
                    "note": "dawn, low sun, over every region in unlock order. "
                            "Regions the player never cleared stay grey."},
            stage=("world",),
            fx=("dawn",),
            music=MUSIC_CLEAN,
            note="The honest half. It is not sad and it is not a punishment; it "
                 "is the size of the win, stated accurately.",
            lines=(
                _say("Most of what was erased stays erased."),
                _say("The Grey Repository holds what was saved, and what was "
                     "saved is not everything. It was never going to be "
                     "everything, and anyone who told you otherwise wanted "
                     "something from you."),
                _say("Three regions still have no word for the month after "
                     "harvest. Nobody now alive knows what the fourth colour "
                     "was called. The pass keeps the name you gave it, which is "
                     "not the name it had."),
                _say("You held a line for one generation. That is the size of "
                     "the win. It is a real win, and that is its real size."),
            ),
        ),
        Beat(
            id="the_one_you_teach", act=ACT_CODA, duration_ms=5000,
            camera={"move": "HOLD", "subject": "pel", "framing": "two-shot",
                    "angle": "child's eye line"},
            stage=("architect", "pel"),
            fx=("dawn",),
            music=MUSIC_CLEAN,
            note="Python Village square, morning, town tier as the save has it. "
                 "The rune-drill box is on the ground between them, open, and "
                 "the lines in it are in the wrong order.",
            lines=(
                _say(_pel_line(), who="pel", name="Pel"),
                _say("She has six loose lines in a box and no idea which order "
                     "they go in. You have until the light goes."),
                _say("This is the last thing the game asks of you and it is not "
                     "a boss. The Source does not come back by being defended. "
                     "It comes back by being said out loud to somebody small "
                     "enough to still be learning it."),
            ),
        ),
        Beat(
            id="the_moral", act=ACT_CODA, duration_ms=4600,
            camera={"move": "HOLD", "subject": "llama", "framing": "wide",
                    "note": "PLAIN is standing where PLAIN has no business "
                            "being. Do not explain how it got there."},
            stage=("architect", "pel", "llama"),
            fx=("dawn",),
            music=MUSIC_CLEAN,
            note="The moral, spoken in character, which is the closer every "
                 "episode of this gets and the reason the llama exists. Story "
                 "bible §6.3.",
            lines=(
                _say("Everyone in that room had their name taken by something "
                     "that offered to hold it for them. Nobody was tricked. It "
                     "was a good offer, they took it, and so would most people.",
                     who="llama", name="PLAIN"),
                _say("You got yours back the only way it has ever been done. By "
                     "doing the work yourself, in a room with nothing in it, on "
                     "a clock, while nothing answered for you.",
                     who="llama", name="PLAIN"),
                _say("There is no second way. There has never been a second "
                     "way. Go and teach the child.",
                     who="llama", name="PLAIN"),
                _say("It chews.", kind="stage"),
            ),
        ),
        Beat(
            id="the_prompt_stays", act=ACT_CODA, duration_ms=3200,
            camera={"move": "HOLD", "subject": "black", "framing": "centred"},
            stage=("black",),
            fx=("cursor_blink",),
            music="cut",
            skippable=False,
            note="Near-black. One prompt, centred, cursor blinking at 530ms. "
                 "Hold past the point of comfort, then cut to the title screen.",
            lines=(
                _interpreter(">>> "),
                _say(_closing_line()),
            ),
        ),
    ]


def _schedule(beats: list) -> list:
    """Absolute timings, and the one millisecond everything else hangs off."""
    at = 0
    for beat in beats:
        beat.at_ms = at
        at += beat.duration_ms
    return beats


def cutscene(*, freed=(), exam_report: dict | None = None,
             readiness: dict | None = None,
             transfer_summary: dict | None = None,
             cleared_bosses=(), names=(), total_captives: int = 0,
             weak_regions=(), encounter=None) -> dict:
    """The whole ending, as a payload a renderer can drive frame by frame.

    Everything optional is genuinely optional. With no arguments at all this
    returns a playable scene: an empty gallery, no send-off line about a
    measurement that never happened, and the same title card, because the card
    is about what the player did rather than about how many people watched.

    `encounter` is the live encounter, if there is one. If it is a measured run
    this refuses in the engine's own shape and returns nothing else, because a
    cutscene is a named voice and a named voice is the MENTOR crutch.
    """
    if encounter is not None and finalexam.sealed(encounter, FINALE_CAPABILITY):
        return finalexam.refuse(FINALE_CAPABILITY)

    roll = roll_call(freed, total=total_captives, weak_regions=weak_regions)
    ev = evidence(exam_report=exam_report, readiness=readiness,
                  transfer_summary=transfer_summary,
                  cleared_bosses=cleared_bosses)
    send_off = readiness_line(ev, roll)
    card = title_card(roll, ev)
    rail = clean_names(names)

    beats = _schedule(
        _act_one(roll)
        + _act_two(roll, rail)
        + _act_three(roll, ev, send_off, card)
        + _act_four(roll, ev))

    freeze = next(b for b in beats if b.id == "freeze")
    return {
        "id": "the_freeze_frame",
        "title": "THE LONG COMPILE — the last of it",
        "room": gallery_view(),
        "beats": [b.to_dict() for b in beats],
        "acts": [ACT_INDEX, ACT_ROLL, ACT_FRAME, ACT_CODA],
        "duration_ms": sum(b.duration_ms for b in beats),
        "freeze_at_ms": freeze.at_ms,
        "guitar_hit_at_ms": freeze.at_ms,
        "guitar_hit": {"cue": GUITAR_HIT_CUE, "fallback": GUITAR_HIT_FALLBACK,
                       "at_ms": freeze.at_ms},
        "title_card": card,
        "title_card_at_ms": freeze.at_ms,
        "roll_call": roll,
        "evidence": ev,
        "send_off": send_off,
        "name_rail": rail,
        "music": [MUSIC_FINAL, MUSIC_VICTORY, MUSIC_CLEAN],
        "camera_moves": list(CAMERA_MOVES),
        "stage_roles": list(STAGE_ROLES),
        "fx": list(FX),
        # Said out loud, next to the scene, so nobody wires it the wrong way
        # round: the exam is upstream of this and is not touched by it.
        "changes_nothing": (
            "This is the scene around the measurement. It does not gate the "
            "practical, it cannot change a verdict, and it plays whether the "
            "verdict was a pass or not. finalexam.py is unmodified."),
        "sealed": False,
    }


# ---------------------------------------------------------------------------
# 7. The API the engine actually calls
# ---------------------------------------------------------------------------


def available(*, exam_report: dict | None = None, cleared_bosses=()) -> dict:
    """Is the ending reachable, and if not, what is still owed.

    Read the direction of this carefully. The finale is gated BY the practical
    and never the other way round: sitting the practical requires nothing from
    this module, and a player who freed nobody sits exactly the same exam. What
    the roll call changes is who is standing in the frame afterwards.
    """
    cleared = set(cleared_bosses or ())
    final_boss = next((b["id"] for b in world.BOSSES if b.get("final")), "")
    sat = bool(exam_report)
    return {
        "open": sat,
        "sat_the_practical": sat,
        "final_boss_cleared": final_boss in cleared,
        "verdict": (exam_report or {}).get("verdict", {}).get("code", ""),
        "why": ("" if sat else
                "The ending plays when the practical has been sat. Pass or "
                "fail — the index empties because for two hours nothing "
                "answered for you, not because the result came back a "
                "particular way."),
        "note": "Nothing in this module is a prerequisite for the practical. "
                "The practical is a prerequisite for this module.",
    }


def record(state: dict, scene: dict) -> dict:
    """Write the bookkeeping after the scene has played. Never evidence."""
    block = ensure(state)
    if scene.get("error"):
        return block
    verdict = (scene.get("evidence") or {}).get("verdict", "")
    block["seen"] = True
    block["plays"] = int(block.get("plays", 0)) + 1
    block["last_verdict"] = verdict
    if VERDICT_ORDER.get(verdict, 0) > VERDICT_ORDER.get(block.get("best_verdict", ""), 0):
        block["best_verdict"] = verdict
    block["freed_at_finale"] = (scene.get("roll_call") or {}).get("count", 0)
    return block


def mark_coda_seen(state: dict) -> dict:
    """Set when the player reaches `the_prompt_stays` rather than when the
    freeze frame lands, because the two halves of this ending are separate and
    a player who skipped out at the title card has seen half of it."""
    block = ensure(state)
    block["coda_seen"] = True
    return block


def view(state: dict, **kwargs) -> dict:
    """Build the scene and write the bookkeeping, in one call.

    Everything `cutscene` takes, this takes. The only difference is that this
    one remembers it happened.
    """
    scene = cutscene(**kwargs)
    if state is not None:
        record(state, scene)
        scene["state"] = dict(ensure(state))
    return scene


# ---------------------------------------------------------------------------
# 8. Self-check
# ---------------------------------------------------------------------------
#
# Six claims are made above. All six are cheap to disprove, so they are checked
# rather than asserted in prose:
#
#   1. the scene plays at every roll-call size, including none
#   2. the camera, stage and fx vocabularies are closed and every beat obeys them
#   3. the freeze, the guitar hit and the title card land on one millisecond
#   4. the triumph is always before the coda, and the coda is always reached
#   5. the send-off says READY only when something measured READY
#   6. exactly one exclamation mark exists in this module, on the title card
#
# `python -m gauntlet.finale` runs it.

_MUSIC_OK = frozenset({"", "cut", MUSIC_FINAL, MUSIC_VICTORY, MUSIC_CLEAN})

_ACT_ORDER = (ACT_INDEX, ACT_ROLL, ACT_FRAME, ACT_CODA)

# Words that would mean a cutscene had started supplying answers. None of them
# has any business in a scene payload, and the audit is the same vocabulary
# finalexam uses so the two cannot drift apart.
_FORBIDDEN_KEYS = finalexam._MUST_BE_ABSENT


def _all_text(scene: dict) -> list:
    """Every authored string a player can see in one playthrough."""
    out = []
    for beat in scene["beats"]:
        out.append(beat["note"])
        for line in beat["lines"]:
            out.append(line["text"])
    card = scene["title_card"]
    out += [card["eyebrow"], card["slab"], card["shout"], card["stinger"],
            card["ribbon"]]
    out += scene["send_off"]["lines"]
    out.append(scene["send_off"]["headline"])
    out.append(scene["send_off"]["honest"])
    return [t for t in out if t]


def _walk_keys(node, found: list) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _FORBIDDEN_KEYS:
                found.append(key)
            _walk_keys(value, found)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _walk_keys(item, found)


def validate(scene: dict | None = None) -> list:
    """Every structural claim about one scene. Empty list means it holds."""
    problems: list = []
    scene = scene or cutscene()
    beats = scene["beats"]

    seen_ids: set = set()
    at = 0
    for beat in beats:
        if beat["id"] in seen_ids:
            problems.append(f"duplicate beat id: {beat['id']}")
        seen_ids.add(beat["id"])
        if beat["camera"].get("move") not in CAMERA_MOVES:
            problems.append(f"{beat['id']}: unknown camera move "
                            f"{beat['camera'].get('move')!r}")
        for role in beat["stage"]:
            if role not in STAGE_ROLES:
                problems.append(f"{beat['id']}: unknown stage role {role!r}")
        for effect in beat["fx"]:
            if effect not in FX:
                problems.append(f"{beat['id']}: unknown fx {effect!r}")
        if beat["music"] not in _MUSIC_OK:
            problems.append(f"{beat['id']}: unknown music {beat['music']!r}")
        if beat["at_ms"] != at:
            problems.append(f"{beat['id']}: timeline gap at {beat['at_ms']}ms")
        if beat["duration_ms"] <= 0:
            problems.append(f"{beat['id']}: zero duration")
        at += beat["duration_ms"]
        if beat["act"] not in _ACT_ORDER:
            problems.append(f"{beat['id']}: unknown act {beat['act']!r}")

    # Acts never interleave, and the coda is last.
    order = [_ACT_ORDER.index(b["act"]) for b in beats]
    if order != sorted(order):
        problems.append("acts are out of order")
    if not beats or beats[-1]["act"] != ACT_CODA:
        problems.append("the scene does not end in the coda")
    if beats and beats[-1]["id"] != "the_prompt_stays":
        problems.append("the last beat is not the prompt")

    # The three things that must land together.
    freeze = next((b for b in beats if b["id"] == "freeze"), None)
    if freeze is None:
        problems.append("there is no freeze frame")
    else:
        if GUITAR_HIT_CUE not in freeze["sfx"]:
            problems.append("the guitar hit is not on the freeze")
        if "title_card" not in freeze["fx"]:
            problems.append("the title card is not on the freeze")
        if scene["guitar_hit_at_ms"] != freeze["at_ms"]:
            problems.append("the guitar hit is not on the freeze frame's ms")
        if scene["title_card_at_ms"] != freeze["at_ms"]:
            problems.append("the title card is not on the freeze frame's ms")
        coda_start = next(b["at_ms"] for b in beats if b["act"] == ACT_CODA)
        if coda_start <= freeze["at_ms"]:
            problems.append("the coda arrives before the freeze frame")

    # The one exclamation mark.
    shouts = [t for t in _all_text(scene) if "!" in t]
    if shouts != [scene["title_card"]["shout"]]:
        problems.append(f"exclamation marks outside the title card: "
                        f"{[s for s in shouts if s != scene['title_card']['shout']][:2]}")

    # Nothing that could supply an answer.
    leaked: list = []
    _walk_keys(scene, leaked)
    if leaked:
        problems.append(f"answer-shaped keys in the payload: {sorted(set(leaked))}")

    # The send-off is honest about what measured it.
    send_off = scene["send_off"]
    verdict = scene["evidence"]["verdict"]
    if send_off["code"] == "READY" and verdict != "READY":
        problems.append("the send-off claims READY without a READY verdict")
    if verdict in ("", None) and send_off["code"] != "UNMEASURED":
        problems.append("a send-off was written without a measurement")
    if send_off["code"] != "READY" and not send_off["celebrates"]:
        problems.append("a non-pass does not celebrate the win")

    # Speaking parts.
    speakers = scene["roll_call"]["speakers"]
    if len(speakers) > 4:
        problems.append(f"{len(speakers)} speaking parts; the cap is four")
    for row in speakers:
        if not row["name"] or not row["speaks"]:
            problems.append(f"a speaker with no name or nothing to say: {row['id']}")

    return problems


def _fake_freed(count: int) -> list:
    """A roster shaped like the one the captives pass will hand over, built
    from the real regions and the real bosses so the staging is exercised
    against the world that exists rather than against invented ids."""
    rows = []
    bosses = world.BOSSES
    for index in range(count):
        boss = bosses[index % len(bosses)]
        rows.append({
            "id": f"freed_{index}",
            "name": f"Person {index}",
            "role": "smith" if index % 3 == 0 else "scout",
            "region": boss["region"],
            "boss_id": boss["id"],
            "order": index,
            # Two thirds arrive with their own words, as they will in the real
            # roster; the rest exercise the positional stage business.
            "line": "" if index % 3 == 0 else f"Person {index} has an opinion.",
            "boon": "works cheaper now" if index % 5 == 0 else "",
        })
    return rows


def _fake_report(code: str) -> dict:
    if not code:
        return {}
    solved = {"READY": 5, "CLOSE": 4, "NOT_READY": 1}[code]
    return {
        "solved": solved, "total": 6, "score": round(100 * solved / 6),
        "within_clock": code != "CLOSE", "clock": "1:52:10",
        "format_label": finalexam.THE_PRACTICAL.label,
        "verdict": {"code": code, "headline": "", "body": ""},
        "dominant_signal": "implementation",
        "signal_note": finalexam.BUCKET_MEANING["implementation"],
        "drills": [{"cause": "OFF_BY_ONE", "skill": "ARRAY", "occurrences": 2,
                    "do": finalexam.DRILL_ACTION["OFF_BY_ONE"],
                    "where": "the Village", "region": "python_village"}],
    }


def self_check() -> dict:
    """Play the ending at every size and every verdict and check all six
    claims. `ok` is the only field a caller needs."""
    failures: list = []
    sizes = (0, 1, 3, 7, 14, 21, 28, 40)
    verdicts = ("", "NOT_READY", "CLOSE", "READY")
    scenes = 0
    durations: list = []
    tiers: dict = {}

    cold = transfer.summarise(
        [{"resolved": True, "counted": True, "solved": i % 4 != 0,
          "skill": "ARRAY", "lineage_id": f"l{i}", "unaided": True,
          "first_encounter": True} for i in range(14)],
        remaining=83, holdout_total=97, lineages_total=97)
    gates = {"gates_passed": 11, "gates_total": 13,
             "gates": [{"id": "retention", "label": "Retains major patterns "
                        "after several days", "passed": False}]}
    cleared = [b["id"] for b in world.BOSSES[:11]]

    for size in sizes:
        for code in verdicts:
            scene = cutscene(
                freed=_fake_freed(size), exam_report=_fake_report(code),
                readiness=gates, transfer_summary=cold,
                cleared_bosses=cleared, total_captives=len(world.BOSSES) * 2,
                names=["seen", "window", "left", "right", "self", "counts", "i"],
                weak_regions=("graph_wastes",))
            scenes += 1
            durations.append(scene["duration_ms"])
            tiers[scene["roll_call"]["scale"]] = tiers.get(
                scene["roll_call"]["scale"], 0) + 1
            for problem in validate(scene):
                failures.append(f"[{size} freed / {code or 'unmeasured'}] {problem}")

            # 1. it plays at every size, and every name is read out.
            named = len(scene["roll_call"]["spoken"]) + len(scene["roll_call"]["scrolled"])
            if named != size:
                failures.append(f"[{size}] roll call reads {named} names")
            # 5. no claim the evidence does not support.
            if code != "READY" and "ready to sit a real Python interview" in " ".join(
                    scene["send_off"]["lines"]):
                failures.append(f"[{size}/{code}] claims readiness without it")
            if code == "READY" and "ready to sit a real Python interview" not in " ".join(
                    scene["send_off"]["lines"]):
                failures.append("a pass does not say the line")
            # The identifier rail drops what the player did not name.
            if "self" in scene["name_rail"] or "i" in scene["name_rail"]:
                failures.append("the name rail kept a name the player did not choose")

    # 3. the seal. A live measured run gets nothing out of this module.
    class _Enc:
        mode = config.MODE_INTERVIEW
        boss_id = ""
        holdout = False

    refused = cutscene(encounter=_Enc())
    if refused.get("error") != "sealed":
        failures.append("the cutscene is reachable inside a measured run")
    if "beats" in refused:
        failures.append("a refusal still carried the scene")

    # 4. the practical is untouched by anything in here.
    if finalexam.EXAM_SEAL.sealed != finalexam.ALL_CRUTCHES:
        failures.append("the exam seal changed")
    if finalexam.audit_seal():
        failures.append(f"crutches unsealed by the exam: {finalexam.audit_seal()}")
    if available(exam_report=None)["open"]:
        failures.append("the ending opens without a practical")
    if not available(exam_report=_fake_report("NOT_READY"))["open"]:
        failures.append("a failed practical does not open the ending")

    # State bookkeeping round-trips and never gates anything.
    save: dict = {}
    scene = cutscene(freed=_fake_freed(5), exam_report=_fake_report("CLOSE"))
    record(save, scene)
    record(save, cutscene(freed=_fake_freed(5), exam_report=_fake_report("READY")))
    record(save, cutscene(freed=_fake_freed(5), exam_report=_fake_report("NOT_READY")))
    if save[STATE_KEY]["best_verdict"] != "READY":
        failures.append("best_verdict does not keep the best result")
    if save[STATE_KEY]["plays"] != 3:
        failures.append("plays did not count three plays")

    return {
        "ok": not failures,
        "scenes": scenes,
        "tiers_exercised": sorted(tiers),
        "tier_counts": tiers,
        "shortest_ms": min(durations),
        "longest_ms": max(durations),
        "beats": len(cutscene(freed=_fake_freed(14),
                              exam_report=_fake_report("READY"))["beats"]),
        "exclamation_marks": 1,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# 9. Wiring
# ---------------------------------------------------------------------------

WIRING = """
WIRING gauntlet/finale.py — the integration contract. Nothing here is optional
and nothing here is a guess. This module edits no other file, holds no evidence,
and cannot change a grade.

0. THE DIRECTION OF THE GATE, SAID ONCE
   The practical gates the finale. The finale does not gate the practical.
   gauntlet/finalexam.py is unchanged by this pass and must stay that way: a
   player who freed nobody sits the same sealed, timed, unassisted exam and can
   pass it. If wiring this module ever makes the exam harder to reach, the
   wiring is wrong, not the exam.

1. SAVE STATE
   engine.DEFAULT_STATE gains one key:

       finale.STATE_KEY: finale.new_state()        # -> "finale"

   It holds {"seen", "plays", "best_verdict", "last_verdict",
   "freed_at_finale", "coda_seen"}. Plain JSON, round-trips through
   db.save_state untouched, BOOKKEEPING AND NOT EVIDENCE: a save that loses it
   replays a cutscene and loses nothing else. engine._merge forward-fills it;
   finale.ensure(state) does the same defensively on every call.

2. THE ONE CALL
   After the practical is scored — the same place engine hands back
   finalexam.debrief(...) — and NOT before:

       scene = finale.view(
           self.state,
           freed=captives.freed(self.state),        # see §3
           exam_report=report,                      # finalexam.debrief(...)
           readiness=ready,                         # adaptive.readiness(...)
           transfer_summary=cold,                   # transfer.summarise(...)
           cleared_bosses=self.state["bosses_cleared"],
           names=self._identifiers_named(),         # see §6
           total_captives=captives.total(),         # see §3
           weak_regions=self._weak_regions(),       # optional; see §4
           encounter=self.encounter)                # optional; see §5
       result["finale"] = scene

   Every argument is optional. `finale.cutscene()` with no arguments returns a
   playable scene, which is what a client gets before the captives pass lands.
   `view` is `cutscene` plus the bookkeeping write; `cutscene` alone is the pure
   function and is what tests should call.

   When the player reaches the last beat, call finale.mark_coda_seen(state) and
   save. Do it on `the_prompt_stays`, not on the freeze frame — the two halves
   of this ending are separate and a player who walked out at the title card has
   seen half of it.

3. THE CAPTIVES ARE NOT OWNED HERE
   This module stages people; another pass writes them. It reads each record
   through finale.normalise(), which accepts a dict OR an object and looks for
   any of these spellings, in this order:

       id      id / captive_id / npc_id / key
       name    name / display_name / who            <- the only required field
       trade   trade / role / job / craft / occupation
       region  region / region_id / home / from_region
       boss    boss / boss_id / taken_by / held_by
       sprite  sprite / portrait / art
       line    finale_line / line / says / greeting / first_words
       boon    boon / afterwards / service / help / consequence
       order   order / freed_order / rescued_order / index / sequence
       freed_at freed_at / rescued_at / timestamp / when

   A record with nothing but a name still stages. `line` is what that person
   says in the freeze-frame scene and it ALWAYS wins over the positional stage
   business in finale.POSITION_BUSINESS — write them a finale_line and they say
   their own words. `boon` is what they do for the player afterwards and it is
   what selects the "already back at work" speaking part.

   `total_captives` is the size of the full roster, and it is what lets the
   title card say EVERY LAST ONE rather than a bare count. Without it the tiers
   fall back to absolute counts and the scene never claims completeness.

4. weak_regions (OPTIONAL)
   The region ids this player has the least evidence in, worst first. It selects
   one speaking part — the survivor who asks whether home is still standing.
   adaptive/skills already computes the weakest skills; map them to regions with
   world.REGIONS. Omit it and that part simply is not cast.

5. THE SEAL
   One capability check, and it is finalexam.sealed, the same one every other
   module asks. Pass the live encounter into `cutscene`/`view`:

       finale.cutscene(..., encounter=self.encounter)

   If that encounter is a measured run or hold-out content, this returns
   finalexam.refuse("MENTOR") — {"error": "sealed"} — and nothing else. A
   cutscene is a named voice speaking to you, which is exactly the MENTOR
   crutch, so it refuses on the MENTOR rung and does not invent a new one.
   tests/test_interview_isolation.py should be extended by one line for it.

6. names — THE IDENTIFIER RAIL (OPTIONAL)
   docs/09-story-bible.md §5 asks for the player's own variable names to answer
   back. Pass a list of identifiers harvested from their accepted submissions,
   newest first. THREE RULES, and the second one is the caller's job:

     * Identifiers only. finale.clean_names() enforces it with a regex and will
       drop anything that is not a bare Python name, so no code fragment can
       reach the screen by accident.
     * NOTHING FROM A HOLD-OUT PROBLEM. Filter on problem.sealed before you pass
       the list. The rail is decoration; the hold-out is a measurement, and a
       measurement is worth more than a decoration.
     * Names the player did not choose are dropped here — self, cls, i, n, tmp,
       every keyword and every builtin — because reading `self` back to somebody
       as a thing they named is both untrue and faintly rude.

   Omit it and the beat plays with a slightly different line. Nothing breaks.

7. AUDIO — ONE NEW CUE
   The scene uses three existing tracks (`final`, `victory`, `town`) and asks
   web/js/audio.js for ONE new sfx case, `finale_hit`, the guitar hit that lands
   on the freeze frame. Until it exists, clients fall back to `crit`, which is
   already in the rig and is the closest thing to it. The recipe, in that file's
   own vocabulary:

       case 'finale_hit':
         this._power('E2', t, 1.60, 0.52);                  // root, held
         this._power('B2', t, 1.60, 0.44);                  // fifth, held
         guitar(freq('E5') * 2, t + 0.01, 1.40, 0.34, { bend: 3 });  // squeal
         this._crash(t, 0.85);
         this._kick(t, 1.0);
         break;

   Music cuts dead on the same frame. The hit is the only sound in the room.

8. THE RENDERER'S CONTRACT
   `scene["beats"]` is the whole spec, in order, with absolute `at_ms`. Three
   closed vocabularies, all shipped in the payload and all checked by
   finale.validate():

       camera.move   HOLD PUSH_IN PULL_BACK TRACK_LEFT CRANE_UP WHIP_PAN
                     LOCK_OFF FREEZE AERIAL CUT
       stage         architect freed niches interpreter mentors companions
                     llama pel world black
       fx            rim_light_low green_index_lit green_index_out name_rail
                     palette_blowout letterbox title_card sunglasses
                     wind_from_below dust dawn cursor_blink guitar_hit

   Each line is {"speaker", "name", "text", "kind"}; kind is prose, code or
   stage. Code is set in the monospace face, stage business in italics.

   `scene["freeze_at_ms"]`, `scene["guitar_hit_at_ms"]` and
   `scene["title_card_at_ms"]` are the same millisecond and validate() fails if
   they ever stop being. Do not stagger them. The whole effect is that they are
   simultaneous.

   Beats with `skippable: false` are the roll call, the freeze and the last
   beat. A skip control may pass over everything else and must not pass over
   those three.

9. SERVER ROUTE
   One GET, after the exam is over:

       GET /api/finale  -> finale.view(game.state, **the arguments in §2)

   Save afterwards, because `view` writes bookkeeping. It is safe to call more
   than once; a re-sit replays the scene with the new verdict in it, which is
   the correct behaviour and is why `plays` is a counter rather than a flag.

10. WHAT THIS MODULE WILL NEVER DO
   It never chooses a problem, never grants mastery, never touches the SRS
   schedule, never reads or writes a grade, and never returns a number it was
   not handed by something that measured one. Every figure in the send-off comes
   from finalexam.debrief, adaptive.readiness, transfer.summarise or the cleared
   boss set. If a sentence in this ending ever says something the player's own
   evidence does not support, that is a bug, and finale.validate() is where it
   should have been caught.
"""


if __name__ == "__main__":   # pragma: no cover - a maintenance entry point
    import json
    import sys

    _report = self_check()
    print(json.dumps({k: v for k, v in _report.items() if k != "failures"},
                     indent=1))
    for _line in _report["failures"]:
        print("FAIL:", _line)
    if "--scene" in sys.argv:
        _scene = cutscene(freed=_fake_freed(14),
                          exam_report=_fake_report("READY"),
                          total_captives=28)
        for _beat in _scene["beats"]:
            print(f"\n[{_beat['at_ms']:>6}ms +{_beat['duration_ms']:<5}] "
                  f"{_beat['act']} / {_beat['id']} / "
                  f"{_beat['camera']['move']}")
            for _line in _beat["lines"]:
                _who = _line["name"] or _line["speaker"]
                print(f"    {_who}: {_line['text']}")
    sys.exit(0 if _report["ok"] else 1)
