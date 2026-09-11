"""The ramp, the diagnostic and the puzzle types.

These exist because the player's report was "the game is too hard". Each test
encodes one of the guarantees that report demanded.
"""
from base import GameTest  # noqa: E402
import unittest


class TestCurriculum(GameTest):
    def test_a_fresh_player_never_meets_an_advanced_pattern(self):
        """The original failure: tree recursion appeared at encounter six."""
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        allowed = curriculum.permitted_patterns(s)
        self.assertTrue(allowed, "a fresh player must be restricted, not unrestricted")
        for forbidden in ("TREE", "RECURSION", "DFS", "BFS", "DP", "GRAPH",
                          "BINARY_SEARCH", "HEAP", "MATRIX"):
            self.assertNotIn(forbidden, allowed,
                             f"{forbidden} must not be reachable on day one")

    def test_the_ladder_opens_in_order(self):
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        self.assertEqual(curriculum.frontier(s), 0)

        # graduate chapter one on both counts
        s["PYTHON"].mastery = 40
        s["PYTHON"].clears = 20
        self.assertGreaterEqual(curriculum.frontier(s), 1)

    def test_graduation_needs_both_mastery_and_clears(self):
        """Mastery alone can come from a few lucky solves; clears alone can come
        without understanding. Requiring both is what makes the ramp honest."""
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        s["PYTHON"].mastery = 99
        s["PYTHON"].clears = 1
        self.assertEqual(curriculum.frontier(s), 0, "mastery alone must not graduate")

        s = skillmod.new_skills()
        s["PYTHON"].mastery = 2
        s["PYTHON"].clears = 99
        self.assertEqual(curriculum.frontier(s), 0, "clears alone must not graduate")

    def test_difficulty_tiers_are_earned_per_skill(self):
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        state = s["HASH_MAP"]
        self.assertFalse(curriculum.tier_unlocked(state, "MEDIUM"))
        self.assertTrue(curriculum.tier_unlocked(state, "TUTORIAL"))

        state.mastery, state.clears, state.unaided_clears = 45, 6, 3
        self.assertTrue(curriculum.tier_unlocked(state, "MEDIUM"))
        self.assertFalse(curriculum.tier_unlocked(state, "HARD"))

    def test_medium_requires_unaided_easy_evidence(self):
        """Someone who only ever clears with hints must not be promoted."""
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        state = s["HASH_MAP"]
        state.mastery, state.clears, state.unaided_clears = 60, 12, 0
        self.assertFalse(curriculum.tier_unlocked(state, "MEDIUM"),
                         "assisted clears alone must not unlock MEDIUM")

    def test_lookahead_keeps_the_world_from_being_a_corridor(self):
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        self.assertGreaterEqual(len(curriculum.open_chapters(s)), 2)

    def test_late_chapters_lift_all_restrictions(self):
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        for state in s.values():
            state.mastery = 95
            state.clears = 40
            state.unaided_clears = 20
        self.assertEqual(curriculum.permitted_patterns(s), set(),
                         "an advanced player must face the whole corpus")

    def test_the_scaffold_rungs_are_what_a_new_player_actually_meets(self):
        """The curriculum module knowing about GUIDED is not the same as the game
        serving it. This drives the real selection path, because the first version
        of the ramp left all 31 GUIDED problems unreachable.

        The guarantee is that nobody's first six encounters are a blank screen.
        It used to be spelled "all six are MISSING_RUNE", which was the only kind
        that could satisfy it at the time; the puzzle kinds satisfy it too, and
        harder — a rune assembly asks for no typing at all. So the check is
        written at the altitude the guarantee actually lives at, and it now also
        forbids the thing it always meant to forbid.
        """
        from gauntlet import puzzles
        g = self.game()
        seen = []
        for _ in range(6):
            enc = g.next_encounter()
            problem = self.by_id(enc["problem"]["id"])
            seen.append(problem)
            g.state["solved_ids"].append(problem.id)
            g.state["recent_ids"].insert(0, problem.id)
        for problem in seen:
            self.assertEqual(problem.difficulty, "GUIDED",
                             f"{problem.id} is {problem.difficulty}; a blank screen "
                             "is what the player complained about")
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                continue              # no editor at all; nothing to type into
            self.assertEqual(problem.encounter_kind, "MISSING_RUNE",
                             f"{problem.id} is a {problem.encounter_kind}; the "
                             "opening rungs are scaffolds and puzzles, not empty "
                             "editors")
            self.assertIn("__BLANK__", problem.starter_code,
                          f"{problem.id} must hand the player complete code")

    def test_the_live_selection_path_honours_the_gate(self):
        """test_a_fresh_player_never_meets_an_advanced_pattern checks the gate in
        isolation. This checks that encounter selection actually consults it —
        it did not, and tree recursion still reached a chapter-one player."""
        from gauntlet import curriculum, skills as skillmod
        g = self.game()
        for _ in range(40):
            enc = g.next_encounter()
            problem = self.by_id(enc["problem"]["id"])
            skills = g.skills
            allowed = curriculum.permitted_patterns(skills)
            if allowed:
                self.assertIn(problem.pattern, allowed,
                              f"{problem.id} ({problem.pattern}) is outside the "
                              "chapters this player has opened")
            state = skills.get(
                skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"))
            self.assertTrue(curriculum.tier_unlocked(state, problem.difficulty),
                            f"{problem.id} is a locked {problem.difficulty} tier")
            g.state["solved_ids"].append(problem.id)
            g.state["recent_ids"].insert(0, problem.id)

    def test_the_ladder_is_reportable_to_the_player(self):
        from gauntlet import curriculum, skills as skillmod
        s = skillmod.new_skills()
        rungs = curriculum.ladder(s)
        self.assertEqual(len(rungs), len(curriculum.CHAPTERS))
        self.assertEqual(rungs[0]["state"], "current")
        self.assertEqual(rungs[1]["state"], "next")
        self.assertEqual(rungs[-1]["state"], "locked")
        objective = curriculum.next_objective(s)
        self.assertTrue(objective["goal"])
        self.assertTrue(objective["title"])


class TestDiagnostic(GameTest):
    def test_it_places_a_reader_who_cannot_write_at_the_beginning(self):
        """The player's actual profile: strong reading, blank-screen paralysis."""
        from gauntlet import diagnostic
        answers = {t.id: {"correct": True} for t in diagnostic.TRIALS}
        answers["t2-write"] = {"correct": False}
        placement = diagnostic.evaluate(answers)
        self.assertEqual(placement.chapter_index, 0)
        self.assertIn("blank screen", placement.verdict.lower())

    def test_it_can_place_a_fluent_player_forward(self):
        from gauntlet import diagnostic
        answers = {t.id: {"correct": True} for t in diagnostic.TRIALS}
        placement = diagnostic.evaluate(answers)
        self.assertGreaterEqual(placement.chapter_index, 2,
                                "a fluent player must not be made to sit through drills")

    def test_a_total_beginner_starts_at_chapter_one(self):
        from gauntlet import diagnostic
        answers = {t.id: {"correct": False} for t in diagnostic.TRIALS}
        placement = diagnostic.evaluate(answers)
        self.assertEqual(placement.chapter_index, 0)

    def test_skipping_is_safe(self):
        from gauntlet import diagnostic
        self.assertEqual(diagnostic.skip_placement().chapter_index, 0)

    def test_seeded_mastery_stays_weak_evidence(self):
        """A diagnostic must not be able to fake its way past a chapter."""
        from gauntlet import diagnostic, skills as skillmod
        s = skillmod.new_skills()
        answers = {t.id: {"correct": True} for t in diagnostic.TRIALS}
        placement = diagnostic.evaluate(answers)
        diagnostic.seed_skills(s, placement)
        for name in placement.seed_mastery:
            self.assertLessEqual(s[name].mastery, 35)
            self.assertLessEqual(s[name].confidence, 18)

    def test_every_trial_explains_itself_either_way(self):
        from gauntlet import diagnostic
        for correct in (True, False):
            answers = {t.id: {"correct": correct} for t in diagnostic.TRIALS}
            placement = diagnostic.evaluate(answers)
            for entry in placement.detail:
                self.assertTrue(entry["note"], f"{entry['id']} teaches nothing")


class TestPuzzles(GameTest):
    def _problem(self, **kwargs):
        from gauntlet.corpus.schema import Problem
        base = dict(id="pz", title="t", realm="python_village", pattern="ARRAY",
                    difficulty="GUIDED", problem_statement="x",
                    entry={"kind": "function", "name": "count_positive"},
                    canonical_solution="", encounter_kind="RUNE_ASSEMBLY")
        base.update(kwargs)
        return Problem(**base)

    RUNES = [
        {"text": "def count_positive(values):", "indent": 0, "distractor": False, "note": ""},
        {"text": "total = 0", "indent": 1, "distractor": False, "note": ""},
        {"text": "for value in values:", "indent": 1, "distractor": False, "note": ""},
        {"text": "if value > 0:", "indent": 2, "distractor": False, "note": ""},
        {"text": "total += 1", "indent": 3, "distractor": False, "note": ""},
        {"text": "return total", "indent": 1, "distractor": False, "note": ""},
        {"text": "values.sort()", "indent": 1, "distractor": True,
         "note": "Sorting cannot change how many values are positive."},
    ]

    def _assembly(self):
        return self._problem(
            mcq={"runes": self.RUNES},
            visible_tests=[{"name": "mixed", "args": [[-1, 2, 3]], "expected": 2,
                            "cmp": "exact", "hidden": False, "kind": "correctness",
                            "reveal": True}],
            hidden_tests=[{"name": "empty", "args": [[]], "expected": 0,
                           "cmp": "exact", "hidden": True, "kind": "correctness",
                           "reveal": True}])

    def test_rune_assembly_accepts_the_right_order(self):
        from gauntlet import puzzles
        p = self._assembly()
        order = [{"index": i, "indent": self.RUNES[i]["indent"]} for i in range(6)]
        self.assertTrue(puzzles.grade(p, order)["solved"])

    def test_rune_assembly_is_graded_by_running_the_code(self):
        """Order and indentation are checked, but the assembled source must also
        actually pass the tests — a puzzle that only compares sequences could be
        solved by memorising a sequence."""
        from gauntlet import puzzles
        p = self._assembly()
        scrambled = [{"index": i, "indent": self.RUNES[i]["indent"]}
                     for i in [0, 2, 1, 3, 4, 5]]
        result = puzzles.grade(p, scrambled)
        self.assertFalse(result["solved"])
        self.assertIn("assembled_source", result)

    def test_rune_assembly_rejects_distractors(self):
        from gauntlet import puzzles
        p = self._assembly()
        order = [{"index": i, "indent": self.RUNES[i]["indent"]} for i in range(6)]
        order.append({"index": 6, "indent": 1})
        result = puzzles.grade(p, order)
        self.assertFalse(result["solved"])
        self.assertTrue(any("does not belong" in line["message"]
                            for line in result["lines"]))

    def test_wrong_indentation_is_caught(self):
        from gauntlet import puzzles
        p = self._assembly()
        order = [{"index": i, "indent": self.RUNES[i]["indent"]} for i in range(6)]
        order[4]["indent"] = 2          # total += 1 escapes the if
        result = puzzles.grade(p, order)
        self.assertFalse(result["solved"])

    def test_break_it_rewards_finding_the_real_edge_case(self):
        from gauntlet import puzzles
        p = self._problem(
            encounter_kind="BREAK_IT",
            entry={"kind": "function", "name": "average"},
            canonical_solution="def average(nums):\n"
                               "    return sum(nums) / len(nums) if nums else 0.0\n",
            mcq={"flawed_code": "def average(nums):\n"
                                "    return sum(nums) / len(nums)\n",
                 "explanation": "An empty list divides by zero."})
        self.assertTrue(puzzles.grade(p, [[]])["solved"],
                        "the empty list is the break and must be recognised")
        self.assertFalse(puzzles.grade(p, [[1, 2, 3]])["solved"],
                         "an ordinary input does not expose the flaw")

    def test_break_it_explains_only_on_success(self):
        from gauntlet import puzzles
        p = self._problem(
            encounter_kind="BREAK_IT",
            entry={"kind": "function", "name": "average"},
            canonical_solution="def average(nums):\n"
                               "    return sum(nums) / len(nums) if nums else 0.0\n",
            mcq={"flawed_code": "def average(nums):\n    return sum(nums) / len(nums)\n",
                 "explanation": "An empty list divides by zero."})
        self.assertTrue(puzzles.grade(p, [[]])["explanation"])
        self.assertFalse(puzzles.grade(p, [[1]])["explanation"])

    def test_trace_is_forgiving_about_format_and_strict_about_value(self):
        from gauntlet import puzzles
        p = self._problem(
            encounter_kind="TRACE", entry={"kind": "mcq", "name": "x"},
            mcq={"checkpoints": [
                {"after_line": 3, "variable": "counts", "expected": "{'a': 2}",
                 "hint": ""}]})
        self.assertTrue(puzzles.grade(p, ["{'a':2}"])["solved"])
        self.assertTrue(puzzles.grade(p, ['{"a": 2}'])["solved"])
        self.assertFalse(puzzles.grade(p, ["{'a': 3}"])["solved"])

    def test_empty_puzzles_never_count_as_solved(self):
        from gauntlet import puzzles
        p = self._problem(encounter_kind="TRACE",
                          entry={"kind": "mcq", "name": "x"},
                          mcq={"checkpoints": []})
        self.assertFalse(puzzles.grade(p, [])["solved"])
        self.assertIs(puzzles.grade(p, [])["solved"], False,
                      "solved must be a real boolean, not a truthy value")

    def test_complexity_match_requires_every_pairing(self):
        from gauntlet import puzzles
        p = self._problem(
            encounter_kind="COMPLEXITY_MATCH", pattern="COMPLEXITY",
            entry={"kind": "mcq", "name": "x"},
            mcq={"snippets": [{"label": "a", "complexity": "O(n)", "why": ""},
                              {"label": "b", "complexity": "O(n^2)", "why": ""}]})
        self.assertTrue(puzzles.grade(p, {"0": "O(n)", "1": "O(n^2)"})["solved"])
        self.assertFalse(puzzles.grade(p, {"0": "O(n)"})["solved"])

    def test_every_puzzle_kind_has_a_grader_and_a_blurb(self):
        from gauntlet import puzzles
        for kind in puzzles.PUZZLE_KINDS:
            self.assertIn(kind, puzzles.GRADERS)
            self.assertIn(kind, puzzles.PUZZLE_BLURB)
            self.assertIn(kind, puzzles.PUZZLE_SKILL)

    def test_a_malformed_answer_is_a_wrong_answer_not_a_crash(self):
        """The payload comes off the wire. A puzzle graded on nonsense is
        unsolved; it is not a traceback out of the server."""
        from gauntlet import puzzles
        for kind in puzzles.PUZZLE_KINDS:
            problem = next(p for p in self.corpus if p.encounter_kind == kind)
            for junk in ("def f():\n    pass\n", None, 42, {}, []):
                self.assertIs(puzzles.grade(problem, junk)["solved"], False,
                              f"{kind} accepted {junk!r}")


class TestPuzzleCorpus(GameTest):
    """The graders are proven by TestPuzzles. This proves there is content for
    them, that the content is honest, and that the engine actually serves it —
    all three failed independently at some point, and each one alone is enough
    to make the puzzle kinds invisible to the player."""

    def test_every_puzzle_kind_has_content_in_the_corpus(self):
        from gauntlet import puzzles
        for kind in puzzles.PUZZLE_KINDS:
            self.assertTrue([p for p in self.corpus if p.encounter_kind == kind],
                            f"{kind} has a grader, an interface and no problems")

    def test_every_puzzle_carries_the_fields_its_grader_needs(self):
        from gauntlet import puzzles
        from gauntlet.corpus import validate as validator
        for p in self.corpus:
            if p.encounter_kind not in puzzles.PUZZLE_KINDS:
                continue
            issues = validator._puzzle_static(p)
            self.assertEqual([i.message for i in issues], [],
                             f"{p.id} would reach the player unplayable")

    def test_every_puzzle_is_winnable_by_its_own_answer_key(self):
        """A puzzle whose key does not grade as solved is a fight with no win
        condition, and no amount of understanding gets the player out of it."""
        from concurrent.futures import ThreadPoolExecutor
        from gauntlet import puzzles

        def check(p):
            outcome = puzzles.grade(p, puzzles.answer_key(p))
            return None if outcome["solved"] else (
                f"{p.id} ({p.encounter_kind}): key grades "
                f"{outcome['passed']}/{outcome['total']}")

        targets = [p for p in self.corpus
                   if p.encounter_kind in puzzles.PUZZLE_KINDS]
        self.assertGreaterEqual(len(targets), 6)
        with ThreadPoolExecutor(max_workers=8) as pool:
            bad = [m for m in pool.map(check, targets) if m]
        self.assertEqual(bad, [])

    def test_no_puzzle_is_trivially_winnable(self):
        """Winnable is half the contract. A puzzle that grades a guess as a solve
        teaches that guessing works, which is worse than an unwinnable one."""
        from concurrent.futures import ThreadPoolExecutor
        from gauntlet import puzzles

        def check(p):
            decoy = puzzles.decoy_answer(p)
            if decoy is None:            # BREAK_IT: an input both spells agree on
                decoy = list(p.visible_tests[0]["args"])
            return (f"{p.id} ({p.encounter_kind}) accepted {decoy!r}"
                    if puzzles.grade(p, decoy)["solved"] else None)

        targets = [p for p in self.corpus
                   if p.encounter_kind in puzzles.PUZZLE_KINDS]
        with ThreadPoolExecutor(max_workers=8) as pool:
            bad = [m for m in pool.map(check, targets) if m]
        self.assertEqual(bad, [])

    def test_the_answer_key_never_reaches_the_client(self):
        """`mcq` carries the grading key, and `player_view` used to ship it whole
        — which handed every answer to anyone who opened devtools once."""
        from gauntlet import puzzles
        leaks = {"flawed_line", "final_state", "probes", "expected", "complexity",
                 "distractor", "indent", "answer", "explanation", "probe", "why"}
        for p in self.corpus:
            if p.encounter_kind not in puzzles.PUZZLE_KINDS:
                continue
            spec = p.player_view(mode="adventure")["mcq"]
            self.assertTrue(spec, f"{p.id} sends the client nothing to render")
            for key, value in spec.items():
                self.assertNotIn(key, leaks, f"{p.id} leaks mcq[{key!r}]")
                for item in (value if isinstance(value, list) else []):
                    if isinstance(item, dict):
                        self.assertEqual(set(item) & leaks, set(),
                                         f"{p.id} leaks inside mcq[{key!r}]")

    def test_the_engine_serves_a_mix_of_encounter_kinds(self):
        """The regression this guards: puzzles scored level with the scaffolds,
        ties resolve by corpus order, and the puzzle families are built last — so
        sixty encounters produced fourteen fill-in-the-blanks in a row and
        exactly one puzzle. Variety is a property of the sequence, so it is
        checked against a sequence."""
        from gauntlet import puzzles
        g = self.game()
        served = []
        for _ in range(60):
            enc = g.next_encounter()
            p = self.by_id(enc["problem"]["id"])
            served.append(p.encounter_kind)
            if p.encounter_kind in puzzles.PUZZLE_KINDS:
                g.solve_puzzle(puzzles.answer_key(p))
            elif p.entry.get("kind") == "mcq":
                g.answer_mcq(p.mcq["answer"])
            elif p.entry.get("kind") == "test_forge":
                g.submit(p.starter_code)
            else:
                g.submit(p.canonical_solution)

        puzzle_count = sum(1 for k in served if k in puzzles.PUZZLE_KINDS)
        self.assertGreaterEqual(puzzle_count, 9,
                                f"only {puzzle_count} puzzles in 60 encounters: "
                                f"{served}")
        self.assertLessEqual(puzzle_count, 24,
                             "puzzles are a change of pace, not the main course")
        self.assertGreaterEqual(len(set(served)), 4,
                                f"the whole run was {set(served)}")

        longest, run = 1, 1
        for before, after in zip(served, served[1:]):
            run = run + 1 if before == after else 1
            longest = max(longest, run)
        self.assertLessEqual(longest, 5,
                             f"{longest} encounters of one kind in a row: {served}")


if __name__ == "__main__":
    unittest.main()
