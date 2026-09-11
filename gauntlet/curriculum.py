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


# A tier opens for a skill when that skill clears the bar below it.
#   mastery         — evidence-weighted competence in the skill
#   unaided_clears  — solves with no hint spells cast
#   clears          — solves of any kind, assistance included
TIER_GATES = {
    "GUIDED":   {"mastery": 0,  "unaided": 0, "clears": 0},
    "TUTORIAL": {"mastery": 0,  "unaided": 0, "clears": 0},
    "EASY":     {"mastery": 12, "unaided": 0, "clears": 1},
    "MEDIUM":   {"mastery": 38, "unaided": 2, "clears": 4},
    "HARD":     {"mastery": 62, "unaided": 5, "clears": 8},
    "ELITE":    {"mastery": 72, "unaided": 7, "clears": 10},
    "BOSS":     {"mastery": 45, "unaided": 2, "clears": 4},
}


def tier_unlocked(state, tier: str) -> bool:
    """Has this skill earned the right to be asked a question at this tier?"""
    gate = TIER_GATES.get(tier)
    if gate is None:
        return True
    if state is None:
        return tier in ("GUIDED", "TUTORIAL")
    return (state.mastery >= gate["mastery"]
            and state.unaided_clears >= gate["unaided"]
            and state.clears >= gate["clears"])


def highest_unlocked_tier(state) -> str:
    best = "GUIDED"
    for tier in TIERS:
        if tier == "BOSS":
            continue
        if tier_unlocked(state, tier):
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
                  "onboarding_lists", "onboarding_loops", "onboarding_conditionals"),
        patterns=("STRING", "ARRAY", "SIMULATION"),
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
        patterns=("HASH_MAP", "SET", "STRING", "ARRAY"),
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
        patterns=("HASH_MAP", "SET", "STRING", "ARRAY", "SORTING"),
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
        blurb="Debugging, testing, design, communication. What separates someone "
              "who can code from someone you would hire.",
        goal="Be the candidate who finds their own bug and says the complexity "
             "before being asked.",
        skills=("DEBUGGING", "TESTING", "DESIGN", "COMMUNICATION", "BIG_O"),
        families=("debugging", "testing", "edge_cases", "code_reading", "design",
                  "big_o"),
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


def frontier(skills: dict) -> int:
    """Index of the chapter the player is currently working through.

    A chapter is graduated only on BOTH counts: enough mastery, and enough actual
    clears. Mastery alone can be reached by a handful of lucky solves; clears alone
    can be reached without understanding. Requiring both is what makes the ramp
    honest.
    """
    for index, chapter in enumerate(CHAPTERS):
        if not chapter_progress(skills, chapter)["graduated"]:
            return index
    return len(CHAPTERS) - 1


def open_chapters(skills: dict) -> list:
    """Everything up to and including the frontier, plus one chapter of lookahead
    so the world never feels like a corridor."""
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


def permitted_families(skills: dict) -> set:
    families: set = set()
    for chapter in open_chapters(skills):
        families |= set(chapter.families)
    return families


def is_permitted(problem, skills: dict, *, skill_state=None) -> bool:
    """Gate a single problem against both mechanisms.

    Retests bypass this entirely — a pattern that is due is always permitted,
    because retention outranks sequencing. That exemption is applied by the
    caller, not here.
    """
    patterns = permitted_patterns(skills)
    if patterns and problem.pattern not in patterns:
        # a family explicitly claimed by an open chapter is allowed through even
        # when its pattern is not, so a chapter can pull in a specific drill
        if problem.spaced_repetition_family not in permitted_families(skills):
            return False
    return tier_unlocked(skill_state, problem.difficulty)


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
            "state": ("done" if index < edge else
                      "current" if index == edge else
                      "next" if index == edge + 1 else "locked"),
            "progress": progress,
        })
    return out
