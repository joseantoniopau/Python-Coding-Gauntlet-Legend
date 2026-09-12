"""The combat model: the wheel, the armour, the pouch, and the poison.

These tests pin the four properties the feature is not allowed to lose, in
descending order of how badly the game breaks without them:

  1. TYPING STILL RULES. No element, status, potion or piece of armour can
     produce damage from a wasted turn, cost a victim their turn, or shorten a
     fight. The Python is the attack; everything here is a multiplier on a
     number the typing already earned.
  2. LEARNING NEVER DEAD-ENDS. The worst loadout in the game against the worst
     matchup in the game still kills the enemy, in a bounded number of casts.
     Elemental disadvantage is a tax on time, never a lock.
  3. THE CHOICE IS REAL. The right element and the right armour measurably
     change the outcome. If they ever stop doing so the feature is decoration,
     and these tests are how we find out.
  4. ONE RULE PER MECHANIC. There are two poison representations in this game
     and exactly one stacking rule and one cure between them.

They are deliberately pure module tests — no corpus, no save file, no Game — so
they run in milliseconds and a failure points at the model rather than at the
harness.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gauntlet import elements as E          # noqa: E402
from gauntlet import potions as P           # noqa: E402
from gauntlet import config                 # noqa: E402

ALL = list(E.ELEMENTS) + [E.NEUTRAL]


# ---------------------------------------------------------------------------
# 1. The wheel
# ---------------------------------------------------------------------------

class TestTheWheel(unittest.TestCase):
    """Three opposed pairs, one documented secondary edge, and no chain."""

    def test_exactly_three_opposed_pairs(self):
        pairs = {tuple(sorted((e, E.OPPOSED[e]))) for e in E.ELEMENTS}
        self.assertEqual(len(pairs), 3)
        self.assertEqual(
            pairs,
            {("COLD", "FIRE"), ("BRUTE", "POISON"), ("LIGHTNING", "VOID")},
            "the brief's ambiguity is resolved as three pairs; changing them is "
            "a design decision, not a refactor",
        )

    def test_opposition_is_symmetric_and_total(self):
        # A pair where only one side wins is a pair nobody picks the losing
        # half of, which would collapse six elements into three.
        for e in E.ELEMENTS:
            self.assertEqual(E.OPPOSED[E.OPPOSED[e]], e)
            self.assertNotEqual(E.OPPOSED[e], e)
            self.assertTrue(E.opposes(e, E.OPPOSED[e]))
            self.assertTrue(E.opposes(E.OPPOSED[e], e))

    def test_opposed_multiplier_is_symmetric(self):
        for e in E.ELEMENTS:
            a = E.matchup(e, E.OPPOSED[e])
            b = E.matchup(E.OPPOSED[e], e)
            self.assertEqual(a, b)
            self.assertEqual(a[1], "OPPOSED")

    def test_the_secondary_edge_is_weaker_than_a_pair_and_asymmetric(self):
        # "Void against poison" is the clause the three pairs could not absorb.
        # It survives as a lesser advantage with a weak mirror, and it must
        # never quietly become a fourth pair.
        strong, kind = E.matchup(E.VOID, E.POISON)
        weak, mirror = E.matchup(E.POISON, E.VOID)
        self.assertEqual(kind, "SECONDARY")
        self.assertEqual(mirror, "WEAK_INTO")
        self.assertLess(strong, E.MATCHUP_MULT["OPPOSED"])
        self.assertGreater(strong, E.MATCHUP_MULT["NEUTRAL"])
        self.assertLess(weak, E.MATCHUP_MULT["NEUTRAL"])
        self.assertNotEqual(strong, weak)

    def test_same_element_is_blunted_but_never_nullified(self):
        # "Your element does nothing here" is a dead end. A tax is not.
        for e in E.ELEMENTS:
            mult, kind = E.matchup(e, e)
            self.assertEqual(kind, "SAME")
            self.assertGreater(mult, 0.0)
            self.assertLess(mult, 1.0)

    def test_neutral_is_a_sentinel_not_an_element(self):
        self.assertNotIn(E.NEUTRAL, E.ELEMENTS)
        self.assertIn(E.NEUTRAL, E.ALL_AFFINITIES)
        for e in ALL:
            self.assertEqual(E.matchup(E.NEUTRAL, e)[1], "NEUTRAL")
            self.assertEqual(E.matchup(e, E.NEUTRAL)[1], "NEUTRAL")

    def test_matchup_is_total_and_never_raises(self):
        # An unelemented enemy is a normal thing for the bestiary to contain,
        # and a KeyError mid-fight is not.
        for junk in ("", "STEAM", None, "fire", 7):
            mult, kind = E.matchup(junk, E.FIRE)
            self.assertEqual(kind, "NEUTRAL")
            self.assertEqual(mult, 1.0)

    def test_no_element_sits_on_top_of_the_wheel(self):
        # Every element must be beaten by something, or the wheel has a
        # dominant pick and the choice stops being a choice.
        for e in E.ELEMENTS:
            beaten_by = [a for a in E.ELEMENTS if E.matchup(a, e)[0] > 1.0]
            self.assertTrue(beaten_by, f"{e} has no counter")

    def test_every_element_has_one_status_and_every_status_has_an_element(self):
        owned = {el.status for el in E.ELEMENTS.values()}
        self.assertEqual(owned, set(E.STATUS_IDS))
        for el in E.ELEMENTS.values():
            self.assertIn(el.status, E.STATUSES)
            self.assertEqual(E.STATUSES[el.status].element, el.id)


# ---------------------------------------------------------------------------
# 2. Areas, boots and companions resolve against the real files
# ---------------------------------------------------------------------------

class TestTheWorldAgrees(unittest.TestCase):

    def test_every_region_in_world_py_has_an_affinity(self):
        from gauntlet import world
        self.assertEqual(len(E.AFFINITY), len(world.REGIONS))
        for region in world.REGIONS:
            self.assertIn(region["id"], E.AFFINITY)
            self.assertIn(E.AFFINITY[region["id"]], E.ALL_AFFINITIES)

    def test_every_biome_is_placed_on_the_wheel(self):
        # A new biome must fail loudly here rather than silently defaulting to
        # neutral and giving a region no weather.
        from gauntlet import world
        for region in world.REGIONS:
            self.assertIn(region["biome"], E.BIOME_AFFINITY,
                          f"biome {region['biome']!r} is not on the wheel")

    def test_neutral_regions_exist_on_purpose(self):
        neutral = [r for r, e in E.AFFINITY.items() if e == E.NEUTRAL]
        self.assertTrue(neutral, "a wheel with no contrast has no baseline")
        self.assertIn("coding_coliseum", neutral,
                      "the Coliseum's own blurb says sand, a clock and no hints")

    def test_bosses_take_the_element_of_their_region(self):
        from gauntlet import world
        for boss in world.BOSSES:
            self.assertEqual(E.boss_element(boss["id"]),
                             E.affinity_for(boss.get("region", "")))

    def test_an_enemy_with_no_element_takes_the_ground_it_stands_on(self):
        from gauntlet import bestiary
        enemy = bestiary.ENEMIES[0]
        self.assertFalse(hasattr(enemy, "element"))
        for region in ("twin_pointer_pass", "stringwood_labyrinth",
                       "python_village"):
            self.assertEqual(E.enemy_element(enemy, region),
                             E.affinity_for(region))

    def test_an_enemy_may_override_with_its_own_element(self):
        self.assertEqual(E.enemy_element({"element": E.VOID}, "python_village"),
                         E.VOID)

    def test_every_companion_in_pets_py_resolves_to_an_element(self):
        from gauntlet import pets
        for pet in pets.PETS:
            self.assertIn(E.pet_element(pet.species, pet.id), E.ELEMENTS,
                          f"{pet.id} ({pet.species}) is not on the wheel")

    def test_the_brief_named_two_companions_and_they_are_right(self):
        self.assertEqual(E.pet_element("penguin"), E.COLD)
        self.assertEqual(E.pet_element("jaguar"), E.POISON)

    def test_every_element_has_a_companion_and_a_hazard(self):
        placed = set(E.PET_ELEMENT.values())
        self.assertTrue(set(E.ELEMENTS) <= placed)
        self.assertEqual(set(E.HAZARD_BY_ELEMENT), set(E.ELEMENTS))

    def test_boots_answer_every_hazard_the_brief_named(self):
        tags = {t for b in E.BOOTS for t in b.immunities}
        for hazard in E.HAZARDS.values():
            self.assertIn(hazard.boots_tag, tags)
        # The three the brief called out by name.
        self.assertTrue(E.hazard_step("twin_pointer_pass", "crampons")["protected"])
        self.assertTrue(E.hazard_step("stack_queue_mines", "cinder_greaves")["protected"])
        self.assertTrue(E.hazard_step("null_kings_castle", "lanternshoes")["protected"])

    def test_a_hazard_slows_or_marks_but_never_kills(self):
        for region in E.AFFINITY:
            step = E.hazard_step(region, "", roll=0.0)
            self.assertGreater(step["speed"], 0.0)
            self.assertNotIn("damage", step)
            if step["status"]:
                self.assertIn(step["status"], E.STATUSES)


# ---------------------------------------------------------------------------
# 3. Armour: monotone, and it actually matters
# ---------------------------------------------------------------------------

class TestArmourMonotonicity(unittest.TestCase):

    def test_more_armour_points_never_increase_damage(self):
        for attacker in ALL:
            for defender in ALL:
                for base in (1, 7, 10, 40, 250):
                    last = None
                    for points in range(0, 60, 3):
                        d = E.resolve_damage(
                            base, attacker,
                            E.Defender(element=defender,
                                       armour=E.ArmourProfile(
                                           points=points,
                                           points_cap=E.ARMOUR_POINT_CAP)),
                        ).damage
                        if last is not None:
                            self.assertLessEqual(d, last)
                        last = d

    def test_more_resistance_never_increases_damage(self):
        for element in E.ELEMENTS:
            last = None
            for r in (0.0, 0.1, 0.2, 0.3, 0.45, 0.6, 0.99):
                d = E.resolve_damage(
                    40, element,
                    E.Defender(element=E.NEUTRAL,
                               armour=E.ArmourProfile(resist={element: r})),
                ).damage
                if last is not None:
                    self.assertLessEqual(d, last)
                last = d

    def test_damage_is_never_zero_or_negative_however_armoured(self):
        # This is the no-dead-end guarantee at the level of a single hit: a
        # landed cast always removes at least one point, so the fight ends.
        absurd = E.ArmourProfile(points=10 ** 6, resist={E.FIRE: 1.0},
                                 points_cap=E.ARMOUR_POINT_CAP)
        for base in (1, 2, 3, 10, 100):
            d = E.resolve_damage(base, E.FIRE,
                                 E.Defender(element=E.FIRE, armour=absurd)).damage
            self.assertGreaterEqual(d, E.MIN_DAMAGE)

    def test_resistance_is_capped_so_an_area_can_always_hurt_you(self):
        for element in E.ELEMENTS:
            profile = E.armour_from_effects({f"resist_{element.lower()}": 5.0})
            self.assertLessEqual(profile.resist_to(element), E.RESIST_CAP)

    def test_flat_points_are_capped_as_a_fraction_of_the_hit(self):
        # Plate scales with the blow rather than trailing it, which is what
        # makes it the only kind whose points still count when something large
        # lands. A hit can never be fully absorbed.
        for base in (4, 10, 60):
            result = E.resolve_damage(
                base, E.NEUTRAL,
                E.Defender(element=E.NEUTRAL,
                           armour=E.ArmourProfile(points=10 ** 6,
                                                  points_cap=E.ARMOUR_POINT_CAP)))
            self.assertLessEqual(result.armour_absorbed,
                                 round(base * E.ARMOUR_POINT_CAP) + 1)
            self.assertGreaterEqual(result.damage, E.MIN_DAMAGE)

    def test_plate_and_warded_are_different_roads(self):
        # Flat mitigation against small unpredictable hits; proportional
        # mitigation against big predictable ones. If these ever collapse into
        # each other the armour choice stops being a choice.
        self.assertGreater(E.ARMOUR_KINDS["PLATE"]["points_cap"],
                           E.ARMOUR_KINDS["WARDED"]["points_cap"])
        plate = E.armour_profile("PLATE")
        warded = E.armour_profile("WARDED", element=E.FIRE, resist=0.3)
        self.assertGreater(plate.points, warded.points)
        self.assertGreater(warded.resist_to(E.FIRE), plate.resist_to(E.FIRE))

    def test_the_cloak_road_uses_the_effect_keys_engine_py_already_reads(self):
        # engine.py folds `stamina_max` / `mana_max` into the bars already. An
        # earlier draft read `health_bonus` / `focus_bonus`, which no item sets,
        # so the brief's third road silently reported zero for every loadout.
        from gauntlet import items
        self.assertIn(E.HEALTH_EFFECT_KEY, items.EFFECT_LABELS)
        self.assertIn(E.FOCUS_EFFECT_KEY, items.EFFECT_LABELS)
        profile = E.armour_from_effects({E.HEALTH_EFFECT_KEY: 6,
                                         E.FOCUS_EFFECT_KEY: 4})
        self.assertEqual(profile.bonus_health, 6)
        self.assertEqual(profile.bonus_focus, 4)

    def test_bar_bonuses_stay_out_of_the_damage_maths(self):
        # The third road is a longer bar, not mitigation. If it ever started
        # reducing damage it would be strictly better than the other two.
        plain = E.resolve_damage(10, E.FIRE, E.Defender(element=E.NEUTRAL)).damage
        cloaked = E.resolve_damage(
            10, E.FIRE,
            E.Defender(element=E.NEUTRAL,
                       armour=E.armour_from_effects({E.HEALTH_EFFECT_KEY: 99,
                                                     E.FOCUS_EFFECT_KEY: 99})),
        ).damage
        self.assertEqual(plain, cloaked)


# ---------------------------------------------------------------------------
# 4. Learning never dead-ends
# ---------------------------------------------------------------------------

class TestNoDeadEnd(unittest.TestCase):

    WORST = E.ArmourProfile(points=9999, resist={E.COLD: E.RESIST_CAP},
                            points_cap=E.ARMOUR_POINT_CAP, kind="PLATE")

    def test_the_module_proves_it_itself(self):
        proof = E._prove_no_dead_end()
        self.assertTrue(proof["every_worst_case_still_lands"])
        self.assertTrue(proof["ratio_holds"])
        self.assertTrue(proof["stretch_within_declared"])
        self.assertTrue(proof["stretch_vs_counter_within_declared"])
        self.assertTrue(proof["winnable_without_potions"])

    def test_the_worst_matchup_in_the_game_still_kills_the_enemy(self):
        # Wrong element, no potions, enemy in capped warded plate. The fight is
        # long. It is never lost, because every correct cast still lands.
        defender = E.Defender(element=E.COLD, armour=self.WORST, max_health=60)
        hp, casts = 60, 0
        while hp > 0 and casts < 10_000:
            hp -= E.resolve_damage(10, E.COLD, defender).damage
            casts += 1
        self.assertLessEqual(hp, 0)
        self.assertLess(casts, 10_000)

    def test_both_stretch_bounds_hold_and_are_distinct(self):
        # Two honest questions: how much worse than a PLAIN fight, and how much
        # worse than a fight you actually read. The second is the bigger number
        # and it is the one a balance conversation should quote.
        self.assertGreater(E.MAX_FIGHT_STRETCH_VS_COUNTER, E.MAX_FIGHT_STRETCH)
        proof = E._prove_no_dead_end()
        self.assertLessEqual(proof["worst_cast_stretch"], E.MAX_FIGHT_STRETCH)
        self.assertLessEqual(proof["worst_cast_stretch_vs_counter"],
                             E.MAX_FIGHT_STRETCH_VS_COUNTER)
        self.assertGreater(proof["worst_cast_stretch_vs_counter"],
                           proof["worst_cast_stretch"])

    def test_disadvantage_lengthens_the_fight_rather_than_losing_it(self):
        def casts_to_kill(attacker, armour):
            hp, n = 50, 0
            defender = E.Defender(element=E.COLD, armour=armour, max_health=50)
            while hp > 0 and n < 10_000:
                hp -= E.resolve_damage(10, attacker, defender).damage
                n += 1
            return n

        best = casts_to_kill(E.FIRE, E.NO_ARMOUR)
        worst = casts_to_kill(E.COLD, self.WORST)
        self.assertGreater(worst, best, "disadvantage must cost something")
        self.assertLessEqual(worst / best, E.MAX_FIGHT_STRETCH_VS_COUNTER)

    def test_a_temporary_status_cannot_break_the_floor_permanently(self):
        # CHILLED can momentarily push below the persistent floor, which is
        # allowed, but it expires on its own and cannot stack with itself.
        chilled = [E.StatusInstance("CHILLED", 3)]
        for _ in range(5):
            E.inflict(chilled, "CHILLED")
        self.assertEqual(len(chilled), 1)
        self.assertEqual(chilled[0].stacks, 1)
        damage = E.resolve_damage(10, E.FIRE, E.Defender(element=E.COLD),
                                  attacker_statuses=chilled).damage
        self.assertGreaterEqual(damage, E.MIN_DAMAGE)


# ---------------------------------------------------------------------------
# 5. The choice is real
# ---------------------------------------------------------------------------

class TestItIsActuallyStrategic(unittest.TestCase):

    def test_reading_the_area_right_is_worth_a_large_measurable_amount(self):
        target = E.Defender(element=E.COLD, max_health=50)
        counter = E.resolve_damage(10, E.FIRE, target).damage
        plain = E.resolve_damage(10, E.LIGHTNING, target).damage
        wrong = E.resolve_damage(10, E.COLD, target).damage
        self.assertGreater(counter, plain)
        self.assertGreater(plain, wrong)
        # Not a rounding artefact: the counter must be worth at least a third
        # more than the wrong pick, or nobody will bother switching weapons.
        self.assertGreaterEqual(counter / wrong, 1.33)

    def test_resistance_pays_out_only_when_you_guessed_right(self):
        # Leverage, not certainty. This asymmetry is the whole reason warded
        # gear is a different decision from plate.
        warded = E.ArmourProfile(resist={E.FIRE: 0.5}, points_cap=0.2)
        right = E.resolve_damage(20, E.FIRE,
                                 E.Defender(element=E.NEUTRAL, armour=warded)).damage
        wrong = E.resolve_damage(20, E.COLD,
                                 E.Defender(element=E.NEUTRAL, armour=warded)).damage
        bare = E.resolve_damage(20, E.COLD, E.Defender(element=E.NEUTRAL)).damage
        self.assertLess(right, wrong)
        self.assertEqual(wrong, bare, "warding the wrong element buys nothing")

    def test_plate_matters_more_on_big_hits_than_warded_does_on_small_ones(self):
        # The brief: "plate reduces large hits".
        plate = E.ArmourProfile(points=6, points_cap=0.5)
        small = E.resolve_damage(4, E.NEUTRAL,
                                 E.Defender(element=E.NEUTRAL, armour=plate))
        large = E.resolve_damage(60, E.NEUTRAL,
                                 E.Defender(element=E.NEUTRAL, armour=plate))
        self.assertGreater(large.armour_absorbed, small.armour_absorbed)

    def test_brute_force_is_the_answer_to_armour_points(self):
        # STAGGERED halves flat mitigation. The counter to plate is not a
        # better element, it is brute force, and that is literally true here.
        plate = E.ArmourProfile(points=8, points_cap=0.5)
        target = E.Defender(element=E.NEUTRAL, armour=plate)
        intact = E.resolve_damage(20, E.NEUTRAL, target).damage
        target.statuses = [E.StatusInstance("STAGGERED", 2)]
        staggered = E.resolve_damage(20, E.NEUTRAL, target).damage
        self.assertGreater(staggered, intact)

    def test_lightning_amplifies_rather_than_deals(self):
        target = E.Defender(element=E.NEUTRAL, max_health=50)
        plain = E.resolve_damage(20, E.NEUTRAL, target).damage
        target.statuses = [E.StatusInstance("SHOCKED", 2)]
        shocked = E.resolve_damage(20, E.NEUTRAL, target).damage
        self.assertGreater(shocked, plain)

    def test_the_element_is_never_enough_on_its_own(self):
        # THE RULE THAT OUTRANKS EVERYTHING: a perfect matchup on a wasted turn
        # is still a wasted turn.
        for attacker in ALL:
            for defender in ALL:
                self.assertEqual(
                    E.resolve_damage(0, attacker,
                                     E.Defender(element=defender)).damage, 0)


# ---------------------------------------------------------------------------
# 6. Nothing here can supply an answer or skip a turn
# ---------------------------------------------------------------------------

class TestTypingStillRules(unittest.TestCase):

    def test_no_status_can_cost_the_victim_their_turn(self):
        # A status that skipped a turn would be a status that reduced how much
        # Python got typed, which is the one thing this feature must not do.
        for status in E.STATUSES.values():
            self.assertIn(status.kind, E._STATUS_KINDS)
            self.assertNotIn(status.kind, ("skip", "stun", "silence", "turn"))

    def test_voided_stops_focus_returning_but_never_focus_being_spent(self):
        # Hints cost focus. A status that locked the hint tree could strand a
        # learner, so VOIDED blocks regeneration only.
        voided = E.STATUSES["VOIDED"]
        self.assertEqual(voided.kind, "regen")
        tick = E.tick_statuses([E.StatusInstance("VOIDED", 3)], 20)
        self.assertTrue(tick["regen_blocked"])
        self.assertEqual(tick["damage"], 0)

    def test_resolve_damage_is_pure(self):
        statuses = [E.StatusInstance("SHOCKED", 2)]
        defender = E.Defender(element=E.COLD, statuses=statuses)
        before = [s.to_dict() for s in statuses]
        first = E.resolve_damage(10, E.FIRE, defender, roll=0.0)
        second = E.resolve_damage(10, E.FIRE, defender, roll=0.0)
        self.assertEqual(first.damage, second.damage)
        self.assertEqual(before, [s.to_dict() for s in statuses],
                         "applying the status is the caller's job, via inflict")

    def test_no_potion_touches_anything_but_the_two_bars_and_poison(self):
        for potion in P.CATALOGUE:
            self.assertTrue(set(potion.effect_keys) <= {"stamina", "mana", "poison"})

    def test_a_shrugged_off_hit_inflicts_nothing(self):
        # Hitting fire with fire does not set anything alight.
        self.assertEqual(E.INFLICT_CHANCE["SAME"], 0.0)
        result = E.resolve_damage(10, E.FIRE, E.Defender(element=E.FIRE), roll=0.0)
        self.assertEqual(result.inflicted, "")


# ---------------------------------------------------------------------------
# 7. The seal — one isolation path, and it is an argument
# ---------------------------------------------------------------------------

class TestTheSeal(unittest.TestCase):

    class _Exam:
        mode = config.MODE_INTERVIEW
        boss_id = ""
        holdout = False

    def test_build_sealed_strips_the_whole_loadout(self):
        armoured = E.Defender(element=E.FIRE,
                              armour=E.ArmourProfile(points=9, resist={E.COLD: 0.6}))
        sealed = E.resolve_damage(10, E.COLD, armoured, build_sealed=True).damage
        plain = E.resolve_damage(10, E.NEUTRAL, E.Defender(element=E.NEUTRAL)).damage
        self.assertEqual(sealed, plain)

    def test_a_sealed_fight_still_lands_and_is_still_winnable(self):
        self.assertGreaterEqual(
            E.resolve_damage(10, E.COLD, E.Defender(element=E.COLD),
                             build_sealed=True).damage, E.MIN_DAMAGE)

    def test_a_sealed_hit_inflicts_no_status(self):
        result = E.resolve_damage(10, E.FIRE, E.Defender(element=E.COLD),
                                  roll=0.0, build_sealed=True)
        self.assertEqual(result.inflicted, "")

    def test_potions_do_not_work_in_interview_mode(self):
        refused = P.drink(P.full_pouch(), "health_hefty",
                          player={"stamina": 1, "stamina_max": 20},
                          turn_state=P.new_fight(), encounter=self._Exam())
        self.assertEqual(refused.get("error"), "sealed")

    def test_there_is_exactly_one_isolation_path(self):
        # Both modules route every gate through finalexam. Neither forms its own
        # opinion about what mode it is in.
        import inspect
        from gauntlet import finalexam
        self.assertIn("ITEMS", finalexam.CAPABILITY_NAMES)
        self.assertIn("BUILD", finalexam.CAPABILITY_NAMES)
        self.assertIn("WEAKNESS_MAP", finalexam.CAPABILITY_NAMES)
        source = inspect.getsource(E)
        self.assertNotIn("MODE_INTERVIEW", source,
                         "elements.py must take the verdict as an argument")

    def test_an_unrevealed_element_still_multiplies(self):
        # Sealing the WEAKNESS_MAP removes the crutch, not the mechanic.
        hidden = E.element_view(E.FIRE, revealed=False)
        self.assertFalse(hidden["revealed"])
        self.assertEqual(hidden["id"], "")
        self.assertEqual(E.matchup(E.FIRE, E.COLD)[1], "OPPOSED")


# ---------------------------------------------------------------------------
# 8. Poison — one rule, one cure, across two representations
# ---------------------------------------------------------------------------

class TestPoison(unittest.TestCase):

    def test_the_two_models_agree_on_the_stacking_rule(self):
        # This is the regression that mattered most: potions used to append
        # doses without limit while the wheel capped POISONED at two stacks, so
        # the same word named a 2-damage effect and a 10-damage one.
        self.assertEqual(P.MAX_DOSES, E.STATUSES["POISONED"].max_stacks)

    def test_poison_stacks_to_two_and_no_further(self):
        poison = P.Poison()
        for _ in range(8):
            P.poison_apply(poison, damage=2, turns=3)
        self.assertEqual(len(poison.doses), P.MAX_DOSES)

        wheel: list = []
        for _ in range(8):
            E.inflict(wheel, "POISONED")
        self.assertEqual(len(wheel), 1)
        self.assertEqual(wheel[0].stacks, E.STATUSES["POISONED"].max_stacks)

    def test_a_capped_application_refreshes_rather_than_being_discarded(self):
        poison = P.Poison()
        P.poison_apply(poison, damage=2, turns=1)
        P.poison_apply(poison, damage=2, turns=1)
        for dose in poison.doses:
            dose.turns = 1
        P.poison_apply(poison, damage=2, turns=5)
        self.assertEqual(len(poison.doses), P.MAX_DOSES)
        self.assertEqual(max(d.turns for d in poison.doses), 5)

    def test_poison_ticks_at_the_start_of_the_victims_turn(self):
        # So a player about to die of poison finds out while they still have a
        # turn in which to drink something.
        poison = P.Poison()
        P.poison_apply(poison, damage=3, turns=2)
        self.assertEqual(P.poison_tick(poison)["damage"], 3)
        self.assertEqual(P.poison_tick(poison)["damage"], 3)
        self.assertEqual(P.poison_tick(poison)["damage"], 0)
        self.assertFalse(poison.active)

    def test_poison_damage_is_never_negative_and_always_terminates(self):
        poison = P.Poison()
        for _ in range(20):
            P.poison_apply(poison, damage=99, turns=99)
        ticks = 0
        while poison.active and ticks < 5_000:
            self.assertGreaterEqual(P.poison_tick(poison)["damage"], 0)
            ticks += 1
        self.assertFalse(poison.active)

        wheel: list = []
        for _ in range(20):
            E.inflict(wheel, "POISONED")
        ticks = 0
        while wheel and ticks < 5_000:
            self.assertGreaterEqual(E.tick_statuses(wheel, 20)["damage"], 0)
            ticks += 1
        self.assertFalse(wheel)

    def test_poison_cannot_take_a_clamped_caller_below_zero(self):
        poison = P.Poison()
        P.poison_apply(poison, damage=50, turns=5)
        hp = 20
        for _ in range(10):
            hp = max(0, hp - P.poison_tick(poison)["damage"])
        self.assertEqual(hp, 0)

    def test_the_wheel_dot_is_a_fraction_of_maximum_health(self):
        # A flat number would be trivial on a 60 HP enemy and lethal on a 20 HP
        # player. A percentage is the same lesson at both scales.
        wheel: list = []
        E.inflict(wheel, "POISONED")
        small = E.tick_statuses(list(wheel), 20)["damage"]
        large = E.tick_statuses(list(wheel), 200)["damage"]
        self.assertGreater(large, small)

    def test_the_dot_is_sized_off_maximum_not_current_health(self):
        # Regression: Defender.for_enemy used to read `hp`, so poison weakened
        # as the enemy weakened — a fifth of a bar at full health decaying to
        # one point at death's door, which is precisely backwards.
        class _Dying:
            hp = 3
            hp_max = 60

        self.assertEqual(E.Defender.for_enemy(_Dying()).max_health, 60)
        self.assertEqual(
            E.Defender.for_enemy({"hp": 3, "hp_max": 60}).max_health, 60)

    def test_an_antidote_clears_both_representations(self):
        # The brief says antidotes clear poison. A marsh monster poisons you
        # through elements.resolve_damage().inflicted, so an antidote that only
        # emptied the dose pool left that poison incurable.
        poison = P.Poison()
        P.poison_apply(poison, damage=2, turns=3)
        wheel: list = []
        E.inflict(wheel, "POISONED")
        result = P.drink(P.full_pouch(), "antidote_medium",
                         player={"stamina": 5, "stamina_max": 20,
                                 "mana": 5, "mana_max": 30},
                         turn_state=P.new_fight(), poison=poison, statuses=wheel)
        self.assertTrue(result["ok"])
        self.assertFalse(poison.active)
        self.assertEqual(wheel, [])
        self.assertIn("POISONED", result["statuses_cured"])

    def test_an_antidote_is_offered_when_only_the_wheel_status_is_present(self):
        wheel: list = []
        E.inflict(wheel, "POISONED")
        pouch = P.Pouch()
        pouch.add("antidote_minor", 1)
        view = P.pouch_view(pouch, player={"stamina": 5, "stamina_max": 20},
                            turn_state=P.new_fight(), poison=P.Poison(),
                            statuses=wheel)
        self.assertTrue(view["potions"][0]["usable"])

    def test_the_antidote_is_narrow_on_purpose(self):
        # A cure-all would make the other five statuses decorative.
        self.assertEqual(set(E.CURES["ANTIDOTE"]), {"POISONED"})
        wheel = [E.StatusInstance("BURNING", 2), E.StatusInstance("POISONED", 4)]
        E.cure(wheel, "ANTIDOTE")
        self.assertEqual([s.id for s in wheel], ["BURNING"])

    def test_a_ward_refuses_new_poison_out_loud(self):
        poison = P.Poison()
        P.poison_clear(poison, clears=0, ward_turns=3)
        applied = P.poison_apply(poison, damage=2, turns=3)
        self.assertFalse(applied["applied"])
        self.assertTrue(applied["warded"])
        self.assertTrue(applied["line"])

    def test_poison_applies_to_monsters_exactly_as_to_the_player(self):
        # tick_statuses never asks whose list it is holding.
        monster: list = []
        E.inflict(monster, "POISONED")
        self.assertGreater(E.tick_statuses(monster, 60)["damage"], 0)

    def test_a_monster_cures_out_loud_and_it_costs_it_the_turn(self):
        poison = P.Poison()
        P.poison_apply(poison, damage=4, turns=4)
        moment = P.monster_cure({"name": "mirebound", "title": "the Warden",
                                 "antidotes": 1, "hp": 60, "hp_max": 60}, poison)
        self.assertTrue(moment["line"])
        self.assertTrue(moment["turn_spent"])
        self.assertFalse(poison.active)

    def test_a_monster_without_an_antidote_does_not_invent_one(self):
        poison = P.Poison()
        P.poison_apply(poison, damage=4, turns=4)
        self.assertIsNone(P.monster_cure({"name": "x", "antidotes": 0,
                                          "hp": 60, "hp_max": 60}, poison))


# ---------------------------------------------------------------------------
# 9. Potions cannot replace thinking
# ---------------------------------------------------------------------------

class TestPotionBalance(unittest.TestCase):

    def test_the_module_proves_it_itself(self):
        self.assertEqual(P._PROBLEMS, [])

    def test_a_draught_is_free_but_a_second_one_costs_a_cast(self):
        # These two sentences together are the whole feature.
        pouch = P.full_pouch()
        turn = P.new_fight()
        player = {"stamina": 1, "stamina_max": 20, "mana": 1, "mana_max": 30}
        first = P.drink(pouch, "health_minor", player=player, turn_state=turn)
        self.assertTrue(first["ok"])
        self.assertFalse(first["turn_spent"])
        self.assertTrue(first["must_still_cast"])

        second = P.drink(pouch, "health_small", player=player, turn_state=turn)
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"], "already")

        P.cast_resolved(turn, correct=True)
        self.assertTrue(P.drink(pouch, "health_small", player=player,
                                turn_state=turn)["ok"])

    def test_a_wrong_cast_still_advances_the_turn(self):
        # Otherwise the pouch could be emptied by typing nonsense.
        turn = P.new_fight()
        turn.drunk_this_turn = "health_minor"
        P.cast_resolved(turn, correct=False)
        self.assertTrue(turn.may_drink)

    def test_no_potion_is_ever_a_full_heal(self):
        for maximum in (10, 20, 30, 60, 120, 400):
            for kind in ("HEALTH", "FOCUS"):
                for strength in P.STRENGTHS:
                    restored = P.band_restore(kind, strength, maximum)
                    self.assertLess(restored, maximum)
                    self.assertLessEqual(restored,
                                         int(maximum * P.CEILING_FRACTION))

    def test_restoration_is_monotonic_in_strength(self):
        for maximum in (20, 30, 60, 120):
            for kind in ("HEALTH", "FOCUS"):
                values = [P.band_restore(kind, s, maximum) for s in P.STRENGTHS]
                self.assertEqual(values, sorted(values))

    def test_diminishing_returns_inside_one_fight(self):
        values = [P.sip_multiplier(n) for n in range(8)]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(values[0], 1.0)
        self.assertGreaterEqual(min(values), P.SIP_FLOOR)

    def test_carry_caps_tighten_as_the_potion_gets_stronger(self):
        caps = [P.CARRY_CAP[s] for s in P.STRENGTHS]
        self.assertEqual(caps, sorted(caps, reverse=True))
        self.assertEqual(len(set(caps)), len(caps))

    def test_the_pouch_refuses_to_hold_more_than_the_cap(self):
        pouch = P.Pouch()
        report = pouch.add("health_hefty", 99)
        self.assertEqual(pouch.count("health_hefty"),
                         P.BY_ID["health_hefty"].cap)
        self.assertGreater(report["overflow"], 0,
                           "overflow must be reported, not silently dropped")

    def test_a_full_pouch_never_shortens_a_fight(self):
        # Paired runs: the cast sequence is identical with and without the
        # pouch, because drinking consumes no randomness. So this is the same
        # fight twice with one variable changed, not a statistical claim.
        for seed in range(1, 31):
            for scenario in (dict(damage=16), dict(damage=5),
                             dict(damage=5, poison_on_miss=3)):
                bare = P.simulate(seed=seed, **scenario)
                full = P.simulate(seed=seed, pouch=P.full_pouch(), **scenario)
                self.assertGreaterEqual(
                    full["casts"], bare["casts"],
                    f"a pouch bought its way out of typing at seed {seed}")

    # bestiary.ENEMIES averages 50 HP, so that is the size of fight this
    # comparison is about. simulate()'s own 240 default is a boss, where the
    # pouch cannot rescue a 45% player at all — it runs dry first — which is a
    # fine result but a different question from the one being asked here.
    TYPICAL_ENEMY_HP = 50

    def test_drinking_optimally_never_beats_writing_good_python(self):
        # THE FAILURE THAT WOULD MATTER MOST. A player who drinks perfectly and
        # types badly must not reach the kill faster than a player who types
        # well and drinks nothing. Both fight the same mismatched enemy.
        sloppy = [P.simulate(seed=s, enemy_hp=self.TYPICAL_ENEMY_HP, damage=5,
                             accuracy=0.45, pouch=P.full_pouch())
                  for s in range(1, 31)]
        fluent = [P.simulate(seed=s, enemy_hp=self.TYPICAL_ENEMY_HP, damage=5,
                             accuracy=0.92) for s in range(1, 31)]
        sloppy_wins = [r for r in sloppy if r["outcome"] == "won"]
        fluent_wins = [r for r in fluent if r["outcome"] == "won"]
        self.assertTrue(fluent_wins)
        self.assertTrue(sloppy_wins, "the pouch should still rescue a weak player")

        sloppy_casts = sum(r["casts"] for r in sloppy_wins) / len(sloppy_wins)
        fluent_casts = sum(r["casts"] for r in fluent_wins) / len(fluent_wins)
        self.assertGreater(
            sloppy_casts, fluent_casts,
            "a full pouch must buy more typing, never less")
        # And it must be a large margin, not a rounding win. Measured at ~1.97x:
        # the potion-abuser writes twice as much Python to reach the same kill,
        # which is the feature working exactly as intended.
        self.assertGreater(sloppy_casts / fluent_casts, 1.5)

    def test_the_pouch_cannot_rescue_a_weak_player_from_a_boss(self):
        # Scale matters, and the pouch is deliberately not a boss strategy. At
        # boss HP the falloff and the carry caps run the bag dry long before
        # 45% accuracy gets there, so the only way through a boss is the Python.
        runs = [P.simulate(seed=s, enemy_hp=240, damage=5, accuracy=0.45,
                           pouch=P.full_pouch()) for s in range(1, 21)]
        self.assertEqual(sum(1 for r in runs if r["outcome"] == "won"), 0)

    def test_a_fluent_player_barely_opens_the_pouch(self):
        runs = [P.simulate(seed=s, damage=16, accuracy=0.92,
                           pouch=P.full_pouch()) for s in range(1, 21)]
        drunk = sum(r["potions_drunk"] for r in runs) / len(runs)
        self.assertLess(drunk, 2.0,
                        "potions are for the player who has not learned the "
                        "moveset yet")

    def test_no_amount_of_drinking_wins_a_fight_without_a_correct_cast(self):
        nothing = P.simulate(accuracy=0.0, pouch=P.full_pouch(), max_turns=200)
        self.assertNotEqual(nothing["outcome"], "won")
        self.assertGreater(nothing["enemy_hp_left"], 0)

    def test_the_wrong_element_with_an_empty_bag_is_still_winnable(self):
        # Learning never dead-ends, stated as a win rate rather than a bound.
        runs = [P.simulate(seed=s, damage=5, accuracy=0.92)
                for s in range(1, 41)]
        won = sum(1 for r in runs if r["outcome"] == "won")
        self.assertGreaterEqual(won, 36, "correct Python must beat a bad matchup")

    def test_elemental_disadvantage_lengthens_the_fight(self):
        matched = [P.simulate(seed=s, damage=16, accuracy=0.92)
                   for s in range(1, 21)]
        mismatched = [P.simulate(seed=s, damage=5, accuracy=0.92)
                      for s in range(1, 21)]
        m = sum(r["casts"] for r in matched) / len(matched)
        x = sum(r["casts"] for r in mismatched) / len(mismatched)
        self.assertGreater(x, m * 1.5)

    def test_the_disadvantage_the_pouch_models_is_one_the_wheel_can_produce(self):
        # potions.simulate() models a bad matchup as `damage=5` against a
        # matched `damage=16`. Those are magic numbers in a module that
        # deliberately does not import elements, so this is the seam where the
        # two files are checked against each other rather than against nothing.
        base = 10  # bestiary.BASE_DAMAGE
        counter = E.resolve_damage(base, E.FIRE,
                                   E.Defender(element=E.COLD)).damage
        floored = E.resolve_damage(
            base, E.COLD,
            E.Defender(element=E.COLD,
                       armour=E.ArmourProfile(points=0,
                                              resist={E.COLD: E.RESIST_CAP}))).damage
        self.assertEqual(counter, 15)
        self.assertEqual(floored, 5)
        self.assertLessEqual(abs(counter - 16), 1,
                             "the simulation's matched damage has drifted from "
                             "what an opposed hit actually deals")
        self.assertEqual(floored, 5,
                         "the simulation's disadvantaged damage has drifted "
                         "from the wheel's persistent floor")

    def test_potions_are_reachable_and_banded_by_area(self):
        self.assertTrue(P.available_at("GUIDED", kind="HEALTH"))
        self.assertFalse(P.found_at("health_hefty", "EASY"),
                         "a flagon must be something you carry out of an Elite room")
        self.assertTrue(P.found_at("health_hefty", "ELITE"))

    def test_drop_rates_never_fall_as_areas_get_deeper(self):
        for table in (P.POTION_DROP_CHANCE, P.CHEST_POTION_CHANCE,
                      P.MONSTER_ANTIDOTE_CHANCE):
            series = [table[t] for t in P.TIER_ORDER]
            self.assertEqual(series, sorted(series))

    def test_a_boss_always_hands_over_supplies_for_the_road(self):
        self.assertEqual(P.drop_chance(difficulty="BOSS", is_boss=True), 1.0)

    def test_an_unknown_affinity_biases_nothing_rather_than_raising(self):
        # The compatibility contract with whichever module owns the elements.
        rng = random.Random(4)
        pid = P.pick_potion(difficulty="HARD", affinity="chartreuse", rng=rng)
        self.assertIn(pid, P.POTION_IDS)

    def test_the_affinity_strings_potions_biases_on_are_real_elements(self):
        # potions.py takes affinity as a lowercase string and never imports the
        # element table. That decoupling is deliberate, so the names have to be
        # checked somewhere or a typo would silently disable a bias forever.
        for affinity in P.AFFINITY_BIAS:
            self.assertIn(affinity.upper(), E.ELEMENTS,
                          f"{affinity!r} is not an element on the wheel")
        for affinity in P.AFFINITY_FLAVOUR:
            self.assertIn(affinity.upper(), E.ELEMENTS)
        self.assertEqual(set(P.POISON_AFFINITIES), {E.POISON.lower()})


# ---------------------------------------------------------------------------
# 10. The two modules and the rest of the game still agree
# ---------------------------------------------------------------------------

class TestIntegrationContract(unittest.TestCase):

    def test_both_self_checks_pass(self):
        self.assertTrue(E.self_check()["ok"])
        self.assertTrue(P.self_check()["ok"])

    def test_the_bars_are_the_fields_the_save_file_already_uses(self):
        self.assertEqual(E.HEALTH_FIELD, "stamina")
        self.assertEqual(E.FOCUS_FIELD, "mana")
        self.assertEqual(P.POURS_INTO["HEALTH"], E.HEALTH_FIELD)
        self.assertEqual(P.POURS_INTO["FOCUS"], E.FOCUS_FIELD)

    def test_the_difficulty_ladder_has_not_drifted_from_items_py(self):
        from gauntlet import items
        self.assertEqual(set(P.TIER_ORDER), set(items.DIFFICULTY_DROP_CHANCE))

    def test_every_wiring_site_potions_names_actually_exists(self):
        from gauntlet import engine
        for attr in ("DEFAULT_STATE", "Encounter"):
            self.assertTrue(hasattr(engine, attr), f"engine.{attr} is gone")
        for attr in ("use_consumable", "_apply_outcome", "_encounter_payload",
                     "_write_encounter", "start_encounter", "submit", "effects"):
            self.assertTrue(hasattr(engine.Game, attr),
                            f"engine.Game.{attr} is gone")

    def test_the_new_effect_keys_are_declared_somewhere_a_player_can_read(self):
        # armour_points, armour_cap and the six resist_* keys were NEW when this
        # module was written, and items.py owns EFFECT_LABELS. The debt is paid:
        # all eight are declared, so the test now asserts the paid state rather
        # than the outstanding one. A key that vanishes from EFFECT_LABELS is a
        # tooltip that silently goes blank, which is what this catches.
        from gauntlet import items
        missing = [k for k in ("armour_points", "armour_cap")
                   + tuple(f"resist_{e.lower()}" for e in E.ELEMENTS)
                   if k not in items.EFFECT_LABELS]
        self.assertEqual(missing, [], "armour effect keys lost their labels")

    def test_armour_cap_is_a_best_of_rather_than_a_sum(self):
        """Two pieces of plate cap at plate's fraction, not at twice it.

        `armour_cap` is "the best points_cap you are wearing". Summed, four
        mail pieces would out-cap plate, which inverts the one decision the
        armour system exists to offer.
        """
        from gauntlet import items
        self.assertIn("armour_cap", items.SWITCH_KEYS)
        folded = items.total_effects({}, {}, {"armour_cap": 0.25})
        self.assertEqual(folded["armour_cap"], 0.25)

    def test_the_three_roads_are_all_equippable(self):
        """elements.py offers a choice between flat points, proportional
        resistance and a longer bar. A choice nobody can equip is a diagram."""
        from gauntlet import items
        plate = [i for i in items.CATALOGUE if i.effects.get("armour_points")]
        warded = [i for i in items.CATALOGUE
                  if any(k.startswith("resist_") for k in i.effects)]
        bars = [i for i in items.CATALOGUE
                if i.effects.get(E.HEALTH_EFFECT_KEY)
                or i.effects.get(E.FOCUS_EFFECT_KEY)]
        self.assertTrue(plate, "nothing in the game carries armour points")
        self.assertTrue(warded, "nothing in the game resists an element")
        self.assertTrue(bars, "nothing in the game lengthens a bar")
        # and every pair of boots elements.py describes is a real item, by the
        # id hazard_step will look up
        for boot in E.BOOTS:
            self.assertIn(boot.id, items.BY_ID, f"{boot.id} is not an item")
            self.assertEqual(items.BY_ID[boot.id].slot, "feet", boot.id)

    def test_the_pouch_has_its_own_save_key(self):
        self.assertEqual(P.POUCH_STATE_KEY, "potions")
        state: dict = {}
        pouch = P.Pouch()
        pouch.add("health_minor", 2)
        pouch.to_state(state)
        self.assertEqual(P.Pouch.from_state(state).count("health_minor"), 2)

    def test_a_save_from_a_future_build_does_not_crash_the_pouch(self):
        restored = P.Pouch.from_state({"potions": {"health_minor": 3,
                                                   "elixir_of_nothing": 9}})
        self.assertEqual(restored.count("health_minor"), 3)
        self.assertEqual(restored.total(), 3)

    def test_a_status_from_a_future_build_is_dropped_rather_than_raising(self):
        wheel = [E.StatusInstance("HAUNTED", 3), E.StatusInstance("POISONED", 4)]
        tick = E.tick_statuses(wheel, 20)
        self.assertEqual([s.id for s in wheel], ["POISONED"])
        self.assertGreater(tick["damage"], 0)

    def test_status_instances_round_trip_through_the_save_file(self):
        original = E.StatusInstance("POISONED", 4, 2)
        self.assertEqual(E.StatusInstance.from_dict(original.to_dict()), original)

    def test_poison_round_trips_through_the_save_file(self):
        poison = P.Poison()
        P.poison_apply(poison, damage=3, turns=2, source="marsh")
        restored = P.Poison.from_dict(poison.to_dict())
        self.assertEqual(restored.per_turn, poison.per_turn)
        self.assertEqual(len(restored.doses), len(poison.doses))

    def test_the_turn_state_round_trips_through_the_save_file(self):
        turn = P.new_fight()
        turn.sips["HEALTH"] = 2
        turn.drunk_this_turn = "health_minor"
        restored = P.TurnState.from_dict(turn.to_dict())
        self.assertEqual(restored.sips, turn.sips)
        self.assertFalse(restored.may_drink)


if __name__ == "__main__":
    unittest.main(verbosity=2)
