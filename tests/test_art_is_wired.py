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


class TestTheEndingPlayerDrawsWhatTheServerSends(unittest.TestCase):
    """The same bug one layer in: the module is reachable, the scene arrives
    over the wire, and the renderer drops fields on the floor.

    THE REGRESSION THIS CAUGHT. The ending has two players — the pre-existing
    web/js/finaleui.js and the one main.js grew when `ending.resolve` started
    firing at the end of every interview run. The new one dropped
    `title_card.ribbon`, which is the single sentence that tells the two kinds
    of freedom apart ('11 BY YOUR HAND. 14 BY THE FALL OF IT.'), and it dropped
    `beat.rows`, which is the only place in the whole scene a captive is named:
    the roll-call beat played as one narrator sentence with none of the
    twenty-five names on screen. Both fields were on the wire the entire time.

    Two players of one scene may differ in style and must not differ about
    which fields of it exist, so this checks them against each other rather
    than against a hardcoded list — finale.py WIRING §8 is the contract both
    are written to.
    """

    # (the expression both renderers must contain, why it matters)
    FIELDS = (
        ("beat.rows", "the roll call's names — the only place in the scene a "
                      "captive is named at all"),
        ("c.ribbon", "the sentence that separates 'by your hand' from 'by the "
                     "fall of it'"),
    )

    def test_both_players_read_the_same_fields_of_the_scene(self):
        main = (JS / "main.js").read_text()
        finaleui = (JS / "finaleui.js").read_text()
        for field, why in self.FIELDS:
            self.assertIn(field, finaleui,
                          f"finaleui.js stopped reading {field} — if the scene "
                          f"really dropped it, update this test and main.js "
                          f"together. It carried {why}.")
            self.assertIn(field, main,
                          f"main.js's ending player never reads {field}, which "
                          f"finaleui.js does: {why}. The server sends it and no "
                          f"screen shows it.")

    def test_the_ending_layer_has_somewhere_to_put_the_names(self):
        """`beat.rows` being read is not enough; there has to be an element to
        draw them into. finaleui.js has #fin-rail and main.js needs its own."""
        main = (JS / "main.js").read_text()
        self.assertIn('id="ed-rail"', main,
                      "main.js's ending layer has no name rail, so the roll "
                      "call has nowhere to land")
        rail = main.index('id="ed-rail"')
        beat = main.index("function showEndingBeat")
        self.assertLess(rail, main.index("function stopEndingCutscene"),
                        "the rail must be part of the ending layer's markup")
        self.assertIn("ed-rail", main[beat:],
                      "showEndingBeat never looks the rail up, so nothing is "
                      "ever drawn into it")


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
    # KNOWN ORPHAN, TRACKED ON PURPOSE — the schoolteacher's curriculum.
    #
    # Thessaly Brun's lessons: the editor, RUN versus CAST, the trials, the
    # belt, the Mender's free healing, Ferro's armour repair, the vendor, Orin
    # Tallow, the forge. It is data with no reader yet because the reader is
    # main.js and townui.js, and those were owned by another pass on the day it
    # was written.
    #
    # It is NOT dangerous to leave unwired the way ending.py was — nothing is
    # silently deleted by its absence; the player simply gets no lessons. But it
    # is the same failure mode this file exists to catch, so it is written down
    # rather than quietly excused. Wire it and delete this entry.
    "tutorial",
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
        # `cli` and `_harness` are reachable by other means. `ending` used to be
        # here as the one real orphan; engine.py imports it now — the four touch
        # points of ending.WIRING are wired — so it must NOT come back.
        self.assertIn("ending", seen,
                      "engine.py has stopped importing ending.py. resolve() "
                      "without stage() returns triggered:False forever, which "
                      "silently deletes the ending; the four touch points land "
                      "together or not at all.")
        self.assertNotIn("ending", PY_ALLOWED,
                         "ending.py is wired; it does not belong on the "
                         "orphan allowlist")
        # And the same rule for the newest entry: the moment anything imports
        # it, it stops being an allowed orphan and this test says so.
        if "tutorial" in PY_ALLOWED:
            self.assertNotIn("tutorial", seen,
                             "tutorial.py IS imported now — the curriculum is "
                             "reachable, so remove it from PY_ALLOWED")


# ------------------------------------------------- the first encounter
#
# THE BUG THIS EXISTS TO CATCH, found by starting a fresh game and looking at
# it: encounter one is a multiple-choice question, and it had no answers on
# screen. `renderMcq` appended the choices straight into #battle-side-body —
# a node `setTab` empties on every call — and `enterBattle` calls `setTab` four
# lines later. So the first thing a new player ever saw was a question, no CAST
# button (correctly hidden: the answers are the button), and nothing to click.
# Clicking any tab did the same thing to any MCQ, anywhere in the game.
#
# The fix was to make the choices what the trials tab IS for that encounter, so
# a repaint restores them instead of destroying them. These are cheap static
# checks; the real proof is driving it in a browser, but a source guard is what
# a future edit will actually trip over.

MAIN = JS / "main.js"


class TestTheFirstEncounterIsAnswerable(unittest.TestCase):
    def test_setTab_knows_about_mcq_choices(self):
        src = MAIN.read_text()
        self.assertIn("function setTab(", src)
        i = src.index("function setTab(")
        body = src[i:i + 1400]
        self.assertIn("G.mcq", body,
                      "setTab empties #battle-side-body and does not know an "
                      "MCQ owns it — the choices will be wiped")

    def test_renderMcq_does_not_paint_into_a_node_it_does_not_own(self):
        src = MAIN.read_text()
        i = src.index("function renderMcq(")
        body = src[i:src.index("\n}", i)]
        self.assertNotIn("battle-side-body", body,
                         "renderMcq is appending into the tab body again; "
                         "setTab will empty it on the next call")

    def test_an_mcq_stays_on_the_tab_that_shows_its_answers(self):
        src = MAIN.read_text()
        self.assertIn("G.mcq ? 'trials'", src,
                      "a measured-run MCQ would open on `approach`, hiding "
                      "the only way to answer it")


# --------------------------------------------------------------- the music
#
# THE BUG THIS EXISTS TO CATCH, reported by a player as "the music keeps
# looping the first couple of seconds":
#
# `_fadeOutRecording` retired a track with `el.src = ''`. An <audio> element
# treats an empty source as a LOAD FAILURE and fires `error` — and the error
# listener existed to recover from a real 404 or codec problem by calling
# play() again. So every crossfade ended with the outgoing track asking to be
# restarted, which restarted it, which crossfaded out the incoming one, which
# fired ITS error. Two tracks traded the same two seconds forever.
#
# Measured before the fix: 15 <audio> elements built in 10 seconds, two tracks
# playing at once, currentTime advancing 0.06s per 2.5s of wall clock. After:
# 2 elements, one playing, currentTime advancing in real time.
#
# The second test below is the cheap one that would have caught a separate bug
# in the same area: `audio.play('world')` — 'world' is not a track and not an
# alias, so it silently fell through to the synthesised rig and fought the
# recording.

AUDIO = JS / "audio.js"


def _music_names() -> set:
    src = AUDIO.read_text()
    keys = set(re.findall(r"^\s{2}(\w+): \{\n\s+file:", src, re.M))
    block = src[src.index("const MUSIC_ALIAS"):src.index("const MUSIC_BASE")]
    return keys | set(dict(re.findall(r"(\w+):\s*'(\w+)'", block)))


class TestTheMusicPlays(unittest.TestCase):
    def test_a_teardown_is_not_mistaken_for_a_load_failure(self):
        src = AUDIO.read_text()
        i = src.index("el.addEventListener('error'")
        handler = src[i:i + 320]
        self.assertIn("__retired", handler,
                      "the error listener will retry a track we retired on "
                      "purpose, which is an infinite crossfade loop")

    def test_nothing_retires_a_track_by_blanking_src(self):
        # Comments are skipped: the paragraph explaining this bug quotes the
        # very line it is warning about, and a test that cannot tell prose from
        # code would punish the explanation.
        offenders = []
        for n, line in enumerate(AUDIO.read_text().splitlines(), 1):
            bare = line.strip()
            if bare.startswith(("*", "//", "/*")):
                continue
            if ".src = ''" in bare or '.src = ""' in bare:
                offenders.append(f"{n}: {bare}")
        self.assertEqual([], offenders,
                         "setting src to '' fires an `error` event and the "
                         "listener will restart the track; use "
                         f"removeAttribute('src') + load(): {offenders}")

    def test_every_track_the_client_asks_for_exists(self):
        known = _music_names()
        self.assertIn("overworld", known, "the music table did not parse")
        bad = []
        for name in ("main.js", "finaleui.js", "overworld.js", "partyui.js"):
            f = JS / name
            if not f.is_file():
                continue
            for m in re.finditer(r"audio\.play\('([a-z_]+)'\)", f.read_text()):
                if m.group(1) not in known:
                    bad.append(f"{name}: '{m.group(1)}'")
        self.assertEqual([], bad,
                         "these fall through to the synthesised rig and fight "
                         f"whatever recording is playing: {bad}")


if __name__ == "__main__":
    unittest.main()
