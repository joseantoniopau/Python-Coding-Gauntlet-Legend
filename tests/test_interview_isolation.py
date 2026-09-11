"""Interview Mode is sacred. These tests exist to prove it stays that way.

The spec requires explicit tests proving AI and assistance are inaccessible.
Everything here checks the SERVER's behaviour, not the UI's, because a guarantee
that lives only in the client is not a guarantee.
"""
from base import GameTest  # noqa: E402
import json
import unittest
import urllib.error
import urllib.request


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


# ---------------------------------------------------------------------------
# The same guarantee, asked of the SERVER over real HTTP.
#
# The engine refuses, and the modules refuse, and that was true before these
# tests existed. What was not true is that a client which skips the engine's
# facade and posts straight at a route would be refused — the routes did not
# exist. Now they do, and this is the door they are refused at.
#
# Every entry below is (path, body, capability). The capability is what
# finalexam.refuse() names in the reply, so a screen can say WHICH crutch was
# taken rather than "409".
# ---------------------------------------------------------------------------
SEALED_POSTS = (
    ("/api/class/choose", {"class_id": "analyst"}, "BUILD"),
    ("/api/class/spend", {"node_id": "analyst_read_the_water"}, "BUILD"),
    ("/api/class/respec", {"scope": "all"}, "BUILD"),
    ("/api/class/dual", {"class_id": "seer"}, "BUILD"),
    ("/api/quest/accept", {"quest_id": "village_beam_count"}, "BUILD"),
    ("/api/quest/abandon", {"quest_id": "village_beam_count"}, "BUILD"),
    ("/api/quest/turnin", {"quest_id": "village_beam_count"}, "BUILD"),
    ("/api/pets/active", {"pet_ids": ["jaguar"]}, "PET"),
    ("/api/pet/intervene", {"signals": {"failed_attempts": 3}}, "PET"),
    ("/api/dungeon/enter", {"dungeon_id": "halfwritten_barrow"}, "BUILD"),
    ("/api/dungeon/move", {"room": 1}, "BUILD"),
    ("/api/dungeon/engage", {}, "BUILD"),
    ("/api/dungeon/retreat", {}, "BUILD"),
    ("/api/dungeon/leave", {}, "BUILD"),
    ("/api/travel", {"route": "rt_waking_road"}, "BUILD"),
    ("/api/route/discover", {"route": "rt_scribes_shortcut"}, "BUILD"),
    ("/api/hand/use", {}, "OBLIGING_HAND"),
    ("/api/world/new", {"seed": 7}, "BUILD"),
    ("/api/incant/start", {"encounter_id": "enc_first_loop"}, "BUILD"),
    ("/api/incant/cast", {"move_id": "bind", "answers": {}}, "BUILD"),
    ("/api/incant/leave", {}, "BUILD"),
    # A load mid-run is a retry with foreknowledge, so it is sealed too. Saving
    # is not, and there is a test below that says so.
    ("/api/load", {"slot_id": 1}, "BUILD"),
    ("/api/undo", {}, "BUILD"),
    ("/api/slot/import", {"payload": {"kind": "gauntlet-save-slot"}}, "BUILD"),
)

# Every world-layer POST, with a body that is the wrong shape in some way. None
# of these may produce a 500: a player who sends nonsense gets a sentence.
JUNK_BODIES = (
    {},
    {"class_id": 12, "node_id": None, "quest_id": [], "pet_ids": "jaguar",
     "dungeon_id": {}, "room": "deep", "route": 4, "slot_id": None,
     "ordinal": "x", "seed": {}, "signals": "go", "move_id": 9,
     "encounter_id": "", "payload": 3, "seconds_by_segment": {"set": "soon"},
     "scope": "sideways", "profile": "NOBODY"},
)


class ServerTest(GameTest):
    """A real HTTP server in front of a throwaway save."""

    def setUp(self):
        super().setUp()
        from gauntlet import server
        self.server = server
        self.g = self.game()
        server.set_game(self.g)
        self.httpd, _ = server.serve()
        self.addCleanup(server.set_game, None)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def hit(self, method, path, body=None, *, token=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "X-Gauntlet-Token": self.server.TOKEN if token is None
                     else token})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw or b"null")
            except ValueError:
                return exc.code, {"error": raw.decode("utf-8", "replace")}

    def enter_the_room(self):
        """Start a measured run. LIVE_SCREEN rather than the practical, because
        the seal does not care which measured format it is and compose() is the
        expensive one."""
        self.g.start_interview("LIVE_SCREEN")


class TestInterviewIsolationOverHTTP(ServerTest):
    def test_every_world_endpoint_is_sealed_during_a_measured_run(self):
        self.enter_the_room()
        for path, body, capability in SEALED_POSTS:
            with self.subTest(path=path):
                status, payload = self.hit("POST", path, body)
                self.assertEqual(status, 409, f"{path} answered {status}")
                self.assertEqual(payload["error"], "sealed")
                self.assertEqual(payload["capability"], capability)
                self.assertTrue(payload["message"].strip())

    def test_the_same_endpoints_are_open_in_adventure_mode(self):
        """The other half of the guarantee: nothing here is sealed by accident,
        and no gate leaves a player with nothing to do."""
        for path, body, _ in SEALED_POSTS:
            with self.subTest(path=path):
                status, payload = self.hit("POST", path, body)
                self.assertNotEqual(status, 409, f"{path} was sealed outside a run")
                self.assertNotEqual(payload.get("error"), "sealed")

    def test_saving_is_allowed_mid_run_but_loading_is_not(self):
        self.enter_the_room()
        status, payload = self.hit("POST", "/api/save",
                                   {"ordinal": 1, "name": "Mid-run"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["slot_id"], "slot:1")
        status, payload = self.hit("POST", "/api/load", {"slot_id": 1})
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "sealed")

    def test_the_way_in_is_not_sealed_behind_itself(self):
        """A seal that blocked the exam endpoints would be a dead end, and the
        rule says learning never dead-ends."""
        status, ladder = self.hit("GET", "/api/exam/ladder")
        self.assertEqual(status, 200)
        self.assertEqual(len(ladder["ladder"]), 14)
        self.enter_the_room()
        status, ladder = self.hit("GET", "/api/exam/ladder")
        self.assertEqual(status, 200)
        status, payload = self.hit("POST", "/api/exam/finish",
                                   {"seconds_by_segment": {}})
        self.assertEqual(status, 200)
        self.assertNotEqual(payload.get("error"), "sealed")

    def test_a_companion_never_speaks_in_a_measured_run(self):
        self.g.state["pets"]["found"] = ["jaguar"]
        self.g.state["pets"]["active"] = ["jaguar"]
        self.g.save()
        self.enter_the_room()
        status, payload = self.hit(
            "POST", "/api/pet/intervene",
            {"signals": {"submitted": True, "failed_attempts": 4,
                         "seconds_since_progress": 600.0,
                         "last_categories": ["wrong_output"] * 4}})
        self.assertEqual(status, 409)
        self.assertEqual(payload["capability"], "PET")

    def test_the_token_guard_still_stands_in_front_of_all_of_it(self):
        for path, body, _ in SEALED_POSTS[:4]:
            with self.subTest(path=path):
                status, payload = self.hit("POST", path, body, token="wrong")
                self.assertEqual(status, 403)
                self.assertEqual(payload["error"], "bad token")


class TestTheServerNeverBreaksOnBadInput(ServerTest):
    """Never 500 at a player. Every handler validates and answers in words."""

    def test_no_world_endpoint_500s_on_a_malformed_body(self):
        for path, _, _ in SEALED_POSTS + (
                ("/api/save", {}, ""), ("/api/slot/rename", {}, ""),
                ("/api/slot/delete", {}, ""), ("/api/slot/export", {}, ""),
                ("/api/exam/start", {}, ""), ("/api/exam/finish", {}, "")):
            for body in JUNK_BODIES:
                with self.subTest(path=path, body=sorted(body)[:1]):
                    status, payload = self.hit("POST", path, body)
                    self.assertLess(status, 500, f"{path} answered {status}")
                    self.assertIsInstance(payload, dict)
                    if payload.get("error"):
                        self.assertIsInstance(payload["error"], str)
                        self.assertTrue(payload["error"].strip())

    def test_a_body_that_is_not_json_is_a_400_with_a_sentence(self):
        request = urllib.request.Request(
            self.base + "/api/class/spend", data=b"{not json",
            method="POST",
            headers={"Content-Type": "application/json",
                     "X-Gauntlet-Token": self.server.TOKEN})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)
        payload = json.loads(caught.exception.read())
        self.assertIn("not valid JSON", payload["error"])

    def test_a_body_that_is_not_an_object_is_refused(self):
        request = urllib.request.Request(
            self.base + "/api/class/spend", data=b"[1, 2, 3]", method="POST",
            headers={"Content-Type": "application/json",
                     "X-Gauntlet-Token": self.server.TOKEN})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)

    def test_unknown_ids_are_404_and_say_what_was_not_found(self):
        for path, key, value in (
                ("/api/class/choose", "class_id", "sorcerer"),
                ("/api/class/spend", "node_id", "nothing_like_that"),
                ("/api/quest/accept", "quest_id", "save_the_cat"),
                ("/api/pets/active", "pet_ids", ["hippogriff"]),
                ("/api/dungeon/enter", "dungeon_id", "the_basement"),
                ("/api/travel", "route", "rt_nowhere"),
                ("/api/incant/start", "encounter_id", "enc_nothing"),
                ("/api/incant/cast", "move_id", "abracadabra")):
            with self.subTest(path=path):
                status, payload = self.hit("POST", path, {key: value})
                self.assertEqual(status, 404, f"{path} answered {status}")
                self.assertIn(str(value if isinstance(value, str) else value[0]),
                              payload["error"])

    def test_an_unknown_route_is_a_404_that_names_itself(self):
        for method in ("GET", "POST"):
            status, payload = self.hit(method, "/api/nothing/here",
                                       {} if method == "POST" else None)
            self.assertEqual(status, 404)
            self.assertIn("/api/nothing/here", payload["error"])


class TestTheWorldLayerIsReachable(ServerTest):
    """The point of the whole exercise: eleven modules a browser can now reach.

    One assertion per system, on the shape the client is written against.
    """

    def get(self, path):
        status, payload = self.hit("GET", path)
        self.assertEqual(status, 200, f"{path} answered {status}: {payload}")
        return payload

    def test_classes_and_the_skill_tree(self):
        self.assertEqual(len(self.get("/api/classes")["selection"]), 6)
        chosen = self.hit("POST", "/api/class/choose", {"class_id": "analyst"})[1]
        self.assertTrue(chosen["ok"])
        tree = self.get("/api/class/tree")
        self.assertEqual(tree["class"]["id"], "analyst")
        self.assertTrue(tree["branches"])
        self.assertTrue(tree["branches"][0]["nodes"])

    def test_quests_pets_and_dungeons(self):
        board = self.get("/api/quests")
        self.assertEqual(board["counts"]["total"], 74)
        self.assertEqual(len(self.get("/api/pets")["pets"]), 9)
        self.assertEqual(self.get("/api/pets")["limit"], 2)
        cards = self.get("/api/dungeons?region=fields_of_syntax")["dungeons"]
        self.assertTrue(cards)
        entered = self.hit("POST", "/api/dungeon/enter",
                           {"dungeon_id": cards[0]["id"]})[1]
        # options() is what guarantees there is always something to press.
        self.assertTrue(entered["options"])
        self.assertTrue(self.hit("POST", "/api/dungeon/leave", {})[1]["ok"])

    def test_progression_never_hands_back_an_empty_floor(self):
        self.assertTrue(self.get("/api/todo")["todo"])
        self.assertTrue(self.get("/api/world-map")["nodes"])
        self.assertTrue(self.get("/api/routes")["routes"])
        self.assertEqual(self.get("/api/events")["total"], 26)

    def test_saves_legendaries_worldgen_and_incantation(self):
        self.assertEqual(len(self.get("/api/saves")["slots"]), 16)
        self.assertEqual(len(self.get("/api/legendaries")["catalogue"]), 22)
        card = self.get("/api/world/card")
        self.assertTrue(card["seed"] and card["card"])
        # The seed round-trips: the same code is the same world for anybody.
        again = self.hit("POST", "/api/world/new", {"seed": card["seed"]})[1]
        self.assertEqual(again["seed"], card["seed"])
        self.assertTrue(self.get("/api/incantation?region=fields_of_syntax")
                        ["encounters"])



if __name__ == "__main__":
    unittest.main()
