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

    def by_id(self, problem_id):
        for p in self.corpus:
            if p.id == problem_id:
                return p
        raise KeyError(problem_id)
