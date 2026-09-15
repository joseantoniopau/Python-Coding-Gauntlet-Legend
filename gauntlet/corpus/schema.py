"""Problem schema, test helpers and the hint-tree scaffolding.

Every problem carries a *reference implementation* (a live Python callable used
at build time to compute expected outputs) and a *canonical solution* (source
text shown to the player as the worked solution). Validation runs the canonical
solution in the sandbox against tests derived from the reference. Two
independent implementations agreeing is what earns a problem its place in the
corpus.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

PATTERNS = [
    # LANGUAGE is first because it is the only one that is not an algorithm.
    # It means: the subject of this problem is Python itself — a statement, an
    # operator, a parameter list, what a name binds to — and no data structure
    # is being exercised. Chapter I is called The Language Itself and had no
    # pattern that said so, which is how `doubled = n * 2` came to be labelled
    # STRING and shown to a beginner under that word. The pattern label is what
    # the player is trained to recognise a problem by, so it has to be true.
    "LANGUAGE",
    "HASH_MAP", "SET", "SLIDING_WINDOW", "TWO_POINTER", "STACK", "QUEUE",
    "BFS", "DFS", "TREE", "RECURSION", "BINARY_SEARCH", "MATRIX", "HEAP",
    "PREFIX_SUM", "SORTING", "SIMULATION", "DP", "STRING", "ARRAY",
    "DESIGN", "GREEDY", "INTERVALS", "DEBUGGING", "COMPLEXITY", "TESTING",
]

DIFFICULTIES = ["GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS"]

SOURCE_TYPES = [
    "REPORTED_INTERVIEW",   # reported coding exercise pattern; legacy machine tag
    "COMPANY_PATTERN",      # reported pattern family; legacy machine tag
    "GENERAL_INTERVIEW",    # general coding exercise; legacy machine tag
    "GENERATED_VARIANT",    # authored variant of a family
    "SECURITY_VARIANT",     # security-domain transfer skin
    "REMEDIATION",          # micro-drill produced by failure analysis
]

ENCOUNTER_KINDS = [
    "CODE_BATTLE", "DEBUG_BATTLE", "MISSING_RUNE", "PATTERN_ENCOUNTER",
    "COMPLEXITY_DUEL", "EDGE_CASE_TRAP", "REFACTOR_QUEST", "CODE_READING",
    "TEST_FORGE", "SPEED_DUEL", "MEMORY_AMBUSH", "ELITE", "BOSS",
    # A Mini-Repo is NOT a Problem, and no Repo is ever built into the corpus:
    # it has no single entry point, no reference callable and no derived tests.
    # The string is here because this list is the one table of what a fight can
    # be, and a kind the engine can serve that the table has never heard of is
    # how the two quietly stop agreeing. See gauntlet/minirepo.py.
    "MINI_REPO",
]

REALMS = [
    "python_village", "fields_of_syntax", "hashmap_highlands",
    "stringwood_labyrinth", "array_caverns", "sliding_window_marsh",
    "twin_pointer_pass", "stack_queue_mines", "matrix_citadel",
    "recursive_forest", "binary_tree_canopy", "graph_wastes",
    "dp_ruins", "debugging_dungeon", "complexity_tower", "coding_coliseum",
    "null_kings_castle",
]

# Difficulty -> target solve seconds for the FAST mastery stage.
TARGET_SECONDS = {
    "GUIDED": 120, "TUTORIAL": 180, "EASY": 420, "MEDIUM": 900,
    "HARD": 1500, "ELITE": 1500, "BOSS": 2100,
}


# ---------------------------------------------------------------------------
# What a puzzle is allowed to tell the client
# ---------------------------------------------------------------------------
#
# Puzzle encounters carry their grading key in `mcq`, and `player_view` used to
# ship `mcq` whole. That handed `flawed_line`, `final_state`, every checkpoint's
# expected value and every snippet's cost straight to the browser, where a
# player who opens devtools once never has to solve another puzzle. So the key
# is named here, per kind, by what the interface genuinely renders — anything
# not on this list is withheld and lives only on the server, where the grader is.

PUZZLE_VISIBLE_MCQ = {
    # The Forge's `mcq` carries `kill_inputs` — one input per Mimic, on which
    # that Mimic provably differs from the honest implementation. That is the
    # answer to the encounter, so the only field that travels is how many Mimics
    # have to die.
    "TEST_FORGE":       ("min_kills",),
    "RUNE_ASSEMBLY":    ("runes", "shuffle"),
    "TRACE":            ("code", "checkpoints"),
    "SPOT_THE_FLAW":    ("code", "reference_code"),
    "STATE_PREDICT":    ("code", "operations"),
    "BREAK_IT":         ("flawed_code",),
    "COMPLEXITY_MATCH": ("snippets", "options"),
}

# Those three fields are lists of records, and some of the record is the answer.
PUZZLE_VISIBLE_ITEM = {
    "runes": ("text",),
    "checkpoints": ("after_line", "variable"),
    "snippets": ("label", "code"),
}


def redact_mcq(encounter_kind: str, mcq: dict) -> dict:
    """The part of `mcq` the player may see before their answer is graded."""
    keep = PUZZLE_VISIBLE_MCQ.get(encounter_kind)
    if keep is None:
        # Plain multiple choice: the choices are the question, the index is not.
        return {k: v for k, v in mcq.items()
                if k not in ("answer", "explanation", "distractors")}
    out = {}
    for key in keep:
        if key not in mcq:
            continue
        fields = PUZZLE_VISIBLE_ITEM.get(key)
        if fields is None:
            out[key] = mcq[key]
        else:
            out[key] = [{f: item[f] for f in fields if f in item}
                        for item in mcq[key]]
    return out


# ---------------------------------------------------------------------------
# Problem record
# ---------------------------------------------------------------------------

@dataclass
class Problem:
    id: str
    title: str
    realm: str
    pattern: str
    difficulty: str
    problem_statement: str
    entry: dict                                   # {kind, name, signature}
    canonical_solution: str
    encounter_kind: str = "CODE_BATTLE"
    secondary_patterns: list[str] = field(default_factory=list)
    source_type: str = "GENERAL_INTERVIEW"
    source_reference: str = ""
    reported_company: str = ""
    reported_year: str = ""
    provenance_note: str = ""
    examples: list[dict] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    starter_code: str = ""
    visible_tests: list[dict] = field(default_factory=list)
    hidden_tests: list[dict] = field(default_factory=list)
    edge_cases: list[dict] = field(default_factory=list)
    perf_tests: list[dict] = field(default_factory=list)
    alternate_solutions: list[dict] = field(default_factory=list)
    optimal_complexity: dict = field(default_factory=dict)   # {time, space}
    complexity_choices: list[str] = field(default_factory=list)
    common_failures: list[str] = field(default_factory=list)
    hint_tree: list[dict] = field(default_factory=list)
    visualization: dict = field(default_factory=dict)
    variants: list[str] = field(default_factory=list)
    security_variant: bool = False
    spaced_repetition_family: str = ""
    prerequisites: list[str] = field(default_factory=list)
    estimated_seconds: int = 600
    target_seconds: int = 600
    boss_eligible: bool = False
    profile_weight: dict = field(default_factory=dict)       # profile -> weight
    mcq: dict = field(default_factory=dict)                  # non-coding encounters
    tags: list[str] = field(default_factory=list)
    mutants: list[str] = field(default_factory=list)         # TEST_FORGE only

    # -- the ramp -----------------------------------------------------------
    #
    # `scaffold_spans` is the ONE declaration from which every rung of the ramp
    # is generated: an ordered list, best blank first, of spans of this
    # problem's own canonical solution that carry the idea, each with the
    # one-line gloss that becomes its numbered comment.
    #
    #   {"line": 3, "text": "counts.get(ch, 0) + 1", "nth": 1,
    #    "gloss": "build the tally for this character"}
    #
    #   rung 3  MANY BLANKS    strikes the first two or three spans
    #   rung 2  ONE BLANK      strikes span #1
    #   rung 1  PICK           strikes span #1 and offers four tokens
    #   rung 4  WRITE IT ALL   strikes the whole body
    #
    # The corpus used to author a rung as a separate problem with the rung
    # frozen into it, which is why TUTORIAL was 195 blank screens out of 202:
    # the middle rung cost a whole second problem, so nobody paid for it. A rung
    # is a PRESENTATION of a problem — see gauntlet/scaffold.py — so there is
    # one id, one canonical solution and one lineage, and a scaffolded serving
    # can never become a second piece of evidence about the same idea.
    #
    # `line` indexes `canonical_solution.split("\n")`, so the declaration is
    # checked against the answer at build time (`scaffold.round_trip`) rather
    # than being a second hand-maintained copy of it. It never travels to the
    # client: `player_view` pops it, for the same reason it pops the mcq answer.
    scaffold_spans: list[dict] = field(default_factory=list)

    # -- lineage and the sealed hold-out set --------------------------------
    #
    # `lineage_id` groups problems that are the same exercise wearing different
    # clothes: a template's skins, an authored problem and the variants
    # generated from it, a scaffolded entry rung and the full-dress version of
    # the same algorithm. Clearing five siblings is one piece of evidence, not
    # five, and the spaced repetition scheduler wants exactly that grouping.
    # It is derived at build time — see corpus.assign_lineage — never typed here.
    #
    # `sealed` marks a problem the teaching side of the game may never touch:
    # no Adventure encounter, no hint, no SRS review, no coaching, no worked
    # solution. It exists so that one measurement in this game is taken on a
    # formulation the player has provably never been shown. Chosen at build
    # time by hashing the id (corpus.seal_holdout), so it cannot drift under a
    # player between rebuilds — a hold-out that moves voids every number it
    # ever produced.
    #
    # Not to be confused with `finalexam.sealed()`, which asks whether a
    # capability is sealed off during an encounter. Different sense of the word,
    # both load-bearing; this one is a property of the corpus.
    lineage_id: str = ""
    sealed: bool = False

    # -- derived ------------------------------------------------------------
    @property
    def all_tests(self) -> list[dict]:
        return self.visible_tests + self.hidden_tests + self.edge_cases + self.perf_tests

    def to_dict(self) -> dict:
        return asdict(self)

    def player_view(self, *, mode: str) -> dict:
        """What the client is allowed to see before a submission is graded."""
        d = self.to_dict()
        d["mcq"] = redact_mcq(self.encounter_kind, self.mcq)
        d.pop("canonical_solution", None)
        d.pop("hidden_tests", None)
        d.pop("edge_cases", None)
        d.pop("perf_tests", None)
        d.pop("alternate_solutions", None)
        d.pop("mutants", None)
        d["hidden_test_count"] = len(self.hidden_tests) + len(self.edge_cases)
        # Hold-out membership does not travel. A player who can read which
        # problems are sealed can study the hold-out, and a studied hold-out
        # measures familiarity again — which is the entire thing it exists not
        # to measure. The server knows; the browser has no business knowing.
        d.pop("sealed", None)
        d.pop("lineage_id", None)
        # The spans ARE the answer — `scaffold_spans[0]["text"]` is the
        # expression the blank is asking for. The client gets the rendered rung
        # (marker and gloss) and never the text that fills it, which is the same
        # rule `redact_mcq` applies to the answer index.
        d.pop("scaffold_spans", None)
        if mode == "interview":
            # Timed Practical Mode measures. No teaching surface whatsoever.
            d["hint_tree"] = []
            d["visualization"] = {}
            d["common_failures"] = []
            d["pattern"] = "REDACTED"
            d["secondary_patterns"] = []
            d["optimal_complexity"] = {}
            d["variants"] = []
            d["prerequisites"] = []
        return d


# ---------------------------------------------------------------------------
# Test construction helpers
# ---------------------------------------------------------------------------

MAP_TAG = "__map__"


def encode_value(value: Any) -> Any:
    """JSON turns integer dict keys into strings. Tag such dicts so the sandbox
    can rebuild them exactly, or `{1: 'a'}` silently becomes `{'1': 'a'}` and
    every test involving a non-string key is quietly wrong."""
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            return {MAP_TAG: [[encode_value(k), encode_value(v)]
                              for k, v in value.items()]}
        return {k: encode_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_value(v) for v in value]
    return value


def case(name: str, args: list, expected: Any, *, cmp: str = "exact",
         hidden: bool = False, kind: str = "correctness", reveal: bool = True,
         timeout_ms: int | None = None) -> dict:
    t = {"name": name, "args": encode_value(copy.deepcopy(args)),
         "expected": encode_value(expected),
         "cmp": cmp, "hidden": hidden, "kind": kind, "reveal": reveal}
    if timeout_ms:
        t["timeout_ms"] = timeout_ms
    return t


def derive(reference: Callable, name: str, args: list, *, cmp: str = "exact",
           hidden: bool = False, kind: str = "correctness",
           reveal: bool = True, timeout_ms: int | None = None) -> dict:
    """Build a test whose expected value comes from the reference implementation."""
    expected = reference(*copy.deepcopy(args))
    if isinstance(expected, tuple):
        expected = list(expected)
    if isinstance(expected, set):
        expected = sorted(expected, key=repr)
        cmp = "set"
    return case(name, args, expected, cmp=cmp, hidden=hidden, kind=kind,
                reveal=reveal, timeout_ms=timeout_ms)


def ops_case(name: str, ops: list[str], args: list[list], expected: list,
             *, hidden: bool = False, reveal: bool = True) -> dict:
    return {"name": name, "ops": ops, "args": encode_value(copy.deepcopy(args)),
            "expected": encode_value(expected), "cmp": "exact", "hidden": hidden,
            "kind": "correctness", "reveal": reveal}


def derive_ops(cls: type, name: str, ops: list[str], args: list[list],
               *, hidden: bool = False, reveal: bool = True) -> dict:
    obj, out = None, []
    for op, a in zip(ops, args):
        if op == "__init__":
            obj = cls(*a)
            out.append(None)
            continue
        if obj is None:
            obj = cls()
        r = getattr(obj, op)(*a)
        out.append(list(r) if isinstance(r, tuple) else r)
    return ops_case(name, ops, args, out, hidden=hidden, reveal=reveal)


# ---------------------------------------------------------------------------
# Hint tree
# ---------------------------------------------------------------------------

HINT_SPELLS = ["ORACLE", "REVEAL_PATH", "VISION", "PSEUDOSIGHT",
               "CODE_FRAGMENT", "PHOENIX"]

PATTERN_ORACLE = {
    "HASH_MAP": "This is a HASH MAP problem. You are trading memory for lookup speed.",
    "SET": "This is a SET problem. You only care about membership, not counts.",
    "SLIDING_WINDOW": "This is a SLIDING WINDOW problem. A contiguous range under a constraint.",
    "TWO_POINTER": "This is a TWO POINTER problem. Two indices moving with intent.",
    "STACK": "This is a STACK problem. The most recent thing matters most.",
    "QUEUE": "This is a QUEUE problem. Oldest in, oldest out.",
    "BFS": "This is a BFS problem. Explore in expanding rings; the first arrival is shortest.",
    "DFS": "This is a DFS problem. Commit to one path, then unwind.",
    "TREE": "This is a TREE problem. Think about what each node needs from its children.",
    "RECURSION": "This is a RECURSION problem. Define the base case, then shrink the input.",
    "BINARY_SEARCH": "This is a BINARY SEARCH problem. Halve the search space each step.",
    "MATRIX": "This is a MATRIX problem. Watch your row/column index discipline.",
    "HEAP": "This is a HEAP problem. You need the extreme element repeatedly, not a full sort.",
    "PREFIX_SUM": "This is a PREFIX SUM problem. Precompute cumulative totals.",
    "SORTING": "This is a SORTING problem. Order first, then the answer becomes local.",
    "SIMULATION": "This is a SIMULATION problem. Model the state faithfully, step by step.",
    "DP": "This is a DYNAMIC PROGRAMMING problem. Overlapping subproblems, reused answers.",
    "STRING": "This is a STRING problem. Think in characters, counts and slices.",
    "ARRAY": "This is an ARRAY problem. Index arithmetic and a single clean pass.",
    "DESIGN": "This is a DESIGN problem. Choose the data structures before writing methods.",
    "GREEDY": "This is a GREEDY problem. A locally best choice is provably globally best here.",
    "INTERVALS": "This is an INTERVALS problem. Sort by start, then merge or count overlaps.",
    "DEBUGGING": "The algorithm is already right. One small mechanical detail is wrong.",
    "COMPLEXITY": "Count the work per element, then multiply by the number of elements.",
    "TESTING": "Think about what an incorrect implementation would still get right.",
}

PATTERN_STRUCTURE = {
    "HASH_MAP": "Reach for `dict` (or `collections.Counter` / `defaultdict`).",
    "SET": "Reach for `set` — O(1) membership.",
    "SLIDING_WINDOW": "Two indices `left`/`right` plus a `dict` of counts inside the window.",
    "TWO_POINTER": "Two integer indices, usually `left = 0` and `right = len(x) - 1`.",
    "STACK": "A plain Python `list` used with `.append()` and `.pop()`.",
    "QUEUE": "`collections.deque` with `.append()` and `.popleft()`.",
    "BFS": "`collections.deque` as the frontier plus a `visited` set.",
    "DFS": "Recursion (or an explicit list-as-stack) plus a `visited` set.",
    "TREE": "Recursion over `node.left` / `node.right`, with `None` as the base case.",
    "RECURSION": "A function that calls itself on a strictly smaller input.",
    "BINARY_SEARCH": "`lo`, `hi`, and `mid = (lo + hi) // 2`.",
    "MATRIX": "Nested indexing `grid[r][c]`; consider `zip(*grid)` for transpose.",
    "HEAP": "`heapq` over a list; negate values for a max-heap.",
    "PREFIX_SUM": "A running total plus a `dict` mapping prefix value to index/count.",
    "SORTING": "`sorted(..., key=...)` — then a single pass.",
    "SIMULATION": "Whatever fields the state genuinely needs. Keep them minimal.",
    "DP": "A list `dp` indexed by subproblem, or a memo `dict`.",
    "STRING": "`collections.Counter`, slicing, and `str.join`.",
    "ARRAY": "The list itself plus a couple of index variables.",
    "DESIGN": "Compose a `dict` with a `list`/`deque` — one for lookup, one for order.",
    "GREEDY": "Sort, then a single accumulator variable.",
    "INTERVALS": "A list sorted by start, plus the current merged interval.",
    "DEBUGGING": "Read the failing test, then trace that exact input by hand.",
    "COMPLEXITY": "Nothing — reason about the loops you can see.",
    "TESTING": "A list of (input, expected) tuples that includes the ugly cases.",
}


def build_hint_tree(pattern: str, *, nudge: str, visual: str, pseudocode: str,
                    fragment: str, solution: str) -> list[dict]:
    """Five escalating rungs. Nobody stays stuck; the cost is only rank."""
    return [
        {"level": 1, "spell": "ORACLE", "mana": 3, "rank_cost": "A",
         "title": "Oracle", "body": PATTERN_ORACLE.get(pattern, "") + "\n\n" + nudge},
        {"level": 2, "spell": "REVEAL_PATH", "mana": 4, "rank_cost": "A",
         "title": "Reveal Path", "body": PATTERN_STRUCTURE.get(pattern, "") + "\n\n" + visual},
        {"level": 3, "spell": "PSEUDOSIGHT", "mana": 6, "rank_cost": "B",
         "title": "Pseudosight", "body": pseudocode},
        {"level": 4, "spell": "CODE_FRAGMENT", "mana": 8, "rank_cost": "C",
         "title": "Code Fragment", "body": fragment},
        {"level": 5, "spell": "PHOENIX", "mana": 12, "rank_cost": "LEARNING_CLEAR",
         "title": "Phoenix", "body": solution},
    ]


def dumps(problems: Iterable[Problem]) -> str:
    return json.dumps([p.to_dict() for p in problems], indent=1)
