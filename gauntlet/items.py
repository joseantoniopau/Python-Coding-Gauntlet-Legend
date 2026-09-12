"""Loot, equipment, sets, attributes and hidden treasures.

The design rule every item obeys: an item may change the *economics* of an
encounter — how much focus a spell costs, how many probes you get, how much
grace the clock gives you, how much XP a clever play pays — but no item may
supply an answer, name a pattern, or survive into Interview Mode.

That constraint is what keeps a genuinely addictive loot loop honest: the power
fantasy is real, and it is still your Python that clears the fight.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

from . import elements, world

# `elements` is the layer ABOVE this one in every sense except the import graph:
# it reads world.REGIONS and it reads nothing here. The dependency runs this way
# round because the elemental gear below is DERIVED from its tables rather than
# copied beside them — eight pairs of boots authored twice would be eight pairs
# of boots that eventually disagree about what they protect you from. There is
# no cycle: elements imports world, and world imports nothing.

# --------------------------------------------------------------------------
# Attributes
# --------------------------------------------------------------------------

ATTRIBUTES = {
    "LOGIC": {
        "label": "Logic",
        "blurb": "Probe charges. Every 2 points grants one more probe per battle — "
                 "and probing is how you turn edge-case reasoning into damage.",
        "colour": "#7ec8ff",
    },
    "FOCUS": {
        "label": "Focus",
        "blurb": "+3 maximum focus per point. Focus pays for learning spells.",
        "colour": "#a89aff",
    },
    "VIGOR": {
        "label": "Vigor",
        "blurb": "+2 maximum stamina per point. More failed casts before Training "
                 "Camp calls you in.",
        "colour": "#8fd07a",
    },
    "INSIGHT": {
        "label": "Insight",
        "blurb": "+4% loot quality per point, and secrets reveal themselves more "
                 "readily.",
        "colour": "#e8c37d",
    },
    "HASTE": {
        "label": "Haste",
        "blurb": "+3% clock grace per point — for RANK only. Correctness is never "
                 "graded on a curve.",
        "colour": "#ff9d4a",
    },
}

POINTS_PER_LEVEL = 3

BUILDS = {
    "ANALYST": {
        "name": "The Analyst",
        "blurb": "Wins by predicting how code breaks. Probes first, writes second.",
        "focus": ["LOGIC", "INSIGHT"],
        "starting": {"LOGIC": 4, "INSIGHT": 3, "FOCUS": 1, "VIGOR": 1, "HASTE": 1},
        "set": "testsmith",
    },
    "DUELIST": {
        "name": "The Duelist",
        "blurb": "Wins on the clock. Fewer hints, faster hands, longer combos.",
        "focus": ["HASTE", "VIGOR"],
        "starting": {"HASTE": 4, "VIGOR": 3, "LOGIC": 1, "FOCUS": 1, "INSIGHT": 1},
        "set": "chronomancer",
    },
    "ARCHIVIST": {
        "name": "The Archivist",
        "blurb": "Wins by knowing. Cheap spells, deep codex, relentless retests.",
        "focus": ["FOCUS", "INSIGHT"],
        "starting": {"FOCUS": 4, "INSIGHT": 3, "LOGIC": 1, "VIGOR": 1, "HASTE": 1},
        "set": "archivist",
    },
}

SLOTS = ["weapon", "offhand", "head", "chest", "hands", "feet",
         "ring1", "ring2", "trinket"]

RARITIES = {
    "COMMON":    {"weight": 100, "colour": "#9b96b8", "mult": 1.0, "label": "Common"},
    "UNCOMMON":  {"weight": 46,  "colour": "#8fd07a", "mult": 1.4, "label": "Uncommon"},
    "RARE":      {"weight": 20,  "colour": "#7ec8ff", "mult": 1.9, "label": "Rare"},
    "EPIC":      {"weight": 7,   "colour": "#c8a8ff", "mult": 2.6, "label": "Epic"},
    "LEGENDARY": {"weight": 2,   "colour": "#e8c37d", "mult": 3.4, "label": "Legendary"},
    "MYTHIC":    {"weight": 0,   "colour": "#ff6a7a", "mult": 4.5, "label": "Mythic"},
}

RARITY_ORDER = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC"]

# --------------------------------------------------------------------------
# Effects vocabulary — every field an item may touch
# --------------------------------------------------------------------------

EFFECT_LABELS = {
    "probe_charges": "+{v} probe charge(s) per battle",
    "mana_max": "+{v} maximum focus",
    "stamina_max": "+{v} maximum stamina",
    "hint_discount": "learning spells cost {p}% less focus",
    "rank_grace": "+{p}% clock grace for rank",
    "crit_bonus": "+{p}% XP when you strike a weakness",
    "loot_luck": "+{p}% loot quality",
    "xp_bonus": "+{p}% XP",
    "retest_bonus": "+{p}% XP on memory ambushes",
    "combo_shield": "your combo survives {v} failure(s)",
    "reveal_category": "probes name the failure category they would trigger",
    "probe_reveal_value": "a failed probe shows the true value",
    "perf_insight": "performance trials report their timing budget",
    "mana_regen": "+{v} focus after every cleared encounter",
    "shrine_bonus": "+{p}% shrine rewards",
    "armor_repair": "+{p}% armour restored per repair",
    "second_wind": "one free re-cast per battle without breaking your combo",

    # -- the elemental layer (gauntlet/elements.py) -------------------------
    # Armour does TWO jobs and the whole point of the system is that the player
    # chooses between them, so they are two keys and never one blended
    # "defence" number. `elements.armour_from_effects` reads exactly these and
    # nothing else, which is why they are spelled the way that module spells
    # them rather than the way this one would have.
    #
    # Points are FLAT and certain; they work against a hit you did not plan
    # for. Resistance is PROPORTIONAL and conditional; it is worth more the
    # bigger the hit and worth nothing against an element you read wrong.
    "armour_points": "-{v} damage from every hit, up to this armour's share of it",
    "armour_cap": "flat armour may stop up to {p}% of any single hit",
    "resist_fire": "-{p}% damage from FIRE",
    "resist_cold": "-{p}% damage from COLD",
    "resist_poison": "-{p}% damage from POISON",
    "resist_brute": "-{p}% damage from BRUTE FORCE",
    "resist_lightning": "-{p}% damage from LIGHTNING",
    "resist_void": "-{p}% damage from VOID",


    # -- character classes and skill trees (gauntlet/classes.py) -------------
    # Each of these names something the engine already measures, or can measure
    # without new instrumentation. They were declared inside classes.py while that
    # module was being reviewed on its own; the effect vocabulary is one dict and
    # this is it, so they live here and classes.py derives its view from here.
    # engine.py renders tooltips from THIS dict, so a key that is not here is a
    # key the player never sees, however carefully its owner declared it.
    "declare_slots": "+{v} pre-write declaration(s) per encounter",
    "declare_bonus": "+{p}% XP when a pre-write declaration proves correct",
    "probe_refund": "a correct probe refunds its charge {p}% of the time",
    "first_try_bonus": "+{p}% XP when you clear on your first submission",
    "iteration_bonus": "+{p}% XP per failed submission that preceded an unaided clear, "
                       "counting at most three",
    "retry_grace": "the first {v} failed submission(s) each encounter cost no stamina",
    "stamina_regen": "+{v} stamina after every cleared encounter",
    "retest_charges": "+{v} memory ambush(es) offered per day",
    "interval_stretch": "memory ambushes schedule {p}% further out, and pay for the "
                        "distance",
    "srs_preview": "the day's memory ambushes are listed before you set out",
    "edge_ward": "each edge case you name before running that turns out to be real "
                 "grants a ward absorbing one failed submission, up to {v}",
    "weakness_scan": "{v} of the enemy's weakness CLASSES are named at the start of the "
                     "fight — the class, never the input and never the answer",
    "bench_slots": "+{v} bench slot(s): helpers you wrote and cleared come back with "
                   "you into later adventure encounters",
    "design_rubric": "+{v} extra rubric point(s) on design answers, each worth XP and "
                     "each requiring an extra argument from you",
    "refactor_bonus": "+{p}% XP for re-clearing a solved encounter with a shorter or "
                      "measurably faster solution",
    "trace_frames": "step your own submitted code {v} frame(s) either side of the point "
                    "it first diverged",
    "root_cause_bonus": "+{p}% XP when you name the failure category before the game "
                        "names it for you",
    "recovery_grace": "+{p}% clock grace for rank on an encounter you already failed "
                      "this session",
    "loot_upgrade": "{v} drop(s) per battle roll one rarity tier higher",
    "gold_bonus": "+{p}% gold",
    "respec_discount": "the Armorer unpicks your tree for {p}% less",
    "rematch_bonus": "+{p}% XP from boss rematches",

    # -- legendary artifacts (gauntlet/legendaries.py) ----------------------
    # A legendary's signature is what a run gets built around, so each of these is
    # a behaviour rather than a percentage. Moved here for the same reason.
    "probe_unbounded": "probes are unlimited, and each one costs {v} focus",
    "probe_first_free": "the first probe of every battle is free and returns {v} cases",
    "boundary_sense": "probes on the first and last element of any input are free and "
                      "unlimited",
    "prereq_sight": "a failure names the prerequisite skill that actually failed, and "
                    "opens the route to it",
    "phase_preview": "a boss phase announces its modifier one phase early",
    "off_map": "dungeon floors reveal one room past the frontier, including the room "
               "that is not on the map",
    "no_clock": "the rank clock does not start until your first keystroke, and runs "
                "double afterwards",
    "rank_floor": "while your combo is intact, rank cannot fall below A",
    "rank_ceiling": "your rank can never exceed {v}",
    "combo_immortal": "your combo never breaks; each failure permanently cuts this "
                      "run's XP rate by {p}%",
    "combo_brittle": "a broken combo cannot be rebuilt for the rest of the session",
    "no_second_attempt": "one failed submission ends the encounter",
    "glass_stamina": "maximum stamina is {v}, and no repair restores it",
    "focus_from_failure": "a failed submission restores {v} focus instead of costing "
                          "stamina",
    "xp_on_failure": "a failed submission still pays {p}% XP, once per problem",
    "armor_eternal": "armour integrity is frozen where it stands: nothing damages it "
                     "and nothing repairs it",
    "hint_surcharge": "learning spells cost {p}% more focus",
    "sealed_hints": "learning spells cannot be cast at all",
    "weakness_chain": "each consecutive weakness strike adds +{p}% XP; a miss resets "
                      "the chain to zero",
    "mastery_spillover": "an unaided clear credits {p}% of its mastery to the weakest "
                         "prerequisite skill",
    "spell_refund": "a learning spell's focus is refunded in full if you then clear "
                    "that problem unaided",
    "memo_bank": "focus spent on a learning spell is banked; the next time that pattern "
                 "appears, the spell is free",
    "retest_storm": "memory ambushes come {v}x as often and pay triple",
    "unlabelled": "problems arrive with pattern, family and difficulty stripped",
    "indexed": "a memory ambush follows every encounter, at full difficulty, paying "
               "{v}x",
    "naming": "after a clutch clear, the next encounter pays double XP and rolls its "
              "loot one rarity higher",
    "loot_double_roll": "every drop rolls twice and you keep both",
    "oblige": "solves the current encounter outright and pays full loot",
    "skill_decay": "permanently removes {v} mastery from the skill it solved",
    "sealed_in_exam": "does nothing whatsoever in Interview Mode",
    "hand_ward": "mastery the Obliging Hand took back regrows at {p}% of an unaided "
                 "clear's gain, and the Hand cannot be worn alongside these",
}


def describe(effects: dict) -> list:
    out = []
    for key, value in effects.items():
        template = EFFECT_LABELS.get(key)
        if not template:
            continue
        out.append(template.format(v=value, p=int(round(value * 100))))
    return out


@dataclass
class Item:
    id: str
    name: str
    slot: str
    rarity: str
    effects: dict = field(default_factory=dict)
    set_id: str = ""
    icon: str = "sword"
    flavour: str = ""
    hidden: bool = False
    source: str = "drop"        # drop | boss | secret | quest | vendor | upgrade
    skill: str = ""             # thematic tie to a skill, for drop weighting
    # The wheel. A weapon's element is what it STRIKES with; armour's is what it
    # is warded against, which is already said numerically in `resist_*` and is
    # repeated here only so the tooltip and the sprite tint have one word to
    # read. "" means neutral, which is most of the catalogue and is a real
    # answer rather than a gap — see elements.NEUTRAL.
    element: str = ""
    # Upgrades are earned, never bought. `upgrades` names what this becomes and
    # `upgrade_requirement` is the evidence that earns it; both are filled in from
    # UPGRADE_PATHS at import, so the whole progression reads as one table rather
    # than as a field scattered across forty item literals.
    upgrades: str = ""
    upgrade_requirement: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["effect_text"] = describe(self.effects)
        d["rarity_colour"] = RARITIES[self.rarity]["colour"]
        return d


# --------------------------------------------------------------------------
# Set bonuses
# --------------------------------------------------------------------------

SETS = {
    "testsmith": {
        "name": "Testsmith Regalia",
        "blurb": "For the player who breaks code before writing it.",
        "bonuses": {
            2: {"probe_charges": 1},
            3: {"reveal_category": 1, "probe_reveal_value": 1},
            5: {"probe_charges": 2, "crit_bonus": 0.5},
        },
    },
    "chronomancer": {
        "name": "Chronomancer's Vestments",
        "blurb": "Time bends for those who have already done the thinking.",
        "bonuses": {
            2: {"rank_grace": 0.2},
            3: {"combo_shield": 1, "xp_bonus": 0.15},
            5: {"rank_grace": 0.45, "second_wind": 1},
        },
    },
    "archivist": {
        "name": "Archivist's Array",
        "blurb": "Every vault opens cheaply when you already know its key.",
        "bonuses": {
            2: {"hint_discount": 0.25},
            3: {"mana_max": 10, "retest_bonus": 0.3},
            5: {"hint_discount": 0.5, "mana_regen": 4},
        },
    },
    "nullbane": {
        "name": "Nullbane Panoply",
        "blurb": "Forged from the fragments the Null King could not shatter.",
        "bonuses": {
            2: {"crit_bonus": 0.3},
            3: {"xp_bonus": 0.25, "loot_luck": 0.2},
            5: {"probe_charges": 2, "second_wind": 1, "xp_bonus": 0.5},
        },
    },

    # ---- chapter sets: one wearable identity per movement of the ladder ----
    # Each answers the chapter it is named for. Vernacular makes the language
    # itself cheap, so chapter I stops costing focus; Pathfinder pays for probing
    # a maze instead of guessing at it; Memoist pays you for never solving the
    # same subproblem twice, which is the entire argument of chapter IX.
    "vernacular": {
        "name": "Vernacular Weave",
        "blurb": "Cloth for someone who has stopped fighting the syntax.",
        "bonuses": {
            2: {"hint_discount": 0.15},
            3: {"mana_regen": 2, "stamina_max": 4},
            5: {"hint_discount": 0.3, "mana_max": 12, "xp_bonus": 0.15},
        },
    },
    "pathfinder": {
        "name": "Pathfinder's Kit",
        "blurb": "Every road on the map was walked by someone carrying this.",
        "bonuses": {
            2: {"probe_charges": 1},
            3: {"crit_bonus": 0.25, "loot_luck": 0.15},
            5: {"probe_charges": 2, "reveal_category": 1, "xp_bonus": 0.25},
        },
    },
    "memoist": {
        "name": "Memoist's Ledger-Mail",
        "blurb": "Each ring is a subproblem, written down once and never again.",
        "bonuses": {
            2: {"retest_bonus": 0.2},
            3: {"mana_regen": 3, "perf_insight": 1},
            5: {"xp_bonus": 0.35, "hint_discount": 0.25, "mana_regen": 5},
        },
    },
}


# --------------------------------------------------------------------------
# The item table
# --------------------------------------------------------------------------

def _i(**kwargs) -> Item:
    return Item(**kwargs)


CATALOGUE: list = [
    # ---- weapons: algorithm mastery made visible ----
    _i(id="hashblade", name="Hashblade", slot="weapon", rarity="UNCOMMON", icon="sword",
       skill="HASH_MAP", effects={"xp_bonus": 0.1, "mana_max": 4},
       flavour="Its edge finds the complement before you have finished the question."),
    _i(id="hashblade_prime", name="Hashblade Prime", slot="weapon", rarity="EPIC",
       icon="sword", skill="HASH_MAP",
       effects={"xp_bonus": 0.25, "mana_max": 8, "probe_charges": 1},
       flavour="Every key it has ever turned is still remembered in the steel."),
    _i(id="twin_sabers", name="Twin Sabers", slot="weapon", rarity="UNCOMMON",
       icon="sabers", skill="TWO_POINTER",
       effects={"rank_grace": 0.1, "crit_bonus": 0.15},
       flavour="Two blades that only ever move toward each other."),
    _i(id="window_staff", name="Window Staff", slot="weapon", rarity="RARE",
       icon="staff", skill="SLIDING_WINDOW",
       effects={"mana_max": 8, "hint_discount": 0.15},
       flavour="The frame it casts widens right and never retreats."),
    _i(id="recursion_spear", name="Recursion Spear", slot="weapon", rarity="RARE",
       icon="spear", skill="RECURSION",
       effects={"xp_bonus": 0.15, "probe_charges": 1},
       flavour="A spear containing a smaller spear, containing a smaller spear."),
    _i(id="queue_lance", name="Queue Lance", slot="weapon", rarity="RARE", icon="lance",
       skill="BFS", effects={"crit_bonus": 0.2, "stamina_max": 3},
       flavour="It strikes in expanding rings. The first ring to land is the shortest."),
    _i(id="depthblade", name="Depthblade", slot="weapon", rarity="RARE", icon="dagger",
       skill="DFS", effects={"crit_bonus": 0.25, "loot_luck": 0.1},
       flavour="It commits to one path entirely, and remembers the way back."),
    _i(id="tree_axe", name="Tree Axe", slot="weapon", rarity="RARE", icon="axe",
       skill="TREE", effects={"xp_bonus": 0.15, "mana_max": 6},
       flavour="Every swing splits exactly twice."),
    _i(id="heap_hammer", name="Heap Hammer", slot="weapon", rarity="RARE", icon="hammer",
       skill="HEAP", effects={"crit_bonus": 0.2, "rank_grace": 0.1},
       flavour="It only ever lifts the heaviest thing in the pile."),
    _i(id="matrix_bow", name="Matrix Bow", slot="weapon", rarity="RARE", icon="bow",
       skill="MATRIX", effects={"probe_charges": 1, "xp_bonus": 0.1},
       flavour="Draw along the row. Loose along the column."),
    _i(id="dynamic_relic", name="Dynamic Relic", slot="weapon", rarity="EPIC",
       icon="relic", skill="DP",
       effects={"xp_bonus": 0.3, "mana_regen": 3, "retest_bonus": 0.2},
       flavour="Everything it has solved once, it never pays for again."),

    # ---- Testsmith set ----
    _i(id="testsmith_monocle", name="Testsmith's Monocle", slot="head", rarity="RARE",
       icon="helm", set_id="testsmith", effects={"probe_charges": 1},
       flavour="Through this lens, the happy path looks suspiciously narrow."),
    _i(id="testsmith_gloves", name="Testsmith's Gloves", slot="hands", rarity="RARE",
       icon="gauntlets", set_id="testsmith", effects={"crit_bonus": 0.2},
       flavour="Made for handling inputs nobody intended."),
    _i(id="testsmith_shield", name="Testsmith's Shield", slot="offhand", rarity="RARE",
       icon="shield", set_id="testsmith", effects={"stamina_max": 4},
       flavour="It has caught every empty list ever thrown."),
    _i(id="testsmith_ring", name="Testsmith's Band", slot="ring1", rarity="EPIC",
       icon="relic", set_id="testsmith", effects={"probe_charges": 1, "loot_luck": 0.1},
       flavour="Turn it once and you think of duplicates. Twice, and negatives."),
    _i(id="testsmith_boots", name="Testsmith's Treads", slot="feet", rarity="RARE",
       icon="boots", set_id="testsmith", effects={"xp_bonus": 0.12},
       flavour="They walk the boundary, never the middle."),

    # ---- Chronomancer set ----
    _i(id="chrono_crown", name="Chronomancer's Circlet", slot="head", rarity="RARE",
       icon="helm", set_id="chronomancer", effects={"rank_grace": 0.12},
       flavour="The clock still runs. It simply runs politely."),
    _i(id="chrono_boots", name="Chronomancer's Striders", slot="feet", rarity="RARE",
       icon="boots", set_id="chronomancer", effects={"rank_grace": 0.12, "xp_bonus": 0.08},
       flavour="Hesitation costs less in these."),
    _i(id="chrono_ring", name="Ring of the Held Hour", slot="ring1", rarity="EPIC",
       icon="relic", set_id="chronomancer", effects={"combo_shield": 1},
       flavour="One mistake does not have to cost the whole run."),
    _i(id="chrono_trinket", name="Hourglass of Second Thought", slot="trinket",
       rarity="EPIC", icon="relic", set_id="chronomancer",
       effects={"second_wind": 1}, flavour="Turn it, and the last cast never happened."),
    _i(id="chrono_chest", name="Chronomancer's Mantle", slot="chest", rarity="RARE",
       icon="chest", set_id="chronomancer", effects={"stamina_max": 4, "rank_grace": 0.1},
       flavour="Woven from the minutes you did not waste."),

    # ---- Archivist set ----
    _i(id="archivist_hood", name="Archivist's Hood", slot="head", rarity="RARE",
       icon="helm", set_id="archivist", effects={"hint_discount": 0.15},
       flavour="Knowledge is cheaper when it is already catalogued."),
    _i(id="archivist_robe", name="Archivist's Robe", slot="chest", rarity="RARE",
       icon="chest", set_id="archivist", effects={"mana_max": 8},
       flavour="Deep pockets, deeper index."),
    _i(id="archivist_ring", name="Band of the Deep Index", slot="ring2", rarity="EPIC",
       icon="relic", set_id="archivist", effects={"retest_bonus": 0.25},
       flavour="It remembers what you learned on a Tuesday three weeks ago."),
    _i(id="archivist_gloves", name="Archivist's Wraps", slot="hands", rarity="UNCOMMON",
       icon="gauntlets", set_id="archivist", effects={"mana_regen": 2},
       flavour="For turning pages without losing your place."),
    _i(id="archivist_trinket", name="Codex Fragment", slot="trinket", rarity="RARE",
       icon="relic", set_id="archivist", effects={"hint_discount": 0.15, "xp_bonus": 0.1},
       flavour="A page torn from something much larger."),

    # ---- Nullbane set: boss drops only ----
    _i(id="nullbane_helm", name="Nullbane Helm", slot="head", rarity="LEGENDARY",
       icon="helm", set_id="nullbane", source="boss",
       effects={"probe_charges": 1, "crit_bonus": 0.2},
       flavour="Shaped from a fragment the Null King could not break."),
    _i(id="nullbane_plate", name="Nullbane Plate", slot="chest", rarity="LEGENDARY",
       icon="plate", set_id="nullbane", source="boss",
       effects={"stamina_max": 6, "combo_shield": 1},
       flavour="It has absorbed a thousand failed casts and lost no shine."),
    _i(id="nullbane_grips", name="Nullbane Grips", slot="hands", rarity="LEGENDARY",
       icon="gauntlets", set_id="nullbane", source="boss",
       effects={"crit_bonus": 0.3, "loot_luck": 0.15},
       flavour="They close around the exact input that breaks a thing."),
    _i(id="nullbane_greaves", name="Nullbane Greaves", slot="feet", rarity="LEGENDARY",
       icon="boots", set_id="nullbane", source="boss",
       effects={"rank_grace": 0.2, "xp_bonus": 0.2},
       flavour="They never take the same wrong path twice."),
    _i(id="nullbane_sigil", name="Nullbane Sigil", slot="trinket", rarity="LEGENDARY",
       icon="relic", set_id="nullbane", source="boss",
       effects={"probe_charges": 1, "mana_max": 10},
       flavour="The Source recognises its own."),

    # ---- standalone notables ----
    _i(id="oracle_amulet", name="Big-O Amulet", slot="trinket", rarity="EPIC",
       icon="relic", skill="BIG_O", effects={"perf_insight": 1, "xp_bonus": 0.15},
       flavour="It hums when your loop is nested and you have not noticed."),
    _i(id="debuggers_lens", name="Debugger's Lens", slot="offhand", rarity="EPIC",
       icon="shield", skill="DEBUGGING",
       effects={"reveal_category": 1, "armor_repair": 0.3},
       flavour="It does not tell you the answer. It tells you where to look."),
    _i(id="shrine_charm", name="Charm of Recall", slot="ring2", rarity="UNCOMMON",
       icon="relic", skill="RECALL", effects={"shrine_bonus": 0.4, "mana_regen": 2},
       flavour="Warm to the touch near a Memory Shrine."),
    _i(id="apprentice_ring", name="Apprentice's Ring", slot="ring1", rarity="COMMON",
       icon="relic", effects={"mana_max": 3},
       flavour="Everyone starts somewhere."),
    _i(id="worn_boots", name="Worn Boots", slot="feet", rarity="COMMON", icon="boots",
       effects={"stamina_max": 2}, flavour="They have walked the Fields many times."),
    _i(id="training_vest", name="Training Vest", slot="chest", rarity="COMMON",
       icon="chest", effects={"stamina_max": 3}, flavour="Padded. Unremarkable. Useful."),
    _i(id="scribes_gloves", name="Scribe's Gloves", slot="hands", rarity="COMMON",
       icon="gauntlets", effects={"xp_bonus": 0.05},
       flavour="For writing the approach down before the code."),
    _i(id="rusty_blade", name="Rusty Blade", slot="weapon", rarity="COMMON", icon="sword",
       effects={"xp_bonus": 0.03},
       flavour="O(n squared), and honest about it."),

    # ---- hidden / secret ----
    _i(id="null_key", name="The Null Key", slot="trinket", rarity="MYTHIC", hidden=True,
       source="secret", effects={"probe_charges": 2, "hint_discount": 0.3,
                                 "loot_luck": 0.3, "xp_bonus": 0.3},
       flavour="Found where the map insists there is nothing. Of course it was there."),
    _i(id="linear_edge", name="The Linear Edge", slot="weapon", rarity="MYTHIC",
       hidden=True, source="secret",
       effects={"crit_bonus": 0.6, "xp_bonus": 0.4, "perf_insight": 1},
       flavour="Awarded to whoever turns a quadratic into a line, knowingly."),
    _i(id="phoenix_feather", name="Phoenix Feather", slot="offhand", rarity="LEGENDARY",
       hidden=True, source="secret",
       effects={"second_wind": 1, "combo_shield": 1, "stamina_max": 5},
       flavour="Failure was never the end of anything."),
    _i(id="mimic_tooth", name="Mimic's Tooth", slot="ring2", rarity="LEGENDARY",
       hidden=True, source="secret",
       effects={"reveal_category": 1, "probe_reveal_value": 1, "crit_bonus": 0.25},
       flavour="Taken from something that looked exactly like correct code."),
    _i(id="architects_seal", name="The Architect's Seal", slot="ring1", rarity="MYTHIC",
       hidden=True, source="secret",
       effects={"mana_max": 15, "stamina_max": 8, "xp_bonus": 0.5, "loot_luck": 0.25},
       flavour="You were always going to be the one to find this."),

    # ---- upgrade tiers: earned forms, never found ----
    # source="upgrade" keeps every one of these out of roll_drop. Finding the
    # Sourceforged Edge in a chest would say the opposite of what it is for: it
    # exists to be the same blade you were handed on the first morning, later.
    _i(id="honed_blade", name="Honed Blade", slot="weapon", rarity="UNCOMMON",
       icon="sword", skill="PYTHON", source="upgrade",
       effects={"xp_bonus": 0.08, "stamina_max": 2},
       flavour="The rust came off. What was underneath had always been straight."),
    _i(id="fluent_edge", name="Fluent Edge", slot="weapon", rarity="RARE",
       icon="sword", skill="PYTHON", source="upgrade",
       effects={"xp_bonus": 0.16, "mana_max": 5, "rank_grace": 0.08},
       flavour="It stopped costing you anything to swing. That was the lesson."),
    _i(id="clarion_edge", name="Clarion Edge", slot="weapon", rarity="EPIC",
       icon="sword", skill="COMMUNICATION", source="upgrade",
       effects={"xp_bonus": 0.28, "mana_max": 8, "hint_discount": 0.15},
       flavour="Named for the habit of saying the plan aloud before the first cut."),
    _i(id="sourceforged_edge", name="Sourceforged Edge", slot="weapon",
       rarity="LEGENDARY", icon="sword", skill="RECALL", source="upgrade",
       effects={"xp_bonus": 0.4, "mana_max": 12, "probe_charges": 1,
                "crit_bonus": 0.25},
       flavour="Reforged from a rusty blade. Same steel. Entirely different owner."),
    _i(id="hashblade_eternal", name="Hashblade Eternal", slot="weapon",
       rarity="LEGENDARY", icon="sword", skill="HASH_MAP", source="upgrade",
       effects={"xp_bonus": 0.35, "mana_max": 12, "probe_charges": 1,
                "retest_bonus": 0.3},
       flavour="It stopped needing to look. It simply knows which vault."),
    _i(id="converging_sabers", name="Converging Sabers", slot="weapon", rarity="RARE",
       icon="sabers", skill="TWO_POINTER", source="upgrade",
       effects={"rank_grace": 0.16, "crit_bonus": 0.25},
       flavour="They no longer have to be aimed. They only have to be released."),
    _i(id="narrowing_sabers", name="Sabers of the Narrowing Pass", slot="weapon",
       rarity="EPIC", icon="sabers", skill="TWO_POINTER", source="upgrade",
       effects={"rank_grace": 0.24, "crit_bonus": 0.4, "combo_shield": 1},
       flavour="The gap between them is the only part of the problem still open."),
    _i(id="held_frame_staff", name="Staff of the Held Frame", slot="weapon",
       rarity="EPIC", icon="staff", skill="SLIDING_WINDOW", source="upgrade",
       effects={"mana_max": 12, "hint_discount": 0.25, "combo_shield": 1},
       flavour="The frame breaks, shrinks from the left, and the scan never restarts."),
    _i(id="smaller_call_spear", name="Spear of the Smaller Call", slot="weapon",
       rarity="EPIC", icon="spear", skill="RECURSION", source="upgrade",
       effects={"xp_bonus": 0.28, "probe_charges": 1, "mana_regen": 3},
       flavour="You stopped checking whether the stack would unwind. It unwinds."),
    _i(id="expanding_rings_lance", name="Lance of Expanding Rings", slot="weapon",
       rarity="EPIC", icon="lance", skill="BFS", source="upgrade",
       effects={"crit_bonus": 0.35, "stamina_max": 5, "probe_charges": 1},
       flavour="Marked when queued, not when reached. The distinction cost you a boss."),
    _i(id="abyssal_depthblade", name="Abyssal Depthblade", slot="weapon", rarity="EPIC",
       icon="dagger", skill="DFS", source="upgrade",
       effects={"crit_bonus": 0.4, "loot_luck": 0.2, "xp_bonus": 0.15},
       flavour="It goes all the way down and still remembers every door it passed."),
    _i(id="split_canopy_axe", name="Axe of the Split Canopy", slot="weapon",
       rarity="EPIC", icon="axe", skill="TREE", source="upgrade",
       effects={"xp_bonus": 0.28, "mana_max": 10, "crit_bonus": 0.2},
       flavour="A node with one child is not a leaf. The Ent made sure you knew."),
    _i(id="kth_weight_hammer", name="Hammer of the Kth Weight", slot="weapon",
       rarity="EPIC", icon="hammer", skill="HEAP", source="upgrade",
       effects={"crit_bonus": 0.32, "rank_grace": 0.18, "perf_insight": 1},
       flavour="It never sorts the pile. It only ever asks the pile one question."),
    _i(id="turned_floor_bow", name="Bow of the Turned Floor", slot="weapon",
       rarity="EPIC", icon="bow", skill="MATRIX", source="upgrade",
       effects={"probe_charges": 1, "xp_bonus": 0.22, "crit_bonus": 0.2},
       flavour="Transpose, then reverse each row. The Golem hates this bow."),
    _i(id="paid_once_relic", name="Relic of the Debt Paid Once", slot="weapon",
       rarity="LEGENDARY", icon="relic", skill="DP", source="upgrade",
       effects={"xp_bonus": 0.45, "mana_regen": 5, "retest_bonus": 0.35},
       flavour="Every tile it has lit stays lit, including the ones you forgot."),
    _i(id="read_failure_lens", name="Lens of the Read Failure", slot="offhand",
       rarity="LEGENDARY", icon="shield", skill="DEBUGGING", source="upgrade",
       effects={"reveal_category": 1, "armor_repair": 0.5, "stamina_max": 5},
       flavour="Still refuses to say the fix. It has only got better at pointing."),
    _i(id="journeyman_ring", name="Journeyman's Ring", slot="ring1", rarity="UNCOMMON",
       icon="relic", source="upgrade", effects={"mana_max": 6, "mana_regen": 1},
       flavour="Everyone starts somewhere. Very few stay there."),
    _i(id="adepts_ring", name="Adept's Ring", slot="ring1", rarity="RARE",
       icon="relic", source="upgrade",
       effects={"mana_max": 10, "mana_regen": 2, "hint_discount": 0.1},
       flavour="The band has worn thin where you turn it while thinking."),

    # ---- Vernacular Weave: chapter I, the language itself ----
    _i(id="vernacular_hood", name="Vernacular Hood", slot="head", rarity="RARE",
       icon="helm", set_id="vernacular", skill="PYTHON",
       effects={"hint_discount": 0.12},
       flavour="Asking costs less when you can already name what you are asking about."),
    _i(id="vernacular_tunic", name="Vernacular Tunic", slot="chest", rarity="RARE",
       icon="chest", set_id="vernacular", skill="PYTHON", effects={"mana_max": 6},
       flavour="Plain weave. Nothing here is showing off, and nothing here is slow."),
    _i(id="vernacular_wraps", name="Vernacular Wraps", slot="hands", rarity="UNCOMMON",
       icon="gauntlets", set_id="vernacular", skill="PYTHON",
       effects={"mana_regen": 2},
       flavour="Wound for people who type the whole line before they think about it."),
    _i(id="vernacular_sandals", name="Vernacular Sandals", slot="feet",
       rarity="UNCOMMON", icon="boots", set_id="vernacular", skill="PYTHON",
       effects={"stamina_max": 3},
       flavour="Village-made. They have never once been anywhere difficult."),
    _i(id="vernacular_charm", name="Charm of Plain Speech", slot="trinket",
       rarity="RARE", icon="relic", set_id="vernacular", skill="COMMUNICATION",
       effects={"xp_bonus": 0.1},
       flavour="Say the structure, then the loop. It is warm when you do."),

    # ---- Pathfinder's Kit: chapter VIII, maps and mazes ----
    _i(id="pathfinder_cowl", name="Pathfinder's Cowl", slot="head", rarity="RARE",
       icon="helm", set_id="pathfinder", skill="GRAPH",
       effects={"probe_charges": 1},
       flavour="Hood up, count the neighbours, then move. In that order."),
    _i(id="pathfinder_coat", name="Pathfinder's Coat", slot="chest", rarity="RARE",
       icon="chest", set_id="pathfinder", skill="GRAPH",
       effects={"stamina_max": 5},
       flavour="Long enough for the Wastes, short enough for the canopy."),
    _i(id="pathfinder_grips", name="Pathfinder's Grips", slot="hands", rarity="RARE",
       icon="gauntlets", set_id="pathfinder", skill="BFS",
       effects={"crit_bonus": 0.18},
       flavour="For holding a frontier and a visited set at the same time."),
    _i(id="pathfinder_boots", name="Pathfinder's Boots", slot="feet", rarity="RARE",
       icon="boots", set_id="pathfinder", skill="DFS",
       effects={"rank_grace": 0.1, "xp_bonus": 0.08},
       flavour="They have walked a cycle exactly once and then refused to again."),
    _i(id="pathfinder_compass", name="Pathfinder's Compass", slot="trinket",
       rarity="EPIC", icon="relic", set_id="pathfinder", skill="GRAPH",
       effects={"loot_luck": 0.15, "probe_charges": 1},
       flavour="It does not point north. It points at the edge you have not tried."),

    # ---- Memoist's Ledger-Mail: chapter IX, paying once ----
    _i(id="memoist_visor", name="Memoist's Visor", slot="head", rarity="RARE",
       icon="helm", set_id="memoist", skill="DP", effects={"mana_max": 8},
       flavour="Ruled in faint lines, like a table nobody has filled in yet."),
    _i(id="memoist_mail", name="Memoist's Ledger-Mail", slot="chest", rarity="EPIC",
       icon="plate", set_id="memoist", skill="DP",
       effects={"stamina_max": 5, "mana_regen": 2},
       flavour="Each ring is a subproblem. None of them is written twice."),
    _i(id="memoist_cuffs", name="Memoist's Cuffs", slot="hands", rarity="RARE",
       icon="gauntlets", set_id="memoist", skill="RECALL",
       effects={"retest_bonus": 0.15},
       flavour="Stiff from being consulted. That is not the same as being read."),
    _i(id="memoist_treads", name="Memoist's Treads", slot="feet", rarity="RARE",
       icon="boots", set_id="memoist", skill="DP", effects={"xp_bonus": 0.12},
       flavour="The Ruins light up under them. You have walked this tile before."),
    _i(id="memoist_ledger", name="The Standing Ledger", slot="trinket", rarity="EPIC",
       icon="relic", set_id="memoist", skill="DP",
       effects={"retest_bonus": 0.2, "mana_regen": 2},
       flavour="A debt recorded once is a debt never paid twice."),

    # ---- hidden: the second tier of secrets ----
    _i(id="interviewers_coin", name="The Interviewer's Coin", slot="ring1",
       rarity="MYTHIC", hidden=True, source="secret",
       effects={"xp_bonus": 0.45, "rank_grace": 0.25, "retest_bonus": 0.35,
                "loot_luck": 0.2},
       flavour="Handed over without comment at the end of a run with no scratches."),
    _i(id="thirty_day_signet", name="Signet of the Thirtieth Day", slot="ring2",
       rarity="LEGENDARY", hidden=True, source="secret",
       effects={"retest_bonus": 0.5, "mana_max": 10, "xp_bonus": 0.2},
       flavour="A month of silence, and the pattern was still where you left it."),
    _i(id="silent_crown", name="The Silent Crown", slot="head", rarity="MYTHIC",
       hidden=True, source="secret",
       effects={"mana_max": 18, "hint_discount": 0.4, "xp_bonus": 0.35,
                "crit_bonus": 0.25},
       flavour="An entire chapter, and not one spell cast. Nobody was watching."),
    _i(id="armorers_last_plate", name="The Armorer's Last Plate", slot="chest",
       rarity="LEGENDARY", hidden=True, source="secret",
       effects={"stamina_max": 10, "armor_repair": 0.6, "combo_shield": 1},
       flavour="She keeps one on the wall unfinished. You finished it for her."),
    _i(id="asymptote_shard", name="Shard of the Unreachable Floor", slot="trinket",
       rarity="MYTHIC", hidden=True, source="secret",
       effects={"perf_insight": 1, "xp_bonus": 0.4, "mana_regen": 4,
                "rank_grace": 0.2},
       flavour="The top floor cannot be brute-forced. You did not brute-force it."),
    _i(id="rematch_spurs", name="Spurs of the Second Meeting", slot="feet",
       rarity="LEGENDARY", hidden=True, source="secret",
       effects={"rank_grace": 0.35, "crit_bonus": 0.3, "xp_bonus": 0.2},
       flavour="It took an hour the first time. It took a verse of a song the second."),
    _i(id="forgekeepers_grips", name="Forgekeeper's Grips", slot="hands",
       rarity="LEGENDARY", hidden=True, source="secret",
       effects={"probe_charges": 2, "reveal_category": 1, "crit_bonus": 0.3},
       flavour="Three forges, no survivors. The Testsmith wrote the date down."),
    _i(id="quicksilver_edge", name="The Quicksilver Edge", slot="weapon",
       rarity="MYTHIC", icon="sabers", hidden=True, source="secret",
       effects={"rank_grace": 0.4, "crit_bonus": 0.5, "xp_bonus": 0.35,
                "second_wind": 1},
       flavour="Half the budget, whole answer. The clock is still checking its work."),
]

# --------------------------------------------------------------------------
# The elemental layer, as objects you can actually hold
# --------------------------------------------------------------------------
#
# elements.py describes three roads and offers a choice between them. A choice
# nobody can equip is a diagram, so this section puts all three in the
# catalogue, DERIVED from that module's own tables:
#
#   PLATE   flat armour points, capped at half of any hit. Certainty.
#   WARDED  one element, heavily, and nothing against the other five. Leverage.
#   CLOAK   no mitigation at all, a longer bar instead. The road that buys the
#           most typing, which is the road this game would like you to take.
#
# and boots, which are not defence at all: they are elements.BOOTS, verbatim,
# because the overworld asks `elements.hazard_step(region, equipped["feet"])`
# and that function looks the id up in elements.BOOTS_BY_ID. Authoring them
# twice would be authoring two answers to "do these keep the ember out".
#
# Numbers scale with rarity rather than being free-handed per item, so a rarer
# piece is measurably stronger and the loot ladder stays honest.

# Points by rarity. Deliberately modest against base damage in the high single
# digits: elements.resolve_damage caps flat absorption at a fraction of the hit
# anyway, so a big number here would not do what it appears to promise.
_PLATE_POINTS = {"COMMON": 1, "UNCOMMON": 2, "RARE": 3, "EPIC": 4,
                 "LEGENDARY": 6, "MYTHIC": 7}
# Resistance by rarity, clamped by elements.PIECE_RESIST_CAP on the way in.
_WARD_RESIST = {"COMMON": 0.06, "UNCOMMON": 0.10, "RARE": 0.15, "EPIC": 0.20,
                "LEGENDARY": 0.26, "MYTHIC": 0.30}
# What rarity buys on the CLOAK road, which has no mitigation to scale. Added on
# top of the archetype's own bars rather than replacing them, so an epic cloak is
# a longer epic cloak and not a different garment. Without this every cloak in
# the game would be identical whatever it cost, and a road where rarity buys
# nothing is a road nobody walks twice.
_BAR_BONUS = {"COMMON": 0, "UNCOMMON": 0, "RARE": 2, "EPIC": 4,
              "LEGENDARY": 6, "MYTHIC": 8}


def armour_effects(kind: str, rarity: str, element: str = "") -> dict:
    """The effect bag for one piece of armour of a given archetype and rarity.

    Runs the numbers through `elements.armour_profile`, which clamps them, and
    reads the result back out into effect keys. Going through that function
    rather than round the side of it means a piece can never be authored past a
    cap the damage function is going to ignore anyway.

    RARITY SCALES A ROAD; IT DOES NOT MOVE YOU ONTO A BETTER ONE. Only PLATE and
    MAIL scale their points, because points are what those two are FOR. A warded
    piece keeps the single token point its archetype declares and a cloak keeps
    none, however rare either gets. Letting a rare ward carry a rare plate's
    points would make it plate-with-resistance-attached, and the moment one road
    is a superset of another the player has no decision left to make — which is
    the decision elements.py wrote three archetypes to offer.
    """
    scaled = kind in ("PLATE", "MAIL")
    bars = _BAR_BONUS.get(rarity, 0) if kind == "CLOAK" else 0
    profile = elements.armour_profile(
        kind, points=_PLATE_POINTS.get(rarity, 1) if scaled else None,
        element=element, resist=_WARD_RESIST.get(rarity, 0.0) if element else 0.0,
        bonus_health=bars, bonus_focus=bars)
    out: dict = {}
    if profile.points:
        out["armour_points"] = profile.points
        out["armour_cap"] = round(profile.points_cap, 2)
    for eid, value in profile.resist.items():
        out[f"resist_{eid.lower()}"] = round(value, 2)
    if profile.bonus_health:
        out[elements.HEALTH_EFFECT_KEY] = profile.bonus_health
    if profile.bonus_focus:
        out[elements.FOCUS_EFFECT_KEY] = profile.bonus_focus
    return out


_WARD_FLAVOUR = {
    "FIRE": "Quenched once, in something that was not water.",
    "COLD": "It never frosts over. Nothing on it ever has.",
    "POISON": "Waxed at every seam. The smell is the point.",
    "BRUTE": "Thicker where a shoulder goes through a wall.",
    "LIGHTNING": "Wired to a tail that drags. Leave it dragging.",
    "VOID": "You keep finding it by touch.",
}

_WARDED_SLOT = {"FIRE": "chest", "COLD": "chest", "POISON": "head",
                "BRUTE": "offhand", "LIGHTNING": "head", "VOID": "offhand"}
_WARDED_ICON = {"chest": "chest", "head": "helm", "offhand": "shield"}
_WARDED_NAME = {"FIRE": "Cinderward Hauberk", "COLD": "Rimeward Hauberk",
                "POISON": "Sporeward Mask", "BRUTE": "Stoneward Buckler",
                "LIGHTNING": "Earthward Coif", "VOID": "Lampward Pavise"}


def _elemental_gear() -> list:
    """Six warded pieces, three cloaks, three plates and the seven boots.

    Built rather than typed. The six wards are one per element because the
    whole argument of a warded piece is that it answers ONE area and shrugs at
    the rest; five of them would leave an element with no answer, and the
    player would read that as the wheel being uneven rather than as an omission.
    """
    made: list = []

    # -- warded: one element, heavily -------------------------------------
    for eid in elements.ELEMENT_IDS:
        slot = _WARDED_SLOT[eid]
        made.append(_i(
            id=f"ward_{eid.lower()}", name=_WARDED_NAME[eid], slot=slot,
            rarity="RARE", icon=_WARDED_ICON[slot], element=eid,
            effects=armour_effects("WARDED", "RARE", eid),
            flavour=_WARD_FLAVOUR[eid]))

    # -- plate: flat points, and the only kind whose points still count when
    #    something large lands
    made.append(_i(id="field_plate", name="Field Plate", slot="chest",
                   rarity="UNCOMMON", icon="plate",
                   effects=armour_effects("PLATE", "UNCOMMON"),
                   flavour="Heavy, unsubtle, and it does not care what hit you."))
    made.append(_i(id="warden_helm", name="Warden's Helm", slot="head",
                   rarity="RARE", icon="helm",
                   effects=armour_effects("PLATE", "RARE"),
                   flavour="Dented in one place, from something it stopped."))
    made.append(_i(id="bulwark_of_the_long_fight", name="Bulwark of the Long Fight",
                   slot="offhand", rarity="EPIC", icon="shield",
                   effects=armour_effects("PLATE", "EPIC"),
                   flavour="Every mark on it is a fight that went to twenty turns."))

    # -- cloaks and helms: no mitigation, a longer bar. The brief's third road,
    #    and the strictly best one for a player who is here to type.
    made.append(_i(id="wanderers_cloak", name="Wanderer's Cloak", slot="chest",
                   rarity="UNCOMMON", icon="chest",
                   effects=armour_effects("CLOAK", "UNCOMMON"),
                   flavour="It stops nothing. You simply last longer in it."))
    made.append(_i(id="long_study_hood", name="Hood of the Long Study", slot="head",
                   rarity="RARE", icon="helm",
                   effects=armour_effects("CLOAK", "RARE"),
                   flavour="Cut so the light falls on the page and not on you."))
    made.append(_i(id="mantle_of_the_tenth_turn", name="Mantle of the Tenth Turn",
                   slot="trinket", rarity="EPIC", icon="relic",
                   effects=armour_effects("CLOAK", "EPIC"),
                   flavour="Nobody has ever been killed by a fight lasting too long."))

    # -- boots: elements.BOOTS, as items. The id is the contract — hazard_step
    #    looks the equipped `feet` id up in elements.BOOTS_BY_ID, so a boot
    #    whose item id drifted from its Boots id would be a boot that protects
    #    against nothing and says otherwise on the tooltip.
    existing = {item.id for item in CATALOGUE}
    for boot in elements.BOOTS:
        if boot.id in existing:
            continue                      # worn_boots is already in the catalogue
        effects: dict = {}
        if boot.bonus_health:
            effects[elements.HEALTH_EFFECT_KEY] = boot.bonus_health
        if boot.bonus_focus:
            effects[elements.FOCUS_EFFECT_KEY] = boot.bonus_focus
        if not effects:
            # Marching Boots and Wayfarer's are the only pair with nothing but
            # speed, and an item with an empty effect bag renders as a blank
            # tooltip. The speed is real; it is just not an effect key, because
            # the overworld reads it off elements.BOOTS and not off this dict.
            effects[elements.HEALTH_EFFECT_KEY] = 1
        rarity = ("RARE" if len(boot.immunities) > 1
                  else "UNCOMMON" if boot.immunities else "COMMON")
        made.append(_i(id=boot.id, name=boot.name, slot="feet", rarity=rarity,
                       icon="boots", element=boot.element,
                       effects=effects, flavour=boot.blurb))
    return made


# -- what a weapon strikes with ---------------------------------------------
#
# Derived, not authored. Every weapon in the catalogue already declares the
# SKILL it belongs to, and world.REGIONS already says which region teaches that
# skill, and elements.AFFINITY already says what that region is made of. So a
# Hashblade strikes with LIGHTNING because the Hashmap Highlands are a plateau
# in a storm, and nobody had to decide that twice.
#
# A weapon with no skill — the Rusty Blade, the Quicksilver Edge — stays
# neutral, which is the right answer for a weapon that belongs to nowhere.

_REGION_FOR_SKILL = {}
for _region in world.REGIONS:
    _REGION_FOR_SKILL.setdefault(_region["skill"], _region["id"])
del _region

for _item in CATALOGUE:
    if _item.slot == "weapon" and not _item.element and _item.skill:
        _found = elements.affinity_for(_REGION_FOR_SKILL.get(_item.skill, ""))
        # Left EMPTY rather than stamped NEUTRAL. They are the same thing to the
        # damage function, but an empty field lets `strike_element` fall through
        # to the companion, and a blade from a region with no weather ought to
        # take the colour of whatever is walking beside you.
        if _found in elements.ELEMENTS:
            _item.element = _found
del _item, _found

CATALOGUE.extend(_elemental_gear())


def strike_element(equipped: dict | None, *, fallback: str = "") -> str:
    """What the player's blow is made of.

    The weapon decides, because the weapon is the thing that lands. `fallback`
    is the caller's second opinion — engine.py passes the active companion's
    element, since a companion is the other thing standing next to you and
    elements.PET_ELEMENT exists precisely to answer that — and NEUTRAL is the
    honest last word rather than an exception.

    Deliberately NOT summed or blended across slots. Two elements at once would
    mean never being wrong about the room, and reading the room is the decision.
    """
    weapon = (equipped or {}).get("weapon", "")
    item = BY_ID.get(weapon)
    if item is not None and item.element in elements.ELEMENTS:
        return item.element
    return fallback if fallback in elements.ELEMENTS else elements.NEUTRAL


def boots_id(equipped: dict | None) -> str:
    """The equipped boots, as an id elements.hazard_step will recognise."""
    feet = (equipped or {}).get("feet", "")
    return feet if feet in elements.BOOTS_BY_ID else ""


def armour_view(effects: dict | None) -> dict:
    """The defensive half of a loadout, rendered. One place, so the equipment
    screen, the battle HUD and the smith's comparison cannot disagree."""
    profile = elements.armour_from_effects(effects or {})
    return {
        "points": profile.points,
        "points_cap": round(profile.points_cap, 2),
        "resist": {eid: round(v, 3) for eid, v in profile.resist.items()},
        "bonus_health": profile.bonus_health,
        "bonus_focus": profile.bonus_focus,
        "text": describe({k: v for k, v in (effects or {}).items()
                          if k in ("armour_points", "armour_cap")
                          or k.startswith("resist_")}),
    }



# --------------------------------------------------------------------------
# The apex trophies — seventeen, one per roaming hunter
# --------------------------------------------------------------------------
#
# `hunters.TROPHIES` is a MANIFEST, not an implementation: hunters.py does not
# own this file, so it wrote down seventeen rows built only out of slots,
# rarities and `EFFECT_LABELS` keys that already exist here, and said that
# whoever wired the drop should transcribe them. This is that transcription,
# and `trophy_manifest_matches()` below is the thing that catches a drift
# rather than a comment claiming there will not be one.
#
# `hidden=True` and `source="boss"` together keep them out of the ordinary loot
# tables. An apex trophy is paid by `hunters.bounty()` and by nothing else — a
# sideways-best-in-slot that fell out of a random chest would stop being the
# receipt for a fight you were not supposed to win the first time.
#
# They are deliberately SIDEWAYS: best in the game at exactly one thing and
# mediocre at everything else, so wearing one is a decision about which area you
# are walking into rather than an upgrade you never take off.

APEX_TROPHY_IDS: tuple = (
    "surveyors_rod", "hooked_tine", "ungrounded_key", "rearranged_quill",
    "index_zero_plate", "unclosed_corner", "frozen_wick", "topmost_plate",
    "seam_rivet", "unwound_frame", "left_fork_claw", "lit_tine",
    "prised_tile", "unsalvaged_plate", "eighth_bar", "hour_through_glass",
    "struck_label",
)

CATALOGUE.extend([
    _i(id='surveyors_rod', name="The Surveyor's Rod", slot='trinket', rarity='RARE',
       element='', source="boss", icon="trophy", hidden=True,
       effects={"mana_max": 4, "hint_discount": 0.1},
       flavour="Four hinges. It measures what is still there."),   # python_village
    _i(id='hooked_tine', name="Hooked Tine", slot='trinket', rarity='RARE',
       element='', source="boss", icon="trophy", hidden=True,
       effects={"stamina_max": 5},
       flavour="Off the drum. It is still turning slightly."),   # fields_of_syntax
    _i(id='ungrounded_key', name="The Ungrounded Key", slot='ring1', rarity='EPIC',
       element='LIGHTNING', source="boss", icon="trophy", hidden=True,
       effects={"resist_lightning": 0.28, "mana_max": 3},
       flavour="It opens nothing. It was never for a door."),   # hashmap_highlands
    _i(id='rearranged_quill', name="Rearranged Quill", slot='trinket', rarity='EPIC',
       element='POISON', source="boss", icon="trophy", hidden=True,
       effects={"resist_poison": 0.28, "stamina_max": 4},
       flavour="The letters on it are not the letters it had."),   # stringwood_labyrinth
    _i(id='index_zero_plate', name="The Index-Zero Plate", slot='offhand', rarity='EPIC',
       element='BRUTE', source="boss", icon="trophy", hidden=True,
       effects={"armour_points": 5, "armour_cap": 0.5},
       flavour="Cut deep, and cut first."),   # array_caverns
    _i(id='unclosed_corner', name="An Unclosed Corner", slot='trinket', rarity='EPIC',
       element='POISON', source="boss", icon="trophy", hidden=True,
       effects={"resist_poison": 0.24, "resist_cold": 0.18},
       flavour="One of four. The other three are still out there."),   # sliding_window_marsh
    _i(id='frozen_wick', name="The Frozen Wick", slot='head', rarity='EPIC',
       element='COLD', source="boss", icon="trophy", hidden=True,
       effects={"resist_cold": 0.3, "stamina_max": 4},
       flavour="Lit. Not burning. It has not decided to stop."),   # twin_pointer_pass
    _i(id='topmost_plate', name="The Topmost Plate", slot='chest', rarity='EPIC',
       element='FIRE', source="boss", icon="trophy", hidden=True,
       effects={"resist_fire": 0.3, "armour_points": 3},
       flavour="Unloaded from the top, which is the only way."),   # stack_queue_mines
    _i(id='seam_rivet', name="The Seam Rivet", slot='ring2', rarity='EPIC',
       element='BRUTE', source="boss", icon="trophy", hidden=True,
       effects={"resist_brute": 0.28, "armour_points": 2},
       flavour="It has been four directions and holds none."),   # matrix_citadel
    _i(id='unwound_frame', name="The Unwound Frame", slot='trinket', rarity='LEGENDARY',
       element='VOID', source="boss", icon="trophy", hidden=True,
       effects={"resist_void": 0.3, "mana_max": 5},
       flavour="The innermost one. It never got to return."),   # recursive_forest
    _i(id='left_fork_claw', name="The Left-Fork Claw", slot='ring1', rarity='EPIC',
       element='', source="boss", icon="trophy", hidden=True,
       effects={"crit_bonus": 0.12, "stamina_max": 4},
       flavour="It committed a long time ago."),   # binary_tree_canopy
    _i(id='lit_tine', name="The Lit Tine", slot='head', rarity='LEGENDARY',
       element='LIGHTNING', source="boss", icon="trophy", hidden=True,
       effects={"resist_lightning": 0.3, "loot_luck": 0.1},
       flavour="A route, snapped off. It still knows the way."),   # graph_wastes
    _i(id='prised_tile', name="A Prised Tile", slot='offhand', rarity='LEGENDARY',
       element='', source="boss", icon="trophy", hidden=True,
       effects={"armour_points": 6, "mana_max": 4},
       flavour="Still lit. It should not be, off the floor."),   # dp_ruins
    _i(id='unsalvaged_plate', name="Unsalvaged Plate", slot='chest', rarity='LEGENDARY',
       element='FIRE', source="boss", icon="trophy", hidden=True,
       effects={"resist_fire": 0.3, "armour_points": 4},
       flavour="One hairline. The hairline is the useful part."),   # debugging_dungeon
    _i(id='eighth_bar', name="The Eighth Bar", slot='offhand', rarity='LEGENDARY',
       element='COLD', source="boss", icon="trophy", hidden=True,
       effects={"resist_cold": 0.28, "armour_points": 4},
       flavour="The eighth is a problem. The ninth is somebody else's."),   # complexity_tower
    _i(id='hour_through_glass', name="The Hour Through Glass", slot='trinket', rarity='LEGENDARY',
       element='', source="boss", icon="trophy", hidden=True,
       effects={"rank_grace": 0.15, "stamina_max": 5},
       flavour="Fused sand. You can read the time through it."),   # coding_coliseum
    _i(id='struck_label', name="The Struck Label", slot='chest', rarity='MYTHIC',
       element='VOID', source="boss", icon="trophy", hidden=True,
       effects={"resist_void": 0.3, "resist_cold": 0.2, "armour_points": 5, "stamina_max": 5},
       flavour="It does not do anything at all. That is the tell."),   # null_kings_castle
])


def trophy_manifest_matches() -> list:
    """Every place this transcription could have drifted from hunters.py.

    Late import, because `items` cannot import `hunters` at module scope:
    hunters imports forge and forge imports this file. Returns a list of
    problems, empty when the two agree.
    """
    try:
        from . import hunters as _hunters
    except Exception as exc:                      # pragma: no cover
        return ["hunters did not import: %s" % exc]
    problems = []
    manifest = getattr(_hunters, "TROPHIES", {})
    if set(manifest) != set(APEX_TROPHY_IDS):
        problems.append("trophy ids differ: %s" % sorted(
            set(manifest) ^ set(APEX_TROPHY_IDS)))
    for tid, row in manifest.items():
        here = BY_ID.get(tid)
        if here is None:
            problems.append("%s is in the manifest and not in the catalogue" % tid)
            continue
        for field in ("slot", "rarity", "element"):
            if getattr(here, field) != row[field]:
                problems.append("%s.%s: manifest %r, catalogue %r"
                                % (tid, field, row[field], getattr(here, field)))
        if dict(here.effects) != dict(row["effects"]):
            problems.append("%s effects drifted" % tid)
    return problems

BY_ID = {item.id: item for item in CATALOGUE}


# --------------------------------------------------------------------------
# Upgrade tiers — gear that improves because you did, not because you paid
# --------------------------------------------------------------------------
#
# There is no forge, no vendor and no currency here on purpose. A blade that can
# be bought says the money was the achievement. Every rung below is unlocked by
# the same evidence the ramp already trusts: mastery, unaided clears, retention,
# speed. The player's starting Rusty Blade walks the spine at the top of the
# table — honed, fluent, clarion, sourceforged — so a single object records the
# whole playthrough, and the weapon on the sprite is a readable progress bar.
#
# A requirement is {"text": <one sentence>, "needs": [<clause>, ...]} where a
# clause is either a skill bar:
#     {"skill": "HASH_MAP", "mastery": 60, "unaided": 6}
# or a lifetime counter from the run's stats dict:
#     {"stat": "armor_repairs", "at_least": 10}
# Clauses are conjunctive. Nothing here reads the corpus, so no requirement can
# ever be satisfied by anything but graded evidence.

UPGRADE_METRICS = {
    "mastery":   ("mastery", "mastery"),
    "unaided":   ("unaided_clears", "unaided clears"),
    "clears":    ("clears", "clears"),
    "retention": ("retention", "retention"),
    "speed":     ("speed", "speed"),
}

UPGRADE_PATHS = {
    # the spine: one blade, five forms, the length of a playthrough
    "rusty_blade": {
        "to": "honed_blade",
        "requirement": {
            "text": "Clear three encounters in Python with no spells cast.",
            "needs": [{"skill": "PYTHON", "mastery": 25, "unaided": 3}],
        }},
    "honed_blade": {
        "to": "fluent_edge",
        "requirement": {
            "text": "Reach real fluency: Python mastery 45 and eight unaided clears.",
            "needs": [{"skill": "PYTHON", "mastery": 45, "unaided": 8}],
        }},
    "fluent_edge": {
        "to": "clarion_edge",
        "requirement": {
            "text": "Say the approach as well as you write it — Python 62, "
                    "Communication 40.",
            "needs": [{"skill": "PYTHON", "mastery": 62},
                      {"skill": "COMMUNICATION", "mastery": 40}],
        }},
    "clarion_edge": {
        "to": "sourceforged_edge",
        "requirement": {
            "text": "Recall it cold in the unlabelled rooms: Recall 60 with "
                    "retention to match.",
            "needs": [{"skill": "RECALL", "mastery": 60, "retention": 55},
                      {"skill": "PYTHON", "mastery": 70}],
        }},

    # branch lines: each weapon answers to the skill it was named for
    "hashblade": {
        "to": "hashblade_prime",
        "requirement": {
            "text": "Hash-map mastery 60 across six unaided clears.",
            "needs": [{"skill": "HASH_MAP", "mastery": 60, "unaided": 6}],
        }},
    "hashblade_prime": {
        "to": "hashblade_eternal",
        "requirement": {
            "text": "Hash-map mastery 80, and it survives the delayed retests.",
            "needs": [{"skill": "HASH_MAP", "mastery": 80, "retention": 65}],
        }},
    "twin_sabers": {
        "to": "converging_sabers",
        "requirement": {
            "text": "Two-pointer mastery 50 with four unaided clears.",
            "needs": [{"skill": "TWO_POINTER", "mastery": 50, "unaided": 4}],
        }},
    "converging_sabers": {
        "to": "narrowing_sabers",
        "requirement": {
            "text": "Two-pointer mastery 70 across eight unaided clears.",
            "needs": [{"skill": "TWO_POINTER", "mastery": 70, "unaided": 8}],
        }},
    "window_staff": {
        "to": "held_frame_staff",
        "requirement": {
            "text": "Sliding-window mastery 60 with five unaided clears.",
            "needs": [{"skill": "SLIDING_WINDOW", "mastery": 60, "unaided": 5}],
        }},
    "recursion_spear": {
        "to": "smaller_call_spear",
        "requirement": {
            "text": "Recursion mastery 60 with five unaided clears.",
            "needs": [{"skill": "RECURSION", "mastery": 60, "unaided": 5}],
        }},
    "queue_lance": {
        "to": "expanding_rings_lance",
        "requirement": {
            "text": "Breadth-first mastery 60, and a graph you can read.",
            "needs": [{"skill": "BFS", "mastery": 60, "unaided": 5},
                      {"skill": "GRAPH", "mastery": 40}],
        }},
    "depthblade": {
        "to": "abyssal_depthblade",
        "requirement": {
            "text": "Depth-first mastery 60 with five unaided clears.",
            "needs": [{"skill": "DFS", "mastery": 60, "unaided": 5}],
        }},
    "tree_axe": {
        "to": "split_canopy_axe",
        "requirement": {
            "text": "Tree mastery 62 with six unaided clears.",
            "needs": [{"skill": "TREE", "mastery": 62, "unaided": 6}],
        }},
    "heap_hammer": {
        "to": "kth_weight_hammer",
        "requirement": {
            "text": "Heap mastery 58, and the cost stated before you are asked.",
            "needs": [{"skill": "HEAP", "mastery": 58, "unaided": 4},
                      {"skill": "BIG_O", "mastery": 45}],
        }},
    "matrix_bow": {
        "to": "turned_floor_bow",
        "requirement": {
            "text": "Matrix mastery 58 with four unaided clears.",
            "needs": [{"skill": "MATRIX", "mastery": 58, "unaided": 4}],
        }},
    "dynamic_relic": {
        "to": "paid_once_relic",
        "requirement": {
            "text": "Dynamic-programming mastery 70 that survives a retest.",
            "needs": [{"skill": "DP", "mastery": 70, "retention": 60}],
        }},

    # off the weapon line, because progression should be visible everywhere
    "debuggers_lens": {
        "to": "read_failure_lens",
        "requirement": {
            "text": "Debugging mastery 65, and ten programs actually repaired.",
            "needs": [{"skill": "DEBUGGING", "mastery": 65},
                      {"stat": "armor_repairs", "at_least": 10}],
        }},
    "apprentice_ring": {
        "to": "journeyman_ring",
        "requirement": {
            "text": "Any twelve clears at all. Turning up is the requirement.",
            "needs": [{"skill": "PYTHON", "clears": 12}],
        }},
    "journeyman_ring": {
        "to": "adepts_ring",
        "requirement": {
            "text": "Python mastery 55, and recall that holds without the map.",
            "needs": [{"skill": "PYTHON", "mastery": 55},
                      {"skill": "RECALL", "mastery": 35}],
        }},
}

# Fill the Item fields from the table, so `item.upgrades` works everywhere an
# Item is already passed around and to_dict() carries it to the client for free.
for _from_id, _path in UPGRADE_PATHS.items():
    _source = BY_ID.get(_from_id)
    if _source is not None:
        _source.upgrades = _path["to"]
        _source.upgrade_requirement = _path["requirement"]


def _clause_checks(clause: dict, skills: dict, stats: dict) -> list:
    """One row per bar in a clause, phrased for a progress bar."""
    rows = []
    if "stat" in clause:
        have = float((stats or {}).get(clause["stat"], 0) or 0)
        need = float(clause.get("at_least", 1))
        rows.append({"label": clause["stat"].replace("_", " "),
                     "have": round(have, 1), "need": need, "met": have >= need})
        return rows
    name = clause.get("skill", "")
    data = (skills or {}).get(name) or {}
    for key, (field_name, label) in UPGRADE_METRICS.items():
        if key not in clause:
            continue
        have = float(data.get(field_name, 0) or 0)
        need = float(clause[key])
        rows.append({"label": f"{name} {label}", "have": round(have, 1),
                     "need": need, "met": have >= need})
    return rows


def upgrade_progress(item_id: str, skills: dict | None = None,
                     stats: dict | None = None) -> dict | None:
    """What this item becomes, and how close the evidence is. None if it is
    already at the end of its line."""
    source = BY_ID.get(item_id)
    if source is None or not source.upgrades:
        return None
    target = BY_ID.get(source.upgrades)
    if target is None:
        return None
    requirement = source.upgrade_requirement or {}
    checks = []
    for clause in requirement.get("needs", []):
        checks.extend(_clause_checks(clause, skills or {}, stats or {}))
    return {
        "from": source.id,
        "from_name": source.name,
        "to": target.id,
        "to_name": target.name,
        "rarity": target.rarity,
        "text": requirement.get("text", ""),
        "requirement": requirement,
        "checks": checks,
        "met": all(row["met"] for row in checks) if checks else False,
        "item": target.to_dict(),
    }


def upgrade_available(item_id: str, skills: dict | None = None,
                      stats: dict | None = None) -> dict | None:
    """The upgrade this item has EARNED, or None.

    Pure: it reads the skill table and the run's counters and returns a
    description. Granting it is the caller's business, which keeps the rule that
    mastery moves only on graded evidence in exactly one place.
    """
    progress = upgrade_progress(item_id, skills, stats)
    if progress is None or not progress["met"]:
        return None
    return progress


def upgrades_for(inventory, skills: dict | None = None,
                 stats: dict | None = None) -> list:
    """Every earned upgrade across an inventory, for the one notification the
    player should get when they walk back into town."""
    out = []
    for item_id in inventory or []:
        found = upgrade_available(item_id, skills, stats)
        if found:
            out.append(found)
    return out


def upgrade_chain(item_id: str) -> list:
    """The whole line this item belongs to, from where it stands onward. Used by
    the codex to show a Rusty Blade what it is going to be."""
    chain = [item_id]
    seen = {item_id}
    current = BY_ID.get(item_id)
    while current is not None and current.upgrades and current.upgrades not in seen:
        chain.append(current.upgrades)
        seen.add(current.upgrades)
        current = BY_ID.get(current.upgrades)
    return chain


# --------------------------------------------------------------------------
# Consumables
# --------------------------------------------------------------------------

CONSUMABLES = {
    "probe_scroll": {
        "name": "Scroll of Probing", "rarity": "UNCOMMON", "icon": "relic",
        "blurb": "Grants one extra probe charge in the current battle.",
        "effect": {"probe_charges": 1},
    },
    "focus_elixir": {
        "name": "Elixir of Focus", "rarity": "COMMON", "icon": "relic",
        "blurb": "Restores 12 focus.",
        "effect": {"mana": 12},
    },
    "stamina_draught": {
        "name": "Draught of Vigour", "rarity": "COMMON", "icon": "relic",
        "blurb": "Restores 6 stamina.",
        "effect": {"stamina": 6},
    },
    "whetstone": {
        "name": "Chronal Whetstone", "rarity": "RARE", "icon": "relic",
        "blurb": "+40% clock grace for this battle's rank. Correctness is unaffected.",
        "effect": {"rank_grace": 0.4},
    },
    "insight_tonic": {
        "name": "Tonic of Insight", "rarity": "RARE", "icon": "relic",
        "blurb": "The next loot roll is upgraded one rarity tier.",
        "effect": {"loot_upgrade": 1},
    },
    "combo_ward": {
        "name": "Ward of Continuity", "rarity": "RARE", "icon": "shield",
        "blurb": "Your combo survives your next failure.",
        "effect": {"combo_shield": 1},
    },
}


# --------------------------------------------------------------------------
# Secrets — hidden content with real discovery conditions
# --------------------------------------------------------------------------

SECRETS = [
    {"id": "secret_linear", "item": "linear_edge",
     "name": "The Optimiser's Revelation",
     "hint": "Somewhere, someone solved a problem the slow way and then solved it "
             "again, properly, without being told to.",
     "condition": "Fail a problem on performance alone, then clear that same problem."},
    {"id": "secret_null_key", "item": "null_key",
     "name": "The Key That Was Not There",
     "hint": "A wall in the Graph Wastes rings hollow on the far eastern edge.",
     "condition": "Find the hidden alcove in the Graph Wastes."},
    {"id": "secret_phoenix", "item": "phoenix_feather",
     "name": "Risen",
     "hint": "Some fights are won on the fourth attempt.",
     "condition": "Clear a problem you had previously failed three times."},
    {"id": "secret_mimic", "item": "mimic_tooth",
     "name": "Every Mimic Dies",
     "hint": "A suite that kills everything it was given.",
     "condition": "Kill every Mimic in a Test Forge on your first submission."},
    {"id": "secret_seal", "item": "architects_seal",
     "name": "The Architect's Seal",
     "hint": "Strike three weaknesses in a row without missing.",
     "condition": "Land three critical weakness strikes consecutively."},

    # The second tier. Every condition below is a thing a player does rather than
    # a thing a player grinds, and no two are satisfied by the same behaviour —
    # one rewards silence, one rewards a month of absence, one rewards walking
    # into a wall in the right tower. `trigger` names the hook the engine should
    # dispatch on; the five above it predate the key and are matched by id in
    # Game._check_secrets.
    {"id": "secret_flawless_run", "item": "interviewers_coin",
     "trigger": "interview_finished",
     "name": "No Scratches",
     "hint": "Somebody, somewhere, finished a whole interview without a single "
             "failed submission. Nobody clapped.",
     "condition": "Complete an Interview Mode run solving every problem with no "
                  "failed submission."},
    {"id": "secret_long_memory", "item": "thirty_day_signet",
     "trigger": "retest_cleared",
     "name": "The Thirtieth Day",
     "hint": "A month of silence is the only honest test of whether you learned it.",
     "condition": "Clear a disguised retest of a pattern you last saw thirty or "
                  "more days ago."},
    {"id": "secret_silent_chapter", "item": "silent_crown",
     "trigger": "chapter_graduated",
     "name": "The Silent Chapter",
     "hint": "There is a crown for the player who never once asked.",
     "condition": "Graduate a chapter without casting a single learning spell."},
    {"id": "secret_full_repair", "item": "armorers_last_plate",
     "trigger": "armor_repaired",
     "name": "The Armorer's Last Plate",
     "hint": "She keeps one unfinished plate on the wall. She is waiting to see "
             "whether anyone finishes the other six first.",
     "condition": "Restore every armour piece to full in a single session."},
    {"id": "secret_tower_alcove", "item": "asymptote_shard",
     "trigger": "location",
     "name": "The Unreachable Floor",
     "hint": "The top floor of the Complexity Tower cannot be reached by brute "
             "force. The stair on the north wall disagrees.",
     "condition": "Find the hidden alcove on the top floor of the Complexity Tower."},
    {"id": "secret_rematch", "item": "rematch_spurs",
     "trigger": "boss_cleared",
     "name": "The Second Meeting",
     "hint": "The first time it took an hour. There is a prize for how long it "
             "takes the second time.",
     "condition": "Beat a boss on a rematch in less than half the time your first "
                  "win took."},
    {"id": "secret_forge_streak", "item": "forgekeepers_grips",
     "trigger": "forge_cleared",
     "name": "Three Forges, No Survivors",
     "hint": "Killing every Mimic once is luck. The Testsmith counts to three.",
     "condition": "Kill every Mimic on the first submission in three consecutive "
                  "Test Forges."},
    {"id": "secret_half_clock", "item": "quicksilver_edge",
     "trigger": "encounter_cleared",
     "name": "Half The Budget",
     "hint": "The clock is still checking its arithmetic.",
     "condition": "Solve a Medium unaided in under half its target time."},
]

SECRET_BY_ID = {s["id"]: s for s in SECRETS}


# --------------------------------------------------------------------------
# Visible progression — what the hero actually looks like
# --------------------------------------------------------------------------
#
# Numbers in a menu are not progression the player can feel. These tables say
# what each armour piece LOOKS like at each repair tier, in the exact vocabulary
# web/js/sprites.js already understands: heroFrame() takes {cloak, tunic, skin,
# hair, boot, trim, metal, weapon} and ramps every colour itself, so a tier only
# has to name the base colours it changes.
#
# Piece ids mirror world.ARMOR (helmet, chestplate, gauntlets, boots, shield,
# legendary). Mirrored rather than imported: this module has no package imports
# and gains nothing by acquiring one.
#
# Tiers are ordered and "at" is the integrity floor, so armor_tier() takes the
# last tier whose floor the piece has reached. Cracked armour should look
# cracked — the Debugging Dungeon is the only way to get the shine back, which
# is the point of the whole repair loop.

ARMOR_TIERS = {
    "helmet": (
        {"at": 0,   "name": "Split Helm", "metal": "#4a4450", "trim": "#3c3846",
         "look": "a hairline crack from brow to crest, and no crest left"},
        {"at": 25,  "name": "Bound Helm", "metal": "#6b6470", "trim": "#7a6a4a",
         "look": "wire-bound over the break, functional and ugly"},
        {"at": 50,  "name": "Patched Helm", "metal": "#8a8494", "trim": "#a08a52",
         "look": "the seam still shows, but it holds under a full swing"},
        {"at": 75,  "name": "Sound Helm", "metal": "#b0aabd", "trim": "#c9a05a",
         "look": "clean lines, a short crest, no visible repair"},
        {"at": 100, "name": "Mirrorbright Helm", "metal": "#e2dcf0", "trim": "#e8c37d",
         "look": "a full crest and a polish that throws the torchlight back"},
    ),
    "chestplate": (
        {"at": 0,   "name": "Staved Plate", "tunic": "#4e4258", "metal": "#4a4450",
         "look": "a caved panel over the ribs, lacing where a buckle used to be"},
        {"at": 25,  "name": "Lashed Plate", "tunic": "#5d5068", "metal": "#6b6470",
         "look": "leather cord across the dent, holding it roughly in shape"},
        {"at": 50,  "name": "Beaten Plate", "tunic": "#6e5f7d", "metal": "#8a8494",
         "look": "hammered back out, the panel proud of the others"},
        {"at": 75,  "name": "Fitted Plate", "tunic": "#7d6b90", "metal": "#b0aabd",
         "look": "every panel flush, the buckles matched"},
        {"at": 100, "name": "Sunplate", "tunic": "#9a7fd0", "metal": "#e2dcf0",
         "look": "a chased sunburst across the chest, unmarked"},
    ),
    "gauntlets": (
        {"at": 0,   "name": "Bare Wraps", "metal": "#5a4f46",
         "look": "cloth wraps where the plates were"},
        {"at": 25,  "name": "Half Gauntlets", "metal": "#75675a",
         "look": "knuckle plates only, the fingers left open"},
        {"at": 50,  "name": "Riveted Gauntlets", "metal": "#96887a",
         "look": "articulated to the second knuckle"},
        {"at": 75,  "name": "Fitted Gauntlets", "metal": "#b8a893",
         "look": "full articulation, no rattle"},
        {"at": 100, "name": "Keysmith's Gauntlets", "metal": "#e6d2ae",
         "look": "fine-jointed, a vault-key motif etched across the back"},
    ),
    "boots": (
        {"at": 0,   "name": "Split Boots", "boot": "#3e3228",
         "look": "the sole parting from the upper at the toe"},
        {"at": 25,  "name": "Bound Boots", "boot": "#4e3f31",
         "look": "wrapped at the ankle to keep them together"},
        {"at": 50,  "name": "Resoled Boots", "boot": "#5f4c3a",
         "look": "new sole, old upper, honest about it"},
        {"at": 75,  "name": "Marching Boots", "boot": "#715b45",
         "look": "greaved at the shin, cut for long roads"},
        {"at": 100, "name": "Wayfarer's Boots", "boot": "#8c7050",
         "look": "greaved and trimmed, quiet on stone"},
    ),
    "shield": (
        {"at": 0,   "name": "Broken Boss", "metal": "#4a4450", "trim": "#3c3846",
         "look": "the boss punched through, the rim bent back"},
        {"at": 25,  "name": "Braced Shield", "metal": "#6b6470", "trim": "#5a4f38",
         "look": "a cross-brace nailed over the hole"},
        {"at": 50,  "name": "Faced Shield", "metal": "#8a8494", "trim": "#7f6a44",
         "look": "refaced, the old hole a pale disc under the paint"},
        {"at": 75,  "name": "Rimmed Shield", "metal": "#b0aabd", "trim": "#a08a52",
         "look": "a whole rim and a true boss"},
        {"at": 100, "name": "Testsmith's Aegis", "metal": "#e2dcf0", "trim": "#e8c37d",
         "look": "every edge case that ever struck it, filed out and forgotten"},
    ),
    "legendary": (
        {"at": 0,   "name": "Empty Stand", "cloak": "#2f2a3c", "metal": "#4a4450",
         "trim": "#3c3846",
         "look": "not worn: it hangs on the Armorer's wall, unfinished"},
        {"at": 25,  "name": "Half-Forged", "cloak": "#39304a", "metal": "#6b6470",
         "trim": "#5a4f38",
         "look": "one shoulder complete, the other still raw stock"},
        {"at": 50,  "name": "Quenched", "cloak": "#443a5c", "metal": "#8a8494",
         "trim": "#7f6a44",
         "look": "both shoulders set, the cloak newly dyed"},
        {"at": 75,  "name": "Fitted", "cloak": "#52456e", "metal": "#b0aabd",
         "trim": "#a08a52",
         "look": "it fits. It did not fit when you started."},
        {"at": 100, "name": "Sourceforged Panoply", "cloak": "#6a4fb0",
         "metal": "#e2dcf0", "trim": "#e8c37d",
         "look": "a full cloak, gold at every seam, and the Source's mark at "
                 "the collar"},
    ),
    # The weapon slot is never repaired, only upgraded, so its tiers step with
    # rarity instead of integrity. "key" is the sprite to draw and every value is
    # one of HERO_WEAPON_KEYS below, which mirrors web/js/sprites.js exactly —
    # the frontend looks the sprite up by that literal string and silently falls
    # back to 'sword' on a miss, which would quietly undo the whole point.
    "weapon": (
        {"at": 0, "name": "Rusted", "key": "sword", "metal": "#7a6f5a",
         "trim": "#4a4236", "look": "pitted edge, no shine, honest about its cost"},
        {"at": 1, "name": "Honed", "key": "sword", "metal": "#9a9384",
         "trim": "#6a5f46", "look": "the rust ground off, the edge true"},
        {"at": 2, "name": "Tempered", "key": "sword", "metal": "#b8b6c4",
         "trim": "#8a7a52", "look": "a blued temper line up the spine"},
        {"at": 3, "name": "Runed", "key": "sword", "metal": "#cfd2e8",
         "trim": "#a89aff", "look": "runework along the fuller, lit from inside"},
        {"at": 4, "name": "Legendary", "key": "sword", "metal": "#eadfae",
         "trim": "#e8c37d", "look": "gold at the guard, and a light that does not "
                                    "come from the room"},
        {"at": 5, "name": "Mythic", "key": "sword", "metal": "#ffd9df",
         "trim": "#ff6a7a", "look": "it hums at a pitch the Null King recognises"},
    ),
}

# Mirrors HERO_WEAPON_KEYS in web/js/sprites.js. Every weapon icon in CATALOGUE
# and every "key" in ARMOR_TIERS["weapon"] must be in here, or the hero draws
# holding the wrong thing.
HERO_WEAPON_KEYS = ("sword", "sabers", "dagger", "axe", "hammer", "spear",
                    "lance", "staff", "bow", "relic")


def armor_tier(piece: str, integrity: float) -> dict:
    """The tier a piece is currently showing. Unknown pieces report nothing
    rather than raising: the sprite layer must never be the thing that crashes."""
    tiers = ARMOR_TIERS.get(piece)
    if not tiers:
        return {}
    current = tiers[0]
    for tier in tiers:
        if integrity >= tier["at"]:
            current = tier
    return {"piece": piece, **current}


def hero_weapon_key(item_id: str) -> str:
    """The sprites.js key for an equipped weapon, validated. A weapon whose icon
    is not a real hero weapon key falls back to the starting sword."""
    item = BY_ID.get(item_id)
    if item is not None and item.icon in HERO_WEAPON_KEYS:
        return item.icon
    return "sword"


def weapon_look(item_id: str) -> dict:
    """Sprite key plus the metal and trim colours for an equipped weapon, keyed
    off its rarity — so an upgrade is visible on the sprite the moment it lands."""
    item = BY_ID.get(item_id)
    rung = RARITY_ORDER.index(item.rarity) if item is not None else 0
    tier = ARMOR_TIERS["weapon"][min(rung, len(ARMOR_TIERS["weapon"]) - 1)]
    return {"key": hero_weapon_key(item_id), "name": tier["name"],
            "look": tier["look"], "metal": tier["metal"], "trim": tier["trim"]}


def hero_look(armor: dict | None = None, equipped: dict | None = None) -> dict:
    """One dict of sprite options, ready to hand to heroFrame() in sprites.js.

    Armour is applied worst-piece-first so the Legendary Plate, which is the last
    thing anyone finishes, overrides the rest of the kit when it is whole.
    """
    out: dict = {}
    order = ["boots", "gauntlets", "shield", "helmet", "chestplate", "legendary"]
    for piece in order:
        integrity = (armor or {}).get(piece, 0)
        # The Legendary Plate at zero is not damaged, it is unbuilt — it is still
        # on the Armorer's wall. Letting it paint the hero would dress the player
        # in armour they have not earned yet.
        if piece == "legendary" and integrity <= 0:
            continue
        tier = armor_tier(piece, integrity)
        for key in ("cloak", "tunic", "boot", "trim", "metal"):
            if key in tier:
                out[key] = tier[key]
    weapon_id = (equipped or {}).get("weapon", "")
    weapon = weapon_look(weapon_id) if weapon_id else weapon_look("rusty_blade")
    out["weapon"] = weapon["key"]
    out["metal"] = weapon["metal"]          # the blade sets the metal ramp
    out["_weapon"] = weapon
    out["_pieces"] = [armor_tier(p, (armor or {}).get(p, 0)) for p in order]
    return out


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

# Keys that are a capability rather than a quantity: two sources of one do not
# make it twice as true, so they take the maximum instead of the sum. Named here
# rather than inlined because `classes.MAXED_KEYS` has to agree with this list,
# and a switch that silently accumulates renders as "sealed_hints: 2".
SWITCH_KEYS = frozenset({
    "reveal_category", "probe_reveal_value", "perf_insight", "second_wind",
    "combo_shield", "srs_preview",
    # Requested by forge.WIRING §1, and granted here rather than in a second
    # list. A learning spell's focus is refunded in full or it is not; two
    # sources of that do not refund it twice. forge.SWITCH_REQUESTS is the
    # literal that asked for it and it is now empty, which is how that module
    # proves the request was granted exactly once.
    "spell_refund",
    # legendary signatures, which are conditions rather than amounts
    "sealed_hints", "no_second_attempt", "armor_eternal", "combo_brittle",
    "combo_immortal", "no_clock", "rank_floor", "probe_unbounded",
    # Not a switch in the yes/no sense, but summing it is nonsense in exactly
    # the same way: `armour_cap` is "the best points_cap you are wearing", so
    # two pieces of plate cap at plate's fraction and not at twice it. Summing
    # it would let four mail pieces out-cap plate, which inverts the one
    # decision the armour system exists to offer. elements.ARMOUR_POINT_CAP is
    # the hard ceiling underneath either way.
    "armour_cap",
    "boundary_sense", "prereq_sight", "phase_preview", "off_map",
    "unlabelled", "oblige", "sealed_in_exam",
    # An absolute, not an amount: "maximum stamina IS {v}". Summing two of them
    # is meaningless; the max is the survivable reading and is what
    # legendaries.WIRING §1 asked for.
    "glass_stamina",
})

# `rank_ceiling` ("your rank can never exceed {v}") is the one effect whose
# combining rule is a design decision rather than an obvious one: two ceilings
# should plausibly take the STRICTER of the two, which is neither the sum nor
# the max. No artifact currently stacks it with another, so it is left out of
# SWITCH_KEYS deliberately rather than by omission — whoever wires a second
# source of it picks the rule then.


def total_effects(equipped: dict, attributes: dict, temp: dict | None = None) -> dict:
    """Fold equipment, set bonuses, attributes and battle-temporary buffs into one
    effect dict. This is the single source of truth for what a build actually does."""
    out: dict = {}

    def add(key, value):
        if key in SWITCH_KEYS:
            out[key] = max(out.get(key, 0), value)
        else:
            out[key] = out.get(key, 0) + value

    counts: dict = {}
    for slot, item_id in (equipped or {}).items():
        item = BY_ID.get(item_id)
        if not item:
            continue
        for key, value in item.effects.items():
            add(key, value)
        if item.set_id:
            counts[item.set_id] = counts.get(item.set_id, 0) + 1

    active_sets = []
    for set_id, count in counts.items():
        spec = SETS.get(set_id)
        if not spec:
            continue
        for threshold in sorted(spec["bonuses"]):
            if count >= threshold:
                for key, value in spec["bonuses"][threshold].items():
                    add(key, value)
                active_sets.append({"id": set_id, "name": spec["name"],
                                    "pieces": count, "threshold": threshold})

    attrs = attributes or {}
    add("probe_charges", attrs.get("LOGIC", 0) // 2)
    add("mana_max", attrs.get("FOCUS", 0) * 3)
    add("stamina_max", attrs.get("VIGOR", 0) * 2)
    add("loot_luck", attrs.get("INSIGHT", 0) * 0.04)
    add("rank_grace", attrs.get("HASTE", 0) * 0.03)

    for key, value in (temp or {}).items():
        add(key, value)

    out["_sets"] = active_sets
    return out


def base_probe_charges(effects: dict) -> int:
    return 1 + int(effects.get("probe_charges", 0))


# --------------------------------------------------------------------------
# Drops
# --------------------------------------------------------------------------

DIFFICULTY_DROP_CHANCE = {
    "GUIDED": 0.1, "TUTORIAL": 0.16, "EASY": 0.28, "MEDIUM": 0.46,
    "HARD": 0.66, "ELITE": 0.8, "BOSS": 1.0,
}

RANK_BONUS = {"S": 0.24, "A": 0.14, "B": 0.06, "C": 0.0, "LEARNING_CLEAR": -0.1}


def roll_drop(*, difficulty: str, rank: str, luck: float, is_boss: bool,
              skill: str = "", owned: set | None = None,
              rng: random.Random | None = None,
              upgrade: int = 0, critical: bool = False) -> dict | None:
    """Return a dropped item (or a consumable, or nothing).

    Luck raises rarity, never the answer. Bosses always drop something, because
    a boss you finally beat should hand you a trophy you can wear."""
    rng = rng or random.Random()
    owned = owned or set()

    chance = DIFFICULTY_DROP_CHANCE.get(difficulty, 0.25)
    chance += RANK_BONUS.get(rank, 0.0) + luck * 0.5
    if critical:
        chance += 0.18
    if not is_boss and rng.random() > min(0.95, chance):
        return None

    # rarity roll, weighted, with luck shifting the curve upward
    pool = []
    for name in RARITY_ORDER[:-1]:          # MYTHIC is secret-only
        weight = RARITIES[name]["weight"]
        tier = RARITY_ORDER.index(name)
        weight *= (1.0 + luck * tier * 0.9)
        if is_boss and tier >= 2:
            weight *= 3.0
        pool.append((name, weight))
    total = sum(w for _, w in pool)
    pick = rng.random() * total
    rarity = pool[0][0]
    for name, weight in pool:
        pick -= weight
        if pick <= 0:
            rarity = name
            break

    for _ in range(max(0, upgrade)):
        i = RARITY_ORDER.index(rarity)
        rarity = RARITY_ORDER[min(i + 1, len(RARITY_ORDER) - 2)]

    if is_boss:
        i = RARITY_ORDER.index(rarity)
        rarity = RARITY_ORDER[max(i, 2)]        # bosses never drop Common/Uncommon

    candidates = [it for it in CATALOGUE
                  if it.rarity == rarity and not it.hidden
                  and it.source != "upgrade"     # earned forms are never found
                  and (it.source != "boss" or is_boss)]
    if skill:
        themed = [it for it in candidates if it.skill == skill]
        if themed and rng.random() < 0.55:
            candidates = themed
    fresh = [it for it in candidates if it.id not in owned]
    if fresh:
        candidates = fresh
    if not candidates:
        # nothing new at this rarity: hand over a useful consumable instead
        key = rng.choice(list(CONSUMABLES))
        return {"kind": "consumable", "id": key, **CONSUMABLES[key]}

    item = rng.choice(candidates)
    return {"kind": "item", **item.to_dict()}


def consumable_drop(rng: random.Random | None = None, luck: float = 0.0) -> dict:
    rng = rng or random.Random()
    keys = list(CONSUMABLES)
    weights = [3 if CONSUMABLES[k]["rarity"] == "COMMON" else
               2 if CONSUMABLES[k]["rarity"] == "UNCOMMON" else 1 + luck * 2
               for k in keys]
    total = sum(weights)
    pick = rng.random() * total
    for key, weight in zip(keys, weights):
        pick -= weight
        if pick <= 0:
            return {"kind": "consumable", "id": key, **CONSUMABLES[key]}
    return {"kind": "consumable", "id": keys[0], **CONSUMABLES[keys[0]]}
