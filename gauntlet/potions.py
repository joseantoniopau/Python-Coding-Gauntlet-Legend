"""Potions: four strengths, three kinds, and the turn they are drunk on.

WHAT A POTION IS FOR
--------------------
This game's attack is a line of Python you type. Everything in this file is the
tactical layer around that line, and the single rule the whole module is built
to obey is:

    A POTION MAY NEVER REDUCE HOW MUCH PYTHON THE PLAYER WRITES.

It may make a fight survivable, and therefore LONGER, and therefore worth more
repetition — which is the actual pedagogical lever, because fluency is built by
casting the same idiom again after having had to think about something else. It
may not shorten one. Nothing in here touches enemy hit points, names a pattern,
or answers anything. `_validate()` checks that at import: a potion's effect keys
are a subset of {stamina, mana, poison} forever, and the day someone adds
`"damage"` to one the module refuses to load.

The consequence is worth stating plainly, because it is the point of the design
and not a side effect. A player with the wrong element and a full pouch does not
win faster. They win having typed roughly twice as many lines. `simulate()` at
the bottom prints that number.

THE FOUR STRENGTHS
------------------
minor, small, medium, hefty — across HEALTH (restores stamina), FOCUS (restores
mana) and ANTIDOTE (clears poison). Twelve potions. Each is banded to a
difficulty area by `min_tier`, so the Fields of Syntax hand out thimbles and a
flagon is something you carry out of an Elite room. Restoration is a FRACTION of
the drinker's own maximum with a floor, so a hefty flagon is still a hefty
flagon after VIGOR has doubled your health bar, and it is never a full heal:
`CEILING_FRACTION` caps the deepest potion in the game at 55% of maximum. A full
heal would mean a fight can be reset, and a fight that can be reset is a fight
whose difficulty is an inventory question.

THE ELEMENTS, AND WHY THE ANTIDOTE IS THE ONLY ONE HERE
------------------------------------------------------
The brief's counters cannot all hold simultaneously, and the resolution adopted
across this feature is THREE OPPOSED PAIRS:

    FIRE <-> COLD        POISON <-> BRUTE FORCE        LIGHTNING <-> VOID

with "void beats poison" kept as a documented SECONDARY advantage — weaker than
a true opposition, and visible here only as the mild antidote bias of a void
region's chests. Potions themselves carry no element. They are drink, not
damage, and giving them one would be a second elemental economy competing with
the weapon and armour tables. The one exception is structural rather than
elemental: an ANTIDOTE opposes POISON because that is what an antidote is.

Affinity reaches this file as a plain lowercase string on the way in
(`affinity="poison"`). Nothing is imported from whichever module owns the
element table, so the two can be written, reordered and rebalanced
independently, and an affinity this file has never heard of biases nothing
rather than raising.

THE TURN — THE PART THAT MATTERS
--------------------------------
Combat is turn based and on the player's turn a potion is drunk ALONGSIDE the
Python attack. Drinking is not a turn. That sounds generous, and the second half
of the rule is what makes it strict:

    ONE DRAUGHT PER TURN, AND ONLY A RESOLVED CAST CREATES THE NEXT TURN.

So a draught is free, and a second draught costs exactly one line of Python.
Emptying a fourteen-potion pouch across a fight costs fourteen casts. There is
no order of operations, no pause menu and no amount of hoarding that converts
potions into a substitute for typing; the pouch is spent at the speed the player
writes Python and at no other speed. Had drinking been a turn instead, the
optimal play in a hard fight would have been to drink rather than think, and the
game would have quietly become an inventory game with a REPL attached.

LIMITS — THE SINGLE MOST IMPORTANT BALANCE DECISION IN THIS FILE
----------------------------------------------------------------
What stops a player carrying forty hefty potions and never thinking again is
three things, in descending order of importance.

1. THE TURN RULE ABOVE. This is the real answer and the only one that cannot be
   farmed around. Forty potions would still be forty turns, and forty turns is
   forty lines of Python — forty MORE than the player would otherwise have
   written. A limit that converts hoarding into practice is better than a limit
   that punishes it.

2. DIMINISHING RETURNS INSIDE ONE FIGHT. Each successive potion of the same kind
   in the same fight is worth `SIP_FALLOFF` of the last, floored at `SIP_FLOOR`.
   The first flagon is a rescue; the fifth is a sip. This is what stops a long
   fight from being won by volume, and it resets between fights so the pouch
   never feels like a punishment for having one.

3. CARRY CAPS, PER STRENGTH, PER KIND. Two hefty, three medium, four small, five
   minor. Forty hefty potions is not a balance question because the pouch will
   not hold them. The cap is tighter the stronger the potion, which is the same
   statement the drop table makes — deep things are rare — expressed where the
   player can see it.

Three things that were considered and rejected, since a balance decision is only
legible next to what it beat:

   A COOLDOWN measured in turns is the turn rule with worse manners. It would
   punish the player for the cast they just made, which is the one behaviour the
   game exists to encourage.

   A GOLD COST would make the strongest tactical option a function of grinding,
   and this game has deliberately never let anything important be bought:
   `items.UPGRADE_PATHS` has no vendor for exactly this reason.

   PURE SCARCITY — just make them rare — was rejected on its own because it
   fails in the direction that matters. Rarity makes potions scary to use, and a
   potion nobody drinks teaches nothing. Better to hand them out reasonably often
   and make the act of drinking cost a line of Python.

THE NUMBERS, SO THE ARGUMENT IS NOT A CLAIM
-------------------------------------------
`simulate_sweep()` runs the same 240-HP fight forty times with paired seeds — the
cast sequence is identical with and without the pouch, because drinking consumes
no randomness — and `break_even_accuracy()` reports the lowest accuracy at which
a player clears it nine times in ten. Run `python -m gauntlet.potions` for the
current figures. At the time of writing:

    scenario                             break-even   mean casts   clears
    matched element, empty pouch              74%         20.1      31/40
    wrong element, empty pouch                90%         33.3       0/40
    wrong element, full pouch                 72%         67.4      35/40
    wrong element + poison, empty pouch       96%         20.4       0/40
    wrong element + poison, full pouch        84%         50.0       9/40
    wrong element, empty pouch, 92% player     --         52.4      39/40

Read the last row first. Wrong element, nothing in the bag, a player who has
actually learned the moveset: thirty-nine clears out of forty, in fifty-two
casts instead of twenty. Elemental disadvantage makes a fight two and a half
times longer and never makes it unwinnable, which is the rule, and the extra
length is thirty-two extra lines of Python, which is the reward.

Read the third row second. A full pouch buys back eighteen points of accuracy —
roughly the whole cost of being on the wrong end of an opposed pair — and it
pays for that by making the fight THREE TIMES LONGER than a matched one. The
pouch is not a shortcut past the Python. It is thirty-four more casts of it.

And row two against row one: potions are for the player who has not learned the
moveset yet. A fluent player barely opens the pouch — `matched_full_pouch`
drinks two potions and leaves forty in the bag.

MONSTERS DRINK TOO
------------------
The brief is explicit that monsters carry antidotes, so they do, and the
asymmetry is deliberate and in the player's favour: a MONSTER'S antidote SPENDS
ITS TURN. Poisoning something that can cure itself is therefore never wasted —
it buys you a free turn, which is one more line of Python you get to land for
nothing. And the cure is announced out loud through `monster_cure()`, never
applied as a silent subtraction. An enemy undoing your plan is a moment; a
number quietly going up is a bug report.

SEALING
-------
Every gate in this file is `finalexam.sealed(encounter, "ITEMS")`, the crutch the
Bug Demon already takes and the exam already seals. There is no second isolation
path here and there must never be one.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict

from . import config, finalexam, items

# ---------------------------------------------------------------------------
# 1. Vocabulary
# ---------------------------------------------------------------------------

KINDS = ("HEALTH", "FOCUS", "ANTIDOTE")
STRENGTHS = ("minor", "small", "medium", "hefty")

# The difficulty ladder, mirrored rather than imported. `curriculum.TIERS`,
# `adaptive.DIFF_ORDER`, `items.DIFFICULTY_DROP_CHANCE` and `forge` all state it;
# mirroring keeps this module loadable on its own, and `_validate()` reconciles
# it against items.DIFFICULTY_DROP_CHANCE so a drift is an import error and not a
# potion that can never drop.
TIER_ORDER = ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS")
TIER_INDEX = {name: i for i, name in enumerate(TIER_ORDER)}

# Which player field each kind pours into. These are the names engine.py already
# uses: stamina IS health and mana IS focus, and they were health and focus in
# all but name long before this file existed. Renaming them was considered and
# rejected — it would touch forty call sites to change nothing.
POURS_INTO = {"HEALTH": "stamina", "FOCUS": "mana", "ANTIDOTE": ""}

KIND_LABEL = {"HEALTH": "Health", "FOCUS": "Focus", "ANTIDOTE": "Antidote"}
KIND_COLOUR = {"HEALTH": "#ff6a7a", "FOCUS": "#a89aff", "ANTIDOTE": "#8fd07a"}

# The sprite layer draws the vessel, not the liquid: strength is readable at a
# glance from the silhouette, colour from the kind. Four silhouettes, four
# strengths, and nobody has to read a tooltip mid-fight.
STRENGTH_VESSEL = {"minor": "thimble", "small": "vial",
                   "medium": "flask", "hefty": "flagon"}

# Rarity is borrowed from items.RARITIES so the pouch and the loot panel colour
# the same object the same way. A potion is not gear and never rolls on the gear
# table; this is purely the swatch.
STRENGTH_RARITY = {"minor": "COMMON", "small": "UNCOMMON",
                   "medium": "RARE", "hefty": "EPIC"}


# ---------------------------------------------------------------------------
# 2. The bands
# ---------------------------------------------------------------------------
#
# `fraction` is of the drinker's own maximum; `floor` is the minimum in points,
# set so that the two agree exactly at the base maxima in config (stamina 20,
# focus 30). The floor is what keeps a minor potion honest for a level-1 player
# and the fraction is what keeps a hefty one honest for a level-40 one.
#
# CEILING_FRACTION is the promise that no potion in the game is a full heal.

CEILING_FRACTION = 0.55

STRENGTH_BAND = {
    "minor":  {"fraction": 0.15, "floor": {"HEALTH": 3,  "FOCUS": 4}},
    "small":  {"fraction": 0.26, "floor": {"HEALTH": 5,  "FOCUS": 8}},
    "medium": {"fraction": 0.40, "floor": {"HEALTH": 8,  "FOCUS": 12}},
    "hefty":  {"fraction": 0.55, "floor": {"HEALTH": 11, "FOCUS": 16}},
}

# How many of each the pouch will hold, per kind. Tighter the stronger it gets.
CARRY_CAP = {"minor": 5, "small": 4, "medium": 3, "hefty": 2}

# Diminishing returns within one fight, per kind. Multiplier on the Nth draught
# of that kind: 1.00, 0.75, 0.56, 0.42, then the floor forever.
SIP_FALLOFF = 0.75
SIP_FLOOR = 0.30


def sip_multiplier(prior: int) -> float:
    """The value of a draught after `prior` draughts of the same kind this fight."""
    return max(SIP_FLOOR, SIP_FALLOFF ** max(0, int(prior)))


# ---------------------------------------------------------------------------
# 3. The catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Potion:
    id: str
    kind: str
    strength: str
    name: str
    min_tier: str               # the shallowest difficulty area it is found in
    blurb: str                  # what it does, in points, for the tooltip
    flavour: str                # dressing
    clears: int = 0             # ANTIDOTE: doses removed; 0 = all of them
    ward_turns: int = 0         # ANTIDOTE: turns of immunity afterwards

    @property
    def vessel(self) -> str:
        return STRENGTH_VESSEL[self.strength]

    @property
    def rarity(self) -> str:
        return STRENGTH_RARITY[self.strength]

    @property
    def colour(self) -> str:
        return KIND_COLOUR[self.kind]

    @property
    def cap(self) -> int:
        return CARRY_CAP[self.strength]

    @property
    def effect_keys(self) -> tuple:
        """Everything this potion is allowed to touch. The audit in `_validate()`
        reads this, and the whole safety argument of the module rests on the set
        staying inside {stamina, mana, poison}."""
        if self.kind == "ANTIDOTE":
            return ("poison",)
        return (POURS_INTO[self.kind],)

    def restores(self, maximum: int) -> int:
        """Points restored to a bar of size `maximum`, before the in-fight
        falloff. Zero for an antidote, which restores nothing and removes
        something."""
        return band_restore(self.kind, self.strength, maximum)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update({
            "vessel": self.vessel, "rarity": self.rarity, "colour": self.colour,
            "cap": self.cap, "kind_label": KIND_LABEL[self.kind],
            "rarity_colour": items.RARITIES[self.rarity]["colour"],
            "min_tier_index": TIER_INDEX[self.min_tier],
            "pours_into": POURS_INTO[self.kind],
        })
        return d


def band_restore(kind: str, strength: str, maximum: int) -> int:
    """Points a (kind, strength) restores from a bar of size `maximum`.

    Fraction of maximum, floored at the band's minimum, hard-capped at
    CEILING_FRACTION so nothing is ever a full heal. Free function as well as a
    method because the client's tooltip and the balance audit both want it
    without holding a Potion.
    """
    if kind == "ANTIDOTE":
        return 0
    maximum = max(1, int(maximum))
    band = STRENGTH_BAND[strength]
    ceiling = max(1, int(maximum * CEILING_FRACTION))
    wanted = int(round(band["fraction"] * maximum))
    return min(max(band["floor"][kind], wanted), ceiling)


def _p(kind: str, strength: str, name: str, min_tier: str, flavour: str,
       *, clears: int = 0, ward_turns: int = 0) -> Potion:
    if kind == "ANTIDOTE":
        cured = "every dose" if clears == 0 else (
            "one dose" if clears == 1 else f"{clears} doses")
        blurb = f"Clears {cured} of poison."
        if ward_turns:
            blurb += f" You cannot be poisoned again for {ward_turns} turns."
    else:
        bar = "health" if kind == "HEALTH" else "focus"
        base = config.STAMINA_MAX if kind == "HEALTH" else config.MANA_MAX
        band = STRENGTH_BAND[strength]
        blurb = (f"Restores {int(band['fraction'] * 100)}% of maximum {bar} "
                 f"(at least {band['floor'][kind]}, {band_restore(kind, strength, base)} "
                 f"at a starting bar).")
    return Potion(id=f"{kind.lower()}_{strength}", kind=kind, strength=strength,
                  name=name, min_tier=min_tier, blurb=blurb, flavour=flavour,
                  clears=clears, ward_turns=ward_turns)


CATALOGUE: tuple = (
    # ---- HEALTH: found from the first morning, because a player who cannot
    # survive the Fields never gets to the part where any of this is strategy.
    _p("HEALTH", "minor", "Thimble of Red", "GUIDED",
       "Two swallows and a taste of iron. The village gives these away."),
    _p("HEALTH", "small", "Vial of Quickblood", "EASY",
       "Warm going down. Whatever it is made of, it was moving recently."),
    _p("HEALTH", "medium", "Flask of Second Wind", "HARD",
       "The long exhale you take before you look at the input again."),
    _p("HEALTH", "hefty", "Flagon of the Long Fight", "ELITE",
       "Brewed for people who intend to still be standing in twenty turns."),

    # ---- FOCUS: one tier later than health, because focus only starts to matter
    # once there are spells to spend it on, and a potion for a bar you are not
    # yet using is a potion that teaches the player to ignore the pouch.
    _p("FOCUS", "minor", "Thimble of Clarity", "TUTORIAL",
       "Tastes faintly of the moment a variable name stops looking arbitrary."),
    _p("FOCUS", "small", "Vial of Sharp Attention", "EASY",
       "The room gets quieter. It has not actually got quieter."),
    _p("FOCUS", "medium", "Flask of the Held Thought", "HARD",
       "For keeping the whole loop in your head while you write the first line."),
    _p("FOCUS", "hefty", "Flagon of the Quiet Room", "ELITE",
       "The Archivist drinks this and then does not speak for an hour."),

    # ---- ANTIDOTE: from EASY, because poison is a rainforest and a marsh, and
    # neither is somewhere the first two tiers send anybody. An antidote
    # available before the first poison would be a mystery item.
    _p("ANTIDOTE", "minor", "Thimble of Chalk", "EASY",
       "Chalk and salt. It absorbs one bad decision and no more.",
       clears=1),
    _p("ANTIDOTE", "small", "Vial of Green Milk", "MEDIUM",
       "It looks considerably worse than what it cures.",
       clears=2, ward_turns=1),
    _p("ANTIDOTE", "medium", "Flask of Clean Blood", "HARD",
       "Every dose at once, and a couple of turns where nothing new sticks.",
       clears=0, ward_turns=2),
    _p("ANTIDOTE", "hefty", "Flagon of the Undone Bite", "ELITE",
       "The canopy has been trying to kill people for a long time. So has this.",
       clears=0, ward_turns=4),
)

BY_ID = {p.id: p for p in CATALOGUE}
POTION_IDS = tuple(p.id for p in CATALOGUE)
BY_KIND = {k: tuple(p for p in CATALOGUE if p.kind == k) for k in KINDS}


def potion(potion_id: str) -> Potion | None:
    return BY_ID.get(str(potion_id))


def catalogue(*, tier: str = "") -> list:
    """Every potion, serialised for the client. With `tier`, only the ones that
    area is allowed to hand out."""
    rows = [p for p in CATALOGUE if not tier or found_at(p.id, tier)]
    return [p.to_dict() for p in rows]


def found_at(potion_id: str, tier: str) -> bool:
    """Can an area of this difficulty produce this potion at all?"""
    p = BY_ID.get(potion_id)
    if p is None:
        return False
    return TIER_INDEX.get(tier, 0) >= TIER_INDEX[p.min_tier]


def available_at(tier: str, *, kind: str = "") -> list:
    """Potion ids an area of this difficulty can hand out."""
    return [p.id for p in CATALOGUE
            if found_at(p.id, tier) and (not kind or p.kind == kind)]


# ---------------------------------------------------------------------------
# 4. The pouch
# ---------------------------------------------------------------------------
#
# Kept in its own save key rather than folded into `state["consumables"]`.
# engine.use_consumable looks every key up in items.CONSUMABLES and refuses what
# it does not find, and a potion is not one of those: it has a strength band, a
# carry cap, a per-fight falloff and a turn rule, none of which that table can
# express. One dict of counts, so a save is still readable by a human.

POUCH_STATE_KEY = "potions"


@dataclass
class Pouch:
    counts: dict = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: dict | None) -> "Pouch":
        raw = (state or {}).get(POUCH_STATE_KEY) or {}
        clean = {}
        for key, value in dict(raw).items():
            if key in BY_ID:
                clean[key] = max(0, min(int(value or 0), BY_ID[key].cap))
        return cls(counts=clean)

    def to_state(self, state: dict) -> dict:
        state[POUCH_STATE_KEY] = {k: v for k, v in self.counts.items() if v > 0}
        return state

    def count(self, potion_id: str) -> int:
        return int(self.counts.get(potion_id, 0))

    def total(self, *, kind: str = "") -> int:
        return sum(n for k, n in self.counts.items()
                   if n > 0 and (not kind or BY_ID[k].kind == kind))

    def space_for(self, potion_id: str) -> int:
        p = BY_ID.get(potion_id)
        return 0 if p is None else max(0, p.cap - self.count(potion_id))

    def add(self, potion_id: str, n: int = 1) -> dict:
        """Put `n` in the pouch, honouring the cap. Reports the overflow rather
        than swallowing it, so the client can say "your pouch is full" instead of
        dropping loot on the floor in silence."""
        p = BY_ID.get(potion_id)
        if p is None:
            return {"added": 0, "overflow": 0, "error": "no such potion"}
        room = self.space_for(potion_id)
        added = max(0, min(int(n), room))
        if added:
            self.counts[potion_id] = self.count(potion_id) + added
        return {"added": added, "overflow": max(0, int(n) - added),
                "held": self.count(potion_id), "cap": p.cap, "id": potion_id}

    def spend(self, potion_id: str) -> bool:
        if self.count(potion_id) <= 0:
            return False
        self.counts[potion_id] -= 1
        if self.counts[potion_id] <= 0:
            self.counts.pop(potion_id, None)
        return True

    def to_dict(self) -> dict:
        return {"counts": dict(self.counts), "total": self.total()}


def grant(state: dict, found, n: int = 1) -> dict:
    """Put a drop into the save state's pouch and write it back.

    `found` is a potion id or the drop envelope roll_monster_drop/roll_chest
    returned, so the engine's loot handler can hand this whatever it is holding.
    Returns the add() report, including `overflow` when the pouch was full — the
    caller should say so out loud rather than deleting loot quietly.
    """
    pid = found if isinstance(found, str) else str((found or {}).get("id", ""))
    pouch = Pouch.from_state(state)
    report = pouch.add(pid, n)
    pouch.to_state(state)
    return report


# ---------------------------------------------------------------------------
# 5. Poison
# ---------------------------------------------------------------------------
#
# Poison is damage over time ON TOP of normal damage, which is the brief's
# phrasing and the right one: a poisoned fighter is still taking hits. A dose is
# independent — two doses tick twice a turn — because that is what makes an
# antidote's `clears` count mean something, and what makes a minor antidote a
# real but partial answer rather than a worse version of a good one.
#
# Doses tick at the START of the poisoned side's turn, before anything is drunk,
# so a dose that would kill you kills you and a potion cannot be used to rewind
# a tick that already landed.
#
# THE STACKING RULE, STATED ONCE AND OBEYED IN TWO PLACES
# -------------------------------------------------------
# POISON STACKS TO TWO DOSES AND NO FURTHER. A third application refreshes the
# shortest-lived dose instead of adding to the pile.
#
# This number is not chosen here. `elements.STATUSES["POISONED"]` sets
# `max_stacks = 2`, with the reason given there: a third stack would make a side
# effect into the main event, and the main event is the line you type. This file
# used to append without limit, which meant the same word — "poison" — named a
# two-stack effect on the element wheel and an unbounded one in the pouch. Five
# applications ticked for 2 on one model and 10 on the other, on the same 20
# point bar. `MAX_DOSES` is mirrored rather than imported for the same reason
# TIER_ORDER is, and `_validate()` reconciles the two so a drift is an import
# error rather than a monster that kills through a full health bar in two turns.
MAX_DOSES = 2

@dataclass
class Dose:
    damage: int = 2          # points per turn, off the same bar HEALTH refills
    turns: int = 3
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Poison:
    doses: list = field(default_factory=list)
    ward: int = 0            # turns of immunity left, from an antidote

    @classmethod
    def from_dict(cls, data: dict | None) -> "Poison":
        data = data or {}
        return cls(doses=[Dose(**d) for d in data.get("doses", [])],
                   ward=int(data.get("ward", 0) or 0))

    def to_dict(self) -> dict:
        return {"doses": [d.to_dict() for d in self.doses], "ward": self.ward,
                "stacks": len(self.doses), "per_turn": self.per_turn,
                "warded": self.ward > 0}

    @property
    def per_turn(self) -> int:
        return sum(d.damage for d in self.doses)

    @property
    def active(self) -> bool:
        return bool(self.doses)


def poison_apply(poison: Poison, *, damage: int = 2, turns: int = 3,
                 source: str = "") -> dict:
    """Land a dose. A ward refuses it, out loud; the stack cap deepens instead.

    At `MAX_DOSES` the new dose does not stack — it REFRESHES the dose with the
    least time left, which is the same "refreshes, never deepens" behaviour
    `elements.inflict` already applies at `max_stacks`. Refreshing rather than
    discarding matters: standing in a spore cloud should keep the poison
    running, it just must not keep making it worse without bound.
    """
    if poison.ward > 0:
        return {"applied": False, "warded": True,
                "line": "The venom beads on your skin and will not take. "
                        f"The ward holds for {poison.ward} more turns.",
                "poison": poison.to_dict()}
    damage = max(1, int(damage))
    turns = max(1, int(turns))
    if len(poison.doses) >= MAX_DOSES:
        weakest = min(poison.doses, key=lambda d: d.turns)
        weakest.turns = max(weakest.turns, turns)
        weakest.damage = max(weakest.damage, damage)
        return {"applied": True, "warded": False, "refreshed": True,
                "capped": True, "stacks": len(poison.doses),
                "line": f"The poison is renewed: {poison.per_turn} a turn. "
                        f"It will not take deeper than {MAX_DOSES} doses.",
                "poison": poison.to_dict()}
    poison.doses.append(Dose(damage=damage, turns=turns, source=source))
    return {"applied": True, "warded": False, "stacks": len(poison.doses),
            "line": f"Poison takes hold: {poison.per_turn} a turn, "
                    f"{len(poison.doses)} dose(s) working.",
            "poison": poison.to_dict()}


def poison_tick(poison: Poison) -> dict:
    """One turn of damage over time. Returns the points owed; the caller
    subtracts them, because this module does not own anybody's hit points."""
    if not poison.doses:
        if poison.ward > 0:
            poison.ward -= 1
        return {"damage": 0, "doses": 0, "line": "", "poison": poison.to_dict()}
    damage = poison.per_turn
    for dose in poison.doses:
        dose.turns -= 1
    expired = [d for d in poison.doses if d.turns <= 0]
    poison.doses = [d for d in poison.doses if d.turns > 0]
    if poison.ward > 0:
        poison.ward -= 1
    line = f"Poison bites for {damage}."
    if expired:
        line += f" {len(expired)} dose(s) burn out."
    return {"damage": damage, "doses": len(poison.doses), "expired": len(expired),
            "line": line, "poison": poison.to_dict()}


def poison_clear(poison: Poison, *, clears: int = 0, ward_turns: int = 0) -> dict:
    """What an antidote does. `clears=0` means every dose."""
    before = len(poison.doses)
    if clears <= 0:
        poison.doses = []
        removed = before
    else:
        # Strongest doses first: an antidote should feel like it went after the
        # thing that is actually killing you.
        order = sorted(range(before), key=lambda i: -poison.doses[i].damage)
        drop = set(order[:clears])
        poison.doses = [d for i, d in enumerate(poison.doses) if i not in drop]
        removed = before - len(poison.doses)
    poison.ward = max(poison.ward, int(ward_turns))
    return {"removed": removed, "remaining": len(poison.doses),
            "ward": poison.ward, "poison": poison.to_dict()}


# ---------------------------------------------------------------------------
# 6. The turn
# ---------------------------------------------------------------------------
#
# The whole argument of the feature is four fields wide.
#
# `drunk_this_turn` is set by drink() and cleared ONLY by cast_resolved(). The
# engine calls cast_resolved() after every submission it grades, right or wrong,
# because a wasted turn is still a turn — that is already the Blitz rule in
# bestiary.py and potions do not get to disagree with it.
#
# `sips` is per kind and per fight, and drives the falloff. It resets when the
# fight does, which is `TurnState()`.

@dataclass
class TurnState:
    turn: int = 1
    drunk_this_turn: str = ""        # the potion id drunk on the current turn
    sips: dict = field(default_factory=dict)     # kind -> draughts this fight
    drunk_total: int = 0
    casts: int = 0

    @classmethod
    def from_dict(cls, data: dict | None) -> "TurnState":
        data = data or {}
        return cls(turn=int(data.get("turn", 1) or 1),
                   drunk_this_turn=str(data.get("drunk_this_turn", "") or ""),
                   sips={k: int(v) for k, v in (data.get("sips") or {}).items()},
                   drunk_total=int(data.get("drunk_total", 0) or 0),
                   casts=int(data.get("casts", 0) or 0))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["may_drink"] = not self.drunk_this_turn
        return d

    @property
    def may_drink(self) -> bool:
        return not self.drunk_this_turn


def cast_resolved(turn_state: TurnState, *, correct: bool = True) -> TurnState:
    """The turn advances. Call this after EVERY graded submission.

    `correct` is accepted and deliberately unused for the turn rule: a wrong cast
    costs the turn too, so the pouch cannot be emptied by typing nonsense. It is
    recorded because the client wants to say "turn 9" honestly.
    """
    turn_state.turn += 1
    turn_state.casts += 1
    turn_state.drunk_this_turn = ""
    return turn_state


def new_fight() -> TurnState:
    """A fresh fight: turn one, nothing drunk, the falloff wiped."""
    return TurnState()


# ---------------------------------------------------------------------------
# 7. Drinking
# ---------------------------------------------------------------------------

REFUSALS = {
    "none": "You have none of those.",
    "unknown": "There is no such potion.",
    "already": "You have already drunk this turn. Cast, and the turn moves with "
               "you.",
    "full_health": "You are at full health. Save it.",
    "full_focus": "Your focus is already whole. Save it.",
    "no_poison": "Nothing in you needs curing.",
}


def _refuse(code: str, **extra) -> dict:
    return {"ok": False, "error": code, "message": REFUSALS.get(code, code), **extra}


def drink(pouch: Pouch, potion_id: str, *, player: dict,
          turn_state: TurnState, poison: Poison | None = None,
          encounter=None, statuses: list | None = None) -> dict:
    """Drink one potion on the player's turn, alongside the attack.

    Mutates `pouch`, `player`, `turn_state`, `poison` and `statuses` and returns
    what happened, in the shape engine.Game.use_consumable already returns so
    the client has one result to render.

    THE RULE: this does not spend the turn, and it may not be called twice
    before `cast_resolved()`. Those two sentences together are the feature.

    `poison` is optional only so the health and focus paths do not have to
    construct one. Always pass the encounter's own Poison: an antidote drunk
    against a default throws the cure and the ward away into a temporary object,
    and the player will report it as the antidote not working.

    `statuses` is the combatant's `elements.StatusInstance` list, and an
    ANTIDOTE clears the POISONED status off it as well as emptying the dose
    pool. PASS IT WHENEVER YOU HAVE ONE. There are two poison representations in
    this game and they are not redundant — `Poison` carries doses, wards and
    durations, while `elements.STATUSES["POISONED"]` is the wheel's entry for
    what a POISON-element hit inflicts — but an antidote that cured only one of
    them was the worst bug in this feature: a monster in the marsh poisons you
    through `elements.resolve_damage().inflicted`, and before this argument
    existed no antidote in the game could touch it. The brief says antidotes
    clear poison. Both kinds, or the item is a lie.

    `elements` is imported inside the branch rather than at module scope so this
    file still loads on its own, which `_validate()` depends on. There is no
    cycle either way — elements does not import potions — so the local import is
    about keeping the module standalone, not about breaking one.
    """
    p = BY_ID.get(str(potion_id))
    if p is None:
        return _refuse("unknown")

    # The seal, first and unconditionally. A potion is ITEMS, the crutch the Bug
    # Demon takes and the exam seals; routing it anywhere else would be the
    # second isolation path this codebase has spent a whole module avoiding.
    if finalexam.sealed(encounter, "ITEMS"):
        return finalexam.refuse("ITEMS")

    if pouch.count(p.id) <= 0:
        return _refuse("none")
    if not turn_state.may_drink:
        return _refuse("already", drunk_this_turn=turn_state.drunk_this_turn,
                       turn=turn_state.turn)

    poison = poison if poison is not None else Poison()
    prior = int(turn_state.sips.get(p.kind, 0))
    multiplier = sip_multiplier(prior)
    log: list = []
    restored = 0

    if p.kind == "ANTIDOTE":
        # A Thimble of Chalk carries no ward, so there is nothing for it to do
        # against an unpoisoned player and drinking it would just be a thrown
        # potion. Everything from `small` upward may be drunk pre-emptively on
        # the way into the rainforest, which is a real and deliberate tactical
        # option: spend the turn's free action before the venom lands.
        wheel_poisoned = any(getattr(s, "id", "") == "POISONED"
                             for s in (statuses or ()))
        if not poison.active and not wheel_poisoned and p.ward_turns <= 0:
            return _refuse("no_poison")
        standing_ward = poison.ward
        cured = poison_clear(poison, clears=p.clears, ward_turns=p.ward_turns)
        # The falloff is a real cost for antidotes too, but it buys turns of ward
        # rather than points: the fourth antidote in a fight still clears the
        # poison, it just stops keeping it away afterwards. A ward already
        # running is never shortened by a weaker one landing on top of it.
        if p.ward_turns and multiplier < 1.0:
            poison.ward = max(standing_ward, int(round(p.ward_turns * multiplier)))
            cured["ward"] = poison.ward
        # The other half of the cure: the wheel's own POISONED status. Routed
        # through elements.cure so the ANTIDOTE cure-kind table stays the single
        # statement of what an antidote is allowed to clear — this file does not
        # get its own opinion about that.
        wheel_cleared = []
        if statuses is not None:
            from . import elements as _elements
            wheel_cleared = _elements.cure(statuses, "ANTIDOTE")["cured"]
        log.append(f"{cured['removed']} dose(s) cleared."
                   if cured["removed"] else "Nothing left to cure.")
        if wheel_cleared:
            log.append("The venom on the wound goes inert.")
        if poison.ward:
            log.append(f"Warded for {poison.ward} turns.")
        outcome = {"cleared": cured["removed"], "ward": poison.ward,
                   "statuses_cured": wheel_cleared,
                   "statuses": [s.to_dict() for s in (statuses or ())]}
    else:
        bar = POURS_INTO[p.kind]
        maximum = int(player.get(f"{bar}_max",
                                 config.STAMINA_MAX if bar == "stamina"
                                 else config.MANA_MAX))
        current = int(player.get(bar, 0))
        if current >= maximum:
            return _refuse("full_health" if p.kind == "HEALTH" else "full_focus")
        band = p.restores(maximum)
        restored = max(1, int(round(band * multiplier)))
        restored = min(restored, maximum - current)
        player[bar] = current + restored
        label = "health" if p.kind == "HEALTH" else "focus"
        log.append(f"{restored} {label} restored.")
        if multiplier < 1.0:
            log.append(f"The {ordinal(prior + 1)} {label} potion this fight — "
                       f"{int(multiplier * 100)}% of its band.")
        outcome = {"restored": restored, "bar": bar, "value": player[bar],
                   "max": maximum}

    pouch.spend(p.id)
    turn_state.sips[p.kind] = prior + 1
    turn_state.drunk_total += 1
    turn_state.drunk_this_turn = p.id

    return {
        "ok": True,
        "id": p.id, "name": p.name, "kind": p.kind, "strength": p.strength,
        "colour": p.colour, "vessel": p.vessel,
        "restored": restored,
        "multiplier": round(multiplier, 3),
        "applied": log,
        # The two lines the client must show, because they are the mechanic:
        "turn_spent": False,
        "must_still_cast": True,
        "prompt": "Down it goes. The turn is still yours — cast.",
        "turn": turn_state.turn,
        "held": pouch.count(p.id),
        "poison": poison.to_dict(),
        "player": {"stamina": player.get("stamina"), "mana": player.get("mana")},
        **outcome,
    }


def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def pouch_view(pouch: Pouch, *, player: dict | None = None,
               turn_state: TurnState | None = None,
               poison: Poison | None = None, encounter=None,
               statuses: list | None = None) -> dict:
    """Everything the potion belt needs to render, including WHY a greyed-out
    potion is greyed out. A disabled button with no reason is how a player
    concludes a mechanic is broken."""
    player = player or {}
    turn_state = turn_state or TurnState()
    poison = poison if poison is not None else Poison()
    sealed = finalexam.sealed(encounter, "ITEMS")
    # An antidote is live against EITHER poison model, and the belt has to agree
    # with `drink()` about that or it will grey out a potion that would in fact
    # work — which is how a player concludes an item is broken.
    poisoned = poison.active or any(getattr(s_, "id", "") == "POISONED"
                                    for s_ in (statuses or ()))
    rows = []
    for pid, held in sorted(pouch.counts.items(),
                            key=lambda kv: (KINDS.index(BY_ID[kv[0]].kind),
                                            STRENGTHS.index(BY_ID[kv[0]].strength))):
        if held <= 0:
            continue
        p = BY_ID[pid]
        reason = ""
        if sealed:
            reason = "Sealed here."
        elif not turn_state.may_drink:
            reason = REFUSALS["already"]
        elif p.kind == "ANTIDOTE" and not poisoned and not p.ward_turns:
            reason = REFUSALS["no_poison"]
        elif p.kind in ("HEALTH", "FOCUS"):
            bar = POURS_INTO[p.kind]
            maximum = int(player.get(f"{bar}_max", 0) or 0)
            if maximum and int(player.get(bar, 0)) >= maximum:
                reason = REFUSALS["full_health" if p.kind == "HEALTH"
                                  else "full_focus"]
        prior = int(turn_state.sips.get(p.kind, 0))
        row = p.to_dict()
        row.update({
            "held": held, "usable": not reason, "reason": reason,
            "next_multiplier": round(sip_multiplier(prior), 3),
        })
        if p.kind in ("HEALTH", "FOCUS"):
            bar = POURS_INTO[p.kind]
            maximum = int(player.get(f"{bar}_max",
                                     config.STAMINA_MAX if bar == "stamina"
                                     else config.MANA_MAX) or 1)
            row["would_restore"] = max(1, int(round(p.restores(maximum)
                                                    * sip_multiplier(prior))))
        rows.append(row)
    return {
        "potions": rows,
        "total": pouch.total(),
        "turn": turn_state.turn,
        "may_drink": (not sealed) and turn_state.may_drink,
        "sealed": sealed,
        "poison": poison.to_dict(),
        # The one sentence that teaches the mechanic, shown under the belt.
        "rule": "A draught is free. A second draught costs a cast.",
    }


# ---------------------------------------------------------------------------
# 8. Drops — the same economy items.roll_drop already runs
# ---------------------------------------------------------------------------
#
# Shape deliberately copied from items.roll_drop: a per-difficulty base chance,
# items.RANK_BONUS on top, luck as a linear term, one clamp. Two differences,
# both arguments rather than oversights:
#
#   * The base chances are roughly a quarter of the gear table's. Gear is the
#     reward loop; potions are ammunition, and ammunition that drops as often as
#     trophies stops being a decision.
#   * Rank matters LESS (RANK_WEIGHT below). A potion is a consumable you spend
#     to survive a fight you are losing, and paying it out mostly to the players
#     already scoring S would hand the most help to whoever needs it least.
#
# Both tables are monotonic non-decreasing across TIER_ORDER, and `_validate()`
# enforces that — a deeper area must never be stingier.

POTION_DROP_CHANCE = {
    "GUIDED": 0.04, "TUTORIAL": 0.06, "EASY": 0.09, "MEDIUM": 0.13,
    "HARD": 0.18, "ELITE": 0.24, "BOSS": 0.45,
}

CHEST_POTION_CHANCE = {
    "GUIDED": 0.35, "TUTORIAL": 0.42, "EASY": 0.52, "MEDIUM": 0.62,
    "HARD": 0.72, "ELITE": 0.82, "BOSS": 0.90,
}

# How many potions a chest holds when it holds any. Deep chests are worth
# walking to.
CHEST_COUNT = {
    "GUIDED": 1, "TUTORIAL": 1, "EASY": 1, "MEDIUM": 2,
    "HARD": 2, "ELITE": 3, "BOSS": 3,
}

RANK_WEIGHT = 0.4          # how much of items.RANK_BONUS a potion roll feels
LUCK_WEIGHT = 0.25         # items.roll_drop uses 0.5 for gear
MONSTER_CAP = 0.60         # a monster drop is rare and stays rare

# Strength weights, echoing the shape of items.RARITIES: common things are
# common. `depth` shifts the curve up exactly the way luck shifts the rarity
# curve in roll_drop, so the two tables behave recognisably alike.
STRENGTH_WEIGHT = {"minor": 100.0, "small": 46.0, "medium": 18.0, "hefty": 6.0}
DEPTH_SHIFT = 0.9

# Base appetite for each kind before the area has an opinion.
KIND_WEIGHT = {"HEALTH": 3.0, "FOCUS": 2.0, "ANTIDOTE": 1.0}

# What an area's affinity does to that appetite. Aesthetics and tactics agreeing:
# the rainforest is full of antidotes because the rainforest is full of poison,
# the volcano hands out health because the volcano hurts, the void hands out
# focus because a room with no signposts is a concentration problem. The void's
# mild antidote lean is the only trace in this file of the brief's SECONDARY
# advantage of void over poison — a nudge in a loot table, not an opposed pair.
#
# Unknown affinities bias nothing. That is the whole compatibility contract with
# whichever module ends up owning the element table.
AFFINITY_BIAS = {
    "poison":    {"ANTIDOTE": 2.6, "HEALTH": 1.0, "FOCUS": 0.8},
    "cold":      {"HEALTH": 1.4, "FOCUS": 1.0, "ANTIDOTE": 0.5},
    "fire":      {"HEALTH": 1.6, "FOCUS": 0.8, "ANTIDOTE": 0.5},
    "lightning": {"HEALTH": 1.0, "FOCUS": 1.6, "ANTIDOTE": 0.5},
    "void":      {"HEALTH": 0.9, "FOCUS": 1.8, "ANTIDOTE": 1.2},
    "brute":     {"HEALTH": 1.8, "FOCUS": 0.7, "ANTIDOTE": 0.6},
}

# A line of dressing so a potion found in the snow reads as a potion found in
# the snow. Pure flavour; nothing downstream branches on it.
AFFINITY_FLAVOUR = {
    "poison": "Corked with resin. The rainforest brews its own cure and hides it.",
    "cold": "Frozen half solid. It has to be warmed in both hands first.",
    "fire": "Ash-quenched glass, still faintly warm.",
    "lightning": "The stopper hums. Do not shake it.",
    "void": "You are fairly sure the bottle is there.",
    "brute": "A stoneware jug. Nothing subtle was ever kept in one.",
}


def drop_chance(*, difficulty: str, rank: str = "C", luck: float = 0.0,
                is_boss: bool = False) -> float:
    """The monster-drop probability, exposed so the balance audit and the
    tuning conversation read the same number the roll does."""
    base = POTION_DROP_CHANCE.get(difficulty, POTION_DROP_CHANCE["EASY"])
    base += items.RANK_BONUS.get(rank, 0.0) * RANK_WEIGHT
    base += float(luck) * LUCK_WEIGHT
    if is_boss:
        # A boss hands over supplies for the road, always. The same argument
        # items.roll_drop makes for the trophy.
        return 1.0
    return max(0.0, min(MONSTER_CAP, base))


def _kind_weights(affinity: str) -> dict:
    bias = AFFINITY_BIAS.get(str(affinity or "").strip().lower(), {})
    return {k: KIND_WEIGHT[k] * bias.get(k, 1.0) for k in KINDS}


def _pick(weighted: list, rng: random.Random):
    total = sum(w for _, w in weighted)
    if total <= 0:
        return weighted[0][0]
    pick = rng.random() * total
    for value, weight in weighted:
        pick -= weight
        if pick <= 0:
            return value
    return weighted[-1][0]


def pick_potion(*, difficulty: str, affinity: str = "", luck: float = 0.0,
                rng: random.Random | None = None, kind: str = "") -> str:
    """Which potion this area hands over. Kind first, then strength, because
    they are independent decisions: the area decides what it is full of, the
    depth decides how good it is."""
    rng = rng or random.Random()
    tier = TIER_INDEX.get(difficulty, TIER_INDEX["EASY"])
    depth = tier / (len(TIER_ORDER) - 1)

    weights = _kind_weights(affinity)
    pool = [(k, w) for k, w in weights.items() if available_at(difficulty, kind=k)]
    if kind:
        pool = [(k, w) for k, w in pool if k == kind]
    if not pool:
        # Nothing of the requested kind exists this shallow. Health from GUIDED
        # is the floor of the whole table, so there is always something.
        pool = [("HEALTH", 1.0)]
    chosen_kind = _pick(pool, rng)

    strengths = [s for s in STRENGTHS
                 if found_at(f"{chosen_kind.lower()}_{s}", difficulty)]
    weighted = []
    for s in strengths:
        i = STRENGTHS.index(s)
        weighted.append((s, STRENGTH_WEIGHT[s] * (1.0 + (depth + luck) * i * DEPTH_SHIFT)))
    chosen_strength = _pick(weighted, rng)
    return f"{chosen_kind.lower()}_{chosen_strength}"


def _found(potion_id: str, *, affinity: str, source: str) -> dict:
    p = BY_ID[potion_id]
    row = p.to_dict()
    row.update({
        "kind_of_drop": "potion",     # not `kind`: that is HEALTH/FOCUS/ANTIDOTE
        "source": source,
        "affinity": str(affinity or "").strip().lower(),
        "found_line": AFFINITY_FLAVOUR.get(
            str(affinity or "").strip().lower(), p.flavour),
    })
    return row


def roll_monster_drop(*, difficulty: str, rank: str = "C", luck: float = 0.0,
                      is_boss: bool = False, affinity: str = "",
                      rng: random.Random | None = None) -> dict | None:
    """A rare drop off a monster, or None.

    Returns the same `{"kind": "potion", "id": ...}` envelope engine._apply_outcome
    already branches on for `{"kind": "consumable"}`, so the drop handler needs
    one more elif and nothing else.
    """
    rng = rng or random.Random()
    if rng.random() > drop_chance(difficulty=difficulty, rank=rank, luck=luck,
                                  is_boss=is_boss):
        return None
    pid = pick_potion(difficulty=difficulty, affinity=affinity, luck=luck, rng=rng)
    return {"kind": "potion", "id": pid,
            **_found(pid, affinity=affinity, source="drop")}


def roll_chest(*, difficulty: str, luck: float = 0.0, affinity: str = "",
               rng: random.Random | None = None, count: int | None = None) -> list:
    """What a randomised chest holds. A list, possibly empty.

    Chests are the reliable half of the economy and monsters are the lottery
    half: a player who explores is never out of thimbles, and a player who only
    fights is occasionally out of everything. Exploring the map is the behaviour
    worth paying for, since the map is where the problems are.
    """
    rng = rng or random.Random()
    chance = CHEST_POTION_CHANCE.get(difficulty, CHEST_POTION_CHANCE["EASY"])
    chance = min(0.97, chance + float(luck) * LUCK_WEIGHT)
    if rng.random() > chance:
        return []
    n = CHEST_COUNT.get(difficulty, 1) if count is None else max(1, int(count))
    out = []
    for _ in range(n):
        pid = pick_potion(difficulty=difficulty, affinity=affinity, luck=luck, rng=rng)
        out.append({"kind": "potion", "id": pid,
                    **_found(pid, affinity=affinity, source="chest")})
    return out


# ---------------------------------------------------------------------------
# 9. Monsters drink too
# ---------------------------------------------------------------------------
#
# The brief: monsters can carry antidotes. Which ones SHOULD is the interesting
# half. The answer here is "the ones who live where the poison is", plus elites
# and bosses anywhere — a thing that has survived a poisoned region is a thing
# that worked out how to survive a poisoned region, and a boss has staff.
#
# And the asymmetry, which is the design decision worth defending: a monster's
# antidote COSTS IT ITS TURN, where the player's does not. That is not a
# balance oversight in the player's favour by accident; it is one on purpose.
# Poisoning something that can cure itself is therefore never wasted — the cure
# buys you a free turn, which is one more line of Python landed for nothing.
# The player is the one being taught. The monster is furniture with opinions.

MONSTER_ANTIDOTE_CHANCE = {
    "GUIDED": 0.0, "TUTORIAL": 0.0, "EASY": 0.10, "MEDIUM": 0.18,
    "HARD": 0.28, "ELITE": 0.45, "BOSS": 0.85,
}

# Away from poison country an antidote on a monster is an oddity, so it is
# scaled hard rather than removed: a Void creature with a vial is a nice
# surprise, a swamp full of them is a tax.
OFF_AFFINITY_SCALE = 0.35
POISON_AFFINITIES = frozenset({"poison"})


def carries_antidote(*, difficulty: str, affinity: str = "", is_boss: bool = False,
                     is_elite: bool = False,
                     rng: random.Random | None = None) -> int:
    """How many antidotes this monster is carrying. Usually zero."""
    rng = rng or random.Random()
    chance = MONSTER_ANTIDOTE_CHANCE.get(difficulty, 0.0)
    if str(affinity or "").strip().lower() not in POISON_AFFINITIES:
        chance *= OFF_AFFINITY_SCALE
    if is_elite and not is_boss:
        chance = min(0.9, chance * 1.5)
    if rng.random() > chance:
        return 0
    if is_boss:
        return 2 if rng.random() < 0.5 else 1
    return 1


def monster_cure(monster: dict, poison: Poison, *,
                 rng: random.Random | None = None) -> dict | None:
    """The monster drinks. Returns None when it does not, or would not.

    Call at the START of the monster's turn. The returned dict is a MOMENT: it
    carries the line to print, the sprite effect to play and `turn_spent: True`,
    because an enemy curing your poison is a thing that happens in front of the
    player or it may as well not have happened.
    """
    rng = rng or random.Random()
    held = int(monster.get("antidotes", 0) or 0)
    if held <= 0 or not poison.active:
        return None
    # It drinks when the poison is actually costing it something: a dose it will
    # feel, or two ticks of anything. A monster that swallows a vial over one
    # point of chip damage looks stupid, and the player notices.
    hp = int(monster.get("hp", 0) or 0)
    hp_max = max(1, int(monster.get("hp_max", hp or 1) or 1))
    pressure = poison.per_turn * max(1, len(poison.doses))
    if pressure < 2 and poison.per_turn * 3 < hp_max * 0.10:
        return None

    cured = poison_clear(poison, clears=0, ward_turns=1)
    monster["antidotes"] = held - 1
    # `display` is already "SEEN, the Hollow Set" wherever incantation.Enemy is
    # the source, so it is taken verbatim rather than re-decorated.
    display = str(monster.get("display", "") or "").strip()
    if display:
        who = display
    else:
        name = str(monster.get("name", "It")).upper()
        title = str(monster.get("title", "")).strip()
        who = f"{name}, {title}" if title else name
    line = (f"{who} tips a green vial down its throat. Your poison sloughs off "
            f"it — {cured['removed']} dose(s) gone. That was its turn.")
    return {
        "cured": True,
        "line": line,
        "effect": "antidote_cure",
        "removed": cured["removed"],
        "ward": cured["ward"],
        "antidotes_left": monster["antidotes"],
        # The consolation, said out loud, because it is the tactical point:
        "aside": "It spent its turn drinking. Yours is free.",
        "turn_spent": True,
        "poison": poison.to_dict(),
    }


# ---------------------------------------------------------------------------
# 10. Simulation — the argument, with real numbers
# ---------------------------------------------------------------------------
#
# The claim under test is the one at the top of the file: potions EXTEND a fight
# rather than skip it, and a full pouch buys more typing rather than less.
#
# The model is the engine's own economy, not an invented one. Damage to the
# enemy comes only from a correct cast. Damage to the player comes only from a
# WRONG cast, at config.STAMINA_LOSS_FAILED_SUBMIT, which is exactly how a
# player loses health in this game today — you are hurt by getting Python wrong,
# not by a clock. Poison is the one addition, and it lands on wrong casts too.
#
# `casts` is therefore the output that matters. It is the number of lines of
# Python the player typed, which is the number the whole game is trying to
# raise.

def _auto_drink(pouch: Pouch, turn_state: TurnState, player: dict,
                poison: Poison) -> dict | None:
    """A plausible player's potion policy, for the simulation only.

    Antidote when poison is doing real damage, otherwise health at a third of
    the bar, and always the smallest potion that covers the hole — hoarding the
    flagon is what a real player does and the simulation should not be more
    disciplined than one.
    """
    if not turn_state.may_drink:
        return None
    if poison.per_turn >= 3:
        for s in STRENGTHS:
            pid = f"antidote_{s}"
            if pouch.count(pid):
                return drink(pouch, pid, player=player, turn_state=turn_state,
                             poison=poison)
    maximum = int(player.get("stamina_max", config.STAMINA_MAX))
    missing = maximum - int(player.get("stamina", 0))
    if missing < max(3, maximum // 3):
        return None
    for s in STRENGTHS:
        pid = f"health_{s}"
        if pouch.count(pid) and BY_ID[pid].restores(maximum) >= missing:
            return drink(pouch, pid, player=player, turn_state=turn_state,
                         poison=poison)
    for s in reversed(STRENGTHS):
        pid = f"health_{s}"
        if pouch.count(pid):
            return drink(pouch, pid, player=player, turn_state=turn_state,
                         poison=poison)
    return None


def full_pouch() -> Pouch:
    """A pouch carrying the legal maximum of everything: 42 potions, and the
    hardest number in the balance argument. If THIS cannot trivialise a fight,
    nothing in the drop table can."""
    pouch = Pouch()
    for pid in POTION_IDS:
        pouch.add(pid, BY_ID[pid].cap)
    return pouch


def simulate(*, enemy_hp: int = 240, damage: int = 10, accuracy: float = 0.70,
             stamina_max: int = config.STAMINA_MAX,
             mana_max: int = config.MANA_MAX,
             pouch: Pouch | None = None, poison_on_miss: int = 0,
             poison_damage: int = 2, poison_turns: int = 3,
             max_turns: int = 600, seed: int = 7) -> dict:
    """One fight, turn by turn. Returns what it cost and what it taught."""
    rng = random.Random(seed)
    player = {"stamina": stamina_max, "stamina_max": stamina_max,
              "mana": mana_max, "mana_max": mana_max}
    pouch = pouch if pouch is not None else Pouch()
    turn_state = new_fight()
    poison = Poison()
    hp = int(enemy_hp)
    misses = 0
    healed = 0
    poison_damage_taken = 0
    low_water = stamina_max

    while turn_state.turn <= max_turns:
        # 1. poison ticks first: a potion cannot rewind a tick that landed.
        tick = poison_tick(poison)
        if tick["damage"]:
            player["stamina"] -= tick["damage"]
            poison_damage_taken += tick["damage"]
            if player["stamina"] <= 0:
                break
        # 2. the draught, alongside the attack and not instead of it.
        sip = _auto_drink(pouch, turn_state, player, poison)
        if sip and sip.get("ok"):
            healed += int(sip.get("restored", 0) or 0)
        # 3. the cast. This is the only thing that damages the enemy, ever.
        correct = rng.random() < accuracy
        if correct:
            hp -= damage
        else:
            misses += 1
            player["stamina"] -= config.STAMINA_LOSS_FAILED_SUBMIT
            if poison_on_miss and misses % poison_on_miss == 0:
                poison_apply(poison, damage=poison_damage, turns=poison_turns,
                             source="ambient")
        low_water = min(low_water, player["stamina"])
        cast_resolved(turn_state, correct=correct)
        if hp <= 0 or player["stamina"] <= 0:
            break

    won = hp <= 0
    return {
        "outcome": "won" if won else "down",
        "casts": turn_state.casts,
        "correct_casts": turn_state.casts - misses,
        "wasted_casts": misses,
        "turns": turn_state.turn - 1,
        "potions_drunk": turn_state.drunk_total,
        "health_restored": healed,
        "poison_damage": poison_damage_taken,
        "health_low_water": low_water,
        "enemy_hp_left": max(0, hp),
        "potions_left": pouch.total(),
    }


SCENARIOS = {
    # A fair fight: the player's element matches, no potions in the bag.
    "matched_no_potions": dict(damage=16, poison_on_miss=0),
    # The same fight with a full pouch. The point of this row is that it is NOT
    # shorter than the one above.
    "matched_full_pouch": dict(damage=16, poison_on_miss=0, pouch="full"),
    # Elemental disadvantage: damage cut, nothing else changed. The brief's rule
    # is that this makes a fight LONGER, never unwinnable.
    "disadvantaged_no_potions": dict(damage=5, poison_on_miss=0),
    "disadvantaged_full_pouch": dict(damage=5, poison_on_miss=0, pouch="full"),
    # Rainforest: disadvantaged and poisoned, which is the worst honest case.
    "poisoned_no_potions": dict(damage=5, poison_on_miss=3),
    "poisoned_full_pouch": dict(damage=5, poison_on_miss=3, pouch="full"),
    # THE NO-DEAD-END ROW. Same elemental disadvantage, same empty bag, a player
    # who has actually learned the moveset. The rule is that correct Python wins
    # this fight with nothing in the pouch at all, and `_validate()` enforces it.
    # Potions are what cover for Python you have not learned yet; they are never
    # the thing standing between a fluent player and a clear.
    "disadvantaged_accurate_no_potions": dict(damage=5, accuracy=0.92,
                                              poison_on_miss=0),
    "poisoned_accurate_no_potions": dict(damage=5, accuracy=0.92,
                                         poison_on_miss=3),
}


def simulate_all(*, seed: int = 7) -> dict:
    out = {}
    for name, kwargs in SCENARIOS.items():
        kwargs = dict(kwargs)
        if kwargs.pop("pouch", "") == "full":
            kwargs["pouch"] = full_pouch()
        out[name] = simulate(seed=seed, **kwargs)
    return out


def break_even_accuracy(*, seeds=range(1, 41), win_rate: float = 0.9,
                        step: float = 0.02, **scenario) -> float:
    """The lowest accuracy at which a player clears this fight `win_rate` of the
    time. The honest way to state what an elemental disadvantage costs and what
    a pouch buys back, in the only unit that matters: how right your Python has
    to be.
    """
    accuracy = 0.40
    while accuracy <= 1.0001:
        kwargs = dict(scenario)
        kwargs.pop("accuracy", None)
        pouch_spec = kwargs.pop("pouch", "")
        wins = 0
        for seed in seeds:
            if pouch_spec == "full":
                kwargs["pouch"] = full_pouch()
            wins += simulate(seed=seed, accuracy=min(1.0, accuracy),
                             **kwargs)["outcome"] == "won"
        if wins / len(list(seeds)) >= win_rate:
            return round(min(1.0, accuracy), 2)
        accuracy += step
    return 1.0


def simulate_sweep(*, seeds=range(1, 41)) -> dict:
    """The same six scenarios across forty different players' luck.

    A single seed is an anecdote. The means below are the numbers the balance
    argument actually rests on, and the per-seed runs are what `_validate()`
    checks the invariant against — every seed, not the convenient one.

    Note the runs are paired: for a given seed the cast sequence is IDENTICAL
    with and without the pouch, because drinking consumes no randomness. So the
    comparison is not statistical, it is the same fight twice with one variable
    changed.
    """
    rows: dict = {name: [] for name in SCENARIOS}
    for seed in seeds:
        for name, kwargs in SCENARIOS.items():
            kwargs = dict(kwargs)
            if kwargs.pop("pouch", "") == "full":
                kwargs["pouch"] = full_pouch()
            rows[name].append(simulate(seed=seed, **kwargs))
    out = {}
    for name, runs in rows.items():
        n = len(runs)
        out[name] = {
            "runs": n,
            "won": sum(1 for r in runs if r["outcome"] == "won"),
            "mean_casts": round(sum(r["casts"] for r in runs) / n, 1),
            "min_casts": min(r["casts"] for r in runs),
            "max_casts": max(r["casts"] for r in runs),
            "mean_potions_drunk": round(
                sum(r["potions_drunk"] for r in runs) / n, 1),
            "mean_health_restored": round(
                sum(r["health_restored"] for r in runs) / n, 1),
        }
    out["_pairs"] = {}
    for bare, full in (("matched_no_potions", "matched_full_pouch"),
                       ("disadvantaged_no_potions", "disadvantaged_full_pouch"),
                       ("poisoned_no_potions", "poisoned_full_pouch")):
        deltas = [f["casts"] - b["casts"]
                  for b, f in zip(rows[bare], rows[full])]
        out["_pairs"][full] = {
            "extra_casts_mean": round(sum(deltas) / len(deltas), 1),
            "extra_casts_min": min(deltas),          # must never be negative
            "extra_casts_max": max(deltas),
        }
    out["_rows"] = rows
    return out


# ---------------------------------------------------------------------------
# 11. Wiring — where the engine and the client call in
# ---------------------------------------------------------------------------
#
# Written in the shape finalexam.ENGINE_HOOKS uses, so the integration is a list
# to work through rather than a thing to infer. Nothing below requires editing
# this file. Units, everywhere: HEALTH restores points of `player["stamina"]`,
# FOCUS restores points of `player["mana"]`, poison is points of stamina PER
# TURN, ward and dose durations are TURNS, drop chances are probabilities in
# [0, 1], and `difficulty` is one of TIER_ORDER.

WIRING: tuple = (
    {"site": "engine.DEFAULT_STATE",
     "do": 'add `"potions": {}` — the pouch, keyed by potion id',
     "call": "potions.POUCH_STATE_KEY"},
    {"site": "engine.Encounter",
     "do": "add two fields: `potion_turn: dict` and `poison: dict`, both "
           "default_factory=dict. They are already JSON, so asdict/to_dict and "
           "the save layer need no changes.",
     "call": "potions.TurnState.to_dict() / potions.Poison.to_dict()"},
    {"site": "engine.Game.use_potion(key)  [new, beside use_consumable]",
     "do": "load Pouch.from_state(self.state), TurnState.from_dict(enc.potion_turn) "
           "and Poison.from_dict(enc.poison); call drink(); write all three back "
           "and self._write_encounter(enc). Do NOT advance any turn counter here.",
     "call": "potions.drink(pouch, key, player=self.state['player'], "
             "turn_state=ts, poison=poison, encounter=enc, "
             "statuses=player_statuses)"},
    {"site": "engine.Game.submit / wherever a cast is graded",
     "do": "after the result is scored — correct OR wrong — advance the turn. "
           "This is the other half of the turn rule and the feature does not "
           "work without it.",
     "call": "potions.cast_resolved(ts, correct=bool(result_ok))"},
    {"site": "engine.Game.start_encounter",
     "do": "enc.potion_turn = potions.new_fight().to_dict(); enc.poison = {}",
     "call": "potions.new_fight()"},
    {"site": "engine.Game._apply_outcome  [beside items.roll_drop]",
     "do": "roll a potion as well as the gear drop; they are independent, and a "
           "fight may pay both.",
     "call": "potions.roll_monster_drop(difficulty=problem.difficulty, "
             "rank=rank, luck=fx.get('loot_luck', 0.0), is_boss=bool(enc.boss_id), "
             "affinity=region_affinity)"},
    {"site": "engine.Game._apply_outcome  [the drop handler at the "
             "`kind == 'consumable'` branch]",
     "do": 'add an `elif drop["kind"] == "potion"` arm that calls grant() and '
           "surfaces `overflow` to the player",
     "call": "potions.grant(self.state, drop)"},
    {"site": "wherever a chest is opened (worldgen / quests / dungeons)",
     "do": "roll the chest's potions and grant each one",
     "call": "potions.roll_chest(difficulty=room_difficulty, "
             "luck=fx.get('loot_luck', 0.0), affinity=region_affinity)"},
    {"site": "engine.Game._encounter_payload",
     "do": 'payload["pouch"] = potions.pouch_view(...) — it already carries its '
           "own `sealed` flag and per-potion `reason`, so no extra seal check is "
           "needed at the payload",
     "call": "potions.pouch_view(pouch, player=player, turn_state=ts, "
             "poison=poison, encounter=enc, statuses=player_statuses)"},
    {"site": "the enemy's turn, wherever the engine resolves one",
     "do": "tick the player's poison FIRST, then let a carrying monster cure "
           "itself. A cure that returns a dict means the monster spent its turn; "
           "print `line`, play `effect`, and do not also let it attack.",
     "call": "potions.poison_tick(poison) / potions.monster_cure(monster, "
             "monster_poison)"},
    {"site": "wherever an enemy is spawned",
     "do": 'stash `monster["antidotes"] = potions.carries_antidote(...)` on the '
           "enemy record. Usually zero; poison regions and elites are where it "
           "is not.",
     "call": "potions.carries_antidote(difficulty=..., affinity=..., "
             "is_boss=..., is_elite=...)"},
    {"site": "the client's battle HUD",
     "do": "render `payload['pouch']['potions']` as a belt. Show `rule` under "
           "it, grey a potion out with its `reason`, and after a drink show "
           "`prompt` — the player must understand that the turn is still theirs "
           "or the mechanic is invisible.",
     "call": "no server call; the payload carries everything"},
)


# ---------------------------------------------------------------------------
# 12. Self-check
# ---------------------------------------------------------------------------
#
# Everything below would reach the player as a broken pouch rather than as an
# exception, so it is checked at import and the module refuses to load if any of
# it is false. The list is the promise this file makes to the rest of the game.

def _validate() -> list:
    problems: list = []

    # -- the ladder this module mirrors has not drifted
    if set(TIER_ORDER) != set(items.DIFFICULTY_DROP_CHANCE):
        problems.append("TIER_ORDER disagrees with items.DIFFICULTY_DROP_CHANCE")

    # -- the OTHER mirrored number: the poison stacking rule. Imported here and
    # nowhere else, so the two poison models can never again disagree about how
    # deep poison goes without this failing at import.
    try:
        from . import elements as _elements
    except Exception:                      # pragma: no cover - standalone use
        _elements = None
    if _elements is not None:
        wheel_stacks = _elements.STATUSES["POISONED"].max_stacks
        if wheel_stacks != MAX_DOSES:
            problems.append(
                f"poison stacking has drifted: potions caps at {MAX_DOSES}, "
                f"elements.STATUSES['POISONED'] caps at {wheel_stacks}")
        if "POISONED" not in _elements.CURES.get("ANTIDOTE", ()):
            problems.append("an ANTIDOTE no longer cures the wheel's POISONED")
        # The stated cap must actually bind.
        deep = Poison()
        for _ in range(MAX_DOSES + 4):
            poison_apply(deep, damage=2, turns=3)
        if len(deep.doses) > MAX_DOSES:
            problems.append("poison stacked past MAX_DOSES")
        # And an antidote must clear BOTH representations, not one.
        both = Poison()
        poison_apply(both, damage=2, turns=3)
        wheel: list = []
        _elements.inflict(wheel, "POISONED")
        cured = drink(full_pouch(), "antidote_medium",
                      player={"stamina": 5, "stamina_max": config.STAMINA_MAX,
                              "mana": 5, "mana_max": config.MANA_MAX},
                      turn_state=new_fight(), poison=both, statuses=wheel)
        if not cured.get("ok") or both.active or wheel:
            problems.append("an antidote did not clear both kinds of poison")

    # -- every kind x strength exists exactly once, and nothing else does
    expected = {f"{k.lower()}_{s}" for k in KINDS for s in STRENGTHS}
    if set(BY_ID) != expected:
        problems.append("the catalogue is not exactly three kinds x four strengths")
    if len({p.name for p in CATALOGUE}) != len(CATALOGUE):
        problems.append("two potions share a name")

    # -- A. every potion is reachable from some area, and hefty is not
    for p in CATALOGUE:
        if p.min_tier not in TIER_INDEX:
            problems.append(f"{p.id}: unknown min_tier {p.min_tier}")
            continue
        reachable = [t for t in TIER_ORDER
                     if found_at(p.id, t) and POTION_DROP_CHANCE[t] > 0]
        if not reachable:
            problems.append(f"{p.id} can never drop anywhere")
        if p.strength == "hefty" and TIER_INDEX[p.min_tier] < TIER_INDEX["ELITE"]:
            problems.append(f"{p.id} is hefty and findable before ELITE")
        if p.strength == "minor" and TIER_INDEX[p.min_tier] > TIER_INDEX["EASY"]:
            problems.append(f"{p.id} is minor and hidden past EASY")

    # -- the safety argument: nothing here touches an enemy or an answer
    allowed = {"stamina", "mana", "poison"}
    for p in CATALOGUE:
        stray = set(p.effect_keys) - allowed
        if stray:
            problems.append(f"{p.id} touches {sorted(stray)}")

    # -- restoration is monotonic in strength and never a full heal, at every
    # bar size a build can actually reach
    for maximum in (10, config.STAMINA_MAX, config.MANA_MAX, 40, 60, 120):
        for kind in ("HEALTH", "FOCUS"):
            values = [band_restore(kind, s, maximum) for s in STRENGTHS]
            if values != sorted(values):
                problems.append(f"{kind} restore is not monotonic at max {maximum}")
            if values[-1] > int(maximum * CEILING_FRACTION) and maximum >= 10:
                problems.append(f"{kind} hefty exceeds the ceiling at max {maximum}")
            if values[-1] >= maximum:
                problems.append(f"{kind} hefty is a full heal at max {maximum}")

    # -- B. drop rates rise with difficulty and never fall
    for table, label in ((POTION_DROP_CHANCE, "monster"),
                         (CHEST_POTION_CHANCE, "chest"),
                         (MONSTER_ANTIDOTE_CHANCE, "antidote")):
        series = [table[t] for t in TIER_ORDER]
        if series != sorted(series):
            problems.append(f"{label} drop chance is not monotonic in difficulty")
    counts = [CHEST_COUNT[t] for t in TIER_ORDER]
    if counts != sorted(counts):
        problems.append("chest count is not monotonic in difficulty")

    # -- E. the caps are real and get tighter as the potion gets stronger
    caps = [CARRY_CAP[s] for s in STRENGTHS]
    if caps != sorted(caps, reverse=True) or len(set(caps)) != len(caps):
        problems.append("carry caps do not tighten with strength")
    if not (0 < SIP_FLOOR < SIP_FALLOFF < 1.0):
        problems.append("the in-fight falloff does not diminish")

    # -- C. the turn rule holds: one draught, and only a cast clears it
    pouch = full_pouch()
    state = new_fight()
    player = {"stamina": 1, "stamina_max": config.STAMINA_MAX,
              "mana": 1, "mana_max": config.MANA_MAX}
    first = drink(pouch, "health_minor", player=player, turn_state=state)
    second = drink(pouch, "health_small", player=player, turn_state=state)
    if not first.get("ok"):
        problems.append("the first draught of a turn was refused")
    if first.get("turn_spent") is not False:
        problems.append("drinking reported itself as a turn")
    if second.get("ok") or second.get("error") != "already":
        problems.append("a second draught was allowed without a cast")
    cast_resolved(state)
    third = drink(pouch, "health_small", player=player, turn_state=state)
    if not third.get("ok"):
        problems.append("a cast did not return the draught")

    # -- the seal: nothing works in Timed Practical Mode, and there is one way to ask
    class _Exam:
        mode = config.MODE_INTERVIEW
        boss_id = ""
        holdout = False

    sealed_try = drink(full_pouch(), "health_hefty",
                       player={"stamina": 1, "stamina_max": 20},
                       turn_state=new_fight(), encounter=_Exam())
    if sealed_try.get("error") != "sealed":
        problems.append("a potion worked in Timed Practical Mode")

    # -- D. a monster with an antidote cures out loud, and it costs it the turn
    poison = Poison()
    poison_apply(poison, damage=4, turns=4, source="test")
    moment = monster_cure({"name": "mirebound", "title": "the Drowned Warden",
                           "antidotes": 1, "hp": 60, "hp_max": 60}, poison)
    if not moment or not moment.get("line") or not moment.get("turn_spent"):
        problems.append("a monster cured itself silently, or for free")
    if poison.active:
        problems.append("a monster's antidote did not clear the poison")

    # -- the pedagogy: potions never shorten a fight, and always buy more typing.
    # Checked across every seed in the sweep rather than a convenient one.
    sweep = simulate_sweep(seeds=range(1, 41))
    rows = sweep["_rows"]
    for bare_name, full_name in (("matched_no_potions", "matched_full_pouch"),
                                 ("disadvantaged_no_potions",
                                  "disadvantaged_full_pouch"),
                                 ("poisoned_no_potions", "poisoned_full_pouch")):
        for bare, full in zip(rows[bare_name], rows[full_name]):
            if full["casts"] < bare["casts"]:
                problems.append(f"{full_name} typed less Python than {bare_name}")
                break
            if full["enemy_hp_left"] > bare["enemy_hp_left"]:
                problems.append(f"{full_name} did less damage than {bare_name}")
                break
    # Elemental disadvantage must LENGTHEN a fight, and must still be winnable
    # with a pouch. Both halves of the brief's rule, in one place.
    if sweep["disadvantaged_full_pouch"]["mean_casts"] <= \
            sweep["matched_no_potions"]["mean_casts"]:
        problems.append("elemental disadvantage did not lengthen the fight")
    if sweep["disadvantaged_full_pouch"]["won"] == 0:
        problems.append("elemental disadvantage was unwinnable even with a pouch")
    # LEARNING NEVER DEAD-ENDS. Wrong element, empty pouch, correct Python: the
    # player must still be able to win. If this ever fails, the elemental layer
    # has stopped being a tax on time and started being a lock.
    accurate = sweep["disadvantaged_accurate_no_potions"]
    if accurate["won"] < accurate["runs"] * 0.9:
        problems.append("the wrong element beat correct Python with no potions")
    # The rainforest at the wrong element while poisoned is deliberately the
    # nastiest honest case in the game and it sits near the edge on purpose: a
    # clear here should feel earned. What it may never be is a lock, so the bar
    # is "a fluent player wins this a quarter of the time with an empty bag",
    # not "comfortably".
    drowned = sweep["poisoned_accurate_no_potions"]
    if drowned["won"] < drowned["runs"] * 0.25:
        problems.append("poison plus the wrong element was a lock, not a tax")

    # -- a fight cannot be won without typing: with no casts, nothing dies
    nothing = simulate(accuracy=0.0, pouch=full_pouch(), max_turns=200)
    if nothing["outcome"] == "won" or nothing["enemy_hp_left"] <= 0:
        problems.append("a fight was won without a correct cast")

    return problems


def self_check() -> dict:
    """The numbers, for `python -m gauntlet.potions` and for the balance
    conversation that will inevitably follow."""
    runs = simulate_all()
    bands = {
        s: {"health@%d" % config.STAMINA_MAX: band_restore("HEALTH", s,
                                                           config.STAMINA_MAX),
            "health@40": band_restore("HEALTH", s, 40),
            "focus@%d" % config.MANA_MAX: band_restore("FOCUS", s, config.MANA_MAX),
            "focus@60": band_restore("FOCUS", s, 60),
            "cap": CARRY_CAP[s],
            "found_from": {k: BY_ID[f"{k.lower()}_{s}"].min_tier for k in KINDS}}
        for s in STRENGTHS
    }
    pouch = full_pouch()
    # What the whole legal pouch is actually worth in one fight, once the
    # in-fight falloff has had its say. This is the number that answers "why
    # can't I carry forty hefty potions and stop thinking".
    best = 0.0
    for i, pid in enumerate(sorted(
            [p for p in POTION_IDS if BY_ID[p].kind == "HEALTH"
             for _ in range(BY_ID[p].cap)],
            key=lambda p: -BY_ID[p].restores(config.STAMINA_MAX))):
        best += BY_ID[pid].restores(config.STAMINA_MAX) * sip_multiplier(i)
    return {
        "potions": len(CATALOGUE),
        "kinds": list(KINDS),
        "strengths": list(STRENGTHS),
        "bands": bands,
        "drop_chance": {t: round(drop_chance(difficulty=t), 3) for t in TIER_ORDER},
        "chest_chance": {t: CHEST_POTION_CHANCE[t] for t in TIER_ORDER},
        "monster_antidote_chance": dict(MONSTER_ANTIDOTE_CHANCE),
        "full_pouch_potions": pouch.total(),
        "full_pouch_health_value": round(best, 1),
        "base_health_bar": config.STAMINA_MAX,
        "one_draught_per_turn": True,
        "turn_advances_only_on_cast": True,
        "break_even_accuracy": {
            "matched_no_potions": break_even_accuracy(damage=16),
            "disadvantaged_no_potions": break_even_accuracy(damage=5),
            "disadvantaged_full_pouch": break_even_accuracy(damage=5,
                                                            pouch="full"),
            "poisoned_no_potions": break_even_accuracy(damage=5,
                                                       poison_on_miss=3),
            "poisoned_full_pouch": break_even_accuracy(damage=5, poison_on_miss=3,
                                                       pouch="full"),
        },
        "simulation": runs,
        "simulation_sweep": {k: v for k, v in
                             simulate_sweep(seeds=range(1, 41)).items()
                             if k != "_rows"},
        "problems": _PROBLEMS,
        "ok": not _PROBLEMS,
    }


_PROBLEMS = _validate()
if _PROBLEMS:                                   # pragma: no cover - authored data
    raise ValueError("gauntlet.potions is inconsistent: " + "; ".join(_PROBLEMS))


if __name__ == "__main__":                      # pragma: no cover
    print(json.dumps(self_check(), indent=2))
