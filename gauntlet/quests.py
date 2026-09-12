"""The world around the spine: quests you find by looking, not by following.

story.py owns the plot — twenty-one main beats, eleven mentor chains, a rival.
Nothing in here repeats any of it. This module is everything the player trips
over while exploring: a mason who needs a beam count, a levee that keeps
breaking, a courier route nobody has mapped, a jaguar that has been watching
the grove for three chapters.

Four things make this file worth its size.

1. IT IS INERT. Like story.py it holds no state, mutates nothing, and imports
   nothing that could import it back. The engine builds a context from state it
   already owns, asks what is available, and pays what is turned in.

2. AVAILABILITY IS DATA. Every prerequisite is a Gate — a declarative predicate
   the quest log renders as a progress bar. `board()` returns what is offered
   now AND why each locked quest is locked, with the single nearest missing
   requirement named. A log that is a wall of grey text is a log nobody reads.

3. REWARDS COME FROM A TABLE, NOT FROM AUTHORING. A quest declares a tier from
   one to five and which extra kinds of reward it carries. REWARD_TIERS decides
   the XP, the gold and the loot rarity floor, so the curve cannot drift as
   content is added, and `validate()` asserts the table is monotonic.

4. EVERY QUEST LEAVES A MARK. `consequence` is mandatory: a line that giver says
   forever after, and usually something physical — a rebuilt workshop, a new
   shortcut, a pet that will now let itself be found. A quest whose only trace is
   a number going up is a chore.

The rules the tests enforce apply here without exception. No reward supplies an
answer to a coding problem: the reward vocabulary buys focus, routes, reference
cards and places to stand, and nothing else. Nothing in here is gated on time
spent, and no quest can expire, so there is no scarcity to manufacture anxiety
with. Adventure Mode only — none of this exists while the interview clock runs.

Wiring is documented at the bottom, in WIRING.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import config
from . import curriculum
from . import dungeons as dungeonmod
from . import elements
from . import forge
from . import items
from . import pets as petmod
from . import potions
from . import puzzles
from . import skills as skillmod
from . import story
from . import world

# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------
# Eight ways to spend an hour. They differ in what the player DOES, not in the
# colour of the exclamation mark over the giver's head.
#
#   HUNT      clear a named pattern family until it stops being unfamiliar
#   ESCORT    a constrained run — a budget of failures, not a doomsday clock
#   PUZZLE    one of the six puzzle kinds, framed as a problem the world has
#   DELVE     reach a given depth of a dungeon
#   RECOVERY  find a lost thing; gated on a discovery, not on a grind
#   MASTERY   a named standard, stated up front: unaided, at a tier, under time
#   RIDDLE    a question about Python, answered where you are standing
#   RELIEF    do the job an NPC actually has, using the thing you just learned

KINDS = ("HUNT", "ESCORT", "PUZZLE", "DELVE", "RECOVERY", "MASTERY",
         "RIDDLE", "RELIEF")

KIND_BLURB = {
    "HUNT": "Clear a pattern family until the shape of it is obvious.",
    "ESCORT": "A run under a constraint. Failing costs a retry and nothing else.",
    "PUZZLE": "A puzzle the world has, in the shape of one of the six kinds.",
    "DELVE": "Go down. Keep going down.",
    "RECOVERY": "Something is lost. Someone knows roughly where.",
    "MASTERY": "A stated standard, met unaided.",
    "RIDDLE": "A question answered out here, with your mouth, not in an editor.",
    "RELIEF": "Somebody's actual job. Do it for them once.",
}


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
# story.Trigger is reused wholesale so the quest log renders quest prerequisites
# with exactly the same progress-bar code as story beats. Gate adds the handful
# of predicates that only exist out here in the world.

class Gate(story.When):
    """Prerequisite constructors. Inherits region/boss/mastery/level/chapter and
    the rest from story.When; adds what the overworld needs."""

    @staticmethod
    def quest(quest_id: str) -> story.Trigger:
        return story.Trigger("quest_done", quest_id)

    @staticmethod
    def quests(count: int) -> story.Trigger:
        return story.Trigger("quests_done", value=count)

    @staticmethod
    def region_open(region_id: str) -> story.Trigger:
        return story.Trigger("region_open", region_id)

    @staticmethod
    def depth(dungeon_id: str, floors: int) -> story.Trigger:
        return story.Trigger("dungeon_depth", dungeon_id, floors)

    @staticmethod
    def secret(secret_id: str) -> story.Trigger:
        return story.Trigger("secret_found", secret_id)

    @staticmethod
    def pet(discovery_id: str) -> story.Trigger:
        return story.Trigger("pet_found", discovery_id)

    @staticmethod
    def puzzles_cleared(kind: str, count: int) -> story.Trigger:
        return story.Trigger("puzzle_clears", kind, count)

    @staticmethod
    def favour(mentor: str, amount: int) -> story.Trigger:
        return story.Trigger("mentor_favor", mentor, amount)

    @staticmethod
    def shortcut(shortcut_id: str) -> story.Trigger:
        return story.Trigger("shortcut_open", shortcut_id)


# The gate kinds this module answers itself. Anything else falls through to
# story.trigger_progress, which already knows how to phrase it.
LOCAL_GATE_KINDS = ("quest_done", "quests_done", "region_open", "dungeon_depth",
                    "secret_found", "pet_found", "puzzle_clears", "mentor_favor",
                    "shortcut_open")


def need_progress(gate: story.Trigger, ctx: dict) -> dict:
    """current / required / met, phrased for the log. Composites report the
    least-complete part, because that is the thing to go and do next."""
    kind = gate.kind
    if kind == "all":
        parts = [need_progress(p, ctx) for p in gate.parts]
        unmet = [p for p in parts if not p["met"]]
        if unmet:
            return {**unmet[0], "met": False}
        return {**parts[-1], "met": True} if parts else \
            {"label": "", "current": 1, "required": 1, "met": True}
    if kind == "any":
        parts = [need_progress(p, ctx) for p in gate.parts]
        done = [p for p in parts if p["met"]]
        if done:
            return done[0]
        return parts[0] if parts else {"label": "", "current": 0,
                                       "required": 1, "met": False}
    if kind == "quest_done":
        met = gate.key in ctx.get("quests_done", ())
        title = QUEST_BY_ID[gate.key].title if gate.key in QUEST_BY_ID else gate.key
        return {"label": f"Finish {title}", "current": int(met), "required": 1,
                "met": met}
    if kind == "quests_done":
        have = len(ctx.get("quests_done", ()))
        return {"label": "Quests completed", "current": have,
                "required": int(gate.value), "met": have >= gate.value}
    if kind == "region_open":
        region = world.REGION_BY_ID.get(gate.key, {})
        opened = ctx.get("regions_open")
        if opened is None:
            opened = ctx.get("regions_entered", ())
        met = gate.key in opened
        return {"label": f"Open {region.get('name', gate.key)}",
                "current": int(met), "required": 1, "met": met}
    if kind == "dungeon_depth":
        have = int(ctx.get("dungeon_depth", {}).get(gate.key, 0))
        dungeon = DUNGEONS.get(gate.key, {})
        return {"label": f"{dungeon.get('name', gate.key)} depth",
                "current": have, "required": int(gate.value),
                "met": have >= gate.value}
    if kind == "secret_found":
        met = gate.key in ctx.get("secrets_found", ())
        secret = items.SECRET_BY_ID.get(gate.key, {})
        return {"label": f"Find {secret.get('name', gate.key)}",
                "current": int(met), "required": 1, "met": met}
    if kind == "pet_found":
        met = gate.key in ctx.get("pets_found", ())
        pet = PET_DISCOVERIES.get(gate.key, {})
        return {"label": f"Befriend {pet.get('name', gate.key)}",
                "current": int(met), "required": 1, "met": met}
    if kind == "puzzle_clears":
        have = int(ctx.get("puzzle_clears", {}).get(gate.key, 0))
        label = gate.key.replace("_", " ").title()
        return {"label": f"{label} puzzles cleared", "current": have,
                "required": int(gate.value), "met": have >= gate.value}
    if kind == "mentor_favor":
        have = int(ctx.get("favor", {}).get(gate.key, 0))
        mentor = world.MENTORS.get(gate.key, {})
        return {"label": f"Standing with {mentor.get('name', gate.key)}",
                "current": have, "required": int(gate.value),
                "met": have >= gate.value}
    if kind == "shortcut_open":
        met = gate.key in ctx.get("shortcuts", ())
        shortcut = SHORTCUTS.get(gate.key, {})
        return {"label": f"Open {shortcut.get('name', gate.key)}",
                "current": int(met), "required": 1, "met": met}
    return story.trigger_progress(gate, ctx)


def need_met(gate: story.Trigger, ctx: dict) -> bool:
    if gate.kind == "all":
        return all(need_met(p, ctx) for p in gate.parts)
    if gate.kind == "any":
        return any(need_met(p, ctx) for p in gate.parts)
    return need_progress(gate, ctx)["met"]


def describe_need(gate: story.Trigger, ctx: dict) -> str:
    progress = need_progress(gate, ctx)
    if not progress["label"]:
        return ""
    if progress["required"] <= 1:
        return progress["label"]
    return f"{progress['label']} {progress['current']}/{progress['required']}"


# ---------------------------------------------------------------------------
# The material layer
# ---------------------------------------------------------------------------
# The reward tiers below were authored before the forge, the elements and the
# potion bands existed, so they paid in XP, gold and paper. Those are still the
# spine of the curve. What follows is the part of a reward that tells you WHERE
# YOU WERE: the metal that only comes out of this ground, the potion this band
# of the map is allowed to brew, the ward that answers what this place does to
# you, and regalia for the animal walking next to you.
#
# WHERE THE LINE IS, said once and enforced by validate().
#
#   A reward may change what the player CARRIES. Metal, potions, a ward against
#   the local element, boots that answer the local hazard, credit at the local
#   vendor, regalia that makes a companion speak sooner and more often. All of
#   that is preparation and equipment, and equipment has never solved a problem
#   in this game.
#
#   A reward may NEVER change what the player is TOLD about a problem. Not one
#   key in items.EFFECT_LABELS that reads the encounter — every one of them is
#   enumerated in pets.DEPTH_GATED_EFFECTS — may be granted by anything in this
#   file. Depth of help belongs to the companion tier ladder, is paid for in
#   rank, and is sealed in a measured run. `_regalia_grants_no_depth()` asserts
#   this and is called from validate(), so the rule cannot rot quietly.
#
# Nothing here is authored twice. The band of the map, the metal of a region and
# the gear that belongs to a place are all DERIVED from the modules that own
# them, so a quest reward cannot drift away from the world it is paid in.

# -- the band -----------------------------------------------------------------
# How hard a region is, which is what decides the potions it may hand out.
# Derived in story.py and re-exported here, not computed twice. story.py is the
# lower of these two modules in the import graph — quests.py imports it and it
# may never import back — so anything both files need has exactly one home, and
# that is it. See story.RUNG_BAND for the reasoning about why the forge is the
# authority on how hard a place is.
RUNG_BAND = story.RUNG_BAND
band_for = story.band_for
REGION_BAND = story.REGION_BAND


# -- the metal ----------------------------------------------------------------
# forge.REGION_METAL already maps region to metal. A quest may only pay the
# metal of the ground it is standing on, which is the whole of requirement B for
# this reward kind: the ingot in the pack names the place it came out of.

def metal_for(region_id: str) -> str:
    """The metal id this region's quests may pay, or "" for the town."""
    metal = forge.metal_for_region(region_id)
    return metal.id if metal else ""


# How much of it, by tier. An errand does not pay ingots at all — tier 1 is not
# in the grant list for `metal` — and the counts stay small because forge.py
# holds bundles at one unit until ELITE on purpose, and a quest that hands over
# a week of drops would undo that in an afternoon.
METAL_COUNT = {2: 1, 3: 2, 4: 3, 5: 5}


# -- the gear -----------------------------------------------------------------
# Armour and weapons are not minted here. items.CATALOGUE already carries an
# `element` on every elemental piece, and elements.AFFINITY already says what a
# region is. A quest may pay a piece whose element IS the region's affinity —
# the ward that answers what this place does to you, the boots that answer its
# hazard, the weapon its own people carry — because that is the piece that
# tells you where you were.
#
# Neutral regions have no elemental gear and are not made to pretend otherwise.
# They pay the two neutral boots, which is what a neutral region actually has.

def gear_for(region_id: str, slot: str = "") -> list:
    """Item ids whose element belongs to this region. Neutral regions fall back
    to the plain boots, because a place with no weather still has roads."""
    affinity = elements.affinity_for(region_id)
    if affinity == elements.NEUTRAL:
        # elements.BOOTS is the authority on what plain boots exist; worn_boots
        # is the pair you start in and is not a reward.
        neutral = {b.id for b in elements.BOOTS
                   if b.element == elements.NEUTRAL and b.id != "worn_boots"}
        rows = [i for i in items.CATALOGUE if i.id in neutral]
    else:
        rows = [i for i in items.CATALOGUE if i.element == affinity]
    return [i.id for i in rows if not slot or i.slot == slot]


# -- the vendor ---------------------------------------------------------------
# `vendor_credit` is the thinnest shape that does the job: a region and an
# amount. It names no vendor id, no stock list and no price, and it must stay
# that way — economy.py imports this module, so this module can never import it
# back. The region is the join, and economy.grant_credit() reads exactly this.
#
# That thinness was insurance when economy.py did not yet exist. It turned out to
# be the right shape anyway, which is the argument for it: a reward that names
# only what it means can be paid by whatever ends up doing the paying.
#
# The amount is by tier, like every other number in this file that decides how
# much. The _MATERIAL table only says WHETHER a quest pays credit.
VENDOR_CREDIT = {2: 40, 3: 90, 4: 170, 5: 300}


# -- regalia ------------------------------------------------------------------
# The brief asked for quests to reward "upgraded hints". There is exactly one
# way to do that without building a second hint economy that quietly outranks
# the companion tiers, and pets.py names it: bond buys EARLIER and MORE OFTEN,
# and it never buys DEPTH.
#
#   pets.BondRank.threshold_scale   lower = the animal speaks sooner
#   pets.BondRank.interventions     how many times it may speak in one encounter
#
# Regalia moves those two numbers and nothing else. It cannot raise a pet's
# tier, so `pets.covers` is untouched and a tutorial pig in a legendary collar
# is still a tutorial pig looking at a boss it cannot read. It carries no
# items.EFFECT_LABELS key at all, which is the blunt way of guaranteeing it
# carries no DEPTH_GATED_EFFECTS key.
#
# Bond itself is NOT granted. Bond is graded evidence in pets.py and it stays
# that way; regalia is tack, not experience. An animal in a good collar is not
# a better-travelled animal.
#
# ONE PIECE AT A TIME, and that number is not arbitrary: it is pets.ACTIVE_LIMIT.
# One companion walks with you, and it wears one set of tack. Letting seven
# pieces stack would turn the choice of regalia into an inventory-clearing
# exercise and would need a clamp to stop it, and a clamp that silently eats a
# reward is a reward the turn-in panel lied about. A choice is what pets.py says
# this whole system exists to create, so regalia is a choice too.
#
# The two limits below are what a single piece plus the best bond rank in
# pets.py is allowed to reach, and the table is tuned to land exactly on them:
# the deepest piece is 0.82 and Storied bond is 0.5, which multiply to 0.41 —
# just inside the floor. One extra intervention plus Storied's three is four —
# exactly the cap. `_regalia_grants_no_depth` checks every piece against both,
# so a new piece cannot be authored past the budget and rely on a clamp to hide
# it.

# THERE IS A SECOND BODY OF TACK, AND THE TWO ARE BRIDGED RATHER THAN MERGED.
#
# `gauntlet/regalia.py` owns twenty-four COMPANION-keyed objects earned by a
# deed. These seven are REGION-keyed and quest-awarded. They are different
# objects with the same name, and both were authored independently onto the same
# two levers, with — by convergence, not by copying — the same floor (0.40) and
# the same ceiling (4).
#
# Applied SIDE BY SIDE they reach 0.3075 and five interventions, past what both
# files declare legal, because two systems that each clamp their own
# contribution do not add up to a clamped total.
# `regalia.self_check()["bounds"]["stacked_with_quests_regalia"]` measures that
# exact case. The resolution is in `engine.Game.pet_intervention`, which is the
# only path either system reaches combat through: this module's numbers are
# handed to `regalia.schedule(also_scale=, also_interventions=)`, and
# `regalia._clamp` applies ONE floor and ONE ceiling to the total.
#
# `companion_speech()` below therefore clamps for a caller that has ONLY this
# module live. Do not call it alongside regalia.py — call regalia.view() or
# regalia.party_intervention() with the pair folded in, as the engine does.
REGALIA_ACTIVE_LIMIT = petmod.ACTIVE_LIMIT
REGALIA_SCALE_FLOOR = 0.40      # earliest any companion may ever speak
REGALIA_INTERVENTION_CAP = 4    # most times any companion may speak in a fight

REGALIA = {
    "field_collar": {
        "name": "Fieldwork Collar", "region": "fields_of_syntax",
        "threshold_scale": 0.92, "interventions": 0,
        "blurb": "Speaks a little sooner.",
        "tell": "Plain leather, a bog-iron ring, and the ring is the whole of "
                "the craftsmanship. It was made for a working animal by "
                "somebody who had one.",
    },
    "keyed_bell": {
        "name": "Keyed Bell", "region": "hashmap_highlands",
        "threshold_scale": 0.90, "interventions": 0,
        "blurb": "Speaks sooner.",
        "tell": "One note, and it is the note of the alcove you are standing "
                "in front of. The animal hears it before you do.",
    },
    "sealed_muzzle": {
        "name": "Sealed Muzzle", "region": "sliding_window_marsh",
        "threshold_scale": 0.95, "interventions": 1,
        "blurb": "Speaks once more per encounter, and slightly sooner.",
        "tell": "It is not a muzzle. It is a filter, and it means the animal "
                "can keep talking in air that would otherwise stop it.",
    },
    "lantern_harness": {
        "name": "Lantern Harness", "region": "recursive_forest",
        "threshold_scale": 0.88, "interventions": 0,
        "blurb": "Speaks considerably sooner.",
        "tell": "A light at the animal's shoulder rather than yours. It sees "
                "the next clearing a beat before you walk into it.",
    },
    "lattice_tack": {
        "name": "Lattice Tack", "region": "graph_wastes",
        "threshold_scale": 0.95, "interventions": 1,
        "blurb": "Speaks once more per encounter, and slightly sooner.",
        "tell": "Braided the way the roads are braided. It drags, it earths, "
                "and the animal stops flinching at the storms.",
    },
    "counted_barding": {
        "name": "Counted Barding", "region": "dp_ruins",
        "threshold_scale": 0.85, "interventions": 1,
        "blurb": "Speaks once more per encounter, and much sooner.",
        "tell": "Every plate is a tile that was already solved. The animal "
                "walks on ground it has been over, and it shows.",
    },
    "unlabelled_collar": {
        "name": "Unlabelled Collar", "region": "null_kings_castle",
        "threshold_scale": 0.82, "interventions": 1,
        "blurb": "Speaks once more per encounter, and far sooner.",
        "tell": "Nullsteel with the maker's mark struck off, like everything "
                "else down there. The animal wears it anyway.",
    },
}


# -- what a rebuilt place then sells ------------------------------------------
# Requirement: a quest's mark on the world and a quest's reward should be the
# same fact where they can be. TOWN_UPGRADES already promises a building that
# stays rebuilt; `stocks` is what that building then has on its shelves, so
# "the levee holds" and "Wade now carries the good antidote" are one sentence
# rather than two systems.
#
# Two things may be stocked and nothing else:
#
#   "potions": [ids]  the potions ONE BAND DEEPER than the region itself. Not a
#                     new potion and not a better price — the same catalogue,
#                     carried by somebody who could not carry it before. That is
#                     the honest meaning of "this place got better".
#   "metal":   id     the region's own metal, for a rebuilt forge or works. The
#                     brief's own example, paid literally.
#
# The band rule is not relaxed here, it is spent. A region hands out potions at
# its own band; a region whose shop you rebuilt SELLS one band deeper. The quest
# reward and the shelf stay different numbers, and the difference is the work.
#
# validate() checks all of it: a stocked potion must be unavailable at the
# region's own band and available one band up (so it is genuinely an upgrade and
# not a restatement), and a stocked metal must be that region's metal.
#
# economy.py owns shelves and imports this module, so this is data it reads. It
# is deliberately not a price, a count or a restock rate — those are the
# economy's business and naming them here would be this file guessing.


def next_band(region_id: str) -> str:
    """The band one step deeper than this region's own. The deepest band is its
    own successor, so the Castle has nothing to upgrade into rather than an
    index error."""
    order = potions.TIER_ORDER
    index = order.index(REGION_BAND[region_id])
    return order[min(index + 1, len(order) - 1)]


def upgrade_stock(state: dict, region_id: str = "") -> dict:
    """Everything the player's rebuilt buildings have put on local shelves.
    region_id -> {"potions": [...], "metal": id}. Empty until something is built,
    which is the point."""
    out: dict = {}
    for upgrade in built_upgrades(state, region_id):
        stocks = upgrade.get("stocks")
        if not stocks:
            continue
        room = out.setdefault(upgrade["region"], {"potions": [], "metal": ""})
        for pid in stocks.get("potions", ()):
            if pid not in room["potions"]:
                room["potions"].append(pid)
        if stocks.get("metal"):
            room["metal"] = stocks["metal"]
    return out


# ---------------------------------------------------------------------------
# The reward table
# ---------------------------------------------------------------------------
# A tier decides XP, gold and the rarity floor of whatever drops. It also
# decides which KINDS of reward a quest at that tier is permitted to carry,
# because variety is what stops a reward feeling like a payout — a shortcut and
# a set piece are both "tier four" and they land completely differently.
#
# `grants` is nested by construction: each tier may award everything the tier
# below may, plus its own new kind. validate() asserts both that nesting and the
# monotonic XP/gold/rarity curve, so this stays true as content is added.
#
# Reward vocabulary, and nothing else:
#
#   xp            int   paid by the engine on turn-in
#   gold          int
#   rarity_floor  str   items.RARITIES key — the worst roll the drop may give
#   card          str   story.GRIMOIRE_CARDS id — a revision card, not a hint
#   codex         str   story.CODEX id — lore and reference
#   favor         dict  {"mentor": world.MENTORS id, "amount": int}
#   consumable    dict  {"id": items.CONSUMABLES key, "count": int}
#   shortcut      str   SHORTCUTS id — a road that stays open
#   incantation   str   INCANTATION_GRANTS id — a combat spell, resolved lazily
#   title         str   an honorific, free text, stored beside the story titles
#   town_upgrade  str   TOWN_UPGRADES id — a building that stays rebuilt
#   pet           str   PET_DISCOVERIES id — the CONDITION, not the animal
#   set_item      str   items.CATALOGUE id belonging to an items.SETS set
#
# and the material layer above, which is the part of a reward that names a place:
#
#   metal         dict  {"id": forge.METAL_BY_ID key, "count": int} — and the id
#                       must be the metal of the quest's own region
#   potion        dict  {"id": potions.BY_ID key, "count": int} — and the potion
#                       must be one this region's band is allowed to brew
#   gear          str   items.BY_ID key whose element is the region's affinity —
#                       a ward, boots, or the weapon that place carries
#   regalia       str   REGALIA id — tack that makes a companion speak sooner and
#                       more often, and that is the whole of what it may do
#   vendor_credit dict  {"region": world.REGION_BY_ID key, "amount": int}
#
# Three of those need their pedantry stated out loud. A `pet` reward grants the
# knowledge of where and how an animal can be found — the player still has to go
# and do it, which is the only reason a hidden pet is worth finding. A card is a
# revision card: it names the shape of a question and never its answer. And
# `regalia` is the brief's "upgraded hints", built the only safe way: it moves
# pets.BondRank.threshold_scale and .interventions, so the companion speaks
# EARLIER and MORE OFTEN, and it cannot touch the tier that decides how DEEP the
# help goes. See the material layer above, and _regalia_grants_no_depth().

REWARD_KEYS = ("xp", "gold", "rarity_floor", "card", "codex", "favor",
               "consumable", "shortcut", "incantation", "title", "town_upgrade",
               "pet", "set_item", "metal", "potion", "gear", "regalia",
               "vendor_credit")

# Nested by construction, as before. The material kinds enter where they stop
# being absurd: a potion is a reasonable thing to be handed for an hour's work,
# an ingot is not, and a ward against an entire element is a thing you are given
# after a place has genuinely changed because of you.
_T1 = ("card", "codex", "favor", "consumable", "potion")
_T2 = _T1 + ("shortcut", "incantation", "metal", "vendor_credit")
_T3 = _T2 + ("title", "town_upgrade", "pet", "gear", "regalia")
_T4 = _T3 + ("set_item",)

REWARD_TIERS = {
    1: {"name": "Errand", "xp": 45, "gold": 30, "rarity_floor": "COMMON",
        "blurb": "An hour. Something small stops being broken.",
        "grants": _T1},
    2: {"name": "Undertaking", "xp": 95, "gold": 65, "rarity_floor": "UNCOMMON",
        "blurb": "A session. Somebody who was struggling stops struggling.",
        "grants": _T2},
    3: {"name": "Charge", "xp": 180, "gold": 130, "rarity_floor": "RARE",
        "blurb": "Several sessions. A place on the map works differently after.",
        "grants": _T3},
    4: {"name": "Reckoning", "xp": 320, "gold": 240, "rarity_floor": "EPIC",
        "blurb": "A chapter of work. People tell the story of it afterwards.",
        "grants": _T4},
    5: {"name": "Legend", "xp": 540, "gold": 420, "rarity_floor": "LEGENDARY",
        "blurb": "The kind of thing the Realms were supposed to have lost.",
        "grants": _T4},
}


def reward_for(tier: int, extras: dict | None = None) -> dict:
    """The full reward for a quest. Base pay is never authored per quest — it is
    read from the table, so the curve cannot drift one generous quest at a time."""
    row = REWARD_TIERS[tier]
    reward = {"tier": tier, "xp": row["xp"], "gold": row["gold"],
              "rarity_floor": row["rarity_floor"]}
    # Copied one level down, not shared. Several extras are dicts — metal,
    # potion, vendor_credit, consumable, favor — and handing the caller the
    # table's own dict would mean an engine that decrements a count while paying
    # it out silently edits the quest for the rest of the process. Rule 1 of this
    # module is that it mutates nothing; that has to survive contact with a
    # caller that does.
    for key, value in (extras or {}).items():
        reward[key] = dict(value) if isinstance(value, dict) else value
    return reward


def reward_summary(reward: dict) -> list:
    """Human lines for the turn-in panel. Names what was given, never why."""
    out = [f"{reward['xp']} XP", f"{reward['gold']} gold"]
    floor = reward.get("rarity_floor")
    if floor and floor != "COMMON":
        out.append(f"Spoils, {floor.title()} or better")
    card = story.GRIMOIRE_CARDS.get(reward.get("card", ""))
    if card:
        out.append(f"Grimoire card: {card['name']}")
    entry = story.CODEX.get(reward.get("codex", ""))
    if entry:
        out.append(f"Codex: {entry['title']}")
    if reward.get("title"):
        out.append(f"Title: {reward['title']}")
    incantation = INCANTATION_GRANTS.get(reward.get("incantation", ""))
    if incantation:
        out.append(f"Incantation: {incantation['name']} — {incantation['form']}")
    shortcut = SHORTCUTS.get(reward.get("shortcut", ""))
    if shortcut:
        out.append(f"Shortcut open: {shortcut['name']}")
    upgrade = TOWN_UPGRADES.get(reward.get("town_upgrade", ""))
    if upgrade:
        out.append(f"{upgrade['name']} — {upgrade['effect']}")
    pet = PET_DISCOVERIES.get(reward.get("pet", ""))
    if pet:
        out.append(f"You now know how to find {pet['name']}")
    if reward.get("set_item"):
        item = items.BY_ID.get(reward["set_item"])
        out.append(f"Set piece: {item.name}" if item else
                   f"Set piece: {reward['set_item']}")
    consumable = reward.get("consumable")
    if consumable:
        row = items.CONSUMABLES.get(consumable["id"], {})
        name = row.get("name", consumable["id"])
        out.append(f"{name} x{consumable['count']}")
    if reward.get("favor"):
        mentor = world.MENTORS.get(reward["favor"]["mentor"], {})
        out.append(f"{mentor.get('name', 'They')} remembers this")
    metal = reward.get("metal")
    if metal:
        row = forge.METAL_BY_ID.get(metal["id"])
        name = row.name if row else metal["id"]
        out.append(f"{name} x{metal['count']}")
    potion = reward.get("potion")
    if potion:
        row = potions.BY_ID.get(potion["id"])
        name = row.name if row else potion["id"]
        out.append(f"{name} x{potion['count']}")
    gear = reward.get("gear")
    if gear:
        item = items.BY_ID.get(gear)
        if item:
            element = item.element or elements.NEUTRAL
            out.append(f"{item.name}"
                       + (f" — warded, {element.title()}"
                          if element != elements.NEUTRAL else ""))
        else:
            out.append(f"Gear: {gear}")
    regalia = REGALIA.get(reward.get("regalia", ""))
    if regalia:
        out.append(f"Regalia: {regalia['name']} — {regalia['blurb']}")
    credit = reward.get("vendor_credit")
    if credit:
        region = world.REGION_BY_ID.get(credit["region"], {})
        out.append(f"{credit['amount']} credit with the trader at "
                   f"{region.get('name', credit['region'])}")
    return out


# ---------------------------------------------------------------------------
# The people
# ---------------------------------------------------------------------------
# Nobody here is a quest dispenser. Each has a job, and the job is why they are
# asking. `line` is what they say before you have done anything for them; every
# quest they give overwrites it with something that acknowledges what happened.

NPCS = {
    "odile": {"name": "Odile Barrow", "role": "mason", "region": "python_village",
              "sprite": "villager",
              "line": "Half this village is scaffolding holding up other "
                      "scaffolding. Mind where you lean."},
    "tamsin": {"name": "Tamsin Reed", "role": "seed-keeper",
               "region": "python_village", "sprite": "villager",
               "line": "Seeds do not care whether you feel ready. They come up "
                       "in March regardless."},
    "pel": {"name": "Pel", "role": "an eight-year-old with a stick",
            "region": "python_village", "sprite": "child",
            "line": "I am not lost. I am doing a route."},
    "harrow": {"name": "Warden Harrow", "role": "field warden",
               "region": "fields_of_syntax", "sprite": "warden",
               "line": "Statements grow wrong out here. They grow anyway."},
    "nils": {"name": "Nils Fenwick", "role": "fence-mender",
             "region": "fields_of_syntax", "sprite": "villager",
             "line": "A fence with one gap is not a fence. It is a shape."},
    "vela": {"name": "Vela Coss", "role": "tollkeeper of the vaults",
             "region": "hashmap_highlands", "sprite": "clerk",
             "line": "One key. One vault. If you are carrying two keys for the "
                     "same door, one of them is a lie."},
    "brant": {"name": "Brant Ulme", "role": "vault-warden",
              "region": "hashmap_highlands", "sprite": "warden",
              "line": "I have opened nine thousand vaults and never once had to "
                      "try the wrong one twice."},
    "quill": {"name": "Quill", "role": "namer of things",
              "region": "stringwood_labyrinth", "sprite": "scribe",
              "line": "Two words with the same letters are the same word wearing "
                      "a different coat. The wood does not care about coats."},
    "moss": {"name": "Moss Arden", "role": "forager",
             "region": "stringwood_labyrinth", "sprite": "forager",
             "line": "I navigate by spelling. It sounds mad until you try the "
                     "alternative."},
    "dorn": {"name": "Quartermaster Dorn", "role": "keeper of the alcoves",
             "region": "array_caverns", "sprite": "quartermaster",
             "line": "The first alcove is zero. The last is one less than the "
                     "count. Everything that has ever gone wrong down here went "
                     "wrong on one of those two facts."},
    "esk": {"name": "Esk", "role": "lamp-runner", "region": "array_caverns",
            "sprite": "runner",
            "line": "I run the lamps end to end. Twice a shift. I know exactly "
                    "how many there are and I still count them."},
    "fenn": {"name": "Fenn Ilder", "role": "levee-keeper",
             "region": "sliding_window_marsh", "sprite": "keeper",
             "line": "The water does not restart when the levee breaks. Neither "
                     "should you."},
    "sable": {"name": "Sable", "role": "ferrier of the reedways",
              "region": "sliding_window_marsh", "sprite": "ferrier",
              "line": "Wide crossing, narrow crossing. Same river. Depends what "
                      "you are carrying."},
    "ondra": {"name": "Ondra Vasc", "role": "convoy master",
              "region": "twin_pointer_pass", "sprite": "captain",
              "line": "Two carts. One from each end. They meet in the middle or "
                      "somebody has miscounted."},
    "kell": {"name": "Kell", "role": "bridge-warden",
             "region": "twin_pointer_pass", "sprite": "warden",
             "line": "The bridge is as strong as its shorter post. Not its taller "
                     "one. People argue with me about this."},
    "greave": {"name": "Greave", "role": "lift engineer",
               "region": "stack_queue_mines", "sprite": "engineer",
               "line": "Carts come off the top. The lift takes the oldest. Mix "
                       "those up and somebody gets buried."},
    "pitch": {"name": "Pitch", "role": "cart-boss", "region": "stack_queue_mines",
              "sprite": "miner",
              "line": "Everything down here nests. Props, braces, brackets, "
                      "arguments. It all closes in the order it opened."},
    "lorne": {"name": "Archivist Lorne", "role": "keeper of the floor plans",
              "region": "matrix_citadel", "sprite": "scholar",
              "line": "The citadel turns. The plans do not. I reconcile them. It "
                      "is less glamorous than it sounds."},
    "ives": {"name": "Drillmaster Ives", "role": "drill sergeant of the citadel",
             "region": "matrix_citadel", "sprite": "soldier",
             "line": "Rows, then columns. Always that order. The day you do it "
                     "the other way round you will know, because nothing will fit."},
    "halla": {"name": "Halla Vane", "role": "forester",
              "region": "recursive_forest", "sprite": "forester",
              "line": "Every clearing has a smaller forest in it. You come back "
                      "out carrying whatever the small one found."},
    "bram": {"name": "Bram", "role": "keeper of the inner grove",
             "region": "recursive_forest", "sprite": "druid",
             "line": "The way out is the way in, unwound. Say the stopping "
                     "condition aloud before you go down."},
    "wren": {"name": "Wren", "role": "rookery keeper",
             "region": "binary_tree_canopy", "sprite": "keeper",
             "line": "Two branches. Never three, never one rejoining. The canopy "
                     "is very strict about this and I like it here."},
    "alder": {"name": "Alder", "role": "climber", "region": "binary_tree_canopy",
              "sprite": "climber",
              "line": "Left, root, right. That order and no other, or the nests "
                      "come out in the wrong sequence and the birds complain."},
    "corvin": {"name": "Corvin Sedge", "role": "courier", "region": "graph_wastes",
               "sprite": "messenger",
               "line": "Every ruin connects to four others. Only one of those "
                       "four is on the way to anywhere."},
    "mira": {"name": "Mira", "role": "waystation cook", "region": "graph_wastes",
             "sprite": "cook",
             "line": "I feed whoever arrives. Lately that is nobody, because the "
                     "roads all go in circles."},
    "tolliver": {"name": "Tolliver Ash", "role": "tallykeeper of the ruins",
                 "region": "dp_ruins", "sprite": "scholar",
                 "line": "Someone already solved this. Probably you. Probably "
                         "twice. That is the whole tragedy of this place."},
    "nima": {"name": "Nima", "role": "surveyor", "region": "dp_ruins",
             "sprite": "surveyor",
             "line": "I light the tiles I have measured so I never measure them "
                     "again. It took me four years to think of that."},
    "garrick": {"name": "Garrick", "role": "forge apprentice",
                "region": "debugging_dungeon", "sprite": "apprentice",
                "line": "The Armorer says read the crack. I have been reading "
                        "this crack for two days."},
    "ilsa": {"name": "Warden Ilsa", "role": "keeper of the cells",
             "region": "debugging_dungeon", "sprite": "warden",
             "line": "Every program in these cells worked once, on somebody's "
                     "machine, for one input."},
    "ember": {"name": "Ember", "role": "lamplighter of the tower",
              "region": "complexity_tower", "sprite": "lamplighter",
              "line": "Each floor has twice the lamps of the one below. I have "
                      "opinions about the architect."},
    "stave": {"name": "Stave", "role": "tower porter",
              "region": "complexity_tower", "sprite": "porter",
              "line": "I carry loads up. Ask me what a trip costs and I will ask "
                      "you how many floors, not how heavy."},
    "junia": {"name": "Junia", "role": "ticket clerk of the Coliseum",
              "region": "coding_coliseum", "sprite": "clerk",
              "line": "The sand does not care how much you know. It cares how "
                      "fast you stop deciding."},
    "bosk": {"name": "Bosk", "role": "sand-raker", "region": "coding_coliseum",
             "sprite": "raker",
             "line": "I rake out the footprints between bouts. You would be "
                     "amazed what the footprints say."},
    "steward": {"name": "The Steward", "role": "keeper of an empty castle",
                "region": "null_kings_castle", "sprite": "steward",
                "line": "There are no signs. There were never any signs. The "
                        "King removed the labels, not the rooms."},
}


def speaker_name(giver: str) -> str:
    """Givers are NPCs out here, but mentors give a few of these themselves."""
    if giver in NPCS:
        return NPCS[giver]["name"]
    mentor = world.MENTORS.get(giver)
    return mentor["name"] if mentor else giver.upper()


# ---------------------------------------------------------------------------
# Places and things the quests point at
# ---------------------------------------------------------------------------
# The dungeon generator owns layouts, monsters, treasure AND names. A DELVE
# quest still has to say where it is sending you and how far down, so this is a
# view onto `dungeons.DUNGEONS` rather than a second list of places: an id, a
# region, a floor count and the generator's own blurb. `floors` is the deepest
# floor `dungeons.generate` guarantees, and therefore the deepest a quest here is
# allowed to demand — `validate()` enforces exactly that.

DUNGEONS = {
    plan.id: {"name": plan.name, "region": plan.region, "floors": plan.floors,
              "blurb": plan.blurb}
    for plan in dungeonmod.DUNGEONS
}


# The hidden animals. A quest never hands over a pet — it hands over the
# CONDITION, which is the part that was actually lost. The animal is still out
# there, still where `pets` says it is, and still has to be earned by the deed
# `pets` names. That is why this is a view over `pets.PETS` and not a second
# opinion about where the jaguar lives: two tables would drift, and the one the
# player is told would be the wrong one.
#
# What a companion does in a fight belongs to the pet system, and the constraint
# lives there too: a pet nudges toward the SHAPE of a question — the same tier of
# help a hint spell gives, at the same cost — and never toward the answer.
# Nothing that walks beside you may write your code.

PET_DISCOVERIES = {
    f"pet_{pet.id}": {
        "pet": pet.id,
        "name": f"{pet.name} the {pet.species}",
        "region": pet.discovery.region,
        "hint": pet.discovery.where,
        "condition": pet.discovery.how,
        "offers": pet.tagline,
    }
    for pet in petmod.PETS
}


# Roads that stay open once opened. A shortcut is the purest side-quest reward
# in an open world: it costs the player nothing to use and it silently repays
# the hour they spent, every session, forever.

SHORTCUTS = {
    "village_causeway": {"name": "The Barrow Causeway", "from": "python_village",
                         "to": "fields_of_syntax",
                         "line": "Odile's causeway runs straight out of the "
                                 "village now. No more walking the long way "
                                 "round the mire."},
    "highland_tramway": {"name": "The Highland Tramway", "from": "fields_of_syntax",
                         "to": "hashmap_highlands",
                         "line": "The hand-tram runs the ridge again. One pull, "
                                 "one arrival."},
    "cavern_lift": {"name": "The Quartermaster's Lift", "from": "array_caverns",
                    "to": "stack_queue_mines",
                    "line": "Dorn's lift drops straight through to the mines, "
                            "and it is the only thing down here that is indexed "
                            "from one, as a joke."},
    "levee_walk": {"name": "The Levee Walk", "from": "sliding_window_marsh",
                   "to": "twin_pointer_pass",
                   "line": "The repaired levee is a road now, which Fenn "
                           "maintains was always the plan."},
    "canopy_ropeway": {"name": "The Canopy Ropeway", "from": "recursive_forest",
                       "to": "binary_tree_canopy",
                       "line": "A rope from the inner grove to the first fork. "
                               "It only goes up, which Wren says is correct."},
    "relay_road": {"name": "The Relay Road", "from": "graph_wastes",
                   "to": "matrix_citadel",
                   "line": "Corvin's road is the only route through the Wastes "
                           "that is shortest rather than merely possible."},
    "ruins_stair": {"name": "The Lit Stair", "from": "dp_ruins",
                    "to": "complexity_tower",
                    "line": "Every step of this stair is already solved and lit. "
                            "You will never pay for it twice."},
    "forge_tunnel": {"name": "The Forge Tunnel", "from": "debugging_dungeon",
                     "to": "python_village",
                     "line": "The Armorer's tunnel comes up behind the village "
                             "forge. Warm the whole way."},
    "arena_undergate": {"name": "The Undergate", "from": "coding_coliseum",
                        "to": "null_kings_castle",
                        "line": "The gate under the arena opens onto the castle "
                                "road. Nobody uses it twice."},
}

# Buildings that stay rebuilt. The effects are small, permanent and economic —
# they buy focus, standing and time, which is the only currency this game is
# allowed to pay in. Keys come from items.EFFECT_LABELS.

TOWN_UPGRADES = {
    "village_workshop": {"name": "The Village Workshop", "region": "python_village",
                         "effect": "Armour repairs here mend more per session.",
                         "effects": {"armor_repair": 0.15},
                        "stocks": {"potions": ["focus_minor"]},
                         "line": "Odile's workshop has a roof, a bench and a "
                                 "queue outside it most mornings."},
    "village_well": {"name": "The Deep Well", "region": "python_village",
                     "effect": "Resting in the village restores more focus.",
                     "effects": {"mana_regen": 2},
                     "line": "The well runs clear. Tamsin has stopped rationing."},
    "fields_granary": {"name": "The Granary", "region": "fields_of_syntax",
                       "effect": "Rations for the road: more stamina.",
                       "effects": {"stamina_max": 2},
                      "stocks": {"potions": ["health_small"]},
                       "line": "The granary is full and the warden has stopped "
                               "counting it twice a day."},
    "ledger_house": {"name": "The Ledger House", "region": "hashmap_highlands",
                     "effect": "Spoils from the Highlands roll better.",
                     "effects": {"loot_luck": 0.1},
                    "stocks": {"potions": ["antidote_small"]},
                     "line": "Vela's ledger house is open. Every vault in the "
                             "Highlands is written down exactly once."},
    "marsh_levee": {"name": "The Mended Levee", "region": "sliding_window_marsh",
                    "effect": "The marsh no longer drains your stamina.",
                    "effects": {"stamina_max": 3},
                   "stocks": {"potions": ["antidote_medium"]},
                    "line": "The levee holds. Fenn sleeps through the night for "
                            "the first time in two years."},
    "liftworks": {"name": "The Liftworks", "region": "stack_queue_mines",
                  "effect": "The mines run both ways: spells cost less here.",
                  "effects": {"hint_discount": 0.1},
                 "stocks": {"potions": ["health_medium"], "metal": "faultsteel"},
                  "line": "Greave's liftworks turn all day. Nothing waits at the "
                          "bottom of a shaft any more."},
    "waystation": {"name": "Mira's Waystation", "region": "graph_wastes",
                   "effect": "A hot meal in the Wastes: more focus.",
                   "effects": {"mana_max": 6},
                  "stocks": {"potions": ["health_hefty", "focus_hefty"]},
                   "line": "The waystation has smoke coming out of it, and "
                           "couriers in it, and a menu of one thing."},
    "annealing_room": {"name": "The Annealing Room",
                       "region": "debugging_dungeon",
                       "effect": "Repairs here mend more, and hold.",
                       "effects": {"armor_repair": 0.2},
                      "stocks": {"potions": ["health_medium"], "metal": "faultsteel"},
                       "line": "Garrick runs the annealing room now. He reads "
                               "every crack aloud before he touches it."},
    "coliseum_stands": {"name": "The Restored Stands",
                        "region": "coding_coliseum",
                        "effect": "A crowd that has seen you before: more grace "
                                  "on the clock.",
                        "effects": {"rank_grace": 0.08},
                        "line": "The stands are full. Junia sells tickets to "
                                "people who come specifically to watch you."},
}

# Spells the combat system owns. These are incantation.py's own ids, copied
# here with their names so the turn-in panel can be rendered without importing
# a combat module into a content module. validate() resolves them against
# incantation.BY_ID if that file is present and says nothing if it is not, so
# neither file can block the other.

INCANTATION_GRANTS = {
    "numbering": {"name": "NUMBERING", "form": "for i, item in enumerate(seq):",
                  "blurb": "Strikes an index and its value in the same breath."},
    "tally": {"name": "TALLY", "form": "book[key] = book.get(key, 0) + 1",
              "blurb": "Counts what it has seen without asking twice."},
    "distill": {"name": "DISTILL", "form": "out = set(seq)",
                "blurb": "Collapses every duplicate to one."},
    "sever": {"name": "SEVER", "form": "part = seq[start:stop]",
              "blurb": "Takes a contiguous piece and leaves the rest standing."},
    "converge": {"name": "CONVERGE", "form": "while left < right:",
                 "blurb": "Two hands, from either end, neither turning back."},
    "dequeue": {"name": "DEQUEUE", "form": "node = frontier.popleft()",
                "blurb": "Takes the oldest waiting thing, at no cost."},
    "cell": {"name": "CELL", "form": "value = grid[r][c]",
             "blurb": "Reads a position out of a turning floor."},
    "halve": {"name": "HALVE", "form": "mid = (left + right) // 2",
              "blurb": "Discards half of what remains with every strike."},
    "enshrine": {"name": "ENSHRINE", "form": "memo[key] = result",
                 "blurb": "The second identical blow costs nothing."},
    "weigh": {"name": "WEIGH", "form": "out = sorted(seq, key=keyfn)",
              "blurb": "Rearranges a foe into an order it cannot hide in."},
}


# ---------------------------------------------------------------------------
# The quest shape
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Quest:
    id: str
    kind: str
    title: str
    region: str
    giver: str
    tier: int
    premise: str                 # one line in the log, the giver's problem
    setup: tuple                 # two to five lines, in that character's voice
    turn_in: str                 # what they say when it is done
    objective: dict              # kind-specific, evaluable data
    consequence: dict            # what stays changed afterwards
    requires: tuple = ()         # Gates, all of which must be met
    extras: dict = field(default_factory=dict)   # reward beyond xp/gold/rarity
    chain: str = ""              # set by _link, never authored on the quest

    @property
    def reward(self) -> dict:
        return reward_for(self.tier, self.extras)

    @property
    def tier_name(self) -> str:
        return REWARD_TIERS[self.tier]["name"]


@dataclass(frozen=True)
class QuestChain:
    id: str
    title: str
    region: str
    giver: str
    premise: str
    steps: tuple                 # quest ids, in order
    epilogue: str = ""           # said once the last step is turned in


# ---------------------------------------------------------------------------
# The quests
# ---------------------------------------------------------------------------
# `objective` is evaluable data, and its shape is fixed by `kind`. Every one of
# them carries a "text" the log can print verbatim, because a quest the player
# has to interpret is a quest they will not start.
#
#   HUNT      {"family"|"pattern", "count", "unaided"?}
#   ESCORT    {"count", "failures_allowed", "seconds"?, "recover"}
#   PUZZLE    {"puzzle", "count", "family"?}
#   DELVE     {"dungeon", "depth"}
#   RECOVERY  {"lost", "condition", "found_in"?}
#   MASTERY   {"skill", "difficulty", "count", "unaided", "under_target"}
#   RIDDLE    {"question", "answers", "skill", "explain"}
#   RELIEF    {"task", "family"|"pattern", "count"}
#
# ESCORT carries `recover` and it is never optional. The player this game was
# built for freezes under a clock. A run with a budget of failures is a clock
# that teaches; a run that ends the quest on one mistake is a clock that
# confirms what he already believes about himself.

_QUESTS = [

    # -- Python Village ----------------------------------------------------
    Quest(
        id="village_beam_count", kind="RELIEF", title="What Is Actually Broken",
        region="python_village", giver="odile", tier=1,
        premise="Odile has to report which beams are cracked and she has been "
                "counting them on her fingers.",
        setup=("There are two hundred beams in the north row and I have counted "
               "them four times and got four numbers.",
               "I do not need you to fix the beams. I need a tally. One pass, "
               "every beam, a mark against each kind of crack.",
               "You look like someone who has done this with a piece of paper. "
               "Do it without the paper."),
        turn_in="Four kinds of crack, and the count of each. That took you one "
                "pass. It took me a week and I got it wrong.",
        objective={"task": "Tally the cracked beams by kind",
                   "family": "counting", "count": 3,
                   "text": "Clear three counting encounters."},
        consequence={"npc_line": "The tally you did is nailed to the post by the "
                                 "gate. People add to it. Nobody recounts it.",
                     "world": "A tally board stands at the village gate, and the "
                              "north row is scaffolded properly."},
        extras={"card": "card_seen_before",
                "favor": {"mentor": "byte", "amount": 2}},
    ),
    Quest(
        id="village_mortar_weeds", kind="HUNT", title="Weeds in the Mortar",
        region="python_village", giver="odile", tier=1,
        premise="Malformed statements have rooted in the mortar of every wall "
                "Odile has ever laid.",
        setup=("The wall is sound. What is growing out of it is not.",
               "Half-spoken statements, the kind that almost parse. They take "
               "hold in the gaps and then the gaps get wider.",
               "Clear them out of the north wall and I will show you the trick "
               "for keeping them out, which is simply laying it right."),
        turn_in="North wall is clean. You did not once stop to ask whether a "
                "line was allowed. That is the whole difference.",
        objective={"family": "python_basics", "count": 4,
                   "text": "Clear four Python fluency encounters."},
        consequence={"npc_line": "North wall has not sprouted since you went "
                                 "over it. I point it out to people.",
                     "world": "The north wall stands clean, and the scaffolding "
                              "around it comes down."},
        extras={"consumable": {"id": "focus_elixir", "count": 2}},
    ),
    Quest(
        id="village_doorframe", kind="PUZZLE", title="The Doorframe Problem",
        region="python_village", giver="odile", tier=2,
        premise="The meeting hall door has been in pieces on the floor for a "
                "year because nobody can agree what order it goes in.",
        setup=("Every piece of that door is cut correctly. I cut them.",
               "Assembling it is not a cutting problem. It is an order problem, "
               "and I am a mason, not whatever you are.",
               "Lay the pieces out. Get the order right and the depth right. "
               "In this village, depth is meaning."),
        turn_in="It hangs. It swings both ways. A year of firewood arguments "
                "ended by somebody putting the lines in the right sequence.",
        objective={"puzzle": "RUNE_ASSEMBLY", "count": 2,
                   "text": "Assemble two spells from shuffled runes."},
        consequence={"npc_line": "The hall door works. I am aware that is a low "
                                 "bar for a year of my life.",
                     "world": "The meeting hall has a door, and the village "
                              "starts holding meetings behind it."},
        extras={"card": "card_reflex",
                "favor": {"mentor": "byte", "amount": 3}},
    ),
    Quest(
        id="village_raising", kind="ESCORT", title="The Raising",
        region="python_village", giver="odile", tier=3,
        premise="The workshop roof beam goes up in one lift, with the whole "
                "village holding it, or it does not go up at all.",
        setup=("Twelve people on ropes and one beam. Once it leaves the ground "
               "we do not put it down.",
               "You are on the near corner because you do not hesitate any more. "
               "I have watched you not hesitate.",
               "If your corner slips we catch it and go again. It has slipped "
               "before. Nobody has ever been dropped."),
        turn_in="It is up. It is pegged. Tamsin is crying and pretending it is "
                "the dust. There is a workshop under that beam now.",
        objective={"count": 3, "failures_allowed": 1,
                   "recover": "A slip costs a rest and another lift. Nothing is "
                              "lost and nothing expires.",
                   "text": "Clear three encounters in one run, failing no more "
                           "than once."},
        consequence={"npc_line": "You held the near corner. Anything you break "
                                 "in this village, I fix for free.",
                     "world": "The workshop stands, roofed, with a bench and a "
                              "forge-light burning in it after dark."},
        requires=(Gate.mastery("PYTHON", 22),),
        extras={"town_upgrade": "village_workshop", "title": "Raiser of Beams"},
    ),
    Quest(
        id="village_deep_well", kind="RECOVERY", title="The Plumb of the Deep Well",
        region="python_village", giver="tamsin", tier=3,
        premise="The village well has been rationed for two years because the "
                "measuring plumb went down it and never came back.",
        setup=("We ration because we do not know how much is down there. Not "
               "because there is not enough.",
               "The plumb line went in during the Shattering, with the old "
               "keeper holding the other end. She let go.",
               "It is on a ledge. Everything in this village that fell is on a "
               "ledge somewhere. You have to go down far enough to see sideways."),
        turn_in="Eleven fathoms and clear the whole way. Two years of half "
                "buckets because nobody went and looked.",
        objective={"lost": "The keeper's plumb line",
                   "condition": "Descend the well shaft past the third ledge, "
                                "which is only visible from below the second.",
                   "found_in": "python_village",
                   "text": "Find the plumb line on the shaft's third ledge."},
        consequence={"npc_line": "Take as much water as you like. We measured "
                                 "it. That is the entire difference.",
                     "world": "The well runs unrationed, and the rope on it is "
                              "marked in fathoms in Tamsin's handwriting."},
        requires=(Gate.quest("village_mortar_weeds"), Gate.level(4)),
        extras={"town_upgrade": "village_well",
                "consumable": {"id": "focus_elixir", "count": 3}},
    ),
    Quest(
        id="village_pels_route", kind="RIDDLE", title="Pel's Route",
        region="python_village", giver="pel", tier=1,
        premise="Pel has invented a game where you have to answer before she "
                "counts to ten, and she counts fast.",
        setup=("You are the one who fixed the door. I watched.",
               "My mother says you know things. I am going to check.",
               "If something has to be fast to look at, and you only ever ask "
               "whether it is in there or not. What do you put it in."),
        turn_in="Set. Everyone says list and then they look at my face and "
                "change it. You said it first time.",
        objective={"question": "A thing you only ever ask 'is it in there' "
                               "about, and it must answer instantly. What do "
                               "you keep it in?",
                   "answers": ["set", "a set", "sets"], "skill": "SET",
                   "explain": "Membership in a set is constant time. Membership "
                              "in a list walks the list.",
                   "text": "Answer Pel, out loud, where you stand."},
        consequence={"npc_line": "I ask everyone your question now. Nobody else "
                                 "gets it. I am keeping score on the gate post.",
                     "world": "A child's chalk scoreboard appears on the gate "
                              "post and slowly fills up with wrong answers."},
        extras={"favor": {"mentor": "byte", "amount": 1}},
    ),

    # -- Fields of Syntax --------------------------------------------------
    Quest(
        id="fields_first_weeding", kind="HUNT", title="The First Weeding",
        region="fields_of_syntax", giver="harrow", tier=1,
        premise="Harrow has four hundred acres of half-formed statements and "
                "one warden.",
        setup=("Out here a sentence of code grows whether or not it means "
               "anything. Most of it does not.",
               "I can tell a weed from a crop by looking. I cannot clear four "
               "hundred acres by looking.",
               "Start at the east strip. Clear what will not run."),
        turn_in="East strip is crop and nothing else. You stopped checking "
                "whether you knew the syntax somewhere around the third acre.",
        objective={"family": "onboarding_loops", "count": 4,
                   "text": "Clear four loop and control-flow encounters."},
        consequence={"npc_line": "East strip is yours by right of clearing. "
                                 "Nobody else touches it.",
                     "world": "The east strip runs green and orderly, visible "
                              "from the causeway."},
        extras={"card": "card_read_the_error"},
    ),
    Quest(
        id="fields_fence_line", kind="PUZZLE", title="The Fence That Is a Shape",
        region="fields_of_syntax", giver="harrow", tier=2,
        premise="Two identical stretches of fence. One holds livestock and one "
                "does not, and Harrow cannot see which is which.",
        setup=("Same posts, same wire, same hands built them. One of them leaks "
               "sheep.",
               "I have walked both of them eleven times. Whatever is wrong with "
               "the bad one is one post wide.",
               "Look at them side by side. Do not repair anything until you can "
               "point at the post."),
        turn_in="One post. Set an inch shallow, four years ago, by me. I have "
                "walked past it eleven times looking for a hole in the wire.",
        objective={"puzzle": "SPOT_THE_FLAW", "count": 3,
                   "text": "Find the single broken line in three near-identical "
                           "pairs."},
        consequence={"npc_line": "I compare things side by side now before I "
                                 "start repairing them. Cheaper. Less walking.",
                     "world": "The south fence holds, and Harrow's repair kit "
                              "sits unopened by the gate."},
        extras={"incantation": "numbering", "card": "card_trace_by_hand"},
    ),
    Quest(
        id="fields_harvest_run", kind="ESCORT", title="The Harvest Run",
        region="fields_of_syntax", giver="harrow", tier=3,
        premise="The crop has to reach the village before the weather turns, "
                "and the long way round the mire takes two days.",
        setup=("Everything that is standing has to be cut, carted and inside by "
               "the time the sky does what it is about to do.",
               "You will lose a cart. Everybody loses a cart. We right it, we "
               "reload it, and we keep going, because the alternative is "
               "standing in a field arguing about a cart.",
               "Odile says there is a causeway line under the mire. If we get "
               "the harvest in, we dig it."),
        turn_in="In, dry, and counted. Two carts over and both of them righted "
                "inside the hour. That is what a good run looks like from "
                "inside — it does not look clean.",
        objective={"count": 4, "failures_allowed": 2,
                   "recover": "An overturned cart is righted and reloaded. The "
                              "run continues from where it stopped.",
                   "text": "Clear four encounters in one run, failing no more "
                           "than twice."},
        consequence={"npc_line": "Granary is full and there is a road to the "
                                 "village. Ask me for anything.",
                     "world": "The granary stands full, and the Barrow Causeway "
                              "runs dry-shod from the fields to the village."},
        requires=(Gate.quest("fields_fence_line"), Gate.mastery("PYTHON", 30)),
        extras={"town_upgrade": "fields_granary", "shortcut": "village_causeway"},
    ),
    Quest(
        id="fields_nils_gap", kind="RELIEF", title="One Gap",
        region="fields_of_syntax", giver="nils", tier=1,
        premise="Nils mends fences for a living and has found a gap he cannot "
                "account for in a list of posts he wrote himself.",
        setup=("Here is my list of posts. Here is the fence. The fence is one "
               "post short of the list.",
               "I have read the list out loud nine times.",
               "You do this differently to me. Do it your way."),
        turn_in="Missing post is numbered in my list twice and standing in the "
                "ground once. I wrote it down twice, four winters apart.",
        objective={"task": "Reconcile the post list against the fence",
                   "family": "onboarding_lists", "count": 3,
                   "text": "Clear three list-handling encounters."},
        consequence={"npc_line": "I keep the list the way you showed me. One "
                                 "entry, one post, and I check it against the "
                                 "ground, not against itself.",
                     "world": "Nils's fence runs unbroken to the tree line."},
        extras={"favor": {"mentor": "byte", "amount": 2}},
    ),
    Quest(
        id="fields_scarecrow", kind="RIDDLE", title="The Scarecrow's Question",
        region="fields_of_syntax", giver="nils", tier=2,
        premise="There is a scarecrow at the crossroads with a question carved "
                "into its post, and Nils has decided it is addressed to you.",
        setup=("It has been there longer than the fence. Longer than me.",
               "Somebody carved a question into the post and then, from what I "
               "can tell, went away and died of it.",
               "It says: an empty field, and you ask whether everything in it "
               "is sound. What does it answer."),
        turn_in="True. It answers true. An empty field has nothing wrong in it "
                "by virtue of having nothing in it. That is going to bother me "
                "all week.",
        objective={"question": "What does all([]) return?",
                   "answers": ["true", "it returns true", "all([]) is true"],
                   "skill": "PYTHON",
                   "explain": "There is no element that fails the test, so "
                              "there is nothing to make it false. Vacuous "
                              "truth, and a reliable source of off-by-nothing "
                              "bugs at the empty edge.",
                   "text": "Answer the scarecrow's carving."},
        consequence={"npc_line": "I put a board under the carving with the "
                                 "answer on it. Travellers stop and argue with "
                                 "the board. Good for trade.",
                     "world": "The crossroads scarecrow has an answer board "
                              "nailed beneath it, and a worn patch where people "
                              "stand and disagree."},
        requires=(Gate.clears("PYTHON", 6),),
        extras={"card": "card_boundaries"},
    ),
]

# Authored in geographic batches, so a region's content can be read as a place
# rather than as a spreadsheet.

_QUESTS += [

    # -- Hashmap Highlands -------------------------------------------------
    Quest(
        id="highlands_double_keys", kind="RELIEF", title="Two Keys, One Door",
        region="hashmap_highlands", giver="vela", tier=2,
        premise="Vela's toll ledger has more keys in it than there are vaults, "
                "and every duplicate is a toll somebody paid twice.",
        setup=("A key is cut for a vault. One vault, one key, that is the whole "
               "law of this plateau.",
               "My ledger says otherwise. My ledger has nine thousand entries "
               "and somewhere in it the same vault is keyed twice under two "
               "different names.",
               "I cannot afford to be the tollkeeper who charges twice. Find "
               "them and I will strike them out in front of witnesses."),
        turn_in="Fourteen duplicates. Struck out, refunded, and the ledger is "
                "one entry per vault for the first time since the Shattering.",
        objective={"task": "Find the duplicated vault keys",
                   "family": "dedupe", "count": 4,
                   "text": "Clear four deduplication encounters."},
        consequence={"npc_line": "One key, one vault, and a ledger that proves "
                                 "it. Tolls here are honest because you counted.",
                     "world": "Vela's toll gate posts a public ledger, and the "
                              "queue at it moves twice as fast."},
        extras={"card": "card_seen_before",
                "favor": {"mentor": "archivist", "amount": 3}},
    ),
    Quest(
        id="highlands_sunken_index", kind="DELVE", title="The Hollow of Keys",
        region="hashmap_highlands", giver="vela", tier=3,
        premise="The vault library fell through its own floor and took the "
                "index with it. The doors down there still work.",
        setup=("Four floors of it went down in one night. The keys still fit, "
               "which is the unsettling part.",
               "Nothing is misfiled down there. It is all filed perfectly, "
               "under a floor.",
               "Get to the third level. Bring up whatever the doors open to."),
        turn_in="Three levels, and every door you opened opened first time. "
                "Nobody has read those shelves in a decade.",
        objective={"dungeon": "hollow_of_keys", "depth": 3,
                   "text": "Reach the third level of the Hollow of Keys."},
        consequence={"npc_line": "The third level is shored and lit. We are "
                                 "carrying it back up one shelf at a time.",
                     "world": "Lantern light shows in the Hollow of Keys' "
                              "stairwell, and a hoist stands over the entrance."},
        requires=(Gate.quest("highlands_double_keys"), Gate.clears("HASH_MAP", 6)),
        extras={"codex": "codex_vaults",
                "consumable": {"id": "probe_scroll", "count": 2}},
    ),
    Quest(
        id="highlands_ledger_closed", kind="MASTERY", title="The Ledger Closes",
        region="hashmap_highlands", giver="vela", tier=4,
        premise="Vela wants the Highlands audited by somebody who can do it in "
                "one pass, unaided, in front of the guild.",
        setup=("An audit is not a test of whether you can open a vault. It is a "
               "test of whether you can open nine thousand without ever trying "
               "the wrong one.",
               "The guild will be watching. No spells, no prompting, and the "
               "clock is the ordinary clock — I am not asking you to hurry, I "
               "am asking you not to deliberate.",
               "Two vaults of the difficult kind. If you fail it we do it again "
               "next month and nobody writes anything down."),
        turn_in="Both, unaided, inside the hour. The guild has ratified the "
                "ledger and put your name on the first page, which I gather is "
                "the highest honour available to a person in my profession.",
        objective={"skill": "HASH_MAP", "difficulty": "MEDIUM", "count": 2,
                   "unaided": True, "under_target": True,
                   "text": "Clear two Medium hash-map encounters unaided and "
                           "inside the target time."},
        consequence={"npc_line": "Ratified. If you ever need a door on this "
                                 "plateau opened, it is already open.",
                     "world": "The Ledger House is rebuilt on the ridge, and "
                              "every vault in the Highlands is written down "
                              "exactly once."},
        requires=(Gate.quest("highlands_sunken_index"),
                  Gate.mastery("HASH_MAP", 55), Gate.unaided("HASH_MAP", 5)),
        extras={"town_upgrade": "ledger_house", "incantation": "tally",
                "set_item": "archivist_ring",
                "favor": {"mentor": "archivist", "amount": 8}},
    ),
    Quest(
        id="highlands_brants_wager", kind="RIDDLE", title="Brant's Wager",
        region="hashmap_highlands", giver="brant", tier=2,
        premise="Brant has bet a month of tolls that no traveller can answer "
                "his question without qualifying it.",
        setup=("Nine thousand vaults and I have never opened the wrong one "
               "twice. People ask me how. This is how.",
               "You have a list of names and a set of the same names. You want "
               "to know, over and over, whether a name is in there.",
               "Which do you reach for, and do not tell me it depends."),
        turn_in="The set. No hedging, no 'it depends on the size'. It depends "
                "on the size only in the sense that the bigger it gets the more "
                "right I am.",
        objective={"question": "List or set, for asking 'is this in here' ten "
                               "thousand times?",
                   "answers": ["set", "a set", "the set"], "skill": "HASH_MAP",
                   "explain": "A set hashes to the answer. A list walks until "
                              "it finds one, or until it runs out.",
                   "text": "Answer Brant at the vault gate."},
        consequence={"npc_line": "I lost a month of tolls to you and I have "
                                 "told the story eleven times, so it was cheap.",
                     "world": "Brant's wager board at the vault gate now reads "
                              "'ASKED AND ANSWERED' with your name under it."},
        extras={"favor": {"mentor": "archivist", "amount": 2}},
    ),
    Quest(
        id="highlands_lost_keyring", kind="RECOVERY", title="The Warden's Keyring",
        region="hashmap_highlands", giver="brant", tier=3,
        premise="Brant's master keyring went missing the night of the "
                "Shattering, and every key on it is cut for a door that still "
                "exists.",
        setup=("Forty keys on one ring. My predecessor was carrying it when the "
               "plateau moved.",
               "We searched the obvious places. The obvious places are where "
               "you look when you do not have a way of narrowing it down.",
               "The ring is iron and the vaults sing near their own keys. Walk "
               "the plateau and listen for a door that hums when nothing is "
               "near it."),
        turn_in="Forty keys, and each one hummed at exactly one door. You did "
                "not try a single wrong lock. I have been doing this for thirty "
                "years and that is the most elegant thing I have watched.",
        objective={"lost": "The warden's forty-key ring",
                   "condition": "Find the vault that hums with nothing near it, "
                                "on the plateau's west shelf, and look under it.",
                   "found_in": "hashmap_highlands",
                   "text": "Track the humming vault on the west shelf."},
        consequence={"npc_line": "Every door on the plateau opens for me again. "
                                 "Half of them had families' things in them.",
                     "world": "The west shelf vaults stand open and emptied, and "
                              "people come up from the Fields to collect what "
                              "was locked away."},
        requires=(Gate.quest("highlands_brants_wager"), Gate.mastery("HASH_MAP", 40)),
        extras={"incantation": "distill", "shortcut": "highland_tramway"},
    ),

    # -- Stringwood Labyrinth ----------------------------------------------
    Quest(
        id="stringwood_same_coat", kind="HUNT", title="The Same Word in a "
                                                      "Different Coat",
        region="stringwood_labyrinth", giver="quill", tier=2,
        premise="Quill names things for a living and the wood has started "
                "giving him the same tree four times under four names.",
        setup=("I am the namer. I write down what a thing is called and the "
               "wood respects the writing.",
               "Lately the wood is cheating. It rearranges the letters of a "
               "grove and presents it as a new grove and I name it again.",
               "Go into the letter-groves. Find me every pair that is the same "
               "word wearing a different coat, and I will strike the duplicates "
               "out of the register."),
        turn_in="Six groves, two names. I have been mapping a wood that is half "
                "the size I thought it was.",
        objective={"family": "anagrams", "count": 4,
                   "text": "Clear four anagram-grouping encounters."},
        consequence={"npc_line": "The register is half as long and twice as "
                                 "true. Sort the letters, then look. Always "
                                 "that order.",
                     "world": "Quill's register hangs open at the wood's edge "
                              "with the duplicate groves struck through in red."},
        requires=(Gate.clears("STRING", 3),),
        extras={"card": "card_canonical_form",
                "favor": {"mentor": "scribe", "amount": 3}},
    ),
    Quest(
        id="stringwood_letterfall", kind="DELVE", title="The Anagram Deeps",
        region="stringwood_labyrinth", giver="quill", tier=3,
        premise="The old spelling-house collapsed into its own cellars, and the "
                "walls down there are still rearranging.",
        setup=("The Deeps were where names were kept before I kept them. They "
               "went down in one piece and are still going down.",
               "The walls spell things. They spell the same thing repeatedly in "
               "different arrangements, which is how you know which way is out.",
               "Three floors. Take a lamp and take nothing on faith."),
        turn_in="Three floors, and you came out by reading the walls rather "
                "than by remembering the turns. That is the only method that "
                "works down there.",
        objective={"dungeon": "anagram_deeps", "depth": 3,
                   "text": "Reach the third floor of the Anagram Deeps."},
        consequence={"npc_line": "I have the old register back. Half the names "
                                 "in it are ones we lost.",
                     "world": "The Deeps' stair is roped and lit, and the "
                              "recovered register sits under glass in Quill's "
                              "hut."},
        requires=(Gate.quest("stringwood_same_coat"),),
        extras={"codex": "codex_index",
                "consumable": {"id": "focus_elixir", "count": 2}},
    ),
    Quest(
        id="stringwood_true_name", kind="RECOVERY", title="The Same Word Twice",
        region="stringwood_labyrinth", giver="quill", tier=3,
        premise="Something large has been leaving marks in the anagram grove, "
                "and each mark spells the previous one differently.",
        setup=("I have eleven marks and eleven spellings and they are all the "
               "same letters.",
               "Whatever is doing this is not lost and is not hunting. It is "
               "leaving me a sequence, and I do not think it understands that I "
               "am the only person who can read it.",
               "The last mark spells a place. Go and be there, twice, by the "
               "same path, and do not bring a lamp."),
        turn_in="It came out and looked at you and went back in. That is an "
                "introduction and not a decision. It will want the deed done "
                "before it stays.",
        objective={"lost": "Whatever is leaving the marks",
                   "condition": "Walk the anagram grove twice and take the "
                                "second path that spells the same word as the "
                                "first.",
                   "found_in": "stringwood_labyrinth",
                   "text": "Walk the anagram grove by the same word twice."},
        consequence={"npc_line": "It sits at the edge of my clearing in the "
                                 "evenings. It has never once been where I "
                                 "expected and has never once been wrong.",
                     "world": "Quill has read the marks, and the anagram "
                              "grove's paths stop rearranging while whatever "
                              "made them is watching."},
        requires=(Gate.quest("stringwood_letterfall"), Gate.mastery("STRING", 45)),
        extras={"pet": "pet_jaguar", "title": "Reader of Marks"},
    ),
    Quest(
        id="stringwood_moss_map", kind="RELIEF", title="Navigating by Spelling",
        region="stringwood_labyrinth", giver="moss", tier=2,
        premise="Moss forages by the spelling of the paths and her route list "
                "has stopped matching the wood.",
        setup=("I do not navigate by landmarks. Landmarks in this wood move.",
               "I navigate by what the path spells, and I keep a list, and the "
               "list has gone wrong in a way I cannot see.",
               "Some of my entries are written in a different case than others. "
               "I am told this matters. I refuse to believe the wood cares "
               "about capital letters."),
        turn_in="The wood does care about capital letters. I have rewritten "
                "four years of route notes into one form and walked three of "
                "them blind to prove it.",
        objective={"task": "Normalise four years of route notes",
                   "family": "onboarding_strings", "count": 3,
                   "text": "Clear three string-handling encounters."},
        consequence={"npc_line": "Every note I keep is in one form now. The "
                                 "wood is exactly as difficult as it always "
                                 "was, and I am no longer adding to it.",
                     "world": "Moss's route notes are pinned at the wood's edge "
                              "for anyone to copy, all in one case."},
        extras={"card": "card_canonical_form"},
    ),

    # -- Array Caverns -----------------------------------------------------
    Quest(
        id="caverns_off_by_one", kind="RELIEF", title="The Last Alcove",
        region="array_caverns", giver="dorn", tier=1,
        premise="Dorn's inventory says there is one more alcove than there is, "
                "and has said so for eleven years.",
        setup=("The first alcove is zero. The last is one less than the count. "
               "Every single thing that has gone wrong down here went wrong on "
               "one of those two facts.",
               "My inventory reaches for an alcove past the end of the row. "
               "Nothing is in it, because it is not there.",
               "Walk the row and tell me where my count and my reach disagree."),
        turn_in="Count of two hundred, last alcove one hundred and ninety-nine. "
                "I have been walking to the end of the row and reaching into "
                "the rock for over a decade.",
        objective={"task": "Reconcile the alcove count against the row",
                   "family": "onboarding_lists", "count": 3,
                   "text": "Clear three indexing encounters."},
        consequence={"npc_line": "Count, minus one. It is painted over the row "
                                 "now in letters a foot high.",
                     "world": "The alcove row is repainted, numbered from zero, "
                              "with the last index called out in white."},
        extras={"card": "card_boundaries",
                "favor": {"mentor": "archivist", "amount": 2}},
    ),
    Quest(
        id="caverns_lamp_run", kind="ESCORT", title="The Lamp Run",
        region="array_caverns", giver="dorn", tier=2,
        premise="The cavern lamps have to be lit end to end in one pass, "
                "because the ones behind you go out if you stop.",
        setup=("The lamps are enchanted to burn while somebody is moving "
               "forward down the row. Do not ask me why. Ask the person who "
               "enchanted them, who is dead.",
               "One pass, start to end. If you go out we walk you back to the "
               "last lit lamp and you carry on from there.",
               "Esk does it twice a shift and can do it in the dark. Esk is "
               "also nineteen and immortal."),
        turn_in="End to end. Two stalls, both recovered, and every alcove in "
                "the row is lit for the first time since the roof came down.",
        objective={"count": 4, "failures_allowed": 1,
                   "recover": "A stall drops you back to the last lit lamp, "
                              "never to the start of the row.",
                   "text": "Clear four encounters in one run, failing no more "
                           "than once."},
        consequence={"npc_line": "Row is lit. People work down here now instead "
                                 "of guessing down here.",
                     "world": "The full alcove row burns with lamplight, and "
                              "the far end of the caverns is passable."},
        requires=(Gate.quest("caverns_off_by_one"),),
        extras={"consumable": {"id": "stamina_draught", "count": 3},
                "card": "card_never_restart"},
    ),
    Quest(
        id="caverns_deeps", kind="DELVE", title="The Sunken Index",
        region="array_caverns", giver="dorn", tier=3,
        premise="Below the lit row the numbering continues downward until it "
                "stops meaning anything, and Dorn wants to know where that is.",
        setup=("The alcoves keep being numbered below the fourth level. That is "
               "the problem, not a comfort.",
               "Whoever cut them kept counting past the point where the count "
               "was useful, which is a thing I understand in my bones.",
               "Four levels down. Find where the numbering breaks and bring me "
               "the number it breaks at."),
        turn_in="Four levels, and the numbering does not break. It wraps. "
                "Somebody down there ran out of room and started again, which "
                "is the most human thing in this cavern.",
        objective={"dungeon": "sunken_index", "depth": 4,
                   "text": "Reach the fourth level of the Sunken Index."},
        consequence={"npc_line": "The lift goes to the fourth now. Straight "
                                 "through to Greave's shafts, and the pair of "
                                 "us split the maintenance.",
                     "world": "A cage lift runs from the alcove row down to the "
                              "mines, and it is indexed from one, as a joke."},
        requires=(Gate.quest("caverns_lamp_run"), Gate.mastery("ARRAY", 40)),
        extras={"shortcut": "cavern_lift", "incantation": "sever"},
    ),
    Quest(
        id="caverns_esk_count", kind="RIDDLE", title="Esk Counts Anyway",
        region="array_caverns", giver="esk", tier=1,
        premise="Esk knows exactly how many lamps there are and counts them "
                "every shift regardless.",
        setup=("Two hundred lamps. I have known that for a year.",
               "I still count them, every run, because Dorn asked me a question "
               "once and I got it wrong in front of people.",
               "Here is the question. Two hundred lamps, numbered the way we "
               "number things down here. What number is the last one."),
        turn_in="One hundred and ninety-nine. Said like it was nothing. I "
                "stood there for a full minute the first time.",
        objective={"question": "A row of 200 items, indexed from zero. What is "
                               "the index of the last one?",
                   "answers": ["199", "one hundred and ninety-nine", "n-1",
                               "len - 1", "len(x) - 1"],
                   "skill": "ARRAY",
                   "explain": "Length counts. Index positions. They are one "
                              "apart, forever, and that gap is most of the "
                              "bugs down here.",
                   "text": "Answer Esk at the head of the row."},
        consequence={"npc_line": "I still count them. But I count them because "
                                 "I like counting them now, which is different.",
                     "world": "Esk's chalk mark at the end of the row reads "
                              "199, underlined twice."},
        extras={"favor": {"mentor": "archivist", "amount": 1}},
    ),
    Quest(
        id="caverns_lost_lamp", kind="RECOVERY", title="The Lamp at the Far End",
        region="array_caverns", giver="esk", tier=2,
        premise="Esk dropped the keeper's lamp somewhere past the end of the "
                "lit row and will not ask Dorn for another.",
        setup=("It is the old keeper's lamp. Brass. It has her name on it.",
               "I was running the row backwards, which we are not supposed to "
               "do, and I went one alcove too far and there is no floor there.",
               "I cannot go back for it because I cannot carry a lamp to a "
               "place I need a lamp to reach. You see my difficulty."),
        turn_in="Brass, dented, and still burning. You went past the last "
                "alcove on purpose, which is the one thing down here nobody "
                "does twice.",
        objective={"lost": "The old keeper's brass lamp",
                   "condition": "Step past the final alcove of the lit row, "
                                "where the floor ends and the ledge begins.",
                   "found_in": "array_caverns",
                   "text": "Search the ledge past the end of the row."},
        consequence={"npc_line": "I hung it at the far end instead of carrying "
                                 "it. Now the end of the row is lit from the "
                                 "end, and nobody has to guess where it stops.",
                     "world": "A brass lamp burns permanently at the last "
                              "alcove, marking the end of the row from a "
                              "hundred yards off."},
        requires=(Gate.quest("caverns_esk_count"),),
        extras={"consumable": {"id": "focus_elixir", "count": 2},
                "card": "card_boundaries"},
    ),
]

_QUESTS += [

    # -- Sliding Window Marsh ----------------------------------------------
    Quest(
        id="marsh_first_breach", kind="HUNT", title="The First Breach",
        region="sliding_window_marsh", giver="fenn", tier=2,
        premise="Fenn has been rebuilding the same stretch of levee from the "
                "beginning every time it breaks, for two years.",
        setup=("When the water comes over, I go back to the first stake and "
               "start again. That is how my father did it.",
               "It takes eleven days and by the end of it the far stretch has "
               "failed, so I go back to the first stake.",
               "Somebody told me there is another way. Show me on the east "
               "breach, which is the small one."),
        turn_in="You widened out from where the water was, and pulled in from "
                "behind it, and never once went back to the first stake. "
                "Eleven days of work in an afternoon.",
        objective={"family": "window_sum", "count": 3,
                   "text": "Clear three sliding-window encounters."},
        consequence={"npc_line": "I have not walked back to the first stake "
                                 "since. The stake is still there. I leave it "
                                 "as a reminder of the eleven days.",
                     "world": "The east breach is sealed, and a single old "
                              "stake stands alone at the marsh's edge."},
        requires=(Gate.clears("HASH_MAP", 6),),
        extras={"card": "card_never_restart",
                "favor": {"mentor": "window_mage", "amount": 3}},
    ),
    Quest(
        id="marsh_never_restart", kind="MASTERY", title="One Unbroken Pass",
        region="sliding_window_marsh", giver="fenn", tier=3,
        premise="Fenn wants to watch somebody hold the ward across the middle "
                "marsh without help, because he does not yet believe it can be "
                "done that way.",
        setup=("I believe you can do it. I do not yet believe I could.",
               "Three crossings of the middle marsh. No spells, nobody calling "
               "advice from the bank.",
               "I am not timing you. I want to see you not stop."),
        turn_in="Three, and you never restarted. I watched the whole way and I "
                "have stopped arguing with myself about it.",
        objective={"skill": "SLIDING_WINDOW", "difficulty": "EASY", "count": 3,
                   "unaided": True, "under_target": False,
                   "text": "Clear three sliding-window encounters unaided."},
        consequence={"npc_line": "I work the way you work now. Slower than you. "
                                 "Still faster than eleven days.",
                     "world": "Fenn's stakes along the middle marsh are set in "
                              "one continuous line rather than in restarts."},
        requires=(Gate.quest("marsh_first_breach"),
                  Gate.unaided("SLIDING_WINDOW", 2)),
        extras={"codex": "codex_window",
                "favor": {"mentor": "window_mage", "amount": 5}},
    ),
    Quest(
        id="marsh_sluice_delve", kind="DELVE", title="Under the Sluice",
        region="sliding_window_marsh", giver="fenn", tier=3,
        premise="There are sluice chambers under the marsh, and something in "
                "them is moving the water level on a schedule nobody set.",
        setup=("The levee is not the problem. The levee is what the problem "
               "breaks.",
               "Under the marsh there are chambers with gates in them, and the "
               "gates open and close, and no hand has been down there in forty "
               "years.",
               "Three chambers down. Find what is holding the frame."),
        turn_in="A mechanism, still running, widening one side and narrowing "
                "the other on a count. It was built to do exactly what I have "
                "spent two years failing to do by hand.",
        objective={"dungeon": "the_long_draw", "depth": 3,
                   "text": "Reach the third chamber of the Long Draw."},
        consequence={"npc_line": "The old mechanism runs again. I maintain it "
                                 "instead of fighting the river.",
                     "world": "The sluice gates under the marsh open and close "
                              "on their own count, and the water sits where it "
                              "is told."},
        requires=(Gate.quest("marsh_never_restart"),),
        extras={"consumable": {"id": "whetstone", "count": 1},
                "card": "card_which_one_moves"},
    ),
    Quest(
        id="marsh_levee_holds", kind="ESCORT", title="The Levee Holds",
        region="sliding_window_marsh", giver="fenn", tier=4,
        premise="The whole marsh, in one pass, with the mechanism running and "
                "Fenn's entire village standing on the bank.",
        setup=("Everything I know is going onto the water at once. The "
               "mechanism, the new stakes, and you on the frame.",
               "If it breaks in the middle we pull back to the last sound "
               "stretch and go again from there. We do not go back to the first "
               "stake. You taught us that and it is the only thing I will be "
               "remembered for.",
               "Five stretches. Bring it home."),
        turn_in="It holds. The whole marsh, one pass, one breach recovered "
                "without a single person walking back to the beginning. There "
                "is a bird on the sluice gate watching you and it has been "
                "there since dawn.",
        objective={"count": 5, "failures_allowed": 1,
                   "recover": "A breach pulls the line back to the last sound "
                              "stretch. Never to the beginning.",
                   "text": "Clear five encounters in one run, failing no more "
                           "than once."},
        consequence={"npc_line": "Two years of my life, and an afternoon of "
                                 "yours. I am not bitter. I sleep now.",
                     "world": "The mended levee runs the length of the marsh "
                              "as a raised road, and the water it sheds goes "
                              "down the mines, to a gallery Fenn can now name."},
        requires=(Gate.quest("marsh_sluice_delve"),
                  Gate.mastery("SLIDING_WINDOW", 55)),
        extras={"town_upgrade": "marsh_levee", "shortcut": "levee_walk",
                "pet": "pet_penguin", "set_item": "chrono_trinket"},
    ),
    Quest(
        id="marsh_sables_ferry", kind="RELIEF", title="Wide Crossing, Narrow "
                                                      "Crossing",
        region="sliding_window_marsh", giver="sable", tier=2,
        premise="Sable's ferry takes a fixed number of reeds per crossing and "
                "she is losing money on every trip she guesses at.",
        setup=("The reedways take a fixed width of raft. Always the same width. "
               "That is not negotiable, the channels are the channels.",
               "So the only question I ever have is which fixed-width stretch "
               "of the load is worth the most, and I have been eyeballing it.",
               "Eyeball it with me for three crossings and tell me what you are "
               "doing differently."),
        turn_in="You never re-weighed the whole raft. You dropped what left the "
                "back and added what came on the front. Three crossings and my "
                "arms are not tired.",
        objective={"task": "Load three crossings at a fixed width",
                   "family": "fixed_window", "count": 3,
                   "text": "Clear three fixed-window encounters."},
        consequence={"npc_line": "Add at the front, drop at the back, never "
                                 "re-weigh the middle. I have it painted on the "
                                 "gunwale.",
                     "world": "Sable's ferry runs twice as often, and the words "
                              "ADD FRONT, DROP BACK are painted along its side."},
        requires=(Gate.clears("SLIDING_WINDOW", 3),),
        extras={"card": "card_never_restart",
                "consumable": {"id": "stamina_draught", "count": 2}},
    ),

    # -- Twin Pointer Pass -------------------------------------------------
    Quest(
        id="pass_two_carts", kind="HUNT", title="Two Carts, One Pass",
        region="twin_pointer_pass", giver="ondra", tier=2,
        premise="Ondra runs carts from both ends of the pass and cannot work "
                "out why the pairing keeps failing.",
        setup=("Cart leaves the low end. Cart leaves the high end. They are "
               "supposed to meet and trade loads in the middle.",
               "They do not meet in the middle. They meet wherever they meet, "
               "and then one of them turns round, and that is a day gone.",
               "The road is sorted, drover. Every waystation on it is in order "
               "of height. Use that."),
        turn_in="Neither cart ever turned round. You moved whichever one was "
                "carrying wrong and left the other standing. Four pairings, "
                "one day.",
        objective={"family": "sorted_pair", "count": 4,
                   "text": "Clear four converging-pointer encounters."},
        consequence={"npc_line": "Nobody on my crews turns a cart round any "
                                 "more. We move the one that is wrong.",
                     "world": "The pass road has trade-posts marked at every "
                              "meeting point, and the carts run without "
                              "doubling back."},
        requires=(Gate.clears("ARRAY", 5),),
        extras={"card": "card_which_one_moves",
                "favor": {"mentor": "ranger", "amount": 3}},
    ),
    Quest(
        id="pass_shorter_post", kind="PUZZLE", title="The Shorter Post",
        region="twin_pointer_pass", giver="ondra", tier=3,
        premise="Two bridges, built to the same plan by the same crew. One "
                "carries a loaded cart and the other does not.",
        setup=("Identical plans. I have them both here. I have compared them "
               "line by line and they are the same plans.",
               "One bridge holds forty tons. The other holds thirty-one and "
               "then does something I will not describe.",
               "Kell says it is the shorter post and Kell is usually right and "
               "never explains. Find me the line."),
        turn_in="The shorter post. It was never the taller one, it could never "
                "have been the taller one, and the two plans differ by one "
                "number in one place.",
        objective={"puzzle": "SPOT_THE_FLAW", "count": 3,
                   "text": "Find the single differing line in three pairs of "
                           "near-identical plans."},
        consequence={"npc_line": "Every bridge on this pass is measured at its "
                                 "shortest post now. Insurance rates halved.",
                     "world": "Both bridges carry loaded carts, and each has "
                              "its limiting post painted yellow."},
        requires=(Gate.quest("pass_two_carts"),),
        extras={"incantation": "converge", "card": "card_trace_by_hand"},
    ),
    Quest(
        id="pass_convoy_run", kind="ESCORT", title="The Convoy",
        region="twin_pointer_pass", giver="ondra", tier=4,
        premise="Winter supplies for three regions cross the pass in one "
                "convoy, and the weather gives them a single window.",
        setup=("Forty carts, both ends, converging. Everything that eats this "
               "winter is on those carts.",
               "You will lose carts. We right them and reload them and the "
               "convoy does not stop, because a convoy that stops on this pass "
               "is a convoy that is still here in spring.",
               "There is a pack animal that has been following my convoys for "
               "six years and has never once let anyone near it. Ignore it. It "
               "will decide what it wants."),
        turn_in="Through, both ends, everything fed. Two carts over and both "
                "righted. And the llama walked in behind you at the cairn and "
                "sat down like it had been invited, which in thirty years I "
                "have never seen it do.",
        objective={"count": 5, "failures_allowed": 2,
                   "recover": "An overturned cart is righted where it fell and "
                              "the convoy continues.",
                   "text": "Clear five encounters in one run, failing no more "
                           "than twice."},
        consequence={"npc_line": "Three regions ate this winter. The llama has "
                                 "decided about you, and I have made my peace "
                                 "with that.",
                     "world": "Winter stores stand full in three regions, and "
                              "the pass cairn has a llama beside it that is "
                              "no longer waiting for Ondra."},
        requires=(Gate.quest("pass_shorter_post"),
                  Gate.mastery("TWO_POINTER", 50)),
        extras={"pet": "pet_llama", "set_item": "chrono_ring",
                "title": "Convoy-Bringer"},
    ),
    Quest(
        id="pass_kell_riddle", kind="RIDDLE", title="Kell's Standing Argument",
        region="twin_pointer_pass", giver="kell", tier=2,
        premise="Kell has the same argument with every traveller and has never "
                "lost it.",
        setup=("Two posts hold a span between them. Water on both sides, and "
               "you want the span to hold the most water it can.",
               "You may move one post inward. One. Which one.",
               "Say the wrong one and I will let you walk on, and the bridge "
               "you build will be worse than the one you started with."),
        turn_in="The shorter one. Moving the taller one loses you width and "
                "buys you nothing, because the water was never above the short "
                "post to begin with.",
        objective={"question": "Two walls hold water between them. You may move "
                               "one inward. Which one, and why?",
                   "answers": ["the shorter", "shorter", "the shorter one",
                               "the short one", "the smaller"],
                   "skill": "TWO_POINTER",
                   "explain": "The shorter wall caps the height. Moving the "
                              "taller one costs width and cannot raise the cap.",
                   "text": "Settle Kell's argument at the bridgehead."},
        consequence={"npc_line": "First traveller in nine years. I have put a "
                                 "board up with your answer on it, which ruins "
                                 "the argument, which is what you get.",
                     "world": "A board at the bridgehead reads MOVE THE SHORTER "
                              "POST, and Kell stands beside it looking robbed."},
        extras={"card": "card_which_one_moves",
                "favor": {"mentor": "ranger", "amount": 2}},
    ),

    # -- Stack & Queue Mines -----------------------------------------------
    Quest(
        id="mines_top_first", kind="HUNT", title="Off the Top",
        region="stack_queue_mines", giver="greave", tier=2,
        premise="Somebody has been unloading carts from the bottom and the "
                "props in shaft four are holding up nothing in the right order.",
        setup=("Carts come off the top. Props come out in the reverse of the "
               "order they went in. This is not a preference.",
               "A new crew has been pulling from the middle because it is "
               "closer, and now shaft four has braces closing in an order that "
               "does not match how they opened.",
               "Go through it. Everything that opened has to close, and it has "
               "to close innermost first."),
        turn_in="Shaft four closes properly from the inside out. You went "
                "through four hundred braces and never once had to look back "
                "further than the last one you opened.",
        objective={"family": "stack_matching", "count": 4,
                   "text": "Clear four nesting and matching encounters."},
        consequence={"npc_line": "Off the top. It is painted on every cart in "
                                 "this mine now, and the new crew recites it.",
                     "world": "Shaft four is re-braced and open, with OFF THE "
                              "TOP stencilled on every cart in the mine."},
        requires=(Gate.clears("PYTHON", 10),),
        extras={"card": "card_nested_is_a_stack",
                "favor": {"mentor": "archivist", "amount": 3}},
    ),
    Quest(
        id="mines_cart_shafts", kind="DELVE", title="The Ninth Cart",
        region="stack_queue_mines", giver="greave", tier=3,
        premise="Four levels of the cart shafts are sealed behind their own "
                "unloading order, and the seals only open from the top.",
        setup=("Every level down is sealed by the level above it. You cannot "
               "get to the fourth without unloading the third, and so on, which "
               "is either brilliant engineering or a curse.",
               "There is a century of ore down there and a lift assembly my "
               "grandfather built.",
               "Four levels. Top down, in order, no shortcuts, because the "
               "shortcuts are what sealed it in the first place."),
        turn_in="Four levels, in order. The lift assembly is down there and it "
                "is intact and it is enormous.",
        objective={"dungeon": "ninth_cart", "depth": 4,
                   "text": "Reach the fourth level of the Ninth Cart."},
        consequence={"npc_line": "Grandfather's lift is coming up in pieces. "
                                 "Takes a month. Worth a century.",
                     "world": "The cart shafts stand open to the fourth level, "
                              "with hoist chains running down all of them."},
        requires=(Gate.quest("mines_top_first"), Gate.mastery("STACK", 40)),
        extras={"codex": "codex_order",
                "consumable": {"id": "probe_scroll", "count": 2}},
    ),
    Quest(
        id="mines_liftworks", kind="RELIEF", title="The Rota",
        region="stack_queue_mines", giver="greave", tier=4,
        premise="The rebuilt lift can run, but only if somebody works out the "
                "order that forty crews go up and down in.",
        setup=("The lift works. I built it, I am proud of it, and it is "
               "currently useless.",
               "Forty crews, one cage. Whoever has been waiting longest goes "
               "next. That is the rule the crews agreed to and I am not "
               "relitigating it.",
               "I have tried to hold the whole rota in my head. Do it properly. "
               "Oldest first, out the front, new arrivals on the back."),
        turn_in="Oldest out the front, new on the back, and nobody waits twice. "
                "The liftworks have been running for six days and there has not "
                "been a single argument at the cage, which in this mine is "
                "historically unprecedented.",
        objective={"task": "Build the cage rota",
                   "family": "queue_window", "count": 4,
                   "text": "Clear four queue encounters."},
        consequence={"npc_line": "Front and back. Never the middle. The rota "
                                 "runs itself and I have taken up carving.",
                     "world": "The Liftworks run day and night, and nothing "
                              "waits at the bottom of a shaft any more."},
        requires=(Gate.quest("mines_cart_shafts"), Gate.mastery("QUEUE", 45)),
        extras={"town_upgrade": "liftworks", "incantation": "dequeue",
                "title": "Keeper of the Order"},
    ),
    Quest(
        id="mines_pitch_nesting", kind="PUZZLE", title="What Is Holding What",
        region="stack_queue_mines", giver="pitch", tier=2,
        premise="Pitch needs to know exactly what is bearing load in a shaft "
                "before he pulls a single prop, and his crew keeps guessing.",
        setup=("I am going to read you a sequence of props going in and coming "
               "out. You are going to tell me what is still in there at the end.",
               "Not roughly. Exactly, and in order, top to bottom.",
               "The crew who guess this are the crew who find out they were "
               "wrong by being underneath it."),
        turn_in="Exact, in order, three times running. You are allowed in my "
                "shafts whenever you like.",
        objective={"puzzle": "STATE_PREDICT", "count": 3,
                   "text": "Predict the exact final state of three structures "
                           "after a trace."},
        consequence={"npc_line": "Nobody pulls a prop in my shafts on a guess. "
                                 "We write the sequence out and read it back.",
                     "world": "Pitch's crews chalk the prop sequence on the "
                              "shaft wall before touching anything."},
        requires=(Gate.clears("STACK", 3),),
        extras={"card": "card_nested_is_a_stack",
                "consumable": {"id": "probe_scroll", "count": 1}},
    ),

    # -- Matrix Citadel ----------------------------------------------------
    Quest(
        id="citadel_plans", kind="RELIEF", title="The Plans Do Not Turn",
        region="matrix_citadel", giver="lorne", tier=2,
        premise="The citadel rotates and the floor plans do not, and Lorne has "
                "to reconcile the two before anybody can be told where to go.",
        setup=("The building turns a quarter at a time. The plans are on paper "
                "and paper does not turn unless somebody turns it.",
               "I have to hand a guard a plan that matches the building they "
               "are standing in. Currently I hand them a plan and an apology.",
               "Take the east wing plans and give me back the same plans, "
               "turned. Not redrawn. Turned."),
        turn_in="Turned, not redrawn. Rows became columns in the right order "
                "and the whole east wing fits its plan for the first time since "
                "the Golem woke.",
        objective={"task": "Rotate the east wing plans",
                   "family": "matrix_transform", "count": 3,
                   "text": "Clear three matrix transformation encounters."},
        consequence={"npc_line": "Rows to columns, then reverse. In that order. "
                                 "I say it in my sleep and I have stopped "
                                 "apologising to guards.",
                     "world": "The citadel's plan room holds a rotating frame "
                              "that turns with the building."},
        requires=(Gate.clears("ARRAY", 8),),
        extras={"card": "card_grid_is_a_graph",
                "favor": {"mentor": "cartographer", "amount": 3}},
    ),
    Quest(
        id="citadel_keep", kind="DELVE", title="The Turning Keep",
        region="matrix_citadel", giver="lorne", tier=3,
        premise="The inner keep turns a quarter-turn whenever it is left alone, "
                "and the stairs stay where they are.",
        setup=("Three floors in, the keep turns and the stairs do not, so the "
               "stair you came down is not the stair you go up.",
               "Everyone who has gone in has come out. Eventually. Usually "
               "somewhere else.",
               "Three floors. Hold the orientation in your head, or better, "
               "hold it on paper the way I do, since I am still alive."),
        turn_in="Three floors in and out by the stair you came down, which "
                "means you tracked the turn the whole way. Nobody does that "
                "without writing it down. I checked your hands. No chalk.",
        objective={"dungeon": "turning_keep", "depth": 3,
                   "text": "Reach the third floor of the Turning Keep."},
        consequence={"npc_line": "The keep has an orientation mark on every "
                                 "landing now. Your idea, my paint.",
                     "world": "Every landing of the Turning Keep carries a "
                              "painted north-mark that turns with the floor."},
        requires=(Gate.quest("citadel_plans"),),
        extras={"consumable": {"id": "whetstone", "count": 1},
                "codex": "codex_order"},
    ),
    Quest(
        id="citadel_true_north", kind="MASTERY", title="True North",
        region="matrix_citadel", giver="lorne", tier=4,
        premise="Lorne wants the whole citadel surveyed by somebody who can "
                "rotate it in their head, unaided, while it is moving.",
        setup=("The Golem stirs twice a day and the whole floor plan turns "
                "ninety degrees.",
               "I need a survey done between stirs. No assistance, no second "
               "matrix to copy into — there is no room for a second citadel "
               "inside this one.",
               "Two wings, in place, inside the window. This is the job I have "
               "wanted done for eleven years."),
        turn_in="Both wings, in place, no copy, inside the window. The survey "
                "is on the wall of the plan room and it is correct in all four "
                "orientations, which took some doing to draw.",
        objective={"skill": "MATRIX", "difficulty": "MEDIUM", "count": 2,
                   "unaided": True, "under_target": True,
                   "text": "Clear two Medium matrix encounters unaided and "
                           "inside the target time."},
        consequence={"npc_line": "Eleven years. You did it between two stirs of "
                                 "the Golem. I am going to sit down.",
                     "world": "The plan room's great survey hangs complete, "
                              "readable from any of the citadel's four "
                              "orientations."},
        requires=(Gate.quest("citadel_keep"), Gate.mastery("MATRIX", 50),
                  Gate.unaided("MATRIX", 3)),
        extras={"title": "True North", "incantation": "cell",
                "codex": "codex_search",
                "favor": {"mentor": "cartographer", "amount": 8}},
    ),
    Quest(
        id="citadel_night_watch", kind="ESCORT", title="The Night Watch",
        region="matrix_citadel", giver="ives", tier=3,
        premise="Ives needs the keep patrolled through a full rotation, and "
                "recruits keep breaking formation when the floor moves.",
        setup=("A patrol is rows then columns. Always that order. The day you "
               "do it the other way round you will know, because nothing will "
               "fit.",
               "The floor turns under you mid-patrol. Recruits panic and start "
               "the circuit again from the gate, which is how you end up with "
               "a guard who has walked all night and seen a quarter of the keep.",
               "If you lose the formation, pick it up at the last corner. Not "
               "at the gate."),
        turn_in="Full rotation, formation held, and when you lost it at the "
                "third turn you picked it up at the corner like you had been "
                "doing it for years. The recruits watched. That was the point.",
        objective={"count": 4, "failures_allowed": 1,
                   "recover": "A broken formation resumes at the last corner "
                              "held, never at the gate.",
                   "text": "Clear four encounters in one run, failing no more "
                           "than once."},
        consequence={"npc_line": "My recruits pick up at the corner now. I told "
                                 "them it was my idea. It was not.",
                     "world": "The citadel's night watch runs unbroken, and the "
                              "keep's corners are marked with formation stones."},
        requires=(Gate.clears("MATRIX", 4),),
        extras={"consumable": {"id": "stamina_draught", "count": 3},
                "card": "card_grid_is_a_graph"},
    ),
]

_QUESTS += [

    # -- Recursive Forest --------------------------------------------------
    Quest(
        id="forest_smaller_forest", kind="HUNT", title="A Smaller Forest",
        region="recursive_forest", giver="halla", tier=3,
        premise="Halla's foresters keep walking into clearings and coming out "
                "days later having achieved nothing.",
        setup=("Every clearing in this forest has a smaller forest inside it. "
               "That is not a metaphor, it is a survey problem.",
               "My people go in to count trees and they get four levels deep "
               "and forget what they went in for.",
               "Go in. Do one thing at each level, take what the smaller level "
               "hands you, and come back out with it. That is all this place "
               "asks."),
        turn_in="Four levels down and you came back out carrying a number. My "
                "foresters came out carrying opinions.",
        objective={"family": "recursion_basics", "count": 4,
                   "text": "Clear four recursion encounters."},
        consequence={"npc_line": "I brief my foresters the way you do it now. "
                                 "Say what stops you before you go in.",
                     "world": "The forest's clearings are staked with depth "
                              "markers, and Halla's survey is finally moving."},
        requires=(Gate.clears("RECURSION", 2),),
        extras={"card": "card_base_case_first",
                "favor": {"mentor": "druid", "amount": 3}},
    ),
    Quest(
        id="forest_unwind", kind="PUZZLE", title="The Way Out Is the Way In",
        region="recursive_forest", giver="halla", tier=3,
        premise="A forester is four levels down and conscious, and Halla needs "
                "to know what he will be holding when he surfaces.",
        setup=("He is not in danger. He is in the fourth level and he is doing "
               "the job.",
               "What I need is to know what he comes out with, before he comes "
               "out, so I can have the cart ready.",
               "Here is what he does at each level. Tell me the value he "
               "surfaces with, and the values at every level on the way up."),
        turn_in="Every level, in order, on the way up. The cart was where it "
                "needed to be and he walked straight onto it.",
        objective={"puzzle": "TRACE", "count": 2,
                   "text": "Predict the values at every checkpoint in two "
                           "traces."},
        consequence={"npc_line": "We trace the call out loud before anyone "
                                 "goes down. Costs five minutes. Saves days.",
                     "world": "A tracing board stands at the forest edge where "
                              "foresters walk their descent aloud before "
                              "entering."},
        requires=(Gate.quest("forest_smaller_forest"),),
        extras={"card": "card_trace_by_hand",
                "consumable": {"id": "focus_elixir", "count": 2}},
    ),
    Quest(
        id="forest_stopping_condition", kind="RIDDLE", title="Say It Before You "
                                                             "Go Down",
        region="recursive_forest", giver="bram", tier=3,
        premise="Bram will not let anyone past the inner treeline until they "
                "have told him what stops them.",
        setup=("I am not testing you. I am doing the thing that keeps people "
               "alive at this treeline.",
               "Everyone who has gone in without an answer to this has come out "
               "eventually, and some of them came out wrong.",
               "Tell me what a stopping condition is for. Not what it is. What "
               "it is for."),
        turn_in="To stop. That is the whole of it. Not to be elegant, not to be "
                "clever — to be the level that does not go down again. Go in.",
        objective={"question": "What is a base case for?",
                   "answers": ["to stop", "stop", "to stop the recursion",
                               "terminate", "to terminate", "so it ends",
                               "prevent infinite recursion", "to end it"],
                   "skill": "RECURSION",
                   "explain": "It is the level that does not call again. "
                              "Without one, every descent is infinite and the "
                              "stack is what runs out first.",
                   "text": "Answer Bram at the inner treeline."},
        consequence={"npc_line": "You may pass the treeline whenever you like. "
                                 "You said the stopping condition first, which "
                                 "is the correct order for everything.",
                     "world": "Bram's treeline gate stands open to you, and a "
                              "carved post beside it reads SAY WHAT STOPS YOU."},
        requires=(Gate.clears("RECURSION", 3),),
        extras={"card": "card_base_case_first",
                "favor": {"mentor": "druid", "amount": 4}},
    ),
    Quest(
        id="forest_inner_grove", kind="DELVE", title="The Innermost Grove",
        region="recursive_forest", giver="bram", tier=4,
        premise="Five levels in there is a single tree and nothing else, and "
                "nobody who has reached it has left it empty-handed, which is "
                "the problem.",
        setup=("The innermost grove is one tree in a clearing. There is nothing "
                "in it. That is what it is for.",
               "Everyone who reaches it takes something — a branch, a stone, a "
               "handful of the soil — and the forest closes a level behind them "
               "for each thing they take.",
               "Go to the bottom. Take nothing. Come back out the way you went "
               "in. Something down there has been waiting a long time for "
               "someone to do exactly that."),
        turn_in="Five levels down, nothing taken, and back out unwinding the "
                "way you came. There is a spring at the centre of it, and "
                "something in the spring watched you the whole way out.",
        objective={"dungeon": "inner_grove", "depth": 5,
                   "text": "Reach the fifth level of the Inner Grove."},
        consequence={"npc_line": "The forest is one forest again. And you have "
                                 "seen the spring, which almost nobody has.",
                     "world": "The Inner Grove's levels stay open, a ropeway "
                              "runs from the grove to the canopy, and the "
                              "innermost spring is on Halla's map at last."},
        requires=(Gate.quest("forest_stopping_condition"),
                  Gate.mastery("RECURSION", 55)),
        extras={"pet": "pet_nautilus", "shortcut": "canopy_ropeway",
                "codex": "codex_recursion"},
    ),

    # -- Binary Tree Canopy ------------------------------------------------
    Quest(
        id="canopy_two_branches", kind="HUNT", title="Never Three",
        region="binary_tree_canopy", giver="wren", tier=3,
        premise="A storm has left branches crossed and rejoining, which the "
                "canopy does not permit and cannot repair itself.",
        setup=("Two branches from every fork. Never three, never one rejoining "
               "another. The canopy is strict and I like it here.",
               "The storm laid branches across each other. Where they touch, "
               "the canopy thinks it has a loop, and a canopy that thinks it "
               "has a loop stops growing.",
               "Walk the forks and separate what is crossed. Every path from "
               "the crown to a leaf should be exactly one path."),
        turn_in="One path, crown to leaf, every leaf. The canopy started "
                "growing again the same afternoon.",
        objective={"family": "tree_traverse", "count": 4,
                   "text": "Clear four tree traversal encounters."},
        consequence={"npc_line": "It grows again. Thirty years of my life is up "
                                 "there and it grows again.",
                     "world": "The canopy's crown is knitting closed, and the "
                              "crossed storm branches are cut and stacked below."},
        requires=(Gate.clears("RECURSION", 5),),
        extras={"card": "card_carry_bounds",
                "favor": {"mentor": "druid", "amount": 3}},
    ),
    Quest(
        id="canopy_nest_order", kind="PUZZLE", title="The Order the Nests Come "
                                                     "Out",
        region="binary_tree_canopy", giver="alder", tier=3,
        premise="Alder has to bring the nests down in a strict order and his "
                "climbing instructions have been shuffled.",
        setup=("Left, then the fork itself, then right. That order and no "
               "other, or the nests come out in the wrong sequence and the "
               "birds are unbearable about it.",
               "Somebody dropped my instruction boards off the spine and I have "
               "the pieces and not the order.",
               "Put them back together. The order is the whole instruction — "
               "the individual lines are obvious."),
        turn_in="Left, node, right. Assembled and nailed to the spine in "
                "sequence, and the depth of each line matters as much as the "
                "order, which you clearly already knew.",
        objective={"puzzle": "RUNE_ASSEMBLY", "count": 2, "family": "tree_traverse",
                   "text": "Assemble two traversals from shuffled runes."},
        consequence={"npc_line": "Boards are up. Every climber on this canopy "
                                 "reads them on the way up and recites them on "
                                 "the way down.",
                     "world": "Instruction boards run the length of the Rookery "
                              "Spine, in order, at the correct depths."},
        requires=(Gate.clears("TREE", 3),),
        extras={"card": "card_say_it_first",
                "consumable": {"id": "probe_scroll", "count": 2}},
    ),
    Quest(
        id="canopy_rookery_spine", kind="DELVE", title="The Split Canopy",
        region="binary_tree_canopy", giver="alder", tier=3,
        premise="The hollow trunk forks twice per storey and nobody has climbed "
                "past the third fork since it was struck by lightning.",
        setup=("Inside the trunk it forks twice a storey. No rejoining. If you "
               "go the wrong way you do not loop back round, you simply arrive "
               "somewhere that is not where you meant to be.",
               "Third storey has the old rookery in it and eleven years of "
               "birds that nobody has counted.",
               "Up three. Come back down by the same forks or do not come back "
               "down at all, and I would like you to come back down."),
        turn_in="Three storeys, same forks both ways. The old rookery is intact "
                "and the count is eleven years out of date in the direction "
                "nobody expected.",
        objective={"dungeon": "split_canopy", "depth": 3,
                   "text": "Reach the third storey of the Split Canopy."},
        consequence={"npc_line": "The spine is roped to the third. I take "
                                 "apprentices up it now.",
                     "world": "Fixed ropes run the Split Canopy to the third "
                              "storey, and the old rookery is counted and "
                              "recorded."},
        requires=(Gate.quest("canopy_nest_order"),),
        extras={"consumable": {"id": "stamina_draught", "count": 3},
                "card": "card_carry_bounds"},
    ),
    Quest(
        id="canopy_lost_fledgling", kind="RECOVERY", title="The Fledgling That "
                                                           "Is Not Where It "
                                                           "Should Be",
        region="binary_tree_canopy", giver="wren", tier=3,
        premise="Wren's ordered rookery has one bird in the wrong place, and "
                "the ordering is the only way anything is ever found up here.",
        setup=("Every nest on this canopy is placed in order. Smaller to the "
                "left, larger to the right, all the way down from the crown.",
               "One fledgling is in a nest where it cannot be. It is not wrong "
               "against its own fork — it is wrong against the whole tree "
               "above it, which is a distinction that took me a decade.",
               "Do not check each fork against its own children. Carry the "
               "bounds down with you from the crown."),
        turn_in="Fourth fork of the west limb. Legal against its parent, "
                "impossible against its grandparent. Nobody checking locally "
                "would ever have found it.",
        objective={"lost": "A fledgling nested outside its bounds",
                   "condition": "Carry the crown's bounds down the west limb "
                                "rather than comparing each fork to its own "
                                "children.",
                   "found_in": "binary_tree_canopy",
                   "text": "Find the out-of-bounds nest on the west limb."},
        consequence={"npc_line": "Bounds come down from the crown. Not up from "
                                 "the children. I teach it that way now and the "
                                 "apprentices get it in an afternoon.",
                     "world": "The west limb's nests are re-ordered, and Wren's "
                              "bound-markers hang from the crown downward."},
        requires=(Gate.quest("canopy_two_branches"), Gate.mastery("TREE", 45)),
        extras={"incantation": "halve", "card": "card_carry_bounds"},
    ),

    # -- Graph Wastes ------------------------------------------------------
    Quest(
        id="wastes_four_roads", kind="HUNT", title="Four Roads Out of Every Room",
        region="graph_wastes", giver="corvin", tier=3,
        premise="Corvin is the last courier working the Wastes and he is "
                "walking three times further than the job requires.",
        setup=("Every ruin connects to four others. Only one of those four is "
                "on the way to anywhere.",
               "I know the roads. Knowing the roads is not the same as knowing "
               "which road, and after eleven years I still find out I was wrong "
               "two days later.",
               "Walk the eastern ruins with me. Every road, once, and mark what "
               "you have already seen so we do not do it twice."),
        turn_in="Every ruin in the east, once each. Eleven years and I have "
                "never once walked that district without repeating myself.",
        objective={"family": "graph_traverse", "count": 4,
                   "text": "Clear four graph traversal encounters."},
        consequence={"npc_line": "Mark it seen when you reach it. I chant it "
                                 "now. It is not a good chant.",
                     "world": "The eastern ruins are waymarked, each junction "
                              "chalked once and only once."},
        requires=(Gate.clears("BFS", 2),),
        extras={"card": "card_mark_on_enqueue",
                "favor": {"mentor": "cartographer", "amount": 3}},
    ),
    Quest(
        id="wastes_rings_of_light", kind="MASTERY", title="Rings of Light",
        region="graph_wastes", giver="corvin", tier=3,
        premise="A shortest route through the Wastes, found unaided, is worth "
                "more to Corvin than any map he has ever been sold.",
        setup=("I have been sold maps. Maps tell you the roads exist. I have "
               "never once been sold the shortest way.",
               "Three routes, and you find them without help, because a route "
               "somebody else found for you is not a route I can trust you to "
               "find again next winter.",
               "Rings out from where you stand, not one committed line. The "
               "committed line finds a way. The rings find the way."),
        turn_in="Three routes, all shortest, all found cold. That is worth more "
                "to me than the eleven maps in my bag, which I am now going to "
                "burn for warmth.",
        objective={"skill": "BFS", "difficulty": "EASY", "count": 3,
                   "unaided": True, "under_target": False,
                   "text": "Clear three breadth-first search encounters "
                           "unaided."},
        consequence={"npc_line": "Rings, not a line. I have taken on two "
                                 "apprentices and that is the first thing I "
                                 "teach them.",
                     "world": "Corvin's courier house takes apprentices again, "
                              "and its wall map is drawn in rings."},
        requires=(Gate.quest("wastes_four_roads"), Gate.unaided("BFS", 2)),
        extras={"codex": "codex_search", "card": "card_mark_on_enqueue",
                "favor": {"mentor": "cartographer", "amount": 5}},
    ),
    Quest(
        id="wastes_undercity", kind="DELVE", title="The Lattice of Ruin",
        region="graph_wastes", giver="corvin", tier=4,
        premise="Seven strata of tunnels under the Wastes, no map, four ways "
                "out of every room, and something down there that never doubles "
                "back.",
        setup=("There is a whole city under the Wastes and every room in it has "
                "four exits and none of them are labelled.",
               "Couriers have gone down. Couriers have come up. Not always the "
               "same couriers, if you follow me.",
               "Five strata. And there is something using the tunnels faster "
               "than anything should be able to — it never revisits a room. "
               "Whatever it is, it is better at this than I am."),
        turn_in="Five strata and a map of all of them. And the thing that never "
                "doubles back walked out behind you at the waystation and "
                "waited while you ate, which Mira says she is fine with and is "
                "very obviously not.",
        objective={"dungeon": "lattice_of_ruin", "depth": 5,
                   "text": "Reach the fifth stratum of the Lattice of Ruin."},
        consequence={"npc_line": "There is a map of the Lattice. There has "
                                 "never been a map of the Lattice.",
                     "world": "The Lattice's first five strata are mapped and "
                              "waymarked, and the courier roads now name the "
                              "one slope something has been pacing for weeks."},
        requires=(Gate.quest("wastes_rings_of_light"), Gate.mastery("GRAPH", 45)),
        extras={"pet": "pet_velociraptor", "set_item": "pathfinder_compass",
                "title": "Mapper of the Lattice"},
    ),
    Quest(
        id="wastes_waystation", kind="RELIEF", title="Mira Feeds Whoever Arrives",
        region="graph_wastes", giver="mira", tier=4,
        premise="Mira's waystation has no custom because every road into it "
                "eventually returns to where it started.",
        setup=("I feed whoever arrives. Lately that is nobody, because the "
               "roads all go in circles and people give up before they get here.",
               "Corvin says you found the shortest way through the east. I need "
               "the shortest way through everything, to here, from all four "
               "quarters.",
               "I am not asking for a map. I am asking to be somewhere people "
               "can get to."),
        turn_in="Four roads in, all of them shortest, all of them signed. There "
                "were nine people in here last night and I did not have enough "
                "bowls, which is the happiest sentence I have said in years.",
        objective={"task": "Find the shortest road in from all four quarters",
                   "family": "grid_bfs", "count": 4,
                   "text": "Clear four shortest-path encounters."},
        consequence={"npc_line": "Nine last night. Eleven the night before. Eat "
                                 "whatever you like, forever, and do not insult "
                                 "me by offering.",
                     "world": "The waystation has smoke coming out of it and "
                              "couriers in it, and the Relay Road runs signed "
                              "and straight to the Citadel."},
        requires=(Gate.quest("wastes_undercity"),),
        extras={"town_upgrade": "waystation", "shortcut": "relay_road",
                "title": "Road-Maker"},
    ),

    # -- Dynamic Programming Ruins -----------------------------------------
    Quest(
        id="ruins_paid_twice", kind="HUNT", title="Paid Twice",
        region="dp_ruins", giver="tolliver", tier=3,
        premise="Tolliver's tally of the ruins keeps coming out higher than the "
                "ruins are, because the same stones are being counted again and "
                "again.",
        setup=("Someone already solved this. Probably you. Probably twice. That "
                "is the tragedy of this place and it is also, specifically, my "
                "problem.",
               "My tally of the western terrace is nine thousand stones. There "
               "are two thousand stones on the western terrace.",
               "Every path I walk crosses paths I have already walked, and I "
               "count the crossing again each time. Do it so that nothing is "
               "counted twice."),
        turn_in="Two thousand and forty. Once each. You wrote down what you had "
                "already answered and then refused to answer it again, which I "
                "am told is a technique and not a personality.",
        objective={"family": "dp_linear", "count": 4,
                   "text": "Clear four dynamic programming encounters."},
        consequence={"npc_line": "Nothing gets counted twice on my terrace. I "
                                 "keep the answers in a box and I look in the "
                                 "box first.",
                     "world": "The western terrace is tallied and marked, its "
                              "counted stones glowing faintly underfoot."},
        requires=(Gate.chapter("optimisation"),),
        extras={"card": "card_refuse_to_answer_twice",
                "favor": {"mentor": "oracle", "amount": 3}},
    ),
    Quest(
        id="ruins_lit_tiles", kind="PUZZLE", title="What the Tiles Cost",
        region="dp_ruins", giver="nima", tier=3,
        premise="Nima lights the tiles she has measured so she never measures "
                "them twice, and she needs to know what each route costs before "
                "she commits to it.",
        setup=("It took me four years to think of lighting the tiles I had "
                "already done. Four years.",
               "Now I have a different problem, which is a better problem. I "
               "have four routes across the ruins and I do not know which is "
               "expensive.",
               "Not which is long. Which is expensive. Those are different and "
               "the difference is the entire ruin."),
        turn_in="Matched, all four, first pass. The cheap-looking one was the "
                "expensive one, which I suspected and could not have defended.",
        objective={"puzzle": "COMPLEXITY_MATCH", "count": 2,
                   "text": "Match two sets of routes to what they actually "
                           "cost."},
        consequence={"npc_line": "I cost a route before I walk it. Four years "
                                 "to light the tiles, one afternoon to learn "
                                 "that. The ratio bothers me.",
                     "world": "The ruins' routes are posted with their costs at "
                              "the terrace gate, cheapest last."},
        requires=(Gate.clears("BIG_O", 3),),
        extras={"card": "card_count_per_element",
                "codex": "codex_cost"},
    ),
    Quest(
        id="ruins_vaults", kind="DELVE", title="The Hall of Lit Tiles",
        region="dp_ruins", giver="tolliver", tier=4,
        premise="Five levels of vaults where any tile you have already crossed "
                "stays lit and costs nothing, and nobody has ever crossed "
                "enough of them to reach the bottom.",
        setup=("The rule down there is generous and everybody breaks it anyway. "
                "A tile you have crossed stays lit. Crossing it again is free.",
               "So the only way to fail is to keep taking new tiles when a lit "
               "one would do. Which is what people do, because new tiles look "
               "like progress.",
               "Five levels. You will run out of light long before you run out "
               "of floor unless you are willing to walk back over old ground."),
        turn_in="Five levels, and you spent most of the descent walking over "
                "your own footprints. The bottom vault has the original tally "
                "of the ruins in it, and it is in a hand I recognise, and it is "
                "mine, from before.",
        objective={"dungeon": "lit_tiles", "depth": 5,
                   "text": "Reach the fifth level of the Hall of Lit Tiles."},
        consequence={"npc_line": "I wrote that tally. I do not remember writing "
                                 "it. Whatever happened here happened to me too.",
                     "world": "The Hall of Lit Tiles stays lit to the fifth level, "
                              "and Tolliver's original tally hangs in the ruins' "
                              "gatehouse."},
        requires=(Gate.quest("ruins_paid_twice"), Gate.mastery("DP", 45)),
        extras={"consumable": {"id": "insight_tonic", "count": 2},
                "codex": "codex_cost"},
    ),
    Quest(
        id="ruins_ledger_balanced", kind="MASTERY", title="The Ledger Balances",
        region="dp_ruins", giver="tolliver", tier=4,
        premise="Tolliver wants the ruins' full account closed by somebody who "
                "can do it without solving anything twice, unaided, on the "
                "clock.",
        setup=("The account of this place has never been closed. Not once, in "
                "all the years, by anybody.",
               "It cannot be closed by working harder. It is too large. It can "
               "only be closed by never paying for the same subproblem twice.",
               "Two of the hard ones, unaided, inside the time. If it does not "
               "close today it will close another day and the work you did "
               "today stays lit."),
        turn_in="Closed. Both, unaided, inside the time. The ruins have an "
                "account and it balances and I have nothing left to do here, "
                "which I am going to have to think about.",
        objective={"skill": "DP", "difficulty": "MEDIUM", "count": 2,
                   "unaided": True, "under_target": True,
                   "text": "Clear two Medium dynamic-programming encounters "
                           "unaided and inside the target time."},
        consequence={"npc_line": "The account balances. I sit on the terrace "
                                 "now and I do not count anything, and it is "
                                 "taking some getting used to.",
                     "world": "Every tile of the ruins is lit, and the Lit Stair "
                              "runs from the terrace up to the Complexity Tower."},
        requires=(Gate.quest("ruins_vaults"), Gate.mastery("DP", 55),
                  Gate.unaided("DP", 4)),
        extras={"incantation": "enshrine", "set_item": "memoist_ledger",
                "title": "The Tallykeeper's Equal", "shortcut": "ruins_stair"},
    ),
]

_QUESTS += [

    # -- Debugging Dungeon -------------------------------------------------
    Quest(
        id="forge_read_the_crack", kind="RELIEF", title="Reading the Crack",
        region="debugging_dungeon", giver="garrick", tier=2,
        premise="Garrick has been staring at the same fracture for two days "
                "because the Armorer told him to read it and he does not know "
                "what that means.",
        setup=("He says read the crack. I have looked at it for two days. I "
                "have not read anything.",
               "I know what a good plate looks like. This one is not it, and I "
               "cannot say why, and he will not tell me.",
               "Sit with me and do it out loud. Whatever it is you do, say it "
               "while you are doing it."),
        turn_in="You read the failing input first. Not the code. The input. Two "
                "days I have been looking at the plate and the plate was never "
                "going to tell me which blow broke it.",
        objective={"task": "Repair three broken plates with Garrick watching",
                   "family": "debugging", "count": 3,
                   "text": "Clear three debugging encounters."},
        consequence={"npc_line": "Failing input first. Then trace it by hand. I "
                                 "say it out loud and the other apprentices "
                                 "have started copying me.",
                     "world": "Garrick's bench is busy, and apprentices around "
                              "it read the failing input aloud before touching "
                              "a hammer."},
        requires=(Gate.clears("PYTHON", 8),),
        extras={"card": "card_read_the_error",
                "favor": {"mentor": "armorer", "amount": 3}},
    ),
    Quest(
        id="forge_cracked_cells", kind="DELVE", title="The Cracked Ward",
        region="debugging_dungeon", giver="garrick", tier=3,
        premise="Three levels of cells hold programs that worked once, for one "
                "input, on somebody's machine.",
        setup=("Every program in those cells passed a test. That is why they "
                "are in cells and not in a furnace.",
               "They are not wrong everywhere. They are wrong in one place, "
               "under one condition, and they are extremely convincing right up "
               "until then.",
               "Three levels. Do not repair anything you cannot first make fail "
               "in front of a witness."),
        turn_in="Three levels and every repair reproduced first. The Armorer "
                "came down to look, said nothing, and went back up, which "
                "Garrick assures me is enormous.",
        objective={"dungeon": "cracked_ward", "depth": 3,
                   "text": "Reach the third level of the Cracked Ward."},
        consequence={"npc_line": "Third level is cleared and the cells are "
                                 "labelled with the input that convicts each "
                                 "one.",
                     "world": "The Cracked Ward's third level is lit, and each "
                              "cell door carries the input that breaks what is "
                              "inside it."},
        requires=(Gate.quest("forge_read_the_crack"), Gate.mastery("DEBUGGING", 35)),
        extras={"card": "card_trace_by_hand",
                "consumable": {"id": "probe_scroll", "count": 3}},
    ),
    Quest(
        id="forge_annealing", kind="MASTERY", title="The Annealing Room",
        region="debugging_dungeon", giver="garrick", tier=4,
        premise="Garrick has been given the annealing room on the condition "
                "that somebody demonstrates it can be run by reading rather "
                "than by guessing.",
        setup=("They are giving me a room. Me. On one condition.",
               "Two of the difficult repairs, no spells, inside the time, in "
               "front of the Armorer. And it has to be you, because he has "
               "already watched me and he wants to watch the method, not the "
               "apprentice.",
               "If it goes badly I keep my bench and we try in the spring. It "
               "is not the kind of thing you only get one of."),
        turn_in="Both. Unaided, in the time, and he took the key off his own "
                "belt. The room is mine. I am going to be insufferable about "
                "this for years.",
        objective={"skill": "DEBUGGING", "difficulty": "MEDIUM", "count": 2,
                   "unaided": True, "under_target": True,
                   "text": "Clear two Medium debugging encounters unaided and "
                           "inside the target time."},
        consequence={"npc_line": "My room. My rules, which are the Armorer's "
                                 "rules, which are read it before you touch it.",
                     "world": "The Annealing Room is lit and staffed, and a warm "
                              "tunnel runs from the forge up into the village."},
        requires=(Gate.quest("forge_cracked_cells"),
                  Gate.mastery("DEBUGGING", 55), Gate.unaided("DEBUGGING", 4)),
        extras={"town_upgrade": "annealing_room", "set_item": "testsmith_ring",
                "shortcut": "forge_tunnel",
                "favor": {"mentor": "armorer", "amount": 8}},
    ),
    Quest(
        id="dungeon_ilsa_cell", kind="PUZZLE", title="The Input That Convicts",
        region="debugging_dungeon", giver="ilsa", tier=3,
        premise="Ilsa cannot condemn a program until somebody produces the "
                "input that breaks it, and the prisoners know it.",
        setup=("Every program in my cells insists it is correct. Most of them "
                "are, mostly.",
               "I do not need an argument. I need an input. One input, in "
               "writing, that makes it do the thing it says it never does.",
               "Two of them are due for release in a week. I would rather they "
               "were not."),
        turn_in="Two inputs, both reproduced in front of witnesses. Neither is "
                "getting out, and both of them knew the moment you read the "
                "input aloud.",
        objective={"puzzle": "BREAK_IT", "count": 2,
                   "text": "Supply the input that breaks two plausible "
                           "programs."},
        consequence={"npc_line": "I do not argue with a program any more. I ask "
                                 "for the input, and if nobody has one, it "
                                 "walks.",
                     "world": "Ilsa's cell block posts a breaking input on every "
                              "occupied door, in her handwriting."},
        requires=(Gate.clears("TESTING", 3),),
        extras={"card": "card_boundaries",
                "favor": {"mentor": "testsmith", "amount": 4}},
    ),
    Quest(
        id="dungeon_lost_hammer", kind="RECOVERY", title="The Hammer That Was "
                                                         "Put Down",
        region="debugging_dungeon", giver="ilsa", tier=2,
        premise="The Armorer's old repair hammer was put down mid-repair on the "
                "night of the Shattering and nobody has found it since.",
        setup=("He will not ask for it. He has been using a borrowed one for "
                "two years and saying nothing, which is his entire personality.",
               "It was put down, not lost. He was in the middle of a repair "
               "when the Shattering came and he set it down beside the work.",
               "So it is beside a repair. Find a plate that was never finished "
               "and the hammer will be lying next to it where a working person "
               "would put it."),
        turn_in="Next to an unfinished plate on the second level, exactly where "
                "somebody who intended to come back would leave it. He has not "
                "said anything. He has also not put it down.",
        objective={"lost": "The Armorer's repair hammer",
                   "condition": "Find the plate that was never finished. The "
                                "hammer is where a working person would have "
                                "set it.",
                   "found_in": "debugging_dungeon",
                   "text": "Find the unfinished repair in the cells."},
        consequence={"npc_line": "He has it back. He has said nothing about it "
                                 "and he has not put it down once.",
                     "world": "The Armorer works with his own hammer again, and "
                              "the unfinished plate hangs finished above his "
                              "bench."},
        requires=(Gate.stat("armor_repairs", 3),),
        extras={"card": "card_read_the_error",
                "consumable": {"id": "focus_elixir", "count": 2}},
    ),

    # -- Complexity Tower --------------------------------------------------
    Quest(
        id="tower_twice_the_lamps", kind="RELIEF", title="Twice the Lamps",
        region="complexity_tower", giver="ember", tier=3,
        premise="Every floor of the tower has twice the lamps of the one below, "
                "and Ember has been lighting them in the order she reaches them.",
        setup=("Ground floor, two lamps. First floor, four. Second, eight. I "
                "have opinions about the architect.",
               "By the sixth floor it is not a job any more, it is an "
               "arithmetic problem wearing a job.",
               "Before I climb another floor I want to know what the climb "
               "costs. Not how heavy the oil is. What the climb costs."),
        turn_in="Doubling per floor, so the top floor alone is more than every "
                "floor beneath it combined. That is not a lamp problem. I am "
                "taking it to the guild.",
        objective={"task": "Cost out the lamp rounds floor by floor",
                   "family": "big_o", "count": 3,
                   "text": "Clear three complexity encounters."},
        consequence={"npc_line": "The guild has hired four more lighters for "
                                 "the upper floors. Because you counted the "
                                 "work per floor instead of counting floors.",
                     "world": "The tower's lower floors are fully lit, and a "
                              "cost-board at the stair foot shows what each "
                              "storey takes."},
        requires=(Gate.clears("BIG_O", 4),),
        extras={"card": "card_count_per_element",
                "favor": {"mentor": "oracle", "amount": 3}},
    ),
    Quest(
        id="tower_flues", kind="DELVE", title="The Flues",
        region="complexity_tower", giver="ember", tier=3,
        premise="The service shafts between floors are the only way to carry "
                "oil upward, and each one is twice the climb of the last.",
        setup=("The flues run between floors. They are how the oil goes up, "
                "and each flue is twice the climb of the one below it.",
               "Brute strength gets you to the third and then stops getting you "
               "anywhere, which the architect clearly found amusing.",
               "Four flues. There is a way up that is not climbing, and it is "
               "up there, and nobody has been high enough to find it."),
        turn_in="Four flues, and there is a counterweight system at the fourth "
                "that has been waiting two hundred years for somebody to get "
                "high enough to pull the lever.",
        objective={"dungeon": "doubling_stair", "depth": 4,
                   "text": "Reach the fourth landing of the Doubling Stair."},
        consequence={"npc_line": "The counterweight runs. Oil goes up on a rope "
                                 "now and I go up with it.",
                     "world": "A counterweighted hoist runs the tower's flues, "
                              "and lamplight shows on the upper floors."},
        requires=(Gate.quest("tower_twice_the_lamps"),),
        extras={"consumable": {"id": "insight_tonic", "count": 1},
                "codex": "codex_cost"},
    ),
    Quest(
        id="tower_staves_load", kind="RIDDLE", title="What a Trip Costs",
        region="complexity_tower", giver="stave", tier=3,
        premise="Stave prices every carrying job the same way and has never "
                "once been argued out of it.",
        setup=("People ask me what it costs to carry a load up. They always ask "
                "how heavy it is.",
               "Weight is not the price. I will carry a heavy thing up one "
               "floor for a coin.",
               "Here is the question, and everybody in this tower gets it "
               "wrong. A job that does a fixed amount of work for each of a "
               "hundred crates, and a job that does a hundred crates of work "
               "for each of a hundred crates. What is the difference called."),
        turn_in="Linear against quadratic. Sequential work adds, nested work "
                "multiplies. Say it to the guild for me, because they will not "
                "hear it from a porter.",
        objective={"question": "Work done once per item, against work done "
                               "once per item per item. What are those two "
                               "costs called?",
                   "answers": ["o(n) and o(n^2)", "linear and quadratic",
                               "o(n), o(n^2)", "n and n squared",
                               "linear, quadratic", "o(n) o(n2)"],
                   "skill": "BIG_O",
                   "explain": "Sequential work adds. Nested work multiplies. "
                              "That is the whole difference, and it is the "
                              "difference between a job and an impossibility.",
                   "text": "Answer Stave on the stair."},
        consequence={"npc_line": "I quote by the nesting now, not the weight. "
                                 "My rates have gone up and my back has stopped "
                                 "hurting.",
                     "world": "Stave's rate card hangs at the tower door, "
                              "priced by nesting rather than by weight."},
        requires=(Gate.clears("BIG_O", 5),),
        extras={"card": "card_count_per_element",
                "favor": {"mentor": "oracle", "amount": 4}},
    ),
    Quest(
        id="tower_top_lamp", kind="MASTERY", title="The Lamp at the Top",
        region="complexity_tower", giver="ember", tier=4,
        premise="The top floor cannot be lit by climbing it. It has never been "
                "lit.",
        setup=("The top floor has been dark since the tower was built, because "
                "the only way anyone has tried to reach it is by doing twice "
                "the work of the floor below.",
               "It cannot be brute-forced. That is not a challenge, it is an "
               "arithmetic fact, and the architect knew it when he drew it.",
               "Two of the hard problems, unaided, inside the time, and the "
               "counterweight will take you the rest of the way. I have wanted "
               "to see the top of my own tower for nineteen years."),
        turn_in="It is lit. From the top floor you can see the Coliseum, the "
                "Ruins, the Wastes, and a castle with no lights in it at all. "
                "Ember has not said anything for ten minutes.",
        objective={"skill": "BIG_O", "difficulty": "MEDIUM", "count": 2,
                   "unaided": True, "under_target": True,
                   "text": "Clear two Medium complexity encounters unaided and "
                           "inside the target time."},
        consequence={"npc_line": "Nineteen years, and the view is worth it, and "
                                 "I am never climbing it again.",
                     "world": "The tower's top lamp burns, visible from every "
                              "region in the Realms after dark."},
        requires=(Gate.quest("tower_flues"), Gate.mastery("BIG_O", 55),
                  Gate.unaided("BIG_O", 3)),
        extras={"title": "Lamplighter of the Fourteenth",
                "incantation": "weigh", "codex": "codex_gates",
                "favor": {"mentor": "oracle", "amount": 8}},
    ),

    # -- The Coding Coliseum -----------------------------------------------
    Quest(
        id="coliseum_first_bout", kind="ESCORT", title="Three Bouts",
        region="coding_coliseum", giver="junia", tier=3,
        premise="Junia sells tickets to bouts nobody wins, and she has a theory "
                "about why that she cannot get anybody to test.",
        setup=("The sand does not care how much you know. It cares how fast you "
                "stop deciding.",
               "Three bouts, back to back, on the clock. If you lose one you "
               "get the next one — the crowd stays, the clock resets, nothing "
               "about the day is over.",
               "I have watched four hundred bouts and the ones people lose, "
               "they lose in the first ten seconds, standing still."),
        turn_in="Three bouts, one lost, and you walked straight into the next "
                "one. Four hundred bouts and that is the first time I have seen "
                "someone lose one and not leave.",
        objective={"count": 3, "failures_allowed": 1, "seconds": 0,
                   "recover": "A lost bout costs the bout. The clock resets and "
                              "the next one starts.",
                   "text": "Clear three encounters in one run, failing no more "
                           "than once."},
        consequence={"npc_line": "I tell people about the one you lost, not the "
                                 "two you won. It sells more tickets and it is "
                                 "better advice.",
                     "world": "The Coliseum's near stand is patched and "
                              "occupied, and the bout board carries your name."},
        requires=(Gate.clears("SPEED", 2),),
        extras={"consumable": {"id": "whetstone", "count": 2},
                "card": "card_start_before_certain"},
    ),
    Quest(
        id="coliseum_under_arena", kind="DELVE", title="Under the Arena",
        region="coding_coliseum", giver="junia", tier=4,
        premise="Beneath the sand are the holding pens, and whatever the "
                "Chronomancer keeps down there has not been inventoried since "
                "the Shattering.",
        setup=("Three levels under the sand. Holding pens, the old prize vault, "
                "and something the Chronomancer does not discuss.",
               "You can hear the clock through the ceiling the whole way down, "
               "which some people find motivating and most people find is the "
               "worst thing they have ever experienced.",
               "No hints down there. Not as a rule — there is simply nothing "
               "down there that helps."),
        turn_in="All three, with the clock audible the whole way. The prize "
                "vault still has prizes in it and one of them has your name on "
                "it already, which the Chronomancer refuses to explain.",
        objective={"dungeon": "under_arena", "depth": 3,
                   "text": "Reach the third level Under the Arena."},
        consequence={"npc_line": "Prize vault is open. It has been closed since "
                                 "before I was born and there is a llama in it "
                                 "now, which I am told is yours.",
                     "world": "The prize vault beneath the arena stands open, "
                              "and the holding pens are clean and lit."},
        requires=(Gate.quest("coliseum_first_bout"), Gate.mastery("SPEED", 45)),
        extras={"consumable": {"id": "whetstone", "count": 3},
                "codex": "codex_gates"},
    ),
    Quest(
        id="coliseum_full_stands", kind="MASTERY", title="The Full Stands",
        region="coding_coliseum", giver="junia", tier=5,
        premise="One card, three bouts, unaided, on the clock, in front of a "
                "Coliseum that has not been full in forty years.",
        setup=("I have sold every seat. Every seat, for the first time since "
                "the Chronomancer took the arena.",
               "Three of the difficult ones, no spells, inside the time. They "
               "are not here to see you win. They are here to see somebody sit "
               "down in front of a blank slate and start writing without the "
               "long pause.",
               "If it goes badly, the tickets are good for the next card. I "
               "printed that on them. It was not optimism, it was arithmetic."),
        turn_in="Three, unaided, inside the time, and the pause before you "
                "started was not there. Forty years since this place was full "
                "and they are still in the stands an hour later.",
        objective={"skill": "SPEED", "difficulty": "MEDIUM", "count": 3,
                   "unaided": True, "under_target": True,
                   "text": "Clear three Medium encounters unaided and inside "
                           "the target time."},
        consequence={"npc_line": "They come specifically to watch you. I have "
                                 "raised prices twice and nobody has complained "
                                 "once.",
                     "world": "The Coliseum's stands are restored and full on "
                              "every card, and the Undergate to the castle road "
                              "stands unbarred."},
        requires=(Gate.quest("coliseum_under_arena"), Gate.mastery("SPEED", 60),
                  Gate.bosses(6)),
        extras={"town_upgrade": "coliseum_stands", "title": "Champion of the Sand",
                "set_item": "nullbane_greaves", "shortcut": "arena_undergate",
                "favor": {"mentor": "chronomancer", "amount": 10}},
    ),
    Quest(
        id="coliseum_footprints", kind="RIDDLE", title="What the Footprints Say",
        region="coding_coliseum", giver="bosk", tier=3,
        premise="Bosk rakes the sand between bouts and has learned to read the "
                "losses in the footprints.",
        setup=("I rake out the prints between bouts. You would be amazed what "
                "they say.",
               "There is one pattern I see in every single loss. A pair of feet, "
               "close together, not moving, for a long time, right at the mark.",
               "So tell me. When somebody knows the answer and loses anyway, "
               "what did they spend it on."),
        turn_in="Deciding whether they knew it. Every time. The knowing was "
                "never the problem and the sand has been saying so for forty "
                "years.",
        objective={"question": "Somebody who knows the answer still loses on "
                               "the clock. What did the time go on?",
                   "answers": ["deciding", "hesitation", "hesitating",
                               "deciding whether they knew it", "doubt",
                               "doubting", "thinking about whether they knew"],
                   "skill": "SPEED",
                   "explain": "Time-to-first-keystroke, not time-to-solution. "
                              "The knowledge was there the whole time and the "
                              "clock does not distinguish.",
                   "text": "Answer Bosk on the sand."},
        consequence={"npc_line": "I rake a line at the mark now. People who "
                                 "stand behind it know what they are doing. "
                                 "Some of them start moving sooner.",
                     "world": "A raked line runs across the Coliseum sand at "
                              "the starting mark, and fighters step over it "
                              "rather than stand behind it."},
        requires=(Gate.clears("SPEED", 4),),
        extras={"card": "card_start_before_certain",
                "favor": {"mentor": "chronomancer", "amount": 4}},
    ),

    # -- The Null King's Castle --------------------------------------------
    Quest(
        id="castle_no_signs", kind="HUNT", title="Nothing Is Labelled",
        region="null_kings_castle", giver="steward", tier=4,
        premise="The Steward keeps a castle where the King removed every sign, "
                "and he would like to know whether the rooms can still be "
                "identified without them.",
        setup=("There were never any signs. That is not quite true. There were "
                "signs, and he took them down, and he left everything else "
                "exactly as it was.",
               "The rooms still are what they are. A room that asks about "
               "counting is still a room that asks about counting. It simply "
               "does not say so on the door any more.",
               "Walk five rooms. Tell me what each one was, before he took the "
               "sign down."),
        turn_in="Five rooms, five names, all correct, and you did not once ask "
                "me for a hint. He took the signs down to see whether anyone "
                "would still know. Somebody still knows.",
        objective={"family": "pattern_recognition", "count": 5, "unaided": True,
                   "text": "Name five unlabelled rooms, unaided."},
        consequence={"npc_line": "Five rooms have their names back. Written by "
                                 "you, in chalk, which he has not wiped off.",
                     "world": "Five halls of the castle carry chalked names "
                              "again, and none of them have been erased."},
        requires=(Gate.mastery("RECALL", 45), Gate.bosses(6)),
        extras={"card": "card_refuse_to_answer_twice", "codex": "codex_castle",
                "consumable": {"id": "insight_tonic", "count": 2}},
    ),
    Quest(
        id="castle_unlabelled_halls", kind="DELVE", title="The Unlabelled Halls",
        region="null_kings_castle", giver="steward", tier=5,
        premise="Nine floors with no signage, no announcements and no pattern "
                "to what any room intends to ask.",
        setup=("Nine floors. I have keys to all of them and I have walked three.",
               "The halls do not escalate in difficulty and they do not group "
               "by kind. They are in the order the King put them in, and the "
               "order is the point.",
               "Five floors would be further than anyone has gone since he "
               "closed the gates. I am not asking you to go to the top. Not "
               "today."),
        turn_in="Five floors. No labels, no warnings, nothing announcing "
                "itself, and you named every room you walked into before it "
                "opened its mouth. There are four floors above you and he knows "
                "you are coming.",
        objective={"dungeon": "unlabelled_halls", "depth": 5,
                   "text": "Reach the fifth floor of the Unlabelled Halls."},
        consequence={"npc_line": "Five floors. I have been Steward for thirty "
                                 "years and I have walked three.",
                     "world": "Five floors of the castle stand lit and "
                              "mapped, and the stair to the sixth is no longer "
                              "barred."},
        requires=(Gate.quest("castle_no_signs"), Gate.mastery("RECALL", 60),
                  Gate.bosses(8)),
        extras={"set_item": "nullbane_helm", "title": "Unlabelled",
                "codex": "codex_castle"},
    ),
    Quest(
        id="castle_stewards_names", kind="RECOVERY", title="The Signs He Took Down",
        region="null_kings_castle", giver="steward", tier=5,
        premise="The Steward has worked out that the King did not destroy the "
                "signs. He stored them, which means he meant to put them back.",
        setup=("I have been thinking about your chalk.",
               "He did not burn the signs. A man who wanted them gone would "
               "have burned them. They are somewhere in this castle, stacked, "
               "in order, by a man who intended to come back and hang them up "
               "again.",
               "Find them. I am not asking for the castle. I am asking for the "
               "names of the rooms in the place where I have worked for thirty "
               "years."),
        turn_in="Stacked, in order, labelled in his own hand, in a room off the "
                "eighth floor with a chair in it facing them. He sat with them. "
                "That is the part I am going to think about.",
        objective={"lost": "Every sign the Null King took down",
                   "condition": "Find the room off the eighth floor that is not "
                                "a trial room. It is the only one with a chair "
                                "in it.",
                   "found_in": "null_kings_castle",
                   "text": "Find the sign room off the eighth floor."},
        consequence={"npc_line": "Every hall has its name back. He will see "
                                 "them on his way down, which I intend to be "
                                 "standing somewhere visible for.",
                     "world": "The castle's halls carry their original signs "
                              "again, hung by the Steward, and the place stops "
                              "being a maze and starts being a building."},
        requires=(Gate.quest("castle_unlabelled_halls"),
                  Gate.mastery("RECALL", 70)),
        extras={"set_item": "nullbane_sigil", "title": "Keeper of the Names",
                "card": "card_refuse_to_answer_twice"},
    ),
]


# ---------------------------------------------------------------------------
# Chains
# ---------------------------------------------------------------------------
# A chain is an ordered list of quest ids and a person whose life gets bigger as
# it goes. The prerequisite linking each step to the one before it is NOT
# authored on the quests — `_link` injects it — so a chain can never end up with
# a step that is reachable out of order, and an orphan step is a validate()
# failure rather than a bug somebody finds in play.

CHAINS = (
    QuestChain(
        id="village_rebuild", title="What Odile Is Building",
        region="python_village", giver="odile",
        premise="A mason with no crew, a village made of scaffolding, and a "
                "workshop she has been describing to people for two years.",
        steps=("village_beam_count", "village_mortar_weeds", "village_doorframe",
               "village_raising"),
        epilogue="Odile's workshop stands at the centre of the village with the "
                 "forge-light on after dark, and she has stopped calling it "
                 "'the workshop I am going to build'.",
    ),
    QuestChain(
        id="fields_weeding", title="Warden Harrow's Season",
        region="fields_of_syntax", giver="harrow",
        premise="Four hundred acres, one warden, and weather coming.",
        steps=("fields_first_weeding", "fields_fence_line", "fields_harvest_run"),
        epilogue="The Fields come in whole for the first season since the "
                 "Shattering, and there is a dry road from the granary to the "
                 "village door.",
    ),
    QuestChain(
        id="highlands_ledger", title="The Index of the Plateau",
        region="hashmap_highlands", giver="vela",
        premise="Nine thousand vaults, one tollkeeper, and a ledger that has "
                "never once been true.",
        steps=("highlands_double_keys", "highlands_sunken_index",
               "highlands_ledger_closed"),
        epilogue="The Ledger House stands open on the ridge. One key, one "
                 "vault, written down exactly once, and Vela's name is on the "
                 "door under yours.",
    ),
    QuestChain(
        id="stringwood_names", title="The Namer and the Long Thing",
        region="stringwood_labyrinth", giver="quill",
        premise="Quill names what the wood contains. Lately the wood has been "
                "answering back, in anagrams.",
        steps=("stringwood_same_coat", "stringwood_letterfall",
               "stringwood_true_name"),
        epilogue="The register is true, the Deeps are lit, and a python the "
                 "length of a cart sits at the edge of Quill's clearing in the "
                 "evenings being deliberately unhelpful.",
    ),
    QuestChain(
        id="caverns_zero", title="Counting From Zero",
        region="array_caverns", giver="dorn",
        premise="A quartermaster who has spent eleven years reaching into solid "
                "rock for an alcove that was never there.",
        steps=("caverns_off_by_one", "caverns_lamp_run", "caverns_deeps"),
        epilogue="The alcove row burns end to end, numbered from zero in white "
                 "paint a foot high, and a cage lift drops from the last alcove "
                 "into Greave's shafts.",
    ),
    QuestChain(
        id="marsh_levee_work", title="The Levee",
        region="sliding_window_marsh", giver="fenn",
        premise="A man who has rebuilt the same stretch of wall from the "
                "beginning, eleven days at a time, for two years.",
        steps=("marsh_first_breach", "marsh_never_restart", "marsh_sluice_delve",
               "marsh_levee_holds"),
        epilogue="The levee holds the length of the marsh, the old sluice "
                 "mechanism runs itself, and Fenn sleeps through the night.",
    ),
    QuestChain(
        id="pass_convoy", title="Both Ends of the Pass",
        region="twin_pointer_pass", giver="ondra",
        premise="Forty carts, two ends, one winter, and a pack animal that has "
                "been following the convoys for six years without explanation.",
        steps=("pass_two_carts", "pass_shorter_post", "pass_convoy_run"),
        epilogue="Three regions ate this winter. No cart on the pass has turned "
                 "round since, and the llama sleeps at whichever cairn you did.",
    ),
    QuestChain(
        id="mines_lift", title="Greave's Grandfather's Lift",
        region="stack_queue_mines", giver="greave",
        premise="A century of ore under four sealed levels, and an engineer "
                "whose grandfather left him a machine and no rota.",
        steps=("mines_top_first", "mines_cart_shafts", "mines_liftworks"),
        epilogue="The Liftworks run day and night, oldest crew out the front, "
                 "new arrivals on the back, and nothing waits at the bottom of "
                 "a shaft any more.",
    ),
    QuestChain(
        id="citadel_rotation", title="The Citadel Turns, the Plans Do Not",
        region="matrix_citadel", giver="lorne",
        premise="Eleven years of an archivist apologising to guards for maps "
                "that do not match the building they are standing in.",
        steps=("citadel_plans", "citadel_keep", "citadel_true_north"),
        epilogue="The great survey hangs in the plan room, correct in all four "
                 "orientations, and Lorne has not apologised to anybody in "
                 "weeks.",
    ),
    QuestChain(
        id="forest_descent", title="Down and Back Out",
        region="recursive_forest", giver="halla",
        premise="Foresters who go four levels into the same clearing and come "
                "out days later with opinions instead of numbers.",
        steps=("forest_smaller_forest", "forest_unwind",
               "forest_stopping_condition", "forest_inner_grove"),
        epilogue="The forest is one forest again, a ropeway runs from the inner "
                 "grove to the canopy, and a jaguar walks the paths beside you "
                 "and will not be discussed.",
    ),
    QuestChain(
        id="canopy_climb", title="The Strictest Place in the Realms",
        region="binary_tree_canopy", giver="wren",
        premise="A canopy that permits exactly two branches per fork, a storm "
                "that did not care, and one bird in the wrong place.",
        steps=("canopy_two_branches", "canopy_nest_order", "canopy_rookery_spine",
               "canopy_lost_fledgling"),
        epilogue="The crown is knitting closed, the spine is roped to the third "
                 "storey, and Wren teaches bounds from the crown downward to "
                 "anyone who will stand still.",
    ),
    QuestChain(
        id="wastes_relay", title="The Last Courier",
        region="graph_wastes", giver="corvin",
        premise="Eleven years of walking three times further than the job "
                "requires, in a land where every ruin has four exits.",
        steps=("wastes_four_roads", "wastes_rings_of_light", "wastes_undercity",
               "wastes_waystation"),
        epilogue="There is a map of the Lattice, a signed road to the "
                 "Citadel, and a waystation in the middle of the Wastes with "
                 "nine people in it and not enough bowls.",
    ),
    QuestChain(
        id="ruins_ledger", title="The Account of the Ruins",
        region="dp_ruins", giver="tolliver",
        premise="A tallykeeper counting the same stones for a lifetime because "
                "nobody ever wrote down what they had already answered.",
        steps=("ruins_paid_twice", "ruins_lit_tiles", "ruins_vaults",
               "ruins_ledger_balanced"),
        epilogue="Every tile in the Ruins is lit, the account balances, and "
                 "Tolliver sits on the terrace counting nothing at all.",
    ),
    QuestChain(
        id="forge_cracks", title="Garrick Reads the Crack",
        region="debugging_dungeon", giver="garrick",
        premise="An apprentice who has been told to read a fracture and has no "
                "idea what that sentence means.",
        steps=("forge_read_the_crack", "forge_cracked_cells", "forge_annealing"),
        epilogue="Garrick runs the annealing room, reads every crack aloud "
                 "before he touches it, and is insufferable.",
    ),
    QuestChain(
        id="tower_ascent", title="Ember's Tower",
        region="complexity_tower", giver="ember",
        premise="Nineteen years of lighting a tower whose top floor cannot be "
                "reached by climbing harder.",
        steps=("tower_twice_the_lamps", "tower_flues", "tower_staves_load",
               "tower_top_lamp"),
        epilogue="The top lamp of the Complexity Tower burns, visible from "
                 "every region in the Realms after dark, and Ember is never "
                 "climbing it again.",
    ),
    QuestChain(
        id="coliseum_card", title="A Full House on the Sand",
        region="coding_coliseum", giver="junia",
        premise="A ticket clerk with four hundred bouts of evidence about why "
                "people lose, and nobody willing to test it.",
        steps=("coliseum_first_bout", "coliseum_under_arena",
               "coliseum_full_stands"),
        epilogue="Every seat sold, the prize vault open, and the Undergate to "
                 "the castle road unbarred beneath it all.",
    ),
    QuestChain(
        id="castle_names", title="The Signs He Took Down",
        region="null_kings_castle", giver="steward",
        premise="A steward of thirty years in a castle whose every label was "
                "removed by a king who, it turns out, kept them.",
        steps=("castle_no_signs", "castle_unlabelled_halls",
               "castle_stewards_names"),
        epilogue="Every hall in the castle carries its name again, hung by the "
                 "Steward, who intends to be standing somewhere visible when "
                 "the King comes down.",
    ),
)


def _link(quests: list, chains: tuple) -> tuple:
    """Inject the two prerequisites nobody should have to author by hand: the
    region must be open, and a chain step waits on the step before it."""
    position = {}
    for chain in chains:
        for index, step_id in enumerate(chain.steps):
            position[step_id] = (chain.id, chain.steps[index - 1] if index else "")

    linked = []
    for quest in quests:
        needs = list(quest.requires)
        region_gate = Gate.region_open(quest.region)
        if region_gate not in needs:
            needs.insert(0, region_gate)
        chain_id, previous = position.get(quest.id, ("", ""))
        if previous:
            previous_gate = Gate.quest(previous)
            if previous_gate not in needs:
                needs.append(previous_gate)
        linked.append(replace(quest, requires=tuple(needs), chain=chain_id))
    return tuple(linked)


# ---------------------------------------------------------------------------
# What each quest pays in kind
# ---------------------------------------------------------------------------
# The material half of every reward, in one table rather than sprinkled through
# seventy-four authored blocks. That is the same reasoning REWARD_TIERS is built
# on: a curve you can read top to bottom cannot drift one generous quest at a
# time, and a reviewer can check "does the marsh pay marsh things" by reading one
# screen instead of grepping.
#
# Three patterns run through it, and they are the answer to "relevant to the
# area".
#
#   THE METAL IS THE GROUND. A quest pays the metal of its own region and no
#   other. validate() enforces it against forge.REGION_METAL, so the Mines
#   cannot start paying tilegold because somebody copied a line.
#
#   THE POTION IS THE WEATHER. Poison country pays antidotes, because poison
#   country is the only place the antidote is the interesting item. Void country
#   pays focus, because VOIDED stops focus coming back and a full pouch is the
#   honest answer to that. Cold and stone country pay health. The strength is
#   whatever that region's band is allowed to brew and never a drop more —
#   potions.found_at() decides, not this table.
#
#   THE GEAR IS THE WEATHER TOO, WORN. A region hands over the ward, the boots
#   or the weapon keyed to its own element: the thing that answers what that
#   place does to you. Which is tactical, and is therefore allowed. None of it
#   touches a problem, an assertion or a hint.
#
# Four regions pay no gear at all and that is deliberate rather than unfinished.
# The Ruins, the Coliseum, the Village and the Fields are NEUTRAL — elements.py
# gives them no affinity and no hazard, so there is no ward to hand over and
# pretending otherwise would be the first lie in the table. They pay in metal,
# in a deeper pouch and in credit instead. The Canopy is the one neutral region
# that pays boots, because it is a place you cross rather than a place that
# fights you, and the Debugging Dungeon pays no gear because it is a forge: what
# it has to give is stock.
#
# Everything here is folded onto the authored quests by _pay_in_kind(), which
# refuses to overwrite an extra the quest already declares. The prose stays where
# the author put it.

_MATERIAL = {

    # -- Python Village: no metal, one potion, and the trader's goodwill. The
    # town is GUIDED and the only thing it is allowed to brew is a thimble.
    "village_beam_count":      {"potion": ("health_minor", 2)},
    "village_mortar_weeds":    {"potion": ("health_minor", 2)},
    "village_doorframe":       {"potion": ("health_minor", 3), "credit": True},
    "village_raising":         {"potion": ("health_minor", 3), "credit": True},
    "village_deep_well":       {"potion": ("health_minor", 3)},
    "village_pels_route":      {"potion": ("health_minor", 2)},

    # -- Fields of Syntax: the first ground that gives up metal at all, and it
    # gives up the softest there is.
    "fields_first_weeding":    {"potion": ("health_minor", 2)},
    "fields_fence_line":       {"potion": ("focus_minor", 2), "metal": 1},
    "fields_harvest_run":      {"potion": ("health_minor", 3), "metal": 2,
                                "regalia": "field_collar"},
    "fields_nils_gap":         {"potion": ("health_minor", 2)},
    "fields_scarecrow":        {"potion": ("focus_minor", 2), "metal": 1},

    # -- Hashmap Highlands: LIGHTNING. Focus, because the work here is holding a
    # key and its place in your head at the same time.
    "highlands_double_keys":   {"potion": ("focus_small", 2), "metal": 1,
                                "credit": True},
    "highlands_sunken_index":  {"potion": ("focus_small", 3), "metal": 2,
                                "regalia": "keyed_bell"},
    "highlands_ledger_closed": {"potion": ("health_small", 3), "metal": 3,
                                "gear": "hashblade"},
    "highlands_brants_wager":  {"potion": ("focus_small", 2)},
    "highlands_lost_keyring":  {"potion": ("health_small", 3),
                                "gear": "earthed_sabatons"},

    # -- Stringwood Labyrinth: POISON, and the first place an antidote is worth
    # carrying rather than reading about.
    "stringwood_same_coat":    {"potion": ("antidote_minor", 2), "metal": 1},
    "stringwood_letterfall":   {"potion": ("antidote_minor", 3), "metal": 2},
    "stringwood_true_name":    {"potion": ("antidote_minor", 3),
                                "gear": "ward_poison"},
    "stringwood_moss_map":     {"potion": ("health_small", 2), "credit": True},

    # -- Array Caverns: BRUTE. Stone and the weight above it, so: health, and
    # the offhand ward, which is the only thing that helps against weight.
    "caverns_off_by_one":      {"potion": ("health_minor", 2)},
    "caverns_lamp_run":        {"potion": ("health_small", 2), "metal": 1,
                                "credit": True},
    "caverns_deeps":           {"potion": ("health_small", 3), "metal": 2,
                                "gear": "ward_brute"},
    "caverns_esk_count":       {"potion": ("health_minor", 2)},
    "caverns_lost_lamp":       {"potion": ("health_small", 2), "credit": True},

    # -- Sliding Window Marsh: POISON at a band that can finally brew the good
    # antidote. This is the brief's example, paid literally.
    "marsh_first_breach":      {"potion": ("antidote_small", 2), "metal": 1},
    "marsh_never_restart":     {"potion": ("antidote_small", 3), "metal": 2,
                                "regalia": "sealed_muzzle"},
    "marsh_sluice_delve":      {"potion": ("antidote_small", 3),
                                "gear": "marsh_waders"},
    "marsh_levee_holds":       {"potion": ("antidote_small", 3), "metal": 3,
                                "gear": "window_staff"},
    "marsh_sables_ferry":      {"potion": ("health_small", 2), "credit": True},

    # -- Twin Pointer Pass: COLD, at the snow line. Crampons are not a luxury
    # here and the quest that pays them says so.
    "pass_two_carts":          {"potion": ("health_small", 2), "metal": 1,
                                "credit": True},
    "pass_shorter_post":       {"potion": ("focus_small", 3), "metal": 2,
                                "gear": "crampons"},
    "pass_convoy_run":         {"potion": ("health_small", 3), "metal": 3,
                                "gear": "twin_sabers"},
    "pass_kell_riddle":        {"potion": ("focus_small", 2)},

    # -- Stack & Queue Mines: FIRE. Boots first, then the ward, in that order,
    # because the floor gets you long before anything else does.
    "mines_top_first":         {"potion": ("health_small", 2), "metal": 1},
    "mines_cart_shafts":       {"potion": ("health_small", 3), "metal": 2,
                                "gear": "cinder_greaves"},
    "mines_liftworks":         {"potion": ("health_small", 3), "metal": 3,
                                "gear": "ward_fire", "credit": True},
    "mines_pitch_nesting":     {"potion": ("focus_small", 2), "credit": True},

    # -- Matrix Citadel: BRUTE, and the first band that can brew a Flask.
    "citadel_plans":           {"potion": ("health_small", 2), "metal": 1,
                                "credit": True},
    "citadel_keep":            {"potion": ("health_medium", 2), "metal": 2,
                                "gear": "matrix_bow"},
    "citadel_true_north":      {"potion": ("focus_medium", 2), "metal": 3,
                                "gear": "ward_brute"},
    "citadel_night_watch":     {"potion": ("health_medium", 2), "credit": True},

    # -- Recursive Forest: VOID. Focus throughout, because VOIDED is the status
    # that stops focus returning and a deep pouch is the only answer to it.
    "forest_smaller_forest":   {"potion": ("focus_medium", 2), "metal": 2},
    "forest_unwind":           {"potion": ("focus_medium", 2),
                                "gear": "lanternshoes"},
    "forest_stopping_condition": {"potion": ("focus_medium", 2),
                                  "regalia": "lantern_harness"},
    "forest_inner_grove":      {"potion": ("focus_medium", 2), "metal": 3,
                                "gear": "ward_void"},

    # -- Binary Tree Canopy: NEUTRAL. Open air, no hazard, and the one neutral
    # region that pays boots, because crossing it is the job.
    "canopy_two_branches":     {"potion": ("health_medium", 2), "metal": 2},
    "canopy_nest_order":       {"potion": ("focus_medium", 2)},
    "canopy_rookery_spine":    {"potion": ("health_medium", 2), "metal": 2,
                                "gear": "wayfarers"},
    "canopy_lost_fledgling":   {"potion": ("health_medium", 2)},

    # -- Graph Wastes: LIGHTNING. SHOCKED makes the next hit worse rather than
    # this one, so health is the potion and the ward is the prize.
    "wastes_four_roads":       {"potion": ("health_medium", 2), "metal": 2,
                                "gear": "ward_lightning"},
    "wastes_rings_of_light":   {"potion": ("focus_medium", 2), "metal": 2,
                                "regalia": "lattice_tack"},
    "wastes_undercity":        {"potion": ("health_medium", 2), "metal": 3,
                                "gear": "hashblade_prime"},
    "wastes_waystation":       {"potion": ("health_medium", 2), "metal": 3,
                                "credit": True},

    # -- Dynamic Programming Ruins: NEUTRAL, ELITE band. No weather to ward
    # against, so it pays in the gold prised out of the floor and in the first
    # Flagons anybody has been allowed to carry.
    "ruins_paid_twice":        {"potion": ("focus_medium", 2), "metal": 2},
    "ruins_lit_tiles":         {"potion": ("focus_medium", 2), "metal": 2},
    "ruins_vaults":            {"potion": ("focus_hefty", 1), "metal": 3},
    "ruins_ledger_balanced":   {"potion": ("health_hefty", 1), "metal": 3,
                                "regalia": "counted_barding"},

    # -- Debugging Dungeon: FIRE, and the Armorer's own forge. It pays in stock.
    # No gear here on purpose: the thing this place has to give is faultsteel.
    "forge_read_the_crack":    {"potion": ("health_small", 2), "metal": 1,
                                "credit": True},
    "forge_cracked_cells":     {"potion": ("health_small", 3), "metal": 2},
    "forge_annealing":         {"potion": ("health_small", 3), "metal": 3,
                                "credit": True},
    "dungeon_ilsa_cell":       {"potion": ("focus_small", 3), "metal": 2},
    "dungeon_lost_hammer":     {"potion": ("health_small", 2), "credit": True},

    # -- Complexity Tower: COLD, and every floor costs more than the one below.
    "tower_twice_the_lamps":   {"potion": ("focus_medium", 2), "metal": 2,
                                "gear": "ward_cold", "credit": True},
    "tower_flues":             {"potion": ("focus_medium", 2), "metal": 2},
    "tower_staves_load":       {"potion": ("focus_medium", 2)},
    "tower_top_lamp":          {"potion": ("focus_hefty", 1), "metal": 3},

    # -- The Coding Coliseum: NEUTRAL. A sand floor, a clock and no hints, so
    # there is nothing elemental to hand over and the pay is stock and credit.
    "coliseum_first_bout":     {"potion": ("health_medium", 2), "credit": True},
    "coliseum_under_arena":    {"potion": ("health_hefty", 1), "metal": 3},
    "coliseum_full_stands":    {"potion": ("health_hefty", 2), "metal": 5,
                                "credit": True},
    "coliseum_footprints":     {"potion": ("focus_medium", 2), "metal": 2},

    # -- The Null King's Castle: VOID, rung six, the deepest metal there is.
    # Requirement D lands here: the two Legend-tier quests are the only place in
    # the game that hands over five bars of nullsteel at once, and forge.py's
    # own drop table will not casually match that — a BOSS bundle is three and
    # there is exactly one boss down here.
    "castle_no_signs":         {"potion": ("focus_hefty", 1), "metal": 3,
                                "gear": "recursion_spear"},
    "castle_unlabelled_halls": {"potion": ("focus_hefty", 2), "metal": 5,
                                "gear": "ward_void"},
    "castle_stewards_names":   {"potion": ("health_hefty", 2), "metal": 5,
                                "regalia": "unlabelled_collar"},
}


def _pay_in_kind(quests: list) -> list:
    """Fold _MATERIAL onto the authored quests.

    `metal` is a count and the id is read from the region, so the table cannot
    name the wrong ore. `credit` is a yes-or-no and both the region and the
    amount are read from the quest, so a vendor cannot be paid off-curve. An extra the quest already authored always wins:
    this fold adds the material half of a reward and never edits the half a
    human wrote.
    """
    out = []
    for quest in quests:
        row = _MATERIAL.get(quest.id)
        if not row:
            out.append(quest)
            continue
        extras = dict(quest.extras)
        potion = row.get("potion")
        if potion and "potion" not in extras:
            extras["potion"] = {"id": potion[0], "count": int(potion[1])}
        if row.get("metal") and "metal" not in extras:
            extras["metal"] = {"id": metal_for(quest.region),
                               "count": int(row["metal"])}
        if row.get("gear") and "gear" not in extras:
            extras["gear"] = row["gear"]
        if row.get("regalia") and "regalia" not in extras:
            extras["regalia"] = row["regalia"]
        if row.get("credit") and "vendor_credit" not in extras:
            # The amount comes from the tier, never from the table. Same reason
            # REWARD_TIERS owns the XP curve: a number authored per quest is a
            # number that drifts one generous quest at a time.
            if quest.tier not in VENDOR_CREDIT:
                # Only reachable by marking a tier-1 quest as paying credit,
                # which validate() would also reject. Said here because this runs
                # at import and an unexplained KeyError in a table is a bad
                # half-hour for whoever hits it.
                raise ValueError(
                    f"{quest.id}: tier {quest.tier} pays vendor credit, and "
                    f"VENDOR_CREDIT only prices tiers {sorted(VENDOR_CREDIT)}")
            extras["vendor_credit"] = {"region": quest.region,
                                       "amount": VENDOR_CREDIT[quest.tier]}
        out.append(replace(quest, extras=extras))
    return out


QUESTS = _link(_pay_in_kind(_QUESTS), CHAINS)
QUEST_BY_ID = {q.id: q for q in QUESTS}
CHAIN_BY_ID = {c.id: c for c in CHAINS}
CHAIN_OF_STEP = {step: c.id for c in CHAINS for step in c.steps}
BY_REGION = {r["id"]: [q for q in QUESTS if q.region == r["id"]]
             for r in world.REGIONS}
BY_KIND = {kind: [q for q in QUESTS if q.kind == kind] for kind in KINDS}
BY_GIVER: dict = {}
for _quest in QUESTS:
    BY_GIVER.setdefault(_quest.giver, []).append(_quest)
del _quest


# ---------------------------------------------------------------------------
# The save shape and the context
# ---------------------------------------------------------------------------

STATE_KEY = "quests"


def new_quest_state() -> dict:
    """Everything this module needs persisted. Add it to engine.DEFAULT_STATE
    under STATE_KEY; _merge already forward-fills new keys."""
    return {
        "done": [],            # quest ids, in the order they were turned in
        "active": [],          # accepted and not yet finished
        "seen": [],            # offered at least once, so the log can mark them new
        "progress": {},        # quest id -> {"count": n} while a run is going
        "depths": {},          # dungeon id -> deepest floor reached
        "puzzle_clears": {},   # puzzle kind -> count cleared
        "pets": [],            # PET_DISCOVERIES ids whose condition is known
        "shortcuts": [],       # SHORTCUTS ids that stay open
        "town_upgrades": [],   # TOWN_UPGRADES ids that stay built
        "incantations": [],    # INCANTATION_GRANTS ids awarded out here
        "titles": [],          # honorifics earned from world content
        "regalia": [],         # REGALIA ids owned. Tack, not experience: it makes
                               # a companion speak sooner and more often and it
                               # never moves the tier that decides how deep.
        "regalia_worn": "",    # the one piece in use, REGALIA_ACTIVE_LIMIT of 1
        "npc_lines": {},       # npc id -> the line they say now, forever after
    }


def _shim_skills(ctx: dict):
    class _Shim:
        def __init__(self, data):
            self.mastery = float(data.get("mastery", 0.0))
            self.clears = int(data.get("clears", 0))
            self.unaided_clears = int(data.get("unaided_clears", 0))
    return {name: _Shim(data) for name, data in ctx.get("skills", {}).items()}


def available_in(mode: str) -> bool:
    """Interview Mode has no quest board. A measured run is not a place to be
    handed a reward for something you did yesterday."""
    return mode != config.MODE_INTERVIEW


def context(story_ctx: dict, state: dict | None = None) -> dict:
    """Extend the context story.build_context already produced with the facts
    only the overworld knows. Everything stays a plain dict so the quest log can
    be rendered without importing the engine."""
    ctx = dict(story_ctx)
    state = state or {}
    raw = state.get(STATE_KEY) or {}
    ctx["quests_done"] = set(raw.get("done", []))
    ctx["quests_active"] = set(raw.get("active", []))
    ctx["dungeon_depth"] = dict(raw.get("depths", {}))
    ctx["puzzle_clears"] = dict(raw.get("puzzle_clears", {}))
    ctx["pets_found"] = set(raw.get("pets", []))
    ctx["shortcuts"] = set(raw.get("shortcuts", []))
    ctx["town_upgrades"] = set(raw.get("town_upgrades", []))
    ctx.setdefault("secrets_found", set(state.get("secrets_found", [])))
    if "regions_open" not in ctx:
        ctx["regions_open"] = set(world.unlocked_regions(
            _shim_skills(ctx), set(ctx.get("cleared_bosses", ()))))
    return ctx


# ---------------------------------------------------------------------------
# The board
# ---------------------------------------------------------------------------

def _entry(quest: Quest, ctx: dict, *, state_of: str) -> dict:
    """One row of the quest log, with every number already worked out."""
    needs = [{"text": describe_need(gate, ctx), **need_progress(gate, ctx)}
             for gate in quest.requires]
    unmet = [n for n in needs if not n["met"]]
    chain = CHAIN_BY_ID.get(quest.chain)
    step = chain.steps.index(quest.id) + 1 if chain else 0
    return {
        "id": quest.id, "kind": quest.kind, "title": quest.title,
        "region": quest.region,
        "region_name": world.REGION_BY_ID[quest.region]["name"],
        "giver": quest.giver, "giver_name": speaker_name(quest.giver),
        "tier": quest.tier, "tier_name": quest.tier_name,
        "state": state_of, "premise": quest.premise,
        "objective": dict(quest.objective),
        "objective_text": quest.objective.get("text", ""),
        "reward": quest.reward, "reward_lines": reward_summary(quest.reward),
        "chain": quest.chain, "chain_title": chain.title if chain else "",
        "step": step, "steps": len(chain.steps) if chain else 0,
        "final_step": bool(chain) and step == len(chain.steps),
        "requirements": needs,
        "blocked_by": unmet[0]["text"] if unmet else "",
        "blocked_count": len(unmet),
    }


def available(ctx: dict, state: dict | None = None) -> list:
    """Everything a giver would hand over right now, best story first.

    Ordered by chain position then tier, so a player who is three steps into
    somebody's life is shown the fourth step before they are shown a stranger's
    errand.
    """
    done = ctx.get("quests_done", set())
    active = ctx.get("quests_active", set())
    out = []
    for quest in QUESTS:
        if quest.id in done or quest.id in active:
            continue
        if all(need_met(gate, ctx) for gate in quest.requires):
            out.append(_entry(quest, ctx, state_of="available"))
    out.sort(key=lambda e: (0 if e["chain"] else 1, -e["step"], e["tier"]))
    return out


def active(ctx: dict) -> list:
    return [_entry(QUEST_BY_ID[qid], ctx, state_of="active")
            for qid in ctx.get("quests_active", ()) if qid in QUEST_BY_ID]


def completed(ctx: dict) -> list:
    return [_entry(QUEST_BY_ID[qid], ctx, state_of="done")
            for qid in ctx.get("quests_done", ()) if qid in QUEST_BY_ID]


def locked(ctx: dict, *, limit: int = 0) -> list:
    """What is not offered, and the one thing standing in the way of each.

    Sorted by how close it is, because a locked list that leads with the castle
    teaches the player that the locked list is not worth reading.
    """
    done = ctx.get("quests_done", set())
    active_ids = ctx.get("quests_active", set())
    out = []
    for quest in QUESTS:
        if quest.id in done or quest.id in active_ids:
            continue
        if all(need_met(gate, ctx) for gate in quest.requires):
            continue
        out.append(_entry(quest, ctx, state_of="locked"))
    out.sort(key=lambda e: (e["blocked_count"], e["tier"]))
    return out[:limit] if limit else out


def board(ctx: dict, state: dict | None = None) -> dict:
    """The whole log in one call: what is offered, what is running, what is
    finished, and why the rest is not offered."""
    offered = available(ctx, state)
    return {
        "available": offered,
        "active": active(ctx),
        "done": completed(ctx),
        "locked": locked(ctx),
        "next": next_steps(ctx, state),
        "counts": {"available": len(offered),
                   "active": len(ctx.get("quests_active", ())),
                   "done": len(ctx.get("quests_done", ())),
                   "total": len(QUESTS)},
    }


def region_board(region_id: str, ctx: dict, state: dict | None = None) -> dict:
    """The same, narrowed to one place, for a signpost or a town noticeboard."""
    whole = board(ctx, state)
    for key in ("available", "active", "done", "locked", "next"):
        whole[key] = [e for e in whole[key] if e.get("region") == region_id]
    return whole


def next_steps(ctx: dict, state: dict | None = None, *, limit: int = 3) -> list:
    """Never empty, and that is the point.

    The rule is that learning must not dead-end: if nothing at all is currently
    offered, this returns the nearest locked quests with the single missing
    requirement spelled out, so the answer to 'what now' is always a sentence
    with a number in it rather than a grey wall.
    """
    offered = available(ctx, state)
    if offered:
        return offered[:limit]
    near = locked(ctx, limit=limit)
    for entry in near:
        entry["state"] = "soon"
    return near


def offer(quest_id: str, ctx: dict) -> dict:
    """What the giver actually says when you walk up to them."""
    quest = QUEST_BY_ID[quest_id]
    entry = _entry(quest, ctx, state_of="offer")
    entry["lines"] = list(quest.setup)
    entry["kind_blurb"] = KIND_BLURB[quest.kind]
    if quest.chain:
        entry["chain_premise"] = CHAIN_BY_ID[quest.chain].premise
    return entry


def chain_view(chain_id: str, ctx: dict) -> dict:
    """One person's whole arc, for the log's chain tab."""
    chain = CHAIN_BY_ID[chain_id]
    done = ctx.get("quests_done", set())
    steps = []
    for index, step_id in enumerate(chain.steps):
        quest = QUEST_BY_ID[step_id]
        state_of = ("done" if step_id in done else
                    "available" if all(need_met(g, ctx) for g in quest.requires)
                    else "locked")
        steps.append(_entry(quest, ctx, state_of=state_of))
    finished = all(s["state"] == "done" for s in steps)
    return {
        "id": chain.id, "title": chain.title, "region": chain.region,
        "region_name": world.REGION_BY_ID[chain.region]["name"],
        "giver": chain.giver, "giver_name": speaker_name(chain.giver),
        "premise": chain.premise, "steps": steps,
        "done": sum(1 for s in steps if s["state"] == "done"),
        "total": len(steps), "complete": finished,
        "epilogue": chain.epilogue if finished else "",
        "reward": QUEST_BY_ID[chain.steps[-1]].reward,
    }


def chains_view(ctx: dict) -> list:
    return [chain_view(c.id, ctx) for c in CHAINS]


# ---------------------------------------------------------------------------
# Playing one
# ---------------------------------------------------------------------------
# The engine owns encounters, dungeons and the sandbox. This module owns the
# question "did that count, and is this finished" — which keeps the rules of a
# quest next to the text of the quest, where they can be read together.

def _bucket(state: dict) -> dict:
    return state.setdefault(STATE_KEY, new_quest_state())


def accept(state: dict, quest_id: str, ctx: dict | None = None) -> dict:
    """Take the quest on. Pass a context and it refuses one the giver would not
    actually offer, so a stale log button cannot start a quest early."""
    quest = QUEST_BY_ID[quest_id]
    raw = _bucket(state)
    if ctx is not None:
        unmet = [g for g in quest.requires if not need_met(g, ctx)]
        if unmet:
            return {"id": quest_id, "refused": True,
                    "blocked_by": describe_need(unmet[0], ctx)}
    if quest_id not in raw["active"] and quest_id not in raw["done"]:
        raw["active"].append(quest_id)
    if quest_id not in raw["seen"]:
        raw["seen"].append(quest_id)
    raw["progress"].setdefault(quest_id, {"count": 0, "failures": 0})
    return {"id": quest_id, "lines": list(quest.setup),
            "objective": quest.objective.get("text", "")}


def abandon(state: dict, quest_id: str) -> None:
    """Putting a quest down costs nothing and loses no progress. There is no
    version of this game where walking away is punished."""
    raw = _bucket(state)
    if quest_id in raw["active"]:
        raw["active"].remove(quest_id)


def target_count(quest: Quest) -> int:
    objective = quest.objective
    if quest.kind == "DELVE":
        return int(objective.get("depth", 1))
    return int(objective.get("count", 1))


def credits(quest: Quest, *, pattern: str = "", family: str = "",
            difficulty: str = "", skill: str = "", unaided: bool = False,
            under_target: bool = False, puzzle_kind: str = "") -> bool:
    """Does the attempt the engine just graded count toward this quest?

    Note what is absent: nothing here reads how long the player has been
    playing, how many days in a row they have shown up, or whether they used a
    hint on some earlier problem. Only the graded attempt itself.
    """
    objective = quest.objective
    if quest.kind == "PUZZLE":
        return puzzle_kind == objective.get("puzzle")
    if quest.kind in ("HUNT", "RELIEF"):
        wanted_family = objective.get("family")
        wanted_pattern = objective.get("pattern")
        matched = ((wanted_family and family == wanted_family)
                   or (wanted_pattern and pattern == wanted_pattern))
        if not matched:
            return False
        return unaided if objective.get("unaided") else True
    if quest.kind == "MASTERY":
        earned = skill or skillmod.PATTERN_TO_SKILL.get(pattern, "")
        if earned != objective.get("skill"):
            return False
        if curriculum.tier_index(difficulty) < \
                curriculum.tier_index(objective.get("difficulty", "EASY")):
            return False
        if objective.get("unaided") and not unaided:
            return False
        if objective.get("under_target") and not under_target:
            return False
        return True
    if quest.kind == "ESCORT":
        return True
    return False


def credit(state: dict, quest_id: str, *, amount: int = 1) -> dict:
    raw = _bucket(state)
    entry = raw["progress"].setdefault(quest_id, {"count": 0, "failures": 0})
    entry["count"] = min(entry["count"] + amount, target_count(QUEST_BY_ID[quest_id]))
    return entry


def note_failure(state: dict, quest_id: str) -> dict:
    """An ESCORT keeps a failure budget. Spending it all restarts the run and
    nothing else — no lost progress elsewhere, no lost items, no cooldown."""
    quest = QUEST_BY_ID[quest_id]
    raw = _bucket(state)
    entry = raw["progress"].setdefault(quest_id, {"count": 0, "failures": 0})
    if quest.kind != "ESCORT":
        return entry
    entry["failures"] += 1
    if entry["failures"] > int(quest.objective.get("failures_allowed", 1)):
        entry["count"] = 0
        entry["failures"] = 0
        entry["restarted"] = int(entry.get("restarted", 0)) + 1
    return entry


def note_clear(state: dict, **attempt) -> list:
    """Fold one graded clear into every active quest it counts for. Returns the
    ids that are now ready to turn in."""
    raw = _bucket(state)
    ready = []
    for quest_id in list(raw["active"]):
        quest = QUEST_BY_ID.get(quest_id)
        if quest is None or not credits(quest, **attempt):
            continue
        credit(state, quest_id)
        if raw["progress"][quest_id]["count"] >= target_count(quest):
            ready.append(quest_id)
    return ready


def note_depth(state: dict, dungeon_id: str, floor: int) -> list:
    """Deepest floor reached, ever. Depth is not lost by leaving a dungeon."""
    raw = _bucket(state)
    depths = raw.setdefault("depths", {})
    depths[dungeon_id] = max(int(depths.get(dungeon_id, 0)), int(floor))
    ready = []
    for quest_id in list(raw["active"]):
        quest = QUEST_BY_ID.get(quest_id)
        if quest is None or quest.kind != "DELVE":
            continue
        if quest.objective.get("dungeon") != dungeon_id:
            continue
        if depths[dungeon_id] >= target_count(quest):
            ready.append(quest_id)
    return ready


def note_puzzle(state: dict, puzzle_kind: str) -> None:
    raw = _bucket(state)
    clears = raw.setdefault("puzzle_clears", {})
    clears[puzzle_kind] = int(clears.get(puzzle_kind, 0)) + 1


def mark_found(state: dict, quest_id: str) -> None:
    """A RECOVERY quest's discovery condition has been satisfied in the world."""
    quest = QUEST_BY_ID[quest_id]
    if quest.kind != "RECOVERY":
        return
    credit(state, quest_id, amount=target_count(quest))


def answer_riddle(state: dict, quest_id: str, said: str) -> dict:
    """Riddles are answered out in the world, in one line, with no editor.

    A wrong answer costs nothing and may be given again immediately. The point
    of a riddle here is to make the player say a thing out loud before they are
    sure of it, which is the specific habit this whole game exists to build.
    """
    quest = QUEST_BY_ID[quest_id]
    accepted = [a.lower().strip() for a in quest.objective.get("answers", [])]
    given = " ".join(said.lower().split()).strip(" .")
    correct = given in accepted or any(
        given == a.strip(" .") for a in accepted)
    if correct:
        credit(state, quest_id, amount=target_count(quest))
    return {"correct": correct,
            "explain": quest.objective.get("explain", "") if correct else "",
            "line": quest.turn_in if correct else "",
            "retry": not correct}


def ready(quest_id: str, ctx: dict, state: dict) -> bool:
    """Is this quest finished, whatever finished means for its kind?"""
    quest = QUEST_BY_ID[quest_id]
    raw = _bucket(state)
    if quest.kind == "DELVE":
        depth = int(raw.get("depths", {}).get(quest.objective["dungeon"], 0))
        return depth >= target_count(quest)
    have = int(raw.get("progress", {}).get(quest_id, {}).get("count", 0))
    return have >= target_count(quest)


def progress_of(quest_id: str, ctx: dict, state: dict) -> dict:
    quest = QUEST_BY_ID[quest_id]
    raw = _bucket(state)
    if quest.kind == "DELVE":
        have = int(raw.get("depths", {}).get(quest.objective["dungeon"], 0))
    else:
        have = int(raw.get("progress", {}).get(quest_id, {}).get("count", 0))
    need = target_count(quest)
    entry = raw.get("progress", {}).get(quest_id, {})
    out = {"id": quest_id, "current": min(have, need), "required": need,
           "percent": round(100 * min(have, need) / max(need, 1)),
           "text": quest.objective.get("text", ""),
           "done": have >= need}
    if quest.kind == "ESCORT":
        out["failures"] = int(entry.get("failures", 0))
        out["failures_allowed"] = int(quest.objective.get("failures_allowed", 1))
        out["recover"] = quest.objective.get("recover", "")
        out["restarts"] = int(entry.get("restarted", 0))
    return out


def complete(state: dict, quest_id: str) -> dict:
    """Turn in. Banks everything this module owns and hands back the rest.

    The split matters: `pay` is what the engine settles (XP, gold, the rarity
    floor for the drop roll, a set piece, a consumable, and the material layer —
    metal into the forge stock, potions into the pouch, gear into the pack,
    credit with a vendor), `story` is what story.apply's buckets already know how
    to hold, and `world` is the part that changes the map. Regalia is banked here
    rather than paid, because it is a thing the player now owns in this module's
    own ledger, exactly like a known pet or an open shortcut.

    The caller never has to learn the reward vocabulary.
    """
    quest = QUEST_BY_ID[quest_id]
    raw = _bucket(state)
    if quest_id in raw["done"]:
        return {}
    raw["done"].append(quest_id)
    if quest_id in raw["active"]:
        raw["active"].remove(quest_id)

    reward = quest.reward
    consequence = quest.consequence
    raw["npc_lines"][quest.giver] = consequence.get("npc_line", "")

    for key, bucket in (("pet", "pets"), ("shortcut", "shortcuts"),
                        ("town_upgrade", "town_upgrades"),
                        ("incantation", "incantations"), ("title", "titles"),
                        ("regalia", "regalia")):
        value = reward.get(key)
        if value and value not in raw[bucket]:
            raw[bucket].append(value)

    chain = CHAIN_BY_ID.get(quest.chain)
    chain_done = bool(chain) and all(s in raw["done"] for s in chain.steps)

    return {
        "id": quest.id, "title": quest.title, "kind": quest.kind,
        "tier": quest.tier, "region": quest.region,
        "giver": quest.giver, "giver_name": speaker_name(quest.giver),
        "lines": [quest.turn_in],
        "consequence": dict(consequence),
        "reward": reward, "reward_lines": reward_summary(reward),
        "pay": {k: reward[k] for k in ("xp", "gold", "rarity_floor",
                                       "set_item", "consumable", "metal",
                                       "potion", "gear", "vendor_credit")
                if k in reward},
        "story": {k: reward[k] for k in ("card", "codex", "title", "favor")
                  if k in reward},
        "world": {k: reward[k] for k in ("shortcut", "town_upgrade", "pet",
                                         "incantation", "regalia")
                  if k in reward},
        "chain": quest.chain,
        "chain_complete": chain_done,
        "epilogue": chain.epilogue if chain_done else "",
    }


# ---------------------------------------------------------------------------
# What the world looks like afterwards
# ---------------------------------------------------------------------------

def npc_line(npc_id: str, state: dict) -> str:
    """What this person says now. Quests overwrite it permanently, which is the
    cheapest possible way to make a world remember you."""
    raw = state.get(STATE_KEY) or {}
    changed = raw.get("npc_lines", {}).get(npc_id)
    if changed:
        return changed
    npc = NPCS.get(npc_id)
    if npc:
        return npc["line"]
    mentor = world.MENTORS.get(npc_id, {})
    return mentor.get("greeting", "")


def world_changes(state: dict, region_id: str = "") -> list:
    """Everything the player has physically changed, for the overworld renderer
    and for the region description text."""
    raw = state.get(STATE_KEY) or {}
    done = set(raw.get("done", []))
    out = []
    for quest_id in raw.get("done", []):
        quest = QUEST_BY_ID.get(quest_id)
        if quest is None or (region_id and quest.region != region_id):
            continue
        change = quest.consequence.get("world")
        if change:
            out.append({"quest": quest.id, "region": quest.region,
                        "text": change})
    for chain in CHAINS:
        if region_id and chain.region != region_id:
            continue
        if chain.epilogue and all(s in done for s in chain.steps):
            out.append({"quest": chain.id, "region": chain.region,
                        "text": chain.epilogue, "chain": True})
    return out


def open_shortcuts(state: dict) -> list:
    raw = state.get(STATE_KEY) or {}
    return [{"id": sid, **SHORTCUTS[sid]} for sid in raw.get("shortcuts", [])
            if sid in SHORTCUTS]


def built_upgrades(state: dict, region_id: str = "") -> list:
    raw = state.get(STATE_KEY) or {}
    out = [{"id": uid, **TOWN_UPGRADES[uid]} for uid in raw.get("town_upgrades", [])
           if uid in TOWN_UPGRADES]
    return [u for u in out if not region_id or u["region"] == region_id]


def upgrade_effects(state: dict) -> dict:
    """The summed, permanent effects of everything that has been rebuilt. Same
    vocabulary as items.EFFECT_LABELS, so the engine folds it in exactly the way
    it folds equipment."""
    totals: dict = {}
    for upgrade in built_upgrades(state):
        for key, value in upgrade.get("effects", {}).items():
            totals[key] = totals.get(key, 0) + value
    return totals


def known_pets(state: dict) -> list:
    """Discovery conditions the player has been told. Knowing is not having —
    the animal still has to be found where the condition says it is."""
    raw = state.get(STATE_KEY) or {}
    return [{"id": pid, **PET_DISCOVERIES[pid]} for pid in raw.get("pets", [])
            if pid in PET_DISCOVERIES]


def granted_incantations(state: dict) -> list:
    raw = state.get(STATE_KEY) or {}
    return [{"id": iid, **INCANTATION_GRANTS[iid]}
            for iid in raw.get("incantations", []) if iid in INCANTATION_GRANTS]


def owned_regalia(state: dict) -> list:
    """Tack the player has earned. Order is turn-in order, which is also the
    order the pet screen should list it in."""
    raw = state.get(STATE_KEY) or {}
    return [{"id": rid, **REGALIA[rid]} for rid in raw.get("regalia", [])
            if rid in REGALIA]


def wear_regalia(state: dict, regalia_id: str) -> dict:
    """Put one piece of tack on the companion. Mirrors pets.ACTIVE_LIMIT: this
    replaces whatever was worn rather than adding to it. Passing "" takes the
    tack off, which is always allowed and never costs anything."""
    raw = _bucket(state)
    if regalia_id and regalia_id not in raw.get("regalia", []):
        return {"ok": False, "reason": "not_owned", "worn": raw.get("regalia_worn", "")}
    raw["regalia_worn"] = regalia_id
    return {"ok": True, "worn": regalia_id,
            "name": REGALIA[regalia_id]["name"] if regalia_id else ""}


def worn_regalia(state: dict) -> dict:
    """The piece currently in use, or {} for none."""
    raw = state.get(STATE_KEY) or {}
    rid = raw.get("regalia_worn", "")
    if rid in REGALIA and rid in raw.get("regalia", []):
        return {"id": rid, **REGALIA[rid]}
    return {}


def regalia_effect(state: dict) -> dict:
    """The one thing the pet screen needs: how much sooner and how much more
    often the companion may speak, from the single worn piece.

    This is the whole of what regalia does, and saying so in one small function
    is deliberate. There is no third key here and there is no room for one: the
    only other lever that exists is pets.Tier, the tier decides DEPTH, and depth
    is not for sale. A caller that wants to know whether a companion can read a
    problem asks pets.covers(), which this function cannot reach.

    `scale` multiplies pets.BondRank.threshold_scale. `interventions` is added to
    pets.BondRank.interventions.
    """
    piece = worn_regalia(state)
    return {"scale": float(piece.get("threshold_scale", 1.0)),
            "interventions": int(piece.get("interventions", 0)),
            "worn": piece.get("id", "")}


def companion_speech(state: dict, bond: int) -> dict:
    """What a companion at this bond, wearing everything the player has earned,
    is allowed to do. Returns exactly pets.py's two non-depth levers, already
    combined, so the engine never has to do this arithmetic and never has to be
    trusted to leave the third lever alone.

    Depth is absent from the return value on purpose. Ask pets.covers().
    """
    rank = petmod.bond_rank(int(bond))
    gear = regalia_effect(state)
    return {
        "rank": rank.key,
        "threshold_scale": max(REGALIA_SCALE_FLOOR,
                               round(rank.threshold_scale * gear["scale"], 4)),
        "interventions": min(rank.interventions + gear["interventions"],
                             REGALIA_INTERVENTION_CAP),
        "regalia": gear["worn"],
    }


# ---------------------------------------------------------------------------
# Counts and self-check
# ---------------------------------------------------------------------------

def counts() -> dict:
    """Content census. Cheap enough to print in a test failure message."""
    by_region = {r["id"]: 0 for r in world.REGIONS}
    by_kind = {k: 0 for k in KINDS}
    by_tier = {t: 0 for t in REWARD_TIERS}
    for quest in QUESTS:
        by_region[quest.region] += 1
        by_kind[quest.kind] += 1
        by_tier[quest.tier] += 1
    return {
        "quests": len(QUESTS),
        "chains": len(CHAINS),
        "chain_steps": sum(len(c.steps) for c in CHAINS),
        "standalone": len(QUESTS) - sum(len(c.steps) for c in CHAINS),
        "regions": len(by_region),
        "by_region": by_region,
        "by_kind": by_kind,
        "by_tier": by_tier,
        "givers": len({q.giver for q in QUESTS}),
        "dungeons": len(DUNGEONS),
        "pets": len(PET_DISCOVERIES),
        "shortcuts": len(SHORTCUTS),
        "town_upgrades": len(TOWN_UPGRADES),
        "incantations": len(INCANTATION_GRANTS),
        "regalia": len(REGALIA),
        "upgrades_stocking": sum(1 for u in TOWN_UPGRADES.values()
                                 if u.get("stocks")),
        "paying_metal": sum(1 for q in QUESTS if "metal" in q.extras),
        "paying_potion": sum(1 for q in QUESTS if "potion" in q.extras),
        "paying_gear": sum(1 for q in QUESTS if "gear" in q.extras),
        "paying_regalia": sum(1 for q in QUESTS if "regalia" in q.extras),
        "paying_credit": sum(1 for q in QUESTS if "vendor_credit" in q.extras),
        "metal_bars": sum(q.extras["metal"]["count"] for q in QUESTS
                          if "metal" in q.extras),
        "metals_reachable": len({q.extras["metal"]["id"] for q in QUESTS
                                 if "metal" in q.extras}),
        "by_band": {band: sum(1 for q in QUESTS
                              if REGION_BAND[q.region] == band)
                    for band in potions.TIER_ORDER},
    }


def report() -> str:
    """The census as text, region by region, for a build log."""
    census = counts()
    lines = [f"{census['quests']} quests, {census['chains']} chains "
             f"({census['chain_steps']} steps), "
             f"{census['standalone']} standalone"]
    for region in world.REGIONS:
        total = census["by_region"][region["id"]]
        kinds = sorted({q.kind for q in BY_REGION[region["id"]]})
        lines.append(f"  {region['name']:<28} {total:>2}  {', '.join(kinds)}")
    lines.append("  by kind:  " + ", ".join(
        f"{k} {v}" for k, v in census["by_kind"].items()))
    lines.append("  by tier:  " + ", ".join(
        f"{REWARD_TIERS[t]['name']} {v}" for t, v in census["by_tier"].items()))
    lines.append(f"  in kind:  {census['paying_potion']} pay potions, "
                 f"{census['paying_metal']} pay metal "
                 f"({census['metal_bars']} bars across "
                 f"{census['metals_reachable']} of {len(forge.METALS)} metals), "
                 f"{census['paying_gear']} pay gear, "
                 f"{census['paying_credit']} pay vendor credit, "
                 f"{census['paying_regalia']} pay regalia "
                 f"(of {census['regalia']})")
    return "\n".join(lines)


_KNOWN_STATS = ("encounters", "armor_repairs", "shrines", "hints_total",
                "sessions", "probes", "probes_correct", "crits", "items_found",
                "secrets")

_OBJECTIVE_REQUIRED = {
    "HUNT": ("count",), "ESCORT": ("count", "failures_allowed", "recover"),
    "PUZZLE": ("puzzle", "count"), "DELVE": ("dungeon", "depth"),
    "RECOVERY": ("lost", "condition"),
    "MASTERY": ("skill", "difficulty", "count"),
    "RIDDLE": ("question", "answers", "skill", "explain"),
    "RELIEF": ("task", "count"),
}


def _regalia_grants_no_depth() -> list:
    """The one rule in this file worth proving rather than asserting.

    pets.py is explicit: a companion's TIER decides how deep the help goes, bond
    buys only EARLIER and MORE OFTEN, and every effect that reads the encounter
    is enumerated in pets.DEPTH_GATED_EFFECTS. The brief asked quests to reward
    "upgraded hints"; this is the check that the upgrade is quantity and never
    depth, so no second hint economy can grow here and quietly outrank the tiers
    the player chose a companion for.

    Three things are checked, and the third is the one that matters:

      1. regalia carries only the two legal levers and its own prose. A piece
         that grew a new key would be a piece that does something unreviewed.
      2. neither lever can be pushed past its clamp, even stacked with the top
         bond rank — and the clamps are enforced in regalia_effect(), not here.
      3. NO regalia key, at any depth, is an items.EFFECT_LABELS key. That is
         stronger than "not in DEPTH_GATED_EFFECTS": regalia may not carry an
         effect AT ALL, which is the cheapest way to be sure it never carries a
         gated one, today or after somebody edits this table in a hurry.
    """
    problems = []
    legal = {"name", "region", "blurb", "tell", "threshold_scale",
             "interventions"}
    for rid, piece in REGALIA.items():
        extra = set(piece) - legal
        if extra:
            problems.append(f"regalia {rid}: unexpected key(s) "
                            f"{sorted(extra)} — regalia moves two numbers and "
                            f"says two sentences, and that is all it may do")
        for key in piece:
            if key in items.EFFECT_LABELS:
                problems.append(f"regalia {rid}: {key!r} is an equipment effect; "
                                f"regalia may not carry effects at all")
            if key in petmod.DEPTH_GATED_EFFECTS:
                problems.append(f"regalia {rid}: {key!r} is depth-gated and "
                                f"belongs to the companion tier ladder")
        if piece["region"] not in world.REGION_BY_ID:
            problems.append(f"regalia {rid}: unknown region {piece['region']!r}")
        scale = float(piece.get("threshold_scale", 1.0))
        if not 0.0 < scale <= 1.0:
            problems.append(f"regalia {rid}: threshold_scale {scale} must be a "
                            f"fraction that makes the animal speak sooner")
        if scale < REGALIA_SCALE_FLOOR:
            problems.append(f"regalia {rid}: a single piece may not undercut the "
                            f"floor of {REGALIA_SCALE_FLOOR}")
        if not 0 <= int(piece.get("interventions", 0)) <= 1:
            problems.append(f"regalia {rid}: one piece may add at most one "
                            f"intervention")

    # Every piece checked against the budget on its own, worn by the best bond
    # rank pets.py has. This is the check that BITES: because only one piece is
    # ever worn, a piece that cannot be afforded is a piece that was authored
    # wrong, and there is no clamp standing behind it to hide that. A reward the
    # turn-in panel describes and the fight does not deliver is a lie, and it is
    # the specific lie this function exists to prevent.
    best = petmod.BOND_RANKS[-1]
    for rid, piece in REGALIA.items():
        scale = round(best.threshold_scale * float(piece["threshold_scale"]), 4)
        if scale < REGALIA_SCALE_FLOOR:
            problems.append(
                f"regalia {rid}: worn at {best.key} bond it reaches {scale}, "
                f"under the floor of {REGALIA_SCALE_FLOOR} — the clamp would "
                f"quietly eat part of this reward")
        total = best.interventions + int(piece.get("interventions", 0))
        if total > REGALIA_INTERVENTION_CAP:
            problems.append(
                f"regalia {rid}: worn at {best.key} bond it reaches {total} "
                f"interventions, over the cap of {REGALIA_INTERVENTION_CAP}")

    # And the shape of what the engine is handed. Depth is not one of the things
    # this module is allowed to return, so its absence is asserted rather than
    # assumed.
    sample = {STATE_KEY: {**new_quest_state(), "regalia": list(REGALIA),
                          "regalia_worn": next(iter(REGALIA), "")}}
    shape = set(companion_speech(sample, best.at))
    if shape - {"rank", "threshold_scale", "interventions", "regalia"}:
        problems.append(f"companion_speech leaked {sorted(shape)}; depth is not "
                        f"one of the things this module may return")
    if REGALIA_ACTIVE_LIMIT != petmod.ACTIVE_LIMIT:
        problems.append("regalia active limit has drifted from pets.ACTIVE_LIMIT")
    return problems


def validate(corpus: list | None = None) -> list:
    """Every id resolves, every reward is payable, every quest is reachable.

    Pass a corpus to also check that the pattern families quests point at are
    families the corpus actually contains — the one class of typo that would
    otherwise present as a quest that can never be completed.
    """
    problems = []
    tiers = sorted(REWARD_TIERS)

    # -- the reward table itself
    for lower, higher in zip(tiers, tiers[1:]):
        low, high = REWARD_TIERS[lower], REWARD_TIERS[higher]
        if high["xp"] <= low["xp"] or high["gold"] <= low["gold"]:
            problems.append(f"reward tier {higher}: pay must exceed tier {lower}")
        if items.RARITY_ORDER.index(high["rarity_floor"]) < \
                items.RARITY_ORDER.index(low["rarity_floor"]):
            problems.append(f"reward tier {higher}: rarity floor went backwards")
        if not set(low["grants"]).issubset(set(high["grants"])):
            problems.append(f"reward tier {higher}: grants must contain tier "
                            f"{lower}'s grants")
    for tier, row in REWARD_TIERS.items():
        if row["rarity_floor"] not in items.RARITIES:
            problems.append(f"reward tier {tier}: unknown rarity floor")
        for key in row["grants"]:
            if key not in REWARD_KEYS:
                problems.append(f"reward tier {tier}: unknown grant {key!r}")

    # -- the registries
    for pid, pet in PET_DISCOVERIES.items():
        if pet["region"] not in world.REGION_BY_ID:
            problems.append(f"{pid}: unknown region {pet['region']!r}")
    for sid, shortcut in SHORTCUTS.items():
        for end in ("from", "to"):
            if shortcut[end] not in world.REGION_BY_ID:
                problems.append(f"{sid}: unknown region {shortcut[end]!r}")
    for uid, upgrade in TOWN_UPGRADES.items():
        if upgrade["region"] not in world.REGION_BY_ID:
            problems.append(f"{uid}: unknown region {upgrade['region']!r}")
        for key in upgrade.get("effects", {}):
            if key not in items.EFFECT_LABELS:
                problems.append(f"{uid}: unknown effect {key!r}")
        stocks = upgrade.get("stocks") or {}
        for key in stocks:
            if key not in ("potions", "metal"):
                problems.append(f"{uid}: may stock potions and metal, not {key!r}")
        region = upgrade["region"]
        for pid in stocks.get("potions", ()):
            if pid not in potions.BY_ID:
                problems.append(f"{uid}: unknown potion {pid!r}")
                continue
            if potions.found_at(pid, REGION_BAND.get(region, "GUIDED")):
                # Already on the shelf, so rebuilding the place changed nothing.
                problems.append(f"{uid}: {pid!r} is already available at "
                                f"{region!r}'s own band — stocking it is not an "
                                f"upgrade, it is a restatement")
            elif not potions.found_at(pid, next_band(region)):
                problems.append(f"{uid}: {pid!r} is more than one band deeper "
                                f"than {region!r}; a rebuilt shop carries the "
                                f"next shelf up, not the last one")
        if stocks.get("metal") and stocks["metal"] != metal_for(region):
            problems.append(f"{uid}: stocks {stocks['metal']!r}, which does not "
                            f"come out of {region!r}")
    for did, dungeon in DUNGEONS.items():
        if dungeon["region"] not in world.REGION_BY_ID:
            problems.append(f"{did}: unknown region {dungeon['region']!r}")
    for nid, npc in NPCS.items():
        if npc["region"] not in world.REGION_BY_ID:
            problems.append(f"{nid}: unknown region {npc['region']!r}")
    problems.extend(_regalia_grants_no_depth())

    # -- the material layer agrees with the modules that own it
    for tier in VENDOR_CREDIT:
        if "vendor_credit" not in REWARD_TIERS[tier]["grants"]:
            problems.append(f"reward tier {tier}: priced for vendor credit but "
                            f"not permitted to grant it")
    for tier, row in REWARD_TIERS.items():
        if "vendor_credit" in row["grants"] and tier not in VENDOR_CREDIT:
            problems.append(f"reward tier {tier}: may grant vendor credit and "
                            f"VENDOR_CREDIT does not price it")
    for region_id, band in REGION_BAND.items():
        if band not in potions.TIER_ORDER:
            problems.append(f"{region_id}: band {band!r} is not a potion tier")
    for region_id in world.REGION_BY_ID:
        mid = metal_for(region_id)
        if mid and mid not in forge.METAL_BY_ID:
            problems.append(f"{region_id}: unknown metal {mid!r}")
        if not mid and region_id not in forge.NO_METAL_REGIONS:
            problems.append(f"{region_id}: no metal, and forge.py does not say "
                            f"it is one of the regions that has none")
        for item_id in gear_for(region_id):
            if item_id not in items.BY_ID:
                problems.append(f"{region_id}: unknown gear {item_id!r}")

    # -- gates
    def check_gate(where: str, gate: story.Trigger):
        if gate.kind in ("all", "any"):
            for part in gate.parts:
                check_gate(where, part)
            return
        if gate.kind == "quest_done" and gate.key not in QUEST_BY_ID:
            problems.append(f"{where}: unknown quest {gate.key!r}")
        if gate.kind == "region_open" and gate.key not in world.REGION_BY_ID:
            problems.append(f"{where}: unknown region {gate.key!r}")
        if gate.kind == "region_entered" and gate.key not in world.REGION_BY_ID:
            problems.append(f"{where}: unknown region {gate.key!r}")
        if gate.kind == "boss_cleared" and gate.key not in world.BOSS_BY_ID:
            problems.append(f"{where}: unknown boss {gate.key!r}")
        if gate.kind == "bosses_cleared" and gate.value > len(world.BOSSES):
            problems.append(f"{where}: asks for more bosses than exist")
        if gate.kind == "dungeon_depth":
            dungeon = DUNGEONS.get(gate.key)
            if dungeon is None:
                problems.append(f"{where}: unknown dungeon {gate.key!r}")
            elif gate.value > dungeon["floors"]:
                problems.append(f"{where}: {gate.key} has no floor {gate.value}")
        if gate.kind == "pet_found" and gate.key not in PET_DISCOVERIES:
            problems.append(f"{where}: unknown pet {gate.key!r}")
        if gate.kind == "shortcut_open" and gate.key not in SHORTCUTS:
            problems.append(f"{where}: unknown shortcut {gate.key!r}")
        if gate.kind == "secret_found" and gate.key not in items.SECRET_BY_ID:
            problems.append(f"{where}: unknown secret {gate.key!r}")
        if gate.kind == "puzzle_clears" and gate.key not in puzzles.PUZZLE_KINDS:
            problems.append(f"{where}: unknown puzzle kind {gate.key!r}")
        if gate.kind == "mentor_favor" and gate.key not in world.MENTORS:
            problems.append(f"{where}: unknown mentor {gate.key!r}")
        if gate.kind == "chapter" and gate.key not in curriculum.CHAPTER_BY_ID:
            problems.append(f"{where}: unknown chapter {gate.key!r}")
        if gate.kind == "stat" and gate.key not in _KNOWN_STATS:
            problems.append(f"{where}: unknown stat {gate.key!r}")
        if gate.kind.startswith("skill_"):
            if gate.key not in skillmod.SKILLS:
                problems.append(f"{where}: unknown skill {gate.key!r}")
            if gate.kind in ("skill_mastery", "skill_retention", "skill_speed") \
                    and gate.value > 100:
                problems.append(f"{where}: {gate.key} can never reach "
                                f"{gate.value}")
        if gate.kind == "quests_done" and gate.value > len(QUESTS):
            problems.append(f"{where}: asks for more quests than exist")

    # -- rewards
    def check_reward(where: str, quest: Quest):
        allowed = set(REWARD_TIERS[quest.tier]["grants"])
        for key, value in quest.extras.items():
            if key not in REWARD_KEYS:
                problems.append(f"{where}: unknown reward key {key!r}")
                continue
            if key not in allowed:
                problems.append(f"{where}: tier {quest.tier} may not grant "
                                f"{key!r}")
            if key == "card" and value not in story.GRIMOIRE_CARDS:
                problems.append(f"{where}: unknown card {value!r}")
            if key == "codex" and value not in story.CODEX:
                problems.append(f"{where}: unknown codex entry {value!r}")
            if key == "shortcut" and value not in SHORTCUTS:
                problems.append(f"{where}: unknown shortcut {value!r}")
            if key == "town_upgrade" and value not in TOWN_UPGRADES:
                problems.append(f"{where}: unknown town upgrade {value!r}")
            if key == "pet" and value not in PET_DISCOVERIES:
                problems.append(f"{where}: unknown pet discovery {value!r}")
            if key == "incantation" and value not in INCANTATION_GRANTS:
                problems.append(f"{where}: unknown incantation {value!r}")
            if key == "favor" and value["mentor"] not in world.MENTORS:
                problems.append(f"{where}: unknown mentor in favour grant")
            if key == "consumable" and value["id"] not in items.CONSUMABLES:
                problems.append(f"{where}: unknown consumable {value['id']!r}")
            if key == "metal":
                metal = forge.METAL_BY_ID.get(value.get("id", ""))
                if metal is None:
                    problems.append(f"{where}: unknown metal {value.get('id')!r}")
                elif quest.region not in metal.regions:
                    # The whole of requirement B for this reward kind. A quest
                    # pays the ground it stands on or it pays no ore at all.
                    problems.append(
                        f"{where}: pays {value['id']!r}, which does not come out "
                        f"of {quest.region!r} (that ground gives "
                        f"{metal_for(quest.region) or 'no metal'})")
                if int(value.get("count", 0)) < 1:
                    problems.append(f"{where}: metal count must be at least 1")
                if int(value.get("count", 0)) > METAL_COUNT[max(METAL_COUNT)]:
                    problems.append(f"{where}: metal count above the tier-5 bundle")
            if key == "potion":
                potion = potions.BY_ID.get(value.get("id", ""))
                band = REGION_BAND[quest.region]
                if potion is None:
                    problems.append(f"{where}: unknown potion {value.get('id')!r}")
                elif not potions.found_at(potion.id, band):
                    # potions.py decides what a band may brew, not this file.
                    problems.append(
                        f"{where}: {potion.id!r} needs a {potion.min_tier} area "
                        f"and {quest.region!r} bands at {band}")
                elif int(value.get("count", 0)) > potions.CARRY_CAP[potion.strength]:
                    # Paying more than the pouch holds is paying nothing.
                    problems.append(
                        f"{where}: {value['count']} x {potion.id!r} exceeds the "
                        f"pouch cap of {potions.CARRY_CAP[potion.strength]}")
                elif int(value.get("count", 0)) < 1:
                    problems.append(f"{where}: potion count must be at least 1")
            if key == "gear":
                item = items.BY_ID.get(value)
                affinity = elements.affinity_for(quest.region)
                if item is None:
                    problems.append(f"{where}: unknown item {value!r}")
                elif item.source == "upgrade":
                    # An upgrade is something the player builds at the forge.
                    # Handing one over as a quest prize would step on forge.py's
                    # ladder, which is somebody else's system and a better one.
                    problems.append(f"{where}: {value!r} is an upgrade-path item "
                                    f"and may not be given away")
                elif value not in gear_for(quest.region):
                    problems.append(
                        f"{where}: {value!r} is {item.element or 'un'}-elemental "
                        f"and {quest.region!r} is {affinity}")
            if key == "regalia" and value not in REGALIA:
                problems.append(f"{where}: unknown regalia {value!r}")
            if key == "vendor_credit":
                if value.get("region") not in world.REGION_BY_ID:
                    problems.append(f"{where}: unknown region in vendor credit")
                elif value["region"] != quest.region:
                    problems.append(f"{where}: credit is for {value['region']!r}, "
                                    f"quest is in {quest.region!r}")
                if int(value.get("amount", 0)) < 1:
                    problems.append(f"{where}: vendor credit must be positive")
            if key == "set_item":
                item = items.BY_ID.get(value)
                if item is None:
                    problems.append(f"{where}: unknown item {value!r}")
                elif not item.set_id:
                    problems.append(f"{where}: {value!r} is not a set piece")
                elif items.RARITY_ORDER.index(item.rarity) < \
                        items.RARITY_ORDER.index(
                            REWARD_TIERS[quest.tier]["rarity_floor"]):
                    problems.append(f"{where}: set piece {value!r} is below the "
                                    f"tier {quest.tier} rarity floor")

    # -- objectives
    def check_objective(where: str, quest: Quest):
        objective = quest.objective
        if not objective.get("text"):
            problems.append(f"{where}: objective needs a text the log can print")
        for key in _OBJECTIVE_REQUIRED[quest.kind]:
            if key not in objective:
                problems.append(f"{where}: {quest.kind} objective needs {key!r}")
        if quest.kind == "DELVE":
            dungeon = DUNGEONS.get(objective.get("dungeon", ""))
            if dungeon is None:
                problems.append(f"{where}: unknown dungeon "
                                f"{objective.get('dungeon')!r}")
            else:
                if dungeon["region"] != quest.region:
                    problems.append(f"{where}: dungeon is in "
                                    f"{dungeon['region']!r}, quest is not")
                if int(objective.get("depth", 0)) > dungeon["floors"]:
                    problems.append(f"{where}: dungeon has no floor "
                                    f"{objective.get('depth')}")
        if objective.get("family") and corpus:
            # An objective that asks for more clears than the family has
            # problems is not impossible — a repeat counts — but it is a quest
            # that can only be finished by meeting the same problem twice, and
            # that teaches nothing the first clear did not.
            stock = sum(1 for p in corpus
                        if p.spaced_repetition_family == objective["family"])
            if stock < int(objective.get("count", 1)):
                problems.append(f"{where}: family {objective['family']!r} holds "
                                f"{stock} problems, objective wants "
                                f"{objective.get('count')}")
        if quest.kind == "PUZZLE" and \
                objective.get("puzzle") not in puzzles.PUZZLE_KINDS:
            problems.append(f"{where}: unknown puzzle kind "
                            f"{objective.get('puzzle')!r}")
        if quest.kind in ("MASTERY", "RIDDLE") and \
                objective.get("skill") not in skillmod.SKILLS:
            problems.append(f"{where}: unknown skill {objective.get('skill')!r}")
        if quest.kind == "MASTERY":
            if objective.get("difficulty") not in curriculum.TIERS:
                problems.append(f"{where}: unknown difficulty "
                                f"{objective.get('difficulty')!r}")
            skill = objective.get("skill")
            mentions = any(g.key == skill for g in _flatten(quest.requires))
            if not mentions:
                problems.append(f"{where}: a named standard in {skill} must be "
                                f"gated on evidence in {skill}, or it can be "
                                f"demanded before the tier is even unlocked")
        if quest.kind in ("HUNT", "RELIEF") and not (objective.get("family")
                                                     or objective.get("pattern")):
            problems.append(f"{where}: nothing would ever credit toward this — "
                            f"a hunt needs a family or a pattern")
        if quest.kind == "RIDDLE" and not objective.get("answers"):
            problems.append(f"{where}: a riddle with no accepted answers")
        if quest.kind == "ESCORT" and not objective.get("recover"):
            problems.append(f"{where}: an escort must say how failure recovers")
        if corpus is not None:
            families = {p.spaced_repetition_family for p in corpus}
            patterns = {p.pattern for p in corpus}
            family = objective.get("family")
            pattern = objective.get("pattern")
            if family and family not in families:
                problems.append(f"{where}: no corpus family {family!r}")
            if pattern and pattern not in patterns:
                problems.append(f"{where}: no corpus pattern {pattern!r}")

    seen_ids = set()
    for quest in QUESTS:
        where = quest.id
        if quest.id in seen_ids:
            problems.append(f"duplicate quest id {quest.id!r}")
        seen_ids.add(quest.id)
        if quest.kind not in KINDS:
            problems.append(f"{where}: unknown kind {quest.kind!r}")
        if quest.region not in world.REGION_BY_ID:
            problems.append(f"{where}: unknown region {quest.region!r}")
        if quest.giver not in NPCS and quest.giver not in world.MENTORS:
            problems.append(f"{where}: unknown giver {quest.giver!r}")
        elif quest.giver in NPCS and NPCS[quest.giver]["region"] != quest.region:
            problems.append(f"{where}: {quest.giver!r} does not live here")
        if quest.tier not in REWARD_TIERS:
            problems.append(f"{where}: tier {quest.tier} is not in the table")
        if not 2 <= len(quest.setup) <= 5:
            problems.append(f"{where}: setup should be two to five lines")
        if not quest.turn_in:
            problems.append(f"{where}: nothing is said on turn-in")
        if not quest.consequence.get("npc_line"):
            problems.append(f"{where}: the giver must say something different "
                            f"forever after")
        if not quest.consequence.get("world"):
            problems.append(f"{where}: a quest that changes nothing is a chore")
        if quest.tier >= 4 and len(quest.requires) < 2:
            problems.append(f"{where}: tier {quest.tier} pay with no gate "
                            f"beyond the region")
        for gate in quest.requires:
            check_gate(where, gate)
        check_reward(where, quest)
        check_objective(where, quest)

    # -- chains
    step_owner: dict = {}
    for chain in CHAINS:
        if len(chain.steps) < 2:
            problems.append(f"{chain.id}: a chain needs at least two steps")
        if chain.region not in world.REGION_BY_ID:
            problems.append(f"{chain.id}: unknown region {chain.region!r}")
        if chain.giver not in NPCS and chain.giver not in world.MENTORS:
            problems.append(f"{chain.id}: unknown giver {chain.giver!r}")
        if not chain.epilogue:
            problems.append(f"{chain.id}: a chain must end with something "
                            f"visible")
        for step_id in chain.steps:
            if step_id not in QUEST_BY_ID:
                problems.append(f"{chain.id}: unknown step {step_id!r}")
                continue
            if step_id in step_owner:
                problems.append(f"{step_id}: claimed by {step_owner[step_id]!r} "
                                f"and {chain.id!r}")
            step_owner[step_id] = chain.id
        tiers_in_chain = [QUEST_BY_ID[s].tier for s in chain.steps
                          if s in QUEST_BY_ID]
        if tiers_in_chain and tiers_in_chain[-1] != max(tiers_in_chain):
            problems.append(f"{chain.id}: the last step must be the best one")
    for quest in QUESTS:
        if quest.chain and step_owner.get(quest.id) != quest.chain:
            problems.append(f"{quest.id}: orphan chain step")

    # -- reachability: no quest may wait on something that can never happen
    for quest in QUESTS:
        for gate in _flatten(quest.requires):
            if gate.kind == "quest_done":
                if gate.key == quest.id:
                    problems.append(f"{quest.id}: waits on itself")
    for quest in QUESTS:
        if _cycles(quest.id, set()):
            problems.append(f"{quest.id}: prerequisite cycle")

    # -- coverage, so the world does not quietly develop bald patches
    census = counts()
    for region_id, total in census["by_region"].items():
        if total == 0:
            problems.append(f"{region_id}: no quests at all")
    for kind, total in census["by_kind"].items():
        if total == 0:
            problems.append(f"{kind}: authored nowhere")
    for pid in PET_DISCOVERIES:
        granting = [q.id for q in QUESTS if q.extras.get("pet") == pid]
        if len(granting) > 1:
            problems.append(f"{pid}: rumoured by {len(granting)} quests, want one")
    rumoured = {q.extras["pet"] for q in QUESTS if q.extras.get("pet")}
    if len(rumoured) < 5:
        problems.append(f"only {len(rumoured)} pets have a quest rumour, want 5")
    for sid in SHORTCUTS:
        granting = [q.id for q in QUESTS if q.extras.get("shortcut") == sid]
        if len(granting) > 1:
            problems.append(f"{sid}: opened by more than one quest")
    for uid in TOWN_UPGRADES:
        granting = [q.id for q in QUESTS if q.extras.get("town_upgrade") == uid]
        if len(granting) > 1:
            problems.append(f"{uid}: built by more than one quest")

    # -- every quest must be reachable in principle
    # A quest gated on something that can never become true is invisible content
    # and the player has no way to find out it exists. Saturate a context — every
    # skill mastered, every boss down, every region open, every other quest done
    # — and check that each quest's gates can actually all be satisfied at once.
    saturated = _saturated_context()
    for quest in QUESTS:
        saturated["quests_done"] = {q.id for q in QUESTS} - {quest.id}
        unmet = [describe_need(g, saturated) for g in quest.requires
                 if not need_met(g, saturated)]
        if unmet:
            problems.append(f"{quest.id}: unreachable even at full strength "
                            f"({unmet[0]})")

    # -- a cold start must have something in it
    cold = {"skills": {}, "cleared_bosses": set(), "quests_done": set(),
            "quests_active": set(), "level": 1, "stats": {},
            "regions_open": set(world.unlocked_regions({}, set()))}
    if len(available(cold)) < 3:
        problems.append("a new game offers fewer than three quests")

    # -- the voice
    for text in _all_prose():
        if "!" in text:
            problems.append(f"exclamation mark in prose: {text[:60]!r}")

    # -- the other team's file, if it has landed yet
    try:
        from . import incantation            # noqa: F401  (optional dependency)
    except Exception:
        pass
    else:
        known = getattr(incantation, "BY_ID", None)
        if isinstance(known, dict):
            for iid in INCANTATION_GRANTS:
                if iid not in known:
                    problems.append(f"{iid}: no such incantation")

    return problems


def _saturated_context() -> dict:
    """A player who has done everything. Used only to prove that the gates in
    this file describe a world that can actually be finished."""
    maxed = {name: {"mastery": 100.0, "clears": 999, "unaided_clears": 999,
                    "attempts": 999, "retention": 100.0, "speed": 100.0,
                    "stage": "MASTERED"} for name in skillmod.SKILLS}
    return {
        "skills": maxed,
        "regions_open": {r["id"] for r in world.REGIONS},
        "regions_entered": {r["id"] for r in world.REGIONS},
        "cleared_bosses": {b["id"] for b in world.BOSSES},
        "solved_count": 9999, "level": 99,
        "stats": {key: 999 for key in _KNOWN_STATS},
        "gates_passed": 13, "gates_total": 13,
        "chapter_index": len(curriculum.CHAPTERS) - 1,
        "flags": set(), "events": set(),
        "favor": {mentor: 999 for mentor in world.MENTORS},
        "quests_done": set(), "quests_active": set(),
        "dungeon_depth": {d: row["floors"] for d, row in DUNGEONS.items()},
        "puzzle_clears": {kind: 999 for kind in puzzles.PUZZLE_KINDS},
        "pets_found": set(PET_DISCOVERIES), "shortcuts": set(SHORTCUTS),
        "town_upgrades": set(TOWN_UPGRADES),
        "secrets_found": {s["id"] for s in items.SECRETS},
    }


def _flatten(gates) -> list:
    out = []
    for gate in gates:
        if gate.kind in ("all", "any"):
            out.extend(_flatten(gate.parts))
        else:
            out.append(gate)
    return out


def _cycles(quest_id: str, seen: set) -> bool:
    if quest_id in seen:
        return True
    quest = QUEST_BY_ID.get(quest_id)
    if quest is None:
        return False
    seen = seen | {quest_id}
    return any(_cycles(gate.key, seen) for gate in _flatten(quest.requires)
               if gate.kind == "quest_done")


def _all_prose():
    for quest in QUESTS:
        yield quest.premise
        yield from quest.setup
        yield quest.turn_in
        yield quest.objective.get("text", "")
        yield quest.consequence.get("npc_line", "")
        yield quest.consequence.get("world", "")
    for chain in CHAINS:
        yield chain.premise
        yield chain.epilogue
    for npc in NPCS.values():
        yield npc["line"]
    for pet in PET_DISCOVERIES.values():
        yield pet["hint"]
        yield pet["condition"]
    for shortcut in SHORTCUTS.values():
        yield shortcut["line"]
    for upgrade in TOWN_UPGRADES.values():
        yield upgrade["line"]
        yield upgrade["effect"]


WIRING = """
How the engine picks this up. Nine touch points, none of them invasive.

1. STATE
   engine.DEFAULT_STATE["quests"] = quests.new_quest_state()
   _merge already forward-fills, so an existing save gains the key on load.

2. CONTEXT
   Wherever the engine already builds a story context:
       ctx = quests.context(self.story_context(...), self.state)
   That adds quests_done, regions_open, dungeon depths, pets and shortcuts to
   the same flat dict the story triggers read.

3. THE LOG
   quests.board(ctx, self.state) returns available / active / done / locked,
   each row carrying its own progress numbers and, when locked, the single
   nearest missing requirement. quests.region_board(region_id, ...) narrows it
   to a signpost. quests.next_steps(ctx) is never empty.

4. ACCEPTING AND TURNING IN
   quests.accept(state, quest_id) -> the giver's setup lines.
   quests.ready(quest_id, ctx, state) -> is it finished.
   quests.complete(state, quest_id) -> {"pay", "story", "world", ...}.
       pay    XP, gold, rarity_floor for the drop roll, set_item, consumable,
              and the material layer: metal / potion / gear / vendor_credit
       story  card / codex / title / favor — the buckets story.apply owns
       world  shortcut / town_upgrade / pet / incantation / regalia — all of
              which are already banked in this module's own state
   Pay `pay`, hand `story` to the story bookkeeping, and re-render the map.
   The four material keys and exactly what each one asks of the engine are
   spelled out in CONTRACT below, because another pass owns engine.py.

5. CREDITING WORK
   After grading an attempt, once:
       ready = quests.note_clear(state, pattern=p.pattern,
                                 family=p.spaced_repetition_family,
                                 difficulty=p.difficulty, unaided=hints == 0,
                                 under_target=seconds <= p.target_seconds,
                                 puzzle_kind=kind_or_empty)
   For dungeons: quests.note_depth(state, dungeon_id, floor) on every descent.
   For puzzles: quests.note_puzzle(state, kind) on every puzzle cleared.
   For a failed encounter inside an ESCORT: quests.note_failure(state, id).

6. RECOVERY AND RIDDLES
   The overworld fires quests.mark_found(state, quest_id) when the player
   reaches the place the condition names. A riddle is answered with
   quests.answer_riddle(state, quest_id, typed) — wrong answers are free and
   immediately retryable, by design.

7. THE WORLD AFTERWARDS
   quests.npc_line(npc_id, state)        what this person says now
   quests.world_changes(state, region)   what is physically different
   quests.open_shortcuts(state)          routes the overworld should draw
   quests.built_upgrades(state, region)  buildings the renderer should raise
   quests.upgrade_effects(state)         folded in like equipment effects
   quests.upgrade_stock(state, region)   what rebuilding put on local shelves
   quests.owned_regalia(state)           tack the player has earned
   quests.worn_regalia(state)            the one piece in use
   quests.wear_regalia(state, id)        choose it; "" takes it off

8. THE COMPANION, AND THE ONE LINE THAT MATTERS
   quests.companion_speech(state, bond) -> {"rank", "threshold_scale",
                                            "interventions", "regalia"}
   Fold that into the pets.py intervention call in place of reading
   pets.bond_rank(bond).threshold_scale and .interventions directly. It is the
   same two numbers with the worn regalia applied, already clamped.

   DEPTH IS NOT IN THAT RETURN VALUE AND MUST NOT BE ADDED TO IT. Whether a
   companion may read a problem at all is still, only, pets.covers(pet_id,
   difficulty). Regalia buys sooner and more often; the tier buys deeper and
   nothing in this file can move it. quests._regalia_grants_no_depth() proves
   that and validate() runs it.

9. INTERVIEW MODE
   None of this exists there. Interview Mode measures; quests teach, pay and
   change the map. The gate is the same one that seals mentors and spells.

10. TESTS
   assert quests.validate(corpus) == []
   The corpus argument is optional and checks the pattern families quests point
   at against the corpus actually shipped.
"""


CONTRACT = """
What quests.py and story.py now need from engine.py, which another pass owns.

Five new reward keys arrive in the `pay` and `world` buckets of complete(), plus
one accessor that is a consequence rather than a reward. None of them needs a new
system; each is a line against a system that already exists. Nothing below
changes what a problem says, what a test asserts or what a hint reveals, and all
of it is Adventure Mode only, behind the same finalexam.sealed() gate that
already seals the rest of this module.

story.py pays the same way. story.apply() now returns "metal", "potion" and
"gear" in the dict it already hands back for xp/gold/companion/consumable, with
identical shapes, so whatever settles those settles these and there is one
handler rather than two. story.py grants no regalia and no vendor credit, and
the reason is written at its REWARD_KEYS.

  pay["metal"]          {"id": forge.METAL_BY_ID key, "count": int}
        Add `count` of that metal to whatever stock forge.py reads when it
        prices a rung. This is the same currency forge.roll_metal already
        produces from encounters, so it goes into the same place; no new
        inventory. 47 of the 74 quests pay it, 107 bars in total, and all 11
        metals in forge.METALS are reachable from quests alone.

  pay["potion"]         {"id": potions.BY_ID key, "count": int}
        potions.grant(state, potions.BY_ID[id], count). The count is already
        checked against potions.CARRY_CAP by validate(), so an overflow here is
        a bug in this file, not a case to handle. All 74 quests pay potions.

  pay["gear"]           items.BY_ID key
        Put the item in the pack exactly as a drop would. It is always a real
        catalogue entry whose element is the region's affinity, it is never an
        `upgrade`-source item, and it is not rolled — it is the named object the
        giver hands over. 20 quests pay it.

  pay["vendor_credit"]  {"region": world.REGION_BY_ID key, "amount": int}
        economy.grant_credit(state, region, amount). It banks against that
        region's shop and is spendable there and nowhere else; economy.py wrote
        that function against this exact shape.

        This key names a region and an amount and deliberately names no vendor,
        stock list or price, and it has to stay that way: economy.py imports
        quests.py, so this module can never import it back without a cycle. The
        region is the join. 19 quests pay it, 1,610 credit in total.

  quests.upgrade_stock(state)   {region: {"potions": [ids], "metal": id}}
        Not a reward key — a consequence, read whenever a vendor's shelf is
        drawn. A region the player has rebuilt sells one band deeper than it
        otherwise could, and a rebuilt works also sells that region's metal.
        economy.py owns price, count and restock; this only says what is now on
        the shelf at all. 7 of the 9 town upgrades stock something.

  world["regalia"]      REGALIA key
        Already banked in this module's state by complete(). The engine only
        has to offer quests.wear_regalia(state, id) on the companion screen.
        economy.buy_regalia() returns the same {"regalia": id} shape, so a piece
        bought from a vendor and a piece earned from a quest settle through one
        code path and there is exactly one regalia ledger.

And one change to an existing call, which is the whole of the brief's
"upgraded hints":

  WHEREVER the pet intervention is built from pets.bond_rank(bond), read
  threshold_scale and interventions from quests.companion_speech(state, bond)
  instead. Same two numbers, worn regalia folded in, already clamped.

  Do NOT let anything in this file reach pets.covers() or pets.Tier. Depth of
  help is the companion's tier, is paid for in rank, and is refused in a
  measured run. Regalia buys EARLIER and MORE OFTEN and may never buy DEEPER.
  quests._regalia_grants_no_depth() is the proof, validate() runs it, and it is
  written to fail loudly if a future piece of regalia grows a third lever.

WHAT COULD NOT BE RESOLVED, stated plainly rather than guessed at:

  economy.py  absent when this pass began and landed while it was running. The
              shape above is unchanged and now resolves: economy.grant_credit,
              economy.VENDOR_BY_REGION and economy.regalia_price all read this
              module rather than the other way round, and economy.area_band is a
              pass-through to story.band_for. Nothing here had to be rewritten,
              which is the argument for having kept the key this thin.
  regalia.py  never appeared. REGALIA therefore lives here, in the same idiom as
              SHORTCUTS, TOWN_UPGRADES and PET_DISCOVERIES,
              which are also registries this module owns. If regalia.py lands,
              move the table and keep _regalia_grants_no_depth() pointed at it —
              the invariant is the valuable part, not the dict. economy.py has
              since built its regalia counter directly on quests.REGALIA, so
              there is one roster, one price list derived from it, and one proof
              that a piece cannot buy depth. Do not add a second.
  region band no module said how hard a region is. It is derived from the rung
              of the region's metal in forge.py rather than authored here, so
              potions.found_at() stays the only authority on what a band brews.
              See RUNG_BAND and band_for().
"""
