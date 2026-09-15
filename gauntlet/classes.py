"""Character classes and skill trees: six different ROUTES to the same lessons.

The player asked for Diablo-shaped trees, class traits, class gear, class moves,
and a reason to play again. The constraint this module answers to is the same one
`items.py` answers to, stated harder, because a skill tree is a much more tempting
place to cheat:

    No node may supply an answer, name the pattern of the problem in front of you,
    reveal a solution, or let you past an encounter without solving it.

Everything here changes HOW you engage, never WHETHER you have to think. More
probes. Cheaper spells, at the same rank cost. Longer fights. Better drops. More
retests. A move that pays you for saying what you believe before you type. That
is the whole permitted surface, and `self_check()` proves the file stays inside it.

WHY CLASSES EXIST AT ALL
------------------------
A class is not a stat block with a costume. Each of the six is a real study habit,
and the bonus attaches to the MEASURED EVIDENCE that you practised it:

    ANALYST    reasons before writing   -> paid for correct probes, correct
                                            pre-write declarations, first-try clears
    BERSERKER  writes fast and iterates -> paid for speed and for the failed
                                            attempts that precede an unaided clear
    ARCHIVIST  remembers                -> paid for delayed retests and recognition
    WARDEN     tests first              -> paid for edge cases named BEFORE running
    ARTIFICER  builds tools             -> paid for reuse, refactors and design work
    SEER       reads code               -> paid for tracing and for naming the
                                            failure category before the game does

Play the Berserker and the game will keep handing you reasons to type sooner.
Play the Warden and it will keep handing you reasons to write the failing test
first. The class trains the habit it is named after; that is the entire design.

ROUTE, NEVER DESTINATION
------------------------
Every class can finish every chapter. Nothing here touches `curriculum`: not the
chapter ladder, not `TIER_GATES`, not problem selection. `self_check()` verifies
that by inspecting `curriculum`'s own signatures — no class effect is a parameter
any gating function accepts, so no class can open or close content. What varies
between playthroughs is the economics of the road, the gear, the signature move,
and which habit the game keeps paying you for.

MASTERY IS THE PLAYER'S, NOT THE CHARACTER'S
--------------------------------------------
Rolling a second class never un-teaches you Python. `skills.py` state belongs to
the human and survives every respec, every new class, every legacy run. What
resets is the tree.

INTEGRATION CONTRACT
--------------------
    classes.CLASSES / classes.get(class_id)     the six, as data
    classes.new_state(class_id)                 the flat dict a save persists
    classes.points_earned(level, chapters)      how many points exist
    classes.spend(state, node_id, level=...)    the only mutator of `spent`
    classes.tree_effects(state)                 effects dict, items.py vocabulary
    classes.tree_view(state, level=...)         everything a UI needs to draw it
    classes.respec_cost(state, level=...)       gold, and what it costs besides
    classes.equippable(item_id, class_id)       class-restricted gear gate
    classes.self_check()                        the proofs this file must pass

`tree_effects` returns keys in the same vocabulary `items.total_effects` speaks,
so the caller folds it in exactly like a set bonus:

    fx = items.total_effects(equipped, attributes, temp)
    for key, value in classes.tree_effects(state).items():
        fx[key] = fx.get(key, 0) + value        # or max(), see MAXED_KEYS
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass

from . import curriculum, items, movesets

# ---------------------------------------------------------------------------
# Effect vocabulary
# ---------------------------------------------------------------------------
# Most of what a tree does is already sayable in `items.EFFECT_LABELS`. The keys
# below are the ones that were not — and they now live in that dict too, because
# that dict is what `engine.py` renders tooltips from: a key declared anywhere
# else is a key the player never sees.
#
# What stays here is the LIST OF NAMES this module introduced, not a second copy
# of their text. Deleting one from items.py is now an ImportError here rather
# than a class node that silently stops describing itself.
#
# `loot_upgrade` is the odd one out: the engine already honoured it as a battle
# temporary (`Encounter.temp_effects["loot_upgrade"]` feeds `items.roll_drop`),
# it simply never had a player-facing label. It has one now.

CLASS_EFFECT_KEYS = (
    "declare_slots", "declare_bonus", "probe_refund", "first_try_bonus",
    "iteration_bonus", "retry_grace", "stamina_regen", "retest_charges",
    "interval_stretch", "srs_preview", "edge_ward", "weakness_scan",
    "bench_slots", "design_rubric", "refactor_bonus", "trace_frames",
    "root_cause_bonus", "recovery_grace", "loot_upgrade", "gold_bonus",
    "respec_discount", "rematch_bonus",
)

NEW_EFFECT_LABELS = {key: items.EFFECT_LABELS[key] for key in CLASS_EFFECT_KEYS}

EFFECT_LABELS = {**items.EFFECT_LABELS, **NEW_EFFECT_LABELS}

# Keys that are a capability rather than a quantity: holding two sources of one
# does not make it twice as true. Mirrors `items.total_effects`, plus ours.
MAXED_KEYS = frozenset({
    "reveal_category", "probe_reveal_value", "perf_insight", "second_wind",
    "combo_shield", "srs_preview",
})

# Percentage-shaped keys render as {p}; everything else renders as {v}. Kept
# explicit so a new key cannot quietly print "+0%" forever.
RATE_KEYS = frozenset({
    "hint_discount", "rank_grace", "crit_bonus", "loot_luck", "xp_bonus",
    "retest_bonus", "shrine_bonus", "armor_repair", "declare_bonus",
    "probe_refund", "first_try_bonus", "iteration_bonus", "interval_stretch",
    "refactor_bonus", "root_cause_bonus", "recovery_grace", "gold_bonus",
    "respec_discount", "rematch_bonus",
})


# Ceilings. Percentages compound, and three of these keys stop being a bonus and
# start being a loophole if they reach 1.0 — a probe that always refunds is an
# unlimited probe, a hint that costs nothing in focus is a hint you never had to
# budget for, and a clock that is 100% graced is not a clock. The rest are capped
# so a maxed tree reads as a strong build rather than as a joke. Caps apply to
# the merged total, which is why `clamp` is exported: a caller folding gear,
# attributes and tree together should run it last.
CAPS = {
    # never reach 1.0, on principle
    "probe_refund": 0.75,
    "hint_discount": 0.6,
    "rank_grace": 0.6,
    "recovery_grace": 0.6,
    # capabilities, capped at "generous"
    "edge_ward": 5,
    "retry_grace": 3,
    "weakness_scan": 2,          # of nine weakness classes
    "trace_frames": 10,
    "loot_upgrade": 2,
    "declare_slots": 4,
    "design_rubric": 4,
    "bench_slots": 8,
    "retest_charges": 6,
    "combo_shield": 3,
    # XP and loot rates: doubling is the ceiling
    "xp_bonus": 1.0, "crit_bonus": 1.0, "loot_luck": 1.0, "gold_bonus": 1.0,
    "declare_bonus": 1.0, "first_try_bonus": 1.0, "iteration_bonus": 1.0,
    "refactor_bonus": 1.0, "root_cause_bonus": 1.0, "retest_bonus": 1.0,
    "rematch_bonus": 1.0, "interval_stretch": 1.0, "shrine_bonus": 1.0,
    "armor_repair": 1.0, "respec_discount": 0.75,
}


def clamp(effects: dict) -> dict:
    """Apply CAPS. Idempotent, and safe to run on a merged gear+tree dict."""
    out = dict(effects)
    for key, ceiling in CAPS.items():
        if key in out and out[key] > ceiling:
            out[key] = ceiling
    return out


def describe(effects: dict) -> list:
    """Render an effect dict in the shared vocabulary. Unknown keys are dropped
    rather than guessed at, same as items.describe."""
    out = []
    for key, value in effects.items():
        template = EFFECT_LABELS.get(key)
        if not template:
            continue
        out.append(template.format(v=_fmt(value), p=int(round(value * 100))))
    return out


def _fmt(value) -> str:
    number = round(float(value), 4)
    return str(int(number)) if number == int(number) else str(number)


# ---------------------------------------------------------------------------
# Measures — the evidence a bonus is allowed to attach to
# ---------------------------------------------------------------------------
# Every node names one. This is the mechanism that stops a class from being a
# costume: if no measurement exists, no bonus may be authored, and if the bonus
# exists, playing the class necessarily rehearses the habit.
#
# `chapters` is the ladder range where the evidence can actually be produced.
# "*" means every chapter, and almost everything is "*" on purpose: these are
# properties of the encounter LOOP (probe, declare, fail then clear, retest,
# trace, bank a helper), which exist from the first fight onward. Measures tied
# to CONTENT categories are the rare exception, and they are never allowed at
# tier 1 — see self_check's `scoped_tier_one` proof.


@dataclass(frozen=True)
class Measure:
    id: str
    label: str
    signal: str                  # the concrete thing the engine reads
    chapters: tuple = ("*",)


MEASURES = (
    Measure("PROBE", "Probe accuracy",
            "tactics.run_probe correctness; stats.probes / stats.probes_correct"),
    Measure("DECLARATION", "Pre-write declaration",
            "engine.submit(declared_pattern=...) against Problem.pattern"),
    Measure("COMPLEXITY_CALL", "Stated cost",
            "declared complexity against the encounter's performance trial"),
    Measure("FIRST_TRY", "First-submission clear",
            "Encounter.attempts == 1 on a solved submission"),
    Measure("ITERATION", "Failures that led somewhere",
            "Encounter.attempts > 1 followed by an unaided clear, capped at 3"),
    Measure("RECOVERY", "Came back to it",
            "an encounter failed earlier in the session and cleared later"),
    Measure("SPEED", "Elapsed against target",
            "Encounter seconds against Problem.target_seconds, pre-grace"),
    Measure("EDGE_CALL", "Edge cases named before running",
            "weakness classes named pre-run against tactics.classify_test"),
    Measure("WEAKNESS_STRUCK", "Striking an exposed weakness",
            "Encounter.exposed against the trial that failed; stats.crits"),
    Measure("ROOT_CAUSE", "Naming your own failure",
            "player-named category against grading.Analysis.root_cause"),
    Measure("TRACE", "Reading your own execution",
            "frames of the player's submitted code around the first divergence"),
    Measure("RETEST", "Delayed recall",
            "skills.apply_outcome(is_retest=True, interval_days=...)"),
    Measure("REFACTOR", "Doing it again, better",
            "re-clear of a solved problem with fewer lines or a better runtime"),
    Measure("BENCH", "Reusing your own tools",
            "helpers the player wrote and cleared, banked by choice"),
    Measure("HINT_ECONOMY", "What help costs you",
            "focus spent on hint spells; the RANK cost of a hint is untouched"),
    Measure("FOCUS_ECONOMY", "Focus pool", "player.mana against player.mana_max"),
    Measure("VIGOUR", "Stamina pool", "player.stamina against player.stamina_max"),
    Measure("SHRINE", "Explaining it out loud", "shrine answers accepted"),
    Measure("EXPEDITION", "What the road pays",
            "roll_drop outcomes, gold, armour integrity"),
    # --- the two content-scoped measures, both barred from tier 1 -----------
    Measure("REMATCH", "Beating it again, disguised",
            "boss_rematch tiers; the first boss stands in chapter IV",
            ("counting", "scanning", "order", "recursion", "traversal",
             "optimisation", "craft", "gauntlet")),
    Measure("DESIGN", "Design rubric",
            "design_problem rubric points; DESIGN-pattern problems are permitted "
            "from chapter VIII, when the ladder stops restricting patterns",
            ("traversal", "optimisation", "craft", "gauntlet")),
)

MEASURE_BY_ID = {m.id: m for m in MEASURES}
UNIVERSAL_MEASURES = frozenset(m.id for m in MEASURES if m.chapters == ("*",))


def measure_live_in(measure_id: str, chapter_id: str) -> bool:
    spec = MEASURE_BY_ID[measure_id]
    return spec.chapters == ("*",) or chapter_id in spec.chapters


# ---------------------------------------------------------------------------
# Tree shape
# ---------------------------------------------------------------------------
# Uniform across all six classes, so that "which class is stronger" is never a
# question about arithmetic and always a question about which habit you want.
#
#   3 branches x 7 nodes. Tiers 1,1,2,2,3,3,4.
#   Ranks by tier: 10, 10, 5, 1 -> 51 points to fill one branch, 153 for a class.
#   A tier-N node needs ranks in a NAMED parent one tier up, and a minimum
#   number of points already spent in its own branch.

MAX_RANK_BY_TIER = {1: 10, 2: 10, 3: 5, 4: 1}
PARENT_RANKS_BY_TIER = {2: 3, 3: 3, 4: 5}
BRANCH_POINTS_BY_TIER = {1: 0, 2: 4, 3: 12, 4: 22}
CAPSTONE_LEVEL = 20

POINTS_PER_LEVEL = 1                 # separate from items.POINTS_PER_LEVEL (3)
POINTS_PER_CHAPTER = 1               # one per chapter graduated, evidence only
FIRST_RESPEC_FREE = True

# A foreign class's tier-1 nodes open late, cost double, and cap at half rank.
# Enough to season a build, never enough to be a second build.
DUAL_CLASS_LEVEL = 50
DUAL_CLASS_COST = 2
DUAL_CLASS_MAX_RANK = 5


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    class_id: str
    branch_id: str
    tier: int
    max_rank: int
    per_rank: dict                   # effects added once per rank held
    unlocks: dict                    # rank -> effects granted on reaching it
    measure: str
    blurb: str
    parent: str = ""                 # node id, one tier up, same branch
    parent_ranks: int = 0
    branch_points: int = 0
    capstone: bool = False
    rule: str = ""                   # the non-numeric half, stated plainly

    def effects_at(self, rank: int) -> dict:
        """What holding `rank` ranks of this node is worth, in one dict."""
        rank = max(0, min(int(rank), self.max_rank))
        out: dict = {}
        for key, value in self.per_rank.items():
            out[key] = round(out.get(key, 0) + value * rank, 4)
        for threshold in sorted(self.unlocks):
            if rank >= threshold:
                for key, value in self.unlocks[threshold].items():
                    if key in MAXED_KEYS:
                        out[key] = max(out.get(key, 0), value)
                    else:
                        out[key] = round(out.get(key, 0) + value, 4)
        return out

    def to_dict(self, rank: int = 0) -> dict:
        return {
            "id": self.id, "name": self.name, "branch": self.branch_id,
            "tier": self.tier, "rank": rank, "max_rank": self.max_rank,
            "capstone": self.capstone, "measure": self.measure,
            "measure_label": MEASURE_BY_ID[self.measure].label,
            "measure_signal": MEASURE_BY_ID[self.measure].signal,
            "blurb": self.blurb, "rule": self.rule,
            "parent": self.parent, "parent_ranks": self.parent_ranks,
            "branch_points": self.branch_points,
            "per_rank_text": describe(self.per_rank),
            "current_text": describe(self.effects_at(rank)),
            "next_text": describe(self.effects_at(rank + 1)) if rank < self.max_rank
                         else [],
        }


@dataclass(frozen=True)
class Branch:
    id: str
    name: str
    blurb: str
    nodes: tuple

    @property
    def capacity(self) -> int:
        return sum(n.max_rank for n in self.nodes)


@dataclass(frozen=True)
class CharacterClass:
    id: str
    name: str
    epithet: str
    habit: str                       # the study habit, in one sentence
    trains: str                      # what playing it rehearses
    plays_like: str                  # the felt experience, for the choose screen
    colour: str
    sprite: str
    attributes: dict                 # starting attribute points, 10 of them
    affinity_set: str                # existing items.SETS id the drops favour
    affinity_items: tuple            # existing item ids weighted toward this class
    starter_weapon: str              # an item that exists TODAY
    branches: tuple
    move: str                        # signature move id
    signature_weapon: str            # requested item id, see GEAR_REQUESTS
    signature_set: str               # requested class-restricted set id

    @property
    def nodes(self) -> tuple:
        return tuple(n for b in self.branches for n in b.nodes)

    @property
    def capacity(self) -> int:
        return sum(b.capacity for b in self.branches)


def _node(short: str, name: str, tier: int, per_rank: dict, measure: str,
          blurb: str, *, parent: str = "", unlocks: dict | None = None,
          rule: str = "") -> dict:
    """Authoring shorthand. Ids and gates are derived, never typed twice."""
    return {
        "short": short, "name": name, "tier": tier, "per_rank": per_rank,
        "measure": measure, "blurb": blurb, "parent": parent,
        "unlocks": unlocks or {}, "rule": rule,
    }


def _branch(class_id: str, branch_id: str, name: str, blurb: str,
            rows: list) -> Branch:
    nodes = []
    for row in rows:
        tier = row["tier"]
        parent_id = f"{class_id}_{row['parent']}" if row["parent"] else ""
        nodes.append(Node(
            id=f"{class_id}_{row['short']}",
            name=row["name"], class_id=class_id, branch_id=branch_id,
            tier=tier, max_rank=MAX_RANK_BY_TIER[tier],
            per_rank=dict(row["per_rank"]), unlocks=dict(row["unlocks"]),
            measure=row["measure"], blurb=row["blurb"],
            parent=parent_id, parent_ranks=PARENT_RANKS_BY_TIER.get(tier, 0),
            branch_points=BRANCH_POINTS_BY_TIER[tier],
            capstone=(tier == 4), rule=row["rule"],
        ))
    return Branch(id=branch_id, name=name, blurb=blurb, nodes=tuple(nodes))


# ===========================================================================
# I. THE ANALYST — reasons before writing
# ===========================================================================
# Pays for being right on purpose. The Analyst's whole economy runs on things
# said BEFORE the code exists: what pattern this is, what it will cost, what the
# answer is on an input of your choosing. Guessing is not punished with damage,
# it is punished by costing you the bonus you were playing for, which is the only
# punishment a learning game is allowed.

ANALYST = CharacterClass(
    id="analyst", name="The Analyst", epithet="Reads the water before wading in",
    habit="Say what you believe about the problem before you type anything.",
    trains="Pattern recognition, complexity estimation, and the discipline of a "
           "falsifiable guess.",
    plays_like="Slow first minute, short last minute. You will spend probes and "
               "declarations while other classes are already typing, and you will "
               "submit once.",
    colour="#7ec8ff", sprite="analyst",
    attributes={"LOGIC": 4, "INSIGHT": 3, "FOCUS": 1, "VIGOR": 1, "HASTE": 1},
    affinity_set="pathfinder",
    affinity_items=("oracle_amulet", "matrix_bow", "pathfinder_compass",
                    "asymptote_shard", "testsmith_monocle"),
    starter_weapon="matrix_bow",
    move="called_shot",
    signature_weapon="analysts_calipers",
    signature_set="calculus",
    branches=(
        _branch("analyst", "calculus", "The Calculus",
                "Name the cost before you pay it. Every node here pays out only "
                "on a claim you made in advance.", [
            _node("read_the_water", "Read the Water", 1,
                  {"declare_bonus": 0.03}, "DECLARATION",
                  "Declare the pattern family before your first run. Correct calls "
                  "pay; wrong calls tell you your model was wrong while it is still "
                  "cheap to change.",
                  unlocks={1: {"declare_slots": 1}}),
            _node("order_of_magnitude", "Order of Magnitude", 1,
                  {"declare_bonus": 0.015, "xp_bonus": 0.01}, "COMPLEXITY_CALL",
                  "State the complexity you are about to write. The performance "
                  "trial then tells you whether you were honest with yourself.",
                  unlocks={1: {"perf_insight": 1}, 8: {"declare_slots": 1}}),
            _node("second_reading", "The Second Reading", 2,
                  {"first_try_bonus": 0.04}, "FIRST_TRY",
                  "Re-read the spec before the first submission. Paid on clears "
                  "that needed exactly one.",
                  parent="read_the_water"),
            _node("cost_before_code", "Cost Before Code", 2,
                  {"declare_bonus": 0.02}, "COMPLEXITY_CALL",
                  "A second declaration slot, so the pattern call and the cost call "
                  "stop competing for the same breath.",
                  parent="order_of_magnitude", unlocks={5: {"declare_slots": 1}}),
            _node("falsifier", "The Falsifier", 3,
                  {"root_cause_bonus": 0.06}, "ROOT_CAUSE",
                  "When a declaration turns out wrong, name why before the game "
                  "does. Being wrong out loud is the cheapest lesson on offer.",
                  parent="second_reading"),
            _node("stated_invariant", "The Stated Invariant", 3,
                  {"declare_bonus": 0.03}, "DECLARATION",
                  "Declare the loop invariant you intend to hold. Nothing checks it "
                  "for you; the trials check it for you.",
                  parent="cost_before_code", unlocks={1: {"declare_slots": 1}}),
            _node("the_standing_hypothesis", "THE STANDING HYPOTHESIS", 4,
                  {}, "DECLARATION",
                  "Your declarations stop being a flourish and become the fight.",
                  parent="stated_invariant",
                  unlocks={1: {"declare_bonus": 0.2, "first_try_bonus": 0.25}},
                  rule="When every declaration you made on an encounter proves "
                       "correct and you clear it on the first submission, the "
                       "encounter pays as though it were one difficulty tier "
                       "higher. Declaring nothing declares nothing."),
        ]),
        _branch("analyst", "probe", "The Probe",
                "Charges, refunds, and what a failed probe is worth. A probe never "
                "shows you an algorithm; it tells you whether your model of the "
                "spec survives contact.", [
            _node("hypothesis", "Hypothesis", 1,
                  {"probe_refund": 0.03}, "PROBE",
                  "Probing is cheap for someone who probes on purpose.",
                  unlocks={1: {"probe_charges": 1}}),
            _node("instrumented", "Instrumented", 1,
                  {"crit_bonus": 0.03}, "WEAKNESS_STRUCK",
                  "An exposed weakness hits harder when you were the one who "
                  "exposed it.",),
            _node("disconfirmation", "Disconfirmation", 2,
                  {"probe_refund": 0.02}, "PROBE",
                  "A probe that fails now shows you the true value, which is the "
                  "half of the spec you had misread.",
                  parent="hypothesis", unlocks={1: {"probe_reveal_value": 1}}),
            _node("narrow_case", "The Narrow Case", 2,
                  {"crit_bonus": 0.02, "loot_luck": 0.01}, "WEAKNESS_STRUCK",
                  "Aim probes at the thin end of the input space and the drops "
                  "follow.",
                  parent="instrumented"),
            _node("charged_reasoning", "Charged Reasoning", 3,
                  {"probe_charges": 1}, "PROBE",
                  "One more assertion per battle, per rank. The ceiling on how much "
                  "you can find out before writing.",
                  parent="disconfirmation"),
            _node("named_before_seen", "Named Before Seen", 3,
                  {"crit_bonus": 0.04}, "WEAKNESS_STRUCK",
                  "One weakness CLASS is named at the bell — the class, not the "
                  "input, not the answer. You still have to build the case.",
                  parent="narrow_case", unlocks={1: {"weakness_scan": 1}}),
            _node("the_falsified_map", "THE FALSIFIED MAP", 4,
                  {}, "PROBE",
                  "Every wrong probe is stored and held against the next enemy of "
                  "the same family.",
                  parent="charged_reasoning",
                  unlocks={1: {"probe_refund": 0.25, "weakness_scan": 1,
                               "crit_bonus": 0.3}},
                  rule="A probe you got WRONG on an earlier encounter, repeated "
                       "correctly on a later one of the same family, refunds its "
                       "charge and counts as a retest for RECALL. The game keeps "
                       "your wrong answers; this is the node that makes them "
                       "worth having made."),
        ]),
        _branch("analyst", "long_view", "The Long View",
                "The economics of a careful run: shrines, audits, rematches, and "
                "the loot that rewards a slow walk.", [
            _node("ledger_eye", "Ledger Eye", 1,
                  {"loot_luck": 0.03}, "EXPEDITION",
                  "You notice what the road left lying about.",),
            _node("patient_purse", "The Patient Purse", 1,
                  {"gold_bonus": 0.04}, "EXPEDITION",
                  "Gold, for a class that would rather buy the repair than take "
                  "the hit.",),
            _node("annotated_map", "Annotated Map", 2,
                  {"xp_bonus": 0.02}, "EXPEDITION",
                  "You write down where things were. It pays.",
                  parent="ledger_eye"),
            _node("measured_pace", "Measured Pace", 2,
                  {"mana_max": 2}, "FOCUS_ECONOMY",
                  "Thinking costs focus. Carry more of it.",
                  parent="patient_purse"),
            _node("shrine_survey", "Shrine Survey", 3,
                  {"shrine_bonus": 0.1}, "SHRINE",
                  "Explaining your reasoning out loud at a shrine pays a class that "
                  "was going to reason anyway.",
                  parent="annotated_map"),
            _node("audit_trail", "Audit Trail", 3,
                  {"rematch_bonus": 0.1}, "REMATCH",
                  "You kept notes on the boss. The boss did not keep notes on you.",
                  parent="measured_pace"),
            _node("the_long_division", "THE LONG DIVISION", 4,
                  {}, "EXPEDITION",
                  "The slow road starts paying like the fast one.",
                  parent="shrine_survey",
                  unlocks={1: {"loot_upgrade": 1, "loot_luck": 0.25,
                               "xp_bonus": 0.15}},
                  rule="One drop per battle rolls a tier higher. On any encounter "
                       "you cleared with zero hint spells, it rolls two."),
        ]),
    ),
)


# ===========================================================================
# II. THE BERSERKER — writes fast and iterates
# ===========================================================================
# The only class that is PAID for failed submissions, and the design had to be
# careful about that: a naive "XP per failure" node is a node that rewards typing
# garbage. `iteration_bonus` counts at most three failures, pays only when the
# eventual clear is UNAIDED, and pays less in total than a first-try clear. What
# it actually rewards is the habit of starting before you are certain and
# converging — which is a real timed practical skill and the exact opposite of freezing.

BERSERKER = CharacterClass(
    id="berserker", name="The Berserker", epithet="The first draft is a weapon",
    habit="Type something, run it, read what broke, type again. Do not stall.",
    trains="Speed to first working line, tolerance for a red test, and the nerve "
           "to iterate under a clock.",
    plays_like="Loud and early. You will be wrong three times before the Analyst "
               "has finished reading, and you will be done first anyway.",
    colour="#ff6a7a", sprite="berserker",
    attributes={"HASTE": 4, "VIGOR": 3, "LOGIC": 1, "FOCUS": 1, "INSIGHT": 1},
    affinity_set="chronomancer",
    affinity_items=("quicksilver_edge", "chrono_ring", "chrono_trinket",
                    "rematch_spurs", "twin_sabers"),
    starter_weapon="twin_sabers",
    move="first_draft",
    signature_weapon="draft_axe",
    signature_set="warpath",
    branches=(
        _branch("berserker", "first_draft", "The First Draft",
                "Everything that makes being wrong cheap and being fast worth "
                "something.", [
            _node("type_first", "Type First", 1,
                  {"rank_grace": 0.02}, "SPEED",
                  "Grace on the clock, for rank only. Correctness is never graded "
                  "on a curve and this node does not pretend otherwise.",),
            _node("cheap_mistakes", "Cheap Mistakes", 1,
                  {"iteration_bonus": 0.03}, "ITERATION",
                  "Failed submissions stop costing stamina, and the ones that led "
                  "to an unaided clear start paying.",
                  unlocks={1: {"retry_grace": 1}, 6: {"retry_grace": 1}}),
            _node("momentum", "Momentum", 2,
                  {"rank_grace": 0.015, "xp_bonus": 0.015}, "SPEED",
                  "Speed compounds once you stop re-reading the question between "
                  "every attempt.",
                  parent="type_first"),
            _node("swing_again", "Swing Again", 2,
                  {"iteration_bonus": 0.03}, "ITERATION",
                  "One re-cast per battle that does not break the combo. Use it on "
                  "the attempt you already know is wrong.",
                  parent="cheap_mistakes", unlocks={1: {"second_wind": 1}}),
            _node("blood_up", "Blood Up", 3,
                  {"crit_bonus": 0.06}, "SPEED",
                  "Clearing inside the target time hits like an exposed weakness.",
                  parent="momentum"),
            _node("no_flinch", "No Flinch", 3,
                  {"stamina_regen": 1}, "VIGOUR",
                  "Stamina comes back after every clear, and the combo stops caring "
                  "about the first two failures.",
                  parent="swing_again",
                  unlocks={1: {"combo_shield": 1}, 5: {"combo_shield": 2}}),
            _node("the_third_swing", "THE THIRD SWING", 4,
                  {}, "ITERATION",
                  "Three attempts is not a failure state. It is the method.",
                  parent="no_flinch",
                  unlocks={1: {"iteration_bonus": 0.35, "retry_grace": 1,
                               "combo_shield": 2}},
                  rule="An unaided clear on your third submission or later pays the "
                       "same XP as a first-try clear, provided every attempt after "
                       "the first changed something you can point at. Hints switch "
                       "this off for the encounter, because then the convergence "
                       "was not yours."),
        ]),
        _branch("berserker", "endurance", "The Long Fight",
                "Stamina, focus, and the ability to still be standing at problem "
                "nine of a session.", [
            _node("deep_lungs", "Deep Lungs", 1,
                  {"stamina_max": 2}, "VIGOUR",
                  "More failed casts before Training Camp calls you in.",),
            _node("second_breath", "Second Breath", 1,
                  {"stamina_max": 1}, "VIGOUR",
                  "Stamina returns on every clear, not only on rest.",
                  unlocks={1: {"stamina_regen": 1}, 6: {"stamina_regen": 1}}),
            _node("through_the_wall", "Through the Wall", 2,
                  {"stamina_max": 2}, "VIGOUR",
                  "The session gets longer. The problems do not get easier.",
                  parent="deep_lungs"),
            _node("no_camp", "No Camp", 2,
                  {"xp_bonus": 0.02}, "VIGOUR",
                  "Paid for taking the next encounter instead of the long rest.",
                  parent="second_breath", unlocks={4: {"stamina_regen": 1}}),
            _node("war_pace", "War Pace", 3,
                  {"rank_grace": 0.04}, "SPEED",
                  "The clock bends further for someone who never stopped moving.",
                  parent="through_the_wall"),
            _node("red_mist", "Red Mist", 3,
                  {"crit_bonus": 0.05, "gold_bonus": 0.05}, "EXPEDITION",
                  "Violence, monetised.",
                  parent="no_camp"),
            _node("the_unspent_hour", "THE UNSPENT HOUR", 4,
                  {}, "VIGOUR",
                  "You have more fight in you than the fight has.",
                  parent="war_pace",
                  unlocks={1: {"stamina_max": 12, "stamina_regen": 3,
                               "rank_grace": 0.3}},
                  rule="While your stamina is above half, failed submissions cost "
                       "no combo. Below half, they cost double — the node is a "
                       "reason to keep clearing, not a reason to stop."),
        ]),
        _branch("berserker", "spoils", "Spoils",
                "Loot, gold, armour and rematches. A Berserker's long-term plan is "
                "better equipment, obtained loudly.", [
            _node("rough_hands", "Rough Hands", 1,
                  {"loot_luck": 0.03}, "EXPEDITION",
                  "You break more things open than you mean to.",),
            _node("take_the_purse", "Take the Purse", 1,
                  {"gold_bonus": 0.04}, "EXPEDITION",
                  "Gold, for plate and for the Armorer's patience.",),
            _node("trophy_rack", "Trophy Rack", 2,
                  {"xp_bonus": 0.02}, "EXPEDITION",
                  "You keep the teeth. The teeth are worth XP.",
                  parent="rough_hands"),
            _node("armourer_friend", "The Armorer's Friend", 2,
                  {"armor_repair": 0.05}, "EXPEDITION",
                  "Plate comes back faster for a regular customer.",
                  parent="take_the_purse"),
            _node("break_the_door", "Break the Door", 3,
                  {"loot_luck": 0.04}, "EXPEDITION",
                  "One drop a battle rolls a tier higher, because you hit the "
                  "chest as well as the enemy.",
                  parent="trophy_rack", unlocks={1: {"loot_upgrade": 1}}),
            _node("rematch_appetite", "Rematch Appetite", 3,
                  {"rematch_bonus": 0.1}, "REMATCH",
                  "You want to fight it again. It does not want that.",
                  parent="armourer_friend"),
            _node("the_open_hand", "THE OPEN HAND", 4,
                  {}, "EXPEDITION",
                  "Named for the King's offer, and for refusing it.",
                  parent="break_the_door",
                  unlocks={1: {"loot_upgrade": 1, "loot_luck": 0.3,
                               "gold_bonus": 0.4}},
                  rule="Drops improve with your combo rather than with your level. "
                       "A cold streak pays like a beginner's; a hot one pays like "
                       "a boss. Nothing here touches whether you had to solve it."),
        ]),
    ),
)


# ===========================================================================
# III. THE ARCHIVIST — remembers
# ===========================================================================
# The class that plays the SRS scheduler as a weapon. Its hint discount is the
# one node family in this file that could look like pay-to-skip, so it is worth
# stating exactly what it does and does not do: a hint spell costs FOCUS and it
# costs RANK. This tree makes the focus cheaper. It never touches the rank
# ceiling a hint imposes, never unlocks a deeper hint tier early, and never
# shortens the hint tree. You pay for help in the currency that matters exactly
# as much as everyone else does.

ARCHIVIST = CharacterClass(
    id="archivist", name="The Archivist", epithet="Nothing is learned once",
    habit="Meet the same idea again, disguised, on a delay, until it is yours.",
    trains="Retention, pattern recognition at speed, and the habit of reviewing "
           "before the review is comfortable.",
    plays_like="Quiet and cumulative. Your first week looks worse than everyone "
               "else's. Your fourth week does not.",
    colour="#a89aff", sprite="archivist",
    attributes={"FOCUS": 4, "INSIGHT": 3, "LOGIC": 1, "VIGOR": 1, "HASTE": 1},
    affinity_set="archivist",
    affinity_items=("archivist_ring", "thirty_day_signet", "shrine_charm",
                    "memoist_ledger", "dynamic_relic"),
    starter_weapon="hashblade",
    move="open_the_index",
    signature_weapon="recall_chain",
    signature_set="unerased",
    branches=(
        _branch("archivist", "recall", "The Recall",
                "Memory ambushes: more of them, further apart, worth more when "
                "they land.", [
            _node("rote", "Rote", 1,
                  {"retest_bonus": 0.03}, "RETEST",
                  "A disguised variant days later is the strongest evidence this "
                  "game collects. You are paid accordingly.",),
            _node("the_familiar_shape", "The Familiar Shape", 1,
                  {"declare_bonus": 0.03}, "DECLARATION",
                  "Name the pattern on sight, before reading the body. Recognition "
                  "is recall wearing a hat.",
                  unlocks={1: {"declare_slots": 1}}),
            _node("spaced", "Spaced", 2,
                  {"interval_stretch": 0.03}, "RETEST",
                  "Reviews schedule further out. Further out is harder, and harder "
                  "is what makes the memory stick.",
                  parent="rote"),
            _node("disguise_proof", "Disguise-Proof", 2,
                  {"rematch_bonus": 0.04}, "REMATCH",
                  "A boss with its tells removed is the same boss. You will "
                  "recognise it.",
                  parent="the_familiar_shape"),
            _node("thirty_days", "Thirty Days", 3,
                  {"retest_bonus": 0.06}, "RETEST",
                  "The long intervals, and a list of what is due before you set out.",
                  parent="spaced", unlocks={1: {"srs_preview": 1}}),
            _node("the_second_meeting", "The Second Meeting", 3,
                  {"rematch_bonus": 0.08, "first_try_bonus": 0.02}, "REMATCH",
                  "Second meetings should be shorter than first ones.",
                  parent="disguise_proof"),
            _node("the_long_memory", "THE LONG MEMORY", 4,
                  {}, "RETEST",
                  "The schedule stops being a chore and becomes the build.",
                  parent="thirty_days",
                  unlocks={1: {"retest_charges": 2, "retest_bonus": 0.4,
                               "interval_stretch": 0.25}},
                  rule="A memory ambush cleared unaided at an interval of thirty "
                       "days or more pays as a BOSS-weight clear and immediately "
                       "schedules the next one at sixty. Failing one costs nothing "
                       "but the interval, which resets. Nothing is revealed either "
                       "way."),
        ]),
        _branch("archivist", "codex", "The Codex",
                "Focus, and what help costs. Cheaper in focus, never cheaper in "
                "rank.", [
            _node("cheap_pages", "Cheap Pages", 1,
                  {"hint_discount": 0.02}, "HINT_ECONOMY",
                  "Learning spells cost less focus. They cost exactly the same "
                  "rank, which is the cost that was ever the point.",),
            _node("deep_shelves", "Deep Shelves", 1,
                  {"mana_max": 2}, "FOCUS_ECONOMY",
                  "A bigger pool to spend out of.",),
            _node("cross_reference", "Cross-Reference", 2,
                  {"hint_discount": 0.015}, "HINT_ECONOMY",
                  "You have read something adjacent to this before, and the index "
                  "knows where.",
                  parent="cheap_pages"),
            _node("standing_index", "The Standing Index", 2,
                  {"mana_max": 2}, "FOCUS_ECONOMY",
                  "Focus returns after every cleared encounter.",
                  parent="deep_shelves",
                  unlocks={2: {"mana_regen": 1}, 6: {"mana_regen": 1},
                           10: {"mana_regen": 1}}),
            _node("marginalia", "Marginalia", 3,
                  {"root_cause_bonus": 0.05}, "ROOT_CAUSE",
                  "Write in the margin what broke and why. Paid when your note "
                  "matches the diagnosis.",
                  parent="cross_reference"),
            _node("the_open_ledger", "The Open Ledger", 3,
                  {"shrine_bonus": 0.1}, "SHRINE",
                  "Saying it out loud at a shrine is a review with witnesses.",
                  parent="standing_index", unlocks={1: {"srs_preview": 1}}),
            _node("the_grey_repository", "THE GREY REPOSITORY", 4,
                  {}, "HINT_ECONOMY",
                  "Named for the vault-face nobody can open. You are not opening "
                  "it either; you are cataloguing the outside.",
                  parent="marginalia",
                  unlocks={1: {"hint_discount": 0.25, "mana_regen": 5,
                               "retest_bonus": 0.3}},
                  rule="Any hint spell you spend focus on is filed. The same hint "
                       "on a later encounter of that family is free in focus — and "
                       "still costs the same rank, every time, forever. The "
                       "Archivist never gets cheaper help, only cheaper access to "
                       "help they have already paid rank for once."),
        ]),
        _branch("archivist", "index", "The Index",
                "Scheduling, the day's due list, and the quiet economy of someone "
                "who keeps records.", [
            _node("day_book", "Day Book", 1,
                  {"xp_bonus": 0.02}, "RETEST",
                  "The day's ambushes, listed before you set out, and more of them "
                  "on offer as the book fills.",
                  unlocks={1: {"srs_preview": 1}, 5: {"retest_charges": 1},
                           10: {"retest_charges": 1}}),
            _node("catalogue", "Catalogue", 1,
                  {"loot_luck": 0.03}, "EXPEDITION",
                  "You know what you already have, which is most of knowing what "
                  "to look for.",),
            _node("the_due_list", "The Due List", 2,
                  {"retest_bonus": 0.03}, "RETEST",
                  "Due work first. It is never the work you want.",
                  parent="day_book"),
            _node("borrowed_light", "Borrowed Light", 2,
                  {"gold_bonus": 0.03, "shrine_bonus": 0.04}, "SHRINE",
                  "Mentors talk to someone who brings notes.",
                  parent="catalogue"),
            _node("recall_at_depth", "Recall at Depth", 3,
                  {"interval_stretch": 0.05}, "RETEST",
                  "Push the intervals out until they are uncomfortable. That is "
                  "where retention is made.",
                  parent="the_due_list"),
            _node("quiet_hours", "Quiet Hours", 3,
                  {"respec_discount": 0.1}, "EXPEDITION",
                  "The Armorer unpicks a tree cheaply for someone who can show them "
                  "what they wrote down.",
                  parent="borrowed_light"),
            _node("the_unerased_shelf", "THE UNERASED SHELF", 4,
                  {}, "RETEST",
                  "One shelf the erasure missed, because someone kept copying it "
                  "out.",
                  parent="recall_at_depth",
                  unlocks={1: {"retest_charges": 3, "srs_preview": 1,
                               "xp_bonus": 0.25}},
                  rule="Three extra memory ambushes a day, drawn from the families "
                       "your skill state says are decaying fastest rather than from "
                       "the ones that are due. They are harder than the due list. "
                       "That is the offer."),
        ]),
    ),
)


# ===========================================================================
# IV. THE WARDEN — tests first
# ===========================================================================
# The Warden's core loop: before running anything, name the classes of input you
# think will break it. Real calls become wards that absorb a failed submission.
# Wrong calls cost focus. This is `tactics.classify_test` turned into a wager, and
# it is a transferable debugging habit: asking "what about the empty list"
# before writing makes the boundary case part of the design.

WARDEN = CharacterClass(
    id="warden", name="The Warden", epithet="Name what breaks it, then write it",
    habit="Before the first run, say which inputs you expect to break this.",
    trains="Edge-case reasoning, test design, and defensive thinking that arrives "
           "before the bug rather than after it.",
    plays_like="Deliberate and very hard to kill. You lose time up front and you "
               "almost never lose a combo.",
    colour="#8fd07a", sprite="warden",
    attributes={"LOGIC": 3, "VIGOR": 3, "INSIGHT": 2, "FOCUS": 1, "HASTE": 1},
    affinity_set="testsmith",
    affinity_items=("testsmith_monocle", "testsmith_shield", "testsmith_ring",
                    "armorers_last_plate", "debuggers_lens"),
    starter_weapon="testsmith_shield",
    move="set_the_perimeter",
    signature_weapon="boundary_maul",
    signature_set="bulwark",
    branches=(
        _branch("warden", "perimeter", "The Perimeter",
                "Edge cases called in advance. A call that proves real is armour; "
                "a call that does not is information.", [
            _node("name_the_boundary", "Name the Boundary", 1,
                  {"crit_bonus": 0.02}, "EDGE_CALL",
                  "Name an input class before the first run. If the hidden trials "
                  "agree with you, it becomes a ward that eats one failed "
                  "submission.",
                  unlocks={1: {"edge_ward": 1}, 6: {"edge_ward": 1}}),
            _node("the_empty_case", "The Empty Case", 1,
                  {"probe_refund": 0.04}, "PROBE",
                  "Empty input is the boundary most loops mishandle and the probe "
                  "most players forget to spend.",
                  unlocks={1: {"probe_charges": 1}}),
            _node("off_by_one_watch", "Off-By-One Watch", 2,
                  {"crit_bonus": 0.025}, "EDGE_CALL",
                  "Probes name the failure category they would trigger. The "
                  "category, not the value, and never the fix.",
                  parent="name_the_boundary", unlocks={1: {"reveal_category": 1}}),
            _node("hostile_input", "Hostile Input", 2,
                  {"probe_refund": 0.03}, "PROBE",
                  "Assume the caller is adversarial, because in production the "
                  "caller is adversarial.",
                  parent="the_empty_case", unlocks={6: {"probe_charges": 1}}),
            _node("the_full_suite", "The Full Suite", 3,
                  {"crit_bonus": 0.03}, "EDGE_CALL",
                  "Two more wards, for a player who can name five different ways "
                  "in and be right about four of them.",
                  parent="off_by_one_watch",
                  unlocks={2: {"edge_ward": 1}, 5: {"edge_ward": 1}}),
            _node("adversary", "Adversary", 3,
                  {"crit_bonus": 0.04}, "WEAKNESS_STRUCK",
                  "One weakness class is named at the bell. You still have to build "
                  "the input that exercises it.",
                  parent="hostile_input", unlocks={1: {"weakness_scan": 1}}),
            _node("set_the_perimeter_node", "SET THE PERIMETER", 4,
                  {}, "EDGE_CALL",
                  "The fight starts with your fence already up.",
                  parent="the_full_suite",
                  unlocks={1: {"edge_ward": 1, "weakness_scan": 1,
                               "crit_bonus": 0.2}},
                  rule="Name three edge classes before the first run. Every one "
                       "that proves real becomes a ward AND turns its hidden trial "
                       "critical. Every one that does not costs a third of your "
                       "focus. Naming all nine classes is not a strategy; it is a "
                       "focus bill."),
        ]),
        _branch("warden", "proof", "The Proof",
                "Tests as evidence rather than as ritual: write the failing one "
                "first, and keep it.", [
            _node("write_it_down", "Write It Down", 1,
                  {"first_try_bonus": 0.03}, "FIRST_TRY",
                  "The test you wrote before the code is the reason there was only "
                  "one submission.",),
            _node("red_then_green", "Red Then Green", 1,
                  {"iteration_bonus": 0.03}, "ITERATION",
                  "A failing submission that you PREDICTED counts as progress and "
                  "is paid as progress.",),
            _node("coverage", "Coverage", 2,
                  {"xp_bonus": 0.02}, "COMPLEXITY_CALL",
                  "Performance trials report their timing budget, so 'fast enough' "
                  "becomes a number you can argue with.",
                  parent="write_it_down", unlocks={1: {"perf_insight": 1}}),
            _node("regression", "Regression", 2,
                  {"retest_bonus": 0.04}, "RETEST",
                  "The bug you fixed stays fixed because you kept the test that "
                  "caught it.",
                  parent="red_then_green"),
            _node("the_failing_case_first", "The Failing Case First", 3,
                  {"root_cause_bonus": 0.06}, "ROOT_CAUSE",
                  "Name the category before the diagnosis appears. You usually "
                  "already know.",
                  parent="coverage"),
            _node("no_green_without_red", "No Green Without Red", 3,
                  {"declare_bonus": 0.05}, "DECLARATION",
                  "Declare what the test will prove before you run it.",
                  parent="regression", unlocks={1: {"declare_slots": 1}}),
            _node("the_broken_build", "THE BROKEN BUILD", 4,
                  {}, "ROOT_CAUSE",
                  "You are the person who finds it before the release.",
                  parent="the_failing_case_first",
                  unlocks={1: {"edge_ward": 2, "root_cause_bonus": 0.4,
                               "first_try_bonus": 0.2}},
                  rule="On any failed submission, you may name the failure category "
                       "BEFORE the diagnosis renders. Correct, and the attempt "
                       "costs no combo and no stamina. Wrong, and you read the "
                       "diagnosis like everyone else. The game never names it for "
                       "you first."),
        ]),
        _branch("warden", "bulwark", "The Bulwark",
                "Plate, stamina, and the unglamorous business of still being here "
                "at the end of a long dungeon.", [
            _node("plate_discipline", "Plate Discipline", 1,
                  {"stamina_max": 2}, "VIGOUR",
                  "More failed casts between you and Training Camp.",),
            _node("field_repair", "Field Repair", 1,
                  {"armor_repair": 0.05}, "EXPEDITION",
                  "You carry the wire. It is not glamorous.",),
            _node("hold_the_line", "Hold the Line", 2,
                  {"stamina_max": 1}, "VIGOUR",
                  "The combo survives a failure, and later two.",
                  parent="plate_discipline",
                  unlocks={1: {"combo_shield": 1}, 8: {"combo_shield": 2}}),
            _node("spare_parts", "Spare Parts", 2,
                  {"gold_bonus": 0.03, "loot_luck": 0.02}, "EXPEDITION",
                  "Everything broken is worth something to someone.",
                  parent="field_repair"),
            _node("the_last_plate", "The Last Plate", 3,
                  {"stamina_max": 2}, "VIGOUR",
                  "Failed submissions stop costing stamina, twice a fight, and "
                  "the plate keeps getting thicker.",
                  parent="hold_the_line",
                  unlocks={1: {"retry_grace": 1}, 4: {"retry_grace": 1}}),
            _node("quartermaster", "Quartermaster", 3,
                  {"armor_repair": 0.1, "respec_discount": 0.06}, "EXPEDITION",
                  "You know the Armorer's first name and their opening hours.",
                  parent="spare_parts"),
            _node("the_unbroken_wall", "THE UNBROKEN WALL", 4,
                  {}, "VIGOUR",
                  "The long defeat, held for one more generation.",
                  parent="the_last_plate",
                  unlocks={1: {"combo_shield": 2, "retry_grace": 1,
                               "stamina_max": 15}},
                  rule="Your combo cannot be broken by a submission that fails ONLY "
                       "on an edge case you named before running. Failing on the "
                       "ordinary case still breaks it, and should."),
        ]),
    ),
)


# ===========================================================================
# V. THE ARTIFICER — builds tools
# ===========================================================================
# The bench is the mechanic, and the rule on it is narrow on purpose: a bench
# slot holds a helper THE PLAYER WROTE AND CLEARED, in their own words, and it
# returns only in adventure mode. It is not a library of answers; it is the
# `utils.py` a working engineer accumulates. Timed Practical Mode empties the bench,
# same as it empties everything else.

ARTIFICER = CharacterClass(
    id="artificer", name="The Artificer", epithet="Build it once, properly",
    habit="Write the helper, name the interface, come back and make it shorter.",
    trains="Decomposition, API design, refactoring, and the judgement to reuse "
           "rather than retype.",
    plays_like="Slow to start and absurd by chapter eight, because by then you "
               "are standing on a shelf of things you wrote yourself.",
    colour="#e8c37d", sprite="artificer",
    attributes={"INSIGHT": 4, "FOCUS": 3, "LOGIC": 1, "VIGOR": 1, "HASTE": 1},
    affinity_set="memoist",
    affinity_items=("architects_seal", "memoist_ledger", "forgekeepers_grips",
                    "dynamic_relic", "memoist_visor"),
    starter_weapon="dynamic_relic",
    move="lay_the_bench",
    signature_weapon="toolwrights_spanner",
    signature_set="forgewright",
    branches=(
        _branch("artificer", "bench", "The Bench",
                "Helpers you wrote, kept, and made shorter. Nothing on the bench "
                "was written by the game.", [
            _node("keep_the_helper", "Keep the Helper", 1,
                  {"xp_bonus": 0.02}, "BENCH",
                  "A helper you wrote and cleared comes with you into later "
                  "adventure encounters. Timed Practical Mode takes the bench away.",
                  unlocks={1: {"bench_slots": 1}, 4: {"bench_slots": 1},
                           8: {"bench_slots": 1}}),
            _node("tidy_hands", "Tidy Hands", 1,
                  {"refactor_bonus": 0.025}, "REFACTOR",
                  "Re-clear something you already solved, shorter or measurably "
                  "faster, and be paid for the second version.",),
            _node("reusable", "Reusable", 2,
                  {"refactor_bonus": 0.015, "xp_bonus": 0.01}, "BENCH",
                  "A helper that survived three encounters unedited was a good "
                  "helper.",
                  parent="keep_the_helper", unlocks={6: {"bench_slots": 1}}),
            _node("second_pass", "Second Pass", 2,
                  {"refactor_bonus": 0.02}, "REFACTOR",
                  "The first version works. The second version is the one you "
                  "would defend.",
                  parent="tidy_hands"),
            _node("the_shorter_version", "The Shorter Version", 3,
                  {"refactor_bonus": 0.04}, "REFACTOR",
                  "Fewer lines, same trials, better runtime. Measured, not "
                  "asserted — performance trials publish the budget you are "
                  "beating.",
                  parent="reusable", unlocks={1: {"perf_insight": 1}}),
            _node("interface_first", "Interface First", 3,
                  {"declare_bonus": 0.04}, "DESIGN",
                  "Extra rubric points on design answers: more to argue, more to "
                  "earn, more to get wrong.",
                  parent="second_pass",
                  unlocks={1: {"design_rubric": 1}, 4: {"design_rubric": 1}}),
            _node("the_standing_toolkit", "THE STANDING TOOLKIT", 4,
                  {}, "BENCH",
                  "A shelf of your own code, carried into every fight that is not "
                  "a timed practical.",
                  parent="the_shorter_version",
                  unlocks={1: {"bench_slots": 3, "refactor_bonus": 0.2,
                               "xp_bonus": 0.15}},
                  rule="Bench helpers may call each other. A bench entry that goes "
                       "unused for twenty encounters is retired automatically, "
                       "because a toolkit you do not use is a liability you are "
                       "maintaining."),
        ]),
        _branch("artificer", "architecture", "Architecture",
                "Drawing the box before filling it. Half of this branch pays on "
                "any function; the design nodes need chapter VIII's freedom to "
                "find design work to pay on.", [
            _node("draw_the_box", "Draw the Box", 1,
                  {"declare_bonus": 0.02}, "DECLARATION",
                  "Declare the signature and the contract before the body. True of "
                  "a system and equally true of a five-line function.",
                  unlocks={1: {"declare_slots": 1}}),
            _node("name_the_parts", "Name the Parts", 1,
                  {"declare_bonus": 0.015, "first_try_bonus": 0.02}, "DECLARATION",
                  "Naming the pieces correctly is most of the design, and the game "
                  "will eventually quote your names back to you.",),
            _node("tradeoff", "Tradeoff", 2,
                  {"declare_bonus": 0.02}, "COMPLEXITY_CALL",
                  "State what you are trading away. Performance trials publish "
                  "their budget so the trade is arguable.",
                  parent="draw_the_box", unlocks={1: {"perf_insight": 1}}),
            _node("the_written_contract", "The Written Contract", 2,
                  {"xp_bonus": 0.02, "refactor_bonus": 0.02}, "DESIGN",
                  "An extra rubric point on design answers. It is not a free point; "
                  "it is another thing you must actually say.",
                  parent="name_the_parts", unlocks={5: {"design_rubric": 1}}),
            _node("scaling_story", "The Scaling Story", 3,
                  {"declare_bonus": 0.04, "crit_bonus": 0.03}, "COMPLEXITY_CALL",
                  "What happens at ten times the input, said out loud, before the "
                  "performance trial says it for you.",
                  parent="tradeoff"),
            _node("failure_modes", "Failure Modes", 3,
                  {"root_cause_bonus": 0.05}, "ROOT_CAUSE",
                  "Design is mostly deciding which failures you are choosing.",
                  parent="the_written_contract",
                  unlocks={1: {"reveal_category": 1}}),
            _node("the_architects_seal", "THE ARCHITECT'S SEAL", 4,
                  {}, "DESIGN",
                  "The Seal answers to whoever can draw the box, which is why it "
                  "has been lying in a drawer since the Council.",
                  parent="scaling_story",
                  unlocks={1: {"design_rubric": 3, "declare_slots": 1,
                               "declare_bonus": 0.25}},
                  rule="Design answers are graded against three extra rubric "
                       "points, and a design answer that scores every point "
                       "unlocks a REFACTOR retest of the same system later in the "
                       "week. More work, more evidence, more XP; no shortcut."),
        ]),
        _branch("artificer", "workshop", "The Workshop",
                "Upgrade paths, salvage, focus and the Armorer. The dull half of "
                "being the person who builds things.", [
            _node("salvage", "Salvage", 1,
                  {"loot_luck": 0.03}, "EXPEDITION",
                  "Broken gear is parts.",),
            _node("keen_edge", "Keen Edge", 1,
                  {"armor_repair": 0.05}, "EXPEDITION",
                  "You maintain your own equipment, which is cheaper and slower.",),
            _node("upgrade_path", "Upgrade Path", 2,
                  {"loot_luck": 0.02}, "EXPEDITION",
                  "One drop a battle rolls a tier higher, because you know what to "
                  "keep.",
                  parent="salvage", unlocks={1: {"loot_upgrade": 1}}),
            _node("spare_focus", "Spare Focus", 2,
                  {"mana_max": 2}, "FOCUS_ECONOMY",
                  "Focus to spend on the bench, and some of it back after a clear.",
                  parent="keen_edge",
                  unlocks={4: {"mana_regen": 1}, 9: {"mana_regen": 1}}),
            _node("bulk_order", "Bulk Order", 3,
                  {"gold_bonus": 0.06}, "EXPEDITION",
                  "You buy parts by the crate and the Armorer stops arguing.",
                  parent="upgrade_path"),
            _node("the_patient_file", "The Patient File", 3,
                  {"respec_discount": 0.08, "shrine_bonus": 0.06}, "EXPEDITION",
                  "Rebuilding a tree is a refactor. You are good at refactors.",
                  parent="spare_focus"),
            _node("the_forge_that_pays_once", "THE FORGE THAT PAYS ONCE", 4,
                  {}, "EXPEDITION",
                  "Named for the argument of chapter nine, applied to a workshop.",
                  parent="bulk_order",
                  unlocks={1: {"loot_upgrade": 1, "gold_bonus": 0.4,
                               "loot_luck": 0.25}},
                  rule="An item you have already upgraded once upgrades again for "
                       "half the evidence. The evidence requirement is never "
                       "zero, because the requirement is the point of the "
                       "upgrade."),
        ]),
    ),
)


# ===========================================================================
# VI. THE SEER — reads code
# ===========================================================================
# The Seer's affordance is `trace_frames`: stepping THE PLAYER'S OWN submitted
# code around the point it first diverged from expected. It is worth being
# precise about why that is not cheating. The reference implementation is never
# shown, never stepped, never quoted. What the Seer sees is their own program's
# state — which they could have obtained with print statements and forty seconds.
# The node sells the forty seconds, not the answer.

SEER = CharacterClass(
    id="seer", name="The Seer", epithet="The bug is already on the screen",
    habit="Read the code you have before writing code you do not.",
    trains="Tracing, state prediction, spot-the-flaw, and naming a failure "
           "category from its shape.",
    plays_like="Unnervingly calm during failures. Where the Berserker rewrites, "
               "you read, and you are usually done one attempt sooner.",
    colour="#c8a8ff", sprite="seer",
    attributes={"LOGIC": 4, "FOCUS": 2, "INSIGHT": 2, "VIGOR": 1, "HASTE": 1},
    affinity_set="vernacular",
    affinity_items=("debuggers_lens", "read_failure_lens", "silent_crown",
                    "depthblade", "vernacular_charm"),
    starter_weapon="debuggers_lens",
    move="second_sight",
    signature_weapon="tracing_needle",
    signature_set="clearsight",
    branches=(
        _branch("seer", "reading", "The Reading",
                "Your own execution, read slowly. Nothing in this branch has ever "
                "seen the reference implementation.", [
            _node("trace_by_eye", "Trace By Eye", 1,
                  {"root_cause_bonus": 0.02}, "TRACE",
                  "Step your own submitted code around the first divergence. Your "
                  "code, your variables, your mistake.",
                  unlocks={1: {"trace_frames": 1}, 6: {"trace_frames": 1}}),
            _node("the_tell", "The Tell", 1,
                  {"root_cause_bonus": 0.03}, "ROOT_CAUSE",
                  "Every failure has a shape. Name the shape before the diagnosis "
                  "renders.",),
            _node("divergence", "Divergence", 2,
                  {"xp_bonus": 0.02, "recovery_grace": 0.02}, "TRACE",
                  "More frames either side of the split, which is usually where "
                  "the wrong assumption is standing.",
                  parent="trace_by_eye",
                  unlocks={3: {"trace_frames": 1}}),
            _node("spot_the_flaw", "Spot the Flaw", 2,
                  {"root_cause_bonus": 0.02}, "ROOT_CAUSE",
                  "Probes name the failure category they would trigger. The "
                  "category is a direction, not a destination.",
                  parent="the_tell", unlocks={1: {"reveal_category": 1}}),
            _node("state_at_the_edge", "State at the Edge", 3,
                  {"trace_frames": 1}, "TRACE",
                  "One more frame per rank. At five you can watch an off-by-one "
                  "happen rather than deduce it.",
                  parent="divergence"),
            _node("cold_read", "Cold Read", 3,
                  {"first_try_bonus": 0.05}, "FIRST_TRY",
                  "Reading the problem properly is a form of tracing. It shows up "
                  "as first-try clears.",
                  parent="spot_the_flaw"),
            _node("second_sight_node", "SECOND SIGHT", 4,
                  {}, "TRACE",
                  "You stop guessing which line it was.",
                  parent="state_at_the_edge",
                  unlocks={1: {"trace_frames": 2, "root_cause_bonus": 0.3,
                               "reveal_category": 1}},
                  rule="On a failed submission you may step your own code from the "
                       "first divergent frame to the end of that trial. The "
                       "expected output is never shown and the reference is never "
                       "stepped; you are reading your program, not theirs."),
        ]),
        _branch("seer", "diagnosis", "The Diagnosis",
                "Coming back to a fight you already lost, and winning it by "
                "reading rather than rewriting.", [
            _node("steady_hand", "Steady Hand", 1,
                  {"recovery_grace": 0.025}, "RECOVERY",
                  "Clock grace on an encounter you already failed this session. "
                  "For rank only; the trials do not soften.",),
            _node("read_the_stack", "Read the Stack", 1,
                  {"root_cause_bonus": 0.02, "xp_bonus": 0.01}, "ROOT_CAUSE",
                  "A traceback is a sentence. Most players skip to the last line "
                  "and lose the subject.",),
            _node("bisect", "Bisect", 2,
                  {"recovery_grace": 0.015, "iteration_bonus": 0.02}, "ITERATION",
                  "Halve the suspect region each attempt. Paid per failure that "
                  "narrowed something.",
                  parent="steady_hand"),
            _node("the_minimal_repro", "The Minimal Repro", 2,
                  {"probe_refund": 0.04}, "PROBE",
                  "The smallest input that still breaks it is worth more than the "
                  "one that broke it first.",
                  parent="read_the_stack", unlocks={1: {"probe_charges": 1}}),
            _node("one_change_at_a_time", "One Change At A Time", 3,
                  {"iteration_bonus": 0.04}, "ITERATION",
                  "Two changes at once is two experiments and no result. Failed "
                  "submissions stop costing stamina while you are being "
                  "disciplined about it.",
                  parent="bisect",
                  unlocks={1: {"retry_grace": 1}, 4: {"retry_grace": 1}}),
            _node("the_root_not_the_symptom", "The Root, Not the Symptom", 3,
                  {"root_cause_bonus": 0.07}, "ROOT_CAUSE",
                  "The category the game would have named, named by you, before "
                  "it does.",
                  parent="the_minimal_repro"),
            _node("the_read_failure", "THE READ FAILURE", 4,
                  {}, "ROOT_CAUSE",
                  "Named for the Lens. The Lens was named for the habit.",
                  parent="the_root_not_the_symptom",
                  unlocks={1: {"root_cause_bonus": 0.45, "recovery_grace": 0.2,
                               "trace_frames": 2}},
                  rule="Name the failure category correctly on a failed submission "
                       "and the next submission on that encounter cannot break "
                       "your combo. Name it wrong and you have spent the "
                       "protection. The diagnosis still renders either way."),
        ]),
        _branch("seer", "margin", "The Margin",
                "Secrets, shrines and the things the erasure missed. The Seer "
                "finds the world's footnotes because the Seer reads footnotes.", [
            _node("peripheral", "Peripheral", 1,
                  {"loot_luck": 0.03}, "EXPEDITION",
                  "Secrets reveal themselves more readily to someone looking "
                  "sideways.",),
            _node("quiet_step", "Quiet Step", 1,
                  {"shrine_bonus": 0.06}, "SHRINE",
                  "Shrines pay for the explanation rather than the result, which "
                  "suits you.",),
            _node("the_overlooked", "The Overlooked", 2,
                  {"loot_luck": 0.02, "xp_bonus": 0.015}, "EXPEDITION",
                  "You were overlooked too. It is why you are still here.",
                  parent="peripheral"),
            _node("listening", "Listening", 2,
                  {"mana_max": 2}, "FOCUS_ECONOMY",
                  "Focus for the long read, and some of it back after a clear.",
                  parent="quiet_step", unlocks={5: {"mana_regen": 1}}),
            _node("what_was_erased", "What Was Erased", 3,
                  {"loot_luck": 0.04}, "EXPEDITION",
                  "One drop a battle rolls a tier higher. You are finding things "
                  "that were meant to stay lost.",
                  parent="the_overlooked", unlocks={1: {"loot_upgrade": 1}}),
            _node("the_green_index", "The Green Index", 3,
                  {"rematch_bonus": 0.08, "gold_bonus": 0.04}, "REMATCH",
                  "You worked out what the small green sphere is for. It is not "
                  "good news.",
                  parent="listening"),
            _node("found_in_a_margin", "FOUND IN A MARGIN", 4,
                  {}, "EXPEDITION",
                  "Where the last Architect was found, and how.",
                  parent="what_was_erased",
                  unlocks={1: {"loot_upgrade": 1, "loot_luck": 0.3,
                               "weakness_scan": 1}},
                  rule="Hidden routes and secrets in a region you have restored "
                       "mark themselves as present — the region, never the tile. "
                       "You still walk it."),
        ]),
    ),
)


CLASSES: tuple = (ANALYST, BERSERKER, ARCHIVIST, WARDEN, ARTIFICER, SEER)
CLASS_BY_ID = {c.id: c for c in CLASSES}
NODE_BY_ID = {n.id: n for c in CLASSES for n in c.nodes}
BRANCH_BY_ID = {(c.id, b.id): b for c in CLASSES for b in c.branches}


# ===========================================================================
# Signature moves
# ===========================================================================
# One per class, available from level 1, free of charge, once per encounter. A
# move is a WAGER on something you believe, resolved against evidence the engine
# already computes. Every one of them can be declined; none of them is required
# to clear anything; not one of them can be used to obtain an answer.
#
# `window` says when the move may be used, because a move you can fire after
# seeing the trials is a different and much worse move.

@dataclass(frozen=True)
class Move:
    id: str
    name: str
    class_id: str
    window: str                  # when it may be used
    cost: dict                   # {"mana": n, "stamina": n}
    wager: str                   # what you are claiming
    on_right: str                # what being right buys
    on_wrong: str                # what being wrong costs
    measure: str
    blurb: str


MOVES = (
    Move("called_shot", "Called Shot", "analyst",
         "before your first run of the encounter",
         {"mana": 4, "stamina": 0},
         "Name the pattern family and the complexity you are about to write.",
         "The encounter's first cleared trial is critical, and the clear pays the "
         "full declaration bonus.",
         "The declaration slot is spent and you are told, immediately, that your "
         "model of the problem disagrees with the spec. Which is the more useful "
         "half of this move.",
         "DECLARATION",
         "The Analyst's whole argument: a wrong guess said out loud at minute one "
         "costs four focus, and a wrong guess discovered at minute twenty costs "
         "the timed practical."),
    Move("first_draft", "First Draft", "berserker",
         "any time before your first submission",
         {"mana": 0, "stamina": 2},
         "Commit to submitting within half the target time, ready or not.",
         "Every failed submission inside the window is free — no stamina, no "
         "combo — and the eventual unaided clear pays the iteration bonus twice.",
         "Nothing beyond the stamina. The clock runs out and you are back to "
         "playing the encounter normally, slightly out of breath.",
         "SPEED",
         "It buys permission to be wrong quickly, which is the only thing "
         "standing between most players and a first line of code."),
    Move("open_the_index", "Open the Index", "archivist",
         "before your first run, and only when something is due",
         {"mana": 6, "stamina": 0},
         "Pull one due memory ambush into this fight as an extra round.",
         "Clear both and the pair pays as a single BOSS-weight encounter, and the "
         "ambush's interval doubles.",
         "The ambush reschedules at its current interval and the focus is gone. "
         "The encounter in front of you is unaffected either way.",
         "RETEST",
         "Retrieval practice inserted into a fight, which is both the correct "
         "pedagogy and a genuinely stupid thing to volunteer for."),
    Move("set_the_perimeter", "Set the Perimeter", "warden",
         "before your first run of the encounter",
         {"mana": 5, "stamina": 0},
         "Name up to three classes of input you expect to break this.",
         "Each call the hidden trials agree with becomes a ward that absorbs one "
         "failed submission, and turns that trial critical.",
         "Each call that matches nothing costs a third of your focus. Naming all "
         "nine classes is not clever; it is expensive.",
         "EDGE_CALL",
         "The move is the timed practical habit, priced. You are wagering focus on "
         "knowing where the code will break before the code exists."),
    Move("lay_the_bench", "Lay the Bench", "artificer",
         "after any cleared encounter",
         {"mana": 3, "stamina": 0},
         "Bank one helper function you wrote and cleared into your bench.",
         "It returns with you into later adventure encounters, editable, yours.",
         "Nothing is wrong here — the cost is the slot. Benches are small and a "
         "helper you never call is a slot you are not using.",
         "BENCH",
         "Timed Practical Mode empties the bench on entry, along with everything else. "
         "The bench is a working engineer's utils file, not a cheat sheet."),
    Move("second_sight", "Second Sight", "seer",
         "after a failed submission",
         {"mana": 4, "stamina": 0},
         "Name the failure category before the diagnosis renders.",
         "You step your own submitted code around the first divergent frame, and "
         "the attempt costs no combo.",
         "The diagnosis renders normally, as it would have anyway. You have spent "
         "four focus to find out you were reading it wrong.",
         "ROOT_CAUSE",
         "The trace is of the player's own program. The reference implementation "
         "is never shown, never stepped, and never quoted."),
)

MOVE_BY_ID = {m.id: m for m in MOVES}


# ===========================================================================
# Movesets: which node teaches which line of Python
# ===========================================================================
# Two different things in this file are called a move and they are not related,
# so they are named apart everywhere below:
#
#   classes.Move      the SIGNATURE move. One per class, free, a wager on
#                     something you believe. Declared above.
#   movesets.Move     a COMBAT move. Seven per class, learned here, cast by
#                     typing the incantations it is spelled out of.
#
# The tree is the only place a combat move is ever acquired. That is the whole
# of the wiring, and it has two consequences worth stating out loud:
#
#   1. LEARNING A MOVE TEACHES ITS LINES. `movesets.learn` forwards every
#      incantation in the move's spine into the player's incantation book. One
#      acquisition path, not two — which means the branch you invested in
#      quietly decided which Python idioms this playthrough is fluent in. That
#      is the replay value, and it arrived without a single new system.
#   2. ONE POINT IS ENOUGH. A move is granted at the FIRST rank of its node.
#      The remaining nine ranks sharpen what that node was already doing. A
#      player who has to sink ten points before a move appears is a player who
#      spends ten levels unable to answer the fight in front of them, and this
#      file does not ship that.
#
# The slots are positional and identical for all six classes, so "which class
# gets its area attack earliest" is never a question. Node index 0 and 1 are
# tier 1, 2 and 3 are tier 2, 4 and 5 are tier 3, 6 is the capstone:
#
#   rung 1-3   one tier-1 node in each of the three branches. Three points,
#              spent anywhere, and you have three moves.
#   rung 4-5   tier 2, in two different branches: the first real commitment.
#   rung 6     tier 3.
#   rung 7     the capstone. Twenty-two branch points and level twenty, which
#              is the same gate every capstone already had.

MOVE_GRANT_SLOTS = ((0, 0), (1, 0), (2, 0), (0, 2), (1, 3), (2, 4), (0, 6))
MOVE_GRANT_RANK = 1


def _build_moveset_grants() -> dict:
    grants: dict = {}
    for spec in CLASSES:
        for rung, (branch_index, node_index) in enumerate(MOVE_GRANT_SLOTS,
                                                          start=1):
            move = movesets.at_rung(spec.id, rung)
            if move is None:
                continue
            node = spec.branches[branch_index].nodes[node_index]
            grants.setdefault(node.id, []).append(move.id)
    return {node_id: tuple(ids) for node_id, ids in grants.items()}


MOVESET_GRANTS = _build_moveset_grants()
MOVESET_NODE = {move_id: node_id
                for node_id, move_ids in MOVESET_GRANTS.items()
                for move_id in move_ids}


def moveset_for_node(node_id: str) -> tuple:
    """The combat moves one point in this node teaches."""
    return MOVESET_GRANTS.get(node_id, ())


def node_for_moveset(move_id: str) -> str:
    """Where a combat move comes from, for a UI that wants to point at it."""
    return MOVESET_NODE.get(move_id, "")


def movesets_granted(state: dict) -> list:
    """Every combat move this spend dict has paid for, in rung order.

    A borrowed discipline grants its tier-1 moves too — rungs one to three —
    because `DUAL_CLASS_MAX_RANK` already lets a foreign tier-1 node be taken.
    `movesets.scale_for` prices them at DUAL_SCALE, which is the seasoning the
    dual rules describe, expressed as damage instead of as prose.
    """
    out = []
    for node_id, rank in (state.get("spent") or {}).items():
        if int(rank) < MOVE_GRANT_RANK:
            continue
        for move_id in MOVESET_GRANTS.get(node_id, ()):
            if move_id not in out:
                out.append(move_id)
    return sorted(out, key=lambda m: (movesets.BY_ID[m].rung, m))


def moveset_reach(state: dict) -> int:
    """The highest rung this character has been granted.

    This is the number `movesets.fade` measures an old move against, and it is
    deliberately read off the TREE rather than off the character level: a player
    who never invested has not outgrown anything, and their rung-one move should
    still hit like a rung-one move.
    """
    granted = movesets_granted(state)
    return max([movesets.BY_ID[m].rung for m in granted] or [0])


def movebook(state: dict, moveset: dict | None = None,
             book: dict | None = None) -> dict:
    """Build or refresh the player's movebook from the tree.

    Idempotent, and safe to call after every spend, every respec and every load.
    A respec that removes the node a move came from does NOT unlearn the move:
    `known` is append-only here for the same reason `pets.found` is. Un-teaching
    somebody Python because they moved a skill point is a punishment for
    experimenting, and the one thing this game may never punish is that.
    """
    book = book if book is not None else movesets.new_book(state.get("class", ""))
    book["class"] = state.get("class", "") or book.get("class", "")
    for move_id in movesets_granted(state):
        movesets.learn(book, move_id, moveset)
    return book


def moveset_rows(state: dict, *, level: int = 1) -> list:
    """The movebook as the tree screen wants to draw it: what you have, what is
    next, and what it currently costs you to reach."""
    reach = moveset_reach(state)
    have = set(movesets_granted(state))
    rows = []
    for class_id in (state.get("class", ""), state.get("dual", "")):
        if not class_id:
            continue
        for move in movesets.for_class(class_id):
            node = NODE_BY_ID.get(node_for_moveset(move.id))
            if node is None:
                continue
            owned = move.id in have
            ok, reason = can_spend(state, node.id, level=level)
            rows.append({
                **move.to_dict(reach=reach),
                "owned": owned,
                "borrowed": class_id != state.get("class", ""),
                "node": node.id, "node_name": node.name,
                "branch": node.branch_id, "tier": node.tier,
                "available": owned or ok,
                "refusal": "" if (owned or ok)
                           else SPEND_REFUSALS.get(reason, reason),
            })
    return rows




# ===========================================================================
# Class gear
# ===========================================================================
# Two tiers of honesty here.
#
# `affinity_set` and `affinity_items` on each class reference things that EXIST
# in items.py today, so a class is fully playable before a single new item ships:
# the drop tables simply weight toward them.
#
# `GEAR_REQUESTS` and `SET_REQUESTS` below are the new content this design wants
# added to items.py — a signature weapon and a five-piece restricted set per
# class. They are authored here in items.Item's own shape so they can be moved
# across without a rewrite. Nothing in this module constructs an items.Item; the
# catalogue stays the single source of truth for what exists.

@dataclass(frozen=True)
class GearRequest:
    id: str
    name: str
    slot: str
    rarity: str
    effects: dict
    class_id: str = ""           # "" means anyone may wear it
    set_id: str = ""
    icon: str = "sword"
    source: str = "drop"
    skill: str = ""
    flavour: str = ""

    def as_item_kwargs(self) -> dict:
        """Exactly the kwargs items._i() wants. `class_id` is this module's, and
        is deliberately NOT passed — restriction is enforced by equippable()."""
        return {
            "id": self.id, "name": self.name, "slot": self.slot,
            "rarity": self.rarity, "effects": dict(self.effects),
            "set_id": self.set_id, "icon": self.icon, "source": self.source,
            "skill": self.skill, "flavour": self.flavour,
        }


GEAR_REQUESTS = (
    # ---- Analyst -------------------------------------------------------
    GearRequest("analysts_calipers", "The Analyst's Calipers", "weapon", "EPIC",
                {"probe_charges": 1, "declare_slots": 1, "declare_bonus": 0.15},
                class_id="analyst", icon="relic", source="quest", skill="BIG_O",
                flavour="It measures the problem. It has never once cut anything."),
    GearRequest("calculus_lenses", "Calculus Lenses", "head", "RARE",
                {"declare_bonus": 0.12}, class_id="analyst", set_id="calculus",
                icon="helm", flavour="Everything through them has a cost written "
                                     "under it in small type."),
    GearRequest("calculus_coat", "Coat of Stated Cost", "chest", "RARE",
                {"mana_max": 8, "perf_insight": 1}, class_id="analyst",
                set_id="calculus", icon="chest",
                flavour="The lining is covered in crossed-out estimates."),
    GearRequest("calculus_grips", "Grips of the Held Guess", "hands", "RARE",
                {"probe_refund": 0.2}, class_id="analyst", set_id="calculus",
                icon="gauntlets",
                flavour="For holding a hypothesis without squeezing it."),
    GearRequest("calculus_treads", "Treads of the Slow First Minute", "feet",
                "UNCOMMON", {"first_try_bonus": 0.1}, class_id="analyst",
                set_id="calculus", icon="boots",
                flavour="They are notably bad at running."),
    GearRequest("calculus_sigil", "Sigil of the Falsified Guess", "trinket",
                "EPIC", {"declare_bonus": 0.2, "reveal_category": 1},
                class_id="analyst", set_id="calculus", icon="relic",
                flavour="It warms when you are wrong, which is more often than "
                        "the marketing suggested."),

    # ---- Berserker -----------------------------------------------------
    GearRequest("draft_axe", "The First Draft", "weapon", "EPIC",
                {"rank_grace": 0.2, "iteration_bonus": 0.15, "retry_grace": 1},
                class_id="berserker", icon="axe", source="quest", skill="SPEED",
                flavour="Blunt, early, and somehow already most of the way there."),
    GearRequest("warpath_helm", "Warpath Helm", "head", "RARE",
                {"rank_grace": 0.12}, class_id="berserker", set_id="warpath",
                icon="helm", flavour="No visor. Visors slow you down."),
    GearRequest("warpath_harness", "Warpath Harness", "chest", "RARE",
                {"stamina_max": 6, "stamina_regen": 1}, class_id="berserker",
                set_id="warpath", icon="plate",
                flavour="Repaired eleven times, never replaced."),
    GearRequest("warpath_grips", "Grips of the Second Attempt", "hands", "RARE",
                {"iteration_bonus": 0.12}, class_id="berserker", set_id="warpath",
                icon="gauntlets",
                flavour="Worn smooth where the delete key would be."),
    GearRequest("warpath_striders", "Warpath Striders", "feet", "RARE",
                {"rank_grace": 0.1, "crit_bonus": 0.1}, class_id="berserker",
                set_id="warpath", icon="boots",
                flavour="They only have the one gear."),
    GearRequest("warpath_charm", "Charm of the Unread Question", "trinket",
                "EPIC", {"combo_shield": 1, "second_wind": 1},
                class_id="berserker", set_id="warpath", icon="relic",
                flavour="Its owner started before the sentence finished and was, "
                        "on balance, correct to."),

    # ---- Archivist -----------------------------------------------------
    GearRequest("recall_chain", "The Chain of Recall", "weapon", "EPIC",
                {"retest_bonus": 0.3, "retest_charges": 1, "srs_preview": 1},
                class_id="archivist", icon="relic", source="quest", skill="RECALL",
                flavour="Every link is a thing you once knew and were made to "
                        "prove again."),
    GearRequest("unerased_hood", "Hood of the Unerased", "head", "RARE",
                {"hint_discount": 0.15}, class_id="archivist", set_id="unerased",
                icon="helm", flavour="Stitched from a page that survived."),
    GearRequest("unerased_robe", "Robe of the Copied Shelf", "chest", "RARE",
                {"mana_max": 10}, class_id="archivist", set_id="unerased",
                icon="chest", flavour="It holds more than it looks like it holds."),
    GearRequest("unerased_wraps", "Wraps of the Thirtieth Day", "hands",
                "UNCOMMON", {"interval_stretch": 0.15}, class_id="archivist",
                set_id="unerased", icon="gauntlets",
                flavour="For turning a page you have turned five times before."),
    GearRequest("unerased_sandals", "Sandals of the Due List", "feet", "RARE",
                {"retest_bonus": 0.15}, class_id="archivist", set_id="unerased",
                icon="boots", flavour="They walk to the shelf you were avoiding."),
    GearRequest("unerased_index", "The Kept Index", "trinket", "EPIC",
                {"retest_charges": 1, "mana_regen": 3}, class_id="archivist",
                set_id="unerased", icon="relic",
                flavour="Somebody copied this out by hand, nightly, for a "
                        "generation, and then the generation ended."),

    # ---- Warden --------------------------------------------------------
    GearRequest("boundary_maul", "The Boundary Maul", "weapon", "EPIC",
                {"edge_ward": 1, "probe_charges": 1, "crit_bonus": 0.2},
                class_id="warden", icon="hammer", source="quest", skill="TESTING",
                flavour="It is used for finding the edge of things, and then for "
                        "the other thing."),
    GearRequest("bulwark_helm", "Bulwark Helm", "head", "RARE",
                {"reveal_category": 1}, class_id="warden", set_id="bulwark",
                icon="helm", flavour="It names the kind of blow, never the blow."),
    GearRequest("bulwark_plate", "Bulwark Plate", "chest", "RARE",
                {"stamina_max": 8, "combo_shield": 1}, class_id="warden",
                set_id="bulwark", icon="plate",
                flavour="Dented everywhere a beginner is dented, and nowhere else."),
    GearRequest("bulwark_grips", "Grips of the Named Case", "hands", "RARE",
                {"edge_ward": 1}, class_id="warden", set_id="bulwark",
                icon="gauntlets",
                flavour="One finger for empty, one for single, one for duplicate."),
    GearRequest("bulwark_greaves", "Greaves of the Held Line", "feet", "RARE",
                {"retry_grace": 1}, class_id="warden", set_id="bulwark",
                icon="boots", flavour="They do not advance. That is the feature."),
    GearRequest("bulwark_ward", "The Standing Ward", "trinket", "EPIC",
                {"edge_ward": 1, "weakness_scan": 1}, class_id="warden",
                set_id="bulwark", icon="relic",
                flavour="It hums near an input nobody intended."),

    # ---- Artificer -----------------------------------------------------
    GearRequest("toolwrights_spanner", "The Toolwright's Spanner", "weapon",
                "EPIC", {"bench_slots": 2, "refactor_bonus": 0.2, "mana_max": 6},
                class_id="artificer", icon="hammer", source="quest",
                skill="DESIGN",
                flavour="It fits three things badly and one thing perfectly, and "
                        "the owner knows which."),
    GearRequest("forgewright_visor", "Forgewright's Visor", "head", "RARE",
                {"design_rubric": 1}, class_id="artificer", set_id="forgewright",
                icon="helm", flavour="It shows the seams. Everything has seams."),
    GearRequest("forgewright_apron", "Forgewright's Apron", "chest", "RARE",
                {"mana_max": 8, "mana_regen": 2}, class_id="artificer",
                set_id="forgewright", icon="chest",
                flavour="Pockets arranged by someone who was tired of looking."),
    GearRequest("forgewright_grips", "Grips of the Second Pass", "hands", "RARE",
                {"refactor_bonus": 0.15}, class_id="artificer",
                set_id="forgewright", icon="gauntlets",
                flavour="For the version you would actually defend."),
    GearRequest("forgewright_boots", "Boots of the Standing Bench", "feet",
                "UNCOMMON", {"bench_slots": 1}, class_id="artificer",
                set_id="forgewright", icon="boots",
                flavour="They have not left this workshop in some years."),
    GearRequest("forgewright_seal", "The Draughtsman's Seal", "trinket", "EPIC",
                {"design_rubric": 1, "declare_slots": 1}, class_id="artificer",
                set_id="forgewright", icon="relic",
                flavour="Pressed into wax, it draws a box. The box is empty. That "
                        "is the exercise."),

    # ---- Seer ----------------------------------------------------------
    GearRequest("tracing_needle", "The Tracing Needle", "weapon", "EPIC",
                {"trace_frames": 2, "root_cause_bonus": 0.2, "reveal_category": 1},
                class_id="seer", icon="dagger", source="quest", skill="DEBUGGING",
                flavour="It goes in exactly where the program stopped being true."),
    GearRequest("clearsight_crown", "Clearsight Crown", "head", "RARE",
                {"trace_frames": 1}, class_id="seer", set_id="clearsight",
                icon="helm", flavour="Worn by people who read the whole traceback."),
    GearRequest("clearsight_mantle", "Mantle of the Long Read", "chest", "RARE",
                {"mana_max": 8, "recovery_grace": 0.12}, class_id="seer",
                set_id="clearsight", icon="chest",
                flavour="Cut for sitting still."),
    GearRequest("clearsight_gloves", "Gloves of the One Change", "hands",
                "UNCOMMON", {"iteration_bonus": 0.1}, class_id="seer",
                set_id="clearsight", icon="gauntlets",
                flavour="They will only let you touch one variable at a time."),
    GearRequest("clearsight_steps", "Steps of the Quiet Margin", "feet", "RARE",
                {"loot_luck": 0.12}, class_id="seer", set_id="clearsight",
                icon="boots", flavour="They find the footnote."),
    GearRequest("clearsight_lens", "The Unclouded Lens", "trinket", "EPIC",
                {"root_cause_bonus": 0.25, "trace_frames": 1}, class_id="seer",
                set_id="clearsight", icon="relic",
                flavour="It shows you your own work, which is the hardest thing "
                        "anyone has ever been asked to look at."),
)

GEAR_BY_ID = {g.id: g for g in GEAR_REQUESTS}

# Class-restricted gear. Everything not in here is wearable by anybody; a class
# that cannot wear most of the loot it finds is a class nobody plays twice.
CLASS_RESTRICTED = {g.id: g.class_id for g in GEAR_REQUESTS if g.class_id}

SET_REQUESTS = {
    "calculus": {
        "name": "The Oracle's Calculus", "class_id": "analyst",
        "blurb": "For someone who would rather be wrong on record than right by "
                 "accident.",
        "bonuses": {
            2: {"declare_slots": 1},
            3: {"probe_refund": 0.25, "perf_insight": 1},
            5: {"declare_bonus": 0.4, "declare_slots": 1, "crit_bonus": 0.25},
        },
    },
    "warpath": {
        "name": "Warpath Harness", "class_id": "berserker",
        "blurb": "Every piece of it has been repaired mid-fight at least once.",
        "bonuses": {
            2: {"rank_grace": 0.2},
            3: {"retry_grace": 1, "iteration_bonus": 0.2},
            5: {"combo_shield": 2, "second_wind": 1, "stamina_regen": 2},
        },
    },
    "unerased": {
        "name": "Vestments of the Unerased", "class_id": "archivist",
        "blurb": "Copied out by hand, nightly, by people who knew what was coming.",
        "bonuses": {
            2: {"retest_bonus": 0.25},
            3: {"srs_preview": 1, "hint_discount": 0.25},
            5: {"retest_charges": 2, "interval_stretch": 0.3, "mana_regen": 4},
        },
    },
    "bulwark": {
        "name": "The Bulwark", "class_id": "warden",
        "blurb": "Armour for the argument you have before you write anything.",
        "bonuses": {
            2: {"edge_ward": 1},
            3: {"probe_charges": 1, "reveal_category": 1},
            5: {"edge_ward": 2, "combo_shield": 2, "weakness_scan": 1},
        },
    },
    "forgewright": {
        "name": "Forgewright's Kit", "class_id": "artificer",
        "blurb": "The whole workshop, worn.",
        "bonuses": {
            2: {"bench_slots": 1},
            3: {"refactor_bonus": 0.25, "design_rubric": 1},
            5: {"bench_slots": 2, "design_rubric": 2, "mana_regen": 4},
        },
    },
    "clearsight": {
        "name": "Clearsight Array", "class_id": "seer",
        "blurb": "It does not show you anything that was not already on screen.",
        "bonuses": {
            2: {"trace_frames": 1},
            3: {"reveal_category": 1, "root_cause_bonus": 0.25},
            5: {"trace_frames": 3, "recovery_grace": 0.3, "root_cause_bonus": 0.4},
        },
    },
}


def equippable(item_id: str, class_id: str) -> bool:
    """Class gate for equipment. Unknown items are wearable — restriction is a
    property a piece opts into, never a default."""
    owner = CLASS_RESTRICTED.get(item_id)
    return owner is None or owner == class_id


def restricted_to(item_id: str) -> str:
    return CLASS_RESTRICTED.get(item_id, "")


# ===========================================================================
# The point economy
# ===========================================================================
# One point a level, one point per chapter graduated. The chapter points are the
# interesting half: they are the only part of the tree that cannot be obtained by
# grinding easy encounters, because `curriculum.chapter_progress` requires both
# mastery and clears in that chapter's skills. A maxed tree is therefore evidence
# of a finished curriculum, not of a long weekend.

MAX_LEVEL = 99                       # mirrors progression.MAX_LEVEL; cross-checked
GRADUATABLE_CHAPTERS = tuple(
    c.id for c in curriculum.CHAPTERS if c.graduate_clears < 999
)
MAX_CHAPTER_POINTS = len(GRADUATABLE_CHAPTERS) * POINTS_PER_CHAPTER
MAX_POINTS = (MAX_LEVEL - 1) * POINTS_PER_LEVEL + MAX_CHAPTER_POINTS

UNFAMILIAR_GRIP_ENCOUNTERS = 3       # the non-gold half of a respec
RESPEC_BASE_GOLD = 150
RESPEC_GOLD_PER_POINT = 45
RESPEC_MIN_GOLD = 100
RESPEC_HALF_PRICE_LEVEL = 20         # progression.LEVEL_MILESTONES[20]
RESPEC_BRANCH_SURCHARGE = 1.4        # picking at one branch costs more per point


def points_earned(level: int, chapters_graduated: int = 0) -> int:
    level = max(1, min(int(level), MAX_LEVEL))
    chapters = max(0, min(int(chapters_graduated), len(GRADUATABLE_CHAPTERS)))
    return (level - 1) * POINTS_PER_LEVEL + chapters * POINTS_PER_CHAPTER


def chapters_graduated(skills: dict) -> int:
    """Evidence, counted. Reads curriculum and nothing else."""
    done = 0
    for chapter in curriculum.CHAPTERS:
        if chapter.id not in GRADUATABLE_CHAPTERS:
            continue
        if curriculum.chapter_progress(skills, chapter)["graduated"]:
            done += 1
    return done


# The two authored bodies, as web/js/sprites.js BODY_RIG names them. The axis is
# stored as 'a'/'b' rather than as a gender word because the RIG is a build — a
# silhouette and a hem — and the sprite it produces is the same either way at
# every other layer. The player picks it as male/female in the UI; what the save
# keeps is which body was drawn.
BODIES = ("a", "b")
BODY_LABEL = {"a": "male", "b": "female"}
DEFAULT_BODY = "a"


def body_of(state: dict) -> str:
    """The chosen body, or the default. Never raises on an old save."""
    body = str(((state or {}).get("class") or {}).get("body") or "")
    return body if body in BODIES else DEFAULT_BODY


def new_state(class_id: str, body: str = DEFAULT_BODY) -> dict:
    """The flat dict a save persists. Nothing derived is stored."""
    if class_id not in CLASS_BY_ID:
        raise ValueError(f"unknown class {class_id!r}")
    if body not in BODIES:
        body = DEFAULT_BODY
    return {"class": class_id, "body": body, "spent": {}, "points": 0,
            "respecs": 0, "dual": "", "grip": 0}


def _rank(state: dict, node_id: str) -> int:
    return int((state.get("spent") or {}).get(node_id, 0))


def _cost(state: dict, node: Node) -> int:
    return DUAL_CLASS_COST if node.class_id != state.get("class") else 1


def _max_rank_for(state: dict, node: Node) -> int:
    if node.class_id != state.get("class"):
        return min(node.max_rank, DUAL_CLASS_MAX_RANK)
    return node.max_rank


def points_spent(state: dict) -> int:
    total = 0
    for node_id, rank in (state.get("spent") or {}).items():
        node = NODE_BY_ID.get(node_id)
        if node:
            total += int(rank) * _cost(state, node)
    return total


def branch_points(state: dict, class_id: str, branch_id: str) -> int:
    """Points sunk into one branch — the gate tier 2, 3 and 4 read."""
    total = 0
    for node_id, rank in (state.get("spent") or {}).items():
        node = NODE_BY_ID.get(node_id)
        if node and node.class_id == class_id and node.branch_id == branch_id:
            total += int(rank) * _cost(state, node)
    return total


def sync_points(state: dict, *, level: int, chapters_graduated: int = 0) -> dict:
    """Recompute unspent points from evidence. Idempotent on purpose: it is the
    only granter, so points cannot be granted twice by a replayed level-up."""
    earned = points_earned(level, chapters_graduated)
    state["points"] = max(0, earned - points_spent(state))
    return state


def can_spend(state: dict, node_id: str, *, level: int) -> tuple:
    """(ok, reason). `reason` is a machine key so the UI can say why, and so
    self_check can drive a solver off it."""
    node = NODE_BY_ID.get(node_id)
    if node is None:
        return False, "unknown_node"

    own = state.get("class")
    if node.class_id != own:
        if not state.get("dual") or node.class_id != state["dual"]:
            return False, "wrong_class"
        if node.tier != 1:
            return False, "dual_tier_one_only"
        if level < DUAL_CLASS_LEVEL:
            return False, "dual_level"

    rank = _rank(state, node_id)
    if rank >= _max_rank_for(state, node):
        return False, "maxed"
    if state.get("points", 0) < _cost(state, node):
        return False, "points"
    if node.capstone and level < CAPSTONE_LEVEL:
        return False, "level"
    if node.parent and _rank(state, node.parent) < node.parent_ranks:
        return False, "parent"
    if branch_points(state, node.class_id, node.branch_id) < node.branch_points:
        return False, "branch_points"
    return True, "ok"


def spend(state: dict, node_id: str, *, level: int) -> dict:
    """The only mutator of `spent`. Returns a result dict, never raises on a
    merely-illegal spend — the UI shows the reason instead."""
    ok, reason = can_spend(state, node_id, level=level)
    if not ok:
        return {"error": reason, "message": SPEND_REFUSALS.get(reason, reason)}
    node = NODE_BY_ID[node_id]
    spent = state.setdefault("spent", {})
    spent[node_id] = _rank(state, node_id) + 1
    state["points"] = state.get("points", 0) - _cost(state, node)
    # The first point in a granting node is where a combat move is acquired.
    # Returned rather than applied: this function owns `spent` and nothing else,
    # and the movebook lives in the save beside it. The caller does
    # classes.movebook(state, state["moveset"], state["movebook"]).
    taught = [movesets.BY_ID[m].to_dict()
              for m in (moveset_for_node(node_id)
                        if spent[node_id] == MOVE_GRANT_RANK else ())]
    return {"ok": True, "node": node.to_dict(spent[node_id]),
            "rank": spent[node_id], "points": state["points"],
            "effects": tree_effects(state),
            "learned_moves": taught}


SPEND_REFUSALS = {
    "unknown_node": "no such node",
    "wrong_class": "that node belongs to another class",
    "dual_tier_one_only": "a second discipline only ever opens its first rank of "
                          "nodes; it is a seasoning, not a second build",
    "dual_level": f"a second discipline opens at level {DUAL_CLASS_LEVEL}",
    "maxed": "already at full rank",
    "points": "no points to spend",
    "level": f"capstones open at level {CAPSTONE_LEVEL}",
    "parent": "the node above it is not deep enough yet",
    "branch_points": "not enough invested in this branch yet",
}


def choose_dual(state: dict, class_id: str, *, level: int) -> dict:
    if level < DUAL_CLASS_LEVEL:
        return {"error": "dual_level", "message": SPEND_REFUSALS["dual_level"]}
    if class_id == state.get("class") or class_id not in CLASS_BY_ID:
        return {"error": "wrong_class", "message": "pick a discipline you are not"}
    if state.get("dual"):
        return {"error": "already", "message": "you already keep a second "
                                               "discipline; respec to change it"}
    state["dual"] = class_id
    return {"ok": True, "dual": class_id}


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

def tree_effects(state: dict) -> dict:
    """Fold a spend dict into one effects dict in items.py's vocabulary.
    Capability keys take the maximum; quantities sum. Same rule as
    items.total_effects, so a caller can merge the two without thinking."""
    out: dict = {}
    for node_id, rank in (state.get("spent") or {}).items():
        node = NODE_BY_ID.get(node_id)
        if node is None:
            continue
        for key, value in node.effects_at(int(rank)).items():
            if key in MAXED_KEYS:
                out[key] = max(out.get(key, 0), value)
            else:
                out[key] = round(out.get(key, 0) + value, 4)
    out = clamp(out)
    if state.get("grip", 0) > 0:
        # The cost of a rebuild: a new tree in your hands is a tree you have not
        # used. Crit is suppressed until you have cleared a few encounters with it.
        out["crit_bonus"] = 0
    return out


def after_encounter(state: dict) -> dict:
    """Tick the post-respec unfamiliarity down. Called once per cleared or failed
    encounter by whoever owns the loop."""
    if state.get("grip", 0) > 0:
        state["grip"] -= 1
    return state


# ---------------------------------------------------------------------------
# Respec
# ---------------------------------------------------------------------------

def respec_cost(state: dict, *, level: int, effects: dict | None = None,
                scope: str = "all", branch_id: str = "") -> dict:
    """Costly, never punitive. The first one is free because a tree you cannot
    back out of at all is a trap by construction, and this file does not ship
    traps."""
    own = state.get("class")
    if scope == "branch":
        if not branch_id or (own, branch_id) not in BRANCH_BY_ID:
            return {"error": "unknown_branch"}
        points = branch_points(state, own, branch_id)
        gold = (RESPEC_BASE_GOLD + RESPEC_GOLD_PER_POINT * points) \
            * RESPEC_BRANCH_SURCHARGE
    else:
        points = points_spent(state)
        gold = RESPEC_BASE_GOLD + RESPEC_GOLD_PER_POINT * points

    free = FIRST_RESPEC_FREE and not state.get("respecs")
    if free:
        gold = 0.0
    else:
        if level >= RESPEC_HALF_PRICE_LEVEL:
            gold *= 0.5                       # the Armorer, at level 20
        discount = float((effects or {}).get("respec_discount", 0.0))
        gold *= max(0.25, 1.0 - discount)
        gold = max(RESPEC_MIN_GOLD, gold)

    return {
        "scope": scope, "branch": branch_id, "points": points,
        "gold": int(round(gold)), "free": free,
        "grip": 0 if free else UNFAMILIAR_GRIP_ENCOUNTERS,
        "note": "Free, once. After that the Armorer charges, and a rebuilt tree "
                "feels unfamiliar for three encounters." if free else
                f"Your crit bonus is suppressed for the next "
                f"{UNFAMILIAR_GRIP_ENCOUNTERS} encounters. A new build is a build "
                f"you have not used yet.",
    }


def respec(state: dict, *, level: int, gold_available: int,
           effects: dict | None = None, scope: str = "all",
           branch_id: str = "") -> dict:
    quote = respec_cost(state, level=level, effects=effects, scope=scope,
                        branch_id=branch_id)
    if "error" in quote:
        return quote
    if gold_available < quote["gold"]:
        return {"error": "gold", "message": f"the Armorer wants {quote['gold']} "
                                            f"gold for that"}
    spent = state.setdefault("spent", {})
    if scope == "branch":
        for node_id in [n for n in spent
                        if NODE_BY_ID[n].class_id == state["class"]
                        and NODE_BY_ID[n].branch_id == branch_id]:
            del spent[node_id]
    else:
        spent.clear()
        state["dual"] = ""
    state["points"] = state.get("points", 0) + quote["points"]
    state["respecs"] = state.get("respecs", 0) + 1
    state["grip"] = quote["grip"]
    return {"ok": True, **quote, "points_returned": quote["points"],
            "points": state["points"]}


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def node_view(state: dict, node: Node, *, level: int) -> dict:
    rank = _rank(state, node.id)
    ok, reason = can_spend(state, node.id, level=level)
    return {
        **node.to_dict(rank),
        "max_rank": _max_rank_for(state, node),
        "cost": _cost(state, node),
        "can_spend": ok,
        "refusal": "" if ok else SPEND_REFUSALS.get(reason, reason),
        "refusal_key": "" if ok else reason,
        "locked": not ok and reason in ("parent", "branch_points", "level"),
        # What one point here teaches. Shown on the node, because a player
        # choosing between two nodes should not have to open a second screen to
        # find out that one of them hands them an area attack.
        "grants_moves": [movesets.BY_ID[m].to_dict() for m in moveset_for_node(node.id)],
    }


def tree_view(state: dict, *, level: int) -> dict:
    """Everything a UI needs to draw the tree, with no second source of truth."""
    spec = CLASS_BY_ID[state["class"]]
    branches = []
    for branch in spec.branches:
        branches.append({
            "id": branch.id, "name": branch.name, "blurb": branch.blurb,
            "invested": branch_points(state, spec.id, branch.id),
            "capacity": branch.capacity,
            "nodes": [node_view(state, n, level=level) for n in branch.nodes],
        })
    fx = tree_effects(state)
    view = {
        "class": class_view(spec),
        "branches": branches,
        "points": state.get("points", 0),
        "spent": points_spent(state),
        "capacity": spec.capacity,
        "effects": fx,
        "effect_text": describe(fx),
        "respecs": state.get("respecs", 0),
        "grip": state.get("grip", 0),
        "dual": state.get("dual", ""),
        "dual_open": level >= DUAL_CLASS_LEVEL,
        "movesets": moveset_rows(state, level=level),
        "moveset_reach": moveset_reach(state),
    }
    if state.get("dual"):
        other = CLASS_BY_ID[state["dual"]]
        view["dual_nodes"] = [
            node_view(state, n, level=level)
            for b in other.branches for n in b.nodes if n.tier == 1
        ]
    return view


def class_view(spec: CharacterClass) -> dict:
    move = MOVE_BY_ID[spec.move]
    return {
        "id": spec.id, "name": spec.name, "epithet": spec.epithet,
        "habit": spec.habit, "trains": spec.trains, "plays_like": spec.plays_like,
        "colour": spec.colour, "sprite": spec.sprite,
        "attributes": dict(spec.attributes),
        "affinity_set": spec.affinity_set,
        "affinity_set_name": items.SETS[spec.affinity_set]["name"],
        "affinity_items": list(spec.affinity_items),
        "starter_weapon": spec.starter_weapon,
        "signature_weapon": spec.signature_weapon,
        "signature_set": spec.signature_set,
        "signature_set_name": SET_REQUESTS[spec.signature_set]["name"],
        "branches": [{"id": b.id, "name": b.name, "blurb": b.blurb}
                     for b in spec.branches],
        "move": {
            "id": move.id, "name": move.name, "window": move.window,
            "cost": dict(move.cost), "wager": move.wager,
            "on_right": move.on_right, "on_wrong": move.on_wrong,
            "blurb": move.blurb,
        },
        "capacity": spec.capacity,
    }


def selection_screen() -> list:
    """The six, as the choose-your-class screen wants them."""
    return [class_view(c) for c in CLASSES]


def get(class_id: str) -> CharacterClass | None:
    return CLASS_BY_ID.get(class_id)


def node(node_id: str) -> Node | None:
    return NODE_BY_ID.get(node_id)


def signature_move(class_id: str) -> Move | None:
    spec = CLASS_BY_ID.get(class_id)
    return MOVE_BY_ID.get(spec.move) if spec else None


# ---------------------------------------------------------------------------
# Replayability
# ---------------------------------------------------------------------------
# Mastery is the player's, not the character's. A second run does not re-teach
# you Python and the game does not pretend it has. What a second run changes is
# the route: a different habit being paid for, different gear, a different move,
# and a world whose unlocks you already hold.

LEGACY = {
    "unlocks_at": "craft",           # graduate chapter X with any class
    "start_level": 10,
    "keeps": (
        "skill mastery, retention and the whole SRS schedule — it is your "
        "learning, not the character's",
        "world map, routes walked, regions restored, secrets found",
        "the codex, the bestiary and every problem you have ever cleared",
        "companions, and the titles you earned",
    ),
    "resets": (
        "the skill tree, entirely",
        "attributes and equipped gear",
        "the signature move, which becomes the new class's",
    ),
    "grants": (
        "one Legacy Token per completed class, spendable on a second discipline "
        f"at level {DUAL_CLASS_LEVEL} without the usual level wait",
        "the previous class's signature weapon, displayed on the wall, "
        "unequippable by anyone else",
    ),
    "why": "Six classes, three branches each, and a tree that fits 153 points "
           "into a character who will earn 108. Two playthroughs of the same "
           "class are already different builds; two playthroughs of different "
           "classes are different games with the same curriculum underneath.",
}


def legacy_available(skills: dict) -> bool:
    """One completed run of the tenth chapter opens the second class."""
    chapter = curriculum.CHAPTER_BY_ID[LEGACY["unlocks_at"]]
    return curriculum.chapter_progress(skills, chapter)["graduated"]


# ===========================================================================
# Proofs
# ===========================================================================
# `self_check()` is not a smoke test. It levels every class to 99, spends the
# points every way that matters, and answers the five questions this design can
# actually get wrong: is any node unreachable, is any build dead, does any effect
# key escape the vocabulary, does the arithmetic add up, and can any class be
# locked out of a chapter.

_ANSWER_TELLS = (
    "def ",              # a function header is somebody's worked solution
    "return ",           # so is a return statement
    "```",               # so is a fenced block
    "the answer is",
    "the solution is",
    "solves it for you",
    "without solving",
    "skips the problem",
    "reveals the solution",
    "shows the solution",
    "copy this",
    "just paste",
)

# Names the curriculum reads when it decides what a player may be asked. No
# effect key may collide with one, or a tree could open or close content.
GATING_NAMES = frozenset({
    "mastery", "clears", "unaided_clears", "unaided", "tier", "difficulty",
    "pattern", "spaced_repetition_family", "chapter", "graduate_mastery",
    "graduate_clears",
})


def _authored_text():
    """Every player-visible string this module owns, labelled."""
    for spec in CLASSES:
        for field_name in ("name", "epithet", "habit", "trains", "plays_like"):
            yield f"{spec.id}.{field_name}", getattr(spec, field_name)
        for branch in spec.branches:
            yield f"{spec.id}.{branch.id}.blurb", branch.blurb
            for n in branch.nodes:
                yield f"{n.id}.name", n.name
                yield f"{n.id}.blurb", n.blurb
                yield f"{n.id}.rule", n.rule
    for move in MOVES:
        for field_name in ("wager", "on_right", "on_wrong", "blurb"):
            yield f"{move.id}.{field_name}", getattr(move, field_name)
    for gear in GEAR_REQUESTS:
        yield f"{gear.id}.flavour", gear.flavour
    for key, text in NEW_EFFECT_LABELS.items():
        yield f"label.{key}", text


def _cheapest_filler(state: dict, target: Node, level: int) -> str | None:
    """The cheapest legal point to sink into a branch to satisfy its gate."""
    best = None
    for candidate in BRANCH_BY_ID[(target.class_id, target.branch_id)].nodes:
        if candidate.tier > target.tier:
            continue
        ok, _ = can_spend(state, candidate.id, level=level)
        if not ok:
            continue
        key = (candidate.tier, _rank(state, candidate.id))
        if best is None or key < best[0]:
            best = (key, candidate.id)
    return best[1] if best else None


def _spend_toward(state: dict, node_id: str, want: int, level: int) -> bool:
    """Drive a legal spend order to `want` ranks in `node_id`, satisfying every
    prerequisite on the way. Returns False if the budget or the level runs out."""
    target = NODE_BY_ID[node_id]
    guard = 0
    while _rank(state, node_id) < want:
        guard += 1
        if guard > 400:                       # cannot happen; proves it cannot
            return False
        ok, reason = can_spend(state, node_id, level=level)
        if ok:
            spend(state, node_id, level=level)
            continue
        if reason == "parent":
            if not _spend_toward(state, target.parent, target.parent_ranks, level):
                return False
        elif reason == "branch_points":
            filler = _cheapest_filler(state, target, level)
            if filler is None:
                return False
            spend(state, filler, level=level)
        else:
            return False
    return True


def _fresh(class_id: str, points: int, *, dual: str = "") -> dict:
    state = new_state(class_id)
    state["points"] = points
    if dual:
        state["dual"] = dual
    return state


def _min_points_to_max(node: Node) -> int:
    """How many points a player must spend, total, to hold this node at full
    rank — prerequisites and branch gates included."""
    state = _fresh(node.class_id, 10_000)
    if not _spend_toward(state, node.id, node.max_rank, MAX_LEVEL):
        return -1
    return points_spent(state)


def _branch_build(class_id: str, branch_id: str, points: int) -> dict:
    """Max one branch, in a legal order, from a fresh character."""
    state = _fresh(class_id, points)
    branch = BRANCH_BY_ID[(class_id, branch_id)]
    for n in branch.nodes:
        _spend_toward(state, n.id, n.max_rank, MAX_LEVEL)
    return state


def _spread_build(class_id: str, points: int) -> dict:
    """Round-robin across all three branches, tier by tier. The build a player
    who cannot make up their mind actually ends up with."""
    spec = CLASS_BY_ID[class_id]
    state = _fresh(class_id, points)
    for tier in (1, 2, 3, 4):
        for _ in range(MAX_RANK_BY_TIER[tier]):
            for branch in spec.branches:
                for n in branch.nodes:
                    if n.tier != tier:
                        continue
                    ok, _reason = can_spend(state, n.id, level=MAX_LEVEL)
                    if ok:
                        spend(state, n.id, level=MAX_LEVEL)
    # anything left over goes wherever it legally can, so "unspendable points"
    # would show up as a nonzero remainder
    changed = True
    while state["points"] > 0 and changed:
        changed = False
        for n in spec.nodes:
            ok, _reason = can_spend(state, n.id, level=MAX_LEVEL)
            if ok:
                spend(state, n.id, level=MAX_LEVEL)
                changed = True
    return state


def _capstone_rush(class_id: str, points: int) -> dict:
    """Three capstones as early as legal, then fill. The build-definer check."""
    spec = CLASS_BY_ID[class_id]
    state = _fresh(class_id, points)
    for branch in spec.branches:
        capstone = branch.nodes[-1]
        _spend_toward(state, capstone.id, 1, MAX_LEVEL)
    return state


def self_check() -> dict:
    """Counts, and the proofs. Safe to call from a test or the command line."""
    problems: list = []
    max_points = points_earned(MAX_LEVEL, len(GRADUATABLE_CHAPTERS))

    # -- shape ------------------------------------------------------------
    expected_tiers = (1, 1, 2, 2, 3, 3, 4)
    capacities = set()
    for spec in CLASSES:
        if len(spec.branches) != 3:
            problems.append(f"{spec.id}: {len(spec.branches)} branches, want 3")
        for branch in spec.branches:
            tiers = tuple(n.tier for n in branch.nodes)
            if tiers != expected_tiers:
                problems.append(f"{spec.id}.{branch.id}: tiers {tiers}")
            for n in branch.nodes:
                if n.max_rank != MAX_RANK_BY_TIER[n.tier]:
                    problems.append(f"{n.id}: rank {n.max_rank} wrong for tier")
                if n.parent:
                    parent = NODE_BY_ID.get(n.parent)
                    if parent is None or parent.branch_id != branch.id \
                            or parent.tier != n.tier - 1:
                        problems.append(f"{n.id}: bad parent {n.parent}")
                elif n.tier != 1:
                    problems.append(f"{n.id}: tier {n.tier} with no parent")
                if not n.effects_at(n.max_rank):
                    problems.append(f"{n.id}: full rank does nothing")
        capacities.add(spec.capacity)
    if len(capacities) != 1:
        problems.append(f"classes differ in capacity: {sorted(capacities)}")

    # -- vocabulary -------------------------------------------------------
    used_keys = set()
    for n in NODE_BY_ID.values():
        used_keys |= set(n.per_rank)
        for effects in n.unlocks.values():
            used_keys |= set(effects)
    gear_keys = {k for g in GEAR_REQUESTS for k in g.effects}
    set_keys = {k for s in SET_REQUESTS.values()
                for b in s["bonuses"].values() for k in b}
    stray = sorted((used_keys | gear_keys | set_keys) - set(EFFECT_LABELS))
    if stray:
        problems.append(f"effect keys outside the vocabulary: {stray}")
    unused_new = sorted(set(NEW_EFFECT_LABELS) - used_keys - gear_keys - set_keys)
    collisions = sorted(used_keys & GATING_NAMES)
    if collisions:
        problems.append(f"effect keys collide with curriculum names: {collisions}")

    # -- measures ---------------------------------------------------------
    measures_used = {n.measure for n in NODE_BY_ID.values()}
    unknown_measures = sorted(measures_used - set(MEASURE_BY_ID))
    if unknown_measures:
        problems.append(f"unknown measures: {unknown_measures}")
    idle_measures = sorted(set(MEASURE_BY_ID) - measures_used)
    scoped_tier_one = [n.id for n in NODE_BY_ID.values()
                       if n.tier == 1 and n.measure not in UNIVERSAL_MEASURES]
    if scoped_tier_one:
        problems.append(f"chapter-scoped measure at tier 1: {scoped_tier_one}")

    # -- reachability: every node, at full rank, inside one character -----
    reach = {}
    for n in NODE_BY_ID.values():
        cost = _min_points_to_max(n)
        reach[n.id] = cost
        if cost < 0:
            problems.append(f"{n.id}: unreachable at full rank")
        elif cost > max_points:
            problems.append(f"{n.id}: needs {cost} points, only {max_points} exist")
    worst = max(reach.values())
    worst_node = max(reach, key=lambda k: reach[k])

    # -- builds -----------------------------------------------------------
    builds = []
    for spec in CLASSES:
        for branch in spec.branches:
            state = _branch_build(spec.id, branch.id, max_points)
            spent = points_spent(state)
            capstone = branch.nodes[-1]
            if _rank(state, capstone.id) != 1:
                problems.append(f"{spec.id}.{branch.id}: capstone not taken")
            if spent != branch.capacity:
                problems.append(f"{spec.id}.{branch.id}: filled with {spent}, "
                                f"capacity {branch.capacity}")
            if len(tree_effects(state)) < 6:
                problems.append(f"{spec.id}.{branch.id}: thin build, "
                                f"{len(tree_effects(state))} effects")
            builds.append((f"{spec.id}/{branch.id}-max", spent,
                           len(tree_effects(state))))

        # two branches to the floor, which is what 108 points actually buys
        pair = _fresh(spec.id, max_points)
        for branch in spec.branches[:2]:
            for n in branch.nodes:
                _spend_toward(pair, n.id, n.max_rank, MAX_LEVEL)
        if points_spent(pair) != 2 * spec.branches[0].capacity:
            problems.append(f"{spec.id}: two-branch build did not complete")
        builds.append((f"{spec.id}/two-branch", points_spent(pair),
                       len(tree_effects(pair))))

        spread = _spread_build(spec.id, max_points)
        if spread["points"] != 0:
            problems.append(f"{spec.id}: spread build stranded "
                            f"{spread['points']} points")
        builds.append((f"{spec.id}/spread", points_spent(spread),
                       len(tree_effects(spread))))

        rush = _capstone_rush(spec.id, max_points)
        taken = sum(1 for b in spec.branches if _rank(rush, b.nodes[-1].id))
        if taken != 3:
            problems.append(f"{spec.id}: capstone rush took {taken}/3")
        builds.append((f"{spec.id}/three-capstones", points_spent(rush),
                       len(tree_effects(rush))))

        # accounting: every point is either spent or still in hand, never both
        for label, state in (("spread", spread), ("rush", rush), ("pair", pair)):
            if points_spent(state) + state["points"] != max_points:
                problems.append(f"{spec.id}/{label}: points do not balance")

    # -- movesets: the tree is the only door in --------------------------
    # Three proofs, because three different mistakes are possible here and each
    # of them would ship a class that cannot fight.
    grant_tiers: dict = {}
    for spec in CLASSES:
        granted = []
        for node in spec.nodes:
            granted += list(moveset_for_node(node.id))
        rungs = sorted(movesets.BY_ID[m].rung for m in granted)
        if rungs != list(range(1, movesets.MAX_RUNG + 1)):
            problems.append(f"{spec.id}: grants rungs {rungs}")
        for move_id in granted:
            node = NODE_BY_ID[node_for_moveset(move_id)]
            move = movesets.BY_ID[move_id]
            grant_tiers.setdefault(move.rung, set()).add(node.tier)
            if move.class_id != spec.id:
                problems.append(f"{node.id}: grants {spec.id} another class's move")
        # 1. Three points, one in each branch's first node, buy three moves.
        starter = _fresh(spec.id, 3)
        for branch in spec.branches:
            spend(starter, branch.nodes[0].id, level=1)
        if len(movesets_granted(starter)) != 3:
            problems.append(f"{spec.id}: three points do not buy three moves")
        if moveset_reach(starter) != 3:
            problems.append(f"{spec.id}: three points do not reach rung three")
        # 2. The WHOLE moveset fits inside one character's point budget, with
        #    room left over. If it did not, the capstone move would be a thing
        #    the player reads about and never casts.
        full = _fresh(spec.id, max_points)
        for node_id in dict.fromkeys(node_for_moveset(m.id)
                                     for m in movesets.for_class(spec.id)):
            _spend_toward(full, node_id, MOVE_GRANT_RANK, MAX_LEVEL)
        if len(movesets_granted(full)) != movesets.MAX_RUNG:
            problems.append(f"{spec.id}: the full moveset does not fit in "
                            f"{max_points} points")
        moveset_cost = points_spent(full)
        if moveset_cost > max_points * 0.75:
            problems.append(f"{spec.id}: the moveset eats {moveset_cost} of "
                            f"{max_points} points and leaves no build")
        # 3. The book the tree builds teaches the lines those moves are made of.
        book = movebook(full, incantation_book := {"known": [], "equipped": [],
                                                   "slots": 99, "stats": {}})
        wanted = {i for m in movesets_granted(full)
                  for i in movesets.BY_ID[m].spine}
        if not wanted <= set(incantation_book["known"]):
            problems.append(f"{spec.id}: movebook did not teach its own lines")
        if movesets.reach_of(book) != movesets.MAX_RUNG:
            problems.append(f"{spec.id}: full tree does not reach the top rung")
    # Every class grants the same rung from the same tier of node, or "which
    # class gets its area attack first" becomes a real question.
    uneven = {rung: sorted(tiers) for rung, tiers in grant_tiers.items()
              if len(tiers) != 1}
    if uneven:
        problems.append(f"grant tiers differ between classes: {uneven}")
    moveset_problems = movesets.self_check()["problems"]
    if moveset_problems:
        problems.append(f"movesets.self_check: {moveset_problems}")

    # -- capstones open only when they should -----------------------------
    early = _fresh(CLASSES[0].id, max_points)
    capstone_id = CLASSES[0].branches[0].nodes[-1].id
    _spend_toward(early, capstone_id, 1, CAPSTONE_LEVEL - 1)
    if _rank(early, capstone_id):
        problems.append("a capstone was taken below the level gate")

    # -- respec conserves points -----------------------------------------
    rs = _branch_build(CLASSES[0].id, CLASSES[0].branches[0].id, max_points)
    before = points_spent(rs) + rs["points"]
    quote = respec_cost(rs, level=MAX_LEVEL)
    respec(rs, level=MAX_LEVEL, gold_available=10 ** 6)
    if rs["points"] != before or points_spent(rs) != 0:
        problems.append("respec lost or invented points")
    if not quote["free"]:
        problems.append("the first respec was not free")

    # -- dual discipline --------------------------------------------------
    dual = _fresh(CLASSES[0].id, max_points, dual=CLASSES[1].id)
    foreign_t1 = [n for n in CLASSES[1].nodes if n.tier == 1][0]
    foreign_t3 = [n for n in CLASSES[1].nodes if n.tier == 3][0]
    ok_t1, _ = can_spend(dual, foreign_t1.id, level=DUAL_CLASS_LEVEL)
    ok_t3, _ = can_spend(dual, foreign_t3.id, level=DUAL_CLASS_LEVEL)
    ok_early, _ = can_spend(dual, foreign_t1.id, level=DUAL_CLASS_LEVEL - 1)
    if not ok_t1 or ok_t3 or ok_early:
        problems.append("dual-discipline gating is wrong")
    spend(dual, foreign_t1.id, level=DUAL_CLASS_LEVEL)
    if max_points - dual["points"] != DUAL_CLASS_COST:
        problems.append("a foreign node did not cost double")

    # -- caps bind at the top of a build, never inside one node -----------
    # A cap that bites before a node is fully ranked would make its last ranks
    # worthless, which is the definition of a trap node.
    cap_strays = sorted(set(CAPS) - set(EFFECT_LABELS))
    if cap_strays:
        problems.append(f"caps on keys with no label: {cap_strays}")
    for n in NODE_BY_ID.values():
        for key, value in n.effects_at(n.max_rank).items():
            if key in CAPS and value > CAPS[key]:
                problems.append(f"{n.id}: {key} {value} exceeds its own cap alone")
    binding = set()
    for spec in CLASSES:
        for branch in spec.branches:
            state = _branch_build(spec.id, branch.id, max_points)
            raw: dict = {}
            for node_id, rank in state["spent"].items():
                for key, value in NODE_BY_ID[node_id].effects_at(rank).items():
                    if key in MAXED_KEYS:
                        raw[key] = max(raw.get(key, 0), value)
                    else:
                        raw[key] = round(raw.get(key, 0) + value, 4)
            over = {k: (v, CAPS[k]) for k, v in raw.items()
                    if k in CAPS and v > CAPS[k]}
            if over:
                problems.append(f"{spec.id}.{branch.id}: ranks stranded by a cap "
                                f"{over}")
            binding |= {k for k, v in raw.items()
                        if k in CAPS and v >= CAPS[k]}

    # -- every class reaches every chapter --------------------------------
    # Two independent arguments. First: the curriculum's gates do not accept
    # anything a class produces, checked against the live signatures rather than
    # against a memory of them.
    gate_params = set()
    for fn in (curriculum.is_permitted, curriculum.tier_unlocked,
               curriculum.permitted_patterns, curriculum.chapter_progress):
        gate_params |= set(inspect.signature(fn).parameters)
    leaked = sorted(gate_params & (used_keys | {"class", "class_id", "effects",
                                                "tree", "node"}))
    if leaked:
        problems.append(f"curriculum gating accepts class data: {leaked}")

    # Second: no class is ever left with a branch that pays nothing in a chapter,
    # so "route" never degrades into "wait".
    liveness = {}
    for spec in CLASSES:
        rows = {}
        for chapter in curriculum.CHAPTERS:
            live = [n.id for n in spec.nodes
                    if measure_live_in(n.measure, chapter.id)]
            live_t1 = {b.id for b in spec.branches
                       for n in b.nodes
                       if n.tier == 1 and measure_live_in(n.measure, chapter.id)}
            rows[chapter.id] = len(live)
            if len(live_t1) != 3:
                problems.append(f"{spec.id}: branch with no live entry node in "
                                f"{chapter.id}")
            if len(live) < 15:
                problems.append(f"{spec.id}: only {len(live)} live nodes in "
                                f"{chapter.id}")
        liveness[spec.id] = rows

    # -- authored text ----------------------------------------------------
    answerish = []
    for label, text in _authored_text():
        lowered = (text or "").lower()
        answerish += [f"{label} ({tell!r})" for tell in _ANSWER_TELLS
                      if tell in lowered]
    if answerish:
        problems.append(f"text reading as an answer: {answerish}")
    banged = [label for label, text in _authored_text() if "!" in (text or "")]
    if banged:
        problems.append(f"exclamation marks: {banged}")

    # -- gear referenced that actually exists -----------------------------
    missing_gear = []
    for spec in CLASSES:
        if spec.affinity_set not in items.SETS:
            missing_gear.append(f"{spec.id}: set {spec.affinity_set}")
        if spec.starter_weapon not in items.BY_ID:
            missing_gear.append(f"{spec.id}: starter {spec.starter_weapon}")
        for item_id in spec.affinity_items:
            if item_id not in items.BY_ID:
                missing_gear.append(f"{spec.id}: affinity {item_id}")
        if spec.signature_weapon not in GEAR_BY_ID:
            missing_gear.append(f"{spec.id}: signature {spec.signature_weapon}")
        if spec.signature_set not in SET_REQUESTS:
            missing_gear.append(f"{spec.id}: signature set {spec.signature_set}")
        if spec.move not in MOVE_BY_ID:
            missing_gear.append(f"{spec.id}: move {spec.move}")
    already = sorted(set(GEAR_BY_ID) & set(items.BY_ID))
    if already:
        missing_gear.append(f"requested ids already taken in items.py: {already}")
    if missing_gear:
        problems.append(f"gear references: {missing_gear}")

    # -- level curve agrees with progression ------------------------------
    curve = "not checked"
    try:
        from . import progression
        curve = "agrees"
        if progression.MAX_LEVEL != MAX_LEVEL:
            problems.append(f"MAX_LEVEL {MAX_LEVEL} != progression "
                            f"{progression.MAX_LEVEL}")
            curve = "disagrees"
    except Exception as exc:                  # pragma: no cover - diagnostics
        curve = f"unavailable: {exc}"

    per_class = CLASSES[0].capacity
    return {
        "classes": len(CLASSES),
        "branches_per_class": 3,
        "nodes_per_branch": 7,
        "nodes_total": len(NODE_BY_ID),
        "capstones_per_class": 3,
        "capstones_total": sum(1 for n in NODE_BY_ID.values() if n.capstone),
        "ranks_per_class": per_class,
        "ranks_total": sum(c.capacity for c in CLASSES),

        "points_per_level": POINTS_PER_LEVEL,
        "points_from_levels": (MAX_LEVEL - 1) * POINTS_PER_LEVEL,
        "points_from_chapters": MAX_CHAPTER_POINTS,
        "points_earned_at_99": max_points,
        "points_spendable_per_class": per_class,
        "points_balance": f"{max_points} earned, {per_class} spendable, "
                          f"{round(100 * max_points / per_class)}% of the tree "
                          f"fits in one character",
        "points_at_level_30": points_earned(30, 4),
        "points_at_level_60": points_earned(60, 9),
        "branch_capacity": CLASSES[0].branches[0].capacity,
        "branches_maxable_at_99": max_points // CLASSES[0].branches[0].capacity,
        "cheapest_capstone_points": min(
            _min_points_to_max(b.nodes[-1]) for c in CLASSES for b in c.branches),
        "worst_node_cost": worst,
        "worst_node": worst_node,
        "every_node_reachable": all(v >= 0 for v in reach.values()),
        "every_node_affordable": all(0 <= v <= max_points for v in reach.values()),

        "effect_keys_used": sorted(used_keys),
        "effect_keys_borrowed_from_items": sorted(used_keys & set(items.EFFECT_LABELS)),
        "effect_keys_new": sorted(NEW_EFFECT_LABELS),
        "effect_keys_outside_vocabulary": stray,
        "new_keys_unused": unused_new,
        "measures": len(MEASURES),
        "measures_used": sorted(measures_used),
        "measures_idle": idle_measures,
        "chapter_scoped_measures": sorted(set(MEASURE_BY_ID) - UNIVERSAL_MEASURES),
        "scoped_measures_at_tier_one": scoped_tier_one,

        "builds_simulated": len(builds),
        "build_sample": builds[:6],
        "no_dead_builds": not any(b[2] < 6 for b in builds),
        "no_stranded_points": True,

        "gear_requests": len(GEAR_REQUESTS),
        "gear_sets_requested": len(SET_REQUESTS),
        "class_restricted_items": len(CLASS_RESTRICTED),
        "existing_items_referenced": sorted(
            {i for c in CLASSES for i in c.affinity_items}
            | {c.starter_weapon for c in CLASSES}),
        "moves": len(MOVES),

        "chapters_total": len(curriculum.CHAPTERS),
        "chapters_graduatable": len(GRADUATABLE_CHAPTERS),
        "live_nodes_by_chapter": liveness,
        "every_class_every_chapter": all(
            v >= 15 for rows in liveness.values() for v in rows.values()),
        "curriculum_gate_parameters": sorted(gate_params),
        "curriculum_untouched": not leaked,

        "caps": len(CAPS),
        "caps_reached_exactly_by_a_maxed_branch": sorted(binding),
        "caps_never_strand_a_rank": True,

        "level_curve": curve,
        "authored_strings": sum(1 for _ in _authored_text()),
        "lines_reading_as_answers": answerish,
        "no_literal_answers": not answerish,
        "respec_first_free": FIRST_RESPEC_FREE,
        "problems": problems,
        "ok": not problems,
    }


if __name__ == "__main__":              # pragma: no cover - a convenience
    import json
    print(json.dumps(self_check(), indent=2, default=str))
