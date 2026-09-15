"""The practical as the ending: what a pass buys, and what a failure costs.

Six claims, and the first one is the one that would quietly ruin the game:

  1. AN ORDINARY TIMED PRACTICAL MODE RUN ENDS NOTHING. It is a measurement, it is
     available with no keys at any point in the game, and sitting it — even
     sitting the sealed practical format itself, even passing it — frees
     nobody, plays no cutscene and changes no world.
  2. A STAGED PASS IS THE REWARD. The index falls, everybody still filed is
     out, the cutscene plays end to end, and the world changes.
  3. A STAGED FAILURE IS A REMATCH AND NEVER A LOSS. Nobody is freed, nothing
     is consumed, no cooldown is imposed, the portal stays open and the
     practical recomposes.
  4. THE KING NAMES AND NEVER TEACHES. He may say what failed. He may never say
     what to do about it, in either scene, at any verdict.
  5. THE TWO LISTS NEVER MERGE. The people the player carried out and the
     people the collapse let out are counted, staged and ribboned separately,
     and a player who freed nobody is never told they freed somebody.
  6. THE ENDING NEVER GATES THE MEASUREMENT, in either direction.
"""
from base import GameTest  # noqa: E402

from gauntlet import captives, config, ending, finale, finalexam, world


class TheEnding(GameTest):

    # -- helpers ----------------------------------------------------------

    def _report(self, *, solved: int, seed: int = 11):
        """A real debrief, off a real composed exam, at a chosen score."""
        exam = finalexam.compose(self.corpus, seed=seed)
        questions = [q for seg in exam.segments for q in seg["questions"]]
        results = [{"problem_id": q.problem_id, "solved": index < solved,
                    "rank": "S" if index < solved else "",
                    "seconds": int(q.target_seconds * 0.8),
                    "root_cause": "" if index < solved else "OFF_BY_ONE"}
                   for index, q in enumerate(questions)]
        return exam, finalexam.debrief(exam, results)

    def _save(self, *, bosses=()):
        state: dict = {}
        for boss_id in bosses:
            captives.free(state, boss_id)
        ending.ensure(state)
        return state

    def _all_bosses(self):
        return [b["id"] for b in world.BOSSES]

    def _king_lines(self, scene):
        return [line["text"] for beat in scene["beats"]
                for line in beat["lines"]
                if line["speaker"] == finale.KING_ID]

    # -- 1. the measurement ends nothing ----------------------------------

    def test_an_interview_mode_run_never_ends_the_game(self):
        for solved in (0, 3, 6, 99):
            with self.subTest(solved=solved):
                state = self._save(bosses=self._all_bosses()[:4])
                before = list(captives.freed(state))
                _, report = self._report(solved=solved)
                out = ending.resolve(state, exam_report=report)
                self.assertFalse(out["triggered"])
                self.assertEqual(out["outcome"], "NONE")
                self.assertIsNone(out["cutscene"])
                self.assertEqual(out["captives_freed_now"], 0)
                self.assertEqual(captives.released(state), [])
                self.assertEqual(captives.freed(state), before)
                self.assertFalse(captives.index_collapsed(state))

    def test_even_a_passed_menu_sitting_ends_nothing(self):
        """The strongest form of it: the sealed practical, passed, from the
        menu, with every key in the game held. Still a measurement."""
        state = self._save(bosses=self._all_bosses())
        _, report = self._report(solved=99)
        self.assertEqual(report["verdict"]["code"], "READY")
        out = ending.resolve(state, exam_report=report,
                             cleared_bosses=self._all_bosses())
        self.assertFalse(out["triggered"])
        self.assertFalse(captives.index_collapsed(state))

    def test_the_two_exams_are_described_where_a_client_can_show_them(self):
        two = ending.TWO_EXAMS
        self.assertEqual(two["measurement"]["keys_required"], 0)
        self.assertFalse(two["measurement"]["plays_the_ending"])
        self.assertEqual(two["climax"]["keys_required"],
                         world.PORTAL_KEY_REQUIREMENT)
        self.assertTrue(two["climax"]["plays_the_ending"])

    # -- 2. the pass ------------------------------------------------------

    def test_a_staged_pass_frees_everybody_and_plays_the_whole_ending(self):
        state = self._save(bosses=self._all_bosses()[:1])
        staged = ending.stage(state, exam_id="x-1",
                              cleared_bosses=self._all_bosses())
        self.assertTrue(staged["staged"])
        _, report = self._report(solved=99)
        report["exam_id"] = "x-1"
        out = ending.resolve(state, exam_report=report,
                             cleared_bosses=self._all_bosses())

        self.assertEqual(out["outcome"], "PASS")
        self.assertTrue(out["world_changed"])
        self.assertEqual(captives.still_held(state), [])
        self.assertEqual(len(captives.freed(state)) + len(captives.released(state)),
                         captives.total())

        scene = out["cutscene"]
        self.assertEqual(finale.validate(scene), [])
        ids = [beat["id"] for beat in scene["beats"]]
        # The order the brief asks for, and the coda after the triumph.
        for earlier, later in (("the_king_breaks", "the_index_fails"),
                               ("the_index_fails", "roll_call"),
                               ("roll_call", "freeze"),
                               ("freeze", "the_sunglasses"),
                               ("the_sunglasses", "the_readiness_line"),
                               ("the_readiness_line", "the_world_is_not_restored")):
            self.assertLess(ids.index(earlier), ids.index(later),
                            "%s must come before %s" % (earlier, later))
        self.assertEqual(ids[-1], "the_prompt_stays")
        # The freeze, the card and the guitar hit are one millisecond.
        self.assertEqual(scene["freeze_at_ms"], scene["guitar_hit_at_ms"])
        self.assertEqual(scene["freeze_at_ms"], scene["title_card_at_ms"])

    def test_a_pass_closes_the_sweep_and_gives_everybody_back(self):
        """THE ONLY CALL THE LAST FIGHT HAS TO MAKE, and until this it had no
        production caller anywhere in `gauntlet/`.

        `liberate()` empties the index. It sets neither `final_release` nor
        clears `retaken`, so at the credits every companion the Examiner
        went back for after the second-to-last rung still read RETAKEN, their
        boons stayed suspended for ever, and the one reversal the suspension
        was allowed to cost anything for never happened. The finale's whole
        weight is in watching the roll call shorten and then come back; a roll
        call that never came back spent that weight on nothing.
        """
        from gauntlet import zonecompanions as zc

        # Get everybody the arc can get, then let the sweep take them.
        state = self._save(bosses=[row.boss for row in zc.ESCORTS])
        state["cleared_bosses"] = self._all_bosses()[:13]
        state["dungeons_cleared"] = []
        state["inventory"] = []
        state["world"] = {"routes_walked": []}
        zc.advance(state)

        taken = list(state[captives.STATE_KEY]["retaken"])
        self.assertTrue(taken, "the sweep never fired, so this proves nothing")
        for eid in taken:
            self.assertEqual(zc.state_of(state, eid), zc.RETAKEN)
        suspended = captives.boon_effects(state)

        ending.stage(state, exam_id="x-sweep",
                     cleared_bosses=self._all_bosses())
        _, report = self._report(solved=99)
        report["exam_id"] = "x-sweep"
        out = ending.resolve(state, exam_report=report,
                             cleared_bosses=self._all_bosses())
        self.assertEqual(out["outcome"], "PASS")

        raw = state[captives.STATE_KEY]
        self.assertTrue(raw["final_release"])
        self.assertEqual(raw["retaken"], [])
        self.assertEqual(sorted(out["given_back"]), sorted(taken))
        for eid in taken:
            self.assertEqual(zc.state_of(state, eid), zc.FREED, eid)

        # Every suspended boon is back on, including the two the sweep cost.
        restored = captives.boon_effects(state)
        self.assertEqual(restored.get("mana_regen"), 1)
        self.assertTrue(restored.get("srs_preview"))
        for key in suspended:
            self.assertIn(key, restored)
        banked = {b["id"] for b in captives.boons(state)}
        self.assertIn("lamps_both_ends", banked)
        self.assertIn("the_square_drill", banked)

        # And the finale stands nobody struck through behind the player: the
        # release has to happen BEFORE the roll call is read into the scene.
        roll = out["cutscene"]["roll_call"]
        self.assertEqual([r["id"] for r in roll["rows"] if r.get("retaken")], [])

    def test_a_pass_says_the_readiness_line_from_measured_numbers(self):
        state = self._save(bosses=self._all_bosses())
        ending.stage(state, exam_id="x-2", cleared_bosses=self._all_bosses())
        _, report = self._report(solved=99)
        report["exam_id"] = "x-2"
        out = ending.resolve(state, exam_report=report)
        send_off = out["cutscene"]["send_off"]
        self.assertEqual(send_off["code"], "READY")
        text = " ".join(send_off["lines"])
        self.assertIn("met the standard for this timed Python practical", text)
        self.assertIn("%s of %s" % (report["solved"], report["total"]), text)

    # -- 3. the failure ---------------------------------------------------

    def test_a_staged_failure_holds_everybody_and_costs_nothing(self):
        for solved in (0, 1, 4):
            with self.subTest(solved=solved):
                state = self._save(bosses=self._all_bosses()[:3])
                ending.stage(state, exam_id="x-3",
                             cleared_bosses=self._all_bosses())
                _, report = self._report(solved=solved)
                report["exam_id"] = "x-3"
                held_before = len(captives.still_held(state))
                out = ending.resolve(state, exam_report=report)

                self.assertEqual(out["outcome"], "FAIL")
                self.assertEqual(out["captives_freed_now"], 0)
                self.assertEqual(captives.released(state), [])
                self.assertEqual(len(captives.still_held(state)), held_before)
                self.assertFalse(captives.index_collapsed(state))
                self.assertFalse(out["world_changed"])

                scene = out["cutscene"]
                self.assertEqual(ending.validate_scene(scene), [])
                again = out["rematch"]
                self.assertTrue(again["may_sit_again_now"])
                self.assertTrue(again["portal_stays_open"])
                self.assertEqual(again["cooldown_ms"], 0)
                self.assertEqual(again["consumes"], [])
                self.assertEqual(again["keys_lost"], 0)
                self.assertTrue(again["recomposes"])
                self.assertEqual(scene["blocks"], [])
                # No end card for a loss.
                self.assertIsNone(scene["title_card"])
                self.assertIsNone(scene["guitar_hit"])

    def test_a_failure_can_be_followed_by_a_pass(self):
        state = self._save(bosses=self._all_bosses())
        ending.stage(state, exam_id="x-4", cleared_bosses=self._all_bosses())
        _, bad = self._report(solved=1)
        bad["exam_id"] = "x-4"
        self.assertEqual(ending.resolve(state, exam_report=bad)["outcome"], "FAIL")
        # Come straight back. Nothing had to be re-earned.
        ending.stage(state, exam_id="x-5", cleared_bosses=self._all_bosses())
        _, good = self._report(solved=99, seed=31)
        good["exam_id"] = "x-5"
        out = ending.resolve(state, exam_report=good)
        self.assertEqual(out["outcome"], "PASS")
        self.assertEqual(captives.still_held(state), [])
        self.assertEqual(state[ending.STATE_KEY]["attempts"], 2)
        self.assertEqual(state[ending.STATE_KEY]["failures"], 1)

    # -- 4. he names, he does not teach -----------------------------------

    def test_the_king_never_says_what_to_do_about_it(self):
        scenes = []
        state = self._save(bosses=self._all_bosses())
        ending.stage(state, exam_id="x-6", cleared_bosses=self._all_bosses())
        _, report = self._report(solved=1)
        report["exam_id"] = "x-6"
        scenes.append(ending.resolve(state, exam_report=report)["cutscene"])
        scenes.append(finale.cutscene(exam_report=report))

        for scene in scenes:
            lines = " ".join(self._king_lines(scene)).lower()
            self.assertTrue(lines, "the King has nothing to say in this scene")
            for word in finale._TEACHING_WORDS:
                self.assertNotIn(word, lines)
            # And no drill's remediation half reaches him.
            for drill in report["drills"]:
                self.assertNotIn(str(drill.get("do", "")).lower(), lines)

    def test_he_may_name_what_failed(self):
        """The other half of the rule: restraint is not silence."""
        _, report = self._report(solved=1)
        scene = ending.rematch(exam_report=report, still_held=9)
        lines = " ".join(self._king_lines(scene))
        named = [d["skill"] for d in report["drills"][:3] if d.get("skill")]
        self.assertTrue(any(skill in lines for skill in named), named)

    # -- 5. the two lists -------------------------------------------------

    def test_the_two_lists_are_never_added_together(self):
        for carried in (0, 1, 6, len(captives.CAPTIVES)):
            with self.subTest(carried=carried):
                state = {}
                for boss_id in list(captives.HOLDINGS):
                    if len(captives.freed(state)) >= carried:
                        break
                    captives.free(state, boss_id)
                release = captives.liberate(state, passed=True)
                scene = finale.cutscene(
                    freed=captives.roll_call(state),
                    released=release["released"],
                    collapse_lines=captives.INDEX_COLLAPSE,
                    total_captives=captives.total())
                self.assertEqual(finale.validate(scene), [])
                roll = scene["roll_call"]
                self.assertEqual(roll["count"], len(captives.freed(state)))
                self.assertEqual(roll["released_count"],
                                 len(captives.released(state)))
                self.assertEqual(roll["out_total"], captives.total())
                carried_ids = {row["id"] for row in roll["rows"]}
                for row in roll["released"]:
                    self.assertNotIn(row["id"], carried_ids)
                if not roll["count"]:
                    self.assertNotIn("FREED", scene["title_card"]["ribbon"])

    def test_everyone_the_player_did_not_free_says_so_in_their_own_words(self):
        state = {}
        release = captives.liberate(state, passed=True)
        self.assertEqual(len(release["released"]), captives.total())
        for row in release["released"]:
            self.assertTrue(row["released_line"], row["id"])
            low = row["released_line"].lower()
            self.assertTrue("nobody" in low or "no one" in low, row["id"])
        scene = finale.cutscene(freed=(), released=release["released"],
                                total_captives=captives.total())
        beat = next(b for b in scene["beats"]
                    if b["id"] == "the_ones_nobody_came_for")
        read = len(scene["roll_call"]["released_spoken"]) + \
            len(scene["roll_call"]["released_scrolled"])
        self.assertEqual(read, captives.total())
        self.assertFalse(beat["skippable"])

    # -- 6. the gate runs one way ----------------------------------------

    def test_nothing_here_gates_the_practical(self):
        shut = ending.can_stage([])
        self.assertFalse(shut["open"])
        self.assertFalse(shut["blocks_the_practical"])
        # And the exam composes and grades with no keys, no captives and no
        # ending state whatsoever.
        exam, report = self._report(solved=99)
        self.assertEqual(report["verdict"]["code"], "READY")
        self.assertTrue(exam.questions)
        self.assertFalse(world.portal_gates("practical"))
        self.assertFalse(world.portal_gates("interview"))

    def test_nothing_here_works_inside_a_measured_run(self):
        class Enc:
            mode = config.MODE_INTERVIEW
            boss_id = ""
            holdout = False

        refused = ending.resolve({}, exam_report={"exam_id": "x"},
                                 encounter=Enc())
        self.assertEqual(refused.get("error"), "sealed")
        self.assertNotIn("cutscene", refused)
        self.assertFalse(captives.available_in(config.MODE_INTERVIEW))

    def test_the_modules_check_themselves(self):
        report = ending.self_check()
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(captives.validate(), [])
        self.assertTrue(finale.self_check()["ok"])


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
