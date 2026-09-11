"""The learning engine's invariants."""
from base import GameTest  # noqa: E402
import time
import unittest


class TestEngine(GameTest):
    def test_clean_solve_moves_the_right_skill(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        before = g.skills["HASH_MAP"].mastery
        g.start_encounter(p.id)
        result = g.submit(p.canonical_solution)
        self.assertTrue(result["solved"])
        self.assertGreater(g.skills["HASH_MAP"].mastery, before)

    def test_viewing_content_never_raises_mastery(self):
        """Spec: never increase technical mastery merely because content was viewed."""
        g = self.game()
        p = self.by_id("sw-longest-no-repeat")
        before = g.skills["SLIDING_WINDOW"].mastery
        g.start_encounter(p.id)
        for level in (1, 2, 3, 4, 5):
            g.use_hint(level)
        self.assertEqual(g.skills["SLIDING_WINDOW"].mastery, before)

    def test_assistance_is_recorded_and_caps_the_rank(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        g.use_hint(5)                     # PHOENIX: full worked solution
        result = g.submit(p.canonical_solution)
        self.assertEqual(result["rank"], "LEARNING_CLEAR")
        self.assertTrue(result["solved"], "a Learning Clear still advances the story")

    def test_failure_never_dead_ends(self):
        g = self.game()
        p = self.by_id("sw-k-distinct")
        g.start_encounter(p.id)
        result = g.submit("def longest_k_distinct(s, k):\n    return 0\n")
        self.assertFalse(result["solved"])
        self.assertIsNotNone(result["training_camp"])
        self.assertIsNotNone(result["remediation"])
        self.assertTrue(result["remediation"]["immediate"])
        self.assertTrue(result["remediation"]["delayed"])

    def test_root_cause_is_the_first_cause_not_the_last_symptom(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        brute = ("def two_sum(nums, target):\n"
                 "    for i in range(len(nums)):\n"
                 "        for j in range(i + 1, len(nums)):\n"
                 "            if nums[i] + nums[j] == target:\n"
                 "                return [i, j]\n"
                 "    return []\n")
        result = g.submit(brute)
        self.assertFalse(result["solved"])
        self.assertEqual(result["analysis"]["root_cause"], "INEFFICIENT_ALGORITHM",
                         "correct-but-slow must be diagnosed as complexity, not logic")

    def test_syntax_error_routes_to_python_village(self):
        g = self.game()
        g.start_encounter("ah-two-sum-indices")
        result = g.submit("def two_sum(nums target):\n    pass\n")
        self.assertEqual(result["analysis"]["root_cause"], "SYNTAX")
        self.assertEqual(result["training_camp"]["region"], "python_village")

    def test_training_camp_targets_the_prerequisite_not_the_surface(self):
        """Failing sliding window with weak dictionaries should route to hash maps."""
        from gauntlet import adaptive
        g = self.game()
        skills = g.skills
        skills["HASH_MAP"].mastery = 12
        skills["HASH_MAP"].attempts = 4
        skills["PYTHON"].mastery = 80
        skills["PYTHON"].attempts = 10
        camp = adaptive.training_camp("WRONG_DATA_STRUCTURE", skills, "SLIDING_WINDOW")
        self.assertEqual(camp["skill"], "HASH_MAP")
        self.assertIn("built on top of it", camp["why"])

    def test_spaced_repetition_schedules_and_disguises(self):
        from gauntlet import srs
        g = self.game()
        p = self.by_id("sw-k-distinct")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        schedule = g.schedule
        entry = schedule[p.spaced_repetition_family]
        self.assertGreater(entry.due_at, time.time())
        self.assertIn(p.id, entry.seen_problem_ids)
        candidates = [x for x in self.corpus
                      if x.spaced_repetition_family == p.spaced_repetition_family]
        pick = srs.pick_disguised(entry, candidates)
        self.assertNotEqual(pick.id, p.id,
                            "a retest must not repeat the identical prompt")

    def test_lapses_shorten_the_interval(self):
        from gauntlet import srs
        entry = srs.ScheduleEntry(family="x", stage=3)
        srs.schedule_after(entry, solved=False, hints_used=0)
        self.assertEqual(entry.stage, 1)
        self.assertEqual(entry.lapses, 1)

    def test_armor_is_repaired_only_by_debugging(self):
        g = self.game()
        g.state["armor"]["boots"] = 20
        g.save()
        p = self.by_id("db-off-by-one-range")
        g.start_encounter(p.id)
        result = g.submit(p.canonical_solution)
        self.assertTrue(result["solved"])
        self.assertTrue(result["armor_event"]["repaired"])
        self.assertGreater(g.state["armor"]["boots"], 20)

    def test_failure_cracks_the_armor_piece_matching_the_cause(self):
        g = self.game()
        g.start_encounter("ah-two-sum-indices")
        before = g.state["armor"]["helmet"]
        g.submit("def two_sum(nums target):\n    pass\n")
        self.assertLess(g.state["armor"]["helmet"], before)

    def test_stamina_zero_triggers_teaching_rather_than_punishment(self):
        g = self.game()
        g.state["player"]["stamina"] = 1
        g.save()
        g.start_encounter("sw-k-distinct")
        result = g.submit("def longest_k_distinct(s, k):\n    return 0\n")
        self.assertTrue(result["stamina_triggered_camp"])
        self.assertGreater(result["stamina"], 0, "the player is never locked out")
        self.assertIsNotNone(result["training_camp"])

    def test_progress_persists_across_sessions(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        xp = g.state["player"]["xp"]
        mastery = g.skills["HASH_MAP"].mastery
        again = self.game()
        self.assertEqual(again.state["player"]["xp"], xp)
        self.assertAlmostEqual(again.skills["HASH_MAP"].mastery, mastery, places=4)

    def test_save_export_and_import_round_trip(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        payload = g.export()
        fresh = self.game()
        fresh.state["player"]["xp"] = 0
        fresh.save()
        fresh.import_save(payload)
        self.assertEqual(fresh.state["player"]["xp"], g.state["player"]["xp"])

    def test_world_unlocks_on_evidence_not_on_time(self):
        from gauntlet import world
        g = self.game()
        skills = g.skills
        locked = world.unlocked_regions(skills, set())
        self.assertNotIn("sliding_window_marsh", locked)
        skills["PYTHON"].mastery = 60
        skills["HASH_MAP"].mastery = 60
        skills["ARRAY"].mastery = 60
        opened = world.unlocked_regions(skills, set())
        self.assertIn("sliding_window_marsh", opened)

    def test_final_castle_needs_bosses_and_gates_not_merely_mastery(self):
        from gauntlet import world
        g = self.game()
        skills = g.skills
        for state in skills.values():
            state.mastery = 95
        self.assertNotIn("null_kings_castle", world.unlocked_regions(skills, set()))

        enough_bosses = {f"boss{i}" for i in range(world.CASTLE_BOSS_REQUIREMENT)}
        thin_gates = {"gates_passed": 3, "gates_total": 13}
        self.assertNotIn("null_kings_castle",
                         world.unlocked_regions(skills, enough_bosses, thin_gates),
                         "mastery and bosses alone must not open the castle")

        met_gates = {"gates_passed": world.CASTLE_GATE_REQUIREMENT, "gates_total": 13}
        self.assertIn("null_kings_castle",
                      world.unlocked_regions(skills, enough_bosses, met_gates))

    def test_the_interviewer_refuses_an_unready_player(self):
        g = self.game()
        result = g.start_boss("the_interviewer")
        self.assertEqual(result["error"], "not ready")
        self.assertFalse(result["requirements"]["open"])
        self.assertIn("readiness bar", result["message"])

    def test_adaptive_selection_prefers_unseen_material(self):
        g = self.game()
        first = g.next_encounter()["problem"]["id"]
        p = self.by_id(first)
        from gauntlet import puzzles
        if p.encounter_kind in puzzles.PUZZLE_KINDS:
            g.solve_puzzle(puzzles.answer_key(p))
        elif p.entry.get("kind") == "mcq":
            g.answer_mcq(p.mcq["answer"])
        else:
            g.submit(p.canonical_solution)
        second = g.next_encounter()["problem"]["id"]
        self.assertNotEqual(first, second)

    def test_retests_take_priority_over_fresh_content(self):
        from gauntlet import srs
        g = self.game()
        p = self.by_id("sw-k-distinct")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        schedule = g.schedule
        entry = schedule[p.spaced_repetition_family]
        entry.due_at = time.time() - 86400
        g._write_schedule(schedule)
        g.save()
        payload = g.next_encounter()
        self.assertTrue(payload["encounter"]["is_retest"])

    def test_readiness_is_not_an_average(self):
        from gauntlet import adaptive
        g = self.game()
        skills = g.skills
        for state in skills.values():
            state.mastery = 90
            state.attempts = 10
            state.confidence = 90
        skills["TREE"].mastery = 0        # one genuine hole
        report = adaptive.readiness(skills=skills, schedule={}, stats={})
        self.assertFalse(report["ready"])
        self.assertLess(report["overall"], 90,
                        "one unmet dimension must drag the headline number down")

    def test_combo_resets_on_failure_but_progress_does_not(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        self.assertEqual(g.state["player"]["combo"], 1)
        xp = g.state["player"]["xp"]
        g.start_encounter("sw-k-distinct")
        g.submit("def longest_k_distinct(s, k):\n    return 0\n")
        self.assertEqual(g.state["player"]["combo"], 0)
        self.assertGreaterEqual(g.state["player"]["xp"], xp)

    def test_mcq_encounters_grade_and_explain(self):
        g = self.game()
        p = next(x for x in self.corpus if x.entry.get("kind") == "mcq")
        g.start_encounter(p.id)
        result = g.answer_mcq(p.mcq["answer"])
        self.assertTrue(result["solved"])
        self.assertTrue(result["explanation"])

    def test_test_forge_requires_killing_every_mimic(self):
        g = self.game()
        p = self.by_id("tf-sum-list")
        g.start_encounter(p.id)
        weak = "def tests():\n    return [(([1, 2, 3],), 6)]\n"
        result = g.submit(weak)
        self.assertFalse(result["solved"], "a suite every mutant passes must not clear")
        g.start_encounter(p.id)
        strong = ("def tests():\n"
                  "    return [(([1, 2, 3],), 6), (([],), 0), (([-1, 1],), 0),\n"
                  "            (([5],), 5)]\n")
        result = g.submit(strong)
        self.assertTrue(result["solved"], result["feedback"]["lines"])


if __name__ == "__main__":
    unittest.main()
