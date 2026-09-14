"""Ordinary encounter reloads preserve the exercise and its recorded support."""
from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from gauntlet import dungeons
from gauntlet.corpus import build_all
from gauntlet.engine import Game


class EncounterResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Corpus validation has its own suite. This fixture supplies the real
        # authored corpus directly and exercises real Game/SQLite persistence.
        cls.corpus = build_all()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="gauntlet-resume-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        env = patch.dict("os.environ", {"GAUNTLET_DATA_DIR": str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        corpus = patch("gauntlet.engine.ensure_corpus", return_value=self.corpus)
        corpus.start()
        self.addCleanup(corpus.stop)
        self.g = self.load()

    def load(self):
        game = Game(db_path=self.path / "save.sqlite3")
        self.addCleanup(game.conn.close)
        return game

    def open_code(self):
        self.g.start_encounter("fs-write-banner")
        enc = self.g.encounter
        self.g.practice_draft(enc.problem_id, "# my unfinished banner\n", "Recall the string boundary.", enc.started_at)
        return self.g.encounter

    def test_reload_preserves_draft_rung_start_and_attempt_counters(self):
        old = self.open_code()
        old.runs, old.submits, old.hints_used = 2, 1, 1
        self.g._write_encounter(old)
        self.g.save()
        loaded = self.load()
        with patch.object(loaded, "_serve_rung", side_effect=AssertionError("resume must not reselect support")):
            resumed = loaded.resume_encounter(old.problem_id)
        self.assertEqual(resumed["reason"], "ENCOUNTER_RESUME")
        self.assertEqual(resumed["problem"]["id"], old.problem_id)
        for field in ("started_at", "rung", "runs", "submits", "hints_used"):
            self.assertEqual(resumed["encounter"][field], getattr(old, field), field)
        self.assertEqual(resumed["problem"]["scaffold"]["rung"], old.rung)
        self.assertEqual(resumed["draft"], old.draft)
        self.assertEqual(loaded.encounter.draft, old.draft)
        self.assertEqual(loaded.conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def test_reading_and_puzzle_reload_the_current_problem(self):
        for kind in ("CODE_READING", "TRACE"):
            problem = next(p for p in self.g.teachable if p.encounter_kind == kind)
            self.g.start_encounter(problem.id)
            old = self.g.encounter
            resumed = self.load().resume_encounter(problem.id)
            self.assertEqual(resumed["problem"]["id"], problem.id)
            self.assertEqual(resumed["encounter"]["started_at"], old.started_at)

    def test_legacy_unknown_rung_remains_unknown(self):
        old = self.open_code()
        old.rung = 0
        self.g._write_encounter(old)
        self.g.save()
        resumed = self.load().resume_encounter(old.problem_id)
        self.assertEqual(resumed["encounter"]["rung"], 0)
        self.assertEqual(resumed["draft"], old.draft)
        self.assertEqual(resumed["problem"]["scaffold"]["rung"], 4)

    def test_stale_or_missing_current_problem_never_selects_another(self):
        self.assertIn("error", self.g.resume_encounter())
        old = self.open_code()
        before = copy.deepcopy(self.g.state)
        self.assertEqual(self.g.resume_encounter("another-problem")["error"], "encounter changed")
        self.assertEqual(self.g.state, before)
        del self.g.by_id[old.problem_id]
        self.assertIn("error", self.g.resume_encounter(old.problem_id))
        self.assertEqual(self.g.state, before)

    def test_measured_and_foreign_activities_refuse_without_mutation(self):
        self.open_code()
        ordinary = copy.deepcopy(self.g.state)
        cases = [{"interview": {"id": "open"}}, {"exam": {"id": "open"}},
                 {"encounter": ["damaged"]}, {"boss_fight": {"id": "open"}},
                 {dungeons.STATE_KEY: {"id": "open"}}, {"incantation": {"id": "open"}}]
        for field, value in (("mode", "interview"), ("mode", "foreign"),
                ("repo_id", "fixture"), ("boss_id", "hash_titan"),
                ("practice_id", "practice-fixture"), ("dungeon_room", 0),
                ("interview_id", "fixture"), ("holdout", True)):
            cases.append({"encounter": {**ordinary["encounter"], field: value}})
        for fields in cases:
            with self.subTest(fields=fields):
                self.g.state = copy.deepcopy(ordinary)
                self.g.state.update(fields)
                before = copy.deepcopy(self.g.state)
                self.assertIn("error", self.g.resume_encounter())
                self.assertEqual(self.g.state, before)

    def test_http_resume_uses_current_identity_and_honours_measurement_seal(self):
        from gauntlet import server
        old = self.open_code()
        server.set_game(self.g)
        self.addCleanup(server.set_game, None)
        httpd = server.Server(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/api/encounter/resume"
        def get(suffix=""):
            request = urllib.request.Request(url + suffix, headers={"X-Gauntlet-Token": server.TOKEN})
            try:
                response = urllib.request.urlopen(request, timeout=10)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, json.load(response)
        status, resumed = get("?problem_id=" + old.problem_id)
        self.assertEqual(status, 200)
        self.assertEqual(resumed["encounter"]["started_at"], old.started_at)
        self.assertEqual(resumed["draft"], old.draft)
        self.assertEqual(get("?problem_id=another")[0], 400)
        self.g.state["exam"] = {"id": "open"}
        status, refused = get()
        self.assertEqual(status, 409)
        self.assertEqual(refused["error"], "sealed")
        self.assertNotIn("draft", refused)


if __name__ == "__main__":
    unittest.main()
