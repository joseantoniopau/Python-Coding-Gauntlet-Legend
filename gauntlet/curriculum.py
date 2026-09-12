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
# three different acts, and only the third one is what an interview asks for.
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


def has_produced_code(state) -> bool:
    """Has this skill ever been cleared, unaided, without a scaffold?"""
    return unaided_at_or_above(state, PRODUCTION_TIER) >= 1


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
              "coding interview.",
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
        goal="Be the candidate who finds their own bug, says the complexity "
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
        # not what any interview question in chapters IV to IX needs, and they
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
