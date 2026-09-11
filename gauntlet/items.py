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
    source: str = "drop"        # drop | boss | secret | quest | vendor
    skill: str = ""             # thematic tie to a skill, for drop weighting

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
]

BY_ID = {item.id: item for item in CATALOGUE}


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
]

SECRET_BY_ID = {s["id"]: s for s in SECRETS}


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def total_effects(equipped: dict, attributes: dict, temp: dict | None = None) -> dict:
    """Fold equipment, set bonuses, attributes and battle-temporary buffs into one
    effect dict. This is the single source of truth for what a build actually does."""
    out: dict = {}

    def add(key, value):
        if key in ("reveal_category", "probe_reveal_value", "perf_insight",
                   "second_wind", "combo_shield"):
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
    "TUTORIAL": 0.16, "EASY": 0.28, "MEDIUM": 0.46,
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
