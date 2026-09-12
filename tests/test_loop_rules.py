"""The five rules the moveset/upkeep loop is only allowed to exist under.

Every claim here is one the brief made as a sentence and this suite turns into
arithmetic. None of them are spot checks of a constant: each drives the real
function against a real battle or a real hundred-encounter run, because a
constant can be correct while the system built on it is not.

  1. HARDER PYTHON HITS HARDER. Same move, same turn, same enemy: a better
     solution deals strictly more. This is the spine. If it inverts, nothing
     else in the file matters.
  2. THE REPAIR CEILING. Upkeep never eats more than a third of income, swept
     across every difficulty, every rank and a player taking a beating.
  3. NO DEAD ENDS. Broke, wrecked, poisoned, fainted companion: still able to
     fight, still able to get unstuck, still able to reach the healer, and not
     one coin required anywhere on that road.
  4. THE FADED-MOVE FLOOR. A rung-one move at the top of the tree is weaker and
     never zero, never removed, never uncastable.
  5. THE SEAL. No class bonus, no rank penalty, no healer, no repair and no
     companion reaches a measured run.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gauntlet import (classes, config, economy, elements, incantation,
                      movesets, pets, upkeep)


# ---------------------------------------------------------------------------
# 1. HARDER PYTHON HITS HARDER
# ---------------------------------------------------------------------------

class ComplexityIsTheSpine(unittest.TestCase):
    """The central mechanic, proved on one real problem rather than asserted."""

    # One incantation, STRIKE, and three genuinely different answers to the same
    # question: put a number in `total`. All three are correct Python and all
    # three pass all three layers. Only the third one is worth writing.
    MINIMAL = {"target": "total", "value": "len(nums)"}
    PLAIN = {"target": "total", "value": "sum(nums)"}
    BETTER = {"target": "total", "value": "sum(n for n in nums if n % 2 == 0)"}

    def cast(self, answers, tier=1):
        context = incantation.make_context(["total", "nums"])
        return incantation.cast("bind", answers, context, tier=tier)

    def test_all_three_are_legal_casts(self):
        for answers in (self.MINIMAL, self.PLAIN, self.BETTER):
            result = self.cast(answers)
            self.assertTrue(result.correct,
                            "%s was rejected at %s: %s"
                            % (answers["value"], result.layer, result.teaching))

    def test_the_better_solution_hits_harder(self):
        minimal = self.cast(self.MINIMAL)
        better = self.cast(self.BETTER)
        self.assertGreater(better.complexity_score, minimal.complexity_score)
        self.assertGreater(better.weight, minimal.weight)
        # Not a rounding difference. A reason to write the better line.
        self.assertGreaterEqual(better.damage, minimal.damage * 2,
                                "composed comprehension %d vs bare call %d"
                                % (better.damage, minimal.damage))

    def test_it_holds_at_every_tier_the_player_actually_types(self):
        inc = incantation.BY_ID["bind"]
        for tier in range(incantation.MAX_TIER + 1):
            if "value" not in incantation.authored_holes(inc, tier):
                continue
            minimal = self.cast(self.MINIMAL, tier=tier)
            better = self.cast(self.BETTER, tier=tier)
            self.assertGreater(better.damage, minimal.damage,
                               "tier %d inverted the incentive" % tier)

    def test_tier_zero_pays_the_same_because_the_game_wrote_the_line(self):
        """At GUIDED the value is printed on screen with one blank beside it.
        The player did not choose the comprehension, so it does not pay for one.
        This is the measure refusing to reward reading, and it is correct."""
        inc = incantation.BY_ID["bind"]
        self.assertNotIn("value", incantation.authored_holes(inc, 0))
        self.assertEqual(self.cast(self.BETTER, tier=0).damage,
                         self.cast(self.MINIMAL, tier=0).damage)

    def test_mastery_follows_the_same_spine(self):
        # The health bar and the skill number must agree about what just
        # happened, or one of them is lying to the player.
        minimal = self.cast(self.MINIMAL)
        better = self.cast(self.BETTER)
        self.assertGreater(better.skill_deltas[incantation.BY_ID["bind"].skill],
                           minimal.skill_deltas[incantation.BY_ID["bind"].skill])

    def test_no_multiplier_outside_incantation_can_invert_it(self):
        # movesets folds rank, groove and variety in multiplicatively and last.
        # Whatever they come to, the better line still wins.
        for scale in (0.1, 0.35, 1.0, 1.61, 4.0):
            context = incantation.make_context(["total", "nums"])
            minimal = incantation.cast("bind", self.MINIMAL, context, scale=scale)
            context = incantation.make_context(["total", "nums"])
            better = incantation.cast("bind", self.BETTER, context, scale=scale)
            self.assertGreater(better.damage, minimal.damage,
                               "scale %.2f inverted the incentive" % scale)

    def test_damage_never_falls_as_the_python_gets_harder(self):
        """Swept across every incantation in the game, not one of them."""
        for inc in incantation.CATALOGUE:
            run = []
            for score in range(0, 101, 5):
                weight = (incantation.WEIGHT_MIN
                          + (incantation.WEIGHT_MAX - incantation.WEIGHT_MIN)
                          * score / 100.0)
                measured = incantation.Complexity(score=score, weight=weight)
                damage, _, _ = incantation._damage_for(
                    inc, None, 1, 0, 0.0, False, complexity=measured)
                run.append(damage)
            self.assertEqual(run, sorted(run),
                             "%s pays less for harder Python somewhere: %s"
                             % (inc.id, run))

    def test_the_power_floor_is_a_floor_and_not_a_spine(self):
        """`inc.power` may keep a plain correct cast from being worthless. It may
        not flatten the curve: authoring a big number on a move must not be a way
        to make that move hit hard."""
        for inc in incantation.CATALOGUE:
            floor = inc.power * incantation.POWER_FLOOR_SHARE
            # The weight at which typing overtakes the floor. Everything above
            # it is decided by the line and nothing else.
            crossover = floor / incantation.DAMAGE_UNIT
            score_masked = max(0.0, (crossover - incantation.WEIGHT_MIN)
                               / (incantation.WEIGHT_MAX - incantation.WEIGHT_MIN))
            self.assertLess(score_masked, 0.05,
                            "%s: the power floor decides damage up to score %d"
                            % (inc.id, int(score_masked * 100)))

    def test_the_module_multipliers_cannot_outrun_the_typing(self):
        report = movesets.self_check()
        self.assertEqual(report["problems"], [])
        self.assertLess(report["module_span"], report["typing_span"])


# ---------------------------------------------------------------------------
# 2. THE REPAIR CEILING
# ---------------------------------------------------------------------------

class DurabilityIsNotATax(unittest.TestCase):

    def test_the_ceiling_holds_across_the_whole_grid(self):
        """Every difficulty x every rank x a player taking up to twelve hits."""
        table = upkeep._worst_player_table(wired=True)
        self.assertTrue(
            table["within"],
            "upkeep reaches %.1f%% of income at %s rank %s on %d hits"
            % (table["worst_share"] * 100, table["worst"]["difficulty"],
               table["worst"]["rank"], table["worst"]["hits"]))

    def hundred_encounters(self, difficulty, rank, hits):
        """The real loop: earn, wear, walk to the smith, pay, walk out.

        Returns (gold earned, gold the smith took including what is still
        outstanding at the end, number of visits).
        """
        state = {"upkeep": upkeep.new_state(), "armor": {}, "equipped": {}}
        upkeep.ensure(state)
        ledger, purse, earned, spent, visits = {}, 0, 0, 0, 0
        for index in range(100):
            award = economy.encounter_award(
                ledger, region_id="verdant", difficulty=difficulty, rank=rank,
                problem_id="p%d" % index)
            economy.record(ledger, award)
            earned += award.gold
            purse += award.gold
            upkeep.record_income(state, award.gold)
            upkeep.wear_encounter(
                state, difficulty=difficulty, hits_taken=hits,
                blows_landed=hits + 1,
                pay_scale=award.multipliers["taper"], gold_earned=award.gold)
            if min(upkeep.integrity(state, p) for p in upkeep.PIECES) < \
                    upkeep.REPAIR_ADVISED_AT:
                done = upkeep.repair(state, gold=purse)
                purse -= done.get("gold_spent", 0)
                spent += done.get("gold_spent", 0)
                visits += int(bool(done.get("ok")))
        # Settle anything still outstanding so the share is the whole bill and
        # not just the part that happened to fall inside a hundred encounters.
        outstanding = upkeep.repair_quote(state, gold=purse)["gold"]
        return earned, spent + outstanding, visits

    def test_a_hundred_encounters_of_ordinary_play(self):
        earned, bill, visits = self.hundred_encounters("MEDIUM", "B", 3)
        share = bill / earned
        self.assertLessEqual(share, upkeep.UPKEEP_INCOME_CEILING,
                             "repair took %.1f%% of %d gold over 100 encounters"
                             % (share * 100, earned))
        # And it is not zero either, or there was no reason to want gold.
        self.assertGreater(bill, 0)
        self.assertGreater(visits, 0)
        # A rhythm rather than an errand: the smith is a place you go now and
        # then, not a turnstile between encounters.
        self.assertLess(visits, 100 / 5)

    def test_a_hundred_encounters_of_having_a_bad_time(self):
        """The player this rule exists for: low rank, taking a beating."""
        for difficulty, rank, hits in (("EASY", "LEARNING_CLEAR", 3),
                                       ("MEDIUM", "LEARNING_CLEAR", 3),
                                       ("MEDIUM", "LEARNING_CLEAR", 8),
                                       ("MEDIUM", "C", 8),
                                       ("BOSS", "LEARNING_CLEAR", 6)):
            earned, bill, _ = self.hundred_encounters(difficulty, rank, hits)
            share = bill / earned
            self.assertLessEqual(
                share, upkeep.UPKEEP_INCOME_CEILING,
                "%s rank %s on %d hits: repair took %.1f%% of %d gold"
                % (difficulty, rank, hits, share * 100, earned))

    def test_a_struggling_player_is_not_billed_out_of_the_game(self):
        """Wear rises with how badly the fight went; income falls with it, so
        the two point in opposite directions exactly where they must not. The
        clamp is the only thing standing between that and a tax on being bad at
        Python."""
        purse = 24 * economy.RANK_PAY["LEARNING_CLEAR"]
        bad = upkeep.wear_points(difficulty="MEDIUM", hits_taken=12,
                                 blows_landed=13, gold_earned=purse)
        self.assertTrue(bad["clamped"], "the clamp never fired")
        self.assertLessEqual(bad["share_of_income"], upkeep.UPKEEP_INCOME_CEILING)
        # What it would have been without the clamp, so the size of the problem
        # is on the record rather than implied.
        unclamped = (upkeep.WEAR_TAKEN * upkeep._effective_hits(12)
                     + upkeep.WEAR_DEALT * 13 / upkeep.DEALT_WEAR_EVERY)
        self.assertGreater(unclamped * upkeep.REPAIR_GOLD_PER_POINT / purse,
                           upkeep.UPKEEP_INCOME_CEILING)

    def test_an_encounter_that_paid_nothing_wears_nothing(self):
        nothing = upkeep.wear_points(difficulty="BOSS", hits_taken=12,
                                     blows_landed=20, gold_earned=0)
        self.assertEqual(nothing["total"], 0.0)

    def test_wear_from_hits_saturates(self):
        """The twelfth hit of a fight may not cost what the first one did."""
        first = upkeep._effective_hits(upkeep.HITS_FULL_RATE)
        later = upkeep._effective_hits(upkeep.HITS_FULL_RATE * 3)
        self.assertLess(later / (upkeep.HITS_FULL_RATE * 3),
                        first / upkeep.HITS_FULL_RATE)
        # Still monotone: more hits is never less wear.
        run = [upkeep._effective_hits(n) for n in range(0, 20)]
        self.assertEqual(run, sorted(run))

    def test_quality_still_cancels_after_the_clamp(self):
        proof = upkeep._prove_quality_cancels()
        self.assertTrue(proof["cancels"], proof["rows"])

    def test_the_module_agrees_with_itself(self):
        report = upkeep.self_check()
        self.assertTrue(report["ok"], report["failures"])


# ---------------------------------------------------------------------------
# 3. NO DEAD ENDS
# ---------------------------------------------------------------------------

class LearningNeverDeadEnds(unittest.TestCase):
    """Zero gold, every piece at zero, a fainted pet, poisoned, mid-dungeon."""

    def setUp(self):
        self.statuses = [{"id": "POISONED", "turns": 6, "stacks": 3}]
        self.state = {
            "player": {"stamina": 3, "stamina_max": config.STAMINA_MAX,
                       "mana": 0, "mana_max": config.MANA_MAX, "gold": 0},
            "equipped": {}, "pets": pets.new_state()}
        upkeep.ensure(self.state)
        for piece in upkeep.PIECES:
            upkeep._set_integrity(self.state, piece, 0)
        pets.grant(self.state["pets"], pets.STARTER_ID)
        pets.set_active(self.state["pets"], [pets.STARTER_ID])
        pets.faint(self.state["pets"], pets.STARTER_ID)
        upkeep.pet_knock(self.state, pets.STARTER_ID,
                         hits=upkeep.PET_KNOCKS_TO_FAINT)

    def test_he_can_still_fight(self):
        """The starting four incantations, a wrecked kit, a real field."""
        moveset = incantation.new_moveset()
        context = incantation.make_context(
            ["seen", "counts"],
            support={"x": "5", "total": "0", "nums": "[3, 1, 4]"})
        answers = {
            "guard": lambda live: {"item": "x", "store": live},
            "mark": lambda live: {"store": "seen", "item": "x"},
            "bind": lambda live: {"target": "total", "value": "len(nums)"},
            "advance": lambda live: {"counter": live},
        }
        turns = 0
        while context.living() and turns < 200:
            turns += 1
            demand = incantation.next_demand(moveset, context)
            self.assertIsNotNone(
                demand, "no line was castable: that is a dead end in a fight")
            incantation.cast(demand["incantation"],
                             answers[demand["incantation"]](context.living()[0].name),
                             context, tier=1)
        self.assertFalse(context.living(),
                         "a wrecked player could not finish an ordinary field")

    def test_a_wrecked_kit_still_supplies_armour(self):
        full = elements.armour_profile("PLATE", points=8)
        worn = upkeep.wear_profile(full, self.state)
        self.assertGreater(worn.points, 0)
        self.assertEqual(upkeep.condition(self.state)["scale"],
                         upkeep.DEGRADED_FLOOR)

    def test_he_can_still_get_unstuck(self):
        gate = upkeep.pet_gate(self.state, pets.STARTER_ID, attempts=0)
        self.assertFalse(gate["speaks"], "a fainted companion is still talking")
        earned = upkeep.pet_gate(self.state, pets.STARTER_ID,
                                 attempts=upkeep._free_solution_after())
        self.assertTrue(earned["floor"],
                        "the worked solution is gated behind a conscious animal")
        # And the focus that buys the first two rungs comes back for free.
        after = upkeep.after_battle(self.state, statuses=self.statuses)
        self.assertGreaterEqual(after["focus"], upkeep.VOIDED_FOCUS_FLOOR)

    def test_repair_is_never_required_to_continue(self):
        quote = upkeep.repair_quote(self.state, gold=0)
        self.assertFalse(quote["affordable"])
        self.assertEqual(quote["partial"], [])
        # Nothing above was blocked by that. The kit is at the floor and stays
        # equipped, which is the whole escape hatch.
        proof = upkeep._prove_nothing_breaks()
        self.assertTrue(proof["still_equipped"])
        self.assertTrue(proof["never_below_floor"])

    def test_he_can_reach_the_healer_and_it_costs_nothing(self):
        healed = upkeep.heal(self.state, statuses=self.statuses)
        self.assertEqual(healed["gold_cost"], 0)
        self.assertNotEqual(upkeep.MENDER.free_because.strip(), "")
        self.assertEqual(healed["cured"], ["POISONED"])
        self.assertEqual(self.statuses, [])
        # upkeep keeps its own knock ledger beside pets.py's, and the healer
        # clears both. Free, because the walk was the price.
        self.assertEqual(healed["revived"], [pets.STARTER_ID])
        self.assertFalse(upkeep.is_fainted(self.state, pets.STARTER_ID))
        self.assertEqual(self.state["player"]["stamina"],
                         self.state["player"]["stamina_max"])
        # The armour is still at zero. He was never made to pay for the walk.
        self.assertEqual(
            [upkeep.integrity(self.state, p) for p in upkeep.PIECES],
            [0] * len(upkeep.PIECES))
        self.assertEqual(self.state["player"]["gold"], 0)

    def test_the_companion_wakes_for_free_too(self):
        revived = pets.heal_all(self.state["pets"])
        self.assertEqual(pets.HEAL_COST_GOLD, 0)
        self.assertFalse(pets.is_down(self.state["pets"], pets.STARTER_ID),
                         revived)


# ---------------------------------------------------------------------------
# 4. THE FADED-MOVE FLOOR
# ---------------------------------------------------------------------------

class OldMovesFadeAndStillWork(unittest.TestCase):

    RUNG_ONE = "measured_strike"
    ANSWERS = [{"size": "size", "seq": "nums"}]

    def book(self, whole_tree):
        book = movesets.new_book("analyst")
        if whole_tree:
            for move in movesets.for_class("analyst"):
                movesets.learn(book, move.id)
        else:
            movesets.learn(book, self.RUNG_ONE)
        return book

    def volley(self, book):
        context = incantation.make_context(["nums"], support={"size": "0"})
        return movesets.resolve_move(self.RUNG_ONE, self.ANSWERS, context,
                                     book=book)

    def test_the_curve_never_reaches_zero(self):
        for reach in range(1, movesets.MAX_RUNG + 1):
            self.assertGreaterEqual(movesets.fade(1, reach), movesets.FADE_FLOOR)
        self.assertGreater(movesets.FADE_FLOOR, 0.0)
        # The curve arrives at the floor at the last rung rather than crossing
        # it early, which is what makes the whole game one continuous dimming.
        self.assertAlmostEqual(movesets.fade(1, movesets.MAX_RUNG),
                               movesets.FADE_FLOOR, delta=0.01)

    def test_the_curve_is_monotone_and_has_no_cliff(self):
        run = [movesets.fade(1, r) for r in range(1, movesets.MAX_RUNG + 1)]
        self.assertEqual(run, sorted(run, reverse=True))
        steps = [run[i] / run[i + 1] for i in range(len(run) - 2)]
        self.assertLess(max(steps), 1.35, "a rung drops off a cliff: %s" % run)

    def test_weaker_at_the_top_of_the_tree_never_gone(self):
        early = self.volley(self.book(False))
        late = self.volley(self.book(True))
        self.assertEqual(movesets.reach_of(self.book(True)), movesets.MAX_RUNG)
        self.assertLess(late.dealt, early.dealt)
        self.assertGreater(late.dealt, 0, "a rung-one move expired")
        self.assertTrue(late.correct, "a faded move stopped landing")

    def test_it_is_never_removed_from_the_book(self):
        book = self.book(True)
        self.assertIn(self.RUNG_ONE, book["known"])
        self.assertIn(self.RUNG_ONE, book["equipped"])
        self.assertIn(self.RUNG_ONE, movesets.BY_ID)
        context = incantation.make_context(["nums"], support={"size": "0"})
        ok, why = movesets.castable(self.RUNG_ONE, context)
        self.assertTrue(ok, why)

    def test_a_faded_move_still_pays_mastery(self):
        late = self.volley(self.book(True))
        self.assertTrue(late.skill_deltas)
        self.assertTrue(all(value > 0 for value in late.skill_deltas.values()))

    def test_a_faded_move_still_rewards_better_python(self):
        """The fade is a multiplier on the typing, so the ratio survives it."""
        faded = movesets.scale_for(self.book(True), self.RUNG_ONE)["total"]
        context = incantation.make_context(["total", "nums"])
        lazy = incantation.cast("bind", {"target": "total", "value": "len(nums)"},
                                context, scale=faded)
        context = incantation.make_context(["total", "nums"])
        good = incantation.cast(
            "bind", {"target": "total", "value": "sum(n for n in nums if n % 2 == 0)"},
            context, scale=faded)
        self.assertGreater(good.damage, lazy.damage)


# ---------------------------------------------------------------------------
# 5. THE SEAL
# ---------------------------------------------------------------------------

class TheSeal(unittest.TestCase):

    def decorated_book(self):
        book = movesets.new_book("analyst")
        for move in movesets.for_class("analyst"):
            movesets.learn(book, move.id)
        book["casts"] = {m.id: 40 for m in movesets.for_class("analyst")}
        book["last"] = "stated_case"
        return book

    def test_no_moveset_bonus_survives(self):
        book = self.decorated_book()
        for move_id in ("falsified_map", "measured_strike"):
            open_scale = movesets.scale_for(book, move_id)["total"]
            sealed = movesets.scale_for(book, move_id, sealed=True)
            self.assertNotEqual(open_scale, movesets.SEALED_SCALE,
                                "%s had no bonus to seal in the first place"
                                % move_id)
            self.assertEqual(sealed["total"], movesets.SEALED_SCALE)

    def test_an_interview_context_seals_it_without_the_keyword(self):
        """The guard rail: a caller who forgot cannot smuggle a bonus in."""
        book = self.decorated_book()
        context = incantation.make_context(["nums"], support={"size": "0"},
                                           mode="interview")
        volley = movesets.resolve_move("measured_strike",
                                       [{"size": "size", "seq": "nums"}],
                                       context, book=book)
        self.assertTrue(volley.sealed)
        self.assertEqual(volley.scale, movesets.SEALED_SCALE)
        self.assertTrue(volley.correct, "the seal stopped the move landing")

    def test_damage_in_a_measured_run_is_the_typing_and_nothing_else(self):
        book = self.decorated_book()
        for answers, label in (
                ({"target": "total", "value": "len(nums)"}, "minimal"),
                ({"target": "total", "value": "sum(n for n in nums if n % 2 == 0)"},
                 "better")):
            context = incantation.make_context(["total", "nums"], mode="interview")
            sealed = incantation.cast(
                "bind", answers, context,
                scale=movesets.scale_for(book, "measured_strike", sealed=True)["total"])
            self.assertEqual(sealed.scale, 1.0, label)

    def test_the_seal_cuts_both_ways(self):
        """A player whose only move is faded does not carry that into the exam."""
        book = self.decorated_book()
        self.assertLess(movesets.scale_for(book, "measured_strike")["total"], 1.0)
        self.assertEqual(
            movesets.scale_for(book, "measured_strike", sealed=True)["total"], 1.0)

    def test_no_healer_no_repair_no_wear_in_a_measured_run(self):
        state = {"player": {"stamina": 1, "stamina_max": 20,
                            "mana": 0, "mana_max": 30}, "equipped": {}}
        upkeep.ensure(state)
        for piece in upkeep.PIECES:
            upkeep._set_integrity(state, piece, 40)
        self.assertEqual(upkeep.heal(state, sealed=True).get("error"), "sealed")
        self.assertEqual(upkeep.repair(state, gold=999, sealed=True).get("error"),
                         "sealed")
        self.assertEqual(
            upkeep.repair_quote(state, gold=999, sealed=True).get("error"),
            "sealed")
        worn = upkeep.wear_encounter(state, difficulty="BOSS", hits_taken=9,
                                     blows_landed=12, sealed=True)
        self.assertFalse(worn["applied"])
        self.assertEqual([upkeep.integrity(state, p) for p in upkeep.PIECES],
                         [40] * len(upkeep.PIECES))
        # And health is untouched: an exam that healed you would be an exam that
        # told you how you were doing.
        self.assertEqual(state["player"]["stamina"], 1)

    def test_no_companion_speaks_in_a_measured_run(self):
        self.assertFalse(pets.available_in("interview"))
        self.assertFalse(pets.available_in("adventure", "python_village",
                                           sealed=True))
        self.assertFalse(pets.party_effects(list(pets.PET_IDS), {}, "interview"))

    def test_the_capability_is_the_one_finalexam_names(self):
        from gauntlet import finalexam
        self.assertIn(upkeep.UPKEEP_CAPABILITY, finalexam.ALL_CRUTCHES)


# ---------------------------------------------------------------------------
# 6. MULTI-ENEMY FIGHTS TERMINATE
# ---------------------------------------------------------------------------

class WorstCaseFightsTerminate(unittest.TestCase):
    """Several enemies, the wrong element, the weakest move, faded to the floor.

    The requirement is not that this is pleasant. It is that it is LONGER and
    never unwinnable, because a longer fight is more typing and more typing is
    the thing the whole game wanted.
    """

    MOVE = "measured_strike"

    def field(self, count):
        return incantation.BattleContext(
            enemies=[incantation.spawn(k)
                     for k in ("nums", "stack", "dp")[:count]],
            support={"size": "0"})

    def run_fight(self, count, whole_tree, cap=1000):
        book = movesets.new_book("analyst")
        if whole_tree:
            for move in movesets.for_class("analyst"):
                movesets.learn(book, move.id)
        else:
            movesets.learn(book, self.MOVE)
        context = self.field(count)
        move = movesets.BY_ID[self.MOVE]
        # The wrong element, hard: the defender resists what this class throws.
        armour = elements.armour_profile("PLATE", points=8,
                                         element=move.element, resist=0.6)
        defender = elements.Defender(element=move.element, armour=armour,
                                     max_health=100)

        def deliver(name, base, step):
            enemy = context.enemy(name)
            if enemy is None or not enemy.alive:
                return 0
            landed = max(1, int(elements.resolve_damage(
                base, move.element, defender).damage))
            before = enemy.hp
            enemy.hp = max(0, enemy.hp - landed)
            return before - enemy.hp

        turns = 0
        while context.living() and turns < cap:
            turns += 1
            target = context.living()[0].name
            volley = movesets.resolve_move(
                self.MOVE, [{"size": "size", "seq": target}], context,
                book=book, primary=target, deliver=deliver)
            movesets.record(book, volley)
            self.assertFalse(volley.refused, volley.refusal)
            self.assertGreater(volley.dealt, 0,
                               "turn %d made no progress at all" % turns)
        return turns, not context.living()

    def test_it_terminates_with_one_enemy(self):
        turns, cleared = self.run_fight(1, whole_tree=False)
        self.assertTrue(cleared)

    def test_more_enemies_is_longer_and_still_finite(self):
        lengths = [self.run_fight(n, whole_tree=False)[0] for n in (1, 2, 3)]
        for count, (turns, cleared) in zip((1, 2, 3),
                                           [(t, True) for t in lengths]):
            self.assertTrue(cleared, "%d enemies was unwinnable" % count)
        self.assertEqual(lengths, sorted(lengths))
        self.assertGreater(lengths[-1], lengths[0])

    def test_the_worst_case_of_all_still_ends(self):
        """Faded to the floor, wrong element, three of them."""
        turns, cleared = self.run_fight(3, whole_tree=True)
        self.assertTrue(cleared, "the worst legal fight in the game hangs")
        # Longer than the same fight with a fresh move, which is the price of
        # never having invested in anything newer.
        fresh, _ = self.run_fight(3, whole_tree=False)
        self.assertGreater(turns, fresh)

    def test_a_refused_move_costs_nothing(self):
        """Demanding a STORM of a player facing one monster is a trick, and this
        game does not charge for trick questions."""
        storm = movesets.at_rung("analyst", 7)
        self.assertEqual(storm.shape, movesets.STORM)
        context = self.field(1)
        volley = movesets.resolve_move(storm.id, [], context)
        self.assertTrue(volley.refused)
        self.assertEqual(volley.focus, 0)
        self.assertEqual(volley.dealt, 0)
        self.assertEqual(context.enemies[0].hp, context.enemies[0].hp_max)

    def test_area_buys_turns_and_not_raw_damage(self):
        report = movesets.self_check()
        for row in report["area_price"]:
            self.assertLessEqual(row["vs_singles"], 1.60, row)

    def test_nothing_but_typing_can_land_a_blow(self):
        """An empty answer list is a wasted turn, not a free one."""
        context = self.field(3)
        before = [e.hp for e in context.enemies]
        volley = movesets.resolve_move(self.MOVE, [], context)
        self.assertFalse(volley.refused, volley.refusal)
        self.assertTrue(volley.wasted, volley.lines)
        self.assertEqual(volley.dealt, 0)
        self.assertEqual([e.hp for e in context.enemies], before)

    def test_a_half_written_volley_keeps_what_it_wrote(self):
        """Miss the second line of a CLEAVE and you keep the first. A player who
        wrote one correct line out of two did not waste the turn."""
        cleave = movesets.at_rung("analyst", 3)
        self.assertEqual(cleave.shape, movesets.CLEAVE)
        context = incantation.make_context(
            ["seen", "counts"], support={"x": "5", "out": "0", "k": "'a'"})
        ok, why = movesets.castable(cleave, context)
        self.assertTrue(ok, why)
        volley = movesets.resolve_move(
            cleave.id,
            [{"item": "x", "store": "seen"}, {}],   # second line left blank
            context, primary="seen")
        self.assertTrue(volley.partial, volley.lines)
        self.assertGreater(volley.dealt, 0)
        self.assertEqual(len(volley.landed), 1)
        self.assertEqual(len(volley.missed), 1)


# ---------------------------------------------------------------------------
# 7. EVERYTHING STILL AGREES WITH EVERYTHING ELSE
# ---------------------------------------------------------------------------

class ModulesAgree(unittest.TestCase):

    def test_every_self_check_passes(self):
        for name, report in (("movesets", movesets.self_check()),
                             ("upkeep", upkeep.self_check()),
                             ("pets", pets.self_check()),
                             ("classes", classes.self_check())):
            problems = report.get("problems") or report.get("failures") or []
            self.assertEqual(problems, [], "%s: %s" % (name, problems))

    def test_the_tree_is_the_only_place_a_move_comes_from(self):
        for move in movesets.CATALOGUE:
            self.assertTrue(classes.node_for_moveset(move.id),
                            "%s is not granted by any skill node" % move.id)

    def test_learning_a_move_teaches_its_lines(self):
        book = movesets.new_book("analyst")
        moveset = incantation.new_moveset()
        movesets.learn(book, "falsified_map", moveset)
        for inc_id in movesets.BY_ID["falsified_map"].spine:
            self.assertTrue(incantation.is_known(moveset, inc_id), inc_id)

    def test_reach_is_read_off_the_tree_not_the_level(self):
        state = {"class": "analyst", "spent": {}}
        self.assertEqual(classes.moveset_reach(state), 0)
        node = classes.node_for_moveset("measured_strike")
        state["spent"][node] = classes.MOVE_GRANT_RANK
        self.assertEqual(classes.moveset_reach(state), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
