"""History seals and task wording across adaptive presentation rungs."""
from __future__ import annotations

import copy
import json
import threading
import unittest
import urllib.request

from base import GameTest
from gauntlet import db, scaffold
from gauntlet.corpus import scaffolding
from gauntlet.corpus.families import first_steps


class HistoryViewGuards(GameTest):
    def setUp(self):
        super().setUp()
        self.g = self.game()
        self.addCleanup(self.g.conn.close)
        self.problem_id = self.g.teachable[0].id
        db.record_attempt(self.g.conn, problem_id=self.problem_id,
                          pattern="PRIVATE_PATTERN", family="private_family",
                          difficulty="EASY", mode="adventure",
                          encounter_kind="CODE_BATTLE", solved=1, rank="A",
                          hints_used=0, seconds=12, submitted_code="private_answer()")
        db.record_interview(self.g.conn, profile="PRACTICAL", format="LIVE_SCREEN",
                            problem_ids=self.problem_id, score=80, solved=1,
                            total=2, seconds=120,
                            detail="private_family private_answer()")

    def test_unsealed_history_keeps_the_players_work(self):
        view = self.g.performance_history(self.problem_id)
        self.assertFalse(view["sealed"])
        self.assertEqual(view["recent"][0]["submitted_code"], "private_answer()")
        self.assertEqual(view["problem"], view["recent"])
        self.assertIn("private_answer()", view["interviews"][0]["detail"])

    def test_every_open_run_shape_withholds_attempts_and_interview_details(self):
        normal = self.g.performance_history(self.problem_id)
        cases = (
            {"interview": {"id": "between-questions"}},
            {"exam": {"id": "practical-between-questions"}},
            {"encounter": {"problem_id": self.problem_id, "mode": "interview",
                           "started_at": 1}},
            {"encounter": {"problem_id": "repo:fixture", "mode": "interview",
                           "repo_id": "fixture", "started_at": 1}},
            {"encounter": ["unreadable"]},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                self.g.state.update(interview=None, exam=None, encounter=None)
                self.g.state.update(fields)
                before = copy.deepcopy(self.g.state)
                for requested in (None, self.problem_id):
                    view = self.g.performance_history(requested)
                    self.assertTrue(view["sealed"])
                    self.assertTrue(view["seal_note"])
                    self.assertEqual(view["recent"], [])
                    self.assertEqual(view["problem"], [])
                    self.assertEqual(view["stats"], normal["stats"])
                    self.assertEqual(view["bosses"], normal["bosses"])
                    self.assertEqual(view["interviews"][0]["score"], 80)
                    self.assertNotIn("detail", view["interviews"][0])
                    self.assertNotIn("problem_ids", view["interviews"][0])
                    rendered = json.dumps(view)
                    for private in ("PRIVATE_PATTERN", "private_family", "private_answer()"):
                        self.assertNotIn(private, rendered)
                self.assertEqual(self.g.state, before)
        self.g.state.update(interview=None, exam=None, encounter=None)
        self.assertEqual(self.g.performance_history(self.problem_id), normal)

    def test_http_history_is_sealed_even_on_the_world_screen(self):
        from gauntlet import server
        server.set_game(self.g)
        self.addCleanup(server.set_game, None)
        httpd = server.Server(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        self.g.state.update(interview=None, exam={"id": "open"}, encounter=None)
        for query in ("", "?problem_id=" + self.problem_id):
            request = urllib.request.Request(base + "/api/history" + query,
                headers={"X-Gauntlet-Token": server.TOKEN})
            with urllib.request.urlopen(request, timeout=10) as response:
                self.assertEqual(response.status, 200)
                view = json.load(response)
            self.assertTrue(view["sealed"])
            self.assertEqual(view["recent"], [])
            self.assertEqual(view["problem"], [])
            self.assertEqual(view["stats"]["total"], 1)
            self.assertNotIn("private_answer()", json.dumps(view))


class BannerPresentation(unittest.TestCase):
    def test_banner_instructions_do_not_assume_an_empty_editor(self):
        problems = first_steps.build()
        scaffolding.apply(problems)
        problem = next(p for p in problems if p.id == "fs-write-banner")
        for rung in (2, 3, 4):
            with self.subTest(rung=rung):
                rendered = scaffold.render(problem, rung)
                self.assertEqual(rendered["rung"], rung)
                self.assertEqual(rendered["blanks"], {2: 1, 3: 2, 4: 0}[rung])
                prose = (problem.title + " " + problem.problem_statement).lower()
                for assumption in ("no blanks", "nothing left blank", "body is empty"):
                    self.assertNotIn(assumption, prose)
                self.assertIn('banner("hi")', problem.problem_statement)
                self.assertIn("'** hi **'", problem.problem_statement)
