"""Dungeons: room networks whose shape is the lesson.

A dungeon here is not a corridor with monsters in it. The floor plan is the
teaching device. The Graph Wastes hand you a lattice and a shortcut that is
literally the shortest path; the Recursive Forest nests rooms inside rooms and
makes you carry the inner answer back out; the Stack Mines will only let you
leave in the reverse of the order you entered. If a player learns the building,
they have learned the pattern, and they learned it with their feet before they
ever wrote a line of it.

Three invariants hold everywhere in this module, and `audit()` proves each one
on every dungeon it is handed:

  1. A dungeon is deterministic. `generate("hollow_of_keys")` returns the same
     place every time, so a player can leave, come back tomorrow, and recognise
     where they left the key.
  2. Locks are entry-only. A door checks its key when you walk *inward*; it
     never checks when you walk out. That single rule is what makes "the exit
     is reachable from every room" true by construction rather than by luck.
  3. Nothing dead-ends. Every encounter room carries a relent chain that
     descends to the dungeon's floor difficulty, every room has at least one
     neighbour, and `options()` is never empty. A player who cannot clear a
     room can always leave it, take another branch, or accept an easier form
     of the same problem.

The boss is assembled per run rather than authored, so the second descent is a
different fight. Modifiers change tactics, never only numbers: a boss that
"resists brute force" carries a real performance trial, and a boss that is
"veiled" cannot be damaged until its weakness is probed. No modifier, item or
treasure in here supplies any part of an answer.

Dungeons are Adventure Mode only. Interview Mode measures, and a place that
hands out shrines, codex pages and hint-bearing mentors cannot measure anything.

Two systems are referenced by string id and never imported: `gauntlet.bestiary`
(enemy bodies) and `gauntlet.incantation` (typed-Python attacks). Both are being
built by another team; a blueprint names its bestiary id and leaves resolution
to whoever owns that module.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

from . import config, curriculum, items, puzzles, world
from . import skills as skillmod
from .corpus.schema import PATTERNS as CORPUS_PATTERNS

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

ROOM_KINDS = (
    "ENTRANCE",    # the way in, and the way out; never holds a fight
    "ENCOUNTER",   # a corpus problem, resolved by difficulty and pattern
    "PUZZLE",      # one of the six kinds in puzzles.PUZZLE_KINDS
    "TREASURE",    # a drop rolled off items.roll_drop
    "VAULT",       # treasure behind a lock, always the better haul
    "STORY",       # empty of enemies, not empty of meaning: lore or a codex page
    "SHRINE",      # a recall question; restores stamina and focus
    "JUNCTION",    # connective tissue, so the map breathes
    "BOSS",        # the chamber, sealed until enough of the floor is cleared
)

# Kinds that never ask the player to solve anything, so they are always passable.
_FREE_KINDS = frozenset({"ENTRANCE", "TREASURE", "STORY", "JUNCTION"})

DIFFICULTY_LADDER = ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE")

ARCHETYPES = {
    "warren": "Burrowed and loopy. Short branches, sudden reconnections, and "
              "more than one way back.",
    "spiral": "One descending coil. Every turn is deeper than the last and the "
              "way out is long until you find the drop.",
    "cross":  "A hub with arms. You will come back to the middle more than once, "
              "and the arms do not know about each other.",
    "ring":   "An outer circuit around a core. Two ways round, one way in.",
    "gauntlet": "Segments in series, each with parallel lanes. There is always "
                "another lane, which is the point.",
    "vault":  "A spine with sealed cells hanging off it. The spine is free. The "
              "cells are not.",
    "nest":   "Rings inside rings. You go in, and you come back out carrying "
              "whatever the inner ring gave you.",
    "branch": "Splits that never rejoin. To take the other fork you must climb "
              "back to the fork.",
    "lattice": "A grid with holes in it. Many routes, of many lengths, and only "
               "one of them is shortest.",
}

# What a layout rule does to the finished map. Each is the physical form of a
# chapter's idea; the text is what the player is told on entering.
LAYOUT_RULES = {
    "indent_depth": "Depth is meaning here. A room sits as deep as the statement "
                    "it holds, and an unfinished statement keeps the next one shut.",
    "keyed_vaults": "Every door answers to exactly one key, and to no other. "
                    "Holding the right key opens it instantly, from anywhere.",
    "anagram_ring": "Several halls are the same hall with its letters moved. "
                    "Clear any one of them and the whole group is cleared.",
    "zero_indexed": "The alcoves are numbered from zero. The last one is always "
                    "one short of the count, and the count is written on the door.",
    "sliding_frame": "A lit frame follows you. Stepping forward widens it on the "
                     "right; when the ward breaks it gives ground on the left.",
    "converging_ends": "Two lanterns, one at each end of the circuit. They walk "
                       "toward each other and the chamber is where they meet.",
    "lifo_exit": "The carts unload from the top. You leave this mine in the exact "
                 "reverse of the order you entered it, or you do not leave.",
    "rotating_grid": "The keep turns a quarter for every few rooms cleared. The "
                     "doors do not move. Your map does.",
    "recursive_nest": "Each ring contains a smaller ring. Go in, solve the small "
                      "one, come back out carrying what it found.",
    "binary_branch": "Every fork splits exactly twice and the forks never rejoin. "
                     "The other branch is reached by climbing back to the fork.",
    "shortest_path": "Many roads connect these ruins. Exactly one of them is "
                     "shortest, and finding it is the shortcut home.",
    "memo_tiles": "A room you have cleared stays lit, and a lit room is free to "
                  "cross for as long as this place stands.",
    "defect_hunt": "One room on each ring is subtly wrong. Finding which is the "
                   "whole job; the rest of the ward is honest.",
    "doubling_floors": "Each floor holds twice the rooms of the floor below. You "
                       "cannot brute-force the top. You were never meant to.",
    "unlabelled": "Nothing here says what it wants. No signposts, no pattern "
                  "names, no region colours. Just rooms.",
    "timed_heats": "Pens in series, and a clock overhead you can hear from "
                   "all of them. Nothing down here explains itself.",
}


# ---------------------------------------------------------------------------
# The authored dungeons
# ---------------------------------------------------------------------------
#
# Tier drives both the ceiling on room difficulty and the reward scale, and it
# tracks the region's place in the curriculum rather than a separate ladder.

@dataclass(frozen=True)
class DungeonPlan:
    id: str
    name: str
    region: str
    chapter: str                 # curriculum.CHAPTERS id this dungeon serves
    tier: int                    # 1..5; reward and difficulty scale
    archetype: str
    rule: str
    size: int                    # target room count before repair
    floor: str                   # the lowest difficulty a room here can relent to
    floors: int                  # depth `generate` guarantees; see FLOOR_ATTEMPTS
    patterns: tuple              # corpus patterns this dungeon may demand
    blurb: str
    lesson: str                  # what the building itself teaches
    motif: tuple                 # room nouns, for naming
    lore: tuple                  # lines for STORY rooms
    codex: tuple                 # story.CODEX ids a STORY room may hand over
    boss_epithet: str            # slotted into the assembled boss name


DUNGEONS = (
    DungeonPlan(
        id="halfwritten_barrow", name="The Half-Written Barrow",
        region="fields_of_syntax", chapter="fluency", tier=1,
        archetype="warren", rule="indent_depth", size=14, floor="GUIDED",
        floors=3,
        patterns=("STRING", "ARRAY", "SIMULATION"),
        blurb="A barrow dug by someone who stopped mid-sentence and never came back.",
        lesson="Rooms sit as deep as the block they belong to. Walking this place "
               "is reading an indented program with your feet.",
        motif=("Stub", "Clause", "Unfinished Hall", "Draft Chamber", "Margin"),
        lore=("Someone laid these walls a line at a time and left a colon hanging "
              "at the end of the last one. The barrow has been waiting for the "
              "indented block ever since.",
              "A slate by the door: FIRST MAKE IT RUN. Beneath it, in a different "
              "hand and much later: THAT IS STILL THE ADVICE.",
              "Every corridor here is exactly four paces wide. Nobody has ever "
              "found this funny except the Archivist, who finds it very funny."),
        codex=("codex_village",),
        boss_epithet="of the Unclosed Bracket",
    ),
    DungeonPlan(
        id="hollow_of_keys", name="The Hollow of Keys",
        region="hashmap_highlands", chapter="counting", tier=2,
        archetype="vault", rule="keyed_vaults", size=20, floor="TUTORIAL",
        floors=8,
        patterns=("HASH_MAP", "SET", "STRING", "ARRAY", "SORTING"),
        blurb="A spine of open corridor with sealed cells hanging off it, one key each.",
        lesson="One key, one door, found instantly. That is what a dictionary is, "
               "and the alternative is trying every key on every door.",
        motif=("Cell", "Keyed Vault", "Tally Room", "Bucket", "Ledger"),
        lore=("The cells were built so that no key ever fits two doors. The "
              "builders considered ambiguity a structural defect, which it is.",
              "A warden's note: I TRIED EVERY KEY ON EVERY DOOR FOR NINE YEARS. "
              "THEN SOMEONE LABELLED THEM. Nine years is the cost of a linear scan.",
              "There are more cells here than keys you will ever carry. You are "
              "not meant to open all of them. You are meant to know which one."),
        codex=("codex_vaults",),
        boss_epithet="of Collisions",
    ),
    DungeonPlan(
        id="anagram_deeps", name="The Anagram Deeps",
        region="stringwood_labyrinth", chapter="idiom", tier=2,
        archetype="ring", rule="anagram_ring", size=20, floor="TUTORIAL",
        floors=10,
        patterns=("STRING", "HASH_MAP", "SET", "SORTING", "TWO_POINTER"),
        blurb="A circuit of halls that keep rearranging their own letters.",
        lesson="Several halls are one hall with its letters moved. Sort the "
               "letters and they collapse into a single clearing.",
        motif=("Grove Hall", "Lettered Round", "Spelling Room", "Shuffled Nave"),
        lore=("The halls rearrange nightly and the Scribe maps them anyway, by "
              "sorting the letters on each door. Same sorted key, same hall.",
              "Carved above the circuit: TWO WORDS THAT SORT ALIKE ARE THE SAME "
              "WORD WEARING A DIFFERENT COAT.",
              "A previous surveyor walked the ring eleven times counting doors. "
              "The Scribe walked it once, counting letters."),
        codex=("codex_vaults",),
        boss_epithet="of Rearrangement",
    ),
    DungeonPlan(
        id="sunken_index", name="The Sunken Index",
        region="array_caverns", chapter="structures", tier=2,
        archetype="gauntlet", rule="zero_indexed", size=22, floor="TUTORIAL",
        floors=12,
        patterns=("ARRAY", "HASH_MAP", "TWO_POINTER", "PREFIX_SUM", "SORTING"),
        blurb="Numbered alcoves in series, flooded at the far end.",
        lesson="The alcoves start at zero, so the last one is one short of the "
               "count. Half the drownings here were off-by-one.",
        motif=("Alcove", "Numbered Shelf", "Indexed Hall", "Stack of Slates"),
        lore=("The first alcove is the zeroth. Surveyors who assume otherwise "
              "arrive at the last door holding a number nobody will accept.",
              "Waterline on the wall, with a note: LEN MINUS ONE. Someone has "
              "underlined MINUS ONE hard enough to score the stone.",
              "A slice taken from the middle of this place leaves the two ends "
              "intact and unaware. That is the whole trick of slicing."),
        codex=("codex_index",),
        boss_epithet="of the Final Index",
    ),
    DungeonPlan(
        id="the_long_draw", name="The Long Draw",
        region="sliding_window_marsh", chapter="scanning", tier=3,
        archetype="gauntlet", rule="sliding_frame", size=24, floor="EASY",
        floors=12,
        patterns=("SLIDING_WINDOW", "HASH_MAP", "SET", "STRING", "TWO_POINTER"),
        blurb="A causeway across the marsh, lit only by a frame that travels with you.",
        lesson="The lit band widens as you advance and gives ground behind you "
               "when the ward breaks. It never once goes back to the start.",
        motif=("Causeway Span", "Lit Reach", "Reed Gate", "Frame Post"),
        lore=("The frame was built to measure a lake. The lake became a marsh and "
              "the frame simply kept measuring, which is why it still works.",
              "Marsh-warden's rule, cut into a post: WIDEN RIGHT. WHEN IT BREAKS, "
              "GIVE GROUND LEFT. NEVER CARRY IT BACK.",
              "Every traveller who restarted the crossing from the beginning is "
              "still crossing. The marsh is patient and the causeway is long."),
        codex=("codex_window",),
        boss_epithet="of the Broken Ward",
    ),
    DungeonPlan(
        id="converging_span", name="The Converging Span",
        region="twin_pointer_pass", chapter="scanning", tier=3,
        archetype="ring", rule="converging_ends", size=22, floor="EASY",
        floors=12,
        patterns=("TWO_POINTER", "ARRAY", "SORTING", "STRING", "BINARY_SEARCH"),
        blurb="A bridge-ring with a lantern walking in from each end.",
        lesson="Two walkers, opposite ends, neither ever turning back. Where they "
               "meet is the answer, and they meet exactly once.",
        motif=("Span", "Lantern Post", "Cable Round", "Meeting Stone"),
        lore=("Two lanterns are lit at opposite ends each dusk. Neither walker "
              "turns around. The Ranger insists this is the entire technique.",
              "Cut into the meeting stone: MOVE THE SHORTER WALL. The taller one "
              "is not what is limiting you and never was.",
              "A walker who doubled back once is remembered here, fondly, as a "
              "cautionary tale about quadratic time."),
        codex=("codex_search",),
        boss_epithet="of the Widening Gap",
    ),
    DungeonPlan(
        id="ninth_cart", name="The Ninth Cart",
        region="stack_queue_mines", chapter="order", tier=3,
        archetype="spiral", rule="lifo_exit", size=22, floor="EASY",
        floors=15,
        patterns=("STACK", "QUEUE", "ARRAY", "STRING", "SIMULATION", "HASH_MAP"),
        blurb="A coil of shafts where the carts only unload from the top.",
        lesson="You leave in the reverse of the order you entered. Nesting is a "
               "stack, and the mine enforces it with rock.",
        motif=("Shaft", "Cart Landing", "Coil Gallery", "Winding Floor"),
        lore=("Nine carts went down. Eight came up, in reverse order, without "
              "incident. The ninth is still down there, out of order, waiting.",
              "Chalked at the winch: LAST IN, FIRST OUT. Beneath it, the lift "
              "schedule, which is first in, first out, and the two have never "
              "once been confused by anyone who works here.",
              "Every open bracket in the realm is a cart that went down. Every "
              "close is one that came back. The mine keeps count whether or not "
              "you do."),
        codex=("codex_order",),
        boss_epithet="of the Unmatched Bracket",
    ),
    DungeonPlan(
        id="turning_keep", name="The Turning Keep",
        region="matrix_citadel", chapter="order", tier=4,
        archetype="lattice", rule="rotating_grid", size=25, floor="EASY",
        floors=7,
        patterns=("MATRIX", "ARRAY", "SIMULATION", "BFS", "DFS"),
        blurb="Perfect rows and columns that turn a quarter while you stand in them.",
        lesson="The doors do not move when the keep turns. Your map does. Row "
               "becomes column, and the transpose was the rotation all along.",
        motif=("Row Hall", "Column Gallery", "Quarter Turn", "Ordered Court"),
        lore=("The keep turns and the Golem does not consider this remarkable. "
              "Rows become columns. Nothing is created; nothing is copied.",
              "The masons who rebuilt this in place, without a second keep to "
              "copy into, are the reason the citadel still stands. Space is not "
              "free and they knew it.",
              "Transpose, then reverse each row. Two moves. The Cartographer has "
              "written this on nine walls and will write it on a tenth."),
        codex=("codex_index",),
        boss_epithet="of the Quarter Turn",
    ),
    DungeonPlan(
        id="inner_grove", name="The Inner Grove",
        region="recursive_forest", chapter="recursion", tier=4,
        archetype="nest", rule="recursive_nest", size=24, floor="EASY",
        floors=14,
        patterns=("RECURSION", "TREE", "DFS", "STRING", "ARRAY"),
        blurb="Rings of trees, each ring containing a smaller and identical ring.",
        lesson="Go in, let the smaller ring solve the smaller thing, and come out "
               "carrying what it found. That is the whole of recursion.",
        motif=("Ring Clearing", "Inner Grove", "Returning Path", "Base Hollow"),
        lore=("Each clearing holds a smaller copy of the forest. You enter, you "
              "wait, you leave carrying what the smaller one worked out.",
              "The Druid was asked where the smallest clearing is. The Druid said "
              "the base case is elsewhere and changed the subject.",
              "A grove without a base hollow is a grove you never leave. Several "
              "such groves are marked on the old maps, in red."),
        codex=("codex_recursion",),
        boss_epithet="of the Missing Base Case",
    ),
    DungeonPlan(
        id="split_canopy", name="The Split Canopy",
        region="binary_tree_canopy", chapter="recursion", tier=4,
        archetype="branch", rule="binary_branch", size=23, floor="EASY",
        floors=4,
        patterns=("TREE", "DFS", "BFS", "RECURSION", "QUEUE", "STACK"),
        blurb="Walkways that fork exactly twice and never, ever rejoin.",
        lesson="To take the other branch you climb back to the fork. That climb "
               "is the call stack, and you are standing in it.",
        motif=("Fork", "Left Limb", "Right Limb", "Leaf Platform", "Crown Walk"),
        lore=("Every fork splits twice and the limbs never meet again. Walkers "
               "who expected a shortcut across are still up there, expecting.",
              "A leaf is a platform with nothing above it. A platform with one "
              "walkway above it is not a leaf, however lonely it looks.",
              "Rings of light climb this canopy level by level. A single "
              "committed rope climbs one limb to its end. Both are surveys; they "
              "answer different questions."),
        codex=("codex_recursion", "codex_search"),
        boss_epithet="of the False Leaf",
    ),
    DungeonPlan(
        id="lattice_of_ruin", name="The Lattice of Ruin",
        region="graph_wastes", chapter="traversal", tier=4,
        archetype="lattice", rule="shortest_path", size=28, floor="EASY",
        floors=7,
        patterns=("BFS", "DFS", "MATRIX", "HASH_MAP", "QUEUE", "SET"),
        blurb="Ruins joined by more roads than anyone needs, of wildly varying length.",
        lesson="Every ruin connects to several others. Exactly one route is "
               "shortest, and the rings of light find it for free.",
        motif=("Ruin Node", "Broken Junction", "Road Head", "Cistern"),
        lore=("The roads were laid by people who never asked how far. The rings "
              "of light ask nothing else, and always answer first.",
              "A single committed path will find every road here eventually. It "
              "will not tell you which was shortest, and it never claimed to.",
              "Mark a ruin as seen when you put it in the queue, not when you "
              "arrive. The wastes have swallowed whole surveys over that."),
        codex=("codex_search",),
        boss_epithet="of the Scenic Route",
    ),
    DungeonPlan(
        id="lit_tiles", name="The Hall of Lit Tiles",
        region="dp_ruins", chapter="optimisation", tier=5,
        archetype="lattice", rule="memo_tiles", size=28, floor="EASY",
        floors=7,
        patterns=("DP", "ARRAY", "STRING", "MATRIX", "RECURSION", "GREEDY"),
        blurb="A floor of tiles, most of them dark, a few of them remembering.",
        lesson="A tile you have solved stays lit and costs nothing to cross "
               "again. Solve it twice and you have simply paid twice.",
        motif=("Tile Court", "Lit Row", "Remembered Hall", "Table Floor"),
        lore=("The ruins keep what they have already worked out. Walk a lit tile "
              "for free, for as long as this place stands.",
              "The unlit floor can be crossed by trying every route. It takes a "
              "length of time best described in the plural of centuries.",
              "Somebody here solved the same tile four thousand times and called "
              "it thorough. The Oracle has a word for it and the word is rent."),
        codex=("codex_cost",),
        boss_epithet="of Recomputation",
    ),
    DungeonPlan(
        id="cracked_ward", name="The Cracked Ward",
        region="debugging_dungeon", chapter="craft", tier=3,
        archetype="cross", rule="defect_hunt", size=21, floor="TUTORIAL",
        floors=5,
        patterns=("DEBUGGING", "TESTING", "ARRAY", "HASH_MAP", "STRING", "SIMULATION"),
        blurb="The Armorer's cells, where broken programs are kept until someone reads them.",
        lesson="One room on each arm is subtly wrong and the rest are honest. "
               "Finding which is the job. Nothing else repairs armour.",
        motif=("Cell", "Repair Bay", "Mending Arm", "Failing Hall"),
        lore=("Cracked plate hangs on every wall. Each crack is a defect in some "
              "program, and there is exactly one way to close it.",
              "The Armorer's rule, hammered into the anvil: READ THE FAILING "
              "INPUT. THEN TRACE IT BY HAND. There is no second rule.",
              "A suite every wrong answer passes is not a suite. The Testsmith "
              "keeps such a suite on the wall here, as a warning."),
        codex=("codex_armour",),
        boss_epithet="of It Works On My Machine",
    ),
    DungeonPlan(
        id="doubling_stair", name="The Doubling Stair",
        region="complexity_tower", chapter="optimisation", tier=5,
        archetype="branch", rule="doubling_floors", size=26, floor="EASY",
        floors=4,
        patterns=("COMPLEXITY", "BINARY_SEARCH", "HEAP", "SORTING", "DP", "ARRAY"),
        blurb="A stairwell where each floor holds twice the rooms of the one below.",
        lesson="You cannot clear the top floor by clearing every room. The stair "
               "that halves the problem is the only one that reaches it.",
        motif=("Landing", "Doubled Floor", "Halving Stair", "Counting Room"),
        lore=("Each floor holds twice the rooms of the floor beneath. This is "
              "architecture, not cruelty, and it was signed off deliberately.",
              "Sequential work adds. Nested work multiplies. The whole tower is "
              "that one sentence, built out of stone at considerable expense.",
              "The Oracle's stair halves what remains at every step. Fifty floors "
              "cost six steps. Nobody believes this until they climb it."),
        codex=("codex_cost", "codex_gates"),
        boss_epithet="of the Quadratic Hide",
    ),
    DungeonPlan(
        id="unlabelled_halls", name="The Unlabelled Halls",
        region="null_kings_castle", chapter="gauntlet", tier=5,
        archetype="warren", rule="unlabelled", size=26, floor="EASY",
        floors=5,
        patterns=(),                      # empty means every permitted pattern
        blurb="Rooms with nothing written on them at all.",
        lesson="Nothing here tells you what it wants. Recognition is the fight, "
               "and recognition is what the outside will ask for too.",
        motif=("Hall", "Grey Room", "Quiet Chamber", "Unmarked Landing"),
        lore=("No signposts. No colours. No pattern names over the doors. It is "
              "not cruelty, it is the only honest arrangement.",
              "The Null King did not break the language. He removed its names. A "
              "thing nobody can name is indistinguishable from a ruin.",
              "You are expected to say what a room is before you fight it. That "
              "expectation follows you out of here and into every room after."),
        codex=("codex_castle", "codex_source"),
        boss_epithet="of the Withheld Name",
    ),
    DungeonPlan(
        id="under_arena", name="Under the Arena",
        region="coding_coliseum", chapter="craft", tier=5,
        archetype="gauntlet", rule="timed_heats", size=21, floor="MEDIUM",
        floors=10,
        patterns=(),                      # empty means every permitted pattern
        blurb="Holding pens under the sand, and the clock is audible in all of them.",
        lesson="Recall you cannot reach at speed is recall you do not have. The "
               "pens ask the same things the regions asked, with the clock on.",
        motif=("Pen", "Holding Cell", "Heat", "Sand Gate", "Waiting Room"),
        lore=("The pens were dug so a fighter could hear the clock before ever "
              "seeing it. The Chronomancer considers this the whole curriculum.",
              "A slate by the third gate: SLOW AND RIGHT BEATS FAST AND WRONG. "
              "Underneath, later: AND FAST AND RIGHT BEATS BOTH, SO GET ON.",
              "Nobody is coached under the arena. The silence is not cruelty; it "
              "is the only honest rehearsal for a room with a stranger in it."),
        codex=("codex_gates",),
        boss_epithet="of the Audible Clock",
    ),
)

DUNGEON_BY_ID = {d.id: d for d in DUNGEONS}
DUNGEONS_BY_REGION: dict = {}
for _plan in DUNGEONS:
    DUNGEONS_BY_REGION.setdefault(_plan.region, []).append(_plan.id)


def dungeons_for_region(region_id: str) -> list:
    """Dungeon ids sitting in a region, in authored order."""
    return list(DUNGEONS_BY_REGION.get(region_id, ()))


# ---------------------------------------------------------------------------
# Map structures
# ---------------------------------------------------------------------------

@dataclass
class Lock:
    """A door. `side` is the room the lock guards, and it is guarded on entry
    only — walking out through a locked door is always free. That asymmetry is
    what makes the exit reachable from everywhere, so nothing else in this file
    is allowed to weaken it."""
    key_id: str
    name: str
    side: int
    tell: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Passage:
    a: int
    b: int
    kind: str = "PASSAGE"        # PASSAGE | SHORTCUT
    lock: Lock | None = None
    revealed_by: int = -1        # -1: always open. Otherwise: clear that room first.

    def other(self, room_id: int) -> int:
        return self.b if room_id == self.a else self.a

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Room:
    id: int
    kind: str
    name: str
    depth: int
    x: int
    y: int
    blurb: str = ""
    encounter: dict = field(default_factory=dict)   # request; the engine resolves it
    treasure: dict = field(default_factory=dict)
    codex: str = ""
    story: str = ""
    shrine_skill: str = ""
    key_id: str = ""             # clearing this room hands over this key
    seal: dict = field(default_factory=dict)        # BOSS only
    group: str = ""              # rooms sharing a group clear together
    tags: list = field(default_factory=list)
    rule_data: dict = field(default_factory=dict)

    @property
    def demands_solving(self) -> bool:
        return self.kind not in _FREE_KINDS

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Dungeon:
    id: str
    name: str
    region: str
    chapter: str
    tier: int
    archetype: str
    rule: str
    seed: int
    blurb: str
    lesson: str
    floor: str
    patterns: list
    rooms: list
    passages: list
    entrance: int
    boss_room: int
    max_depth: int
    shortest_path: list = field(default_factory=list)
    rule_note: str = ""

    # -- lookups -----------------------------------------------------------
    def room(self, room_id: int) -> Room:
        return self.rooms[room_id]

    def passages_at(self, room_id: int) -> list:
        return [p for p in self.passages if p.a == room_id or p.b == room_id]

    def neighbours(self, room_id: int) -> list:
        return [p.other(room_id) for p in self.passages_at(room_id)]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Dungeon":
        rooms = [Room(**r) for r in data["rooms"]]
        passages = []
        for p in data["passages"]:
            lock = p.get("lock")
            passages.append(Passage(a=p["a"], b=p["b"], kind=p.get("kind", "PASSAGE"),
                                    lock=Lock(**lock) if lock else None,
                                    revealed_by=p.get("revealed_by", -1)))
        rest = {k: v for k, v in data.items() if k not in ("rooms", "passages")}
        return cls(rooms=rooms, passages=passages, **rest)


# ---------------------------------------------------------------------------
# Layout generators
# ---------------------------------------------------------------------------
#
# Each returns (coords, edges): coords is a list of (x, y) indexed by room id,
# edges is a list of (a, b) pairs. Room 0 is always the entrance. Generators may
# return fewer rooms than asked for when the grid boxes them in; the pipeline
# repairs connectivity afterwards and reports the real count rather than the
# requested one.

_DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def _grow(rng, size, *, loop_p, parent_pick):
    """Shared random-growth core. `parent_pick` decides how the shape sprawls:
    picking the newest room makes corridors, picking any room makes warrens."""
    coords = [(0, 0)]
    taken = {(0, 0): 0}
    edges = []
    stalls = 0
    while len(coords) < size and stalls < 400:
        parent = parent_pick(rng, len(coords))
        px, py = coords[parent]
        placed = False
        for dx, dy in rng.sample(_DIRS, len(_DIRS)):
            spot = (px + dx, py + dy)
            if spot in taken:
                continue
            new_id = len(coords)
            coords.append(spot)
            taken[spot] = new_id
            edges.append((parent, new_id))
            placed = True
            break
        stalls = 0 if placed else stalls + 1

    # Loop edges: any two rooms that ended up adjacent on the grid may join.
    # Loops are what turn a tree into a place you can get out of two ways.
    for (x, y), rid in list(taken.items()):
        for dx, dy in _DIRS[:2]:
            other = taken.get((x + dx, y + dy))
            if other is None:
                continue
            if (rid, other) in edges or (other, rid) in edges:
                continue
            if rng.random() < loop_p:
                edges.append((rid, other))
    return coords, edges


def _layout_warren(rng, size):
    return _grow(rng, size, loop_p=0.30,
                 parent_pick=lambda r, n: r.randrange(n))


def _layout_spiral(rng, size):
    """One descending coil, with the odd short stub off the turns."""
    coords, edges = [(0, 0)], []
    taken = {(0, 0)}
    x = y = 0
    leg, direction, step = 2, 0, 0
    while len(coords) < size:
        dx, dy = _DIRS[direction % 4]
        for _ in range(leg):
            if len(coords) >= size:
                break
            x, y = x + dx, y + dy
            if (x, y) in taken:
                continue
            taken.add((x, y))
            edges.append((len(coords) - 1, len(coords)))
            coords.append((x, y))
        direction += 1
        step += 1
        if step % 2 == 0:
            leg += 1
    # Stubs: a coil with nothing hanging off it is a queue, not a place.
    spine = list(range(1, len(coords) - 1))
    rng.shuffle(spine)
    for parent in spine[:max(1, size // 7)]:
        px, py = coords[parent]
        for dx, dy in rng.sample(_DIRS, 4):
            spot = (px + dx, py + dy)
            if spot in taken:
                continue
            taken.add(spot)
            edges.append((parent, len(coords)))
            coords.append(spot)
            break
    return coords, edges


def _layout_cross(rng, size):
    """A hub with arms that do not know about each other."""
    coords, edges = [(0, 0)], []
    arms = 4
    per_arm = max(2, (size - 1) // arms)
    tips = []
    for index, (dx, dy) in enumerate(_DIRS):
        prev = 0
        length = per_arm + rng.randint(-1, 1)
        for step in range(1, max(2, length) + 1):
            if len(coords) >= size:
                break
            coords.append((dx * step, dy * step))
            edges.append((prev, len(coords) - 1))
            prev = len(coords) - 1
        tips.append(prev)
        # one blind alcove per arm, at a random point along it
        if len(coords) < size and prev != 0:
            bx, by = coords[prev]
            side = _DIRS[(index + 1) % 4]
            coords.append((bx + side[0], by + side[1]))
            edges.append((prev, len(coords) - 1))
    if rng.random() < 0.5 and len(tips) >= 2:
        edges.append((tips[0], tips[2]))       # one arm-to-arm loop, sometimes
    return coords, edges


def _layout_ring(rng, size):
    """An outer circuit around a core: two ways round, one way in."""
    ring_len = max(6, int(size * 0.6))
    core_len = max(2, size - ring_len - 1)
    coords, edges = [(0, 0)], []
    radius = max(2, ring_len // 4)
    for i in range(ring_len):
        angle = (i / ring_len) * 6.283185
        x = int(round(radius * 2 * _cos(angle)))
        y = int(round(radius * _sin(angle)))
        coords.append((x, y))
        if i:
            edges.append((len(coords) - 2, len(coords) - 1))
    edges.append((1, len(coords) - 1))         # close the circuit
    edges.append((0, 1))                       # entrance joins the ring
    edges.append((0, len(coords) - 1))         # ...at both ends, so it converges
    # The core hangs off the far side of the ring.
    far = 1 + ring_len // 2
    prev = far
    for depth in range(core_len):
        coords.append((0, radius + 2 + depth))
        edges.append((prev, len(coords) - 1))
        prev = len(coords) - 1
    return coords, edges


def _cos(a: float) -> float:
    import math
    return math.cos(a)


def _sin(a: float) -> float:
    import math
    return math.sin(a)


def _layout_gauntlet(rng, size):
    """Segments in series, each with one or two lanes. There is always another
    lane, which is exactly the property requirement F needs."""
    coords, edges = [(0, 0)], []
    node = 0
    y = 0
    while len(coords) < size:
        y += 1
        lanes = 2 if rng.random() < 0.7 else 1
        lane_ids = []
        for lane in range(lanes):
            if len(coords) >= size:
                break
            coords.append((lane * 2 - (lanes - 1), y))
            edges.append((node, len(coords) - 1))
            lane_ids.append(len(coords) - 1)
        if not lane_ids:
            break
        if len(coords) >= size:
            break
        y += 1
        coords.append((0, y))                  # the lanes rejoin
        join = len(coords) - 1
        for lane_id in lane_ids:
            edges.append((lane_id, join))
        node = join
    return coords, edges


def _layout_vault(rng, size):
    """A free spine with sealed cells hanging off it."""
    spine_len = max(4, size // 2)
    coords, edges = [(0, 0)], []
    for i in range(1, spine_len):
        coords.append((0, i))
        edges.append((i - 1, i))
    spine = list(range(1, spine_len))
    while len(coords) < size and spine:
        parent = rng.choice(spine)
        px, py = coords[parent]
        side = 1 if rng.random() < 0.5 else -1
        spot = (px + side, py)
        if spot in set(coords):
            spot = (px + side * 2, py)
        if spot in set(coords):
            spine.remove(parent)
            continue
        coords.append(spot)
        edges.append((parent, len(coords) - 1))
    return coords, edges


def _layout_nest(rng, size):
    """Rings inside rings. Each ring has one gate into the next one in."""
    coords, edges = [(0, 0)], []
    remaining = size - 1
    level = 0
    outer_gate = 0
    while remaining > 0 and level < 10:
        ring_size = max(2, min(remaining, max(2, 6 - level)))
        first = len(coords)
        radius = max(2, 8 - level)
        for i in range(ring_size):
            angle = (i / ring_size) * 6.283185
            coords.append((int(round(radius * 2 * _cos(angle))),
                           int(round(radius * _sin(angle)))))
            if i:
                edges.append((len(coords) - 2, len(coords) - 1))
        if ring_size > 2:
            edges.append((first, len(coords) - 1))     # close the ring
        edges.append((outer_gate, first))              # the way in
        outer_gate = first + ring_size // 2            # the next gate, further round
        remaining -= ring_size
        level += 1
    return coords, edges


def _layout_branch(rng, size):
    """Forks that split twice and never rejoin. Each level doubles."""
    coords, edges = [(0, 0)], []
    frontier = [(0, 0, 0)]                             # id, x, depth
    while frontier and len(coords) < size:
        node, x, depth = frontier.pop(0)
        spread = max(1, 2 ** max(0, 4 - depth))
        for side in (-1, 1):
            if len(coords) >= size:
                break
            coords.append((x + side * spread, depth + 1))
            edges.append((node, len(coords) - 1))
            frontier.append((len(coords) - 1, x + side * spread, depth + 1))
    return coords, edges


def _layout_lattice(rng, size):
    """A grid with holes. Many routes, of many lengths, one of them shortest."""
    width = max(3, int(size ** 0.5))
    height = max(3, (size + width - 1) // width)
    coords = []
    index = {}
    for y in range(height):
        for x in range(width):
            if len(coords) >= size:
                break
            index[(x, y)] = len(coords)
            coords.append((x, y))
    edges = []
    for (x, y), rid in index.items():
        for dx, dy in ((1, 0), (0, 1)):
            other = index.get((x + dx, y + dy))
            if other is None:
                continue
            if rng.random() < 0.22:
                continue                                # a hole in the lattice
            edges.append((rid, other))
    return coords, edges


def _validate_plans() -> None:
    """Content drift is a bug, and this is the cheapest possible place to catch it.

    Every authored dungeon has to name a region that exists, a chapter the
    curriculum actually has, an archetype something can build, a rule something
    applies, and patterns the corpus can serve. Getting any of those wrong
    produces a dungeon that generates perfectly and then cannot find a single
    problem to put in it."""
    for plan in DUNGEONS:
        if plan.region not in world.REGION_BY_ID:
            raise ValueError(f"{plan.id}: no region {plan.region!r}")
        if plan.chapter not in curriculum.CHAPTER_BY_ID:
            raise ValueError(f"{plan.id}: no chapter {plan.chapter!r}")
        if plan.archetype not in LAYOUT_BUILDERS:
            raise ValueError(f"{plan.id}: no archetype {plan.archetype!r}")
        if plan.rule not in LAYOUT_RULES:
            raise ValueError(f"{plan.id}: no layout rule {plan.rule!r}")
        if plan.floor not in DIFFICULTY_LADDER:
            raise ValueError(f"{plan.id}: no difficulty {plan.floor!r}")
        if plan.floors < 1:
            raise ValueError(f"{plan.id}: floors must be at least 1")
        for pattern in plan.patterns:
            if pattern not in CORPUS_PATTERNS:
                raise ValueError(f"{plan.id}: {pattern!r} is not a corpus pattern")


LAYOUT_BUILDERS = {
    "warren": _layout_warren,
    "spiral": _layout_spiral,
    "cross": _layout_cross,
    "ring": _layout_ring,
    "gauntlet": _layout_gauntlet,
    "vault": _layout_vault,
    "nest": _layout_nest,
    "branch": _layout_branch,
    "lattice": _layout_lattice,
}

_validate_plans()


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def _adjacency(count: int, edges) -> list:
    adj = [[] for _ in range(count)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    return adj


def _bfs(adj: list, start: int) -> tuple:
    dist = {start: 0}
    parent = {start: -1}
    queue = [start]
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        for other in adj[node]:
            if other in dist:
                continue
            dist[other] = dist[node] + 1
            parent[other] = node
            queue.append(other)
    return dist, parent


def _path_from(parent: dict, target: int) -> list:
    if target not in parent:
        return []
    path = [target]
    while parent[path[-1]] != -1:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def _normalise(count: int, edges) -> list:
    """Drop self-loops and duplicates, keep insertion order stable."""
    seen = set()
    clean = []
    for a, b in edges:
        if a == b or not (0 <= a < count and 0 <= b < count):
            continue
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        clean.append(key)
    return clean


def _repair(coords: list, edges: list) -> list:
    """Join any stray component to the nearest room in the main one. A generator
    that boxes itself in must not be able to strand a wing of the dungeon."""
    count = len(coords)
    while True:
        adj = _adjacency(count, edges)
        dist, _ = _bfs(adj, 0)
        stranded = [i for i in range(count) if i not in dist]
        if not stranded:
            return edges
        orphan = stranded[0]
        ox, oy = coords[orphan]
        nearest = min(dist, key=lambda r: abs(coords[r][0] - ox) + abs(coords[r][1] - oy))
        edges.append((min(orphan, nearest), max(orphan, nearest)))


# ---------------------------------------------------------------------------
# Room contents
# ---------------------------------------------------------------------------

_FILLER_WEIGHTS = (
    ("ENCOUNTER", 38), ("PUZZLE", 24), ("TREASURE", 10),
    ("STORY", 12), ("SHRINE", 8), ("JUNCTION", 8),
)

_ROOM_PREFIX = ("Lower", "Upper", "Far", "Near", "Old", "Sunk", "Quiet", "Long",
                "Narrow", "Broken", "Cold", "First", "Second", "Hollow", "Outer")


def _weighted(rng, pairs):
    total = sum(w for _, w in pairs)
    pick = rng.random() * total
    for name, weight in pairs:
        pick -= weight
        if pick <= 0:
            return name
    return pairs[-1][0]


def _difficulty_for(plan: DungeonPlan, depth: int, max_depth: int, rng) -> str:
    """Deeper is harder, and the tier decides how much harder it is allowed to get.
    This is the only place room difficulty is decided, so E holds by construction."""
    floor_i = DIFFICULTY_LADDER.index(plan.floor)
    ceiling = min(len(DIFFICULTY_LADDER) - 1, floor_i + 1 + plan.tier)
    frac = depth / max(1, max_depth)
    index = floor_i + int(round(frac * (ceiling - floor_i)))
    index += rng.choice((0, 0, 0, 1, -1))
    return DIFFICULTY_LADDER[max(floor_i, min(ceiling, index))]


def _relent_chain(plan: DungeonPlan, difficulty: str) -> list:
    """The ladder down. A room the player cannot clear offers the same idea one
    rung easier, and keeps offering until it reaches the dungeon's floor. This is
    requirement F expressed per room rather than per map."""
    floor_i = DIFFICULTY_LADDER.index(plan.floor)
    index = DIFFICULTY_LADDER.index(difficulty)
    chain = [DIFFICULTY_LADDER[i] for i in range(index, floor_i - 1, -1)]
    if len(chain) > 4:
        chain = chain[:3] + [plan.floor]
    if chain[-1] != plan.floor:
        chain.append(plan.floor)
    return chain


# What a shrine may ask. All three are answer-one-question kinds: a shrine hands
# back stamina for recall, and asking for written code there would make it a
# second encounter with a nicer name.
_SHRINE_KINDS = ("STATE_PREDICT", "TRACE", "COMPLEXITY_MATCH")


def _encounter_request(plan: DungeonPlan, rng, depth: int, max_depth: int,
                       *, puzzle_kind: str = "") -> dict:
    """What the engine should look for in the corpus when this room is entered.

    Deliberately a *request* and not a problem id: the corpus is built and
    validated elsewhere, the curriculum gate lives in curriculum.is_permitted,
    and a dungeon that hard-coded problem ids would drift out of date the first
    time a family was re-authored."""
    difficulty = _difficulty_for(plan, depth, max_depth, rng)
    patterns = list(plan.patterns)
    if patterns:
        rng.shuffle(patterns)
        patterns = patterns[:3]
    request = {
        "realm": plan.region,
        "patterns": patterns,               # empty: whatever the chapter permits
        "difficulty": difficulty,
        "relent": _relent_chain(plan, difficulty),
        "chapter": plan.chapter,
        "kind": "PUZZLE" if puzzle_kind else "CODE_BATTLE",
    }
    if puzzle_kind:
        request["puzzle_kind"] = puzzle_kind
        request["skill"] = puzzles.PUZZLE_SKILL[puzzle_kind]
        request["blurb"] = puzzles.PUZZLE_BLURB[puzzle_kind]
    return request


def _name_room(rng, plan: DungeonPlan, kind: str, used: set) -> str:
    base = {
        "ENTRANCE": "The Threshold",
        "BOSS": f"The {rng.choice(('Deep', 'Last', 'Sealed', 'Far'))} Chamber",
        "SHRINE": f"{rng.choice(('Still', 'Quiet', 'Lamplit'))} Shrine",
        "VAULT": f"Sealed {rng.choice(plan.motif)}",
    }.get(kind)
    if base is None:
        base = f"{rng.choice(_ROOM_PREFIX)} {rng.choice(plan.motif)}"
    name, n = base, 2
    while name in used:
        name = f"{base} {n}"
        n += 1
    used.add(name)
    return name


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def dungeon_seed(dungeon_id: str, salt: int = 0) -> int:
    """Stable across processes — hash() is salted per interpreter and would give
    a player a different building every time they relaunched the game."""
    value = 2166136261
    for ch in f"{dungeon_id}:{salt}":
        value = ((value ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return value


# How many layouts to try before accepting one shallower than `plan.floors`.
# A quest is allowed to say "reach the fifth floor", so `floors` has to be a
# promise rather than a tendency — and the layouts are random, so the only way
# to keep the promise is to reroll the ones that come up short.
FLOOR_ATTEMPTS = 24


def floors_for(dungeon_id: str) -> int:
    """Deepest floor anything outside this module may demand of a dungeon."""
    plan = DUNGEON_BY_ID.get(dungeon_id)
    if plan is None:
        raise KeyError(f"no dungeon {dungeon_id!r}")
    return plan.floors


def generate(dungeon_id: str, *, seed: int | None = None, size_bonus: int = 0) -> Dungeon:
    """Build a dungeon. Same id and seed, same place, every time.

    `seed` is left alone by normal play: the default is derived from the id so a
    dungeon is a fixed location in the world. Deeper expeditions pass a salt to
    get a genuinely new floor plan under the same name.

    A layout shallower than `plan.floors` is rerolled from a derived seed, and
    the returned dungeon keeps the seed it was ASKED for rather than the one that
    happened to work — otherwise a saved run could not be rebuilt from its own
    state."""
    plan = DUNGEON_BY_ID.get(dungeon_id)
    if plan is None:
        raise KeyError(f"no dungeon {dungeon_id!r}")
    asked = dungeon_seed(dungeon_id) if seed is None else seed
    best = None
    for attempt in range(FLOOR_ATTEMPTS):
        built = _generate_once(plan, asked, attempt, size_bonus)
        if built.max_depth >= plan.floors:
            return built
        if best is None or built.max_depth > best.max_depth:
            best = built
    return best


def _generate_once(plan: DungeonPlan, asked: int, attempt: int,
                   size_bonus: int) -> Dungeon:
    dungeon_id = plan.id
    seed = asked
    rng = random.Random((asked * 1000003 + attempt * 2654435761) & 0xFFFFFFFF
                        if attempt else asked)

    size = max(8, plan.size + size_bonus)
    coords, edges = LAYOUT_BUILDERS[plan.archetype](rng, size)
    edges = _repair(coords, _normalise(len(coords), edges))
    count = len(coords)

    adj = _adjacency(count, edges)
    dist, parent = _bfs(adj, 0)
    max_depth = max(dist.values())
    deepest = [r for r, d in dist.items() if d == max_depth]
    boss_room = rng.choice(sorted(deepest))
    critical = _path_from(parent, boss_room)

    # -- locks. Only on edges whose far side holds neither the entrance nor the
    # boss, so a locked door can never stand between the player and the fight.
    lock_quota = max(1, count // 8)
    locks: list = []
    locked_edges: set = set()
    claimed: set = set()                 # rooms already sealed behind some door
    on_critical = set(zip(critical, critical[1:]))
    on_critical |= {(b, a) for a, b in on_critical}
    candidates = [e for e in edges if e not in on_critical]
    rng.shuffle(candidates)
    for edge in candidates:
        if len(locks) >= lock_quota:
            break
        # Each candidate is judged against the FULL map with only its own edge
        # removed. Judging it against the already-locked map lets locks nest,
        # and a nested lock can name the wrong side of itself as the guarded one.
        trial = [e for e in edges if e != edge]
        near = _bfs(_adjacency(count, trial), 0)[0]
        if boss_room not in near:
            continue                                    # would seal the boss away
        beyond = [r for r in range(count) if r not in near]
        if not beyond or len(beyond) > count // 3:
            continue                                    # nothing behind it, or too much
        if any(r in claimed for r in beyond):
            continue                                    # keep sealed branches disjoint
        locked_edges.add(edge)
        claimed.update(beyond)
        deep_side = edge[0] if edge[0] in beyond else edge[1]
        locks.append({"edge": edge, "side": deep_side, "beyond": beyond})

    if not locks:
        # Loopy archetypes often have no bridge worth locking: every edge has a
        # way round it, which is a good map and a dungeon with no sealed branch
        # in it. So dig one. A cell hung off a shallow room can never stand
        # between the player and anything they need.
        shallow = [r for r in range(count)
                   if r not in (0, boss_room) and dist.get(r, 0) <= max(1, max_depth - 2)]
        anchor = rng.choice(shallow or [r for r in range(count) if r != boss_room])
        ax, ay = coords[anchor]
        taken = set(coords)
        spot = next(((ax + dx, ay + dy) for dx, dy in _DIRS
                     if (ax + dx, ay + dy) not in taken), (ax + 7, ay + 7))
        new_id = count
        coords.append(spot)
        count += 1
        edge = (min(anchor, new_id), max(anchor, new_id))
        edges.append(edge)
        locked_edges.add(edge)
        locks.append({"edge": edge, "side": new_id, "beyond": [new_id]})
        claimed.add(new_id)
        dist, parent = _bfs(_adjacency(count, edges), 0)
        max_depth = max(dist.values())
        critical = _path_from(parent, boss_room)

    # Keys live in rooms the player can reach without holding any key at all.
    free_edges = [e for e in edges if e not in locked_edges]
    free_set = set(_bfs(_adjacency(count, free_edges), 0)[0])
    key_rooms: dict = {}
    pool = sorted(free_set - {0, boss_room} - claimed)
    rng.shuffle(pool)
    kept_locks = []
    for i, lock in enumerate(locks):
        available = [r for r in pool if r not in key_rooms]
        if not available:
            break                                       # no key room, no lock
        key_room = available[0]
        key_id = f"{plan.id}_key_{i + 1}"
        key_rooms[key_room] = key_id
        lock["key_id"] = key_id
        kept_locks.append(lock)
    locks = kept_locks
    locked_edges = {lock["edge"] for lock in locks}

    # -- rooms
    used_names: set = set()
    rooms: list = []
    behind_lock = {r for lock in locks for r in lock["beyond"]}
    vault_rooms = set()
    for lock in locks:
        deepest_beyond = max(lock["beyond"], key=lambda r: (dist.get(r, 0), r))
        vault_rooms.add(deepest_beyond)

    puzzle_kinds = list(puzzles.PUZZLE_KINDS)
    rng.shuffle(puzzle_kinds)
    puzzle_cursor = 0
    lore = list(plan.lore)
    codex = list(plan.codex)
    lore_cursor = 0

    for rid in range(count):
        depth = dist.get(rid, 0)
        if rid == 0:
            kind = "ENTRANCE"
        elif rid == boss_room:
            kind = "BOSS"
        elif rid in vault_rooms:
            kind = "VAULT"
        elif rid in key_rooms:
            kind = "ENCOUNTER"
        else:
            kind = _weighted(rng, _FILLER_WEIGHTS)

        room = Room(id=rid, kind=kind, name=_name_room(rng, plan, kind, used_names),
                    depth=depth, x=coords[rid][0], y=coords[rid][1])

        if kind == "ENTRANCE":
            room.blurb = ("The way in, and — this matters — the way out. "
                          "Nothing fights you on the threshold.")
            room.tags.append("exit")
        elif kind == "BOSS":
            room.blurb = "Something in here has been waiting the whole descent."
        elif kind == "ENCOUNTER":
            room.encounter = _encounter_request(plan, rng, depth, max_depth)
        elif kind == "PUZZLE":
            puzzle_kind = puzzle_kinds[puzzle_cursor % len(puzzle_kinds)]
            puzzle_cursor += 1
            room.encounter = _encounter_request(plan, rng, depth, max_depth,
                                                puzzle_kind=puzzle_kind)
            room.blurb = puzzles.PUZZLE_BLURB[puzzle_kind]
        elif kind == "SHRINE":
            room.shrine_skill = skillmod.PATTERN_TO_SKILL.get(
                plan.patterns[0] if plan.patterns else "PYTHON", "RECALL")
            # A shrine asks something, so it needs something to ask. Without a
            # request `populate` skips it and `options` still offers "engage",
            # which is a room the caller cannot serve.
            room.encounter = _encounter_request(
                plan, rng, depth, max_depth,
                puzzle_kind=rng.choice(_SHRINE_KINDS))
            room.encounter["shrine"] = room.shrine_skill
            room.blurb = ("A shrine that asks one question and gives back stamina "
                          "and focus for a true answer.")
        elif kind == "STORY":
            if lore_cursor < len(lore):
                room.story = lore[lore_cursor]
            else:
                room.story = rng.choice(lore)
            if codex and lore_cursor < len(codex):
                room.codex = codex[lore_cursor]
            lore_cursor += 1
            room.blurb = "Empty of anything that fights. Not empty."
        elif kind == "JUNCTION":
            room.blurb = "A place where corridors meet and nothing else happens."

        if kind in ("TREASURE", "VAULT"):
            room.treasure = {"tier": plan.tier, "depth": depth,
                             "sealed": kind == "VAULT"}
            if kind == "VAULT":
                # The key gets you through the door; the hoard still argues. A
                # vault is not in _FREE_KINDS, so it has to carry a request like
                # any other room that demands solving.
                room.encounter = _encounter_request(plan, rng, depth, max_depth)
                room.encounter["vault"] = True
            room.blurb = ("A hoard behind a door that answers to exactly one key."
                          if kind == "VAULT" else "Something was left here.")
        if rid in key_rooms:
            room.key_id = key_rooms[rid]
            room.tags.append("key")
            room.blurb = (room.blurb + " Whatever is in here is holding a key.").strip()
        if rid in behind_lock:
            room.tags.append("sealed_branch")
        rooms.append(room)

    # Quotas. A dungeon that rolled no shrine, no lore and one puzzle kind is
    # technically a dungeon and is, in practice, a corridor.
    _enforce_quotas(plan, rng, rooms, max_depth, boss_room, puzzle_kinds)

    passages = []
    for a, b in edges:
        lock = None
        for entry in locks:
            if entry["edge"] == (a, b):
                lock = Lock(key_id=entry["key_id"],
                            name=f"The {plan.motif[0]} Door",
                            side=entry["side"],
                            tell="One key. This door. No others.")
                break
        passages.append(Passage(a=a, b=b, lock=lock))

    # -- the shortcut home, found from the deep end and opening both ways after.
    # Prefer a room deep on the critical path that the player genuinely engages
    # with; a lever nobody has a reason to touch is a shortcut nobody finds.
    reveal = boss_room
    for candidate in reversed(critical[1:-1] or critical[:1]):
        if rooms[candidate].demands_solving:
            reveal = candidate
            break
    else:
        reveal = critical[max(1, len(critical) - 2)] if len(critical) > 1 else boss_room
    passages.append(Passage(a=0, b=boss_room, kind="SHORTCUT", revealed_by=reveal))
    rooms[reveal].tags.append("shortcut")

    dungeon = Dungeon(
        id=plan.id, name=plan.name, region=plan.region, chapter=plan.chapter,
        tier=plan.tier, archetype=plan.archetype, rule=plan.rule, seed=seed,
        blurb=plan.blurb, lesson=plan.lesson, floor=plan.floor,
        patterns=list(plan.patterns), rooms=rooms, passages=passages,
        entrance=0, boss_room=boss_room, max_depth=max_depth,
        shortest_path=critical, rule_note=LAYOUT_RULES[plan.rule],
    )
    _apply_rule(dungeon, plan, rng)

    # -- the boss seal, set from what is actually reachable without it.
    reachable = _reachable(dungeon)
    clearable = [r for r in reachable
                 if r != dungeon.boss_room and dungeon.rooms[r].demands_solving]
    required = max(2, min(len(clearable), int(len(clearable) * 0.45)))
    rooms[boss_room].seal = {
        "clears_required": required,
        "of_available": len(clearable),
        "tell": "The chamber opens to anyone who has cleared enough of this place "
                "to have earned the conversation.",
    }
    return dungeon


def _enforce_quotas(plan, rng, rooms, max_depth, boss_room, puzzle_kinds):
    """Guarantee the mix. Exploration that is one thing repeated is a chore."""
    spare = [r for r in rooms
             if r.id not in (0, boss_room)
             and r.kind in ("JUNCTION", "ENCOUNTER", "TREASURE")
             and not r.key_id]

    def take():
        return spare.pop() if spare else None

    def convert(room, kind):
        room.kind = kind
        room.encounter = {}
        room.treasure = {}
        return room

    if not any(r.kind == "SHRINE" for r in rooms):
        room = take()
        if room:
            convert(room, "SHRINE")
            room.shrine_skill = "RECALL"
            room.encounter = _encounter_request(
                plan, rng, room.depth, max_depth,
                puzzle_kind=rng.choice(_SHRINE_KINDS))
            room.encounter["shrine"] = room.shrine_skill
    if not any(r.kind == "STORY" for r in rooms):
        room = take()
        if room:
            convert(room, "STORY")
            room.story = plan.lore[0]
            room.codex = plan.codex[0] if plan.codex else ""
    if not any(r.kind in ("TREASURE", "VAULT") for r in rooms):
        room = take()
        if room:
            convert(room, "TREASURE")
            room.treasure = {"tier": plan.tier, "depth": room.depth, "sealed": False}

    present = {r.encounter.get("puzzle_kind") for r in rooms if r.kind == "PUZZLE"}
    present.discard(None)
    wanted = 3
    for puzzle_kind in puzzle_kinds:
        if len(present) >= wanted:
            break
        if puzzle_kind in present:
            continue
        room = take()
        if room is None:
            break
        convert(room, "PUZZLE")
        room.encounter = _encounter_request(plan, rng, room.depth, max_depth,
                                            puzzle_kind=puzzle_kind)
        room.blurb = puzzles.PUZZLE_BLURB[puzzle_kind]
        present.add(puzzle_kind)

    # Anything still a bare junction near the deep end is wasted floor space.
    for room in rooms:
        if room.kind == "JUNCTION" and room.depth >= max_depth - 1 and room.id != 0:
            convert(room, "ENCOUNTER")
            room.encounter = _encounter_request(plan, rng, room.depth, max_depth)


# ---------------------------------------------------------------------------
# The layout rules — where the building becomes the lesson
# ---------------------------------------------------------------------------

def _apply_rule(dungeon: Dungeon, plan: DungeonPlan, rng) -> None:
    rule = plan.rule
    rooms = dungeon.rooms

    if rule == "indent_depth":
        for room in rooms:
            room.rule_data["indent"] = room.depth
            room.tags.append(f"indent:{room.depth}")

    elif rule == "keyed_vaults":
        for passage in dungeon.passages:
            if passage.lock:
                passage.lock.tell = (
                    f"{passage.lock.key_id.rsplit('_', 1)[-1]} fits this door and "
                    "nothing else in the hollow. Trying the others is the slow way.")

    elif rule == "anagram_ring":
        by_depth: dict = {}
        for room in rooms:
            if room.demands_solving and room.kind != "BOSS":
                by_depth.setdefault(room.depth, []).append(room)
        groups = 0
        for depth in sorted(by_depth):
            cohort = by_depth[depth]
            if len(cohort) < 2 or groups >= 2:
                continue
            groups += 1
            group = f"anagram_{groups}"
            for room in cohort[:3]:
                room.group = group
                room.tags.append("anagram")
                room.blurb = (room.blurb or "") + (
                    " The letters over this door are the letters over another. "
                    "Clear either and both are cleared.")

    elif rule == "zero_indexed":
        for room in rooms:
            room.rule_data["index"] = room.id
            room.name = f"{room.name} [{room.id}]"
        last = rooms[dungeon.boss_room]
        last.rule_data["is_last"] = True
        last.blurb += (f" The door is numbered {len(rooms) - 1}, and there are "
                       f"{len(rooms)} alcoves. That is not a mistake.")

    elif rule == "sliding_frame":
        for room in rooms:
            room.rule_data["frame"] = True
        dungeon.rule_note += " The frame is three rooms wide."

    elif rule == "converging_ends":
        heads = [p.other(0) for p in dungeon.passages_at(0) if p.kind == "PASSAGE"]
        for i, head in enumerate(heads[:2]):
            rooms[head].tags.append(f"lantern:{i + 1}")
            rooms[head].rule_data["lantern"] = i + 1

    elif rule == "lifo_exit":
        for room in rooms:
            room.rule_data["lifo"] = True
        dungeon.rule_note += (" Leaving happens in reverse order of entry, and the "
                              "way back is therefore always exactly one room.")

    elif rule == "rotating_grid":
        for room in rooms:
            room.rule_data["row"] = room.y
            room.rule_data["col"] = room.x
        dungeon.rule_note += " Four clears turn the keep a quarter."

    elif rule == "recursive_nest":
        for room in rooms:
            room.rule_data["ring"] = room.depth
        deepest = max(rooms, key=lambda r: (r.depth, r.id))
        deepest.rule_data["base_case"] = True
        deepest.tags.append("base_case")
        deepest.blurb += (" Nothing smaller is inside this one. That is what makes "
                          "it the place the unwinding starts.")

    elif rule == "binary_branch":
        for room in rooms:
            if room.id == 0:
                continue
            room.rule_data["limb"] = "left" if room.x < 0 else "right"
            room.tags.append(room.rule_data["limb"])
        for room in rooms:
            if len(dungeon.neighbours(room.id)) == 1 and room.id != 0:
                room.tags.append("leaf")
                room.rule_data["leaf"] = True

    elif rule == "shortest_path":
        on_path = set(zip(dungeon.shortest_path, dungeon.shortest_path[1:]))
        for passage in dungeon.passages:
            if (passage.a, passage.b) in on_path or (passage.b, passage.a) in on_path:
                passage.kind = "PASSAGE"
                for room in (rooms[passage.a], rooms[passage.b]):
                    if "shortest" not in room.tags:
                        room.tags.append("shortest")
        dungeon.rule_note += (f" The shortest road from the threshold to the chamber "
                              f"is {len(dungeon.shortest_path) - 1} roads long. "
                              "Rings of light find it; a committed path does not.")

    elif rule == "memo_tiles":
        for room in rooms:
            room.rule_data["memo"] = True
        dungeon.rule_note += " A cleared tile stays lit and costs nothing to recross."

    elif rule == "defect_hunt":
        by_depth: dict = {}
        for room in rooms:
            if room.demands_solving and room.kind != "BOSS":
                by_depth.setdefault(room.depth, []).append(room)
        for depth in sorted(by_depth):
            room = rng.choice(by_depth[depth])
            room.rule_data["defect"] = True
            room.tags.append("defect")
            room.blurb = ((room.blurb or "") +
                          " Something in this room is subtly wrong. Reading it is "
                          "the only way that has ever worked.").strip()

    elif rule == "doubling_floors":
        for room in rooms:
            room.rule_data["floor"] = room.depth
            room.rule_data["floor_width"] = sum(1 for r in rooms
                                                if r.depth == room.depth)
        # The way down halves what is left at every step; that is the only
        # stair in the tower that reaches the top, and it is the shortcut.
        rooms[dungeon.boss_room].rule_data["halving_stair"] = True

    elif rule == "timed_heats":
        for room in rooms:
            room.rule_data["heat"] = room.depth
            if room.encounter:
                # The Coliseum advertises no help and pets already honour that
                # (pets.SILENCED_REGIONS). The pens carry the same flag so a
                # caller reading a room does not have to know the region rule.
                room.encounter["silenced"] = True
        dungeon.rule_note += (" The clock above is audible in every pen, and "
                              "nothing down here explains itself.")

    elif rule == "unlabelled":
        for room in rooms:
            if room.encounter:
                # The pattern still steers which problem is served. It simply is
                # not shown, which is the entire exercise of the castle.
                room.encounter["label_hidden"] = True
            room.blurb = "" if room.kind not in ("ENTRANCE", "BOSS") else room.blurb
            room.name = room.name.split("[")[0].strip()


def rotate_view(dungeon: Dungeon, turns: int) -> dict:
    """The Turning Keep's quarter turn. Room ids and passages are untouched — only
    the coordinates move, so a rotation can never strand anyone."""
    turns %= 4
    out = {}
    for room in dungeon.rooms:
        x, y = room.x, room.y
        for _ in range(turns):
            x, y = -y, x
        out[room.id] = (x, y)
    return out


# ---------------------------------------------------------------------------
# Reachability. Locks are entry-only, so "can I get out" and "can I get in" are
# two different questions and only one of them has a key in it.
# ---------------------------------------------------------------------------

def _reachable(dungeon: Dungeon, *, start: int | None = None,
               keys: set | None = None, assume_clears: bool = True) -> set:
    """Rooms the player can reach, taking keys from rooms they pass through.

    `assume_clears` models the honest case: every room in this file is clearable
    because every encounter relents to the dungeon floor, so a player who can
    stand in a key room can take its key."""
    start = dungeon.entrance if start is None else start
    held = set(keys or ())
    seen = {start}
    changed = True
    while changed:
        changed = False
        frontier = list(seen)
        for room_id in frontier:
            if assume_clears and dungeon.rooms[room_id].key_id:
                if dungeon.rooms[room_id].key_id not in held:
                    held.add(dungeon.rooms[room_id].key_id)
                    changed = True
            for passage in dungeon.passages_at(room_id):
                other = passage.other(room_id)
                if other in seen:
                    continue
                if passage.revealed_by != -1 and passage.revealed_by not in seen:
                    continue
                if passage.lock and passage.lock.side == other \
                        and passage.lock.key_id not in held:
                    continue
                seen.add(other)
                changed = True
    return seen


def exit_path(dungeon: Dungeon, room_id: int) -> list:
    """The walk back to the threshold. Locks never obstruct it: a door that
    checked its key on the way out would be a dead end with extra steps."""
    adj = [[] for _ in dungeon.rooms]
    for passage in dungeon.passages:
        if passage.kind == "SHORTCUT":
            continue                       # not assumed open; this is the honest walk
        adj[passage.a].append(passage.b)
        adj[passage.b].append(passage.a)
    _, parent = _bfs(adj, room_id)
    return _path_from(parent, dungeon.entrance)


# ---------------------------------------------------------------------------
# Depth and reward, which scale together
# ---------------------------------------------------------------------------

_KIND_REWARD_MULT = {
    "ENTRANCE": 0.0, "JUNCTION": 0.1, "STORY": 0.3, "SHRINE": 0.3,
    "TREASURE": 0.45, "VAULT": 0.7, "PUZZLE": 0.9, "ENCOUNTER": 1.0, "BOSS": 3.0,
}


def room_reward(dungeon: Dungeon, room: Room) -> dict:
    """The dungeon's own bonus, on top of whatever the encounter itself pays.

    A pure function of tier, depth and kind, which is what makes "deeper pays
    better" a property of the code rather than a hope about the tables."""
    base = 16 + 13 * dungeon.tier
    depth_mult = 1.0 + 0.18 * room.depth
    xp = int(round(base * depth_mult * _KIND_REWARD_MULT.get(room.kind, 0.5)))
    return {
        "xp": xp,
        "gold": xp // 3,
        "depth": room.depth,
        "tier": dungeon.tier,
        "drop_luck": round(0.02 * dungeon.tier + 0.015 * room.depth, 3),
    }


def _drop_difficulty(dungeon: Dungeon, room: Room) -> str:
    """Which rung of items.DIFFICULTY_DROP_CHANCE this room's hoard rolls on."""
    if room.kind == "BOSS":
        return "BOSS"
    floor_i = DIFFICULTY_LADDER.index(dungeon.floor)
    ceiling = min(len(DIFFICULTY_LADDER) - 1, floor_i + 1 + dungeon.tier)
    frac = room.depth / max(1, dungeon.max_depth)
    index = floor_i + int(round(frac * (ceiling - floor_i)))
    if room.kind == "VAULT":
        index = min(ceiling, index + 1)
    return DIFFICULTY_LADDER[max(floor_i, min(ceiling, index))]


def roll_room_treasure(dungeon: Dungeon, room: Room, *, luck: float = 0.0,
                       owned: set | None = None, rank: str = "B",
                       rng: random.Random | None = None) -> dict | None:
    """One economy, not two: this is items.roll_drop with the depth and the tier
    folded into its existing knobs."""
    reward = room_reward(dungeon, room)
    skill = ""
    if dungeon.patterns:
        skill = skillmod.PATTERN_TO_SKILL.get(dungeon.patterns[0], "")
    upgrade = 0
    if room.kind == "VAULT":
        upgrade += 1                       # sealed cells are worth the key
    if room.depth >= dungeon.max_depth - 1 and dungeon.tier >= 4:
        upgrade += 1
    drop = items.roll_drop(
        difficulty=_drop_difficulty(dungeon, room), rank=rank,
        luck=luck + reward["drop_luck"], is_boss=room.kind == "BOSS",
        skill=skill, owned=owned, rng=rng, upgrade=upgrade)
    if drop is None and room.kind in ("TREASURE", "VAULT"):
        # A room the map calls treasure has to contain something. This is not a
        # rarity trick — it is the ordinary consumable table, so a chest is worth
        # opening without ever being worth farming.
        drop = items.consumable_drop(rng, luck)
    return drop


# ---------------------------------------------------------------------------
# Randomised bosses
# ---------------------------------------------------------------------------
#
# A dungeon boss is assembled, not authored: archetype, phases, demanded
# patterns and modifiers are all drawn per run. `bestiary_id` names a body in
# gauntlet/bestiary.py, which this module deliberately does not import — that
# file belongs to another team and is resolved by string at the point of use.

BOSS_ARCHETYPES = (
    {"id": "warden", "title": "The Warden", "sprite": "titan",
     "bestiary_id": "dungeon_warden", "hp": 120, "colour": "#8a8f9c",
     "stance": "Stands in the doorway and waits for you to explain yourself.",
     "bias": ("recognise", "explain", "implement", "edges")},
    {"id": "hydra", "title": "The Hydra", "sprite": "hydra",
     "bestiary_id": "dungeon_hydra", "hp": 150, "colour": "#4fb783",
     "stance": "Every case you forget grows back as another head.",
     "bias": ("implement", "edges", "edges", "variant")},
    {"id": "automaton", "title": "The Automaton", "sprite": "automaton",
     "bestiary_id": "dungeon_automaton", "hp": 130, "colour": "#b0763f",
     "stance": "Replays your operations in order and asks what state remains.",
     "bias": ("state", "trace", "implement", "complexity")},
    {"id": "lich", "title": "The Lich", "sprite": "lich",
     "bestiary_id": "dungeon_lich", "hp": 140, "colour": "#8f3f6f",
     "stance": "Writes the structure down, then demands you read it back exactly.",
     "bias": ("assemble", "implement", "variant", "explain")},
    {"id": "wyrm", "title": "The Wyrm", "sprite": "wyrm",
     "bestiary_id": "dungeon_wyrm", "hp": 160, "colour": "#3f6f9c",
     "stance": "Correct is not the same as fast, and it is the difference.",
     "bias": ("complexity", "implement", "scale", "explain")},
    {"id": "golem", "title": "The Golem", "sprite": "golem",
     "bestiary_id": "dungeon_golem", "hp": 175, "colour": "#6b6f7c",
     "stance": "Slow, enormous, and entirely unbothered by a clever opening.",
     "bias": ("implement", "edges", "complexity", "variant")},
    {"id": "swarm", "title": "The Swarm", "sprite": "spirit",
     "bestiary_id": "dungeon_swarm", "hp": 105, "colour": "#e8c37d",
     "stance": "Many small demands at once. None of them individually hard.",
     "bias": ("trace", "recognise", "break", "assemble")},
    {"id": "mirror", "title": "The Mirror", "sprite": "wraith",
     "bestiary_id": "dungeon_mirror", "hp": 125, "colour": "#7f6ad6",
     "stance": "Answers you with your own last wrong answer, politely.",
     "bias": ("flaw", "break", "implement", "variant")},
    {"id": "herald", "title": "The Herald", "sprite": "messenger",
     "bestiary_id": "dungeon_herald", "hp": 115, "colour": "#7ec8ff",
     "stance": "Asks for the approach before it will allow a keystroke.",
     "bias": ("explain", "recognise", "implement", "complexity")},
    {"id": "colossus", "title": "The Colossus", "sprite": "behemoth",
     "bestiary_id": "dungeon_colossus", "hp": 190, "colour": "#c4553f",
     "stance": "Takes the whole fight to move and hits like the whole fight.",
     "bias": ("implement", "scale", "edges", "complexity")},
)

# Phase kinds match the engine's existing encounter vocabulary, plus the six
# graded puzzle kinds, so a phase is always something the game can already run.
BOSS_PHASE_POOL = (
    {"key": "recognise", "label": "Name the family", "kind": "PATTERN_ENCOUNTER",
     "share": 0.12, "demand": "Say what this is before you touch it."},
    {"key": "explain", "label": "State the approach", "kind": "COMMUNICATION",
     "share": 0.14, "demand": "Out loud, in order, before the first keystroke."},
    {"key": "implement", "label": "Cast the spell", "kind": "CODE_BATTLE",
     "share": 0.30, "demand": "Write it. All of it."},
    {"key": "edges", "label": "The hidden trials", "kind": "EDGE_CASE_TRAP",
     "share": 0.16, "demand": "Empty, single, duplicate, boundary. In that order."},
    {"key": "complexity", "label": "Name its cost", "kind": "COMPLEXITY_DUEL",
     "share": 0.12, "demand": "Time and space, and why."},
    {"key": "variant", "label": "The disguised rematch", "kind": "MEMORY_AMBUSH",
     "share": 0.20, "demand": "Same bones, different skin, no label."},
    {"key": "trace", "label": "Follow the cast", "kind": "TRACE",
     "share": 0.12, "demand": "What does the variable hold at each mark?"},
    {"key": "assemble", "label": "Set the runes in order", "kind": "RUNE_ASSEMBLY",
     "share": 0.16, "demand": "No typing. Only structure, and depth."},
    {"key": "flaw", "label": "Find the cursed line", "kind": "SPOT_THE_FLAW",
     "share": 0.10, "demand": "Two spells, one line apart."},
    {"key": "break", "label": "Break it", "kind": "BREAK_IT",
     "share": 0.12, "demand": "One input that proves it wrong."},
    {"key": "state", "label": "Say what remains", "kind": "STATE_PREDICT",
     "share": 0.10, "demand": "Replay the operations. Report the exact state."},
    {"key": "scale", "label": "Survive the scale trial", "kind": "SPEED_DUEL",
     "share": 0.18, "demand": "It has to finish, not merely be right."},
)

_PHASE_BY_KEY = {p["key"]: p for p in BOSS_PHASE_POOL}

# Modifiers change what you DO, not how big the numbers are. Every one of these
# has a tactic attached, and the tactic is the point of it.
BOSS_MODIFIERS = (
    {"id": "brute_resistant", "name": "Resists Brute Force", "group": "performance",
     "resistance": "BRUTE_FORCE",
     "tell": "Nested loops slide off its hide.",
     "tactic": "A correct quadratic answer does not finish this phase. Find the "
               "structure that removes the inner loop before you write anything."},
    {"id": "veiled", "name": "Veiled", "group": "probe",
     "tell": "It cannot be touched, and it knows it.",
     "tactic": "Immune until you probe it correctly once. Assert what the right "
               "answer is on one input; a correct probe lifts the veil."},
    {"id": "sealed_weakness", "name": "Sealed Weakness", "group": "probe",
     "tell": "One part of it is darker than the rest.",
     "tactic": "Critical strikes do nothing until its hidden trial has been named. "
               "Probe for the edge case, then aim at it."},
    {"id": "splits", "name": "Splits At Half", "group": "structure",
     "tell": "There is a seam down the middle of it.",
     "tactic": "At half health it becomes two halves demanding two different "
               "patterns. Clear both; neither one alone ends the fight."},
    {"id": "regenerating", "name": "Regenerating", "group": "structure",
     "tell": "The damage closes while you think.",
     "tactic": "A phase you leave unfinished heals. Finish what you open, in one "
               "go, even if you open it later than you would like."},
    {"id": "reversed", "name": "Reversed Order", "group": "order",
     "tell": "It presents its demands back to front.",
     "tactic": "Phases must be answered in the reverse of the order it shows "
               "them. Last shown, first answered."},
    {"id": "ordered", "name": "Strict Order", "group": "order",
     "tell": "It will not be hurried.",
     "tactic": "Phases only count in the order given. Skipping ahead is simply "
               "not accepted, however right the answer is."},
    {"id": "silent", "name": "Silent", "group": "information",
     "tell": "It says nothing at all, which is worse.",
     "tactic": "No pattern name, no family, no region colour. Recognition is "
               "yours to do. Hints still work; the label does not exist."},
    {"id": "cold_open", "name": "Cold Open", "group": "information",
     "tell": "It begins before it has explained anything.",
     "tactic": "The first phase arrives underspecified. Probe for the contract "
               "before you commit to an approach — that is the phase."},
    {"id": "hint_fed", "name": "Feeds On Hints", "group": "economy",
     "tell": "It leans toward the lantern.",
     "tactic": "Every learning spell you cast heals it a little. Hints remain "
               "available and always will; they simply cost you the rank here."},
    {"id": "mirrored", "name": "Mirrored", "group": "economy",
     "tell": "It answers in your own handwriting.",
     "tactic": "Repeating a failed approach does less each time. Change the "
               "shape of the answer, not the typing speed."},
    {"id": "escorted", "name": "Escorted", "group": "company",
     "tell": "It did not come alone.",
     "tactic": "Two lesser demands interrupt between phases. Clear them or they "
               "keep interrupting; they are the dungeon's floor pattern, no harder."},
)

MODIFIER_BY_ID = {m["id"]: m for m in BOSS_MODIFIERS}

_DEFAULT_PATTERNS = ("HASH_MAP", "ARRAY", "STRING", "TWO_POINTER", "STACK",
                     "TREE", "BFS", "DFS", "DP", "SORTING")


@dataclass
class BossBlueprint:
    id: str
    name: str
    archetype: str
    sprite: str
    colour: str
    bestiary_id: str
    dungeon: str
    region: str
    tier: int
    hp: int
    stance: str
    taunt: str
    phases: list
    modifiers: list
    demands: list
    reward: dict
    fingerprint: str

    def to_dict(self) -> dict:
        return asdict(self)


def assemble_boss(dungeon: Dungeon, *, run_seed: int | None = None) -> BossBlueprint:
    """Build this run's boss. Same dungeon, different descent, different fight."""
    run_seed = random.randrange(1 << 30) if run_seed is None else run_seed
    rng = random.Random((dungeon.seed ^ (run_seed * 2654435761)) & 0xFFFFFFFF)

    archetype = rng.choice(BOSS_ARCHETYPES)
    patterns = list(dungeon.patterns) or list(_DEFAULT_PATTERNS)
    rng.shuffle(patterns)

    phase_count = max(3, min(5, 2 + dungeon.tier // 2 + rng.choice((0, 1))))
    keys: list = []
    for key in archetype["bias"]:
        if key not in keys and len(keys) < phase_count:
            keys.append(key)
    pool = [p["key"] for p in BOSS_PHASE_POOL if p["key"] not in keys]
    rng.shuffle(pool)
    while len(keys) < phase_count and pool:
        keys.append(pool.pop())
    if "implement" not in keys:
        keys[-1] = "implement"              # a boss you never write code against
    rng.shuffle(keys)                       # is not a boss in this game
    if dungeon.tier >= 4 and "variant" in keys:
        keys.remove("variant")
        keys.append("variant")              # the disguised rematch closes the fight

    total_share = sum(_PHASE_BY_KEY[k]["share"] for k in keys)
    hp = int(archetype["hp"] * (0.8 + 0.16 * dungeon.tier))
    phases = []
    for index, key in enumerate(keys):
        spec = _PHASE_BY_KEY[key]
        phases.append({
            "index": index,
            "key": key,
            "label": spec["label"],
            "kind": spec["kind"],
            "demand": spec["demand"],
            "pattern": patterns[index % len(patterns)],
            "hp": max(8, int(round(hp * spec["share"] / total_share))),
            "relent": _relent_chain(DUNGEON_BY_ID[dungeon.id],
                                    DIFFICULTY_LADDER[min(len(DIFFICULTY_LADDER) - 1,
                                                          1 + dungeon.tier)]),
        })

    mod_count = max(1, min(3, 1 + dungeon.tier // 2))
    chosen: list = []
    groups: set = set()
    candidates = list(BOSS_MODIFIERS)
    rng.shuffle(candidates)
    for modifier in candidates:
        if len(chosen) >= mod_count:
            break
        if modifier["group"] in groups:
            continue                        # two order rules would contradict
        groups.add(modifier["group"])
        chosen.append(dict(modifier))

    plan = DUNGEON_BY_ID[dungeon.id]
    name = f"{archetype['title']} {plan.boss_epithet}"
    fingerprint = "-".join([archetype["id"]] + keys +
                           sorted(m["id"] for m in chosen))

    return BossBlueprint(
        id=f"{dungeon.id}_boss_{run_seed & 0xFFFF:04x}",
        name=name, archetype=archetype["id"], sprite=archetype["sprite"],
        colour=archetype["colour"], bestiary_id=archetype["bestiary_id"],
        dungeon=dungeon.id, region=dungeon.region, tier=dungeon.tier,
        hp=hp, stance=archetype["stance"],
        taunt=_boss_taunt(rng, archetype, chosen),
        phases=phases, modifiers=chosen,
        demands=[p["pattern"] for p in phases],
        reward={"xp": 180 + 90 * dungeon.tier, "gold": 60 + 30 * dungeon.tier,
                "drop": {"difficulty": "BOSS", "is_boss": True,
                         "upgrade": 1 if dungeon.tier >= 4 else 0}},
        fingerprint=fingerprint,
    )


_TAUNTS = (
    "Take your time. I am the one thing down here that has plenty.",
    "Say what I am. Out loud. I will wait for that and nothing else.",
    "Everyone writes the loop first. Everyone.",
    "You have seen this before, in a different coat, and you did not recognise it then.",
    "Correct is table stakes. I am asking for the other thing.",
    "The last one explained the approach beautifully and then wrote something else.",
)


def _boss_taunt(rng, archetype, modifiers) -> str:
    if modifiers and rng.random() < 0.5:
        return modifiers[0]["tell"]
    return rng.choice(_TAUNTS)


# ---------------------------------------------------------------------------
# Filling the rooms from the corpus
# ---------------------------------------------------------------------------

def resolve_encounter(request: dict, corpus: list, *, skills: dict | None = None,
                      solved_ids=(), recent_ids=(), rng: random.Random | None = None,
                      attempts: int = 0):
    """Turn a room's request into an actual problem out of the corpus.

    The search widens rather than failing: the requested difficulty first, then
    each rung of the relent chain, then the region's patterns dropped, then any
    permitted problem at all. A room that cannot find a problem is a dead end,
    and there are none of those here — the only way this returns None is an
    empty corpus.

    Difficulty walks down with `attempts`, which is why a room the player keeps
    losing to becomes a room they can win rather than a wall with a story."""
    if not corpus:
        return None
    rng = rng or random.Random(0)
    solved = set(solved_ids)
    recent = list(recent_ids)[:12]
    puzzle_kind = request.get("puzzle_kind", "")
    chain = request.get("relent") or [request.get("difficulty", "EASY")]
    start = min(attempts, len(chain) - 1)
    patterns = set(request.get("patterns") or ())

    def permitted(problem) -> bool:
        if skills is None:
            return True
        state = skills.get(skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"))
        return curriculum.is_permitted(problem, skills, skill_state=state)

    def kind_ok(problem) -> bool:
        if puzzle_kind:
            return problem.encounter_kind == puzzle_kind
        return problem.encounter_kind not in puzzles.PUZZLE_KINDS

    def pick(pool):
        if not pool:
            return None
        fresh = [p for p in pool if p.id not in solved and p.id not in recent]
        unseen = [p for p in pool if p.id not in recent]
        return rng.choice(fresh or unseen or pool)

    for difficulty in chain[start:]:
        for wide in (False, True):
            pool = [p for p in corpus
                    if p.difficulty == difficulty and kind_ok(p) and permitted(p)
                    and (wide or not patterns or p.pattern in patterns)]
            if wide:
                # Still prefer the region, but no longer require its patterns.
                local = [p for p in pool if p.realm == request.get("realm")]
                pool = local or pool
            choice = pick(pool)
            if choice is not None:
                return choice

    fallback = [p for p in corpus if kind_ok(p) and permitted(p)]
    return pick(fallback) or pick([p for p in corpus if permitted(p)]) or pick(corpus)


def populate(dungeon: Dungeon, corpus: list, *, skills: dict | None = None,
             solved_ids=(), rng: random.Random | None = None) -> dict:
    """Bind every room in a dungeon to a real problem id, once, up front.

    Returned as a separate map rather than written into the rooms: the map is
    what a save state stores, so a player returning tomorrow meets the same
    problem in the same room, while the dungeon itself stays pure geometry."""
    rng = rng or random.Random(dungeon.seed)
    chosen: dict = {}
    used: set = set(solved_ids)
    for room in dungeon.rooms:
        if not room.encounter:
            continue
        problem = resolve_encounter(room.encounter, corpus, skills=skills,
                                    solved_ids=(), recent_ids=sorted(used), rng=rng)
        if problem is None:
            continue
        chosen[str(room.id)] = problem.id
        used.add(problem.id)
    return chosen


# ---------------------------------------------------------------------------
# Running a descent. Plain JSON in, plain JSON out, so a run drops straight into
# the save state db.export_save already writes.
# ---------------------------------------------------------------------------

STATE_KEY = "dungeon_run"


def available_in(mode: str) -> bool:
    """Interview Mode has no dungeons. Enforced here rather than advised, so a
    caller cannot get one by forgetting to ask."""
    return mode != config.MODE_INTERVIEW


def enter(dungeon: Dungeon, *, run_seed: int | None = None,
          mode: str = config.MODE_ADVENTURE) -> dict:
    """Start a descent. Adventure Mode only — see the module docstring."""
    if not available_in(mode):
        raise ValueError("dungeons do not exist in Interview Mode")
    boss = assemble_boss(dungeon, run_seed=run_seed)
    return {
        "dungeon": dungeon.id,
        "seed": dungeon.seed,
        "run_seed": run_seed if run_seed is not None else 0,
        "mode": mode,
        "at": dungeon.entrance,
        "trail": [dungeon.entrance],          # entry order; the mines read this
        "visited": [dungeon.entrance],
        "cleared": [],
        "keys": [],
        "attempts": {},                       # room id (str) -> failed attempts
        "lit": [],                            # memo_tiles: rooms that stay free
        "turns": 0,                           # rotating_grid: quarter turns so far
        "shortcut_open": False,
        "boss": boss.to_dict(),
        "boss_phase": 0,
        "loot": [],
        "xp": 0,
        "gold": 0,
    }


def _room_ids(state, field_name) -> set:
    return set(state.get(field_name) or ())


def _fights_cleared(dungeon: Dungeon, state: dict) -> int:
    """Rooms cleared that actually asked something. Walking through an empty
    hall is progress on the map and not progress toward the chamber."""
    return sum(1 for r in state.get("cleared", ())
               if dungeon.rooms[r].demands_solving)


def current_difficulty(dungeon: Dungeon, state: dict, room_id: int) -> str:
    """What this room is asking for right now. Every failure walks one rung down
    the relent chain, and the chain bottoms out at the dungeon's floor — which is
    how a room stops being a wall without ever stopping being a room."""
    room = dungeon.rooms[room_id]
    chain = room.encounter.get("relent") if room.encounter else None
    if not chain:
        return dungeon.floor
    attempts = int(state.get("attempts", {}).get(str(room_id), 0))
    return chain[min(attempts, len(chain) - 1)]


def can_enter(dungeon: Dungeon, state: dict, room_id: int) -> tuple:
    """(allowed, reason). A refusal here always leaves at least one other move,
    which `options()` asserts."""
    here = state["at"]
    if room_id == here:
        return False, "you are already standing in it"
    passage = None
    for candidate in dungeon.passages_at(here):
        if candidate.other(here) == room_id:
            passage = candidate
            break
    if passage is None:
        return False, "no passage runs that way"
    if passage.kind == "SHORTCUT" and not state.get("shortcut_open"):
        return False, "that way is not open yet"
    if passage.revealed_by != -1 and passage.revealed_by not in _room_ids(state, "cleared"):
        return False, "there is no passage there that you can see"
    if passage.lock and passage.lock.side == room_id \
            and passage.lock.key_id not in _room_ids(state, "keys"):
        return False, f"locked: {passage.lock.tell or passage.lock.name}"

    target = dungeon.rooms[room_id]
    if target.kind == "BOSS":
        needed = target.seal.get("clears_required", 0)
        done = _fights_cleared(dungeon, state)
        if done < needed:
            return False, (f"the chamber is sealed until {needed} rooms here are "
                           f"cleared ({done} so far)")

    if dungeon.rule == "lifo_exit" and passage.kind != "SHORTCUT":
        # The winch is exempt. Hauling straight up is what a shortcut IS, and a
        # mine that refused it would have found a new way to trap someone.
        trail = state.get("trail") or [dungeon.entrance]
        going_back = dungeon.rooms[room_id].depth < dungeon.rooms[here].depth
        if going_back and len(trail) >= 2 and trail[-2] != room_id:
            return False, ("the mine only unloads from the top: the way back is "
                           f"room {trail[-2]}, in the order you came")
    return True, ""


def options(dungeon: Dungeon, state: dict) -> list:
    """Everything the player can do from where they stand. Never empty — that is
    requirement F at runtime, and the assertion at the bottom says so out loud."""
    here = state["at"]
    room = dungeon.rooms[here]
    out = []
    for neighbour in sorted(dungeon.neighbours(here)):
        allowed, reason = can_enter(dungeon, state, neighbour)
        target = dungeon.rooms[neighbour]
        out.append({"action": "move", "room": neighbour, "name": target.name,
                    "kind": target.kind, "depth": target.depth,
                    "available": allowed, "reason": reason})
    if room.demands_solving and here not in _room_ids(state, "cleared"):
        out.append({"action": "engage", "room": here, "available": True,
                    "difficulty": current_difficulty(dungeon, state, here),
                    "relent": (room.encounter or {}).get("relent", [dungeon.floor])})
    if here != dungeon.entrance:
        out.append({"action": "retreat", "available": True,
                    "path": exit_path(dungeon, here),
                    "reason": "walking out is always allowed, from anywhere"})
    else:
        out.append({"action": "leave", "available": True,
                    "reason": "you are standing on the threshold"})
    assert any(o["available"] for o in out), "a dungeon room with nothing to do"
    return out


def move(dungeon: Dungeon, state: dict, room_id: int) -> dict:
    allowed, reason = can_enter(dungeon, state, room_id)
    if not allowed:
        return {"moved": False, "reason": reason,
                "options": options(dungeon, state)}
    here = state["at"]
    via = next((p for p in dungeon.passages_at(here) if p.other(here) == room_id), None)
    state["at"] = room_id
    trail = state.setdefault("trail", [dungeon.entrance])
    if via is not None and via.kind == "SHORTCUT":
        state["trail"] = ([dungeon.entrance] if room_id == dungeon.entrance
                          else [dungeon.entrance, room_id])
    elif len(trail) >= 2 and trail[-2] == room_id:
        trail.pop()                                   # stepping back out
    else:
        trail.append(room_id)
    if room_id not in state["visited"]:
        state["visited"].append(room_id)

    if dungeon.rule == "sliding_frame":
        # The lit band widens right and gives ground on the left. It is never
        # carried back to the start, which is the entire lesson of the marsh.
        window = state.setdefault("window", [here])
        if room_id not in window:
            window.append(room_id)
        state["window"] = window[-3:]

    room = dungeon.rooms[room_id]
    if not room.demands_solving and room_id not in state["cleared"]:
        # A story room, a junction, an opened vault: there is nothing to beat, so
        # arriving is the whole of it. This is also how a lever gets pulled.
        state["cleared"].append(room_id)
        if "shortcut" in room.tags:
            state["shortcut_open"] = True

    return {"moved": True, "room": room.to_dict(), "depth": room.depth,
            "reward": room_reward(dungeon, room),
            "difficulty": current_difficulty(dungeon, state, room_id),
            "options": options(dungeon, state)}


def clear_room(dungeon: Dungeon, state: dict, room_id: int | None = None, *,
               solved: bool = True) -> dict:
    """Record the outcome of engaging the room the player is standing in.

    A failure is never terminal: it walks the relent chain down one rung and
    hands back what the room will ask for next time."""
    room_id = state["at"] if room_id is None else room_id
    room = dungeon.rooms[room_id]
    attempts = state.setdefault("attempts", {})
    if not solved:
        attempts[str(room_id)] = int(attempts.get(str(room_id), 0)) + 1
        return {"cleared": False,
                "next_difficulty": current_difficulty(dungeon, state, room_id),
                "relented": True,
                "note": "the room asks the same idea one rung easier. It will keep "
                        "asking, and you can also simply walk out.",
                "options": options(dungeon, state)}

    newly = []
    for target in dungeon.rooms:
        if target.id == room_id or (room.group and target.group == room.group):
            if target.id not in state["cleared"]:
                state["cleared"].append(target.id)
                newly.append(target.id)
    if room.key_id and room.key_id not in state["keys"]:
        state["keys"].append(room.key_id)
    if "shortcut" in room.tags:
        state["shortcut_open"] = True
    if dungeon.rule == "memo_tiles":
        for rid in newly:
            if rid not in state["lit"]:
                state["lit"].append(rid)
    if dungeon.rule == "rotating_grid" and len(state["cleared"]) % 4 == 0:
        state["turns"] = (state.get("turns", 0) + 1) % 4

    reward = room_reward(dungeon, room)
    state["xp"] += reward["xp"]
    state["gold"] += reward["gold"]
    return {"cleared": True, "rooms": newly, "reward": reward,
            "key": room.key_id, "shortcut_open": state["shortcut_open"],
            "carried": room.rule_data.get("base_case", False),
            "turns": state.get("turns", 0),
            "options": options(dungeon, state)}


def progress(dungeon: Dungeon, state: dict) -> dict:
    total = sum(1 for r in dungeon.rooms if r.demands_solving)
    seal = dungeon.rooms[dungeon.boss_room].seal
    return {
        "name": dungeon.name, "rule": dungeon.rule, "note": dungeon.rule_note,
        "rooms": len(dungeon.rooms), "visited": len(state.get("visited", [])),
        "cleared": len(state.get("cleared", [])),
        "cleared_fights": _fights_cleared(dungeon, state), "clearable": total,
        "keys": list(state.get("keys", [])),
        "seal": {"required": seal.get("clears_required", 0),
                 "met": _fights_cleared(dungeon, state) >= seal.get("clears_required", 0)},
        "shortcut_open": bool(state.get("shortcut_open")),
        "xp": state.get("xp", 0), "gold": state.get("gold", 0),
        "boss": state.get("boss", {}).get("name", ""),
        "exit_from_here": exit_path(dungeon, state.get("at", dungeon.entrance)),
    }


# ---------------------------------------------------------------------------
# Proofs
# ---------------------------------------------------------------------------

def _walkable(dungeon: Dungeon, state: dict, here: int, there: int) -> bool:
    """Ignores the mine's exit order, which `simulate` honours by walking rather
    than teleporting; everything else a door checks is checked here."""
    for passage in dungeon.passages_at(here):
        if passage.other(here) != there:
            continue
        if passage.kind == "SHORTCUT" and not state.get("shortcut_open"):
            return False
        if passage.revealed_by != -1 and passage.revealed_by not in state["cleared"]:
            return False
        if passage.lock and passage.lock.side == there \
                and passage.lock.key_id not in state["keys"]:
            return False
        target = dungeon.rooms[there]
        if target.kind == "BOSS":
            needed = target.seal.get("clears_required", 0)
            return _fights_cleared(dungeon, state) >= needed
        return True
    return False


def _route(dungeon: Dungeon, state: dict, target: int) -> list:
    here = state["at"]
    seen = {here}
    parent = {here: -1}
    queue, head = [here], 0
    while head < len(queue):
        node = queue[head]
        head += 1
        for other in dungeon.neighbours(node):
            if other in seen or not _walkable(dungeon, state, node, other):
                continue
            seen.add(other)
            parent[other] = node
            queue.append(other)
    return _path_from(parent, target) if target in parent else []


def simulate(dungeon: Dungeon, *, run_seed: int = 0, fail_each: int = 1) -> dict:
    """Play the whole dungeon the dumb way and see whether it holds.

    Every room is failed `fail_each` times before it is cleared, so the relent
    chain is exercised on every single encounter rather than assumed. The run
    ends by walking into the boss chamber, which is the claim requirement F
    actually makes: entrance to boss, using only rooms the player can clear."""
    state = enter(dungeon, run_seed=run_seed)
    blocked: list = []
    unreachable: set = set()
    guard = len(dungeon.rooms) * 8
    while guard > 0:
        guard -= 1
        room = dungeon.rooms[state["at"]]
        if not room.demands_solving and state["at"] not in state["cleared"]:
            state["cleared"].append(state["at"])
            if "shortcut" in room.tags:
                state["shortcut_open"] = True
        elif room.demands_solving and state["at"] not in state["cleared"] \
                and room.kind != "BOSS":
            for _ in range(fail_each):
                clear_room(dungeon, state, solved=False)
            clear_room(dungeon, state, solved=True)
        pending = [r.id for r in dungeon.rooms
                   if r.id not in state["cleared"] and r.id not in unreachable
                   and r.id not in (dungeon.boss_room, state["at"])]
        route = []
        for target in sorted(pending, key=lambda r: dungeon.rooms[r].depth):
            candidate = _route(dungeon, state, target)
            if len(candidate) > 1:
                route = candidate
                break
        if not route:
            break
        for step in route[1:]:
            result = move(dungeon, state, step)
            if not result["moved"]:
                blocked.append((state["at"], step, result["reason"]))
                unreachable.add(route[-1])
                break

    boss_route = _route(dungeon, state, dungeon.boss_room)
    entered_boss = False
    for step in boss_route[1:]:
        result = move(dungeon, state, step)
        if not result["moved"]:
            blocked.append((state["at"], step, result["reason"]))
            break
    else:
        entered_boss = state["at"] == dungeon.boss_room

    return {
        "cleared": len(state["cleared"]),
        "fights_cleared": _fights_cleared(dungeon, state),
        "visited": len(state["visited"]),
        "boss_reached": entered_boss,
        "shortcut_open": bool(state["shortcut_open"]),
        "exit_len": len(exit_path(dungeon, state["at"])),
        "blocked": blocked,
        "xp": state["xp"],
    }



def _clearable(dungeon: Dungeon, room: Room) -> bool:
    """Can a player get past this room at all?

    A room with no problem in it cannot block anyone — a shrine you answer
    wrongly still lets you walk on, and a vault is gated by its key rather than
    by a fight. A room that does hold a problem is passable only if its relent
    chain bottoms out at the dungeon floor, which every generated one does."""
    if room.kind == "BOSS":
        return True
    chain = (room.encounter or {}).get("relent") or []
    if not chain:
        return True
    return chain[-1] == dungeon.floor


def _key_aware_path(dungeon: Dungeon, target: int) -> list:
    """Walk from the threshold to `target`, picking up keys from rooms passed
    through. Shortcuts are excluded: they are a reward for arriving, so they may
    not be used to prove that arriving was possible."""
    held: set = set()
    seen = {dungeon.entrance}
    parent = {dungeon.entrance: -1}
    changed = True
    while changed:
        changed = False
        for room_id in list(seen):
            key = dungeon.rooms[room_id].key_id
            if key and key not in held:
                held.add(key)
                changed = True
            for passage in dungeon.passages_at(room_id):
                if passage.kind == "SHORTCUT":
                    continue
                other = passage.other(room_id)
                if other in seen:
                    continue
                if passage.revealed_by != -1 and passage.revealed_by not in seen:
                    continue
                if passage.lock and passage.lock.side == other \
                        and passage.lock.key_id not in held:
                    continue
                seen.add(other)
                parent[other] = room_id
                changed = True
    return _path_from(parent, target) if target in parent else []


def audit(dungeon: Dungeon) -> dict:
    """Every structural promise this module makes, checked on one dungeon."""
    count = len(dungeon.rooms)
    open_edges = [(p.a, p.b) for p in dungeon.passages if p.kind != "SHORTCUT"]
    adj = _adjacency(count, open_edges)
    dist, _ = _bfs(adj, dungeon.entrance)

    connected = len(dist) == count
    degrees_ok = all(len(dungeon.neighbours(r.id)) >= 1 for r in dungeon.rooms)

    boss_path = _key_aware_path(dungeon, dungeon.boss_room)
    path_clearable = bool(boss_path) and all(
        _clearable(dungeon, dungeon.rooms[r]) for r in boss_path)

    exits_ok = True
    for room in dungeon.rooms:
        path = exit_path(dungeon, room.id)
        if not path or path[0] != room.id or path[-1] != dungeon.entrance:
            exits_ok = False
            break

    # Every key must sit on the entrance side of the door it opens, or it is a
    # key locked inside its own cell.
    keys_ok = True
    for passage in dungeon.passages:
        if not passage.lock:
            continue
        trial = [(p.a, p.b) for p in dungeon.passages
                 if p.kind != "SHORTCUT" and p is not passage]
        near_side = set(_bfs(_adjacency(count, trial), dungeon.entrance)[0])
        holders = [r.id for r in dungeon.rooms if r.key_id == passage.lock.key_id]
        if not holders or not all(h in near_side for h in holders):
            keys_ok = False
            break
        if dungeon.boss_room not in near_side:
            keys_ok = False               # a lock standing between player and boss
            break

    reachable = _reachable(dungeon)
    clearable_rooms = [r for r in reachable
                       if r != dungeon.boss_room and dungeon.rooms[r].demands_solving]
    seal = dungeon.rooms[dungeon.boss_room].seal
    seal_ok = seal.get("clears_required", 0) <= len(clearable_rooms)

    encounters = [r for r in dungeon.rooms if r.encounter]
    relent_ok = all(_clearable(dungeon, r) for r in encounters)

    # Compared within a kind: a story room at depth nine should not be expected
    # to out-pay an elite encounter at depth eight, but an encounter deeper than
    # another encounter always must.
    reward_monotonic = True
    for kind in ("ENCOUNTER", "PUZZLE", "TREASURE", "VAULT"):
        by_depth = {}
        for room in dungeon.rooms:
            if room.kind == kind:
                by_depth.setdefault(room.depth, room_reward(dungeon, room)["xp"])
        depths = sorted(by_depth)
        if any(by_depth[a] > by_depth[b] for a, b in zip(depths, depths[1:])):
            reward_monotonic = False
            break

    puzzle_kinds = {r.encounter.get("puzzle_kind") for r in dungeon.rooms
                    if r.kind == "PUZZLE"}
    puzzle_kinds.discard(None)
    shortcut = any(p.kind == "SHORTCUT" for p in dungeon.passages)

    checks = {
        "connected": connected,
        "degrees_ok": degrees_ok,
        "boss_path_exists": bool(boss_path),
        "boss_path_clearable": path_clearable,
        "exit_from_every_room": exits_ok,
        "keys_obtainable": keys_ok,
        "seal_satisfiable": seal_ok,
        "relent_reaches_floor": relent_ok,
        "reward_monotonic_by_depth": reward_monotonic,
        "has_shortcut": shortcut,
        "mixed_contents": len(puzzle_kinds) >= 3
        and any(r.kind == "SHRINE" for r in dungeon.rooms)
        and any(r.kind == "STORY" for r in dungeon.rooms)
        and any(r.kind in ("TREASURE", "VAULT") for r in dungeon.rooms),
    }
    return {
        "id": dungeon.id, "archetype": dungeon.archetype, "rule": dungeon.rule,
        "rooms": count, "passages": len(dungeon.passages),
        "max_depth": dungeon.max_depth,
        "locks": sum(1 for p in dungeon.passages if p.lock),
        "boss_path_length": max(0, len(boss_path) - 1),
        "puzzle_kinds": len(puzzle_kinds),
        "checks": checks,
        "ok": all(checks.values()),
    }


def self_check(runs: int = 200, *, boss_samples: int = 12) -> dict:
    """Generate a lot of dungeons and prove the invariants on every one.

    This is the function the requirement asks for: real numbers, no sampling of
    the convenient cases, and a crash counted as a failure rather than swallowed."""
    ids = [d.id for d in DUNGEONS]
    stats = {
        "generated": 0, "crashes": 0, "failures": [],
        "rooms_total": 0, "rooms_min": 10 ** 6, "rooms_max": 0,
        "passages_total": 0, "locks_total": 0, "depth_total": 0,
        "boss_path_total": 0, "walkthroughs_reaching_boss": 0,
        "walkthroughs_blocked": 0, "walkthroughs_refused_a_step": 0,
        "cleared_total": 0, "run_xp_total": 0,
        "by_archetype": {}, "by_dungeon": {}, "by_rule": {},
        "check_failures": {}, "boss_variety": {},
    }
    for index in range(runs):
        dungeon_id = ids[index % len(ids)]
        salt = index // len(ids)
        try:
            dungeon = generate(dungeon_id, seed=dungeon_seed(dungeon_id, salt))
            report = audit(dungeon)
            # Walk every room's options once: `options` asserts that no room is
            # ever a dead end, so this turns that promise into a test.
            state = enter(dungeon, run_seed=index)
            for room in dungeon.rooms:
                state["at"] = room.id
                state["trail"] = exit_path(dungeon, room.id)[::-1]
                options(dungeon, state)
            run = simulate(dungeon, run_seed=index)
        except Exception as exc:                       # noqa: BLE001 - counted, not hidden
            stats["crashes"] += 1
            stats["failures"].append(f"{dungeon_id}/{salt}: {type(exc).__name__}: {exc}")
            continue

        stats["generated"] += 1
        if run["boss_reached"]:
            stats["walkthroughs_reaching_boss"] += 1
        else:
            stats["failures"].append(f"{dungeon_id}/{salt}: boss unreachable in play")
        if run["blocked"]:
            # `simulate`'s router teleports along the shortest path and does not
            # know the mine's exit order, so the lifo dungeon refuses some of its
            # steps and names the legal one instead. A refusal that still ends
            # with the boss reached and a way out is the rule working, which is
            # why only the other kind is counted against the build.
            stats["walkthroughs_refused_a_step"] += 1
            if not run["boss_reached"] or run["exit_len"] < 1:
                stats["walkthroughs_blocked"] += 1
                stats["failures"].append(
                    f"{dungeon_id}/{salt}: blocked {run['blocked'][0]}")
        stats["cleared_total"] += run["fights_cleared"]
        stats["run_xp_total"] += run["xp"]
        stats["rooms_total"] += report["rooms"]
        stats["rooms_min"] = min(stats["rooms_min"], report["rooms"])
        stats["rooms_max"] = max(stats["rooms_max"], report["rooms"])
        stats["passages_total"] += report["passages"]
        stats["locks_total"] += report["locks"]
        stats["depth_total"] += report["max_depth"]
        stats["boss_path_total"] += report["boss_path_length"]
        stats["by_archetype"].setdefault(dungeon.archetype, 0)
        stats["by_archetype"][dungeon.archetype] += 1
        stats["by_rule"].setdefault(dungeon.rule, 0)
        stats["by_rule"][dungeon.rule] += 1
        stats["by_dungeon"].setdefault(dungeon_id, 0)
        stats["by_dungeon"][dungeon_id] += 1
        for name, passed in report["checks"].items():
            if not passed:
                stats["check_failures"].setdefault(name, 0)
                stats["check_failures"][name] += 1
                stats["failures"].append(f"{dungeon_id}/{salt}: {name}")

        if salt == 0:
            fingerprints = {assemble_boss(dungeon, run_seed=s).fingerprint
                            for s in range(boss_samples)}
            stats["boss_variety"][dungeon_id] = len(fingerprints)

    generated = max(1, stats["generated"])
    stats["rooms_mean"] = round(stats["rooms_total"] / generated, 1)
    stats["passages_mean"] = round(stats["passages_total"] / generated, 1)
    stats["locks_mean"] = round(stats["locks_total"] / generated, 2)
    stats["depth_mean"] = round(stats["depth_total"] / generated, 1)
    stats["boss_path_mean"] = round(stats["boss_path_total"] / generated, 1)
    stats["cleared_mean"] = round(stats["cleared_total"] / generated, 1)
    stats["run_xp_mean"] = round(stats["run_xp_total"] / generated, 1)
    stats["all_checks_passed"] = (not stats["check_failures"] and not stats["crashes"]
                                  and stats["walkthroughs_reaching_boss"] == generated
                                  and not stats["walkthroughs_blocked"])
    stats["regions_covered"] = len({DUNGEON_BY_ID[i].region for i in stats["by_dungeon"]})
    stats["failures"] = stats["failures"][:20]
    return stats


__all__ = [
    "ARCHETYPES", "LAYOUT_RULES", "ROOM_KINDS", "DIFFICULTY_LADDER",
    "DUNGEONS", "DUNGEON_BY_ID", "DUNGEONS_BY_REGION", "dungeons_for_region",
    "DungeonPlan", "Dungeon", "Room", "Passage", "Lock", "BossBlueprint",
    "BOSS_ARCHETYPES", "BOSS_PHASE_POOL", "BOSS_MODIFIERS", "MODIFIER_BY_ID",
    "STATE_KEY", "dungeon_seed", "generate", "assemble_boss", "rotate_view",
    "room_reward", "roll_room_treasure", "exit_path", "enter", "options",
    "can_enter", "move", "clear_room", "current_difficulty", "progress",
    "resolve_encounter", "populate",
    "audit", "simulate", "self_check",
]


if __name__ == "__main__":                       # pragma: no cover - dev tool
    import json as _json
    print(_json.dumps(self_check(), indent=2, sort_keys=True))
