"""The twenty acceptance criteria from section 80 of the build request.

Each test is named for the criterion it proves. If this file passes, the product
meets the bar it was specified against.
"""
from base import GameTest  # noqa: E402
import time
import unittest


class TestAcceptance(GameTest):

    def test_01_launches_locally(self):
        import json
        import urllib.request
        from gauntlet import server
        httpd, url = server.serve()
        try:
            port = httpd.server_address[1]
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/ping",
                headers={"X-Gauntlet-Token": server.TOKEN})
            payload = json.loads(urllib.request.urlopen(req, timeout=20).read())
            self.assertTrue(payload["ok"])
            page = urllib.request.urlopen(f"http://127.0.0.1:{port}/",
                                          timeout=10).read().decode()
            self.assertIn("GAUNTLET LEGEND", page)
        finally:
            httpd.shutdown()

    def test_02_progress_persists(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        self.assertEqual(self.game().state["player"]["xp"], g.state["player"]["xp"])

    def test_03_python_executes_safely(self):
        from gauntlet import sandbox
        check = sandbox.self_check()
        self.assertTrue(check["network_blocked"])
        self.assertTrue(check["timeout_enforced"])

    def test_04_problems_can_be_solved(self):
        """Take the first twelve problems that are actually code and solve them.

        This used to filter `corpus[:12]` down to the code problems in it, which
        made the assertion depend on the order `corpus._FAMILIES` happens to
        build in — a positional slice standing in for "some code problems".
        When the first_steps family was added at the front of that tuple, the
        first twelve problems in the corpus became twelve reading questions and
        multiple-choice traces, the filter skipped every one of them, and a test
        about whether code problems can be solved failed without a single code
        problem having been tried.

        Collecting twelve code problems instead of hoping twelve happen to be
        first is strictly more work for the test, not less: it now always
        submits twelve canonical solutions rather than however many the slice
        happened to contain.
        """
        g = self.game()
        code_problems = [p for p in self.corpus
                         if p.entry.get("kind") in ("function", "class_ops")][:12]
        self.assertEqual(len(code_problems), 12)
        cleared = 0
        for p in code_problems:
            g.start_encounter(p.id)
            if g.submit(p.canonical_solution)["solved"]:
                cleared += 1
        self.assertGreaterEqual(cleared, 5)

    def test_05_tests_evaluate_correctly(self):
        g = self.game()
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        self.assertTrue(g.submit(p.canonical_solution)["solved"])
        g.start_encounter(p.id)
        self.assertFalse(g.submit("def two_sum(n, t):\n    return []\n")["solved"])

    def test_06_adventure_mode_teaches_after_failure(self):
        g = self.game()
        g.start_encounter("sw-k-distinct")
        result = g.submit("def longest_k_distinct(s, k):\n    return 0\n")
        self.assertTrue(result["coach"]["available"])
        self.assertTrue(result["coach"]["questions"])
        self.assertTrue(result["analysis"]["narrative"])

    def test_07_player_never_permanently_dead_ends(self):
        g = self.game()
        p = self.by_id("sw-min-window")
        for _ in range(4):
            g.start_encounter(p.id)
            result = g.submit("def min_window(s, t):\n    return ''\n")
            self.assertIsNotNone(result["remediation"])
        g.start_encounter(p.id)
        phoenix = g.use_hint(5)
        self.assertIn("def min_window", phoenix["body"])
        result = g.submit(p.canonical_solution)
        self.assertTrue(result["solved"])

    def test_08_debugging_repairs_armor(self):
        g = self.game()
        g.state["armor"]["gauntlets"] = 10
        g.save()
        p = self.by_id("db-keyerror")
        g.start_encounter(p.id)
        result = g.submit(p.canonical_solution)
        self.assertTrue(result["armor_event"]["repaired"])
        self.assertGreater(g.state["armor"]["gauntlets"], 10)

    def test_09_spaced_repetition_schedules_correctly(self):
        """A REVIEW MEASURES RETENTION, so what enrols a family is a serving the
        player wrote whole.

        This used to clear one EASY problem on a fresh save and assert stage 1.
        A fresh save is served EASY at its floor — rung 3, two blanks — and
        counting that as the family's first review is the measurement error the
        whole ramp exists to avoid: measured, four such clears reached stage 4,
        ease 1.40 and a next sighting 42 days out, bought with fill-in-the-
        blanks. So the test asks the question in two halves, which is what
        `srs.counts_as_review` now answers.
        """
        from gauntlet import scaffold, skills as skillmod
        from gauntlet.config import SRS_INTERVALS_DAYS
        g = self.game()
        p = self.by_id("ah-two-sum-indices")

        g.start_encounter(p.id)
        self.assertLess(g.encounter.rung, scaffold.WRITE_IT_ALL,
                        "a fresh save was served this whole; the half below is "
                        "then the only half being tested")
        g.submit(p.canonical_solution)
        self.assertNotIn(p.spaced_repetition_family,
                         [f for f, e in g.schedule.items() if e.due_at],
                         "a two-blank serving scheduled the family's next "
                         "sighting")

        # Now the same problem, written whole. `rung_for` is capped by mastery,
        # so the evidence has to be real on both axes.
        skill = skillmod.PATTERN_TO_SKILL.get(p.pattern, "PYTHON")
        skills = g.skills
        skills[skill].rung_unaided = {"3": 99, "4": 99}
        skills[skill].mastery = 80.0
        g._write_skills(skills)
        g.save()
        g.start_encounter(p.id)
        self.assertEqual(g.encounter.rung, scaffold.WRITE_IT_ALL)
        result = g.submit(p.canonical_solution)
        self.assertGreaterEqual(result["next_retest_days"],
                                SRS_INTERVALS_DAYS[0] * 0.6)
        entry = g.schedule[p.spaced_repetition_family]
        self.assertEqual(entry.stage, 1)

    def test_10_bosses_test_genuine_mastery(self):
        """A boss is a LADDER, and every rung is a graded solve.

        This test used to assert the opposite — one solved problem and the
        boss was down — and that was the defect, not the specification. A
        region boss now carries four to six phases, each with its own health
        pool and its own problem, and the ONLY thing that empties a phase is a
        submission that ran. The teaching phase is unchanged and still fires on
        the first failure, because a boss must never become a wall.
        """
        from gauntlet import world, bestiary
        g = self.game()
        boss = world.BOSS_BY_ID["window_wraith"]
        # A boss is fought where it lives. `Game.start_boss` refuses one the
        # player is not standing in front of, so the walk is part of the test.
        self.stand_where(g, boss["id"])
        payload = g.start_boss(boss["id"])
        self.assertEqual(len(payload["boss"]["phases"]), 6)
        fight = payload["boss"]["fight"]
        self.assertGreaterEqual(fight["phases"], 4)
        self.assertEqual(fight["phase"], 0, "a boss opens whole")
        self.assertTrue(payload["boss"]["key"], "every boss is holding a key")

        result = g.submit("def length_of_longest_substring(s):\n    return 0\n")
        self.assertFalse(result["solved"])
        self.assertTrue(result["boss"]["teaching_phase"],
                        "a boss must never become a wall")
        self.assertFalse(result["boss"]["defeated"])

        # Walk the whole ladder. Each phase serves its own problem, and the
        # phase turn arrives with the buffs that make the next one harder.
        # A phase draws the KIND of problem bestiary.phase_kind names for it —
        # name the family, state the approach, write it, survive the edges, name
        # its cost — so a boss ladder runs through every entry kind the corpus
        # has, not just the code editor. Answering each one the way the client
        # does is the point of this dispatch rather than an inconvenience.
        from gauntlet import puzzles

        def answer(problem):
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                return g.solve_puzzle(puzzles.answer_key(problem))
            if problem.entry.get("kind") == "mcq":
                return g.answer_mcq(problem.mcq.get("answer"))
            return g.submit(problem.canonical_solution)

        turns = 0
        for _ in range(fight["phases"] + 2):
            if g.encounter is None:
                g.start_boss(boss["id"])
            enc = g.encounter
            out = answer(g.by_id[enc.problem_id])
            event = out["boss"]
            if event.get("advanced"):
                turns += 1
                beat = event["beat"]
                self.assertTrue(beat["herald"], "a phase turn is announced")
                self.assertTrue(beat["tell"], "and says what changed")
                self.assertTrue(beat["state"]["kinds"], "and buffs the boss")
                self.assertNotIn(boss["id"], g.state["cleared_bosses"],
                                 "a phase is not the fight")
                continue
            if event.get("defeated"):
                break
        self.assertEqual(turns, fight["phases"] - 1,
                         "every phase but the first is a turn")
        self.assertIn(boss["id"], g.state["cleared_bosses"])
        # The key, which is derived rather than stored, and the road it opens.
        self.assertIn(world.KEY_BY_BOSS[boss["id"]]["id"],
                      world.keys_held(g.state["cleared_bosses"]))
        self.assertIsNone(g.state["boss_fight"], "a cleared fight comes down")

    def test_10b_the_portal_gates_the_story_and_never_the_practical(self):
        """The sharpest edge in the whole build, checked from both sides.

        The Standing Portal wants all fourteen keys and opens the story's last
        room. The practical is a MEASUREMENT and is reachable from the menu at
        any time with none of them. Both halves must be true.
        """
        from gauntlet import world
        g = self.game()
        self.assertEqual(g.portal()["held"], 0)
        self.assertFalse(g.portal()["open"])
        shut = g.enter_portal()
        self.assertFalse(shut["ok"])
        self.assertEqual(len(shut["missing"]), world.PORTAL_KEY_REQUIREMENT)

        # ...and the exam, with nothing unlocked and nothing earned.
        exam = g.start_interview("FINAL_EXAM")
        self.assertNotIn("error", exam)
        self.assertTrue(g.practical_access()["open"])
        self.assertFalse(g.practical_access()["requires_keys"])
        for name in ("practical", "interview", "exam", "measurement",
                     "readiness", "diagnostic"):
            self.assertFalse(world.portal_gates(name),
                             f"the portal must never gate {name!r}")
        g.finish_interview()

        g.state["cleared_bosses"] = [k["boss"] for k in world.KEYS]
        g.save()
        self.assertTrue(g.portal()["open"])
        self.assertTrue(g.enter_portal()["ok"])

    def test_11_interview_mode_disables_assistance(self):
        g = self.game()
        g.start_interview("LIVE_SCREEN")
        payload = g.interview_current()
        self.assertEqual(payload["problem"]["hint_tree"], [])
        self.assertEqual(g.use_hint(1)["error"], "sealed")
        self.assertEqual(g.probe([[1]], 1)["error"], "sealed")

    def test_12_skills_reflect_evidence(self):
        g = self.game()
        before = g.skills["SLIDING_WINDOW"]
        self.assertEqual(before.attempts, 0)
        self.assertEqual(before.mastery, 0)
        p = self.by_id("sw-k-distinct")
        g.start_encounter(p.id)
        g.submit(p.canonical_solution)
        after = g.skills["SLIDING_WINDOW"]
        self.assertEqual(after.attempts, 1)
        self.assertGreater(after.mastery, 0)
        self.assertIn(after.stage, ("INDEPENDENT", "ASSISTED", "RETAINED", "FAST"))

    def test_13_world_progression_works(self):
        from gauntlet import world
        g = self.game()
        skills = g.skills
        self.assertNotIn("graph_wastes", world.unlocked_regions(skills, set()))
        for name in ("PYTHON", "HASH_MAP", "ARRAY", "STRING", "RECURSION",
                     "TREE", "STACK"):
            skills[name].mastery = 70
        self.assertIn("binary_tree_canopy", world.unlocked_regions(skills, set()))

    def test_14_provenance_is_honest_and_company_agnostic(self):
        """Reported patterns carry the disclaimer and name nobody.

        Naming an employer would be a claim we cannot stand behind: these
        are recurring shapes, not questions anyone confirmed was asked. So
        the contract is the disclaimer, not the attribution.
        """
        reported = [p for p in self.corpus if p.source_type == "REPORTED_INTERVIEW"]
        self.assertGreaterEqual(len(reported), 8)
        for p in reported:
            self.assertIn("not a guarantee", p.provenance_note.lower())
            self.assertFalse(
                (p.reported_company or "").strip(),
                "%s names an employer" % p.id,
            )

    def test_14b_no_employer_is_named_anywhere_in_the_corpus(self):
        """Agnostic everywhere, not just in the provenance field."""
        banned = ("quora", "leetcode", "codesignal", "hackerrank", "faang")
        for p in self.corpus:
            blob = " ".join(str(x) for x in (
                p.title, p.problem_statement, p.provenance_note,
                p.reported_company or "", " ".join(p.tags or ()),
            )).lower()
            for word in banned:
                self.assertNotIn(word, blob, "%s mentions %s" % (p.id, word))

    def test_15_at_least_300_validated_problems(self):
        self.assertGreaterEqual(len(self.corpus), 300)
        self.assertEqual(len(self.report.errors), 0)

    def test_16_practical_interview_profile_works(self):
        g = self.game()
        g.set_profile("PRACTICAL")
        run = g.start_interview("GAUNTLET")
        self.assertEqual(run["run"]["profile"], "PRACTICAL")
        self.assertGreaterEqual(len(run["problems"]), 3)
        difficulties = [p["difficulty"] for p in run["problems"]]
        order = ["TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE", "BOSS"]
        indices = [order.index(d) for d in difficulties]
        self.assertEqual(indices, sorted(indices),
                         "the gauntlet must rise in difficulty")

    def test_17_game_has_depth_beyond_the_first_hour(self):
        """Content, systems and loot that keep a long session going."""
        from gauntlet import items, world
        self.assertGreaterEqual(len(self.corpus), 300)
        self.assertGreaterEqual(len(world.REGIONS), 16)
        self.assertGreaterEqual(len(world.BOSSES), 12)
        self.assertGreaterEqual(len(items.CATALOGUE), 30)
        self.assertGreaterEqual(len(items.SETS), 3)
        self.assertGreaterEqual(len(items.SECRETS), 4)
        kinds = {p.encounter_kind for p in self.corpus}
        self.assertGreaterEqual(len(kinds), 6, f"only {kinds} encounter types")

    def test_18_learning_gains_are_measurable(self):
        g = self.game()
        start = g.dashboard()["readiness"]["overall"]
        for pid in ("ah-two-sum-indices", "sw-k-distinct", "tp-valid-palindrome",
                    "sq-valid-parens", "tr-max-depth", "gr-bfs-order",
                    "bs-search", "dp-climb-stairs"):
            p = self.by_id(pid)
            g.start_encounter(p.id)
            g.submit(p.canonical_solution)
        end = g.dashboard()["readiness"]["overall"]
        self.assertGreater(end, start, "measurable improvement must be visible")
        history = g.performance_history()
        self.assertGreaterEqual(history["stats"]["solved"], 8)

    def test_19_the_loop_offers_a_reason_to_continue(self):
        g = self.game()
        g.choose_build("ANALYST")
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        result = g.submit(p.canonical_solution)
        self.assertGreater(result["xp"], 0)
        self.assertGreater(result["next_retest_days"], 0)
        dash = g.dashboard()
        self.assertTrue(dash["daily"]["quests"])
        self.assertTrue(dash["regions"])
        following = g.next_encounter()
        self.assertNotEqual(following["problem"]["id"], p.id)

    def test_20_final_completion_requires_readiness_gates(self):
        from gauntlet import adaptive, world
        g = self.game()
        skills = g.skills
        for state in skills.values():
            state.mastery = 30
            state.attempts = 3
        self.assertNotIn("null_kings_castle",
                         world.unlocked_regions(skills, {"a", "b", "c", "d", "e", "f"}))
        report = adaptive.readiness(skills=skills, schedule={}, stats={})
        self.assertFalse(report["ready"])
        self.assertLess(report["gates_passed"], report["gates_total"])


if __name__ == "__main__":
    unittest.main()
