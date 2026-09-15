"""The hold-out, and the second number it exists to produce.

Everything here is played rather than read. The claims under test are about what
a running Game does — what it serves, what it refuses, what it counts — and a
test that asserts the source code says the right thing proves only that somebody
typed it. So each test below starts a real Game against the real corpus and
drives it through the same doors the client does.

Two separate things are being proved.

  THE SEAL. Hold-out content is unreachable from every teaching path: adaptive
  selection, the review schedule, dungeons, bosses, hints, the coach, the worked
  solution, and every browsable list. One refusal, routed through
  finalexam.sealed()/refuse(), because a second isolation mechanism is how the
  first one quietly stops being true.

  THE NUMBER. Transfer readiness moves only on sealed, zero-assistance, first-
  of-its-lineage clears; a second sibling is not independent evidence; and a
  sample too small to support a percentage does not get one.
"""
from base import GameTest  # noqa: E402

import json
import time

from gauntlet import config, dungeons, finalexam, puzzles, transfer, world
from gauntlet import corpus as corpusmod
from gauntlet import srs as srsmod


def _strings(value, out: list) -> list:
    """Every string anywhere in a JSON-shaped payload."""
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            out.append(key)
            _strings(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _strings(item, out)
    return out


class TransferTest(GameTest):
    """Shared scaffolding: a game, and a supply of cold problems to measure on."""

    def sealed_ids(self) -> set:
        return {p.id for p in self.corpus if p.sealed}

    def cold(self, game, count: int, *, difficulty=("GUIDED", "TUTORIAL", "EASY")):
        """`count` hold-out problems from `count` different lineages, each one
        gradable by submitting its canonical solution."""
        chosen, lineages = [], set()
        for problem in sorted(game.holdout, key=lambda p: p.id):
            if problem.lineage_id in lineages:
                continue
            if problem.entry.get("kind") != "function":
                continue
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                continue
            if problem.difficulty not in difficulty:
                continue
            lineages.add(problem.lineage_id)
            chosen.append(problem)
            if len(chosen) == count:
                break
        self.assertEqual(len(chosen), count, "the hold-out cannot supply the test")
        return chosen

    def other_game(self):
        """A second, independent save. base.GameTest.game() always opens the
        same file, and an import test needs somewhere empty to import into."""
        from gauntlet.engine import Game
        return Game(db_path=self.data_dir / "other.sqlite3",
                    corpus_path=self.corpus_path)

    def measure(self, game, problem, code=None):
        """Serve one hold-out problem in a measured run and answer it. This is
        the same pair of calls interview_current/submit make."""
        payload = game.start_encounter(problem.id, mode=config.MODE_INTERVIEW)
        self.assertNotIn("error", payload, problem.id)
        return game.submit(problem.canonical_solution if code is None else code)


# ===========================================================================
# The seal
# ===========================================================================

class TestTheSealHolds(TransferTest):

    def test_adventure_mode_never_serves_hold_out_content(self):
        """The headline claim. A hundred and twenty encounters of ordinary play,
        including the failures that route to remediation, and not one of them is
        allowed to be a problem the measurement depends on being unseen."""
        game = self.game()
        sealed = self.sealed_ids()
        served = []
        for index in range(120):
            payload = game.next_encounter()
            problem_id = payload["encounter"]["problem_id"]
            served.append(problem_id)
            self.assertNotIn(problem_id, sealed,
                             f"adventure selection served hold-out content: {problem_id}")
            problem = game.by_id[problem_id]
            # Alternate clearing and failing: failure is what opens the
            # remediation and training-camp paths, which hand back problem ids
            # of their own.
            if index % 2:
                result = game.submit(problem.canonical_solution)
            else:
                result = game.submit("def __nope():\n    return None\n")
                for key in ("immediate", "next", "delayed"):
                    named = (result.get("remediation") or {}).get(key)
                    if named:
                        self.assertNotIn(named["id"], sealed,
                                         f"remediation named hold-out content: {named}")
        self.assertGreater(len(set(served)), 20, "the selector stopped exploring")

    def test_every_door_into_an_encounter_refuses_hold_out_content(self):
        """Selection is filtered, and the door is locked anyway. A guarantee
        that depends on every caller getting it right is not a guarantee."""
        game = self.game()
        problem = game.holdout[0]
        refusal = game.start_encounter(problem.id)
        self.assertEqual(refusal["error"], "sealed")
        self.assertEqual(refusal["capability"], finalexam.HOLDOUT)
        self.assertIsNone(game.state["encounter"])
        # And it is not spent by being refused — nothing was shown.
        self.assertEqual(game.transfer_report()["served"], 0)

    def test_the_browsable_problem_door_refuses_hold_out_content(self):
        game = self.game()
        self.assertEqual(game.problem(game.holdout[0].id)["error"], "sealed")
        self.assertEqual(game.problem(game.teachable[0].id)["id"],
                         game.teachable[0].id)

    def test_no_dungeon_room_is_filled_with_hold_out_content(self):
        game = self.game()
        sealed = self.sealed_ids()
        entered = 0
        for dungeon_id in dungeons.DUNGEON_BY_ID:
            state = game.enter_dungeon(dungeon_id)
            if state.get("error"):
                continue
            entered += 1
            for problem_id in (game.state["dungeon_map"].get(dungeon_id) or {}).values():
                self.assertNotIn(problem_id, sealed,
                                 f"{dungeon_id} put hold-out content in a room")
            game.leave_dungeon()
        self.assertGreater(entered, 0, "no dungeon could be entered at all")

    def test_no_boss_and_no_boss_ladder_points_at_hold_out_content(self):
        game = self.game()
        sealed = self.sealed_ids()
        for boss in world.BOSSES:
            self.assertNotIn(boss["problem_id"], sealed, boss["id"])
            for rung in game.boss_ladder(boss["id"]).get("ladder", []):
                self.assertNotIn(rung["id"], sealed, boss["id"])
            for tier in range(6):
                self.assertNotIn(game._rematch_problem(boss, tier), sealed, boss["id"])

    def test_the_review_schedule_never_serves_hold_out_content(self):
        """Every family in the corpus made overdue at once, so the retest branch
        of the selector runs on every pass. It is the one branch that is exempt
        from the curriculum gate, which makes it the most likely leak."""
        game = self.game()
        sealed = self.sealed_ids()
        families = sorted({p.spaced_repetition_family for p in game.holdout
                           if p.spaced_repetition_family})
        self.assertGreater(len(families), 5, "the hold-out shares no family at all")
        overdue = time.time() - 30 * 86400
        game.state["schedule"] = {
            family: srsmod.ScheduleEntry(family=family, stage=2, reviews=3,
                                         due_at=overdue,
                                         last_reviewed=overdue).to_dict()
            for family in families}
        game.save()
        retests = 0
        for _ in range(60):
            payload = game.next_encounter()
            problem_id = payload["encounter"]["problem_id"]
            self.assertNotIn(problem_id, sealed,
                             f"the schedule served hold-out content: {problem_id}")
            retests += payload["reason"] == "RETEST"
            game.submit(game.by_id[problem_id].canonical_solution)
        self.assertGreater(retests, 0, "no retest was served, so nothing was proved")

    def test_a_sealed_clear_never_enters_or_advances_the_schedule(self):
        """The SRS may not schedule one and may not schedule FROM one. A sealed
        clear that advanced its family's stage would be the hold-out teaching
        through the back door on its own way out."""
        game = self.game()
        problem = self.cold(game, 1)[0]
        family = problem.spaced_repetition_family or problem.pattern.lower()
        before = json.dumps(game.state["schedule"], sort_keys=True)
        result = self.measure(game, problem)
        self.assertTrue(result["solved"])
        self.assertEqual(json.dumps(game.state["schedule"], sort_keys=True), before)
        self.assertNotIn(family, game.state["schedule"])
        self.assertEqual(result["next_retest_days"], 0.0)

    def test_hints_probes_the_coach_and_the_solution_all_refuse(self):
        game = self.game()
        problem = self.cold(game, 1)[0]
        payload = game.start_encounter(problem.id, mode=config.MODE_INTERVIEW)

        self.assertEqual(payload["problem"]["hint_tree"], [])
        self.assertEqual(payload["hint_count"], 0)
        self.assertEqual(payload["problem"]["pattern"], "REDACTED")
        self.assertEqual(payload["problem"]["visualization"], {})
        self.assertEqual(payload["enemy"]["weaknesses"], [])
        self.assertEqual(payload["tactics"], {})
        self.assertIsNone(payload["mentor"])
        self.assertEqual(payload["companions"], [])
        self.assertEqual(payload["probe_charges"], 0)
        self.assertNotIn("canonical_solution", payload["problem"])

        for capability in finalexam.ALL_CRUTCHES:
            self.assertTrue(finalexam.sealed(game.encounter, capability), capability)
        self.assertTrue(finalexam.sealed(game.encounter, finalexam.HOLDOUT))

        self.assertEqual(game.use_hint(1)["error"], "sealed")
        self.assertEqual(game.use_hint(5)["error"], "sealed")
        self.assertEqual(game.probe([[1, 2], 3], [0, 1])["error"], "sealed")
        self.assertEqual(game.probes_remaining(), 0)

        result = game.submit(problem.canonical_solution)
        self.assertTrue(result["solved"])
        self.assertIsNone(result["canonical_solution"])
        self.assertFalse(result["coach"]["available"])
        self.assertEqual(result["coach"]["questions"], [])
        self.assertFalse(result["coach"]["reveal_solution"])

    def test_a_failed_sealed_attempt_still_hands_back_no_solution(self):
        """The one place a worked solution is normally owed: a player stuck on
        the same problem. The hold-out owes them nothing but the result."""
        game = self.game()
        problem = self.cold(game, 1)[0]
        for _ in range(4):
            result = self.measure(game, problem, code="def __nope():\n    return 1\n")
            self.assertFalse(result["solved"])
            self.assertIsNone(result["canonical_solution"])
            self.assertFalse(result["coach"]["reveal_solution"])

    def test_the_encounter_payload_never_says_which_problems_are_sealed(self):
        """A player who can read the hold-out can study it, and a studied
        hold-out measures familiarity again."""
        game = self.game()
        problem = self.cold(game, 1)[0]
        payload = game.start_encounter(problem.id, mode=config.MODE_INTERVIEW)
        self.assertNotIn("lineage_id", payload["problem"])
        # `problem["sealed"]` is the OTHER sense of the word: exam_view stamps
        # the list of sealed CAPABILITIES onto every question, identically, and
        # it is the same list whether or not the question is hold-out content.
        # Membership of the hold-out is a boolean and it does not travel.
        self.assertEqual(payload["problem"]["sealed"],
                         sorted(finalexam.EXAM_SEAL.sealed))
        self.assertNotIsInstance(payload["problem"]["sealed"], bool)
        # What it DOES say is that this one is measured, which is the engine's
        # job to say rather than the client's to infer.
        self.assertTrue(payload["transfer"]["holdout"])
        self.assertTrue(payload["transfer"]["first_encounter"])

    def test_no_browsable_list_ever_names_hold_out_content(self):
        """The grimoire, the codex, the quest board, the world map, the daily
        quests and everything else the dashboard ships, scanned whole."""
        game = self.game()
        sealed = self.sealed_ids()
        for _ in range(12):
            payload = game.next_encounter()
            game.submit(game.by_id[payload["encounter"]["problem_id"]].canonical_solution)
        views = [game.dashboard(), game.quest_board(), game.world_map(),
                 game.dungeon_list(), game.things_to_do(), game.save_slots(),
                 game.exam_ladder(), game.legendary_catalogue(),
                 game.performance_history(), game.class_selection()]
        named = set()
        for view in views:
            named.update(_strings(view, []))
        leaked = named & sealed
        self.assertEqual(leaked, set(), f"hold-out content named in a player view: {leaked}")


# ===========================================================================
# The number
# ===========================================================================

class TestTransferReadiness(TransferTest):

    def test_a_small_sample_refuses_to_print_a_percentage(self):
        """A 100% built from two attempts is not 100%, and an interface handed
        that number will render it as one. So it is not handed one."""
        game = self.game()
        self.assertFalse(game.transfer_report()["measured"])
        for problem in self.cold(game, 3):
            self.assertTrue(self.measure(game, problem)["solved"])
        report = game.transfer_report()
        self.assertEqual(report["sample"], 3)
        self.assertEqual(report["cleared"], 3)
        self.assertFalse(report["measured"])
        self.assertIsNone(report["score"])
        self.assertNotIn("%", report["headline"])
        self.assertIn("too small a sample", report["note"])
        self.assertLess(report["sample"], transfer.MIN_SAMPLE)

    def test_a_player_who_has_sat_nothing_sealed_is_told_so_in_words(self):
        """Not 0%, which reads as "you cannot do this", and not 100%, which is
        what an empty numerator over an empty denominator becomes the moment
        anybody divides. There is no percentage anywhere in the payload."""
        report = self.game().transfer_report()
        self.assertEqual(report["sample"], 0)
        self.assertEqual(report["cleared"], 0)
        self.assertFalse(report["measured"])
        self.assertIsNone(report["score"], "an unmeasured player was given a number")
        self.assertNotIn("%", report["headline"])
        self.assertIn("not yet measurable", report["headline"])
        self.assertIn("has been attempted unaided yet", report["note"])
        self.assertEqual(report["by_skill"], [])
        # And nothing in there can be mistaken for a score by a renderer that
        # reaches for the first number it finds.
        for key in ("score", "rate"):
            self.assertIsNone(report.get(key))

    def test_the_band_is_a_real_wilson_interval_and_not_a_decoration(self):
        """Checked against the published values, because a band that is quietly
        the naive normal interval says things like "104%" and puts a zero-width
        interval around a perfect score — which is exactly the overclaim the
        band exists to prevent."""
        for cleared, sample, low, high in (
                (7, 10, 0.3968, 0.8922),
                (5, 10, 0.2366, 0.7634),
                (50, 100, 0.4038, 0.5962),
                (0, 10, 0.0000, 0.2775)):
            got_low, got_high = transfer.wilson(cleared, sample)
            self.assertAlmostEqual(got_low, low, places=3)
            self.assertAlmostEqual(got_high, high, places=3)
        # The two shapes the naive interval gets wrong.
        low, high = transfer.wilson(10, 10)
        self.assertLess(low, 1.0, "a perfect score got a zero-width band")
        self.assertLessEqual(high, 1.0, "the band claimed more than 100%")
        self.assertAlmostEqual(high, 1.0, places=6)
        low, high = transfer.wilson(0, 10)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0, "a zero score got a zero-width band")
        self.assertGreaterEqual(low, 0.0, "the band went below 0%")
        # And the band always brackets the point estimate it belongs to.
        for cleared in range(0, 13):
            low, high = transfer.wilson(cleared, 12)
            self.assertLessEqual(low, cleared / 12)
            self.assertGreaterEqual(high, cleared / 12)

    def test_a_per_skill_line_holds_itself_to_the_same_standard(self):
        """Most skills own one or two sealed lineages for the life of a save, so
        most of these lines must report counts and refuse a rate forever."""
        game = self.game()
        for problem in self.cold(game, 2):
            self.measure(game, problem)
        for entry in game.transfer_report()["by_skill"]:
            self.assertLess(entry["sample"], transfer.SKILL_MIN_SAMPLE)
            self.assertFalse(entry["measured"])
            self.assertIsNone(entry["rate"])
            self.assertNotIn("%", entry["text"])
            self.assertIn("too few", entry["text"])

    def test_the_number_arrives_with_its_sample_and_its_band(self):
        game = self.game()
        problems = self.cold(game, transfer.MIN_SAMPLE)
        for problem in problems:
            self.assertTrue(self.measure(game, problem)["solved"])
        report = game.transfer_report()
        self.assertTrue(report["measured"])
        self.assertEqual(report["sample"], transfer.MIN_SAMPLE)
        self.assertEqual(report["score"], 100)
        self.assertIn(f"n={transfer.MIN_SAMPLE}", report["headline"])
        # A perfect score out of ten is not a promise of a perfect score.
        self.assertLess(report["band"]["low"], 100)
        self.assertIn(report["band"]["text"], report["headline"])

    def test_a_failure_counts_in_the_denominator_and_not_the_numerator(self):
        """Otherwise a failed transfer attempt would vanish from its own
        denominator and the number would only ever go up."""
        game = self.game()
        problems = self.cold(game, transfer.MIN_SAMPLE + 2)
        for problem in problems[:2]:
            self.assertFalse(self.measure(
                game, problem, code="def __nope():\n    return 1\n")["solved"])
        for problem in problems[2:]:
            self.assertTrue(self.measure(game, problem)["solved"])
        report = game.transfer_report()
        self.assertEqual(report["sample"], transfer.MIN_SAMPLE + 2)
        self.assertEqual(report["cleared"], transfer.MIN_SAMPLE)
        self.assertEqual(report["score"],
                         round(100 * transfer.MIN_SAMPLE / (transfer.MIN_SAMPLE + 2)))

    def test_a_second_sibling_is_not_independent_evidence(self):
        """The whole reason lineage exists. Five siblings cleared is one
        unfamiliar problem solved five times."""
        game = self.game()
        family = None
        for lineage, group in corpusmod.lineage_index(game.holdout).items():
            usable = [p for p in group if p.entry.get("kind") == "function"
                      and p.encounter_kind not in puzzles.PUZZLE_KINDS]
            if len(usable) >= 2:
                family = usable
                break
        self.assertIsNotNone(family, "no sealed lineage has two gradable siblings")
        first, second = family[0], family[1]
        self.assertEqual(first.lineage_id, second.lineage_id)

        result = self.measure(game, first)
        self.assertTrue(result["solved"])
        self.assertTrue(result["transfer"]["counted"])
        after_first = game.transfer_report()
        self.assertEqual(after_first["sample"], 1)

        result = self.measure(game, second)
        self.assertTrue(result["solved"])
        self.assertFalse(result["transfer"]["first_encounter"])
        self.assertFalse(result["transfer"]["counted"])
        after_second = game.transfer_report()
        self.assertEqual(after_second["sample"], 1, "a sibling moved the number")
        self.assertEqual(after_second["cleared"], 1)
        self.assertEqual(after_second["served"], 2)
        self.assertEqual(after_second["repeat_lineage"], 1)
        self.assertEqual(after_second["spent_lineages"], 1)

    def test_walking_away_from_a_sealed_problem_still_spends_its_lineage(self):
        """It cannot be farmed: the lineage is gone the moment it is served,
        pass, fail or close the tab. Enforced in the ledger, not in the UI."""
        game = self.game()
        family = None
        for lineage, group in corpusmod.lineage_index(game.holdout).items():
            usable = [p for p in group if p.entry.get("kind") == "function"
                      and p.encounter_kind not in puzzles.PUZZLE_KINDS]
            if len(usable) >= 2:
                family = usable
                break
        first, second = family[0], family[1]

        game.start_encounter(first.id, mode=config.MODE_INTERVIEW)  # and nothing else
        self.assertEqual(game.transfer_report()["served"], 1)
        self.assertEqual(game.transfer_report()["resolved"], 0)

        result = self.measure(game, second)
        self.assertTrue(result["solved"])
        self.assertFalse(result["transfer"]["counted"])
        self.assertEqual(game.transfer_report()["sample"], 0)

    def test_serving_the_same_sealed_problem_twice_cannot_restore_it(self):
        game = self.game()
        problem = self.cold(game, 1)[0]
        game.start_encounter(problem.id, mode=config.MODE_INTERVIEW)
        game.start_encounter(problem.id, mode=config.MODE_INTERVIEW)
        rows = game.conn.execute(
            "SELECT problem_id, first_encounter FROM transfer_encounters").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["first_encounter"], 1)

    def test_nothing_taught_can_move_it(self):
        """Adventure clears move mastery and must not move this. Neither may a timed practical sat on teachable material, which measures performance under
        timed practical conditions and says nothing about transfer."""
        game = self.game()
        for _ in range(12):
            payload = game.next_encounter()
            game.submit(game.by_id[payload["encounter"]["problem_id"]].canonical_solution)
        self.assertEqual(game.transfer_report()["sample"], 0)

        taught = next(p for p in game.teachable
                      if p.entry.get("kind") == "function"
                      and p.encounter_kind not in puzzles.PUZZLE_KINDS
                      and p.difficulty in ("EASY", "TUTORIAL"))
        game.start_encounter(taught.id, mode=config.MODE_INTERVIEW)
        result = game.submit(taught.canonical_solution)
        self.assertTrue(result["solved"])
        self.assertNotIn("transfer", result)
        report = game.transfer_report()
        self.assertEqual(report["sample"], 0)
        self.assertEqual(report["served"], 0)
        self.assertFalse(report["measured"])

    def test_it_says_what_transferred_and_not_only_how_much(self):
        game = self.game()
        for problem in self.cold(game, transfer.MIN_SAMPLE):
            self.measure(game, problem)
        report = game.transfer_report()
        self.assertTrue(report["by_skill"])
        self.assertEqual(sum(entry["sample"] for entry in report["by_skill"]),
                         report["sample"])
        for entry in report["by_skill"]:
            self.assertLessEqual(entry["cleared"], entry["sample"])
            if entry["sample"] < transfer.SKILL_MIN_SAMPLE:
                self.assertIsNone(entry["rate"])
                self.assertFalse(entry["measured"])
                self.assertIn("too few", entry["text"])
            else:
                self.assertIsNotNone(entry["rate"])
        # Largest sample first: the order is how much each line can be believed.
        samples = [entry["sample"] for entry in report["by_skill"]]
        self.assertEqual(samples, sorted(samples, reverse=True))

    def test_transfer_and_ordinary_readiness_are_two_separate_numbers(self):
        """Neither gates the other and neither is folded into the other. One is
        a measure of familiarity with taught material; the other is not."""
        game = self.game()
        for problem in self.cold(game, transfer.MIN_SAMPLE):
            self.measure(game, problem)
        dashboard = game.dashboard()
        self.assertNotIn("transfer", dashboard["readiness"])
        self.assertNotIn("overall", dashboard["transfer"])
        self.assertNotEqual(dashboard["transfer"]["score"],
                            dashboard["readiness"]["overall"])
        # Mastery moved on the same evidence, for its own separate reason.
        self.assertGreater(max(s["mastery"] for s in dashboard["skills"]), 0)
        self.assertFalse(dashboard["readiness"]["ready"])

    def test_an_interview_really_does_produce_transfer_evidence(self):
        """The whole loop, through the doors the client uses: start a timed practical, answer what it serves, and check the ledger afterwards."""
        game = self.game()
        game.start_interview("LIVE_SCREEN")
        counted = 0
        while True:
            payload = game.interview_current()
            if payload.get("finished") or payload.get("error"):
                break
            problem = game.by_id[payload["encounter"]["problem_id"]]
            result = game.submit(problem.canonical_solution)
            counted += bool((result.get("transfer") or {}).get("counted"))
            if game.interview_advance(result).get("finished"):
                break
        self.assertGreater(counted, 0, "an interview measured nothing cold")
        report = game.transfer_report()
        self.assertEqual(report["sample"], counted)
        self.assertGreater(report["remaining"], 0)


# ===========================================================================
# Persistence
# ===========================================================================

class TestTransferSurvives(TransferTest):

    def _evidence(self, game, count=4):
        for problem in self.cold(game, count):
            self.measure(game, problem)
        return game.transfer_report()

    def test_it_survives_export_and_import(self):
        game = self.game()
        before = self._evidence(game)
        payload = game.export()
        self.assertEqual(len(payload["transfer_encounters"]), before["served"])

        fresh = self.other_game()
        self.assertEqual(fresh.transfer_report()["served"], 0)
        self.assertTrue(fresh.import_save(payload)["ok"])
        after = fresh.transfer_report()
        self.assertEqual(after["sample"], before["sample"])
        self.assertEqual(after["cleared"], before["cleared"])
        self.assertEqual(after["spent_lineages"], before["spent_lineages"])
        # And the spent lineages are still spent, so they cannot be re-measured.
        self.assertEqual(len(fresh.transfer_pool()), len(game.transfer_pool()))

    def test_a_save_slot_rollback_cannot_un_spend_the_hold_out(self):
        """The obvious attack, and the one this used to lose to.

        A save slot rewinds the game. It must not rewind the player. This test
        used to assert the opposite — that a slot load put the transfer sample
        back where it was — which is a rollback that hands the hold-out back
        unspent, and four clicks from a 100% transfer score: save, sit a sealed
        problem, fail, load, sit it again with the answer in your head.

        So the ledger ratchets. Loading an older slot may take back the XP and
        the mastery; the record of which sealed problems have already been in
        front of this player's eyes only ever grows.
        """
        game = self.game()
        before = self._evidence(game)
        slot = game.save_to_slot(1, name="before more")["slot_id"]

        extra = self.cold(game, before["served"] + 3)[before["served"]:]
        for problem in extra:
            self.measure(game, problem)
        grown = game.transfer_report()
        self.assertGreater(grown["sample"], before["sample"])
        pool_after_spending = len(game.transfer_pool())

        loaded = game.load_slot(slot)
        self.assertTrue(loaded["ok"])
        after = game.transfer_report()
        self.assertEqual(after["sample"], grown["sample"],
                         "a slot load rolled the transfer sample back")
        self.assertEqual(after["served"], grown["served"])
        self.assertEqual(len(game.transfer_pool()), pool_after_spending,
                         "a slot load handed back hold-out problems already spent")
        for problem in extra:
            self.assertIn(problem.lineage_id,
                          {r["lineage_id"] for r in game.conn.execute(
                              "SELECT lineage_id FROM transfer_encounters")})

    def test_a_rollback_cannot_launder_a_failed_sealed_attempt(self):
        """The same attack, played for the thing it is actually worth: turning
        a failure into a clear. Fail cold, roll back, answer it knowing it."""
        game = self.game()
        problem = self.cold(game, 1)[0]
        slot = game.save_to_slot(1, name="cheat point")["slot_id"]

        self.measure(game, problem, code="def wrong():\n    return None\n")
        failed = game.transfer_report()
        self.assertEqual(failed["sample"], 1)
        self.assertEqual(failed["cleared"], 0)

        self.assertTrue(game.load_slot(slot)["ok"])
        result = self.measure(game, problem)          # now with the answer
        self.assertTrue(result["solved"], "the retry should still be playable")
        self.assertFalse(result["transfer"]["counted"],
                         "a laundered retry counted toward transfer readiness")
        after = game.transfer_report()
        self.assertEqual(after["sample"], 1)
        self.assertEqual(after["cleared"], 0, "a failed cold attempt became a clear")

    def test_an_import_cannot_un_spend_the_hold_out(self):
        """Export before, fail a sealed problem, import the old file. The file
        is a rollback with more steps, and it is refused the same way."""
        game = self.game()
        problem = self.cold(game, 1)[0]
        before_file = json.loads(json.dumps(game.export()))

        self.measure(game, problem, code="def wrong():\n    return None\n")
        self.assertEqual(game.transfer_report()["sample"], 1)

        self.assertTrue(game.import_save(before_file)["ok"])
        self.assertEqual(game.transfer_report()["sample"], 1,
                         "an import rolled the hold-out ledger back")
        result = self.measure(game, problem)
        self.assertFalse(result["transfer"]["counted"])
        self.assertEqual(game.transfer_report()["cleared"], 0)

    def test_an_in_place_retry_cannot_regrade_a_sealed_problem(self):
        """No save file involved at all. Fail it, ask for it again, answer it.

        The ledger holds one row per sealed problem and it used to be UPDATEd on
        every submission, so the cheapest farm in the game was the retry button:
        every sealed problem was clearable by brute force and the number went to
        100% having measured nothing. The grading is write-once now. The retry
        still runs — nothing dead-ends — it simply is not the measurement.
        """
        game = self.game()
        problem = self.cold(game, 1)[0]
        self.measure(game, problem, code="def wrong():\n    return None\n")
        self.assertEqual(game.transfer_report()["cleared"], 0)

        for _ in range(5):
            result = self.measure(game, problem)
            self.assertTrue(result["solved"])
            self.assertFalse(result["transfer"]["counted"])
            self.assertTrue(result["transfer"]["measurement_stands"])
        after = game.transfer_report()
        self.assertEqual(after["sample"], 1)
        self.assertEqual(after["cleared"], 0, "brute force moved the number")
        self.assertEqual(after["served"], 1)

    def test_the_undo_ring_cannot_un_spend_the_hold_out(self):
        """undo_load restores the pre-load snapshot, which is a rollback by
        another name and was the third door into the same room."""
        from gauntlet import saves as savesmod
        game = self.game()
        problem = self.cold(game, 1)[0]
        slot = game.save_to_slot(1, name="a")["slot_id"]
        game.load_slot(slot)                       # banks an undo snapshot

        self.measure(game, problem, code="def wrong():\n    return None\n")
        self.assertEqual(game.transfer_report()["sample"], 1)

        self.assertTrue(savesmod.undo_available(game.conn))
        savesmod.undo_load(game.conn, current_state=game.state)
        game.state = game._load_or_create()
        self.assertEqual(game.transfer_report()["sample"], 1,
                         "undo rolled the hold-out ledger back")

    def test_an_older_save_format_still_loads(self):
        """A save written before the hold-out existed has no transfer evidence
        in it, which is the truth about it rather than an error."""
        game = self.game()
        payload = game.export()
        payload["version"] = 1
        payload.pop("transfer_encounters")
        self.assertTrue(game.import_save(payload)["ok"])
        self.assertEqual(game.transfer_report()["served"], 0)


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
