"""Loot economics.

The player asked for "loot drops random with percentages increasing for
difficulties" and rarity that means something. These tests measure the real
distributions rather than trusting the table, because a drop curve that looks
right in a constant and is wrong in practice is the classic way this goes bad.
"""
from base import GameTest  # noqa: E402
import random
import unittest
from collections import Counter


def _sample(difficulty, *, rank="B", luck=0.0, is_boss=False, n=4000, seed=11):
    from gauntlet import items
    rng = random.Random(seed)
    drops = 0
    rarities = Counter()
    for _ in range(n):
        drop = items.roll_drop(difficulty=difficulty, rank=rank, luck=luck,
                               is_boss=is_boss, rng=rng)
        if drop:
            drops += 1
            rarities[drop.get("rarity", "CONSUMABLE")] += 1
    return drops / n, rarities


class TestDropRates(GameTest):
    def test_drop_chance_rises_with_difficulty(self):
        from gauntlet import items
        order = ["TUTORIAL", "EASY", "MEDIUM", "HARD"]
        order = [d for d in order if d in items.DIFFICULTY_DROP_CHANCE]
        rates = [_sample(d, n=3000)[0] for d in order]
        for a, b, low, high in zip(rates, rates[1:], order, order[1:]):
            self.assertLess(a, b,
                            f"{low} ({a:.0%}) must drop less often than {high} ({b:.0%})")

    def test_a_tutorial_drop_is_uncommon_and_a_hard_drop_is_likely(self):
        tutorial, _ = _sample("TUTORIAL", n=3000)
        hard, _ = _sample("HARD", n=3000)
        self.assertLess(tutorial, 0.35, "early drops must stay a small reward")
        self.assertGreater(hard, 0.5, "a hard clear should usually pay")

    def test_bosses_always_drop(self):
        rate, _ = _sample("BOSS", is_boss=True, n=600)
        self.assertEqual(rate, 1.0, "a boss you finally beat must hand you something")

    def test_rank_and_luck_both_improve_the_odds(self):
        plain, _ = _sample("MEDIUM", rank="C", luck=0.0, n=3000)
        ranked, _ = _sample("MEDIUM", rank="S", luck=0.0, n=3000)
        lucky, _ = _sample("MEDIUM", rank="C", luck=0.6, n=3000)
        self.assertGreater(ranked, plain, "a better rank must pay better")
        self.assertGreater(lucky, plain, "INSIGHT must be worth spending points on")

    def test_rarity_is_a_real_curve_not_a_coin_flip(self):
        from gauntlet import items
        _, rarities = _sample("MEDIUM", n=6000, luck=0.0)
        counts = {r: rarities.get(r, 0) for r in items.RARITY_ORDER}
        ladder = [counts[r] for r in ["COMMON", "UNCOMMON", "RARE", "EPIC"]]
        for higher, lower, hname, lname in zip(ladder, ladder[1:],
                                               ["COMMON", "UNCOMMON", "RARE"],
                                               ["UNCOMMON", "RARE", "EPIC"]):
            self.assertGreater(higher, lower,
                               f"{hname} must be commoner than {lname}")
        self.assertGreater(counts["COMMON"], 0)

    def test_luck_shifts_the_curve_upward(self):
        _, plain = _sample("MEDIUM", n=5000, luck=0.0)
        _, lucky = _sample("MEDIUM", n=5000, luck=0.9)

        def high_share(counter):
            total = sum(counter.values()) or 1
            return (counter.get("RARE", 0) + counter.get("EPIC", 0)
                    + counter.get("LEGENDARY", 0)) / total

        self.assertGreater(high_share(lucky), high_share(plain),
                           "loot_luck must move the rarity curve, not just the rate")

    def test_mythic_is_never_in_the_random_pool(self):
        """Mythic items are discovered, never farmed."""
        for difficulty in ("MEDIUM", "HARD", "BOSS"):
            _, rarities = _sample(difficulty, is_boss=difficulty == "BOSS",
                                  luck=1.0, n=4000)
            self.assertEqual(rarities.get("MYTHIC", 0), 0,
                             "MYTHIC must only come from a secret")

    def test_every_rarity_has_items_to_drop(self):
        from gauntlet import items
        by_rarity = Counter(i.rarity for i in items.CATALOGUE if not i.hidden)
        for rarity in ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"]:
            self.assertGreater(by_rarity[rarity], 0,
                               f"nothing exists at {rarity}")

    def test_items_carry_real_attributes(self):
        from gauntlet import items
        bare = [i.id for i in items.CATALOGUE if not i.effects]
        self.assertEqual(bare, [], f"items with no effect at all: {bare[:5]}")
        for item in items.CATALOGUE:
            for key in item.effects:
                self.assertIn(key, items.EFFECT_LABELS,
                              f"{item.id} uses an undocumented effect {key}")
            self.assertTrue(item.flavour, f"{item.id} has no flavour text")

    def test_rarity_buys_power(self):
        """A legendary must actually be better than a common, or rarity is a lie."""
        from gauntlet import items

        # Effects are measured in wildly different units — a probe charge, ten
        # points of focus and a 25% XP bonus are all "1 effect" but not remotely
        # the same power. Score each on a comparable scale or the comparison is
        # meaningless.
        WEIGHT = {
            "probe_charges": 22.0, "second_wind": 20.0, "combo_shield": 16.0,
            "reveal_category": 14.0, "probe_reveal_value": 12.0,
            "perf_insight": 10.0, "mana_regen": 4.0,
            "mana_max": 1.0, "stamina_max": 1.4,
            "hint_discount": 30.0, "rank_grace": 26.0, "crit_bonus": 28.0,
            "loot_luck": 24.0, "xp_bonus": 30.0, "retest_bonus": 22.0,
            "shrine_bonus": 12.0, "armor_repair": 12.0,
        }

        def weight(item):
            return sum(WEIGHT.get(key, 8.0) * float(value)
                       for key, value in item.effects.items())

        by_rarity = {}
        for item in items.CATALOGUE:
            by_rarity.setdefault(item.rarity, []).append(weight(item))
        common = sum(by_rarity.get("COMMON", [0])) / max(1, len(by_rarity.get("COMMON", [1])))
        legendary = sum(by_rarity.get("LEGENDARY", [0])) / max(
            1, len(by_rarity.get("LEGENDARY", [1])))
        self.assertGreater(legendary, common,
                           "legendary items must be measurably stronger than common ones")


if __name__ == "__main__":
    unittest.main()
