"""THE SHELF, and the four things it is not allowed to get wrong.

This file exists because a shop is the easiest place in a game to lose an
economy, and this project has lost one twice already — a dungeon room that kept
paying and a boss that kept paying. Both were the same shape: a reward whose
input was something the player could repeat for free. So the headline test here
is not "does the rack produce items". It is `TheRackCannotBeRerolled`, which
plays the game badly on purpose — leaves the shop, leaves the region, drops the
save to JSON and loads it back, wipes the potion stock, fails encounters — and
asserts that the eight pieces on the wall are byte-for-byte the same eight
pieces afterwards.

  1. THE CURVE IS THE DROPS' CURVE. 10,000 rolls per region against the
     distribution declared from `items.RARITIES`, not against a number typed
     into this file. Rare is rare because the weights say so.
  2. THE RACK CANNOT BE REROLLED, and cannot be advanced by anything except a
     cleared encounter.
  3. THE PRICES ARE ECONOMY'S. Every price the shop quotes is recomputed from
     `economy.py` and compared, including the potions it does not own.
  4. A GENERATED ITEM NEVER BEATS AN AUTHORED ONE. Enumerated over every
     region, slot and rarity, and then exercised over 80,000 real rolls.
"""
from __future__ import annotations

import json
import math
import unittest

import base  # noqa: F401  - imported for the sys.path side effect

from gauntlet import economy, elements, forge, items, potions, shop, world


SHALLOW = "python_village"      # depth 0: floor COMMON, ceiling RARE
MID = "array_caverns"           # depth 3: floor UNCOMMON, ceiling EPIC
DEEP = "graph_wastes"           # depth 6: floor RARE, ceiling LEGENDARY

SAMPLES = 10_000                # the brief asked for ten thousand rolls


def a_state() -> dict:
    return {"economy": economy.new_state(), "forge": forge.new_state(),
            "class": {"class": "analyst"}, "player": {"gold": 5000}}


# ---------------------------------------------------------------------------
# 1. THE CURVE IS THE DROPS' CURVE
# ---------------------------------------------------------------------------

class RareStatsAreRare(unittest.TestCase):
    """The distribution, measured, against the curve the module declares.

    The declared curve is not a constant in this test. It is computed in
    `shop.declared_curve` straight out of `items.RARITIES["*"]["weight"]` and
    the region's depth clamp, so if somebody doubles the LEGENDARY weight in
    items.py to make drops richer, this test does not fail — the rack gets
    richer with the drops, which is the invariant. What it catches is the rack
    drifting away from the drops.
    """

    def _measure(self, region_id, samples=SAMPLES):
        counts = {r: 0 for r in shop.RACK_RARITIES}
        for i in range(samples):
            for slot in shop.RACK_SLOTS:
                row = shop.roll(region_id, slot, save_seed=i, restock_index=0)
                self.assertTrue(row, f"{region_id}/{slot} rolled nothing")
                counts[row["rarity"]] += 1
        total = sum(counts.values())
        return counts, total

    def test_ten_thousand_rolls_match_the_declared_curve(self):
        for region_id in (SHALLOW, MID, DEEP):
            with self.subTest(region=region_id):
                counts, total = self._measure(region_id)
                declared = shop.declared_curve(region_id)
                for rarity, share in declared.items():
                    got = 100.0 * counts[rarity] / total
                    # Three standard errors of a binomial at this sample size,
                    # with a floor so that a 1.1% bucket is not held to a
                    # tolerance tighter than the sampling noise it has.
                    p = share / 100.0
                    se = 100.0 * math.sqrt(max(p * (1 - p), 1e-6) / total)
                    self.assertAlmostEqual(
                        got, share, delta=max(3.0 * se, 0.15),
                        msg=(f"{region_id} {rarity}: rolled {got:.3f}% against "
                             f"a declared {share:.3f}% over {total} rolls"))

    def test_the_weights_are_read_from_items_and_not_copied(self):
        """The raw curve, before any clamp, is items.RARITIES exactly."""
        weights = {r: items.RARITIES[r]["weight"] for r in shop.RACK_RARITIES}
        total = sum(weights.values())
        self.assertEqual(total, 175)
        expect = {r: round(100.0 * w / total, 3) for r, w in weights.items()}
        # graph_wastes clamps COMMON and UNCOMMON up into RARE and nothing
        # else, so EPIC and LEGENDARY come through untouched.
        deep = shop.declared_curve(DEEP)
        self.assertAlmostEqual(deep["EPIC"], expect["EPIC"], places=3)
        self.assertAlmostEqual(deep["LEGENDARY"], expect["LEGENDARY"], places=3)
        self.assertEqual(deep["COMMON"], 0.0)
        self.assertEqual(deep["UNCOMMON"], 0.0)

    def test_a_legendary_costs_about_eleven_restocks_of_work(self):
        """The design's claim, in encounters, checked rather than repeated."""
        p = shop.declared_curve(DEEP)["LEGENDARY"] / 100.0
        per_restock = 1.0 - (1.0 - p) ** len(shop.RACK_SLOTS)
        restocks = 1.0 / per_restock
        self.assertLess(abs(restocks - 11.0), 1.5, f"{restocks:.1f} restocks")
        self.assertLess(abs(restocks * economy.RESTOCK_EVERY - 66.0), 9.0)

    def test_the_village_never_sells_a_legendary_and_the_wastes_never_junk(self):
        for i in range(2000):
            for slot in shop.RACK_SLOTS:
                shallow = shop.roll(SHALLOW, slot, save_seed=i, restock_index=i)
                deep = shop.roll(DEEP, slot, save_seed=i, restock_index=i)
                self.assertIn(shallow["rarity"],
                              ("COMMON", "UNCOMMON", "RARE"))
                self.assertIn(deep["rarity"], ("RARE", "EPIC", "LEGENDARY"))

    def test_mythic_is_never_on_a_shop_wall(self):
        self.assertEqual(items.RARITIES["MYTHIC"]["weight"], 0)
        self.assertNotIn("MYTHIC", shop.RACK_RARITIES)
        for i in range(4000):
            for slot in shop.RACK_SLOTS:
                for region_id in (SHALLOW, DEEP):
                    self.assertNotEqual(
                        shop.roll(region_id, slot, save_seed=i,
                                  restock_index=0)["rarity"], "MYTHIC")

    def test_the_three_rare_stats_are_locked_and_not_merely_unlikely(self):
        """loot_luck and armour_cap need RARE; xp_bonus needs EPIC. A lock is
        not a low weight: at 80,000 rolls a 1-in-1000 chance would show."""
        for i in range(SAMPLES):
            for slot in shop.RACK_SLOTS:
                row = shop.roll(MID, slot, save_seed=i, restock_index=0)
                rank = shop.RACK_RARITIES.index(row["rarity"])
                for key in row["effects"]:
                    need = shop.MIN_RARITY.get(key)
                    if need:
                        self.assertGreaterEqual(
                            rank, shop.RACK_RARITIES.index(need),
                            f"{key} on a {row['rarity']} {slot}")

    def test_a_common_rack_item_is_one_plain_line(self):
        seen = 0
        for i in range(3000):
            for slot in shop.RACK_SLOTS:
                row = shop.roll(SHALLOW, slot, save_seed=i, restock_index=0)
                if row["rarity"] != "COMMON":
                    continue
                seen += 1
                self.assertEqual(len(row["effects"]), 1, row["name"])
                self.assertFalse(set(row["effects"]) & set(shop.MIN_RARITY))
        self.assertGreater(seen, 1000)


# ---------------------------------------------------------------------------
# 2. THE RACK CANNOT BE REROLLED
# ---------------------------------------------------------------------------

class TheRackCannotBeRerolled(unittest.TestCase):
    """The lock that matters. Everything a player can do for free, done."""

    def test_leaving_and_coming_back_finds_the_same_wall(self):
        st = a_state()
        first = shop.rack(st, DEEP, save_seed=99)
        # open the panel again
        self.assertEqual(shop.rack(st, DEEP, save_seed=99), first)
        # walk out of the building, round the region and back in: nothing in
        # that sequence is a cleared encounter, so nothing in it is an input.
        shop.counter(st, DEEP, save_seed=99, gold=10_000)
        shop.counter(st, SHALLOW, save_seed=99, gold=10_000)
        shop.counter(st, DEEP, save_seed=99, gold=10_000)
        self.assertEqual(shop.rack(st, DEEP, save_seed=99), first)
        # quit to title and load the save back off disk
        reloaded = json.loads(json.dumps(st))
        self.assertEqual(shop.rack(reloaded, DEEP, save_seed=99), first)

    def test_nothing_in_this_module_can_advance_the_restock_index(self):
        """`economy.restock` is the only door, so every other door is tried.

        A failed encounter never reaches `restock()` — the engine calls it for
        a CLEARED encounter only, and its own docstring says so — so a failure
        is modelled here by the thing it actually is: the absence of that call,
        with everything a player CAN do without clearing anything done to the
        shop in between.
        """
        st = a_state()
        forge.grant_blade(st["forge"], "analysts_calipers")
        first = shop.rack(st, DEEP, save_seed=99)
        for _ in range(50):
            shop.counter(st, DEEP, gold=10_000, save_seed=99)
            shop.rack(st, DEEP, save_seed=99, gold=10_000)
            shop.blank(st, DEEP, save_seed=99, gold=10_000)
            shop.buy(st, DEEP, "chest", gold=10_000, save_seed=99)
            shop.buy_blank(st, DEEP, gold=10_000, save_seed=99)
            shop.sell(st, DEEP, shop.item_id(DEEP, 0, "chest"))
            economy.vendor_view(st, DEEP, gold=10_000)
            economy.grant_credit(st, DEEP, 50)
            st = json.loads(json.dumps(st))
        self.assertEqual(economy.rack_index(st, DEEP), 0)
        after = shop.rack(st, DEEP, save_seed=99)
        for before, now in zip(first, after):
            self.assertEqual(before["id"], now["id"])
            self.assertEqual(before["effects"], now["effects"])
            self.assertEqual(before["price"], now["price"])

    def test_only_six_clears_turn_the_rack_over(self):
        st = a_state()
        first = shop.rack(st, DEEP, save_seed=99)
        for n in range(1, economy.RESTOCK_EVERY):
            economy.restock(st, DEEP, clears=1)
            self.assertEqual(economy.rack_index(st, DEEP), 0, f"after {n}")
            self.assertEqual(shop.rack(st, DEEP, save_seed=99), first)
        economy.restock(st, DEEP, clears=1)
        self.assertEqual(economy.rack_index(st, DEEP), 1)
        self.assertNotEqual(shop.rack(st, DEEP, save_seed=99), first)

    def test_buying_does_not_reroll_the_other_pegs(self):
        st = a_state()
        before = {r["slot"]: r for r in shop.rack(st, DEEP, save_seed=99)}
        out = shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        self.assertNotIn("error", out, out)
        after = {r["slot"]: r for r in shop.rack(st, DEEP, save_seed=99)}
        for slot, row in before.items():
            if slot == "chest":
                self.assertTrue(after[slot]["sold"])
            else:
                self.assertEqual(row["effects"], after[slot]["effects"])
                self.assertEqual(row["price"], after[slot]["price"])

    def test_a_bought_peg_stays_empty_until_the_shelves_turn_over(self):
        st = a_state()
        shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        again = shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        self.assertEqual(again.get("error"), "sold")
        economy.restock(st, DEEP, clears=economy.RESTOCK_EVERY)
        fresh = shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        self.assertNotIn("error", fresh, fresh)

    def test_two_seeds_build_two_different_shops(self):
        """A pure function of the seed is worth nothing if it ignores the seed."""
        a = shop.rack(None, DEEP, save_seed=1)
        b = shop.rack(None, DEEP, save_seed=2)
        self.assertNotEqual([r["id"] for r in a], [])
        self.assertNotEqual([(r["rarity"], r["effects"]) for r in a],
                            [(r["rarity"], r["effects"]) for r in b])

    def test_an_item_rebuilds_from_its_id_alone(self):
        """Nothing about a bought piece has to be stored beyond its id, which
        is the same statement as 'the rack is a function' said backwards."""
        for region_id in (SHALLOW, MID, DEEP):
            for index in (0, 1, 7, 40):
                for slot in shop.RACK_SLOTS:
                    row = shop.roll(region_id, slot, save_seed=1234,
                                    restock_index=index)
                    back = shop.item_by_id(row["id"], save_seed=1234)
                    self.assertEqual(row, back)
                    self.assertTrue(shop.is_rack_item(row["id"]))
        self.assertFalse(shop.is_rack_item("warden_helm"))
        self.assertEqual(shop.item_by_id("warden_helm", save_seed=1), {})

    def test_a_rack_item_is_not_in_the_catalogue(self):
        """Generated stock must never enter items.BY_ID, roll_drop's candidate
        list or the trophy manifest."""
        row = shop.roll(DEEP, "chest", save_seed=5, restock_index=0)
        self.assertNotIn(row["id"], items.BY_ID)
        self.assertEqual(row["source"], "vendor")


# ---------------------------------------------------------------------------
# 3. THE PRICES ARE ECONOMY'S
# ---------------------------------------------------------------------------

class ThePricesComeFromEconomy(unittest.TestCase):

    def test_every_rack_price_recomputes_from_economy(self):
        for region in world.REGIONS:
            rid = region["id"]
            if economy.vendor_for(rid) is None:
                continue
            for i in range(40):
                for slot in shop.RACK_SLOTS:
                    row = shop.roll(rid, slot, save_seed=i, restock_index=i)
                    want = economy.rack_price(
                        row["rarity"], rid,
                        budget_used=row["budget_used"],
                        budget_max=float(row["budget"]))
                    self.assertEqual(row["price"], want,
                                     f"{rid}/{slot} {row['rarity']}")

    def test_the_worked_example_in_the_design_document(self):
        """A RARE piece in the Graph Wastes at a full roll: 100 x 1.60 x 1.60."""
        self.assertEqual(economy.ARMOUR_FEE["RARE"], 100)
        self.assertEqual(economy.area_depth(DEEP), 6)
        self.assertEqual(
            economy.rack_price("RARE", DEEP, budget_used=1.0, budget_max=1.0),
            255)

    def test_price_rises_with_rarity_depth_and_roll(self):
        base = economy.rack_price("RARE", SHALLOW, budget_used=0.0,
                                  budget_max=1.0)
        self.assertLess(base, economy.rack_price("RARE", DEEP, budget_used=0.0,
                                                 budget_max=1.0))
        self.assertLess(base, economy.rack_price("RARE", SHALLOW,
                                                 budget_used=1.0,
                                                 budget_max=1.0))
        self.assertLess(base, economy.rack_price("EPIC", SHALLOW,
                                                 budget_used=0.0,
                                                 budget_max=1.0))

    def test_a_clamped_roll_is_not_charged_for_what_it_did_not_get(self):
        """The ceiling takes effect away; the price has to follow it down."""
        full = economy.rack_price("RARE", DEEP, budget_used=10.0,
                                  budget_max=10.0)
        thin = economy.rack_price("RARE", DEEP, budget_used=3.0,
                                  budget_max=10.0)
        self.assertLess(thin, full)

    def test_buy_then_sell_is_a_seventy_five_percent_loss(self):
        st = a_state()
        out = shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        paid = out["price"]
        back = shop.sell(st, DEEP, out["bought"])
        self.assertNotIn("error", back, back)
        self.assertEqual(back["gold_back"], economy.rack_sellback(paid))
        self.assertAlmostEqual(back["gold_back"] / paid, 0.25, delta=0.01)
        self.assertEqual(shop.sell(st, DEEP, out["bought"]).get("error"),
                         "not_bought")

    def test_a_piece_can_be_sold_back_after_the_shelves_turn_over(self):
        """The receipt outlives the peg. Bought, then six cleared encounters,
        then sold back — the shop that sold it still knows what was paid."""
        st = a_state()
        out = shop.buy(st, DEEP, "head", gold=100_000, save_seed=99)
        for _ in range(4):
            economy.restock(st, DEEP, clears=economy.RESTOCK_EVERY)
        self.assertEqual(economy.rack_index(st, DEEP), 4)
        self.assertEqual(economy.rack_sold(st, DEEP), {})
        back = shop.sell(st, DEEP, out["bought"])
        self.assertNotIn("error", back, back)
        self.assertEqual(back["paid"], out["price"])
        self.assertEqual(back["gold_back"], economy.rack_sellback(out["price"]))

    def test_a_piece_cannot_be_sold_twice(self):
        st = a_state()
        out = shop.buy(st, DEEP, "head", gold=100_000, save_seed=99)
        self.assertNotIn("error", shop.sell(st, DEEP, out["bought"]))
        for _ in range(5):
            self.assertEqual(shop.sell(st, DEEP, out["bought"]).get("error"),
                             "not_bought")

    def test_a_piece_cannot_be_sold_to_a_vendor_who_did_not_sell_it(self):
        st = a_state()
        out = shop.buy(st, DEEP, "head", gold=100_000, save_seed=99)
        self.assertEqual(shop.sell(st, MID, out["bought"]).get("error"),
                         "not_bought")

    def test_a_piece_nobody_sold_cannot_be_sold_back(self):
        st = a_state()
        self.assertEqual(
            shop.sell(st, DEEP, shop.item_id(DEEP, 0, "head")).get("error"),
            "not_bought")
        self.assertEqual(shop.sell(st, DEEP, "warden_helm").get("error"),
                         "not_bought")

    def test_selling_back_does_not_reopen_the_peg(self):
        st = a_state()
        out = shop.buy(st, DEEP, "offhand", gold=100_000, save_seed=99)
        shop.sell(st, DEEP, out["bought"])
        self.assertEqual(
            shop.buy(st, DEEP, "offhand", gold=100_000,
                     save_seed=99).get("error"), "sold")

    def test_the_rack_refuses_vendor_credit(self):
        """Credit is a quest reward and quest rewards are already curved.
        Letting it buy generated armour routes it round its own taper."""
        st = a_state()
        economy.grant_credit(st, DEEP, 100_000)
        self.assertEqual(economy.credit_at(st, DEEP), 100_000)
        out = shop.buy(st, DEEP, "chest", gold=0, save_seed=99)
        self.assertEqual(out.get("error"), "no_gold")
        self.assertEqual(economy.credit_at(st, DEEP), 100_000)

    def test_a_purchase_is_recorded_in_the_same_ledger_as_everything_else(self):
        st = a_state()
        out = shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        ledger = economy.ledger_view(st)
        self.assertEqual(ledger["spent"].get(economy.RACK_SINK), out["price"])

    def test_nothing_here_touches_the_purse(self):
        st = a_state()
        st["player"]["gold"] = 777
        shop.counter(st, DEEP, gold=777, save_seed=99)
        shop.buy(st, DEEP, "chest", gold=100_000, save_seed=99)
        shop.sell(st, DEEP,
                  shop.item_id(DEEP, economy.rack_index(st, DEEP), "chest"))
        shop.buy_blank(st, DEEP, gold=100_000, save_seed=99)
        self.assertEqual(st["player"]["gold"], 777)

    def test_the_potion_counter_is_economys_untouched(self):
        st = a_state()
        counter = shop.counter(st, MID, gold=500, save_seed=1)
        vendor = economy.vendor_view(st, MID, gold=500)
        self.assertEqual(counter["stock"], vendor["stock"])
        ids = [row["id"] for row in counter["stock"]]
        self.assertEqual(ids, economy.stock_list(MID))
        self.assertEqual(ids, potions.available_at(economy.area_band(MID)))
        for row in counter["stock"]:
            self.assertEqual(row["price"], economy.potion_price(row["id"], MID))

    def test_level_specific_means_region_band_and_says_so(self):
        shallow = shop.counter(None, SHALLOW, save_seed=1)
        deep = shop.counter(None, DEEP, save_seed=1)
        self.assertLess(len(shallow["stock"]), len(deep["stock"]))
        self.assertTrue(shallow["shelf_note"])
        self.assertEqual(shallow["band"], economy.area_band(SHALLOW))


# ---------------------------------------------------------------------------
# 4. A GENERATED ITEM NEVER BEATS AN AUTHORED ONE
# ---------------------------------------------------------------------------

class TheRackCannotOutDropABoss(unittest.TestCase):

    def test_the_ceiling_is_measured_off_the_authored_catalogue(self):
        """Not typed. Re-derive it here and compare."""
        cost = shop.RACK_COST
        running, best = {}, 0.0
        for rarity in shop.RACK_RARITIES:
            for r, effects in shop._authored_surface():
                if r != rarity:
                    continue
                total = 0.0
                for key, value in effects.items():
                    if key not in shop.RACK_EFFECTS:
                        continue
                    running[key] = max(running.get(key, 0.0), float(value))
                    total += float(value) * cost[key]
                best = max(best, total)
            self.assertAlmostEqual(shop.ROLL_CEILING[rarity], round(best, 2),
                                   places=2)

    def test_no_roll_anywhere_exceeds_an_authored_item(self):
        """Every region, every slot, 10,000 seeds' worth of rolls."""
        worst = {}
        for i in range(SAMPLES):
            for slot in shop.RACK_SLOTS:
                for region_id in (SHALLOW, MID, DEEP):
                    row = shop.roll(region_id, slot, save_seed=i,
                                    restock_index=0)
                    table = shop.CEILINGS[row["rarity"]]
                    for key, value in row["effects"].items():
                        self.assertLessEqual(
                            float(value), float(table[key]) + 1e-9,
                            f"{region_id}/{slot}/{row['rarity']}: {key}")
                        k = (row["rarity"], key)
                        worst[k] = max(worst.get(k, 0.0), float(value))
        self.assertTrue(worst)

    def test_the_budget_never_exceeds_the_authored_bar(self):
        for region in world.REGIONS:
            for rarity in shop.RACK_RARITIES:
                self.assertLessEqual(
                    shop._budget(rarity, region["id"]),
                    shop.ROLL_CEILING[rarity],
                    f"{region['id']}/{rarity}")

    def test_the_damage_functions_own_caps_are_respected(self):
        for rarity, table in shop.CEILINGS.items():
            for key, value in table.items():
                if key.startswith("resist_"):
                    self.assertLessEqual(value, elements.PIECE_RESIST_CAP)
                if key == "armour_cap":
                    self.assertLessEqual(value, elements.ARMOUR_POINT_CAP)

    def test_nothing_on_the_rack_supplies_an_answer(self):
        self.assertEqual(shop._no_rack_item_supplies_an_answer(), [])
        self.assertFalse(shop.RACK_EFFECTS & shop.RACK_EFFECTS_REFUSED)
        for key in shop.RACK_EFFECTS:
            self.assertIn(key, items.EFFECT_LABELS)
        for i in range(500):
            for slot in shop.RACK_SLOTS:
                row = shop.roll(DEEP, slot, save_seed=i, restock_index=0)
                for key in row["effects"]:
                    self.assertIn(key, shop.RACK_EFFECTS)
                    self.assertNotIn(key, shop.RACK_EFFECTS_REFUSED)

    def test_a_legendary_rack_piece_is_still_worse_than_a_legendary_drop(self):
        """Spot check on the strongest thing the rack can build."""
        best = None
        for i in range(6000):
            for slot in shop.RACK_SLOTS:
                row = shop.roll(DEEP, slot, save_seed=i, restock_index=0)
                if row["rarity"] != "LEGENDARY":
                    continue
                points = sum(float(v) * shop.RACK_COST[k]
                             for k, v in row["effects"].items())
                if best is None or points > best:
                    best = points
        self.assertIsNotNone(best, "no legendary in 48,000 rolls")
        self.assertLessEqual(best, shop.ROLL_CEILING["LEGENDARY"] + 1e-9)


# ---------------------------------------------------------------------------
# 5. THE BLADE BLANK — swords for gold, without a second sword curve
# ---------------------------------------------------------------------------

class TheBlankIsNotASecondLadder(unittest.TestCase):

    def _armed(self, tier=4):
        st = a_state()
        forge.grant_blade(st["forge"], "analysts_calipers")
        st["forge"]["tiers"]["analysts_calipers"] = tier
        return st

    def test_the_blank_is_always_exactly_one_rung_up(self):
        for have in range(1, forge.MAX_TIER):
            st = self._armed(have)
            for index in range(30):
                economy._vendor_room(st, "null_kings_castle")["rack"] = index
                offer = shop.blank(st, "null_kings_castle", save_seed=3)
                if offer:
                    self.assertEqual(offer["tier"], have + 1)
                    break

    def test_no_blank_past_the_top_of_the_ladder(self):
        st = self._armed(forge.MAX_TIER)
        for index in range(30):
            economy._vendor_room(st, "null_kings_castle")["rack"] = index
            self.assertEqual(shop.blank(st, "null_kings_castle", save_seed=3),
                             {})

    def test_no_blank_a_regions_own_metal_could_not_have_reached(self):
        st = self._armed(4)
        self.assertEqual(shop.max_blank_tier("fields_of_syntax"), 2)
        for index in range(30):
            economy._vendor_room(st, "fields_of_syntax")["rack"] = index
            self.assertEqual(shop.blank(st, "fields_of_syntax", save_seed=3),
                             {})

    def test_no_blank_before_the_class_quest_hands_over_the_line(self):
        st = a_state()
        for index in range(30):
            economy._vendor_room(st, DEEP)["rack"] = index
            self.assertEqual(shop.blank(st, DEEP, save_seed=3), {})

    def test_the_blank_is_dearer_than_forging_it(self):
        """The forge must stay the cheap road. The Shelf is the convenient one."""
        for blade in forge.BLADES:
            for tier in sorted(forge.GOLD_SHAPE):
                price = economy.blank_price(blade.id, tier)
                self.assertGreater(price, forge.GOLD_SHAPE[tier],
                                   f"{blade.id} rung {tier}")
                metal = economy.blank_metal_value(blade.id, tier)
                self.assertAlmostEqual(
                    price,
                    economy.round_to_5((forge.GOLD_SHAPE[tier] + metal)
                                       * economy.BLANK_PREMIUM))

    def test_the_metal_is_priced_off_the_fights_that_would_have_yielded_it(self):
        """No new opinion about gold: forge.expected_metal and
        economy.encounter_award, multiplied."""
        blade = forge.BLADES[0]
        rung = blade.rung(5)
        want = 0.0
        for metal_id, units in rung.cost.items():
            metal = forge.METAL_BY_ID[metal_id]
            rid = metal.regions[0]
            band = economy.area_band(rid)
            per = forge.expected_metal(band, rank="B")
            award = economy.encounter_award(None, region_id=rid,
                                            difficulty=band, rank="B",
                                            problem_id="")
            want += (units / per) * award.gold
        self.assertEqual(economy.blank_metal_value(blade.id, 5),
                         int(round(want)))

    def test_the_blank_does_not_write_the_forges_tiers(self):
        st = self._armed(4)
        for index in range(30):
            economy._vendor_room(st, DEEP)["rack"] = index
            out = shop.buy_blank(st, DEEP, gold=1_000_000, save_seed=3)
            if "error" not in out:
                self.assertEqual(st["forge"]["tiers"]["analysts_calipers"], 4)
                self.assertEqual(out["grant"]["owner"], "forge")
                self.assertEqual(out["grant"]["tier"], 5)
                return
        self.fail("no blank offered in thirty restocks")

    def test_the_blank_carries_no_new_rarity_mapping(self):
        st = self._armed(5)
        for index in range(30):
            economy._vendor_room(st, DEEP)["rack"] = index
            offer = shop.blank(st, DEEP, save_seed=3)
            if offer:
                self.assertEqual(offer["rarity"],
                                 forge.RARITY_BY_RUNG[offer["tier"]])
                self.assertEqual(
                    offer["name"],
                    forge.BLADE_BY_ID["analysts_calipers"]
                    .rung(offer["tier"]).name)
                return
        self.fail("no blank offered in thirty restocks")


# ---------------------------------------------------------------------------
# 6. THE MODULE'S OWN CHECKS
# ---------------------------------------------------------------------------

class TheModuleChecksItself(unittest.TestCase):

    def test_shop_self_check(self):
        check = shop.self_check()
        self.assertTrue(check["ok"], check["problems"])
        self.assertEqual(check["slots"], 8)

    def test_economy_self_check_still_passes(self):
        self.assertTrue(economy.self_check()["ok"],
                        economy.self_check()["problems"])

    def test_the_counter_answers_in_one_call(self):
        st = a_state()
        forge.grant_blade(st["forge"], "analysts_calipers")
        view = shop.counter(st, DEEP, gold=400, save_seed=11)
        for key in ("stock", "rack", "blank", "rack_index", "rack_left",
                    "restock_in", "credit", "shelf_note", "band", "depth"):
            self.assertIn(key, view)
        self.assertEqual(len(view["rack"]), 8)
        self.assertEqual(view["rack_left"], 8)

    def test_eight_pegs_are_eight_different_objects(self):
        for region in world.REGIONS:
            if economy.vendor_for(region["id"]) is None:
                continue
            for index in range(20):
                rows = shop.rack(None, region["id"], save_seed=index)
                names = [r["name"] for r in rows]
                self.assertEqual(len(set(names)), len(names),
                                 f"{region['id']}: {sorted(names)}")
                ids = [r["id"] for r in rows]
                self.assertEqual(len(set(ids)), len(ids))

    def test_every_region_with_a_vendor_fills_all_eight_pegs(self):
        for region in world.REGIONS:
            if economy.vendor_for(region["id"]) is None:
                continue
            for index in range(20):
                rows = [shop.roll(region["id"], slot, save_seed=index,
                                  restock_index=index)
                        for slot in shop.RACK_SLOTS]
                self.assertTrue(all(rows), region["id"])
                self.assertEqual([r["slot"] for r in rows],
                                 list(shop.RACK_SLOTS), region["id"])

    def test_a_region_with_no_vendor_refuses_rather_than_raises(self):
        view = shop.counter(None, "nowhere_at_all", save_seed=1)
        self.assertIn("error", view)
        self.assertEqual(view["rack"], [])
        self.assertEqual(
            shop.buy({}, "nowhere_at_all", "chest", gold=99).get("error"),
            "no_vendor")

    def test_an_old_save_gains_a_rack_rather_than_crashing(self):
        """A save written before the rack existed has no `rack` key."""
        st = {"economy": {"ledger": {}, "earned": {}, "spent": {},
                          "vendors": {DEEP: {"stock": {}, "credit": 0,
                                             "clears": 3}},
                          "broker": {}, "regalia": []}}
        self.assertEqual(economy.rack_index(st, DEEP), 0)
        self.assertEqual(len(shop.rack(st, DEEP, save_seed=1)), 8)


# ---------------------------------------------------------------------------
# 9. THE TWO GUARDS THAT WERE GUARDING NOTHING
# ---------------------------------------------------------------------------

class TheRarityTableIsPinnedAndNotMerelyPresent(unittest.TestCase):
    """`validate()` used to iterate MIN_RARITY to prove MIN_RARITY, which is
    vacuous on a SHORTENED table: delete a key and there is nothing left to
    iterate, so the guard reports success by having nothing to say. Measured on
    a clone with `"xp_bonus": "EPIC"` removed — validate() returned [], all 51
    tests passed, and +5%% XP shipped on 9.78%% of COMMON python_village rolls.
    The tests in section 1 had the same hole: both read the table they exist to
    test, through `.get()` and through `set(shop.MIN_RARITY)`.
    """

    PAYING = ("loot_luck", "armour_cap", "xp_bonus")

    def _without(self, keys):
        """Run validate() against a table with `keys` deleted, then restore.

        MIN_RARITY is module state and `_keys_for` reads it live, so this has
        to put it back whatever happens or every later test in the process is
        measuring a different shop.
        """
        saved = dict(shop.MIN_RARITY)
        try:
            for key in keys:
                shop.MIN_RARITY.pop(key, None)
            return shop.validate()
        finally:
            shop.MIN_RARITY.clear()
            shop.MIN_RARITY.update(saved)

    def test_the_table_is_whole_to_start_with(self):
        self.assertEqual(shop.validate(), [])
        for key in self.PAYING:
            self.assertIn(key, shop.MIN_RARITY)

    def test_deleting_any_paying_key_is_caught_by_name(self):
        for key in self.PAYING:
            with self.subTest(deleted=key):
                problems = self._without([key])
                self.assertTrue(problems, f"deleting {key} was invisible")
                self.assertTrue(any(key in p for p in problems), problems)

    def test_emptying_the_table_is_caught_three_times(self):
        problems = self._without(self.PAYING)
        self.assertEqual(len(problems), 3, problems)

    def test_the_deletion_it_missed_really_did_ship_an_item(self):
        """The measurement that made this worth a guard: without the lock,
        a 30-gold COMMON ring in the starting village pays the player XP."""
        saved = dict(shop.MIN_RARITY)
        try:
            shop.MIN_RARITY.pop("xp_bonus")
            hits = commons = 0
            for i in range(400):
                for slot in shop.RACK_SLOTS:
                    row = shop.roll(SHALLOW, slot, save_seed=i, restock_index=0)
                    if row and row["rarity"] == "COMMON":
                        commons += 1
                        hits += "xp_bonus" in row["effects"]
        finally:
            shop.MIN_RARITY.clear()
            shop.MIN_RARITY.update(saved)
        self.assertGreater(commons, 500)
        self.assertGreater(hits / commons, 0.05,
                           "the lock was load-bearing and this proves it")


class SellingBackAsksWhetherYouStillHaveIt(unittest.TestCase):
    """LOCK 6. A receipt deliberately outlives the restock — that is the point
    of it — so on its own it says "this vendor sold you one of these", never
    "you still have it"."""

    def _bought(self):
        st = a_state()
        row = shop.rack(st, DEEP, save_seed=7)[0]
        out = shop.buy(st, DEEP, row["slot"], gold=99999, save_seed=7)
        self.assertNotIn("error", out, out)
        return st, out["bought"]

    def test_an_empty_bag_refuses_by_name_and_keeps_the_receipt(self):
        st, item_id = self._bought()
        out = shop.sell(st, DEEP, item_id, inventory=[])
        self.assertEqual(out["error"], "not_held")
        self.assertEqual(out["text"], shop.REFUSALS["not_held"])
        self.assertNotIn("gold_back", out)
        # THE RECEIPT IS TORN UP LAST. A refused sale must not cost the player
        # the receipt on the way out, or the refusal becomes the confiscation.
        self.assertIn(item_id, economy.rack_receipts(st, DEEP))
        paid = shop.sell(st, DEEP, item_id, inventory=[item_id])
        self.assertEqual(paid["sold"], item_id)
        self.assertGreater(paid["gold_back"], 0)

    def test_holding_it_pays_and_the_second_sale_still_refuses(self):
        st, item_id = self._bought()
        first = shop.sell(st, DEEP, item_id, inventory=[item_id])
        self.assertEqual(first["sold"], item_id)
        again = shop.sell(st, DEEP, item_id, inventory=[item_id])
        self.assertEqual(again["error"], "not_bought")

    def test_no_bag_at_all_is_still_allowed_for_a_price_check(self):
        """`inventory` is optional ONLY so a caller checking a price, and this
        module's own proofs, need not synthesise one. An engine always passes
        it — CONTRACT section 3 says so — and engine.sell_rack does."""
        st, item_id = self._bought()
        out = shop.sell(st, DEEP, item_id)
        self.assertEqual(out["sold"], item_id)

    def test_the_contract_tells_the_wirer_both_of_these(self):
        """A CONTRACT that leaves out the seal produces an engine that lets a
        player re-kit mid-exam, and one that leaves out the bag produces one
        that pays for an empty hand."""
        text = shop.CONTRACT
        self.assertIn("_sealed_in_interview", text)
        self.assertIn("BUILD", text)
        self.assertIn("inventory=", text)
        self.assertIn("not_held", text)


if __name__ == "__main__":
    unittest.main()
