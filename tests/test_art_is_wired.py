"""Every client module must be reachable from the page's entry point.

THE BUG THIS EXISTS TO CATCH, which really happened and shipped for a while:
web/js/monsterart.js was 3,859 lines of thematic per-region monster art, with
its own verify harness reporting 71 enemies over 17 regions and zero failures —
and *nothing imported it*. The game drew `slime` for every ordinary encounter in
all seventeen regions, which is exactly the complaint that caused the module to
be written. Passing harnesses said nothing, because a harness imports the module
directly.

So: a harness proves a module WORKS. This proves the game can REACH it.
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "web" / "js"
ENTRY = "main.js"

# Static `from './x.js'` and dynamic `import('./x.js')` both count as an edge.
EDGE = re.compile(r"""(?:from|import)\s*\(?\s*['"]\./([A-Za-z0-9_.-]+\.js)['"]""")

# Modules that are deliberately not reachable yet. Each needs a reason and an
# owner. Shrink this list; never grow it without one.
KNOWN_UNWIRED = set()


def edges(path: Path) -> set:
    return set(EDGE.findall(path.read_text()))


def reachable_from(entry: str) -> set:
    seen, stack = {entry}, [entry]
    while stack:
        cur = stack.pop()
        p = JS / cur
        if not p.is_file():
            continue
        for nxt in edges(p):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


class TestEveryModuleIsReachable(unittest.TestCase):
    def test_entry_point_is_the_one_the_page_loads(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn(f"/js/{ENTRY}", html,
                      "index.html no longer loads main.js; update ENTRY")

    def test_no_orphaned_client_modules(self):
        on_disk = {p.name for p in JS.glob("*.js")}
        orphans = on_disk - reachable_from(ENTRY) - KNOWN_UNWIRED
        self.assertEqual(
            set(), orphans,
            "unreachable from main.js — built, possibly harness-verified, and "
            f"dead to the player: {sorted(orphans)}")

    def test_allowlist_does_not_rot(self):
        """A module that got wired must leave KNOWN_UNWIRED, or the list stops
        meaning anything and the next real orphan hides behind it."""
        on_disk = {p.name for p in JS.glob("*.js")}
        reach = reachable_from(ENTRY)
        for name in sorted(KNOWN_UNWIRED):
            self.assertIn(name, on_disk,
                          f"{name} is allowlisted but no longer exists")
            self.assertNotIn(name, reach,
                             f"{name} IS reachable now — remove it from "
                             "KNOWN_UNWIRED")

    def test_the_monster_art_is_actually_drawn(self):
        """The specific regression: the thematic bestiary must be on the draw
        path for both venues, and nothing may draw a hardcoded species."""
        overworld = (JS / "overworld.js").read_text()
        fx = (JS / "fx.js").read_text()
        for name, src in (("overworld.js", overworld), ("fx.js", fx)):
            self.assertIn("monsterart", src, f"{name} does not use monsterart")
        self.assertNotIn("'elite' ? 'construct' : 'slime'", overworld,
                         "overworld is hardcoding a species again")


# ---------------------------------------------------------------- the server
#
# The same bug has now bitten the Python side twice: gauntlet/unmaking.py was
# written, tested and imported by nothing, and gauntlet/ending.py still is. A
# module nobody imports is a module the player cannot reach, however green its
# own tests are.

GAUNTLET = ROOT / "gauntlet"

# Reachable without an `import` naming them. Each needs a reason.
PY_ALLOWED = {
    # Executed as a FILE in the sandbox subprocess, never imported. That is the
    # whole point of it — it runs on the other side of the isolation boundary.
    "_harness",
    # run.py imports it inside main(), which is a call this AST walk of
    # gauntlet/ deliberately does not follow.
    "cli",
    # KNOWN ORPHAN, TRACKED ON PURPOSE.
    #
    # ending.py is the seam that tells a practical walked through the Standing
    # Portal apart from one sat from the menu, so that the captives-freed
    # cutscene is the reward for the ENDING rather than for any FINAL_EXAM run.
    # The reward itself is NOT missing: engine.finish_interview already plays
    # finale_scene on every exam.
    #
    # It is four touch points (see ending.WIRING): a DEFAULT_STATE key, a
    # stage() at the portal, a resolve() replacing the `if was_exam` block, and
    # a client path that starts the exam as staged. It must be wired ALL AT
    # ONCE — resolve() without stage() returns triggered:False forever and
    # would silently delete the ending — and its own contract names the failure
    # mode: staging from the menu path "would collapse the two exams into one".
    "ending",
}


def py_modules() -> set:
    return {p.stem for p in GAUNTLET.glob("*.py")} - {"__init__"}


def py_imported() -> set:
    mods, seen = py_modules(), set()
    for path in list(GAUNTLET.glob("*.py")) + [ROOT / "run.py"]:
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in mods:
                    seen.add(node.module)
                for alias in node.names:
                    if alias.name in mods:
                        seen.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    tail = alias.name.split(".")[-1]
                    if tail in mods:
                        seen.add(tail)
    return seen


class TestEveryServerModuleIsReachable(unittest.TestCase):
    def test_no_orphaned_gauntlet_modules(self):
        orphans = py_modules() - py_imported() - PY_ALLOWED
        self.assertEqual(
            set(), orphans,
            "nothing in gauntlet/ imports these, so the player cannot reach "
            f"them however green their own tests are: {sorted(orphans)}")

    def test_the_python_allowlist_does_not_rot(self):
        mods, seen = py_modules(), py_imported()
        for name in sorted(PY_ALLOWED):
            self.assertIn(name, mods, f"{name} is allowlisted but is gone")
        # `cli` and `_harness` are reachable by other means; `ending` is the one
        # entry that is a real orphan, and it must leave this list when wired.
        self.assertNotIn("ending", seen,
                         "ending.py is imported now — wire all four touch "
                         "points, then remove it from PY_ALLOWED")


if __name__ == "__main__":
    unittest.main()
