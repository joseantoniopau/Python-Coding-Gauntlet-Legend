"""The apex hunters: one per region, and the way they come for you.

    "There should be a random spawn uber monster that randomly spawns per area
     that is very difficult for that area, and actively but slowly tries to hunt
     down the player. If the player is new to that area it should be a very hard
     fight, once the player upgrades for that area it should be a normal to hard
     fight."

That last sentence is the whole design and it is worth saying back more sharply
than it was said: THE APEX SCALES AGAINST YOUR PREPARATION FOR THIS AREA, NOT
AGAINST YOUR LEVEL. Nothing in this module reads `xp`, `level`, `mastery` or any
skill number, and `self_check` proves it by grepping its own source. What it
reads is five things you could only have got by doing the area's work:

    the element you strike with        elements.strike_element / items.py
    the rung you strike at             forge.METALS, forge.RUNG_BY_ID
    what you are wearing against it    elements.armour_from_effects
    which companion you brought        pets.TIERS
    what is in the pouch               potions.STRENGTH_BAND

A level is a record of time spent. Those five are a record of ATTENTION spent —
on this place, on its metal, on its weather. Scaling against them turns the apex
into a mirror: the readout it hands back is a list of the things you have not
done here yet, and the fight is the practical exam on the one you skipped.

WHAT AN APEX IS FOR, PEDAGOGICALLY
----------------------------------
An area teaches a gear lesson: this ground is lightning, so do not swing
lightning at it, and wear something that does not conduct. Ordinary rooms teach
that lesson gently, over many small fights, and a player can coast through them
wearing the wrong thing and never notice. The apex is the version of that lesson
you cannot coast through, because it is long, and length is the only currency
this game has. Per RULE ONE:

    THE PYTHON TYPING IS THE ATTACK. A harder fight is MORE TYPING, not a
    different kind of challenge. Nothing in this module invents a mechanic, a
    dodge, a timer or a minigame. It sets how many times you type the idiom.

So an apex is authored in CASTS, not in hit points. Hit points are derived at
the moment the fight starts, from the casts the design wants and the damage this
particular player's loadout actually does. See `scale_for`.

THE ESCAPE, WHICH WAS DESIGNED FIRST
------------------------------------
Section D of this file is not the safety section, it is the FIRST section that
was written, and every number after it was chosen to fit inside it. The rule
from the brief:

    LEARNING NEVER DEAD-ENDS. A hunter may never trap, corner or soft-lock a
    player, and a player who cannot beat it must always be able to leave.

Stated as arithmetic rather than as intent, because intent does not survive a
tuning pass:

    G1  APEX_MAX_SPEED (74 px/s) < PLAYER_WALK_SPEED (112 px/s), always, in
        every state, for every apex. Walking away is not a skill check. It is
        subtraction.
    G2  Fleeing a started fight ALWAYS succeeds. No roll. Turn one included.
    G3  Leaving the region always works and the apex never crosses the boundary.
    G4  It never spawns where you would be cornered, and an active hunt fades
        the instant your reachable ground drops below MIN_FREE_TILES.
    G5  It is an overworld creature. It does not exist inside a dungeon and a
        hunt carried to a dungeon threshold goes DORMANT at the door.
    G6  It never takes a capability, seals an exit, destroys an item, spends
        your gold, touches mastery, or blocks a save. It takes TIME and nothing
        else.
    G7  Below LOW_HEALTH_FRACTION of your bar it will not enter CLOSING. It
        holds at TRACKING and you get to walk out.
    G8  Every landed cast does at least `elements.MIN_DAMAGE`, so no fight is
        infinite even when every guarantee above has been declined.

`hunt_step` checks the guarantees BEFORE it advances the chase, and the comment
there says the thing this module most needs said: WHEN A GUARANTEE AND THE DRAMA
DISAGREE, THE GUARANTEE WINS AND THE CHASE ENDS. An apex that cornered somebody
once would be an apex every player learns to avoid the area over, and an avoided
area is an untaught lesson.

THE FIRST MEETING IS SUPPOSED TO BE A DEFEAT
--------------------------------------------
At readiness zero an apex is TWICE as long as it is at readiness a hundred, and
hits harder into the bargain. That is not a fight the design expects you to win;
it is a fight the design expects you to LOOK AT and leave, which is why leaving
is free and why the telegraph starts twenty seconds before the creature exists.
The intended shape of a first encounter is: hear it, see it, try it, run, go and
fix the thing it showed you was missing, come back. The second meeting is half
the length at 1.00x, and that is a real fight you can win.

HOW LONG IS TWICE AS LONG: THE CHAPTER RAMP
-------------------------------------------
It used to be twenty-six casts prepared and fifty-two unprepared IN EVERY
REGION, which meant the first hunter a player ever meets and the last one before
the portal cost the same afternoon. Section B2 fixes that. Length now ramps
along `curriculum.CHAPTERS`, three casts a rung:

    chapter I    14 casts prepared   28 unprepared   strike 1.25x  TEACHES
    chapter V    26 casts prepared   52 unprepared   strike 1.37x  TESTS
    chapter XI   44 casts prepared   88 unprepared   strike 1.55x  TESTS

Chapter V is the anchor and it is exactly what this file always said — the two
constants CASTS_AT_READY and CASTS_AT_UNREADY keep their names and their values
and now describe one rung instead of all eleven. Fourteen is inside the ordinary
elite band this game already uses, which is the whole of section B3: an early
apex is an ORDINARY-LENGTH FIGHT WEARING AN EXAM SHEET, short enough to lose,
read, fix and come back to in one sitting, and only the later ones are long
enough to be an occasion.

The chapter is read off the GROUND — `curriculum.CHAPTERS[i].region`, the map's
own statement about which chapter is taught where — and never off the player. A
player who walks into the Graph Wastes during chapter III meets a chapter-VIII
apex at full chapter-VIII length. Two lines:

    THE CHAPTER SAYS HOW BIG THE PLACE IS.
    READINESS SAYS WHERE IN THE PLACE YOU LAND.

Fighting all seventeen once costs 520 landed lines prepared and 1040 unprepared.
The flat design cost 442 and 884, so the total barely moved; what changed is
that the first one is now 46% cheaper and the last one 69% dearer.

WHAT THIS MODULE DOES NOT OWN
-----------------------------
It has no opinion about isolation. `finalexam.sealed` is the one capability
check in this game and this file does not form a second one: callers pass
`build_sealed=` down to `elements.resolve_damage` exactly as they already do,
and a sealed run simply never spawns an apex at all (`SPAWNS_WHILE_SEALED`).

It grants no mastery and returns no skill delta, for the same reason
`elements.py` does not: mastery is earned by casting, and the casting already
happened, one cast at a time, and was already paid for.

It does not count those casts either, and that is worth saying plainly because
it was once read as "nobody counts them". `Scaling.target_casts` says how many
LANDED LINES this apex is long; `engine.Game` keeps the tally, in the open
fight's `casts`, and `hunt_resolve` pays a bounty only when the tally reaches
the target. The client is told the same two numbers through `hunt_view()["fight"]`
so its bar and the engine's arithmetic cannot drift. A POST claiming a kill is
refused and the fight is LEFT STANDING — walking away is the free door, and it
is still free.

It draws nothing. `Apex.sprite` is a NEW key nobody has authored yet and
`Apex.sprite_fallback` is an existing `web/js/bosses.js` archetype that resolves
today, so the creature has a face the hour it is wired and a better one later.
`scripts/verify/apex.mjs` measures that seam.

It does not move anything either. `hunt_step` is the authority on the chase and
`web/js/overworld.js` mirrors it frame by frame; the contract between them is
`client_payload()` and nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import curriculum, elements, forge, world

__all__ = [
    "Apex", "APEXES", "APEX_BY_ID", "APEX_BY_REGION", "apex_for",
    "EXAM_COMPONENTS", "ELEMENTAL_EXAM", "NEUTRAL_EXAM", "exam_weights",
    "Loadout", "Readiness", "readiness", "readiness_from_game",
    "best_available", "ELEMENT_CREDIT",
    "BANDS", "band_for",
    "Scaling", "scale_for", "expected_cast_damage",
    "CASTS_AT_READY", "CASTS_AT_UNREADY", "STRIKE_AT_READY", "STRIKE_AT_UNREADY",
    "CHAPTERS", "CHAPTER_COUNT", "CHAPTER_ANCHOR", "CHAPTER_FOR_REGION",
    "CASTS_PER_CHAPTER", "UNREADY_RATIO", "STRIKE_AT_UNREADY_FLOOR",
    "TEACHING_CHAPTERS", "TEACHES", "TESTS",
    "chapter_for_region", "chapter_view", "casts_at_ready", "casts_at_unready",
    "strike_at_unready", "stance_for_chapter", "pace_for", "ramp_table",
    "playthrough_cost",
    "HUNT_STATES", "STATE_SPEED", "Hunt", "Moment", "new_hunt", "spawn_check",
    "hunt_step",
    "telegraph", "TELEGRAPH",
    "PLAYER_WALK_SPEED", "APEX_MAX_SPEED", "SPEED_MARGIN",
    "ROAM_FLOOR_PX", "ROAM_PATIENCE_SECONDS",
    "escape_guarantees", "can_flee", "flee", "leave_region", "corner_check",
    "Bounty", "bounty", "TROPHIES", "trophy_for",
    "lesson_for", "curve", "client_payload", "self_check",
]

# ---------------------------------------------------------------------------
# Units, borrowed rather than reinvented
# ---------------------------------------------------------------------------
#
# Everything spatial in this file is in SOURCE PIXELS, which is what
# web/js/overworld.js is in. A tile is sixteen of them. Two numbers below are
# read straight out of that file and must not drift from it; `self_check`
# reports them so a reviewer can diff by eye.

TILE = 16                     # tiles.TILE_SIZE
PLAYER_WALK_SPEED = 112.0     # px/s. overworld.js, "the player walks at 112"

# The calibration constant from `incantation.DAMAGE_UNIT` (11.0, its own
# comment calls it "the MEASURED median of an ordinary cast") times the weight
# of a competent-but-unremarkable cast, ~1.18 of a 0.55..3.00 range. Copied
# rather than imported because `incantation` imports half the world and this
# module is deliberately loadable on its own — the same independence
# `bestiary.py` keeps from it. `_damage_unit_drift` re-checks the copy against
# the live number whenever that module happens to be importable and `self_check`
# FAILS on drift, so this cannot rot in silence the way a copied constant
# usually does.
CAST_DAMAGE_REFERENCE = 13.0
_DAMAGE_UNIT_EXPECTED = 11.0

# Region order IS region tier. world.REGIONS is authored in unlock order and
# `numeral` agrees with it, so an index is the cheapest honest depth number
# available and it stays correct when somebody inserts a region.
REGION_INDEX = {r["id"]: i for i, r in enumerate(world.REGIONS)}


def _region_index(region_id: str) -> int:
    return REGION_INDEX.get(region_id, 0)


# ---------------------------------------------------------------------------
# A. The seventeen
# ---------------------------------------------------------------------------
#
# One per region, with no exceptions and no "this one is a town so it is
# exempt". A region with nothing hunting it is a region with no pressure in it,
# and the brief asked for presence.
#
# WHAT IS AUTHORED HERE AND WHAT IS DERIVED
#
#   authored   name, silhouette, why it is here, what it is testing, the tell,
#              the trophy, the exam weights, the sprite keys
#   derived    element (from elements.REGION_AFFINITIES — the ground decides,
#              exactly as it decides for every other creature in the game),
#              required rung (from forge.METALS), exam difficulty (from depth)
#
# Deriving the element is the important half. An apex that carried a hand-typed
# element could disagree with the ground it stands on, and then the map would
# stop meaning anything — which is the argument `forge.Metal.to_dict` already
# makes about metals, made again one layer up.
#
# THE BRIEF NAMED THREE AND THEY ARE ALL HERE, under the names the world uses
# for those places:
#
#   a fire elemental for the volcano   THE CINDER PHOENIX, Stack & Queue Mines,
#                                      which is this game's volcano and whose
#                                      palette is already "ember". A phoenix,
#                                      because the brief asked for one by name.
#   an ice elemental for the cold      THE RIMEWARDEN, Twin Pointer Pass, the
#                                      one region with real ice in it.
#   a shadow elemental for the void    THE UNNAMED, the Null King's Castle, and
#                                      THE UNRETURNING one region earlier, which
#                                      is the same idea at a smaller size.
#
# The other fourteen follow the same rule: read what the region physically IS in
# world.REGIONS["physical"], and build the thing that would live there.
#
# SILHOUETTES ARE WRITTEN FOR AN ARTIST, not for a tooltip. Each one names a
# READABLE OUTLINE at 48x48 — a shape you could identify as a black cutout at
# the far edge of the screen, which is exactly the size and the contrast an
# approaching hunter is first seen at.


@dataclass(frozen=True)
class Apex:
    id: str
    name: str
    region: str
    silhouette: str       # for whoever draws it. A black cutout at 48x48.
    presence: str         # why it is here. One paragraph of place, not of stats.
    lesson: str           # section F: the gear lesson it examines
    tell: str             # the thing it does that makes the lesson visible
    sprite: str           # NEW bosses.js key. Nobody has authored it yet.
    sprite_fallback: str  # an existing bosses.js archetype. Resolves today.
    colour: str
    exam: dict            # component -> weight, sums to 100
    trophy: str           # TROPHIES key

    # -- derived, never stored ---------------------------------------------

    @property
    def elements(self) -> tuple:
        """Everything it is, primary first.

        A boss-class chain, because an apex IS the hardest thing in its region
        and `elements.affinity_count` gates the third affinity on exactly that.
        A neutral region returns `(NEUTRAL,)` and that is not a bug: five
        regions are weatherless on purpose and their apexes examine the other
        four components instead. See `NEUTRAL_EXAM`.
        """
        return elements.affinities_for(self.region, difficulty="BOSS",
                                       is_boss=True)

    @property
    def element(self) -> str:
        """What it strikes with, and what it is hardest to hurt through."""
        return self.elements[0]

    @property
    def depth(self) -> int:
        return _region_index(self.region)

    @property
    def required_rung(self) -> int:
        """The rung of this region's own metal: the bar `forge` itself sets for
        being current here. Python Village has no metal and reads as one."""
        metal = forge.metal_for_region(self.region)
        return metal.rung if metal else 1

    @property
    def metal(self) -> str:
        metal = forge.metal_for_region(self.region)
        return metal.id if metal else ""

    @property
    def exam_difficulty(self) -> str:
        return exam_difficulty_for(self.region)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "region": self.region,
            "region_name": world.REGION_BY_ID[self.region]["name"],
            "depth": self.depth,
            "element": self.element, "elements": list(self.elements),
            "art": elements.element_view(self.element),
            "silhouette": self.silhouette, "presence": self.presence,
            "lesson": self.lesson, "tell": self.tell,
            "sprite": self.sprite, "sprite_fallback": self.sprite_fallback,
            "colour": self.colour,
            "exam": dict(self.exam), "metal": self.metal,
            "required_rung": self.required_rung,
            "exam_difficulty": self.exam_difficulty,
            "trophy": self.trophy,
            # The ramp, per creature, so a roster row is self-describing and
            # the client never has to join it against another table to say how
            # long this one is. Derived at read time; nothing is stored.
            "chapter": chapter_for_region(self.region),
            "pace": pace_for(self.region),
        }


# -- the exam weights -------------------------------------------------------
#
# Section F, made mechanical instead of merely written down. A component with
# weight zero is a component this apex is not examining, and a component with
# a big weight is the sentence in `lesson` restated as arithmetic. If the two
# ever disagree, the number is the one the player will feel, so the number is
# the one that is true.

EXAM_COMPONENTS = ("element", "rung", "armour", "companion", "potions")

# The default for the twelve elemental regions. Element and rung are the two
# halves of the weapon and they are equal, because "the right metal at the wrong
# rung" and "the right rung of the wrong metal" are the same mistake twice.
ELEMENTAL_EXAM = {"element": 25, "rung": 25, "armour": 25,
                  "companion": 15, "potions": 10}

# The default for the five neutral regions. There is nothing to counter, so the
# twenty-five points the wheel would have taken are redistributed, and the
# lesson becomes the OTHER half of preparation: a longer bar, more flat
# mitigation, a companion that can actually speak about this depth, and a full
# pouch. Neutral apexes are where a player learns what the wheel was worth, by
# fighting one without it.
NEUTRAL_EXAM = {"element": 0, "rung": 35, "armour": 30,
                "companion": 20, "potions": 15}


def _exam(**over) -> dict:
    """An exam sheet that still sums to a hundred. `self_check` proves it."""
    base = dict(ELEMENTAL_EXAM)
    base.update(over)
    return base


def _neutral_exam(**over) -> dict:
    base = dict(NEUTRAL_EXAM)
    base.update(over)
    return base


APEXES: tuple = (

    # -- 0. Python Village -- NEUTRAL -----------------------------------------
    Apex(
        "margin_walker", "The Margin-Walker", "python_village",
        "A surveyor two heads too tall, in a shroud of blank unprinted board. "
        "One arm is a folded measuring rod, hinged in four places; the other "
        "hangs. Where the face should be there is a rectangle of paper with "
        "nothing on it. The outline is a plumb line with shoulders.",
        "The village was erased once and the erasure did not take. This is "
        "what the King sent back to check the work, and it has been checking "
        "ever since — walking the fence line, measuring what has been rebuilt, "
        "and finding the number larger every season. It has never entered the "
        "streets. It does not appear to know how.",
        "Nothing to counter, nothing to ward. It examines whether you can "
        "still type when there is no advantage on the board, which is the "
        "state every interview is conducted in.",
        "It stops and measures a rebuilt wall. While it measures, it is not "
        "walking, and you can see exactly how much time that buys you.",
        "margin_walker", "wraith", "#c8c4d6",
        _neutral_exam(rung=25, armour=25, companion=25, potions=25),
        "surveyors_rod",
    ),

    # -- 1. Fields of Syntax -- NEUTRAL ---------------------------------------
    Apex(
        "thresher", "The Thresher", "fields_of_syntax",
        "A harvester on six thin stilt legs, tall and mostly empty, with a "
        "drum of hooked blades where a body should be. The drum turns whether "
        "or not it is cutting. Read as a cutout it is a wheel held up on "
        "insect legs, and the legs are longer than the wheel is wide.",
        "Somebody built it to cut down the malformed statements growing in the "
        "field margins. It worked. It is still working, and the definition of "
        "malformed it was given has degraded to 'standing up'.",
        "The first neutral fight in the game that is genuinely long. It tests "
        "the unglamorous half of a loadout — bar length, flat armour points, "
        "and whether you bothered to fill the pouch before leaving town.",
        "The drum slows before it turns toward you. It cannot cut and pivot at "
        "the same time and it never learned to hide that.",
        "thresher", "automaton", "#b9a86a",
        _neutral_exam(),
        "hooked_tine",
    ),

    # -- 2. Hashmap Highlands -- LIGHTNING (+BRUTE) ---------------------------
    Apex(
        "storm_ordinal", "The Storm Ordinal", "hashmap_highlands",
        "A ten-foot conductor standing on one grounded spike, with a ring of "
        "spent vault keys orbiting where a head would be. At the centre of the "
        "ring is a keyhole with nothing behind it. The silhouette is a "
        "lightning rod wearing a crown it cannot put down.",
        "The Highlands are the tallest metal for a day's walk in any "
        "direction, and everything up here has been struck at least once. This "
        "one was struck enough times to start expecting it, and now it goes "
        "and stands where the next one will land. You are simply taller than "
        "the grass.",
        "Lightning, and the first area where hitting back with the local "
        "element is a real mistake — a lightning weapon here is shrugged off "
        "at 0.65x. The counter is void, which you cannot have yet, and that is "
        "deliberate: this apex teaches that NEUTRAL beats SAME, and that the "
        "answer to a bad matchup is sometimes to stop bringing an element.",
        "The keys stop orbiting a full second before it discharges. Every key "
        "points at you at once, which is the only time it aims.",
        "storm_ordinal", "titan", "#f2dc6a",
        _exam(element=25, rung=25, armour=25, companion=15, potions=10),
        "ungrounded_key",
    ),

    # -- 3. Stringwood Labyrinth -- POISON (+COLD) ----------------------------
    Apex(
        "sporecrown", "The Sporecrown", "stringwood_labyrinth",
        "A great owl whose feathers are letters, layered like shingles, and "
        "whose crown is a fruiting body grown through the skull from the "
        "inside. It shakes spores the way an owl shakes rain. The cutout is a "
        "wide low wedge with a cauliflower where the tufts should be.",
        "It roosts in the anagram groves and it has been rearranging them. The "
        "paths that used to spell a way out now spell something else, and the "
        "something else is a word in no language, and repeating it is how the "
        "spores get in.",
        "Poison, which is the patient element: it does not care how the fight "
        "is going right now. The lesson is that a damage-over-time is answered "
        "by a LONGER BAR and an antidote, not by flat armour points — plate "
        "does nothing about a tick that is a percentage of your maximum.",
        "It drops one shingle-feather before every spore cloud. The feather "
        "lands first and you have the length of its fall.",
        "sporecrown", "ent", "#8fd07a",
        _exam(element=25, rung=20, armour=20, companion=15, potions=20),
        "rearranged_quill",
    ),

    # -- 4. Array Caverns -- BRUTE (+COLD) ------------------------------------
    Apex(
        "zeroth_weight", "The Zeroth Weight", "array_caverns",
        "A slab of numbered alcove plates folded into something shoulder-heavy "
        "and short-legged, walking with the whole cavern roof on it. A single "
        "cut zero is scored across the chest, deep. The outline is an anvil "
        "that has been given a stoop.",
        "The Caverns number their alcoves from zero and something has to hold "
        "up the first one. It has held it up for a very long time, and the "
        "weight has pressed it into roughly the shape of a man, and it has "
        "started walking the halls counting the alcoves to check they are all "
        "still there.",
        "Brute force, which is the element that makes plate stop mattering — "
        "`elements.BRUTE` arrives and flat points are exactly what it is for "
        "ignoring. The lesson is that against brute you want RESISTANCE, not "
        "points, and poison is the counter.",
        "It sets down before it swings. Both feet, audibly, and the dust comes "
        "off the ceiling half a second before the arm does.",
        "zeroth_weight", "golem", "#bf8f4f",
        _exam(element=25, rung=25, armour=25, companion=15, potions=10),
        "index_zero_plate",
    ),

    # -- 5. Sliding Window Marsh -- POISON (+COLD) ----------------------------
    Apex(
        "fenlight", "The Fenlight", "sliding_window_marsh",
        "A drowned lamp-carrier with seven arms, each holding one corner of a "
        "frame that has four corners. The frame therefore never closes. The "
        "lamp is inside it and lights the reeds from the wrong side. As a "
        "cutout: a wading bird made of held-up rectangles.",
        "The magical frame out in the reeds expands right and shrinks left, "
        "and once in a while it shrinks past something that was inside it. "
        "This is one of those. It has been carrying a broken copy of the frame "
        "ever since, looking for the position where it closes again.",
        "Poison over standing water, with cold underneath at depth. The lesson "
        "is DUAL AFFINITY: no single weapon answers it, the counter to poison "
        "is brute and the counter to cold is fire, and you are going to have "
        "to pick which half to answer and ward the other.",
        "The frame brightens on the side it is about to advance. It telegraphs "
        "its own window, which is the joke the region has been making all "
        "along.",
        "fenlight", "hydra", "#7f9a5a",
        _exam(element=25, rung=20, armour=25, companion=15, potions=15),
        "unclosed_corner",
    ),

    # -- 6. Twin Pointer Pass -- COLD (+LIGHTNING) ----------------------------
    # The brief's ice elemental, and the region with the only real ice.
    Apex(
        "rimewarden", "The Rimewarden", "twin_pointer_pass",
        "A lantern-bearer of blue ice, walking the bridge from both ends at "
        "once: two bodies, mirrored, sharing one shadow that lies between them "
        "and does not move. Each body carries a lantern with a frozen flame. "
        "The cutout is two identical figures converging, and the gap between "
        "them is the shape you have to read.",
        "Two lanterns start at either end of the Pass and converge. That is "
        "the region, and it is also what this is: the Pass grew a warden out "
        "of its own rule and the warden has been converging on things ever "
        "since. It arrives from both sides and it is the same creature. "
        "Killing either half kills it. Fleeing past either half works.",
        "Cold. This is the ice elemental and it is the cleanest ward lesson in "
        "the game: fire counters it at 1.33x — the dual pulls it in from the "
        "1.50x a pure cold enemy would give — a warded chest at RESIST_CAP "
        "takes 60% off everything it throws, and CHILLED cuts YOUR outgoing "
        "damage, so the fight gets longer the worse you handle it.",
        "Both lanterns dim together before it closes. The pass goes dark for a "
        "beat and that beat is your whole warning.",
        "rimewarden", "colossus", "#7ec8ff",
        _exam(element=25, rung=20, armour=30, companion=15, potions=10),
        "frozen_wick",
    ),

    # -- 7. Stack & Queue Mines -- FIRE (+BRUTE) ------------------------------
    # The brief's phoenix, in this game's volcano.
    Apex(
        "cinder_phoenix", "The Cinder Phoenix", "stack_queue_mines",
        "A bird built out of ore-cart iron and flame, wings made of stacked "
        "plates that unload from the top, one at a time, and burn on the way "
        "down. Its legs are lift cable. The cutout is a raptor whose wings are "
        "visibly a stack rather than a fan.",
        "The Mines run their carts last-in-first-out and their lifts "
        "first-in-first-out, and a fire that got into the third gallery has "
        "spent forty years learning which is which. It unloads itself from the "
        "top. When it burns down to nothing the lift brings the oldest plate "
        "back up and it starts again, which is the only sense in which it is a "
        "phoenix and the only sense it needs.",
        "Fire, which leaves the wound still burning. The lesson is that BURNING "
        "is a percentage of your maximum bar, so the counter is cold, the ward "
        "is a fire resist, and the third road — a bigger bar — makes the tick "
        "hurt MORE, not less. This is the apex that teaches that a cloak is not "
        "always the answer.",
        "It drops a plate before every pass. The plate lands where it is about "
        "to be, not where it is, so the ground tells you the route.",
        "cinder_phoenix", "dragon", "#e06a3c",
        _exam(element=25, rung=20, armour=20, companion=15, potions=20),
        "topmost_plate",
    ),

    # -- 8. Matrix Citadel -- BRUTE (+LIGHTNING) ------------------------------
    Apex(
        "fourth_orientation", "The Fourth Orientation", "matrix_citadel",
        "A knight cast in place in the Citadel floor and then prised out of it, "
        "so the armour has been through four rotations and settled into none. "
        "Pauldrons face forward, the helm faces left, the greaves face back. It "
        "walks without turning. The cutout is a human figure assembled from "
        "four different human figures.",
        "The whole floor plan turns ninety degrees when the Golem stirs, and "
        "everything standing on it turns with it. This one was standing on the "
        "seam. It has been rotated four times and returned to where it started "
        "and it does not accept that those are the same place.",
        "Brute with lightning under it. The lesson is the ARMOUR half of a "
        "dual: its primary is what it hits you with, so ward BRUTE and counter "
        "with POISON for 1.33x, and notice that the obvious reading — counter "
        "the lightning, it is scarier — pays 1.167x. The primary is weighted "
        "double, and that gap is the whole reason why.",
        "It squares up by rotating its whole body in ninety-degree steps. You "
        "can count the steps and you know it needs all four.",
        "fourth_orientation", "knight", "#8a8f9c",
        _exam(element=25, rung=25, armour=25, companion=15, potions=10),
        "seam_rivet",
    ),

    # -- 9. Recursive Forest -- VOID (+POISON) --------------------------------
    Apex(
        "unreturning", "The Unreturning", "recursive_forest",
        "One figure at three sizes in a single outline: a walker, stepping "
        "into a smaller copy of itself, which is stepping into a smaller copy "
        "of itself. The smallest is not finished. Nothing about the silhouette "
        "resolves — it is legible only as a nested taper, and that is correct.",
        "Each clearing in this forest contains a smaller copy of the forest, "
        "and you are supposed to come back out carrying what the inner copy "
        "found. This one went in and did not come back out, and then it went "
        "in again, from the inside. It is still descending. The part of it you "
        "meet is the part that has not descended yet.",
        "Void, the brief's shadow elemental at the size the Forest can hold. "
        "The lesson is that void is an ABSENCE arriving where a force was "
        "expected: lightning counters it, void is blunted by nothing, and its "
        "secondary edge over poison means the poison gear that carried you "
        "through the Stringwood is now the wrong bag.",
        "The innermost copy takes its step first. The outer ones follow, "
        "smallest to largest, so the attack visibly unwinds outward before it "
        "reaches you.",
        "unreturning", "lich", "#6a4f8f",
        _exam(element=30, rung=20, armour=25, companion=15, potions=10),
        "unwound_frame",
    ),

    # -- 10. Binary Tree Canopy -- NEUTRAL ------------------------------------
    Apex(
        "bough_stalker", "The Bough Stalker", "binary_tree_canopy",
        "A long cat, built for branches, with two shadows: one going left and "
        "one going right, neither of them under it. The shadows never rejoin. "
        "The cutout is unmistakably a hunting animal, which is the point — up "
        "here the danger has a spine and four legs rather than a cosmology.",
        "The brief asked for hunter animals, and the canopy is where the "
        "world's answer to that is simply an animal. Every branch up here "
        "splits exactly twice and never rejoins, so a thing that hunts in the "
        "canopy has to commit at every fork. This one committed a long time "
        "ago and has been going left ever since.",
        "Neutral air above the Forest's dark. No element to read, so the exam "
        "is entirely the other four: rung, points, companion depth, pouch. It "
        "is the last quiet lesson before the Wastes.",
        "It picks a shadow. Whichever shadow moves first is the side it comes "
        "down on, and it cannot change its mind mid-fall.",
        "bough_stalker", "wyrm", "#6b8f3f",
        _neutral_exam(rung=35, armour=25, companion=25, potions=15),
        "left_fork_claw",
    ),

    # -- 11. Graph Wastes -- LIGHTNING (+BRUTE) -------------------------------
    Apex(
        "lattice_stag", "The Lattice Stag", "graph_wastes",
        "A stag of road-iron, antlers grown into the lattice of the Wastes "
        "roads — every tine is a route and the tines connect to each other, "
        "which no antler does. It is bigger than the ruins it walks between. "
        "The cutout is a crown of wire on a body of broken kerbstone.",
        "Every ruin out here connects to several others, some routes shorter "
        "and some merely existing. The Stag carries the map in its head "
        "because the map grew there. It does not wander toward you: it takes "
        "the shortest road, and if you break the road it takes the next "
        "shortest, and there is always a next one. That is the region's whole "
        "lesson given legs.",
        "Lightning off the lattice, poison out of what rotted in the ruins "
        "the lattice runs between. It is the one apex on the wheel where a "
        "single element answers BOTH halves — void counters the lightning and "
        "has its secondary edge over the poison, so it pays 1.40x, the highest "
        "number any apex in the game will give you. The lesson is that reading "
        "a dual is worth doing properly rather than settling for the primary.",
        "A tine brightens when it commits to a route. Follow the lit tine "
        "backwards and you know which way it is coming before it moves.",
        "lattice_stag", "behemoth", "#9a8220",
        _exam(element=25, rung=25, armour=20, companion=20, potions=10),
        "lit_tine",
    ),

    # -- 12. Dynamic Programming Ruins -- NEUTRAL -----------------------------
    Apex(
        "relighter", "The Relighter", "dp_ruins",
        "A lamp-lighter on stilts, walking backwards, with a long pole that "
        "has a snuffer on the end instead of a wick. Its coat is made of "
        "prised-up floor tiles that still glow, hung in overlapping rows. The "
        "cutout is a tall thin cross on two poles, dragging a hem of squares.",
        "Here a tile you have already solved stays lit and can be walked again "
        "for free. This thing goes along behind putting them out. Not out of "
        "malice — it is collecting them; its coat is what it has collected — "
        "but the effect is the same, and the ground you crossed for free an "
        "hour ago costs full price on the way back.",
        "Neutral, which in the Ruins is the joke: the region's whole gift is "
        "that work already done stays done, and its apex is the thing that "
        "takes that gift back. The exam is rung, points, companion, pouch, and "
        "an honest answer to whether you can afford to recompute.",
        "The pole comes down before the stilt does. It always snuffs the tile "
        "it is about to step on, so its next square is the one that just went "
        "dark.",
        "relighter", "necromancer", "#e0b44a",
        _neutral_exam(rung=35, armour=25, companion=20, potions=20),
        "prised_tile",
    ),

    # -- 13. Debugging Dungeon -- FIRE (+BRUTE) -------------------------------
    Apex(
        "slagmother", "The Slagmother", "debugging_dungeon",
        "A furnace-bellied figure hung all over with cracked plate, dragging "
        "the cells' failed armour behind it on chains. The belly is open and "
        "lit. The cutout is a bell with arms, trailing a long low tail of "
        "hanging shapes, and the tail is longer than the bell is tall.",
        "Cracked armour hangs on every wall of the Armorer's forge, each crack "
        "a defect in some program. Somebody has to take the ones that cannot "
        "be saved back to the furnace. She does, patiently, and she has "
        "started to count things that still work as things that will not.",
        "Fire in a place that is already a forge, and void underneath it, "
        "because a crack in sound plate is an absence where a thing was "
        "expected and that is the definition of the element. The lesson is "
        "that a WARD IS NOT A COUNTER: a fire resist caps at 0.60 and is worth "
        "more here than anywhere, but you still need something that is not "
        "fire in your hand, because SAME is 0.65x and this fight is long "
        "enough for that to be the whole difference.",
        "The belly brightens before a swing and dims before a charge. One "
        "creature, two tells, and they are opposites.",
        "slagmother", "demon", "#c43f4f",
        _exam(element=25, rung=25, armour=30, companion=10, potions=10),
        "unsalvaged_plate",
    ),

    # -- 14. Complexity Tower -- COLD (+VOID, BRUTE) --------------------------
    Apex(
        "the_doubling", "The Doubling", "complexity_tower",
        "A thin cold figure on the stair, and behind it another exactly twice "
        "its size, and behind that another. You only ever see the top one "
        "whole. The cutout is a single narrow shape with a much larger shape "
        "cropped by the frame behind it, and the crop is the horror.",
        "Each floor of the Tower holds twice the enemies of the one below and "
        "the top floor is unreachable by brute force. The Doubling is what "
        "that sentence looks like when it starts walking down. The one you "
        "meet is the smallest one. It is not the one that is coming.",
        "Cold, void and brute — the only three-element chain in the game "
        "outside the Castle, which is exactly what a final-approach apex "
        "should be. The lesson is that at three affinities the wheel "
        "COMPRESSES: your best available counter is fire at 1.25x rather than "
        "the 1.50x a single element would pay, so the fight is decided by rung "
        "and by ward, and no single clever pick saves it.",
        "It counts the stair aloud. The number it reaches is how many times "
        "its next attack lands, and it always says the number first.",
        "the_doubling", "automaton", "#7ec8ff",
        _exam(element=25, rung=30, armour=20, companion=15, potions=10),
        "eighth_bar",
    ),

    # -- 15. The Coding Coliseum -- NEUTRAL -----------------------------------
    Apex(
        "sand_champion", "The Sand Champion", "coding_coliseum",
        "A gladiator of compacted sand and fused glass, carrying a clock face "
        "as a shield. Where the sand is thin you can see the hour through it. "
        "The cutout is a classical fighting stance, which is the only apex in "
        "the game whose outline reads as a person doing a job.",
        "A sand floor, a clock, and no hints. Whoever this was won here often "
        "enough that the floor kept a copy, and the copy has kept fighting "
        "because nobody told it the card had ended. It is scrupulously fair. "
        "It waits for you to be ready. That is somehow worse.",
        "Neutral, and the only apex that is neutral BY CHARTER rather than by "
        "biome — the Coliseum says in its own description that it gives no "
        "hints. It examines the pouch hardest of the five neutrals, because "
        "the Chronomancer's region turns knowledge into speed and a potion is "
        "the only thing here that buys time.",
        "It salutes. The salute is not courtesy, it is a wind-up, and it takes "
        "exactly as long every time.",
        "sand_champion", "titan", "#e8c37d",
        _neutral_exam(rung=35, armour=20, companion=20, potions=25),
        "hour_through_glass",
    ),

    # -- 16. The Null King's Castle -- VOID (+COLD, BRUTE) --------------------
    # The brief's shadow elemental, at full size, in the place it belongs.
    Apex(
        "the_unnamed", "The Unnamed", "null_kings_castle",
        "A tall absence in the shape of a knight. Not black — absent: the "
        "outline is where the room stops. It carries nothing and wears "
        "nothing. The part of the shape that would say what it is has been "
        "removed, and the removal is visible as a clean rectangular notch "
        "through the chest that you can see the far wall through.",
        "NUL-9 took a name because it was the one name it had never been "
        "given. This is what happened to something that was in the way when it "
        "did. It is not a servant of the King and it is not hunting on orders. "
        "It is looking for the part of itself that said what it was, and it "
        "checks everything that has a name, and you have one.",
        "Void, cold and brute: everything the Castle is. The final exam of the "
        "gear layer, and it is a three-part question — counter the void with "
        "lightning, ward the void because it strikes with its primary, and "
        "bring a rung that does not care. No signposts, no region labels, "
        "nothing tells you what is being tested. That is the region's promise "
        "and this keeps it.",
        "The notch through its chest goes dark before it moves. That is the "
        "whole tell, it is the smallest tell in the game, and by here you "
        "should be reading tells that small.",
        "the_unnamed", "colossus", "#4a4458",
        _exam(element=30, rung=25, armour=25, companion=10, potions=10),
        "struck_label",
    ),
)

APEX_BY_ID = {a.id: a for a in APEXES}
APEX_BY_REGION = {a.region: a for a in APEXES}

# The three fallback sprites that repeat, named rather than discovered.
# bosses.js already documents exactly this problem for world.BOSSES ("two
# identical silhouettes in one playthrough is a defect the player can see") and
# solves it with a one-line override table. Same here: seventeen apexes, fifteen
# authored boss archetypes, so three pairs share until somebody draws the real
# ones. The pairs are chosen to be as far apart in the region order as the roster
# allows — you will have played for hours between meeting either half.
#
#   automaton   Thresher (1)        <-> The Doubling (14)     13 regions apart
#   titan       Storm Ordinal (2)   <-> Sand Champion (15)    13 regions apart
#   colossus    Rimewarden (6)      <-> The Unnamed (16)      10 regions apart
#
# Authoring `Apex.sprite` in bosses.js removes each one with a single line in
# BOSS_SHAPE_FOR and changes nothing in this file.
SPRITE_FALLBACK_REPEATS = ("automaton", "titan", "colossus")

# The archetypes bosses.js actually has, as of this writing. `scripts/verify/
# apex.mjs` reads the live list out of the JS and fails if this drifts; the copy
# exists so `self_check` can say something true without Node installed.
_BOSS_ARCHETYPES = (
    "titan", "hydra", "wraith", "behemoth", "golem", "dragon", "ent",
    "necromancer", "automaton", "lich", "demon", "wyrm", "knight", "colossus",
    "interpreter",
)


def apex_for(region_id: str) -> Apex | None:
    """The thing hunting this region. None only for a region that does not
    exist — every one of the seventeen has one."""
    return APEX_BY_REGION.get(region_id)


def exam_weights(apex: Apex) -> dict:
    return dict(apex.exam)


def lesson_for(region_id: str) -> dict:
    """Section F as a readable answer: what this area's apex is testing you on,
    in the words of the exam sheet rather than in prose alone."""
    apex = apex_for(region_id)
    if apex is None:
        return {}
    # Ties resolve toward the EARLIER component in EXAM_COMPONENTS rather than
    # alphabetically. A balanced 25/25/25 sheet reported "rung" under an
    # alphabetical tie-break, which is a true statement about sorting and a
    # false one about the apex.
    heaviest = max(apex.exam.items(),
                   key=lambda kv: (kv[1], -EXAM_COMPONENTS.index(kv[0])))
    return {"apex": apex.id, "name": apex.name, "region": region_id,
            "element": apex.element, "elements": list(apex.elements),
            "lesson": apex.lesson, "tell": apex.tell,
            "exam": dict(apex.exam),
            "examines_hardest": heaviest[0],
            "counter": elements.OPPOSED.get(apex.element, ""),
            "ward": apex.element if apex.element in elements.ELEMENTS else "",
            "metal": apex.metal, "required_rung": apex.required_rung}


# -- how deep a region is, in the vocabulary the rest of the game uses -------
#
# Not a new ladder. `curriculum.TIERS` is the ladder, `pets.Tier.depth` is
# already expressed in it, and `elements.affinity_count` already gates on it, so
# a region's exam difficulty is stated in the same words or it is not stated at
# all.

_EXAM_DIFFICULTY_BANDS = (
    (2, "EASY"),      # regions 0-1: the village and the first fields
    (6, "MEDIUM"),    # 2-5:  Highlands through the Marsh
    (12, "HARD"),     # 6-11: the Pass through the Wastes
    (16, "ELITE"),    # 12-15: the Ruins, the Dungeon, the Tower, the Coliseum
)


def exam_difficulty_for(region_id: str) -> str:
    depth = _region_index(region_id)
    for limit, name in _EXAM_DIFFICULTY_BANDS:
        if depth < limit:
            return name
    return "BOSS"


# ---------------------------------------------------------------------------
# B. Readiness: difficulty from preparation
# ---------------------------------------------------------------------------
#
# Five components, one score from zero to a hundred, and NOT ONE OF THEM IS XP.
#
# The thing to keep hold of while reading the arithmetic: every component is
# measured AGAINST THIS AREA. A rung-six blade is not "good", it is good in the
# Castle and it is three rungs of overkill in the Marsh, and the score says so
# by comparing against `Apex.required_rung` rather than against a global maximum.
# That is what makes the number a statement about whether you did the local work
# rather than about how long you have been playing.
#
# WHY THE WEIGHTS ARE THESE WEIGHTS
#
#   element 25   the wheel is the area's headline lesson and 0.65x versus 1.50x
#                is the largest single swing available to a player
#   rung    25   the other half of the weapon. Equal to element, because the two
#                mistakes are the same mistake
#   armour  25   what you are wearing against what it strikes with. Equal again,
#                because `elements.py` deliberately made the defensive road as
#                strong as the offensive one and this must not quietly disagree
#   companion 15 a real choice with a real gate (pets.covers), worth less than
#                gear because there are only twelve of them and you own few
#   potions 10   the smallest, on purpose: the pouch is the component a player
#                can fix in thirty seconds, so it should not dominate a score
#                whose job is to describe months of work
#
# A neutral region redistributes the element's 25 rather than capping the score
# at 75. A player who has done everything available in the Coliseum must be able
# to reach a hundred in the Coliseum, or the apex there is permanently harder
# than the apex anywhere else, which is not what "difficulty from preparation"
# means.

# Flat mitigation worth "a full mark". Bestiary enemies carry points in the low
# single digits against base damage near twelve, so ten points is a genuinely
# heavy plate loadout rather than a theoretical maximum.
ARMOUR_POINTS_REFERENCE = 10.0

# Bonus bar (elements.HEALTH_EFFECT_KEY + FOCUS_EFFECT_KEY) worth a full mark.
# config.STAMINA_MAX is twenty, so twelve points of bonus is a bar half again as
# long, which is what a committed cloak-and-helm build actually reaches.
BAR_BONUS_REFERENCE = 12.0

# A full pouch, in band-weighted doses. potions.CARRY_CAP tops out at five minor
# or two hefty, so eight weighted units is "you went shopping and you meant it".
POTION_REFERENCE = 8.0
POTION_BAND_WEIGHT = {"minor": 1.0, "small": 2.0, "medium": 3.0, "hefty": 4.0}

# The element mark is LINEAR IN THE MULTIPLIER YOU ACTUALLY GET, normalised
# across the wheel's full range: SAME (0.65x) earns nothing and OPPOSED (1.50x)
# earns everything.
#
# An earlier draft scored the matchup KIND from a hand-written table, and it was
# wrong for exactly the case this game has most of. `elements.matchup_multi`
# returns the BEST kind found anywhere in a defender's chain, which is the right
# label for a combat log and the wrong number for an exam: a cold weapon against
# the cold-and-lightning Rimewarden gets kind NEUTRAL — because cold into
# lightning is neutral — while actually resolving at 0.767x. The table paid that
# player 48% of the mark for a swing that is nearly the worst available. Reading
# the multiplier instead pays them 14%, which is what 0.767x is worth.
#
# The single-element values fall out of the formula rather than being typed, and
# `self_check` reports them so the shape stays inspectable:
#
#   SAME 0.65x -> 0.00   WEAK_INTO 0.85x -> 0.24   NEUTRAL 1.00x -> 0.41
#   SECONDARY 1.20x -> 0.65                        OPPOSED 1.50x -> 1.00
#
# Neutral earning 0.41 rather than zero is deliberate and is the same argument
# `elements.py` makes about its own floor: bringing no element is an honest
# non-answer, not a mistake, and the thing worth punishing is bringing the
# element the ground is already made of.
_CREDIT_FLOOR = elements.MATCHUP_MULT["SAME"]       # 0.65
_CREDIT_CEIL = elements.MATCHUP_MULT["OPPOSED"]     # 1.50


def _element_credit(multiplier: float) -> float:
    span = _CREDIT_CEIL - _CREDIT_FLOOR
    return max(0.0, min(1.0, (float(multiplier) - _CREDIT_FLOOR) / span))


# Derived, never typed. Kept as a name because a designer reading this file
# wants the five landmark values on one line.
ELEMENT_CREDIT = {kind: round(_element_credit(mult), 3)
                  for kind, mult in elements.MATCHUP_MULT.items()}

# Rung delta -> credit. Being CURRENT with the area (delta 0) is 0.60, not 1.00:
# the region's own metal is the pass mark, not distinction, and the last 40% is
# there so that going back to the forge with what the previous region gave you
# is always worth something.
RUNG_CREDIT = {-3: 0.00, -2: 0.15, -1: 0.35, 0: 0.60, 1: 0.80, 2: 0.92, 3: 1.00}

# Companion depth, in rungs short of the region's exam difficulty.
COMPANION_CREDIT = {0: 1.00, 1: 0.50, 2: 0.20}

# Weapon tier -> per-cast damage scale. Anchored so that tier 3 is 1.00, because
# CAST_DAMAGE_REFERENCE is the damage of a competent cast with a mid blade. Used
# ONLY to size the apex's hit points so that the authored cast count is the cast
# count that actually happens — see `scale_for`.
RUNG_DAMAGE_SCALE = {0: 0.75, 1: 0.80, 2: 0.90, 3: 1.00, 4: 1.12, 5: 1.25,
                     6: 1.40, 7: 1.55, 8: 1.72, 9: 1.90}


@dataclass
class Loadout:
    """What the player is actually carrying, flattened.

    Deliberately not the save state and not `engine.Game`: both get adapted into
    this at the call site, exactly as `elements.Defender` is adapted, so the
    readiness maths is testable with nothing else loaded. `readiness_from_game`
    is the adapter, and it is the only function in this file that imports
    anything late.
    """
    weapon_element: str = elements.NEUTRAL
    weapon_rung: int = 0              # forge tier 1..9; 0 means no forged blade
    armour_points: int = 0
    armour_resist: dict = field(default_factory=dict)   # element -> 0..1
    bar_bonus: int = 0                # stamina_max + mana_max from gear
    companion_tier: str = ""          # pets.TIERS key, or "" for no companion
    potions: dict = field(default_factory=dict)   # potions strength -> count

    def resist_to(self, element: str) -> float:
        if element not in elements.ELEMENTS:
            return 0.0
        return min(elements.RESIST_CAP,
                   max(0.0, float(self.armour_resist.get(element, 0.0) or 0.0)))


@dataclass
class Readiness:
    """A score, its five parts, and the sentence each part is worth saying."""
    score: int                 # 0..100
    band: str
    parts: dict                # component -> {"earned", "weight", "fraction"}
    advice: tuple              # what to go and fix, worst gap first
    apex: str
    region: str

    def to_dict(self) -> dict:
        return {"score": self.score, "band": self.band,
                "parts": {k: dict(v) for k, v in self.parts.items()},
                "advice": list(self.advice),
                "apex": self.apex, "region": self.region}


# The four bands the brief asked for, in its own words where it had them.
# "Very hard if you are new here, normal to hard once you have upgraded" is two
# points on a line; these are the four that line passes through.
BANDS = (
    (0, "UNPREPARED", "Very hard. You have not done the work here yet, and it "
                      "is going to tell you which work."),
    (25, "THIN", "Hard. You have some of it. Not the half that matters most."),
    (50, "READY", "Hard, and fair. This is the fight the area was built to "
                  "hand you."),
    (75, "SEASONED", "A real fight rather than a wall. You did the reading."),
)


def band_for(score: int) -> str:
    name = BANDS[0][1]
    for floor, key, _ in BANDS:
        if score >= floor:
            name = key
    return name


def band_blurb(score: int) -> str:
    text = BANDS[0][2]
    for floor, _, blurb in BANDS:
        if score >= floor:
            text = blurb
    return text


def _rung_credit(delta: int) -> float:
    if delta <= -3:
        return RUNG_CREDIT[-3]
    if delta >= 3:
        return RUNG_CREDIT[3]
    return RUNG_CREDIT[delta]


def _companion_credit(tier_key: str, difficulty: str) -> float:
    """How far short of this area's depth the companion is.

    Resolved through `curriculum.tier_index` and a small local copy of
    `pets.TIERS`' depth column, because this module stays loadable without
    `pets` — the same independence `bestiary` keeps from `incantation`.
    `readiness_from_game` passes the live tier key through and the table is
    checked against `pets.TIERS` by `self_check` when pets is importable.
    """
    if not tier_key:
        return 0.0
    depth = _PET_TIER_DEPTH.get(tier_key.upper())
    if depth is None:
        return 0.0
    short = curriculum.tier_index(difficulty) - curriculum.tier_index(depth)
    if short <= 0:
        return COMPANION_CREDIT[0]
    return COMPANION_CREDIT.get(short, 0.0)


# pets.TIERS' depth column, copied. `self_check` diffs it against the live
# module when that module is importable, so the copy cannot rot in silence.
_PET_TIER_DEPTH = {"TUTORIAL": "TUTORIAL", "BEGINNER": "EASY", "ADEPT": "MEDIUM",
                   "MASTER": "HARD", "LEGENDARY": "BOSS", "HIDDEN": "BOSS"}


def _potion_credit(pouch: dict) -> float:
    total = 0.0
    for strength, count in (pouch or {}).items():
        total += POTION_BAND_WEIGHT.get(str(strength).lower(), 1.0) \
            * max(0, int(count or 0))
    return min(1.0, total / POTION_REFERENCE)


def best_available(apex: Apex) -> tuple:
    """The best element to swing at this apex, and what it is worth.

    Six candidates, evaluated through the same `matchup_multi` the fight uses,
    so the advice a player is given and the number they later feel are computed
    by one function. For a dual apex this is NOT simply the primary's opposite —
    against the cold-and-lightning Rimewarden, fire pays 1.333x and void pays
    1.167x, and a player told "counter the cold" without the number would have
    no way to know the gap was that small.
    """
    best = (elements.NEUTRAL, elements.MATCHUP_MULT["NEUTRAL"])
    for candidate in elements.ELEMENT_IDS:
        mult, _kind, _rows = elements.matchup_multi(candidate, apex.elements)
        if mult > best[1]:
            best = (candidate, mult)
    return best


def readiness(region_id: str, loadout: Loadout | None = None) -> Readiness:
    """How ready this player is FOR THIS AREA. Zero to a hundred.

    Pure. Reads nothing global, mutates nothing, and never once asks how many
    experience points the player has — `self_check` reads this module's own
    source to prove that the words `xp`, `level` and `mastery` do not appear in
    any expression here.
    """
    apex = apex_for(region_id)
    lo = loadout or Loadout()
    if apex is None:
        return Readiness(0, band_for(0), {}, (), "", region_id)

    weights = apex.exam
    parts: dict = {}
    gaps: list = []

    # -- element --------------------------------------------------------
    mult, kind, _rows = elements.matchup_multi(lo.weapon_element, apex.elements)
    credit = _element_credit(mult)
    _put(parts, "element", credit, weights["element"],
         f"{kind.lower().replace('_', ' ')} at {mult:.2f}x")
    if weights["element"] and credit < 0.8:
        best_element, best_mult = best_available(apex)
        gaps.append((weights["element"] * (1.0 - credit),
                     f"Your weapon resolves at {mult:.2f}x against "
                     f"{apex.name}. The best reading available here is "
                     f"{best_element.lower()} at {best_mult:.2f}x."))

    # -- rung -----------------------------------------------------------
    delta = int(lo.weapon_rung or 0) - apex.required_rung
    credit = _rung_credit(delta)
    _put(parts, "rung", credit, weights["rung"],
         f"rung {lo.weapon_rung or 0} against a rung-{apex.required_rung} area")
    if weights["rung"] and credit < 0.6:
        gaps.append((weights["rung"] * (1.0 - credit),
                     f"You are {abs(delta)} rung(s) short for this ground. The "
                     f"metal here is {apex.metal or 'nothing — this is the town'}."))

    # -- armour ---------------------------------------------------------
    points_fraction = min(1.0, lo.armour_points / ARMOUR_POINTS_REFERENCE)
    if apex.element in elements.ELEMENTS:
        ward = lo.resist_to(apex.element) / elements.RESIST_CAP
        credit = 0.6 * ward + 0.4 * points_fraction
        note = (f"{int(lo.resist_to(apex.element) * 100)}% ward vs "
                f"{apex.element.lower()}, {lo.armour_points} points")
    else:
        # Nothing to ward. The whole mark comes from the two roads that still
        # mean something in a weatherless region: flat points, and bar length.
        bar_fraction = min(1.0, lo.bar_bonus / BAR_BONUS_REFERENCE)
        credit = 0.6 * points_fraction + 0.4 * bar_fraction
        note = f"{lo.armour_points} points, +{lo.bar_bonus} bar"
    _put(parts, "armour", credit, weights["armour"], note)
    if weights["armour"] and credit < 0.6:
        if apex.element in elements.ELEMENTS:
            worn = lo.resist_to(apex.element)
            gaps.append((weights["armour"] * (1.0 - credit),
                         f"You are carrying {int(worn * 100)}% "
                         f"{apex.element.lower()} resistance and "
                         f"{lo.armour_points} armour points into a fight that "
                         f"strikes with {apex.element.lower()}. The ward caps "
                         f"at {int(elements.RESIST_CAP * 100)}%."))
        else:
            gaps.append((weights["armour"] * (1.0 - credit),
                         f"No element to ward here, so it is {lo.armour_points} "
                         f"points and +{lo.bar_bonus} of bar or it is nothing."))

    # -- companion ------------------------------------------------------
    credit = _companion_credit(lo.companion_tier, apex.exam_difficulty)
    _put(parts, "companion", credit, weights["companion"],
         f"{lo.companion_tier or 'none'} against {apex.exam_difficulty}")
    if weights["companion"] and credit < 1.0:
        gaps.append((weights["companion"] * (1.0 - credit),
                     f"Your companion cannot speak about {apex.exam_difficulty} "
                     f"content."))

    # -- potions --------------------------------------------------------
    credit = _potion_credit(lo.potions)
    doses = sum(max(0, int(v or 0)) for v in (lo.potions or {}).values())
    _put(parts, "potions", credit, weights["potions"], f"{doses} dose(s)")
    if weights["potions"] and credit < 0.6:
        gaps.append((weights["potions"] * (1.0 - credit),
                     "The pouch is the cheapest thing on this list to fix."))

    score = int(round(sum(p["earned"] for p in parts.values())))
    score = max(0, min(100, score))
    gaps.sort(key=lambda g: -g[0])
    return Readiness(score, band_for(score), parts,
                     tuple(text for _weight, text in gaps), apex.id, region_id)


def _put(parts: dict, key: str, credit: float, weight: int, note: str) -> None:
    credit = max(0.0, min(1.0, float(credit)))
    parts[key] = {"fraction": round(credit, 3), "weight": weight,
                  "earned": credit * weight, "note": note}


def readiness_from_game(state: dict, effects: dict | None, region_id: str, *,
                        companion_tier: str = "", potions: dict | None = None,
                        build_sealed: bool = False) -> Readiness:
    """Adapter. The only late-importing function in this module.

    `state` is `engine.Game.state` and `effects` is `engine.Game.effects()`.
    `build_sealed` is the caller's `finalexam.sealed(enc, "BUILD")` verdict,
    passed in the way `elements` takes it — when it is true the loadout is
    simply not read, readiness is zero, and (see `SPAWNS_WHILE_SEALED`) no apex
    was going to spawn anyway.
    """
    if build_sealed:
        return readiness(region_id, Loadout())

    from . import items  # local: items imports elements, and so do we

    equipped = (state or {}).get("equipped") or {}
    fx = effects or {}
    profile = elements.armour_from_effects(fx)

    weapon_id = equipped.get("weapon", "")
    rung = 0
    if weapon_id in forge.RUNG_BY_ID:
        rung = forge.RUNG_BY_ID[weapon_id][1].tier

    return readiness(region_id, Loadout(
        weapon_element=items.strike_element(equipped),
        weapon_rung=rung,
        armour_points=profile.points,
        armour_resist=dict(profile.resist),
        bar_bonus=profile.bonus_health + profile.bonus_focus,
        companion_tier=companion_tier,
        potions=dict(potions or {}),
    ))


# ---------------------------------------------------------------------------
# B1. What readiness buys, in casts
# ---------------------------------------------------------------------------
#
# THE AUTHORED NUMBER IS CASTS. Hit points are derived from it.
#
# That inversion is the most important decision in this file after the escape
# guarantees, and it exists to stop a specific bug that a hit-point-first design
# walks straight into: if an underprepared player fights an apex with MORE hit
# points AND does LESS damage per cast because their element is wrong, the two
# penalties MULTIPLY. Fifty-two casts against a 0.25x multiplier is two hundred
# and eight casts. That is not a hard fight, it is a wall with a health bar, and
# it is the exact shape of dead end the brief forbids.
#
# So: `scale_for` computes the damage this loadout actually does per cast —
# including its elemental multiplier and its rung — and sizes the pool so the
# authored cast count is the cast count that HAPPENS. The mismatch is already
# priced once, in readiness, which is what made the fight fifty-two casts in the
# first place. It is not priced twice.
#
# The consequence worth stating out loud, because it looks like rubber-banding
# and is not: overgearing does not trivialise an apex. A rung-nine blade in the
# Highlands hits for far more and the apex has far more to lose, and the fight
# is still twenty-six casts. Preparation buys you a fight HALF AS LONG and an
# incoming multiplier a third lower — it does not buy you a free kill, because a
# free kill is a fight with no typing in it and this game has nothing else.

# THESE TWO ARE NO LONGER THE WHOLE GAME'S NUMBERS. THEY ARE CHAPTER V's.
#
# They kept their names and their values through the chapter ramp in B2 on
# purpose: every other rung is derived from them by `casts_at_ready`, the
# anchor is the chapter the Pass and the Marsh sit on, and `self_check` asserts
# that `casts_at_ready(CHAPTER_ANCHOR) == CASTS_AT_READY`. A reader who arrives
# here first and stops reading has an outdated picture rather than a wrong one.
CASTS_AT_READY = 26      # readiness 100, AT CHAPTER V. Longer than any elite
                         # encounter, and inside the "8 to 20 is the band, above
                         # 20 is a chore" rule only because it is the area's
                         # biggest moment and is meant to be remembered. The
                         # chapter-I rung IS inside that band, at fourteen.
CASTS_AT_UNREADY = 52    # readiness 0, at chapter V. Exactly double, and NOT a
                         # fight you are expected to win. See "the first meeting
                         # is supposed to be a defeat" in the module docstring.
                         # The doubling is now UNREADY_RATIO and holds at every
                         # chapter rather than at this one.

STRIKE_AT_READY = 1.00   # what it hits for, as a multiple of a normal elite.
                         # FLAT ACROSS ALL ELEVEN CHAPTERS: a prepared player is
                         # fighting the fight the area was built to hand them,
                         # and that fight gets no discount for being early.
STRIKE_AT_UNREADY = 1.55 # readiness 0 AT CHAPTER XI, and the ceiling of the
                         # ramp in B3. The floor is STRIKE_AT_UNREADY_FLOOR.

# A ceiling on the derived pool, so an absurd loadout cannot produce an absurd
# number. It has to sit ABOVE the largest pool the ramp can legitimately ask
# for, or the cap silently shortens a fight below its own `target_casts` and the
# client's bar and the engine's tally stop agreeing about the same creature —
# which is the one thing `hunt_view()["fight"]` exists to prevent. The old 2400
# was comfortably above a flat fifty-two casts and is not above eighty-eight.
# `_pool_cap_is_never_reached` sweeps the whole legal space and reports the
# largest pool it found; `self_check` FAILS if that number ever reaches here.
HP_CAP = 3600


# ---------------------------------------------------------------------------
# B2. THE CHAPTER RAMP: how big the place is
# ---------------------------------------------------------------------------
#
# THE HUNT WAS TWENTY-SIX TO FIFTY-TWO CASTS EVERYWHERE, WHICH MEANT THE
# VILLAGE AND THE CASTLE COST THE SAME AFTERNOON.
#
# That was the one number in this file that was authored once and then applied
# seventeen times, and it is the number a player feels most. The Margin-Walker
# is the first hunter anybody meets — it should be a lesson you can sit through
# in one session. The Unnamed is the last thing walking the overworld before
# the portal — it should be an event. Charging the same twenty-six casts for
# both says neither.
#
# So length now ramps, and the axis it ramps along is the CHAPTER, because the
# chapter is the unit of progress this game actually has: `curriculum.CHAPTERS`
# is eleven rungs, each one names the region it is taught in, and the player
# reads their own position in the game off it.
#
# WHY THIS IS NOT A LEVEL CHECK, WHICH IS THE ONLY THING THIS FILE FORBIDS
#
# The chapter used here is A PROPERTY OF THE GROUND, not of the player. It is
# derived from `curriculum.CHAPTERS[i].region` — the map's own statement about
# which chapter is taught where — and it is the same integer for everybody who
# ever stands in that region. A player who walks into the Graph Wastes during
# chapter III meets a chapter-VIII apex, at full chapter-VIII length, and a
# player who comes back at chapter XI meets exactly the same one.
#
# Stated as the two-line division this whole module rests on:
#
#     THE CHAPTER SAYS HOW BIG THE PLACE IS.
#     READINESS SAYS WHERE IN THE PLACE YOU LAND.
#
# Nothing here reads xp, level or mastery, and `_reads_no_progression` still
# greps this file's own source to prove it. `curriculum.CHAPTERS` is consulted
# for `.id`, `.title` and `.region` and for nothing else.
#
# HOW A REGION GETS A CHAPTER
#
# Ten of the seventeen regions are named by a chapter outright. The other seven
# are the ones the curriculum passes through without stopping — the Stringwood,
# the Caverns, the Pass, the Citadel, the Canopy, the Tower — and they inherit
# the chapter of the last named region before them in world order, because that
# is the chapter you are working on while you are standing in them. The tail
# (the Castle) inherits the last chapter for the same reason.
#
# Where a region is named by TWO chapters — Python Village is both chapter I
# and chapter II — the EARLIER one wins. An apex starts hunting you once you
# have cleared three encounters and stayed a hundred and fifty seconds, which
# is early in your time in a region, so the chapter you arrive on is the chapter
# you meet it on.

CHAPTERS = tuple(curriculum.CHAPTERS)
CHAPTER_COUNT = len(CHAPTERS)


def _chapter_by_region() -> dict:
    """region id -> chapter index. Derived from the curriculum, never typed.

    Forward-filled in WORLD ORDER, which is the order a player walks them in,
    so an unclaimed region reads as the chapter that was open when they got
    there. `self_check` prints the whole map so the fill is inspectable.
    """
    anchors: dict = {}
    for index, chapter in enumerate(CHAPTERS):
        anchors.setdefault(chapter.region, index)
    out: dict = {}
    running = 0
    for row in world.REGIONS:
        running = anchors.get(row["id"], running)
        out[row["id"]] = running
    return out


CHAPTER_FOR_REGION = _chapter_by_region()

# The rung the two legacy constants below describe. Chapter V is the Pass and
# the Marsh, it is the middle of the eleven, and it is the region every worked
# example and the default `curve()` in this file already points at. Anchoring
# here is what lets CASTS_AT_READY and CASTS_AT_UNREADY keep both their names
# and their values through a change that makes them vary.
CHAPTER_ANCHOR = CHAPTER_FOR_REGION["twin_pointer_pass"]     # 4, chapter V

# Three casts per chapter, which over the eleven rungs takes the prepared fight
# from fourteen to forty-four. Fourteen is inside the ordinary elite band this
# game already uses ("8 to 20 is the band, above 20 is a chore") and that is the
# point of section B3: the FIRST apex is an ordinary-length fight wearing an
# exam sheet, and only the later ones are long enough to be an occasion.
CASTS_PER_CHAPTER = 3


def chapter_for_region(region_id: str) -> int:
    """Which chapter's ground this is. A map fact, not a player fact."""
    return CHAPTER_FOR_REGION.get(region_id, 0)


def _clamp_chapter(chapter: int) -> int:
    return max(0, min(CHAPTER_COUNT - 1, int(chapter)))


def chapter_view(chapter: int) -> dict:
    """The chapter, in the words the player already sees on the ladder."""
    row = CHAPTERS[_clamp_chapter(chapter)]
    title = row.title
    numeral = title.split(".", 1)[0].strip() if "." in title else str(chapter + 1)
    return {"index": _clamp_chapter(chapter), "number": _clamp_chapter(chapter) + 1,
            "id": row.id, "title": title, "numeral": numeral}


# -- what the ramp pays out, per chapter ------------------------------------
#
# READINESS STILL HALVES THE FIGHT, AT EVERY CHAPTER, AND THAT IS AN INVARIANT
# RATHER THAN A COINCIDENCE.
#
# The old pair was 26 and 52 and the doubling was a fact about two typed
# numbers. Now that both ends move, the doubling is the thing being preserved:
# the unprepared length is DERIVED from the prepared one by UNREADY_RATIO, so
# there is no chapter at which a tuning pass can quietly make preparation worth
# less. `self_check` asserts it over all eleven rungs, and it asserts that the
# legacy constants still agree with the anchor rung, so the two names at the top
# of this section cannot drift away from the table they now describe.

UNREADY_RATIO = 2.0      # readiness 0 is exactly twice readiness 100. Everywhere.


def casts_at_ready(chapter: int) -> int:
    """How many landed lines this chapter's apex is, at readiness 100."""
    return CASTS_AT_READY + CASTS_PER_CHAPTER * (_clamp_chapter(chapter)
                                                 - CHAPTER_ANCHOR)


def casts_at_unready(chapter: int) -> int:
    """...and at readiness 0. Twice the above, by construction."""
    return int(round(casts_at_ready(chapter) * UNREADY_RATIO))


# -- B3. EARLY APEXES TEACH, LATE ONES TEST ---------------------------------
#
# Length is most of this, and the ramp above is most of the answer: the first
# apex a player meets is fourteen casts prepared and twenty-eight unprepared,
# which is a thing you can lose, look at, fix and come back to inside one
# sitting. Fifty-two was not. A first lesson that costs an afternoon is a first
# lesson most players take exactly once, and the lesson they actually take from
# it is "do not go near those".
#
# The second half is HOW HARD IT HITS WHILE IT IS TEACHING YOU. An unprepared
# player at chapter I has a twenty-point bar, no ward, no potions and no
# companion, and 1.55x into that is the harshest ratio in the game arriving at
# the exact moment the player is least able to read why. So the unprepared
# strike ramps too — 1.25x at chapter I, 1.55x at chapter XI — and the PREPARED
# strike stays flat at 1.00x at every chapter, because a prepared player is
# fighting the fight the area was built to hand them and that fight does not get
# a discount for being early.
#
# What that buys, concretely: the early apex leaves you standing long enough to
# watch the tell fire twice. `Apex.tell` is authored for every one of the
# seventeen and it is the only thing in this feature a player can LEARN as
# opposed to buy, and a creature that flattens you before the second telegraph
# has taught nothing.
#
# STRIKE_AT_UNREADY keeps its name and its value: it is now the CEILING of the
# ramp rather than a flat rate, and `tests/test_hunters.py` pins it at 1.55 for
# exactly the reason it always did — one blow must never take a quarter of the
# bar. The floor is a new number and it is the only one here that is not derived.

STRIKE_AT_UNREADY_FLOOR = 1.25    # chapter I. Hard, and survivable enough to read.

# Where the ramp stops teaching and starts testing. Chapters I-IV are the four
# rungs before `curriculum` starts naming algorithm families the player did not
# choose; they are also, not by accident, the four regions with the shortest
# apexes. An apex on a TEACHES chapter is a lesson with a health bar. An apex on
# a TESTS chapter is the practical.
TEACHING_CHAPTERS = 4
TEACHES = "TEACHES"
TESTS = "TESTS"

_STANCE_LINE = {
    TEACHES: "A lesson. Short enough to lose, read, fix and come back to "
             "inside one sitting.",
    TESTS: "A practical. It is long, it hits at full weight, and walking away "
           "is still free.",
}


def strike_at_unready(chapter: int) -> float:
    """Incoming multiplier at readiness 0, ramped across the eleven chapters.

    Linear between STRIKE_AT_UNREADY_FLOOR and STRIKE_AT_UNREADY so that the
    two named constants are the two ends and nothing in between is typed.
    """
    chapter = _clamp_chapter(chapter)
    span = max(1, CHAPTER_COUNT - 1)
    fraction = chapter / span
    return round(STRIKE_AT_UNREADY_FLOOR
                 + (STRIKE_AT_UNREADY - STRIKE_AT_UNREADY_FLOOR) * fraction, 3)


def stance_for_chapter(chapter: int) -> str:
    return TEACHES if _clamp_chapter(chapter) < TEACHING_CHAPTERS else TESTS


def pace_for(region_id: str) -> dict:
    """Everything the ramp says about one region, in one row.

    The row a designer reads, the row `Scaling` folds into its payload, and the
    row the client can render beside the readiness readout so a player can see
    that the length they are being quoted is a property of WHERE THEY ARE
    STANDING rather than of how well they have done.
    """
    chapter = chapter_for_region(region_id)
    stance = stance_for_chapter(chapter)
    return {
        "region": region_id,
        "chapter": chapter,
        "chapter_view": chapter_view(chapter),
        "casts_ready": casts_at_ready(chapter),
        "casts_unready": casts_at_unready(chapter),
        "strike_ready": STRIKE_AT_READY,
        "strike_unready": strike_at_unready(chapter),
        "stance": stance,
        "stance_line": _STANCE_LINE[stance],
    }


def ramp_table() -> list:
    """The ramp, chapter by chapter, with the regions that sit on each rung.

    Section A of the brief asks for this table reported rather than asserted,
    so it is a function and `self_check` prints it. A chapter with no regions on
    it is not a defect: Python Village is chapter I and chapter II both, and the
    apex meets you on the first of them, so rung II is defined and currently
    unoccupied. It stays defined so that a chapter that later gains a region
    gains a length with it.
    """
    rows = []
    for chapter in range(CHAPTER_COUNT):
        regions = [r["id"] for r in world.REGIONS
                   if chapter_for_region(r["id"]) == chapter]
        rows.append({
            **chapter_view(chapter),
            "casts_ready": casts_at_ready(chapter),
            "casts_unready": casts_at_unready(chapter),
            "strike_ready": STRIKE_AT_READY,
            "strike_unready": strike_at_unready(chapter),
            "stance": stance_for_chapter(chapter),
            "regions": regions,
            "apexes": [APEX_BY_REGION[r].id for r in regions
                       if r in APEX_BY_REGION],
        })
    return rows


def playthrough_cost() -> dict:
    """What fighting every apex once costs, in landed lines.

    One landed line is one graded submission is one cleared encounter, so this
    number is directly comparable to the size of the corpus. Reported for both
    ends of the readiness axis and against the flat 26/52 this replaced, because
    the honest headline is not the total — it is that the total barely moved
    while the SHAPE of it changed completely.
    """
    ready = sum(casts_at_ready(chapter_for_region(a.region)) for a in APEXES)
    unready = sum(casts_at_unready(chapter_for_region(a.region)) for a in APEXES)
    flat_ready = CASTS_AT_READY * len(APEXES)
    return {
        "apexes": len(APEXES),
        "prepared_casts": ready,
        "unprepared_casts": unready,
        "was_flat_prepared": flat_ready,
        "was_flat_unprepared": CASTS_AT_UNREADY * len(APEXES),
        "delta_prepared": ready - flat_ready,
        "shortest": min(casts_at_ready(chapter_for_region(a.region))
                        for a in APEXES),
        "longest": max(casts_at_ready(chapter_for_region(a.region))
                       for a in APEXES),
    }


@dataclass
class Scaling:
    """The apex, sized for one specific player, at one specific moment.

    `chapter` and `pace` are NEW and they are additive: every existing key keeps
    its name, its type and its meaning, so `web/js/huntui.js` and `main.js`
    (both of which read `scaling.target_casts`) need no change to keep working
    and one line each to start saying WHY the number is what it is.
    """
    apex: str
    region: str
    readiness: int
    band: str
    target_casts: int
    hp: int
    strike_multiplier: float
    per_cast_damage: float
    matchup: str
    elements: tuple
    blurb: str
    # Defaulted so that every positional construction already in the tree —
    # engine.py builds a blank `Scaling(apex.id, region_id, 0, "", 0, 0, 1.0,
    # 1.0, "", (), "")` when a region has no apex — keeps working untouched.
    chapter: int = 0
    pace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"apex": self.apex, "region": self.region,
                "readiness": self.readiness, "band": self.band,
                "target_casts": self.target_casts, "hp": self.hp,
                "strike_multiplier": round(self.strike_multiplier, 3),
                "per_cast_damage": round(self.per_cast_damage, 2),
                "matchup": self.matchup, "elements": list(self.elements),
                "blurb": self.blurb,
                # The two ends of this region's band, shipped beside the number
                # actually in force, so the client can draw "31 of a possible
                # 23-46" without a second copy of the ramp in JavaScript.
                "chapter": self.chapter,
                "pace": dict(self.pace)}


def expected_cast_damage(apex: Apex, loadout: Loadout) -> tuple:
    """What one competent cast from this loadout does to this apex.

    `(damage, matchup_kind)`. Uses `elements.matchup_multi` so a dual or triple
    apex resolves through exactly the weighted mean the wheel already promises,
    and `RUNG_DAMAGE_SCALE` for the weapon. Armour is not in here: the apex's
    own mitigation belongs to whatever builds its `elements.Defender`, and
    double-counting it would shorten every fight by a third.
    """
    mult, kind, _rows = elements.matchup_multi(loadout.weapon_element,
                                               apex.elements)
    rung = max(0, min(9, int(loadout.weapon_rung or 0)))
    return (CAST_DAMAGE_REFERENCE * RUNG_DAMAGE_SCALE[rung] * mult), kind


def scale_for(region_id: str, loadout: Loadout | None = None, *,
              ready: Readiness | None = None) -> Scaling | None:
    """Size this region's apex against this player. Pure.

    Called ONCE, when the encounter starts, and the result is frozen for the
    duration. Freezing it is not an optimisation: it is what stops a player
    stripping their gear mid-fight to shrink the pool, and it is what stops the
    pool growing under somebody who upgrades between rounds.
    """
    apex = apex_for(region_id)
    if apex is None:
        return None
    lo = loadout or Loadout()
    r = ready or readiness(region_id, lo)

    # THE TWO AXES, IN THE ORDER THEY ARE READ.
    #
    # The chapter picks the band this region's fight lives in; readiness picks
    # the point inside it. Swapping that order would be the level check this
    # file exists to refuse: a band chosen by the player's progress rather than
    # by the ground would make the same creature a different size for two people
    # standing in the same doorway.
    chapter = chapter_for_region(region_id)
    low, high = casts_at_ready(chapter), casts_at_unready(chapter)
    hardest = strike_at_unready(chapter)

    fraction = max(0.0, min(1.0, r.score / 100.0))
    casts = high + (low - high) * fraction
    strike = hardest + (STRIKE_AT_READY - hardest) * fraction

    per_cast, kind = expected_cast_damage(apex, lo)
    hp = min(HP_CAP, int(round(casts * per_cast)))

    return Scaling(
        apex=apex.id, region=region_id, readiness=r.score, band=r.band,
        target_casts=int(round(casts)), hp=hp,
        strike_multiplier=strike, per_cast_damage=per_cast,
        matchup=kind, elements=apex.elements,
        blurb=band_blurb(r.score),
        chapter=chapter, pace=pace_for(region_id),
    )


def curve(region_id: str = "twin_pointer_pass", *,
          loadout: Loadout | None = None) -> list:
    """The difficulty curve, reported rather than asserted.

    Section B of the brief asks for the curve to be reported. This is it: the
    same apex at five readiness scores, with the cast count and the incoming
    multiplier each one produces. `self_check` calls it and prints the table.

    The default region is the Pass, which is CHAPTER_ANCHOR's ground, so this
    curve still runs from CASTS_AT_UNREADY down to CASTS_AT_READY exactly as it
    did before the ramp existed. Pass any other region and the two ends move to
    that chapter's band; `ramp_table()` is the across-chapters view.
    """
    apex = apex_for(region_id)
    chapter = chapter_for_region(region_id)
    low, high = casts_at_ready(chapter), casts_at_unready(chapter)
    hardest = strike_at_unready(chapter)
    rows = []
    for score in (0, 25, 50, 75, 100):
        fraction = score / 100.0
        casts = high + (low - high) * fraction
        strike = hardest + (STRIKE_AT_READY - hardest) * fraction
        rows.append({
            "readiness": score, "band": band_for(score),
            "chapter": chapter,
            "casts": int(round(casts)),
            "strike_multiplier": round(strike, 3),
            "bounty_metal": _metal_units(score),
            "trophy_chance": round(_trophy_chance(score), 3),
            "note": band_blurb(score),
        })
    if apex is not None:
        for row in rows:
            row["apex"] = apex.id
    return rows


# ---------------------------------------------------------------------------
# C. The hunt
# ---------------------------------------------------------------------------
#
# "Actively but slowly tries to hunt down the player." Slowly is the brief's
# word and it is the correct one: the tension in a hunter is WATCHING IT COME.
# An ambush is a jump scare, which is a thing you feel once; an approach you can
# see and measure is a thing you feel for ten minutes, and it is also the only
# version that is compatible with never cornering anybody.
#
# THE STATE MACHINE, and what the player can see at each stage
#
#   DORMANT    nothing exists. The region is quiet.
#   STIRRING   it is going to exist in STIR_SECONDS. A line of banter, the
#              region music drops a voice, and NOTHING is on the map yet. Twenty
#              seconds of warning before there is a creature at all.
#   ROAMING    it exists and it does not know where you are. It walks its own
#              circuit at 38 px/s. The minimap shows a HEADING only — an arrow
#              at the edge, no position.
#   TRACKING   it has your scent and is following your TRAIL. 52 px/s. The
#              minimap shows a position that updates every 2 seconds and is
#              therefore always a little stale, which is honest: it knows where
#              you WERE.
#   CLOSING    it has line of sight. 74 px/s, which is still two thirds of
#              walking pace. Continuous position, a vignette in its element
#              colour, and a seconds-to-contact readout, because "a player
#              always knows how much time they have" is a requirement and the
#              honest way to meet it is to print the number.
#   ENGAGED    the fight. `scale_for` has been called and frozen.
#   FADING     it has given up. Six seconds of it turning and walking off, so
#              that giving up is visible and the player learns the rule.
#   SPENT      killed or fled from. Cooldown, then DORMANT.
#
# THE SCENT, and why it costs nothing to implement
#
# overworld.js already keeps a ring buffer of the player's recent positions, for
# the companion, which "retraces rather than pathfinds" — ground behind you is
# ground you were allowed to stand on, so a follower using it can never clip a
# wall or wedge on a corner. The apex uses the SAME buffer from the other end.
# It does not pathfind to you. It walks to a sample SCENT_LAG pixels of walked
# ground behind you and then to the next one.
#
# Three real consequences fall out of that for free:
#
#   * it cannot get stuck, for exactly the reason the companion cannot
#   * STANDING STILL ADDS NO SAMPLES, so standing still makes you harder to
#     track, and sprinting in a straight line makes you trivial to track. That
#     is a genuine tactic that the player can discover, and it is emergent from
#     a data structure that already exists
#   * it rounds corners the way you rounded them, so it looks like it is
#     following you rather than homing on you
#
# The exception is the Lattice Stag, which takes roads instead of scent, because
# its region is the graph region and an apex that ignored the lattice there
# would be a missed lesson. `SCENT_MODE` names it.

HUNT_STATES = ("DORMANT", "STIRRING", "ROAMING", "TRACKING", "CLOSING",
               "ENGAGED", "FADING", "SPENT")

# -- speeds. G1 lives here --------------------------------------------------
#
# THE SINGLE MOST IMPORTANT NUMBER IN THIS FILE IS 74 < 112.
#
# Not "usually". Not "unless it is enraged". There is no enrage. No apex has any
# state in which it moves faster than 74 px/s and the player walks at 112, so a
# player who holds a direction gains 38 pixels a second, forever, in every
# region, at every readiness. Fleeing is subtraction. `self_check` asserts it
# over the whole table and `escape_guarantees` states it as a sentence.
STATE_SPEED = {
    "DORMANT": 0.0, "STIRRING": 0.0,
    "ROAMING": 38.0,      # 34% of walking pace. A wander, not a pursuit.
    "TRACKING": 52.0,     # 46%. Purposeful and still obviously slower than you.
    "CLOSING": 74.0,      # 66%. The fastest anything here ever moves.
    "ENGAGED": 0.0, "FADING": 22.0, "SPENT": 0.0,
}
APEX_MAX_SPEED = max(STATE_SPEED.values())
SPEED_MARGIN = PLAYER_WALK_SPEED - APEX_MAX_SPEED     # 38.0 px/s in your favour

# -- spawn conditions -------------------------------------------------------
#
# An apex must never be the first thing a player meets in an area. Every
# condition below exists to make sure the creature arrives AFTER the area has
# had a chance to teach its own lesson gently, so that the apex is an exam on
# something rather than an introduction to it.
MIN_REGION_DWELL_S = 150.0      # seconds actually spent in the region
MIN_REGION_CLEARS = 3           # encounters won here first. Meet the area first.
SPAWN_PRESSURE_S = 90.0         # further eligible seconds before it stirs
REGION_COOLDOWN_S = 600.0       # after one is resolved, that region rests
GLOBAL_COOLDOWN_S = 240.0       # and no two regions hunt you back to back
STIR_SECONDS = 20.0             # warning before the creature exists

# Never in these places, for the reasons in section D.
SANCTUARY_PX = 6 * TILE         # 96. Town, shop, forge, save point, boss door.
EXIT_SAFE_PX = 8 * TILE         # 128. Any region boundary or warp.
# Both are further out than NOTICE_PX (384) on purpose: a creature that spawned
# inside its own notice radius would go from "appeared" to "has your scent" in
# about four seconds, and ROAMING — the state the whole "slowly" promise lives
# in — would be a word rather than a behaviour.
SPAWN_MIN_PX = 26 * TILE        # 416. It never appears on top of you.
SPAWN_MAX_PX = 40 * TILE        # 640. Nor so far away that it is theoretical.

# Never at all, in these conditions.
SPAWNS_WHILE_SEALED = False     # finalexam.sealed(enc, anything) -> no apex.
SPAWNS_IN_DUNGEONS = False      # G5. It is an overworld creature.
LOW_HEALTH_FRACTION = 0.30      # G7. Below this it will not spawn or close.
MIN_FREE_TILES = 24             # G4. Less reachable ground than this -> no hunt.

# -- the approach -----------------------------------------------------------
NOTICE_PX = 24 * TILE           # 384. Picks up the scent inside this.
CLOSE_PX = 10 * TILE            # 160. Has line of sight; commits.
CONTACT_PX = int(1.25 * TILE)   # 20. The fight starts.
GIVE_UP_PX = 30 * TILE          # 480. Beyond this it starts losing you.
BREAK_SECONDS = 8.0             # ...and after this long beyond it, it stops.
PATIENCE_SECONDS = 90.0         # tracking without closing the gap. Then it stops.
FADE_SECONDS = 6.0              # visibly turning and leaving.

# ROAMING is the state a player who is standing still and typing meets, and it
# needs its own two numbers or it is a state with no exit. See the ROAMING
# branch of `hunt_step` for what went wrong without them.
ROAM_FLOOR_PX = CLOSE_PX        # 160. It will not walk onto somebody it has
                                # not found. TRACKING has to start with ground
                                # in hand or the approach is not an approach.
ROAM_PATIENCE_SECONDS = 120.0   # a circuit that turns up nothing ends. Longer
                                # than PATIENCE_SECONDS because a creature that
                                # has your trail has a reason to persist and one
                                # that is merely walking around does not.

SCENT_HALFLIFE_S = 45.0         # a trail sample's usefulness halves this often
SCENT_LAG_PX = {"TRACKING": 160.0, "CLOSING": 64.0}
SCENT_MODE = {"lattice_stag": "ROADS"}   # the one exception, and it is a lesson

# ---------------------------------------------------------------------------
# The telegraph. One row per state, three channels, no exceptions.
# ---------------------------------------------------------------------------
#
# "It should telegraph at every stage so a player always knows how much time
# they have." Taken literally: every state below says what the player HEARS,
# what they SEE on the screen edge, and what the MAP shows, and the last two
# states before contact print an actual number of seconds. A hunter you cannot
# measure is a hunter you can only be surprised by, and being surprised is the
# one thing this design is not for.
#
# `vignette` is alpha on a screen-edge wash in the apex's element colour.
# `map` is one of: none | heading | stale | live.
TELEGRAPH = {
    "STIRRING": {
        "audio": "region music drops its top voice; one distant footfall, "
                 "off-screen, repeating slowly",
        "vignette": 0.00, "map": "none", "countdown": False,
        "line": "Something in {region} has stopped what it was doing.",
        "seconds_of_warning": STIR_SECONDS,
    },
    "ROAMING": {
        "audio": "footfalls, panned, distance-attenuated. No music change.",
        "vignette": 0.06, "map": "heading", "countdown": False,
        "line": "{name} is walking its circuit. It has not found you.",
        "seconds_of_warning": None,
    },
    "TRACKING": {
        "audio": "the footfalls acquire a pulse and stop being random",
        "vignette": 0.12, "map": "stale", "countdown": False,
        "line": "{name} has your trail. It knows where you were.",
        "seconds_of_warning": None,
    },
    "CLOSING": {
        "audio": "a heartbeat under the footfalls, locked to its stride",
        "vignette": 0.22, "map": "live", "countdown": True,
        "line": "{name} has you. {seconds} seconds.",
        "seconds_of_warning": None,
    },
    "ENGAGED": {
        "audio": "battle theme, region variant",
        "vignette": 0.00, "map": "live", "countdown": False,
        "line": "{name}.",
        "seconds_of_warning": None,
    },
    "FADING": {
        "audio": "the heartbeat drops out first, then the pulse",
        "vignette": 0.10, "map": "stale", "countdown": False,
        "line": "{name} has lost you. It is going back.",
        "seconds_of_warning": FADE_SECONDS,
    },
}


@dataclass
class Hunt:
    """One region's hunt, as plain data. Serialisable, no objects inside.

    This is the whole of the state `web/js/overworld.js` mirrors and the whole
    of what a save has to keep. Everything else is derived by `hunt_step`.
    """
    region: str = ""
    state: str = "DORMANT"
    apex: str = ""
    elapsed: float = 0.0        # seconds in the current state
    dwell: float = 0.0          # seconds spent in the region this visit
    pressure: float = 0.0       # eligible seconds banked toward a spawn
    # WHERE IT IS, WHEN ANYBODY ACTUALLY KNOWS.
    #
    # `None` until a caller that HAS A MAP fills them in. This module does not
    # have one: a `Moment` carries the player's position, a reachable-tile count
    # and nothing else, so nothing here can say which tile is walkable, and a
    # position invented without that knowledge is a creature standing in rock.
    # The client owns the placement (`apex.js` `_place`, a deterministic scan
    # for an open tile inside the engine's own spawn band) and this module owns
    # the STATE and the SCALAR DISTANCE, which is all the chase arithmetic in
    # `hunt_step` is written in.
    #
    # They default to None rather than to 0.0 because zero is a POSITION and it
    # is the worst one available. `to_dict` used to ship `x: 0.0, y: 0.0`, which
    # `apex.js` reads as a finite tile coordinate, so it declared the row
    # authoritative, pinned the creature to the top-left corner of the map for
    # the whole hunt, and never ran its own placement. A field that is unset
    # has to SERIALISE as unset; see `to_dict`, which omits the keys entirely,
    # because `Number(null)` is 0 in JavaScript and only a missing key reads as
    # missing.
    x: float | None = None
    y: float | None = None
    distance: float = 0.0       # px to the player, last measured
    best_distance: float = 0.0  # closest it has got this hunt. Drives patience.
    beyond: float = 0.0         # seconds spent past GIVE_UP_PX
    scent: float = 0.0          # 0..1, decays on SCENT_HALFLIFE_S
    cooldown: float = 0.0       # seconds until this region may hunt again
    spawns: int = 0             # how many times this region has hunted you
    kills: int = 0              # how many of those you finished
    flights: int = 0            # how many of those you walked away from

    def to_dict(self) -> dict:
        row = {"region": self.region, "state": self.state, "apex": self.apex,
               "elapsed": round(self.elapsed, 2), "dwell": round(self.dwell, 2),
               "pressure": round(self.pressure, 2),
               "distance": round(self.distance, 1),
               "best_distance": round(self.best_distance, 1),
               "beyond": round(self.beyond, 2), "scent": round(self.scent, 3),
               "cooldown": round(self.cooldown, 2), "spawns": self.spawns,
               "kills": self.kills, "flights": self.flights}
        # Omitted, not nulled. See the note on `x`.
        if self.x is not None and self.y is not None:
            row["x"] = round(float(self.x), 2)
            row["y"] = round(float(self.y), 2)
        return row


def new_hunt(region_id: str) -> Hunt:
    apex = apex_for(region_id)
    return Hunt(region=region_id, apex=(apex.id if apex else ""))


@dataclass
class Moment:
    """What `hunt_step` is allowed to know about right now. Nothing else.

    Named `Moment` rather than `World` for a boring and load-bearing reason:
    this module imports `gauntlet.world`, and a parameter called `world` would
    shadow it inside every function that takes one. That is the kind of thing
    that works until somebody adds one line and then does not.

    Every field is something the overworld already has or can compute in O(1),
    because a hunt tick runs every frame and a hunt tick that needed a pathfind
    would be a hunt tick somebody eventually removed.
    """
    player_x: float = 0.0
    player_y: float = 0.0
    moving: bool = False            # the player covered ground this tick
    health_fraction: float = 1.0
    in_dungeon: bool = False
    in_sanctuary: bool = False      # within SANCTUARY_PX of town/shop/save/door
    near_exit: bool = False         # within EXIT_SAFE_PX of a boundary or warp
    free_tiles: int = 999           # reachable open ground around the player
    clears: int = 0                 # encounters won in this region
    sealed: bool = False            # finalexam.sealed(enc, ...) — passed in
    in_battle: bool = False
    global_cooldown: float = 0.0
    # Deterministic jitter source. A seed, not a random number: nothing in this
    # module or its mirror may call random() in a per-frame path.
    seed: int = 0


def _fnv(text: str, seed: int = 0) -> int:
    """FNV-1a, the same hash overworld.js already uses, so a jitter computed
    here and a jitter computed there agree to the bit."""
    h = 2166136261 ^ (seed & 0xFFFFFFFF)
    for ch in text:
        h ^= ord(ch) & 0xFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _jitter(hunt: Hunt, moment: Moment, span: float) -> float:
    """A stable offset in [0, span). Same region, same seed, same answer, every
    run, on every machine. Deterministic replays are worth more than surprise."""
    return (_fnv(f"{hunt.region}:{hunt.spawns}", moment.seed) % 1000) / 1000.0 * span


# ---------------------------------------------------------------------------
# D. The escape. Written first; everything above fits inside it.
# ---------------------------------------------------------------------------
#
# These are not safeties bolted onto a chase. They are the specification, and
# the chase is what is left over once they are satisfied. Read `hunt_step` and
# notice the order: guarantees, then drama, and the drama never gets a vote.

FLEE_ALWAYS_SUCCEEDS = True     # G2. There is no roll and there never will be.
FLEE_HEALTH_COST = 3            # flat points off the bar. The only cost.
FLEE_BREAKS_COMBO = True        # you lose the streak. Nothing else.
FLEE_COOLDOWN_SCALE = 0.5       # it remembers: this region rests half as long.
FLEE_COSTS_GOLD = False
FLEE_COSTS_ITEMS = False
FLEE_COSTS_MASTERY = False      # and it never will. Mastery is earned by casting.
FLEE_AVAILABLE_FROM_TURN = 1    # turn one included.


def escape_guarantees() -> dict:
    """The eight promises, as checkable facts rather than as intentions.

    `self_check` runs every one of these against the live tables. If a tuning
    pass ever raises a speed or invents an enrage state, this stops being true
    and the check fails with the number that broke it.
    """
    worst_hp = HP_CAP
    return {
        "G1_cannot_outrun_you": {
            "holds": APEX_MAX_SPEED < PLAYER_WALK_SPEED,
            "apex_max_speed": APEX_MAX_SPEED,
            "player_walk_speed": PLAYER_WALK_SPEED,
            "margin_px_per_second": SPEED_MARGIN,
            "says": "Hold a direction and you gain 38 pixels a second. In every "
                    "region, in every state, at every readiness. There is no "
                    "enrage state and no apex has a dash.",
        },
        "G2_flight_always_works": {
            "holds": FLEE_ALWAYS_SUCCEEDS and FLEE_AVAILABLE_FROM_TURN == 1,
            "roll": None,
            "cost": {"health": FLEE_HEALTH_COST, "combo": FLEE_BREAKS_COMBO,
                     "gold": FLEE_COSTS_GOLD, "items": FLEE_COSTS_ITEMS,
                     "mastery": FLEE_COSTS_MASTERY},
            "says": "Fleeing is a button, not a chance. It costs three points "
                    "of health and your streak, and the region remembers and "
                    "rests half as long. It never costs gold, an item, or one "
                    "point of mastery.",
        },
        "G3_leaving_the_region_always_works": {
            "holds": True,
            "exit_safe_px": EXIT_SAFE_PX,
            "follows_across_boundary": False,
            "says": "It never crosses a region boundary, never spawns within "
                    "eight tiles of one, and a region change resolves the hunt "
                    "to SPENT before the new region has loaded.",
        },
        "G4_never_corners_you": {
            "holds": MIN_FREE_TILES > 0,
            "min_free_tiles": MIN_FREE_TILES,
            "spawn_min_px": SPAWN_MIN_PX,
            "says": "It never spawns closer than twenty-six tiles, never in "
                    "your room, and an active hunt is forced to FADING the "
                    "instant your reachable ground drops below twenty-four "
                    "tiles. The corner check runs before the pursuit, every "
                    "tick, and it cannot be outvoted.",
        },
        "G5_never_traps_you_in_a_dungeon": {
            "holds": not SPAWNS_IN_DUNGEONS,
            "says": "An apex is an overworld creature. It does not spawn in a "
                    "dungeon and a hunt carried to a threshold goes DORMANT at "
                    "the door. dungeons.py never has to know this module "
                    "exists.",
        },
        "G6_takes_only_time": {
            "holds": not (FLEE_COSTS_GOLD or FLEE_COSTS_ITEMS
                          or FLEE_COSTS_MASTERY),
            "says": "No apex takes a capability, seals an exit, destroys an "
                    "item, spends gold, blocks a save, or touches mastery. The "
                    "only resource it consumes is minutes, and minutes spent "
                    "typing Python are the thing this game is for.",
        },
        "G7_will_not_close_on_a_dying_player": {
            "holds": 0.0 < LOW_HEALTH_FRACTION < 1.0,
            "low_health_fraction": LOW_HEALTH_FRACTION,
            "says": "Below thirty percent of your bar it will not enter "
                    "CLOSING and will not spawn. It holds at TRACKING, which "
                    "is 52 px/s against your 112, and you walk out.",
        },
        "G8_every_fight_terminates": {
            "holds": elements.MIN_DAMAGE >= 1,
            "min_damage": elements.MIN_DAMAGE,
            "worst_case_pool": worst_hp,
            "hard_bound_casts": worst_hp // max(1, elements.MIN_DAMAGE),
            "says": "elements.resolve_damage floors every landed cast at one "
                    "point, so even the worst-armed fight against the largest "
                    "pool this module can produce ends in a finite number of "
                    "casts. That bound is enormous and it is not the promise "
                    "that matters — G2 is. It is stated so that nobody has to "
                    "wonder whether an infinite case exists. It does not.",
        },
    }


def corner_check(moment: Moment) -> bool:
    """True when the player has room. G4, isolated so it is impossible to skip.

    Called at the top of `hunt_step` and again before any transition INTO
    CLOSING. Two calls rather than one because the geometry can change under a
    player who walks into a cul-de-sac while being chased, and that is precisely
    the moment the guarantee is for.
    """
    return moment.free_tiles >= MIN_FREE_TILES


def can_flee(hunt: Hunt, turn: int = 1) -> dict:
    """Always yes. The function exists so that the answer is a value the UI can
    render on turn one rather than a rule somebody has to remember."""
    return {"allowed": True, "roll": None, "turn": turn,
            "cost": {"health": FLEE_HEALTH_COST, "combo": FLEE_BREAKS_COMBO},
            "line": "You can leave. It costs three health and your streak, and "
                    "it works."}


def flee(hunt: Hunt) -> Hunt:
    """Resolve a flight. Always succeeds; the only cost is stated in `can_flee`.

    The region's cooldown is HALVED rather than reset, which is the one place
    this module lets the drama have something: it remembers that you ran, and it
    comes back sooner. That is pressure, not punishment — the fight it comes
    back for is the same fight, and by then you will have had time to fix
    whatever `Readiness.advice` told you was missing.
    """
    out = Hunt(**vars(hunt))
    out.state = "SPENT"
    out.elapsed = 0.0
    out.scent = 0.0
    out.flights += 1
    out.cooldown = REGION_COOLDOWN_S * FLEE_COOLDOWN_SCALE
    return out


def leave_region(hunt: Hunt) -> Hunt:
    """G3. A region change resolves the hunt. No pursuit crosses a boundary."""
    out = Hunt(**vars(hunt))
    out.state = "SPENT"
    out.elapsed = 0.0
    out.dwell = 0.0
    out.pressure = 0.0
    out.scent = 0.0
    out.distance = 0.0
    out.cooldown = max(out.cooldown, GLOBAL_COOLDOWN_S)
    return out


# ---------------------------------------------------------------------------
# C2. The tick
# ---------------------------------------------------------------------------

def spawn_check(hunt: Hunt, moment: Moment, dt: float) -> dict:
    """Is this region allowed to start hunting, and is it ready to?

    Split out of `hunt_step` because it is the function a reviewer will want to
    read on its own, and because the overworld may want to ask the question
    without advancing anything.
    """
    apex = apex_for(hunt.region)
    blockers = []
    if apex is None:
        blockers.append("no apex for this region")
    if moment.sealed and not SPAWNS_WHILE_SEALED:
        blockers.append("sealed run")
    if moment.in_dungeon and not SPAWNS_IN_DUNGEONS:
        blockers.append("in a dungeon")          # G5
    if moment.in_battle:
        blockers.append("already in a fight")
    if moment.in_sanctuary:
        blockers.append("in a sanctuary")        # G4
    if moment.near_exit:
        blockers.append("too close to the way out")   # G3
    if not corner_check(moment):
        blockers.append("not enough open ground")     # G4
    if moment.health_fraction < LOW_HEALTH_FRACTION:
        blockers.append("player is hurt")             # G7
    if hunt.cooldown > 0:
        blockers.append("region is resting")
    if moment.global_cooldown > 0:
        blockers.append("something else hunted you recently")
    if moment.clears < MIN_REGION_CLEARS:
        blockers.append(f"meet the area first ({moment.clears}/"
                        f"{MIN_REGION_CLEARS} cleared)")
    if hunt.dwell < MIN_REGION_DWELL_S:
        blockers.append(f"dwell {hunt.dwell:.0f}s/{MIN_REGION_DWELL_S:.0f}s")

    eligible = not blockers
    needed = SPAWN_PRESSURE_S + _jitter(hunt, moment, 30.0)
    return {"eligible": eligible, "blockers": tuple(blockers),
            "pressure": hunt.pressure, "needed": round(needed, 1),
            "ready": eligible and hunt.pressure + dt >= needed}


def hunt_step(hunt: Hunt, moment: Moment, dt: float) -> tuple:
    """Advance one region's hunt by `dt` seconds. Pure: returns a NEW Hunt.

    THE ORDER OF THIS FUNCTION IS THE ARGUMENT OF THIS FILE.

    The guarantees are evaluated first and they can end the hunt outright. Only
    if every one of them is satisfied does any pursuit logic run at all. If a
    guarantee and the drama disagree, THE GUARANTEE WINS AND THE CHASE ENDS —
    there is no weighting, no grace period and no "but it was so close". A
    hunter that cornered one player once is a hunter every player learns to
    avoid an entire region over, and an avoided region is a lesson nobody gets.

    Returns `(hunt, events)` where events is a tuple of strings the overworld
    turns into banter, audio cues and map changes.
    """
    out = Hunt(**vars(hunt))
    events: list = []
    dt = max(0.0, float(dt))

    out.cooldown = max(0.0, out.cooldown - dt)
    out.dwell += dt
    # Scent decays on wall-clock, not on distance, so standing still loses you.
    if out.scent > 0:
        out.scent *= 0.5 ** (dt / SCENT_HALFLIFE_S)

    # -- the guarantees, before anything else ------------------------------
    #
    # THE OVERRIDE FIRES ON THE TRANSITION, NOT ON THE CONDITION.
    #
    # An earlier draft set FADING and returned every tick the condition held,
    # which reads as the safer code and is the opposite. `elapsed` was reset on
    # each of those ticks, so the FADING timer below never advanced and the hunt
    # never reached SPENT: a player who stepped into a dungeon to get away got a
    # creature pinned outside the door forever — still embodied, still painting
    # a vignette, and with the region's cooldown never set, so the region could
    # not rest and could not hunt again either. The guarantee held (nothing
    # could reach them) while the state machine quietly stopped being a machine.
    #
    # So the override now does one thing once: it starts the retreat. Everything
    # after it, including the six seconds of FADING and the SPENT that follows,
    # is the ordinary machine running. A creature that is already leaving is not
    # made to leave harder.
    if out.state not in ("DORMANT", "SPENT", "ENGAGED", "FADING"):
        stop = None
        if moment.in_dungeon and not SPAWNS_IN_DUNGEONS:
            stop = "dungeon threshold"              # G5
        elif not corner_check(moment):
            stop = "no room"                        # G4
        elif moment.in_sanctuary:
            stop = "sanctuary"                      # G4
        if stop:
            out.state = "FADING"
            out.elapsed = 0.0
            events.append(f"give_up:{stop}")
            return out, tuple(events)

    state = out.state
    out.elapsed += dt

    if state == "DORMANT":
        check = spawn_check(out, moment, dt)
        if check["eligible"]:
            out.pressure += dt if moment.moving else dt * 0.25
            if check["ready"]:
                out.state = "STIRRING"
                out.elapsed = 0.0
                out.pressure = 0.0
                out.spawns += 1
                events.append("stir")
        else:
            out.pressure = max(0.0, out.pressure - dt * 0.5)

    elif state == "STIRRING":
        if out.elapsed >= STIR_SECONDS:
            out.state = "ROAMING"
            out.elapsed = 0.0
            out.distance = SPAWN_MIN_PX + _jitter(
                out, moment, SPAWN_MAX_PX - SPAWN_MIN_PX)
            out.best_distance = out.distance
            events.append("appear")

    elif state == "ROAMING":
        # A wander, not an approach. It closes at a fifth of its own walking
        # speed — about 7.6 px/s — because a circuit that happens to cross yours
        # closes ground far more slowly than something walking at you. From the
        # spawn band that is between four and thirty-four seconds of visible,
        # unhurried, not-yet-aware creature, which is the state the brief's
        # "slowly" is actually made of.
        #
        # TWO FLOORS, AND THE PLAYER THIS GAME ACTUALLY HAS.
        #
        # A player in this game spends most of their time STANDING STILL AND
        # TYPING PYTHON. That is not an edge case, it is the main loop, and an
        # earlier draft of this branch handled it badly in both directions:
        # distance decayed to literally zero and `scent` only grows for a moving
        # player, so a creature that had not found anybody walked up and stood
        # on them, indefinitely, in a state with no exit — no contact, no give
        # up, no cooldown, and a telegraph that never stopped. The first move
        # after that was an ambush from nought pixels, which is the jump scare
        # the module docstring spends a paragraph refusing to build.
        #
        #   ROAM_FLOOR_PX   it will not walk nearer than line-of-sight to
        #                   somebody it has not found. Ten tiles is still close
        #                   enough to be alarming and far enough that TRACKING
        #                   starts with ground to give away.
        #   ROAM_PATIENCE_S a circuit that turns up nothing ends. Standing still
        #                   adds no scent, so a player who genuinely never moves
        #                   is a player it genuinely never finds, and it goes
        #                   home. That is the same tactic this file already
        #                   advertises, followed through to its conclusion.
        out.distance = max(ROAM_FLOOR_PX,
                           out.distance - STATE_SPEED["ROAMING"] * dt * 0.20)
        if moment.moving:
            out.scent = min(1.0, out.scent + dt / 12.0)
        if out.distance <= NOTICE_PX and out.scent >= 0.35:
            out.state = "TRACKING"
            out.elapsed = 0.0
            out.best_distance = out.distance
            events.append("scent")
        elif out.elapsed >= ROAM_PATIENCE_SECONDS:
            out.state = "FADING"
            out.elapsed = 0.0
            events.append("give_up:circuit")

    elif state == "TRACKING":
        # The whole chase, in one line of arithmetic: a moving player gains
        # (112 - 52) px/s and a standing player loses 52. There is no third
        # case, no acceleration term and no catch-up multiplier, because any of
        # those would be the place G1 quietly stopped being true.
        #
        # THE FLOOR IS `SCENT_LAG_PX`, AND IT USED TO BE DECORATION.
        #
        # This module's section C says in prose what TRACKING is: the creature
        # does not home on you, it walks to a sample of walked ground
        # SCENT_LAG_PX behind you and then to the next one. That constant was
        # shipped in `client_payload` and read by nothing, and the arithmetic
        # here let distance collapse to nought instead — so a player who stood
        # still ended up with a tracking apex standing ON them, at zero
        # pixels, printing "it knows where you WERE" about a square it was
        # occupying.
        #
        # It matters most in exactly the case G7 exists for. A player below
        # thirty percent is demoted out of CLOSING and held here, and "held at
        # TRACKING" has to mean held at a distance or the guarantee is a label
        # on a creature breathing on them. Ten tiles is the trail's lag and ten
        # tiles is where it waits.
        #
        # CLOSING has no equivalent floor and must not have one: that state's
        # entire job is to arrive, it has line of sight rather than a trail,
        # and a floor there would be a fight that can never start.
        rate = ((PLAYER_WALK_SPEED - STATE_SPEED["TRACKING"]) if moment.moving
                else -STATE_SPEED["TRACKING"])
        out.distance = max(SCENT_LAG_PX["TRACKING"], out.distance + rate * dt)
        out.best_distance = min(out.best_distance, out.distance)
        if out.distance > GIVE_UP_PX:
            out.beyond += dt
        else:
            out.beyond = 0.0
        if out.beyond >= BREAK_SECONDS:
            out.state = "FADING"
            out.elapsed = 0.0
            events.append("give_up:outrun")
        elif out.elapsed >= PATIENCE_SECONDS and out.distance >= out.best_distance:
            out.state = "FADING"
            out.elapsed = 0.0
            events.append("give_up:patience")
        elif out.distance <= CLOSE_PX and out.scent >= 0.5:
            if (moment.health_fraction >= LOW_HEALTH_FRACTION
                    and corner_check(moment)):          # G7 and G4, again
                out.state = "CLOSING"
                out.elapsed = 0.0
                events.append("close")
            else:
                events.append("held:guarantee")

    elif state == "CLOSING":
        # G7 AGAIN, AND THIS IS THE PLACE IT WAS MISSING.
        #
        # `spawn_check` refuses to spawn on a hurt player and the TRACKING
        # branch refuses to promote one, which between them made the guarantee
        # look complete. It was not: nothing demoted a hunt that was ALREADY
        # closing when the bar dropped, and that is the only ordering a player
        # actually meets it in — you get hurt while something is closing on you,
        # not before. The promise in `escape_guarantees` is written in the
        # present tense — "below thirty percent it will not close, it holds at
        # TRACKING and you walk out" — so it has to be a condition that is
        # rechecked, not a gate that was passed once.
        #
        # Demoting rather than ending the hunt is deliberate. TRACKING is 52
        # px/s against your 112: the creature is still there, still visible,
        # still on the map, and you are still gaining forty-two pixels a second
        # more than you were. It backs off; it does not vanish and let you
        # forget it. Heal above the line and it may commit again.
        if moment.health_fraction < LOW_HEALTH_FRACTION:
            out.state = "TRACKING"
            out.elapsed = 0.0
            events.append("held:guarantee")
            return out, tuple(events)
        # Same shape, faster number, and the number is still smaller than yours.
        # A moving player gains (112 - 74) = 38 px/s even here, which is the
        # state the escape simulation is run in precisely because it is the
        # worst one the machine has.
        rate = ((PLAYER_WALK_SPEED - STATE_SPEED["CLOSING"]) if moment.moving
                else -STATE_SPEED["CLOSING"])
        out.distance = max(0.0, out.distance + rate * dt)
        out.best_distance = min(out.best_distance, out.distance)
        if out.distance <= CONTACT_PX:
            out.state = "ENGAGED"
            out.elapsed = 0.0
            events.append("contact")
        elif out.distance > NOTICE_PX:
            out.state = "TRACKING"
            out.elapsed = 0.0
            events.append("lost_sight")

    elif state == "FADING":
        out.distance += STATE_SPEED["FADING"] * dt
        if out.elapsed >= FADE_SECONDS:
            out.state = "SPENT"
            out.elapsed = 0.0
            out.scent = 0.0
            out.cooldown = REGION_COOLDOWN_S
            events.append("gone")

    elif state == "SPENT":
        if out.cooldown <= 0:
            out.state = "DORMANT"
            out.elapsed = 0.0
            out.pressure = 0.0

    return out, tuple(events)


def telegraph(hunt: Hunt) -> dict:
    """Everything the client should be showing right now.

    One function, one dict, so that a state with no telegraph is impossible to
    ship — `self_check` asserts that every state a player can witness has a row
    in `TELEGRAPH`.
    """
    row = TELEGRAPH.get(hunt.state)
    if row is None:
        return {"state": hunt.state, "audio": "", "vignette": 0.0,
                "map": "none", "line": "", "seconds": None}
    apex = APEX_BY_ID.get(hunt.apex)
    name = apex.name if apex else "Something"
    region = (world.REGION_BY_ID.get(hunt.region, {}) or {}).get("name",
                                                                 hunt.region)
    seconds = None
    if row["countdown"]:
        gap = max(0.0, hunt.distance - CONTACT_PX)
        seconds = round(gap / max(1.0, STATE_SPEED["CLOSING"]), 1)
    return {
        "state": hunt.state,
        "audio": row["audio"],
        "vignette": row["vignette"],
        "colour": apex.colour if apex else "#9b96b8",
        "map": row["map"],
        "line": row["line"].format(name=name, region=region,
                                   seconds=(seconds if seconds is not None
                                            else "")),
        "seconds": seconds,
        "seconds_of_warning": row["seconds_of_warning"],
        "distance_tiles": round(hunt.distance / TILE, 1),
    }


# ---------------------------------------------------------------------------
# E. The bounty
# ---------------------------------------------------------------------------
#
# "Rewards should be adequate for their difficulty", and separately: an apex
# killed while underprepared should pay noticeably better, because that is the
# braver thing to have done. Both are true here and the second one needed a
# guard.
#
# THE STRIP-FARM PROBLEM, AND THE FIX
#
# If the bounty reads readiness at the moment of the kill, the optimal play is
# to take off your armour on the last cast. If it reads readiness at the moment
# of the spawn, the optimal play is to walk around naked until it stirs and then
# gear up. Both of those are a player being paid to do something boring, which
# is the definition of a bad incentive.
#
# So the bounty reads the PEAK readiness observed across the whole hunt —
# sampled at spawn, at contact, and once per cast — and pays on that. Stripping
# cannot lower a maximum. The only way to be paid the underprepared rate is to
# have genuinely been underprepared for the entire fight, which is exactly the
# bravery the rule was written to reward. The caller keeps one integer,
# `readiness_peak`, and hands it to `bounty`.
#
# WHAT IT PAYS, AND WHY EACH ONE
#
#   METAL      the area's own metal, in quantity. forge.METAL_BUNDLE gives 3 for
#              a boss; an apex gives 3 at full readiness and 9 at zero, which is
#              two to three forge steps in one fight and is the most direct
#              possible answer to "you were underprepared": the thing it drops
#              is the thing that would have prepared you.
#   POTION     one band above what the region normally offers, because the
#              pouch is the component the score weights lightest and the fight
#              is where the player finds out why that was wrong.
#   GOLD       scales with depth and with how badly outmatched you were.
#   TROPHY     a rare, apex-only item. 12% prepared, 40% unprepared, and
#              GUARANTEED on your first kill of each apex, because a creature
#              you beat once should leave you something you can hold.
#
#   NOT XP-SHAPED, AND NO MASTERY AT ALL. Mastery was already paid, one cast at
#   a time, by `incantation`. An apex that also granted skill would be paying
#   twice for the same typing and would make farming it better than learning.

METAL_BOUNTY_MIN = 3      # readiness 100
METAL_BOUNTY_MAX = 9      # readiness 0
GOLD_BASE = 80            # region 0
GOLD_PER_DEPTH = 45       # ...and per region after it
GOLD_UNDERPREP = 0.90     # up to +90% for having been outmatched
TROPHY_CHANCE_READY = 0.12
TROPHY_CHANCE_UNREADY = 0.40
TWO_POTIONS_BELOW = 50    # readiness under this pays a second draught

# What band a region normally hands out, and therefore what an apex hands out
# one better. Bands are potions.STRENGTH_BAND keys.
_BAND_LADDER = ("minor", "small", "medium", "hefty")
_REGION_BAND_BY_DEPTH = ((4, "minor"), (9, "small"), (14, "medium"))


def _region_band(region_id: str) -> str:
    depth = _region_index(region_id)
    for limit, band in _REGION_BAND_BY_DEPTH:
        if depth < limit:
            return band
    return "hefty"


def _band_up(band: str) -> str:
    i = _BAND_LADDER.index(band) if band in _BAND_LADDER else 0
    return _BAND_LADDER[min(i + 1, len(_BAND_LADDER) - 1)]


def _underprep(readiness_peak: int) -> float:
    return max(0.0, min(1.0, (100 - int(readiness_peak)) / 100.0))


def _metal_units(readiness_peak: int) -> int:
    spread = METAL_BOUNTY_MAX - METAL_BOUNTY_MIN
    return METAL_BOUNTY_MIN + int(round(spread * _underprep(readiness_peak)))


def _trophy_chance(readiness_peak: int) -> float:
    spread = TROPHY_CHANCE_UNREADY - TROPHY_CHANCE_READY
    return TROPHY_CHANCE_READY + spread * _underprep(readiness_peak)


@dataclass
class Bounty:
    apex: str
    region: str
    readiness_peak: int
    metal: str
    metal_units: int
    potion_band: str
    potion_doses: int
    gold: int
    trophy: str
    trophy_chance: float
    trophy_guaranteed: bool
    # Always zero. Named `mastery_granted` rather than `mastery` on purpose:
    # `_reads_no_progression` greps this module for `.mastery`, and a field that
    # collided with the pattern would have turned a real proof into a warning
    # somebody eventually silenced. The declaration stays; the name gets out of
    # the check's way.
    mastery_granted: int
    line: str

    def to_dict(self) -> dict:
        d = dict(vars(self))
        d["trophy_chance"] = round(self.trophy_chance, 3)
        return d


def bounty(region_id: str, readiness_peak: int, *,
           first_kill: bool = False) -> Bounty | None:
    """What an apex pays. Pure; rolls nothing.

    `trophy_chance` is returned rather than rolled so the caller can use its own
    RNG, its own luck stat and its own seed — exactly the way `forge.roll_metal`
    and `items.roll_drop` already take an `rng`. Nothing in this file draws a
    random number.
    """
    apex = apex_for(region_id)
    if apex is None:
        return None
    peak = max(0, min(100, int(readiness_peak)))
    under = _underprep(peak)
    depth = apex.depth

    units = _metal_units(peak)
    metal = apex.metal
    gold = int(round((GOLD_BASE + GOLD_PER_DEPTH * depth) * (1 + GOLD_UNDERPREP * under)))
    if not metal:
        # The village has no metal (forge.NO_METAL_REGIONS). Pay the difference
        # in gold rather than dropping a reward on the floor.
        gold += units * 25
        units = 0

    doses = 2 if peak < TWO_POTIONS_BELOW else 1
    band = _band_up(_region_band(region_id))

    if under >= 0.5:
        line = (f"{apex.name} falls to somebody who had no business fighting "
                f"it. The pile it leaves is embarrassingly generous.")
    elif under >= 0.25:
        line = f"{apex.name} falls. You earned most of this."
    else:
        line = (f"{apex.name} falls to somebody who came prepared. The reward "
                f"is smaller and you already know why.")

    return Bounty(
        apex=apex.id, region=region_id, readiness_peak=peak,
        metal=metal, metal_units=units,
        potion_band=band, potion_doses=doses,
        gold=gold, trophy=apex.trophy,
        trophy_chance=(1.0 if first_kill else _trophy_chance(peak)),
        trophy_guaranteed=bool(first_kill),
        mastery_granted=0, line=line,
    )


# -- the trophies -----------------------------------------------------------
#
# One per apex, and this module does not own `items.py`, so these are a MANIFEST
# rather than an implementation: id, slot, rarity, element and an effects bag
# built only out of keys that already exist in `items.EFFECT_LABELS` or in the
# three that `elements.armour_from_effects` documents as NEW. Whoever wires the
# drop adds these rows to items.py verbatim; nothing here has to change.
#
# They are deliberately SIDEWAYS rather than upward — a trophy is the best in
# the game at exactly one thing and mediocre at everything else, so wearing one
# is a decision about which area you are about to walk into rather than a
# straight upgrade you never take off again.

TROPHIES = {
    "surveyors_rod":    {"slot": "trinket", "rarity": "RARE", "element": "",
                         "effects": {"mana_max": 4, "hint_discount": 0.10},
                         "name": "The Surveyor's Rod",
                         "flavour": "Four hinges. It measures what is still there."},
    "hooked_tine":      {"slot": "trinket", "rarity": "RARE", "element": "",
                         "effects": {"stamina_max": 5},
                         "name": "Hooked Tine",
                         "flavour": "Off the drum. It is still turning slightly."},
    "ungrounded_key":   {"slot": "ring1", "rarity": "EPIC", "element": "LIGHTNING",
                         "effects": {"resist_lightning": 0.28, "mana_max": 3},
                         "name": "The Ungrounded Key",
                         "flavour": "It opens nothing. It was never for a door."},
    "rearranged_quill": {"slot": "trinket", "rarity": "EPIC", "element": "POISON",
                         "effects": {"resist_poison": 0.28, "stamina_max": 4},
                         "name": "Rearranged Quill",
                         "flavour": "The letters on it are not the letters it had."},
    "index_zero_plate": {"slot": "offhand", "rarity": "EPIC", "element": "BRUTE",
                         "effects": {"armour_points": 5, "armour_cap": 0.50},
                         "name": "The Index-Zero Plate",
                         "flavour": "Cut deep, and cut first."},
    "unclosed_corner":  {"slot": "trinket", "rarity": "EPIC", "element": "POISON",
                         "effects": {"resist_poison": 0.24, "resist_cold": 0.18},
                         "name": "An Unclosed Corner",
                         "flavour": "One of four. The other three are still out there."},
    "frozen_wick":      {"slot": "head", "rarity": "EPIC", "element": "COLD",
                         "effects": {"resist_cold": 0.30, "stamina_max": 4},
                         "name": "The Frozen Wick",
                         "flavour": "Lit. Not burning. It has not decided to stop."},
    "topmost_plate":    {"slot": "chest", "rarity": "EPIC", "element": "FIRE",
                         "effects": {"resist_fire": 0.30, "armour_points": 3},
                         "name": "The Topmost Plate",
                         "flavour": "Unloaded from the top, which is the only way."},
    "seam_rivet":       {"slot": "ring2", "rarity": "EPIC", "element": "BRUTE",
                         "effects": {"resist_brute": 0.28, "armour_points": 2},
                         "name": "The Seam Rivet",
                         "flavour": "It has been four directions and holds none."},
    "unwound_frame":    {"slot": "trinket", "rarity": "LEGENDARY", "element": "VOID",
                         "effects": {"resist_void": 0.30, "mana_max": 5},
                         "name": "The Unwound Frame",
                         "flavour": "The innermost one. It never got to return."},
    "left_fork_claw":   {"slot": "ring1", "rarity": "EPIC", "element": "",
                         "effects": {"crit_bonus": 0.12, "stamina_max": 4},
                         "name": "The Left-Fork Claw",
                         "flavour": "It committed a long time ago."},
    "lit_tine":         {"slot": "head", "rarity": "LEGENDARY", "element": "LIGHTNING",
                         "effects": {"resist_lightning": 0.30, "loot_luck": 0.10},
                         "name": "The Lit Tine",
                         "flavour": "A route, snapped off. It still knows the way."},
    "prised_tile":      {"slot": "offhand", "rarity": "LEGENDARY", "element": "",
                         "effects": {"armour_points": 6, "mana_max": 4},
                         "name": "A Prised Tile",
                         "flavour": "Still lit. It should not be, off the floor."},
    "unsalvaged_plate": {"slot": "chest", "rarity": "LEGENDARY", "element": "FIRE",
                         "effects": {"resist_fire": 0.30, "armour_points": 4},
                         "name": "Unsalvaged Plate",
                         "flavour": "One hairline. The hairline is the useful part."},
    "eighth_bar":       {"slot": "offhand", "rarity": "LEGENDARY", "element": "COLD",
                         "effects": {"resist_cold": 0.28, "armour_points": 4},
                         "name": "The Eighth Bar",
                         "flavour": "The eighth is a problem. The ninth is somebody "
                                    "else's."},
    "hour_through_glass": {"slot": "trinket", "rarity": "LEGENDARY", "element": "",
                          "effects": {"rank_grace": 0.15, "stamina_max": 5},
                          "name": "The Hour Through Glass",
                          "flavour": "Fused sand. You can read the time through it."},
    "struck_label":     {"slot": "chest", "rarity": "MYTHIC", "element": "VOID",
                         "effects": {"resist_void": 0.30, "resist_cold": 0.20,
                                     "armour_points": 5, "stamina_max": 5},
                         "name": "The Struck Label",
                         "flavour": "It does not do anything at all. That is the tell."},
}


def trophy_for(apex_id: str) -> dict:
    apex = APEX_BY_ID.get(apex_id)
    if apex is None:
        return {}
    row = dict(TROPHIES.get(apex.trophy, {}))
    row["id"] = apex.trophy
    row["apex"] = apex.id
    row["region"] = apex.region
    return row


# ---------------------------------------------------------------------------
# The client contract
# ---------------------------------------------------------------------------

def client_payload() -> dict:
    """Everything web/js/overworld.js needs, once, at load.

    Deliberately static. Per-frame state is the `Hunt` dict; this is the table
    the client draws it against, and it is small enough to inline in a save.
    """
    return {
        "apexes": [a.to_dict() for a in APEXES],
        "states": list(HUNT_STATES),
        "speed": dict(STATE_SPEED),
        "player_walk_speed": PLAYER_WALK_SPEED,
        "tile": TILE,
        "telegraph": {k: dict(v) for k, v in TELEGRAPH.items()},
        "distances": {
            "spawn_min": SPAWN_MIN_PX, "spawn_max": SPAWN_MAX_PX,
            "notice": NOTICE_PX, "close": CLOSE_PX, "contact": CONTACT_PX,
            "give_up": GIVE_UP_PX, "sanctuary": SANCTUARY_PX,
            "exit_safe": EXIT_SAFE_PX,
        },
        "timings": {
            "stir": STIR_SECONDS, "fade": FADE_SECONDS,
            "break": BREAK_SECONDS, "patience": PATIENCE_SECONDS,
            "dwell": MIN_REGION_DWELL_S, "pressure": SPAWN_PRESSURE_S,
            "region_cooldown": REGION_COOLDOWN_S,
            "global_cooldown": GLOBAL_COOLDOWN_S,
            "scent_halflife": SCENT_HALFLIFE_S,
        },
        # The ramp, so the client can say "44 casts because this is chapter XI"
        # without a second copy of the table in JavaScript. Static for the life
        # of the process, like everything else in this payload.
        "ramp": ramp_table(),
        "chapter_for_region": dict(CHAPTER_FOR_REGION),
        "scent_lag": dict(SCENT_LAG_PX),
        "scent_mode": dict(SCENT_MODE),
        "guarantees": escape_guarantees(),
    }


# ---------------------------------------------------------------------------
# Self check
# ---------------------------------------------------------------------------

_FORBIDDEN_SIGNALS = ("xp", "level", "mastery")


def _reads_no_progression() -> dict:
    """Proof, not assertion, that readiness is not a level check.

    Reads this module's own source and looks for any attribute access or
    subscript naming a progression signal. The docstrings talk about xp and
    level constantly — that is the whole argument of the file — so the check
    looks at CODE lines with the comment and string content stripped, which is
    the difference between "we say we do not read xp" and "we do not read xp".
    """
    import re
    try:
        with open(__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
    except OSError:
        return {"checked": False, "hits": []}

    # Strip docstrings, then comments, then any remaining string literal.
    stripped = re.sub(r'"""(?:.|\n)*?"""', '""', source)
    stripped = re.sub(r"#[^\n]*", "", stripped)
    stripped = re.sub(r'"[^"\n]*"', '""', stripped)
    stripped = re.sub(r"'[^'\n]*'", "''", stripped)

    hits = []
    for signal in _FORBIDDEN_SIGNALS:
        for pattern in (rf"\.{signal}\b", rf"\[\s*{signal}\s*\]",
                        rf"\bget\(\s*{signal}\b"):
            if re.search(pattern, stripped):
                hits.append(signal)
                break
    return {"checked": True, "hits": sorted(set(hits))}


def _prose_matches_the_data() -> dict:
    """Every element an apex's prose NAMES must be one the wheel justifies.

    Added because two apexes shipped a draft whose `lesson` named the wrong
    second element — the Lattice Stag's prose said brute where `graph_wastes` is
    poison, and the Slagmother's said brute where `debugging_dungeon` is void.
    Nothing caught it, because `Apex.elements` is DERIVED and the derivation was
    correct: only the English was wrong, and English is what the player reads.

    The rule: an element named in an apex's written fields must be in its own
    chain, or a counter to something in its chain, or the best reading available
    against it. Anything else is prose describing a monster that does not exist.

    WHAT THIS CATCHES AND WHAT IT DOES NOT, measured by reintroducing both
    original defects and watching which one turns it red:

        CAUGHT      the Slagmother saying "brute" when its chain is FIRE/VOID.
                    Brute counters neither, so the word has no business there.
        NOT CAUGHT  the Lattice Stag saying "brute" when its chain is
                    LIGHTNING/POISON. Brute is the COUNTER to poison, so the
                    word is legitimate here in some sentence — just not in the
                    sentence that used it, which claimed the creature WAS brute.

    Distinguishing "the monster is X" from "X beats the monster" needs a parser,
    and a parser in a self-check is a second thing to get wrong. So this is a
    vocabulary check, not a grammar check, and the honest claim is the narrow
    one: it catches an element that has no relationship to the apex at all.
    """
    import re
    bad = []
    for apex in APEXES:
        text = " ".join((apex.lesson, apex.presence, apex.tell)).upper()
        chain = set(apex.elements)
        allowed = set(chain)
        for element in chain:
            counter = elements.OPPOSED.get(element)
            if counter:
                allowed.add(counter)
        allowed.add(best_available(apex)[0])
        allowed.add(elements.NEUTRAL)
        for element in elements.ELEMENT_IDS:
            # Match the ELEMENT ID, not `Element.name`. An earlier version of
            # this check looked for the display name "BRUTE FORCE" while every
            # line of prose in the file says "brute", so the one element the
            # check was written to catch was the one element it could not see.
            # A mutation test — reintroducing the original defect and watching
            # this stay green — is what found that.
            if re.search(rf"\b{element}\b", text) and element not in allowed:
                bad.append(f"{apex.id}: prose names {element}, which is not in "
                           f"{sorted(chain)} nor a counter to it")
    return {"checked": True, "mismatches": bad}


def _damage_unit_drift() -> dict:
    """Is CAST_DAMAGE_REFERENCE still anchored to the live calibration?"""
    try:
        from . import incantation
    except Exception:
        return {"checked": False}
    live = float(getattr(incantation, "DAMAGE_UNIT", _DAMAGE_UNIT_EXPECTED))
    return {"checked": True, "damage_unit": live,
            "expected": _DAMAGE_UNIT_EXPECTED,
            "drifted": abs(live - _DAMAGE_UNIT_EXPECTED) > 1e-9,
            "implied_weight": round(CAST_DAMAGE_REFERENCE / live, 3)}


def _pet_tier_drift() -> dict:
    """Is the copied pets.TIERS depth column still the real one?"""
    try:
        from . import pets
    except Exception:
        return {"checked": False}
    live = {t.key: t.depth for t in pets.TIERS}
    return {"checked": True, "drifted": live != _PET_TIER_DEPTH,
            "live": live, "copied": dict(_PET_TIER_DEPTH)}


def _escape_simulation() -> dict:
    """G1 and G3 measured rather than asserted.

    A player who holds a direction, from contact range, in the worst state the
    machine has. If this ever reports anything but a clean break, a speed has
    been raised and the guarantee is gone.
    """
    hunt = new_hunt("null_kings_castle")
    hunt.state = "CLOSING"
    hunt.distance = float(CONTACT_PX)
    hunt.best_distance = hunt.distance
    hunt.scent = 1.0
    w = Moment(moving=True, health_fraction=1.0, free_tiles=999, clears=99,
              seed=7)
    dt = 1.0 / 60.0
    seconds = 0.0
    escaped_at = None
    for _ in range(60 * 300):
        hunt, _events = hunt_step(hunt, w, dt)
        seconds += dt
        if escaped_at is None and hunt.distance >= GIVE_UP_PX:
            escaped_at = round(seconds, 2)
        if hunt.state in ("SPENT", "DORMANT"):
            break
    return {"escaped": hunt.state in ("SPENT", "DORMANT", "FADING"),
            "seconds_to_break_contact": escaped_at,
            "seconds_to_give_up": round(seconds, 2),
            "final_state": hunt.state,
            "final_distance_tiles": round(hunt.distance / TILE, 1)}


def _corner_override() -> dict:
    """G4 measured: a hunt in CLOSING, with the ground pulled out from under the
    player, must be FADING on the very next tick."""
    hunt = new_hunt("stack_queue_mines")
    hunt.state = "CLOSING"
    hunt.distance = float(CLOSE_PX)
    hunt.scent = 1.0
    boxed = Moment(moving=False, free_tiles=MIN_FREE_TILES - 1, clears=99, seed=3)
    after, events = hunt_step(hunt, boxed, 1.0 / 60.0)
    return {"state_after_one_tick": after.state,
            "events": list(events),
            "holds": after.state == "FADING"}


def _low_health_hold() -> dict:
    """G7 measured: a hurt player in TRACKING range is never closed on."""
    hunt = new_hunt("complexity_tower")
    hunt.state = "TRACKING"
    hunt.distance = float(CLOSE_PX) - 1.0
    hunt.best_distance = hunt.distance
    hunt.scent = 1.0
    hurt = Moment(moving=False, health_fraction=LOW_HEALTH_FRACTION - 0.05,
                 free_tiles=999, clears=99, seed=5)
    after, events = hunt_step(hunt, hurt, 1.0 / 60.0)
    return {"state_after_one_tick": after.state, "events": list(events),
            "holds": after.state != "CLOSING"}


def _fading_completes_under_a_held_guarantee() -> dict:
    """The defect F1 fixed, kept measured so it cannot come back.

    A hunt stopped by a guarantee must still finish leaving. The three
    conditions that can stop one are all held DOWN for ten minutes here —
    the player stays in the dungeon, stays boxed in, stays in town — which is
    the realistic case and the one the old code could not survive.
    """
    rows = {}
    holds = True
    for label, kw in (("dungeon", {"in_dungeon": True}),
                      ("no_room", {"free_tiles": MIN_FREE_TILES - 1}),
                      ("sanctuary", {"in_sanctuary": True})):
        hunt = new_hunt("stack_queue_mines")
        hunt.state = "CLOSING"
        hunt.distance = float(CLOSE_PX)
        hunt.scent = 1.0
        moment = Moment(moving=True, health_fraction=1.0, free_tiles=999,
                        clears=99, seed=1)
        for key, value in kw.items():
            setattr(moment, key, value)
        seconds = 0.0
        dt = 1.0 / 20.0
        while seconds < 600.0:
            hunt, _events = hunt_step(hunt, moment, dt)
            seconds += dt
            if hunt.state in ("SPENT", "DORMANT"):
                break
        done = hunt.state in ("SPENT", "DORMANT") and hunt.cooldown > 0
        holds = holds and done
        rows[label] = {"final_state": hunt.state,
                       "seconds": round(seconds, 1),
                       "cooldown": round(hunt.cooldown, 1),
                       "resolved": done}
    return {"holds": holds, "cases": rows,
            "says": "A hunt a guarantee stops still reaches SPENT and still "
                    "sets the region's cooldown. It is not pinned in FADING "
                    "for as long as the condition lasts."}


def _low_health_demotes_a_live_close() -> dict:
    """G7 in the ordering a player actually meets it in: hurt WHILE closing.

    The old `_low_health_hold` only ever tested the TRACKING -> CLOSING gate,
    which is the ordering nobody meets. Getting hurt first and then being
    noticed is rare; being noticed and then getting hurt is Tuesday.
    """
    hunt = new_hunt("complexity_tower")
    hunt.state = "CLOSING"
    hunt.distance = float(CLOSE_PX)
    hunt.best_distance = hunt.distance
    hunt.scent = 1.0
    hurt = Moment(moving=False, health_fraction=LOW_HEALTH_FRACTION - 0.25,
                  free_tiles=999, clears=99, seed=2)
    dt = 1.0 / 20.0
    seconds = 0.0
    reached_closing = False
    engaged = False
    closest = hunt.distance
    while seconds < 300.0:
        hunt, _events = hunt_step(hunt, hurt, dt)
        seconds += dt
        closest = min(closest, hunt.distance)
        if hunt.state == "CLOSING":
            reached_closing = True
        if hunt.state == "ENGAGED":
            engaged = True
            break
        if hunt.state in ("SPENT", "DORMANT"):
            break
    return {"holds": (not engaged and not reached_closing
                      and closest >= SCENT_LAG_PX["TRACKING"] - 1e-6),
            "final_state": hunt.state,
            "ever_closed_again": reached_closing,
            "ever_reached_you": engaged,
            "closest_tiles": round(closest / TILE, 1),
            "held_at_tiles": SCENT_LAG_PX["TRACKING"] / TILE,
            "seconds": round(seconds, 1),
            "says": "A player hurt below thirty percent while something is "
                    "closing is demoted to TRACKING on the next tick, held ten "
                    "tiles off by the trail's own lag, and never touched. It "
                    "stays visible; it stops committing."}


def _roaming_resolves_against_a_still_player() -> dict:
    """The state a player who is typing Python actually spends the game in.

    Standing still adds no scent, so a roaming apex cannot find a stationary
    player. It must therefore have both a floor (it does not walk onto somebody
    it has not found) and an ending (a circuit that turns up nothing goes
    home). Without the two, ROAMING was a state with no exit.
    """
    hunt = new_hunt("stack_queue_mines")
    hunt.state = "ROAMING"
    hunt.distance = float(SPAWN_MAX_PX)
    still = Moment(moving=False, health_fraction=1.0, free_tiles=999,
                   clears=99, seed=1)
    dt = 1.0 / 20.0
    seconds = 0.0
    closest = hunt.distance
    while seconds < 900.0:
        hunt, _events = hunt_step(hunt, still, dt)
        seconds += dt
        if hunt.state == "ROAMING":
            closest = min(closest, hunt.distance)
        if hunt.state in ("SPENT", "DORMANT", "ENGAGED"):
            break
    return {"holds": (hunt.state in ("SPENT", "DORMANT")
                      and closest >= ROAM_FLOOR_PX - 1e-6),
            "final_state": hunt.state,
            "seconds": round(seconds, 1),
            "closest_tiles": round(closest / TILE, 1),
            "floor_tiles": ROAM_FLOOR_PX / TILE,
            "says": "It never walks nearer than ten tiles to somebody it has "
                    "not found, and a circuit that finds nobody ends."}


def _full_lifecycle() -> dict:
    """Drive one region's hunt through EVERY state it has, and time each one.

    This exists because it was missing, and the thing it was missing caught a
    real defect: `hunt_step`'s STIRRING branch referenced the `world` MODULE
    where it meant the `Moment`, and every other simulation in this file starts
    a hunt mid-chase, so nothing ever executed that line. A proof that covers
    only the dramatic states is a proof that the mundane ones are where the
    defects live.

    Two passes, because the machine has two endings and a player sees both:

        pass 1  walk until it reaches you, then fight  -> ENGAGED, then flee
        pass 2  let it find you and then walk away     -> FADING, then SPENT

    `flee` deliberately skips FADING — a creature you ran from does not also get
    to give up on you — so pass two is the only way FADING is ever entered by a
    live hunt rather than by a guarantee override.
    """
    hunt = new_hunt("stack_queue_mines")
    walking = Moment(moving=True, health_fraction=1.0, free_tiles=999,
                     clears=MIN_REGION_CLEARS, seed=11)
    still = Moment(moving=False, health_fraction=1.0, free_tiles=999,
                   clears=MIN_REGION_CLEARS, seed=11)

    seen, order = [], []
    time_in: dict = {}
    dt = 1.0 / 30.0
    elapsed = 0.0
    contacted_at = None
    gave_up_at = None
    phase = 0                  # 0: get caught. 1: get away.

    for _tick in range(30 * 3600):          # an hour of simulated time
        if phase == 0:
            # Walk until it has you; stand still so contact actually happens.
            m = walking if hunt.state in ("DORMANT", "STIRRING",
                                          "ROAMING") else still
        else:
            # Keep walking. At 112 against 74 this can only end one way.
            m = walking

        hunt, _events = hunt_step(hunt, m, dt)
        elapsed += dt
        # Accumulate UNROUNDED. Rounding each step to one decimal turned a
        # 0.033s tick into 0.0 and every total into zero — a counter that
        # confidently reported nothing.
        time_in[hunt.state] = time_in.get(hunt.state, 0.0) + dt
        if not order or order[-1] != hunt.state:
            order.append(hunt.state)
        if hunt.state not in seen:
            seen.append(hunt.state)

        if phase == 0 and hunt.state == "ENGAGED":
            contacted_at = round(elapsed, 1)
            hunt = flee(hunt)               # G2, exercised rather than asserted
            for state in ("SPENT",):
                if state not in seen:
                    seen.append(state)
                if order[-1] != state:
                    order.append(state)
            phase = 1
            continue

        if phase == 1 and hunt.state == "FADING" and gave_up_at is None:
            gave_up_at = round(elapsed, 1)

        if phase == 1 and gave_up_at is not None and hunt.state == "DORMANT":
            break

    unreached = [s for s in HUNT_STATES if s not in seen]
    return {"states_reached": seen, "transitions": order,
            "states_never_reached": unreached,
            "seconds_in_each_state": {k: round(v, 1)
                                      for k, v in time_in.items()},
            "seconds_to_contact": contacted_at,
            "seconds_to_give_up": gave_up_at,
            "seconds_total": round(elapsed, 1),
            "covers_every_state": not unreached,
            "terminated": hunt.state == "DORMANT"}


def _docstring_ramp_rows_are_live() -> dict:
    """The three rows in the module docstring, checked against the functions.

    `_prose_matches_the_data` already makes the argument for this: English is
    what the player and the next maintainer read, so a table in a docstring is
    either verified or it is decoration that will be wrong within two tuning
    passes. This one is narrow on purpose — it checks the three rows it can
    parse and claims nothing about the rest of the prose.
    """
    import re
    text = __doc__ or ""
    wanted = {
        "I": (0, casts_at_ready(0), casts_at_unready(0), strike_at_unready(0)),
        "V": (CHAPTER_ANCHOR, CASTS_AT_READY, CASTS_AT_UNREADY,
              strike_at_unready(CHAPTER_ANCHOR)),
        "XI": (CHAPTER_COUNT - 1, casts_at_ready(CHAPTER_COUNT - 1),
               casts_at_unready(CHAPTER_COUNT - 1),
               strike_at_unready(CHAPTER_COUNT - 1)),
    }
    bad = []
    for numeral, (_index, ready, unready, strike) in wanted.items():
        pattern = (rf"chapter {numeral}\s+{ready} casts prepared\s+"
                   rf"{unready} unprepared\s+strike {strike:.2f}x")
        if not re.search(pattern, text):
            bad.append(f"chapter {numeral}: docstring does not say "
                       f"{ready}/{unready} at {strike:.2f}x")
    return {"checked": bool(text), "mismatches": bad}


def _ramp_holds() -> dict:
    """The four things the chapter ramp promises, checked rather than claimed.

    1. The legacy constants still describe the anchor rung, so a reader who
       trusts CASTS_AT_READY has not been lied to.
    2. Readiness halves the fight at EVERY chapter, not just at the anchor.
    3. The ramp is strictly increasing. A chapter that bought nothing would be
       a rung a player cannot feel, and a flat spot is where a ramp starts
       quietly becoming a constant again.
    4. Every region resolves to a chapter that exists.
    """
    ready = [casts_at_ready(c) for c in range(CHAPTER_COUNT)]
    unready = [casts_at_unready(c) for c in range(CHAPTER_COUNT)]
    strikes = [strike_at_unready(c) for c in range(CHAPTER_COUNT)]
    halves = all(u == r * 2 for r, u in zip(ready, unready))
    rising = all(b > a for a, b in zip(ready, ready[1:]))
    strike_rising = all(b >= a for a, b in zip(strikes, strikes[1:]))
    orphans = sorted(r["id"] for r in world.REGIONS
                     if r["id"] not in CHAPTER_FOR_REGION)
    return {
        "anchor_chapter": CHAPTER_ANCHOR,
        "anchor_matches_legacy_constants": (
            casts_at_ready(CHAPTER_ANCHOR) == CASTS_AT_READY
            and casts_at_unready(CHAPTER_ANCHOR) == CASTS_AT_UNREADY),
        "readiness_halves_at_every_chapter": halves,
        "ramp_is_strictly_rising": rising,
        "strike_ramp_never_falls": strike_rising,
        "strike_ends": [strikes[0], strikes[-1]],
        "strike_ends_are_the_named_constants": (
            strikes[0] == STRIKE_AT_UNREADY_FLOOR
            and strikes[-1] == STRIKE_AT_UNREADY),
        "casts_ready": ready,
        "casts_unready": unready,
        "regions_without_a_chapter": orphans,
        "holds": (casts_at_ready(CHAPTER_ANCHOR) == CASTS_AT_READY
                  and casts_at_unready(CHAPTER_ANCHOR) == CASTS_AT_UNREADY
                  and halves and rising and strike_rising and not orphans),
    }


def _pool_cap_is_never_reached() -> dict:
    """HP_CAP must be a guard against nonsense, not a lid on the design.

    A capped pool is a fight that ends before `target_casts` is reached, which
    puts the client's bar and the engine's tally on different arithmetic about
    the same creature. So the cap has to sit above the largest pool the ramp can
    legitimately produce, and the honest way to know that is to go and measure
    it rather than to reason about it: every region, every rung, every element a
    player can actually strike with, at the readiness that loadout really earns.
    """
    worst = {"pool": 0}
    for apex in APEXES:
        chapter = chapter_for_region(apex.region)
        low, high = casts_at_ready(chapter), casts_at_unready(chapter)
        # The pool is `casts x per_cast`, and those two pull in OPPOSITE
        # directions: the loadout that hits hardest is the loadout that scores
        # highest and therefore gets the shortest fight. The largest pool is
        # somewhere in the middle — a huge blade carried by somebody who did
        # none of the other four components — so the sweep has to include the
        # stripped shapes as well as the complete one or it will report a
        # maximum that is merely a local one.
        kits = (
            {"armour_points": 10, "bar_bonus": 12,
             "companion_tier": "LEGENDARY", "potions": {"hefty": 2}},
            {"armour_points": 0, "bar_bonus": 0,
             "companion_tier": "", "potions": {}},
            {"armour_points": 5, "bar_bonus": 6,
             "companion_tier": "BEGINNER", "potions": {"minor": 1}},
        )
        for rung in range(10):
          for kit in kits:
            for element in list(elements.ELEMENT_IDS) + [elements.NEUTRAL]:
                lo = Loadout(weapon_element=element, weapon_rung=rung,
                             armour_resist={}, **kit)
                score = readiness(apex.region, lo).score
                fraction = max(0.0, min(1.0, score / 100.0))
                casts = high + (low - high) * fraction
                per_cast, _kind = expected_cast_damage(apex, lo)
                pool = int(round(casts * per_cast))
                if pool > worst["pool"]:
                    worst = {"pool": pool, "apex": apex.id, "rung": rung,
                             "element": element, "readiness": score,
                             "casts": int(round(casts)),
                             "per_cast": round(per_cast, 2)}
    return {**worst, "cap": HP_CAP, "headroom": HP_CAP - worst["pool"],
            "holds": worst["pool"] < HP_CAP}


def _worked_examples() -> list:
    """Three real players against three real apexes, with real numbers.

    Chosen to be the three sentences the brief asked to be able to say:
    a newcomer, a player who did the area's work, and a player who did it and
    then read the wheel as well.
    """
    rows = []

    # 1. Straight into the Pass with the blade the Fields gave you.
    newcomer = Loadout(weapon_element=elements.NEUTRAL, weapon_rung=1,
                       armour_points=1, armour_resist={}, bar_bonus=0,
                       companion_tier="BEGINNER", potions={"minor": 1})
    # 2. Did the local work: current rung, warded against the cold, adept pet.
    local = Loadout(weapon_element=elements.NEUTRAL, weapon_rung=3,
                    armour_points=6, armour_resist={elements.COLD: 0.30},
                    bar_bonus=6, companion_tier="MASTER",
                    potions={"small": 3, "medium": 1})
    # 3. Did the work AND read the wheel: fire counters the Rimewarden.
    reader = Loadout(weapon_element=elements.FIRE, weapon_rung=4,
                     armour_points=8, armour_resist={elements.COLD: 0.45},
                     bar_bonus=8, companion_tier="MASTER",
                     potions={"medium": 2, "hefty": 1})
    # 4. The classic mistake: the local element, at a good rung.
    mirror = Loadout(weapon_element=elements.COLD, weapon_rung=4,
                     armour_points=8, armour_resist={elements.COLD: 0.45},
                     bar_bonus=8, companion_tier="MASTER",
                     potions={"medium": 2, "hefty": 1})

    for label, lo in (("new to the Pass", newcomer),
                      ("did the area's work", local),
                      ("did the work and read the wheel", reader),
                      ("good gear, wrong element", mirror)):
        r = readiness("twin_pointer_pass", lo)
        s = scale_for("twin_pointer_pass", lo, ready=r)
        b = bounty("twin_pointer_pass", r.score)
        rows.append({
            "player": label, "readiness": r.score, "band": r.band,
            "matchup": s.matchup,
            "casts": s.target_casts, "hp": s.hp,
            "per_cast": round(s.per_cast_damage, 1),
            "incoming": round(s.strike_multiplier, 2),
            "metal": f"{b.metal_units} x {b.metal}",
            "gold": b.gold,
            "trophy_chance": round(b.trophy_chance, 2),
            "first_advice": (r.advice[0] if r.advice else ""),
        })
    return rows


def self_check() -> dict:
    """Counts, proofs and the curve. Safe to call from a test or the CLI."""
    ids = [a.id for a in APEXES]
    regions = [a.region for a in APEXES]
    missing = [r["id"] for r in world.REGIONS if r["id"] not in APEX_BY_REGION]
    extra = [r for r in regions if r not in world.REGION_BY_ID]

    # Every apex's chain is the ground's chain, not a hand-typed one.
    chain_ok = all(a.elements == elements.affinities_for(a.region,
                                                         difficulty="BOSS",
                                                         is_boss=True)
                   for a in APEXES)

    # No exam sheet may fail to add up, and no component may be unknown.
    exam_sums = {a.id: sum(a.exam.values()) for a in APEXES}
    exam_ok = all(v == 100 for v in exam_sums.values())
    exam_keys_ok = all(set(a.exam) == set(EXAM_COMPONENTS) for a in APEXES)

    # Sprites. Fallbacks must resolve today; new keys must all be distinct.
    bad_fallbacks = sorted({a.sprite_fallback for a in APEXES
                            if a.sprite_fallback not in _BOSS_ARCHETYPES})
    fallback_counts: dict = {}
    for a in APEXES:
        fallback_counts[a.sprite_fallback] = \
            fallback_counts.get(a.sprite_fallback, 0) + 1
    repeats = sorted(k for k, v in fallback_counts.items() if v > 1)

    # Trophies: one each, all distinct, all present in the manifest.
    trophy_ids = [a.trophy for a in APEXES]
    missing_trophies = sorted({t for t in trophy_ids if t not in TROPHIES})

    by_element: dict = {}
    for a in APEXES:
        by_element.setdefault(a.element, []).append(a.id)

    guarantees = escape_guarantees()
    guarantee_ok = all(g["holds"] for g in guarantees.values())

    escape = _escape_simulation()
    lifecycle = _full_lifecycle()
    corner = _corner_override()
    low = _low_health_hold()
    low_mid = _low_health_demotes_a_live_close()
    fade = _fading_completes_under_a_held_guarantee()
    roam = _roaming_resolves_against_a_still_player()
    progression = _reads_no_progression()
    telegraph_missing = sorted(
        s for s in ("STIRRING", "ROAMING", "TRACKING", "CLOSING", "ENGAGED",
                    "FADING") if s not in TELEGRAPH)

    prose = _prose_matches_the_data()
    anchor = _damage_unit_drift()
    pet_copy = _pet_tier_drift()
    ramp = _ramp_holds()
    pool_cap = _pool_cap_is_never_reached()
    docstring_rows = _docstring_ramp_rows_are_live()

    ok = (len(APEXES) == len(world.REGIONS)
          and len(set(ids)) == len(ids)
          and len(set(regions)) == len(regions)
          and not missing and not extra
          and chain_ok and exam_ok and exam_keys_ok
          and not bad_fallbacks
          and len(set(a.sprite for a in APEXES)) == len(APEXES)
          and len(set(trophy_ids)) == len(trophy_ids)
          and not missing_trophies
          and not telegraph_missing
          and guarantee_ok
          and escape["escaped"] and corner["holds"] and low["holds"]
          and low_mid["holds"] and fade["holds"] and roam["holds"]
          and lifecycle["covers_every_state"] and lifecycle["terminated"]
          and progression["checked"] and not progression["hits"]
          and not prose["mismatches"]
          and APEX_MAX_SPEED < PLAYER_WALK_SPEED
          and CASTS_AT_READY < CASTS_AT_UNREADY
          and STRIKE_AT_READY < STRIKE_AT_UNREADY
          and ramp["holds"] and pool_cap["holds"]
          and not docstring_rows["mismatches"]
          and not (anchor.get("checked") and anchor.get("drifted"))
          and not (pet_copy.get("checked") and pet_copy.get("drifted")))

    return {
        # -- A: the roster
        "apexes": len(APEXES),
        "regions": len(world.REGIONS),
        "one_per_region": len(APEXES) == len(world.REGIONS) and not missing,
        "regions_without_an_apex": missing,
        "ids": ids,
        "by_element": {k: sorted(v) for k, v in sorted(by_element.items())},
        "elemental_apexes": sum(1 for a in APEXES
                                if a.element in elements.ELEMENTS),
        "neutral_apexes": sum(1 for a in APEXES
                              if a.element == elements.NEUTRAL),
        "element_derived_from_ground": chain_ok,
        "dual_or_more": sum(1 for a in APEXES if len(a.elements) > 1),
        "triple": [a.id for a in APEXES if len(a.elements) > 2],
        "brief_named_three": {
            "fire_in_the_volcano": APEX_BY_REGION["stack_queue_mines"].name,
            "ice_in_the_cold": APEX_BY_REGION["twin_pointer_pass"].name,
            "shadow_in_the_void": APEX_BY_REGION["null_kings_castle"].name,
        },

        # -- art seam
        "sprite_keys_new": [a.sprite for a in APEXES],
        "sprite_fallbacks_unresolved": bad_fallbacks,
        "sprite_fallbacks_repeated": repeats,
        "sprite_fallbacks_repeated_declared": sorted(SPRITE_FALLBACK_REPEATS),
        "repeats_are_declared": repeats == sorted(SPRITE_FALLBACK_REPEATS),

        # -- B: readiness
        "exam_components": list(EXAM_COMPONENTS),
        "exam_sheets_sum_to_100": exam_ok,
        "exam_sums": exam_sums,
        "prose_matches_the_data": prose,
        "element_credit_landmarks": dict(ELEMENT_CREDIT),
        "best_available": {a.id: list(best_available(a)) for a in APEXES},
        "elemental_exam": dict(ELEMENTAL_EXAM),
        "neutral_exam": dict(NEUTRAL_EXAM),
        "reads_no_progression_signal": progression,
        "damage_anchor": anchor,
        "pet_tier_copy": pet_copy,
        "curve": curve("twin_pointer_pass"),
        "worked_examples": _worked_examples(),

        # -- B2/B3: the chapter ramp
        "chapters": CHAPTER_COUNT,
        "chapter_anchor": CHAPTER_ANCHOR,
        "chapter_for_region": dict(CHAPTER_FOR_REGION),
        "ramp": ramp,
        "docstring_ramp_rows": docstring_rows,
        "ramp_table": ramp_table(),
        "pace": {a.region: pace_for(a.region) for a in APEXES},
        "playthrough_cost": playthrough_cost(),
        "pool_cap": pool_cap,

        # -- C: the hunt
        "states": list(HUNT_STATES),
        "speeds": dict(STATE_SPEED),
        "telegraph_states_missing": telegraph_missing,
        "telegraph_warning_before_it_exists_seconds": STIR_SECONDS,

        # -- D: the escape
        "guarantees_hold": guarantee_ok,
        "guarantees": {k: v["holds"] for k, v in guarantees.items()},
        "apex_max_speed": APEX_MAX_SPEED,
        "player_walk_speed": PLAYER_WALK_SPEED,
        "speed_margin": SPEED_MARGIN,
        "escape_simulation": escape,
        "full_lifecycle": lifecycle,
        "corner_override": corner,
        "low_health_hold": low,
        "low_health_demotes_a_live_close": low_mid,
        "fading_completes_under_a_held_guarantee": fade,
        "roaming_resolves_against_a_still_player": roam,

        # -- E: the bounty
        "bounty_at_0": bounty("twin_pointer_pass", 0).to_dict(),
        "bounty_at_100": bounty("twin_pointer_pass", 100).to_dict(),
        "bounty_village_has_no_metal":
            bounty("python_village", 0).to_dict(),
        "trophies": len(TROPHIES),
        "trophies_missing": missing_trophies,
        "grants_mastery": bounty("twin_pointer_pass", 50).mastery_granted,

        # -- F: the lesson
        "lessons": {a.region: lesson_for(a.region)["examines_hardest"]
                    for a in APEXES},

        "ok": ok,
    }


if __name__ == "__main__":       # pragma: no cover
    import json
    print(json.dumps(self_check(), indent=2, default=str))
