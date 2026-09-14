"""Persisted practice, actual grading evidence and sealed API boundaries."""
from __future__ import annotations

import copy
import json
import sqlite3
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

from base import GameTest
from gauntlet import adaptive, db, practice, scaffold, rematches, world


class PracticeSessions(GameTest):
    def setUp(self):
        super().setUp()
        self.g = self.game()
        self.addCleanup(self.g.conn.close)

    def test_pause_clock_resume_draft_and_no_second_task_on_reload(self):
        with patch("gauntlet.practice.time.time", return_value=1000):
            self.g.practice_start(10)
            first = self.g.practice_next()
        pid = first["problem"]["id"]
        with patch("gauntlet.practice.time.time", return_value=1010):
            self.g.practice_draft(pid, "# my unfinished work", "Explain before coding")
        with patch("gauntlet.practice.time.time", return_value=1030):
            paused = self.g.practice_action("pause")["plan"]
        self.assertEqual(paused["elapsed_seconds"], 30)
        with patch("gauntlet.practice.time.time", return_value=1100):
            self.assertEqual(self.g.practice_action("pause")["plan"]["elapsed_seconds"], 30)
            self.assertIn("error", self.g.practice_next())
            loaded = self.game()
            self.addCleanup(loaded.conn.close)
            loaded.practice_action("resume")
        with patch("gauntlet.practice.time.time", return_value=1110):
            same = loaded.practice_next()
        self.assertEqual(same["problem"]["id"], pid)
        self.assertEqual(same["encounter"]["started_at"], first["encounter"]["started_at"])
        self.assertEqual(same["problem"]["scaffold"], first["problem"]["scaffold"])
        self.assertEqual(same["draft"]["code"], "# my unfinished work")
        self.assertEqual(same["draft"]["explanation"], "Explain before coding")
        self.assertEqual(same["practice"]["elapsed_seconds"], 40)

    def test_idle_lease_stops_a_crashed_browser_clock(self):
        plan = practice.begin(10, "balanced", "expedition", now=1000)
        self.assertEqual(practice.elapsed(plan, now=1500), 180)
        practice.heartbeat(plan, now=1500)
        self.assertEqual(practice.elapsed(plan, now=1530), 210)
        practice.pause(plan, now=1530)
        self.assertEqual(practice.elapsed(plan, now=9000), 210)

    def test_stale_draft_cannot_replace_current_work_and_ordinary_draft_survives_adoption(self):
        problem = self.g.teachable[0]
        self.g.start_encounter(problem.id)
        enc = self.g.encounter
        self.assertTrue(self.g.practice_draft(problem.id, "# current", encounter_started_at=enc.started_at)["saved"])
        self.assertIn("error", self.g.practice_draft(problem.id, "# stale", encounter_started_at=enc.started_at - 1))
        self.g.practice_start(20)
        payload = self.g.practice_next()
        self.assertEqual(payload["draft"]["code"], "# current")
        self.assertEqual(payload["encounter"]["started_at"], enc.started_at)

    def test_trace_wrapper_uses_only_selected_visible_case_and_refuses_invalid_index(self):
        problem = next(p for p in self.g.teachable if scaffold.scaffoldable(p) and p.visible_tests)
        self.g.start_encounter(problem.id)
        with patch("gauntlet.sandbox.trace_program", return_value={"ok": True, "frames": []}) as runner:
            result = self.g.trace("# player source", 0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["source"], "# player source")
            self.assertEqual(result["kind"], "actual_program")
            runner.assert_called_once_with("# player source", problem.entry, problem.visible_tests[0])
            self.assertIn("error", self.g.trace("pass", -1))
            self.assertIn("error", self.g.trace("pass", True))
            self.assertEqual(runner.call_count, 1)

    def test_all_intents_preserve_initial_chain_and_no_holdout(self):
        for intent in practice.INTENTS:
            selected = adaptive.select_next(self.g.corpus, skills=self.g.skills,
                schedule={}, profile="PRACTICAL", solved_ids=set(), recent_ids=[],
                intent=intent)
            self.assertEqual(selected.problem.id, "fs-see-a-value", intent)
            self.assertFalse(selected.problem.sealed)

    def test_real_reading_and_scaffold_grades_are_not_independent_code(self):
        self.g.practice_start(10, "balanced", "rehearsal")
        encounter = self.g.practice_next()
        problem = self.g.by_id[encounter["problem"]["id"]]
        result = self.g.answer_mcq(problem.mcq["answer"])
        self.assertTrue(result["solved"], result)
        self.assertEqual(result["practice"]["completed_count"], 1)
        row = db.recent_attempts(self.g.conn, 1)[0]
        self.assertEqual(row["evidence_kind"], "reading")
        self.assertIsNone(row["served_rung"])
        self.assertEqual(row["practice_kind"], "rehearsal")
        self.assertEqual(self.g.conn.execute("SELECT COUNT(*) FROM transfer_encounters").fetchone()[0], 0)
        self.g.practice_action("finish")
        problem = self.g.by_id["fs-write-banner"]
        self.g.start_encounter(problem.id)
        self.g.practice_start(10)
        self.g.practice_next()
        result = self.g.submit(problem.canonical_solution)
        self.assertTrue(result["solved"], result)
        row = db.recent_attempts(self.g.conn, 1)[0]
        self.assertEqual(row["served_rung"], 2)
        self.assertEqual(row["evidence_kind"], "scaffolded")
        self.assertEqual(result["practice"]["summary"]["independent"], 0)

    def test_whole_function_evidence_is_recorded_from_served_encounter(self):
        problem = next(p for p in self.g.teachable if p.difficulty == "MEDIUM"
                       and scaffold.scaffoldable(p))
        self.g.start_encounter(problem.id)
        self.assertEqual(self.g.encounter.rung, 4)
        result = self.g.submit(problem.canonical_solution)
        self.assertTrue(result["solved"], result)
        row = db.recent_attempts(self.g.conn, 1)[0]
        self.assertEqual((row["served_rung"], row["evidence_kind"]), (4, "whole_function"))

    def test_finish_and_retreat_are_idempotent_and_do_not_award_currency(self):
        self.g.practice_start(20, "weakest")
        first = self.g.practice_next()
        self.g.practice_action("retreat")
        self.g.practice_action("retreat")
        self.assertIsNone(self.g.encounter)
        self.assertEqual(self.g.practice_view()["plan"]["summary"]["retreated"], 1)
        second = self.g.practice_next()
        self.assertNotEqual(first["encounter"]["practice_task_id"], second["encounter"]["practice_task_id"])
        self.g.practice_draft(second["problem"]["id"], "# keep this")
        # A different screen/run may have cleared the live encounter, while
        # the resumable plan still owns its saved copy.
        self.g._write_encounter(None)
        player = copy.deepcopy(self.g.state["player"])
        self.g.practice_action("finish")
        self.g.practice_action("finish")
        self.assertEqual(len(self.g.practice_view()["history"]), 1)
        self.assertEqual(self.g.state["player"]["gold"], player["gold"])
        self.assertEqual(self.g.state["player"]["xp"], player["xp"])
        self.assertEqual(self.g.encounter.draft["code"], "# keep this")
        self.assertEqual(self.g.encounter.practice_id, "")

    def test_journal_unknown_legacy_evidence_notes_and_holdout_exclusion(self):
        problem = self.g.teachable[0]
        def attempt(p, code):
            db.record_attempt(self.g.conn, problem_id=p.id,
                pattern=p.pattern, family=p.spaced_repetition_family,
                difficulty=p.difficulty, mode="adventure", encounter_kind=p.encounter_kind,
                solved=1, hints_used=0, submitted_code=code)
        attempt(problem, "# old personal work")
        self.assertTrue(self.g.holdout)
        hidden = self.g.holdout[0]
        attempt(hidden, "NEVER_SHIP_THIS_HOLDOUT_ANSWER")
        family = problem.spaced_repetition_family
        self.g.journal_note(family, "Check the empty input first.")
        page = self.g.journal()
        row = next(f for f in page["families"] if f["id"] == family)
        self.assertEqual(row["notes"], "Check the empty input first.")
        self.assertEqual(row["attempts"][0]["evidence_kind"], "unknown")
        self.assertIsNone(row["attempts"][0]["served_rung"])
        self.assertEqual(row["attempts"][0]["submitted_code"], "# old personal work")
        blob = json.dumps(page)
        self.assertNotIn("NEVER_SHIP_THIS_HOLDOUT_ANSWER", blob)
        self.assertNotIn(hidden.id, blob)
        loaded = self.game()
        self.addCleanup(loaded.conn.close)
        self.assertEqual(loaded.state[practice.STATE_KEY]["notes"][family], row["notes"])

    def test_legacy_database_columns_are_nullable_and_preserve_existing_rows(self):
        path = self.data_dir / "legacy.sqlite3"
        old_schema = db.SCHEMA
        for field, typ in (("served_rung", "INTEGER"), ("evidence_kind", "TEXT"),
                           ("practice_id", "TEXT"), ("practice_kind", "TEXT")):
            import re
            old_schema = re.sub(r"^\s*" + field + r"\s+" + typ + r",\n", "", old_schema, flags=re.M)
        conn = sqlite3.connect(path)
        conn.executescript(old_schema)
        conn.execute("INSERT INTO attempts (problem_id,pattern,family,difficulty,mode,encounter_kind,solved,created_at) VALUES ('old','ARRAY','old','EASY','adventure','CODE_BATTLE',1,1)")
        conn.commit()
        conn.close()
        conn = db.connect(path)
        self.addCleanup(conn.close)
        row = db.recent_attempts(conn, 1)[0]
        self.assertEqual(row["problem_id"], "old")
        self.assertIsNone(row["served_rung"])
        self.assertIsNone(row["evidence_kind"])

    def test_earned_appearance_changes_only_colors_and_stays_chosen_under_seal(self):
        self.assertIn("error", self.g.choose_appearance("copper"))
        problem = self.g.teachable[0]
        db.record_attempt(self.g.conn, problem_id=problem.id, pattern=problem.pattern,
            family=problem.spaced_repetition_family, difficulty="EASY", mode="adventure",
            encounter_kind="CODE_BATTLE", solved=1, hints_used=0,
            evidence_kind="whole_function", served_rung=4)
        base = self.g._hero_look()
        effects = self.g.effects()
        chosen = self.g.choose_appearance("copper")
        self.assertEqual(chosen["selected"], "copper")
        look = self.g._hero_look()
        self.assertEqual(look["cloak"], "#a45438")
        for key in ("body", "sprite", "metal", "weapon", "_weapon", "_gear"):
            self.assertEqual(look.get(key), base.get(key))
        self.assertEqual(self.g.effects(), effects)
        self.g.state["exam"] = {"id": "open"}
        self.assertEqual(self.g.appearance()["error"], "sealed")
        self.assertEqual(self.g.choose_appearance("equipment")["error"], "sealed")
        self.assertEqual(self.g._hero_look()["cloak"], "#a45438")

    def test_all_boss_rematch_contracts_select_and_eventually_exhaust(self):
        self.assertEqual(rematches.validate_manifest(self.g.by_id), [])
        self.assertEqual(len(world.BOSSES), 14)
        for boss in world.BOSSES:
            entries = rematches.MANIFEST[boss["id"]]
            self.assertEqual(self.g._rematch_problem(boss, 0), boss["problem_id"])
            for index, entry in enumerate(entries, 1):
                self.assertEqual(self.g._rematch_problem(boss, index), entry.problem_id)
            exhausted = rematches.get_rematch(boss, len(entries) + 1, self.g.by_id)
            self.assertTrue(exhausted["exhausted"])
            self.assertFalse(exhausted["constraint_changed"])
            self.assertFalse(exhausted["transfer_evidence"])
        boss = world.BOSS_BY_ID["hash_titan"]
        self.g.state["player"]["region"] = boss["region"]
        self.g.state["boss_rematch"][boss["id"]] = 1
        opened = self.g.start_boss(boss["id"])
        self.assertNotIn("error", opened, opened)
        metadata = opened["boss"]["rematch_contract"]
        self.assertEqual(metadata["problem_id"], opened["problem"]["id"])
        self.assertTrue(metadata["constraint_changed"])
        fight = self.g._boss_fight()
        fight["phase"] = 1
        self.g._write_boss_fight(fight)
        later = self.g.start_boss(boss["id"])
        self.assertEqual(later["boss"]["rematch_contract"]["kind"], "phase_practice")
        self.assertFalse(later["boss"]["rematch_contract"]["constraint_changed"])

    def test_seal_refuses_all_learning_routes_and_export_without_mutation(self):
        self.g.practice_start(10)
        self.g.practice_next()
        normal = self.g.export()
        self.assertIn("attempts", normal)
        for fields in ({"interview": {"id": "run"}}, {"exam": {"id": "exam"}},
                       {"encounter": {"problem_id": "x", "mode": "interview", "started_at": 1}},
                       {"encounter": ["corrupt"]}):
            self.g.state.update(interview=None, exam=None, encounter=None)
            self.g.state.update(fields)
            before = copy.deepcopy(self.g.state)
            with patch("gauntlet.sandbox.trace_program", create=True) as trace:
                for operation in (self.g.practice_view, self.g.journal, self.g.export,
                        lambda: self.g.practice_start(10), lambda: self.g.practice_action("finish"),
                        self.g.practice_next, lambda: self.g.practice_draft("x", "pass"),
                        lambda: self.g.journal_note("x", "a"), lambda: self.g.trace("pass")):
                    self.assertEqual(operation().get("error"), "sealed")
                trace.assert_not_called()
            self.assertEqual(self.g.state, before)

    def test_real_http_practice_journal_draft_validation_and_export_seal(self):
        from gauntlet import server
        server.set_game(self.g)
        self.addCleanup(server.set_game, None)
        httpd = server.Server(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        def call(path, body=None):
            req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                headers={"X-Gauntlet-Token": server.TOKEN, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                with error:
                    return error.code, json.load(error)
        self.assertEqual(call("/api/practice")[0], 200)
        self.assertEqual(call("/api/practice/start", {"minutes": True})[0], 400)
        self.assertEqual(call("/api/practice/start", {"minutes": 10, "kind": "rehearsal"})[0], 200)
        status, payload = call("/api/practice/next", {})
        self.assertEqual(status, 200, payload)
        pid = payload["problem"]["id"]
        self.assertEqual(call("/api/practice/draft", {"problem_id": pid, "code": "x" * 20001})[0], 400)
        self.assertEqual(call("/api/practice/draft", {"problem_id": pid, "code": "# draft"})[0], 200)
        self.assertEqual(call("/api/journal")[0], 200)
        self.g.state.update(interview=None, exam={"id": "open"}, encounter=None)
        for path in ("/api/practice", "/api/journal", "/api/export"):
            self.assertEqual(call(path)[0], 409, path)
        self.assertEqual(call("/api/practice/next", {})[0], 409)
