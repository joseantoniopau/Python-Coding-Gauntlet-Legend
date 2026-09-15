"""The wheel: six elements, seventeen areas, one damage function, and what
armour, status and boots actually do.

WHAT THIS MODULE IS FOR, AND WHAT IT IS FORBIDDEN FROM DOING
------------------------------------------------------------
The attack in this game is a line of Python the player types. `incantation.cast`
decides whether that line was correct; if it was not, the turn is wasted and the
damage is zero. Nothing in this file can change that, and nothing in this file is
consulted until after a cast has already landed.

So the whole of the elemental layer is a MULTIPLIER ON A NUMBER THAT THE TYPING
ALREADY EARNED. It decides how LONG a fight is, which decides how many times the
player types the idiom, which is the only pedagogical lever any of this has. An
element that could win a fight on its own would be an element that removed
repetition, and removing repetition is the one thing this game must not do.

Two consequences are enforced by `self_check`:

  * `resolve_damage` takes `base` as an argument. It never generates damage. Feed
    it zero and it returns zero: a wrong cast stays a wrong cast.
  * no status effect in `STATUSES` can skip, shorten or block the victim's turn.
    Every status is damage, mitigation or amplification. A poisoned player still
    types the same line; they simply have less room to get it wrong.

THE AMBIGUITY IN THE BRIEF, AND HOW IT IS RESOLVED
--------------------------------------------------
The brief asks for fire against cold, cold against fire, void against poison,
lightning against void, poison against brute force, brute force against poison,
and separately that "void should be lightning". Those cannot all hold: void
cannot both beat lightning's beater and be lightning, and poison cannot sit
opposite brute force while also being void's prey on equal terms.

Resolved as THREE OPPOSED PAIRS, which is the shape most of those clauses already
describe and the shape with the most strategy in it — three real choices rather
than one long chain where one element quietly sits at the top:

        FIRE  <->  COLD
        POISON <-> BRUTE
        LIGHTNING <-> VOID

Opposition is SYMMETRIC. Fire is strong into cold AND cold is strong into fire,
because a pair where one side wins is a pair nobody picks the losing half of.

"Void against poison" survives as a SECONDARY advantage (`SECONDARY`), worth less
than a true opposition and carrying its own weak mirror — poison into void is
slightly blunted. It is the one asymmetric edge on the wheel and it is documented
rather than hidden, because the player has to be able to learn it.

MONSTERS THAT ARE MORE THAN ONE THING
-------------------------------------
Section H adds the multi-affinity layer, and it is additive in the strict sense:
`Defender.elements` defaults to empty, which means "just `element`", which is
what every caller that predates it passes. A defender with several affinities
resolves through a WEIGHTED MEAN of its per-element matchups, weights 2-1-1,
primary first. A mean of numbers in [0.65, 1.50] is in [0.65, 1.50], so the
floor below — a mismatched fight is at most four times as long and never
unwinnable — is inherited rather than re-argued, and `_prove_multi_affinity`
measures it over every legal chain rather than asserting it.

No defender is ever both halves of an opposed pair, which is what guarantees a
player always has a weapon whose counter is not simultaneously a shrug.
`threat_view` is how any of that reaches the screen.

NEUTRAL IS NOT AN ELEMENT
-------------------------
`NEUTRAL` is a sentinel, deliberately absent from `ELEMENTS`. It has no
opposition, no status and no resistance, and a wheel where every region and every
animal is something is a wheel with no contrast in it — the player would never
feel the moment an area starts pushing back. Five of the seventeen regions are
neutral on purpose. Every companion, by contrast, does have an element: there
are only twelve of them, they are chosen rather than wandered into, and a
companion with no place on the wheel would be a companion with nothing to say
about where you are standing.

VOCABULARY ALIGNMENT WITH THE EXISTING GAME
-------------------------------------------
The player already has the two bars the brief asks for, under older names, and
this module does not rename them because saves and the client both read them:

        HEALTH  is  player["stamina"] / player["stamina_max"]   (config.STAMINA_MAX)
        FOCUS   is  player["mana"]    / player["mana_max"]      (config.MANA_MAX)

`HEALTH_FIELD` and `FOCUS_FIELD` are exported so no caller has to guess.

THE SEAL
--------
There is exactly one isolation path in this game and it is `finalexam.sealed`.
This module does not form a second opinion about it: it has no idea what mode it
is in and never asks. The caller passes the verdict in, the same way
`pets.available_in` takes `sealed=` as an argument.

    build_sealed=finalexam.sealed(enc, "BUILD")   -> gear element, gear resists and
                                                     armour points all go away
    revealed=not finalexam.sealed(enc, "WEAKNESS_MAP")
                                                  -> whether the enemy's element
                                                     may be shown at all
    potions  -> finalexam.sealed(enc, "ITEMS"), which engine.use_consumable
                already checks. This module adds no new capability name.

Mastery is untouched by everything here. A potion is not evidence, an elemental
advantage is not evidence, and no function in this file returns a skill delta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import world

__all__ = [
    "FIRE", "COLD", "POISON", "BRUTE", "LIGHTNING", "VOID", "NEUTRAL",
    "Element", "ELEMENTS", "ELEMENT_IDS", "ALL_AFFINITIES",
    "OPPOSED", "SECONDARY", "opposes", "matchup", "element_view",
    "AFFINITY", "affinity_for", "enemy_element", "boss_element",
    "Status", "STATUSES", "STATUS_IDS", "StatusInstance",
    "inflict", "tick_statuses", "cure", "CURES", "outgoing_scale", "marks",
    "ArmourProfile", "ARMOUR_KINDS", "armour_profile", "armour_from_effects",
    "Defender", "DamageResult", "resolve_damage",
    "Boots", "BOOTS", "Hazard", "HAZARDS", "hazard_for", "hazard_step",
    "PET_ELEMENT", "pet_element",
    "EXTRA_AFFINITY", "REGION_AFFINITIES", "MAX_AFFINITIES", "MULTI_WEIGHTS",
    "SECOND_AFFINITY_AT", "THIRD_AFFINITY_AT", "affinity_count",
    "affinities_for", "enemy_elements", "matchup_multi", "strike_element",
    "threat_view", "combination_advice",
    "HEALTH_FIELD", "FOCUS_FIELD",
    "MIN_DAMAGE", "MULT_FLOOR", "MULT_CEIL", "RESIST_CAP", "ARMOUR_POINT_CAP",
    "WORST_CASE_MULTIPLIER", "MAX_FIGHT_STRETCH",
    "MAX_FIGHT_STRETCH_VS_COUNTER", "HEALTH_EFFECT_KEY", "FOCUS_EFFECT_KEY",
    "self_check",
]

# The two bars, under the names the save file already uses. Renaming them would
# be a migration for no gain; naming them here is free.
HEALTH_FIELD = "stamina"
FOCUS_FIELD = "mana"

# The EFFECT keys gear uses to lengthen those two bars. These are NOT the same
# strings as the fields above, and they already exist: engine.py reads them when
# it sizes the bars, and items.EFFECT_LABELS already documents both. The brief's
# "cloaks and helms give health and focus" is therefore already wired — it needs
# naming here, not reimplementing. See `armour_from_effects`.
HEALTH_EFFECT_KEY = "stamina_max"
FOCUS_EFFECT_KEY = "mana_max"


def _round_half_up(value: float) -> int:
    """Rounding, the way a player expects it.

    `round()` is banker's rounding, so `round(2.5)` is 2, and at the small
    numbers this game deals in that is not a rounding rule, it is a stealth
    nerf: it turns the guaranteed floor of a quarter of neutral damage into a
    fifth. Half goes up, always, and the guarantee in `resolve_damage` holds as
    stated.
    """
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


# ---------------------------------------------------------------------------
# A. The six elements
# ---------------------------------------------------------------------------

FIRE = "FIRE"
COLD = "COLD"
POISON = "POISON"
BRUTE = "BRUTE"
LIGHTNING = "LIGHTNING"
VOID = "VOID"
NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class Element:
    id: str
    name: str
    colour: str          # the art's primary. Drawn from the palettes already in
                         # items.RARITIES and world.BOSSES so nothing clashes.
    dark: str            # the shade, for outlines and the damage number's drop
    glyph: str           # ASCII. The terminal client can always draw this.
    rune: str            # BMP. The web client draws this instead.
    status: str          # the status this element inflicts, "" for none
    opposed: str         # the element it counters and is countered by
    blurb: str


ELEMENTS: dict = {
    FIRE: Element(
        FIRE, "Fire", "#e06a3c", "#8f3a1e", "^", "▲", "BURNING", COLD,
        "Rises, spends itself, and leaves the wound still burning."),
    COLD: Element(
        COLD, "Cold", "#7ec8ff", "#2f6d9e", "*", "▼", "CHILLED", FIRE,
        "Settles, and makes everything it touches slower to swing."),
    POISON: Element(
        POISON, "Poison", "#8fd07a", "#3f7a3a", "~", "◆", "POISONED", BRUTE,
        "Patient. It does not care how the fight is going right now."),
    BRUTE: Element(
        BRUTE, "Brute Force", "#bf8f4f", "#6f4f28", "#", "■", "STAGGERED",
        POISON,
        "No cleverness at all. It simply arrives, and plate stops mattering."),
    LIGHTNING: Element(
        LIGHTNING, "Lightning", "#f2dc6a", "#9a8220", "/", "✦", "SHOCKED",
        VOID,
        "One instant of contact, and everything after it conducts."),
    VOID: Element(
        VOID, "Void", "#6a4f8f", "#2f2445", ".", "●", "VOIDED", LIGHTNING,
        "Not a force. An absence, arriving where a force was expected."),
}

ELEMENT_IDS: tuple = tuple(ELEMENTS)

# Neutral gets a display record so the art never has to special-case it, but it
# is NOT in ELEMENTS and never will be: it has no opposition, and `self_check`
# asserts that every entry in ELEMENTS does.
_NEUTRAL_VIEW = Element(
    NEUTRAL, "Neutral", "#9b96b8", "#4a4450", "+", "○", "", "",
    "Weather-free. Whatever happens here, happens because you did it.")

ALL_AFFINITIES: dict = dict(ELEMENTS)
ALL_AFFINITIES[NEUTRAL] = _NEUTRAL_VIEW

# The three pairs, flattened both ways so a lookup is a dict hit rather than a
# search. Symmetric by construction — see the module docstring.
OPPOSED: dict = {e.id: e.opposed for e in ELEMENTS.values()}

# The one asymmetric edge the brief asked for and the pairs could not absorb.
# Void eats poison a little faster than it eats anything else; poison finds
# nothing in the void to work on. Both directions are stated so neither is a
# surprise, and both are weaker than a real opposition so the pairs stay the
# structure the player actually learns.
SECONDARY: dict = {VOID: POISON}
SECONDARY_MIRROR: dict = {POISON: VOID}


def opposes(attacker: str, defender: str) -> bool:
    """True when these two are a pair. Symmetric, and that is the point."""
    return bool(attacker) and OPPOSED.get(attacker) == defender


# -- the numbers, and why they are these numbers ----------------------------
#
# OPPOSED 1.50    A fight two thirds as long. Big enough to feel like a reward
#                 for reading the area, small enough that it is not a substitute
#                 for typing the idiom correctly.
# SECONDARY 1.20  Noticeably better than nothing, clearly worse than a pair.
#                 If it were 1.5 it would be a fourth pair, which is not what
#                 the brief described.
# WEAK_INTO 0.85  The mirror of the above. Small, so the player learns it by
#                 noticing rather than by being punished.
# SAME 0.65       Hitting fire with fire. Reduced rather than nullified, because
#                 "your element does nothing here" is a dead end and a 35% tax
#                 is a reason to go and find a different weapon.
# NEUTRAL 1.00    Both directions. Neutral areas are the control group.
_OPPOSED_MULT = 1.50
_SECONDARY_MULT = 1.20
_WEAK_INTO_MULT = 0.85
_SAME_MULT = 0.65
_NEUTRAL_MULT = 1.00

MATCHUP_MULT: dict = {
    "OPPOSED": _OPPOSED_MULT,
    "SECONDARY": _SECONDARY_MULT,
    "WEAK_INTO": _WEAK_INTO_MULT,
    "SAME": _SAME_MULT,
    "NEUTRAL": _NEUTRAL_MULT,
}

MATCHUP_LABEL: dict = {
    "OPPOSED": "a counter",
    "SECONDARY": "an edge",
    "WEAK_INTO": "blunted",
    "SAME": "shrugged off",
    "NEUTRAL": "plain",
}


def matchup(attacker: str, defender: str) -> tuple:
    """`(multiplier, kind)` for one element striking another.

    Pure, total and symmetric on the pairs. `NEUTRAL`, `""` and any unknown
    string all resolve to the neutral case rather than raising, because an
    unelemented enemy is a normal thing for the bestiary to contain and a
    KeyError in the middle of a fight is not.
    """
    a = attacker if attacker in ELEMENTS else NEUTRAL
    d = defender if defender in ELEMENTS else NEUTRAL
    if a == NEUTRAL or d == NEUTRAL:
        kind = "NEUTRAL"
    elif OPPOSED[a] == d:
        kind = "OPPOSED"
    elif a == d:
        kind = "SAME"
    elif SECONDARY.get(a) == d:
        kind = "SECONDARY"
    elif SECONDARY_MIRROR.get(a) == d:
        kind = "WEAK_INTO"
    else:
        kind = "NEUTRAL"
    return MATCHUP_MULT[kind], kind


def element_view(element: str, *, revealed: bool = True) -> dict:
    """What the client may draw for an element.

    `revealed` is the caller's verdict, which is
    `not finalexam.sealed(enc, "WEAKNESS_MAP")`. When it is False the element
    still exists and still multiplies — the fight does not become neutral — but
    the player is not told which one it is. That is the crutch being removed,
    not the mechanic.
    """
    view = ALL_AFFINITIES.get(element or NEUTRAL, _NEUTRAL_VIEW)
    if not revealed:
        return {"id": "", "name": "Unreadable", "colour": _NEUTRAL_VIEW.colour,
                "dark": _NEUTRAL_VIEW.dark, "glyph": "?", "rune": "?",
                "status": "", "opposed": "", "revealed": False,
                "blurb": "Nothing about this one is labelled."}
    return {"id": view.id, "name": view.name, "colour": view.colour,
            "dark": view.dark, "glyph": view.glyph, "rune": view.rune,
            "status": view.status, "opposed": view.opposed, "revealed": True,
            "blurb": view.blurb}


# ---------------------------------------------------------------------------
# B. Area affinity, for all seventeen regions
# ---------------------------------------------------------------------------
#
# Derived from the BIOME each region already declares in world.REGIONS, not
# invented next to it, so a region's weather follows from what it physically is.
# The map below is keyed by biome, and `AFFINITY` is built from world.REGIONS by
# looking each region's biome up — which means a new region gets an affinity for
# free and `self_check` fails loudly if a biome ever appears that nobody has
# placed on the wheel.
#
# Five biomes are NEUTRAL and that is a decision rather than an omission. The
# Coliseum in particular says in its own description that it is a sand floor, a
# clock and no hints; giving it weather would be the module contradicting the
# region. The neutral regions are where the player learns what a plain fight
# costs, which is the baseline every other area is felt against.
BIOME_AFFINITY: dict = {
    # -- elemental --------------------------------------------------------
    "highland":  LIGHTNING,   # an exposed plateau of keyed vaults, and the only
                              # tall metal for a day's walk in any direction
    "forest":    POISON,      # Stringwood: living, humid, and shedding spores
                              # between the letters. The rainforest of the brief.
    "cave":      BRUTE,       # Array Caverns. Stone, and the weight above it.
    "swamp":     POISON,      # Sliding Window Marsh. Standing water and gas.
    "mountain":  COLD,        # Twin Pointer Pass, at the snow line. The brief's
                              # snowfield, and the only region with real ice.
    "mine":      FIRE,        # Stack & Queue Mines, palette "ember". The heat is
                              # already in the region's own colours.
    "citadel":   BRUTE,       # Matrix Citadel, where the floor plan is a golem.
    "deepforest": VOID,       # Recursive Forest: each clearing contains a smaller
                              # copy. A recursion that does not return is the
                              # nearest thing this world has to an absence.
    "wastes":    LIGHTNING,   # Graph Wastes. A lattice of ruins is a lattice of
                              # conductors, and the storms have noticed.
    "dungeon":   FIRE,        # Debugging Dungeon, which world.py calls the
                              # Armorer's forge in its own blurb.
    "tower":     COLD,        # Complexity Tower, palette "azure". Every floor
                              # costs more and is colder than the one below.
    "castle":    VOID,        # The Null King's. Palette "void". Nothing is
                              # labelled and nothing is lit.

    # -- neutral, deliberately --------------------------------------------
    "village":   NEUTRAL,     # a town. Weather in a town is just weather.
    "grass":     NEUTRAL,     # the first fields. Nothing should push back yet.
    "canopy":    NEUTRAL,     # open air above the Recursive Forest's dark
    "ruins":     NEUTRAL,     # DP Ruins: what is remarkable here is the light
                              # already on the solved tiles
    "arena":     NEUTRAL,     # the Coliseum. A sand floor, a clock, and no hints.
}

AFFINITY: dict = {r["id"]: BIOME_AFFINITY.get(r["biome"], NEUTRAL)
                  for r in world.REGIONS}


def affinity_for(region_id: str) -> str:
    """The element of a place. Unknown places are neutral, never an exception."""
    return AFFINITY.get(region_id, NEUTRAL)


def enemy_element(enemy, region_id: str = "") -> str:
    """What element a monster fights with.

    The bestiary does not carry an element and does not need to: an enemy takes
    the affinity of the ground it is standing on, which is exactly the brief's
    "every area has an affinity from its surroundings" pushed one step down into
    the things that live there. An entry that names its own `element` wins, so a
    future bestiary can override without this module changing.

    Accepts an Enemy, a dict, or None.
    """
    own = None
    if enemy is not None:
        own = (getattr(enemy, "element", None)
               if not isinstance(enemy, dict) else enemy.get("element"))
    if own in ELEMENTS or own == NEUTRAL:
        return own
    return affinity_for(region_id)


def boss_element(boss_id: str) -> str:
    """A boss is made of its region, same as everything else in it."""
    boss = world.BOSS_BY_ID.get(boss_id)
    if not boss:
        return NEUTRAL
    return affinity_for(boss.get("region", ""))


def region_affinities() -> list:
    """Every region with its element, in world order. For the map screen."""
    return [{"region": r["id"], "name": r["name"], "biome": r["biome"],
             "element": AFFINITY[r["id"]],
             # Everything the region's hard rooms can also be — see section H.
             # Listed on the map screen so a player can read the combination
             # before walking into it rather than after.
             "elements": list(REGION_AFFINITIES.get(r["id"],
                                                    (AFFINITY[r["id"]],))),
             "hazard": (hazard_for(r["id"]).id if hazard_for(r["id"]) else ""),
             "art": element_view(AFFINITY[r["id"]])}
            for r in world.REGIONS]


# ---------------------------------------------------------------------------
# E. Status effects
# ---------------------------------------------------------------------------
#
# Six, one per element, and no more — a seventh would be one the player stops
# reading. Each one has exactly one job, named in `kind`, and the allowed jobs
# are enumerated in `_STATUS_KINDS`. Nothing in that list can cost the victim a
# turn, and `self_check` proves it, because a status that skipped a turn would
# be a status that reduced how much Python got typed.
#
# Every status applies to MONSTERS exactly as it applies to the player. The
# functions below take a list of `StatusInstance` and do not ask whose it is.
#
# Damage-over-time is a PERCENTAGE OF MAXIMUM HEALTH, with a floor of one. The
# player's bar is twenty (config.STAMINA_MAX) and a bestiary enemy's is forty to
# sixty, so a flat number would be either trivial on one side or lethal on the
# other. A percentage is the same lesson at both scales.

_STATUS_KINDS = ("dot", "outgoing", "vulnerability", "armour", "regen")


@dataclass(frozen=True)
class Status:
    id: str
    name: str
    element: str
    kind: str            # one of _STATUS_KINDS
    turns: int           # duration in the VICTIM's turns
    potency: float       # dot: fraction of max health per tick
                         # outgoing/vulnerability: multiplier
                         # armour: fraction of armour points remaining
    max_stacks: int      # 1 means "refreshes, never deepens"
    curable: tuple       # cure kinds that clear it (see CURES)
    icon: str
    blurb: str           # what the player reads in the status bar
    why: str             # why it exists, for the codex


STATUSES: dict = {
    # Poison first, because the brief put it first and because it is the one
    # with a dedicated cure. Long, shallow, stacking, and the only status a
    # consumable exists specifically to remove.
    "POISONED": Status(
        "POISONED", "Poisoned", POISON, "dot", 4, 0.05, 2, ("ANTIDOTE", "FULL"),
        "drop",
        "Losing health at the start of each of your turns.",
        "Damage over time on top of the hit that delivered it. Four turns at five "
        "percent is a fifth of a bar if it runs its course, and a second stack "
        "doubles that — which is worth an antidote and is not worth panicking "
        "about. It stops at two stacks because a third would make a side effect "
        "into the main event, and the main event is the line you type."),
    "BURNING": Status(
        "BURNING", "Burning", FIRE, "dot", 2, 0.10, 1, ("SALVE", "FULL"), "flame",
        "Burning. Heavy damage, but it goes out.",
        "The same total as poison delivered in half the time, and it does not "
        "stack. Fire is a burst; poison is a debt. They should never feel alike."),
    "CHILLED": Status(
        "CHILLED", "Chilled", COLD, "outgoing", 3, 0.85, 1, ("SALVE", "FULL"),
        "frost",
        "Your blows land fifteen percent lighter.",
        "Cold makes the fight longer rather than more dangerous. On a monster "
        "that is mercy; on the player it is more typing, which is the trade this "
        "whole system is built to make."),
    "SHOCKED": Status(
        "SHOCKED", "Shocked", LIGHTNING, "vulnerability", 2, 1.25, 1,
        ("SALVE", "FULL"), "spark",
        "Taking twenty-five percent more from every hit.",
        "Lightning does not do the damage. It makes whatever comes next do more, "
        "which is why it is the element that rewards a plan."),
    "STAGGERED": Status(
        "STAGGERED", "Staggered", BRUTE, "armour", 2, 0.50, 1, ("SALVE", "FULL"),
        "crack",
        "Your armour points are halved.",
        "Brute force is the answer to plate, and this is where that is literally "
        "true: it does not care about resistances, it removes the flat mitigation "
        "instead. The counter to armour points is not a better element."),
    "VOIDED": Status(
        "VOIDED", "Voided", VOID, "regen", 3, 0.0, 1, ("SALVE", "FULL"), "hollow",
        "No focus returns while this lasts.",
        "It stops focus COMING BACK. It never stops focus being SPENT, because "
        "hints cost focus and a status that locked the hint tree would be a "
        "status that could strand a learner. Voided players can still ask for "
        "help; they just cannot afford to ask twice."),
}

STATUS_IDS: tuple = tuple(STATUSES)

# What each cure clears. The antidote is deliberately narrow — a cure-all would
# make the four other statuses decorative — and there is deliberately no cure
# that is free.
CURES: dict = {
    "ANTIDOTE": ("POISONED",),
    "SALVE": ("BURNING", "CHILLED", "SHOCKED", "STAGGERED", "VOIDED"),
    "FULL": tuple(STATUS_IDS),
}

# How likely an element is to leave its mark. Only on a hit that was not shrugged
# off: hitting fire with fire does not set anything alight.
INFLICT_CHANCE: dict = {
    "OPPOSED": 0.35,
    "SECONDARY": 0.30,
    "NEUTRAL": 0.20,
    "WEAK_INTO": 0.15,
    "SAME": 0.0,
}


def marks(kind: str) -> bool:
    """Can a hit of this matchup leave a mark at all?

    The one owner of "hitting fire with fire does not set anything alight".
    `resolve_damage` gets that rule for free out of INFLICT_CHANCE["SAME"] being
    zero, but an enemy's CHARGED attack applies its status from outside this
    module — engine's `_enemy_turn` reads `special["inflicts"]` — and that path
    was quietly exempt. A fire monster in a fire region therefore set a player
    holding fire on fire, which is the exact sentence the table above exists to
    forbid, and it did it for a fifth of the player's health bar a time.

    Taking a status from a shrug is also the thing that made the wrong element
    cost more than the documented ceiling: the shrug is supposed to be the
    consolation for standing in the wrong weather.
    """
    return INFLICT_CHANCE.get(kind, 0.0) > 0


@dataclass
class StatusInstance:
    """One status riding on one combatant. Mutable, because it counts down.

    Serialises to a flat dict for the save file; `from_dict` takes it back.
    """
    id: str
    turns: int
    stacks: int = 1

    def to_dict(self) -> dict:
        return {"id": self.id, "turns": self.turns, "stacks": self.stacks}

    @classmethod
    def from_dict(cls, d: dict) -> "StatusInstance":
        return cls(id=d["id"], turns=int(d.get("turns", 0)),
                   stacks=int(d.get("stacks", 1)))

    @property
    def spec(self) -> Status:
        return STATUSES[self.id]


def inflict(statuses: list, status_id: str) -> dict:
    """Put a status on a victim, in place. Returns what happened, for the log.

    Re-applying refreshes the duration always, and deepens the stack only where
    `max_stacks` allows. Poison is the only one that deepens, which keeps the
    status bar readable: everything else is on or off.
    """
    spec = STATUSES.get(status_id)
    if spec is None:
        return {"applied": False, "reason": "unknown status"}
    for live in statuses:
        if live.id == status_id:
            live.turns = spec.turns
            if live.stacks < spec.max_stacks:
                live.stacks += 1
                return {"applied": True, "status": status_id, "deepened": True,
                        "stacks": live.stacks,
                        "line": f"{spec.name} deepens ({live.stacks})."}
            return {"applied": True, "status": status_id, "refreshed": True,
                    "stacks": live.stacks, "line": f"{spec.name} is renewed."}
    statuses.append(StatusInstance(id=status_id, turns=spec.turns, stacks=1))
    return {"applied": True, "status": status_id, "new": True, "stacks": 1,
            "line": f"{spec.name}. {spec.blurb}"}


def tick_statuses(statuses: list, max_health: int) -> dict:
    """Advance every status by one of the VICTIM's turns.

    Call this at the START of a combatant's turn, before they act, so a player
    who is about to die of poison finds out while they still have a turn in which
    to drink something. Mutates `statuses` in place: expired entries are removed.

    Returns damage (already summed), the ids that expired, whether focus
    regeneration is suppressed this turn, and lines for the combat log.
    """
    damage = 0
    expired = []
    lines = []
    regen_blocked = False
    for live in list(statuses):
        spec = STATUSES.get(live.id)
        if spec is None:                      # a save from a build that had more
            statuses.remove(live)
            continue
        if spec.kind == "dot":
            tick = max(1, _round_half_up(max_health * spec.potency * live.stacks))
            damage += tick
            lines.append(f"{spec.name}: {tick}.")
        elif spec.kind == "regen":
            regen_blocked = True
        live.turns -= 1
        if live.turns <= 0:
            statuses.remove(live)
            expired.append(live.id)
            lines.append(f"{spec.name} fades.")
    return {"damage": damage, "expired": expired, "regen_blocked": regen_blocked,
            "lines": lines, "statuses": [s.to_dict() for s in statuses]}


def cure(statuses: list, kind: str = "ANTIDOTE") -> dict:
    """Clear what this cure clears, in place. The antidote's whole implementation.

    Works on monsters too, and it should: the brief says monsters can carry
    antidotes, and nothing here asks whose list this is.
    """
    clears = set(CURES.get(kind, ()))
    removed = [s.id for s in statuses if s.id in clears]
    statuses[:] = [s for s in statuses if s.id not in clears]
    if not removed:
        return {"cured": [], "line": "Nothing to clear.",
                "statuses": [s.to_dict() for s in statuses]}
    names = ", ".join(STATUSES[r].name for r in removed)
    return {"cured": removed, "line": f"{names} cleared.",
            "statuses": [s.to_dict() for s in statuses]}


def outgoing_scale(statuses: list) -> float:
    """How hard this combatant is currently able to hit, as a multiplier.

    This is CHILLED and nothing else today, but the caller should route all
    outgoing scaling through here so that a second such status never needs a
    second call site.
    """
    scale = 1.0
    for live in statuses or ():
        spec = STATUSES.get(live.id)
        if spec and spec.kind == "outgoing":
            scale *= spec.potency
    return scale


def _vulnerability(statuses) -> float:
    scale = 1.0
    for live in statuses or ():
        spec = STATUSES.get(getattr(live, "id", None))
        if spec and spec.kind == "vulnerability":
            scale *= spec.potency
    return scale


def _armour_scale(statuses) -> float:
    scale = 1.0
    for live in statuses or ():
        spec = STATUSES.get(getattr(live, "id", None))
        if spec and spec.kind == "armour":
            scale *= spec.potency
    return scale


# ---------------------------------------------------------------------------
# D. Armour: two jobs, and the choice between them
# ---------------------------------------------------------------------------
#
# The brief names them separately and they must stay separate, because choosing
# between them is the decision the player is being offered.
#
#   ARMOUR POINTS are FLAT. They subtract a fixed number from every hit
#   regardless of element. They are certainty: they work against things you did
#   not plan for. Their weakness is that they are capped as a FRACTION of the
#   incoming hit (`points_cap`), so heavy armour is the only kind whose points
#   still matter when something large lands — which is exactly the brief's "plate
#   reduces large hits" — and light armour's points quietly stop counting.
#
#   ELEMENTAL RESISTANCE is PROPORTIONAL. It removes a percentage, so it is worth
#   MORE the bigger the hit and worth NOTHING against an element you did not
#   guess. It is leverage: it pays out enormously when you read the area right
#   and not at all when you read it wrong.
#
# Flat mitigation against small hits you cannot predict, proportional mitigation
# against big hits you can. That is a real decision and it falls out of the
# arithmetic without a special case anywhere.
#
#   HEALTH AND FOCUS are the third road, the brief's cloaks and helms: no
#   mitigation at all, a bigger bar instead. It is the choice that makes the
#   fight last longer in the most literal way available, and it is strictly the
#   best one for a player who is here to type rather than to win efficiently.
#   That is not an accident.


@dataclass(frozen=True)
class ArmourProfile:
    """The defensive half of a loadout, collapsed into four numbers.

    `points` and `resist` are what `resolve_damage` reads. `bonus_health` and
    `bonus_focus` are what engine.py should fold into `stamina_max` / `mana_max`
    alongside the existing `items.EFFECT_LABELS` bonuses; they do not appear in
    the damage maths at all, which is the point of them being a different road.
    """
    points: int = 0
    resist: dict = field(default_factory=dict)   # element -> 0..1
    bonus_health: int = 0
    bonus_focus: int = 0
    points_cap: float = 0.50     # fraction of a hit flat points may remove
    kind: str = "NONE"

    def resist_to(self, element: str) -> float:
        return float(self.resist.get(element, 0.0)) if element in ELEMENTS else 0.0


# The three roads, as authored archetypes. Forge and loot tables should scale
# these by rarity rather than inventing fourth and fifth shapes.
ARMOUR_KINDS: dict = {
    "PLATE": {
        "name": "Plate", "points_cap": 0.50, "slots": ("chest", "head", "offhand"),
        "blurb": "Flat mitigation, and the only kind whose points still count "
                 "when something big lands.",
        "shape": {"points": 6, "resist": {}, "bonus_health": 0, "bonus_focus": 0},
    },
    "MAIL": {
        "name": "Mail", "points_cap": 0.25, "slots": ("chest", "hands", "feet"),
        "blurb": "Half the certainty, and it does not slow you down.",
        "shape": {"points": 4, "resist": {}, "bonus_health": 2, "bonus_focus": 0},
    },
    "WARDED": {
        "name": "Warded", "points_cap": 0.20, "slots": ("chest", "head", "offhand",
                                                        "ring1", "ring2", "trinket"),
        "blurb": "One element, heavily. Nothing against the other five.",
        "shape": {"points": 1, "resist": {}, "bonus_health": 0, "bonus_focus": 2},
    },
    "CLOAK": {
        "name": "Cloak", "points_cap": 0.0, "slots": ("chest", "head", "trinket"),
        "blurb": "No mitigation. A longer bar instead, which is the same thing "
                 "said more honestly.",
        "shape": {"points": 0, "resist": {}, "bonus_health": 6, "bonus_focus": 6},
    },
}

# A single piece may never resist more than this, and a whole loadout may never
# exceed RESIST_CAP. Without the second number a player in six warded pieces
# would take nothing at all in their chosen element, and an area that cannot
# hurt you is an area you stop reading.
PIECE_RESIST_CAP = 0.30
RESIST_CAP = 0.60

# The most that flat points may remove from any single hit, whatever the profile
# claims. Plate's own cap is 0.50 and this is the ceiling over all of them.
ARMOUR_POINT_CAP = 0.50


def armour_profile(kind: str = "PLATE", *, points: int | None = None,
                   element: str = "", resist: float = 0.0,
                   bonus_health: int = 0, bonus_focus: int = 0) -> ArmourProfile:
    """Build one piece from an archetype. Clamps, so a loot roll cannot cheat."""
    spec = ARMOUR_KINDS.get(kind, ARMOUR_KINDS["PLATE"])
    shape = spec["shape"]
    resists = {}
    if element in ELEMENTS and resist > 0:
        resists[element] = min(PIECE_RESIST_CAP, max(0.0, float(resist)))
    return ArmourProfile(
        points=max(0, int(shape["points"] if points is None else points)),
        resist=resists,
        bonus_health=int(shape["bonus_health"]) + int(bonus_health),
        bonus_focus=int(shape["bonus_focus"]) + int(bonus_focus),
        points_cap=min(ARMOUR_POINT_CAP, float(spec["points_cap"])),
        kind=kind if kind in ARMOUR_KINDS else "PLATE",
    )


def armour_from_effects(effects: dict | None) -> ArmourProfile:
    """Collapse a whole loadout's effect bag into one profile.

    `effects` is the flat dict engine.py already assembles from equipped gear
    (see `engine.Game.effects`). Three of these keys are NEW and must be added
    to `items.EFFECT_LABELS` before the player can ever see them in a tooltip —
    items.py owns that dict, not this module:

        armour_points        int, flat                         NEW
        armour_cap           float, the best points_cap worn    NEW
        resist_<ELEMENT>     float 0..1, e.g. resist_fire       NEW, six of them

    THE TWO BAR KEYS ARE NOT NEW AND MUST NOT BE REINVENTED. engine.py already
    folds gear into the bars, in `Game.effects`' caller, as:

        player["stamina_max"] = config.STAMINA_MAX + int(fx.get("stamina_max", 0))
        player["mana_max"]    = config.MANA_MAX    + int(fx.get("mana_max", 0))

    so `stamina_max` and `mana_max` are the live effect keys for the brief's
    cloaks and helms, they are already in `items.EFFECT_LABELS`, and gear
    already rolls them. An earlier draft of this function read `health_bonus`
    and `focus_bonus` instead, which no item in the game has ever set: the
    third road would have silently reported zero for every loadout while
    looking implemented. The old names are still accepted as aliases so a forge
    that has started emitting them is not punished, but the existing names win.

    Summing then clamping, rather than clamping each piece, is deliberate: two
    half-measures should beat one, but six should not beat three.
    """
    fx = effects or {}
    resist = {}
    for eid in ELEMENTS:
        value = float(fx.get(f"resist_{eid.lower()}", 0.0) or 0.0)
        if value:
            resist[eid] = min(RESIST_CAP, max(0.0, value))
    return ArmourProfile(
        points=max(0, int(fx.get("armour_points", 0) or 0)),
        resist=resist,
        bonus_health=int(fx.get(HEALTH_EFFECT_KEY, 0) or 0)
        + int(fx.get("health_bonus", 0) or 0),
        bonus_focus=int(fx.get(FOCUS_EFFECT_KEY, 0) or 0)
        + int(fx.get("focus_bonus", 0) or 0),
        points_cap=min(ARMOUR_POINT_CAP,
                       max(0.0, float(fx.get("armour_cap", ARMOUR_POINT_CAP)))),
        kind=str(fx.get("armour_kind", "PLATE")),
    )


NO_ARMOUR = ArmourProfile()


# ---------------------------------------------------------------------------
# C. The damage function
# ---------------------------------------------------------------------------
#
# One function. Everything — the player striking a monster, a monster striking
# the player, a boss, a pet's contribution — goes through it, because two damage
# functions is how two different games end up in one binary.
#
# ORDER OF OPERATIONS, and it matters:
#
#   1. base                      what the typed cast earned. Never generated here.
#   2. x matchup                 0.65 .. 1.50
#   3. x (1 - resist)            resist clamped to RESIST_CAP = 0.60
#   4. clamp to [0.50, 1.50]     MULT_FLOOR / MULT_CEIL
#   5. x outgoing (attacker)     CHILLED
#   6. x vulnerability (defender) SHOCKED
#   7. - armour points           capped at points_cap of the hit, and the cap is
#                                applied to the post-multiplier number so plate
#                                scales with the blow rather than trailing it
#   8. max(MIN_DAMAGE, half-up)  never zero, never negative. Half rounds UP —
#                                see `_round_half_up`, because banker's rounding
#                                would quietly break the guarantee below.
#
# THE FLOOR IS THE WHOLE ARGUMENT. Step 4 means the persistent elemental terms
# can never take a hit below half, whatever the player is wearing and whatever
# they brought. Step 7 means armour can never take it below half of what is left.
# So the worst persistent case is 0.25 of NEUTRAL damage.
#
# TWO STRETCH FIGURES, BECAUSE THERE ARE TWO HONEST QUESTIONS, and an earlier
# draft of this comment conflated them. The proof below measures both:
#
#   MAX_FIGHT_STRETCH            = 4.0   worst case vs a PLAIN, unelemented
#                                        fight. This is the "I brought nothing
#                                        and read nothing" tax.
#   MAX_FIGHT_STRETCH_VS_COUNTER = 6.0   worst case vs a player who actually
#                                        countered. This is the real spread
#                                        between the best and worst reading of
#                                        the same room, and it is the bigger
#                                        number, so it is the one a balance
#                                        conversation should quote.
#
# The measured figures are lower than both ceilings — 4.0 and 5.0 across the
# rows in `_prove_no_dead_end` — because integer damage rounds half UP and
# ceiling division on casts can only ever round in the player's favour.
#
# Six times is long. It is meant to be: it is what walking into the Complexity
# Tower in fire gear against a cold enemy in warded plate should feel like. It is
# also survivable without exception, because every single cast still lands for at
# least one point, so the fight terminates. And the realistic worst is nearer
# 2.4x, because bestiary enemies carry armour points in the low single digits
# against base damage in the high single digits.
#
# The two temporary terms (steps 5 and 6) can push momentarily past that — a
# chilled attacker's worst case is 0.2125 — but they expire on their own in two
# or three turns and cannot be stacked with themselves. The guarantee is stated
# over the persistent terms because those are the ones a player's choices set.

MIN_DAMAGE = 1
MULT_FLOOR = 0.50
MULT_CEIL = 1.50

# Exported so a test, a tooltip and a designer can all cite the same number.
WORST_CASE_MULTIPLIER = MULT_FLOOR * (1.0 - ARMOUR_POINT_CAP)   # 0.25
BEST_CASE_MULTIPLIER = MULT_CEIL                                 # 1.50
MAX_FIGHT_STRETCH = 1.0 / WORST_CASE_MULTIPLIER                  # 4.0, vs plain
MAX_FIGHT_STRETCH_VS_COUNTER = (BEST_CASE_MULTIPLIER
                                / WORST_CASE_MULTIPLIER)         # 6.0, vs a counter


@dataclass
class Defender:
    """Everything the damage function needs to know about whoever is being hit.

    Deliberately not an Enemy and not the player dict: both of those get adapted
    into this at the call site, which keeps this function testable without the
    rest of the game being loaded.
    """
    element: str = NEUTRAL
    armour: ArmourProfile = NO_ARMOUR
    statuses: list = field(default_factory=list)
    max_health: int = 0          # only used to size a status tick, not the hit
    # Everything it is, primary first. EMPTY means "just `element`", which is
    # what every existing caller passes and what every existing caller will keep
    # getting: section H is additive, and a Defender built the old way resolves
    # through exactly the arithmetic it resolved through before.
    elements: tuple = ()

    def affinities(self) -> tuple:
        """The chain the damage function actually reads."""
        if self.elements:
            return tuple(self.elements)
        return (self.element or NEUTRAL,)

    @classmethod
    def for_enemy(cls, enemy, region_id: str = "", *,
                  armour: ArmourProfile | None = None,
                  statuses: list | None = None,
                  difficulty: str = "", is_boss: bool = False) -> "Defender":
        # `difficulty` and `is_boss` are how many elements this thing gets to
        # be — see `affinity_count`. Both default to the shape of an ordinary
        # room, so a caller that has not been updated builds exactly the
        # single-element Defender it built before section H existed.
        # MAXIMUM health, not current. `max_health` sizes a damage-over-time
        # tick, and a DOT is documented as a percentage of the bar's FULL
        # length. Reading `hp` here would have made poison weaken as the enemy
        # weakened — a fifth of a bar at full health decaying to one point at
        # death's door — which is precisely backwards and would have been read
        # as poison "not working" on anything nearly dead.
        # `incantation.Enemy` carries both; `hp` is the fallback for a plain
        # dict that only has the one number.
        hp_max = getattr(enemy, "hp_max", None)
        hp = getattr(enemy, "hp", None)
        if isinstance(enemy, dict):
            hp_max = enemy.get("hp_max", hp_max)
            hp = enemy.get("hp", hp)
        chain = enemy_elements(enemy, region_id, difficulty=difficulty,
                               is_boss=is_boss)
        return cls(element=chain[0],
                   elements=chain,
                   armour=armour or NO_ARMOUR,
                   statuses=statuses if statuses is not None else [],
                   max_health=int(hp_max or hp or 0))

    @classmethod
    def for_player(cls, player: dict, effects: dict | None = None, *,
                   element: str = NEUTRAL, statuses: list | None = None,
                   build_sealed: bool = False) -> "Defender":
        """`build_sealed` is `finalexam.sealed(enc, "BUILD")`, passed in by the
        caller. When it is true the loadout is simply not read."""
        armour = NO_ARMOUR if build_sealed else armour_from_effects(effects)
        return cls(element=NEUTRAL if build_sealed else element, armour=armour,
                   statuses=statuses if statuses is not None else [],
                   max_health=int(player.get(f"{HEALTH_FIELD}_max", 0) or 0))


@dataclass
class DamageResult:
    """One resolved hit. Everything the log, the client and the FX need."""
    damage: int
    base: int
    multiplier: float          # the persistent elemental multiplier, post-clamp
    total_multiplier: float    # including statuses, pre-armour
    kind: str                  # OPPOSED | SECONDARY | WEAK_INTO | SAME | NEUTRAL
    attacker_element: str
    defender_element: str
    resisted: float            # fraction removed by elemental resistance
    armour_absorbed: int       # points actually subtracted
    inflicted: str             # status id, or ""
    floored: bool              # True when the guarantee, not the maths, set this
    line: str                  # one sentence for the combat log
    # Section H. Appended with defaults so nothing that builds a DamageResult
    # positionally had to change. `defender_element` above is still the primary,
    # which is what every existing reader of it meant.
    defender_elements: tuple = ()
    rows: tuple = ()           # the per-element breakdown, in weight order

    def to_dict(self) -> dict:
        return {"damage": self.damage, "base": self.base,
                "multiplier": round(self.multiplier, 3),
                "total_multiplier": round(self.total_multiplier, 3),
                "kind": self.kind, "label": MATCHUP_LABEL.get(self.kind, ""),
                "attacker_element": self.attacker_element,
                "defender_element": self.defender_element,
                "resisted": round(self.resisted, 3),
                "armour_absorbed": self.armour_absorbed,
                "inflicted": self.inflicted, "floored": self.floored,
                "defender_elements": list(self.defender_elements
                                          or (self.defender_element,)),
                "rows": [dict(r) for r in self.rows],
                "line": self.line}


def resolve_damage(base: int, attacker_element: str, defender: Defender, *,
                   attacker_statuses: list | None = None,
                   roll: float = 1.0,
                   build_sealed: bool = False,
                   can_inflict: bool = True) -> DamageResult:
    """Attacker element + defender element + armour + resistances -> damage.

    Pure. Given the same arguments it returns the same result; it mutates
    nothing, including `defender.statuses`. Applying the status it names is the
    caller's job, via `inflict`, so that a caller which wants to preview a swing
    can call this and throw the answer away.

    `base` is what the typed cast already earned — see
    `incantation._damage_for`. Pass zero for a wasted turn and zero comes back:
    this function cannot manufacture a hit, and that is the rule the rest of the
    game is built on.

    `roll` is a float in [0, 1), normally `random.random()`, kept as a parameter
    rather than drawn inside so this stays pure and testable. The default of 1.0
    means no status is ever inflicted, which is the right default for a preview.

    `build_sealed` is the caller's `finalexam.sealed(enc, "BUILD")` verdict.
    True strips the attacker's element and the defender's entire loadout, so the
    exam is fought on the typing and nothing else.
    """
    base = max(0, int(base))
    if base == 0:
        return DamageResult(0, 0, 1.0, 1.0, "NEUTRAL", NEUTRAL, NEUTRAL, 0.0, 0,
                            "", False, "Nothing lands.")

    atk = NEUTRAL if build_sealed else (attacker_element or NEUTRAL)
    armour = NO_ARMOUR if build_sealed else (defender.armour or NO_ARMOUR)

    # 2 + 3: the two persistent elemental terms. `matchup_multi` over a chain
    # of one returns exactly what `matchup` returns, so a single-element
    # defender resolves through the same arithmetic it always did.
    chain = (NEUTRAL,) if build_sealed else defender.affinities()
    dfn = chain[0]
    mult, kind, rows = matchup_multi(atk, chain)
    resist = min(RESIST_CAP, max(0.0, armour.resist_to(atk)))
    mult *= (1.0 - resist)

    # 4: the guarantee. Nothing a player wears and nothing a player forgot can
    # take a landed cast below half.
    floored = mult < MULT_FLOOR
    mult = min(MULT_CEIL, max(MULT_FLOOR, mult))

    # 5 + 6: the temporary terms.
    total = mult * outgoing_scale(attacker_statuses or []) \
        * _vulnerability(defender.statuses)

    raw = base * total

    # 7: flat mitigation, capped as a fraction of this particular hit, and
    # halved outright if somebody has staggered the defender.
    points = armour.points * _armour_scale(defender.statuses)
    ceiling = raw * min(ARMOUR_POINT_CAP, max(0.0, armour.points_cap))
    absorbed = min(points, ceiling)

    damage = max(MIN_DAMAGE, _round_half_up(raw - absorbed))

    # The status, if the roll says so. Never on a shrugged-off hit: hitting fire
    # with fire does not set anything alight.
    inflicted = ""
    if can_inflict and not build_sealed and atk in ELEMENTS:
        chance = INFLICT_CHANCE.get(kind, 0.0)
        if chance > 0 and roll < chance:
            inflicted = ELEMENTS[atk].status

    return DamageResult(
        damage=damage, base=base, multiplier=mult, total_multiplier=total,
        kind=kind, attacker_element=atk, defender_element=dfn,
        resisted=resist, armour_absorbed=_round_half_up(absorbed),
        inflicted=inflicted, floored=floored,
        line=_damage_line(damage, kind, resist, _round_half_up(absorbed),
                          inflicted, len(rows)),
        defender_elements=chain, rows=rows)


def _damage_line(damage: int, kind: str, resist: float, absorbed: int,
                 inflicted: str, affinities: int = 1) -> str:
    parts = [f"{damage}"]
    if kind == "OPPOSED":
        parts.append("a counter")
    elif kind == "SECONDARY":
        parts.append("an edge")
    elif kind == "SAME":
        parts.append("mostly shrugged off")
    elif kind == "WEAK_INTO":
        parts.append("blunted")
    if resist >= 0.10:
        parts.append(f"{int(resist * 100)}% warded")
    if absorbed:
        parts.append(f"{absorbed} stopped by plate")
    if affinities > 1:
        # Said every time, because the player has to be able to LEARN that this
        # one is two things without reading a wiki about which ones are.
        parts.append(f"it is {'two' if affinities == 2 else 'three'} things")
    if inflicted:
        parts.append(STATUSES[inflicted].name.lower())
    return ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# F. Boots, and the hazards they answer
# ---------------------------------------------------------------------------
#
# The brief is specific about boots: movement speed, and immunity to the hazard
# of an area — ice that slips, ground that burns, a dark that needs lighting.
# The hazards are modelled here. Whether the overworld actually slides the
# player's sprite is somebody else's wiring; what this module owes them is a
# single function that answers "what does this step cost" and a table they can
# render from.
#
# Every hazard is MILD. A hazard that could kill would be a hazard that stopped
# a player exploring an area they were under-equipped for, and this game does not
# have areas you are not allowed into — it has areas that cost more.


@dataclass(frozen=True)
class Hazard:
    id: str
    name: str
    element: str
    status: str          # what a failed step inflicts, "" for none
    speed: float         # multiplier on movement while unprotected
    chance: float        # per-step probability of the consequence landing
    boots_tag: str       # the boots property that answers it
    blurb: str


HAZARDS: dict = {
    "ICE": Hazard("ICE", "Black ice", COLD, "", 0.75, 0.25, "sure_footed",
                  "The ground takes your step somewhere you did not aim it."),
    "EMBER": Hazard("EMBER", "Ember ground", FIRE, "BURNING", 1.0, 0.20, "insulated",
                    "The floor is hotter than the boots you are standing in."),
    "DARK": Hazard("DARK", "Unlit", VOID, "", 0.70, 0.0, "lit",
                   "You can see one tile. The map fills in behind you and not "
                   "in front."),
    "SPORE": Hazard("SPORE", "Spore air", POISON, "POISONED", 1.0, 0.15, "sealed_sole",
                    "Every step lifts a little more of it off the ground."),
    "STATIC": Hazard("STATIC", "Charged air", LIGHTNING, "SHOCKED", 1.0, 0.15,
                     "earthed",
                     "Your own gear is the tallest metal on the plateau."),
    "RUBBLE": Hazard("RUBBLE", "Loose rubble", BRUTE, "", 0.80, 0.0, "shod",
                     "Nothing here is dangerous. All of it is slow."),
}

# One hazard per element, so the hazard follows from the area's affinity rather
# than being a second thing to author per region. Neutral areas have none, which
# is most of what makes them read as safe.
HAZARD_BY_ELEMENT: dict = {h.element: h.id for h in HAZARDS.values()}


@dataclass(frozen=True)
class Boots:
    id: str
    name: str
    element: str         # the area these belong to, NEUTRAL for the plain pair
    speed: float         # overworld movement multiplier. 1.0 is barefoot-normal.
    immunities: tuple    # hazard boots_tags answered
    bonus_health: int = 0
    bonus_focus: int = 0
    blurb: str = ""


BOOTS: tuple = (
    Boots("worn_boots", "Worn Boots", NEUTRAL, 1.00, (), 0, 0,
          "They are boots. That is the entire claim."),
    Boots("marching_boots", "Marching Boots", NEUTRAL, 1.15, ("shod",), 2, 0,
          "Cut for long roads and loose ground, and nothing else."),
    Boots("crampons", "Iron Crampons", COLD, 1.05, ("sure_footed",), 0, 0,
          "You will still be cold. You will be cold where you meant to stand."),
    Boots("cinder_greaves", "Cinder Greaves", FIRE, 1.05, ("insulated",), 3, 0,
          "Soled in something that was already burnt once."),
    Boots("lanternshoes", "Lantern Shoes", VOID, 1.00, ("lit",), 0, 3,
          "A light at the ankle, which is the wrong height for reading and the "
          "right height for not falling."),
    Boots("marsh_waders", "Marsh Waders", POISON, 0.95, ("sealed_sole",), 4, 0,
          "Sealed to the knee. Slow, and you keep your own blood."),
    Boots("earthed_sabatons", "Earthed Sabatons", LIGHTNING, 1.00, ("earthed",), 0, 2,
          "A braided tail that drags. It is not decorative."),
    Boots("wayfarers", "Wayfarer's Boots", NEUTRAL, 1.25,
          ("shod", "sure_footed"), 2, 2,
          "Quiet on stone, and they have been on every kind of it."),
)

BOOTS_BY_ID: dict = {b.id: b for b in BOOTS}


def hazard_for(region_id: str) -> Hazard | None:
    """The hazard of a place, derived from its affinity. Neutral areas: None."""
    element = affinity_for(region_id)
    hid = HAZARD_BY_ELEMENT.get(element)
    return HAZARDS.get(hid) if hid else None


def hazard_step(region_id: str, boots_id: str = "", *, roll: float = 1.0) -> dict:
    """What one step across this region costs.

    Pure, like `resolve_damage`, and for the same reason: `roll` comes in rather
    than being drawn here. `speed` is a multiplier the overworld applies to its
    own movement rate; `status` is a status id the caller should `inflict`.
    """
    hazard = hazard_for(region_id)
    boots = BOOTS_BY_ID.get(boots_id)
    speed = boots.speed if boots else 1.0
    if hazard is None:
        return {"hazard": "", "protected": True, "speed": speed, "status": "",
                "line": ""}
    protected = bool(boots and hazard.boots_tag in boots.immunities)
    if not protected:
        speed *= hazard.speed
    status = ""
    if not protected and hazard.status and roll < hazard.chance:
        status = hazard.status
    return {"hazard": hazard.id, "name": hazard.name, "element": hazard.element,
            "protected": protected, "speed": round(speed, 3), "status": status,
            "line": "" if protected else hazard.blurb}


# ---------------------------------------------------------------------------
# G. Pets belong to areas
# ---------------------------------------------------------------------------
#
# Keyed on the SPECIES string rather than the pet id, because pets.py is being
# rewritten as this is written and the ids will move before the animals do. An
# animal nobody placed is NEUTRAL, which is a real answer rather than a gap.
#
# This module does not import pets. It would be a hard dependency on a file in
# flux, for a dict of twelve strings.
PET_ELEMENT: dict = {
    # The brief named these two, and they set the rule for the rest:
    "penguin": COLD,          # PIVOT, and the only animal here built for ice
    "jaguar": POISON,         # ROSETTE, out of the rainforest, same as the marsh

    "boar": BRUTE,            # STUB and BARROW. It charges in a straight line and
                              # has never once considered an alternative.
    "python": VOID,           # IDIOM. The namesake, and the same animal as the
                              # thing waiting under the castle in the void.
    "llama": COLD,            # PLAIN. A high, cold plateau animal, and PLAIN is
                              # what you wear above the snow line.
    "axolotl": FIRE,          # PATCH. A salamander, and the salamander has lived
                              # in the flame since the oldest bestiaries. It also
                              # regrows what it loses, which is why the repair
                              # animal belongs in the Armorer's forge.
    "velociraptor": LIGHTNING,  # SICKLE. One strike, arriving before the thought
                                # of it. Lightning is the element of suddenness
                                # here, not of weather.
    "nautilus": VOID,         # CHAMBER. Deep, dark, and built as a spiral of
                              # smaller copies of itself.
    "crow": LIGHTNING,        # WITNESS. Storm bird. It sits on the tallest metal
                              # in the wastes and watches what happens next.
    "tortoise": BRUTE,        # HALT. A shell is armour points with legs.
    "mimic octopus": POISON,  # MIMIC. Poisonous by imitation, which is the only
                              # way it has ever done anything.
}


def pet_element(species: str = "", pet_id: str = "") -> str:
    """The element of a companion. Species first, id second, NEUTRAL last.

    Unknown animals are neutral on purpose: a companion whose element had to be
    guessed would be a companion the wheel lied about.
    """
    key = (species or "").strip().lower()
    if key in PET_ELEMENT:
        return PET_ELEMENT[key]
    key = (pet_id or "").strip().lower()
    if key in PET_ELEMENT:
        return PET_ELEMENT[key]
    return NEUTRAL


def pet_home(species: str = "", pet_id: str = "") -> list:
    """Which regions a companion is at home in. For the codex entry, and for
    whoever decides where an animal is found."""
    element = pet_element(species, pet_id)
    if element == NEUTRAL:
        return []
    return [rid for rid, e in AFFINITY.items() if e == element]


# ---------------------------------------------------------------------------
# H. Monsters that are more than one thing
# ---------------------------------------------------------------------------
#
# Everything above this line assumes a defender is one element. Later enemies
# are not. A thing in the Null King's castle is void AND cold, and the point of
# saying so is that no single weapon answers it: the player has to counter one
# half with what they swing and ward the other half with what they wear.
#
# THE FOUR RULES THIS MODEL IS BUILT ON, IN THE ORDER THEY MATTER
#
# 1. A DEFENDER'S AFFINITIES ARE NEVER AN OPPOSED PAIR. Nothing is ever both
#    fire and cold. A monster that was both halves of a pair would be a monster
#    where every counter is also a shrug, which is not a puzzle, it is a coin
#    that always lands on its edge. `_prove_multi_affinity` asserts it over the
#    whole table, so a region cannot acquire a contradictory second element by
#    someone editing a line.
#
# 2. THE MULTIPLIER IS A WEIGHTED MEAN, weights 2-1-1, primary first. A mean of
#    numbers drawn from [0.65, 1.50] is itself in [0.65, 1.50], so EVERY floor
#    and ceiling proven for the single-element case survives unchanged and
#    WORST_CASE_MULTIPLIER is still 0.25. That is the whole reason it is a mean
#    and not a product: a product of two matchups would reach 0.42 and 2.25 and
#    would have broken the one guarantee this module makes.
#
# 3. COUNTERING MORE OF IT IS ALWAYS BETTER. A mean is monotone in each term,
#    so there is never a case where reading the enemy correctly makes the fight
#    longer. `_prove_multi_affinity` measures that too.
#
# 4. THE PRIMARY IS WHAT IT SWINGS WITH. Weighting it double gives the player
#    something to aim at — counter the primary for the large reward, the
#    secondary for the smaller one — and it means the element the monster hits
#    you with is also the element it is most defended against, which is the
#    sentence that makes "a weapon of one element, armour of another" the
#    natural build rather than a puzzle solution somebody had to be told.
#
# WHAT A SECOND AFFINITY IS WORTH, IN NUMBERS
#
#   defender FIRE only          attacker COLD   1.500   attacker FIRE  0.650
#   defender FIRE + BRUTE       attacker COLD   1.333   attacker FIRE  0.767
#                               attacker POISON 1.167
#
# So a dual enemy compresses the wheel toward the middle: the best available
# reading pays 1.333 instead of 1.500 and the worst costs 0.767 instead of
# 0.650. It is deliberately a SMALLER spread per weapon, because the spread the
# player is supposed to chase is now across TWO pieces of gear rather than one,
# and the armour half of it is unchanged — warding the element it strikes with
# is still worth the full RESIST_CAP.

MAX_AFFINITIES = 3

# Primary, secondary, tertiary. Not a curve, a statement about attention: the
# thing it mostly is, the thing it also is, and the thing that is only true in
# the deepest room of the deepest region.
MULTI_WEIGHTS: tuple = (2, 1, 1)

# The extra elements a region's inhabitants pick up when the room is hard
# enough to have earned them. Authored per region rather than derived, because
# a second affinity is a statement about a place that its biome does not
# already contain — the Mines are hot because they are a mine, and they are
# heavy because of what happened in the third gallery, and only one of those is
# in `world.REGIONS`.
#
# NEUTRAL REGIONS NEVER GAIN ONE. Five regions are weatherless on purpose, and
# the Coliseum says in its own description that it is a sand floor, a clock and
# no hints. Giving its enemies two elements at ELITE would be this section
# contradicting section B to make a late region feel late. They stay plain, and
# three of the last six regions being plain is a mercy rather than an omission.
EXTRA_AFFINITY: dict = {
    "hashmap_highlands": (BRUTE,),
    # Lightning because it is the tallest metal for a day's walk; brute because
    # the vaults are stone plates and the thing guarding them is a plate.
    "stringwood_labyrinth": (COLD,),
    # Poison from the spores. Cold because the canopy closes over the groves and
    # nothing down there has been in the sun since the looms were built.
    "array_caverns": (COLD,),
    # Brute is the weight above you. Cold is the depth: the Hydra's hall has
    # never thawed and the water coming off it has been underground for years.
    "sliding_window_marsh": (COLD,),
    # Standing water and gas, and then the temperature standing water reaches
    # at night out past the frame.
    "twin_pointer_pass": (LIGHTNING,),
    # Snow line, and two lanterns held up above the cloud in a storm.
    "stack_queue_mines": (BRUTE,),
    # Ember ground, and then the seam that gave way in the wrong order.
    "matrix_citadel": (LIGHTNING,),
    # A floor plan that is a golem is a floor plan wired through its own plates.
    "recursive_forest": (POISON,),
    # Void at the centre, where the copies stop returning; poison on the way in,
    # because the innermost clearings of the Stringwood and this are the same
    # rainforest at two depths.
    "graph_wastes": (POISON,),
    # Lightning off the lattice. Poison because the Necromancer's answer to a
    # broken road is to stand the road back up, and the things that walk it have
    # been in the ground since the roads were whole.
    "debugging_dungeon": (VOID,),
    # The Armorer's forge, and then the cells: plate that was sound the day
    # before and is not sound now. A defect is a thing that used to be there,
    # which is the nearest the wheel comes to an absence with a cause.
    "complexity_tower": (VOID, BRUTE),
    # Cold all the way up. Void from the eighth landing, where the floors stop
    # being labelled. Brute at the top, which is what every floor costing twice
    # the floor below eventually amounts to.
    "null_kings_castle": (COLD, BRUTE),
    # Void, because nothing is labelled. Cold, because nothing is lit. Brute,
    # because the Examiner has never once cared what you were wearing.
}


def _affinity_chain(region_id: str) -> tuple:
    """Primary first, then whatever else that region is, deduplicated."""
    primary = affinity_for(region_id)
    if primary == NEUTRAL:
        return (NEUTRAL,)
    chain = [primary]
    for extra in EXTRA_AFFINITY.get(region_id, ()):
        if extra in ELEMENTS and extra not in chain:
            chain.append(extra)
    return tuple(chain[:MAX_AFFINITIES])


REGION_AFFINITIES: dict = {r["id"]: _affinity_chain(r["id"])
                           for r in world.REGIONS}

# Which rung of `curriculum.TIERS` wakes each extra element. Gating on
# DIFFICULTY rather than on region index is not laziness about "later": the
# dungeon plan already makes later rooms harder, so a rule that reads the room's
# own difficulty reads lateness for free and stays correct if somebody retunes a
# chapter. It also means a player who goes looking for a hard fight in an early
# region gets the hard fight they asked for.
#
# Named as strings rather than indices so the table is readable next to
# `curriculum.TIERS`, and resolved through `_depth` so an unknown difficulty
# falls back exactly the way the rest of the game falls back.
SECOND_AFFINITY_AT = "HARD"
THIRD_AFFINITY_AT = "ELITE"

# A third element is for bosses only, on top of the depth requirement. Two
# regions in the game even have one to give, and a third affinity on an ordinary
# room would be three things to read in a fight the player is passing through.
THIRD_AFFINITY_NEEDS_BOSS = True

_DIFFICULTY_LADDER = ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE",
                      "BOSS")


def _depth(difficulty: str) -> int:
    """Where a difficulty sits on the ladder. Unknown reads as EASY, which is
    `curriculum.tier_index`'s own fallback, reproduced rather than imported so
    this module keeps its single dependency."""
    try:
        return _DIFFICULTY_LADDER.index(difficulty)
    except ValueError:
        return _DIFFICULTY_LADDER.index("EASY")


def affinity_count(difficulty: str = "", *, is_boss: bool = False) -> int:
    """How many elements an encounter of this depth is allowed to carry."""
    depth = _depth(difficulty)
    if is_boss:
        depth = max(depth, _depth("ELITE"))
    count = 1
    if depth >= _depth(SECOND_AFFINITY_AT):
        count = 2
    if depth >= _depth(THIRD_AFFINITY_AT) and (is_boss or
                                               not THIRD_AFFINITY_NEEDS_BOSS):
        count = 3
    return min(MAX_AFFINITIES, count)


def affinities_for(region_id: str, *, difficulty: str = "",
                   is_boss: bool = False) -> tuple:
    """Every element a thing standing on this ground fights with and defends
    with, primary first.

    Always at least one entry, and for a neutral region exactly one, which is
    NEUTRAL. Never longer than the region has elements to give: asking the
    Fields of Syntax for a boss's three affinities returns the one it has.
    """
    chain = REGION_AFFINITIES.get(region_id, (NEUTRAL,))
    return chain[:affinity_count(difficulty, is_boss=is_boss)] or (NEUTRAL,)


def enemy_elements(enemy, region_id: str = "", *, difficulty: str = "",
                   is_boss: bool = False) -> tuple:
    """What a monster is, as a tuple. The multi-affinity `enemy_element`.

    An entry that names its own `elements` wins outright, an entry that names a
    single `element` wins as a one-tuple, and everything else takes the ground
    it is standing on — exactly the precedence `enemy_element` already uses, so
    the bestiary can adopt this one field at a time.
    """
    own = None
    single = None
    if enemy is not None:
        if isinstance(enemy, dict):
            own = enemy.get("elements")
            single = enemy.get("element")
        else:
            own = getattr(enemy, "elements", None)
            single = getattr(enemy, "element", None)
    if own:
        # Filtered here rather than trusted, because a bestiary entry is data and
        # data is where a FIRE/COLD monster eventually gets typed by hand. An
        # element that opposes one already in the chain is DROPPED, so rule one
        # of section H — no defender is ever both halves of a pair — is true of
        # anything the bestiary hands in and not only of the table above.
        seen = []
        for element in own:
            if element not in ELEMENTS and element != NEUTRAL:
                continue
            if element in seen:
                continue
            if any(OPPOSED.get(element) == other for other in seen):
                continue
            seen.append(element)
        if seen:
            return tuple(seen[:MAX_AFFINITIES])
    if single in ELEMENTS or single == NEUTRAL:
        return (single,)
    return affinities_for(region_id, difficulty=difficulty, is_boss=is_boss)


def matchup_multi(attacker: str, defenders) -> tuple:
    """`(multiplier, kind, rows)` for one element striking several at once.

    The multiplier is the weighted mean described at the top of this section.
    `kind` is the BEST matchup the attacker has among the defender's elements,
    which is both the label the combat log should show and the kind
    `INFLICT_CHANCE` is read with — one meaning, used twice. For a defender with
    one element this function returns exactly what `matchup` returns, which is
    why `resolve_damage` can route everything through it.

    `rows` is the breakdown, in weight order, and it is the entire answer to
    "how is the player supposed to SEE this": a combination puzzle you cannot
    inspect is just losing. `threat_view` renders it.
    """
    order = []
    for element in (defenders or ()):
        element = element if element in ELEMENTS else NEUTRAL
        if element not in order:
            order.append(element)
    if not order:
        order = [NEUTRAL]
    order = order[:MAX_AFFINITIES]

    rows = []
    weighted = 0.0
    weight_total = 0
    best_mult = None
    best_kind = "NEUTRAL"
    for index, element in enumerate(order):
        weight = MULTI_WEIGHTS[min(index, len(MULTI_WEIGHTS) - 1)]
        mult, kind = matchup(attacker, element)
        rows.append({"element": element, "weight": weight,
                     "multiplier": mult, "kind": kind,
                     "label": MATCHUP_LABEL.get(kind, ""),
                     "primary": index == 0})
        weighted += mult * weight
        weight_total += weight
        if best_mult is None or mult > best_mult:
            best_mult, best_kind = mult, kind
    return weighted / weight_total, best_kind, tuple(rows)


def strike_element(affinities, special_element: str = "") -> str:
    """What a multi-affinity monster actually hits you with.

    Its PRIMARY, unless it is spending focus on a special that belongs to one of
    its other elements — `bestiary.SPECIALS` is already one special per element,
    so a dual enemy with two specials alternates between two elements of
    incoming damage and one warded chest piece only answers half of it. That is
    the armour half of the combination, and it is the reason the primary is
    weighted double on defence: the element it is hardest to hurt through is the
    element it hits you with most.
    """
    chain = tuple(affinities or ()) or (NEUTRAL,)
    if special_element in ELEMENTS and special_element in chain:
        return special_element
    return chain[0]


def threat_view(affinities, *, attacker_element: str = "",
                armour: "ArmourProfile | None" = None,
                revealed: bool = True) -> dict:
    """What the client draws above a monster's head, and the only reason the
    combination puzzle is fair.

    `revealed` is the caller's `not finalexam.sealed(enc, "WEAKNESS_MAP")`, the
    same verdict `element_view` takes and formed in the same one place. Sealed,
    the enemy still has every element it had and every multiplier still applies;
    the player is simply not told which, and `count` is withheld too, because
    "it is two things but you may not know which two" is a crutch wearing a
    blindfold.

    Unsealed, every number in the fight is on the screen: each element, what
    your weapon does into it, what your armour does about it, and the weight
    each one carries in the mean. Nothing here is a Python answer and nothing
    here moves mastery. It is a legend for a wheel the player can already see.
    """
    chain = tuple(affinities or ()) or (NEUTRAL,)
    mult, kind, rows = matchup_multi(attacker_element or NEUTRAL, chain)
    if not revealed:
        return {"revealed": False, "count": 0, "rows": [],
                "multiplier": round(mult, 3), "kind": "",
                "label": "", "strikes_with": "",
                "line": "Nothing about this one is labelled.",
                "advice": []}
    out_rows = []
    for row in rows:
        warded = float(armour.resist_to(row["element"])) if armour else 0.0
        out_rows.append({
            **row,
            "art": element_view(row["element"]),
            "warded": round(warded, 3),
            "warded_text": (f"{int(warded * 100)}% warded"
                            if warded else "unwarded"),
        })
    return {
        "revealed": True,
        "count": len(out_rows),
        "rows": out_rows,
        "multiplier": round(mult, 3),
        "kind": kind,
        "label": MATCHUP_LABEL.get(kind, ""),
        "weights": list(MULTI_WEIGHTS[:len(out_rows)]),
        "strikes_with": strike_element(chain),
        "line": _threat_line(out_rows, mult),
        "advice": combination_advice(chain, attacker_element=attacker_element,
                                     armour=armour),
    }


def _threat_line(rows: list, mult: float) -> str:
    names = [ALL_AFFINITIES[r["element"]].name for r in rows]
    if len(names) == 1:
        head = names[0]
    else:
        head = ", ".join(names[:-1]) + " and " + names[-1]
    return f"{head}. Your blows land at {round(mult, 2)}x."


def combination_advice(affinities, *, attacker_element: str = "",
                       armour: "ArmourProfile | None" = None) -> list:
    """One sentence per thing the player could do about this, in plain words.

    It names ELEMENTS. It never names a pattern, an approach or a line of
    Python, because the wheel is not the lesson and the typing is. Telling
    somebody that void gear would help here is the same category of statement as
    the map screen already makes about the region they are standing in.
    """
    # Normalised through the same path the damage function uses, so an unknown
    # string advises the same way it resolves rather than advising not at all.
    _, _, rows = matchup_multi(attacker_element or NEUTRAL, affinities or ())
    chain = tuple(row["element"] for row in rows)
    if set(chain) <= {NEUTRAL}:
        return ["Neutral ground. Nothing here answers to an element, which is "
                "what makes it the fight you measure the others against."]
    out = []
    counters = [ALL_AFFINITIES[OPPOSED[r["element"]]].name for r in rows
                if r["element"] in ELEMENTS]
    struck = [r for r in rows if r["kind"] == "OPPOSED"]
    shrugged = [r for r in rows if r["kind"] == "SAME"]
    if struck:
        out.append(f"You already counter its "
                   f"{ALL_AFFINITIES[struck[0]['element']].name.lower()} half.")
    elif counters and len(chain) == 1:
        out.append(f"A {counters[0].lower()} weapon counters it outright.")
    elif counters:
        out.append(f"A {counters[0].lower()} weapon answers the half of it that "
                   f"matters most. There is no weapon that answers all of it.")
    if shrugged:
        out.append(f"It shrugs off "
                   f"{ALL_AFFINITIES[shrugged[0]['element']].name.lower()}. "
                   f"Anything else is better than what you are holding.")
    hits_with = strike_element(chain)
    if hits_with in ELEMENTS:
        warded = float(armour.resist_to(hits_with)) if armour else 0.0
        name = ALL_AFFINITIES[hits_with].name.lower()
        if warded >= 0.10:
            out.append(f"It strikes with {name}, and you are warded against "
                       f"{name} by {int(warded * 100)} percent.")
        else:
            out.append(f"It strikes with {name} and you have nothing warded "
                       f"against {name}.")
    if len(chain) > 1:
        word = "Two" if len(chain) == 2 else "Three"
        out.append(f"{word} things at once. One weapon cannot counter all of "
                   f"it, so the rest is answered by what you are wearing.")
    return out


# ---------------------------------------------------------------------------
# The proofs
# ---------------------------------------------------------------------------

def _prove_no_dead_end() -> dict:
    """The rule that keeps the game learnable, with numbers.

    A player with the worst possible element, the worst possible gear and no
    potions, against the most armoured thing the wheel allows, must still win by
    typing correct Python. Not eventually. Provably, in a bounded number of
    casts, and the bound is `MAX_FIGHT_STRETCH`.

    Three things are measured, because they say different things:

      * the DAMAGE RATIO, worst hit over plain hit, which is the invariant the
        floors in `resolve_damage` actually guarantee;
      * the CAST STRETCH vs PLAIN, how many more times the player has to type
        the idiom than in an unelemented fight, bounded by MAX_FIGHT_STRETCH;
        and
      * the CAST STRETCH vs a COUNTER, the same against a player who read the
        room correctly, bounded by MAX_FIGHT_STRETCH_VS_COUNTER. This is the
        larger and more honest number, and it is measured rather than asserted
        because an earlier version of this proof computed `best` and then
        quietly compared against `plain` instead — which made the docstring's
        "four times" claim true of a sentence nobody was making.

    Integer rounding can only ever move either stretch in the player's favour,
    since half rounds up and casts are a ceiling division.
    """
    # Everything wrong at once: same element, the cap on elemental warding, the
    # cap on flat points, and enough points to hit that cap several times over.
    worst_armour = ArmourProfile(points=9999, resist={FIRE: RESIST_CAP},
                                 points_cap=ARMOUR_POINT_CAP, kind="PLATE")

    rows = []
    worst_ratio = 1.0
    worst_stretch = 1.0
    worst_stretch_vs_counter = 1.0
    for base, enemy_hp in ((6, 40), (10, 50), (14, 56), (22, 120), (40, 200)):
        plain = resolve_damage(base, NEUTRAL, Defender(element=NEUTRAL)).damage
        best = resolve_damage(base, COLD, Defender(element=FIRE)).damage
        worst = resolve_damage(base, FIRE,
                               Defender(element=FIRE, armour=worst_armour)).damage
        chilled = resolve_damage(
            base, FIRE, Defender(element=FIRE, armour=worst_armour),
            attacker_statuses=[StatusInstance("CHILLED", 3)]).damage

        def casts(hit):
            return -(-enemy_hp // max(1, hit))       # ceiling division

        ratio = worst / plain
        stretch = casts(worst) / casts(plain)
        stretch_vs_counter = casts(worst) / casts(best)
        worst_ratio = min(worst_ratio, ratio)
        worst_stretch = max(worst_stretch, stretch)
        worst_stretch_vs_counter = max(worst_stretch_vs_counter,
                                       stretch_vs_counter)
        rows.append({
            "base": base, "enemy_hp": enemy_hp,
            "best_hit": best, "best_casts": casts(best),
            "plain_hit": plain, "plain_casts": casts(plain),
            "worst_hit": worst, "worst_casts": casts(worst),
            "chilled_worst_hit": chilled, "chilled_worst_casts": casts(chilled),
            "damage_ratio": round(ratio, 3),
            "cast_stretch": round(stretch, 2),
            "cast_stretch_vs_counter": round(stretch_vs_counter, 2),
            "lands": worst >= MIN_DAMAGE and chilled >= MIN_DAMAGE,
        })

    return {
        "rows": rows,
        "worst_damage_ratio": round(worst_ratio, 3),
        "guaranteed_damage_ratio": WORST_CASE_MULTIPLIER,
        "worst_cast_stretch": round(worst_stretch, 2),
        "declared_max_stretch": MAX_FIGHT_STRETCH,
        "worst_cast_stretch_vs_counter": round(worst_stretch_vs_counter, 2),
        "declared_max_stretch_vs_counter": MAX_FIGHT_STRETCH_VS_COUNTER,
        "every_worst_case_still_lands": all(r["lands"] for r in rows),
        "ratio_holds": worst_ratio >= WORST_CASE_MULTIPLIER - 1e-9,
        "stretch_within_declared": worst_stretch <= MAX_FIGHT_STRETCH + 1e-9,
        "stretch_vs_counter_within_declared":
            worst_stretch_vs_counter <= MAX_FIGHT_STRETCH_VS_COUNTER + 1e-9,
        "winnable_without_potions": all(r["worst_hit"] >= MIN_DAMAGE
                                        for r in rows),
        "reading": ("Everything wrong at once costs at most four times the "
                    "typing of a plain fight, and at most six times the typing "
                    "of a fight you actually read. Nothing about it is "
                    "unwinnable, and one gear swap undoes most of it."),
    }


def _prove_monotonic_in_armour() -> dict:
    """Damage never rises as armour rises, never goes negative, never hits zero."""
    defender = Defender(element=NEUTRAL, armour=NO_ARMOUR)
    last = None
    monotonic = True
    positive = True
    for points in range(0, 201):
        defender.armour = ArmourProfile(points=points, points_cap=ARMOUR_POINT_CAP)
        d = resolve_damage(40, LIGHTNING, defender).damage
        if last is not None and d > last:
            monotonic = False
        if d < MIN_DAMAGE:
            positive = False
        last = d
    # And across every matchup, at three base sizes, for the same two properties.
    for a in list(ELEMENTS) + [NEUTRAL]:
        for b in list(ELEMENTS) + [NEUTRAL]:
            for base in (1, 9, 120):
                prev = None
                for points in (0, 3, 25, 400):
                    dfn = Defender(element=b,
                                   armour=ArmourProfile(points=points,
                                                        points_cap=ARMOUR_POINT_CAP))
                    d = resolve_damage(base, a, dfn).damage
                    if d < MIN_DAMAGE:
                        positive = False
                    if prev is not None and d > prev:
                        monotonic = False
                    prev = d
    return {"monotonic_in_armour": monotonic, "always_positive": positive,
            "floor": MIN_DAMAGE, "armour_sweep": 201}


def _prove_typing_still_rules() -> dict:
    """No element, status or armour can produce damage from a wasted turn, and
    no status can cost the victim their turn."""
    zero = [resolve_damage(0, a, Defender(element=b)).damage
            for a in list(ELEMENTS) + [NEUTRAL]
            for b in list(ELEMENTS) + [NEUTRAL]]
    bad_kinds = [s.id for s in STATUSES.values() if s.kind not in _STATUS_KINDS]
    return {"zero_base_gives_zero": not any(zero),
            "status_kinds": sorted({s.kind for s in STATUSES.values()}),
            "no_turn_skipping_status": not bad_kinds,
            "illegal_status_kinds": bad_kinds}


def _legal_chains() -> list:
    """Every affinity chain this module can actually produce, plus every chain
    the bestiary could legally hand it.

    The second half matters: `enemy_elements` lets an entry override the region,
    so the proofs below have to hold for any non-opposed combination somebody
    types into bestiary.py, not only for the twelve in `EXTRA_AFFINITY`.
    """
    chains = {tuple(chain) for chain in REGION_AFFINITIES.values()}
    chains |= {(e,) for e in list(ELEMENTS) + [NEUTRAL]}
    for a in ELEMENTS:
        for b in ELEMENTS:
            if b == a or OPPOSED[a] == b:
                continue
            chains.add((a, b))
            for c in ELEMENTS:
                if c in (a, b) or OPPOSED[a] == c or OPPOSED[b] == c:
                    continue
                chains.add((a, b, c))
    return sorted(chains)


def _prove_multi_affinity() -> dict:
    """Re-proving the floor for defenders that are more than one thing.

    The single-element proof above is not weakened by section H, it is inherited
    by it, and this shows the inheritance rather than asserting it:

      * no chain is ever an opposed pair, so there is always a weapon whose
        counter is not simultaneously a shrug;
      * the weighted mean of matchups is bounded by the best and worst matchup
        in the chain, so it never leaves [0.65, 1.50] and every clamp in
        `resolve_damage` behaves exactly as it did;
      * therefore the worst persistent case is still
        WORST_CASE_MULTIPLIER = 0.25, measured here over every legal chain
        against every attacker with the worst armour in the game;
      * and countering more of a thing never pays less, which is the property
        that makes the puzzle a puzzle rather than a trick.
    """
    worst_armour = ArmourProfile(points=9999, resist={FIRE: RESIST_CAP},
                                 points_cap=ARMOUR_POINT_CAP, kind="PLATE")
    attackers = list(ELEMENTS) + [NEUTRAL]
    chains = _legal_chains()

    contradictions = [c for c in chains
                      for a in c for b in c
                      if a in ELEMENTS and OPPOSED.get(a) == b]

    lowest = 2.0
    highest = 0.0
    worst_ratio = 1.0
    worst_stretch = 1.0
    worst_stretch_vs_counter = 1.0
    always_lands = True
    monotone = True

    for chain in chains:
        # bounded by the extremes of its own rows
        for atk in attackers:
            mult, _, rows = matchup_multi(atk, chain)
            row_mults = [r["multiplier"] for r in rows]
            if not (min(row_mults) - 1e-9 <= mult <= max(row_mults) + 1e-9):
                monotone = False
            lowest = min(lowest, mult)
            highest = max(highest, mult)

        # the floor, measured against a plain fight and against the best
        # reading of this same enemy
        best = max(matchup_multi(a, chain)[0] for a in attackers)
        best_atk = max(attackers, key=lambda a: matchup_multi(a, chain)[0])
        for base, enemy_hp in ((6, 40), (10, 50), (14, 56), (22, 120),
                               (40, 200)):
            plain = resolve_damage(base, NEUTRAL,
                                   Defender(element=NEUTRAL)).damage
            best_hit = resolve_damage(
                base, best_atk, Defender(elements=chain)).damage
            for atk in attackers:
                hit = resolve_damage(
                    base, atk,
                    Defender(elements=chain, armour=worst_armour)).damage
                if hit < MIN_DAMAGE:
                    always_lands = False
                worst_ratio = min(worst_ratio, hit / plain)
                casts = lambda h: -(-enemy_hp // max(1, h))
                worst_stretch = max(worst_stretch, casts(hit) / casts(plain))
                worst_stretch_vs_counter = max(
                    worst_stretch_vs_counter, casts(hit) / casts(best_hit))
        del best

        # countering more of it is never worse: if attacker A is at least as
        # good as attacker B against every element in the chain, A's damage is
        # at least B's.
        for a in attackers:
            for b in attackers:
                rows_a = matchup_multi(a, chain)[2]
                rows_b = matchup_multi(b, chain)[2]
                if all(ra["multiplier"] >= rb["multiplier"] - 1e-9
                       for ra, rb in zip(rows_a, rows_b)):
                    da = resolve_damage(20, a, Defender(elements=chain)).damage
                    db = resolve_damage(20, b, Defender(elements=chain)).damage
                    if da < db:
                        monotone = False

    # The worked rows from the section H comment, computed rather than typed.
    table = []
    for chain in (("FIRE",), ("FIRE", "BRUTE"), ("VOID", "COLD", "BRUTE")):
        row = {"chain": list(chain)}
        for atk in (COLD, FIRE, POISON, LIGHTNING):
            row[atk] = round(matchup_multi(atk, chain)[0], 3)
        table.append(row)

    # And the filter, which is the runtime half of rule one: a bestiary entry
    # that names both halves of a pair loses the second half rather than being
    # believed.
    contradictory = enemy_elements({"elements": [FIRE, COLD, BRUTE]}, "")

    return {
        "chains_proved": len(chains),
        "overrides_are_filtered": OPPOSED[contradictory[0]] not in contradictory,
        "contradictory_override_becomes": list(contradictory),
        "regions_with_two_or_more": sorted(
            rid for rid, chain in REGION_AFFINITIES.items() if len(chain) > 1),
        "no_opposed_pair_in_any_chain": not contradictions,
        "contradictions": sorted({tuple(sorted(set(c))) for c in contradictions}),
        "multiplier_span": [round(lowest, 3), round(highest, 3)],
        "stays_inside_single_element_bounds":
            lowest >= _SAME_MULT - 1e-9 and highest <= _OPPOSED_MULT + 1e-9,
        "worst_damage_ratio": round(worst_ratio, 3),
        "guaranteed_damage_ratio": WORST_CASE_MULTIPLIER,
        "ratio_holds": worst_ratio >= WORST_CASE_MULTIPLIER - 1e-9,
        "worst_cast_stretch": round(worst_stretch, 2),
        "stretch_within_declared": worst_stretch <= MAX_FIGHT_STRETCH + 1e-9,
        "worst_cast_stretch_vs_counter": round(worst_stretch_vs_counter, 2),
        "stretch_vs_counter_within_declared":
            worst_stretch_vs_counter <= MAX_FIGHT_STRETCH_VS_COUNTER + 1e-9,
        "every_worst_case_still_lands": always_lands,
        "countering_more_never_pays_less": monotone,
        "worked": table,
        "reading": ("A defender that is two or three things is still bounded by "
                    "the wheel it is made of. The worst reading of it costs the "
                    "same four times the typing it always did, and the best "
                    "reading of it is worth less than countering one thing "
                    "outright — which is the point: the rest of the advantage "
                    "has moved into what you are wearing."),
    }


def self_check() -> dict:
    """Counts, and the proofs. Safe to call from a test or the command line."""
    missing_biomes = sorted({r["biome"] for r in world.REGIONS
                             if r["biome"] not in BIOME_AFFINITY})
    unplaced = [rid for rid, e in AFFINITY.items()
                if e != NEUTRAL and e not in ELEMENTS]

    # Every element opposes exactly one other, and opposition is symmetric.
    pairs_ok = all(OPPOSED.get(OPPOSED[e]) == e for e in ELEMENTS)
    self_opposed = [e for e in ELEMENTS if OPPOSED[e] == e]
    pairs = sorted({tuple(sorted((e, OPPOSED[e]))) for e in ELEMENTS})

    # Every element inflicts exactly one status, and every status belongs to
    # exactly one element. A status nobody can apply is decoration.
    element_statuses = {e.status for e in ELEMENTS.values()}
    orphan_statuses = sorted(set(STATUS_IDS) - element_statuses)
    uncurable = [s.id for s in STATUSES.values() if not s.curable]

    by_element = {}
    for rid, e in AFFINITY.items():
        by_element.setdefault(e, []).append(rid)

    pet_by_element = {}
    for species, e in PET_ELEMENT.items():
        pet_by_element.setdefault(e, []).append(species)

    dead_end = _prove_no_dead_end()
    monotone = _prove_monotonic_in_armour()
    typing = _prove_typing_still_rules()
    multi = _prove_multi_affinity()

    # A worked example of the secondary advantage, so the asymmetry is visible
    # rather than asserted.
    void_into_poison = matchup(VOID, POISON)
    poison_into_void = matchup(POISON, VOID)

    ok = (not missing_biomes and not unplaced and pairs_ok and not self_opposed
          and not orphan_statuses and not uncurable
          and len(by_element) > 1 and NEUTRAL in by_element
          and set(ELEMENTS) <= set(pet_by_element)
          and monotone["monotonic_in_armour"] and monotone["always_positive"]
          and typing["zero_base_gives_zero"]
          and typing["no_turn_skipping_status"]
          and dead_end["every_worst_case_still_lands"]
          and dead_end["ratio_holds"]
          and dead_end["stretch_within_declared"]
          and dead_end["stretch_vs_counter_within_declared"]
          and multi["no_opposed_pair_in_any_chain"]
          and multi["stays_inside_single_element_bounds"]
          and multi["ratio_holds"]
          and multi["stretch_within_declared"]
          and multi["stretch_vs_counter_within_declared"]
          and multi["every_worst_case_still_lands"]
          and multi["countering_more_never_pays_less"]
          and multi["overrides_are_filtered"]
          and NEUTRAL not in ELEMENTS)

    return {
        # -- A: the wheel
        "elements": len(ELEMENTS),
        "element_ids": list(ELEMENT_IDS),
        "pairs": [list(p) for p in pairs],
        "every_element_has_an_opposition": pairs_ok and not self_opposed,
        "opposition_symmetric": pairs_ok,
        "neutral_is_not_an_element": NEUTRAL not in ELEMENTS,
        "secondary": {"VOID->POISON": void_into_poison,
                      "POISON->VOID": poison_into_void},
        "secondary_weaker_than_opposition":
            void_into_poison[0] < MATCHUP_MULT["OPPOSED"],
        "multipliers": dict(MATCHUP_MULT),

        # -- B: the areas
        "regions": len(world.REGIONS),
        "regions_with_affinity": len(AFFINITY),
        "every_region_has_an_affinity": len(AFFINITY) == len(world.REGIONS),
        "biomes_unplaced": missing_biomes,
        "affinity_by_element": {k: sorted(v) for k, v in sorted(by_element.items())},
        "neutral_regions": sorted(by_element.get(NEUTRAL, [])),
        "elemental_regions": len(world.REGIONS) - len(by_element.get(NEUTRAL, [])),
        "affinity": dict(sorted(AFFINITY.items())),

        # -- C: the damage function
        "min_damage": MIN_DAMAGE,
        "mult_floor": MULT_FLOOR, "mult_ceil": MULT_CEIL,
        "resist_cap": RESIST_CAP, "armour_point_cap": ARMOUR_POINT_CAP,
        "worst_case_multiplier": WORST_CASE_MULTIPLIER,
        "max_fight_stretch": MAX_FIGHT_STRETCH,
        "max_fight_stretch_vs_counter": MAX_FIGHT_STRETCH_VS_COUNTER,
        "no_dead_end": dead_end,
        **monotone,
        **typing,

        # -- D: armour
        "armour_kinds": list(ARMOUR_KINDS),
        "points_caps": {k: v["points_cap"] for k, v in ARMOUR_KINDS.items()},
        "flat_and_elemental_are_distinct":
            ARMOUR_KINDS["PLATE"]["points_cap"] > ARMOUR_KINDS["WARDED"]["points_cap"],
        "piece_resist_cap": PIECE_RESIST_CAP,

        # -- E: status
        "statuses": list(STATUS_IDS),
        "status_elements": {s.id: s.element for s in STATUSES.values()},
        "orphan_statuses": orphan_statuses,
        "every_status_has_an_element": not orphan_statuses,
        "every_status_curable": not uncurable,
        "cures": {k: list(v) for k, v in CURES.items()},
        "dots": [s.id for s in STATUSES.values() if s.kind == "dot"],
        "applies_to_monsters_too": True,   # tick_statuses never asks whose list

        # -- F: boots
        "boots": len(BOOTS),
        "hazards": list(HAZARDS),
        "hazard_per_element": dict(sorted(HAZARD_BY_ELEMENT.items())),
        "every_element_has_a_hazard":
            set(HAZARD_BY_ELEMENT) == set(ELEMENTS),
        "boots_cover_every_hazard":
            {h.boots_tag for h in HAZARDS.values()}
            <= {tag for b in BOOTS for tag in b.immunities},

        # -- H: monsters that are more than one thing
        "max_affinities": MAX_AFFINITIES,
        "multi_weights": list(MULTI_WEIGHTS),
        "second_affinity_at": SECOND_AFFINITY_AT,
        "third_affinity_at": THIRD_AFFINITY_AT,
        "region_affinities": {k: list(v)
                              for k, v in sorted(REGION_AFFINITIES.items())},
        "multi_affinity": multi,

        # -- G: pets
        "pet_species": len(PET_ELEMENT),
        "pet_element": dict(sorted(PET_ELEMENT.items())),
        "pet_by_element": {k: sorted(v) for k, v in sorted(pet_by_element.items())},
        "every_element_has_a_companion": set(ELEMENTS) <= set(pet_by_element),

        # -- the seal
        "seal_is_an_argument": True,   # nothing here reads mode or encounter
        "build_sealed_neutralises":
            resolve_damage(10, COLD, Defender(element=FIRE), build_sealed=True
                           ).damage
            == resolve_damage(10, NEUTRAL, Defender(element=NEUTRAL)).damage,

        "ok": ok,
    }


if __name__ == "__main__":                                    # pragma: no cover
    import json
    print(json.dumps(self_check(), indent=2, default=str))
