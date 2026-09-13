"""Village life is data, so these tests are about the data being TRUE.

Four claims the brief asks to be proved, and each has a test named after it:
every biome has an activity, no village is empty, the same seed gives the same
village twice, and the payload round-trips through json.dumps.

Deliberately NOT a `base.GameTest`. That class builds the corpus in
setUpClass and a Game costs about thirty seconds; `villagelife` is a pure
function of world.REGIONS and quests.NPCS and needs neither. `base` is still
imported, because importing it is what puts the repo root on sys.path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import base  # noqa: F401  -- imported for the sys.path insertion

from gauntlet import quests, villagelife as vl, world

REPO = Path(__file__).resolve().parent.parent
SEEDS = (0, 1, 7, 42, 99, 1234, 65535, 987654321)


class ActivityTable(unittest.TestCase):

    def test_every_biome_has_an_activity(self):
        """CLAIM 1. No region can reach this table and find nothing."""
        for region in world.REGIONS:
            biome = region["biome"]
            self.assertIn(biome, vl.ACTIVITIES,
                          "%s has biome %r and no activity row"
                          % (region["id"], biome))
            row = vl.ACTIVITIES[biome]
            self.assertTrue(row["label"],
                            "%s has an activity with no label" % biome)
            self.assertIn(row["motion"], vl.MOTIONS)

    def test_every_settled_region_actually_does_something(self):
        """The table being total is not the same as the village being alive."""
        for region in world.REGIONS:
            rid = region["id"]
            if not vl.has_village(rid):
                continue
            act = vl.village(rid, 7)["activity"]
            self.assertNotEqual(act["motion"], "none",
                                "%s is settled and inert" % rid)
            self.assertTrue(act["actors"], "%s has an activity nobody is in" % rid)

    def test_the_castle_is_the_only_place_with_nobody_in_it(self):
        """The absence is the design, so it is asserted rather than tolerated.

        docs/12 section 5.3: the Null King's Castle "is the one place that gets
        no settlement, and the absence is the point". A second unsettled region
        appearing here means somebody changed a biome without reading that.
        """
        empty = [r["id"] for r in world.REGIONS if not vl.has_village(r["id"])]
        self.assertEqual(empty, ["null_kings_castle"])
        pay = vl.village("null_kings_castle", 7)
        self.assertFalse(pay["settled"])
        self.assertEqual(pay["villagers"], [])
        self.assertEqual(pay["activity"]["motion"], "none")
        self.assertEqual(pay["activity"]["particles"], [])

    def test_only_the_ten_commissioned_sprites_are_asked_for(self):
        """An eleventh particle sprite is art nobody was asked to draw."""
        asked = {row["kind"] for row in vl.ACTIVITIES.values() if row["kind"]}
        self.assertEqual(asked, set(vl.ACTIVITY_SPRITES))
        self.assertEqual(len(vl.ACTIVITY_SPRITES), 10)

    def test_no_sprite_outgrows_the_art_budget(self):
        for biome, row in vl.ACTIVITIES.items():
            if not row["kind"]:
                self.assertIsNone(row["size"], biome)
                continue
            w, h = row["size"]
            self.assertLessEqual(w, vl.SPRITE_MAX_W, biome)
            self.assertLessEqual(h, vl.SPRITE_MAX_H, biome)

    def test_particle_cap_is_never_exceeded(self):
        """Section 7.5 budgets twelve particles per village. The Mines spend
        exactly twelve; nobody may spend thirteen."""
        for biome, row in vl.ACTIVITIES.items():
            self.assertLessEqual(row["particles"], vl.PARTICLE_CAP, biome)
        peak = max(row["particles"] for row in vl.ACTIVITIES.values())
        self.assertEqual(peak, vl.PARTICLE_CAP)
        for seed in SEEDS:
            for pay in vl.region_payload(seed=seed):
                self.assertLessEqual(pay["activity"]["particle_count"],
                                     vl.PARTICLE_CAP, pay["region"])

    def test_the_player_named_four_activities_and_they_are_where_they_belong(self):
        """The brief's own words, checked against the map.

        "children playing or chasing butterflys", "a snowball fight in snow
        land", "playing with fireworks in volcano land", "chasing ants in
        rainforest". If a later pass re-biomes a region, this fails by name.
        """
        want = {
            "python_village": "butterfly",
            "fields_of_syntax": "butterfly",
            "twin_pointer_pass": "snowball",
            "stack_queue_mines": "firework_spark",
            "recursive_forest": "ant",
        }
        for rid, kind in want.items():
            self.assertEqual(vl.activity_for(rid)["kind"], kind, rid)

    def test_activities_are_copies_not_the_table_itself(self):
        """ACTIVITIES is module state. A caller that edits a returned params
        dict must not be editing every other village in the process."""
        a = vl.activity_for("python_village")
        a["params"]["period_ms"] = -1
        a["size"][0] = 999
        b = vl.activity_for("python_village")
        self.assertNotEqual(b["params"]["period_ms"], -1)
        self.assertNotEqual(b["size"][0], 999)


class Headcount(unittest.TestCase):

    def test_the_doc_numbers(self):
        """Section 7.1 states two of these outright; both are checked."""
        self.assertEqual(vl.headcount("python_village"),
                         {"buildings": 5, "villagers": 10, "children": 3,
                          "adults": 7})
        self.assertEqual(vl.headcount("array_caverns"),
                         {"buildings": 2, "villagers": 4, "children": 1,
                          "adults": 3})

    def test_the_building_total_matches_the_design(self):
        """docs/12 section 5.3 totals 41 buildings, up from 20."""
        self.assertEqual(sum(vl.BUILDING_COUNT.values()), 41)
        self.assertEqual(vl.BUILDING_COUNT["null_kings_castle"], 0)

    def test_a_caller_may_override_the_building_count(self):
        """A map that could not find dry ground for a building must not grow
        villagers standing in a lake."""
        self.assertEqual(vl.headcount("python_village", buildings=1)["villagers"], 2)
        self.assertEqual(len(vl.villagers("python_village", 3, buildings=1)), 2)
        self.assertEqual(vl.villagers("python_village", 3, buildings=0), [])

    def test_the_cap_holds(self):
        self.assertEqual(vl.headcount("python_village", buildings=40)["villagers"],
                         12)


class NobodyIsMissing(unittest.TestCase):

    def settled(self):
        return [r["id"] for r in world.REGIONS if vl.has_village(r["id"])]

    def test_no_village_is_empty(self):
        """CLAIM 2. Sixteen settlements, and every one of them has people, at
        least one child, and at least one person worth talking to."""
        self.assertEqual(len(self.settled()), 16)
        for seed in SEEDS:
            for rid in self.settled():
                pay = vl.village(rid, seed)
                self.assertGreaterEqual(pay["count"], 4, rid)
                self.assertGreaterEqual(pay["children"], 1, rid)
                self.assertGreaterEqual(pay["adults"], 1, rid)
                self.assertGreaterEqual(pay["named"], 1, rid)
                self.assertEqual(pay["count"],
                                 pay["children"] + pay["adults"], rid)

    def test_both_body_types_stand_in_every_village(self):
        """The brief asks for "male and female sprites interacting like a
        village", so a single-sex village is a failed requirement, not a
        cosmetic wobble."""
        for seed in SEEDS:
            for rid in self.settled():
                bodies = {v["body"] for v in vl.villagers(rid, seed)}
                self.assertEqual(bodies, set(vl.BODY_TYPES),
                                 "%s at seed %s: %s" % (rid, seed, bodies))

    def test_the_split_is_even(self):
        for seed in SEEDS:
            for rid in self.settled():
                folk = vl.villagers(rid, seed)
                a = sum(1 for v in folk if v["body"] == "a")
                self.assertEqual(a * 2, len(folk), rid)

    def test_the_named_cast_is_the_one_that_already_existed(self):
        """No new people. Every named villager is a row of quests.NPCS,
        unedited — name, sprite and line all match their source."""
        seen = set()
        for rid in self.settled():
            for v in vl.villagers(rid, 5):
                if not v["npc"]:
                    continue
                self.assertIn(v["npc"], quests.NPCS)
                npc = quests.NPCS[v["npc"]]
                self.assertEqual(npc["region"], rid)
                self.assertEqual(v["name"], npc["name"])
                self.assertEqual(v["sprite"], npc["sprite"])
                self.assertEqual(v["line"], npc["line"])
                self.assertTrue(v["speaks"])
                seen.add(v["npc"])
        # Everyone except the Steward, who keeps an empty castle.
        self.assertEqual(seen, set(quests.NPCS) - {"steward"})
        self.assertEqual(len(seen), 33)

    def test_the_crowd_is_silent(self):
        """Section 7.2: the unnamed "never open a dialogue box". A village of
        twelve people who all talk is a village nobody walks through twice."""
        for rid in self.settled():
            for v in vl.villagers(rid, 5):
                if v["npc"]:
                    continue
                self.assertIsNone(v["line"], v["id"])
                self.assertIsNone(v["name"], v["id"])
                self.assertFalse(v["speaks"], v["id"])

    def test_pel_is_counted_as_a_child_not_as_a_bonus_one(self):
        """Pel is the only written child in the game. Python Village's quota is
        three, and he is one of the three rather than a fourth."""
        pay = vl.village("python_village", 11)
        self.assertEqual(pay["children"], 3)
        pel = [v for v in pay["villagers"] if v["npc"] == "pel"]
        self.assertEqual(len(pel), 1)
        self.assertTrue(pel[0]["child"])


class WhereTheyStand(unittest.TestCase):

    def test_waypoints_are_four_distinct_legal_cells(self):
        for seed in (0, 7, 1234):
            for pay in vl.region_payload(seed=seed):
                for v in pay["villagers"]:
                    cells = [(w["dx"], w["dy"]) for w in v["waypoints"]]
                    self.assertEqual(len(cells), vl.WAYPOINTS, v["id"])
                    self.assertEqual(len(set(cells)), vl.WAYPOINTS, v["id"])
                    for cell in cells:
                        self.assertIn(cell, vl.HOME_CELLS, v["id"])

    def test_nobody_stands_in_a_wall_or_in_a_doorway(self):
        """The 5x5 box has a 2x2 building in the middle of it and the door is
        one of those four cells. A body parked in a doorway reads as a
        collision bug in a game where villagers are deliberately not solid."""
        self.assertEqual(len(vl.HOME_CELLS), 21)
        for cell in vl.FOOTPRINT:
            self.assertNotIn(cell, vl.HOME_CELLS)
        self.assertIn(vl.DOOR_CELL, vl.FOOTPRINT)
        for seed in (0, 7, 1234):
            for pay in vl.region_payload(seed=seed):
                for v in pay["villagers"]:
                    for w in v["waypoints"]:
                        self.assertNotIn((w["dx"], w["dy"]), vl.FOOTPRINT)

    def test_no_leg_is_zero_length(self):
        """A villager who walks nowhere reads as a stuck sprite."""
        for seed in (0, 7, 1234):
            for pay in vl.region_payload(seed=seed):
                for v in pay["villagers"]:
                    w = v["waypoints"]
                    for i in range(len(w)):
                        a, b = w[i], w[(i + 1) % len(w)]
                        self.assertNotEqual((a["dx"], a["dy"]),
                                            (b["dx"], b["dy"]), v["id"])

    def test_facings_and_emotes_are_words_the_renderer_knows(self):
        for seed in (0, 42):
            for pay in vl.region_payload(seed=seed):
                for v in pay["villagers"]:
                    self.assertIn(v["facing"], vl.FACINGS, v["id"])
                    for w in v["waypoints"]:
                        self.assertIn(w["face"], vl.FACINGS, v["id"])
                        self.assertIn(w["emote"], vl.EMOTE_KEYS, v["id"])
                        self.assertLessEqual(vl.PAUSE_MIN, w["pause_s"])
                        self.assertLessEqual(w["pause_s"], vl.PAUSE_MAX)

    def test_every_villager_is_attached_to_a_real_building(self):
        for seed in (0, 42):
            for pay in vl.region_payload(seed=seed):
                for v in pay["villagers"]:
                    self.assertIn(v["building"], range(pay["buildings"]),
                                  v["id"])
                if pay["settled"]:
                    plaza = pay["activity"]["plaza"]
                    self.assertIn(plaza["building"], range(pay["buildings"]))

    def test_home_is_the_first_waypoint(self):
        for pay in vl.region_payload(seed=3):
            for v in pay["villagers"]:
                self.assertEqual(v["home"],
                                 {"dx": v["waypoints"][0]["dx"],
                                  "dy": v["waypoints"][0]["dy"]})


class TheActivityActors(unittest.TestCase):

    def test_actors_are_real_people_in_this_village(self):
        for seed in SEEDS:
            for pay in vl.region_payload(seed=seed):
                ids = {v["id"] for v in pay["villagers"]}
                for aid in pay["activity"]["actors"]:
                    self.assertIn(aid, ids, pay["region"])

    def test_a_fight_and_a_race_have_two_people_in_them(self):
        """Twin Pointer Pass is a two-building waystation with exactly one
        child in it, and section 7.4 puts a snowball FIGHT there. One child
        throwing a snowball at nobody is not a snowball fight."""
        for seed in SEEDS:
            for rid in ("twin_pointer_pass", "sliding_window_marsh",
                        "matrix_citadel", "coding_coliseum",
                        "debugging_dungeon"):
                act = vl.village(rid, seed)["activity"]
                self.assertGreaterEqual(len(act["actors"]), 2,
                                        "%s at seed %s" % (rid, seed))

    def test_every_activity_reaches_its_minimum(self):
        for seed in SEEDS:
            for region in world.REGIONS:
                rid = region["id"]
                spec = vl.ACTIVITIES[region["biome"]]
                got = len(vl.village(rid, seed)["activity"]["actors"])
                self.assertGreaterEqual(
                    got, min(spec["actors"], spec["min_actors"]), rid)

    def test_the_quench_is_done_by_adults(self):
        """Garrick is a forge apprentice, two days into reading one crack. He
        is not a child, and neither is anybody else at that barrel."""
        pay = vl.village("debugging_dungeon", 9)
        folk = {v["id"]: v for v in pay["villagers"]}
        self.assertEqual(pay["activity"]["actor_kind"], "adult")
        for aid in pay["activity"]["actors"]:
            self.assertFalse(folk[aid]["child"], aid)

    def test_actors_have_a_station_and_walkers_do_not(self):
        for seed in (0, 7, 1234):
            for pay in vl.region_payload(seed=seed):
                actors = set(pay["activity"]["actors"])
                for v in pay["villagers"]:
                    if v["id"] in actors:
                        self.assertEqual(v["duty"], "activity", v["id"])
                        self.assertIsNotNone(v["station"], v["id"])
                        self.assertIn(v["station"]["face"], vl.FACINGS)
                        # A station is measured from the plaza, not from the
                        # villager's own building. Both origins produce numbers
                        # that look identical, so the frame is stated.
                        self.assertEqual(v["station"]["anchor"], "plaza",
                                         v["id"])
                        # Their route stays on the record: reduced motion hides
                        # the activity, and they need somewhere to stand.
                        self.assertEqual(len(v["waypoints"]), vl.WAYPOINTS)
                    else:
                        self.assertEqual(v["duty"], "walk", v["id"])
                        self.assertIsNone(v["station"], v["id"])

    def test_unnamed_people_are_taken_for_the_activity_first(self):
        """The thirty-four written people are the ones a player walks up to. A
        village where all of them are frozen at a snowball fight is a village
        with nobody in it."""
        for seed in SEEDS:
            for pay in vl.region_payload(seed=seed):
                if not pay["settled"]:
                    continue
                folk = {v["id"]: v for v in pay["villagers"]}
                actors = [folk[a] for a in pay["activity"]["actors"]]
                named_used = [a for a in actors if a["npc"]]
                if not named_used:
                    continue
                # A named person is only ever pulled in when the preferred pool
                # of unnamed people of that kind has run out.
                kind = pay["activity"]["actor_kind"]
                spare = [v for v in pay["villagers"]
                         if not v["npc"] and v["duty"] == "walk"
                         and (v["child"] if kind == "child" else not v["child"])]
                self.assertEqual(spare, [], pay["region"])

    def test_particles_carry_their_own_phase(self):
        """The renderer gets no RNG: if a particle had to invent its phase, two
        machines would animate the same village differently."""
        for pay in vl.region_payload(seed=13):
            act = pay["activity"]
            self.assertEqual(len(act["particles"]), act["particle_count"])
            for p in act["particles"]:
                self.assertIn("phase", p)
                self.assertGreaterEqual(p["phase"], 0.0)
                self.assertLess(p["phase"], 1.0)
                self.assertIsInstance(p["lane"], int)
            if act["motion"] == "burst":
                self.assertTrue(all("angle_deg" in p for p in act["particles"]))
            if act["motion"] == "spline":
                self.assertTrue(all("t" in p for p in act["particles"]))
                self.assertGreaterEqual(len(act["params"]["points"]), 4)


class SameSeedSameVillage(unittest.TestCase):

    def test_the_same_seed_gives_the_same_village_twice(self):
        """CLAIM 3."""
        for seed in SEEDS:
            self.assertEqual(vl.region_payload(seed=seed),
                             vl.region_payload(seed=seed))

    def test_a_different_seed_gives_a_different_village(self):
        """Determinism that returns one village for every seed is a constant,
        not a generator."""
        sigs = {json.dumps(vl.village("python_village", s), sort_keys=True)
                for s in range(200)}
        self.assertEqual(len(sigs), 200)

    def test_a_seed_may_be_a_string(self):
        """Save codes are text. Both spellings of one seed agree."""
        self.assertEqual(vl.village("python_village", "ORCHID-7"),
                         vl.village("python_village", "ORCHID-7"))
        self.assertNotEqual(vl.village("python_village", "ORCHID-7"),
                            vl.village("python_village", "ORCHID-8"))

    def test_determinism_survives_a_new_interpreter(self):
        """The load-bearing claim, and the one an in-process test cannot make.

        Python salts `hash()` per interpreter, so a village built with it would
        be a different village after a relaunch. This runs the generator in two
        fresh interpreters under different PYTHONHASHSEED values and compares
        the bytes.
        """
        script = ("import json, sys; sys.path.insert(0, %r);"
                  " from gauntlet import villagelife as vl;"
                  " print(json.dumps(vl.region_payload(seed=99),"
                  " sort_keys=True))" % str(REPO))
        out = []
        for hashseed in ("0", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=hashseed)
            out.append(subprocess.run([sys.executable, "-c", script],
                                      capture_output=True, text=True,
                                      env=env, cwd=str(REPO),
                                      check=True).stdout)
        self.assertEqual(out[0], out[1])
        self.assertEqual(json.loads(out[0]), vl.region_payload(seed=99))

    def test_the_module_reads_no_clock_and_rolls_no_dice(self):
        """Grepped rather than trusted. `random`, a wall clock or a bare
        `hash()` would each break the claim above in a way no single run
        would necessarily show."""
        src = (REPO / "gauntlet" / "villagelife.py").read_text()
        for banned in ("import random", "import time", "import datetime",
                       "from random", "time.time", "datetime.", "uuid"):
            self.assertNotIn(banned, src, banned)
        # `hash(` as a call, not as part of `_h32` or the word "hash".
        for line in src.splitlines():
            code = line.split("#")[0]
            self.assertNotIn(" hash(", code)
            self.assertNotIn("=hash(", code)

    def test_payloads_do_not_share_mutable_state(self):
        a = vl.village("python_village", 4)
        a["villagers"][0]["waypoints"][0]["dx"] = 99
        a["activity"]["params"]["period_ms"] = -5
        b = vl.village("python_village", 4)
        self.assertNotEqual(b["villagers"][0]["waypoints"][0]["dx"], 99)
        self.assertNotEqual(b["activity"]["params"]["period_ms"], -5)


class ItGoesOnTheWire(unittest.TestCase):

    def test_the_payload_round_trips_through_json(self):
        """CLAIM 4. Not "it serialises" — that it comes back identical."""
        for seed in SEEDS:
            payload = vl.region_payload(seed=seed)
            text = json.dumps(payload)
            self.assertEqual(json.loads(text), payload)

    def test_every_value_is_a_json_primitive(self):
        """A tuple survives json.dumps by becoming a list, so equality after a
        round trip would catch it — but only on the way back. This catches it
        on the way out, where the error names the field."""
        def walk(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    self.assertIsInstance(k, str, path)
                    walk(v, path + "." + k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, "%s[%d]" % (path, i))
            else:
                self.assertIsInstance(node, (str, int, float, bool, type(None)),
                                      "%s is %s" % (path, type(node)))
                self.assertNotIsInstance(node, tuple, path)
        for pay in vl.region_payload(seed=77):
            walk(pay, pay["region"])

    def test_the_renderer_is_told_what_an_offset_means(self):
        """The payload has to be readable without this file open next to it."""
        pay = vl.village("python_village", 1)
        anchor = pay["anchor"]
        self.assertEqual(anchor["tile"], vl.TILE)
        self.assertIn("dx", anchor["formula"])
        self.assertIn("building", anchor["building_is"])
        self.assertIn("villager.station", anchor["frames"]["plaza"])
        self.assertIn("activity.plaza", anchor["frames"]["building"])
        self.assertEqual(pay["speed_px_s"], vl.VILLAGER_SPEED)
        self.assertEqual(pay["tick_hz"], vl.TICK_HZ)
        self.assertEqual(pay["particle_cap"], vl.PARTICLE_CAP)
        self.assertEqual(pay["reduced_motion"]["activity"], "hide")
        self.assertEqual(pay["reduced_motion"]["walk"], "freeze")

    def test_region_payload_covers_the_whole_world(self):
        payload = vl.region_payload(seed=2)
        self.assertEqual([p["region"] for p in payload],
                         [r["id"] for r in world.REGIONS])
        self.assertEqual(len(payload), 17)


class SelfCheck(unittest.TestCase):

    def test_self_check_passes_on_a_spread_of_seeds(self):
        for seed in SEEDS:
            report = vl.self_check(seed)
            self.assertTrue(report["ok"],
                            "seed %s: %s" % (seed, report["problems"]))

    def test_self_check_reports_the_shape_of_the_world(self):
        report = vl.self_check()
        self.assertEqual(report["biomes"], 17)
        self.assertEqual(report["activities"], 17)
        self.assertEqual(report["settlements"], 16)
        self.assertEqual(report["buildings"], 41)
        self.assertEqual(report["population"], 82)
        self.assertEqual(report["sprites_unused"], [])

    def test_self_check_actually_fails_when_something_is_wrong(self):
        """A checker that cannot fail has not been tested."""
        saved = dict(vl.ACTIVITIES["mountain"])
        try:
            vl.ACTIVITIES["mountain"]["particles"] = 99
            vl.ACTIVITIES["mountain"]["kind"] = "trebuchet"
            report = vl.self_check()
            self.assertFalse(report["ok"])
            self.assertIn("over_particle_cap", report["problems"])
            self.assertIn("unknown_sprite", report["problems"])
        finally:
            vl.ACTIVITIES["mountain"] = saved
        self.assertTrue(vl.self_check()["ok"])


if __name__ == "__main__":
    unittest.main()
