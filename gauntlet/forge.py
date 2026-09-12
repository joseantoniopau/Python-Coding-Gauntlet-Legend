"""The metals, the blades and the smith.

The map already had seventeen regions and no reason to prefer any of them. You
fought where the quest pointed, and a region was a backdrop. This module makes a
region a SOURCE: each one drops a metal that drops nowhere else, and the only
person who can work it stands in Python Village. That is the whole loop — walk
further to get better material, carry it back to somebody who knows what to do
with it, and watch one object you have owned since Chapter I become something a
player recognises across a room.

Six blades, one per class in `classes.py`. Eleven metals across sixteen fighting
regions. Nine rungs per blade, each costing metals and each changing three things
at once: what the weapon DOES, what it LOOKS like, and what its technique is.

THE ANSWER RULE, WHICH THIS FILE IS THE MOST TEMPTING PLACE TO BREAK
-------------------------------------------------------------------
`items.py` states it and `classes.py` states it harder, and a legendary weapon
with a signature technique is exactly where somebody eventually writes "reveals
the optimal approach" and tells themselves it is fine because it took four
hundred fights to earn.

    No rung, no technique and no rank of a technique may supply an answer, name
    the pattern of the problem in front of you, reveal any part of a solution,
    or let you past an encounter without solving it.

What a technique is permitted to buy is INFORMATION ABOUT THE ENCOUNTER and
ECONOMICS: another probe, a longer clock for rank, a ward that absorbs a failed
submission you already paid for by naming the edge case, a trace of YOUR OWN
submitted code, a named failure CATEGORY, a second attempt at a rank cost. Every
one of those makes you engage more, not less. `validate()` proves it two ways:
every effect key resolves inside `items.EFFECT_LABELS`, and no technique text
contains the vocabulary of giving something away.

The strongest technique in the file is PERIMETER STRIKE at rank nine, which
makes probes on the first and last element of any input free and unlimited. A
player who plans a run around it still has to know that the first and last
element are where it breaks, still has to choose the input, and still has to
write the function. That is the line, and it is a long way from the other side
of it.

WHAT THIS MODULE BUILDS ON, AND DOES NOT DUPLICATE
--------------------------------------------------
    items.EFFECT_LABELS      the effect vocabulary. Not one new key is added
                             here, which is the headline claim of the file.
    items.ARMOR_TIERS        the six-step weapon metal ramp the hero already
                             uses; every rung's colour is derived from it
    items.RARITIES           the rarity ladder a rung climbs
    classes.CLASSES          the six classes, their signature_weapon ids, and
                             classes.CAPS, which every rung stays well under
    classes.GEAR_REQUESTS    the six EPIC weapons class design already asked
                             for. They are rung SIX here, unchanged in id, name
                             and effect, because a weapon that upgrades cannot
                             sensibly be born EPIC.
    world.REGIONS            the metal ladder is this list, in order
    dungeons.DUNGEONS        the typical difficulty of a region is READ off the
                             real dungeon plan, so grind estimates are measured
                             rather than asserted
    legendaries.LOOTART_*    the art vocabulary. The motifs and auras below
                             extend that request; they do not fork it.
    finalexam.sealed         the one isolation path. See `active()`.

MASTERY IS NOT FOR SALE HERE
----------------------------
A metal is loot. Nothing in this module reads or writes `skills.py` state, and
`validate()` proves it by inspecting this module's own namespace for a skills
import. The blade changes the economics of a fight. It never moves a number that
says you learned something.

INTEGRATION CONTRACT
--------------------
    forge.METALS / forge.metal_for_region(region_id)
    forge.BLADES / forge.blade_for_class(class_id) / forge.BLADE_BY_ID
    forge.rung(blade_id, tier)            one rung, as data
    forge.item_kwargs(blade_id, tier)     exactly what items._i() wants
    forge.new_state()                     the flat dict a save persists
    forge.active(encounter)               the only isolation question
    forge.roll_metal(...)                 the drop
    forge.quote(state, blade_id)          what the next rung costs and lacks
    forge.upgrade(state, blade_id, ...)   the only mutator of a tier
    forge.smith_view(...)                 everything the smith screen draws
    forge.swap_view(blade_id, tier)       the found-weapon comparison
    forge.grind_estimate()                encounters per rung, measured
    forge.validate()                      the proofs this file must pass

`ART_BRIEF` at the bottom is the contract for whoever is drawing this, and
`WIRING` is the contract for whoever is wiring it. Both are written to be read
by somebody who has not read the rest of the file.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, asdict

from . import classes, dungeons, elements, finalexam, items, legendaries, world

# ==========================================================================
# SECTION 1 — THE EFFECT VOCABULARY
# ==========================================================================
#
# There is nothing to declare. Every effect any rung of any blade grants is
# already a key in `items.EFFECT_LABELS`, introduced there by items.py, by
# classes.py or by legendaries.py, and rendered by the same tooltip path the
# rest of the game uses.
#
# That was a design constraint rather than a happy accident. A weapon line that
# needs a private verb is a weapon line whose designer wanted to do something
# the existing verbs would not let them do, and in this file the thing the
# existing verbs will not let you do is give the player an answer.
#
# FORGE_EFFECT_KEYS is the surface this module actually touches. Deleting one
# from items.py is now an ImportError here rather than a rung that quietly stops
# describing itself.

FORGE_EFFECT_KEYS = (
    # measurement and declaration — the Analyst's argument
    "declare_slots", "declare_bonus", "probe_charges", "probe_refund",
    "perf_insight", "first_try_bonus", "probe_first_free",
    # speed and iteration — the Berserker's
    "rank_grace", "iteration_bonus", "retry_grace", "stamina_max",
    "recovery_grace", "focus_from_failure",
    # retrieval — the Archivist's
    "retest_bonus", "retest_charges", "srs_preview", "interval_stretch",
    "mana_max", "spell_refund", "retest_storm",
    # edges — the Warden's
    "edge_ward", "crit_bonus", "reveal_category", "weakness_scan",
    "boundary_sense",
    # tools — the Artificer's
    "bench_slots", "refactor_bonus", "design_rubric", "mana_regen",
    "second_wind",
    # reading — the Seer's
    "trace_frames", "root_cause_bonus", "probe_reveal_value", "prereq_sight",
)

EFFECT_LABELS = {key: items.EFFECT_LABELS[key] for key in FORGE_EFFECT_KEYS}


def describe(effects: dict) -> list:
    """Effect text, in the shared vocabulary. `items.describe` is the renderer
    on purpose: a rung that reads differently on the smith's counter than it
    reads in the equipment screen is a bug the player finds before we do."""
    return items.describe(effects or {})


# Keys whose value is a capability rather than an amount. Mirrors
# `items.SWITCH_KEYS` and `classes.MAXED_KEYS` for the keys this file uses, and
# `validate()` checks it against both rather than trusting the copy.
SWITCH_KEYS = frozenset({
    "perf_insight", "reveal_category", "srs_preview", "second_wind",
    "probe_reveal_value", "boundary_sense", "prereq_sight", "spell_refund",
})

# Of those, the ones items.SWITCH_KEYS does not yet contain. Two sources of
# "a learning spell's focus is refunded in full" do not refund it twice, so a
# key like this must take max() rather than sum(). `legendaries.WIRING` §1 made
# the same request for four of its own keys and it is made the same way here:
# as a named, checkable list rather than as a comment somebody deletes.
#
# Written out rather than computed from items.SWITCH_KEYS, which is the whole
# point: a derived list would agree with reality by construction and the check
# below would prove nothing. As a literal it fails in BOTH directions — if
# items.py grants the request and nobody deletes the line, and if forge starts
# using a switch key that items.py sums and nobody notices.
# GRANTED. items.py took "spell_refund" into items.SWITCH_KEYS, so the list
# is empty — which is the only state validate() accepts once it is there.
SWITCH_REQUESTS: tuple = ()

# Ceiling discipline. `classes.CAPS` is the ceiling on the WHOLE build — tree
# plus gear plus attributes plus set bonuses. A single weapon that reaches the
# cap on its own makes every skill node above it worthless, so no rung is
# allowed past this fraction of a cap. Sixty per cent leaves the tree the
# majority stake in its own numbers, which is the correct ordering: the tree is
# what you chose, the blade is what you carried.
CAP_SHARE = 0.6

# Integer capabilities need the rule stated differently, because 60% of a cap of
# three is 1.8 and rounding that down would mean a MYTHIC rung may never grant a
# second free retry — which is not "leave the tree the majority stake", it is
# "delete the capability". So for whole-number capabilities the rule is the one
# that was actually intended: a blade may never reach the ceiling on its own.
# There is always at least one point of it left for the tree to give.
CAP_HEADROOM = 1


# ==========================================================================
# SECTION 2 — THE METALS
# ==========================================================================
#
# Eleven metals over sixteen fighting regions. Python Village has no metal
# because Python Village has no monsters; the smith lives there, and a town that
# drops its own ore would let a player finish the whole ladder without leaving
# the tutorial.
#
# Regions share metals deliberately. Seventeen metals would be seventeen things
# to forget; eleven means every one of them is a place you can picture. Where
# two regions share a metal they share a REASON — the Highlands and the Caverns
# both keep things by position, so both give up Keybrass; the Mines and the
# Debugging Dungeon are both places where you find out what the last shift did
# wrong, so both give up Faultsteel.
#
# `rung` is the ladder. It runs 1..6 and it tracks region tier: walking further
# is the only thing that gets you better material.

@dataclass(frozen=True)
class Metal:
    id: str
    name: str
    rung: int
    regions: tuple
    blurb: str          # what it is, said the way a smith would say it
    tell: str           # how you know you are carrying it
    colour: str         # for the inventory chip, and for the smith's counter

    def to_dict(self) -> dict:
        d = asdict(self)
        d["regions"] = list(self.regions)
        d["region_names"] = [world.REGION_BY_ID[r]["name"] for r in self.regions]
        # Derived, never stored on the dataclass: see SECTION 2b. A metal that
        # carried a hand-typed element could disagree with the ground it came
        # out of, and then the map would stop meaning anything.
        d["affinity"] = list(METAL_AFFINITY.get(self.id, ()))
        return d


METALS: tuple = (
    Metal("fieldiron", "Fieldiron", 1, ("fields_of_syntax",),
          "Bog iron out of the field margins, where the half-formed statements "
          "rot down. Soft, plentiful, and honest about being soft.",
          "It leaves orange on your palms and it will not stop doing that.",
          "#8a7f6a"),
    Metal("keybrass", "Keybrass", 2, ("hashmap_highlands", "array_caverns"),
          "Brass from spent vault keys and from the numbered plates over the "
          "alcoves. Two places, one idea: metal that remembers a position.",
          "Warm on one side only, and always the side facing its own vault.",
          "#c9a05a"),
    Metal("loomsteel", "Loomsteel", 2, ("stringwood_labyrinth",),
          "Steel drawn on the letter-looms, one wire per character. Take a "
          "bar apart and you get the same letters in a different order.",
          "Rearranges its grain overnight. The weight never changes.",
          "#9aa4b8"),
    Metal("marshsilver", "Marshsilver", 3, ("sliding_window_marsh",
                                            "twin_pointer_pass"),
          "Silver that only forms at a moving edge — under the frame out in the "
          "reeds, and under the two lanterns on the Pass. Both are the same "
          "trick done at a different speed.",
          "Bright at both ends of the bar and dull through the middle.",
          "#b9c8c0"),
    Metal("faultsteel", "Faultsteel", 3, ("stack_queue_mines",
                                          "debugging_dungeon"),
          "Ore cut out of a failure. The Mines give it up where a seam gave way "
          "in the wrong order; the Armorer's cells give it up out of plate that "
          "was sound the day before.",
          "Every bar has one hairline in it and the hairline is the useful part.",
          "#7e6f66"),
    Metal("quarterturn", "Quarterturn Bronze", 4, ("matrix_citadel",),
          "Bronze off the Citadel's floor plates. Cast in place, so every ingot "
          "has been through four orientations and holds none of them.",
          "Set it down square and come back to find it square the other way.",
          "#b07a45"),
    Metal("heartwood_iron", "Heartwood Iron", 4, ("recursive_forest",
                                                  "binary_tree_canopy"),
          "Iron that is grown rather than mined. Split a bar and there is a "
          "smaller bar inside it, correct in every particular, down as far as "
          "anyone has had the patience to go.",
          "Lighter than it has any right to be, and it rings twice.",
          "#6f7a55"),
    Metal("wastes_iron", "Wastes-iron", 4, ("graph_wastes",),
          "Iron out of the Wastes, pulled from the lattice roads between the "
          "ruins. Every piece was connected to several other pieces and the "
          "breaks tell you which.",
          "Two bars set near each other lean together. Three lean into a road.",
          "#6a6470"),
    Metal("tilegold", "Tilegold", 5, ("dp_ruins",),
          "Gold prised out of the Ruin floor. A tile you have already solved "
          "stays lit, and a lit tile is worth prising up — which is either the "
          "lesson of that place or a very expensive misreading of it.",
          "Cold in the dark. Warm on ground you have walked before.",
          "#e0b44a"),
    Metal("doubling_steel", "Doubling Steel", 5, ("complexity_tower",
                                                  "coding_coliseum"),
          "Tower steel, and the same alloy the Coliseum quenches in its sand. "
          "Each bar weighs twice the bar below it, which is a joke the Tower "
          "makes once and then keeps making.",
          "The eighth bar is a problem. The ninth is somebody else's problem.",
          "#8fa8c8"),
    Metal("nullsteel", "Nullsteel", 6, ("null_kings_castle",),
          "Steel with the label struck off. It is not that nobody knows what it "
          "is; it is that the Castle removed the part of it that said.",
          "Nothing. That is the tell. It does not do anything at all.",
          "#4a4458"),
)

METAL_BY_ID = {m.id: m for m in METALS}
METAL_RUNGS = (1, 2, 3, 4, 5, 6)

# region -> metal. Built rather than written twice, so a region cannot silently
# acquire two metals or lose the one it had.
REGION_METAL = {r: m.id for m in METALS for r in m.regions}

# The one region with no metal, named rather than implied.
NO_METAL_REGIONS = ("python_village",)


def metal_for_region(region_id: str) -> Metal | None:
    """The metal a region gives up, or None for the town."""
    mid = REGION_METAL.get(region_id, "")
    return METAL_BY_ID.get(mid)


def metals_at_rung(rung: int) -> list:
    return [m for m in METALS if m.rung == rung]


# --------------------------------------------------------------------------
# The drop
# --------------------------------------------------------------------------
# Shaped like `items.DIFFICULTY_DROP_CHANCE` because a second, differently-
# shaped drop model is a second thing to tune and a second thing to get wrong.
# Rank feeds in through `items.RANK_BONUS`, unchanged, for the same reason:
# fighting well should pay in metal exactly as much as it pays in loot.
#
# Bundles stay at one unit until ELITE on purpose. A metal that arrives in
# threes at MEDIUM collapses the whole ladder into an afternoon, and "slowly"
# was the word the design started from.

METAL_DROP_CHANCE = {
    "GUIDED": 0.20, "TUTORIAL": 0.30, "EASY": 0.42, "MEDIUM": 0.58,
    "HARD": 0.72, "ELITE": 0.85, "BOSS": 1.0,
}

METAL_BUNDLE = {
    "GUIDED": 1, "TUTORIAL": 1, "EASY": 1, "MEDIUM": 1,
    "HARD": 1, "ELITE": 2, "BOSS": 3,
}

MAX_METAL_CHANCE = 0.95         # mirrors items.roll_drop; a boss ignores it


def metal_chance(difficulty: str, *, rank: str = "B", luck: float = 0.0,
                 is_boss: bool = False) -> float:
    """The probability this encounter yields its region's metal."""
    if is_boss:
        return 1.0
    chance = METAL_DROP_CHANCE.get(difficulty, 0.3)
    chance += items.RANK_BONUS.get(rank, 0.0) + luck * 0.5
    return max(0.0, min(MAX_METAL_CHANCE, chance))


def expected_metal(difficulty: str, *, rank: str = "B", luck: float = 0.0,
                   is_boss: bool = False) -> float:
    """Units per encounter, on average. This is the number every grind estimate
    in this file is built out of, so it is one function rather than a constant
    somebody updated in three places."""
    bundle = METAL_BUNDLE.get("BOSS" if is_boss else difficulty, 1)
    return metal_chance(difficulty, rank=rank, luck=luck,
                        is_boss=is_boss) * bundle


def roll_metal(*, region_id: str, difficulty: str, rank: str = "B",
               luck: float = 0.0, is_boss: bool = False,
               encounter=None, rng: random.Random | None = None) -> dict | None:
    """One encounter's metal, or None.

    `encounter` goes through `active()` and nowhere else. A metal is gear
    progress, and gear does not accrue in a measured run.
    """
    if encounter is not None and not active(encounter):
        return None
    metal = metal_for_region(region_id)
    if metal is None:
        return None
    rng = rng or random.Random()
    if not is_boss and rng.random() > metal_chance(difficulty, rank=rank,
                                                   luck=luck):
        return None
    units = METAL_BUNDLE.get("BOSS" if is_boss else difficulty, 1)
    return {"metal": metal.id, "name": metal.name, "units": units,
            "colour": metal.colour, "region": region_id}


# --------------------------------------------------------------------------
# Substitution — the reason no upgrade path can dead-end
# --------------------------------------------------------------------------
# A player who took the Tree route and skipped the Mines can still be short of
# Faultsteel at rung five with a bag full of Heartwood Iron. Vess will beat the
# better metal down into the worse one and she will lose some of it doing that,
# which is both physically sensible and the correct incentive: substitution is
# always available and always a bad deal.
#
# Downward only. There is no alchemy in this game and a player who has not
# walked far enough does not get to skip the walk.

SUBSTITUTION_COVER = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}


def substitution_cover(higher_rung: int, lower_rung: int) -> int:
    """How many units of the lower metal one unit of the higher one covers.
    Zero when the trade is upward, which Vess does not do."""
    delta = higher_rung - lower_rung
    if delta <= 0:
        return 0
    return SUBSTITUTION_COVER.get(delta, 6)


def substitutes_for(metal_id: str, held: dict) -> list:
    """Everything in the bag that could stand in for `metal_id`, best first."""
    want = METAL_BY_ID.get(metal_id)
    if want is None:
        return []
    out = []
    for other_id, units in (held or {}).items():
        other = METAL_BY_ID.get(other_id)
        if other is None or units <= 0:
            continue
        cover = substitution_cover(other.rung, want.rung)
        if cover:
            out.append({"metal": other.id, "name": other.name,
                        "held": int(units), "covers_each": cover,
                        "covers_total": int(units) * cover})
    out.sort(key=lambda row: (-row["covers_each"], row["metal"]))
    return out


# ==========================================================================
# SECTION 2b — AFFINITY: WHAT A METAL IS MADE OF
# ==========================================================================
#
# A metal already belongs to a region. `elements.AFFINITY` already gives every
# region an element. Joining the two is the whole of this section, and the join
# is DERIVED rather than authored, for the same reason `elements.AFFINITY` is
# derived from biome: a metal that carried a hand-typed element could disagree
# with the ground it comes out of, and then "go and fight in the mine to make a
# fire blade" would be a sentence that was true in one file and false in
# another.
#
# THE THREE CASES, AND WHY THE THIRD ONE IS THE GOOD ONE
#
#   ONE ELEMENTAL REGION      the metal carries that element. Faultsteel is
#                             fire, because the Mines and the Armorer's cells
#                             are both fire.
#   NO ELEMENTAL REGION       the metal is INERT. Fieldiron out of the fields
#                             and Tilegold out of the Ruins temper nothing,
#                             because neutral regions are the control group and
#                             a metal that could impart "no element" would be a
#                             metal that could strip one for free.
#   TWO DIFFERENT ELEMENTS    the metal is DUAL and tempers toward either one,
#                             chosen at the bench, one at a time. Keybrass is
#                             lightning out of the Highlands and brute out of
#                             the Caverns; it is the same brass and it remembers
#                             both places.
#
# The dual metals are not a special case bolted on to cover an inconvenience in
# the table. They are the cheapest way the map has of saying that a player who
# walked two regions has more options than a player who walked one, and they are
# the reason `elements.MAX_AFFINITIES` monsters are answerable at all: two of
# the six elements are reachable from a single bar in your bag.
#
# A NEUTRAL REGION NEVER CONTRIBUTES. Heartwood Iron comes out of the Recursive
# Forest and the Binary Tree Canopy; the Forest is void and the Canopy is
# weatherless, so the iron is void and the Canopy abstains. Abstention rather
# than dilution, because "half a void" is not a thing the wheel can express.

METAL_AFFINITY: dict = {}
for _metal in METALS:
    _seen = []
    for _region in _metal.regions:
        _element = elements.affinity_for(_region)
        if _element != elements.NEUTRAL and _element not in _seen:
            _seen.append(_element)
    METAL_AFFINITY[_metal.id] = tuple(_seen)
del _metal, _seen, _region, _element

# element -> the metals that can temper toward it, cheapest rung first. Built
# rather than written, so an element cannot silently lose its only source.
METALS_BY_ELEMENT: dict = {}
for _mid, _chain in METAL_AFFINITY.items():
    for _e in _chain:
        METALS_BY_ELEMENT.setdefault(_e, []).append(_mid)
for _e in METALS_BY_ELEMENT:
    METALS_BY_ELEMENT[_e].sort(key=lambda m: (METAL_BY_ID[m].rung, m))
del _mid, _chain, _e

INERT_METALS: tuple = tuple(m.id for m in METALS if not METAL_AFFINITY[m.id])


def metal_affinities(metal_id: str) -> tuple:
    """Every element this metal can temper toward. Empty for an inert metal."""
    return METAL_AFFINITY.get(metal_id, ())


def metals_for_element(element: str) -> list:
    """Where an element comes from, cheapest first. This is the function that
    answers "where do I get a fire blade", and `counsel()` answers the rest."""
    return list(METALS_BY_ELEMENT.get(element, ()))


def temper_counsel(element: str) -> dict:
    """Which metals carry this element, where they drop, and how many fights a
    temper is. Same job `counsel()` does for a rung: a player who cannot see the
    route treats the feature as a wall."""
    rows = []
    for mid in metals_for_element(element):
        row = counsel(mid)
        row["affinities"] = list(METAL_AFFINITY[mid])
        rows.append(row)
    art = elements.element_view(element)
    if not rows:
        return {"element": element, "art": art, "metals": [],
                "line": f"Nothing in the ground carries {art['name'].lower()}."}
    first = rows[0]
    return {"element": element, "art": art, "metals": rows,
            "line": (f"{art['name']} is in {first['name']}. {first['line']}")}


# ==========================================================================
# SECTION 2c — THE TEMPER
# ==========================================================================
#
# A rung is what a blade IS. A temper is what it is AGAINST, and they are two
# ladders on purpose: the rung ladder sends you across the whole map for one
# object, and the temper sends you to ONE region for one element. A player who
# needs fire knows exactly where fire is and roughly how long it takes, and
# that is the sentence this whole request was written to make possible.
#
# WHAT A TEMPER DOES, IN THE VOCABULARY THAT ALREADY EXISTS
#
#   a WEAPON      takes the metal's element. That is `items.Item.element`,
#                 which items.py already declares and describes as "what a
#                 weapon STRIKES with", and it is what `elements.matchup` reads.
#                 One element at a time: a blade is one thing.
#   ARMOUR        takes `resist_<element>`, which items.EFFECT_LABELS already
#                 carries and `elements.armour_from_effects` already reads. One
#                 element per PIECE, in three steps of 0.10 up to
#                 `elements.PIECE_RESIST_CAP`.
#
# NOT ONE NEW EFFECT KEY, which is the same claim this file made about rungs and
# is load-bearing for the same reason: a private verb here would be a verb
# nobody's tooltip renders and nobody's test checks.
#
# ONE ELEMENT PER PIECE IS THE ENTIRE STRATEGIC POINT. A chest plate that could
# hold three resistances would answer a three-affinity boss on its own, and then
# `elements.EXTRA_AFFINITY` would be a tax rather than a puzzle. Six armour
# slots, one element each, is what makes "a weapon of one element and armour of
# another" a build you assemble rather than a sentence you read.
#
# SUBSTITUTION DOES NOT APPLY HERE, AND THAT IS DELIBERATE
# Vess will beat a higher metal down into a lower one for a RUNG, because there
# the metal is raw weight and the ladder must not dead-end. Here the metal is
# not weight, it is the element — beating Nullsteel down into a fire temper
# would mean the Mines had nothing the Castle did not, and the map would stop
# meaning anything. Nobody is stranded by that: `elements.WORST_CASE_MULTIPLIER`
# guarantees the worst possible reading of an area is four times the typing and
# never a wall, so a temper is always an economy and never a gate.
#
# THE NUMBERS, AND WHY THEY ARE THESE NUMBERS
# Measured with `forge.best_yield`, at B rank with no luck, in the best region
# that gives the metal up:
#
#   a weapon temper          7 units    ~11 fights   (Faultsteel, the Mines)
#   armour step 1  (0.10)    5 units    ~ 8 fights
#   armour step 2  (0.20)    9 units    ~14 fights
#   armour step 3  (0.30)   15 units    ~23 fights
#   one piece to the cap    29 units    ~46 fights
#
# Against ~460 fights for a blade to rung nine, an eleven-fight fire blade is
# cheap on purpose: the temper is the thing a player does IN an area they are
# already fighting in, and if it cost a chapter nobody would ever hold two.
# The step curve is steep so that the first 0.10 is nearly free and the last is
# a decision — the same shape as the rung ladder, for the same reason.
#
# GOLD IS ON TOP OF METAL AND IS NEVER THE BINDING CONSTRAINT, exactly as it is
# for a rung. An encounter pays roughly xp//3 gold, so a player who farmed the
# metal has already earned the fee several times over. The fee exists so that
# Vess is a business, and so that gold earned from graded Python has somewhere
# to go that is not help.

TEMPER_ELEMENTS: tuple = tuple(elements.ELEMENT_IDS)

# Steps of elemental resistance, and what each one costs. The cap is
# elements.PIECE_RESIST_CAP and it is READ rather than restated, so a change
# there cannot leave a fourth step here that the damage function ignores.
TEMPER_STEP_RESIST = (0.10, 0.20, 0.30)
TEMPER_MAX_STEP = len(TEMPER_STEP_RESIST)
TEMPER_UNITS = {1: 5, 2: 9, 3: 15}
TEMPER_GOLD = {1: 60, 2: 120, 3: 240}

WEAPON_TEMPER_UNITS = 7
WEAPON_TEMPER_GOLD = 90

# The save key. Flat, JSON-shaped, keyed by item id, and small: one row per
# object a player has ever had tempered.
TEMPER_KEY = "temper"

# Which slot counts as a weapon. Everything else in items.SLOTS wears armour's
# side of the deal, including rings and trinkets — `elements.ARMOUR_KINDS`
# already lists ring1, ring2 and trinket under WARDED, so a warding ring is a
# thing the armour model already believed in.
WEAPON_SLOT = "weapon"


def _temper_kind(slot: str) -> str:
    return "weapon" if slot == WEAPON_SLOT else "armour"


def temper_of(state: dict, item_id: str) -> dict:
    """What has been done to this object, or an empty row. Never None, because
    every caller of this wants to render something."""
    row = ((state or {}).get(TEMPER_KEY) or {}).get(item_id) or {}
    return {"item": item_id,
            "element": str(row.get("element", "") or ""),
            "step": int(row.get("step", 0) or 0),
            "kind": str(row.get("kind", "") or "")}


def tempered_element(state: dict, item_id: str) -> str:
    """The element this object now belongs to, or "" for untouched."""
    return temper_of(state, item_id)["element"]


def temper_effects(state: dict, item_id: str) -> dict:
    """The effect bag one tempered object contributes.

    Weapons contribute NOTHING here — a weapon's element is not an effect, it is
    an argument to `elements.resolve_damage`, and putting it in the effect bag
    would be two owners of one number. Use `tempered_element` for a weapon.
    """
    row = temper_of(state, item_id)
    if row["kind"] != "armour" or not row["element"] or row["step"] <= 0:
        return {}
    resist = TEMPER_STEP_RESIST[min(row["step"], TEMPER_MAX_STEP) - 1]
    return {f"resist_{row['element'].lower()}":
            min(elements.PIECE_RESIST_CAP, resist)}


def loadout_temper_effects(state: dict, equipped: dict | None) -> dict:
    """Every tempered piece a player is wearing, summed into one effect bag.

    SUMMED, not maxed, and then clamped by `elements.armour_from_effects` at
    RESIST_CAP — which is elements.py's own rule, stated there as "two
    half-measures should beat one, but six should not beat three". This function
    deliberately does not clamp, so there is exactly one place that does.
    """
    out: dict = {}
    for slot, item_id in (equipped or {}).items():
        if not item_id or slot == WEAPON_SLOT:
            continue
        for key, value in temper_effects(state, item_id).items():
            out[key] = round(out.get(key, 0.0) + value, 3)
    return out


def temper_quote(state: dict, item_id: str, *, slot: str, metal_id: str,
                 element: str = "", gold: int = 0) -> dict:
    """What the next temper of this object costs, and what it would change.

    Every refusal in here names the thing that is missing and where it drops,
    because `counsel()` exists and a refusal without a route is a wall.
    """
    metal = METAL_BY_ID.get(metal_id)
    if metal is None:
        return {"error": "no such metal", "item": item_id}
    if slot not in items.SLOTS:
        return {"error": "no such slot", "item": item_id, "slot": slot}
    chain = metal_affinities(metal_id)
    if not chain:
        return {"error": "inert", "item": item_id, "metal": metal_id,
                "text": (f"{metal.name} came out of ground with no weather in "
                         f"it. There is nothing in it to put into anything.")}
    want = element or chain[0]
    if want not in chain:
        return {"error": "wrong element", "item": item_id, "metal": metal_id,
                "element": want, "offers": list(chain),
                "text": (f"{metal.name} carries "
                         f"{' and '.join(elements.ALL_AFFINITIES[e].name for e in chain)}"
                         f". It does not carry "
                         f"{elements.ALL_AFFINITIES.get(want, elements.ALL_AFFINITIES[elements.NEUTRAL]).name}.")}

    kind = _temper_kind(slot)
    current = temper_of(state, item_id)
    art = elements.element_view(want)

    if kind == "weapon":
        same = current["element"] == want
        need_units = WEAPON_TEMPER_UNITS
        need_gold = WEAPON_TEMPER_GOLD
        step = 1
        note = ("It already strikes with this." if same else
                (f"It strikes with "
                 f"{elements.ALL_AFFINITIES[current['element']].name.lower()} "
                 f"now. That goes." if current["element"] else
                 "It strikes with nothing in particular now."))
    else:
        # A piece that is already warded against something else starts again at
        # step one. Not a punishment: the first step is the cheap one, and a
        # piece that could accumulate two elements would answer a dual monster
        # on its own. The refusal to stack is the mechanic.
        restart = bool(current["element"]) and current["element"] != want
        step = 1 if restart or not current["element"] else current["step"] + 1
        if step > TEMPER_MAX_STEP:
            return {"item": item_id, "slot": slot, "kind": kind,
                    "metal": metal_id, "metal_name": metal.name,
                    "element": want, "art": art, "kind": kind,
                    "at_cap": True, "step": current["step"],
                    "resist": TEMPER_STEP_RESIST[-1],
                    "text": (f"That is as much {art['name'].lower()} as one "
                             f"piece will hold. Ward something else with the "
                             f"next bar.")}
        need_units = TEMPER_UNITS[step]
        need_gold = TEMPER_GOLD[step]
        note = (f"It is warded against "
                f"{elements.ALL_AFFINITIES[current['element']].name.lower()} "
                f"now, and that comes out." if restart else "")

    have = held(state, metal_id)
    short = max(0, need_units - have)
    gold_short = max(0, need_gold - int(gold))
    out = {
        "item": item_id, "slot": slot, "kind": kind,
        "metal": metal_id, "metal_name": metal.name, "colour": metal.colour,
        "element": want, "art": art,
        "offers": list(chain),
        "step": step, "at_cap": False,
        "from": dict(current),
        "units": need_units, "have": have, "short": short,
        "gold": need_gold, "gold_short": gold_short,
        "ready": not short and not gold_short,
        "note": note,
        # No substitution row, and its absence is the feature. See the comment
        # at the top of this section.
        "substitution": {},
        "where": counsel(metal_id)["line"],
        "encounters": int(math.ceil(need_units / best_yield(metal_id)))
        if best_yield(metal_id) else None,
    }
    if kind == "armour":
        out["resist"] = TEMPER_STEP_RESIST[step - 1]
        out["resist_key"] = f"resist_{want.lower()}"
        out["from_resist"] = (TEMPER_STEP_RESIST[current["step"] - 1]
                              if current["element"] == want
                              and current["step"] else 0.0)
    return out


def temper(state: dict, item_id: str, *, slot: str, metal_id: str,
           element: str = "", gold: int = 0) -> dict:
    """The only mutator of a temper. All or nothing, like `upgrade`.

    Gold is reported, never deducted: the purse lives in
    `engine.state["player"]` and two owners of one number is how a purse goes
    negative. The metal IS taken here, and it is taken only after the quote says
    the whole bill is payable.
    """
    q = temper_quote(state, item_id, slot=slot, metal_id=metal_id,
                     element=element, gold=gold)
    if q.get("error"):
        return q
    if q.get("at_cap"):
        return {"error": "at_cap", **q}
    if q["gold_short"]:
        return {"error": "gold", "needs_gold": q["gold_short"], **q}
    if q["short"]:
        return {"error": "metal", "short": q["short"], **q}

    bag = state.setdefault("metals", {})
    bag[metal_id] = int(bag.get(metal_id, 0)) - q["units"]
    rows = state.setdefault(TEMPER_KEY, {})
    rows[item_id] = {"element": q["element"], "step": q["step"],
                     "kind": q["kind"], "metal": metal_id}
    state["tempered"] = int(state.get("tempered", 0)) + 1

    result = {
        "item": item_id, "slot": slot, "kind": q["kind"],
        "metal": metal_id, "element": q["element"], "art": q["art"],
        "step": q["step"], "spent": {metal_id: q["units"]},
        "gold_spent": q["gold"],
        "effects": temper_effects(state, item_id),
        "strikes_with": q["element"] if q["kind"] == "weapon" else "",
        "lines": SMITH_TEMPERED(q),
    }
    return result


def SMITH_TEMPERED(q: dict) -> list:
    """What Vess says over a finished temper. She names the element, the number
    and the consequence, because those are the three things the player is about
    to need and she has never said anything else."""
    art = q["art"]
    if q["kind"] == "weapon":
        return [
            f"{q['metal_name']} into the edge. It strikes "
            f"{art['name'].lower()} now.",
            "One element. It was never going to hold two and neither will you.",
            f"{art['blurb']}",
        ]
    pct = int(round(q["resist"] * 100))
    return [
        f"{q['metal_name']} through the plate. {pct} percent off anything "
        f"{art['name'].lower()} throws at you.",
        ("That is the last step. A second element goes on a second piece."
         if q["step"] >= TEMPER_MAX_STEP else
         f"Step {q['step']} of {TEMPER_MAX_STEP}. Bring more of the same bar."),
        "What it does against the other five is what it did before. Nothing.",
    ]


def temper_view(state: dict, *, equipped: dict | None = None,
                gold: int = 0) -> dict:
    """Vess's second counter: every element, where its metal is, what you are
    already wearing against it, and what your blade currently strikes with.

    This is the player-facing answer to "how am I supposed to SEE a combination
    puzzle". `elements.threat_view` says what the monster is; this says what
    you have, in the same six rows, in the same order.
    """
    worn = loadout_temper_effects(state, equipped)
    weapon_id = (equipped or {}).get(WEAPON_SLOT, "")
    rows = []
    for eid in TEMPER_ELEMENTS:
        sources = metals_for_element(eid)
        rows.append({
            "element": eid,
            "art": elements.element_view(eid),
            "warded": round(float(worn.get(f"resist_{eid.lower()}", 0.0)), 3),
            "metals": [{"metal": m, "name": METAL_BY_ID[m].name,
                        "rung": METAL_BY_ID[m].rung,
                        "held": held(state, m),
                        "regions": [world.REGION_BY_ID[r]["name"]
                                    for r in METAL_BY_ID[m].regions]}
                       for m in sources],
            "line": temper_counsel(eid)["line"],
        })
    return {
        "smith": dict(SMITH),
        "gold": int(gold),
        "elements": rows,
        "strikes_with": tempered_element(state, weapon_id) if weapon_id else "",
        "worn": worn,
        "resist_cap": elements.RESIST_CAP,
        "piece_cap": elements.PIECE_RESIST_CAP,
        "steps": list(TEMPER_STEP_RESIST),
        "inert": [{"metal": m, "name": METAL_BY_ID[m].name}
                  for m in INERT_METALS],
        "lines": [
            "One element to a blade and one element to a piece. That is not me "
            "being difficult, that is what metal does.",
            "If it is two things, you counter one of them and you wear the "
            "other. There is no bar in this room that does both.",
        ],
    }


# ==========================================================================
# SECTION 3 — THE ART VOCABULARY
# ==========================================================================
#
# `legendaries.py` already asked web/js/lootart.js for a motif pass and an aura
# pass, and listed twelve motifs and six auras. This file uses those and adds
# six more of each kind, in the same shape, for the same pass. There is one
# merged list — ART_MOTIFS and ART_AURAS below — so the art agent reads one
# table and implements one pipeline stage.
#
# Everything here is legible at 24x24 and costs at most two palette entries,
# which is the only real constraint: lootart's BUDGET is fifteen colours and a
# rung that needs a sixteenth is a rung that does not ship.

NEW_ART_MOTIFS = {
    "caliper_jaw": "two opposed arms closing on the body with a measured gap "
                   "between them, the gap narrowing by one pixel per rung",
    "rule_marks": "evenly spaced tick marks along one edge, every fifth mark "
                  "one pixel longer than the rest",
    "quench_line": "a hard horizontal boundary across the body where the metal "
                   "changes shade — the temper line, drawn rather than shaded",
    "forge_mark": "the smith's stamp: three struck pips in a triangle, set near "
                  "the haft, slightly off square because she does it by eye",
    "link": "one closed ring of accent worked into the body, and a second ring "
            "behind it that is drawn only where the first does not cover it",
    "hairline": "a single-pixel fracture that does NOT branch, running with the "
                "long axis rather than across it — a fault, not a break",
}

NEW_ART_AURAS = {
    "quenchsteam": "a two-pixel plume off the upper edge that rises, thins and "
                   "vanishes; six-frame loop, and the loop is deliberately one "
                   "frame longer than the glint so the two never sync",
    "heatglow": "the lowest third of the body cycles one step up its ramp and "
                "back, as if it came out of the fire an hour ago",
    "measure": "a single accent pixel that travels the long axis end to end and "
               "restarts, one pixel per frame — the only aura that reads as an "
               "instrument rather than as power",
    "tallylight": "one accent pixel lights per frame along a row of marks until "
                  "the row is full, then all of them go dark at once",
    "roadglow": "three accent pixels outside the silhouette, arranged as a bent "
                "path, that swap which of them is brightest",
    "unlabelled": "the aura is drawn and then the ROW of pixels that would "
                  "carry a maker's mark is left empty, every frame",
}

# The merged tables. Whoever implements the motif and aura passes implements
# THESE, once — legendaries' twelve and six, plus this file's six and six. Two
# modules asking lootart.js for the same pipeline stage with two different lists
# is how a pipeline stage ends up implemented twice and disagreeing.
ART_MOTIFS = {**legendaries.NEW_ART_MOTIFS, **NEW_ART_MOTIFS}
ART_AURAS = {**legendaries.NEW_ART_AURAS, **NEW_ART_AURAS}

# Shapes legal in the weapon slot, and the material list, taken from
# legendaries.py rather than copied. That module already mirrors lootart.js and
# already fails its own validate() when lootart drifts; a third copy here would
# just be a third thing to forget.
WEAPON_SHAPES = legendaries.LOOTART_SLOT_ALLOWED["weapon"]
LOOTART_MATERIALS = legendaries.LOOTART_MATERIALS

# The hero sprite's own six-step ladder, read straight off items.ARMOR_TIERS so
# a forged blade sits on exactly the ramp the armour already uses. Nine rungs
# map onto six steps; the map is in RUNG_TO_HERO below, and the effect a player
# actually sees is that runework appears at rung six — web/js/sprites.js draws
# runeBlade() from hero rung 3 upward, and switches its glyph at hero rung 5.
#
# Two tiers share a rung three times over, and what separates them is `half` on
# the hero dict: the upper of the pair gets the one detail its `look` describes
# added to the rung below it, because sharing a rung used to mean sharing a
# DRAWING and differing only in trim.
#
# HERO_WEAPON_ANCHOR is not touched and must not be. Every rung is the same
# twelve-row weapon box in the same place; what changes is the grid and the two
# colours.
RUNG_TO_HERO = {1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3, 8: 4, 9: 5}

RARITY_BY_RUNG = {
    1: "COMMON", 2: "UNCOMMON", 3: "UNCOMMON", 4: "RARE", 5: "RARE",
    6: "EPIC", 7: "EPIC", 8: "LEGENDARY", 9: "MYTHIC",
}


def _hex(value: str) -> tuple:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _mix(base: str, tint: str, amount: float) -> str:
    """Blend toward a blade's own tint. Six blades on one metal ramp would be
    six recolours of the same object; a quarter of a tint is enough to tell an
    Analyst's brass from a Warden's cold grey without inventing a ramp per
    blade, and it adds no colours to the sprite — it is still one metal and one
    trim, which is what the fifteen-colour budget cares about."""
    a, b = _hex(base), _hex(tint)
    out = [int(round(a[i] + (b[i] - a[i]) * amount)) for i in range(3)]
    return "#%02x%02x%02x" % tuple(max(0, min(255, c)) for c in out)


def hero_metal(tier: int, tint: str) -> str:
    ramp = items.ARMOR_TIERS["weapon"][RUNG_TO_HERO[tier]]
    return _mix(ramp["metal"], tint, 0.25)


# ==========================================================================
# SECTION 4 — THE RUNG AND THE BLADE
# ==========================================================================

@dataclass(frozen=True)
class Rung:
    tier: int                   # 1..9
    id: str                     # the catalogue id at this rung
    name: str
    rarity: str
    effects: dict
    cost: dict                  # metal id -> units. Empty at rung one.
    gold: int                   # the smith's labour, not the material
    look: str                   # what changed on the sprite, in one line
    technique_rank: str         # what the technique is called at this rung
    technique_text: str         # what the technique now does
    art: dict                   # the lootart spec
    hero: dict                  # the _weapon dict web/js/sprites.js reads

    def to_dict(self) -> dict:
        d = asdict(self)
        d["effect_text"] = describe(self.effects)
        d["rarity_colour"] = items.RARITIES[self.rarity]["colour"]
        d["cost_text"] = cost_text(self.cost, self.gold)
        return d


@dataclass(frozen=True)
class Blade:
    id: str                     # the line's id; equals the rung-six item id
    class_id: str
    line: str                   # the name of the LINE, not of a rung
    technique: str              # the technique's name
    technique_blurb: str        # what it is for, in the player's terms
    argument: str               # the thing this class believes, as an object
    history: tuple              # four lines: made, for, failed, found
    flavour: str
    shape: str                  # lootart shape
    hero_key: str               # items.HERO_WEAPON_KEYS
    tint: str
    metals: dict                # cost slot -> metal id
    rungs: tuple = ()

    def rung(self, tier: int) -> Rung:
        return self.rungs[max(1, min(9, int(tier))) - 1]

    @property
    def made_by(self) -> str:
        return self.history[0]

    @property
    def made_for(self) -> str:
        return self.history[1]

    @property
    def failed(self) -> str:
        return self.history[2]

    @property
    def found(self) -> str:
        return self.history[3]


# --------------------------------------------------------------------------
# The cost shape
# --------------------------------------------------------------------------
# One shape, shared by all six blades, expressed in METAL SLOTS rather than in
# metal ids. Each blade then names which metal fills each slot, so the six lines
# send you to six different parts of the map for comparable work.
#
# The slots are named for the rung of metal they take:
#   r1   the first field metal
#   r2   a chapter-II metal
#   r3   a scanning or mining metal
#   r4a  the blade's primary deep metal
#   r4b  its secondary deep metal
#   r5a  its primary late metal
#   r5b  its secondary late metal
#   r6   Nullsteel, which exists in exactly one place
#
# The curve is deliberately gentle at the bottom and cruel at the top. Rungs two
# through five are roughly a chapter's fighting each; rung eight is most of a
# chapter on its own; rung nine is the reason the last rung is a thing people
# talk about rather than a thing people have.

COST_SHAPE = {
    2: {"r1": 4},
    3: {"r1": 5, "r2": 4},
    4: {"r2": 10, "r3": 6},
    5: {"r3": 14, "r4a": 8},
    6: {"r4a": 18, "r4b": 12},
    7: {"r4a": 24, "r5a": 18},
    8: {"r5a": 34, "r5b": 24, "r4b": 14},
    9: {"r5a": 48, "r6": 28, "r4b": 20},
}

# Vess's labour, in gold. Gold is never the binding constraint and is not meant
# to be: an encounter pays roughly xp//3 gold, so a player farming the metal for
# a rung has earned its fee several times over by the time they have the metal.
# The fee exists so the smith is a business rather than a vending machine, and
# so a player who wants to know whether they can afford it has something to ask.
GOLD_SHAPE = {2: 40, 3: 75, 4: 130, 5: 220, 6: 360, 7: 560, 8: 900, 9: 1500}

# Which cost slots exist at all, in ladder order. Used by validate() and by the
# smith when she explains the route ahead.
COST_SLOTS = ("r1", "r2", "r3", "r4a", "r4b", "r5a", "r5b", "r6")
SLOT_RUNG = {"r1": 1, "r2": 2, "r3": 3, "r4a": 4, "r4b": 4,
             "r5a": 5, "r5b": 5, "r6": 6}


def cost_text(cost: dict, gold: int = 0) -> list:
    out = [f"{units} {METAL_BY_ID[mid].name}"
           for mid, units in sorted(cost.items(),
                                    key=lambda kv: (-METAL_BY_ID[kv[0]].rung,
                                                    kv[0]))]
    if gold:
        out.append(f"{gold} gold for the labour")
    return out


# ==========================================================================
# SECTION 5 — THE SIX BLADES
# ==========================================================================
#
# One per class, and each one is the argument that class makes, made into an
# object. The Analyst measures before cutting, so the Analyst's weapon is a
# measuring instrument that has never cut anything. The Warden finds the edge of
# things before hitting the middle, so the Warden carries a maul used first for
# finding and second for the other thing. The Seer reads, so the Seer carries
# the smallest weapon in the game and puts it exactly where the program stopped
# being true.
#
# `classes.GEAR_REQUESTS` already authored six EPIC weapons with these ids,
# names and effects. They are RUNG SIX of these ladders, unchanged in all three,
# because a weapon that upgrades across a campaign cannot be born EPIC — that
# would leave two visual steps for eight upgrades. `validate()` proves rung six
# still delivers everything class design promised.
#
# Every rung's `technique_text` says what the technique DOES at that rank, and
# everything it says is one of the keys granted at that rung. A technique is not
# a second effect system running alongside the first; it is the readable name
# for the keys, and that is enforced.


def _rung(blade, tier, rid, name, effects, look, rank_name, rank_text,
          material, accent, motif, aura, silhouette) -> Rung:
    """One rung, with everything derivable derived rather than retyped."""
    cost = {}
    for slot, units in COST_SHAPE.get(tier, {}).items():
        cost[blade["metals"][slot]] = units
    return Rung(
        tier=tier, id=rid, name=name, rarity=RARITY_BY_RUNG[tier],
        effects=dict(effects), cost=cost, gold=GOLD_SHAPE.get(tier, 0),
        look=look, technique_rank=rank_name, technique_text=rank_text,
        art={"shape": blade["shape"], "material": material, "accent": accent,
             "motif": motif, "aura": aura, "silhouette": silhouette,
             "frames": 1 if aura == "stillness" else 0},
        # `line` and `silhouette` ride along because the hero sprite cannot
        # derive either one. `key` is shared — the Calipers and the Chain are
        # both `relic`, the Maul and the Spanner are both `hammer` — so without
        # a line id sprites.js has no way to draw six hands instead of four, and
        # without the band it has no way to know the Needle must stay narrow at
        # rung nine while the Maul is broad at rung one. Both are already
        # decided here; they were simply never sent.
        # `half` is the other thing the sprite cannot derive. Nine tiers map
        # onto six hero rungs, so tiers 3, 5 and 7 arrive on the rung their
        # predecessor already drew and used to differ from it in TRIM AND
        # NOTHING ELSE — colour-only, which is the exact failure the whole
        # ladder exists to avoid, three times in every blade. It is a half
        # step, not a rung, so it does not get its own drawing; it gets the
        # one detail this tier's `look` describes, added inside the band.
        hero={"key": blade["hero_key"], "rung": RUNG_TO_HERO[tier],
              "half": 1 if RUNG_TO_HERO.get(tier - 1) == RUNG_TO_HERO[tier] else 0,
              "line": blade["id"], "silhouette": silhouette,
              "name": name, "look": look,
              "metal": hero_metal(tier, blade["tint"]), "trim": accent},
    )


# --------------------------------------------------------------------------
# THE ANALYST — The Calipers
# --------------------------------------------------------------------------

_CALIPERS = {
    "id": "analysts_calipers", "class_id": "analyst", "shape": "relic",
    "hero_key": "relic", "tint": "#7ec8ff",
    "metals": {"r1": "fieldiron", "r2": "keybrass", "r3": "marshsilver",
               "r4a": "quarterturn", "r4b": "wastes_iron",
               "r5a": "doubling_steel", "r5b": "tilegold", "r6": "nullsteel"},
}

_CALIPERS_RUNGS = (
    _rung(_CALIPERS, 1, "calipers_student", "Student's Calipers",
          {"declare_bonus": 0.04},
          "Field iron, one hinge, a scale scratched on by hand and not quite "
          "even.",
          "THE MEASURED CUT I",
          "Declaring a pattern family before your first run pays a little more "
          "when the declaration proves out. Nothing names the family for you.",
          "iron", "#6f8ba8", "rule_marks", "none", "narrow"),
    _rung(_CALIPERS, 2, "calipers_trued", "Trued Calipers",
          {"declare_bonus": 0.06, "probe_charges": 1},
          "The hinge is true and the jaws close square. A brass scale replaces "
          "the scratches.",
          "THE MEASURED CUT II",
          "One more probe per battle. A probe asserts the RESULT you expect on "
          "an input you chose, and the expectation is yours.",
          "iron", "#8aa6c4", "caliper_jaw", "none", "narrow"),
    _rung(_CALIPERS, 3, "calipers_brassbound", "Brassbound Calipers",
          {"declare_bonus": 0.08, "probe_charges": 1},
          "Keybrass at both jaws and at the pivot. It stops flexing under the "
          "hand, which was the whole complaint.",
          "THE MEASURED CUT III",
          "The declaration bonus grows again. This rung is the one where "
          "declaring stops being a ritual and starts paying for itself.",
          "steel", "#c9a05a", "caliper_jaw", "measure", "narrow"),
    _rung(_CALIPERS, 4, "calipers_stated_cost", "The Stated Cost",
          {"declare_bonus": 0.10, "probe_charges": 1, "declare_slots": 1},
          "A second scale up the outer arm, in a different hand, reading in "
          "orders of magnitude rather than in units.",
          "THE MEASURED CUT IV",
          "A second declaration slot, so the pattern call and the complexity "
          "call stop competing for the same breath.",
          "steel", "#a8b4d0", "rule_marks", "measure", "standard"),
    _rung(_CALIPERS, 5, "calipers_held_guess", "Calipers of the Held Guess",
          {"declare_bonus": 0.12, "probe_charges": 1, "declare_slots": 1,
           "perf_insight": 1},
          "Marshsilver at the jaw tips, bright at the ends and dull through the "
          "middle, which is also how the measurement reads.",
          "THE MEASURED CUT V",
          "Performance trials report their timing budget. You are told what the "
          "trial is willing to spend, never what to spend it on.",
          "steel", "#b9c8c0", "quench_line", "measure", "standard"),
    _rung(_CALIPERS, 6, "analysts_calipers", "The Analyst's Calipers",
          {"declare_bonus": 0.15, "probe_charges": 1, "declare_slots": 1,
           "perf_insight": 1},
          "Quarterturn bronze through the arms and the first runework up the "
          "outer scale. This is the object the Guild has a drawing of.",
          "THE MEASURED CUT VI",
          "The instrument the Guild recognises. Everything it does, it has been "
          "doing since rung one; it now does all of it at once and well.",
          "steel", "#b07a45", "caliper_jaw", "coldlight", "standard"),
    _rung(_CALIPERS, 7, "calipers_narrow_interval",
          "Calipers of the Narrow Interval",
          {"declare_bonus": 0.20, "probe_charges": 2, "declare_slots": 1,
           "perf_insight": 1, "probe_refund": 0.15},
          "Wastes-iron pins. The jaws now close to a gap you cannot see and the "
          "scale reads it anyway.",
          "THE MEASURED CUT VII",
          "A second extra probe, and a correct probe sometimes refunds its own "
          "charge. Being right about where to look costs less than being "
          "thorough about it.",
          "steel", "#8fa8c8", "boundary", "coldlight", "standard"),
    _rung(_CALIPERS, 8, "calipers_proven_bound", "The Proven Bound",
          {"declare_bonus": 0.26, "probe_charges": 2, "declare_slots": 2,
           "perf_insight": 1, "probe_refund": 0.25, "first_try_bonus": 0.15},
          "Doubling steel and tilegold. Three scales now, and the third one is "
          "read from the far side by somebody watching you work.",
          "THE MEASURED CUT VIII",
          "A third declaration slot, and clearing on your first submission pays "
          "properly. The Analyst has always claimed one submission is enough; "
          "this is the rung where the game starts paying for the claim.",
          "gold", "#e0b44a", "rule_marks", "coldlight", "broad"),
    _rung(_CALIPERS, 9, "calipers_standing_hypothesis",
          "THE STANDING HYPOTHESIS",
          {"declare_bonus": 0.34, "probe_charges": 2, "declare_slots": 2,
           "perf_insight": 1, "probe_refund": 0.35, "first_try_bonus": 0.22,
           "probe_first_free": 2},
          "Nullsteel at the pivot, and the maker's row on the arm is blank. It "
          "measures with no scale visible at all.",
          "THE MEASURED CUT IX",
          "The first probe of every battle is free and returns two cases you "
          "chose. You still choose them, you still say what you expect, and the "
          "Calipers still have no edge.",
          "gold", "#cfd2e8", "caliper_jaw", "unlabelled", "broad"),
)


CALIPERS = Blade(
    id="analysts_calipers", class_id="analyst",
    line="The Analyst's Calipers",
    technique="THE MEASURED CUT",
    technique_blurb=(
        "You say what the problem is and what it will cost before you touch it, "
        "and the Calipers pay you for being right and tell you early when you "
        "are wrong. Nothing it grants is worth anything to a player who will "
        "not commit to a claim first."),
    argument="Measure, then cut. The measuring is the expensive part and it is "
             "the part everyone skips.",
    history=(
        "Made by an apprentice of the Oracle who was told to estimate the "
        "Tower's height and came back four days later with a number and a "
        "method.",
        "Made for surveying, which is why it has jaws and no edge. Nobody in "
        "the Guild has ever agreed on whether it counts as a weapon.",
        "It failed its second owner, who read the measurement correctly, wrote "
        "it in the margin, and then wrote the code she had already decided to "
        "write.",
        "Found in the Fields of Syntax, in a surveyor's kit, closed on a gap of "
        "exactly one and set down carefully."),
    flavour="It measures the problem. It has never once cut anything.",
    shape="relic", hero_key="relic", tint="#7ec8ff",
    metals=_CALIPERS["metals"],
    rungs=_CALIPERS_RUNGS,
)



# --------------------------------------------------------------------------
# THE BERSERKER — The First Draft
# --------------------------------------------------------------------------

_DRAFT = {
    "id": "draft_axe", "class_id": "berserker", "shape": "axe",
    "hero_key": "axe", "tint": "#ff7a4a",
    "metals": {"r1": "fieldiron", "r2": "loomsteel", "r3": "faultsteel",
               "r4a": "heartwood_iron", "r4b": "quarterturn",
               "r5a": "doubling_steel", "r5b": "tilegold", "r6": "nullsteel"},
}

_DRAFT_RUNGS = (
    _rung(_DRAFT, 1, "draft_blunt", "Blunt Draft",
          {"rank_grace": 0.05},
          "Field iron on a green haft. Heavy at the head and it will take your "
          "wrist off if you swing it politely.",
          "REDLINE I",
          "A little more clock before the rank drops. The clock only ever "
          "decides your rank; correctness is never graded on a curve.",
          "iron", "#a06a4a", "hairline", "none", "broad"),
    _rung(_DRAFT, 2, "draft_working", "Working Draft",
          {"rank_grace": 0.08, "iteration_bonus": 0.05, "stamina_max": 1},
          "The haft is seasoned and wrapped. The head has been reground once, "
          "badly, by its owner.",
          "REDLINE II",
          "One more stamina, and failed submissions that precede an unaided "
          "clear start paying. You are being paid for the iteration, not for "
          "the failure.",
          "iron", "#b8784a", "forge_mark", "none", "broad"),
    _rung(_DRAFT, 3, "draft_second_pass", "Second Pass",
          {"rank_grace": 0.10, "iteration_bonus": 0.08, "stamina_max": 1},
          "Loomsteel welded along the bit. The grain reorders overnight and the "
          "edge is never quite where you left it.",
          "REDLINE III",
          "Both rates grow. This is the rung where a fast wrong first attempt "
          "is measurably better than a slow right one.",
          "steel", "#9aa4b8", "seam", "heatglow", "broad"),
    _rung(_DRAFT, 4, "draft_revision", "The Revision",
          {"rank_grace": 0.13, "iteration_bonus": 0.10, "retry_grace": 1,
           "stamina_max": 2},
          "Faultsteel through the eye, hairline and all. The crack is the "
          "useful part and the smith left it showing.",
          "REDLINE IV",
          "Your first failed submission each encounter costs no stamina. The "
          "attempt still fails and is still recorded as a failure.",
          "steel", "#7e6f66", "hairline", "heatglow", "broad"),
    _rung(_DRAFT, 5, "draft_short_clock", "Draft of the Short Clock",
          {"rank_grace": 0.16, "iteration_bonus": 0.12, "retry_grace": 1,
           "stamina_max": 2},
          "Heartwood iron in the haft. Lighter than it looks, rings twice, and "
          "comes back up faster than you swung it down.",
          "REDLINE V",
          "More grace and more iteration pay. The axe is now built entirely "
          "around getting to a second attempt sooner.",
          "steel", "#6f7a55", "thorn", "heatglow", "broad"),
    _rung(_DRAFT, 6, "draft_axe", "The First Draft",
          {"rank_grace": 0.20, "iteration_bonus": 0.15, "retry_grace": 1,
           "stamina_max": 3},
          "Quarterturn bronze at the cheeks and the first runework down the "
          "bit. It stops being a tool somebody found.",
          "REDLINE VI",
          "The axe the Coliseum's records name. Twenty per cent more clock, "
          "three more stamina, and three failures' worth of iteration pay on "
          "every unaided clear.",
          "steel", "#b07a45", "forge_mark", "emberfall", "broad"),
    _rung(_DRAFT, 7, "draft_unhesitating", "The Unhesitating Draft",
          {"rank_grace": 0.25, "iteration_bonus": 0.20, "retry_grace": 1,
           "stamina_max": 4},
          "Doubling steel plates the bit. Each plate is twice the last and the "
          "outermost is theatrical.",
          "REDLINE VII",
          "Four more stamina, which is four more bad attempts before Training "
          "Camp calls you in. That is the entire Berserker thesis, priced.",
          "steel", "#8fa8c8", "quench_line", "emberfall", "broad"),
    _rung(_DRAFT, 8, "draft_struck_line", "The Struck Line",
          {"rank_grace": 0.30, "iteration_bonus": 0.26, "retry_grace": 2,
           "stamina_max": 6, "recovery_grace": 0.20},
          "Tilegold inlaid down the haft in a single struck line, as though "
          "somebody crossed the weapon out and kept it anyway.",
          "REDLINE VIII",
          "Two free failed submissions per encounter, and extra clock on an "
          "encounter you already failed this session. Coming back at a problem "
          "is cheaper than arriving at it perfect.",
          "gold", "#e0b44a", "tally", "emberfall", "broad"),
    _rung(_DRAFT, 9, "draft_that_shipped", "THE DRAFT THAT SHIPPED",
          {"rank_grace": 0.36, "iteration_bonus": 0.34, "retry_grace": 2,
           "stamina_max": 8, "recovery_grace": 0.30, "focus_from_failure": 3},
          "Nullsteel bit, unlabelled, on a haft worn to the shape of one "
          "specific pair of hands.",
          "REDLINE IX",
          "A failed submission restores three focus instead of costing stamina. "
          "It is still a failure, it is still on your record, and it now feeds "
          "the next attempt.",
          "gold", "#ff9d4a", "forge_mark", "unlabelled", "broad"),
)


DRAFT = Blade(
    id="draft_axe", class_id="berserker",
    line="The First Draft",
    technique="REDLINE",
    technique_blurb=(
        "It buys permission to be wrong quickly. Every rank of it makes the "
        "early, bad, submitted attempt cheaper — never more likely to pass, and "
        "never scored as though it passed."),
    argument="The first draft is a weapon. The blank page is the enemy and "
             "nothing else on this list has ever killed anybody.",
    history=(
        "Made in an afternoon by a smith who had been asked for a masterwork "
        "and had until sundown.",
        "Made for clearing ground. It is a felling axe. The Guild's armoury "
        "catalogued it as a tool for eleven years before anyone tried it on "
        "something that moved.",
        "It failed a swordsman who spent the morning deciding which of his "
        "eleven weapons to carry into the Coliseum and arrived at noon with all "
        "of them.",
        "Found buried to the haft in the Coliseum's sand, mid-swing, by "
        "somebody who had clearly stopped needing it."),
    flavour="Blunt, early, and somehow already most of the way there.",
    shape="axe", hero_key="axe", tint="#ff7a4a",
    metals=_DRAFT["metals"],
    rungs=_DRAFT_RUNGS,
)



# --------------------------------------------------------------------------
# THE ARCHIVIST — The Chain of Recall
# --------------------------------------------------------------------------

_CHAIN = {
    "id": "recall_chain", "class_id": "archivist", "shape": "relic",
    "hero_key": "relic", "tint": "#c8a8ff",
    "metals": {"r1": "fieldiron", "r2": "keybrass", "r3": "faultsteel",
               "r4a": "wastes_iron", "r4b": "heartwood_iron",
               "r5a": "tilegold", "r5b": "doubling_steel", "r6": "nullsteel"},
}

_CHAIN_RUNGS = (
    _rung(_CHAIN, 1, "chain_short", "Short Chain",
          {"retest_bonus": 0.08},
          "Four links of field iron on a ring. It is barely a chain and it is "
          "already too heavy.",
          "THE OPEN DRAWER I",
          "Memory ambushes pay a little more. An ambush is a problem you "
          "already solved, asked again later, with nothing revealed.",
          "iron", "#9a8fb8", "link", "none", "narrow"),
    _rung(_CHAIN, 2, "chain_linked", "Linked Chain",
          {"retest_bonus": 0.12, "mana_max": 3},
          "Keybrass links, each warm on the side facing a vault you have "
          "already emptied.",
          "THE OPEN DRAWER II",
          "Three more focus, which is what buys the retrieval in the first "
          "place.",
          "iron", "#c9a05a", "link", "none", "narrow"),
    _rung(_CHAIN, 3, "chain_three_links", "Chain of Three Links",
          {"retest_bonus": 0.16, "mana_max": 4},
          "Three heavy links and a hundred small ones. The heavy three are "
          "labelled and the labels are worn off.",
          "THE OPEN DRAWER III",
          "The ambush bonus grows. The Archivist's economy is now visibly "
          "better than everyone else's on old material.",
          "steel", "#a89aff", "chain", "coldlight", "narrow"),
    _rung(_CHAIN, 4, "chain_weighted", "The Weighted Chain",
          {"retest_bonus": 0.20, "mana_max": 5, "retest_charges": 1},
          "Faultsteel weights at each end. Every weight has its hairline and "
          "every hairline is somebody's forgotten fact.",
          "THE OPEN DRAWER IV",
          "One more memory ambush offered per day. Offered, not forced; you "
          "still choose to take the fight.",
          "steel", "#7e6f66", "chain", "coldlight", "narrow"),
    _rung(_CHAIN, 5, "chain_second_asking", "Chain of the Second Asking",
          {"retest_bonus": 0.25, "mana_max": 6, "retest_charges": 1,
           "srs_preview": 1},
          "Wastes-iron through the middle span. Two links near each other lean "
          "together; the whole chain lies in a road.",
          "THE OPEN DRAWER V",
          "The day's ambushes are listed before you set out. You learn WHICH "
          "skills are due, which is a schedule, not a shortcut.",
          "steel", "#6a6470", "index_dot", "coldlight", "standard"),
    _rung(_CHAIN, 6, "recall_chain", "The Chain of Recall",
          {"retest_bonus": 0.30, "mana_max": 8, "retest_charges": 1,
           "srs_preview": 1},
          "Heartwood iron links, each containing a smaller link, and the first "
          "runework along the span.",
          "THE OPEN DRAWER VI",
          "The chain the Archivist describes to new students. A third more pay "
          "on everything you are asked to prove twice.",
          "steel", "#6f7a55", "chain", "coldlight", "standard"),
    _rung(_CHAIN, 7, "chain_long_interval", "Chain of the Long Interval",
          {"retest_bonus": 0.38, "mana_max": 10, "retest_charges": 2,
           "srs_preview": 1, "interval_stretch": 0.15},
          "Tilegold at every fifth link. The gold ones are cold until you walk "
          "ground you have walked before.",
          "THE OPEN DRAWER VII",
          "Ambushes schedule further out and pay for the distance. Longer gaps "
          "are harder and that is the entire point of them.",
          "gold", "#e0b44a", "spiral", "tallylight", "standard"),
    _rung(_CHAIN, 8, "chain_unerased", "The Unerased Chain",
          {"retest_bonus": 0.48, "mana_max": 12, "retest_charges": 2,
           "srs_preview": 1, "interval_stretch": 0.25, "spell_refund": 1},
          "Doubling steel doubles the span every fifth link and the last span "
          "is absurd. She keeps it because it is honest.",
          "THE OPEN DRAWER VIII",
          "A learning spell's focus comes back in full if you then clear that "
          "problem unaided. The spell still costs you the rank it always cost.",
          "gold", "#8fa8c8", "tally", "tallylight", "broad"),
    _rung(_CHAIN, 9, "chain_learned_once", "NOTHING IS LEARNED ONCE",
          {"retest_bonus": 0.60, "mana_max": 14, "retest_charges": 3,
           "srs_preview": 1, "interval_stretch": 0.35, "spell_refund": 1,
           "retest_storm": 2},
          "One nullsteel link, unmarked, that the others are all attached to.",
          "THE OPEN DRAWER IX",
          "Memory ambushes come twice as often and pay triple. This is a "
          "harder game than the one everyone else is playing and it is "
          "voluntary.",
          "gold", "#c8a8ff", "link", "unlabelled", "broad"),
)


CHAIN = Blade(
    id="recall_chain", class_id="archivist",
    line="The Chain of Recall",
    technique="THE OPEN DRAWER",
    technique_blurb=(
        "It drags things you already learned back into the present and pays you "
        "for still knowing them. Every rank makes retrieval practice more "
        "frequent, further apart, or better paid — and retrieval practice is "
        "the only study method in this game with evidence behind it."),
    argument="Nothing is learned once. A thing you cannot produce on the "
             "fourteenth day was not knowledge, it was a good afternoon.",
    history=(
        "Made by the Archivist's predecessor out of the vault keys of rooms "
        "whose contents she had already committed to memory.",
        "Made for carrying, not for opening. Each link is one thing she was "
        "asked to prove again and did.",
        "It failed a scholar who read the whole Stringwood index twice in a "
        "night and could not, a week later, name three things in it.",
        "Found in the Highlands, coiled inside a vault that had been opened "
        "from the inside."),
    flavour="Every link is a thing you once knew and were made to prove again.",
    shape="relic", hero_key="relic", tint="#c8a8ff",
    metals=_CHAIN["metals"],
    rungs=_CHAIN_RUNGS,
)



# --------------------------------------------------------------------------
# THE WARDEN — The Boundary Maul
# --------------------------------------------------------------------------

_MAUL = {
    "id": "boundary_maul", "class_id": "warden", "shape": "hammer",
    "hero_key": "hammer", "tint": "#8fd07a",
    "metals": {"r1": "fieldiron", "r2": "loomsteel", "r3": "marshsilver",
               "r4a": "heartwood_iron", "r4b": "wastes_iron",
               "r5a": "tilegold", "r5b": "doubling_steel", "r6": "nullsteel"},
}

_MAUL_RUNGS = (
    _rung(_MAUL, 1, "maul_split", "Split Maul",
          {"crit_bonus": 0.06},
          "Field iron head, split down one cheek, on a haft that was a fence "
          "post last month.",
          "PERIMETER STRIKE I",
          "Striking a weakness pays a little more. A weakness is an edge case "
          "and it is on you to find it.",
          "iron", "#6f8a5a", "boundary", "none", "broad"),
    _rung(_MAUL, 2, "maul_bound", "Bound Maul",
          {"crit_bonus": 0.09, "probe_charges": 1},
          "The split is wire-bound and the binding is neater than the head "
          "deserves.",
          "PERIMETER STRIKE II",
          "One more probe per battle. A probe is a test you wrote before the "
          "code, which is the whole habit this class is named after.",
          "iron", "#8fd07a", "boundary", "none", "broad"),
    _rung(_MAUL, 3, "maul_first_case", "Maul of the First Case",
          {"crit_bonus": 0.12, "probe_charges": 1},
          "Loomsteel face. The grain reorders and the strike marks on it never "
          "match the ones from yesterday.",
          "PERIMETER STRIKE III",
          "More pay for striking a weakness. At this rung the maul is already "
          "better than any found weapon at rewarding a correct edge call.",
          "steel", "#9aa4b8", "rule_marks", "coldlight", "broad"),
    _rung(_MAUL, 4, "maul_empty_input", "Maul of the Empty Input",
          {"crit_bonus": 0.15, "probe_charges": 1, "edge_ward": 1},
          "Marshsilver rings at both ends of the head. Bright at the extremes, "
          "dull through the middle, exactly as advertised.",
          "PERIMETER STRIKE IV",
          "An edge case you name before running, that turns out to be real, "
          "becomes a ward that absorbs one failed submission. Naming a case "
          "that is not real buys nothing.",
          "steel", "#b9c8c0", "boundary", "coldlight", "broad"),
    _rung(_MAUL, 5, "maul_named_edge", "The Named Edge",
          {"crit_bonus": 0.18, "probe_charges": 1, "edge_ward": 1,
           "reveal_category": 1},
          "Heartwood iron haft, ringing twice, with a smaller haft inside it "
          "that nobody has ever needed.",
          "PERIMETER STRIKE V",
          "Probes name the failure CATEGORY they would trigger. The category, "
          "never the input and never the expected value.",
          "steel", "#6f7a55", "thorn", "coldlight", "broad"),
    _rung(_MAUL, 6, "boundary_maul", "The Boundary Maul",
          {"crit_bonus": 0.20, "probe_charges": 1, "edge_ward": 1,
           "reveal_category": 1},
          "Wastes-iron face and the first runework around the crown. Set it "
          "near another maul and they lean together.",
          "PERIMETER STRIKE VI",
          "The maul the Testsmith signs. One ward, one extra probe, and every "
          "weakness strike paying a fifth more.",
          "steel", "#6a6470", "boundary", "coldlight", "broad"),
    _rung(_MAUL, 7, "maul_nine_classes", "Maul of the Nine Classes",
          {"crit_bonus": 0.26, "probe_charges": 2, "edge_ward": 2,
           "reveal_category": 1},
          "Tilegold banding, cold in the dark, warm over ground you have "
          "already cleared.",
          "PERIMETER STRIKE VII",
          "Two wards and a second extra probe. Nine classes of input exist; "
          "naming all nine is still expensive and still not clever.",
          "gold", "#e0b44a", "tally", "tallylight", "broad"),
    _rung(_MAUL, 8, "maul_perimeter", "The Perimeter",
          {"crit_bonus": 0.34, "probe_charges": 2, "edge_ward": 2,
           "reveal_category": 1, "weakness_scan": 1},
          "Doubling steel through the head, each course twice the last, and the "
          "outer course is where the weight went.",
          "PERIMETER STRIKE VIII",
          "One of the enemy's weakness CLASSES is named at the start of the "
          "fight. The class. Not the input, not the value, not the approach.",
          "gold", "#8fa8c8", "boundary", "tallylight", "broad"),
    _rung(_MAUL, 9, "maul_last_element", "THE LAST ELEMENT",
          {"crit_bonus": 0.44, "probe_charges": 2, "edge_ward": 3,
           "reveal_category": 1, "weakness_scan": 1, "boundary_sense": 1},
          "Nullsteel face with no maker's row. It strikes the first and last of "
          "anything and is indifferent to the middle.",
          "PERIMETER STRIKE IX",
          "Probes on the first and last element of any input are free and "
          "unlimited. You still choose the input, still state what you expect, "
          "and still write the function.",
          "gold", "#8fd07a", "boundary", "unlabelled", "broad"),
)


MAUL = Blade(
    id="boundary_maul", class_id="warden",
    line="The Boundary Maul",
    technique="PERIMETER STRIKE",
    technique_blurb=(
        "You name where the code will break before the code exists, and the "
        "maul turns correct calls into wards that absorb a failed submission. "
        "Every rank of it is worth exactly as much as your ability to predict "
        "an edge case, and worth nothing at all otherwise."),
    argument="Name what breaks it, then write it. The empty list is not an "
             "afterthought; it is the first thing.",
    history=(
        "Made by the Testsmith, who was asked for a weapon and delivered an "
        "instrument for locating the edges of things, with a weapon attached "
        "at the far end as a courtesy.",
        "Made for surveying foundations. It finds the boundary of a structure "
        "by striking near it and listening, which is also how it fights.",
        "It failed a Warden who named nine classes of input before every "
        "encounter, was right about all nine every time, and never once "
        "finished inside the clock.",
        "Found in the Marsh, upright in the reeds at the exact line where the "
        "ward had broken, marking it."),
    flavour="It is used for finding the edge of things, and then for the other "
            "thing.",
    shape="hammer", hero_key="hammer", tint="#8fd07a",
    metals=_MAUL["metals"],
    rungs=_MAUL_RUNGS,
)



# --------------------------------------------------------------------------
# THE ARTIFICER — The Toolwright's Spanner
# --------------------------------------------------------------------------

_SPANNER = {
    "id": "toolwrights_spanner", "class_id": "artificer", "shape": "hammer",
    "hero_key": "hammer", "tint": "#e8c37d",
    "metals": {"r1": "fieldiron", "r2": "keybrass", "r3": "faultsteel",
               "r4a": "quarterturn", "r4b": "heartwood_iron",
               "r5a": "doubling_steel", "r5b": "tilegold", "r6": "nullsteel"},
}

_SPANNER_RUNGS = (
    _rung(_SPANNER, 1, "spanner_loose", "Loose Spanner",
          {"refactor_bonus": 0.05},
          "Field iron, one jaw, and enough play in it to round off anything you "
          "care about.",
          "THE SECOND FITTING I",
          "Re-clearing a solved encounter with a shorter or measurably faster "
          "solution pays. You write the shorter one.",
          "iron", "#a08a52", "forge_mark", "none", "narrow"),
    _rung(_SPANNER, 2, "spanner_fitted", "Fitted Spanner",
          {"refactor_bonus": 0.08, "bench_slots": 1},
          "The jaw is shimmed true. Keybrass on the adjuster, warm on one side "
          "only.",
          "THE SECOND FITTING II",
          "One bench slot. A helper you wrote and cleared comes back with you "
          "into later adventure encounters, and it is your code.",
          "iron", "#c9a05a", "seam", "none", "narrow"),
    _rung(_SPANNER, 3, "spanner_and_shim", "Spanner and Shim",
          {"refactor_bonus": 0.11, "bench_slots": 1, "mana_max": 3},
          "A set of shims on a ring at the butt. Four of them. She uses two.",
          "THE SECOND FITTING III",
          "Three more focus and a better rewrite bonus. Building costs focus "
          "and this is the rung where you stop rationing it.",
          "steel", "#b8a893", "seam", "heatglow", "narrow"),
    _rung(_SPANNER, 4, "spanner_second_fitting", "The Second Fitting",
          {"refactor_bonus": 0.14, "bench_slots": 1, "mana_max": 4},
          "Faultsteel handle, hairline showing, stamped where the last owner's "
          "stamp was filed off.",
          "THE SECOND FITTING IV",
          "More focus, more pay for the rewrite. The Artificer's whole loop — "
          "make it work, then make it right — is now the cheapest loop in the "
          "game to run.",
          "steel", "#7e6f66", "hairline", "heatglow", "standard"),
    _rung(_SPANNER, 5, "spanner_kept_helper", "Spanner of the Kept Helper",
          {"refactor_bonus": 0.17, "bench_slots": 2, "mana_max": 5},
          "Quarterturn bronze through the head. Set it down square; it will be "
          "square the other way by morning.",
          "THE SECOND FITTING V",
          "A second bench slot. Two helpers travel with you, editable, and "
          "Interview Mode empties the bench at the door.",
          "steel", "#b07a45", "forge_mark", "heatglow", "standard"),
    _rung(_SPANNER, 6, "toolwrights_spanner", "The Toolwright's Spanner",
          {"refactor_bonus": 0.20, "bench_slots": 2, "mana_max": 6},
          "Heartwood iron grip with a smaller grip inside it, and the first "
          "runework along the shank.",
          "THE SECOND FITTING VI",
          "The spanner the Toolwright's own students are issued a drawing of. "
          "Two slots, six focus, a fifth more on every rewrite.",
          "steel", "#6f7a55", "spiral", "heatglow", "standard"),
    _rung(_SPANNER, 7, "spanner_shared_bench", "Spanner of the Shared Bench",
          {"refactor_bonus": 0.26, "bench_slots": 3, "mana_max": 8,
           "design_rubric": 1},
          "Doubling steel jaws. The larger jaw is exactly twice the smaller and "
          "she has never needed it.",
          "THE SECOND FITTING VII",
          "An extra rubric point on design answers — worth XP, and requiring "
          "one more argument from you than the question asked for.",
          "steel", "#8fa8c8", "rule_marks", "quenchsteam", "standard"),
    _rung(_SPANNER, 8, "spanner_standing_toolkit", "The Standing Toolkit",
          {"refactor_bonus": 0.34, "bench_slots": 4, "mana_max": 10,
           "design_rubric": 1, "mana_regen": 2},
          "Tilegold at every fitting, cold until you are back somewhere you "
          "have already solved.",
          "THE SECOND FITTING VIII",
          "Four bench slots and focus back after every cleared encounter. The "
          "bench is now a working engineer's utils file, which is what it has "
          "always been.",
          "gold", "#e0b44a", "chain", "quenchsteam", "broad"),
    _rung(_SPANNER, 9, "spanner_built_once", "BUILT ONCE, PROPERLY",
          {"refactor_bonus": 0.44, "bench_slots": 5, "mana_max": 12,
           "design_rubric": 2, "mana_regen": 3, "second_wind": 1},
          "Nullsteel head, no stamp, on a handle somebody has clearly been "
          "using daily for a very long time.",
          "THE SECOND FITTING IX",
          "One free re-cast per battle without breaking your combo, five bench "
          "slots, two extra rubric points. Each rubric point is another "
          "argument you have to make.",
          "gold", "#e8c37d", "forge_mark", "unlabelled", "broad"),
)


SPANNER = Blade(
    id="toolwrights_spanner", class_id="artificer",
    line="The Toolwright's Spanner",
    technique="THE SECOND FITTING",
    technique_blurb=(
        "It pays for building things twice: once badly to learn the shape, once "
        "properly to keep. Every rank widens the bench you carry forward and "
        "raises what a measurably better rewrite is worth."),
    argument="Build it once, properly. The second time you write the same "
             "helper is the first time you should have noticed.",
    history=(
        "Made by a Toolwright who had made four hundred other things first and "
        "was, by her own account, finally getting the hang of it.",
        "Made for fitting other tools. It is the only weapon in the Guild's "
        "catalogue whose entry lists what it is compatible with.",
        "It failed an engineer who kept a bench of six hundred helpers, every "
        "one of them written for exactly one problem and never called again.",
        "Found in the Citadel, in a bracket on a wall, holding the bracket on."),
    flavour="It fits three things badly and one thing perfectly, and the owner "
            "knows which.",
    shape="hammer", hero_key="hammer", tint="#e8c37d",
    metals=_SPANNER["metals"],
    rungs=_SPANNER_RUNGS,
)



# --------------------------------------------------------------------------
# THE SEER — The Tracing Needle
# --------------------------------------------------------------------------

_NEEDLE = {
    "id": "tracing_needle", "class_id": "seer", "shape": "dagger",
    "hero_key": "dagger", "tint": "#ff6a7a",
    "metals": {"r1": "fieldiron", "r2": "loomsteel", "r3": "faultsteel",
               "r4a": "wastes_iron", "r4b": "quarterturn",
               "r5a": "tilegold", "r5b": "doubling_steel", "r6": "nullsteel"},
}

_NEEDLE_RUNGS = (
    _rung(_NEEDLE, 1, "needle_bent", "Bent Needle",
          {"root_cause_bonus": 0.05},
          "Field iron, drawn thin, with a set in it from the last thing it was "
          "put into.",
          "DIVERGENCE I",
          "Naming the failure category before the game names it for you pays a "
          "little. You name it; nothing names it first.",
          "iron", "#a86a72", "hairline", "none", "narrow"),
    _rung(_NEEDLE, 2, "needle_trued", "Trued Needle",
          {"root_cause_bonus": 0.08, "trace_frames": 1},
          "Straightened on a jig and polished at the point. It will now go "
          "where you aim it.",
          "DIVERGENCE II",
          "Step your own submitted code one frame either side of the point it "
          "first diverged. Your code. Nobody else's.",
          "iron", "#c07a86", "eye", "none", "narrow"),
    _rung(_NEEDLE, 3, "needle_first_divergence", "Needle of the First Divergence",
          {"root_cause_bonus": 0.11, "trace_frames": 1},
          "Loomsteel shank. The grain reorders overnight and the point is "
          "always in the same place by morning.",
          "DIVERGENCE III",
          "More pay for a correct root-cause call. The Seer's habit is now "
          "measurably worth having.",
          "steel", "#9aa4b8", "eye", "coldlight", "narrow"),
    _rung(_NEEDLE, 4, "needle_reading", "The Reading Needle",
          {"root_cause_bonus": 0.14, "trace_frames": 1, "reveal_category": 1},
          "Faultsteel edge. The hairline runs with the shank rather than "
          "across it, which is the difference between a fault and a break.",
          "DIVERGENCE IV",
          "Probes name the failure category they would trigger. A category is "
          "a label on a kind of mistake, not a description of the fix.",
          "steel", "#7e6f66", "hairline", "coldlight", "narrow"),
    _rung(_NEEDLE, 5, "needle_named_cause", "Needle of the Named Cause",
          {"root_cause_bonus": 0.17, "trace_frames": 2, "reveal_category": 1},
          "Wastes-iron pommel. Left near another needle it leans; left near "
          "three it points down a road.",
          "DIVERGENCE V",
          "Two frames either side of the divergence. Still your program, still "
          "stepped by you, still no reference implementation anywhere.",
          "steel", "#6a6470", "eye", "coldlight", "standard"),
    _rung(_NEEDLE, 6, "tracing_needle", "The Tracing Needle",
          {"root_cause_bonus": 0.20, "trace_frames": 2, "reveal_category": 1},
          "Quarterturn bronze guard and the first runework up the shank. The "
          "Armorer recognises it across a room.",
          "DIVERGENCE VI",
          "The needle the Armorer signs. Two frames, category-naming probes, "
          "a fifth more on every root cause you call first.",
          "steel", "#b07a45", "eye", "coldlight", "standard"),
    _rung(_NEEDLE, 7, "needle_four_frames", "Needle of Four Frames",
          {"root_cause_bonus": 0.26, "trace_frames": 3, "reveal_category": 1,
           "recovery_grace": 0.15},
          "Tilegold inlay at the guard, cold in the dark and warm over a "
          "problem you have already lost to once.",
          "DIVERGENCE VII",
          "Three frames, and extra clock for rank on an encounter you already "
          "failed this session. The second look is the one that finds it.",
          "gold", "#e0b44a", "spiral", "slowbleed", "standard"),
    _rung(_NEEDLE, 8, "needle_root_cause", "The Root Cause",
          {"root_cause_bonus": 0.34, "trace_frames": 4, "reveal_category": 1,
           "recovery_grace": 0.25, "probe_reveal_value": 1},
          "Doubling steel through the shank, each section twice the last, and "
          "the last section is the handle.",
          "DIVERGENCE VIII",
          "A failed probe shows the true value for the input YOU chose. It is "
          "one case, you selected it, and the function is still unwritten.",
          "gold", "#8fa8c8", "fracture", "slowbleed", "standard"),
    _rung(_NEEDLE, 9, "needle_on_the_screen", "IT IS ALREADY ON THE SCREEN",
          {"root_cause_bonus": 0.44, "trace_frames": 6, "reveal_category": 1,
           "recovery_grace": 0.35, "probe_reveal_value": 1, "prereq_sight": 1},
          "Nullsteel point with the maker's row struck blank. Held up, it does "
          "not reflect the room.",
          "DIVERGENCE IX",
          "A failure names the prerequisite SKILL that actually failed, and "
          "opens the route to it. It tells you what to go and learn, which "
          "is the opposite of doing the learning for you.",
          "gold", "#ff6a7a", "eye", "unlabelled", "standard"),
)


NEEDLE = Blade(
    id="tracing_needle", class_id="seer",
    line="The Tracing Needle",
    technique="DIVERGENCE",
    technique_blurb=(
        "It steps YOUR OWN submitted program around the point it first stopped "
        "agreeing with the specification. It has never shown anyone a reference "
        "implementation and there is no rank at which it starts."),
    argument="The bug is already on the screen. It has been on the screen the "
             "entire time you have been looking somewhere else.",
    history=(
        "Made by the Armorer, from a probe she used for finding the actual "
        "crack in a plate rather than the crack somebody reported.",
        "Made for reading. It is the smallest thing in the Guild's armoury and "
        "the only one issued with instructions on where NOT to put it.",
        "It failed an examiner who could name the failing line in anybody's "
        "program in under a minute and had not written one of his own in six "
        "years.",
        "Found in the Debugging Dungeon, in a plate, at the exact depth where "
        "the metal had stopped being sound."),
    flavour="It goes in exactly where the program stopped being true.",
    shape="dagger", hero_key="dagger", tint="#ff6a7a",
    metals=_NEEDLE["metals"],
    rungs=_NEEDLE_RUNGS,
)



BLADES: tuple = (CALIPERS, DRAFT, CHAIN, MAUL, SPANNER, NEEDLE)
BLADE_BY_ID = {b.id: b for b in BLADES}
BLADE_BY_CLASS = {b.class_id: b for b in BLADES}

# Every rung id, in one place, because the engine needs to know that all
# fifty-four of these are class-restricted and not only the six that
# classes.GEAR_REQUESTS already restricts.
RUNG_BY_ID = {r.id: (b, r) for b in BLADES for r in b.rungs}
FORGE_RESTRICTED = {r.id: b.class_id for b in BLADES for r in b.rungs}

MAX_TIER = 9
MIN_TIER = 1


def blade_for_class(class_id: str) -> Blade | None:
    return BLADE_BY_CLASS.get(class_id)


def rung(blade_id: str, tier: int) -> Rung | None:
    blade = BLADE_BY_ID.get(blade_id)
    return blade.rung(tier) if blade else None


def ladder(blade_id: str) -> list:
    blade = BLADE_BY_ID.get(blade_id)
    return [r.to_dict() for r in blade.rungs] if blade else []


def item_kwargs(blade_id: str, tier: int) -> dict:
    """Exactly the kwargs `items._i()` wants, so a rung can be adopted into the
    catalogue without a rewrite. `class_id` is deliberately absent: restriction
    is enforced by `classes.equippable`, and FORGE_RESTRICTED is what that needs
    to be told about."""
    blade = BLADE_BY_ID.get(blade_id)
    if blade is None:
        return {}
    r = blade.rung(tier)
    nxt = blade.rung(tier + 1) if tier < MAX_TIER else None
    return {
        "id": r.id, "name": r.name, "slot": "weapon", "rarity": r.rarity,
        "effects": dict(r.effects), "set_id": "", "icon": blade.hero_key,
        "source": "upgrade" if tier > MIN_TIER else "quest",
        "skill": "", "flavour": blade.flavour,
        "upgrades": nxt.id if nxt else "",
        "upgrade_requirement": {
            "text": "Bring Vess the metal: " + ", ".join(
                cost_text(nxt.cost, nxt.gold)) if nxt else "",
            "needs": [],
        },
    }


def hero_weapon_look(blade_id: str, tier: int) -> dict:
    """The `_weapon` dict `web/js/sprites.js` already reads.

    `weaponRung()` honours `w.rung` when it is finite and falls back to matching
    `w.name` against its own six-name table otherwise, so this needs no change
    to sprites.js at all. HERO_WEAPON_ANCHOR is untouched.
    """
    r = rung(blade_id, tier)
    return dict(r.hero) if r else {}


def art_at(blade_id: str, tier: int) -> dict:
    r = rung(blade_id, tier)
    return dict(r.art) if r else {}


# ==========================================================================
# SECTION 6 — THE ISOLATION PATH
# ==========================================================================
#
# One function. There is no second one, and nothing else in this module tests a
# mode, reads `config.MODE_*`, or asks an encounter what it is.
#
# BUILD is the right capability: `finalexam.CRUTCHES` defines it as "Attribute
# and gear effects, including extra clock before the rank drops", and a forged
# weapon is gear effects with a name. When the Editor Automaton takes BUILD at
# rung eight of the boss ladder, it takes the blade's numbers with it, and the
# player fights the rest of that ladder on their Python. That is the design of
# the whole game and the forge does not get an exemption from it.
#
# Metal drops go through the same question rather than a separate one, because
# a metal is gear progress and a measured run does not accrue gear progress.

FORGE_CAPABILITY = "BUILD"


def active(encounter) -> bool:
    """Whether a forged blade does anything in this encounter."""
    return not finalexam.sealed(encounter, FORGE_CAPABILITY)


def effects_in(blade_id: str, tier: int, encounter=None) -> dict:
    """The blade's effects as they actually apply here. Sealed is empty, not
    reduced — a half-working legendary is worse than an honest nothing."""
    if encounter is not None and not active(encounter):
        return {}
    r = rung(blade_id, tier)
    return dict(r.effects) if r else {}


def refusal():
    """The engine's standard refusal, so the forge's 'no' reads exactly like
    every other 'no' in the game."""
    return finalexam.refuse(FORGE_CAPABILITY)


# ==========================================================================
# SECTION 7 — STATE
# ==========================================================================
#
# Flat, JSON-shaped, and small. `metals` is a bag; `tiers` is which rung each
# blade line stands at; `racked` is the blade a player has taken off in favour
# of something they found, kept at its tier because a forge does not un-forge
# anything.
#
# Nothing here is skill state and nothing here is evidence. A save that loses
# this file loses gear, not learning.


def new_state() -> dict:
    """`temper` is keyed by ITEM id, not by blade id, because a temper is a
    thing done to an object rather than a rung of a line — a found chest plate
    can be warded and it has no blade to belong to. Every reader of it goes
    through `temper_of`, which tolerates its absence, so a save written before
    SECTION 2c existed loads with everything untempered rather than crashing."""
    return {"metals": {}, "tiers": {}, "racked": "", "forged": 0,
            TEMPER_KEY: {}, "tempered": 0}


def owned_tier(state: dict, blade_id: str) -> int:
    """The rung a player's blade stands at. Zero means they have not been given
    the line yet — the class quest does that, not this module."""
    return int((state or {}).get("tiers", {}).get(blade_id, 0) or 0)


def grant_blade(state: dict, blade_id: str) -> dict:
    """Hand over rung one. Idempotent, so the class quest can be finished twice
    by a save-file accident without resetting anybody's blade."""
    if blade_id not in BLADE_BY_ID:
        return {"error": "no such blade"}
    tiers = state.setdefault("tiers", {})
    if not tiers.get(blade_id):
        tiers[blade_id] = MIN_TIER
    return {"blade": blade_id, "tier": tiers[blade_id]}


def add_metal(state: dict, metal_id: str, units: int = 1) -> dict:
    if metal_id not in METAL_BY_ID:
        return {"error": "no such metal"}
    bag = state.setdefault("metals", {})
    bag[metal_id] = int(bag.get(metal_id, 0)) + int(units)
    return {"metal": metal_id, "held": bag[metal_id]}


def held(state: dict, metal_id: str) -> int:
    return int((state or {}).get("metals", {}).get(metal_id, 0) or 0)


# ==========================================================================
# SECTION 8 — THE UPGRADE
# ==========================================================================


def _shortfall(state: dict, cost: dict) -> dict:
    """What is missing, per metal, before substitution."""
    return {mid: units - held(state, mid)
            for mid, units in cost.items() if held(state, mid) < units}


def _plan_substitution(state: dict, cost: dict, missing: dict) -> dict:
    """Cover a shortfall out of higher metals, best rate first. Returns the
    spend plan, or the part of the shortfall that stays uncovered.

    Deliberately greedy from the CHEAPEST adequate metal upward: a player with
    Nullsteel and Tilegold should have the Tilegold taken first, because the
    thing they are short of is never Nullsteel.

    `cost` is the rung's own bill, and it is here because the substitution pool
    is what the bag holds AFTER the bill is paid, not what it holds now. A metal
    can appear on both sides of this: the Analyst's rung five wants Marshsilver
    AND Quarterturn Bronze, so a player holding only Quarterturn has every bar
    of it claimed by its own line already. Planning against the raw bag spends
    those bars twice — once for the Quarterturn line and once to beat down into
    the Marshsilver the player never had — which quoted an upgrade the player
    could not afford and then settled the difference by leaving the bag at minus
    seven. Reserve first, then plan.
    """
    bag = {mid: max(0, held(state, mid) - int(units))
           for mid, units in cost.items()}
    for mid in METAL_BY_ID:
        bag.setdefault(mid, held(state, mid))
    spend: dict = {}
    still: dict = {}
    for mid, need in sorted(missing.items(),
                            key=lambda kv: METAL_BY_ID[kv[0]].rung):
        want = METAL_BY_ID[mid]
        remaining = need
        for other in sorted(METALS, key=lambda m: m.rung):
            if remaining <= 0:
                break
            cover = substitution_cover(other.rung, want.rung)
            if not cover:
                continue
            have = bag.get(other.id, 0) - spend.get(other.id, 0)
            if have <= 0:
                continue
            use = min(have, math.ceil(remaining / cover))
            spend[other.id] = spend.get(other.id, 0) + use
            remaining -= use * cover
        if remaining > 0:
            still[mid] = remaining
    return {"spend": spend, "still_short": still}


def quote(state: dict, blade_id: str, *, gold: int = 0) -> dict:
    """Everything the smith's counter needs for the next rung of one blade.

    This is the function the UI should call. `upgrade()` calls it too, so a
    quote a player was shown and the upgrade they then bought cannot disagree.
    """
    blade = BLADE_BY_ID.get(blade_id)
    if blade is None:
        return {"error": "no such blade"}
    tier = owned_tier(state, blade_id)
    if tier < MIN_TIER:
        return {"error": "unowned", "blade": blade_id,
                "line": blade.line,
                "text": "Vess has nothing of yours on the bench."}
    if tier >= MAX_TIER:
        current = blade.rung(tier)
        return {"blade": blade_id, "line": blade.line, "tier": tier,
                "at_top": True, "current": current.to_dict(),
                "text": f"{current.name} is finished. There is no rung ten."}

    nxt = blade.rung(tier + 1)
    missing = _shortfall(state, nxt.cost)
    plan = _plan_substitution(state, nxt.cost, missing) if missing \
        else {"spend": {}, "still_short": {}}
    rows = []
    for mid, units in sorted(nxt.cost.items(),
                             key=lambda kv: -METAL_BY_ID[kv[0]].rung):
        metal = METAL_BY_ID[mid]
        rows.append({
            "metal": mid, "name": metal.name, "colour": metal.colour,
            "need": units, "have": held(state, mid),
            "met": held(state, mid) >= units,
            "short": max(0, units - held(state, mid)),
            "regions": [world.REGION_BY_ID[r]["name"] for r in metal.regions],
            "region_ids": list(metal.regions),
        })

    gold_short = max(0, nxt.gold - int(gold))
    ready = not plan["still_short"] and gold_short == 0
    return {
        "blade": blade_id, "line": blade.line, "tier": tier,
        "next_tier": nxt.tier, "at_top": False,
        "current": blade.rung(tier).to_dict(),
        "next": nxt.to_dict(),
        "cost": rows, "gold": nxt.gold, "gold_short": gold_short,
        "substitution": plan["spend"],
        # `short` is what the bag is missing outright; `still_short` is what is
        # missing AFTER substitution. They are different questions and the smith
        # answers both — "you are ready" and "you are ready because I am about to
        # ruin twenty bars of Nullsteel" are not the same sentence.
        "short": dict(missing),
        "still_short": plan["still_short"],
        "ready": ready,
        "changes": rung_diff(blade_id, tier, tier + 1),
    }


def upgrade(state: dict, blade_id: str, *, gold: int = 0,
            allow_substitution: bool = True) -> dict:
    """The only mutator of a tier. Returns the new rung, or why not.

    Gold is passed in and the SPEND is reported back rather than deducted here,
    because the player's purse lives in `engine.state["player"]` and two places
    that both think they own a number is how a purse goes negative.
    """
    q = quote(state, blade_id, gold=gold)
    if q.get("error"):
        return q
    if q.get("at_top"):
        return {"error": "at_top", **q}
    if q["gold_short"]:
        return {"error": "gold", "needs_gold": q["gold_short"], **q}
    if q["still_short"]:
        return {"error": "metal", "still_short": q["still_short"], **q}

    blade = BLADE_BY_ID[blade_id]
    nxt = blade.rung(q["next_tier"])
    bag = state.setdefault("metals", {})

    # THE WHOLE SPEND IS DECIDED BEFORE THE BAG IS TOUCHED.
    #
    # This used to be two loops with a refusal between them: take the direct
    # cost, then notice that substitution was forbidden and return an error. A
    # caller passing allow_substitution=False therefore had its metal taken by
    # the first loop and was handed a refusal by the second, and the rung did
    # not move. A forge that eats the metal and gives nothing back is the one
    # bug this feature cannot ship with, so the refusal comes first and the
    # plan is applied in a single pass once it is known to be payable.
    if q["substitution"] and not allow_substitution:
        return {"error": "metal", "still_short": _shortfall(state, nxt.cost),
                **q}

    spent: dict = {}
    for mid, units in nxt.cost.items():
        take = min(int(units), int(bag.get(mid, 0)))
        if take:
            spent[mid] = spent.get(mid, 0) + take
    for mid, units in q["substitution"].items():
        spent[mid] = spent.get(mid, 0) + int(units)

    # Checked rather than trusted. quote() already said this is payable, but the
    # failure mode if it is ever wrong again is a negative pile of Nullsteel in
    # a save file, which no later code can tell apart from a legitimate one.
    over = {mid: n - int(bag.get(mid, 0)) for mid, n in spent.items()
            if n > int(bag.get(mid, 0))}
    if over:
        return {"error": "metal", "still_short": over, **q}

    for mid, n in spent.items():
        bag[mid] = int(bag.get(mid, 0)) - n

    state.setdefault("tiers", {})[blade_id] = nxt.tier
    state["forged"] = int(state.get("forged", 0)) + 1

    return {
        "blade": blade_id, "line": blade.line, "tier": nxt.tier,
        "rung": nxt.to_dict(), "spent": spent, "gold_spent": nxt.gold,
        "substituted": dict(q["substitution"]),
        "changes": rung_diff(blade_id, nxt.tier - 1, nxt.tier),
        "hero": dict(nxt.hero), "art": dict(nxt.art),
        "lines": SMITH_DONE(blade, nxt),
    }


def rung_diff(blade_id: str, from_tier: int, to_tier: int) -> dict:
    """The three things a rung changes, stated plainly, because 'say plainly in
    the data what each tier costs and what it changes' was the brief."""
    blade = BLADE_BY_ID.get(blade_id)
    if blade is None:
        return {}
    a = blade.rung(from_tier) if from_tier >= MIN_TIER else None
    b = blade.rung(to_tier)
    before = dict(a.effects) if a else {}
    gained, grew = {}, {}
    for key, value in b.effects.items():
        old = before.get(key, 0)
        if key not in before:
            gained[key] = value
        elif value > old:
            grew[key] = (old, value)
    return {
        "power": {
            "new": describe(gained),
            "grown": [f"{EFFECT_LABELS[k].format(v=new, p=int(round(new * 100)))}"
                      f" (was {old if old >= 1 else str(int(round(old * 100))) + '%'})"
                      for k, (old, new) in grew.items()],
            "rarity": (a.rarity if a else "", b.rarity),
        },
        "appearance": {
            "name": (a.name if a else "", b.name),
            "look": b.look,
            "hero_rung": (a.hero["rung"] if a else 0, b.hero["rung"]),
            "metal": (a.hero["metal"] if a else "", b.hero["metal"]),
            "trim": (a.hero["trim"] if a else "", b.hero["trim"]),
            "motif": (a.art["motif"] if a else "", b.art["motif"]),
            "aura": (a.art["aura"] if a else "", b.art["aura"]),
        },
        "technique": {
            "name": blade.technique,
            "rank": (a.technique_rank if a else "", b.technique_rank),
            "text": b.technique_text,
        },
    }


def technique_view(blade_id: str, tier: int) -> dict:
    """The technique, as the skills screen should draw it: nine ranks, where you
    are, and what each rank is. Locked ranks show their NAME and their cost, not
    their text — a ladder you can read to the top is not a ladder you climb."""
    blade = BLADE_BY_ID.get(blade_id)
    if blade is None:
        return {}
    rows = []
    for r in blade.rungs:
        reached = r.tier <= tier
        rows.append({
            "tier": r.tier, "rank": r.technique_rank, "reached": reached,
            "text": r.technique_text if reached else "",
            "cost_text": cost_text(r.cost, r.gold),
        })
    return {"blade": blade_id, "name": blade.technique,
            "blurb": blade.technique_blurb, "at": tier, "ranks": rows}


# ==========================================================================
# SECTION 9 — SWAPPING
# ==========================================================================
#
# The brief's hardest requirement, because it is the one that is easy to fake.
# If the signature blade is simply better, the choice is decoration.
#
# The trade that makes it real is this: a FOUND weapon of the same band carries
# bigger RAW RATES and no capability, and a SIGNATURE blade carries the
# capability and pays for it in rate. `items.CATALOGUE` already contains
# twenty-nine weapons and the numbers below are read off them rather than
# claimed — `linear_edge` really does carry +60% weakness XP and +40% XP, which
# is more raw throughput than any rung of any blade in this file.
#
# What each side trades away, said once:
#
#   A found weapon is what it is. It arrived finished. It will not improve, it
#   has no technique, it cannot be brought to Vess, and the metal you have been
#   carrying stays in your bag doing nothing. In exchange it is available NOW
#   and its percentages are, band for band, roughly a third higher.
#
#   A signature blade grows. Its rung is kept on the rack whether you are
#   carrying it or not, so trying a found weapon for a chapter costs nothing but
#   the rungs you did not forge while you were away. In exchange it asks you to
#   spend four hundred-odd encounters' worth of metal on one object, and it is
#   worse than the alternative at every single point along the way if all you
#   are counting is percentages.
#
# Both halves are true and neither is the trap. A Duelist who wants throughput
# should carry the found weapon and should not feel clever about it.

RATE_KEYS = frozenset({
    "xp_bonus", "crit_bonus", "rank_grace", "loot_luck", "hint_discount",
    "retest_bonus", "declare_bonus", "iteration_bonus", "refactor_bonus",
    "root_cause_bonus", "first_try_bonus", "recovery_grace",
    "interval_stretch", "probe_refund",
})


def _rate_total(effects: dict) -> float:
    return sum(float(v) for k, v in effects.items() if k in RATE_KEYS)


def _capability_count(effects: dict) -> int:
    return sum(1 for k in effects if k not in RATE_KEYS)


def found_weapons(rarity: str) -> list:
    """The real alternatives at one rarity, out of the live catalogue."""
    return [i for i in items.CATALOGUE
            if i.slot == "weapon" and i.rarity == rarity]


def swap_view(blade_id: str, tier: int) -> dict:
    """The comparison screen: this rung against everything the game will
    actually drop in its band, with the trade stated in numbers."""
    blade = BLADE_BY_ID.get(blade_id)
    if blade is None:
        return {}
    r = blade.rung(tier)
    rivals = []
    for item in found_weapons(r.rarity):
        rivals.append({
            "id": item.id, "name": item.name, "icon": item.icon,
            "rarity": item.rarity,
            "effect_text": items.describe(item.effects),
            "rate_total": round(_rate_total(item.effects), 3),
            "capabilities": _capability_count(item.effects),
            "upgrades": bool(item.upgrades),
            "technique": "",
        })
    rivals.sort(key=lambda row: -row["rate_total"])
    mine_rate = _rate_total(r.effects)
    best_rate = max([row["rate_total"] for row in rivals], default=0.0)
    return {
        "blade": blade_id, "tier": tier, "rarity": r.rarity,
        "mine": {"id": r.id, "name": r.name,
                 "effect_text": describe(r.effects),
                 "rate_total": round(mine_rate, 3),
                 "capabilities": _capability_count(r.effects),
                 "technique": f"{blade.technique} — {r.technique_rank}",
                 "upgrades": tier < MAX_TIER},
        "rivals": rivals,
        "rate_gap": round(best_rate - mine_rate, 3),
        "trade": SWAP_TRADE,
        "verdict": _swap_verdict(mine_rate, best_rate, r, blade),
    }


SWAP_TRADE = (
    "A found weapon is finished the moment it drops. Bigger percentages, no "
    "technique, no rung, nothing Vess can do with it. A forged blade is worse "
    "on paper at every band and is the only weapon in the game that grows a "
    "capability. Swap freely — the rung stays on the rack.")


def _swap_verdict(mine: float, best: float, r: Rung, blade: Blade) -> str:
    if best > mine:
        return (f"The best {items.RARITIES[r.rarity]['label'].lower()} weapon in "
                f"the drop tables beats {r.name} by {round((best - mine) * 100)} "
                f"points of raw rate and cannot do {blade.technique}.")
    return (f"{r.name} is ahead on rate as well as capability at this band, "
            f"which means the band is thin. It will not last.")


def rack(state: dict, blade_id: str) -> dict:
    """Take the blade off. The rung is kept; nothing is refunded and nothing is
    lost. A forge does not un-forge anything."""
    if blade_id not in BLADE_BY_ID:
        return {"error": "no such blade"}
    state["racked"] = blade_id
    return {"racked": blade_id, "tier": owned_tier(state, blade_id),
            "text": "Vess will keep it on the wall. It will be at the same rung "
                    "when you want it."}


def unrack(state: dict) -> dict:
    blade_id = state.get("racked", "")
    state["racked"] = ""
    return {"blade": blade_id, "tier": owned_tier(state, blade_id)}


# ==========================================================================
# SECTION 10 — VESS
# ==========================================================================
#
# The Armorer already exists in `world.MENTORS`: she repairs plate, she unpicks
# skill trees, and her subject is debugging. She is not a blacksmith and giving
# her a second job would make her the answer to every question in town.
#
# Vess is the smith. She does three things — upgrade, appraise, and tell you
# what you are short of and where it drops — and the third one is the one that
# matters. A player who does not know that Wastes-iron comes out of the Graph
# Wastes will simply stop trying, and will be right to, because from where they
# are standing the upgrade is indistinguishable from a wall.
#
# So every refusal Vess makes names the metal, the region, the difficulty that
# pays best for it, and roughly how many fights that is. She does not encourage
# anyone. She counts things.
#
# Her sprite is `smith`, which `web/js/sprites.js` already draws for the
# Testsmith. No new NPC art is required for this module to ship.

SMITH = {
    "id": "vess",
    "name": "VESS",
    "role": "the village smith",
    "sprite": "smith",
    "region": "python_village",
    "greeting": "Put it on the bench. I will tell you what it needs and you can "
                "tell me whether that is a problem.",
    "voice": "Dry, numerate, uninterested in whether you are having a nice time. "
             "She has never once said a weapon was worthy of anyone.",
    "history": (
        "She served the Guild's armoury for nineteen years and left over a "
        "disagreement about whether a weapon should be finished when it is "
        "issued.",
        "She holds that it should not, and that an Architect who has not "
        "changed their blade has not changed."),
}

SMITH_LINES = {
    "idle": (
        "Metal, then. Or do not; the bench is not going anywhere.",
        "Everything on that wall was brought to me by somebody who thought they "
        "were nearly finished.",
        "I do not sharpen. Sharpening is what you do to a thing you have given "
        "up on improving."),
    "no_blade": (
        "You have not been issued a line yet. Come back when your order has "
        "given you something with your name on it.",),
    "at_top": (
        "That is rung nine. There is no rung ten and there is no metal left "
        "that I have not already put into it.",
        "I have nothing further to do to that. Go and find out whether it was "
        "the weapon."),
    "ready": (
        "That is the full weight. Leave it overnight.",
        "Yes. All of it, and the fee. Come back in the morning."),
    "no_gold": (
        "The metal is fine. The labour is not free and I am not a charity.",),
}


def SMITH_DONE(blade: Blade, r: Rung) -> list:
    """What she says when a rung lands. Names the three things that changed,
    because the player is about to look at the sprite and should know what to
    look for."""
    return [
        f"{r.name}. Rung {r.tier}.",
        r.look,
        f"{r.technique_rank}. {r.technique_text}",
        "Do not thank me. Thank whatever you took the metal off.",
    ]


def counsel(metal_id: str) -> dict:
    """Where a metal drops, how hard it hits there, and roughly how many fights
    a unit costs. This is the function that stops a player giving up."""
    metal = METAL_BY_ID.get(metal_id)
    if metal is None:
        return {}
    rows = []
    for region_id in metal.regions:
        region = world.REGION_BY_ID[region_id]
        difficulty = typical_difficulty(region_id)
        per = expected_metal(difficulty)
        rows.append({
            "region": region_id, "name": region["name"],
            "numeral": region.get("numeral", ""),
            "typical_difficulty": difficulty,
            "per_encounter": round(per, 3),
            "encounters_per_unit": round(1.0 / per, 1) if per else None,
        })
    rows.sort(key=lambda row: -(row["per_encounter"] or 0))
    best = rows[0] if rows else {}
    where = " and ".join(row["name"] for row in rows)
    rate = (f"about {best.get('encounters_per_unit', '?')} fights a bar at "
            f"{str(best.get('typical_difficulty', '')).lower()}")
    # One source reads as one sentence; two need the better of them named, or
    # the player walks to whichever they thought of first and it is the wrong
    # one. Vess would say which.
    if len(rows) == 1:
        line = (f"{metal.name} comes out of {where} — {rate}. "
                f"Bosses there give three.")
    else:
        line = (f"{metal.name} comes out of {where}. Take {best.get('name', '')}: "
                f"{rate}. Bosses there give three.")
    return {
        "metal": metal.id, "name": metal.name, "rung": metal.rung,
        "colour": metal.colour, "blurb": metal.blurb, "tell": metal.tell,
        "regions": rows, "line": line,
    }


def smith_view(state: dict, blade_id: str = "", *, gold: int = 0,
               class_id: str = "") -> dict:
    """Everything the smith's screen draws: the quote, the shortfall, where the
    shortfall comes from, and what she says about it."""
    blade_id = blade_id or (BLADE_BY_CLASS.get(class_id).id
                            if class_id in BLADE_BY_CLASS else "")
    view = {"smith": dict(SMITH), "lines": list(SMITH_LINES["idle"]),
            "bag": [{"metal": m.id, "name": m.name, "rung": m.rung,
                     "colour": m.colour, "held": held(state, m.id)}
                    for m in METALS],
            "blade": blade_id}
    if not blade_id:
        view["lines"] = list(SMITH_LINES["no_blade"])
        return view

    q = quote(state, blade_id, gold=gold)
    view["quote"] = q
    if q.get("error") == "unowned":
        view["lines"] = list(SMITH_LINES["no_blade"])
        return view
    if q.get("at_top"):
        view["lines"] = list(SMITH_LINES["at_top"])
        return view

    view["technique"] = technique_view(blade_id, q["tier"])
    view["swap"] = swap_view(blade_id, q["tier"])

    lines = []
    for mid, units in sorted(q["short"].items(),
                             key=lambda kv: METAL_BY_ID[kv[0]].rung):
        lines.append(f"You are {units} short of {METAL_BY_ID[mid].name}. "
                     + counsel(mid)["line"])
    if q["substitution"]:
        names = ", ".join(f"{u} {METAL_BY_ID[m].name}"
                          for m, u in q["substitution"].items())
        lines.append(f"I can beat {names} down into what you need. You will "
                     f"lose some of it in the beating. That is the trade.")
    if q["gold_short"]:
        lines.extend(SMITH_LINES["no_gold"])
        lines.append(f"{q['gold_short']} gold short.")
    if q["ready"]:
        lines.extend(SMITH_LINES["ready"])
    view["lines"] = lines or list(SMITH_LINES["idle"])
    return view


def route_ahead(state: dict, blade_id: str) -> list:
    """Every remaining rung, its cost, and where that metal lives. A player who
    can see the whole road can decide whether to walk it; a player who can only
    see the next step decides whether to bother."""
    blade = BLADE_BY_ID.get(blade_id)
    if blade is None:
        return []
    at = owned_tier(state, blade_id)
    out = []
    for r in blade.rungs:
        if r.tier <= max(at, MIN_TIER):
            continue
        out.append({
            "tier": r.tier, "name": r.name, "rarity": r.rarity,
            "gold": r.gold,
            "cost": [{"metal": mid, "name": METAL_BY_ID[mid].name,
                      "units": units, "have": held(state, mid),
                      "where": [world.REGION_BY_ID[x]["name"]
                                for x in METAL_BY_ID[mid].regions]}
                     for mid, units in sorted(
                         r.cost.items(),
                         key=lambda kv: -METAL_BY_ID[kv[0]].rung)],
            "technique_rank": r.technique_rank,
            "encounters": encounters_for(r.cost),
        })
    return out


# ==========================================================================
# SECTION 11 — THE GRIND, MEASURED
# ==========================================================================
#
# Every number below is computed, not claimed. `typical_difficulty()` reads the
# real dungeon plan out of `dungeons.DUNGEONS` and reproduces that module's own
# arithmetic for a room's difficulty, so if somebody retunes a dungeon, these
# estimates move with it instead of quietly becoming a lie.
#
# The model is an honest average at B rank with no luck: metal_chance times
# bundle size. A player at S rank with loot gear does better, which is the
# correct direction for both of those things to push.


def typical_difficulty(region_id: str) -> str:
    """The midpoint of the difficulty band a region's own dungeon can produce.

    `dungeons._difficulty_for` computes the ceiling as floor + 1 + tier and
    clamps to the ladder; this takes the midpoint of floor..ceiling, which is
    what a player grinding a region actually sees over an evening.
    """
    ladder_ = dungeons.DIFFICULTY_LADDER
    for plan in dungeons.DUNGEONS:
        if plan.region != region_id:
            continue
        floor_i = ladder_.index(plan.floor)
        ceiling = min(len(ladder_) - 1, floor_i + 1 + plan.tier)
        return ladder_[(floor_i + ceiling) // 2]
    return "EASY"


def best_yield(metal_id: str) -> float:
    """Units per encounter in the best region that gives this metal up."""
    metal = METAL_BY_ID.get(metal_id)
    if metal is None:
        return 0.0
    return max((expected_metal(typical_difficulty(r)) for r in metal.regions),
               default=0.0)


def encounters_for(cost: dict) -> int:
    """Encounters to farm one rung's cost, at B rank, no luck, region by
    region."""
    total = 0.0
    for mid, units in cost.items():
        per = best_yield(mid)
        if per > 0:
            total += units / per
    return int(math.ceil(total))


def grind_estimate(blade_id: str = "") -> dict:
    """The honest cost of a blade, in fights. Reported per rung, because the
    interesting fact is not the total, it is that rung nine is ten times rung
    two."""
    blades = [BLADE_BY_ID[blade_id]] if blade_id in BLADE_BY_ID else list(BLADES)
    out = {}
    for blade in blades:
        rows, running = [], 0
        for r in blade.rungs:
            if r.tier == MIN_TIER:
                continue
            n = encounters_for(r.cost)
            running += n
            rows.append({
                "tier": r.tier, "name": r.name, "encounters": n,
                "cumulative": running, "gold": r.gold,
                "cost": {mid: units for mid, units in r.cost.items()},
            })
        out[blade.id] = {"class": blade.class_id, "rungs": rows,
                         "total_encounters": running,
                         "total_gold": sum(r.gold for r in blade.rungs)}
    totals = [v["total_encounters"] for v in out.values()]
    return {"blades": out,
            "spread": {"min": min(totals), "max": max(totals),
                       "mean": round(sum(totals) / len(totals), 1)}}


# ==========================================================================
# SECTION 12 — THE PROOFS
# ==========================================================================
#
# Every claim this file makes about itself, checked. `validate()` returns a list
# of problems and an empty list is the pass condition, exactly as
# `legendaries.validate()` works, so one test line covers both.

FORBIDDEN_IN_TECHNIQUE = (
    "the answer", "an answer", "the solution", "a solution", "solves it",
    "solves the", "reveals the approach", "names the pattern",
    "the correct code", "worked solution", "writes it for you",
    "for you automatically", "canonical",
)


def _effect_problems(tag: str, effects: dict) -> list:
    problems = []
    for key, value in effects.items():
        if key not in items.EFFECT_LABELS:
            problems.append(f"{tag}: effect key {key!r} is not in "
                            f"items.EFFECT_LABELS")
            continue
        if key not in FORGE_EFFECT_KEYS:
            problems.append(f"{tag}: effect key {key!r} is not declared in "
                            f"FORGE_EFFECT_KEYS")
        cap = classes.CAPS.get(key)
        if cap is None:
            continue
        if key not in classes.RATE_KEYS:
            # A whole-number capability. `classes.RATE_KEYS` is the
            # discriminator rather than "is the cap an integer", because most
            # rate caps are exactly 1.0 and treating those as capabilities
            # would forbid a blade from granting +5% of anything.
            ceiling = cap - CAP_HEADROOM
            if value > ceiling:
                problems.append(f"{tag}: {key}={value} leaves the tree no room "
                                f"under the classes.CAPS ceiling {cap}")
        elif value > cap * CAP_SHARE + 1e-9:
            problems.append(f"{tag}: {key}={value} exceeds {CAP_SHARE:.0%} of "
                            f"the classes.CAPS ceiling {cap}")
    if len(describe(effects)) != len(effects):
        problems.append(f"{tag}: an effect renders to no text")
    return problems


def validate() -> list:
    problems = []

    # ---- A: the vocabulary is not extended ------------------------------
    for key in FORGE_EFFECT_KEYS:
        if key not in items.EFFECT_LABELS:
            problems.append(f"vocabulary: {key!r} is claimed but absent from "
                            f"items.EFFECT_LABELS")
    for key in SWITCH_KEYS:
        if key in items.SWITCH_KEYS:
            if key in SWITCH_REQUESTS:
                problems.append(f"vocabulary: {key!r} is listed in "
                                f"SWITCH_REQUESTS but items.py already has it")
        elif key not in SWITCH_REQUESTS:
            problems.append(f"vocabulary: {key!r} is a switch here, sums in "
                            f"items.total_effects, and is not in "
                            f"SWITCH_REQUESTS")

    # ---- B: the metals -------------------------------------------------
    seen_regions = set()
    for metal in METALS:
        tag = f"metal {metal.id}"
        if metal.rung not in METAL_RUNGS:
            problems.append(f"{tag}: rung {metal.rung} is off the ladder")
        if not metal.regions:
            problems.append(f"{tag}: drops nowhere")
        for region_id in metal.regions:
            if region_id not in world.REGION_BY_ID:
                problems.append(f"{tag}: region {region_id!r} is not in "
                                f"world.REGIONS")
            if region_id in seen_regions:
                problems.append(f"{tag}: region {region_id!r} already has a "
                                f"metal")
            seen_regions.add(region_id)
        if "!" in metal.blurb or "!" in metal.tell:
            problems.append(f"{tag}: exclamation mark")

    for region in world.REGIONS:
        if region["id"] in NO_METAL_REGIONS:
            continue
        if region["id"] not in seen_regions:
            problems.append(f"region {region['id']}: no metal drops here")

    # The ladder must run with region tier: a metal's rung may never exceed the
    # rung of a metal from a region that unlocks it.
    for metal in METALS:
        for region_id in metal.regions:
            for prereq in world.REGION_BY_ID[region_id].get("unlocks", []):
                other = metal_for_region(prereq)
                if other is not None and other.rung > metal.rung:
                    problems.append(
                        f"metal {metal.id}: rung {metal.rung} is below its "
                        f"prerequisite region's {other.id} at rung {other.rung}")

    used_metals = {mid for b in BLADES for r in b.rungs for mid in r.cost}
    for metal in METALS:
        if metal.id not in used_metals:
            problems.append(f"metal {metal.id}: no blade ever asks for it")

    # ---- C: the blades --------------------------------------------------
    ids = set()
    for blade in BLADES:
        tag = f"blade {blade.id}"
        if blade.class_id not in classes.CLASS_BY_ID:
            problems.append(f"{tag}: class {blade.class_id!r} does not exist")
            continue
        cls = classes.CLASS_BY_ID[blade.class_id]
        if cls.signature_weapon != blade.id:
            problems.append(f"{tag}: classes.py names {cls.signature_weapon!r} "
                            f"as this class's signature weapon")
        if len(blade.history) != 4:
            problems.append(f"{tag}: history has {len(blade.history)} lines, "
                            f"not 4")
        if any(not str(line).strip() for line in blade.history):
            problems.append(f"{tag}: a history line is empty")
        if not blade.flavour.strip():
            problems.append(f"{tag}: no inscription")
        for text in (blade.flavour, blade.argument, blade.technique_blurb,
                     *blade.history):
            if "!" in text:
                problems.append(f"{tag}: exclamation mark")
        if blade.hero_key not in items.HERO_WEAPON_KEYS:
            problems.append(f"{tag}: hero key {blade.hero_key!r} is not in "
                            f"items.HERO_WEAPON_KEYS")
        if blade.shape not in WEAPON_SHAPES:
            problems.append(f"{tag}: shape {blade.shape!r} is not legal in the "
                            f"weapon slot")
        if len(blade.rungs) != MAX_TIER:
            problems.append(f"{tag}: {len(blade.rungs)} rungs, not {MAX_TIER}")

        for slot in COST_SLOTS:
            mid = blade.metals.get(slot, "")
            if mid not in METAL_BY_ID:
                problems.append(f"{tag}: cost slot {slot} has no metal")
                continue
            if METAL_BY_ID[mid].rung != SLOT_RUNG[slot]:
                problems.append(f"{tag}: slot {slot} wants a rung "
                                f"{SLOT_RUNG[slot]} metal, got {mid} at rung "
                                f"{METAL_BY_ID[mid].rung}")
        if len(set(blade.metals.values())) != len(COST_SLOTS):
            problems.append(f"{tag}: two cost slots share a metal, which makes "
                            f"one rung of the ladder invisible")

        # ---- D: the rungs -----------------------------------------------
        previous = None
        for r in blade.rungs:
            rtag = f"{blade.id} rung {r.tier}"
            if r.id in ids:
                problems.append(f"{rtag}: duplicate id {r.id!r}")
            ids.add(r.id)
            if r.id in items.BY_ID:
                problems.append(f"{rtag}: id {r.id!r} collides with the "
                                f"items.py catalogue")
            if r.rarity != RARITY_BY_RUNG[r.tier]:
                problems.append(f"{rtag}: rarity {r.rarity} is off the ladder")
            if r.rarity not in items.RARITIES:
                problems.append(f"{rtag}: rarity {r.rarity} is not a rarity")
            problems.extend(_effect_problems(rtag, r.effects))

            if r.tier == MIN_TIER:
                if r.cost or r.gold:
                    problems.append(f"{rtag}: rung one is issued, not bought")
            else:
                if not r.cost:
                    problems.append(f"{rtag}: costs no metal")
                if not r.gold:
                    problems.append(f"{rtag}: costs no labour")
                for mid in r.cost:
                    if mid not in METAL_BY_ID:
                        problems.append(f"{rtag}: unknown metal {mid!r}")

            # nothing gets worse
            if previous is not None:
                for key, value in previous.effects.items():
                    if r.effects.get(key, 0) < value:
                        problems.append(f"{rtag}: {key} fell from {value} to "
                                        f"{r.effects.get(key, 0)}")
                if items.RARITY_ORDER.index(r.rarity) < \
                        items.RARITY_ORDER.index(previous.rarity):
                    problems.append(f"{rtag}: rarity went backwards")
                if r.hero["rung"] < previous.hero["rung"]:
                    problems.append(f"{rtag}: the sprite got worse")
                if r.cost and previous.cost and \
                        encounters_for(r.cost) < encounters_for(previous.cost):
                    problems.append(f"{rtag}: cheaper than the rung below it")

            # art
            if r.art["shape"] not in WEAPON_SHAPES:
                problems.append(f"{rtag}: shape {r.art['shape']!r} is illegal "
                                f"for the weapon slot")
            if r.art["material"] not in LOOTART_MATERIALS:
                problems.append(f"{rtag}: material {r.art['material']!r} is not "
                                f"a lootart material")
            if r.art["motif"] not in ART_MOTIFS and r.art["motif"] != "none":
                problems.append(f"{rtag}: motif {r.art['motif']!r} is not in "
                                f"ART_MOTIFS")
            if r.art["aura"] not in ART_AURAS and r.art["aura"] != "none":
                problems.append(f"{rtag}: aura {r.art['aura']!r} is not in "
                                f"ART_AURAS")
            if r.hero["rung"] != RUNG_TO_HERO[r.tier]:
                problems.append(f"{rtag}: hero rung disagrees with RUNG_TO_HERO")
            if r.hero["half"] != (1 if RUNG_TO_HERO.get(r.tier - 1)
                                  == RUNG_TO_HERO[r.tier] else 0):
                problems.append(f"{rtag}: hero half step disagrees with "
                                f"RUNG_TO_HERO")
            if not r.look.strip():
                problems.append(f"{rtag}: nothing changed on the sprite")

            # ---- E: the technique supplies nothing ----------------------
            low = r.technique_text.lower()
            for phrase in FORBIDDEN_IN_TECHNIQUE:
                if phrase in low:
                    problems.append(f"{rtag}: technique text contains "
                                    f"{phrase!r}")
            if not r.technique_rank.startswith(blade.technique):
                problems.append(f"{rtag}: rank {r.technique_rank!r} is not a "
                                f"rank of {blade.technique!r}")
            if "!" in r.technique_text or "!" in r.look:
                problems.append(f"{rtag}: exclamation mark")

            previous = r

        # ---- F: the promise classes.py made is kept at rung six ----------
        promised = next((g for g in classes.GEAR_REQUESTS
                         if g.id == blade.id), None)
        if promised is None:
            problems.append(f"{tag}: classes.GEAR_REQUESTS has no entry")
        else:
            six = blade.rung(6)
            if six.id != promised.id:
                problems.append(f"{tag}: rung six is {six.id!r}, not "
                                f"{promised.id!r}")
            if six.name != promised.name:
                problems.append(f"{tag}: rung six is named {six.name!r}, not "
                                f"{promised.name!r}")
            if six.rarity != promised.rarity:
                problems.append(f"{tag}: rung six is {six.rarity}, not "
                                f"{promised.rarity}")
            for key, value in promised.effects.items():
                if six.effects.get(key, 0) < value:
                    problems.append(
                        f"{tag}: rung six gives {key}="
                        f"{six.effects.get(key, 0)}, and classes.py promised "
                        f"{value}")

    # ---- G: nothing dead-ends -------------------------------------------
    # Every rung's metals must be reachable, and a player who is short may
    # always substitute downward from SOMETHING, so the only unreachable rung
    # would be one demanding a metal above the top of the ladder.
    for blade in BLADES:
        for r in blade.rungs:
            for mid in r.cost:
                metal = METAL_BY_ID[mid]
                if not metal.regions:
                    problems.append(f"{blade.id} rung {r.tier}: {mid} has no "
                                    f"source")
                if metal.rung > max(METAL_RUNGS):
                    problems.append(f"{blade.id} rung {r.tier}: {mid} is above "
                                    f"the ladder")
    if substitution_cover(max(METAL_RUNGS), 1) <= 0:
        problems.append("substitution: the top metal covers nothing, so a "
                        "player who skipped a region can dead-end")

    # ---- H: mastery is untouched -----------------------------------------
    # The proof is structural: this module never imports skills, and the only
    # state it writes is its own.
    if "skillmod" in globals() or "skills" in globals():
        problems.append("isolation: this module has reached for skill state")

    # ---- I: exactly one isolation path ------------------------------------
    if FORGE_CAPABILITY not in finalexam.ALL_CRUTCHES:
        problems.append(f"isolation: {FORGE_CAPABILITY!r} is not a real "
                        f"finalexam capability")


    # ---- J: affinity and the temper (SECTION 2b / 2c) --------------------
    # A metal's element is derived from its regions, so the only way this can be
    # wrong is if a region's affinity moves or a metal changes regions. Both are
    # one-line edits in other files, which is exactly the kind of change that
    # needs a test with an opinion.
    for metal in METALS:
        chain = METAL_AFFINITY[metal.id]
        for element in chain:
            if element not in elements.ELEMENTS:
                problems.append(f"{metal.id}: affinity {element!r} is not an "
                                f"element")
            if element not in {elements.affinity_for(r) for r in metal.regions}:
                problems.append(f"{metal.id}: claims {element} and no region it "
                                f"drops in has it")
        if len(chain) != len(set(chain)):
            problems.append(f"{metal.id}: the same element twice")
        if len(chain) > 2:
            problems.append(f"{metal.id}: three elements in one bar is more "
                            f"than a player can hold in their head")

    # Every element has a source, or the region it belongs to is unanswerable.
    for element in elements.ELEMENT_IDS:
        if not metals_for_element(element):
            problems.append(f"temper: nothing in the ground carries {element}, "
                            f"so no weapon can ever be made to counter it")

    # The temper invents no effect key and exceeds no cap elements.py declares.
    for step, resist in enumerate(TEMPER_STEP_RESIST, start=1):
        if resist > elements.PIECE_RESIST_CAP + 1e-9:
            problems.append(f"temper: step {step} is {resist}, over "
                            f"elements.PIECE_RESIST_CAP")
        if step not in TEMPER_UNITS or step not in TEMPER_GOLD:
            problems.append(f"temper: step {step} has no price")
    for element in elements.ELEMENT_IDS:
        key = f"resist_{element.lower()}"
        if key not in items.EFFECT_LABELS:
            problems.append(f"temper: {key} is not in items.EFFECT_LABELS")
    if sorted(TEMPER_STEP_RESIST) != list(TEMPER_STEP_RESIST):
        problems.append("temper: the steps are not in ascending order")
    previous_units = 0
    for step in sorted(TEMPER_UNITS):
        if TEMPER_UNITS[step] <= previous_units:
            problems.append(f"temper: step {step} is not dearer than the step "
                            f"below it")
        previous_units = TEMPER_UNITS[step]

    # A full warded loadout still cannot pass elements.RESIST_CAP, because
    # elements.armour_from_effects clamps and this file does not.
    _probe = new_state()
    _probe["metals"] = {m.id: 999 for m in METALS}
    _worn = {}
    for slot in ("chest", "head", "offhand", "hands", "feet", "ring1", "ring2",
                 "trinket"):
        item_id = f"probe_{slot}"
        _worn[slot] = item_id
        for _ in range(TEMPER_MAX_STEP):
            temper(_probe, item_id, slot=slot, metal_id="faultsteel",
                   gold=10 ** 6)
    _bag = loadout_temper_effects(_probe, _worn)
    if _bag.get("resist_fire", 0) <= elements.RESIST_CAP:
        problems.append("temper: eight capped pieces did not even reach the "
                        "loadout cap, so the cap is not doing anything")
    _profile = elements.armour_from_effects(_bag)
    if _profile.resist_to(elements.FIRE) > elements.RESIST_CAP + 1e-9:
        problems.append("temper: a full warded loadout passed "
                        "elements.RESIST_CAP")
    if elements.resolve_damage(
            20, elements.FIRE,
            elements.Defender(element=elements.COLD, armour=_profile)
    ).damage < elements.MIN_DAMAGE:
        problems.append("temper: a fully warded player can be hit for nothing, "
                        "which would make an area unwinnable from the other "
                        "side")

    # A temper is all-or-nothing, and a refusal takes nothing. The one bug this
    # feature cannot ship with is the one `upgrade` already had.
    _poor = new_state()
    _poor["metals"] = {"faultsteel": 1}
    _before = dict(_poor["metals"])
    if not temper(_poor, "x", slot="weapon", metal_id="faultsteel",
                  gold=0).get("error"):
        problems.append("temper: an unpayable temper was allowed")
    if _poor["metals"] != _before or _poor.get(TEMPER_KEY):
        problems.append("temper: a refused temper still took the metal")

    return problems


def self_check() -> dict:
    """What `validate()` proved, for a test to print rather than paraphrase."""
    problems = validate()
    est = grind_estimate()
    return {
        "problems": problems,
        "ok": not problems,
        "blades": len(BLADES),
        "rungs": sum(len(b.rungs) for b in BLADES),
        "metals": len(METALS),
        "metals_with_affinity": len([m for m in METALS if METAL_AFFINITY[m.id]]),
        "dual_metals": sorted(m.id for m in METALS
                              if len(METAL_AFFINITY[m.id]) > 1),
        "inert_metals": list(INERT_METALS),
        "metal_affinity": {k: list(v) for k, v in sorted(METAL_AFFINITY.items())},
        "metals_by_element": {k: list(v)
                              for k, v in sorted(METALS_BY_ELEMENT.items())},
        "every_element_has_a_metal":
            all(metals_for_element(e) for e in elements.ELEMENT_IDS),
        "temper_steps": list(TEMPER_STEP_RESIST),
        "temper_units": dict(TEMPER_UNITS),
        "temper_gold": dict(TEMPER_GOLD),
        "weapon_temper": {"units": WEAPON_TEMPER_UNITS,
                          "gold": WEAPON_TEMPER_GOLD},
        "temper_encounters": {
            "weapon_fire": int(math.ceil(WEAPON_TEMPER_UNITS
                                         / best_yield("faultsteel"))),
            "armour_piece_to_cap": int(math.ceil(
                sum(TEMPER_UNITS.values()) / best_yield("faultsteel"))),
        },
        "regions_with_metal": len(REGION_METAL),
        "regions_total": len(world.REGIONS),
        "new_effect_keys": 0,
        "effect_keys_used": len(FORGE_EFFECT_KEYS),
        "encounters_min": est["spread"]["min"],
        "encounters_max": est["spread"]["max"],
        "encounters_mean": est["spread"]["mean"],
    }


def stats() -> dict:
    est = grind_estimate()
    return {
        "blades": len(BLADES),
        "rungs_per_blade": MAX_TIER,
        "rungs_total": sum(len(b.rungs) for b in BLADES),
        "metals": len(METALS),
        "metal_rungs": len(METAL_RUNGS),
        "regions_with_metal": len(REGION_METAL),
        "new_effect_keys": 0,
        "new_motifs": len(NEW_ART_MOTIFS),
        "new_auras": len(NEW_ART_AURAS),
        "techniques": len(BLADES),
        "technique_ranks": MAX_TIER * len(BLADES),
        "found_weapon_rivals": len([i for i in items.CATALOGUE
                                    if i.slot == "weapon"]),
        "encounters_to_rung_nine": est["spread"],
    }


# ==========================================================================
# SECTION 13 — THE ART CONTRACT
# ==========================================================================

ART_BRIEF = """
FOR WHOEVER IS DRAWING THIS.

Everything below is already in the data. Nothing here needs a decision from you
about balance, cost or wording; it needs pixels.

1. WHAT EXISTS ALREADY AND MUST NOT MOVE
   web/js/sprites.js HERO_WEAPON_ANCHOR stays exactly where it is. Every rung of
   every blade is the same twelve-row weapon box at the same anchor; what changes
   is the grid and two colours. lootart.js mirrors that anchor for its overlays
   and moving it detaches all of them.

2. THE HERO SPRITE — THE DATA PLUGS IN, AND THE LADDER NOW MOVES
   forge.hero_weapon_look(blade_id, tier) returns the `_weapon` dict sprites.js
   reads:
       {key, rung, half, line, silhouette, name, look, metal, trim}
   `weaponRung()` honours a finite `rung` before it falls back to matching the
   name. `scripts/verify/forgehero.mjs --strict` drives all 54 rungs through
   heroFrame at four facings: 216 frames, no nulls, every key legal, the anchor
   untouched, worst frame 14 colours of a 15 budget.

   THE THREE ASKS BELOW HAVE ALL LANDED. The numbers are re-measured rather than
   re-asserted; run forgehero.mjs --strict and it prints them.

     a) EVERY RUNG IS DRAWN. HERO_WEAPON_LADDER carries six grids per family
        over ten families, plus twelve more for the two lines that would
        otherwise arrive as somebody else's tool — the Chain is not the Calipers
        and the Spanner is not the Maul, and at sixteen pixels that is the
        cheapest legibility there is. Every grid is authored to its `look`
        sentence, inside the `silhouette` band this file grades, and every one
        moves the alpha mask of the rung below it. massBlade() — one derived
        pixel of mass on whichever row was widest — is gone: it bought one or
        two outline changes in the same place on every family at once, and next
        to a drawn rung it only fights the drawing.

     b) RUNEWORK REACHES ALL TEN SHAPES. It used to reach four. runeBlade()
        bailed out on any grid without three rows of 'M', which was six of the
        ten families — dagger 2, axe 2, spear 2, bow 1, staff 0, relic 0 — so
        the Calipers, the Chain, the First Draft and the Tracing Needle were
        colour-only from rung one to rung nine. It now falls through the
        interior vocabulary ('M', then 'm', 'w', 'g') until it finds a body to
        etch, borrows the next colour up when the body IS the trim, and steps
        from every other row to every row at the Mythic rung, because this
        palette resolves 'M' and 'w' to one value and a second etch COLOUR would
        have been a switch in name only.

     c) THE HALF STEP. RUNG_TO_HERO puts nine tiers on six rungs, so tiers 3, 5
        and 7 land on a rung their predecessor already drew. Measured, they used
        to differ from it in TRIM AND NOTHING ELSE: eighteen colour-only steps
        across the six blades, three grinds per blade a player could finish
        without seeing one pixel change. `hero["half"]` now says which tier that
        is, and HALF_STEP in sprites.js adds the single detail that tier's own
        `look` promises — a ferrule, a brace, a pin, a band, a second course on
        a jaw — inside the columns the rung already occupies, because every rung
        is drawn to the edge of its band and a half step is a detail rather than
        a promotion. All 48 tier-to-tier steps now move the outline.

   WHAT THIS SECTION STILL CONSTRAINS, for whoever draws the next rung:
     1. `silhouette` on each rung is narrow | standard | broad and it is the one
        thing the grids cannot derive: the Needle is still narrow at rung nine
        and the Maul is already broad at rung one. It is the maximum COLUMN SPAN
        the weapon may occupy in its six-wide box. A line that gets wider every
        rung arrives at rung nine as a rectangle.
     2. No rung and no half step brings a colour of its own. They are drawn in
        the ramp the armour already uses — 'A' shadow, 'm' mid, 'M' light, 'w'
        specular, 'g' the trim the rarity tier colours, 'u' the grip — so the
        fifteen-colour budget is paid for before the ladder starts.

   `key` is one of items.HERO_WEAPON_KEYS: relic, axe, relic, hammer, hammer,
   dagger for the six lines in order — four distinct silhouettes for six blades.
   The Calipers and the Chain share the `relic` grid today and they should not;
   so do the Maul and the Spanner on `hammer`. Six distinct hand poses is the
   cheapest legibility win available here.

   Acceptance test: `node scripts/verify/forgehero.mjs --strict`. It passes
   today on the forge side and fails on (a) and (b); it goes green when the art
   pass lands, and it is the only file that has to change to prove that.

3. THE INVENTORY / LOOT SPRITE — lootart.js
   forge.art_at(blade_id, tier) returns:
       {shape, material, accent, motif, aura, silhouette, frames}
   `shape` is a shape lootart already has and is legal in the weapon slot.
   `material` is one of lootart's MATERIAL keys. `accent` is one hot rim colour,
   given per rung so nine rungs do not become one object in nine golds.

   `motif` and `aura` are the two passes legendaries.py already requested.
   forge.ART_MOTIFS and forge.ART_AURAS are the MERGED tables — legendaries'
   twelve motifs and six auras plus six and six more from here. Implement the
   merged tables once:
       applyRarity(): a motif pass between ornament() and applyRim()
       an aura pass drawn outside the silhouette, after animate()
   Six new motifs: caliper_jaw, rule_marks, quench_line, forge_mark, link,
   hairline. Six new auras: quenchsteam, heatglow, measure, tallylight,
   roadglow, unlabelled.

   `silhouette` is narrow | standard | broad and is a hint for the grow stage:
   the Needle should stay narrow at rung nine and the Maul should be broad at
   rung one, because a weapon that gets wider with every upgrade ends up as a
   rectangle.

   `frames` is 0 for "use the rarity's frame count" and 1 for a pinned single
   frame. Nothing in this file pins one, but legendaries asked for the override
   and this honours the same field.

4. THE COLOUR BUDGET
   Fifteen per sprite, unchanged. A rung contributes exactly two colours to the
   hero: `metal` and `trim`. `metal` is items.ARMOR_TIERS["weapon"] at the hero
   rung, blended 25% toward the blade's own tint, so six lines are
   distinguishable without six ramps. Check with lootart.paletteBudget().

5. THE ONE THING WORTH EXTRA EFFORT
   Rung 9 of every blade sets aura "unlabelled": the aura draws, and then the row
   of pixels that would carry a maker's mark is left empty. That is the Null
   King's metal doing what the Null King's metal does, it is the same idea as
   the castle stripping the pattern label off a problem, and on a shelf of
   animated legendaries a deliberate absence is the loudest thing there.

6. THE SMITH
   Vess uses sprite key `smith`, which sprites.js already draws for the
   Testsmith. No new NPC art is required. If you want her distinct, she is older,
   she is not looking at you, and she is holding something up to the light.
"""


# ==========================================================================
# SECTION 14 — THE WIRING CONTRACT
# ==========================================================================

WIRING = """
FOR WHOEVER IS WIRING THIS.

Nine call sites. None of them is in a hot loop and none of them needs new
instrumentation.

1. THE EFFECT VOCABULARY — NOTHING TO DO
   forge adds zero keys to items.EFFECT_LABELS. Every rung's effects render
   through items.describe() today. If forge.validate() passes, the tooltip path
   is already correct.

   One request, and it is one line. forge.SWITCH_KEYS lists the eight keys this
   file uses that are capabilities rather than amounts — two sources of one do
   not make it twice as true, so they take max() rather than sum(). Seven of the
   eight are already in items.SWITCH_KEYS. The eighth is:

       items.SWITCH_KEYS |= {"spell_refund"}

   "a learning spell's focus is refunded in full if you then clear that problem
   unaided" is true or it is not; it does not refund twice. forge.SWITCH_REQUESTS
   is that list and forge.validate() fails if it stops matching items.py — in
   either direction, so granting the request means deleting the line.

2. STATE
   engine.DEFAULT_STATE["forge"] = forge.new_state()
   It persists. A bag of metal that resets on load makes the ladder infinite.

3. THE CATALOGUE
   Fifty-four rungs want to exist as items. forge.item_kwargs(blade_id, tier)
   returns exactly what items._i() takes, including `upgrades` pointing at the
   next rung's id, so the whole ladder can be adopted with one loop:

       for blade in forge.BLADES:
           for tier in range(1, forge.MAX_TIER + 1):
               items._i(**forge.item_kwargs(blade.id, tier))

   They are class-restricted. classes.CLASS_RESTRICTED covers only the six ids
   classes.GEAR_REQUESTS declared — which are rung SIX of each line. Merge
   forge.FORGE_RESTRICTED into it or a Berserker will be able to equip the
   Analyst's rung-seven Calipers, which is the kind of bug nobody reports and
   everybody exploits.

4. THE DROP
   After an encounter resolves, once:
       got = forge.roll_metal(region_id=..., difficulty=..., rank=result["rank"],
                              luck=eff.get("loot_luck", 0.0),
                              is_boss=enc.is_boss, encounter=enc)
       if got: forge.add_metal(G.state["forge"], got["metal"], got["units"])
   roll_metal returns None in town, in a sealed run, and on a miss, so it is safe
   to call unconditionally. It takes the encounter and asks forge.active() — do
   not add a mode test at the call site.

5. THE SEAL
   forge.active(encounter) is the only isolation question in this module. It is
   finalexam.sealed(enc, "BUILD") and nothing else. When the Editor Automaton
   takes BUILD at rung eight of the boss ladder, the blade's numbers go with it;
   that is correct and must not be special-cased. forge.refusal() returns the
   standard refusal payload.

6. THE SMITH SCREEN
   forge.smith_view(state["forge"], blade_id, gold=player["gold"],
                    class_id=state["class"]["class"])
   returns the quote, the shortfall, Vess's lines, the technique ladder, the
   swap comparison and the bag. forge.route_ahead() is the "show me the whole
   road" panel. Draw her at python_village; she is not a mentor and must not be
   added to world.MENTORS, because mentors are a sealed capability and a
   blacksmith is not.

7. THE UPGRADE
       result = forge.upgrade(state["forge"], blade_id, gold=player["gold"])
       if not result.get("error"):
           player["gold"] -= result["gold_spent"]
   forge.upgrade does NOT touch the purse. It reports what to deduct. Two owners
   of one number is how a purse goes negative.

   It DOES own the metal, and it is all-or-nothing: the whole spend is worked
   out and checked against the bag before a single bar leaves it, so a result
   carrying an `error` has changed nothing and a result without one has moved
   exactly one rung. Do not re-check the bag at the call site and do not try to
   refund anything on a refusal — there is nothing to refund, and a caller that
   thinks otherwise is the second owner of the number again.

8. THE SPRITE
   items.hero_look() reads equipped["weapon"] out of the catalogue and derives
   the ramp from rarity. Once the rungs are in the catalogue that works
   unchanged, and sprites.js needs no edit to RENDER a forged blade — see
   ART_BRIEF §2 for what it does need to make the ladder visible, which is a
   separate job from this one. To use the blade's own tint, override after the
   call:
       look = items.hero_look(armor, equipped)
       if equipped.get("weapon") in forge.RUNG_BY_ID:
           blade, rung = forge.RUNG_BY_ID[equipped["weapon"]]
           look["_weapon"] = forge.hero_weapon_look(blade.id, rung.tier)
           look["metal"] = look["_weapon"]["metal"]
   sprites.js needs no change either way; weaponRung() already honours `rung`.

9. MASTERY
   Nothing. This module never reads or writes skills state and must not be given
   a reason to. A metal is loot. If a future quest wants to pay mastery for
   forging, that quest pays it through skills.apply_outcome on graded evidence,
   and the forge is not part of the transaction.

11. THE TEMPER — SECTION 2b / 2c, AND THE ONE NEW STATE KEY
    engine.DEFAULT_STATE["forge"] already persists. `new_state()` now also
    carries forge.TEMPER_KEY ("temper"), keyed by ITEM id. Every reader goes
    through forge.temper_of(), which tolerates its absence, so an existing save
    loads with everything untempered.

    The bench:
        forge.temper_view(state["forge"], equipped=player["equipped"],
                          gold=player["gold"])
        q = forge.temper_quote(state["forge"], item_id, slot=item.slot,
                               metal_id=..., element=..., gold=player["gold"])
        r = forge.temper(state["forge"], item_id, slot=item.slot,
                         metal_id=..., element=..., gold=player["gold"])
        if not r.get("error"):
            player["gold"] -= r["gold_spent"]
    Same contract as `upgrade`: the metal is taken here, the purse is not, and a
    result carrying an `error` has changed nothing.

12. WHAT A TEMPER CHANGES, AND WHERE THE TWO NUMBERS GO
    ARMOUR. Fold the resist keys into the effect bag engine.Game.effects
    already builds, next to the equipped items' own effects:

        fx.update_with(forge.loadout_temper_effects(state["forge"],
                                                    player["equipped"]))

    They are `resist_<element>` keys, they are already in items.EFFECT_LABELS,
    and elements.armour_from_effects() already reads them and clamps the total
    at elements.RESIST_CAP. Do NOT clamp at the call site; there is one clamp.

    WEAPON. A weapon's element is not an effect and must not go in the bag.
    Read it where the swing is resolved:

        atk = forge.tempered_element(state["forge"],
                                     player["equipped"].get("weapon", ""))
        result = elements.resolve_damage(base, atk, defender, ...)

    An untempered weapon returns "", which elements.matchup already treats as
    neutral. Nothing needs a fallback.

13. TESTS
    assert forge.validate() == []
    That call proves, among other things: every effect key resolves inside
    items.EFFECT_LABELS and no new one was invented; no rung exceeds 60% of any
    classes.CAPS ceiling; every region except the town drops exactly one metal;
    every metal is asked for by at least one blade; no rung is cheaper or weaker
    than the rung below it; rung six of every blade delivers everything
    classes.GEAR_REQUESTS promised, by id, name, rarity and effect; and no rank
    of any technique contains the vocabulary of giving something away.
"""
