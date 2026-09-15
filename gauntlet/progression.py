"""The open world: geography, gates, world events, levelling, and region state.

Until now the seventeen regions in `world.py` were a menu. They had an unlock
tree — `world.unlocked_regions` — but no *geography*: nothing said that the Marsh
lies downhill of the Caverns, or that the only honest way into the Wastes is the
long road under a fallen canopy. A menu cannot be explored. This module gives the
regions a map.

Four things live here, and they are all data first so the client can render them
as prose and progress bars rather than as invisible thresholds:

1. ROUTES. A directed graph over regions, each edge named, each edge carrying a
   NEED. Most needs are SOFT: the road is open, the things down it will simply
   hurt you. Walking into a region twenty levels above you is a design feature —
   the player asked for an open world, and an open world you are forbidden from
   entering is a corridor with extra steps. Hard walls exist only where the story
   demands one, and every hard wall is a shortcut or the Castle. No region is
   ever reachable *only* through a hard wall; `verify_no_orphans` proves it.

2. WORLD_EVENTS. Forty-two beats that fire when the player has earned them and
   then change the world: a road opens, a region transforms, a boss wakes up, the
   sky goes wrong. Triggers are evidence or exploration, never elapsed time.
   Fourteen of them are key drops and two of them are the Standing Portal.

2b. KEYS, ROADS AND THE PORTAL. Fourteen bosses, fourteen keys (world.KEYS),
   fourteen hard-walled roads that open when the matching boss dies, and one
   portal in Python Village that needs all fourteen. A key is DERIVED from
   `cleared_bosses`, so there is no second ledger to fall out of step. Every key
   road is a second way to somewhere already reachable, which is what makes it
   safe to make it hard: `verify_no_orphans` deletes every wall and the sixteen
   mortal regions are still one connected map, and `self_check` re-proves it
   from a keyless save standing in each of the seventeen regions in turn.

   THE PORTAL GATES THE STORY CLIMAX AND NEVER THE PRACTICAL. Timed Practical Mode is
   a measurement, reachable from the menu at any time with no keys, no roads and
   no bosses. `finalexam.sealed()` is the one capability check in this game;
   `portal_blocks()` is a question with a permanent answer, not a second one.

3. THE LEVEL CURVE, deepened. `world.level_for` grows 18% per level forever,
   which is fine to level 20 and absurd by level 40 (one level there costs
   76,310 XP — several hundred graded solves for one attribute point). Here the
   growth *decays* by half every fourteen levels, so the cost per level converges
   to about 4,250 XP and stops rising: level 40 costs 2,485, level 60 costs
   3,479, and no level anywhere ever costs more than 4,130. Plus a real
   grant every single level, and prestige recognition that is computed from
   graded evidence only, so it cannot be farmed by wandering around.

4. REGION STATE. Ruined, stirring, restored, transformed — derived from actual
   progress made in that region, so the world visibly answers the player.

Rules this module is bound by, same as the rest of the codebase: mastery and XP
move only on graded evidence; nothing here supplies an answer to a problem;
learning never dead-ends, which is what `things_to_do` exists to guarantee.

STATE KEYS. This module reads the engine's save dict and never writes to it
except through `advance()`. It reads, all optional and all forward-filled:
    state["player"]["level"|"xp"|"region"]   state["cleared_bosses"]
    state["inventory"] / state["equipped"]   state["secrets_found"]
    state["stats"]                           state["skills"]
    state["story"]["fired"]                  state["quests_completed"]
    state["pets"]                            state["dungeons_cleared"]
    state["world"]                           — this module's own sub-state
`pets` and `dungeons_cleared` are owned by other systems; we only ever read ids
out of them, so a save written before those systems existed still works.

THE KEYS ADD NOTHING TO THIS LIST. There is no `state["keys"]`, on purpose:
`world.keys_held(state["cleared_bosses"])` is the whole implementation, so every
save that has ever existed already holds exactly the keys its owner earned and
there is nothing to migrate, nothing to lose and no second ledger to disagree
with the kill list. The same is true of the Standing Portal, which is a function
of the same fact. `state["world"]["events_fired"]` gains sixteen ids as a
consequence of play, which `_merge` forward-fills like any other.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config, curriculum, items, world
from . import dungeons as dungeonmod
from . import pets as petmod
from . import skills as skillmod

# ---------------------------------------------------------------------------
# Needs — one declarative predicate type, shared by routes, events and advice
# ---------------------------------------------------------------------------
# A need is data rather than a lambda for the same reason story.Trigger is: the
# map screen renders it ("3/8 bosses"), and an unlock the player cannot see
# coming is an unlock that feels arbitrary when it lands.


@dataclass(frozen=True)
class Need:
    kind: str
    key: str = ""
    value: float = 0.0
    parts: tuple = ()


class Needs:
    """Constructors, namespaced so the content tables below read as prose."""

    @staticmethod
    def none() -> Need:
        return Need("none")

    @staticmethod
    def level(value: int) -> Need:
        return Need("level", value=value)

    @staticmethod
    def chapter(chapter_id: str) -> Need:
        return Need("chapter", chapter_id)

    @staticmethod
    def boss(boss_id: str) -> Need:
        return Need("boss", boss_id)

    @staticmethod
    def bosses(count: int) -> Need:
        return Need("bosses", value=count)

    @staticmethod
    def item(item_id: str) -> Need:
        return Need("item", item_id)

    @staticmethod
    def quest(quest_id: str) -> Need:
        return Need("quest", quest_id)

    @staticmethod
    def quests(count: int) -> Need:
        return Need("quests", value=count)

    @staticmethod
    def dungeon(dungeon_id: str) -> Need:
        return Need("dungeon", dungeon_id)

    @staticmethod
    def dungeons(count: int) -> Need:
        return Need("dungeons", value=count)

    @staticmethod
    def pet(pet_id: str) -> Need:
        return Need("pet", pet_id)

    @staticmethod
    def pets(count: int) -> Need:
        return Need("pets", value=count)

    @staticmethod
    def mastery(skill: str, value: float) -> Need:
        return Need("mastery", skill, value)

    @staticmethod
    def stage(skill: str, stage_name: str) -> Need:
        return Need("stage", skill, value=_stage_rank(stage_name))

    @staticmethod
    def unaided(skill: str, count: int) -> Need:
        return Need("unaided", skill, count)

    @staticmethod
    def secret(secret_id: str) -> Need:
        return Need("secret", secret_id)

    @staticmethod
    def stat(key: str, count: int) -> Need:
        return Need("stat", key, count)

    @staticmethod
    def region_at(region_id: str, state_name: str) -> Need:
        return Need("region_state", region_id, _state_rank(state_name))

    @staticmethod
    def restored(count: int) -> Need:
        return Need("restored", value=count)

    @staticmethod
    def event(event_id: str) -> Need:
        return Need("event", event_id)

    # -- keys. A key is proof you were somewhere and beat what lived there, so
    # -- it is DERIVED from cleared_bosses and never stored twice. See
    # -- world.KEYS for the fourteen and for what each one opens.

    @staticmethod
    def key(key_id: str) -> Need:
        return Need("key", key_id)

    @staticmethod
    def keys(count: int) -> Need:
        return Need("keys", value=count)

    @staticmethod
    def all_keys() -> Need:
        """Every key in the realm. The Standing Portal's need, and nothing
        else's — a gate this expensive may exist exactly once."""
        return Need("keys", value=len(world.KEYS))

    @staticmethod
    def discovered(route_id: str) -> Need:
        """Hidden until found. The only need exploration alone can satisfy."""
        return Need("discovery", route_id)

    @staticmethod
    def all_of(*parts: Need) -> Need:
        return Need("all", parts=tuple(parts))

    @staticmethod
    def any_of(*parts: Need) -> Need:
        return Need("any", parts=tuple(parts))


def _stage_rank(stage_name: str) -> int:
    try:
        return skillmod.STAGES.index(stage_name)
    except ValueError:
        return 0


REGION_STATES = ("ruined", "stirring", "restored", "transformed")


def _state_rank(state_name: str) -> int:
    try:
        return REGION_STATES.index(state_name)
    except ValueError:
        return 0


def _ratio(have: float, want: float) -> float:
    if want <= 0:
        return 1.0
    return max(0.0, min(1.0, have / want))


def need_status(need: Need, prog: dict) -> dict:
    """Evaluate one need against a snapshot. Returns met, a 0..1 ratio for the
    progress bar, and the label the map screen prints under the road sign."""
    kind = need.kind
    if kind == "none":
        return {"met": True, "ratio": 1.0, "label": "open"}

    if kind == "level":
        have = prog["level"]
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"level {int(have)}/{int(need.value)}"}

    if kind == "chapter":
        chapter = curriculum.CHAPTER_BY_ID.get(need.key)
        title = chapter.title if chapter else need.key
        met = need.key in prog["chapters_graduated"]
        return {"met": met, "ratio": 1.0 if met else prog["chapter_ratio"].get(need.key, 0.0),
                "label": f"graduate {title}"}

    if kind == "boss":
        boss = world.BOSS_BY_ID.get(need.key)
        name = boss["name"] if boss else need.key
        met = need.key in prog["cleared_bosses"]
        return {"met": met, "ratio": 1.0 if met else 0.0, "label": f"defeat {name}"}

    if kind == "bosses":
        have = len(prog["cleared_bosses"])
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"bosses {have}/{int(need.value)}"}

    if kind == "item":
        item = items.BY_ID.get(need.key)
        name = item.name if item else need.key
        met = need.key in prog["items"]
        return {"met": met, "ratio": 1.0 if met else 0.0, "label": f"carry {name}"}

    if kind == "quest":
        met = need.key in prog["quests"]
        return {"met": met, "ratio": 1.0 if met else 0.0,
                "label": f"finish {need.key.replace('_', ' ')}"}

    if kind == "quests":
        have = prog["quests_done"]
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"quests {have}/{int(need.value)}"}

    if kind == "dungeon":
        dungeon = DUNGEON_BY_ID.get(need.key)
        name = dungeon["name"] if dungeon else need.key
        met = need.key in prog["dungeons"]
        return {"met": met, "ratio": 1.0 if met else 0.0, "label": f"clear {name}"}

    if kind == "dungeons":
        have = len(prog["dungeons"])
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"dungeons {have}/{int(need.value)}"}

    if kind == "pet":
        pet = PET_BY_ID.get(need.key)
        name = pet["name"] if pet else need.key
        met = need.key in prog["pets"]
        return {"met": met, "ratio": 1.0 if met else 0.0, "label": f"travel with {name}"}

    if kind == "pets":
        have = len(prog["pets"])
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"companions found {have}/{int(need.value)}"}

    if kind == "mastery":
        have = prog["skills"].get(need.key, {}).get("mastery", 0.0)
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"{need.key} mastery {round(have)}/{int(need.value)}"}

    if kind == "stage":
        have = _stage_rank(prog["skills"].get(need.key, {}).get("stage", "UNKNOWN"))
        want = skillmod.STAGES[int(need.value)]
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"{need.key} at {want.lower()}"}

    if kind == "unaided":
        have = prog["skills"].get(need.key, {}).get("unaided_clears", 0)
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"{need.key} unaided {have}/{int(need.value)}"}

    if kind == "secret":
        met = need.key in prog["secrets"]
        return {"met": met, "ratio": 1.0 if met else 0.0, "label": "find what is hidden"}

    if kind == "stat":
        have = prog["stats"].get(need.key, 0)
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"{need.key.replace('_', ' ')} {have}/{int(need.value)}"}

    if kind == "region_state":
        region = world.REGION_BY_ID.get(need.key)
        name = region["name"] if region else need.key
        have = _state_rank(prog["region_states"].get(need.key, "ruined"))
        want = REGION_STATES[int(need.value)]
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"{name} {want}"}

    if kind == "restored":
        have = prog["restored_count"]
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"regions restored {have}/{int(need.value)}"}

    if kind == "event":
        met = need.key in prog["events_fired"]
        event = EVENT_BY_ID.get(need.key)
        return {"met": met, "ratio": 1.0 if met else 0.0,
                "label": event.title if event else need.key}

    if kind == "discovery":
        met = need.key in prog["discovered"]
        return {"met": met, "ratio": 1.0 if met else 0.0, "label": "undiscovered"}

    if kind == "key":
        key = world.KEY_BY_ID.get(need.key)
        name = key["name"] if key else need.key
        # Read straight off the bosses. There is no key ledger to fall out of
        # step with the kill list, because there is no key ledger.
        met = bool(key) and key["boss"] in prog["cleared_bosses"]
        boss = world.BOSS_BY_ID.get(key["boss"], {}) if key else {}
        return {"met": met, "ratio": 1.0 if met else 0.0,
                "label": f"carry {name}" if met
                         else f"take {name} from {boss.get('name', 'its holder')}"}

    if kind == "keys":
        have = len(world.keys_held(prog["cleared_bosses"]))
        return {"met": have >= need.value, "ratio": _ratio(have, need.value),
                "label": f"keys {have}/{int(need.value)}"}

    if kind == "all":
        parts = [need_status(p, prog) for p in need.parts]
        return {"met": all(p["met"] for p in parts),
                "ratio": min([p["ratio"] for p in parts] or [1.0]),
                "label": ", then ".join(p["label"] for p in parts)}

    if kind == "any":
        parts = [need_status(p, prog) for p in need.parts]
        return {"met": any(p["met"] for p in parts),
                "ratio": max([p["ratio"] for p in parts] or [1.0]),
                "label": " or ".join(p["label"] for p in parts)}

    # An unknown need is treated as met. A typo must never be able to lock a
    # player out of the world; it should merely fail to gate anything.
    return {"met": True, "ratio": 1.0, "label": "open"}


# ---------------------------------------------------------------------------
# Hidden companions and the dungeons under the map
# ---------------------------------------------------------------------------
# The pet SYSTEM — taming, hints on attack — is not ours, and neither is where
# each animal hides: `pets` owns that, because the deed that reveals one is
# evaluated there against graded evidence. All the world layer needs is a row
# per animal so the map can say "something is hiding in the Wastes", so this is
# a view rather than a second, quietly different, list of hiding places.

PETS = [
    {"id": pet.id, "name": f"{pet.name} the {pet.species}",
     "region": pet.discovery.region, "hint": pet.discovery.where}
    for pet in petmod.PETS
]

PET_BY_ID = {p["id"]: p for p in PETS}

# Dungeons are named sites *inside* regions: a vast network under the map. The
# dungeon system owns the places themselves — id, name, region, guaranteed depth,
# blurb — so this table holds only the world layer's half of the contract, which
# is what OPENS each one. Deriving the rest is the difference between one world
# and two worlds that disagree about where the Ninth Cart is.
#
# Every entry's need must be reachable from an empty save without entering the
# dungeon it gates; `verify_no_orphans` proves that rather than trusting it.

DUNGEON_NEEDS = {
    "halfwritten_barrow": Needs.none(),
    "hollow_of_keys": Needs.chapter("counting"),
    "anagram_deeps": Needs.quests(3),
    "sunken_index": Needs.level(10),
    "the_long_draw": Needs.boss("window_wraith"),
    "converging_span": Needs.chapter("scanning"),
    "ninth_cart": Needs.bosses(2),
    "turning_keep": Needs.boss("matrix_golem"),
    "inner_grove": Needs.chapter("recursion"),
    "split_canopy": Needs.chapter("recursion"),
    "lattice_of_ruin": Needs.bosses(5),
    "lit_tiles": Needs.mastery("DP", 45),
    "cracked_ward": Needs.stat("armor_repairs", 3),
    "doubling_stair": Needs.mastery("BIG_O", 40),
    "under_arena": Needs.bosses(6),
    "unlabelled_halls": Needs.event("ev_castle_unsealed"),
}

DUNGEONS = [
    {"id": plan.id, "name": plan.name, "region": plan.region,
     "floors": plan.floors, "blurb": plan.blurb,
     "need": DUNGEON_NEEDS.get(plan.id, Needs.none())}
    for plan in dungeonmod.DUNGEONS
]

DUNGEON_BY_ID = {d["id"]: d for d in DUNGEONS}
DUNGEONS_BY_REGION: dict = {}
for _d in DUNGEONS:
    DUNGEONS_BY_REGION.setdefault(_d["region"], []).append(_d)


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
# Danger is the recommended level for the content in a region. It is advisory,
# never a lock: walking into the Wastes at level nine is allowed, and the Wastes
# will make their own argument about whether it was wise.

REGION_DANGER = {
    "python_village": 1, "fields_of_syntax": 3, "debugging_dungeon": 5,
    "hashmap_highlands": 7, "stringwood_labyrinth": 9, "array_caverns": 11,
    "sliding_window_marsh": 14, "twin_pointer_pass": 15, "stack_queue_mines": 16,
    "matrix_citadel": 18, "recursive_forest": 20, "binary_tree_canopy": 22,
    "dp_ruins": 26, "graph_wastes": 24, "complexity_tower": 23,
    "coding_coliseum": 25, "null_kings_castle": 32,
}


@dataclass(frozen=True)
class Route:
    id: str
    name: str
    frm: str
    to: str
    kind: str                 # road, climb, tunnel, ferry, stair, drop, burrow
    need: Need
    prose: str                # what the road looks like
    wall: bool = False        # True: you cannot pass. False: you may, at your peril
    two_way: bool = True
    danger: int = 1


# The backbone is deliberately soft: every one of the sixteen mortal regions is
# reachable from every other at any point in the game, gated only by warnings.
# The shortcuts and the Castle approaches are the hard edges, and no region hangs
# off one of those alone — verify_no_orphans() is the proof.
ROUTES = [
    Route("rt_waking_road", "The Waking Road", "python_village", "fields_of_syntax",
          "road", Needs.none(),
          "Cart ruts leaving the village gate, worn back into use by one person "
          "walking them every day.", danger=3),
    Route("rt_armorers_stair", "The Armorer's Stair", "python_village",
          "debugging_dungeon", "stair", Needs.none(),
          "A spiral stair under the forge. The heat gets worse. So does the "
          "quality of the programs they keep down there.", danger=5),
    Route("rt_old_pilgrim_road", "The Old Pilgrim Road", "fields_of_syntax",
          "debugging_dungeon", "road", Needs.none(),
          "The long way round to the forge, through fields nobody weeds any more.",
          danger=5),
    Route("rt_keyward_climb", "The Keyward Climb", "fields_of_syntax",
          "hashmap_highlands", "climb", Needs.chapter("structures"),
          "Switchbacks up onto the plateau. Every step of it is easier if you "
          "already know which vault you are looking for.", danger=7),
    Route("rt_letterline", "The Letterline", "fields_of_syntax",
          "stringwood_labyrinth", "road", Needs.level(6),
          "A hedgerow of consonants that thickens into forest without ever "
          "announcing that it has.", danger=9),
    Route("rt_anagram_track", "The Anagram Track", "hashmap_highlands",
          "stringwood_labyrinth", "road", Needs.none(),
          "Three tracks leave the plateau. They are the same track, spelled "
          "differently, and they arrive at the same clearing.", danger=9),
    Route("rt_zeroth_descent", "The Zeroth Descent", "hashmap_highlands",
          "array_caverns", "tunnel", Needs.none(),
          "A staircase cut into the plateau's edge. The first step is numbered "
          "zero, and the argument about that is carved into the wall.", danger=11),
    Route("rt_reed_causeway", "The Reed Causeway", "array_caverns",
          "sliding_window_marsh", "road",
          Needs.any_of(Needs.chapter("scanning"), Needs.boss("hash_titan")),
          "Duckboards laid across the reeds. You can see the whole crossing from "
          "here, which is the point.", danger=14),
    Route("rt_frame_ferry", "The Frame Ferry", "hashmap_highlands",
          "sliding_window_marsh", "ferry",
          Needs.all_of(Needs.level(12), Needs.mastery("SLIDING_WINDOW", 25)),
          "A flat-bottomed boat inside a glowing frame. The frame widens to the "
          "right as you board and shrinks from the left when it must.", danger=14),
    Route("rt_converging_bridge", "The Converging Bridge", "array_caverns",
          "twin_pointer_pass", "road", Needs.none(),
          "Two lanterns are lit at either end of the bridge each evening. They "
          "meet in the middle and go out together.", danger=15),
    Route("rt_cart_tunnel", "The Cart Tunnel", "array_caverns", "stack_queue_mines",
          "tunnel", Needs.none(),
          "An ore line running out of the caverns. Mind the carts; they only "
          "come off the top of the pile.", danger=16),
    Route("rt_ruled_approach", "The Ruled Approach", "array_caverns",
          "matrix_citadel", "road", Needs.level(16),
          "A perfectly straight avenue of perfectly spaced stones, which is how "
          "you know something in the Citadel is still counting.", danger=18),
    Route("rt_high_ledge", "The High Ledge", "twin_pointer_pass", "matrix_citadel",
          "climb", Needs.level(18),
          "A ledge along the pass wall with the Citadel's rows visible below, "
          "rotating slowly, as if aligning for something.", danger=18),
    Route("rt_inward_trail", "The Inward Trail", "stringwood_labyrinth",
          "recursive_forest", "road", Needs.chapter("recursion"),
          "The trail enters a clearing containing a smaller copy of the trail. "
          "People who do not trust the smaller copy tend to turn back here.",
          danger=20),
    Route("rt_branch_ladder", "The Branch Ladder", "recursive_forest",
          "binary_tree_canopy", "climb", Needs.none(),
          "Rungs hammered into a trunk that forks left and right, twice per "
          "storey, and never forks back.", danger=22),
    Route("rt_memo_causeway", "The Memo Causeway", "recursive_forest", "dp_ruins",
          "road", Needs.chapter("optimisation"),
          "A raised road across the sinkholes. Every slab you have crossed once "
          "stays lit behind you and costs nothing to cross again.", danger=26),
    Route("rt_fallen_canopy", "The Fallen Canopy Road", "binary_tree_canopy",
          "graph_wastes", "road",
          Needs.any_of(Needs.level(20), Needs.dungeon("split_canopy")),
          "Where the canopy came down, the branches fused into a lattice. Every "
          "ruin out there touches several others.", danger=24),
    Route("rt_lattice_rail", "The Lattice Rail", "stack_queue_mines", "graph_wastes",
          "tunnel", Needs.chapter("traversal"),
          "An abandoned mine rail that forks, rejoins, and forks again. The "
          "surveyors gave up drawing it and started drawing the connections.",
          danger=24),
    Route("rt_tower_approach", "The Tower Approach", "hashmap_highlands",
          "complexity_tower", "road",
          Needs.any_of(Needs.level(14), Needs.mastery("BIG_O", 35)),
          "A causeway to the tower's base. The tower does not look tall from "
          "here. That is a property of the tower, not of your eyes.", danger=23),
    Route("rt_sand_road", "The Sand Road", "sliding_window_marsh", "coding_coliseum",
          "road", Needs.level(18),
          "Marsh gives way to packed sand, and then to a floor that has been "
          "swept flat by people who did not want any excuses left on it.",
          danger=25),
    Route("rt_challengers_gate", "The Challengers' Gate", "twin_pointer_pass",
          "coding_coliseum", "road", Needs.bosses(3),
          "The gate the pass empties into. The Chronomancer's people count your "
          "kills at the door, politely, and out loud.", danger=25),
    Route("rt_wasted_ledger", "The Wasted Ledger", "graph_wastes", "dp_ruins",
          "road", Needs.bosses(5),
          "A ruined road between two ruins. Somebody has been relighting the "
          "tiles ahead of you, one per day, for years.", danger=26),

    # --- shortcuts. Every one of these is a second way to somewhere you can
    # --- already get to, which is what makes it safe to gate them hard.
    Route("rt_scribes_shortcut", "The Scribe's Shortcut", "python_village",
          "stringwood_labyrinth", "road", Needs.discovered("rt_scribes_shortcut"),
          "A gap in the village's back hedge that is not on any map, because the "
          "Scribe drew the maps and did not want the company.", wall=True, danger=9),
    Route("rt_drowned_root", "The Drowned Root", "sliding_window_marsh",
          "recursive_forest", "tunnel", Needs.discovered("rt_drowned_root"),
          "A hollow root running under the marsh into the forest. Inside it is "
          "another root, and inside that one, another.", wall=True, danger=20),
    Route("rt_cracked_seam", "The Cracked Seam", "debugging_dungeon",
          "stack_queue_mines", "tunnel", Needs.item("architects_seal"),
          "A fault the forge cells back onto. The seal the Architect left opens "
          "it; nothing else has, and people have tried with hammers.",
          wall=True, danger=16),
    Route("rt_rotating_stair", "The Rotating Stair", "matrix_citadel",
          "complexity_tower", "stair", Needs.boss("matrix_golem"),
          "The Citadel's north stair lines up with the tower's third floor once "
          "the floor plan stops turning. The Golem was the thing turning it.",
          wall=True, danger=23),
    Route("rt_ledger_bridge", "The Ledger Bridge", "dp_ruins", "complexity_tower",
          "road", Needs.quest("ruins_ledger_balanced"),
          "A span of ledger stones between the Ruins and the tower. The Oracle "
          "had it built to carry one argument back and forth.", wall=True, danger=26),
    Route("rt_python_burrow", "The Old Python's Burrow", "python_village",
          "array_caverns", "burrow", Needs.pet("python"),
          "A burrow under the village that comes out level with the numbered "
          "alcoves. Only one thing has ever fitted through it comfortably.",
          wall=True, danger=11),
    Route("rt_jaguars_line", "The Jaguar's Line", "stringwood_labyrinth",
          "twin_pointer_pass", "climb", Needs.pet("jaguar"),
          "A run along the ridge that only makes sense at a jaguar's pace. Going "
          "up this way is not on offer.", wall=True, two_way=False, danger=15),
    Route("rt_llama_track", "The Llama Track", "twin_pointer_pass",
          "sliding_window_marsh", "road", Needs.pet("llama"),
          "A stock route down off the pass, walked flat by something that knows "
          "exactly how far apart its feet should be.", wall=True, danger=14),
    Route("rt_penguin_shelf", "The Penguin Shelf", "sliding_window_marsh",
          "stack_queue_mines", "tunnel", Needs.pet("penguin"),
          "An ice shelf over the flooded workings. It holds. It holds in the "
          "order things were put on it, which is a different guarantee.",
          wall=True, danger=16),
    Route("rt_raptor_run", "The Raptor Run", "graph_wastes", "coding_coliseum",
          "road", Needs.pet("velociraptor"),
          "A straight line through the Wastes that ignores every road. Something "
          "fast worked out the shortest path a long time ago.", wall=True, danger=25),
    Route("rt_oracles_line", "The Oracle's Line", "complexity_tower",
          "python_village", "drop", Needs.dungeon("doubling_stair"),
          "A single cable from the tower's summit to the village bell. The "
          "Oracle calls it amortised. The ride down takes eleven seconds.",
          wall=True, two_way=False, danger=1),

    # --- the key roads. Fourteen bosses, fourteen keys, fourteen roads that
    # --- were always drawn and never open. Each one is HARD (wall=True) and
    # --- each one is a SECOND way to somewhere the player can already walk to,
    # --- which is the whole reason it is safe to make it hard: delete every
    # --- wall in this list and the sixteen mortal regions are still one
    # --- connected map. verify_no_orphans() proves that rather than promising
    # --- it, and self_check proves it again from a thousand random saves.
    #
    # --- Read the destinations top to bottom and the shape is deliberate: the
    # --- early keys widen the map sideways, and the late ones — the Leaf, the
    # --- Ring, the Undo, the Written Tree — all come home. By the time you are
    # --- holding thirteen of these, every road you opened last leads back to
    # --- the village, which is where the fourteenth one is standing.
    Route("rt_indexed_road", "The Indexed Road", "hashmap_highlands", "dp_ruins",
          "road", Needs.key("key_one_rune"),
          "The Titan's key fits a lock at the plateau's south edge that nobody "
          "had a name for. Behind it, one road, straight to the Ruins, with no "
          "searching at either end.", wall=True, danger=26),
    Route("rt_sorted_run", "The Sorted Run", "array_caverns",
          "stringwood_labyrinth", "road", Needs.key("key_skipped_head"),
          "The Hydra was lying across the run in nine places at once. Sorted, "
          "it is one road. It was always one road.", wall=True, danger=11),
    Route("rt_single_pass", "The Single-Pass Road", "sliding_window_marsh",
          "complexity_tower", "road", Needs.key("key_unbroken_frame"),
          "Marsh to tower without doubling back once. The Oracle has been "
          "asking for a road like this for a decade and refusing to explain "
          "why the old one offended her.", wall=True, danger=23),
    Route("rt_both_ends", "Both Ends Road", "twin_pointer_pass", "graph_wastes",
          "road", Needs.key("key_shorter_wall"),
          "Two parties set out from opposite ends of this road in the year of "
          "the Shattering. The Behemoth was standing where they would have "
          "met. It is not standing there now.", wall=True, danger=24),
    Route("rt_turned_hall", "The Turned Hall", "matrix_citadel",
          "stack_queue_mines", "tunnel", Needs.key("key_quarter_turn"),
          "A hall in the Citadel's west wing, turned a quarter turn in place, "
          "which puts its far door level with the top of the ore line. Nothing "
          "was allocated to hold it while it turned.", wall=True, danger=18),
    Route("rt_in_order_walk", "The In-Order Walk", "binary_tree_canopy",
          "dp_ruins", "drop", Needs.key("key_bounded_branch"),
          "Left, then the branch itself, then right, all the way down, and the "
          "order you come out in is the order the Ruins are numbered in. The "
          "Dragon was the reason nobody had ever finished the walk.",
          wall=True, danger=26),
    Route("rt_root_to_leaf", "The Root-to-Leaf Road", "binary_tree_canopy",
          "python_village", "road", Needs.key("key_counted_leaf"),
          "One path from the highest leaf to the root, and the root of this "
          "country is a village square with a bell in it. The Ent had been "
          "standing on the last stretch, insisting it was a leaf.",
          wall=True, danger=22),
    Route("rt_shortest_hop", "The Shortest Hop", "graph_wastes", "python_village",
          "road", Needs.key("key_ring_of_light"),
          "The Cartographer sets the Ring down in the Wastes and the light goes "
          "out in rings until one of them touches the village bell. Four hops. "
          "It was four hops the entire time.", wall=True, danger=24),
    Route("rt_discard_line", "The Discard Line", "sliding_window_marsh",
          "graph_wastes", "road", Needs.key("key_discarded_maximum"),
          "A causeway of everything the marsh threw away, laid end to end and "
          "walkable. What it threw away could never have won. What it kept is "
          "still in front.", wall=True, danger=24),
    Route("rt_undo_stair", "The Undo Stair", "matrix_citadel", "python_village",
          "stair", Needs.key("key_other_undo"),
          "Every change made to this realm, walked backwards, one step per "
          "change, ending in the square. The Automaton had the stair and no "
          "intention of implementing it.", wall=True, danger=18),
    Route("rt_amortised_run", "The Amortised Run", "complexity_tower",
          "coding_coliseum", "drop", Needs.key("key_amortised_step"),
          "One expensive step off the summit and then a long cheap glide onto "
          "the sand. Averaged over the whole descent it is the cheapest road in "
          "the realm, which the Wyrm found personally insulting.",
          wall=True, danger=25),
    Route("rt_written_down", "The Road Written Down", "recursive_forest",
          "python_village", "road", Needs.key("key_written_tree"),
          "The forest, serialised: one line of road that can be read back into "
          "the whole wood exactly, and read forward into the village gate. The "
          "Lich wrote it. The Lich could never read it back.",
          wall=True, danger=20),
    Route("rt_reproduction_road", "The Reproduction Road", "debugging_dungeon",
          "coding_coliseum", "road", Needs.key("key_reproduced_fault"),
          "The Armorer walks cracked plate down this road to the Coliseum, "
          "where a fault can be made to happen again on demand, to the second. "
          "You cannot fix what you cannot reproduce.", wall=True, danger=25),
    # The fourteenth. It runs the OTHER way down the road you always had out of
    # the castle, and it exists so that having beaten the Examiner you may
    # walk back into the exam hall from your own village whenever you like.
    # It is a convenience, not a permission: the practical needs no key and no
    # road, and `world.portal_gates("practical")` is False forever.
    Route("rt_road_back_in", "The Road Back In", "python_village",
          "null_kings_castle", "road", Needs.key("key_unlabelled"),
          "The Long Walk Back, walked the other way. Nothing on the signposts "
          "and nothing at the gate. You know where it goes because you have "
          "been, which was always the qualification.",
          wall=True, two_way=False, danger=32),

    # --- the Castle. The one hard wall the story insists on: it is the exam
    # --- hall, and walking in early would not be freedom, it would be a lie
    # --- about readiness. It is also never the only way to anywhere.
    Route("rt_nameless_causeway", "The Nameless Causeway", "graph_wastes",
          "null_kings_castle", "road", Needs.event("ev_castle_unsealed"),
          "A causeway out of the Wastes with no signs on it. There were signs. "
          "Somebody took the words off them.", wall=True, danger=32),
    Route("rt_lit_tiles_road", "The Road of Lit Tiles", "dp_ruins",
          "null_kings_castle", "road", Needs.event("ev_castle_unsealed"),
          "Every tile from the Ruins to the gate is already lit. Somebody solved "
          "this walk before you and left the light on.", wall=True, danger=32),
    Route("rt_overlook_drop", "The Overlook Drop", "complexity_tower",
          "null_kings_castle", "drop", Needs.event("ev_castle_unsealed"),
          "From the tower's top floor the castle is below you. It is the only "
          "place in the realm from which that is true.",
          wall=True, two_way=False, danger=32),
    Route("rt_victors_gate", "The Victor's Gate", "coding_coliseum",
          "null_kings_castle", "road", Needs.event("ev_castle_unsealed"),
          "The gate the Coliseum's winners leave by. It has been shut so long "
          "the sand has drifted a foot up the base of it.", wall=True, danger=32),
    Route("rt_long_fall", "The Long Walk Back", "null_kings_castle",
          "python_village", "road", Needs.none(),
          "You can always leave. That is the difference between an examination "
          "and a cell.", two_way=False, danger=1),
]

ROUTE_BY_ID = {r.id: r for r in ROUTES}

HIDDEN_ROUTES = [r for r in ROUTES if r.need.kind == "discovery"]

# Adjacency, as directed edges. A two-way route contributes both.
_EDGES: dict = {r["id"]: [] for r in world.REGIONS}
for _r in ROUTES:
    _EDGES.setdefault(_r.frm, []).append((_r.to, _r))
    if _r.two_way:
        _EDGES.setdefault(_r.to, []).append((_r.frm, _r))


def routes_from(region_id: str) -> list:
    """Every route leaving a region, in the direction the player would take it."""
    return [route for _, route in _EDGES.get(region_id, [])]


def route_other_end(route: Route, region_id: str) -> str:
    return route.to if route.frm == region_id else route.frm


# ---------------------------------------------------------------------------
# World events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Change:
    kind: str        # route_open, region_state, npc, dungeon, boss_awakens,
                     # sky, fast_travel, music, shop
    target: str
    detail: str = ""


@dataclass(frozen=True)
class WorldEvent:
    id: str
    title: str
    need: Need
    changes: tuple
    prose: str
    herald: str           # one line, for the banner across the top of the map
    region: str = ""      # where it visibly happens, if anywhere


WORLD_EVENTS = (
    WorldEvent(
        id="ev_village_wakes", title="The Village Remembers Its Name",
        need=Needs.mastery("PYTHON", 18),
        changes=(Change("region_state", "python_village", "stirring"),
                 Change("npc", "cartographers_apprentice",
                        "She sets up a table in the square and starts drawing."),
                 Change("music", "town", "the bell is rung on the hour again")),
        prose="Somebody has swept the square. There is a table in it now, and on "
              "the table a half-drawn map with your road on it — the only road "
              "anyone has walked in years. BYTE says nothing about this, which "
              "from BYTE is approval.",
        herald="Python Village is stirring.", region="python_village"),
    WorldEvent(
        id="ev_weeds_part", title="The Weeds Part",
        need=Needs.all_of(Needs.level(4), Needs.chapter("fluency")),
        changes=(Change("dungeon", "halfwritten_barrow", "the irrigation tunnels drain"),
                 Change("region_state", "fields_of_syntax", "stirring")),
        prose="The malformed statements in the east field have stopped growing "
              "back. Under where they were is a hatch, and under the hatch is "
              "the irrigation system somebody built before the Shattering and "
              "nobody has read since.",
        herald="The Half-Written Barrow is open.", region="fields_of_syntax"),
    WorldEvent(
        id="ev_keyward_opens", title="The Keyward Climb",
        need=Needs.chapter("structures"),
        changes=(Change("route_open", "rt_keyward_climb", ""),
                 Change("npc", "the_archivist", "waiting at the top, of course")),
        prose="The switchbacks up to the plateau are walkable. They always were. "
              "What changed is that you now know which vault you are climbing to, "
              "which turns out to be the difference between a climb and a wander.",
        herald="The road to Hashmap Highlands is yours.", region="hashmap_highlands"),
    WorldEvent(
        id="ev_titan_stirs", title="The Titan Stops Waiting",
        need=Needs.all_of(Needs.quests(3), Needs.mastery("HASH_MAP", 30)),
        changes=(Change("boss_awakens", "hash_titan", ""),
                 Change("sky", "amber", "the plateau light goes hard and yellow")),
        prose="The Hash Titan has spent an age offering to compare every scroll "
              "against every other, and an age is a long time to be ignored. It "
              "is standing up. The light on the plateau has gone the colour of "
              "old brass.",
        herald="The Hash Titan is awake.", region="hashmap_highlands"),
    WorldEvent(
        id="ev_marsh_drains", title="The Marsh Lowers",
        need=Needs.boss("hash_titan"),
        changes=(Change("route_open", "rt_reed_causeway", ""),
                 Change("region_state", "sliding_window_marsh", "stirring")),
        prose="Whatever the Titan was holding, it let go of when it fell. The "
              "marsh drops a foot overnight and a causeway surfaces across it, "
              "duckboards still sound, laid by people who intended to come back.",
        herald="A causeway has surfaced in the Marsh.",
        region="sliding_window_marsh"),
    WorldEvent(
        id="ev_mines_reopen", title="The Cart Line Runs Again",
        need=Needs.bosses(2),
        changes=(Change("dungeon", "ninth_cart", ""),
                 Change("npc", "shift_foreman", "gathering a crew, apparently")),
        prose="Two of the realm's monsters are dead and the mines have decided "
              "that is enough reason to reopen. The top shaft unloads from the "
              "top. The bottom shaft takes the oldest cart first. Both of them "
              "go all the way down.",
        herald="The Ninth Cart is running.", region="stack_queue_mines"),
    WorldEvent(
        id="ev_forge_relights", title="The Forge Relights",
        need=Needs.stat("armor_repairs", 6),
        changes=(Change("dungeon", "cracked_ward", ""),
                 Change("region_state", "debugging_dungeon", "stirring"),
                 Change("shop", "armorer_upgrades", "the Armorer will take work now")),
        prose="Six plates repaired by someone who read the crack before striking "
              "it. The Armorer opens the cells behind the forge, where the "
              "programs that could not be read are kept, and does not explain "
              "why she thinks you can read them.",
        herald="The Cracked Ward is unsealed.", region="debugging_dungeon"),
    WorldEvent(
        id="ev_frame_ferry", title="The Ferry Runs",
        need=Needs.all_of(Needs.level(12), Needs.mastery("SLIDING_WINDOW", 25)),
        changes=(Change("route_open", "rt_frame_ferry", ""),
                 Change("npc", "the_window_mage", "poling the boat himself")),
        prose="The Window Mage has got the ferry working. It is a flat boat "
              "inside a frame of light: the frame widens to the right as you "
              "board and shrinks from the left when the load gets illegal. He "
              "insists this is not a metaphor.",
        herald="The Frame Ferry is running.", region="sliding_window_marsh"),
    WorldEvent(
        id="ev_forest_turns_inward", title="The Forest Turns Inward",
        need=Needs.chapter("recursion"),
        changes=(Change("route_open", "rt_inward_trail", ""),
                 Change("region_state", "recursive_forest", "stirring"),
                 Change("sky", "dusk", "permanent late afternoon under the canopy")),
        prose="The Inward Trail has stopped being a rumour. It enters a clearing "
              "that contains a smaller copy of itself, and the copy contains "
              "another, and somewhere at the bottom of that is a base case and a "
              "very old druid who has been waiting for someone who trusts it.",
        herald="The Inward Trail is open.", region="recursive_forest"),
    WorldEvent(
        id="ev_canopy_lights", title="The Canopy Lights",
        need=Needs.dungeon("split_canopy"),
        changes=(Change("region_state", "binary_tree_canopy", "restored"),
                 Change("route_open", "rt_fallen_canopy", ""),
                 Change("sky", "verdant", "light comes through the leaves again")),
        prose="You carried something back up out of the hollows, which nobody had "
              "managed before. The canopy responds by lighting: every branch, "
              "left and right, all the way out to where it fell.",
        herald="The Canopy is lit.", region="binary_tree_canopy"),
    WorldEvent(
        id="ev_wastes_wake", title="Something Moves in the Wastes",
        need=Needs.bosses(5),
        changes=(Change("boss_awakens", "graph_necromancer", ""),
                 Change("dungeon", "lattice_of_ruin", ""),
                 Change("sky", "ash", "the ash stops falling and hangs there")),
        prose="Five of the realm's powers are dead and the Wastes have noticed. "
              "The ash stops falling. It simply hangs, holding its shape, in a "
              "lattice, and every ruin out there is suddenly connected to "
              "several others by a line of grey light.",
        herald="The Wastes have woken.", region="graph_wastes"),
    WorldEvent(
        id="ev_tower_first_floor", title="The Tower Admits You",
        need=Needs.mastery("BIG_O", 35),
        changes=(Change("dungeon", "doubling_stair", ""),
                 Change("route_open", "rt_tower_approach", ""),
                 Change("npc", "the_oracle", "on the stair, counting")),
        prose="The Oracle opens the tower door the moment you can say what a "
              "nested loop costs without stopping to think. Each floor holds "
              "twice the enemies of the floor below. She mentions this the way "
              "you would mention weather.",
        herald="The Doubling Stair is open.", region="complexity_tower"),
    WorldEvent(
        id="ev_ruins_relight", title="The Ruins Relight",
        need=Needs.mastery("DP", 40),
        changes=(Change("dungeon", "lit_tiles", ""),
                 Change("region_state", "dp_ruins", "stirring"),
                 Change("sky", "gold", "the ruins glow from underneath")),
        prose="Every tile you have already solved is lit, and stays lit, and "
              "costs nothing to cross again. From the ridge the Ruins now look "
              "like a city that has had its lights on the whole time and was "
              "waiting for somebody to stop paying twice.",
        herald="The Ruins are lit.", region="dp_ruins"),
    WorldEvent(
        id="ev_coliseum_opens", title="The Coliseum Opens Its Gate",
        need=Needs.all_of(Needs.level(18), Needs.bosses(3)),
        changes=(Change("route_open", "rt_sand_road", ""),
                 Change("route_open", "rt_challengers_gate", ""),
                 Change("npc", "the_chronomancer", "already holding the clock")),
        prose="The Chronomancer's people count your kills at the door, politely, "
              "out loud, and then open it. Sand floor. A clock. No hints, no "
              "labels, and nobody in the stands who cares how you feel about "
              "that.",
        herald="The Coliseum is open.", region="coding_coliseum"),
    WorldEvent(
        id="ev_pet_python", title="The Old Python",
        need=Needs.pet("python"),
        changes=(Change("route_open", "rt_python_burrow", ""),
                 Change("npc", "the_old_python", "it lives in the square now")),
        prose="The village was named for something, and the something was bricked "
              "up under the founders' cellar and is not remotely dead. It follows "
              "you out. Nobody in the village is surprised, which raises its own "
              "questions.",
        herald="The Old Python travels with you.", region="python_village"),
    WorldEvent(
        id="ev_pet_jaguar", title="The Stringwood Jaguar",
        need=Needs.pet("jaguar"),
        changes=(Change("route_open", "rt_jaguars_line", ""),
                 Change("region_state", "stringwood_labyrinth", "stirring")),
        prose="It has been rearranging the letters on the trail behind you for a "
              "week to see whether you would notice they still spelled the same "
              "word. You noticed. It walks beside you now, at the front, which "
              "it clearly considers beside.",
        herald="The Jaguar runs with you.", region="stringwood_labyrinth"),
    WorldEvent(
        id="ev_pet_llama", title="The Pass Llama",
        need=Needs.pet("llama"),
        changes=(Change("route_open", "rt_llama_track", ""),
                 Change("npc", "the_ranger", "openly delighted, for the Ranger")),
        prose="It started at the far end of the bridge at the same moment you "
              "started at yours, kept your exact pace, and met you in the middle. "
              "The Ranger says this is the only correct way to cross a bridge and "
              "refuses to elaborate.",
        herald="The Llama walks with you.", region="twin_pointer_pass"),
    WorldEvent(
        id="ev_pet_penguin", title="The Marsh Penguin",
        need=Needs.pet("penguin"),
        changes=(Change("route_open", "rt_penguin_shelf", ""),
                 Change("region_state", "sliding_window_marsh", "restored"),
                 Change("sky", "pale", "the marsh freezes over, cleanly")),
        prose="One patch of the marsh never thawed, and now you know what was "
              "keeping it that way. The ice spreads out from where it was "
              "standing and holds — in the order things were put on it, which is "
              "a different guarantee from holding.",
        herald="The Marsh has frozen over.", region="sliding_window_marsh"),
    WorldEvent(
        id="ev_pet_raptor", title="The Wastes Raptor",
        need=Needs.pet("velociraptor"),
        changes=(Change("route_open", "rt_raptor_run", ""),
                 Change("boss_awakens", "graph_necromancer", "it takes this personally")),
        prose="Three sets of tracks converged on the ruin and one set left. You "
              "followed the set that left, which is the first sensible thing "
              "anyone has done in the Wastes for a decade. It worked out the "
              "shortest path across this country long before the Cartographer "
              "did, and it is not impressed by roads.",
        herald="The Raptor hunts alongside you.", region="graph_wastes"),
    WorldEvent(
        id="ev_menagerie", title="The Whole Menagerie",
        need=Needs.pets(5),
        changes=(Change("npc", "the_menagerie", "they will not all fit indoors"),
                 Change("region_state", "python_village", "restored"),
                 Change("fast_travel", "village_hub", "they know every road now")),
        prose="Five things that were hiding in this realm are not hiding any "
              "more, and all five of them sleep in the village square. Between "
              "them they know every road on the map, including the ones the "
              "Cartographer left off it on purpose.",
        herald="All five companions found.", region="python_village"),
    WorldEvent(
        id="ev_rival_returns", title="The Rival Comes Back",
        need=Needs.all_of(Needs.quests(8), Needs.level(16)),
        changes=(Change("npc", "the_rival", "waiting on the road, not in a town"),
                 Change("sky", "storm", "weather moves in behind them")),
        prose="They are sitting on the milestone at the crossroads with their "
              "boots crossed, and they have been there long enough to have "
              "worked out which road you would take. They do not say well done. "
              "They say: you are slower than this by about a minute, and I can "
              "prove it.",
        herald="Your rival is waiting at the crossroads."),
    WorldEvent(
        id="ev_night_comes", title="The Null Spreads",
        need=Needs.all_of(Needs.level(24), Needs.bosses(6)),
        changes=(Change("sky", "void", "the colour goes out of the horizon"),
                 Change("region_state", "graph_wastes", "stirring"),
                 Change("npc", "the_interviewer", "seen at a distance, waiting")),
        prose="The horizon has stopped having a colour. Not dark — absent, the "
              "way a variable is absent. Every mentor in the realm notices on "
              "the same afternoon and every one of them says a version of: it "
              "knows your name now, and it is going to ask you to say it.",
        herald="The Null is spreading."),
    # -- the fourteen keys. One event per key, firing in the payload of the
    # -- submission that killed the boss, because a drop the player has to go
    # -- and look at a menu to discover is not a drop. Each one announces
    # -- exactly the road its key opens, and `self_check` refuses to let an
    # -- event announce a road that is not open at the moment it fires.
    WorldEvent(
        id="ev_key_one_rune", title="The One-Rune Key",
        need=Needs.key("key_one_rune"),
        changes=(Change("route_open", "rt_indexed_road", ""),
                 Change("npc", "vela_the_tollkeeper",
                        "she wants to see it, and she wants to see it twice")),
        prose="The Titan had been holding it the entire fight, which is why it "
              "never struck you. There is a lock at the plateau's south edge "
              "that nobody has had a name for in a generation, and this is its "
              "name. Behind the lock is a road to the Ruins with no searching "
              "at either end of it.",
        herald="The Indexed Road is open.", region="hashmap_highlands"),
    WorldEvent(
        id="ev_key_skipped_head", title="The Skipped Head",
        need=Needs.key("key_skipped_head"),
        changes=(Change("route_open", "rt_sorted_run", ""),),
        prose="Eight heads grew back. The ninth did not, because you walked "
              "past the duplicate instead of fighting it, and a head that was "
              "never fought has nothing to grow back from. The run out of the "
              "caverns to the Stringwood is one road once it is sorted.",
        herald="The Sorted Run is open.", region="array_caverns"),
    WorldEvent(
        id="ev_key_unbroken_frame", title="The Unbroken Frame",
        need=Needs.key("key_unbroken_frame"),
        changes=(Change("route_open", "rt_single_pass", ""),
                 Change("sky", "clearing", "the marsh light stops flickering")),
        prose="It starved. What is left of it is a frame of cold light with no "
              "seam anywhere in it, and laid flat across the reeds it makes a "
              "road to the tower that never doubles back. The Oracle has been "
              "asking for this road for ten years without once explaining what "
              "was wrong with the old one.",
        herald="The Single-Pass Road is open.", region="sliding_window_marsh"),
    WorldEvent(
        id="ev_key_shorter_wall", title="The Shorter Wall",
        need=Needs.key("key_shorter_wall"),
        changes=(Change("route_open", "rt_both_ends", ""),
                 Change("npc", "the_ranger", "walking it from the far end")),
        prose="Two bits, one filed down, and the Behemoth is no longer standing "
              "in the middle of the road where the two parties from either end "
              "would have met. The Ranger sets off from the Wastes side at the "
              "same moment you set off from the pass. You meet in the middle. "
              "He says that is the only correct way to open a road.",
        herald="Both Ends Road is open.", region="twin_pointer_pass"),
    WorldEvent(
        id="ev_key_quarter_turn", title="The Quarter Turn",
        need=Needs.key("key_quarter_turn"),
        changes=(Change("route_open", "rt_turned_hall", ""),
                 Change("region_state", "matrix_citadel", "stirring")),
        prose="The west hall turns ninety degrees, in place, with nothing "
              "allocated anywhere to hold it while it turns, and stops with its "
              "far door level with the top of the ore line. The Golem had been "
              "the thing preventing that, on the grounds that it could not be "
              "done without a second hall to put the first one in.",
        herald="The Turned Hall is open.", region="matrix_citadel"),
    WorldEvent(
        id="ev_key_bounded_branch", title="The Bounded Branch",
        need=Needs.key("key_bounded_branch"),
        changes=(Change("route_open", "rt_in_order_walk", ""),
                 Change("region_state", "binary_tree_canopy", "stirring")),
        prose="A branch with a floor and a ceiling carved along it. Carry the "
              "bounds down instead of comparing each thing to the things "
              "directly under it, and the walk comes out of the canopy in "
              "exactly the order the Ruins are numbered in. Nobody had ever "
              "finished the walk. The Dragon was why.",
        herald="The In-Order Walk is open.", region="binary_tree_canopy"),
    WorldEvent(
        id="ev_key_counted_leaf", title="The Leaf That Counted",
        need=Needs.key("key_counted_leaf"),
        changes=(Change("route_open", "rt_root_to_leaf", ""),
                 Change("npc", "the_cartographer",
                        "redrawing the village sheet, which she has not "
                        "touched in years")),
        prose="One leaf, pressed flat, and a road under it that runs from the "
              "highest branch in the country down to the root, and the root of "
              "this country is a square with a bell in it. The Ent had been "
              "standing on the last stretch for eleven years insisting that a "
              "node with one child was a leaf and the road therefore ended "
              "there.",
        herald="The Root-to-Leaf Road reaches the village.",
        region="binary_tree_canopy"),
    WorldEvent(
        id="ev_key_ring_of_light", title="The Ring of Light",
        need=Needs.key("key_ring_of_light"),
        changes=(Change("route_open", "rt_shortest_hop", ""),
                 Change("sky", "ash", "the lattice keeps its shape and starts "
                                      "to glow along one line")),
        prose="The Cartographer sets it down in the ash and the light leaves it "
              "in rings, every ruin at the same distance lighting at the same "
              "moment, until one ring touches the village bell and stops. Four "
              "hops. She sits down in the road. It was four hops the whole "
              "time and she has been walking eleven.",
        herald="The Shortest Hop runs from the Wastes to the village.",
        region="graph_wastes"),
    WorldEvent(
        id="ev_key_discarded_maximum", title="The Discarded Maximum",
        need=Needs.key("key_discarded_maximum"),
        changes=(Change("route_open", "rt_discard_line", ""),),
        prose="Everything the marsh threw away, laid end to end across the "
              "reeds and walkable. None of it could ever have won again; that "
              "is the only reason it was thrown. What is still being carried is "
              "at the front, where it has always been, and the Titan is at the "
              "bottom of the pile it was calling max() on.",
        herald="The Discard Line crosses the marsh.",
        region="sliding_window_marsh"),
    WorldEvent(
        id="ev_key_other_undo", title="The Other Undo",
        need=Needs.key("key_other_undo"),
        changes=(Change("route_open", "rt_undo_stair", ""),
                 Change("npc", "the_archivist",
                        "taking the stair down, backwards, out of principle")),
        prose="It was on a hook by the door the whole time, labelled for "
              "whoever came back and finished the job. The stair it opens walks "
              "every change ever made to this realm backwards, one step per "
              "change, and comes out in the village square about four hundred "
              "steps before you were born.",
        herald="The Undo Stair reaches the village square.",
        region="matrix_citadel"),
    WorldEvent(
        id="ev_key_amortised_step", title="The Amortised Step",
        need=Needs.key("key_amortised_step"),
        changes=(Change("route_open", "rt_amortised_run", ""),
                 Change("npc", "the_chronomancer",
                        "at the bottom of the run, timing it")),
        prose="One expensive step off the summit and then a long cheap glide "
              "onto the sand, and averaged across the whole descent it is the "
              "cheapest road in the realm. The Wyrm took this personally to the "
              "end. Correct is not the same as fast, and it had spent an age "
              "being the difference.",
        herald="The Amortised Run drops onto the Coliseum sand.",
        region="complexity_tower"),
    WorldEvent(
        id="ev_key_written_tree", title="The Written Tree",
        need=Needs.key("key_written_tree"),
        changes=(Change("route_open", "rt_written_down", ""),
                 Change("region_state", "recursive_forest", "stirring")),
        prose="The whole wood folded down into one line of road that can be "
              "read back into the wood exactly, and read forward into the "
              "village gate. The Lich could always write. What it could never "
              "once do, in four hundred years of trying, was read its own "
              "handwriting back.",
        herald="The Road Written Down leads home.", region="recursive_forest"),
    WorldEvent(
        id="ev_key_reproduced_fault", title="The Reproduced Fault",
        need=Needs.key("key_reproduced_fault"),
        changes=(Change("route_open", "rt_reproduction_road", ""),
                 Change("shop", "armorer_upgrades",
                        "she will take Coliseum work now")),
        prose="It works on your machine. So you made it fail on your machine, "
              "on purpose, twice in a row, and there was nowhere left for the "
              "Demon to stand. The Armorer starts walking cracked plate down "
              "the new road to the Coliseum, where a fault can be made to "
              "happen again on demand, to the second.",
        herald="The Reproduction Road is open.", region="debugging_dungeon"),
    WorldEvent(
        id="ev_key_unlabelled", title="The Unlabelled Key",
        need=Needs.key("key_unlabelled"),
        changes=(Change("route_open", "rt_road_back_in", ""),
                 Change("npc", "the_interviewer",
                        "at the village end of it, not the castle end")),
        prose="Nothing is stamped on it. No region, no pattern, no difficulty, "
              "no name. You know what it opens because you recognised it, which "
              "was the whole of the examination. It runs the Long Walk Back the "
              "other way, so the exam hall is now a morning's walk from your "
              "own gate whenever you want it. It was always a morning's walk. "
              "Nobody had ever had a reason to come back.",
        herald="The Road Back In is open.", region="null_kings_castle"),

    WorldEvent(
        id="ev_castle_visible", title="The Castle Becomes Visible",
        need=Needs.bosses(7),
        changes=(Change("npc", "the_castle", "it appears on the map, shut"),
                 Change("sky", "void", "")),
        prose="It has been there the whole time. You can see it now from four "
              "places — the Wastes, the Ruins, the tower's top floor and the "
              "Coliseum's back gate — and from all four it is the same distance "
              "away, which is not how distance works.",
        herald="The Null King's Castle is on the map.",
        region="null_kings_castle"),
    WorldEvent(
        id="ev_castle_unsealed", title="The Castle Unseals",
        need=Needs.all_of(Needs.bosses(world.CASTLE_BOSS_REQUIREMENT),
                          Needs.mastery("RECALL", 40),
                          Needs.restored(4)),
        changes=(Change("route_open", "rt_nameless_causeway", ""),
                 Change("route_open", "rt_lit_tiles_road", ""),
                 Change("route_open", "rt_overlook_drop", ""),
                 Change("route_open", "rt_victors_gate", ""),
                 Change("dungeon", "unlabelled_halls", "")),
        prose="Eight powers dead, four regions standing, and enough of the realm "
              "remembered without signposts that the castle has decided you are "
              "worth the walk. All four gates open at once. None of them is "
              "shorter than the others.",
        herald="The Castle is open. Nothing inside it is labelled.",
        region="null_kings_castle"),
    # -- the Standing Portal. The first event is the promise, and it fires on
    # -- the very first key so that fourteen means something for the whole rest
    # -- of the game rather than arriving as a surprise at the end. The second
    # -- is the ending's door. Neither of them touches the practical: see
    # -- world.portal_gates, and see PORTAL below.
    WorldEvent(
        id="ev_portal_wakes", title="Something in the Square Lights Up",
        need=Needs.keys(1),
        changes=(Change("npc", "the_standing_portal",
                        "it has been in the square the entire game"),
                 Change("region_state", "python_village", "stirring")),
        prose="There is a door frame standing in the village square behind the "
              "bell, with no door in it and no wall around it, in the gap "
              "everybody assumed was part of the founders' cellar. It has "
              "fourteen wards cut into the lintel. One of them is now lit. "
              "BYTE, who has stood next to this thing every day of your life, "
              "says: yes. I did know. You could not have opened it.",
        herald="The Standing Portal has one ward lit. There are fourteen.",
        region="python_village"),
    WorldEvent(
        id="ev_portal_opens", title="The Standing Portal Opens",
        need=Needs.all_keys(),
        changes=(Change("npc", "the_standing_portal", "open"),
                 Change("sky", "dawn", "over the village, first of anywhere"),
                 Change("fast_travel", "the_portal",
                        "the square, to the room under the square")),
        prose="Fourteen wards, fourteen things that were holding them, and not "
              "one of them is holding anything now. The frame stops being a "
              "frame. What is on the other side is a room underneath the place "
              "that taught you to read, and the castle was built on top of the "
              "far end of the same room specifically so that nobody would have "
              "to look at it. You end where you began. That was not a "
              "consolation prize; that was the shape of the thing all along.",
        herald="The Standing Portal is open. All fourteen keys are yours.",
        region="python_village"),
    WorldEvent(
        id="ev_realm_restored", title="The Realm Stands",
        need=Needs.restored(8),
        changes=(Change("sky", "dawn", "the light comes back from the east"),
                 Change("region_state", "python_village", "transformed"),
                 Change("fast_travel", "all_roads", "every road is safe to walk")),
        prose="Eight regions repaired by one person who kept turning up. The "
              "roads between them are being walked by other people now — traders, "
              "pilgrims, a school of some kind at the Highlands. You did not set "
              "out to do this. You set out to stop freezing at a blank page.",
        herald="Eight regions restored. The roads are busy again."),
    WorldEvent(
        id="ev_the_source", title="The Source Reopens",
        need=Needs.all_of(Needs.boss("the_interviewer"), Needs.restored(6)),
        changes=(Change("region_state", "null_kings_castle", "transformed"),
                 Change("sky", "dawn", "over the castle, last of anywhere"),
                 Change("npc", "the_source", "the thing under the castle, running")),
        prose="Under the castle is the Source: the thing every program in the "
              "realm was written against, and the thing the Shattering took "
              "apart. It comes back up in one piece. It was never broken. It was "
              "waiting for somebody who could read it without being told what it "
              "was.",
        herald="The Source is running again.", region="null_kings_castle"),
)

EVENT_BY_ID = {e.id: e for e in WORLD_EVENTS}


# ---------------------------------------------------------------------------
# The key ring and the Standing Portal
# ---------------------------------------------------------------------------
# world.py owns what the fourteen keys ARE — their names, whose they were, what
# each is proof of. This module owns what they DO, which is roads. The two are
# joined by one string per key (`world.KEYS[i]["opens"]` is a route id in this
# file) and `verify_no_orphans()` refuses to let that string be wrong: every key
# must name a real road, every key road must be gated on exactly that key, and
# no key road may be the only way to anywhere.
#
# THE PORTAL AND THE PRACTICAL. Said once more here, where the gate is actually
# evaluated, because this is the line that would be easiest to cross by accident
# and the most damaging to cross. The Standing Portal gates the STORY CLIMAX.
# The Timed Practical Mode practical is a MEASUREMENT and is reachable from the menu
# at any time with no keys, no roads, no bosses and no portal —
# `finalexam.sealed()` is the one capability check in this game and nothing
# here is a second one. `portal_blocks()` exists so that a caller can ask that
# question out loud instead of remembering the answer.

PORTAL = world.THE_STANDING_PORTAL
PORTAL_NEED = Needs.all_keys()
PORTAL_REGION = world.THE_STANDING_PORTAL["region"]

KEY_ROUTE = {key["id"]: key["opens"] for key in world.KEYS}


def portal_open(prog: dict) -> bool:
    """All fourteen, or not open. There is no partial credit on a door."""
    return need_status(PORTAL_NEED, prog)["met"]


def portal_blocks(what: str) -> bool:
    """Does the portal stand in front of `what`? Never the measurement.

    Delegates to world.portal_gates so there is exactly one answer in the
    codebase. Anything unrecognised is not gated: the default is open, because
    a door that locks things nobody has thought of yet is a door that will one
    day lock the exam.
    """
    return world.portal_gates(what)


def keyring_view(prog: dict) -> dict:
    """Fourteen keys, what each one is, and what each one opened.

    This is the payload behind E: a key in hand opens a road, and the road has
    a name and a destination the player can read before they walk it.
    """
    held = set(world.keys_held(prog["cleared_bosses"]))
    rows = []
    for key in world.KEYS:
        route = ROUTE_BY_ID.get(key["opens"])
        boss = world.BOSS_BY_ID.get(key["boss"], {})
        rows.append({
            "id": key["id"], "name": key["name"],
            "held": key["id"] in held,
            "boss": key["boss"], "boss_name": boss.get("name", key["boss"]),
            "region": key["region"],
            "region_name": world.REGION_BY_ID[key["region"]]["name"],
            "sigil": key["sigil"], "colour": key["colour"],
            "line": key["line"],
            "opens": key["opens"], "opens_name": key["opens_name"],
            "route_name": route.name if route else "",
            "route_from": route.frm if route else "",
            "route_to": route.to if route else "",
            "route_to_name": world.REGION_BY_ID[route.to]["name"] if route else "",
            "route_open": key["id"] in held,
            "route_prose": route.prose if route else "",
            "one_way": bool(route and not route.two_way),
        })
    return {
        "keys": rows,
        "held": len(held),
        "total": len(world.KEYS),
        "percent": round(100 * _ratio(len(held), len(world.KEYS))),
        "roads_opened": [row["route_name"] for row in rows if row["held"]],
        "note": "A key is proof you were somewhere and beat what lived there. "
                "It is derived from the kill, so it cannot be lost, sold or "
                "desynchronised from the thing it is proof of.",
    }


def portal_view(prog: dict) -> dict:
    """The Standing Portal, as the village square renders it.

    Readable from the first key onward, on purpose: fourteen is only a number
    worth caring about if you can see the counter the whole way up.
    """
    ring = keyring_view(prog)
    is_open = ring["held"] >= len(world.KEYS)
    missing = [row for row in ring["keys"] if not row["held"]]
    status = need_status(PORTAL_NEED, prog)
    return {
        "id": PORTAL["id"], "name": PORTAL["name"],
        "region": PORTAL_REGION,
        "region_name": world.REGION_BY_ID[PORTAL_REGION]["name"],
        "where": PORTAL["where"], "blurb": PORTAL["blurb"], "law": PORTAL["law"],
        "sprite": PORTAL["sprite"], "colour": PORTAL["colour"],
        "accent": PORTAL["accent"],
        "open": is_open,
        "held": ring["held"], "required": len(world.KEYS),
        "percent": ring["percent"],
        "requirement": status["label"],
        "line": PORTAL["open_line"] if is_open else PORTAL["locked_line"],
        "wards": [{"key": row["id"], "name": row["name"], "lit": row["held"],
                   "colour": row["colour"], "sigil": row["sigil"]}
                  for row in ring["keys"]],
        "missing": [{"key": row["id"], "name": row["name"],
                     "boss": row["boss"], "boss_name": row["boss_name"],
                     "region": row["region"], "region_name": row["region_name"]}
                    for row in missing],
        "seen": ring["held"] >= 1 or "ev_portal_wakes" in prog["events_fired"],
        # The whole point, restated in the payload so a client cannot render
        # this panel without the sentence being right there in the data.
        "gates": list(world.PORTAL_GATES),
        "never_gates": list(world.PORTAL_NEVER_GATES),
        "practical_requires_keys": False,
        "note": "This portal gates the story climax. The Timed Practical Mode "
                "practical is a measurement and is reachable from the menu at "
                "any time with no keys at all.",
    }


# ---------------------------------------------------------------------------
# The level curve
# ---------------------------------------------------------------------------
# world.level_for grows the requirement 18% per level, forever. That is right for
# the first twenty levels and wrong after: at level 40 a single level costs about
# 76,000 XP, which at realistic rates is several hundred graded solves for one
# attribute point and a number going up. Here the growth rate DECAYS by half
# every fourteen levels, so the requirement converges instead of exploding.
#
# The consequence, in real numbers (see self_check): the requirement converges
# on about 4,250 XP per level and never exceeds 4,130 inside the playable range,
# against world.py's 76,310 at level 40 and 2,090,353 at level 60. Past thirty, a
# level is roughly one good session, permanently, which is the point.

BASE_REQUIREMENT = 120
GROWTH_START = 0.18
GROWTH_HALF_LIFE = 14.0
MAX_LEVEL = 99

_REQUIREMENTS: list = []


def _build_requirements() -> list:
    reqs = [0, BASE_REQUIREMENT]           # index is level; reqs[L] = L -> L+1
    need = float(BASE_REQUIREMENT)
    for level in range(2, MAX_LEVEL + 1):
        growth = 1.0 + GROWTH_START * (0.5 ** ((level - 2) / GROWTH_HALF_LIFE))
        need *= growth
        reqs.append(int(round(need)))
    return reqs


_REQUIREMENTS = _build_requirements()

_CUMULATIVE: list = [0]
for _level in range(1, MAX_LEVEL + 1):
    _CUMULATIVE.append(_CUMULATIVE[-1] + _REQUIREMENTS[_level])


def xp_needed(level: int) -> int:
    """XP to go from `level` to `level + 1`."""
    if level < 1:
        return _REQUIREMENTS[1]
    if level >= MAX_LEVEL:
        return _REQUIREMENTS[MAX_LEVEL]
    return _REQUIREMENTS[level]


def total_xp_for(level: int) -> int:
    """Cumulative XP at which `level` is reached."""
    level = max(1, min(level, MAX_LEVEL))
    return _CUMULATIVE[level - 1]


def level_for(xp: int) -> int:
    """Signature-compatible with world.level_for, so the engine can adopt this
    curve without touching any call site."""
    xp = max(0, int(xp))
    level = 1
    while level < MAX_LEVEL and xp >= _CUMULATIVE[level]:
        level += 1
    return level


def xp_to_next(xp: int) -> tuple:
    """(into this level, required for the next) — same shape as world.xp_to_next."""
    level = level_for(xp)
    into = xp - _CUMULATIVE[level - 1]
    return into, xp_needed(level)


# Every level gives something real. Attribute points alone are a number going up;
# a number going up is not a reward, it is a receipt.
CAP_CYCLE = (
    {"stat": "stamina_max", "amount": 2, "text": "+2 maximum stamina"},
    {"stat": "mana_max", "amount": 3, "text": "+3 maximum focus"},
)

CONSUMABLE_CYCLE = ("probe_scroll", "focus_elixir", "whetstone", "stamina_draught",
                    "insight_tonic", "combo_ward")

# Named grants at specific levels. These are things, not numbers: a road, a key,
# a person who will now talk to you, a rematch that was not on offer before.
LEVEL_MILESTONES = {
    2: {"name": "The Armorer's Bench", "kind": "unlock",
        "text": "The Armorer will repair your plate while you wait, and will "
                "explain the crack if you ask."},
    3: {"name": "Cartographer's Blank", "kind": "unlock",
        "text": "The world map opens: routes, danger ratings, and the roads you "
                "have not walked drawn as dashes."},
    5: {"name": "First Whistle", "kind": "unlock",
        "text": "You can call a found companion to travel with you. Finding one "
                "is still on you."},
    7: {"name": "Shrine Attunement", "kind": "unlock",
        "text": "Shrines will take your answer without the mentor present."},
    10: {"name": "Second Loadout", "kind": "slot",
         "text": "A second saved loadout, swappable outside battle."},
    12: {"name": "Dungeon Lantern", "kind": "unlock",
         "text": "Dungeon floors stay mapped once walked, including the ones you "
                 "left in a hurry."},
    15: {"name": "Boss Rematch: Tier II", "kind": "unlock",
         "text": "Defeated bosses will fight you again, disguised, for real "
                 "stakes."},
    18: {"name": "The Ranger's Road Sense", "kind": "unlock",
         "text": "Route danger is shown against your level before you commit to "
                 "the walk."},
    20: {"name": "Third Loadout", "kind": "slot",
         "text": "A third saved loadout, and the Armorer halves respec cost."},
    22: {"name": "Mentor's Audience", "kind": "unlock",
         "text": "Any mentor will see you without an appointment, including the "
                 "Oracle, who claims to be busy."},
    25: {"name": "The Long Memory", "kind": "unlock",
         "text": "Thirty-day retests become available, and they are worth more "
                 "than anything else in the game."},
    28: {"name": "Deep Delve", "kind": "unlock",
         "text": "Dungeons past floor six roll their own layouts, monsters and "
                 "treasure each descent."},
    30: {"name": "Boss Rematch: Tier III", "kind": "unlock",
         "text": "Bosses return at full strength with their tells removed."},
    33: {"name": "The Chronomancer's Clock", "kind": "unlock",
         "text": "You may set your own time target on any encounter and be "
                 "graded against it."},
    36: {"name": "Cartographer's Full Sheet", "kind": "unlock",
         "text": "Hidden routes show as question marks in the region that holds "
                 "them. Not where. Just that."},
    40: {"name": "The Armorer's Last Plate", "kind": "unlock",
         "text": "Legendary Plate can be forged, if you have earned the parts."},
    45: {"name": "Free Passage", "kind": "unlock",
         "text": "Fast travel between any two regions you have restored."},
    50: {"name": "The Examiner's Attention", "kind": "unlock",
         "text": "Timed Practical Mode will run a full loop, unlabelled, on demand."},
    55: {"name": "The Nameless Trial", "kind": "unlock",
         "text": "The castle's rooms re-roll on request. Nothing in them is ever "
                 "labelled, and nothing is ever labelled the same way twice."},
    60: {"name": "The Open Door", "kind": "unlock",
         "text": "Every dungeon, every rematch, every region, permanently. There "
                 "is nothing left to unlock. There is plenty left to learn."},
}


def level_grant(level: int) -> dict:
    """Exactly what arriving at `level` hands the player. Never empty."""
    grants = []
    points = items.POINTS_PER_LEVEL
    grants.append(f"+{points} attribute points")

    cap = CAP_CYCLE[(level - 1) % len(CAP_CYCLE)]
    grants.append(cap["text"])

    # A purse every level, scaled, so that even a level between milestones buys
    # something at the Armorer rather than only moving a number.
    gold = 20 + 10 * level
    grants.append(f"{gold} gold")

    consumable = None
    if level % 2 == 0:
        consumable = CONSUMABLE_CYCLE[(level // 2 - 1) % len(CONSUMABLE_CYCLE)]
        grants.append(f"one {consumable.replace('_', ' ')}")

    milestone = LEVEL_MILESTONES.get(level)
    if milestone:
        grants.append(milestone["name"])

    title = None
    for threshold, name in world.TITLES:
        if threshold == level:
            title = name
    if title:
        grants.append(f"the title {title}")

    return {
        "level": level,
        "points": points,
        "gold": gold,
        "cap": cap,
        "consumable": consumable,
        "milestone": milestone,
        "title": title,
        "grants": grants,
        "xp_required": xp_needed(max(1, level - 1)),
    }


def next_level_summary(xp: int) -> dict:
    """The readable answer to 'what does the next level actually give me'."""
    level = level_for(xp)
    into, need = xp_to_next(xp)
    grant = level_grant(level + 1)
    remaining = max(0, need - into)
    headline = "; ".join(grant["grants"])
    return {
        "level": level,
        "next_level": level + 1,
        "xp_into_level": into,
        "xp_for_level": need,
        "xp_remaining": remaining,
        "percent": round(100 * _ratio(into, need)),
        "title_now": world.title_for(level),
        "title_next": grant["title"],
        "grant": grant,
        "summary": f"Level {level + 1} in {remaining} XP: {headline}.",
    }


def level_table(start: int = 1, end: int = 60) -> list:
    """The whole ladder, for the progression screen."""
    return [{**level_grant(level),
             "cumulative_xp": total_xp_for(level),
             "title": world.title_for(level)}
            for level in range(max(1, start), min(end, MAX_LEVEL) + 1)]


# ---------------------------------------------------------------------------
# Prestige — recognition for mastery, not for hours
# ---------------------------------------------------------------------------
# Every term in the prestige score is graded evidence: unaided clears, retention,
# speed against target, first-try passes. None of it moves by walking around, and
# none of it can be bought. That is the point of having it at all.

@dataclass(frozen=True)
class Accolade:
    id: str
    name: str
    need: Need
    blurb: str


ACCOLADES = (
    Accolade("acc_unaided", "Unaided", Needs.stat("unaided_total", 25),
             "Twenty-five encounters cleared with no spell cast. The number that "
             "an examiner is actually measuring."),
    Accolade("acc_fluent", "Fluent", Needs.mastery("PYTHON", 80),
             "The language costs you nothing. Everything else is now the hard "
             "part, which is the correct arrangement."),
    Accolade("acc_long_memory", "The Long Memory", Needs.stat("retained_skills", 5),
             "Five patterns survived a delayed, disguised retest. Retention is "
             "the only evidence that generalises."),
    Accolade("acc_standards", "Nine Standards", Needs.stat("skills_at_60", 9),
             "Nine skills held at sixty mastery at once. Breadth, held, not "
             "visited."),
    Accolade("acc_first_try", "First Try", Needs.stat("first_try_total", 15),
             "Fifteen encounters passed every hidden trial on the first "
             "submission."),
    Accolade("acc_fast", "Under the Clock", Needs.stat("fast_skills", 4),
             "Four skills at speed sixty or better. Correct, and then correct "
             "in time."),
    Accolade("acc_unlabelled", "Nothing Labelled", Needs.mastery("RECALL", 60),
             "You recognise the family when nothing in the room names it."),
    Accolade("acc_mastered", "Mastered", Needs.stat("mastered_skills", 3),
             "Three skills at the final stage: boss down, and retained across "
             "intervals afterward."),
    Accolade("acc_explainer", "Says It First", Needs.mastery("COMMUNICATION", 55),
             "You state the approach before the first keystroke, reliably."),
    Accolade("acc_own_bug", "Finds Their Own Bug", Needs.mastery("DEBUGGING", 70),
             "The single most valuable trait the realm knows how to measure."),
)

PRESTIGE_RANKS = ((0, "Unranked"), (60, "Marked"), (160, "Named"),
                  (320, "Cited"), (560, "Renowned"), (860, "Legend of the Source"))


def prestige(prog: dict) -> dict:
    """Standing, computed from evidence. Grinding easy encounters moves this
    barely; retaining a hard pattern for a month moves it a lot."""
    score = 0.0
    for data in prog["skills"].values():
        # Mastery counts, but mastery you have KEPT counts double, and mastery
        # you can produce unaided and on time counts more than either.
        score += data["mastery"] * 0.25
        score += data["retention"] * 0.35
        score += data["speed"] * 0.15
        score += data["unaided_clears"] * 1.5
    score = round(score)
    rank = PRESTIGE_RANKS[0][1]
    next_rank = None
    next_at = 0
    for threshold, name in PRESTIGE_RANKS:
        if score >= threshold:
            rank = name
        elif next_rank is None:
            next_rank, next_at = name, threshold
    earned = []
    pending = []
    for accolade in ACCOLADES:
        status = need_status(accolade.need, prog)
        row = {"id": accolade.id, "name": accolade.name, "blurb": accolade.blurb,
               "label": status["label"], "percent": round(100 * status["ratio"])}
        (earned if status["met"] else pending).append(row)
    pending.sort(key=lambda row: -row["percent"])
    return {
        "score": score,
        "rank": rank,
        "next_rank": next_rank,
        "next_at": next_at,
        "to_next": max(0, next_at - score) if next_rank else 0,
        "earned": earned,
        "pending": pending,
        "note": "Prestige moves on graded evidence only. Time spent in the realm "
                "does not appear in this number anywhere.",
    }


# ---------------------------------------------------------------------------
# Region state
# ---------------------------------------------------------------------------
# Ruined, stirring, restored, transformed — and each one is earned in that
# region, by that region's work. A player who grinds hash maps does not restore
# the Marsh, and the Marsh should look like it.

REGION_STATE_PROSE = {
    "ruined": "Nothing here is standing that does not have to.",
    "stirring": "Somebody has started clearing the road. It was probably you.",
    "restored": "It works again. People who left have started coming back.",
    "transformed": "It is better than it was before the Shattering, and the "
                   "people here know exactly why.",
}

# What the renderer does about it: the palette darkens or lifts, and the sky is
# the loudest signal the player gets that the world noticed.
REGION_STATE_VISUALS = {
    "ruined": {"palette_shift": -0.35, "sky": "overcast", "npc_density": 0},
    "stirring": {"palette_shift": -0.1, "sky": "clearing", "npc_density": 2},
    "restored": {"palette_shift": 0.1, "sky": "clear", "npc_density": 5},
    "transformed": {"palette_shift": 0.3, "sky": "radiant", "npc_density": 9},
}

BOSSES_BY_REGION: dict = {}
for _b in world.BOSSES:
    BOSSES_BY_REGION.setdefault(_b["region"], []).append(_b)


def region_state(region_id: str, skills_folded: dict, cleared_bosses: set) -> str:
    """The visible state of one region, from progress made in that region."""
    region = world.REGION_BY_ID.get(region_id)
    if region is None:
        return "ruined"
    data = skills_folded.get(region["skill"], {})
    mastery = data.get("mastery", 0.0)
    retention = data.get("retention", 0.0)
    clears = data.get("clears", 0)
    region_bosses = BOSSES_BY_REGION.get(region_id, [])
    bosses_down = all(b["id"] in cleared_bosses for b in region_bosses) \
        if region_bosses else clears >= 6

    if mastery >= 78 and retention >= 45 and bosses_down:
        return "transformed"
    if mastery >= 50 and bosses_down:
        return "restored"
    if mastery >= 20:
        return "stirring"
    return "ruined"


def region_view(region_id: str, prog: dict) -> dict:
    """One region, fully annotated: state, what moves it next, what is in it."""
    region = world.REGION_BY_ID[region_id]
    state_name = prog["region_states"][region_id]
    index = _state_rank(state_name)
    next_state = REGION_STATES[index + 1] if index + 1 < len(REGION_STATES) else None
    data = prog["skills"].get(region["skill"], {})
    region_bosses = BOSSES_BY_REGION.get(region_id, [])
    if next_state == "stirring":
        toward = f"{region['skill']} mastery {round(data.get('mastery', 0))}/20"
    elif next_state == "restored":
        outstanding = [b["name"] for b in region_bosses
                       if b["id"] not in prog["cleared_bosses"]]
        toward = (f"{region['skill']} mastery {round(data.get('mastery', 0))}/50"
                  + (", and " + " and ".join(outstanding) if outstanding else ""))
    elif next_state == "transformed":
        toward = (f"{region['skill']} mastery {round(data.get('mastery', 0))}/78 "
                  f"and retention {round(data.get('retention', 0))}/45 — the "
                  f"pattern held across intervals, not just cleared")
    else:
        toward = "nothing. This region is finished, and it shows."
    return {
        "id": region_id,
        "name": region["name"],
        "numeral": region["numeral"],
        "skill": region["skill"],
        "biome": region["biome"],
        "palette": region["palette"],
        "blurb": region["blurb"],
        "physical": region["physical"],
        "mentor": region["mentor"],
        "music": region["music"],
        "state": state_name,
        "state_prose": REGION_STATE_PROSE[state_name],
        "visuals": REGION_STATE_VISUALS[state_name],
        "next_state": next_state,
        "toward_next": toward,
        "danger": REGION_DANGER.get(region_id, 1),
        "town_tier": world.town_tier(data.get("mastery", 0.0)),
        "bosses": [{"id": b["id"], "name": b["name"],
                    "cleared": b["id"] in prog["cleared_bosses"]}
                   for b in region_bosses],
        "dungeons": [{"id": d["id"], "name": d["name"], "floors": d["floors"],
                      "blurb": d["blurb"],
                      "open": need_status(d["need"], prog)["met"],
                      "requirement": need_status(d["need"], prog)["label"],
                      "cleared": d["id"] in prog["dungeons"]}
                     for d in DUNGEONS_BY_REGION.get(region_id, [])],
        "pet": next((p for p in PETS if p["region"] == region_id
                     and p["id"] not in prog["pets"]), None),
        # The keys this ground owes or has already paid, so the map screen can
        # draw a key on a region rather than hiding the whole system in a menu.
        "keys": [{"id": k["id"], "name": k["name"], "boss": k["boss"],
                  "held": k["id"] in prog["keys"], "colour": k["colour"],
                  "opens": k["opens_name"]}
                 for k in world.KEYS_BY_REGION.get(region_id, [])],
        "portal": portal_view(prog) if region_id == PORTAL_REGION else None,
    }


# ---------------------------------------------------------------------------
# The snapshot — one fold of engine state into the shape everything here reads
# ---------------------------------------------------------------------------


def new_world_state() -> dict:
    """This module's own persisted sub-state. Add under state["world"]; the
    engine's _merge already forward-fills new keys for old saves."""
    return {
        "events_fired": [],       # world event ids, in the order they fired
        "discovered": [],         # hidden route ids the player has found
        "npcs": [],               # npc ids now standing somewhere
        "sky": "dawn",            # current sky, last event to change it wins
        "fast_travel": [],        # fast travel networks unlocked
        "region_states": {},      # last-seen state, so a change can be announced
        "routes_walked": [],      # which roads have actually been used
    }


class _Shim:
    """curriculum.chapter_progress wants objects with .mastery/.clears."""

    def __init__(self, data):
        self.mastery = data["mastery"]
        self.clears = data["clears"]
        self.unaided_clears = data["unaided_clears"]


def _fold_skills(raw) -> dict:
    folded = {}
    for name, value in (raw or {}).items():
        source = value if isinstance(value, dict) else value.__dict__
        folded[name] = {
            "mastery": float(source.get("mastery", 0.0)),
            "clears": int(source.get("clears", 0)),
            "unaided_clears": int(source.get("unaided_clears", 0)),
            "first_try_clears": int(source.get("first_try_clears", 0)),
            "attempts": int(source.get("attempts", 0)),
            "retention": float(source.get("retention", 0.0)),
            "speed": float(source.get("speed", 0.0)),
            "stage": source.get("stage", "UNKNOWN"),
        }
    for name in skillmod.SKILLS:
        folded.setdefault(name, {"mastery": 0.0, "clears": 0, "unaided_clears": 0,
                                 "first_try_clears": 0, "attempts": 0,
                                 "retention": 0.0, "speed": 0.0, "stage": "UNKNOWN"})
    return folded


def _quests_done(state: dict) -> tuple:
    """Completed quests, as ids and as a count.

    Quests live in story.py as main beats and mentor chain steps; a completed one
    is an id in story["fired"]. We resolve against story's own tables when it is
    importable and fall back to prefix matching when it is not, so this module
    never hard-depends on the narrative build.
    """
    fired = set((state.get("story") or {}).get("fired", []))
    explicit = set(state.get("quests_completed", []) or [])
    # Side quests live in quests.py and keep their own ledger. A quest the player
    # turned in there has to count toward `Needs.quests(n)` here, or the roads it
    # was meant to open stay shut.
    explicit |= set(((state.get("quests") or {}) if isinstance(
        state.get("quests"), dict) else {}).get("done") or [])
    known: set = set()
    try:
        from . import story as storymod
        known = set(getattr(storymod, "MAIN_BY_ID", {})) \
            | set(getattr(storymod, "STEP_BY_ID", {})) \
            | {c.id for c in getattr(storymod, "SIDE_CHAINS", [])}
    except Exception:
        known = set()
    if known:
        done = (fired & known) | explicit
    else:
        done = {fid for fid in fired
                if fid.startswith("main_") or fid.startswith("ms_")} | explicit
    # A finished chain counts as one quest as well as its steps counting
    # individually; the player experienced both, and the count is used for
    # pacing, not for scoring.
    try:
        from . import story as storymod
        chains = (state.get("story") or {}).get("chains", {})
        for chain in getattr(storymod, "SIDE_CHAINS", []):
            if chains.get(chain.id, 0) >= len(chain.steps):
                done.add(chain.id)
    except Exception:
        pass
    return done, len(done)


def _pet_ids(state: dict) -> set:
    """Which animals the player has actually found.

    `pets.new_state()` is a dict with a `found` list in it, and older saves kept
    a bare list of ids or of rows. All three are read here rather than in three
    places, because the map screen quietly showing no companions is exactly the
    kind of bug a shape disagreement produces.
    """
    raw = state.get("pets") or []
    if isinstance(raw, dict):
        raw = raw.get("found") or []
    found = set()
    for entry in raw:
        if isinstance(entry, str):
            found.add(entry)
        elif isinstance(entry, dict):
            pet_id = entry.get("id")
            if pet_id and (entry.get("found", True) or entry.get("owned", False)):
                found.add(pet_id)
    return found & set(PET_BY_ID)


def snapshot(state: dict, skills=None, *, readiness: dict | None = None) -> dict:
    """Fold the engine's save into the flat shape every function here reads.

    Accepts either Game.skills (typed) or state["skills"] (raw dicts), same as
    story.build_context, because the engine has both to hand.
    """
    folded = _fold_skills(skills if skills is not None else state.get("skills"))
    player = state.get("player") or {}
    world_state = state.get("world") or new_world_state()

    shimmed = {k: _Shim(v) for k, v in folded.items()}
    graduated = set()
    chapter_ratio = {}
    for chapter in curriculum.CHAPTERS:
        progress = curriculum.chapter_progress(shimmed, chapter)
        chapter_ratio[chapter.id] = progress["percent"] / 100.0
        if progress["graduated"]:
            graduated.add(chapter.id)

    cleared_bosses = set(state.get("cleared_bosses") or [])
    states = {region["id"]: region_state(region["id"], folded, cleared_bosses)
              for region in world.REGIONS}
    restored_count = sum(1 for name in states.values()
                         if _state_rank(name) >= _state_rank("restored"))

    quests, quests_done = _quests_done(state)
    carried = set(state.get("inventory") or []) | set(
        (state.get("equipped") or {}).values())

    stats = dict(state.get("stats") or {})
    # Derived evidence counters the accolades read. Computed here so that no
    # accolade can ever be satisfied by a stat the engine merely incremented for
    # showing up.
    stats["unaided_total"] = sum(d["unaided_clears"] for d in folded.values())
    stats["first_try_total"] = sum(d["first_try_clears"] for d in folded.values())
    stats["retained_skills"] = sum(
        1 for d in folded.values()
        if _stage_rank(d["stage"]) >= _stage_rank("RETAINED"))
    stats["mastered_skills"] = sum(1 for d in folded.values()
                                   if d["stage"] == "MASTERED")
    stats["skills_at_60"] = sum(1 for d in folded.values() if d["mastery"] >= 60)
    stats["fast_skills"] = sum(1 for d in folded.values() if d["speed"] >= 60)

    xp = int(player.get("xp", 0) or 0)
    level = int(player.get("level") or level_for(xp) or 1)

    return {
        "region": player.get("region", "python_village"),
        "level": level,
        "xp": xp,
        "skills": folded,
        "chapters_graduated": graduated,
        "chapter_ratio": chapter_ratio,
        "chapter_index": curriculum.frontier(shimmed),
        "cleared_bosses": cleared_bosses,
        # Keys, derived. Never read out of the save — there is nothing in the
        # save to read. See world.keys_held.
        "keys": set(world.keys_held(cleared_bosses)),
        "keys_held": len(world.keys_held(cleared_bosses)),
        "items": carried,
        "secrets": set(state.get("secrets_found") or []),
        "quests": quests,
        "quests_done": quests_done,
        "dungeons": set(state.get("dungeons_cleared") or []),
        "pets": _pet_ids(state),
        "stats": stats,
        "region_states": states,
        "restored_count": restored_count,
        "events_fired": set(world_state.get("events_fired") or []),
        "discovered": set(world_state.get("discovered") or []),
        "npcs": list(world_state.get("npcs") or []),
        "sky": world_state.get("sky", "dawn"),
        "fast_travel": list(world_state.get("fast_travel") or []),
        "unspent_points": int(state.get("unspent_points", 0) or 0),
        "readiness": readiness or {},
        "gates_passed": (readiness or {}).get("gates_passed", 0),
    }


# ---------------------------------------------------------------------------
# Travel
# ---------------------------------------------------------------------------

ROUTE_OPEN = "open"        # walk it
ROUTE_SOFT = "soft"        # walk it, and be told plainly what is down there
ROUTE_WALL = "wall"        # the story says no, and says why
ROUTE_HIDDEN = "hidden"    # not on the map yet


def route_status(route: Route, prog: dict, *, frm: str | None = None) -> dict:
    """One road, as the map screen prints it."""
    status = need_status(route.need, prog)
    if status["met"]:
        state_name = ROUTE_OPEN
    elif route.need.kind == "discovery":
        state_name = ROUTE_HIDDEN
    elif route.wall:
        state_name = ROUTE_WALL
    else:
        state_name = ROUTE_SOFT
    origin = frm or route.frm
    destination = route_other_end(route, origin)
    gap = route.danger - prog["level"]
    if state_name == ROUTE_HIDDEN:
        warning = ""
    elif gap >= 10:
        warning = ("Nothing on this road is scaled to you. You will be allowed "
                   "all the way in, and it will not go well.")
    elif gap >= 5:
        warning = "You are under-levelled for what is down there by some margin."
    elif gap >= 2:
        warning = "A stretch above your weight. Survivable, expensively."
    else:
        warning = ""
    return {
        "id": route.id,
        "name": route.name,
        "kind": route.kind,
        "from": origin,
        "to": destination,
        "to_name": world.REGION_BY_ID[destination]["name"],
        "state": state_name,
        "passable": state_name in (ROUTE_OPEN, ROUTE_SOFT),
        "requirement": status["label"],
        "percent": round(100 * status["ratio"]),
        "prose": route.prose,
        "danger": route.danger,
        "warning": warning,
        "one_way": not route.two_way,
    }


def open_routes(prog: dict, region_id: str | None = None) -> list:
    """Every road out of a region the player may actually take right now."""
    origin = region_id or prog["region"]
    out = []
    for _, route in _EDGES.get(origin, []):
        status = route_status(route, prog, frm=origin)
        if status["passable"]:
            out.append(status)
    return out


def reachable(prog: dict, start: str | None = None) -> set:
    """Flood fill over passable routes. This is the function the connectivity
    proof in self_check leans on."""
    origin = start or prog["region"]
    seen = {origin}
    stack = [origin]
    while stack:
        here = stack.pop()
        for neighbour, route in _EDGES.get(here, []):
            if neighbour in seen:
                continue
            if route_status(route, prog, frm=here)["passable"]:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def path_between(prog: dict, start: str, goal: str) -> list:
    """Shortest passable route list from start to goal, or [] if there is none."""
    if start == goal:
        return []
    queue = [(start, [])]
    seen = {start}
    while queue:
        here, trail = queue.pop(0)
        for neighbour, route in _EDGES.get(here, []):
            if neighbour in seen:
                continue
            if not route_status(route, prog, frm=here)["passable"]:
                continue
            if neighbour == goal:
                return trail + [route.id]
            seen.add(neighbour)
            queue.append((neighbour, trail + [route.id]))
    return []


def can_travel(prog: dict, route_id: str, *, frm: str | None = None) -> dict:
    """Ask before walking. A soft gate answers yes, with the warning attached."""
    route = ROUTE_BY_ID.get(route_id)
    if route is None:
        return {"ok": False, "reason": "there is no such road"}
    origin = frm or prog["region"]
    if origin not in (route.frm, route.to):
        return {"ok": False, "reason": "that road does not touch this region"}
    if origin == route.to and not route.two_way:
        return {"ok": False, "reason": "that road only runs the other way"}
    status = route_status(route, prog, frm=origin)
    if status["passable"]:
        return {"ok": True, **status}
    if status["state"] == ROUTE_HIDDEN:
        return {"ok": False, "reason": "you have not found that road", **status}
    return {"ok": False, "reason": status["requirement"], **status}


def discover_route(state: dict, route_id: str) -> dict:
    """Finding a hidden road. This is the one unlock exploration alone can buy,
    and every hidden road is a shortcut to somewhere already reachable."""
    route = ROUTE_BY_ID.get(route_id)
    if route is None or route.need.kind != "discovery":
        return {"ok": False, "reason": "nothing hidden there"}
    world_state = state.setdefault("world", new_world_state())
    discovered = world_state.setdefault("discovered", [])
    if route_id in discovered:
        return {"ok": False, "reason": "already on your map"}
    discovered.append(route_id)
    return {"ok": True, "route": route.id, "name": route.name,
            "prose": route.prose,
            "announce": f"{route.name} is on your map. Nobody drew it there for you."}


def world_map(state: dict, skills=None, *, readiness: dict | None = None) -> dict:
    """The whole overworld in one payload: nodes, edges, states, where you are."""
    prog = snapshot(state, skills, readiness=readiness)
    here = prog["region"]
    within = reachable(prog)
    nodes = []
    for region in world.REGIONS:
        view = region_view(region["id"], prog)
        view["reachable"] = region["id"] in within
        view["here"] = region["id"] == here
        view["hops"] = len(path_between(prog, here, region["id"])) \
            if region["id"] in within else None
        nodes.append(view)
    edges = []
    for route in ROUTES:
        status = route_status(route, prog)
        if status["state"] == ROUTE_HIDDEN:
            # Hidden roads are drawn as a question mark in their region once the
            # Cartographer's full sheet is earned, and not at all before.
            if prog["level"] < 36:
                continue
            status = {**status, "name": "?", "prose": "Something is drawn here and "
                      "then scratched out.", "to_name": "?"}
        edges.append(status)
    return {
        "here": here,
        "nodes": nodes,
        "edges": edges,
        "open_routes": open_routes(prog),
        "reachable": sorted(within),
        "sky": prog["sky"],
        "npcs": prog["npcs"],
        "fast_travel": prog["fast_travel"],
        "restored": prog["restored_count"],
        "events": events_view(prog),
        "keys": keyring_view(prog),
        "portal": portal_view(prog),
        "level": next_level_summary(prog["xp"]),
        "prestige": prestige(prog),
    }


# ---------------------------------------------------------------------------
# Firing events
# ---------------------------------------------------------------------------


def pending_events(prog: dict) -> list:
    """Every event whose need is satisfied and which has not fired yet."""
    return [event for event in WORLD_EVENTS
            if event.id not in prog["events_fired"]
            and need_status(event.need, prog)["met"]]


def events_view(prog: dict) -> dict:
    """Fired, and the three closest to firing — so the world's next move is
    always legible rather than a surprise."""
    fired = [{"id": e.id, "title": e.title, "herald": e.herald, "region": e.region}
             for e in WORLD_EVENTS if e.id in prog["events_fired"]]
    upcoming = []
    for event in WORLD_EVENTS:
        if event.id in prog["events_fired"]:
            continue
        status = need_status(event.need, prog)
        if status["met"]:
            continue
        upcoming.append({"id": event.id, "title": event.title,
                         "requirement": status["label"],
                         "percent": round(100 * status["ratio"]),
                         "region": event.region})
    upcoming.sort(key=lambda row: -row["percent"])
    return {"fired": fired, "upcoming": upcoming[:3], "total": len(WORLD_EVENTS)}


def _apply_changes(world_state: dict, event: WorldEvent) -> list:
    applied = []
    for change in event.changes:
        if change.kind == "npc":
            npcs = world_state.setdefault("npcs", [])
            if change.target not in npcs:
                npcs.append(change.target)
        elif change.kind == "sky":
            world_state["sky"] = change.target
        elif change.kind == "fast_travel":
            network = world_state.setdefault("fast_travel", [])
            if change.target not in network:
                network.append(change.target)
        elif change.kind == "region_state":
            # Deliberately no write. Region state is DERIVED from evidence made
            # in that region; an event may announce that a place is stirring, but
            # it may not declare it. If the derivation disagrees, the derivation
            # is right and the world quietly declines to lie about it.
            pass
        applied.append({"kind": change.kind, "target": change.target,
                        "detail": change.detail})
    return applied


def advance(state: dict, skills=None, *, readiness: dict | None = None) -> dict:
    """Fire everything the player has earned. Call after a graded submission.

    Returns the announcements the client should play, in order. Mutates only
    state["world"], which is this module's own sub-state.
    """
    world_state = state.setdefault("world", new_world_state())
    for key, value in new_world_state().items():
        world_state.setdefault(key, value)

    fired = []
    # Events can satisfy each other's needs (the Castle unseals, its routes open,
    # the vault becomes enterable), so we iterate until the world settles.
    for _ in range(len(WORLD_EVENTS)):
        prog = snapshot(state, skills, readiness=readiness)
        ready = pending_events(prog)
        if not ready:
            break
        for event in ready:
            world_state.setdefault("events_fired", []).append(event.id)
            fired.append({
                "id": event.id,
                "title": event.title,
                "herald": event.herald,
                "prose": event.prose,
                "region": event.region,
                "changes": _apply_changes(world_state, event),
                "routes_opened": [ROUTE_BY_ID[c.target].name
                                  for c in event.changes
                                  if c.kind == "route_open" and c.target in ROUTE_BY_ID],
            })
    prog = snapshot(state, skills, readiness=readiness)
    world_state["region_states"] = dict(prog["region_states"])
    return {"events": fired, "sky": world_state.get("sky", "dawn"),
            "open_routes": open_routes(prog)}


# ---------------------------------------------------------------------------
# No dead ends
# ---------------------------------------------------------------------------
# The hard rule of this codebase is that learning never dead-ends. These four
# are always true, need nothing, and cost nothing, which is what makes the
# guarantee structural rather than hopeful. self_check asserts their needs are
# all `none` and that there are at least three of them.

ALWAYS_AVAILABLE = (
    {"id": "do_training", "kind": "train", "title": "Train at the Camp",
     "region": "python_village", "need": Needs.none(),
     "why": "The Camp always has work at your level. It is the one place in the "
            "realm that never asks you to be ready first.",
     "action": {"kind": "encounter", "region": "python_village"}},
    {"id": "do_shrine", "kind": "shrine", "title": "Answer at a shrine",
     "region": "python_village", "need": Needs.none(),
     "why": "One question, one answer, thirty seconds. Recognition is a skill "
            "and it is trained separately from writing.",
     "action": {"kind": "shrine"}},
    {"id": "do_repair", "kind": "repair", "title": "Repair a broken program",
     "region": "debugging_dungeon", "need": Needs.none(),
     "why": "The Armorer always has cracked plate. Reading a defect is worth "
            "more per minute than writing a correct thing you already know.",
     "action": {"kind": "encounter", "region": "debugging_dungeon"}},
    {"id": "do_fields", "kind": "explore", "title": "Walk the Fields of Syntax",
     "region": "fields_of_syntax", "need": Needs.none(),
     "why": "Open ground, low stakes, and the road out of the village has been "
            "clear since the first day.",
     "action": {"kind": "travel", "region": "fields_of_syntax"}},
)


def available_in(mode: str) -> bool:
    """Timed Practical Mode has no overworld. The measured run is the whole world for
    as long as it lasts."""
    return mode != config.MODE_INTERVIEW


def things_to_do(state: dict, skills=None, *, readiness: dict | None = None,
                 due_retests: int = 0, limit: int = 6) -> list:
    """What could I do right now, and where. Never returns fewer than three.

    Ordered by what the evidence says would help most, not by what is shiniest.
    """
    limit = max(3, limit)
    prog = snapshot(state, skills, readiness=readiness)
    here = prog["region"]
    within = reachable(prog)
    out: list = []
    seen: set = set()

    def offer(entry: dict) -> None:
        if entry["id"] in seen:
            return
        seen.add(entry["id"])
        region_id = entry.get("region") or here
        entry.setdefault("hops", len(path_between(prog, here, region_id)))
        entry.setdefault("region_name",
                         world.REGION_BY_ID.get(region_id, {}).get("name", ""))
        out.append(entry)

    # 1. Retention outranks everything. A pattern due for retest is the single
    #    most valuable thing on the board and the engine already knows it.
    if due_retests:
        offer({"id": "do_retests", "kind": "retest", "priority": 0,
               "title": f"Clear {due_retests} due retest"
                        f"{'s' if due_retests != 1 else ''}",
               "region": here,
               "why": "Delayed recall is the strongest evidence this game "
                      "collects, and it is the only kind that expires.",
               "action": {"kind": "retest"}})

    # 2. The chapter the ladder says they are on.
    objective = curriculum.next_objective({k: _Shim(v)
                                           for k, v in prog["skills"].items()})
    offer({"id": "do_chapter", "kind": "chapter", "priority": 1,
           "title": objective["goal"],
           "region": objective["region"],
           "why": f"{objective['title']} — {objective['progress']['percent']}% "
                  f"through. Focus skill: {objective['focus_skill'] or 'PYTHON'}.",
           "action": {"kind": "encounter", "region": objective["region"]}})

    # 3. A boss this player has the evidence to fight.
    for boss in world.BOSSES:
        if boss["id"] in prog["cleared_bosses"] or boss.get("final"):
            continue
        if boss["region"] not in within:
            continue
        data = prog["skills"].get(boss["skill"], {})
        if curriculum.tier_unlocked(_Shim(data) if data else None, "BOSS"):
            offer({"id": f"do_boss_{boss['id']}", "kind": "boss", "priority": 2,
                   "title": f"Fight {boss['name']}",
                   "region": boss["region"],
                   "why": f"Your {boss['skill']} is past the bar for it. \""
                          f"{boss['taunt']}\"",
                   "action": {"kind": "boss", "boss": boss["id"]}})
            break

    # 3b. The keys. One of the two things this game now ends on, so it sits
    #     directly under the boss that would hand one over. When the portal is
    #     open it outranks nearly everything, because at that point there is
    #     exactly one thing left in the realm the player has not seen.
    if portal_open(prog):
        offer({"id": "do_portal", "kind": "portal", "priority": 0.5,
               "title": "Step through the Standing Portal",
               "region": PORTAL_REGION,
               "why": "Fourteen keys, fourteen things that were holding them. "
                      "The frame in the village square is a doorway now, and "
                      "it opens on the room under the place you started.",
               "action": {"kind": "portal", "portal": PORTAL["id"]}})
    elif prog["keys_held"]:
        nearest = next((k for k in world.KEYS if k["id"] not in prog["keys"]), None)
        if nearest:
            boss = world.BOSS_BY_ID.get(nearest["boss"], {})
            offer({"id": "do_keys", "kind": "keys", "priority": 3.5,
                   "title": f"Take {nearest['name']} from "
                            f"{boss.get('name', 'its holder')}",
                   "region": nearest["region"],
                   "why": f"{prog['keys_held']} of {len(world.KEYS)} wards lit "
                          f"on the portal in the village square. This one opens "
                          f"{nearest['opens_name']}.",
                   "action": {"kind": "boss", "boss": nearest["boss"]}})

    # 4. A dungeon that is open and unfinished.
    for dungeon in DUNGEONS:
        if dungeon["id"] in prog["dungeons"] or dungeon["region"] not in within:
            continue
        if need_status(dungeon["need"], prog)["met"]:
            offer({"id": f"do_dungeon_{dungeon['id']}", "kind": "dungeon",
                   "priority": 3, "title": f"Descend into {dungeon['name']}",
                   "region": dungeon["region"],
                   "why": f"{dungeon['floors']} floors, unfinished. "
                          f"{dungeon['blurb']}",
                   "action": {"kind": "dungeon", "dungeon": dungeon["id"]}})
            break

    # 5. The world event closest to firing — the map's own next move.
    upcoming = events_view(prog)["upcoming"]
    if upcoming:
        nearest = upcoming[0]
        offer({"id": f"do_event_{nearest['id']}", "kind": "event", "priority": 4,
               "title": nearest["title"],
               "region": nearest["region"] or here,
               "why": f"{nearest['requirement']} — {nearest['percent']}% there. "
                      f"The world moves when that lands.",
               "action": {"kind": "objective", "event": nearest["id"]}})

    # 6. Somewhere new that is actually worth walking to.
    for status in sorted(open_routes(prog), key=lambda r: r["danger"]):
        destination = status["to"]
        if destination == here:
            continue
        gap = REGION_DANGER.get(destination, 1) - prog["level"]
        if gap > 6:
            continue
        region = world.REGION_BY_ID[destination]
        offer({"id": f"do_travel_{destination}", "kind": "travel", "priority": 5,
               "title": f"Take {status['name']} to {region['name']}",
               "region": destination,
               "why": status["prose"],
               "action": {"kind": "travel", "region": destination,
                          "route": status["id"]}})
        break

    # 7. A companion hiding in a region they can already reach.
    for pet in PETS:
        if pet["id"] in prog["pets"] or pet["region"] not in within:
            continue
        offer({"id": f"do_pet_{pet['id']}", "kind": "secret", "priority": 6,
               "title": f"Find what is hiding in "
                        f"{world.REGION_BY_ID[pet['region']]['name']}",
               "region": pet["region"], "why": pet["hint"],
               "action": {"kind": "explore", "region": pet["region"]}})
        break

    # 8. Unspent points are a chore, but they are a chore with a payoff.
    if prog["unspent_points"]:
        offer({"id": "do_points", "kind": "build", "priority": 7,
               "title": f"Spend {prog['unspent_points']} attribute points",
               "region": here,
               "why": "Unspent points are power you have earned and are not "
                      "using.",
               "action": {"kind": "allocate"}})

    # 9. The floor. These require nothing, so the list cannot come back empty.
    for entry in ALWAYS_AVAILABLE:
        offer({"id": entry["id"], "kind": entry["kind"], "priority": 8,
               "title": entry["title"], "region": entry["region"],
               "why": entry["why"], "action": dict(entry["action"])})

    out.sort(key=lambda row: (row["priority"], row["hops"]))
    return out[:limit]


# ---------------------------------------------------------------------------
# Static invariants
# ---------------------------------------------------------------------------


def verify_no_orphans() -> dict:
    """No region may hang off a hard wall or a hidden road alone.

    Proof by construction: delete every route that is a wall or hidden, and the
    sixteen mortal regions must still form one connected component. The Castle is
    the single deliberate exception — it is an examination hall, and the story
    requires that walking in early is not on offer.
    """
    soft_edges: dict = {}
    for route in ROUTES:
        if route.wall:
            continue
        soft_edges.setdefault(route.frm, []).append(route.to)
        if route.two_way:
            soft_edges.setdefault(route.to, []).append(route.frm)

    mortal = [r["id"] for r in world.REGIONS if r["id"] != "null_kings_castle"]
    start = mortal[0]
    seen = {start}
    stack = [start]
    while stack:
        here = stack.pop()
        for neighbour in soft_edges.get(here, []):
            if neighbour not in seen and neighbour != "null_kings_castle":
                seen.add(neighbour)
                stack.append(neighbour)
    missing = [r for r in mortal if r not in seen]

    # Every route's endpoints must be real regions, and every event's route
    # changes must name a real route.
    bad_routes = [r.id for r in ROUTES
                  if r.frm not in world.REGION_BY_ID or r.to not in world.REGION_BY_ID]
    bad_changes = [f"{e.id}:{c.target}" for e in WORLD_EVENTS for c in e.changes
                   if c.kind == "route_open" and c.target not in ROUTE_BY_ID]
    bad_dungeons = [f"{e.id}:{c.target}" for e in WORLD_EVENTS for c in e.changes
                    if c.kind == "dungeon" and c.target not in DUNGEON_BY_ID]
    bad_bosses = [f"{e.id}:{c.target}" for e in WORLD_EVENTS for c in e.changes
                  if c.kind == "boss_awakens" and c.target not in world.BOSS_BY_ID]
    bad_regions = [f"{e.id}:{c.target}" for e in WORLD_EVENTS for c in e.changes
                   if c.kind == "region_state" and c.target not in world.REGION_BY_ID]

    # -- the keys. Four separate ways this could be wrong, all of them silent
    # -- if nobody checks: a key that opens nothing, a key road gated on the
    # -- wrong key (or on nothing), two keys claiming the same road, and — the
    # -- one that would actually break the game — a key road that is the only
    # -- way into somewhere. The last is already covered by the connectivity
    # -- proof above, because every key road is a wall and the proof deletes
    # -- every wall; it is asserted here again by name so the reason is written
    # -- down next to the thing it protects.
    key_routes = [r for r in ROUTES if r.need.kind == "key"]
    bad_keys = [k["id"] for k in world.KEYS if k["opens"] not in ROUTE_BY_ID]
    bad_key_bosses = [k["id"] for k in world.KEYS
                      if k["boss"] not in world.BOSS_BY_ID]
    mismatched = []
    for key in world.KEYS:
        route = ROUTE_BY_ID.get(key["opens"])
        if route is None:
            continue
        if route.need.kind != "key" or route.need.key != key["id"]:
            mismatched.append(f'{key["id"]}:{key["opens"]}')
        if not route.wall:
            # A soft key road would be walkable without the key, which makes
            # the key decorative.
            mismatched.append(f'{key["id"]}:{key["opens"]}:not-a-wall')
    unclaimed = [r.id for r in key_routes
                 if r.need.key not in world.KEY_BY_ID]
    doubled = [r.id for r in key_routes
               if sum(1 for k in world.KEYS if k["opens"] == r.id) != 1]
    keyed_regions = {r.frm for r in key_routes} | {r.to for r in key_routes}
    key_only_regions = [region for region in mortal
                        if region in keyed_regions and region not in seen]
    portal_in_village = PORTAL_REGION == "python_village"
    portal_needs_all = (PORTAL_NEED.kind == "keys"
                        and int(PORTAL_NEED.value) == len(world.KEYS))
    portal_seals_nothing = not any(portal_blocks(name)
                                   for name in world.PORTAL_NEVER_GATES)

    return {
        "mortal_regions": len(mortal),
        "connected_without_hard_gates": len(missing) == 0,
        "keys": len(world.KEYS),
        "bosses": len(world.BOSSES),
        "one_key_per_boss": len(world.KEY_BY_BOSS) == len(world.BOSSES),
        "key_routes": len(key_routes),
        "bad_keys": bad_keys,
        "bad_key_bosses": bad_key_bosses,
        "mismatched_key_routes": mismatched,
        "unclaimed_key_routes": unclaimed,
        "doubled_key_routes": doubled,
        "key_only_regions": key_only_regions,
        "portal_in_first_village": portal_in_village,
        "portal_needs_every_key": portal_needs_all,
        "portal_never_gates_the_practical": portal_seals_nothing,
        "orphans": missing,
        "bad_routes": bad_routes,
        "bad_event_routes": bad_changes,
        "bad_event_dungeons": bad_dungeons,
        "bad_event_bosses": bad_bosses,
        "bad_event_regions": bad_regions,
        "always_available": len(ALWAYS_AVAILABLE),
        "always_unconditional": all(entry["need"].kind == "none"
                                    for entry in ALWAYS_AVAILABLE),
    }


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------


def _random_state(rng) -> dict:
    """A plausible save, anywhere on the progression range."""
    level = rng.randint(1, 60)
    xp = total_xp_for(level) + rng.randint(0, max(1, xp_needed(level) - 1))
    # Mastery correlates with level but not perfectly — real players are spiky.
    centre = min(95.0, 4.0 + level * 1.6)
    raw = {}
    for name in skillmod.SKILLS:
        mastery = max(0.0, min(100.0, rng.gauss(centre, 22)))
        clears = int(mastery / rng.uniform(4.0, 12.0))
        raw[name] = {
            "mastery": mastery,
            "clears": clears,
            "unaided_clears": int(clears * rng.uniform(0.2, 0.9)),
            "first_try_clears": int(clears * rng.uniform(0.0, 0.6)),
            "attempts": clears + rng.randint(0, 8),
            "retention": max(0.0, min(100.0, rng.gauss(centre - 18, 25))),
            "speed": max(0.0, min(100.0, rng.gauss(centre - 12, 25))),
            "stage": rng.choice(skillmod.STAGES),
        }
    boss_count = min(len(world.BOSSES), max(0, int(level / 4) + rng.randint(-2, 2)))
    cleared = [b["id"] for b in rng.sample(world.BOSSES, max(0, boss_count))]
    return {
        "player": {"level": level, "xp": xp,
                   "region": rng.choice([r["id"] for r in world.REGIONS])},
        "skills": raw,
        "cleared_bosses": cleared,
        "inventory": [rng.choice(list(items.BY_ID)) for _ in range(rng.randint(0, 6))],
        "equipped": {},
        "secrets_found": [s["id"] for s in items.SECRETS if rng.random() < 0.2],
        "quests_completed": [f"q{i}" for i in range(rng.randint(0, 14))],
        "pets": [p["id"] for p in PETS if rng.random() < 0.35],
        "dungeons_cleared": [d["id"] for d in DUNGEONS if rng.random() < 0.3],
        "stats": {"armor_repairs": rng.randint(0, 20), "shrines": rng.randint(0, 30),
                  "encounters": rng.randint(0, 400)},
        "unspent_points": rng.randint(0, 9),
        "story": {"fired": [], "chains": {}},
        "world": new_world_state(),
    }


def _upgrade(state: dict) -> dict:
    """A strictly-better version of a save, for the monotonicity proof: no gate
    that was open may close because the player got stronger."""
    import copy
    better = copy.deepcopy(state)
    better["player"]["level"] = min(99, better["player"]["level"] + 5)
    better["player"]["xp"] = total_xp_for(better["player"]["level"])
    for data in better["skills"].values():
        data["mastery"] = min(100.0, data["mastery"] + 10)
        data["retention"] = min(100.0, data["retention"] + 10)
        data["speed"] = min(100.0, data["speed"] + 10)
        data["clears"] += 4
        data["unaided_clears"] += 2
    better["cleared_bosses"] = list({b["id"] for b in world.BOSSES[:4]}
                                    | set(better["cleared_bosses"]))
    better["quests_completed"] = better["quests_completed"] + ["extra_1", "extra_2"]
    better["stats"]["armor_repairs"] += 5
    better["pets"] = list({p["id"] for p in PETS[:2]} | set(better["pets"]))
    better["dungeons_cleared"] = list({DUNGEONS[0]["id"]}
                                      | set(better["dungeons_cleared"]))
    return better


def self_check(trials: int = 500, seed: int = 20260911) -> dict:
    """Simulate `trials` random saves across the whole range and prove the three
    promises: the world stays connected, there is always a road, and there is
    always something to do."""
    import random

    rng = random.Random(seed)
    statics = verify_no_orphans()

    mortal = {r["id"] for r in world.REGIONS if r["id"] != "null_kings_castle"}
    failures = {"connectivity": [], "no_open_route": [], "nothing_to_do": [],
                "monotonicity": [], "castle_shut_when_open": [],
                "castle_is_a_trap": [], "announced_but_shut": [],
                "key_road_disagrees": [], "portal_disagrees": [],
                "portal_gated_the_practical": [], "keyless_stranded": [],
                "keyless_nothing_to_do": [], "key_ladder_stranded": []}
    min_reach = 99
    min_routes = 99
    min_todo = 99
    min_candidates = 99
    todo_total = 0
    events_total = 0
    castle_open_states = 0

    for trial in range(trials):
        state = _random_state(rng)
        report = advance(state)                     # fire whatever is earned
        events_total += len(report["events"])
        prog = snapshot(state)
        here = prog["region"]

        # 1. every mortal region reachable from wherever the player is standing
        within = reachable(prog)
        min_reach = min(min_reach, len(within & mortal))
        if not mortal <= within:
            failures["connectivity"].append(
                (trial, here, sorted(mortal - within)))

        # 2. at least one road out, from anywhere, at any state
        roads = open_routes(prog)
        min_routes = min(min_routes, len(roads))
        if not roads:
            failures["no_open_route"].append((trial, here))

        # 3. something to do, always — measured twice: the full candidate list
        #    before truncation, and the list at the smallest limit anyone could
        #    ask for, which the floor of three has to survive.
        candidates = things_to_do(state, due_retests=rng.randint(0, 3), limit=99)
        todo = things_to_do(state, due_retests=0, limit=1)
        min_candidates = min(min_candidates, len(candidates))
        min_todo = min(min_todo, len(todo))
        todo_total += len(candidates)
        if len(todo) < 3 or len(candidates) < 3:
            failures["nothing_to_do"].append((trial, here, len(todo), len(candidates)))

        # 4. the Castle is reachable exactly when it has been unsealed, and is
        #    never a room you cannot walk out of
        unsealed = "ev_castle_unsealed" in prog["events_fired"]
        if unsealed:
            castle_open_states += 1
            if "null_kings_castle" not in within:
                failures["castle_shut_when_open"].append((trial, here))
        castle_prog = dict(prog, region="null_kings_castle")
        if not mortal <= reachable(castle_prog, "null_kings_castle"):
            failures["castle_is_a_trap"].append(trial)

        # 5. an event that announces a road must be announcing a road that is
        #    actually open — the world is not allowed to promise and then not
        #    deliver, which is the failure mode of every unlock-by-cutscene
        for event in WORLD_EVENTS:
            if not need_status(event.need, prog)["met"]:
                continue
            for change in event.changes:
                if change.kind != "route_open":
                    continue
                route = ROUTE_BY_ID[change.target]
                if not need_status(route.need, prog)["met"]:
                    failures["announced_but_shut"].append(
                        (trial, event.id, change.target))

        # 6. a key opens exactly the road it names, and that road is shut
        #    until the key is held. Both directions matter: a road that opens
        #    early makes the key a souvenir, and a road that stays shut with
        #    the key in hand is a promise the world did not keep.
        for key in world.KEYS:
            route = ROUTE_BY_ID[key["opens"]]
            held = key["id"] in prog["keys"]
            passable = route_status(route, prog, frm=route.frm)["passable"]
            if passable != held:
                failures["key_road_disagrees"].append((trial, key["id"], held))

        # 7. the portal is open exactly when all fourteen are in hand, and it
        #    has never in any state stood in front of the measurement.
        if portal_open(prog) != (len(prog["keys"]) == len(world.KEYS)):
            failures["portal_disagrees"].append((trial, len(prog["keys"])))
        if any(portal_blocks(name) for name in world.PORTAL_NEVER_GATES):
            failures["portal_gated_the_practical"].append(trial)

        # 8. getting stronger never closes a road
        better = _upgrade(state)
        advance(better)
        better_prog = snapshot(better)
        for route in ROUTES:
            was = route_status(route, prog)
            now = route_status(route, better_prog)
            if was["passable"] and not now["passable"]:
                failures["monotonicity"].append((trial, route.id))

    # -- THE KEYLESS PROOF -------------------------------------------------
    # The sharp edge of a key economy is the player who cannot beat the boss.
    # Fourteen locked roads must never cost that player a destination or an
    # afternoon, so: take every state again with the kill list emptied, stand
    # the player in each of the seventeen regions in turn, and require the whole
    # mortal map to still be reachable and the board to still hold three things.
    keyless_rng = random.Random(seed + 1)
    keyless_min_reach = 99
    keyless_min_todo = 99
    keyless_states = 0
    for trial in range(trials):
        state = _random_state(keyless_rng)
        state["cleared_bosses"] = []          # has beaten nothing, ever
        advance(state)
        prog = snapshot(state)
        keyless_states += 1
        within = reachable(prog)
        keyless_min_reach = min(keyless_min_reach, len(within & mortal))
        if not mortal <= within:
            failures["keyless_stranded"].append(
                (trial, prog["region"], sorted(mortal - within)))
        todo = things_to_do(state, limit=99)
        keyless_min_todo = min(keyless_min_todo, len(todo))
        if len(todo) < 3:
            failures["keyless_nothing_to_do"].append((trial, prog["region"]))

    # -- THE KEY LADDER ----------------------------------------------------
    # Zero keys through fourteen, standing in every region at every rung. The
    # random sweep above covers the middle of that distribution; this covers all
    # of it, including the two ends it would almost never draw.
    ladder_rows = []
    for count in range(len(world.KEYS) + 1):
        cleared = [k["boss"] for k in world.KEYS[:count]]
        opened = set()
        for region in world.REGIONS:
            state = {
                "player": {"level": 1, "xp": 0, "region": region["id"]},
                "skills": {}, "cleared_bosses": list(cleared),
                "quests_completed": [], "pets": [], "dungeons_cleared": [],
                "stats": {}, "unspent_points": 0,
                "story": {"fired": [], "chains": {}},
                "world": new_world_state(),
            }
            advance(state)
            prog = snapshot(state)
            within = reachable(prog)
            opened |= {status["id"] for status in open_routes(prog)}
            if not mortal <= within:
                failures["key_ladder_stranded"].append(
                    (count, region["id"], sorted(mortal - within)))
            if len(things_to_do(state, limit=99)) < 3:
                failures["key_ladder_stranded"].append((count, region["id"], "todo"))
        ladder_rows.append({
            "keys": count,
            "key_roads_open": sum(1 for k in world.KEYS[:count]
                                  if k["opens"] in opened),
            "portal": count >= len(world.KEYS),
        })

    # The curve, in numbers, against the one it deepens.
    curve = []
    for level in (1, 5, 10, 20, 30, 40, 50, 60):
        curve.append({
            "level": level,
            "xp_for_next": xp_needed(level),
            "cumulative": total_xp_for(level),
            "world_py_xp_for_next": int(round(120 * (1.18 ** (level - 1)))),
        })

    passed = all(not rows for rows in failures.values()) \
        and statics["connected_without_hard_gates"] \
        and not statics["orphans"] and not statics["bad_routes"] \
        and not statics["bad_event_routes"] and not statics["bad_event_dungeons"] \
        and not statics["bad_event_bosses"] and not statics["bad_event_regions"] \
        and statics["always_unconditional"] and statics["always_available"] >= 3 \
        and statics["one_key_per_boss"] and not statics["bad_keys"] \
        and not statics["bad_key_bosses"] \
        and not statics["mismatched_key_routes"] \
        and not statics["unclaimed_key_routes"] \
        and not statics["doubled_key_routes"] \
        and not statics["key_only_regions"] \
        and statics["portal_in_first_village"] \
        and statics["portal_needs_every_key"] \
        and statics["portal_never_gates_the_practical"]

    return {
        "trials": trials,
        "passed": passed,
        "statics": statics,
        "regions": len(world.REGIONS),
        "routes": len(ROUTES),
        "hidden_routes": len(HIDDEN_ROUTES),
        "hard_walls": sum(1 for r in ROUTES if r.wall),
        "soft_gates": sum(1 for r in ROUTES if not r.wall and r.need.kind != "none"),
        "always_open": sum(1 for r in ROUTES if r.need.kind == "none"),
        "world_events": len(WORLD_EVENTS),
        "dungeons": len(DUNGEONS),
        "dungeon_floors": sum(d["floors"] for d in DUNGEONS),
        "min_mortal_regions_reachable": min_reach,
        "mortal_regions": len(mortal),
        "min_open_routes": min_routes,
        "min_things_to_do": min_todo,
        "min_candidates": min_candidates,
        "mean_candidates": round(todo_total / max(trials, 1), 2),
        "mean_events_fired": round(events_total / max(trials, 1), 2),
        "castle_open_states": castle_open_states,
        "keys": len(world.KEYS),
        "key_roads": sum(1 for r in ROUTES if r.need.kind == "key"),
        "key_events": sum(1 for e in WORLD_EVENTS if e.need.kind == "key"),
        "keyless_states": keyless_states,
        "keyless_min_mortal_regions_reachable": keyless_min_reach,
        "keyless_min_things_to_do": keyless_min_todo,
        "key_ladder_rungs": len(ladder_rows),
        "key_ladder": ladder_rows,
        "portal_region": PORTAL_REGION,
        "portal_requires": len(world.KEYS),
        "portal_gates": list(world.PORTAL_GATES),
        "portal_never_gates": list(world.PORTAL_NEVER_GATES),
        "failures": {key: len(rows) for key, rows in failures.items()},
        "examples": {key: rows[:3] for key, rows in failures.items() if rows},
        "curve": curve,
        "max_xp_per_level": max(xp_needed(level) for level in range(1, MAX_LEVEL)),
        "xp_to_60": total_xp_for(60),
    }


if __name__ == "__main__":                          # pragma: no cover
    import json

    print(json.dumps(self_check(), indent=2, default=str))
