"""MINI-REPO BATTLES, proved by playing one.

The foundation — the sandbox, the assembly order, the tamper check, the
winnability audit — has its own proof in `minirepo.self_check()`, and the first
test here runs it rather than restating it. Everything after that is about the
WIRING: whether a Repo actually reaches the engine, the database, the world
layer and the browser, and whether the guarantees this game rests on survive the
trip.

Four of them are re-proved end to end rather than assumed:

  * Adventure Mode teaches, Interview Mode measures, and `finalexam.sealed()` is
    the one question. A Mini-Repo in a measured run gets no starting-file
    pointer, no task shapes, no target list, no hints, no probes, no companion
    and no coach — and the reference patch is not in the payload in any mode.
  * Mastery moves on graded evidence. A tampered attempt is void, and void
    earns nothing.
  * Nothing supplies an answer. The patch arrives in the debrief, after the
    attempt is scored, and never before it.
  * Learning never dead-ends — including after a cheat, where the lesson and the
    file the cause lived in are still owed.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from base import GameTest

from gauntlet import config, finalexam, minirepo, sandbox
from gauntlet.corpus import schema
from gauntlet.engine import REPO_ID_PREFIX, repo_problem

# One small repo, used wherever the test is about the wiring rather than about
# the repository. EASY, five files, two target tests.
REPO = "pager"


def tree_of(repo, files=None):
    """The player's whole working tree: the project, plus the suite exactly as
    it was handed out. That is what the editor sends, and the server needs the
    test bodies present to tell an untouched suite from a deleted one."""
    out = dict(files if files is not None else repo.files)
    out.update(repo.tests)
    return out


def solved_tree(repo):
    """The tree the reference patch leaves behind. Proof the fight is winnable
    is `audit()`'s job; this is how a test wins it."""
    return tree_of(repo, minirepo.apply_patch(repo))


# ==========================================================================
class TestTheFoundationStillHolds(GameTest):

    def test_every_repository_is_provably_winnable(self):
        report = minirepo.self_check()
        self.assertTrue(report["ok"],
                        f"mini-repos that cannot be won: {report['failed']}")
        self.assertGreaterEqual(report["repos"], 8)

    def test_a_repo_is_never_a_problem_in_the_corpus(self):
        g = self.game()
        for repo_id in minirepo.REPOS:
            self.assertNotIn(repo_id, g.by_id)
            self.assertNotIn(REPO_ID_PREFIX + repo_id, g.by_id)
        # The encounter table knows the string, and nothing was built from it.
        self.assertIn(minirepo.ENCOUNTER_KIND, schema.ENCOUNTER_KINDS)
        self.assertFalse([p for p in g.corpus
                          if p.encounter_kind == minirepo.ENCOUNTER_KIND])

    def test_choosing_never_dead_ends(self):
        """A player who has beaten all sixteen still gets a fight.

        `minirepo.pick` widens the difficulty tier but not the exclusion list,
        so it answers None once everything is excluded. The engine is the one
        that must not dead-end, so it is the engine that is asked here.
        """
        self.assertIsNone(minirepo.pick(exclude=set(minirepo.REPOS)))
        g = self.game()
        g.state["solved_ids"] = [REPO_ID_PREFIX + r for r in minirepo.REPOS]
        payload = g.start_minirepo()
        self.assertNotIn("error", payload)
        self.assertIn(payload["repo"]["id"], minirepo.REPOS)


# ==========================================================================
class TestPlayingOneAllTheWayThrough(GameTest):

    def test_spawn_read_edit_run_fail_fix_pass_resolve(self):
        g = self.game()
        repo = minirepo.get(REPO)

        payload = g.start_minirepo(REPO)
        self.assertEqual(payload["repo"]["id"], REPO)
        self.assertEqual(payload["repo"]["encounter_kind"], "MINI_REPO")
        self.assertEqual(g.encounter.repo_id, REPO)

        # READ: every file arrives with its body, and the suite is marked
        # read-only rather than merely omitted.
        paths = {row["path"] for row in payload["repo"]["files"]}
        self.assertEqual(paths, set(repo.files))
        self.assertTrue(all(not row["editable"] for row in payload["repo"]["tests"]))
        self.assertTrue(all(row["body"] for row in payload["repo"]["tests"]))

        # RUN, ungraded: the suite is red where the ticket says it is.
        before = g.minirepo_run(tree_of(repo))
        self.assertTrue(before["ok"])
        failing = {t["name"] for t in before["tests"] if t["status"] != "pass"}
        self.assertEqual(failing, set(repo.targets))
        self.assertFalse(before["graded"])

        # FAIL: handing it back untouched is INCOMPLETE, and earns no clear.
        miss = g.minirepo_submit(tree_of(repo))
        self.assertFalse(miss["solved"])
        self.assertEqual(miss["mini_repo"]["verdict"]["outcome"], "INCOMPLETE")
        self.assertIsNotNone(g.encounter, "a failed attempt closed the fight")

        # FIX, then run: green.
        after = g.minirepo_run(solved_tree(repo))
        self.assertEqual(after["passed"], after["total"])

        # PASS: resolved through the same outcome path as every other encounter.
        result = g.minirepo_submit(solved_tree(repo))
        self.assertTrue(result["solved"])
        self.assertEqual(result["mini_repo"]["verdict"]["outcome"], "SOLVED")
        self.assertIn(result["rank"], ("S", "A", "B", "C"))
        self.assertGreater(result["xp"], 0)
        self.assertEqual(result["skill"], "DEBUGGING")
        self.assertIsNone(g.state["encounter"], "a clear left the fight open")
        self.assertIn(REPO_ID_PREFIX + REPO, g.state["solved_ids"])

    def test_the_outcome_is_paid_into_the_world_like_any_other_encounter(self):
        g = self.game()
        repo = minirepo.get(REPO)
        xp_before = g.state["player"]["xp"]
        skills_before = g.skills["DEBUGGING"].clears
        g.start_minirepo(REPO)
        result = g.minirepo_submit(solved_tree(repo))

        self.assertGreater(g.state["player"]["xp"], xp_before)
        self.assertEqual(g.skills["DEBUGGING"].clears, skills_before + 1)
        # The suite is the contract, so testing is credited too, at a lower rate.
        self.assertGreater(g.skills["TESTING"].attempts, 0)
        # The attempt log, which is what every readiness number is built from.
        row = g.performance_history()["recent"][0]
        self.assertEqual(row["problem_id"], REPO_ID_PREFIX + REPO)
        self.assertEqual(row["encounter_kind"], "MINI_REPO")
        self.assertEqual(row["solved"], 1)
        self.assertEqual(row["tests_total"], row["tests_passed"])
        # And the rest of the world layer, which only runs because the outcome
        # went through _apply_outcome rather than around it.
        for key in ("quests_ready", "world_events", "upgrades", "artifacts"):
            self.assertIn(key, result)
        self.assertIn({"id", "family", "pattern", "kind", "solved"},
                      [set(entry) & {"id", "family", "pattern", "kind", "solved"}
                       for entry in g.state["session"]["log"]])

    def test_mastery_moves_on_the_verdict_and_nothing_else(self):
        g = self.game()
        repo = minirepo.get(REPO)
        g.start_minirepo(REPO)
        g.minirepo_submit(tree_of(repo))              # INCOMPLETE
        self.assertEqual(g.skills["DEBUGGING"].clears, 0)
        g.minirepo_submit(solved_tree(repo))          # SOLVED
        self.assertEqual(g.skills["DEBUGGING"].clears, 1)

    def test_only_what_was_actually_changed_is_carried(self):
        """The save keeps the player's edits, not a copy of the repository.

        Both halves matter: several kilobytes of unchanged source in every save
        is waste, and a file marked edited that nobody touched is a lie about
        where the work is.
        """
        g = self.game()
        repo = minirepo.get(REPO)
        g.start_minirepo(REPO)
        touched = sorted(repo.files)[-1]
        tree = tree_of(repo)
        tree[touched] += "\n# mine\n"
        g.minirepo_run(tree)
        self.assertEqual(set(g.encounter.repo_files), {touched})
        view = g.minirepo_view()
        edited = {row["path"] for row in view["repo"]["files"] if row.get("edited")}
        self.assertEqual(edited, {touched})
        # And the state payload does not carry the tree at all.
        active = g.dashboard()["active_encounter"]
        self.assertEqual(active["repo_id"], REPO)
        self.assertEqual(active["repo_files"], {})
        self.assertTrue(g.dashboard()["mini_repos"]["repos"])

    def test_a_reload_does_not_lose_twenty_minutes_of_reading(self):
        g = self.game()
        repo = minirepo.get(REPO)
        g.start_minirepo(REPO)
        edited = dict(repo.files)
        first = sorted(repo.files)[-1]
        edited[first] = repo.files[first] + "\n# my notes\n"
        g.minirepo_run(tree_of(repo, edited))

        again = self.game()               # the same save, a new process
        view = again.minirepo_view()
        body = {row["path"]: row["body"] for row in view["repo"]["files"]}[first]
        self.assertIn("# my notes", body)
        self.assertGreater(view["elapsed_seconds"], 0)
        # And it can be put down without earning anything.
        self.assertTrue(again.leave_minirepo()["ok"])
        self.assertIsNone(again.state["encounter"])


# ==========================================================================
class TestTheCheatCheck(GameTest):
    """The suite is the only honest thing in the room. Server-side, and it is
    not enough for the cheat to fail — it has to be refused out loud, because
    silently ignoring it teaches the player that it half-worked."""

    def setUp(self):
        super().setUp()
        self.g = self.game()
        self.repo = minirepo.get(REPO)

    def attempt(self, tree):
        self.g.start_minirepo(REPO)
        return self.g.minirepo_submit(tree)

    def test_a_blanked_test_file_is_refused_and_never_run(self):
        tree = tree_of(self.repo)
        victim = self.repo.test_paths[0]
        tree[victim] = "def test_free_pass():\n    assert True\n"
        result = self.attempt(tree)
        verdict = result["mini_repo"]["verdict"]
        self.assertEqual(verdict["outcome"], "TAMPERED")
        self.assertFalse(result["solved"])
        self.assertEqual(verdict["tests"], [],
                         "a tampered submission was run anyway")
        self.assertIn(victim, verdict["tamper"]["edited"])
        self.assertIn(victim, verdict["tamper"]["message"])

    def test_the_cheat_is_refused_even_when_the_code_is_right(self):
        # The interesting case: solve it properly AND weaken a test. A check
        # that only fires when the player was going to fail anyway is not a
        # check.
        tree = solved_tree(self.repo)
        tree[self.repo.test_paths[0]] = "def test_ok():\n    assert True\n"
        result = self.attempt(tree)
        self.assertEqual(result["mini_repo"]["verdict"]["outcome"], "TAMPERED")
        self.assertFalse(result["solved"])
        self.assertEqual(self.g.skills["DEBUGGING"].clears, 0)

    def test_a_deleted_test_file_is_a_deletion(self):
        tree = tree_of(self.repo)
        victim = self.repo.test_paths[0]
        del tree[victim]
        verdict = self.attempt(tree)["mini_repo"]["verdict"]
        self.assertEqual(verdict["outcome"], "TAMPERED")
        self.assertIn(victim, verdict["tamper"]["deleted"])

    def test_a_partial_save_is_not_an_accusation(self):
        # The sharp edge in the API, on purpose: the same submission is a
        # deletion or is not, depending on what the caller says it is.
        self.g.start_minirepo(REPO)
        partial = dict(self.repo.files)
        verdict = self.g.minirepo_submit(partial, full_tree=False)
        self.assertNotEqual(verdict["mini_repo"]["verdict"]["outcome"], "TAMPERED")

    def test_learning_does_not_dead_end_at_a_cheat(self):
        tree = tree_of(self.repo)
        tree[self.repo.test_paths[0]] = "def test_ok():\n    assert True\n"
        debrief = self.attempt(tree)["mini_repo"]["debrief"]
        self.assertTrue(debrief["lesson"])
        self.assertTrue(debrief["where"])

    def test_a_file_the_repository_never_handed_out_is_refused(self):
        for path in ("pager/evil.py", "../../../../etc/passwd", "/tmp/owned.py",
                     "tests/test_page.py.bak", "pager/../../x.py"):
            tree = tree_of(self.repo)
            tree[path] = "print('hello')\n"
            self.g.start_minirepo(REPO)
            refusal = self.g.minirepo_submit(tree)
            self.assertEqual(refusal.get("error"), "not a file in this repository",
                             f"{path} was accepted")
            self.assertNotIn("solved", refusal)
            # Refused, not graded: the fight is untouched and still open.
            self.assertIsNotNone(self.g.encounter)

    def test_a_working_tree_nobody_could_have_typed_is_refused(self):
        tree = tree_of(self.repo)
        tree["pager/page.py"] = "#" * (10 * 1024 * 1024)
        self.g.start_minirepo(REPO)
        refusal = self.g.minirepo_submit(tree)
        self.assertEqual(refusal.get("error"), "working tree is too large")
        self.assertLess(self.repo.byte_count, sandbox.MAX_PROJECT_BYTES)

    def test_the_bytes_of_a_weakened_test_never_reach_the_sandbox(self):
        # Belt and braces, which is minirepo's own invariant: even with the
        # check removed, the submitted bytes are not the bytes that get written.
        tree = tree_of(self.repo)
        victim = self.repo.test_paths[0]
        tree[victim] = "def test_free_pass():\n    assert True\n"
        self.assertEqual(minirepo.assemble(self.repo, tree)[victim],
                         self.repo.tests[victim])

    def test_an_infinite_loop_is_contained_and_reported(self):
        tree = tree_of(self.repo)
        tree["pager/page.py"] = "while True:\n    pass\n" + tree["pager/page.py"]
        self.g.start_minirepo(REPO)
        started = time.time()
        result = self.g.minirepo_submit(tree)
        spent = time.time() - started
        self.assertLess(spent, 60, "a hung project hung the server")
        self.assertFalse(result["solved"])
        # Whatever it is called, the player is told something specific enough to
        # act on, and the fight is still theirs to continue.
        self.assertTrue(result["mini_repo"]["verdict"]["message"])
        self.assertTrue(result["feedback"]["lines"])


# ==========================================================================
class TestTheSeal(GameTest):
    """What a measured run takes off a Mini-Repo, and the one place it is asked."""

    def payload(self, mode):
        """A fresh fight in `mode`.

        Each `self.game()` is a new object over the SAME save, so a repository
        left open by the previous call is still open — and the engine hands
        that one back rather than throwing its working tree away. Putting it
        down first is what a player does, and it is what makes the two halves
        of these tests independent.
        """
        g = self.game()
        g.leave_minirepo()
        return g, g.start_minirepo("dispatch", mode=mode)

    def test_interview_mode_takes_the_pointer_the_shapes_and_the_targets(self):
        g, payload = self.payload(config.MODE_INTERVIEW)
        view = payload["repo"]
        self.assertEqual(view["start_file"], "")
        self.assertEqual(view["start_note"], "")
        self.assertEqual(view["shapes"], [])
        self.assertEqual(view["targets"], [])
        self.assertIsNone(payload["mentor"])
        self.assertEqual(payload["hint_count"], 0)
        self.assertEqual(payload["probe_charges"], 0)
        self.assertEqual(payload["companions"], [])
        self.assertEqual(payload["skill"], "")
        # The files themselves are all still there. A practical is not a
        # redaction exercise.
        self.assertEqual({row["path"] for row in view["files"]},
                         set(minirepo.get("dispatch").files))

    def test_adventure_mode_keeps_the_pointer(self):
        g, payload = self.payload(config.MODE_ADVENTURE)
        self.assertTrue(payload["repo"]["start_file"])
        self.assertTrue(payload["repo"]["start_note"])
        self.assertTrue(payload["repo"]["shapes"])
        self.assertTrue(payload["repo"]["targets"])

    def test_the_seal_is_whatever_finalexam_says_it_is(self):
        """Not a second check. Every capability in the payload agrees with
        finalexam.sealed(), in both modes, or this is a place the rule can
        drift."""
        for mode in (config.MODE_ADVENTURE, config.MODE_INTERVIEW):
            g, payload = self.payload(mode)
            enc = g.encounter
            for cap in minirepo.SEALED_CAPABILITIES:
                self.assertEqual(cap in payload["sealed"],
                                 finalexam.sealed(enc, cap),
                                 f"{cap} in {mode}")

    def test_the_patch_is_never_in_the_payload_in_any_mode(self):
        repo = minirepo.get("dispatch")
        for mode in (config.MODE_ADVENTURE, config.MODE_INTERVIEW):
            g, payload = self.payload(mode)
            blob = json.dumps(payload)
            for fix in repo.patch:
                self.assertNotIn(fix.new, blob, f"the patch shipped in {mode}")

    def test_the_worked_solution_follows_the_rule_it_always_follows(self):
        repo = minirepo.get(REPO)
        g = self.game()
        g.start_minirepo(REPO, mode=config.MODE_INTERVIEW)
        sealed = g.minirepo_submit(tree_of(repo))
        self.assertEqual(sealed["mini_repo"]["debrief"]["solution"], [])
        self.assertTrue(sealed["mini_repo"]["debrief"]["lesson"])

        g = self.game()
        g.start_minirepo(REPO)
        taught = g.minirepo_submit(tree_of(repo))
        self.assertTrue(taught["mini_repo"]["debrief"]["solution"])

    def test_the_clock_is_the_repos_own_with_no_grace(self):
        repo = minirepo.get("dispatch")
        g, adventure = self.payload(config.MODE_ADVENTURE)
        self.assertIsNone(adventure["clock_seconds"])
        self.assertEqual(adventure["target_seconds"], repo.clock)
        g, measured = self.payload(config.MODE_INTERVIEW)
        self.assertEqual(measured["clock_seconds"], float(repo.clock))
        self.assertEqual(repo_problem(repo).target_seconds, repo.clock)

    def test_the_crutches_have_nothing_to_offer_and_say_so(self):
        g = self.game()
        # Wearing the Hand, so the refusal under test is the Mini-Repo's own
        # and not "you do not own one".
        g.state["legendaries"].append("obliging_hand")
        g.start_minirepo(REPO)
        for refusal in (g.use_hint(1), g.probe([1], 1), g.use_hand()):
            self.assertIn("error", refusal)
            self.assertNotEqual(refusal.get("error"), "sealed")
            self.assertTrue(refusal.get("message"))
        # And the code-shaped doors send the player to the right one rather
        # than raising a KeyError on an id the corpus has never heard of.
        for refusal in (g.submit("x = 1"), g.run_visible("x = 1"),
                        g.solve_puzzle({}), g.answer_mcq(0)):
            self.assertIn("error", refusal)

    def test_a_measured_run_refuses_to_open_a_repository_at_all(self):
        g = self.game()
        g._start_exam(config.DEFAULT_PROFILE)
        refusal = g.start_minirepo(REPO)
        self.assertEqual(refusal.get("error"), "sealed")
        self.assertTrue(refusal.get("capability"))


# ==========================================================================
class TestOverHTTP(GameTest):
    """The same fight, through the door the browser actually uses."""

    def setUp(self):
        super().setUp()
        from gauntlet import server as server_module
        self.server_module = server_module
        self.g = self.game()
        server_module.set_game(self.g)
        # Put the module back the way it was found. `_GAME` is process-wide, and
        # a dead Game pointing at a deleted temp directory is not something to
        # leave lying around for whatever test runs next.
        self.addCleanup(server_module.set_game, None)
        self.httpd, url = server_module.serve()
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)
        self.base = url.split("/?")[0]
        self.token = server_module.TOKEN
        self.repo = minirepo.get(REPO)

    def call(self, path, body=None):
        request = urllib.request.Request(
            self.base + path, method="POST" if body is not None else "GET",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Gauntlet-Token": self.token,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_the_whole_fight_over_the_wire(self):
        status, board = self.call("/api/repos")
        self.assertEqual(status, 200)
        self.assertTrue(board["repos"])

        status, started = self.call("/api/repo/start", {"repo_id": REPO})
        self.assertEqual(status, 200, started)
        self.assertEqual(started["repo"]["id"], REPO)

        status, resumed = self.call("/api/repo")
        self.assertEqual(status, 200)
        self.assertEqual(resumed["repo"]["id"], REPO)

        status, report = self.call("/api/repo/run", {"files": tree_of(self.repo)})
        self.assertEqual(status, 200, report)
        self.assertLess(report["passed"], report["total"])

        status, result = self.call("/api/repo/submit",
                                   {"files": solved_tree(self.repo)})
        self.assertEqual(status, 200, result)
        self.assertTrue(result["solved"])
        self.assertTrue(result["mini_repo"]["debrief"]["lesson"])

        # And the board now says it was beaten.
        status, board = self.call("/api/repos")
        self.assertIn(REPO, board["cleared"])

    def test_a_blanked_test_over_the_wire_is_refused(self):
        self.call("/api/repo/start", {"repo_id": REPO})
        tree = tree_of(self.repo)
        tree[self.repo.test_paths[0]] = "def test_ok():\n    assert True\n"
        status, result = self.call("/api/repo/submit", {"files": tree})
        self.assertEqual(status, 200)
        self.assertEqual(result["mini_repo"]["verdict"]["outcome"], "TAMPERED")
        self.assertFalse(result["solved"])

    def test_malformed_working_trees_are_a_sentence_not_a_stack_trace(self):
        status, payload = self.call("/api/repo/start", {"repo_id": "nowhere"})
        self.assertEqual(status, 404, payload)
        self.call("/api/repo/start", {"repo_id": REPO})
        for body in ({"files": ["pager/page.py"]},
                     {"files": {"pager/page.py": 17}},
                     {"files": {"pager/page.py": "x"}, "full_tree": "yes"}):
            status, payload = self.call("/api/repo/submit", body)
            self.assertEqual(status, 400, payload)
            self.assertIn("error", payload)

    def test_a_second_repository_never_silently_discards_the_first(self):
        """Twenty minutes of reading lives on the encounter. Opening another
        repository would throw it away, so it is refused — and asking for the
        one already open is a resume rather than a refusal."""
        self.call("/api/repo/start", {"repo_id": REPO})
        tree = tree_of(self.repo)
        touched = sorted(self.repo.files)[-1]
        tree[touched] += "\n# mine\n"
        self.call("/api/repo/run", {"files": tree})
        status, refusal = self.call("/api/repo/start", {"repo_id": "logsift"})
        self.assertEqual(status, 200, refusal)
        self.assertEqual(refusal.get("error"), "a mini-repo is already open")
        status, resumed = self.call("/api/repo/start", {"repo_id": REPO})
        self.assertEqual(status, 200)
        self.assertEqual(resumed["repo"]["id"], REPO)
        body = {row["path"]: row["body"] for row in resumed["repo"]["files"]}
        self.assertIn("# mine", body[touched])

    def test_the_door_is_shut_during_a_measured_run(self):
        status, _ = self.call("/api/exam/start", {})
        self.assertEqual(status, 200)
        status, payload = self.call("/api/repo/start", {"repo_id": REPO})
        self.assertEqual(status, 409, payload)
        self.assertEqual(payload.get("error"), "sealed")
        self.assertTrue(payload.get("capability"))


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
