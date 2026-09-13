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
        state.tier_clears = {"EASY": 6}
        state.tier_unaided = {"EASY": 3}
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

    # -- the scaffold band ------------------------------------------------
    #
    # These replace the old pins on "GUIDED below mastery 10, TUTORIAL below
    # 18". Those numbers were a real guarantee and this is a stricter one:
    # under the old rule five fill-in-the-blanks bought a blank screen, and
    # under this one a hundred of them never do. Every case below fails on the
    # old calibration.

    def _scaffolded(self, guided=0, tutorial=0, easy=0, mastery=0.0):
        """A skill state whose evidence is exactly the tiers named."""
        from gauntlet import skills as skillmod
        state = skillmod.SkillState(name="PYTHON")
        record = {"GUIDED": guided, "TUTORIAL": tutorial, "EASY": easy}
        state.tier_unaided = {k: v for k, v in record.items() if v}
        state.tier_clears = dict(state.tier_unaided)
        state.clears = state.unaided_clears = guided + tutorial + easy
        state.attempts = state.clears
        state.mastery = mastery
        return state

    def test_leaving_the_scaffold_costs_production_and_not_accumulation(self):
        """The bug this replaces: PYTHON gains 2.25 per GUIDED clear, the old
        band ended at 10, so eight scaffolded multiple-choice answers aimed a
        player who had never typed Python at a blank screen."""
        from gauntlet import adaptive, curriculum
        seven = self._scaffolded(guided=7, mastery=60.0)
        self.assertEqual(curriculum.scaffold_target(seven), "GUIDED")
        self.assertEqual(adaptive._difficulty_target(seven, seven), "GUIDED",
                         "seven fill-in-the-blanks is not evidence the "
                         "scaffolding can come off, at any mastery")

        eight = self._scaffolded(guided=8, mastery=60.0)
        self.assertEqual(adaptive._difficulty_target(eight, eight), "TUTORIAL")

        mid = self._scaffolded(guided=8, tutorial=5, mastery=99.0)
        self.assertEqual(adaptive._difficulty_target(mid, mid), "TUTORIAL",
                         "five skeletons filled in is not a blank screen")

        done = self._scaffolded(guided=8, tutorial=6, mastery=20.0)
        self.assertEqual(adaptive._difficulty_target(done, done), "EASY")

    def test_a_hundred_fill_in_the_blanks_never_buy_a_blank_screen(self):
        """The property, stated at the altitude it lives at: scaffolded
        evidence cannot promote past the scaffold however much of it there is.
        Mastery is pinned at the ceiling so it cannot be the thing deciding."""
        from gauntlet import adaptive, curriculum
        piles = self._scaffolded(guided=100, mastery=100.0)
        self.assertEqual(adaptive._difficulty_target(piles, piles), "TUTORIAL")
        self.assertFalse(curriculum.tier_unlocked(piles, "EASY"),
                         "the EASY gate must refuse what the target refuses")

    def test_one_unaided_clear_on_a_blank_screen_ends_the_band(self):
        """The escape hatch, and the only one. A beginner cannot reach it —
        EASY is gated — so it is the diagnostic's writing trial or nothing."""
        from gauntlet import adaptive, curriculum
        wrote = self._scaffolded(easy=1, mastery=18.0)
        self.assertTrue(curriculum.scaffold_cleared(wrote))
        self.assertEqual(adaptive._difficulty_target(wrote, wrote), "EASY")

    def test_targeting_and_unlocking_agree_about_the_blank_screen(self):
        """Two mechanisms decide whether a blank screen is allowed and they
        used to be calibrated separately. A target the gate refuses is a player
        aimed at material that cannot be served, which is how the beginner
        chain ended up ranked 285th."""
        from gauntlet import adaptive, curriculum
        cases = [self._scaffolded(guided=g, tutorial=t, easy=e, mastery=m)
                 for g in (0, 7, 8, 40) for t in (0, 5, 6)
                 for e in (0, 1) for m in (0.0, 15.0, 41.0)]
        for state in cases:
            target = adaptive._difficulty_target(state, state)
            aimed = curriculum.tier_index(target) >= 2
            # The gate has per-skill mastery and clear counts in it too, and
            # those are allowed to disagree with a target — a fluent player
            # meeting a new pattern is aimed at EASY and held at TUTORIAL until
            # that pattern has a clear behind it, which is the point. What may
            # never disagree is the scaffold clause, because it is the same
            # question asked twice.
            self.assertEqual(aimed, curriculum.scaffold_cleared(state),
                             f"target {target} against scaffold "
                             f"{curriculum.scaffold_target(state)}: "
                             f"{state.tier_unaided}")

    def test_the_language_is_what_the_scaffold_is_about(self):
        """A player who can write Python does not re-prove it once per pattern.
        Requiring that would also deadlock: the proof only exists at the tiers
        the requirement is gating."""
        from gauntlet import adaptive, curriculum
        fluent = self._scaffolded(easy=4, mastery=60.0)
        fresh = self._scaffolded()
        fresh.mastery = 14.0
        fresh.clears = fresh.attempts = 1
        fresh.tier_clears = {"TUTORIAL": 1}
        self.assertTrue(curriculum.tier_unlocked(fresh, "EASY", fluency=fluent))
        self.assertFalse(curriculum.tier_unlocked(fresh, "EASY", fluency=fresh))
        self.assertEqual(adaptive._difficulty_target(fresh, fluent), "EASY")

    def test_a_save_written_before_tier_records_is_not_demoted(self):
        """Old saves must still load, and loading is not the whole of it: a
        player mid-ramp when this shipped has real clears and no per-tier
        record of them. Absent evidence is not evidence of absence."""
        from gauntlet import adaptive, curriculum, skills as skillmod
        legacy = skillmod.SkillState(name="PYTHON", mastery=50.0, clears=30,
                                     unaided_clears=20, attempts=34)
        self.assertEqual(legacy.tier_clears, {})
        self.assertTrue(curriculum.scaffold_cleared(legacy))
        self.assertEqual(adaptive._difficulty_target(legacy, legacy), "MEDIUM")
        self.assertTrue(curriculum.tier_unlocked(legacy, "EASY"))

    def test_the_legacy_exemption_outlives_the_first_clear_after_it(self):
        """The pin this replaces held only at the instant of load, and the
        exemption it was pinning lasted exactly one encounter.

        `_tier_record_missing` asked whether the record was EMPTY. A returning
        player with thirty clears cleared one problem, the record became
        `{"TUTORIAL": 1}` — no longer empty — and the scaffold band was then
        decided on that single clear. Aimed at HARD on load, demoted to GUIDED
        one encounter later. The question is whether there are clears OUTSIDE
        the record, which thirty untracked ones remain however many tracked
        ones arrive after them.
        """
        from gauntlet import adaptive, curriculum, skills as skillmod
        legacy = skillmod.SkillState(name="PYTHON", mastery=50.0, clears=30,
                                     unaided_clears=20, attempts=34)
        self.assertEqual(curriculum.untracked_clears(legacy), 30)
        for tier in ("TUTORIAL", "GUIDED", "GUIDED", "EASY"):
            skillmod.apply_outcome(legacy, solved=True, difficulty=tier,
                                   hints_used=0, seconds=10.0,
                                   target_seconds=60.0, first_try=True,
                                   is_retest=False)
            self.assertEqual(curriculum.untracked_clears(legacy), 30,
                             "the old clears stopped counting as evidence")
            self.assertTrue(curriculum.scaffold_cleared(legacy),
                            f"demoted into the scaffold band by a {tier} clear")
        self.assertEqual(adaptive._difficulty_target(legacy, legacy), "MEDIUM")

    def test_an_old_save_keeps_the_bottom_of_the_band_it_was_earned_under(self):
        """Handing a pre-record save to the mastery ladder is only half an
        answer, because this build's ladder starts at EASY.

        A player with five old fill-in-the-blanks behind them — mastery 14,
        aimed at TUTORIAL by the build that wrote the save — came back to an
        empty editor, which is the exact failure the band was written to end.
        The clears were earned under the old calibration, so the old
        calibration is what they are read against, bottom rungs included.
        """
        from gauntlet import adaptive, curriculum, scaffold, skills as skillmod

        def old(mastery, clears=5):
            return skillmod.SkillState(name="PYTHON", mastery=mastery,
                                       clears=clears, unaided_clears=clears,
                                       attempts=clears)

        for mastery, tier in ((4.0, "GUIDED"), (14.0, "TUTORIAL"),
                              (30.0, "EASY"), (50.0, "MEDIUM")):
            state = old(mastery)
            self.assertEqual(adaptive._difficulty_target(state, state), tier,
                             f"mastery {mastery} on an old save")
        # And the same question asked through general fluency, for a pattern
        # the old save has no evidence in at all.
        fresh = skillmod.SkillState(name="HASH_MAP")
        self.assertEqual(adaptive._difficulty_target(fresh, old(14.0)), "GUIDED")
        self.assertEqual(adaptive._difficulty_target(fresh, old(70.0)), "EASY")
        # Once they produce unscaffolded code there IS a record, and it wins.
        # UNSCAFFOLDED IS THE RUNG, and it has to be said: this used to pass no
        # rung at all, which is what `engine` passes for a multiple choice, a
        # RUNE_ASSEMBLY or a DEBUG_BATTLE — and it passed anyway, because
        # `production_seen` was only incremented inside `if rung:` while
        # `tier_unaided` was incremented unconditionally, so the difference the
        # pre-rung exemption reads came out at 1 for an encounter where nothing
        # was written. See `curriculum.untracked_production`.
        produced = old(14.0)
        skillmod.apply_outcome(produced, solved=True, difficulty="EASY",
                               hints_used=0, seconds=10.0, target_seconds=60.0,
                               first_try=True, is_retest=False,
                               rung=scaffold.WRITE_IT_ALL)
        self.assertTrue(curriculum.has_produced_code(produced))
        self.assertEqual(adaptive._difficulty_target(produced, produced), "EASY")

    def test_a_player_whose_every_clear_is_recorded_is_still_governed(self):
        """The other side of that exemption: it must not become an escape
        hatch. A save written by this build has `clears` and `tier_clears` in
        step by construction, so the band applies to it in full."""
        from gauntlet import curriculum, skills as skillmod
        state = skillmod.SkillState(name="PYTHON")
        for _ in range(30):
            skillmod.apply_outcome(state, solved=True, difficulty="GUIDED",
                                   hints_used=0, seconds=10.0,
                                   target_seconds=60.0, first_try=True,
                                   is_retest=False)
        self.assertEqual(curriculum.untracked_clears(state), 0)
        self.assertEqual(curriculum.scaffold_target(state), "TUTORIAL",
                         "thirty fill-in-the-blanks are still thirty "
                         "fill-in-the-blanks")

    def test_the_state_survives_a_round_trip_through_the_save(self):
        from gauntlet import skills as skillmod
        state = skillmod.SkillState(name="PYTHON")
        skillmod.apply_outcome(state, solved=True, difficulty="GUIDED",
                               hints_used=0, seconds=10.0, target_seconds=60.0,
                               first_try=True, is_retest=False)
        reloaded = skillmod.SkillState(**state.to_dict())
        self.assertEqual(reloaded.tier_unaided, {"GUIDED": 1})

    def test_a_hinted_clear_is_not_evidence_the_hint_can_go(self):
        from gauntlet import curriculum, skills as skillmod
        state = skillmod.SkillState(name="PYTHON")
        for _ in range(20):
            skillmod.apply_outcome(state, solved=True, difficulty="GUIDED",
                                   hints_used=2, seconds=10.0,
                                   target_seconds=60.0, first_try=False,
                                   is_retest=False)
        self.assertEqual(state.tier_unaided, {})
        self.assertEqual(curriculum.scaffold_target(state), "GUIDED")

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

        Spelling it as an allow-list of kinds was still one kind short. The
        first_steps family opens on CODE_READING — a multiple-choice question
        about one line of Python, no editor on the screen at all — which
        satisfies the guarantee more completely than a fill-in-the-blank does
        and was nonetheless rejected for not being MISSING_RUNE. So the test
        asks the question directly instead of naming the kinds that happen to
        answer it: either the encounter wants no typed code, or it hands over
        working code with a hole in it. A bare `def f(n): pass` passes neither
        arm, which is the whole point.
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
            # Arm one: nothing to type into. The six puzzle kinds are graded
            # from a structured answer — an ordering, a checkpoint, a chosen
            # line — and a multiple-choice entry is graded from a chosen index.
            # Both conditions are needed: a RUNE_ASSEMBLY is a puzzle that still
            # carries a `function` entry, and a CODE_READING is an `mcq` entry
            # that is not in PUZZLE_KINDS.
            if (problem.encounter_kind in puzzles.PUZZLE_KINDS
                    or problem.entry.get("kind") == "mcq"):
                continue
            # Arm two: an editor, but never an empty one.
            self.assertIn("__BLANK__", problem.starter_code,
                          f"{problem.id} is a {problem.encounter_kind} that puts "
                          "an editor in front of a brand new player without "
                          "complete code in it")

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

    # Problems are reached by family and tier below, never by id. An id written
    # into the source is an id `corpus.RESERVED` has to carry, and adding to
    # RESERVED moves the hold-out — which a test about chapter gating has no
    # business doing.
    def _object_model_problems(self, tier="GUIDED"):
        from gauntlet import curriculum
        owned = {f for f in curriculum.CHAPTER_BY_ID["craft"].families
                 if f.startswith(("oop_", "python_"))}
        found = [p for p in self.corpus
                 if p.spaced_repetition_family in owned and p.difficulty == tier]
        self.assertTrue(found, "no object-model content at this tier")
        return found

    def test_a_family_a_later_chapter_owns_cannot_arrive_on_its_pattern(self):
        """Bug three, stated as a rule rather than as a symptom.

        The `__len__` fill-in-the-blank is labelled ARRAY, because there is no
        better word for it, and chapter I permits ARRAY. So a player twenty
        minutes past `print` met the object model at encounter nine. A pattern
        is a coarse label; the chapter that owns the family is the finer one,
        and it wins.
        """
        from gauntlet import curriculum, skills as skillmod
        fresh = skillmod.new_skills()
        allowed = curriculum.permitted_patterns(fresh)
        on_a_permitted_pattern = [p for p in self._object_model_problems()
                                  if p.pattern in allowed]
        self.assertTrue(on_a_permitted_pattern,
                        "the point of this test is a permitted pattern")
        for problem in on_a_permitted_pattern:
            self.assertFalse(curriculum.is_permitted(problem, fresh),
                             f"{problem.id} is not hour-one content")

    def test_nothing_the_ladder_owns_becomes_unreachable(self):
        """The other half. A gate that shuts a door forever is worse than the
        leak it closed, so every claimed family must open somewhere."""
        from gauntlet import curriculum, skills as skillmod
        late = skillmod.new_skills()
        for state in late.values():
            state.mastery, state.clears, state.unaided_clears = 95, 40, 20
            state.tier_clears = {"EASY": 40}
            state.tier_unaided = {"EASY": 20}
        opened = curriculum.permitted_families(late)
        self.assertEqual(sorted(curriculum.CLAIMED_FAMILIES - opened), [],
                         "these families are owned by a chapter that never opens")
        for problem in self._object_model_problems():
            self.assertTrue(
                curriculum.is_permitted(
                    problem, late,
                    skill_state=late.get(
                        skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")),
                    fluency=late.get("PYTHON")),
                f"{problem.id} became unreachable")

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


class TestTheBeginnerRamp(GameTest):
    """Bug one, driven through the real engine with a fresh save.

    The curriculum knowing about a 57-rung chain is not the same claim as the
    game walking it. Before this, a player met three of the fifty-seven rungs
    in two hundred encounters — the ramp existed and the selector would not
    take it.
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
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)
        return served

    def _chain_order(self):
        from gauntlet.corpus.families import first_steps
        return [p.id for p in first_steps.build()]

    def test_a_beginner_actually_walks_the_chain(self):
        """Measured on the real selector. Twelve is a floor, not a target: the
        rule is one rung in three while the scaffolding is on, and three of
        fifty-seven in two hundred is what it replaces."""
        served = self._walk(self.game(), 40)
        order = self._chain_order()
        met = [p.id for p in served if p.id in order]
        self.assertGreaterEqual(
            len(met), 12,
            f"only {len(met)} of {len(order)} rungs in 40 encounters: {met}")

    def test_the_rungs_arrive_in_the_order_they_were_written_in(self):
        served = self._walk(self.game(), 40)
        order = self._chain_order()
        positions = [order.index(p.id) for p in served if p.id in order]
        self.assertEqual(positions, sorted(positions),
                         "the chain was served out of order; the order is the "
                         "entire content of this family")
        self.assertEqual(positions, list(range(len(positions))),
                         "the chain skipped a rung")

    def test_nobody_is_shown_a_blank_screen_before_the_scaffolding_is_off(self):
        """The guarantee the old mastery band was trying to make and missed by
        thirty encounters."""
        from gauntlet import curriculum
        game = self.game()
        by_id = {p.id: p for p in self.corpus}
        from gauntlet import puzzles
        for _ in range(40):
            before = game.skills["PYTHON"]
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            if curriculum.tier_index(problem.difficulty) >= 2:
                self.assertTrue(
                    curriculum.scaffold_cleared(before),
                    f"{problem.id} is {problem.difficulty} and the player has "
                    f"only produced {before.tier_unaided}")
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)

    def test_the_chain_is_a_spine_and_not_a_diet(self):
        """The bound on the other side. One rung in three, so the beginner is
        not handed a run of twenty-five reading questions."""
        served = self._walk(self.game(), 40)
        order = set(self._chain_order())
        run = longest = 0
        for problem in served:
            run = run + 1 if problem.id in order else 0
            longest = max(longest, run)
        self.assertLessEqual(longest, 1, "the chain came in a block")
        self.assertLessEqual(
            sum(1 for p in served if p.id in order), 14,
            "more than a third of the first forty encounters was the chain")

    def test_a_rung_the_player_cannot_clear_is_not_served_on_a_loop(self):
        """CHAIN_GAP bounds how often a rung arrives, not which one.

        For a player who clears the rung those are the same sentence — the next
        pick is a different problem, because the last one is solved now. For a
        player who does not, they are not: a beginner who failed everything was
        served `fs-see-a-value` fourteen times in forty encounters, the same
        reading question every third turn, which is worse monotony than the
        block the gap exists to prevent and lands on the player least able to
        take it.
        """
        from gauntlet import puzzles
        from gauntlet.corpus.families import first_steps
        rungs = {p.id for p in first_steps.build()}
        game = self.game()
        by_id = {p.id: p for p in self.corpus}
        served = []
        for _ in range(40):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            served.append(problem.id)
            # Everything below is a WRONG answer, deliberately.
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.decoy_answer(problem) or [])
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(((problem.mcq.get("answer") or 0) + 1) % 4)
            else:
                game.submit("def wrong():\n    return None\n")
        worst = max((served.count(i) for i in set(served) if i in rungs),
                    default=0)
        self.assertLessEqual(
            worst, 5,
            f"one rung was served {worst} times in forty encounters to a "
            "player who never cleared it")
        self.assertGreater(worst, 0, "the chain stopped being offered at all")

    def test_a_chain_you_started_is_a_chain_you_finish(self):
        """The band ends around encounter forty with a dozen rungs behind the
        player; the forty-odd that teach `def`, `return` and the error messages
        are worth meeting. Past the band the open rung is scored at par rather
        than served by rule, so it keeps arriving without taking over."""
        served = self._walk(self.game(), 120)
        order = self._chain_order()
        met = [order.index(p.id) for p in served if p.id in order]
        self.assertEqual(met, list(range(len(met))), "out of order, or skipped")
        self.assertGreaterEqual(
            len(met), 18,
            f"the chain stalled at rung {len(met)} once the scaffolding came off")

    def test_the_waiver_cannot_reach_somebody_who_never_started(self):
        """Structural rather than a threshold: the waiver needs the previous
        rung cleared and the root has no previous rung, so a player who never
        took rung one is never offered rung two."""
        from gauntlet import adaptive
        from gauntlet.corpus.families import first_steps
        rungs = first_steps.build()
        root, second = rungs[0], rungs[1]
        self.assertFalse(adaptive._chain_in_progress(root, set()))
        self.assertFalse(adaptive._chain_in_progress(second, set()))
        self.assertTrue(adaptive._chain_in_progress(second, {root.id}))
        self.assertFalse(adaptive._chain_in_progress(second, {root.id, second.id}),
                         "a rung already cleared is not the open rung")

    def test_one_kind_never_runs_longer_than_the_limit(self):
        """Eight distinct kinds in twenty encounters is satisfied by six code
        battles in a row followed by seven other things. A run is what the
        player experiences as monotony, so it is bounded on its own."""
        from gauntlet import adaptive
        served = [p.encounter_kind for p in self._walk(self.game(), 60)]
        longest = run = 1
        for before, after in zip(served, served[1:]):
            run = run + 1 if before == after else 1
            longest = max(longest, run)
        self.assertLessEqual(longest, adaptive.KIND_RUN_LIMIT,
                             f"{longest} of one kind in a row: {served}")

    def test_the_object_model_stays_out_of_hour_one(self):
        """Bug three, measured. `oopl-len-guided` and `oopl-iter-guided` were
        encounters nine and ten — `__len__` and `__iter__`, to somebody who met
        `print` twenty minutes ago."""
        from gauntlet import curriculum
        owned = set(curriculum.CHAPTER_BY_ID["craft"].families)
        object_model = {f for f in owned
                        if f.startswith(("oop_", "python_", "stdlib_"))}
        served = self._walk(self.game(), 40)
        leaked = sorted({p.id for p in served
                         if p.spaced_repetition_family in object_model})
        self.assertEqual(leaked, [], "the object model reached hour one")


class TestAReturningPlayer(GameTest):
    """A save written by the build before this one, played forward.

    Loading it is the easy half and it always worked. The half that did not:
    what the ramp does with it on the very next encounter.
    """

    def _legacy_game(self, *, mastery=70.0, clears=40):
        """A save in the pre-change shape: real progress, no per-tier record.

        Built by playing nothing and writing the numbers, then stripping the
        two fields `SkillState` did not have when that build shipped — which is
        exactly what is on disk for everyone who has already played.
        """
        import json
        from gauntlet import db
        game = self.game()
        skills = game.skills
        for name in ("PYTHON", "HASH_MAP", "STRING", "ARRAY", "SET"):
            state = skills[name]
            state.mastery, state.clears = mastery, clears
            state.unaided_clears, state.attempts = int(clears * 0.7), clears + 4
            state.stage = "INDEPENDENT"
        game._write_skills(skills)
        game.save()
        raw = json.loads(json.dumps(game.state))
        for record in raw["skills"].values():
            record.pop("tier_clears", None)
            record.pop("tier_unaided", None)
        path = self.data_dir / "legacy.sqlite3"
        conn = db.connect(path)
        db.save_state(conn, raw)
        conn.close()
        from gauntlet.engine import Game
        return Game(db_path=path, corpus_path=self.corpus_path)

    def test_a_returning_player_is_not_sent_back_to_the_alphabet(self):
        """Measured, because the unit test above passed while this failed.

        Sixteen of the first twenty were fill-in-the-blanks and seven of them
        were rungs of the beginner chain — `print`, to somebody with forty
        clears and mastery 70 who was aimed at HARD on the load screen.
        """
        from gauntlet import curriculum
        from gauntlet.corpus.families import first_steps
        rungs = {p.id for p in first_steps.build()}
        game = self._legacy_game()
        self.assertTrue(curriculum.scaffold_cleared(game.skills["PYTHON"]))
        served = self._walk(game, 20)
        self.assertEqual([p.id for p in served if p.id in rungs], [],
                         "a returning player was walked into the beginner chain")
        guided = sum(1 for p in served if p.difficulty == "GUIDED")
        self.assertLessEqual(
            guided, 5,
            f"{guided} of the first twenty after reopening an old save were "
            f"fill-in-the-blanks: {[p.id for p in served]}")

    def test_an_old_save_keeps_every_number_it_arrived_with(self):
        from gauntlet import curriculum
        game = self._legacy_game()
        skills = game.skills
        self.assertEqual(skills["PYTHON"].clears, 40)
        self.assertAlmostEqual(skills["PYTHON"].mastery, 70.0)
        self.assertEqual(skills["PYTHON"].tier_clears, {})
        self.assertEqual(curriculum.untracked_clears(skills["PYTHON"]), 40)
        self.assertTrue(game.dashboard().get("player"))

    _walk = TestTheBeginnerRamp._walk


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

    # -- the skip has to be real -------------------------------------------
    #
    # `chapter_index` was computed, printed to the player in so many words —
    # "You do not need the alphabet. We start at Counting and Membership" —
    # written into the save, and read by nothing. `diagnostic_finish` seeded
    # mastery, `frontier()` recomputed from that mastery, and the answer was
    # chapter one. A player who aced every trial was told chapter IV and served
    # twelve GUIDED fill-in-the-blanks out of their first twenty. Either the
    # sentence goes or the skip does; these pin the skip.

    def test_the_skip_the_diagnostic_promises_is_the_skip_it_performs(self):
        from gauntlet import curriculum, diagnostic
        game = self.game()
        answers = {t.id: {"correct": True} for t in diagnostic.TRIALS}
        result = game.diagnostic_finish(answers)
        self.assertGreaterEqual(result["chapter_index"], 3)
        self.assertEqual(result["chapter"]["number"],
                         result["chapter_index"] + 1,
                         "the game told them one chapter and opened another")
        self.assertEqual(curriculum.frontier(game.skills),
                         result["chapter_index"])

    def test_the_skip_opens_what_the_chapter_it_names_is_about(self):
        from gauntlet import curriculum, diagnostic
        game = self.game()
        game.diagnostic_finish({t.id: {"correct": True}
                                for t in diagnostic.TRIALS})
        allowed = curriculum.permitted_patterns(game.skills)
        self.assertTrue(allowed and "HASH_MAP" in allowed,
                        "placed at Counting and Membership with no hash maps")

    def test_a_skipped_chapter_is_not_a_lost_chapter(self):
        """Nothing is taken away by a placement. The skipped chapters stay
        open, their content stays servable, and the quest log says `skipped`
        rather than `done`, because the player did not do them."""
        from gauntlet import curriculum, diagnostic
        game = self.game()
        placed = game.diagnostic_finish({t.id: {"correct": True}
                                         for t in diagnostic.TRIALS})
        skills = game.skills
        families = curriculum.permitted_families(skills)
        for family in curriculum.CHAPTERS[0].families:
            self.assertIn(family, families, "a skipped chapter went dark")
        states = [rung["state"] for rung in curriculum.ladder(skills)]
        self.assertEqual(states[:placed["chapter_index"]],
                         ["skipped"] * placed["chapter_index"])
        self.assertEqual(states[placed["chapter_index"]], "current")

    def test_the_placement_never_moves_a_player_backwards(self):
        """A floor, and only a floor. Somebody who has earned their way past
        the chapter they were placed on is not pulled back to it."""
        from gauntlet import curriculum, diagnostic, skills as skillmod
        placed = skillmod.new_skills().with_floor(3)
        for state in placed.values():
            state.mastery, state.clears, state.unaided_clears = 95, 40, 20
            state.tier_clears, state.tier_unaided = {"EASY": 40}, {"EASY": 20}
        self.assertGreater(curriculum.frontier(placed), 3)
        self.assertEqual(curriculum.frontier(skillmod.new_skills()), 0,
                         "no placement, no floor")
        self.assertEqual(diagnostic.skip_placement().chapter_index, 0)

    def test_the_skip_rests_on_the_one_trial_that_is_graded_code(self):
        """Mastery moves only on graded evidence, and so does a skip. Four of
        the five trials are multiple choice; the writing trial runs the
        player's code in the real sandbox against real tests, and it is the
        only one that leaves a record of production."""
        from gauntlet import curriculum, diagnostic, skills as skillmod
        every = {t.id: {"correct": True} for t in diagnostic.TRIALS}
        wrote = diagnostic.evaluate(every)
        self.assertTrue(wrote.produced_code)

        read_only = dict(every, **{"t2-write": {"correct": False}})
        placement = diagnostic.evaluate(read_only)
        self.assertFalse(placement.produced_code)
        self.assertEqual(placement.chapter_index, 0,
                         "a skip without production evidence is not a skip")

        book = skillmod.new_skills()
        diagnostic.seed_skills(book, placement)
        self.assertEqual(curriculum.scaffold_target(book["PYTHON"]), "GUIDED",
                         "reading well is not writing; the scaffold stays on")

        book = skillmod.new_skills()
        diagnostic.seed_skills(book, wrote)
        self.assertTrue(curriculum.scaffold_cleared(book["PYTHON"]))
        self.assertEqual(book["PYTHON"].tier_unaided, {"EASY": 1},
                         "the trial was one unaided solve and counts as one")

    def test_a_fluent_player_is_not_walked_through_the_beginner_chain(self):
        """The other end of bug one. The chain is fifty-seven rungs of `print`
        and somebody who already writes Python must not meet any of it."""
        from gauntlet import diagnostic, puzzles
        from gauntlet.corpus.families import first_steps
        rungs = {p.id for p in first_steps.build()}
        game = self.game()
        game.diagnostic_finish({t.id: {"correct": True}
                                for t in diagnostic.TRIALS})
        by_id = {p.id: p for p in self.corpus}
        served = []
        for _ in range(20):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            served.append(problem)
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)
        self.assertEqual([p.id for p in served if p.id in rungs], [])
        guided = sum(1 for p in served if p.difficulty == "GUIDED")
        self.assertLessEqual(guided, 4,
                             f"{guided} of the first twenty were fill-in-the-"
                             "blanks for somebody who writes Python: "
                             f"{[p.id for p in served]}")

    def test_the_chapter_the_skip_names_is_the_chapter_that_is_served(self):
        """Half of bug two survived the floor that fixed the other half.

        `frontier()` returned 3 and the ladder said Counting and Membership,
        and the first twenty encounters were twelve linked-list two-pointer
        problems against one hash map. The cause was not the gate — chapter IV
        was open and so was its content — it was that nothing in the scorer
        preferred the chapter the player is ON over the chapter of lookahead
        behind it, so a sixteen-way tie at the top of the ranking was settled
        by which family the corpus builds first. Being told a chapter's name
        and served the next one is the same complaint in a smaller font.
        """
        from gauntlet import curriculum, diagnostic, puzzles
        game = self.game()
        placed = game.diagnostic_finish({t.id: {"correct": True}
                                         for t in diagnostic.TRIALS})
        owned = set(curriculum.CHAPTERS[placed["chapter_index"]].families)
        by_id = {p.id: p for p in self.corpus}
        served = []
        for _ in range(20):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            served.append(problem)
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)
        on_topic = [p.id for p in served
                    if p.spaced_repetition_family in owned]
        self.assertGreaterEqual(
            len(on_topic), 8,
            f"placed on {placed['chapter']['title']} and served "
            f"{len(on_topic)} of twenty from it: "
            f"{[(p.id, p.spaced_repetition_family) for p in served]}")

    def test_the_frontier_is_a_thumb_on_the_scale_and_not_a_gate(self):
        """The bound on that term. Lookahead is a feature — the world is not a
        corridor — so being on the frontier may break a tie and may not
        outrank readiness, monotony, or anything else with real evidence
        behind it."""
        from gauntlet import adaptive
        self.assertLess(adaptive.FRONTIER_CHAPTER_BONUS, 5.0,
                        "the frontier must not be worth a difficulty tier")
        self.assertLess(adaptive.FRONTIER_CHAPTER_BONUS, 6.0,
                        "the frontier must not outrank an unexplored skill")

    def test_a_player_who_fails_the_trial_gets_the_ramp(self):
        """The instrument has to cut both ways or it is not an instrument."""
        from gauntlet import curriculum, diagnostic
        game = self.game()
        result = game.diagnostic_finish({t.id: {"correct": False}
                                         for t in diagnostic.TRIALS})
        self.assertEqual(result["chapter_index"], 0)
        skills = game.skills
        self.assertEqual(curriculum.frontier(skills), 0)
        self.assertEqual(curriculum.scaffold_target(skills["PYTHON"]), "GUIDED")

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
