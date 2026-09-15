"""The secret arts: what the hidden sages teach, and why it hits harder.

A sage stands somewhere in every fighting region. Which sage depends on the
class you are playing — the Berserker finds a scarred woman behind the mine
face, the Seer finds an old man who has been sitting in the same chair in the
Stringwood for eleven years — and each of them sets a gauntlet keyed to that
region's difficulty. Clear it and you are taught one line of Python you did not
have before. `gauntlet/sages.py` owns WHO and WHAT THE TRIAL IS. This module
owns the line itself, and the arithmetic that says the line is worth finding.

THE ONE RULE THIS FILE EXISTS TO ENFORCE
----------------------------------------
An art out-damages an ordinary move BECAUSE IT DEMANDS MORE PYTHON. Never
because you found it.

There is no discovery bonus anywhere in this module. No secret-art multiplier,
no flat bonus for having cleared a gauntlet, no term that reads the player's
progress. Damage comes from exactly where every other cast's damage comes from:
`incantation.measure_complexity` reads the line the player actually typed and
`incantation._damage_for` turns its weight into a number. An art is stronger
only because its line scores higher on that same measurement, at the same
scaffold tier, against the same ruler.

    Hardest ordinary line in the game   SIFT, chapter II          raw 25.75
    Weakest art in the catalogue        THE KEY CUT TO FIT        raw 19.45
    Strongest art                       THE INDEX OF EVERY FRAME  raw 58.60

The bar is per AREA, not global — the weakest art is a Village art and the only
ordinary lines a player standing in the Village has reach 9.60. `ranking_report()`
prints the whole table and `self_check()` fails if a single art stops clearing
the bar. The fix for an art that does not clear it is to make the art harder. It
is never to raise its number, and there is no number here to raise:
`Incantation.power` is set to the FLOOR the engine already treats it as,
computed from the art's own tier-0 measurement, so it never binds and never
decides anything.

WHERE THIS ARGUMENT STOPS BEING TRUE, WHICH IS NOT IN THIS FILE
---------------------------------------------------------------
`incantation.measure_complexity` clamps at `SCORE_FULL = 40.0` raw. The sixty-six
ordinary lines never reach it — SIFT, the hardest, is 34.00 even at RECALLED. The
arts pass it at PROMPTED and by RECALLED ninety-four of ninety-six are pinned
there, which means the whole catalogue resolves to THREE distinct damage numbers
at the tier a drilled art is actually cast at. Above raw 40 more Python buys
nothing.

That is not fixable here. There are six raw points between the hardest ordinary
line and the ceiling, and a sixteen-rung secret ladder does not fit in six
points. `saturation_report()` measures it every run and `handover()["score_full"]`
names the one edit: raise `incantation.SCORE_FULL` to about 85.0 and bring
`DAMAGE_UNIT` with it.

WHAT AN ART IS, MECHANICALLY
----------------------------
Two registrations into two existing catalogues, and not one new combat rule:

  * a real `incantation.Incantation` — same dataclass, same template with holes,
    same ghost line, same four scaffold tiers, same three validation layers,
    same sandbox, same wasted turn on a miss;
  * a real `movesets.Move` — an ART MOVE whose spine is that line plus, for the
    wider shapes, the hardest ordinary lines already available in that area.

Both are registered by id so every existing call site works untouched:
`incantation.render_template`, `incantation.cast`, `movesets.plan_move`,
`movesets.resolve_move`, `movesets.fx_for`, `movesets.record`. What is
deliberately NOT done is adding the art lines to `incantation.CATALOGUE`, which
is the single omission that stops `learn_from_clear()` from ever handing one out
as a clear reward, or adding the art moves to any skill-tree node. A sage or
nothing.

AoE, WHICH IS movesets' AND NOT OURS
------------------------------------
The Berserker's arts are STORMs because a Berserker rewrites a whole collection
in one line and that is literally what the template does; the Seer's are SINGLE
because a Seer's line locates exactly one element. The shapes, the target
counts, the splash falloff and the "hitting four monsters costs four monsters'
worth of thinking" price model are all `movesets.SHAPES`. This module chooses a
shape per class and adds nothing to how one resolves, because a second area
system is how the first one quietly stops being true.

REPETITION STILL RULES
----------------------
An art the player never masters is a trophy. Four things keep it in their hands,
and none of them is a new mechanic:

  * the movebook has no slot limit, so an art never costs an ordinary move its
    place and nobody has to choose between their book and their secret;
  * `demandable()` puts arts into the ordinary turn rotation, interleaved;
  * a wrong line wastes the line, not the fight — `movesets.resolve_move` keeps
    whatever else landed, and `incantation._fail` is the only penalty there is;
  * repetition is the ONLY thing that can raise the damage spine itself. Casting
    an art again raises its scaffold tier, a higher tier means the player types
    more of the line, and `measure_complexity` sees that directly. An art at
    GUIDED is worth about half an art at RECALLED, measured, every time.

THREE DAMAGE SYSTEMS, ONE ORDER
-------------------------------
See `ORDER_OF_OPERATIONS` and `weapon_note()`. In one sentence: the typing sets
the payload, the shape divides it, the class element is the one matchup term,
and the forge never touches damage at all.

Pure stdlib. Importing this module builds plain data and NOTHING ELSE — in
particular it does not write into `incantation.BY_ID` or `movesets.BY_ID`.
Registration is an explicit call: `register()` at wiring time, `registered()`
for a block that wants to measure and then put the catalogues back.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, asdict, replace

from . import elements, incantation, movesets, world


# ---------------------------------------------------------------------------
# 1. Where the sages are
# ---------------------------------------------------------------------------
# `world.REGIONS` has seventeen entries and no chapter number on any of them.
# `curriculum.CHAPTERS` names a region for nine of the eleven chapters, which
# leaves eight regions with no stated difficulty. ASSUMPTION, declared rather
# than hidden: the eight are placed at the chapter of the region that unlocks
# them, which is what `world.REGIONS[*]["unlocks"]` already implies. If
# curriculum later claims one of them, `self_check()` will report the
# disagreement rather than silently keeping this table's opinion.

REGION_CHAPTER: dict = {
    "python_village": 0,
    "fields_of_syntax": 2,
    "hashmap_highlands": 3,
    "stringwood_labyrinth": 3,
    "array_caverns": 3,
    "sliding_window_marsh": 4,
    "twin_pointer_pass": 4,
    "stack_queue_mines": 5,
    "recursive_forest": 6,
    "binary_tree_canopy": 6,
    "matrix_citadel": 7,
    "graph_wastes": 7,
    "dp_ruins": 8,
    "complexity_tower": 8,
    "debugging_dungeon": 9,
    "coding_coliseum": 10,
    "null_kings_castle": 10,
}


@dataclass(frozen=True)
class Sanctum:
    """One hidden room, and the rank of the art taught in it.

    `sages.py` owns the person standing in it and the gauntlet they set. What is
    here is only what the ART needs: where it is, how hard the area is, what
    colour the room is drawn in, and which rank of the ladder this is.
    """
    id: str                  # short key: "marsh", "castle"
    region: str              # world.REGIONS id
    rank: int                # 1..16, the order a player meets them in
    chapter: int             # curriculum chapter: the difficulty of the trial
    skill: str               # skills.SKILLS id the arts here train
    name: str                # what the room is called once you have found it
    where: str               # the one line that tells a player it is findable
    ink: str                 # the colour the sanctum's script is drawn in
    sigil: str               # the glyph that turns before an art accepts input

    @property
    def numeral(self) -> str:
        return _ROMAN[self.rank]

    @property
    def element(self) -> str:
        return elements.affinity_for(self.region)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["numeral"] = self.numeral
        data["element"] = self.element
        data["region_name"] = world.REGION_BY_ID.get(self.region, {}).get("name", "")
        return data


_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
          "XI", "XII", "XIII", "XIV", "XV", "XVI")


def _sanctum(short, region, rank, skill, name, where, ink, sigil) -> Sanctum:
    return Sanctum(id=short, region=region, rank=rank,
                   chapter=REGION_CHAPTER[region], skill=skill, name=name,
                   where=where, ink=ink, sigil=sigil)


SANCTUMS: tuple = (
    _sanctum("village", "python_village", 1, "PYTHON",
             "The Step Nobody Swept",
             "Every step in the village is swept every morning. One is swept "
             "every evening, by somebody nobody sees arrive.", "#d6b98c", "◌"),
    _sanctum("syntax", "fields_of_syntax", 2, "PYTHON",
             "The Unmown Acre",
             "A square of field nobody has cut, in the middle of land that is "
             "otherwise kept.", "#cfd8b0", "▚"),
    _sanctum("highlands", "hashmap_highlands", 3, "HASH_MAP",
             "The Vault With No Rune",
             "One vault on the plateau has no key glowing anywhere near it.",
             "#f2dc6a", "◈"),
    _sanctum("stringwood", "stringwood_labyrinth", 4, "STRING",
             "The Clearing That Spells Nothing",
             "Every grove in the wood rearranges into a word. One does not.",
             "#8fd07a", "❧"),
    _sanctum("caverns", "array_caverns", 5, "ARRAY",
             "Alcove Minus One",
             "The numbering starts at zero. There is an alcove before it.",
             "#bf8f4f", "▣"),
    _sanctum("marsh", "sliding_window_marsh", 6, "SLIDING_WINDOW",
             "The Standing Frame",
             "The frame slides across the reeds all day. In one place it stops.",
             "#8fd07a", "▤"),
    _sanctum("pass", "twin_pointer_pass", 7, "TWO_POINTER",
             "The Third Lantern",
             "Two lanterns cross the bridge. On certain nights a third is lit "
             "and does not move.", "#7ec8ff", "◇"),
    _sanctum("mines", "stack_queue_mines", 8, "STACK",
             "The Cart That Was Never Unloaded",
             "At the bottom of the last shaft, a cart still full, under a cart "
             "that is empty.", "#e06a3c", "▰"),
    _sanctum("forest", "recursive_forest", 9, "RECURSION",
             "The Clearing That Contains Itself",
             "Every clearing holds a smaller copy of the forest. One holds a "
             "copy the same size.", "#6a4f8f", "◉"),
    _sanctum("canopy", "binary_tree_canopy", 10, "TREE",
             "The Branch That Does Not Fork",
             "Every branch splits twice. There is one that goes straight and "
             "keeps going.", "#8fbf6a", "⋔"),
    _sanctum("citadel", "matrix_citadel", 11, "MATRIX",
             "The Room Off The Grid",
             "The floor plan turns ninety degrees. One room turns with it and "
             "stays where it was.", "#bf8f4f", "▦"),
    _sanctum("wastes", "graph_wastes", 12, "GRAPH",
             "The Ruin With One Road",
             "Every ruin out here connects to several others. One connects to "
             "nothing, and somebody lives in it.", "#f2dc6a", "✦"),
    _sanctum("ruins", "dp_ruins", 13, "DP",
             "The Tile Paid For Twice",
             "Solved tiles stay lit. One tile is lit twice as bright, and no "
             "record says who solved it.", "#e8c37d", "▩"),
    _sanctum("tower", "complexity_tower", 14, "BIG_O",
             "The Floor Between Floors",
             "Each floor holds twice the enemies of the one below. Between the "
             "seventh and the eighth there is a landing.", "#7ec8ff", "◬"),
    _sanctum("dungeon", "debugging_dungeon", 15, "DEBUGGING",
             "The Cell That Locks From Inside",
             "The cells hold broken programs. One is bolted on the wrong side "
             "and the occupant is not a program.", "#e06a3c", "◎"),
    _sanctum("coliseum", "coding_coliseum", 16, "SPEED",
             "Under The Sand",
             "The arena floor is sand. Somebody has been living beneath it "
             "since before the clock was installed.", "#e8d8a0", "◐"),
)

SANCTUM_BY_ID: dict = {s.id: s for s in SANCTUMS}
SANCTUM_BY_REGION: dict = {s.region: s for s in SANCTUMS}


def sanctum_for_region(region_id: str) -> Sanctum | None:
    return SANCTUM_BY_REGION.get(region_id)


# ---------------------------------------------------------------------------
# 2. The ruler
# ---------------------------------------------------------------------------
# There is exactly one complexity measure in this game and it is not in this
# file. `incantation.measure_complexity` reads a cast — the constructs in the
# line, which holes the player authored at this tier, how deep their own
# expressions nest, whether the form is a comprehension, whether two ideas were
# composed — and turns it into a `Complexity` with a `score` out of a hundred
# and the `weight` that score becomes when it is multiplied into damage.
#
# Everything below is a wrapper. That is on purpose: an art that were ranked on
# a private ruler would be ranked on a ruler the damage does not consult, and
# the whole argument of this file would be decoration.
#
# `raw` rather than `score` is what the bar is stated in. `score` clamps at a
# hundred, and several arts are past it; `raw` keeps discriminating above the
# cap, which matters when the question is "which of these is harder" rather than
# "how hard is this for the damage formula".

ART_TIER_REFERENCE = 1        # the tier every published comparison is made at


def measure(art, *, tier: int = ART_TIER_REFERENCE, answers: dict | None = None):
    """What the engine will say this art demanded. Returns incantation.Complexity."""
    art = BY_ID[art] if isinstance(art, str) else art
    return incantation.measure_complexity(
        art.inc, dict(answers or art.inc.example), tier=tier)


def measure_line(inc, *, tier: int = ART_TIER_REFERENCE):
    """The same reading for any ordinary incantation, so the table is one table."""
    inc = incantation.BY_ID[inc] if isinstance(inc, str) else inc
    return incantation.measure_complexity(inc, dict(inc.example), tier=tier)


def ordinary_lines(chapter: int) -> list:
    """Every ordinary line a player in this area could already cast."""
    return [i for i in incantation.CATALOGUE if i.chapter <= int(chapter)]


def ordinary_line_ceiling(chapter: int, *, tier: int = ART_TIER_REFERENCE) -> tuple:
    """The hardest ordinary line available in an area, and what it measures.

    Read off `incantation.CATALOGUE` at call time, so if the rewrite of that
    file adds something harder the bar tightens by itself instead of going
    quietly out of date.
    """
    best, best_raw = None, 0.0
    for inc in ordinary_lines(chapter):
        raw = measure_line(inc, tier=tier).raw
        if raw > best_raw:
            best, best_raw = inc, raw
    return best, round(best_raw, 2)


def ordinary_moves(chapter: int, *, shape: str = "") -> list:
    """Every ordinary MOVE a player in this area could already cast."""
    return [m for m in movesets.CATALOGUE
            if m.chapter <= int(chapter) and (not shape or m.shape == shape)]


def move_payload(move, *, tier: int = ART_TIER_REFERENCE) -> float:
    """What a competent cast of a whole move is worth, before shape and wheel.

    The sum of `incantation.expected_damage` over the spine, which is what
    `movesets.resolve_move` will actually add up when every line lands.
    """
    move = movesets.BY_ID[move] if isinstance(move, str) else move
    return round(sum(incantation.expected_damage(i, tier=tier)
                     for i in move.incantations), 1)


def move_demand(move, *, tier: int = ART_TIER_REFERENCE) -> float:
    """How much Python a whole move demanded: summed raw complexity."""
    move = movesets.BY_ID[move] if isinstance(move, str) else move
    return round(sum(measure_line(i, tier=tier).raw for i in move.incantations), 2)


def ordinary_move_ceiling(chapter: int, *, shape: str = "",
                          tier: int = ART_TIER_REFERENCE) -> tuple:
    """The strongest ordinary move available in an area, and its payload."""
    best, best_pay = None, 0.0
    for move in ordinary_moves(chapter, shape=shape):
        if move.id in ART_MOVE_IDS:
            continue
        pay = move_payload(move, tier=tier)
        if pay > best_pay:
            best, best_pay = move, pay
    return best, round(best_pay, 1)


# ---------------------------------------------------------------------------
# 3. Shape, rung and the lines an art is cast beside
# ---------------------------------------------------------------------------
# A class casts one way. Six classes, four shapes, and the shape is the class
# fantasy expressed in `movesets.SHAPES` rather than in a second vocabulary.

# The class's own word for how its arts land, kept because it is what the player
# is told and what the sage says. It is a LABEL: the mechanical shape is
# `CLASS_SHAPE` below, and it lives in `movesets`.
FOCUSED = "FOCUSED"     # one target, all of it
SWEEPING = "SWEEPING"   # everything standing
CHAINED = "CHAINED"     # jumps, quieter each time
SPREAD = "SPREAD"       # the target and what is beside it
TOOLED = "TOOLED"       # built first, then turned on something
SURGICAL = "SURGICAL"   # one target, chosen by the line itself

# The shorthand the catalogue is authored in.
SINGLE, SWEEP, CHAIN, SPLIT, MARK, TOOL = (
    FOCUSED, SWEEPING, CHAINED, SPREAD, SURGICAL, TOOLED)

TACTICS: tuple = (FOCUSED, SWEEPING, CHAINED, SPREAD, TOOLED, SURGICAL)

CLASS_TACTIC_LABEL: dict = {
    "analyst": FOCUSED, "berserker": SWEEPING, "archivist": CHAINED,
    "warden": SPREAD, "artificer": TOOLED, "seer": SURGICAL,
}

CLASS_SHAPE: dict = {
    "analyst": movesets.SINGLE,     # one claim, one target, all of it
    "seer": movesets.SINGLE,        # surgical: the line locates exactly one thing
    "warden": movesets.CLEAVE,      # a ward covers the thing and the thing beside it
    "artificer": movesets.CLEAVE,   # the tool is built, then it bites twice
    "archivist": movesets.CHAIN,    # files onward, weaker at every jump
    "berserker": movesets.STORM,    # rewrites the whole collection, hits the room
}

CLASS_TACTIC: dict = {
    "analyst": "States the whole claim in one line and puts all of it into one "
               "target.",
    "seer": "One target. The line's whole job is finding which one, so the cast "
            "also reads that monster's weakness aloud.",
    "warden": "Two lines, the target and its neighbour. A ward does not stop at "
              "one monster.",
    "artificer": "Two lines: the tool, then what it is turned on.",
    "archivist": "Two lines that jump to everything of the same kind, quieter at "
                 "every jump.",
    "berserker": "Three lines. Everything still standing is in them.",
}

# Rank 1..16 mapped onto the seven rungs `movesets.fade` is written against, so
# an art taught in the Fields ages exactly like a rung-one tree move and one
# taught under the castle does not age at all. An art is not exempt from the
# fade curve; being secret is not being permanent.
ART_RUNG_MIN, ART_RUNG_MAX = 1, movesets.MAX_RUNG


def rung_for(rank: int) -> int:
    span = max(1, len(SANCTUMS) - 1)
    step = (ART_RUNG_MAX - ART_RUNG_MIN) * (int(rank) - 1) / span
    return int(ART_RUNG_MIN + round(step))


def _companions(art_inc, chapter: int, wanted: int) -> tuple:
    """The ordinary lines an art is cast beside, when its shape wants more.

    Chosen by rule rather than by hand, and the rule is deliberately the one
    that is hardest on the art: take the HARDEST ordinary lines in the area that
    can stand on the same field. So an art move is the strongest ordinary move
    that could be built there with one line swapped for the art's, and it can
    only come out ahead if the art's own line is the harder line. It is the
    least flattering comparison available, which is the point.

    One line per construct family where possible, because three lines that drill
    the same idiom is a rep, not a move.
    """
    if wanted <= 0:
        return ()
    need = set(art_inc.requires)
    pool = [i for i in ordinary_lines(chapter)
            if set(i.requires) <= need and i.id != art_inc.id]
    pool.sort(key=lambda i: (-measure_line(i).raw, i.id))
    picked, families = [], {art_inc.family}
    for inc in pool:
        if inc.family in families:
            continue
        picked.append(inc.id)
        families.add(inc.family)
        if len(picked) == wanted:
            return tuple(picked)
    for inc in pool:                       # families exhausted; fall back
        if inc.id not in picked:
            picked.append(inc.id)
        if len(picked) == wanted:
            break
    return tuple(picked)


# The art's `power` is the FLOOR `incantation._damage_for` already treats it as:
# `max(DAMAGE_UNIT * weight, power * POWER_FLOOR_SHARE)`. It is set from the
# art's own tier-0 measurement, which makes it exactly non-binding — the floor
# equals what the worst possible cast of the art is worth, and every better cast
# is decided by the typing. There is no number in this file that can be raised
# to make an art stronger, and `self_check()` proves the floor never binds.

def power_floor(art_inc) -> int:
    weakest = incantation.measure_complexity(art_inc, dict(art_inc.example), tier=0)
    return max(1, int(round(incantation.DAMAGE_UNIT * weakest.weight
                            / incantation.POWER_FLOOR_SHARE)))


COST_PER_RAW = 10.0           # focus per point of demanded complexity
COST_FLOOR, COST_CEIL = 3, 6   # an art is never as cheap as an ordinary line
PAR_BASE, PAR_PER_RAW, PAR_CEIL = 14.0, 0.85, 70.0


def cost_for(raw: float) -> int:
    return max(COST_FLOOR, min(COST_CEIL, int(round(raw / COST_PER_RAW))))


def par_for(raw: float) -> float:
    return round(min(PAR_CEIL, PAR_BASE + PAR_PER_RAW * raw), 1)


# ---------------------------------------------------------------------------
# 4. An art
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Art:
    """One secret line, the move it is cast as, and the measurement behind both.

    `inc` is the `incantation.Incantation` the player types. `move_id` names the
    `movesets.Move` the engine actually resolves, whose spine begins with that
    line. Everything else here is the wrapper: which sage taught it, where, and
    what the ruler says about it.
    """
    id: str
    name: str
    class_id: str
    sanctum: str
    tactic: str                # the class's own word for how it lands
    inc: object                # incantation.Incantation
    note: str

    # -- the room ----------------------------------------------------------
    @property
    def room(self) -> Sanctum:
        return SANCTUM_BY_ID[self.sanctum]

    @property
    def rank(self) -> int:
        return self.room.rank

    @property
    def region(self) -> str:
        return self.room.region

    @property
    def rung(self) -> int:
        return rung_for(self.rank)

    # -- the line ----------------------------------------------------------
    @property
    def incantation_id(self) -> str:
        return self.inc.id

    @property
    def template(self) -> str:
        return self.inc.template

    @property
    def holes(self) -> tuple:
        return self.inc.holes

    @property
    def chapter(self) -> int:
        return self.inc.chapter

    @property
    def skill(self) -> str:
        return self.inc.skill

    @property
    def par_seconds(self) -> float:
        return self.inc.par_seconds

    # -- the move ----------------------------------------------------------
    @property
    def move_id(self) -> str:
        return "art_move_%s_%s" % (self.class_id, self.sanctum)

    @property
    def move(self):
        ensure_registered()
        return movesets.BY_ID[self.move_id]

    @property
    def shape(self) -> str:
        return CLASS_SHAPE[self.class_id]

    @property
    def spine(self) -> tuple:
        return self.move.spine

    @property
    def element(self) -> str:
        """The class's element, from `movesets.CLASS_ELEMENT`. An art does not
        get an element of its own; a second elemental opinion would be a second
        multiplier. The sanctum's own affinity is the colour of the ROOM, and it
        is why that sage settled there — see `Sanctum.element`."""
        return movesets.CLASS_ELEMENT.get(self.class_id, elements.NEUTRAL)

    @property
    def cost(self) -> int:
        """Focus, summed over the spine. Three lines cost three lines' worth."""
        return self.move.cost

    @property
    def max_targets(self) -> int:
        return movesets.SHAPES[self.shape].max_targets

    @property
    def power(self) -> int:
        """The FLOOR on `Incantation.power`, not what the art hits for.

        `incantation._damage_for` takes `max(DAMAGE_UNIT * weight, power *
        POWER_FLOOR_SHARE)`, and an art's floor is computed from its own tier-0
        measurement so it never binds. Kept as a property because it is a
        reasonable thing to ask an art and because `sages.overlap_report()`
        reads it; do not mistake it for a damage number. See section 9.
        """
        return self.inc.power

    # -- the ruler ---------------------------------------------------------
    def complexity(self, *, tier: int = ART_TIER_REFERENCE):
        return measure(self, tier=tier)

    def payload(self, *, tier: int = ART_TIER_REFERENCE) -> float:
        return move_payload(self.move_id, tier=tier)

    def to_dict(self, *, reach: int = 0) -> dict:
        score = self.complexity()
        return {
            "id": self.id, "name": self.name, "class": self.class_id,
            "sanctum": self.sanctum, "region": self.region, "rank": self.rank,
            "numeral": self.room.numeral, "rung": self.rung,
            "chapter": self.chapter, "skill": self.skill,
            "shape": self.shape, "tactic": self.tactic,
            "element": self.element, "cost": self.cost,
            "par_seconds": self.par_seconds, "note": self.note,
            "complexity": score.to_dict(),
            "payload": self.payload(),
            "incantation": self.inc.to_dict(),
            "move": self.move.to_dict(reach=reach),
            "room": self.room.to_dict(),
        }


# Hole-kind shorthand, so the catalogue below reads as a table.
_E, _N, _X, _B, _L = (incantation.ENEMY, incantation.NAME, incantation.EXPR,
                      incantation.BINDER, incantation.LITERAL)

_CATALOGUE: list = []


def _art(class_id: str, short: str, name: str, template: str, *, holes: dict,
         note: str, mode: str, demo: dict, example: dict, lands: str = "",
         proves: str = "", assertion: str = "", snapshot: dict | None = None,
         requires: tuple = (), imports: tuple = (), miss: str = "") -> Art:
    """Author one art. Power, cost and par are MEASURED, never passed.

    `mode` is the class's own word for how the line lands and is kept for the
    player-facing text; the mechanical shape comes from `CLASS_SHAPE` and lives
    in `movesets`.
    """
    room = SANCTUM_BY_ID[short]
    ident = "art_%s_%s" % (class_id, short)
    snapshot = dict(snapshot or {})
    if not assertion:
        if not (lands and proves):
            raise ValueError("%s: needs either an assertion or lands+proves" % ident)
        snapshot.setdefault("was", "{%s}" % lands)
        assertion = ("{%s} == (%s) and {%s} != __b__['was']"
                     % (lands, proves, lands))
    draft = incantation._inc(
        ident, name, template, holes=holes, skill=room.skill,
        chapter=room.chapter, note=note, family="art_%s" % class_id,
        effect="art_%s" % class_id, cost=2, power=8, par=20.0,
        requires=requires, imports=imports, demo=demo, example=example,
        snapshot=snapshot, assertion=assertion, miss=miss,
    )
    raw = incantation.measure_complexity(draft, dict(draft.example),
                                         tier=ART_TIER_REFERENCE).raw
    inc = replace(draft, power=power_floor(draft), cost=cost_for(raw),
                  par_seconds=par_for(raw))
    art = Art(id=ident, name=name, class_id=class_id, sanctum=short,
              tactic=mode, inc=inc, note=note)
    _CATALOGUE.append(art)
    return art
_NUMS8 = "[3, 1, 4, 1, 5, 9, 2, 6]"
_NUMS5 = "[3, 1, 4, 1, 5]"
_SORTED4 = "[1, 2, 3, 4]"
_GRID = "[[1, 2, 3], [4, 5, 6], [7, 8, 9]]"
_GRAPH = "{'a': ['b', 'c'], 'b': ['a'], 'c': []}"
_TREE = ("{'val': 5, 'left': {'val': 3, 'left': None, 'right': None}, "
         "'right': {'val': 8, 'left': None, 'right': None}}")
_DP = "[1, 1, 0, 0, 0, 0]"
_CASES = "[(1, 2), (2, 4)]"
_STEP = "lambda v: v * 2"
_SOLVE = "lambda v: v + 1"


# ===========================================================================
# I. THE STEP NOBODY SWEPT — Python Village
# ===========================================================================
# The first sanctum, and the only one a player can reach before they have
# cleared anything. These are the SHALLOWEST arts in the catalogue on purpose:
# the bottom rung of the ladder has to be a rung, not a cliff, and a player who
# finds this room in their first hour should walk out with a line they can hold
# in their head. Every one of them is still a long way above `sever`, the
# hardest ordinary line a player standing here can cast: the six measure 19.45
# to 37.40 against its 9.60, which is 2.03x to 3.90x, the widest margin in the
# catalogue. Being the easiest arts in the game does not make them easy.
#
# Nothing here uses a construct chapter one has not met. The difficulty is
# entirely in saying three chapter-one things at once.

_art("analyst", "village", "THE AVERAGE ALREADY GUARDED",
     "{out} = sum({expr} for {var} in {seq} if {test}) / max({one}, "
     "len([{var} for {var} in {seq} if {test}]))",
     holes={"out": (_N, "where the number lands"),
            "expr": (_X, "what each one contributes"),
            "var": (_B, "the name you give each element"),
            "seq": (_E, "the host you are averaging over"),
            "test": (_X, "which of them count"),
            "one": (_L, "the floor on the divisor, so the empty case cannot raise")},
     note="A mean over a filtered host, with the division by zero already "
          "answered. The guard is part of the claim, not a line after it.",
     mode=SINGLE, demo={"avg": "None", "nums": _NUMS8},
     example={"out": "avg", "expr": "n", "var": "n", "seq": "nums",
              "test": "n > 2", "one": "1"},
     lands="out",
     proves="sum({expr} for {var} in {seq} if {test}) / max({one}, "
            "len([{var} for {var} in {seq} if {test}]))",
     requires=("list",)),

_art("berserker", "village", "NOTHING LEAVES THE FIELD",
     "{out} = [{expr} for {var} in {seq} if {test}] + "
     "[{var} for {var} in {seq} if not ({test})]",
     holes={"out": (_N, "where the host lands when you are done with it"),
            "expr": (_X, "what the ones you pick on become"),
            "var": (_B, "the name you give each element"),
            "seq": (_E, "the host you are going through"),
            "test": (_X, "which of them you pick on")},
     note="Rewrite the ones that answer to you, keep the ones that do not, and "
          "come out holding the same number you walked in with.",
     mode=SWEEP, demo={"out": "[]", "nums": _NUMS8},
     example={"out": "out", "expr": "n * n", "var": "n", "seq": "nums",
              "test": "n % 2 == 0"},
     lands="out",
     proves="[{expr} for {var} in {seq} if {test}] + "
            "[{var} for {var} in {seq} if not ({test})]",
     requires=("list",)),

_art("archivist", "village", "THE TALLY WITH NO COUNTER",
     "{book} = dict((({var}), {seq}.count({var})) for {var} in set({seq}) "
     "if {test})",
     holes={"book": (_N, "where the tally lands"),
            "var": (_B, "the name you give each distinct thing"),
            "seq": (_E, "the host being counted"),
            "test": (_X, "which of them are worth a line in the ledger")},
     note="Every distinct thing and how many of it, filed in one line, with no "
          "import and no second pass you have to remember to write.",
     mode=CHAIN, demo={"book": "{}", "nums": "[3, 1, 4, 1, 5, 3]"},
     example={"book": "book", "var": "n", "seq": "nums", "test": "n > 1"},
     lands="book",
     proves="dict((({var}), {seq}.count({var})) for {var} in set({seq}) "
            "if {test})",
     requires=("list",)),

_art("warden", "village", "THE STEP TESTED BEFORE IT IS TAKEN",
     "{ok} = {low} <= len({seq}) <= {high} and all({test} for {var} in {seq}) "
     "and {seq}[{zero}] in {seq}",
     holes={"ok": (_N, "where the verdict lands"),
            "low": (_L, "the shortest it may be"),
            "seq": (_E, "the host you are standing in front of"),
            "high": (_L, "the longest it may be"),
            "test": (_X, "what must be true of every one of them"),
            "var": (_B, "the name you give each element while you check it"),
            "zero": (_L, "the index you are prepared to read")},
     note="Length between two walls, every element sound, and the index you "
          "are about to use proved to exist. Said before anything is touched.",
     mode=SPLIT, demo={"ok": "None", "nums": _NUMS5},
     example={"ok": "ok", "low": "1", "seq": "nums", "high": "99",
              "test": "n >= 0", "var": "n", "zero": "0"},
     lands="ok",
     proves="{low} <= len({seq}) <= {high} and all({test} for {var} in {seq}) "
            "and {seq}[{zero}] in {seq}",
     requires=("list",)),

_art("artificer", "village", "THE KEY CUT TO FIT",
     "{out} = sorted({seq}, key=lambda {var}: ({expr}, {alt}))[:{k}]",
     holes={"out": (_N, "where the short list lands"),
            "seq": (_E, "the host being ordered"),
            "var": (_B, "the name the key gives each element"),
            "expr": (_X, "what you are ordering by"),
            "alt": (_X, "what breaks a tie"),
            "k": (_L, "how many of the front of it you keep")},
     note="One tool, built in the line that uses it. A tuple key orders by the "
          "first thing and settles ties with the second.",
     mode=TOOL, demo={"top": "[]", "nums": _NUMS8},
     example={"out": "top", "seq": "nums", "var": "v", "expr": "-v",
              "alt": "v", "k": "3"},
     lands="out",
     proves="sorted({seq}, key=lambda {var}: ({expr}, {alt}))[:{k}]",
     requires=("list",)),

_art("seer", "village", "THE FIRST PLACE IT IS TRUE",
     "{at} = ([{i} for {i}, {var} in enumerate({seq}) if {test}] + [{miss}])"
     "[{zero}]",
     holes={"at": (_N, "where the position lands"),
            "i": (_B, "the name you give the position"),
            "var": (_B, "the name you give the thing at it"),
            "seq": (_E, "the host being read"),
            "test": (_X, "what you are looking for"),
            "miss": (_L, "where you stand if it is never true"),
            "zero": (_L, "which of the answers is the first one")},
     note="The first index that answers, and the answer for when none of them "
          "does, decided in the same breath as the search.",
     mode=MARK, demo={"hit": "None", "nums": _NUMS8},
     example={"at": "hit", "i": "i", "var": "v", "seq": "nums",
              "test": "v > 4", "miss": "-1", "zero": "0"},
     lands="at",
     proves="([{i} for {i}, {var} in enumerate({seq}) if {test}] + [{miss}])"
            "[{zero}]",
     requires=("list",)),


# ===========================================================================
# II. THE UNMOWN ACRE — Fields of Syntax
# ===========================================================================
# The six first arts. Each one is a single line that does what three ordinary
# lines of this chapter do, which is the entire reason it hits for three times
# as much.

_art("analyst", "syntax", "THE STATED PROPERTY",
     "{claim} = all({test} for {var} in {seq}) and any({some} for {var} in {seq}) "
     "and len({seq}) > {floor}",
     holes={"claim": (_N, "where the verdict lands"),
            "test": (_X, "the property you are claiming of every element"),
            "var": (_B, "the name you give each element while you check it"),
            "seq": (_E, "the sequence you are claiming it of"),
            "some": (_X, "the property you are claiming of at least one"),
            "floor": (_L, "the length it must beat to be worth claiming")},
     note="Every, at least one, and the whole. Three claims in one breath, and "
          "`all` on an empty sequence is True, which is why the third is there.",
     mode=SINGLE, demo={"ok": "None", "nums": _NUMS8},
     example={"claim": "ok", "test": "n > 0", "var": "n", "seq": "nums",
              "some": "n % 2 == 0", "floor": "0"},
     lands="claim",
     proves="all({test} for {var} in {seq}) and any({some} for {var} in {seq}) "
            "and len({seq}) > ({floor})",
     requires=("list",)),

_art("berserker", "syntax", "SUNDER THE HOST",
     "{out} = [{expr} if {test} else {var} for {var} in {seq} if {keep}]",
     holes={"out": (_N, "where the wreckage lands"),
            "expr": (_X, "what the ones you pick on become"),
            "test": (_X, "which of the survivors get it worse"),
            "var": (_B, "the name you give each element"),
            "seq": (_E, "the host you are going through"),
            "keep": (_X, "which ones you bother with at all")},
     note="Filter, then branch, then transform — one pass, one line. The if "
          "before the for chooses; the if after it filters.",
     mode=SWEEP, demo={"out": "[]", "nums": _NUMS8},
     example={"out": "out", "expr": "n * n", "test": "n % 2", "var": "n",
              "seq": "nums", "keep": "n > 1"},
     lands="out", proves="[{expr} if {test} else {var} for {var} in {seq} if {keep}]",
     requires=("list",)),

_art("archivist", "syntax", "THE LEDGER OF WHAT THEY BECAME",
     "{book} = dict((({var}), {expr}) for {var} in {seq} if {test})",
     holes={"book": (_N, "where the ledger lands"),
            "var": (_B, "the name you give each element"),
            "expr": (_X, "what each one is filed AS"),
            "seq": (_E, "what is being filed"),
            "test": (_X, "which of them are worth filing")},
     note="A dict is built from pairs. Generate the pairs and hand them over; "
          "do not write the loop.",
     mode=CHAIN, demo={"book": "{}", "nums": _NUMS8},
     example={"book": "book", "var": "n", "expr": "n * 2 + len(nums)", "seq": "nums",
              "test": "n > 1"},
     lands="book", proves="dict((({var}), {expr}) for {var} in {seq} if {test})",
     requires=("list",)),

_art("warden", "syntax", "THE FIRST WARD",
     "{ok} = 0 <= {i} < len({seq}) and {seq}[{i}] != {bad} "
     "and all({proof} for {var} in {seq}[:{i}])",
     holes={"proof": (_X, "what must be true of everything behind you"),
            "ok": (_N, "where the ward's answer lands"),
            "i": (_N, "the index you are about to trust"),
            "seq": (_E, "the sequence it indexes"),
            "bad": (_L, "the value that means nothing is there"),
            "var": (_B, "the name you give each element behind you")},
     note="Bounds first, contents second, everything you already walked past "
          "third. In that order, or the second one raises.",
     mode=SPLIT, demo={"ok": "None", "nums": _NUMS8, "k": "2"},
     example={"proof": "n is not None and n != nums[-1]",
              "ok": "ok", "i": "k", "seq": "nums", "bad": "None", "var": "n"},
     lands="ok",
     proves="0 <= {i} < len({seq}) and {seq}[{i}] != {bad} "
            "and all({proof} for {var} in {seq}[:{i}])",
     requires=("list",)),

_art("artificer", "syntax", "THE ORDERING ENGINE",
     "{out} = sorted({seq}, key=lambda {arg}: {key})[:{k}]",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the shortlist lands"),
            "seq": (_E, "what is being ordered"),
            "arg": (_B, "the name the key function gives its argument"),
            "k": (_L, "how many of them you keep")},
     note="A key function is a tool: build it once, break the ties on purpose, "
          "and take only the top of what comes back.",
     mode=TOOL, demo={"out": "[]", "nums": _NUMS8},
     example={"key": "(-n, nums.index(n))",
              "out": "out", "seq": "nums", "arg": "n", "k": "3"},
     lands="out",
     proves="sorted({seq}, key=lambda {arg}: {key})[:{k}]",
     requires=("list",)),

_art("seer", "syntax", "THE FIRST THAT BREAKS IT",
     "{at} = min({idx} for {idx}, {var} in enumerate({seq}) if {test})",
     holes={"at": (_N, "where the position lands"),
            "idx": (_B, "the name you give the position"),
            "var": (_B, "the name you give the element"),
            "seq": (_E, "the sequence you are reading"),
            "test": (_X, "what makes a position interesting")},
     note="The earliest index that satisfies it. If nothing does, min() says so "
          "loudly.",
     mode=MARK, demo={"hit": "0", "nums": _NUMS8},
     example={"at": "hit", "idx": "i", "var": "n", "seq": "nums",
              "test": "n > 4 and n < nums[0] * 3"},
     lands="at", proves="min({idx} for {idx}, {var} in enumerate({seq}) if {test})",
     requires=("list",),
     miss="It found the same position it already held. Nothing moved."),


# ===========================================================================
# III. THE VAULT WITH NO RUNE — Hashmap Highlands
# ===========================================================================

_art("analyst", "highlands", "THE TALLY DECLARED",
     "{claim} = sum({book}.values()) == len({seq}) and set({book}) == set({seq}) "
     "and all({proof} for {k} in {book})",
     holes={"proof": (_X, "the claim you are making about every entry"),
            "claim": (_N, "where the verdict lands"),
            "book": (_E, "the tally you are auditing"),
            "seq": (_N, "what it claims to have counted"),
            "k": (_B, "the name you give each key while you check it"),
            "floor": (_L, "the count no key may sit at or below")},
     note="A count table is right when its total, its keys and every one of its "
          "values agree with the input. Check all three.",
     mode=SINGLE, demo={"ok": "None", "tally": "{'a': 2, 'b': 1}",
                        "said": "['a', 'a', 'b']"},
     example={"proof": "tally[w] > 0 and w in said",
              "claim": "ok", "book": "tally", "seq": "said", "k": "w",
              "floor": "0"},
     lands="claim",
     proves="sum({book}.values()) == len({seq}) and set({book}) == set({seq}) "
            "and all({proof} for {k} in {book})",
     requires=("dict",)),

_art("berserker", "highlands", "SUNDER THE TALLY",
     "{out} = dict({pair} for {pair} in {book}.items() if {proof})",
     holes={"proof": (_X, "what earns a key its place"),
            "out": (_N, "where what survives lands"),
            "pair": (_B, "the name you give each key-and-count"),
            "book": (_E, "the tally being cut down"),
            "floor": (_L, "the count a key has to beat to live")},
     note="Rebuild the dict keeping only what earns its place. One pass, one line.",
     mode=SWEEP, demo={"out": "{}", "counts": "{'a': 2, 'b': 3, 'c': 1}"},
     example={"proof": "kv[1] > 1 and kv[0] != 'c'",
              "out": "out", "pair": "kv", "book": "counts", "floor": "1"},
     lands="out",
     proves="dict({pair} for {pair} in {book}.items() if {proof})",
     requires=("dict",)),

_art("archivist", "highlands", "THE INDEX THAT KEEPS ITS ORDER",
     "{book}[{key}] = sorted({var} for {var} in set({book}.get({key}, []) "
     "+ [{item}]) if {test})",
     holes={"book": (_E, "the archive being written to"),
            "key": (_X, "the bucket this belongs in"),
            "var": (_B, "the name you give each thing already in it"),
            "item": (_X, "what goes in the bucket"),
            "test": (_X, "what is worth keeping once it is in there")},
     note="Group into a dict of lists without ever asking whether the key "
          "exists, and without filing the same thing twice.",
     mode=CHAIN, demo={"groups": "{'a': ['sha']}", "ch": "'a'", "word": "'ash'"},
     example={"book": "groups", "key": "ch", "var": "p", "item": "word",
              "test": "p and len(p) > 1"},
     snapshot={"prev": "{book}.get({key}, [])"},
     assertion="{book}[{key}] == sorted(x for x in set(__b__['prev'] + [{item}]) "
               "if x) and len({book}[{key}]) > len(__b__['prev'])",
     requires=("dict",),
     miss="The bucket is the size it was. Nothing was filed."),

_art("warden", "highlands", "THE WARD ON THE KEY",
     "{ok} = {key} in {book} and isinstance({book}[{key}], int) "
     "and {book}[{key}] > {floor} and all({proof} for {v} in {book}.values())",
     holes={"proof": (_X, "the claim about every other value"),
            "ok": (_N, "where the ward's answer lands"),
            "key": (_N, "the key you are about to read"),
            "book": (_E, "the dict you are about to read it from"),
            "floor": (_L, "the value it has to beat"),
            "v": (_B, "the name you give every other value while you check it")},
     note="Presence, then type, then value, then the same claim about the whole "
          "table. Reading a missing key raises; asking in this order does not.",
     mode=SPLIT, demo={"ok": "None", "counts": "{'a': 2}", "ch": "'a'"},
     example={"proof": "n >= 1 and n <= counts[ch]",
              "ok": "ok", "key": "ch", "book": "counts", "floor": "1",
              "v": "n"},
     lands="ok",
     proves="{key} in {book} and isinstance({book}[{key}], int) "
            "and {book}[{key}] > ({floor}) "
            "and all({proof} for {v} in {book}.values())",
     requires=("dict",)),

_art("artificer", "highlands", "THE RANKING ENGINE",
     "{out} = sorted({book}.items(), key=lambda {pair}: {key})",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the ranking lands"),
            "book": (_E, "the tally being ranked"),
            "pair": (_B, "the name the key function gives each entry")},
     note="Most first, ties broken by name. A tuple key sorts on two things at "
          "once.",
     mode=TOOL, demo={"out": "[]", "counts": "{'a': 2, 'b': 3}"},
     example={"key": "(-kv[1], kv[0])",
              "out": "out", "book": "counts", "pair": "kv"},
     lands="out",
     proves="sorted({book}.items(), key=lambda {pair}: {key})",
     requires=("dict",)),

_art("seer", "highlands", "THE HEAVIEST NAME",
     "{worst} = max(({k} for {k} in {book} if {test}), "
     "key=lambda {k}: ({book}[{k}], {k}))",
     holes={"worst": (_N, "where the name lands"),
            "k": (_B, "the name you give each key"),
            "book": (_E, "the tally you are reading"),
            "test": (_X, "which keys are even in the running")},
     note="Narrow first, then take the largest of what is left. Two different "
          "jobs, and the lambda only does the second one.",
     mode=MARK, demo={"top": "None", "counts": "{'a': 2, 'b': 3}"},
     example={"worst": "top", "k": "w", "book": "counts",
              "test": "counts[w] > 0"},
     lands="worst",
     proves="max(({k} for {k} in {book} if {test}), "
            "key=lambda {k}: ({book}[{k}], {k}))",
     requires=("dict",)),


# ===========================================================================
# IV. THE CLEARING THAT SPELLS NOTHING — Stringwood Labyrinth
# ===========================================================================

_art("analyst", "stringwood", "THE LENGTH ACCOUNTED FOR",
     "{claim} = len({text}) == sum(len({var}) for {var} in {parts}) "
     "+ len({parts}) - {one} and all({proof} for {var} in {parts})",
     holes={"proof": (_X, "what must be true of every piece"),
            "claim": (_N, "where the verdict lands"),
            "text": (_E, "the utterance being accounted for"),
            "var": (_B, "the name you give each piece"),
            "parts": (_N, "the pieces it was cut into"),
            "one": (_L, "the separator you do not get back at the end")},
     note="Pieces plus separators equals the whole. The minus one is the joint "
          "that is not there.",
     mode=SINGLE, demo={"ok": "None", "text": "'the rain it raineth'",
                        "parts": "['the', 'rain', 'it', 'raineth']"},
     example={"proof": "w in text and len(w) > 1",
              "claim": "ok", "text": "text", "var": "w", "parts": "parts",
              "one": "1"},
     lands="claim",
     proves="len({text}) == sum(len({var}) for {var} in {parts}) "
            "+ len({parts}) - ({one}) and all({proof} for {var} in {parts})",
     requires=("str",)),

_art("berserker", "stringwood", "SUNDER THE UTTERANCE",
     "{out} = [{var}[::-1] for {var} in {text}.split({sep}) if {proof}]",
     holes={"proof": (_X, "what makes a piece worth keeping"),
            "out": (_N, "where the pieces land"),
            "var": (_B, "the name you give each word"),
            "text": (_E, "the utterance being torn up"),
            "sep": (_L, "what it comes apart on"),
            "floor": (_L, "the length a piece has to beat to be kept")},
     note="Split, filter and reverse in one pass. The empty step in a slice is "
          "the direction.",
     mode=SWEEP, demo={"out": "[]", "text": "'the rain it raineth'"},
     example={"proof": "len(w) > 2 and w[0] != 'i'",
              "out": "out", "var": "w", "text": "text", "sep": "' '",
              "floor": "2"},
     lands="out",
     proves="[{var}[::-1] for {var} in {text}.split({sep}) if {proof}]",
     requires=("str",)),

_art("archivist", "stringwood", "THE INDEX OF ANAGRAMS",
     "{book} = dict(zip({parts}, [{value} for {var} in {parts}]))",
     holes={"value": (_X, "what each word is filed under"),
            "book": (_N, "where the index lands"),
            "parts": (_E, "the words being filed"),
            "var": (_B, "the name you give each word")},
     note="Two words are the same word rearranged when their sorted letters "
          "match. That is the whole trick.",
     mode=CHAIN, demo={"index": "{}", "parts": "['ash', 'sha', 'cat']"},
     example={"value": "''.join(sorted(w)) + str(len(w))",
              "book": "index", "parts": "parts", "var": "w"},
     lands="book",
     proves="dict(zip({parts}, [{value} for {var} in {parts}]))",
     requires=("list",)),

_art("warden", "stringwood", "THE WARD OF BOTH ENDS",
     "{ok} = {n} <= len({text}) and {text}[:{n}] == {text}[-{n}:][::-1] "
     "and all({proof} for {i} in range({n}))",
     holes={"proof": (_X, "the character-by-character claim"),
            "ok": (_N, "where the ward's answer lands"),
            "n": (_N, "how many characters from each end"),
            "text": (_E, "the utterance being checked"),
            "i": (_B, "the name you give each offset from the front"),
            "one": (_L, "what turns an offset from the front into one from the back")},
     note="Compare the head with the reversed tail, then say the same thing "
          "character by character. Check the length first or the slices lie.",
     mode=SPLIT, demo={"ok": "None", "text": "'abcba'", "n": "2"},
     example={"proof": "text[i] == text[-i - 1]",
              "ok": "ok", "n": "n", "text": "text", "i": "i", "one": "1"},
     lands="ok",
     proves="{n} <= len({text}) and {text}[:{n}] == {text}[-{n}:][::-1] "
            "and all({proof} for {i} in range({n}))",
     requires=("str",)),

_art("artificer", "stringwood", "THE SHORTEST-FIRST ENGINE",
     "{out} = sorted(({w} for {w} in {parts} if {test}), "
     "key=lambda {w}: {key})[:{k}]",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the shortlist lands"),
            "w": (_B, "the name you give each word"),
            "parts": (_E, "the words being ordered"),
            "test": (_X, "which words are worth ordering"),
            "k": (_L, "how many you keep")},
     note="Length first, then alphabetical, case folded so the ordering is about "
          "the word rather than the shouting — and only the front of it.",
     mode=TOOL, demo={"out": "[]", "parts": "['Rain', 'it', 'the']"},
     example={"key": "(len(p), p.lower())",
              "out": "out", "w": "p", "parts": "parts", "test": "p", "k": "2"},
     lands="out",
     proves="sorted(({w} for {w} in {parts} if {test}), "
            "key=lambda {w}: {key})[:{k}]",
     requires=("list",)),

_art("seer", "stringwood", "THE LAST VOWEL",
     "{at} = max({idx} for {idx}, {ch} in enumerate({text}) if {proof})",
     holes={"proof": (_X, "what makes a character worth marking"),
            "at": (_N, "where the position lands"),
            "idx": (_B, "the name you give the position"),
            "ch": (_B, "the name you give the character"),
            "text": (_E, "the utterance being read"),
            "vowels": (_L, "the characters that count")},
     note="enumerate over a string walks characters with their positions. "
          "Membership in a string is membership in its characters.",
     mode=MARK, demo={"hit": "0", "text": "'the rain'"},
     example={"proof": "c in 'aeiou' and c != 't'",
              "at": "hit", "idx": "i", "ch": "c", "text": "text",
              "vowels": "'aeiou'"},
     lands="at",
     proves="max({idx} for {idx}, {ch} in enumerate({text}) if {proof})",
     requires=("str",)),


# ===========================================================================
# V. ALCOVE MINUS ONE — Array Caverns
# ===========================================================================

_art("analyst", "caverns", "THE ORDER DECLARED",
     "{claim} = {seq} == sorted({seq}) and len(set({seq})) == len({seq}) "
     "and all({seq}[{i}] < {seq}[{i} + {one}] for {i} in range(len({seq}) - {one}))",
     holes={"claim": (_N, "where the verdict lands"),
            "seq": (_E, "the sequence being declared about"),
            "i": (_B, "the name you give each position"),
            "one": (_L, "the step to the next one")},
     note="Sorted, distinct, and strictly increasing are three claims, not one. "
          "Most bugs live in the gaps between them.",
     mode=SINGLE, demo={"ok": "None", "nums": "[1, 2, 3]"},
     example={"claim": "ok", "seq": "nums", "i": "i", "one": "1"},
     lands="claim",
     proves="{seq} == sorted({seq}) and len(set({seq})) == len({seq}) "
            "and all({seq}[{i}] < {seq}[{i} + ({one})] "
            "for {i} in range(len({seq}) - ({one})))",
     requires=("list",)),

_art("berserker", "caverns", "SUNDER THE ALCOVES",
     "{out} = [{seq}[{i}] + {seq}[{i} - {one}] for {i} in range({one}, len({seq})) "
     "if {test}]",
     holes={"out": (_N, "where the results land"),
            "seq": (_E, "the indexed host"),
            "i": (_B, "the name you give the position"),
            "one": (_L, "the step back to the previous alcove"),
            "test": (_X, "which positions you bother with")},
     note="Every element and the one before it, in one pass. Start at one or the "
          "first step walks off the front.",
     mode=SWEEP, demo={"out": "[]", "nums": _NUMS5},
     example={"out": "out", "seq": "nums", "i": "i", "one": "1",
              "test": "i % 2 == 1"},
     lands="out",
     proves="[{seq}[{i}] + {seq}[{i} - ({one})] "
            "for {i} in range({one}, len({seq})) if {test}]",
     requires=("list",)),

_art("archivist", "caverns", "THE INDEX OF WHAT CAME BEFORE",
     "{book} = dict(zip({seq}, [{value} for {i} in range(len({seq}))]))",
     holes={"value": (_X, "what each element is filed against"),
            "book": (_N, "where the index lands"),
            "seq": (_E, "the host being filed"),
            "i": (_B, "the name you give the position"),
            "one": (_L, "the step back")},
     note="Index minus one at position zero is the last element. Python wraps; "
          "know that you are using it.",
     mode=CHAIN, demo={"book": "{}", "nums": _NUMS5},
     example={"value": "nums[i - 1] + nums[i]",
              "book": "book", "seq": "nums", "i": "i", "one": "1"},
     lands="book",
     proves="dict(zip({seq}, [{value} for {i} in range(len({seq}))]))",
     requires=("list",)),

_art("warden", "caverns", "THE WARD ON THE RANGE",
     "{ok} = 0 <= {lo} <= {hi} < len({seq}) and all({proof} "
     "for {i} in range({lo}, {hi}))",
     holes={"proof": (_X, "what neighbouring positions owe each other"),
            "ok": (_N, "where the ward's answer lands"),
            "lo": (_N, "the first index of the stretch"),
            "hi": (_N, "the last index of the stretch"),
            "seq": (_E, "the host the stretch is in"),
            "i": (_B, "the name you give each position inside it"),
            "one": (_L, "the step to the next one")},
     note="A chained comparison is one claim about three things. Then prove the "
          "stretch itself is in order.",
     mode=SPLIT, demo={"ok": "None", "nums": _SORTED4, "lo": "0", "hi": "2"},
     example={"proof": "nums[i] <= nums[i + 1]",
              "ok": "ok", "lo": "lo", "hi": "hi", "seq": "nums", "i": "i",
              "one": "1"},
     lands="ok",
     proves="0 <= {lo} <= {hi} < len({seq}) and all({proof} "
            "for {i} in range({lo}, {hi}))",
     requires=("list",)),

_art("artificer", "caverns", "THE POSITION ENGINE",
     "{out} = sorted(range(len({seq})), key=lambda {i}: {key})",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the ordered positions land"),
            "seq": (_E, "the host being read"),
            "i": (_B, "the name the key function gives each position")},
     note="Sort the positions, not the values. You keep the addresses, which is "
          "what you actually needed.",
     mode=TOOL, demo={"out": "[]", "nums": _NUMS5},
     example={"key": "(nums[i], -i, nums[i] % 2)",
              "out": "out", "seq": "nums", "i": "i"},
     lands="out",
     proves="sorted(range(len({seq})), key=lambda {i}: {key})",
     requires=("list",)),

_art("seer", "caverns", "THE FIRST HIGH-WATER MARK",
     "{at} = min({i} for {i} in range(len({seq})) if {proof})",
     holes={"proof": (_X, "what makes a position the one you want"),
            "at": (_N, "where the position lands"),
            "i": (_B, "the name you give the position"),
            "seq": (_E, "the host being read")},
     note="Not the largest value — the earliest place it happens. Those are "
          "different questions and timed practicals ask the second one.",
     mode=MARK, demo={"hit": "0", "nums": _NUMS5},
     example={"proof": "nums[i] == max(nums)",
              "at": "hit", "i": "i", "seq": "nums"},
     lands="at", proves="min({i} for {i} in range(len({seq})) if {proof})",
     requires=("list",)),


# ===========================================================================
# VI. THE STANDING FRAME — Sliding Window Marsh
# ===========================================================================

_art("analyst", "marsh", "THE FRAME ACCOUNTED FOR",
     "{claim} = {hi} - {lo} + {one} == len({win}) and sum({win}) <= {cap} "
     "and all({proof} for {v} in {win})",
     holes={"proof": (_X, "what must be true of everything inside the frame"),
            "claim": (_N, "where the verdict lands"),
            "hi": (_N, "the right edge"),
            "lo": (_N, "the left edge"),
            "one": (_L, "what makes two edges into a width"),
            "win": (_E, "the frame itself"),
            "cap": (_N, "the budget the frame may not exceed"),
            "v": (_B, "the name you give each thing inside it")},
     note="Width, budget and contents. A window bug is almost always the first "
          "of those three.",
     mode=SINGLE, demo={"ok": "None", "lo": "0", "hi": "2", "win": "[1, 2, 3]",
                        "cap": "10"},
     example={"proof": "n >= 0 and n <= cap",
              "claim": "ok", "hi": "hi", "lo": "lo", "one": "1", "win": "win",
              "cap": "cap", "v": "n"},
     lands="claim",
     proves="{hi} - {lo} + ({one}) == len({win}) and sum({win}) <= {cap} "
            "and all({proof} for {v} in {win})",
     requires=("list",)),

_art("berserker", "marsh", "SUNDER EVERY FRAME AT ONCE",
     "{out} = [{expr} for {i} in range(len({seq}) - {k} + {one})]",
     holes={"expr": (_X, "what each frame is worth"),
            "out": (_N, "where every window's weight lands"),
            "seq": (_E, "the ground the frame slides over"),
            "i": (_B, "the name you give each left edge"),
            "k": (_N, "how wide the frame is"),
            "one": (_L, "the fencepost")},
     note="Every window in one line. The plus one is the fencepost, and it is "
          "the only part anybody ever gets wrong.",
     mode=SWEEP, demo={"out": "[]", "nums": _NUMS5, "k": "3"},
     example={"expr": "sum(nums[i:i + k]) - min(nums[i:i + k])",
              "out": "out", "seq": "nums", "i": "i", "k": "k", "one": "1"},
     lands="out",
     proves="[{expr} for {i} in range(len({seq}) - {k} + ({one}))]",
     requires=("list",)),

_art("archivist", "marsh", "THE INDEX OF EVERY FRAME",
     "{book} = dict(zip(range(len({seq})), "
     "[{value} for {i} in range(len({seq}))]))",
     holes={"value": (_X, "what you file about the frame at that edge"),
            "book": (_N, "where the index lands"),
            "seq": (_E, "the ground being filed"),
            "i": (_B, "the name you give each left edge"),
            "k": (_N, "how wide the frame is")},
     note="Left edge to the best thing visible from it. A slice past the end is "
          "short, not an error.",
     mode=CHAIN, demo={"book": "{}", "nums": _NUMS5, "k": "3"},
     example={"value": "max(nums[i:i + k]) - min(nums[i:i + k])",
              "book": "book", "seq": "nums", "i": "i", "k": "k"},
     lands="book",
     proves="dict(zip(range(len({seq})), "
            "[{value} for {i} in range(len({seq}))]))",
     requires=("list",)),

_art("warden", "marsh", "THE WARD ON THE FRAME",
     "{ok} = 0 <= {lo} <= {hi} <= len({seq}) and sum({seq}[{lo}:{hi}]) <= {cap} "
     "and all({proof} for {v} in {seq}[{lo}:{hi}])",
     holes={"proof": (_X, "the claim about each thing inside the frame"),
            "ok": (_N, "where the ward's answer lands"),
            "lo": (_N, "the left edge"),
            "hi": (_N, "the right edge"),
            "seq": (_E, "the ground the frame is on"),
            "cap": (_N, "the budget"),
            "v": (_B, "the name you give each thing inside the frame")},
     note="The right edge may sit at len; the left may not sit past it. That "
          "asymmetry is the whole of slice safety.",
     mode=SPLIT, demo={"ok": "None", "nums": _NUMS5, "lo": "0", "hi": "3",
                       "cap": "10"},
     example={"proof": "n <= cap and n >= 0",
              "ok": "ok", "lo": "lo", "hi": "hi", "seq": "nums", "cap": "cap",
              "v": "n"},
     lands="ok",
     proves="0 <= {lo} <= {hi} <= len({seq}) and sum({seq}[{lo}:{hi}]) <= {cap} "
            "and all({proof} for {v} in {seq}[{lo}:{hi}])",
     requires=("list",)),

_art("artificer", "marsh", "THE HEAVIEST-FRAME ENGINE",
     "{out} = sorted(range(len({seq}) - {k} + {one}), "
     "key=lambda {i}: {key})",
     holes={"key": (_X, "what each left edge sorts by"),
            "out": (_N, "where the ordered left edges land"),
            "seq": (_E, "the ground being read"),
            "k": (_N, "how wide the frame is"),
            "one": (_L, "the fencepost"),
            "i": (_B, "the name the key function gives each left edge")},
     note="Order the positions by what you would see from them. Negating the "
          "key is how you sort downward without reversing twice.",
     mode=TOOL, demo={"out": "[]", "nums": _NUMS5, "k": "3"},
     example={"key": "-sum(nums[i:i + k])",
              "out": "out", "seq": "nums", "k": "k", "one": "1", "i": "i"},
     lands="out",
     proves="sorted(range(len({seq}) - {k} + ({one})), "
            "key=lambda {i}: {key})",
     requires=("list",)),

_art("seer", "marsh", "THE FIRST FRAME THAT PAYS",
     "{at} = min({i} for {i} in range(len({seq}) - {k} + {one}) "
     "if {proof})",
     holes={"proof": (_X, "what makes a frame worth stopping at"),
            "at": (_N, "where the left edge lands"),
            "i": (_B, "the name you give each left edge"),
            "seq": (_E, "the ground being read"),
            "k": (_N, "how wide the frame is"),
            "one": (_L, "the fencepost"),
            "goal": (_N, "what the frame has to be worth")},
     note="The earliest window that clears the bar. Not the best one — the first.",
     mode=MARK, demo={"hit": "0", "nums": _NUMS5, "k": "3", "goal": "9"},
     example={"proof": "sum(nums[i:i + k]) >= goal",
              "at": "hit", "i": "i", "seq": "nums", "k": "k", "one": "1",
              "goal": "goal"},
     lands="at",
     proves="min({i} for {i} in range(len({seq}) - {k} + ({one})) "
            "if {proof})",
     requires=("list",)),


# ===========================================================================
# VII. THE THIRD LANTERN — Twin Pointer Pass
# ===========================================================================

_art("analyst", "pass", "THE MEETING DECLARED",
     "{claim} = {lo} < {hi} and {seq} == sorted({seq}) "
     "and {proof} and len(set({seq})) == len({seq})",
     holes={"proof": (_X, "the claim about the pair"),
            "claim": (_N, "where the verdict lands"),
            "lo": (_N, "the near lantern"),
            "hi": (_N, "the far lantern"),
            "seq": (_E, "the bridge they are crossing"),
            "goal": (_N, "what the pair has to come to")},
     note="Two pointers are only meaningful on sorted ground. Say so before you "
          "trust the sum.",
     mode=SINGLE, demo={"ok": "None", "nums": _SORTED4, "lo": "0", "hi": "3",
                        "goal": "5"},
     example={"proof": "nums[lo] + nums[hi] == goal",
              "claim": "ok", "lo": "lo", "hi": "hi", "seq": "nums",
              "goal": "goal"},
     lands="claim",
     proves="{lo} < {hi} and {seq} == sorted({seq}) "
            "and {proof} and len(set({seq})) == len({seq})",
     requires=("list",)),

_art("berserker", "pass", "SUNDER FROM BOTH ENDS",
     "{out} = [({seq}[{i}], {seq}[-{i} - {one}]) "
     "for {i} in range(len({seq}) // {two}) if {test}]",
     holes={"out": (_N, "where the pairs land"),
            "seq": (_E, "the host being folded"),
            "i": (_B, "the name you give the offset from the front"),
            "one": (_L, "what turns a front offset into a back one"),
            "two": (_L, "how many ends there are"),
            "test": (_X, "which pairs are worth keeping")},
     note="Fold the sequence onto itself. Negative indices count from the back, "
          "and minus one is where the back starts.",
     mode=SWEEP, demo={"out": "[]", "nums": _SORTED4},
     example={"out": "out", "seq": "nums", "i": "i", "one": "1", "two": "2",
              "test": "nums[i] != nums[-i - 1]"},
     lands="out",
     proves="[({seq}[{i}], {seq}[-{i} - ({one})]) "
            "for {i} in range(len({seq}) // ({two})) if {test}]",
     requires=("list",)),

_art("archivist", "pass", "THE INDEX OF WHAT IS MISSING",
     "{book} = dict((({var}), {value}) for {var} in {seq} if {test})",
     holes={"value": (_X, "what this element still needs"),
            "book": (_N, "where the index lands"),
            "var": (_B, "the name you give each element"),
            "seq": (_E, "the host being filed"),
            "test": (_X, "which elements could still be half of a pair")},
     note="File what each element still needs, and only for the ones that could "
          "still be paid. Then the second pass is a lookup rather than a search.",
     mode=CHAIN, demo={"book": "{}", "nums": _SORTED4, "goal": "5"},
     example={"value": "goal - n if n <= goal else 0",
              "book": "book", "var": "n", "seq": "nums",
              "test": "n <= goal"},
     lands="book",
     proves="dict((({var}), {value}) for {var} in {seq} if {test})",
     requires=("list",)),

_art("warden", "pass", "THE WARD BETWEEN THE LANTERNS",
     "{ok} = 0 <= {lo} < {hi} < len({seq}) "
     "and not any({proof} for {i} in range({lo}, {hi}))",
     holes={"proof": (_X, "the fault you are looking for"),
            "ok": (_N, "where the ward's answer lands"),
            "lo": (_N, "the near lantern"),
            "hi": (_N, "the far lantern"),
            "seq": (_E, "the bridge"),
            "i": (_B, "the name you give each plank between them"),
            "one": (_L, "the step to the next plank")},
     note="`not any` says what `all` says, and says it in the voice of the bug "
          "you are looking for.",
     mode=SPLIT, demo={"ok": "None", "nums": _SORTED4, "lo": "0", "hi": "2"},
     example={"proof": "nums[i] > nums[i + 1]",
              "ok": "ok", "lo": "lo", "hi": "hi", "seq": "nums", "i": "i",
              "one": "1"},
     lands="ok",
     proves="0 <= {lo} < {hi} < len({seq}) "
            "and not any({proof} for {i} in range({lo}, {hi}))",
     requires=("list",)),

_art("artificer", "pass", "THE CONVERGENCE ENGINE",
     "{out} = sorted(zip({seq}, {seq}[::-1]), "
     "key=lambda {pair}: {key})",
     holes={"key": (_X, "what each pair sorts by"),
            "out": (_N, "where the ordered pairs land"),
            "seq": (_E, "the host being folded"),
            "pair": (_B, "the name the key function gives each pair")},
     note="Zipping a sequence with its own reverse pairs every element with its "
          "opposite number. No indices anywhere.",
     mode=TOOL, demo={"out": "[]", "nums": _SORTED4},
     example={"key": "abs(p[0] - p[1])",
              "out": "out", "seq": "nums", "pair": "p"},
     lands="out",
     proves="sorted(zip({seq}, {seq}[::-1]), "
            "key=lambda {pair}: {key})",
     requires=("list",)),

_art("seer", "pass", "THE LAST THAT STILL FITS",
     "{at} = max({i} for {i} in range(len({seq})) "
     "if {proof})",
     holes={"proof": (_X, "what makes a lantern still affordable"),
            "at": (_N, "where the position lands"),
            "i": (_B, "the name you give each position"),
            "seq": (_E, "the bridge being read"),
            "goal": (_N, "the budget the pair may not exceed")},
     note="The furthest lantern that can still be paid for from the near end. "
          "That is where the far pointer belongs.",
     mode=MARK, demo={"hit": "0", "nums": _SORTED4, "goal": "5"},
     example={"proof": "nums[i] + nums[0] <= goal",
              "at": "hit", "i": "i", "seq": "nums", "goal": "goal"},
     lands="at",
     proves="max({i} for {i} in range(len({seq})) if {proof})",
     requires=("list",)),


# ===========================================================================
# VIII. THE CART THAT WAS NEVER UNLOADED — Stack & Queue Mines
# ===========================================================================

_art("analyst", "mines", "THE TOP ACCOUNTED FOR",
     "{claim} = bool({stack}) and {stack}[-{one}] == {items}[len({stack}) - {one}] "
     "and len({stack}) <= len({items}) and all({proof} for {v} in {stack})",
     holes={"proof": (_X, "what must be true of everything still stacked"),
            "claim": (_N, "where the verdict lands"),
            "stack": (_E, "the tower"),
            "one": (_L, "the step from the length to the last index"),
            "items": (_N, "everything that was ever loaded"),
            "v": (_B, "the name you give each thing still on the tower")},
     note="Minus one is the top. Length minus one is the same place, counted "
          "from the other side, and confusing the two is the classic.",
     mode=SINGLE, demo={"ok": "None", "stack": "[1, 2, 3]",
                        "items": "[1, 2, 3, 4]"},
     example={"proof": "n in items and n > 0",
              "claim": "ok", "stack": "stack", "one": "1", "items": "items",
              "v": "n"},
     lands="claim",
     proves="bool({stack}) and {stack}[-({one})] == {items}[len({stack}) - ({one})] "
            "and len({stack}) <= len({items}) and all({proof} for {v} in {stack})",
     requires=("list",)),

_art("berserker", "mines", "EMPTY THE CAIRN",
     "{out} = sorted([heapq.heappop({heap}) for {i} in range(len({heap}))], "
     "key=lambda {x}: {key})[:{k}]",
     holes={"key": (_X, "what order you want them back in"),
            "x": (_B, "the name the key function gives each thing you pulled out"),
            "out": (_N, "where everything you pulled out lands"),
            "heap": (_E, "the cairn being emptied"),
            "i": (_B, "the name you give each pull"),
            "k": (_L, "how much of it you keep")},
     note="A heap drained in order is a sorted list. range() is measured once, "
          "before the first pop, which is the only reason this works at all.",
     mode=SWEEP, demo={"out": "[]", "heap": "[1, 2, 3]"},
     example={"key": "(-v, v % 2)",
              "x": "v",
              "out": "out", "heap": "heap", "i": "i", "k": "2"},
     snapshot={"before": "{heap}"},
     assertion="{out} == sorted(__b__['before'], key=lambda {x}: {key})[:{k}] and not {heap} "
               "and len(__b__['before']) > 0",
     requires=("heap",), imports=("import heapq",),
     miss="The cairn is exactly as full as it was. Nothing came out."),

_art("archivist", "mines", "THE INDEX OF WHAT KEEPS COMING BACK",
     "{book} = dict(zip(sorted(set({items})), "
     "[{value} for {var} in sorted(set({items}))]))",
     holes={"value": (_X, "what you file about each distinct thing"),
            "book": (_N, "where the index lands"),
            "items": (_E, "the ore being counted"),
            "var": (_B, "the name you give each distinct thing")},
     note="Distinct, ordered, then counted. `.count` inside a loop over the same "
          "list is quadratic, and you should know that you chose it.",
     mode=CHAIN, demo={"book": "{}", "items": "[1, 2, 2, 3]"},
     example={"value": "items.count(n) * n",
              "book": "book", "items": "items", "var": "n"},
     lands="book",
     proves="dict(zip(sorted(set({items})), "
            "[{value} for {var} in sorted(set({items}))]))",
     requires=("list",)),

_art("warden", "mines", "THE WARD ON THE TOP",
     "{ok} = bool({stack}) and {stack}[-{one}] == {pairs}.get({ch}, {stack}[-{one}]) "
     "and all({proof} for {v} in {stack})",
     holes={"proof": (_X, "what must be true of everything on the tower"),
            "ok": (_N, "where the ward's answer lands"),
            "stack": (_E, "the tower"),
            "one": (_L, "the step to the top"),
            "pairs": (_N, "what closes what"),
            "ch": (_N, "the thing arriving"),
            "v": (_B, "the name you give each thing already stacked")},
     note="Ask the empty tower for its top and it raises. Ask whether it is "
          "empty first and it does not.",
     mode=SPLIT, demo={"ok": "None", "stack": "['(']", "pairs": "{')': '('}",
                       "ch": "')'"},
     example={"proof": "c is not None and c in pairs.values()",
              "ok": "ok", "stack": "stack", "one": "1", "pairs": "pairs",
              "ch": "ch", "v": "c"},
     lands="ok",
     proves="bool({stack}) and {stack}[-({one})] == {pairs}.get({ch}, {stack}[-({one})]) "
            "and all({proof} for {v} in {stack})",
     requires=("list",)),

_art("artificer", "mines", "THE FREQUENCY ENGINE",
     "{out} = sorted(({x} for {x} in {items} if {test}), "
     "key=lambda {x}: {key})[:{k}]",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the ordered ore lands"),
            "x": (_B, "the name you give each piece"),
            "items": (_E, "the ore being ordered"),
            "test": (_X, "which pieces are worth carrying"),
            "k": (_L, "how many you carry")},
     note="Commonest first, ties by value, top of the pile only. The key "
          "function scans the list every time it runs; that is the price.",
     mode=TOOL, demo={"out": "[]", "items": "[1, 2, 2, 3]"},
     example={"key": "(-items.count(n), n)",
              "out": "out", "x": "n", "items": "items", "test": "n",
              "k": "3"},
     lands="out",
     proves="sorted(({x} for {x} in {items} if {test}), "
            "key=lambda {x}: {key})[:{k}]",
     requires=("list",)),

_art("seer", "mines", "THE LEAST, IF THERE IS ONE",
     "{top} = heapq.heappop({heap}) if min(({x} for {x} in {heap} if {test}), "
     "default={fallback}) <= {cap} else {fallback}",
     holes={"top": (_N, "where the smallest lands"),
            "heap": (_E, "the cairn"),
            "x": (_B, "the name you give each thing buried in it"),
            "test": (_X, "which of them you are willing to pay for"),
            "fallback": (_L, "what you get instead when nothing qualifies"),
            "cap": (_N, "the most you will pay")},
     note="Look before you take. A conditional expression is a guard you can put "
          "inside another expression, and `default=` is what stops min() raising "
          "on an empty one.",
     mode=MARK, demo={"top": "None", "heap": "[1, 2, 3]", "cap": "9"},
     example={"top": "top", "heap": "heap", "x": "n", "test": "n > 1 and n < cap",
              "fallback": "0", "cap": "cap"},
     snapshot={"least": "min({heap}) if {heap} else ({fallback})",
               "n": "len({heap})"},
     assertion="{top} == __b__['least'] and len({heap}) == max(0, __b__['n'] - 1)",
     requires=("heap",), imports=("import heapq",),
     miss="The cairn is the size it was, so nothing surfaced."),


# ===========================================================================
# IX. THE CLEARING THAT CONTAINS ITSELF — Recursive Forest
# ===========================================================================
# The forest teaches the half of recursion that is not the call: what you keep,
# what you have already paid for, and how to ask without paying twice.

_art("analyst", "forest", "THE PRICE ALREADY PAID",
     "{claim} = {memo}.get({n}, None) == {fn}({n}) and {n} > {floor} "
     "and all({proof} for {k} in {memo})",
     holes={"proof": (_X, "the claim that each filed answer is still the right one"),
            "claim": (_N, "where the verdict lands"),
            "memo": (_E, "the archive of paid answers"),
            "n": (_N, "the question you are asking"),
            "fn": (_N, "the thing that knows the answer"),
            "floor": (_L, "the size below which it is not worth asking"),
            "k": (_B, "the name you give each question already paid for")},
     note="A memo is only a memo while every entry still agrees with the "
          "function. Say that out loud before you trust it.",
     mode=SINGLE, demo={"ok": "None", "memo": "{3: 6}", "n": "3",
                        "step": _STEP},
     example={"proof": "step(q) == memo[q]",
              "claim": "ok", "memo": "memo", "n": "n", "fn": "step",
              "floor": "0", "k": "q"},
     lands="claim",
     proves="{memo}.get({n}, None) == {fn}({n}) and {n} > ({floor}) "
            "and all({proof} for {k} in {memo})",
     requires=("dict",)),

_art("berserker", "forest", "PAY FOR ALL OF IT AT ONCE",
     "{out} = [{fn}({var}) if {var} not in {memo} else {memo}[{var}] "
     "for {var} in {seq} if {test}]",
     holes={"out": (_N, "where the answers land"),
            "fn": (_N, "the thing that knows the answer"),
            "var": (_B, "the name you give each question"),
            "memo": (_E, "the archive you are hoping to avoid it with"),
            "seq": (_N, "every question you intend to ask"),
            "test": (_X, "which questions are worth asking at all")},
     note="Ask the archive first and the function only when it does not know. "
          "One line, one pass, no repeated work.",
     mode=SWEEP, demo={"out": "[]", "nums": "[1, 2, 3]", "memo": "{2: 99}",
                       "step": _STEP},
     example={"out": "out", "fn": "step", "var": "n", "memo": "memo",
              "seq": "nums", "test": "n > 0 and n < max(nums)"},
     lands="out",
     proves="[{fn}({var}) if {var} not in {memo} else {memo}[{var}] "
            "for {var} in {seq} if {test}]",
     requires=("dict",)),

_art("archivist", "forest", "FILE EVERY ANSWER AT ONCE",
     "{memo}.update(zip({seq}, [{value} for {var} in {seq} if {test}]))",
     holes={"value": (_X, "the answer being filed"),
            "memo": (_E, "the archive being written to"),
            "seq": (_N, "the questions"),
            "var": (_B, "the name you give each question"),
            "test": (_X, "which answers are worth keeping")},
     note="`update` takes pairs. zip makes pairs. Neither of them needs a loop "
          "written around it.",
     mode=CHAIN, demo={"memo": "{}", "nums": "[1, 2, 3]", "step": _STEP},
     example={"value": "step(n) + n",
              "memo": "memo", "seq": "nums", "var": "n",
              "test": "n > 0"},
     snapshot={"n": "len({memo})"},
     assertion="all({memo}[{var}] == {value} for {var} in {seq}) "
               "and len({memo}) > __b__['n']",
     requires=("dict",),
     miss="The archive holds exactly what it held. Nothing was filed."),

_art("warden", "forest", "THE WARD ON THE DESCENT",
     "{ok} = {n} <= {floor} or ({n} - {one} in {memo} and {n} - {two} in {memo} "
     "and all({proof} for {k} in {memo}))",
     holes={"proof": (_X, "what must be true of every question already paid for"),
            "ok": (_N, "where the ward's answer lands"),
            "n": (_N, "the question you are about to recurse on"),
            "floor": (_L, "the size at which you stop"),
            "one": (_L, "the first step down"),
            "two": (_L, "the second step down"),
            "memo": (_E, "the archive that has to already hold them"),
            "k": (_B, "the name you give each question in it")},
     note="Base case or both sub-answers. A recursion with neither is a "
          "RecursionError with a stack trace attached.",
     mode=SPLIT, demo={"ok": "None", "n": "5", "memo": "{3: 2, 4: 3}"},
     example={"proof": "q >= 0 and q <= n",
              "ok": "ok", "n": "n", "floor": "1", "one": "1", "two": "2",
              "memo": "memo", "k": "q"},
     lands="ok",
     proves="{n} <= ({floor}) or ({n} - ({one}) in {memo} and {n} - ({two}) in {memo} "
            "and all({proof} for {k} in {memo}))",
     requires=("dict",)),

_art("artificer", "forest", "THE ASK-ONCE ENGINE",
     "{out} = list(map(lambda {arg}: {key}, [{arg} for {arg} in {seq} if {test}]))",
     holes={"key": (_X, "what the tool returns for one argument"),
            "out": (_N, "where the answers land"),
            "arg": (_B, "the name the tool gives its argument"),
            "seq": (_E, "the questions it is run over"),
            "test": (_X, "which questions the tool is worth building for")},
     note="`.get` with a computed default evaluates the default every time. Know "
          "that you are paying for it, and choose it anyway.",
     mode=TOOL, demo={"out": "[]", "memo": "{2: 99}", "nums": "[1, 2, 3]",
                       "step": _STEP},
     example={"key": "memo.get(q, step(q) * 2) + q",
              "out": "out", "arg": "q",
              "seq": "nums", "test": "q not in memo or q > 0"},
     lands="out",
     proves="list(map(lambda {arg}: {key}, [{arg} for {arg} in {seq} if {test}]))",
     requires=("list",)),

_art("seer", "forest", "THE CHEAPEST THING NOT YET PAID FOR",
     "{at} = min(({var} for {var} in {seq} if {var} not in {memo}), "
     "key=lambda {var}: {key})",
     holes={"key": (_X, "what makes one unpaid question cheaper than another"),
            "at": (_N, "where the question lands"),
            "var": (_B, "the name you give each question"),
            "seq": (_N, "every question you have"),
            "memo": (_E, "the archive of what is already paid for"),
     },
     note="The smallest sub-problem the archive cannot answer. That is where the "
          "recursion has to go next, and it is the only place it has to go.",
     mode=MARK, demo={"hit": "0", "nums": "[3, 1, 4]", "memo": "{1: 1}"},
     example={"key": "(q, nums.index(q))",
              "at": "hit", "var": "q", "seq": "nums", "memo": "memo"},
     lands="at",
     proves="min(({var} for {var} in {seq} if {var} not in {memo}), "
            "key=lambda {var}: {key})",
     requires=("dict",)),


# ===========================================================================
# X. THE BRANCH THAT DOES NOT FORK — Binary Tree Canopy
# ===========================================================================
# A node here is a plain dict with a value and two children, because the lesson
# is the shape of the walk and not the shape of the class.

_art("analyst", "canopy", "THE ORDER OF THE BRANCHES DECLARED",
     "{claim} = {node}[{side}] is None or ({node}[{side}][{key}] < {node}[{key}] "
     "and all({node}[{s}] is None or {node}[{s}][{key}] != {node}[{key}] "
     "for {s} in ({side}, {other})))",
     holes={"claim": (_N, "where the verdict lands"),
            "node": (_E, "the node you are standing on"),
            "side": (_L, "the child you are claiming about"),
            "key": (_L, "where a node keeps its value"),
            "other": (_L, "the child you are not claiming about"),
            "s": (_B, "the name you give each side while you check it")},
     note="A node compared only with its own children is the classic wrong "
          "answer. Say which claim you are actually making.",
     mode=SINGLE, demo={"ok": "None", "node": _TREE},
     example={"claim": "ok", "node": "node", "side": "'left'", "key": "'val'",
              "other": "'right'", "s": "w"},
     lands="claim",
     proves="{node}[{side}] is None or ({node}[{side}][{key}] < {node}[{key}] "
            "and all({node}[{s}] is None or {node}[{s}][{key}] != {node}[{key}] "
            "for {s} in ({side}, {other})))",
     requires=("dict",)),

_art("berserker", "canopy", "SUNDER BOTH BRANCHES",
     "{out} = [{kid}[{key}] for {kid} in ({node}[{lhs}], {node}[{rhs}]) "
     "if {kid} and {test}]",
     holes={"out": (_N, "where the values land"),
            "kid": (_B, "the name you give each child"),
            "key": (_L, "where a node keeps its value"),
            "node": (_E, "the node you are standing on"),
            "lhs": (_L, "the near child"),
            "rhs": (_L, "the far child"),
            "test": (_X, "which children are worth taking")},
     note="Both children in one pass, with the None check inside the filter "
          "where it belongs.",
     mode=SWEEP, demo={"out": "[]", "node": _TREE},
     example={"out": "out", "kid": "c", "key": "'val'", "node": "node",
              "lhs": "'left'", "rhs": "'right'", "test": "c['val'] > 0"},
     lands="out",
     proves="[{kid}[{key}] for {kid} in ({node}[{lhs}], {node}[{rhs}]) "
            "if {kid} and {test}]",
     requires=("dict",)),

_art("archivist", "canopy", "THE INDEX OF WHAT HANGS BELOW",
     "{book}[{node}[{key}]] = [{value} "
     "for {kid} in ({node}[{lhs}], {node}[{rhs}]) if {kid}]",
     holes={"value": (_X, "what you file about each child"),
            "book": (_E, "the archive being written to"),
            "node": (_N, "the node being filed"),
            "key": (_L, "where a node keeps its value"),
            "kid": (_B, "the name you give each child"),
            "lhs": (_L, "the near child"),
            "rhs": (_L, "the far child")},
     note="A tree filed as a dict of parent to children is a graph, and every "
          "graph algorithm you know applies to it immediately.",
     mode=CHAIN, demo={"book": "{}", "node": _TREE},
     example={"value": "c['val'] * 2",
              "book": "book", "node": "node", "key": "'val'", "kid": "c",
              "lhs": "'left'", "rhs": "'right'"},
     snapshot={"n": "len({book})"},
     assertion="{book}[{node}[{key}]] == [{value} "
               "for {kid} in ({node}[{lhs}], {node}[{rhs}]) if {kid}] "
               "and len({book}) == __b__['n'] + 1",
     requires=("dict",),
     miss="The archive is the size it was. Nothing was filed."),

_art("warden", "canopy", "THE WARD ON THE FORK",
     "{ok} = {node} is not None and ({node}[{lhs}] is None) == ({node}[{rhs}] is None) "
     "and all({proof} "
     "for {kid} in ({node}, {node}[{lhs}], {node}[{rhs}]) if {kid})",
     holes={"proof": (_X, "what every node in reach has to hold"),
            "ok": (_N, "where the ward's answer lands"),
            "node": (_E, "the node being checked"),
            "lhs": (_L, "the near child"),
            "rhs": (_L, "the far child"),
            "kid": (_B, "the name you give each node in the little family"),
            "floor": (_L, "the value none of them may sit at or below")},
     note="A node with one child is not a leaf. Half the tree bugs in the world "
          "are that sentence, unlearned — and the other half are the None you "
          "walked into afterwards.",
     mode=SPLIT, demo={"ok": "None", "node": _TREE},
     example={"proof": "c['val'] > 0 and c['val'] < 99",
              "ok": "ok", "node": "node", "lhs": "'left'", "rhs": "'right'",
              "kid": "c", "floor": "0"},
     lands="ok",
     proves="{node} is not None and ({node}[{lhs}] is None) == ({node}[{rhs}] is None) "
            "and all({proof} "
            "for {kid} in ({node}, {node}[{lhs}], {node}[{rhs}]) if {kid})",
     requires=("dict",)),

_art("artificer", "canopy", "THE IN-ORDER ENGINE",
     "{out} = sorted([{kid} for {kid} in ({node}[{lhs}], {node}, {node}[{rhs}]) "
     "if {kid}], key=lambda {t}: {rank})",
     holes={"rank": (_X, "what each node sorts by"),
            "out": (_N, "where the ordered nodes land"),
            "kid": (_B, "the name you give each node in the little family"),
            "node": (_E, "the node you are standing on"),
            "lhs": (_L, "the near child"),
            "rhs": (_L, "the far child"),
            "t": (_B, "the name the key function gives each node"),
            "key": (_L, "where a node keeps its value")},
     note="Left, self, right, ordered by value. That is one step of an in-order "
          "walk, written without a walk.",
     mode=TOOL, demo={"out": "[]", "node": _TREE},
     example={"rank": "(x['val'], x['left'] is None)",
              "out": "out", "kid": "c", "node": "node", "lhs": "'left'",
              "rhs": "'right'", "t": "x", "key": "'val'"},
     lands="out",
     proves="sorted([{kid} for {kid} in ({node}[{lhs}], {node}, {node}[{rhs}]) "
            "if {kid}], key=lambda {t}: {rank})",
     requires=("dict",)),

_art("seer", "canopy", "THE HIGHEST VALUE IN REACH",
     "{at} = max(({kid}[{key}] for {kid} in ({node}, {node}[{lhs}], {node}[{rhs}]) "
     "if {test}), default={floor})",
     holes={"test": (_X, "which nodes are actually in reach"),
            "at": (_N, "where the value lands"),
            "kid": (_B, "the name you give each node in reach"),
            "key": (_L, "where a node keeps its value"),
            "node": (_E, "the node you are standing on"),
            "lhs": (_L, "the near child"),
            "rhs": (_L, "the far child"),
            "floor": (_L, "what you get when there is nothing in reach")},
     note="`default=` is the difference between an empty answer and a "
          "ValueError, and you choose which one this is.",
     mode=MARK, demo={"hit": "0", "node": _TREE},
     example={"test": "c and c['val'] > 0",
              "at": "hit", "kid": "c", "key": "'val'", "node": "node",
              "lhs": "'left'", "rhs": "'right'", "floor": "0"},
     lands="at",
     proves="max(({kid}[{key}] for {kid} in ({node}, {node}[{lhs}], {node}[{rhs}]) "
            "if {test}), default={floor})",
     requires=("dict",)),


# ===========================================================================
# XI. THE ROOM OFF THE GRID — Matrix Citadel
# ===========================================================================

_art("analyst", "citadel", "THE PLAN DECLARED SQUARE",
     "{claim} = len({grid}) == len({grid}[0]) "
     "and all(len({row}) == len({grid}) for {row} in {grid}) "
     "and all({v} is not None for {row} in {grid} for {v} in {row})",
     holes={"claim": (_N, "where the verdict lands"),
            "grid": (_E, "the plane being declared about"),
            "row": (_B, "the name you give each row"),
            "v": (_B, "the name you give each cell")},
     note="Square, rectangular and fully populated are three different claims. "
          "A ragged grid fails the second one silently.",
     mode=SINGLE, demo={"ok": "None", "grid": _GRID},
     example={"claim": "ok", "grid": "grid", "row": "r", "v": "c"},
     lands="claim",
     proves="len({grid}) == len({grid}[0]) "
            "and all(len({row}) == len({grid}) for {row} in {grid}) "
            "and all({v} is not None for {row} in {grid} for {v} in {row})",
     requires=("grid",)),

_art("berserker", "citadel", "TURN THE WHOLE FLOOR",
     "{out} = [[{value} for {row} in {grid}] for {c} in range(len({grid}[0]))]",
     holes={"value": (_X, "what lands in the turned cell"),
            "out": (_N, "where the turned plane lands"),
            "row": (_B, "the name you give each row"),
            "c": (_B, "the name you give each column"),
            "grid": (_E, "the plane being turned")},
     note="A comprehension inside a comprehension transposes in one line and "
           "allocates nothing you did not ask for.",
     mode=SWEEP, demo={"out": "[]", "grid": _GRID},
     example={"value": "r[c] * 2",
              "out": "out", "row": "r", "c": "c", "grid": "grid"},
     lands="out",
     proves="[[{value} for {row} in {grid}] for {c} in range(len({grid}[0]))]",
     requires=("grid",)),

_art("archivist", "citadel", "THE INDEX OF EVERY CELL",
     "{book} = dict(zip([({r}, {c}) for {r} in range(len({grid})) "
     "for {c} in range(len({grid}[0]))], "
     "[{v} for {row} in {grid} for {v} in {row}]))",
     holes={"book": (_N, "where the index lands"),
            "r": (_B, "the name you give the row number"),
            "c": (_B, "the name you give the column number"),
            "grid": (_E, "the plane being filed"),
            "v": (_B, "the name you give each cell"),
            "row": (_B, "the name you give each row")},
     note="Two for clauses in one comprehension walk the whole plane in row "
          "order. Both lists come out in the same order, which is why zip works.",
     mode=CHAIN, demo={"book": "{}", "grid": _GRID},
     example={"book": "book", "r": "y", "c": "x", "grid": "grid", "v": "cell",
              "row": "line"},
     lands="book",
     proves="dict(zip([({r}, {c}) for {r} in range(len({grid})) "
            "for {c} in range(len({grid}[0]))], "
            "[{v} for {row} in {grid} for {v} in {row}]))",
     requires=("grid",)),

_art("warden", "citadel", "THE PERIMETER WARD",
     "{ok} = 0 <= {r} < len({grid}) and 0 <= {c} < len({grid}[0]) "
     "and {grid}[{r}][{c}] != {wall} "
     "and all({proof} for {row} in {grid})",
     holes={"proof": (_X, "what every row has to be"),
            "ok": (_N, "where the ward's answer lands"),
            "r": (_N, "the row you are about to step into"),
            "c": (_N, "the column you are about to step into"),
            "grid": (_E, "the plane you are stepping on"),
            "wall": (_L, "the value that means you may not"),
            "row": (_B, "the name you give each row while you check its width")},
     note="Both bounds, then the contents, then the claim that every row is wide "
          "enough. A ragged grid passes the first three.",
     mode=SPLIT, demo={"ok": "None", "grid": _GRID, "r": "1", "c": "1"},
     example={"proof": "len(line) > c and len(line) == len(grid)",
              "ok": "ok", "r": "r", "c": "c", "grid": "grid", "wall": "0",
              "row": "line"},
     lands="ok",
     proves="0 <= {r} < len({grid}) and 0 <= {c} < len({grid}[0]) "
            "and {grid}[{r}][{c}] != ({wall}) "
            "and all({proof} for {row} in {grid})",
     requires=("grid",)),

_art("artificer", "citadel", "THE HEAVIEST-ROW ENGINE",
     "{out} = sorted(range(len({grid})), key=lambda {i}: {key})",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the ordered row numbers land"),
            "grid": (_E, "the plane being read"),
            "i": (_B, "the name the key function gives each row number")},
     note="Rank the rows without moving them. What you get back are addresses, "
          "which is what you can actually use.",
     mode=TOOL, demo={"out": "[]", "grid": _GRID},
     example={"key": "(-sum(grid[i]), i)",
              "out": "out", "grid": "grid", "i": "i"},
     lands="out",
     proves="sorted(range(len({grid})), key=lambda {i}: {key})",
     requires=("grid",)),

_art("seer", "citadel", "THE ONE CELL THAT MATTERS",
     "{at} = max((({r}, {c}) for {r} in range(len({grid})) "
     "for {c} in range(len({grid}[0]))), key=lambda {p}: {grid}[{p}[0]][{p}[1]])",
     holes={"at": (_N, "where the coordinates land"),
            "r": (_B, "the name you give the row number"),
            "c": (_B, "the name you give the column number"),
            "grid": (_E, "the plane being read"),
            "p": (_B, "the name the key function gives each coordinate pair")},
     note="Search the addresses and score them by what is at them. You end up "
          "holding where it is, not just what it was.",
     mode=MARK, demo={"hit": "None", "grid": _GRID},
     example={"at": "hit", "r": "y", "c": "x", "grid": "grid", "p": "pos"},
     lands="at",
     proves="max((({r}, {c}) for {r} in range(len({grid})) "
            "for {c} in range(len({grid}[0]))), key=lambda {p}: {grid}[{p}[0]][{p}[1]])",
     requires=("grid",)),


# ===========================================================================
# XII. THE RUIN WITH ONE ROAD — Graph Wastes
# ===========================================================================

_art("analyst", "wastes", "THE MOOT DECLARED WHOLE",
     "{claim} = all({proof} for {node} in {graph} for {nb} in {graph}[{node}]) "
     "and len({graph}) > {floor}",
     holes={"proof": (_X, "what must be true of every edge"),
            "claim": (_N, "where the verdict lands"),
            "nb": (_B, "the name you give each neighbour"),
            "graph": (_E, "the moot being declared about"),
            "node": (_B, "the name you give each ruin"),
            "floor": (_L, "the size below which the claim is not worth making")},
     note="Every name a node knows must itself be a node. A dangling edge is a "
          "KeyError waiting for a traversal to find it.",
     mode=SINGLE, demo={"ok": "None", "graph": _GRAPH},
     example={"proof": "b in graph and b != a",
              "claim": "ok", "nb": "b", "graph": "graph", "node": "a",
              "floor": "0"},
     lands="claim",
     proves="all({proof} for {node} in {graph} for {nb} in {graph}[{node}]) "
            "and len({graph}) > ({floor})",
     requires=("dict",)),

_art("berserker", "wastes", "TAKE THE WHOLE RING",
     "{out} = [{expr} for {node} in {frontier} for {nb} in {graph}[{node}] "
     "if {nb} not in {seen}]",
     holes={"out": (_N, "where the next ring lands"),
            "expr": (_X, "what you record about each one you take"),
            "node": (_B, "the name you give each ruin on the edge"),
            "frontier": (_N, "the edge you are standing on"),
            "nb": (_B, "the name you give each neighbour"),
            "graph": (_E, "the moot"),
            "seen": (_N, "everywhere you have already been")},
     note="A whole BFS ring in one line. Carry where each one came from or you "
          "will finish holding the distance and no path.",
     mode=SWEEP, demo={"out": "[]", "graph": _GRAPH, "frontier": "['a']",
                       "seen": "set()"},
     example={"out": "out", "expr": "(n, cur, len(graph[n]))", "node": "cur",
              "frontier": "frontier", "nb": "n", "graph": "graph",
              "seen": "seen"},
     lands="out",
     proves="[{expr} for {node} in {frontier} for {nb} in {graph}[{node}] "
            "if {nb} not in {seen}]",
     requires=("dict",)),

_art("archivist", "wastes", "THE INDEX OF DISTANCES",
     "{book} = dict(zip({graph}[{node}], "
     "[{value} for {nb} in {graph}[{node}] if {test}]))",
     holes={"value": (_X, "how far the neighbour is"),
            "book": (_N, "where the distances land"),
            "graph": (_E, "the moot"),
            "node": (_N, "the ruin you are standing in"),
            "nb": (_B, "the name you give each neighbour"),
            "test": (_X, "which roads are worth costing")},
     note="Every neighbour is exactly one further than you are. That sentence is "
          "the whole of breadth-first search.",
     mode=CHAIN, demo={"book": "{}", "graph": _GRAPH, "node": "'a'",
                       "dist": "{'a': 0}"},
     example={"value": "dist[node] + 1",
              "book": "book", "graph": "graph", "node": "node", "nb": "n", "test": "n in graph"},
     lands="book",
     proves="dict(zip({graph}[{node}], "
            "[{value} for {nb} in {graph}[{node}] if {test}]))",
     requires=("dict",)),

_art("warden", "wastes", "THE WARD ON THE ROAD",
     "{ok} = {node} in {graph} "
     "and all({proof} for {nb} in {graph}[{node}]) "
     "and len({graph}[{node}]) >= {floor}",
     holes={"proof": (_X, "what has to be true of a neighbour before you walk to it"),
            "ok": (_N, "where the ward's answer lands"),
            "node": (_N, "the ruin you are about to leave"),
            "graph": (_E, "the moot"),
            "nb": (_B, "the name you give each neighbour"),
            "floor": (_L, "the number of roads it must have")},
     note="Check the node is known before you index it. `graph[node]` on a name "
          "the graph has never heard of is the most common traversal crash there is.",
     mode=SPLIT, demo={"ok": "None", "graph": _GRAPH, "node": "'a'",
                       "seen": "set()"},
     example={"proof": "n in seen or n in graph",
              "ok": "ok", "node": "node", "graph": "graph", "nb": "n", "floor": "0"},
     lands="ok",
     proves="{node} in {graph} "
            "and all({proof} for {nb} in {graph}[{node}]) "
            "and len({graph}[{node}]) >= ({floor})",
     requires=("dict",)),

_art("artificer", "wastes", "THE BUSIEST-RUIN ENGINE",
     "{out} = sorted(({n} for {n} in {graph} if {test}), "
     "key=lambda {n}: {key})",
     holes={"key": (_X, "the whole sort key, ties included"),
            "out": (_N, "where the ordered ruins land"),
            "n": (_B, "the name you give each ruin"),
            "graph": (_E, "the moot"),
            "test": (_X, "which ruins are worth ranking")},
     note="Degree, descending, ties by name. Ranking the nodes before you walk "
          "them is how a heuristic starts.",
     mode=TOOL, demo={"out": "[]", "graph": _GRAPH},
     example={"key": "(-len(graph[v]), v)",
              "out": "out", "n": "v", "graph": "graph", "test": "v in graph"},
     lands="out",
     proves="sorted(({n} for {n} in {graph} if {test}), "
            "key=lambda {n}: {key})",
     requires=("dict",)),

_art("seer", "wastes", "THE QUIETEST ROAD OUT",
     "{at} = min(({nb} for {nb} in {graph}[{node}] if {nb} not in {seen}), "
     "key=lambda {nb}: {key})",
     holes={"key": (_X, "what makes one road quieter than another"),
            "at": (_N, "where the neighbour's name lands"),
            "nb": (_B, "the name you give each neighbour"),
            "graph": (_E, "the moot"),
            "node": (_N, "the ruin you are standing in"),
            "seen": (_N, "everywhere you have already been")},
     note="The unvisited neighbour with the fewest roads of its own. That is a "
          "choice, and a depth-first walk is nothing but a sequence of them.",
     mode=MARK, demo={"hit": "None", "graph": _GRAPH, "node": "'a'",
                      "seen": "set()"},
     example={"key": "(len(graph[n]), n)",
              "at": "hit", "nb": "n", "graph": "graph", "node": "node",
              "seen": "seen"},
     lands="at",
     proves="min(({nb} for {nb} in {graph}[{node}] if {nb} not in {seen}), "
            "key=lambda {nb}: {key})",
     requires=("dict",)),


# ===========================================================================
# XIII. THE TILE PAID FOR TWICE — Dynamic Programming Ruins
# ===========================================================================

_art("analyst", "ruins", "THE TABLE DECLARED SOUND",
     "{claim} = len({dp}) == len({seq}) + {one} and {dp}[0] == {base} "
     "and all({proof} for {v} in {dp})",
     holes={"proof": (_X, "the invariant every row has to hold"),
            "claim": (_N, "where the verdict lands"),
            "dp": (_E, "the ledger of paid debts"),
            "seq": (_N, "the input it was sized from"),
            "one": (_L, "the empty prefix the table also needs a row for"),
            "base": (_L, "what the empty prefix is worth"),
            "v": (_B, "the name you give each entry while you check it")},
     note="Length, base case, and the invariant. A DP table with the wrong "
          "length is an off-by-one that only shows up on the last input.",
     mode=SINGLE, demo={"ok": "None", "dp": _DP, "nums": _NUMS5},
     example={"proof": "x >= 0 and x <= max(dp)",
              "claim": "ok", "dp": "dp", "seq": "nums", "one": "1",
              "base": "1", "v": "x"},
     lands="claim",
     proves="len({dp}) == len({seq}) + ({one}) and {dp}[0] == ({base}) "
            "and all({proof} for {v} in {dp})",
     requires=("list",)),

_art("berserker", "ruins", "PAY THE WHOLE LEDGER AT ONCE",
     "{out} = [max({dp}[{i} - {one}], {expr}) "
     "for {i} in range({two}, len({dp}))]",
     holes={"expr": (_X, "what taking this one is worth"),
            "out": (_N, "where every decision lands"),
            "dp": (_E, "the ledger"),
            "i": (_B, "the name you give each row"),
            "one": (_L, "one step back"),
            "two": (_L, "two steps back"),
            "seq": (_N, "the input the ledger is about")},
     note="Take it or leave it, at every row, in one line. The offset between "
          "the table and the input is the part that bites.",
     mode=SWEEP, demo={"out": "[]", "dp": _DP, "nums": _NUMS5},
     example={"expr": "dp[i - 2] + nums[i - 1]",
              "out": "out", "dp": "dp", "i": "i", "one": "1", "two": "2",
              "seq": "nums"},
     lands="out",
     proves="[max({dp}[{i} - ({one})], {expr}) "
            "for {i} in range(({two}), len({dp}))]",
     requires=("list",)),

_art("archivist", "ruins", "THE INDEX OF WHAT EACH ROW BOUGHT",
     "{book} = dict(zip(range(len({dp})), "
     "[{value} for {i} in range(len({dp}))]))",
     holes={"value": (_X, "what that row actually bought"),
            "book": (_N, "where the index lands"),
            "dp": (_E, "the ledger being read"),
            "i": (_B, "the name you give each row"),
            "one": (_L, "the step back to the previous row")},
     note="The difference between neighbouring rows is what that row actually "
          "bought. Row zero reaches backwards to the end, and you should notice.",
     mode=CHAIN, demo={"book": "{}", "dp": _DP},
     example={"value": "dp[i] - dp[i - 1]",
              "book": "book", "dp": "dp", "i": "i", "one": "1"},
     lands="book",
     proves="dict(zip(range(len({dp})), "
            "[{value} for {i} in range(len({dp}))]))",
     requires=("list",)),

_art("warden", "ruins", "THE WARD ON THE ROW",
     "{ok} = {two} <= {i} < len({dp}) and {dp}[{i} - {one}] >= {dp}[{i} - {two}] "
     "and all({proof} for {j} in range({i}))",
     holes={"proof": (_X, "the invariant behind you"),
            "ok": (_N, "where the ward's answer lands"),
            "two": (_L, "how far back the recurrence reaches"),
            "i": (_N, "the row you are about to fill"),
            "dp": (_E, "the ledger"),
            "one": (_L, "one step back"),
            "j": (_B, "the name you give every row behind you")},
     note="A recurrence that reaches two rows back cannot be started at row one. "
          "Prove the rows behind you exist before you read them.",
     mode=SPLIT, demo={"ok": "None", "dp": _DP, "i": "2"},
     example={"proof": "dp[k] >= 0 and dp[k] <= max(dp)",
              "ok": "ok", "two": "2", "i": "i", "dp": "dp", "one": "1",
              "j": "k"},
     lands="ok",
     proves="({two}) <= {i} < len({dp}) and {dp}[{i} - ({one})] >= {dp}[{i} - ({two})] "
            "and all({proof} for {j} in range({i}))",
     requires=("list",)),

_art("artificer", "ruins", "THE BEST-ROW ENGINE",
     "{out} = sorted(({j} for {j} in range(len({dp})) if {test}), "
     "key=lambda {j}: (-{dp}[{j}], {j}))",
     holes={"out": (_N, "where the ordered rows land"),
            "j": (_B, "the name you give each row"),
            "dp": (_E, "the ledger"),
            "test": (_X, "which rows are worth ranking")},
     note="Rank the rows by what they hold and keep their numbers. The number is "
          "the answer; the value is only the evidence.",
     mode=TOOL, demo={"out": "[]", "dp": _DP},
     example={"out": "out", "j": "k", "dp": "dp", "test": "dp[k] >= 0"},
     lands="out",
     proves="sorted(({j} for {j} in range(len({dp})) if {test}), "
            "key=lambda {j}: (-{dp}[{j}], {j}))",
     requires=("list",)),

_art("seer", "ruins", "THE LAST ROW THAT PAID",
     "{at} = max(({j} for {j} in range(len({dp})) if {proof}), "
     "default={floor})",
     holes={"proof": (_X, "what makes a row the one you want"),
            "at": (_N, "where the row number lands"),
            "j": (_B, "the name you give each row"),
            "dp": (_E, "the ledger"),
            "floor": (_L, "what you get when the ledger is empty")},
     note="The furthest row still holding the best answer. Reconstructing the "
          "choice starts there and walks backwards.",
     mode=MARK, demo={"hit": "-1", "dp": _DP},
     example={"proof": "dp[k] == max(dp)",
              "at": "hit", "j": "k", "dp": "dp", "floor": "0"},
     lands="at",
     proves="max(({j} for {j} in range(len({dp})) if {proof}), "
            "default={floor})",
     requires=("list",)),


# ===========================================================================
# XIV. THE FLOOR BETWEEN FLOORS — Complexity Tower
# ===========================================================================
# Every art in this room writes its own quadratic on purpose, in a place where
# the player can see it. The lesson is not "never do this". It is "know when you
# have done it".

_art("analyst", "tower", "THE COST DECLARED",
     "{claim} = len({seq}) * len({seq}) > {budget} "
     "and len({seq}) == len([{y} for {y} in {seq} if {proof}])",
     holes={"proof": (_X, "what makes an element real work"),
            "claim": (_N, "where the verdict lands"),
            "seq": (_E, "the work you are about to do"),
            "budget": (_N, "what you are allowed to spend"),
            "y": (_B, "the name you give each element"),
            "floor": (_L, "the value below which an element is not real work")},
     note="Say the cost before you pay it. Work per element times elements is "
          "the whole art, and the whole art fits on one line.",
     mode=SINGLE, demo={"ok": "None", "nums": _NUMS5, "budget": "10"},
     example={"proof": "n >= 0 and n < budget",
              "claim": "ok", "seq": "nums", "budget": "budget", "y": "n",
              "floor": "0"},
     lands="claim",
     proves="len({seq}) * len({seq}) > {budget} "
            "and len({seq}) == len([{y} for {y} in {seq} if {proof}])",
     requires=("list",)),

_art("berserker", "tower", "COUNT EVERY PAIR",
     "{out} = [len([{y} for {y} in {seq} if {y} < {x}]) for {x} in {seq} if {test}]",
     holes={"out": (_N, "where the counts land"),
            "y": (_B, "the name you give the inner element"),
            "seq": (_E, "the host being counted against itself"),
            "x": (_B, "the name you give the outer element"),
            "test": (_X, "which of them are worth the inner pass")},
     note="A comprehension inside a comprehension over the same list is n "
          "squared. It is written here so you can recognise it written anywhere "
          "— and the filter is the only thing that ever brings it down.",
     mode=SWEEP, demo={"out": "[]", "nums": _NUMS5},
     example={"out": "out", "y": "b", "seq": "nums", "x": "a", "test": "a > 1 and a != max(nums)"},
     lands="out",
     proves="[len([{y} for {y} in {seq} if {y} < {x}]) for {x} in {seq} if {test}]",
     requires=("list",)),

_art("archivist", "tower", "THE INDEX OF RANKS",
     "{book} = dict(zip({seq}, "
     "[len([{y} for {y} in {seq} if {proof}]) for {x} in {seq}]))",
     holes={"proof": (_X, "what makes the inner element count"),
            "book": (_N, "where the index lands"),
            "seq": (_E, "the host being ranked"),
            "y": (_B, "the name you give the inner element"),
            "x": (_B, "the name you give the outer element")},
     note="Value to rank, filed once. You paid n squared to build it; do not pay "
          "it twice by rebuilding it inside a loop.",
     mode=CHAIN, demo={"book": "{}", "nums": _NUMS5},
     example={"proof": "b < a and b >= 0",
              "book": "book", "seq": "nums", "y": "b", "x": "a"},
     lands="book",
     proves="dict(zip({seq}, "
            "[len([{y} for {y} in {seq} if {proof}]) for {x} in {seq}]))",
     requires=("list",)),

_art("warden", "tower", "THE WARD ON THE BUDGET",
     "{ok} = len({seq}) <= {budget} "
     "and not any(len([{y} for {y} in {seq} if {proof}]) > {cap} for {x} in {seq})",
     holes={"proof": (_X, "what counts as the same value"),
            "ok": (_N, "where the ward's answer lands"),
            "seq": (_E, "the work being budgeted"),
            "budget": (_N, "how much input you can afford"),
            "y": (_B, "the name you give the inner element"),
            "x": (_B, "the name you give the outer element"),
            "cap": (_L, "how many times one value may repeat")},
     note="Size and skew. An input inside your budget that is all one value is "
          "still the input that kills you.",
     mode=SPLIT, demo={"ok": "None", "nums": _NUMS5, "budget": "10"},
     example={"proof": "b == a and b > 0",
              "ok": "ok", "seq": "nums", "budget": "budget", "y": "b",
              "x": "a", "cap": "2"},
     lands="ok",
     proves="len({seq}) <= {budget} "
            "and not any(len([{y} for {y} in {seq} if {proof}]) > ({cap}) "
            "for {x} in {seq})",
     requires=("list",)),

_art("artificer", "tower", "THE RANK-ORDER ENGINE",
     "{out} = sorted({seq}, key=lambda {x}: (len([{y} for {y} in {seq} if {proof}]), {x}))",
     holes={"proof": (_X, "what makes the inner element count"),
            "out": (_N, "where the ordered host lands"),
            "seq": (_E, "the host being ordered"),
            "x": (_B, "the name the key function gives its argument"),
            "y": (_B, "the name you give the inner element")},
     note="A key function with a loop inside it runs that loop once per element. "
          "sorted() is n log n; this key made it n squared log n.",
     mode=TOOL, demo={"out": "[]", "nums": _NUMS5},
     example={"proof": "b < a and b % 2 == 0",
              "out": "out", "seq": "nums", "x": "a", "y": "b"},
     lands="out",
     proves="sorted({seq}, key=lambda {x}: (len([{y} for {y} in {seq} if {proof}]), {x}))",
     requires=("list",)),

_art("seer", "tower", "THE ONE THAT COSTS THE MOST",
     "{at} = max({seq}, key=lambda {x}: (len([{y} for {y} in {seq} if {proof}]), {x}))",
     holes={"proof": (_X, "what counts as another sighting"),
            "at": (_N, "where the value lands"),
            "seq": (_E, "the host being read"),
            "x": (_B, "the name the key function gives its argument"),
            "y": (_B, "the name you give the inner element")},
     note="The value that repeats most is the value that decides the worst case. "
          "Find it before the clock does.",
     mode=MARK, demo={"hit": "None", "nums": _NUMS5},
     example={"proof": "b == a and b > 0",
              "at": "hit", "seq": "nums", "x": "a", "y": "b"},
     lands="at",
     proves="max({seq}, key=lambda {x}: (len([{y} for {y} in {seq} if {proof}]), {x}))",
     requires=("list",)),


# ===========================================================================
# XV. THE CELL THAT LOCKS FROM INSIDE — Debugging Dungeon
# ===========================================================================

_art("analyst", "dungeon", "THE SUITE DECLARED GREEN",
     "{claim} = all({fn}({case}[0]) == {case}[{one}] for {case} in {cases}) "
     "and bool({cases}) and all(len({case}) == {two} for {case} in {cases})",
     holes={"claim": (_N, "where the verdict lands"),
            "fn": (_N, "the thing under test"),
            "case": (_B, "the name you give each case"),
            "one": (_L, "where the expected answer sits in a case"),
            "cases": (_E, "the suite"),
            "two": (_L, "how many parts a case has")},
     note="A green suite over an empty list is still green. Say the suite is "
          "non-empty and well-formed in the same breath as saying it passes.",
     mode=SINGLE, demo={"ok": "None", "cases": _CASES, "solve": _SOLVE},
     example={"claim": "ok", "fn": "solve", "case": "c", "one": "1",
              "cases": "cases", "two": "2"},
     lands="claim",
     proves="all({fn}({case}[0]) == {case}[{one}] for {case} in {cases}) "
            "and bool({cases}) and all(len({case}) == ({two}) for {case} in {cases})",
     requires=("list",)),

_art("berserker", "dungeon", "DRAG OUT EVERY FAILURE",
     "{out} = [{expr} for {case} in {cases} "
     "if {fn}({case}[0]) != {case}[{one}]]",
     holes={"expr": (_X, "what you record about each failure"),
            "out": (_N, "where the failures land"),
            "case": (_B, "the name you give each case"),
            "fn": (_N, "the thing under test"),
            "cases": (_E, "the suite"),
            "one": (_L, "where the expected answer sits in a case")},
     note="Every failing case with what it actually returned, in one pass. The "
          "pair is the whole bug report.",
     mode=SWEEP, demo={"out": "[]", "cases": _CASES, "solve": _SOLVE},
     example={"expr": "(c, solve(c[0]))",
              "out": "out", "case": "c", "fn": "solve", "cases": "cases",
              "one": "1"},
     lands="out",
     proves="[{expr} for {case} in {cases} "
            "if {fn}({case}[0]) != {case}[{one}]]",
     requires=("list",)),

_art("archivist", "dungeon", "THE INDEX OF WHAT IT ACTUALLY DID",
     "{book} = dict(zip([{case}[0] for {case} in {cases}], "
     "[{value} for {case} in {cases}]))",
     holes={"value": (_X, "what you file about each case"),
            "book": (_N, "where the index lands"),
            "case": (_B, "the name you give each case"),
            "cases": (_E, "the suite"),
            "fn": (_N, "the thing under test")},
     note="Input to observed output, filed. The expected column is a separate "
          "argument, and keeping them separate is the discipline.",
     mode=CHAIN, demo={"book": "{}", "cases": _CASES, "solve": _SOLVE},
     example={"value": "solve(c[0]) - c[1]",
              "book": "book", "case": "c", "cases": "cases", "fn": "solve"},
     lands="book",
     proves="dict(zip([{case}[0] for {case} in {cases}], "
            "[{value} for {case} in {cases}]))",
     requires=("list",)),

_art("warden", "dungeon", "THE WARD ON THE SUITE",
     "{ok} = bool({cases}) and all({proof} for {case} in {cases}) "
     "and {fn}({cases}[0][0]) == {cases}[0][{one}]",
     holes={"proof": (_X, "what a well-formed case looks like"),
            "ok": (_N, "where the ward's answer lands"),
            "cases": (_E, "the suite"),
            "case": (_B, "the name you give each case"),
            "fn": (_N, "the thing under test"),
            "one": (_L, "where the expected answer sits in a case")},
     note="Check the suite before you trust the result of running it. A "
           "malformed case fails in a way that looks like a bug in the code.",
     mode=SPLIT, demo={"ok": "None", "cases": _CASES, "solve": _SOLVE},
     example={"proof": "len(c) == 2 and c[0] < c[1]",
              "ok": "ok", "cases": "cases", "case": "c",
              "fn": "solve", "one": "1"},
     lands="ok",
     proves="bool({cases}) and all({proof} for {case} in {cases}) "
            "and {fn}({cases}[0][0]) == {cases}[0][{one}]",
     requires=("list",)),

_art("artificer", "dungeon", "THE FAILURES-FIRST ENGINE",
     "{out} = sorted({cases}, key=lambda {case}: {key})",
     holes={"key": (_X, "the whole sort key: green last, smallest first"),
            "out": (_N, "where the ordered suite lands"),
            "cases": (_E, "the suite"),
            "case": (_B, "the name the key function gives each case"),
            "one": (_L, "where the expected answer sits in a case")},
     note="False sorts before True, so the failures come out at the front for "
          "free. Nobody needs to be told that twice.",
     mode=TOOL, demo={"out": "[]", "cases": _CASES, "solve": _SOLVE},
     example={"key": "(solve(c[0]) == c[1], c[0])",
              "out": "out", "cases": "cases", "case": "c",
              "one": "1"},
     lands="out",
     proves="sorted({cases}, key=lambda {case}: {key})",
     requires=("list",)),

_art("seer", "dungeon", "THE SMALLEST THING THAT BREAKS IT",
     "{at} = min(({case} for {case} in {cases} if {proof}), "
     "key=lambda {case}: {case}[0])",
     holes={"proof": (_X, "what makes a case a failing one"),
            "at": (_N, "where the case lands"),
            "case": (_B, "the name you give each case"),
            "cases": (_E, "the suite"),
            "one": (_L, "where the expected answer sits in a case")},
     note="The smallest failing input, not the first one you noticed. Reducing "
          "the case is most of the debugging.",
     mode=MARK, demo={"hit": "None", "cases": _CASES, "solve": _SOLVE},
     example={"proof": "solve(c[0]) != c[1]",
              "at": "hit", "case": "c", "cases": "cases",
              "one": "1"},
     lands="at",
     proves="min(({case} for {case} in {cases} if {proof}), "
            "key=lambda {case}: {case}[0])",
     requires=("list",)),


# ===========================================================================
# XVI. UNDER THE SAND — The Coding Coliseum
# ===========================================================================
# Two structures at once, under a clock. Nothing new is taught here; what is
# taught is holding two things in your head while somebody watches.

_art("analyst", "coliseum", "THE TWO-STRUCTURE CLAIM",
     "{claim} = len({seq}) == sum({book}.values()) and set({book}) == set({seq}) "
     "and len({book}) <= len({seq}) and all({book}[{k}] > {floor} for {k} in {book})",
     holes={"claim": (_N, "where the verdict lands"),
            "seq": (_N, "the sequence"),
            "book": (_E, "the table that is supposed to describe it"),
            "k": (_B, "the name you give each key while you check it"),
            "floor": (_L, "the count no key may sit at or below")},
     note="Four claims tying a list to its own count table. If any one of them "
          "is false the pair has drifted, and the drift is the bug.",
     mode=SINGLE, demo={"ok": "None", "nums": "[3, 1, 4, 1]",
                        "tally": "{3: 1, 1: 2, 4: 1}"},
     example={"claim": "ok", "seq": "nums", "book": "tally", "k": "w",
              "floor": "0"},
     lands="claim",
     proves="len({seq}) == sum({book}.values()) and set({book}) == set({seq}) "
            "and len({book}) <= len({seq}) "
            "and all({book}[{k}] > ({floor}) for {k} in {book})",
     requires=("dict",)),

_art("berserker", "coliseum", "SUNDER WHAT THE TABLE MARKS",
     "{out} = [{x} for {x} in {seq} if {proof} "
     "and {x} not in {seen}]",
     holes={"proof": (_X, "what the table has to say about it"),
            "out": (_N, "where the survivors land"),
            "x": (_B, "the name you give each element"),
            "seq": (_E, "the sequence being cut down"),
            "seen": (_N, "what you have already dealt with")},
     note="One pass consulting two structures. `.get` with a default is what "
          "keeps a missing key from ending the line.",
     mode=SWEEP, demo={"out": "[]", "nums": "[3, 1, 4, 1]",
                       "tally": "{3: 1, 1: 2, 4: 1}", "seen": "set()",
                       "floor": "1"},
     example={"proof": "tally.get(n, 0) > floor",
              "out": "out", "x": "n", "seq": "nums", "seen": "seen"},
     lands="out",
     proves="[{x} for {x} in {seq} if {proof} "
            "and {x} not in {seen}]",
     requires=("list",)),

_art("archivist", "coliseum", "THE TABLE BUILT IN ONE BREATH",
     "{book} = dict(zip(sorted(set({seq})), "
     "[sum({one} for {y} in {seq} if {proof}) for {x} in sorted(set({seq}))]))",
     holes={"proof": (_X, "what counts as another sighting"),
            "book": (_N, "where the table lands"),
            "seq": (_E, "the sequence being counted"),
            "one": (_L, "what each sighting is worth"),
            "y": (_B, "the name you give the inner element"),
            "x": (_B, "the name you give each distinct value")},
     note="`sum(1 for ...)` counts without building the list it would have "
          "counted. It is the version that fits in memory.",
     mode=CHAIN, demo={"book": "{}", "nums": "[3, 1, 4, 1]"},
     example={"proof": "b == a and b > 0",
              "book": "book", "seq": "nums", "one": "1", "y": "b", "x": "a"},
     lands="book",
     proves="dict(zip(sorted(set({seq})), "
            "[sum({one} for {y} in {seq} if {proof}) for {x} in sorted(set({seq}))]))",
     requires=("list",)),

_art("warden", "coliseum", "THE WARD ACROSS BOTH",
     "{ok} = 0 <= {i} < len({seq}) and {seq}[{i}] in {book} "
     "and {book}[{seq}[{i}]] == sum({one} for {y} in {seq} if {y} == {seq}[{i}])",
     holes={"ok": (_N, "where the ward's answer lands"),
            "i": (_N, "the position you are about to trust"),
            "seq": (_E, "the sequence"),
            "book": (_N, "the table that claims to describe it"),
            "one": (_L, "what each sighting is worth"),
            "y": (_B, "the name you give each element while you recount")},
     note="Bounds, then presence, then agreement. Recounting is expensive and is "
          "exactly what a ward is for.",
     mode=SPLIT, demo={"ok": "None", "nums": "[3, 1, 4, 1]",
                       "tally": "{3: 1, 1: 2, 4: 1}", "i": "0"},
     example={"ok": "ok", "i": "i", "seq": "nums", "book": "tally",
              "one": "1", "y": "b"},
     lands="ok",
     proves="0 <= {i} < len({seq}) and {seq}[{i}] in {book} "
            "and {book}[{seq}[{i}]] == sum({one} for {y} in {seq} if {y} == {seq}[{i}])",
     requires=("list",)),

_art("artificer", "coliseum", "THE TOP-K ENGINE",
     "{out} = sorted(set({seq}), "
     "key=lambda {x}: (-sum({one} for {y} in {seq} if {proof}), {x}))[:{k}]",
     holes={"proof": (_X, "what counts as another sighting"),
            "out": (_N, "where the shortlist lands"),
            "seq": (_E, "the sequence being ranked"),
            "x": (_B, "the name the key function gives its argument"),
            "one": (_L, "what each sighting is worth"),
            "y": (_B, "the name you give the inner element"),
            "k": (_N, "how many you keep")},
     note="Top-k by frequency, in one line, with the ties broken on purpose. It "
          "is the timed practical question and it is also the tool.",
     mode=TOOL, demo={"out": "[]", "nums": "[3, 1, 4, 1]", "k": "2"},
     example={"proof": "b == a and b > 0",
              "out": "out", "seq": "nums", "x": "a", "one": "1", "y": "b",
              "k": "k"},
     lands="out",
     proves="sorted(set({seq}), "
            "key=lambda {x}: (-sum({one} for {y} in {seq} if {proof}), {x}))[:{k}]",
     requires=("list",)),

_art("seer", "coliseum", "THE ONE THAT CAME BACK MOST",
     "{at} = max(set({seq}), "
     "key=lambda {x}: (sum({one} for {y} in {seq} if {proof}), -{seq}.index({x})))",
     holes={"proof": (_X, "what counts as another sighting"),
            "at": (_N, "where the value lands"),
            "seq": (_E, "the sequence being read"),
            "x": (_B, "the name the key function gives its argument"),
            "one": (_L, "what each sighting is worth"),
            "y": (_B, "the name you give the inner element")},
     note="Commonest, ties broken toward whichever appeared first. Negating the "
          "index is how you reverse half of a tuple key.",
     mode=MARK, demo={"hit": "None", "nums": "[3, 1, 4, 1]"},
     example={"proof": "b == a and b > 0",
              "at": "hit", "seq": "nums", "x": "a", "one": "1", "y": "b"},
     lands="at",
     proves="max(set({seq}), "
            "key=lambda {x}: (sum({one} for {y} in {seq} if {proof}), -{seq}.index({x})))",
     requires=("list",)),


ARTS: tuple = tuple(_CATALOGUE)
BY_ID: dict = {a.id: a for a in ARTS}
ART_IDS: frozenset = frozenset(BY_ID)
CLASS_IDS: tuple = tuple(sorted({a.class_id for a in ARTS}))


# ---------------------------------------------------------------------------
# 5. Registration
# ---------------------------------------------------------------------------
# Two registries, both by id, neither of them edited in place beyond one key.
#
#   incantation.BY_ID   so `render_template`, `cast`, `stats_for`,
#                       `record_cast` and `tier_for_move` work on an art line
#                       with nothing changed at the call site.
#   movesets.BY_ID      so `plan_move`, `resolve_move`, `castable`,
#                       `targets_for`, `scale_for`, `record` and `fx_for` work
#                       on an art move with nothing changed at the call site.
#
# What is deliberately NOT touched:
#
#   incantation.CATALOGUE   omitting the art lines is what stops
#                           `learn_from_clear()` handing one out for clearing
#                           content. An art is a sage or it is nothing.
#   movesets.CATALOGUE      and therefore `movesets.self_check()`,
#                           `fx_table()` and the rung-per-class accounting stay
#                           about the forty-two tree moves, which is what they
#                           are written about.
#   movesets.BY_CLASS       `at_rung(class_id, rung)` answers with the tree move
#                           for that rung. An art shares a rung with a tree move
#                           on purpose — it ages on the same curve — and must
#                           never be returned in its place.
#
# Both files are being rewritten alongside this one. If either rebuilds its
# dict, `ensure_registered()` puts the arts back; every public entry point calls
# it first and it costs one set comparison.

ART_MOVE_IDS: frozenset = frozenset(a.move_id for a in ARTS)

_ART_FLAVOUR = {
    "analyst": "Nobody wrote this down. The sage made you produce it twice and "
               "then stopped talking.",
    "berserker": "Taught in one sitting, by somebody who did not explain it "
                 "and did not repeat it.",
    "archivist": "A line kept by one person in one room, on the grounds that "
                 "the alternative was losing it.",
    "warden": "A ward from before the erasure, still holding, still checked "
              "every morning.",
    "artificer": "A tool rather than a blow. The sage was unmoved by the "
                 "distinction being pointed out.",
    "seer": "It finds the one that matters. That is all it does and it is "
            "enough.",
}


def _build_move(art) -> object:
    spec = movesets.SHAPES[CLASS_SHAPE[art.class_id]]
    spine = (art.inc.id,) + _companions(art.inc, art.chapter, spec.spine - 1)
    return movesets._move(
        art.move_id, art.name, art.class_id, art.rung, spec.id, spine,
        art.note, _ART_FLAVOUR[art.class_id])


def register(*, force: bool = False) -> dict:
    """Put the arts into both registries. Idempotent. Returns what was added."""
    lines = moves = 0
    for art in ARTS:
        if force or art.inc.id not in incantation.BY_ID:
            incantation.BY_ID[art.inc.id] = art.inc
            lines += 1
    for art in ARTS:
        if force or art.move_id not in movesets.BY_ID:
            movesets.BY_ID[art.move_id] = _build_move(art)
            moves += 1
    return {"lines": lines, "moves": moves}


def ensure_registered() -> None:
    if not (ART_IDS <= set(incantation.BY_ID)
            and ART_MOVE_IDS <= set(movesets.BY_ID)):
        register()


def is_art(identifier: str) -> bool:
    """True for an art's line id or an art move's id."""
    return identifier in ART_IDS or identifier in ART_MOVE_IDS


def get(art_id: str):
    return BY_ID.get(art_id)


def by_move(move_id: str):
    for art in ARTS:
        if art.move_id == move_id:
            return art
    return None


def for_class(class_id: str) -> list:
    """One class's whole ladder, in the order the sanctums are met."""
    return sorted((a for a in ARTS if a.class_id == class_id),
                  key=lambda a: a.rank)


def in_sanctum(sanctum_id: str) -> list:
    return [a for a in ARTS if a.sanctum == sanctum_id]


def taught_here(region_id: str, class_id: str):
    """The one art this region's sage teaches this class. `sages.py` asks this;
    there is never more than one answer, and never one for a region with no
    sanctum in it."""
    room = SANCTUM_BY_REGION.get(region_id)
    if room is None:
        return None
    for art in ARTS:
        if art.sanctum == room.id and art.class_id == class_id:
            return art
    return None


@contextmanager
def registered():
    """Register for the duration of a block, then put the catalogues back.

    For a caller that wants to MEASURE the arts without leaving them in
    `incantation.BY_ID` — a test, a report, a ranking table. The game calls
    `register()` once at wiring time and never unregisters.
    """
    had_lines = ART_IDS <= set(incantation.BY_ID)
    had_moves = ART_MOVE_IDS <= set(movesets.BY_ID)
    register()
    try:
        yield
    finally:
        if not (had_lines and had_moves):
            unregister()


# IMPORTING THIS MODULE REGISTERS NOTHING.
#
# It used to end with a bare `register()`, which wrote ninety-six lines into
# `incantation.BY_ID` and ninety-six moves into `movesets.BY_ID` as a side
# effect of the import statement. Two modules this pass does not own, mutated
# by an import, in a package whose test suite imports every module at discovery
# time: `tests/test_incantation.py::test_contract_mirror_has_not_drifted`
# asserts that `bestiary.EXPECTED_INCANTATIONS` and `incantation.BY_ID` hold the
# same ids, and it failed the moment anything imported this file.
#
# Registration is now something a caller ASKS for. `ensure_registered()` still
# does it lazily for anyone who touches a move, `registered()` does it and takes
# it back, and the wiring pass calls `register()` once, deliberately, where it
# can see it happen.


# ---------------------------------------------------------------------------
# 6. What a player carries
# ---------------------------------------------------------------------------
# An art is a move, so it lives in the movebook `movesets.new_book()` already
# defines, and it is acquired through `movesets.learn`, which also teaches the
# incantations its spine is spelled out of. There is no second book, no art slot
# limit, and no second statistics store: an art's cast statistics are in
# `state["moveset"]["stats"]` beside every other incantation's, and its groove
# is in `state["movebook"]["casts"]` beside every other move's.
#
# What IS kept here is the bookkeeping the movebook has no opinion about: which
# sanctums have been found, and when.

STATE_KEY = "arts"


def new_state() -> dict:
    """Flat, JSON-safe, small enough to sit in the save blob beside `movebook`."""
    return {"found": [], "cleared": [], "taught_at": {}}


def knows(state: dict, art_id: str, book: dict | None = None) -> bool:
    """Taught, which means the move is in the movebook. `found` is a mirror the
    quest log reads; the movebook is the truth."""
    if book is not None:
        art = BY_ID.get(art_id)
        return bool(art) and movesets.is_known(book, art.move_id)
    return art_id in (state or {}).get("found", [])


def grant(state: dict, book: dict, art_id: str, *, moveset: dict | None = None,
          at: float = 0.0) -> dict:
    """The sage has finished with you.

    The ONE road into an art. Calls `movesets.learn`, which puts the art move in
    the movebook and teaches the incantations its spine is made of — the art's
    own line and, for the wider shapes, the ordinary lines it is cast beside.
    Idempotent, because a re-attemptable gauntlet must be safe to re-clear.
    """
    ensure_registered()
    art = BY_ID.get(art_id)
    if art is None:
        return {"art": art_id, "taught": False, "reason": "no such art"}
    taught = movesets.learn(book, art.move_id, moveset)
    found = state.setdefault("found", [])
    already = art_id in found
    if not already:
        found.append(art_id)
        state.setdefault("taught_at", {})[art_id] = round(float(at), 2)
    cleared = state.setdefault("cleared", [])
    if art.sanctum not in cleared:
        cleared.append(art.sanctum)
    return {
        "art": art.id, "name": art.name, "move": art.move_id,
        "taught": bool(taught.get("learned")) or not already,
        "already": already,
        "incantations": list(taught.get("incantations", [])),
        "sanctum": art.sanctum, "rank": art.rank, "rung": art.rung,
        "shape": art.shape,
        "line": "%s. %s" % (art.name, art.note),
    }


def cleared_sanctums(state: dict) -> list:
    return [SANCTUM_BY_ID[s] for s in (state or {}).get("cleared", [])
            if s in SANCTUM_BY_ID]


def ladder_view(state: dict, class_id: str, book: dict | None = None) -> list:
    """The class ladder as the quest log should draw it: sixteen rooms, which
    you have found, and how many you have not. What is NOT here is where any of
    them are — that is `sages.py`'s to reveal, and it does not."""
    ensure_registered()
    reach = movesets.reach_of(book or {})
    out = []
    for art in for_class(class_id):
        held = knows(state, art.id, book)
        out.append({
            "rank": art.rank, "numeral": art.room.numeral,
            "sanctum": art.sanctum, "region": art.region,
            "region_name": world.REGION_BY_ID.get(art.region, {}).get("name", ""),
            "room": art.room.name if held else "",
            "art": art.id if held else "", "move": art.move_id if held else "",
            "name": art.name if held else "—",
            "known": held, "rung": art.rung, "shape": art.shape,
            "element": art.element if held else "",
            "fade": movesets.fade(art.rung, reach) if held else 0.0,
            "complexity": art.complexity().score if held else 0,
        })
    return out


# ---------------------------------------------------------------------------
# 7. Casting an art
# ---------------------------------------------------------------------------
# There is nothing to resolve here. An art move is a `movesets.Move` and
# `movesets.resolve_move` casts it: every line in its spine, in order, in one
# turn, each line graded through `incantation`'s three layers, each landing on
# its own merits. Miss one line and you keep what the others did; miss all of
# them and the turn is gone. That is the rule, it is already written, and this
# module does not get a second opinion about it.
#
# The two functions below are the only things an art adds: a demand picker that
# knows an art is class-locked and sealed out of a measured run, and the Seer's
# reading.


def demandable(book: dict, context, *, class_id: str = "", chapter: int = 99,
               sealed: bool = False) -> list:
    """The art moves this encounter may ask for.

    Taught, of the class being played, inside an open chapter, and castable
    against what is standing there — `movesets.castable` refuses a shape the
    field is too small to answer, before the turn is spent and at no cost.

    `sealed` is the caller's `finalexam.sealed(encounter, SEAL_CAPABILITY)`
    verdict, and True empties this list: an art is a class capability bought
    with a class's gauntlet, and the one measurement in this game is taken
    without it.
    """
    ensure_registered()
    if sealed:
        return []
    out = []
    for move in movesets.equipped(book or {}):
        art = by_move(move.id)
        if art is None:
            continue
        if class_id and art.class_id != class_id:
            continue
        ok, _ = movesets.castable(move, context, chapter=chapter)
        if ok:
            out.append(art)
    return out


def next_demand(book: dict, context, *, class_id: str = "", chapter: int = 99,
                sealed: bool = False, avoid: str = "", primary: str = "",
                rng=None) -> dict | None:
    """What this turn asks for, decided against the field as it stands NOW.

    Interleaving, the same rule `movesets` and `incantation` already follow:
    never the same move twice running while another is available, because
    discriminating between them is the skill. Repetition is the rest of it — an
    art stays in the rotation all fight, which is how it stops being a trophy.
    """
    pool = demandable(book, context, class_id=class_id, chapter=chapter,
                      sealed=sealed)
    if not pool:
        return None
    choices = [a for a in pool if a.move_id != avoid] or pool
    art = rng.choice(choices) if rng is not None else choices[0]
    targets = movesets.targets_for(art.move, context, primary=primary)
    return {
        "art": art.id, "move": art.move_id, "name": art.name,
        "shape": art.shape, "tactic": art.tactic, "spine": list(art.spine),
        "focus": art.cost, "suggested_target": targets[0] if targets else "",
        "would_paint": targets,
    }


def plan(art_id: str, context, *, book: dict | None = None,
         moveset: dict | None = None, skills: dict | None = None,
         primary: str = "", chapter: int = 99) -> dict:
    """Everything the client needs before a key is pressed.

    `movesets.plan_move` does the work — per spine step, the incantation, the
    scaffold tier it has earned, and the rendered ghost. This adds the things
    that make it look like an art rather than a tree move.
    """
    ensure_registered()
    art = BY_ID[art_id]
    view = movesets.plan_move(art.move, context, primary=primary, book=book,
                              moveset=moveset, skills=skills, chapter=chapter)
    view["art"] = art.to_dict(reach=movesets.reach_of(book or {}))
    view["secret"] = secret_marks(art)
    view["fx"] = fx(art, book=book)
    view["tactic"] = art.tactic
    return view


def reading(art_id: str, context, *, primary: str = "",
            sealed: bool = False) -> dict:
    """The Seer's one extra: the target's weakness family, read aloud.

    Information about the MONSTER, never about the answer — the same line the
    forge's techniques are allowed to stand on, and the reason this is not a
    damage bonus is that it is not a number. Empty for every other class.

    `sealed` is the caller's `finalexam.sealed(encounter, "WEAKNESS_MAP")`
    verdict and True empties this. What this function returns IS the weakness
    map: the enemy's weakness family and its resistances, in words. `demandable`
    already refuses to offer an art inside a measured run, so a sealed Seer
    cannot reach this by casting — but this is a public function with a monster
    in its arguments, and a capability that is only out of reach by accident is
    not sealed. The seal is asserted here as well, where the information is.
    """
    if sealed:
        return {}
    ensure_registered()
    art = BY_ID.get(art_id)
    if art is None or art.class_id != "seer":
        return {}
    targets = movesets.targets_for(art.move, context, primary=primary)
    enemy = context.enemy(targets[0]) if targets else None
    if enemy is None:
        return {}
    return {
        "target": enemy.name, "display": enemy.display,
        "weakness": enemy.weakness or "",
        "resists": list(enemy.resists or ()),
        "line": ("%s answers to %s." % (enemy.display, enemy.weakness)
                 if enemy.weakness else "%s has no soft place." % enemy.display),
    }


# ---------------------------------------------------------------------------
# 8. The graphics contract
# ---------------------------------------------------------------------------
# `movesets.fx_for` already produces the complete drawing order for a move, in
# the vocabulary `web/js/spellfx.js` and `web/js/battlescene.js` speak: `law`,
# `colour`, `power`, `scale`, `alpha`, `motes`, `debris`, `duration`,
# `impactAt`, `hold`, `shake`, `flash`, `wash`, `impactWhere`, `lanes`,
# `targets`, `sweep`, `rings`, `arc`, `strikes`. An art is a move, so it gets
# all of that for free and this module does not fork it.
#
# What is added is one block, `secret`, and a swapped identity. Nothing in the
# base dict is overwritten except `id`, `family` and `label`, so a renderer that
# has never heard of arts draws an art correctly and simply does not draw the
# secret part.
#
# WHAT MAKES A SECRET ART LOOK SECRET
# -----------------------------------
# Not "bigger" — bigger is what rung already means, and an art shares its rung
# with a tree move on purpose. Six marks, none of which any ordinary move uses,
# so the player learns the visual language once and then recognises an art
# across the room the first time somebody else casts one:
#
#   1. GHOST INK      the ghost line is drawn in the sanctum's ink instead of
#                     the usual grey #7a7a86. The line looks handwritten by
#                     whoever taught it, because it was.
#   2. SIGIL RING     the sanctum's glyph turns once, fully, BEFORE the input
#                     accepts a keystroke. It is the only input in the game the
#                     player waits a beat for, and the beat is the tell.
#   3. DESATURATION   the screen falls to 35% saturation for `hold_frames`
#                     before impact. Nothing else in this game desaturates.
#   4. THE BANNER     the art's name draws letter by letter in the sage's
#                     script, two frames a letter, in the sanctum's ink.
#   5. TWO-TONE HIT   the impact flash is the class element's key colour over
#                     the sanctum ink, in that order. Ordinary hits are one.
#   6. THE DUCK       the music drops 12 dB for 220 ms and comes back. Nothing
#                     else ducks it.
#
# Per-spine-step, one more thing: the art's OWN line is drawn with the six
# marks and the ordinary lines it is cast beside are not. A three-line Berserker
# storm therefore reads as one secret line and two familiar ones, which is
# exactly what it is.
#
# A FAILED cast gets none of it. A wrong art fizzles like any other wrong line,
# because a wasted turn must never be the best-looking thing on screen.

ORDINARY_GHOST_INK = "#7a7a86"
SECRET_DESATURATION = 0.35
SECRET_DUCK_DB, SECRET_DUCK_MS = -12, 220
SIGIL_RING_MS = 600
BANNER_FRAMES_PER_LETTER = 2


def secret_marks(art) -> dict:
    """The six marks, as numbers. Same for every art on purpose: the language is
    learned once. Only the ink, the sigil and the hold length vary."""
    art = BY_ID[art] if isinstance(art, str) else art
    room = art.room
    hold = 3 + art.rank // 4
    colour = movesets.FX_COLOUR.get(art.element,
                                    movesets.FX_COLOUR[elements.NEUTRAL])
    return {
        "ghost_ink": room.ink,
        "ordinary_ghost_ink": ORDINARY_GHOST_INK,
        "sigil_ring": {"glyph": room.sigil, "count": min(4, 1 + art.rank // 5),
                       "turns": 1, "ms": SIGIL_RING_MS,
                       "blocks_input_until_done": True},
        "desaturate": {"to": SECRET_DESATURATION, "frames": hold},
        "banner": {"text": art.name, "font": "sage", "colour": room.ink,
                   "frames_per_letter": BANNER_FRAMES_PER_LETTER},
        "two_tone_impact": [colour["key"], room.ink],
        "duck_music": {"db": SECRET_DUCK_DB, "ms": SECRET_DUCK_MS},
        "hold_frames": hold,
        "room": {"id": room.id, "name": room.name, "numeral": room.numeral,
                 "ink": room.ink, "sigil": room.sigil,
                 "element": room.element},
        # which steps of the spine are the secret one
        "secret_steps": [0],
        "ordinary_steps": list(range(1, len(art.spine))),
        "note": "Marks 1-6 belong to step 0 only. The other steps are ordinary "
                "lines and must look ordinary.",
    }


def fx(art, result=None, *, book: dict | None = None, score: int | None = None,
       targets: list | None = None, reduced_motion: bool = False) -> dict:
    """The complete per-cast drawing order for an art. One dict, nothing else.

    Callable without a result, so the movebook can preview an art at the
    strength it would currently be cast at.
    """
    ensure_registered()
    art = BY_ID[art] if isinstance(art, str) else art
    base = movesets.fx_for(art.move, result, reach=movesets.reach_of(book or {}),
                           score=score, targets=targets,
                           reduced_motion=reduced_motion)
    base["id"] = art.id
    base["family"] = "art"
    base["label"] = art.name
    base["art"] = art.id
    base["rank"] = art.rank
    base["numeral"] = art.room.numeral
    base["sanctum"] = art.sanctum
    base["tactic"] = art.tactic
    base["secret"] = secret_marks(art)
    base["on_fail"] = {"effect": "fizzle", "secret": None,
                       "note": "A failed art gets none of the six marks."}
    return base


def fx_table(*, reduced_motion: bool = False) -> list:
    """All ninety-six drawing orders, for whoever writes the effects."""
    return [fx(a, reduced_motion=reduced_motion) for a in ARTS]


# ---------------------------------------------------------------------------
# 9. Three damage systems, one order
# ---------------------------------------------------------------------------
# The brief's worry, stated plainly: complexity damage, elemental affinity and
# weapon techniques must not multiply into nonsense. They do not, and this is
# exactly why.
#
#   1. THE TYPING SETS THE PAYLOAD. `incantation.measure_complexity` reads the
#      line the player wrote — constructs, authored holes, nesting, form,
#      composition — and `_damage_for` turns its weight into damage. For an art
#      this is the WHOLE spine. `Incantation.power` is a floor, and an art's
#      floor is set from its own tier-0 measurement, so it is exactly
#      non-binding: there is no authored number here that can be raised.
#
#   2. THE SHAPE DIVIDES IT. `movesets.SHAPES[shape].share(i)` splits the
#      payload across targets, and those fractions are chosen so an area move is
#      worth between 0.87 and 1.35 of casting SINGLE once per monster over the
#      same number of turns. AoE buys tempo, not output. An art does not get its
#      own falloff table.
#
#   3. THE MOVESET MULTIPLIERS. Rank fade, groove, variety, first-cast, and the
#      dual-class penalty — `movesets.scale_for`, applied multiplicatively to
#      whatever the typing earned. An art is subject to every one of them,
#      including the fade curve: it shares a rung with a tree move and it ages
#      on the same line. Their own invariant holds for arts too — the span the
#      typing can move (5.45x) is wider than the span everything else can move
#      (4.60x), so writing better Python is always the bigger lever.
#
#   4. THE ELEMENT IS THE ONE MATCHUP TERM. Each strike's base goes through
#      `elements.resolve_damage(base, move.element, defender)` exactly once, in
#      the engine's `deliver`. An art's element is `movesets.CLASS_ELEMENT` —
#      the class's, not a private one — so an art carries the same affinity the
#      player's ordinary moves already carry and there is nothing new to reason
#      about. The sanctum's own region affinity is the COLOUR OF THE ROOM and
#      the reason that sage settled there; it is never multiplied by anything.
#
#   5. THE WEAKNESS TABLE DOES NOT APPLY. Every art line's `family` is
#      `art_<class>`, which no entry in `incantation.ARCHETYPES` names as a
#      weakness or a resistance. An art is never doubled for striking true and
#      never halved for being shrugged off. It lands for what it is.
#      `self_check()` proves it, and it is the cheapest thing that keeps the
#      multiplication from compounding: the ordinary lines in an art's spine
#      still ride the weakness table, the art's own line does not.
#
#   6. THE FORGE NEVER TOUCHES IT. Not one key across `forge.py`'s nine rungs
#      multiplies damage — they buy probes, clocks, wards, traces and gold. A
#      blade at rung nine and a blade at rung one cast the same art for the same
#      number. See `weapon_note()`.

SEAL_CAPABILITY = "BUILD"     # finalexam.sealed(encounter, SEAL_CAPABILITY)

ORDER_OF_OPERATIONS: tuple = (
    "1. movesets.resolve_move(art.move_id, answers, ctx, ...) casts every line "
    "of the spine. Each line's base is incantation.measure_complexity of what "
    "was typed. No discovery term exists at any point.",
    "2. movesets.SHAPES[shape].share(i) divides the payload across targets.",
    "3. movesets.scale_for(book, move_id) multiplies fade, groove, variety and "
    "first-cast into it. Arts are subject to all of them.",
    "4. deliver(): elements.resolve_damage(base, move.element, "
    "elements.Defender.for_enemy(enemy, region)) -> apply DamageResult.damage. "
    "This is the ONLY elemental multiplication, and there is one of it.",
    "5. forge techniques: none. No rung multiplies damage; nothing to fold in.",
    "6. finalexam: if sealed(enc, 'BUILD'), arts.demandable() returns [] and "
    "resolve_damage strips the element anyway. The exam is fought on typing.",
)


def through_elements(base: int, art, enemy, region_id: str = "", *,
                     attacker_statuses=None, roll: float = 1.0,
                     build_sealed: bool = False):
    """Step 4, offered as one call so a caller cannot get the order wrong.

    Returns an `elements.DamageResult`. Pure: it neither reads nor writes the
    enemy's hit points, so a caller that only wants a preview can throw the
    answer away. This is what `engine._incant_deliver` should be doing for an
    art, and it is the same thing it already does for an ordinary move.
    """
    art = BY_ID[art] if isinstance(art, str) else art
    defender = elements.Defender.for_enemy(enemy, region_id)
    return elements.resolve_damage(
        max(0, int(base)), art.element, defender,
        attacker_statuses=attacker_statuses, roll=roll,
        build_sealed=build_sealed)


def weapon_note() -> str:
    return (
        "A forged blade changes what you walk in knowing and what the fight "
        "costs you. It does not change what an art hits for. There is no rung, "
        "no technique and no rank of a technique in forge.py that multiplies "
        "damage, so there is nothing to fold in and nothing to cap. If one is "
        "ever added it must go inside elements.resolve_damage, not here and not "
        "in movesets, or the systems start compounding and the argument this "
        "file is built on stops being true.")


# ---------------------------------------------------------------------------
# 10. The ranking table
# ---------------------------------------------------------------------------
# The honesty mechanism, printable. Two bars, both measured on the engine's own
# ruler at the same scaffold tier, and both asserted by `self_check()`.
#
#   LINE BAR  the art's own line must demand more Python than the HARDEST
#             ordinary line available in that area. Not the median, the hardest
#             — which for every sanctum is SIFT, the filtered comprehension from
#             chapter two, the one ordinary incantation in the game that is
#             already very nearly an art. Margin 1.10.
#
#   MOVE BAR  the art move's payload must beat the strongest ordinary move
#             available in that area of the SAME SHAPE. Same shape, because
#             comparing a three-line storm to a one-line strike would be
#             comparing turn lengths rather than difficulty. Margin 1.10.
#             Where an area has no ordinary move of that shape yet, the
#             comparison falls back to the strongest of any shape and the row
#             says so.
#
# The move bar reduces to the line bar by construction and that is deliberate:
# an art move's spine is the art's line plus the HARDEST ordinary lines in the
# area, so it can only beat the strongest ordinary move if the art's own line is
# the harder line. Nothing is won by the art having more lines.

LINE_MARGIN = 1.10
MOVE_MARGIN = 1.10


def ranking_row(art, *, tier: int = ART_TIER_REFERENCE) -> dict:
    ensure_registered()
    art = BY_ID[art] if isinstance(art, str) else art
    mine = art.complexity(tier=tier)
    line_best, line_raw = ordinary_line_ceiling(art.chapter, tier=tier)
    same_shape, same_pay = ordinary_move_ceiling(art.chapter, shape=art.shape,
                                                 tier=tier)
    fallback = False
    if same_shape is None:
        same_shape, same_pay = ordinary_move_ceiling(art.chapter, tier=tier)
        fallback = True
    payload = art.payload(tier=tier)
    return {
        "art": art.id, "name": art.name, "class": art.class_id,
        "rank": art.rank, "sanctum": art.sanctum, "region": art.region,
        "chapter": art.chapter, "shape": art.shape, "rung": art.rung,
        "element": art.element, "focus": art.cost,
        # the line
        "raw": mine.raw, "score": mine.score, "weight": mine.weight,
        "depth": mine.depth, "form": mine.form, "composed": mine.composed,
        "holes_filled": mine.holes_filled,
        "families": list(mine.families),
        "ordinary_line": line_best.id if line_best else "",
        "ordinary_line_raw": line_raw,
        "line_ratio": round(mine.raw / line_raw, 2) if line_raw else 0.0,
        "clears_line_bar": bool(line_raw) and mine.raw >= line_raw * LINE_MARGIN,
        # the move
        "spine": list(art.spine),
        "payload": payload,
        "ordinary_move": same_shape.id if same_shape else "",
        "ordinary_move_shape": same_shape.shape if same_shape else "",
        "ordinary_move_payload": same_pay,
        "shape_fallback": fallback,
        "move_ratio": round(payload / same_pay, 2) if same_pay else 0.0,
        "clears_move_bar": bool(same_pay) and payload >= same_pay * MOVE_MARGIN,
    }


def ranking_table(*, tier: int = ART_TIER_REFERENCE) -> list:
    """The whole table. Self-restoring: a report does not leave the arts in
    `incantation.BY_ID` behind it."""
    with registered():
        return [ranking_row(a, tier=tier)
                for a in sorted(ARTS, key=lambda a: (a.rank, a.class_id))]


def ranking_report(*, sanctum: str = "", class_id: str = "",
                   tier: int = ART_TIER_REFERENCE) -> str:
    """The table as text, for the acceptance tests and for anyone who doubts it."""
    rows = ranking_table(tier=tier)
    if sanctum:
        rows = [r for r in rows if r["sanctum"] == sanctum]
    if class_id:
        rows = [r for r in rows if r["class"] == class_id]
    out = ["ARTS vs ORDINARY — incantation.measure_complexity, tier %d "
           "(%s)" % (tier, incantation.TIER_NAMES[tier]),
           "%-24s %-10s %-6s %6s %6s %5s %7s %7s %5s"
           % ("ART", "SANCTUM", "SHAPE", "RAW", "ORD", "x", "PAYLOAD", "ORD", "x"),
           "-" * 96]
    for row in rows:
        out.append("%-24s %-10s %-6s %6.2f %6.2f %5.2f %7.1f %7.1f %5.2f%s"
                   % (row["art"], row["sanctum"], row["shape"][:6], row["raw"],
                      row["ordinary_line_raw"], row["line_ratio"],
                      row["payload"], row["ordinary_move_payload"],
                      row["move_ratio"],
                      "" if row["clears_line_bar"] and row["clears_move_bar"]
                      else "  <-- UNDER BAR"))
    if rows:
        out.append("-" * 96)
        out.append("%d arts | line ratio %.2f-%.2f (bar %.2f) | move ratio "
                   "%.2f-%.2f (bar %.2f) | hardest ordinary line: %s"
                   % (len(rows),
                      min(r["line_ratio"] for r in rows),
                      max(r["line_ratio"] for r in rows), LINE_MARGIN,
                      min(r["move_ratio"] for r in rows),
                      max(r["move_ratio"] for r in rows), MOVE_MARGIN,
                      rows[0]["ordinary_line"]))
    return "\n".join(out)


def tier_report(art_id: str) -> str:
    """One art across all four scaffold tiers: the repetition argument, in
    numbers. Nothing else in this file is allowed to move damage this much."""
    with registered():
        return _tier_report(art_id)


def _tier_report(art_id: str) -> str:
    art = BY_ID[art_id]
    out = ["%s — %s, %s" % (art.name, art.room.name, art.shape),
           "%-10s %6s %6s %7s %8s" % ("TIER", "RAW", "SCORE", "WEIGHT", "PAYLOAD")]
    for tier in range(incantation.MAX_TIER + 1):
        measured = art.complexity(tier=tier)
        out.append("%-10s %6.2f %6d %7.3f %8.1f"
                   % (incantation.TIER_NAMES[tier], measured.raw, measured.score,
                      measured.weight, art.payload(tier=tier)))
    first = art.payload(tier=0)
    last = art.payload(tier=incantation.MAX_TIER)
    out.append("Drilling it to RECALLED is worth %.2fx. Nothing else in the "
               "game moves one move that far." % (last / max(1.0, first)))
    return "\n".join(out)


def saturation_report(*, tier: int | None = None) -> dict:
    """How many arts the ruler can no longer tell apart, per scaffold tier.

    THIS IS THE ONE NUMBER THAT DECIDES WHETHER THIS FILE'S ARGUMENT SURVIVES
    CONTACT WITH PLAY, AND IT IS NOT GOOD.

    `incantation.measure_complexity` clamps: `score = min(100, raw * 100 /
    SCORE_FULL)` with `SCORE_FULL = 40.0`, and `weight` is a straight line from
    that clamped score. Every cast above raw 40 therefore measures identically
    and does identical damage, no matter how much more Python it demanded.

    The ordinary catalogue never reaches the clamp — its hardest line, SIFT, is
    raw 25.75 at PROMPTED and 34.00 at RECALLED, so the sixty-six ordinary lines
    live entirely inside the ruler and discriminate properly all the way up. The
    arts do not. At PROMPTED forty of ninety-six are already pinned at the
    ceiling; at RECALLED — the tier a player who has actually drilled an art
    casts it at, which is the steady state this whole system is aiming for — ALL
    NINETY-SIX ARE, and THE INDEX OF EVERY FRAME hits for exactly what the
    shallowest art in the Village hits for.

    The usable band above the hardest ordinary line is 34.00 to 40.00 at
    RECALLED: six raw points, fifteen per cent of the scale, for sixteen ranks
    times six classes. A secret tier cannot be expressed in it, and no amount of
    re-authoring in this file can create room that the ruler does not have. The
    arts are not too hard; the ruler is too short.

    THE FIX IS ONE CONSTANT IN A FILE THIS PASS DOES NOT OWN. Raising
    `incantation.SCORE_FULL` from 40.0 to about 85.0 puts SIFT at RECALLED on 40
    of 100 and the hardest art on 94, with nothing clamped and every rung
    distinct. It rescales every ordinary line by the same factor, so their
    ranking against each other is untouched, and `DAMAGE_UNIT` has to come up
    with it to keep an ordinary cast worth what it is worth today. That is a
    combat-calibration decision and it belongs to whoever owns `incantation.py`,
    which is why this is a report and not an edit. `handover()` carries it.
    """
    with registered():
        tiers = ([int(tier)] if tier is not None
                 else list(range(incantation.MAX_TIER + 1)))
        rows = []
        for step in tiers:
            arts = [measure(a, tier=step) for a in ARTS]
            ordinary = [measure_line(i, tier=step) for i in incantation.CATALOGUE]
            pinned = [a for a in arts if a.score >= 100]
            rows.append({
                "tier": step,
                "tier_name": incantation.TIER_NAMES[step],
                "arts_at_the_ceiling": len(pinned),
                "arts": len(arts),
                "art_raw_mean": round(sum(a.raw for a in arts) / len(arts), 2),
                "art_raw_max": round(max(a.raw for a in arts), 2),
                "distinct_art_weights": len({a.weight for a in arts}),
                "ordinary_at_the_ceiling": sum(1 for o in ordinary
                                               if o.score >= 100),
                "hardest_ordinary_raw": round(max(o.raw for o in ordinary), 2),
                "headroom": round(incantation.SCORE_FULL
                                  - max(o.raw for o in ordinary), 2),
            })
    top = rows[-1]
    # A ladder of ninety-six arts that the ruler renders as a handful of
    # distinct damage numbers is not a ladder. Five is generous.
    collapsed = top["distinct_art_weights"] <= 5
    return {
        "score_full": incantation.SCORE_FULL,
        "weight_range": [incantation.WEIGHT_MIN, incantation.WEIGHT_MAX],
        "by_tier": rows,
        "distinct_damage_numbers_at_recalled": top["distinct_art_weights"],
        "collapsed_at_recalled": collapsed,
        "usable_band_at_recalled": [top["hardest_ordinary_raw"],
                                    incantation.SCORE_FULL],
        "verdict": (
            "BROKEN: at %s the ninety-six arts resolve to %d distinct damage "
            "numbers (%d of %d pinned at the ceiling). The ruler clamps at raw "
            "%.1f and the hardest ordinary line is already at %.2f, leaving "
            "%.2f raw points for the whole secret catalogue."
            % (top["tier_name"], top["distinct_art_weights"],
               top["arts_at_the_ceiling"], top["arts"], incantation.SCORE_FULL,
               top["hardest_ordinary_raw"], top["headroom"])
            if collapsed else
            "OK: the arts resolve to %d distinct damage numbers at %s."
            % (top["distinct_art_weights"], top["tier_name"])),
        "edit": "raise incantation.SCORE_FULL from %.1f to about 85.0 and bring "
                "DAMAGE_UNIT up with it" % incantation.SCORE_FULL,
    }


# ---------------------------------------------------------------------------
# 11. The proofs
# ---------------------------------------------------------------------------

# Vocabulary an art may never use about itself. Borrowed, deliberately, from the
# instinct `forge.validate()` is built on: the place a rule gets broken is the
# place somebody was proud of what they built.
_GIVEAWAY = (
    "reveals the answer", "gives you the answer", "solves it for you",
    "without solving", "the optimal approach", "tells you which pattern",
    "automatically solves", "skips the",
)


def self_test_all() -> dict:
    """Cast all ninety-six lines through the real sandbox, all three layers.

    Slow on purpose: nothing is mocked. If an art cannot cast itself with its
    own worked example it has no business being taught to anybody.

    Self-restoring, like every other proof in this section.
    """
    with registered():
        return _self_test_all()


def _self_test_all() -> dict:
    failures = {}
    for art in ARTS:
        ok, result = incantation.self_test(art.inc, explain=True)
        if not ok:
            failures[art.id] = "%s: %s %s" % (result.layer, result.teaching,
                                              result.detail)
    return {"total": len(ARTS), "failed": len(failures), "detail": failures}


def self_check() -> dict:
    """Every claim this module makes about itself, checked. Static only — no
    sandbox — so the acceptance tests can run it in milliseconds.

    Runs inside `registered()` so that asking this module whether it is honest
    does not leave ninety-six lines in `incantation.BY_ID` behind it.
    """
    with registered():
        return _self_check()


def _self_check() -> dict:
    problems = []

    def fail(message):
        problems.append(message)

    rows = ranking_table()

    # 1. THE CLAIM. Every art demands more Python than the hardest ordinary
    #    line available in its area, on the engine's own ruler, at the same tier.
    for row in rows:
        if not row["clears_line_bar"]:
            fail("%s: raw %.2f does not clear %.2f x %.2f (%s). Make the art "
                 "harder, not stronger." % (row["art"], row["raw"], LINE_MARGIN,
                                            row["ordinary_line_raw"],
                                            row["ordinary_line"]))
        if not row["clears_move_bar"]:
            fail("%s: payload %.1f does not clear %.2f x %.1f (%s)"
                 % (row["art"], row["payload"], MOVE_MARGIN,
                    row["ordinary_move_payload"], row["ordinary_move"]))

    # 2. No authored number decides an art's damage. `power` is the floor the
    #    engine already treats it as, and it must never bind above tier 0.
    for art in ARTS:
        expected = power_floor(art.inc)
        if art.inc.power != expected:
            fail("%s: power %d is not its measured floor %d"
                 % (art.id, art.inc.power, expected))
        floor = art.inc.power * incantation.POWER_FLOOR_SHARE
        for tier in range(1, incantation.MAX_TIER + 1):
            spine_term = (incantation.DAMAGE_UNIT
                          * art.complexity(tier=tier).weight)
            if floor > spine_term + 1e-9:
                fail("%s: the power floor binds at tier %d, so the number is "
                     "deciding the damage instead of the typing"
                     % (art.id, tier))
        if art.inc.cost != cost_for(art.complexity().raw):
            fail("%s: focus cost is not derived from the measurement" % art.id)
        if art.inc.par_seconds != par_for(art.complexity().raw):
            fail("%s: par is not derived from the measurement" % art.id)

    # 3. Repetition is the biggest lever there is on an art.
    for art in ARTS:
        cold = art.payload(tier=0)
        drilled = art.payload(tier=incantation.MAX_TIER)
        if drilled <= cold * 1.5:
            fail("%s: drilling it to RECALLED is worth only %.2fx; repetition "
                 "has to be the largest lever in the game" % (art.id, drilled / max(1.0, cold)))
    # and larger than anything movesets can do on its own.
    typing_span = incantation.WEIGHT_MAX / incantation.WEIGHT_MIN
    module_span = ((1.0 / movesets.FADE_FLOOR) * movesets.groove(99)
                   * (1.0 + movesets.VARIETY_BONUS) * (1.0 + movesets.FRESH_BONUS))
    if typing_span <= module_span:
        fail("the typing span (%.2fx) no longer beats what the multipliers can "
             "do (%.2fx); a player would be paid to reach for a fresh move "
             "instead of a better line" % (typing_span, module_span))

    # 4. The catalogue's shape.
    for room in SANCTUMS:
        here = in_sanctum(room.id)
        if len(here) != len(CLASS_IDS):
            fail("%s: %d arts for %d classes" % (room.id, len(here), len(CLASS_IDS)))
        if len({a.class_id for a in here}) != len(here):
            fail("%s: two arts for one class" % room.id)
    for class_id in CLASS_IDS:
        ladder = for_class(class_id)
        if len(ladder) != len(SANCTUMS):
            fail("%s: %d arts for %d sanctums" % (class_id, len(ladder), len(SANCTUMS)))
        if len({a.shape for a in ladder}) != 1:
            fail("%s: casts in more than one shape; a class fantasy is one way"
                 % class_id)
        ranks = sorted(a.rank for a in ladder)
        if ranks != list(range(1, len(SANCTUMS) + 1)):
            fail("%s: its ladder has holes in it" % class_id)
    if {a.shape for a in ARTS} != set(movesets.SHAPE_IDS):
        fail("not every shape in movesets is used by some class's arts")
    if set(CLASS_IDS) != set(movesets.CLASS_IDS):
        fail("the classes with arts are not the classes with movesets")

    # 5. An art is never handed out by clearing content, and never by a tree.
    leaked = ART_IDS & {i.id for i in incantation.CATALOGUE}
    if leaked:
        fail("in incantation.CATALOGUE, so learn_from_clear could hand them "
             "out: %s" % ", ".join(sorted(leaked)))
    leaked = ART_MOVE_IDS & {m.id for m in movesets.CATALOGUE}
    if leaked:
        fail("in movesets.CATALOGUE, so a skill tree node could grant them: %s"
             % ", ".join(sorted(leaked)))
    for class_id, moves in movesets.BY_CLASS.items():
        if ART_MOVE_IDS & {m.id for m in moves}:
            fail("%s: an art is in movesets.BY_CLASS, so at_rung() could "
                 "return it instead of the tree move" % class_id)
    if not ART_IDS <= set(incantation.BY_ID):
        fail("art lines are not registered; incantation.cast cannot find them")
    if not ART_MOVE_IDS <= set(movesets.BY_ID):
        fail("art moves are not registered; movesets.resolve_move cannot find them")

    # 6. No art line rides the weakness table, so nothing is multiplied twice.
    art_families = {a.inc.family for a in ARTS}
    for key, spec in incantation.ARCHETYPES.items():
        if spec.get("weakness") in art_families:
            fail("%s is weak to an art family; that is a second multiplier" % key)
        if art_families & set(spec.get("resists") or ()):
            fail("%s resists an art family; that is a second multiplier" % key)

    # 7. One enemy hole per art line, so the target is never ambiguous, and the
    #    spine an art is cast beside can actually stand on the same field.
    for art in ARTS:
        enemies = [h for h in art.holes if h.kind == incantation.ENEMY]
        if len(enemies) != 1:
            fail("%s: %d enemy holes; the target is ambiguous" % (art.id, len(enemies)))
        move = art.move
        if move.spine[0] != art.inc.id:
            fail("%s: its own line is not the first step of its move" % art.id)
        if len(move.spine) != movesets.SHAPES[art.shape].spine:
            fail("%s: spine length disagrees with its shape" % art.id)
        if move.chapter != art.chapter:
            fail("%s: the move opens at chapter %d and the art at %d; a "
                 "companion line is out of the area"
                 % (art.id, move.chapter, art.chapter))
        for inc_id in move.spine[1:]:
            companion = incantation.BY_ID[inc_id]
            if not set(companion.requires) <= set(art.inc.requires):
                fail("%s: %s needs a kind the art does not, so the move can be "
                     "demanded on a field it cannot land on" % (art.id, inc_id))
            if inc_id in ART_IDS:
                fail("%s: casts another art as a companion line" % art.id)

    # 8. Difficulty follows the area, and the area agrees with the curriculum.
    for art in ARTS:
        if art.chapter != REGION_CHAPTER[art.region]:
            fail("%s: chapter does not match its region" % art.id)
        if art.rung != rung_for(art.rank):
            fail("%s: rung does not follow its rank" % art.id)
    try:
        from . import curriculum
        stated = {}
        for index, chapter in enumerate(curriculum.CHAPTERS):
            stated.setdefault(chapter.region, index)
        for region, chapter in stated.items():
            mine = REGION_CHAPTER.get(region)
            if mine is not None and mine != chapter:
                fail("REGION_CHAPTER says %s is chapter %d; curriculum says %d"
                     % (region, mine, chapter))
    except Exception as exc:                      # pragma: no cover
        fail("could not check REGION_CHAPTER against curriculum: %s" % exc)

    # 9. Every sanctum is a real place with a real colour, and the ranks are a
    #    ladder rather than a heap.
    for room in SANCTUMS:
        if room.region not in world.REGION_BY_ID:
            fail("%s: no such region" % room.id)
        if room.element not in elements.ALL_AFFINITIES:
            fail("%s: no such element" % room.id)
    if sorted(s.rank for s in SANCTUMS) != list(range(1, len(SANCTUMS) + 1)):
        fail("the sanctum ranks are not a ladder")
    if len({s.region for s in SANCTUMS}) != len(SANCTUMS):
        fail("two sanctums in one region")

    # 10. The answer rule, and the voice.
    for art in ARTS:
        blob = ("%s %s %s" % (art.name, art.note, art.tactic)).lower()
        for phrase in _GIVEAWAY:
            if phrase in blob:
                fail("%s: says %r, which is the wrong side of the answer rule"
                     % (art.id, phrase))
        if "!" in art.name or "!" in art.note:
            fail("%s: exclamation mark" % art.id)

    # 11. Failing an art costs the turn and nothing else.
    for key, value in incantation._FAIL_DELTA.items():
        if value < -2.0:
            fail("incantation._FAIL_DELTA[%r] is %.2f, which is more than a "
                 "wasted turn" % (key, value))

    # 12. Nothing about damage or cost may read player progress.
    import inspect
    for func in (power_floor,):
        if set(inspect.signature(func).parameters) - {"art_inc"}:
            fail("%s reads more than the line" % func.__name__)
    for func in (cost_for, par_for):
        if set(inspect.signature(func).parameters) - {"raw"}:
            fail("%s reads more than the measurement" % func.__name__)

    line_ratios = [r["line_ratio"] for r in rows]
    move_ratios = [r["move_ratio"] for r in rows]
    return {
        "ok": not problems,
        "arts": len(ARTS), "sanctums": len(SANCTUMS), "classes": len(CLASS_IDS),
        "shapes": {s: sum(1 for a in ARTS if a.shape == s)
                   for s in movesets.SHAPE_IDS},
        "hardest_ordinary_line": rows[0]["ordinary_line"] if rows else "",
        "hardest_ordinary_raw": rows[0]["ordinary_line_raw"] if rows else 0.0,
        "raw_min": round(min(r["raw"] for r in rows), 2) if rows else 0.0,
        "raw_max": round(max(r["raw"] for r in rows), 2) if rows else 0.0,
        "line_ratio_min": round(min(line_ratios), 2) if rows else 0.0,
        "line_ratio_max": round(max(line_ratios), 2) if rows else 0.0,
        "move_ratio_min": round(min(move_ratios), 2) if rows else 0.0,
        "move_ratio_max": round(max(move_ratios), 2) if rows else 0.0,
        "line_margin": LINE_MARGIN, "move_margin": MOVE_MARGIN,
        "typing_span": round(typing_span, 2),
        "multiplier_span": round(module_span, 2),
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# 12. Integration contract
# ---------------------------------------------------------------------------
# Another agent wires this up. Nothing below is a suggestion.
#
# STATE, two keys, both flat and JSON-safe
#   state["movebook"] = movesets.new_book(state["class"]["class"])
#       already required by movesets.py. An art lives here like any other move:
#       "known", "equipped", "casts", "landed", "last". There is no art slot
#       limit and no second book.
#   state["arts"] = arts.new_state()
#       {"found": [art_id...], "cleared": [sanctum_id...],
#        "taught_at": {art_id: epoch_seconds}}
#       Bookkeeping only. The movebook is the truth about what can be cast.
#   A save from an older build is repaired with
#       state.setdefault("arts", arts.new_state())
#
# WHAT sages.py CALLS
#   arts.taught_here(region_id, class_id) -> Art | None
#       the one art this region's sage teaches this class. None for a region
#       with no sanctum. Use it to author the trial's reward text.
#   arts.SANCTUMS, arts.SANCTUM_BY_REGION, Sanctum.where / .name / .ink / .sigil
#       where the room is and what it looks like. The sage, the trial and the
#       dialogue are yours; the difficulty of the trial is Sanctum.chapter.
#   arts.grant(state["arts"], state["movebook"], art.id,
#              moveset=state["moveset"], at=time.time()) -> dict
#       the ONLY road into an art. Calls movesets.learn, which also teaches the
#       incantations in the move's spine. Idempotent, so a re-attemptable
#       gauntlet is safe to re-clear, and "already" in the returned dict says so.
#
# WHAT engine.py CALLS, per turn
#   1. demand:  arts.next_demand(state["movebook"], ctx, class_id=...,
#                   chapter=curriculum.frontier(self.skills),
#                   sealed=finalexam.sealed(enc, arts.SEAL_CAPABILITY),
#                   avoid=<last move id>, primary=<clicked enemy>, rng=rng)
#               -> {"art", "move", "name", "shape", "spine", "focus",
#                   "suggested_target", "would_paint"} or None.
#   2. render:  arts.plan(art_id, ctx, book=state["movebook"],
#                         moveset=state["moveset"], skills=self.skills,
#                         primary=..., chapter=...)
#               -> movesets.plan_move's payload plus "art", "secret", "fx",
#                  "tactic". Send it to the client as-is.
#   3. cast:    movesets.resolve_move(art.move_id, [answers_per_line], ctx,
#                   book=state["movebook"], moveset=state["moveset"],
#                   skills=self.skills, primary=..., streak=combo,
#                   timed=(mode == MODE_INTERVIEW), chapter=...,
#                   deliver=self._incant_deliver)
#               There is no arts.resolve(). An art move IS a movesets move and
#               resolving it a second way would be a second combat system.
#   4. deliver: unchanged. `_incant_deliver` runs each base through
#               elements.resolve_damage with move.element — arts.through_elements
#               is that call, spelled out, if you want it named.
#   5. after:   movesets.record(state["movebook"], result)
#               incantation.record_cast(state["moveset"], CastResult) per step
#               fold result.skill_deltas into state["skills"] as usual
#               if art.class_id == "seer":
#                   payload["reading"] = arts.reading(art.id, ctx, primary=...)
#               — information about the monster, never about the answer, and
#               empty for every other class.
#   6. fx:      result.fx goes to the client untouched; arts.fx(art, result,
#               book=...) is the same dict with the six secret marks added and
#               the identity swapped. arts.fx_table() is the ninety-six-row
#               brief for whoever writes the effects in web/js/spellfx.js.
#
# WHAT THE EXAM DOES
#   finalexam.sealed(encounter, arts.SEAL_CAPABILITY) — "BUILD" — is True inside
#   a measured run, and arts.demandable() returns [] for it. An art is a class
#   capability bought with a class's gauntlet, and the one measurement in this
#   game is taken without it. No second isolation mechanism is needed.
#
# WHAT NOBODY CALLS
#   Nothing here mutates incantation.CATALOGUE, movesets.CATALOGUE,
#   movesets.BY_CLASS, classes.py, world.py or curriculum.py. The only mutations
#   this module performs on another module are two registrations by id, at
#   import, both idempotent:
#       incantation.BY_ID[art.inc.id] = art.inc
#       movesets.BY_ID[art.move_id]   = <the art move>
#   `arts.ensure_registered()` repairs both if either dict is rebuilt.


# ---------------------------------------------------------------------------
# 13. Hand-off: what this module needs from files it does not own
# ---------------------------------------------------------------------------
# Four things, all small, all stated rather than assumed. `handover()` returns
# them as data so a wiring pass can work through the list instead of finding
# them one failure at a time.
#
# 1. THE BESTIARY MIRROR TEST WILL FAIL THE DAY THIS IS IMPORTED.
#    `tests/test_incantation.py::test_contract_mirror_has_not_drifted` asserts
#        set(bestiary.EXPECTED_INCANTATIONS) == set(incantation.BY_ID)
#    and this module adds ninety-six ids to that dict at import. The assertion
#    is right to exist — it is what keeps the bestiary's string references
#    honest — and it wants one word:
#        set(bestiary.EXPECTED_INCANTATIONS) == set(incantation.BY_ID) - arts.ART_IDS
#    Nothing else in the test changes. `arts.unregister()` is provided for a
#    test that would rather put the catalogue back than special-case it.
#
# 2. THERE ARE TWO ART CATALOGUES AND ONLY ONE SHOULD SHIP.
#    `gauntlet/sages.py` was briefed to author the arts as well and did, with
#    its own `Art` dataclass, its own complexity scale and its own ninety-six
#    lines. Nothing collides — its ids are `art_<region>_<class>` and these are
#    `art_<class>_<sanctum>` — but a class with thirty-two signature moves is
#    not the design. `sages.overlap_report()` states the differences; the two
#    facts that should settle it are:
#      * these arts are `incantation.Incantation` objects and `movesets.Move`
#        objects, so they are cast, tiered, faded, grooved, drawn and recorded
#        by the systems that already exist. sages' arts are a third dataclass
#        with a private complexity measure and a private power formula, which
#        means a second damage spine to keep in step with the first;
#      * the geographies USED to disagree by one room in each direction — these
#        put a sanctum in the Null King's Castle and none in Python Village;
#        sages did the reverse, on the grounds that the castle is the exam hall.
#        SETTLED, in sages' favour, and this file moved: the castle room is
#        retired and `THE STEP NOBODY SWEPT` stands in Python Village at rank
#        one. The argument that decided it was not the seal — `demandable()` is
#        emptied by `finalexam.sealed(enc, "BUILD")` either way — but the
#        ladder. A sanctum reachable only after four regions at twenty-five
#        mastery, six bosses and the castle gates is a sanctum nobody meets in
#        time for it to matter, and a first-hour player who never meets one at
#        all never learns the system exists. `sage_bridge()` now maps ninety-six
#        rooms with nothing unmatched in either direction.
#    If these arts win: `sages.py` drops `ARTS`, `ART_BY_ID`, `_art` and
#    `moveset_requests`, and points `Face.art` at `arts.taught_here(region_id,
#    class_id)` — which is why that function takes a region and a class and
#    returns exactly one art or None. `sage_bridge()` below is that mapping,
#    pre-computed, including the two rooms the rosters do not share.
#    If sages' arts win: this module keeps `SANCTUMS`, `CLASS_SHAPE`,
#    `rung_for`, `_companions`, sections 5 to 13 and the whole ranking harness,
#    and drops its catalogue — the machinery does not care whose lines it is
#    given, only that they are `Incantation`s.
#
# 3. `incantation.BUILTIN_NAMES` DOES NOT NEED ANYTHING FOR THESE ARTS.
#    `sages.py` asks for `next` to be added because seventeen of its lines use
#    `next(generator, default)`. None of these ninety-six do — the idiom here is
#    `min(..., default=...)` and `max(..., default=...)`, which layer 2 already
#    accepts because `default=` is a keyword rather than a name. If `next` is
#    added for sages' sake nothing here changes either way.
#
# 4. NINE REGIONS HAVE A STATED CHAPTER AND EIGHT DO NOT.
#    `REGION_CHAPTER` at the top of this file fills in the eight from the
#    unlock graph and `self_check()` compares the nine against
#    `curriculum.CHAPTERS` every run. If curriculum ever claims one of the
#    eight, the check reports the disagreement instead of quietly keeping this
#    file's opinion. Note that `sages.REGION_LADDER` carries its own chapter
#    column and disagrees with this one in four places — it puts the Stringwood
#    at chapter 2, the Caverns at 1, the Citadel at 5 and the Canopy at 7.
#    Those are its numbers for its own gauntlets; whichever catalogue ships,
#    the two tables should be made one.


def unregister() -> dict:
    """Take the arts back out of both registries.

    For a test that would rather restore the catalogues than special-case them.
    Not used by the game: an unregistered art cannot be cast.
    """
    lines = sum(1 for art in ARTS
                if incantation.BY_ID.pop(art.inc.id, None) is not None)
    moves = sum(1 for art in ARTS
                if movesets.BY_ID.pop(art.move_id, None) is not None)
    return {"lines": lines, "moves": moves}


def sage_bridge() -> dict:
    """`sages.py`'s (region, class) key -> the art taught there, and the gaps.

    One call, so wiring `Face.art` at this catalogue is a lookup rather than a
    reconciliation. `missing` names every room one roster has and the other
    does not, in both directions.
    """
    mapping, missing_here = {}, []
    try:
        from . import sages
        wanted = [(r["id"], c) for r in world.REGIONS
                  for c in getattr(sages, "CLASS_IDS", CLASS_IDS)
                  if r["id"] in getattr(sages, "SAGE_BY_REGION", {})]
    except Exception:                              # pragma: no cover
        wanted = [(a.region, a.class_id) for a in ARTS]
    for region, class_id in wanted:
        art = taught_here(region, class_id)
        if art is None:
            missing_here.append((region, class_id))
        else:
            mapping["%s|%s" % (region, class_id)] = art.id
    theirs = set(r for r, _ in wanted)
    mine = set(SANCTUM_BY_REGION)
    return {
        "mapping": mapping,
        "regions_only_in_sages": sorted(theirs - mine),
        "regions_only_here": sorted(mine - theirs),
        "unmatched": sorted("%s|%s" % pair for pair in missing_here),
        "note": "A region only in sages has no art here and needs six written, "
                "at that region's chapter. A region only here has an art and "
                "no sage to teach it, which sages.py would have to add.",
    }


def handover() -> dict:
    """The asks in section 13, as data, with the current state of each.

    Self-restoring, like `self_check()`: reading the handover must not perform
    half of it.
    """
    with registered():
        return _handover()


def _handover() -> dict:
    from . import bestiary
    mirror_ok = set(bestiary.EXPECTED_INCANTATIONS) == (set(incantation.BY_ID)
                                                        - ART_IDS)
    try:
        from . import sages
        rival = len(getattr(sages, "ARTS", ()))
        collisions = sorted(ART_IDS & set(getattr(sages, "ART_BY_ID", {})))
    except Exception:                              # pragma: no cover
        rival, collisions = 0, []
    needs_builtin = sorted(
        {"next"} & {name for art in ARTS
                    for name in (art.inc.template,) if "next(" in name})
    return {
        "bestiary_mirror": {
            "assertion": "set(bestiary.EXPECTED_INCANTATIONS) == "
                         "set(incantation.BY_ID) - arts.ART_IDS",
            "holds_with_the_fix": mirror_ok,
            "art_ids_added": len(ART_IDS),
            "file": "tests/test_incantation.py::test_contract_mirror_has_not_drifted",
        },
        "duplicate_catalogue": {
            "sages_arts": rival, "these_arts": len(ARTS),
            "id_collisions": collisions,
            "bridge": "arts.taught_here(region_id, class_id)",
        },
        "builtins_needed": needs_builtin,
        "score_full": {
            "assertion": "incantation.SCORE_FULL is tall enough that a secret "
                         "art measures differently from an ordinary line at "
                         "every scaffold tier, not just the low ones.",
            "holds": not saturation_report()["collapsed_at_recalled"],
            "report": "arts.saturation_report()",
            "edit": "raise incantation.SCORE_FULL from %.1f to about 85.0, and "
                    "raise DAMAGE_UNIT with it so an ordinary cast is still "
                    "worth what it is worth today"
                    % incantation.SCORE_FULL,
            "why": "The ruler clamps at raw SCORE_FULL. The sixty-six ordinary "
                   "lines never reach it; the arts pass it at PROMPTED and are "
                   "all past it by RECALLED, so at the tier a drilled art is "
                   "actually cast at they are indistinguishable from each "
                   "other. No re-authoring in this file can fix that — there "
                   "are six raw points between the hardest ordinary line and "
                   "the ceiling, and a sixteen-rung secret ladder does not fit "
                   "in them.",
        },
        "region_chapter": {
            "stated_by_curriculum": sorted(
                {c.region for c in _curriculum().CHAPTERS}),
            "assumed_here": sorted(set(REGION_CHAPTER)
                                   - {c.region for c in _curriculum().CHAPTERS}),
        },
    }


def _curriculum():
    from . import curriculum
    return curriculum
