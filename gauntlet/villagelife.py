"""Village life: who stands in a village, what they are doing, and how it moves.

THIS FILE DRAWS NOTHING. It is the data half of docs/12-the-zone-companions.md
section 7, and the renderer that consumes it lives in `web/js/overworld.js`,
which is owned by another pass and is not touched from here. The contract in
this docstring is therefore the whole handover: a renderer that reads it should
never need to ask this module a second question, and should never need an RNG
of its own.

WHY THE POSITIONS ARE OFFSETS AND NOT TILES
-------------------------------------------
Buildings are placed in JavaScript. `overworld.placeMarkers()` walks a
`pixel.rng(hash(region.id) + 99)` stream and nudges each 2x2 footprint until it
finds dry ground, so the absolute tile of building *i* is not knowable from
Python without reimplementing that RNG here — and a second implementation of a
placement rule is the exact bug this project keeps writing down: two sources of
truth that agree until the day they do not.

So every position below is an OFFSET IN TILES FROM A BUILDING ANCHOR, and the
renderer adds the anchor it already has:

    px = ((building.x + dx) + 0.5) * TILE
    py = ((building.y + dy) + 0.5) * TILE

`building` is an index into the region's building markers in the order
`placeMarkers` pushed them, which is the same order `variant = i % 4` uses. The
+0.5 centres the sprite in the tile, which is what the hero rig already does.

THE HOME BOX
------------
Each villager owns a 5x5-tile box centred on their building. A building
occupies (bx, by)..(bx+1, by+1), so the box spans dx, dy in -1..3 and its four
footprint cells are excluded — a villager never stands in a wall, and never
stands on the door at (0, +1) either, because a body parked in a doorway reads
as a collision bug in a game where villagers are deliberately not in `solid()`.
That leaves `HOME_CELLS`, 21 legal cells, and waypoints are drawn from it.

DETERMINISM
-----------
Everything is a pure function of `(region_id, seed, building_count)`. There is
no `random`, no `time`, no `hash()` — Python salts `hash()` per interpreter, so
a village built with it would be a different village after a relaunch, which is
the same failure `weather.py` writes out FNV-1a to avoid. This module writes
out the same FNV-1a for the same reason, and namespaces every key with "vl|"
so that an identical hash over an identical region id cannot correlate a
village with that region's weather.

WHAT THE PLAYER ASKED FOR, AND WHERE IT IS
------------------------------------------
"male and female sprites interacting like a village"  -> `body`, balanced per
    village (see BODY_TYPES), plus `palette`, `waypoints` and `emote`.
"children playing or chasing butterflys where appropriate"  -> ACTIVITIES,
    biome `village` and `grass`.
"a snowball fight in snow land"   -> ACTIVITIES['mountain'], Twin Pointer Pass.
"playing with fireworks in volcano land" -> ACTIVITIES['mine'], the Mines.
"chasing ants in rainforest"      -> ACTIVITIES['deepforest'], and the beetles
    of `forest` next door; the design doc assigns THE GREEN to those regions.
"towns should feel interactive"   -> `speaks`, which is true for exactly the
    34 people `banter.SPEAKERS` already wrote and false for everybody else.

ZERO NEW WRITING. Every line in this payload came out of `quests.NPCS`. The
unnamed crowd is silent by design: a village of twelve people who all open a
dialogue box is a village nobody walks through twice.

WHERE IT IS WIRED, so the next reader does not have to grep for it
------------------------------------------------------------------
Two call sites, both in `engine.py`, both pure reads of the save seed:

    Game.region_view(region_id)   view["village"] = villagelife.village(
                                      region_id, self._save_seed())
    Game.world_map()              {"villages": {row["region"]: row for row in
                                      villagelife.region_payload(seed=...)}}

and they reach the client on `/api/region` and `/api/world-map`, which the
overworld already asks for on every arrival and on every map screen. Nothing
new was opened for this.

SEEDED OFF THE SAVE SEED, NOT OFF THE REGION ALONE, and that is the one
decision a caller can get wrong. `state["world_seed"]` is the value every
deterministic generator in a save shares — `worldgen` and `shop` both take it
— so two saves get two villages and one save gets the same village every time
it is opened. Seeding off the region id alone would make every player in the
world walk through the identical crowd; seeding off time would rebuild the
village under a player who reloaded.

It costs 0.77 ms for one region and 6.5 ms for all seventeen, measured, which
is why the whole map can ride a single payload rather than needing a route of
its own.
"""
from __future__ import annotations

from . import banter, quests, world

# ---------------------------------------------------------------------------
# UNITS
# ---------------------------------------------------------------------------
# All three of these are read off the files that already own them rather than
# invented here. TILE is `tiles.TILE_SIZE`. The hero walks at 112 px/s
# (`overworld.js`, next to COMPANION_MAX_SPEED, which is 190). 40 px/s is
# 0.357x the hero and 0.40 s/tile: an amble, not a slowed-down hero.
TILE = 16
HERO_SPEED = 112.0
VILLAGER_SPEED = 40.0

# Section 7.3. A villager stands still for between a second and a half and four
# seconds at each waypoint. Below 1.5 s the pause reads as a stutter in the walk
# cycle; above 4.0 s the village reads as abandoned.
PAUSE_MIN = 1.5
PAUSE_MAX = 4.0

# Section 7.5. The activity is updated at 12 Hz and interpolated between ticks,
# and there are never more than twelve particles alive in one village. Both
# numbers are stated here so a renderer can assert against them instead of
# trusting that the table below stayed small.
TICK_HZ = 12
PARTICLE_CAP = 12

# Section 7.3. Four waypoints inside a 5x5 box.
BOX = 5
WAYPOINTS = 4

# The 2x2 building footprint, in box-relative tiles, and the door in it.
FOOTPRINT = frozenset({(0, 0), (1, 0), (0, 1), (1, 1)})
DOOR_CELL = (0, 1)

# The 21 cells a villager may stand on: the 5x5 box minus the building.
HOME_CELLS: tuple = tuple((dx, dy)
                          for dy in range(-1, BOX - 1)
                          for dx in range(-1, BOX - 1)
                          if (dx, dy) not in FOOTPRINT)

FACINGS: tuple = ("down", "up", "left", "right")
BODY_TYPES: tuple = ("a", "b")


# ---------------------------------------------------------------------------
# HOW MANY BUILDINGS, AND SO HOW MANY PEOPLE
# ---------------------------------------------------------------------------
# Section 5.3 of the design doc. Python Village gets five because it is the one
# town in the game with a puzzle house in it; the three other town-shaped
# biomes get four; every other vendor region gets a waystation of two, which is
# a mender's hut and a shelf; and the Null King's Castle gets none.
#
# THE CASTLE HAVING NO VILLAGE IS THE DESIGN, NOT AN OMISSION. The doc says so
# in its own words — "It is the one place that gets no settlement, and the
# absence is the point" — and section 7.4 gives its biome the only activity row
# that is `none`. `has_village()` is the function that says so out loud, so a
# caller that iterates every region gets a settled=False payload rather than an
# empty list it has to interpret.
TOWN_BIOMES: tuple = ("highland", "citadel", "arena")
UNSETTLED_BIOMES: tuple = ("castle",)

BUILDINGS_VILLAGE = 5
BUILDINGS_TOWN = 4
BUILDINGS_WAYSTATION = 2


def buildings_for(region_id: str) -> int:
    """How many buildings the settlement in this region has. Zero means there
    is no settlement at all."""
    region = world.REGION_BY_ID.get(region_id)
    if not region:
        return 0
    biome = region.get("biome", "")
    if biome in UNSETTLED_BIOMES:
        return 0
    if region_id == "python_village":
        return BUILDINGS_VILLAGE
    if biome in TOWN_BIOMES:
        return BUILDINGS_TOWN
    return BUILDINGS_WAYSTATION


BUILDING_COUNT: dict = {r["id"]: buildings_for(r["id"]) for r in world.REGIONS}


def has_village(region_id: str) -> bool:
    """True where somebody lives. False for the Castle, and only the Castle."""
    return buildings_for(region_id) > 0


def headcount(region_id: str, buildings: int = None) -> dict:
    """Section 7.1, as arithmetic rather than as a table.

        villagers = min(12, 2 * buildings)
        children  = villagers // 3

    Five buildings gives ten villagers and three children, which is what the
    doc says Python Village has. Two gives four and one, which is what it says
    a waystation has. `buildings` may be passed by a caller that has already
    placed the markers and counted them, so a map that failed to find dry
    ground for a building does not produce villagers standing in a lake.
    """
    n = buildings_for(region_id) if buildings is None else max(0, int(buildings))
    villagers = min(12, 2 * n)
    children = villagers // 3
    return {"buildings": n, "villagers": villagers, "children": children,
            "adults": villagers - children}


# ---------------------------------------------------------------------------
# THE ACTIVITY, ONE PER BIOME
# ---------------------------------------------------------------------------
# Section 7.4, with the doc's "Cost" column turned into numbers a renderer can
# execute. Every biome in `world.REGIONS` is answered, including the one whose
# answer is "nobody plays here", so this table can never raise KeyError — the
# same totality rule `elements.BIOME_AFFINITY` keeps with NEUTRAL.
#
# FIELDS
#   kind        the particle sprite, and the argument to the planned
#               `tiles.activitySprite(kind, P, frame)`. None means this
#               activity has no particles at all and is carried by poses.
#   prop        a static piece of scenery drawn once, not a particle. Only the
#               Canopy's rope uses it.
#   particles   how many are alive at once. Never more than PARTICLE_CAP.
#   size        [w, h] in pixels. Never larger than 8x10, which is the ceiling
#               the doc's sprite row states.
#   motion      which path the renderer runs. The vocabulary is MOTIONS below.
#   params      the numbers that motion needs. Documented per motion.
#   actors      how many people stand in the activity instead of walking, when
#               the village has that many of the right kind spare.
#   min_actors  how many it takes for the activity to still READ as itself. A
#               snowball FIGHT and a reed-boat RACE need two people or they are
#               a child throwing snow at nobody; a kite needs one. Where the
#               preferred kind runs short — a two-building waystation has
#               exactly one child — the roster is topped up from whoever else
#               is in the village to reach this number, and never past it.
#   actor_kind  'child' or 'adult', a preference rather than a law. The
#               Debugging Dungeon's quench is done by apprentices, who are
#               adults; everything else prefers children, which is what the
#               player asked for.
#   label       prose, for tests and for a debug overlay. Never shown in game.
ACTIVITIES: dict = {
    # -- The starter village, and the field beyond it. The player named this
    # one: "children playing or chasing butterflys where appropriate".
    "village": {
        "kind": "butterfly", "prop": None, "particles": 3, "size": [4, 4],
        "motion": "sine", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"span_px": 96, "amp_px": 10, "period_ms": 2600},
        "label": "children chase butterflies",
    },
    "grass": {
        "kind": "butterfly", "prop": None, "particles": 3, "size": [4, 4],
        "motion": "sine", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"span_px": 112, "amp_px": 12, "period_ms": 2800},
        "label": "children chase butterflies across the open field",
    },
    # -- An exposed plateau is the one place in the game where a kite works.
    "highland": {
        "kind": "kite", "prop": None, "particles": 1, "size": [8, 10],
        "motion": "tether", "actors": 1, "min_actors": 1, "actor_kind": "child",
        "params": {"radius_px": 34, "period_ms": 5200, "line": True,
                   "line_px": 1, "tilt_deg": 18},
        "label": "a kite on a string",
    },
    # -- Stringwood. The letters are the local fauna, so the beetles spell.
    "forest": {
        "kind": "beetle", "prop": None, "particles": 4, "size": [3, 3],
        "motion": "scatter", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"radius_px": 22, "period_ms": 3400, "settle_ms": 900},
        "label": "children chase spelling-beetles across a fallen letter",
    },
    # -- Array Caverns. There is no sky, so the children make one.
    "cave": {
        "kind": "paper_lamp", "prop": None, "particles": 3, "size": [4, 6],
        "motion": "rise", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"rise_px_s": 8, "life_s": 9.0, "sway_px": 5,
                   "period_ms": 3000},
        "label": "children float paper lamps upward",
    },
    # -- Sliding Window Marsh. A ditch, two boats, and a frame that slides.
    "swamp": {
        "kind": "reed_boat", "prop": None, "particles": 2, "size": [6, 3],
        "motion": "lane", "actors": 2, "min_actors": 2, "actor_kind": "child",
        "params": {"span_px": 80, "period_ms": 4600, "lane_gap_px": 9,
                   "bob_px": 2},
        "label": "reed boats raced in a ditch",
    },
    # -- THE SNOW. The player asked for this one by name.
    "mountain": {
        "kind": "snowball", "prop": None, "particles": 1, "size": [3, 3],
        "motion": "arc", "actors": 2, "min_actors": 2, "actor_kind": "child",
        "params": {"frames": 6, "period_ms": 1500, "peak_px": 18,
                   "span_px": 48, "rest_ms": 700},
        "label": "a snowball fight",
    },
    # -- THE FIRE. The player asked for this one by name too. Twelve sparks is
    # exactly PARTICLE_CAP, and it is the only village in the game that reaches
    # it, which is why the cap is worth stating rather than assuming.
    "mine": {
        "kind": "firework_spark", "prop": None, "particles": 12, "size": [2, 2],
        "motion": "burst", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"launch_min_s": 8.0, "launch_max_s": 14.0, "life_s": 1.4,
                   "speed_px_s": 46, "gravity_px_s2": 38, "rise_px": 40},
        "label": "fireworks, one launch every eight to fourteen seconds",
    },
    # -- The Citadel drills. Badly, because they are eight.
    "citadel": {
        "kind": None, "prop": None, "particles": 0, "size": None,
        "motion": "pose", "actors": 2, "min_actors": 2, "actor_kind": "child",
        "params": {"pose": "drill", "period_ms": 1800, "beats": 4,
                   "stagger_ms": 220},
        "label": "children drill in a square, badly",
    },
    # -- THE RAINFOREST ANTS, which the player asked for. A fixed spline so the
    # column is a column and not eight independent insects: the renderer walks
    # every ant down these control points at a fixed spacing.
    "deepforest": {
        "kind": "ant", "prop": None, "particles": 8, "size": [2, 2],
        "motion": "spline", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"period_ms": 6400, "spacing": 0.11, "loop": True,
                   "points": [[-3, 1], [-1, 0], [1, 1], [2, 2],
                              [1, 3], [-1, 3], [-3, 2], [-3, 1]]},
        "label": "children follow an ant column",
    },
    # -- The Canopy. The rope is scenery, drawn once; the swing is a pose. That
    # is why this row has a `prop` and no `kind`: the doc's sprite list is ten
    # long and a rope is not one of the ten.
    "canopy": {
        "kind": None, "prop": "rope", "particles": 0, "size": None,
        "motion": "swing", "actors": 1, "min_actors": 1, "actor_kind": "child",
        "params": {"period_ms": 2400, "arc_deg": 34, "rope_px": 28,
                   "pose": "swing"},
        "label": "a child swings on a spliced rope",
    },
    # -- Graph Wastes. Somebody still flies a flag over a lattice of ruins.
    "wastes": {
        "kind": "pennant", "prop": None, "particles": 1, "size": [6, 10],
        "motion": "flutter", "actors": 1, "min_actors": 1, "actor_kind": "child",
        "params": {"period_ms": 1300, "amp_px": 3, "mast_px": 22},
        "label": "a pennant flown off a ruin",
    },
    # -- DP Ruins. The solved tiles stay lit, so hopping them is the local game.
    "ruins": {
        "kind": None, "prop": None, "particles": 0, "size": None,
        "motion": "pose", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"pose": "hop", "period_ms": 1100, "beats": 2,
                   "stagger_ms": 400},
        "label": "children hop the lit tiles",
    },
    # -- The Armorer's forge. Apprentices, so ADULTS: Garrick is two days into
    # reading one crack and he is not a child.
    "dungeon": {
        "kind": "steam_puff", "prop": None, "particles": 6, "size": [6, 6],
        "motion": "puff", "actors": 2, "min_actors": 2, "actor_kind": "adult",
        "params": {"life_s": 1.1, "rise_px_s": 22, "period_ms": 2600,
                   "spread_px": 7},
        "label": "apprentices quench hot metal",
    },
    # -- The Tower, whose whole joke is that each floor costs more than the one
    # below, counted out loud by somebody who has not yet got to the top.
    "tower": {
        "kind": None, "prop": None, "particles": 0, "size": None,
        "motion": "pose", "actors": 2, "min_actors": 1, "actor_kind": "child",
        "params": {"pose": "count", "period_ms": 2000, "beats": 3,
                   "stagger_ms": 600},
        "label": "children count floors out loud",
    },
    # -- The Coliseum. Sticks, because the sand does not care how much you know.
    "arena": {
        "kind": None, "prop": None, "particles": 0, "size": None,
        "motion": "pose", "actors": 2, "min_actors": 2, "actor_kind": "child",
        "params": {"pose": "spar", "period_ms": 1400, "beats": 2,
                   "stagger_ms": 180},
        "label": "children spar with sticks",
    },
    # -- The Null King's. Nobody plays here, and nobody lives here either.
    "castle": {
        "kind": None, "prop": None, "particles": 0, "size": None,
        "motion": "none", "actors": 0, "min_actors": 0, "actor_kind": None,
        "params": {},
        "label": "nobody plays here",
    },
}

# The ten particle sprites the design doc's renderer row commissions, in the
# order it lists them. `self_check` proves the table above asks for these ten
# and no eleventh, because an eleventh is a sprite nobody was asked to draw.
ACTIVITY_SPRITES: tuple = (
    "butterfly", "beetle", "paper_lamp", "kite", "reed_boat",
    "snowball", "firework_spark", "ant", "pennant", "steam_puff",
)

# The paths a renderer has to implement. Named so an unknown motion is a loud
# failure rather than a still village.
MOTIONS: tuple = ("sine", "tether", "scatter", "rise", "lane", "arc",
                  "burst", "spline", "flutter", "puff", "swing", "pose", "none")

# No activity sprite is larger than this. The doc states it as a rule for the
# sprite work; it is asserted here so the data cannot quietly outgrow the art.
SPRITE_MAX_W = 8
SPRITE_MAX_H = 10


def activity_for(region_id: str) -> dict:
    """The activity spec for a region's biome. Always answers."""
    region = world.REGION_BY_ID.get(region_id) or {}
    row = ACTIVITIES.get(region.get("biome", ""), ACTIVITIES["castle"])
    out = dict(row)
    out["params"] = _deep_copy(row["params"])
    out["size"] = list(row["size"]) if row["size"] else None
    return out


def _deep_copy(value):
    """A copy deep enough for this module's payloads: dicts, lists, scalars.

    ACTIVITIES is module-level shared state. A caller that mutated a params
    dict in place would change every other caller's village, which is the class
    of bug `weather.region_payload` copies to avoid.
    """
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_deep_copy(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# THE HASH
# ---------------------------------------------------------------------------
# FNV-1a, 32 bit, over a text key. Written out rather than reached for from
# hashlib because a village is built a few hundred keys at a time, and written
# out rather than using hash() because Python salts hash() per interpreter — a
# village that changed when the player relaunched the game would not be a
# village, it would be a crowd.
def _h32(text: str) -> int:
    h = 0x811C9DC5
    for ch in text:
        h = ((h ^ (ord(ch) & 0xFF)) * 0x01000193) & 0xFFFFFFFF
    return h


def _mix32(h: int) -> int:
    """Murmur3's finalizer, and this module needs it where weather.py does not.

    Weather hashes a key whose variable parts are at the END, so every bit of
    every difference gets the full remaining avalanche. This module's keys are
    shaped "vl|region|seed|<region>-vil-07|skin": the byte that differs between
    two villagers is followed by only five more, which is five multiplications
    of mixing and not enough. Measured, over 19,800 adjacent pairs: two
    neighbours shared a skin tone 22.293% of the time against an expected
    16.667%, roughly twenty sigma out. Villages had a grain in them.

    Five operations fix it and cost nothing a village can notice — the whole
    world's worth of people is a few thousand calls, once.
    """
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def _unit(text: str) -> float:
    """A float in [0, 1) from a key, avalanched. The top byte is dropped
    because FNV's low bits are the weak ones and the finalizer has already
    spread the rest across the word."""
    return ((_mix32(_h32(text)) >> 8) & 0xFFFFFF) / 0x1000000


def _seed_int(seed) -> int:
    """Accept an int, a save seed code, or anything at all, and get an int."""
    if isinstance(seed, int):
        return seed & 0xFFFFFFFF
    return _h32(str(seed))


def _key(*parts) -> str:
    """Every key this module hashes starts with 'vl|'. That prefix is the only
    reason a village and that region's weather cannot share a draw: both use
    FNV-1a over a region id, and without the namespace a sunny day and a
    particular child would be the same coin."""
    return "vl|" + "|".join(str(p) for p in parts)


def _span(key: str, lo: float, hi: float, places: int = 2) -> float:
    return round(lo + _unit(key) * (hi - lo), places)


def _index(key: str, n: int) -> int:
    """An index in [0, n) from a key, taken off the HIGH bits.

    NOT `_h32(key) % n`, and the difference is measurable rather than
    theoretical. FNV-1a's final operation is `(h ^ byte) * PRIME` with an odd
    prime, so the low bit of the digest is the XOR of the low bits of every
    input byte — a parity, not a hash. Keys that differ by one in a trailing
    counter ("...-vil-02|skin", "...-vil-03|skin") therefore always land on
    opposite parities, and `% n` for any EVEN n inherits that: with six skin
    tones, adjacent villagers shared a skin tone 0.000% of the time across
    19,800 pairs where 16.667% was expected. Every villager in the game was
    standing next to somebody who could not look like them.

    `_unit` already drops the low byte for this reason — weather.py's own
    comment says the top byte goes because the low bits are where FNV is
    weak — so every index draw in this module goes through it.
    """
    return min(int(_unit(key) * n), n - 1) if n > 0 else 0


def _choice(seq, key: str):
    return seq[_index(key, len(seq))]


def _weighted(table: dict, key: str) -> str:
    """A weighted draw over a {name: weight} dict, iterated in sorted order so
    that dict insertion order can never change a village."""
    total = sum(table.values())
    roll = _unit(key) * total
    acc = 0.0
    for name in sorted(table):
        acc += table[name]
        if roll < acc:
            return name
    return sorted(table)[-1]


# ---------------------------------------------------------------------------
# WHAT PEOPLE LOOK LIKE
# ---------------------------------------------------------------------------
# `sprites.heroFrame` already draws a villager out of the hero rig with
# `weapon: null` — its own comment says so — and it already takes a palette
# dict of cloak, tunic, skin, hair, boot and trim. So nobody has to draw a
# single new body: a villager IS a hero with the sword taken off and the
# colours changed, and both body types already exist as HERO_BODY_TYPES.
#
# Clothing comes from the job, which is what the doc means by "palette comes
# from the role". Skin and hair do not: a village where everyone shares a face
# is its own kind of empty, so those are drawn per person.
ROLE_PALETTE: dict = {
    "carter":    {"cloak": "#6b5638", "tunic": "#59452f", "boot": "#3a2c22",
                  "trim": "#b98a3f"},
    "weaver":    {"cloak": "#7a4f6b", "tunic": "#5c3a52", "boot": "#3c2c33",
                  "trim": "#d2a2c0"},
    "cooper":    {"cloak": "#4f5f43", "tunic": "#3e4b36", "boot": "#332b23",
                  "trim": "#9fb06a"},
    "baker":     {"cloak": "#b0894f", "tunic": "#8a6a3c", "boot": "#40342a",
                  "trim": "#e8d2a0"},
    "drover":    {"cloak": "#3f5a6b", "tunic": "#33485a", "boot": "#2c3038",
                  "trim": "#7fa6bf"},
    "thatcher":  {"cloak": "#8a7a42", "tunic": "#6b5f34", "boot": "#3a3126",
                  "trim": "#c9bb72"},
    "potter":    {"cloak": "#8a4a3f", "tunic": "#6b3a32", "boot": "#3c2a25",
                  "trim": "#c98a6a"},
    "herbalist": {"cloak": "#436b5a", "tunic": "#345247", "boot": "#2a332e",
                  "trim": "#8fc9a8"},
}
UNNAMED_ROLES: tuple = tuple(sorted(ROLE_PALETTE))

# Children wear whatever was cut down for them, which is to say brighter and
# worse-fitting. One palette, because a child is a child.
CHILD_PALETTE: dict = {"cloak": "#c46a4f", "tunic": "#e0a85f",
                       "boot": "#4a382c", "trim": "#ffe2a8"}

# The named thirty-four already have a voice in banter.py, so their clothes are
# taken from that register rather than from an invented trade. A WARDEN and a
# SCHOLAR standing in the same square should not be wearing the same coat.
REGISTER_PALETTE: dict = {
    "LABOURER": {"cloak": "#6b5638", "tunic": "#59452f", "boot": "#3a2c22",
                 "trim": "#b98a3f"},
    "RANGER":   {"cloak": "#3f6b4a", "tunic": "#33523c", "boot": "#2e3328",
                 "trim": "#9fd2a8"},
    "WARDEN":   {"cloak": "#3f5570", "tunic": "#33455c", "boot": "#2c3038",
                 "trim": "#cfd8e8"},
    "VENDOR":   {"cloak": "#8a6a3f", "tunic": "#6b5230", "boot": "#3c3026",
                 "trim": "#e8c86a"},
    "SCHOLAR":  {"cloak": "#5a4f7a", "tunic": "#463c60", "boot": "#332e40",
                 "trim": "#bfb0e0"},
    "SOLDIER":  {"cloak": "#7a3f3f", "tunic": "#5c3232", "boot": "#3a2a2a",
                 "trim": "#d8a0a0"},
    "CHILD":    dict(CHILD_PALETTE),
    "STEWARD":  {"cloak": "#4a4a52", "tunic": "#3a3a42", "boot": "#2c2c32",
                 "trim": "#a8a8b8"},
    "SMITH":    {"cloak": "#5a3f32", "tunic": "#463229", "boot": "#332822",
                 "trim": "#e0a05a"},
    "MENTOR":   {"cloak": "#3f5a7a", "tunic": "#33475c", "boot": "#2c3038",
                 "trim": "#d8c88a"},
}

SKIN_TONES: tuple = ("#f0c9a0", "#e8b88a", "#d2a077", "#b07a52", "#8a5a3c",
                     "#6b432c")
HAIR_TONES: tuple = ("#2a2028", "#4a3050", "#5c3a22", "#8a6a3f", "#b09060",
                     "#d8d0c0", "#7a3a2a")

# Mostly neutral, because sprites.js says so in its own words: "Everything else
# is NEUTRAL, and neutral still blinks." A village of delighted faces is as
# wrong as a village of blank ones.
ADULT_EMOTES: dict = {"neutral": 52, "pleased": 20, "strained": 10,
                      "stubborn": 8, "delighted": 6, "alarmed": 2,
                      "defeated": 2}
CHILD_EMOTES: dict = {"neutral": 30, "pleased": 26, "delighted": 28,
                      "alarmed": 8, "strained": 5, "stubborn": 3}

# sprites.EMOTE_KEYS, mirrored so self_check can prove no emote in this file is
# one the renderer would have to alias.
EMOTE_KEYS: tuple = ("neutral", "pleased", "strained", "alarmed", "stubborn",
                     "delighted", "defeated")


# ---------------------------------------------------------------------------
# WHO IS HERE
# ---------------------------------------------------------------------------
def named_for(region_id: str) -> list:
    """The written people who live in this region, in `quests.NPCS` order.

    Two per region, three in Python Village, one in the Castle: thirty-four in
    total, every one of them already carrying a name, a role, a sprite key, a
    register and a line. This is the whole of section 7.2's "for free".
    """
    return [nid for nid, npc in quests.NPCS.items()
            if npc.get("region") == region_id]


def _named_record(npc_id: str) -> dict:
    who = banter.speaker(npc_id)
    npc = quests.NPCS.get(npc_id, {})
    return {
        "npc": npc_id,
        "name": who.get("name", npc_id),
        "role": who.get("role", ""),
        "sprite": who.get("sprite", "villager"),
        "register": who.get("register", "LABOURER"),
        "line": npc.get("line"),
        "speaks": True,
    }


def _unnamed_record(region_id: str, seed: int, index: int, child: bool) -> dict:
    """One of the crowd. Silent, on purpose.

    Section 7.2: "Everyone else is unnamed and silent. They walk, they pause,
    they emote. They never open a dialogue box." That is not a shortcut, it is
    the reason the thirty-four written people stay worth walking up to.
    """
    if child:
        return {"npc": None, "name": None, "role": "child", "sprite": "child",
                "register": "CHILD", "line": None, "speaks": False}
    role = _choice(UNNAMED_ROLES, _key(region_id, seed, index, "role"))
    return {"npc": None, "name": None, "role": role, "sprite": "villager",
            "register": None, "line": None, "speaks": False}


def _palette(region_id: str, seed: int, vid: str, who: dict) -> dict:
    """Clothes from the job, face from the person."""
    if who["register"] and who["register"] in REGISTER_PALETTE:
        base = REGISTER_PALETTE[who["register"]]
    elif who["role"] in ROLE_PALETTE:
        base = ROLE_PALETTE[who["role"]]
    else:
        base = CHILD_PALETTE if who["sprite"] == "child" else \
            ROLE_PALETTE[UNNAMED_ROLES[0]]
    out = dict(base)
    out["skin"] = _choice(SKIN_TONES, _key(region_id, seed, vid, "skin"))
    out["hair"] = _choice(HAIR_TONES, _key(region_id, seed, vid, "hair"))
    out["metal"] = "#c3cbd8"
    return out


# ---------------------------------------------------------------------------
# HOW THEY MOVE
# ---------------------------------------------------------------------------
def _facing(from_cell, to_cell) -> str:
    """Which way a villager is looking on the leg between two waypoints.

    Screen y grows downward, so a positive dy is 'down'. A leg with no
    displacement at all cannot happen — `_route` guarantees distinct waypoints
    — but it would answer 'down', which is the facing every idle sprite in this
    game already defaults to.
    """
    ddx = to_cell[0] - from_cell[0]
    ddy = to_cell[1] - from_cell[1]
    if abs(ddx) >= abs(ddy):
        if ddx > 0:
            return "right"
        if ddx < 0:
            return "left"
        return "down"
    return "down" if ddy > 0 else "up"


def _route(region_id: str, seed: int, vid: str) -> list:
    """Four distinct cells of the home box, walked in a loop.

    The picks are biased AWAY from wherever the villager just was: candidates
    are ranked by Chebyshev distance from the previous waypoint and the draw is
    taken from the farther half. Four cells chosen without that rule land
    adjacent often enough that a villager shuffles one tile and stops, which
    reads as a stuck sprite rather than as somebody going about their day.
    """
    chosen: list = []
    pool = list(HOME_CELLS)
    for i in range(WAYPOINTS):
        if not chosen:
            cand = pool
        else:
            prev = chosen[-1]
            ranked = sorted(
                pool,
                key=lambda c: (-max(abs(c[0] - prev[0]), abs(c[1] - prev[1])),
                               c[0], c[1]))
            cand = ranked[:max(1, len(ranked) // 2)]
        pick = cand[_index(_key(region_id, seed, vid, "wp", i), len(cand))]
        chosen.append(pick)
        pool.remove(pick)
    return chosen


def _waypoints(region_id: str, seed: int, vid: str, child: bool) -> list:
    cells = _route(region_id, seed, vid)
    emotes = CHILD_EMOTES if child else ADULT_EMOTES
    out = []
    for i, cell in enumerate(cells):
        nxt = cells[(i + 1) % len(cells)]
        out.append({
            "dx": cell[0], "dy": cell[1],
            "face": _facing(cell, nxt),
            "pause_s": _span(_key(region_id, seed, vid, "pause", i),
                             PAUSE_MIN, PAUSE_MAX),
            "emote": _weighted(emotes, _key(region_id, seed, vid, "emote", i)),
        })
    return out


# ---------------------------------------------------------------------------
# WHERE THE ACTIVITY HAPPENS
# ---------------------------------------------------------------------------
# A ring of eight candidate offsets clear of a building's 5x5 home box, so the
# plaza is next to the settlement rather than inside a wall. Decoration only:
# nothing in the game is gated on it, so a renderer that has to nudge one of
# these onto walkable ground may, and should.
PLAZA_RING: tuple = ((-4, 0), (-4, 3), (5, 0), (5, 3),
                     (0, -4), (1, -4), (0, 5), (1, 5))

# Where the actors stand, relative to the plaza origin, each facing it. Taken
# in order, so two actors face each other across the activity and four box it.
# TWO FRAMES OF REFERENCE, AND BOTH SAY WHICH ONE THEY ARE IN.
#
# A villager's box, home and waypoints are offsets from THEIR OWN building.
# A station is an offset from the PLAZA, which hangs off a building that is
# usually somebody else's. Those are different origins and the numbers look
# identical, so every station carries `anchor: "plaza"` rather than leaving a
# renderer to infer it and get it wrong once, silently, in one region.
STATION_RING: tuple = (
    {"anchor": "plaza", "dx": -2, "dy": 0, "face": "right"},
    {"anchor": "plaza", "dx": 2, "dy": 0, "face": "left"},
    {"anchor": "plaza", "dx": 0, "dy": -2, "face": "down"},
    {"anchor": "plaza", "dx": 0, "dy": 2, "face": "up"},
)


def _particles(region_id: str, seed: int, spec: dict) -> list:
    """Every particle, with its phase already drawn.

    THE RENDERER GETS NO RNG. Phase, lane and launch angle are decided here so
    that the same village animates identically on two machines, and so that a
    reduced-motion pass can freeze the whole thing at phase 0 without anything
    jumping. `phase` is a fraction of `params.period_ms`; `lane` indexes
    whatever the motion lays out in parallel.
    """
    n = int(spec.get("particles") or 0)
    if n <= 0:
        return []
    motion = spec["motion"]
    params = spec.get("params") or {}
    out = []
    for i in range(n):
        base = _key(region_id, seed, "p", motion, i)
        p = {
            "i": i,
            "phase": round(_unit(base + "|ph"), 4),
            "lane": i % max(1, min(n, 4)),
        }
        if motion == "sine":
            p["dir"] = 1 if _unit(base + "|dir") < 0.5 else -1
            p["amp_px"] = round(params.get("amp_px", 10)
                                * _span(base + "|amp", 0.7, 1.3, 3), 2)
        elif motion == "burst":
            p["angle_deg"] = round(360.0 * i / n, 2)
            p["speed_px_s"] = round(params.get("speed_px_s", 46)
                                    * _span(base + "|v", 0.75, 1.25, 3), 2)
        elif motion == "spline":
            p["t"] = round((i * params.get("spacing", 0.11)) % 1.0, 4)
        elif motion == "rise":
            p["sway_phase"] = round(_unit(base + "|sw"), 4)
        elif motion == "lane":
            p["lane"] = i
        out.append(p)
    return out


def activity(region_id: str, seed=0, buildings: int = None) -> dict:
    """The activity payload for one village: what is happening, where, who is
    in it, and every number needed to animate it."""
    s = _seed_int(seed)
    spec = activity_for(region_id)
    n_build = buildings_for(region_id) if buildings is None else max(0, int(buildings))
    if n_build <= 0 or spec["motion"] == "none":
        return {"kind": None, "prop": None, "motion": "none", "particles": [],
                "particle_count": 0, "size": None, "params": {},
                "label": spec["label"], "actors": [], "actor_kind": None,
                "plaza": None, "tick_hz": TICK_HZ}
    home = _index(_key(region_id, s, "plaza"), n_build)
    ring = PLAZA_RING[_index(_key(region_id, s, "ring"), len(PLAZA_RING))]
    parts = _particles(region_id, s, spec)
    return {
        "kind": spec["kind"],
        "prop": spec["prop"],
        "motion": spec["motion"],
        "size": spec["size"],
        "params": spec["params"],
        "label": spec["label"],
        "actor_kind": spec["actor_kind"],
        "particle_count": len(parts),
        "particles": parts,
        # Anchored on a building, like everything else in this payload.
        "plaza": {"building": home, "dx": ring[0], "dy": ring[1]},
        # Filled by `village()`, which is the only place that knows the roster.
        "actors": [],
        "tick_hz": TICK_HZ,
    }


# ---------------------------------------------------------------------------
# THE VILLAGE
# ---------------------------------------------------------------------------
def villagers(region_id: str, seed=0, buildings: int = None) -> list:
    """Everybody in this village, named people first.

    Named first is not cosmetic. Buildings are assigned round-robin, so putting
    the written thirty-four at the head of the roster puts them at buildings 0,
    1 and 2 — the mender's house, the shelf and the forge — which are the three
    doors a player walks to anyway.
    """
    s = _seed_int(seed)
    counts = headcount(region_id, buildings)
    total = counts["villagers"]
    if total <= 0:
        return []
    n_build = counts["buildings"]

    named = named_for(region_id)[:total]
    # A named NPC may already be a child — Pel is, and is the only one. He
    # counts against the children quota rather than on top of it, or Python
    # Village grows a fourth child nobody asked for.
    named_children = sum(1 for nid in named
                         if quests.NPCS[nid].get("sprite") == "child")
    want_children = max(0, counts["children"] - named_children)

    roster: list = []
    for nid in named:
        roster.append(_named_record(nid))
    # Children before adults among the unnamed, so a two-building waystation
    # whose quota is one child actually gets one.
    filler = total - len(roster)
    for i in range(filler):
        child = i < want_children
        roster.append(_unnamed_record(region_id, s, i, child))

    out = []
    for i, who in enumerate(roster):
        vid = "%s-vil-%02d" % (region_id, i)
        child = who["sprite"] == "child"
        # BOTH SEXES, IN EVERY VILLAGE, BY CONSTRUCTION.
        #
        # The design doc says `body = hash(id) & 1`. I first wrote that it
        # risked an all-one-sex waystation; I measured it, and it does not —
        # but for a worse reason than it working. A villager id ends in a
        # sequential counter, and FNV-1a's low bit is a parity of the input
        # bytes, so `hash(id) & 1` does not flip a coin down the roster, it
        # ALTERNATES, mechanically, in every one of the sixteen villages. It
        # also never varies: the id carries no seed, so a player's second save
        # would hold the identical sixteen villages, sex for sex.
        #
        # So the split is kept even on purpose instead of by accident, and the
        # phase is drawn from (region, seed) so that a new save is a new
        # village. Same one hash, same guarantee the brief asked for — "male
        # and female sprites interacting like a village" — and a reason that
        # survives somebody changing the id format.
        phase = 0 if _unit(_key(region_id, s, "body")) < 0.5 else 1
        body = BODY_TYPES[(i + phase) % 2]
        rec = {
            "id": vid,
            "npc": who["npc"],
            "name": who["name"],
            "role": who["role"],
            "sprite": who["sprite"],
            "register": who["register"],
            "line": who["line"],
            "speaks": who["speaks"],
            "child": child,
            "body": body,
            # `sprites.heroFrame` draws a villager as a hero with no weapon.
            # Its own comment says so; this is that call, spelled out.
            "weapon": None,
            "palette": _palette(region_id, s, vid, who),
            "building": i % max(1, n_build),
            "box": {"dx": -1, "dy": -1, "w": BOX, "h": BOX},
            # `duty` is overwritten to "activity" for the few people the
            # activity claims. Their waypoints STAY on the record even so:
            # `reduced_motion` hides the activity, and somebody whose only
            # position was a station would have nowhere to stand when it did.
            "duty": "walk",
            "station": None,
            "speed_px_s": VILLAGER_SPEED,
            "waypoints": _waypoints(region_id, s, vid, child),
        }
        rec["home"] = {"dx": rec["waypoints"][0]["dx"],
                       "dy": rec["waypoints"][0]["dy"]}
        rec["facing"] = rec["waypoints"][0]["face"]
        out.append(rec)
    return out


def _assign_actors(roster: list, act: dict, spec: dict) -> None:
    """Pull the activity's actors out of the walking crowd.

    UNNAMED FIRST, always. A named villager standing at a fixed station is
    still reachable — `speaks` does not change — but the thirty-four written
    people are the ones a player walks up to, and a village where all of them
    are frozen at a snowball fight is a village with nobody in it.
    """
    want = int(spec.get("actors") or 0)
    if want <= 0:
        return
    need = min(want, int(spec.get("min_actors") or 0))
    kind = spec.get("actor_kind")
    order = {v["id"]: i for i, v in enumerate(roster)}
    rank = lambda v: (v["npc"] is not None, order[v["id"]])

    preferred = sorted((v for v in roster
                        if (v["child"] if kind == "child" else not v["child"])),
                       key=rank)
    take = preferred[:want]

    # THE TOP-UP, AND WHY IT EARNS ITS LINES.
    #
    # Section 7.1 gives a two-building waystation four villagers and exactly
    # ONE child, and section 7.4 puts a snowball FIGHT in Twin Pointer Pass,
    # which is a two-building waystation. Clamping to the children present is
    # arithmetically tidy and produces a child throwing a snowball at nobody in
    # the one region the player named by name. So a reciprocal activity borrows
    # whoever else is standing about — a parent in the snow is a village; one
    # child alone in the snow is a bug.
    if len(take) < need:
        chosen = {v["id"] for v in take}
        for v in sorted((v for v in roster if v["id"] not in chosen), key=rank):
            take.append(v)
            if len(take) >= need:
                break

    for n, v in enumerate(take):
        station = STATION_RING[n % len(STATION_RING)]
        v["duty"] = "activity"
        v["station"] = dict(station)
        v["facing"] = station["face"]
        act["actors"].append(v["id"])


def village(region_id: str, seed=0, buildings: int = None) -> dict:
    """THE PAYLOAD. One village, complete, ready to serialise.

    Everything a renderer needs and nothing it has to decide. Read the module
    docstring for the offset-to-pixel formula; read `reduced_motion` for what
    to switch off when the player has asked for stillness.
    """
    region = world.REGION_BY_ID.get(region_id) or {}
    s = _seed_int(seed)
    counts = headcount(region_id, buildings)
    folk = villagers(region_id, s, buildings)
    act = activity(region_id, s, buildings)
    spec = activity_for(region_id)
    if folk:
        _assign_actors(folk, act, spec)
    return {
        "region": region_id,
        "name": region.get("name", region_id),
        "biome": region.get("biome", ""),
        "seed": s,
        "settled": bool(folk),
        "buildings": counts["buildings"],
        "count": len(folk),
        "children": sum(1 for v in folk if v["child"]),
        "adults": sum(1 for v in folk if not v["child"]),
        "named": sum(1 for v in folk if v["npc"]),
        "villagers": folk,
        "activity": act,
        # The contract, restated on the wire so a renderer never has to come
        # back to this file to find out what a dx means.
        "anchor": {
            "space": "tile-offset-from-building",
            "formula": "px = ((origin.x + dx) + 0.5) * tile",
            "building_is": "index into the region's building markers, in the "
                           "order placeMarkers pushed them",
            "tile": TILE,
            # Which origin a given dx/dy is measured from. Anything carrying
            # `anchor: "plaza"` resolves against activity.plaza; everything
            # else on a villager resolves against that villager's `building`.
            "frames": {
                "building": ["villager.box", "villager.home",
                             "villager.waypoints[].", "activity.plaza"],
                "plaza": ["villager.station", "activity.particles[]"],
            },
            "plaza_origin": "the building named by activity.plaza.building, "
                            "offset by activity.plaza.dx/dy",
        },
        "speed_px_s": VILLAGER_SPEED,
        "pause_s": [PAUSE_MIN, PAUSE_MAX],
        "tick_hz": TICK_HZ,
        "particle_cap": PARTICLE_CAP,
        # Section 7.5, spelled out per part rather than as one boolean, because
        # "suppress all of it" does not say whether a villager vanishes or
        # merely stops. Nobody vanishes: they hold waypoint 0 on frame 0, which
        # is what `overworld.js` already does to the companion under the same
        # flag.
        "reduced_motion": {"activity": "hide", "walk": "freeze",
                           "emote": "freeze", "hold_waypoint": 0, "frame": 0},
    }


def region_payload(regions=None, seed=0) -> list:
    """Every region's village, in `world.REGIONS` order.

    Copies throughout: `world.REGIONS` is shared module state and a village
    written into it in place would be one village for every later caller.
    """
    rows = list(regions) if regions is not None else list(world.REGIONS)
    return [village(r["id"] if isinstance(r, dict) else str(r), seed)
            for r in rows]


# ---------------------------------------------------------------------------
# SELF CHECK
# ---------------------------------------------------------------------------
def self_check(seed=1234) -> dict:
    """Prove the table and the generator agree with the design and with the
    renderer's budget. Returns problems by name; `ok` is the only thing a
    caller needs to look at."""
    problems: dict = {
        "biomes_unplaced": [], "unknown_motion": [], "unknown_sprite": [],
        "sprite_too_big": [], "over_particle_cap": [], "unknown_emote": [],
        "empty_village": [], "no_activity": [], "single_sex": [],
        "bad_waypoint": [], "actorless": [], "under_min_actors": [],
    }

    biomes = sorted({r["biome"] for r in world.REGIONS})
    for biome in biomes:
        if biome not in ACTIVITIES:
            problems["biomes_unplaced"].append(biome)

    asked = set()
    for biome, spec in sorted(ACTIVITIES.items()):
        if spec["motion"] not in MOTIONS:
            problems["unknown_motion"].append("%s:%s" % (biome, spec["motion"]))
        if spec["kind"]:
            asked.add(spec["kind"])
            if spec["kind"] not in ACTIVITY_SPRITES:
                problems["unknown_sprite"].append("%s:%s" % (biome, spec["kind"]))
            size = spec["size"] or [0, 0]
            if size[0] > SPRITE_MAX_W or size[1] > SPRITE_MAX_H:
                problems["sprite_too_big"].append("%s:%dx%d"
                                                  % (biome, size[0], size[1]))
        if (spec["particles"] or 0) > PARTICLE_CAP:
            problems["over_particle_cap"].append("%s:%d" % (biome, spec["particles"]))

    for region in world.REGIONS:
        rid = region["id"]
        pay = village(rid, seed)
        if not has_village(rid):
            continue
        if pay["count"] <= 0:
            problems["empty_village"].append(rid)
            continue
        if pay["children"] <= 0:
            problems["empty_village"].append(rid + ":no-children")
        if pay["named"] <= 0:
            problems["empty_village"].append(rid + ":no-named")
        if pay["activity"]["motion"] == "none":
            problems["no_activity"].append(rid)
        spec = ACTIVITIES[region["biome"]]
        got = len(pay["activity"]["actors"])
        if spec["actors"] and not got:
            problems["actorless"].append(rid)
        if got < min(spec["actors"], spec["min_actors"]):
            problems["under_min_actors"].append(
                "%s:%d<%d" % (rid, got, spec["min_actors"]))
        if len({v["body"] for v in pay["villagers"]}) < 2:
            problems["single_sex"].append(rid)
        for v in pay["villagers"]:
            cells = [(w["dx"], w["dy"]) for w in v["waypoints"]]
            if len(set(cells)) != WAYPOINTS:
                problems["bad_waypoint"].append(v["id"] + ":repeat")
            for cell in cells:
                if cell not in HOME_CELLS:
                    problems["bad_waypoint"].append("%s:%s" % (v["id"], cell))
            for w in v["waypoints"]:
                if w["emote"] not in EMOTE_KEYS:
                    problems["unknown_emote"].append("%s:%s" % (v["id"], w["emote"]))

    missing_sprites = sorted(set(ACTIVITY_SPRITES) - asked)
    ok = not any(problems.values()) and not missing_sprites
    return {
        "ok": ok,
        "biomes": len(biomes),
        "activities": len(ACTIVITIES),
        "settlements": sum(1 for r in world.REGIONS if has_village(r["id"])),
        "buildings": sum(BUILDING_COUNT.values()),
        "population": sum(headcount(r["id"])["villagers"] for r in world.REGIONS),
        "sprites_asked": sorted(asked),
        "sprites_unused": missing_sprites,
        "problems": {k: v for k, v in problems.items() if v},
    }
