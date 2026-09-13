"""THE SHELF — the counter inside a village building, and THE RACK on its wall.

WHAT THIS MODULE IS FOR, AND THE THREE THINGS IT REFUSES TO DO
--------------------------------------------------------------
The brief asked for "randomized armor stats with rare stats being low and same
with swords for gold as well as level specific potions". Two of those three
already shipped and shipping them again would be the bug, not the feature:

  POTIONS BY LEVEL BAND are `economy.stock_list(region)` ->
  `potions.available_at(economy.area_band(region))`, priced by
  `economy.potion_price`, stocked by `economy.VENDOR_STOCK` and refilled by
  `economy.restock`. This module renders that counter. It does not re-decide a
  single number on it. `counter()` calls `economy.vendor_view` and hands the
  result straight through.

  SWORDS FOR GOLD are `forge.GOLD_SHAPE`: a nine-rung ladder from 40 gold to
  1500, wired into `forge.RARITY_BY_RUNG`, `forge.RUNG_TO_HERO`, the temper
  system and `hunters.RUNG_CREDIT`. A second sword curve would desynchronise
  all five in one commit. What this module adds is one BLANK — the same blade,
  at the same rung, at that rung's own price plus a premium for the metal you
  did not walk out and find. See `blank()`.

  THE THIRD THING, the one that is actually new, is THE RACK: eight slots of
  generated armour on the east wall, rolled on the drops' own rarity weights,
  priced by `economy.rack_price`, and turned over only by cleared encounters.

THE ECONOMY HAS BEEN BROKEN BY FARMING TWICE IN THIS PROJECT — a cleared
dungeon room that kept paying, and a beaten boss that kept paying. Both were
the same bug: a reward whose input was an action the player could repeat for
free. So the rack's stock is a PURE FUNCTION of three values, none of which a
player can move without writing Python:

    (save_seed, region_id, economy.rack_index(state, region_id))

Walking out of the building, out of the region, quitting to the title screen,
reloading the save, or reopening the panel does not appear in that tuple. The
rack cannot be rerolled. It is not that rerolling is discouraged; there is no
input to reroll. `restock_index` moves on `economy.restock()` alone, which is
credited per CLEARED encounter, six to a step, and pays nothing for a failure.

THE CEILING, WHICH IS THE RULE THAT KEEPS THE RACK HONEST
---------------------------------------------------------
A generated item may never beat an authored one of the same rarity. Bosses drop
authored items, and a boss drop has to stay the best thing that happened to you
today. So `CEILINGS` is not a table anybody typed: it is MEASURED at import off
the whole authored surface — every `items.CATALOGUE` piece of that rarity or
below, plus every piece `items.armour_effects()` is willing to mint at that
rarity — and every rolled magnitude and every roll's total budget is clamped
against it. `validate()` re-derives it and fails the import if the clamp ever
lets something through.

That measurement found two places where the design document's own tables broke
the document's own rule, and both are fixed here rather than in the doc:

  * BASE[COMMON] = 2 budget points, against an authored COMMON surface worth
    9.70 — fine. But BASE[LEGENDARY] = 16 grows to 25 at depth 7, against an
    authored LEGENDARY surface worth 18.70. `_budget()` therefore clamps to the
    measured ceiling: LEGENDARY stops growing at depth 2 and EPIC at depth 4,
    and the whole 34%-over-the-bar LEGENDARY roll the document's table would
    have shipped at depth 7 never exists.
  * `stamina_regen` is on the design's allowlist and is carried by NO authored
    item anywhere in the game, at any rarity. A key with no authored precedent
    cannot be bounded by a measurement of authored precedent. It is kept, bound
    to its declared twin `mana_regen` through `TWIN`, and the substitution is
    named here rather than left to be discovered.

WHAT THIS MODULE NEVER TOUCHES
------------------------------
The purse (`state["player"]["gold"]`) — like `economy.py` and `forge.py`, this
reports `gold_spent` and lets `engine.py` do the arithmetic. The inventory —
`buy()` hands back an item and the engine files it. The blade tiers —
`state["forge"]["tiers"]` is forge.py's, so `buy_blank()` returns a `grant` for
the engine to apply and says so in the return value. Three owners, unchanged.
"""
from __future__ import annotations

import hashlib
import random

from . import economy, elements, forge, items, world


# ==========================================================================
# SECTION 1 — THE STREAM
# ==========================================================================
#
# One independent random stream per slot, keyed by name, exactly the way
# `worldgen._rng` does it and for exactly the same reason: drawing everything
# from one sequential Random would mean that adding a ninth slot next year
# reshuffled every existing slot, and a rack a player had walked away from
# would be a different rack when they came back.

def _rng(save_seed: int, region_id: str, index: int, label: str) -> random.Random:
    key = f"{int(save_seed) & 0xFFFFFFFF}:{region_id}:{int(index)}:{label}"
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


# ==========================================================================
# SECTION 2 — WHAT THE RACK CARRIES
# ==========================================================================

# Eight slots: `items.SLOTS` minus the weapon, because the weapon ladder is
# forge.py's and the rack is not allowed a second one. Derived rather than
# retyped, so a ninth armour slot appears here the day items.py grows one.
RACK_SLOTS: tuple = tuple(s for s in items.SLOTS if s != "weapon")

# THE ALLOWLIST. The same discipline `captives.BOON_EFFECTS_ALLOWED` uses: a
# rack item buys mitigation, bars and the two slow economies. It buys nothing
# that reads a problem, names a weakness, discounts a hint, grants a probe or
# stretches a clock, and `_no_rack_item_supplies_an_answer()` proves it at
# import against a NAMED refusal list rather than against the absence of an
# entry somebody could add without noticing what they were adding.
RACK_EFFECTS = frozenset({
    "armour_points", "armour_cap", "stamina_max", "stamina_regen",
    "mana_max", "mana_regen", "loot_luck", "xp_bonus",
    "resist_fire", "resist_cold", "resist_poison",
    "resist_lightning", "resist_void", "resist_brute",
})

RACK_EFFECTS_REFUSED = frozenset({
    "probe_charges", "probe_refund", "probe_reveal_value", "probe_unbounded",
    "probe_first_free", "reveal_category", "perf_insight", "weakness_scan",
    "weakness_chain", "hint_discount", "rank_grace", "recovery_grace",
    "srs_preview", "interval_stretch", "prereq_sight", "phase_preview",
    "boundary_sense", "off_map", "trace_frames", "no_clock", "oblige",
})

# `stamina_regen` is the one key on the allowlist that no authored item carries,
# so it has no measured ceiling of its own. Its twin does: `EFFECT_LABELS`
# spells the two identically bar the resource ("+{v} stamina after every cleared
# encounter" / "+{v} focus after every cleared encounter"). It borrows that
# bound. This is a judgement, and it is the only one in the ceiling table.
TWIN = {"stamina_regen": "mana_regen"}

# Which keys a slot is allowed to roll. Not in the design document; added here
# because a ring that grants plate points reads as a bug however carefully the
# number was chosen, and because a pool per slot is what makes eight rolls feel
# like eight different objects instead of one object drawn eight times.
_WARDS = ("resist_fire", "resist_cold", "resist_poison",
          "resist_lightning", "resist_void", "resist_brute")
SLOT_KEYS: dict = {
    "offhand": ("armour_points", "armour_cap") + _WARDS,
    "head":    ("armour_points", "armour_cap", "mana_max") + _WARDS,
    "chest":   ("armour_points", "armour_cap", "stamina_max") + _WARDS,
    "hands":   ("armour_points", "stamina_max", "stamina_regen") + _WARDS,
    "feet":    ("armour_points", "stamina_max", "stamina_regen") + _WARDS,
    "ring1":   ("mana_max", "mana_regen", "stamina_max", "stamina_regen",
                "loot_luck", "xp_bonus"),
    "ring2":   ("mana_max", "mana_regen", "stamina_max", "stamina_regen",
                "loot_luck", "xp_bonus"),
    "trinket": ("mana_max", "mana_regen", "loot_luck", "xp_bonus",
                "armour_cap") + _WARDS,
}

# RARE STATS ARE RARE BY RULE, NOT BY ROUNDING. The two keys that pay the
# player in loot and the one that pays them in XP are gated on rarity outright,
# so no amount of budget can put `xp_bonus` on a common cap. A COMMON rack item
# is a point of armour or a single bar. Every time.
MIN_RARITY = {"loot_luck": "RARE", "armour_cap": "RARE", "xp_bonus": "EPIC"}

# Integer keys round; fractional keys do not. Split explicitly, because
# `max(1, round(budget * share / 20.0))` on a resistance would hand out a 100%
# ward for three budget points, which is the kind of arithmetic that reads fine
# in a design document and ships a god item.
INT_KEYS = frozenset({"armour_points", "stamina_max", "mana_max",
                      "stamina_regen", "mana_regen"})

# Budget points per unit of effect. The design document's table, unchanged. It
# is internally coherent with the measured ceilings in a way worth noticing: a
# LEGENDARY roll of three lines at the measured budget ceiling lands EXACTLY on
# the authored per-key ceiling for every single key. That is not a coincidence
# — the table was priced against those numbers — but it is the check that says
# so out loud.
RACK_COST: dict = {
    "armour_points": 1.0,
    "stamina_max": 0.5, "mana_max": 0.5,
    "stamina_regen": 2.0, "mana_regen": 2.0,
    "armour_cap": 15.0, "loot_luck": 40.0, "xp_bonus": 30.0,
    **{w: 20.0 for w in _WARDS},
}

# What a roll of each rarity is worth before the region multiplier.
BASE_BUDGET = {"COMMON": 2, "UNCOMMON": 4, "RARE": 7, "EPIC": 11,
               "LEGENDARY": 16}
# 8% a rung of `economy.AREA_DEPTH`. Gentler than the 10% the price moves by,
# so a deep piece is dearer slightly faster than it is better, which is the
# direction that keeps a shallow region worth shopping in.
DEPTH_STEP = 0.08
LINES = {"COMMON": 1, "UNCOMMON": 1, "RARE": 2, "EPIC": 2, "LEGENDARY": 3}

# The rarities the rack may roll. MYTHIC is excluded twice over: its
# `items.RARITIES` weight is already zero, and it is named here so that a future
# edit to that weight cannot quietly put a mythic on a shop wall. Mythic is
# secret-only and the rack never sells one.
RACK_RARITIES: tuple = ("COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY")
RARITY_REFUSED: tuple = ("MYTHIC",)

# The depth clamp. A shallow region cannot sell a legendary and a deep one
# cannot sell junk, which is what stops a player walking back to the village to
# shop and what stops the Wastes wasting a slot.
DEPTH_BANDS = (
    (0, 2, "COMMON", "RARE"),
    (3, 5, "UNCOMMON", "EPIC"),
    (6, 99, "RARE", "LEGENDARY"),
)


def rarity_bounds(region_id: str) -> tuple:
    depth = economy.area_depth(region_id)
    for low, high, floor, ceiling in DEPTH_BANDS:
        if low <= depth <= high:
            return floor, ceiling
    return "COMMON", "RARE"


# ==========================================================================
# SECTION 3 — THE CEILING, MEASURED
# ==========================================================================

def _authored_surface() -> list:
    """Every authored effect bag in the game that the rack could be compared to.

    Two sources, because the authored world states its armour curve in two
    places. `items.CATALOGUE` is the written pieces; `items.armour_effects` is
    the FUNCTION items.py uses to mint armour from `_PLATE_POINTS`,
    `_WARD_RESIST` and `_BAR_BONUS`, and it is the only authority that says
    what a COMMON plate is worth — the catalogue happens to contain no common
    armour at all, so measuring the catalogue alone would leave
    `armour_points` with no COMMON bound and the rack unable to offer the one
    thing a common rack item is supposed to be.

    `source == "upgrade"` is excluded for the reason `items.roll_drop` excludes
    it: earned forms are never found, so they are not the bar a shop is held to.
    MYTHIC is excluded because the rack never rolls one.
    """
    out = []
    for it in items.CATALOGUE:
        if it.rarity not in RACK_RARITIES or it.source == "upgrade":
            continue
        out.append((it.rarity, dict(it.effects)))
    kinds = ("PLATE", "MAIL", "WARDED", "CLOAK")
    wards = ("", "FIRE", "COLD", "POISON", "LIGHTNING", "VOID", "BRUTE")
    for rarity in RACK_RARITIES:
        for kind in kinds:
            for element in wards:
                out.append((rarity, items.armour_effects(kind, rarity, element)))
    return out


def _measure_ceilings() -> tuple:
    """Per-key and per-roll ceilings, cumulative up the rarity ladder.

    CUMULATIVE, so the bound at EPIC is the best authored thing at EPIC *or
    below*. Without that, `resist_void` — which no authored EPIC piece carries
    — would have no EPIC bound at all, and a hole in a ceiling is not a
    ceiling. It also makes the table monotone, so a generated LEGENDARY can
    never be bounded below a generated EPIC.
    """
    per_key: dict = {}
    per_roll: dict = {}
    running: dict = {}
    best_total = 0.0
    surface = _authored_surface()
    for rarity in RACK_RARITIES:
        for r, effects in surface:
            if r != rarity:
                continue
            total = 0.0
            for key, value in effects.items():
                if key not in RACK_EFFECTS:
                    continue
                running[key] = max(running.get(key, 0.0), float(value))
                total += float(value) * RACK_COST[key]
            best_total = max(best_total, total)
        per_key[rarity] = dict(running)
        per_roll[rarity] = round(best_total, 2)
    # The twin, and the two hard caps the damage function will enforce anyway.
    # Reading them from elements.py rather than typing 0.30 means a rack item
    # can never be authored past a number `elements.resolve_damage` is going to
    # ignore, which is the same argument `items.armour_effects` makes.
    for rarity in RACK_RARITIES:
        table = per_key[rarity]
        for key, twin in TWIN.items():
            if key not in table and twin in table:
                table[key] = table[twin]
        for ward in _WARDS:
            if ward in table:
                table[ward] = min(table[ward], elements.PIECE_RESIST_CAP)
        if "armour_cap" in table:
            table["armour_cap"] = min(table["armour_cap"],
                                      elements.ARMOUR_POINT_CAP)
    return per_key, per_roll


CEILINGS, ROLL_CEILING = _measure_ceilings()


def _budget(rarity: str, region_id: str) -> int:
    """`BASE * (1 + 0.08 * depth)`, clamped by what the authored world carries.

    The clamp is the whole of the import-time ceiling check, expressed as
    arithmetic instead of as an assertion: a roll cannot be worth more budget
    points than the richest authored piece of its rarity, so it cannot convert
    more budget points into effect, so it cannot beat one. LEGENDARY stops
    growing at depth 2 (18 points against an authored 18.70) and EPIC at depth
    4 (15 against 15.50), because that is where each one reaches the bar.
    """
    base = BASE_BUDGET.get(rarity, 0)
    if not base:
        return 0
    grown = round(base * (1.0 + DEPTH_STEP * economy.area_depth(region_id)))
    return int(min(grown, int(ROLL_CEILING.get(rarity, grown))))


# ==========================================================================
# SECTION 4 — THE ROLL
# ==========================================================================

def _roll_rarity(rng: random.Random, region_id: str) -> str:
    """items.RARITIES' own weights, then the region's clamp.

    The weights are READ, never copied, so the rack can never be richer than
    the drops. Raising a roll to the floor and lowering it to the ceiling —
    rather than rejecting and redrawing — is what makes the arithmetic
    stateable: at depth 0-2, P(RARE) is the raw P(RARE or better).
    """
    pool = [(r, items.RARITIES[r]["weight"]) for r in RACK_RARITIES]
    total = sum(w for _, w in pool)
    pick = rng.random() * total
    rolled = pool[0][0]
    for rarity, weight in pool:
        pick -= weight
        if pick <= 0:
            rolled = rarity
            break
    floor, ceiling = rarity_bounds(region_id)
    i = RACK_RARITIES.index(rolled)
    return RACK_RARITIES[min(max(i, RACK_RARITIES.index(floor)),
                             RACK_RARITIES.index(ceiling))]


def _keys_for(slot: str, rarity: str) -> list:
    """The pool this slot may draw from at this rarity, after every gate.

    Three filters, in order: the slot's own pool, the rarity lock on the three
    rare stats, and the ceiling — a key with no authored precedent at or below
    this rarity is not offered at all, because there is nothing to bound it
    against and an unbounded key is how a shop out-drops a boss.
    """
    table = CEILINGS.get(rarity, {})
    out = []
    for key in SLOT_KEYS.get(slot, ()):
        need = MIN_RARITY.get(key)
        if need and RACK_RARITIES.index(rarity) < RACK_RARITIES.index(need):
            continue
        cap = table.get(key)
        if cap is None or cap <= 0:
            continue
        if key in INT_KEYS and cap < 1:
            continue
        out.append(key)
    return out


def _magnitudes(rng: random.Random, slot: str, rarity: str,
                budget: int) -> tuple:
    """Turn budget points into effect, one line at a time.

    Budget is handed out as `remaining / lines_left`, so a line clamped by the
    ceiling passes what it could not spend to the line after it rather than
    burning it. That matters: at RARE and above the per-key ceilings bite
    often, and without the carry-over the second line of a two-line roll would
    be as thin as the first was blocked.
    """
    pool = _keys_for(slot, rarity)
    if not pool:
        return {}, 0.0
    want = min(LINES.get(rarity, 1), len(pool))
    chosen = rng.sample(pool, want)
    table = CEILINGS.get(rarity, {})
    effects: dict = {}
    remaining = float(budget)
    spent_total = 0.0
    for n, key in enumerate(chosen):
        left = want - n
        share = remaining / left if left else remaining
        cap = float(table[key])
        cost = RACK_COST[key]
        if key in INT_KEYS:
            value = max(1, int(round(share / cost)))
            value = int(min(value, int(cap)))
            if value < 1:
                continue
        else:
            value = round(min(share / cost, cap), 2)
            if value < 0.01:
                continue
        effects[key] = value
        spend = value * cost
        spent_total += spend
        remaining = max(0.0, remaining - spend)
    return effects, round(spent_total, 3)


# -- names -----------------------------------------------------------------
#
# Procedural, like everything else drawn in this game. The maker's mark is the
# region's own metal, read from `forge.REGION_METAL`, so a piece says where it
# was made without a single line of per-region text; the noun climbs with
# rarity; and the mark in front of it is the smith's, because a smith signs
# only the piece she would want found.

_NOUNS = {
    "offhand": ("Buckler", "Targe", "Pavise"),
    "head":    ("Cap", "Coif", "Helm"),
    "chest":   ("Jerkin", "Hauberk", "Cuirass"),
    "hands":   ("Mitts", "Bracers", "Gauntlets"),
    "feet":    ("Shoes", "Boots", "Sabatons"),
    # The two ring slots get two different nouns on purpose. They share a
    # key pool, so without this a wall could carry "Homespun Band" twice with
    # different effects inside, which reads as a bug in the shop rather than as
    # two rings.
    "ring1":   ("Band", "Ring", "Signet"),
    "ring2":   ("Hoop", "Coil", "Seal-ring"),
    "trinket": ("Charm", "Token", "Seal"),
}
_NOUN_STEP = {"COMMON": 0, "UNCOMMON": 0, "RARE": 1, "EPIC": 1, "LEGENDARY": 2}
_MARK = {"COMMON": "", "UNCOMMON": "Sound", "RARE": "Fine",
         "EPIC": "Masterwork", "LEGENDARY": "Signed"}
_EPITHET = {
    "resist_fire": "Emberproof", "resist_cold": "Rimeproof",
    "resist_poison": "Sporeproof", "resist_lightning": "Earthed",
    "resist_void": "Lamplit", "resist_brute": "Braced",
    "armour_points": "Plated", "armour_cap": "Deep-set",
    "stamina_max": "Long-wearing", "stamina_regen": "Second-wind",
    "mana_max": "Clear-headed", "mana_regen": "Steady",
    "loot_luck": "Sharp-eyed", "xp_bonus": "Well-read",
}
_ICONS = {"offhand": "shield", "head": "helm", "chest": "chest",
          "hands": "gauntlets", "feet": "boots", "ring1": "relic",
          "ring2": "relic", "trinket": "relic"}
# The village has no metal (`forge.NO_METAL_REGIONS`) and is the only region
# that does not, so it is named rather than defaulted.
_NO_METAL_MARK = "Homespun"


def _maker(region_id: str) -> str:
    metal = forge.metal_for_region(region_id)
    return metal.name if metal else _NO_METAL_MARK


def _dominant(effects: dict) -> str:
    """The line that cost the most budget. Names the piece and tints it."""
    if not effects:
        return ""
    return max(effects, key=lambda k: float(effects[k]) * RACK_COST[k])


def _name(region_id: str, slot: str, rarity: str, effects: dict) -> str:
    noun = _NOUNS[slot][_NOUN_STEP[rarity]]
    head = _dominant(effects)
    parts = [p for p in (_MARK[rarity], _maker(region_id), noun) if p]
    name = " ".join(parts)
    if head and RACK_RARITIES.index(rarity) >= RACK_RARITIES.index("RARE"):
        name = f"{name}, {_EPITHET.get(head, 'Plain')}"
    return name


def roll(region_id: str, slot: str, *, save_seed: int = 0,
         restock_index: int = 0) -> dict:
    """One slot of the rack, as a plain dict.

    PURE. Same three inputs, same item, for ever. No state is read and none is
    written, which is what lets `counter()` be called on every frame of a shop
    panel and what makes `item_by_id()` able to rebuild a piece a save only
    remembered the id of.
    """
    if slot not in RACK_SLOTS:
        return {}
    rng = _rng(save_seed, region_id, restock_index, f"rack:{slot}")
    rarity = _roll_rarity(rng, region_id)
    budget = _budget(rarity, region_id)
    effects, used = _magnitudes(rng, slot, rarity, budget)
    if not effects:
        return {}
    head = _dominant(effects)
    element = head[len("resist_"):].upper() if head.startswith("resist_") else ""
    item = items.Item(
        id=item_id(region_id, restock_index, slot),
        name=_name(region_id, slot, rarity, effects),
        slot=slot, rarity=rarity, effects=effects,
        icon=_ICONS[slot], source="vendor", element=element,
        flavour=_flavour(rng, region_id, rarity),
    )
    price = economy.rack_price(rarity, region_id,
                               budget_used=used, budget_max=float(budget))
    return {
        **item.to_dict(),
        "kind": "item",
        "price": price,
        "sellback": economy.rack_sellback(price),
        "budget": budget, "budget_used": used,
        "budget_ratio": round(used / budget, 3) if budget else 0.0,
        "region": region_id, "restock_index": int(restock_index),
    }


_FLAVOURS = (
    "Off the {maker} bench, this morning.",
    "Two of these were made. The other one sold.",
    "Nobody has worn it yet. You can tell by the buckles.",
    "The mark on the inside is hers, not the guild's.",
    "It was made to a measurement, and not to yours.",
    "Whoever ordered it did not come back for it.",
)


def _flavour(rng: random.Random, region_id: str, rarity: str) -> str:
    return rng.choice(_FLAVOURS).format(maker=_maker(region_id))


# ==========================================================================
# SECTION 5 — IDENTITY
# ==========================================================================
#
# A generated item is deliberately NOT added to `items.CATALOGUE`. Doing that
# would put shop stock into `items.BY_ID`, into `roll_drop`'s candidate list,
# into the trophy manifest and into every test that counts the catalogue. So a
# rack item carries an id that is its own recipe, and `item_by_id` rebuilds it
# from that id plus the save seed. Nothing about a bought piece has to be
# stored beyond its id, and a save that only remembers ids loses nothing.

ID_PREFIX = "rack"
ID_SEP = "__"       # doubled, so the single underscores in a region id survive


def item_id(region_id: str, restock_index: int, slot: str) -> str:
    return ID_SEP.join((ID_PREFIX, region_id, str(int(restock_index)), slot))


def parse_id(value: str) -> dict:
    parts = str(value).split(ID_SEP)
    if len(parts) != 4 or parts[0] != ID_PREFIX:
        return {}
    _, region_id, index, slot = parts
    if not index.isdigit() or slot not in RACK_SLOTS:
        return {}
    return {"region": region_id, "restock_index": int(index), "slot": slot}


def is_rack_item(value: str) -> bool:
    return bool(parse_id(value))


def item_by_id(value: str, *, save_seed: int = 0) -> dict:
    """Rebuild a rack item from its id. The proof that the rack is a function."""
    parsed = parse_id(value)
    if not parsed:
        return {}
    return roll(parsed["region"], parsed["slot"], save_seed=save_seed,
                restock_index=parsed["restock_index"])


# ==========================================================================
# SECTION 6 — THE WALL
# ==========================================================================

# A NAMING COLLISION, NAMED. `forge.rack(state, blade_id)` already exists and
# means something else entirely — it is the VERB for putting a blade away, and
# `state["forge"]["racked"]` is where it goes. This is the NOUN, the armour
# rack on a shop wall, and it lives in a different module. They never collide
# in code, but this project has already been bitten twice by a word that meant
# two things (`companion` was the pet before it was the escort; `ambush` was an
# SRS retest before it was a pack of beasts), so the third one is written down
# rather than discovered.

def rack(state: dict | None, region_id: str, *, save_seed: int = 0,
         gold: int = 0) -> list:
    """The eight slots, in `items.SLOTS` order, with the sold ones marked.

    Sold slots are returned rather than dropped, because an empty peg is the
    part of the anti-farm rule the player can actually see: the shelf is finite
    by construction and it says so.
    """
    index = economy.rack_index(state, region_id)
    sold = economy.rack_sold(state, region_id)
    rows = []
    for slot in RACK_SLOTS:
        row = roll(region_id, slot, save_seed=save_seed, restock_index=index)
        if not row:
            continue
        was = sold.get(slot)
        row["sold"] = bool(was)
        row["affordable"] = (not was) and int(gold) >= int(row["price"])
        if was:
            row["sold_for"] = int(was.get("price", 0))
        rows.append(row)
    return rows


# -- the blade blank -------------------------------------------------------
#
# "Swords for gold", honoured without a second sword curve. The Shelf sometimes
# has ONE un-tempered blank of the player's own line, at a rung this region's
# own metal could have reached, for that rung's `forge.GOLD_SHAPE` labour plus
# `economy.BLANK_PREMIUM`. It is the same blade the forge makes; the premium is
# for the metal you did not go and find. It tempers, switches and upgrades
# through forge.py exactly like a forged one, because it IS one.

BLANK_CHANCE = 0.35


def max_blank_tier(region_id: str) -> int:
    """The highest rung this region's metal could pay for, derived from
    `forge.COST_SHAPE` and `forge.SLOT_RUNG` rather than typed as a table, so a
    change to the cost shape moves this with it."""
    metal = forge.metal_for_region(region_id)
    if metal is None:
        return 0
    best = 0
    for tier, cost in forge.COST_SHAPE.items():
        if max(forge.SLOT_RUNG[s] for s in cost) <= metal.rung:
            best = max(best, int(tier))
    return best


def blank(state: dict | None, region_id: str, *, save_seed: int = 0,
          blade_id: str = "", gold: int = 0) -> dict:
    """The blank on the Shelf this restock, or {} for none.

    THE OFFER IS ALWAYS THE NEXT RUNG AND NEVER A HIGHER ONE. A blank is a step,
    not a ladder. Offering the top rung a region's metal permits would let a
    player at rung two buy rung nine over the counter, which does not shorten
    the walk — it deletes the walk, and this game's whole spine is the walk.
    `forge.upgrade` moves one rung at a time and so does this.

    `blade_id` is the player's own line. Without one there is no blank: a blank
    of somebody else's class is not a discount, it is a dead object.
    """
    blade_id = blade_id or _blade_of(state)
    if not blade_id or blade_id not in forge.BLADE_BY_ID:
        return {}
    have = forge.owned_tier((state or {}).get("forge", {}) or {}, blade_id)
    if have < forge.MIN_TIER:
        return {}          # the class quest hands over rung one, not the shop
    tier = have + 1
    # Never past what this region's own metal could have reached, and never
    # past the top of the ladder.
    if tier > min(max_blank_tier(region_id), forge.MAX_TIER):
        return {}
    index = economy.rack_index(state, region_id)
    rng = _rng(save_seed, region_id, index, f"blank:{blade_id}:{tier}")
    if rng.random() >= BLANK_CHANCE:
        return {}
    rung = forge.BLADE_BY_ID[blade_id].rung(tier)
    price = economy.blank_price(blade_id, tier)
    return {
        "kind": "blank", "blade": blade_id,
        "line": forge.BLADE_BY_ID[blade_id].line,
        "tier": tier, "rarity": rung.rarity, "name": rung.name,
        "price": price, "forge_labour": int(rung.gold),
        "metal_value": economy.blank_metal_value(blade_id, tier),
        "metal_cost": forge.cost_text(rung.cost),
        "premium": economy.BLANK_PREMIUM,
        "owned_tier": have, "useful": True,
        "affordable": int(gold) >= price,
        "sold": bool((economy.rack_sold(state, region_id) or {}).get("blank")),
        "effect_text": items.describe(rung.effects),
        "note": "The same rung forge.py makes, one step up, bought instead of "
                "forged. The premium is on the whole job, metal included.",
    }


def _blade_of(state: dict | None) -> str:
    class_id = ((state or {}).get("class") or {}).get("class", "")
    blade = forge.blade_for_class(class_id) if class_id else None
    return blade.id if blade else ""


# ==========================================================================
# SECTION 7 — THE COUNTER
# ==========================================================================

# The design document's answer to "level specific potions", said out loud in
# the UI rather than left as a silent design decision: the game bands by REGION
# DEPTH, not character level, so a strong player in a shallow region does not
# find deep stock and a weak player in a deep region is not sold something
# useless. The band is `economy.area_band`, which is `story.band_for`, which is
# the rung of the metal the place gives up. One authority, read three times.
SHELF_NOTE = ("The shelf is what this place can brew. Walk deeper and the "
              "bottles get bigger; nothing you do to yourself changes them.")


def counter(state: dict | None, region_id: str, *, gold: int = 0,
            save_seed: int = 0, blade_id: str = "") -> dict:
    """Everything the Shelf sells, in one call, the way `forge.smith_view` does.

    Potions come back from `economy.vendor_view` untouched — same stock, same
    prices, same restock counter the panel has always shown. The rack and the
    blank are the new rows.
    """
    view = economy.vendor_view(state, region_id, gold=gold)
    if view.get("error"):
        return {**view, "rack": [], "blank": {}}
    rows = rack(state, region_id, save_seed=save_seed, gold=gold)
    return {
        **view,
        "depth": economy.area_depth(region_id),
        "shelf_note": SHELF_NOTE,
        "rack": rows,
        "rack_index": economy.rack_index(state, region_id),
        "rack_left": sum(1 for r in rows if not r["sold"]),
        "rack_bounds": rarity_bounds(region_id),
        "blank": blank(state, region_id, save_seed=save_seed,
                       blade_id=blade_id, gold=gold),
        "credit_note": "Vendor credit buys bottles. The rack takes gold.",
    }


# ==========================================================================
# SECTION 8 — BUYING, AND THE FIVE LOCKS
# ==========================================================================

REFUSALS = {
    "no_vendor": "Nobody keeps a shelf here.",
    "no_slot": "Nothing hangs on that peg.",
    "sold": "That one is gone. The rack fills when the work does.",
    "no_gold": "Not enough gold. The rack does not take credit.",
    "not_bought": "You did not buy that here.",
    "not_held": "You are not carrying that.",
    "no_blank": "There is no blank on the Shelf this week.",
    "owned": "Your blade is already at that rung or past it.",
}


def buy(state: dict, region_id: str, slot: str, *, gold: int = 0,
        save_seed: int = 0) -> dict:
    """Take a piece off the rack.

    REPORTS the spend; never touches the purse and never touches the
    inventory. `engine.py` owns both, exactly as it does for `forge.upgrade`
    and `economy.buy_potion`.

    LOCK 4, stated where it is enforced: vendor credit is NOT read here. Credit
    is a quest reward and quest rewards are already curved; letting it buy
    generated armour would route a curved reward around the taper that curves
    it. Credit stays on the bottles.
    """
    if economy.vendor_for(region_id) is None:
        return {"error": "no_vendor", "text": REFUSALS["no_vendor"]}
    index = economy.rack_index(state, region_id)
    ledger = economy.rack_ledger(state, region_id)
    if slot in ledger:
        return {"error": "sold", "text": REFUSALS["sold"]}
    row = roll(region_id, slot, save_seed=save_seed, restock_index=index)
    if not row:
        return {"error": "no_slot", "text": REFUSALS["no_slot"]}
    price = int(row["price"])
    if int(gold) < price:
        return {"error": "no_gold", "text": REFUSALS["no_gold"],
                "price": price, "needs_gold": price - int(gold)}
    ledger[slot] = {"item": row["id"], "price": price}
    economy.rack_receipts(state, region_id)[row["id"]] = price
    economy.spend(state, economy.RACK_SINK, price)
    return {"bought": row["id"], "item": row, "slot": slot,
            "price": price, "gold_spent": price,
            "credit_spent": 0,
            "sellback": economy.rack_sellback(price),
            "rack_index": index,
            "note": "engine.py adds the item and subtracts the gold."}


def sell(state: dict, region_id: str, item_id_value: str,
         *, inventory: list | None = None) -> dict:
    """Sell a rack piece back to the vendor who sold it, once, for a quarter.

    LOCK 5. A quarter makes buy -> sell a 75% loss, so there is no laundering
    loop and no arbitrage between two regions' racks. The peg does NOT reopen:
    selling a piece back does not put it back on the wall.

    It reads the RECEIPT, not the peg. The pegs are cleared every time the
    shelves turn over, so reading them would have meant that a piece bought
    before a restock could never be sold back — the shop that sold it would
    say "you did not buy that here" six cleared encounters later. The receipt
    survives the restock and is torn up on the sale, which is also what makes
    a second sale of the same piece refuse rather than pay twice.

    LOCK 6, AND THE RECEIPT IS NOT THE PIECE. A receipt deliberately outlives
    the restock — that is the whole point of it — so on its own it says "this
    vendor sold you one of these", never "you still have it". Any engine that
    removes a rack item by a route other than this call (death, a drop, a
    future disenchant, a save repair) would leave a live receipt that still
    paid 25% of the price for an empty hand. So pass the bag and possession
    becomes a named refusal like every other lock in this section.

    `inventory` is optional ONLY so that a caller checking a price, and the
    module's own proofs, need not synthesise one. An engine ALWAYS passes it:
    CONTRACT section 3 says so.

    THE RECEIPT IS TORN UP LAST. Every refusal returns before the `pop`, so a
    sale that is going to be refused cannot cost the player the receipt on the
    way out.
    """
    receipts = economy.rack_receipts(state, region_id)
    if item_id_value not in receipts:
        return {"error": "not_bought", "text": REFUSALS["not_bought"]}
    if inventory is not None and item_id_value not in inventory:
        return {"error": "not_held", "text": REFUSALS["not_held"]}
    paid = int(receipts.pop(item_id_value))
    back = economy.rack_sellback(paid)
    return {"sold": item_id_value, "paid": paid,
            "gold_back": back, "loss": paid - back,
            "slot": (parse_id(item_id_value) or {}).get("slot", ""),
            "note": "engine.py adds the gold and removes the item."}


def buy_blank(state: dict, region_id: str, *, gold: int = 0,
              save_seed: int = 0, blade_id: str = "") -> dict:
    """Buy the blank, if there is one.

    BLOCKED, and said in the return value rather than in a commit message:
    `state["forge"]["tiers"]` is forge.py's to write and forge.py has no public
    mutator that sets a rung without consuming metal — `forge.upgrade` demands
    the cost and `forge.grant_blade` only ever hands over rung one. So this
    returns a `grant`, the way `economy.record` returns gold, and engine.py
    applies it. A one-line `forge.grant_rung(state, blade_id, tier)` would let
    this call it directly; forge.py is not this pass's to edit.
    """
    offer = blank(state, region_id, save_seed=save_seed, blade_id=blade_id,
                  gold=gold)
    if not offer:
        return {"error": "no_blank", "text": REFUSALS["no_blank"]}
    ledger = economy.rack_ledger(state, region_id)
    if "blank" in ledger:
        return {"error": "sold", "text": REFUSALS["sold"]}
    price = int(offer["price"])
    if int(gold) < price:
        return {"error": "no_gold", "text": REFUSALS["no_gold"],
                "price": price, "needs_gold": price - int(gold)}
    ledger["blank"] = {"item": f"blank:{offer['blade']}:{offer['tier']}",
                       "price": price}
    economy.spend(state, economy.RACK_SINK, price)
    return {"bought": offer["blade"], "tier": offer["tier"], "price": price,
            "gold_spent": price, "blank": offer,
            "grant": {"owner": "forge", "blade": offer["blade"],
                      "tier": offer["tier"]},
            "note": "forge.py owns state['forge']['tiers']. engine.py applies "
                    "the grant and subtracts the gold."}


# ==========================================================================
# SECTION 9 — THE CHECKS
# ==========================================================================

def _no_rack_item_supplies_an_answer() -> list:
    """Modelled on `captives._no_boon_supplies_an_answer`, and for the same
    reason. A rack item buys mitigation, bars, and the two slow economies. None
    of them may buy a look at the problem, the enemy or the answer."""
    problems = []
    for key in sorted(RACK_EFFECTS):
        if key in RACK_EFFECTS_REFUSED:
            problems.append(f"{key!r} is on the rack allowlist AND on the "
                            f"refusal list; a shop may never sell a look at "
                            f"the answer")
        if key not in items.EFFECT_LABELS:
            problems.append(f"{key!r} is not an items.EFFECT_LABELS key, so "
                            f"nothing will ever apply it")
    for slot, keys in SLOT_KEYS.items():
        for key in keys:
            if key not in RACK_EFFECTS:
                problems.append(f"slot {slot!r} may roll {key!r}, which is not "
                                f"on the rack allowlist")
    return problems


def _ceiling_holds() -> list:
    """THE INVARIANT: no generated item beats an authored one of its rarity.

    Not asserted — enumerated. Every region, every slot, every rarity the
    region's clamp permits, against the measured per-key ceiling and the
    measured per-roll budget ceiling. This is the check the design document
    said should be written before the generator, and it is the check that
    caught the design document's own LEGENDARY budget running 34% over the
    authored bar at depth 7.
    """
    problems = []
    for region in world.REGIONS:
        rid = region["id"]
        for rarity in RACK_RARITIES:
            budget = _budget(rarity, rid)
            if budget > ROLL_CEILING.get(rarity, 0) + 1e-9:
                problems.append(
                    f"{rid}/{rarity}: budget {budget} exceeds the authored "
                    f"ceiling {ROLL_CEILING.get(rarity)}")
            table = CEILINGS.get(rarity, {})
            for slot in RACK_SLOTS:
                for key in _keys_for(slot, rarity):
                    if key not in table:
                        problems.append(f"{rarity}/{slot}: {key} has no "
                                        f"authored ceiling")
    return problems


def _rolls_respect_the_ceiling(seeds: int = 8) -> list:
    """The clamp, exercised rather than trusted: real rolls, real regions.

    Eight seeds at import — about three thousand rolls, a tenth of a second —
    because this runs every time anything in the game loads. The exhaustive
    version is `tests/test_shop.py`, which runs a quarter of a million.
    """
    problems = []
    for seed in range(seeds):
        for region in world.REGIONS:
            rid = region["id"]
            for index in (0, 3, 11):
                for slot in RACK_SLOTS:
                    row = roll(rid, slot, save_seed=seed * 7919,
                               restock_index=index)
                    if not row:
                        continue
                    table = CEILINGS[row["rarity"]]
                    for key, value in row["effects"].items():
                        if float(value) > float(table.get(key, 0)) + 1e-9:
                            problems.append(
                                f"{rid}/{slot}/{row['rarity']}: {key}="
                                f"{value} over ceiling {table.get(key)}")
                    if row["rarity"] == "MYTHIC":
                        problems.append(f"{rid}/{slot}: the rack rolled MYTHIC")
                    if row["price"] <= 0:
                        problems.append(f"{rid}/{slot}: priced at nothing")
    return problems


def validate() -> list:
    problems = _no_rack_item_supplies_an_answer()
    problems.extend(_ceiling_holds())
    problems.extend(_rolls_respect_the_ceiling())

    # -- the rarity locks actually lock -----------------------------------
    #
    # THE TABLE IS CHECKED AGAINST A NAMED LIST, NOT AGAINST ITSELF. The loop
    # below iterates MIN_RARITY, which makes it vacuous on a SHORTENED table:
    # delete a key and there is nothing left to iterate over it, so the guard
    # that exists to prove the lock reports success by having nothing to say.
    # Measured on a clone with `"xp_bonus": "EPIC"` removed: validate() returned
    # [], all 51 tests in tests/test_shop.py passed, and +5% XP shipped on 9.78%
    # of COMMON python_village rolls — a 30-gold common ring that pays the
    # player back. Emptying the table entirely also passed, and additionally put
    # `armour_cap` on 5.63% of commons.
    #
    # This is the same discipline the module already applies to
    # RACK_EFFECTS_REFUSED and captives.py applies to its boons: the refusal is
    # stated against a list somebody has to deliberately edit, so widening it is
    # a visible act rather than a deletion. The mechanism six lines below
    # (`_keys_for`) is already pinned — removing it dies at import — and
    # DEPTH_BANDS is pinned by tests/test_shop.py:110. This table was the one
    # thing in the section nothing was holding.
    #
    # `CEILINGS` is a coincidental second gate for `loot_luck` only — no
    # authored COMMON item carries it — and is NOT one for `armour_cap` or
    # `xp_bonus`, whose COMMON ceilings are 0.5 and 0.05.
    PAYING_KEYS = ("loot_luck", "armour_cap", "xp_bonus")
    for key in PAYING_KEYS:
        if key not in MIN_RARITY:
            problems.append(f"{key!r} pays the player back and carries no "
                            f"MIN_RARITY lock")
    for key, need in MIN_RARITY.items():
        for rarity in RACK_RARITIES:
            if RACK_RARITIES.index(rarity) >= RACK_RARITIES.index(need):
                continue
            for slot in RACK_SLOTS:
                if key in _keys_for(slot, rarity):
                    problems.append(f"{key} is offered at {rarity}, below its "
                                    f"{need} lock")

    # -- the rack cannot be rerolled ---------------------------------------
    a = [roll("graph_wastes", s, save_seed=42, restock_index=5)
         for s in RACK_SLOTS]
    b = [roll("graph_wastes", s, save_seed=42, restock_index=5)
         for s in RACK_SLOTS]
    if a != b:
        problems.append("the rack is not a pure function of its three inputs")
    c = [roll("graph_wastes", s, save_seed=42, restock_index=6)
         for s in RACK_SLOTS]
    if a == c:
        problems.append("a restock does not change the rack")

    # -- price is monotone in rarity ---------------------------------------
    prices = [economy.rack_price(r, "graph_wastes", budget_used=1.0,
                                 budget_max=1.0) for r in RACK_RARITIES]
    if prices != sorted(prices):
        problems.append(f"rack prices are not monotone in rarity: {prices}")
    if any(economy.rack_sellback(p) >= p for p in prices):
        problems.append("sell-back is not a loss")

    # -- eight pegs, eight different objects -------------------------------
    for region in world.REGIONS:
        if economy.vendor_for(region["id"]) is None:
            continue
        for index in (0, 1, 2):
            names = [r["name"] for r in
                     rack(None, region["id"], save_seed=index * 31 + 5)]
            if len(set(names)) != len(names):
                problems.append(f"{region['id']}: two pegs carry the same "
                                f"name: {sorted(names)}")

    # -- ids round-trip ----------------------------------------------------
    for region in world.REGIONS:
        for slot in RACK_SLOTS:
            back = parse_id(item_id(region["id"], 3, slot))
            if back != {"region": region["id"], "restock_index": 3,
                        "slot": slot}:
                problems.append(f"id does not round-trip: {region['id']}/{slot}")
    return problems


def rarity_distribution(region_id: str, *, samples: int = 10_000) -> dict:
    """The measured curve, for the test and for anybody who does not believe it."""
    counts = {r: 0 for r in RACK_RARITIES}
    for i in range(samples):
        for slot in RACK_SLOTS:
            row = roll(region_id, slot, save_seed=i, restock_index=0)
            if row:
                counts[row["rarity"]] += 1
    total = sum(counts.values()) or 1
    return {"region": region_id, "samples": total, "counts": counts,
            "share": {r: round(100.0 * n / total, 3) for r, n in counts.items()},
            "bounds": rarity_bounds(region_id)}


def declared_curve(region_id: str) -> dict:
    """What the rolled curve is supposed to be, computed from
    `items.RARITIES` and the region's clamp. The test compares the two."""
    weights = {r: items.RARITIES[r]["weight"] for r in RACK_RARITIES}
    total = sum(weights.values())
    raw = {r: weights[r] / total for r in RACK_RARITIES}
    floor, ceiling = rarity_bounds(region_id)
    lo, hi = RACK_RARITIES.index(floor), RACK_RARITIES.index(ceiling)
    out = {r: 0.0 for r in RACK_RARITIES}
    for r, p in raw.items():
        i = min(max(RACK_RARITIES.index(r), lo), hi)
        out[RACK_RARITIES[i]] += p
    return {r: round(100.0 * p, 3) for r, p in out.items()}


def self_check() -> dict:
    problems = validate()
    return {
        "ok": not problems,
        "problems": problems,
        "slots": len(RACK_SLOTS),
        "effects": len(RACK_EFFECTS),
        "ceilings": {r: ROLL_CEILING[r] for r in RACK_RARITIES},
        "budgets": {r: {d: min(round(BASE_BUDGET[r] * (1 + DEPTH_STEP * d)),
                               int(ROLL_CEILING[r]))
                        for d in range(economy.MAX_DEPTH + 1)}
                    for r in RACK_RARITIES},
        "village": declared_curve("python_village"),
        "wastes": declared_curve("graph_wastes"),
    }


CONTRACT = """
FOR WHOEVER IS WIRING THIS. Nothing here needs new instrumentation. Every
argument is a value engine.py already holds at the moment the player walks up
to a counter.

THE THREE RULES THAT MAKE THE REST SAFE
    NOTHING IN THIS MODULE TOUCHES state["player"]["gold"] — buy() and
    buy_blank() return `gold_spent` and the engine subtracts it, exactly as it
    already does for forge.upgrade() and economy.buy_potion().
    NOTHING IN THIS MODULE TOUCHES THE INVENTORY — buy() returns `item` and the
    engine files it.
    NOTHING IN THIS MODULE WRITES state["forge"] — buy_blank() returns a
    `grant` and the engine applies it. See BLOCKED, below.

0. STATE
   None of its own. The rack lives in economy's vendor room, which already
   exists in every save:
       state["economy"]["vendors"][region]["rack"]       int, the restock index
       state["economy"]["vendors"][region]["rack_sold"]  {slot: {item, price}}
   Both are back-filled by economy._vendor_room(), so an old save loads with an
   untouched rack rather than a KeyError.

   `save_seed` is state["world_seed"] — engine.DEFAULT_STATE already holds it
   and engine._reseed_world already writes it. Pass it through; do not invent a
   second one, or two shops in one save will disagree about what is on the wall.

1. THE COUNTER — one call, the whole building
       view = shop.counter(game.state, region_id,
                           gold=game.state["player"]["gold"],
                           save_seed=game.state.get("world_seed", 0))
   `view["stock"]` is economy.vendor_view's potion rows, unchanged, so an
   existing panel keeps working. `view["rack"]` is eight rows; `view["blank"]`
   is one row or {}.

2. BUYING ARMOUR
       out = shop.buy(game.state, region_id, slot,
                      gold=game.state["player"]["gold"], save_seed=seed)
       if "error" not in out:
           game.state["player"]["gold"] -= out["gold_spent"]
           <add out["item"] to the inventory>
   `out["item"]` is an items.Item.to_dict() with a `price`, so the inventory
   needs no new shape. It is NOT in items.BY_ID — see 4.

   SEAL IT. A rack purchase is a loadout change mid-exam. Gate the call on
   `self._sealed_in_interview()` in engine.py and on `self._sealed(g)` at the
   route, at capability BUILD, exactly as /api/shop/buy already is.
   `economy.buy_potion` is sealed twice for this reason — once at the engine
   and once at the door — and tests/test_interview_isolation.py:181 already
   lists /api/shop/buy as a BUILD-sealed route. buy() and buy_blank() have no
   gate of their own and must not be given one here: this module never reads
   the exam, and a story layer that started asking whether a measurement was
   running would be the first time one did. The gate belongs at the two doors,
   and the same sentence applies to buy_blank() in full.

3. SELLING BACK
       out = shop.sell(game.state, region_id, item_id,
                       inventory=game.state["inventory"])
       game.state["player"]["gold"] += out["gold_back"]
   PASS THE BAG. Without it the receipt alone pays out, and a receipt outlives
   the restock on purpose — it says the vendor sold you one, never that you
   still have it. `{"error": "not_held"}` is the refusal. Selling is a loadout
   change too: seal it the same way section 2 says.

4. PERSISTING A RACK ITEM
   Store the id and nothing else. shop.item_by_id(item_id, save_seed=seed)
   rebuilds the whole piece. Any code that does items.BY_ID[item_id] on an
   equipped piece must first ask shop.is_rack_item(item_id) — that is the one
   integration point a generated item creates, and it is one line:
       piece = (shop.item_by_id(i, save_seed=seed) if shop.is_rack_item(i)
                else items.BY_ID.get(i))

5. RESTOCK — already wired
   economy.restock(state, region_id) is already called per cleared encounter.
   It now also turns the rack over. No new call site.

BLOCKED, and named rather than worked around:
   forge.py has no public mutator that sets a blade's rung without consuming
   metal — upgrade() demands the cost and grant_blade() only hands over rung
   one. buy_blank() therefore returns
       {"grant": {"owner": "forge", "blade": <id>, "tier": <n>}}
   for the engine to apply. A one-line forge.grant_rung(state, blade_id, tier)
   would let this module call it directly. forge.py was not this pass's to edit.
"""


_PROBLEMS = validate()
if _PROBLEMS:   # pragma: no cover - refuse to load a shop that can out-drop a boss
    raise AssertionError("gauntlet.shop: " + "; ".join(_PROBLEMS))


if __name__ == "__main__":   # pragma: no cover
    import json
    check = self_check()
    print(json.dumps({k: v for k, v in check.items() if k != "problems"},
                     indent=2))
    print("self check:", "ok" if check["ok"] else check["problems"])
    for rid in ("python_village", "array_caverns", "graph_wastes"):
        print()
        print(rid, rarity_distribution(rid, samples=400)["share"])
