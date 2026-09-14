"""Honest explanation coverage, support-aware coaching and real boss variants."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

from gauntlet import coach, communication, rematches, sandbox, world
from gauntlet.corpus import build_all
from gauntlet.corpus.families.rematch_variants import build as build_variants
from gauntlet.corpus.validate import _run_canonical


class CommunicationAndRematches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_id = {p.id: p for p in build_all()}
        # Allows this owned slice to run before root registers its family module.
        for p in build_variants():
            cls.by_id.setdefault(p.id, p)

    def test_keyword_bluff_does_not_pass(self):
        p = SimpleNamespace(id="hash", pattern="HASH_MAP", spaced_repetition_family="counting",
                            optimal_complexity={"time": "O(n)", "space": "O(n)"}, constraints=[],
                            problem_statement="Count every value in the input.")
        result = coach.explanation_score("map because good O(1)", p)
        self.assertLess(result["score"], 100)
        self.assertEqual(result["semantic_status"], "unverified")
        self.assertTrue(result["self_check_required"])
        self.assertNotIn("strong answer", result["verdict"])

    def test_explicit_wrong_cost_is_identified_separately(self):
        p = self.by_id["sw-longest-no-repeat"]
        result = communication.checklist("Time: O(1)\nSpace: O(1)", p)
        time = next(c for c in result["checks"] if c["id"] == "time")
        self.assertFalse(time["passed"])
        self.assertEqual(time["status"], "differs_from_reference")
        self.assertEqual(time["expected"], "O(n)")
        self.assertEqual(time["evidence"], "O(1)")

    def test_language_explanation_needs_no_data_structure_jargon(self):
        result = communication.checklist(
            "Approach: I convert count with str, prefix it with 'count: ', and return the resulting text.\n"
            "Value claim: The returned value is a string with the prefix and the supplied number's text.\n"
            "Edge case: For zero the returned text is the string 'count: 0'.\n"
            "Time: O(1)\nSpace: O(1)", self.by_id["ob-number-to-text"])
        self.assertEqual(result["score"], 100, result)
        self.assertEqual(result["score_kind"], "topic_coverage")
        self.assertEqual(result["semantic_status"], "unverified")
        self.assertNotIn("dictionary", result["prompts"]["approach"])
        self.assertIn("returned value", result["checks"][1]["evidence"].lower())

    def test_nested_costs_and_both_dimensions_are_distinct(self):
        p = self.by_id["sw-min-window"]
        result = communication.checklist("O(len(s) + len(t)) time and O(len(t)) space.", p)
        self.assertTrue(all(c["passed"] for c in result["checks"] if c["id"] in {"time", "space"}))
        no_space = communication.checklist("Time: O(len(s) + len(t))", p)
        self.assertFalse(next(c for c in no_space["checks"] if c["id"] == "space")["passed"])

    def test_conflicting_time_claims_are_not_accepted(self):
        p = self.by_id["sw-longest-no-repeat"]
        result = communication.checklist("O(n) time. O(1) time. O(n) space.", p)
        self.assertFalse(next(c for c in result["checks"] if c["id"] == "time")["passed"])

    def _reply(self, **kwargs):
        return coach.coach(mode="adventure", analysis=SimpleNamespace(root_cause=None),
                           problem=self.by_id["sw-longest-no-repeat"],
                           report=SimpleNamespace(tests=[]), hints_used=0, seconds=20,
                           history=[], attempts_on_problem=1, **kwargs)

    def test_scaffold_clears_never_claim_independence(self):
        for rung in (1, 2, 3):
            text = self._reply(served_rung=rung, evidence_kind="whole_function").analysis
            self.assertIn("scaffold support", text)
            self.assertNotIn("entirely unaided", text)
            self.assertNotIn("with whole-function", text)

    def test_reading_puzzle_and_unknown_support_are_distinct(self):
        for kind in ("reading", "puzzle", "debugging", "test_writing", "repository"):
            text = self._reply(served_rung=4, evidence_kind=kind).analysis
            self.assertIn(kind, text)
            self.assertIn("not whole-function", text)
        unknown = self._reply().analysis
        self.assertIn("independence is unverified", unknown)
        self.assertNotIn("entirely unaided", unknown)
        known = self._reply(served_rung=4, evidence_kind="whole_function").analysis
        self.assertIn("whole-function coding practice", known)
        self.assertIn("no recorded spells", known)

    def test_interview_coach_stays_sealed(self):
        r = coach.coach(mode="interview", analysis=None, problem=None, report=None,
                        hints_used=0, seconds=0, history=[], attempts_on_problem=0,
                        served_rung=4, evidence_kind="whole_function")
        self.assertFalse(r.available)

    def test_every_boss_has_eligible_changed_contracts(self):
        self.assertEqual(rematches.validate_manifest(self.by_id), [])
        self.assertEqual(set(rematches.MANIFEST), {b["id"] for b in world.BOSSES})
        for boss in world.BOSSES:
            entries = rematches.MANIFEST[boss["id"]]
            self.assertEqual(rematches.get_rematch(boss, 0, self.by_id)["problem_id"], boss["problem_id"])
            for n, entry in enumerate(entries, 1):
                r = rematches.get_rematch(boss, n, self.by_id)
                self.assertEqual(r["problem_id"], entry.problem_id)
                self.assertTrue(r["constraint_changed"])
                self.assertFalse(r["transfer_evidence"])
            exhausted = rematches.get_rematch(boss, len(entries) + 1, self.by_id)
            self.assertEqual(exhausted["kind"], "repeat_practice")
            self.assertFalse(exhausted["constraint_changed"])
            self.assertTrue(exhausted["exhausted"])

    def test_invalid_and_sealed_variant_fails_closed_to_repeat(self):
        by = self.by_id.copy()
        p = copy.copy(by["rm-anagram-index-pairs"])
        p.sealed = True
        by[p.id] = p
        result = rematches.get_rematch("hash_titan", 1, by)
        self.assertEqual(result["kind"], "repeat_practice")
        self.assertEqual(result["problem_id"], "ah-group-anagrams")
        self.assertFalse(result["constraint_changed"])
        del by[p.id]
        self.assertEqual(rematches.get_rematch("hash_titan", 1, by)["problem_id"], "ah-group-anagrams")

    def test_every_selected_canonical_passes_real_sandbox_tests(self):
        for problem_id in sorted({v.problem_id for rows in rematches.MANIFEST.values() for v in rows}):
            with self.subTest(problem_id=problem_id):
                self.assertIsNone(_run_canonical(self.by_id[problem_id]))

    def test_new_contracts_have_concrete_visible_hidden_and_boundary_trials(self):
        for p in build_variants():
            self.assertTrue(p.visible_tests and p.hidden_tests and p.edge_cases, p.id)
            self.assertIn("practice:constraint-change", p.tags)
            self.assertTrue(any(t.startswith("rematch-of:") for t in p.tags))
        pairs = self.by_id["rm-anagram-index-pairs"]
        self.assertEqual(pairs.visible_tests[0]["expected"], 3)
        tree = self.by_id["rm-bst-subtree-report"]
        self.assertEqual(tree.visible_tests[1]["expected"], {"is_bst": True, "height": 3, "balanced": False})
        graph = self.by_id["rm-shortest-node-path"]
        self.assertEqual(graph.visible_tests[1]["expected"], ["a", "c", "d"])
        stream = self.by_id["rm-streaming-window-max"]
        self.assertEqual(stream.visible_tests[1]["expected"], [None, None, 9, None, None, 2])
        wildcard = self.by_id["rm-wildcard-window-cover"]
        self.assertEqual(wildcard.visible_tests[0]["expected"], "ca")
        self.assertEqual(wildcard.hidden_tests[0]["expected"], "")

    def test_tests_reject_ignoring_each_new_contract(self):
        mutants = {
            "rm-anagram-index-pairs": "def count_anagram_pairs(words):\n    return len({tuple(sorted(w)) for w in words})\n",
            "rm-bst-subtree-report": "def bst_report(root):\n    return True\n",
            "rm-shortest-node-path": "def shortest_node_path(graph, start, end):\n    return 1\n",
            "rm-streaming-window-max": "class RollingMaximum:\n    def __init__(self,k):\n        self.values=[]\n    def push(self,value):\n        self.values.append(value)\n        return max(self.values)\n    def reset(self):\n        pass\n",
            "rm-wildcard-window-cover": "def wildcard_window(s,target):\n    return s if '?' in s else ''\n",
        }
        for problem_id, source in mutants.items():
            p = self.by_id[problem_id]
            with self.subTest(problem_id=problem_id):
                report = sandbox.run_tests(source, p.entry, p.visible_tests + p.hidden_tests + p.edge_cases)
                self.assertTrue(report.ok, report.error)
                self.assertTrue(any(not t.passed for t in report.tests), problem_id)


if __name__ == "__main__":
    unittest.main()
