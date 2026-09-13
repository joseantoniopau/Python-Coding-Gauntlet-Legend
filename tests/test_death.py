"""Dying, and the one thing it is never allowed to take.

THE LINE UNDER TEST, and it is the whole feature:

    DEATH REWINDS THE GAME. IT NEVER REWINDS THE PLAYER.

The brief asked for "a real threat to lose progress". Gold, position, inventory,
loot and the minutes since the last save are that threat, and they are supposed
to hurt. The graded record — attempts, skills, mastery, the SRS schedule, the
sealed hold-out ledger, boss records, interview runs — is evidence of what this
person can do, and dying may not touch one byte of it.

The tests below are written to FAIL if that line moves, and they are written to
be able to. Three habits, on purpose:

  * The graded checks DEEP-DIFF the record rather than counting it. A count is
    satisfied by a rollback that happens to replace five rows with five other
    rows, and `_restore_history` is a function that does exactly that.
  * The cost checks assert the cost is NON-ZERO. "Nothing was lost" passes every
    test that only asks whether the record survived, and it is the failure mode
    where the feature quietly stops existing.
  * The spiral checks arrange the worst state a player can actually be in and
    then ask, as a question with an answer, whether they can still act.

Nothing here reads a constant and asserts it equals itself. Every number is
recomputed from upkeep.py and config.py at runtime, so a pass that retunes the
alarm moves these tests with it or breaks them.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gauntlet import config, db, death, saves, upkeep, world  # noqa: E402

HEALTH = upkeep.HEALTH_FIELD
FOCUS = upkeep.FOCUS_FIELD


# ---------------------------------------------------------------------------
# A deep diff, because a count is not a diff
# ---------------------------------------------------------------------------

def diff(a, b, path="") -> list:
    """Every leaf that differs, named by its path. Empty means identical."""
    if isinstance(a, bool) != isinstance(b, bool):
        return ["%s: %r -> %r" % (path, a, b)]
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            where = "%s.%s" % (path, key)
            if key not in a:
                out.append("%s: ADDED %r" % (where, b[key]))
            elif key not in b:
                out.append("%s: REMOVED %r" % (where, a[key]))
            else:
                out += diff(a[key], b[key], where)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return ["%s: length %d -> %d" % (path, len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, "%s[%d]" % (path, i))
        return out
    return [] if a == b else ["%s: %r -> %r" % (path, a, b)]


class DeathTest(unittest.TestCase):
    """A throwaway save file per test. No corpus: nothing here serves a problem,
    and building 1,013 of them to prove that dying does not delete a row would
    make the suite slower for no evidence."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gauntlet-death-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.conn = saves.connect(self.dir / "save.sqlite3")
        self.addCleanup(self.conn.close)

    # -- the fixtures ------------------------------------------------------

    def fresh(self, **player) -> dict:
        state = saves.normalize({})
        state["player"].update(player)
        return state

    def graded(self, state: dict) -> dict:
        """EVERY graded thing, in full. The four tables as rows, not counts, and
        every state key death.py itself promises survives."""
        record = {
            "attempts": db.recent_attempts(self.conn, limit=10 ** 6),
            "boss_records": db.boss_history(self.conn),
            "interview_runs": db.interview_history(self.conn, limit=10 ** 6),
            "transfer_encounters": db.transfer_ledger(self.conn),
        }
        for key in death.SURVIVES:
            record["state.%s" % key] = copy.deepcopy(state.get(key))
        for key in death.PLAYER_SURVIVES:
            record["player.%s" % key] = copy.deepcopy(
                (state.get("player") or {}).get(key))
        for key in death.STATS_SURVIVE:
            record["stats.%s" % key] = copy.deepcopy(
                (state.get("stats") or {}).get(key))
        return record

    def with_history(self) -> None:
        """A real graded history on disk: forty attempts, four bosses, three
        measured runs and six rows of the sealed hold-out ledger."""
        for n in range(40):
            db.record_attempt(self.conn, problem_id="p%d" % n,
                              pattern="HASH_MAP", family="hash_map",
                              difficulty="MEDIUM", mode="ADVENTURE",
                              encounter_kind="BATTLE", solved=int(n % 3 != 0),
                              rank="B", hints_used=n % 2, seconds=20.0 + n)
        for n in range(4):
            db.record_boss(self.conn, "boss_%d" % n, attempt_no=1,
                           seconds=300.0 + n, hints_used=0, rank="A", defeated=1)
        for n in range(3):
            db.record_interview(self.conn, format="SCREEN", profile="BACKEND",
                                score=60.0 + n, problem_ids="p1,p2", solved=2,
                                total=2, seconds=1200.0, detail="{}")
        for n in range(6):
            db.open_transfer(self.conn, problem_id="h%d" % n,
                             lineage_id="lin%d" % n, pattern="HASH_MAP",
                             skill="HASH_MAP", difficulty="MEDIUM",
                             mode="ADVENTURE", first_encounter=True)
            db.resolve_transfer(self.conn, "h%d" % n, solved=(n % 2 == 0),
                                unaided=True, seconds=90.0, rank="A")

    def an_afternoon(self, anchored: dict) -> dict:
        """The state the player dies in: an hour past the anchor, rich, levelled,
        loaded with loot, and carrying evidence earned since the save."""
        dying = copy.deepcopy(anchored)
        dying["player"].update({
            "gold": 1180, "xp": 3100, "level": 7, "region": "fields_of_syntax",
            "x": 55, "y": 30, "playtime_seconds": 4900.0,
            HEALTH: 0, FOCUS: 1,
        })
        dying["inventory"] = ["rusted_dagger", "marsh_ward", "iron_greaves",
                              "coil_of_rope", "vault_key", "sealed_letter"]
        dying["potions"] = {"lesser_draught": 3, "greater_draught": 1}
        dying["cleared_bosses"] = ["boss_0", "boss_1"]
        dying["solved_ids"] = ["p%d" % n for n in range(28)]
        dying["perf_failed_ids"] = ["p31", "p32"]
        for i, key in enumerate(list(dying["skills"])[:9]):
            dying["skills"][key]["mastery"] = round(0.11 * (i + 1), 4)
            dying["skills"][key]["clears"] = i + 1
            dying["skills"][key]["attempts"] = 2 * (i + 1)
        dying["schedule"] = {
            "HASH_MAP:p%d" % n: {"key": "HASH_MAP:p%d" % n, "due": 100.0 + n,
                                 "interval": 3.0, "ease": 2.5, "reps": 2,
                                 "lapses": 1} for n in range(12)}
        dying["recent_ids"] = ["p25", "p26", "p27"]
        dying["session"] = {"ids": ["p25", "p26"], "started": 111.0}
        dying["achievements"] = ["first_blood", "hash_slinger", "marathon"]
        dying["diagnostic"] = {"placed": "MEDIUM", "score": 61.0, "at": 5.0}
        dying["settings"] = {"high_contrast": True, "vol_master": 0.2,
                             "reduced_motion": True, "text_scale": 1.4,
                             "colourblind": "deuteranopia"}
        dying["stats"].update({"probes": 30, "probes_correct": 22,
                               "interviews_passed": 2, "chapters_graduated": 3,
                               "hints_total": 17, "sessions": 9,
                               "encounters": 61, "gold_earned": 2000})
        dying["player"]["diagnostic_done"] = True
        dying["encounter"] = {"problem_id": "p28"}
        dying["upkeep"]["statuses"] = [{"id": "POISON", "turns": 4}]
        upkeep.pet_knock(dying, "companion_fox", hits=upkeep.PET_KNOCKS_TO_FAINT)
        return dying

    def a_real_death(self, *, over_a_manual_slot: bool):
        """Anchor, earn evidence, have a bad afternoon, die. Returns everything
        a test needs to interrogate what moved."""
        anchored = self.fresh(gold=12, xp=140, level=2, region="python_village",
                              x=20, y=12, playtime_seconds=800.0, name="Ada")
        anchored["inventory"] = ["rusted_dagger"]
        saves.apply_state(self.conn, anchored)
        if over_a_manual_slot:
            written = saves.save_to_slot(self.conn, 1, anchored,
                                         name="before the marsh")
        else:
            written = saves.anchor(self.conn, anchored, "region_entered",
                                   note="Entered Python Village")
        self.assertIsNotNone(written)

        # Every row of this is earned AFTER the save, which is what makes the
        # manual-slot case dangerous: the slot carries a history snapshot from
        # before any of it existed.
        self.with_history()
        dying = self.an_afternoon(anchored)
        saves.apply_state(self.conn, dying)
        return anchored, dying, written


# ===========================================================================
# 1. DEATH NEVER TOUCHES THE GRADED RECORD
# ===========================================================================

class TheRecordDoesNotMove(DeathTest):
    """The check that matters most. Everything else in this file is a detail
    beside it."""

    def test_one_death_over_an_anchor_moves_nothing_graded(self):
        _, dying, _ = self.a_real_death(over_a_manual_slot=False)
        before = self.graded(dying)
        self.assertGreater(len(before["attempts"]), 0, "no evidence to protect")

        result = death.die(self.conn, dying, cause="enemy_turn")

        after = self.graded(result["state"])
        self.assertEqual(diff(before, after, "record"), [],
                         "dying moved the graded record")

    def test_one_death_over_a_manual_slot_moves_nothing_graded(self):
        """The path a naive implementation gets wrong.

        A manual slot carries a HISTORY snapshot, and saves._restore_history
        DELETEs attempts, boss_records and interview_runs before rewriting them
        from it. A death that loaded the slot the ordinary way would roll the
        record back to the moment of the save and look like it worked — the
        tables would still be full, just full of older rows, which is why this
        test diffs the rows instead of counting them.
        """
        _, dying, slot = self.a_real_death(over_a_manual_slot=True)
        snapshot = saves.read_slot(self.conn, slot["slot_id"]).get("history") or {}
        self.assertEqual(len(snapshot.get("attempts") or []), 0,
                         "the slot's history snapshot should predate the evidence")
        self.assertEqual(saves.wake_slot(self.conn)["slot_id"], slot["slot_id"])

        before = self.graded(dying)
        result = death.die(self.conn, dying, cause="enemy_turn")
        after = self.graded(result["state"])

        self.assertEqual(diff(before, after, "record"), [],
                         "dying over a manual slot rolled the record back")
        self.assertEqual(len(after["attempts"]), 40)

    def test_ten_deaths_move_nothing_graded(self):
        """Once could be luck. Ten is the ledger."""
        _, dying, _ = self.a_real_death(over_a_manual_slot=False)
        before = self.graded(dying)

        state = dying
        for n in range(10):
            state["player"][HEALTH] = 0
            state["player"]["gold"] = 400 + 90 * n
            state["inventory"] = list(state["inventory"]) + ["loot_%d" % n]
            state = death.die(self.conn, state, cause="enemy_turn")["state"]

        after = self.graded(state)
        self.assertEqual(diff(before, after, "record"), [],
                         "ten deaths moved the graded record")

    def test_the_four_graded_tables_are_never_written(self):
        """Not "unchanged" — UNTOUCHED. A sqlite trace catches a DELETE followed
        by an identical rewrite, which a diff of the rows cannot."""
        _, dying, _ = self.a_real_death(over_a_manual_slot=True)
        seen = []
        self.conn.set_trace_callback(seen.append)
        try:
            death.die(self.conn, dying, cause="enemy_turn")
        finally:
            self.conn.set_trace_callback(None)

        # Matched at STATEMENT position, not as a substring: sqlite's trace
        # hands back the expanded SQL with the bound parameters in it, and the
        # state blob contains the word "attempts" inside every skill row.
        for table in death.GRADED_TABLES:
            pattern = re.compile(
                r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|REPLACE\s+INTO"
                r"|DELETE\s+FROM|UPDATE)\s+[\"'`\[]?%s\b" % re.escape(table),
                re.IGNORECASE)
            offenders = [sql for sql in seen if pattern.search(sql)]
            self.assertEqual(offenders, [],
                             "dying wrote to %s: %s" % (table, offenders[:1]))

    def test_the_record_survives_the_round_trip_to_disk(self):
        """Dying writes the rolled-back state through saves.apply_state. If the
        surviving half were only folded in memory, the next load would hand the
        player back the anchor's evidence instead of their own — and the tests
        above, which all read the returned dict, would not notice."""
        _, dying, _ = self.a_real_death(over_a_manual_slot=False)
        before = self.graded(dying)

        result = death.die(self.conn, dying, cause="enemy_turn")
        on_disk = db.load_state(self.conn) or {}

        self.assertEqual(diff(self.graded(result["state"]),
                              self.graded(on_disk), "disk"), [],
                         "what was written differs from what was returned")
        self.assertEqual(diff(before, self.graded(on_disk), "disk"), [])
        # and the game half really did rewind on disk too
        self.assertEqual(on_disk["player"]["gold"], 12)
        self.assertEqual(on_disk["player"]["region"], "python_village")

    def test_mastery_is_never_removed_by_dying(self):
        """The brief's own sentence, as an assertion."""
        _, dying, _ = self.a_real_death(over_a_manual_slot=False)
        at_death = {k: v["mastery"] for k, v in dying["skills"].items()}
        self.assertTrue(any(at_death.values()), "no mastery to lose")

        woken = death.die(self.conn, dying, cause="enemy_turn")["state"]

        self.assertEqual({k: v["mastery"] for k, v in woken["skills"].items()},
                         at_death)

    def test_the_ledger_classifies_every_key_in_a_real_state(self):
        """The failure this guards is somebody adding a state key in six months
        and not deciding which side of the line it is on. An unclassified key
        defaults to being rewound, so it silently becomes a thing a player can
        be robbed of by dying."""
        from gauntlet import engine
        self.assertEqual(death.unclassified_keys(engine.DEFAULT_STATE), [])
        self.assertEqual(sorted(set(death.SURVIVES) & set(death.ROLLED_BACK)), [])
        stray = sorted((set(death.SURVIVES) | set(death.ROLLED_BACK)
                        | set(death.MIXED)) - set(engine.DEFAULT_STATE))
        self.assertEqual(stray, [], "the ledger names keys the state lacks")
        for table in death.GRADED_TABLES:
            self.assertIn(table, saves.capture_history(self.conn))

    def test_accessibility_settings_are_not_game_state(self):
        """Resetting somebody's contrast because they lost a fight is the kind
        of key that gets swept into a rollback by accident."""
        _, dying, _ = self.a_real_death(over_a_manual_slot=False)
        woken = death.die(self.conn, dying, cause="enemy_turn")["state"]
        self.assertEqual(woken["settings"], dying["settings"])
        self.assertTrue(woken["settings"]["high_contrast"])
        self.assertEqual(woken["settings"]["colourblind"], "deuteranopia")

    def test_survivor_counters_are_monotone_never_lowered(self):
        """stats is half evidence and half game. The evidence half is raised by
        the dying state and never lowered by the restored one, for the same
        reason db.merge_transfer is monotone."""
        anchored = self.fresh(gold=5, region="python_village")
        anchored["stats"]["hints_total"] = 40      # the anchor holds MORE
        anchored["stats"]["sessions"] = 12
        saves.anchor(self.conn, anchored, "region_entered")
        saves.apply_state(self.conn, anchored)

        dying = copy.deepcopy(anchored)
        dying["player"][HEALTH] = 0
        dying["stats"]["hints_total"] = 9          # ...than the death does
        dying["stats"]["sessions"] = 13
        woken = death.die(self.conn, dying, cause="enemy_turn")["state"]

        self.assertEqual(woken["stats"]["hints_total"], 40)
        self.assertEqual(woken["stats"]["sessions"], 13)


# ===========================================================================
# 2. DEATH DOES COST SOMETHING
# ===========================================================================

class DeathCosts(DeathTest):
    """If dying costs nothing the feature does not exist, and every test in the
    section above would still pass."""

    def test_a_realistic_death_costs_gold_loot_levels_and_the_afternoon(self):
        anchored, dying, written = self.a_real_death(over_a_manual_slot=False)
        saved_at = float((written.get("summary") or {}).get("saved_at", 0.0))

        result = death.die(self.conn, dying, cause="enemy_turn",
                           now=saved_at + 3600.0)
        lost, woken = result["lost"], result["state"]

        self.assertEqual(lost["gold"], 1180 - 12)
        self.assertEqual(lost["xp"], 3100 - 140)
        self.assertEqual(lost["levels"], 7 - 2)
        self.assertEqual(lost["items"], 6 - 1)
        self.assertEqual(lost["potions"], 4)
        self.assertEqual(lost["bosses"], 2)
        self.assertEqual(lost["elapsed_text"], "1h 00m")
        # and the player is physically back where they saved
        self.assertEqual(woken["player"]["region"], "python_village")
        self.assertEqual((woken["player"]["x"], woken["player"]["y"]), (20, 12))
        self.assertEqual(woken["inventory"], ["rusted_dagger"])
        self.assertEqual(woken["potions"], {})
        self.assertEqual(woken["cleared_bosses"], [])
        self.assertEqual(woken["stats"]["encounters"], 0)

    def test_the_cost_is_never_silently_zero(self):
        """The failure mode this feature dies of: a rollback that rolls nothing
        back. Stated as its own test so it cannot be mistaken for a detail."""
        for manual in (False, True):
            with self.subTest(over_a_manual_slot=manual):
                self.setUp()
                _, dying, _ = self.a_real_death(over_a_manual_slot=manual)
                lost = death.die(self.conn, dying, cause="enemy_turn")["lost"]
                self.assertGreater(lost["gold"], 0)
                self.assertGreater(lost["items"], 0)
                self.assertGreater(lost["xp"], 0)
                self.assertGreater(lost["levels"], 0)

    def test_the_death_screen_states_the_cost_in_numbers(self):
        """A death screen that hides the cost is worse than one that states it:
        the player cannot decide to be more careful if the game will not tell
        them what carelessness is worth."""
        _, dying, written = self.a_real_death(over_a_manual_slot=False)
        saved_at = float((written.get("summary") or {}).get("saved_at", 0.0))
        report = death.die(self.conn, dying, cause="enemy_turn",
                           now=saved_at + 742.0)["report"]

        self.assertEqual(sorted(report), ["cost", "kept", "wake"])
        self.assertEqual(report["cost"]["gold"], 1168)
        self.assertEqual(report["cost"]["items"], 5)
        self.assertEqual(report["cost"]["levels"], 5)
        self.assertEqual(report["cost"]["playtime"], "12m 22s")
        self.assertEqual(report["wake"]["region"], "Python Village")
        # the kept half is never empty, and is said on every death
        self.assertEqual(report["kept"]["attempts"], 40)
        self.assertGreater(report["kept"]["skills"], 0)
        self.assertTrue(report["kept"]["mastery"].endswith("%"))
        self.assertEqual(report["kept"]["due"], 12)
        self.assertNotIn("!", json.dumps(report))

    def test_a_death_seconds_after_a_save_costs_almost_nothing(self):
        """The threat is a function of how long ago you saved, which is what
        makes it a decision rather than a tax."""
        anchored = self.fresh(gold=300, xp=900, level=4, region="fields_of_syntax")
        anchored["inventory"] = ["a", "b"]
        saves.anchor(self.conn, anchored, "region_entered")
        saves.apply_state(self.conn, anchored)
        dying = copy.deepcopy(anchored)
        dying["player"][HEALTH] = 0

        lost = death.die(self.conn, dying, cause="enemy_turn")["lost"]

        self.assertEqual(lost["gold"], 0)
        self.assertEqual(lost["items"], 0)
        self.assertEqual(lost["levels"], 0)

    def test_dying_cannot_be_undone(self):
        """The undo ring makes a mistaken LOAD one keypress away from harmless.
        A death is not a mistaken load, and offering it back would make dying
        free — which is the one thing this feature is not."""
        _, dying, _ = self.a_real_death(over_a_manual_slot=False)
        before = saves.undo_available(self.conn)
        result = death.die(self.conn, dying, cause="enemy_turn")

        self.assertFalse(result["undo_available"])
        row = saves.describe(self.conn, result["forensic_slot"])
        self.assertTrue(row["consumed"], "the dying state was left un-sealed")
        if not before:
            self.assertFalse(saves.undo_available(self.conn),
                             "undo_load would hand back the moment before death")


# ===========================================================================
# 3. NO SPIRAL — the rule at the top of the brief
# ===========================================================================

class NoSpiral(DeathTest):
    """LEARNING NEVER DEAD-ENDS. A player who dies repeatedly must always be
    able to keep playing. Death is a setback, never a spiral and never a wall."""

    def the_worst_state(self) -> dict:
        """0 gold, armour ground to the floor, companion fainted, poisoned,
        eleven rooms deep in a dungeon, and the anchor is no better."""
        state = self.fresh(gold=0, xp=900, level=4, region="sunken_vault",
                           x=8, y=40, **{HEALTH: 3})
        upkeep.ensure(state)
        for _ in range(400):
            upkeep.wear_encounter(state, difficulty="HARD", hits_taken=6)
        upkeep.pet_knock(state, "companion_fox", hits=upkeep.PET_KNOCKS_TO_FAINT)
        state["upkeep"]["statuses"] = [{"id": "POISON", "turns": 5},
                                       {"id": "BURN", "turns": 2}]
        state["dungeon_run"] = {"dungeon": "sunken_vault", "at": 7, "depth": 7}
        return state

    def assert_can_act(self, state: dict, where: str):
        """Can this player fight, ask a question, and reach help."""
        alarm = upkeep.alarm(state)
        floor = death.wake_health(config.STAMINA_MAX)
        health = state["player"][HEALTH]

        self.assertGreaterEqual(health, floor, "%s: woke below the floor" % where)
        self.assertGreaterEqual(
            health, 2 * config.STAMINA_LOSS_FAILED_SUBMIT,
            "%s: not enough health for two failed submissions" % where)
        self.assertNotIn(alarm["band"], ("DIRE", "CRITICAL"),
                         "%s: woke inside the alarm" % where)
        self.assertFalse(alarm["heartbeat"],
                         "%s: woke to the sound that killed them" % where)
        self.assertFalse(alarm["pulse"], "%s: woke inside the red pulse" % where)
        self.assertGreaterEqual(
            state["player"][FOCUS], upkeep.VOIDED_FOCUS_FLOOR,
            "%s: cannot afford to ask a question" % where)
        self.assertFalse(upkeep.fainted_pets(state),
                         "%s: the hint system is still unconscious" % where)
        self.assertEqual((state.get("upkeep") or {}).get("statuses"), [],
                         "%s: woke still poisoned" % where)
        self.assertGreaterEqual(upkeep.armour_scale(state), upkeep.DEGRADED_FLOOR,
                                "%s: armour below the floor" % where)
        for key in ("encounter", "boss_fight", "incantation", "interview", "exam"):
            self.assertFalse(state.get(key),
                             "%s: woke inside an open %s" % (where, key))
        self.assertFalse((state.get("hunters") or {}).get("fight"),
                         "%s: woke with an apex in front of them" % where)
        # and help is reachable with an empty purse
        healed = upkeep.heal(json.loads(json.dumps(state)), sealed=False)
        self.assertTrue(healed.get("ok"), "%s: the healer refused" % where)
        self.assertEqual(int(healed.get("gold_cost", 0) or 0), 0,
                         "%s: healing was not free" % where)

    def test_the_worst_death_in_the_game_still_leaves_a_playable_game(self):
        state = self.the_worst_state()
        saves.apply_state(self.conn, state)
        saves.anchor(self.conn, state, "region_entered",
                     note="Entered the Sunken Vault")

        dying = copy.deepcopy(state)
        dying["player"].update({HEALTH: 0, FOCUS: 0, "gold": 0, "x": 60, "y": 60})
        dying["dungeon_run"] = {"dungeon": "sunken_vault", "at": 11, "depth": 11}
        dying["encounter"] = {"problem_id": "deep", "dungeon_room": 11}
        dying["upkeep"]["statuses"] = [{"id": "POISON", "turns": 5}]
        upkeep.pet_knock(dying, "companion_fox", hits=upkeep.PET_KNOCKS_TO_FAINT)

        result = death.die(self.conn, dying, cause="enemy_turn")
        self.assert_can_act(result["state"], "first death")
        self.assertTrue(result["woke_at"]["region"], "nowhere to wake")

    def test_and_dying_again_immediately_still_holds(self):
        state = self.the_worst_state()
        saves.apply_state(self.conn, state)
        saves.anchor(self.conn, state, "region_entered")
        dying = copy.deepcopy(state)
        dying["player"][HEALTH] = 0

        state = death.die(self.conn, dying, cause="enemy_turn")["state"]
        self.assert_can_act(state, "first death")
        state["player"][HEALTH] = 0
        state = death.die(self.conn, state, cause="enemy_turn")["state"]
        self.assert_can_act(state, "second death")

    def test_ten_deaths_in_a_row_never_find_a_wall(self):
        state = self.the_worst_state()
        saves.apply_state(self.conn, state)
        saves.anchor(self.conn, state, "region_entered")
        for n in range(10):
            state["player"][HEALTH] = 0
            db.record_attempt(self.conn, problem_id="q%d" % n,
                              pattern="TWO_POINTER", family="two_pointer",
                              difficulty="EASY", mode="ADVENTURE",
                              encounter_kind="BATTLE", solved=0, rank="C",
                              hints_used=0, seconds=20.0)
            state = death.die(self.conn, state, cause="enemy_turn")["state"]
            self.assert_can_act(state, "death %d" % (n + 1))
            # and the evidence only ever grew
            self.assertEqual(len(db.recent_attempts(self.conn, limit=10 ** 6)),
                             n + 1)

    def test_waking_never_puts_you_below_where_you_saved(self):
        """The floor is a floor, not a heal. A player who anchored at full
        health wakes at full health."""
        for saved in (0, 1, 4, 7, 10, 15, config.STAMINA_MAX):
            with self.subTest(saved_at=saved):
                woken = death.wake(self.fresh(**{HEALTH: 0}),
                                   self.fresh(**{HEALTH: saved}))
                self.assertGreaterEqual(woken["health"], saved)
                self.assertGreaterEqual(woken["health"],
                                        death.wake_health(config.STAMINA_MAX))

    def test_the_wake_floor_is_read_from_upkeep_not_copied(self):
        """A pass that retunes the alarm moves this floor with it or fails."""
        maximum = config.STAMINA_MAX
        floor = death.wake_health(maximum)
        self.assertGreater(floor, int(maximum * upkeep.ALARM_ONSET),
                           "the wake floor is inside the alarm band")
        band = upkeep.alarm_for(floor, maximum)
        self.assertFalse(band["heartbeat"])
        self.assertFalse(band["pulse"])
        self.assertGreaterEqual(band["failures_left"], 3)

    def test_a_tick_may_never_kill_you(self):
        """Poison lands at the top of a turn, before the player has done
        anything. If it could finish the job the player would be told they were
        dying by a death screen."""
        for cause, row in sorted(death.CAUSES.items()):
            with self.subTest(cause=cause):
                state = self.fresh(**{HEALTH: 0})
                verdict = death.adjudicate(state, cause=cause)
                self.assertEqual(verdict["dead"], row["lethal"])
                if not row["lethal"]:
                    self.assertEqual(verdict["health"], death.DOT_FLOOR)
                    self.assertEqual(state["player"][HEALTH], death.DOT_FLOOR)

    def test_an_unclassified_damage_source_is_lethal_not_safe(self):
        self.assertTrue(death.adjudicate(self.fresh(**{HEALTH: 0}),
                                         cause="some_new_thing")["dead"])

    def test_a_measured_run_is_death_proof(self):
        """Killing a player mid-run would DESTROY EVIDENCE: the run is graded
        work in progress, and graded work is not the game's to take."""
        for key in ("interview", "exam"):
            with self.subTest(open=key):
                state = self.fresh(**{HEALTH: 0})
                state[key] = {"id": "run-1", "results": []}
                verdict = death.adjudicate(state, cause="enemy_turn")
                self.assertFalse(verdict["dead"])
                self.assertEqual(verdict["cause"], "measured_run")
                self.assertEqual(verdict["health"], death.DOT_FLOOR)

    def test_check_does_not_kill_a_player_who_is_standing(self):
        state = self.fresh(**{HEALTH: 6})
        out = death.check(self.conn, state, cause="enemy_turn")
        self.assertFalse(out["died"])
        self.assertIs(out["state"], state)


# ===========================================================================
# 5. THE SEQUENCE — three beats, each slower, then silence
# ===========================================================================

class TheHeart(DeathTest):
    """The alarm speeds the heart UP as health falls. Death is the inversion.
    Continuity is by construction, not by resemblance, so every number below is
    recomputed from upkeep.py rather than compared against a literal."""

    def test_three_beats_each_slower_than_the_last(self):
        beats = death.heartbeat_schedule()["beats"]
        self.assertEqual(len(beats), 3)
        gaps = [beats[i + 1]["at_ms"] - beats[i]["at_ms"]
                for i in range(len(beats) - 1)]
        self.assertEqual(gaps, sorted(gaps))
        self.assertTrue(all(b > a for a, b in zip(gaps, gaps[1:])))
        self.assertTrue(all(beats[i]["bpm"] > beats[i + 1]["bpm"]
                            for i in range(len(beats) - 1)))

    def test_it_starts_on_the_alarms_own_tempo(self):
        """The first death beat is the alarm's next beat, so the seam between
        the fight and the death is inaudible."""
        beats = death.heartbeat_schedule()["beats"]
        self.assertEqual(beats[0]["bpm"],
                         upkeep.alarm_for(0, config.STAMINA_MAX)["bpm"])
        self.assertEqual(beats[0]["bpm"], upkeep.BPM_MAX)
        self.assertEqual(beats[1]["bpm"], upkeep.BPM_ONSET)

    def test_the_first_gap_is_slower_than_anything_the_alarm_can_play(self):
        """Otherwise the slowdown is a matter of memory rather than a fact."""
        tempos = [upkeep.alarm_for(h, config.STAMINA_MAX)["bpm"]
                  for h in range(config.STAMINA_MAX + 1)]
        slowest = min(b for b in tempos if b)
        schedule = death.heartbeat_schedule()
        first_gap = schedule["beats"][1]["at_ms"] - schedule["beats"][0]["at_ms"]
        self.assertGreater(first_gap, round(60000.0 / slowest))

    def test_the_silence_lands_on_the_beat_that_does_not_come(self):
        schedule = death.heartbeat_schedule()
        self.assertEqual(schedule["silence_ms"],
                         schedule["beats"][-1]["interval_ms"])
        self.assertEqual(schedule["black_at_ms"], schedule["beats"][-1]["at_ms"])
        self.assertEqual(schedule["screen_at_ms"],
                         schedule["black_at_ms"] + schedule["silence_ms"])

    def test_picture_and_sound_are_one_clock(self):
        """upkeep asserts pulse_hz == bpm/60 for the alarm. The same must hold
        here or the black-out and the thump drift apart."""
        for beat in death.heartbeat_schedule()["beats"]:
            self.assertAlmostEqual(beat["hz"], beat["bpm"] / 60.0, places=2)
            self.assertEqual(beat["interval_ms"], round(60000.0 / beat["bpm"]))

    def test_each_beat_is_quieter_and_lower_and_the_last_is_unanswered(self):
        beats = death.heartbeat_schedule()["beats"]
        self.assertTrue(all(beats[i]["gain"] > beats[i + 1]["gain"]
                            for i in range(len(beats) - 1)))
        self.assertTrue(all(beats[i]["base_hz"] > beats[i + 1]["base_hz"]
                            for i in range(len(beats) - 1)))
        self.assertEqual([b["pair"] for b in beats], [True, True, False])

    def test_the_whole_thing_is_short_enough_to_sit_through_ten_times(self):
        self.assertLessEqual(death.heartbeat_schedule()["total_ms"], 4000)

    def test_reduced_motion_removes_the_fade_and_keeps_every_beat(self):
        """What is HEARD is the content. The iris and the fade are the motion."""
        full = death.heartbeat_schedule()
        reduced = death.heartbeat_schedule(reduced_motion=True)
        self.assertEqual(reduced["beats"], full["beats"])
        self.assertEqual(reduced["total_ms"], full["total_ms"])
        self.assertEqual(reduced["silence_ms"], full["silence_ms"])
        self.assertEqual(reduced["fade_to_ms"], 0)
        self.assertGreater(full["fade_to_ms"], 0)

    def test_the_last_red_is_the_alarms_red(self):
        self.assertEqual(death.heartbeat_schedule()["colour"],
                         upkeep.ALARM_BANDS[0].colour)

    def test_the_schedule_rides_on_every_death(self):
        anchored = self.fresh(gold=5, region="python_village")
        saves.anchor(self.conn, anchored, "region_entered")
        saves.apply_state(self.conn, anchored)
        dying = copy.deepcopy(anchored)
        dying["player"][HEALTH] = 0
        result = death.die(self.conn, dying, cause="enemy_turn")
        self.assertEqual(result["heartbeat"]["bpm"],
                         list(death.DEATH_BEAT_BPM))


# ===========================================================================
# 6. IT CANNOT TRAP
# ===========================================================================

class ItCannotTrap(DeathTest):
    """The death screen always releases the player. The JavaScript half of this
    is proved frame by frame in scripts/verify/death.mjs; this is the Python
    half — the report that drives it can never fail to produce a screen."""

    def test_every_report_shape_still_produces_a_screen(self):
        for label, payload in (
                ("nothing at all", {}),
                ("no wake group", {"lost": {"gold": 5}, "kept": {"attempts": 3}}),
                ("nulls throughout", {"lost": None, "kept": None,
                                      "woke_at": None}),
                ("a fallback death", {"woke_at": {"fallback": True,
                                                  "region": "Python Village"},
                                      "lost": {}, "kept": {"attempts": 3}}),
                ("junk types", {"lost": {"gold": "many"}, "kept": {},
                                "woke_at": {"region": None}}),
        ):
            with self.subTest(case=label):
                out = death.report(payload)
                self.assertEqual(sorted(out), ["cost", "kept", "wake"])
                self.assertTrue(all(isinstance(v, dict) for v in out.values()))
                for key in ("gold", "items", "levels"):
                    self.assertIsInstance(out["cost"][key], int)
                self.assertEqual(sorted(out["kept"]),
                                 ["attempts", "due", "mastery", "skills"])

    def test_a_player_with_no_save_at_all_still_gets_up(self):
        """Nothing dead-ends, the death screen included. A fallback death shows
        no region, which is deathfx's NO_SAVE_LINE case — "you can keep going" —
        rather than a blank screen."""
        self.assertIsNone(saves.wake_slot(self.conn))
        state = self.fresh(**{HEALTH: 0})
        result = death.die(self.conn, state, cause="enemy_turn")

        self.assertTrue(result["died"])
        self.assertTrue(result["woke_at"]["fallback"])
        self.assertEqual(result["report"]["wake"]["region"], "")
        self.assertGreaterEqual(result["state"]["player"][HEALTH],
                                death.wake_health(config.STAMINA_MAX))
        # and it cannot happen twice in a row
        self.assertIsNotNone(saves.wake_slot(self.conn))

    def test_boot_writes_a_waking_point_and_does_it_once(self):
        state = self.fresh(**{HEALTH: config.STAMINA_MAX})
        self.assertIsNotNone(death.ensure_wake_point(self.conn, state))
        self.assertIsNone(death.ensure_wake_point(self.conn, state))
        self.assertIsNotNone(saves.wake_slot(self.conn))

    def test_a_corrupt_waking_point_falls_through_to_the_one_before(self):
        first = self.fresh(gold=5, region="python_village")
        saves.apply_state(self.conn, first)
        older = saves.anchor(self.conn, first, "region_entered", note="Village")
        second = copy.deepcopy(first)
        second["player"].update({"gold": 50, "region": "fields_of_syntax"})
        newer = saves.anchor(self.conn, second, "region_entered", note="Fields")

        self.conn.execute("UPDATE save_slots SET body = ? WHERE slot_id = ?",
                          (sqlite3.Binary(b"not-zlib"), newer["slot_id"]))
        self.conn.commit()
        self.assertEqual(saves.verify_slot(self.conn, newer["slot_id"])["status"],
                         "corrupt")

        dying = copy.deepcopy(second)
        dying["player"].update({HEALTH: 0, "gold": 900})
        result = death.die(self.conn, dying, cause="enemy_turn")

        self.assertEqual(result["woke_at"]["slot_id"], older["slot_id"])
        self.assertEqual(result["state"]["player"]["gold"], 5)

    def test_every_waking_point_corrupt_is_still_not_a_wall(self):
        state = self.fresh(gold=5, region="python_village")
        saves.apply_state(self.conn, state)
        written = saves.anchor(self.conn, state, "region_entered")
        self.conn.execute("UPDATE save_slots SET body = ? WHERE slot_id = ?",
                          (sqlite3.Binary(b"gone"), written["slot_id"]))
        self.conn.commit()

        dying = copy.deepcopy(state)
        dying["player"][HEALTH] = 0
        result = death.die(self.conn, dying, cause="enemy_turn")

        self.assertTrue(result["died"])
        self.assertTrue(result["woke_at"]["fallback"])
        self.assertGreaterEqual(result["state"]["player"][HEALTH],
                                death.wake_health(config.STAMINA_MAX))

    def test_the_death_screen_never_shouts(self):
        """Quiet and a little frightening. Not dramatic."""
        text = json.dumps({"causes": death.CAUSES, "anchors": death.ANCHOR_LINES})
        self.assertNotIn("!", text)
        for row in death.CAUSES.values():
            self.assertTrue(row["line"])
            self.assertEqual(row["line"], row["line"].rstrip())


# ===========================================================================
# THE FILE'S OWN SELF-CHECK
# ===========================================================================

class SelfCheck(DeathTest):
    def test_self_check_is_green(self):
        out = death.self_check()
        self.assertTrue(out["ok"], "\n".join(out["failures"]))
        self.assertEqual(out["failures"], [])
        self.assertEqual(out["headline"]["graded_tables_touched_by_dying"], 0)
        self.assertEqual(out["headline"]["mastery_lost"], 0.0)
        self.assertEqual(out["headline"]["attempts_lost"], 0)

    def test_nothing_here_supplies_an_answer(self):
        """A death screen is not a second capability check, and it may not leak
        one word of a problem."""
        text = json.dumps(death.self_check(), default=str)
        for word in ("def solve", "return ", "solution", "answer"):
            self.assertNotIn(word, text.lower().replace("returns", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
