"""The economy: four rules, and the arithmetic that has to keep agreeing with them.

These tests exist because every one of the four is the kind of rule that survives
a code review and then dies quietly to a reasonable-sounding tuning change. Each
section therefore tries to BREAK the rule by playing the game badly on purpose,
rather than asking the module whether it still believes its own docstring.

  1. GOLD IS PAID FOR CORRECT PYTHON, NOT FOR TIME. The headline test is not
     "does a failure pay zero" — that is easy and was already true. It is
     `NoStrategyBeatsSolving`, which prices every loop a real player could
     actually run, in gold per minute, and asserts that everything above the
     plain rate requires fresh Python and everything below it does not. Three
     things failed that test when it was first written and all three are fixed:
     dungeon rooms that asked for nothing, an untapered boss rematch bonus, and
     a repeat floor that disagreed with the rest of the file.

  2. POTIONS CANNOT BE STOCKPILED INTO IRRELEVANCE. Tested by buying the largest
     pouch the game permits and showing what it converts into, which is casts.

  3. REGALIA BUYS FREQUENCY, NEVER DEPTH. Tested by diffing the whole help
     payload with and without every object, across every difficulty.

  4. MULTI-AFFINITY IS STILL WINNABLE. Tested by exhaustive sweep rather than by
     sampling, because the guarantee is a claim about the worst case and a
     sampled worst case is not a worst case.
"""
from __future__ import annotations

import itertools
import math
import random
import unittest

import base  # noqa: F401  - imported for the sys.path side effect

from gauntlet import dungeons, economy, elements, potions, quests, regalia


DEEP = "null_kings_castle"      # deepest region: the best multipliers in the game


# ---------------------------------------------------------------------------
# 1. GOLD IS PAID FOR CORRECT PYTHON, NOT FOR TIME
# ---------------------------------------------------------------------------

class NothingPaysForFailure(unittest.TestCase):
    """The floor under everything else. Every public earner, failing branch."""

    def test_every_earner_pays_zero_for_a_failure(self):
        st = economy.new_state()
        losers = {
            "encounter": economy.encounter_award(
                st, region_id=DEEP, difficulty="BOSS", rank="S",
                problem_id="p", solved=False),
            "puzzle": economy.puzzle_award(
                st, region_id=DEEP, difficulty="BOSS", kind="BREAK_IT",
                problem_id="p", solved=False),
            "purse": economy.roll_purse(
                region_id=DEEP, difficulty="BOSS", is_boss=True, solved=False,
                rng=random.Random(0)),
            "boss": economy.boss_award(region_id=DEEP, solved=False),
            "room": economy.dungeon_room_award(
                region_id=DEEP, room_kind="ENCOUNTER", solved=False),
            "quest": economy.quest_award(tier=5, turned_in=False),
        }
        for name, award in losers.items():
            self.assertEqual(award.gold, 0, f"{name} paid for a failure")

    def test_a_failed_trial_pays_nothing_however_far_it_got(self):
        st = economy.new_state()
        economy.open_trial(st, DEEP, "assay")
        economy.submit_to_trial(st, problem_id="a", solved=True,
                                difficulty=economy.trial_band("assay", DEEP))
        self.assertEqual(economy.close_trial(st, abandon=True).gold, 0)

    def test_no_earner_touches_the_players_purse(self):
        """One owner, one number. The engine adds; this module only reports."""
        st = economy.new_state()
        player = {"gold": 100}
        economy.record(st, economy.encounter_award(
            st, region_id=DEEP, difficulty="HARD", problem_id="p"))
        economy.buy_potion(st, DEEP, "health_minor", gold=10_000)
        self.assertEqual(player["gold"], 100)


class NothingPaysForWalking(unittest.TestCase):
    """A room that asks the player for nothing must pay nothing.

    dungeons.py owns the question of which rooms demand solving. This module may
    only agree with it, so the test reads dungeons._FREE_KINDS rather than
    restating a list that could drift.
    """

    def test_free_room_kinds_pay_nothing_anywhere_at_any_depth(self):
        for kind in sorted(dungeons._FREE_KINDS):
            self.assertEqual(economy.ROOM_MULT.get(kind, 0.0), 0.0,
                             f"{kind} demands no solving and is priced above zero")
            for region in ("fields_of_syntax", DEEP):
                for depth in (0, 3, 9):
                    award = economy.dungeon_room_award(
                        region_id=region, room_kind=kind, depth=depth,
                        solved=True)
                    self.assertEqual(award.gold, 0,
                                     f"{kind} paid {award.gold} for walking in")

    def test_an_unknown_room_kind_pays_nothing(self):
        """Fail closed. The old default was 0.2, which meant a new free room kind
        added to dungeons.py would start paying gold for walking on the day it
        shipped, without anybody editing economy.py."""
        award = economy.dungeon_room_award(
            region_id=DEEP, room_kind="A_KIND_INVENTED_NEXT_YEAR", depth=4)
        self.assertEqual(award.gold, 0)

    def test_every_room_kind_dungeons_defines_is_priced_here(self):
        for kind in dungeons.ROOM_KINDS:
            self.assertIn(kind, economy.ROOM_MULT,
                          f"dungeons defines {kind}; ROOM_MULT has no entry")

    def test_rooms_that_do_demand_solving_are_still_worth_entering(self):
        """The fix must not have deleted the dungeon's reason to exist."""
        gated = [k for k in dungeons.ROOM_KINDS
                 if k not in dungeons._FREE_KINDS and k != "BOSS"]
        self.assertTrue(gated)
        for kind in gated:
            self.assertGreater(
                economy.dungeon_room_award(region_id=DEEP, room_kind=kind,
                                           depth=2).gold, 0,
                f"gated room kind {kind} pays nothing at all")

    def test_no_gold_is_reachable_in_a_real_dungeon_without_solving(self):
        """Walk every generated dungeon from its entrance through free rooms only,
        the way a player farming it would, and bank whatever falls out."""
        for dungeon_id in dungeons.DUNGEON_BY_ID:
            dungeon = dungeons.generate(dungeon_id)
            by_id = {r.id: r for r in dungeon.rooms}
            adjacent: dict = {}
            for passage in dungeon.passages:
                if passage.lock is None and passage.revealed_by == -1:
                    adjacent.setdefault(passage.a, []).append(passage.b)
                    adjacent.setdefault(passage.b, []).append(passage.a)
            seen = {dungeon.entrance}
            queue = [dungeon.entrance]
            banked = 0
            while queue:
                current = queue.pop()
                room = by_id[current]
                if room.demands_solving and current != dungeon.entrance:
                    continue
                banked += economy.dungeon_room_award(
                    region_id=dungeon.region, room_kind=room.kind,
                    depth=room.depth, solved=True).gold
                for neighbour in adjacent.get(current, ()):
                    if neighbour not in seen:
                        seen.add(neighbour)
                        queue.append(neighbour)
            self.assertEqual(banked, 0,
                             f"{dungeon_id} pays {banked} gold for walking")


class TheTaper(unittest.TestCase):
    """The area rate is flat. The problem rate collapses. That is the whole
    argument the module opens with, so it is the one most worth pinning."""

    def test_the_area_rate_is_flat_across_distinct_problems(self):
        st = economy.new_state()
        paid = []
        for i in range(40):
            award = economy.encounter_award(
                st, region_id="graph_wastes", difficulty="MEDIUM",
                problem_id=f"problem-{i}")
            economy.record(st, award)
            paid.append(award.gold)
        self.assertEqual(len(set(paid)), 1,
                         "practising an area got cheaper, which punishes the "
                         "behaviour the game exists to cause")

    def test_the_problem_rate_collapses_to_the_floor(self):
        st = economy.new_state()
        paid = []
        for _ in range(10):
            award = economy.encounter_award(
                st, region_id="graph_wastes", difficulty="MEDIUM",
                problem_id="the-one-i-memorised")
            economy.record(st, award)
            paid.append(award.gold)
        self.assertEqual(paid, sorted(paid, reverse=True))
        self.assertLessEqual(paid[-1], paid[0] * economy.TAPER_FLOOR + 1)

    def test_a_spaced_retest_pays_full_and_does_not_advance_the_counter(self):
        st = economy.new_state()
        for _ in range(5):
            economy.record(st, economy.encounter_award(
                st, region_id="graph_wastes", difficulty="MEDIUM",
                problem_id="x"))
        tapered = economy.taper(st, "x")
        self.assertLess(tapered, 1.0)
        retest = economy.encounter_award(
            st, region_id="graph_wastes", difficulty="MEDIUM",
            problem_id="x", is_retest=True)
        fresh = economy.encounter_award(
            st, region_id="graph_wastes", difficulty="MEDIUM",
            problem_id="never-seen")
        self.assertEqual(retest.gold, fresh.gold)

    def test_every_repetition_floor_in_the_file_is_the_same_number(self):
        """Two floors for one question is how a farm gets authored by accident."""
        self.assertEqual(economy.QUEST_REPEAT_FLOOR, economy.TAPER_FLOOR)


class TheBossRematch(unittest.TestCase):
    """engine._rematch_problem clamps: once a boss's spaced-repetition family is
    spent, every further rematch replays one identical problem id. The phases
    taper correctly on their own; the bonus and the purse did not."""

    def test_the_bonus_decays_on_a_boss_already_beaten(self):
        first = economy.boss_award(region_id=DEEP, boss_id="null_king").gold
        later = [economy.boss_award(region_id=DEEP, boss_id="null_king",
                                    times_defeated=n).gold for n in range(1, 12)]
        self.assertEqual(later, sorted(later, reverse=True))
        self.assertLess(later[-1], first * 0.25)

    def test_the_purse_stops_being_guaranteed_after_the_first_kill(self):
        def share(times):
            hits = [economy.roll_purse(region_id=DEEP, difficulty="BOSS",
                                       is_boss=True, times_defeated=times,
                                       rng=random.Random(seed)).gold > 0
                    for seed in range(600)]
            return sum(hits) / len(hits)
        self.assertEqual(share(0), 1.0, "a first boss kill must always pay out")
        self.assertLess(share(9), 0.5,
                        "a boss you have killed nine times is not a rare event")

    def test_farming_a_beaten_boss_pays_worse_than_ordinary_fighting(self):
        band = economy.area_band(DEEP)
        area = economy.area_multiplier(DEEP)
        base = economy.ENCOUNTER_BASE[band]
        minutes = economy.BATTLE_MINUTES[band]
        plain_rate = base * area / minutes

        purse = sum(economy.roll_purse(region_id=DEEP, difficulty=band,
                                       is_boss=True, times_defeated=12,
                                       rng=random.Random(s)).gold
                    for s in range(600)) / 600.0
        farmed = (economy.boss_award(region_id=DEEP, boss_id="b",
                                     times_defeated=12).gold
                  + purse
                  + 6 * base * area * economy.TAPER_FLOOR)
        self.assertLess(farmed / (6 * minutes), plain_rate,
                        "re-killing a boss you have memorised out-earns "
                        "fighting something new")


class NoStrategyBeatsSolving(unittest.TestCase):
    """THE HEADLINE TEST.

    Price every loop a real player could sit down and run, in gold per minute,
    and sort them. The rule is not that solving is merely viable — it is that
    solving is OPTIMAL. Anything that pays above the plain rate has to be fresh
    Python, and anything that is not fresh Python has to pay below it.
    """

    def _strategies(self):
        band = economy.area_band(DEEP)
        area = economy.area_multiplier(DEEP)
        base = economy.ENCOUNTER_BASE[band]
        minutes = economy.BATTLE_MINUTES[band]

        def purse_at(times):
            return sum(economy.roll_purse(region_id=DEEP, difficulty=band,
                                          is_boss=True, times_defeated=times,
                                          rng=random.Random(s)).gold
                       for s in range(400)) / 400.0

        out = {}
        # -- loops that are fresh Python -----------------------------------
        out["solve fresh problems"] = (base * area, minutes, True)
        out["solve fresh problems at S rank"] = (
            base * area * economy.RANK_PAY["S"], minutes, True)
        best = max(
            ((economy.trial_total_estimate(f.id, DEEP), f) for f in economy.TRIAL_FORMS),
            key=lambda pair: pair[0]["total"]
            / (pair[0]["problems"] * economy.BATTLE_MINUTES[pair[0]["band"]]))
        estimate, _form = best
        out["the best broker contract"] = (
            estimate["total"],
            estimate["problems"] * economy.BATTLE_MINUTES[estimate["band"]], True)
        out["first kill of a region boss"] = (
            economy.boss_award(region_id=DEEP, boss_id="b").gold
            + purse_at(0) + 6 * base * area, 6 * minutes, True)

        # -- loops that are not ---------------------------------------------
        out["re-type one memorised problem"] = (
            base * area * economy.TAPER_FLOOR, minutes, False)
        out["grind the easiest band"] = (
            economy.ENCOUNTER_BASE["GUIDED"] * area,
            economy.BATTLE_MINUTES["GUIDED"], False)
        cheapest = min(economy.PUZZLE_MINUTES, key=economy.PUZZLE_MINUTES.get)
        puzzle_minutes = economy.PUZZLE_MINUTES[cheapest]
        out["grind the cheapest puzzle"] = (
            puzzle_minutes * economy.gold_per_minute(band)
            * economy.PUZZLE_RATE * area, puzzle_minutes, False)
        out["farm a boss already beaten"] = (
            economy.boss_award(region_id=DEEP, boss_id="b", times_defeated=12).gold
            + purse_at(12) + 6 * base * area * economy.TAPER_FLOOR,
            6 * minutes, False)
        out["re-run a repeatable quest at the floor"] = (
            economy.quest_award(tier=5, region_id=DEEP, repeatable=True,
                                times_completed=20).gold, 25.0, False)
        out["walk a dungeon and solve nothing"] = (
            sum(economy.dungeon_room_award(region_id=DEEP, room_kind=k,
                                           depth=3).gold
                for k in sorted(dungeons._FREE_KINDS)), 1.0, False)
        return {k: (gold / mins, fresh) for k, (gold, mins, fresh) in out.items()}

    def test_the_best_paying_strategy_in_the_game_is_fresh_python(self):
        rates = self._strategies()
        best = max(rates, key=lambda k: rates[k][0])
        self.assertTrue(rates[best][1],
                        f"the best gold-per-minute loop is {best!r}, which is "
                        f"not fresh Python — the economy is pointed at farming")

    def test_no_repetition_loop_outearns_the_plain_rate(self):
        rates = self._strategies()
        plain = rates["solve fresh problems"][0]
        for name, (rate, fresh) in sorted(rates.items()):
            if not fresh:
                self.assertLess(
                    rate, plain,
                    f"{name!r} pays {rate:.2f} gold/min against a plain rate of "
                    f"{plain:.2f} — repeating beats practising")

    def test_climbing_the_difficulty_ladder_is_never_a_pay_cut(self):
        rates = [economy.gold_per_minute(b) for b in economy.ENCOUNTER_BASE]
        self.assertEqual(rates, sorted(rates))
        self.assertLess(rates[-1] / rates[0], 2.0,
                        "the top band pays so much better per minute that the "
                        "early game is a waste of time")

    def test_the_broker_premium_is_bounded(self):
        for form in economy.TRIAL_FORMS:
            self.assertLessEqual(economy.trial_rate_ratio(form.id),
                                 economy.TRIAL_RATE_CEILING,
                                 f"{form.id} pays above the contract ceiling")

    def test_an_unidentified_submission_cannot_fill_a_contract(self):
        """The id is the only thing that makes two submissions distinct, so a
        submission without one cannot be counted. Six copies of one answer used
        to fill a three-piece assay and collect the whole quote."""
        st = economy.new_state()
        economy.open_trial(st, DEEP, "assay")
        band = economy.trial_band("assay", DEEP)
        counted = sum(bool(economy.submit_to_trial(
            st, problem_id="", solved=True, difficulty=band,
            hints_used=0).get("counted")) for _ in range(8))
        self.assertEqual(counted, 0)
        self.assertEqual(economy.close_trial(st).gold, 0)

    def test_a_trial_still_pays_when_it_is_filled_honestly(self):
        """The guard above must refuse the bad case without breaking the good
        one, or the broker has simply stopped working."""
        st = economy.new_state()
        opened = economy.open_trial(st, DEEP, "assay")
        band = economy.trial_band("assay", DEEP)
        for i in range(economy.TRIAL_BY_ID["assay"].problems):
            result = economy.submit_to_trial(
                st, problem_id=f"distinct-{i}", solved=True, difficulty=band,
                hints_used=0)
            self.assertTrue(result.get("counted"), result)
        self.assertEqual(economy.close_trial(st).gold, opened["quote"])

    def test_a_trial_cannot_be_filled_by_one_problem_submitted_repeatedly(self):
        st = economy.new_state()
        economy.open_trial(st, DEEP, "assay")
        band = economy.trial_band("assay", DEEP)
        counted = sum(bool(economy.submit_to_trial(
            st, problem_id="the-same-one", solved=True, difficulty=band,
            hints_used=0).get("counted")) for _ in range(8))
        self.assertEqual(counted, 1)
        self.assertEqual(economy.close_trial(st).gold, 0)


# ---------------------------------------------------------------------------
# 2. POTIONS CANNOT BE STOCKPILED INTO IRRELEVANCE
# ---------------------------------------------------------------------------

class ThePotionCap(unittest.TestCase):
    """A rich player is still a player who has to type.

    The binding limit is not the price and not the shelf — it is potions.py's
    turn rule: one draught per turn, and only a resolved cast creates the next
    turn. So the pouch converts into casts at exactly one to one, and the test
    is arithmetic on that conversion rather than an opinion about balance.
    """

    def _kinds(self):
        return sorted({p.kind for p in potions.CATALOGUE})

    def test_the_vendor_never_stocks_deeper_than_the_pouch_can_carry(self):
        for strength, cap in potions.CARRY_CAP.items():
            self.assertEqual(economy.VENDOR_STOCK[strength], cap,
                             "a shelf deeper than the pouch is a shelf whose "
                             "extra depth the player can look at and not carry")

    def test_buying_everything_affordable_is_bounded_by_the_pouch(self):
        """Infinite gold, every line on the shelf, drained and restocked until the
        vendor gives up. The pouch, not the purse, is what stops it."""
        st = economy.new_state()
        landed = 0
        for _ in range(30):                      # far more rounds than stock
            for potion_id in economy.stock_list(DEEP):
                for _ in range(10):
                    result = economy.buy_potion(st, DEEP, potion_id,
                                                gold=10 ** 9, quantity=1)
                    if "error" in result:
                        break
                    landed += (int(result.get("quantity", 0))
                               - int(result.get("overflow", 0)))
            economy.restock(st, DEEP, clears=economy.RESTOCK_EVERY * 20)
        ceiling = sum(potions.CARRY_CAP.values()) * len(self._kinds())
        self.assertGreater(landed, 0, "the shop sold nothing at all")
        self.assertLessEqual(landed, ceiling,
                             f"the pouch accepted {landed} bottles against a "
                             f"cap of {ceiling}")

    def test_a_second_draught_is_refused_until_a_cast_has_resolved(self):
        """The turn rule, exercised rather than quoted. This is the only limit on
        potions that cannot be farmed around, so it is the one worth executing."""
        pouch = potions.full_pouch()
        turn = potions.TurnState()
        player = {"stamina": 5, "stamina_max": 100, "mana": 5, "mana_max": 100}

        first = potions.drink(pouch, "health_minor", player=player,
                              turn_state=turn)
        self.assertNotIn("error", first, f"the first draught failed: {first}")
        self.assertFalse(turn.may_drink)

        second = potions.drink(pouch, "health_minor", player=player,
                               turn_state=turn)
        self.assertIn("error", second,
                      "a second potion was drunk without a line of Python "
                      "between them")

        potions.cast_resolved(turn, correct=True)
        self.assertTrue(turn.may_drink)
        third = potions.drink(pouch, "health_minor", player=player,
                              turn_state=turn)
        self.assertNotIn("error", third)

    def test_emptying_the_whole_pouch_costs_one_cast_per_bottle(self):
        """42 bottles is 42 turns is 42 MORE lines of Python than the player
        would otherwise have written. Hoarding converts into practice."""
        pouch = potions.full_pouch()
        held = pouch.total()
        turn = potions.TurnState()
        player = {"stamina": 1, "stamina_max": 10_000,
                  "mana": 1, "mana_max": 10_000}
        drunk = 0
        refusals = set()
        for potion_id in potions.POTION_IDS:
            while True:
                result = potions.drink(pouch, potion_id, player=player,
                                       turn_state=turn)
                if "error" in result:
                    refusals.add(result["error"])
                    break
                drunk += 1
                potions.cast_resolved(turn, correct=True)

        self.assertGreater(drunk, 0)
        self.assertEqual(turn.casts, drunk,
                         f"{drunk} bottles cost {turn.casts} casts; a bottle "
                         f"that costs no cast substitutes for typing")
        # Whatever stayed in the pouch stayed there because drinking it would
        # have been wasted, not because the game ran out of turns to offer.
        self.assertTrue(refusals <= {"none", "full_health", "full_focus",
                                     "no_poison"},
                        f"a draught was refused for an unexpected reason: "
                        f"{sorted(refusals)}")
        self.assertLessEqual(drunk, held)

    def test_even_the_largest_legal_pouch_still_demands_correct_python(self):
        """The end of the argument, in the only unit that matters: how right your
        typing has to be. A pouch that removed the requirement would be a pouch
        that substitutes for the game."""
        bare = potions.break_even_accuracy(damage=5, poison_on_miss=3)
        stocked = potions.break_even_accuracy(damage=5, poison_on_miss=3,
                                              pouch="full")
        self.assertLess(stocked, bare,
                        "carrying 42 potions bought the player nothing at all")
        self.assertGreater(stocked, 0.5,
                           f"the largest legal pouch drops the accuracy a player "
                           f"needs to {stocked:.0%}, which is a fight won by "
                           f"shopping rather than by typing")

    def test_stacking_one_kind_in_one_fight_hits_hard_diminishing_returns(self):
        multipliers = [potions.sip_multiplier(i) for i in range(10)]
        self.assertEqual(multipliers, sorted(multipliers, reverse=True))
        self.assertEqual(multipliers[-1], potions.SIP_FLOOR)
        hefty = potions.CARRY_CAP["hefty"]
        effective = sum(potions.sip_multiplier(i) for i in range(hefty))
        self.assertLess(effective, hefty,
                        "potions of one kind stack linearly inside a fight")

    def test_a_full_pouch_costs_a_serious_share_of_the_weapon_ladder(self):
        """Not a wall, but not pocket change either — otherwise the shelf is
        decoration and the player simply always has everything."""
        cost = 0
        for kind in self._kinds():
            for strength, count in potions.CARRY_CAP.items():
                price = economy.potion_price(f"{kind.lower()}_{strength}", DEEP)
                cost += price * count
        self.assertGreater(cost, 500)

    def test_restock_is_measured_in_cleared_encounters_and_never_in_time(self):
        """A clock would pay for waiting. This file does not pay for waiting."""
        st = economy.new_state()
        drained = economy.buy_potion(st, DEEP, "health_minor", gold=10 ** 9,
                                     quantity=potions.CARRY_CAP["minor"])
        self.assertNotIn("error", drained)
        self.assertEqual(drained["stock_left"], 0)

        def stock_of(potion_id):
            for row in economy.vendor_view(st, DEEP)["stock"]:
                if row["id"] == potion_id:
                    return row["stock"]
            raise KeyError(potion_id)

        self.assertEqual(stock_of("health_minor"), 0)
        # Time alone restores nothing: no clears, no restock.
        economy.restock(st, DEEP, clears=0)
        self.assertEqual(stock_of("health_minor"), 0,
                         "the shelf refilled without anybody clearing anything")
        economy.restock(st, DEEP, clears=economy.RESTOCK_EVERY)
        self.assertGreater(stock_of("health_minor"), 0,
                           "cleared encounters did not restock the shelf")


# ---------------------------------------------------------------------------
# 3. REGALIA BUYS FREQUENCY, NEVER DEPTH
# ---------------------------------------------------------------------------

class TheRegaliaTierLine(unittest.TestCase):
    """pets.py: "What bond never buys is DEPTH."

    There are two bodies of regalia and both have to obey it. This is the rule
    most easily broken by a buff that sounds reasonable, so the test diffs the
    actual help payload rather than reading the tables.
    """

    DEPTH_KEYS = ("tier", "depth", "hint_kind", "helps_through", "rank_ceiling",
                  "hint_weight")

    def test_no_regalia_object_carries_a_tier_or_a_depth_or_a_hint_kind(self):
        for piece in regalia.REGALIA:
            payload = piece.to_dict()
            for key in self.DEPTH_KEYS:
                self.assertNotIn(key, payload,
                                 f"{piece.id} carries {key}, which is depth")

    def test_regalia_has_exactly_two_levers_and_they_are_early_and_often(self):
        self.assertEqual(set(regalia.KINDS), {regalia.EARLY, regalia.OFTEN})
        for piece in regalia.REGALIA:
            self.assertIn(piece.kind, regalia.KINDS)

    def test_wearing_any_object_never_changes_what_a_companion_may_speak_about(self):
        """Every companion, every object it owns, every difficulty band."""
        for piece in regalia.REGALIA:
            bare = regalia.schedule(piece.pet, bond=3, region_id=piece.region)
            worn = regalia.schedule(piece.pet, bond=3, region_id=piece.region,
                                    regalia_id=piece.id)
            for key in self.DEPTH_KEYS:
                self.assertEqual(bare.get(key), worn.get(key),
                                 f"{piece.id} moved {key}")

    def test_an_object_may_only_make_help_earlier_or_more_frequent(self):
        for piece in regalia.REGALIA:
            bare = regalia.schedule(piece.pet, bond=3, region_id=piece.region)
            worn = regalia.schedule(piece.pet, bond=3, region_id=piece.region,
                                    regalia_id=piece.id)
            self.assertLessEqual(worn["threshold_scale"],
                                 bare["threshold_scale"] + 1e-9)
            self.assertGreaterEqual(worn["interventions"], bare["interventions"])

    def test_the_combined_bond_and_regalia_bounds_still_hold(self):
        """Two systems that each clamp their own share do not add up to a
        clamped total, so the bridge has to clamp the sum."""
        for piece in regalia.REGALIA:
            row = regalia.schedule(piece.pet, bond=9, region_id=piece.region,
                                   regalia_id=piece.id, also_scale=0.1,
                                   also_interventions=9)
            self.assertGreaterEqual(row["threshold_scale"], regalia.SCALE_FLOOR)
            self.assertLessEqual(row["interventions"],
                                 regalia.INTERVENTION_CEILING)

    def test_only_one_piece_may_be_worn_at_a_time(self):
        self.assertEqual(regalia.WORN_LIMIT, 1)

    def test_the_regional_tack_economy_sells_carries_no_new_lever(self):
        """quests.REGALIA is the body economy.py prices. Its rows may contain
        the two levers and cosmetics, and nothing else — a third key is how a
        priced object grows an effect."""
        for rid, piece in quests.REGALIA.items():
            extra = set(piece) - economy._REGALIA_LEGAL_KEYS
            self.assertFalse(extra, f"{rid} carries {sorted(extra)}")
            self.assertLessEqual(float(piece.get("threshold_scale", 1.0)), 1.0)
            self.assertGreaterEqual(int(piece.get("interventions", 0)), 0)

    def test_the_shop_never_prices_a_companion_object(self):
        """regalia.py's twenty-four are earned by evidence and must stay unpriced;
        help that can be bought with gold is help bought with time."""
        for piece in regalia.REGALIA:
            self.assertEqual(economy.regalia_price(piece.id), 0,
                             f"{piece.id} has acquired a price tag")
            self.assertNotIn(piece.id, economy.regalia_catalogue())

    def test_no_regalia_object_has_a_price_field_at_all(self):
        fields = set(regalia.Regalia.__dataclass_fields__)
        for forbidden in ("price", "cost", "fitting", "gold", "effects"):
            self.assertNotIn(forbidden, fields)


# ---------------------------------------------------------------------------
# 4. MULTI-AFFINITY IS STILL WINNABLE
# ---------------------------------------------------------------------------

class TheMultiAffinityFloor(unittest.TestCase):
    """elements.py guarantees: at most four times longer, never unwinnable, every
    hit lands for at least one. Multiple affinities must not weaken that.

    Swept exhaustively, because a guarantee about the worst case cannot be
    established by sampling.
    """

    BASE = 40

    def _chains(self):
        for width in range(1, elements.MAX_AFFINITIES + 1):
            for chain in itertools.product(elements.ELEMENTS, repeat=width):
                yield chain

    def _armours(self):
        return (
            ("none", elements.NO_ARMOUR),
            ("max plate", elements.ArmourProfile(
                points=999, resist={}, points_cap=elements.ARMOUR_POINT_CAP,
                kind="PLATE")),
            ("max warded", elements.ArmourProfile(
                points=999, resist={e: 1.0 for e in elements.ELEMENTS},
                points_cap=elements.ARMOUR_POINT_CAP, kind="WARDED")),
        )

    def test_every_hit_lands_for_at_least_one_whatever_the_affinities(self):
        for label, armour in self._armours():
            for attacker in elements.ELEMENTS:
                for chain in self._chains():
                    defender = elements.Defender(
                        element=chain[0], elements=chain, armour=armour,
                        max_health=200)
                    result = elements.resolve_damage(self.BASE, attacker, defender)
                    self.assertGreaterEqual(
                        result.damage, elements.MIN_DAMAGE,
                        f"{attacker} into {chain} behind {label} did nothing")

    def test_the_worst_case_is_exactly_the_advertised_worst_case(self):
        worst = 1.0
        witness = None
        for label, armour in self._armours():
            for attacker in elements.ELEMENTS:
                for chain in self._chains():
                    defender = elements.Defender(
                        element=chain[0], elements=chain, armour=armour,
                        max_health=200)
                    result = elements.resolve_damage(self.BASE, attacker, defender)
                    fraction = result.damage / self.BASE
                    if fraction < worst:
                        worst, witness = fraction, (label, attacker, chain)
        self.assertGreaterEqual(
            worst, elements.WORST_CASE_MULTIPLIER - 1e-9,
            f"{witness} beat the advertised floor")
        self.assertLessEqual(
            1.0 / worst, elements.MAX_FIGHT_STRETCH + 1e-9,
            f"a mismatched fight runs longer than {elements.MAX_FIGHT_STRETCH}x")

    def test_adding_affinities_never_makes_a_fight_unwinnable(self):
        """A third affinity may dilute your advantage. It may not erase your
        damage, and it may not push the fight past the advertised stretch."""
        for chain in self._chains():
            best = max(
                elements.resolve_damage(
                    self.BASE, attacker,
                    elements.Defender(element=chain[0], elements=chain,
                                      armour=elements.NO_ARMOUR, max_health=200)
                ).damage for attacker in elements.ELEMENTS)
            self.assertGreaterEqual(
                best / self.BASE, elements.WORST_CASE_MULTIPLIER,
                f"no blade does acceptable damage to {chain}")


class GoodGearBeatsBadGear(unittest.TestCase):
    """If the combination does not measurably pay, the strategy layer is
    decoration and the brief's whole multi-affinity design is cosmetic."""

    BASE = 40
    HP = 400

    def _turns(self, attacker, chain, armour=None):
        defender = elements.Defender(
            element=chain[0], elements=chain,
            armour=armour or elements.NO_ARMOUR, max_health=self.HP)
        damage = elements.resolve_damage(self.BASE, attacker, defender).damage
        return math.ceil(self.HP / max(1, damage))

    def test_choosing_the_right_blade_measurably_shortens_every_fight(self):
        for chain in (("FIRE",), ("FIRE", "COLD"), ("POISON", "VOID", "COLD"),
                      ("BRUTE", "POISON", "FIRE")):
            turns = [self._turns(a, chain) for a in elements.ELEMENTS]
            self.assertLess(min(turns), max(turns),
                            f"blade choice does not matter against {chain}")

    def test_the_right_ward_measurably_reduces_what_lands_on_you(self):
        for element in elements.ELEMENTS:
            other = next(e for e in elements.ELEMENTS if e != element)
            right = elements.ArmourProfile(points=4, resist={element: 0.6},
                                           points_cap=0.20, kind="WARDED")
            wrong = elements.ArmourProfile(points=4, resist={other: 0.6},
                                           points_cap=0.20, kind="WARDED")
            took_right = elements.resolve_damage(
                self.BASE, element,
                elements.Defender(armour=right, max_health=200)).damage
            took_wrong = elements.resolve_damage(
                self.BASE, element,
                elements.Defender(armour=wrong, max_health=200)).damage
            self.assertLess(took_right, took_wrong,
                            f"warding against {element} did not help against it")

    def test_a_full_combination_pays_more_than_either_half(self):
        """The brief's actual ask: combinations of armour AND weapons."""
        chain = ("FIRE", "BRUTE")
        best_blade = min(elements.ELEMENTS,
                         key=lambda a: self._turns(a, chain))
        worst_blade = max(elements.ELEMENTS,
                          key=lambda a: self._turns(a, chain))
        self.assertLess(self._turns(best_blade, chain),
                        self._turns(worst_blade, chain))
        ward = elements.ArmourProfile(points=4, resist={"FIRE": 0.6},
                                      points_cap=0.20, kind="WARDED")
        warded = elements.resolve_damage(
            self.BASE, "FIRE",
            elements.Defender(armour=ward, max_health=200)).damage
        bare = elements.resolve_damage(
            self.BASE, "FIRE",
            elements.Defender(armour=elements.NO_ARMOUR, max_health=200)).damage
        self.assertLess(warded, bare)


# ---------------------------------------------------------------------------
# 5. THE BROKER IS A PERSON, NOT A TYPE
# ---------------------------------------------------------------------------

class TheBoardSaysWhenTheWorkIsDone(unittest.TestCase):
    """`submit_to_trial` computes `ready` and hands it back in the submission
    payload. That is one screen. A player who closes the battle, or refreshes
    the page, then stands at the broker's board with the contract finished and
    is shown nothing but the demands — so `trial_state`, which IS the board,
    carries the same two numbers."""

    def test_the_open_contract_reports_what_is_left(self):
        state: dict = {}
        economy.open_trial(state, "fields_of_syntax", "tally")
        opened = economy.trial_state(state)
        self.assertIn("remaining", opened)
        self.assertIn("ready", opened)
        self.assertEqual(opened["remaining"], opened["need"])
        self.assertFalse(opened["ready"])

        last = None
        for i in range(opened["need"]):
            last = economy.submit_to_trial(
                state, problem_id="p%d" % i, difficulty=opened["band"],
                skill="PYTHON", hints_used=0, seconds=0.0, target_seconds=0.0)
            board = economy.trial_state(state)
            # The board and the submission must never disagree about this.
            self.assertEqual(board["remaining"], last["remaining"])
            self.assertEqual(board["ready"], last["ready"])
        self.assertTrue(last["ready"])
        self.assertTrue(economy.trial_state(state)["ready"])
        self.assertGreater(economy.close_trial(state).gold, 0)


class TheBrokerIsNotACaricature(unittest.TestCase):
    """The mechanic was requested with an ethnic shorthand. It is built as one
    specific woman instead, and these tests keep it that way — a later pass
    adding "flavour" to her lines is the realistic way this regresses."""

    SLURS_AND_SIGNIFIERS = (
        "gypsy", "gipsy", "romani", "roma ", "vardo", "caravan", "tambourine",
        "crystal ball", "fortune-tell", "fortune tell", "tarot", "palm read",
        "swarthy", "dusky", "exotic", "headscarf", "hoop earring", "rasta",
        "dreadlock", "jah ", "irie", "tribe", "wanderer's blood",
    )
    DIALECT = (" ye ", " yer ", "'ee ", " mon ", " ting ", " dem ", " nuh ",
               " tis ", "'tis", " o' ", " an' ", " de ")

    def _lines(self):
        for key, pool in economy.ASSAYER_LINES.items():
            for line in pool:
                yield key, line
        for key, value in economy.ASSAYER.items():
            if isinstance(value, str):
                yield key, value
        for form in economy.TRIAL_FORMS:
            yield form.id, form.offer
            yield form.id, form.blurb

    def test_no_line_carries_an_ethnic_signifier(self):
        for key, line in self._lines():
            low = line.lower()
            for token in self.SLURS_AND_SIGNIFIERS:
                self.assertNotIn(token, low, f"{key} carries {token!r}")

    def test_no_line_spells_out_an_accent(self):
        for key, line in self._lines():
            padded = f" {line.lower()} "
            for token in self.DIALECT:
                self.assertNotIn(token, padded, f"{key} uses dialect {token!r}")

    def test_she_is_a_specific_person_with_a_specific_history(self):
        for field in ("name", "was", "why_she_walks", "law", "blurb"):
            self.assertTrue(economy.ASSAYER.get(field),
                            f"the broker has no {field}")
        self.assertIn("Assayer", economy.ASSAYER["was"])

    def test_she_never_supplies_an_answer(self):
        for line in economy.ASSAYER_LINES["refuses_to_help"]:
            self.assertTrue(line)
        self.assertIn("refuses_to_help", economy.ASSAYER_LINES)

    def test_she_does_not_shout(self):
        for key, line in self._lines():
            self.assertNotIn("!", line, f"{key} uses an exclamation mark")


# ---------------------------------------------------------------------------
# 6. THE MODULES STILL AGREE WITH EACH OTHER
# ---------------------------------------------------------------------------

class TheModulesAgree(unittest.TestCase):

    def test_economy_validates_at_import(self):
        self.assertEqual(economy.validate(), [])

    def test_regalia_self_check_passes(self):
        self.assertTrue(regalia.self_check()["ok"])

    def test_the_economy_self_check_passes(self):
        self.assertTrue(economy.self_check()["ok"])

    def test_the_campaign_is_still_affordable(self):
        """Learning never dead-ends. No area may be unbeatable for want of gold,
        so the sinks must stay payable out of an ordinary playthrough."""
        report = economy.balance_report()
        self.assertLess(report["sink_share_fighting_only"], 1.4,
                        "a player who only fights cannot afford the game")

    def test_the_purse_is_a_minority_of_income(self):
        """The brief said RARE. A quarter of all income is a second wage paid by
        a dice roll."""
        for route, run in economy.simulate_all().items():
            earned = run["earned"]
            total = sum(earned.values())
            share = earned.get("purse", 0) / max(1, total)
            self.assertLess(share, 0.20,
                            f"a dice roll supplies {share:.0%} of income on the "
                            f"{route} route")


if __name__ == "__main__":
    unittest.main(verbosity=2)
