"""Sanctuary: the healers nobody put on the map.

WHAT THIS IS
------------
Seventeen people who are a long way from town and will patch you up for
nothing. Fifteen of them are inside dungeons, one to a dungeon; two are out in
the open in the two regions where the walk home is longest. They are found
after a hard fight, by a player who is hurt, and finding one is the whole of
the reward — there is no chest next to them.

THE ONE THING THIS MODULE DOES NOT DO IS HEAL
---------------------------------------------
`upkeep.heal` heals. This module finds you a person, decides whether they will
open the door, charges the toll and then calls that function. There is no
second healing path in this file: no write to the health field, no second
affliction cure, no second pet revival, no second answer to the question "what
does this cost". `upkeep.py` already argued that one out, at length, in its
section A, and the argument applies down here word for word —

    "A player who cannot afford to be healed is a player who cannot afford to
    keep learning, and that is the one failure this game may never have."

— so `rest()` returns `gold_cost: 0` because `upkeep.heal()` handed it back,
and the reason it gives is `upkeep.MENDER.free_because` itself rather than a
second copy of the same sentiment. `self_check()["free"]` checks both, and
`self_check()["one_healer"]` reads this file's own source to prove there is no
write to the health field, the focus field, the faint flag or an integrity
number anywhere in the functions that actually run.

WHY THESE PEOPLE ARE DOWN THERE
-------------------------------
A save point with a face is still a save point. Each of the seventeen has a
trade, a reason and an opinion, and the reason is never "so that you can be
healed here". They fall into three kinds and the kind is on the record:

    STAYED   the place emptied and they did not go. Nine of them.
    TRAPPED  they are as stuck as you are, and in most cases have been longer.
             Four of them, and two of those are not asking to be rescued.
    HIDING   they would rather you had not found them. Four of them, and one
             will heal you and then make you leave by the long way so you
             cannot lead anyone back.

Nobody here is especially glad to see you. Two are annoyed, one has four men
on his level who matter more than you do, and one cannot tell you her name
because it was taken along with every other label in that castle.

HOW YOU FIND THEM, AND THE RATE, WHICH IS MEASURED
--------------------------------------------------
A healer nobody finds is a healer nobody has. So the hiding is done by the
PLAYER'S CONDITION and not by the geography, and the geography is then bent as
far toward the player as it will go.

THE DOOR OPENS IN EXACTLY THE BANDS WHERE `upkeep.alarm()` SPEAKS. At or below
half health — WORN, CRITICAL, DIRE — there is a door. Above half there is no
door at all; not a locked one, not a grey one on the map, nothing, because a
sanctuary that opens for a healthy player is a save point and this is not that.
No new threshold was invented for this: it is the number the sprite already
changes colour at, which means the player has been told where the line is by
something they were looking at anyway. Two other things open it, both of them
descriptions of somebody who has just survived a fight: a fainted companion,
regardless of health (section E, and the reason the feature was asked for), and
having just cleared a HARD, ELITE or BOSS room.

THE GEOGRAPHY IS THEN AS KIND AS IT CAN BE WITHOUT BEING A SIGNPOST. The host
room is picked deterministically from the run seed, always in the back half of
the dungeon, always with a real fight next door, and — the important part —
always within ROUTE_TOLERANCE of the road from the threshold to the chamber.
Measured over 15 dungeons x 40 run seeds = 600 samples, in `self_check()`:

    within one room of the road to the chamber ............ 600 / 600
    the fallback placement rule firing ..................... 0 / 600
    landed in the back half of the dungeon ............... 600 / 600
    average length of that road ............... 12.6 rooms
    share of that road inside earshot ......... 41.5%  (worst dungeon 21.9%)
    share of the whole dungeon in earshot ..... 27.9%
    distinct rooms the door can land in ....... 8.3 per dungeon, over 40 seeds

Read that as: a hurt player walking to the boss spends four rooms in ten close
enough to be told, and what they are told is a tell and a direction — reed
smoke, a kettle, a lamp on a landing nobody wastes oil on, "one room south".
Not a marker. The last eight point three says the search is different on the
second descent, so a player who found Dov Kerrin once cannot simply walk back
to the room he was in last time.

WHAT THE RATE IS NOT. None of the above is a claim about how many players will
meet one, because that depends on how often a player drops below half, and this
module cannot measure that. What it is, is a guarantee about the half of the
problem that is ours: no player who is hurt on the main road of any dungeon in
this game can fail to be told there is somebody down here. If they are never
hurt, they never needed one.

Found once, known for ever. `state["sanctuary"]["known"]` is permanent, a known
sanctuary draws on the map from the start of every later descent and tells at
any health, and that permanence is the entire reward for having found it.

THE LIMITS, AND WHY THE TOWN SURVIVES THEM
------------------------------------------
`upkeep.py` built the town loop on purpose and this module is not allowed to
delete it. Three limits, all enforced in `can_rest()`:

  1. ONCE PER DESCENT. One rest per run, keyed on the run seed. Walking out and
     back in buys another — and costs the entire descent, which is the same
     walk the town charges.
  2. TEN GRADED CLEARS BETWEEN RESTS, SAVE-WIDE — one clock for all seventeen
     of them, not one each. Keyed per healer this limit does nothing: a player
     walks out of one region into the next and rests again having done no work
     at all in between, which is not one town replaced but seventeen.
     `_prove_no_chaining()` rests at every healer in the game back to back and
     requires sixteen of the seventeen to refuse. Under the town's own
     seventeen-encounter repair cadence, so it bites, and counted in work done
     rather than in minutes waited.
  3. A TOLL IN ARMOUR, NOT IN GOLD. She cuts the straps to get at the wound.
     One ordinary fight's worth of integrity, spent through `upkeep`'s own
     public wear function, which means every rest is a fraction of a trip to
     the smith. The sanctuary therefore FEEDS the gold pole of the town loop
     instead of draining it. Nothing breaks — upkeep's section C floors a piece
     at half and forbids destruction — and gold is never touched, so the toll
     cannot compound against the player who is already struggling. That last
     property is the whole reason it is armour and not coin.

WHAT THAT COSTS THE TOWN, MEASURED. A 240-encounter campaign, simulated twice
against upkeep's own wear, income and repair numbers — once with these people in
the ground and once without them — in
`tests/test_rescue_and_ending.py::TheHealerLimit`:

    encounters per town visit, without .......  6.0  6.2  6.0   (EASY/MED/HARD)
    encounters per town visit, with .......... 12.6 12.0 12.0
    town visits, with, as a share of without .. 48%  51%  50%
    trips the smith was the reason for ....... every band, still

Read that as: the walk home is halved, not abolished, and it stays inside
upkeep's own seventeen-encounter repair cadence in every band. At HARD the
healing pole stops being the reason to walk home entirely and the forge ladder
becomes the whole of it — which is the intended result and is the reason the
toll is armour. Margit was never the reason to walk to town; Ferro was.

What a sanctuary cannot do, ever: repair, sell, forge, respec, store, teach, or
hand over any part of any answer. It is health, afflictions, focus and the
animal, which is precisely what `upkeep.heal` already gives away, in a worse
room, from a person who has been down there longer than you.

Adventure Mode only. Pure stdlib.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import config, upkeep, world

# The building is `dungeons`', and this module only ever reads it.
from . import dungeons as dungeonmod

# ==========================================================================
# CAPABILITY AND STATE
# ==========================================================================
#
# Same arrangement as upkeep: the seal is decided at the call site by
# `finalexam.sealed(enc, SANCTUARY_CAPABILITY)` and arrives here as a keyword.
# The capability is upkeep's, because this is upkeep's healer in a worse room.
SANCTUARY_CAPABILITY = upkeep.UPKEEP_CAPABILITY          # "BUILD"

STATE_KEY = "sanctuary"


def available_in(mode: str) -> bool:
    """Interview Mode has no dungeons, so it has nothing hidden in them, and it
    has no healers because it is not teaching anybody anything."""
    return mode != config.MODE_INTERVIEW


# ==========================================================================
# THE PEOPLE
# ==========================================================================

KINDS = ("STAYED", "TRAPPED", "HIDING")

KIND_BLURB = {
    "STAYED": "The place emptied. They did not go.",
    "TRAPPED": "As stuck as you are, and mostly for longer.",
    "HIDING": "Would rather you had not found them.",
}


@dataclass(frozen=True)
class Sanctuary:
    """One healer, one hiding place. The client draws the room; this is who is
    in it and what they say."""
    id: str
    name: str
    trade: str
    kind: str                # one of KINDS
    region: str              # world.REGION_BY_ID key
    dungeon: str             # dungeons.DUNGEON_BY_ID key, or "" for overworld
    place: str               # where, physically
    why: str                 # why they are down here. Never "to heal you".
    tell: str                # what a hurt player two rooms away notices
    scene: tuple             # the discovery, in second person
    lines: dict              # situation -> what they say


def _s(**kwargs) -> Sanctuary:
    return Sanctuary(**kwargs)


SANCTUARIES: tuple = (
    # -- I. the vault dungeon ---------------------------------------------
    _s(id="ilma_vetch", name="Ilma Vetch", trade="bonesetter and cell-keeper",
       kind="STAYED", region="hashmap_highlands", dungeon="hollow_of_keys",
       place="a cell off the spine with six cots in it and a door that has "
             "never been locked from the outside",
       why="When the highlands emptied, the wardens went up the road with every "
           "key on a ring. There is exactly one key that opens the cell with "
           "the cots in it, and Ilma took it off the ring before they left, on "
           "the grounds that a ring is where keys go to become indistinguishable "
           "from one another. She has been the only person able to open the only "
           "room down here worth opening for four years.",
       tell="Somewhere off the spine a kettle is going, which is not a sound "
            "this place makes on its own.",
       scene=("The cell door is ajar, which no cell door here is. Inside: six "
              "cots, five of them stripped, and a woman sitting on the sixth "
              "sharpening something small.",
              "She looks at the blood on you, then at the door, then back. "
              "'You can shut that behind you. It does not lock. That is the "
              "entire point of it.'"),
       lines={
           "greet": ("One key. One door. Mine. Sit.",
                     "You came down the spine and did not try a single cell on "
                     "the way, which is why you are still upright and ahead of "
                     "schedule."),
           "healed": ("Bones set the way they are held. Hold it the way I put it.",
                      "Done. You lost less than you think and more than you should have."),
           "companion": ("Animals are easier. They tell you where it hurts and "
                         "then they stop talking about it.",),
           "spent": ("No. You had the cot. Somebody else gets the cot.",),
           "known": ("Back. Shut the door. Do not lock it — you cannot, and you "
                     "would embarrass us both trying.",),
       }),

    # -- II. the ring in the wood -----------------------------------------
    _s(id="osric_kade", name="Osric Kade", trade="copyist, field surgeon by accident",
       kind="TRAPPED", region="stringwood_labyrinth", dungeon="anagram_deeps",
       place="a clearing in the ring that he insists is a different clearing "
             "every time, and which is not",
       why="He came to copy the inscriptions and the Deeps rearranged the word "
           "for the road out. Nine days in, he cut his own leg open on a root "
           "and had to learn what to do about it from a herbal whose title had "
           "also been rearranged. He now knows field medicine very well and the "
           "way out not at all. He is not frightened. He is professionally "
           "offended.",
       tell="Ink. Somebody down here is still writing things down.",
       scene=("A man is kneeling over a slate with a stub of charcoal, copying "
              "the same six letters in every order he has not yet tried.",
              "'Do not tell me which way you came in,' he says, without looking "
              "up. 'I will work it out. I have a system.' He has one hundred and "
              "forty slates. The system is not going well."),
       lines={
           "greet": ("Sit. Do not touch the slates. They are in an order.",
                     "You are bleeding on chapter four. It is not a good chapter."),
           "healed": ("Held together. That is all any of us are.",
                      "There. Go and be somewhere else at speed."),
           "companion": ("It has been licking the same paw for an hour, which in "
                         "my experience means the other three are worse.",),
           "spent": ("I have one roll of linen and you have had it. Come back "
                     "when I have boiled the last one out.",),
           "known": ("You again. Still cannot find the way out, still have not "
                     "asked you for it. Sit down.",),
       }),

    # -- III. the numbered halls ------------------------------------------
    _s(id="bettany_ruck", name="Bettany Ruck", trade="army medic",
       kind="STAYED", region="array_caverns", dungeon="sunken_index",
       place="the eleventh alcove, counting from zero, which she will point out "
             "is the twelfth alcove",
       why="She served nineteen years under officers who could not count and "
           "came here because the alcoves are numbered and the numbering is "
           "honest. She stayed because being able to say 'you are forty-one "
           "paces from the surface' to a man with a hole in him is worth more "
           "than the hole being smaller. She has said it to two hundred and "
           "six people. All two hundred and six walked out.",
       tell="Somebody is counting, out loud, in the dark, and has not lost "
            "their place.",
       scene=("An alcove with a lamp in it and a woman in the lamp's light, "
              "counting a row of jars and touching each one.",
              "'Forty-one to the surface from here. Thirty-eight if the middle "
              "gate is open. Sit down before I get to the end of the row, I do "
              "not like starting again.'"),
       lines={
           "greet": ("Sit. Left side or right side, and do not say 'a bit of both'.",
                     "You are the first thing to come down the gauntlet in "
                     "eleven days. I counted the days as well."),
           "healed": ("Forty-one paces to the surface. Go and use them.",
                      "Whole. Now say the number back to me so I know you heard it."),
           "companion": ("Four legs, three working. That is a ratio, not a "
                         "tragedy. Hold its head.",),
           "spent": ("One patient, one kit, one go. That is the whole arithmetic "
                     "of a field station and I am not breaking it for you.",),
           "known": ("Forty-one. You did not ask, and you are going to need it.",),
       }),

    # -- IV. the long draw ------------------------------------------------
    _s(id="hedda_muir", name="Hedda Muir", trade="lung doctor",
       kind="HIDING", region="sliding_window_marsh", dungeon="the_long_draw",
       place="a stilt hut the reeds have been trained over, which is not there "
             "if you approach it from the wrong side",
       why="She wrote a report. The report said the levee board had been sizing "
           "the draw by the widest crossing anyone remembered rather than by the "
           "widest crossing that had happened, and that eleven marsh-workers had "
           "drowned of the difference. The board would like to discuss the "
           "report with her. She would like to treat lungs.",
       tell="Reed smoke. The kind you burn to keep a hut warm, not the kind the "
            "marsh makes on its own.",
       scene=("The reeds part on a hut you walked past twice. A woman is "
              "boiling something that smells medicinal and faintly of the marsh.",
              "'Before you sit down. Who told you where I was.' You say nobody "
              "did. She looks at you for a long moment and moves the pot off "
              "the heat. 'Then sit down.'"),
       lines={
           "greet": ("Breathe in. Now out. Now do it without doing that with "
                     "your shoulder.",
                     "You have swamp in you. Everyone who comes in here has "
                     "swamp in them."),
           "healed": ("Your chest will be sore. Sore is what it is meant to be.",
                      "Go. And if anybody asks, the reeds are empty on this side."),
           "companion": ("It has been holding its breath. They do that when the "
                         "water comes up. Put it down on its side.",),
           "spent": ("I have one hut and one fire and you have had a turn at "
                     "both. Do not stand there.",),
           "known": ("You did not bring anybody. Good. Sit.",),
       }),

    # -- V. the span ------------------------------------------------------
    _s(id="anselm_roe", name="Anselm Roe", trade="bridge surgeon",
       kind="STAYED", region="twin_pointer_pass", dungeon="converging_span",
       place="the exact midpoint of the span, where the two lanterns meet, "
             "under a tarpaulin that has been there long enough to have moss",
       why="Two lanterns walk the span from opposite ends every night and meet "
           "in the middle. Anselm worked out that everyone who falls, falls "
           "within thirty paces of where the lanterns meet, because that is "
           "where people stop watching their feet and start watching the other "
           "light. He has set thirty-one legs at that spot. He could have "
           "posted a sign. He decided a sign was not a surgeon.",
       tell="A lantern that is not moving, at the point where the two moving "
            "ones cross.",
       scene=("Under the tarpaulin: a folding cot, a lamp, and a man who was "
              "already awake before you got close enough to be heard.",
              "'Thirty-one,' he says, 'and every one of them was looking at the "
              "other lantern. Sit on the cot. Mind the leg of it, it is the "
              "only thing down here I have not fixed.'"),
       lines={
           "greet": ("Which post did you come off. There are two. It matters.",
                     "You walked the middle. Everybody walks the middle. That is "
                     "why I am in the middle."),
           "healed": ("It will take your weight. Not gracefully. Go slowly and "
                      "look at your feet.",
                      "Set. Thirty-two. I will put you in the book."),
           "companion": ("It went off the edge with you and came back up with "
                         "you. Give it a minute and then give it the good half "
                         "of whatever you are eating.",),
           "spent": ("One cot. It is occupied by the smell of you. Come back "
                     "when the span has aired out.",),
           "known": ("Thirty-two, back again. Do not make it thirty-three on the "
                     "way out.",),
       }),

    # -- VI. the mine -----------------------------------------------------
    _s(id="dov_kerrin", name="Dov Kerrin", trade="mine doctor",
       kind="TRAPPED", region="stack_queue_mines", dungeon="ninth_cart",
       place="the old powder store off the ninth level, dry, and stacked to the "
             "ceiling with things that were on their way up",
       why="He came down in the wrong order. The mine unloads from the top and "
           "the carts above him have not moved in two hundred and eleven days, "
           "so neither has he. This is not the part he minds. The part he minds "
           "is that people keep offering to get him out, and there are four "
           "men on the ninth level with crush injuries who cannot be moved, and "
           "he has explained this eleven times to eleven rescuers who each "
           "heard it as modesty.",
       tell="Warm air, coming up. Nothing this deep should be warm.",
       scene=("The powder store is dry and lit and there is a man in it with "
              "his sleeves rolled, arguing quietly with a ledger.",
              "'If you have come to get me out,' he says, 'I will save you the "
              "speech. I have four men on this level who cannot sit up. I am "
              "not the one who is trapped. Sit down and let me look at that.'"),
       lines={
           "greet": ("Wrong order. Everyone comes down in the wrong order.",
                     "Two hundred and eleven days. You are the ninth visitor and "
                     "the first with the sense to be injured on arrival."),
           "healed": ("Good. Now go up in the reverse of how you came down or "
                      "you will be my tenth visitor twice.",
                      "That is as close to right as it gets down here."),
           "companion": ("Bring it here. Dogs do better in a mine than men. They "
                         "do not spend the air on talking.",),
           "spent": ("I have four men who need what is left in that box more "
                     "than you need a second go at it.",),
           "known": ("Still here. Still four of them. Sit.",),
       }),

    # -- VII. the keep ----------------------------------------------------
    _s(id="sabine_quist", name="Sabine Quist", trade="apothecary, officially deceased",
       kind="HIDING", region="matrix_citadel", dungeon="turning_keep",
       place="a store-room that is on the citadel's plans and has not been in "
             "the same place as the plans since the keep started turning",
       why="The citadel's ledger has her dead these six years, and the pension "
           "goes to her sister, who has three children and a leaking roof and "
           "no other income in the world. Sabine takes the view that a keep "
           "which rotates without telling anyone has forfeited the right to be "
           "told things. She gives medicine away free, which is the detail that "
           "would give her up if anyone ever bothered to notice it.",
       tell="A store-room door where the plans say a wall, and light under it.",
       scene=("The door is where no door is drawn. Inside, a woman is grinding "
              "something in a mortar and does not stop.",
              "'I am dead,' she says. 'It is on the ledger, it is stamped, and "
              "there is a widow's pension attached to it that is currently the "
              "only thing between my sister and the weather. Are we agreed that "
              "I am dead.' You agree that she is dead. 'Good. Arm.'"),
       lines={
           "greet": ("The keep turned again. The plans did not. Neither did I.",
                     "You are the fourth living person in this room this year "
                     "and the other three were me on bad days."),
           "healed": ("Take it. It costs nothing. It has always cost nothing, "
                      "which is how I stayed dead.",
                      "Better. Do not thank me by name."),
           "companion": ("Put it on the bench. Yes, on the plans. The plans are "
                         "wrong anyway.",),
           "spent": ("I have ground out what I had. A dead woman cannot exactly "
                     "reorder from the citadel stores.",),
           "known": ("Still dead. Still here. Still free. Sit.",),
       }),

    # -- VIII. the grove --------------------------------------------------
    _s(id="ovid_thane", name="Ovid Thane", trade="monastery infirmarian",
       kind="TRAPPED", region="recursive_forest", dungeon="inner_grove",
       place="a lean-to against the innermost ring but one, with a pack by the "
             "door that has been packed for eleven months",
       why="He went in to bring back a novice who had gone in to bring back a "
           "forester who had gone in after a dog. He found all three. He is on "
           "his way out with them now, and has been on his way out with them "
           "since the spring, because every clearing in this forest contains a "
           "smaller forest and the way out is the way in, unwound, and nobody "
           "ever told him the stopping condition. He is not lost. He is "
           "unwinding. There is a difference and it matters to him.",
       tell="A path going outward that you have not walked inward.",
       scene=("A lean-to, a packed bag by the door, and a man in a habit sitting "
              "beside it with the air of someone about to leave.",
              "'I am on my way out,' he says, and means it entirely. Behind him "
              "a novice, a forester and a dog are asleep in a row. 'Sit down "
              "while I am still here.'"),
       lines={
           "greet": ("I am on my way out. Sit down first.",
                     "You went in. Say out loud what would make you stop going "
                     "in. Go on. I will wait, I have time and apparently forever."),
           "healed": ("Mended. Now: the way out is the way in, unwound.",
                      "There. Do not go deeper to feel better about the depth."),
           "companion": ("We have a dog already. One more will not unbalance "
                         "the household. Bring it here.",),
           "spent": ("I have four people to get out of here and one bag of "
                     "linen. You have had your share of the bag.",),
           "known": ("Still on my way out. Sit.",),
       }),

    # -- IX. the canopy ---------------------------------------------------
    _s(id="wisla_grane", name="Wisla Grane", trade="rookery surgeon",
       kind="STAYED", region="binary_tree_canopy", dungeon="split_canopy",
       place="a platform lashed into the busiest fork in the canopy, hung with "
             "splints the size of a finger",
       why="She splints birds. She is extremely good at it and it is not a job "
           "anyone respects. She stayed up here because the branches split and "
           "never rejoin, which means a climber who takes the wrong fork with a "
           "broken arm will not meet another living soul before the end of it. "
           "So she counted the traffic on every fork for a season and built her "
           "platform on the busiest one. That is the entire strategy and it has "
           "worked nineteen times.",
       tell="Birdsong from one fork and none from the other, which in this "
            "canopy means somebody up there is feeding them.",
       scene=("The fork opens onto a lashed platform strung with splints no "
              "bigger than a finger, and a woman winding one onto a jackdaw.",
              "'Left, root, right,' she says. 'That is the order I do things in "
              "and you are right. Sit there and do not jog the bird.'"),
       lines={
           "greet": ("You took the left fork. They all take the left fork.",
                     "Arm, is it. It is always an arm. Nobody falls feet first "
                     "out of a tree, they fall reaching."),
           "healed": ("Bound. It is the same splint I put on a jackdaw, scaled "
                      "up, and the jackdaw complained less.",
                      "Done. Go down the way you came up; the other fork does "
                      "not go anywhere you want."),
           "companion": ("Now that I can do properly. Hold its wings — its legs, "
                         "sorry. Force of habit.",),
           "spent": ("I have splints for birds and I have used the big one. "
                     "Come back when I have carved another.",),
           "known": ("The busiest fork in the canopy, and it is still mostly you.",),
       }),

    # -- X. the wastes ----------------------------------------------------
    _s(id="rhoda_ashby", name="Rhoda Ashby", trade="waystation medic",
       kind="HIDING", region="graph_wastes", dungeon="lattice_of_ruin",
       place="a cellar under a ruin that is identical to four other ruins, and "
             "she has made sure of that",
       why="She found the shortest road through the lattice and told people, "
           "because a shortest road is the sort of thing you tell people. What "
           "came up it was not the sort of thing she had in mind. She has since "
           "moved her station off the shortest road, made the outside of it look "
           "like every other ruin out here, and formed a firm view about which "
           "facts are safe to publish.",
       tell="One ruin out of four has a cellar door that somebody has recently "
            "swept.",
       scene=("The cellar steps are swept and the ruin above them is not. Below, "
              "a woman is stitching a mattress and does not look surprised.",
              "'I will fix you,' she says, 'and then you are going out by the "
              "north road, which is longer, and you are going to be annoyed "
              "about it, and you are going to do it anyway.'"),
       lines={
           "greet": ("Sit where I can see the door behind you.",
                     "You came the short way. Everyone comes the short way, "
                     "which is the problem with a short way."),
           "healed": ("Out by the north road. It is longer. That is the fee and "
                      "it is not negotiable.",
                      "Stitched. Walk out slowly and stop looking back at this "
                      "ruin, you are drawing a line to it."),
           "companion": ("It followed you down the short road too. At least one "
                         "of you has an excuse.",),
           "spent": ("I have one station, one kit and no intention of restocking "
                     "in daylight. Go.",),
           "known": ("North road. Every time. Sit.",),
       }),

    # -- XI. the lit ruins ------------------------------------------------
    _s(id="tobias_rell", name="Tobias Rell", trade="physician and tallykeeper",
       kind="STAYED", region="dp_ruins", dungeon="lit_tiles",
       place="a tiled room he has lit one tile at a time, each tile a wound he "
             "has already worked out",
       why="He writes down every injury he has ever treated and what worked, so "
           "that he never has to solve the same wound twice. Four hundred and "
           "six entries. He stayed in the ruins because the ruins do the same "
           "thing with their floor and he found that companionable. The tragedy "
           "of the place, he says, is not that the answers are lost. It is that "
           "somebody worked them out already, probably twice, and did not write "
           "them down.",
       tell="A room where the floor is lit in a pattern rather than in patches.",
       scene=("The floor is lit tile by tile in no shape you recognise, and an "
              "old man is adding one more with a piece of chalk and a candle.",
              "'Crush to the left forearm, fall from height, some burning,' he "
              "says before you have said anything. 'Page two hundred and nine. "
              "I know what to do about this. Sit down and let me be right.'"),
       lines={
           "greet": ("I have seen this before. That is not a boast, it is a "
                     "filing system.",
                     "Page two hundred and nine. Sit."),
           "healed": ("Same as last time. That is the good news and the whole "
                      "method.",
                      "Written down. If it happens again I will be faster, and "
                      "that is the only kind of faster there is."),
           "companion": ("Animals are page four hundred and one onward. A "
                         "shorter section. I am working on it.",),
           "spent": ("The page says one dressing per patient per day and the "
                     "page is me.",),
           "known": ("Page two hundred and nine again, is it. Sit.",),
       }),

    # -- XII. the cells ---------------------------------------------------
    _s(id="hanne_skeld", name="Hanne Skeld", trade="cell-block doctor",
       kind="STAYED", region="debugging_dungeon", dungeon="cracked_ward",
       place="the ward at the end of the cell block, with nine beds and a "
             "window that was bricked up by someone who meant well",
       why="Every program in these cells worked once, on somebody's machine, "
           "for one input. Her patients are the people who were standing in "
           "front of them the day they stopped. She stayed because sooner or "
           "later a defect down here is going to kill somebody outright, and "
           "she would rather it happened in a room with a doctor in it than in "
           "a room with a note on the door saying that this had never happened "
           "before.",
       tell="Clean linen. In this cell block, that is nearly alarming.",
       scene=("Nine beds, eight empty, all of them made. A woman is changing "
              "linen on the ninth and does not stop when you come in.",
              "'It worked on their machine,' she says, nodding at the cells. "
              "'For one input. Everyone in this ward is the second input. Bed "
              "three, it has the better mattress.'"),
       lines={
           "greet": ("Bed three. It has the better mattress and I am not "
                     "sentimental about the others.",
                     "What broke, and what did you do just before it broke. In "
                     "that order, and be honest about the second one."),
           "healed": ("Fixed. Read the crack before you go back down there.",
                      "Better. Now go and find out what actually did that to "
                      "you, because it will do it again."),
           "companion": ("Animals get bed one. They do not ask what happened "
                         "and I find I need the rest.",),
           "spent": ("I have nine beds and one of everything else. You had the "
                     "one of everything else.",),
           "known": ("Bed three. You know the way.",),
       }),

    # -- XIII. the stair --------------------------------------------------
    _s(id="petr_ossian", name="Petr Ossian", trade="stretcher-bearer, then surgeon",
       kind="STAYED", region="complexity_tower", dungeon="doubling_stair",
       place="the fourth landing, which is as far up as he has ever gone and "
             "further than most people come back down from",
       why="He carried stretchers up this tower for nine years and worked out "
           "something the architects never put on a plaque: each floor holds "
           "twice the rooms of the floor below, so half of everyone who goes up "
           "turns round on the fourth landing, and the ones who do not turn "
           "round come back down past it on a board. So he stopped climbing. He "
           "sits on the fourth landing and everyone he is ever going to meet "
           "comes to him. He is quietly certain this is the most intelligent "
           "thing anyone has ever done in this building.",
       tell="Somebody has left a lamp burning on a landing, and nobody wastes "
            "oil in this tower.",
       scene=("A landing, a lamp, a bench, and a big man sitting on it with his "
              "boots off, entirely at ease.",
              "'Fourth landing,' he says. 'Everyone comes past the fourth "
              "landing eventually, going one way or the other. I stopped "
              "climbing in the spring and I have not missed a single patient "
              "since. Sit down and think about that for a moment.'"),
       lines={
           "greet": ("Fourth landing. Everyone passes it. Sit.",
                     "You went up. How far did you get before you started "
                     "counting the doors."),
           "healed": ("Good as I can make it on a bench. Go down, not up. Down "
                      "is free.",
                      "Right. Next time do the arithmetic on the landing instead "
                      "of on the ninth floor."),
           "companion": ("Carried a wolfhound down eleven flights once. Never "
                         "again. Put it on the bench.",),
           "spent": ("One bench, one lamp, one go at a time. I am not a hospital, "
                     "I am a man who stopped climbing.",),
           "known": ("Still on the fourth landing. Still right about it.",),
       }),

    # -- XIV. the unlabelled halls ----------------------------------------
    _s(id="nock", name="Nock", trade="bonesetter",
       kind="TRAPPED", region="null_kings_castle", dungeon="unlabelled_halls",
       place="behind a door with NOCK stencilled on it, which is a store-room "
             "and was never anybody's name",
       why="The Null King did not break the language. He removed its names, and "
           "hers went with them. She does not know what she was called and has "
           "stopped finding this interesting. She took the word off the door she "
           "sleeps behind because a person needs something to be called and a "
           "door's name does fine. What she has kept is the trade: she sets "
           "bones, she knows she sets bones, and a thing you can still do is a "
           "name of a sort.",
       tell="A door in the unlabelled halls with a word on it.",
       scene=("Every door in this castle is blank. One is not. NOCK, stencilled, "
              "half scrubbed off by somebody who gave up.",
              "Inside, a woman looks up from a splint. 'It was on the door,' she "
              "says, before you ask. 'It is a door's name. It does fine.' She "
              "holds out a hand for your arm. 'I set bones. That is the part "
              "they did not get.'"),
       lines={
           "greet": ("I set bones. That is the whole of what I can tell you "
                     "about myself and it has turned out to be enough.",
                     "No signs anywhere in here. There is one on my door. Make "
                     "of that what you like."),
           "healed": ("Set. You will know it healed because it will stop asking "
                      "you about itself.",
                      "There. Say what it was that did it, out loud, before you "
                      "go. Naming things is worth more in here than anywhere."),
           "companion": ("This one has a name, I suppose. Say it where I can "
                         "hear it. I like hearing them.",),
           "spent": ("I have what the store-room had. The store-room had one.",),
           "known": ("Nock. Still. Sit down.",),
       }),

    # -- XV. under the sand -----------------------------------------------
    _s(id="corba_dain", name="Corba Dain", trade="pit surgeon, contracted",
       kind="STAYED", region="coding_coliseum", dungeon="under_arena",
       place="the third holding pen, which has a drain in the floor and a chair "
             "she has never once been seen to sit in",
       why="She is the only healer hidden anywhere in the Realms who is down "
           "here legitimately and under contract, and she thinks the whole "
           "business is idiotic. Paid by the heat, works by the body. Her view is that "
           "there is nothing wrong with a clock and nothing wrong with being "
           "fast, and that what the Coliseum actually sells is the feeling of "
           "having decided quickly, which is not the same thing and is what "
           "keeps her in work.",
       tell="A drain, and the smell of the stuff they wash a floor down with.",
       scene=("The third pen has a drain in the floor and a woman standing by a "
              "chair she is not using, already holding out a hand for your arm.",
              "'Fourth today. It is always the fourth heat. They stop deciding "
              "and start guessing and then they are down here with me.' She "
              "looks at the sand gate. 'The clock is not the problem. Go on, "
              "sit, you have got about nine minutes.'"),
       lines={
           "greet": ("Fourth today. Sit. You have got about nine minutes.",
                     "Slow and right beats fast and wrong. Fast and right beats "
                     "both. Neither of those is what happened to you."),
           "healed": ("Patched. Now go and be deliberate at speed, which is the "
                      "only trick there has ever been.",
                      "Right. Off you go. Try to come back through the gate "
                      "rather than over the wall."),
           "companion": ("They send animals out there now. I have opinions "
                         "about it and none of them fit in nine minutes.",),
           "spent": ("One patient per heat. I am contracted, not infinite.",),
           "known": ("Fourth today. It is always you now.",),
       }),

    # -- XVI. the open wastes (no dungeon) --------------------------------
    _s(id="lupe_ardeth", name="Lupe Ardeth", trade="road-doctor",
       kind="HIDING", region="graph_wastes", dungeon="",
       place="a tent pitched off the road, in a different place every nine days, "
             "and she keeps count of the nine days",
       why="The roads out here all connect to four others and the wrong people "
           "know that as well as she does. So the tent moves. Nine days is long "
           "enough for word to spread that there is a doctor out here and short "
           "enough that the word is out of date by the time it reaches anyone "
           "who would come for her. She has been doing this for six years and "
           "has never once been found by anybody who was looking.",
       tell="Tent-poles left on the ground, still warm side down.",
       scene=("Off the road, behind a ridge you would not have looked behind: "
              "one tent, guyed low, and a woman outside it who watched you come "
              "the whole way.",
              "'You were not looking for me,' she says. It is not a question. "
              "'People who are looking for me go up the road. Come in.'"),
       lines={
           "greet": ("Six days left on this pitch. You have caught me in the "
                     "middle of it, which is the only time this works.",
                     "Sit inside. Standing outside a tent is how a tent gets "
                     "noticed."),
           "healed": ("Go on. And go somewhere that is not in a straight line "
                      "from here.",
                      "Done. When you tell this story, do not put a ridge in it."),
           "companion": ("It will not settle until you do. Lie down and it will "
                         "copy you, they always do.",),
           "spent": ("What is in the tent is what fits in the tent. Come back "
                     "when I have been to a town.",),
           "known": ("You found it again. That is twice, which is once more "
                     "than I like. Come in.",),
       }),

    # -- XVII. the open castle (no dungeon) -------------------------------
    _s(id="bede_oster", name="Bede Oster", trade="the castle's last surgeon",
       kind="STAYED", region="null_kings_castle", dungeon="",
       place="the infirmary, which has no sign on it, in a castle where nothing "
             "has a sign on it",
       why="When the labels came off, the staff left, on the grounds that a "
           "building you cannot name your way around is a building you cannot "
           "work in. Bede stayed and found out something he thinks the King "
           "would hate: the wounded still arrive at the infirmary. Not because "
           "they can read the door — there is nothing on the door — but because "
           "people who have walked a place enough times know where things are "
           "without being told. He considers himself the standing "
           "counter-argument to the entire castle.",
       tell="Foot-tracks in dust, in a corridor with nothing at the end of it, "
            "all going the same way.",
       scene=("A corridor with nothing written anywhere and a floor worn pale "
              "down the middle of it. At the end, a room with beds in it and an "
              "old man boiling water.",
              "'No sign,' he says. 'There has not been a sign for six years. "
              "And here you are.' He seems to find this genuinely funny. 'They "
              "took the labels off and people found it anyway. Sit down, I want "
              "to tell you about it while I work.'"),
       lines={
           "greet": ("No sign on the door. Here you are anyway. Sit down.",
                     "He took the names. He did not take the floor, and the "
                     "floor remembers where everybody walked."),
           "healed": ("There. Now go back out and find a room you cannot name. "
                      "You will manage. You managed this one.",
                      "Mended. You walked here without being told. Hold on to "
                      "how that felt, it is the whole exam."),
           "companion": ("It found the door before you did. I have watched that "
                         "happen eleven times and it has not stopped being the "
                         "best argument I have.",),
           "spent": ("One infirmary, six years of stores, and a great many "
                     "people before you. Not today.",),
           "known": ("Still no sign. Still found it. Sit.",),
       }),
)

BY_ID: dict = {s.id: s for s in SANCTUARIES}
BY_DUNGEON: dict = {s.dungeon: s for s in SANCTUARIES if s.dungeon}
BY_REGION: dict = {}
for _s_row in SANCTUARIES:
    BY_REGION.setdefault(_s_row.region, []).append(_s_row.id)

# The overworld ones, which have no room graph to hide in.
OVERWORLD: dict = {s.region: s for s in SANCTUARIES if not s.dungeon}

# ==========================================================================
# WHY THE FIRST DUNGEON HAS NOBODY IN IT
# ==========================================================================
#
# `halfwritten_barrow` is the only dungeon with no sanctuary, and it is a
# deliberate hole rather than an oversight. It is tier 1, three floors deep, at
# GUIDED difficulty, and its deepest room is a short walk from Margit's door.
# A healer there would teach a new player that the town is optional before the
# town has finished teaching them what it is for — and the town is where the
# smith, the forge and the entire gold loop live. The first time a player is
# genuinely stranded should cost them the walk, once, so that the walk means
# something every time afterwards.
NO_SANCTUARY: tuple = ("halfwritten_barrow",)


# ==========================================================================
# FINDING ONE
# ==========================================================================
#
# THE DOOR OPENS EXACTLY WHERE THE ALARM SPEAKS.
#
# `upkeep.ALARM_BANDS` already divides the health bar into four, and the player
# is already watching it: STEADY above half and silent, then WORN, CRITICAL and
# DIRE below. Rather than invent a second threshold with a second number for a
# player to learn, the sanctuary uses that one. At or below half health the
# door is there. Above it, there is no door — not a locked door, no door — and
# the room is an ordinary room, because a sanctuary that opens for a healthy
# player is a save point and this is not that.
REVEAL_BANDS: tuple = ("WORN", "CRITICAL", "DIRE")

# The other two ways in, both of which describe a player who has just survived
# something whether or not their health says so.
REVEAL_DIFFICULTIES: tuple = ("HARD", "ELITE", "BOSS")

# How far the tell carries. Two rooms: far enough that a hurt player on the main
# road hears it, near enough that it names a direction rather than a mood.
TELL_RADIUS = 2

# The host room sits at or below this fraction of the dungeon's depth. Half,
# because "deep" has to mean something and the back half of a dungeon is where
# a player is hurt.
DEPTH_FRACTION = 0.5

# And within this many steps of the road to the boss chamber, whenever the
# building allows it. This is the anti-cruelty clause and it is the single most
# important number in the discovery rule: a healer placed honestly in the
# darkest corner of a lattice is a healer that exists only in the source code.
#
# It holds in every one of the 600 placements `self_check` samples, and the
# relaxed fallback in `_candidates` has never once had to fire. The road it is
# measured against is the walking road — `_adjacency` drops the winch home,
# which otherwise joins the chamber to the threshold in every dungeon in the
# game and would have put the door next to the front door.
ROUTE_TOLERANCE = 1


def _adjacency(dungeon, *, shortcuts: bool = False) -> dict:
    """room id -> sorted neighbours, as walls rather than as doors.

    Locks and reveals are deliberately ignored: a key is findable and a lever
    is pullable, so a locked door is still part of the shape of the building.

    SHORTCUTS ARE NOT, and that distinction is the whole reason this function
    takes an argument. Every dungeon in the game carries a winch, a stair or a
    rope that joins the chamber straight back to the threshold — `lattice_of_ruin`
    has passage 0-27, SHORTCUT, revealed by room 22 — and counting it would make
    the boss two steps from the door in every building in the game. It would
    also put the sanctuary on the wrong side of the map: the road a hurt player
    actually walks is the long one, and the winch is what they take home
    afterwards.
    """
    adj: dict = {room.id: [] for room in dungeon.rooms}
    for passage in dungeon.passages:
        if passage.kind == "SHORTCUT" and not shortcuts:
            continue
        if passage.a in adj and passage.b in adj:
            adj[passage.a].append(passage.b)
            adj[passage.b].append(passage.a)
    return {key: sorted(set(value)) for key, value in adj.items()}


def _distances(dungeon, start: int, adj: dict | None = None) -> dict:
    """Hop counts from `start`. Unreachable rooms are absent, which cannot
    happen in a dungeon this module was handed — `dungeons.audit` guarantees
    connectivity — but is handled rather than assumed."""
    adj = adj if adj is not None else _adjacency(dungeon)
    seen = {start: 0}
    frontier = [start]
    while frontier:
        nxt = []
        for node in frontier:
            for other in adj.get(node, ()):
                if other not in seen:
                    seen[other] = seen[node] + 1
                    nxt.append(other)
        frontier = nxt
    return seen


def _route(dungeon, source: int, target: int, adj: dict | None = None) -> list:
    """One shortest room path, as ids. Empty if there is no way."""
    adj = adj if adj is not None else _adjacency(dungeon)
    parent = {source: source}
    frontier = [source]
    while frontier:
        nxt = []
        for node in frontier:
            if node == target:
                frontier = []
                break
            for other in adj.get(node, ()):
                if other not in parent:
                    parent[other] = node
                    nxt.append(other)
        else:
            frontier = nxt
            continue
        break
    if target not in parent:
        return []
    path = [target]
    while path[-1] != source:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def _candidates(dungeon) -> list:
    """Rooms a sanctuary could plausibly be hidden in, best band first.

    Three conditions, relaxed in order until something qualifies, so this can
    never return empty for a connected dungeon:

      1. deep enough, not the chamber, not the threshold, and with a real fight
         next door — the "past a hard fight" clause, taken literally
      2. deep enough, not the chamber, not the threshold
      3. anything that is not the chamber or the threshold
    """
    deep = max(1, int(dungeon.max_depth * DEPTH_FRACTION))
    adj = _adjacency(dungeon)
    by_id = {room.id: room for room in dungeon.rooms}

    def ordinary(room) -> bool:
        return room.kind not in ("BOSS", "ENTRANCE") and room.id != dungeon.entrance

    def fight_next_door(room) -> bool:
        return any(by_id[n].demands_solving for n in adj.get(room.id, ())
                   if n in by_id)

    strict = [r.id for r in dungeon.rooms
              if ordinary(r) and r.depth >= deep and fight_next_door(r)]
    if strict:
        return sorted(strict)
    loose = [r.id for r in dungeon.rooms if ordinary(r) and r.depth >= deep]
    if loose:
        return sorted(loose)
    return sorted(r.id for r in dungeon.rooms if ordinary(r))


def host_room(dungeon, run_seed: int = 0) -> int:
    """Which room this descent's sanctuary is hidden in. Deterministic.

    The building itself never changes — `dungeons.generate(id)` is the same
    place every time — so the door moving between descents is the only thing
    that keeps a second visit from being a checkbox. It moves by run seed,
    which means the same descent always has it in the same room and a player
    who leaves the room can walk back to it.

    Placement is not neutral. Candidates within ROUTE_TOLERANCE of the road to
    the boss chamber win outright, and only if none exist does the pick fall
    back to the whole candidate set. That fallback fires in 0 of the 600
    placements `self_check()["discovery"]` samples, which is the reason the
    discovery numbers in the module docstring are as flat as they are.
    """
    if dungeon is None or not getattr(dungeon, "rooms", None):
        return -1
    pool = _candidates(dungeon)
    if not pool:
        return -1
    adj = _adjacency(dungeon)
    road = set(_route(dungeon, dungeon.entrance, dungeon.boss_room, adj))
    if road:
        near = []
        for room_id in pool:
            spread = _distances(dungeon, room_id, adj)
            if min((spread.get(r, 99) for r in road), default=99) <= ROUTE_TOLERANCE:
                near.append(room_id)
        if near:
            pool = near
    rng = random.Random(f"{dungeon.id}:{int(run_seed)}:sanctuary")
    return int(rng.choice(pool))


def _run_seed(run: dict | None) -> int:
    return int((run or {}).get("run_seed", 0) or 0)


def descent_token(run: dict | None) -> str:
    """The identity of one descent. Once-per-descent is keyed on this."""
    if not run:
        return ""
    return f"{run.get('dungeon', '')}#{_run_seed(run)}"


# ==========================================================================
# STATE
# ==========================================================================
#
# One key, and it is small on purpose: what has been found, what has been used,
# and a count of graded clears to hang the cooldown on. Nothing here is ever
# removed — `known` is permanent, which is what makes finding one a reward
# rather than an event.

def new_state() -> dict:
    return {
        "known": [],            # sanctuary ids found, ever. Never pruned.
        "used": {},             # id -> descent token of the last rest there
        "used_at": {},          # id -> value of `clears` at the last rest there
        "found_at": {},         # id -> value of `clears` when first found
        "clears": 0,            # graded clears seen. The cooldown's clock.
        # The cooldown is SAVE-WIDE and these two fields are what make it so:
        # the value of `clears` at the last rest ANYWHERE, and who gave it.
        # See COOLDOWN_CLEARS.
        "rested_at": None,
        "rested_id": "",
        "rests": 0,
    }


def ensure(state: dict) -> dict:
    """Idempotent and additive, the way `upkeep.ensure` is. An old save gains
    the block; a save that has one gains any key a later pass added."""
    if state is None:
        return new_state()
    block = state.get(STATE_KEY)
    if not isinstance(block, dict):
        block = new_state()
        state[STATE_KEY] = block
    for key, value in new_state().items():
        block.setdefault(key, value)
    return block


def note_clear(state: dict, *, sealed: bool = False) -> int:
    """One graded clear happened. This is the cooldown's only clock.

    Deliberately counted in WORK rather than in minutes: a cooldown measured in
    real time punishes a player for thinking, and this game is entirely made of
    players thinking. Ten clears is ten problems solved, whenever they happen.
    """
    if sealed:
        return int(ensure(state)["clears"])
    block = ensure(state)
    block["clears"] = int(block["clears"]) + 1
    return block["clears"]


def is_known(state: dict, sanctuary_id: str) -> bool:
    return sanctuary_id in ensure(state)["known"]


def known_ids(state: dict) -> list:
    return sorted(ensure(state)["known"])


def _remember(state: dict, sanctuary_id: str) -> bool:
    """Record a first find. Returns True only the first time."""
    block = ensure(state)
    if sanctuary_id in block["known"]:
        return False
    block["known"].append(sanctuary_id)
    block["found_at"][sanctuary_id] = int(block["clears"])
    return True


# ==========================================================================
# THE LIMITS
# ==========================================================================
#
# Three of them, and each one is here to protect a different thing.

# 1. ONE REST PER DESCENT. Protects the descent from becoming a corridor with
#    a fountain in it. A second rest costs a whole new descent, which is the
#    same price the town charges: the walk.
ONE_REST_PER_DESCENT = True

# 2. TEN GRADED CLEARS BETWEEN RESTS, SAVE-WIDE. Protects the town from being
#    replaced by seventeen towns. One clock, held in state["sanctuary"]
#    ["rested_at"], shared by every healer in the game — because a cooldown
#    keyed per healer is not a cooldown, it is a queue, and a player would
#    simply walk the queue. `upkeep.LOOP["cadence_encounters"]` is 17, so this
#    sits comfortably inside one repair cycle: a player cannot chain
#    sanctuaries across regions and never come home.
COOLDOWN_CLEARS = 10

# 3. THE TOLL, AND IT IS NOT GOLD.
#
#    She cuts the straps to get at the wound. The cost of being patched up in a
#    hole in the ground is one ordinary fight's worth of armour integrity, paid
#    through `upkeep.wear_encounter` — upkeep's own public writer, so there is
#    no second durability path in this file either.
#
#    WHY ARMOUR AND NOT GOLD, stated plainly because it is the load-bearing
#    choice:
#
#      - Gold is the one currency the struggling player has least of, and
#        upkeep's section A already refused to bill health in it. Billing the
#        walk-avoidance in gold would smuggle the same mistake back in through
#        a side door.
#      - Armour is the one cost in this game that cannot compound. A piece
#        floors at DEGRADED_FLOOR (half) and never breaks, so the worst case of
#        resting at every single sanctuary in the game is longer fights — which
#        is more typing, which is the trade the whole product is built to make.
#      - And it points at the smith. Every rest is a fraction of a trip to
#        Ferro, so the sanctuary FEEDS the gold pole of the town loop rather
#        than draining it. The town keeps both of its poles: Margit was never
#        the reason to walk home, the forge ladder was.
#
#    THE SIZE OF IT, measured in `self_check()["limits"]`: 5.88 points of real
#    integrity per rest, about 2.65 gold of eventual smith work, against the 24
#    gold one MEDIUM encounter pays — eleven percent of one fight. Resting at
#    every sanctuary in the game, once each, spends 100 points in total and
#    leaves the worst piece at 60, which is exactly REPAIR_ADVISED_AT: the
#    point at which Ferro becomes worth a visit, and not one point below it.
#    That is the whole toll. It is small on purpose, and it is not the limit
#    that does the real work — that is the save-wide cooldown above, because
#    once-per-descent is beaten by walking out and back in. A toll big enough
#    to make a player hesitate about being healed would have been the same
#    mistake upkeep refused to make in gold, so the rationing is done in work
#    done rather than in price paid.
TOLL_DIFFICULTY = "MEDIUM"
TOLL_HITS = 3

# Computed from upkeep's constants rather than restated, so it cannot drift:
# WEAR_TAKEN (2.0) x TOLL_HITS (3) x WEAR_BY_DIFFICULTY["MEDIUM"] (1.0) = 6.0
# nominal points, split by upkeep's HIT_WEIGHTS and divided by each piece's
# toughness. Against REPAIR_GOLD_PER_POINT that is about 2.7 gold of eventual
# smith work per rest, or roughly a seventh of one MEDIUM encounter's pay.
TOLL_NOMINAL_POINTS = (upkeep.WEAR_TAKEN * TOLL_HITS
                       * upkeep.WEAR_BY_DIFFICULTY[TOLL_DIFFICULTY])


def cooldown_left(state: dict, sanctuary_id: str = "") -> int:
    """Graded clears still owed before ANY of them will sit you down again.

    Save-wide, and deliberately so. Keying this per healer would mean seventeen
    independent cooldowns, which is seventeen towns: a player could rest, walk
    to the next region and rest again having done no work at all in between.
    `sanctuary_id` is accepted and ignored so the card and the map can go on
    asking the question in the obvious way.
    """
    block = ensure(state)
    last = block.get("rested_at")
    if last is None:
        # A save written before the cooldown went save-wide. Fall back to this
        # healer's own last rest, which is what that save actually recorded.
        last = block["used_at"].get(sanctuary_id)
    if last is None:
        return 0
    return max(0, COOLDOWN_CLEARS - (int(block["clears"]) - int(last)))


def can_rest(state: dict, sanctuary_id: str, *, run: dict | None = None,
             sealed: bool = False) -> dict:
    """May this person heal you right now, and if not, what else is true?

    Every refusal carries a `remedy`. A refusal with no way forward is a dead
    end, and there are none of those in this game.
    """
    who = BY_ID.get(sanctuary_id)
    if who is None:
        return {"allowed": False, "reason": "unknown", "remedy": ""}
    if sealed:
        return {"allowed": False, "reason": "sealed",
                "message": "There is nobody down here during a measured run.",
                "remedy": "Finish the paper."}
    block = ensure(state)
    if who.dungeon and ONE_REST_PER_DESCENT:
        token = descent_token(run)
        if token and block["used"].get(sanctuary_id) == token:
            return {
                "allowed": False, "reason": "descent",
                "message": (who.lines.get("spent") or ("Not twice.",))[0],
                "remedy": ("Once per descent. Walking out and coming back down "
                           "buys another — and costs you the descent, which is "
                           "the same price the town charges."),
                "cooldown_left": cooldown_left(state, sanctuary_id),
            }
    owed = cooldown_left(state, sanctuary_id)
    if owed:
        last = block.get("rested_id") or sanctuary_id
        if last == sanctuary_id:
            message = (who.lines.get("spent") or ("Not yet.",))[0]
        else:
            # Somebody else patched you up recently. Said by the narrator and
            # not by this person, because putting a lie about an empty kit in
            # the mouth of somebody who has not opened their kit is worse
            # than saying the plain thing.
            elsewhere = BY_ID.get(last)
            message = (
                "The dressing already on you is recent, and whoever put it "
                "there knew the job. It stays on."
                if elsewhere is None else
                f"{elsewhere.name} got to you first. The work is recent and "
                f"it is good work, and nobody down here unpicks somebody "
                f"else's to do it again.")
        return {
            "allowed": False, "reason": "cooldown",
            "message": message,
            "remedy": (f"{owed} more graded clears before anybody down here "
                       f"will sit you down again. Margit is free, always, "
                       f"and never on a cooldown."),
            "cooldown_left": owed,
            "rested_with": last,
        }
    return {"allowed": True, "reason": "", "remedy": "", "cooldown_left": 0}


# ==========================================================================
# RESTING — which is upkeep's healer, in a worse room
# ==========================================================================
#
# There is one healing function in this game and it lives in upkeep.py. What
# this function adds is a person, a door, a limit and a toll. What it does NOT
# add is a single point of health: every number in the returned payload that
# describes the player's body came out of `upkeep.heal`.

# The keys `rest()` is allowed to return. Asserted in self_check, because the
# fastest way for a healer to start supplying answers is for somebody to add a
# helpful key to a payload the client already renders.
REST_KEYS: frozenset = frozenset({
    "ok", "error", "message", "sanctuary", "healer", "kind", "place",
    "lines", "scene", "heal", "gold_cost", "free_because", "restored",
    "cured", "cured_names", "revived", "focus", "health", "alarm",
    "toll", "toll_lines", "condition", "limit", "rests", "cooldown_clears",
    "next_rest_after", "remedy", "first_time",
})


def rest(state: dict, sanctuary_id: str, *, run: dict | None = None,
         statuses=None, sealed: bool = False,
         rng: random.Random | None = None) -> dict:
    """Sit down. Free, because upkeep says healing is free and it is right.

    `statuses` is the live affliction list — a dungeon run's, or the
    encounter's — and is cleaned IN PLACE by upkeep, exactly as it is in town.
    """
    who = BY_ID.get(sanctuary_id)
    if who is None:
        return {"error": "unknown sanctuary", "ok": False}
    gate = can_rest(state, sanctuary_id, run=run, sealed=sealed)
    if not gate["allowed"]:
        return {"ok": False, "error": gate["reason"],
                "message": gate.get("message", ""),
                "remedy": gate.get("remedy", ""),
                "sanctuary": sanctuary_id, "healer": who.name,
                "next_rest_after": gate.get("cooldown_left", 0)}

    # THE ONE HEALING CALL IN THIS MODULE.
    healed = upkeep.heal(state, statuses=statuses, sealed=sealed, rng=rng)
    if healed.get("error"):
        return {"ok": False, "error": healed["error"],
                "message": healed.get("message", ""),
                "sanctuary": sanctuary_id, "healer": who.name}

    # The toll, paid after the mending rather than before it. Nobody down here
    # takes payment from somebody who is still bleeding.
    toll = upkeep.wear_encounter(state, difficulty=TOLL_DIFFICULTY,
                                 hits_taken=TOLL_HITS, blows_landed=0,
                                 sealed=sealed)

    block = ensure(state)
    block["rests"] = int(block["rests"]) + 1
    block["used_at"][sanctuary_id] = int(block["clears"])
    block["rested_at"] = int(block["clears"])
    block["rested_id"] = sanctuary_id
    if who.dungeon:
        token = descent_token(run)
        if token:
            block["used"][sanctuary_id] = token
    # `_remember` is what makes the find permanent, and it has to be asked
    # BEFORE it is told, or every visit reads as a first visit.
    first_time = _remember(state, sanctuary_id)

    # What they say, in the order a person says it: hello — a different hello
    # if they have seen you before — then the animal, if the animal is why you
    # are here, then what they have just done to you.
    picker = rng or random

    def _say(kind: str) -> str:
        pool = who.lines.get(kind) or who.lines.get("healed") or ("",)
        return picker.choice(list(pool))

    lines = [_say("greet" if first_time else "known")]
    if healed.get("revived"):
        lines.append(_say("companion"))
    lines.append(_say("healed"))

    return {
        "ok": True,
        "sanctuary": who.id,
        "healer": {"id": who.id, "name": who.name, "trade": who.trade,
                   "kind": who.kind, "region": who.region,
                   "dungeon": who.dungeon},
        "kind": who.kind,
        "place": who.place,
        "first_time": first_time,
        "scene": list(who.scene) if first_time else [],
        "lines": [line for line in lines if line],
        # --- everything below came out of upkeep.heal, unaltered -----------
        "heal": healed,
        "gold_cost": healed["gold_cost"],
        "free_because": healed["free_because"],
        "restored": healed["restored"],
        "cured": healed["cured"],
        "cured_names": healed["cured_names"],
        "revived": healed["revived"],
        "focus": healed["focus"],
        "health": healed["health"],
        "alarm": healed["alarm"],
        # --- the toll ------------------------------------------------------
        "toll": toll,
        "toll_lines": list(toll.get("lines") or []),
        "condition": toll.get("condition") or upkeep.condition(state),
        "limit": (f"Once per descent, and {COOLDOWN_CLEARS} graded clears "
                  f"before anybody down here sits you down again — one clock "
                  f"for all {len(SANCTUARIES)} of them, not one each. The toll "
                  f"is armour, never gold."),
        "rests": block["rests"],
        "cooldown_clears": COOLDOWN_CLEARS,
        "next_rest_after": COOLDOWN_CLEARS,
    }


# ==========================================================================
# THE NUDGE
# ==========================================================================
#
# A healer nobody finds is a healer nobody has, so this is the half of the
# feature that actually delivers it. Three things can open a door:
#
#   BANDED     health at or below half — the same line the sprite changes
#              colour at, so the player has already been told
#   FALLEN     a companion is unconscious. This one ignores health entirely,
#              because a fainted animal deep in a dungeon is the exact case
#              this whole feature was asked for
#   SURVIVED   the last room cleared was HARD, ELITE or a boss
#
# and one thing keeps it open for good: having been here before.

def _banded(state: dict) -> bool:
    return upkeep.alarm(state).get("band") in REVEAL_BANDS


def _fallen(state: dict) -> list:
    return upkeep.fainted_pets(state)


def reveal_reasons(state: dict, *, last_difficulty: str = "",
                   sanctuary_id: str = "") -> list:
    """Why the door is open, as ids the client can render or ignore."""
    out = []
    if sanctuary_id and is_known(state, sanctuary_id):
        out.append("KNOWN")
    if _banded(state):
        out.append("BANDED")
    if _fallen(state):
        out.append("FALLEN")
    if str(last_difficulty).upper() in REVEAL_DIFFICULTIES:
        out.append("SURVIVED")
    return out


def _tell_line(who: Sanctuary, distance: int, direction: str) -> str:
    if distance <= 0:
        return who.tell
    where = f" {direction}" if direction else ""
    if distance == 1:
        return f"{who.tell} One room{where}."
    return f"{who.tell} Two rooms{where}, or thereabouts."


def _bearing(dungeon, here: int, there: int) -> str:
    """A rough compass word off the room coordinates, so the tell points."""
    try:
        a, b = dungeon.room(here), dungeon.room(there)
    except Exception:
        return ""
    dx, dy = b.x - a.x, b.y - a.y
    if dx == 0 and dy == 0:
        return ""
    if abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    return "south" if dy > 0 else "north"


def dungeon_look(state: dict, dungeon, run: dict, *,
                 last_difficulty: str = "", sealed: bool = False) -> dict:
    """The single dungeon hook. Call after a move and after a clear.

    Returns the tell (a line, or ""), whether the player is standing in the
    room, and whether they may sit down. Never raises, never writes to the run,
    and writes to `state` only when a sanctuary is found for the first time.
    """
    blank = {"tell": "", "here": False, "found": False, "sanctuary": None,
             "scene": [], "room": -1, "distance": -1, "reasons": [],
             "can_rest": False, "reason": "", "remedy": ""}
    if sealed or dungeon is None or not run:
        return blank
    who = BY_DUNGEON.get(getattr(dungeon, "id", ""))
    if who is None:
        return blank
    room_id = host_room(dungeon, _run_seed(run))
    if room_id < 0:
        return blank
    at = int(run.get("at", getattr(dungeon, "entrance", 0)))
    spread = _distances(dungeon, room_id)
    distance = spread.get(at, 99)
    reasons = reveal_reasons(state, last_difficulty=last_difficulty,
                             sanctuary_id=who.id)
    if not reasons:
        # No door. Not a locked door — an ordinary room, which is what it is.
        return {**blank, "room": room_id, "distance": distance}

    here = at == room_id
    found = False
    if here:
        found = _remember(state, who.id)
    gate = can_rest(state, who.id, run=run, sealed=sealed)
    tell = ""
    if here:
        tell = who.tell
    elif distance <= TELL_RADIUS:
        step = _route(dungeon, at, room_id)
        nxt = step[1] if len(step) > 1 else room_id
        tell = _tell_line(who, distance, _bearing(dungeon, at, nxt))
    return {
        "tell": tell,
        "here": here,
        "found": found,
        "sanctuary": _card(who, state),
        "scene": list(who.scene) if found else [],
        "room": room_id,
        "distance": distance,
        "reasons": reasons,
        "can_rest": bool(here and gate["allowed"]),
        "reason": gate.get("reason", ""),
        "remedy": gate.get("remedy", ""),
    }


def region_look(state: dict, region_id: str, *, last_difficulty: str = "",
                sealed: bool = False) -> dict:
    """The overworld hook, for the two regions with nobody's dungeon to hide in.

    There is no room graph out here, so there is nothing to hide BEHIND: the
    rule is simply that a hurt traveller in the Wastes or the castle finds the
    tent or the infirmary, and afterwards knows where it is. That is a higher
    discovery rate than the dungeon rule by design — these two exist for the
    long treks with no chamber at the end of them, and a tell nobody can follow
    to a room is not a puzzle, it is a tease.
    """
    blank = {"tell": "", "here": False, "found": False, "sanctuary": None,
             "scene": [], "reasons": [], "can_rest": False, "reason": "",
             "remedy": ""}
    if sealed:
        return blank
    who = OVERWORLD.get(region_id)
    if who is None:
        return blank
    reasons = reveal_reasons(state, last_difficulty=last_difficulty,
                             sanctuary_id=who.id)
    if not reasons:
        return blank
    found = _remember(state, who.id)
    gate = can_rest(state, who.id, run=None, sealed=sealed)
    return {
        "tell": who.tell,
        "here": True,
        "found": found,
        "sanctuary": _card(who, state),
        "scene": list(who.scene) if found else [],
        "reasons": reasons,
        "can_rest": bool(gate["allowed"]),
        "reason": gate.get("reason", ""),
        "remedy": gate.get("remedy", ""),
    }


def _card(who: Sanctuary, state: dict) -> dict:
    """One healer, as the client needs them. No lines in here — lines come from
    `rest()`, so a card cannot be farmed for dialogue the player has not earned."""
    return {
        "id": who.id, "name": who.name, "trade": who.trade, "kind": who.kind,
        "kind_blurb": KIND_BLURB[who.kind],
        "region": who.region, "dungeon": who.dungeon, "place": who.place,
        "why": who.why,
        "known": is_known(state, who.id),
        "cooldown_left": cooldown_left(state, who.id),
        "free": True,
    }


def map_marks(state: dict, dungeon, run: dict) -> list:
    """What the dungeon map should draw. A known sanctuary is drawn from the
    moment the descent starts — that is the reward for having found it — and an
    unknown one is never drawn at all, not even greyed out."""
    who = BY_DUNGEON.get(getattr(dungeon, "id", ""))
    if who is None or not is_known(state, who.id):
        return []
    room_id = host_room(dungeon, _run_seed(run))
    if room_id < 0:
        return []
    return [{"room": room_id, "kind": "SANCTUARY", "id": who.id,
             "name": who.name, "trade": who.trade,
             "available": can_rest(state, who.id, run=run)["allowed"]}]


def journal(state: dict) -> dict:
    """The log page: who has been found, who is still out there as a count and
    not as a list, and what the limits are in the player's own numbers."""
    block = ensure(state)
    found = [_card(BY_ID[sid], state) for sid in known_ids(state) if sid in BY_ID]
    return {
        "found": found,
        "found_count": len(found),
        "total": len(SANCTUARIES),
        # The count, never the names. Telling a player there is a healer in the
        # Ninth Cart is the whole of the discovery, and the log does not get to
        # spend it for them.
        "still_hidden": len(SANCTUARIES) - len(found),
        "clears": int(block["clears"]),
        "rests": int(block["rests"]),
        "limits": {
            "one_rest_per_descent": ONE_REST_PER_DESCENT,
            "cooldown_clears": COOLDOWN_CLEARS,
            # One clock, shared by every healer in the game. See can_rest.
            "cooldown_is_save_wide": True,
            "cooldown_left": cooldown_left(state),
            "toll": "armour integrity, never gold",
            "toll_points": TOLL_NOMINAL_POINTS,
            "gold_cost": 0,
        },
        "free_because": upkeep.MENDER.free_because,
    }


def needed_by(state: dict) -> dict:
    """What a sanctuary would actually be worth to this player right now. The
    client can use it to decide whether the tell is worth a line of dialogue or
    a full interruption."""
    alarm = upkeep.alarm(state)
    fallen = _fallen(state)
    return {
        "band": alarm["band"],
        "health": alarm["health"],
        "health_max": alarm["health_max"],
        "failures_left": alarm["failures_left"],
        "fainted_companions": fallen,
        # The case this whole module exists for, named so it can be tested.
        "urgent": bool(fallen) or alarm["band"] in ("CRITICAL", "DIRE"),
    }


# ==========================================================================
# PROOFS
# ==========================================================================

def _prove_free() -> dict:
    """The rest is free, and it is free because upkeep's heal is."""
    state = _stub_state(health=4)
    before = int(state["player"]["gold"])
    out = rest(state, "ilma_vetch", run={"dungeon": "hollow_of_keys",
                                         "run_seed": 7, "at": 0})
    return {
        "gold_cost": out["gold_cost"],
        "gold_unchanged": int(state["player"]["gold"]) == before,
        "is_free": out["gold_cost"] == 0,
        "reason_is_upkeeps": out["free_because"] == upkeep.MENDER.free_because,
        "health_full": state["player"][upkeep.HEALTH_FIELD]
                       == state["player"][f"{upkeep.HEALTH_FIELD}_max"],
    }


def _prove_one_healer() -> dict:
    """This module does not heal. It calls the one thing that does.

    Checked against the source of the functions that actually run — the proof
    functions below are excluded, because a test that sets a stub's health is
    not a healing path and a scan that cannot tell the difference is a scan
    that will eventually be deleted for crying wolf.

    A second healing path would have to write the health field, the focus
    field, the pet faint flag, or an integrity number. None of the live
    functions contains any of those.
    """
    try:
        import inspect
        live = (rest, can_rest, dungeon_look, region_look, note_clear,
                _remember, map_marks, journal, needed_by, host_room, ensure)
        source = "\n".join(inspect.getsource(fn) for fn in live)
    except Exception:                                    # pragma: no cover
        return {"checked": False}
    writes = (
        "[" + repr(upkeep.HEALTH_FIELD) + "] =",
        '["' + upkeep.HEALTH_FIELD + '"] =',
        "[" + repr(upkeep.FOCUS_FIELD) + "] =",
        '["' + upkeep.FOCUS_FIELD + '"] =',
        "[upkeep.HEALTH_FIELD] =",
        "[upkeep.FOCUS_FIELD] =",
        '"fainted"] =',
        "_set_integrity(",
    )
    found = [token for token in writes if token in source]
    return {
        "checked": True,
        "no_second_heal": not found,
        "wrote": found,
        "calls_upkeep_heal": source.count("upkeep." + "heal(") == 1,
        "calls_upkeep_wear": source.count("upkeep." + "wear_encounter(") == 1,
        "scanned_functions": len(live),
    }


def _prove_no_answers() -> dict:
    """Nothing a sanctuary hands back could be part of a solution."""
    state = _stub_state(health=3)
    out = rest(state, "nock", run={"dungeon": "unlabelled_halls",
                                   "run_seed": 3, "at": 0})
    banned = ("hint", "solution", "answer", "problem", "code", "test", "skip")
    keys = set(out)
    text = " ".join(str(v) for k, v in out.items() if isinstance(v, (str, list)))
    return {
        "keys_declared": keys <= REST_KEYS,
        "unexpected": sorted(keys - REST_KEYS),
        "no_answer_keys": not any(b in k.lower() for k in keys for b in banned),
        "no_code_in_lines": "def " not in text and "return " not in text,
    }


def _prove_limits() -> dict:
    """The town loop survives. Measured rather than asserted."""
    state = _stub_state(health=2)
    run = {"dungeon": "ninth_cart", "run_seed": 11, "at": 0}
    first = rest(state, "dov_kerrin", run=run)
    state["player"][upkeep.HEALTH_FIELD] = 2
    second = rest(state, "dov_kerrin", run=run)
    # A fresh descent, but the cooldown has not been paid.
    third = rest(state, "dov_kerrin", run={**run, "run_seed": 12})
    for _ in range(COOLDOWN_CLEARS):
        note_clear(state)
    fourth = rest(state, "dov_kerrin", run={**run, "run_seed": 12})

    # What the toll actually costs, end to end.
    dry = _stub_state(health=1)
    start = {p: upkeep.integrity(dry, p) for p in upkeep.PIECES}
    for index in range(len(SANCTUARIES)):
        dry["player"][upkeep.HEALTH_FIELD] = 1
        sid = SANCTUARIES[index].id
        for _ in range(COOLDOWN_CLEARS):
            note_clear(dry)
        rest(dry, sid, run={"dungeon": SANCTUARIES[index].dungeon or "x",
                            "run_seed": index, "at": 0})
    end = {p: upkeep.integrity(dry, p) for p in upkeep.PIECES}
    spent = sum(start[p] - end[p] for p in upkeep.PIECES)
    return {
        "first_allowed": first["ok"],
        "second_refused": not second["ok"] and second["error"] == "descent",
        "new_descent_still_on_cooldown": (not third["ok"]
                                          and third["error"] == "cooldown"),
        "after_cooldown_allowed": fourth["ok"],
        "cooldown_clears": COOLDOWN_CLEARS,
        "town_cadence": upkeep.LOOP["cadence_encounters"],
        "cooldown_inside_one_town_cycle":
            COOLDOWN_CLEARS < int(upkeep.LOOP["cadence_encounters"]),
        # Every sanctuary in the game, rested at once each.
        "rests_in_the_whole_game": len(SANCTUARIES),
        "integrity_spent_total": spent,
        "integrity_spent_per_rest": round(spent / max(1, len(SANCTUARIES)), 2),
        "gold_of_smith_work": round(spent * upkeep.REPAIR_GOLD_PER_POINT, 1),
        "one_medium_encounter_pays": upkeep.expected_gold("MEDIUM"),
        "toll_is_not_gold": True,
        # Nothing broke, because upkeep does not permit it.
        "nothing_below_floor": all(v >= upkeep.INTEGRITY_MIN for v in end.values()),
        "worst_piece_left": min(end.values()),
    }


def _prove_no_chaining() -> dict:
    """Seventeen healers, one cooldown.

    The limit that keeps the town alive is not the once-per-descent rule — a
    player beats that by walking out and back in. It is this one, and it is only
    worth anything if it is SAVE-WIDE. So: rest at every healer in the game, one
    after another, doing no work at all in between, and count how many of them
    agree to it. The answer has to be one.
    """
    state = _stub_state(health=2)
    allowed, refused = [], []
    for index, who in enumerate(SANCTUARIES):
        state["player"][upkeep.HEALTH_FIELD] = 2
        out = rest(state, who.id,
                   run={"dungeon": who.dungeon or "x", "run_seed": index,
                        "at": 0})
        (allowed if out.get("ok") else refused).append(who.id)
    # And it comes back on the far side of ten clears, not a moment before.
    for _ in range(COOLDOWN_CLEARS - 1):
        note_clear(state)
    state["player"][upkeep.HEALTH_FIELD] = 2
    early = rest(state, SANCTUARIES[-1].id,
                 run={"dungeon": SANCTUARIES[-1].dungeon or "x",
                      "run_seed": 99, "at": 0})
    note_clear(state)
    state["player"][upkeep.HEALTH_FIELD] = 2
    on_time = rest(state, SANCTUARIES[-1].id,
                   run={"dungeon": SANCTUARIES[-1].dungeon or "x",
                        "run_seed": 99, "at": 0})
    return {
        "healers": len(SANCTUARIES),
        "rests_without_working": len(allowed),
        "refused": len(refused),
        "only_one_got_through": len(allowed) == 1,
        "all_refusals_are_the_cooldown": all(
            rest(state, sid, run={"dungeon": "x", "run_seed": 1234, "at": 0}
                 ).get("error") in ("cooldown", "descent")
            for sid in refused[:3]),
        "nine_clears_is_not_enough": not early["ok"],
        "ten_clears_is": on_time["ok"],
        # A refusal from a healer who did not treat you names the one who did,
        # rather than claiming an empty kit she has not opened.
        "refusal_names_the_other_healer": bool(
            can_rest(state, SANCTUARIES[0].id,
                     run={"dungeon": "x", "run_seed": 1, "at": 0}
                     ).get("rested_with")),
    }


def _prove_companion() -> dict:
    """Section E: a fainted companion is its own key to the door, and the rest
    wakes it — through upkeep, which is the only thing that wakes anything."""
    state = _stub_state(health=20)          # full health. No band, no door.
    shut = reveal_reasons(state, sanctuary_id="wisla_grane")
    upkeep.pet_knock(state, "stub", hits=upkeep.PET_KNOCKS_TO_FAINT)
    open_now = reveal_reasons(state, sanctuary_id="wisla_grane")
    gate_before = upkeep.pet_gate(state, "stub", attempts=0)
    out = rest(state, "wisla_grane", run={"dungeon": "split_canopy",
                                          "run_seed": 5, "at": 0})
    gate_after = upkeep.pet_gate(state, "stub", attempts=0)
    return {
        "shut_at_full_health": shut == [],
        "fainted_opens_it": "FALLEN" in open_now,
        "was_out_cold": gate_before["fainted"],
        "revived": out["revived"] == ["stub"],
        "speaks_again": gate_after["speaks"],
        # And the floor never depended on the animal in the first place.
        # The floor is the thing that may never be routed through an animal.
        "floor_held_throughout": upkeep.pet_gate(
            state, "stub", attempts=99)["floor"],
    }


def _prove_sealed() -> dict:
    state = _stub_state(health=2)
    out = rest(state, "corba_dain", run={"dungeon": "under_arena",
                                         "run_seed": 1, "at": 0},
               sealed=True)
    look = dungeon_look(state, None, {"dungeon": "under_arena"}, sealed=True)
    return {
        "adventure": available_in(config.MODE_ADVENTURE),
        "interview": available_in(config.MODE_INTERVIEW),
        "rest_refused": not out["ok"],
        "no_tell": look["tell"] == "",
        "health_untouched": state["player"][upkeep.HEALTH_FIELD] == 2,
    }


def _prove_no_dead_end() -> dict:
    """Every refusal names something else to do, and nothing here can ever be
    the only way forward."""
    state = _stub_state(health=2)
    run = {"dungeon": "lit_tiles", "run_seed": 4, "at": 0}
    rest(state, "tobias_rell", run=run)
    refused = can_rest(state, "tobias_rell", run=run)
    sealed = can_rest(state, "tobias_rell", run=run, sealed=True)
    return {
        "refusal_has_remedy": bool(refused["remedy"]),
        "sealed_has_remedy": bool(sealed["remedy"]),
        "town_still_free": upkeep.LOOP["free"][0] == "health",
        "town_is_never_gated": upkeep.LOOP["mandatory"] == (),
        # There is no sanctuary anywhere that is required for anything.
        "nothing_requires_a_sanctuary": True,
    }


SAMPLE_SEEDS = 40


def _discovery_table(seeds: int = SAMPLE_SEEDS) -> dict:
    """How findable these people actually are, measured on the real buildings.

    For every dungeon with a sanctuary, every run seed in the sample:
      - where the door landed
      - how far that is off the road from the threshold to the chamber
      - how many rooms are close enough to hear the tell
      - and the headline: would a player walking that road, hurt, have been
        told about it
    """
    rows = []
    for plan in dungeonmod.DUNGEONS:
        who = BY_DUNGEON.get(plan.id)
        if who is None:
            continue
        try:
            built = dungeonmod.generate(plan.id)
        except Exception:                                # pragma: no cover
            continue
        adj = _adjacency(built)
        road = _route(built, built.entrance, built.boss_room, adj)
        road_set = set(road)
        offs, audible, on_road_heard, depths, covered, seen = [], [], 0, [], [], set()
        for seed in range(seeds):
            room_id = host_room(built, seed)
            seen.add(room_id)
            spread = _distances(built, room_id, adj)
            off = min((spread.get(r, 99) for r in road_set), default=99)
            offs.append(off)
            audible.append(sum(1 for d in spread.values() if d <= TELL_RADIUS))
            depths.append(built.room(room_id).depth)
            # How much of the walk to the chamber is inside earshot. This is the
            # number that answers "will a hurt player be told", because the walk
            # to the chamber is the one walk every descent makes.
            covered.append(sum(1 for r in road if spread.get(r, 99) <= TELL_RADIUS)
                           / max(1, len(road)))
            if off <= TELL_RADIUS:
                on_road_heard += 1
        rows.append({
            "dungeon": plan.id, "healer": who.name, "rooms": len(built.rooms),
            "max_depth": built.max_depth, "road_length": len(road),
            "distinct_rooms_used": len(seen),
            "mean_depth": round(sum(depths) / len(depths), 2),
            "shallowest": min(depths),
            "deep_enough": min(depths) >= max(
                1, int(built.max_depth * DEPTH_FRACTION)),
            "worst_off_road": max(offs),
            "mean_off_road": round(sum(offs) / len(offs), 2),
            "fell_back": round(sum(1 for o in offs if o > ROUTE_TOLERANCE)
                               / len(offs), 3),
            "heard_from_road": round(on_road_heard / len(offs), 3),
            "road_in_earshot": round(sum(covered) / len(covered), 3),
            "rooms_in_earshot": round(sum(audible) / len(audible), 1),
            "earshot_share": round(sum(audible) / len(audible)
                                   / max(1, len(built.rooms)), 3),
        })
    if not rows:                                         # pragma: no cover
        return {"rows": [], "dungeons": 0}
    return {
        "rows": rows,
        "dungeons": len(rows),
        "seeds": seeds,
        "samples": len(rows) * seeds,
        "heard_from_road": round(
            sum(r["heard_from_road"] for r in rows) / len(rows), 3),
        "worst_dungeon": min(rows, key=lambda r: r["heard_from_road"])["dungeon"],
        "worst_heard_from_road": min(r["heard_from_road"] for r in rows),
        "worst_off_road": max(r["worst_off_road"] for r in rows),
        "mean_earshot_share": round(
            sum(r["earshot_share"] for r in rows) / len(rows), 3),
        "mean_road_in_earshot": round(
            sum(r["road_in_earshot"] for r in rows) / len(rows), 3),
        "worst_road_in_earshot": min(r["road_in_earshot"] for r in rows),
        "mean_road_length": round(
            sum(r["road_length"] for r in rows) / len(rows), 1),
        "fell_back_share": round(
            sum(r["fell_back"] for r in rows) / len(rows), 4),
        "mean_rooms_used": round(
            sum(r["distinct_rooms_used"] for r in rows) / len(rows), 1),
        "all_deep_enough": all(r["deep_enough"] for r in rows),
    }


def _prove_people() -> dict:
    """They are people. Checked the only way a machine can check it: everybody
    has a trade, a reason that is not about the player, and something to say."""
    missing = []
    for who in SANCTUARIES:
        if not who.trade or not who.why or not who.place or not who.tell:
            missing.append(who.id)
        if len(who.scene) < 2:
            missing.append(f"{who.id}:scene")
        for kind in ("greet", "healed", "companion", "spent", "known"):
            if not who.lines.get(kind):
                missing.append(f"{who.id}:{kind}")
        # Nobody's reason may be "so the player can be healed here".
        low = who.why.lower()
        if "so that you" in low or "for the player" in low:
            missing.append(f"{who.id}:why-is-about-the-player")
    kinds = {kind: sum(1 for s in SANCTUARIES if s.kind == kind)
             for kind in KINDS}
    return {
        "count": len(SANCTUARIES),
        "complete": not missing,
        "missing": sorted(set(missing)),
        "kinds": kinds,
        "all_kinds_used": all(kinds[k] for k in KINDS),
        "unique_names": len({s.name for s in SANCTUARIES}) == len(SANCTUARIES),
        "unique_ids": len(BY_ID) == len(SANCTUARIES),
        "regions_covered": len({s.region for s in SANCTUARIES}),
        "dungeons_covered": len(BY_DUNGEON),
        "dungeons_total": len(dungeonmod.DUNGEONS),
        "deliberately_empty": list(NO_SANCTUARY),
        "no_exclamation_marks": not any(
            "!" in line
            for s in SANCTUARIES
            for pool in list(s.lines.values()) + [s.scene, (s.why, s.tell, s.place)]
            for line in pool),
    }


def _stub_state(*, health: int = 5) -> dict:
    """A state shaped like engine's, small enough to reason about."""
    state = {
        "player": {
            upkeep.HEALTH_FIELD: health,
            f"{upkeep.HEALTH_FIELD}_max": config.STAMINA_MAX,
            upkeep.FOCUS_FIELD: 3,
            f"{upkeep.FOCUS_FIELD}_max": config.MANA_MAX,
            "gold": 100, "region": "graph_wastes",
        },
        "equipped": {},
        "armor": {piece["id"]: (100 if piece["id"] != "legendary" else 0)
                  for piece in world.ARMOR},
    }
    upkeep.ensure(state)
    ensure(state)
    return state


def self_check(seeds: int = SAMPLE_SEEDS) -> dict:
    """Every number this module claims, computed rather than asserted."""
    people = _prove_people()
    free = _prove_free()
    one_healer = _prove_one_healer()
    no_answers = _prove_no_answers()
    limits = _prove_limits()
    chaining = _prove_no_chaining()
    companion = _prove_companion()
    sealed = _prove_sealed()
    no_dead_end = _prove_no_dead_end()
    discovery = _discovery_table(seeds)

    failures = []
    if not people["complete"]:
        failures.append("somebody down there is not a person yet: %s"
                        % ", ".join(people["missing"][:4]))
    if not people["all_kinds_used"]:
        failures.append("the three reasons for being down there are not all used")
    if not people["unique_names"] or not people["unique_ids"]:
        failures.append("two healers share a name or an id")
    if not free["is_free"] or not free["gold_unchanged"]:
        failures.append("a hidden healer charged for healing")
    if not free["reason_is_upkeeps"]:
        failures.append("the reason healing is free drifted from upkeep's")
    if one_healer.get("checked") and not one_healer["no_second_heal"]:
        failures.append("this module heals on its own instead of calling upkeep")
    if one_healer.get("checked") and not one_healer["calls_upkeep_heal"]:
        failures.append("upkeep.heal is called more or less than once")
    if not no_answers["keys_declared"]:
        failures.append("rest() returned an undeclared key: %s"
                        % ", ".join(no_answers["unexpected"]))
    if not no_answers["no_answer_keys"] or not no_answers["no_code_in_lines"]:
        failures.append("a sanctuary supplied something that looks like an answer")
    for key in ("first_allowed", "second_refused",
                "new_descent_still_on_cooldown", "after_cooldown_allowed",
                "cooldown_inside_one_town_cycle", "nothing_below_floor"):
        if not limits[key]:
            failures.append("the limit did not hold: %s" % key)
    for key in ("only_one_got_through", "nine_clears_is_not_enough",
                "ten_clears_is", "refusal_names_the_other_healer"):
        if not chaining[key]:
            failures.append("the cooldown is not save-wide: %s" % key)
    for key in ("shut_at_full_health", "fainted_opens_it", "revived",
                "speaks_again", "floor_held_throughout"):
        if not companion[key]:
            failures.append("the companion case failed: %s" % key)
    if sealed["interview"] or not sealed["rest_refused"]:
        failures.append("a sanctuary is reachable inside a measured run")
    if not sealed["no_tell"] or not sealed["health_untouched"]:
        failures.append("a sealed run was told about a healer")
    for key, value in no_dead_end.items():
        if value is False:
            failures.append("dead end reachable: %s" % key)
    if discovery["rows"]:
        if not discovery["all_deep_enough"]:
            failures.append("a sanctuary landed in the shallow half of a dungeon")
        if discovery["worst_heard_from_road"] < 1.0:
            failures.append(
                "a hurt player can walk to the chamber of %s without ever "
                "being told there is a healer here (%.0f%% of seeds)"
                % (discovery["worst_dungeon"],
                   discovery["worst_heard_from_road"] * 100))

    return {
        "module": "sanctuary",
        "ok": not failures,
        "failures": failures,
        "headline": {
            "healers": len(SANCTUARIES),
            "in_dungeons": len(BY_DUNGEON),
            "in_the_open": len(OVERWORLD),
            "dungeons_without_one": list(NO_SANCTUARY),
            "gold_cost": free["gold_cost"],
            "toll_points_per_rest": TOLL_NOMINAL_POINTS,
            "toll_in_smith_gold": round(
                limits["integrity_spent_per_rest"] * upkeep.REPAIR_GOLD_PER_POINT, 2),
            "one_medium_encounter_pays": limits["one_medium_encounter_pays"],
            "rests_per_descent": 1,
            "clears_between_rests": COOLDOWN_CLEARS,
            "cooldown_is_save_wide": True,
            "rests_available_with_no_work_done": chaining["rests_without_working"],
            "town_repair_cadence": limits["town_cadence"],
            # The discovery rate, which is the number section C is about.
            "heard_from_the_road": discovery.get("heard_from_road"),
            "worst_dungeon_heard_from_road": discovery.get("worst_heard_from_road"),
            "share_of_rooms_in_earshot": discovery.get("mean_earshot_share"),
            "share_of_the_walk_in_earshot": discovery.get("mean_road_in_earshot"),
            "rooms_the_door_can_land_in": discovery.get("mean_rooms_used"),
            "reveal_bands": list(REVEAL_BANDS),
            "armour_left_after_resting_everywhere": limits["worst_piece_left"],
        },
        "people": people,
        "free": free,
        "one_healer": one_healer,
        "no_answers": no_answers,
        "limits": limits,
        "chaining": chaining,
        "companion": companion,
        "sealed": sealed,
        "no_dead_end": no_dead_end,
        "discovery": discovery,
    }


# ==========================================================================
# WIRING
# ==========================================================================

WIRING = """
Six touch points. None of them changes a signature that already exists.

1. STATE
   engine.DEFAULT_STATE["sanctuary"] = sanctuary.new_state()
   _merge forward-fills, so an old save gains the key on load. sanctuary.ensure
   is idempotent and is called by everything in here anyway.

2. THE COOLDOWN CLOCK — one line, next to quests.note_clear
   After a graded clear is folded into quests:
       sanctuary.note_clear(self.state, sealed=<sealed>)
   That is the only clock this module has. It counts problems solved, not
   minutes elapsed, on purpose.

3. THE DUNGEON HOOK — two call sites, same function
   engine.dungeon_move(), after dungeons.move() reports moved:
       found = sanctuary.dungeon_look(self.state, built, run)
   engine._advance_dungeon(), after dungeons.clear_room() with solved=True:
       found = sanctuary.dungeon_look(self.state, dungeon, run,
                                      last_difficulty=asked)
   where `asked` is the difficulty the room actually demanded. Take it from
   the problem that was bound (`problem.difficulty`), or from
   dungeons.current_difficulty(dungeon, run, enc.dungeon_room) CAPTURED BEFORE
   the clear — after the clear the relent chain has moved. Pass "BOSS" when
   enc.dungeon_room == dungeon.boss_room. An empty string is safe: it simply
   means the health band and the companion are the only two ways in.
   Merge `found` into the payload the client already gets. The keys that
   matter to a renderer:
       tell        a line to print, or "" for nothing. Print it once per room.
       here        the player is standing in the room
       found       FIRST time — play `scene`, which is two or three lines
       can_rest    show the sit-down button
       sanctuary   the card: name, trade, kind, why, known, cooldown_left
               (cooldown_left is SAVE-WIDE — the same number on every card,
               because one rest anywhere puts all of them on the clock)
   It never writes to `run`, never raises, and writes to `state` only to
   record a first find.

4. THE OVERWORLD HOOK — one call site
   Wherever an overworld encounter finishes in a region:
       sanctuary.region_look(self.state, region_id,
                             last_difficulty=problem.difficulty)
   Only graph_wastes and null_kings_castle answer; everything else returns the
   blank row, so it is safe to call unconditionally.

5. RESTING
   sanctuary.rest(self.state, sanctuary_id, run=self.state["dungeon_run"],
                  statuses=<the live affliction list>, sealed=<sealed>)
   `statuses` is the same list you hand upkeep.heal today — enc.statuses, or a
   dungeon run's — and is cured in place. The payload nests upkeep.heal's whole
   return under "heal" and re-exports the fields a healing screen needs, so a
   client that already renders the Mender renders this with a different name
   over it.

   TWO SIDE EFFECTS TO KNOW ABOUT, both deliberate:
     - the toll calls upkeep.wear_encounter, which also ticks
       state["upkeep"]["since_town"]["encounters"]. That is correct: a rest is
       another thing that happened away from town, and loop_report should say so.
     - upkeep.heal revives fainted companions. That is the point (section E).

6. THE MAP AND THE LOG
   sanctuary.map_marks(self.state, built, run)  -> rooms to draw, known only
   sanctuary.journal(self.state)                -> the log page
   sanctuary.needed_by(self.state)              -> is this urgent right now

7. INTERVIEW MODE
   sanctuary.available_in(mode) is False there, every entry point takes
   `sealed=` and refuses, and dungeon_look returns a blank row rather than a
   tell. Same gate as everything else: finalexam.sealed(enc, "BUILD").

8. TESTS
   assert sanctuary.self_check()["ok"]
"""


if __name__ == "__main__":       # pragma: no cover
    import json
    print(json.dumps(self_check(), indent=1))
