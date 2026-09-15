"""The first lesson, held to every claim gauntlet/tutorial.py makes about it.

Nothing here builds a Game. This is a pure data layer, and a test that spent
thirty seconds building a corpus to prove a dict would be testing the wrong
thing. The one place the corpus is touched is the refusal vocabulary, which
tutorial.validate() imports for itself.

Eleven properties decide whether this layer is correct, and each has a section.

  THE DESIGN IS THE CONTRACT   docs/13-the-first-lesson.md §5.3 is PARSED, and
                               every numbered entry in it is either a beat or a
                               declared handoff — and every line she says, and
                               every phrase she teaches, is compared word for
                               word against the data. A lesson dropped from the
                               data, or prose corrected in one place and not the
                               other, fails here rather than being noticed by a
                               player.
  THE CURRICULUM WALKS         all twenty-four taught start to finish, pending
                               shrinking by exactly one each time, ending empty.
  A LESSON TAUGHT IS TAUGHT    the second call returns {} and writes NOTHING —
                               compared as serialised bytes, not as a feeling.
  THE BOARD                    with the teacher swept away every unfired beat
                               still arrives, as one chalk line in a toast; and
                               after final_release her voice comes back.
  AN OLD SAVE IS FINE          None, {}, the wrong type in every slot and a save
                               written before this file existed all answer, and
                               none of them raises.
  IT NEVER ASKS THE SEAL       no module-level import of finalexam, no call to
                               sealed() anywhere in the AST, and a measured run
                               teaches nothing and writes nothing.
  IT ROUND-TRIPS               every state and every return survives json.dumps.
  THE GATES FAIL CLOSED        every gated entry point called with NO keyword
                               arguments refuses and writes nothing — and the
                               one call the engine can actually make still
                               teaches. Both halves, because a gate closed on
                               the only caller is the same bug wearing a safer
                               face.
  NO BEAT NAMES A PROBLEM      the refusal is measured against the real shapes
                               of the corpus's ids, and mutation-tested to
                               fail on each of them.
  THE NUMBERS ARE THE CODE'S   every count in her mouth — nine rungs, eleven
                               metals, six counters, fourteen keys, rung seven,
                               three sealed tabs — is read off the module that
                               owns it, so a beat cannot go on being confidently
                               wrong about its own subject.
  EVERY SCREEN HAS AN OWNER    the other half of "one feature, one lesson":
                               the buttons on the first frame of play are
                               counted against the curriculum, not the
                               curriculum against itself.

Run from tests/:  python3 -m unittest test_tutorial
"""
from __future__ import annotations

import ast
import copy
import json
import re
import unittest
from pathlib import Path

import base  # noqa: F401  — puts the repo on sys.path

from gauntlet import captives, config, tutorial, world
from gauntlet import zonecompanions as zc

MODULE = Path(base.REPO) / "gauntlet" / "tutorial.py"
DESIGN = Path(base.REPO) / "docs" / "13-the-first-lesson.md"


def blank() -> dict:
    """The smallest save that is still a save. Deliberately does NOT contain
    tutorial.LESSON_KEY: every test here starts from a save written before this
    module existed."""
    return {"cleared_bosses": [], "dungeons_cleared": [], "inventory": [],
            "world": {"routes_walked": []},
            "captives": captives.new_captive_state()}


def swept() -> dict:
    """A save at the Examiner's sweep: the Bug Demon down and the ladder
    essentially walked, which is the whole of zonecompanions.sweep_fired."""
    state = blank()
    others = [b["id"] for b in world.BOSSES
              if b["id"] not in (zc.SWEEP_AFTER_BOSS, "the_interviewer")]
    state["cleared_bosses"] = ([zc.SWEEP_AFTER_BOSS]
                               + others[:zc.SWEEP_MIN_RUNGS - 1])
    assert zc.sweep_fired(state), "the sweep fixture stopped firing"
    return state


# ---------------------------------------------------------------------------
# EVERY GATE IN tutorial.py FAILS CLOSED, so a bare `teach(state, id)`
# is answered with {} and writes nothing. That is the point of the defaults and
# it is tested by name in `TheGatesFailClosed` below, which calls the module
# directly. Everywhere else in this file the subject is Adventure Mode with no
# run open, so it gets three helpers rather than two keyword arguments on forty
# call sites — and the helpers pass the arguments explicitly, which is what the
# engine does too.

ADVENTURE = {"mode": config.MODE_ADVENTURE, "run_open": False}


def teach(state, beat_id, **kw) -> dict:
    return tutorial.teach(state, beat_id, **{**ADVENTURE, **kw})


def cue_note(state, kind, control_id, **kw) -> dict:
    return tutorial.cue_note(state, kind, control_id,
                             **{"run_open": False, **kw})


def forget(state, **kw) -> dict:
    return tutorial.forget(state, **{"run_open": False, **kw})


def cueable(state, control_id, **kw) -> bool:
    return tutorial.cueable(state, control_id, **{**ADVENTURE, **kw})


def teach_all(state: dict) -> list:
    return [teach(state, bid) for bid in tutorial.ORDER]


# ---------------------------------------------------------------------------

class TheDesignIsTheContract(unittest.TestCase):
    """docs/13 §5.3 numbers twenty-one entries. This file must account for all
    twenty-one, and for no more."""

    @classmethod
    def setUpClass(cls):
        text = DESIGN.read_text(encoding="utf-8")
        section = text.split("### 5.3 The beats")[1].split("### 5.4")[0]
        cls.entries = []
        for match in re.finditer(r"^\*\*(\d+) · (.+?)\*\*", section, re.M):
            ids = re.findall(r"`([a-z_]+)`", match.group(2))
            tail = section[match.end():match.end() + 80]
            cls.entries.append((int(match.group(1)), ids,
                                "HANDED OFF" in tail))

    def test_the_document_still_parses(self):
        self.assertEqual(len(self.entries), 30,
                         "docs/13 §5.3 no longer lists thirty numbered "
                         "entries; the data and the design have diverged")

    def test_every_numbered_entry_is_a_beat_or_a_declared_handoff(self):
        handoffs = {h.order for h in tutorial.HANDOFFS}
        beats = {row.order: row.id for row in tutorial.BEATS}
        for number, ids, is_handoff in self.entries:
            with self.subTest(beat=number):
                if is_handoff:
                    self.assertIn(number, handoffs,
                                  f"beat {number} is handed off in the design "
                                  f"and is not recorded in HANDOFFS, so a "
                                  f"reader counting the numbering finds a hole")
                    self.assertNotIn(number, beats,
                                     f"beat {number} is somebody else's prose "
                                     f"and must not be re-implemented here")
                else:
                    self.assertIn(number, beats,
                                  f"the design teaches beat {number} ({ids}) "
                                  f"and this file does not")
                    self.assertEqual(beats[number], ids[0],
                                     f"beat {number} is {ids[0]!r} in the "
                                     f"design")

    def test_the_prose_in_the_design_is_the_prose_in_the_data(self):
        """The numbers were not the only thing that drifted.

        §5.3 quotes every line she says. If the data is edited and the
        document is not, the next reader is working from prose no player will
        ever hear — which is how "every region leaves a different metal"
        survived in two places at once.
        """
        text = DESIGN.read_text(encoding="utf-8")
        section = text.split("### 5.3 The beats")[1].split("### 5.4")[0]
        chunks = re.split(r"^\*\*(\d+) · ", section, flags=re.M)[1:]
        entries = dict(zip((int(n) for n in chunks[::2]), chunks[1::2]))
        squash = lambda t: " ".join(t.split())
        heads = dict(re.findall(r"^\*\*(\d+) · .+?\*\*(.*)$", section, re.M))
        checked = 0
        for row in tutorial.BEATS:
            body = entries.get(row.order)
            self.assertIsNotNone(body, f"{row.id} has no §5.3 entry")
            taught = re.search(r"\*teaches: (.+?)\*", heads.get(str(row.order), ""))
            self.assertTrue(taught, f"{row.id}: §5.3 names no `teaches`")
            self.assertEqual(taught.group(1), row.teaches,
                             f"§5.3 and BEATS disagree about what {row.id} "
                             f"teaches")
            quoted = [line[1:].strip() for line in body.splitlines()
                      if line.startswith(">")]
            if not any(quoted):
                continue          # the_last_lesson defers to §6
            paragraphs, current = [], []
            for line in quoted:
                if line:
                    current.append(line)
                elif current:
                    paragraphs.append(squash(" ".join(current)))
                    current = []
            if current:
                paragraphs.append(squash(" ".join(current)))
            with self.subTest(beat=row.id):
                self.assertEqual(paragraphs, [squash(x) for x in row.lines],
                                 f"§5.3 and BEATS disagree about what "
                                 f"{row.id} says")
                board = re.search(r"^`board:` \*(.+)\*$", body, re.M)
                self.assertTrue(board, f"{row.id} has no board line in §5.3")
                self.assertEqual(squash(board.group(1)), squash(row.board))
                checked += 1
        self.assertGreaterEqual(checked, len(tutorial.BEATS) - 1)

    def test_no_beat_exists_that_the_design_never_asked_for(self):
        designed = {ids[0] for _, ids, handoff in self.entries if not handoff}
        self.assertEqual({row.id for row in tutorial.BEATS}, designed)

    def test_every_feature_has_exactly_one_lesson(self):
        phrases = [row.teaches for row in tutorial.BEATS]
        self.assertEqual(len(phrases), len(set(phrases)),
                         "two beats teach the same idea; one idea, one lesson")
        # Every counter in townui.TABS, which is five and not four: the beat
        # that promises "I will introduce you to each as you reach it" is only
        # true if this loop covers the whole tab list.
        for counter in ("mender", "smith", "shelf", "broker", "voices"):
            hits = [r for r in tutorial.BEATS if r.id == "town_" + counter]
            self.assertEqual(len(hits), 1,
                             f"the {counter} counter needs exactly one lesson")
        # And the four the request named in its own words.
        for idea in ("the_forge", "the_belt", "gear", "the_square_panel"):
            self.assertIn(idea, tutorial.BY_ID)

    def test_the_data_validates(self):
        self.assertEqual(tutorial.validate(), [])
        self.assertEqual(tutorial.self_check()["beats"], 24)

    def test_twenty_four_beats_six_handoffs_and_no_gap(self):
        counts = tutorial.counts()
        self.assertEqual(counts["beats"], 24)
        self.assertEqual(counts["handoffs"], 6)
        self.assertEqual(counts["numbered"], 30)


# ---------------------------------------------------------------------------

class TheCurriculumWalks(unittest.TestCase):

    def test_start_to_finish_shrinking_by_exactly_one(self):
        state = blank()
        self.assertEqual(len(tutorial.pending(state)), len(tutorial.BEATS),
                         "a save that has never been taught anything is owed "
                         "the whole curriculum")
        for step, beat_id in enumerate(tutorial.ORDER, 1):
            before = len(tutorial.pending(state))
            out = teach(state, beat_id)
            self.assertTrue(out, f"{beat_id} taught nothing on a fresh save")
            self.assertEqual(out["id"], beat_id)
            self.assertEqual(len(tutorial.pending(state)), before - 1,
                             f"{beat_id} did not shrink pending by exactly one")
            self.assertEqual(out["remaining"], before - 1)
        self.assertEqual(tutorial.pending(state), [])

    def test_every_beat_arrives_in_a_shape_the_client_can_play(self):
        state = blank()
        for beat_id in tutorial.ORDER:
            out = teach(state, beat_id)
            with self.subTest(beat=beat_id):
                self.assertIn(out["channel"], tutorial.CHANNELS)
                self.assertIn(out["speaker"], tutorial.SPEAKERS)
                self.assertTrue(out["lines"])
                if out["channel"] == tutorial.CHANNEL_TOAST:
                    self.assertEqual(len(out["lines"]), 1)
                    self.assertTrue(out["title"])
                else:
                    self.assertLessEqual(len(out["lines"]),
                                         tutorial.SAY_LINES_MAX)
                    self.assertEqual(out["portrait"],
                                     tutorial.TEACHER_PORTRAIT)

    def test_a_lesson_is_offered_and_never_blocks(self):
        state = blank()
        for beat_id in tutorial.ORDER:
            self.assertFalse(teach(state, beat_id)["blocks_input"],
                             "a lesson the player has to dismiss to keep "
                             "playing is a modal, and she does not do those")

    def test_an_unknown_id_teaches_nothing_and_writes_nothing(self):
        state = blank()
        before = json.dumps(state, sort_keys=True)
        self.assertEqual(teach(state, "the_thing_i_made_up"), {})
        self.assertEqual(teach(state, ""), {})
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_order_is_authored_not_emergent(self):
        numbers = [tutorial.BY_ID[b].order for b in tutorial.ORDER]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(tutorial.ORDER[0], "the_square")
        self.assertEqual(tutorial.ORDER[-1], tutorial.LAST_LESSON_ID)


# ---------------------------------------------------------------------------

class ALessonTaughtIsTaught(unittest.TestCase):

    def test_the_second_call_returns_nothing_and_writes_nothing(self):
        state = blank()
        first = teach(state, "the_fight")
        self.assertTrue(first)
        after_first = json.dumps(state, sort_keys=True)
        for _ in range(5):
            self.assertEqual(teach(state, "the_fight"), {})
        self.assertEqual(json.dumps(state, sort_keys=True), after_first,
                         "a repeated trigger changed the save; the call site "
                         "is supposed to be able to fire on every frame")

    def test_taught_is_pure_and_total(self):
        state = blank()
        self.assertFalse(tutorial.taught(state, "the_fight"))
        self.assertFalse(tutorial.taught(state, "not_a_beat"))
        self.assertFalse(tutorial.taught(None, "the_fight"))
        teach(state, "the_fight")
        self.assertTrue(tutorial.taught(state, "the_fight"))

    def test_teach_me_again_clears_the_latch_and_the_counters(self):
        state = blank()
        teach_all(state)
        cue_note(state, "shown", "run")
        cue_note(state, "used", "cast")
        self.assertEqual(tutorial.pending(state), [])
        cleared = forget(state)
        self.assertEqual(cleared["cleared"]["beats"], len(tutorial.BEATS))
        self.assertEqual(len(tutorial.pending(state)), len(tutorial.BEATS))
        self.assertEqual(tutorial.cue_state(state)["shown"], {})
        self.assertEqual(tutorial.cue_state(state)["used"], {})
        # and the whole curriculum walks again
        self.assertTrue(all(teach_all(state)))


# ---------------------------------------------------------------------------

class TheBoard(unittest.TestCase):
    """A lesson she never reached is not lost and is not dumped."""

    def test_before_the_sweep_she_speaks(self):
        self.assertEqual(tutorial.speaker(blank()), tutorial.SPEAKER_THESSALY)

    def test_after_the_sweep_the_board_speaks(self):
        self.assertEqual(tutorial.speaker(swept()), tutorial.SPEAKER_BOARD)

    def test_an_untaught_curriculum_survives_the_teacher(self):
        state = swept()
        delivered = 0
        for beat_id in tutorial.ORDER:
            row = tutorial.BY_ID[beat_id]
            out = teach(state, beat_id)
            if beat_id == tutorial.LAST_LESSON_ID:
                continue
            with self.subTest(beat=beat_id):
                self.assertTrue(out, f"{beat_id} was lost at the sweep")
                self.assertEqual(out["speaker"], tutorial.SPEAKER_BOARD)
                self.assertEqual(out["channel"], tutorial.CHANNEL_TOAST,
                                 "the board is a wall; it cannot hold a "
                                 "dialogue")
                self.assertEqual(out["lines"], [row.board],
                                 "exactly one chalk line, which is what a "
                                 "board holds")
                self.assertEqual(out["portrait"], "")
                self.assertEqual(out["who"], tutorial.BOARD_NAME)
                delivered += 1
        self.assertEqual(delivered, len(tutorial.BEATS) - 1)

    def test_the_trigger_and_the_latch_are_unchanged_by_the_sweep(self):
        walking, board = blank(), swept()
        # The sweep changes the SPEAKER and the CHANNEL. It changes nothing
        # about when a beat fires or how it is remembered.
        for beat_id in tutorial.ORDER:
            before, after = (tutorial.view(walking, beat_id),
                             tutorial.view(board, beat_id))
            self.assertEqual(before["trigger"], after["trigger"])
            self.assertEqual(before["taught"], after["taught"])
            self.assertEqual(before["id"], after["id"])
            if beat_id != tutorial.LAST_LESSON_ID:
                self.assertNotEqual(before["speaker"], after["speaker"],
                                    f"{beat_id} did not change speaker")
                self.assertEqual(after["channel"], tutorial.CHANNEL_TOAST)
        teach(board, "the_belt")
        self.assertTrue(tutorial.taught(board, "the_belt"))
        self.assertFalse(tutorial.taught(walking, "the_belt"))
        # a beat taught before the sweep is not re-taught by the board
        teach(walking, "the_belt")
        walking["cleared_bosses"] = swept()["cleared_bosses"]
        self.assertEqual(teach(walking, "the_belt"), {})

    def test_the_last_lesson_never_moves_to_the_board(self):
        state = swept()
        row = tutorial.BY_ID[tutorial.LAST_LESSON_ID]
        self.assertEqual(row.board, "",
                         "the one beat with no chalk line, on purpose")
        out = teach(state, tutorial.LAST_LESSON_ID)
        self.assertTrue(out, "her goodbye became unreachable")
        self.assertEqual(out["speaker"], tutorial.SPEAKER_THESSALY,
                         "the board cannot say goodbye")
        self.assertEqual(out["channel"], tutorial.CHANNEL_SAY)

    def test_she_comes_home_and_her_voice_comes_with_her(self):
        state = swept()
        self.assertEqual(tutorial.speaker(state), tutorial.SPEAKER_BOARD)
        captives.final_release(state)
        self.assertEqual(tutorial.speaker(state), tutorial.SPEAKER_THESSALY)
        out = teach(state, "gear")
        self.assertEqual(out["speaker"], tutorial.SPEAKER_THESSALY)
        self.assertEqual(out["channel"], tutorial.CHANNEL_SAY)
        self.assertEqual(out["lines"], list(tutorial.BY_ID["gear"].lines))

    def test_every_beat_but_one_carries_a_chalk_line(self):
        boardless = [r.id for r in tutorial.BEATS if not r.board]
        self.assertEqual(boardless, [tutorial.LAST_LESSON_ID])
        for row in tutorial.BEATS:
            if row.board:
                self.assertNotIn("\n", row.board)
                self.assertLess(len(row.board), 140,
                                f"{row.id}: a board holds a line, not a speech")


# ---------------------------------------------------------------------------

class TheLastLesson(unittest.TestCase):

    def test_the_count_is_the_only_interpolation(self):
        hits = [line for row in tutorial.BEATS
                for line in row.lines + row.alt_lines + (row.board,)
                if tutorial.COUNT_TOKEN in line]
        self.assertEqual(len(hits), 1, "a number hard-coded into authored "
                                       "prose is a number that goes wrong")

    def test_a_schoolteacher_can_count(self):
        self.assertEqual(tutorial._fill("{n} things", 1), "1 thing")
        self.assertEqual(tutorial._fill("{n} things", 2), "2 things")
        self.assertEqual(tutorial._fill("{n} things", 0), "0 things")

    def test_the_variant_with_something_left(self):
        state = blank()
        teach(state, "the_square")
        out = teach(state, tutorial.LAST_LESSON_ID)
        self.assertIn("still a list on that board", out["lines"][0])
        self.assertNotIn(tutorial.COUNT_TOKEN, out["lines"][0])
        self.assertIn(str(len(tutorial.BEATS) - 2), out["lines"][0],
                      "the count excludes the beat doing the counting")

    def test_the_variant_with_nothing_left(self):
        state = blank()
        for beat_id in tutorial.ORDER:
            if beat_id != tutorial.LAST_LESSON_ID:
                teach(state, beat_id)
        out = teach(state, tutorial.LAST_LESSON_ID)
        self.assertIn("nothing left on that board", out["lines"][0])

    def test_the_singular_reads_as_a_singular(self):
        state = blank()
        for beat_id in tutorial.ORDER:
            if beat_id not in (tutorial.LAST_LESSON_ID, "the_belt"):
                teach(state, beat_id)
        out = teach(state, tutorial.LAST_LESSON_ID)
        self.assertIn("1 thing,", out["lines"][0])
        self.assertNotIn("1 things", out["lines"][0])


# ---------------------------------------------------------------------------

class AnOldSaveIsFine(unittest.TestCase):
    """A save is a file on somebody's disk. It can be old, half-written, or
    edited by hand by a player who wanted to see what happened."""

    BROKEN = (
        None,
        {},
        "not a save at all",
        [],
        {"lessons": None},
        {"lessons": []},
        {"lessons": "taught"},
        {"lessons": {"beats": "the_square"}},
        {"lessons": {"beats": [1, 2, None], "cue": "gone"}},
        {"lessons": {"beats": ["the_square"], "cue": {"shown": [], "used": 7}}},
        {"lessons": {"cue": {"shown": {"run": "three"}, "used": {"run": -4}}}},
        {"lessons": {"cue": {"shown": {"run": True}}}},
    )

    def test_nothing_raises_on_any_of_them(self):
        for save in self.BROKEN:
            with self.subTest(save=repr(save)[:40]):
                state = copy.deepcopy(save)
                tutorial.taught(state, "the_square")
                tutorial.pending(state)
                tutorial.speaker(state)
                tutorial.cue_state(state)
                tutorial.cue_retired(state, "run")
                tutorial.snapshot(state)
                tutorial.view(state, "the_square")
                tutorial.lines_for(state, "the_square")

    def test_a_save_written_before_this_file_existed_is_owed_everything(self):
        state = blank()
        self.assertNotIn(tutorial.LESSON_KEY, state)
        self.assertEqual(len(tutorial.pending(state)), len(tutorial.BEATS))
        self.assertEqual(tutorial.cue_state(state)["shown"], {})
        self.assertEqual(tutorial.cue_state(state)["retired"], [])

    def test_a_damaged_block_heals_on_the_next_write(self):
        state = {"lessons": {"beats": "nonsense",
                             "cue": {"shown": 5, "used": {"run": "x"}}}}
        out = teach(state, "the_square")
        self.assertTrue(out)
        block = state[tutorial.LESSON_KEY]
        self.assertEqual(block["beats"], ["the_square"])
        self.assertEqual(block["cue"]["shown"], {})
        self.assertEqual(block["cue"]["used"], {})

    def test_a_non_dict_save_is_never_written_to(self):
        for save in (None, "x", [], 3):
            self.assertEqual(teach(save, "the_square"), {})
            self.assertEqual(cue_note(save, "shown", "run"), {})

    def test_new_lesson_state_is_the_shape_default_state_gets(self):
        fresh = tutorial.new_lesson_state()
        self.assertEqual(fresh, {"beats": [], "cue": {"shown": {}, "used": {}}})
        self.assertEqual(json.loads(json.dumps(fresh)), fresh)


# ---------------------------------------------------------------------------

class ItNeverAsksTheSeal(unittest.TestCase):
    """This is a story-and-interface layer. The exam is a measurement. They do
    not touch, and the gate is ONE gate rather than a per-lesson opinion."""

    @classmethod
    def setUpClass(cls):
        cls.source = MODULE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_finalexam_is_not_a_module_level_import(self):
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn("finalexam", alias.name)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn("finalexam", node.module or "")
                for alias in node.names:
                    self.assertNotIn("finalexam", alias.name)

    def test_sealed_is_never_called_anywhere_in_the_file(self):
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.attr if isinstance(func, ast.Attribute)
                    else getattr(func, "id", ""))
            self.assertNotEqual(name, "sealed",
                                "tutorial.py asked the seal; the gate is "
                                "available_in() and there is no second one")

    def test_the_gate_is_the_gate_captives_already_uses(self):
        self.assertFalse(tutorial.available_in(config.MODE_INTERVIEW))
        self.assertTrue(tutorial.available_in(config.MODE_ADVENTURE))
        body = self.source.split("def available_in(")[1].split("\ndef ")[0]
        self.assertIn("captives.available_in", body,
                      "available_in must defer, not re-derive: three modules "
                      "answering the same question three ways is the thing "
                      "docs/10 was written about")

    def test_a_measured_run_teaches_nothing_and_writes_nothing(self):
        state = blank()
        before = json.dumps(state, sort_keys=True)
        for beat_id in tutorial.ORDER:
            self.assertEqual(
                teach(state, beat_id, mode=config.MODE_INTERVIEW), {})
        self.assertEqual(json.dumps(state, sort_keys=True), before,
                         "the latch is not byte-identical after a measured "
                         "run tried to learn something")
        self.assertEqual(len(tutorial.pending(state)), len(tutorial.BEATS))

    def test_an_open_run_teaches_nothing_even_in_adventure_mode(self):
        """The gap clause: a measured run is open BETWEEN two questions too."""
        state = blank()
        before = json.dumps(state, sort_keys=True)
        for beat_id in tutorial.ORDER:
            self.assertEqual(teach(state, beat_id,
                                            mode=config.MODE_ADVENTURE,
                                            run_open=True), {})
        self.assertEqual(json.dumps(state, sort_keys=True), before)
        self.assertFalse(tutorial.may_teach(config.MODE_ADVENTURE, True))
        self.assertTrue(tutorial.may_teach(config.MODE_ADVENTURE, False))

    def test_she_is_never_inside_an_encounter(self):
        self.assertEqual(tutorial._she_is_never_in_a_fight(), [])

    def test_no_beat_names_a_problem(self):
        self.assertEqual(tutorial._no_beat_names_a_problem(), [])

    def test_the_refusal_vocabulary_actually_loaded(self):
        """A refusal check that silently failed to import its own vocabulary
        is a check that passes everything."""
        from gauntlet.corpus import _FAMILIES
        from gauntlet.finalexam import CRUTCHES
        self.assertGreater(len(_FAMILIES), 20)
        self.assertGreater(len(CRUTCHES), 10)

    def test_the_refusals_bite(self):
        """Break each rule on purpose and watch the check catch it."""
        import dataclasses
        good = tutorial.BEATS
        base_row = good[0]
        cases = {
            "family name": {"lines": ("The sliding window is on the shelf.",)},
            "problem id": {"lines": ("Ask about arrays_hashing today.",)},
            "code": {"lines": ("Write return x and stop.",)},
            "complexity": {"lines": ("That one wants O(n) time.",)},
            "advice": {"lines": ("Use the hint when you are stuck.",)},
            "crutch": {"lines": ("Open the weakness map first.",)},
        }
        try:
            for name, patch in cases.items():
                with self.subTest(rule=name):
                    tutorial.BEATS = (dataclasses.replace(base_row, **patch),)
                    self.assertTrue(tutorial._no_beat_names_a_problem(),
                                    f"the {name} refusal did not fire")
        finally:
            tutorial.BEATS = good
        self.assertEqual(tutorial.validate(), [])


# ---------------------------------------------------------------------------

class TheCueCounters(unittest.TestCase):
    """Three times pointed at, or three times done, whichever comes first."""

    def test_three_shows_retire_a_control(self):
        state = blank()
        for n in range(1, tutorial.CUE_RETIRE_AT):
            cue_note(state, "shown", "run")
            self.assertFalse(tutorial.cue_retired(state, "run"), f"at {n}")
        out = cue_note(state, "shown", "run")
        self.assertEqual(out["shown"], tutorial.CUE_RETIRE_AT)
        self.assertTrue(out["retired"])
        self.assertTrue(tutorial.cue_retired(state, "run"))

    def test_three_uses_retire_a_control_with_shown_still_at_zero(self):
        """The competence signal: a player who finds RUN on their own never
        sees an arrow on it."""
        state = blank()
        for _ in range(tutorial.CUE_RETIRE_AT):
            cue_note(state, "used", "run")
        self.assertTrue(tutorial.cue_retired(state, "run"))
        self.assertEqual(tutorial.cue_state(state)["shown"], {})

    def test_the_two_counters_do_not_add_up(self):
        """Two shows and two uses is five short of nothing: each retires on
        its own at three, and neither borrows from the other."""
        state = blank()
        cue_note(state, "shown", "cast")
        cue_note(state, "shown", "cast")
        cue_note(state, "used", "cast")
        cue_note(state, "used", "cast")
        self.assertFalse(tutorial.cue_retired(state, "cast"))
        cue_note(state, "shown", "cast")
        self.assertTrue(tutorial.cue_retired(state, "cast"))

    def test_controls_retire_independently(self):
        state = blank()
        for _ in range(tutorial.CUE_RETIRE_AT):
            cue_note(state, "shown", "run")
        self.assertTrue(tutorial.cue_retired(state, "run"))
        self.assertFalse(tutorial.cue_retired(state, "cast"))

    def test_an_unknown_control_is_refused_rather_than_counted(self):
        state = blank()
        self.assertEqual(cue_note(state, "shown", "btn_flee"), {})
        self.assertEqual(cue_note(state, "shown", "the_first_choice"),
                         {})
        self.assertEqual(cue_note(state, "gestured", "run"), {})
        self.assertNotIn(tutorial.LESSON_KEY, state)
        self.assertTrue(tutorial.cue_retired(state, "btn_flee"),
                        "a control this file has never heard of is retired, "
                        "which is the safe answer")

    def test_the_refused_list_holds_the_ones_that_matter(self):
        refused = " ".join(r.target.lower() for r in tutorial.CUE_REFUSED)
        for shape in ("trial failed", "hidden trial", "mcq choice",
                      "spot_the_flaw", "complexity_match", "break_it",
                      "target_seconds", "measured run"):
            self.assertIn(shape.lower(), refused,
                          f"{shape} is not recorded as refused, and an "
                          f"unargued cue is the one that gets added back")
        for row in tutorial.CUE_REFUSED:
            self.assertTrue(row.why)

    def test_no_control_points_at_a_member_of_a_set(self):
        """The container rule. The choices, the code lines, the options and
        the six named edge cases are not in the registry and never will be."""
        selectors = " ".join(r.selector for r in tutorial.CUE_CONTROLS)
        for member in (".list-item", ".code-pick", ".inc-move", ".inc-enemy",
                       ".inc-hole", "puzzle-input", ".trace-row"):
            self.assertNotIn(member, selectors)

    def test_cueable_is_off_in_a_measured_run_and_off_when_switched_off(self):
        state = blank()
        self.assertTrue(cueable(state, "run"))
        self.assertFalse(cueable(state, "run",
                                          mode=config.MODE_INTERVIEW))
        self.assertFalse(cueable(state, "run", run_open=True))
        self.assertFalse(cueable(state, "run", setting_on=False))
        self.assertFalse(cueable(state, "not_a_control"))

    def test_the_policy_the_client_must_not_re_decide(self):
        policy = tutorial.cue_state(blank())["policy"]
        self.assertEqual(policy["retire_at"], 3)
        self.assertEqual(policy["per_encounter"], 2)
        self.assertEqual(policy["dwell_ms"][tutorial.KIND_CODE], 8000)
        self.assertEqual(policy["dwell_ms"][tutorial.KIND_MCQ], 2000)
        self.assertEqual(policy["setting"], "cues")

    def test_the_registry_is_servable(self):
        rows = tutorial.cue_registry()
        self.assertEqual(len(rows), len(tutorial.CUE_CONTROLS))
        self.assertEqual([r["id"] for r in rows[:2]], ["trials_tab", "run"],
                         "served in priority order, lowest first")
        for row in rows:
            self.assertTrue(row["selector"] and row["why"])
        self.assertEqual(json.loads(json.dumps(rows)), rows)


# ---------------------------------------------------------------------------

class ItRoundTrips(unittest.TestCase):

    def test_every_payload_survives_json(self):
        state = blank()
        payloads = [tutorial.snapshot(state), tutorial.cue_state(state)]
        for beat_id in tutorial.ORDER:
            payloads.append(tutorial.view(state, beat_id))
            payloads.append(teach(state, beat_id))
        payloads.append(cue_note(state, "shown", "run"))
        payloads.append(forget(state))
        payloads.append(tutorial.snapshot(swept()))
        for payload in payloads:
            with self.subTest(keys=sorted(payload)[:3]):
                self.assertEqual(json.loads(json.dumps(payload)), payload)

    def test_the_save_block_survives_json(self):
        state = blank()
        teach_all(state)
        cue_note(state, "shown", "run")
        cue_note(state, "used", "cast")
        block = state[tutorial.LESSON_KEY]
        self.assertEqual(json.loads(json.dumps(block)), block)
        # and a round-tripped save reads back identically
        reloaded = json.loads(json.dumps(state))
        self.assertEqual(tutorial.pending(reloaded), [])
        self.assertEqual(tutorial.cue_state(reloaded)["shown"], {"run": 1})

    def test_the_wiring_note_names_every_beat(self):
        """The next pass gets a work list, not a re-reading job."""
        for row in tutorial.BEATS:
            self.assertIn(row.id, tutorial.WIRING)
            self.assertIn(row.site.split(" · ")[0], tutorial.WIRING)


# ---------------------------------------------------------------------------

class TheGatesFailClosed(unittest.TestCase):
    """docs/13 §7.9 X7. The defaults are the gate, so they are tested as one.

    Every other class in this file goes through the helpers at the top, which
    pass Adventure Mode and a closed run explicitly. These call the module
    with no keyword arguments at all — the shape a forgetful engine writes, and
    the shape docs/13 §7.8 E2 used to instruct — and the answer must be
    silence and an untouched save.
    """

    def test_a_bare_teach_teaches_nothing_and_writes_nothing(self):
        state = blank()
        before = json.dumps(state, sort_keys=True)
        for beat_id in tutorial.ORDER:
            self.assertEqual(tutorial.teach(state, beat_id), {},
                             f"{beat_id} was taught by a call that named "
                             f"neither the mode nor the run")
        self.assertEqual(json.dumps(state, sort_keys=True), before,
                         "the save is not byte-identical after a bare teach()")
        self.assertNotIn(tutorial.LESSON_KEY, state)
        self.assertEqual(len(tutorial.pending(state)), len(tutorial.BEATS))

    def test_a_bare_cue_note_counts_nothing_and_writes_nothing(self):
        state = blank()
        before = json.dumps(state, sort_keys=True)
        for kind in ("shown", "used"):
            for control in tutorial.CUE_IDS:
                self.assertEqual(tutorial.cue_note(state, kind, control), {})
        self.assertEqual(json.dumps(state, sort_keys=True), before)
        self.assertNotIn(tutorial.LESSON_KEY, state)

    def test_a_bare_forget_clears_nothing(self):
        state = blank()
        teach_all(state)
        cue_note(state, "shown", "run")
        latched = json.dumps(state, sort_keys=True)
        self.assertEqual(tutorial.forget(state), {},
                         "TEACH ME AGAIN fired inside a measured run")
        self.assertEqual(json.dumps(state, sort_keys=True), latched)
        self.assertEqual(tutorial.pending(state), [])

    def test_a_bare_cueable_is_false_and_a_bare_may_teach_is_false(self):
        state = blank()
        for control in tutorial.CUE_IDS:
            self.assertFalse(tutorial.cueable(state, control))
        self.assertFalse(tutorial.may_teach())

    def test_the_gates_are_keyword_only(self):
        """A positional `True` in the wrong slot is how a gate gets inverted
        by a caller who was trying to hold it."""
        import inspect
        for func, after in ((tutorial.teach, 2), (tutorial.cueable, 2),
                            (tutorial.cue_note, 3), (tutorial.forget, 1)):
            params = list(inspect.signature(func).parameters.values())
            for extra in params[after:]:
                self.assertEqual(extra.kind, inspect.Parameter.KEYWORD_ONLY,
                                 f"{func.__name__}.{extra.name} can be passed "
                                 f"positionally")

    def test_the_open_run_refusal_still_bites_when_the_mode_is_adventure(self):
        state = blank()
        before = json.dumps(state, sort_keys=True)
        self.assertEqual(
            tutorial.teach(state, "the_square",
                           mode=config.MODE_ADVENTURE, run_open=True), {})
        self.assertEqual(
            tutorial.cue_note(state, "shown", "run", run_open=True), {})
        self.assertEqual(tutorial.forget(state, run_open=True), {})
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_run_open_false_alone_is_enough_to_teach(self):
        """The other half of the gate, and the half a fail-closed `mode`
        default would have broken.

        The engine has no mode string, so the only call it can make is
        `teach(state, id, run_open=self._run_is_open())`. If `mode` defaulted
        to a measured run as well, that call would return {} for every beat
        forever and the curriculum would be dead on arrival — silently, since
        {} is a legal answer. Both halves of the disjunction are tested here
        so neither can be flipped without the other being noticed.
        """
        state = blank()
        out = tutorial.teach(state, "the_square", run_open=False)
        self.assertTrue(out, "the only call the engine can make taught "
                             "nothing; check may_teach's `mode` default")
        self.assertEqual(out["id"], "the_square")
        self.assertEqual(tutorial.cue_note(state, "shown", "run",
                                           run_open=False)["shown"], 1)
        self.assertTrue(tutorial.cueable(state, "run", run_open=False))
        self.assertTrue(tutorial.forget(state, run_open=False)["cleared"])
        self.assertTrue(tutorial.may_teach(run_open=False))
        # and the mode gate is still a gate for a caller that holds one
        self.assertFalse(tutorial.may_teach(config.MODE_INTERVIEW, False))

    def test_the_wiring_note_never_tells_the_engine_to_read_a_mode(self):
        """Game has no `mode` attribute; the instructed call raised."""
        self.assertNotIn("self.mode", tutorial.WIRING)
        self.assertIn("run_open=self._run_is_open()", tutorial.WIRING)
        for name in ("lesson_note", "lessons_forget"):
            self.assertIn(name, tutorial.WIRING)


# ---------------------------------------------------------------------------

class NoBeatNamesAProblem(unittest.TestCase):
    """docs/13 §7.1 F12, held to the corpus's real id shapes.

    The refusal was an underscore test, and its own comment claimed every
    problem id in the project has one. Measured against the built corpus:
    1013 problem ids, 1013 with a hyphen, 24 with an underscore. So the check
    refused 24 and let 989 through.
    """

    # SHAPE-EQUIVALENT AND DELIBERATELY NOT REAL. A real problem id written as
    # a bare string literal anywhere under gauntlet/, tests/ or web/ is an id
    # `corpus.RESERVED` then has to carry — `corpus.named_in_source` scans for
    # exactly that and `validate()` errors on it, because a quest naming a
    # sealed problem either leaks the hold-out or dead-ends. This file is about
    # a refusal that fires on the SHAPE, so it uses invented ids with the
    # shape, and `test_the_shape_covers_every_id_the_corpus_actually_ships`
    # does the same job against the real ones without naming any of them.
    HYPHENATED = ("zz-alpha-beta", "qq-gamma", "xy-delta-epsilon-two",
                  "ab-one", "zzzz-nine-ten", "qq-a1-b2-c3")
    UNDERSCORED = ("zz-fixed_thing-market-1", "sliding_window",
                   "arrays_hashing")

    def _fires_on(self, line):
        import dataclasses
        good = tutorial.BEATS
        try:
            tutorial.BEATS = (dataclasses.replace(good[0], lines=(line,)),)
            return tutorial._no_beat_names_a_problem()
        finally:
            tutorial.BEATS = good

    def test_a_beat_carrying_a_real_problem_id_fails(self):
        for pid in self.HYPHENATED:
            with self.subTest(id=pid):
                self.assertTrue(
                    self._fires_on(f"Try {pid} when you are ready."),
                    f"{pid} is a shipped problem id and the refusal that "
                    f"docs/13 §7.1 F12 promises by name let it through")

    def test_the_invented_ids_are_invented(self):
        """A test that quietly started naming real problems would be the bug
        it is testing for."""
        from gauntlet import config as cfg
        path = cfg.corpus_path()
        if not path.exists():
            self.skipTest("no corpus built; nothing to measure against")
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["problems"] if isinstance(data, dict) else data
        real = {row["id"] for row in rows}
        for pid in self.HYPHENATED + self.UNDERSCORED:
            self.assertNotIn(pid, real)

    def test_the_underscore_half_still_fires(self):
        for pid in self.UNDERSCORED:
            with self.subTest(id=pid):
                self.assertTrue(self._fires_on(f"Ask about {pid} today."))

    def test_the_shape_covers_every_id_the_corpus_actually_ships(self):
        """Both halves together, against the ids themselves rather than
        against a memory of what they look like. Skipped rather than failed
        when the corpus has not been built on this machine: this file builds
        nothing, by design."""
        from gauntlet import config as cfg
        path = cfg.corpus_path()
        if not path.exists():
            self.skipTest("no corpus built; nothing to measure against")
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["problems"] if isinstance(data, dict) else data
        ids = [row["id"] for row in rows]
        self.assertGreater(len(ids), 300)
        missed = [i for i in ids
                  if not tutorial._PROBLEM_ID_SHAPE.search(i) and "_" not in i]
        self.assertEqual(missed, [],
                         "these ids would pass straight through a beat")

    def test_the_authored_curriculum_contains_no_hyphen_at_all(self):
        """Why the shape rule is affordable: she does not use hyphens."""
        for row in tutorial.BEATS:
            with self.subTest(beat=row.id):
                self.assertNotIn("-", tutorial._beat_text(row))


# ---------------------------------------------------------------------------

class TheNumbersAreTheCodesNumbers(unittest.TestCase):
    """Every count in her mouth, read off the module that owns it.

    A schoolteacher who is confidently wrong about her own square is worse
    than one who says nothing, and five of these were wrong: five counters in
    a square with six, every region leaving a different metal in a game with
    eleven metals over sixteen regions and none here, the bosses taking five
    panels when they take three, rung five for a crutch taken at rung seven,
    and one key opening a screen no key opens.
    """

    WEB = Path(base.REPO) / "web"

    def text(self, beat_id):
        return tutorial._beat_text(tutorial.BY_ID[beat_id])

    def test_nine_rungs_is_forge_max_tier(self):
        from gauntlet import forge
        self.assertEqual(forge.MAX_TIER, 9)
        self.assertIn("Nine rungs", self.text("the_forge"))

    def test_eleven_metals_over_sixteen_regions_and_none_from_here(self):
        from gauntlet import forge
        used = set(forge.REGION_METAL.values())
        shared = [m for m in used
                  if list(forge.REGION_METAL.values()).count(m) > 1]
        self.assertEqual(len(forge.METALS), 11)
        self.assertEqual(len(forge.REGION_METAL), 16)
        self.assertEqual(len(shared), 5)
        self.assertIn("python_village", forge.NO_METAL_REGIONS)
        said = self.text("the_forge")
        self.assertIn("eleven metals over sixteen regions", said)
        self.assertIn("five of them shared by two", said)
        self.assertIn("not one of them from this village", said)

    def test_rung_seven_is_where_the_ladder_takes_the_companion(self):
        from gauntlet import finalexam
        pet = finalexam.CRUTCH_BY_ID["PET"]
        self.assertEqual(finalexam._rung_of(pet), 7,
                         "PET's LADDER rung, which is not its index in "
                         "CRUTCHES — the index is five and this line said "
                         "five for exactly that reason")
        self.assertIn("Rung seven", self.text("the_companion"))

    def test_the_fourteen_is_one_set_of_fourteen(self):
        from gauntlet import finalexam, progression, world
        self.assertEqual(len(world.BOSSES), 14)
        self.assertEqual(len(world.KEYS), 14)
        self.assertEqual(len(finalexam.BOSS_LADDER), 14)
        self.assertEqual(progression.PORTAL_NEED.value, 14)
        takes = [s for s in finalexam.BOSS_LADDER if s.takes]
        self.assertEqual(len(takes), 12,
                         "the beat says twelve of the fourteen take something")
        said = self.text("the_keys")
        self.assertIn("Fourteen of them are out there", said)
        self.assertIn("Twelve take something off you", said)
        self.assertTrue(all(key.get("opens") for key in world.KEYS),
                        "the beat says every key opens a road")

    def test_the_shelf_clock_is_economy_restock_every(self):
        from gauntlet import economy
        self.assertEqual(economy.RESTOCK_EVERY, 6)
        self.assertIn("every sixth encounter", self.text("town_shelf"))

    def test_five_panels_is_what_index_html_draws(self):
        html = (self.WEB / "index.html").read_text(encoding="utf-8")
        tabs = re.findall(r'data-tab="([a-z]+)"', html)
        self.assertEqual(tabs,
                         ["trials", "tactics", "spells", "approach", "vision"])
        said = self.text("the_tabs")
        self.assertIn("Five panels on the right", said)
        for tab in tabs:
            self.assertIn(tab.upper(), said)

    def test_only_three_tabs_are_ever_sealed_and_in_ladder_order(self):
        """main.js's TAB_SEAL is the authority for WHICH, finalexam for the
        ORDER. The board line names the three that go and the two that stay."""
        from gauntlet import finalexam
        js = (self.WEB / "js" / "main.js").read_text(encoding="utf-8")
        raw = re.search(r"const TAB_SEAL = \{([^}]*)\}", js).group(1)
        seal = dict(re.findall(r"(\w+):\s*'(\w+)'", raw))
        self.assertEqual(seal, {"spells": "HINTS", "tactics": "PROBES",
                                "vision": "VISUALS"})
        order = sorted(seal, key=lambda tab:
                       finalexam._rung_of(finalexam.CRUTCH_BY_ID[seal[tab]]))
        self.assertEqual(order, ["spells", "tactics", "vision"])
        board = tutorial.BY_ID["the_tabs"].board
        positions = [board.index(tab.upper()) for tab in order]
        self.assertEqual(positions, sorted(positions),
                         f"the board line names them out of ladder order: "
                         f"{board!r}")
        for kept in ("TRIALS", "APPROACH"):
            self.assertIn(kept, board)
            self.assertNotIn(kept.lower(), seal)
        self.assertIn("yours to the end", board)

    def test_approach_is_a_box_you_write_in_and_not_a_restatement(self):
        js = (self.WEB / "js" / "main.js").read_text(encoding="utf-8")
        approach = js.split("function paintApproach(")[1][:1200]
        self.assertIn("textarea", approach)
        self.assertIn("communication self-check", approach)
        self.assertNotIn("Interviewers score this", approach,
                         "keyword coverage must not claim verified interviewer judgment")
        self.assertIn("G.explainBox = ta", approach)
        said = self.text("the_tabs")
        self.assertIn("APPROACH is a box you write in", said)
        self.assertNotIn("plain statement of what you were asked", said)

    def test_six_counters_here_and_five_everywhere_else(self):
        js = (self.WEB / "js" / "townui.js").read_text(encoding="utf-8")
        tabs = re.search(r"const TABS = \[(.*?)\n\];", js, re.S).group(1)
        ids = re.findall(r"\{ id: '([a-z]+)'", tabs)
        self.assertEqual(ids, ["mender", "smith", "shelf", "broker", "voices"])
        self.assertIn("PORTAL_TAB", js)
        said = self.text("the_square_panel")
        self.assertIn("Six counters in this one and five in every other", said)
        # and every one of the five has a beat of its own
        for tab in ids:
            self.assertIn("town_" + tab, tutorial.BY_ID,
                          f"the beat promises to introduce each counter and "
                          f"{tab} has no lesson")

    def test_no_key_opens_the_town_square(self):
        """There is exactly ONE way into the square in the whole client and it
        is a button. The beat used to open with a key that does not exist."""
        client = {path.name: path.read_text(encoding="utf-8")
                  for path in (self.WEB / "js").glob("*.js")}
        opens = {name: js.count("go('town')") for name, js in client.items()}
        self.assertEqual(sum(opens.values()), 1, opens)
        js = client["main.js"]
        where = js.index("go('town')")
        self.assertIn("btnTown.onclick", js[where - 60:where])
        # and the global key handler binds four keys, none of them that one
        handler = js.split("window.addEventListener('keydown'")[-1][:1400]
        self.assertEqual(set(re.findall(r"e\.key === '([^']+)'", handler)),
                         {"n", "f", "Escape", " "})
        said = self.text("the_square_panel")
        self.assertIn("THE TOWN SQUARE is a button", said)
        self.assertNotIn("One key", said)


# ---------------------------------------------------------------------------

class EveryScreenHasALessonOrAnOwner(unittest.TestCase):
    """The other half of "one feature, one lesson": count the curriculum
    against the SCREENS, not only against itself. A feature with no beat and
    no handoff is a feature the design never enumerated, which is how the MCQ
    pane, the puzzle trays, the incantations, the shrine, the disciplines and
    the fourteen keys all went missing at once."""

    WEB = Path(base.REPO) / "web"

    def covered(self, needle):
        blob = " ".join([tutorial._beat_text(r) for r in tutorial.BEATS]
                        + [r.trigger for r in tutorial.BEATS]
                        + [h.owner + " " + h.why for h in tutorial.HANDOFFS])
        return needle.lower() in blob.lower()

    def test_every_button_in_the_world_screens_actions_list_is_accounted_for(self):
        js = (self.WEB / "js" / "main.js").read_text(encoding="utf-8")
        block = js.split("side.appendChild(el('div', 'section-title', 'ACTIONS'))")[1][:1800]
        found = re.findall(r"""el\('button', '[^']*', (?:'([^']*)'|"([^"]*)")\)""",
                           block)
        labels = [a or b for a, b in found]
        self.assertGreaterEqual(len(labels), 7, labels)
        self.assertIn("ARMORER'S FORGE", labels,
                      "the double-quoted label is the one an apostrophe hides "
                      "from a lazier regex, and it is a whole mechanic")
        for label in labels:
            with self.subTest(button=label):
                self.assertTrue(self.covered(label),
                                f"{label!r} is on the first frame of play and "
                                f"no beat and no handoff mentions it")

    def test_the_three_encounter_surfaces_are_handed_off_by_name(self):
        owners = " ".join(h.owner for h in tutorial.HANDOFFS)
        self.assertIn("#answer-here", owners)
        self.assertIn("puzzle-help", owners)
        self.assertIn("explainBlank", owners)

    def test_field_handoffs_reach_the_actual_response_consumers(self):
        """Execute authored payloads through the shipped movement/travel UI."""
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required for the actual client consumer check")
        check = Path(base.REPO) / "scripts" / "verify" / "escort-handoffs.mjs"
        result = subprocess.run([node, str(check)], cwd=base.REPO,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("both travel paths", result.stdout)
        for order in (2, 26):
            row = next(h for h in tutorial.HANDOFFS if h.order == order)
            self.assertNotIn("NOT DELIVERED TODAY", row.why)
        self.assertIn("W3  DELIVERED", tutorial.WIRING)
        self.assertIn("distinct service signs", tutorial.WIRING)

    def test_the_seal_the_client_is_told_to_watch_is_not_the_one_that_lies(self):
        """`body.interview-mode` and `G.interview` are both cleared by
        `returnToWorld()` while the measured run is still open server-side —
        RETREAT reaches it mid-run — and that gap is exactly where five of the
        beats fire. The policy names its own class, carried from
        `Game._run_is_open()`."""
        seal = tutorial.CUE_POLICY["sealed_body_class"]
        self.assertNotEqual(seal, "interview-mode")
        self.assertEqual(seal, "run-open")
        self.assertEqual(tutorial.CUE_POLICY["sealed_field"], "run_open")
        # the client half: game.css hides the cue under BOTH classes
        css = (Path(base.REPO) / "web" / "css" / "game.css").read_text(
            encoding="utf-8")
        self.assertIn("body.%s .cue { display: none; }" % seal, css)
        self.assertIn("body.interview-mode .cue { display: none; }", css)
        # and the engine is told to ship the boolean
        self.assertIn(tutorial.RUN_OPEN_FIELD, tutorial.WIRING)
        # main.js really does clear both signals mid-run; this is the premise
        js = (Path(base.REPO) / "web" / "js" / "main.js").read_text(
            encoding="utf-8")
        body = js.split("function returnToWorld()")[1][:2500]
        self.assertIn("classList.remove('interview-mode')", body)
        self.assertIn("G.interview = null", body)

    def test_the_cue_registry_records_that_a_disabled_host_is_refused(self):
        source = MODULE.read_text(encoding="utf-8")
        registry = source.split("CUE_CONTROLS = (")[0][-1600:]
        self.assertIn("disabled", registry.lower())
        self.assertIn("opacity", registry.lower())


if __name__ == "__main__":
    unittest.main()
