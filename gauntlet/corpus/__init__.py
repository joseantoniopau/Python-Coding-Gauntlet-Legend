"""Corpus assembly: authored families plus generated variants, all validated.

Two things happen here that nothing else in the game is allowed to undo.

LINEAGE. Problems that are the same exercise wearing different clothes share a
`lineage_id`. Five skins of one template, an authored problem and the variants
generated from it, a scaffolded entry rung and the full-dress version of the
same algorithm — one lineage, one piece of evidence. The grouping is derived,
never hand-labelled: 956 hand labels would be 956 opportunities to lie.

THE SEALED HOLD-OUT. A slice of the corpus is marked `sealed` at build time and
never shown by the teaching side of the game. It is the only content that can
answer the question the player actually asked — does this transfer to a
formulation I have never seen? — and it can only answer it once. Everything
below exists to keep that one answer honest.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import io
import itertools
import json
import re
import sys
import types
from collections import Counter, defaultdict
from pathlib import Path

from .. import config, curriculum
from . import scaffolding
from .schema import MAP_TAG, Problem

_FAMILIES = (
    # The bottom of the ramp, and therefore first: no function, no `def`, no
    # parameter until a player has met each one on its own. Everything else in
    # this tuple assumes the five concepts this family exists to teach.
    "first_steps",
    "onboarding", "scaffolds", "parsons", "breaking",
    "arrays_hashing", "sliding_window", "two_pointers", "stacks_queues",
    "trees", "matrix_graphs", "recursion_dp", "python_village",
    "binary_search", "design_oop", "debugging", "meta", "reasoning", "rematch_variants",
    # Ramp-first families: each of these enters every topic it owns at GUIDED
    # or TUTORIAL, which is why they are listed after the original seventeen
    # rather than folded into them.
    "language", "pythonic", "oop_language", "generators",
    "linked_structures", "search_optimize", "practical_test",
    # The entry rungs. Authored from a ramp audit rather than from a subject:
    # every topic that had no GUIDED or TUTORIAL doorway now has one.
    "ramp",
)


def build_all() -> list:
    """Every authored problem plus every generated variant, unvalidated.

    Lineage and the hold-out are assigned here rather than in `ensure`, so that
    every caller — the CLI, the test suite, a one-off script — gets the same
    corpus. A build where only some callers know what is sealed is a build with
    two different answers to "has the player seen this".
    """
    import importlib
    from . import generator

    problems: list = []
    for name in _FAMILIES:
        module = importlib.import_module(f".families.{name}", __package__)
        problems.extend(module.build())
    problems.extend(generator.generate())
    # The pattern label is the vocabulary the player is trained on, so it is
    # corrected before anything downstream reads it — lineage, the hold-out,
    # validation, selection and the interface all see one answer. See
    # curriculum.LANGUAGE_PROBLEM_IDS for what is corrected and why.
    curriculum.apply_pattern_corrections(problems)
    assign_lineage(problems)
    seal_holdout(problems)
    # AFTER the hold-out, deliberately. The ramp's declarations name spans of a
    # canonical solution that already exists; they create no problem, no id and
    # no lineage, so `assign_lineage` and `seal_holdout` see byte-for-byte the
    # input they saw before this line existed and produce the same 122 ids.
    # Running it here rather than earlier is what makes that true by
    # construction rather than by inspection. See tests/test_ramp.py.
    scaffolding.apply(problems)
    return problems


# ===========================================================================
# LINEAGE
# ===========================================================================
#
# Two problems share a lineage when solving one teaches you the other. That is
# a claim about code, not about titles, so it is settled by looking at code —
# by three signals, in order of how much they prove:
#
#   1. DECLARED. generator.py knows which template and which mode produced a
#      variant; the skins are the clothes and the mode is the exercise. It says
#      so in `tags` and we take its word.
#   2. STRUCTURAL. Two canonical solutions that are the same syntax tree once
#      local names are anonymised are the same solution, typed twice. This is
#      what catches an authored problem and the generated variants of it, and a
#      security reskin of a tree walk sitting in a different family.
#   3. BEHAVIOURAL. Two canonical solutions that satisfy each other's tests
#      compute the same function. This is what catches the same exercise
#      written two different ways — the hand-rolled two-sum and the Counter
#      one — which the structural signal cannot see.
#
# Where none of the three fires, a lineage of one is the answer. Titles that
# rhyme are not evidence, and guessing two problems together would quietly
# shrink the hold-out for no reason anyone could audit.


class _Anonymise(ast.NodeTransformer):
    """Rename everything the author chose; keep everything the algorithm needs.

    Local names, parameters and the entry function's own name are clothes: a
    template skin changes `window_sum_market` to `window_sum_guild` and nothing
    else. Imported names, attributes, keyword arguments and every literal stay,
    because `Counter` versus `dict`, `popleft` versus `pop`, and `'aeiou'`
    versus `'0123456789'` are the difference between two exercises.
    """

    def __init__(self, keep: set):
        self.keep = keep
        self.names: dict = {}

    def _sub(self, name: str) -> str:
        if name in self.keep or name.startswith("__"):
            return name
        return self.names.setdefault(name, f"n{len(self.names)}")

    def visit_FunctionDef(self, node):
        node.name = self._sub(node.name)
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.name = self._sub(node.name)
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        node.arg = self._sub(node.arg)
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        node.id = self._sub(node.id)
        self.generic_visit(node)
        return node

    def visit_ExceptHandler(self, node):
        if node.name:
            node.name = self._sub(node.name)
        self.generic_visit(node)
        return node


def _imported_names(tree: ast.AST) -> set:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                out.add((alias.asname or alias.name).split(".")[0])
    return out


def _skeleton(source: str) -> str:
    """The shape of a solution with the author's naming taken off it."""
    tree = ast.parse(source)
    tree = _Anonymise(_imported_names(tree)).visit(tree)
    ast.fix_missing_locations(tree)
    return ast.dump(tree, annotate_fields=False)


def _digest(*parts) -> str:
    sha = hashlib.sha256()
    for part in parts:
        sha.update(str(part).encode("utf-8", "replace"))
        sha.update(b"\x00")
    return sha.hexdigest()


def _algorithm_key(problem: Problem) -> str:
    """A content key that is equal for two problems with the same solution.

    Puzzles and multiple choice do not have a solution to compare, so the
    graded key itself is the exercise: two TRACE puzzles over the same spell
    with the same checkpoints are one exercise, and two that are not, are not.
    """
    kind = problem.entry.get("kind")
    if kind == "mcq":
        return _digest("mcq", problem.mcq.get("code", ""),
                       problem.mcq.get("choices"), problem.mcq.get("answer"),
                       problem.problem_statement)
    try:
        shape = _skeleton(problem.canonical_solution)
    except SyntaxError:
        # An mcq's "canonical solution" is the winning choice, in prose.
        shape = "raw:" + problem.canonical_solution
    extra = ""
    if problem.mutants:
        parts = []
        for mutant in problem.mutants:
            try:
                parts.append(_skeleton(mutant))
            except SyntaxError:
                parts.append(mutant)
        extra += "mutants:" + "|".join(sorted(parts))
    if problem.mcq and kind != "test_forge":
        # A puzzle wraps a solution in a question; the question is the exercise.
        extra += "puzzle:" + _digest(json.dumps(problem.mcq, sort_keys=True,
                                                default=str))
    return _digest("code", kind, shape, extra)


# --- signal 3: do two solutions compute the same function? -----------------

def _decode(value):
    """Undo schema.encode_value, so a test's arguments can be used directly."""
    if isinstance(value, dict):
        if len(value) == 1 and MAP_TAG in value:
            return {_decode(k): _decode(v) for k, v in value[MAP_TAG]}
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _type_signature(value, depth: int = 0) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (list, tuple)):
        outer = "list" if isinstance(value, list) else "tuple"
        if depth >= 2:
            return outer
        if not value:
            return outer + "[]"
        inner = {_type_signature(v, depth + 1) for v in value[:8]}
        return f"{outer}[{'|'.join(sorted(inner))}]"
    if isinstance(value, dict):
        if depth >= 2:
            return "dict"
        if not value:
            return "dict[]"
        keys = {_type_signature(k, depth + 1) for k in list(value)[:8]}
        vals = {_type_signature(v, depth + 1) for v in list(value.values())[:8]}
        return f"dict[{'|'.join(sorted(keys))}:{'|'.join(sorted(vals))}]"
    return type(value).__name__


def _widen(a: str, b: str):
    if a == b:
        return a
    for narrow, wide in ((a, b), (b, a)):
        if narrow.endswith("[]") and wide.startswith(narrow[:-2]):
            return wide
        if narrow in ("list", "tuple", "dict") and wide.startswith(narrow):
            return wide
    if {a, b} == {"int", "float"}:
        return "float"
    return None


def _argument_shape(probes: list):
    """One type signature covering every probe, or None if they disagree.

    This is a safety rail as much as a filter. Feeding one problem's arguments
    to another problem's solution is how the behavioural check works, and
    `seed * 1103515245` with a list where an int was expected allocates a
    billion-element list before anything can stop it. Same shapes only.
    """
    if not probes:
        return None
    shape = [_type_signature(arg) for arg in probes[0]]
    for probe in probes[1:]:
        if len(probe) != len(shape):
            return None
        for i, arg in enumerate(probe):
            widened = _widen(shape[i], _type_signature(arg))
            if widened is None:
                return None
            shape[i] = widened
    return tuple(shape)


class _StepBudget(Exception):
    pass


_STEP_LIMIT = 4000


def _call_bounded(fn, args):
    """Run a solution on somebody else's input without betting the build on it.

    A line-event budget is the only stdlib way to stop a `while` loop that was
    never meant to see this input, and this runs on a player's machine, so a
    build that hangs is a game that will not start.
    """
    left = [_STEP_LIMIT]

    def trace(frame, event, arg):
        if event == "line":
            left[0] -= 1
            if left[0] < 0:
                raise _StepBudget()
        return trace

    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        result = fn(*copy.deepcopy(args))
        if isinstance(result, types.GeneratorType) or (
                hasattr(result, "__next__") and hasattr(result, "__iter__")):
            result = list(itertools.islice(result, 300))
        return result
    finally:
        sys.settrace(previous)


def _same_answer(a, b) -> bool:
    if a == b and type(a) is type(b):
        return True
    if isinstance(a, (list, set, tuple)) and isinstance(b, (list, set, tuple)):
        try:
            return sorted(map(repr, a)) == sorted(map(repr, b))
        except TypeError:
            return False
    return False


def _behavioural_links(problems: list) -> list:
    """Pairs whose canonical solutions answer each other's tests identically.

    Restricted to plain functions with the same family and the same argument
    shape: the adapters that turn a list into a TreeNode live in the sandbox,
    not here, and comparing across families would be a claim the evidence does
    not support.
    """
    candidates = []
    for problem in problems:
        entry = problem.entry
        if entry.get("kind") != "function":
            continue
        if entry.get("preamble") or entry.get("arg_adapters") or entry.get("result_adapter"):
            continue
        probes = [_decode(t["args"])
                  for t in (problem.visible_tests + problem.hidden_tests)[:3]
                  if "args" in t]
        if len(probes) < 2:
            continue
        shape = _argument_shape(probes)
        if shape is None:
            continue
        namespace: dict = {}
        try:
            exec(compile(problem.canonical_solution, f"<{problem.id}>", "exec"),
                 namespace)
            fn = namespace[entry["name"]]
        except Exception:
            continue
        candidates.append((problem, fn, probes, shape))

    buckets = defaultdict(list)
    for entry in candidates:
        buckets[(entry[0].spaced_repetition_family, entry[3])].append(entry)

    def equivalent(left, right) -> bool:
        for args in left[2] + right[2]:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    a = _call_bounded(left[1], args)
                    b = _call_bounded(right[1], args)
            except Exception:
                return False        # disagreeing by raising is still disagreeing
            if not _same_answer(a, b):
                return False
        return True

    links = []
    for key in sorted(buckets, key=lambda k: (k[0], k[1])):
        representatives = []
        for entry in buckets[key]:
            for other in representatives:
                if equivalent(other, entry):
                    links.append((other[0].id, entry[0].id))
                    break
            else:
                representatives.append(entry)
    return links


class _Union:
    def __init__(self, keys):
        self.parent = {k: k for k in keys}

    def find(self, key):
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Smallest key wins, so the grouping does not depend on input order.
            lo, hi = sorted((ra, rb))
            self.parent[hi] = lo


def assign_lineage(problems: list) -> dict:
    """Stamp every problem with its `lineage_id`. Returns lineage -> problems."""
    union = _Union([p.id for p in problems])

    by_algorithm = defaultdict(list)
    declared = defaultdict(list)
    for problem in problems:
        by_algorithm[_algorithm_key(problem)].append(problem.id)
        for tag in problem.tags:
            if tag.startswith("lineage:"):
                declared[tag].append(problem.id)

    for group in (list(by_algorithm.values()) + list(declared.values())):
        for other in group[1:]:
            union.join(group[0], other)
    # A coached rematch follows an already taught boss. Keep its evidence in
    # that teaching lineage even when the changed contract needs new code.
    known = {p.id for p in problems}
    for problem in problems:
        for tag in problem.tags:
            if tag.startswith("rematch-of:") and tag.split(":", 1)[1] in known:
                union.join(problem.id, tag.split(":", 1)[1])
    for a, b in _behavioural_links(problems):
        union.join(a, b)

    members = defaultdict(list)
    for problem in problems:
        members[union.find(problem.id)].append(problem)

    index = {}
    for root in sorted(members):
        group = members[root]
        # The id is content-addressed rather than positional: adding a problem
        # somewhere else in the corpus must not rename anybody's lineage, or
        # every "have they seen this" answer in a save file turns to noise.
        family = min(p.spaced_repetition_family or "unfamilied" for p in group)
        originals = [p for p in group if not any(t.startswith("rematch-of:") for t in p.tags)]
        key = min(_algorithm_key(p) for p in (originals or group))[:10]
        lineage_id = f"lin-{family}-{key}"
        for problem in group:
            problem.lineage_id = lineage_id
        index[lineage_id] = sorted(group, key=lambda p: p.id)
    return index


# ===========================================================================
# THE SEALED HOLD-OUT SET
# ===========================================================================
#
# Four rules govern the choice, and they are in priority order, because they
# genuinely conflict and pretending otherwise is how a corpus ends up with an
# unlearnable topic.
#
#   1. WHOLE LINEAGES ONLY. A sealed problem with a teachable sibling is not an
#      unseen problem, and a transfer score built on it is a lie with a
#      percentage sign after it.
#   2. THE RAMP SURVIVES. Every topic keeps a GUIDED or TUTORIAL doorway that
#      the teaching side can still reach. An unmeasured topic is a gap; an
#      unlearnable one is a wall, and the wall is worse.
#   3. SPREAD. Every pattern the corpus teaches gets sealed representation
#      wherever rule 2 leaves room, or the transfer number describes one corner
#      of the syllabus and is quoted as if it described the whole thing.
#   4. MEDIUM AND EASY FIRST. Sealing the hardest problems measures whether the
#      player can do hard problems. The question is whether ordinary knowledge
#      transferred, so ordinary problems are what the hold-out is made of.
#
# The choice is a hash of the problem id, never a random draw. A hold-out that
# moves between rebuilds voids every measurement ever taken against it.

SEALED_TARGET = 0.12            # aim here
SEALED_BAND = (0.10, 0.15)      # never leave here
SEALED_HARD_SHARE = 0.10        # at most this fraction of the hold-out is HARD
SEALED_ORDINARY_SHARE = 0.60    # at least this fraction is EASY or MEDIUM

GENTLE = ("GUIDED", "TUTORIAL")
STEEP = ("HARD", "ELITE", "BOSS")


def _rank(lineage_id: str) -> str:
    return hashlib.sha256(lineage_id.encode()).hexdigest()


# Problems the rest of the game names by id. A quest that opens with
# `tr-validate-bst`, a boss that demands `mx-rotate`, a test that asserts
# something about `sw-min-window`: sealing one of those does not measure
# transfer, it deletes content the game already promised somewhere else.
#
# The list is derived — `named_in_source` below reads the source for its own
# string literals and validation fails the build the moment it finds an id that
# is not here. It is written down anyway, rather than scanned at build time,
# because the packaged app ships `gauntlet/` and `web/` and not `tests/`: a
# scanned list would come out shorter on a player's machine than on the machine
# that authored the corpus, and the hold-out would quietly differ between them.
# A hold-out that differs between two builds of the same game is not a hold-out.
RESERVED = (
    "rm-anagram-index-pairs", "rm-bst-subtree-report", "rm-shortest-node-path",
    "rm-streaming-window-max", "rm-wildcard-window-cover",
    "rp-three-sum-pair", "sw-longest-no-repeat-substr", "tp-trap-water",
    "rp-matrix-rotate-counter", "mx-transpose", "tr-lowest-common", "ds-undo-redo",
    "rp-tree-deserialize", "db-window-slice", "db-column-bounds", "ds-time-map",
    "ah-group-anagrams", "ah-three-sum", "ah-two-sum-indices", "bs-search",
    "db-bfs-visited", "db-keyerror", "db-off-by-one-range", "dp-climb-stairs",
    "ds-lru-cache", "ds-text-editor", "gr-bfs-order", "gr-shortest-hops",
    "mx-rotate", "sq-valid-parens", "sw-k-distinct", "sw-longest-no-repeat",
    "sw-max-sliding-window", "sw-min-window", "tf-sum-list",
    "tp-container-water", "tp-valid-palindrome", "tr-max-depth", "tr-path-sum",
    "tr-serialize", "tr-validate-bst",
    # The language rungs, named one by one in curriculum.LANGUAGE_PROBLEM_IDS
    # because their pattern label is corrected at build time. Reserved for the
    # ordinary reason: the source names them, so the hold-out may not take them
    # out from under it. None of them was sealable anyway — every one is a
    # GENTLE rung and rule 2 already protects those — so this reserves nothing
    # the hold-out was going to want.
    "lang-args-guided", "lang-args-tutorial", "lang-default-guided",
    "lang-default-tutorial", "lang-identity-guided", "lang-ternary-guided",
    "lang-ternary-tutorial", "lang-truthy-guided", "lang-unpack-guided",
    "lang-unpack-tutorial", "ob-bigger", "ob-default-argument", "ob-grade",
    # The root of the first_steps chain. tests/test_first_steps.py names it: it
    # is the one problem in the corpus that has to be a brand-new player's very
    # first encounter, so the test asserts on it by id. Reserved for the
    # ordinary reason — the source names it, so the hold-out may not take it —
    # and, like the language rungs below, it was never sealable anyway: every
    # first_steps rung is GENTLE and sits in a lineage of GENTLE rungs, which
    # `_sealable` refuses outright.
    "fs-see-a-value", "fs-write-banner",
    "ob-is-even", "ob-number-to-text", "ob-return-not-print", "ob-say-hello",
    "ob-store-value", "ob-two-arguments", "ob-type-name", "rp-cr-alias",
    "sf-indent-escape", "tr-alias", "tr-assign-order", "tr-lost-value",
    "tr-seconds-split",
    # The world layer. Quests, sages, dungeons, arts and the mini-repos name
    # these by id the same way the bosses above name theirs, and they arrived
    # after this list was last written down — which is exactly the drift
    # `named_in_source` exists to catch. Reserved for the one reason anything
    # is reserved: the game already promised them somewhere a player can reach,
    # so the hold-out may not take them back.
    "ah-longest-consecutive", "ah-top-k-frequent", "ah-two-sum-count",
    "bk-loopbound-find-index", "bs-min-capacity", "bs-rotated", "cx-grid-work",
    "cx-lookup-four-ways", "cx-space-tradeoff", "db-binary-search",
    "db-modulo-negative", "dp-edit-distance", "dp-house-robber", "dp-lis",
    "gr-count-islands", "gr-detect-cycle", "gr-topo-order", "ll-cycle-entry",
    "mx-spiral", "ob-add-lists", "ob-double-each", "ob-index-of", "ob-initials",
    "ob-keep-long-words", "ob-top-words", "pt-bug-denominator", "pt-class-apply",
    "pt-feature-date-range", "pt-feature-env-overrides", "rc-combination-sum",
    "sc-first-unique-char", "sec-risk-pairing", "so-bt-n-queens",
    "so-bt-palindrome-partition", "sq-daily-temperatures", "sq-next-greater",
    "sq-simplify-path", "sw-find-anagrams", "sw-k-categories",
    "tr-all-path-sums", "tr-level-order",
)


def reserved_ids(problems: list) -> set:
    """The protected ids that actually exist in this corpus."""
    return {p.id for p in problems} & set(RESERVED)


def named_in_source(problems: list) -> set:
    """Problem ids the rest of the source names as string literals.

    Returns an empty set where the source is not on disk to be read, because
    "I could not look" and "there is nothing there" are different answers and
    only validation running in a source tree is entitled to the second one.
    """
    ids = {p.id for p in problems}
    root = Path(__file__).resolve().parent.parent.parent
    if not (root / "tests").exists():
        return set()                # a packaged build; the scan would be partial
    literals: set = set()
    for folder in ("gauntlet", "tests", "web"):
        base = root / folder
        if not base.exists():
            continue
        for source in base.rglob("*"):
            if source.suffix not in (".py", ".js", ".html"):
                continue
            if "corpus" in source.parts:
                continue            # the families are where the ids are born
            try:
                text = source.read_text(errors="ignore")
            except OSError:
                continue
            literals.update(re.findall(r"['\"]([A-Za-z0-9_\-]{3,60})['\"]", text))
    return ids & literals


def _gentle_ledger(problems: list) -> tuple:
    """How many gentle rungs each topic and each pattern still has."""
    by_family: Counter = Counter()
    by_pattern: Counter = Counter()
    for problem in problems:
        if problem.difficulty in GENTLE:
            by_family[problem.spaced_repetition_family] += 1
            by_pattern[problem.pattern] += 1
    return by_family, by_pattern


def _sealable(group: list, reserved: set, by_family: Counter,
              by_pattern: Counter) -> bool:
    """Could this lineage be sealed at all, budget aside?

    Three ways to fail. It contains a problem the rest of the game names by id.
    It is nothing but entry rungs, so sealing it costs the ramp and measures
    nothing. Or it holds the last gentle rung of some topic, which is rule 2 and
    outranks every reason to want it.
    """
    if any(p.id in reserved or p.boss_eligible for p in group):
        return False
    if all(p.difficulty in GENTLE for p in group):
        return False
    families, patterns = Counter(), Counter()
    for problem in group:
        if problem.difficulty in GENTLE:
            families[problem.spaced_repetition_family] += 1
            patterns[problem.pattern] += 1
    if any(by_family[f] - n < 1 for f, n in families.items()):
        return False
    if any(by_pattern[p] - n < 1 for p, n in patterns.items()):
        return False
    return True


def coverable_patterns(problems: list) -> set:
    """Patterns the hold-out could represent without breaking a ramp.

    The honest version of "sealed content covers every skill". A pattern whose
    every lineage is somebody's last doorway cannot be measured for transfer,
    and saying so out loud is better than quietly lowering the bar to whatever
    the selection happened to achieve.
    """
    reserved = reserved_ids(problems)
    by_family, by_pattern = _gentle_ledger(problems)
    index = defaultdict(list)
    for problem in problems:
        index[problem.lineage_id].append(problem)
    out = set()
    for group in index.values():
        if _sealable(group, reserved, by_family, by_pattern):
            out.update(p.pattern for p in group)
    return out


def seal_holdout(problems: list, *, target: float = SEALED_TARGET) -> list:
    """Mark whole lineages sealed until the hold-out is the right size."""
    for problem in problems:
        problem.sealed = False

    index = defaultdict(list)
    for problem in problems:
        index[problem.lineage_id].append(problem)

    total = len(problems)
    goal = int(round(total * target))
    ceiling = int(total * SEALED_BAND[1])
    hard_cap = int(goal * SEALED_HARD_SHARE)
    reserved = reserved_ids(problems)

    # The doorway ledger: how many gentle rungs each topic still has that the
    # teaching side can reach. Sealing decrements it; it may never reach zero.
    gentle_by_family, gentle_by_pattern = _gentle_ledger(problems)
    state = {"size": 0, "hard": 0}

    def admissible(lineage_id: str) -> bool:
        group = index[lineage_id]
        if any(p.sealed for p in group):
            return False
        if state["size"] + len(group) > ceiling:
            return False
        steep = sum(1 for p in group if p.difficulty in STEEP)
        if state["hard"] + steep > hard_cap:
            return False
        return _sealable(group, reserved, gentle_by_family, gentle_by_pattern)

    def take(lineage_id: str) -> None:
        group = index[lineage_id]
        for problem in group:
            problem.sealed = True
            if problem.difficulty in GENTLE:
                gentle_by_family[problem.spaced_repetition_family] -= 1
                gentle_by_pattern[problem.pattern] -= 1
        state["size"] += len(group)
        state["hard"] += sum(1 for p in group if p.difficulty in STEEP)

    def tier(lineage_id: str) -> int:
        group = index[lineage_id]
        if any(p.difficulty in STEEP for p in group):
            return 2            # rule 4: last, and capped
        if any(p.difficulty in ("EASY", "MEDIUM") for p in group):
            return 0
        return 1

    order = sorted(index, key=lambda lid: (tier(lid), _rank(lid)))

    # Pass one, rule 3: every pattern gets a seat before anyone gets a second.
    # A lineage usually carries one pattern but is not obliged to, so what has
    # already been covered is read back off the sealed set rather than assumed.
    for pattern in sorted({p.pattern for p in problems}):
        if any(p.sealed and p.pattern == pattern for p in problems):
            continue
        for lineage_id in order:
            if any(p.pattern == pattern for p in index[lineage_id]) \
                    and admissible(lineage_id):
                take(lineage_id)
                break

    # Pass two: fill to the target in hash order, ordinary difficulties first.
    for lineage_id in order:
        if state["size"] >= goal:
            break
        if admissible(lineage_id):
            take(lineage_id)

    sever_references(problems)
    return [p for p in problems if p.sealed]


def sever_references(problems: list) -> int:
    """Cut every cross-reference from teachable content into the hold-out.

    The seal is not only about which problem the selector hands over. A problem
    record carries `prerequisites` and `variants`, both of them lists of problem
    ids, and `player_view` ships both to the browser in Adventure Mode. So an
    ordinary teaching payload for an ordinary teachable problem was naming
    sealed ids out loud — 28 of them, reaching 27 of the 97 hold-out lineages,
    better than a quarter of the measurement — and an id is all you need: it
    says the exercise exists, roughly what it is about, and what to go and read.
    A player who has been handed `oopl-mro-cooperative-easy` before ever sitting
    it has not met it cold.

    That edge was also a lie in its own right. A prerequisite pointing into the
    hold-out is a prerequisite the teaching side is forbidden to satisfy, so the
    curriculum was advertising a doorway that does not open. Cutting it repairs
    the ramp and closes the leak with the same stroke, and there is nothing to
    repoint it at: rule 1 seals whole lineages, so a sealed prerequisite has no
    teachable sibling to stand in for it.

    Done here, at build time, rather than by redacting in `player_view`: a
    redaction has to be remembered by every future field that holds an id, and
    the corpus is written once and read everywhere. Returns how many references
    were cut, and validate._corpus_checks proves the count is zero on what
    actually shipped.
    """
    sealed = {p.id for p in problems if p.sealed}
    cut = 0
    for problem in problems:
        if problem.sealed:
            continue          # a sealed problem may refer to its own kin freely
        for field_name in ("prerequisites", "variants"):
            values = getattr(problem, field_name, None)
            if not values:
                continue
            kept = [v for v in values if v not in sealed]
            if len(kept) != len(values):
                cut += len(values) - len(kept)
                setattr(problem, field_name, kept)
    return cut


# ===========================================================================
# THE CONTRACT
# ===========================================================================
#
# Everything the engine needs to ask about lineage or the hold-out, asked here
# and nowhere else. Two fields carry it — `problem.sealed` and
# `problem.lineage_id` — and these are the questions worth asking of them.
#
#   is this teachable?        not is_sealed(problem)   /   teachable(corpus)
#   what may I measure with?  sealed_pool(corpus)
#   same exercise?            a.lineage_id == b.lineage_id / siblings(...)
#   have they seen this one?  problem.lineage_id in seen_lineages(corpus, ids)
#
# Three things this contract asks of the other side.
#
#   ADVENTURE, HINTS, SRS AND COACHING SELECT FROM `teachable`. Not "filter the
#   sealed ones out at the end" — a sealed problem that reaches the selector is
#   a sealed problem one bug away from being taught.
#
#   TRANSFER READINESS COUNTS ONLY UNFAMILIAR SEALED ENCOUNTERS. Sealed, no
#   assistance, and `is_unfamiliar` true at the moment it was served. A sealed
#   problem whose lineage the player has already met is ordinary evidence: it
#   still counts for mastery, it does not count for transfer.
#
#   A LINEAGE IS ONE PIECE OF EVIDENCE. Five siblings cleared is one unfamiliar
#   problem solved five times, not five unfamiliar problems solved.
#
# `player_view()` ships neither field. A player who can read the hold-out can
# study it, and a studied hold-out measures familiarity — the one thing it
# exists not to measure. If the interface needs to mark a transfer encounter,
# the engine can say so itself; the corpus will not say it for free.
#
# Not to be confused with `finalexam.sealed(encounter, capability)`, which asks
# whether a capability is sealed off inside an encounter. That stays the only
# way to ask whether a capability is available; this is a property of content.

def is_sealed(problem: Problem) -> bool:
    """Is this problem part of the hold-out? Never teach it, never hint it,
    never schedule it for review, never show its solution."""
    return bool(problem.sealed)


def sealed_pool(corpus: list, *, pattern: str = "", difficulty: str = "") -> list:
    """The hold-out, optionally narrowed. The only legitimate source of a
    transfer measurement."""
    out = [p for p in corpus if p.sealed]
    if pattern:
        out = [p for p in out if p.pattern == pattern]
    if difficulty:
        out = [p for p in out if p.difficulty == difficulty]
    return out


def teachable(corpus: list) -> list:
    """Everything Adventure Mode, hints, coaching and SRS are allowed to use."""
    return [p for p in corpus if not p.sealed]


def lineage_of(problem: Problem) -> str:
    return problem.lineage_id


def lineage_index(corpus: list) -> dict:
    """lineage_id -> its problems, ordered by id."""
    out = defaultdict(list)
    for problem in corpus:
        out[problem.lineage_id].append(problem)
    return {k: sorted(v, key=lambda p: p.id) for k, v in sorted(out.items())}


def siblings(corpus: list, problem: Problem) -> list:
    """The same exercise in other clothes. Excellent spaced repetition; not
    independent evidence of anything."""
    return [p for p in corpus
            if p.lineage_id == problem.lineage_id and p.id != problem.id]


def seen_lineages(corpus: list, seen_problem_ids) -> set:
    """Which lineages this player has already met, from the problem ids they
    have encountered. Store ids, derive lineages — ids are what save files
    already keep, and a derived answer cannot go stale against a rebuild."""
    wanted = set(seen_problem_ids)
    return {p.lineage_id for p in corpus if p.id in wanted}


def is_unfamiliar(corpus: list, problem: Problem, seen_problem_ids) -> bool:
    """The question a transfer score is allowed to count: is this problem's
    whole lineage new to them?"""
    return problem.lineage_id not in seen_lineages(corpus, seen_problem_ids)


def transfer_pool(corpus: list, seen_problem_ids) -> list:
    """Sealed, and from a lineage this player has never met. What is left is
    what can still be asked of them exactly once."""
    seen = seen_lineages(corpus, seen_problem_ids)
    return [p for p in corpus if p.sealed and p.lineage_id not in seen]


# ===========================================================================


def write(problems: list, path: Path | None = None) -> Path:
    path = path or config.corpus_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([p.to_dict() for p in problems], indent=1))
    return path


def load(path: Path | None = None) -> list:
    path = path or config.corpus_path()
    raw = json.loads(path.read_text())
    return [Problem(**entry) for entry in raw]


def fingerprint() -> str:
    """A hash of everything that can change the corpus.

    Without this, a player who started before new content shipped would keep
    their original corpus forever: the old ensure() only checked whether the
    file existed. Content is part of the program, so it has to invalidate the
    way code does.
    """
    import hashlib
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    sources = sorted(here.glob("families/*.py")) + [
        here / "generator.py", here / "schema.py", here / "validate.py",
        # The ramp's declarations are content: they decide which span of each
        # problem the player is asked to write. `scaffold.py` is content too,
        # because it is what turns a declaration into the spans that are stored.
        here / "scaffolding.py", here.parent / "scaffold.py",
        # Lineage and the hold-out are decided in this file, so this file is
        # content too: changing how the set is chosen has to invalidate a
        # corpus that was built under the old rule.
        here / "__init__.py",
    ]
    for source in sources:
        if source.exists():
            digest.update(source.name.encode())
            digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def _stamp_path(path: Path) -> Path:
    return path.with_suffix(".stamp")


def ensure(path: Path | None = None, *, rebuild: bool = False) -> list:
    """Load the corpus, rebuilding and revalidating whenever the content that
    produces it has changed."""
    path = path or config.corpus_path()
    stamp = _stamp_path(path)
    current = fingerprint()
    stale = True
    if path.exists() and stamp.exists():
        try:
            stale = stamp.read_text().strip() != current
        except OSError:
            stale = True

    if rebuild or not path.exists() or stale:
        from .validate import validate
        problems = build_all()
        report = validate(problems)
        write(report.accepted, path)
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(current)
        return report.accepted
    return load(path)
