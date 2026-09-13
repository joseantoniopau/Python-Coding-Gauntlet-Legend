"""Shared test scaffolding. Every test runs against a throwaway data directory."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_SHARED_CORPUS = None


class GameTest(unittest.TestCase):
    """Builds the corpus once for the whole suite, then gives each test its own
    save file so state cannot leak between them."""

    @classmethod
    def setUpClass(cls):
        global _SHARED_CORPUS
        cls._tmp = Path(tempfile.mkdtemp(prefix="gauntlet-test-"))
        os.environ["GAUNTLET_DATA_DIR"] = str(cls._tmp)
        from gauntlet.corpus import build_all, write
        from gauntlet.corpus.validate import validate
        if _SHARED_CORPUS is None:
            problems = build_all()
            report = validate(problems)
            _SHARED_CORPUS = (report.accepted, report)
        cls.corpus, cls.report = _SHARED_CORPUS
        cls.corpus_path = cls._tmp / "corpus.json"
        write(cls.corpus, cls.corpus_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self.data_dir = Path(tempfile.mkdtemp(prefix="gauntlet-case-"))
        os.environ["GAUNTLET_DATA_DIR"] = str(self.data_dir)
        self.addCleanup(shutil.rmtree, self.data_dir, ignore_errors=True)

    def game(self):
        from gauntlet.engine import Game
        return Game(db_path=self.data_dir / "save.sqlite3",
                    corpus_path=self.corpus_path)

    def stand_where(self, game, boss_id):
        """Walk to the region a boss lives in, and prove the road exists.

        `Game.start_boss` refuses a boss the player is not standing in front of
        — the reason is written there, and it is what makes
        `story._places_proved` true rather than hopeful. A test that wants a
        fight therefore has to make the journey a player makes, and this walks
        it route by route rather than assigning the region, so a road that
        closed would fail the test that depends on it instead of being skipped.
        """
        from gauntlet import progression, world
        boss = world.BOSS_BY_ID[boss_id]
        here = game.state["player"]["region"]
        if boss["region"] == here:
            return []
        prog = progression.snapshot(game.state, game.skills,
                                    readiness=game._readiness())
        path = progression.path_between(prog, here, boss["region"])
        self.assertTrue(path, f"no open road from {here} to {boss['region']}")
        for route_id in path:
            out = game.travel(route_id)
            self.assertNotIn("error", out, f"{route_id}: {out.get('error')}")
        self.assertEqual(game.state["player"]["region"], boss["region"])
        return path

    def by_id(self, problem_id):
        for p in self.corpus:
            if p.id == problem_id:
                return p
        raise KeyError(problem_id)
