"""The apex hunters: the way out, the curve, and the floor under the art.

Three properties, in the order they are allowed to fail in — which is to say
the first one is not allowed to fail at all.

  1. THE ESCAPE ALWAYS EXISTS. There is no combination of region, health,
     purse, armour, companion, geometry or bad luck in which a hunted player
     cannot leave. This is checked by simulation over the whole roster rather
     than by reading the constants back, because a guarantee that is only true
     of the constants is a guarantee that survives exactly until somebody adds
     a state. Every other test in this file is subordinate to this one.
  2. PREPARATION IS THE CURVE. The brief asked for "very hard" when you are new
     to an area and "normal to hard" once you have upgraded for it. Both are
     numbers here: casts to kill, points taken, and the band each one lands in.
     The apex must not read a level, an XP total or a mastery score to get
     there, and `hunters.self_check` greps its own source to prove it.
  3. NEVER UNWINNABLE. elements.py promises a mismatched fight is at most four
     times longer and always terminates. An apex sizes its pool from the
     player's OWN per-cast damage, so the mismatch must be priced once, not
     twice — the worst loadout in the game must not produce a fight four times
     the length of the best one.

The art floor and the "no hunter, no cost" claim are measured in JavaScript by
scripts/verify/*.mjs, because they are claims about rendered pixels and about
allocation counts and neither is visible from Python. The last class here shells
out to them and is skipped, not failed, where node is absent — a missing
toolchain is not a broken game.
"""
from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gauntlet import config                 # noqa: E402
from gauntlet import elements as E          # noqa: E402
from gauntlet import hunters as H           # noqa: E402
from gauntlet import world                  # noqa: E402

REGIONS = [r["id"] for r in world.REGIONS]
ENEMY_BASE_DAMAGE = config.STAMINA_LOSS_FAILED_SUBMIT   # engine's own anchor


def drive(hunt, moment, seconds, dt=0.05, stop=("SPENT", "DORMANT", "ENGAGED")):
    """Run a hunt forward and report what happened. Returns (hunt, elapsed)."""
    elapsed = 0.0
    while elapsed < seconds:
        hunt, _events = H.hunt_step(hunt, moment, dt)
        elapsed += dt
        if hunt.state in stop:
            break
    return hunt, elapsed


def closing_hunt(region, distance=None):
    """A hunt in the worst state the machine has, at contact range."""
    hunt = H.new_hunt(region)
    hunt.state = "CLOSING"
    hunt.distance = float(H.CONTACT_PX if distance is None else distance)
    hunt.best_distance = hunt.distance
    hunt.scent = 1.0
    return hunt


# ---------------------------------------------------------------------------
# 1. The escape
# ---------------------------------------------------------------------------

class TestTheEscapeAlwaysExists(unittest.TestCase):
    """The guarantee that outranks every other check in this file."""

    def test_nothing_in_the_game_moves_faster_than_the_player(self):
        """G1. Not usually, not in most states. In all of them."""
        for state, speed in H.STATE_SPEED.items():
            self.assertLess(speed, H.PLAYER_WALK_SPEED,
                            f"{state} moves at {speed} against a player at "
                            f"{H.PLAYER_WALK_SPEED}. Fleeing stopped being "
                            f"subtraction.")
        self.assertGreater(H.SPEED_MARGIN, 0)

    def test_a_player_who_walks_away_is_never_caught_anywhere(self):
        """Every region, crossed with every awful condition at once.

        Broke is not in the matrix because being broke is not an input: no
        guarantee in this module reads gold, and `escape_guarantees` says so in
        G6. The rest of the brief's list is here — unarmoured and at low health
        (health_fraction), deep in a dungeon (in_dungeon), boxed into a dead
        end (free_tiles), and at the far edge of a region (near_exit) — and the
        player is holding a direction, which is the whole technique.
        """
        caught = []
        for region in REGIONS:
            for health, free, dungeon, sanctuary, exitish in itertools.product(
                    (1.0, 0.31, 0.30, 0.05, 0.01),
                    (999, H.MIN_FREE_TILES, H.MIN_FREE_TILES - 1, 0),
                    (False, True), (False, True), (False, True)):
                hunt = closing_hunt(region)
                moment = H.Moment(moving=True, health_fraction=health,
                                  free_tiles=free, in_dungeon=dungeon,
                                  in_sanctuary=sanctuary, near_exit=exitish,
                                  clears=99, seed=13)
                hunt, _t = drive(hunt, moment, 200.0)
                if hunt.state == "ENGAGED":
                    caught.append((region, health, free, dungeon, sanctuary,
                                   exitish))
        self.assertEqual(caught, [], f"{len(caught)} of 2720 walk-away cases "
                                     f"ended in contact. First: {caught[:3]}")

    def test_every_hunt_a_guarantee_stops_actually_finishes_leaving(self):
        """The condition is HELD DOWN, which is the realistic case.

        A player who ducks into a dungeon stays in it. A player who walks into
        a cul-de-sac is in it for as long as it takes them to walk back out. An
        override that fires every tick and restarts the retreat every tick
        leaves a creature parked at the threshold with the region's cooldown
        never set — the guarantee holds and the state machine stops being one.
        """
        for label, field, value in (("dungeon", "in_dungeon", True),
                                    ("no room", "free_tiles",
                                     H.MIN_FREE_TILES - 1),
                                    ("sanctuary", "in_sanctuary", True)):
            with self.subTest(label):
                hunt = closing_hunt("stack_queue_mines", H.CLOSE_PX)
                moment = H.Moment(moving=True, health_fraction=1.0,
                                  free_tiles=999, clears=99, seed=1)
                setattr(moment, field, value)
                hunt, elapsed = drive(hunt, moment, 600.0)
                self.assertIn(hunt.state, ("SPENT", "DORMANT"),
                              f"pinned in {hunt.state} for {elapsed:.0f}s")
                self.assertGreater(hunt.cooldown, 0,
                                   "it left without the region resting, so the "
                                   "region can neither rest nor hunt again")
                self.assertLess(elapsed, H.FADE_SECONDS + 2.0)

    def test_a_dying_player_is_never_closed_on_even_mid_chase(self):
        """G7 in the ordering a player meets it in.

        Being hurt and then noticed is rare. Being noticed and then hurt is the
        normal way round, and it is the one a gate checked only on the
        TRACKING -> CLOSING transition cannot see.
        """
        hunt = closing_hunt("complexity_tower", H.CLOSE_PX)
        hurt = H.Moment(moving=False,
                        health_fraction=H.LOW_HEALTH_FRACTION - 0.25,
                        free_tiles=999, clears=99, seed=2)
        closest = hunt.distance
        elapsed = 0.0
        while elapsed < 300.0:
            hunt, _events = H.hunt_step(hunt, hurt, 0.05)
            elapsed += 0.05
            closest = min(closest, hunt.distance)
            self.assertNotEqual(hunt.state, "CLOSING",
                                "it committed to a player below the line")
            self.assertNotEqual(hunt.state, "ENGAGED",
                                "it reached a player below the line")
            if hunt.state in ("SPENT", "DORMANT"):
                break
        self.assertGreaterEqual(
            round(closest, 3), H.SCENT_LAG_PX["TRACKING"],
            "it walked in on a dying player. TRACKING follows the TRAIL, and "
            "the trail is SCENT_LAG_PX behind — being held at TRACKING has to "
            "mean being held at a distance or the guarantee is a label on a "
            "creature standing over them.")

    def test_standing_still_and_typing_is_not_a_trap(self):
        """The state this game's player is in for most of their playtime.

        Standing still adds no scent, so a roaming apex cannot find a
        stationary player. Without a floor it walked onto them anyway and sat
        there; without an ending the hunt never resolved and the telegraph
        never stopped. Both halves are pinned here.
        """
        hunt = H.new_hunt("stack_queue_mines")
        hunt.state = "ROAMING"
        hunt.distance = float(H.SPAWN_MAX_PX)
        still = H.Moment(moving=False, health_fraction=1.0, free_tiles=999,
                         clears=99, seed=1)
        closest = hunt.distance
        elapsed = 0.0
        while elapsed < 900.0:
            hunt, _events = H.hunt_step(hunt, still, 0.05)
            elapsed += 0.05
            if hunt.state == "ROAMING":
                closest = min(closest, hunt.distance)
            if hunt.state in ("SPENT", "DORMANT", "ENGAGED"):
                break
        self.assertIn(hunt.state, ("SPENT", "DORMANT"))
        self.assertGreaterEqual(round(closest, 3), H.ROAM_FLOOR_PX,
                                "it walked onto somebody it had not found")

    def test_fleeing_is_a_button_and_never_a_roll(self):
        """G2. Turn one included, and it costs nothing that cannot be regained
        by typing."""
        self.assertTrue(H.FLEE_ALWAYS_SUCCEEDS)
        self.assertEqual(H.FLEE_AVAILABLE_FROM_TURN, 1)
        for region in REGIONS:
            hunt = H.new_hunt(region)
            hunt.state = "ENGAGED"
            for turn in (1, 2, 40):
                verdict = H.can_flee(hunt, turn)
                self.assertTrue(verdict["allowed"])
                self.assertIsNone(verdict["roll"])
            after = H.flee(hunt)
            self.assertEqual(after.state, "SPENT")
            self.assertEqual(after.flights, 1)
        for costs in (H.FLEE_COSTS_GOLD, H.FLEE_COSTS_ITEMS,
                      H.FLEE_COSTS_MASTERY):
            self.assertFalse(costs, "flight started charging for itself")

    def test_leaving_the_region_always_resolves_the_hunt(self):
        """G3. In every state it can be in, including the one mid-contact."""
        for region in REGIONS:
            for state in H.HUNT_STATES:
                hunt = H.new_hunt(region)
                hunt.state = state
                hunt.distance = 40.0
                hunt.scent = 1.0
                after = H.leave_region(hunt)
                self.assertEqual(after.state, "SPENT", f"{region}/{state}")
                self.assertEqual(after.scent, 0.0)
                self.assertGreaterEqual(after.cooldown, H.GLOBAL_COOLDOWN_S)

    def test_it_never_spawns_anywhere_that_would_corner_you(self):
        """Every refusal in `spawn_check`, one at a time, against an otherwise
        perfectly eligible region."""
        ready = dict(moving=True, health_fraction=1.0, free_tiles=999,
                     clears=99, seed=4)
        base = H.new_hunt("twin_pointer_pass")
        base.dwell = H.MIN_REGION_DWELL_S + 10
        base.pressure = 1e6
        self.assertTrue(H.spawn_check(base, H.Moment(**ready), 1.0)["eligible"])
        for field, value in (("in_dungeon", True), ("in_sanctuary", True),
                             ("near_exit", True), ("in_battle", True),
                             ("sealed", True),
                             ("free_tiles", H.MIN_FREE_TILES - 1),
                             ("health_fraction", H.LOW_HEALTH_FRACTION - 0.01),
                             ("global_cooldown", 1.0), ("clears", 0)):
            with self.subTest(field):
                moment = H.Moment(**dict(ready, **{field: value}))
                check = H.spawn_check(base, moment, 1.0)
                self.assertFalse(check["eligible"], check["blockers"])
                self.assertFalse(check["ready"])

    def test_the_module_says_all_eight_guarantees_hold(self):
        for name, row in H.escape_guarantees().items():
            self.assertTrue(row["holds"], f"{name} stopped holding: {row}")

    def test_every_state_a_player_can_witness_telegraphs_itself(self):
        """A hunter you cannot measure is a hunter you can only be surprised
        by. CLOSING must print an actual number of seconds."""
        for state in ("STIRRING", "ROAMING", "TRACKING", "CLOSING", "ENGAGED",
                      "FADING"):
            self.assertIn(state, H.TELEGRAPH)
            hunt = H.new_hunt("twin_pointer_pass")
            hunt.state = state
            hunt.distance = 300.0
            row = H.telegraph(hunt)
            self.assertTrue(row["line"])
            self.assertLessEqual(row["vignette"], 0.26)
        hunt = H.new_hunt("twin_pointer_pass")
        hunt.state = "CLOSING"
        hunt.distance = float(H.CLOSE_PX)
        self.assertIsInstance(H.telegraph(hunt)["seconds"], float)

    def test_an_unknown_region_is_a_shrug_and_not_an_exception(self):
        self.assertIsNone(H.apex_for("no_such_place"))
        self.assertIsNone(H.scale_for("no_such_place"))
        self.assertIsNone(H.bounty("no_such_place", 50))
        self.assertEqual(H.readiness("no_such_place").score, 0)
        hunt = H.new_hunt("no_such_place")
        hunt, _t = drive(hunt, H.Moment(moving=True, clears=99), 5.0)
        self.assertEqual(hunt.state, "DORMANT")


# ---------------------------------------------------------------------------
# 2. The curve
# ---------------------------------------------------------------------------

def apex_defender(apex):
    """The Defender a caller must build for an apex.

    Flat mitigation is deliberately absent: `scale_for` derives the pool from
    the player's per-cast damage BEFORE armour, so an apex that also carried
    armour points would lengthen every fight past its authored cast count.
    """
    return E.Defender(element=apex.element, elements=apex.elements,
                      armour=E.NO_ARMOUR, max_health=0)


def player_defender(loadout):
    profile = E.ArmourProfile(points=loadout.armour_points,
                              resist=dict(loadout.armour_resist))
    return E.Defender(element=E.NEUTRAL, armour=profile,
                      max_health=config.STAMINA_MAX + loadout.bar_bonus)


def fight(region, loadout, miss_rate=0.30):
    """One apex, one loadout, resolved through the real damage function."""
    apex = H.apex_for(region)
    ready = H.readiness(region, loadout)
    scale = H.scale_for(region, loadout, ready=ready)
    rung = max(0, min(9, int(loadout.weapon_rung or 0)))
    base = int(round(H.CAST_DAMAGE_REFERENCE * H.RUNG_DAMAGE_SCALE[rung]))
    cast = E.resolve_damage(base, loadout.weapon_element, apex_defender(apex),
                            roll=1.0, can_inflict=False)
    casts = -(-scale.hp // max(1, cast.damage))
    swing = E.resolve_damage(
        max(0, int(round(ENEMY_BASE_DAMAGE * scale.strike_multiplier))),
        apex.element, player_defender(loadout), roll=1.0, can_inflict=False)
    bar = config.STAMINA_MAX + loadout.bar_bonus
    return {"readiness": ready.score, "band": ready.band,
            "target_casts": scale.target_casts, "real_casts": casts,
            "per_cast": cast.damage, "strike": scale.strike_multiplier,
            "swing": swing.damage, "bar": bar,
            "taken": casts * miss_rate * swing.damage}


def unprepared():
    """Walked in off the previous region with what it gave you."""
    return H.Loadout(weapon_element=E.NEUTRAL, weapon_rung=1, armour_points=0,
                     armour_resist={}, bar_bonus=0, companion_tier="",
                     potions={})


def did_the_work(apex):
    """Read the wheel, went to the forge, brought the pet and the pouch."""
    best, _mult = H.best_available(apex)
    resist = {apex.element: 0.45} if apex.element in E.ELEMENTS else {}
    return H.Loadout(weapon_element=best, weapon_rung=apex.required_rung,
                     armour_points=7, armour_resist=resist, bar_bonus=8,
                     companion_tier="MASTER",
                     potions={"medium": 2, "small": 2})


def the_worst_loadout(apex):
    """The ground's own element, no forge, no armour, no pouch, no companion.

    Requirement 3's player: wrong element and nothing to drink.
    """
    return H.Loadout(weapon_element=apex.element, weapon_rung=0,
                     armour_points=0, armour_resist={}, bar_bonus=0,
                     companion_tier="", potions={})


class TestPreparationIsTheCurve(unittest.TestCase):

    def test_it_reads_no_level_no_xp_and_no_mastery(self):
        """The whole design in one assertion. `_reads_no_progression` strips
        this module's docstrings and comments and greps what is left."""
        verdict = H._reads_no_progression()
        self.assertTrue(verdict["checked"])
        self.assertEqual(verdict["hits"], [],
                         "the apex started scaling against progression")

    def test_more_preparation_is_always_fewer_casts_and_a_softer_blow(self):
        """Monotone, with no local flat spot to farm and no inversion."""
        rows = H.curve("twin_pointer_pass")
        casts = [r["casts"] for r in rows]
        strikes = [r["strike_multiplier"] for r in rows]
        self.assertEqual(casts, sorted(casts, reverse=True))
        self.assertEqual(strikes, sorted(strikes, reverse=True))
        # The Pass is CHAPTER_ANCHOR's ground, which is why these two legacy
        # constants are still the right ends for this particular curve.
        self.assertEqual(H.chapter_for_region("twin_pointer_pass"),
                         H.CHAPTER_ANCHOR)
        self.assertEqual(casts[0], H.CASTS_AT_UNREADY)
        self.assertEqual(casts[-1], H.CASTS_AT_READY)
        for a, b in zip(casts, casts[1:]):
            self.assertGreater(a, b, "a readiness step bought nothing")

    def test_very_hard_when_you_are_new_and_normal_to_hard_once_you_upgrade(self):
        """The brief's two sentences, as numbers, in every region.

        THE THRESHOLDS ARE NOW THE CHAPTER'S, NOT THE GAME'S. They used to be
        two literals — at least forty-five casts unprepared, no more than
        thirty-six prepared — which were true when every apex in the game was
        26/52. Since `hunters.casts_at_ready` ramps the band along
        `curriculum.CHAPTERS`, a literal here would be asserting the flat design
        the ramp replaced: chapter I is 14/28 and chapter XI is 44/88, and both
        of those fail a forty-five-cast floor for opposite reasons.

        So "very hard" is read as: within ten percent of this chapter's
        unprepared length, at very nearly this chapter's unprepared multiplier,
        and above 1.2x in absolute terms wherever you are. "Normal to hard" is
        read as: inside half again this chapter's prepared length, at no more
        than 1.2x. The gap between them has to be worth the trip to the forge,
        so the unprepared fight is also required to be at least 1.35 times the
        length of the prepared one, and that one IS chapter-independent because
        it is a statement about preparation rather than about depth.
        """
        for region in REGIONS:
            apex = H.apex_for(region)
            chapter = H.chapter_for_region(region)
            long_fight = H.casts_at_unready(chapter)
            short_fight = H.casts_at_ready(chapter)
            hardest = H.strike_at_unready(chapter)
            with self.subTest(region):
                new = fight(region, unprepared())
                done = fight(region, did_the_work(apex))

                self.assertLess(new["readiness"], 25, "a newcomer scored well")
                self.assertEqual(H.band_for(new["readiness"]), "UNPREPARED")
                self.assertGreaterEqual(new["real_casts"], long_fight * 0.90)
                self.assertGreater(new["strike"], 1.2)
                self.assertGreater(new["strike"], hardest - 0.10)

                self.assertGreaterEqual(done["readiness"], 50,
                                        "doing the area's work did not reach "
                                        "the band the area was built for")
                self.assertIn(done["band"], ("READY", "SEASONED"))
                self.assertLessEqual(done["real_casts"], short_fight * 1.45)
                self.assertLessEqual(done["strike"], 1.2)

                self.assertGreaterEqual(
                    new["real_casts"] / done["real_casts"], 1.35,
                    "preparation stopped being worth the trip")
                self.assertGreater(new["taken"], done["taken"] * 2.5,
                                   "being unprepared stopped hurting")

    def test_the_work_of_every_area_is_actually_completable(self):
        """A region whose best available loadout cannot reach the top band is a
        region with a permanently harder apex than its neighbours, which is not
        what "difficulty from preparation" means."""
        for region in REGIONS:
            apex = H.apex_for(region)
            best, _mult = H.best_available(apex)
            resist = ({apex.element: E.RESIST_CAP}
                      if apex.element in E.ELEMENTS else {})
            perfect = H.Loadout(weapon_element=best,
                                weapon_rung=min(9, apex.required_rung + 3),
                                armour_points=12, armour_resist=resist,
                                bar_bonus=14, companion_tier="LEGENDARY",
                                potions={"hefty": 2, "medium": 1})
            score = H.readiness(region, perfect).score
            with self.subTest(region):
                self.assertGreaterEqual(score, 90, f"ceiling is {score}")
                self.assertEqual(H.band_for(score), "SEASONED")

    def test_the_derived_pool_produces_the_cast_count_it_authored(self):
        """`scale_for` sizes hit points from expected damage. Resolve the same
        cast through the real function and the answer has to agree, or the
        authored number is a fiction."""
        for region in REGIONS:
            apex = H.apex_for(region)
            for label, loadout in (("unprepared", unprepared()),
                                   ("prepared", did_the_work(apex)),
                                   ("worst", the_worst_loadout(apex))):
                row = fight(region, loadout)
                # RELATIVE, because the ramp made the fights longer. The drift
                # between the authored count and the measured one is the
                # per-cast integer rounding in elements.resolve_damage, which is
                # a PERCENTAGE of the fight rather than a fixed number of casts:
                # four casts was 8% of a flat fifty-two and is 5% of a
                # chapter-XI eighty-eight. Holding the absolute number would
                # tighten the test on exactly the fights that got longer.
                slack = max(4, int(round(row["target_casts"] * 0.08)))
                with self.subTest(f"{region}/{label}"):
                    self.assertLessEqual(
                        abs(row["real_casts"] - row["target_casts"]), slack,
                        f"authored {row['target_casts']} casts, measured "
                        f"{row['real_casts']}")

    def test_the_readout_names_what_is_missing_worst_gap_first(self):
        """The apex as a mirror: the advice has to be ordered by what it would
        actually buy, or it is a list rather than a plan."""
        for region in REGIONS:
            ready = H.readiness(region, unprepared())
            with self.subTest(region):
                self.assertTrue(ready.advice, "a bare player was told nothing")
                self.assertTrue(all(isinstance(a, str) for a in ready.advice))
            perfect_apex = H.apex_for(region)
            done = H.readiness(region, did_the_work(perfect_apex))
            self.assertLess(len(done.advice), len(ready.advice) + 1)

    def test_the_bounty_pays_for_bravery_and_cannot_be_farmed_by_stripping(self):
        """It reads the PEAK readiness of the whole hunt, so taking your armour
        off on the last cast cannot lower a maximum."""
        for region in REGIONS:
            low = H.bounty(region, 0)
            high = H.bounty(region, 100)
            with self.subTest(region):
                if H.apex_for(region).metal:
                    self.assertGreater(low.metal_units, high.metal_units)
                else:
                    # forge.NO_METAL_REGIONS. The village pays the difference
                    # in gold rather than dropping a reward on the floor.
                    self.assertEqual(low.metal_units, 0)
                    self.assertEqual(high.metal_units, 0)
                self.assertGreater(low.gold, high.gold)
                self.assertGreater(low.trophy_chance, high.trophy_chance)
                self.assertEqual(low.mastery_granted, 0)
                self.assertEqual(high.mastery_granted, 0)
                self.assertTrue(H.bounty(region, 100,
                                         first_kill=True).trophy_guaranteed)


# ---------------------------------------------------------------------------
# 3. Never unwinnable
# ---------------------------------------------------------------------------

class TestTheChapterRamp(unittest.TestCase):
    """Section A of the fifth brief: the hunt ramps, and readiness still halves
    it at every rung of the ramp."""

    def test_the_chapter_comes_from_the_ground_and_not_from_the_player(self):
        """The one thing that would turn this into the level check the whole
        module exists to refuse. A region's chapter is a map fact: it is derived
        from curriculum.CHAPTERS[i].region, it takes no player argument, and it
        is the same integer for everybody who ever stands there."""
        import inspect
        import re
        source = inspect.getsource(H.chapter_for_region) + \
            inspect.getsource(H._chapter_by_region)
        # Docstrings and comments stripped first, the same way
        # `_reads_no_progression` does it: the prose in this module talks about
        # players constantly, because that is the argument of the file, and the
        # difference worth asserting is between saying so and doing so.
        code = re.sub(r'"""(?:.|\n)*?"""', "", source)
        code = re.sub(r"#[^\n]*", "", code)
        for forbidden in ("state", "skills", "player", "xp", "level",
                          "mastery"):
            self.assertNotIn(forbidden, code,
                             f"the chapter map reads {forbidden}")
        first = H.chapter_for_region("graph_wastes")
        self.assertEqual(first, H.chapter_for_region("graph_wastes"))
        self.assertEqual(H._reads_no_progression()["hits"], [])

    def test_every_region_lands_on_a_chapter_that_exists(self):
        for row in world.REGIONS:
            chapter = H.chapter_for_region(row["id"])
            with self.subTest(row["id"]):
                self.assertIn(chapter, range(H.CHAPTER_COUNT))

    def test_readiness_halves_the_fight_at_every_chapter(self):
        """The invariant, not the coincidence. It used to be true because 26 and
        52 were both typed; now the second is derived from the first."""
        for chapter in range(H.CHAPTER_COUNT):
            with self.subTest(chapter=chapter):
                self.assertEqual(H.casts_at_unready(chapter),
                                 H.casts_at_ready(chapter) * 2)
        for region in REGIONS:
            rows = H.curve(region)
            with self.subTest(region):
                self.assertEqual(rows[0]["casts"], rows[-1]["casts"] * 2)

    def test_the_ramp_rises_and_never_flattens(self):
        ready = [H.casts_at_ready(c) for c in range(H.CHAPTER_COUNT)]
        strikes = [H.strike_at_unready(c) for c in range(H.CHAPTER_COUNT)]
        for a, b in zip(ready, ready[1:]):
            self.assertGreater(b, a, "a chapter bought no length")
        for a, b in zip(strikes, strikes[1:]):
            self.assertGreater(b, a, "a chapter bought no weight")
        self.assertEqual(strikes[0], H.STRIKE_AT_UNREADY_FLOOR)
        self.assertEqual(strikes[-1], H.STRIKE_AT_UNREADY)

    def test_the_two_legacy_constants_still_describe_the_anchor_rung(self):
        """CASTS_AT_READY and CASTS_AT_UNREADY kept their names through a change
        that made them vary. They now describe chapter V, and if they ever stop
        describing it, everything that still imports them is quietly wrong."""
        self.assertEqual(H.casts_at_ready(H.CHAPTER_ANCHOR), H.CASTS_AT_READY)
        self.assertEqual(H.casts_at_unready(H.CHAPTER_ANCHOR),
                         H.CASTS_AT_UNREADY)

    def test_the_first_apex_is_a_lesson_and_the_last_is_an_event(self):
        """Section B. The earliest apex has to be short enough to lose, read,
        fix and come back to; the deepest has to be long enough to remember."""
        first = H.pace_for("python_village")
        last = H.pace_for("null_kings_castle")
        self.assertEqual(first["stance"], H.TEACHES)
        self.assertEqual(last["stance"], H.TESTS)
        # Inside the ordinary elite band this game already uses: 8 to 20 casts.
        self.assertLessEqual(first["casts_ready"], 20)
        self.assertGreaterEqual(first["casts_ready"], 8)
        # And it hits softly enough that the tell can fire twice.
        self.assertLess(first["strike_unready"], last["strike_unready"])
        self.assertGreater(last["casts_ready"], first["casts_ready"] * 2.5)

    def test_the_pool_cap_never_binds(self):
        """A capped pool ends the fight before target_casts is reached, which
        puts the client's bar and the engine's tally on different arithmetic
        about the same creature."""
        verdict = H._pool_cap_is_never_reached()
        self.assertTrue(verdict["holds"],
                        f"largest legitimate pool {verdict['pool']} reached "
                        f"HP_CAP {verdict['cap']}")

    def test_the_ramp_is_shipped_to_the_client_exactly_once(self):
        payload = H.client_payload()
        self.assertEqual(len(payload["ramp"]), H.CHAPTER_COUNT)
        self.assertEqual(payload["chapter_for_region"],
                         {r["id"]: H.chapter_for_region(r["id"])
                          for r in world.REGIONS})
        for row in payload["ramp"]:
            self.assertEqual(row["casts_unready"], row["casts_ready"] * 2)

    def test_a_full_playthrough_is_reported_rather_than_guessed(self):
        cost = H.playthrough_cost()
        self.assertEqual(cost["apexes"], len(H.APEXES))
        self.assertEqual(cost["unprepared_casts"], cost["prepared_casts"] * 2)
        self.assertEqual(
            cost["prepared_casts"],
            sum(H.casts_at_ready(H.chapter_for_region(a.region))
                for a in H.APEXES))


class TestNeverUnwinnable(unittest.TestCase):

    def test_the_mismatch_is_priced_once_and_not_twice(self):
        """The fight that a hit-point-first design gets wrong.

        An underprepared player has a LONGER fight and does LESS damage per
        cast. If the pool were authored in hit points those two would multiply
        and a fifty-two cast fight would become two hundred. The pool is derived
        from the player's own damage instead, so the worst loadout in the game
        must come out near THIS CHAPTER'S unprepared length rather than near
        four times it.
        """
        for region in REGIONS:
            apex = H.apex_for(region)
            ceiling = H.casts_at_unready(H.chapter_for_region(region))
            worst = fight(region, the_worst_loadout(apex))
            best = fight(region, did_the_work(apex))
            with self.subTest(region):
                self.assertLessEqual(
                    worst["real_casts"], ceiling + 4,
                    "the wrong element bought a second penalty")
                self.assertLess(
                    worst["real_casts"] / best["real_casts"],
                    E.MAX_FIGHT_STRETCH,
                    "a mismatched apex fight exceeded the four-times bound "
                    "elements.py promises")

    def test_every_landed_cast_moves_the_bar(self):
        """G8. Worst attacker element, worst rung, against every apex."""
        for region in REGIONS:
            apex = H.apex_for(region)
            defender = apex_defender(apex)
            for element in list(E.ELEMENTS) + [E.NEUTRAL]:
                hit = E.resolve_damage(1, element, defender, roll=0.0,
                                       can_inflict=False)
                self.assertGreaterEqual(hit.damage, E.MIN_DAMAGE,
                                        f"{region}/{element} landed for zero")

    def test_a_player_with_the_wrong_element_and_no_potions_still_finishes(self):
        """Requirement 3, driven rather than reasoned about: cast until it dies
        and count. No drinking, no swapping, no running."""
        for region in REGIONS:
            apex = H.apex_for(region)
            loadout = the_worst_loadout(apex)
            scale = H.scale_for(region, loadout)
            defender = apex_defender(apex)
            base = int(round(H.CAST_DAMAGE_REFERENCE
                             * H.RUNG_DAMAGE_SCALE[0]))
            pool, casts = scale.hp, 0
            while pool > 0 and casts < 10000:
                pool -= E.resolve_damage(base, loadout.weapon_element, defender,
                                         roll=0.0, can_inflict=False).damage
                casts += 1
            ceiling = H.casts_at_unready(H.chapter_for_region(region))
            with self.subTest(region):
                self.assertLess(casts, 10000, "the fight did not terminate")
                # Was a flat eighty, which was the old CASTS_AT_UNREADY plus
                # half again. The bound that matters is "this fight is not
                # longer than the one the chapter authored for a player with
                # nothing", and that number now depends on the chapter.
                self.assertLessEqual(casts, ceiling + 6,
                                     f"{casts} casts is a wall with a health "
                                     f"bar, not a fight")

    def test_being_beaten_up_is_never_a_loss_state(self):
        """The apex only swings when the Python was wrong, and the engine
        routes an empty bar to a training camp rather than to a defeat. The
        arithmetic here pins the size of the blow so that a tuning pass cannot
        quietly turn the hunter into the first thing in this game that can end
        a run."""
        apex = H.apex_for("null_kings_castle")
        bare = the_worst_loadout(apex)
        scale = H.scale_for("null_kings_castle", bare)
        swing = E.resolve_damage(
            max(0, int(round(ENEMY_BASE_DAMAGE * scale.strike_multiplier))),
            apex.element, player_defender(bare), roll=1.0, can_inflict=False)
        self.assertLessEqual(swing.damage, config.STAMINA_MAX // 4,
                             "one blow now takes a quarter of the bar")
        self.assertLessEqual(H.STRIKE_AT_UNREADY, 1.55)


# ---------------------------------------------------------------------------
# 4. The roster, and the seam to the art
# ---------------------------------------------------------------------------

class TestTheRosterAndTheArtSeam(unittest.TestCase):

    def test_self_check_is_green(self):
        report = H.self_check()
        self.assertTrue(report["ok"], json.dumps(
            {k: v for k, v in report.items()
             if k in ("regions_without_an_apex", "exam_sums",
                      "sprite_fallbacks_unresolved", "guarantees",
                      "prose_matches_the_data", "damage_anchor",
                      "pet_tier_copy")}, indent=1, default=str))

    def test_one_apex_per_region_with_a_distinct_face(self):
        self.assertEqual(len(H.APEXES), len(world.REGIONS))
        self.assertEqual(len({a.region for a in H.APEXES}), len(H.APEXES))
        self.assertEqual(len({a.sprite for a in H.APEXES}), len(H.APEXES),
                         "two apexes propose the same new sprite key")
        self.assertEqual(len({a.trophy for a in H.APEXES}), len(H.APEXES))
        for apex in H.APEXES:
            self.assertIn(apex.trophy, H.TROPHIES)
            self.assertIn(apex.sprite_fallback, H._BOSS_ARCHETYPES,
                          f"{apex.id} falls back to a key bosses.js will "
                          f"silently replace with a titan")

    def test_the_element_is_the_grounds_element_and_never_a_typed_one(self):
        for apex in H.APEXES:
            self.assertEqual(apex.elements,
                             E.affinities_for(apex.region, difficulty="BOSS",
                                              is_boss=True))

    def test_the_brief_named_three_and_all_three_are_here(self):
        self.assertEqual(H.APEX_BY_REGION["stack_queue_mines"].element, E.FIRE)
        self.assertEqual(H.APEX_BY_REGION["twin_pointer_pass"].element, E.COLD)
        self.assertEqual(H.APEX_BY_REGION["null_kings_castle"].element, E.VOID)
        self.assertIn("phoenix",
                      H.APEX_BY_REGION["stack_queue_mines"].id.lower())

    def test_every_exam_sheet_sums_to_a_hundred(self):
        for apex in H.APEXES:
            self.assertEqual(sum(apex.exam.values()), 100, apex.id)
            self.assertEqual(set(apex.exam), set(H.EXAM_COMPONENTS), apex.id)

    def test_the_client_payload_serialises_without_an_object_in_it(self):
        json.dumps(H.client_payload())

    def test_a_hunt_with_no_position_does_not_claim_one(self):
        """The one seam this module says is the whole contract.

        `apex.js` treats a finite `x`/`y` on a hunt row as authority and stops
        placing the creature itself. JavaScript's `Number(null)` is 0 and
        `Number(undefined)` is NaN, so a field this module cannot fill has to be
        ABSENT from the row rather than null or zero — anything else pins the
        apex to the map's top-left corner for the whole hunt and looks, from
        the client's side, exactly like an engine that meant it.
        """
        hunt = H.new_hunt("twin_pointer_pass")
        hunt.state = "TRACKING"
        hunt.distance = 300.0
        row = hunt.to_dict()
        self.assertNotIn("x", row)
        self.assertNotIn("y", row)
        self.assertEqual(row["distance"], 300.0)
        hunt.x, hunt.y = 336.0, 48.0
        placed = hunt.to_dict()
        self.assertEqual((placed["x"], placed["y"]), (336.0, 48.0))
        json.dumps(row)
        json.dumps(placed)

    def test_a_hunt_survives_a_round_trip_through_its_own_dict(self):
        hunt = H.new_hunt("stack_queue_mines")
        hunt, _elapsed = drive(
            hunt, H.Moment(moving=True, health_fraction=1.0, free_tiles=999,
                           clears=99, seed=9), 5.0, stop=())
        again = H.Hunt(**dict(hunt.to_dict()))
        self.assertEqual(again.state, hunt.state)
        self.assertEqual(again.region, hunt.region)


# ---------------------------------------------------------------------------
# 5. The pixels, measured in the only place they exist
# ---------------------------------------------------------------------------

NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is not installed; the art floor is measured "
                           "by scripts/verify/*.mjs")
class TestTheArtFloorAndTheCostOfNothingHunting(unittest.TestCase):
    """Shelling out is deliberate. These are claims about a rendered raster and
    about canvas allocation counts, and neither is visible from Python. The
    harnesses already exist and print JSON; this pins their verdicts so the
    suite fails when the art floor does."""

    def verify(self, script):
        result = subprocess.run([NODE, f"scripts/verify/{script}"],
                                cwd=REPO, capture_output=True, text=True,
                                timeout=900)
        self.assertEqual(result.returncode, 0,
                         (result.stderr or result.stdout)[-2000:])
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"{script} did not print JSON:\n{result.stdout[-2000:]}")

    def test_every_monster_is_distinct_at_sixteen_pixels_and_inside_budget(self):
        report = self.verify("monsters.mjs")
        self.assertEqual(report["failures"], 0, report["detail"])
        self.assertLessEqual(report["colour"]["worst"], 15,
                             "a rendered frame went over the palette budget")
        self.assertEqual(report["colour"]["over"], [])
        self.assertEqual(report["determinism"]["differingAfterRebuild"], 0)
        self.assertEqual(report["cache"]["canvasesAllocated"], 0)
        self.assertEqual(report["sprites"]["fellThrough"], [])
        self.assertEqual(report["bestiary"]["broken"], [])
        self.assertEqual(report["fallback"]["threw"], [],
                         "an unknown sprite key threw instead of falling back")
        self.assertGreaterEqual(report["apexScale"]["smallestMargin"], 1.2,
                                "an apex stopped reading as bigger than the "
                                "mobs it hunts beside")

    HOSTILE_KEYS = """
import { installRaster } from './scripts/verify/raster.mjs';
installRaster();
const MA = await import('./web/js/monsterart.js');
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const nasty = ['constructor', 'valueOf', 'toString', 'hasOwnProperty',
               '__proto__', 'isPrototypeOf', 'propertyIsEnumerable',
               '', 'zzz_not_a_key', '../../etc/passwd', null, undefined, 0, 42,
               true, {}, []];
const bad = [];
for (const k of nasty) {
  let key, apexKey;
  try {
    key = MA.monsterKeyFor(k);
    apexKey = MA.apexKeyFor(k);
    MA.monsterFrame(k, 1, { region: 'null_kings_castle' });
    MA.monsterSilhouette(k, 0);
    MA.monsterMotion(k);
    MA.rosterFor(k);
    MA.elementOf(k);
  } catch (e) { bad.push([String(k), 'threw: ' + e.message]); continue; }
  if (typeof key !== 'string' || !own(MA.MONSTERS, key))
    bad.push([String(k), 'monsterKeyFor -> ' + typeof key + ' ' + String(key)]);
  if (typeof apexKey !== 'string' || !own(MA.MONSTERS, apexKey))
    bad.push([String(k), 'apexKeyFor -> ' + typeof apexKey]);
  if (MA.monsterIsAuthored(k) && !['margin_walker'].includes(key))
    bad.push([String(k), 'claimed to be authored']);
}
console.log(JSON.stringify(bad));
"""

    def test_a_hostile_key_falls_back_and_never_walks_the_prototype(self):
        """An unknown key must reach the unmarked body, not Object.prototype.

        Every table here is an object literal, so `TABLE['constructor']` is a
        function rather than a miss, and `strip()` cannot disarm a key that is
        already lowercase and unseparated. Measured before the guard existed:
        `monsterKeyFor('constructor')` returned a FUNCTION and
        `monsterIsAuthored('constructor')` returned true. Nothing threw, which
        is the bad version — the fallback that exists to make unknown names
        harmless simply did not run.
        """
        result = subprocess.run([NODE, "--input-type=module", "-e",
                                 self.HOSTILE_KEYS],
                                cwd=REPO, capture_output=True, text=True,
                                timeout=300)
        self.assertEqual(result.returncode, 0,
                         (result.stderr or result.stdout)[-2000:])
        self.assertEqual(json.loads(result.stdout), [],
                         "a hostile key escaped the fallback")

    def test_the_apex_sprite_seam_resolves_and_draws(self):
        report = self.verify("apex.mjs")
        self.assertEqual(report["failures"], [])
        self.assertTrue(report["ok"])
        self.assertEqual(report["fallbacksUnresolved"], 0)
        self.assertEqual(report["overPaletteBudget"], 0)
        self.assertLessEqual(report["maxColoursSeen"], 15)
        self.assertEqual(report["undeclaredCollisions"], 0)
        self.assertEqual(report["identicalSilhouettePairs"], 0)

    def test_with_nothing_hunting_the_frame_is_the_frame_it_always_was(self):
        report = self.verify("apexhunt.mjs")
        self.assertEqual(report["failures"], 0, report["detail"])
        self.assertTrue(report["nothingHuntingAllIdentical"],
                        "a world with nothing hunting stopped rendering "
                        "identically to one built without this feature")
        frames = {row["frame"] for row in report["nothingHunting"].values()}
        self.assertEqual(len(frames), 1, report["nothingHunting"])
        steady = report["steadyState"]
        self.assertEqual(steady["canvasesAddedWhenNothingIsHunting"], 0)
        self.assertEqual(steady["canvasesAddedByAnActiveHunt"], 0)
        self.assertEqual(steady["perFrameAllocationsInTheOverlay"], 0)

    def test_no_payload_can_make_it_outrun_you_and_the_door_stays_visible(self):
        report = self.verify("apexhunt.mjs")
        speed = report["cannotOutrunYou"]
        self.assertTrue(speed["everyStateAtOrUnderTheCap"])
        self.assertLessEqual(speed["speedActuallyUsedWhileClosing"],
                             H.APEX_MAX_SPEED)
        self.assertLess(speed["apexMaxSpeed"], speed["playerWalkSpeed"])
        door = report["dreadNeverHidesTheDoor"]
        self.assertEqual(door["goldPixelPaintedOver"], 0,
                         "the telegraph covered the way out")
        self.assertLessEqual(door["peakVignettePainted"], door["cap"])
        self.assertEqual(report["neverInTheWay"]["framesInsideTheExitKeepOut"],
                         0)


if __name__ == "__main__":       # pragma: no cover
    unittest.main(verbosity=2)
