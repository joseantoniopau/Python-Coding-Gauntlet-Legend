"""Pet regalia: twenty-four objects, twelve companions, and the one line none of
them may cross.

WHAT THIS IS
------------
A companion's help arrives unasked, and `pets.py` decides two things about it:
HOW EARLY it arrives (`BondRank.threshold_scale`, which multiplies every trigger
threshold) and HOW OFTEN (`BondRank.interventions`, which caps how many times
one animal may speak in one encounter). Bond buys both of those, slowly, on
graded evidence.

Regalia buys the same two things and nothing else. A jade collar makes the
jaguar notice sooner. A mystic scarf gives the penguin a second thing to say in
the Pass. Neither of them teaches either animal to read a problem it could not
read yesterday.

THE LINE, AND WHY IT IS EXACTLY WHERE pets.py PUT IT
----------------------------------------------------
`pets.py` states it in one sentence and this module inherits it whole:

    "What bond never buys is DEPTH. A Storied tutorial pig is a tutorial pig.
     Letting bond climb the tier ladder would turn the choice of companion back
     into a grind, and the choice is the thing this module exists to create."

Regalia obeys that for the same reason and one more. Bond is earned by evidence
and cannot be rushed; an OBJECT is a thing a player can go and get. If an object
could raise a tier, then the answer to "this problem is above my companion" would
be "farm the collar", and the tier ladder — the whole reason choosing a companion
is a decision — would become a shopping list. So:

  * no regalia carries a tier, a depth, or a `hint_kind`;
  * no regalia changes `rank_ceiling`, `hint_weight`, `hint_kind`, `helps_through`
    or whether a companion refuses an encounter as above its depth;
  * `self_check` proves all of that by running every companion against every
    difficulty with and without every one of its objects and diffing the payload.

NOTHING IN THIS FILE HAS A PRICE
--------------------------------
There is a gold economy in this game now — a vendor, a broker, a smith who
charges for labour. None of it touches these twenty-four objects. Every one of
them is earned by evidence in the companion's own skill, and there is no
`fitting`, `price` or `cost` field for one to acquire; `_prove_no_effect_keys`
checks the dataclass for those names so a later pass cannot quietly add one.

That is not squeamishness about commerce. Gold is paid for correct Python, but it
is paid for correct Python that has ALREADY BEEN GRADED, which means a player can
accumulate it by repeating work they have already mastered. Help that could be
bought with gold would therefore be help bought with time, and help bought with
time is the exact failure this whole design is built to avoid. Metal for a blade
can be farmed; the blade changes the economics of a fight. An extra hint changes
what the player has to work out for themselves, and that has one price.

THERE IS A SECOND BODY OF TACK, AND IT IS NOT THIS ONE
------------------------------------------------------
`quests.REGALIA` already exists: SEVEN regional pieces, awarded by quest
turn-ins, priced on a shelf by `economy.py`, and applied to whichever companion
is in the field. It is a different object with the same name, and it arrived
from a different pass while this one was being written.

The two are not in conflict about what regalia MAY do — independently, both
landed on the same two levers, the same floor of 0.40 and the same ceiling of 4,
which is some evidence that the line is in the right place. They differ in what
regalia IS: quests.py's tack belongs to a REGION and to the player's quest log;
these objects belong to an ANIMAL and to the skill it teaches, which is what the
brief asked for when it asked for a jade collar for the jaguar.

Whoever integrates picks one, or keeps both. If both: fold quests.py's
contribution in through `schedule(also_scale=, also_interventions=)` rather than
applying it separately, because two systems that each clamp their own share do
not add up to a clamped total. See `_prove_bounds`, which measures the exact
overrun that bridge closes.

WHAT "RELATIVE TO THEIR AREA" RESOLVES TO
-----------------------------------------
The brief asks for regalia that buffs hints "relative to their area", which can
be read two ways: scaled by how hard the area is, or only strong in the area the
object came from. Resolved as the second, because the first is a difficulty
multiplier wearing a costume and this game already has one of those.

So every object has a HOME — the regions that share its companion's element, plus
the region it was found in — and it is worth full value there and less elsewhere.
The jade collar is jade out of the Stringwood and it is worth most under the
Stringwood canopy. See `at_home` and `SITE`.

THE TWO KINDS, AND WHY THEY ARE NOT SYMMETRIC
---------------------------------------------
    EARLY   multiplies the trigger thresholds. 0.75 at home, 0.90 away.
    OFTEN   one more intervention per encounter. +1 at home, +0 away.

OFTEN is worth nothing outside its area and EARLY is worth something everywhere,
and that asymmetry is deliberate rather than a rounding accident. An intervention
is an integer; half an intervention does not exist, and the only way to fake one
would be a dice roll — which `pets._fires` refuses in as many words, because "a
companion that helps on a dice roll is a slot machine". So the frequency piece is
the one that is genuinely about a place, and the earliness piece is the one that
travels. That is the choice the player is being offered: the collar you wear at
home, or the one you wear on the road.

MORE HELP IS NOT FREE HELP
--------------------------
Every intervention costs a hint. `pets.HINT_WEIGHT` is 1, it counts against
`hints_used`, and it clamps the earnable rank to the companion's
`HINT_KINDS[...]["rank_ceiling"]`. A player wearing the scarf gets a second
sentence from the penguin and pays a second hint for it. Regalia therefore buys
FREQUENCY at the ordinary price of frequency, which is why it does not need a
cost of its own on top.

INTEGRATION CONTRACT
--------------------
    regalia.REGALIA / regalia.BY_ID / regalia.for_pet(pet_id)
    regalia.new_state()                       the flat dict a save persists
    regalia.progress(regalia_id, evidence)    the deed, measured
    regalia.newly_found(evidence, already)    what the player has just earned
    regalia.grant(state, regalia_id)          record it
    regalia.wear(state, regalia_id)           one per companion
    regalia.worn_by(state, pet_id)            what that animal has on
    regalia.schedule(pet_id, bond, ...)       the two numbers, and the arithmetic
    regalia.intervention(...)                 the drop-in replacement for
                                              pets.party_intervention
    regalia.view(state, ...)                  everything the codex screen draws
    regalia.self_check()                      the proofs this file must pass

`WIRING` at the bottom is written for whoever hooks it up and assumes they have
not read the rest of the file.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import elements, items, pets, world

__all__ = [
    "Regalia", "REGALIA", "BY_ID", "BY_PET", "for_pet",
    "EARLY", "OFTEN", "KINDS",
    "EARLY_SCALE_HOME", "EARLY_SCALE_AWAY", "OFTEN_EXTRA_HOME",
    "OFTEN_EXTRA_AWAY", "SCALE_FLOOR", "INTERVENTION_CEILING", "WORN_LIMIT",
    "REGALIA_STATE_KEY", "new_state", "grant", "wear", "take_off", "worn_by",
    "is_found", "at_home", "home_regions",
    "schedule", "intervention", "progress", "newly_found", "view", "catalogue",
    "self_check", "WIRING",
]


# ==========================================================================
# SECTION 1 — WHAT AN OBJECT DOES
# ==========================================================================
#
# Two kinds, and there will not be a third. A third kind would be a third thing
# the player has to read on a screen whose entire purpose is to say "your animal
# speaks sooner" or "your animal speaks twice", and neither of those sentences
# needs a paragraph.

EARLY = "EARLY"
OFTEN = "OFTEN"

# -- the numbers, and why they are these numbers ---------------------------
#
# EARLY_SCALE_HOME 0.75   A trigger authored at 120 seconds fires at 90. That is
#                         half a minute of the blank screen given back, which is
#                         a real gift at the moment it matters and is not the
#                         difference between thinking and not thinking.
# EARLY_SCALE_AWAY 0.90   Twelve seconds off the same trigger. Noticeable if you
#                         are counting, which is the right size for a thing you
#                         are wearing in the wrong forest.
# OFTEN_EXTRA_HOME 1      One more sentence per encounter, and one more hint
#                         charged for it. Two would double a Wary animal's whole
#                         output from a single object, which is more than bond
#                         itself buys between its first two ranks.
# OFTEN_EXTRA_AWAY 0      See the module docstring. Half an intervention does not
#                         exist and a dice roll is not an answer.
EARLY_SCALE_HOME = 0.75
EARLY_SCALE_AWAY = 0.90
OFTEN_EXTRA_HOME = 1
OFTEN_EXTRA_AWAY = 0

# The floor under the combined scale. A Storied companion is already at 0.50, so
# a collar would put it at 0.375 and that 120-second trigger would fire at 45
# seconds — before a player has finished READING a MEDIUM problem. A companion
# that speaks before you have read the screen has read it for you, which is the
# one thing no amount of bond and no object is allowed to buy.
SCALE_FLOOR = 0.40

# And the ceiling on how many times one animal may speak. Storied is 3; one
# object makes it 4. A fifth would be a fifth hint charged against a rank that
# has already been clamped to the companion's hint kind three times over — noise
# with a cost attached.
INTERVENTION_CEILING = 4

# One object per companion. The same argument pets.ACTIVE_LIMIT makes: two means
# there is a piece for every kind of trouble and no decision in the choosing.
WORN_LIMIT = 1

KINDS: dict = {
    EARLY: {
        "label": "Early",
        "buys": "it notices sooner",
        "home": EARLY_SCALE_HOME,
        "away": EARLY_SCALE_AWAY,
        "blurb": "Every trigger it watches comes forward. It does not learn "
                 "anything new; it stops waiting so long to say the thing it "
                 "already knew.",
    },
    OFTEN: {
        "label": "Often",
        "buys": "it speaks again, at home",
        "home": OFTEN_EXTRA_HOME,
        "away": OFTEN_EXTRA_AWAY,
        "blurb": "One more intervention per encounter, in its own country, and "
                 "one more hint charged for it. Outside its country it is a nice "
                 "thing the animal is wearing.",
    },
}


# ==========================================================================
# SECTION 2 — HOW ONE IS EARNED
# ==========================================================================
#
# Every deed below is expressed in `pets.DISCOVERY_CHECKS`, evaluated by
# `pets._discovery_row`, and read off the same evidence snapshot the codex
# already assembles for finding a companion in the first place. This module does
# NOT get a second evidence vocabulary. One vocabulary means one place where the
# question "what counts as having done something" is answered, and a second one
# is how a game ends up with two definitions of an unaided clear.
#
# THE SPINE OF EVERY DEED IS THE COMPANION'S OWN SKILL. `Pet.skill` is the skill
# an animal teaches and the skill it bonds on; it is also the only skill its
# regalia can be earned in. A collar that could be earned anywhere would be a
# collar you bought with time, and time is what this economy refuses to pay for.
#
# THE COUNTS ARE BANDED BY THE COMPANION'S TIER, which is the other half of
# "relative to their area": a MASTER animal's objects should not be affordable on
# the afternoon you meet it, and a TUTORIAL animal's should be, because it has
# about an hour left to live.
#
# At roughly one unaided clear every three or four encounters in a skill you are
# actually working on, the bands below are: an evening, an evening and a bit,
# two or three sessions, a week, and a long week.

SPINE_COUNT = {
    #                EARLY  OFTEN
    "TUTORIAL":    (    6,    10),
    "BEGINNER":    (    8,    14),
    "ADEPT":       (   12,    20),
    "MASTER":      (   16,    28),
    "LEGENDARY":   (   20,    34),
    "HIDDEN":      (   20,    34),
}


@dataclass(frozen=True)
class Regalia:
    """One object, belonging to one animal and one place.

    Deliberately without an `effects` field. A regalia is not a trinket and must
    not compete with `items.CATALOGUE`: it grants nothing from
    `items.EFFECT_LABELS`, which means it can never accidentally grant one of
    `pets.DEPTH_GATED_EFFECTS` and become a tier climb with a bow on it.
    `self_check` proves the absence rather than trusting it.
    """
    id: str
    pet: str                  # pets.BY_ID key
    name: str
    kind: str                 # EARLY | OFTEN
    region: str               # where it is found. world.REGION_BY_ID key
    where: str                # the place, in prose
    how: str                  # the deed, in prose
    needs: tuple              # the same deed, as pets.DISCOVERY_CHECKS clauses
    blurb: str                # what the object is
    worn: str                 # what it looks like on the animal
    line: str                 # what the companion says the first time it is on
    icon: str                 # web/js art key. All of these are small objects.
    colour: str

    @property
    def element(self) -> str:
        """The companion's element, and therefore the object's country."""
        pet = pets.BY_ID.get(self.pet)
        return elements.pet_element(pet.species if pet else "", self.pet)

    def to_dict(self, *, found: bool = False, worn_now: bool = False,
                region_id: str = "") -> dict:
        spec = KINDS[self.kind]
        home = at_home(self.id, region_id) if region_id else None
        return {
            "id": self.id, "pet": self.pet, "name": self.name,
            "kind": self.kind, "kind_label": spec["label"],
            "buys": spec["buys"], "kind_blurb": spec["blurb"],
            "element": self.element,
            "art": elements.element_view(self.element),
            "region": self.region,
            "region_name": world.REGION_BY_ID.get(self.region, {}).get("name", ""),
            "home_regions": home_regions(self.id),
            "where": self.where, "how": self.how,
            "blurb": self.blurb, "worn": self.worn, "line": self.line,
            "icon": self.icon, "colour": self.colour,
            "found": bool(found), "worn_now": bool(worn_now),
            "at_home": home,
            "home_value": spec["home"], "away_value": spec["away"],
        }


def _R(id, pet, name, kind, region, where, how, blurb, worn, line, icon,
       colour, extra=()):
    """One object, with the part that is the same for all of them derived.

    The spine clause — N unaided clears in the companion's own skill — is built
    here rather than typed twenty-four times, so a band cannot be edited in one
    place and forgotten in another.

    `extra` is the clause that belongs to THIS object, and only the OFTEN pieces
    have one. That is the shape of the pair rather than an omission: EARLY is the
    cheaper half and asks for one thing, OFTEN is the stronger half and asks for
    a second thing that is about the PLACE — the region cleared, the ambushes
    survived, the barrow closed. Nothing has three conditions, because a deed
    with three conditions is a checklist and nobody reads a checklist twice.
    """
    spec = pets.BY_ID[pet]
    early, often = SPINE_COUNT[spec.tier]
    count = early if kind == EARLY else often
    needs = ({"kind": "skill_unaided", "skill": spec.skill, "count": count},)
    return Regalia(id=id, pet=pet, name=name, kind=kind, region=region,
                   where=where, how=how, needs=needs + tuple(extra),
                   blurb=blurb, worn=worn, line=line, icon=icon, colour=colour)


# ==========================================================================
# SECTION 3 — THE TWENTY-FOUR
# ==========================================================================
#
# Two per companion, and each one is an object that could not have belonged to
# any other animal or come from any other place. The rule the player set with
# "a jade collar for the jaguar, a mystic scarf for the penguin" is that the
# thing is specific, slightly absurd, and obviously from somewhere — so nothing
# here is a Ring of Hints +1.
#
# The player's two are in the roster under their own names and both are OFTEN
# pieces, because the player described the buff as "how many hints they can
# give" and that is the frequency side.

REGALIA: tuple = (

    # ---- STUB, the boar piglet under the porch ---------------------------
    # Both of these stop working when the barrow closes. That is not a bug and
    # it is not softened: the loss is the point of the arc, and an object that
    # kept paying out afterwards would be the game apologising for it. What is
    # left on the floor is `pets.KEEPSAKE`, and the ring is downstairs.
    _R("porch_nail", "stub", "The Porch Nail", EARLY,
       "python_village",
       "Under the porch of the house that has never finished repairing itself, "
       "in the dirt the piglet sleeps in.",
       "Clear six encounters in PYTHON with nothing cast and nothing hinted. It "
       "is watching, in the way a thing with one ear watches.",
       "A square-cut nail, bent once and never pulled. It came out of a join "
       "that was left open, which is the only kind of problem this animal has "
       "ever been able to see.",
       "Tied at the throat on a twist of wire, tapping when it walks.",
       "I know what an unfinished thing looks like. I sleep under one.",
       "nail", "#8a7f6a"),
    _R("doorbell_cord", "stub", "The Doorbell Cord", OFTEN,
       "python_village",
       "The knotted pull-cord off the village door, which nobody has answered "
       "in years.",
       "Clear ten encounters in PYTHON unaided, and clear the Fields of Syntax.",
       "A short length of knotted cord with the bell end missing. It rings "
       "nothing. The piglet pulls it anyway, twice, and then looks at you.",
       "Dragged, and stood on regularly.",
       "I can say two things now. They are both small words.",
       "cord", "#b08968",
       extra=({"kind": "region_cleared", "region": "fields_of_syntax"},)),

    # ---- IDIOM, the python under the floor -------------------------------
    _R("kept_skin", "python", "The Kept Skin", EARLY,
       "python_village",
       "Under the floor of the half-rebuilt house, folded where the joists "
       "cross.",
       "Clear eight encounters in PYTHON unaided. It will not part with this "
       "for anything less than fluency.",
       "A whole shed skin, uncracked from nose to tail, kept rather than left. "
       "Held against a line it shows you what the same snake was the week "
       "before, which is most of what this animal is for.",
       "Wound once around the throat, dull side out.",
       "I keep them. Not for sentiment. For comparison.",
       "skin", "#6f7a55"),
    _R("doorstep_dish", "python", "The Doorstep Dish", OFTEN,
       "python_village",
       "The chipped saucer on the step, which somebody in this village has been "
       "filling every night without admitting to it.",
       "Clear fourteen encounters in PYTHON unaided, and clear the Fields of "
       "Syntax.",
       "A saucer with one bite out of the rim. An animal that is fed on a "
       "schedule turns up on a schedule, and turns up twice if the night is "
       "going badly.",
       "Not worn. Carried, which is worse, and it will not be talked out of it.",
       "Somebody feeds me. I have decided that somebody is you.",
       "dish", "#c9a05a",
       extra=({"kind": "region_cleared", "region": "fields_of_syntax"},)),

    # ---- PLAIN, the llama on the plateau ---------------------------------
    _R("plateau_blinder", "llama", "The Plateau Blinder", EARLY,
       "hashmap_highlands",
       "Woven on the open plateau out of the grass that grows against the vault "
       "plates, where the glare is worst.",
       "Clear eight encounters in COMMUNICATION unaided. It has to hear you say "
       "eight things clearly before it will let you put anything on its head.",
       "A woven brow-band that cuts the white off the keyed plates. It is not "
       "magic and it is barely even clever: the llama can read the vault "
       "numbers sooner because it can see them.",
       "Across the brow, at an angle nobody has managed to correct.",
       "I could always read them. Now I can read them without squinting.",
       "band", "#c9a05a"),
    _R("keybrass_bell", "llama", "The Keybrass Bell", OFTEN,
       "hashmap_highlands",
       "Cast from a spent vault key by somebody on the plateau who had one key "
       "too many and no vault left.",
       "Clear fourteen encounters in COMMUNICATION unaided, and survive four "
       "memory ambushes.",
       "A two-note bell. One note for the thing it wants to say, and one for the "
       "fact that it is going to say it again in a minute.",
       "At the throat, and it is loud.",
       "Two notes. I will use both of them and you will not enjoy the second.",
       "bell", "#c9a05a",
       extra=({"kind": "retest_survived", "skill": "", "count": 4},)),

    # ---- PATCH, the axolotl in the quench trough -------------------------
    _R("trough_lens", "axolotl", "The Quench-Trough Lens", EARLY,
       "debugging_dungeon",
       "A disc of glass fused flat in the bottom of the Armorer's quench "
       "trough, which nobody has drained in a decade.",
       "Clear eight encounters in DEBUGGING unaided. It will hand this over "
       "wet, and it will not apologise.",
       "Glass with one hairline through it, the same hairline every bar of "
       "Faultsteel has. Held over plate it finds the crack before the crack "
       "finds daylight.",
       "Strapped over one eye. The other eye is doing nothing and never has.",
       "I can see it earlier. It is the same crack. It was always the same "
       "crack.",
       "lens", "#7e6f66"),
    _R("second_whistle", "axolotl", "The Armorer's Second Whistle", OFTEN,
       "debugging_dungeon",
       "The Armorer keeps two whistles on one cord. The second one is for work "
       "that has already been repaired once.",
       "Clear fourteen encounters in DEBUGGING unaided, and clear the Debugging "
       "Dungeon.",
       "A flat brass whistle with a lower note than the first. It means 'this "
       "again', and the axolotl has strong feelings about this again.",
       "On the cord with the first, which it did not get.",
       "The low one is for the second time. There is nearly always a second "
       "time.",
       "whistle", "#b07a45",
       extra=({"kind": "region_cleared", "region": "debugging_dungeon"},)),

    # ---- ROSETTE, the jaguar in the anagram groves -----------------------
    _R("three_path_cord", "jaguar", "The Three-Path Cord", EARLY,
       "stringwood_labyrinth",
       "Plaited in the anagram groves out of three fibres off three different "
       "paths, which turn out to be the same fibre.",
       "Clear twelve encounters in SPEED unaided. It will be watching from the "
       "treeline for all twelve of them.",
       "Three strands, one rope, and you cannot tell afterwards which strand "
       "was which. An animal that has been shown the same shape three times "
       "recognises the fourth one faster, and this is that, as an object.",
       "Around the left foreleg, where it will not catch on anything.",
       "Three roads. One clearing. I stopped being surprised by that a long "
       "time ago.",
       "cord", "#8fd07a"),
    _R("jade_collar", "jaguar", "The Jade Collar", OFTEN,
       "stringwood_labyrinth",
       "Cut from the one green stone in the Stringwood, in the clearing all "
       "three groves lead to.",
       "Clear twenty encounters in SPEED unaided, and clear the Stringwood "
       "Labyrinth.",
       "Jade the colour of the canopy at noon, cut in a single band with no "
       "clasp, which means somebody made it for a specific neck. Nobody in the "
       "Stringwood will say who.",
       "One band, worn loose, and it does not rattle. Nothing this animal "
       "carries is allowed to rattle.",
       "Somebody cut this to fit me. I have thought about that more than I "
       "intend to admit.",
       "collar", "#3f7a3a",
       extra=({"kind": "region_cleared", "region": "stringwood_labyrinth"},)),

    # ---- SICKLE, the velociraptor on the scree ---------------------------
    _R("spur_cap", "velociraptor", "The Scree Spur-Cap", EARLY,
       "array_caverns",
       "Keybrass, hammered thin over the killing claw by somebody who wanted to "
       "be able to hear it coming.",
       "Clear twelve encounters in TESTING unaided. It has been following you "
       "since the Hydra and it has not forgotten the duplicate you skipped.",
       "A brass cap on one claw. It taps the scree ahead and the loose stone "
       "answers differently from the sound stone, which is this animal's entire "
       "philosophy expressed in one noise.",
       "Over the second claw. It taps constantly and it knows it is doing it.",
       "I hear which one is loose now. I heard before. Now I hear sooner.",
       "cap", "#c9a05a"),
    _R("duplicate_tooth", "velociraptor", "The Duplicate Tooth", OFTEN,
       "array_caverns",
       "On the scree slope below the Hydra's hall, where two teeth came down "
       "that are the same tooth.",
       "Clear twenty encounters in TESTING unaided, and clear the Array "
       "Caverns.",
       "Two teeth, identical to the wear pattern, wired together at the root. "
       "Nobody has explained them. The raptor finds them very funny and brings "
       "them up twice.",
       "Strung at the throat where they knock together.",
       "There were two. There are always two. I will mention it again.",
       "tooth", "#f2dc6a",
       extra=({"kind": "region_cleared", "region": "array_caverns"},)),

    # ---- PIVOT, the penguin in the flooded gallery -----------------------
    _R("lamp_glass", "penguin", "The Gallery Lamp-Glass", EARLY,
       "stack_queue_mines",
       "Off a drowned mine lamp in the flooded third gallery, past where the "
       "ore carts stop.",
       "Clear twelve encounters in SORTING unaided. It will watch you do all "
       "twelve from the top of something.",
       "Cold-fogged glass with a clear disc in the middle where the flame was. "
       "Held down a shaft it shows you the bottom of the stack, which is the "
       "only part of a stack anybody ever forgets.",
       "Round the neck on a loop, and it fogs when the penguin talks.",
       "The bottom. It is always about the bottom. Look at the bottom.",
       "lens", "#7ec8ff"),
    _R("mystic_scarf", "penguin", "The Mystic Scarf", OFTEN,
       "stack_queue_mines",
       "Knitted from something that was growing in the flooded gallery, by "
       "somebody who was down there alone for a long time.",
       "Clear twenty encounters in SORTING unaided, and clear the Stack and "
       "Queue Mines.",
       "It is not mystic. It is a long grey scarf with an uneven end, and the "
       "penguin has decided that it is mystic, and has been correcting people "
       "about it since the day it found it. In the cold it is worth roughly one "
       "extra opinion per fight, which the penguin attributes to the mysticism.",
       "Wound twice and trailing, which on a penguin is most of the animal.",
       "It is mystic. I have explained this. It is mystic and it is mine.",
       "scarf", "#7ec8ff",
       extra=({"kind": "region_cleared", "region": "stack_queue_mines"},)),

    # ---- CHAMBER, the nautilus at the innermost spring -------------------
    _R("inner_shell", "nautilus", "The Inner Chamber", EARLY,
       "recursive_forest",
       "At the spring in the innermost clearing, which is a smaller copy of the "
       "clearing before it.",
       "Clear sixteen encounters in RECURSION unaided. It will not surface for "
       "fifteen.",
       "A shell out of a shell: one chamber, empty, correct in every particular "
       "and small enough to sit in the palm. It is the same shell. Everyone who "
       "has held it has had the same argument with themselves about that.",
       "Balanced in the first chamber of the big one, where it fits exactly.",
       "It is the same shell. Stop turning it over. It is the same shell.",
       "shell", "#6a4f8f"),
    _R("twice_ringing_pin", "nautilus", "The Twice-Ringing Pin", OFTEN,
       "recursive_forest",
       "Heartwood iron, drawn out at the spring. Struck once, it rings twice.",
       "Clear twenty-eight encounters in RECURSION unaided, and clear the "
       "Recursive Forest.",
       "A pin of grown iron, lighter than it has any right to be. One strike, "
       "two notes: the call and the same call one size smaller. The nautilus "
       "uses the second note for the part you always miss.",
       "Through the mantle, which looked alarming once and no longer does.",
       "One strike. Two notes. The second one is the one that is about you.",
       "pin", "#6f7a55",
       extra=({"kind": "region_cleared", "region": "recursive_forest"},)),

    # ---- WITNESS, the crow on the broken junction ------------------------
    _R("road_ring", "crow", "The Road-Number Ring", EARLY,
       "graph_wastes",
       "A leg-ring off a junction post in the Wastes, stamped with a road "
       "number that no longer leads anywhere.",
       "Clear sixteen encounters in TESTING unaided. It has been on the post "
       "the whole time, keeping count.",
       "A thin iron ring with a number struck into it. Two rings set near each "
       "other lean together, which is how the crow knows which road it is "
       "standing on before it has finished landing.",
       "On the left leg, over an older one it will not discuss.",
       "I knew the road. Now I know it on the way down.",
       "ring", "#6a6470"),
    _R("rooks_tally", "crow", "The Rook's Tally", OFTEN,
       "graph_wastes",
       "A strip of Wastes-iron on the junction, scratched once for every time "
       "somebody came back along a road they had already walked.",
       "Clear twenty-eight encounters in TESTING unaided, and survive eight "
       "memory ambushes.",
       "Forty-one scratches. Eleven of them are yours. The crow will read out "
       "two per fight and it does not consider this unkind.",
       "Carried in the beak, set down to speak, picked up again.",
       "Forty-one. I will do two of them now.",
       "tally", "#6a6470",
       extra=({"kind": "retest_survived", "skill": "", "count": 8},)),

    # ---- HALT, the tortoise on the fifth landing -------------------------
    _R("stair_rule", "tortoise", "The Stair-Rule", EARLY,
       "complexity_tower",
       "A tick-marked strip of Doubling Steel off the Tower's own measuring "
       "rail, on the fifth landing where the stair stops being climbable.",
       "Clear sixteen encounters in BIG_O unaided. The tortoise is in no rush "
       "about this and neither is the Tower.",
       "Evenly spaced marks with every fifth one longer, and the spacing "
       "doubles halfway along, which is the Tower making its joke in metal. "
       "Laid against a loop it prices the loop a floor earlier.",
       "Strapped along the shell's left ridge like a ruler on a desk.",
       "I could always price it. Now I price it before you have finished "
       "climbing.",
       "rule", "#8fa8c8"),
    _R("shell_gong", "tortoise", "The Landing Gong", OFTEN,
       "complexity_tower",
       "The small bronze gong off the fifth landing, which used to be struck "
       "once per floor by somebody who gave up.",
       "Clear twenty-eight encounters in BIG_O unaided, and clear four "
       "performance trials.",
       "A dished bronze plate bolted flat to the shell. It sounds once for the "
       "floor you are on and once for the floor this is going to cost you, and "
       "the tortoise has never once struck it in the wrong order.",
       "Bolted to the shell. It was not asked. It does not mind.",
       "One for here. One for where this ends. Listen to the second one.",
       "gong", "#b07a45",
       extra=({"kind": "perf_cleared", "count": 4},)),

    # ---- BARROW, the boar that came back ---------------------------------
    _R("lit_tile_chip", "barrow", "The Lit-Tile Chip", EARLY,
       "dp_ruins",
       "A chip of Tilegold off the fourth floor of the Hall of Lit Tiles, on a "
       "tile you lit yourself.",
       "Clear twenty encounters in RECALL unaided. The Ruins keep no record of "
       "who did the work, so you will have to.",
       "Cold in the dark and warm on ground you have walked before. The boar "
       "does not need it to remember. It needs it to be sure, which is a "
       "different and more useful thing.",
       "Set in the wire of the old half-ring, where a bead would go.",
       "It is warm. So we have been here. I thought so, and now I am sure.",
       "chip", "#e0b44a"),
    _R("closed_half_ring", "barrow", "The Closed Half-Ring", OFTEN,
       "dp_ruins",
       "The keepsake off the floor of the Half-Written Barrow, carried since, "
       "and put down on a lit tile.",
       "Clear thirty-four encounters in RECALL unaided, and have the barrow "
       "close on something of yours.",
       "The mark that closed the bracket, closed. It is the thing the piglet "
       "went in with and the thing that came back out without it, and the boar "
       "wears it the way an old soldier wears somebody else's number. Once "
       "more a fight, in the Ruins, it will tell you what you already solved. "
       "Once more is not a lot. It is what there is.",
       "Through the ear that is still there.",
       "I closed it. You do not have to say anything about that.",
       "ring", "#b08968",
       extra=({"kind": "starter_fallen"},)),

    # ---- MIMIC, the octopus in the reeds ---------------------------------
    _R("borrowed_eye", "mimic", "The Borrowed Eye", EARLY,
       "sliding_window_marsh",
       "In the reeds out past the frame, in a pile of things that belonged to "
       "other animals.",
       "Clear twenty encounters in DESIGN unaided. It is already watching and "
       "it is already pretending not to be.",
       "A glass eye, convincingly veined, off something that had two. The "
       "octopus does not need it and cannot use it. Wearing it makes it read "
       "the room a beat sooner, for reasons it declines to go into.",
       "Held in one arm, at roughly head height, pointed at whatever you are "
       "pointed at.",
       "It is not my eye. That has never once stopped anything from working.",
       "eye", "#8fd07a"),
    _R("borrowed_reed", "mimic", "Somebody's Reed Whistle", OFTEN,
       "sliding_window_marsh",
       "Carved by somebody in the marsh, left on a stone for one minute, and "
       "not there when they came back.",
       "Clear thirty-four encounters in DESIGN unaided, and clear four dungeon "
       "floors with no companion, no spell and no item.",
       "A reed whistle with somebody else's tooth-marks on it. Every note it "
       "plays is in another animal's voice, which is the only way this "
       "companion has ever said anything, and now it can do it twice.",
       "Held in the fourth arm. The other seven are doing other impressions.",
       "This is not my voice either. Neither was the first one.",
       "whistle", "#8fd07a",
       extra=({"kind": "solo_floor", "count": 4},)),
)

BY_ID: dict = {r.id: r for r in REGALIA}
REGALIA_IDS: tuple = tuple(BY_ID)

BY_PET: dict = {}
for _r in REGALIA:
    BY_PET.setdefault(_r.pet, []).append(_r)
del _r


def for_pet(pet_id: str) -> list:
    """Both objects that belong to one companion, EARLY first."""
    return sorted(BY_PET.get(pet_id, []), key=lambda r: (r.kind != EARLY, r.id))


# ==========================================================================
# SECTION 4 — COUNTRY: WHERE AN OBJECT IS WORTH WHAT IT SAYS
# ==========================================================================
#
# An object is at home in the regions that share its companion's element, plus
# the one it came out of. The element half is what makes it a rule rather than a
# list — `elements.pet_home` already answers "where does this animal belong" —
# and the found-region half is what stops the penguin's scarf being worthless in
# the Mines it was knitted in. PIVOT is a cold animal that was found in a fire
# region, which is the one place those two answers disagree, and both of them
# are right.

SITE: dict = {}
for _regalia in REGALIA:
    _home = set(elements.pet_home(
        pets.BY_ID[_regalia.pet].species, _regalia.pet))
    _home.add(_regalia.region)
    SITE[_regalia.id] = tuple(sorted(_home))
del _regalia, _home


def home_regions(regalia_id: str) -> list:
    """Every region this object is worth full value in."""
    return list(SITE.get(regalia_id, ()))


def at_home(regalia_id: str, region_id: str = "") -> bool:
    """Is the player standing in this object's country.

    An empty region reads as AWAY rather than as home. A caller that has not
    told us where it is should get the conservative answer: the alternative is
    that a missing field quietly hands out the stronger version of everything.
    """
    return bool(region_id) and region_id in SITE.get(regalia_id, ())


# ==========================================================================
# SECTION 5 — THE SCHEDULE: THE TWO NUMBERS, AND NOTHING ELSE
# ==========================================================================


def schedule(pet_id: str, bond: int = 0, *, region_id: str = "",
             regalia_id: str = "", mode: str = "adventure",
             sealed: bool = False, also_scale: float = 1.0,
             also_interventions: int = 0) -> dict:
    """The bond rank's two numbers, with the object's contribution folded in.

    This is the whole mechanical surface of this module. `threshold_scale`
    multiplies every `pets.Trigger.value`; `interventions` caps how many times
    the companion may speak. Both are read straight out of `pets.BOND_RANKS` and
    then moved by at most one object.

    `sealed` is the caller's `finalexam.sealed(enc, "PET")` verdict, passed in
    for exactly the reason `pets.available_in` takes it as an argument: there is
    one isolation path in this game and this module does not form a second
    opinion about it. Sealed, or in Interview Mode, an object contributes
    nothing — same as the companion it is on.

    `also_scale` and `also_interventions` ARE THE BRIDGE TO quests.REGALIA, and
    they exist because two systems that each clamp their own contribution do not
    add up to a clamped total. `quests.py` owns a second body of tack — regional
    rather than personal, quest-awarded rather than earned in a skill — with the
    same two levers, and by coincidence or by convergence the same floor (0.40)
    and the same cap (4). If both are live, fold theirs in HERE:

        gear = quests.regalia_effect(state["quests"])
        plan = regalia.schedule(pet_id, bond, region_id=...,
                                also_scale=gear["scale"],
                                also_interventions=gear["interventions"])

    and the floor and the ceiling then hold over the pair, which is the only
    version of them that is worth anything. Calling both systems separately and
    trusting two clamps would let a Storied companion in an unlabelled collar
    and a jade collar reach 0.3075 and five interventions, and `_prove_bounds`
    measures exactly that case to show the bridge closing it.
    """
    rank = pets.bond_rank(int(bond or 0))
    base_scale = rank.threshold_scale
    base_interventions = rank.interventions
    out = {
        "pet": pet_id,
        "bond": int(bond or 0),
        "rank": rank.key,
        "rank_label": rank.label,
        "base_threshold_scale": base_scale,
        "base_interventions": base_interventions,
        "threshold_scale": base_scale,
        "interventions": base_interventions,
        "regalia": "", "regalia_name": "", "kind": "",
        "at_home": False, "applied": False,
        "floored": False, "capped": False,
        "line": "",
    }
    from .config import MODE_INTERVIEW
    if sealed or mode == MODE_INTERVIEW:
        out["line"] = "Nothing it is wearing means anything in here."
        return out

    also_scale = max(0.0, float(also_scale or 1.0))
    also_interventions = max(0, int(also_interventions or 0))

    piece = BY_ID.get(regalia_id)
    if piece is None or piece.pet != pet_id:
        if also_scale != 1.0 or also_interventions:
            out.update(_clamp(out, base_scale * also_scale,
                              base_interventions + also_interventions))
            out["applied"] = True
            out["line"] = "Tack, and it is doing what tack does."
        return out

    home = at_home(piece.id, region_id)
    out.update({"regalia": piece.id, "regalia_name": piece.name,
                "kind": piece.kind, "at_home": home, "applied": True})

    if piece.kind == EARLY:
        scale = base_scale * (EARLY_SCALE_HOME if home else EARLY_SCALE_AWAY)
        extra = 0
    else:
        scale = base_scale
        extra = OFTEN_EXTRA_HOME if home else OFTEN_EXTRA_AWAY

    out.update(_clamp(out, scale * also_scale,
                      base_interventions + extra + also_interventions))
    out["line"] = _schedule_line(piece, out)
    return out


def _clamp(row: dict, scale: float, interventions: int) -> dict:
    """The one place either number is clamped. Both clamps live here so that
    however many sources contribute, there is exactly one floor and exactly one
    ceiling and they are applied to the TOTAL."""
    return {
        "floored": scale < SCALE_FLOOR,
        "threshold_scale": round(max(SCALE_FLOOR, scale), 3),
        "capped": interventions > INTERVENTION_CEILING,
        "interventions": min(INTERVENTION_CEILING, int(interventions)),
    }


def _schedule_line(piece: Regalia, row: dict) -> str:
    if piece.kind == EARLY:
        pct = int(round((1.0 - row["threshold_scale"] / row["base_threshold_scale"])
                        * 100)) if row["base_threshold_scale"] else 0
        where = "here" if row["at_home"] else "away from its own country"
        if not pct:
            return f"{piece.name} is already doing everything it can."
        return f"{piece.name}: it notices {pct} percent sooner {where}."
    if row["interventions"] > row["base_interventions"]:
        return (f"{piece.name}: one more thing to say, and one more hint "
                f"charged for it.")
    return (f"{piece.name} is a long way from home. It is a nice thing the "
            f"animal is wearing.")


# ==========================================================================
# SECTION 6 — THE INTERVENTION
# ==========================================================================
#
# `pets.intervention` builds the event. This function decides WHEN it is allowed
# to, and it does not rebuild anything: the trigger evaluator is `pets._fires`,
# the payload author is `pets.intervention`, the tier gate is `pets.covers`, and
# the refusal is `pets._refusal`. One author per thing.
#
# THE ONE PIECE OF MACHINERY WORTH EXPLAINING
# `pets.intervention` evaluates its own triggers at the bond rank's scale, which
# is by definition no earlier than ours. So when a regalia has brought a trigger
# forward, this function has to tell pets.py which trigger fired without lying to
# it about anything else: `_saturate` hands it the minimum signal that fires
# THAT trigger at ITS OWN threshold, merged over the real signals.
#
# That is exact rather than approximate, and it is exact because of one property
# of the roster which is asserted in `self_check`: no companion has two triggers
# with the same (kind, category). A signal raised for one trigger therefore
# cannot fire another, every trigger earlier in the list has already been shown
# not to fire at our lower scale, and pets.py walks the list in order. The
# resulting event names the trigger we chose, with pets.py's own line, body,
# rank ceiling and hint weight — and `self_check` proves that by diffing every
# pet against every one of its triggers.

_SATURATE = {
    "idle_before_first_submit": lambda t, v: {"submitted": False,
                                              "seconds_elapsed": v},
    "stuck_seconds": lambda t, v: {"seconds_since_progress": v},
    "failed_attempts": lambda t, v: {"failed_attempts": int(v) + 1},
    "syntax_failures": lambda t, v: {"syntax_failures": max(1, int(v) + 1)},
    "timeout_failures": lambda t, v: {"timeout_failures": max(1, int(v) + 1)},
    "hidden_trial_failed": lambda t, v: {"hidden_failures": max(1, int(v) + 1)},
    "perf_trial_failed": lambda t, v: {"perf_failed": True},
    "weakness_survived": lambda t, v: {"weakness": "held"},
    "repeat_category": lambda t, v: {
        "last_categories": [t.category or "REPEAT"] * max(2, int(round(v)))},
    "failure_category": lambda t, v: {
        "category_counts": {t.category: max(1, int(round(v)))}},
}


def _saturate(trigger, signals: dict, scale: float) -> dict:
    """The real signals, plus the least thing that fires this trigger at `scale`.

    `scale` here is the BOND RANK's scale, not ours: we are constructing the
    signal pets.py needs in order to agree with us, and it is going to compare
    against its own threshold.
    """
    out = dict(signals or {})
    build = _SATURATE.get(trigger.kind)
    if build is None:
        return out
    value = trigger.threshold(scale)
    patch = build(trigger, value)
    for key, item in patch.items():
        if key == "category_counts":
            merged = dict(out.get("category_counts") or {})
            merged.update(item)
            out[key] = merged
        else:
            out[key] = item
    return out


def intervention(pet_id: str, *, bond: int = 0, mode: str = "adventure",
                 region_id: str = "", signals: dict | None = None,
                 context: dict | None = None, spoken: int = 0,
                 difficulty: str = "", boss: bool = False, final: bool = False,
                 sealed: bool = False, refused_already: bool = False,
                 state: dict | None = None,
                 regalia_state: dict | None = None,
                 also_scale: float = 1.0,
                 also_interventions: int = 0) -> dict | None:
    """`pets.intervention` with an object on the animal. Same shape, always.

    Drop-in: every argument `pets.intervention` takes, in the same order, plus
    `regalia_state` and the two bridge keywords `schedule` documents. Returns
    the same dict or None, with four extra keys —
    `regalia`, `regalia_name`, `regalia_kind` and `regalia_home` — so the client
    can say WHY the animal spoke twice. Nothing else about the payload moves, and
    `self_check` proves that field by field.
    """
    pet = pets.BY_ID.get(pet_id)
    if pet is None:
        return None
    worn = worn_by(regalia_state, pet_id)
    plan = schedule(pet_id, bond, region_id=region_id, regalia_id=worn,
                    mode=mode, sealed=sealed, also_scale=also_scale,
                    also_interventions=also_interventions)

    def _tag(event):
        if event is None:
            return None
        event["regalia"] = plan["regalia"]
        event["regalia_name"] = plan["regalia_name"]
        event["regalia_kind"] = plan["kind"]
        event["regalia_home"] = plan["at_home"]
        return event

    # No object, or an object that is doing nothing here: pets.py answers, and
    # this function is a pass-through with four extra keys on the payload.
    if not plan["applied"]:
        return _tag(pets.intervention(
            pet_id, bond=bond, mode=mode, region_id=region_id, signals=signals,
            context=context, spoken=spoken, difficulty=difficulty, boss=boss,
            final=final, sealed=sealed, refused_already=refused_already,
            state=state))

    # ABOVE ITS DEPTH: regalia does not touch the refusal path at all. Not as a
    # safety margin — as a statement. The refusal is the tier ladder speaking,
    # it costs nothing and clamps nothing, and an object that made an animal
    # apologise sooner or more often would be an object that had an opinion
    # about depth. pets.py answers this case on its own, exactly as it would
    # have with nothing on the animal.
    depth = pets.effective_difficulty(
        difficulty or (context or {}).get("difficulty", ""),
        boss=boss, final=final)
    if not pets.covers(pet_id, depth):
        return _tag(pets.intervention(
            pet_id, bond=bond, mode=mode, region_id=region_id, signals=signals,
            context=context, spoken=spoken, difficulty=difficulty, boss=boss,
            final=final, sealed=sealed, refused_already=refused_already,
            state=state))

    rank = pets.bond_rank(int(bond or 0))

    # The frequency half. pets.py refuses at `spoken >= rank.interventions`, so
    # a companion on its last regalia-granted sentence is handed a `spoken` it
    # will accept and the true numbers are corrected on the way out. It is a
    # correction of two display fields, not of a decision.
    allowance = plan["interventions"]
    if spoken >= allowance:
        return None
    pets_spoken = min(int(spoken), max(0, rank.interventions - 1))

    # The earliness half. Our scale is lower or equal, so this is a superset of
    # what pets.py would fire on, and the first entry in the pet's own order is
    # the one pets.py would have chosen too.
    fired = None
    for trigger in pet.triggers:
        if pets._fires(trigger, signals or {}, plan["threshold_scale"]):
            fired = trigger
            break
    if fired is None:
        return None

    event = pets.intervention(
        pet_id, bond=bond, mode=mode, region_id=region_id,
        signals=_saturate(fired, signals, rank.threshold_scale),
        context=context, spoken=pets_spoken, difficulty=difficulty, boss=boss,
        final=final, sealed=sealed, refused_already=refused_already,
        state=state)
    if event is None:
        return None
    if not event.get("refused"):
        # The two display fields, and the real threshold rather than the
        # saturated one. A player who is told the raptor spoke at 3 failures
        # when the collar brought it to 2 has been told the wrong thing about
        # the object they are wearing.
        event["spoken"] = int(spoken) + 1
        event["remaining"] = max(0, allowance - int(spoken) - 1)
        event["threshold"] = fired.threshold(plan["threshold_scale"])
    return _tag(event)


def party_intervention(active: list, *, bonds: dict | None = None,
                       mode: str = "adventure", region_id: str = "",
                       signals: dict | None = None, context: dict | None = None,
                       spoken: dict | None = None, difficulty: str = "",
                       boss: bool = False, final: bool = False,
                       sealed: bool = False, refused: list | None = None,
                       state: dict | None = None,
                       regalia_state: dict | None = None,
                       also_scale: float = 1.0,
                       also_interventions: int = 0) -> dict | None:
    """The call site the engine already makes, with regalia folded in.

    Same name and same signature as `pets.party_intervention` plus
    `regalia_state`, so wiring this up is one import change at one call site.
    """
    already = set(refused or [])
    for pet_id in (active or [])[:pets.ACTIVE_LIMIT]:
        found = intervention(
            pet_id, bond=int((bonds or {}).get(pet_id, 0)), mode=mode,
            region_id=region_id, signals=signals, context=context,
            spoken=int((spoken or {}).get(pet_id, 0)),
            difficulty=difficulty, boss=boss, final=final, sealed=sealed,
            refused_already=pet_id in already, state=state,
            regalia_state=regalia_state, also_scale=also_scale,
            also_interventions=also_interventions)
        if found:
            return found
    return None


# ==========================================================================
# SECTION 7 — EARNING ONE
# ==========================================================================


def progress(regalia_id: str, evidence: dict | None = None) -> dict:
    """How close this player is to this object. Pure: it describes, it does not
    grant, which is the same division `pets.discovery_progress` draws and for the
    same reason — evidence is evaluated in one place and acted on in another."""
    piece = BY_ID.get(regalia_id)
    if piece is None:
        return {"regalia": regalia_id, "checks": [], "met": False}
    # pets.py owns the evidence vocabulary and its evaluator. Reaching for the
    # private name is deliberate and is cheaper than the alternative, which is a
    # second opinion about what an unaided clear is.
    checks = [pets._discovery_row(clause, evidence or {}) for clause in piece.needs]
    return {
        "regalia": piece.id, "name": piece.name, "pet": piece.pet,
        "pet_name": pets.BY_ID[piece.pet].name,
        "kind": piece.kind, "kind_label": KINDS[piece.kind]["label"],
        "buys": KINDS[piece.kind]["buys"],
        "region": piece.region,
        "region_name": world.REGION_BY_ID.get(piece.region, {}).get("name", ""),
        "where": piece.where, "how": piece.how,
        "checks": checks,
        "met": bool(checks) and all(row["met"] for row in checks),
    }


def newly_found(evidence: dict | None = None,
                already: list | None = None) -> list:
    """Every object whose deed is now done and which the player does not have.

    Only for companions the player has actually MET. An object arriving for an
    animal you have never seen would be a spoiler with a progress bar, and the
    codex has `undiscovered` for that job.
    """
    have = set(already or [])
    met = set((evidence or {}).get("pets_found") or [])
    out = []
    for piece in REGALIA:
        if piece.id in have or piece.pet not in met:
            continue
        row = progress(piece.id, evidence)
        if row["met"]:
            out.append(row)
    return out


# ==========================================================================
# SECTION 8 — STATE
# ==========================================================================
#
# Flat, JSON-safe, tiny. `found` is append-only. `worn` is one object per
# companion and is the only thing in here a player can change back.

REGALIA_STATE_KEY = "regalia"


def new_state() -> dict:
    return {"found": [], "worn": {}}


def is_found(state: dict | None, regalia_id: str) -> bool:
    return regalia_id in ((state or {}).get("found") or [])


def grant(state: dict, regalia_id: str, *, wear_it: bool = True) -> dict:
    """Record that the player has the object. Idempotent.

    It goes on the animal immediately if that animal has nothing on, because the
    alternative is a player who earns a jade collar and then has to find a menu.
    It never displaces something already worn: that was a decision, and this
    module does not overrule decisions it did not make.
    """
    piece = BY_ID.get(regalia_id)
    if piece is None:
        return {"error": "no such regalia", "regalia": regalia_id}
    found = state.setdefault("found", [])
    news = regalia_id not in found
    if news:
        found.append(regalia_id)
    worn = state.setdefault("worn", {})
    put_on = False
    if wear_it and not worn.get(piece.pet):
        worn[piece.pet] = regalia_id
        put_on = True
    return {"regalia": piece.id, "name": piece.name, "pet": piece.pet,
            "new": news, "worn": put_on, "line": piece.line}


def wear(state: dict, regalia_id: str) -> dict:
    """Put one object on its animal, replacing whatever was there.

    Choosing IS the taking-off, same as `pets.set_active`: there is no separate
    destructive gesture because there is nothing destructive about it.
    """
    piece = BY_ID.get(regalia_id)
    if piece is None:
        return {"error": "no such regalia", "regalia": regalia_id}
    if not is_found(state, regalia_id):
        return {"error": "not found", "regalia": regalia_id,
                "how": piece.how}
    worn = state.setdefault("worn", {})
    before = worn.get(piece.pet, "")
    worn[piece.pet] = regalia_id
    return {"regalia": piece.id, "name": piece.name, "pet": piece.pet,
            "replaced": before, "line": piece.line}


def take_off(state: dict, pet_id: str) -> dict:
    worn = state.setdefault("worn", {})
    before = worn.pop(pet_id, "")
    return {"pet": pet_id, "removed": before}


def worn_by(state: dict | None, pet_id: str) -> str:
    """What that animal currently has on, or "". Tolerates a state written
    before this module existed, which is every save there currently is."""
    piece = ((state or {}).get("worn") or {}).get(pet_id, "")
    return piece if piece in BY_ID and BY_ID[piece].pet == pet_id else ""


# ==========================================================================
# SECTION 9 — THE SCREEN
# ==========================================================================


def catalogue(state: dict | None = None, *, region_id: str = "",
              pets_found: list | None = None) -> list:
    """Every object, grouped by companion, for the codex page.

    Unearned objects render — name, place, and the deed — for companions the
    player has met, because a hidden thing nobody can work toward is not content,
    it is an accident. Objects belonging to animals the player has never seen are
    left out entirely, which is the same call `pets.catalogue` makes about the
    animals themselves.
    """
    met = set(pets_found if pets_found is not None else pets.PET_IDS)
    rows = []
    for pet_id in pets.PET_IDS:
        if pet_id not in met:
            continue
        pet = pets.BY_ID[pet_id]
        pieces = [p.to_dict(found=is_found(state, p.id),
                            worn_now=worn_by(state, pet_id) == p.id,
                            region_id=region_id)
                  for p in for_pet(pet_id)]
        rows.append({
            "pet": pet_id, "name": pet.name, "species": pet.species,
            "tier": pet.tier, "helps_through": pets.TIER_BY_KEY[pet.tier].depth,
            "element": elements.pet_element(pet.species, pet_id),
            "skill": pet.skill,
            "worn": worn_by(state, pet_id),
            "regalia": pieces,
            # Said on every row, because this is the screen where a player would
            # otherwise invent the belief that a better collar reads harder
            # problems.
            "note": (f"Whatever it is wearing, {pet.name} still helps through "
                     f"{pets.TIER_BY_KEY[pet.tier].depth} and no further."),
        })
    return rows


def view(state: dict | None = None, *, pet_id: str = "", bond: int = 0,
         region_id: str = "", pets_found: list | None = None,
         mode: str = "adventure", sealed: bool = False,
         also_scale: float = 1.0, also_interventions: int = 0) -> dict:
    """Everything the regalia screen draws for the companion in the field."""
    worn = worn_by(state, pet_id)
    plan = schedule(pet_id, bond, region_id=region_id, regalia_id=worn,
                    mode=mode, sealed=sealed, also_scale=also_scale,
                    also_interventions=also_interventions)
    pet = pets.BY_ID.get(pet_id)
    return {
        "pet": pet_id,
        "pet_name": pet.name if pet else "",
        "region": region_id,
        "region_name": world.REGION_BY_ID.get(region_id, {}).get("name", ""),
        "schedule": plan,
        "choices": [p.to_dict(found=is_found(state, p.id),
                              worn_now=worn == p.id, region_id=region_id)
                    for p in for_pet(pet_id)],
        "catalogue": catalogue(state, region_id=region_id,
                               pets_found=pets_found),
        "limit": WORN_LIMIT,
        "ceiling": INTERVENTION_CEILING,
        "floor": SCALE_FLOOR,
        "helps_through": (pets.TIER_BY_KEY[pet.tier].depth if pet else ""),
        "lines": [
            "It buys how soon and how often. It does not buy how deep.",
            "Nothing here is for sale, at any price, in any shop.",
        ],
    }


# ==========================================================================
# SECTION 10 — THE PROOFS
# ==========================================================================


def _prove_no_depth() -> dict:
    """Regalia cannot move the tier ladder, proved by running it.

    For every companion, every object it owns and every difficulty in the
    ladder, the payload with the object on is compared to the payload without
    it. The fields below are the tier ladder's whole surface; if any of them
    ever differ, an object has started buying depth.
    """
    frozen = ("pet", "refused", "tier", "helps_through", "hint_kind",
              "hint_label", "rule", "rank_ceiling", "hint_weight", "trigger",
              "trigger_category", "opening", "body", "difficulty")
    signals = {"submitted": False, "seconds_elapsed": 10_000,
               "seconds_since_progress": 10_000, "failed_attempts": 50,
               "syntax_failures": 50, "timeout_failures": 50,
               "hidden_failures": 50, "perf_failed": True, "weakness": "held",
               "last_categories": ["X"] * 6,
               "category_counts": {c: 9 for c in
                                   ("PYTHON_RECALL", "WRONG_ALGORITHM",
                                    "OFF_BY_ONE", "PATTERN_NOT_RECOGNIZED",
                                    "EDGE_CASE", "WRONG_DATA_STRUCTURE",
                                    "RECURSION", "TREE_TRAVERSAL", "TESTING",
                                    "INEFFICIENT_ALGORITHM")}}
    differences = []
    refusals_changed = []
    covered = 0
    for piece in REGALIA:
        pet_id = piece.pet
        for difficulty in ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD",
                           "ELITE", "BOSS"):
            for region_id in home_regions(piece.id)[:1] + ["fields_of_syntax"]:
                bare = pets.intervention(
                    pet_id, bond=400, region_id=region_id, signals=signals,
                    difficulty=difficulty)
                state = new_state()
                grant(state, piece.id)
                dressed = intervention(
                    pet_id, bond=400, region_id=region_id, signals=signals,
                    difficulty=difficulty, regalia_state=state)
                if bare is None or dressed is None:
                    if (bare is None) != (dressed is None):
                        differences.append(
                            f"{piece.id} @ {difficulty}: one spoke and the "
                            f"other did not")
                    continue
                covered += 1
                if bare.get("refused") != dressed.get("refused"):
                    refusals_changed.append(f"{piece.id} @ {difficulty}")
                for key in frozen:
                    if bare.get(key) != dressed.get(key):
                        differences.append(
                            f"{piece.id} @ {difficulty}: {key} moved from "
                            f"{bare.get(key)!r} to {dressed.get(key)!r}")
    return {
        "payloads_compared": covered,
        "tier_fields_unchanged": not differences,
        "differences": differences[:10],
        "refusals_unchanged": not refusals_changed,
        "refusals_changed": refusals_changed[:10],
    }


def _prove_no_effect_keys() -> dict:
    """No object grants anything from `items.EFFECT_LABELS`, so no object can
    grant one of `pets.DEPTH_GATED_EFFECTS` by accident.

    Checked against the dataclass rather than against a list of values, because
    the failure mode this guards against is somebody ADDING an `effects` field
    to Regalia in six months and wiring it to the party bag.
    """
    fields = set(Regalia.__dataclass_fields__)
    banned = {"effects", "passives", "tier", "depth", "hint_kind",
              "rank_ceiling", "hint_weight", "fitting", "price", "gold",
              "cost"}
    return {
        "regalia_fields": sorted(fields),
        "no_effect_field": not (fields & banned),
        "offending_fields": sorted(fields & banned),
        "depth_gated_effects_unreachable": not (fields & {"effects"}),
        "nothing_costs_gold": not (fields & {"gold", "price", "cost",
                                             "fitting"}),
    }


def _prove_bounds() -> dict:
    """Every schedule a player can reach, with the numbers written out.

    The interesting rows are the last two: a Storied companion in an EARLY
    object is held at SCALE_FLOOR rather than at 0.375, and a Storied companion
    in an OFTEN object is held at INTERVENTION_CEILING.
    """
    rows = []
    worst_scale = 1.0
    most = 0
    # The jaguar's two, because the player named one of them and because they
    # are one of each kind on the same animal, which is the comparison a player
    # is actually making at the codex screen.
    for rank in pets.BOND_RANKS:
        for regalia_id in ("", "three_path_cord", "jade_collar"):
            for home in (True, False):
                piece = BY_ID.get(regalia_id)
                region = (home_regions(regalia_id)[0]
                          if piece is not None and home else "")
                plan = schedule(piece.pet if piece else "jaguar", rank.at,
                                region_id=region, regalia_id=regalia_id)
                worst_scale = min(worst_scale, plan["threshold_scale"])
                most = max(most, plan["interventions"])
                rows.append({
                    "rank": rank.key, "regalia": regalia_id or "-",
                    "kind": plan["kind"] or "-",
                    "at_home": plan["at_home"],
                    "threshold_scale": plan["threshold_scale"],
                    "interventions": plan["interventions"],
                    # STUB's blank-screen trigger is authored at 120 seconds.
                    # This is when it actually fires, which is the only form of
                    # this number a player ever experiences.
                    "idle_120_fires_at": round(120 * plan["threshold_scale"]),
                })
    # And the bridge: the deepest piece quests.py can hand out is 0.82 with one
    # extra intervention, stacked on top of the collar, on a Storied companion.
    # Separately clamped that is 0.5 * 0.75 * 0.82 = 0.3075 and five
    # interventions; folded through `also_scale` it is the floor and the
    # ceiling, which is the entire reason the parameter exists.
    stacked = schedule("jaguar", 400, region_id="stringwood_labyrinth",
                       regalia_id="three_path_cord", also_scale=0.82,
                       also_interventions=1)
    stacked_often = schedule("jaguar", 400, region_id="stringwood_labyrinth",
                             regalia_id="jade_collar", also_scale=0.82,
                             also_interventions=1)
    worst_scale = min(worst_scale, stacked["threshold_scale"])
    most = max(most, stacked_often["interventions"])

    return {
        "rows": rows,
        "stacked_with_quests_regalia": {
            "threshold_scale": stacked["threshold_scale"],
            "unclamped_would_be": round(0.5 * EARLY_SCALE_HOME * 0.82, 4),
            "interventions": stacked_often["interventions"],
            "unclamped_would_be_interventions": 3 + OFTEN_EXTRA_HOME + 1,
            "floored": stacked["floored"], "capped": stacked_often["capped"],
        },
        "lowest_threshold_scale": round(worst_scale, 3),
        "floor": SCALE_FLOOR,
        "floor_holds": worst_scale >= SCALE_FLOOR - 1e-9,
        "most_interventions": most,
        "ceiling": INTERVENTION_CEILING,
        "ceiling_holds": most <= INTERVENTION_CEILING,
        "fastest_blank_screen_seconds": round(120 * worst_scale),
    }


def _prove_seal() -> dict:
    """Sealed, and in Interview Mode, an object is jewellery."""
    from .config import MODE_INTERVIEW
    state = new_state()
    grant(state, "jade_collar")
    bare = pets.bond_rank(400)
    sealed = schedule("jaguar", 400, region_id="stringwood_labyrinth",
                      regalia_id="jade_collar", sealed=True)
    exam = schedule("jaguar", 400, region_id="stringwood_labyrinth",
                    regalia_id="jade_collar", mode=MODE_INTERVIEW)
    live = schedule("jaguar", 400, region_id="stringwood_labyrinth",
                    regalia_id="jade_collar")
    return {
        "sealed_matches_bare": (sealed["interventions"] == bare.interventions
                                and sealed["threshold_scale"]
                                == bare.threshold_scale),
        "interview_matches_bare": (exam["interventions"] == bare.interventions
                                   and exam["threshold_scale"]
                                   == bare.threshold_scale),
        "live_is_different": live["interventions"] != bare.interventions,
        "seal_is_an_argument": True,   # nothing here reads a mode or an encounter
    }


def _prove_triggers_are_unique() -> dict:
    """The precondition `_saturate` relies on, asserted rather than assumed.

    No companion has two triggers sharing a (kind, category). If one ever does,
    raising the signal for the later one would fire the earlier one and a player
    would be shown the wrong sentence.
    """
    clashes = []
    for pet in pets.PETS:
        keys = [(t.kind, t.category) for t in pet.triggers]
        if len(keys) != len(set(keys)):
            clashes.append(pet.id)
        for trigger in pet.triggers:
            if trigger.kind not in _SATURATE:
                clashes.append(f"{pet.id}: {trigger.kind} has no saturation")
    return {"trigger_keys_unique": not clashes, "clashes": clashes}


def _prove_earlier_actually_fires() -> dict:
    """The EARLY object does something, and the thing it does is what it says.

    Takes a real trigger — PLAIN's 150-second blank screen — and walks the clock
    forward one second at a time with and without the brow-band, then reports the
    two moments. If they are ever the same number, this whole module is a
    cosmetic.
    """
    def first_second(regalia_id: str, region_id: str) -> int:
        state = new_state()
        if regalia_id:
            grant(state, regalia_id)
        for second in range(0, 200):
            event = intervention(
                "llama", bond=0, region_id=region_id,
                signals={"submitted": False, "seconds_elapsed": second},
                difficulty="EASY", regalia_state=state)
            if event and not event.get("refused"):
                return second
        return -1

    home = home_regions("plateau_blinder")[0]
    bare = first_second("", home)
    dressed = first_second("plateau_blinder", home)
    away = first_second("plateau_blinder", "fields_of_syntax")
    return {
        "trigger": "llama / idle_before_first_submit / 150s",
        "without": bare, "with_at_home": dressed, "with_away": away,
        "earlier_at_home": dressed < bare,
        "earlier_away": away < bare,
        "home_beats_away": dressed < away,
    }


def _prove_more_often_actually_fires() -> dict:
    """The OFTEN object does something too, and only at home.

    A Wary jaguar is allowed one intervention. With the collar on, at home, it
    is allowed two, and the second one still costs a hint.
    """
    signals = {"submitted": False, "seconds_elapsed": 10_000,
               "seconds_since_progress": 10_000,
               "category_counts": {"PATTERN_NOT_RECOGNIZED": 9}}
    state = new_state()
    grant(state, "jade_collar")
    home = "stringwood_labyrinth"

    def speaks(spoken, region_id, dressed):
        return intervention("jaguar", bond=0, region_id=region_id,
                            signals=signals, difficulty="MEDIUM",
                            spoken=spoken,
                            regalia_state=state if dressed else None)

    second_bare = speaks(1, home, False)
    second_home = speaks(1, home, True)
    second_away = speaks(1, "fields_of_syntax", True)
    return {
        "bare_second_intervention": second_bare is not None,
        "collared_second_intervention_at_home": second_home is not None,
        "collared_second_intervention_away": second_away is not None,
        "second_still_costs_a_hint":
            bool(second_home) and second_home.get("hint_weight") == pets.HINT_WEIGHT,
        "second_still_clamps_rank":
            bool(second_home) and bool(second_home.get("rank_ceiling")),
        "remaining_reported":
            second_home.get("remaining") if second_home else None,
    }


def _validate() -> list:
    """Everything that must be true of the roster, checked at import."""
    problems = []
    for pet_id in pets.PET_IDS:
        pieces = for_pet(pet_id)
        if len(pieces) != 2:
            problems.append(f"{pet_id}: {len(pieces)} objects, not two")
        kinds = sorted(p.kind for p in pieces)
        if kinds != sorted((EARLY, OFTEN)):
            problems.append(f"{pet_id}: kinds are {kinds}, not one of each")
    for piece in REGALIA:
        tag = piece.id
        if piece.pet not in pets.BY_ID:
            problems.append(f"{tag}: {piece.pet!r} is not a companion")
            continue
        if piece.kind not in KINDS:
            problems.append(f"{tag}: {piece.kind!r} is not a kind")
        if piece.region not in world.REGION_BY_ID:
            problems.append(f"{tag}: {piece.region!r} is not a region")
        if not piece.needs:
            problems.append(f"{tag}: no deed, so it is a pick-up")
        for clause in piece.needs:
            if clause.get("kind") not in pets.DISCOVERY_CHECKS:
                problems.append(f"{tag}: {clause.get('kind')!r} is not in "
                                f"pets.DISCOVERY_CHECKS")
        spine = piece.needs[0]
        if spine.get("kind") != "skill_unaided":
            problems.append(f"{tag}: the deed does not start in a skill")
        elif spine.get("skill") != pets.BY_ID[piece.pet].skill:
            problems.append(f"{tag}: earned in {spine.get('skill')}, and the "
                            f"companion teaches {pets.BY_ID[piece.pet].skill}")
        if not SITE.get(piece.id):
            problems.append(f"{tag}: no country, so it is never worth full "
                            f"value anywhere")
        for text in (piece.blurb, piece.worn, piece.line, piece.where,
                     piece.how):
            if "!" in text:
                problems.append(f"{tag}: exclamation mark")
        # An object must not describe itself as making the animal cleverer.
        low = " ".join((piece.blurb, piece.line, piece.worn)).lower()
        for phrase in ("harder problems", "deeper", "higher tier", "the answer",
                       "solves it", "any problem", "tells you the solution"):
            if phrase in low:
                problems.append(f"{tag}: text claims {phrase!r}")
    if len(set(REGALIA_IDS)) != len(REGALIA):
        problems.append("duplicate regalia ids")
    if len(REGALIA) != 2 * len(pets.PET_IDS):
        problems.append(f"{len(REGALIA)} objects for {len(pets.PET_IDS)} "
                        f"companions")
    return problems


def self_check() -> dict:
    """Counts and proofs. Safe to call from a test or the command line."""
    depth = _prove_no_depth()
    keys = _prove_no_effect_keys()
    bounds = _prove_bounds()
    seal = _prove_seal()
    unique = _prove_triggers_are_unique()
    early = _prove_earlier_actually_fires()
    often = _prove_more_often_actually_fires()
    problems = _validate()

    by_element: dict = {}
    for piece in REGALIA:
        by_element.setdefault(piece.element, []).append(piece.id)

    ok = (not problems
          and depth["tier_fields_unchanged"] and depth["refusals_unchanged"]
          and keys["no_effect_field"] and keys["nothing_costs_gold"]
          and bounds["floor_holds"] and bounds["ceiling_holds"]
          and seal["sealed_matches_bare"] and seal["interview_matches_bare"]
          and seal["live_is_different"]
          and unique["trigger_keys_unique"]
          and early["earlier_at_home"] and early["home_beats_away"]
          and often["collared_second_intervention_at_home"]
          and not often["bare_second_intervention"]
          and not often["collared_second_intervention_away"]
          and often["second_still_costs_a_hint"])

    return {
        "regalia": len(REGALIA),
        "companions": len(pets.PET_IDS),
        "per_companion": 2,
        "kinds": list(KINDS),
        "by_kind": {k: len([p for p in REGALIA if p.kind == k])
                    for k in KINDS},
        "by_element": {k: sorted(v) for k, v in sorted(by_element.items())},
        "named_by_the_player": ["jade_collar", "mystic_scarf"],
        "regions_used": sorted({p.region for p in REGALIA}),
        "spine_counts": {k: list(v) for k, v in SPINE_COUNT.items()},

        "numbers": {
            "early_home": EARLY_SCALE_HOME, "early_away": EARLY_SCALE_AWAY,
            "often_home": OFTEN_EXTRA_HOME, "often_away": OFTEN_EXTRA_AWAY,
            "scale_floor": SCALE_FLOOR,
            "intervention_ceiling": INTERVENTION_CEILING,
            "worn_limit": WORN_LIMIT,
        },

        "depth_is_untouched": depth,
        "effect_keys": keys,
        "bounds": bounds,
        "seal": seal,
        "triggers": unique,
        "earliness_works": early,
        "frequency_works": often,

        "problems": problems,
        "ok": ok,
    }


_PROBLEMS = _validate()
if _PROBLEMS:                                              # pragma: no cover
    raise AssertionError("regalia roster is wrong: " + "; ".join(_PROBLEMS))


# ==========================================================================
# SECTION 11 — THE WIRING CONTRACT
# ==========================================================================

WIRING = """
FOR WHOEVER IS WIRING THIS.

Four call sites, one state key, and no new effect vocabulary.

1. STATE
   engine.DEFAULT_STATE["regalia"] = regalia.new_state()
   regalia.REGALIA_STATE_KEY is that string. It persists next to the pet state
   and is the same shape: {"found": [...], "worn": {pet_id: regalia_id}}.
   Every reader tolerates its absence, so an old save loads with nothing worn
   rather than crashing.

2. THE INTERVENTION — THE ONLY BEHAVIOURAL CHANGE
   Wherever the engine calls pets.party_intervention today, call
   regalia.party_intervention instead. Identical signature plus one keyword:

       event = regalia.party_intervention(
           active, bonds=..., mode=..., region_id=..., signals=...,
           context=..., spoken=..., difficulty=..., boss=..., final=...,
           sealed=finalexam.sealed(enc, "PET"), refused=..., state=pet_state,
           regalia_state=G.state["regalia"])

   The payload is byte-for-byte what pets.py produced, plus `regalia`,
   `regalia_name`, `regalia_kind` and `regalia_home`. Charge `hint_weight` and
   clamp `rank_ceiling` exactly as before — a regalia-granted intervention is a
   hint and costs one.

   Do NOT add a mode test at the call site. `sealed` goes in, the same verdict
   pets.py already takes.

3. EARNING ONE
   After an encounter resolves, alongside pets.newly_found:

       for row in regalia.newly_found(evidence, state["regalia"]["found"]):
           regalia.grant(state["regalia"], row["regalia"])

   `evidence` is the SAME snapshot pets.discovery_progress already takes, with
   one extra key this module reads and pets.py does not:

       evidence["pets_found"] = state["pets"]["found"]

   That is the only addition. Without it nothing is ever earned, because an
   object for an animal you have not met is a spoiler with a progress bar.

4. THE SCREEN
   regalia.view(state["regalia"], pet_id=pets.active_id(state["pets"]),
                bond=state["pets"]["bond"].get(pet_id, 0),
                region_id=G.region, pets_found=state["pets"]["found"])
   returns the worn object, both choices for the active companion, the whole
   codex and the two numbers currently in force. regalia.wear() and
   regalia.take_off() are the only mutators the UI needs.

5. IF quests.REGALIA IS ALSO LIVE
   Do not call both systems side by side. Fold theirs through this one so both
   contributions pass a single floor and a single ceiling:

       gear = quests.regalia_effect(G.state["quests"])
       event = regalia.party_intervention(..., also_scale=gear["scale"],
                                          also_interventions=gear["interventions"])

   regalia.schedule(), regalia.intervention(), regalia.party_intervention() and
   regalia.view() all take the pair. Applying quests.companion_speech() and this
   module separately lets a Storied companion in a lantern harness and a jade
   collar reach 0.3075 and five interventions, both past the limits both files
   declare. regalia.self_check()["bounds"]["stacked_with_quests_regalia"] is that
   case, measured.

6. NOTHING FOR items.py TO DO
   Not one key is added to items.EFFECT_LABELS and no regalia enters
   items.CATALOGUE. A regalia is not equipment: it has no slot, no rarity, no
   effects bag, and it cannot be sold, bought, dropped or rolled. If it were an
   Item it would be an Item that buys help, and then a loot table could hand one
   out. If the inventory screen wants to SHOW them, read regalia.catalogue();
   that is a render, not an adoption.

7. THE FALLEN STARTER
   STUB's two objects stop working when the barrow closes, because
   pets.intervention returns None for a fallen companion before any of this is
   consulted. Nothing needs writing for that to be true. What the player is
   holding afterwards is pets.KEEPSAKE, and the boar that comes back out of the
   Ruins wears it: regalia id `closed_half_ring`, and its deed requires
   evidence["starter_fallen"].

8. TESTS
   assert regalia.self_check()["ok"]
   That call proves, among other things: every companion has exactly two
   objects, one of each kind; every deed is expressed in pets.DISCOVERY_CHECKS
   and evaluated by pets' own evaluator; no object moves tier, hint kind, rank
   ceiling, hint weight or a refusal, across every companion at every
   difficulty; no object grants an items.EFFECT_LABELS key or costs gold; the
   threshold floor and the intervention ceiling both hold at maximum bond; and
   an object is inert in a sealed run and in Interview Mode.
"""


if __name__ == "__main__":                                 # pragma: no cover
    import json
    print(json.dumps(self_check(), indent=2, default=str))
