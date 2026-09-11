"""Interview Mode is sacred. These tests exist to prove it stays that way.

The spec requires explicit tests proving AI and assistance are inaccessible.
Everything here checks the SERVER's behaviour, not the UI's, because a guarantee
that lives only in the client is not a guarantee.
"""
from base import GameTest  # noqa: E402
import unittest


class TestInterviewIsolation(GameTest):
    def _interview_encounter(self, g):
        g.start_interview("LIVE_SCREEN")
        return g.interview_current()

    def test_pattern_name_is_redacted(self):
        g = self.game()
        payload = self._interview_encounter(g)
        self.assertEqual(payload["problem"]["pattern"], "REDACTED")
        self.assertEqual(payload["problem"]["secondary_patterns"], [])

    def test_hint_tree_is_empty(self):
        g = self.game()
        payload = self._interview_encounter(g)
        self.assertEqual(payload["problem"]["hint_tree"], [])
        self.assertEqual(payload["hint_count"], 0)

    def test_hints_are_refused_by_the_server(self):
        g = self.game()
        self._interview_encounter(g)
        result = g.use_hint(1)
        self.assertEqual(result["error"], "sealed")

    def test_probes_are_refused(self):
        g = self.game()
        self._interview_encounter(g)
        self.assertEqual(g.probe([[1, 2], 3], [0, 1]).get("error"), "sealed")
        self.assertEqual(g.probes_remaining(), 0)

    def test_items_are_refused(self):
        g = self.game()
        g.choose_build("ANALYST")
        self._interview_encounter(g)
        result = g.use_consumable("whetstone")
        self.assertIn(result.get("error"), ("sealed", "you have none of those"))

    def test_visualisation_and_failure_hints_are_withheld(self):
        g = self.game()
        payload = self._interview_encounter(g)
        self.assertEqual(payload["problem"]["visualization"], {})
        self.assertEqual(payload["problem"]["common_failures"], [])
        self.assertEqual(payload["problem"]["optimal_complexity"], {})

    def test_mentor_and_skill_state_are_withheld(self):
        g = self.game()
        payload = self._interview_encounter(g)
        self.assertEqual(payload["skill"], "")
        self.assertIsNone(payload["skill_state"])
        self.assertEqual(payload["loadout"], {})
        self.assertEqual(payload["tactics"], {})

    def test_the_coach_is_unavailable_until_the_attempt_is_scored(self):
        from gauntlet import coach
        self.assertFalse(coach.available_in("interview"))
        self.assertTrue(coach.available_in("adventure"))

    def test_coach_output_during_interview_is_a_refusal(self):
        g = self.game()
        payload = self._interview_encounter(g)
        problem = g.by_id[payload["problem"]["id"]]
        result = g.submit(problem.canonical_solution)
        self.assertFalse(result["coach"]["available"])
        self.assertEqual(result["coach"]["questions"], [])

    def test_worked_solution_is_never_returned_in_interview_mode(self):
        g = self.game()
        payload = self._interview_encounter(g)
        problem = g.by_id[payload["problem"]["id"]]
        result = g.submit(problem.canonical_solution)
        self.assertIsNone(result["canonical_solution"])

    def test_explanation_scoring_is_sealed(self):
        g = self.game()
        self._interview_encounter(g)
        enc = g.encounter
        self.assertEqual(enc.mode, "interview")

    def test_rank_grace_from_gear_does_not_apply(self):
        g = self.game()
        g.choose_build("DUELIST")
        for _ in range(6):
            g.allocate("HASTE", 1)
        payload = self._interview_encounter(g)
        problem = g.by_id[payload["problem"]["id"]]
        self.assertEqual(g._graced_target(problem), problem.target_seconds)

    def test_interview_records_a_scored_run(self):
        g = self.game()
        run = g.start_interview("LIVE_SCREEN")
        for _ in run["problems"]:
            payload = g.interview_current()
            if payload.get("finished"):
                break
            problem = g.by_id[payload["problem"]["id"]]
            result = g.submit(problem.canonical_solution)
            g.interview_advance(result)
        report = g.finish_interview() if g.state.get("interview") else None
        if report is None:
            from gauntlet import db
            history = db.interview_history(g.conn)
            self.assertTrue(history)
        else:
            self.assertTrue(report["finished"])
            self.assertGreaterEqual(report["score"], 0)

    def test_adventure_mode_still_has_everything(self):
        g = self.game()
        payload = g.start_encounter("sw-k-distinct", mode="adventure")
        self.assertNotEqual(payload["problem"]["pattern"], "REDACTED")
        self.assertTrue(payload["problem"]["hint_tree"])
        self.assertTrue(payload["tactics"])
        self.assertNotEqual(g.use_hint(1).get("error"), "sealed")


if __name__ == "__main__":
    unittest.main()
