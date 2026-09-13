"""Upkeep: the healer, durability, the focus refill, the low-health alarm, and
the honest shape of the town loop.

WHAT THIS MODULE IS FOR
-----------------------
Everything in here is the layer AROUND the fight. None of it is the fight. The
fight is `incantation.py`: the enemy is a variable, the attack is a line of
Python, and the only thing that makes a monster's health go down is a line that
runs. Nothing in this file deals damage, and nothing in this file can be spent,
drunk, repaired or prayed to in order to win an encounter the player could not
type their way out of. If any number here could end a fight on its own, the
feature would have failed, and the self-check at the bottom asserts that it
cannot.

What it DOES do is decide what it costs to keep showing up, and the whole design
brief for that is three words from the player: "dont make it annoying".

THE ONE NUMBER, AND WHY THERE IS ONLY ONE
-----------------------------------------
Durability is not a new quantity. `engine.DEFAULT_STATE` already carries

    state["armor"] = {"helmet": 100, "chestplate": 100, "gauntlets": 100,
                      "boots": 100, "shield": 100, "legendary": 0}

as integers 0..100, and `items.armor_tier(piece, integrity)` already turns that
number into what the hero SPRITE looks like — a split helm at 0, a mirrorbright
one at 100, with visible steps at 25, 50 and 75. A second durability number
living beside it would have meant a player whose armour reads "Sound Helm" on the
map and "nearly broken" at the smith. So this module writes to that same key and
nothing else. Integrity IS durability, the sprite IS the durability bar, and the
player never has to be told which number to read.

Engine already moves that number in two places this module deliberately leaves
alone: a solved DEBUG_BATTLE repairs a piece for free, and a failed submission
cracks one by 12. Both are typing-linked — fix the bug, mend the armour — and
they are the best argument in the game that the gear is a readout of competence.
This module adds the other half: wear from the fight itself.

Pure stdlib, like everything else here.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from . import config, elements, items, world

# `pets` is imported LAZILY and defensively, for one constant.
#
# This module needs exactly one number out of pets.py — FREE_SOLUTION_AFTER, the
# attempt count at which the worked solution is guaranteed — and that number is
# the floor the fainted-companion rule is not allowed to sink below. Importing
# the whole module at load time would mean the town, the healer and the entire
# repair economy fail to import while a sibling pass is mid-edit on the pet
# catalogue. The town is the place a stuck player goes; it is the last thing that
# should be able to break.
#
# So: ask pets at call time, fall back to the mirrored value, and say out loud
# that the mirror is a mirror. `self_check` asserts they agree whenever pets is
# importable, which is how a drift gets caught instead of silently widening.
FREE_SOLUTION_AFTER_FALLBACK = 3


def _free_solution_after() -> int:
    """`pets.FREE_SOLUTION_AFTER`, or the mirror if pets will not load."""
    try:
        from . import pets as _pets
        return int(getattr(_pets, "FREE_SOLUTION_AFTER",
                           FREE_SOLUTION_AFTER_FALLBACK))
    except Exception:
        return FREE_SOLUTION_AFTER_FALLBACK

# --------------------------------------------------------------------------
# Capability. There is exactly one way to ask whether a mode allows something,
# and it is `finalexam.sealed(encounter, capability)`. This module does not
# import finalexam — it takes the ANSWER as a keyword, which is the same
# arrangement `elements.Defender.for_player(..., build_sealed=...)` uses. The
# check stays at the call site, where the encounter actually is.
#
# The capability is "BUILD", the loadout capability that `forge.FORGE_CAPABILITY`
# also uses, because durability, repair and the healer are all loadout. In a
# measured run the loadout is not read at all, so there is nothing to wear out
# and nothing to mend. A sealed run costs no gold and inflicts no damage on the
# kit: an exam that quietly billed you afterwards would be an exam that punished
# you for sitting it.
# --------------------------------------------------------------------------
UPKEEP_CAPABILITY = "BUILD"

UPKEEP_STATE_KEY = "upkeep"
ARMOUR_STATE_KEY = "armor"          # engine's existing key, spelled its way


# ==========================================================================
# A. THE HEALER
# ==========================================================================
#
# SHE IS FREE, AND THAT IS THE MOST LOAD-BEARING DECISION IN THIS FILE.
#
# The one failure this game may never have is a player who cannot afford to keep
# learning. Every other system here is allowed to squeeze: the smith charges, the
# forge charges, the Armorer charges to unpick your attributes. Health does not,
# because health is the gate on ATTEMPTS, and attempts are the entire mechanism
# by which anybody gets better at this. Charge gold for healing and you have
# built a game in which the players who are struggling most — who fail more
# submissions, who lose more stamina, who earn less gold because they clear
# fewer encounters — are exactly the players who can least afford another go.
# That is a difficulty curve that steepens precisely where it should flatten. It
# is not a balance problem. It is the opposite of the product.
#
# So: health is free, affliction removal is free, and reviving a fainted pet is
# free. The cost of dying badly is the WALK — the time, and the interruption, and
# having to leave the dungeon floor you were on. Time is a real cost. It is just
# not one that compounds against the people who have least of it.
#
# The smith is where gold goes. Keeping those two on opposite sides of the square
# is what gives the town two poles instead of one till.

@dataclass(frozen=True)
class Healer:
    """The town healer, as data. The client draws her; this is what she says."""
    id: str
    name: str
    title: str
    blurb: str
    free_because: str
    lines: dict          # situation -> tuple of things she might say


MENDER = Healer(
    id="margit_orr",
    name="Margit Orr",
    title="the Mender",
    blurb=(
        "Ran a debugging bench for eleven years before the Null Kings took the "
        "castle, which is why she treats a poisoned adventurer and a corrupted "
        "stack trace with the same expression. Charges nothing. Has been asked "
        "about it enough times that she now answers before you ask."),
    free_because=(
        "A player who cannot afford to be healed is a player who cannot afford "
        "to keep learning, and that is the one failure this game may never "
        "have."),
    lines={
        # What she says when you walk in. Dry, unbothered, faintly put upon.
        "greet": (
            "Sit down. You are not dying on my floor.",
            "You again. Good — the ones who stop coming are the ones I read "
            "about later.",
            "Hands where I can see the burns.",
            "Before you ask: no. It is free. It has always been free.",
        ),
        # Health restored.
        "healed": (
            "There. Back to full. Try to make it last past the gate this time.",
            "Done. You were three points from a very stupid death.",
            "Mended. That will be nothing, same as last time.",
        ),
        # Afflictions cleared.
        "cleansed": (
            "Whatever that was, it is out of you now.",
            "Held still, for once. That helps.",
            "Poison is patient. So am I. I won.",
        ),
        # Nothing was actually wrong.
        "unneeded": (
            "You are fine. Go away.",
            "Nothing wrong with you that a harder problem would not fix.",
            "This is not a waiting room. You are at full.",
        ),
        # A fainted companion woken up.
        "revived": (
            "It will be groggy for an hour and insufferable for a day. "
            "It is fine.",
            "It took the blow that was meant for you. Consider that.",
            "Awake. It has been asking where you were, in its way.",
        ),
        # Said when the player arrives badly hurt AND broke. The point of the
        # line is to state the policy out loud, in her voice, at the exact
        # moment a player would otherwise brace for a bill.
        "broke": (
            "You have no gold and half a lung. One of those is my problem.",
            "I do not take gold. The smith does, and the smith can wait.",
            "Keep it. You will want it for your armour, and armour is not me.",
        ),
        # Said when the player's kit is falling apart. She will not fix it —
        # that is the smith — but she will point.
        "kit": (
            "Your plate is a suggestion at this point. Ferro is across the "
            "square and awake.",
            "I mend people. Steel is someone else's calling.",
            "I can keep you upright. I cannot keep you armoured.",
        ),
    },
)

# Kept as a mapping so a later pass can add a second healer in a second town
# without every call site learning a new name.
HEALERS: dict = {MENDER.id: MENDER}
DEFAULT_HEALER = MENDER.id


def healer_line(kind: str, *, healer_id: str = DEFAULT_HEALER,
                rng: random.Random | None = None) -> str:
    """One thing she says, for the dialogue box. Unknown kinds stay quiet rather
    than raising: a missing line is a silent NPC, not a crash."""
    who = HEALERS.get(healer_id, MENDER)
    pool = who.lines.get(kind, ())
    if not pool:
        return ""
    return (rng or random).choice(list(pool))


# ==========================================================================
# B. DURABILITY — the rates, and the arithmetic that defends them
# ==========================================================================
#
# The pieces that wear. `world.ARMOR` lists six; only five of them are gear you
# are wearing into a fight.
#
# THE LEGENDARY PLATE IS EXCLUDED ON PURPOSE. `items.hero_look` reads a
# legendary integrity of 0 as "not built yet — still on the Armorer's wall" and
# refuses to paint it. If this module wore it down, a player would watch the
# armour they spent the whole game assembling evaporate off their own sprite and
# reappear as if unearned. That is the single most unforgivable thing durability
# could do, so it simply never touches it. The forge exists now; what comes out
# of it does not rot.

PIECES: tuple = ("helmet", "chestplate", "gauntlets", "boots", "shield")
EXCLUDED_PIECES: tuple = ("legendary",)

# Which equipment slot supplies each piece's quality. `items.SLOTS` names these.
PIECE_SLOT: dict = {
    "helmet": "head",
    "chestplate": "chest",
    "gauntlets": "hands",
    "boots": "feet",
    "shield": "offhand",
}

# Where an incoming blow lands. Not a roll — see `wear_encounter`. A chestplate
# covers most of a person, so it takes most of the wear and is therefore the
# piece that decides how often the player walks to the smith.
HIT_WEIGHTS: dict = {
    "chestplate": 0.40,
    "helmet": 0.15,
    "gauntlets": 0.15,
    "boots": 0.15,
    "shield": 0.15,
}

INTEGRITY_MAX = 100
INTEGRITY_MIN = 0

# --- the two rates --------------------------------------------------------
#
# WEAR_TAKEN: points of integrity spent per incoming hit that actually landed.
# A hit fully absorbed by armour points still counts — absorbing IS the wear, and
# a shield that never scuffs is a shield that is not doing anything.
WEAR_TAKEN = 2.0

# WEAR_DEALT: the brief says armour and shields wear from HITTING as well. The
# hard part is that hitting is frequent — one graded submission is one turn, and
# a MEDIUM problem takes several — so charging a full point per blow put the
# shield at the smith every eight encounters, which is the definition of
# annoying. So outgoing wear is a third of a point, expressed as one point per
# three landed blows, and it all goes on the guard piece: the shield you are
# bracing behind, or your gauntlets if your off hand is empty.
WEAR_DEALT = 1.0
DEALT_WEAR_EVERY = 3.0

# --- the two things that stop wear becoming a tax -------------------------
#
# Both of these exist because of one measurement. The table under
# `_budget_table` is computed at three hits taken and four blows landed, at
# rank B, and at those numbers upkeep runs at eight to twenty per cent of
# income — comfortably inside the brief's third. But that is the competent
# player. Take the measurement again for somebody having a bad afternoon and
# the same rates read like this:
#
#   MEDIUM, rank B, 3 hits    13.7%     the tuned case
#   MEDIUM, rank B, 8 hits    35.6%     over
#   MEDIUM, LEARNING_CLEAR, 3 hits      34.4%     over
#   EASY,   LEARNING_CLEAR, 8 hits     128.2%     absurd
#
# Wear is driven by how badly the fight went and income is driven by how well
# it went, so the two diverge exactly where they must not: the worse the player
# is doing, the larger the share of their money the smith takes. That is the
# tax the brief forbids, aimed at the one person who can least afford it.
#
# HITS_FULL_RATE / HITS_TAIL_RATE: wear from incoming hits SATURATES. The first
# four hits of a fight wear at full rate; every hit after that wears at half.
# The fiction and the arithmetic agree — a fight where you are hit twelve times
# is a fight you nearly lost, and billing that linearly bills the worst day the
# most. Deterministic, so the player can still count encounters.
HITS_FULL_RATE = 4
HITS_TAIL_RATE = 0.5

# INCOME_CLAMP: the guarantee, rather than the tuning. One encounter's wear may
# never cost more to mend than `UPKEEP_INCOME_CEILING` of what that encounter
# actually paid. Quality cancels — wear divides by toughness and price
# multiplies by it — so clamping nominal POINTS clamps the gold exactly, whatever
# the player is wearing.
#
# Pass `gold_earned` and the ceiling is enforced against the real purse. Leave it
# out and it is enforced against `expected_gold(difficulty)`, the band's base
# pay, which is the stingiest published figure and therefore a real clamp rather
# than a decorative one. A caller who earned NOTHING — a failed submission — wears
# nothing, and that is not an oversight: a third of zero is zero, and the player
# who just failed is the last person in the game who should be billed.
INCOME_CLAMP = True


def _effective_hits(hits_taken: int) -> float:
    """Incoming hits, after saturation. See HITS_FULL_RATE."""
    count = max(0, int(hits_taken))
    if count <= HITS_FULL_RATE:
        return float(count)
    return HITS_FULL_RATE + (count - HITS_FULL_RATE) * HITS_TAIL_RATE


def wear_ceiling_points(gold_earned: float) -> float:
    """The most wear one encounter may produce, in nominal points, given what it
    paid. This is the brief's sentence — "not more than a third of what the
    player earned meanwhile" — expressed as the only unit wear is measured in."""
    gold = max(0.0, float(gold_earned))
    return gold * UPKEEP_INCOME_CEILING / REPAIR_GOLD_PER_POINT

# Harder content wears kit faster. It also PAYS more, and the whole point of the
# table below is that it pays more, faster, than it wears. Read these against
# `grading.xp_for` base values and engine's `gold = xp // 3`:
#
#   difficulty   gold @ rank B    wear multiplier    ratio wear:income vs MEDIUM
#   TUTORIAL              4              0.0         zero. a tutorial never bills
#   EASY                  8              0.6         1.50x worse
#   MEDIUM               20              1.0         1.00x
#   HARD                 36              1.4         0.78x better
#   ELITE                46              1.6         0.70x better
#   BOSS                 66              2.0         0.61x better
#
# Every step up the ladder is a step toward upkeep mattering LESS, which is what
# progression should feel like. EASY is the worst ratio in the game and it is
# still comfortably inside budget — the numbers are in `self_check`.
WEAR_BY_DIFFICULTY: dict = {
    "TUTORIAL": 0.0,
    "EASY": 0.6,
    "MEDIUM": 1.0,
    "HARD": 1.4,
    "ELITE": 1.6,
    "BOSS": 2.0,
}
DEFAULT_DIFFICULTY = "MEDIUM"

# --- quality, and why it cancels out -------------------------------------
#
# Better gear is tougher AND dearer to mend, by the same factor, and that is not
# a coincidence — it is the mechanism that makes the whole system fair.
#
#   toughness = 1 + (rarity_mult - 1) * QUALITY_DAMPING
#
# A Mythic chestplate takes 1/2.4 of the wear a Common one takes, and costs 2.4x
# as much per point. The two cancel exactly, so GOLD SPENT ON REPAIR PER
# ENCOUNTER IS THE SAME WHATEVER YOU ARE WEARING. Rarity changes how OFTEN you
# visit the smith, never what fraction of your income the visit eats.
#
# This matters because the alternative — cost scaling with rarity alone — meant a
# lucky Legendary drop at level nine turned into a bill the player could not pay,
# and the game would have punished them for good luck. Damping at 0.4 keeps the
# spread readable (1.0 for Common to 2.4 for Mythic) rather than the raw 1.0-4.5,
# which would have made a Mythic piece feel like it was made of paper between
# visits.
QUALITY_DAMPING = 0.4


def toughness_of(rarity: str) -> float:
    """How many points of wear one nominal point of punishment becomes. Also the
    multiplier on the price per point. Same number, used twice, on purpose."""
    mult = float(items.RARITIES.get(rarity, items.RARITIES["COMMON"])["mult"])
    return 1.0 + (mult - 1.0) * QUALITY_DAMPING


def piece_rarity(state: dict, piece: str) -> str:
    """The rarity of whatever is in the slot this piece represents.

    An empty slot reads as COMMON: there is nothing there to be tough, and a
    bare head still counts as a helmet for the sprite's purposes. Never raises —
    a save that references an item this build dropped falls back rather than
    taking the town down with it.
    """
    slot = PIECE_SLOT.get(piece)
    if not slot:
        return "COMMON"
    item_id = ((state or {}).get("equipped") or {}).get(slot) or ""
    item = items.BY_ID.get(item_id)
    rarity = getattr(item, "rarity", "COMMON")
    return rarity if rarity in items.RARITIES else "COMMON"


def piece_toughness(state: dict, piece: str) -> float:
    return toughness_of(piece_rarity(state, piece))


# --- what a worn piece is actually worth ---------------------------------
#
# Durability has to MEAN something or it is a tax with a progress bar. It scales
# what the piece contributes to `elements.ArmourProfile` — flat points and
# elemental resistance both.
#
#   integrity >= HEALTHY_AT   ->  100% effective
#   integrity  = 0            ->  DEGRADED_FLOOR effective, and never less
#   between                   ->  linear
#
# HEALTHY_AT is 60 rather than 100 because of the brief's warning. There has to
# be a band where ordinary play costs you NOTHING — where the numbers are moving
# and you are not being penalised for it — or every fight after the first is
# fought at a deficit and the player is being nagged. Sixty points of headroom is
# roughly seventeen encounters of not caring, which is a session.
HEALTHY_AT = 60.0

# ==========================================================================
# C. NOTHING BREAKS PERMANENTLY
# ==========================================================================
#
# A piece at zero is DEGRADED, not destroyed. It is still equipped, still drawn
# on the sprite (as a split helm and a staved plate, which is the point), still
# supplying half its armour, and one visit to the smith away from whole.
#
# Losing a forged piece to an unlucky afternoon would be unforgivable. The forge
# ladder is hundreds of encounters long; `forge.GOLD_SHAPE` alone runs to 1500
# gold at the top rung. Nothing in this file deletes an item, empties a slot, or
# writes below INTEGRITY_MIN. There is no breakage code here to audit, because
# there is no breakage.
#
# The floor is 50% and not lower for a second reason: `elements.py` proves its
# no-dead-end guarantee against WORST_CASE_MULTIPLIER = 0.25, which is what
# happens with FULL armour points against the worst matchup. Halving armour
# points moves the player TOWARD the unarmoured case, which elements has already
# proved is survivable and which only ever makes the fight longer. A longer fight
# is more typing. That is the trade this entire game is built to make.
DEGRADED_FLOOR = 0.50

# Below this a piece is worth mentioning in the UI. It is also the visible step
# in `items.ARMOR_TIERS` where a helm stops being "Sound" and starts being
# "Patched", so the player is told by the sprite before they are told by a menu.
REPAIR_ADVISED_AT = 60


def effectiveness(integrity: float) -> float:
    """How much of a piece is still working, 0.5 to 1.0."""
    value = max(float(INTEGRITY_MIN), min(float(INTEGRITY_MAX), float(integrity)))
    if value >= HEALTHY_AT:
        return 1.0
    return DEGRADED_FLOOR + (1.0 - DEGRADED_FLOOR) * (value / HEALTHY_AT)


# --- price -----------------------------------------------------------------
#
# Gold per point of integrity, before the quality factor. Derived, not guessed:
#
#   an ordinary MEDIUM encounter costs 7.33 points of wear across the kit
#   7.33 points x 0.45 gold  =  3.30 gold of upkeep per encounter
#   a MEDIUM encounter at rank B pays 20 gold
#   3.30 / 20  =  16.5% of income
#
# The brief's ceiling is a third. Sixteen and a half percent leaves room for the
# player to be worse than rank B, to fight below their level, and to still be
# saving for something. Worked for every difficulty in `self_check`.
REPAIR_GOLD_PER_POINT = 0.45

# The smith's mercy, and it is aimed at one specific person.
#
# Engine cracks a piece by 12 on every FAILED submission. A player who is
# struggling therefore arrives with armour at single digits AND the smallest
# purse in the game, because failed submissions pay nothing. Charging that
# player full freight for a piece at zero is the same mistake as charging for
# healing, one room over.
#
# So the first 25 points of any repair are free. A piece at 0 is priced as if it
# were at 25. Rich players never notice the clause exists; it only ever fires for
# someone having a bad day, which is exactly who it is for.
MERCY_THRESHOLD = 25

SMITH_NAME = "Ferro"
SMITH_LINES: dict = {
    "quote": (
        "I can see daylight through that. Hold still.",
        "Steel does not mind being hit. It minds being ignored.",
    ),
    "mercy": (
        "A piece in that state is an insult to me. The first quarter is on the "
        "house — I am fixing it for my own sake, not yours.",
        "No. I am not charging you for the part that should never have got "
        "that bad. Pay for the rest.",
    ),
    "unneeded": (
        "Nothing wrong with it. Go and get it dirty.",
    ),
    "broke": (
        "Come back with gold, or come back with less of it and I will do what "
        "that buys.",
    ),
}


# ==========================================================================
# STATE
# ==========================================================================
#
# One new key. `state["armor"]` is engine's and is written in place; everything
# else this module needs to remember lives under `state["upkeep"]`.

def new_state() -> dict:
    """A fresh upkeep block. `engine.DEFAULT_STATE` should carry this shape."""
    return {
        # Fractional wear that has not yet become a whole point. Wear is
        # DETERMINISTIC and accumulates — see `wear_encounter` for why there is
        # no dice roll anywhere in this module.
        "carry": {piece: 0.0 for piece in PIECES},
        # Companions that have been knocked out. pet_id -> {"fainted", "knocks"}.
        "pets": {},
        # The town loop's own bookkeeping, so `loop_report` can tell the player
        # the truth about their own last session rather than a design average.
        "since_town": {"encounters": 0, "gold": 0, "wear": 0.0},
        "visits": 0,
        "gold_spent_on_repairs": 0,
        "healed_count": 0,
        # Afflictions that outlived the encounter they were picked up in. The
        # Mender clears this as well as whatever list she is handed.
        "statuses": [],
    }


def ensure(state: dict) -> dict:
    """Make `state` upkeep-shaped, in place, and hand the block back.

    Idempotent and additive: an older save that has never heard of upkeep gets a
    fresh block, and a save that has one gets any missing sub-key filled in. It
    never rewrites `state["armor"]`, which may already have been played with.
    """
    if state is None:
        return new_state()
    block = state.get(UPKEEP_STATE_KEY)
    if not isinstance(block, dict):
        block = new_state()
        state[UPKEEP_STATE_KEY] = block
    fresh = new_state()
    for key, value in fresh.items():
        if key not in block:
            block[key] = value
    carry = block.get("carry")
    if not isinstance(carry, dict):
        carry = {}
        block["carry"] = carry
    for piece in PIECES:
        carry.setdefault(piece, 0.0)
    armour = state.get(ARMOUR_STATE_KEY)
    if not isinstance(armour, dict):
        # Rebuild engine's key the way engine builds it, legendary at zero.
        state[ARMOUR_STATE_KEY] = {
            piece["id"]: (INTEGRITY_MAX if piece["id"] != "legendary" else 0)
            for piece in world.ARMOR}
    return block


def _armour(state: dict) -> dict:
    ensure(state)
    return state[ARMOUR_STATE_KEY]


def integrity(state: dict, piece: str) -> int:
    return int(_armour(state).get(piece, INTEGRITY_MAX))


def _set_integrity(state: dict, piece: str, value: float) -> int:
    """The ONLY writer of an integrity number in this module. Clamped at both
    ends, so section C is enforced by there being nowhere else to write."""
    clamped = int(max(INTEGRITY_MIN, min(INTEGRITY_MAX, round(value))))
    _armour(state)[piece] = clamped
    return clamped


# ==========================================================================
# WEAR
# ==========================================================================

def guard_piece(state: dict) -> str:
    """What takes the wear from HITTING. Your shield, if you are carrying one;
    your gauntlets if your off hand is empty. Something always takes it, so a
    player cannot dodge outgoing wear by unequipping a slot."""
    offhand = ((state or {}).get("equipped") or {}).get("offhand") or ""
    return "shield" if offhand else "gauntlets"


def wear_points(*, difficulty: str = DEFAULT_DIFFICULTY, hits_taken: int = 0,
                blows_landed: int = 0, pay_scale: float = 1.0,
                gold_earned: float | None = None) -> dict:
    """The nominal wear one encounter produces, before quality, as a dict of
    {"taken": float, "dealt": float, "total": float}. Pure arithmetic, no state,
    so the balance can be argued with in a test without building a save.

    `pay_scale` IS THE SECOND THING THAT HAS TO CANCEL, and it is the one that
    nearly broke this module. `economy.py` tapers repeat solves of the same
    problem down to `economy.TAPER_FLOOR` — fifteen per cent — because the fifth
    solve of one problem is muscle memory rather than work. Correct. But wear
    driven by the fight while income is driven by the taper means a player
    drilling one problem pays full upkeep on fifteen per cent of the income,
    which is ninety-odd per cent of their earnings and exactly the tax the brief
    forbids.

    So wear rides the same multiplier. The fiction agrees with the arithmetic: a
    fight you have already won five times is not hitting you the way it did the
    first time. Grinding therefore earns little and costs little, and the RATIO
    the brief cares about is invariant — by construction, not by luck.

    Pass `economy.encounter_award(...)`'s taper for this problem. Defaults to 1.0,
    so a caller that has not been wired yet gets the full-price behaviour. It
    lives in `award.multipliers["taper"]`, which is the one place it is
    published; there is no `award.taper` attribute and reaching for one silently
    reads 1.0, which is precisely the bug this parameter exists to prevent.

    `gold_earned` is what this encounter actually paid. Supply it and the
    encounter's wear is clamped so mending it cannot cost more than
    `UPKEEP_INCOME_CEILING` of that. Omit it and the clamp runs against the
    band's base pay instead. See INCOME_CLAMP.
    """
    scale = float(WEAR_BY_DIFFICULTY.get(difficulty, 1.0))
    pay = max(0.0, min(1.0, float(pay_scale)))
    scale *= pay
    taken = WEAR_TAKEN * _effective_hits(hits_taken) * scale
    dealt = (WEAR_DEALT * max(0, int(blows_landed)) / DEALT_WEAR_EVERY) * scale
    total = taken + dealt

    # The clamp. Applied to both streams proportionally so the guard piece keeps
    # its share of the bill and the cadence stays where the player expects it.
    income = (float(gold_earned) if gold_earned is not None
              else float(expected_gold(difficulty)) * pay)
    ceiling = wear_ceiling_points(income) if INCOME_CLAMP else total
    clamped = False
    if total > ceiling:
        shrink = (ceiling / total) if total else 0.0
        taken, dealt, total = taken * shrink, dealt * shrink, ceiling
        clamped = True

    return {"taken": taken, "dealt": dealt, "total": total,
            "difficulty": difficulty, "scale": scale, "pay_scale": pay,
            "income": round(income, 2), "ceiling": round(ceiling, 3),
            "clamped": clamped,
            # What mending this encounter will cost, which is the number the
            # whole module is actually arguing about.
            "repair_gold": round(total * REPAIR_GOLD_PER_POINT, 3),
            "share_of_income": (round(total * REPAIR_GOLD_PER_POINT / income, 4)
                                if income else 0.0)}


def wear_encounter(state: dict, *, difficulty: str = DEFAULT_DIFFICULTY,
                   hits_taken: int = 0, blows_landed: int = 0,
                   pay_scale: float = 1.0, gold_earned: float | None = None,
                   sealed: bool = False) -> dict:
    """Spend one encounter's worth of durability. Call this ONCE, at the end of a
    fight, with the tallies the fight already kept.

    THERE IS NO RANDOMNESS HERE, and that is deliberate. Spreading wear by a dice
    roll means an unlucky run concentrates on one piece and the player is at the
    smith twice as often for no reason they can see or plan around. Instead the
    nominal points are split by `HIT_WEIGHTS` into per-piece fractions, banked in
    `state["upkeep"]["carry"]`, and only WHOLE points ever leave the bank. The
    result is that a player can count encounters and know what is coming, which
    is the difference between a maintenance rhythm and a nuisance.

    `gold_earned` is what the encounter paid — `economy.encounter_award(...).gold`.
    Passing it is what makes the brief's ceiling a guarantee rather than a tuning
    claim: the encounter's bill cannot exceed a third of its own purse. Omitting
    it clamps against the band's base pay instead, which is weaker but never
    absent.

    `sealed` is `finalexam.sealed(encounter, upkeep.UPKEEP_CAPABILITY)`. A
    measured run does not read the loadout, so it cannot wear it out.
    """
    block = ensure(state)
    if sealed:
        return {"applied": False, "reason": "sealed",
                "pieces": {}, "points": 0.0, "lines": []}

    nominal = wear_points(difficulty=difficulty, hits_taken=hits_taken,
                          blows_landed=blows_landed, pay_scale=pay_scale,
                          gold_earned=gold_earned)
    if nominal["total"] <= 0.0:
        return {"applied": False, "reason": "nothing to wear",
                "pieces": {}, "points": 0.0, "lines": []}

    guard = guard_piece(state)
    share: dict = {}
    for piece in PIECES:
        share[piece] = nominal["taken"] * float(HIT_WEIGHTS.get(piece, 0.0))
    share[guard] = share.get(guard, 0.0) + nominal["dealt"]

    carry = block["carry"]
    changed: dict = {}
    lines: list = []
    spent = 0.0
    for piece, raw in share.items():
        if raw <= 0.0:
            continue
        # Quality divides the wear here and multiplies the price in
        # `repair_quote`. Same factor, opposite ends, so it cancels.
        effective = raw / piece_toughness(state, piece)
        spent += effective
        carry[piece] = float(carry.get(piece, 0.0)) + effective
        whole = int(carry[piece])
        if whole <= 0:
            continue
        carry[piece] -= whole
        before = integrity(state, piece)
        after = _set_integrity(state, piece, before - whole)
        if after == before:
            continue
        changed[piece] = {"before": before, "after": after,
                          "lost": before - after,
                          "tier": items.armor_tier(piece, after)}
        # Only speak up on a threshold the sprite is about to show anyway. A
        # line of log per point would be the annoyance the brief warned about.
        if before >= REPAIR_ADVISED_AT > after:
            lines.append(f"Your {piece} is starting to show it.")
        elif before > INTEGRITY_MIN == after:
            lines.append(f"Your {piece} is done in — still worn, still worth "
                         f"half. {SMITH_NAME} can put it right.")

    block["since_town"]["encounters"] += 1
    block["since_town"]["wear"] = round(
        float(block["since_town"]["wear"]) + spent, 3)
    return {"applied": True, "pieces": changed, "points": round(spent, 3),
            "nominal": nominal, "guard": guard, "lines": lines,
            "condition": condition(state)}


def record_income(state: dict, gold: int) -> int:
    """Tell upkeep what the player just earned, so `loop_report` can quote their
    real income rather than a designer's average. Engine calls this wherever it
    already does `player["gold"] += ...` for an encounter."""
    block = ensure(state)
    block["since_town"]["gold"] = int(block["since_town"]["gold"]) + max(0, int(gold))
    return block["since_town"]["gold"]


# ==========================================================================
# CONDITION — what the worn kit is currently worth
# ==========================================================================

def condition(state: dict) -> dict:
    """Everything the client and the damage layer need about the kit's state."""
    rows = []
    scale_sum = 0.0
    weight_sum = 0.0
    for piece in PIECES:
        value = integrity(state, piece)
        eff = effectiveness(value)
        weight = float(HIT_WEIGHTS.get(piece, 0.0))
        scale_sum += eff * weight
        weight_sum += weight
        rows.append({
            "piece": piece,
            "integrity": value,
            "effectiveness": round(eff, 3),
            "advised": value < REPAIR_ADVISED_AT,
            "degraded": value <= INTEGRITY_MIN,
            "rarity": piece_rarity(state, piece),
            "toughness": round(piece_toughness(state, piece), 3),
            "tier": items.armor_tier(piece, value),
        })
    scale = (scale_sum / weight_sum) if weight_sum else 1.0
    worst = min(rows, key=lambda r: r["integrity"]) if rows else None
    return {
        "pieces": rows,
        "scale": round(scale, 3),
        "worst": worst["piece"] if worst else "",
        "advised": [r["piece"] for r in rows if r["advised"]],
        "degraded": [r["piece"] for r in rows if r["degraded"]],
        # Never "broken". There is no such state and the word should not appear
        # in a tooltip, because a player who reads "broken" reasonably assumes
        # they have lost something.
        "label": _condition_label(scale),
    }


def _condition_label(scale: float) -> str:
    if scale >= 0.99:
        return "Sound"
    if scale >= 0.90:
        return "Scuffed"
    if scale >= 0.75:
        return "Worn"
    if scale >= 0.60:
        return "Battered"
    return "Degraded"


def armour_scale(state: dict, *, sealed: bool = False) -> float:
    """One multiplier for the whole kit, weighted by how much of the player each
    piece covers. A sealed run reads 1.0 because it does not read the kit."""
    if sealed:
        return 1.0
    return float(condition(state)["scale"])


def wear_profile(profile, state: dict, *, sealed: bool = False):
    """Apply the kit's condition to an `elements.ArmourProfile`.

    Returns a NEW frozen profile — the caller's is untouched — with points and
    every resistance scaled by `armour_scale`. This is the one place durability
    becomes damage, and it is a multiplier on mitigation only. It can never add
    damage, never reduce the player's own output, and never touch the enemy, so
    there is no route by which a worn suit makes a fight unwinnable rather than
    longer.

    Call site: engine builds the player's Defender via
    `elements.Defender.for_player(...)`; wrap the profile on the way in.
    """
    if sealed or profile is None:
        return profile
    scale = armour_scale(state)
    if scale >= 0.999:
        return profile
    resist = {element: round(value * scale, 4)
              for element, value in (profile.resist or {}).items()}
    return elements.ArmourProfile(
        points=int(math.floor(profile.points * scale)),
        resist=resist,
        bonus_health=profile.bonus_health,      # a dented plate is still a plate:
        bonus_focus=profile.bonus_focus,        # the bar it lends you does not rot
        points_cap=profile.points_cap,
        kind=profile.kind,
    )


# ==========================================================================
# REPAIR
# ==========================================================================

def _affordable(rows: list, purse: int) -> list:
    """The pieces `repair` would actually mend with this much gold, in the order
    it would mend them. Cheapest first, because a poor player should leave with
    the most pieces fixed rather than the dearest one."""
    left = max(0, int(purse))
    out = []
    for row in sorted(rows, key=lambda r: r["gold"]):
        if row["gold"] <= left:
            left -= row["gold"]
            out.append(row)
    return out


def repair_quote(state: dict, piece: str = "", *, gold: int = 0,
                 sealed: bool = False) -> dict:
    """What it costs to put a piece — or the whole kit — back to 100.

    `piece` empty means everything that wants it. `gold` is what the player has,
    and only affects `affordable` / `partial`; the price is the price.
    """
    if sealed:
        # Names the capability that took it. A refusal that will not say which
        # seal it is speaking for is a refusal the next reader has to guess at,
        # and the sealed-GET contract checks for exactly this key.
        return {"error": "sealed", "capability": UPKEEP_CAPABILITY, "lines": [],
                "message": "Nothing is being worn in here, so nothing is worn out."}
    ensure(state)
    targets = [piece] if piece else [p for p in PIECES
                                     if integrity(state, p) < INTEGRITY_MAX]
    rows = []
    total = 0
    total_free = 0
    for target in targets:
        if target not in PIECES:
            continue
        current = integrity(state, target)
        if current >= INTEGRITY_MAX:
            continue
        # The mercy clause. Points below MERCY_THRESHOLD are not billed.
        billed_from = max(current, MERCY_THRESHOLD)
        charged_points = INTEGRITY_MAX - billed_from
        free_points = max(0, billed_from - current)
        tough = piece_toughness(state, target)
        # Rounded DOWN, with a floor of one coin. This used to round up, which
        # looks like a rounding detail and is not: five pieces times sixteen
        # smith visits across a hundred encounters is eighty half-coins, and
        # eighty half-coins is enough to push a struggling player's upkeep
        # across the third of income this whole module is built around. Rounding
        # in the player's favour is the same instinct as MERCY_THRESHOLD one
        # clause up, and it makes the ceiling arithmetic rather than hopeful.
        # Nothing is ever mended for free: any repair at all costs at least one.
        raw_cost = charged_points * REPAIR_GOLD_PER_POINT * tough
        cost = max(1, int(raw_cost)) if charged_points > 0 else 0
        rows.append({
            "piece": target,
            "integrity": current,
            "points": INTEGRITY_MAX - current,
            "charged_points": charged_points,
            "free_points": free_points,
            "rarity": piece_rarity(state, target),
            "toughness": round(tough, 3),
            "gold": cost,
            "mercy": free_points > 0,
            "gold_per_point": round(REPAIR_GOLD_PER_POINT * tough, 3),
        })
        total += cost
        total_free += free_points
    have = max(0, int(gold))
    lines = []
    if not rows:
        lines.append(SMITH_LINES["unneeded"][0])
    elif total_free:
        lines.append(SMITH_LINES["mercy"][0])
    else:
        lines.append(SMITH_LINES["quote"][0])
    if rows and have < total:
        lines.append(SMITH_LINES["broke"][0])
    return {
        "smith": SMITH_NAME,
        "rows": rows,
        "gold": total,
        "free_points": total_free,
        "affordable": have >= total,
        # A player who cannot afford everything can always afford SOMETHING, and
        # the UI should say so rather than showing one red number.
        #
        # This is computed exactly the way `repair` spends — cheapest piece
        # first, cumulatively, until the purse is empty — so the preview and the
        # button agree. Listing every individually affordable piece instead
        # would promise four repairs and deliver two.
        "partial": _affordable(rows, have),
        "lines": lines,
    }


def repair(state: dict, piece: str = "", *, gold: int = 0,
           sealed: bool = False) -> dict:
    """Do it. Returns what was mended and what it cost.

    This module never touches `player["gold"]` — engine owns the purse, the way
    it does for `forge.upgrade`. Deduct `result["gold_spent"]` at the call site.

    Partial payment is allowed and is the normal case for a poor player: pieces
    are mended cheapest-first until the gold runs out, so a broke player always
    leaves the smith with something fixed. Refusing the whole transaction because
    it could not be completed would be the same mistake as charging for healing.
    """
    if sealed:
        return {"error": "sealed", "capability": UPKEEP_CAPABILITY,
                "message": "Not in here. Whatever you break in an exam, you "
                           "break in the exam only."}
    block = ensure(state)
    quote = repair_quote(state, piece, gold=gold)
    rows = sorted(quote["rows"], key=lambda r: r["gold"])
    purse = max(0, int(gold))
    mended = []
    spent = 0
    for row in rows:
        if row["gold"] > purse:
            continue
        before = integrity(state, row["piece"])
        after = _set_integrity(state, row["piece"], INTEGRITY_MAX)
        purse -= row["gold"]
        spent += row["gold"]
        # The fractional bank is cleared too, or the first point after a repair
        # would fall off immediately and the player would swear the repair did
        # not take.
        block["carry"][row["piece"]] = 0.0
        mended.append({"piece": row["piece"], "before": before, "after": after,
                       "gold": row["gold"], "mercy": row["mercy"],
                       "tier": items.armor_tier(row["piece"], after)})
    block["gold_spent_on_repairs"] = int(block["gold_spent_on_repairs"]) + spent
    if not mended:
        return {"ok": False, "mended": [], "gold_spent": 0,
                "quote": quote,
                "message": (SMITH_LINES["unneeded"][0] if not quote["rows"]
                            else SMITH_LINES["broke"][0])}
    names = ", ".join(m["piece"] for m in mended)
    return {"ok": True, "mended": mended, "gold_spent": spent,
            "remaining": [r for r in quote["rows"]
                          if r["piece"] not in {m["piece"] for m in mended}],
            "condition": condition(state),
            "message": f"{names} put right. {spent} gold.",
            "smith": SMITH_NAME}


# ==========================================================================
# D. FOCUS REFILLS FREE AFTER EVERY BATTLE
# ==========================================================================
#
# Focus is `player["mana"]`, ceiling `config.MANA_MAX` = 30. It is the currency
# of the hint ladder: 3, 4, 6, 8, 12 for Oracle, Reveal Path, Pseudosight, Code
# Fragment and Phoenix — 33 for the whole climb, against a bar of 30.
#
# It refills to full after every battle, automatically, for nothing. The reason
# is the same one that makes the healer free, and it is arguably even more
# direct: focus buys HELP. A player who is out of focus is a player who cannot
# ask a question, and a player who cannot ask a question when they are stuck is
# a player who closes the game. Focus is therefore a within-fight budget — it
# makes you choose how much help to take in THIS encounter — and never a
# between-fight resource that can be depleted across a session.
#
# The one wrinkle is VOIDED, which `elements.STATUSES` defines as "no focus
# returns while this lasts". That status is honoured here rather than ignored,
# because ignoring it would quietly delete an element's identity. But it is
# honoured down to a FLOOR, not to zero: a voided player still comes out of the
# fight with enough for Oracle and Reveal Path — the nudge and the map — which
# are the two rungs that must never be unaffordable. Elements says it itself:
# "Voided players can still ask for help; they just cannot afford to ask twice."
# This is that sentence, as a number.

FOCUS_FIELD = elements.FOCUS_FIELD          # "mana"
HEALTH_FIELD = elements.HEALTH_FIELD        # "stamina"

VOIDED_FOCUS_FLOOR = 7      # Oracle (3) + Reveal Path (4). The map, always.


def after_battle(state: dict, *, statuses=None, sealed: bool = False) -> dict:
    """Run this at the end of EVERY encounter, win or lose, in adventure mode.

    Refills focus, resets the companion's knock counter if it is still standing,
    and reports the low-health alarm so the client can start or stop the pulse
    without a second call.

    Health is NOT restored here. Health is what makes the walk to the Mender mean
    something; focus is not allowed to mean anything between fights.
    """
    block = ensure(state)
    player = (state or {}).get("player") or {}
    if sealed:
        return {"applied": False, "reason": "sealed", "focus": player.get(FOCUS_FIELD, 0)}

    live = _as_status_ids(statuses)
    voided = any(elements.STATUSES.get(sid) is not None
                 and elements.STATUSES[sid].kind == "regen" for sid in live)
    ceiling = int(player.get(f"{FOCUS_FIELD}_max", config.MANA_MAX) or config.MANA_MAX)
    before = int(player.get(FOCUS_FIELD, 0) or 0)
    if voided:
        target = max(before, min(ceiling, VOIDED_FOCUS_FLOOR))
        line = ("The void is still on you. Enough focus returns to ask twice, "
                "and no more.")
    else:
        target = ceiling
        line = "Focus returns." if target > before else ""
    player[FOCUS_FIELD] = target

    # A companion that stayed upright shakes off the knocks it took. Free, and
    # for the same reason focus is free: the pet is the hint system.
    woken = []
    for pet_id, row in (block.get("pets") or {}).items():
        if not row.get("fainted"):
            if row.get("knocks"):
                woken.append(pet_id)
            row["knocks"] = 0

    return {"applied": True, "focus": target, "focus_before": before,
            "focus_max": ceiling, "voided": voided, "steadied": woken,
            "line": line, "alarm": alarm(state)}


def _as_status_ids(statuses) -> list:
    """Accepts a list of StatusInstance, a list of the flat dicts engine stores
    in `enc.statuses`, or None. Anything it does not recognise is skipped rather
    than raising: the status bar must never be the thing that crashes the town."""
    out = []
    for entry in statuses or ():
        if isinstance(entry, dict):
            sid = entry.get("id")
        else:
            sid = getattr(entry, "id", None)
        if isinstance(sid, str) and sid in elements.STATUSES:
            out.append(sid)
    return out


# ==========================================================================
# E. THE LOW-HEALTH ALARM
# ==========================================================================
#
# Modelled here as data; drawn and sounded by files another pass owns.
#
# The brief: "At low health the player sprite blinks red with a heartbeat so it
# is impossible to miss." Two channels, one clock. The blink rate and the
# heartbeat rate are the SAME NUMBER expressed twice — `pulse_hz` is literally
# `beats_per_minute / 60` — because a sprite flashing at one speed over a heart
# thumping at another reads as two unrelated warnings and the player tunes both
# out. One pulse, seen and heard, is impossible to miss.
#
# Thresholds against `config.STAMINA_MAX` = 20, and a failed submission costs
# `config.STAMINA_LOSS_FAILED_SUBMIT` = 2:
#
#   band       fraction      health      meaning
#   STEADY     > 0.50        11-20       silent. no alarm in the healthy half
#   WORN       0.35-0.50      8-10       a colour shift only. no pulse, no sound
#   CRITICAL   0.15-0.35      4-7        red pulse + heartbeat. three bad submits
#   DIRE       <= 0.15        0-3        fast and loud. one bad submit
#
# WORN does not pulse on purpose. If the alarm starts at half health it is
# running for most of every fight, and an alarm that is always on is decoration.
# It starts at seven, where the player has exactly three more failures in hand —
# enough time to act, little enough to matter.

@dataclass(frozen=True)
class AlarmBand:
    id: str
    name: str
    at: float               # fraction of max health at or below which it fires
    pulse: bool             # does the sprite blink
    heartbeat: bool         # is there a sound under it
    colour: str
    blurb: str


# The sound is an ALARM TO HEAL, so it starts late and it starts once.
#
# These were 0.35 and 0.15 with sound on both, which meant a heartbeat under
# roughly a third of every fight. An alarm that is usually on is not an alarm —
# it is ambience, and the player stops hearing it long before the fight it was
# supposed to warn them about. So the sound now waits until a tenth of the bar,
# and the band above it warns in silence: red on the sprite, nothing in the ears.
# Look up and you get a warning; ignore it and the room starts making a noise.
ALARM_BANDS: tuple = (
    AlarmBand("DIRE", "Dire", 0.10, True, True, "#ff3b46",
              "Red pulse and a heartbeat under it. Heal now."),
    AlarmBand("CRITICAL", "Critical", 0.25, True, False, "#ff6a7a",
              "Red pulse on the sprite, and deliberately no sound yet."),
    AlarmBand("WORN", "Worn", 0.50, False, False, "#e8c37d",
              "A colour shift and nothing else. Not an alarm yet."),
    AlarmBand("STEADY", "Steady", 1.01, False, False, "#8fd07a",
              "Nothing. The healthy half of the bar says nothing."),
)

ALARM_ONSET = 0.25          # where the silent red pulse begins
HEARTBEAT_ONSET = 0.10      # where the sound begins, and not one point sooner
BPM_ONSET = 72              # a resting heart, at the moment it starts to matter
BPM_MAX = 132               # at zero. fast, not cartoonish
PULSE_MIN_ALPHA = 0.25      # how far the red fades out between blinks
PULSE_MAX_ALPHA = 0.85


def alarm_for(current: int, maximum: int) -> dict:
    """The alarm as pure numbers. No state needed, so the client's own
    prediction and the server's agree by construction."""
    maximum = max(1, int(maximum or 1))
    current = max(0, min(maximum, int(current or 0)))
    ratio = current / maximum
    band = ALARM_BANDS[-1]
    for candidate in ALARM_BANDS:
        if ratio <= candidate.at:
            band = candidate
            break
    # How far into the alarm we are, 0 at onset and 1 on the floor.
    severity = 0.0
    if ratio < ALARM_ONSET:
        severity = min(1.0, (ALARM_ONSET - ratio) / ALARM_ONSET)
    bpm = 0
    if band.heartbeat:
        bpm = int(round(BPM_ONSET + (BPM_MAX - BPM_ONSET) * severity))
    return {
        "band": band.id,
        "name": band.name,
        "health": current,
        "health_max": maximum,
        "ratio": round(ratio, 3),
        "severity": round(severity, 3),
        # The sprite. One pulse, shared with the sound.
        "pulse": band.pulse,
        "pulse_hz": round(bpm / 60.0, 3) if bpm else 0.0,
        "colour": band.colour,
        "alpha_min": PULSE_MIN_ALPHA,
        "alpha_max": round(PULSE_MIN_ALPHA
                           + (PULSE_MAX_ALPHA - PULSE_MIN_ALPHA) * max(severity, 0.4), 3),
        # The sound. Same clock.
        "heartbeat": band.heartbeat,
        "bpm": bpm,
        # What the player should be told, once, when the band changes — not
        # every frame. The client should latch on `band` and only speak on a
        # transition downward.
        "blurb": band.blurb,
        "advice": _alarm_advice(band.id),
        # Rounds of grace left at the standard failure cost, which is the only
        # genuinely actionable number in here.
        "failures_left": current // max(1, config.STAMINA_LOSS_FAILED_SUBMIT),
    }


def _alarm_advice(band_id: str) -> str:
    if band_id == "DIRE":
        return ("Drink something or walk out. Margit is free and she is not "
                "going anywhere.")
    if band_id == "CRITICAL":
        return "Three more bad submissions and you are on the floor."
    if band_id == "WORN":
        return "Half gone. Worth noticing, not worth panicking about."
    return ""


def alarm(state: dict) -> dict:
    player = (state or {}).get("player") or {}
    return alarm_for(player.get(HEALTH_FIELD, 0),
                     player.get(f"{HEALTH_FIELD}_max", config.STAMINA_MAX))


# ==========================================================================
# PETS: FAINTING, AND THE FLOOR THAT SURVIVES IT
# ==========================================================================
#
# The brief: pets take AoE damage from monsters and bosses and can faint; a
# fainted pet gives no hints; the player returns to town to heal both.
#
# THE DANGER IN THIS IDEA, stated plainly because it nearly broke the rules:
# engine's own comment says "THE COMPANION IS THE HINT SYSTEM". If a fainted pet
# simply switched hints off, then bad luck in a fight would remove the player's
# ability to ask for help in the NEXT fight, and learning would dead-end. That is
# forbidden.
#
# So a faint removes the SHORTCUT and never the FLOOR. `pets.FREE_SOLUTION_AFTER`
# is 3: after three attempts on a problem the worked solution is available and
# engine already makes it free. That floor does not run through the animal and
# must not start to. What a fainted pet costs you is the early, cheap, tiered
# read — the thing that would have saved you those three attempts. That is a real
# loss with a real remedy (walk to town, it is free), and it cannot strand
# anybody.
#
# Knocks, not hit points. Giving a pet a health bar means a second bar to watch
# during a fight whose entire attention budget belongs to the code editor.

PET_KNOCKS_TO_FAINT = 3


def _pet_row(state: dict, pet_id: str) -> dict:
    block = ensure(state)
    rows = block.setdefault("pets", {})
    row = rows.get(pet_id)
    if not isinstance(row, dict):
        row = {"fainted": False, "knocks": 0}
        rows[pet_id] = row
    row.setdefault("fainted", False)
    row.setdefault("knocks", 0)
    return row


def pet_knock(state: dict, pet_id: str, *, hits: int = 1,
              sealed: bool = False) -> dict:
    """An area attack caught the companion. Three in one encounter and it drops.

    Call from wherever a monster's AoE resolves. `hits` lets a boss that hits the
    whole field twice in a turn be one call.
    """
    if sealed or not pet_id:
        return {"fainted": False, "knocks": 0, "applied": False}
    row = _pet_row(state, pet_id)
    if row["fainted"]:
        return {"fainted": True, "knocks": row["knocks"], "applied": False,
                "line": ""}
    row["knocks"] = int(row["knocks"]) + max(1, int(hits))
    if row["knocks"] < PET_KNOCKS_TO_FAINT:
        left = PET_KNOCKS_TO_FAINT - row["knocks"]
        return {"fainted": False, "knocks": row["knocks"], "applied": True,
                "remaining": left,
                "line": f"It takes the edge of that one. {left} more like it "
                        f"and it goes down."}
    row["fainted"] = True
    return {"fainted": True, "knocks": row["knocks"], "applied": True,
            "remaining": 0,
            "line": "It goes down, and it stays down. It will not read for you "
                    "until Margit has seen it.",
            "remedy": "Free, at the Mender. It costs you the walk."}


def is_fainted(state: dict, pet_id: str) -> bool:
    if not pet_id:
        return False
    return bool(_pet_row(state, pet_id)["fainted"])


def fainted_pets(state: dict) -> list:
    block = ensure(state)
    return sorted(pid for pid, row in (block.get("pets") or {}).items()
                  if row.get("fainted"))


def pet_gate(state: dict, pet_id: str, *, attempts: int = 0) -> dict:
    """May this companion speak, and if not, what is still guaranteed?

    Engine's `_hint_gate` should consult this before asking pets for a hint.
    The `floor` key is the contract that keeps rule one intact: it is always
    present, always true once the player has genuinely tried, and never depends
    on the animal being conscious.
    """
    floor_open = int(attempts) >= _free_solution_after()
    if not is_fainted(state, pet_id):
        return {"speaks": True, "fainted": False, "floor": floor_open}
    return {
        "speaks": False,
        "fainted": True,
        # THE FLOOR. Unconditional, and deliberately not routed through the pet.
        "floor": floor_open,
        "floor_after": _free_solution_after(),
        "message": (
            "It is out cold and cannot read the problem for you. The ladder is "
            "still there and the worked solution still arrives after "
            f"{_free_solution_after()} honest attempts — a fainted companion "
            "costs you the shortcut, never the road."),
        "remedy": f"{MENDER.name} will wake it for nothing.",
    }


def revive_pets(state: dict) -> dict:
    """Wake everything that is down. Free, at the Mender, always."""
    block = ensure(state)
    woken = []
    for pet_id, row in (block.get("pets") or {}).items():
        if row.get("fainted"):
            row["fainted"] = False
            woken.append(pet_id)
        row["knocks"] = 0
    return {"revived": sorted(woken), "count": len(woken)}


# ==========================================================================
# THE HEALER, AS A FUNCTION
# ==========================================================================

def _cure_in_place(statuses: list) -> list:
    """Clear every affliction from a live status list, whatever shape it is in.

    `elements.cure` wants `StatusInstance` objects, which is what engine holds
    mid-turn; but `enc.statuses` and a dungeon run's `run["statuses"]` are the
    flat dicts those objects serialise to. The Mender is reachable from both, so
    she normalises rather than making the caller remember which list it is
    holding. Mutates in place and hands back the ids that were cleared.
    """
    if not statuses:
        return []
    flat = isinstance(statuses[0], dict)
    live = [elements.StatusInstance.from_dict(s) if isinstance(s, dict) else s
            for s in statuses]
    result = elements.cure(live, "FULL")
    statuses[:] = [s.to_dict() for s in live] if flat else live
    return list(result.get("cured", []))


def heal(state: dict, *, statuses=None, sealed: bool = False,
         rng: random.Random | None = None) -> dict:
    """Everything Margit does, in one call, for nothing.

    Health to full, every affliction in `elements.STATUSES` cleared, every
    fainted companion woken, focus topped up on the way out. `statuses` is the
    live list — `enc.statuses`, or a dungeon run's — and is cleaned IN PLACE via
    `elements.cure(..., "FULL")` so the caller's list is correct afterwards.

    Returns `gold_cost: 0`. That key exists so that nobody wiring a shop screen
    has to wonder whether they forgot to charge for it. They did not. It is free.
    """
    if sealed:
        return {"error": "sealed", "capability": UPKEEP_CAPABILITY,
                "message": "There is no town in here. Finish the paper."}
    block = ensure(state)
    player = (state or {}).get("player") or {}

    ceiling = int(player.get(f"{HEALTH_FIELD}_max", config.STAMINA_MAX)
                  or config.STAMINA_MAX)
    before = int(player.get(HEALTH_FIELD, 0) or 0)
    player[HEALTH_FIELD] = ceiling
    restored = ceiling - before

    # Afflictions: the handed list, plus anything that outlived its encounter.
    cured = []
    if statuses is not None:
        cured.extend(_cure_in_place(statuses))
    carried = _as_status_ids(block.get("statuses"))
    if carried:
        cured.extend(carried)
    block["statuses"] = []

    revived = revive_pets(state)

    # Focus too, because she is not going to let you walk out of here unable to
    # ask a question.
    focus_ceiling = int(player.get(f"{FOCUS_FIELD}_max", config.MANA_MAX)
                        or config.MANA_MAX)
    focus_before = int(player.get(FOCUS_FIELD, 0) or 0)
    player[FOCUS_FIELD] = focus_ceiling

    block["healed_count"] = int(block["healed_count"]) + 1

    did_something = bool(restored or cured or revived["count"])
    kind = "healed" if restored else ("cleansed" if cured else
                                      ("revived" if revived["count"] else "unneeded"))
    lines = [healer_line("greet", rng=rng), healer_line(kind, rng=rng)]
    cond = condition(state)
    if cond["advised"]:
        lines.append(healer_line("kit", rng=rng))
    return {
        "ok": True,
        "healer": {"id": MENDER.id, "name": MENDER.name, "title": MENDER.title},
        "gold_cost": 0,
        "free_because": MENDER.free_because,
        "health": ceiling, "health_before": before, "restored": restored,
        "cured": sorted(set(cured)),
        "cured_names": [elements.STATUSES[s].name for s in sorted(set(cured))
                        if s in elements.STATUSES],
        "revived": revived["revived"],
        "focus": focus_ceiling, "focus_before": focus_before,
        "statuses": list(statuses or []),
        "did_something": did_something,
        "alarm": alarm(state),
        "lines": [line for line in lines if line],
    }


# ==========================================================================
# F. THE TOWN LOOP, STATED HONESTLY
# ==========================================================================
#
# The question the brief asks is the right one: if the answer is "nothing but
# chores", redesign it. So here is the answer without varnish.
#
# WHAT BRINGS A PLAYER BACK — four things, and only one of them is a chore:
#
#   1. HEALTH, which is free. This is a rhythm, not a decision. At four health
#      with a dungeon floor left you go home, and it costs you the walk. Because
#      it is free it never becomes a calculation, and because it is a walk it
#      still costs something real.
#
#   2. A FAINTED COMPANION, also free. Same shape, different sting: what you
#      lost was the cheap read on the next problem, so the walk buys back help
#      rather than health. This is the one that makes an AoE boss feel expensive
#      without making it feel unfair.
#
#   3. DURABILITY, which is the chore, and which is why it is rationed to
#      roughly one visit every seventeen encounters and roughly a sixth of what
#      you earned in them. It is NEVER mandatory: the kit degrades to half and
#      stops. A player who hates the smith can simply not go, fight at half
#      armour, and the only thing that happens is the fights get longer — which
#      is more typing, which is the thing the game wanted from them anyway. That
#      is the escape hatch that keeps this from being a tax.
#
#   4. THE PART THAT IS NOT MAINTENANCE, and without which the other three ARE
#      just chores: the smith and the forge are the same building. `forge.py`
#      runs a nine-rung weapon ladder with gold costs from 40 to 1500, and the
#      gold you did not spend on repairs is the gold that buys the next rung.
#      That is the real loop, and it is a loop rather than an errand because the
#      two uses of gold are in tension. Every repair is a rung deferred. A player
#      running their kit down to 60 and spending the difference on the forge is
#      playing the game correctly, and so is the one who keeps their plate
#      mirror-bright. Upkeep's job is to make that a CHOICE with legible numbers,
#      which is what `loop_report` exists to print.
#
# WHAT THE TOWN IS NOT: it is not a gate. Nothing in town is required to progress,
# nothing in town can be locked, and a player with no gold, a degraded kit and an
# unconscious companion can walk straight back out and keep learning. That is not
# generosity. It is the rule.

LOOP: dict = {
    "free": ("health", "afflictions", "fainted companions", "focus"),
    "costs_gold": ("armour repair", "the forge ladder", "the Armorer's respec"),
    "cadence_encounters": 17,
    "mandatory": (),
    "escape_hatch": (
        "Never repair anything. The kit floors at half effectiveness and stops. "
        "Fights get longer; nothing becomes unwinnable."),
    "tension": (
        "Gold spent on repairs is gold not spent on the next forge rung. That "
        "is the decision the town exists to pose."),
}


def town_visit(state: dict, *, gold: int = 0, sealed: bool = False,
               statuses=None, rng: random.Random | None = None) -> dict:
    """Walking into town. Heals for free, quotes the smith, and reports the loop.

    Does not spend gold and does not repair — `repair` is a separate, deliberate
    click, because the free half should never be able to surprise you by billing
    you. Engine deducts nothing from this call.
    """
    if sealed:
        return {"error": "sealed", "capability": UPKEEP_CAPABILITY,
                "message": "The town is outside. Finish."}
    block = ensure(state)
    healed = heal(state, statuses=statuses, rng=rng)
    quote = repair_quote(state, gold=gold)
    report = loop_report(state)
    block["visits"] = int(block["visits"]) + 1
    block["since_town"] = {"encounters": 0, "gold": 0, "wear": 0.0}
    return {
        "ok": True,
        "healer": healed,
        "smith": quote,
        "loop": report,
        "condition": condition(state),
        "alarm": alarm(state),
        "visits": block["visits"],
    }


def loop_report(state: dict, *, difficulty: str = DEFAULT_DIFFICULTY,
                hits_taken: int = 3, blows_landed: int = 4,
                sealed: bool = False) -> dict:
    """The arithmetic, using the player's OWN last stretch where it has one.

    This is the anti-chore device: the player is told how many encounters until
    the smith matters, what it will cost, and what share of what they actually
    earned that is. A maintenance system the player can predict is a rhythm; one
    they cannot is an interruption.

    `sealed` is the in-force test from docs/10-sealed-views.md, and it is here
    because the town square was answering one question twice and disagreeing
    with itself. `repair_quote(sealed=True)` says "nothing is being worn in
    here, so nothing is worn out" — correct, because a measured run is build
    sealed and the kit is not in play — and `Game.town` then rendered THIS
    report beside it, unsealed, quoting a mending bill and a sentence naming
    the piece and the price. Two doors onto one number, one of them refusing
    and the other one answering. That is finding 4.E wearing a fourth hat: a
    number is not a hint and is still FALSE, and a player will plan against it.

    DEGRADE rather than refuse, because half of this report is world and stays
    true: what an encounter pays, the third-of-income ceiling, the escape
    hatch, and the fact that health is free. Only the mending half is
    suspended, and it is named in `suspended` rather than silently zeroed.
    """
    block = ensure(state)
    since = block["since_town"]
    played = int(since["encounters"])
    earned = int(since["gold"])

    per = wear_points(difficulty=difficulty, hits_taken=hits_taken,
                      blows_landed=blows_landed)
    # The piece that decides the cadence is whichever is closest to the line,
    # measured in encounters rather than points so the answer is actionable.
    soonest = None
    for piece in PIECES:
        share = per["taken"] * float(HIT_WEIGHTS.get(piece, 0.0))
        if piece == guard_piece(state):
            share += per["dealt"]
        rate = share / piece_toughness(state, piece)
        if rate <= 0:
            continue
        headroom = integrity(state, piece) - REPAIR_ADVISED_AT
        encounters = max(0.0, headroom / rate)
        if soonest is None or encounters < soonest["encounters"]:
            soonest = {"piece": piece, "encounters": round(encounters, 1),
                       "rate": round(rate, 3),
                       "integrity": integrity(state, piece)}

    quote = repair_quote(state, gold=0)
    # Upkeep per encounter in gold, which is the single number that decides
    # whether this system is a rhythm or a tax.
    per_encounter_gold = 0.0
    for piece in PIECES:
        share = per["taken"] * float(HIT_WEIGHTS.get(piece, 0.0))
        if piece == guard_piece(state):
            share += per["dealt"]
        tough = piece_toughness(state, piece)
        # wear is divided by toughness, price is multiplied by it: cancels.
        per_encounter_gold += (share / tough) * REPAIR_GOLD_PER_POINT * tough
    income = expected_gold(difficulty)
    share_of_income = (per_encounter_gold / income) if income else 0.0
    actual_share = ((quote["gold"] / earned) if earned else None)

    report = {
        "since_town": {"encounters": played, "gold": earned,
                       "wear_points": round(float(since["wear"]), 2)},
        "next_repair": soonest or {},
        "quote_now": quote["gold"],
        "upkeep_per_encounter": round(per_encounter_gold, 2),
        "income_per_encounter": income,
        "share_of_income": round(share_of_income, 3),
        "share_of_income_actual": (round(actual_share, 3)
                                   if actual_share is not None else None),
        "budget": UPKEEP_INCOME_CEILING,
        "within_budget": share_of_income <= UPKEEP_INCOME_CEILING,
        "free": LOOP["free"],
        "mandatory": LOOP["mandatory"],
        "escape_hatch": LOOP["escape_hatch"],
        "tension": LOOP["tension"],
        "line": _loop_line(soonest, quote["gold"], share_of_income),
        "sealed": False,
        "suspended": [],
    }
    if not sealed:
        return report
    # The mending half, zeroed and named. `repair_quote(sealed=True)` already
    # says this sentence at the other door; saying the same thing in the same
    # words is the point.
    report.update({
        "next_repair": {},
        "quote_now": 0,
        "upkeep_per_encounter": 0.0,
        "share_of_income": 0.0,
        "share_of_income_actual": None,
        "within_budget": True,
        "line": "Nothing is being worn in here, so nothing is worn out. The "
                "smith's arithmetic comes back when the run does.",
        "sealed": True,
        "suspended": ["next_repair", "quote_now", "upkeep_per_encounter",
                      "share_of_income", "share_of_income_actual"],
    })
    return report


def _loop_line(soonest, gold: int, share: float) -> str:
    if not soonest:
        return "Nothing wants mending."
    if soonest["encounters"] <= 0:
        return (f"Your {soonest['piece']} wants {SMITH_NAME} now. "
                f"{gold} gold puts the whole kit right — about "
                f"{int(round(share * 100))} percent of what this kind of fight "
                f"pays you.")
    return (f"About {int(soonest['encounters'])} more encounters before your "
            f"{soonest['piece']} is worth mending. Upkeep is running at roughly "
            f"{int(round(share * 100))} percent of what you earn.")


# The brief's own ceiling: "If repair costs more than a third of what the player
# earned meanwhile, it is a tax and you have got it wrong." Asserted, not hoped.
#
# ONE CALL SITE MAKES THIS A GUARANTEE INSTEAD OF A CLAIM. Wherever engine.py
# ends an encounter it already has the award in hand, so:
#
#     award = economy.encounter_award(econ, region_id=..., difficulty=d, rank=r,
#                                     problem_id=p)
#     upkeep.wear_encounter(state, difficulty=d,
#                           hits_taken=enc.hits_taken,
#                           blows_landed=enc.blows_landed,
#                           pay_scale=award.multipliers["taper"],
#                           gold_earned=award.gold,
#                           sealed=finalexam.sealed(enc, UPKEEP_CAPABILITY))
#
# `pay_scale` keeps a grinder's wear in step with a grinder's income;
# `gold_earned` keeps a struggling player's bill in step with a struggling
# player's purse. `self_check()["worst_player_wired"]` is that sweep — every
# difficulty against every rank against a player taking twelve hits — and it
# comes back at exactly a third in the worst square of the grid.
# `worst_player_unwired` is the same sweep with the keyword left off: 83%, at
# EASY on a LEARNING_CLEAR. That gap is the cost of not passing one argument.
UPKEEP_INCOME_CEILING = 1.0 / 3.0

# What an encounter pays, at rank B in the cheapest area.
#
# `economy.py` owns this and is asked first. It is imported lazily for the same
# reason pets is: the town must not fail to load because a sibling module is
# mid-edit. The fallback below is the OLD derivation — `grading.xp_for` base at
# rank B and combo 1.0, through engine's `player["gold"] += xp // 3` — which is
# what this module was balanced against before economy landed. The fallback pays
# LESS than economy does in every band (MEDIUM 20 against 24, HARD 36 against
# 42), so every ratio in this file is stated against the stingier of the two.
# If the fallback is the one in use, the real game is more generous than the
# numbers claim, never less.
XP_BASE: dict = {"TUTORIAL": 12, "EASY": 25, "MEDIUM": 60, "HARD": 110,
                 "ELITE": 140, "BOSS": 200}


def expected_gold(difficulty: str = DEFAULT_DIFFICULTY) -> int:
    """Gold for one clear at rank B, before area and before the taper."""
    try:
        from . import economy as _economy
        base = _economy.ENCOUNTER_BASE.get(str(difficulty or "").upper())
        if base:
            # rank B pays 1.0 and the cheapest area multiplies by 1.0, so this
            # is the floor of what the band pays rather than a typical purse.
            return int(base)
    except Exception:
        pass
    return int(XP_BASE.get(difficulty, 60)) // 3


# ==========================================================================
# SELF-CHECK — every balance claim above, run as arithmetic
# ==========================================================================

def _budget_table(*, hits_taken: int = 3, blows_landed: int = 4) -> list:
    """Upkeep as a share of income, per difficulty, on a Common kit.

    Quality cancels (wear divides by toughness, price multiplies by it) so this
    table is the same for every kit in the game. That is proved separately.
    """
    rows = []
    for difficulty in ("TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS"):
        income = expected_gold(difficulty)
        per = wear_points(difficulty=difficulty, hits_taken=hits_taken,
                          blows_landed=blows_landed, gold_earned=income)
        gold_per_encounter = per["total"] * REPAIR_GOLD_PER_POINT
        share = (gold_per_encounter / income) if income else 0.0
        rows.append({
            "difficulty": difficulty,
            "wear_points": round(per["total"], 3),
            "repair_gold": round(gold_per_encounter, 2),
            "income_gold": income,
            "share": round(share, 4),
            "clamped": per["clamped"],
            "within": share <= UPKEEP_INCOME_CEILING,
        })
    return rows


# The rank multipliers income is actually paid at. Named here rather than
# imported so the worst-case table below still computes if economy is mid-edit.
_RANK_PAY_FALLBACK = {"S": 1.5, "A": 1.25, "B": 1.0, "C": 0.8,
                      "LEARNING_CLEAR": 0.4}


def _rank_pay() -> dict:
    try:
        from . import economy as _economy
        return dict(_economy.RANK_PAY)
    except Exception:
        return dict(_RANK_PAY_FALLBACK)


def _worst_player_table(*, wired: bool = True) -> dict:
    """The table that matters, which is not the competent player's.

    Wear is driven by how badly the fight went; income is driven by how well it
    went. They diverge exactly where they must not, so this sweeps every
    difficulty against every rank against a player taking a beating, and reports
    the worst share in the whole grid.

    `wired` is whether the caller told `wear_points` what the encounter actually
    paid. Wired, the ceiling is a guarantee. Unwired it is a tuning claim, and
    this is where you can read how far the claim bends.
    """
    ranks = _rank_pay()
    worst = {"share": 0.0}
    rows = []
    for difficulty in ("EASY", "MEDIUM", "HARD", "ELITE", "BOSS"):
        base = expected_gold(difficulty)
        for rank, pay in sorted(ranks.items(), key=lambda kv: kv[1]):
            income = base * pay
            if income <= 0:
                continue
            for hits in (2, 3, 4, 6, 8, 12):
                per = wear_points(difficulty=difficulty, hits_taken=hits,
                                  blows_landed=hits + 1,
                                  gold_earned=income if wired else None)
                share = per["total"] * REPAIR_GOLD_PER_POINT / income
                row = {"difficulty": difficulty, "rank": rank, "hits": hits,
                       "income": round(income, 1),
                       "repair_gold": round(per["total"] * REPAIR_GOLD_PER_POINT, 2),
                       "share": round(share, 4)}
                rows.append(row)
                if share > worst["share"]:
                    worst = {**row, "share": share}
    return {"wired": wired, "rows": rows, "worst": worst,
            "worst_share": round(worst["share"], 4),
            "within": worst["share"] <= UPKEEP_INCOME_CEILING + 1e-9}


def _cadence(piece: str = "chestplate", difficulty: str = DEFAULT_DIFFICULTY,
             *, hits_taken: int = 3, blows_landed: int = 4) -> dict:
    """How many encounters until one piece wants the smith, and what that costs."""
    per = wear_points(difficulty=difficulty, hits_taken=hits_taken,
                      blows_landed=blows_landed)
    rate = per["taken"] * float(HIT_WEIGHTS.get(piece, 0.0))
    if piece == "shield":
        rate += per["dealt"]
    to_advised = (INTEGRITY_MAX - REPAIR_ADVISED_AT) / rate if rate else 0.0
    to_floor = INTEGRITY_MAX / rate if rate else 0.0
    points = INTEGRITY_MAX - REPAIR_ADVISED_AT
    # Priced the way `repair_quote` prices, or the headline disagrees with the till.
    cost = max(1, int(points * REPAIR_GOLD_PER_POINT))
    earned = to_advised * expected_gold(difficulty)
    return {
        "piece": piece, "difficulty": difficulty,
        "points_per_encounter": round(rate, 3),
        "encounters_to_advised": round(to_advised, 1),
        "encounters_to_floor": round(to_floor, 1),
        "repair_gold": cost,
        "gold_earned_meanwhile": int(round(earned)),
        "share": round(cost / earned, 4) if earned else 0.0,
    }


def _prove_quality_cancels() -> dict:
    """A Mythic kit and a Common kit must cost the same gold per encounter."""
    out = []
    for rarity in items.RARITY_ORDER:
        tough = toughness_of(rarity)
        per = wear_points(difficulty="MEDIUM", hits_taken=3, blows_landed=4)
        # points actually lost, then priced at this rarity's rate
        lost = per["total"] / tough
        gold = lost * REPAIR_GOLD_PER_POINT * tough
        out.append({"rarity": rarity, "toughness": round(tough, 3),
                    "points_lost": round(lost, 3), "gold": round(gold, 4)})
    spread = max(r["gold"] for r in out) - min(r["gold"] for r in out)
    return {"rows": out, "spread": round(spread, 6), "cancels": spread < 1e-9}


def _prove_taper_cancels() -> dict:
    """The player drilling one problem into the ground.

    economy tapers a repeated problem's pay to TAPER_FLOOR. Wear rides the same
    multiplier, so the SHARE of income upkeep eats does not move. Without this,
    a grinder paid 15% of the gold for 100% of the wear.
    """
    try:
        from . import economy as _economy
        floor = float(_economy.TAPER_FLOOR)
    except Exception:
        floor = 0.15
    rows = []
    for pay in (1.0, 0.55, 0.30, floor):
        per = wear_points(difficulty="MEDIUM", hits_taken=3, blows_landed=4,
                          pay_scale=pay)
        gold_cost = per["total"] * REPAIR_GOLD_PER_POINT
        income = expected_gold("MEDIUM") * pay
        rows.append({"pay_scale": round(pay, 3),
                     "wear_points": round(per["total"], 3),
                     "repair_gold": round(gold_cost, 3),
                     "income_gold": round(income, 3),
                     "share": round(gold_cost / income, 4) if income else 0.0})
    shares = [r["share"] for r in rows]
    spread = max(shares) - min(shares)
    return {"rows": rows, "taper_floor": floor, "spread": round(spread, 6),
            "invariant": spread < 1e-6,
            "within": all(r["share"] <= UPKEEP_INCOME_CEILING for r in rows)}


def _prove_nothing_breaks() -> dict:
    """Hammer one piece far past zero and confirm it is degraded, not gone."""
    state = {"player": {"stamina": 20, "stamina_max": 20, "mana": 30,
                        "mana_max": 30},
             "equipped": {"chest": "training_vest", "offhand": ""}}
    ensure(state)
    for _ in range(400):
        wear_encounter(state, difficulty="BOSS", hits_taken=6, blows_landed=9)
    worn = {piece: integrity(state, piece) for piece in PIECES}
    cond = condition(state)
    quote = repair_quote(state, gold=10_000)
    fixed = repair(state, gold=10_000)
    return {
        "after_400_boss_encounters": worn,
        "floor_respected": all(v >= INTEGRITY_MIN for v in worn.values()),
        "still_equipped": all(piece in state[ARMOUR_STATE_KEY] for piece in PIECES),
        "legendary_untouched": state[ARMOUR_STATE_KEY].get("legendary") == 0,
        "worst_effectiveness": min(r["effectiveness"] for r in cond["pieces"]),
        "never_below_floor": min(r["effectiveness"]
                                 for r in cond["pieces"]) >= DEGRADED_FLOOR,
        "full_restore_gold": quote["gold"],
        "restored": all(integrity(state, p) == INTEGRITY_MAX for p in PIECES),
        "mercy_fired": quote["free_points"] > 0,
        "repair_ok": fixed["ok"],
    }


def _prove_no_dead_end() -> dict:
    """The broke player with a wrecked kit and an unconscious companion.

    Everything they need must still be reachable, and every price they face must
    be zero.
    """
    state = {"player": {"stamina": 1, "stamina_max": 20, "mana": 0,
                        "mana_max": 30},
             "equipped": {}}
    ensure(state)
    for piece in PIECES:
        _set_integrity(state, piece, 0)
    pet_knock(state, "stub", hits=PET_KNOCKS_TO_FAINT)

    gate_stuck = pet_gate(state, "stub", attempts=_free_solution_after())
    gate_fresh = pet_gate(state, "stub", attempts=0)
    warn = alarm(state)
    # Focus comes back even while voided, down to the floor that buys the map.
    voided = after_battle(state, statuses=[{"id": "VOIDED", "turns": 3,
                                            "stacks": 1}])
    state["player"]["mana"] = 0
    plain = after_battle(state, statuses=[])
    healed = heal(state, statuses=[{"id": "POISONED", "turns": 4, "stacks": 2},
                                   {"id": "BURNING", "turns": 2, "stacks": 1}])
    return {
        "kit_at_zero_still_worth": condition(state)["scale"] >= DEGRADED_FLOOR,
        "fainted_pet_silent": gate_stuck["speaks"] is False,
        "worked_solution_still_reachable": gate_stuck["floor"] is True,
        "floor_not_yet_earned_at_zero_attempts": gate_fresh["floor"] is False,
        "alarm_fired": warn["band"] == "DIRE" and warn["heartbeat"],
        "voided_focus_floor": voided["focus"] >= VOIDED_FOCUS_FLOOR,
        "voided_can_buy_first_two_rungs": voided["focus"] >= 3 + 4,
        "plain_focus_full": plain["focus"] == 30,
        "heal_cost": healed["gold_cost"],
        "heal_is_free": healed["gold_cost"] == 0,
        "afflictions_cleared": sorted(healed["cured"]) == ["BURNING", "POISONED"],
        "pet_revived": healed["revived"] == ["stub"],
        "health_full": state["player"]["stamina"] == 20,
        "gold_never_required": True,
    }


def _prove_typing_still_rules() -> dict:
    """Nothing here can win a fight. Durability only ever scales MITIGATION."""
    base = elements.armour_profile("PLATE", points=8)
    state = {"player": {}, "equipped": {}}
    ensure(state)
    for piece in PIECES:
        _set_integrity(state, piece, 0)
    worn = wear_profile(base, state)
    return {
        # A wrecked suit reduces your armour and touches nothing else.
        "points_full": base.points,
        "points_worn": worn.points,
        "mitigation_only_went_down": worn.points <= base.points,
        # It cannot reach the enemy, the player's output, or the clock.
        "no_damage_function": not any(
            name.startswith("damage") or name.endswith("_damage")
            for name in globals()),
        # The worst durability can do is halve armour, which moves the player
        # toward the unarmoured case elements.py has already proved survivable.
        "worst_scale": DEGRADED_FLOOR,
        "elements_worst_case": elements.WORST_CASE_MULTIPLIER,
        "longer_not_unwinnable": DEGRADED_FLOOR > 0.0,
    }


def _prove_alarm_readable() -> dict:
    rows = []
    for hp in range(config.STAMINA_MAX, -1, -1):
        row = alarm_for(hp, config.STAMINA_MAX)
        rows.append({"hp": hp, "band": row["band"], "bpm": row["bpm"],
                     "pulse_hz": row["pulse_hz"],
                     "failures_left": row["failures_left"]})
    bands = [r["band"] for r in rows]
    onset = next(r for r in rows if r["band"] == "CRITICAL")
    return {
        "rows": rows,
        "silent_in_healthy_half": all(
            r["bpm"] == 0 for r in rows if r["hp"] > config.STAMINA_MAX * 0.5),
        "pulse_starts_at_hp": onset["hp"],
        "grace_at_onset": onset["failures_left"],
        # `pulse_hz` is rounded to three places on the way to the client, so the
        # tolerance here is the rounding and not a fudge: the blink and the
        # heartbeat are the same clock to within half a thousandth of a hertz.
        "one_clock": all(
            (r["bpm"] == 0 and r["pulse_hz"] == 0.0)
            or abs(r["pulse_hz"] - r["bpm"] / 60.0) <= 5e-4 for r in rows),
        "monotone": all(
            rows[i]["bpm"] <= rows[i + 1]["bpm"] for i in range(len(rows) - 1)),
        "bands_seen": sorted(set(bands)),
    }


def self_check() -> dict:
    """Every number this module asserts, computed rather than claimed."""
    budget = _budget_table()
    cadence = [_cadence("chestplate", "MEDIUM"), _cadence("shield", "MEDIUM"),
               _cadence("chestplate", "EASY"), _cadence("chestplate", "HARD")]
    quality = _prove_quality_cancels()
    taper = _prove_taper_cancels()
    unbreakable = _prove_nothing_breaks()
    no_dead_end = _prove_no_dead_end()
    typing = _prove_typing_still_rules()
    alarm_rows = _prove_alarm_readable()
    wired = _worst_player_table(wired=True)
    unwired = _worst_player_table(wired=False)

    worst = max(budget, key=lambda r: r["share"])
    failures = []
    if not all(row["within"] for row in budget):
        failures.append("upkeep exceeds a third of income at %s (%.1f%%)"
                        % (worst["difficulty"], worst["share"] * 100))
    # The competent player was never the risk. This is the sweep that includes
    # the player being beaten up on a LEARNING_CLEAR, which is where wear and
    # income point in opposite directions.
    if not wired["within"]:
        failures.append(
            "with gold_earned supplied, upkeep still reaches %.1f%% of income "
            "at %s rank %s on %d hits"
            % (wired["worst_share"] * 100, wired["worst"]["difficulty"],
               wired["worst"]["rank"], wired["worst"]["hits"]))
    if not quality["cancels"]:
        failures.append("rarity does not cancel; gold per encounter varies by "
                        "kit quality")
    if not taper["invariant"]:
        failures.append("the economy taper does not cancel; a player drilling "
                        "one problem pays full wear on tapered income")
    if not taper["within"]:
        failures.append("upkeep exceeds a third of income under the taper")
    for key in ("floor_respected", "still_equipped", "legendary_untouched",
                "never_below_floor", "restored"):
        if not unbreakable[key]:
            failures.append("nothing-breaks guarantee failed: %s" % key)
    for key, value in no_dead_end.items():
        if value is False:
            failures.append("dead end reachable: %s" % key)
    if not typing["mitigation_only_went_down"]:
        failures.append("durability changed something other than mitigation")
    for key in ("silent_in_healthy_half", "one_clock", "monotone"):
        if not alarm_rows[key]:
            failures.append("alarm is not readable: %s" % key)
    if MENDER.free_because.strip() == "":
        failures.append("the healer does not say why she is free")
    # The mirrored constant must not drift from the module that owns it. Only
    # checked when pets is importable, so a sibling pass mid-edit does not turn
    # into a failure report about the town.
    try:
        from . import pets as _pets
    except Exception:
        pets_agree = None
    else:
        pets_agree = (int(_pets.FREE_SOLUTION_AFTER)
                      == FREE_SOLUTION_AFTER_FALLBACK)
        if not pets_agree:
            failures.append(
                "FREE_SOLUTION_AFTER_FALLBACK is %d but pets says %d"
                % (FREE_SOLUTION_AFTER_FALLBACK, _pets.FREE_SOLUTION_AFTER))

    return {
        "module": "upkeep",
        "ok": not failures,
        "failures": failures,
        # Both readings, because the difference between them is the cost of not
        # yet wiring `gold_earned` and the reader is entitled to see it.
        "worst_player_wired": {"worst": wired["worst"],
                               "worst_share": wired["worst_share"],
                               "within": wired["within"]},
        "worst_player_unwired": {"worst": unwired["worst"],
                                 "worst_share": unwired["worst_share"],
                                 "within": unwired["within"]},
        "headline": {
            # One piece — the chestplate, which is always the first to want the
            # smith because it covers most of the player.
            "encounters_until_the_smith_matters":
                cadence[0]["encounters_to_advised"],
            "that_one_piece_costs": cadence[0]["repair_gold"],
            "gold_earned_meanwhile": cadence[0]["gold_earned_meanwhile"],
            "that_one_piece_share_of_income": cadence[0]["share"],
            # The whole kit, which is the number the brief's ceiling is about.
            "whole_kit_share_of_income":
                next(r["share"] for r in budget if r["difficulty"] == "MEDIUM"),
            "worst_difficulty": worst["difficulty"],
            "worst_share": worst["share"],
            "ceiling": round(UPKEEP_INCOME_CEILING, 4),
            "encounters_until_fully_degraded":
                cadence[0]["encounters_to_floor"],
            "healing_cost": 0,
            "focus_refill_cost": 0,
            "pet_revive_cost": 0,
        },
        "budget": budget,
        "cadence": cadence,
        "quality_cancels": quality,
        "taper_cancels": taper,
        "nothing_breaks": unbreakable,
        "no_dead_end": no_dead_end,
        "typing_still_rules": typing,
        "alarm": alarm_rows,
        "loop": LOOP,
        "pets_constant_agrees": pets_agree,
    }


if __name__ == "__main__":       # pragma: no cover
    import json
    print(json.dumps(self_check(), indent=1))
