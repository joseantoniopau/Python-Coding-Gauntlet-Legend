"""The ramp: what this player is allowed to meet, and in what order.

The complaint that produced this module was "the game is too hard". The cause was
not that individual problems were too hard — it was that the engine had no concept
of *order*. It scored problems by pattern weight and difficulty distance and then
handed a beginner tree recursion as their sixth encounter.

This module supplies the missing spine. Two mechanisms:

1. A CHAPTER LADDER. Concepts are grouped into ordered chapters. A chapter opens
   only when the one before it has real evidence behind it. Nothing from chapter 7
   can appear while the player is still on chapter 2, regardless of how attractive
   it looks to the scorer.

2. PER-SKILL DIFFICULTY GATES. Within an open chapter, a difficulty tier unlocks
   for a skill only when that skill has demonstrated readiness for it. Mediums do
   not appear until Easies are being cleared unaided.

Both are evidence-driven. Neither has any notion of time spent playing.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import scaffold

# ---------------------------------------------------------------------------
# Difficulty ordering
# ---------------------------------------------------------------------------

TIERS = ["GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS"]


def tier_index(name: str) -> int:
    try:
        return TIERS.index(name)
    except ValueError:
        return TIERS.index("EASY")


# ---------------------------------------------------------------------------
# The scaffold band: what "the scaffolding has come off" is allowed to mean
# ---------------------------------------------------------------------------
#
# GUIDED hands the player complete code with one blank in it. TUTORIAL hands
# them a skeleton and asks for the body. EASY is a blank screen. Those are
# three different acts, and only the third one is what a timed practical asks for.
#
# The bottom of the ramp used to be governed by mastery alone, and mastery is a
# single accumulating number: a GUIDED clear pays PYTHON 7.5 x 0.3 = 2.25, so
# five fill-in-the-blanks reached 10 and eight reached 18, which were the old
# thresholds for leaving GUIDED and for leaving TUTORIAL. By encounter nine a
# player who had answered eight scaffolded multiple-choice questions and had
# never typed a line of Python was being aimed at a blank screen — and the
# fifty-five remaining rungs of the beginner chain, two tiers below target,
# scored -10 and ranked about 285th. The ramp existed and the selector would
# not walk it.
#
# The number was not the mistake; the QUESTION was. "Have you accumulated 10
# mastery" and "can you write a function from nothing" are not the same
# question, and the second one is the one the scaffolding is there to answer.
# So below EASY the band is decided by what the player has actually PRODUCED,
# counted at the tier it was produced at:
#
#   to be aimed above GUIDED    — eight clears with no hint cast
#   to be aimed above TUTORIAL  — six of those at TUTORIAL or harder
#
# Unaided, because a hinted clear is evidence that the hint worked. Counted at
# or above the tier, because a player already clearing EASY unaided has
# obviously finished with the scaffold and must not be sent back down it.
#
# THE ESCAPE HATCH, and the reason this cannot drag a competent player: one
# unaided clear at EASY or harder ends the band outright. A beginner cannot
# reach one — EASY is gated below — so the only way to hold that evidence
# without walking the band is to have produced working code on a blank screen
# in the opening diagnostic, which is graded in the same sandbox against real
# tests. That is the instrument that tells the two players apart, and it is the
# only thing that may skip the ramp.
SCAFFOLD_LADDER = (
    ("GUIDED", 8),
    ("TUTORIAL", 6),
)

# The tier at which a clear stops being scaffolded and starts being production.
PRODUCTION_TIER = "EASY"


def unaided_at_or_above(state, tier: str) -> int:
    """Unaided clears this skill has earned at `tier` or anything harder."""
    if state is None:
        return 0
    record = getattr(state, "tier_unaided", None) or {}
    floor = tier_index(tier)
    return sum(count for name, count in record.items()
               if tier_index(name) >= floor)


def untracked_clears(state) -> int:
    """Clears this skill holds that were never filed under a tier.

    `apply_outcome` writes `clears` and `tier_clears` in the same breath, so
    for any evidence collected since the record existed the two agree exactly.
    A positive difference can therefore mean only one thing: those clears were
    earned by a build that did not keep the record.
    """
    if state is None:
        return 0
    record = getattr(state, "tier_clears", None) or {}
    return max(0, int(state.clears) - sum(record.values()))


def _tier_record_missing(state) -> bool:
    """Does this skill hold evidence from before clears were filed by tier?

    Absent evidence is not evidence of absence. A player who was mid-ramp when
    this shipped has real clears and no per-tier record of them, and holding
    them at GUIDED on that silence is the same lie as promoting them on five
    fill-in-the-blanks, pointed the other way. Those saves fall back to the
    mastery ladder.

    THE QUESTION IS "ARE THERE CLEARS OUTSIDE THE RECORD", NOT "IS THE RECORD
    EMPTY", and the difference is a shipped save being thrown back to the
    bottom of the ramp. Asking whether the record was empty made the exemption
    last exactly one encounter: a returning player with forty clears and
    mastery 70 was aimed at HARD on load, cleared one TUTORIAL problem, and
    with `tier_clears == {"TUTORIAL": 1}` the record was no longer empty — so
    the band was decided on that single clear, the player was demoted to
    GUIDED, and encounter two was rung one of the beginner chain. Measured:
    sixteen of their next twenty encounters were fill-in-the-blanks and seven
    were `print`. The forty clears do not stop being evidence because a
    forty-first arrived, so the comparison is against the whole of it.
    """
    return untracked_clears(state) > 0


def rung_record(state) -> dict:
    """Unaided clears filed by the RUNG of the ramp they were earned at."""
    if state is None:
        return {}
    record = getattr(state, "rung_unaided", None) or {}
    return {int(k): int(v) for k, v in record.items() if str(k).isdigit()}


def has_produced_code(state) -> bool:
    """Has this skill ever been cleared, unaided, on a blank screen?

    THE BAND IS NOT THE RUNG, and conflating the two was a live mastery farm.
    `PRODUCTION_TIER` is EASY, and the corpus contains 21 EASY problems that
    ship a two-or-three-blank scaffold. Clearing any one of them satisfied this
    predicate outright, which ended the scaffold band and satisfied the
    `scaffold` clause on every TIER_GATE above it — on the strength of having
    filled in two blanks. Measured, not reasoned: a fresh player with
    `tier_unaided == {"EASY": 1}` came out of here True.

    So the question is asked in the vocabulary that can answer it, and it takes
    BOTH halves: rung 4, and EASY or harder. Rung 4 alone is not enough, because
    a GUIDED one-liner with no declaration is served at rung 4 and would mint
    the evidence on encounter two — measured, that is exactly what happened, and
    it moved the mastery farm rather than closing it. EASY alone is not enough
    either, because 21 EASY problems ship a two-blank scaffold, which is the
    farm this started as. `skills.production_unaided` is the one tally that
    counts the conjunction.

    Because the rung is recorded from what the player was SHOWN (skills.
    apply_outcome, from the encounter), a scaffolded serving cannot produce
    rung-4 evidence. That is not a convention anybody has to remember — it is
    arithmetic.

    ABSENT EVIDENCE IS NOT EVIDENCE OF ABSENCE. A save written before rungs were
    recorded holds real clears and no rung record of them, and re-judging those
    under the new predicate would throw a returning player back to the bottom of
    the ramp — the exact trap `_tier_record_missing` already documents. Those
    saves fall through to the old reading, unchanged.
    """
    if int(getattr(state, "production_unaided", 0) or 0) >= 1:
        return True
    # And the clears that predate rungs being recorded. THE QUESTION IS "ARE
    # THERE UNAIDED EASY-OR-HARDER CLEARS OUTSIDE THE RUNG RECORD", NOT "IS THE
    # RUNG RECORD EMPTY" — measured, the second question makes the exemption
    # last exactly one encounter, and a fluent player who had skipped the
    # beginner chain met six rungs of it as soon as their first scaffolded clear
    # was filed.
    return untracked_production(state) >= 1


def untracked_production(state) -> int:
    """Unaided EASY-or-harder clears this skill holds that carry no rung."""
    if state is None:
        return 0
    filed = int(getattr(state, "production_seen", 0) or 0)
    return max(0, unaided_at_or_above(state, PRODUCTION_TIER) - filed)


# ---------------------------------------------------------------------------
# Which rung of the ramp this player has earned
# ---------------------------------------------------------------------------
#
# The rung comes from the player's measured competence on the skill, never from
# the problem. A problem that is always rung 2 is a problem the player can never
# graduate from, which is the thing the player asked not to have.
#
# The shape is `incantation.tier_for`, which has decided the scaffold tier for
# combat lines from evidence since the retrieval gradient shipped, and does
# every part of this right: it rises on accumulated unaided clears, falls one
# rung per consecutive miss, decays with time away, and is capped by mastery of
# the underlying skill, because typing speed cannot outrun comprehension.
#
# How much evidence buys the next rung. SCAFFOLD_LADDER's existing numbers —
# eight at the bottom, six above it — are the right grain and are kept; what
# changes is that they are counted per RUNG rather than per band.
#
# Six one-blank clears yield rung 3, and rung 4 only after that. Six pieces of
# evidence about writing one expression are six pieces of evidence about writing
# one expression, and none at all about writing a function.
# These three numbers ARE the curve. docs/14-the-ramp.md §1b decides the mix a
# band should serve — 95 / 70 / 35 / 10 / 0 scaffolded, strictly decreasing —
# and the only free parameter that produces it is how long a player stays on
# each rung.
#
# THEY ARE SIZED TO THE EVIDENCE ONE SKILL ACCUMULATES, NOT TO A BAND'S LENGTH.
# That distinction is the whole of this correction, and it is worth a paragraph
# because getting it wrong is invisible: 21 / 24 / 30 were solved against the
# measured length of a band in a real career — 62 GUIDED editor encounters, 59
# TUTORIAL, 75 EASY over 400 encounters — and the arithmetic was right for a
# question nobody was asking. EVIDENCE IS FILED PER SKILL. Those 241 editor
# encounters spread over eighteen skills: median fifteen apiece, and only
# HASH_MAP (32) and TWO_POINTER (31) ever reached 24. So no skill climbed off
# TUTORIAL's or EASY's floor in a whole career, and the mix the game served was
# not measured competence at all — it was declaration coverage clamped by the
# floor. Measured: TUTORIAL served 100.0% scaffolded against a 70% target and
# EASY 66.7% against 35%, with every TUTORIAL encounter on the band floor.
#
# Re-solved against what one skill actually holds, on the same 400-encounter
# replay: 8 / 9 / 11 puts TUTORIAL at 71.2% against its 70% and EASY at 49.3%.
# EASY stays above its 35% because 111 of its 164 editor problems carry two
# spans and rung 3 is EASY's own floor — that is a floor, not a climb, and the
# remedy for it is a band-wide judgement about EASY's floor rather than a number
# here.
#
# ORDER MATTERS AND IS NOT OPTIONAL. A faster climb is only safe once a GUIDED
# problem can actually serve rung 3: while 120 of the 184 GUIDED declarations
# carried a single span, climbing faster pushed more of them into
# `scaffold.servable`'s fall-up to rung 4 and took GUIDED DOWN to 53.2%. The
# second spans in `corpus/scaffolding.py` come first; these numbers come after.
#
# They are a design decision and they are meant to be revised by data. The first
# cohort through TUTORIAL is what should revise them.
RUNG_EVIDENCE = {
    scaffold.PICK: 8,
    scaffold.ONE_BLANK: 9,
    scaffold.MANY_BLANKS: 11,
}

# Time away returns support before the player notices. Same two steps as
# `incantation.tier_for`, and the same signal `SRS_INTERVALS_DAYS` encodes —
# expressed as help rather than as a due date.
RUNG_DECAY_DAYS = ((14.0, 2), (5.0, 1))


def _unaided_at_or_below(record: dict, rung: int) -> int:
    """Evidence earned at this rung or with MORE help than it.

    At-or-below, because a player who has been writing whole functions has
    obviously finished with one-blank problems and must not be sent back down
    for want of a tally at the easier rung.
    """
    return sum(count for name, count in record.items() if name >= rung)


def _mastery_ceiling(state) -> int:
    mastery = float(getattr(state, "mastery", 0.0) or 0.0)
    if mastery < 25:
        return scaffold.ONE_BLANK
    if mastery < 55:
        return scaffold.MANY_BLANKS
    return scaffold.WRITE_IT_ALL


def rung_for(state, difficulty: str, *, now=None, lapsed: bool = False) -> int:
    """The rung this player has earned on this skill, in this band.

    Never below the band's floor — that is structural and monotone and content
    drift cannot reach it — with exactly one exception, named here rather than
    hidden: a LAPSED spaced-repetition review drops the serving one rung, which
    is the only route to a scaffold at MEDIUM and the reason the expected mix
    puts 10% there rather than zero.
    """
    import time

    floor = scaffold.floor_for(difficulty)
    if lapsed:
        floor = max(scaffold.PICK, floor - 1)
    if state is None:
        return floor

    record = rung_record(state)
    if _tier_record_missing(state):
        # A save from before rungs were recorded holds real clears and no rung
        # record of them. Judging it on that silence would aim a competent
        # returning player at fill-in-the-blanks. It starts at the top instead —
        # and the misses and the decay below still apply, so the ramp can still
        # give support back to a returning player who needs it. What it will not
        # do is take it as read that they need it.
        earned = scaffold.WRITE_IT_ALL
    else:
        # The climb STARTS AT THE FLOOR, one rung at a time. The floor is where
        # this band admits the player; evidence is what carries them above it.
        # Starting the count at rung 1 regardless of band would hold a TUTORIAL
        # player at one blank until they had eight clears they were never going
        # to be offered, because rung 1 is a rung TUTORIAL may not serve.
        earned = floor
        while earned < scaffold.WRITE_IT_ALL:
            needed = RUNG_EVIDENCE.get(earned)
            if needed is None or _unaided_at_or_below(record, earned) < needed:
                break
            earned += 1

    # Falling back, one rung per miss in a row. No announcement, no penalty.
    earned -= int(getattr(state, "miss_streak", 0) or 0)

    last_seen = float(getattr(state, "last_seen", 0.0) or 0.0)
    if last_seen:
        days = max(0.0, ((time.time() if now is None else now) - last_seen) / 86400.0)
        for threshold, cost in RUNG_DECAY_DAYS:
            if days >= threshold:
                earned -= cost
                break

    earned = min(earned, _mastery_ceiling(state))
    if lapsed:
        # One rung of support back, not a fall to the bottom. `srs.schedule_after`
        # already halves the stage and the ease on a lapse; the rung moves with
        # it, by one. This is the ONLY thing in the game that serves a scaffold
        # at MEDIUM, and the only thing that serves one blank at EASY — which is
        # exactly where the expected mix puts its 10% in each of those bands.
        earned -= 1
    return max(floor, min(scaffold.WRITE_IT_ALL, earned))


def review_rung(*, lapsed: bool = False) -> int:
    """The rung a spaced-repetition review is served at.

    A review exists to MEASURE RETENTION, and a retained skill delivered with
    the answer half written measures nothing — `srs.schedule_after` would then
    grow the interval on the strength of it. So a review is the whole function
    by default, whatever rung the player is climbing elsewhere.

    A lapse drops it one rung, and only one: the player has just shown they
    have forgotten something, and the next sight of it should carry a little
    help rather than the same blank screen they have just failed at.
    """
    return scaffold.MANY_BLANKS if lapsed else scaffold.WRITE_IT_ALL


def servable_rung(problem, state, *, lapsed: bool = False, mode: str = "adventure",
                  now=None) -> int:
    """The rung a given problem is actually served at, for a given player.

    Three gates, all of which can only move the answer UP the ladder — towards
    less help — because every way of getting this wrong that the corpus has
    already demonstrated moved it down.
    """
    if mode in scaffold.UNSCAFFOLDED_MODES or getattr(problem, "sealed", False):
        # The practical, Timed Practical Mode and the hold-out are the whole function
        # with nothing to lean on, in any band, forever. A sealed problem is
        # never served at any rung, because a rung is a presentation OF a
        # problem and the seal is a property of the problem.
        return scaffold.WRITE_IT_ALL
    desired = rung_for(state, problem.difficulty, lapsed=lapsed, now=now)
    return scaffold.servable(problem, problem.difficulty, desired,
                             floor=lapse_floor(problem.difficulty) if lapsed else None)


# The bands the lapse exception does NOT reach. docs/14-the-ramp.md §1b says
# HARD is "0%, with no mechanism to reach anything else", and that sentence was
# true only by content accident: `lapse_floor` returned 3 for HARD, ELITE and
# BOSS exactly as it does for MEDIUM, and the only thing stopping a lapsed HARD
# review from being served two blanks was that 0 of the 20 HARD editor problems
# happen to carry a declaration. One declaration authored at HARD would have
# turned a documented structural guarantee into a bug, silently. MEDIUM's
# recovery rung is the one documented exception and stays.
NO_LAPSE_SCAFFOLD = frozenset({"HARD", "ELITE", "BOSS"})


def lapse_floor(difficulty: str) -> int:
    """The band's floor, one rung lower, for a lapsed review and nothing else."""
    if difficulty in NO_LAPSE_SCAFFOLD:
        return scaffold.WRITE_IT_ALL
    return max(scaffold.PICK, scaffold.floor_for(difficulty) - 1)


def scaffold_target(state):
    """The scaffold rung this player has not yet earned their way off.

    Returns "GUIDED", "TUTORIAL", or None — None meaning the band is finished
    with them and the mastery ladder takes over.
    """
    if state is None:
        return SCAFFOLD_LADDER[0][0]
    if has_produced_code(state) or _tier_record_missing(state):
        return None
    for tier, needed in SCAFFOLD_LADDER:
        if unaided_at_or_above(state, tier) < needed:
            return tier
    return None


def scaffold_cleared(state) -> bool:
    """Has this player finished the scaffold band?"""
    return scaffold_target(state) is None


# A tier opens for a skill when that skill clears the bar below it.
#   mastery         — evidence-weighted competence in the skill
#   unaided_clears  — solves with no hint spells cast
#   clears          — solves of any kind, assistance included
#   scaffold        — the band above must be finished, in this skill or in the
#                     language itself; unlocking and targeting have to agree, or
#                     the ramp says one thing and the gate says another
TIER_GATES = {
    "GUIDED":   {"mastery": 0,  "unaided": 0, "clears": 0},
    "TUTORIAL": {"mastery": 0,  "unaided": 0, "clears": 0},
    "EASY":     {"mastery": 12, "unaided": 0, "clears": 1, "scaffold": True},
    "MEDIUM":   {"mastery": 38, "unaided": 2, "clears": 4, "scaffold": True},
    "HARD":     {"mastery": 62, "unaided": 5, "clears": 8, "scaffold": True},
    "ELITE":    {"mastery": 72, "unaided": 7, "clears": 10, "scaffold": True},
    "BOSS":     {"mastery": 45, "unaided": 2, "clears": 4, "scaffold": True},
}


def tier_unlocked(state, tier: str, *, fluency=None) -> bool:
    """Has this skill earned the right to be asked a question at this tier?

    `fluency` is the PYTHON state, and it satisfies the scaffold clause on its
    own. The scaffold band is about the language, not about hash maps: a player
    who can write a function from nothing does not have to prove it again once
    per pattern, and requiring them to would be a deadlock anyway, since the
    proof only exists at tiers the clause is gating.
    """
    gate = TIER_GATES.get(tier)
    if gate is None:
        return True
    if state is None:
        return tier in ("GUIDED", "TUTORIAL")
    if gate.get("scaffold") and not (scaffold_cleared(state)
                                     or scaffold_cleared(fluency)):
        return False
    return (state.mastery >= gate["mastery"]
            and state.unaided_clears >= gate["unaided"]
            and state.clears >= gate["clears"])


def highest_unlocked_tier(state, *, fluency=None) -> str:
    best = "GUIDED"
    for tier in TIERS:
        if tier == "BOSS":
            continue
        if tier_unlocked(state, tier, fluency=fluency):
            best = tier
    return best


# ---------------------------------------------------------------------------
# The chapter ladder
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Chapter:
    id: str
    title: str
    blurb: str
    goal: str                    # what the player is told they are working toward
    skills: tuple                # skills this chapter trains
    families: tuple              # spaced_repetition_family values it draws from
    patterns: tuple              # patterns permitted while this is the newest chapter
    graduate_mastery: float      # mastery in `skills` needed to open the next chapter
    graduate_clears: int         # clears within this chapter needed
    region: str


# Ordered. Index is the chapter number; earlier chapters never close, they simply
# stop being the frontier.
CHAPTERS: tuple = (
    Chapter(
        id="fluency",
        title="I. The Language Itself",
        blurb="Variables, strings, lists, loops, conditionals. The alphabet before "
              "the sentences.",
        goal="Stop losing time to syntax. Typing Python should cost you nothing.",
        skills=("PYTHON",),
        families=("python_basics", "onboarding_basics", "onboarding_strings",
                  "onboarding_lists", "onboarding_loops", "onboarding_conditionals",
                  # The 57-rung beginner chain. It was reachable only because
                  # its patterns happened to be permitted here, which is not
                  # the same as this chapter claiming it — and a family no
                  # chapter claims is a family the ladder cannot reason about.
                  "first_steps_values", "first_steps_names", "first_steps_types",
                  "first_steps_calls", "first_steps_conditions",
                  "first_steps_loops", "first_steps_lists", "first_steps_indent",
                  "first_steps_functions", "first_steps_parameters",
                  "first_steps_return", "first_steps_errors",
                  "first_steps_handover"),
        patterns=("LANGUAGE", "STRING", "ARRAY", "SIMULATION"),
        graduate_mastery=26, graduate_clears=8,
        region="python_village",
    ),
    Chapter(
        id="structures",
        title="II. The Four Vaults",
        blurb="dict, set, list, tuple — what each one is FOR, and what it costs.",
        goal="Choose the structure before you write the loop.",
        skills=("PYTHON", "HASH_MAP", "SET"),
        families=("onboarding_dict", "onboarding_set", "onboarding_functions",
                  "python_basics", "dedupe", "set_ops"),
        patterns=("LANGUAGE", "HASH_MAP", "SET", "STRING", "ARRAY"),
        graduate_mastery=32, graduate_clears=10,
        region="python_village",
    ),
    Chapter(
        id="idiom",
        title="III. The Idioms",
        blurb="enumerate, zip, comprehensions, Counter, defaultdict, deque. The "
              "shorthand that makes Python fast to write.",
        goal="Write the idiomatic form first, not the transliterated-from-C form.",
        skills=("PYTHON", "HASH_MAP"),
        families=("onboarding_idioms", "onboarding_comprehensions",
                  "onboarding_collections", "python_basics", "counting", "frequency"),
        patterns=("LANGUAGE", "HASH_MAP", "SET", "STRING", "ARRAY", "SORTING"),
        graduate_mastery=40, graduate_clears=10,
        region="fields_of_syntax",
    ),
    Chapter(
        id="counting",
        title="IV. Counting and Membership",
        blurb="The hash map, properly. The single highest-yield pattern in any "
              "timed coding practical.",
        goal="Make 'have I seen this before?' an automatic reflex.",
        skills=("HASH_MAP", "SET", "PYTHON"),
        families=("two_sum", "counting", "frequency", "dedupe", "set_ops", "anagrams"),
        patterns=("HASH_MAP", "SET", "STRING", "ARRAY", "SORTING", "RECOGNITION"),
        graduate_mastery=48, graduate_clears=10,
        region="hashmap_highlands",
    ),
    Chapter(
        id="scanning",
        title="V. Scanning a Sequence",
        blurb="One pass, two indices. Sliding windows and converging pointers.",
        goal="Never restart a scan you could have continued.",
        skills=("SLIDING_WINDOW", "TWO_POINTER", "PREFIX_SUM"),
        families=("window_distinct", "window_k_distinct", "window_sum",
                  "fixed_window", "sorted_pair", "converging", "fast_slow",
                  "palindrome", "prefix_sum", "merge"),
        patterns=("SLIDING_WINDOW", "TWO_POINTER", "PREFIX_SUM", "HASH_MAP",
                  "SET", "STRING", "ARRAY", "SORTING", "RECOGNITION", "COMPLEXITY"),
        graduate_mastery=50, graduate_clears=12,
        region="sliding_window_marsh",
    ),
    Chapter(
        id="order",
        title="VI. Order and Structure",
        blurb="Stacks, queues, sorting, intervals, binary search. Problems where "
              "arrangement is the answer.",
        goal="Recognise when order buys you the solution.",
        skills=("STACK", "QUEUE", "SORTING", "BINARY_SEARCH", "INTERVALS", "HEAP"),
        families=("stack_matching", "stack_eval", "monotonic_stack", "stack_nesting",
                  "stack_simulation", "queue_window", "intervals", "binary_search",
                  "binary_search_answer", "top_k", "counting"),
        patterns=("STACK", "QUEUE", "SORTING", "BINARY_SEARCH", "INTERVALS", "HEAP",
                  "HASH_MAP", "SET", "ARRAY", "STRING", "SIMULATION", "MATRIX",
                  "RECOGNITION", "COMPLEXITY", "TESTING"),
        graduate_mastery=52, graduate_clears=12,
        region="stack_queue_mines",
    ),
    Chapter(
        id="recursion",
        title="VII. Things That Contain Themselves",
        blurb="Recursion, trees, backtracking. Define the base case, then trust "
              "the smaller call.",
        goal="Stop fearing the call stack.",
        skills=("RECURSION", "TREE", "DFS"),
        families=("recursion_basics", "recursion_divide", "backtracking",
                  "tree_traverse", "tree_paths", "bst", "tree_bfs", "tree_serialize"),
        patterns=("RECURSION", "TREE", "DFS", "BFS", "STACK", "QUEUE", "HASH_MAP",
                  "SET", "ARRAY", "STRING", "SORTING", "MATRIX", "BINARY_SEARCH",
                  "HEAP", "INTERVALS", "PREFIX_SUM", "SLIDING_WINDOW", "TWO_POINTER",
                  "RECOGNITION", "COMPLEXITY", "TESTING", "SIMULATION"),
        graduate_mastery=52, graduate_clears=12,
        region="recursive_forest",
    ),
    Chapter(
        id="traversal",
        title="VIII. Maps and Mazes",
        blurb="Grids and graphs. BFS for the shortest road, DFS for every road.",
        goal="Know which search answers the question being asked.",
        skills=("BFS", "DFS", "GRAPH", "MATRIX"),
        families=("grid_bfs", "grid_traverse", "graph_traverse", "graph_shortest",
                  "graph_paths", "graph_cycle", "graph_topo", "matrix_traverse",
                  "matrix_transform"),
        patterns=tuple(),                 # empty means "everything is permitted"
        graduate_mastery=52, graduate_clears=12,
        region="graph_wastes",
    ),
    Chapter(
        id="optimisation",
        title="IX. Paying Once",
        blurb="Dynamic programming, memoisation, complexity. Never solve the same "
              "subproblem twice.",
        goal="Turn exponential into linear, on purpose, and be able to say why.",
        skills=("DP", "BIG_O"),
        families=("dp_linear", "dp_grid", "dp_2d", "dp_string", "dp_subsequence",
                  "dp_knapsack", "dp_unbounded", "big_o"),
        patterns=tuple(),
        graduate_mastery=50, graduate_clears=10,
        region="dp_ruins",
    ),
    Chapter(
        id="craft",
        title="X. The Working Engineer",
        blurb="Debugging, testing, design, the object model and the runtime. "
              "What separates someone who can code from someone you would hire.",
        goal="Be the learner who finds their own bug, says the complexity "
             "before being asked, and writes a class somebody else can read.",
        skills=("DEBUGGING", "TESTING", "DESIGN", "COMMUNICATION", "BIG_O"),
        # THE OBJECT MODEL AND THE RUNTIME LIVE HERE, and the reason is bug
        # three. `__len__` and `__iter__` were hour-one content: a brand-new
        # player met `oopl-len-guided` and `oopl-iter-guided` at encounters nine
        # and ten. oop_language and generators wear SIMULATION, STRING and ARRAY
        # as no-better-word labels, chapter I permits all three, no chapter
        # claimed their families, and `is_permitted` let them through on the
        # pattern alone. Relabelling them first would have hidden them behind a
        # pattern nothing permits, which is a wall and not an order — so the
        # chapter claims them first, which is the sequence LANGUAGE_PROBLEM_IDS
        # has been asking for since it was written.
        #
        # This chapter rather than a twelfth one: the story spine is eleven
        # beats, one per chapter, and a twelfth chapter would need a twelfth
        # beat that nobody has written. It is also where the codebase already
        # said this material belonged — tests/test_coverage.py has filed
        # `oop_classes` under "the design work of chapter X" since before any of
        # it was reachable. Descriptors, dunders, decorators and generators are
        # not what any timed practical question in chapters IV to IX needs, and they
        # are exactly what separates code somebody can maintain from code that
        # merely runs.
        families=("debugging", "testing", "edge_cases", "code_reading", "design",
                  "big_o",
                  # the object model
                  "oop_classes", "oop_class_attrs", "oop_methods", "oop_repr",
                  "oop_inheritance", "oop_mro", "oop_property", "oop_slots",
                  "oop_container", "oop_iter", "oop_eq_hash", "oop_ordering",
                  "oop_exceptions", "oop_custom_exc", "oop_narrow_except",
                  "oop_mutability", "oop_typing", "oop_gil", "codebase_class",
                  # the runtime
                  "python_closures", "python_context", "python_decorators",
                  "python_generators", "python_iterators",
                  "stdlib_dataclasses", "stdlib_namedtuple", "stdlib_enum"),
        patterns=tuple(),
        graduate_mastery=55, graduate_clears=14,
        region="debugging_dungeon",
    ),
    Chapter(
        id="gauntlet",
        title="XI. Under Pressure",
        blurb="Everything at once, on a clock, with nothing labelled.",
        goal="Do all of it again when it counts.",
        skills=("SPEED", "RECALL"),
        families=tuple(),
        patterns=tuple(),
        graduate_mastery=100, graduate_clears=999,
        region="coding_coliseum",
    ),
)

CHAPTER_BY_ID = {c.id: c for c in CHAPTERS}


# ---------------------------------------------------------------------------
# LANGUAGE: the label for content that is not an algorithm
# ---------------------------------------------------------------------------
#
# Chapter I permitted three patterns — STRING, ARRAY, SIMULATION — and every
# problem in it had to wear one of them. So the first problem a new player ever
# meets, whose entire content is
#
#     doubled = n * 2
#
# was labelled STRING, and the interface printed STRING to them as the family
# they had just practised. The pattern label is shown on the encounter, written
# into the grimoire, and is the vocabulary the player is being trained to
# recognise a problem by. A wrong one is not cosmetic; it teaches the wrong
# word, and it teaches it at the exact moment the player has no way to tell.
#
# LANGUAGE is the missing fourth: the subject of this problem is Python itself.
# A statement, an operator, a parameter list, what a name binds to. No data
# structure is being exercised — swap the values for different values and the
# lesson is unchanged.
#
# THE LINE, drawn deliberately narrow so the label does not swallow chapter I
# and leave STRING and ARRAY never taught at all: a problem is LANGUAGE only
# when no data structure is its subject. `text[0]` stays STRING, because
# zero-based indexing into a sequence is what it is about. `items[1:-1]` stays
# ARRAY. `prices.get(item, 0)` stays HASH_MAP. `first, second = pair` becomes
# LANGUAGE, because the pair is scenery and unpacking assignment is the lesson.
#
# THE SECOND BOUNDARY is difficulty, and it is a ramp decision rather than a
# taxonomic one. Everything corrected below is GUIDED or TUTORIAL — the rungs
# chapter I is actually built out of. Chapter I permits LANGUAGE, and permits it
# forever, so anything wearing the label is reachable on day one with only the
# tier gate holding it back. Python's harder language content — decorators,
# context managers, generators, the MRO, __slots__, late binding, the mutable
# default — is language by the same definition and is deliberately NOT corrected
# here, because giving it this label would hand it to a beginner before some
# chapter claims its families. That is the fix to make next, and in that order:
# a chapter for the object model and the runtime, then the label.
#
# WHY THE IDS ARE LISTED HERE rather than set in the families: the label belongs
# on the Problem record, and that is where it should eventually live. This table
# is the correction applied at build time until each family carries
# pattern="LANGUAGE" at source. Every id below was read against its own
# statement and solution; none is a guess from the title. When a family adopts
# the label, delete its ids from here; `apply_pattern_corrections` refuses to
# build against an id that no longer exists, so the table cannot rot in silence.
LANGUAGE_PROBLEM_IDS = frozenset({
    # onboarding_basics — name binding, identity, types, print versus return.
    "ob-store-value",         # was STRING: `doubled = n * 2`
    "ob-say-hello",           # was STRING: print does not return
    "ob-number-to-text",      # was STRING: str(), because + will not mix types
    "ob-type-name",           # was STRING: type(value).__name__
    "lang-identity-guided",   # was STRING: `is None` versus falsiness
    "lang-unpack-guided",     # was ARRAY:  `first, second = pair`
    "lang-unpack-tutorial",   # was ARRAY:  `first, *rest = items`

    # onboarding_functions — parameters, defaults, *args, return.
    "ob-two-arguments",       # was ARRAY:  width * height, and no array anywhere
    "ob-return-not-print",    # was ARRAY:  return versus print, again
    "ob-default-argument",    # was STRING: a parameter with a default
    "lang-default-guided",    # was STRING: defaults are evaluated at def time
    "lang-default-tutorial",  # was STRING: two defaults at once
    "lang-args-guided",       # was ARRAY:  *args packs into a tuple
    "lang-args-tutorial",     # was STRING: fixed parameters before the starred one

    # onboarding_conditionals — branching, truthiness, the conditional expression.
    "ob-is-even",             # was SIMULATION: % and a single if
    "ob-bigger",              # was SIMULATION: if/else, one or the other
    "ob-grade",               # was SIMULATION: the elif ladder, and why order matters
    "lang-ternary-guided",    # was STRING: A if TEST else B
    "lang-ternary-tutorial",  # was STRING: three exhaustive ordered cases
    "lang-truthy-guided",     # was STRING: the falsy five, and what `or` returns

    # python_basics — traces and flaw-spots whose subject is a statement.
    "tr-assign-order",        # was ARRAY:  the right-hand side is evaluated first
    "tr-lost-value",          # was ARRAY:  a swap that overwrites the value it needs
    "tr-seconds-split",       # was SIMULATION: // and % taking a number apart
    "tr-alias",               # was ARRAY:  assignment binds a name, it does not copy
    "sf-indent-escape",       # was ARRAY:  in Python, depth is meaning

    # code_reading — the same aliasing lesson, read rather than written.
    "rp-cr-alias",            # was STRING: two names, one list
})


def corrected_pattern(problem) -> str:
    """The pattern this problem should be shown under."""
    if problem.id in LANGUAGE_PROBLEM_IDS:
        return "LANGUAGE"
    return problem.pattern


def apply_pattern_corrections(problems) -> int:
    """Relabel the language problems in place. Returns how many changed.

    Called once from corpus.build_all, before lineage and the hold-out are
    assigned, so that every consumer — validation, sealing, selection, the
    interface, the skill credit — sees one pattern per problem and the same one.

    An id in the table that no longer names a problem is fatal rather than
    ignored. A correction that has quietly stopped applying looks exactly like a
    correction that was never needed, and the way you find out is a beginner
    being told that storing a number is a STRING problem all over again. If a
    family has adopted pattern="LANGUAGE" at source, or the problem is gone,
    delete the id — that is the whole fix.
    """
    known = {problem.id for problem in problems}
    stale = sorted(LANGUAGE_PROBLEM_IDS - known)
    if stale:
        raise ValueError(
            "curriculum.LANGUAGE_PROBLEM_IDS names problems that are not in the "
            "corpus: " + ", ".join(stale) + ". Remove them from the table.")
    changed = 0
    for problem in problems:
        wanted = corrected_pattern(problem)
        if problem.pattern != wanted:
            problem.pattern = wanted
            changed += 1
    return changed


def _avg_mastery(skills: dict, names) -> float:
    values = [skills[n].mastery for n in names if n in skills]
    return sum(values) / len(values) if values else 0.0


def _clears_in(skills: dict, names) -> int:
    return sum(skills[n].clears for n in names if n in skills)


def chapter_progress(skills: dict, chapter: Chapter) -> dict:
    mastery = _avg_mastery(skills, chapter.skills)
    clears = _clears_in(skills, chapter.skills)
    by_mastery = min(1.0, mastery / max(chapter.graduate_mastery, 1))
    by_clears = min(1.0, clears / max(chapter.graduate_clears, 1))
    return {
        "mastery": round(mastery, 1),
        "mastery_target": chapter.graduate_mastery,
        "clears": clears,
        "clears_target": chapter.graduate_clears,
        "percent": round(100 * min(by_mastery, by_clears)),
        "graduated": mastery >= chapter.graduate_mastery
        and clears >= chapter.graduate_clears,
    }


def placement_floor(skills) -> int:
    """The chapter the diagnostic PLACED this player on, if it placed them.

    Carried on the skills mapping itself (skills.SkillBook) rather than passed
    down twenty call sites, and absent on anything that rebuilt a plain dict —
    which is the safe direction, since a lost floor under-places.
    """
    floor = getattr(skills, "placement_floor", 0) or 0
    return max(0, min(int(floor), len(CHAPTERS) - 1))


def frontier(skills: dict) -> int:
    """Index of the chapter the player is currently working through.

    A chapter is graduated only on BOTH counts: enough mastery, and enough actual
    clears. Mastery alone can be reached by a handful of lucky solves; clears alone
    can be reached without understanding. Requiring both is what makes the ramp
    honest.

    A PLACEMENT floors that answer, and floors it only — it can move the player
    forward and never back, and it never marks anything graduated, so nothing
    below it closes. The Trial of the Architect used to compute a chapter, print
    "You do not need the alphabet. We start at Counting and Membership", store
    it in the save, and then be read by nothing: the seeded mastery recomputed
    to chapter I and a fluent player was served twelve GUIDED fill-in-the-blanks
    in their first twenty encounters. Either the skip is real or the sentence
    comes out. This is the skip being real.
    """
    for index, chapter in enumerate(CHAPTERS):
        if not chapter_progress(skills, chapter)["graduated"]:
            return max(index, placement_floor(skills))
    return len(CHAPTERS) - 1


def open_chapters(skills: dict) -> list:
    """Everything up to and including the frontier, plus one chapter of lookahead
    so the world never feels like a corridor.

    Note that this is a PREFIX, always taken from the beginning. A placed player
    has the skipped chapters open too — they are behind the frontier, not shut.
    Nothing is lost by a skip; it is only not where they start.
    """
    edge = frontier(skills)
    return list(CHAPTERS[:min(edge + 2, len(CHAPTERS))])


def permitted_patterns(skills: dict) -> set:
    """The union of patterns the open chapters allow. An empty set means no
    restriction — from chapter VIII onward the whole corpus is fair game."""
    allowed: set = set()
    for chapter in open_chapters(skills):
        if not chapter.patterns:
            return set()
        allowed |= set(chapter.patterns)
    return allowed


def frontier_families(skills: dict) -> set:
    """The families of the chapter the player is working through right now.

    Distinct from `permitted_families`, which is everything the prefix and the
    lookahead allow. This is the narrower question the scorer asks when two
    candidates are otherwise level: which of them is what the player was told
    they are doing.
    """
    return set(CHAPTERS[frontier(skills)].families)


def permitted_families(skills: dict) -> set:
    families: set = set()
    for chapter in open_chapters(skills):
        families |= set(chapter.families)
    return families


# Every family some chapter owns. A family in here is served when its chapter
# is open and not before; a family in no chapter at all is governed by its
# pattern, as everything always was.
CLAIMED_FAMILIES = frozenset(f for c in CHAPTERS for f in c.families)


def is_permitted(problem, skills: dict, *, skill_state=None, fluency=None) -> bool:
    """Gate a single problem against all three mechanisms.

    Retests bypass this entirely — a pattern that is due is always permitted,
    because retention outranks sequencing. That exemption is applied by the
    caller, not here.

    THE FAMILY GATE runs first, and it is the half that was missing. A pattern
    is a coarse label and several families wear one because there is no better
    word for what they do: oop_language's `__len__` drill is filed under ARRAY,
    its `__repr__` drill under STRING, its exception work under SIMULATION.
    Chapter I permits all three, so a brand-new player met the object model at
    encounter nine. Letting a problem through on its pattern alone, while the
    chapter that OWNS its family is still shut, is the ladder being overruled by
    a naming convention.

    The rule is narrow: a family a chapter claims belongs to that chapter. A
    family no chapter claims is unaffected, which is most of the corpus and
    includes the deliberate cases — `breaking` files a COMPLEXITY problem under
    an early family precisely so that "what breaks this?" reaches chapter I, and
    that still works, because the family it borrows is claimed by an open
    chapter.
    """
    family = problem.spaced_repetition_family
    claimed_and_open = family in permitted_families(skills)
    if family in CLAIMED_FAMILIES and not claimed_and_open:
        return False
    patterns = permitted_patterns(skills)
    # A family an open chapter claims is allowed through even when its pattern
    # is not, so a chapter can pull in a specific drill.
    if patterns and problem.pattern not in patterns and not claimed_and_open:
        return False
    return tier_unlocked(skill_state, problem.difficulty, fluency=fluency)


def next_objective(skills: dict) -> dict:
    """What the player is working toward right now, in their own terms."""
    index = frontier(skills)
    chapter = CHAPTERS[index]
    progress = chapter_progress(skills, chapter)
    weakest = None
    worst = 101.0
    for name in chapter.skills:
        state = skills.get(name)
        if state is not None and state.mastery < worst:
            weakest, worst = name, state.mastery
    return {
        "index": index,
        "number": index + 1,
        "total": len(CHAPTERS),
        "id": chapter.id,
        "title": chapter.title,
        "blurb": chapter.blurb,
        "goal": chapter.goal,
        "region": chapter.region,
        "skills": list(chapter.skills),
        "focus_skill": weakest,
        "progress": progress,
        "next_title": CHAPTERS[index + 1].title if index + 1 < len(CHAPTERS) else None,
    }


def ladder(skills: dict) -> list:
    """The whole curriculum, annotated — for the quest log's progress view."""
    edge = frontier(skills)
    out = []
    for index, chapter in enumerate(CHAPTERS):
        progress = chapter_progress(skills, chapter)
        out.append({
            "number": index + 1,
            "id": chapter.id,
            "title": chapter.title,
            "blurb": chapter.blurb,
            "goal": chapter.goal,
            "region": chapter.region,
            # "skipped" rather than "done" for a chapter the placement floored
            # past: the player never worked it, and telling them it is finished
            # is the same untruth the placement itself used to tell. Skipped
            # chapters are open — their content is still served, and the ladder
            # says so rather than pretending the material is gone.
            "state": ("done" if index < edge and progress["graduated"] else
                      "skipped" if index < edge else
                      "current" if index == edge else
                      "next" if index == edge + 1 else "locked"),
            "progress": progress,
        })
    return out
