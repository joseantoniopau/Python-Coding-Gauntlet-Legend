"""The Final Exam: the practical test itself, and the ladder that earns it.

The last boss is not a harder problem. It is the same kind of problem with the
apparatus switched off — a timed set of four, mixed easy and medium, followed by
somebody else's codebase you have to navigate, extend, repair, and hand back with
its existing tests still green. That is the shape of the loop this player is
actually preparing for, so that is the shape of the last fight.

Three commitments hold this module together.

1. IT DOES NOT INVENT A SECOND ISOLATION PATH. Interview Mode already exists, is
enforced server-side, and is proven by tests/test_interview_isolation.py: the
pattern is redacted, the hint tree is emptied, and hints, probes, items and the
coach are all refused with `{"error": "sealed"}`. The exam runs in exactly that
mode (`EXAM_MODE is config.MODE_INTERVIEW`). What this module adds is a *seal* —
a named, ordered set of capabilities that can also be withdrawn one at a time
from ordinary boss fights, and an audit that checks the sealed payload for leaks
the original redaction never had to think about.

2. THE BOSSES SPEND THE WHOLE GAME REMOVING THE CRUTCHES, one at a time, so the
exam is the first fight with nothing left rather than an ambush. The ladder is
data (`BOSS_LADDER`), derived from the fourteen bosses in `world.BOSSES` in the
order they stand there. Boss 3 takes hints, boss 6 takes probes, boss 9 takes the
pattern label, boss 12 starts the clock, boss 14 takes the last thing you have.

3. THE EXAM IS PERSONAL AND IT RECOMPOSES. It is drawn from the corpus, weighted
toward the skills this player has actual evidence of being weak at, and it refuses
to hand back a question set it has handed back before.

The report afterwards is the point of all of it. If the player is not ready, it
says so in the first sentence and then says what evidence is missing.

TWO THINGS IN THIS GAME WEAR THE WORD "EXAM" AND THEY ARE NOT THE SAME THING
----------------------------------------------------------------------------
The next person to read this file will assume there is one. There are two, and
the difference is the single most load-bearing sentence in the project:

    THE PRACTICAL — this module — is a MEASUREMENT. It is reachable from the
    menu, at any time, at level one, holding nothing, with no boss beaten and
    no key taken. That is the entire point of this game: a player must always
    be able to ask where they stand and get an honest answer. Nothing gates it.
    Nothing may ever gate it.

    THE STORY CLIMAX is a REWARD. It is behind the Standing Portal in Python
    Village, which wants all fourteen boss keys, and behind it are the mythic
    python wizard, the captives, the cutscene and the ending. That is a thing
    you earn, and earning it is the shape of the campaign.

Those are separate doors and they must stay separate. `world.portal_gates()`
answers False for "practical", "interview", "exam", "readiness", "diagnostic",
"measurement" and everything else measured, forever and by default; tests check
it rather than trusting it. `compose()`, `interview_format()` and every entry
point below read the corpus, the player's skills and the clock — and NOTHING
ELSE. There is no line in this file that reads `cleared_bosses`, a keyring, a
route or a portal, and `PRACTICAL_IS_NEVER_GATED` below exists so that adding
one means deleting a constant that says not to.

Gating the measurement behind fourteen boss kills would make the one honest
number in this game something you have to earn twice, and a player who cannot
find out where they stand until they have finished the story has been sold the
opposite of what was advertised.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, asdict, replace

from . import adaptive, config, grading, world
from . import skills as skillmod

# The exam is Interview Mode. Not a mode that resembles it, not a mode with the
# same rules copied out — the same constant, so every `enc.mode == MODE_INTERVIEW`
# check already in engine.py fires for the exam without being told about it.
EXAM_MODE = config.MODE_INTERVIEW

# THE MEASUREMENT IS NOT A REWARD. Read as a sentence, and checked by
# tests/test_interview_isolation.py rather than trusted.
#
# The value is True and must stay True. What it is really doing is giving the
# rule a name that shows up in a grep for "gate", so that whoever one day
# wonders whether the practical ought to want a key finds this line and the
# paragraph above it before they write the `if`.
PRACTICAL_IS_NEVER_GATED = True

# What may decide whether a player can sit the practical, in full. This tuple is
# the complete list and it has one entry.
PRACTICAL_REQUIREMENTS: tuple = ("the player asked",)

# What may NOT, ever. Every one of these is something the campaign hands out,
# and none of them is evidence about whether this person can write Python under
# time. `world.PORTAL_NEVER_GATES` says the same thing from the other side.
PRACTICAL_NEVER_REQUIRES: tuple = (
    "keys", "boss_kills", "the_standing_portal", "routes", "level", "gold",
    "items", "class", "story_progress", "captives_freed", "region",
)


def practical_gate() -> dict:
    """Why the practical is open. The answer never varies and that is the point.

    Handed to the client so the menu, the portal panel and the keyring all print
    the same sentence from the same place, rather than three screens each
    deciding for themselves how to describe a door that does not exist.
    """
    return {
        "open": True,
        "requires": list(PRACTICAL_REQUIREMENTS),
        "never_requires": list(PRACTICAL_NEVER_REQUIRES),
        "line": "The practical is a measurement, not a reward. It is reachable "
                "from the menu at any time, with nothing unlocked and nothing "
                "earned, because being able to ask where you stand is the whole "
                "point of the game.",
    }


# ---------------------------------------------------------------------------
# 1. The crutches, named once
# ---------------------------------------------------------------------------
#
# Everything the game gives you that the practical test will not. Each entry
# names the boss that takes it away and the engine call site that enforces it,
# because a guarantee nobody can point at in the source is not a guarantee.

@dataclass(frozen=True)
class Crutch:
    id: str
    name: str
    taken_by: str          # boss id that removes it; "" means the exam only
    blurb: str             # what it does for you while you still have it
    hook: str              # where the engine must consult the seal
    herald: str            # what the boss says as it goes


CRUTCHES: tuple = (
    Crutch("HINTS", "The hint tree", "window_wraith",
           "Five escalating rungs, up to and including the worked solution.",
           "engine.Game.use_hint",
           "You have been reading the answer off the wall. The wall is gone."),
    Crutch("MENTOR", "The mentor", "twin_behemoth",
           "A named teacher standing in the encounter with a line about the pattern.",
           "engine.Game._encounter_payload -> payload['mentor']",
           "No one is standing behind you this time."),
    Crutch("WEAKNESS_MAP", "The tactical read", "matrix_golem",
           "The enemy's weaknesses, which are literally the problem's edge cases, "
           "and the tactical brief that explains them.",
           "engine.Game._encounter_payload -> payload['enemy'], payload['tactics']",
           "You used to be able to see where I was soft. Look again."),
    Crutch("PROBES", "The probe", "tree_dragon",
           "Assert the correct answer on an input you choose, before you commit.",
           "engine.Game.probe / probes_remaining",
           "Ask me one more question before you write. Go on. Ask."),
    Crutch("PET", "Companion interventions", "path_sum_ent",
           "A companion volunteering the one line you had forgotten.",
           "engine.Game.submit -> companion line selection",
           "Your friends are outside. They send their regards."),
    Crutch("VISUALS", "The visualisation", "graph_necromancer",
           "The animated picture of the algorithm running.",
           "engine.Game._encounter_payload -> problem['visualization']",
           "Picture it yourself."),
    Crutch("PATTERN", "The pattern label", "rolling_titan",
           "The family name, the secondary families, the optimal complexity and "
           "the list of common failures.",
           "corpus.schema.Problem.player_view(mode='interview')",
           "Nothing here is labelled. That was always the easy part."),
    Crutch("BUILD", "Class bonuses and rank grace", "editor_automaton",
           "Attribute and gear effects, including extra clock before the rank drops.",
           "engine.Game._graced_target / engine.Game.effects",
           "Take the armour off. It was never load-bearing."),
    Crutch("COACH", "The coach", "complexity_wyrm",
           "The Socratic debrief that asks the question that would have unblocked you.",
           "coach.available_in",
           "Afterwards, there will be no conversation. Only a result."),
    Crutch("UNLIMITED_TIME", "All the time you want", "serialization_lich",
           "Thinking as long as you like at no cost but rank.",
           "engine.Game._graced_target / interview clock",
           "I have somewhere to be. You have until then."),
    Crutch("ITEMS", "Consumables", "bug_demon",
           "Charms, whetstones and scrolls bought with gold rather than practice.",
           "engine.Game.use_consumable",
           "Your bag is on the table by the door."),
    Crutch("OBLIGING_HAND", "The Obliging Hand", "the_interviewer",
           "The gauntlet from Chapter IV that solves any encounter instantly.",
           "wherever the Hand is offered — it must consult this seal first",
           "Wear it. Please. I want you to. It will not help you here, and that "
           "is the only thing I have ever been unable to change."),
    # Not a rung on the ladder: the worked solution is not something you lean on
    # during the fight, it is what you are owed afterwards. The exam owes you a
    # debrief instead, so it goes only at the end.
    Crutch("SOLUTION", "The worked solution", "",
           "The canonical implementation, shown once the attempt is scored.",
           "engine.Game.submit -> result['canonical_solution']",
           ""),
    Crutch("SKILL_STATE", "Your own numbers", "",
           "Mastery, stage and hint-dependence shown alongside the question, which "
           "tells you what is being tested.",
           "engine.Game._encounter_payload -> payload['skill'], payload['skill_state']",
           ""),
)

CRUTCH_BY_ID = {c.id: c for c in CRUTCHES}
ALL_CRUTCHES = frozenset(CRUTCH_BY_ID)


# ---------------------------------------------------------------------------
# 1b. The sealed hold-out, which is content rather than a crutch
# ---------------------------------------------------------------------------
#
# `corpus.sealed` marks problems the teaching side of the game may never touch:
# no Adventure encounter, no hint, no SRS review, no coaching, no worked
# solution. They exist so that one measurement in this game is taken on a
# formulation the player has provably never been shown, and they can answer
# that question exactly once each.
#
# It is not a crutch — nothing is being taken away from the player — so it is
# not on the ladder and no boss removes it. It is a capability in the same
# vocabulary for one reason: the refusal has to travel the same road as every
# other refusal in this file. A second isolation mechanism is how the first one
# quietly stops being true.
#
# Two consequences, both deliberate:
#   * `sealed(encounter, HOLDOUT)` is true exactly when the encounter's problem
#     is hold-out content, which is what every teaching surface asks.
#   * a hold-out encounter seals every crutch as well, because it is served
#     cold or it is not served at all.
HOLDOUT = "HOLDOUT"

CAPABILITY_NAMES = {c.id: c.name for c in CRUTCHES}
CAPABILITY_NAMES[HOLDOUT] = "The sealed hold-out"

# The default refusal tells the player a crutch has been taken away. The
# hold-out has not taken anything away, so it says what it actually is.
REFUSAL_MESSAGE = {
    HOLDOUT: ("That problem is held out of the teaching side of the game. It is "
              "one of the few formulations left that can still measure whether "
              "any of this transfers, and spending it on a lesson would spend "
              "it for nothing."),
}


def refuse(capability: str) -> dict:
    """The refusal the server returns. Deliberately the same `{"error": "sealed"}`
    shape engine.py already returns for Interview Mode, so callers and the client
    have exactly one failure to handle."""
    name = CAPABILITY_NAMES.get(capability, capability)
    return {
        "error": "sealed",
        "capability": capability,
        "message": REFUSAL_MESSAGE.get(
            capability, f"{name} does not work here. That is the point of here."),
    }


def suspended(capability: str) -> dict:
    """The same sentence, for a view that DEGRADES instead of refusing.

    `refuse()` carries `error: "sealed"`, and `server._reply` reads that key and
    answers 409. That is correct for a whole view that is the problem. It is
    wrong for a view with a world half, because a 409 tells the client to throw
    away the half that was served — which is how `/api/antagonist` came to hand
    over a standing, a pressure and an empty line list under a status code
    meaning "there is no answer".

    So this is the DEGRADE outcome's payload: the capability and the reason, at
    200, beside whatever the view could honestly serve. docs/10-sealed-views.md
    section 1 says degrading beats refusing wherever it is available; this is
    the shape that makes it available.
    """
    name = CAPABILITY_NAMES.get(capability, capability)
    return {
        "sealed": True,
        "capability": capability,
        "message": REFUSAL_MESSAGE.get(
            capability, f"{name} does not work here. That is the point of here."),
    }


# ---------------------------------------------------------------------------
# 2. The boss ladder
# ---------------------------------------------------------------------------
#
# Each boss removes exactly one thing and never gives it back. By the time the
# Interviewer is standing in front of you, the exam's rule set is not a surprise
# — it is the twelfth time in a row the rules got quieter.
#
# Rung numbers come from the position of the boss in world.BOSSES, so the ladder
# cannot drift out of step with the world. A boss not named by any crutch takes
# nothing: the first two exist to establish what a full kit feels like, which is
# what makes losing it legible.

_BOSS_INDEX = {b["id"]: i + 1 for i, b in enumerate(world.BOSSES)}
_LADDER_LENGTH = len(world.BOSSES)


def _rung_of(crutch: Crutch) -> int:
    """Which rung takes this crutch. Exam-only crutches go at the last rung."""
    return _BOSS_INDEX.get(crutch.taken_by, _LADDER_LENGTH)


@dataclass(frozen=True)
class Seal:
    """What is switched off for one encounter."""
    boss_id: str
    rung: int                      # 1-based ladder position; 0 = an ordinary fight
    label: str
    sealed: frozenset
    takes: tuple                   # crutch ids removed AT this rung
    herald: str
    final: bool = False

    @property
    def timed(self) -> bool:
        return "UNLIMITED_TIME" in self.sealed

    def blocks(self, capability: str) -> bool:
        return capability in self.sealed

    def refusal(self, capability: str) -> dict:
        return refuse(capability)

    def remaining(self) -> tuple:
        """What the player still has. The boss preamble reads this out loud."""
        return tuple(c.id for c in CRUTCHES if c.id not in self.sealed)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sealed"] = sorted(self.sealed)
        d["timed"] = self.timed
        d["remaining"] = list(self.remaining())
        return d


def _seal_for_rung(boss: dict, rung: int) -> Seal:
    sealed = frozenset(c.id for c in CRUTCHES if _rung_of(c) <= rung)
    takes = tuple(c.id for c in CRUTCHES if _rung_of(c) == rung and c.taken_by)
    herald = " ".join(CRUTCH_BY_ID[t].herald for t in takes).strip()
    return Seal(boss_id=boss["id"], rung=rung, label=boss["name"], sealed=sealed,
                takes=takes, herald=herald, final=bool(boss.get("final")))


BOSS_LADDER: tuple = tuple(
    _seal_for_rung(boss, index + 1) for index, boss in enumerate(world.BOSSES))

SEAL_BY_BOSS = {seal.boss_id: seal for seal in BOSS_LADDER}

# An ordinary encounter: nothing sealed, everything available, no apology for it.
OPEN_SEAL = Seal(boss_id="", rung=0, label="", sealed=frozenset(), takes=(),
                 herald="")

# The exam seals every crutch in the list, including the two that are not rungs.
EXAM_SEAL = Seal(boss_id="the_interviewer", rung=_LADDER_LENGTH,
                 label="The Final Exam", sealed=ALL_CRUTCHES,
                 takes=tuple(c.id for c in CRUTCHES if _rung_of(c) == _LADDER_LENGTH),
                 herald=CRUTCH_BY_ID["OBLIGING_HAND"].herald, final=True)


def _with_holdout(seal: Seal) -> Seal:
    """The same seal with the hold-out's own withdrawals added on top.

    A hold-out problem is served cold: no pattern label, no weakness map, no
    hints, no companion, no clock the build can widen. That is every crutch in
    the list, which is what the exam already seals — so this adds the exam's set
    to whatever the encounter had, and leaves the label, the boss and `final`
    alone. Sealing MORE is the only direction this function travels.
    """
    return replace(seal, sealed=frozenset(seal.sealed | ALL_CRUTCHES | {HOLDOUT}))


def seal_for(*, mode: str = config.MODE_ADVENTURE, boss_id: str = "",
             holdout: bool = False) -> Seal:
    """The one function every call site asks. Interview Mode is always the full
    seal; a boss fight is whatever its rung has taken; anything else is open.
    Hold-out content seals everything either way."""
    if mode == EXAM_MODE:
        base = EXAM_SEAL
    elif boss_id in SEAL_BY_BOSS:
        base = SEAL_BY_BOSS[boss_id]
    else:
        base = OPEN_SEAL
    return _with_holdout(base) if holdout else base


# An encounter on hold-out content outside a measured run. The engine refuses to
# start one at all; this exists so that anything which somehow holds such an
# encounter still answers "sealed" to every question asked of it.
HOLDOUT_SEAL = _with_holdout(OPEN_SEAL)


def encounter_seal(encounter) -> Seal:
    """Convenience for engine.py, which has an Encounter rather than two strings."""
    if encounter is None:
        return OPEN_SEAL
    return seal_for(mode=getattr(encounter, "mode", config.MODE_ADVENTURE),
                    boss_id=getattr(encounter, "boss_id", ""),
                    holdout=bool(getattr(encounter, "holdout", False)))


def sealed(encounter, capability: str) -> bool:
    """`if finalexam.sealed(enc, "HINTS"): return finalexam.refuse("HINTS")`"""
    return encounter_seal(encounter).blocks(capability)


def clock_for(problem, seal: Seal) -> float | None:
    """Seconds allowed, or None when the encounter is untimed.

    Note what is NOT here: no grace. `engine._graced_target` widens the target for
    HASTE and Chronomancer gear, and from rung 12 onward that is a sealed BUILD
    bonus, so the clock is the problem's own target and nothing else.
    """
    if not seal.timed:
        return None
    return float(problem.target_seconds)


def ladder_view() -> list:
    """The progression as the quest log should render it: fourteen rungs, each
    with the one thing it takes and what is still in your hands afterwards."""
    out = []
    for seal in BOSS_LADDER:
        boss = world.BOSS_BY_ID.get(seal.boss_id, {})
        out.append({
            "rung": seal.rung,
            "boss_id": seal.boss_id,
            "boss": seal.label,
            "region": boss.get("region", ""),
            "takes": [{"id": t, "name": CRUTCH_BY_ID[t].name,
                       "herald": CRUTCH_BY_ID[t].herald} for t in seal.takes],
            "sealed": sorted(seal.sealed),
            "remaining": list(seal.remaining()),
            "timed": seal.timed,
            "final": seal.final,
        })
    return out


# Exactly where the engine has to ask. Each of these is one line: replace the
# bare `enc.mode == config.MODE_INTERVIEW` test with `finalexam.sealed(enc, CAP)`,
# which is true for Interview Mode AND for every boss that has already taken it.
ENGINE_HOOKS: tuple = tuple(
    {"capability": c.id, "call_site": c.hook,
     "from_rung": _rung_of(c), "taken_by": c.taken_by or "the exam only"}
    for c in CRUTCHES)


# --- Applying the ladder ---------------------------------------------------
#
# Ten edits, all of them the same edit. Interview Mode's behaviour does not
# change: `sealed()` returns True for every capability whenever the mode is
# interview, so each site below keeps doing exactly what it does today and
# additionally starts doing it for the boss that has taken that crutch.
#
#   engine.Game.use_hint
#       if enc.mode == config.MODE_INTERVIEW:   becomes
#           return {"error": "sealed", ...}
#       if finalexam.sealed(enc, "HINTS"):
#           return finalexam.refuse("HINTS")
#
#   engine.Game.probe, engine.Game.probes_remaining   "PROBES"
#   engine.Game.use_consumable                        "ITEMS"
#   engine.Game._graced_target                        "BUILD"   (return the bare
#       target_seconds whenever the seal blocks BUILD, which also removes the
#       rank grace that gear buys)
#   coach.available_in(mode)  ->  coach.available_for(seal)      "COACH"
#   engine.Game.submit, where a companion volunteers a line       "PET"
#
# Four sites are payload fields rather than refusals. In `_encounter_payload`,
# take `seal = finalexam.encounter_seal(enc)` once and then:
#
#   payload["mentor"]       {} if seal.blocks("MENTOR") else ...
#   payload["tactics"]      {} if seal.blocks("WEAKNESS_MAP") else ...
#   payload["enemy"]        strip "weaknesses", "resistances" and "exposed" when
#                           seal.blocks("WEAKNESS_MAP") — they ARE the hidden
#                           edge cases, spelled out with a teaching line attached
#   problem view            problem.player_view(mode=...) already redacts the
#                           pattern for interview; for rungs 9-13 pass the
#                           interview view once seal.blocks("PATTERN"), and use
#                           `finalexam.exam_view(problem)` for the exam itself
#
# And one addition rather than a removal: from rung 12, `clock_for(problem, seal)`
# returns a hard deadline where it previously returned None.
#
# `audit_payload()` is the regression test for all of it. Run it against a live
# exam encounter; anything it names is a door still open. As of writing it names
# three on the engine's own Interview Mode payload — the mentor, the enemy's
# derived weaknesses, and `complexity_choices` — none of which existed when
# `player_view` was written, and all of which are help.


def interview_format() -> dict:
    """The exam, described the way `engine.Game.INTERVIEW_FORMATS` describes a
    format, so it can be registered in one line:

        Game.INTERVIEW_FORMATS["FINAL_EXAM"] = finalexam.interview_format()

    The `ladder` key is what the engine's own simple composer would use if it ran
    this format; `compose()` is the composer that should actually run it, because
    the engine's picks nothing for the codebase segment and knows nothing about
    which skills this player is weak at.
    """
    fmt = THE_PRACTICAL
    return {
        "label": fmt.label,
        "minutes": fmt.minutes,
        "count": fmt.count,
        "ladder": [slot.want[0] for segment in fmt.segments
                   for slot in segment.slots],
        "composer": "gauntlet.finalexam.compose",
        "rules": list(fmt.rules),
        "examiner": examiner_view(),
    }


# ---------------------------------------------------------------------------
# 3. The format
# ---------------------------------------------------------------------------
#
# Drawn from what is actually reported for this kind of hiring loop, and no more
# than that: a timed multi-question set on the order of four problems in seventy
# minutes, mixed easy and medium, no hints of any kind; then a practical segment
# in the reported shape — here is an existing codebase, navigate it, add a
# feature, fix a bug, keep the existing tests green.
#
# Reported format, not a guaranteed one. Nobody here claims to know what any
# particular company will ask on any particular day.

@dataclass(frozen=True)
class SlotSpec:
    role: str                 # "algorithm" | "feature" | "bug"
    want: tuple               # difficulty preference, best first
    label: str


@dataclass(frozen=True)
class SegmentSpec:
    id: str
    label: str
    minutes: int
    brief: str
    slots: tuple

    @property
    def count(self) -> int:
        return len(self.slots)


@dataclass(frozen=True)
class ExamFormat:
    id: str
    label: str
    blurb: str
    segments: tuple
    rules: tuple
    pass_rule: dict

    @property
    def minutes(self) -> int:
        return sum(s.minutes for s in self.segments)

    @property
    def count(self) -> int:
        return sum(s.count for s in self.segments)


THE_PRACTICAL = ExamFormat(
    id="THE_PRACTICAL",
    label="The Practical Test",
    blurb="Four problems on one clock, then somebody else's codebase.",
    segments=(
        SegmentSpec(
            id="set", label="The Set", minutes=70,
            brief="Four problems. Seventy minutes across all four, not seventy "
                  "each. Spend them however you like; nobody will tell you when "
                  "you are spending too long on the second one.",
            slots=(
                SlotSpec("algorithm", ("EASY", "TUTORIAL", "MEDIUM"), "Warm-up"),
                SlotSpec("algorithm", ("EASY", "MEDIUM", "TUTORIAL"), "Second"),
                SlotSpec("algorithm", ("MEDIUM", "EASY", "HARD"), "Third"),
                SlotSpec("algorithm", ("MEDIUM", "HARD", "EASY"), "Last"),
            ),
        ),
        SegmentSpec(
            id="codebase", label="The Codebase", minutes=45,
            brief="A module you did not write, that works today, with tests that "
                  "pass today. Add what is asked. Repair what is broken. The tests "
                  "that were green when you arrived are green when you leave, or "
                  "you have broken something that already shipped.",
            slots=(
                SlotSpec("feature", ("MEDIUM", "EASY"), "Add the feature"),
                SlotSpec("bug", ("MEDIUM", "EASY"), "Find the bug"),
            ),
        ),
    ),
    rules=(
        "No hints. No probes. No items. No companion. No coach. No mentor.",
        "The algorithm family is never named, and neither is its complexity.",
        "One clock per segment, running whether or not you are typing.",
        "The visible tests are the tests you were given. There are others.",
        "The Obliging Hand does not work here. It was never going to.",
    ),
    pass_rule={
        "set_solved": 3,          # of four
        "codebase_solved": 2,     # both
        "min_medium_solved": 1,   # one of the solves must be a MEDIUM
        "within_clock": True,
    },
)

FORMATS = {THE_PRACTICAL.id: THE_PRACTICAL}


# ---------------------------------------------------------------------------
# 3b. The face of it
# ---------------------------------------------------------------------------
#
# The practical had no face. It was a rule set, a clock and a report, and all
# three of those are correct, and a measurement with nobody standing behind it
# is a form the player fills in rather than the last room of a story.
#
# So: THE LAST INTERPRETER. A python, in both senses, at a scale that stopped
# being an animal somewhere around the third coil, wearing a hat that was once
# ceremonial and is now simply old. It is a wizard the way a mountain is a
# landmark — not because it chose the profession but because everything else
# that knew the language is gone and it is still running.
#
# Its whole character is one rule, and the rule is not a gimmick: IT SPEAKS ONLY
# IN PYTHON, AND IT EXPECTS YOU TO DO THE SAME. The Null King un-named the
# Source; every other survivor in this world learned to talk around the gap in
# approximations, gestures and mentor-speak. This one refused. It kept the
# language by being the thing that still executes it, and it has not uttered a
# sentence in nine hundred years that could not be run.
#
# WHAT IT IS NOT. It is not a difficulty change, a rule change, a hint, or a
# mercy. Every string below is authored against NOTHING: it has never seen a
# problem, a test, a pattern label or a solution, and there is no field on it
# that could carry one. `examiner_view()` is static module data with the
# player's verdict code selecting one of three closing lines, which is the only
# input it takes from the run at all. The exam is sealed, unassisted and timed
# exactly as it was before this existed, and the audit that proves it —
# `audit_payload` — is unchanged and still refuses to ship a question that leaks.
#
# It is the last thing the player sees. That is the entire argument for it.

@dataclass(frozen=True)
class Examiner:
    id: str
    name: str
    epithet: str
    species: str
    sprite: str
    colour: str
    accent: str
    tagline: str
    blurb: str
    law: str                  # why it will not speak to you in English
    arrival: tuple
    segment_lines: dict       # SegmentSpec.id -> what it says as that clock starts
    silence: tuple            # what it says to anything asked of it in here
    verdict_lines: dict       # verdict code -> the value it returns about you
    closing: tuple


THE_LAST_INTERPRETER = Examiner(
    id="the_last_interpreter",
    name="THE LAST INTERPRETER",
    epithet="of the Standing Prompt",
    species="Python",
    sprite="interpreter",
    colour="#3f7f5a",
    accent="#e8c37d",
    tagline="It will not explain anything to you in a language that cannot be run.",
    blurb="A python long enough that the room was built around it rather than "
          "the other way round, coiled through the floor it is standing on. "
          "Somewhere past the fourth turn there is a head, and the head is "
          "wearing a hat, and neither of those facts makes the rest of it "
          "smaller. It does not move while you work. It is not watching you "
          "either. It is waiting for a value.",
    law="It has no second language, and that is a fact about what it is rather "
        "than a manner it has adopted. When the Null King un-named the Source, "
        "everything else that survived learned to talk around the hole — in "
        "approximations, in gestures, in the careful mentor-voice you have been "
        "listening to for the whole of this game. This one refused, on the "
        "grounds that a description of a thing is not the thing. It kept the "
        "language by continuing to execute it, alone, for nine hundred years, "
        "and it has not said one sentence since that could not be run.",
    arrival=(
        "The coils arrive first and they keep arriving. You are some way into "
        "the room before you understand that the floor is not the floor.",
        ">>> ",
        "It does not greet you. It opens a prompt. The prompt is the greeting, "
        "and it is also the entire courtesy you are going to be shown in here.",
        ">>> assert isinstance(candidate, Fluent)",
        "That line either raises or it does not. It has been waiting the whole "
        "game to find out which. So, if you are honest about it, have you.",
    ),
    segment_lines={
        "set": ">>> for problem in the_set: solve(problem)   # 70 minutes, "
               "shared",
        "codebase": ">>> import somebody_elses   # it did not write this either. "
                    "it has read it.",
    },
    silence=(
        ">>> help(problem)",
        "no documentation found",
        "It is not being cruel and it is not making a point. It genuinely has "
        "nothing to read out. Everything in this room that could have spoken "
        "was taken from you one at a time, on purpose, by things you have "
        "already beaten, and the last of them was taken three rooms ago by "
        "something in mirror armour that was very polite about it.",
    ),
    verdict_lines={
        "READY": (">>> candidate.ready", "True",
                  "It does not congratulate you. It returns a value. In this "
                  "room that is the higher form of respect, because unlike "
                  "praise it can be checked, and because it is the first thing "
                  "anyone has said to you in nine hundred years that meant "
                  "exactly what it said."),
        "CLOSE": (">>> candidate.ready", "False",
                  "False is a value and not a verdict about you. The coils "
                  "shift by about a foot, which from something this size is the "
                  "gesture of an examiner who has seen the near miss before and "
                  "knows which of the two kinds it is."),
        "NOT_READY": (">>> candidate.ready",
                      "Traceback (most recent call last):",
                      "A traceback is the most generous thing this language "
                      "produces. It names the line, it names the cause, and it "
                      "reads from the bottom up. Everything under this paragraph "
                      "is that traceback, written out in your own numbers."),
    },
    closing=(
        "The coils withdraw in the order they arrived, which takes some time, "
        "and you are left standing in a room that turns out to be quite small.",
        ">>> del interpreter",
        "The prompt stays. It was never his.",
    ),
)

EXAMINER_BY_ID = {THE_LAST_INTERPRETER.id: THE_LAST_INTERPRETER}


def examiner() -> Examiner:
    """The thing standing at the end of the practical."""
    return THE_LAST_INTERPRETER


def examiner_view(verdict_code: str = "") -> dict:
    """Everything the client needs to draw and voice the examiner.

    Static module data. The ONLY thing the run contributes is `verdict_code`,
    which selects one of three closing exchanges, so there is no path by which
    a question, a test or a solution could reach this payload — there is no
    field here for one. That is deliberate and it is why this can be shipped
    inside a sealed run without widening the seal by a single capability.
    """
    who = THE_LAST_INTERPRETER
    return {
        "id": who.id, "name": who.name, "epithet": who.epithet,
        "species": who.species, "sprite": who.sprite,
        "colour": who.colour, "accent": who.accent,
        "tagline": who.tagline, "blurb": who.blurb, "law": who.law,
        # Where it stands. world.py owns the geography; this module owns the
        # animal, and neither of them keeps a second copy of the other's half.
        "region": world.FINAL_TRIAL["region"],
        "where": world.FINAL_TRIAL["where"],
        "arrival": list(who.arrival),
        "segments": dict(who.segment_lines),
        "silence": list(who.silence),
        "closing": list(who.closing),
        "verdict": list(who.verdict_lines.get(verdict_code, ())),
        # Said out loud next to its own portrait: the animal is new, the rules
        # are not, and nothing about the measurement moved to make room for it.
        "changes_nothing": (
            "It is an identity, a herald and a voice around a measurement that "
            "was already here. It seals nothing extra and it unseals nothing. "
            "The rules below are the rules that were always below."),
        "sealed": sorted(EXAM_SEAL.sealed),
        "rules": list(THE_PRACTICAL.rules),
    }


# ---------------------------------------------------------------------------
# 4. Choosing the questions
# ---------------------------------------------------------------------------

# How far the exam is allowed to lean on evidence of weakness. In the draw, the
# worst skill is worth about nine ordinary ones and the sixth-worst barely tilts
# anything; across a whole exam that lands at roughly twice the weak-skill share
# an unweighted composer would produce (see `self_check`). Enough that the exam
# is about this player, not so much that it stops resembling an interview.
WEAK_FOCUS = 6
WEAK_BONUS = 8.0
UNSEEN_MULTIPLIER = 1.5          # never tested is not proven weak, only unproven
RECENT_PENALTY = 0.15

# Within one exam: no two questions from the same family, at most two sharing a
# pattern. Four hash-map questions is not a practical test, it is a hash-map test.
MAX_PER_PATTERN = 2

# The bug should live in the codebase you just extended, where that is possible.
SAME_CODEBASE_BONUS = 3.0

# The encounter kinds an exam question may be. Everything else in the corpus is
# a teaching interaction — a scaffold with the answer struck out, a puzzle, a
# multiple choice — and a practical test does not contain any of those.
EXAM_ENCOUNTERS = {
    "algorithm": ("CODE_BATTLE",),
    "feature": ("CODE_BATTLE", "REFACTOR_QUEST"),
    "bug": ("DEBUG_BATTLE",),
}

# A GUIDED problem is a finished function with one expression struck out. That is
# a scaffold, which is help, which is the one thing this exam does not have.
_EXAM_DIFFICULTIES = frozenset({"TUTORIAL", "EASY", "MEDIUM", "HARD"})

# "practical" is a TAG on every problem the practical-test family authors, not a
# spaced_repetition_family — it sat in the family set below, where nothing could
# ever match it, until a cross-module audit compared both sets against the
# corpus. It belongs here, with the other tags.
_CODEBASE_TAGS = frozenset({"given-codebase", "add-feature", "refactor",
                            "practical"})
_CODEBASE_FAMILIES = frozenset({
    "codebase_feature", "codebase_class", "codebase_refactor",
})


def _normalise(skills) -> dict:
    """Accept either live SkillState objects or the raw dicts a save file holds.
    The exam is composed from both places, so it tolerates both shapes rather
    than making the caller remember which one it has."""
    if not skills:
        return {}
    out = {}
    for name, value in skills.items():
        if isinstance(value, dict):
            try:
                out[name] = skillmod.SkillState(**value)
            except TypeError:
                continue
        else:
            out[name] = value
    return out


def focus_skills(skills, *, limit: int | None = None) -> list:
    """The skills this player has evidence of being weak at, worst first.

    This is `skills.weakest` and nothing else — the ordering lives there because
    that is where the pain formula lives, and a second copy of it here would
    drift within a fortnight.
    """
    states = _normalise(skills)
    if not states:
        return []
    return skillmod.weakest(states, limit=limit or WEAK_FOCUS, floor_attempts=1)


def _skill_of(problem) -> str:
    return skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")


def _eligible(problem, role: str) -> bool:
    """Can this problem be an exam question of this kind at all?"""
    if problem.difficulty not in _EXAM_DIFFICULTIES:
        return False
    if problem.entry.get("kind") not in ("function", "class_ops"):
        return False
    if not problem.canonical_solution.strip():
        return False
    if not problem.all_tests:
        return False

    # The kind gate comes first and is not negotiable. A MISSING_RUNE encounter
    # also arrives as a multi-line module you did not write — and it arrives with
    # the answer struck out of it, which is a scaffold, which is help. Selecting
    # the codebase slots on "has substantial starter code" alone put twenty-seven
    # of them in the pool.
    if problem.encounter_kind not in EXAM_ENCOUNTERS.get(role, ()):
        return False

    if role == "algorithm":
        # Write the function, on a blank screen, the way a screen asks.
        return True

    if role == "bug":
        # Somebody else's module, already broken, tests that must come back green.
        return True

    if role == "feature":
        # Somebody else's module, already working, extended without breaking it.
        # The strong form is the practical family's given-codebase problems; the
        # honest fallback is anything that hands you real working code to start
        # from, and after that, extending a class you did not write.
        if _CODEBASE_TAGS & set(problem.tags):
            return True
        if problem.spaced_repetition_family in _CODEBASE_FAMILIES:
            return True
        if problem.encounter_kind == "REFACTOR_QUEST":
            return True
        if _given_module(problem.starter_code):
            return True
        return problem.entry.get("kind") == "class_ops"

    return False


def _given_module(starter: str) -> bool:
    """Is this starter code somebody else's working module, or an empty stub?

    Counting lines is not enough. Every ordinary problem's starter is a `def`, a
    docstring and a `pass`, which is five lines of nothing, and eighteen
    onboarding stubs walked into the codebase segment on exactly that basis. A
    module you have to navigate has code in it that already does something.
    """
    body = []
    in_doc = False
    for raw in starter.splitlines():
        line = raw.strip()
        if line.startswith(('"""', "'''")):
            # One-line docstrings open and close on the same line.
            in_doc = not (len(line) > 3 and line.endswith(line[:3]))
            continue
        if in_doc or not line or line.startswith("#"):
            continue
        if line.startswith(("def ", "class ", "@")):
            continue
        if line in ("pass", "...", "return", "return None"):
            continue
        body.append(line)
    return len(body) >= 4


def _pools(corpus) -> dict:
    pools = {role: [] for role in ("algorithm", "feature", "bug")}
    for problem in corpus:
        for role in pools:
            if _eligible(problem, role):
                pools[role].append(problem)
    return pools


def _multipliers(skills) -> tuple:
    """skill -> weight multiplier, plus the focus list that produced it."""
    states = _normalise(skills)
    focus = focus_skills(states)
    weights = {}
    for index, name in enumerate(focus):
        # Decay across the focus list, weighted toward its head: the worst skill
        # is worth nine ordinary ones, the sixth-worst barely tilts the draw.
        share = (1.0 - index / max(len(focus), 1)) ** 1.5
        weights[name] = 1.0 + WEAK_BONUS * share
    for name, state in states.items():
        if state.attempts == 0:
            weights.setdefault(name, UNSEEN_MULTIPLIER)
    return weights, focus


def _codebase_strength(problem, role: str) -> float:
    """How well this problem plays the part the codebase segment is asking for.

    _eligible() answers yes/no and lists its fallbacks in order of quality, but
    a boolean cannot express that order at the draw, so an `entry.kind ==
    class_ops` fallback was beating the practical family's purpose-built
    given-codebase problems roughly as often as it lost to them. The reported
    format is "navigate somebody else's module", and those problems were
    authored to be exactly that, so they should win when they exist.
    """
    if role not in ("feature", "bug"):
        return 1.0
    if _CODEBASE_TAGS & set(problem.tags):
        return 4.0
    if problem.spaced_repetition_family in _CODEBASE_FAMILIES:
        return 3.0
    if problem.encounter_kind == "REFACTOR_QUEST":
        return 2.5
    if _given_module(problem.starter_code):
        return 1.5
    return 1.0


def _weight(problem, *, multipliers: dict, profile: str, recent: set,
            prefer_family: str = "", role: str = "") -> float:
    weight = multipliers.get(_skill_of(problem), 1.0)
    weight *= _codebase_strength(problem, role)
    # A secondary family counts, at a discount: a window problem that also leans
    # on hash maps is a fair way to examine hash maps.
    for pattern in problem.secondary_patterns:
        secondary = multipliers.get(skillmod.PATTERN_TO_SKILL.get(pattern, ""), 1.0)
        weight = max(weight, 1.0 + 0.35 * (secondary - 1.0))
    weight *= max(0.25, problem.profile_weight.get(profile, 1.0)) ** 0.5
    if problem.id in recent:
        weight *= RECENT_PENALTY
    if prefer_family and problem.spaced_repetition_family == prefer_family:
        weight *= SAME_CODEBASE_BONUS
    return max(weight, 0.01)


def _pick(rng, candidates, weights) -> object:
    total = sum(weights)
    if total <= 0:
        return rng.choice(candidates)
    mark = rng.random() * total
    for candidate, weight in zip(candidates, weights):
        mark -= weight
        if mark <= 0:
            return candidate
    return candidates[-1]


@dataclass
class Question:
    position: int
    segment: str
    role: str
    label: str
    problem_id: str
    title: str
    difficulty: str
    target_seconds: int
    # Server-side only. `player_view` strips both, because the whole exam rests
    # on the player not being told which family they are looking at.
    pattern: str = ""
    skill: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def player_view(self) -> dict:
        """The question as a slot in a timetable, not as a question.

        `problem_id` and `title` go the same way `pattern` and `skill` do, and
        for the reason already written above them. The exam reaches into the
        sealed hold-out, and a hold-out problem is spent when it is served, so
        a roster naming the questions before they are served hands over sealed
        ids — with titles attached, which is the whole exercise in four words —
        at no cost and with the run still abandonable. What the client needs to
        draw the timetable is the position, the segment, the role, the
        difficulty and the clock. It is all still here.
        """
        d = self.to_dict()
        d["pattern"] = "REDACTED"
        d["skill"] = ""
        d.pop("problem_id", None)
        d.pop("title", None)
        return d


@dataclass
class Exam:
    id: str
    format_id: str
    profile: str
    seed: int
    created_at: float
    segments: list = field(default_factory=list)   # [{spec fields, questions}]
    focus: list = field(default_factory=list)      # weak skills this exam leans on
    notes: list = field(default_factory=list)

    @property
    def format(self) -> ExamFormat:
        return FORMATS[self.format_id]

    @property
    def questions(self) -> list:
        return [q for segment in self.segments for q in segment["questions"]]

    @property
    def problem_ids(self) -> list:
        return [q.problem_id for q in self.questions]

    @property
    def fingerprint(self) -> str:
        """Identity of the question SET, order-independent. Two exams with the
        same four problems in a different order are the same exam."""
        return "|".join(sorted(self.problem_ids))

    @property
    def minutes(self) -> int:
        return sum(s["minutes"] for s in self.segments)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "format_id": self.format_id, "profile": self.profile,
            "seed": self.seed, "created_at": self.created_at,
            "fingerprint": self.fingerprint, "focus": list(self.focus),
            "notes": list(self.notes), "minutes": self.minutes,
            "segments": [{**s, "questions": [q.to_dict() for q in s["questions"]]}
                         for s in self.segments],
        }

    def player_view(self) -> dict:
        """What the client may see before the first question opens: how long, how
        many, and in what order. Not what they are about."""
        fmt = self.format
        return {
            "id": self.id,
            "format": fmt.id,
            "label": fmt.label,
            "blurb": fmt.blurb,
            "minutes": self.minutes,
            "count": len(self.questions),
            "rules": list(fmt.rules),
            "mode": EXAM_MODE,
            "sealed": sorted(EXAM_SEAL.sealed),
            # Who is in the room. Static module data with no field that could
            # carry a question; see `examiner_view`.
            "examiner": examiner_view(),
            "segments": [
                {"id": s["id"], "label": s["label"], "minutes": s["minutes"],
                 "brief": s["brief"],
                 "questions": [q.player_view() for q in s["questions"]]}
                for s in self.segments
            ],
        }


def compose(corpus, skills=None, *, profile: str = config.DEFAULT_PROFILE,
            seed: int | None = None, history=(), recent_ids=(),
            format_id: str = THE_PRACTICAL.id, redraws: int = 24) -> Exam:
    """Build one exam: personal, in band, and one this player has not sat before.

    `history` is a collection of fingerprints from previous exams — pass
    `history_fingerprints(db.interview_history(conn))`. A drawn set that matches
    one of them is thrown away and redrawn, which is what makes passing once not
    the end of it.
    """
    fmt = FORMATS.get(format_id)
    if fmt is None:
        raise KeyError(format_id)
    pools = _pools(corpus)
    if not pools["algorithm"]:
        raise ValueError("the corpus has no code battles to examine with")

    rng = random.Random(seed if seed is not None else random.getrandbits(48))
    multipliers, focus = _multipliers(skills)
    recent = set(recent_ids)
    seen = set(history)

    draft = None
    for attempt in range(max(1, redraws)):
        draft = _draw(rng, fmt, pools, multipliers=multipliers, profile=profile,
                      recent=recent)
        if "|".join(sorted(q.problem_id for q in draft)) not in seen:
            break
    else:
        attempt = redraws

    notes = []
    if "|".join(sorted(q.problem_id for q in draft)) in seen:
        # Honest rather than silent: the corpus has run out of unseen combinations
        # for this shape, and the player is owed that sentence rather than a
        # repeat presented as fresh material.
        notes.append("This set repeats one you have sat before. The corpus has "
                     "run out of new combinations at this shape.")

    exam = Exam(id=f"fx-{int(time.time() * 1000)}", format_id=fmt.id,
                profile=profile, seed=rng.randrange(1 << 30),
                created_at=time.time(), focus=list(focus), notes=notes)
    by_segment = {s.id: [] for s in fmt.segments}
    for question in draft:
        by_segment[question.segment].append(question)
    exam.segments = [
        {"id": s.id, "label": s.label, "minutes": s.minutes, "brief": s.brief,
         "questions": by_segment[s.id]}
        for s in fmt.segments
    ]
    return exam


def _draw(rng, fmt, pools, *, multipliers, profile, recent) -> list:
    chosen: list = []
    used_ids: set = set()
    used_families: set = set()
    pattern_count: dict = {}
    feature_family = ""
    position = 0

    for segment in fmt.segments:
        for slot in segment.slots:
            position += 1
            pool = pools.get(slot.role) or pools["algorithm"]
            problem = _fill(rng, pool, slot, used_ids=used_ids,
                            used_families=used_families,
                            pattern_count=pattern_count,
                            multipliers=multipliers, profile=profile,
                            recent=recent, role=slot.role,
                            prefer_family=(feature_family if slot.role == "bug"
                                           else ""))
            if problem is None:
                # Never leave a slot empty: an exam with a hole in it is worse
                # than an exam with a repeated pattern.
                problem = _fill(rng, pools["algorithm"], slot, used_ids=used_ids,
                                used_families=set(), pattern_count={},
                                multipliers=multipliers, profile=profile,
                                recent=set())
            if problem is None:
                raise ValueError(f"the corpus cannot fill the {slot.role} slot")

            used_ids.add(problem.id)
            used_families.add(problem.spaced_repetition_family)
            pattern_count[problem.pattern] = pattern_count.get(problem.pattern, 0) + 1
            if slot.role == "feature":
                feature_family = problem.spaced_repetition_family
            chosen.append(Question(
                position=position, segment=segment.id, role=slot.role,
                label=slot.label, problem_id=problem.id, title=problem.title,
                difficulty=problem.difficulty,
                target_seconds=problem.target_seconds,
                pattern=problem.pattern, skill=_skill_of(problem)))
    return chosen


def _fill(rng, pool, slot, *, used_ids, used_families, pattern_count,
          multipliers, profile, recent, prefer_family="", role=""):
    """Walk the slot's difficulty preference until something fits, relaxing the
    family and pattern caps only once the preferred difficulties are exhausted."""
    for relax in (False, True):
        for difficulty in slot.want:
            candidates = [
                p for p in pool
                if p.difficulty == difficulty
                and p.id not in used_ids
                and (relax or p.spaced_repetition_family not in used_families)
                and (relax or pattern_count.get(p.pattern, 0) < MAX_PER_PATTERN)
            ]
            if not candidates:
                continue
            weights = [_weight(p, multipliers=multipliers, profile=profile,
                               recent=recent, prefer_family=prefer_family, role=role)
                       for p in candidates]
            return _pick(rng, candidates, weights)
    return None


def history_fingerprints(rows) -> list:
    """Fingerprints of past runs, from the `interview_runs` rows the engine
    already writes (`problem_ids` is stored comma-joined)."""
    out = []
    for row in rows or ():
        ids = (row.get("problem_ids") or "") if isinstance(row, dict) else ""
        parts = [part for part in ids.split(",") if part]
        if parts:
            out.append("|".join(sorted(parts)))
    return out


# ---------------------------------------------------------------------------
# 5. The band
# ---------------------------------------------------------------------------
#
# "Mixed easy and medium" is a claim the exam has to keep every time it
# recomposes, so it is checked rather than hoped for.

BAND = {
    "set": {"min_easy_or_below": 1, "min_medium_or_above": 1, "max_hard": 1},
    "codebase": {"min_easy_or_below": 0, "min_medium_or_above": 1, "max_hard": 0},
}
_EASYISH = frozenset({"TUTORIAL", "EASY"})
_MEDIUMISH = frozenset({"MEDIUM", "HARD"})


def within_band(exam: Exam) -> tuple:
    """(ok, reasons). Reasons are plain sentences, not codes: they end up in the
    self-check output and in nobody's hands but a maintainer's."""
    reasons = []
    for segment in exam.segments:
        band = BAND.get(segment["id"])
        if band is None:
            continue
        difficulties = [q.difficulty for q in segment["questions"]]
        easyish = sum(1 for d in difficulties if d in _EASYISH)
        mediumish = sum(1 for d in difficulties if d in _MEDIUMISH)
        hard = sum(1 for d in difficulties if d == "HARD")
        if easyish < band["min_easy_or_below"]:
            reasons.append(f"{segment['id']}: no easy question to open with")
        if mediumish < band["min_medium_or_above"]:
            reasons.append(f"{segment['id']}: nothing at medium or above")
        if hard > band["max_hard"]:
            reasons.append(f"{segment['id']}: {hard} hard questions is not this format")
        if "GUIDED" in difficulties:
            reasons.append(f"{segment['id']}: a GUIDED problem is a scaffold, "
                           "which is help")
    if len(exam.questions) != exam.format.count:
        reasons.append("wrong number of questions")
    return (not reasons), reasons


# ---------------------------------------------------------------------------
# 6. No help means no help
# ---------------------------------------------------------------------------
#
# `Problem.player_view(mode="interview")` already does the redaction and is
# already proven by tests/test_interview_isolation.py. What follows does two
# things that redaction does not: it tightens one field that predates the exam,
# and it audits the result so a future edit to player_view cannot quietly open a
# door. The audit is a tripwire over the existing path, not a second one.

_MUST_BE_EMPTY = ("hint_tree", "secondary_patterns", "common_failures",
                  "variants", "prerequisites", "complexity_choices")
_MUST_BE_ABSENT = ("canonical_solution", "hidden_tests", "edge_cases",
                   "perf_tests", "alternate_solutions", "mutants")


# The answer surface of a puzzle payload, named once so that `exam_view` strips
# exactly what `audit_view` refuses — the two agreeing by construction rather
# than by two lists staying in step by hand.
#
# `schema.PUZZLE_VISIBLE_MCQ` ships some of these to the client on purpose,
# because a teaching puzzle needs them to be playable: SPOT_THE_FLAW is
# literally "two spells, near identical, one cursed, find the line", so the
# honest version has to be on screen next to the cursed one. Correct code on
# screen is also precisely the teaching surface an exam may not have. Both
# readings are right; they just belong to different modes, and `redact_mcq` is
# mode-blind, so the narrowing happens here.
#
# No exam composes one of these today — EXAM_ENCOUNTERS admits CODE_BATTLE,
# REFACTOR_QUEST and DEBUG_BATTLE and nothing else — so this closes a door
# rather than a live leak. It is closed anyway: the day somebody widens
# EXAM_ENCOUNTERS should not also be the day fourteen puzzles start handing out
# correct code, and finding that out from an audit is better than from a player.
_MCQ_ANSWER_KEYS = ("answer", "explanation", "distractors", "reference_code",
                    "flawed_line", "final_state")


def exam_view(problem) -> dict:
    """The question as the player may see it.

    Everything here comes from `player_view(mode=EXAM_MODE)`. Two things are
    taken off it. `complexity_choices` goes because four Big-O options with the
    right one among them tell you what shape of solution is expected, which is a
    hint that predates Interview Mode and was never reconsidered — a real
    practical gives you a specification, examples, and a test suite you can run,
    not a multiple-choice list of the answer's cost. And the puzzle answer keys
    go, for the reason set out above them.
    """
    view = problem.player_view(mode=EXAM_MODE)
    view["complexity_choices"] = []
    mcq = view.get("mcq")
    if isinstance(mcq, dict):
        view["mcq"] = {k: v for k, v in mcq.items()
                       if k not in _MCQ_ANSWER_KEYS}
    view["sealed"] = sorted(EXAM_SEAL.sealed)
    return view


def audit_view(view: dict) -> list:
    """Leaks in a question payload. Empty list or it does not ship."""
    leaks = []
    if view.get("pattern") != "REDACTED":
        leaks.append("pattern label is present")
    for key in _MUST_BE_EMPTY:
        if view.get(key):
            leaks.append(f"{key} is populated")
    if view.get("visualization"):
        leaks.append("visualization is populated")
    if view.get("optimal_complexity"):
        leaks.append("optimal_complexity is populated")
    for key in _MUST_BE_ABSENT:
        if key in view:
            leaks.append(f"{key} was serialised to the client")
    mcq = view.get("mcq") or {}
    for key in _MCQ_ANSWER_KEYS:
        if key in mcq:
            leaks.append(f"mcq.{key} was serialised to the client")
    for test in view.get("visible_tests") or ():
        if test.get("hidden"):
            leaks.append("a hidden test was served as a visible one")
    return leaks


def audit_payload(payload: dict) -> list:
    """Leaks in a whole encounter payload, the shape `engine._encounter_payload`
    returns. Run this against a live exam encounter; anything it names is a door
    that has to be closed in engine.py, not worked around here."""
    leaks = list(audit_view(payload.get("problem") or {}))
    if not payload.get("interview_locked"):
        leaks.append("interview_locked is not set")
    if payload.get("mode") != EXAM_MODE:
        leaks.append("encounter is not running in interview mode")
    if payload.get("hint_count"):
        leaks.append("hint_count is non-zero")
    if payload.get("probe_charges"):
        leaks.append("probe charges are available")
    if payload.get("tactics"):
        leaks.append("tactical brief is present")
    if payload.get("loadout"):
        leaks.append("loadout is present")
    if payload.get("skill") or payload.get("skill_state"):
        leaks.append("the player's own skill numbers are attached to the question")
    if payload.get("mentor"):
        leaks.append("a mentor is attached to the encounter")
    enemy = payload.get("enemy") or {}
    if enemy.get("weaknesses"):
        leaks.append("enemy weaknesses expose the hidden edge cases")
    if enemy.get("resistances"):
        leaks.append("enemy resistances name the complexity ceiling")
    if enemy.get("exposed"):
        leaks.append("probed weaknesses are attached to the encounter")
    return leaks


def audit_seal() -> list:
    """Nothing in CRUTCHES escapes the exam's seal. One line, checked in the
    self-check, so adding a new crutch without sealing it fails loudly."""
    return [c.id for c in CRUTCHES if not EXAM_SEAL.blocks(c.id)]


# ---------------------------------------------------------------------------
# 7. The debrief
# ---------------------------------------------------------------------------
#
# This is the thing the player is actually here for. It is allowed to be blunt
# and it is not allowed to be vague. Every sentence below either states a
# measured fact or names a specific next action.

# The three things a failed question can mean. Named here rather than inline so
# the exam report and `engine.finish_interview` cannot drift into disagreeing
# about what a root cause signifies.
CAUSE_BUCKETS = {
    "knowledge": ("PATTERN_NOT_RECOGNIZED", "WRONG_ALGORITHM",
                  "WRONG_DATA_STRUCTURE", "COMPLEXITY"),
    "implementation": ("SYNTAX", "PYTHON_RECALL", "OFF_BY_ONE", "EDGE_CASE",
                       "STATE_MANAGEMENT", "MUTABILITY", "RECURSION",
                       "TREE_TRAVERSAL", "GRAPH_TRAVERSAL", "DEBUGGING",
                       "TESTING"),
    "timing": ("TIME_PRESSURE", "INEFFICIENT_ALGORITHM"),
}

BUCKET_MEANING = {
    "knowledge": "You did not identify what kind of problem it was, so the "
                 "implementation never had a chance. Cheapest thing on this list "
                 "to fix, and the most embarrassing to leave unfixed.",
    "implementation": "You knew the approach and the Python got in the way. That "
                      "is fluency, and fluency is drills, not insight.",
    "timing": "Correct thinking, too slow to finish. Interviews do not award "
              "partial credit for a right answer arriving after the call ends.",
}

# What to actually go and do about a root cause. Deliberately countable: "five
# unaided" is checkable, "revise hash maps" is not.
DRILL_ACTION = {
    "PATTERN_NOT_RECOGNIZED": "Twenty PATTERN_ENCOUNTER cards, naming the family "
                              "in under ten seconds each, before you write "
                              "anything at all.",
    "WRONG_DATA_STRUCTURE": "Five problems where you must state the structure and "
                            "its cost out loud before the first keystroke.",
    "WRONG_ALGORITHM": "Re-solve the three you failed here, unaided, then a "
                       "disguised variant of each three days later.",
    "INEFFICIENT_ALGORITHM": "Complexity Tower to the fifth floor, then five "
                             "problems with performance tests attached.",
    "COMPLEXITY": "Ten COMPLEXITY_MATCH duels. State the cost before you look at "
                  "the options.",
    "SYNTAX": "Village drills until the syntax costs you nothing: twenty "
              "MISSING_RUNE encounters, no reference open.",
    "PYTHON_RECALL": "Twenty RUNE_ASSEMBLY puzzles. You know the algorithm; this "
                     "is about producing the Python without stopping to think.",
    "OFF_BY_ONE": "Ten TRACE puzzles, then five debug battles in the Armorer's "
                  "Forge. Trace the first and last iteration by hand every time.",
    "EDGE_CASE": "Five TEST_FORGE encounters. Kill every mutant. A suite that "
                 "every wrong implementation passes is not a suite.",
    "STATE_MANAGEMENT": "Ten STATE_PREDICT puzzles, then re-solve any design "
                        "problem you have cleared before, from scratch.",
    "MUTABILITY": "The mutation drills in the Village, then re-read your own "
                  "failed submission and find the line that changed a caller's "
                  "list.",
    "RECURSION": "Five recursion problems where you write the base case first "
                 "and refuse to write anything else until it is right.",
    "TREE_TRAVERSAL": "Five tree problems, saying what each node needs from its "
                      "children before you write the signature.",
    "GRAPH_TRAVERSAL": "Five grid and graph searches. Mark visited on enqueue, "
                       "never on pop, and be able to say why.",
    "DEBUGGING": "Ten debug battles. Read the failing input first, every time, "
                 "before you read the code.",
    "TESTING": "Five TEST_FORGE encounters plus one pass over every problem you "
               "have solved, adding the case you did not think of.",
    "TIME_PRESSURE": "The Coliseum: five problems you have already solved, each "
                     "one under its target time, unaided.",
    "COMMUNICATION": "State the approach out loud, in one sentence, before every "
                     "encounter for a week. If you cannot, you do not have one.",
    "UNKNOWN": "Re-run the failed submission in the sandbox and classify the "
               "failure yourself. An unclassified failure repeats.",
}


def _clock(seconds) -> str:
    seconds = max(0, int(round(seconds or 0)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _bucket_of(cause: str) -> str:
    for bucket, causes in CAUSE_BUCKETS.items():
        if cause in causes:
            return bucket
    return ""


def _result_index(exam: Exam, results) -> dict:
    """Match results to questions by problem id, falling back to position for
    callers that hand back a bare ordered list."""
    index = {}
    for position, entry in enumerate(results or ()):
        pid = entry.get("problem_id") or entry.get("id")
        if pid:
            index[pid] = entry
        else:
            questions = exam.questions
            if position < len(questions):
                index[questions[position].problem_id] = entry
    return index


def _assess(question: Question, result: dict) -> str:
    seconds = result.get("seconds") or 0
    target = question.target_seconds or 0
    if not result:
        return "Not attempted. On the day, that is a zero."
    if result.get("solved"):
        if seconds <= target:
            return (f"Solved in {_clock(seconds)} against a {_clock(target)} "
                    "target. That is interview pace.")
        if seconds <= target * 1.5:
            return (f"Solved in {_clock(seconds)}, over the {_clock(target)} "
                    "target but not by enough to lose the room.")
        return (f"Solved in {_clock(seconds)} against {_clock(target)}. Correct, "
                "and in a real loop you would have been stopped before this.")
    cause = result.get("root_cause") or "UNKNOWN"
    blurb = grading.FAILURE_BLURB.get(cause, grading.FAILURE_BLURB["UNKNOWN"])
    submits = result.get("submits") or 0
    tail = f" {submits} submissions." if submits > 1 else ""
    return f"Not solved in {_clock(seconds)}. {blurb}{tail}"


def _drills(causes: list, skills) -> list:
    """Specific skills to drill, worst first, with what to do about each."""
    states = _normalise(skills)
    counts: dict = {}
    for cause in causes:
        counts[cause] = counts.get(cause, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    drills = []
    for cause, count in ordered[:4]:
        skill = grading.CATEGORY_TO_SKILL.get(cause, "PYTHON")
        camp = adaptive.CAMPS.get(cause, {})
        # A failed skill often stands on a weaker one. Route to the thing
        # underneath rather than reteaching the surface that just broke.
        underneath = skillmod.missing_prerequisite(states, skill) if states else None
        state = states.get(skill)
        drills.append({
            "cause": cause,
            "skill": skill,
            "occurrences": count,
            "why": grading.FAILURE_BLURB.get(cause, ""),
            "do": DRILL_ACTION.get(cause, DRILL_ACTION["UNKNOWN"]),
            "where": camp.get("name", "the Village"),
            "region": camp.get("region", "python_village"),
            "mentor": world.MENTORS.get(camp.get("mentor", "byte"), {}).get("name", ""),
            "prerequisite": underneath,
            "prerequisite_note": (
                f"{skill} is standing on {underneath}, which is weaker than it is. "
                f"Fix {underneath} first or you will fix {skill} twice."
                if underneath else ""),
            "mastery": round(state.mastery) if state else None,
        })
    return drills


def _verdict(*, set_solved, set_total, codebase_solved, codebase_total,
             medium_solved, overran, rule) -> dict:
    solved = set_solved + codebase_solved
    total = set_total + codebase_total
    passed = (set_solved >= rule["set_solved"]
              and codebase_solved >= rule["codebase_solved"]
              and medium_solved >= rule["min_medium_solved"]
              and not (rule["within_clock"] and overran))

    if passed:
        return {
            "code": "READY",
            "headline": "That is a pass.",
            "body": ("You solved {s} of {t} with nothing to lean on, inside the "
                     "clock. On this evidence you can sit this format. Keep the "
                     "retests current — this result is true about the week it was "
                     "measured in, not about you permanently.").format(
                         s=solved, t=total),
        }

    # Near miss: the work is there and exactly one condition is not. Losing the
    # whole codebase segment is not a near miss, however well the set went — that
    # segment is the half of the loop this player is least practised at.
    near = solved >= total - 1 or (
        set_solved >= rule["set_solved"]
        and codebase_solved >= codebase_total - 1
        and (overran or medium_solved < rule["min_medium_solved"]))
    if near:
        reason = ("you went over the clock" if overran else
                  "one question did not come out")
        return {
            "code": "CLOSE",
            "headline": "Not a pass, and not far off.",
            "body": ("You solved {s} of {t}; {r}. This is the band where people "
                     "pass one week and fail the next, which means it is not yet "
                     "a result you can rely on. Sit it again after the drills "
                     "below and look for the same number twice.").format(
                         s=solved, t=total, r=reason),
        }

    return {
        "code": "NOT_READY",
        "headline": "You are not ready for this format yet. Plainly.",
        "body": ("You solved {s} of {t} unaided. In a real loop that does not "
                 "advance. Nothing about that is a verdict on whether you can do "
                 "the job, and it is a straight answer about whether you could do "
                 "it on Tuesday under a clock with a stranger watching. The drills "
                 "below are the shortest route between those two facts.").format(
                     s=solved, t=total),
    }


# A question that was never put in front of the player and is drawn from the
# sealed hold-out. Naming it in the debrief spends nothing and costs everything:
# end the practical the second it starts and the report tells you the titles of
# the sealed questions it had lined up for you, still unspent, ready to be met
# "cold" once you have looked them up.
UNSEEN_TITLE = "Not asked — still sealed"
UNSEEN_NOTE = ("You never saw this one, so it is still hold-out content and it "
               "still has to be met cold. It keeps its name until you sit it.")


def debrief(exam: Exam, results, *, skills=None, seconds_by_segment=None,
            readiness=None, corpus_index=None, served=()) -> dict:
    """The report: per-question outcome, time spent, what it says about
    readiness, and the specific skills to drill.

    `results` is the shape `engine.interview_advance` already records —
    `{problem_id, solved, rank, seconds, root_cause}` — plus anything else the
    grader felt like attaching.

    `served` is the set of problem ids this player has actually been shown, and
    it exists for one case: a sealed question the run composed but never served.
    Everything else in this report is about something that happened; that row is
    about something that did not, and it is the only row that has to stay
    anonymous. A teachable question keeps its name either way — there is nothing
    to protect — so the redaction costs a debrief nothing it was worth having.
    """
    fmt = exam.format
    index = _result_index(exam, results)
    seconds_by_segment = seconds_by_segment or {}
    served = set(served or ())
    corpus_index = corpus_index or {}

    def unseen(question) -> bool:
        problem = corpus_index.get(question.problem_id)
        return (bool(getattr(problem, "sealed", False))
                and question.problem_id not in served
                and not index.get(question.problem_id))

    questions = []
    segments = []
    causes = []
    medium_solved = 0
    overran = False

    for segment in exam.segments:
        spent = seconds_by_segment.get(segment["id"])
        solved_here = 0
        rows = []
        for question in segment["questions"]:
            result = index.get(question.problem_id, {})
            solved = bool(result.get("solved"))
            seconds = result.get("seconds") or 0
            cause = "" if solved else (result.get("root_cause") or "UNKNOWN")
            if cause:
                causes.append(cause)
            if solved:
                solved_here += 1
                if question.difficulty in _MEDIUMISH:
                    medium_solved += 1
            hidden = unseen(question)
            rows.append({
                "position": question.position,
                "label": question.label,
                "role": question.role,
                "title": UNSEEN_TITLE if hidden else question.title,
                "unseen": hidden,
                "difficulty": question.difficulty,
                # The labels come back now. Knowing afterwards what the thing was
                # is the entire value of a debrief, and it costs nothing once the
                # attempt is scored — which is the condition, not a figure of
                # speech. On a question that was never served and is still
                # sealed, it costs the measurement.
                "pattern": "" if hidden else question.pattern,
                "skill": "" if hidden else question.skill,
                "solved": solved,
                "rank": result.get("rank", ""),
                "seconds": round(seconds),
                "clock": _clock(seconds),
                "target_seconds": question.target_seconds,
                "target_clock": _clock(question.target_seconds),
                "over_target": bool(seconds > question.target_seconds),
                "root_cause": cause,
                "bucket": _bucket_of(cause),
                "assessment": UNSEEN_NOTE if hidden else _assess(question, result),
            })
        questions.extend(rows)
        if spent is None:
            spent = sum(r["seconds"] for r in rows)
        budget = segment["minutes"] * 60
        over = spent > budget
        overran = overran or over
        segments.append({
            "id": segment["id"], "label": segment["label"],
            "budget_seconds": budget, "budget_clock": _clock(budget),
            "spent_seconds": round(spent), "spent_clock": _clock(spent),
            "over_budget": over,
            "solved": solved_here, "total": len(rows),
        })

    set_segment = next((s for s in segments if s["id"] == "set"), None) or {}
    code_segment = next((s for s in segments if s["id"] == "codebase"), None) or {}
    verdict = _verdict(
        set_solved=set_segment.get("solved", 0),
        set_total=set_segment.get("total", 0),
        codebase_solved=code_segment.get("solved", 0),
        codebase_total=code_segment.get("total", 0),
        medium_solved=medium_solved, overran=overran, rule=fmt.pass_rule)

    signal = {bucket: sum(1 for c in causes if _bucket_of(c) == bucket)
              for bucket in CAUSE_BUCKETS}
    dominant = max(signal, key=lambda k: signal[k]) if any(signal.values()) else ""

    solved_total = sum(s["solved"] for s in segments)
    total = len(questions)
    spent_total = sum(s["spent_seconds"] for s in segments)

    report = {
        "exam_id": exam.id,
        "format": fmt.id,
        "format_label": fmt.label,
        "fingerprint": exam.fingerprint,
        "profile": exam.profile,
        "solved": solved_total,
        "total": total,
        "score": round(100 * solved_total / max(total, 1)),
        "within_clock": not overran,
        "seconds": spent_total,
        "clock": _clock(spent_total),
        "budget_clock": _clock(fmt.minutes * 60),
        "verdict": verdict,
        "segments": segments,
        "questions": questions,
        "signal": signal,
        "dominant_signal": dominant,
        "signal_note": BUCKET_MEANING.get(dominant, ""),
        "drills": _drills(causes, skills),
        "what_it_says": _readiness_paragraph(verdict, readiness, exam),
        "next": {
            "recomposes": True,
            "avoid": exam.fingerprint,
            "note": "The exam recomposes. Passing it once is a data point; "
                    "passing a different one next week is evidence.",
        },
        # No coach, no worked solutions, no hint tree — the exam is over, and what
        # replaces them is this page.
        "sealed": sorted(EXAM_SEAL.sealed),
        # And the last thing in the room says what it found, in the one language
        # it has. A closing line, selected by the verdict this report already
        # computed; it adds no information the page does not already carry.
        "examiner": examiner_view(verdict["code"]),
    }
    return report


READINESS_LEAD = {
    "READY": "What this says about readiness: on one set, under one clock, with "
             "nothing to lean on, you performed. One result is a data point. Two "
             "results a fortnight apart, on different sets, is readiness.",
    "CLOSE": "What this says about readiness: the knowledge is largely there and "
             "it is not yet reliable under the conditions. Reliability is the "
             "thing being measured here, because the interview measures it too.",
    "NOT_READY": "What this says about readiness: the gap is not effort and it is "
                 "not talent, it is evidence. Specific skills failed in specific "
                 "ways, all of them listed below, and every one of them moves.",
}


def _readiness_paragraph(verdict: dict, readiness, exam: Exam) -> str:
    """What the result says about readiness, in the terms the rest of the game
    uses: evidence, not weeks. Nothing in this project measures time spent
    playing, and the debrief is not going to be the first thing that does."""
    # Deliberately does not repeat the verdict: the report renders both, and a
    # paragraph that opens by restating its own headline reads like filler.
    lines = [READINESS_LEAD[verdict["code"]]]
    if readiness:
        passed = readiness.get("gates_passed", 0)
        total = readiness.get("gates_total", 0)
        failed = [g["label"] for g in readiness.get("gates", ()) if not g["passed"]]
        if total:
            lines.append(f"Readiness gates: {passed} of {total} met.")
        if failed:
            lines.append("Still open: " + "; ".join(failed[:4]) + ".")
    if exam.focus:
        lines.append("This exam was weighted toward " +
                     ", ".join(exam.focus[:3]) +
                     ", because that is where your evidence is thinnest. A pass "
                     "on a set weighted that way is worth more than a pass on a "
                     "kind one.")
    return " ".join(lines)


# ---------------------------------------------------------------------------
# 8. Self-check
# ---------------------------------------------------------------------------
#
# Five claims are made above and all five are cheap to disprove, so they are
# checked rather than asserted in prose:
#
#   1. every exam is solvable from the corpus
#   2. the difficulty mix stays in band
#   3. no help path is reachable
#   4. weak skills are genuinely over-represented
#   5. no exam repeats its question set
#
# `python -m gauntlet.finalexam` runs it. Solvability is structural: the corpus
# is validated at build time by running each canonical solution in the sandbox
# against tests derived from an independent reference, so a problem that is in
# the corpus at all has been solved once already by code nobody was allowed to
# copy. `deep=True` re-runs that in the sandbox for every problem the exams
# actually drew, which is slower and proves it again from scratch.

def _synthetic_player(rng) -> dict:
    """A plausible player, built by feeding real outcomes through the real skill
    model rather than by inventing numbers that the model would never produce."""
    states = skillmod.new_skills()
    shape = rng.choice(("fresh", "early", "lopsided", "broad", "strong"))
    if shape == "fresh":
        return states
    names = list(states)
    if shape == "lopsided":
        # Good at a handful of things, untouched everywhere else. The state that
        # most exposes a composer that weights by mastery alone.
        names = rng.sample(names, rng.randint(4, 8))
    attempts = {"early": (1, 6), "lopsided": (3, 14), "broad": (2, 10),
                "strong": (8, 20)}[shape]
    for name in names:
        for _ in range(rng.randint(*attempts)):
            difficulty = rng.choice(("TUTORIAL", "EASY", "EASY", "MEDIUM"))
            target = 420 if difficulty == "EASY" else 900
            solved = rng.random() < (0.85 if shape == "strong" else 0.55)
            skillmod.apply_outcome(
                states[name], solved=solved, difficulty=difficulty,
                hints_used=rng.choice((0, 0, 1, 2)),
                seconds=target * rng.uniform(0.5, 2.0), target_seconds=target,
                first_try=solved and rng.random() < 0.5, is_retest=False)
    return states


def self_check(corpus, *, trials: int = 200, players: int = 25,
               seed: int = 20260911, deep: bool = False) -> dict:
    """Compose `trials` exams across `players` player states and check all five
    claims. Returns a report; `ok` is the only field a caller needs."""
    rng = random.Random(seed)
    by_id = {p.id: p for p in corpus}
    pools = _pools(corpus)
    failures: list = []
    fingerprints_all: list = []
    exams_composed = 0
    used_ids: set = set()
    weak_hits = 0
    weak_questions = 0
    pool_weak_share_total = 0.0
    pool_samples = 0
    band_failures = 0
    leaks: list = []

    if audit_seal():
        failures.append(f"crutches not sealed by the exam: {audit_seal()}")

    per_player = max(1, trials // max(players, 1))
    for player_index in range(players):
        states = _synthetic_player(rng)
        focus = set(focus_skills(states))
        profile = rng.choice(config.INTERVIEW_PROFILES)
        history: list = []
        recent = set(rng.sample(list(by_id), rng.randint(0, 15)))

        for _ in range(per_player):
            if exams_composed >= trials:
                break
            exam = compose(corpus, states, profile=profile,
                           seed=rng.randrange(1 << 40), history=history,
                           recent_ids=recent)
            exams_composed += 1
            history.append(exam.fingerprint)
            fingerprints_all.append(exam.fingerprint)
            if exam.notes:
                failures.append(f"exam {exam.id} could not find an unseen set")

            # 1. solvable from the corpus
            for question in exam.questions:
                problem = by_id.get(question.problem_id)
                if problem is None:
                    failures.append(f"{question.problem_id} is not in the corpus")
                    continue
                used_ids.add(problem.id)
                if not problem.canonical_solution.strip():
                    failures.append(f"{problem.id} has no canonical solution")
                if not problem.all_tests:
                    failures.append(f"{problem.id} has no tests")
                if problem.entry.get("kind") not in ("function", "class_ops"):
                    failures.append(f"{problem.id} is not a writable question")

                # 3. no help path is reachable
                leaked = audit_view(exam_view(problem))
                if leaked:
                    leaks.append((problem.id, leaked))

            # 2. difficulty mix in band
            ok, reasons = within_band(exam)
            if not ok:
                band_failures += 1
                failures.append(f"exam {exam.id} out of band: {reasons}")

            # 4. weak skills over-represented.
            #
            # Measured as lift against the draw the exam would have made by
            # chance: for each slot, the share of ITS OWN eligible pool that
            # credits a weak skill is what an unweighted composer would have
            # produced. Comparing against the whole corpus instead would flatter
            # the number, because the bug slot can only ever return DEBUGGING and
            # that has nothing to do with the weighting.
            if focus:
                for question in exam.questions:
                    weak_questions += 1
                    weak_hits += question.skill in focus
                    slot_pool = [p for p in pools[question.role]
                                 if p.difficulty == question.difficulty]
                    if slot_pool:
                        pool_weak_share_total += sum(
                            1 for p in slot_pool if _skill_of(p) in focus
                        ) / len(slot_pool)
                        pool_samples += 1

    # 3. no help, at the seal level as well as the payload level
    for crutch in CRUTCHES:
        if not seal_for(mode=EXAM_MODE).blocks(crutch.id):
            failures.append(f"{crutch.id} survives interview mode")
        if not seal_for(mode=config.MODE_ADVENTURE,
                        boss_id="the_interviewer").blocks(crutch.id):
            failures.append(f"{crutch.id} survives the final boss")
    if refuse("HINTS").get("error") != "sealed":
        failures.append("refusals do not use the engine's sealed shape")
    if leaks:
        failures.append(f"{len(leaks)} question payloads leaked: {leaks[:3]}")

    # 5. no exam repeats its question set
    unique = len(set(fingerprints_all))
    duplicates = len(fingerprints_all) - unique

    weak_share = weak_hits / max(weak_questions, 1)
    pool_share = pool_weak_share_total / max(pool_samples, 1)
    over_representation = weak_share / pool_share if pool_share else 0.0
    if over_representation < 1.5:
        failures.append(
            f"weak skills only {over_representation:.2f}x over-represented")

    deep_report = {}
    if deep:
        deep_report = _deep_solve(sorted(used_ids), by_id)
        if deep_report["failed"]:
            failures.append(f"canonical solutions failed: {deep_report['failed'][:3]}")

    return {
        "ok": not failures,
        "exams": exams_composed,
        "players": players,
        "distinct_problems_used": len(used_ids),
        "unique_question_sets": unique,
        "duplicate_question_sets": duplicates,
        "band_failures": band_failures,
        "payload_leaks": len(leaks),
        "weak_skill_share": round(weak_share, 3),
        "pool_weak_share": round(pool_share, 3),
        "weak_over_representation": round(over_representation, 2),
        "deep": deep_report,
        "failures": failures,
    }


def _deep_solve(ids, by_id) -> dict:
    """Run every drawn problem's canonical solution against its own full test set
    in the sandbox. Slow, and the only proof of solvability that does not take
    the corpus build's word for it."""
    from . import sandbox
    failed = []
    for pid in ids:
        problem = by_id[pid]
        # Same call the corpus validator makes, same budgets. Diverging from it
        # would only mean this check and that one could disagree.
        report = sandbox.run_tests(problem.canonical_solution, problem.entry,
                                   problem.all_tests, timeout_ms=4000,
                                   wall_seconds=25)
        if not report.all_passed:
            failed.append(pid)
    return {"checked": len(ids), "failed": failed}


if __name__ == "__main__":   # pragma: no cover - a maintenance entry point
    import json
    import sys
    from .corpus import ensure as _ensure

    _report = self_check(_ensure(), deep="--deep" in sys.argv)
    print(json.dumps({k: v for k, v in _report.items() if k != "failures"},
                     indent=1))
    for _line in _report["failures"]:
        print("FAIL:", _line)
    sys.exit(0 if _report["ok"] else 1)
