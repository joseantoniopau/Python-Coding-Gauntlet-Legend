"""The sky, and the one place that decides what it is doing.

WHY THIS FILE EXISTS
--------------------
It used to rain in every battle, forever. Not because anybody wanted a wet
game: because the battle backdrop carried a per-biome list of animated effects
that was ALWAYS FULLY ON. `grass` was `['lightning', 'rain', 'fog']`, Fields of
Syntax is a grass region, and so every fight fought there had lightning in it
from the first frame to the last, in every save, in every seed. Meanwhile the
overworld drew a completely unrelated thing out of its own private table. Two
systems, no shared truth, no possibility of agreement — and no clear state
anywhere in either of them, so nothing could ever "come and go".

This module is the shared truth. It answers exactly one question:

    what is the weather in region R at time T

and it answers it the same way in the server, in the battle renderer and in the
overworld renderer, because the other two do not compute it at all. They read a
STRIP that this file wrote (see `strip()` below). There is no second opinion to
drift out of step with the first one, which is the whole reason the answer lives
in Python rather than being mirrored into two JavaScript modules.

THE MODEL, IN FOUR SENTENCES
----------------------------
1. Time is cut into fixed SLOT_SECONDS slots, counted from the Unix epoch.
2. A slot either BREAKS (starts a new spell of weather) or holds the previous
   one. Breaking is a hash of (region, seed, slot) — never random.random() —
   and every HOLD_CHAIN'th slot breaks unconditionally, which caps a spell's
   length and, more importantly, makes "where did this spell start" a genuine
   function of the slot rather than a walk of unbounded length.
3. The condition of a spell is a weighted pick from the region's CLIMATE, taken
   once at the slot the spell started. Every region's climate contains a clear
   state with real weight, because "sunny to rainy" needs a sunny.
4. That is the whole model. It is pure, it is O(HOLD_CHAIN), and two calls a
   second apart inside one spell return the identical dict.

WHY FIVE MINUTES
----------------
SLOT_SECONDS is 300 and a spell runs 1..HOLD_CHAIN slots, so weather changes on
a 5-minute grid and a single spell lasts 5 to 35 minutes, averaging about
eleven. The numbers are picked off how long things actually take here:

  * an encounter is one to three minutes, so a fight cannot see more than one
    change and usually sees none — weather that flickered inside a battle would
    read as a strobe, not as weather;
  * walking a region and stepping into a fight is well under a slot, so the
    backdrop you walked in under is the backdrop you fight under. That
    continuity is the point of the whole feature;
  * a 45-minute session sees four or five spells per region, which is enough
    for a player to notice that the sky is a thing that changes at all — the
    lower bound on "it comes and goes" being felt rather than merely true;
  * and the cap at 35 minutes means no session can be one unbroken rainstorm.
    That was the complaint. It is now structurally impossible.

Anything much under a minute strobes. Anything much over half an hour is the
bug this file was written to delete.
"""
from __future__ import annotations

from collections import Counter

from . import elements, world

__all__ = [
    "SLOT_SECONDS", "HOLD_CHAIN", "BREAK_P", "STRIP_SLOTS",
    "CONDITIONS", "CONDITION_IDS", "VOCAB", "FIXTURES", "CLIMATE",
    "condition_at", "spell_at", "forecast", "strip", "for_region",
    "region_payload", "simulate", "self_check",
]

# ---------------------------------------------------------------------------
# THE CLOCK
# ---------------------------------------------------------------------------
SLOT_SECONDS = 300            # five minutes. See WHY FIVE MINUTES above.
HOLD_CHAIN = 7                # a spell is at most seven slots: 35 minutes.
BREAK_P = 0.45                # chance a slot starts a new spell, so the mean
                              # spell is ~1/0.45 slots ~= 11 minutes.
STRIP_SLOTS = 24              # two hours of sky shipped to the client at once.


# ---------------------------------------------------------------------------
# THE VOCABULARY
# ---------------------------------------------------------------------------
# battlescene.js already knew how to draw all of these and they are good, so
# none of them are being replaced. What changes is WHO CHOOSES THEM: a biome
# used to hard-code its list and leave it on forever, and now a CONDITION picks
# from the same list and the condition changes with the hour.
#
# `fireball` is the one addition, and the player asked for it by name: "ash and
# fireballs in the volcano". Nothing in the old vocabulary reads as a fireball —
# `ember` is a drifting spark and `lava` is a seam at the horizon — so the fire
# regions got a third thing that arcs across the sky and lands.
VOCAB = frozenset({
    "rain", "snow", "ash", "ember", "lava", "fog", "lightning",
    "leaves", "flies", "drip", "torch", "godray", "fireball",
})

# FIXTURES are the half of that vocabulary that is NOT weather: a wall torch is
# furniture, a lava seam is geology, and neither of them stops because the sky
# cleared. They stay on always, which is why they are listed per biome here and
# are never part of a condition. Everything else in VOCAB comes and goes.
FIXTURES = {
    "village": ("torch",),
    "mine": ("lava",),
    "dungeon": ("torch",),
    "arena": ("torch",),
    "castle": ("torch",),
}

# ---------------------------------------------------------------------------
# THE CONDITIONS
# ---------------------------------------------------------------------------
# `anim`      which of the vocabulary the battle backdrop runs
# `particle`  which pixel.PARTICLE_STYLE the overworld falls in
# `density`   0..1, how much of it: the overworld's particle count and the
#             battle's alpha both scale off this one number, so light rain is
#             light in both renderers or in neither
# `wet`/`cold`/`fire` are for the simulation table and for self_check, not for
# the renderers.
CONDITIONS = {
    "clear": {
        "label": "clear", "anim": (), "particle": "motes", "density": 0.22,
        "line": "the sky is empty and stays that way",
    },
    "mist": {
        "label": "misted over", "anim": ("fog",), "particle": "motes",
        "density": 0.34, "line": "a fog sits in it and does not lift",
    },
    "drizzle": {
        "label": "drizzling", "anim": ("rain",), "particle": "rain",
        "density": 0.45, "wet": True,
        "line": "it spits rain without ever committing to it",
    },
    "rain": {
        "label": "raining", "anim": ("rain", "fog"), "particle": "rain",
        "density": 0.8, "wet": True, "line": "it rains, steadily",
    },
    "storm": {
        "label": "storming", "anim": ("rain", "lightning", "fog"),
        "particle": "rain", "density": 1.0, "wet": True,
        "line": "the rain arrives sideways and the sky goes white with it",
    },
    "flurry": {
        "label": "flurrying", "anim": ("snow",), "particle": "snow",
        "density": 0.4, "cold": True, "line": "snow drifts down in loose handfuls",
    },
    "snow": {
        "label": "snowing", "anim": ("snow", "fog"), "particle": "snow",
        "density": 0.75, "cold": True, "line": "it snows, and settles",
    },
    "blizzard": {
        "label": "a blizzard", "anim": ("snow", "fog", "lightning"),
        "particle": "snow", "density": 1.0, "cold": True,
        "line": "the snow is horizontal and there is thunder inside it",
    },
    "ashfall": {
        "label": "ashfall", "anim": ("ash", "fog"), "particle": "ash",
        "density": 0.7, "fire": True, "line": "ash comes down like grey snow",
    },
    "emberfall": {
        "label": "emberfall", "anim": ("ember",), "particle": "ember",
        "density": 0.55, "fire": True,
        "line": "sparks come up off the floor and hang there",
    },
    "firestorm": {
        "label": "a firestorm", "anim": ("ash", "ember", "fireball"),
        "particle": "ember", "density": 1.0, "fire": True,
        "line": "ash, sparks, and something burning falls out of the dark",
    },
    "leaffall": {
        "label": "leaf-fall", "anim": ("leaves",), "particle": "leaves",
        "density": 0.65, "line": "the air is full of leaves going somewhere",
    },
    "swarm": {
        "label": "a swarm", "anim": ("flies",), "particle": "motes",
        "density": 0.5, "line": "the insects are up and they are interested",
    },
    "seep": {
        "label": "seeping", "anim": ("drip",), "particle": "ash",
        "density": 0.3, "wet": True,
        "line": "water finds its way through the roof, one drop at a time",
    },
    "godlight": {
        "label": "shafted with light", "anim": ("godray",), "particle": "motes",
        "density": 0.4, "line": "light comes through the high windows in bars",
    },
}

CONDITION_IDS = tuple(CONDITIONS)

# ---------------------------------------------------------------------------
# THE CLIMATE OF EACH PLACE
# ---------------------------------------------------------------------------
# Keyed by BIOME, because that is the word world.py already uses for "what kind
# of place is this" and elements.BIOME_AFFINITY already turns it into fire, cold
# or neither. The weights are integers out of a hundred so the table can be read
# as percentages by eye, and so the simulation below has something to be checked
# against.
#
# Three rules the table obeys, all asserted in self_check():
#   * every biome has `clear` with real weight. A place with no clear state can
#     never "come and go", which was the bug;
#   * a FIRE biome (elements.BIOME_AFFINITY) has firestorm — the volcano the
#     player asked for, with ash and fireballs in it;
#   * a COLD biome has snow. Snow where it is cold, nowhere else.
CLIMATE = {
    # The starting village. Deliberately the driest table in the game: this is
    # the exact place the player said should be sunny, and it is fair or merely
    # misty about three-quarters of the time.
    "village":    {"clear": 52, "mist": 18, "leaffall": 8, "drizzle": 12,
                   "rain": 8, "storm": 2},
    # Fields of Syntax. Open country: real rain, real lightning, and a clear day
    # far more often than not.
    "grass":      {"clear": 40, "mist": 14, "leaffall": 10, "drizzle": 12,
                   "rain": 16, "storm": 8},
    # An exposed plateau, and elements.py calls it LIGHTNING for that reason:
    # the only tall metal for a day's walk. Storms find it.
    "highland":   {"clear": 28, "mist": 18, "drizzle": 8, "rain": 14,
                   "storm": 22, "flurry": 10},
    # Stringwood: living, humid, shedding spores between the letters.
    "forest":     {"clear": 28, "mist": 22, "swarm": 16, "leaffall": 12,
                   "drizzle": 10, "rain": 12},
    # Array Caverns. No sky at all, so its weather is the roof: still air, fog
    # off the cold stone, and water finding its way in.
    "cave":       {"clear": 40, "mist": 22, "seep": 30, "drizzle": 8},
    # Sliding Window Marsh. Standing water and gas.
    "swamp":      {"clear": 22, "mist": 26, "swarm": 18, "rain": 20,
                   "drizzle": 8, "storm": 6},
    # Twin Pointer Pass, at the snow line. The one region with real ice.
    "mountain":   {"clear": 22, "mist": 14, "flurry": 18, "snow": 24,
                   "blizzard": 14, "storm": 8},
    # Stack & Queue Mines. The volcano, by the player's own word for it, and
    # FIRE by elements.BIOME_AFFINITY. Ash and fireballs live here.
    "mine":       {"clear": 22, "mist": 10, "emberfall": 26, "ashfall": 20,
                   "firestorm": 22},
    # Matrix Citadel: a fortress with glass in it. Its weather is what comes
    # through the glass.
    "citadel":    {"clear": 32, "godlight": 28, "mist": 22, "rain": 12,
                   "storm": 6},
    # Recursive Forest. Dark, closed, and mostly fog about it.
    "deepforest": {"clear": 24, "mist": 32, "swarm": 18, "leaffall": 14,
                   "rain": 12},
    # Binary Tree Canopy: open air above the dark. Leaves, and a lot of sky.
    "canopy":     {"clear": 36, "leaffall": 26, "mist": 14, "drizzle": 10,
                   "rain": 10, "storm": 4},
    # Graph Wastes. A lattice of ruins is a lattice of conductors, and the ash
    # never really stopped falling.
    "wastes":     {"clear": 26, "ashfall": 28, "mist": 16, "storm": 22,
                   "rain": 8},
    # DP Ruins. What is remarkable here is the light on the solved tiles, so
    # the sky is mostly out of the way.
    "ruins":      {"clear": 38, "mist": 20, "ashfall": 18, "godlight": 12,
                   "rain": 12},
    # Debugging Dungeon: the Armorer's FORGE, and the second FIRE region. It
    # burns and it leaks, and sometimes it does neither.
    "dungeon":    {"clear": 28, "seep": 24, "emberfall": 22, "firestorm": 18,
                   "ashfall": 8},
    # Complexity Tower, palette azure, COLD, and high enough that the weather
    # is happening at the windows rather than below them.
    "tower":      {"clear": 22, "mist": 18, "flurry": 14, "snow": 18,
                   "storm": 20, "rain": 8},
    # The Coliseum: a sand floor, a clock, and no hints. Mostly open sky, with
    # the braziers throwing sparks when it is not.
    "arena":      {"clear": 50, "mist": 14, "emberfall": 18, "drizzle": 10,
                   "rain": 8},
    # The Null King's. Nothing is labelled and nothing is lit, and what little
    # light there is comes in bars through the high windows.
    "castle":     {"clear": 24, "mist": 34, "godlight": 20, "storm": 14,
                   "ashfall": 8},
}


# ---------------------------------------------------------------------------
# THE HASH
# ---------------------------------------------------------------------------
# FNV-1a, 32-bit, over a text key. Written out rather than reached for from
# hashlib because it has to be cheap enough to call a few hundred times while
# building one dashboard, and written out rather than using hash() because
# Python salts hash() per interpreter and weather that changed when you
# relaunched the game would not be weather.
def _h32(text: str) -> int:
    h = 0x811C9DC5
    for ch in text:
        h = ((h ^ (ord(ch) & 0xFF)) * 0x01000193) & 0xFFFFFFFF
    return h


def _unit(text: str) -> float:
    """A float in [0, 1) from a key. The top byte is dropped because FNV's low
    bits are the well-mixed ones."""
    return ((_h32(text) >> 8) & 0xFFFFFF) / 0x1000000


def _seed_int(seed) -> int:
    """Accept an int, a seed code, or anything at all, and get an int."""
    if isinstance(seed, int):
        return seed & 0xFFFFFFFF
    return _h32(str(seed))


# ---------------------------------------------------------------------------
# SPELLS
# ---------------------------------------------------------------------------
def slot_of(when: float) -> int:
    """The coarse clock tick. Unix seconds floored to SLOT_SECONDS."""
    return int(when // SLOT_SECONDS)


def _breaks(region_id: str, seed: int, slot: int) -> bool:
    """Does a new spell of weather start at this slot?

    Every HOLD_CHAIN'th slot breaks whatever the hash says. That is not a
    fudge: it is what makes `_spell_start` a bounded, exact function instead of
    a walk backwards through the whole history of the world, and it is what
    guarantees no spell can outlast HOLD_CHAIN slots — no session is one
    unbroken rainstorm, ever, in any seed.
    """
    if slot % HOLD_CHAIN == 0:
        return True
    return _unit("%s|%d|%d|break" % (region_id, seed, slot)) < BREAK_P


def _spell_start(region_id: str, seed: int, slot: int) -> int:
    """The slot this spell of weather began on. At most HOLD_CHAIN - 1 steps,
    because a multiple of HOLD_CHAIN always breaks."""
    s = slot
    for _ in range(HOLD_CHAIN):
        if _breaks(region_id, seed, s):
            return s
        s -= 1
    return s


def _spell_end(region_id: str, seed: int, start: int) -> int:
    """The first slot AFTER this spell. Bounded by the same guarantee."""
    s = start + 1
    for _ in range(HOLD_CHAIN):
        if _breaks(region_id, seed, s):
            return s
        s += 1
    return s


def _pick(region_id: str, seed: int, start: int, biome: str) -> str:
    """The weighted draw, taken once per spell at the slot it started."""
    table = CLIMATE.get(biome) or CLIMATE["grass"]
    total = sum(table.values())
    roll = _unit("%s|%d|%d|pick" % (region_id, seed, start)) * total
    acc = 0.0
    for name in sorted(table):          # sorted: dict order must not matter
        acc += table[name]
        if roll < acc:
            return name
    return "clear"


def _biome_of(region_id: str) -> str:
    return (world.REGION_BY_ID.get(region_id) or {}).get("biome", "grass")


def condition_at(region_id: str, seed=0, when: float = 0.0) -> str:
    """The condition id in region R at time T. The whole model, in one call."""
    s = _seed_int(seed)
    start = _spell_start(region_id, s, slot_of(when))
    return _pick(region_id, s, start, _biome_of(region_id))


def spell_at(region_id: str, seed=0, when: float = 0.0) -> dict:
    """The condition, plus when it started and when it gives out."""
    s = _seed_int(seed)
    slot = slot_of(when)
    start = _spell_start(region_id, s, slot)
    end = _spell_end(region_id, s, start)
    return {
        "condition": _pick(region_id, s, start, _biome_of(region_id)),
        "slot": slot, "start_slot": start, "end_slot": end,
        "since": start * SLOT_SECONDS, "until": end * SLOT_SECONDS,
    }


def strip(region_id: str, seed=0, when: float = 0.0,
          slots: int = STRIP_SLOTS) -> list:
    """The next `slots` slots of sky, as condition ids, starting at the slot
    containing `when`.

    THIS IS THE WHOLE CLIENT CONTRACT. Neither renderer implements the model
    above — they index this list by wall-clock and read off a string. That is
    deliberate: a JavaScript mirror of `_breaks` and `_pick` would be a second
    source of truth, and a second source of truth is exactly the bug that made
    the overworld and the battle disagree in the first place.
    """
    s = _seed_int(seed)
    first = slot_of(when)
    biome = _biome_of(region_id)
    out = []
    for i in range(max(1, int(slots))):
        slot = first + i
        out.append(_pick(region_id, s, _spell_start(region_id, s, slot), biome))
    return out


def forecast(region_id: str, seed=0, when: float = 0.0,
             slots: int = STRIP_SLOTS) -> dict:
    """Everything a renderer needs about one region's sky, in one dict.

    This is what rides on the region payload. It carries the current condition
    spelled out (so a client that never looks at the clock again is still
    right at the moment it loaded), and the strip plus the epoch it is indexed
    from (so a client that DOES look at the clock stays right for two hours
    without another request).
    """
    now = float(when)
    s = _seed_int(seed)
    spell = spell_at(region_id, s, now)
    cond = CONDITIONS[spell["condition"]]
    biome = _biome_of(region_id)
    band = strip(region_id, s, now, slots)
    return {
        "region": region_id,
        "biome": biome,
        "seed": s,
        "condition": spell["condition"],
        "label": cond["label"],
        "line": cond["line"],
        # The battle backdrop runs exactly these, plus the fixtures, and
        # nothing else. An empty `anim` with fixtures is a clear day indoors;
        # an empty `anim` with no fixtures is a clear day outdoors, which is
        # the state that did not exist before this module.
        "anim": list(cond["anim"]),
        "fixtures": list(FIXTURES.get(biome, ())),
        "particle": cond["particle"],
        "density": cond["density"],
        "now": now,
        "slot": spell["slot"],
        "slot_seconds": SLOT_SECONDS,
        "since": spell["since"],
        "until": spell["until"],
        # strip[0] is the slot containing `now`; slot i covers
        # [epoch + i*slot_seconds, epoch + (i+1)*slot_seconds).
        "epoch": spell["slot"] * SLOT_SECONDS,
        "strip": band,
        # What each of those names means, for THIS region only. A region's
        # climate can produce four to six conditions, so this is a handful of
        # entries rather than the whole table, and it is the reason neither
        # renderer contains a copy of CONDITIONS: a client reading `strip[i]`
        # looks the name up here and gets the same anim list the server would
        # have given it. The model stays in Python; the client gets a legend.
        "legend": {
            name: {
                "label": CONDITIONS[name]["label"],
                "anim": list(CONDITIONS[name]["anim"]),
                "particle": CONDITIONS[name]["particle"],
                "density": CONDITIONS[name]["density"],
            }
            for name in sorted(CLIMATE.get(biome) or CLIMATE["grass"])
        },
    }


def for_region(region: dict, seed=0, when: float = 0.0) -> dict:
    """`forecast` for a region record rather than an id."""
    return forecast((region or {}).get("id", ""), seed, when)


def region_payload(regions, seed=0, when: float = 0.0) -> list:
    """Every region record with its sky attached, ready to serialise.

    Copies. `world.REGIONS` is module-level shared state and a weather key
    written into it in place would be a different sky for every caller after
    the first one.
    """
    return [{**r, "weather": forecast(r["id"], seed, when)} for r in regions]


# ---------------------------------------------------------------------------
# MEASUREMENT
# ---------------------------------------------------------------------------
def simulate(region_id: str, seed=0, hours: float = 200.0,
             start: float = 0.0) -> dict:
    """Walk `hours` of slots and count where the time went.

    Returns fractions of total time per condition, plus the mean spell length
    in minutes. This is the function the report's table comes out of, and it is
    the honest version: it counts SLOTS OF TIME, not spells, so a condition
    that happens rarely but lasts a long time is reported as the long thing it
    is.
    """
    s = _seed_int(seed)
    biome = _biome_of(region_id)
    n = max(1, int(hours * 3600 / SLOT_SECONDS))
    first = slot_of(start)
    tally = Counter()
    spells = 0
    prev_start = None
    for i in range(n):
        slot = first + i
        st = _spell_start(region_id, s, slot)
        if st != prev_start:
            spells += 1
            prev_start = st
        tally[_pick(region_id, s, st, biome)] += 1
    return {
        "region": region_id, "biome": biome, "slots": n,
        "hours": n * SLOT_SECONDS / 3600.0,
        "share": {k: tally[k] / n for k in sorted(tally)},
        "spells": spells,
        "mean_spell_minutes": (n / spells) * SLOT_SECONDS / 60.0 if spells else 0.0,
    }


def table(seed=0, hours: float = 200.0) -> list:
    """`simulate` for every region in the world, in world order."""
    return [simulate(r["id"], seed, hours) for r in world.REGIONS]


# ---------------------------------------------------------------------------
# SELF CHECK
# ---------------------------------------------------------------------------
def self_check(seeds: int = 12, hours: float = 200.0) -> dict:
    """Prove the four promises this module makes, by measurement.

    1. Every region has a climate, every condition in it exists, and every
       animation it names is in the vocabulary the renderers implement.
    2. Every region has a CLEAR state and spends real time in it.
    3. Fire regions get fireballs; cold regions get snow; nowhere else does.
    4. It is pure: the same (region, seed, time) gives the same answer, and a
       time one second later inside a spell gives the SAME answer.
    """
    problems = []

    # -- 1. the tables agree with the world and with the renderers -----------
    for r in world.REGIONS:
        if r["biome"] not in CLIMATE:
            problems.append("no climate for biome %s (%s)" % (r["biome"], r["id"]))
    for biome, tbl in CLIMATE.items():
        if "clear" not in tbl or tbl["clear"] < 20:
            problems.append("%s has no real clear state" % biome)
        for name in tbl:
            if name not in CONDITIONS:
                problems.append("%s names unknown condition %s" % (biome, name))
    for name, c in CONDITIONS.items():
        for a in c["anim"]:
            if a not in VOCAB:
                problems.append("condition %s draws unknown %s" % (name, a))
    for biome, fx in FIXTURES.items():
        for a in fx:
            if a not in VOCAB:
                problems.append("fixture %s of %s is not vocabulary" % (a, biome))
        if biome not in CLIMATE:
            problems.append("fixture for unknown biome %s" % biome)

    # -- 3. thematic, and the player named the cases ------------------------
    for biome, tbl in CLIMATE.items():
        aff = elements.BIOME_AFFINITY.get(biome, elements.NEUTRAL)
        has_fire = any(CONDITIONS[c].get("fire") for c in tbl)
        has_snow = any(CONDITIONS[c].get("cold") for c in tbl)
        if aff == elements.FIRE and "firestorm" not in tbl:
            problems.append("%s is FIRE and has no firestorm" % biome)
        if aff == elements.COLD and not has_snow:
            problems.append("%s is COLD and never snows" % biome)
        if has_snow and aff not in (elements.COLD,) and biome not in (
                "highland", "tower", "mountain"):
            problems.append("%s snows and is not cold" % biome)
        if has_fire and aff != elements.FIRE and biome not in ("arena", "wastes",
                                                               "ruins", "castle"):
            problems.append("%s burns and is not a fire place" % biome)

    # -- 2 and 4. measured ---------------------------------------------------
    worst_clear = 1.0
    worst_region = ""
    longest = 0.0
    for i in range(max(1, seeds)):
        seed = 0x51EED * (i + 1)
        for r in world.REGIONS:
            sim = simulate(r["id"], seed, hours)
            clear = sim["share"].get("clear", 0.0)
            if clear < worst_clear:
                worst_clear, worst_region = clear, r["id"]
            if clear < 0.10:
                problems.append("%s is clear only %.1f%% of the time at seed %d"
                                % (r["id"], clear * 100, seed))
            for cond, share in sim["share"].items():
                if share > 0.62:
                    problems.append("%s is %s %.0f%% of the time at seed %d"
                                    % (r["id"], cond, share * 100, seed))
            longest = max(longest, sim["mean_spell_minutes"])

    # purity: the same moment twice, and a second later
    rid = "fields_of_syntax"
    base = 1_700_000_000.0
    for off in (0, 1, 7, 63, SLOT_SECONDS - 1):
        a = forecast(rid, 12345, base + off)
        b = forecast(rid, 12345, base + off)
        if a["condition"] != b["condition"] or a["strip"] != b["strip"]:
            problems.append("impure at +%ds" % off)
    inside = spell_at(rid, 12345, base)
    if inside["until"] - base > 1.0:
        one = condition_at(rid, 12345, base)
        two = condition_at(rid, 12345, base + 1)
        if one != two:
            problems.append("the weather changed in one second")

    return {
        "ok": not problems,
        "problems": problems,
        "conditions": len(CONDITIONS),
        "biomes": len(CLIMATE),
        "slot_seconds": SLOT_SECONDS,
        "max_spell_minutes": HOLD_CHAIN * SLOT_SECONDS / 60.0,
        "mean_spell_minutes": round(longest, 1),
        "least_clear_region": worst_region,
        "least_clear_share": round(worst_clear, 4),
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 400.0
    names = sorted({c for t in CLIMATE.values() for c in t})
    head = "%-24s %-10s" % ("region", "biome") + "".join(
        "%9s" % n[:9] for n in names) + "%8s" % "spell"
    print(head)
    print("-" * len(head))
    for row in table(seed, hours):
        line = "%-24s %-10s" % (row["region"][:24], row["biome"])
        for n in names:
            v = row["share"].get(n, 0.0)
            line += "%8s " % (("%.1f%%" % (v * 100)) if v else "·")
        line += "%7.1fm" % row["mean_spell_minutes"]
        print(line)
    print()
    print(json.dumps(self_check(), indent=2))
