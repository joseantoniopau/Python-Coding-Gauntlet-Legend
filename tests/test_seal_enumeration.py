"""THE SEAL, BY ENUMERATION.

The other seal tests each walk one door and prove it locked. This file assumes
that is not enough. A hold-out that leaks does not leak through the door someone
thought to test; it leaks through the twelfth caller of a selector, added six
months later, that filtered `self.corpus` instead of `self.teachable`.

So this is a census rather than an inspection. Every surface that can name a
problem is called, many thousands of times between them, and every payload is
scanned WHOLE — every string anywhere in the returned JSON is checked against
the set of sealed ids, not just the field that happens to be called
`problem_id`. A leak in a quest objective, a remediation suggestion, a codex
entry, a dungeon room map or a shrine payload is a leak, and naming a sealed id
anywhere in a teaching payload is already the end of the measurement: an id is
enough to look it up.

Two things are deliberately NOT here, because they are the measurement itself:
Interview Mode and the final practical. A sealed id is supposed to come back
from those. Everything else in the game is on trial.
"""
from base import GameTest  # noqa: E402

import json
import random
import urllib.error
import urllib.request

from gauntlet import config, dungeons, finalexam, puzzles, world
from gauntlet import corpus as corpusmod
from gauntlet import srs as srsmod


def _walk_strings(value, out: list) -> list:
    """Every string anywhere in a JSON-shaped payload, keys included. Keys
    count: `dungeon_map` is {room id: problem id} in one direction and there is
    no promise about which way round the next such map will be written."""
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            out.append(key)
            _walk_strings(item, out)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _walk_strings(item, out)
    return out


class SealCensus(GameTest):
    """A game, a scanner, and a running count of how much was actually looked at."""

    def setUp(self):
        super().setUp()
        self.game_ = self.game()
        self.sealed = {p.id for p in self.corpus if p.sealed}
        self.assertTrue(self.sealed, "there is no hold-out to leak")
        self.draws = 0
        self.leaks: list = []

    def scan(self, where: str, payload) -> None:
        """One draw. Count it, then look at everything in it."""
        self.draws += 1
        for text in _walk_strings(payload, []):
            if text in self.sealed:
                self.leaks.append(f"{where}: {text}")

    def verdict(self, *, at_least: int) -> None:
        self.assertFalse(self.leaks,
                         "the hold-out leaked into teaching surfaces:\n  "
                         + "\n  ".join(sorted(set(self.leaks))[:40]))
        self.assertGreaterEqual(self.draws, at_least,
                                "the census did not actually draw anything")
        print(f"\n    [seal census] {self._testMethodName}: "
              f"{self.draws} payloads scanned, 0 sealed ids")


# ===========================================================================
# Selection, played rather than inspected
# ===========================================================================

class TestNothingThatTeachesEverDrawsASealedProblem(SealCensus):

    def test_the_selector_under_every_profile_region_and_kind(self):
        """next_encounter is the main road. Drive it under every profile, every
        region, every encounter kind and every armor tag, clearing and failing
        in turn so that remediation, the training camp and the retest branch all
        get their turn at choosing."""
        game = self.game_
        kinds = sorted({p.encounter_kind for p in self.corpus if p.encounter_kind})
        kinds.append(None)
        regions = [r["id"] for r in world.REGIONS] + [None]
        profiles = ["BALANCED", "FAANG", "STARTUP", "DATA", "BACKEND"]
        rng = random.Random(20260911)
        for round_no in range(600):
            if round_no % 50 == 0:
                try:
                    game.set_profile(profiles[(round_no // 50) % len(profiles)])
                except Exception:            # an unknown profile is not the point
                    pass
            payload = game.next_encounter(
                region=rng.choice(regions),
                kind=rng.choice(kinds) if round_no % 3 == 0 else None,
                armor_piece=rng.choice(["", "helm", "chest", "boots"]))
            self.scan("next_encounter", payload)
            enc = payload.get("encounter") or {}
            problem_id = enc.get("problem_id")
            if not problem_id:
                continue
            problem = game.by_id.get(problem_id)
            if problem is None or problem.entry.get("kind") != "function":
                continue
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                continue
            # Alternate: a clear advances the curriculum and the schedule, a
            # failure opens remediation. Both hand back further problem ids.
            code = (problem.canonical_solution if round_no % 2
                    else "def __not_it():\n    return None\n")
            self.scan("submit", game.submit(code))
        self.verdict(at_least=700)

    def test_the_review_schedule_after_every_family_falls_due(self):
        """The retest branch is exempt from the curriculum gate, which makes it
        the branch most likely to reach past the wall. Every family in the
        corpus is made overdue at once and then drained."""
        game = self.game_
        schedule = game.schedule
        for family in {p.spaced_repetition_family for p in self.corpus}:
            if family:
                schedule[family] = srsmod.ScheduleEntry(
                    family=family, stage=2, due_at=0.0, reviews=3, ease=1.4)
        game._write_schedule(schedule)
        for _ in range(250):
            payload = game.next_encounter()
            self.scan("retest", payload)
            problem_id = (payload.get("encounter") or {}).get("problem_id")
            problem = game.by_id.get(problem_id) if problem_id else None
            if problem and problem.entry.get("kind") == "function" \
                    and problem.encounter_kind not in puzzles.PUZZLE_KINDS:
                self.scan("retest-submit", game.submit(problem.canonical_solution))
        self.verdict(at_least=250)

    def test_daily_quests_across_a_year_of_days(self):
        """The daily board is regenerated per day from its own selector, so one
        day's board proves nothing about the selector's tail."""
        game = self.game_
        from gauntlet import adaptive
        for day in range(365):
            game.state["daily"] = {"date": f"1970-01-{(day % 28) + 1:02d}",
                                   "completed": [], "quests": []}
            game._refresh_daily(game.skills, game.schedule)
            self.scan("daily", game.state["daily"])
            self.scan("daily_direct", adaptive.daily_quests(
                skills=game.skills, schedule=game.schedule,
                corpus=game.teachable, profile=game.state["player"]["profile"]))
        self.verdict(at_least=700)

    def test_every_dungeon_room_under_many_worlds(self):
        """Room contents are seeded off the world, so one world's dungeons are
        one sample. Forty worlds, every dungeon in each, every room."""
        game = self.game_
        for seed in range(1, 41):
            game._reseed_world(seed)
            for dungeon_id in dungeons.DUNGEON_BY_ID:
                state = game.enter_dungeon(dungeon_id)
                self.scan("enter_dungeon", state)
                if state.get("error"):
                    continue
                self.scan("dungeon_map",
                          game.state["dungeon_map"].get(dungeon_id) or {})
                self.scan("dungeon_state", game.dungeon_state())
                game.leave_dungeon()
            self.scan("dungeon_list", game.dungeon_list())
        self.verdict(at_least=400)

    def test_every_boss_every_ladder_rung_and_every_rematch_tier(self):
        game = self.game_
        for seed in range(1, 11):
            game._reseed_world(seed)
            for boss in world.BOSSES:
                self.scan("boss", boss)
                self.scan("ladder", game.boss_ladder(boss["id"]))
                for tier in range(12):
                    self.scan("rematch", game._rematch_problem(boss, tier))
            self.scan("exam_ladder", game.exam_ladder())
        self.verdict(at_least=600)

    def test_shrines_secrets_quests_repos_and_incantations(self):
        game = self.game_
        for seed in range(1, 21):
            game._reseed_world(seed)
            self.scan("shrine", game.shrine())
            self.scan("world_map", game.world_map())
            self.scan("things_to_do", game.things_to_do())
            self.scan("quest_board", game.quest_board())
            self.scan("dashboard", game.dashboard())
            self.scan("minirepo_board", game.minirepo_board())
            self.scan("incantations", game.incantation_encounters())
            self.scan("loadout", game.loadout())
            self.scan("legendaries", game.legendary_catalogue())
            self.scan("transfer_report", game.transfer_report())
            for region in world.REGIONS:
                self.scan("region_view", game.region_view(region["id"]))
                self.scan("quest_board_region", game.quest_board(region["id"]))
                self.scan("dungeon_list_region", game.dungeon_list(region["id"]))
                self.scan("incant_region",
                          game.incantation_encounters(region["id"]))
                self.scan("secret_target", game.secret_target(region["id"]))
        self.verdict(at_least=500)

    def test_the_curriculum_the_codex_and_every_browsable_list(self):
        game = self.game_
        from gauntlet import curriculum
        self.scan("objective", curriculum.next_objective(game.skills))
        self.scan("ladder", curriculum.ladder(game.skills))
        self.scan("history", game.performance_history())
        self.scan("saves", game.save_slots())
        self.scan("classes", game.class_selection())
        self.scan("pets", game.pet_catalogue())
        self.scan("diagnostic", game.diagnostic_trials())
        self.scan("story", game.story_context())
        for difficulty in ("", "EASY", "MEDIUM", "HARD"):
            self.scan("repos", game.minirepo_board(difficulty=difficulty))
        # The problem browser, asked for every sealed id by name, which is the
        # deep link a curious player types into the URL bar.
        for problem_id in sorted(self.sealed):
            view = game.problem(problem_id)
            self.draws += 1
            self.assertEqual(view.get("error"), "sealed",
                             f"the browser showed sealed content: {problem_id}")
            self.assertEqual(view.get("capability"), finalexam.HOLDOUT)
        self.verdict(at_least=100)

    def test_the_encounter_door_refuses_every_sealed_id_in_every_taught_mode(self):
        """The last door, tried once per sealed problem per teaching mode, which
        is the brute-force deep link: paste the id, pick a mode, see what opens."""
        game = self.game_
        modes = [m for m in (config.MODE_ADVENTURE, "adventure", "practice",
                             "boss", "dungeon", "daily", "review", "")
                 if m != config.MODE_INTERVIEW]
        for problem_id in sorted(self.sealed):
            for mode in modes:
                refusal = game.start_encounter(problem_id, mode=mode)
                self.draws += 1
                self.assertEqual(refusal.get("error"), "sealed",
                                 f"{mode} opened sealed content: {problem_id}")
                self.assertIsNone(game.state["encounter"],
                                  "a refused sealed problem still became the "
                                  "live encounter")
        # And not one of those refusals spent anything: nothing was shown.
        self.assertEqual(game.transfer_report()["served"], 0,
                         "refusing to serve a sealed problem spent it anyway")
        self.verdict(at_least=len(self.sealed) * len(modes))


    def test_a_measured_run_never_names_a_question_before_it_serves_it(self):
        """The roster, which is the leak that is not a selector.

        Interview Mode reaches for the hold-out FIRST, so the list of problem
        ids a run is composed from is a list of sealed ids — and a hold-out
        problem is spent when it is SERVED, not when it is composed. A roster
        handed over at the start of a run was therefore a free look: read the
        sealed ids and titles, abandon the run, spend nothing, go and read about
        them, and come back to be measured on problems chosen precisely because
        they had never been seen.

        A hundred runs are started and thrown away here. Not one may name a
        sealed problem, in the start payload or on any poll of the dashboard
        while the run is open — and not one may spend anything either, because
        a roster the player never saw must not cost them the measurement.
        """
        game = self.game_
        for round_no in range(100):
            game.state["interview"] = None
            started = game.start_interview(
                "GAUNTLET" if round_no % 2 else "LIVE_SCREEN")
            if started.get("error"):
                continue
            self.scan("start_interview", started)
            self.scan("dashboard-mid-run", game.dashboard())
            self.assertNotIn("problem_ids", started["run"],
                             "the run handed over its roster")
            for entry in started.get("problems") or []:
                self.assertNotIn("id", entry)
                self.assertNotIn("title", entry)
            game.state["interview"] = None          # abandoned, nothing served
        self.assertEqual(game.transfer_report()["served"], 0,
                         "composing a run spent the hold-out without serving it")
        self.verdict(at_least=200)

    def test_the_final_practical_never_names_a_question_before_it_serves_it(self):
        """The same rule for the exam, which composes from the whole corpus and
        so reaches the hold-out the same way."""
        game = self.game_
        for _ in range(6):
            game.state["interview"] = None
            started = game.start_interview("FINAL_EXAM")
            if started.get("error"):
                continue
            self.scan("start_exam", started)
            self.scan("dashboard-mid-exam", game.dashboard())
            for segment in (started.get("exam") or {}).get("segments") or []:
                for question in segment["questions"]:
                    self.assertNotIn("problem_id", question)
                    self.assertNotIn("title", question)
            game.state["interview"] = None
            game.state["exam"] = None
        self.assertEqual(game.transfer_report()["served"], 0)
        self.verdict(at_least=6)


    def test_the_debrief_never_names_a_sealed_question_it_never_asked(self):
        """End the practical the moment it opens and read the report.

        The debrief names every question so the player knows what to drill, and
        for a question that was actually sat that is exactly right and costs
        nothing. For a sealed question the run composed and never served it
        costs the lineage: the title is the exercise in four words, the run was
        abandoned, and nothing was spent. So a sealed question that was never
        put in front of the player stays anonymous — and only that one: a
        teachable question keeps its name whether it was asked or not, and so
        does a sealed question that WAS served.
        """
        game = self.game_
        # Titles that belong ONLY to sealed problems. The generator hands the
        # same title to two different exercises from one family — "Best Stretch
        # of Events" is both a minimum-subarray problem and a longest-positive-
        # run problem — so a shared title identifies nothing sealed and is not
        # evidence of a leak. The ones that are unshared are.
        teachable_titles = {p.title for p in self.corpus if not p.sealed}
        sealed_titles = {p.title for p in self.corpus
                         if p.sealed and p.title not in teachable_titles}
        found_unasked_sealed = False
        for _ in range(12):
            game.state["interview"] = None
            game.state["exam"] = None
            started = game.start_interview("FINAL_EXAM")
            if started.get("error"):
                continue
            roster = list(game.state["interview"]["problem_ids"])
            report = game.finish_interview()          # answered nothing
            self.scan("exam-debrief", report)
            rows = (report.get("debrief") or {}).get("questions") or []
            for position, row in enumerate(rows):
                if position < len(roster) and roster[position] in self.sealed:
                    found_unasked_sealed = True
                    self.assertTrue(row["unseen"], roster[position])
                    self.assertNotIn(row["title"], sealed_titles)
                    self.assertFalse(row["pattern"])
                else:
                    # Nothing teachable is redacted: the debrief is still a
                    # debrief.
                    self.assertFalse(row["unseen"])
            for text in _walk_strings(rows, []):
                if text in sealed_titles:
                    self.leaks.append(f"exam debrief named sealed title {text!r}")
        self.assertTrue(found_unasked_sealed,
                        "no exam composed an unasked sealed question, so this "
                        "test proved nothing")
        self.assertEqual(game.transfer_report()["served"], 0)
        self.verdict(at_least=1)

    def test_a_sealed_question_that_was_actually_sat_keeps_its_name(self):
        """The other half, so the redaction cannot quietly grow into a debrief
        that tells the player nothing. Once it has been served it is spent, and
        knowing what it was is the whole value of the report."""
        game = self.game_
        roster = []
        for _ in range(12):
            game.state["interview"] = None
            game.state["exam"] = None
            started = game.start_interview("FINAL_EXAM")
            if started.get("error"):
                continue
            roster = list(game.state["interview"]["problem_ids"])
            if any(pid in self.sealed for pid in roster):
                break
        self.assertTrue(any(pid in self.sealed for pid in roster),
                        "no exam drew a sealed question")
        index = next(i for i, pid in enumerate(roster) if pid in self.sealed)
        game.state["interview"]["index"] = index
        current = game.interview_current()
        problem = game.by_id[current["problem"]["id"]]
        # Which question the exam drew as its sealed one is luck, and when it
        # draws the LAST one this test used to fail — roughly one run in three.
        # Advancing past the final question finishes the exam, and
        # finish_interview() clears state["interview"] AND state["exam"], so a
        # debrief rebuilt afterwards has no payload to rebuild from and comes
        # back None. The debrief is not lost, though: the finish returns it. So
        # hold the results list before advancing, and then take the debrief from
        # whichever of the two places actually has it.
        results = game.state["interview"]["results"]
        advanced = game.interview_advance(game.submit(problem.canonical_solution))
        debrief = advanced.get("debrief") or game._exam_debrief(results, {})
        rows = (debrief or {}).get("questions") or []
        self.assertTrue(rows, "the exam produced no per-question debrief")
        self.assertFalse(rows[index]["unseen"],
                         "a sealed question that was sat was redacted anyway")
        self.assertEqual(rows[index]["title"], problem.title)
        self.draws += 1
        self.verdict(at_least=1)


# ===========================================================================
# The same census, over HTTP
# ===========================================================================

class TestNoEndpointEverReturnsASealedId(SealCensus):
    """The engine is one caller of itself. The client is the other, and it goes
    through a different dispatcher with different defaults."""

    def setUp(self):
        super().setUp()
        from gauntlet import server
        self.server = server
        server.set_game(self.game_)
        self.httpd, _ = server.serve()
        self.addCleanup(server.set_game, None)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def hit(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "X-Gauntlet-Token": self.server.TOKEN})
        try:
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return json.loads(raw or b"null")
            except ValueError:
                return {"error": raw.decode("utf-8", "replace")}

    GETS = ("/api/state", "/api/world", "/api/shrine", "/api/history",
            "/api/curriculum", "/api/story", "/api/loadout", "/api/transfer",
            "/api/probes", "/api/repos", "/api/repo", "/api/ping",
            "/api/diagnostic", "/api/interview/current", "/api/world-map",
            "/api/dungeons", "/api/quests", "/api/classes", "/api/pets",
            "/api/legendaries", "/api/chains", "/api/todo", "/api/events",
            "/api/routes", "/api/saves", "/api/hand", "/api/incantation",
            "/api/exam/ladder", "/api/world/card")

    def test_every_get_endpoint_across_many_worlds(self):
        for seed in range(1, 16):
            self.game_._reseed_world(seed)
            for path in self.GETS:
                self.scan(path, self.hit("GET", path))
            for region in world.REGIONS:
                self.scan("/api/region", self.hit(
                    "GET", f"/api/region?id={region['id']}"))
        self.verdict(at_least=len(self.GETS) * 15)

    def test_the_problem_endpoint_refuses_every_sealed_id(self):
        """The deep link, over the wire, in every mode the query string
        accepts. `mode=interview` on this endpoint must not be a way to read
        hold-out content at leisure outside a measured run."""
        for problem_id in sorted(self.sealed):
            for mode in ("", "adventure", "interview", "practice", "boss"):
                suffix = f"&mode={mode}" if mode else ""
                payload = self.hit("GET", f"/api/problem?id={problem_id}{suffix}")
                self.draws += 1
                self.assertEqual(payload.get("error"), "sealed",
                                 f"/api/problem?id={problem_id}&mode={mode} "
                                 "returned hold-out content")
        self.verdict(at_least=len(self.sealed) * 5)

    def test_the_encounter_endpoints_over_http(self):
        for _ in range(120):
            payload = self.hit("POST", "/api/encounter/next", {})
            self.scan("/api/encounter/next", payload)
            problem_id = (payload.get("encounter") or {}).get("problem_id")
            if not problem_id:
                continue
            problem = self.game_.by_id.get(problem_id)
            if problem and problem.entry.get("kind") == "function" \
                    and problem.encounter_kind not in puzzles.PUZZLE_KINDS:
                self.scan("/api/submit", self.hit(
                    "POST", "/api/submit", {"code": problem.canonical_solution}))
        for problem_id in sorted(self.sealed)[:40]:
            payload = self.hit("POST", "/api/encounter/start",
                               {"problem_id": problem_id})
            self.draws += 1
            self.assertEqual(payload.get("error"), "sealed",
                             f"/api/encounter/start opened {problem_id}")
        self.verdict(at_least=160)


# ===========================================================================
# The corpus invariant the whole census rests on
# ===========================================================================

class TestTheWallItself(SealCensus):

    def test_the_teachable_list_and_the_hold_out_do_not_overlap(self):
        game = self.game_
        self.assertEqual(len(game.teachable) + len(game.holdout), len(game.corpus))
        self.assertFalse({p.id for p in game.teachable} & self.sealed)
        self.assertEqual({p.id for p in game.holdout}, self.sealed)
        self.draws += 1
        self.verdict(at_least=1)

    def test_no_teachable_problem_names_a_sealed_id_anywhere(self):
        """The leak this census actually found. `prerequisites` and `variants`
        are lists of problem ids, `player_view` ships both in Adventure Mode,
        and 28 teachable problems were naming sealed ids into 27 of the 97
        hold-out lineages. An id is enough to look the exercise up, and a
        looked-up exercise is not one you meet cold.

        Every player-visible field of every teachable problem, against the
        sealed set. Checked over the whole record rather than over the two
        fields that were wrong, so the next field to hold an id is caught too.
        """
        sealed_ids = self.sealed
        for problem in self.corpus:
            if problem.sealed:
                continue
            view = problem.player_view(mode=config.MODE_ADVENTURE)
            self.draws += 1
            for text in _walk_strings(view, []):
                if text in sealed_ids and text != problem.id:
                    self.leaks.append(f"{problem.id} player_view names {text}")
        self.verdict(at_least=len(self.corpus) - len(self.sealed))

    def test_no_sealed_lineage_has_a_teachable_sibling(self):
        """The invariant that makes `first_encounter` mean anything. If a sealed
        problem had a teachable sibling, Adventure Mode could teach the exercise
        and the measurement would still call it cold."""
        index = corpusmod.lineage_index(self.corpus)
        for lineage, group in index.items():
            flags = {p.sealed for p in group}
            self.assertEqual(len(flags), 1,
                             f"lineage {lineage} is half sealed and half taught")
        self.draws += len(index)
        self.verdict(at_least=1)
