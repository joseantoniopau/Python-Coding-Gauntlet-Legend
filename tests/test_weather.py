"""The sky: one source of truth, and it had better be pure, slow and varied.

The bug this file guards is not "does weather.py run". It is the three things
that were actually wrong before it existed:

    it always rained            -> every region must have a CLEAR state and
                                   must spend real time in it
    nothing ever changed        -> the condition must be a function of time and
                                   must actually move over a session
    two renderers disagreed     -> there must be exactly ONE answer, and the
                                   strip shipped to the client must be the same
                                   answer the server would give

Everything here is measured over simulated play rather than asserted about a
table, because a table nobody has run is a table nobody knows the shape of.
"""
from __future__ import annotations

import unittest
from collections import Counter

from base import GameTest  # noqa: F401  (imported for the data-dir fixture)

from gauntlet import elements, weather, world

REGIONS = [r["id"] for r in world.REGIONS]
SEEDS = [0, 1, 12345, 0xC0FFEE, 987654321, 0x51EED]
HOUR = 3600.0
BASE = 1_700_000_000.0


class TheModelIsPure(unittest.TestCase):
    """Same inputs, same answer. Twice, and a second apart."""

    def test_same_call_twice_is_identical(self):
        for rid in REGIONS:
            a = weather.forecast(rid, 12345, BASE)
            b = weather.forecast(rid, 12345, BASE)
            self.assertEqual(a, b, rid)

    def test_a_second_later_inside_a_spell_agrees(self):
        """Two calls a second apart inside one spell must agree. This is the
        promise a battle depends on: the fight must not change weather between
        the frame that built the backdrop and the frame that drew it."""
        checked = 0
        for seed in SEEDS:
            for rid in REGIONS:
                for step in range(0, 40):
                    t = BASE + step * 977.0        # a prime, to land anywhere
                    spell = weather.spell_at(rid, seed, t)
                    if spell["until"] - t < 2:
                        continue                    # genuinely on the boundary
                    self.assertEqual(weather.condition_at(rid, seed, t),
                                     weather.condition_at(rid, seed, t + 1),
                                     f"{rid} changed in one second")
                    checked += 1
        self.assertGreater(checked, 3000)

    def test_no_live_entropy_in_the_module(self):
        """A model that reads random.random() or its own clock cannot be
        reproduced, and weather.py is read by the server, by both renderers and
        by a simulation that all have to see the same sky.

        Parsed rather than grepped: the prose in this module talks ABOUT
        random.random() at length, and a test that cannot tell a sentence from a
        call is a test that will be deleted the first time it cries wolf."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(weather))
        banned = {"random", "time", "datetime", "secrets", "os", "uuid"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotIn(a.name.split(".")[0], banned, a.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], banned,
                                 node.module)
            elif isinstance(node, ast.Attribute):
                base = node.value
                if isinstance(base, ast.Name):
                    self.assertNotIn(base.id, banned,
                                     f"{base.id}.{node.attr}")

    def test_the_hash_does_not_move_between_runs(self):
        """Python salts hash() per interpreter. Weather that changed when the
        game relaunched would not be weather, so the module carries its own."""
        self.assertEqual(weather._h32("fields_of_syntax|12345|5666666|break"),
                         weather._h32("fields_of_syntax|12345|5666666|break"))
        self.assertEqual(weather.condition_at("fields_of_syntax", 12345, BASE),
                         weather.condition_at("fields_of_syntax", 12345, BASE))


class TheStripIsTheModel(unittest.TestCase):
    """The client never computes the weather; it reads a strip. So the strip has
    to BE the model, slot for slot, or the client is looking at a copy that can
    drift — which is the original bug in a new costume."""

    def test_every_slot_of_the_strip_matches_the_model(self):
        mismatches = 0
        for seed in (0, 12345, 0xC0FFEE):
            for rid in REGIONS:
                band = weather.strip(rid, seed, BASE, slots=weather.STRIP_SLOTS)
                for i, name in enumerate(band):
                    t = BASE + i * weather.SLOT_SECONDS
                    if weather.condition_at(rid, seed, t) != name:
                        mismatches += 1
        self.assertEqual(mismatches, 0)

    def test_the_legend_explains_every_name_in_the_strip(self):
        for seed in SEEDS:
            for rid in REGIONS:
                f = weather.forecast(rid, seed, BASE)
                for name in f["strip"]:
                    self.assertIn(name, f["legend"], f"{rid}: {name}")
                    leg = f["legend"][name]
                    self.assertEqual(leg["anim"],
                                     list(weather.CONDITIONS[name]["anim"]))
                self.assertIn(f["condition"], f["legend"])

    def test_the_strip_covers_two_hours_from_its_own_epoch(self):
        f = weather.forecast("fields_of_syntax", 7, BASE)
        self.assertEqual(len(f["strip"]), weather.STRIP_SLOTS)
        self.assertEqual(f["slot_seconds"], weather.SLOT_SECONDS)
        span = weather.STRIP_SLOTS * weather.SLOT_SECONDS
        self.assertGreaterEqual(span, 2 * HOUR)
        self.assertLessEqual(f["epoch"], BASE)
        self.assertLess(BASE - f["epoch"], weather.SLOT_SECONDS)
        # strip[0] is the slot containing `now`
        self.assertEqual(f["strip"][0], f["condition"])


class ItIsSlow(unittest.TestCase):
    """Weather that changes every few seconds is a strobe."""

    def test_a_spell_lasts_minutes_not_seconds(self):
        for seed in SEEDS:
            for rid in REGIONS:
                sim = weather.simulate(rid, seed, hours=300)
                self.assertGreaterEqual(sim["mean_spell_minutes"], 5.0)
                self.assertLessEqual(sim["mean_spell_minutes"], 20.0)

    def test_no_spell_can_outlast_the_cap(self):
        """The hard cap is what makes 'it always rains' structurally impossible
        rather than merely unlikely."""
        cap = weather.HOLD_CHAIN
        for seed in (0, 12345, 424242):
            for rid in REGIONS:
                run = 0
                prev = None
                first = weather.slot_of(BASE)
                for i in range(4000):
                    start = weather._spell_start(rid, weather._seed_int(seed),
                                                 first + i)
                    run = run + 1 if start == prev else 1
                    prev = start
                    self.assertLessEqual(run, cap, f"{rid} held {run} slots")

    def test_a_battle_length_window_almost_never_changes(self):
        """An encounter is one to three minutes. Over that window the sky should
        hold: a fight that changes weather halfway through is the strobe this
        dwell time exists to prevent."""
        changed = 0
        total = 0
        for seed in SEEDS:
            for rid in REGIONS:
                for i in range(120):
                    t = BASE + i * 131.0
                    total += 1
                    if (weather.condition_at(rid, seed, t)
                            != weather.condition_at(rid, seed, t + 120)):
                        changed += 1
        # 120s inside a 300s grid: at most 120/300 of windows can straddle a
        # boundary, and a boundary only changes the sky when the spell breaks.
        self.assertLess(changed / total, 0.25, f"{changed}/{total}")


class ItComesAndGoes(unittest.TestCase):
    """Sunny to rainy, none snowing to snowing, in every place there is."""

    def test_every_region_has_a_clear_state_and_lives_in_it(self):
        for seed in SEEDS:
            for rid in REGIONS:
                sim = weather.simulate(rid, seed, hours=300)
                clear = sim["share"].get("clear", 0.0)
                self.assertGreater(clear, 0.10,
                                   f"{rid} is clear only {clear:.1%} at {seed}")

    def test_nothing_is_one_weather(self):
        """The complaint, as an assertion: no region may sit in any single
        condition for most of its time."""
        for seed in SEEDS:
            for rid in REGIONS:
                sim = weather.simulate(rid, seed, hours=300)
                for cond, share in sim["share"].items():
                    self.assertLess(share, 0.62,
                                    f"{rid} is {cond} {share:.0%} at {seed}")

    def test_the_starting_village_is_mostly_fair(self):
        """This is the sentence that started the work: 'its sunny in the
        starting area'. Fair means clear or merely misted — nothing falling."""
        for seed in SEEDS:
            for rid in ("python_village", "fields_of_syntax"):
                sim = weather.simulate(rid, seed, hours=400)
                dry = sim["share"].get("clear", 0) + sim["share"].get("mist", 0)
                self.assertGreater(dry, 0.45, f"{rid} dry {dry:.0%} at {seed}")
                wet = sum(v for k, v in sim["share"].items()
                          if weather.CONDITIONS[k].get("wet"))
                self.assertLess(wet, 0.45, f"{rid} wet {wet:.0%} at {seed}")

    def test_a_session_sees_several_spells(self):
        """A 45 minute sitting should see the sky turn more than once, or the
        player never learns it turns at all."""
        for seed in SEEDS[:3]:
            for rid in REGIONS:
                seen = []
                for i in range(int(45 * 60 / weather.SLOT_SECONDS)):
                    c = weather.condition_at(rid, seed,
                                             BASE + i * weather.SLOT_SECONDS)
                    if not seen or seen[-1] != c:
                        seen.append(c)
                self.assertGreaterEqual(len(seen), 2, f"{rid} never changed")

    def test_different_seeds_are_different_worlds(self):
        a = weather.strip("fields_of_syntax", 1, BASE, 48)
        b = weather.strip("fields_of_syntax", 2, BASE, 48)
        self.assertNotEqual(a, b)

    def test_two_regions_sharing_a_biome_do_not_share_a_sky(self):
        """stringwood_labyrinth and binary_tree_canopy share the palette
        `verdant`, recursive_forest and stringwood are both woods. The weather
        is drawn per REGION, so standing in one tells you nothing about the
        other."""
        pairs = [("stringwood_labyrinth", "binary_tree_canopy"),
                 ("stack_queue_mines", "debugging_dungeon")]
        for a, b in pairs:
            self.assertNotEqual(weather.strip(a, 99, BASE, 48),
                                weather.strip(b, 99, BASE, 48))


class ItIsThematic(unittest.TestCase):
    """The player named the cases."""

    def test_ash_and_fireballs_in_the_volcano(self):
        """'ash and fireballs in the volcano' — stack_queue_mines and
        debugging_dungeon are the FIRE regions by elements.BIOME_AFFINITY."""
        fire = [r["id"] for r in world.REGIONS
                if elements.BIOME_AFFINITY.get(r["biome"]) == elements.FIRE]
        self.assertEqual(sorted(fire),
                         ["debugging_dungeon", "stack_queue_mines"])
        for rid in fire:
            names = set(weather.strip(rid, 12345, BASE, 500))
            self.assertIn("firestorm", names, rid)
            self.assertIn("fireball",
                          weather.CONDITIONS["firestorm"]["anim"])
            self.assertTrue(any("ash" in weather.CONDITIONS[n]["anim"]
                                for n in names), rid)

    def test_snow_where_it_is_cold_and_not_where_it_is_not(self):
        snowy = set()
        for rid in REGIONS:
            names = set(weather.strip(rid, 12345, BASE, 800))
            if any(weather.CONDITIONS[n].get("cold") for n in names):
                snowy.add(rid)
        self.assertIn("twin_pointer_pass", snowy)       # COLD, the snow line
        self.assertIn("complexity_tower", snowy)        # COLD, palette azure
        self.assertIn("hashmap_highlands", snowy)       # an exposed plateau
        for warm in ("stack_queue_mines", "sliding_window_marsh",
                     "coding_coliseum", "debugging_dungeon"):
            self.assertNotIn(warm, snowy, warm)

    def test_rain_with_lightning_in_ordinary_country(self):
        self.assertIn("lightning", weather.CONDITIONS["storm"]["anim"])
        self.assertIn("rain", weather.CONDITIONS["storm"]["anim"])
        names = set(weather.strip("fields_of_syntax", 12345, BASE, 800))
        self.assertIn("storm", names)
        self.assertIn("rain", names)
        self.assertIn("clear", names)

    def test_indoor_places_still_have_something_to_say(self):
        """'for all places'. A cave has no sky, so its weather is the roof."""
        for rid, expect in (("array_caverns", "seep"),
                            ("null_kings_castle", "godlight"),
                            ("matrix_citadel", "godlight")):
            self.assertIn(expect, set(weather.strip(rid, 12345, BASE, 800)), rid)

    def test_every_animation_is_one_the_renderer_can_draw(self):
        for name, c in weather.CONDITIONS.items():
            for a in c["anim"]:
                self.assertIn(a, weather.VOCAB, f"{name}: {a}")
        for biome, fx in weather.FIXTURES.items():
            self.assertIn(biome, weather.CLIMATE)
            for a in fx:
                self.assertIn(a, weather.VOCAB)

    def test_fixtures_are_never_weather(self):
        """A wall torch does not go out because the sky cleared."""
        furniture = set()
        for fx in weather.FIXTURES.values():
            furniture.update(fx)
        for name, c in weather.CONDITIONS.items():
            self.assertFalse(furniture & set(c["anim"]),
                             f"{name} claims furniture")


class EveryPlaceIsCovered(unittest.TestCase):

    def test_every_region_has_a_climate(self):
        for r in world.REGIONS:
            self.assertIn(r["biome"], weather.CLIMATE, r["id"])

    def test_every_climate_names_real_conditions(self):
        for biome, table in weather.CLIMATE.items():
            for name in table:
                self.assertIn(name, weather.CONDITIONS, f"{biome}:{name}")

    def test_the_weights_are_honoured_by_the_simulation(self):
        """A table nobody has run is a table nobody knows the shape of: the
        measured share of each condition must track its declared weight."""
        for rid in ("fields_of_syntax", "twin_pointer_pass",
                    "stack_queue_mines", "python_village"):
            biome = world.REGION_BY_ID[rid]["biome"]
            table = weather.CLIMATE[biome]
            total = sum(table.values())
            agg = Counter()
            for seed in range(24):
                sim = weather.simulate(rid, seed * 7919, hours=300)
                for k, v in sim["share"].items():
                    agg[k] += v / 24
            for name, w in table.items():
                self.assertAlmostEqual(agg[name], w / total, delta=0.06,
                                       msg=f"{rid}:{name}")

    def test_self_check_is_green(self):
        report = weather.self_check(seeds=6, hours=200)
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["biomes"], len(weather.CLIMATE))
        self.assertEqual(report["slot_seconds"], 300)


class ItRidesOnTheRegionPayload(GameTest):
    """The client gets no new route, no new fetch and no new plumbing: the sky
    arrives on the region record both renderers are already handed."""

    def test_the_dashboard_carries_the_sky(self):
        g = self.game()
        regions = g.dashboard()["regions"]
        self.assertEqual(len(regions), len(world.REGIONS))
        for r in regions:
            w = r.get("weather")
            self.assertIsInstance(w, dict, r["id"])
            self.assertEqual(w["region"], r["id"])
            self.assertEqual(w["biome"], r["biome"])
            self.assertIn(w["condition"], weather.CONDITIONS)
            self.assertEqual(len(w["strip"]), weather.STRIP_SLOTS)
            self.assertIn(w["condition"], w["legend"])
            self.assertGreater(w["now"], 1_600_000_000)
            for a in w["anim"]:
                self.assertIn(a, weather.VOCAB)

    def test_world_regions_are_not_mutated(self):
        """world.REGIONS is module-level shared state. A weather key written
        into it in place would hand every later caller the first caller's
        clock."""
        g = self.game()
        g.dashboard()
        for r in world.REGIONS:
            self.assertNotIn("weather", r, r["id"])

    def test_two_dashboards_in_one_spell_agree(self):
        g = self.game()
        a = {r["id"]: r["weather"]["condition"] for r in g.dashboard()["regions"]}
        b = {r["id"]: r["weather"]["condition"] for r in g.dashboard()["regions"]}
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
