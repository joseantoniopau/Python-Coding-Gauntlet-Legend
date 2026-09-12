"""Gold: where it comes from, who takes it, and the one rule underneath both.

    GOLD IS A RECEIPT FOR CORRECT PYTHON. IT IS NOT A RECEIPT FOR TIME.

Every function in this file that produces a number takes a graded outcome as an
argument. There is no timer, no idle yield, no daily login, no "you were here"
payment. If the sandbox did not run something and a grader did not pass it, this
module pays nothing, and `validate()` walks every public earner at import to
prove that the failing branch returns zero.

The distinction that took the longest to get right is the one the brief asked
for by name. Repetition is the entire point of this game. Clearing the SAME AREA
for an evening is a player practising, and that pays at a flat rate forever.
Clearing the SAME PROBLEM for an evening is a player rehearsing one answer, and
that tapers hard. So:

    THE AREA RATE IS FLAT. THE PROBLEM RATE TAPERS.

`taper()` is keyed on problem id and nothing else. The fifth solve of
`ah-three-sum` pays 15% of the first. The five hundredth *encounter* in Hashmap
Highlands pays exactly what the first one did, because it was five hundred
different problems. A spaced retest — the SRS's disguised variant, days later —
pays FULL rate and does not advance the counter, because recalling a thing cold
after a week is the good evidence and the economy should say so out loud.

WHERE THE NUMBERS CAME FROM
---------------------------
`BATTLE_MINUTES` is measured, not guessed: it is the median `target_seconds` of
the 1,013-problem corpus per difficulty band, in minutes.

    GUIDED 2   TUTORIAL 3   EASY 7   MEDIUM 15   HARD 25

ELITE and BOSS are extrapolated and labelled as such, because the corpus holds
no problems at those bands — they are assembled encounters.

`ENCOUNTER_BASE` is then chosen so that GOLD PER MINUTE rises gently and
monotonically with difficulty:

    GUIDED 1.00   TUTORIAL 1.33   EASY 1.43   MEDIUM 1.60
    HARD 1.68     ELITE 1.71      BOSS 1.78

Gently, so no band is a farm. Monotonically, so climbing is never a pay cut.
Both properties are asserted in `validate()` rather than hoped for.

WHAT THIS FILE DELIBERATELY DOES NOT OWN
----------------------------------------
THE PURSE. `state["player"]["gold"]` belongs to the engine. Every function here
REPORTS a spend or an award and mutates nothing of the player's. This is not
fastidiousness; it is copied deliberately from `forge.upgrade()`, whose
docstring says two places that both think they own a number is how a purse goes
negative. One owner, one number.

THE WEAPON UPGRADE FEE. `forge.GOLD_SHAPE` already exists, is already quoted by
`forge.quote()` and already reported by `forge.upgrade()`. `weapon_fee()` here
reads it. It does not restate it. A second table of weapon prices would be the
same bug as a second purse, one level up.

THE QUEST REWARD. `quests.REWARD_TIERS` already fixes gold per quest tier, and
that table is load-bearing for quest design. `quest_award()` passes it through
and adds only the repeat taper for repeatable quests.

THE REGION'S DIFFICULTY BAND. `story.band_for` derives it from the rung of the
metal the region gives up, `quests.py` re-exports that rather than recomputing
it, and this module does the same. Three files agreeing is worth more than a
fourth opinion, and `story.py`'s version is the one already used to decide what
potions a place may hand out — which is precisely the question a vendor asks.

WHAT REGALIA IS. There are two bodies of tack and neither belongs to this file.
`gauntlet/regalia.py` owns twenty-four COMPANION-keyed objects, earned by
evidence and explicitly unpriced; this module does not sell them and
`validate()` checks that it never starts. `quests.REGALIA` owns seven
REGION-keyed pieces with their own levers, limits, caps and
`_regalia_grants_no_depth()` proof; those this module PRICES and shelves, which
is exactly what regalia.py's docstring says should happen to them. No second
effect is defined here, and `regalia_speech()` is a pass-through to
`quests.companion_speech()` that exists only so a caller has one obvious door.

WHAT IT DOES OWN: the encounter rate, the puzzle rate, the rare monster purse,
the area scale, the taper, seventeen potion vendors and their stock, the price
of regalia, the challenge broker and her trials, and the ARMOUR upgrade fee —
which had no owner before, because `items.UPGRADE_PATHS` gates armour on graded
evidence and charges nothing.

THE BALANCE, WITH THE WORKING SHOWN
-----------------------------------
Run `python -m gauntlet.economy` for the current figures. The verdict is taken
from a SIMULATED campaign — `simulate_all()` plays the real award functions, the
real trial machinery and the real taper across the fourteen regions of
CAMPAIGN_WALK — rather than from the closed-form model beside it, because the
closed form came out 1.4x optimistic and it is better to know that than to argue
about it. At the time of writing:

    an ordinary hour in Sliding Window Marsh   4.0 encounters
                                               129 gold fighting
                                               190 gold working the board
    the 449 fights the weapon ladder takes     about 98 hours
    earned over them, fighting only            9,654 gold
    earned over them, working the board       11,787 gold  (1.22x)
    weapon ladder to rung nine                 3,785
    three warded slots and boots               2,110
    the best piece of regalia                    679
    potions, moderate drinking                 1,594
    total                                      8,168  =  85% / 69%

VERDICT: TIGHT BUT NOT BINDING. A player who fights and never speaks to the
broker can afford everything worth buying with about a sixth of their income to
spare. A player who works the board has a third spare and can be careless with
potions. Nothing in the game is gated on gold — the blade works at rung one, the
armour works unupgraded, and potions drop free — so the tightness is a set of
decisions and never a wall, which is the rule.

Where a purse fits: about 13% of income. It was 27% in the first draft, which
was not "rare" by any reading of the word, and the numbers were halved.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

from . import (curriculum, elements, forge, items, pets, potions, puzzles,
               quests, story, world)


# ==========================================================================
# SECTION 1 — WHAT AN AREA IS WORTH
# ==========================================================================
#
# Two different questions get asked about a region and they have two different
# answers, so they get two different functions. Collapsing them into one number
# was the first thing tried and it was wrong in both directions.
#
#   HOW FAR IN IS THIS?  -> `area_depth`, the longest path to this region through
#       world.REGIONS' unlock graph. This is what scales PAY, because the unlock
#       graph is the learning graph: a region you had to prove four things to
#       reach is a region whose fights are worth more.
#
#   WHAT DOES THIS PLACE HOLD?  -> `area_band`, a difficulty tier. This is what
#       decides a vendor's shelf and a trial's band.
#
# The obvious third option — measure the mean difficulty of the region's own
# problems in the corpus — was tried and discarded, and it is worth saying why
# because it looks like the most honest option available. It does not separate
# the regions. Measured that way, fifteen of the seventeen come out as EASY:
# every region carries a broad band of its own pattern, from GUIDED warm-ups to
# one or two HARD showpieces, so the means all land between 1.5 and 2.2. A
# measurement that says every place in the game is the same place is a true
# measurement of the wrong quantity. `measure_area_bands()` at the bottom of this
# file still computes it, so the claim can be rechecked rather than believed.

def _depths() -> dict:
    """Longest path to each region through the unlock graph, memoised once.

    `unlocks` in world.REGIONS is the PREREQUISITE list despite the name, so the
    graph runs the way it reads. Cycles are impossible by construction and would
    recurse forever if they were not, so the visiting set turns one into a zero
    rather than a stack overflow in a save-file loader.
    """
    deps = {r["id"]: list(r["unlocks"]) for r in world.REGIONS}
    out: dict = {}

    def walk(rid: str, seen: frozenset) -> int:
        if rid in out:
            return out[rid]
        if rid in seen or rid not in deps:
            return 0
        parents = [p for p in deps[rid] if p in deps]
        value = 0 if not parents else 1 + max(
            walk(p, seen | {rid}) for p in parents)
        out[rid] = value
        return value

    for rid in deps:
        walk(rid, frozenset())
    return out


AREA_DEPTH: dict = _depths()
MAX_DEPTH = max(AREA_DEPTH.values())          # 7, the Null King's Castle

# The BAND is not computed here. `story.band_for` derives a region's difficulty
# from the rung of the metal it gives up — the forge is the authority on how hard
# a place is — and `quests.py` re-exports that rather than working it out a second
# time. This module does the same. It is the same question a vendor is asking
# ("what may this place hand out?") and it already has one answer.
#
#   GUIDED     python_village
#   TUTORIAL   fields_of_syntax
#   EASY       hashmap_highlands, stringwood_labyrinth, array_caverns
#   MEDIUM     sliding_window_marsh, twin_pointer_pass, stack_queue_mines,
#              debugging_dungeon
#   HARD       matrix_citadel, recursive_forest, binary_tree_canopy, graph_wastes
#   ELITE      dp_ruins, complexity_tower, coding_coliseum
#   BOSS       null_kings_castle

# How much deeper pays. 10% a rung, so the castle pays 1.7x the village for the
# same difficulty of problem. Small on purpose: the difficulty band is already
# doing most of the scaling, and stacking two steep curves is how a late region
# ends up worth twenty times an early one and the early game stops being playable
# by anyone who ever visited the late one.
AREA_STEP = 0.10


def area_depth(region_id: str) -> int:
    """How many unlocks deep a region sits. Unknown regions read as the surface,
    never as an exception — an economy that raises on an unrecognised region id
    is an economy that eats a player's reward."""
    return int(AREA_DEPTH.get(region_id, 0))


def area_band(region_id: str) -> str:
    """The difficulty band a region's shelves and trials are pitched at.

    story.py's number, read rather than recomputed. See the note above.
    """
    return story.REGION_BAND.get(region_id) or story.band_for(region_id)


def area_multiplier(region_id: str) -> float:
    """The pay scale for a region. 1.00 at the village, 1.70 at the castle."""
    return round(1.0 + AREA_STEP * area_depth(region_id), 3)


def area_view(region_id: str) -> dict:
    """Everything the UI wants to say about a region's economy in one row."""
    region = world.REGION_BY_ID.get(region_id, {})
    return {
        "region": region_id, "name": region.get("name", region_id),
        "depth": area_depth(region_id), "band": area_band(region_id),
        "multiplier": area_multiplier(region_id),
        "element": elements.affinity_for(region_id),
        "vendor": vendor_for(region_id).name if vendor_for(region_id) else "",
    }


# ==========================================================================
# SECTION 2 — THE RATE
# ==========================================================================
#
# Measured from the corpus: the median target_seconds per difficulty, in
# minutes. GUIDED 120s, TUTORIAL 180s, EASY 420s, MEDIUM 900s, HARD 1500s.
# Recompute with `measure_battle_minutes()`.
#
# ELITE and BOSS carry no corpus problems — they are assembled encounters with
# phases — so those two are estimates, and they are the only two numbers in this
# section that are. They are marked here rather than buried.
BATTLE_MINUTES = {"GUIDED": 2.0, "TUTORIAL": 3.0, "EASY": 7.0, "MEDIUM": 15.0,
                  "HARD": 25.0, "ELITE": 35.0, "BOSS": 45.0}
ESTIMATED_BANDS = ("ELITE", "BOSS")

# Gold for one cleared encounter at B rank in a depth-zero region, before
# everything else. Chosen so gold-per-minute rises gently and monotonically:
# 1.00, 1.33, 1.43, 1.60, 1.68, 1.71, 1.78. Both properties are enforced in
# `validate()`, which is the only reason to trust them.
#
# The shape deliberately lands within about 15% of what engine.py was already
# paying (`xp // 3` at B rank: 4, 8, 20, 36, 46, 66), so switching the call site
# over is a rebalance rather than an earthquake. The 15% it gains at the top is
# the combo multiplier, which used to reach gold through xp and now does not —
# see COMBO, below.
ENCOUNTER_BASE = {"GUIDED": 2, "TUTORIAL": 4, "EASY": 10, "MEDIUM": 24,
                  "HARD": 42, "ELITE": 60, "BOSS": 80}

# COMBO. Gold is a function of (difficulty, rank, area) and nothing else. It used
# to ride on xp, which carries `grading.combo_multiplier` — a streak bonus of up
# to 1.5x. A streak is real evidence and xp is right to reward it, but gold is
# the number the player SPENDS, and a spendable number that swings 50% on
# momentum makes every price in the game mean something different depending on
# how the last ten minutes went. XP measures growth. Gold measures work
# delivered. One number, one job.
RANK_PAY = {"S": 1.5, "A": 1.25, "B": 1.0, "C": 0.8, "LEARNING_CLEAR": 0.4}

# A phoenix clear still pays. Forty per cent of nothing would be nothing, and a
# player who needed the crutch is exactly the player who cannot afford to also be
# broke. Learning never dead-ends, and that rule has a price tag.
FALLBACK_RANK_PAY = 0.8


def gold_per_minute(difficulty: str) -> float:
    """The rate a band pays, before rank and area. The number every other rate in
    this file is checked against."""
    d = _band(difficulty)
    return round(ENCOUNTER_BASE[d] / BATTLE_MINUTES[d], 4)


def _band(difficulty: str) -> str:
    """Clamp any difficulty string onto the ladder. curriculum.tier_index already
    owns the fallback for an unclassifiable encounter, so borrow it rather than
    invent a second answer to the same question."""
    name = str(difficulty or "").upper()
    if name in ENCOUNTER_BASE:
        return name
    return curriculum.TIERS[curriculum.tier_index(name)]


def rank_pay(rank: str) -> float:
    return RANK_PAY.get(str(rank or "").upper(), FALLBACK_RANK_PAY)


# ==========================================================================
# SECTION 3 — THE TAPER, WHICH IS THE WHOLE ARGUMENT
# ==========================================================================
#
# WHERE THE LINE IS, SAID PLAINLY:
#
#   The AREA rate never moves. Clear Graph Wastes a hundred times and the
#   hundredth fight pays what the first did, because a hundred fights in Graph
#   Wastes is a hundred different graph problems and that is a player getting
#   fluent at graphs. That is the behaviour this game exists to cause and it
#   would be perverse to pay less for more of it.
#
#   The PROBLEM rate collapses. The fifth solve of one problem pays 15% of the
#   first, because the fifth solve of one problem is muscle memory of one answer.
#   It is not worthless — 15%, not zero, because a player re-running a problem to
#   check something should not be actively punished for it — but it is not work.
#
# TAPER_RATIO is 0.55 rather than something gentler because the interesting case
# is the player who finds one easy problem they can type from memory in forty
# seconds. At 0.55 that strategy is worth less than moving on by the third
# repetition, which is roughly when a human would have noticed anyway.
TAPER_RATIO = 0.55
TAPER_FLOOR = 0.15

# A problem forgotten is a problem worth solving again. One repetition is
# forgiven per ten days since the last time it paid, so a problem you have not
# seen in a month is fresh money again. This is `srs.py`'s argument stated in
# gold: the value of an answer decays with time away from it, and so should the
# price of proving you still have it.
TAPER_FORGIVE_DAYS = 10.0
_DAY = 86400.0

# A disguised retest — engine's `is_retest`, the SRS's delayed variant — pays
# FULL rate and does not advance the counter. Recalling something cold after a
# week is the strongest evidence this game collects. Charging it the repeat
# penalty would be the economy calling its own best signal a rerun.
RETEST_PAYS_FULL = True


def taper(state: dict | None, problem_id: str, *, now: float = 0.0) -> float:
    """The multiplier this problem pays right now. 1.0 for anything unseen.

    Read-only. `record()` is what advances the counter, and the two are separate
    so a UI can show a player what a fight is worth before they take it without
    that glance costing them the money.
    """
    if not problem_id:
        return 1.0
    entry = _ledger(state).get(str(problem_id))
    if not entry:
        return 1.0
    n = _effective_repeats(entry, now)
    if n <= 0:
        return 1.0
    return round(max(TAPER_FLOOR, TAPER_RATIO ** n), 4)


def _effective_repeats(entry: dict, now: float) -> int:
    n = int(entry.get("n", 0))
    at = float(entry.get("at", 0.0))
    if now and at and now > at:
        n -= int((now - at) // (TAPER_FORGIVE_DAYS * _DAY))
    return max(0, n)


def taper_view(state: dict | None, problem_id: str, *, now: float = 0.0) -> dict:
    """What the taper is doing and what the next solve will pay, for the tooltip.
    A taper the player cannot see reads as a bug in the reward code."""
    entry = _ledger(state).get(str(problem_id), {})
    n = _effective_repeats(entry, now) if entry else 0
    mult = taper(state, problem_id, now=now)
    return {
        "problem": problem_id, "solves": int(entry.get("n", 0)),
        "counted": n, "multiplier": mult,
        "next_multiplier": round(max(TAPER_FLOOR, TAPER_RATIO ** (n + 1)), 4),
        "at_floor": mult <= TAPER_FLOOR,
        "forgives_in_days": (TAPER_FORGIVE_DAYS if n else 0.0),
        "text": ("Fresh." if n == 0 else
                 f"Solved {n} time{'s' if n != 1 else ''} recently. "
                 f"Paying {int(round(mult * 100))}%."),
    }


# ==========================================================================
# SECTION 4 — AWARDS
# ==========================================================================
#
# Every earner returns an Award and mutates nothing. `record()` commits. The
# split exists because the UI wants to preview, the engine wants to settle, and
# an earner that does both at once cannot serve the first without corrupting the
# second.

@dataclass(frozen=True)
class Award:
    gold: int
    source: str
    base: int = 0
    problem_id: str = ""
    region_id: str = ""
    multipliers: dict = field(default_factory=dict)
    detail: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


NOTHING = Award(gold=0, source="none")

SOURCES = ("encounter", "puzzle", "purse", "boss", "dungeon_room",
           "quest", "trial")


def _award(gold: float, source: str, **kw) -> Award:
    """Round once, at the end, and never below zero. Rounding per-multiplier was
    the first version and it lost a fifth of the low-band income to the floor."""
    return Award(gold=max(0, int(round(gold))), source=source, **kw)


def encounter_award(state: dict | None, *, region_id: str, difficulty: str,
                    rank: str = "B", problem_id: str = "", solved: bool = True,
                    is_retest: bool = False, now: float = 0.0) -> Award:
    """A cleared encounter. The spine of the economy and the plainest case of the
    rule: no clear, no gold, and the failing branch is the first line."""
    if not solved:
        return Award(gold=0, source="encounter", region_id=region_id,
                     problem_id=problem_id,
                     lines=["Nothing was proved, so nothing is owed."])
    band = _band(difficulty)
    base = ENCOUNTER_BASE[band]
    rk = rank_pay(rank)
    area = area_multiplier(region_id)
    tp = 1.0 if (is_retest and RETEST_PAYS_FULL) else taper(state, problem_id, now=now)
    return _award(base * rk * area * tp, "encounter", base=base,
                  problem_id=problem_id, region_id=region_id,
                  multipliers={"rank": rk, "area": area, "taper": tp},
                  detail={"difficulty": band, "is_retest": bool(is_retest)})


# -- puzzles ---------------------------------------------------------------
#
# The six kinds in puzzles.py are graded by running real Python or by an exact
# structural match, so they are evidence and they pay. The rate is set by MINUTES
# rather than by a share of the encounter, because `target_seconds` in the corpus
# is assigned by DIFFICULTY BAND and not by encounter kind: a TRACE authored at
# EASY carries the same 420-second budget as a full EASY code battle and takes
# about two minutes. Paying a share of the band would have made TRACE the most
# profitable minute in the game by a factor of three.
#
# These minute figures are estimates of wall clock, not measurements, and they
# are the softest numbers in the file. They are ordered by how much of the
# solution the player has to hold in their head at once, which is the only
# ordering defensible without telemetry.
PUZZLE_MINUTES = {
    "TRACE": 2.5,             # read six lines, say what a variable holds
    "SPOT_THE_FLAW": 3.0,     # two near-identical bodies, find the diverging line
    "STATE_PREDICT": 3.0,     # one structure, one operation trace, exact state
    "COMPLEXITY_MATCH": 5.0,  # several snippets at once, each costed
    "RUNE_ASSEMBLY": 6.0,     # order the whole solution, indentation included
    "BREAK_IT": 7.0,          # construct an input that defeats plausible code
}

# A puzzle pays 80% of what the same minutes at a blank screen would pay.
#
# Not 100%, and the 20% is a deliberate thumb on the scale. RUNE_ASSEMBLY is the
# best tool in this game for this player's actual bottleneck and the economy
# should never discourage it — but producing Python from nothing is the thing the
# interview asks for, and if the gold-optimal hour were an hour of ordering
# shuffled lines, the economy would be quietly teaching the wrong skill. Twenty
# per cent is enough to keep the blank screen the best-paid seat in the house and
# small enough that nobody avoids a puzzle over it.
PUZZLE_RATE = 0.80


def puzzle_award(state: dict | None, *, region_id: str, difficulty: str,
                 kind: str, problem_id: str = "", solved: bool = True,
                 rank: str = "B", now: float = 0.0) -> Award:
    """One of the six puzzle kinds, graded. `kind` is a puzzles.PUZZLE_KINDS
    member; anything else is treated as the cheapest kind rather than refused,
    because a new puzzle type should ship at a conservative rate and not crash
    the reward screen."""
    if not solved:
        return Award(gold=0, source="puzzle", region_id=region_id,
                     problem_id=problem_id,
                     lines=["The grader was not satisfied. Neither is the purse."])
    band = _band(difficulty)
    minutes = PUZZLE_MINUTES.get(str(kind).upper(), min(PUZZLE_MINUTES.values()))
    base = minutes * gold_per_minute(band) * PUZZLE_RATE
    rk = rank_pay(rank)
    area = area_multiplier(region_id)
    tp = taper(state, problem_id, now=now)
    return _award(base * rk * area * tp, "puzzle", base=int(round(base)),
                  problem_id=problem_id, region_id=region_id,
                  multipliers={"rank": rk, "area": area, "taper": tp},
                  detail={"difficulty": band, "kind": str(kind).upper(),
                          "minutes": minutes})


# -- the rare monster purse ------------------------------------------------
#
# The brief asked for gold from monster drops, scaled to the area, and RARE. The
# capitalisation was the brief's own.
#
# A dropped purse is still traced to graded evidence, and the trace matters: the
# ROLL only happens on a cleared encounter. Randomness decides the SIZE of a
# reward that correct Python has already earned. It never decides whether typing
# was worth anything. That is the same shape `items.roll_drop` and
# `potions.roll_monster_drop` already use, and the three are deliberately
# consistent so a player reads one loot rule rather than three.
# These numbers were halved once, after the simulation at the bottom of the file
# reported that a purse was supplying 27% of a campaign's gold. "Rare" was the
# brief's own word and a quarter of all income is not rare — it is a second wage
# paid by a dice roll, and it made the purse, rather than the typing, the thing
# that decided how rich an evening felt. At the figures below a purse is about
# 13% of income: often enough to be a pleasant surprise, never enough to be a
# plan. `simulate_all()` reports the current share under "earned".
PURSE_CHANCE = {"GUIDED": 0.0, "TUTORIAL": 0.015, "EASY": 0.03, "MEDIUM": 0.05,
                "HARD": 0.07, "ELITE": 0.09, "BOSS": 0.25}

# GUIDED is zero on purpose. A GUIDED encounter is complete code with one blank
# in it. Rewarding it with treasure would tell a new player that the scaffolded
# rung is a place worth staying.

PURSE_MULT = 2.2            # a purse is worth about two fights
PURSE_JITTER = (0.75, 1.35)  # so two purses in a row are not the same purse
PURSE_RANK_WEIGHT = 0.35    # rank matters, but less than it does for gear
PURSE_LUCK_WEIGHT = 0.5
MAX_PURSE_CHANCE = 0.30     # a bag of luck gear does not make purses routine

PURSE_NAMES = ("a cut purse", "a knotted rag of coin", "a split pouch",
               "a handful of cold coin", "a merchant's lost tally-purse",
               "coin still warm from something's mouth")


def roll_purse(*, region_id: str, difficulty: str, rank: str = "B",
               luck: float = 0.0, is_boss: bool = False,
               solved: bool = True, times_defeated: int = 0,
               rng: random.Random | None = None) -> Award:
    """A monster's coin. NOTHING unless it drops, and nothing at all unless the
    encounter was cleared.

    A boss carries a purse THE FIRST TIME. The rarity of a boss is the rarity —
    making the drop chancy as well would be two rare events multiplied, which is
    how a player beats the Hash Titan and gets a shrug.

    A boss you have already killed is not a rare event, so a rematch rolls on the
    ordinary band chance like anything else. Leaving it at a flat 1.0 made a
    guaranteed 316-gold purse part of an infinitely repeatable loop; see
    BOSS_REPEAT_RATIO for the measurement. `times_defeated` is the same count
    boss_award takes, and zero still means the first kill.
    """
    if not solved:
        return NOTHING
    r = rng or random.Random()
    band = _band(difficulty)
    if is_boss and int(times_defeated) <= 0:
        chance = 1.0
    else:
        chance = PURSE_CHANCE.get(band, 0.0)
        if chance <= 0.0:
            return NOTHING
        chance += items.RANK_BONUS.get(str(rank).upper(), 0.0) * PURSE_RANK_WEIGHT
        chance += float(luck) * PURSE_LUCK_WEIGHT
        chance = max(0.0, min(MAX_PURSE_CHANCE, chance))
    if r.random() >= chance:
        return NOTHING
    area = area_multiplier(region_id)
    jitter = r.uniform(*PURSE_JITTER)
    gold = ENCOUNTER_BASE[band] * area * PURSE_MULT * jitter
    return _award(gold, "purse", base=ENCOUNTER_BASE[band], region_id=region_id,
                  multipliers={"area": area, "purse": PURSE_MULT,
                               "jitter": round(jitter, 3)},
                  detail={"difficulty": band, "chance": round(chance, 4),
                          "boss": bool(is_boss)},
                  lines=[r.choice(PURSE_NAMES)])


def expected_purse(*, region_id: str, difficulty: str, rank: str = "B",
                   luck: float = 0.0) -> float:
    """Chance times mean size. The number `balance_report()` uses, so the report
    and the roll cannot drift apart."""
    band = _band(difficulty)
    chance = PURSE_CHANCE.get(band, 0.0)
    if chance <= 0.0:
        return 0.0
    chance += items.RANK_BONUS.get(str(rank).upper(), 0.0) * PURSE_RANK_WEIGHT
    chance += float(luck) * PURSE_LUCK_WEIGHT
    chance = max(0.0, min(MAX_PURSE_CHANCE, chance))
    mean_jitter = sum(PURSE_JITTER) / 2.0
    size = ENCOUNTER_BASE[band] * area_multiplier(region_id) * PURSE_MULT * mean_jitter
    return round(chance * size, 3)


# -- bosses, rooms, quests -------------------------------------------------
#
# These are multiples of the area's own encounter rate rather than tables of
# their own, so a boss is always worth a legible number of ordinary fights and
# stays worth that number after any future rebalance of the base.
BOSS_MULT = 6.0          # a region boss: six fights, and it is six phases
DUNGEON_BOSS_MULT = 4.0  # a dungeon boss, on top of the phases' own pay

# THE REMATCH TAPER, AND WHY A BOSS NEEDED ONE AT ALL.
#
# engine.py keeps `state["boss_rematch"][boss_id]` and re-fights a boss with a
# DIFFERENT problem drawn from the same spaced-repetition family, one rung
# harder each time. That is good design and it is why this taper is gentle: for
# as long as the family holds out, a rematch is fresh Python and deserves paying
# for like fresh Python.
#
# The family does not hold out. `engine._rematch_problem` ends in
# `family[min(rematch - 1, len(family) - 1)]`, which CLAMPS: once a boss's family
# is spent, every further rematch replays one identical problem id forever. The
# phases themselves handle that correctly — they run through `encounter_award`
# and taper to TAPER_FLOOR like anything else. The bonus did not, because
# `boss_award` took no state and knew no problem id, and the purse did not,
# because `is_boss` set its drop chance to a flat 1.0.
#
# Measured in the Null King's Castle: a farmed rematch paid 4.64 gold/minute
# against a plain rate of 3.02 — 1.54x — and NINETY PER CENT of it was the
# untapered bonus and the guaranteed purse. That made re-typing one memorised
# problem the equal of the best honest strategy in the game, which is the exact
# inversion this file exists to prevent.
#
# So the bonus decays per prior defeat of that boss and the purse stops being
# guaranteed after the first kill. Both are keyed on a count the engine already
# holds, and both default to the first-kill behaviour, so a caller that has not
# been updated gets exactly what it got before.
BOSS_REPEAT_RATIO = 0.7
BOSS_REPEAT_FLOOR = 0.2


def boss_repeat(times_defeated: int = 0) -> float:
    """What the bonus is worth after this boss has already gone down N times."""
    n = max(0, int(times_defeated))
    return 1.0 if n <= 0 else round(max(BOSS_REPEAT_FLOOR,
                                        BOSS_REPEAT_RATIO ** n), 4)


# A ROOM PAYS ONLY IF THE ROOM ASKED FOR SOMETHING.
#
# This table used to pay for ENTRANCE, JUNCTION, STORY and TREASURE. Those are
# exactly the four kinds in `dungeons._FREE_KINDS`, whose own comment reads
# "kinds that never ask the player to solve anything, so they are always
# passable" — so those were four lines of gold paid for walking through a door.
# Measured across the sixteen generated dungeons it was 993 gold, 12% of all
# room income, and the reachable part of it farmed at 72 gold/minute in
# Unlabelled Halls against an intended ceiling of 1.78. That is not a tuning
# error, it is the one rule this file opens by stating, broken.
#
# So the free kinds pay zero, and `validate()` reads `dungeons._FREE_KINDS` and
# fails the import if the two ever disagree. dungeons.py owns which rooms demand
# solving; this table may only agree with it.
#
# A TREASURE room keeps its entire point: `dungeons.roll_room_treasure` puts an
# ITEM in the chest, and items are not this module's currency. What it no longer
# does is hand over coin for having walked in.
#
# SHRINE stays paid because a shrine asks a recall question and a recall question
# is graded; it is not in _FREE_KINDS. VAULT stays paid because dungeons.py's
# own comment says a vault "is not in _FREE_KINDS, so it has to carry a request".
ROOM_MULT = {            # the room's bonus, on top of the encounter inside it
    "ENTRANCE": 0.0, "JUNCTION": 0.0, "STORY": 0.0, "SHRINE": 0.15,
    "TREASURE": 0.0, "VAULT": 0.35, "PUZZLE": 0.45, "ENCOUNTER": 0.45,
    "BOSS": 0.0,   # paid by dungeon_boss_award instead, once, not twice
}
ROOM_DEPTH_STEP = 0.06   # deeper rooms pay more, matching dungeons.room_reward


def boss_award(*, region_id: str, boss_id: str = "", solved: bool = True,
               dungeon: bool = False, tier: int = 0,
               times_defeated: int = 0) -> Award:
    """A boss, region or dungeon. Six ordinary fights, or four for a dungeon's,
    where the phases were paid as they were cleared.

    `times_defeated` is engine's `state["boss_rematch"].get(boss_id, 0)`, read
    BEFORE this kill is counted. Zero — the default — is the first kill and pays
    in full; see BOSS_REPEAT_RATIO for why a rematch must not.
    """
    if not solved:
        return Award(gold=0, source="boss", region_id=region_id)
    band = area_band(region_id)
    mult = DUNGEON_BOSS_MULT if dungeon else BOSS_MULT
    # A dungeon's own tier is a second depth axis the overworld does not have.
    tier_scale = 1.0 + 0.08 * max(0, int(tier)) if dungeon else 1.0
    area = area_multiplier(region_id)
    repeat = boss_repeat(times_defeated)
    return _award(ENCOUNTER_BASE[band] * mult * area * tier_scale * repeat, "boss",
                  base=ENCOUNTER_BASE[band], region_id=region_id,
                  multipliers={"boss": mult, "area": area, "tier": tier_scale,
                               "repeat": repeat},
                  detail={"boss": boss_id, "dungeon": bool(dungeon),
                          "band": band, "times_defeated": max(0, int(times_defeated))})


def dungeon_room_award(*, region_id: str, room_kind: str = "ENCOUNTER",
                       depth: int = 0, solved: bool = True) -> Award:
    """The room's share, on top of whatever the fight in it paid.

    A room that asked the player for nothing pays nothing — see ROOM_MULT. An
    UNKNOWN kind also pays nothing, which is the deliberate direction to fail in:
    the old default was 0.2, so a new free room kind added to dungeons.py would
    have started paying gold for walking the moment it shipped, silently and
    without anyone editing this file. `validate()` now refuses to import if
    dungeons.ROOM_KINDS has grown a member this table has not been told about,
    so the zero is a tripwire rather than a shrug."""
    if not solved:
        return Award(gold=0, source="dungeon_room", region_id=region_id)
    band = area_band(region_id)
    mult = ROOM_MULT.get(str(room_kind).upper(), 0.0)
    if mult <= 0.0:
        return NOTHING
    depth_scale = 1.0 + ROOM_DEPTH_STEP * max(0, int(depth))
    area = area_multiplier(region_id)
    return _award(ENCOUNTER_BASE[band] * mult * area * depth_scale,
                  "dungeon_room", base=ENCOUNTER_BASE[band], region_id=region_id,
                  multipliers={"room": mult, "depth": depth_scale, "area": area},
                  detail={"kind": str(room_kind).upper(), "depth": int(depth)})


# Quests are the one earner whose number is not ours. `quests.REWARD_TIERS` fixes
# gold per tier (30 / 65 / 130 / 240 / 420) and quest design leans on the figures.
# Restating them here would create the second-table bug this module opens by
# complaining about. What is added is the repeat taper, for the repeatable ones,
# under the same rule as everything else: the fifth run of one contract is not
# four times the work of the second.
# The floor is TAPER_FLOOR's number and not a second opinion about the same
# question. It used to be 0.3, which was the only repetition floor in the file
# that disagreed with the others, and the disagreement was worth 1.67x the plain
# rate: a tier-five repeatable at 0.3 pays 126 gold forever.
#
# Nothing currently exploits this, because `repeatable` is a forward hook —
# quests.Quest has no such field and the word does not appear in quests.py. That
# is exactly why it is worth pinning now. A hook that pays above the plain rate
# on repetition is a farm that ships the day somebody authors the first
# repeatable quest, and it would ship looking like a content change rather than
# an economy change.
QUEST_REPEAT_RATIO = 0.7
QUEST_REPEAT_FLOOR = TAPER_FLOOR


def quest_award(*, tier: int, region_id: str = "", repeatable: bool = False,
                times_completed: int = 0, turned_in: bool = True) -> Award:
    """A quest turn-in. The gold comes from quests.REWARD_TIERS, unchanged."""
    if not turned_in:
        return Award(gold=0, source="quest", region_id=region_id)
    row = quests.REWARD_TIERS.get(int(tier)) or {}
    base = int(row.get("gold", 0))
    if not base:
        return NOTHING
    repeat = 1.0
    if repeatable and times_completed > 0:
        repeat = max(QUEST_REPEAT_FLOOR, QUEST_REPEAT_RATIO ** int(times_completed))
    return _award(base * repeat, "quest", base=base, region_id=region_id,
                  multipliers={"repeat": round(repeat, 4)},
                  detail={"tier": int(tier), "name": row.get("name", ""),
                          "repeatable": bool(repeatable)})


# ==========================================================================
# SECTION 5 — THE LEDGER
# ==========================================================================

ECONOMY_STATE_KEY = "economy"


def new_state() -> dict:
    """The save shape. Flat and readable, because a save file is read by humans
    more often than anybody plans for."""
    return {
        "ledger": {},     # problem_id -> {"n": solves, "at": unix seconds}
        "earned": {},     # source -> lifetime gold, for the audit and the codex
        "spent": {},      # sink -> lifetime gold
        "vendors": {},    # region_id -> {"stock": {potion_id: n}, "credit": int}
        "broker": {"met": False, "regions": {}, "completed": {}, "trial": None},
        "regalia": [],    # pet ids whose regalia has been bought
    }


def _economy(state: dict | None) -> dict:
    if state is None:
        return new_state()
    room = state.setdefault(ECONOMY_STATE_KEY, new_state())
    for key, default in new_state().items():
        room.setdefault(key, default)
    return room


def _ledger(state: dict | None) -> dict:
    return _economy(state).get("ledger", {})


def record(state: dict, award: Award, *, now: float = 0.0) -> dict:
    """Commit an award: advance the problem's taper, add to the lifetime tally.

    THIS DOES NOT TOUCH THE PURSE. It returns the gold to add, and the caller —
    engine.py, which owns `state["player"]["gold"]` — adds it. See the module
    docstring for why that line is drawn where it is.

    A retest does not advance the counter. That is the whole of the SRS's
    argument expressed in one branch.
    """
    room = _economy(state)
    if award.gold:
        room["earned"][award.source] = int(
            room["earned"].get(award.source, 0)) + int(award.gold)
    pid = str(award.problem_id or "")
    is_retest = bool(award.detail.get("is_retest"))
    if pid and award.gold and not (is_retest and RETEST_PAYS_FULL):
        entry = room["ledger"].setdefault(pid, {"n": 0, "at": 0.0})
        entry["n"] = _effective_repeats(entry, now) + 1
        entry["at"] = float(now or entry.get("at", 0.0))
    return {"gold": int(award.gold), "source": award.source,
            "problem": pid, "lifetime": dict(room["earned"])}


def spend(state: dict, sink: str, amount: int) -> dict:
    """Record a spend for the audit. Also does not touch the purse."""
    room = _economy(state)
    room["spent"][sink] = int(room["spent"].get(sink, 0)) + int(amount)
    return {"gold_spent": int(amount), "sink": sink, "lifetime": dict(room["spent"])}


def ledger_view(state: dict | None) -> dict:
    """Earned against spent, by source. The player asked where it all went."""
    room = _economy(state)
    earned, spent_ = dict(room["earned"]), dict(room["spent"])
    return {
        "earned": earned, "spent": spent_,
        "earned_total": sum(earned.values()), "spent_total": sum(spent_.values()),
        "problems_tapering": sum(1 for e in room["ledger"].values()
                                 if int(e.get("n", 0)) > 0),
        "at_floor": sum(1 for e in room["ledger"].values()
                        if TAPER_RATIO ** int(e.get("n", 0)) <= TAPER_FLOOR),
    }


# ==========================================================================
# SECTION 6 — SEVENTEEN POTION VENDORS
# ==========================================================================
#
# PRICE, AND THE INVARIANT IT KEEPS
# ---------------------------------
# A potion's price carries the SAME area multiplier its region's fights pay. The
# deep regions are dearer and they are dearer by exactly the amount they are
# richer, so the honest unit — how many fights is this vial — is constant across
# the map. A player never has to work out whether it is cheaper to shop at home,
# because it is not, and the absence of that calculation is the feature.
#
# The honest unit is MINUTES OF PLAY, not fights, because a GUIDED fight is two
# minutes and an ELITE one is thirty-five. Priced in minutes, the ladder is
# roughly flat per strength across the whole map and falls gently as the player
# gets deeper — purchasing power never goes backwards, which is the property that
# stops a region feeling like a treadmill:
#
#   thimble  about  8 minutes of play       flask   about 48
#   vial     about 15                       flagon  about 82
#
# The strong ones cost about three times as much per point restored as the weak
# ones. That is deliberate and it is what you are actually buying: not the
# points, but the points ARRIVING IN ONE DRAUGHT, in a fight where the falloff in
# potions.sip_multiplier has already made the fourth thimble worth a third of the
# first. `validate()` proves the flatness and the direction rather than asserting
# them.
POTION_PRICE = {"minor": 12, "small": 24, "medium": 80, "hefty": 140}

# An antidote is priced under the others because it is situational. It does
# nothing at all in eleven of the seventeen regions, and a player should not pay
# a health potion's price for a bottle that is dead weight outside the marsh.
POTION_KIND_PRICE = {"HEALTH": 1.0, "FOCUS": 1.0, "ANTIDOTE": 0.8}


def potion_price(potion_id: str, region_id: str = "") -> int:
    p = potions.potion(potion_id)
    if p is None:
        return 0
    base = POTION_PRICE.get(p.strength, 0)
    kind = POTION_KIND_PRICE.get(p.kind, 1.0)
    return max(1, int(round(base * kind * area_multiplier(region_id))))


def price_in_fights(potion_id: str, region_id: str) -> float:
    """How many of this region's own fights a bottle costs."""
    band = area_band(region_id)
    per_fight = ENCOUNTER_BASE[band] * area_multiplier(region_id)
    return round(potion_price(potion_id, region_id) / max(1.0, per_fight), 3)


def price_in_minutes(potion_id: str, region_id: str) -> float:
    """The honest unit, and the one the invariant is stated in.

    The area multiplier cancels exactly — it is on the price and on the pay —
    so this is a function of the region's BAND alone. That cancellation is the
    feature: a player never has to work out where it is cheaper to shop.
    """
    band = area_band(region_id)
    return round(price_in_fights(potion_id, region_id) * BATTLE_MINUTES[band], 2)


# STOCK, AND THE CAP THE BRIEF ASKED ME TO DEFEND
# -----------------------------------------------
# The cap is `potions.CARRY_CAP` — five minor, four small, three medium, two
# hefty, per kind — and the vendor holds exactly one pouch-fill of each line.
#
# Taking the vendor's number from the pouch's number rather than inventing a
# second one is the argument. A shelf deeper than the pouch would be a shelf
# whose extra depth the player can look at and not carry, which reads as the shop
# being broken. A shelf shallower would be the game refusing a purchase it has
# already decided is legal. One number, in one place, already defended in
# potions.py, and this module borrows it.
#
# So: forty hefty potions is not a balance question here for three reasons, in
# ascending order of how much they matter.
#
#   The vendor has two. Then it has none until you have fought for the restock.
#
#   The pouch holds two. Even if you emptied every vendor in the world, the bag
#   would hold two flagons and the rest would be a story about shopping.
#
#   And the one that actually settles it, which is potions.py's and not mine:
#   ONE DRAUGHT PER TURN, AND ONLY A RESOLVED CAST CREATES THE NEXT TURN. Forty
#   potions would be forty turns, which is forty more lines of Python than the
#   player would otherwise have written. The pouch is spent at the speed the
#   player writes Python and at no other speed.
#
# RESTOCK is measured in CLEARED ENCOUNTERS IN THAT REGION, not in days and not
# in real time. A clock would pay for waiting, and this file does not pay for
# waiting. Six clears restores one unit to every line the vendor carries. A
# vendor fully drained is therefore about thirty fights from full — long enough
# that draining one is a decision, short enough that it is never a wall.
RESTOCK_EVERY = 6
VENDOR_STOCK = dict(potions.CARRY_CAP)


@dataclass(frozen=True)
class Vendor:
    region: str
    name: str
    trade: str        # what they were before they sold bottles
    lines: tuple      # two, and they are the whole characterisation

    @property
    def band(self) -> str:
        return area_band(self.region)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update({"band": self.band, "lines": list(self.lines),
                  "region_name": world.REGION_BY_ID.get(
                      self.region, {}).get("name", self.region)})
        return d


# Seventeen regions, seventeen people. The brief called this seventeen chances to
# make a region feel inhabited, which is the correct amount of pressure to put on
# a shopkeeper. Each one is a local: their trade is the region's own physics, and
# their two lines are the only two things they ever need to say.
VENDORS: tuple = (
    Vendor("python_village", "MOTHER SEDGE", "baker",
           ("The oven still works. That is most of what I have to say about "
            "this village.",
            "Red is for blood. Violet is for thinking. Do not confuse them in "
            "the dark.")),
    Vendor("fields_of_syntax", "BRAMBLE OAT", "weeder's boy with a handcart",
           ("Thimbles only. You are not in enough trouble yet for a vial.",
            "Everything out here is half a sentence. The tonic is not. The "
            "tonic is finished.")),
    Vendor("hashmap_highlands", "KEEPER ANWYLL", "vault clerk",
           ("One bottle, one key, one shelf. I have never once had to look for "
            "anything.",
            "If you want it faster than that you want a different shop, and a "
            "worse one.")),
    Vendor("stringwood_labyrinth", "PERRIN LOOM", "letter-gatherer",
           ("Same letters, different order, different cure. Read the label "
            "twice.",
            "The trees rearrange themselves nightly. My shelves do not. That is "
            "the service.")),
    Vendor("array_caverns", "NEVE NULL-INDEX", "alcove-keeper",
           ("Alcove zero is the first one. I am not having that argument again "
            "today.",
            "Count what you are carrying before you pay me. The last one is "
            "one short of the total.")),
    Vendor("sliding_window_marsh", "WADE HOLLOWAY", "punt-hand",
           ("The stall moves. Widen to the right and it will come to you.",
            "Green milk, for the marsh. You will want it some while before you "
            "think you want it.")),
    Vendor("twin_pointer_pass", "INGA TWOCAIRN", "bridge-warden",
           ("Two stalls. One at each end. Whichever you reach first is the one "
            "I am at.",
            "Cold work up here. Buy the red before you are cold enough to want "
            "it.")),
    Vendor("stack_queue_mines", "ASH KETTLE", "cart foreman",
           ("Top of the cart or nothing. I am not digging down for a thimble.",
            "The lift takes the oldest first. So do I. So should you.")),
    Vendor("matrix_citadel", "QUARTERMASTER ODILE", "garrison quartermaster",
           ("Row, column, price. Three numbers, and none of them is negotiable.",
            "When the floor turns, hold the flask. I have seen what happens to "
            "those who do not.")),
    Vendor("recursive_forest", "HOB UNDERLEAF", "the smaller merchant",
           ("There is a smaller shop than this further in. He sells the same "
            "things. He is also me.",
            "Buy on the way down. On the way back up you will be carrying what "
            "the inner one found.")),
    Vendor("binary_tree_canopy", "ROOKERY PELL", "branch-rigger",
           ("Left branch or right branch. There is no third. Choose, and I will "
            "not ask twice.",
            "Everything I sell is up here. Getting down again is entirely your "
            "own business.")),
    Vendor("graph_wastes", "TINKER MALLOW", "cart-router",
           ("Every ruin connects to this cart. Not all of them connect quickly.",
            "Shortest road or any road at all. My prices are the same either "
            "way.")),
    Vendor("dp_ruins", "LARK OF THE LIT TILES", "ledger-keeper",
           ("You bought this in the spring. I remember, so that you do not have "
            "to.",
            "Nothing here is ever paid for twice. That is the whole of the "
            "local religion.")),
    Vendor("debugging_dungeon", "MATRON QUILL", "infirmarian",
           ("The Armorer mends the plate. I mend what was inside the plate.",
            "Tell me where it hurts, not what you think it is. Those are two "
            "different sentences.")),
    Vendor("complexity_tower", "STEWARD AMAR", "floor steward",
           ("The stall one floor down was cheaper. It is also one floor further "
            "than you want to walk.",
            "Every floor doubles. My prices do not, and you may take that as "
            "generosity.")),
    Vendor("coding_coliseum", "VIRE SANDSIDE", "gate-seller",
           ("No hints in there. A flask is not a hint. I have that ruling in "
            "writing.",
            "You drink it in the sand, in front of everyone. Decide now whether "
            "you mind.")),
    Vendor("null_kings_castle", "OSK THE LAMPLIGHTER", "lamplighter",
           ("Nothing in the castle is labelled. My bottles are. That is why I "
            "am expensive.",
            "Take the flagon. You will not be able to read the wall at the "
            "moment you need to.")),
)

VENDOR_BY_REGION = {v.region: v for v in VENDORS}


def vendor_for(region_id: str) -> Vendor | None:
    return VENDOR_BY_REGION.get(region_id)


def stock_list(region_id: str) -> list:
    """What this vendor carries: every potion the region's band can produce.

    Deliberately the whole band and not just its top: a deep vendor still sells
    thimbles. `potions.sip_multiplier` already makes a fistful of thimbles worse
    than one flagon inside a single fight, so there is no exploit to close, and
    the cheap line is what a broke player buys on the way back out.
    """
    return potions.available_at(area_band(region_id))


def _vendor_room(state: dict, region_id: str) -> dict:
    room = _economy(state)["vendors"].setdefault(region_id, {})
    room.setdefault("clears", 0)    # progress toward the next restock
    room.setdefault("credit", 0)    # quests.VENDOR_CREDIT, spendable here only
    stock = room.setdefault("stock", {})
    for pid in stock_list(region_id):
        p = potions.potion(pid)
        stock.setdefault(pid, VENDOR_STOCK.get(p.strength, 1) if p else 1)
    return room


def restock(state: dict, region_id: str, *, clears: int = 1) -> dict:
    """Credit cleared encounters toward this region's shelves.

    Call once per CLEARED encounter in the region. Failures buy nothing, here as
    everywhere else in the file.
    """
    if vendor_for(region_id) is None:
        return {"restocked": {}, "clears": 0}
    room = _vendor_room(state, region_id)
    room["clears"] = int(room.get("clears", 0)) + max(0, int(clears))
    steps, room["clears"] = divmod(int(room["clears"]), RESTOCK_EVERY)
    added: dict = {}
    if steps:
        for pid, have in list(room["stock"].items()):
            p = potions.potion(pid)
            cap = VENDOR_STOCK.get(p.strength, 1) if p else 1
            new = min(cap, int(have) + steps)
            if new != have:
                added[pid] = new - int(have)
                room["stock"][pid] = new
    return {"restocked": added, "clears": int(room["clears"]),
            "next_in": RESTOCK_EVERY - int(room["clears"])}


# VENDOR CREDIT
# -------------
# quests.py grants `{"vendor_credit": {"region": ..., "amount": ...}}` and says
# in its own comment that it deliberately names no vendor, no stock and no
# price, because this module had not been written yet, and that the engine
# resolves the region to whichever vendor economy.py puts there. This is that
# resolution. Credit is spendable at ONE vendor and is spent before gold, which
# is what makes it a reward for a region rather than a smaller lump of money.

def grant_credit(state: dict, region_id: str, amount: int) -> dict:
    """Bank a quest's vendor credit against this region's shop."""
    if vendor_for(region_id) is None:
        return {"error": "no_vendor", "region": region_id}
    room = _vendor_room(state, region_id)
    room["credit"] = int(room.get("credit", 0)) + max(0, int(amount))
    return {"region": region_id, "credit": int(room["credit"]),
            "vendor": vendor_for(region_id).name}


def credit_at(state: dict | None, region_id: str) -> int:
    if state is None:
        return 0
    return int(_economy(state)["vendors"].get(region_id, {}).get("credit", 0))


def vendor_view(state: dict | None, region_id: str, *, gold: int = 0) -> dict:
    """The whole shop counter, in one call, the way forge.smith_view does it."""
    vendor = vendor_for(region_id)
    if vendor is None:
        return {"error": "no vendor", "region": region_id}
    room = _vendor_room(state, region_id) if state is not None else \
        {"stock": {pid: VENDOR_STOCK.get(potions.potion(pid).strength, 1)
                   for pid in stock_list(region_id)}, "clears": 0, "credit": 0}
    rows = []
    for pid in stock_list(region_id):
        p = potions.potion(pid)
        cost = potion_price(pid, region_id)
        rows.append({
            **p.to_dict(), "price": cost,
            "stock": int(room["stock"].get(pid, 0)),
            "cap": VENDOR_STOCK.get(p.strength, 1),
            "affordable": int(gold) + int(room.get("credit", 0)) >= cost,
            "fights": price_in_fights(pid, region_id),
            "minutes": price_in_minutes(pid, region_id),
        })
    return {
        "region": region_id, "vendor": vendor.to_dict(), "band": vendor.band,
        "gold": int(gold), "stock": rows,
        "restock_every": RESTOCK_EVERY,
        "restock_clears": int(room.get("clears", 0)),
        "restock_in": RESTOCK_EVERY - int(room.get("clears", 0)),
        "credit": int(room.get("credit", 0)),
        "regalia": regalia_shelf(state, region_id),
    }


BUY_REFUSALS = {
    "no_vendor": "Nobody sells potions here.",
    "not_stocked": "That is not something this region's shelves carry.",
    "out_of_stock": "Sold out. Come back when you have done some work.",
    "no_gold": "Not enough gold.",
    "pouch_full": "Your pouch will not hold another one of those.",
}


def buy_potion(state: dict, region_id: str, potion_id: str, *,
               gold: int = 0, quantity: int = 1) -> dict:
    """Buy from the shelf. Decrements stock, fills the pouch, REPORTS the spend.

    The pouch is `potions.grant`'s to fill, because potions.py owns the pouch and
    its carry caps. The purse is the engine's to empty, because engine.py owns the
    purse. This function owns exactly one thing — the shelf — and touching either
    of the other two from here is the bug the module docstring is about.
    """
    vendor = vendor_for(region_id)
    if vendor is None:
        return {"error": "no_vendor", "text": BUY_REFUSALS["no_vendor"]}
    p = potions.potion(potion_id)
    if p is None or potion_id not in stock_list(region_id):
        return {"error": "not_stocked", "text": BUY_REFUSALS["not_stocked"]}
    n = max(1, int(quantity))
    room = _vendor_room(state, region_id)
    have = int(room["stock"].get(potion_id, 0))
    if have < n:
        return {"error": "out_of_stock", "text": BUY_REFUSALS["out_of_stock"],
                "stock": have}
    unit = potion_price(potion_id, region_id)
    credit = int(room.get("credit", 0))
    if int(gold) + credit < unit * n:
        return {"error": "no_gold", "text": BUY_REFUSALS["no_gold"],
                "needs_gold": unit * n - int(gold) - credit, "price": unit * n}

    # Hand it over FIRST, then charge for what the pouch actually accepted.
    # potions.Pouch.add honours the carry cap and reports the overflow rather
    # than swallowing it, so buying three flagons into a pouch holding one
    # flagon costs one flagon and says so.
    granted = potions.grant(state, potion_id, n=n)
    taken = int(granted.get("added", 0))
    if taken <= 0:
        return {"error": "pouch_full", "text": BUY_REFUSALS["pouch_full"],
                "grant": granted}
    cost = unit * taken
    from_credit = min(credit, cost)
    room["credit"] = credit - from_credit
    room["stock"][potion_id] = have - taken
    spend(state, "potions", cost)
    return {
        "bought": potion_id, "name": p.name, "quantity": taken,
        "unit_price": unit, "price": cost,
        "credit_spent": from_credit,
        "gold_spent": cost - from_credit,
        "overflow": int(granted.get("overflow", 0)),
        "stock_left": room["stock"][potion_id],
        "credit_left": int(room["credit"]),
        "grant": granted,
        "line": vendor.lines[taken % len(vendor.lines)],
    }


# ==========================================================================
# SECTION 7 — ORIN TALLOW, THE ASSAYER
# ==========================================================================
#
# WHO SHE IS, AND THE NOTE ON WHY SHE IS NOT THE OTHER THING
# ----------------------------------------------------------
# The mechanic requested was a travelling challenge-broker who sets repeatable
# Python trials for gold. The shorthand offered for her was an ethnic one, and it
# is not used here and should not be added later. "Gypsy" is a slur for Romani
# people; dialect spelling and ethnic signifiers used as character shorthand
# produce a caricature rather than a character, and a caricature is also just
# weaker writing. What was actually wanted out of that shorthand — warmth, the
# road, rhythm, somebody outside the institutions who deals straight with you —
# is all here, and it is here as the biography of one specific woman.
#
# ORIN TALLOW was Third Assayer of the Fluency Office at the Highlands mint. An
# assay office is the bench where a claim about metal is settled by fire before
# anyone is allowed to spend it. Her whole trade was refusing to take anybody's
# word.
#
# The Office began certifying on reputation. A house whose silver had always run
# pure got its purity assumed, because assuming is cheaper than firing a
# crucible. She refused to sign the first certificate and was overruled. She
# refused the second and was overruled. On the third she took the touchstone and
# the scales off the bench, walked out through the yard, and did not come back.
#
# She walks because a bench that stays in a building eventually belongs to the
# building. Scales that travel cannot be leaned on. She has set up in seventeen
# regions and stayed in none of them, and she will tell you, if you ask her
# twice, that this is the only part of the arrangement she dislikes.
#
# She has never certified anybody. She reports what came out of the crucible and
# lets other people decide what that is worth. She charges nothing to set a
# trial and takes no cut of the payout; her living is that people who have been
# assayed by her tell other people where she is.
#
# HER VOICE — the rules, so that whoever writes her next keeps her
# ----------------------------------------------------------------
#   Short declarative sentences. Twelve words is long for her.
#   Metal, fire, weights and measures. She prices work aloud before it starts.
#   She quotes, then she weighs, and she does not renegotiate either one.
#   Correct is PURE. Wrong is ADULTERATED. She does not say wrong and she never
#     says "well done"; the closest she comes to praise is a number.
#   "The sample" is the work. It is never the person. She is careful about this.
#   Her warmth is exactness plus a kettle. She remembers what you failed at and
#     does not mention it unless you ask.
#   She pays in front of you and counts it twice.
#   No dialect spelling. No apostrophes standing in for an accent. She has a
#     rhythm, not an accent, and the rhythm is the short sentences.

ASSAYER = {
    "id": "orin_tallow",
    "name": "ORIN TALLOW",
    "epithet": "THE ASSAYER",
    "pronoun": "she",
    "sprite": "assayer",
    "colour": "#c9a05a",
    "accent": "#7fb0a0",
    "was": "Third Assayer of the Fluency Office, Hashmap Highlands mint",
    "carries": "a touchstone, a two-pan balance, a crucible, and a kettle",
    "why_she_walks": (
        "A bench that stays in a building eventually belongs to the building. "
        "Scales that travel cannot be leaned on."
    ),
    "law": "I do not pass people. I report metal.",
    "blurb": (
        "A woman of about sixty with a portable assay kit and a kettle already "
        "on. She sets you a piece of work, states the price before you begin, "
        "and pays it out in front of you, counting twice."
    ),
}

ASSAYER_LINES = {
    "first_meeting": (
        "Orin Tallow. I test metal. Lately I have been testing people, which is "
        "the same procedure with worse manners.",
        "You will not be graded. You will be assayed. The difference is that an "
        "assay has a number at the end of it and no opinion.",
        "The kettle is on. Sit down. I quote before the work, always.",
    ),
    "greeting": (
        "The kettle is on.",
        "Back already. Good.",
        "I have work, a price for it, and nothing else to offer you.",
        "Sit. Let us see what you are made of, in the strictly technical sense.",
    ),
    "quote": (
        "That is the price. I quote, then I weigh. Nobody argues with a scale.",
        "Stated before you start, so that you cannot be talked out of it after.",
        "The price does not move. Not up for a good result, not down for a bad "
        "one.",
    ),
    "pure": (
        "Pure. Counted twice.",
        "That came out clean. Here.",
        "No adulteration in it anywhere. Take the gold.",
        "The crucible has no opinion and neither do I. It is pure.",
    ),
    "adulterated": (
        "Adulterated. Not a judgement. A reading.",
        "Something in the sample was not what it claimed. That happens most "
        "days.",
        "It did not come out clean. The trial stands open; the fire is not "
        "going anywhere.",
    ),
    "failed_trial": (
        "The contract is closed and unpaid. You may open another one now if you "
        "like.",
        "Not paid. Also not held against you. I keep a ledger of metal, not of "
        "people.",
    ),
    "idle": (
        "I have been in seventeen places this year and liked the walking in "
        "about four of them.",
        "An assay you can buy is not an assay. That is not a saying. That is the "
        "reason I am out here.",
        "Most people want to be told they are gold. I can only tell them what "
        "they are.",
        "The Office still has my chair. It does not have the scales.",
    ),
    "personal": (
        "Three certificates. That is the whole story. I refused one, refused the "
        "second, and on the third I took the scales off the bench and walked out "
        "through the yard.",
        "I did not think of it as principle at the time. I thought of it as not "
        "being able to sign my name to a guess.",
    ),
    "on_repetition": (
        "Yes, the same area again. Repetition is not the failure mode. Repeating "
        "one answer is the failure mode, and I pay accordingly.",
        "Do the work a hundred times. Do the SAME work a hundred times and the "
        "hundredth is worth nothing to either of us.",
    ),
    "refuses_to_help": (
        "No. I set the trial. I do not sit the trial.",
        "If I told you, the number at the end would be about me.",
    ),
}


def assayer_line(key: str, rng: random.Random | None = None) -> str:
    """One of hers. Unknown keys fall back to idle rather than raising, because a
    missing line should be a dull NPC and never a crash in a shop."""
    pool = ASSAYER_LINES.get(key) or ASSAYER_LINES["idle"]
    return (rng or random.Random()).choice(pool)


# -- THE TRIALS ------------------------------------------------------------
#
# Twelve contract shapes across seventeen regions, drawing from the area's own
# problem pool, is 204 distinct standing offers with rotating contents. That is
# the answer to "enough variety that the loop does not go stale".
#
# Every demand below is a fact the engine ALREADY computes at submission time —
# hints used, rank, seconds against target, first try, is_retest, pattern, skill.
# Nothing here needs new instrumentation, and nothing here can be satisfied by
# anything except a graded submission.
#
# `bonus` is a multiplier on the area's encounter rate per problem, paid ON TOP
# of what the problems themselves pay. It is the price of the CONTRACT, not of
# the code: what the player is being paid for is the constraint held across a
# set, and a constraint held across a set is the thing an interview actually
# measures. That is also why the bonus is FLAT and does not taper. A specific
# problem can be memorised; "five in a row without a failed submission" cannot.

@dataclass(frozen=True)
class TrialForm:
    id: str
    name: str
    problems: int
    bonus: float
    demands: dict          # constraint -> value, checked per submission
    offer: str             # what Orin says when she puts it on the board
    blurb: str             # what the contract actually asks for
    band_shift: int = 0    # relative to the area band, in ladder steps
    needs_history: int = 0 # prior clears in the region before she will offer it
    puzzles_only: bool = False

    @property
    def demand_text(self) -> list:
        return [DEMAND_TEXT[k].format(v=v) for k, v in self.demands.items()
                if k in DEMAND_TEXT]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["demand_text"] = self.demand_text
        return d


DEMAND_TEXT = {
    "unaided": "no hints, and no companion speaking",
    "first_try": "clean on the first submission",
    "under_target": "inside the target time",
    "no_failures": "no failed submission anywhere in the contract",
    "retest": "problems you have not seen in days, disguised",
    "distinct_skills": "across {v} different skills",
    "distinct_kinds": "across {v} different puzzle kinds",
    "explained": "the approach stated before the implementation, both graded",
    "unlabelled": "nothing tells you which pattern it is",
}

TRIAL_FORMS: tuple = (
    TrialForm(
        "assay", "The Assay", 3, 0.45, {"unaided": True},
        "Three pieces, this region's own band, and nothing whispered to you. "
        "Standard assay. I have done ten thousand of them.",
        "Three problems at the area's band, no hints.",
    ),
    TrialForm(
        "tally", "The Tally", 5, 0.22, {},
        "Five pieces. Any quality. Some days the useful thing is volume, and I "
        "am not too proud to pay for it.",
        "Five problems at the area's band, any rank, hints allowed.",
    ),
    TrialForm(
        "crucible", "The Crucible", 1, 0.95, {},
        "One piece, and it is from a band above this one. Bring whatever tools "
        "you like. The fire does not care how you got it clean.",
        "One problem a band above the area, by any means.",
        band_shift=1,
    ),
    TrialForm(
        "quench", "The Quench", 3, 0.55, {"under_target": True},
        "Three pieces, each inside its own clock. Hints permitted. Speed is a "
        "property of metal too.",
        "Three problems, each inside target time. Hints allowed.",
    ),
    TrialForm(
        "straight_draw", "The Straight Draw", 5, 0.70, {"no_failures": True},
        "Five in a row and not one bad submission between them. The moment you "
        "hand me something adulterated, the draw is over.",
        "Five problems consecutively with no failed submission.",
        needs_history=6,
    ),
    TrialForm(
        "touchstone", "The Touchstone", 3, 0.85, {"retest": True},
        "Three things you have not touched in days, wearing different clothes. "
        "Anyone can hold a shape for an hour. I want the week.",
        "Three delayed, disguised retests.",
        needs_history=12,
    ),
    TrialForm(
        "double_pan", "The Double Pan", 4, 0.60, {"distinct_skills": 2},
        "Four pieces off two different shelves. One pan each. A person good at "
        "exactly one thing weighs less than they think.",
        "Four problems across at least two skills.",
        needs_history=4,
    ),
    TrialForm(
        "spot_assay", "The Spot Assay", 3, 0.50,
        {"distinct_kinds": 3},
        "Three readings, three different instruments. Read the code rather than "
        "writing it. It is still the same metal.",
        "Three puzzles of three different kinds.",
        puzzles_only=True,
    ),
    TrialForm(
        "flaw_hunt", "The Flaw Hunt", 2, 0.65, {"distinct_kinds": 2},
        "Find the bad line, then build the input that proves it. Two halves of "
        "one habit, and the second half is the one people skip.",
        "One SPOT_THE_FLAW and one BREAK_IT.",
        puzzles_only=True, needs_history=4,
    ),
    TrialForm(
        "proof", "The Proof", 2, 0.80, {"explained": True},
        "Say what you are about to do. Then do it. If the two do not match, I "
        "have learned something and you have not been paid.",
        "Two problems, approach stated and graded before implementation.",
        needs_history=8,
    ),
    TrialForm(
        "cold_crucible", "The Cold Crucible", 3, 1.00,
        {"unlabelled": True, "unaided": True},
        "Three pieces and nothing on the labels. No family named, no shelf "
        "given. This is the one the Office stopped running.",
        "Three unlabelled problems, no hints, pattern not named.",
        needs_history=20,
    ),
    TrialForm(
        "fire_assay", "The Fire Assay", 1, 1.35,
        {"unaided": True, "first_try": True, "under_target": True},
        "One piece from the band above. No hints, first submission, inside the "
        "clock. I will not pretend this is reasonable. It is simply the "
        "highest price I pay for a single piece, and most people do not "
        "collect it.",
        "One problem a band above the area: unaided, first try, under time.",
        band_shift=1, needs_history=30,
    ),
)

TRIAL_BY_ID = {f.id: f for f in TRIAL_FORMS}

# How many contracts stand on the board at once. Three: enough that there is a
# choice, few enough that the choice is one a person makes rather than reads.
BOARD_SIZE = 3

# A completed form goes to the back of the queue for this many completions. This
# is variety enforcement, not an income cap — see NO DAILY CAP below.
FORM_COOLDOWN = 2

# THERE IS NO DAILY CAP ON BROKER GOLD, AND THERE WILL NOT BE ONE.
#
# A cap on gold earned by doing Python is the game telling a player to stop
# practising. Every other lever in this file — the problem taper, the form
# cooldown, the vendor restock, the pouch's own carry caps — limits REPETITION OF
# ONE THING, which is the behaviour that teaches nothing. None of them limits
# volume, because volume is the entire point. A player who wants to work through
# the board all afternoon should be paid all afternoon.


def _band_shift(band: str, steps: int) -> str:
    i = curriculum.TIERS.index(band) if band in curriculum.TIERS else 2
    return curriculum.TIERS[max(0, min(len(curriculum.TIERS) - 1, i + steps))]


def trial_band(form_id: str, region_id: str) -> str:
    form = TRIAL_BY_ID.get(form_id)
    return _band_shift(area_band(region_id), form.band_shift if form else 0)


def _trial_unit(form: TrialForm, band: str) -> float:
    """What one piece of this contract is worth before the bonus.

    A PUZZLE-ONLY contract is measured on the puzzle rate, not the code-battle
    rate. This was wrong in the first draft and it was wrong in the expensive
    direction: a two-puzzle Flaw Hunt takes about ten minutes and was being paid
    a bonus sized for two full MEDIUM encounters, which is fifty. That made the
    puzzle contracts the best-paid minutes in the game and quietly inverted
    PUZZLE_RATE, which exists precisely to keep the blank screen the best seat.
    """
    if form.puzzles_only:
        mean_minutes = sum(PUZZLE_MINUTES.values()) / len(PUZZLE_MINUTES)
        return mean_minutes * gold_per_minute(band) * PUZZLE_RATE
    return float(ENCOUNTER_BASE[band])


def trial_payout(form_id: str, region_id: str) -> int:
    """The bonus Orin pays for the contract, on top of the problems' own gold.

    Quoted before the work begins and never recomputed afterwards, which is both
    her character and the correct behaviour: a payout that moves after the fact
    is a payout a player cannot plan around.
    """
    form = TRIAL_BY_ID.get(form_id)
    if form is None:
        return 0
    band = trial_band(form_id, region_id)
    return max(1, int(round(_trial_unit(form, band) * form.problems * form.bonus
                            * area_multiplier(region_id))))


# A contract may pay at most this multiple of the plain rate for the same
# minutes. The arithmetic is exact and pleasingly boring: a contract's bonus IS
# its multiple minus one, because the bonus is quoted per problem against the
# same unit the problems themselves pay. So the ceiling is a statement about
# TrialForm.bonus and nothing else.
#
# 2.35 is reached by exactly one contract, The Fire Assay, and only on the runs
# where it is WON. It demands unaided, first submission, and inside the clock, at
# a band above the region, and it is gated behind thirty completed trials. At a
# realistic one-in-three success rate on all three conditions at once, its
# EXPECTED multiple is about 1.47 — the same as every other contract on the
# board. That is the design: the headline rate is high, the earned rate is not,
# and the difference is entirely made of Python the player had to get right.
TRIAL_RATE_CEILING = 2.4


def trial_rate_ratio(form_id: str) -> float:
    """How many times the plain rate this contract pays for the same minutes."""
    form = TRIAL_BY_ID.get(form_id)
    return round(1.0 + form.bonus, 4) if form else 0.0


def trial_total_estimate(form_id: str, region_id: str) -> dict:
    """Bonus plus the expected pay of the problems inside it, so the board can
    show a real total rather than a bonus the player has to add up themselves."""
    form = TRIAL_BY_ID.get(form_id)
    if form is None:
        return {}
    band = trial_band(form_id, region_id)
    area = area_multiplier(region_id)
    inner = int(round(_trial_unit(form, band) * area * form.problems))
    bonus = trial_payout(form_id, region_id)
    return {"bonus": bonus, "problems_pay": inner, "total": bonus + inner,
            "band": band, "problems": form.problems}


def _broker(state: dict, region_id: str) -> dict:
    room = _economy(state)["broker"]
    room.setdefault("regions", {})
    per = room["regions"].setdefault(region_id, {})
    per.setdefault("done", 0)
    per.setdefault("recent", [])
    per.setdefault("board", [])
    return per


def available_forms(state: dict | None, region_id: str) -> list:
    """Which contracts she will offer here, given what the player has proved.

    `needs_history` is counted in COMPLETED TRIALS IN THIS REGION, which is
    graded evidence like everything else. She does not offer the Cold Crucible
    to somebody she has assayed twice, and the reason she gives is that it would
    waste the fire.
    """
    per = _broker(state, region_id) if state is not None else {"done": 0,
                                                               "recent": []}
    done = int(per.get("done", 0))
    recent = list(per.get("recent", []))[-FORM_COOLDOWN:]
    return [f for f in TRIAL_FORMS
            if done >= f.needs_history and f.id not in recent]


def broker_board(state: dict | None, region_id: str, *, seed: int = 0) -> dict:
    """The three contracts standing here now.

    Deterministic in (region, completions, seed), so the board does not reshuffle
    every time the player opens the panel — a board that changes when you look at
    it reads as broken, which is the same argument puzzles.shuffle_runes makes.
    """
    per = _broker(state, region_id) if state is not None else {"done": 0,
                                                               "recent": []}
    pool = available_forms(state, region_id)
    if not pool:
        pool = list(TRIAL_FORMS[:BOARD_SIZE])
    rng = random.Random(hash((region_id, int(per.get("done", 0)), seed)) & 0xFFFFFFFF)
    chosen = pool[:] if len(pool) <= BOARD_SIZE else rng.sample(pool, BOARD_SIZE)
    return {
        "region": region_id, "band": area_band(region_id),
        "broker": dict(ASSAYER),
        "greeting": assayer_line("first_meeting" if not _economy(state).get(
            "broker", {}).get("met") else "greeting", rng)
        if state is not None else ASSAYER_LINES["first_meeting"][0],
        "completed_here": int(per.get("done", 0)),
        "offers": [{**f.to_dict(), **trial_total_estimate(f.id, region_id),
                    "payout": trial_payout(f.id, region_id)} for f in chosen],
        "locked": [{"id": f.id, "name": f.name, "needs": f.needs_history,
                    "have": int(per.get("done", 0))}
                   for f in TRIAL_FORMS
                   if int(per.get("done", 0)) < f.needs_history],
    }


def open_trial(state: dict, region_id: str, form_id: str, *,
               now: float = 0.0) -> dict:
    """Take a contract. She quotes here and the quote is frozen into the state.

    One trial open at a time. Two would let a player stack the constraints of a
    gentle contract and a strict one onto the same submissions and be paid twice
    for holding one line, which is exactly the kind of thing an assayer exists to
    refuse.
    """
    form = TRIAL_BY_ID.get(form_id)
    if form is None:
        return {"error": "no_such_trial"}
    room = _economy(state)["broker"]
    if room.get("trial"):
        return {"error": "trial_open", "trial": room["trial"],
                "text": "One contract at a time. Finish or abandon that one."}
    per = _broker(state, region_id)
    if int(per.get("done", 0)) < form.needs_history:
        return {"error": "not_yet", "needs": form.needs_history,
                "have": int(per.get("done", 0)),
                "text": "Not yet. That one would waste the fire."}
    room["met"] = True
    quote = trial_payout(form_id, region_id)
    room["trial"] = {
        "form": form_id, "region": region_id, "band": trial_band(form_id, region_id),
        "need": form.problems, "done": 0, "quote": quote,
        "opened_at": float(now), "problems": [], "skills": [], "kinds": [],
        "failed": False, "closed": False,
    }
    return {"opened": form_id, "name": form.name, "quote": quote,
            "band": room["trial"]["band"], "demands": form.demand_text,
            "line": form.offer, "quote_line": assayer_line("quote")}


def submit_to_trial(state: dict, *, problem_id: str = "", solved: bool = True,
                    rank: str = "B", hints_used: int = 0, seconds: float = 0.0,
                    target_seconds: float = 0.0, first_try: bool = True,
                    is_retest: bool = False, difficulty: str = "",
                    skill: str = "", puzzle_kind: str = "",
                    pattern_shown: bool = True,
                    companion_spoke: bool = False) -> dict:
    """Offer one graded submission to the open contract.

    Every argument is something engine.py already has in hand at the moment it
    settles an encounter. Returns whether the submission counted and, if not,
    the one sentence saying why.
    """
    room = _economy(state)["broker"]
    trial = room.get("trial")
    if not trial or trial.get("closed"):
        return {"counted": False, "reason": "no_trial"}
    form = TRIAL_BY_ID.get(trial["form"])
    if form is None:
        return {"counted": False, "reason": "no_trial"}
    d = form.demands

    if not solved:
        if d.get("no_failures"):
            trial["failed"] = True
            return {"counted": False, "reason": "draw_broken", "failed": True,
                    "text": "The draw is over. Open another when you are ready."}
        return {"counted": False, "reason": "not_solved"}

    band_ok = _band(difficulty) == trial["band"] or \
        curriculum.tier_index(_band(difficulty)) >= curriculum.tier_index(trial["band"])
    if not band_ok:
        return {"counted": False, "reason": "band",
                "text": f"Below the band I quoted. That one is not on the bench."}
    if form.puzzles_only and not puzzle_kind:
        return {"counted": False, "reason": "needs_puzzle"}
    if d.get("unaided") and (int(hints_used) > 0 or companion_spoke):
        return {"counted": False, "reason": "unaided",
                "text": "Something spoke. That piece does not count toward this."}
    if d.get("first_try") and not first_try:
        return {"counted": False, "reason": "first_try"}
    if d.get("under_target") and target_seconds and seconds > float(target_seconds):
        return {"counted": False, "reason": "under_target"}
    if d.get("retest") and not is_retest:
        return {"counted": False, "reason": "retest"}
    if d.get("unlabelled") and pattern_shown:
        return {"counted": False, "reason": "unlabelled"}
    # A contract counts DISTINCT pieces, and the id is the only thing that makes
    # two submissions distinct. Without one there is nothing to compare against,
    # so an unidentified submission cannot be counted — six copies of one answer
    # used to fill a three-piece assay and collect the whole quote. The engine
    # always has `problem.id` in hand here (see CONTRACT, step 1), so this
    # refuses a caller that is wired wrong rather than a player doing anything.
    if not problem_id:
        return {"counted": False, "reason": "unidentified",
                "text": "I weigh pieces, not gestures. That one has no mark on it."}
    if problem_id in trial["problems"]:
        return {"counted": False, "reason": "already_counted",
                "text": "I have that one on the bench already."}

    trial["done"] = int(trial["done"]) + 1
    if problem_id:
        trial["problems"].append(problem_id)
    if skill and skill not in trial["skills"]:
        trial["skills"].append(skill)
    if puzzle_kind and puzzle_kind not in trial["kinds"]:
        trial["kinds"].append(puzzle_kind)
    remaining = max(0, int(trial["need"]) - int(trial["done"]))
    return {"counted": True, "done": trial["done"], "need": trial["need"],
            "remaining": remaining, "ready": remaining == 0,
            "text": assayer_line("pure") if remaining else ""}


def trial_state(state: dict | None) -> dict:
    """The open contract, or an empty dict. For the HUD strip."""
    trial = _economy(state)["broker"].get("trial") or {}
    if not trial:
        return {}
    form = TRIAL_BY_ID.get(trial.get("form"))
    # `ready` and `remaining` are the same arithmetic `submit_to_trial` returns,
    # and they belong here too. Told only in the submission payload, the fact
    # that a contract is finished and collectable survives exactly one screen
    # and dies on a page refresh — a player could stand at the board with the
    # work done and be shown nothing but the demands.
    remaining = max(0, int(trial.get("need", 0)) - int(trial.get("done", 0)))
    return {**trial, "name": form.name if form else "",
            "demands": form.demand_text if form else [],
            "remaining": remaining,
            "ready": remaining == 0 and not trial.get("failed")}


def close_trial(state: dict, *, abandon: bool = False) -> Award:
    """Settle the contract. Pays the quote, or nothing, and clears the slot.

    The set-completion demands — distinct skills, distinct puzzle kinds — are
    checked HERE rather than per submission, because they are properties of the
    set and not of any one piece of it.
    """
    room = _economy(state)["broker"]
    trial = room.get("trial")
    if not trial:
        return NOTHING
    form = TRIAL_BY_ID.get(trial["form"])
    region_id = trial["region"]
    room["trial"] = None
    if abandon or trial.get("failed") or form is None:
        return Award(gold=0, source="trial", region_id=region_id,
                     detail={"form": trial.get("form"), "abandoned": True},
                     lines=[assayer_line("failed_trial")])
    if int(trial["done"]) < int(trial["need"]):
        return Award(gold=0, source="trial", region_id=region_id,
                     detail={"form": form.id, "short": True},
                     lines=[assayer_line("failed_trial")])
    need_skills = int(form.demands.get("distinct_skills", 0))
    if need_skills and len(trial.get("skills", [])) < need_skills:
        return Award(gold=0, source="trial", region_id=region_id,
                     detail={"form": form.id, "short_skills": True},
                     lines=["Four pieces off one shelf is not two pans."])
    need_kinds = int(form.demands.get("distinct_kinds", 0))
    if need_kinds and len(trial.get("kinds", [])) < need_kinds:
        return Award(gold=0, source="trial", region_id=region_id,
                     detail={"form": form.id, "short_kinds": True},
                     lines=["Same instrument three times is one reading."])

    per = _broker(state, region_id)
    per["done"] = int(per.get("done", 0)) + 1
    per["recent"] = (list(per.get("recent", [])) + [form.id])[-8:]
    room["completed"][form.id] = int(room["completed"].get(form.id, 0)) + 1
    return Award(gold=int(trial["quote"]), source="trial", region_id=region_id,
                 base=int(trial["quote"]),
                 detail={"form": form.id, "name": form.name,
                         "problems": list(trial.get("problems", []))},
                 lines=[assayer_line("pure"),
                        f"{trial['quote']} gold. As quoted."])


# ==========================================================================
# SECTION 8 — SINKS
# ==========================================================================
#
# Three, and the brief named all three: potions, pet regalia, and an upgrade fee
# on weapons and armour on top of materials.

# -- the upgrade fee -------------------------------------------------------
#
# WEAPONS ARE NOT OURS. forge.GOLD_SHAPE already prices every rung, forge.quote()
# already shows it, forge.upgrade() already reports gold_spent and deliberately
# does not deduct. `weapon_fee` reads that table. It does not have one.
#
# ARMOUR IS OURS, because nothing priced it. items.UPGRADE_PATHS gates gear on
# graded evidence and charges nothing, and the brief asks for gold on top of
# materials for armour as well as weapons.
#
# The fee is keyed on the rarity being upgraded INTO, and the numbers are set so
# that carrying a full set of armour up three rarity steps costs about what one
# weapon ladder costs. That is deliberate: the brief's own design is that
# monsters gain multiple affinities and the player answers with COMBINATIONS of
# armour and weapons. If armour were much cheaper than weapons the answer would
# always be more armour, and if it were much dearer nobody would ever build the
# second combination. Equal cost makes it a real choice.
ARMOUR_FEE = {"COMMON": 20, "UNCOMMON": 45, "RARE": 100, "EPIC": 220,
              "LEGENDARY": 450, "MYTHIC": 850}


def armour_fee(rarity: str) -> int:
    """The smith's labour on a piece of armour, in gold, on top of the metal."""
    return int(ARMOUR_FEE.get(str(rarity).upper(), 0))


def weapon_fee(blade_id: str, to_tier: int) -> int:
    """forge.py's number, read rather than copied."""
    blade = forge.BLADE_BY_ID.get(blade_id)
    if blade is None:
        return int(forge.GOLD_SHAPE.get(int(to_tier), 0))
    r = blade.rung(int(to_tier))
    return int(getattr(r, "gold", 0)) if r is not None else 0


def upgrade_fee(*, item_id: str = "", blade_id: str = "", to_tier: int = 0,
                to_rarity: str = "") -> dict:
    """One door for both, so a caller does not have to know who owns which.

    Weapons route to forge and say so in `owner`, which is there specifically so
    that a future reader who wonders why weapon prices are not in this file gets
    an answer from the return value rather than from the git history.
    """
    if blade_id or (item_id and item_id in forge.BLADE_BY_ID):
        bid = blade_id or item_id
        return {"gold": weapon_fee(bid, to_tier), "owner": "forge",
                "kind": "weapon", "blade": bid, "tier": int(to_tier),
                "note": "forge.GOLD_SHAPE owns weapon labour. This reads it."}
    rarity = to_rarity
    if not rarity and item_id:
        target = items.UPGRADE_PATHS.get(item_id, {}).get("to", "")
        piece = items.BY_ID.get(target) or items.BY_ID.get(item_id)
        rarity = getattr(piece, "rarity", "")
        if getattr(piece, "slot", "") == "weapon":
            return {"gold": 0, "owner": "items", "kind": "weapon",
                    "note": "An items.UPGRADE_PATHS weapon. Gated on evidence, "
                            "not gold; forge owns the priced ladder."}
    return {"gold": armour_fee(rarity), "owner": "economy", "kind": "armour",
            "rarity": str(rarity).upper(), "item": item_id,
            "note": "Labour only. The metal is forge's and the evidence is items'."}


# -- regalia ---------------------------------------------------------------
#
# THE TACK IS NOT OURS. `quests.REGALIA` owns it outright: seven authored pieces,
# each keyed to a region, each moving exactly two numbers —
# `pets.BondRank.threshold_scale` and `pets.BondRank.interventions` — with a hard
# key whitelist and `_regalia_grants_no_depth()` proving that a piece can carry
# no effect at all, let alone a depth-gated one. `quests.companion_speech()` is
# the single door through which the two levers reach a companion.
#
# That is the correct design and it is already built, so this module adds no
# second effect, no second table and no second door. What it adds is the part
# quests.py cannot have: A PRICE AND A SHELF.
#
# The brief asked that upgrading a companion be a gold sink, and that a piece
# buy MORE hints and never DEEPER ones — which is the same rule quests.py is
# already proving, so buying a piece with gold instead of earning it with a quest
# changes nothing about what it does. It changes only how you got it.
#
# RELATIVE TO THEIR AREA, which the brief asked for by name: each piece already
# names a region, and the vendor of that region is the one who sells it. A piece
# is therefore bought where its region is, worn anywhere, and named after the
# place that taught the animal the trick. The regional tie is quests.py's and
# this module simply shelves it where it belongs.

# Price is quoted in MINUTES OF PLAY IN THE PIECE'S OWN REGION, the same unit the
# potions use and for the same reason: a fight in the Fields is three minutes and
# a fight in the Wastes is twenty-five, so "forty fights" is not a price, it is
# two different prices wearing one label.
#
# A hundred minutes is the base. That is most of a session for the plainest
# piece, which is the right weight for a permanent upgrade to the animal walking
# next to you — and remember only ONE piece is worn at a time
# (quests.REGALIA_ACTIVE_LIMIT), so the shelf is a choice and not a checklist.
#
# The multiplier on interventions is much larger than the one on earliness,
# because an extra intervention is the stronger of the two levers by a distance:
# speaking sooner is worth something in a fight you were going to win anyway, and
# speaking again is worth something in the fight you were not.
REGALIA_MINUTES = 100.0
REGALIA_INTERVENTION_WEIGHT = 0.85   # per extra intervention the piece grants
REGALIA_EARLINESS_WEIGHT = 2.2       # per unit of threshold_scale bought down


def regalia_catalogue() -> dict:
    """quests.REGALIA, read live. Nothing is copied, so a piece added there is on
    the shelves here the moment it lands, priced, with no edit to this file."""
    return dict(quests.REGALIA)


def regalia_price(regalia_id: str) -> int:
    """What this piece of tack costs in gold."""
    piece = quests.REGALIA.get(regalia_id)
    if piece is None:
        return 0
    region = piece.get("region", "")
    band = area_band(region)
    base = REGALIA_MINUTES * gold_per_minute(band) * area_multiplier(region)
    earliness = max(0.0, 1.0 - float(piece.get("threshold_scale", 1.0)))
    weight = (1.0
              + REGALIA_INTERVENTION_WEIGHT * int(piece.get("interventions", 0))
              + REGALIA_EARLINESS_WEIGHT * earliness)
    return max(1, int(round(base * weight)))


def regalia_sold_at(region_id: str) -> list:
    """The pieces this region's vendor carries."""
    return [rid for rid, piece in quests.REGALIA.items()
            if piece.get("region") == region_id]


def owns_regalia(state: dict | None, regalia_id: str) -> bool:
    """quests.py's owned list is the one list. There is not a second one."""
    if state is None:
        return False
    return any(r["id"] == regalia_id for r in quests.owned_regalia(state))


def regalia_shelf(state: dict | None, region_id: str) -> list:
    """The regalia counter, priced, with what is already owned marked."""
    rows = []
    for rid in regalia_sold_at(region_id):
        piece = quests.REGALIA[rid]
        rows.append({
            "id": rid, **piece, "price": regalia_price(rid),
            "owned": owns_regalia(state, rid),
            "rule": "More often, and sooner. Never deeper.",
        })
    return rows


def buy_regalia(state: dict, regalia_id: str, *, gold: int = 0,
                region_id: str = "") -> dict:
    """Buy a piece of tack. Reports the spend and the GRANT; applies neither.

    The grant is returned in quests.py's own reward vocabulary —
    `{"regalia": rid}` — so the engine settles it through exactly the code path
    it already uses for a quest that pays regalia. This module does not write
    into another module's owned list, any more than it writes into the purse.
    """
    piece = quests.REGALIA.get(regalia_id)
    if piece is None:
        return {"error": "no_such_regalia"}
    if region_id and piece.get("region") != region_id:
        return {"error": "wrong_region", "region": piece.get("region", ""),
                "text": "Not sold here. Try where the animal learned it."}
    if owns_regalia(state, regalia_id):
        return {"error": "already_owned"}
    cost = regalia_price(regalia_id)
    if int(gold) < cost:
        return {"error": "no_gold", "needs_gold": cost - int(gold),
                "price": cost}
    spend(state, "regalia", cost)
    return {"bought": regalia_id, "name": piece.get("name", ""),
            "gold_spent": cost, "grant": {"regalia": regalia_id},
            "region": piece.get("region", ""),
            "text": piece.get("blurb", ""),
            "note": "Apply `grant` through the quest-reward path. Wearing it is "
                    "quests.wear_regalia; one piece at a time, as ever."}


def regalia_speech(state: dict | None, *, bond: int = 0) -> dict:
    """A pass-through to quests.companion_speech, and deliberately nothing more.

    It exists so that a caller reading this module does not have to be told
    twice where the answer lives, and so that the absence of a depth field in the
    return value is visible from here too.
    """
    if state is None:
        rank = pets.bond_rank(int(bond))
        return {"rank": rank.key, "threshold_scale": rank.threshold_scale,
                "interventions": rank.interventions, "regalia": ""}
    return quests.companion_speech(state, int(bond))


# WHO OWNS WHICH TACK, NOW THAT THERE ARE TWO BODIES OF IT
# ---------------------------------------------------------
# A sibling pass landed `gauntlet/regalia.py` while this file was being written,
# and the two do not overlap once you know which is which:
#
#   regalia.py     TWENTY-FOUR objects keyed to a COMPANION — the jade collar
#                  for the jaguar and the mystic scarf for the penguin among
#                  them. Earned by evidence in that animal's own skill, and its
#                  docstring says in as many words that none of them has a price
#                  and that `_prove_no_effect_keys` exists to stop a later pass
#                  adding one. This module therefore does not sell them, does
#                  not price them, and does not put them on a shelf.
#
#   quests.REGALIA SEVEN pieces keyed to a REGION, awarded by quest turn-ins —
#                  and regalia.py's own docstring describes them as "priced on a
#                  shelf by economy.py", which is what the code above does.
#
# An earlier draft of this file proposed nine more region-keyed pieces, a jade
# collar and a mystic scarf among them, because at the time nothing in the game
# had either and the brief asked for both by name. regalia.py has since authored
# both properly — keyed to the right animals, with a home-region rule and proofs
# behind them. The proposal is deleted rather than reconciled: two jade collars
# would be worse than none, and the one that belongs to the jaguar is the right
# one.
#
# The boundary is checked rather than trusted. `validate()` imports regalia.py if
# it can and asserts that no id it owns is ever on an economy shelf. The import
# is wrapped because a sibling module mid-edit must not be able to stop the
# economy from loading, and a skipped check is better than a false one.

def _sibling_regalia_ids() -> frozenset:
    """The ids regalia.py owns, or an empty set if it cannot be read right now."""
    try:
        from . import regalia as _sibling
        return frozenset(getattr(_sibling, "BY_ID", {}))
    except Exception:
        return frozenset()



# ==========================================================================
# SECTION 9 — THE BALANCE, WITH ITS WORKING SHOWN
# ==========================================================================
#
# An estimate of gold per hour needs a model of an hour, and the model is stated
# rather than assumed. Two constants, both arguable, both visible:
#
#   SOLVE_FACTOR — wall clock against target_seconds. 1.15, because a player at
#       B or A rank is near target by definition of the rank, and reading the
#       statement plus one failed submission pushes them a little over.
#
#   ENCOUNTER_OVERHEAD — seconds around the fight that are not the fight: the
#       reward screen, the loot, walking, choosing the next one. 75 seconds.
#
# Change either and every figure below moves. That is the point of naming them.
SOLVE_FACTOR = 1.15
ENCOUNTER_OVERHEAD = 75.0

# The mix a player actually meets, measured from the corpus, region by region.
# `measure_region_mix()` recomputes any row from the live corpus; the table is
# frozen here so that pricing a potion does not load 1,013 problems.
REGION_MIX = {
    "python_village":       {"GUIDED": 92, "TUTORIAL": 77, "EASY": 34, "MEDIUM": 3},
    "fields_of_syntax":     {"GUIDED": 70, "TUTORIAL": 69, "EASY": 78, "MEDIUM": 38, "HARD": 1},
    "hashmap_highlands":    {"GUIDED": 10, "TUTORIAL": 12, "EASY": 36, "MEDIUM": 8, "HARD": 2},
    "stringwood_labyrinth": {"GUIDED": 9, "TUTORIAL": 6, "EASY": 14, "MEDIUM": 5, "HARD": 1},
    "array_caverns":        {"GUIDED": 7, "TUTORIAL": 7, "EASY": 16, "MEDIUM": 13},
    "sliding_window_marsh": {"GUIDED": 7, "TUTORIAL": 5, "EASY": 21, "MEDIUM": 20, "HARD": 3},
    "twin_pointer_pass":    {"GUIDED": 8, "TUTORIAL": 7, "EASY": 18, "MEDIUM": 9, "HARD": 2},
    "stack_queue_mines":    {"GUIDED": 13, "TUTORIAL": 9, "EASY": 25, "MEDIUM": 16, "HARD": 1},
    "matrix_citadel":       {"GUIDED": 2, "TUTORIAL": 3, "EASY": 1, "MEDIUM": 6, "HARD": 1},
    "recursive_forest":     {"GUIDED": 6, "TUTORIAL": 4, "EASY": 6, "MEDIUM": 7, "HARD": 1},
    "binary_tree_canopy":   {"GUIDED": 5, "TUTORIAL": 5, "EASY": 9, "MEDIUM": 8, "HARD": 1},
    "graph_wastes":         {"GUIDED": 8, "TUTORIAL": 2, "EASY": 12, "MEDIUM": 9, "HARD": 3},
    "dp_ruins":             {"GUIDED": 8, "TUTORIAL": 1, "EASY": 7, "MEDIUM": 16, "HARD": 3},
    "debugging_dungeon":    {"GUIDED": 6, "TUTORIAL": 5, "EASY": 25, "MEDIUM": 27, "HARD": 1},
    "complexity_tower":     {"GUIDED": 4, "EASY": 16, "MEDIUM": 9, "HARD": 2},
    "coding_coliseum":      {"GUIDED": 3, "TUTORIAL": 3, "EASY": 3, "MEDIUM": 2, "HARD": 1},
    # The castle authors no problems of its own. It draws from everywhere,
    # unlabelled, so it is modelled at its own BOSS band rather than from a pool.
    "null_kings_castle":    {"MEDIUM": 1, "HARD": 1},
}

# THE SCAFFOLD BANDS ARE DROPPED FROM THE STEADY-STATE MIX, and this is not a
# convenience. curriculum.SCAFFOLD_LADDER ends the scaffold after eight unaided
# clears and six more at TUTORIAL or harder — fourteen encounters, once, near the
# beginning — and `curriculum.scaffold_target` returns None for good afterwards.
# A player is served GUIDED and TUTORIAL in their first session and then almost
# never again, so counting a region's forty GUIDED warm-ups as forty encounters a
# player will meet would understate every income figure in this report by a third.
# The first-session income is genuinely tiny and genuinely does not matter: there
# is nothing to buy yet.
STEADY_BANDS = tuple(b for b in ENCOUNTER_BASE
                     if b not in ("GUIDED", "TUTORIAL"))

REFERENCE_REGION = "sliding_window_marsh"
REFERENCE_MIX = {b: n for b, n in REGION_MIX[REFERENCE_REGION].items()
                 if b in STEADY_BANDS}

# The regions a player actually walks through on the way to rung nine, in unlock
# order, skipping the town (no metal, no fights worth counting) and the castle
# (which is the exam, not a grind). Fourteen regions; forge.grind_estimate says
# the ladder is 449 encounters, so this is about thirty-two fights each.
CAMPAIGN_WALK = ("fields_of_syntax", "hashmap_highlands", "array_caverns",
                 "stringwood_labyrinth", "sliding_window_marsh",
                 "stack_queue_mines", "twin_pointer_pass", "debugging_dungeon",
                 "matrix_citadel", "recursive_forest", "binary_tree_canopy",
                 "complexity_tower", "dp_ruins", "graph_wastes")

# The rank mix. A player who is learning is mostly B with A on the ones they
# know, and this is the softest assumption in the report.
REFERENCE_RANKS = {"S": 0.10, "A": 0.25, "B": 0.45, "C": 0.20}


def _mean_rank_pay() -> float:
    return sum(RANK_PAY[r] * w for r, w in REFERENCE_RANKS.items())


def steady_mix(region_id: str) -> dict:
    """A region's problem mix with the scaffold bands removed. See STEADY_BANDS."""
    raw = REGION_MIX.get(region_id) or REGION_MIX[REFERENCE_REGION]
    out = {b: n for b, n in raw.items() if b in STEADY_BANDS}
    return out or {area_band(region_id): 1}


def hour_model(region_id: str = REFERENCE_REGION, mix: dict | None = None) -> dict:
    """How many encounters an hour is, and what they pay, in one region."""
    mix = mix or steady_mix(region_id)
    total = sum(mix.values()) or 1
    minutes = sum(BATTLE_MINUTES[b] * n for b, n in mix.items()) / total
    wall = minutes * 60.0 * SOLVE_FACTOR + ENCOUNTER_OVERHEAD
    per_hour = 3600.0 / wall
    area = area_multiplier(region_id)
    rk = _mean_rank_pay()
    base = sum(ENCOUNTER_BASE[b] * n for b, n in mix.items()) / total
    fight = base * area * rk
    purse = sum(expected_purse(region_id=region_id, difficulty=b) * n
                for b, n in mix.items()) / total
    return {
        "region": region_id, "depth": area_depth(region_id), "area": area,
        "mean_target_minutes": round(minutes, 2),
        "wall_seconds": round(wall, 1),
        "encounters_per_hour": round(per_hour, 2),
        "mean_rank_pay": round(rk, 3),
        "gold_per_encounter": round(fight, 2),
        "expected_purse_per_encounter": round(purse, 2),
        "gold_per_hour_fighting": round((fight + purse) * per_hour, 1),
    }


def broker_hour(region_id: str = REFERENCE_REGION) -> dict:
    """What working the board adds. The mid-weight contracts, not the best one,
    because a player picking the single most profitable form every time is not
    the ordinary hour this report is about."""
    model = hour_model(region_id)
    forms = [TRIAL_BY_ID[f] for f in ("assay", "tally", "quench", "double_pan")]
    bonus_per_problem = sum(
        trial_payout(f.id, region_id) / f.problems for f in forms) / len(forms)
    # Scaled by BOARD_FETCH_RATE, because not every encounter counts toward the
    # open contract: a player fetches the work Orin asked for about two times in
    # three. Without this correction the closed form ran nearly twice the income
    # the simulation actually produced, which is the sort of model that gets a
    # feature shipped and then quietly retuned in a patch.
    earned = bonus_per_problem * BOARD_FETCH_RATE
    return {
        **model,
        "mean_bonus_per_problem": round(bonus_per_problem, 2),
        "expected_bonus_per_encounter": round(earned, 2),
        "gold_per_hour_with_broker": round(
            (model["gold_per_encounter"] + model["expected_purse_per_encounter"]
             + earned) * model["encounters_per_hour"], 1),
    }


def campaign_income(fights: int = 0, *, with_broker: bool = False) -> dict:
    """What the whole walk pays, region by region, rather than one region twice.

    This is the figure the verdict is taken from. The single-region hour above is
    the one a player feels; this is the one the sinks are actually paid out of,
    and they are different by about a quarter because the walk starts in the
    Fields, where a fight is worth four gold.
    """
    total = int(fights or forge.grind_estimate("calipers")["blades"]
                ["analysts_calipers"]["total_encounters"])
    each = total / len(CAMPAIGN_WALK)
    gold = 0.0
    minutes = 0.0
    rows = []
    for region in CAMPAIGN_WALK:
        m = hour_model(region)
        per = m["gold_per_encounter"] + m["expected_purse_per_encounter"]
        if with_broker:
            per += broker_hour(region)["expected_bonus_per_encounter"]
        gold += per * each
        minutes += each * m["wall_seconds"] / 60.0
        rows.append({"region": region, "band": area_band(region),
                     "per_encounter": round(per, 2),
                     "encounters": round(each, 1)})
    return {"fights": total, "regions": rows,
            "gold": int(round(gold)), "hours": round(minutes / 60.0, 1),
            "gold_per_hour": round(gold / max(0.01, minutes / 60.0), 1),
            "with_broker": with_broker}


# -- the simulation -------------------------------------------------------
#
# The closed-form model above is useful and it is optimistic, and the gap is
# worth knowing about rather than arguing about. It assumes every encounter
# carries a broker bonus, which no real session manages: a contract asks for work
# at the region's band, a player fetches it most of the time and not all of the
# time, and there are gaps between closing one contract and opening the next.
#
# So the verdict is taken from a SIMULATED campaign instead. It plays the real
# award functions, the real trial machinery and the real taper against a pool of
# synthetic problems sized and banded from REGION_MIX, which means the taper
# actually bites: a region holding forty-four steady problems over thirty-two
# fights repeats some of them, and the simulation pays the repeat rate for them
# exactly as the game would.
#
# BOARD_FETCH_RATE is the one behavioural assumption. 0.66 — two encounters in
# three, a player who is working the board goes and gets the kind of work Orin
# asked for, and the third time they fight whatever was in front of them.
BOARD_FETCH_RATE = 0.66
SIM_SEEDS = 5
SIM_RANKS = (("S", 0.10), ("A", 0.25), ("B", 0.45), ("C", 0.20))
# About one encounter in seven is one of the six puzzle kinds, which is roughly
# their share of the corpus (136 of 1,013 once the non-puzzle kinds are removed).
SIM_PUZZLE_SHARE = 0.14


def _sim_pool(region_id: str) -> list:
    """Synthetic problems for one region: the real band mix, the real count."""
    pool = []
    for band, n in steady_mix(region_id).items():
        for i in range(int(n)):
            pool.append((f"{region_id}:{band}:{i}", band))
    return pool


def simulate_campaign(*, fights: int = 0, work_board: bool = True,
                      seed: int = 1) -> dict:
    """One playthrough's worth of gold, played rather than estimated."""
    total = int(fights or forge.grind_estimate("calipers")["blades"]
                ["analysts_calipers"]["total_encounters"])
    each = max(1, total // len(CAMPAIGN_WALK))
    rng = random.Random(seed)
    state: dict = {}
    gold = 0
    minutes = 0.0
    trials = 0
    kinds = list(PUZZLE_MINUTES)
    for region in CAMPAIGN_WALK:
        pool = _sim_pool(region)
        if work_board:
            open_trial(state, region, "assay")
        for _ in range(each):
            trial = trial_state(state)
            want = trial.get("band", "")
            candidates = pool
            if want and rng.random() < BOARD_FETCH_RATE:
                at_band = [row for row in pool
                           if curriculum.tier_index(row[1])
                           >= curriculum.tier_index(want)]
                candidates = at_band or pool
            pid, band = rng.choice(candidates)
            rank = _weighted_rank(rng)
            puzzle = rng.random() < SIM_PUZZLE_SHARE
            kind = rng.choice(kinds) if puzzle else ""
            if puzzle:
                award = puzzle_award(state, region_id=region, difficulty=band,
                                     kind=kind, problem_id=pid, rank=rank)
                minutes += PUZZLE_MINUTES[kind] * SOLVE_FACTOR
            else:
                award = encounter_award(state, region_id=region, difficulty=band,
                                        rank=rank, problem_id=pid)
                minutes += BATTLE_MINUTES[band] * SOLVE_FACTOR
            minutes += ENCOUNTER_OVERHEAD / 60.0
            gold += record(state, award)["gold"]
            gold += record(state, roll_purse(region_id=region, difficulty=band,
                                             rank=rank, rng=rng))["gold"]
            restock(state, region, clears=1)
            if work_board:
                got = submit_to_trial(state, problem_id=pid, difficulty=band,
                                      skill=band, hints_used=0,
                                      puzzle_kind=kind, seconds=0.0,
                                      target_seconds=0.0)
                if got.get("ready"):
                    gold += record(state, close_trial(state))["gold"]
                    trials += 1
                    forms = [f.id for f in available_forms(state, region)
                             if not f.demands.get("retest")
                             and not f.demands.get("unlabelled")]
                    if forms:
                        open_trial(state, region, rng.choice(forms))
        close_trial(state, abandon=True)
    hours = minutes / 60.0
    return {"fights": each * len(CAMPAIGN_WALK), "gold": gold,
            "hours": round(hours, 1),
            "gold_per_hour": round(gold / max(0.01, hours), 1),
            "trials": trials, "work_board": work_board,
            "earned": dict(_economy(state)["earned"]),
            "tapering": ledger_view(state)["problems_tapering"]}


def _weighted_rank(rng: random.Random) -> str:
    roll = rng.random()
    running = 0.0
    for rank, share in SIM_RANKS:
        running += share
        if roll <= running:
            return rank
    return "B"


def simulate_all(*, seeds: int = SIM_SEEDS) -> dict:
    """The simulation averaged over several seeds, both ways."""
    out = {}
    for board in (False, True):
        runs = [simulate_campaign(work_board=board, seed=s)
                for s in range(1, seeds + 1)]
        out["with_broker" if board else "fighting_only"] = {
            "gold": int(round(sum(r["gold"] for r in runs) / len(runs))),
            "hours": round(sum(r["hours"] for r in runs) / len(runs), 1),
            "gold_per_hour": round(sum(r["gold_per_hour"] for r in runs)
                                   / len(runs), 1),
            "trials": round(sum(r["trials"] for r in runs) / len(runs), 1),
            "fights": runs[0]["fights"],
            "earned": runs[0]["earned"],
        }
    return out


def cost_of_living() -> dict:
    """What the things worth buying actually cost, totalled."""
    blade = forge.grind_estimate("calipers")["blades"]["analysts_calipers"]
    ladder_gold = int(blade["total_gold"])
    ladder_fights = int(blade["total_encounters"])

    # ARMOUR, counted off the catalogue rather than guessed at. The elemental
    # pieces in items.CATALOGUE occupy exactly three non-boot slots — chest, head
    # and offhand, one ward per element — so a player answering an area's weather
    # is carrying three warded pieces and a pair of boots, not five of everything.
    # Costing a five-slot set was the first version of this line and it inflated
    # the sink by two thirds against a set the game does not actually sell.
    ward_slots = {i.slot for i in items.CATALOGUE
                  if getattr(i, "element", "") and i.slot not in ("weapon", "feet")}
    set_steps = ("EPIC", "LEGENDARY")
    armour_set = (len(ward_slots) * sum(armour_fee(r) for r in set_steps)
                  + armour_fee("RARE"))          # the boots, one step

    # Only ONE piece is worn at a time — quests.REGALIA_ACTIVE_LIMIT, which is
    # pets.ACTIVE_LIMIT. So the REQUIRED regalia spend is one good piece, and the
    # full set is a completionist's number that no player has to reach. Counting
    # the full set as a required sink was the first version of this report and it
    # returned WRONG for a game that was in fact fine.
    prices = sorted(regalia_price(rid) for rid in quests.REGALIA)
    regalia_all = sum(prices)
    regalia_one = prices[-1] if prices else 0

    # Potions: a serious dungeon run's top-up at the reference region's band.
    band = area_band(REFERENCE_REGION)
    restock_basket = sum(
        potion_price(pid, REFERENCE_REGION) *
        min(2, VENDOR_STOCK.get(potions.potion(pid).strength, 1))
        for pid in stock_list(REFERENCE_REGION))
    # POTIONS are the one RECURRING sink, and the assumption is stated twice
    # because it is the softest number in the report.
    #
    #   HEAVY:    a full shelf bought out every forty fights.
    #   MODERATE: half of that, which is the figure the verdict uses.
    #
    # Moderate, because potions also drop free — potions.POTION_DROP_CHANCE and
    # potions.CHEST_POTION_CHANCE both run on every cleared encounter — so a
    # player who buys an entire shelf every forty fights is buying a good deal of
    # what they were about to be given. Doubling this number to the heavy case
    # moves the verdict, which is exactly why it is named rather than buried.
    baskets_per_ladder = ladder_fights / 40.0
    POTION_TOPUP_SHARE = 0.5
    return {
        "weapon_ladder_gold": ladder_gold,
        "weapon_ladder_fights": ladder_fights,
        "armour_set_gold": armour_set,
        "regalia_best_piece_gold": regalia_one,
        "regalia_all_gold": regalia_all,
        "potion_basket_gold": restock_basket,
        "potion_basket_band": band,
        "potions_over_ladder_gold": int(round(restock_basket
                                              * baskets_per_ladder
                                              * POTION_TOPUP_SHARE)),
        "potions_over_ladder_heavy": int(round(restock_basket
                                               * baskets_per_ladder)),
        "baskets_per_ladder": round(baskets_per_ladder, 1),
        "topup_share": POTION_TOPUP_SHARE,
    }


def balance_report() -> dict:
    """The whole argument as numbers. A real number beats a vibe."""
    fighting = hour_model()
    with_broker = broker_hour()
    costs = cost_of_living()

    fights = costs["weapon_ladder_fights"]
    walk = campaign_income(fights)
    walk_broker = campaign_income(fights, with_broker=True)
    played = simulate_all()
    # The SIMULATION is what the verdict is read from. The closed-form walk is
    # kept beside it because a model that disagrees with the thing it models is
    # information, and the size of the disagreement is the honest error bar.
    income_over_ladder = float(played["fighting_only"]["gold"])
    broker_income = float(played["with_broker"]["gold"])

    sinks = (costs["weapon_ladder_gold"] + costs["armour_set_gold"]
             + costs["regalia_best_piece_gold"]
             + costs["potions_over_ladder_gold"])
    share_fighting = sinks / max(1.0, income_over_ladder)
    share_broker = sinks / max(1.0, broker_income)

    # The verdict is read off the CAMPAIGN income, not the reference hour, and
    # the two thresholds are the two ways an economy fails. Above 1.4, a player
    # who fights and does not work the board cannot finish the blade at all,
    # which would make gold a wall — and the rule is that nothing dead-ends for
    # want of gold. Below 0.35 with the board worked, gold has stopped being a
    # decision, and a sink nobody feels is a sink nobody thinks about.
    if share_broker > 1.0:
        verdict = ("WRONG — even a player working the board every hour cannot "
                   "afford the things worth buying.")
    elif share_fighting > 1.4:
        verdict = ("WRONG — gold is a wall for a player who does not use the "
                   "broker, and gold is never allowed to be a wall.")
    elif share_broker < 0.35:
        verdict = "SLACK — gold stops being a decision too early."
    elif share_fighting > 0.95:
        verdict = ("TIGHT, DELIBERATELY — a player who only fights must choose "
                   "between the blade, the armour set and heavy potion use. "
                   "Working Orin's board is how they stop having to choose, "
                   "which is exactly what the board is for.")
    else:
        verdict = ("TIGHT BUT NOT BINDING — everything is affordable in one "
                   "playthrough, nothing is affordable at once.")

    return {
        "hour_fighting": fighting,
        "hour_with_broker": with_broker,
        "costs": costs,
        "campaign_model": walk,
        "campaign_model_with_broker": walk_broker,
        "played": played,
        "model_optimism": {
            "fighting_only": round(walk["gold"] / max(1.0, income_over_ladder), 3),
            "with_broker": round(walk_broker["gold"] / max(1.0, broker_income), 3),
        },
        "gold_over_one_weapon_ladder": {
            "fights": fights,
            "hours": played["fighting_only"]["hours"],
            "fighting_only": int(round(income_over_ladder)),
            "with_broker": int(round(broker_income)),
            "broker_uplift": round(broker_income / max(1.0, income_over_ladder), 3),
        },
        "sinks_total": int(sinks),
        "sink_share_fighting_only": round(share_fighting, 3),
        "sink_share_with_broker": round(share_broker, 3),
        "gold_per_minute": {b: gold_per_minute(b) for b in ENCOUNTER_BASE},
        "verdict": verdict,
    }


def print_balance() -> None:
    r = balance_report()
    f, b, c = r["hour_fighting"], r["hour_with_broker"], r["costs"]
    print("GOLD PER MINUTE BY BAND")
    for band, rate in r["gold_per_minute"].items():
        mark = "  (estimated band)" if band in ESTIMATED_BANDS else ""
        print(f"  {band:9s} {rate:5.2f} gold/min   "
              f"{ENCOUNTER_BASE[band]:3d} gold / {BATTLE_MINUTES[band]:4.1f} min{mark}")
    print()
    print(f"ONE ORDINARY HOUR IN {f['region']} (depth {f['depth']}, "
          f"x{f['area']})")
    print(f"  mean target          {f['mean_target_minutes']:6.2f} min")
    print(f"  wall clock per fight {f['wall_seconds']:6.1f} s")
    print(f"  encounters per hour  {f['encounters_per_hour']:6.2f}")
    print(f"  gold per fight       {f['gold_per_encounter']:6.2f}")
    print(f"  rare purse, expected {f['expected_purse_per_encounter']:6.2f}")
    print(f"  GOLD PER HOUR        {f['gold_per_hour_fighting']:6.1f}  (fighting only)")
    print(f"  GOLD PER HOUR        {b['gold_per_hour_with_broker']:6.1f}  "
          f"(working Orin's board)")
    print()
    print("WHAT IT BUYS")
    print(f"  weapon ladder to rung nine   {c['weapon_ladder_gold']:6d} gold "
          f"over {c['weapon_ladder_fights']} fights")
    print(f"  armour set, RARE -> LEGENDARY {c['armour_set_gold']:6d} gold")
    print(f"  the best piece of regalia    {c['regalia_best_piece_gold']:6d} gold "
          f"(one is worn at a time)")
    print(f"  every piece, completionist   {c['regalia_all_gold']:6d} gold")
    print(f"  a full potion top-up         {c['potion_basket_gold']:6d} gold")
    print(f"  potions over the ladder      {c['potions_over_ladder_gold']:6d} gold "
          f"({c['baskets_per_ladder']} top-ups at {c['topup_share']:.0%} of a shelf)")
    print(f"  the same, drinking heavily   {c['potions_over_ladder_heavy']:6d} gold")
    print()
    g = r["gold_over_one_weapon_ladder"]
    print(f"OVER THE {g['fights']} FIGHTS THE LADDER TAKES "
          f"({g['hours']} hours, walked across {len(CAMPAIGN_WALK)} regions)")
    print(f"  earned, fighting only  {g['fighting_only']:6d}   (simulated, "
          f"{r['played']['fighting_only']['gold_per_hour']:.0f} gold/hour)")
    print(f"  earned, with the board {g['with_broker']:6d}   (simulated, "
          f"{r['played']['with_broker']['trials']:.0f} contracts closed)")
    print(f"  the board is worth     {g['broker_uplift']:6.2f}x")
    print(f"  sinks                  {r['sinks_total']:6d}")
    print(f"  share, fighting only   {r['sink_share_fighting_only']:.0%}")
    print(f"  share, with the board  {r['sink_share_with_broker']:.0%}")
    print(f"  closed-form model runs {r['model_optimism']['fighting_only']:.2f}x "
          f"/ {r['model_optimism']['with_broker']:.2f}x optimistic")
    print("  by source:", r["played"]["with_broker"]["earned"])
    print()
    print("VERDICT:", r["verdict"])


def potion_affordability() -> list:
    """Every potion in every region it is sold in, priced three ways."""
    rows = []
    for v in VENDORS:
        for pid in stock_list(v.region):
            rows.append({"region": v.region, "band": area_band(v.region),
                         "potion": pid,
                         "price": potion_price(pid, v.region),
                         "fights": price_in_fights(pid, v.region),
                         "minutes": price_in_minutes(pid, v.region)})
    return rows


# ==========================================================================
# SECTION 10 — RE-MEASUREMENT
# ==========================================================================
#
# The corpus is not imported at module load. Loading 1,013 problems to price a
# potion would be an absurd import cost, so the measured constants are frozen
# above with these functions to recheck them. Run them when the corpus changes.

def measure_battle_minutes() -> dict:
    """Median target_seconds per band, in minutes, from the live corpus."""
    from statistics import median
    from . import corpus
    rows: dict = {}
    for p in corpus.load():
        rows.setdefault(p.difficulty, []).append(p.target_seconds)
    return {band: round(median(v) / 60.0, 2) for band, v in rows.items()}


def measure_region_mix(region_id: str) -> dict:
    """The band mix of one region's problems, from the live corpus."""
    from . import corpus
    out: dict = {}
    for p in corpus.load():
        if p.realm == region_id:
            out[p.difficulty] = out.get(p.difficulty, 0) + 1
    return out


def measure_area_bands() -> dict:
    """The rejected measurement, kept so the rejection can be rechecked.

    Returns the mean difficulty index of each region's own problems. Fifteen of
    seventeen come out at EASY, which is why `area_band` uses unlock depth.
    """
    from . import corpus
    rows: dict = {}
    for p in corpus.load():
        rows.setdefault(p.realm, []).append(curriculum.tier_index(p.difficulty))
    return {rid: round(sum(v) / len(v), 2) for rid, v in rows.items() if v}


# ==========================================================================
# SECTION 11 — THE PROOFS
# ==========================================================================

# quests._regalia_grants_no_depth's own whitelist, restated only so the
# proposed pieces can be held to it before they are merged. If it ever diverges
# there, the check below starts failing here, which is the correct direction for
# a disagreement about somebody else's schema to travel.
_REGALIA_LEGAL_KEYS = frozenset({"name", "region", "blurb", "tell",
                                 "threshold_scale", "interventions"})


def validate() -> list:
    """Everything this module claims, checked at import. Returns problems."""
    bad: list = []

    # -- the rate is monotonic and gentle ---------------------------------
    rates = [gold_per_minute(b) for b in curriculum.TIERS if b in ENCOUNTER_BASE]
    if rates != sorted(rates):
        bad.append(f"gold per minute is not monotonic in difficulty: {rates}")
    if rates and rates[-1] / rates[0] > 2.0:
        bad.append("the top band pays more than twice the bottom band per "
                   "minute, which makes the early game a waste of time")

    # -- nothing pays for failure -----------------------------------------
    st: dict = {}
    losers = [
        encounter_award(st, region_id="graph_wastes", difficulty="HARD",
                        rank="S", problem_id="x", solved=False),
        puzzle_award(st, region_id="graph_wastes", difficulty="HARD",
                     kind="BREAK_IT", problem_id="x", solved=False),
        roll_purse(region_id="graph_wastes", difficulty="BOSS", is_boss=True,
                   solved=False, rng=random.Random(1)),
        boss_award(region_id="graph_wastes", solved=False),
        dungeon_room_award(region_id="graph_wastes", solved=False),
        quest_award(tier=5, turned_in=False),
    ]
    for a in losers:
        if a.gold:
            bad.append(f"{a.source} paid {a.gold} gold for a failure")

    # -- nothing pays for walking -----------------------------------------
    #
    # The strongest version of "gold is not paid for time" that can be checked
    # mechanically: a dungeon room that dungeons.py says demands no solving must
    # pay zero, in every region, at every depth. Imported lazily because this is
    # the only thing in the file that needs dungeons.py and a module-scope import
    # would drag the whole generator in for one frozenset.
    try:
        from . import dungeons as _dng
    except Exception:                      # pragma: no cover - dungeons optional
        _dng = None
    if _dng is not None:
        free = set(getattr(_dng, "_FREE_KINDS", ()))
        for kind in sorted(free):
            if ROOM_MULT.get(kind, 0.0) != 0.0:
                bad.append(f"room kind {kind} demands no solving and still pays")
            for region in ("fields_of_syntax", "null_kings_castle"):
                for depth in (0, 9):
                    if dungeon_room_award(region_id=region, room_kind=kind,
                                          depth=depth, solved=True).gold:
                        bad.append(f"{kind} paid gold for walking in {region}")
        # Fail closed on a kind nobody has priced, rather than paying a default.
        for kind in getattr(_dng, "ROOM_KINDS", ()):
            if kind not in ROOM_MULT:
                bad.append(f"dungeons.ROOM_KINDS has {kind}; ROOM_MULT does not")
        # And the other direction: a gated room must still be worth walking into,
        # or the fix above has quietly deleted the dungeon's reason to exist.
        gated = [k for k in getattr(_dng, "ROOM_KINDS", ())
                 if k not in free and k != "BOSS"]
        for kind in gated:
            if not dungeon_room_award(region_id="graph_wastes", room_kind=kind,
                                      depth=2, solved=True).gold:
                bad.append(f"gated room kind {kind} pays nothing at all")

    # -- the taper: area flat, problem tapering ---------------------------
    st = {}
    flat = []
    for i in range(6):
        a = encounter_award(st, region_id="array_caverns", difficulty="EASY",
                            rank="B", problem_id=f"p{i}")
        record(st, a)
        flat.append(a.gold)
    if len(set(flat)) != 1:
        bad.append(f"the area rate is not flat across distinct problems: {flat}")

    st = {}
    same = []
    for _ in range(6):
        a = encounter_award(st, region_id="array_caverns", difficulty="EASY",
                            rank="B", problem_id="one")
        record(st, a)
        same.append(a.gold)
    if same != sorted(same, reverse=True):
        bad.append(f"the problem rate does not taper: {same}")
    if same and same[-1] >= same[0]:
        bad.append("the sixth solve of one problem pays as much as the first")
    if same and same[-1] <= 0:
        bad.append("the taper reaches zero; a repeat should be cheap, not free "
                   "work")

    # -- a retest pays full and does not advance the counter --------------
    st = {}
    for _ in range(3):
        record(st, encounter_award(st, region_id="array_caverns",
                                   difficulty="EASY", problem_id="r"))
    before = taper(st, "r")
    a = encounter_award(st, region_id="array_caverns", difficulty="EASY",
                        problem_id="r", is_retest=True)
    record(st, a)
    if a.gold != encounter_award({}, region_id="array_caverns",
                                 difficulty="EASY", problem_id="r").gold:
        bad.append("a disguised retest did not pay the full rate")
    if taper(st, "r") != before:
        bad.append("a retest advanced the repeat counter")

    # -- the potion invariant, in minutes ---------------------------------
    #
    # Three claims, each checked rather than asserted:
    #   1. a bottle never costs MORE minutes in a deeper region than a shallower
    #      one. Purchasing power may rise with depth; it may never fall, or the
    #      map becomes a treadmill.
    #   2. at the band a potion is first found at, it costs between five minutes
    #      and an hour and a half of play. Under five and it is free; over that
    #      and nobody ever buys one.
    #   3. a stronger bottle always costs more than a weaker one of its kind.
    order = [b for b in curriculum.TIERS if b in ENCOUNTER_BASE]
    for pid in potions.POTION_IDS:
        pot = potions.potion(pid)
        by_band = []
        for band in order:
            region = next((v.region for v in VENDORS
                           if area_band(v.region) == band
                           and pid in stock_list(v.region)), "")
            if region:
                by_band.append((band, price_in_minutes(pid, region)))
        if not by_band:
            bad.append(f"{pid} is stocked by no vendor anywhere")
            continue
        mins = [m for _, m in by_band]
        if mins != sorted(mins, reverse=True):
            bad.append(f"{pid} costs more minutes in a deeper region: {by_band}")
        first = by_band[0][1]
        if not (5.0 <= first <= 90.0):
            bad.append(f"{pid} costs {first} minutes at its own band")
    for kind in potions.KINDS:
        ladder = [POTION_PRICE[st] for st in potions.STRENGTHS]
        if ladder != sorted(ladder):
            bad.append(f"the {kind} price ladder is not monotonic: {ladder}")

    # -- vendors ----------------------------------------------------------
    if len(VENDORS) != len(world.REGIONS):
        bad.append(f"{len(VENDORS)} vendors for {len(world.REGIONS)} regions")
    for r in world.REGIONS:
        v = vendor_for(r["id"])
        if v is None:
            bad.append(f"no vendor in {r['id']}")
            continue
        if len(v.lines) != 2:
            bad.append(f"{v.name} has {len(v.lines)} lines, not two")
        if not stock_list(r["id"]):
            bad.append(f"{v.name} has an empty shelf")
    names = [v.name for v in VENDORS]
    if len(set(names)) != len(names):
        bad.append("two vendors share a name")
    for v in VENDORS:
        for line in v.lines:
            if "!" in line:
                bad.append(f"{v.name} uses an exclamation mark")
    if VENDOR_STOCK != potions.CARRY_CAP:
        bad.append("vendor stock has drifted from potions.CARRY_CAP; the whole "
                   "defence of the cap is that they are the same number")

    # -- regalia: priced here, owned elsewhere, and never deeper ----------
    #
    # Held to quests.py's OWN constants rather than to a copy of them, so a
    # clamp changed there fails here rather than drifting silently.
    for rid, piece in quests.REGALIA.items():
        extra = set(piece) - _REGALIA_LEGAL_KEYS
        if extra:
            bad.append(f"regalia {rid} carries {sorted(extra)}; quests.py's "
                       "whitelist has moved and the price model has not")
        scale = float(piece.get("threshold_scale", 1.0))
        worst = pets.BOND_RANKS[-1].threshold_scale
        if round(scale * worst, 4) < quests.REGALIA_SCALE_FLOOR:
            bad.append(f"regalia {rid}: {scale} with Storied bond breaks "
                       f"quests.REGALIA_SCALE_FLOOR")
        if (int(piece.get("interventions", 0))
                + pets.BOND_RANKS[-1].interventions
                > quests.REGALIA_INTERVENTION_CAP):
            bad.append(f"regalia {rid} exceeds quests.REGALIA_INTERVENTION_CAP")
    for rid in quests.REGALIA:
        if regalia_price(rid) <= 0:
            bad.append(f"regalia {rid} is priced at nothing")
        if not regalia_sold_at(quests.REGALIA[rid]["region"]):
            bad.append(f"regalia {rid} is on no shelf")
    # A piece costs between an hour and four hours of play where it is sold.
    # Under an hour it is not a decision; over four it is not a purchase.
    for rid in quests.REGALIA:
        region = quests.REGALIA[rid]["region"]
        band = area_band(region)
        minutes = regalia_price(rid) / (gold_per_minute(band)
                                        * area_multiplier(region))
        if not (60.0 <= minutes <= 240.0):
            bad.append(f"regalia {rid} costs {minutes:.0f} minutes of play in "
                       f"its own region")
    # regalia.py's objects are EARNED, never bought. Nothing this module puts
    # on a shelf may be one of them. Skipped, not failed, if that module cannot
    # be read — a sibling mid-edit must not stop the economy from loading.
    theirs = _sibling_regalia_ids()
    if theirs:
        for_sale = {rid for v in VENDORS for rid in regalia_sold_at(v.region)}
        overlap = for_sale & theirs
        if overlap:
            bad.append(f"economy is selling regalia.py's objects "
                       f"{sorted(overlap)}; those are earned by evidence and "
                       "carry no price")

    # This module's speech helper reports no depth, because it is
    # quests.companion_speech and nothing else.
    speech = regalia_speech({}, bond=400)
    if "depth" in speech or "tier" in speech:
        bad.append("regalia_speech leaked a depth field")
    if speech["interventions"] != pets.bond_rank(400).interventions:
        bad.append("regalia_speech paid out with nothing worn")

    # -- trials -----------------------------------------------------------
    if len(TRIAL_BY_ID) != len(TRIAL_FORMS):
        bad.append("two trial forms share an id")
    for f in TRIAL_FORMS:
        if f.problems < 1:
            bad.append(f"{f.id} demands no problems")
        if f.bonus <= 0:
            bad.append(f"{f.id} pays no bonus")
        if "!" in f.offer:
            bad.append(f"{f.id}'s offer line uses an exclamation mark")
        for key in f.demands:
            if key not in DEMAND_TEXT:
                bad.append(f"{f.id} demands {key}, which has no player-facing "
                           "text")
    # Harder contracts pay better per problem, or nobody takes them.
    gentle = TRIAL_BY_ID["tally"].bonus
    if any(f.bonus < gentle for f in TRIAL_FORMS):
        bad.append("a constrained contract pays less per problem than the "
                   "unconstrained one")
    # And no contract outruns the ceiling. This is the guard that stops the
    # broker loop from becoming the farm it exists to replace.
    for f in TRIAL_FORMS:
        if trial_rate_ratio(f.id) > TRIAL_RATE_CEILING:
            bad.append(f"trial {f.id} pays {trial_rate_ratio(f.id)}x the plain "
                       f"rate, past the {TRIAL_RATE_CEILING}x ceiling")
    # A puzzle contract must not pay a code-battle bonus, or PUZZLE_RATE is
    # inverted by the back door.
    for f in TRIAL_FORMS:
        if f.puzzles_only and _trial_unit(f, "MEDIUM") >= ENCOUNTER_BASE["MEDIUM"]:
            bad.append(f"puzzle trial {f.id} is priced on the code-battle unit")

    # -- the six puzzle kinds, and only those ------------------------------
    #
    # puzzles.PUZZLE_KINDS is the list. A seventh kind added there and not here
    # would silently be paid at the cheapest rate, which is the kind of shortfall
    # nobody notices and everybody resents.
    missing = set(puzzles.PUZZLE_KINDS) - set(PUZZLE_MINUTES)
    if missing:
        bad.append(f"no minute estimate for puzzle kind(s) {sorted(missing)}")
    extra = set(PUZZLE_MINUTES) - set(puzzles.PUZZLE_KINDS)
    if extra:
        bad.append(f"PUZZLE_MINUTES names {sorted(extra)}, which puzzles.py has "
                   "never heard of")
    # And the whole point of PUZZLE_RATE: a puzzle minute must be worth less
    # than a blank-screen minute, at every band.
    for band in ENCOUNTER_BASE:
        for kind, minutes in PUZZLE_MINUTES.items():
            pay = minutes * gold_per_minute(band) * PUZZLE_RATE
            if pay / minutes >= gold_per_minute(band):
                bad.append(f"{kind} pays at or above the blank-screen rate at "
                           f"{band}")

    # -- the broker's voice -----------------------------------------------
    for key, pool in ASSAYER_LINES.items():
        for line in pool:
            if "!" in line:
                bad.append(f"assayer line ({key}) uses an exclamation mark")

    # -- ownership --------------------------------------------------------
    w = upgrade_fee(blade_id="analysts_calipers", to_tier=5)
    if w["owner"] != "forge" or w["gold"] != forge.GOLD_SHAPE[5]:
        bad.append("weapon fees are not coming from forge.GOLD_SHAPE")
    a = upgrade_fee(to_rarity="EPIC")
    if a["owner"] != "economy" or a["gold"] != ARMOUR_FEE["EPIC"]:
        bad.append("armour fees are not coming from this module")
    q = quest_award(tier=3, region_id="graph_wastes")
    if q.gold != quests.REWARD_TIERS[3]["gold"]:
        bad.append("quest gold is not quests.REWARD_TIERS' number")

    # -- the purse is never touched ---------------------------------------
    st = {"player": {"gold": 100}}
    record(st, encounter_award(st, region_id="array_caverns", difficulty="EASY",
                               problem_id="purse-check"))
    buy_potion(st, "array_caverns", "health_minor", gold=10_000)
    buy_regalia(st, "field_collar", gold=10_000, region_id="fields_of_syntax")
    if st["player"]["gold"] != 100:
        bad.append("something in this module wrote to the player's purse")

    # -- learning never dead-ends -----------------------------------------
    if rank_pay("LEARNING_CLEAR") <= 0:
        bad.append("a phoenix clear pays nothing, which leaves a stuck player "
                   "stuck and broke")
    if TAPER_FLOOR <= 0:
        bad.append("the taper floor is zero; a repeat becomes unpaid work")

    return bad


def self_check() -> dict:
    problems = validate()
    r = balance_report()
    return {
        "ok": not problems,
        "problems": problems,
        "vendors": len(VENDORS),
        "trial_forms": len(TRIAL_FORMS),
        "standing_offers": len(TRIAL_FORMS) * len(VENDORS),
        "regalia_priced": len(quests.REGALIA),
        "regalia_owned_by_sibling": len(_sibling_regalia_ids()),
        "gold_per_hour_fighting": r["hour_fighting"]["gold_per_hour_fighting"],
        "gold_per_hour_with_broker": r["hour_with_broker"]["gold_per_hour_with_broker"],
        "sink_share_fighting_only": r["sink_share_fighting_only"],
        "sink_share_with_broker": r["sink_share_with_broker"],
        "trial_rate_ceiling": max(trial_rate_ratio(f.id) for f in TRIAL_FORMS),
        "verdict": r["verdict"],
    }


CONTRACT = """
FOR WHOEVER IS WIRING THIS. Nothing here needs new instrumentation: every
argument is a value engine.py already holds at the moment it settles a result.

THE ONE RULE THAT MAKES THE REST SAFE
    NOTHING IN THIS MODULE TOUCHES state["player"]["gold"]. Earners return an
    Award; sinks return `gold_spent`. The engine adds and subtracts, exactly as
    it already does for forge.upgrade(). validate() proves it.

0. STATE
       engine.DEFAULT_STATE[economy.ECONOMY_STATE_KEY] = economy.new_state()

   ECONOMY_STATE_KEY == "economy". Shape:
       ledger   {problem_id: {"n": int, "at": unix_seconds}}   the taper
       earned   {source: int}          lifetime, for the codex
       spent    {sink: int}            lifetime
       vendors  {region_id: {"stock": {potion_id: int},
                             "clears": int,      restock progress
                             "credit": int}}     quests.VENDOR_CREDIT, banked
       broker   {"met": bool, "completed": {form_id: int},
                 "regions": {region_id: {"done": int, "recent": [form_id]}},
                 "trial": <the open contract, or None>}
       regalia  [] — UNUSED. quests.py owns owned regalia. Left in new_state()
                only so an old save does not trip _economy()'s defaulting.

   The pouch stays potions.POUCH_STATE_KEY. The tack stays quests.STATE_KEY. The
   purse stays state["player"]["gold"]. Three other owners, unchanged.

1. THE ENCOUNTER — engine.py's `player["gold"] += (xp // 3 + crits * 5)`
   Replace that one expression with:

       award = economy.encounter_award(
           self.state,
           region_id=enc.region, difficulty=problem.difficulty, rank=rank,
           problem_id=problem.id, solved=solved, is_retest=enc.is_retest,
           now=time.time())
       player["gold"] += economy.record(self.state, award, now=time.time())["gold"]

   `now` is optional everywhere. Omit it and the taper never forgives, which is
   harsher and still correct. Pass it and a problem untouched for ten days pays
   full again.

   Then, on the SAME cleared branch and once each:

       purse = economy.roll_purse(region_id=enc.region,
                                  difficulty=problem.difficulty, rank=rank,
                                  luck=fx.get("loot_luck", 0.0),
                                  is_boss=enemy.boss, solved=solved,
                                  times_defeated=self.state["boss_rematch"].get(
                                      enc.boss_id, 0),
                                  rng=self._rng)
       player["gold"] += economy.record(self.state, purse)["gold"]
       economy.restock(self.state, enc.region, clears=1)
       economy.submit_to_trial(self.state, problem_id=problem.id, solved=solved,
                               rank=rank, hints_used=enc.hints_used,
                               seconds=seconds, target_seconds=problem.target_seconds,
                               first_try=enc.first_try, is_retest=enc.is_retest,
                               difficulty=problem.difficulty, skill=problem.pattern,
                               puzzle_kind=<kind if this was a puzzle else "">,
                               pattern_shown=<False in the castle and the Coliseum>,
                               companion_spoke=<a pet intervened this encounter>)

   crits: the old formula paid 5 gold a crit. That is gone deliberately — crits
   already feed xp through tactics.resolve_combat's multiplier, and paying them
   twice made gold swing on combat rolls rather than on correctness. If you want
   them back, they belong in RANK_PAY, not beside it.

2. THE PUZZLE — same place, when the encounter was one of the six kinds:
       award = economy.puzzle_award(self.state, region_id=enc.region,
                                    difficulty=problem.difficulty,
                                    kind=problem.encounter_kind,
                                    problem_id=problem.id, solved=solved,
                                    rank=rank, now=time.time())

3. DUNGEONS — replace the two `int(reward.get("gold", 0))` reads:
       room:  economy.dungeon_room_award(region_id=dungeon.region,
                                         room_kind=room.kind, depth=room.depth,
                                         solved=solved)
       boss:  economy.boss_award(region_id=dungeon.region, boss_id=boss["id"],
                                 dungeon=True, tier=dungeon.tier,
                                 times_defeated=<prior kills of this boss>)
   A region boss (world.BOSSES) is economy.boss_award(region_id=..., boss_id=...)
   with dungeon=False.

   PASS times_defeated. It is `state["boss_rematch"].get(boss_id, 0)` READ BEFORE
   this kill increments it, which engine.py already does at _resolve_boss. It is
   optional and defaults to the first-kill payout, so omitting it cannot break a
   call site — but omitting it leaves the rematch loop paying full price forever,
   and engine's own `_rematch_problem` clamps to one repeated problem id once a
   boss's family is spent. That combination was worth 1.54x the plain rate for
   re-typing something memorised. With the count passed it is 0.46x, which is
   less than walking next door and fighting something. See BOSS_REPEAT_RATIO.

   A ROOM PAYS ONLY IF IT ASKED FOR SOMETHING. dungeon_room_award now returns
   zero for ENTRANCE, JUNCTION, STORY and TREASURE — dungeons._FREE_KINDS — and
   for any kind it has not been told about. Nothing changes at the call site; the
   numbers simply stop including gold for walking. The chest still contains what
   dungeons.roll_room_treasure puts in it.

4. QUESTS — the number is still quests.REWARD_TIERS'. Route it through
       economy.quest_award(tier=reward["tier"], region_id=quest.region,
                           repeatable=quest.repeatable,
                           times_completed=<prior completions>)
   only if you want repeatables to taper. A one-shot quest is unchanged either
   way, so this call site is optional.

   VENDOR CREDIT. quests grants {"vendor_credit": {"region": r, "amount": n}}
   and left the resolution open. It is:
       economy.grant_credit(self.state, r, n)
   Credit is spent before gold at that region's vendor and nowhere else.

   REGALIA. economy.buy_regalia() returns {"grant": {"regalia": rid}}. Apply it
   through the same code path that applies a quest's `regalia` extra, then
   quests.wear_regalia() as normal. Do not append to the owned list from here.

5. THE SHOP — three calls, all region-scoped:
       economy.vendor_view(state, region_id, gold=player["gold"])
       economy.buy_potion(state, region_id, potion_id, gold=player["gold"],
                          quantity=1)
           -> {"gold_spent", "credit_spent", "quantity", "overflow", ...}
              or {"error": one of BUY_REFUSALS}
           The pouch is already filled (potions.grant) when it returns.
           Subtract `gold_spent` only; `credit_spent` is already deducted.
       economy.restock(state, region_id, clears=1)   -- see 1

6. THE BROKER — four calls:
       economy.broker_board(state, region_id)      -> offers, locked, greeting
       economy.open_trial(state, region_id, form_id)
       economy.submit_to_trial(state, ...)         -- see 1, every submission
       economy.close_trial(state, abandon=False)   -> Award
   Settle the Award the same way as any other:
       player["gold"] += economy.record(state, award)["gold"]
   economy.trial_state(state) is the HUD strip. One trial open at a time.

7. THE FEES — quote only, never deduct:
       economy.upgrade_fee(blade_id=..., to_tier=...)  -> forge.GOLD_SHAPE
       economy.upgrade_fee(item_id=..., to_rarity=...) -> ARMOUR_FEE
   forge.upgrade() already reports `gold_spent` and engine already subtracts it.
   Nothing about the weapon path changes. The armour path is new and has no
   deduction site yet, because the armour upgrade itself does not exist yet;
   when it does, it subtracts economy.upgrade_fee(...)["gold"] and nothing else.

8. UNITS, so nobody has to guess
       gold                 int, always, and never negative
       difficulty / band    a curriculum.TIERS string
       rank                 a grading.RANKS string; "" reads as FALLBACK_RANK_PAY
       region_id            a world.REGION_BY_ID key
       now                  unix seconds, float, optional everywhere
       luck                 the same float items.roll_drop takes
       seconds/target       seconds, float
       Award.gold           what to add to the purse. Award.detail is display.

9. THE TWO BODIES OF REGALIA
   gauntlet/regalia.py owns twenty-four COMPANION-keyed objects — the jade collar
   and the mystic scarf included — earned by evidence and deliberately unpriced.
   This module never sells them and validate() checks that it never starts.
   quests.REGALIA owns seven REGION-keyed pieces, which this module prices and
   shelves; regalia.py's own docstring says that is what should happen to them.
   If you integrate both, regalia.py's WIRING says to fold quests.py's
   contribution in through regalia.schedule(also_scale=, also_interventions=)
   rather than applying the two separately. Nothing about the shelf changes.
"""


_PROBLEMS = validate()
if _PROBLEMS:   # pragma: no cover - refuse to load a broken economy
    raise AssertionError("gauntlet.economy: " + "; ".join(_PROBLEMS))


if __name__ == "__main__":   # pragma: no cover
    print_balance()
    print()
    check = self_check()
    print(f"{check['vendors']} vendors, {check['trial_forms']} trial forms, "
          f"{check['standing_offers']} standing offers, "
          f"{check['regalia_priced']} regalia priced "
          f"({check['regalia_owned_by_sibling']} more owned, unpriced, by "
          f"regalia.py).")
    print("self check:", "ok" if check["ok"] else check["problems"])
