"""The adaptive learning engine: what should this player face next, and why.

Two rules govern everything here:

1. Difficulty rises on *evidence*, never on time spent playing.
2. Nobody ever dead-ends. If the player cannot progress, the engine's job is to
   find the prerequisite they are actually missing and route them to it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import curriculum
from . import puzzles
from . import skills as skillmod
from . import srs, world
from .config import SRS_INTERVALS_DAYS
from .corpus import teachable

DIFF_ORDER = ["GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS"]

# Variety targets. The six puzzle kinds exist because every encounter being
# "type a function" was both the hardest interaction for this player and the
# dullest. They are a change of pace, not the main course: roughly one encounter
# in four, mixed through the code battles rather than served in a block.
PUZZLE_SHARE = 0.25
VARIETY_WINDOW = 12
VARIETY_SEED = 4

# The puzzle families weight themselves toward this player's profile, which is
# right for choosing WHICH puzzle and a standing thumb on the scale for choosing
# WHETHER — it held the mix near a third. Paid back here so the share above is
# what actually decides, and measured rather than guessed: it is the gap between
# `2.0 * profile_weight` at their weighting and at the default.
PUZZLE_PROFILE_EDGE = 2.0

# Variety was steered for the puzzle GROUP and for nothing else, so the two
# largest families in the corpus — CODE_BATTLE and MISSING_RUNE — could and did
# take 46 of 60 encounters while nine kinds were never served at all. This
# spreads the same pressure across every kind: a kind over its fair share is
# pushed down, a kind that has not appeared is pulled up.
#
# KIND_SPREAD is set so the whole term stays inside one difficulty tier (5.0
# per step, below). Wanting a change of pace must never outrank what the
# curriculum has opened or what the player is ready for.
KIND_WINDOW = 24
KIND_SEED = 8              # denominator floor, so a short history is not evidence
KIND_FAIR_SHARE = 0.125    # twenty-four encounters should touch about eight kinds
KIND_SPREAD = 18.0
# Every variety term together is capped so that the SPREAD between any two
# candidates stays under one difficulty tier (5.0 per step, below) — which is
# what "worth less than one tier" has to mean if it is to hold. Uncapped, a kind
# served eight times running scored -15.75 against a starved one's +2.25, and
# that 18-point gap is three tiers of pull: enough for a change of pace to
# outrank what the player is actually ready for, which it did.
VARIETY_CAP = 2.4

# The share term above reshapes the mix but cannot cross a difficulty tier, and
# a kind whose only candidates sit one tier up therefore still never arrives —
# which is how BREAK_IT, COMPLEXITY_MATCH, PATTERN_ENCOUNTER and CODE_READING
# were all served zero times despite being unlocked. This is the explicit floor
# instead: any twenty consecutive encounters contain at least this many distinct
# kinds, and when they do not, the next encounter is one of the missing ones.
#
# The substitution is bounded twice over. It only ever chooses from the pool the
# curriculum has ALREADY opened, and only material within one difficulty tier of
# the player's target — so it cannot unlock anything and cannot skip a rung.
KIND_FLOOR_WINDOW = 20
KIND_FLOOR = 8
KIND_FLOOR_MAX_TIERS = 1

# The distinct-kinds floor says nothing about ORDER, and order is what the
# player experiences. Eight kinds in twenty encounters is perfectly satisfied by
# six code battles in a row followed by seven other things, which is exactly the
# run that turned up at encounter forty-eight once the ramp stopped feeding the
# window its own variety. The scoring terms that were supposed to prevent it —
# "whatever just happened is the least interesting thing to do again" — are
# capped at VARIETY_CAP, a third of one difficulty tier, so they cannot and
# should not outrank readiness. So the run is bounded directly instead, by the
# same substitution and under the same two bounds: already-opened material,
# within one tier of target.
KIND_RUN_LIMIT = 4

# --- within-session repetition ------------------------------------------------
# The SRS minimum interval is one day, so a first session contained no repetition
# whatsoever — 60 encounters, 60 distinct problems, nothing due. That is the
# opposite of the design. A family cleared earlier TODAY comes back today, in a
# different problem, after enough other work has passed to make it recall rather
# than a re-read.
SESSION_ECHO_GAP = 3       # encounters that must pass before a family returns
SESSION_ECHO_LIMIT = 2     # a family is met once and comes back once
SESSION_ECHO_BONUS = 40.0  # enough to beat the -45 "already solved" penalty
SESSION_ECHO_REACH = 8     # the gap at which the echo is worth full value

PROFILE_PATTERN_WEIGHT = {
    "PRACTICAL": {
        "LANGUAGE": 3.0,
        "ARRAY": 3.0, "STRING": 3.0, "HASH_MAP": 3.0, "SET": 2.5, "SORTING": 2.0,
        "SLIDING_WINDOW": 3.0, "TWO_POINTER": 3.0, "MATRIX": 2.5, "TREE": 2.5,
        "RECURSION": 2.5, "BFS": 2.5, "DFS": 2.5, "DESIGN": 2.5,
        "DEBUGGING": 2.0, "COMPLEXITY": 2.0, "TESTING": 2.0, "SIMULATION": 2.0,
        "PREFIX_SUM": 1.5, "HEAP": 1.5, "BINARY_SEARCH": 1.5, "DP": 1.5,
        "STACK": 1.5, "QUEUE": 1.5, "INTERVALS": 1.5, "GREEDY": 1.0,
        "RECOGNITION": 2.0,
    },
    "GENERAL_SWE": {p: 2.0 for p in skillmod.PATTERN_TO_SKILL},
    "SECURITY_ENGINEERING": {
        # An experienced engineer who has not written Python needs the language
        # rungs more than anyone, not less. Weighted with the staples.
        "LANGUAGE": 3.0,
        "HASH_MAP": 3.0, "SET": 3.0, "SLIDING_WINDOW": 3.0, "BFS": 2.5, "DFS": 2.5,
        "QUEUE": 2.5, "STACK": 2.0, "MATRIX": 2.0, "DESIGN": 2.5, "STRING": 2.0,
        "ARRAY": 2.0, "SORTING": 2.0, "DEBUGGING": 2.5, "TREE": 1.5,
        "RECURSION": 1.5, "DP": 1.0, "COMPLEXITY": 1.5, "TESTING": 2.0,
        "RECOGNITION": 2.0,
    },
    "CUSTOM": {},
}

# Training Camp: what a root cause routes you to.
CAMPS = {
    "SYNTAX": {"region": "python_village", "skill": "PYTHON",
               "name": "Syntax Drill", "mentor": "byte"},
    "PYTHON_RECALL": {"region": "python_village", "skill": "PYTHON",
                      "name": "Recall Drill", "mentor": "byte"},
    "WRONG_DATA_STRUCTURE": {"region": "hashmap_highlands", "skill": "HASH_MAP",
                             "name": "Hashmap Training Camp", "mentor": "archivist"},
    "PATTERN_NOT_RECOGNIZED": {"region": "fields_of_syntax", "skill": "RECALL",
                               "name": "Recognition Camp", "mentor": "scribe"},
    "INEFFICIENT_ALGORITHM": {"region": "complexity_tower", "skill": "BIG_O",
                              "name": "Complexity Tower", "mentor": "oracle"},
    "OFF_BY_ONE": {"region": "debugging_dungeon", "skill": "DEBUGGING",
                   "name": "Armorer's Forge", "mentor": "armorer"},
    "EDGE_CASE": {"region": "debugging_dungeon", "skill": "TESTING",
                  "name": "Testsmith Forge", "mentor": "testsmith"},
    "STATE_MANAGEMENT": {"region": "debugging_dungeon", "skill": "DEBUGGING",
                         "name": "Armorer's Forge", "mentor": "armorer"},
    "MUTABILITY": {"region": "python_village", "skill": "PYTHON",
                   "name": "Mutation Drill", "mentor": "byte"},
    "RECURSION": {"region": "recursive_forest", "skill": "RECURSION",
                  "name": "Recursive Forest Camp", "mentor": "druid"},
    "TREE_TRAVERSAL": {"region": "binary_tree_canopy", "skill": "TREE",
                       "name": "Canopy Camp", "mentor": "druid"},
    "GRAPH_TRAVERSAL": {"region": "graph_wastes", "skill": "GRAPH",
                        "name": "Cartographer's Camp", "mentor": "cartographer"},
    "WRONG_ALGORITHM": {"region": "fields_of_syntax", "skill": "RECALL",
                        "name": "Recognition Camp", "mentor": "scribe"},
    "TIME_PRESSURE": {"region": "coding_coliseum", "skill": "SPEED",
                      "name": "Chronomancer's Arena", "mentor": "chronomancer"},
    "COMPLEXITY": {"region": "complexity_tower", "skill": "BIG_O",
                   "name": "Complexity Tower", "mentor": "oracle"},
    "TESTING": {"region": "debugging_dungeon", "skill": "TESTING",
                "name": "Testsmith Forge", "mentor": "testsmith"},
    "DEBUGGING": {"region": "debugging_dungeon", "skill": "DEBUGGING",
                  "name": "Armorer's Forge", "mentor": "armorer"},
    "COMMUNICATION": {"region": "python_village", "skill": "COMMUNICATION",
                      "name": "The Scribe's Table", "mentor": "scribe"},
}


@dataclass
class Selection:
    problem: object
    reason: str
    is_retest: bool = False
    interval_days: float = 0.0
    encounter_kind: str = "CODE_BATTLE"
    tags: list = field(default_factory=list)


# --- saves written before the scaffold band existed ---------------------------
#
# A pre-record save cannot be read at the grain the band asks about, so
# `curriculum._tier_record_missing` hands it to the mastery ladder instead. The
# ladder above starts at EASY, and that is a blank screen: a player with five
# old fill-in-the-blanks behind them, mastery 14, whom the previous build aimed
# at TUTORIAL, would be aimed at an empty editor by the build that shipped to
# fix exactly that. Bug one, kept alive for everyone who had already started.
#
# So the old band comes with them. These are the previous build's own numbers,
# copied rather than re-derived, because the whole claim being made about those
# clears is "they were earned under that calibration". Two of them, for the two
# questions the old build asked: what this skill's own mastery says, and what
# general fluency says about a pattern with no evidence at all.
_LEGACY_SKILL_BAND = ((10.0, "GUIDED"), (18.0, "TUTORIAL"))
_LEGACY_FLUENCY_BAND = ((30.0, "GUIDED"), (55.0, "TUTORIAL"))


def _legacy_band(state, band) -> str | None:
    """The scaffold rung an old save is on, by the band it was earned under.

    None for a save this build wrote — its evidence is in the record and the
    record is a better answer — and None once the player has produced
    unscaffolded code since, because then there IS a record and it says so.
    """
    if state is None or not curriculum.untracked_clears(state):
        return None
    if curriculum.has_produced_code(state):
        return None
    for ceiling, tier in band:
        if state.mastery < ceiling:
            return tier
    return None


def _difficulty_target(state, fluency=None) -> str:
    """Where this skill should be pitched right now.

    A skill with no evidence at all starts on the scaffold rungs, not on a blank
    screen: GUIDED hands the player complete code with a blank in it.

    THE SCAFFOLD BAND IS NOT A MASTERY BAND. It used to be — GUIDED below 10,
    TUTORIAL below 18 — and since a GUIDED clear pays PYTHON 2.25, that was five
    fill-in-the-blanks and eight respectively. A player nine encounters into
    their first session, who had answered eight scaffolded multiple-choice
    questions and had never typed a line of Python, was being aimed at a blank
    screen. `curriculum.scaffold_target` asks the question the band is actually
    for instead: what has this player produced, unaided, and at which tier. It
    returns None once they have produced working code with no scaffold at all,
    which is where the mastery ladder takes over and where a player who arrived
    already writing Python starts.
    """
    if state is None or state.attempts == 0:
        # An unfamiliar pattern starts where the player's Python starts — not
        # from zero for someone who already writes it, and not on a blank screen
        # for someone who does not. Mastery used to decide this (55 for EASY, 30
        # for TUTORIAL) and mastery is the number the band exists to stop
        # trusting down here: PYTHON is paid twice for every gentle clear, so a
        # beginner crosses 55 while still inside the band and was handed a blank
        # screen on the first pattern they had no evidence in at all.
        legacy = _legacy_band(fluency, _LEGACY_FLUENCY_BAND)
        if legacy is not None:
            return legacy
        scaffold = curriculum.scaffold_target(fluency)
        return scaffold if scaffold is not None else "EASY"
    # The scaffold band is asked BEFORE mastery, not underneath it. Gating it on
    # "mastery below 42" only moved the bug later: PYTHON is paid twice for
    # every gentle clear, so a beginner crosses 42 in about twenty encounters
    # and would be aimed at MEDIUM LANGUAGE problems that do not exist, putting
    # the whole remaining beginner chain two tiers below target all over again.
    # Either the player has produced unscaffolded code or they have not, and
    # mastery is not entitled to a second opinion on it.
    scaffold = curriculum.scaffold_target(state)
    if scaffold is not None and not curriculum.scaffold_cleared(fluency):
        return scaffold
    legacy = _legacy_band(state, _LEGACY_SKILL_BAND)
    if legacy is not None:
        return legacy
    m = state.mastery
    if m < 42:
        return "EASY"
    if m < 68:
        return "MEDIUM"
    if m < 85:
        return "HARD"
    return "ELITE"


def _difficulty_distance(problem_difficulty: str, target: str) -> int:
    try:
        return abs(DIFF_ORDER.index(problem_difficulty) - DIFF_ORDER.index(target))
    except ValueError:
        return 3


def _variety_bonus(problem, recent_kinds: list) -> float:
    """Steer the SHAPE of the sequence, not the quality of one problem.

    Everything on the opening rungs scores identically, and Python's sort is
    stable, so before this term existed every tie was won by whichever family
    happened to be built first. That served fourteen fill-in-the-blanks in a row
    and put exactly one rune assembly in sixty encounters — the monotony the six
    puzzle kinds were written to end.

    Every term here is worth less than one difficulty tier (5.0 per step, below).
    Wanting a change of pace must never be able to drag in material the
    curriculum has not opened or the player is not ready for.
    """
    kind = problem.encounter_kind
    window = list(recent_kinds[:VARIETY_WINDOW])
    bonus = 0.0

    if kind in puzzles.PUZZLE_KINDS:
        # A one-encounter history is not evidence of a 100% puzzle diet, so the
        # denominator never falls below a handful. It reaches the true window
        # size as soon as there is a real history to measure.
        seen = max(len(window), VARIETY_SEED)
        share = sum(1 for k in window if k in puzzles.PUZZLE_KINDS) / seen
        # Below the target this pulls puzzles in, above it pushes them back out,
        # so the sequence settles at the target rather than at either extreme.
        bonus += 12.0 * (PUZZLE_SHARE - share) - PUZZLE_PROFILE_EDGE
        if window[:1] and window[0] in puzzles.PUZZLE_KINDS:
            bonus -= 3.0          # a change of pace, not a second mode

    # Whatever just happened is the least interesting thing to do again. This is
    # what keeps the mix interleaved instead of arriving in blocks.
    if window[:1] == [kind]:
        bonus -= 3.0
    if len(window) > 1 and window[1] == kind:
        bonus -= 1.5

    # The same pressure, applied to every kind rather than to the puzzle group
    # alone. This is the term that ends a 24-in-a-row run of one encounter kind.
    wide = list(recent_kinds[:KIND_WINDOW])
    share = sum(1 for k in wide if k == kind) / max(len(wide), KIND_SEED)
    bonus += KIND_SPREAD * (KIND_FAIR_SHARE - share)
    return max(-VARIETY_CAP, min(VARIETY_CAP, bonus))


def _starved_kind(scored: list, recent_kinds: list, skills: dict,
                  recent_ids: list) -> object | None:
    """The best-scoring encounter the recent sequence is short of.

    Two conditions, both about the shape of the sequence rather than the quality
    of one problem, and both substituting out of the pool the curriculum has
    already opened and within one tier of the player's target:

      THE FLOOR — twenty consecutive encounters that touch fewer than eight
      kinds. Needs a full window, so it never fires early.

      THE RUN — four encounters of one kind back to back. Needs no window at
      all, because a run is monotony from the moment it happens.
    """
    window = list(recent_kinds[:KIND_FLOOR_WINDOW])
    available = {p.encounter_kind for _, p in scored}
    run = list(recent_kinds[:KIND_RUN_LIMIT])
    running = (len(run) == KIND_RUN_LIMIT and len(set(run)) == 1
               and len(available) > 1)
    avoid: set = set()
    if running:
        avoid = set(run)
    elif len(window) >= KIND_FLOOR_WINDOW:
        seen = set(window)
        if len(seen) >= min(KIND_FLOOR, len(available)):
            return None
        avoid = seen
    else:
        return None
    # is_permitted() and permitted_patterns() do not agree on every problem, and
    # the second is the one the ramp tests read, so the floor honours both — a
    # variety pick must never be the one thing that walks past a chapter gate.
    allowed = curriculum.permitted_patterns(skills)
    blocked = set(recent_ids[:12])
    for _, problem in scored:                  # already sorted best-first
        if problem.encounter_kind in avoid or problem.id in blocked:
            continue
        if allowed and problem.pattern not in allowed:
            continue
        state = skills.get(
            skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"))
        target = _difficulty_target(state, skills.get("PYTHON"))
        if _difficulty_distance(problem.difficulty, target) > KIND_FLOOR_MAX_TIERS:
            continue
        return problem
    return None


def _session_echo(problem, session: list) -> float:
    """Bring back, later in the same sitting, a family cleared earlier in it.

    Interleaved recall inside one session is the single highest-value thing the
    selector can do and it was not happening at all. The rules are narrow on
    purpose: a DIFFERENT problem in the same family, only after enough other
    work has passed for it to be recall, and only a few times before the family
    is left alone and the spaced-repetition schedule takes over tomorrow.
    """
    if not session:
        return 0.0
    family = problem.spaced_repetition_family
    if not family:
        return 0.0
    rows = [i for i, row in enumerate(session)
            if row.get("family") == family and row.get("solved")]
    if not rows or len(rows) >= SESSION_ECHO_LIMIT:
        return 0.0
    if any(session[i].get("id") == problem.id for i in rows):
        return 0.0                     # the same problem again is a re-read
    since = len(session) - 1 - rows[-1]
    if since < SESSION_ECHO_GAP:
        return 0.0                     # too soon: it is still on the screen
    reach = max(1, SESSION_ECHO_REACH - SESSION_ECHO_GAP)
    return SESSION_ECHO_BONUS * min(1.0, (since - SESSION_ECHO_GAP + 1) / reach)


# ---------------------------------------------------------------------------
# Teaching order
# ---------------------------------------------------------------------------
#
# `Problem.prerequisites` carries three different meanings in this corpus, and
# only one of them is a precondition the selector may enforce.
#
#   A PRECONDITION. first_steps chains 57 rungs so that nothing is used before
#   it is met. `fs-two-lines` genuinely cannot be read by someone who has not
#   done `fs-name-a-value`. Serving it early is the "five concepts as scenery"
#   failure the family exists to remove.
#
#   A SUGGESTED ORDER. parsons and reasoning thread an `after=` through their
#   families. It is a pleasant progression, but `pa-count-evens` is perfectly
#   comprehensible to someone who has not done `pa-sum-values`.
#
#   A POINTER AT THE FULL-DRESS VERSION. onboarding and oop_language point the
#   other way — `oopl-len-guided` names `oopl-eq-without-hash-medium`, a MEDIUM
#   problem. Read as an order that is a deadlock: a GUIDED rung gated behind a
#   tier the player cannot unlock without clearing GUIDED rungs.
#
# Nothing in the record distinguishes them, so the content declares which it is
# rather than the engine inferring it — the same arrangement `lineage:` tags
# already use for the grouping that cannot be inferred either. Only a problem
# tagged `order:strict` is gated.
#
# Inferring instead was tried and is worth writing down, because it looks
# reasonable: honour an edge whenever it points at something no harder, which is
# true of every first_steps edge and false of every oop_language one. It gates
# 440 problems rather than 57, serialises parsons and reasoning along with the
# ramp, and flattens sixty encounters into a run of seven code battles. A field
# that means three things cannot be read as one thing, however careful the rule.
#
# The tier rail below survives from that attempt and is kept: a declared chain
# still may not point up the ladder. TestTheTeachingOrderGateStrandsNobody in
# tests/test_first_steps.py proves on the real corpus that nothing is stranded.


ORDER_TAG = "order:strict"

# --- the chapter the player was told they are on -----------------------------
#
# `open_chapters` is a PREFIX plus one chapter of lookahead, and the scorer
# treated all of it as one flat pool. Nothing preferred the chapter the player
# is actually on, so among equal-scoring candidates the winner was whichever
# family the corpus happened to build first.
#
# That is fine until the game says a chapter's name out loud. A player who aces
# the diagnostic is told "We do not need the alphabet. We start at Counting and
# Membership", is placed on chapter IV — and was then served twelve linked-list
# two-pointer problems out of their first twenty, against one hash map, because
# the top of the ranking was a sixteen-way tie at 17.25 and `ll-` sorts before
# `pt-`. The skip was real and the sentence was still not true.
#
# So the frontier chapter's own families get a thumb on the scale, and the size
# is chosen rather than tuned: smaller than the 5.0 a difficulty tier costs and
# smaller than VARIETY_CAP, so readiness and monotony both still outrank it and
# it can never drag in material the curriculum has not opened. Lookahead keeps
# working — a chapter-V problem a point ahead on merit still wins — it simply
# stops winning coin tosses against the chapter the player was promised.
#
# It is paid for, and the price is written down rather than discovered later: a
# beginner walking the whole game meets 26 of the 57 beginner rungs in two
# hundred encounters where they met 33 without it, because after the
# scaffolding comes off the chapter they are on now outranks the leftovers of
# the chapter they have left. In the same two hundred they reach chapter VI
# rather than chapter V. Nothing is lost — the rungs stay in order, stay
# reachable, and keep arriving — the player simply spends the back half of the
# session on the chapter they are actually being taught.
FRONTIER_CHAPTER_BONUS = 2.0

# --- walking the chain, as opposed to merely permitting it --------------------
#
# `unlocked_by_order` reduces a 57-rung chain to exactly ONE candidate at a
# time. That is what makes the order real, and it is also what made the ramp
# unwalkable: one candidate among two hundred equally-scored gentle problems
# gets picked about once in fifty encounters, which is how a chain of
# fifty-seven rungs delivered three of them in two hundred. The gate and this
# term are one mechanism, and shipping either half alone is a bug.
#
# Scoring was tried first and is worth writing down, because it looks like the
# smaller change. A bonus large enough to win reliably has to beat the terms the
# open rung loses to, and those are `+6.0 unexplored skill` and the weakness
# terms — up to eight points, which is more than the 5.0 a whole difficulty tier
# costs. A tie-break that has to outweigh a tier is not a tie-break, and a
# number chosen by arms race against the rest of the formula is a number nobody
# can defend later. So it is a rule instead, stated once, with its bounds on the
# outside where they can be read.
#
# WHILE THE PLAYER IS INSIDE THE SCAFFOLD BAND, EVERY THIRD ENCOUNTER IS THE
# NEXT RUNG OF THE CHAIN. Bounded three ways, and every one is load-bearing.
#
#   IT CAN ONLY EVER SERVE THE RUNG THE ORDER GATE HAS ALREADY OPENED, chosen
#   out of the same scored, permitted, in-order pool as any other pick. It
#   cannot skip a rung, unlock a tier, or reach past a chapter — it decides
#   WHICH of the things the player may already be shown comes next, and nothing
#   more. Same standing as the retest branch above it and the variety floor
#   below it, both of which override scoring for a stated reason.
#
#   IT APPLIES ONLY INSIDE THE SCAFFOLD BAND. When the scaffolding comes off the
#   chain stops being the main road and drops to the scoring affordance below.
#   This is what stops somebody who already writes Python being walked through
#   fifty-seven rungs of `print` — and the diagnostic's writing trial is what
#   puts them outside the band before their first encounter.
#
#   ONE RUNG IN THREE AT MOST. A spine is not a diet. Without the gap the chain
#   wins every turn until it runs out, which is a run of reading questions —
#   the monotony the six puzzle kinds were written to end.
CHAIN_GAP = 2

# ...AND NEVER THE SAME RUNG TWICE IN A ROW OF ENCOUNTERS. CHAIN_GAP bounds how
# often *a* rung arrives and says nothing about *which*, and for a player who
# clears the rung that is the same sentence — the next pick is a different
# problem because the last one is now solved. For a player who does not clear
# it, it is not: measured on a beginner who failed everything, rung one arrived
# fourteen times in forty encounters, the same reading question every third
# turn. That is worse monotony than the block CHAIN_GAP exists to prevent, and
# it lands on the one player least able to take it. So the rule yields for as
# long as the scorer's own "never repeat what was just played" window is still
# holding that problem down, and the encounter is decided by scoring instead.
# Nothing is lost: the rung is still the next thing the chain wants, and it
# comes back the moment the window has moved past it.
CHAIN_REPEAT_WINDOW = 12

# AFTER THE BAND, A CHAIN YOU STARTED IS A CHAIN YOU FINISH — but by scoring,
# not by rule. A beginner leaves the band around encounter forty with roughly a
# dozen rungs behind them, and the forty-odd that teach `def`, parameters,
# `return` and the error messages are worth meeting; at two tiers below target
# they score -10 and are worth nothing. So the open rung of a chain the player
# is PARTWAY THROUGH is scored as if it were on target — never better, which is
# the bound — and thereafter arrives when it earns its place, roughly one
# encounter in eight. Intense while the scaffolding is on, occasional after.
#
# It cannot reach somebody who writes Python, and the reason is structural
# rather than a threshold: the waiver needs the previous rung cleared, and the
# chain's first rung has no waiver at all. A player who never took rung one is
# never offered rung two.


def gating_prerequisites(problem, by_id: dict) -> list:
    """The prerequisites of `problem` that are genuinely a teaching order."""
    if ORDER_TAG not in problem.tags:
        return []
    out = []
    for pre in problem.prerequisites:
        other = by_id.get(pre)
        if other is None:
            continue                   # severed by the hold-out, or never built
        if curriculum.tier_index(other.difficulty) <= curriculum.tier_index(
                problem.difficulty):
            # The tier rail. A declared chain still may not point UP the ladder:
            # that would gate a GUIDED rung behind a tier the player cannot
            # unlock without clearing GUIDED rungs, which is a deadlock however
            # sincerely it was declared. Cheap to check, and it means a future
            # family cannot declare itself into a wall.
            out.append(pre)
    return out


# The band inside which even a declared order binds. The reason is stranding,
# not pedagogy: a gate applied at every tier locks a chain's BODY behind its
# HEAD forever. A chain running from a GUIDED head to an EASY body dies the
# moment the player's difficulty target moves past GUIDED — which
# `_difficulty_target` does after about eight clears — because the head is then
# out-scored by two tiers and never picked again, so the body it gates can never
# open. A corpus-wide reachability proof does not catch that: a path existing is
# not the same as the selector taking it.
#
# Above the gentle band the order is advisory, which is also when the player has
# demonstrated the competence the chain existed to build. first_steps is gentle
# end to end, so its chain is bound in full.
_ORDER_BINDING_TIERS = ("GUIDED", "TUTORIAL")


def unlocked_by_order(problem, by_id: dict, solved_ids: set) -> bool:
    """Has the player cleared what this problem is written to assume?"""
    if problem.difficulty not in _ORDER_BINDING_TIERS:
        return True
    return all(pre in solved_ids
               for pre in gating_prerequisites(problem, by_id))


def _chain_in_progress(problem, solved_ids: set) -> bool:
    """Is this the open rung of a declared chain the player has begun?

    Deliberately not "is this a chain rung": the root has no prerequisites and
    so never qualifies, which is what keeps the waiver away from a player who
    never started the chain in the first place.
    """
    return (ORDER_TAG in problem.tags
            and problem.id not in solved_ids
            and bool(problem.prerequisites)
            and all(pre in solved_ids for pre in problem.prerequisites))


def _chain_rung(scored: list, skills: dict, solved_ids: set,
                recent_ids: list, by_id: dict):
    """The next rung of a declared teaching chain, when it is that rung's turn.

    Returns None when the player is past the scaffold rungs, None when a rung
    was served inside the last CHAIN_GAP encounters, and None when the chain is
    finished. See CHAIN_GAP above for why this is a rule and not a scoring term.

    "Past the scaffold rungs" is asked as WHERE THE PLAYER IS BEING AIMED, not
    as whether the band has been cleared, and for a save this build wrote those
    are the same sentence — the band is what decides the target down there. They
    part company on a save written before the band existed, whose clears cannot
    be read at that grain and which is therefore aimed by the old calibration
    instead (`_legacy_band`). Asked the other way, a returning beginner with
    five old fill-in-the-blanks and mastery 14 was aimed at TUTORIAL and never
    offered a single rung of the chain that exists for exactly them: not
    unreachable, just never picked, which is the bug this whole rule replaced.
    """
    fluency = skills.get("PYTHON")
    if _difficulty_target(fluency, fluency) not in _ORDER_BINDING_TIERS:
        return None
    if any(ORDER_TAG in by_id[pid].tags
           for pid in recent_ids[:CHAIN_GAP] if pid in by_id):
        return None
    for _score, problem in scored:              # already sorted best-first
        if ORDER_TAG in problem.tags and problem.id not in solved_ids:
            if problem.id in recent_ids[:CHAIN_REPEAT_WINDOW]:
                return None      # still on the screen; let scoring decide
            return problem
    return None


def score_problem(problem, *, skills: dict, profile: str, solved_ids: set,
                  recent_ids: list, region: str | None, now: float,
                  recent_kinds: list = (), session: list = (),
                  frontier_families: set | None = None) -> float:
    """Higher is a better next encounter. This is the whole selection policy.

    `frontier_families` is passed in by `select_next` because it is the same
    answer for every candidate and deriving it walks the chapter ladder; a
    caller that omits it gets it derived here.
    """
    skill_name = skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
    state = skills.get(skill_name)
    fluency = skills.get("PYTHON")
    score = 0.0

    weights = PROFILE_PATTERN_WEIGHT.get(profile) or PROFILE_PATTERN_WEIGHT["GENERAL_SWE"]
    score += 4.0 * weights.get(problem.pattern, 1.0)
    score += 2.0 * problem.profile_weight.get(profile, 1.0)

    # What the player was told they are doing. See FRONTIER_CHAPTER_BONUS above.
    if frontier_families is None:
        frontier_families = curriculum.frontier_families(skills)
    chain_open = _chain_in_progress(problem, solved_ids)
    if ORDER_TAG in problem.tags:
        # A declared chain counts as the frontier too — first_steps belongs to
        # chapter I and the player leaves chapter I at about the moment the
        # scaffolding comes off, so without this arm the term would quietly end
        # the beginner chain with forty rungs still unmet. But only AFTER the
        # band: inside it the rung is already served by rule, one encounter in
        # three, and a bonus on top of that rule lifts the NEXT rung straight
        # after the last one. Measured as two in a row, which is the block
        # CHAIN_GAP exists to prevent.
        if chain_open and curriculum.scaffold_cleared(fluency):
            score += FRONTIER_CHAPTER_BONUS
    elif problem.spaced_repetition_family in frontier_families:
        score += FRONTIER_CHAPTER_BONUS

    target = _difficulty_target(state, fluency)
    # The open rung of a chain the player is partway through is scored at par —
    # never better. See CHAIN_GAP above for why, and for what it may not buy.
    if not chain_open:
        score -= 5.0 * _difficulty_distance(problem.difficulty, target)

    if state is not None:
        # Weakness attracts work, but only where we have evidence of weakness.
        if state.attempts:
            score += (100 - state.mastery) * 0.06
            score += state.error_rate * 0.04
            score += state.hint_dependence * 0.03
        else:
            score += 6.0                     # unexplored skills are worth probing

    if problem.id in solved_ids:
        score -= 45.0                        # strongly prefer unseen material
    if problem.id in recent_ids[:12]:
        score -= 60.0                        # never repeat what was just played
    if region and problem.realm == region:
        score += 12.0
    if problem.difficulty == "BOSS":
        score -= 25.0                        # bosses are entered deliberately
    if problem.encounter_kind in ("PATTERN_ENCOUNTER", "COMPLEXITY_DUEL",
                                  "CODE_READING", "EDGE_CASE_TRAP") \
            and not (target == "GUIDED" and problem.difficulty == "GUIDED"):
        score -= 6.0                         # spice, not the main course
        # ...but only for a player who can already write Python. Those four
        # kinds ask the player to read a piece of code and judge it rather than
        # produce one, which is garnish next to a code battle when you are
        # preparing for an interview. At the bottom of the ramp it is the exact
        # reverse: the player cannot type yet, and a question about one line of
        # code is the LARGEST thing that can honestly be asked of them. This
        # term is why the first rung of the first_steps chain — "here is one
        # line of Python, what does it print" — scored 266th of 351 eligible
        # problems for a brand-new player, six points behind a __repr__
        # fill-in. The condition is narrow on purpose: it lifts only for a
        # GUIDED problem being shown to a skill with no evidence at all, which
        # is the one population for whom reading is the main course.
    # The six graded puzzle kinds are NOT spiced down with those. They are graded
    # by running real Python or by an exact structural match, they carry full
    # hint trees, and they move mastery — they are encounters, not flavour. Their
    # share is steered instead, so they arrive mixed in rather than never.
    score += _variety_bonus(problem, list(recent_kinds))
    # Deliberately added AFTER the solved/recent penalties rather than folded
    # into them: an echo is meant to overcome "you have seen this family", which
    # is exactly what those penalties say.
    score += _session_echo(problem, list(session))
    return score


def select_next(corpus: list, *, skills: dict, schedule: dict, profile: str,
                solved_ids: set, recent_ids: list, region: str | None = None,
                now: float | None = None, allow_retest: bool = True,
                recent_kinds: list | None = None,
                session: list | None = None, intent: str = "balanced") -> Selection:
    """Retests come first — a due pattern is the highest-value thing we can show.
    Otherwise pick the best-scoring fresh encounter."""
    now = now or time.time()
    # Everything below this line teaches, including the retest branch, so the
    # hold-out is removed from the input rather than from the output. A sealed
    # problem that reaches a scoring loop is one bug away from being taught, and
    # callers that already hand us teachable content lose nothing by it.
    corpus = teachable(corpus)

    if allow_retest and intent != "new":
        for entry in srs.due(schedule, now=now, limit=6):
            candidates = [p for p in corpus
                          if p.spaced_repetition_family == entry.family
                          and p.entry.get("kind") not in ("mcq",)]
            pick = srs.pick_disguised(entry, candidates)
            if pick is not None and pick.id not in recent_ids[:6]:
                days = srs.days_since_review(entry, now=now)
                return Selection(
                    problem=pick, reason="RETEST", is_retest=True,
                    interval_days=days, encounter_kind="MEMORY_AMBUSH",
                    tags=["retest", f"{int(days)}d"])

    # The curriculum gate is a guarantee, not a preference: a pattern or tier the
    # player has not unlocked must not appear at all. Scoring alone only made
    # advanced material unlikely, which is how tree recursion still reached a
    # chapter-one player. Retests above are exempt by design — retention outranks
    # sequencing — and an empty gate falls back to the whole corpus so that a
    # misconfigured chapter can never dead-end the player.
    fluency = skills.get("PYTHON")
    eligible = [p for p in corpus
                if curriculum.is_permitted(
                    p, skills,
                    skill_state=skills.get(
                        skillmod.PATTERN_TO_SKILL.get(p.pattern, "PYTHON")),
                    fluency=fluency)]
    if not eligible:
        eligible = corpus

    # The second gate: teaching order. A problem written to assume another
    # problem is not shown until that one is cleared. Without this the 57-rung
    # first_steps chain scored as 57 interchangeable GUIDED problems and was
    # served in build order, which is to say in no order at all — the field was
    # authored, validated, shipped, and read by nothing.
    #
    # Same shape as the gate above, including the fallback: if honouring the
    # order would leave nothing to serve, serve something. Dead-ending the
    # player is worse than showing them a rung early, and rule 2 of this module
    # says nobody ever dead-ends.
    by_id = {p.id: p for p in corpus}
    in_order = [p for p in eligible
                if unlocked_by_order(p, by_id, solved_ids)]
    if in_order:
        eligible = in_order

    # The caller knows the whole corpus and can name the kinds it has just
    # served; falling back to this filtered slice is only for direct callers.
    if recent_kinds is None:
        kind_of = {p.id: p.encounter_kind for p in corpus}
        recent_kinds = [kind_of[i] for i in recent_ids if i in kind_of]

    session = list(session or ())
    frontier_families = curriculum.frontier_families(skills)
    def intent_bonus(p):
        if intent == "new":
            return 18.0 if p.id not in solved_ids else 0.0
        if intent == "review":
            return 18.0 if p.spaced_repetition_family in schedule else 0.0
        if intent == "weakest":
            state = skills.get(skillmod.PATTERN_TO_SKILL.get(p.pattern, "PYTHON"))
            return max(0, 100 - getattr(state, "mastery", 0)) * 0.22
        return 0.0

    scored = [(score_problem(p, skills=skills, profile=profile,
                             solved_ids=solved_ids, recent_ids=recent_ids,
                             region=region, now=now, recent_kinds=recent_kinds,
                             session=session,
                             frontier_families=frontier_families) + intent_bonus(p), p)
              for p in eligible]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        raise ValueError("empty corpus")

    rung = _chain_rung(scored, skills, solved_ids, recent_ids, by_id)
    if rung is not None:
        return Selection(problem=rung, reason="RAMP",
                         encounter_kind=rung.encounter_kind,
                         tags=["ramp", rung.spaced_repetition_family])
    starved = _starved_kind(scored, list(recent_kinds), skills, recent_ids)
    if starved is not None:
        return Selection(problem=starved, reason="VARIETY",
                         encounter_kind=starved.encounter_kind,
                         tags=["variety", starved.encounter_kind])

    best = scored[0][1]
    # An echo is a different reason than "the best fresh thing", and the client
    # says so out loud — a returning pattern the player is not told is a return
    # reads as the engine repeating itself rather than as deliberate recall.
    if _session_echo(best, session) > 0:
        return Selection(problem=best, reason="SESSION_ECHO",
                         encounter_kind=best.encounter_kind,
                         tags=["echo", best.spaced_repetition_family])
    reason = {"new": "PRACTICE_NEW", "review": "PRACTICE_REVIEW",
              "weakest": "PRACTICE_WEAKEST"}.get(intent, "ADAPTIVE")
    return Selection(problem=best, reason=reason,
                     encounter_kind=best.encounter_kind)


def training_camp(root_cause: str, skills: dict, failed_skill: str) -> dict:
    """Failure becomes navigation through the learning graph.

    If the player failed a sliding-window problem because their dictionary work
    is weak, do NOT reteach sliding window. Teach the dictionary.
    """
    prereq = skillmod.missing_prerequisite(skills, failed_skill)
    if prereq and prereq != failed_skill:
        camp_skill = prereq
        region = next((r["id"] for r in world.REGIONS if r["skill"] == prereq),
                      "python_village")
        return {
            "skill": camp_skill,
            "region": region,
            "name": f"{prereq.replace('_', ' ').title()} Training Camp",
            "mentor": world.REGION_BY_ID.get(region, {}).get("mentor", "byte"),
            "why": (f"You did not fail because of {failed_skill.replace('_', ' ').lower()}. "
                    f"You failed because {prereq.replace('_', ' ').lower()} is not yet "
                    "automatic — and that pattern is built on top of it."),
            "root_cause": root_cause,
        }

    camp = CAMPS.get(root_cause) or CAMPS["PYTHON_RECALL"]
    return {
        "skill": camp["skill"], "region": camp["region"], "name": camp["name"],
        "mentor": camp["mentor"], "root_cause": root_cause,
        "why": f"The first thing that went wrong was: {root_cause.replace('_', ' ').lower()}.",
    }


def remediation_plan(corpus: list, root_cause: str, problem, skills: dict) -> dict:
    """After every failure: one micro-drill, one related standard problem, one
    delayed variant. Never nothing."""
    # Remediation is teaching by definition: it hands back three problem ids to
    # go and study. None of them may be hold-out content.
    corpus = teachable(corpus)
    camp = training_camp(root_cause, skills,
                         skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"))
    by_id = {p.id: p for p in corpus}

    def find(pred, limit=1):
        return [p for p in corpus if pred(p)][:limit]

    drill = find(lambda p: (p.difficulty == "TUTORIAL"
                            and skillmod.PATTERN_TO_SKILL.get(p.pattern) == camp["skill"]
                            and p.id != problem.id))
    if not drill:
        drill = find(lambda p: p.difficulty == "TUTORIAL" and p.realm == camp["region"])
    if not drill:
        drill = find(lambda p: p.difficulty == "TUTORIAL")

    simpler = find(lambda p: (p.spaced_repetition_family == problem.spaced_repetition_family
                              and p.id != problem.id
                              and DIFF_ORDER.index(p.difficulty)
                              < DIFF_ORDER.index(problem.difficulty)))
    if not simpler:
        simpler = find(lambda p: (p.pattern == problem.pattern and p.id != problem.id
                                  and p.difficulty in ("TUTORIAL", "EASY")))

    delayed = find(lambda p: (p.spaced_repetition_family == problem.spaced_repetition_family
                              and p.id != problem.id
                              and ("disguised" in p.tags
                                   or p.source_type in ("GENERATED_VARIANT",
                                                        "SECURITY_VARIANT"))))
    if not delayed:
        delayed = find(lambda p: (p.pattern == problem.pattern and p.id != problem.id))

    return {
        "camp": camp,
        "immediate": {"id": drill[0].id, "title": drill[0].title,
                      "why": "A micro-drill on the thing that actually broke."}
        if drill else None,
        "next": {"id": simpler[0].id, "title": simpler[0].title,
                 "why": "The same pattern, one rung easier."} if simpler else None,
        "delayed": {"id": delayed[0].id, "title": delayed[0].title,
                    "days": 3,
                    "why": "The same algorithm in disguise, three days from now."}
        if delayed else None,
    }


def daily_quests(*, skills: dict, schedule: dict, corpus: list, profile: str,
                 now: float | None = None) -> list:
    """Personalised to weakness, retention schedule and recent failures."""
    now = now or time.time()
    quests = []

    ready = srs.due(schedule, now=now, limit=5)
    if ready:
        entry = ready[0]
        quests.append({
            "kind": "RETEST", "id": "daily-retest",
            "title": f"{entry.family.replace('_', ' ').title()} is due for retest",
            "detail": f"A pattern you learned {int(srs.days_since_review(entry, now=now))} "
                      "days ago wants proving again — in disguise.",
            "count": min(2, len(ready)), "reward_xp": 60,
        })

    weak = skillmod.weakest(skills, limit=2)
    for name in weak:
        quests.append({
            "kind": "MENTOR", "id": f"daily-weak-{name.lower()}",
            "title": f"{name.replace('_', ' ').title()} training",
            "detail": "Your weakest area with real evidence behind it.",
            "count": 2, "reward_xp": 45,
        })

    python_state = skills.get("PYTHON")
    if python_state is None or python_state.mastery < 70:
        quests.append({
            "kind": "DAILY", "id": "daily-village",
            "title": "Python Village drills",
            "detail": "Three fluency drills. Syntax should cost you nothing.",
            "count": 3, "reward_xp": 30,
        })

    quests.append({
        "kind": "DAILY", "id": "daily-armor",
        "title": "Repair one piece of armour",
        "detail": "The Armorer has a broken program with your name on it.",
        "count": 1, "reward_xp": 35,
    })
    quests.append({
        "kind": "DAILY", "id": "daily-shrine",
        "title": "Visit a Memory Shrine",
        "detail": "Rapid recall. Fifteen seconds per question.",
        "count": 1, "reward_xp": 20,
    })

    speed = skills.get("SPEED")
    if speed and speed.attempts >= 5:
        quests.append({
            "kind": "BOUNTY", "id": "daily-bounty",
            "title": "Beat yesterday's median solve time",
            "detail": "Same knowledge. Less hesitation.",
            "count": 1, "reward_xp": 50,
        })
    return quests[:6]


# --- readiness ---------------------------------------------------------------

READINESS_DIMENSIONS = [
    ("Python Fluency", ["PYTHON"]),
    ("Pattern Recognition", ["RECALL"]),
    ("Algorithms", ["SLIDING_WINDOW", "TWO_POINTER", "BFS", "DFS", "DP",
                    "BINARY_SEARCH", "RECURSION"]),
    ("Data Structures", ["HASH_MAP", "SET", "STACK", "QUEUE", "HEAP", "TREE",
                         "MATRIX", "ARRAY"]),
    ("Debugging", ["DEBUGGING"]),
    ("Complexity", ["BIG_O"]),
    ("Testing", ["TESTING"]),
    ("Speed", ["SPEED"]),
    ("Communication", ["COMMUNICATION"]),
    ("Retention", None),          # computed from the schedule, not a skill
]

GATES = [
    {"id": "python_no_weakness", "label": "No major Python syntax weakness",
     "check": lambda ctx: ctx["skills"]["PYTHON"].mastery >= 65},
    {"id": "easy_independent", "label": "Common Easy problems solved independently",
     "check": lambda ctx: ctx["unaided_easy"] >= 8},
    {"id": "medium_independent", "label": "Representative Mediums solved independently",
     "check": lambda ctx: ctx["unaided_medium"] >= 6},
    {"id": "hashmap_automatic", "label": "Hash-map pattern is automatic",
     "check": lambda ctx: ctx["skills"]["HASH_MAP"].mastery >= 70
     and ctx["skills"]["HASH_MAP"].hint_dependence <= 30},
    {"id": "window_recognized", "label": "Sliding window recognised unprompted",
     "check": lambda ctx: ctx["skills"]["SLIDING_WINDOW"].mastery >= 60},
    {"id": "two_pointer_recognized", "label": "Two-pointer pattern recognised",
     "check": lambda ctx: ctx["skills"]["TWO_POINTER"].mastery >= 60},
    {"id": "traversal_functional", "label": "BFS and DFS basics functional",
     "check": lambda ctx: min(ctx["skills"]["BFS"].mastery,
                              ctx["skills"]["DFS"].mastery) >= 50},
    {"id": "tree_functional", "label": "Tree traversal functional",
     "check": lambda ctx: ctx["skills"]["TREE"].mastery >= 55},
    {"id": "bigo_explained", "label": "Can state and justify Big-O",
     "check": lambda ctx: ctx["skills"]["BIG_O"].mastery >= 60},
    {"id": "edge_tests", "label": "Can produce edge-case tests",
     "check": lambda ctx: ctx["skills"]["TESTING"].mastery >= 50},
    {"id": "debug_under_pressure", "label": "Can debug under pressure",
     "check": lambda ctx: ctx["skills"]["DEBUGGING"].mastery >= 60},
    {"id": "timed_performance", "label": "Performs with a timer running",
     "check": lambda ctx: ctx["skills"]["SPEED"].mastery >= 50
     or ctx["skills"]["SPEED"].speed >= 55},
    {"id": "retention", "label": "Retains major patterns after several days",
     "check": lambda ctx: ctx["retention"] >= 55},
]


def _avg(values: list) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def retention_score(schedule: dict, now: float | None = None) -> float:
    now = now or time.time()
    if not schedule:
        return 0.0
    scores = []
    for entry in schedule.values():
        if entry.reviews == 0:
            continue
        stage_score = 100.0 * entry.stage / max(len(SRS_INTERVALS_DAYS) - 1, 1)
        penalty = min(35.0, entry.lapses * 12.0)
        overdue = srs.overdue_days(entry, now=now)
        stale = min(25.0, overdue * 4.0)
        scores.append(max(0.0, stage_score - penalty - stale))
    return _avg(scores)


def readiness(*, skills: dict, schedule: dict, stats: dict,
              unaided_easy: int = 0, unaided_medium: int = 0,
              now: float | None = None) -> dict:
    ret = retention_score(schedule, now=now)
    dimensions = []
    for label, names in READINESS_DIMENSIONS:
        if names is None:
            dimensions.append({"label": label, "score": round(ret)})
            continue
        vals = []
        for name in names:
            state = skills.get(name)
            if state is None:
                continue
            # Confidence discounts mastery we have little evidence for.
            vals.append(state.mastery * (0.55 + 0.45 * state.confidence / 100.0))
        dimensions.append({"label": label, "score": round(_avg(vals))})

    ctx = {"skills": skills, "retention": ret, "stats": stats,
           "unaided_easy": unaided_easy, "unaided_medium": unaided_medium}
    gates = []
    for gate in GATES:
        try:
            passed = bool(gate["check"](ctx))
        except Exception:
            passed = False
        gates.append({"id": gate["id"], "label": gate["label"], "passed": passed})

    passed_gates = sum(1 for g in gates if g["passed"])
    # Never declare READY from an average alone: the gates are the real bar,
    # and the weakest dimension caps the headline number.
    avg = _avg([d["score"] for d in dimensions])
    weakest = min((d["score"] for d in dimensions), default=0)
    gate_ratio = passed_gates / len(gates)
    overall = round(min(avg, 40 + weakest * 0.7) * (0.4 + 0.6 * gate_ratio))

    return {
        "overall": overall,
        "dimensions": dimensions,
        "gates": gates,
        "gates_passed": passed_gates,
        "gates_total": len(gates),
        "ready": passed_gates == len(gates),
        "verdict": _verdict(overall, passed_gates, len(gates)),
    }


def _verdict(overall: int, passed: int, total: int) -> str:
    if passed == total:
        return ("Every readiness gate is met. On this evidence you are prepared for a "
                "demanding Python coding screen.")
    remaining = total - passed
    if overall >= 70:
        return (f"Strong overall, but {remaining} gate{'s' if remaining > 1 else ''} "
                "remain{'' if remaining > 1 else 's'} unmet. Averages do not pass "
                "interviews; the gates do.")
    if overall >= 45:
        return (f"Real progress. {remaining} gates still open — the open ones are "
                "exactly what to train next.")
    return ("Early days. The engine will keep routing you to whatever is actually "
            "blocking you.")
