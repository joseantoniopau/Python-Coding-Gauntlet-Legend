"""Dying, and where you wake up.

THE LINE, AND IT IS THE WHOLE DESIGN:

    DEATH REWINDS THE GAME. IT NEVER REWINDS THE PLAYER.

Gold, position, inventory, loot and the minutes since the last save are all fair
to lose, and losing them is the point — the brief asked for "a real threat to
lose progress if they die" and this is that threat, stated in the only currency
a game is allowed to charge. But attempts, skills, mastery, the spaced-repetition
schedule, the sealed hold-out ledger, boss records and interview runs are
EVIDENCE OF WHAT THIS PERSON CAN DO, and no amount of dying may take that away.

gauntlet/saves.py already holds this exact line for slot loads — "a save slot
rewinds the game, it does not rewind the player" — and gauntlet/db.py keeps the
transfer ledger monotone for the same reason. This module reuses both rather
than inventing a second answer: a death IS a load, with a ledger applied on top
of it and the graded tables never touched at all.

WHAT DEATH ACTUALLY IS, in five steps:

  1. Something takes health to zero. `adjudicate` decides whether that counts.
  2. The dying state goes into the undo ring and is sealed, so a bug here is
     recoverable by hand and by nothing the player can reach.
  3. `saves.wake_slot` names the last waking point — an anchor or a named slot,
     never a mere autosave. See THE ANCHOR RING in saves.py for why.
  4. That state is decoded but NOT applied. `wake()` folds the surviving half of
     the ledger from the dying state onto it, floors health and focus, wakes the
     companion, and clears any fight it finds.
  5. The result is written through `saves.apply_state`. The graded tables —
     attempts, boss_records, interview_runs, transfer_encounters — are never
     read and never written, because `restore_history=False`. That is not a
     precaution. It is the line, expressed as a keyword argument.

THE CONTINUITY, which is what makes this land rather than merely happen:
upkeep.py's alarm speeds the heart UP as health falls, from BPM_ONSET 72 to
BPM_MAX 132. Death is the inversion. Three beats, each half the rate of the one
before — 132, then 72, then 39 — and then a silence exactly as long as the beat
that does not come. 132 is upkeep's BPM_MAX, the rate the alarm was already
running at; 72 is its BPM_ONSET, the rate it began at. The heart goes back down
the ladder it climbed. The player has been listening to that heart get faster for the whole
fight. The moment it slows is the moment they understand.

TONE: quiet, and a little frightening. Not dramatic. The death screen states the
cost in numbers because a death screen that hides the cost is worse than one
that states it.
"""
from __future__ import annotations

import copy
import json
import math
import sqlite3
import time

from . import config, saves, upkeep, world

# ==========================================================================
# A. THE LEDGER — exactly what is rolled back, exactly what survives
# ==========================================================================
#
# The failure mode this section exists to prevent is not a bug that is written
# today. It is somebody in six months adding a key to engine.DEFAULT_STATE and
# not thinking about which side of the line it belongs on. A key that nobody
# classified defaults to whichever behaviour the code happens to have, and the
# code happens to rewind everything, so an unclassified key silently becomes a
# thing a player can be robbed of by dying.
#
# So both halves are written out by hand, every key carries the reason it is
# where it is, and `self_check` walks engine.DEFAULT_STATE and FAILS on any key
# that appears in neither list. Adding a state key now means answering one
# question, out loud, in this file.

# --------------------------------------------------------------------------
# ROLLED BACK. The game. Fair to lose, and losing it is the threat.
# --------------------------------------------------------------------------
ROLLED_BACK: dict = {
    "armor": "durability. upkeep floors effectiveness at half and nothing "
             "breaks, so a rewound kit can never make a fight unwinnable.",
    "weapons": "gear.",
    "equipped": "gear.",
    "inventory": "loot. named in the brief.",
    "consumables": "loot.",
    "potions": "ammunition. the pouch is a fight's worth of supplies and a "
               "fight is what you just lost.",
    "forge": "the metal bag and the blade ladder. loot, never evidence.",
    "legendaries": "artifacts owned. loot, however rare.",
    "hand": "the Obliging Hand's ledger travels with the artifact it belongs to.",
    "regalia": "worn things.",
    "attributes": "spent points. they come back with the xp that bought them.",
    "unspent_points": "same ledger as attributes; rewinding one without the "
                      "other would print points.",
    "build": "a label over attributes.",
    "class": "the class tree, which attributes pay for.",
    "moveset": "the book of lines. rebuilt from the movebook.",
    "movebook": "the book of moves. earned in fights, and the fights rewound.",
    "grimoire": "spells held.",
    "codex": "entries collected.",
    "companions": "who is walking with you.",
    "pets": "the companion roster, its knocks and its faints. `wake` heals what "
            "survives the rollback anyway — see E, the spiral.",
    "pet_fall": "an undelivered cutscene about a fall that is now un-fallen.",
    "cleared_bosses": "PROGRESSION, not the record. db.boss_records is the "
                      "record and it is never touched. Losing the gate flag "
                      "costs you a door; losing the record would cost you the "
                      "proof, and one of those is allowed.",
    "boss_rematch": "rematch counters, which price the purse. game economy.",
    "boss_fight": "an open boss fight. cleared outright by `wake`.",
    "encounter": "the fight you were in. cleared outright by `wake`.",
    "incantation": "the typed-Python field battle. cleared outright by `wake`.",
    "interview": "a measured run cannot be open here — a measured run is "
                 "death-proof, see F — so this is only ever already None.",
    "exam": "same as interview.",
    "quests": "quest progress. a turn-in is an anchor, so at most one is lost.",
    "world": "region control and route discovery.",
    "dungeon_run": "the descent. you are not in the dungeon any more.",
    "dungeons_cleared": "which floors are done. progression, not evidence.",
    "dungeon_map": "which room held which problem. rebuilt on the next descent.",
    "world_seed": "carried in the save, so it rewinds to the identical value. "
                  "listed rather than omitted because a seed that silently "
                  "rerolled would move the geography under the player.",
    "secrets_found": "loot with a better name.",
    "crit_streak": "a combat counter.",
    "daily": "today's quest board. it regenerates.",
    "story": "which beats have fired. the game's timeline, and the game is "
             "what rewinds. a re-shown scene is a cost worth paying for not "
             "having to reason about a beat that granted something twice.",
    "economy": "the earn ledger and the region taper. gold's bookkeeping "
               "rewinds with gold or the taper stops matching the purse.",
    "upkeep": "wear, repairs, afflictions. `wake` clears the afflictions it "
              "finds; the wear stays, because wear can never wall anybody.",
    "banter": "what has already been said.",
    "sanctuary": "a built place. game.",
    "captives": "who has been freed. game.",
    "escorts": "the zone companions' latch — which capture scenes have played, "
               "which drops were handed over, whether the Interviewer's sweep "
               "fired. IT REWINDS IN LOCKSTEP WITH `captives`, `inventory`, "
               "`cleared_bosses` and `dungeons_cleared`, and it has to, "
               "because it is a RECORD OF those four and every one of them is "
               "on this page. zonecompanions.state_of() reads the latch before "
               "it derives, so a latch that survived a rollback would report "
               "TAKEN for somebody the rewound world says is still walking — "
               "and `given` would claim a drop was handed over while the "
               "rewound bag is empty, which is the one way in this arc an item "
               "CAN be lost. Rewound, the derivation rebuilds the whole thing "
               "off the four keys on the next tick, which is what it is for.",
    "finale": "the ending's own bookkeeping.",
    "ending": "the seam's own bookkeeping — staging, the verdict, whether "
              "the coda has been seen. It rewinds IN LOCKSTEP WITH "
              "`captives`, and that is the whole of the reasoning: a "
              "surviving `ending.passed` over a rewound index would be a "
              "save claiming an ending the shelves have not had.",
    "antagonist": "the Null King's ledger of what he has already said.",
    "sages": "found, cleared, tolls paid. the GAUNTLET RUNGS rewind; the "
             "attempts that were graded inside them do not, because they are "
             "rows in `attempts`.",
    "arts": "arts learned from sages, which rewind with the sages.",
    "hunters": "the chase, the cooldowns, the trophies and any open apex "
               "fight. `wake` clears the open fight outright.",
}

# --------------------------------------------------------------------------
# SURVIVES. The record. Not the game's to take, whatever happens in it.
# --------------------------------------------------------------------------
SURVIVES: dict = {
    "skills": "MASTERY. the brief's own words: mastery moves only on graded "
              "evidence and is never removed by dying. this is the key that "
              "the whole rule is about.",
    "schedule": "the spaced-repetition schedule. named in the brief. an SRS "
                "that rewound would re-ask what you have already proved and "
                "would forget what you are actually due.",
    "solved_ids": "which problems this person has solved. graded evidence, and "
                  "rewinding it would let the same solve be farmed twice.",
    "perf_failed_ids": "which problems failed on performance. evidence, and "
                       "unflattering evidence at that, which is the test of "
                       "whether this list is honest.",
    "diagnostic": "the placement result. graded, and taken once.",
    "recent_ids": "what has been put in front of you lately. the anti-repeat "
                  "list is a small hold-out ledger and obeys the same rule: "
                  "the game may rewind, the record of what you have SEEN "
                  "may not.",
    "session": "this sitting's log, which the selector reads to bring a family "
               "back inside the session. same reasoning as recent_ids.",
    "achievements": "badges, and the one entry on this page that is here on "
                    "feel rather than on rule. every one of them is awarded off "
                    "`skills`, which "
                    "survives, so a rewound list would re-award instantly and "
                    "the only thing rewinding achieves is the half-second in "
                    "which the player sees a badge they earned disappear. "
                    "Taking a badge back for dying is the one item on this "
                    "page that would read as spite.",
    "settings": "volume, text scale, high contrast, reduced motion, colourblind "
                "palette. these are ACCESSIBILITY CHOICES, not game state. "
                "Resetting somebody's contrast setting because they lost a "
                "fight is indefensible and is exactly the kind of key that gets "
                "swept into a rollback by accident.",
}

# Fields inside `player`. The body rewinds; these two do not.
PLAYER_SURVIVES: tuple = (
    # You played those minutes. They happened.
    "playtime_seconds",
    # An intro is watched once. Re-showing it is not a cost, it is an annoyance.
    "intro_seen",
    # Whether the diagnostic has been sat. Pairs with `diagnostic` above; if the
    # flag rewound without the result, the player would sit it again for nothing.
    "diagnostic_done",
    # The player's own name, which is theirs.
    "name",
)

# Fields inside `stats`. Mixed by nature, so it gets a ledger of its own rather
# than a guess. Everything not named here rewinds with the game.
STATS_SURVIVE: tuple = (
    "probes", "probes_correct",      # graded micro-checks
    "interviews_passed",             # a measured run that was passed
    "chapters_graduated",            # curriculum progress, earned on evidence
    "hints_total",                   # you asked. dying does not un-ask.
    "sessions",                      # how many times this person sat down
)

# --------------------------------------------------------------------------
# MIXED. Two keys are not one thing, and pretending otherwise is how a rollback
# eats something it should not. Each gets a ledger at FIELD level instead —
# PLAYER_SURVIVES and STATS_SURVIVE above — and is named here so that `classify`
# has an answer for it and `self_check` does not report it as forgotten.
# --------------------------------------------------------------------------
MIXED: dict = {
    "player": "the body rewinds — position, gold, xp, level, health, focus. "
              "PLAYER_SURVIVES names the four fields inside it that do not, "
              "and playtime is the interesting one: those minutes happened.",
    "stats": "a bag of counters, some of them the game's and some of them "
             "evidence. STATS_SURVIVE names the evidence half, and it is "
             "carried MONOTONELY — raised, never lowered — for the same reason "
             "db.merge_transfer is monotone.",
}

# The four graded tables. Named here so that the assertion in `self_check` reads
# as a sentence rather than as a list of strings, and so that a fifth table
# added to db.py without thought shows up as a missing name here.
GRADED_TABLES: tuple = ("attempts", "boss_records", "interview_runs",
                        "transfer_encounters")


def classify(key: str) -> str:
    """'survives', 'rewinds', 'mixed', or 'unclassified'. The last one is a bug
    and `self_check` fails on it."""
    if key in SURVIVES:
        return "survives"
    if key in MIXED:
        return "mixed"
    if key in ROLLED_BACK:
        return "rewinds"
    return "unclassified"


def unclassified_keys(state: dict | None = None) -> list:
    """Every top-level state key nobody has taken a position on.

    Defaults to engine.DEFAULT_STATE, which is the real question: what does a
    brand new save contain that this file has not thought about. The import is
    local because engine imports half the package and this module is imported
    by saves.py, which engine imports.
    """
    if state is None:
        from . import engine
        state = engine.DEFAULT_STATE
    return sorted(k for k in state if classify(k) == "unclassified")


def ledger() -> dict:
    """The whole of A, as data, for a UI or a test that wants to print it."""
    return {
        "line": "Death rewinds the game. It never rewinds the player.",
        "rolled_back": dict(ROLLED_BACK),
        "survives": dict(SURVIVES),
        "mixed": dict(MIXED),
        "player_survives": list(PLAYER_SURVIVES),
        "stats_survive": list(STATS_SURVIVE),
        "graded_tables": list(GRADED_TABLES),
        "graded_tables_are_never_touched":
            "death loads with restore_history=False, so saves._restore_history "
            "is never reached and not one row of the four is read or written.",
    }


# ==========================================================================
# F. WHAT KILLS YOU — and what is not allowed to
# ==========================================================================
#
# There are exactly five places in this codebase where the player's health goes
# down. They were found by reading for it rather than by assuming, because "what
# can kill me" is a question a player is entitled to a true answer to.
#
# Named by FUNCTION first and line second, because the lines drift and the
# functions do not — this table was written against an older engine.py and every
# one of its line numbers had moved by the time anybody checked. Line numbers
# below are as of the last audit; the function names are the contract.
#
#   _enemy_turn        (engine.py:1383)  the vitals-less fallback swing
#   _enemy_turn        (engine.py:1441)  the real blow, via elements.resolve_damage
#   _open_player_turn  (engine.py:1514)  statuses and poison ticking
#   _incant_enemy_turn (engine.py:8538)  the typed-Python field battle's blow
#   _incant_open_turn  (engine.py:8575)  the same tick on the incantation side
#
# Three of them are BLOWS and two of them are TICKS, and the difference decides
# whether they are allowed to kill.
#
# A BLOW ANSWERS SOMETHING YOU DID. The enemy swings because a submission
# failed; engine's own comment says so — "the reward for typing the right thing
# is that nothing hits you, and the cost of typing the wrong thing is a blow".
# You chose, the game answered, and the answer may be fatal. That is a fair
# death and it is the only kind this module allows.
#
# A TICK ANSWERS NOTHING. Poison and burn land at the top of a turn, before the
# player has done anything, and engine orders them that way deliberately so that
# "a poisoned player finds out they are about to die while they still have a
# turn in which to drink something". If the tick could finish the job, that
# sentence would be false exactly when it mattered most — the player would be
# told they were dying by a death screen. So a tick FLOORS AT DOT_FLOOR and
# never kills. What it does instead is hand you one point of health and a turn,
# which is the scariest thing in the game and costs nothing to be fair.
#
# AND A MEASURED RUN IS DEATH-PROOF, which is the other half of F. During an
# interview or the final exam the Mender refuses to exist — upkeep.heal returns
# "There is no town in here. Finish the paper." — so a player cannot act on low
# health at all. Worse, killing them mid-run would DESTROY EVIDENCE: the run is
# graded work in progress, and the whole point of this file is that graded work
# is not the game's to take. So health floors at DOT_FLOOR for the length of the
# run, the paper gets finished and recorded, and the player walks out at one
# health with the alarm screaming, which is a consequence and not a punishment.

DOT_FLOOR = 1               # what a tick may never take you below

# Every cause the engine can hand us, and whether it may kill. Anything not
# named here is treated as LETHAL, because a new damage source that nobody
# classified should be conservative in the direction of the brief rather than in
# the direction of the player never being at risk.
CAUSES: dict = {
    "enemy_turn": {
        "lethal": True,
        "where": "engine._enemy_turn (the blow, and the fallback above it)",
        "why": "it answers a failed submission. you acted, it answered.",
        "line": "It answers the line you did not write.",
    },
    "incant_enemy_turn": {
        "lethal": True,
        "where": "engine._incant_enemy_turn",
        "why": "the same rule on the incantation side: a wasted turn is a turn "
               "the field gets to take.",
        "line": "The field takes the turn you wasted.",
    },
    "status_tick": {
        "lethal": False,
        "where": "engine._open_player_turn and engine._incant_open_turn",
        "why": "it lands before you can act. see F.",
        "line": "It is in you and it is patient. One point left.",
    },
    "hazard": {
        "lethal": False,
        "where": "nothing in the codebase does this today",
        "why": "a room that kills you for standing in it is a death you could "
               "not answer. Declared non-lethal in advance so that whoever "
               "adds the first hazard has to argue with this comment.",
        "line": "The room is doing something to you.",
    },
    "measured_run": {
        "lethal": False,
        "where": "any of the five, while state['interview'] or state['exam'] "
                 "is open",
        "why": "graded work in progress, and no town to walk to. see F.",
        "line": "Finish the paper. It cannot kill you in here.",
    },
}

LETHAL: frozenset = frozenset(k for k, v in CAUSES.items() if v["lethal"])
REPRIEVE: frozenset = frozenset(k for k, v in CAUSES.items() if not v["lethal"])


def measured(state: dict, encounter=None) -> bool:
    """Is a graded run open.

    The first two clauses are engine._sealed_in_interview's own test, so there
    is one answer to this question in the codebase and not two. The third —
    `exam` — is this file being conservative in the direction the rest of F is
    conservative in, and it is not redundant in the way it looks.

    engine._start_exam writes BOTH keys today: `state["exam"]` carries the paper
    and `state["interview"]` carries the run over it, and engine.finish_interview
    clears the two together. So while the engine behaves as it does now, `exam`
    is never set alone and this clause never decides anything. But the two keys
    are written by different lines and the cost of them parting is not symmetric:
    if `exam` were ever set without `interview`, a player could be KILLED in the
    middle of the final practical, which destroys graded work in progress and is
    the one thing F exists to forbid — and `battle_lock` would refuse a save that
    server.py's own rule explicitly allows. `wake()` already clears both keys for
    exactly this reason. This makes the other two doors agree with it.
    """
    state = state or {}
    if state.get("interview") or state.get("exam"):
        return True
    return getattr(encounter, "mode", "") == config.MODE_INTERVIEW


def adjudicate(state: dict, *, cause: str = "enemy_turn", encounter=None) -> dict:
    """Did that kill them.

    Call it where engine already asks whether health has reached zero — see
    THE WIRING CONTRACT at the foot of this file — AFTER the damage has landed
    and BEFORE anything is shown to the player.
    Returns a verdict; it MUTATES health only on the reprieve paths, where it
    puts the player back on DOT_FLOOR.

    Nothing here loads, saves or writes the database. `die` does that, and it
    only runs when this says so.
    """
    player = (state or {}).get("player") or {}
    health = int(player.get(upkeep.HEALTH_FIELD, 0) or 0)
    maximum = int(player.get(f"{upkeep.HEALTH_FIELD}_max", config.STAMINA_MAX)
                  or config.STAMINA_MAX)
    if health > 0:
        return {"dead": False, "reason": "standing", "health": health,
                "cause": cause, "alarm": upkeep.alarm_for(health, maximum)}

    if measured(state, encounter):
        cause = "measured_run"
    row = CAUSES.get(cause) or {"lethal": True, "line": "", "why": "unclassified"}

    if not row["lethal"]:
        player[upkeep.HEALTH_FIELD] = DOT_FLOOR
        return {
            "dead": False,
            "reason": "reprieve",
            "cause": cause,
            "health": DOT_FLOOR,
            "why": row["why"],
            "line": row.get("line", ""),
            "message": row.get("line", ""),
            "alarm": upkeep.alarm_for(DOT_FLOOR, maximum),
        }

    return {"dead": True, "reason": "killed", "cause": cause, "health": 0,
            "why": row["why"], "line": row.get("line", ""),
            "alarm": upkeep.alarm_for(0, maximum)}


# ==========================================================================
# D. SAVING ANYWHERE EXCEPT A BATTLE
# ==========================================================================
#
# The brief: "the player can save whenever but not during a battle." The whole
# difficulty is the word BATTLE, so here is the rule in one sentence the player
# can hold in their head:
#
#     YOU CANNOT SAVE WHILE SOMETHING IS TAKING A TURN AGAINST YOU.
#
# That is a rule about a live turn order, not about a location, and it settles
# every case the brief lists without needing a special clause for any of them:
#
#   an open encounter     state["encounter"]. LOCKED.
#   a dungeon fight       engine.dungeon_engage opens a normal encounter with
#                         `dungeon_room` set, so the encounter lock has it.
#                         Standing in a dungeon between rooms is NOT locked —
#                         nothing is swinging at you in a corridor.
#   a sage gauntlet rung  runs through encounters too. same lock, no new clause.
#   an apex hunt          state["hunters"]["fight"]. LOCKED, and the refusal
#                         names the way out: engine.hunt_flee always succeeds,
#                         turn one included, for nothing.
#   a boss fight          state["boss_fight"], which is four to six graded
#                         solves and therefore the fight most likely to be
#                         interrupted. LOCKED.
#   an incantation        state["incantation"], the typed-Python field battle.
#                         LOCKED.
#   a measured run        ALLOWED, and this is the one exception. server.py
#                         already says why — "saving during a measured run is
#                         allowed; it banks the run, it does not help with it.
#                         LOADING is sealed, because a load mid-exam is a
#                         retry" — and F makes the run death-proof, so the lock
#                         would be protecting the player from a risk that does
#                         not exist in there.
#
# Autosaves are NOT subject to this. They are the game writing down where you
# are, which is the one thing that should keep happening while you are in
# trouble, and they never land in a slot the player chose.

_BATTLE_KEYS: tuple = (
    ("encounter", "You are in a fight."),
    ("boss_fight", "You are in the middle of a boss."),
    ("incantation", "You are in the middle of a battle."),
)


def battle_lock(state: dict) -> dict | None:
    """None when saving is allowed. Otherwise a refusal with a player-facing
    `message` that says what is happening and what to do about it.

    `saves.save_to_slot` calls this itself, so the lock is at the door rather
    than in the server, and a second caller cannot walk around it.
    """
    state = state or {}
    if measured(state):
        return None                      # banks the run, does not help with it

    for key, what in _BATTLE_KEYS:
        if state.get(key):
            return {
                "allowed": False, "what": key,
                "message": (f"{what} You cannot save during a battle — finish "
                            "it, walk out of it, or lose it. The game saves "
                            "itself when you reach a new region and when a "
                            "boss goes down."),
            }

    if ((state.get("hunters") or {}).get("fight")):
        return {
            "allowed": False, "what": "apex_hunt",
            "message": ("The apex is standing in front of you. You cannot save "
                        "during a hunt. Walking away always works and costs "
                        "nothing, and you can save the moment you do."),
        }
    return None


def save_allowed(state: dict) -> bool:
    return battle_lock(state) is None


# ==========================================================================
# E. THE SPIRAL, WHICH IS THE REAL RISK
# ==========================================================================
#
# A player who dies, wakes underpowered, and dies again has not found a
# challenge. They have found a wall, and a wall in a game whose only job is to
# keep somebody practising is the worst bug in the product. It is also the
# easiest one to write by accident, because "you wake exactly as you were saved"
# sounds principled right up until the save was taken at four health.
#
# upkeep.py already wrote the argument that settles this, about its free healer:
#
#     "health is the gate on ATTEMPTS, and attempts are the entire mechanism by
#      which anybody gets better at this. Charge gold for healing and you have
#      built a game in which the players who are struggling most ... are exactly
#      the players who can least afford another go."
#
# That reasoning applies double here, because a death is the moment a struggling
# player is most likely to close the tab. So waking has a floor, and the floor is
# a FRACTION measured against upkeep's alarm rather than a number picked to feel
# right. Against upkeep as it stands today:
#
#   config.STAMINA_MAX                20
#   upkeep.ALARM_ONSET                0.25  -> pulse and sound begin at 5
#   upkeep.ALARM_BANDS DIRE           0.10  -> the heartbeat itself begins at 2
#   config.STAMINA_LOSS_FAILED_SUBMIT 2     -> a failed submission costs 2
#   WAKE_HEALTH_FRACTION              0.5   -> you wake at 10, band WORN
#
# Ten is five failed submissions in hand, and it is above every band that makes a
# noise. Waking inside the red pulse would be the spiral with a soundtrack: the
# player opens their eyes to the thing that killed them, still audible. They wake
# in silence, in the band upkeep itself describes as "a colour shift and nothing
# else. Not an alarm yet."
#
# Every one of those five numbers is READ from upkeep and config at runtime by
# `_prove_waking_cannot_spiral`, never copied. A pass that retunes the alarm —
# and one has already retuned it once — moves this floor with it or fails the
# self-check, which is the only way two files stay in agreement over time.
#
# The floor is a floor and not a heal. `max(saved, floor)` — a player who
# anchored at full health wakes at full health, and waking never puts you below
# where you saved. Dying does not top you up, it stops you from being stranded.
#
# WHAT ELSE WAKING FIXES, and each one is a documented way to strand somebody:
#   * afflictions cleared     — waking still poisoned is dying twice
#   * focus to full           — focus buys hints; elements.py's own floor is
#                               Oracle plus Reveal Path, and a player who cannot
#                               afford to ask a question has dead-ended
#   * the companion woken     — pets.py: "THE COMPANION IS THE HINT SYSTEM"
#   * every live fight closed — you do not wake up inside the thing that killed
#                               you, whatever the save happened to contain
#
# WHAT WAKING DOES NOT FIX, on purpose:
#   * armour wear   — upkeep floors effectiveness at 50% and NOTHING BREAKS, so
#                     a degraded kit makes fights longer and never unwinnable.
#                     More typing is the thing the game wanted anyway.
#   * gold, xp, loot, position — that is the cost. It is the whole feature.

WAKE_HEALTH_FRACTION = 0.5


def wake_health(maximum: int) -> int:
    """The floor, in points. Rounded UP so the fraction can never round into
    the alarm band on an odd maximum."""
    maximum = max(1, int(maximum or config.STAMINA_MAX))
    return min(maximum, int(math.ceil(maximum * WAKE_HEALTH_FRACTION)))


def _carry(source: dict, target: dict, keys) -> list:
    moved = []
    for key in keys:
        if key in source:
            target[key] = copy.deepcopy(source[key])
            moved.append(key)
    return moved


def wake(dying: dict, restored: dict) -> dict:
    """Fold the surviving half of the ledger onto a restored state.

    Pure: it reads `dying`, writes `restored`, touches no database and no disk,
    and is the function a test should reach for when it wants to ask what death
    costs without arranging for anybody to die.
    """
    dying = dying or {}
    restored = restored or {}

    carried = _carry(dying, restored, SURVIVES)

    player = restored.setdefault("player", {})
    dying_player = dying.get("player") or {}
    carried_player = _carry(dying_player, player, PLAYER_SURVIVES)

    stats = restored.setdefault("stats", {})
    dying_stats = dying.get("stats") or {}
    carried_stats = []
    for key in STATS_SURVIVE:
        if key in dying_stats:
            # Monotone, like db.merge_transfer: a counter that survives may be
            # raised by the dying state and never lowered by the restored one.
            # These count things that happened, and dying did not un-happen them.
            try:
                stats[key] = max(int(stats.get(key, 0) or 0),
                                 int(dying_stats.get(key, 0) or 0))
            except (TypeError, ValueError):
                stats[key] = dying_stats[key]
            carried_stats.append(key)

    # No fight survives waking, whatever the anchor happened to hold. An anchor
    # is written outside combat, so this is normally a no-op; it is here because
    # "normally" is not a guarantee and waking inside the fight that killed you
    # is the spiral in its purest form.
    closed = []
    for key in ("encounter", "boss_fight", "incantation", "interview", "exam",
                "pet_fall"):
        if restored.get(key):
            closed.append(key)
        restored[key] = None
    hunt = restored.get("hunters")
    if isinstance(hunt, dict) and hunt.get("fight"):
        hunt["fight"] = None
        closed.append("hunters.fight")

    # Health and focus floors, and the companion.
    maximum = int(player.get(f"{upkeep.HEALTH_FIELD}_max", config.STAMINA_MAX)
                  or config.STAMINA_MAX)
    saved_health = int(player.get(upkeep.HEALTH_FIELD, 0) or 0)
    floor = wake_health(maximum)
    player[upkeep.HEALTH_FIELD] = max(saved_health, floor)
    focus_max = int(player.get(f"{upkeep.FOCUS_FIELD}_max", config.MANA_MAX)
                    or config.MANA_MAX)
    player[upkeep.FOCUS_FIELD] = focus_max

    block = upkeep.ensure(restored)
    cleared_statuses = list(block.get("statuses") or [])
    block["statuses"] = []
    revived = upkeep.revive_pets(restored)

    return {
        "state": restored,
        "carried": carried,
        "carried_player": carried_player,
        "carried_stats": carried_stats,
        "closed": closed,
        "health": player[upkeep.HEALTH_FIELD],
        "health_floor": floor,
        "health_max": maximum,
        "focus": focus_max,
        "statuses_cleared": len(cleared_statuses),
        "pets_revived": revived.get("count", 0),
        "alarm": upkeep.alarm_for(player[upkeep.HEALTH_FIELD], maximum),
    }


# ==========================================================================
# C. SAVE POINTS, AND KNOWING YOU WERE SAVED
# ==========================================================================
#
# The brief asks for a save on a new area and after a boss fight. Both already
# fire — engine.py:3502 calls saves.autosave(..., "region_entered") and 6538 and
# 7582 both call it with "boss_defeated", unthrottled — so nothing new had to be
# invented. What was missing is that they were INDISTINGUISHABLE from the
# autosave after every cleared encounter, and that mattered in two ways.
#
# THE FIRST IS EVICTION, and it is arithmetic: see THE ANCHOR RING in saves.py.
# Four cleared encounters push a region entry out of a four-deep ring.
#
# THE SECOND IS THE ONE THE BRIEF IS ACTUALLY ABOUT. A threat is only fair if
# the player knows where the floor is. If the game saves silently, dying is a
# surprise about how much you lost; if it says so, dying is a consequence of a
# decision you made after being told. `announce` is the line, and it is meant to
# be shown as a small persistent note rather than a toast that fades — a player
# who looks up in the middle of a fight should be able to find out where they
# will wake without leaving the fight.
#
# AND THE DECISION ABOUT encounter_cleared, stated because it was asked: it is
# NOT a waking point, and it stays an autosave. Waking at the fight you cleared
# ninety seconds ago costs a player nothing but the fight they were in, and a
# cost of one fight is not the "real threat to lose progress" the brief asked
# for. It stays in the autosave ring because a CRASH should cost one fight —
# that is a different failure with a different fair price. The two rings exist
# precisely so those two prices can differ.

ANCHOR_LINES: dict = {
    "region_entered": "Saved. You would wake here.",
    "boss_defeated": "Saved. That fight is behind you for good.",
    "quest_turned_in": "Saved.",
    "level_gained": "Saved.",
    "session_end": "Saved.",
    "game_started": "Saved. This is where you would wake up.",
}


def announce(written: dict | None) -> dict | None:
    """The note to put on screen when an anchor lands. None when nothing did.

    Hand it whatever `saves.autosave` returned, or what `saves.anchor` returned.
    Deliberately total: an unknown reason still produces a line, because the
    player being told is more important than the wording being bespoke.
    """
    if not written:
        return None
    row = written.get("anchor") if "anchor" in written else written
    if not row or row.get("kind") != saves.KIND_ANCHOR:
        return None
    summary = row.get("summary") or {}
    reason = row.get("reason", "")
    return {
        "saved": True,
        "slot_id": row.get("slot_id", ""),
        "reason": reason,
        "line": ANCHOR_LINES.get(reason, "Saved."),
        "where": summary.get("region", ""),
        "at": summary.get("saved_at", 0.0),
        "level": summary.get("level", 1),
        "gold": summary.get("gold", 0),
        # For a persistent corner note: "Waking point: Fields of Syntax, 12m ago"
        "label": f"Waking point: {summary.get('region', 'unknown')}",
    }


def waking_point(conn: sqlite3.Connection, *, now: float | None = None) -> dict:
    """Where the player would wake if they died right now. Read-only, cheap.

    `announce` is the moment a save lands; this is the standing answer, and C
    needs both. A toast that has faded tells a player nothing when they look up
    mid-fight and want to know what a bad submission is actually worth, so this
    is meant to live in a corner of the HUD permanently — "Waking point: Fields
    of Syntax, 12m ago" — and it is the number that makes the threat FAIR rather
    than merely present.

    It also covers the one seam in `announce`: `saves.autosave` returns None when
    the state is byte-for-byte what the newest autosave already holds, and on
    that path the caller never sees the anchor row even though one was written.
    An anchor event always moves the state in practice — you cannot enter a
    region without changing region — but "in practice" is not a guarantee, and
    this function never depends on having caught the moment.
    """
    now = time.time() if now is None else now
    slot = saves.wake_slot(conn)
    if slot is None:
        return {
            "known": False, "slot_id": "", "region": "", "last_event": "",
            "age_seconds": 0.0, "age": "",
            "line": "No waking point yet. Nothing to lose, for the moment.",
        }
    summary = slot.get("summary") or {}
    age = max(0.0, now - float(summary.get("saved_at", now) or now))
    return {
        "known": True,
        "slot_id": slot["slot_id"],
        "kind": slot["kind"],
        "reason": slot.get("reason", ""),
        "reason_label": saves.AUTOSAVE_EVENTS.get(slot.get("reason", ""),
                                                  "Saved by hand"),
        "region": summary.get("region", ""),
        "last_event": summary.get("last_event", ""),
        "level": summary.get("level", 1),
        "gold": summary.get("gold", 0),
        "age_seconds": round(age, 1),
        "age": _elapsed_text(age),
        "line": "Waking point: %s, %s ago." % (summary.get("region", "unknown"),
                                               _elapsed_text(age)),
    }


def ensure_wake_point(conn: sqlite3.Connection, state: dict) -> dict | None:
    """Guarantee somewhere to wake up. Call once at boot, after the state loads.

    Without this, a player who dies in their first fight — before a region has
    been entered, before a level, before anything — has no anchor at all. The
    fallback in `die` would still catch them, but a fallback that runs on every
    new game is not a fallback, it is the design, and it should not be.
    """
    if saves.wake_slot(conn) is not None:
        return None
    return saves.anchor(conn, state, "game_started",
                        note="The first waking point")


# ==========================================================================
# B. WAKING UP — the sound, the screen, and the words
# ==========================================================================
#
# WHO OWNS WHAT, because this half of the feature is split across three files
# and a reader needs to know which one to open:
#
#   web/js/audio.js     MAKES THE SOUND. heartbeatStop() schedules the three
#                       beats on the audio clock in one call.
#   web/js/deathfx.js   DRAWS THE SCREEN, against the same offsets, and turns a
#                       report into the words on it via deathLines().
#   THIS FILE           SUPPLIES THE NUMBERS. Every tempo in the table below,
#                       and every figure on that screen. scripts/verify/death.mjs
#                       enforces the second half of that literally: it fails on
#                       "numbers on the death screen that gauntlet/death.py
#                       never supplied". `report()` is the wire shape it feeds.
#
# THE SOUND is continuous with upkeep.py's alarm by construction rather than by
# resemblance. The alarm runs from BPM_ONSET 72 at the moment health starts to
# matter up to BPM_MAX 132 on the floor, and upkeep asserts pulse_hz == bpm/60
# so the red pulse on the sprite and the thump underneath it are one clock.
# Death does not start near where the alarm ended. It starts ON it, and then
# runs the same ramp backwards. The exact table is below.
#
# THE SCREEN says what it cost. A death screen that hides the cost is worse than
# one that states it: the player cannot decide whether to be more careful if the
# game will not tell them what carelessness is worth. And it says what survived,
# in the same breath and the same size, because that is the sentence this whole
# feature is built to be able to say — and `report()` sends the kept half
# unconditionally, with the cost half allowed to be empty, so a player who lost
# nothing is still told what dying cannot take.

# THE THREE TEMPOS, and not one of them is invented. web/js/audio.js carries the
# identical table, scripts/verify/death.mjs reads upkeep.py and fails if any of
# the three files drift, and web/js/deathfx.js draws its fade against these same
# offsets so picture and sound are one clock — the contract upkeep.py already
# holds between its own pulse_hz and bpm.
#
#   132  upkeep.BPM_MAX     the rate the alarm is ALREADY running at when health
#                           hits zero, so the first death beat is the alarm's
#                           next beat and the seam is inaudible
#    72  upkeep.BPM_ONSET   the rate the alarm spoke at when it first spoke. The
#                           heart comes back to where the warning began
#    39  72 x (72/132)      the same geometric step continued once more, off the
#                           bottom of the scale the alarm can express at all
#
# Periods 455, 833 and 1538 ms. Each beat falls one period of ITS OWN tempo
# after the one before, so the gaps are 833 and 1538 and every gap is longer
# than the last. The first gap is already 1.83x the 455ms the player has been
# hearing: the heart does not ease off, it MISSES. That stumble is the moment
# the player understands, which is why the sequence starts slowing on beat one
# rather than politely holding tempo for a bar first.
#
# The silence afterwards is 1538 ms — one more of the last interval, not the
# next step of the ramp, which would be 2816 and is far too long to hold a black
# screen for. The ear extrapolates the interval it most recently heard, so
# holding exactly 1538 puts the end of the silence on the beat that did not
# come. The player feels the absence land rather than waiting through it.

DEATH_BEATS = 3                       # the brief: "1 then 2 then 3"
BPM_FLOOR = upkeep.BPM_MAX            # 132. where the alarm ends, where death starts
BPM_REST = upkeep.BPM_ONSET           # 72. where the alarm began

DEATH_BEAT_BPM: tuple = (
    BPM_FLOOR,
    BPM_REST,
    int(round(BPM_REST * BPM_REST / float(BPM_FLOOR))),
)
DEATH_BEAT_MS: tuple = tuple(int(round(60000.0 / bpm)) for bpm in DEATH_BEAT_BPM)


def _beat_offsets() -> tuple:
    at = [0]
    for ms in DEATH_BEAT_MS[1:]:
        at.append(at[-1] + ms)
    return tuple(at)


DEATH_BEAT_AT: tuple = _beat_offsets()
DEATH_SILENCE_MS = DEATH_BEAT_MS[-1]
BLACK_AT_MS = DEATH_BEAT_AT[-1]
DEATH_TOTAL_MS = BLACK_AT_MS + DEATH_SILENCE_MS


def heartbeat_schedule(*, reduced_motion: bool = False) -> dict:
    """The exact timeline, in milliseconds, for the client to play and draw to.

    audio.js schedules the beats on the AUDIO clock rather than off a timer —
    setTimeout drifts and is throttled outright in a background tab, and these
    three intervals are the entire effect. This table is the shared truth the
    two sides are scheduled against, and the numbers a server-rendered client
    would need if it had no audio rig at all.

    `reduced_motion` shortens nothing that is heard. It removes the iris and the
    fade; the beats and the silence are the content, not the motion.
    """
    beats = []
    for index, bpm in enumerate(DEATH_BEAT_BPM):
        beats.append({
            "index": index,
            "at_ms": DEATH_BEAT_AT[index],
            "bpm": bpm,
            "hz": round(bpm / 60.0, 3),
            "interval_ms": DEATH_BEAT_MS[index],
            # The alarm's own gain and pitch spans, walked back down at half a
            # span a beat. Beat one IS the alarm's severity-1 beat, which is
            # what makes the seam inaudible. audio.deathBeatShape computes the
            # same three numbers from the same two spans.
            "gain": round(0.36 - index * 0.10, 3),
            "base_hz": round(46.0 - index * 6.0, 1),
            # The last beat does not close its pair. Nothing answers it.
            "pair": index < DEATH_BEATS - 1,
        })
    return {
        "beats": beats,
        "beat_count": DEATH_BEATS,
        "bpm": list(DEATH_BEAT_BPM),
        "at_ms": list(DEATH_BEAT_AT),
        "interval_ms": list(DEATH_BEAT_MS),
        "starts_at_bpm": BPM_FLOOR,
        "returns_to_bpm": BPM_REST,
        "continuous_with": "upkeep.BPM_MAX and upkeep.BPM_ONSET",
        "fade_from_ms": 0,
        "fade_to_ms": 0 if reduced_motion else BLACK_AT_MS,
        "black_at_ms": BLACK_AT_MS,
        "silence_ms": DEATH_SILENCE_MS,
        "screen_at_ms": DEATH_TOTAL_MS,
        "total_ms": DEATH_TOTAL_MS,
        "reduced_motion": bool(reduced_motion),
        # upkeep's own DIRE colour, so the last red the player sees is the red
        # that was pulsing at them a second ago.
        "colour": upkeep.ALARM_BANDS[0].colour,
        "black": "#000000",
    }


def _elapsed_text(seconds: float) -> str:
    """How long the player is about to lose, written the way a stopwatch would.

    "12m 22s", not "about twelve minutes". The brief asks for a threat, and a
    threat stated vaguely is a threat the player cannot calibrate against. The
    seconds are there because on a bad run they are the part that stings.
    """
    seconds = max(0, int(seconds or 0))
    if seconds >= 3600:
        return saves.format_playtime(seconds)
    return "%dm %02ds" % divmod(seconds, 60)


def _as_int(value, fallback: int = 0):
    """A number for the screen, out of whatever was actually in the dict.

    `report` is TOTAL — see its docstring — and totality has to survive the
    values as well as the keys. `die` always builds `lost` and `kept` out of
    arithmetic, so nothing it produces reaches here as a string; but `report` is
    a public function with a published wire shape, deathfx.js is handed whatever
    a server route decided to send, and a death screen that raises instead of
    drawing is the trap rule E forbids. An unreadable number costs the screen one
    clause. It may not cost the player the way out.
    """
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return fallback


def _as_text(value) -> str:
    return value if isinstance(value, str) else ""


def report(result: dict) -> dict:
    """THE WIRE SHAPE web/js/deathfx.js reads, and the contract it is tested on.

    `deathfx.deathLines(report)` builds the words from exactly three groups —
    `wake`, `cost` and `kept` — and scripts/verify/death.mjs then checks that
    every digit on the finished screen came out of this dict. So this function
    is the only place a number reaches a dying player, and anything it omits is
    a sentence deathfx simply will not print.

    THREE RULES IT IS BUILT TO:

      * The COST half may be empty. A player who anchored thirty seconds ago
        lost nothing, and deathfx drops the lines rather than printing zeroes.
      * The KEPT half is never empty and carries `attempts`, `skills`, `mastery`
        and `due` unconditionally. That is the sentence this module exists to
        say, and it is said on every death including the ones that cost nothing.
      * A player with no save still gets a `wake` group with no region in it,
        which is deathfx's NO_SAVE_LINE case — "you can keep going" — rather
        than a blank screen. Nothing dead-ends, the death screen included.
    """
    lost = result.get("lost") or {}
    kept = result.get("kept") or {}
    woke = result.get("woke_at") or {}
    mastery = _as_int(kept.get("mastery_percent"), None)
    return {
        "wake": {
            "slot": _as_text(woke.get("slot_id")),
            "label": _as_text(woke.get("last_event")),
            "region": "" if woke.get("fallback") else _as_text(woke.get("region")),
            "reason": _as_text(woke.get("reason")),
        },
        "cost": {
            "playtime": _as_text(lost.get("elapsed_text")),
            "gold": _as_int(lost.get("gold")),
            "items": _as_int(lost.get("items")),
            "levels": _as_int(lost.get("levels")),
        },
        "kept": {
            "attempts": _as_int(kept.get("attempts")),
            "skills": _as_int(kept.get("skills")),
            "mastery": "" if mastery is None else "%d%%" % mastery,
            "due": _as_int(kept.get("scheduled")),
        },
    }


# ==========================================================================
# THE ONE CALL SITE — everything above, wired together
# ==========================================================================

def check(conn: sqlite3.Connection, state: dict, *, cause: str = "enemy_turn",
          encounter=None, readiness: dict | None = None) -> dict:
    """Adjudicate, and die if that is the verdict. The single entry point.

    Call it at the two sites named in THE WIRING CONTRACT at the foot of this
    file, after the damage has landed. The caller MUST
    adopt `result["state"]` as its own in-memory state when `result["died"]` is
    true, exactly as it must after `saves.load_slot`.
    """
    verdict = adjudicate(state, cause=cause, encounter=encounter)
    if not verdict["dead"]:
        return {"died": False, **verdict, "state": state}
    return die(conn, state, cause=verdict["cause"], readiness=readiness)


def die(conn: sqlite3.Connection, state: dict, *, cause: str = "enemy_turn",
        readiness: dict | None = None, now: float | None = None) -> dict:
    """Roll the game back to the last waking point. Never touch the record.

    Ordering, and every step of it is deliberate:
      1. snapshot the dying state, then SEAL the snapshot, so the death is
         recoverable by a developer and not by the player.
      2. find the waking point. If there is none, wake where you fell — a
         setback of nothing is still not a wall, and a wall is the one outcome
         forbidden.
      3. decode WITHOUT applying, and with restore_history=False. That argument
         is the line: it is what keeps saves._restore_history away from
         `attempts`, `boss_records` and `interview_runs`, all of which would
         otherwise be DELETEd and rewritten from a manual slot's snapshot.
      4. fold the ledger, then apply.
    """
    now = time.time() if now is None else now
    dying = state or {}
    before = _measure(conn, dying)

    # The forensic snapshot. It takes a slot in the undo ring, which is a real
    # cost — UNDO_RING is 4, so four deaths in a row evict every pre-load
    # snapshot the player had. That is accepted rather than overlooked: the undo
    # ring is by definition where "the state that was just replaced" lives, a
    # death is exactly that, and a fifth ring to hold one row would be a table
    # for a case nobody reaches. It is SEALED the moment it is written, so
    # `undo_load` will never offer the player the moment before they died —
    # undoing a death would make dying free, which is the one thing this whole
    # feature is not.
    snapshot = saves.snapshot_for_undo(
        conn, dying, note="Died", include_history=False)
    saves.seal_snapshot(conn, snapshot["slot_id"])

    slot = saves.wake_slot(conn)
    if slot is None:
        # Nothing readable to wake at. Not a wall: the player gets up where they
        # fell, keeps everything, and an anchor is written so this branch is not
        # reachable twice in a row.
        restored = copy.deepcopy(dying)
        woke_from = {"slot_id": "", "kind": "", "reason": "fell_where_you_stood",
                     "summary": {}}
        fallback = True
    else:
        loaded = saves.load_slot(conn, slot["slot_id"], current_state=None,
                                 apply=False, restore_history=False)
        restored = loaded["state"]
        woke_from = slot
        fallback = False

    woken = wake(dying, restored)
    new_state = woken["state"]
    saves.apply_state(conn, new_state)
    if fallback:
        saves.anchor(conn, new_state, "game_started",
                     note="Woke where you fell")

    after = _measure(conn, new_state)
    summary = (woke_from.get("summary") or {})
    elapsed = max(0.0, now - float(summary.get("saved_at", now) or now))
    lost = {
        "gold": max(0, before["gold"] - after["gold"]),
        "xp": max(0, before["xp"] - after["xp"]),
        "levels": max(0, before["level"] - after["level"]),
        "items": max(0, before["items"] - after["items"]),
        "potions": max(0, before["potions"] - after["potions"]),
        "bosses": max(0, before["bosses"] - after["bosses"]),
        "seconds": round(elapsed, 1),
        "elapsed_text": _elapsed_text(elapsed) if not fallback else "",
        "region_left": before["region"],
    }
    kept = {
        "solved": after["solved"],
        "attempts": after["attempts"],
        "skills": after["skills_with_evidence"],
        "mastery_total": after["mastery_total"],
        "boss_records": after["boss_records"],
        "interview_runs": after["interview_runs"],
        "transfer_rows": after["transfer_rows"],
        "scheduled": after["scheduled"],
        # Average mastery across the skills that have evidence behind them,
        # as a percent, which is the one figure on the death screen that is
        # about the PLAYER rather than about the run they just lost.
        "mastery_percent": (
            int(round(100.0 * after["mastery_total"]
                      / max(1, after["skills_with_evidence"])))
            if after["skills_with_evidence"] else 0),
        # Proof, not a claim. These are the four tables read back AFTER the
        # rollback and compared with what they held before it.
        "graded_unchanged": all(before[k] == after[k] for k in
                                ("attempts", "boss_records", "interview_runs",
                                 "transfer_rows")),
        "mastery_unchanged": before["mastery_total"] == after["mastery_total"],
    }
    row = CAUSES.get(cause) or {}
    result = {
        "ok": True,
        "died": True,
        "cause": cause,
        "cause_line": row.get("line", ""),
        "state": new_state,
        "woke_at": {
            "slot_id": woke_from.get("slot_id", ""),
            "kind": woke_from.get("kind", ""),
            "reason": woke_from.get("reason", ""),
            "reason_label": saves.AUTOSAVE_EVENTS.get(
                woke_from.get("reason", ""), ""),
            "region": summary.get("region", after["region"]),
            "last_event": summary.get("last_event", ""),
            "saved_at": summary.get("saved_at", 0.0),
            "age_seconds": round(elapsed, 1),
            "fallback": fallback,
        },
        "lost": lost,
        "kept": kept,
        "wake": {k: v for k, v in woken.items() if k != "state"},
        "forensic_slot": snapshot["slot_id"],
        "undo_available": False,       # a death is not undoable. see seal_snapshot
        "heartbeat": heartbeat_schedule(),
    }
    result["report"] = report(result)
    return result


def _measure(conn: sqlite3.Connection, state: dict) -> dict:
    """Everything both halves of the ledger are counted in, in one pass.

    Total by design: a death must never fail because a counter could not be
    read. A number that cannot be computed is zero and the screen simply says
    less, which is a worse death screen and not a broken game.
    """
    from . import db
    player = (state or {}).get("player") or {}
    skills = (state or {}).get("skills") or {}
    mastery = 0.0
    with_evidence = 0
    for row in skills.values():
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get("mastery", 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        mastery += value
        if value > 0 or int(row.get("clears", 0) or 0) > 0:
            with_evidence += 1

    def count(sql: str) -> int:
        try:
            return int(conn.execute(sql).fetchone()[0])
        except Exception:
            return 0

    potion_pouch = (state or {}).get("potions") or {}
    try:
        potion_count = sum(int(v or 0) for v in potion_pouch.values()
                           if isinstance(v, (int, float)))
    except (TypeError, ValueError):
        potion_count = 0

    return {
        "gold": int(player.get("gold", 0) or 0),
        "xp": int(player.get("xp", 0) or 0),
        "level": int(player.get("level", 1) or 1),
        "region": (world.REGION_BY_ID.get(player.get("region", ""), {}) or {}
                   ).get("name", player.get("region", "")),
        "items": len((state or {}).get("inventory") or []),
        "potions": potion_count,
        "bosses": len((state or {}).get("cleared_bosses") or []),
        "solved": len((state or {}).get("solved_ids") or []),
        "scheduled": len((state or {}).get("schedule") or {}),
        "skills_with_evidence": with_evidence,
        "mastery_total": round(mastery, 4),
        "attempts": count("SELECT COUNT(*) FROM attempts"),
        "boss_records": count("SELECT COUNT(*) FROM boss_records"),
        "interview_runs": count("SELECT COUNT(*) FROM interview_runs"),
        "transfer_rows": count("SELECT COUNT(*) FROM transfer_encounters"),
    }


# ==========================================================================
# SELF-CHECK — every number this file asserts, computed rather than claimed
# ==========================================================================
#
# The interesting proofs in here are the two that actually kill somebody: a
# death over a MANUAL slot (which is the one that carries a history snapshot and
# would therefore DELETE the attempts table if `restore_history` were left at
# its default) and a death in a row, five times, to prove the spiral is closed.

def _prove_ledger_is_total() -> dict:
    """Every key in a real DEFAULT_STATE has a side. No exceptions, no default."""
    from . import engine
    missing = unclassified_keys(engine.DEFAULT_STATE)
    overlap = sorted(set(SURVIVES) & set(ROLLED_BACK))
    # The parentheses are load-bearing. `-` binds tighter than `|`, so without
    # them this reads as SURVIVES | ROLLED_BACK | (MIXED - DEFAULT_STATE) and
    # reports every classified key in the file as stray — which is both useless
    # and, worse, unable to ever detect a real one.
    stray = sorted((set(SURVIVES) | set(ROLLED_BACK) | set(MIXED))
                   - set(engine.DEFAULT_STATE))
    return {
        "keys": len(engine.DEFAULT_STATE),
        "survives": len(SURVIVES),
        "rewinds": len(ROLLED_BACK),
        "mixed": len(MIXED),
        "unclassified": missing,
        "total": not missing,
        "no_key_on_both_sides": not overlap,
        "both_sides": overlap,
        "named_but_not_in_state": stray,
        "every_entry_states_a_reason": all(
            bool(str(v).strip()) for d in (SURVIVES, ROLLED_BACK, MIXED)
            for v in d.values()),
    }


def _prove_the_heart_is_the_same_heart() -> dict:
    """Continuity with upkeep's alarm, as numbers rather than as a claim."""
    schedule = heartbeat_schedule()
    beats = schedule["beats"]
    dire = upkeep.alarm_for(0, config.STAMINA_MAX)
    return {
        "alarm_at_zero_bpm": dire["bpm"],
        "death_first_beat_bpm": beats[0]["bpm"],
        "starts_where_the_alarm_ended": dire["bpm"] == beats[0]["bpm"],
        # Inside the band that actually sounds, whichever band that is today.
        "audible_tempos": sorted({upkeep.alarm_for(h, 20)["bpm"]
                                  for h in range(21)} - {0}),
        "alarm_speeds_up": (min(upkeep.alarm_for(h, 20)["bpm"] for h in range(21)
                                if upkeep.alarm_for(h, 20)["bpm"])
                            < upkeep.alarm_for(0, 20)["bpm"]),
        # The whole effect depends on the first death gap being slower than
        # ANYTHING the alarm can play, or the slowdown is a matter of memory
        # rather than a fact. scripts/verify/death.mjs asserts the same thing
        # from the JavaScript side.
        "slowest_alarm_gap_ms": int(round(60000.0 / min(
            b for b in (upkeep.alarm_for(h, 20)["bpm"] for h in range(21)) if b))),
        "first_death_gap_ms": beats[1]["at_ms"] - beats[0]["at_ms"],
        "the_miss_is_unambiguous": (beats[1]["at_ms"] - beats[0]["at_ms"]) > int(
            round(60000.0 / min(b for b in
                                (upkeep.alarm_for(h, 20)["bpm"] for h in range(21))
                                if b))),
        "death_slows_down": all(beats[i]["bpm"] > beats[i + 1]["bpm"]
                                for i in range(len(beats) - 1)),
        "three_beats": len(beats) == DEATH_BEATS == 3,
        "each_beat_quieter": all(beats[i]["gain"] > beats[i + 1]["gain"]
                                 for i in range(len(beats) - 1)),
        # upkeep asserts pulse_hz == bpm/60 for the alarm. The same must hold
        # here or the black-out and the thump drift apart.
        "one_clock": all(abs(b["hz"] - b["bpm"] / 60.0) <= 5e-3 for b in beats),
        "silence_is_the_beat_that_does_not_come":
            schedule["silence_ms"] == beats[-1]["interval_ms"],
        "black_lands_on_the_last_beat":
            schedule["black_at_ms"] == beats[-1]["at_ms"],
        "total_ms": schedule["total_ms"],
        "short_enough_on_the_tenth_death": schedule["total_ms"] <= 4000,
        "beats_at_ms": [b["at_ms"] for b in beats],
        "bpm": [b["bpm"] for b in beats],
    }


def _prove_waking_cannot_spiral() -> dict:
    """The wake floor, measured against upkeep's own alarm bands."""
    maximum = config.STAMINA_MAX
    floor = wake_health(maximum)
    at_floor = upkeep.alarm_for(floor, maximum)
    onset = int(maximum * upkeep.ALARM_ONSET)
    rows = []
    for saved in (0, 1, 4, 7, 10, 15, 20):
        state = _fresh_state(health=saved)
        woken = wake(_fresh_state(health=0), state)
        rows.append({"saved_at": saved, "woke_at": woken["health"],
                     "band": woken["alarm"]["band"],
                     "never_lower": woken["health"] >= saved})
    return {
        "stamina_max": maximum,
        "wake_floor": floor,
        "alarm_starts_at": onset,
        "wake_floor_is_above_the_alarm": floor > onset,
        "band_on_waking": at_floor["band"],
        "silent_on_waking": not at_floor["heartbeat"],
        "no_red_pulse_on_waking": not at_floor["pulse"],
        "dire_band_begins_at": int(upkeep.ALARM_BANDS[0].at * maximum),
        "failures_in_hand": at_floor["failures_left"],
        "failed_submit_costs": config.STAMINA_LOSS_FAILED_SUBMIT,
        "never_wakes_below_the_save": all(r["never_lower"] for r in rows),
        "rows": rows,
        "focus_on_waking": config.MANA_MAX,
        "focus_floor_needed_to_ask_twice": upkeep.VOIDED_FOCUS_FLOOR,
        "can_always_afford_a_question": config.MANA_MAX >= upkeep.VOIDED_FOCUS_FLOOR,
    }


def _prove_ticks_do_not_kill() -> dict:
    """F, as a table. Blows kill; ticks and measured runs do not."""
    rows = []
    for cause in sorted(CAUSES):
        state = _fresh_state(health=0)
        verdict = adjudicate(state, cause=cause)
        rows.append({
            "cause": cause,
            "declared_lethal": CAUSES[cause]["lethal"],
            "dead": verdict["dead"],
            "health_after": verdict["health"],
            "where": CAUSES[cause]["where"],
        })
    # An unknown cause must be treated as lethal, not as safe.
    unknown = adjudicate(_fresh_state(health=0), cause="something_new")
    # And a measured run overrides whatever cause was handed in.
    sealed_state = _fresh_state(health=0)
    sealed_state["interview"] = {"id": "iv-1", "results": []}
    in_the_exam = adjudicate(sealed_state, cause="enemy_turn")
    return {
        "rows": rows,
        "agree_with_the_table": all(r["declared_lethal"] == r["dead"]
                                    for r in rows),
        "ticks_floor_at": DOT_FLOOR,
        "ticks_leave_you_a_turn": all(
            r["health_after"] == DOT_FLOOR for r in rows
            if not r["declared_lethal"]),
        "unknown_cause_is_lethal": unknown["dead"],
        "measured_run_is_death_proof": not in_the_exam["dead"],
        "measured_run_health": in_the_exam["health"],
        "live_damage_sites": sorted({c["where"] for c in CAUSES.values()
                                     if c["where"].startswith("engine.")}),
    }


def _prove_the_battle_lock() -> dict:
    """D, as a table. One rule: something is taking a turn against you."""
    cases = [
        ("standing in a field", {}, True),
        ("an open encounter", {"encounter": {"problem_id": "p1"}}, False),
        ("a dungeon room", {"encounter": {"problem_id": "p1",
                                          "dungeon_room": 4}}, False),
        ("a sage gauntlet rung", {"encounter": {"problem_id": "p1",
                                                "reason": "SAGE"}}, False),
        ("a boss", {"boss_fight": {"boss_id": "the_interviewer"}}, False),
        ("an incantation", {"incantation": {"region": "fields"}}, False),
        ("an apex hunt", {"hunters": {"fight": {"region": "fields"}}}, False),
        ("a dungeon corridor", {"dungeon_run": {"dungeon": "barrow",
                                                "at": 3}}, True),
        ("a chase with no fight open", {"hunters": {"fight": None,
                                                    "regions": {}}}, True),
        ("a measured run", {"interview": {"id": "iv-1"},
                            "encounter": {"problem_id": "p1"}}, True),
    ]
    rows = []
    for label, overlay, expected in cases:
        state = _fresh_state()
        state.update(overlay)
        lock = battle_lock(state)
        rows.append({
            "case": label,
            "allowed": lock is None,
            "expected": expected,
            "agrees": (lock is None) == expected,
            "message": "" if lock is None else lock["message"],
        })
    return {
        "rows": rows,
        "all_agree": all(r["agrees"] for r in rows),
        "every_refusal_says_why": all(
            r["allowed"] or len(r["message"]) > 40 for r in rows),
        "rule": "You cannot save while something is taking a turn against you.",
    }


def _scratch_conn():
    """A throwaway save file for the proofs below.

    Not ':memory:' — db.connect takes a Path and makes its parent — and a real
    file is the better test anyway, because it exercises the same WAL-mode
    sqlite the game actually runs on. The caller closes it; the temp directory
    goes with the process.
    """
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="gauntlet-death-")) / "scratch.db"
    return saves.connect(tmp)


def _fresh_state(*, health: int | None = None) -> dict:
    """A real starting state: DEFAULT_STATE with the skill rows and the story
    block filled in, which is what `saves.normalize` does on every load."""
    state = saves.normalize({})
    if health is not None:
        state["player"][upkeep.HEALTH_FIELD] = int(health)
    return state


def _prove_a_real_death(*, over_a_manual_slot: bool) -> dict:
    """Kill somebody, on a real database, and count what moved.

    `over_a_manual_slot` is the case that matters most and is the one a naive
    implementation gets wrong: a manual slot carries a HISTORY snapshot, and
    `saves._restore_history` DELETEs `attempts`, `boss_records` and
    `interview_runs` before rewriting them from it. A death that loaded a manual
    slot the ordinary way would therefore roll the graded record back to the
    moment of the save — which is precisely the thing this module exists to
    prevent — and it would look like it worked.
    """
    from . import db
    conn = _scratch_conn()

    # The anchor: a quiet moment, in the first region, with nothing in the purse.
    anchored = _fresh_state(health=20)
    anchored["player"].update({"gold": 10, "xp": 100, "level": 2,
                               "region": "python_village", "x": 24, "y": 18,
                               "playtime_seconds": 600.0})
    anchored["inventory"] = ["rusted_dagger"]
    anchored["solved_ids"] = ["p1", "p2"]
    anchored["skills"]["HASH_MAP"]["mastery"] = 0.2
    anchored["stats"]["hints_total"] = 1
    anchored["settings"]["high_contrast"] = True
    saves.apply_state(conn, anchored)
    if over_a_manual_slot:
        written = saves.save_to_slot(conn, 1, anchored, name="before the marsh")
    else:
        written = saves.anchor(conn, anchored, "region_entered",
                               note="Entered Python Village")
    assert written is not None

    # Graded evidence recorded AFTER the save. This is what must not move.
    for n in range(6):
        db.record_attempt(conn, problem_id=f"p{n}", pattern="HASH_MAP",
                          family="hash_map", difficulty="MEDIUM",
                          mode="ADVENTURE", encounter_kind="BATTLE",
                          solved=int(n % 2 == 0), rank="B", hints_used=0,
                          seconds=30.0 + n)
    db.record_boss(conn, "the_interviewer", attempt_no=1, seconds=400.0,
                   hints_used=0, rank="A", defeated=1)
    db.record_interview(conn, format="SCREEN", profile="BACKEND", score=72.0,
                        problem_ids="p1,p2,p3,p4", solved=3, total=4,
                        seconds=2400.0, detail="{}")
    db.open_transfer(conn, problem_id="h1", lineage_id="two_sum",
                     pattern="HASH_MAP", skill="HASH_MAP", difficulty="MEDIUM",
                     mode="ADVENTURE", first_encounter=True)
    db.resolve_transfer(conn, "h1", solved=True, unaided=True, seconds=100.0,
                        rank="A")

    # Then a bad afternoon: gold, loot, xp, a level, a boss, a new region — and
    # mastery earned on the graded attempts above.
    dying = json.loads(json.dumps(anchored))
    dying["player"].update({"gold": 940, "xp": 2600, "level": 6,
                            "region": "fields_of_syntax", "x": 40, "y": 9,
                            "playtime_seconds": 3300.0,
                            upkeep.HEALTH_FIELD: 0, upkeep.FOCUS_FIELD: 2})
    dying["inventory"] = ["rusted_dagger", "marsh_ward", "iron_greaves",
                          "coil_of_rope"]
    dying["potions"] = {"lesser_draught": 2}
    dying["cleared_bosses"] = ["the_gatekeeper"]
    dying["solved_ids"] = ["p1", "p2", "p3", "p4", "p5"]
    dying["skills"]["HASH_MAP"]["mastery"] = 0.71
    dying["skills"]["HASH_MAP"]["clears"] = 5
    dying["schedule"] = {"HASH_MAP:p3": {"key": "HASH_MAP:p3", "due": 1.0,
                                         "interval": 2.0, "ease": 2.5,
                                         "reps": 1, "lapses": 0}}
    dying["recent_ids"] = ["p3", "p4", "p5"]
    dying["achievements"] = ["first_blood", "hash_slinger"]
    dying["perf_failed_ids"] = ["p9"]
    dying["stats"]["hints_total"] = 9
    dying["stats"]["encounters"] = 31
    dying["stats"]["interviews_passed"] = 1
    dying["settings"]["high_contrast"] = True
    dying["settings"]["vol_master"] = 0.2
    dying["encounter"] = {"problem_id": "p5"}
    dying["upkeep"]["statuses"] = [{"id": "POISON", "turns": 3}]
    upkeep.pet_knock(dying, "companion_fox", hits=upkeep.PET_KNOCKS_TO_FAINT)
    saves.apply_state(conn, dying)

    graded_before = {
        "attempts": len(db.recent_attempts(conn, limit=10 ** 6)),
        "boss_records": len(db.boss_history(conn)),
        "interview_runs": len(db.interview_history(conn, limit=10 ** 6)),
        "transfer_rows": len(db.transfer_ledger(conn)),
    }

    result = die(conn, dying, cause="enemy_turn", now=float(
        (written.get("summary") or {}).get("saved_at", time.time())) + 1500.0)
    woken = result["state"]
    graded_after = {
        "attempts": len(db.recent_attempts(conn, limit=10 ** 6)),
        "boss_records": len(db.boss_history(conn)),
        "interview_runs": len(db.interview_history(conn, limit=10 ** 6)),
        "transfer_rows": len(db.transfer_ledger(conn)),
    }
    on_disk = db.load_state(conn) or {}
    conn.close()

    return {
        "over_a_manual_slot": over_a_manual_slot,
        "woke_at": result["woke_at"]["region"],
        "woke_from_kind": result["woke_at"]["kind"],
        "graded_before": graded_before,
        "graded_after": graded_after,
        "graded_unchanged": graded_before == graded_after,
        # THE LOSSES
        "gold": {"had": 940, "now": woken["player"]["gold"],
                 "lost": result["lost"]["gold"]},
        "xp": {"had": 2600, "now": woken["player"]["xp"],
               "lost": result["lost"]["xp"]},
        "items": {"had": 4, "now": len(woken["inventory"]),
                  "lost": result["lost"]["items"]},
        "bosses_relocked": result["lost"]["bosses"],
        "elapsed": result["lost"]["elapsed_text"],
        "moved_back_to": woken["player"]["region"],
        # THE SURVIVALS
        "mastery": {"at_death": 0.71,
                    "on_waking": woken["skills"]["HASH_MAP"]["mastery"]},
        "mastery_survived": woken["skills"]["HASH_MAP"]["mastery"] == 0.71,
        "solved_survived": woken["solved_ids"] == ["p1", "p2", "p3", "p4", "p5"],
        "schedule_survived": bool(woken["schedule"]),
        "recent_survived": woken["recent_ids"] == ["p3", "p4", "p5"],
        "achievements_survived": woken["achievements"] == ["first_blood",
                                                           "hash_slinger"],
        "perf_failed_survived": woken["perf_failed_ids"] == ["p9"],
        "settings_survived": (woken["settings"]["high_contrast"] is True
                              and woken["settings"]["vol_master"] == 0.2),
        "playtime_survived": woken["player"]["playtime_seconds"] == 3300.0,
        "hints_survived": woken["stats"]["hints_total"] == 9,
        "game_counters_rewound": woken["stats"]["encounters"] == 0,
        # THE WAKING
        "health": woken["player"][upkeep.HEALTH_FIELD],
        "focus": woken["player"][upkeep.FOCUS_FIELD],
        "band": upkeep.alarm(woken)["band"],
        "statuses_cleared": not (woken.get("upkeep") or {}).get("statuses"),
        "companion_awake": not upkeep.fainted_pets(woken),
        "no_fight_open": not any(woken.get(k) for k in
                                 ("encounter", "boss_fight", "incantation")),
        "armour_left_alone": round(upkeep.armour_scale(woken), 3),
        "armour_above_the_floor":
            upkeep.armour_scale(woken) >= upkeep.DEGRADED_FLOOR,
        "undo_offers_the_death_back": result["undo_available"],
        "state_written_through": on_disk.get("player", {}).get("gold") == 10,
        "report_cost": result["report"]["cost"],
        "report_kept": result["report"]["kept"],
        "report_wake": result["report"]["wake"],
        # deathfx.js prints the kept half unconditionally, so it must always be
        # populated even on a death that cost nothing.
        "kept_half_is_never_empty": all(
            v != 0 and v != "" for v in result["report"]["kept"].values()),
    }


def _prove_dying_repeatedly_is_not_a_wall() -> dict:
    """Five deaths in a row. The last one must leave a playable game.

    This is the rule at the top of the brief — LEARNING NEVER DEAD-ENDS — asked
    as a question a machine can answer: after N deaths, can this player still
    fight, and can they still reach a healer.
    """
    from . import db
    conn = _scratch_conn()
    state = _fresh_state(health=20)
    state["player"].update({"gold": 60, "xp": 300, "level": 3,
                            "region": "fields_of_syntax"})
    saves.anchor(conn, state, "region_entered", note="Entered the fields")
    saves.apply_state(conn, state)

    rows = []
    for n in range(5):
        state["player"][upkeep.HEALTH_FIELD] = 0
        state["player"]["gold"] = 60 + 40 * n
        db.record_attempt(conn, problem_id=f"q{n}", pattern="TWO_POINTER",
                          family="two_pointer", difficulty="EASY",
                          mode="ADVENTURE", encounter_kind="BATTLE",
                          solved=0, rank="C", hints_used=0, seconds=20.0)
        result = die(conn, state, cause="enemy_turn")
        state = result["state"]
        alarm = upkeep.alarm(state)
        rows.append({
            "death": n + 1,
            "health": state["player"][upkeep.HEALTH_FIELD],
            "focus": state["player"][upkeep.FOCUS_FIELD],
            "band": alarm["band"],
            "failures_in_hand": alarm["failures_left"],
            "attempts_on_disk": len(db.recent_attempts(conn, limit=10 ** 6)),
            "armour": round(upkeep.armour_scale(state), 3),
            "can_reach_a_healer": upkeep.heal(
                json.loads(json.dumps(state)), sealed=False).get("ok", False),
            "woke_at": result["woke_at"]["region"],
        })
    conn.close()
    floor = wake_health(config.STAMINA_MAX)
    return {
        "rows": rows,
        "every_wake_is_fightable": all(r["health"] >= floor for r in rows),
        "never_wakes_in_the_alarm": all(r["band"] not in ("DIRE", "CRITICAL")
                                        for r in rows),
        "always_has_focus_to_ask": all(
            r["focus"] >= upkeep.VOIDED_FOCUS_FLOOR for r in rows),
        "healer_always_reachable": all(r["can_reach_a_healer"] for r in rows),
        "armour_never_below_the_floor": all(
            r["armour"] >= upkeep.DEGRADED_FLOOR for r in rows),
        "evidence_only_grew": [r["attempts_on_disk"] for r in rows] == [1, 2, 3,
                                                                       4, 5],
        "always_somewhere_to_wake": all(r["woke_at"] for r in rows),
    }


def _prove_there_is_always_somewhere_to_wake() -> dict:
    """A brand new game, killed before it has entered anything."""
    conn = _scratch_conn()
    state = _fresh_state(health=0)
    no_anchor = saves.wake_slot(conn) is None
    result = die(conn, state, cause="enemy_turn")
    after_first = saves.wake_slot(conn) is not None
    # And the boot-time guarantee, which is what should make the branch above
    # unreachable in a real game.
    conn2 = _scratch_conn()
    fresh = _fresh_state(health=20)
    written = ensure_wake_point(conn2, fresh)
    twice = ensure_wake_point(conn2, fresh)
    conn.close()
    conn2.close()
    return {
        "started_with_no_anchor": no_anchor,
        "died_anyway_without_raising": result["died"],
        "fell_where_they_stood": result["woke_at"]["fallback"],
        "health_on_waking": result["state"]["player"][upkeep.HEALTH_FIELD],
        "wrote_an_anchor_so_it_cannot_happen_twice": after_first,
        "ensure_wake_point_writes_one": written is not None,
        "ensure_wake_point_is_idempotent": twice is None,
    }


def _prove_the_anchor_ring_survives_grinding() -> dict:
    """The eviction arithmetic that THE ANCHOR RING exists to defeat.

    Enter a region, then clear encounters until the autosave ring has turned
    over twice. The waking point must still be the region.
    """
    conn = _scratch_conn()
    state = _fresh_state(health=20)
    state["player"]["region"] = "fields_of_syntax"
    saves.autosave(conn, state, "region_entered", note="Entered the fields")
    anchor_after_region = saves.wake_slot(conn)
    for n in range(saves.AUTOSAVE_RING * 2 + 1):
        state["player"]["gold"] = 100 + n
        saves.autosave(conn, state, "encounter_cleared")
    final = saves.wake_slot(conn)
    autos = [r for r in saves.list_slots(conn, kinds=(saves.KIND_AUTO,))
             if not r["empty"]]
    screen_rows = saves.list_slots(conn)
    conn.close()
    return {
        "autosaves_written": saves.AUTOSAVE_RING * 2 + 2,
        "autosave_ring_depth": len(autos),
        "region_entry_still_in_the_autosave_ring":
            any(r["reason"] == "region_entered" for r in autos),
        "waking_point_after_the_region": (anchor_after_region or {}).get("reason"),
        "waking_point_after_the_grind": (final or {}).get("reason"),
        "the_grind_did_not_move_it":
            (final or {}).get("slot_id") == (anchor_after_region or {}).get("slot_id"),
        "encounter_cleared_is_never_a_waking_point":
            "encounter_cleared" not in saves.ANCHOR_EVENTS,
        "save_screen_is_still_sixteen_rows": len(screen_rows),
    }


def _prove_the_report_never_breaks() -> dict:
    """web/js/deathfx.js is handed this dict and must always produce a screen.

    Its own suite feeds deathLines() null, {}, garbage and a no-save report. This
    is the Python half: whatever `die` failed to compute, `report` still returns
    the three groups with the right types, the kept half is still populated, and
    a player with no waking point gets an empty region — which is deathfx's
    NO_SAVE_LINE case, "you can keep going", rather than a blank screen.
    """
    rows = []
    for label, payload in (
            ("nothing at all", {}),
            ("no wake group", {"lost": {"gold": 5}, "kept": {"attempts": 3}}),
            ("a fallback death", {"woke_at": {"fallback": True,
                                              "region": "Python Village"},
                                  "lost": {}, "kept": {"attempts": 3,
                                                       "skills": 2,
                                                       "mastery_percent": 40,
                                                       "scheduled": 1}}),
            ("junk", {"lost": None, "kept": None, "woke_at": None}),
            # Junk VALUES, not merely junk keys. int("many") raises, and a
            # death screen that raises is a player who cannot get up.
            ("junk values", {"lost": {"gold": "many", "items": None,
                                      "levels": [], "elapsed_text": 12},
                             "kept": {"attempts": "lots", "skills": {},
                                      "mastery_percent": "high",
                                      "scheduled": None},
                             "woke_at": {"region": None, "slot_id": 7}}),
    ):
        out = report(payload)
        rows.append({
            "case": label,
            "groups": sorted(out),
            "shape_holds": (sorted(out) == ["cost", "kept", "wake"]
                            and all(isinstance(v, dict) for v in out.values())),
            "cost_types": all(isinstance(out["cost"][k], int)
                              for k in ("gold", "items", "levels")),
            "no_save_shows_no_region": out["wake"]["region"] == "",
            "kept": out["kept"],
        })
    full = report({"woke_at": {"region": "Python Village", "slot_id": "anchor:0",
                               "last_event": "Entered Python Village",
                               "reason": "region_entered"},
                   "lost": {"gold": 930, "items": 3, "levels": 4,
                            "elapsed_text": "25m 00s"},
                   "kept": {"attempts": 6, "skills": 1, "mastery_percent": 71,
                            "scheduled": 1}})
    text = json.dumps(full)
    return {
        "rows": rows,
        "every_shape_holds": all(r["shape_holds"] and r["cost_types"]
                                 for r in rows),
        "a_fallback_death_reads_as_no_save": rows[2]["no_save_shows_no_region"],
        "a_full_report": full,
        "no_exclamation_marks": "!" not in text,
        # deathfx prints the kept half unconditionally. Every key must exist.
        "kept_keys": sorted(full["kept"]),
        "kept_is_complete": sorted(full["kept"]) == ["attempts", "due",
                                                     "mastery", "skills"],
        "cost_keys": sorted(full["cost"]),
        "wake_keys": sorted(full["wake"]),
    }


def self_check() -> dict:
    """Every number this module asserts, computed rather than claimed."""
    ledger_total = _prove_ledger_is_total()
    heart = _prove_the_heart_is_the_same_heart()
    spiral = _prove_waking_cannot_spiral()
    lethality = _prove_ticks_do_not_kill()
    lock = _prove_the_battle_lock()
    anchor_ring = _prove_the_anchor_ring_survives_grinding()
    over_anchor = _prove_a_real_death(over_a_manual_slot=False)
    over_manual = _prove_a_real_death(over_a_manual_slot=True)
    repeated = _prove_dying_repeatedly_is_not_a_wall()
    always = _prove_there_is_always_somewhere_to_wake()
    wire = _prove_the_report_never_breaks()

    failures = []
    if not ledger_total["total"]:
        failures.append("state keys nobody classified: %s"
                        % ", ".join(ledger_total["unclassified"]))
    if not ledger_total["no_key_on_both_sides"]:
        failures.append("a key is on both sides of the ledger: %s"
                        % ", ".join(ledger_total["both_sides"]))
    if not ledger_total["every_entry_states_a_reason"]:
        failures.append("a ledger entry gives no reason")
    if ledger_total["named_but_not_in_state"]:
        failures.append("the ledger classifies keys the state does not have: %s"
                        % ", ".join(ledger_total["named_but_not_in_state"]))

    for key in ("starts_where_the_alarm_ended", "death_slows_down",
                "the_miss_is_unambiguous", "alarm_speeds_up",
                "three_beats", "each_beat_quieter", "one_clock",
                "silence_is_the_beat_that_does_not_come",
                "black_lands_on_the_last_beat",
                "short_enough_on_the_tenth_death"):
        if not heart[key]:
            failures.append("the death heartbeat is not the alarm's heart: %s" % key)

    for key in ("wake_floor_is_above_the_alarm", "silent_on_waking",
                "no_red_pulse_on_waking", "never_wakes_below_the_save",
                "can_always_afford_a_question"):
        if not spiral[key]:
            failures.append("waking can spiral: %s" % key)

    for key in ("agree_with_the_table", "ticks_leave_you_a_turn",
                "unknown_cause_is_lethal", "measured_run_is_death_proof"):
        if not lethality[key]:
            failures.append("what kills you is wrong: %s" % key)

    if not lock["all_agree"]:
        failures.append("the battle lock disagrees with its own table: %s"
                        % ", ".join(r["case"] for r in lock["rows"]
                                    if not r["agrees"]))
    if not lock["every_refusal_says_why"]:
        failures.append("a save refusal does not say why")

    for key in ("the_grind_did_not_move_it",
                "encounter_cleared_is_never_a_waking_point"):
        if not anchor_ring[key]:
            failures.append("the anchor ring does not hold: %s" % key)
    if anchor_ring["save_screen_is_still_sixteen_rows"] != 16:
        failures.append("the anchor ring leaked into the save screen (%d rows)"
                        % anchor_ring["save_screen_is_still_sixteen_rows"])

    for run in (over_anchor, over_manual):
        label = "manual slot" if run["over_a_manual_slot"] else "anchor"
        if not run["graded_unchanged"]:
            failures.append(
                "dying over a %s moved the graded record: %s -> %s"
                % (label, run["graded_before"], run["graded_after"]))
        for key in ("mastery_survived", "solved_survived", "schedule_survived",
                    "recent_survived", "achievements_survived",
                    "perf_failed_survived", "settings_survived",
                    "playtime_survived", "hints_survived"):
            if not run[key]:
                failures.append("dying over a %s took something it may not: %s"
                                % (label, key))
        if not run["game_counters_rewound"]:
            failures.append("dying over a %s did not rewind the game" % label)
        if run["gold"]["lost"] <= 0 or run["items"]["lost"] <= 0:
            failures.append("dying over a %s cost nothing" % label)
        for key in ("statuses_cleared", "companion_awake", "no_fight_open",
                    "armour_above_the_floor", "state_written_through"):
            if not run[key]:
                failures.append("waking after a %s is broken: %s" % (label, key))
        if run["undo_offers_the_death_back"]:
            failures.append("a death over a %s can be undone" % label)
        # deathfx.js prints the kept half unconditionally. It printing zeroes
        # on a death that really did keep something would be the screen
        # contradicting the sentence above it.
        if not run["kept_half_is_never_empty"]:
            failures.append("the kept half of a %s death screen came out empty"
                            % label)

    for key in ("every_wake_is_fightable", "never_wakes_in_the_alarm",
                "always_has_focus_to_ask", "healer_always_reachable",
                "armour_never_below_the_floor", "evidence_only_grew",
                "always_somewhere_to_wake"):
        if not repeated[key]:
            failures.append("five deaths in a row found a wall: %s" % key)

    for key in ("died_anyway_without_raising", "fell_where_they_stood",
                "wrote_an_anchor_so_it_cannot_happen_twice",
                "ensure_wake_point_writes_one",
                "ensure_wake_point_is_idempotent"):
        if not always[key]:
            failures.append("there is not always somewhere to wake: %s" % key)

    for key in ("every_shape_holds", "a_fallback_death_reads_as_no_save",
                "no_exclamation_marks", "kept_is_complete"):
        if not wire[key]:
            failures.append("the death report deathfx.js reads is wrong: %s" % key)

    return {
        "module": "death",
        "ok": not failures,
        "failures": failures,
        "headline": {
            "the_line": "Death rewinds the game. It never rewinds the player.",
            "state_keys_classified": ledger_total["keys"],
            "keys_that_survive": ledger_total["survives"],
            "keys_that_rewind": ledger_total["rewinds"],
            "keys_split_field_by_field": ledger_total["mixed"],
            "graded_tables_touched_by_dying": 0,
            "heartbeat_bpm": heart["bpm"],
            "heartbeat_at_ms": heart["beats_at_ms"],
            "black_at_ms": heartbeat_schedule()["black_at_ms"],
            "death_screen_at_ms": heartbeat_schedule()["screen_at_ms"],
            "wake_health": spiral["wake_floor"],
            "of_a_maximum_of": spiral["stamina_max"],
            "alarm_starts_at": spiral["alarm_starts_at"],
            "failures_in_hand_on_waking": spiral["failures_in_hand"],
            "worst_case_gold_lost": over_anchor["gold"]["lost"],
            "worst_case_xp_lost": over_anchor["xp"]["lost"],
            "worst_case_items_lost": over_anchor["items"]["lost"],
            "mastery_lost": 0.0,
            "attempts_lost": 0,
            "waking_points": sorted(saves.ANCHOR_EVENTS),
            "not_a_waking_point": sorted(saves.NOT_AN_ANCHOR),
            "cannot_save_during": [r["case"] for r in lock["rows"]
                                   if not r["allowed"]],
        },
        "ledger": ledger(),
        "ledger_is_total": ledger_total,
        "the_same_heart": heart,
        "no_spiral": spiral,
        "what_kills_you": lethality,
        "battle_lock": lock,
        "anchor_ring": anchor_ring,
        "a_real_death_over_an_anchor": over_anchor,
        "a_real_death_over_a_manual_slot": over_manual,
        "five_deaths_in_a_row": repeated,
        "always_somewhere_to_wake": always,
        "the_report_deathfx_reads": wire,
    }


# ==========================================================================
# THE WIRING CONTRACT — what the other passes have to do, and nothing more
# ==========================================================================
#
# This module is complete and self-checking, and it is NOT wired in. engine.py,
# server.py and web/js/main.js belong to other passes, so what follows is the
# whole of what they have to add. Five call sites and one response field. If a
# pass finds itself needing a sixth, something here is wrong and it should be
# fixed here rather than worked around there.
#
# TODAY, ZERO HEALTH IS NOT A DEATH. Both engines catch it and heal you back to
# a third of your maximum:
#
#   engine._apply_outcome      `stamina_zero`, engine.py:5178
#                              -> player["stamina"] = max(4, stamina_max // 3)
#   engine.incantation_cast    `routed`, engine.py:8343, via the rout at 8615
#                              -> the same line
#
# Those two lines ARE the feature that is being replaced. Leaving them in place
# alongside a call to `check` would produce a game that heals you and then kills
# you, in that order.
#
# 1. AT BOOT, once, after the state has loaded:
#
#        death.ensure_wake_point(self.conn, self.state)
#
#    Idempotent, returns None when there was already a waking point. Without it
#    a player who dies in their first fight has no anchor and takes the fallback
#    path on every new game — and a fallback that runs every time is not a
#    fallback, it is the design.
#
# 2. AT THE TWO ZERO-HEALTH CHECKS, in place of the heal-back lines above:
#
#        out = death.check(self.conn, self.state, cause="enemy_turn",
#                          encounter=self.encounter)
#        if out["died"]:
#            self.state = out["state"]      # MANDATORY. see below.
#            ... return out to the client ...
#
#    `cause` is "enemy_turn" in _apply_outcome and "incant_enemy_turn" in
#    incantation_cast. Pass "status_tick" from the two tick sites if they are
#    ever made to ask; they floor at DOT_FLOOR and never kill, which is section
#    F and is the reason a poisoned player always gets a turn to drink something.
#
#    ADOPTING THE RETURNED STATE IS NOT OPTIONAL. `die` has already written the
#    rolled-back state to the database through saves.apply_state. A caller that
#    keeps its old in-memory dict will write the DEAD state back over it on its
#    next save, which un-does the death and hands the player their gold back.
#    This is the same rule that already applies after saves.load_slot.
#
# 3. WHEREVER AN AUTOSAVE ALREADY FIRES, to tell the player it landed:
#
#        note = death.announce(saves.autosave(conn, state, reason))
#
#    None unless the reason was an anchor event, so it is safe to call on every
#    autosave. `region_entered` and `boss_defeated` are the brief's two.
#
# 4. IN THE HUD PAYLOAD, permanently:
#
#        "waking_point": death.waking_point(self.conn)
#
#    Read-only and cheap. A toast that has faded tells a player nothing when
#    they look up mid-fight and want to know what a bad submission is worth,
#    and the threat is only FAIR if that number is on screen.
#
# 5. IN THE SAVE ROUTE, nothing at all. saves.save_to_slot already calls
#    battle_lock and raises SaveError with a player-facing message; the route
#    only has to show `str(exc)` rather than inventing a second refusal.
#
# WHAT THE CLIENT GETS. `check` returns `result["report"]` in the wire shape
# web/js/deathfx.js reads, and `result["heartbeat"]` in the shape
# web/js/audio.js schedules against. main.js needs:
#
#        const fx = createDeath({ report, seen, look, reduced,
#                                 alarmColour: alarm.colour });
#        audio.heartbeatStop();          // the three beats, on the audio clock
#        fx.begin({});                   // then update/draw it like any effect
#
#    and one rule: keep listening to the keyboard the whole time. deathfx
#    installs no listener and owns no timer, `skip()` is ungated and works from
#    any frame, and `canSkip` says whether a press should take it. A host that
#    reads `blocking` and stops reading input has written the trap this whole
#    section exists to prevent.


if __name__ == "__main__":       # pragma: no cover
    print(json.dumps(self_check(), indent=1))
