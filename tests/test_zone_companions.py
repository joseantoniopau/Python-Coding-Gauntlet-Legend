"""The five people who walk a zone with you, held to every claim the module
makes about them.

Nothing here builds a Game. This is a pure data layer and a test that needed
thirty seconds of corpus to prove a dict would be testing the wrong thing.

Five properties decide whether this layer is correct, and each has a section:

  THE ARC IS WALKABLE        three companions are taken all the way round —
                             walking, taken, carrying, freed, taken back,
                             freed again — by moving only the keys a real save
                             actually has.
  AN OLD SAVE IS FINE        an empty dict, a save with the wrong types in it
                             and a save written before this file existed all
                             answer correctly and none of them raises.
  THE ITEM IS WORSE          every drop is provably weaker than the person, on
                             a named axis or by a named missing capability.
  IT CANNOT BE MISSED        the drop lands by BOTH roads — taken by the boss,
                             and freed by a player who beat that boss first.
  IT NEVER READS THE EXAM    the module does not import finalexam and does not
                             contain the word `sealed`. The exam is a
                             measurement; this is a story layer.
"""
from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path

import base  # noqa: F401  — puts the repo on sys.path

from gauntlet import captives, config, items, world, zonecompanions as zc

MODULE = Path(base.REPO) / "gauntlet" / "zonecompanions.py"


def blank() -> dict:
    """The smallest save that is still a save: the three lists the engine
    actually keeps, and nothing this module invented."""
    return {"cleared_bosses": [], "dungeons_cleared": [], "inventory": [],
            "world": {"routes_walked": []}}


def clear_dungeon(state: dict, dungeon_id: str) -> None:
    state.setdefault("dungeons_cleared", []).append(dungeon_id)


def beat_boss(state: dict, boss_id: str) -> dict:
    """What engine._resolve_boss does, in the order it does it."""
    state.setdefault("cleared_bosses", []).append(boss_id)
    return captives.free(state, boss_id)


def near_the_end(state: dict) -> None:
    """Walk the ladder far enough that the Interviewer's sweep can fire.

    THE BUG DEMON ALONE IS NOT NEAR THE END, and a test that says it is was
    testing the defect rather than the design. `rt_armorers_stair` runs
    python_village -> debugging_dungeon carrying Need(kind='none'), so it is
    passable on a brand new save; walk the graph from the village square using
    only the roads that need nothing and you reach three regions and exactly
    ONE boss stands in them — the Bug Demon. A player who took the stair under
    the forge on their first afternoon and won had Thessaly Brun collected
    before the tutorial she exists to give. `zc.sweep_fired()` therefore wants
    the name AND the ladder: bug_demon plus at least `len(world.BOSSES) - 2`
    rungs.

    This clears the ladder up to and including the Bug Demon, which is the
    state a player who got there the long way is actually in. It appends to
    `cleared_bosses` only; it never calls `captives.free`, so nobody is
    rescued by walking the ladder.
    """
    cleared = state.setdefault("cleared_bosses", [])
    for boss in world.BOSSES:
        if boss["id"] not in cleared:
            cleared.append(boss["id"])
        if boss["id"] == zc.SWEEP_AFTER_BOSS:
            break


# ---------------------------------------------------------------------------
# The roster
# ---------------------------------------------------------------------------

class TheRosterIsRealPeople(unittest.TestCase):

    def test_both_modules_validate(self):
        self.assertEqual(zc.validate(), [])
        self.assertEqual(captives.validate(), [])

    def test_every_escort_is_a_captive_who_already_existed(self):
        for row in zc.ESCORTS:
            person = captives.CAPTIVE_BY_ID.get(row.id)
            self.assertIsNotNone(person, "%s is not in captives.py" % row.id)
            self.assertEqual(person.boss, row.boss, row.id)
            self.assertIn(person.home, zc.ZONE_BY_ID[row.zone].regions, row.id)
            self.assertTrue(person.name and person.trade, row.id)

    def test_no_new_boss_and_no_new_key(self):
        """Adding a boss would renumber every crutch in the game. This whole
        arc hangs off fourteen bosses that were already there."""
        self.assertEqual(len(world.BOSSES), 14)
        self.assertEqual(len(world.KEYS), 14)
        for row in zc.ESCORTS:
            self.assertIn(row.boss, world.BOSS_BY_ID, row.id)

    def test_five_zones_five_escorts_and_nobody_doubled_up(self):
        self.assertEqual(len(zc.ESCORTS), 5)
        self.assertEqual(len(zc.ZONES), 5)
        self.assertEqual(len({r.zone for r in zc.ESCORTS}), 5)
        rungs = sorted(zc.RUNG[r.boss] for r in zc.ESCORTS)
        self.assertEqual(rungs, [2, 4, 6, 8, 14])

    def test_the_sweep_fires_on_the_second_to_last_rung(self):
        self.assertEqual(zc.RUNG[zc.SWEEP_AFTER_BOSS], len(world.BOSSES) - 1)
        self.assertEqual(zc.SWEEP_AFTER_BOSS, world.BOSSES[-2]["id"])

    def test_the_two_promoted_rows_are_held_downstream_of_their_own_village(self):
        """Halla and Greave are taken out of regions that have no boss. The
        rule that lets that happen is geography, and it is checked against
        world.REGIONS rather than asserted."""
        self.assertEqual(captives.TAKEN_FROM_UPSTREAM,
                         frozenset({"halla_vane", "greave"}))
        for cid in captives.TAKEN_FROM_UPSTREAM:
            person = captives.CAPTIVE_BY_ID[cid]
            cage = world.BOSS_BY_ID[person.boss]["region"]
            self.assertIn(person.home, captives._upstream_of(cage), cid)

    def test_the_reward_still_belongs_to_the_village_the_cage_is_in(self):
        self.assertEqual(captives.home_of("tree_dragon"), "binary_tree_canopy")
        self.assertEqual(captives.home_of("graph_necromancer"), "graph_wastes")


# ---------------------------------------------------------------------------
# The arc, walked end to end
# ---------------------------------------------------------------------------

class TheArcIsWalkable(unittest.TestCase):

    def _walk(self, escort_id):
        """Walking -> taken -> carrying -> freed, by moving only save keys."""
        row = zc.BY_ID[escort_id]
        state = blank()

        self.assertEqual(zc.state_of(state, escort_id), zc.WALKING)
        self.assertEqual(zc.escort_in(state, row_region(row))["id"], escort_id)

        # The capture dungeon's seal is met and the player comes back up.
        clear_dungeon(state, row.capture_dungeon)
        self.assertEqual(zc.state_of(state, escort_id), zc.TAKEN)
        self.assertEqual(zc.escort_in(state, row_region(row)), {})

        scene = zc.capture(state, escort_id)
        self.assertEqual(len(scene["lines"]), 3)
        self.assertTrue(scene["narrator"])
        self.assertTrue(scene["granted"])
        self.assertLessEqual(scene["max_seconds"], 8.0)
        self.assertFalse(scene["blocks_input"])

        # Beat 4 ran in the same transaction: it is already in the bag.
        self.assertIn(row.drop, state["inventory"])
        self.assertEqual(zc.state_of(state, escort_id), zc.ITEM_HELD)
        self.assertEqual(zc.capture(state, escort_id), {},
                         "the scene played twice")

        # Beat 5: the existing rescue call, unchanged.
        rescue = beat_boss(state, row.boss)
        self.assertTrue(rescue)
        self.assertEqual(zc.state_of(state, escort_id), zc.FREED)
        self.assertIn(row.drop, state["inventory"], "they took it back")

        # Beat 6: the thank-you, the keep-it line, and the next zone.
        said = zc.lines_for(state, escort_id)
        self.assertIn(row.thanks[0], said)
        self.assertIn(row.handover, said)
        return state

    def test_the_dark_josa_fell(self):
        state = self._walk("josa_fell")
        self.assertIn("the_lamp", state["inventory"])

    def test_the_snow_hessa_dunmar(self):
        state = self._walk("hessa_dunmar")
        self.assertIn("skate_irons", state["inventory"])
        # Torv is taken in the same scene and freed by the same fight. One
        # escort sprite, two people out.
        self.assertTrue(captives.is_freed(state, "torv_bael"))

    def test_the_fire_greave(self):
        state = self._walk("greave")
        self.assertIn("the_gear", state["inventory"])
        # The Necromancer came up the ore line, and the man he took lives in a
        # region the Wastes unlock from.
        self.assertEqual(captives.CAPTIVE_BY_ID["greave"].home,
                         "stack_queue_mines")
        self.assertEqual(captives.CAPTIVE_BY_ID["greave"].held_in,
                         "graph_wastes")

    def test_the_green_halla_vane(self):
        state = self._walk("halla_vane")
        self.assertIn("the_dart", state["inventory"])

    def test_home_thessaly_brun_is_the_exception_and_the_proof(self):
        """Python Village has no boss and no dungeon, so nothing there can take
        her mid-game. She hands the map over on the first road out, and she is
        taken at the finale with the other two."""
        state = blank()
        self.assertEqual(zc.state_of(state, "thessaly_brun"), zc.WALKING)
        self.assertNotIn("the_slate", state["inventory"])

        state["world"]["routes_walked"].append(zc.SLATE_ROUTE)
        zc.advance(state)
        self.assertIn("the_slate", state["inventory"])
        self.assertEqual(zc.state_of(state, "thessaly_brun"), zc.WALKING,
                         "the map is given, not dropped")

        # THE BUG DEMON ON ITS OWN DOES NOT TAKE HER. It is one hop from the
        # village square on a road that is open at level 1, and a player who
        # beat it on their first afternoon would have lost the tutorial guide
        # before the tutorial. The sweep wants the LADDER as well as the name.
        state["cleared_bosses"].append("bug_demon")
        self.assertEqual(zc.state_of(state, "thessaly_brun"), zc.WALKING)
        self.assertTrue(zc.escort_in(state, "python_village"),
                        "she still walks the village, so the captions happen")

        near_the_end(state)
        self.assertEqual(zc.state_of(state, "thessaly_brun"), zc.TAKEN)
        zc.advance(state)
        self.assertEqual(zc.state_of(state, "thessaly_brun"), zc.ITEM_HELD)

        captives.final_release(state)
        self.assertEqual(zc.state_of(state, "thessaly_brun"), zc.FREED)
        self.assertIn("the_slate", state["inventory"])


def row_region(row):
    return zc.ZONE_BY_ID[row.zone].regions[0]


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------

class TheInterviewerTakesThemAll(unittest.TestCase):

    def _three_freed(self):
        state = blank()
        state["world"]["routes_walked"].append(zc.SLATE_ROUTE)
        zc.advance(state)
        for eid in ("josa_fell", "hessa_dunmar", "greave"):
            row = zc.BY_ID[eid]
            clear_dungeon(state, row.capture_dungeon)
            zc.capture(state, eid)
            beat_boss(state, row.boss)
            self.assertEqual(zc.state_of(state, eid), zc.FREED)
        return state

    def test_the_full_sweep_and_the_release_that_undoes_it(self):
        state = self._three_freed()
        carried = list(state["inventory"])
        roads = list(captives.open_routes(state))
        before = captives.boon_effects(state)

        near_the_end(state)
        out = zc.advance(state)
        sweep = [e for e in out["events"] if e["kind"] == "sweep"]
        self.assertEqual(len(sweep), 1)
        self.assertEqual(sorted(sweep[0]["retaken"]),
                         sorted(["josa_fell", "hessa_dunmar", "greave"]))
        self.assertEqual(len(sweep[0]["lines"]), 3)

        for eid in ("josa_fell", "hessa_dunmar", "greave"):
            self.assertEqual(zc.state_of(state, eid), zc.RETAKEN)
            self.assertTrue(captives.is_retaken(state, eid))

        # It costs boons. It never costs items and it never closes a road.
        self.assertEqual(state["inventory"], carried)
        self.assertIn("the_slate", carried)
        self.assertEqual(captives.open_routes(state), roads)
        after = captives.boon_effects(state)
        self.assertNotEqual(after, before,
                            "the sweep suspended nothing, so it cost nothing")
        # Josa's lamp line is the one with arithmetic on it. It stops.
        self.assertIn("mana_regen", before)
        self.assertNotIn("mana_regen", after)
        # And the road two of them built stays open, because a road that shuts
        # behind a player is a dead end with a story attached.
        self.assertIn("cap_rigged_span", [r["id"] for r in roads])

        # And the roll call strikes them through rather than shortening.
        roll = captives.roll_call(state)
        struck = [r["id"] for r in roll if r["retaken"]]
        self.assertEqual(sorted(struck),
                         sorted(["josa_fell", "hessa_dunmar", "greave"]))
        self.assertTrue(captives.is_freed(state, "josa_fell"))

        # Idempotent: a replayed cutscene cannot suspend a boon twice.
        again = zc.advance(state)
        self.assertEqual([e for e in again["events"] if e["kind"] == "sweep"],
                         [])

        # The finale gives every one of them back.
        released = captives.final_release(state)
        self.assertEqual(sorted(released["given_back"]),
                         sorted(["josa_fell", "hessa_dunmar", "greave"]))
        for eid in ("josa_fell", "hessa_dunmar", "greave"):
            self.assertEqual(zc.state_of(state, eid), zc.FREED)
        # Every suspended boon is back on. The finale also frees three more
        # people out of Python Village, so the dict is LARGER than it was —
        # what is being proved is that nothing the sweep took is still missing.
        restored = captives.boon_effects(state)
        for key, value in before.items():
            self.assertEqual(restored.get(key), value, key)
        self.assertEqual([r["id"] for r in captives.roll_call(state)
                          if r["retaken"]], [])

    def test_the_sweep_never_takes_somebody_a_boss_is_already_holding(self):
        state = blank()
        clear_dungeon(state, zc.BY_ID["josa_fell"].capture_dungeon)
        zc.advance(state)
        self.assertEqual(zc.state_of(state, "josa_fell"), zc.ITEM_HELD)
        near_the_end(state)
        zc.advance(state)
        self.assertFalse(captives.is_retaken(state, "josa_fell"))
        self.assertEqual(zc.state_of(state, "josa_fell"), zc.ITEM_HELD)

    def test_the_sweep_leaves_a_zone_the_player_never_worked_alone(self):
        """A player can reach rung 13 having never gone near the Caverns.
        Taking somebody they have arguably never met is arithmetic, not loss."""
        state = blank()
        near_the_end(state)
        zc.advance(state)
        self.assertEqual(zc.state_of(state, "josa_fell"), zc.WALKING)

    def test_retake_refuses_anybody_who_is_not_out(self):
        state = blank()
        out = captives.retake(state, ["josa_fell"])
        self.assertEqual(out["retaken"], [])
        self.assertFalse(out["first_time"])

    def test_all_five_states_are_reachable(self):
        seen = set()
        state = blank()
        seen.add(zc.state_of(state, "josa_fell"))
        clear_dungeon(state, "sunken_index")
        seen.add(zc.state_of(state, "josa_fell"))
        zc.advance(state)
        seen.add(zc.state_of(state, "josa_fell"))
        beat_boss(state, "three_sum_hydra")
        seen.add(zc.state_of(state, "josa_fell"))
        near_the_end(state)
        zc.advance(state)
        seen.add(zc.state_of(state, "josa_fell"))
        self.assertEqual(seen, set(zc.STATES))

    def test_freed_is_a_state_you_pass_through_and_not_one_you_skip(self):
        """RETAKEN IS A RECORD, NOT A STANDING CONDITION.

        `state_of` used to answer RETAKEN for anybody freed while
        `sweep_fired()` was true, which is a fact about the WORLD rather than
        about the person. Every companion rescued after the Bug Demon fell then
        jumped WALKING/ITEM_HELD straight to RETAKEN and never passed through
        FREED at all — so `lines_for()` never reached its FREED branch and the
        thank-you, the keep-it line and the handover gift for the next zone
        were unreachable for all four dungeon companions.
        """
        for eid in ("josa_fell", "hessa_dunmar", "halla_vane", "greave"):
            with self.subTest(escort=eid):
                row = zc.BY_ID[eid]
                state = blank()
                near_the_end(state)          # the sweep condition is standing
                clear_dungeon(state, row.capture_dungeon)
                zc.capture(state, eid)
                beat_boss(state, row.boss)   # rescued AFTER rung 13 fell

                self.assertEqual(zc.state_of(state, eid), zc.FREED,
                                 "a rescue is not undone by a fact about the "
                                 "world; only captives.retake() takes anybody")
                self.assertFalse(captives.is_retaken(state, eid))
                lines = zc.lines_for(state, eid)
                for thanks in row.thanks:
                    self.assertIn(thanks, lines, "%s never says thank you" % eid)
                self.assertIn(row.handover, lines,
                              "%s never offers the next zone's gift" % eid)

    def test_the_sweep_is_a_one_shot_and_its_roster_freezes(self):
        """It happens once, and it collects who was out when the rung fell.

        `sweep_fired()` is a STANDING fact — the Bug Demon stays beaten — so a
        guard that only asked it re-fired for ever: every companion rescued
        afterwards was collected the moment they were freed, each with its own
        fresh one-time cutscene. Measured before the fix: four separate sweep
        events in one run, and a fifth one tick AFTER the Interviewer was
        already dead.
        """
        state = blank()
        near_the_end(state)
        row = zc.BY_ID["josa_fell"]
        clear_dungeon(state, row.capture_dungeon)
        zc.capture(state, "josa_fell")
        beat_boss(state, row.boss)

        fired = []
        for _ in range(3):
            fired += [e for e in zc.advance(state)["events"]
                      if e["kind"] == "sweep"]
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["retaken"], ["josa_fell"])
        self.assertEqual(state[zc.STATE_KEY]["swept"], [zc.SWEEP_AFTER_BOSS])

        # Somebody rescued AFTER the scene has played is not collected by a
        # second showing of a one-time scene. The roster froze.
        other = zc.BY_ID["hessa_dunmar"]
        clear_dungeon(state, other.capture_dungeon)
        zc.capture(state, "hessa_dunmar")
        beat_boss(state, other.boss)
        after = [e for e in zc.advance(state)["events"] if e["kind"] == "sweep"]
        self.assertEqual(after, [])
        self.assertEqual(zc.state_of(state, "hessa_dunmar"), zc.FREED)

    def test_the_sweep_does_not_fire_from_the_village_square(self):
        """One hop from the start, on a road that is open at level 1."""
        state = blank()
        state["cleared_bosses"].append(zc.SWEEP_AFTER_BOSS)
        self.assertFalse(zc.sweep_fired(state))
        # the ladder without the name is not it either
        state["cleared_bosses"] = [b["id"] for b in world.BOSSES[:13]
                                   if b["id"] != zc.SWEEP_AFTER_BOSS]
        self.assertFalse(zc.sweep_fired(state))
        # the name plus the ladder is
        state["cleared_bosses"].append(zc.SWEEP_AFTER_BOSS)
        self.assertTrue(zc.sweep_fired(state))


# ---------------------------------------------------------------------------
# An old save
# ---------------------------------------------------------------------------

class AnOldSaveStillPlays(unittest.TestCase):

    def test_an_empty_dict_answers_for_everybody(self):
        for eid in zc.ORDER:
            self.assertEqual(zc.state_of({}, eid), zc.WALKING)
        self.assertEqual(zc.snapshot({})["counts"]["walking"], 5)

    def test_a_save_written_before_this_file_existed(self):
        """No `escorts` key, no `captives` key, cleared bosses in the save
        already. The derivation has to reach the right answer with no latch and
        no migration."""
        old = {"cleared_bosses": ["hash_titan", "three_sum_hydra"],
               "dungeons_cleared": ["sunken_index"], "inventory": []}
        # The Hydra is down, so captives.free was never called on this save.
        self.assertEqual(zc.state_of(old, "josa_fell"), zc.TAKEN)
        out = zc.advance(old)
        self.assertIn("the_lamp", old["inventory"])
        self.assertEqual(zc.state_of(old, "josa_fell"), zc.ITEM_HELD)
        self.assertTrue(out["events"])

    def test_nothing_raises_on_a_save_full_of_the_wrong_types(self):
        broken = {"cleared_bosses": None, "dungeons_cleared": "not a list",
                  "inventory": 7, "captives": "gone", "escorts": 4,
                  "world": "burnt"}
        for eid in zc.ORDER:
            self.assertIn(zc.state_of(broken, eid), zc.STATES)
        self.assertTrue(zc.snapshot(broken, "array_caverns"))
        zc.advance(broken)
        # Nothing has happened to anybody on that save, so nothing was written.
        self.assertEqual(zc.states(broken),
                         {eid: zc.WALKING for eid in zc.ORDER})
        # Now give it something to hand over, and watch it repair the bag it
        # was handed rather than refusing to write into it.
        broken["dungeons_cleared"] = ["sunken_index"]
        zc.advance(broken)
        self.assertIsInstance(broken["inventory"], list)
        self.assertIn("the_lamp", broken["inventory"])
        self.assertEqual(zc.state_of(broken, "josa_fell"), zc.ITEM_HELD)

    def test_a_hand_edited_latch_is_repaired_rather_than_trusted(self):
        state = blank()
        state["escorts"] = {"taken": "josa_fell", "given": 3, "scenes": None}
        for eid in zc.ORDER:
            self.assertEqual(zc.state_of(state, eid), zc.WALKING)
        clear_dungeon(state, "sunken_index")
        zc.advance(state)
        self.assertEqual(state["escorts"]["taken"], ["josa_fell"])
        self.assertIn("the_lamp", state["inventory"])

    def test_an_unknown_id_answers_rather_than_raising(self):
        self.assertEqual(zc.state_of(blank(), "nobody_at_all"), "")
        self.assertEqual(zc.view(blank(), "nobody_at_all"), {})
        self.assertEqual(zc.lines_for(blank(), "nobody_at_all"), [])
        self.assertEqual(zc.scene("nobody_at_all"), {})
        self.assertEqual(zc.escort_in(blank(), "dp_ruins"), {})
        self.assertEqual(zc.zone_of("dp_ruins"), {})

    def test_the_answer_is_pure(self):
        """state_of, view, snapshot and lines_for read the save. They do not
        touch it, and a function that decides the arc must not."""
        state = blank()
        state["dungeons_cleared"].append("converging_span")
        before = copy.deepcopy(state)
        for eid in zc.ORDER:
            zc.state_of(state, eid)
            zc.view(state, eid)
            zc.lines_for(state, eid)
        zc.snapshot(state, "twin_pointer_pass")
        zc.states(state)
        zc.sweep_fired(state)
        self.assertEqual(state, before)

    def test_advance_is_idempotent(self):
        state = blank()
        clear_dungeon(state, "ninth_cart")
        first = zc.advance(state)
        snap = copy.deepcopy(state)
        second = zc.advance(state)
        self.assertTrue(first["events"])
        self.assertEqual(second["events"], [])
        self.assertEqual(state, snap)

    def test_the_module_declares_its_own_state_and_forward_fills(self):
        fresh = zc.new_escort_state()
        self.assertEqual(sorted(fresh), ["given", "scenes", "swept", "taken"],
                         "`swept` is the sweep's one-shot latch; it is a LIST "
                         "so _write_bucket's repair covers it for free")
        self.assertTrue(all(v == [] for v in fresh.values()))
        self.assertIn("retaken", captives.new_captive_state())


# ---------------------------------------------------------------------------
# The item is always worse than the person
# ---------------------------------------------------------------------------

class TheItemIsWorseThanThePerson(unittest.TestCase):

    def test_every_capture_costs_something_that_can_be_named(self):
        for row in zc.ESCORTS:
            named = bool(row.lost) or bool(row.metric)
            self.assertTrue(named, "%s: the capture cost nothing" % row.id)
            self.assertTrue(row.loss_line, row.id)
            for key in row.lost:
                self.assertTrue(row.with_them.get(key), row.id)
                self.assertFalse(row.with_item.get(key), row.id)

    def test_the_lamp_is_a_tile_short_and_loses_the_facing_offset(self):
        row = zc.BY_ID["josa_fell"]
        self.assertEqual(row.without["radius"], 2)      # two sprites ahead
        self.assertEqual(row.with_them["radius"], 6)
        self.assertEqual(row.with_item["radius"], 5)
        self.assertEqual(row.with_them["offset"], 2)
        self.assertEqual(row.with_item["offset"], 0)

    def test_the_gear_holds_twelve_seconds_less_than_the_man_did(self):
        row = zc.BY_ID["greave"]
        self.assertEqual(row.with_them["open"] - row.with_item["open"], 12.0)
        self.assertGreater(row.with_item["drain"], row.with_them["drain"])

    def test_the_skates_are_faster_and_still_worse(self):
        row = zc.BY_ID["hessa_dunmar"]
        self.assertGreater(row.with_item["speed_mult"],
                           row.with_them["speed_mult"])
        self.assertTrue(row.with_them["calls_exit"])
        self.assertFalse(row.with_item["calls_exit"])

    def test_the_dart_is_counted_and_she_was_not(self):
        row = zc.BY_ID["halla_vane"]
        self.assertTrue(row.with_them["unlimited"])
        self.assertEqual(row.with_item["charges"], 2)
        self.assertEqual(row.with_item["leaves"], row.with_them["leaves"])
        self.assertEqual(zc.PACK["charges"]["cap"], 2)

    def test_no_zone_item_buys_a_look_at_a_problem(self):
        """The same refusal captives.BOON_EFFECTS_REFUSED makes, for the same
        reason. A zone item is an overworld verb, never a stat line."""
        for drop in zc.DROPS.values():
            self.assertEqual(drop.effects, {}, drop.id)
            self.assertIn(drop.slot, ["weapon", "offhand", "head", "chest",
                                      "hands", "feet", "ring1", "ring2",
                                      "trinket"], drop.id)


# ---------------------------------------------------------------------------
# The item cannot be missed
# ---------------------------------------------------------------------------

class TheDropCannotBeMissed(unittest.TestCase):

    def test_it_lands_when_the_boss_takes_them(self):
        state = blank()
        clear_dungeon(state, "sunken_index")
        zc.advance(state)
        self.assertIn("the_lamp", state["inventory"])

    def test_it_lands_even_for_a_player_who_beat_the_boss_first(self):
        """The capture never fired, so there was nothing to drop. They hand it
        over anyway, because a zone mechanic a player can miss is a dead end
        and this arc does not have one."""
        state = blank()
        beat_boss(state, "tree_dragon")
        self.assertEqual(zc.state_of(state, "halla_vane"), zc.FREED)
        out = zc.advance(state)
        self.assertIn("the_dart", state["inventory"])
        self.assertEqual([e["kind"] for e in out["events"]], ["kept"])

    def test_every_road_out_of_walking_hands_the_item_over(self):
        for row in zc.ESCORTS:
            if row.drop_early:
                continue
            for road in ("taken", "freed"):
                state = blank()
                if road == "taken":
                    clear_dungeon(state, row.capture_dungeon)
                else:
                    beat_boss(state, row.boss)
                zc.advance(state)
                self.assertIn(row.drop, state["inventory"],
                              "%s: missed by the %s road" % (row.id, road))

    def test_the_grant_is_never_doubled(self):
        state = blank()
        clear_dungeon(state, "converging_span")
        for _ in range(4):
            zc.advance(state)
        self.assertEqual(state["inventory"].count("skate_irons"), 1)


# ---------------------------------------------------------------------------
# It is a story layer, and it never reads the exam
# ---------------------------------------------------------------------------

class ItNeverReadsTheExam(unittest.TestCase):

    def test_the_module_never_imports_or_touches_finalexam(self):
        """Checked on the parse tree, not on the prose. The module docstring
        talks about finalexam at some length, and a grep would be satisfied by
        renaming a comment."""
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn("finalexam", alias.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn("finalexam", node.module or "")
                for alias in node.names:
                    self.assertNotEqual(alias.name, "finalexam")
            elif isinstance(node, ast.Attribute):
                self.assertNotEqual(node.attr, "sealed")
                if isinstance(node.value, ast.Name):
                    self.assertNotEqual(node.value.id, "finalexam")
            elif isinstance(node, ast.Name):
                self.assertNotEqual(node.id, "finalexam")
        self.assertNotIn("finalexam", dir(zc))

    def test_the_rung_comes_off_world_bosses_and_not_off_the_ladder(self):
        for n, boss in enumerate(world.BOSSES, 1):
            self.assertEqual(zc.RUNG[boss["id"]], n)

    def test_it_is_gated_to_adventure_mode_like_the_rescue_is(self):
        self.assertFalse(zc.available_in(config.MODE_INTERVIEW))
        self.assertTrue(zc.available_in(config.MODE_ADVENTURE))

    def test_nothing_here_supplies_an_answer(self):
        """Every line in the file is about a place, a person or a verb. None of
        it may name a category, a weakness or a value."""
        banned = ("reveal_category", "probe_reveal_value", "weakness_scan",
                  "perf_insight", "probe_charges")
        source = MODULE.read_text(encoding="utf-8")
        for word in banned:
            self.assertNotIn(word + '"', source)
            self.assertNotIn(word + "'", source)

    def test_the_bill_items_py_still_owes_is_stated_rather_than_assumed(self):
        """These five items do not exist yet and this module does not own
        items.py. Nothing raises; the bill is a list."""
        owed = zc.missing_items()
        self.assertEqual(set(owed) - set(zc.DROPS), set())
        for drop_id in owed:
            self.assertTrue(zc.DROPS[drop_id].mechanic)
            self.assertFalse(zc.drop_view(drop_id)["in_catalogue"])


# ---------------------------------------------------------------------------
# The telling
# ---------------------------------------------------------------------------

class TheyAreWrittenAsPeople(unittest.TestCase):

    def test_everybody_has_something_to_say_in_every_state(self):
        for eid in zc.ORDER:
            row = zc.BY_ID[eid]
            self.assertTrue(row.walking, eid)
            self.assertEqual(len(row.capture), 3, eid)
            self.assertTrue(row.narrator, eid)
            self.assertTrue(row.thanks, eid)
            self.assertTrue(row.handover, eid)
            self.assertTrue(row.retaken_line, eid)

    def test_the_capture_is_about_their_own_life(self):
        for row in zc.ESCORTS:
            at_player = sum(1 for line in row.capture
                            if "you" in line.lower().split()[:4])
            self.assertLess(at_player, len(row.capture), row.id)

    def test_rule_seven_of_the_bible_no_exclamation_marks(self):
        for row in zc.ESCORTS:
            for line in (row.role, row.verb, row.narrator, row.loss_line,
                         row.handover, row.retaken_line, *row.walking,
                         *row.capture, *row.thanks):
                self.assertNotIn("!", line, row.id)

    def test_lines_change_with_the_state(self):
        state = blank()
        walking = zc.lines_for(state, "greave")
        clear_dungeon(state, "ninth_cart")
        taken = zc.lines_for(state, "greave")
        zc.advance(state)
        held = zc.lines_for(state, "greave")
        beat_boss(state, "graph_necromancer")
        freed = zc.lines_for(state, "greave")
        self.assertEqual(len({tuple(walking), tuple(taken), tuple(held),
                              tuple(freed)}), 4)
        self.assertIn(captives.CAPTIVE_BY_ID["greave"].lines[0], freed)

    def test_the_snapshot_is_one_call_for_the_whole_panel(self):
        state = blank()
        snap = zc.snapshot(state, "array_caverns")
        self.assertEqual(len(snap["escorts"]), 5)
        self.assertEqual(snap["here"]["id"], "josa_fell")
        self.assertEqual(snap["zone"]["id"], "the_dark")
        self.assertEqual(snap["counts"]["total"], 5)
        self.assertFalse(snap["sweep"])

    def test_the_release_lines_the_ending_needs_exist_for_the_new_rows(self):
        for cid in ("halla_vane", "greave"):
            line = captives.RELEASE_LINES[cid]
            self.assertGreater(len(line), 80, cid)
            self.assertIn("nobody", line.lower(), cid)


# ---------------------------------------------------------------------------
# The five rows items.py owed, and the two ways they could have been wrong
# ---------------------------------------------------------------------------

class TheDropsAreRealItems(unittest.TestCase):

    def test_every_drop_is_in_the_catalogue(self):
        """Until these landed, a granted drop was a string the catalogue had
        never heard of: `engine._item()` returned None, the loadout loop
        skipped it, and `equip` refused with "you do not carry that" — which
        made `skate_irons`, slot `feet`, a slot that could never be filled
        while §4.1 makes ice control conditional on it being EQUIPPED."""
        self.assertEqual(zc.missing_items(), [])
        self.assertEqual(zc.self_check()["drops_in_catalogue"], len(zc.DROPS))
        for drop_id, drop in zc.DROPS.items():
            with self.subTest(drop=drop_id):
                row = items.BY_ID.get(drop_id)
                self.assertIsNotNone(row, drop_id)
                self.assertEqual(row.slot, drop.slot)
                self.assertEqual(row.rarity, drop.rarity)
                self.assertEqual(row.element, drop.element)
                self.assertEqual(dict(row.effects), {},
                                 "a zone item is an overworld verb, never a "
                                 "stat line: a number here would quietly pay "
                                 "back some of the loss the arc is built on")
                self.assertFalse(row.hidden, "it is meant to be looked at")
                self.assertIn(row.slot, items.SLOTS)
                self.assertIn(row.rarity, items.RARITIES)

    def test_a_drop_is_handed_over_and_never_found(self):
        """HANDED OVER IS NOT FOUND. Every one of these arrives from a named
        person, in a scene, at a moment the arc chose. Left in the ordinary
        loot pool they were rollable out of any chest: measured at 158 of
        4,275 rolled items, 3.7% — the Lamp arriving before Josa Fell has said
        a word."""
        import random
        zone = set(zc.DROPS)
        for row in (items.BY_ID[d] for d in zone):
            self.assertEqual(row.source, "quest", row.id)
        rolled = leaked = 0
        for seed in range(3000):
            for boss in (False, True):
                out = items.roll_drop(difficulty="normal", rank="A", luck=0.4,
                                      is_boss=boss, rng=random.Random(seed))
                if out and out.get("kind") == "item":
                    rolled += 1
                    if out["id"] in zone:
                        leaked += 1
        self.assertGreater(rolled, 1000, "the sample proved nothing")
        self.assertEqual(leaked, 0)


# ---------------------------------------------------------------------------
# The drop follows the BAG, not the ledger
# ---------------------------------------------------------------------------

class TheItemCannotBeLostEither(unittest.TestCase):

    def test_a_drop_that_leaves_the_bag_is_granted_again(self):
        """`raw["given"]` is a RECORD of what was handed over; the inventory is
        the FACT of whether the player has it. Guarding the re-grant on the
        record meant a drop removed by any route was gone for good, while
        `state_of()` went on answering ITEM_HELD off the capture latch — so the
        zone mechanic was gone and nothing anywhere said so."""
        row = zc.BY_ID["josa_fell"]
        state = blank()
        clear_dungeon(state, row.capture_dungeon)
        zc.capture(state, "josa_fell")
        self.assertIn(row.drop, state["inventory"])
        beat_boss(state, row.boss)
        self.assertEqual(zc.state_of(state, "josa_fell"), zc.FREED)

        state["inventory"].remove(row.drop)
        out = zc.advance(state)
        self.assertIn(row.drop, state["inventory"])
        self.assertTrue(zc.view(state, "josa_fell")["held"])
        self.assertEqual([e["kind"] for e in out["events"]], ["kept"])
        # and it is still idempotent: the second tick does nothing at all
        self.assertEqual(zc.advance(state)["events"], [])
        self.assertEqual(state["inventory"].count(row.drop), 1)


# ---------------------------------------------------------------------------
# A save written before two people were promoted into CAPTIVES
# ---------------------------------------------------------------------------

class ThePromotedAreNotStranded(unittest.TestCase):

    def test_a_save_that_beat_their_boss_before_the_promotion(self):
        """`free()` returns {} the moment the boss is already in `raw["bosses"]`
        — correctly, so a rematch cannot pay twice — and it does that BEFORE
        the per-person loop. Promoting halla_vane and greave therefore stranded
        them on every save that had already beaten the Tree Dragon or the
        Necromancer: is_freed False, a rematch that changed nothing, and two
        people `still_held()` listed that the player had demonstrably walked
        past. They held the dart and the gear with no thank-you and no handover
        for the rest of the run."""
        state = blank()
        state["cleared_bosses"] = ["tree_dragon", "graph_necromancer"]
        state["dungeons_cleared"] = ["anagram_deeps", "ninth_cart"]
        raw = state.setdefault(captives.STATE_KEY, captives.new_captive_state())
        # the save as it was written, before the two rows existed
        raw["bosses"] = ["tree_dragon", "graph_necromancer"]
        raw["freed"] = ["oskar_lind", "jessamy_roke", "abel_sarrow"]

        self.assertFalse(captives.is_freed(state, "halla_vane"))

        filled = captives.repair(state)
        self.assertEqual(sorted(filled["filled"]), ["greave", "halla_vane"])
        self.assertEqual(captives.free(state, "tree_dragon"), {},
                         "a rematch still pays nothing, which is the point")
        for cid in ("halla_vane", "greave"):
            self.assertTrue(captives.is_freed(state, cid), cid)
            self.assertEqual(zc.state_of(state, cid), zc.FREED, cid)
        held = [p.id for p in captives.still_held(state)]
        self.assertNotIn("halla_vane", held)
        self.assertNotIn("greave", held)

        # and it is derivation, not migration: a second call fills nothing
        self.assertEqual(captives.repair(state)["filled"], [])

        # ANY writer heals it, not just `repair()`. `_bucket()` is the one
        # function every writer in captives.py goes through, which is why the
        # fill lives there: a save that is loaded and then written to for any
        # reason at all comes back correct without a migration step.
        other = copy.deepcopy(state)
        other[captives.STATE_KEY]["freed"] = ["oskar_lind", "jessamy_roke",
                                              "abel_sarrow"]
        captives.free(other, "hash_titan")      # a completely unrelated boss
        self.assertTrue(captives.is_freed(other, "halla_vane"))
        self.assertTrue(captives.is_freed(other, "greave"))

        # the arc then hands both items over, which is what the strand cost
        zc.advance(state)
        self.assertIn("the_dart", state["inventory"])
        self.assertIn("the_gear", state["inventory"])


if __name__ == "__main__":
    unittest.main()
