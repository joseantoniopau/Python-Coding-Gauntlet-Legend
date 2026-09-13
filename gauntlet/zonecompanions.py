"""The five people who walk a zone with you until the thing that owns it takes
them.

This is the DATA LAYER for docs/12-the-zone-companions.md. It holds the people,
the arc, the items they leave and every line anybody says. It renders nothing,
it generates no terrain and it owns no tiles.

Five things this module insists on.

1. IT IS NOT A NEW CAST. All five are already in `captives.CAPTIVES`, and three
   of them were there before this file existed. Thessaly Brun already taught in
   Python Village. Josa Fell already ran a lamp line and her boon already reads
   "the Caverns are lit from both ends". Hessa Dunmar already rigged spans from
   both ends at once. Halla Vane and Greave were already named in
   `quests.GIVERS` and `banter.SPEAKERS`, in the regions this file puts them in,
   with the sprites this file draws them with; promoting them cost one row each
   in captives.py and no new boss, no new key and no new rung.

2. THE ITEM IS ALWAYS WORSE THAN THE PERSON, AND THE LOSS IS NAMED. Every
   escort carries three dicts — `without`, `with_them`, `with_item` — and
   `validate()` proves the middle one beats the last one on the axis the design
   chose, or that a named capability is missing from it. A drop that quietly
   matched the person would turn the capture into an inventory update.

3. THE ITEM CANNOT BE MISSED. `advance()` grants the drop on the transition out
   of WALKING by EITHER road — taken by the boss, or freed by a player who beat
   the boss before the capture ever fired. There is no roll, no chest and
   nothing on the ground to walk back for. A zone mechanic a player can lose
   access to is a dead end, and this game's one rule is that the measurement is
   never behind a locked door.

4. THE STATE IS DERIVED, NOT MIGRATED. `state_of()` is a pure function of the
   save. It reads `cleared_bosses`, `dungeons_cleared`, `inventory`, the
   `captives` block and this module's own small latch, every one of them
   through `.get`. A save written before this file existed answers WALKING for
   everybody who is still held and FREED for everybody already carried out,
   which is exactly right, and nothing anywhere raises.

5. NOTHING HERE READS THE EXAM. This module does not import `finalexam` and
   never calls `finalexam.sealed()`. The ladder rung it needs — the
   second-to-last boss, for the Interviewer's sweep — is read off
   `world.BOSSES`, because world.py's own comment says rung N is the Nth entry
   of that list. The exam is a measurement. This is a story layer. They do not
   touch.

Wiring is at the bottom, in WIRING, and what this needs from files it does not
own is in CONTRACT.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import captives
from . import config
from . import dungeons as dungeonmod
from . import items
from . import world

# ---------------------------------------------------------------------------
# The five states
# ---------------------------------------------------------------------------
# One shape, five instances. A companion is in exactly one of these at any
# moment and `state_of()` is the only thing that decides which.
#
#   WALKING    free, in their zone, doing their verb when you are in it
#   TAKEN      the boss has them; the scene has not been settled yet
#   ITEM_HELD  the boss has them; the thing they left is in your bag
#   FREED      you beat the boss that took them and they went home
#   RETAKEN    the Interviewer collected them after the second-to-last rung
#
# TAKEN -> ITEM_HELD is the grant, and it is one transaction: the item is in
# the inventory before the scene finishes playing. See `advance()`.

WALKING = "WALKING"
TAKEN = "TAKEN"
ITEM_HELD = "ITEM_HELD"
FREED = "FREED"
RETAKEN = "RETAKEN"

STATES = (WALKING, TAKEN, ITEM_HELD, FREED, RETAKEN)

# What each state means, for a panel that wants to say it rather than switch on
# it. Prose, never logic.
STATE_LABELS = {
    WALKING: "Walking with you",
    TAKEN: "Taken",
    ITEM_HELD: "Taken. You are carrying what they left.",
    FREED: "Home, and back at work",
    RETAKEN: "Taken back, by the thing at the end of the road",
}


# ---------------------------------------------------------------------------
# The ladder, without opening the exam
# ---------------------------------------------------------------------------
# world.py states in its own comment that finalexam.BOSS_LADDER rung N is the
# Nth entry of world.BOSSES, and that appending to that list would renumber
# every crutch in the game. So the rung of a boss is its index here, this file
# does not import finalexam, and `validate()` re-proves the one rung it cares
# about rather than trusting the arithmetic.

RUNG = {boss["id"]: n for n, boss in enumerate(world.BOSSES, 1)}

# The second-to-last rung. When this falls, the Interviewer goes and collects
# everyone the player has got back. The player's words: "the last boss captures
# all of these known villagers after the second-to-last boss is defeated."
SWEEP_AFTER_BOSS = "bug_demon"

# The road Thessaly hands the Slate over on. progression.ROUTES id; the save
# records it in state["world"]["routes_walked"].
SLATE_ROUTE = "rt_waking_road"


# ---------------------------------------------------------------------------
# A zone is a cluster of regions, and it is named here and nowhere else
# ---------------------------------------------------------------------------
# Seventeen regions with seventeen mechanics is seventeen tutorials. Five zones
# carry a companion; the other nine regions keep exactly what they have — a
# captive who goes home, a boon that changes the village, and a gift — which is
# already a reward and already works.

@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    regions: tuple       # world.REGION_BY_ID ids
    element: str         # the element the zone reads as, for flavour only
    verb: str            # the one thing the player does here that they cannot
                         # do anywhere else


ZONES = (
    Zone(id="home", name="Home", element="NEUTRAL",
         regions=("python_village", "fields_of_syntax"),
         verb="read the road"),
    Zone(id="the_dark", name="The Dark", element="BRUTE",
         regions=("array_caverns",),
         verb="see"),
    Zone(id="the_snow", name="The Snow", element="COLD",
         regions=("twin_pointer_pass",),
         verb="cross"),
    Zone(id="the_green", name="The Green", element="POISON",
         regions=("stringwood_labyrinth", "recursive_forest",
                  "binary_tree_canopy"),
         verb="thin the pack"),
    Zone(id="the_fire", name="The Fire", element="FIRE",
         regions=("stack_queue_mines",),
         verb="divert the flow"),
)

ZONE_BY_ID = {zone.id: zone for zone in ZONES}
ZONE_BY_REGION = {region: zone for zone in ZONES for region in zone.regions}


# ---------------------------------------------------------------------------
# What they leave behind
# ---------------------------------------------------------------------------
# These five items DO NOT EXIST IN items.py YET. This module does not own that
# file, so the rows below are the specification for whoever does, written in
# items.Item's own field order so the port is a copy rather than a translation.
#
# NONE OF THEM CARRIES AN items.EFFECT_LABELS EFFECT, and that is deliberate
# rather than an omission. Every one of them is an OVERWORLD verb — a radius, a
# grip on ice, a thinned pack, a gate that opens. None of them may buy a look at
# a problem, a weakness or an answer, which is the same refusal
# captives.BOON_EFFECTS_REFUSED makes about the boons, for the same reason.
#
# `mechanic` names the verb for the pass that implements it. `numbers` is the
# design's arithmetic, kept as data so a client reads one row instead of
# hard-coding four constants in four files.

@dataclass(frozen=True)
class Drop:
    id: str
    name: str
    slot: str            # items.SLOTS
    rarity: str          # items.RARITIES
    icon: str
    element: str
    flavour: str
    mechanic: str        # the overworld verb, in the implementer's words
    effects: dict = field(default_factory=dict)   # always empty. See above.


DROPS = {
    "the_slate": Drop(
        id="the_slate", name="The Slate", slot="trinket", rarity="UNCOMMON",
        icon="scroll", element="NEUTRAL",
        flavour="A schoolteacher's slate, blank, with the chalk still tied to "
                "the frame by a length of string that has been re-knotted more "
                "than once.",
        mechanic="Draws the regions you have entered and the routes you have "
                 "walked. Upgraded by the_marked_line to carry open quest "
                 "markers and a where-next pointer. It gates nothing: "
                 "everything on it is also on the world screen.",
    ),
    "the_lamp": Drop(
        id="the_lamp", name="The Lamp", slot="trinket", rarity="RARE",
        icon="lantern", element="BRUTE",
        flavour="A runner's lamp, cut off short at the hip so it cannot catch "
                "on anything, with a burn ladder up the handle where twelve "
                "years of reaching past a wick have marked it.",
        mechanic="Sight radius 5 tiles with a 2-tile falloff, centred on the "
                 "player. No facing offset.",
    ),
    "skate_irons": Drop(
        id="skate_irons", name="Skate Irons", slot="feet", rarity="RARE",
        icon="boots", element="COLD",
        flavour="Strap-on irons off a rigger's kit, filed flat on the inside "
                "edge by somebody who has spent a life judging distances in "
                "bad light and would rather arrive where she aimed.",
        mechanic="Control on ICE tiles is restored, and movement across them "
                 "runs at 1.35x. They never call the exit.",
    ),
    "the_dart": Drop(
        id="the_dart", name="The Poison Dart", slot="trinket", rarity="RARE",
        icon="thorn", element="POISON",
        flavour="A Stringwood thorn, hollowed, charged with dried pitch, and "
                "carried in a bone tube that is older than the thorn and has "
                "held a great many of them.",
        mechanic="Spent at the top of a pack, before turn one, it leaves "
                 "exactly one enemy standing. Two charges, +1 per dungeon "
                 "boss cleared, cap 2.",
    ),
    "the_gear": Drop(
        id="the_gear", name="The Mechanical Gear", slot="trinket",
        rarity="RARE", icon="gear", element="FIRE",
        flavour="A spare sluice gear, cut for the seized gates and never "
                "fitted, with the tooth-count scratched on the boss of it in a "
                "lift engineer's hand.",
        mechanic="Cranks a sluice by hand: 4.0s to drain, the channel holds "
                 "open 8.0s, 1.5s to refill.",
    ),
}


# ---------------------------------------------------------------------------
# The shape of an escort
# ---------------------------------------------------------------------------
# `escort`, not `companion`. `companion` is the PET everywhere in this codebase
# — overworld.js reads state.pets into this.companion and hunters.py scores it
# with COMPANION_CREDIT — and a second meaning for a word that is already
# load-bearing in the renderer is a bug waiting for a maintenance pass.
#
# `pack`, not `ambush`, for the same reason: `ambush` already means an SRS
# retest in classes.py, forge.py, items.py and finalexam.py.

@dataclass(frozen=True)
class Escort:
    id: str               # captives.CAPTIVE_BY_ID id. Never a new person.
    zone: str             # ZONE_BY_ID id
    boss: str             # world.BOSS_BY_ID id — who takes them
    capture_kind: str     # "dungeon" (the zone's capture delve) or "sweep"
    capture_dungeon: str  # dungeonmod.DUNGEON_BY_ID id, or "" for the sweep
    drop: str             # DROPS id — the thing they leave, always
    drop_early: bool      # True for the one item handed over before anything
                          # is taken, because it is the thing that tells the
                          # player where the zones are

    role: str             # what they are doing in the zone, in one line
    verb: str             # the mechanic, in the implementer's words
    without: dict         # the zone with nobody and nothing
    with_them: dict       # the zone with them walking
    with_item: dict       # the zone with the drop and no them
    metric: str           # the key in those three that carries the loss, or ""
    metric_better: str    # "higher" or "lower"
    lost: tuple           # capability keys they had and the item does not

    walking: tuple        # what they say while they walk, in their own voice
    capture: tuple        # three lines, at the moment the boss takes them
    narrator: str         # one line of narrator, after they are gone
    loss_line: str        # what the item does not do, said to the player once
    thanks: tuple         # the keep-it line at the cage, after captives' own
    handover: str         # what they offer for the next zone
    retaken_line: str     # what is said when the Interviewer collects them


# ---------------------------------------------------------------------------
# The five
# ---------------------------------------------------------------------------
# Ladder order 2, 4, 6, 8, 14. Evenly spaced, and none of it was arranged: it
# fell out of which boss each of these people was already assigned to in
# captives.py before this design existed.

ESCORTS = (

    # -- HOME -------------------------------------------------------------
    # The exception, and the proof. Python Village has no boss and no dungeon,
    # so nothing there can take her mid-game. She is taken at the finale, with
    # Yoren Halt and Ivo Brannt, which is already exactly what captives.py says
    # happens — and the player's line, "the last boss captures all of these
    # known villagers", lands hardest on the one they have known since minute
    # one.
    Escort(
        id="thessaly_brun", zone="home", boss="the_interviewer",
        capture_kind="sweep", capture_dungeon="",
        drop="the_slate", drop_early=True,
        role="Walks the village and the Fields, and reads the place to you.",
        verb="Standing on a building's door tile prints, once per building, "
             "what that building is and what its sign means. Standing at a "
             "route head prints where that road goes and what it costs. She "
             "never says anything about a problem; she says things about "
             "places.",
        without={"building_captions": False, "route_captions": False,
                 "map": False},
        with_them={"building_captions": True, "route_captions": True,
                   "map": False},
        with_item={"building_captions": False, "route_captions": False,
                   "map": True, "stages": 2},
        metric="", metric_better="higher",
        lost=("building_captions", "route_captions"),
        walking=("That door is the mender's. The sign is a bowl, not a cup, "
                 "because a cup is a tavern and half the village cannot read "
                 "either.",
                 "The road out of the gate is the only one worth anything at "
                 "your age. Everything else is somebody else's idea of a "
                 "shortcut.",
                 "I have taught in this square for nineteen years. I can tell "
                 "you what is behind every door on it and I am not going to "
                 "tell you what is in any of the books."),
        capture=("There is a man at the gate who has been standing there "
                 "since the bell. He has not moved and he has not sat down.",
                 "Get the board in off the wall. The list for tomorrow is on "
                 "it and if it rains on that list the whole square will claim "
                 "they never saw it.",
                 "Nineteen years. Go on, then. You know the road."),
        narrator="The square is the same square. The board is still on the "
                 "wall, the list for tomorrow is still on the board, and "
                 "there is nobody standing in front of it.",
        loss_line="The captions stop. The Slate keeps working. You have "
                  "already read the signs.",
        thanks=("Keep the slate. It was blank when I gave it to you and it is "
                "not blank now, which is the only thing a slate is for.",),
        handover="The morning drill goes back up on the board the night "
                 "before, so nobody can say they did not know what was being "
                 "asked.",
        retaken_line="The board is still on the wall. The list for tomorrow "
                     "is in her hand, and she is not in the square.",
    ),

    # -- THE DARK ---------------------------------------------------------
    # Josa Fell was written as this companion before this design existed. Her
    # boon already reads "The Caverns are lit from both ends, so nothing waits
    # in the dark for a runner." It needed a mechanic attached and nothing else.
    Escort(
        id="josa_fell", zone="the_dark", boss="three_sum_hydra",
        capture_kind="dungeon", capture_dungeon="sunken_index",
        drop="the_lamp", drop_early=False,
        role="Carries the lamp, and walks a pace ahead on the path.",
        verb="Sight radius 6 tiles with a 2-tile falloff, offset 2 tiles in "
             "the facing direction. She walks ahead, so you see round a "
             "corner before you turn it.",
        without={"radius": 2, "falloff": 1, "offset": 0},
        with_them={"radius": 6, "falloff": 2, "offset": 2},
        with_item={"radius": 5, "falloff": 2, "offset": 0},
        metric="radius", metric_better="higher",
        lost=("offset",),
        walking=("Stay off my heel. If I stop it is because the lamp found "
                 "something and you are going to want the room to stop with "
                 "me.",
                 "Sera runs this line from the sump end. If you see a second "
                 "light down there it is my sister and she is not lost, she "
                 "is early.",
                 "Four thousand alcoves and the numbers are cut, not painted. "
                 "Read them. The damp cannot argue with a cut number."),
        capture=("It has been counting the lights. Two lights, one line, and "
                 "it has just worked out that the second one is not me.",
                 "Take the lamp. Do not take it after me, take it now, off my "
                 "hand, because in a moment I am going to be somewhere I "
                 "cannot reach.",
                 "Tell Sera the gate end is dark. She will know what that "
                 "means and she will not go down it alone."),
        narrator="The lamp is on the floor of the passage, still upright, "
                 "still lit, and the disc of light around it has stopped "
                 "moving forward.",
        loss_line="The lamp lights five tiles instead of six, and it lights "
                  "them around you rather than ahead of you. Every blind "
                  "corner in the Sunken Index was a corner she saw first.",
        thanks=("Keep the lamp. I have a better one and I cut the wick for it "
                "myself, and a lamp that has been down there ought to stay "
                "with whoever brought it up.",),
        handover="Both ends of the lamp line burn again, and nothing in the "
                 "Sunken Index sits dark for a whole shift.",
        retaken_line="The lamp line goes out from the gate end first, one "
                     "wick at a time, in the order she lights them.",
    ),

    # -- THE SNOW ---------------------------------------------------------
    # Torv Bael is taken in the same scene and is already her co-captive on the
    # same boss. He does not walk with you — he is at the far end of the pass
    # rigging the other half, which is why the_rigged_span is a boon they share
    # and why they are taken together. One escort sprite, two people freed.
    Escort(
        id="hessa_dunmar", zone="the_snow", boss="twin_behemoth",
        capture_kind="dungeon", capture_dungeon="converging_span",
        drop="skate_irons", drop_early=False,
        role="Rigs a hand line across the ice, and calls the exit.",
        verb="Stepping onto ICE does not commit you; you keep tile-by-tile "
             "control at walking speed. On approaching a patch she names, in "
             "one line, which edge of it is walkable.",
        without={"control": False, "speed_mult": 1.0, "calls_exit": False},
        with_them={"control": True, "speed_mult": 1.0, "calls_exit": True},
        with_item={"control": True, "speed_mult": 1.35, "calls_exit": False},
        metric="", metric_better="higher",
        lost=("calls_exit",),
        walking=("North lip holds. The west one drops and it drops onto "
                 "stone, so take the long way round and do not argue with me "
                 "about the four extra paces.",
                 "Torv is rigging the other half from the far end. We will "
                 "meet in the middle and one of us will be four inches out "
                 "and it will be him.",
                 "A span is not strong in the middle. It is strong at the "
                 "ends and honest in the middle, which is where you find out "
                 "who was counting."),
        capture=("Two of it. From both ends of the pass at once, which is my "
                 "own method and I do not care for seeing it used.",
                 "The irons are in the kit by the post. Take them, strap them "
                 "inside the boot and not over it, and file the inside edge "
                 "when they start running away with you.",
                 "Torv. Torv, the far end, now. Do not finish the knot."),
        narrator="The hand line is still strung across the patch, tied off at "
                 "the near post and loose at the far one, and there is nobody "
                 "at either end of it.",
        loss_line="The irons give you control and they give you speed. They "
                  "never call the exit. After Hessa you read the patch "
                  "yourself, which is the whole point of putting ice on the "
                  "way through.",
        thanks=("Keep the irons. I rig spans, I do not skate, and they have "
                "been on your feet longer than they were ever on mine.",),
        handover="The Rimeward Hauberk, for the pass you are leaving and the "
                 "tower you are about to climb, and she says so out loud.",
        retaken_line="The hand line comes off the near post first. The far "
                     "end stays tied, because Torv tied it and Torv is still "
                     "at the far end.",
    ),

    # -- THE GREEN --------------------------------------------------------
    # The player asked for a female jaguar warrior. She is a forester who works
    # both sides of the Branch Ladder, she moves through the canopy, and she
    # carries an axe because her family does. The sprite is `forester`. The
    # jaguar is how she moves and how the packs react to her, and a pass that
    # wants literal jaguar art should say so rather than assume it.
    Escort(
        id="halla_vane", zone="the_green", boss="tree_dragon",
        capture_kind="dungeon", capture_dungeon="anagram_deeps",
        drop="the_dart", drop_early=False,
        role="Drops all but one of a pack before the first turn, every time, "
             "for nothing.",
        verb="In the three Green regions an encounter marker has a 22 per cent "
             "chance of fielding three to five enemies instead of one. With "
             "Halla walking, all but one are down before turn one.",
        without={"leaves": 0, "charges": 0, "unlimited": False},
        with_them={"leaves": 1, "charges": 0, "unlimited": True},
        with_item={"leaves": 1, "charges": 2, "unlimited": False},
        metric="", metric_better="higher",
        lost=("unlimited",),
        walking=("Stand still. Not quiet, still. They hear movement before "
                 "they hear noise and those are not the same thing.",
                 "Every clearing has a smaller forest in it. Count the way "
                 "down before you count the way back, or you will come out "
                 "somewhere that looks exactly like where you went in.",
                 "Four of them is a pack. One of them is a beast. You can "
                 "walk away from a beast."),
        capture=("It came down the trunk. Not along a branch, down the trunk, "
                 "head first, and nothing that size is supposed to be able to "
                 "do that.",
                 "Tube at my hip. Two charges in it, thorn and dried pitch, "
                 "and it is for the packs and not for the single beasts. "
                 "Waste one on a beast and you will meet four with an empty "
                 "tube.",
                 "Tell Corr it was not the ladder. He will hear a version "
                 "where I fell and I would rather he heard this one."),
        narrator="The understorey closes. The bone tube is lying on the moss "
                 "where the trail turns, and the trail keeps turning without "
                 "anybody on it.",
        loss_line="Halla did it every time, for free, forever. The dart does "
                  "it twice. A pack with no charges left is a full pack, and a "
                  "full pack is a legal, winnable fight. It is harder. It is "
                  "not a wall.",
        thanks=("Keep the dart. I cut the thorn and I dried the pitch and I "
                "would only make another one, and you have been carrying it "
                "into worse places than I ever did.",),
        handover="Both sides of the Branch Ladder are cut and blazed again, "
                 "and she has a pair of her cousin's boots she says you will "
                 "want before the Wastes.",
        retaken_line="The trail stops being cut about forty paces short of "
                     "the high crown, and the blaze marks stop with it.",
    ),

    # -- THE FIRE ---------------------------------------------------------
    # Greave is taken by a boss from a different region, and that is a real
    # deviation from "the zone boss takes them". The Mines have no boss row and
    # cannot be given one — finalexam.BOSS_LADDER rung N is the Nth entry of
    # world.BOSSES, and adding a boss would renumber every crutch in the game.
    # world.REGIONS makes graph_wastes unlock FROM stack_queue_mines, so the
    # Wastes are strictly downstream, and the fiction is exact: the Necromancer
    # came up the ore line and took the man who runs the lift. The scene says
    # so, out loud, in his own first line.
    Escort(
        id="greave", zone="the_fire", boss="graph_necromancer",
        capture_kind="dungeon", capture_dungeon="ninth_cart",
        drop="the_gear", drop_early=False,
        role="Works the sluices, and holds the channel open long enough that "
             "you never think about it.",
        verb="A lava channel crossing a route has a sluice beside it. Greave "
             "cranks it: 1.5s to drain, 20.0s open, 1.5s to refill.",
        without={"drain": 0.0, "open": 0.0, "refill": 0.0, "crankable": False},
        with_them={"drain": 1.5, "open": 20.0, "refill": 1.5,
                   "crankable": True},
        with_item={"drain": 4.0, "open": 8.0, "refill": 1.5,
                   "crankable": True},
        metric="open", metric_better="higher",
        lost=(),
        walking=("Do not stand on the lip while it drains. It drains at the "
                 "bottom and the bottom is not where you are looking.",
                 "The lift takes the cart that came off last. Mix that up and "
                 "somebody gets buried, and I have been to both of those "
                 "funerals.",
                 "Cross when you like. I will hold it. Holding it is the "
                 "entire job and I have been doing it for thirty years."),
        capture=("It came up the ore line. Not down the stair, not through "
                 "the gate. Up the line, in the dark, at the speed of a cart.",
                 "Spare gear, in the tool bag, cut for the seized gates. Four "
                 "seconds to drain and it will hold you about eight, so do "
                 "not crank it and then go and have a think.",
                 "Shut the third sluice behind me. Not for me. For the cart "
                 "crew, who are eleven minutes behind and do not know yet."),
        narrator="The sluice wheel is still turning, slowing, with nobody on "
                 "the handle, and the channel behind it has already started to "
                 "come back up.",
        loss_line="Two and a half seconds slower to open and twelve seconds "
                  "less margin. With Greave you crossed when you felt like it. "
                  "With the gear you stand at the lip, crank, and go.",
        thanks=("Keep the gear. It is a spare and it was cut for gates that "
                "are seized, and a man with one gear and no lift has a "
                "paperweight.",),
        handover="The sluices are cranked on the hour whether anything is "
                 "crossing or not, and he has a pair of greaves off the Mines' "
                 "own bench that he says are wasted on a smith.",
        retaken_line="The third sluice is cranked shut and the wheel is "
                     "chained, which is how he leaves it, and the lift does "
                     "not come back up.",
    ),
)

BY_ID = {row.id: row for row in ESCORTS}
BY_ZONE = {row.zone: row for row in ESCORTS}
BY_BOSS: dict = {}
for _row in ESCORTS:
    BY_BOSS.setdefault(_row.boss, []).append(_row)
del _row
BY_REGION = {region: BY_ZONE[zone.id]
             for zone in ZONES for region in zone.regions
             if zone.id in BY_ZONE}

# The ids, in ladder order, which is the order the player meets them in and the
# order the roll call reads them out in.
ORDER = tuple(row.id for row in
              sorted(ESCORTS, key=lambda r: RUNG.get(r.boss, 99)))


# ---------------------------------------------------------------------------
# The pack
# ---------------------------------------------------------------------------
# Never called an ambush. `ambush` already means an SRS retest in twenty-odd
# places. This is the whole of the pack's specification; the battle itself is
# incantation.make_context([a, b, c, d]), which already fields several enemies
# of different kinds at once and says so in its own docstring. There is no
# second combat system here and there must not be one.

PACK = {
    "regions": ("stringwood_labyrinth", "recursive_forest",
                "binary_tree_canopy"),
    "chance": 0.22,
    "size": (3, 5),
    "seed": "hash(save_seed, marker.id) — fixed per marker per save, so it "
            "cannot be reload-scummed",
    "never": "elite markers. An elite is already the hard thing.",
    "thinning": "Set every enemy but the last to hp 0 before turn 1. "
                "ctx.living() returns one. ctx.bindings() still holds the dead "
                "names, so they are still in scope and still typeable, which "
                "is not a leak — it is the lesson.",
    "charges": {"start": 2, "cap": 2, "refill_per_dungeon_boss": 1},
}


# ---------------------------------------------------------------------------
# The save
# ---------------------------------------------------------------------------
# One key, three lists, and every one of them optional. Nothing in this module
# requires the key to exist: `state_of()` derives the same answer from
# cleared_bosses, dungeons_cleared, inventory and the captives block when the
# latch is absent, which is what makes an old save correct rather than merely
# non-fatal.
#
#   taken   escort ids the engine has latched as taken, in order
#   given   drop ids already handed over, so a grant cannot happen twice
#   scenes  escort ids whose capture scene has been played
#
# THE LATCH IS AN OPTIMISATION AND A RECORD, NEVER AN AUTHORITY. If it
# disagrees with the derivation, the derivation is the one that can be wrong in
# only one direction: it can be late, never early.

STATE_KEY = "escorts"


def new_escort_state() -> dict:
    """Add to engine.DEFAULT_STATE under STATE_KEY. Forward-fills on load."""
    # `swept` is a LIST holding at most one boss id, and it is a list rather
    # than a bool so `_write_bucket`'s existing repair covers it for free: the
    # loop there rebuilds any key that is not a list, and a hand-edited save
    # that put `true` in here heals on the next write instead of raising.
    return {"taken": [], "given": [], "scenes": [], "swept": []}


def _bucket(state: dict) -> dict:
    """Read-only view of the latch. Never writes; `_write_bucket` does that."""
    raw = state.get(STATE_KEY) if isinstance(state, dict) else None
    return raw if isinstance(raw, dict) else {}


def _latch(state: dict, key: str) -> list:
    """One list out of the latch, and [] for anything that is not one. A save
    is a file on somebody's disk and it can have been edited by hand."""
    value = _bucket(state).get(key)
    return value if isinstance(value, list) else []


def _write_bucket(state: dict) -> dict:
    raw = state.get(STATE_KEY)
    if not isinstance(raw, dict):
        raw = new_escort_state()
        state[STATE_KEY] = raw
    for key, blank in new_escort_state().items():
        if not isinstance(raw.get(key), list):
            raw[key] = list(blank)
    return raw


def available_in(mode: str) -> bool:
    """Adventure Mode only, on the same gate captives.py uses. A measured run
    does not hand anybody an escort, a lamp or a road."""
    return captives.available_in(mode)


# ---------------------------------------------------------------------------
# The one function that answers "what state is this person in"
# ---------------------------------------------------------------------------
# Pure. Reads the save, mutates nothing, raises nothing, and returns one of
# STATES — or "" for an id that is not an escort, which is the answer a caller
# asking about a villager deserves rather than an exception.

def _list(state: dict, key: str) -> list:
    value = (state or {}).get(key)
    return value if isinstance(value, list) else []


def _final_release_done(state: dict) -> bool:
    block = (state or {}).get(captives.STATE_KEY)
    return bool(isinstance(block, dict) and block.get("final_release"))


# The sweep is "near the end", and near the end is TWO facts, not one.
#
# The Bug Demon alone is not near the end. Measured against progression.ROUTES:
# `rt_armorers_stair` runs python_village -> debugging_dungeon carrying
# Need(kind='none'), so it is open and passable on a brand new save. Walk the
# graph from the village square using ONLY the roads that need nothing and you
# reach exactly three regions — python_village, fields_of_syntax and
# debugging_dungeon — and exactly ONE boss stands in them. It is the Bug
# Demon, and it is the second-to-last rung on the ladder.
#
# So a player who takes the stair under the forge on their first afternoon and
# wins that fight has the tutorial guide collected before the tutorial: with
# the sweep keyed on that boss alone, `escort_in(state, 'python_village')`
# returns {} and every building caption and route caption the player asked for
# never happens.
#
# The fiction the design already describes is "after the second-to-last boss",
# and the honest reading of that is the LADDER, not the name: the Bug Demon
# down AND the ladder essentially walked. Twelve of the fourteen rungs is one
# clear of bug_demon's own rung 13, which is unreachable from the village
# square and reachable by anybody who got to rung 13 the long way.
SWEEP_MIN_RUNGS = len(world.BOSSES) - 2


def sweep_fired(state: dict) -> bool:
    """Has the second-to-last rung fallen, with the finale still to come.

    This is the whole of the Interviewer's sweep condition and it is derived,
    so a save that cleared the Bug Demon before this file existed answers
    correctly on the next load.

    TWO CONDITIONS, and the second one is what stops the sweep being reachable
    from the tutorial. See the note above SWEEP_MIN_RUNGS.
    """
    if _final_release_done(state):
        return False
    cleared = _list(state, "cleared_bosses")
    if SWEEP_AFTER_BOSS not in cleared:
        return False
    return len([b for b in cleared if b in RUNG]) >= SWEEP_MIN_RUNGS


def captured(state: dict, escort_id: str) -> bool:
    """Has the thing that takes this person taken them yet."""
    row = BY_ID.get(escort_id)
    if row is None:
        return False
    if escort_id in _latch(state, "taken"):
        return True
    if row.capture_kind == "sweep":
        return sweep_fired(state)
    return row.capture_dungeon in _list(state, "dungeons_cleared")


def state_of(state: dict, escort_id: str) -> str:
    """What state is this companion in, given the save. Pure, total, and the
    only thing in this module that decides.

    Order matters and is the arc's order read backwards: the last thing that
    happened to somebody is the thing that is true about them.
    """
    row = BY_ID.get(escort_id)
    if row is None:
        return ""
    save = state if isinstance(state, dict) else {}

    freed = captives.is_freed(save, escort_id)
    if freed:
        # RETAKEN IS A RECORD, NOT A CONDITION. It means exactly what
        # `captives.retake()` latched and nothing else.
        #
        # This used to read `or sweep_fired(save)`, which turned the sweep into
        # a standing fact about the world rather than a thing that happened to
        # a person. Anybody rescued after the Bug Demon fell then jumped
        # WALKING/ITEM_HELD straight to RETAKEN and never passed through FREED
        # at all — so `lines_for()` never reached its FREED branch and the
        # thank-you, the keep-it line and the handover gift for the next zone
        # were unreachable for all four dungeon companions. Measured before the
        # fix: thanks_said False, handover_said False, for every one of them.
        #
        # The docstring above this function promises the derivation is
        # late-never-early, and this is the shape that keeps that promise:
        # `_sweep()` is what performs the taking, it runs on the very next
        # tick, and until it has run the player is looking at somebody they
        # really did get back.
        if captives.is_retaken(save, escort_id):
            return RETAKEN
        return FREED
    if captured(save, escort_id):
        if escort_id in _latch(save, "scenes"):
            return ITEM_HELD
        # The derived fallback, for a save the engine never latched. It reads
        # the bag, and it can only be used for the four drops that arrive AT
        # the capture: the Slate is handed over long before Thessaly is taken,
        # so for her a bag with a slate in it says nothing about whether the
        # scene has played.
        if not row.drop_early and row.drop in _list(save, "inventory"):
            return ITEM_HELD
        return TAKEN
    return WALKING


def states(state: dict) -> dict:
    """All five at once, in ladder order."""
    return {eid: state_of(state, eid) for eid in ORDER}


def escort_in(state: dict, region_id: str) -> dict:
    """Who is actually walking beside you in this region, or {}.

    A companion walks only in their own zone and only while WALKING. This is
    the call overworld.setEscort() is fed from, and it is the only thing the
    renderer needs to know.
    """
    row = BY_REGION.get(region_id)
    if row is None:
        return {}
    if state_of(state, row.id) != WALKING:
        return {}
    return view(state, row.id)


def zone_of(region_id: str) -> dict:
    """The zone a region belongs to, or {} for the nine that have none."""
    zone = ZONE_BY_REGION.get(region_id)
    return _zone_view(zone) if zone else {}


# ---------------------------------------------------------------------------
# What the client is handed
# ---------------------------------------------------------------------------

def _zone_view(zone: Zone) -> dict:
    return {"id": zone.id, "name": zone.name, "regions": list(zone.regions),
            "element": zone.element, "verb": zone.verb}


def drop_view(drop_id: str) -> dict:
    row = DROPS.get(drop_id)
    if row is None:
        return {}
    return {"id": row.id, "name": row.name, "slot": row.slot,
            "rarity": row.rarity, "icon": row.icon, "element": row.element,
            "flavour": row.flavour, "mechanic": row.mechanic,
            "effects": dict(row.effects),
            "in_catalogue": row.id in items.BY_ID}


def view(state: dict, escort_id: str) -> dict:
    """One escort, everything about them, at the state the save says."""
    row = BY_ID.get(escort_id)
    if row is None:
        return {}
    person = captives.CAPTIVE_BY_ID.get(row.id)
    zone = ZONE_BY_ID[row.zone]
    now = state_of(state, escort_id)
    return {
        "id": row.id,
        "name": person.name if person else row.id,
        "trade": person.trade if person else "",
        "sprite": person.sprite if person else "villager",
        "home": person.home if person else "",
        "held_in": person.held_in if person else "",
        "zone": _zone_view(zone),
        "boss": row.boss,
        "boss_name": world.BOSS_BY_ID[row.boss]["name"],
        "rung": RUNG.get(row.boss, 0),
        "capture_kind": row.capture_kind,
        "capture_dungeon": row.capture_dungeon,
        "state": now,
        "state_label": STATE_LABELS.get(now, ""),
        "walking": now == WALKING,
        "role": row.role,
        "verb": row.verb,
        "drop": drop_view(row.drop),
        "drop_early": row.drop_early,
        "held": row.drop in _list(state, "inventory"),
        "without": dict(row.without),
        "with_them": dict(row.with_them),
        "with_item": dict(row.with_item),
        "lost": list(row.lost),
        "loss_line": row.loss_line,
        "gift": person.gift if person else "",
        "boon": person.boon if person else "",
        "handover": row.handover,
        "lines": lines_for(state, escort_id),
    }


def lines_for(state: dict, escort_id: str) -> list:
    """What this person says NOW. The state machine, rendered as dialogue."""
    row = BY_ID.get(escort_id)
    if row is None:
        return []
    now = state_of(state, escort_id)
    if now == WALKING:
        return list(row.walking)
    if now == TAKEN:
        return list(row.capture) + [row.narrator]
    if now == ITEM_HELD:
        return [row.loss_line]
    if now == FREED:
        person = captives.CAPTIVE_BY_ID.get(row.id)
        out = list(person.lines) if person else []
        return out + list(row.thanks) + [row.handover]
    if now == RETAKEN:
        return [row.retaken_line]
    return []


def scene(escort_id: str) -> dict:
    """Beat 3, as data. Eight seconds, and it never blocks input.

    The house precedent is unmakingfx.js, which makes exactly this argument in
    its own source: on the world map, a hundred and fifteen seconds is not
    weather, it is a hostage situation.
    """
    row = BY_ID.get(escort_id)
    if row is None:
        return {}
    boss = world.BOSS_BY_ID[row.boss]
    return {
        "escort": row.id,
        "boss": row.boss,
        "boss_name": boss["name"],
        "colour": boss.get("colour", ""),
        "lines": list(row.capture),
        "narrator": row.narrator,
        "drop": drop_view(row.drop),
        "loss_line": row.loss_line,
        # The item is in the bag before this plays. What is on the ground is a
        # two-second decorative glint and there is nothing to collect: a
        # dropped item the player has to remember to pick up is the same dead
        # end as a locked door, arrived at from the other side.
        "glint_seconds": 2.0,
        "wash_alpha": 0.35,
        "wash_seconds": 1.2,
        "max_seconds": 8.0,
        "blocks_input": False,
    }


def snapshot(state: dict, region_id: str = "") -> dict:
    """Everything a panel or a save-summary wants, in one call."""
    rows = [view(state, eid) for eid in ORDER]
    here = escort_in(state, region_id) if region_id else {}
    return {
        "escorts": rows,
        "states": states(state),
        "here": here,
        "zone": zone_of(region_id) if region_id else {},
        "sweep": sweep_fired(state),
        "carrying": [r["drop"]["id"] for r in rows if r["held"]],
        "counts": {
            "total": len(ESCORTS),
            **{name.lower(): sum(1 for r in rows if r["state"] == name)
               for name in STATES},
        },
    }


# ---------------------------------------------------------------------------
# The one call that moves the arc
# ---------------------------------------------------------------------------
# Everything above is pure. This is the only thing in the file that writes, it
# is idempotent, and it is safe to call on every overworld tick: a run in which
# nothing changed returns no events and touches nothing.

def _grant(state: dict, item_id: str) -> bool:
    """The same one-line path engine.py already uses everywhere it hands over
    gear. There is no items.grant(); do not invent one."""
    bag = state.get("inventory")
    if not isinstance(bag, list):
        bag = []
        state["inventory"] = bag
    if item_id in bag:
        return False
    bag.append(item_id)
    return True


def capture(state: dict, escort_id: str) -> dict:
    """Beat 3 and beat 4, in one transaction.

    Called by the engine on the transition of the capture dungeon's seal to
    met, resolved on the player's return to the overworld so the scene has
    ground to play on. Latches, grants the drop, and hands back the scene.
    Returns {} when there is nothing to do, so the caller needs no guard.
    """
    row = BY_ID.get(escort_id)
    if row is None:
        return {}
    if captives.is_freed(state, escort_id):
        return {}
    raw = _write_bucket(state)
    if escort_id in raw["scenes"]:
        return {}
    if escort_id not in raw["taken"]:
        raw["taken"].append(escort_id)
    # The same one-word discipline as the FREED/RETAKEN re-grant in advance():
    # `_grant` asks the BAG, and `given` is written as the record of what was
    # handed over. The two roads into ITEM_HELD are then identical.
    granted = _grant(state, row.drop)
    if row.drop not in raw["given"]:
        raw["given"].append(row.drop)
    raw["scenes"].append(escort_id)
    out = scene(escort_id)
    out["granted"] = granted
    return out


def hand_over_early(state: dict) -> dict:
    """The Slate, and the only item in the arc that is given rather than left.

    The map is the one zone item the player must have BEFORE anything is taken,
    because it is the thing that tells them where the zones are. Thessaly hands
    it over the first time the Waking Road is walked.
    """
    world_block = state.get("world")
    walked = []
    if isinstance(world_block, dict):
        value = world_block.get("routes_walked")
        if isinstance(value, list):
            walked = value
    out: dict = {}
    for row in ESCORTS:
        if not row.drop_early:
            continue
        if SLATE_ROUTE not in walked:
            continue
        if state_of(state, row.id) != WALKING:
            continue
        raw = _write_bucket(state)
        if row.drop in raw["given"]:
            continue
        raw["given"].append(row.drop)
        _grant(state, row.drop)
        out = {"escort": row.id, "drop": drop_view(row.drop),
               "lines": list(row.walking[:1]),
               "note": "She hands it over blank. It gates nothing; everything "
                       "on it is also on the world screen."}
    return out


def advance(state: dict) -> dict:
    """Reconcile the save with the arc. Idempotent, and safe every tick.

    Four things, in order, and every one of them a no-op when it has already
    happened:

      1. The Slate, once the Waking Road has been walked.
      2. The drop, for anybody the arc says has left your side — TAKEN by the
         boss, or FREED by a player who beat that boss before the capture ever
         fired. BOTH ROADS GRANT, which is the invariant that makes the item
         impossible to miss.
      3. The capture scene, latched so it plays once.
      4. The Interviewer's sweep, once the second-to-last rung has fallen.
    """
    events: list = []
    early = hand_over_early(state)
    if early:
        events.append({"kind": "given", **early})

    for row in ESCORTS:
        now = state_of(state, row.id)
        if now == WALKING:
            continue
        raw = _write_bucket(state)
        if now in (TAKEN, ITEM_HELD) and row.id not in raw["scenes"]:
            events.append({"kind": "taken", **capture(state, row.id)})
            continue
        # Freed without ever being taken: the boss fell first. They still hand
        # the thing over, because a zone mechanic the player can miss is a dead
        # end and this arc does not have one.
        #
        # THE GUARD READS THE BAG, NOT THE LEDGER, and that is the whole of the
        # difference. `raw["given"]` is a RECORD of what was handed over; the
        # inventory is the FACT of whether the player has it. Guarding on the
        # record meant a drop that left the bag by any route was never
        # re-granted: `state_of()` goes on answering ITEM_HELD off the capture
        # latch regardless of the bag, so the item was gone for good and the
        # zone mechanic with it. Measured: remove the_lamp after the capture,
        # advance() twice, and you get 0 events, an empty bag and view()['held']
        # False, forever.
        #
        # Not reachable through the shipped engine today — the inventory is
        # append-only and shop.sell refuses anything without a rack receipt —
        # but this module goes to length everywhere else for a save that was
        # hand-edited or half-written, and this is the same courtesy.
        # `_grant()` is already idempotent, so the check costs nothing.
        if now in (FREED, RETAKEN) and row.drop not in _list(state, "inventory"):
            if row.drop not in raw["given"]:
                raw["given"].append(row.drop)
            if _grant(state, row.drop):
                events.append({"kind": "kept", "escort": row.id,
                               "drop": drop_view(row.drop),
                               "lines": list(row.thanks)})

    swept = _sweep(state)
    if swept:
        events.append(swept)
    return {"events": events, "states": states(state)}


def _sweep(state: dict) -> dict:
    """Beat 7. The Interviewer collects everyone the player got back.

    WHO IS TAKEN, and the reasoning, because the edge cases are real: a player
    can beat the Bug Demon at rung 13 having never gone near the Caverns.

      - Everybody among these five who is currently FREED. They are out, the
        player went and got them, and they are the ones the sweep can cost.
      - Thessaly Brun, whose own capture IS this event, and who has been in
        Python Village since minute one.
      - NOT anybody a boss is already holding. The Necromancer has Greave; the
        Interviewer does not need to take him twice.
      - NOT anybody still walking in a zone the player has not worked. Taking
        somebody the player has arguably never met is a beat with no weight in
        it, and it would read as arithmetic rather than as loss.

    Items are never touched. Removing a zone mechanic at rung 13 would put the
    last two bosses behind a wall built out of a cutscene.

    IT HAPPENS ONCE, AND THE ROSTER FREEZES AT WHO WAS OUT WHEN THE RUNG FELL,
    which is what the paragraph above has always claimed and what the code did
    not do. `sweep_fired()` is a STANDING fact — the Bug Demon stays beaten —
    and the roster was recomputed on every call as "freed and not retaken", so
    every companion rescued AFTER the rung fell was collected the moment they
    were freed and a fresh one-time cutscene was emitted for them. Measured
    before the fix: the Interviewer's single collection scene fired four
    separate times in one run, and fired once more on Thessaly Brun one tick
    AFTER the Interviewer himself was already dead.

    So the one-shot is latched HERE, in this module's own bucket, rather than
    inferred from the world. `captives.retake()` is idempotent per person and
    would not have double-suspended a boon; what it could not do is stop the
    scene from playing again, because a scene is an event and not a set.
    """
    if _latch(state, "swept"):
        return {}
    if not sweep_fired(state):
        return {}
    wanted = [row.id for row in ESCORTS
              if captives.is_freed(state, row.id)
              and not captives.is_retaken(state, row.id)]
    if not wanted:
        return {}
    taken = captives.retake(state, wanted)
    if not taken.get("retaken"):
        return {}
    # Latched on the call that FIRES, never on the calls that found nobody: a
    # player who reaches rung 13 with nobody rescued has not watched the scene,
    # and the first person they get back after that is still worth taking.
    _write_bucket(state)["swept"].append(SWEEP_AFTER_BOSS)
    return {
        "kind": "sweep",
        "after_boss": SWEEP_AFTER_BOSS,
        "rung": RUNG.get(SWEEP_AFTER_BOSS, 0),
        "retaken": taken["retaken"],
        "lines": [BY_ID[eid].retaken_line for eid in taken["retaken"]
                  if eid in BY_ID],
        "keeps_items": True,
        "note": taken.get("note", ""),
    }


# ---------------------------------------------------------------------------
# Proofs
# ---------------------------------------------------------------------------

def _better(a, b, direction: str) -> bool:
    """Is `a` strictly better than `b` on a metric read in `direction`."""
    try:
        if direction == "lower":
            return float(a) < float(b)
        return float(a) > float(b)
    except (TypeError, ValueError):
        return False


def missing_items() -> list:
    """The drops this module names that items.py does not carry yet.

    NOT A FAILURE. This module does not own items.py. The list is the bill, and
    DROPS is the specification, written in items.Item's own field order.
    """
    return [row.id for row in DROPS.values() if row.id not in items.BY_ID]


def validate() -> list:
    """Everything that can be checked about five people and one arc. Returns a
    list of problems; empty is the pass condition."""
    problems = []

    # -- the ladder, re-proved rather than trusted
    if RUNG.get(SWEEP_AFTER_BOSS) != len(world.BOSSES) - 1:
        problems.append(
            f"{SWEEP_AFTER_BOSS!r} is rung {RUNG.get(SWEEP_AFTER_BOSS)} of "
            f"{len(world.BOSSES)}, not the second-to-last; the sweep fires on "
            f"the wrong fight")
    if len(RUNG) != len(world.BOSSES):
        problems.append("the rung table does not agree with world.BOSSES")

    # -- the zones
    seen_regions: set = set()
    for zone in ZONES:
        if not zone.regions:
            problems.append(f"{zone.id}: a zone with no regions in it")
        for region in zone.regions:
            if region not in world.REGION_BY_ID:
                problems.append(f"{zone.id}: unknown region {region!r}")
            if region in seen_regions:
                problems.append(f"{region}: in two zones, and a region has "
                                f"one mechanic or none")
            seen_regions.add(region)
        if not zone.verb:
            problems.append(f"{zone.id}: a zone is a verb the player performs; "
                            f"this one has none")

    # -- the people
    seen: set = set()
    for row in ESCORTS:
        where = row.id
        if row.id in seen:
            problems.append(f"duplicate escort {row.id!r}")
        seen.add(row.id)
        person = captives.CAPTIVE_BY_ID.get(row.id)
        if person is None:
            problems.append(f"{where}: not a captive. Every escort is somebody "
                            f"captives.py already carries; this file invents "
                            f"nobody")
            continue
        if row.zone not in ZONE_BY_ID:
            problems.append(f"{where}: unknown zone {row.zone!r}")
        elif person.home not in ZONE_BY_ID[row.zone].regions:
            problems.append(f"{where}: lives in {person.home}, which is not in "
                            f"zone {row.zone!r}")
        if person.boss != row.boss:
            problems.append(f"{where}: captives.py says {person.boss!r} takes "
                            f"them and this file says {row.boss!r}")
        if row.boss not in world.BOSS_BY_ID:
            problems.append(f"{where}: unknown boss {row.boss!r}")
        if row.capture_kind not in ("dungeon", "sweep"):
            problems.append(f"{where}: capture kind {row.capture_kind!r}")
        if row.capture_kind == "dungeon":
            if row.capture_dungeon not in dungeonmod.DUNGEON_BY_ID:
                problems.append(f"{where}: unknown capture dungeon "
                                f"{row.capture_dungeon!r}")
            else:
                plan = dungeonmod.DUNGEON_BY_ID[row.capture_dungeon]
                zone = ZONE_BY_ID.get(row.zone)
                if zone and plan.region not in zone.regions:
                    problems.append(f"{where}: taken in {plan.region}, which "
                                    f"is not in their own zone")
        elif row.capture_dungeon:
            problems.append(f"{where}: the sweep has no dungeon")

        # -- the drop
        if row.drop not in DROPS:
            problems.append(f"{where}: unknown drop {row.drop!r}")
        else:
            drop = DROPS[row.drop]
            if drop.slot not in items.SLOTS:
                problems.append(f"{drop.id}: slot {drop.slot!r} is not an "
                                f"items.SLOTS slot")
            if drop.rarity not in items.RARITIES:
                problems.append(f"{drop.id}: rarity {drop.rarity!r}")
            if drop.effects:
                problems.append(f"{drop.id}: carries effects {sorted(drop.effects)}. "
                                f"A zone item is an overworld verb, not a stat "
                                f"line, and nothing here may buy a look at a "
                                f"problem")
            if not drop.mechanic:
                problems.append(f"{drop.id}: no mechanic, so nothing will ever "
                                f"read it")
            if drop.id in items.BY_ID:
                real = items.BY_ID[drop.id]
                if real.slot != drop.slot:
                    problems.append(f"{drop.id}: items.py says slot "
                                    f"{real.slot!r}, this file says "
                                    f"{drop.slot!r}")
                if real.rarity != drop.rarity:
                    problems.append(f"{drop.id}: items.py says rarity "
                                    f"{real.rarity!r}, this file says "
                                    f"{drop.rarity!r}")

        # -- the item is worse than the person, and the loss is named
        if row.metric:
            for half in ("without", "with_them", "with_item"):
                if row.metric not in getattr(row, half):
                    problems.append(f"{where}: {half} has no {row.metric!r}")
        if row.metric and all(row.metric in getattr(row, half)
                              for half in ("without", "with_them",
                                           "with_item")):
            if not _better(row.with_item[row.metric], row.without[row.metric],
                           row.metric_better):
                problems.append(f"{where}: the item is no better than having "
                                f"nothing on {row.metric!r}")
            if not row.with_them.get("unlimited") and not _better(
                    row.with_them[row.metric], row.with_item[row.metric],
                    row.metric_better):
                problems.append(f"{where}: the item matches or beats the "
                                f"person on {row.metric!r}, and the whole "
                                f"design is that it is worse")
        if not row.metric and not row.lost:
            problems.append(f"{where}: no metric and nothing named as lost, so "
                            f"nothing says what the capture cost")
        for key in row.lost:
            if not row.with_them.get(key):
                problems.append(f"{where}: {key!r} is named as lost but the "
                                f"person did not have it")
            if row.with_item.get(key):
                problems.append(f"{where}: {key!r} is named as lost and the "
                                f"item still has it")
        if row.metric_better not in ("higher", "lower"):
            problems.append(f"{where}: metric_better {row.metric_better!r}")

        # -- the telling
        if not 1 <= len(row.walking) <= 4:
            problems.append(f"{where}: one to four walking lines, not "
                            f"{len(row.walking)}")
        if len(row.capture) != 3:
            problems.append(f"{where}: the capture is three lines, not "
                            f"{len(row.capture)}")
        if not row.narrator:
            problems.append(f"{where}: no narrator line after they are gone")
        if not row.thanks:
            problems.append(f"{where}: nothing said at the cage, and the "
                            f"thank-you is half the point of the rescue")
        if not row.handover:
            problems.append(f"{where}: nothing offered for the next zone")
        if not row.retaken_line:
            problems.append(f"{where}: nothing said when they are taken back")
        if not row.loss_line:
            problems.append(f"{where}: the loss is not said out loud")
        # Rule 7 of the story bible, enforced rather than remembered.
        for line in (row.role, row.verb, row.narrator, row.loss_line,
                     row.handover, row.retaken_line, *row.walking,
                     *row.capture, *row.thanks):
            if "!" in line:
                problems.append(f"{where}: exclamation mark")
                break
        # At least one thing they say at the capture has to be about their own
        # life rather than addressed at the player. Same rule captives.py holds
        # its cage lines to, and for the same reason.
        at_you = sum(1 for line in row.capture
                     if "you" in line.lower().split()[:4])
        if at_you == len(row.capture):
            problems.append(f"{where}: every capture line opens at the player; "
                            f"at least one has to be about their own life")

    # -- coverage
    if len(BY_ZONE) != len(ZONES):
        problems.append("a zone with no escort, or two escorts in one zone")
    rungs = sorted(RUNG.get(row.boss, 0) for row in ESCORTS)
    if len(set(rungs)) != len(rungs):
        problems.append(f"two escorts on the same rung {rungs}, so one rescue "
                        f"would free two zones at once")
    early = [row for row in ESCORTS if row.drop_early]
    if len(early) != 1:
        problems.append(f"{len(early)} items are given before anything is "
                        f"taken; the map is the one that has to be, and it is "
                        f"the only one")
    if not any(row.capture_kind == "sweep" for row in ESCORTS):
        problems.append("nobody is taken at the finale, and the player asked "
                        "for the last boss to take the ones they know")

    # -- the pack
    for region in PACK["regions"]:
        if region not in world.REGION_BY_ID:
            problems.append(f"pack names unknown region {region!r}")
        if ZONE_BY_REGION.get(region) is None:
            problems.append(f"pack fires in {region!r}, which is in no zone")
    if not 0.0 < PACK["chance"] < 1.0:
        problems.append("the pack chance is not a probability")

    # -- the states
    if len(set(STATES)) != 5:
        problems.append("the arc has five states and this is not five")
    for name in STATES:
        if name not in STATE_LABELS:
            problems.append(f"state {name!r} has no label")

    return problems


def counts() -> dict:
    """The numbers, for the self-check and for whoever writes the patch note."""
    return {
        "escorts": len(ESCORTS),
        "zones": len(ZONES),
        "regions_in_zones": sum(len(z.regions) for z in ZONES),
        "regions_total": len(world.REGIONS),
        "drops": len(DROPS),
        "drops_in_catalogue": sum(1 for d in DROPS if d in items.BY_ID),
        "missing_items": missing_items(),
        "rungs": {row.id: RUNG.get(row.boss, 0) for row in ESCORTS},
        "states": len(STATES),
        "lines": sum(len(row.walking) + len(row.capture) + len(row.thanks) + 3
                     for row in ESCORTS),
        "words": sum(len(" ".join([row.role, row.verb, row.narrator,
                                   row.loss_line, row.handover,
                                   row.retaken_line, *row.walking,
                                   *row.capture, *row.thanks]).split())
                     for row in ESCORTS),
        # The two who had to be promoted out of banter.py and quests.GIVERS,
        # and who are held one route downstream of their own village because
        # the region they work in has no boss to take them.
        "promoted": sorted(row.id for row in ESCORTS
                           if row.id in captives.TAKEN_FROM_UPSTREAM),
    }


def self_check() -> dict:
    """Raises on the first thing that is wrong, and otherwise hands back the
    numbers. Tests call `assert zonecompanions.validate() == []`; this is the
    version a human runs from a shell."""
    problems = validate()
    if problems:
        raise AssertionError("zonecompanions.py: " + "; ".join(problems[:8]))
    return counts()


WIRING = """
How the engine picks this up. Five touch points, four of them one line.

THE ORDER IS A REQUIREMENT, NOT A SUGGESTION, and this is the one hazard in
the design that can seize a gate permanently rather than merely look wrong.

    STEP 2 BELOW IS THE ONLY THING THAT GRANTS THE FIVE DROPS. Nothing else in
    the codebase writes them. Greave's `without` column is
    {"drain": 0.0, "open": 0.0, "refill": 0.0, "crankable": False} — a flat
    refusal and the only hard gate in the arc — so `the_gear` is the only other
    way to open a sluice. If the lava channels and sluices of docs/12 §4.3 ever
    ship before this call exists, every sluice in stack_queue_mines is shut
    permanently for a player who has already lost Greave. Measured by
    enumerating the two facts this module derives from — capture dungeon
    cleared, boss beaten — across the four dungeon companions, 1,024 save
    shapes: with advance() called, 1024 of 1024 carry either the person or the
    thing; with it never called, 768 of 1024 carry NEITHER, and 512 of those
    are FREED, which is the worse half — the player went and beat the boss,
    the person went home, and the thing they left never arrived.

    AND STEP 1 AND STEP 2 BOTH COME AFTER items.py. A granted id the catalogue
    has never heard of is not an error anywhere — it is simply invisible:
    engine._item() returns None for it and the loadout loop skips anything it
    cannot resolve, so a granted lamp cannot be looked at and skate_irons, slot
    "feet", can never be worn. docs/12 §4.1 makes ice control conditional on
    skate_irons being EQUIPPED, which is a slot that cannot be filled until the
    rows land. missing_items() is the bill; it must be empty first.

    So: items.py rows -> DEFAULT_STATE key -> advance() per region entry ->
    only then the terrain work in overworld.js (O4, O7, O9).

1. STATE
   engine.DEFAULT_STATE["escorts"] = zonecompanions.new_escort_state()
   _merge forward-fills, so an existing save gains the key on load with nobody
   latched — which is the correct starting position, because state_of() derives
   the same answer from cleared_bosses, dungeons_cleared and inventory whether
   the latch is there or not.

2. EVERY OVERWORLD TICK, OR EVERY REGION ENTRY
       zonecompanions.advance(self.state)
   Idempotent, cheap, and returns {"events": [...], "states": {...}}. Events
   carry kind in {"given", "taken", "kept", "sweep"}; a tick where nothing
   changed returns none of them. This is the only call that writes.

3. WHO IS WALKING BESIDE YOU
       row = zonecompanions.escort_in(self.state, region_id)
   {} when nobody is. Feed it to overworld.setEscort(row). The mechanics read
   row["with_them"] and the inventory reads row["with_item"]; nothing on the
   client needs a table of its own.

4. THE CAPTURE, ON THE SEAL
   In the handler that resolves a dungeon run, on the transition of
   dungeons.progress(d, run)["seal"]["met"] to true in a capture dungeon,
   resolved on the player's RETURN TO THE OVERWORLD so the scene has ground to
   play on:
       scene = zonecompanions.capture(self.state, escort_id)
   It latches, grants the drop in the same transaction, and returns the scene.
   {} when there is nothing to do. advance() will do it anyway on the next tick
   if this call site is never written, one tick late and otherwise identical.

5. THE RESCUE
   Nothing. captives.free(state, boss_id) already frees them, pays through
   quests.reward_for, banks the boon and the route and returns {pay, story,
   world}. state_of() reads the result. The only line worth adding is the one
   the design asks for:
       state["escort"] = None   # they are home; they do not walk with you again

THE PANEL
   zonecompanions.snapshot(state, region_id) is one call for everything: five
   rows, the five states, who is here, what the player is carrying, and whether
   the sweep has fired.
"""


CONTRACT = """
What zonecompanions.py needs from files it does not own, stated precisely so
nobody has to guess.

OWED BY items.py — FIVE ITEM ROWS. LANDED. missing_items() is now empty.

  the_slate     trinket  UNCOMMON  NEUTRAL  icon scroll
  the_lamp      trinket  RARE      BRUTE    icon lantern
  skate_irons   feet     RARE      COLD     icon boots
  the_dart      trinket  RARE      POISON   icon thorn
  the_gear      trinket  RARE      FIRE     icon gear

  DROPS in this file is the specification, written in items.Item's own field
  order, and validate() cross-checks slot and rarity against items.BY_ID. Call
  missing_items() to re-read the bill; an empty list is the pass condition and
  is what it returns today.

  They carry source="quest" in the catalogue, and items.roll_drop() excludes
  that source from the ordinary loot pool the same way it excludes "upgrade".
  That is not decoration: with them in the pool, measured, 158 of 4,275 rolled
  items were one of these five — the Lamp arriving out of a random chest before
  Josa Fell has said a word. Handed over is not found.

  Until the rows existed NOTHING RAISED, which is what made the gap hard to
  see: state_of() and advance() work on item ids the catalogue has never heard
  of, because the inventory is a list of strings. What did not work was
  LOOKING at one — engine._item() returned None, the loadout loop skipped it,
  and equip refused with "you do not carry that".

  EVERY ONE OF THEM CARRIES effects={}. That is not an oversight. A zone item
  is an overworld verb — a radius, a grip, a thinned pack, a gate — and none of
  them may buy a look at a problem, a weakness or an answer, which is the same
  refusal captives.BOON_EFFECTS_REFUSED makes about the boons. validate() fails
  the build if one of them grows a stat line here.

OWED BY overworld.js AND tiles.js — the four mechanics. Both files are owned by
a concurrent pass and neither is touched here. Everything they need is data on
the Escort row:

  row["without"] / row["with_them"] / row["with_item"]  the three columns
  row["lost"]                                           what the item is not

  the Dark   radius 2 / 6 (+2 facing offset) / 5
  the Snow   control False / True / True, speed 1.0 / 1.0 / 1.35,
             calls_exit False / True / False
  the Green  PACK, above: chance 0.22, size 3-5, thinning to one
  the Fire   drain 0 / 1.5 / 4.0, open 0 / 20.0 / 8.0, refill 1.5

OWED BY engine.py — one state key and one call per tick. See WIRING. LANDED:
engine.py imports this module, DEFAULT_STATE carries STATE_KEY, and
Game._advance_escorts() runs on both region-change sites and in _resolve_boss.

OWED BY NOBODY — and this is the point of the file:

  no new boss      finalexam.BOSS_LADDER rung N is the Nth entry of
                   world.BOSSES, so appending to it would renumber every crutch
                   in the game. All five hang off bosses that already exist, at
                   rungs 2, 4, 6, 8 and 14.
  no new key       world.KEYS is fourteen rows and the Standing Portal wants
                   all fourteen. Untouched.
  no new cast      all five are captives.CAPTIVES rows.
  no new combat    the pack is incantation.make_context([a, b, c, d]), which
                   already fields several enemies at once and says so in its
                   own docstring.
  no new reward    captives.free() already pays through quests.reward_for.

WHAT COULD NOT BE RESOLVED, said plainly rather than guessed at:

  the rescue gift  The design recommends lanternshoes for Halla Vane and
                   cinder_greaves for Greave. captives.validate() refuses both,
                   for two rules it has held since it was written: a cage pays
                   ONE piece of gear, and a gift names the region the cage is
                   in. Oskar Lind already hands over wayfarers out of the
                   Canopy and Jessamy Roke already hands over earthed_sabatons
                   out of the Wastes, and those are the cages Halla and Greave
                   are in. Both new rows therefore carry gift="". Their
                   handover is prose — Escort.handover — and the material half
                   is the co-captive's, which is the same reward the boss
                   already paid. If a later pass wants them unique, mint two
                   items and move one field each; nothing else changes.

  the sweep        captives.retake(state, ids) suspends boons and never touches
                   items. Taking a mechanic away at rung 13 would put the last
                   two bosses behind a wall built out of a cutscene, and this
                   game does not put a measurement behind a locked door.
"""
