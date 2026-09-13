"""Where the game saves itself, where the player may save, and what protects both.

The brief, in four clauses:

    "each new area auto saves or after a boss fight. the player can save
     whenever but not during a battle."

Each clause is a test below, and one thing that is not in the brief is tested
harder than any of them: THE RINGS. An autosave that can overwrite the last good
save turns a crash into a lost afternoon, and a waking point that can be evicted
by ordinary play turns dying into a lottery rather than a threat. Both rings
exist to make a bad write survivable, and a ring is only a safety net if the
thing it protects against is actually simulated — so the tests here corrupt
slots on disk and grind the ring over, rather than asserting that a constant
equals four.

THE RULE FOR SAVING, in one sentence the player can hold in their head:

    YOU CANNOT SAVE WHILE SOMETHING IS TAKING A TURN AGAINST YOU.

That is a rule about a live turn order, not about a location, which is why a
dungeon corridor is fine and a dungeon room is not.
"""
from __future__ import annotations

import copy
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gauntlet import config, death, saves, upkeep  # noqa: E402

HEALTH = upkeep.HEALTH_FIELD


class SaveTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gauntlet-saves-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.conn = saves.connect(self.dir / "save.sqlite3")
        self.addCleanup(self.conn.close)

    def fresh(self, **player) -> dict:
        state = saves.normalize({})
        state["player"].update(player)
        return state

    def corrupt(self, slot_id: str) -> None:
        self.conn.execute("UPDATE save_slots SET body = ? WHERE slot_id = ?",
                          (sqlite3.Binary(b"not-a-zlib-stream"), slot_id))
        self.conn.commit()


# ===========================================================================
# THE BRIEF'S TWO AUTOSAVES
# ===========================================================================

class AutosavePoints(SaveTest):

    def test_a_new_area_writes_a_waking_point(self):
        state = self.fresh(region="python_village")
        written = saves.autosave(self.conn, state, "region_entered",
                                 note="Entered Python Village")

        self.assertIsNotNone(written)
        self.assertIsNotNone(written["anchor"], "a new area wrote no anchor")
        self.assertEqual(written["anchor"]["reason"], "region_entered")
        self.assertEqual(saves.wake_slot(self.conn)["slot_id"],
                         written["anchor"]["slot_id"])

    def test_a_defeated_boss_writes_a_waking_point(self):
        state = self.fresh(region="fields_of_syntax", gold=400)
        written = saves.autosave(self.conn, state, "boss_defeated",
                                 note="The Gatekeeper is down")

        self.assertIsNotNone(written["anchor"])
        self.assertEqual(saves.wake_slot(self.conn)["reason"], "boss_defeated")

    def test_every_anchor_event_the_brief_asks_for_is_one(self):
        for reason in ("region_entered", "boss_defeated"):
            self.assertIn(reason, saves.ANCHOR_EVENTS)
        # and a cleared encounter deliberately is not: a threat that costs one
        # fight is not the threat the brief asked for.
        self.assertIn("encounter_cleared", saves.NOT_AN_ANCHOR)
        self.assertNotIn("encounter_cleared", saves.ANCHOR_EVENTS)
        self.assertEqual(saves.ANCHOR_EVENTS & saves.NOT_AN_ANCHOR, frozenset())

    def test_a_cleared_encounter_autosaves_but_does_not_move_the_waking_point(self):
        state = self.fresh(region="fields_of_syntax")
        entered = saves.autosave(self.conn, state, "region_entered")
        before = saves.wake_slot(self.conn)["slot_id"]

        state["player"]["gold"] = 40
        cleared = saves.autosave(self.conn, state, "encounter_cleared")

        self.assertIsNotNone(cleared, "the crash net stopped working")
        self.assertIsNone(cleared["anchor"])
        self.assertEqual(saves.wake_slot(self.conn)["slot_id"], before)
        self.assertNotEqual(cleared["slot_id"], entered["slot_id"])

    def test_an_unknown_reason_never_moves_where_death_puts_you(self):
        """A later pass inventing a new autosave trigger must not be able to
        move a waking point by accident, or crash the save path by trying."""
        state = self.fresh(region="python_village")
        saves.autosave(self.conn, state, "region_entered")
        before = saves.wake_slot(self.conn)["slot_id"]

        state["player"]["gold"] = 7
        written = saves.autosave(self.conn, state, "a_thing_invented_next_month")

        self.assertIsNotNone(written)
        self.assertIsNone(written["anchor"])
        self.assertEqual(saves.wake_slot(self.conn)["slot_id"], before)

    def test_an_idle_loop_cannot_rotate_the_good_saves_out(self):
        state = self.fresh(region="fields_of_syntax")
        first = saves.autosave(self.conn, state, "encounter_cleared")
        for _ in range(20):
            self.assertIsNone(saves.autosave(self.conn, state,
                                             "encounter_cleared"))
        rows = [r for r in saves.list_slots(self.conn, kinds=(saves.KIND_AUTO,))
                if not r["empty"]]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slot_id"], first["slot_id"])


# ===========================================================================
# THE RINGS — a bad write must never destroy the good one before it
# ===========================================================================

class TheRingsProtect(SaveTest):

    def test_the_autosave_ring_keeps_the_previous_good_save(self):
        """The whole reason AUTOSAVE_RING is greater than one."""
        state = self.fresh(region="fields_of_syntax")
        good = []
        for n in range(3):
            state["player"]["gold"] = 100 + n
            good.append(saves.autosave(self.conn, state,
                                       "encounter_cleared")["slot_id"])

        self.corrupt(good[-1])
        self.assertEqual(saves.verify_slot(self.conn, good[-1])["status"],
                         "corrupt")

        previous = good[-2]
        self.assertEqual(saves.verify_slot(self.conn, previous)["status"], "ok")
        self.assertEqual(
            saves.read_slot(self.conn, previous)["state"]["player"]["gold"], 101)

        # and the next write does not land on the survivor
        state["player"]["gold"] = 999
        landed = saves.autosave(self.conn, state, "encounter_cleared")
        self.assertNotEqual(landed["slot_id"], previous)
        self.assertEqual(saves.verify_slot(self.conn, previous)["status"], "ok")

    def test_the_ring_is_deep_enough_to_be_a_ring(self):
        self.assertGreaterEqual(saves.AUTOSAVE_RING, 3,
                                "the brief asks for an autosave ring of at least 3")
        self.assertGreaterEqual(saves.ANCHOR_RING, 2,
                                "one bad anchor could destroy the good one")

    def test_grinding_encounters_cannot_evict_the_waking_point(self):
        """THE ARITHMETIC the anchor ring exists to defeat.

        The autosave ring is four deep and every cleared encounter writes one,
        so four fights evict a region entry from it. If the waking point lived
        in that ring, a player who fought to the bottom of a dungeon would die
        and be handed a checkpoint four fights old.
        """
        state = self.fresh(region="fields_of_syntax")
        saves.autosave(self.conn, state, "region_entered",
                       note="Entered the fields")
        anchored = saves.wake_slot(self.conn)["slot_id"]

        for n in range(saves.AUTOSAVE_RING * 3 + 1):
            state["player"]["gold"] = 100 + n
            saves.autosave(self.conn, state, "encounter_cleared")

        autos = [r for r in saves.list_slots(self.conn, kinds=(saves.KIND_AUTO,))
                 if not r["empty"]]
        self.assertFalse(any(r["reason"] == "region_entered" for r in autos),
                         "the grind was too short to prove anything")
        self.assertEqual(saves.wake_slot(self.conn)["slot_id"], anchored,
                         "the grind moved where the player wakes")

    def test_a_corrupt_anchor_never_becomes_the_waking_point(self):
        state = self.fresh(region="python_village", gold=5)
        older = saves.anchor(self.conn, state, "region_entered", note="Village")
        newer_state = copy.deepcopy(state)
        newer_state["player"].update({"region": "fields_of_syntax", "gold": 60})
        newer = saves.anchor(self.conn, newer_state, "region_entered",
                             note="Fields")
        self.assertEqual(saves.wake_slot(self.conn)["slot_id"],
                         newer["slot_id"])

        self.corrupt(newer["slot_id"])

        self.assertEqual(saves.wake_slot(self.conn)["slot_id"], older["slot_id"])
        self.assertEqual(len(saves.anchors(self.conn)), 1)

    def test_the_anchor_ring_does_not_leak_into_the_save_screen(self):
        """The player picks between eight named slots and sees four autosaves.
        Waking points are the game's bookkeeping and are not on that screen."""
        state = self.fresh(region="python_village")
        for n in range(6):
            state["player"]["gold"] = n
            saves.autosave(self.conn, state, "region_entered")

        rows = saves.list_slots(self.conn)
        self.assertEqual(len(rows),
                         saves.MANUAL_SLOTS + saves.AUTOSAVE_RING + saves.UNDO_RING)
        self.assertNotIn(saves.KIND_ANCHOR, {r["kind"] for r in rows})


# ===========================================================================
# SAVE WHENEVER, BUT NOT DURING A BATTLE
# ===========================================================================

class TheBattleLock(SaveTest):

    CASES = (
        ("standing in a field",      {},                                        True),
        ("a town",                   {},                                        True),
        ("a dungeon corridor",       {"dungeon_run": {"dungeon": "d", "at": 3}}, True),
        ("a chase with no fight",    {"hunters": {"fight": None}},               True),
        ("a measured run",           {"interview": {"id": "iv"},
                                      "encounter": {"problem_id": "p"}},         True),
        ("the final practical",      {"exam": {"id": "ex"},
                                      "encounter": {"problem_id": "p"}},         True),
        ("an open encounter",        {"encounter": {"problem_id": "p"}},        False),
        ("a dungeon room",           {"encounter": {"problem_id": "p",
                                                    "dungeon_room": 4}},        False),
        ("a sage gauntlet rung",     {"encounter": {"problem_id": "p",
                                                    "reason": "SAGE"}},         False),
        ("a boss",                   {"boss_fight": {"boss_id": "b"}},          False),
        ("an incantation",           {"incantation": {"region": "r"}},          False),
        ("an apex hunt",             {"hunters": {"fight": {"region": "r"}}},   False),
    )

    def state_for(self, overlay: dict) -> dict:
        state = self.fresh(region="fields_of_syntax")
        state.update(copy.deepcopy(overlay))
        return state

    def test_the_lock_agrees_with_its_own_table(self):
        for label, overlay, allowed in self.CASES:
            with self.subTest(case=label):
                self.assertEqual(death.save_allowed(self.state_for(overlay)),
                                 allowed)

    def test_a_manual_save_is_refused_at_the_door_not_in_the_server(self):
        """Enforced in saves.save_to_slot so a second caller — a CLI, a test, a
        later pass — cannot walk around it."""
        for label, overlay, allowed in self.CASES:
            with self.subTest(case=label):
                state = self.state_for(overlay)
                if allowed:
                    row = saves.save_to_slot(self.conn, 1, state, name=label)
                    self.assertEqual(row["kind"], saves.KIND_MANUAL)
                else:
                    with self.assertRaises(saves.SaveError) as caught:
                        saves.save_to_slot(self.conn, 1, state, name=label)
                    self.assertNotIn("!", str(caught.exception))

    def test_every_refusal_says_what_is_happening_and_what_to_do(self):
        """A refusal the player cannot act on is a bug wearing a message."""
        for label, overlay, allowed in self.CASES:
            if allowed:
                continue
            with self.subTest(case=label):
                lock = death.battle_lock(self.state_for(overlay))
                self.assertIsNotNone(lock)
                self.assertFalse(lock["allowed"])
                self.assertGreater(len(lock["message"]), 40)
                self.assertTrue(lock["what"])
                self.assertNotIn("!", lock["message"])
                # it names a way out, not just a refusal
                self.assertTrue(
                    any(word in lock["message"].lower() for word in
                        ("finish", "walk", "lose", "saves itself")),
                    "the refusal offers the player nothing to do: %s"
                    % lock["message"])

    def test_autosaves_are_not_subject_to_the_lock(self):
        """The game writing down where you are is the one thing that should keep
        happening while you are in trouble."""
        state = self.state_for({"boss_fight": {"boss_id": "b"},
                                "encounter": {"problem_id": "p"}})
        self.assertFalse(death.save_allowed(state))
        self.assertIsNotNone(saves.autosave(self.conn, state, "region_entered"))
        self.assertIsNotNone(saves.snapshot_for_undo(self.conn, state))

    def test_the_deliberate_exception_still_exists_for_tools(self):
        state = self.state_for({"encounter": {"problem_id": "p"}})
        row = saves.save_to_slot(self.conn, 2, state, name="bug report",
                                 allow_in_battle=True)
        self.assertEqual(row["kind"], saves.KIND_MANUAL)


# ===========================================================================
# KNOWING WHERE THE FLOOR IS
# ===========================================================================

class TheThreatIsStated(SaveTest):
    """A threat is only fair if the player knows where the floor is. If the game
    saves silently, dying is a surprise about how much you lost; if it says so,
    dying is a consequence of a decision made after being told."""

    def test_an_anchor_announces_itself(self):
        state = self.fresh(region="python_village", level=3, gold=40)
        written = saves.autosave(self.conn, state, "region_entered",
                                 note="Entered Python Village")

        note = death.announce(written)
        self.assertIsNotNone(note)
        self.assertTrue(note["saved"])
        self.assertEqual(note["reason"], "region_entered")
        self.assertTrue(note["line"])
        self.assertTrue(note["label"].startswith("Waking point:"))
        self.assertNotIn("!", note["line"])

    def test_a_non_anchor_announces_nothing(self):
        state = self.fresh(region="python_village")
        self.assertIsNone(death.announce(
            saves.autosave(self.conn, state, "encounter_cleared")))
        self.assertIsNone(death.announce(None))
        self.assertIsNone(death.announce({}))

    def test_every_anchor_event_has_a_line_to_show(self):
        for reason in saves.ANCHOR_EVENTS:
            self.assertIn(reason, death.ANCHOR_LINES, reason)
            self.assertTrue(death.ANCHOR_LINES[reason])

    def test_the_standing_answer_survives_a_missed_moment(self):
        """announce() is the moment a save lands; waking_point() is the standing
        answer, and a toast that has faded tells a player nothing when they look
        up mid-fight and want to know what a bad submission is worth."""
        state = self.fresh(region="python_village", level=4, gold=90)
        written = saves.anchor(self.conn, state, "region_entered",
                               note="Entered Python Village")
        saved_at = float(written["summary"]["saved_at"])

        point = death.waking_point(self.conn, now=saved_at + 742.0)

        self.assertTrue(point["known"])
        self.assertEqual(point["slot_id"], written["slot_id"])
        self.assertEqual(point["region"], "Python Village")
        self.assertEqual(point["age"], "12m 22s")
        self.assertIn("12m 22s", point["line"])
        self.assertEqual(point["reason_label"], "Entered a new region")

    def test_with_nothing_to_lose_it_says_so(self):
        point = death.waking_point(self.conn)
        self.assertFalse(point["known"])
        self.assertTrue(point["line"])
        self.assertNotIn("!", point["line"])

    def test_a_named_slot_counts_as_a_waking_point(self):
        """The player chose to write it, and the brief says they may save
        wherever they like."""
        state = self.fresh(region="python_village", gold=15)
        saves.anchor(self.conn, state, "region_entered")
        later = copy.deepcopy(state)
        later["player"].update({"region": "fields_of_syntax", "gold": 200})
        slot = saves.save_to_slot(self.conn, 3, later, name="before the marsh")

        self.assertEqual(saves.wake_slot(self.conn)["slot_id"], slot["slot_id"])
        point = death.waking_point(self.conn)
        self.assertEqual(point["reason_label"], "Saved by hand")

        dying = copy.deepcopy(later)
        dying["player"].update({HEALTH: 0, "gold": 900})
        woken = death.die(self.conn, dying, cause="enemy_turn")["state"]
        self.assertEqual(woken["player"]["gold"], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
