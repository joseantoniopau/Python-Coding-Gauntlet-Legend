"""The RPG layer: it must be genuinely powerful and structurally unable to cheat."""
from base import GameTest  # noqa: E402
import random
import unittest


class TestTactics(GameTest):
    def test_weaknesses_come_from_the_problems_real_edge_cases(self):
        from gauntlet import tactics
        p = self.by_id("ah-two-sum-indices")
        enemy = tactics.derive_enemy(p, name="x", sprite="slime")
        self.assertTrue(enemy.weaknesses)
        for w in enemy.weaknesses:
            self.assertIn(w["key"], tactics.WEAKNESSES)

    def test_performance_tests_create_brute_force_resistance(self):
        from gauntlet import tactics
        p = self.by_id("ah-two-sum-indices")
        enemy = tactics.derive_enemy(p, name="x", sprite="slime")
        self.assertIn("BRUTE_FORCE", {r["key"] for r in enemy.resistances})

    def test_a_correct_probe_exposes_a_weakness(self):
        g = self.game()
        g.choose_build("ANALYST")
        g.start_encounter("ah-two-sum-indices")
        result = g.probe([[3, 3], 6], [0, 1])
        self.assertTrue(result["correct"])
        self.assertTrue(result["weakness_hit"])
        self.assertIn(result["weakness"], g.encounter.exposed)

    def test_a_wrong_probe_teaches_rather_than_punishes(self):
        g = self.game()
        g.choose_build("ANALYST")
        g.start_encounter("ah-two-sum-indices")
        result = g.probe([[2, 7, 11, 15], 9], [1, 0])   # wrong order
        self.assertFalse(result["correct"])
        self.assertIn("wrong", result["message"].lower())
        self.assertGreaterEqual(result["charges_left"], 0)

    def test_probing_credits_the_testing_skill(self):
        g = self.game()
        g.choose_build("ANALYST")
        before = g.skills["TESTING"].mastery
        g.start_encounter("ah-two-sum-indices")
        g.probe([[], 0], [])
        self.assertGreater(g.skills["TESTING"].mastery, before)

    def test_exposed_weaknesses_produce_criticals_and_more_xp(self):
        g = self.game()
        g.choose_build("ANALYST")
        p = self.by_id("ah-two-sum-indices")

        g.start_encounter(p.id)
        plain = g.submit(p.canonical_solution)

        g2 = self.game()
        g2.state = g2._load_or_create()
        g2.choose_build("ANALYST")
        g2.start_encounter(p.id)
        g2.probe([[3, 3], 6], [0, 1])
        g2.probe([[-3, 4, 3, 90], 0], [0, 2])
        probed = g2.submit(p.canonical_solution)

        self.assertTrue(probed["combat"]["crits"])
        self.assertGreater(probed["combat"]["xp_multiplier"], 1.0)
        self.assertGreater(probed["xp"], plain["xp"],
                           "tactical play must pay measurably better")

    def test_probes_are_limited_by_the_build(self):
        g = self.game()
        g.choose_build("DUELIST")       # low LOGIC
        g.start_encounter("ah-two-sum-indices")
        charges = g.probes_remaining()
        self.assertGreaterEqual(charges, 1)
        for _ in range(charges):
            g.probe([[1, 2], 3], [0, 1])
        result = g.probe([[1, 2], 3], [0, 1])
        self.assertEqual(result["error"], "no charges")

    def test_probe_cannot_reveal_the_solution(self):
        g = self.game()
        g.choose_build("ANALYST")
        g.start_encounter("sw-longest-no-repeat")
        result = g.probe(["abcabcbb"], 3)
        blob = str(result).lower()
        self.assertNotIn("last_seen", blob)
        self.assertNotIn("def length_of_longest", blob)


class TestItems(GameTest):
    def test_set_bonuses_apply_at_their_thresholds(self):
        from gauntlet import items
        two = items.total_effects(
            {"head": "testsmith_monocle", "hands": "testsmith_gloves"}, {})
        three = items.total_effects(
            {"head": "testsmith_monocle", "hands": "testsmith_gloves",
             "offhand": "testsmith_shield"}, {})
        self.assertGreater(two["probe_charges"], 1)
        self.assertTrue(three.get("reveal_category"))

    def test_attributes_raise_real_ceilings(self):
        g = self.game()
        g.choose_build("ARCHIVIST")
        before = g.state["player"]["mana_max"]
        g.state["unspent_points"] = 5
        g.allocate("FOCUS", 5)
        self.assertGreater(g.state["player"]["mana_max"], before)

    def test_hint_discount_reduces_focus_cost(self):
        g = self.game()
        g.state["inventory"] = ["archivist_hood", "archivist_robe", "archivist_ring"]
        g.state["equipped"] = {"head": "archivist_hood", "chest": "archivist_robe",
                               "ring1": "archivist_ring"}
        g._sync_caps()
        g.save()
        g.start_encounter("sw-k-distinct")
        result = g.use_hint(3)
        rung = next(r for r in self.by_id("sw-k-distinct").hint_tree if r["level"] == 3)
        self.assertLess(result["cost"], rung["mana"])

    def test_rank_grace_never_changes_correctness(self):
        g = self.game()
        g.choose_build("DUELIST")
        p = self.by_id("ah-two-sum-indices")
        g.start_encounter(p.id)
        result = g.submit("def two_sum(nums, target):\n    return []\n")
        self.assertFalse(result["solved"], "grace must not turn a wrong answer right")

    def test_bosses_always_drop_something_wearable(self):
        from gauntlet import items
        rng = random.Random(3)
        for _ in range(12):
            drop = items.roll_drop(difficulty="BOSS", rank="A", luck=0.0,
                                   is_boss=True, rng=rng)
            self.assertIsNotNone(drop)
            if drop["kind"] == "item":
                self.assertIn(drop["rarity"], ("RARE", "EPIC", "LEGENDARY"))

    def test_no_item_can_supply_an_answer(self):
        """Structural guarantee: the effect vocabulary contains nothing that
        could reveal a solution, a pattern name, or a hidden expected value."""
        from gauntlet import items
        forbidden = {"reveal_solution", "auto_solve", "skip_tests", "reveal_pattern",
                     "reveal_expected", "show_answer"}
        for item in items.CATALOGUE:
            self.assertEqual(set(item.effects) & forbidden, set(), item.id)
            for key in item.effects:
                self.assertIn(key, items.EFFECT_LABELS, f"{item.id}: {key}")

    def test_hidden_items_are_not_in_the_normal_drop_pool(self):
        from gauntlet import items
        rng = random.Random(11)
        seen = set()
        for _ in range(400):
            drop = items.roll_drop(difficulty="BOSS", rank="S", luck=1.0,
                                   is_boss=True, rng=rng)
            if drop and drop["kind"] == "item":
                seen.add(drop["id"])
        hidden = {i.id for i in items.CATALOGUE if i.hidden}
        self.assertEqual(seen & hidden, set(), "secret items must stay secret")

    def test_secrets_are_awarded_for_genuine_feats(self):
        g = self.game()
        g.choose_build("ANALYST")
        p = self.by_id("ah-two-sum-indices")
        brute = ("def two_sum(nums, target):\n"
                 "    for i in range(len(nums)):\n"
                 "        for j in range(i + 1, len(nums)):\n"
                 "            if nums[i] + nums[j] == target:\n"
                 "                return [i, j]\n"
                 "    return []\n")
        g.start_encounter(p.id)
        g.submit(brute)                      # fails on performance alone
        self.assertIn(p.id, g.state["perf_failed_ids"])
        g.start_encounter(p.id)
        result = g.submit(p.canonical_solution)
        ids = [s["id"] for s in result["secrets"]]
        self.assertIn("secret_linear", ids,
                      "turning a quadratic into a line must be recognised")
        self.assertIn("linear_edge", g.state["inventory"])

    def test_level_up_grants_attribute_points(self):
        g = self.game()
        g.choose_build("ANALYST")
        g.state["player"]["xp"] = 0
        before = g.state["unspent_points"]
        for pid in ("ah-two-sum-indices", "sw-k-distinct", "tp-valid-palindrome",
                    "sq-valid-parens", "mx-rotate"):
            p = self.by_id(pid)
            g.start_encounter(p.id)
            g.submit(p.canonical_solution)
        self.assertGreater(g.state["player"]["level"], 1)
        self.assertGreater(g.state["unspent_points"], before)

    def test_equipping_and_unequipping_is_reversible(self):
        g = self.game()
        g.state["inventory"] = ["hashblade"]
        g.save()
        self.assertTrue(g.equip("hashblade")["ok"])
        self.assertEqual(g.state["equipped"]["weapon"], "hashblade")
        g.unequip("weapon")
        self.assertNotIn("weapon", g.state["equipped"])


if __name__ == "__main__":
    unittest.main()
