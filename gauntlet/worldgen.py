"""A world that is different every run, and a curriculum that is not.

The request behind this module was "randomise the world so each playthrough is
completely different, while still incorporating the main story and all the
lessons". Those two halves pull against each other, and resolving that pull is
the entire job here. The resolution is a division of the world into three
layers:

  THE ARGUMENT   — what a place teaches. Never random. `hashmap_highlands`
                   teaches HASH_MAP in every seed that has ever existed, because
                   the corpus, the bestiary, the dungeon rules and the boss
                   taunts are all keyed to that fact. Moving it would not be
                   variety, it would be a bug with a nice name.

  THE ARRANGEMENT— what order you meet things in, and how they connect. Random,
                   but only along edges the dependency graph leaves free. The
                   chapter order is a real topological sort of the curriculum
                   DAG derived from `skills.PREREQUISITES`; the route graph is a
                   rank-monotone spanning tree, so you can never arrive somewhere
                   through a door that skips its prerequisite.

  THE DRESSING   — biome, palette, route names, which mentor greets you, where
                   the pets hide, boss affixes, loot weights, which optional
                   quests are on the board. Free to move. This is where most of
                   the felt difference lives, and it costs the curriculum nothing.

Three things are pinned across every seed and are asserted in `self_check`:

  1. THE LESSON SET. Every skill in `skills.SKILLS` is introduced by some chapter,
     and every chapter in `curriculum.CHAPTERS` appears exactly once, in an order
     where each skill's prerequisites are introduced no later than the skill
     itself. This is enforced by construction (Kahn's algorithm over the derived
     DAG) and proved afterwards by re-deriving the constraint and checking it.

  2. THE MAIN STORY. The eleven beats of docs/09-story-bible.md §2 fire in order,
     one per chapter position. The chapter at position 4 changes with the seed;
     the fact that THE OBLIGING HAND is offered there does not.

  3. THE RAMP. Positions 0-2 are drawn only from the gentle chapters, so the
     first hour is GUIDED/TUTORIAL/EASY regardless of seed. Reordering the middle
     is safe for a second reason worth stating: difficulty tiers are gated
     per-skill by evidence (`curriculum.TIER_GATES`), not by chapter number, so an
     early `order` chapter opens the topic without opening HARD problems.

A seed is a 32-bit integer with a shareable text form ("K7P4-2QX"). Every
sub-decision draws from its own named stream, so adding a feature later perturbs
only that feature and old seeds keep most of their shape.

Nothing here mutates any other module. `generate()` returns a plain, frozen
description; integration is the caller's business. The obvious seams:

  * `WorldSpec.routes` replaces `progression.ROUTES` for a run.
  * `WorldSpec.region_order()` replaces the static prerequisite list in
    `world.unlocked_regions`.
  * `build_dungeon()` returns a real `dungeons.Dungeon` for a spec.
  * `WorldSpec.slot_label` is what the save slot shows.

Run it: `python -m gauntlet.worldgen 12345` for one world card,
`python -m gauntlet.worldgen --check 300` for the proof over many seeds.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, replace

from . import curriculum, skills as skillmod, world

# Imported for their tables only; none of these are called at import time.
from . import dungeons as dungeonmod
from . import items as itemmod
from . import pets as petmod
from . import progression
from . import quests as questmod

# ---------------------------------------------------------------------------
# Seeds
# ---------------------------------------------------------------------------
#
# 32 bits: small enough to read aloud, large enough that two players comparing
# worlds are comparing different worlds. blake2b rather than hash(), because
# hash() is salted per interpreter and a seed has to survive a relaunch.

SEED_BITS = 32
SEED_MASK = (1 << SEED_BITS) - 1

# Crockford base32: no I, L, O or U, so a seed read over a phone survives the
# reading. Seven symbols cover 35 bits, which covers 32 with room over.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {ch: i for i, ch in enumerate(_ALPHABET)}
_DECODE.update({"I": 1, "L": 1, "O": 0, "U": 0})


def seed_text(seed: int) -> str:
    """The shareable form. Grouped, because unbroken seven-symbol strings get
    miscopied and a world you cannot hand to someone else is half a feature."""
    value = int(seed) & SEED_MASK
    out = []
    for _ in range(7):
        out.append(_ALPHABET[value & 31])
        value >>= 5
    coded = "".join(reversed(out))
    return f"{coded[:4]}-{coded[4:]}"


def parse_seed(value) -> int:
    """Accept an int, a decimal string, a seed code, or any text at all.

    The last case is deliberate: "my birthday" and "chapter 9 hurt" are both
    valid seeds. They hash rather than fail, because a seed box that rejects
    input is a seed box nobody uses.
    """
    if isinstance(value, int):
        return value & SEED_MASK
    text = str(value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text) & SEED_MASK
    compact = text.replace("-", "").replace(" ", "").upper()
    if len(compact) == 7 and all(ch in _DECODE for ch in compact):
        out = 0
        for ch in compact:
            out = (out << 5) | _DECODE[ch]
        return out & SEED_MASK
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & SEED_MASK


def _rng(seed: int, label: str) -> random.Random:
    """One independent stream per decision, keyed by name.

    Drawing everything from a single sequential Random would mean that adding a
    new decision anywhere reshuffles every decision after it, and every seed
    anyone had written down would build a different world.
    """
    digest = hashlib.blake2b(f"{seed & SEED_MASK}:{label}".encode("utf-8"),
                             digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


# ---------------------------------------------------------------------------
# The curriculum DAG — the constraint everything else has to live inside
# ---------------------------------------------------------------------------

CHAPTER_IDS: tuple = tuple(c.id for c in curriculum.CHAPTERS)
CANONICAL_INDEX = {cid: i for i, cid in enumerate(CHAPTER_IDS)}

FINAL_CHAPTER = "gauntlet"

# Chapters gentle enough to open a run with. The first three positions come only
# from here, which is what keeps the first hour inside the band.
GENTLE_CHAPTERS = ("fluency", "structures", "idiom", "counting")
GENTLE_PREFIX = 3

# Four skills are named by a chapter's prose and its corpus families but not by
# its `skills` or `patterns` tuples, so a purely derived map would leave them
# homeless and "every skill is taught" would quietly become false. They are
# pinned here rather than in curriculum.py because this is the module that makes
# the claim and therefore the module that owes the receipt.
#
#   GREEDY        — the corpus has no GREEDY pattern at all; the greedy material
#                   lives in the interval and sorting families, which `order`
#                   claims. Flagged again in self_check under
#                   `skills_without_corpus_pattern`.
#   COMMUNICATION — explanation phases, which `craft` is built around.
#   SPEED, RECALL — the Coliseum and the castle: chapter XI by definition.
_PINNED_INTRO = {
    "GREEDY": "order",
    "COMMUNICATION": "craft",
    "SPEED": FINAL_CHAPTER,
    "RECALL": FINAL_CHAPTER,
}


def _build_introduces() -> dict:
    """skill -> id of the chapter that first teaches it.

    Preference order: an explicit `skills` entry, then a `patterns` entry (an
    empty `patterns` tuple means "everything is permitted" and teaches nothing
    new, so it is skipped), then the pins above.
    """
    intro: dict = {}
    for chapter in curriculum.CHAPTERS:
        for name in chapter.skills:
            intro.setdefault(name, chapter.id)
    for chapter in curriculum.CHAPTERS:
        for pattern in chapter.patterns:
            name = skillmod.PATTERN_TO_SKILL.get(pattern)
            if name:
                intro.setdefault(name, chapter.id)
    for name, chapter_id in _PINNED_INTRO.items():
        intro.setdefault(name, chapter_id)
    return intro


INTRODUCES: dict = _build_introduces()

SKILLS_BY_CHAPTER: dict = {cid: tuple(sorted(s for s, c in INTRODUCES.items()
                                             if c == cid))
                           for cid in CHAPTER_IDS}


def _build_chapter_deps() -> dict:
    """Two ordering laws, both read out of existing tables rather than restated,
    so that editing the skill graph re-shapes every future world by itself.

    USES   — a chapter that trains a skill some earlier chapter introduces must
             come after it. Without this rule the two pass-through chapters
             (III Idioms and IV Counting introduce nothing of their own) float
             free of the graph and a seed can legally open on Counting, which is
             chapter IV difficulty handed to somebody on their first day. Only
             `Chapter.skills` counts here, never `Chapter.patterns`: patterns say
             what is PERMITTED in a chapter, not what it teaches, and reading
             them as teaching would make III depend on VI for listing SORTING.

    STANDS ON — a chapter that introduces a skill must come after whichever
             chapter introduces that skill's prerequisites.
    """
    deps: dict = {cid: set() for cid in CHAPTER_IDS}
    for chapter in curriculum.CHAPTERS:
        for skill in chapter.skills:
            owner = INTRODUCES.get(skill)
            if owner and owner != chapter.id:
                deps[chapter.id].add(owner)
    for skill, chapter_id in INTRODUCES.items():
        for prereq in skillmod.PREREQUISITES.get(skill, ()):
            owner = INTRODUCES.get(prereq)
            if owner and owner != chapter_id:
                deps[chapter_id].add(owner)
    # XI is "everything at once, on a clock". It is last by definition, not by
    # luck, so the finale depends on the whole book.
    deps[FINAL_CHAPTER] |= {cid for cid in CHAPTER_IDS if cid != FINAL_CHAPTER}
    return {cid: frozenset(v) for cid, v in deps.items()}


CHAPTER_DEPS: dict = _build_chapter_deps()


def chapter_order(seed: int) -> tuple:
    """A random topological order of the chapter DAG, with the ramp pinned.

    Kahn's algorithm with a seeded pick among the ready set. Two extra rules,
    both of them content rules rather than dependency rules:
      * while fewer than GENTLE_PREFIX chapters are placed, only gentle chapters
        are eligible (if any gentle chapter is ready at all);
      * the finale is held back while anything else is ready.
    """
    rng = _rng(seed, "chapter-order")
    remaining = set(CHAPTER_IDS)
    placed: list = []
    while remaining:
        done = set(placed)
        ready = sorted(cid for cid in remaining if CHAPTER_DEPS[cid] <= done)
        if not ready:                       # unreachable unless the DAG cycles
            raise ValueError("curriculum dependency graph has a cycle")
        if len(placed) < GENTLE_PREFIX:
            gentle = [cid for cid in ready if cid in GENTLE_CHAPTERS]
            ready = gentle or ready
        if len(remaining) > 1:
            held = [cid for cid in ready if cid != FINAL_CHAPTER]
            ready = held or ready
        pick = rng.choice(ready)
        placed.append(pick)
        remaining.discard(pick)
    return tuple(placed)


# ---------------------------------------------------------------------------
# Regions, and which chapter first sends you to one
# ---------------------------------------------------------------------------

def _build_region_chapter() -> dict:
    """region id -> the earliest chapter with business there.

    Two sources disagree in places and both are right about something:
    `curriculum.Chapter.region` names the chapter's home, and a dungeon plan's
    `chapter` names what the building drills. The earlier of the two is what
    decides when the region can first be reached — the Coliseum, for instance, is
    chapter XI's home but its under-arena is craft-tier content, and a player who
    can do craft-tier work has no business being kept out of the door.
    """
    owner: dict = {}

    def claim(region_id: str, chapter_id: str) -> None:
        rank = CANONICAL_INDEX.get(chapter_id)
        if rank is None or region_id not in world.REGION_BY_ID:
            return
        held = owner.get(region_id)
        if held is None or rank < CANONICAL_INDEX[held]:
            owner[region_id] = chapter_id

    for chapter in curriculum.CHAPTERS:
        claim(chapter.region, chapter.id)
    for plan in dungeonmod.DUNGEONS:
        claim(plan.region, plan.chapter)
    for region in world.REGIONS:
        owner.setdefault(region["id"], CHAPTER_IDS[0])
    return owner


REGION_CHAPTER: dict = _build_region_chapter()

START_REGION = "python_village"          # the Margin. Beat I happens here, always.
FINAL_REGION = "null_kings_castle"

# How far up the ladder one open road is allowed to carry you. Every chapter
# position has at least one region, so a parent within this span always exists
# and the cap never has to be relaxed. It keeps the map readable: you arrive in
# new country from the country next to it, not from four chapters away.
MAX_OPEN_SPAN = 2

# Biomes shuffle only inside a terrain family. Free permutation across all
# seventeen produces a tower in a swamp and reads as noise; permutation inside a
# family produces a genuinely different-looking map that still makes sense when
# you walk it. Three biomes are pinned: the village you wake in, the Coliseum,
# and the castle.
BIOME_FAMILIES = (
    ("grass", "highland", "swamp", "mountain", "wastes"),
    ("forest", "deepforest", "canopy"),
    ("cave", "mine", "dungeon", "ruins"),
    ("citadel", "tower"),
)
PINNED_BIOMES = {"python_village": "village", "coding_coliseum": "arena",
                 FINAL_REGION: "castle"}
PINNED_PALETTES = {FINAL_REGION: "void"}

ROUTE_KINDS = ("road", "stair", "tunnel", "ferry", "climb", "drop", "burrow")
# Which crossings a biome can plausibly offer. Route flavour is dressing, but
# dressing that contradicts the picture on screen is worse than no dressing.
BIOME_ROUTE_KINDS = {
    "village": ("road", "stair"), "grass": ("road", "ferry"),
    "highland": ("road", "climb"), "swamp": ("ferry", "road"),
    "mountain": ("climb", "stair", "drop"), "wastes": ("road", "burrow"),
    "forest": ("road", "burrow"), "deepforest": ("burrow", "road"),
    "canopy": ("climb", "drop"), "cave": ("tunnel", "drop"),
    "mine": ("tunnel", "stair"), "dungeon": ("stair", "tunnel"),
    "ruins": ("stair", "burrow"), "citadel": ("stair", "road"),
    "tower": ("stair", "climb"), "arena": ("road", "stair"),
    "castle": ("stair", "drop"),
}

_ROUTE_ADJECTIVE = ("Long", "Sunk", "Quiet", "Cold", "Broken", "Old", "Narrow",
                    "Blind", "Grey", "Last", "Wide", "Bitter", "Patient", "Thin")
_ROUTE_NOUN = {
    "road": ("Road", "Cartway", "Run"), "stair": ("Stair", "Ascent", "Steps"),
    "tunnel": ("Tunnel", "Adit", "Throat"), "ferry": ("Crossing", "Ferry", "Wade"),
    "climb": ("Climb", "Face", "Ladder"), "drop": ("Drop", "Fall", "Shaft"),
    "burrow": ("Burrow", "Warren", "Cut"),
}


# ---------------------------------------------------------------------------
# World character — the part the player actually feels
# ---------------------------------------------------------------------------
#
# Randomness that averages out is indistinguishable from no randomness. A seed
# therefore draws a CHARACTER: a small set of global multipliers pulled hard in
# one direction, plus a weaker UNDERCURRENT pulled in another. The pair is named,
# and the name goes on the save slot, because a run you can describe in four
# words is a run worth starting again.

@dataclass(frozen=True)
class Mods:
    danger: float = 1.0          # enemy pressure and route danger
    loot: float = 1.0            # rarity weighting on drops
    dungeons: float = 1.0        # how many optional dungeons are open
    towns: float = 1.0           # settlements, shops, repair benches
    quests: float = 1.0          # optional quest offers
    index: float = 1.0           # Green Index sightings
    affixes: float = 1.0         # boss modifiers per boss
    phases: float = 1.0          # boss phase count
    lateral: float = 1.0         # side roads between regions of similar rank
    hidden: float = 1.0          # shortcuts that skip rank
    mentors: float = 1.0         # mentor availability

    def blend(self, other: "Mods", weight: float) -> "Mods":
        """Fold an undercurrent in at partial strength."""
        out = {}
        for name in self.__dataclass_fields__:
            a = getattr(self, name)
            b = getattr(other, name)
            out[name] = round(a * (1.0 - weight) + b * weight, 4)
        return Mods(**out)


@dataclass(frozen=True)
class Character:
    id: str
    name: str                    # what the save slot says
    epithet: str                 # what the undercurrent line says
    blurb: str
    mods: Mods
    weight: int = 10


WORLD_CHARACTERS: tuple = (
    Character(
        id="even_grain", name="An Even Grain", epithet="an even grain",
        blurb="Nothing is unusually wrong. Given the state of the world, that is "
              "itself unusual.",
        mods=Mods(), weight=14),
    Character(
        id="harrow", name="A Harrowed World", epithet="a harrowing",
        blurb="Everything out here bites harder, and everything out here is "
              "carrying something worth taking off it.",
        mods=Mods(danger=1.45, loot=1.5, towns=0.85, quests=0.9, affixes=1.4),
        weight=11),
    Character(
        id="fracture", name="A Fractured World", epithet="a fracture",
        blurb="The land came apart along its seams. More holes in it than "
              "settlements, and the holes go down a long way.",
        mods=Mods(dungeons=1.6, towns=0.6, hidden=1.7, lateral=0.8, danger=1.15),
        weight=11),
    Character(
        id="haunting", name="A Haunted Run", epithet="a haunting",
        blurb="The small green sphere keeps turning up. In pockets. In wells. "
              "In the hands of people who did not have it a moment ago.",
        mods=Mods(index=2.4, danger=1.1, quests=1.15, affixes=1.2), weight=10),
    Character(
        id="long_green", name="A Long Green Season", epithet="a long green season",
        blurb="The erasure took the nouns and left the weather. Roads are open, "
              "people are talking, and there is more asked of you than done to you.",
        mods=Mods(quests=1.5, towns=1.35, danger=0.8, loot=0.9, dungeons=0.75,
                  lateral=1.3), weight=10),
    Character(
        id="quiet", name="A Quiet World", epithet="a quiet",
        blurb="Long roads between few things. What is out there is deep rather "
              "than plentiful.",
        mods=Mods(quests=0.7, dungeons=0.85, towns=0.8, lateral=0.6, hidden=1.2,
                  phases=1.3, loot=1.2), weight=9),
    Character(
        id="rust", name="A Rusting World", epithet="a rusting",
        blurb="The King's machines got here first and are still running, badly, "
              "on instructions nobody has read in two generations.",
        mods=Mods(affixes=1.6, phases=1.35, danger=1.25, loot=1.15, towns=0.9),
        weight=9),
    Character(
        id="choir", name="A World Still Teaching", epithet="a standing choir",
        blurb="More of the Fellowship survived here. They are tired, they are "
              "outnumbered, and they still hold office hours.",
        mods=Mods(mentors=1.6, quests=1.25, danger=0.85, phases=0.85), weight=9),
    Character(
        id="wide_margin", name="A Wide Margin", epithet="a wide margin",
        blurb="The erasure was sloppy here. Whole side roads were missed, and "
              "they connect places that should not be one walk apart.",
        mods=Mods(lateral=1.8, hidden=1.5, towns=1.15, dungeons=1.1), weight=9),
    Character(
        id="tally", name="A World Kept Counting", epithet="a long tally",
        blurb="Fewer things, and each of them takes longer. The bosses here have "
              "been waiting, and they have prepared.",
        mods=Mods(phases=1.5, affixes=1.3, quests=0.8, dungeons=0.8, loot=1.3),
        weight=8),
)

CHARACTER_BY_ID = {c.id: c for c in WORLD_CHARACTERS}
UNDERCURRENT_WEIGHT = 0.4        # how much of the second character actually lands


def _pick_character(rng: random.Random, exclude: str = "") -> Character:
    pool = [c for c in WORLD_CHARACTERS if c.id != exclude]
    total = sum(c.weight for c in pool)
    roll = rng.uniform(0, total)
    for character in pool:
        roll -= character.weight
        if roll <= 0:
            return character
    return pool[-1]


# ---------------------------------------------------------------------------
# Boss affixes
# ---------------------------------------------------------------------------
#
# Named, because "+15% HP" is not a memory and "the Unerased Hash Titan" is.
# Every affix is a real failure mode of the pattern it is attached to rather than
# a stat line, so learning to beat one is learning something.

@dataclass(frozen=True)
class Affix:
    id: str
    name: str
    line: str
    effect: dict


AFFIXES: tuple = (
    Affix("unerased", "Unerased",
          "It keeps a name the erasure missed, and heals when you use the wrong one.",
          {"hp": 1.2, "wrong_incantation_heal": 0.05}),
    Affix("doubled", "Doubled",
          "Two of it. They take turns, and they do not share a health bar.",
          {"phases": 1, "hp": 0.7}),
    Affix("patient", "Patient",
          "It will not act until you do. It has been waiting longer than you "
          "have been alive.",
          {"clock": 0.8, "hint_cost": 1.5}),
    Affix("off_by_one", "Off-By-One",
          "Every trial it sets you is the neighbouring case of the one it states.",
          {"edge_bias": 1.0}),
    Affix("indexed", "Indexed",
          "A green sphere sits where its heart should be. It knows where you "
          "have been.",
          {"index_sighting": 1, "loot": 1.25}),
    Affix("mutable", "Mutable",
          "It remembers every attempt you have made against it, including the ones "
          "you abandoned.",
          {"retest_bias": 1.0, "hp": 1.1}),
    Affix("jawless", "Jawless",
          "It states nothing. You are expected to work out what is being asked.",
          {"unlabelled": 1.0, "loot": 1.4}),
    Affix("quick", "Quickened",
          "It moves on the half-beat. The target time is the target time.",
          {"clock": 0.7, "loot": 1.2}),
    Affix("armoured", "Plated",
          "Glancing Python does nothing to it. Only the idiom it exists for lands.",
          {"glance": 0.0, "hp": 1.15}),
    Affix("brittle", "Brittle",
          "Whatever holds it together stopped being maintained. One clean cast "
          "does disproportionate work.",
          {"signature_damage": 1.6, "hp": 0.8}),
    Affix("chorused", "Chorused",
          "It repeats its own taunt one clause deeper each time it is hit.",
          {"phases": 1, "explain_required": 1.0}),
    Affix("starving", "Starving",
          "It feeds on restarts. Every abandoned run is a health potion.",
          {"abandon_heal": 0.1, "loot": 1.3}),
    Affix("cold", "Cold",
          "No pets speak in this room. Whatever you know, you know alone.",
          {"pets_silenced": 1.0, "loot": 1.5}),
    Affix("recursive", "Recursive",
          "Beating it opens a smaller copy of it, which is also the way out.",
          {"phases": 1, "xp": 1.35}),
)

AFFIX_BY_ID = {a.id: a for a in AFFIXES}

# Phase composition. `implement` is not optional — a boss you can beat without
# writing anything is not this game. The others are drawn, and then a repair pass
# guarantees each kind survives somewhere in the world so that no seed can quietly
# delete, say, every complexity duel.
PHASE_KEYS: tuple = tuple(p["key"] for p in world.BOSS_PHASES)
PHASE_BY_KEY = {p["key"]: p for p in world.BOSS_PHASES}
REQUIRED_PHASE = "implement"
FIRST_PHASE = "recognize"
LAST_PHASE = "variant"
MIN_PHASE_OCCURRENCES = 2        # per phase kind, across the whole world


# ---------------------------------------------------------------------------
# Timing model
# ---------------------------------------------------------------------------
#
# HONESTY NOTE, because this is the number most easily fudged: there is no
# telemetry in this repository. The only per-encounter times that exist are the
# corpus's authored `target_seconds`, and `estimated_seconds` is currently a copy
# of them. The constants below are those authored means, scaled by a single
# published factor for a cleared first attempt. They are an estimate and are
# labelled as one everywhere they surface. `calibrate()` replaces them with real
# recorded solve times the moment a save file has any.

# Mean authored `target_seconds` per difficulty, measured over the corpus itself
# rather than typed here by hand, rounded to the nearest whole second.
# Re-derived after rematch_variants: 1018 problems, of which GUIDED 258,
# TUTORIAL 215, EASY 321, MEDIUM 199, HARD 25. The five changed contracts add
# three MEDIUM targets of 900 seconds and two HARD targets of 1500 seconds.
# Their resulting means are 795.0 and 1443.6 seconds; the gentle bands do not
# change. These remain authored time budgets, not observed player solve times.
#
# ELITE and BOSS have no authored problems at all — the fourteen bosses are
# assembled from ordinary corpus problems by `finalexam` and `world.BOSS_PHASES`,
# so those two rows are `schema.TARGET_SECONDS` defaults and are marked as such
# by `measured_corpus_means()`, which is what a caller should prefer.
CORPUS_MEAN_TARGET = {
    "GUIDED": 114, "TUTORIAL": 179, "EASY": 385, "MEDIUM": 795, "HARD": 1444,
    "ELITE": 1500, "BOSS": 2100,
}
CLEARED_FRACTION_OF_TARGET = 0.72   # a clear usually lands inside its own budget
FAILED_FRACTION_OF_CLEAR = 0.55     # a failed attempt is shorter than a clear
CLEAR_RATE = 0.70                   # attempts that clear, at the gates the ramp sets

OVERHEAD_SECONDS = 40               # walking to it, reading it, the dialogue round it
QUEST_OVERHEAD_SECONDS = 150        # accept, travel, turn-in, the llama's closer
DUNGEON_ROOM_SECONDS = 55           # non-encounter rooms: doors, treasure, lore
DUNGEON_ROOM_VISIT_RATE = 0.62      # of a floor plan, what a player actually walks
DUNGEON_ENCOUNTER_RATE = 0.45       # of the rooms walked, what fights
STORY_BEAT_SECONDS = 150            # a spine beat, read at reading speed
BOSS_PHASE_SECONDS = 300            # one phase of one boss

GAUNTLET_CLEARS = 12                # chapter XI's graduate_clears is a 999 sentinel

TARGET_HOURS = 10.0                 # what was asked for


def encounter_seconds(difficulty: str) -> float:
    """Estimated wall time for one cleared encounter at this difficulty."""
    base = CORPUS_MEAN_TARGET.get(difficulty, CORPUS_MEAN_TARGET["EASY"])
    return base * CLEARED_FRACTION_OF_TARGET


def measured_corpus_means(corpus=None) -> dict:
    """The real mean `target_seconds` per difficulty, read off the corpus.

    `CORPUS_MEAN_TARGET` above is a transcription of this, kept as a literal so
    the timing model does not have to load the corpus to answer a question about
    a seed. This function is what proves the transcription is still true, and
    `tests/test_coverage.py` fails if the two drift apart.

    Returns {difficulty: {"mean", "count"}}; difficulties with no authored
    problems are absent rather than zero, because a mean of nothing is not zero.
    """
    if corpus is None:
        from .corpus import ensure
        corpus = ensure()
    totals: dict = {}
    for problem in corpus:
        entry = totals.setdefault(problem.difficulty, [0, 0])
        entry[0] += problem.target_seconds
        entry[1] += 1
    return {name: {"mean": total / count, "count": count}
            for name, (total, count) in totals.items() if count}


def calibrate(samples: dict) -> dict:
    """Replace the estimate with measurement.

    `samples` maps difficulty -> a list of real recorded solve seconds, which is
    exactly what `SkillState.solve_times` accumulates. Returns the new table and
    installs it. Anything not measured keeps its estimate, and the report says
    which is which.
    """
    updated, source = {}, {}
    for name, default in CORPUS_MEAN_TARGET.items():
        values = sorted(float(v) for v in samples.get(name, ()) if v)
        if len(values) >= 5:
            mid = len(values) // 2
            median = (values[mid] if len(values) % 2
                      else (values[mid - 1] + values[mid]) / 2.0)
            updated[name] = median / CLEARED_FRACTION_OF_TARGET
            source[name] = f"measured (n={len(values)})"
        else:
            updated[name] = float(default)
            source[name] = "authored estimate"
    CORPUS_MEAN_TARGET.update(updated)
    return {"table": dict(CORPUS_MEAN_TARGET), "source": source}


# The difficulty mix a chapter is served at, by its POSITION in the seeded order
# rather than by its identity — which is what makes reordering safe. Position 0
# is somebody's first ten minutes with Python no matter which chapter landed
# there; position 9 is somebody who has been playing for eight hours.
POSITION_MIX = (
    {"GUIDED": 0.45, "TUTORIAL": 0.40, "EASY": 0.15},
    {"GUIDED": 0.20, "TUTORIAL": 0.40, "EASY": 0.40},
    {"TUTORIAL": 0.30, "EASY": 0.60, "MEDIUM": 0.10},
    {"TUTORIAL": 0.15, "EASY": 0.60, "MEDIUM": 0.25},
    {"TUTORIAL": 0.10, "EASY": 0.60, "MEDIUM": 0.30},
    {"EASY": 0.55, "MEDIUM": 0.40, "HARD": 0.05},
    {"EASY": 0.45, "MEDIUM": 0.45, "HARD": 0.10},
    {"EASY": 0.40, "MEDIUM": 0.48, "HARD": 0.12},
    {"EASY": 0.35, "MEDIUM": 0.50, "HARD": 0.15},
    {"EASY": 0.30, "MEDIUM": 0.50, "HARD": 0.20},
    {"EASY": 0.25, "MEDIUM": 0.50, "HARD": 0.25},
)

# The gentle band the first hour has to land inside, whatever the seed did.
GENTLE_BAND = {
    "max_difficulty": "EASY",       # nothing harder inside the first hour
    "min_encounters": 12,           # and not four long slogs either
    "max_single_seconds": 420.0,
    "no_boss_before_seconds": 2400.0,
    # A dungeon reachable in the first hour is fine — the Half-Written Barrow is
    # three floors of chapter-I drill and belongs there. What is not fine is one
    # whose rooms cannot relent below MEDIUM, because a player an hour old will
    # walk in and be handed a chapter-VI problem by a corridor.
    "max_dungeon_floor": "EASY",
}
_TIER_RANK = {name: i for i, name in enumerate(curriculum.TIERS)}


# ---------------------------------------------------------------------------
# The spine — eleven beats, in order, in whatever world this seed built
# ---------------------------------------------------------------------------
#
# docs/09-story-bible.md §2. One beat per chapter position, so the beat that
# fires fifth fires fifth in every seed; only the ground it happens on moves.

@dataclass(frozen=True)
class Beat:
    number: int
    key: str
    title: str
    line: str
    position: int = 0
    chapter: str = ""
    region: str = ""


SPINE: tuple = (
    Beat(1, "margin", "THE MARGIN",
         "You wake in a place too small to have been worth erasing. You can name "
         "three things. Past the fence there are no nouns left."),
    Beat(2, "messenger", "THE MESSENGER",
         "Vail comes out of a torn place in the sky, wounded, carrying paper. The "
         "paper is code in your handwriting from a future you have not lived."),
    Beat(3, "running", "WHAT VAIL WAS RUNNING FROM",
         "Vail dies. The pages keep arriving. Vail sent them ahead, knowing."),
    Beat(4, "obliging_hand", "THE OBLIGING HAND",
         "The King offers you the gauntlet in person, sincerely. It solves "
         "anything. Each use decays the skill it solved. Nobody stops you."),
    Beat(5, "repository", "THE GREY REPOSITORY",
         "A jawless stone vault-face in the middle of the world, holding "
         "everything not yet erased. Its door is the last gate."),
    Beat(6, "fellowship", "THE FELLOWSHIP OF THE UNERASED",
         "The surviving mentors, each the last of a discipline. Some of them do "
         "not survive the book."),
    Beat(7, "long_defeat", "THE LONG DEFEAT",
         "You retake a region. It does not stay retaken. They tell you plainly "
         "that this is the shape of it, and keep going."),
    Beat(8, "green_index", "THE GREEN INDEX",
         "The small green sphere is a pointer. It is how the King finds things. "
         "Everyone you met holding it was being indexed."),
    Beat(9, "loop", "THE LOOP",
         "You read NUL-9's source. It is yours. You are the reason there is a "
         "Null King, and Vail knew, and taught you anyway."),
    Beat(10, "no_fate", "NO FATE",
         "It can only return what it already holds. It cannot learn. You can."),
    Beat(11, "naming", "THE NAMING",
         "Every name you gave anything answers back. Then the coda: most of what "
         "was erased stays erased, and you teach someone else to name."),
)

assert len(SPINE) == len(CHAPTER_IDS) == 11

# Where the Green Index has been seen. The bible's rule is that it starts as an
# off-by-one joke in Chapter II and stops being funny; the reveal is beat VIII.
INDEX_IN_A_BOSS = ("in the chest cavity, where a heart would have been "
                   "inconvenient")

INDEX_OCCASIONS = (
    "in a lost-property drawer, filed under a name nobody remembers giving",
    "in a child's game of counting-out, one count short every time",
    "in the palm of someone who has just agreed to help you",
    "at the bottom of a well that was dry last season",
    "in a merchant's change, warm, and not returned when pointed out",
    "on a grave marker, set into the stone where a name would go",
    "in your own pack, under the pages, which you did not put there",
)


# ---------------------------------------------------------------------------
# Spec dataclasses — the output of all of the above
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegionSpec:
    id: str
    name: str
    chapter: str
    position: int                # index of its chapter in this seed's order
    skill: str
    biome: str
    palette: str
    music: str
    mentor: str
    danger: int
    town_tier: int               # 0 = no settlement here at all
    loot: dict                   # rarity -> weight
    loot_floor: str


@dataclass(frozen=True)
class RouteSpec:
    id: str
    name: str
    frm: str
    to: str
    kind: str
    two_way: bool
    danger: int
    hidden: bool
    prose: str


@dataclass(frozen=True)
class DungeonSpec:
    id: str
    name: str
    region: str
    chapter: str
    tier: int
    archetype: str               # dressing: the shape of the floor plan
    rule: str                    # argument: what the building teaches. Never moves.
    size_bonus: int
    layout_seed: int
    required: bool               # the one this chapter cannot lose


@dataclass(frozen=True)
class QuestSpec:
    id: str
    title: str
    region: str
    giver: str
    kind: str
    tier: int
    chain: str
    lesson_bearing: bool
    position: int                # when it comes on the board


@dataclass(frozen=True)
class PetSpec:
    id: str
    name: str
    region: str
    position: int
    hint: str


@dataclass(frozen=True)
class BossSpec:
    id: str
    name: str
    region: str
    skill: str
    problem_id: str
    position: int                # the earliest position it can honestly be fought
    phases: tuple
    affixes: tuple
    hp_scale: float
    final: bool


@dataclass(frozen=True)
class Sighting:
    position: int
    region: str
    occasion: str
    revealing: bool


@dataclass(frozen=True)
class Segment:
    """One chapter position, costed."""
    position: int
    chapter: str
    title: str
    region: str
    clears: int
    attempts: int
    mix: dict
    solve_seconds: float
    overhead_seconds: float
    seconds: float
    cumulative_seconds: float


@dataclass(frozen=True)
class Budget:
    encounters: int
    attempts: int
    bosses: int
    boss_phases: int
    quests: int
    dungeons: int
    dungeon_rooms: int
    dungeon_encounters: int
    solve_seconds: float
    overhead_seconds: float
    boss_seconds: float
    quest_seconds: float
    dungeon_seconds: float
    story_seconds: float
    exposure_hours: float        # meet every chapter and every skill once
    graduation_hours: float      # actually pass every chapter's gates
    full_hours: float            # plus everything optional this seed scheduled
    target_hours: float
    meets_target: bool           # every chapter reached inside target_hours
    at_target: dict              # what `target_hours` actually buys
    verdict: str
    segments: tuple


@dataclass(frozen=True)
class WorldSpec:
    seed: int
    code: str
    character: Character
    undercurrent: Character
    mods: Mods
    character_name: str
    blurb: str
    chapter_order: tuple
    regions: tuple
    routes: tuple
    dungeons: tuple
    quests: tuple
    pets: tuple
    bosses: tuple
    spine: tuple
    sightings: tuple
    first_mentor: str
    index_home: str
    budget: Budget

    # -- lookups the rest of the game will want -----------------------------

    @property
    def slot_label(self) -> str:
        """What the save slot shows. Seed first: it is the shareable part."""
        return f"{self.code} · {self.character_name}"

    @property
    def region_by_id(self) -> dict:
        return {r.id: r for r in self.regions}

    def position_of(self, region_id: str) -> int:
        spec = self.region_by_id.get(region_id)
        return spec.position if spec else 0

    def region_order(self) -> list:
        """Region ids in the order this seed opens them. Drop-in replacement for
        the static prerequisite walk in `world.unlocked_regions`."""
        return [r.id for r in sorted(self.regions, key=lambda r: (r.position, r.id))]

    def routes_from(self, region_id: str) -> list:
        out = []
        for route in self.routes:
            if route.frm == region_id:
                out.append(route)
            elif route.two_way and route.to == region_id:
                out.append(route)
        return out

    def neighbours(self, region_id: str) -> list:
        return [route.to if route.frm == region_id else route.frm
                for route in self.routes_from(region_id)]

    def beat_at(self, position: int):
        for beat in self.spine:
            if beat.position == position:
                return beat
        return None

    def summary(self) -> dict:
        """A flat dict, for the save slot, the world card and the test suite."""
        return {
            "seed": self.seed,
            "code": self.code,
            "character": self.character.id,
            "undercurrent": self.undercurrent.id,
            "character_name": self.character_name,
            "slot_label": self.slot_label,
            "chapter_order": list(self.chapter_order),
            "first_mentor": self.first_mentor,
            "index_home": self.index_home,
            "regions": len(self.regions),
            "routes": len(self.routes),
            "hidden_routes": sum(1 for r in self.routes if r.hidden),
            "towns": sum(1 for r in self.regions if r.town_tier > 0),
            "dungeons": len(self.dungeons),
            "quests": len(self.quests),
            "pets": len(self.pets),
            "bosses": len(self.bosses),
            "sightings": len(self.sightings),
            "graduation_hours": self.budget.graduation_hours,
            "full_hours": self.budget.full_hours,
        }


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _biome_assignment(rng: random.Random) -> dict:
    """Permute biomes inside their terrain family; leave the three pins alone."""
    out = dict(PINNED_BIOMES)
    for family in BIOME_FAMILIES:
        holders = [r["id"] for r in world.REGIONS
                   if r["biome"] in family and r["id"] not in PINNED_BIOMES]
        pool = list(family)
        rng.shuffle(pool)
        for region_id, biome in zip(holders, pool):
            out[region_id] = biome
    for region in world.REGIONS:
        out.setdefault(region["id"], region["biome"])
    return out


def _palette_assignment(rng: random.Random) -> dict:
    out = dict(PINNED_PALETTES)
    holders = [r["id"] for r in world.REGIONS if r["id"] not in PINNED_PALETTES]
    pool = [r["palette"] for r in world.REGIONS
            if r["palette"] not in PINNED_PALETTES.values()]
    rng.shuffle(pool)
    for region_id, palette in zip(holders, pool):
        out[region_id] = palette
    for region in world.REGIONS:
        out.setdefault(region["id"], region["palette"])
    return out


def _loot_table(rank: float, mods: Mods, rng: random.Random) -> tuple:
    """Rarity weights for a region. Deeper regions and harsher worlds tilt the
    curve; the floor rises so that late-game commons stop dropping entirely."""
    weights = {}
    tilt = (0.55 + 0.9 * rank) * mods.loot
    for index, name in enumerate(itemmod.RARITY_ORDER):
        base = itemmod.RARITIES[name]["weight"]
        weights[name] = round(base * (tilt ** index) * rng.uniform(0.9, 1.1), 2)
    floor_index = 0
    if rank > 0.45:
        floor_index = 1
    if rank > 0.75 and mods.loot >= 1.0:
        floor_index = 2
    return weights, itemmod.RARITY_ORDER[floor_index]


def _region_specs(seed: int, order: tuple, mods: Mods) -> tuple:
    biomes = _biome_assignment(_rng(seed, "biomes"))
    palettes = _palette_assignment(_rng(seed, "palettes"))
    rng = _rng(seed, "regions")
    position = {cid: i for i, cid in enumerate(order)}
    span = max(len(order) - 1, 1)

    mentor_pool = list(world.MENTORS)
    rng.shuffle(mentor_pool)

    specs = []
    for index, region in enumerate(world.REGIONS):
        region_id = region["id"]
        chapter = REGION_CHAPTER[region_id]
        pos = position[chapter]
        rank = pos / span
        base_danger = progression.REGION_DANGER.get(region_id, 10)
        danger = max(1, round(base_danger * (0.75 + 0.5 * rank) * mods.danger))
        # Towns thin out in a fractured world and thicken in a green one. The
        # Margin always has one: it is where the player is taught to stand up.
        town_roll = rng.uniform(0, 1) * mods.towns
        if region_id == START_REGION:
            town = 2
        elif region_id == FINAL_REGION:
            town = 0
        else:
            town = 2 if town_roll > 0.72 else 1 if town_roll > 0.34 else 0
        loot, floor = _loot_table(rank, mods, rng)
        mentor = (region["mentor"] if rng.uniform(0, 1) > 0.55 * mods.mentors
                  else mentor_pool[index % len(mentor_pool)])
        specs.append(RegionSpec(
            id=region_id, name=region["name"], chapter=chapter, position=pos,
            skill=region["skill"], biome=biomes[region_id],
            palette=palettes[region_id], music=region["music"], mentor=mentor,
            danger=danger, town_tier=town, loot=loot, loot_floor=floor))
    return tuple(specs)


def _route_name(rng: random.Random, kind: str) -> str:
    return (f"The {rng.choice(_ROUTE_ADJECTIVE)} "
            f"{rng.choice(_ROUTE_NOUN.get(kind, ('Road',)))}")


_HIDDEN_PROSE = (
    "Not on any map that survived. Someone walked it often enough to wear it in.",
    "A way through that the erasure missed because nobody had named it.",
    "It should not connect these two places. It does, and it is shorter.",
)
_OPEN_PROSE = (
    "Cart ruts worn back into use by one person walking them every day.",
    "Passable, watched, and quiet in a way that is not restful.",
    "The old way. Longer than it looks and colder than it should be.",
    "Kept clear by people who will not say who they are keeping it clear for.",
)


def _routes(seed: int, regions: tuple, mods: Mods) -> tuple:
    """A rank-monotone spanning tree, plus laterals, plus shortcuts.

    The tree is the load-bearing part. Every region except the start gets exactly
    one parent whose position is no later than its own, which gives two
    guarantees at once and gives them by construction rather than by testing
    afterwards: the map is connected, and no route can deliver a player into a
    region whose chapter has not opened.
    """
    rng = _rng(seed, "routes")
    by_id = {r.id: r for r in regions}
    # The Margin is the root, then everything else in ladder order with a seeded
    # tiebreak inside each rung. Placing in ladder order is what lets the parent
    # rule below be a simple filter instead of a search.
    ordered = ([by_id[START_REGION]]
               + sorted((r for r in regions if r.id != START_REGION),
                        key=lambda r: (r.position, rng.random())))

    routes: list = []
    edges: set = set()

    def add(frm: str, to: str, *, hidden: bool, two_way: bool) -> None:
        key = tuple(sorted((frm, to)))
        if key in edges or frm == to:
            return
        edges.add(key)
        source = by_id[frm]
        kinds = BIOME_ROUTE_KINDS.get(source.biome, ROUTE_KINDS)
        kind = rng.choice(list(kinds) if not hidden
                          else ["tunnel", "burrow", "drop", "climb"])
        danger = max(1, round((by_id[to].danger + source.danger) / 2
                              * (1.3 if hidden else 1.0)))
        routes.append(RouteSpec(
            id=f"rt_{frm}__{to}" + ("_hidden" if hidden else ""),
            name=_route_name(rng, kind), frm=frm, to=to, kind=kind,
            two_way=two_way, danger=danger, hidden=hidden,
            prose=rng.choice(_HIDDEN_PROSE if hidden else _OPEN_PROSE)))

    placed = [ordered[0]]
    for region in ordered[1:]:
        candidates = [c for c in placed
                      if region.position - MAX_OPEN_SPAN <= c.position
                      <= region.position]
        if not candidates:                  # only possible if a position is empty
            candidates = [c for c in placed if c.position <= region.position] or placed
        # Prefer a parent of adjacent rank: a spanning tree that always hangs off
        # the start region is a star, and a star is not a world.
        weights = [1.0 / (1.0 + (region.position - c.position) ** 2)
                   for c in candidates]
        total = sum(weights)
        roll = rng.uniform(0, total)
        parent = candidates[-1]
        for candidate, weight in zip(candidates, weights):
            roll -= weight
            if roll <= 0:
                parent = candidate
                break
        add(parent.id, region.id, hidden=False, two_way=True)
        placed.append(region)

    # Laterals: extra ways between neighbours of similar rank. Loops in the map.
    lateral_pairs = [(a, b) for i, a in enumerate(regions) for b in regions[i + 1:]
                     if abs(a.position - b.position) <= 1
                     and tuple(sorted((a.id, b.id))) not in edges]
    rng.shuffle(lateral_pairs)
    for a, b in lateral_pairs[:max(0, round(5 * mods.lateral))]:
        add(a.id, b.id, hidden=False, two_way=True)

    # Shortcuts: one-way, dangerous, skipping rank. These are the only edges that
    # reach further than MAX_OPEN_SPAN, and they run one way only, forwards into
    # deeper country. A player who finds one has chosen to go somewhere they are
    # not ready for, which is a different thing from a door that opens on them —
    # and because they are one-way, they can never be the route by which a region
    # becomes reachable in the first place.
    hidden_pairs = [(a, b) for i, a in enumerate(regions) for b in regions[i + 1:]
                    if abs(a.position - b.position) >= 3
                    and tuple(sorted((a.id, b.id))) not in edges]
    rng.shuffle(hidden_pairs)
    for a, b in hidden_pairs[:max(0, round(3 * mods.hidden))]:
        low, high = (a, b) if a.position < b.position else (b, a)
        add(low.id, high.id, hidden=True, two_way=False)

    return tuple(routes)


def _dungeons(seed: int, order: tuple, mods: Mods) -> tuple:
    """Which buildings exist, and what shape they are inside.

    `rule` never moves — the rotating grid is the Matrix Citadel's argument and a
    citadel that does not turn teaches nothing. `archetype` is the floor-plan
    shape and moves freely. Every chapter that has a dungeon plan keeps at least
    one, so a seed can thin the world out but cannot delete a lesson.
    """
    rng = _rng(seed, "dungeons")
    position = {cid: i for i, cid in enumerate(order)}
    by_chapter: dict = {}
    for plan in dungeonmod.DUNGEONS:
        by_chapter.setdefault(plan.chapter, []).append(plan)

    keep: list = []
    for chapter, plans in sorted(by_chapter.items()):
        pool = list(plans)
        rng.shuffle(pool)
        required = pool[0]
        keep.append((required, True))
        for plan in pool[1:]:
            if rng.uniform(0, 1) < min(0.95, 0.6 * mods.dungeons):
                keep.append((plan, False))

    specs = []
    for plan, required in sorted(keep, key=lambda pr: (position.get(pr[0].chapter, 0),
                                                       pr[0].id)):
        archetype = rng.choice(list(dungeonmod.ARCHETYPES))
        size_bonus = rng.choice((-2, 0, 0, 2, 4)) + (2 if mods.dungeons > 1.2 else 0)
        specs.append(DungeonSpec(
            id=plan.id, name=plan.name, region=plan.region, chapter=plan.chapter,
            tier=plan.tier, archetype=archetype, rule=plan.rule,
            size_bonus=size_bonus,
            layout_seed=_rng(seed, f"layout:{plan.id}").getrandbits(32),
            required=required))
    return tuple(specs)


def _lesson_bearing(quest) -> bool:
    """A quest carries a lesson if it hands over something the player cannot get
    elsewhere: an incantation, a codex page, a pet, a shortcut, a town upgrade or
    a set piece. Those are never rolled away."""
    extras = quest.extras or {}
    return bool(quest.chain) or any(key in extras for key in
                                    ("incantation", "codex", "pet", "shortcut",
                                     "town_upgrade", "set_item", "technique"))


def _quests(seed: int, order: tuple, mods: Mods) -> tuple:
    """Which quests are on the board, and who is holding them.

    Honest scope note: 58 of the 74 authored quests belong to chains and are
    always offered, because a chain with a hole in it is a broken short story
    rather than a varied one. The seed varies the 16 standalone offers, recasts
    every giver among the NPCs who actually live in that region, and — the part
    that is genuinely felt — reorders when whole regions' worth of quests arrive,
    because that follows the chapter order.
    """
    rng = _rng(seed, "quests")
    position = {cid: i for i, cid in enumerate(order)}
    npcs_by_region: dict = {}
    for npc_id, npc in questmod.NPCS.items():
        npcs_by_region.setdefault(npc["region"], []).append(npc_id)

    kept_by_region: dict = {}
    specs = []
    for quest in questmod.QUESTS:
        bearing = _lesson_bearing(quest)
        if not bearing:
            keep_p = min(0.95, 0.55 * mods.quests)
            already = kept_by_region.get(quest.region, 0)
            # Every region keeps at least two things to do, whatever the roll.
            if already >= 2 and rng.uniform(0, 1) > keep_p:
                continue
        pool = npcs_by_region.get(quest.region) or [quest.giver]
        giver = quest.giver if rng.uniform(0, 1) > 0.5 else rng.choice(pool)
        chapter = REGION_CHAPTER.get(quest.region, order[0])
        kept_by_region[quest.region] = kept_by_region.get(quest.region, 0) + 1
        specs.append(QuestSpec(
            id=quest.id, title=quest.title, region=quest.region, giver=giver,
            kind=quest.kind, tier=quest.tier, chain=quest.chain or "",
            lesson_bearing=bearing, position=position.get(chapter, 0)))
    return tuple(sorted(specs, key=lambda q: (q.position, q.region, q.id)))


_PET_SIGHTING = (
    "Something has been in the {noun} and left the prints in the wrong order.",
    "Whatever lives out past the {noun} watches the fights and does not join them.",
    "There is a shape in the {noun} that only resolves once you stop looking for it.",
    "Someone has been leaving food by the {noun}, and it keeps being eaten.",
)
_BIOME_NOUN = {
    "village": "cellar", "grass": "hedgerow", "highland": "cairn", "swamp": "reeds",
    "mountain": "scree", "wastes": "ash-drift", "forest": "coppice",
    "deepforest": "deadfall", "canopy": "crown-walk", "cave": "sump",
    "mine": "cart-road", "dungeon": "cell-block", "ruins": "lit tiles",
    "citadel": "west stair", "tower": "third floor", "arena": "under-arena",
    "castle": "unlabelled halls",
}


def _pets(seed: int, regions: tuple) -> tuple:
    """Where the pets hide.

    Two constraints. One per region, so finding one is a reason to go somewhere
    specific; and at least two inside the first four positions, because a
    companion early is part of what makes the first hour gentle.
    """
    rng = _rng(seed, "pets")
    canonical = {row["id"]: row for row in progression.PETS}

    eligible = sorted((r for r in regions
                       if 1 <= r.position <= len(CHAPTER_IDS) - 3),
                      key=lambda r: (r.position, r.id))
    early = [r for r in eligible if r.position <= 4]
    later = [r for r in eligible if r.position > 4]
    rng.shuffle(early)
    rng.shuffle(later)

    pet_ids = list(petmod.PET_IDS)
    rng.shuffle(pet_ids)
    # Front-load two homes from the early band so the player is not alone through
    # the opening, then shuffle everything that is left over the rest of the map.
    rest = early[2:] + later
    rng.shuffle(rest)
    homes = early[:2] + rest

    specs = []
    for pet_id, home in zip(pet_ids, homes):
        pet = petmod.BY_ID[pet_id]
        row = canonical.get(pet_id)
        if row and row["region"] == home.id:
            hint = row["hint"]           # the authored line, when it still fits
        else:
            noun = _BIOME_NOUN.get(home.biome, "treeline")
            hint = rng.choice(_PET_SIGHTING).format(noun=noun)
        specs.append(PetSpec(id=pet_id, name=pet.name, region=home.id,
                             position=home.position, hint=hint))
    return tuple(sorted(specs, key=lambda p: (p.position, p.id)))


def _bosses(seed: int, regions: tuple, order: tuple, mods: Mods) -> tuple:
    """Phase composition and affixes.

    Composition is seeded but not free: `implement` is mandatory, `recognize`
    leads when present and `variant` closes when present, and afterwards a repair
    pass makes sure every phase kind survives at least twice somewhere in the
    world. A seed may make the complexity duel rare. It may not make it extinct.
    """
    rng = _rng(seed, "bosses")
    by_id = {r.id: r for r in regions}
    span = max(len(CHAPTER_IDS) - 1, 1)

    position = {cid: i for i, cid in enumerate(order)}

    drafts = []
    for boss in world.BOSSES:
        region = by_id.get(boss["region"])
        # A boss is gated by its own pattern, not by the ground it stands on. The
        # Three-Sum Hydra sits in the Array Caverns, which a player reaches early,
        # and asks a two-pointer question, which is chapter V work. It wakes when
        # the pattern is taught, and not before: this is the single rule that
        # keeps the ramp gentle no matter how the map came out.
        gate = position.get(INTRODUCES.get(boss["skill"], order[0]), 0)
        where = max(region.position if region else 0, gate)
        rank = where / span
        target = 3 + rank * 2.0 * mods.phases
        optional = [k for k in PHASE_KEYS if k != REQUIRED_PHASE]
        rng.shuffle(optional)
        chosen = {REQUIRED_PHASE}
        for key in optional:
            if len(chosen) >= min(len(PHASE_KEYS), round(target)):
                break
            chosen.add(key)
        if boss.get("final"):
            chosen = set(PHASE_KEYS)     # the Interviewer asks for all of it
        affix_count = max(0, min(3, round((0.4 + rank * 1.4) * mods.affixes)))
        affixes = tuple(a.id for a in rng.sample(list(AFFIXES), affix_count))
        extra = sum(AFFIX_BY_ID[a].effect.get("phases", 0) for a in affixes)
        hp = round((0.85 + rank * 0.5) * mods.danger
                   * _product(AFFIX_BY_ID[a].effect.get("hp", 1.0) for a in affixes), 2)
        drafts.append([boss, chosen, affixes, hp, where])

    # Repair pass: no phase kind may fall below MIN_PHASE_OCCURRENCES.
    for key in PHASE_KEYS:
        while sum(1 for d in drafts if key in d[1]) < MIN_PHASE_OCCURRENCES:
            draft = rng.choice(drafts)
            draft[1].add(key)

    specs = []
    for boss, chosen, affixes, hp, where in drafts:
        specs.append(BossSpec(
            id=boss["id"], name=boss["name"], region=boss["region"],
            skill=boss["skill"], problem_id=boss["problem_id"], position=where,
            phases=_order_phases(chosen), affixes=affixes, hp_scale=hp,
            final=bool(boss.get("final"))))
    return tuple(sorted(specs, key=lambda b: (b.position, b.id)))


def _order_phases(chosen: set) -> tuple:
    """Recognition first, the disguised rematch last, the rest in canonical
    order. A boss that asks you to name the family after you have already
    implemented it is asking a question you have answered."""
    middle = [k for k in PHASE_KEYS if k in chosen
              and k not in (FIRST_PHASE, LAST_PHASE)]
    out = ([FIRST_PHASE] if FIRST_PHASE in chosen else []) + middle
    if LAST_PHASE in chosen:
        out.append(LAST_PHASE)
    return tuple(out)


def _product(values) -> float:
    out = 1.0
    for value in values:
        out *= value
    return out


def _chapter_homes(seed: int, regions: tuple) -> dict:
    """chapter id -> the region its story happens in.

    Six chapters own two regions, so this is a real choice and it moves the
    staging of six of the eleven beats. Position 0 is pinned: beat I is the
    Margin, in every seed, because waking up somewhere else is a different game.
    """
    rng = _rng(seed, "homes")
    grouped: dict = {}
    for region in sorted(regions, key=lambda r: r.id):
        grouped.setdefault(region.chapter, []).append(region.id)
    homes = {}
    for chapter_id, options in grouped.items():
        homes[chapter_id] = rng.choice(options)
    homes[REGION_CHAPTER[START_REGION]] = START_REGION
    return homes


def _spine(seed: int, order: tuple, homes: dict) -> tuple:
    """Attach the eleven beats to the eleven chapter positions.

    Beat k fires at position k in every seed. The region it fires in is whichever
    region the chapter at that position calls home, which is how the arc stays
    fixed while the world it happens in moves.
    """
    out = []
    for index, beat in enumerate(SPINE):
        chapter = order[index]
        out.append(replace(beat, position=index, chapter=chapter,
                           region=homes.get(chapter, START_REGION)))
    return tuple(out)


def _sightings(seed: int, order: tuple, regions: tuple, spine: tuple,
               bosses: tuple, mods: Mods) -> tuple:
    """Green Index appearances.

    The bible's rule: it turns up from Chapter II onward in unconnected places,
    and beat VIII is where it stops being a joke. So there is always at least one
    sighting before the reveal, the reveal itself is always present, and a haunted
    seed simply has the thing following you around.
    """
    rng = _rng(seed, "index")
    at_position: dict = {}
    for region in sorted(regions, key=lambda r: r.id):
        at_position.setdefault(region.position, []).append(region.id)
    reveal = spine[7]

    count = max(3, round(4 * mods.index))
    positions = [p for p in range(1, len(order)) if p != reveal.position]
    rng.shuffle(positions)
    picks = sorted(positions[:count])
    # Guarantee the joke lands before the reveal explains it.
    if not any(p < reveal.position for p in picks):
        picks = sorted(set(picks) | {rng.randint(1, max(1, reveal.position - 1))})

    occasions = list(INDEX_OCCASIONS)
    rng.shuffle(occasions)
    out = [Sighting(position=p,
                    region=rng.choice(at_position.get(p) or [START_REGION]),
                    occasion=occasions[i % len(occasions)], revealing=False)
           for i, p in enumerate(picks)]
    out.append(Sighting(position=reveal.position, region=reveal.region,
                        occasion="in the King's own hand, held up so you can see "
                                 "it is the same one", revealing=True))
    # An Indexed boss is carrying one by definition.
    for boss in bosses:
        if "indexed" in boss.affixes:
            region = next((r for r in regions if r.id == boss.region), None)
            if region:
                out.append(Sighting(position=region.position, region=boss.region,
                                    occasion=INDEX_IN_A_BOSS, revealing=False))
    return tuple(sorted(out, key=lambda s: (s.position, s.region)))


def _first_mentor(seed: int) -> str:
    """Who greets you in the Margin. Restricted to the disciplines that make
    sense on day one — the Chronomancer meeting a player who cannot type yet is
    a joke the game only gets to make once."""
    rng = _rng(seed, "mentor")
    gentle = ("byte", "archivist", "scribe", "armorer", "testsmith")
    return rng.choice([m for m in gentle if m in world.MENTORS])


# ---------------------------------------------------------------------------
# Content budget
# ---------------------------------------------------------------------------

def _mix_for(position: int) -> dict:
    return POSITION_MIX[min(position, len(POSITION_MIX) - 1)]


def _mix_seconds(mix: dict) -> float:
    return sum(share * encounter_seconds(name) for name, share in mix.items())


def _clears_for(chapter_id: str) -> int:
    chapter = curriculum.CHAPTER_BY_ID[chapter_id]
    # XI never graduates by design: its gate is a 999 sentinel meaning "the run
    # ends here". Costing 999 encounters would make the estimate nonsense.
    if chapter.graduate_clears >= 999:
        return GAUNTLET_CLEARS
    return chapter.graduate_clears


def budget_for(order: tuple, homes: dict, dungeons: tuple, quests: tuple,
               bosses: tuple, *, target_hours: float = TARGET_HOURS) -> Budget:
    """How much content this seed schedules, and roughly how long that is.

    Three numbers, because "how long is the game" has three honest answers:

      exposure_hours    — meet every chapter and every skill at least twice. The
                          floor under "all the lessons are in there".
      graduation_hours  — actually pass every chapter's `graduate_mastery` and
                          `graduate_clears` gates. The curriculum's own definition
                          of finishing, and the number to compare against ten.
      full_hours        — graduation plus every optional dungeon, quest and boss
                          this particular seed put on the map.

    All three are estimates built on authored corpus targets. See the honesty
    note on CORPUS_MEAN_TARGET.
    """
    segments: list = []
    solve = overhead = 0.0
    total_clears = total_attempts = 0
    cumulative = 0.0
    exposure_seconds = 0.0

    for position, chapter_id in enumerate(order):
        mix = _mix_for(position)
        clears = _clears_for(chapter_id)
        attempts = max(clears, round(clears / CLEAR_RATE))
        per_clear = _mix_seconds(mix)
        failed = attempts - clears
        seg_solve = clears * per_clear + failed * per_clear * FAILED_FRACTION_OF_CLEAR
        seg_overhead = attempts * OVERHEAD_SECONDS
        seg_total = seg_solve + seg_overhead
        cumulative += seg_total
        segments.append(Segment(
            position=position, chapter=chapter_id,
            title=curriculum.CHAPTER_BY_ID[chapter_id].title,
            region=homes.get(chapter_id, START_REGION),
            clears=clears, attempts=attempts, mix=dict(mix),
            solve_seconds=round(seg_solve, 1),
            overhead_seconds=round(seg_overhead, 1),
            seconds=round(seg_total, 1),
            cumulative_seconds=round(cumulative, 1)))
        solve += seg_solve
        overhead += seg_overhead
        total_clears += clears
        total_attempts += attempts
        # Exposure: two clears per chapter, plus one per skill it introduces.
        exposure_clears = 2 + len(SKILLS_BY_CHAPTER.get(chapter_id, ()))
        exposure_seconds += exposure_clears * (per_clear + OVERHEAD_SECONDS)

    boss_phases = sum(len(b.phases) for b in bosses)
    boss_seconds = boss_phases * BOSS_PHASE_SECONDS
    story_seconds = len(SPINE) * STORY_BEAT_SECONDS

    quest_seconds = len(quests) * QUEST_OVERHEAD_SECONDS
    rooms = 0
    for spec in dungeons:
        plan = dungeonmod.DUNGEON_BY_ID.get(spec.id)
        size = (plan.size if plan else 20) + spec.size_bonus
        rooms += max(8, round(size * DUNGEON_ROOM_VISIT_RATE))
    dungeon_encounters = round(rooms * DUNGEON_ENCOUNTER_RATE)
    dungeon_seconds = (rooms * DUNGEON_ROOM_SECONDS
                       + dungeon_encounters * _mix_seconds(_mix_for(5)))

    graduation = solve + overhead + boss_seconds + story_seconds
    full = graduation + quest_seconds + dungeon_seconds
    exposure = exposure_seconds + story_seconds

    at_target = _pace_plan(segments, boss_seconds, story_seconds,
                           target_hours * 3600.0)
    # If every chapter has to be REACHED inside the target, what would each
    # chapter's clears quota have to shrink to? Reported rather than applied:
    # worldgen does not get to lower the curriculum's gates, it only gets to say
    # what they cost.
    solving = sum(seg.seconds for seg in segments)
    spare = max(0.0, target_hours * 3600.0 - boss_seconds - story_seconds)
    quota_scale = round(min(1.0, spare / max(solving, 1.0)), 3)
    at_target["quota_scale_for_all_chapters"] = quota_scale
    at_target["clears_per_chapter_for_all_chapters"] = round(
        sum(seg.clears for seg in segments) * quota_scale / max(len(segments), 1), 1)
    graduation_hours = round(graduation / 3600.0, 2)
    full_hours = round(full / 3600.0, 2)
    exposure_hours = round(exposure / 3600.0, 2)
    # Deliberately strict: "meets the target" means every chapter is actually
    # reached inside it, not that the target lands somewhere between the floor
    # and the ceiling. A softer definition here would let the verdict below say
    # something true and useless.
    meets = bool(at_target["all_chapters_reached"])

    if target_hours < exposure_hours:
        verdict = (f"{target_hours:g} hours is not enough for this seed: meeting "
                   f"every lesson once costs {exposure_hours:g}h before any "
                   f"repetition at all.")
    elif target_hours > full_hours:
        verdict = (f"This seed runs out of content at {full_hours:g} hours, short "
                   f"of the {target_hours:g} asked for.")
    else:
        verdict = (
            f"Honestly: {target_hours:g} hours is not the whole syllabus on this "
            f"seed. At the curriculum's own gates it reaches chapter "
            f"{at_target['chapters_touched']} of {len(order)} and clears "
            f"{at_target['clears']} of {total_clears} required encounters. "
            f"Reaching all {len(order)} chapters costs {graduation_hours:g}h; "
            f"everything this seed scheduled is {full_hours:g}h. The floor — "
            f"every chapter and every skill met once, with no repetition — is "
            f"{exposure_hours:g}h, so a {target_hours:g}-hour run that covers "
            f"every lesson exists only if the per-chapter clears quota drops to "
            f"{at_target['clears_per_chapter_for_all_chapters']:g} "
            f"(x{at_target['quota_scale_for_all_chapters']:g} of the authored "
            f"gates), which is thinner evidence than the gates were set at on "
            f"purpose.")

    return Budget(
        encounters=total_clears, attempts=total_attempts, bosses=len(bosses),
        boss_phases=boss_phases, quests=len(quests), dungeons=len(dungeons),
        dungeon_rooms=rooms, dungeon_encounters=dungeon_encounters,
        solve_seconds=round(solve, 1), overhead_seconds=round(overhead, 1),
        boss_seconds=round(boss_seconds, 1), quest_seconds=round(quest_seconds, 1),
        dungeon_seconds=round(dungeon_seconds, 1),
        story_seconds=round(story_seconds, 1),
        exposure_hours=exposure_hours, graduation_hours=graduation_hours,
        full_hours=full_hours, target_hours=target_hours, meets_target=meets,
        at_target=at_target, verdict=verdict, segments=tuple(segments))


def _pace_plan(segments, boss_seconds: float, story_seconds: float,
               budget_seconds: float) -> dict:
    """What a fixed number of hours actually buys, walking the ramp in order.

    Bosses and story beats are charged pro rata as the positions they belong to
    are reached, rather than billed up front, because a player who stops at hour
    ten has not fought the Interviewer and should not be charged for him.
    """
    positions = max(len(segments), 1)
    per_position_fixed = (boss_seconds + story_seconds) / positions
    spent = 0.0
    clears = attempts = completed = 0
    for segment in segments:
        cost = segment.seconds + per_position_fixed
        if spent + cost <= budget_seconds:
            spent += cost
            clears += segment.clears
            attempts += segment.attempts
            completed += 1
            continue
        share = max(0.0, (budget_seconds - spent) / cost)
        clears += int(segment.clears * share)
        attempts += int(segment.attempts * share)
        spent = budget_seconds
        break
    return {
        "hours": round(budget_seconds / 3600.0, 2),
        "clears": clears,
        "attempts": attempts,
        "chapters_completed": completed,
        "chapters_touched": min(completed + 1, positions),
        "all_chapters_reached": completed >= positions,
    }


def pace_plan(budget: Budget, hours: float) -> dict:
    """Public form of the above: what `hours` of play gets you on this seed."""
    return _pace_plan(budget.segments, budget.boss_seconds, budget.story_seconds,
                      hours * 3600.0)


def first_hour(spec: "WorldSpec") -> dict:
    """What the first sixty minutes actually contains, and whether it is gentle.

    Built by walking the costed segments and cutting at 3600 seconds, then asking
    the same questions of every seed: nothing above EASY, no single encounter
    longer than seven minutes, enough encounters that it moves, and no boss or
    dungeon arriving before the player has a reason to care.
    """
    budget = spec.budget
    used = 0.0
    encounters = 0
    hardest = "GUIDED"
    longest = 0.0
    chapters: list = []
    for segment in budget.segments:
        if used >= 3600.0:
            break
        chapters.append(segment.chapter)
        per = _mix_seconds(segment.mix) + OVERHEAD_SECONDS
        share = min(1.0, (3600.0 - used) / max(segment.seconds, 1.0))
        taken = max(0, int(segment.attempts * share))
        encounters += taken
        for name, weight in segment.mix.items():
            if weight <= 0:
                continue
            if _TIER_RANK.get(name, 0) > _TIER_RANK.get(hardest, 0):
                hardest = name
            longest = max(longest, encounter_seconds(name))
        used += segment.seconds * share
    boss_at = min((b.position for b in spec.bosses), default=99)
    first_boss_seconds = _seconds_to_position(budget, boss_at)
    reachable = [d for d in spec.dungeons
                 if _seconds_to_position(budget, spec.position_of(d.region)) < 3600.0]
    harshest_room = "GUIDED"
    for dungeon in reachable:
        plan = dungeonmod.DUNGEON_BY_ID.get(dungeon.id)
        floor = plan.floor if plan else "EASY"
        if _TIER_RANK.get(floor, 0) > _TIER_RANK.get(harshest_room, 0):
            harshest_room = floor

    ok = (_TIER_RANK.get(hardest, 9) <= _TIER_RANK[GENTLE_BAND["max_difficulty"]]
          and encounters >= GENTLE_BAND["min_encounters"]
          and longest <= GENTLE_BAND["max_single_seconds"]
          and first_boss_seconds >= GENTLE_BAND["no_boss_before_seconds"]
          and _TIER_RANK.get(harshest_room, 9)
          <= _TIER_RANK[GENTLE_BAND["max_dungeon_floor"]])
    return {
        "encounters": encounters,
        "chapters": chapters,
        "hardest_difficulty": hardest,
        "longest_encounter_seconds": round(longest, 1),
        "first_boss_seconds": round(first_boss_seconds, 1),
        "dungeons_reachable": len(reachable),
        "harshest_dungeon_floor": harshest_room,
        "minutes": round(min(used, 3600.0) / 60.0, 1),
        "gentle": ok,
    }


def _seconds_to_position(budget: Budget, position: int) -> float:
    """Estimated seconds before the player first stands at a chapter position."""
    if position <= 0:
        return 0.0
    total = 0.0
    for segment in budget.segments:
        if segment.position >= position:
            break
        total += segment.seconds
    return total


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------

def generate(seed=0) -> WorldSpec:
    """Build the whole world for one seed. Same seed, same world, every time."""
    seed = parse_seed(seed)
    order = chapter_order(seed)

    pick = _rng(seed, "character")
    primary = _pick_character(pick)
    under = _pick_character(pick, exclude=primary.id)
    mods = primary.mods.blend(under.mods, UNDERCURRENT_WEIGHT)

    regions = _region_specs(seed, order, mods)
    routes = _routes(seed, regions, mods)
    dungeon_specs = _dungeons(seed, order, mods)
    quest_specs = _quests(seed, order, mods)
    pet_specs = _pets(seed, regions)
    boss_specs = _bosses(seed, regions, order, mods)
    homes = _chapter_homes(seed, regions)
    spine = _spine(seed, order, homes)
    sightings = _sightings(seed, order, regions, spine, boss_specs, mods)
    budget = budget_for(order, homes, dungeon_specs, quest_specs, boss_specs)

    return WorldSpec(
        seed=seed, code=seed_text(seed), character=primary, undercurrent=under,
        mods=mods,
        character_name=f"{primary.name}, under {under.epithet}",
        blurb=primary.blurb, chapter_order=order, regions=regions, routes=routes,
        dungeons=dungeon_specs, quests=quest_specs, pets=pet_specs,
        bosses=boss_specs, spine=spine, sightings=sightings,
        first_mentor=_first_mentor(seed),
        index_home=spine[7].region, budget=budget)


def build_dungeon(spec: DungeonSpec):
    """Turn a DungeonSpec into a real `dungeons.Dungeon`.

    `dungeons.generate` takes an id and a seed and reads the archetype off the
    authored plan, so varying the floor-plan SHAPE means handing it a plan with a
    different archetype. That is `_generate_once`, which is module-private. It is
    used here behind a getattr guard, and the fallback — same dungeon, seeded
    layout, authored shape — is still a different building every seed, so nothing
    breaks if that helper ever moves.

    `plan.floors` is a promise, not a tendency: quests say "reach the fifth floor"
    and `dungeons.floors_for` is what they ask. A reshaped building that cannot
    keep the promise is therefore discarded and the authored shape used instead —
    the authored archetypes are the ones tuned to reach their own depth. Variety
    does not get to break a quest.
    """
    plan = dungeonmod.DUNGEON_BY_ID.get(spec.id)
    if plan is None:
        raise KeyError(f"no dungeon {spec.id!r}")
    once = getattr(dungeonmod, "_generate_once", None)
    authored = dungeonmod.generate(spec.id, seed=spec.layout_seed,
                                   size_bonus=spec.size_bonus)
    if once is None or spec.archetype == plan.archetype:
        return authored
    variant = replace(plan, archetype=spec.archetype)
    best = None
    for attempt in range(dungeonmod.FLOOR_ATTEMPTS):
        built = once(variant, spec.layout_seed, attempt, spec.size_bonus)
        if built.max_depth >= variant.floors:
            return built
        if best is None or built.max_depth > best.max_depth:
            best = built
    if best is not None and best.max_depth > authored.max_depth:
        return best                       # neither reached it; take the deeper
    return authored


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(spec: WorldSpec) -> list:
    """Every invariant this module claims, re-derived and checked.

    Deliberately independent of the code that built the spec: the generator uses
    Kahn's algorithm, and this walks the finished order asking whether each
    prerequisite already happened. Two implementations that agree is the same
    trick the corpus uses with its reference and canonical solutions, for the same
    reason.
    """
    problems: list = []

    # 1. The lesson set: chapters.
    order = list(spec.chapter_order)
    if sorted(order) != sorted(CHAPTER_IDS):
        problems.append(f"chapter set is wrong: {order}")
    if len(set(order)) != len(order):
        problems.append("a chapter appears twice")
    seen: set = set()
    for chapter_id in order:
        missing = sorted(CHAPTER_DEPS[chapter_id] - seen)
        if missing:
            problems.append(f"{chapter_id} placed before its prerequisites {missing}")
        seen.add(chapter_id)
    if order and order[-1] != FINAL_CHAPTER:
        problems.append(f"the finale is not last: {order[-1]}")

    # 2. The lesson set: skills. Every skill introduced, no skill introduced
    #    before something it stands on.
    position = {cid: i for i, cid in enumerate(order)}
    for skill in skillmod.SKILLS:
        owner = INTRODUCES.get(skill)
        if owner is None:
            problems.append(f"skill {skill} is never taught")
            continue
        if owner not in position:
            problems.append(f"skill {skill} belongs to absent chapter {owner}")
            continue
        for prereq in skillmod.PREREQUISITES.get(skill, ()):
            source = INTRODUCES.get(prereq)
            if source is None:
                problems.append(f"prerequisite {prereq} of {skill} is never taught")
            elif position[source] > position[owner]:
                problems.append(
                    f"{skill} (pos {position[owner]}) precedes its prerequisite "
                    f"{prereq} (pos {position[source]})")

    # 3. The main story.
    if len(spec.spine) != len(SPINE):
        problems.append(f"spine has {len(spec.spine)} beats, not {len(SPINE)}")
    last = -1
    for index, beat in enumerate(spec.spine):
        if beat.number != index + 1:
            problems.append(f"beat {beat.key} out of order")
        if beat.position <= last:
            problems.append(f"beat {beat.key} does not advance the position")
        last = beat.position
        if beat.region not in world.REGION_BY_ID:
            problems.append(f"beat {beat.key} fires in unknown region {beat.region}")
    if spec.spine and spec.spine[0].region != START_REGION:
        problems.append("beat I does not happen in the Margin")

    # 4. The world graph.
    region_ids = {r.id for r in spec.regions}
    if region_ids != set(world.REGION_BY_ID):
        problems.append("region set does not match world.REGIONS")
    adjacency: dict = {rid: set() for rid in region_ids}
    for route in spec.routes:
        if route.frm not in region_ids or route.to not in region_ids:
            problems.append(f"route {route.id} leaves the map")
            continue
        adjacency[route.frm].add(route.to)
        if route.two_way:
            adjacency[route.to].add(route.frm)
    stack, reached = [START_REGION], {START_REGION}
    while stack:
        current = stack.pop()
        for nxt in adjacency.get(current, ()):
            if nxt not in reached:
                reached.add(nxt)
                stack.append(nxt)
    if reached != region_ids:
        problems.append(f"unreachable regions: {sorted(region_ids - reached)}")
    by_id = spec.region_by_id
    # The load-bearing graph property: every region is reachable from the Margin
    # along OPEN roads without ever stepping backwards down the ladder. That is
    # what makes "no route delivers you past a prerequisite" a fact about the map
    # rather than a hope about the player.
    monotone: dict = {rid: set() for rid in region_ids}
    for route in spec.routes:
        if route.hidden or route.frm not in by_id or route.to not in by_id:
            continue
        low, high = route.frm, route.to
        if by_id[low].position > by_id[high].position:
            low, high = high, low
        if route.two_way or route.frm == low:
            monotone[low].add(high)
        if by_id[low].position == by_id[high].position and route.two_way:
            monotone[high].add(low)      # same rung: walking it either way is level
        if by_id[route.frm].position - by_id[route.to].position > MAX_OPEN_SPAN \
                or by_id[route.to].position - by_id[route.frm].position > MAX_OPEN_SPAN:
            problems.append(f"open route {route.id} skips "
                            f"more than {MAX_OPEN_SPAN} positions")
    stack, climbed = [START_REGION], {START_REGION}
    while stack:
        current = stack.pop()
        for nxt in monotone.get(current, ()):
            if nxt not in climbed:
                climbed.add(nxt)
                stack.append(nxt)
    if climbed != region_ids:
        problems.append("regions reachable only by walking backwards down the "
                        f"ladder: {sorted(region_ids - climbed)}")

    # 5. Biomes and palettes stay a bijection: two regions wearing the same
    #    palette is how a generated world starts looking generated.
    biomes = sorted(r.biome for r in spec.regions)
    palettes = sorted(r.palette for r in spec.regions)
    if biomes != sorted(r["biome"] for r in world.REGIONS):
        problems.append("the biome set is not a permutation of the authored one")
    # Not "all distinct": world.REGIONS spends `verdant` twice, so seventeen
    # regions share sixteen palettes and exactly one collision is authored.
    if palettes != sorted(r["palette"] for r in world.REGIONS):
        problems.append("the palette set is not a permutation of the authored one")
    for region_id, biome in PINNED_BIOMES.items():
        if by_id[region_id].biome != biome:
            problems.append(f"{region_id} lost its pinned biome")

    # 6. Dungeons: no chapter loses its building, no rule is rewritten.
    chapters_with_plans = {p.chapter for p in dungeonmod.DUNGEONS}
    covered = {d.chapter for d in spec.dungeons}
    if chapters_with_plans - covered:
        problems.append(f"chapters with no dungeon: "
                        f"{sorted(chapters_with_plans - covered)}")
    for dungeon in spec.dungeons:
        plan = dungeonmod.DUNGEON_BY_ID[dungeon.id]
        if dungeon.rule != plan.rule:
            problems.append(f"{dungeon.id} had its rule rewritten")
        if dungeon.archetype not in dungeonmod.ARCHETYPES:
            problems.append(f"{dungeon.id} has no such archetype")

    # 7. Quests: chains intact, lessons intact, nowhere empty.
    offered = {q.id for q in spec.quests}
    for quest in questmod.QUESTS:
        if _lesson_bearing(quest) and quest.id not in offered:
            problems.append(f"lesson-bearing quest {quest.id} was rolled away")
    per_region: dict = {}
    for quest in spec.quests:
        per_region[quest.region] = per_region.get(quest.region, 0) + 1
        if quest.giver not in questmod.NPCS:
            problems.append(f"quest {quest.id} has no such giver {quest.giver}")
    for region_id in region_ids:
        available = len(questmod.BY_REGION.get(region_id, ()))
        if available and per_region.get(region_id, 0) < min(2, available):
            problems.append(f"{region_id} has nothing to do")

    # 8. Pets: one per region, two of them early.
    homes = [p.region for p in spec.pets]
    if len(set(homes)) != len(homes):
        problems.append("two pets share a hiding place")
    if sum(1 for p in spec.pets if p.position <= 4) < 2:
        problems.append("no early companions")
    if len(spec.pets) != len(petmod.PET_IDS):
        problems.append("a pet was not placed")

    # 9. Bosses: phases survive, implementation is never optional.
    counts = {key: 0 for key in PHASE_KEYS}
    for boss in spec.bosses:
        if REQUIRED_PHASE not in boss.phases:
            problems.append(f"{boss.id} can be beaten without writing anything")
        if boss.phases and boss.phases[-1] == FIRST_PHASE and len(boss.phases) > 1:
            problems.append(f"{boss.id} asks for recognition last")
        for key in boss.phases:
            counts[key] += 1
        for affix in boss.affixes:
            if affix not in AFFIX_BY_ID:
                problems.append(f"{boss.id} has unknown affix {affix}")
    for key, count in counts.items():
        if count < MIN_PHASE_OCCURRENCES:
            problems.append(f"phase {key} appears only {count} times in the world")

    # 10. The Green Index: joke before reveal, reveal present.
    reveal = [s for s in spec.sightings if s.revealing]
    if len(reveal) != 1:
        problems.append("the Index reveal is missing or duplicated")
    elif not any(s.position < reveal[0].position for s in spec.sightings):
        problems.append("the Index is explained before it is ever seen")

    # 11. The ramp.
    gentle = first_hour(spec)
    if not gentle["gentle"]:
        problems.append(f"first hour is outside the gentle band: {gentle}")
    for chapter_id in spec.chapter_order[:GENTLE_PREFIX]:
        if chapter_id not in GENTLE_CHAPTERS:
            problems.append(f"{chapter_id} opens the run and is not gentle")

    return problems


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------

def _corpus_check() -> dict:
    """Cross-check the lesson set against the content that actually exists.

    Building the corpus costs a couple of seconds, which is why it is not done at
    import. It is worth doing here: "every skill is taught" is a claim about
    chapters, and this is the only place that asks whether there are problems
    behind the chapters to teach it with.
    """
    try:
        from .corpus import build_all
        problems = build_all()
    except Exception as exc:                # pragma: no cover - diagnostics only
        return {"available": False, "error": str(exc)}

    credited = {skillmod.PATTERN_TO_SKILL[p.pattern] for p in problems
                if p.pattern in skillmod.PATTERN_TO_SKILL}
    families = {p.spaced_repetition_family for p in problems}

    thin = []
    for chapter in curriculum.CHAPTERS:
        if chapter.graduate_clears >= 999:
            continue
        own = sum(1 for p in problems
                  if p.spaced_repetition_family in set(chapter.families))
        if own < chapter.graduate_clears:
            thin.append({"chapter": chapter.id, "problems": own,
                         "clears_required": chapter.graduate_clears})

    unknown_families = sorted({f for chapter in curriculum.CHAPTERS
                               for f in chapter.families if f not in families})
    return {
        "available": True,
        "problems": len(problems),
        "patterns": len({p.pattern for p in problems}),
        # Skills no problem credits directly. They are taught by chapters that
        # claim them (PYTHON through every drill in the village, GRAPH through
        # BFS and DFS, COMMUNICATION through explanation phases, SPEED through
        # the Coliseum clock) but nothing in the corpus names them, so the claim
        # "every skill is taught" rests on the chapter, not on a problem.
        "skills_no_problem_credits": sorted(set(skillmod.SKILLS) - credited),
        "chapters_short_of_content": thin,
        "chapter_families_absent_from_corpus": unknown_families,
        "ok": not thin,
    }


def self_check(count: int = 300, *, start: int = 0, corpus: bool = True) -> dict:
    """Generate `count` seeds and prove the contract over all of them.

    Real numbers, including the ones that are not flattering.
    """
    failures: list = []
    orders: set = set()
    characters: dict = {}
    biome_arrangements: set = set()
    route_counts: list = []
    dungeon_counts: list = []
    quest_counts: list = []
    town_counts: list = []
    sighting_counts: list = []
    first_mentors: dict = {}
    grad_hours: list = []
    full_hours: list = []
    exposure_hours: list = []
    first_hour_encounters: list = []
    first_hour_hardest: dict = {}
    skills_seen: set = set()
    chapters_seen: set = set()
    roundtrip_failures: list = []

    for offset in range(count):
        seed = (start + offset * 2654435761) & SEED_MASK
        if seed_text(parse_seed(seed_text(seed))) != seed_text(seed):
            roundtrip_failures.append(seed)
        spec = generate(seed)
        problems = validate(spec)
        if problems:
            failures.append({"seed": seed, "code": spec.code,
                             "problems": problems[:4]})
        orders.add(spec.chapter_order)
        characters[spec.character.id] = characters.get(spec.character.id, 0) + 1
        first_mentors[spec.first_mentor] = first_mentors.get(spec.first_mentor, 0) + 1
        biome_arrangements.add(tuple(sorted((r.id, r.biome) for r in spec.regions)))
        route_counts.append(len(spec.routes))
        dungeon_counts.append(len(spec.dungeons))
        quest_counts.append(len(spec.quests))
        town_counts.append(sum(1 for r in spec.regions if r.town_tier > 0))
        sighting_counts.append(len(spec.sightings))
        grad_hours.append(spec.budget.graduation_hours)
        full_hours.append(spec.budget.full_hours)
        exposure_hours.append(spec.budget.exposure_hours)
        gentle = first_hour(spec)
        first_hour_encounters.append(gentle["encounters"])
        first_hour_hardest[gentle["hardest_difficulty"]] = \
            first_hour_hardest.get(gentle["hardest_difficulty"], 0) + 1
        chapters_seen |= set(spec.chapter_order)
        skills_seen |= {s for cid in spec.chapter_order
                        for s in SKILLS_BY_CHAPTER.get(cid, ())}

    def band(values) -> dict:
        if not values:
            return {"min": 0, "median": 0, "max": 0, "mean": 0}
        ordered = sorted(values)
        mid = len(ordered) // 2
        median = (ordered[mid] if len(ordered) % 2
                  else (ordered[mid - 1] + ordered[mid]) / 2.0)
        return {"min": round(ordered[0], 2), "median": round(median, 2),
                "max": round(ordered[-1], 2),
                "mean": round(sum(ordered) / len(ordered), 2)}

    # Skills with no entry in the pattern vocabulary at all. Distinct from the
    # corpus report's `skills_no_problem_credits`, which is the stronger claim:
    # GREEDY has a pattern name and no problems behind it, and both facts are
    # worth printing rather than one of them being quietly dropped.
    mapped = set(skillmod.PATTERN_TO_SKILL.values())
    uncovered = sorted(s for s in skillmod.SKILLS if s not in mapped)

    # Building floor plans is the expensive part of this module, so the promise
    # that a reshaped dungeon still reaches its authored depth is proved on a
    # sample rather than on all 300 seeds. Shallow buildings are listed, not
    # counted, because a quest that cannot be finished is a name, not a number.
    shallow: list = []
    built_count = 0
    for offset in range(min(count, 12)):
        seed = (start + offset * 2654435761) & SEED_MASK
        for dungeon in generate(seed).dungeons:
            plan = dungeonmod.DUNGEON_BY_ID[dungeon.id]
            depth = build_dungeon(dungeon).max_depth
            built_count += 1
            if depth < plan.floors:
                shallow.append(f"{dungeon.id}@{seed_text(seed)}: "
                               f"{depth} of {plan.floors}")

    corpus_report = _corpus_check() if corpus else {"available": False,
                                                    "skipped": True}
    reference = generate(20260911)
    sample = {
        "code": reference.code,
        "slot_label": reference.slot_label,
        "chapter_order": list(reference.chapter_order),
        "first_mentor": reference.first_mentor,
        "index_home": reference.index_home,
        "verdict": reference.budget.verdict,
        "at_ten_hours": reference.budget.at_target,
    }

    return {
        "seeds": count,
        "failures": failures,
        "ok": (not failures and not roundtrip_failures and not shallow
               and corpus_report.get("ok", True)),
        "seed_roundtrip_failures": roundtrip_failures,

        "all_chapters_every_seed": sorted(chapters_seen) == sorted(CHAPTER_IDS),
        "all_skills_taught_every_seed": sorted(skills_seen) == sorted(skillmod.SKILLS),
        "skills": len(skillmod.SKILLS),
        "chapters": len(CHAPTER_IDS),
        "skills_with_no_pattern_name": uncovered,
        "corpus": corpus_report,
        "dungeons_built": built_count,
        "dungeons_shallower_than_promised": shallow,
        "chapter_dependency_edges": sum(len(v) for v in CHAPTER_DEPS.values()),

        "distinct_chapter_orders": len(orders),
        "distinct_biome_maps": len(biome_arrangements),
        "world_characters": characters,
        "first_mentors": first_mentors,

        "routes": band(route_counts),
        "dungeons": band(dungeon_counts),
        "quests": band(quest_counts),
        "towns": band(town_counts),
        "index_sightings": band(sighting_counts),

        "first_hour_encounters": band(first_hour_encounters),
        "first_hour_hardest_difficulty": first_hour_hardest,
        "first_hour_gentle_every_seed": all(
            "first hour" not in p for f in failures for p in f["problems"]),

        "exposure_hours": band(exposure_hours),
        "graduation_hours": band(grad_hours),
        "full_hours": band(full_hours),
        "target_hours": TARGET_HOURS,
        "timing_basis": "authored corpus target_seconds, scaled by "
                        f"{CLEARED_FRACTION_OF_TARGET} for a cleared attempt; "
                        "no telemetry exists yet. calibrate() replaces this.",
        "sample": sample,
    }


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def world_card(spec: WorldSpec) -> str:
    """The seed, printed. This is what a player would screenshot."""
    lines = [
        f"  {spec.slot_label}",
        f"  {spec.blurb}",
        "",
        f"  first mentor    {world.MENTORS[spec.first_mentor]['name']}",
        f"  towns           {sum(1 for r in spec.regions if r.town_tier > 0)}"
        f" of {len(spec.regions)}",
        f"  routes          {len(spec.routes)}"
        f" ({sum(1 for r in spec.routes if r.hidden)} unmapped)",
        f"  dungeons        {len(spec.dungeons)}",
        f"  quests offered  {len(spec.quests)}",
        f"  index seen      {len(spec.sightings)} times,"
        f" explained in {world.REGION_BY_ID[spec.index_home]['name']}",
        "",
        "  the road, and what happens on it",
    ]
    for beat in spec.spine:
        chapter = curriculum.CHAPTER_BY_ID[beat.chapter]
        region = world.REGION_BY_ID[beat.region]
        spec_region = spec.region_by_id[beat.region]
        numeral = chapter.title.split(".", 1)[0]
        lines.append(f"   {beat.number:>2}. {beat.title:<30} ch {numeral:<5}"
                     f"{region['name']} ({spec_region.biome})")
    budget = spec.budget
    lines += [
        "",
        f"  scheduled       {budget.encounters} required clears in "
        f"{budget.attempts} attempts, {budget.bosses} bosses in "
        f"{budget.boss_phases} phases,",
        f"                  {budget.dungeon_rooms} dungeon rooms, "
        f"{budget.quests} quests",
        f"  exposure floor  {budget.exposure_hours} h  (every lesson met once)",
        f"  all chapters    {budget.graduation_hours} h  (at the authored gates)",
        f"  everything      {budget.full_hours} h",
        f"  at {budget.target_hours:g} h        chapter "
        f"{budget.at_target['chapters_touched']} of {len(spec.chapter_order)},"
        f" {budget.at_target['clears']} of {budget.encounters} required clears",
        "",
        f"  {budget.verdict}",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    import json
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--check":
        count = int(argv[1]) if len(argv) > 1 else 300
        report = self_check(count)
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["ok"] else 1
    spec = generate(argv[0] if argv else 0)
    print(world_card(spec))
    return 0


if __name__ == "__main__":            # pragma: no cover - manual use
    raise SystemExit(main())
