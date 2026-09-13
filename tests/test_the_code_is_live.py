"""A rebuilt game must be the game the player actually runs.

THE BUG THIS EXISTS TO CATCH, and it wasted a player's evening: static assets
were served `Cache-Control: public, max-age=3600` with NO ETag and NO
Last-Modified. With no validator a browser does not revalidate — it serves its
stored copy outright for the hour. So a music fix that was measured working on
this machine was invisible to the person who reported the bug: they force-quit
the app, reloaded, and ran the same old JavaScript, because the cache lives on
disk in the app's own browser profile and force-quitting does not touch it.

The bug reported second ("is the code live?") was the better question.
"""

import http.client
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestStaticAssetsRevalidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ, GAUNTLET_NO_WINDOW="1")
        cls.proc = subprocess.Popen(
            [sys.executable, "-u", "run.py"], cwd=str(ROOT), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        cls.port = None
        deadline = time.time() + 180
        while time.time() < deadline:
            line = cls.proc.stdout.readline()
            if not line:
                break
            m = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
            if m:
                cls.port = int(m.group(1))
                break
        if cls.port is None:
            cls.proc.kill()
            raise unittest.SkipTest("the server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.kill()
        cls.proc.wait(timeout=10)

    def _head(self, path, extra=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        c.request("GET", path, headers=extra or {})
        r = c.getresponse()
        r.read()
        c.close()
        return r

    def test_javascript_carries_a_validator(self):
        """Without one, the browser never asks whether the code changed."""
        for path in ("/js/main.js", "/js/audio.js", "/css/game.css"):
            r = self._head(path)
            self.assertEqual(200, r.status, path)
            etag = r.getheader("ETag")
            self.assertTrue(etag, f"{path} has no ETag, so a stale copy is "
                                  "served for the whole max-age with no way "
                                  "for the player to know")
            cc = (r.getheader("Cache-Control") or "").lower()
            self.assertNotIn("max-age", cc,
                             f"{path} is cached by time rather than by "
                             f"validator: {cc!r}")

    def test_an_unchanged_file_costs_a_304(self):
        r = self._head("/js/audio.js")
        etag = r.getheader("ETag")
        again = self._head("/js/audio.js", {"If-None-Match": etag})
        self.assertEqual(304, again.status,
                         "revalidation should be cheap, or it will be removed")

    def test_a_changed_file_is_delivered_at_once(self):
        target = ROOT / "web" / "js" / "audio.js"
        before = self._head("/js/audio.js").getheader("ETag")
        stat = target.stat()
        try:
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
            after = self._head("/js/audio.js", {"If-None-Match": before})
            self.assertEqual(200, after.status,
                             "a rebuilt file must not be answered with 304")
            self.assertNotEqual(before, after.getheader("ETag"))
        finally:
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))


if __name__ == "__main__":
    unittest.main()
