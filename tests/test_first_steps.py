"""The bottom of the ramp: nothing is used before it has been taught.

This file exists because the first_steps family is 57 rungs whose entire value
is the ORDER they are in. Everything else about a problem — its tests, its
canonical solution, its hint tree — is checked by the validator and fails loudly
when it breaks. The order fails silently. Move one rung, or add a rung in the
wrong place, and every problem still validates, still builds, still ships, and
the only symptom is a beginner meeting `def` before anyone has told them what a
function is. That is exactly the failure the family was written to remove, so it
is the one that gets pinned here.

Four properties, in the order they can break:

  1. THE CHAIN IS A CHAIN. One root, one line, no cycles, no forks.
  2. NOTHING ARRIVES UNANNOUNCED. Walking the rungs in order, no rung leans on a
     Python construct that no earlier rung has shown, and no rung introduces a
     pile of new ideas at once.
  3. THE ENGINE SERVES IT IN ORDER. The order is authored in `prerequisites`,
     and a field nothing reads is a field that is not true. This drives the real
     selector.
  4. THE HOLD-OUT NEVER TAKES A FIRST RUNG, and the teaching-order gate that
     property 3 depends on can never strand anybody.
"""
from __future__ import annotations

import ast
import re

from base import GameTest


def adaptive_order_tag() -> str:
    from gauntlet import adaptive
    return adaptive.ORDER_TAG


# ---------------------------------------------------------------------------
# Reading the concepts off the code, rather than off the titles
# ---------------------------------------------------------------------------
#
# A concept is counted when it appears in the syntax tree of code the encounter
# either SHOWS the player or DEMANDS they produce. Both halves matter. Reading
# only the visible text scores an empty editor as demanding nothing, which is
# backwards — a code battle with a bare `def f(n): pass` starter is asking for
# every construct in its solution. Reading only the solution misses the traces
# and reading questions, which show code and ask for no code at all.

_BUILTINS = {"len", "str", "int", "float", "bool", "print", "range", "sorted",
             "sum", "max", "min", "abs", "enumerate", "zip", "list", "dict",
             "set", "tuple", "type", "round", "any", "all", "reversed",
             "isinstance", "repr"}


def concepts(code: str) -> set:
    """Every Python idea this snippet puts in front of the reader."""
    out: set = set()
    if not code or not code.strip():
        return out
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out                  # a fragment, not a program; counted elsewhere
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            value = node.value
            out.add("literal:str" if isinstance(value, str) else
                    "literal:bool" if isinstance(value, bool) else
                    "literal:number" if isinstance(value, (int, float)) else
                    "literal:none" if value is None else "literal:other")
        elif isinstance(node, ast.Assign):
            out.add("name-binding")
        elif isinstance(node, ast.AugAssign):
            out.add("augmented-assignment")
        elif isinstance(node, ast.BinOp):
            out.add("arithmetic/concat")
        elif isinstance(node, ast.Compare):
            out.add("comparison")
        elif isinstance(node, ast.BoolOp):
            out.add("and/or")
        elif isinstance(node, ast.If):
            out.add("if/else")
        elif isinstance(node, ast.For):
            out.add("for-loop")
        elif isinstance(node, ast.While):
            out.add("while-loop")
        elif isinstance(node, ast.List):
            out.add("list")
        elif isinstance(node, ast.Dict):
            out.add("dict")
        elif isinstance(node, ast.Set):
            out.add("set")
        elif isinstance(node, ast.Tuple):
            out.add("tuple")
        elif isinstance(node, ast.Subscript):
            out.add("slicing" if isinstance(node.slice, ast.Slice) else "indexing")
        elif isinstance(node, ast.FunctionDef):
            out.add("def")
            if node.args.args:
                out.add("parameter")
            if node.args.defaults:
                out.add("default-argument")
            if node.args.vararg or node.args.kwarg:
                out.add("*args/**kwargs")
            if node.decorator_list:
                out.add("decorator")
            if node.name.startswith("__") and node.name.endswith("__"):
                out.add("dunder-method")
        elif isinstance(node, ast.Return):
            out.add("return")
        elif isinstance(node, ast.ClassDef):
            out.add("class")
        elif isinstance(node, ast.JoinedStr):
            out.add("f-string")
        elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp)):
            out.add("comprehension")
        elif isinstance(node, ast.GeneratorExp):
            out.add("generator-expression")
        elif isinstance(node, ast.Lambda):
            out.add("lambda")
        elif isinstance(node, ast.Try):
            out.add("try/except")
        elif isinstance(node, ast.Raise):
            out.add("raise")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out.add("import")
        elif isinstance(node, ast.With):
            out.add("with")
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            out.add("yield")
        elif isinstance(node, ast.Attribute):
            out.add("dot-call/attribute")
        elif isinstance(node, ast.Name) and node.id == "self":
            out.add("self")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            out.add("call:%s" % node.func.id if node.func.id in _BUILTINS
                    else "call:function")
    return out


def shown_and_demanded(problem) -> set:
    """Concepts this encounter shows the player, plus the ones it asks them for."""
    used: set = set()
    for match in re.finditer(r"```(?:python)?\n(.*?)```",
                             problem.problem_statement, re.S):
        used |= concepts(match.group(1))
    if problem.starter_code:
        used |= concepts(problem.starter_code)
    spec = problem.mcq or {}
    for key in ("code", "reference_code", "flawed_code"):
        if isinstance(spec.get(key), str):
            used |= concepts(spec[key])
    if problem.canonical_solution:
        used |= concepts(problem.canonical_solution)
    return used


class FirstStepsTest(GameTest):
    """The family in its authored order, read straight from the module.

    Read from `first_steps.build()` rather than filtered out of the corpus by id
    prefix: the authored ORDER is the thing under test, and the corpus is a set
    with no order in it. A test that recovered the order by sorting ids would be
    asserting against its own guess.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from gauntlet.corpus.families import first_steps
        cls.rungs = first_steps.build()
        cls.position = {p.id: i for i, p in enumerate(cls.rungs)}


class TestTheChainIsAChain(FirstStepsTest):

    def test_there_is_exactly_one_first_rung(self):
        roots = [p.id for p in self.rungs if not p.prerequisites]
        self.assertEqual(roots, ["fs-see-a-value"],
                         "the bottom of the ramp must have exactly one bottom; "
                         f"found {len(roots)} rungs with no prerequisite")

    def test_every_other_rung_follows_the_one_before_it(self):
        for previous, current in zip(self.rungs, self.rungs[1:]):
            self.assertEqual(current.prerequisites, [previous.id],
                             f"{current.id} should follow {previous.id}; the "
                             "chain is what makes the order survive leaving "
                             "the family file")

    def test_no_rung_depends_on_one_that_comes_later(self):
        for problem in self.rungs:
            for pre in problem.prerequisites:
                self.assertIn(pre, self.position, f"{problem.id} names {pre}, "
                                                  "which is not in this family")
                self.assertLess(self.position[pre], self.position[problem.id],
                                f"{problem.id} depends on {pre}, which the "
                                "player has not reached yet")

    def test_the_whole_family_is_gentle(self):
        """A rung above TUTORIAL is not a rung. It is also what keeps the
        hold-out off this family — see TestTheHoldOutKeepsAway."""
        for problem in self.rungs:
            self.assertIn(problem.difficulty, ("GUIDED", "TUTORIAL"),
                          f"{problem.id} is {problem.difficulty}")


class TestNothingArrivesUnannounced(FirstStepsTest):
    """The property this file is named for."""

    def _ledger(self):
        """Walk the rungs in order, returning [(problem, newly introduced)]."""
        taught: set = set()
        out = []
        for problem in self.rungs:
            used = shown_and_demanded(problem)
            out.append((problem, sorted(used - taught)))
            taught |= used
        return out

    def test_no_rung_introduces_more_than_a_handful_of_ideas(self):
        """Authoring rule 3: one new idea per problem.

        Measured rather than aspirational, and set at the family's real worst
        case rather than at a comfortable round number. Today that worst case is
        three, at `fs-return-vs-print` — the rung that introduces `def`, and
        which needs the function, the call and the `return` in one breath
        because the whole point of it is the difference between returning and
        printing. Every other rung averages 0.37. A bar of three can only ever
        be tightened; a rung that arrives carrying eight new ideas is the "five
        concepts presented as scenery" failure coming back one file further
        down, which is the entire reason this family exists.
        """
        for problem, new in self._ledger():
            self.assertLessEqual(
                len(new), 3,
                f"{problem.id} introduces {len(new)} new ideas at once "
                f"({', '.join(new)}). That is a step, not a rung.")

    def test_the_function_concepts_arrive_in_the_only_order_that_works(self):
        """`def`, then a parameter, then `return` — never the reverse, and never
        all three as scenery around the thing the player is actually asked for.
        This is the complaint the whole family was written to answer."""
        ledger = self._ledger()
        first = {}
        for index, (problem, new) in enumerate(ledger):
            for concept in new:
                first.setdefault(concept, (index, problem.id))
        for concept in ("def", "parameter", "return"):
            self.assertIn(concept, first,
                          f"nothing in the family ever introduces {concept}")
        self.assertLessEqual(first["def"][0], first["parameter"][0],
                             "a parameter appears before `def` does")
        self.assertLessEqual(first["def"][0], first["return"][0],
                             "`return` appears before `def` does")

    def test_no_function_appears_until_the_family_says_so(self):
        """Authoring rule 1: the first rungs contain no function at all — not in
        the statement, not in the code, not in the starter. A beginner meeting
        `def` as scenery is the exact thing this family exists to stop."""
        ledger = self._ledger()
        introduces_def = next(i for i, (_p, new) in enumerate(ledger)
                              if "def" in new)
        self.assertGreaterEqual(
            introduces_def, 22,
            "the family promises its first twenty-two rungs contain no function "
            f"at all; `def` turns up at rung {introduces_def + 1} "
            f"({ledger[introduces_def][0].id})")
        for problem, _new in ledger[:introduces_def]:
            haystack = " ".join([problem.problem_statement,
                                 problem.starter_code or "",
                                 problem.canonical_solution or "",
                                 str(problem.mcq or {})])
            self.assertNotRegex(
                haystack, r"\bdef\b",
                f"{problem.id} comes before functions are taught but says `def`")


class TestTheEngineServesItInOrder(FirstStepsTest):
    """`prerequisites` was authored, validated, shipped — and read by nothing.

    The selector scored the 57 rungs as 57 interchangeable GUIDED problems and
    handed them over in build order, which is to say in no order at all. These
    drive the real engine rather than the curriculum module, because "the
    curriculum knows about teaching order" and "the game serves it" are
    different claims and only the second one is the product.
    """

    def _walk(self, game, count):
        from gauntlet import puzzles
        by_id = {p.id: p for p in self.corpus}
        served = []
        for _ in range(count):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            served.append(problem)
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            else:
                game.submit(problem.canonical_solution)
        return served

    def test_a_brand_new_player_starts_at_the_bottom_of_the_ramp(self):
        """Before the ramp was wired up, encounter one of a fresh save was
        `oopl-repr-guided` — filling a blank inside a `__repr__`, for somebody
        who had never seen a function. It scored highest in the whole corpus."""
        game = self.game()
        first = self._walk(game, 1)[0]
        self.assertEqual(first.id, "fs-see-a-value",
                         f"a fresh player's first encounter is {first.id} "
                         f"({first.title}); it must be the root of the ramp")

    def test_no_first_steps_rung_is_ever_served_early(self):
        """The load-bearing one. Forty encounters of the real selector, and
        every first_steps rung that comes up must have had its prerequisite
        cleared first."""
        game = self.game()
        solved: set = set()
        for problem in self._walk(game, 40):
            if problem.id.startswith("fs-"):
                for pre in problem.prerequisites:
                    self.assertIn(
                        pre, solved,
                        f"{problem.id} was served before {pre}, which it is "
                        "written to assume")
            solved.add(problem.id)


class TestTheHoldOutKeepsAway(FirstStepsTest):
    """Sealing must never take a beginner's first rung."""

    def test_no_first_steps_rung_is_sealed(self):
        sealed = [p.id for p in self.corpus
                  if p.id.startswith("fs-") and p.sealed]
        self.assertEqual(sealed, [],
                         "the hold-out has taken rungs out of the bottom of the "
                         "ramp; a measurement is not worth a wall")

    def test_sealing_skips_the_family_by_rule_and_not_by_luck(self):
        """`_sealable` refuses a lineage that is nothing but entry rungs. Every
        first_steps rung is GUIDED or TUTORIAL and sits in its own lineage, so
        the refusal is structural. Pinned because an outcome that happens to
        hold is not the same as one that cannot fail."""
        from gauntlet.corpus import _sealable, _gentle_ledger, reserved_ids
        groups: dict = {}
        for problem in self.corpus:
            groups.setdefault(problem.lineage_id, []).append(problem)
        reserved = reserved_ids(self.corpus)
        by_family, by_pattern = _gentle_ledger(self.corpus)
        for problem in self.corpus:
            if not problem.id.startswith("fs-"):
                continue
            group = groups[problem.lineage_id]
            self.assertFalse(
                _sealable(group, reserved, by_family, by_pattern),
                f"{problem.id}'s lineage is sealable; the ramp is one hash "
                "away from losing it")


class TestTheTeachingOrderGateStrandsNobody(FirstStepsTest):
    """The gate that makes the order real must not be able to wall anyone in.

    `prerequisites` is authored in two directions in this corpus. first_steps
    chains rungs so nothing is used before it is met; onboarding and
    oop_language point the other way, naming the full-dress version of an idea
    (`oopl-len-guided` cites a MEDIUM problem). Honouring the second kind as an
    order deadlocks 52 gentle problems behind tiers they cannot unlock. The
    selector therefore honours an edge only when it points at something no
    harder — and this proves, on the real corpus, that following only those
    edges leaves nothing unreachable.
    """

    def test_every_problem_is_reachable_under_the_gate(self):
        from gauntlet import adaptive
        by_id = {p.id: p for p in self.corpus}
        solved: set = set()
        progressed = True
        while progressed:
            progressed = False
            for problem in self.corpus:
                if problem.id in solved:
                    continue
                if adaptive.unlocked_by_order(problem, by_id, solved):
                    solved.add(problem.id)
                    progressed = True
        stranded = sorted(p.id for p in self.corpus if p.id not in solved)
        self.assertEqual(stranded, [],
                         "the teaching-order gate has walled these in")

    def test_an_edge_that_points_up_the_ladder_is_not_an_order(self):
        """The rule itself, stated once so it cannot drift into a heuristic
        about which family authored what."""
        from gauntlet import adaptive, curriculum
        by_id = {p.id: p for p in self.corpus}
        for problem in self.corpus:
            for pre in adaptive.gating_prerequisites(problem, by_id):
                self.assertLessEqual(
                    curriculum.tier_index(by_id[pre].difficulty),
                    curriculum.tier_index(problem.difficulty),
                    f"{problem.id} is gated behind {pre}, which is harder")

    def test_only_declared_chains_are_gated(self):
        """The gate reads a declaration, not a guess.

        `prerequisites` means three different things across this corpus — a
        precondition here, a suggested `after=` in parsons and reasoning, a
        pointer at the full-dress version in oop_language — so the selector
        enforces it only where the content says it is a precondition. This
        pins the blast radius: if some future change starts gating families
        that merely suggested an order, sixty encounters collapse into a run
        of code battles, and that is a slow thing to notice by hand.
        """
        from gauntlet import adaptive
        by_id = {p.id: p for p in self.corpus}
        gated = {p.id for p in self.corpus
                 if adaptive.gating_prerequisites(p, by_id)}
        stray = sorted(pid for pid in gated if not pid.startswith("fs-"))
        self.assertEqual(stray, [],
                         "these are gated but never declared a strict order")
        self.assertEqual(len(gated), len(self.rungs) - 1,
                         "every first_steps rung but the root should be gated")

    def test_the_declaration_travels_with_the_problem(self):
        """The tag is on the record, so it survives the corpus being written to
        disk and read back — which is how the engine actually gets it."""
        tagged = [p for p in self.corpus if adaptive_order_tag() in p.tags]
        self.assertEqual(sorted(p.id for p in tagged),
                         sorted(p.id for p in self.rungs))

    def test_the_first_steps_chain_survives_the_rule(self):
        """All 57 edges are real orders, or the gate is decorative."""
        from gauntlet import adaptive
        by_id = {p.id: p for p in self.corpus}
        for problem in self.rungs:
            self.assertEqual(
                adaptive.gating_prerequisites(by_id[problem.id], by_id),
                list(problem.prerequisites),
                f"{problem.id} lost its teaching order to the gate rule")
