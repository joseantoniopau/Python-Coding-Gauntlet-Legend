"""A BFS discovery-marking omission must fail real hidden coverage."""
from __future__ import annotations

import unittest
import sys

from gauntlet import sandbox, scaffold
from gauntlet.corpus import RESERVED, scaffolding
from gauntlet.corpus.families import scaffolds, first_steps
from gauntlet.corpus.validate import _kills, _verify_scaffold


class GridBfsCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        problems = scaffolds.build()
        scaffolding.apply(problems)
        matches = [p for p in problems if p.entry.get("name") == "shortest_path"
                   and p.pattern == "BFS"]
        assert len(matches) == 1
        cls.problem = matches[0]
        cls.mark = next(s for s in scaffold.spans_of(cls.problem)
                        if s["text"] == "visited.add((nr, nc))")

    def test_hidden_cyclic_component_preserves_correct_shortest_path_contract(self):
        case = next(t for t in self.problem.hidden_tests
                    if t["name"] == "unreachable exit beyond a cycle")
        self.assertEqual(case["expected"], -1)
        self.assertEqual(case["args"][0][0][0], 0)
        self.assertEqual(case["args"][0][-1][-1], 0)
        # Canonical still faces every original visible, hidden and boundary case.
        report = sandbox.run_tests(self.problem.canonical_solution,
                                   self.problem.entry, self.problem.all_tests)
        self.assertTrue(report.all_passed, report.to_dict())
        self.assertEqual(len(report.tests), 7)

    def test_both_formerly_surviving_mark_omissions_fail_the_hidden_case(self):
        case = next(t for t in self.problem.hidden_tests
                    if t["name"] == "unreachable exit beyond a cycle")
        for replacement in ("visited.discard((nr, nc))", "(nr, nc)"):
            with self.subTest(replacement=replacement):
                source = scaffold.substitute(self.problem, self.mark, replacement)
                report = sandbox.run_tests(source, self.problem.entry, [case],
                                           timeout_ms=150, wall_seconds=3)
                self.assertNotEqual(report.phase, "syntax", report.to_dict())
                self.assertTrue(report.ok, report.to_dict())
                self.assertFalse(report.all_passed, report.to_dict())
                self.assertEqual(report.tests[0].status, "timeout", report.to_dict())

    def test_every_served_scaffold_span_is_observable_without_relaxing_validation(self):
        self.assertTrue(_kills(self.problem, self.mark))
        self.assertEqual([i for i in _verify_scaffold(self.problem)
                          if i.severity == "error"], [])

    def test_named_banner_regression_is_explicitly_reserved(self):
        self.assertIn("fs-write-banner", RESERVED)

    def test_banner_space_accounts_for_the_allocated_edge_before_the_result(self):
        problem = next(p for p in first_steps.build() if p.entry.get("name") == "banner")
        namespace = {}
        exec(problem.canonical_solution, namespace)
        banner = namespace["banner"]
        allocations = []
        def observe(frame, event, arg):
            if frame.f_code is banner.__code__ and event == "return":
                edge = frame.f_locals["edge"]
                allocations.append((len(edge), sys.getsizeof(edge)))
            return observe
        previous = sys.gettrace()
        try:
            sys.settrace(observe)
            for length in (16, 8192):
                banner("x" * length)
        finally:
            sys.settrace(previous)
        self.assertEqual([length for length, _ in allocations], [16, 8192])
        self.assertGreater(allocations[1][1], allocations[0][1] + 8000)
        self.assertEqual(problem.optimal_complexity["space"], "O(n)")
