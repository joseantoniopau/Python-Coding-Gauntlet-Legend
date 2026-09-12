"""The forge: the answer rule, the seal, reachability, the economy and the art.

These are the four claims the feature cannot ship without, in the order they
matter. The first one matters most and is the one a well-meaning future rung
will break: a technique that sounds helpful is exactly what "supplies an answer"
looks like from the inside.

The economy tests deliberately do NOT call forge.grind_estimate() and assert it
agrees with itself. They roll forge.roll_metal() the number of times a player
would and count, because the question the brief asked — "how many encounters
does tier eight actually cost" — cannot be answered by the function whose
arithmetic is the thing under suspicion.
"""
from __future__ import annotations

import copy
import random
import re

from base import GameTest

from gauntlet import classes, config, finalexam, forge, items, saves, world


# ---------------------------------------------------------------------------
# 1. THE ANSWER RULE
# ---------------------------------------------------------------------------

class AnswerRule(GameTest):
    """No rung, at any tier, may supply an answer.

    Checked three ways, because each one catches a different mistake: the
    vocabulary check catches a new effect key invented to do something the
    existing ones will not, the allowlist catches an EXISTING key borrowed for a
    weapon that has no business granting it, and the prose check catches a rung
    whose effects are innocent and whose description promises more than they
    deliver.
    """

    # Every effect key any rung of any blade is allowed to grant, written out
    # rather than derived from forge.FORGE_EFFECT_KEYS. A derived list would
    # agree with the module by construction and prove nothing; as a literal, a
    # new key on a new rung fails here and a human has to look at it and decide
    # whether a weapon may grant it. That decision is the whole point.
    ALLOWED = frozenset({
        "declare_slots", "declare_bonus", "probe_charges", "probe_refund",
        "perf_insight", "first_try_bonus", "probe_first_free",
        "rank_grace", "iteration_bonus", "retry_grace", "stamina_max",
        "recovery_grace", "focus_from_failure",
        "retest_bonus", "retest_charges", "srs_preview", "interval_stretch",
        "mana_max", "spell_refund", "retest_storm",
        "edge_ward", "crit_bonus", "reveal_category", "weakness_scan",
        "boundary_sense",
        "bench_slots", "refactor_bonus", "design_rubric", "mana_regen",
        "second_wind",
        "trace_frames", "root_cause_bonus", "probe_reveal_value", "prereq_sight",
    })

    # Keys that would hand over the thing the player is supposed to produce. No
    # weapon may grant any of these at any rung. They are named individually
    # rather than pattern-matched because "contains the word solution" is a spell
    # check, not a rule.
    FORBIDDEN = frozenset({
        "reveal_solution", "worked_solution", "show_answer", "auto_solve",
        "skip_encounter", "free_clear", "reveal_pattern", "name_pattern",
        "reference_impl", "solution_preview", "autocomplete", "copy_solution",
    })

    def test_every_effect_key_exists_in_the_shared_vocabulary(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                for key in rung.effects:
                    self.assertIn(
                        key, items.EFFECT_LABELS,
                        f"{blade.id} t{rung.tier}: {key!r} is a private verb; "
                        f"effects must come from items.EFFECT_LABELS")

    def test_no_rung_grants_a_key_outside_the_reviewed_allowlist(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                for key in rung.effects:
                    self.assertIn(
                        key, self.ALLOWED,
                        f"{blade.id} t{rung.tier} grants {key!r}, which no "
                        f"reviewer has cleared for a weapon. Add it to "
                        f"AnswerRule.ALLOWED only after deciding it cannot "
                        f"supply an answer.")

    def test_no_rung_grants_an_answer_supplying_key(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                bad = self.FORBIDDEN & set(rung.effects)
                self.assertEqual(
                    set(), bad,
                    f"{blade.id} t{rung.tier} supplies an answer: {sorted(bad)}")

    def test_the_forge_adds_no_new_effect_keys_at_all(self):
        """The module's headline claim, checked rather than believed."""
        self.assertEqual(
            [], [k for k in forge.FORGE_EFFECT_KEYS
                 if k not in items.EFFECT_LABELS])

    def test_technique_text_never_promises_an_answer(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                low = rung.technique_text.lower()
                for phrase in forge.FORBIDDEN_IN_TECHNIQUE:
                    self.assertNotIn(
                        phrase, low,
                        f"{blade.id} t{rung.tier}: technique text says "
                        f"{phrase!r}")

    def test_technique_text_describes_only_keys_the_rung_actually_grants(self):
        """The module's prose claims a technique is "the readable name for the
        keys". It was not enforced anywhere, so a rung could advertise a
        capability it does not grant — which is the cheapest possible way to
        promise an answer without shipping one.

        Checked as a floor rather than a parse: a rung that names a capability
        must hold it. The vocabulary is the handful of capabilities whose names
        appear in this file's own prose.
        """
        claims = {
            r"probes?": ("probe_charges", "probe_first_free", "probe_refund",
                         "probe_reveal_value", "boundary_sense",
                         "reveal_category"),
            r"bench": ("bench_slots",),
            r"wards?": ("edge_ward",),
            r"frames?": ("trace_frames",),
            r"stamina": ("stamina_max", "retry_grace", "focus_from_failure"),
            r"focus": ("mana_max", "mana_regen", "spell_refund",
                       "focus_from_failure", "second_wind"),
            r"ambush(?:es)?": ("retest_bonus", "retest_charges", "retest_storm",
                               "srs_preview", "interval_stretch"),
            r"declar\w*": ("declare_slots", "declare_bonus"),
            r"rubric": ("design_rubric",),
        }
        # Whole words only. "rewarding a correct edge call" is not a claim to
        # grant a ward, and a substring match says it is.
        for blade in forge.BLADES:
            for rung in blade.rungs:
                low = rung.technique_text.lower()
                for word, keys in claims.items():
                    if not re.search(rf"\b{word}\b", low):
                        continue
                    self.assertTrue(
                        any(k in rung.effects for k in keys),
                        f"{blade.id} t{rung.tier} talks about {word!r} but "
                        f"grants none of {keys}. A technique is the readable "
                        f"name for the keys, not a second effect system.")

    def test_no_rung_reaches_a_class_cap_on_its_own(self):
        """A blade that caps a stat by itself deletes every tree node above it."""
        for blade in forge.BLADES:
            for rung in blade.rungs:
                for key, value in rung.effects.items():
                    cap = classes.CAPS.get(key)
                    if cap is None:
                        continue
                    if key in classes.RATE_KEYS:
                        self.assertLessEqual(
                            value, cap * forge.CAP_SHARE + 1e-9,
                            f"{blade.id} t{rung.tier}: {key}={value} takes more "
                            f"than {forge.CAP_SHARE:.0%} of the cap {cap}")
                    else:
                        self.assertLessEqual(
                            value, cap - forge.CAP_HEADROOM,
                            f"{blade.id} t{rung.tier}: {key}={value} leaves the "
                            f"tree no room under cap {cap}")

    def test_naming_a_category_never_hands_over_the_value(self):
        """The rule that matters most, checked where it was actually broken.

        `tactics.run_probe` ORed reveal_category into probe_reveal_value, so any
        blade granting the weaker effect alone returned the true expected value
        on a failed probe. The Boundary Maul carries reveal_category from rung
        five and the Tracing Needle from rung four, and both of their technique
        texts promise the opposite in as many words. A blade that says "never the
        expected value" and then prints the expected value is worse than one that
        never claimed anything.
        """
        from gauntlet import tactics
        problem = next(p for p in self.corpus
                       if p.entry.get("kind") == "function" and p.visible_tests)
        visible = problem.visible_tests[0]

        def probe(effects):
            # A deliberately wrong expectation, so the probe fails and the
            # reveal path is the one under test.
            return tactics.run_probe(problem, visible["args"],
                                     "__certainly not the answer__",
                                     effects=effects, already_exposed=[])

        category_only = probe({"reveal_category": 1})
        self.assertTrue(category_only.ok, category_only.error)
        self.assertFalse(category_only.correct)
        self.assertIsNone(
            category_only.true_value,
            "reveal_category handed over the true value; it names a category")

        with_value = probe({"probe_reveal_value": 1})
        self.assertIsNotNone(
            with_value.true_value,
            "probe_reveal_value stopped doing the thing it is labelled as")

        nothing = probe({})
        self.assertIsNone(nothing.true_value)

    def test_no_blade_grants_a_probe_oracle_on_its_own(self):
        """boundary_sense makes probes on the first and last element free and
        unlimited. probe_reveal_value prints the true answer for the input you
        chose. Either alone is information about the encounter; together, on one
        weapon, they are an unlimited oracle for two positions and the player
        stops having to think about those two. No rung may carry both."""
        for blade in forge.BLADES:
            for rung in blade.rungs:
                self.assertFalse(
                    "boundary_sense" in rung.effects
                    and "probe_reveal_value" in rung.effects,
                    f"{blade.id} t{rung.tier} grants unlimited free probes AND "
                    f"the true value for them")

    def test_a_metal_is_loot_and_never_evidence(self):
        """Mastery moves on graded evidence. The forge must not touch it.

        `temper` and `tempered` were added by the affinity pass (SECTION 2b/2c).
        They are gear: `temper` is {item_id: {element, step, kind, metal}} and
        `tempered` is a counter of bench visits, the same shape and the same
        nature as `tiers` and `forged`. The assertion is kept exact rather than
        loosened to a subset, because its entire job is to notice a key nobody
        argued for.
        """
        self.assertNotIn("skills", vars(forge))
        self.assertNotIn("skillmod", vars(forge))
        self.assertEqual(
            sorted(forge.new_state()),
            ["forged", "metals", "racked", "temper", "tempered", "tiers"],
            "forge state grew a key; if it is skill state, it does not belong")
        # And the two new ones hold gear, not evidence: nothing a temper writes
        # is a skill, a mastery number or a clear count.
        state = forge.new_state()
        state["metals"] = {"faultsteel": 99}
        forge.temper(state, "some_chestplate", slot="chest",
                     metal_id="faultsteel", gold=10 ** 6)
        row = state[forge.TEMPER_KEY]["some_chestplate"]
        self.assertEqual(sorted(row), ["element", "kind", "metal", "step"])

    def test_the_modules_own_proofs_pass(self):
        self.assertEqual([], forge.validate())


# ---------------------------------------------------------------------------
# 2. THE SEAL
# ---------------------------------------------------------------------------

class Sealed(GameTest):
    """Nothing the forge does works in a measured run.

    There is exactly one isolation path — finalexam.sealed(enc, "BUILD") — and
    these tests exist to keep it at one. A second path is how a feature ends up
    half-sealed: technique off, metal still dropping.
    """

    def _interview(self, g):
        g.start_interview("LIVE_SCREEN")
        return g.interview_current()

    def test_build_is_a_real_finalexam_capability(self):
        self.assertIn(forge.FORGE_CAPABILITY, finalexam.ALL_CRUTCHES)

    def test_the_final_practical_seals_the_forge(self):
        final = [s for s in finalexam.BOSS_LADDER if s.final]
        self.assertTrue(final, "there is no final practical")
        for seal in final:
            self.assertTrue(
                seal.blocks(forge.FORGE_CAPABILITY),
                "the final practical does not seal BUILD, so a blade works in it")

    def test_no_technique_applies_in_an_interview_encounter(self):
        g = self.game()
        self._interview(g)
        enc = g.encounter
        self.assertEqual(enc.mode, config.MODE_INTERVIEW)
        for blade in forge.BLADES:
            for tier in range(forge.MIN_TIER, forge.MAX_TIER + 1):
                self.assertEqual(
                    {}, forge.effects_in(blade.id, tier, enc),
                    f"{blade.id} t{tier} still has effects in a measured run")

    def test_a_sealed_blade_returns_nothing_rather_than_less(self):
        """Half a legendary is worse than an honest nothing: a player who can
        see a reduced number will spend the run wondering which number it is."""
        g = self.game()
        self._interview(g)
        top = forge.effects_in("boundary_maul", forge.MAX_TIER, g.encounter)
        self.assertEqual({}, top)

    def test_no_metal_drops_in_an_interview_encounter(self):
        g = self.game()
        self._interview(g)
        rng = random.Random(1)
        for _ in range(300):
            self.assertIsNone(forge.roll_metal(
                region_id="graph_wastes", difficulty="BOSS", rank="S",
                luck=1.0, is_boss=True, encounter=g.encounter, rng=rng),
                "a metal accrued in a measured run")

    def test_the_smith_refuses_in_interview_mode(self):
        g = self.game()
        self._interview(g)
        for call in (lambda: g.forge_upgrade("analysts_calipers"),
                     lambda: g.forge_rack("analysts_calipers"),
                     lambda: g.forge_unrack()):
            self.assertEqual("sealed", call().get("error"))

    def test_the_equipped_blade_contributes_nothing_to_a_measured_run(self):
        """End to end, through engine.effects(), which is what the encounter
        actually reads."""
        g = self.game()
        state = g.state.setdefault("forge", forge.new_state())
        forge.grant_blade(state, "boundary_maul")
        state["tiers"]["boundary_maul"] = forge.MAX_TIER
        top_id = forge.rung("boundary_maul", forge.MAX_TIER).id
        g.state["inventory"].append(top_id)
        g.state["equipped"]["weapon"] = top_id
        loose = g.effects()
        self._interview(g)
        sealed = g.effects()
        for key in forge.rung("boundary_maul", forge.MAX_TIER).effects:
            self.assertGreaterEqual(
                loose.get(key, 0), sealed.get(key, 0),
                f"{key} did not fall when the seal came up")
        self.assertEqual(
            0, sealed.get("boundary_sense", 0),
            "the Mythic maul's free probes survived into a measured run")


# ---------------------------------------------------------------------------
# 3. REACHABILITY AND THE ECONOMY
# ---------------------------------------------------------------------------

class Economy(GameTest):
    """Every tier is reachable, and the cost is a number rather than a promise.

    "Slowly" was the word the design started from; "unreachable" is a different
    word, and only a measured count tells them apart.
    """

    # A player who is competent but not perfect. Rank feeds the drop rate
    # through items.RANK_BONUS exactly as loot does.
    RANKS = ["S"] * 10 + ["A"] * 25 + ["B"] * 35 + ["C"] * 20 + ["D"] * 10

    # The ceiling the design is willing to defend for one rung, and for a whole
    # blade. Rung nine is meant to be talked about rather than had; it is not
    # meant to be a second job.
    MAX_ENCOUNTERS_PER_RUNG = 220
    MAX_ENCOUNTERS_PER_BLADE = 700

    def _best_region(self, metal_id):
        metal = forge.METAL_BY_ID[metal_id]
        return max(metal.regions,
                   key=lambda r: forge.expected_metal(
                       forge.typical_difficulty(r)))

    def _fights_for(self, cost, rng):
        """Encounters to farm one rung's bill, region by region, no boss kills
        and no substitution. The honest pessimistic path."""
        fights = 0
        for metal_id, need in cost.items():
            region = self._best_region(metal_id)
            difficulty = forge.typical_difficulty(region)
            have = 0
            while have < need:
                fights += 1
                got = forge.roll_metal(
                    region_id=region, difficulty=difficulty,
                    rank=rng.choice(self.RANKS), rng=rng)
                if got:
                    have += got["units"]
                if fights > 50000:
                    self.fail(f"{cost} is not farmable")
        return fights

    def test_every_tier_is_reachable_and_the_cost_is_sane(self):
        rng = random.Random(20260912)
        for blade in forge.BLADES:
            total = 0
            for rung in blade.rungs:
                if rung.tier == forge.MIN_TIER:
                    continue
                runs = sorted(self._fights_for(rung.cost, rng)
                              for _ in range(24))
                median = runs[len(runs) // 2]
                total += median
                self.assertGreater(
                    median, 0, f"{blade.id} t{rung.tier} costs no fighting")
                self.assertLessEqual(
                    median, self.MAX_ENCOUNTERS_PER_RUNG,
                    f"{blade.id} t{rung.tier} takes {median} encounters, which "
                    f"is a wall rather than a climb")
            self.assertLessEqual(
                total, self.MAX_ENCOUNTERS_PER_BLADE,
                f"{blade.id} costs {total} encounters end to end")

    def test_the_ladder_gets_dearer_and_never_cheaper(self):
        for blade in forge.BLADES:
            previous = 0
            for rung in blade.rungs:
                if rung.tier == forge.MIN_TIER:
                    continue
                cost = forge.encounters_for(rung.cost)
                self.assertGreaterEqual(
                    cost, previous,
                    f"{blade.id} t{rung.tier} is cheaper than the rung below")
                previous = cost

    def test_the_modules_own_estimate_is_not_optimistic(self):
        """forge.grind_estimate() is what the smith quotes a player. It is
        allowed to be pessimistic and it is not allowed to undersell the grind,
        because a player who is told 'about forty fights' and spends ninety
        stops trusting every other number in the game."""
        rng = random.Random(4242)
        for blade in forge.BLADES:
            claimed = {row["tier"]: row["encounters"]
                       for row in forge.grind_estimate(blade.id)
                       ["blades"][blade.id]["rungs"]}
            for rung in blade.rungs:
                if rung.tier == forge.MIN_TIER:
                    continue
                runs = sorted(self._fights_for(rung.cost, rng)
                              for _ in range(24))
                median = runs[len(runs) // 2]
                self.assertGreaterEqual(
                    claimed[rung.tier] * 1.35, median,
                    f"{blade.id} t{rung.tier}: quoted {claimed[rung.tier]} "
                    f"encounters, measured {median}")

    def test_every_metal_drops_somewhere_a_player_can_stand(self):
        for metal in forge.METALS:
            self.assertTrue(metal.regions, f"{metal.id} drops nowhere")
            for region_id in metal.regions:
                self.assertIn(region_id, world.REGION_BY_ID,
                              f"{metal.id} drops in a region that does not exist")

    def test_every_fighting_region_pays_a_metal(self):
        """The map is the economy. A region that pays nothing is a region with
        no reason to visit it, which is the problem this feature exists to fix."""
        for region in world.REGIONS:
            if region["id"] in forge.NO_METAL_REGIONS:
                continue
            self.assertIsNotNone(
                forge.metal_for_region(region["id"]),
                f"{region['id']} drops no metal")

    def test_the_town_pays_nothing(self):
        for region_id in forge.NO_METAL_REGIONS:
            self.assertIsNone(forge.metal_for_region(region_id))
            self.assertIsNone(forge.roll_metal(
                region_id=region_id, difficulty="BOSS", is_boss=True,
                rng=random.Random(0)))

    def test_no_upgrade_path_dead_ends(self):
        """A player who skipped a region must always be able to buy their way
        forward out of higher metal, at a bad rate. Learning never dead-ends and
        neither does the ladder that hangs off it."""
        for blade in forge.BLADES:
            for rung in blade.rungs:
                if rung.tier == forge.MIN_TIER:
                    continue
                state = forge.new_state()
                forge.grant_blade(state, blade.id)
                state["tiers"][blade.id] = rung.tier - 1
                # Nothing but the top metal, in quantity.
                forge.add_metal(state, "nullsteel", 4000)
                quote = forge.quote(state, blade.id, gold=10 ** 6)
                self.assertTrue(
                    quote["ready"],
                    f"{blade.id} t{rung.tier} cannot be reached with a bag of "
                    f"the top metal: {quote['still_short']}")


# ---------------------------------------------------------------------------
# 4. EVERY CLASS IS SERVED
# ---------------------------------------------------------------------------

class ClassParity(GameTest):

    def test_every_class_has_exactly_one_blade(self):
        covered = {b.class_id for b in forge.BLADES}
        self.assertEqual(
            {c.id for c in classes.CLASSES}, covered,
            "a class has no signature weapon, or two of them")
        self.assertEqual(len(forge.BLADES), len(covered))

    def test_each_blade_is_the_signature_weapon_classes_py_names(self):
        for blade in forge.BLADES:
            self.assertEqual(
                classes.CLASS_BY_ID[blade.class_id].signature_weapon, blade.id)

    def test_every_blade_climbs_all_nine_rungs(self):
        for blade in forge.BLADES:
            self.assertEqual(forge.MAX_TIER, len(blade.rungs))
            for tier, rung in enumerate(blade.rungs, start=1):
                self.assertEqual(tier, rung.tier)

    def test_rung_six_keeps_the_promise_classes_py_made(self):
        for blade in forge.BLADES:
            promised = next(g for g in classes.GEAR_REQUESTS if g.id == blade.id)
            six = blade.rung(6)
            self.assertEqual(promised.id, six.id)
            self.assertEqual(promised.name, six.name)
            self.assertEqual(promised.rarity, six.rarity)
            for key, value in promised.effects.items():
                self.assertGreaterEqual(
                    six.effects.get(key, 0), value,
                    f"{blade.id} rung six dropped {key} below what class design "
                    f"promised")

    def test_no_blade_is_strictly_worse_than_a_weapon_it_could_have_found(self):
        """The trade is deliberate: a forged blade loses on raw rate and wins on
        capability and on the fact that it grows. Losing on BOTH is not a trade,
        it is a reason to leave the blade on the rack — and the Berserker used to
        do exactly that at rungs two, three and six, because every effect it had
        was a rate.

        Rivals are filtered through classes.equippable(), because a weapon this
        class may not carry is not an alternative to anything.
        """
        for blade in forge.BLADES:
            for rung in blade.rungs:
                rivals = [i for i in forge.found_weapons(rung.rarity)
                          if classes.equippable(i.id, blade.class_id)]
                if not rivals:
                    continue
                best_rate = max(forge._rate_total(i.effects) for i in rivals)
                best_caps = max(forge._capability_count(i.effects)
                                for i in rivals)
                mine_rate = forge._rate_total(rung.effects)
                mine_caps = forge._capability_count(rung.effects)
                self.assertFalse(
                    mine_rate < best_rate and mine_caps < best_caps,
                    f"{blade.id} t{rung.tier} ({rung.rarity}) loses on rate "
                    f"({mine_rate:.2f} vs {best_rate:.2f}) AND on capability "
                    f"({mine_caps} vs {best_caps}). There is no reason to carry "
                    f"it.")

    def test_every_rung_grants_something(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                self.assertTrue(
                    rung.effects,
                    f"{blade.id} t{rung.tier} does nothing at all")

    def test_nothing_ever_gets_worse_going_up(self):
        for blade in forge.BLADES:
            for lower, higher in zip(blade.rungs, blade.rungs[1:]):
                for key, value in lower.effects.items():
                    self.assertGreaterEqual(
                        higher.effects.get(key, 0), value,
                        f"{blade.id} t{higher.tier}: {key} fell")

    def test_a_blade_is_restricted_to_its_own_class(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                self.assertEqual(
                    blade.class_id, forge.FORGE_RESTRICTED.get(rung.id),
                    f"{rung.id} is not locked to {blade.class_id}")

    def test_no_rung_id_collides_with_the_items_catalogue(self):
        for blade in forge.BLADES:
            for rung in blade.rungs:
                self.assertNotIn(
                    rung.id, items.BY_ID,
                    f"{rung.id} exists in items.py too; one of them will win "
                    f"and nobody will know which")


# ---------------------------------------------------------------------------
# 5. THE ART LADDER
# ---------------------------------------------------------------------------

class Art(GameTest):
    """The Python side of the art contract. The rendered-pixel half lives in
    scripts/verify/forge.mjs and scripts/verify/forgehero.mjs, which raster the
    sprites and count colours; what can be checked here is that the data those
    scripts read actually describes nine different objects."""

    def test_every_rung_has_a_distinct_art_spec(self):
        for blade in forge.BLADES:
            seen = {}
            for rung in blade.rungs:
                key = tuple(sorted(rung.art.items()))
                self.assertNotIn(
                    key, seen,
                    f"{blade.id} t{rung.tier} is drawn identically to "
                    f"t{seen.get(key)}")
                seen[key] = rung.tier

    def test_every_rung_says_what_changed_on_the_sprite(self):
        for blade in forge.BLADES:
            looks = set()
            for rung in blade.rungs:
                self.assertTrue(rung.look.strip(),
                                f"{blade.id} t{rung.tier} has no look line")
                looks.add(rung.look)
            self.assertEqual(
                len(blade.rungs), len(looks),
                f"{blade.id} describes two rungs the same way")

    def test_the_hero_sprite_rung_never_goes_backwards(self):
        for blade in forge.BLADES:
            rungs = [r.hero["rung"] for r in blade.rungs]
            self.assertEqual(sorted(rungs), rungs,
                             f"{blade.id}: the held sprite got worse")
            self.assertGreater(
                len(set(rungs)), 1,
                f"{blade.id}: nine tiers and one sprite rung")

    def test_the_art_vocabulary_is_the_shared_one(self):
        for blade in forge.BLADES:
            self.assertIn(blade.shape, forge.WEAPON_SHAPES)
            self.assertIn(blade.hero_key, items.HERO_WEAPON_KEYS)
            for rung in blade.rungs:
                self.assertIn(rung.art["material"], forge.LOOTART_MATERIALS)
                self.assertIn(rung.art["motif"],
                              set(forge.ART_MOTIFS) | {"none"})
                self.assertIn(rung.art["aura"], set(forge.ART_AURAS) | {"none"})

    def test_six_lines_are_six_objects(self):
        """Six classes, six weapons a player can tell apart across a room. The
        tint is the cheapest way two lines end up reading as one, because the
        shape table is shared — four shapes carry the six lines."""
        self.assertEqual(6, len(forge.BLADES))
        self.assertEqual(6, len({b.id for b in forge.BLADES}))
        self.assertEqual(6, len({b.tint for b in forge.BLADES}),
                         "two lines share a tint and will read as one weapon")
        self.assertEqual(6, len({b.technique for b in forge.BLADES}),
                         "two lines share a technique name")


# ---------------------------------------------------------------------------
# 6. THE BAG SURVIVES, AND NEVER LIES
# ---------------------------------------------------------------------------

class Persistence(GameTest):

    def test_metals_and_tiers_survive_a_save_slot_round_trip(self):
        conn = saves.connect(self.data_dir / "save.sqlite3")
        state = saves.normalize({})
        bag = state.setdefault("forge", forge.new_state())
        forge.grant_blade(bag, "tracing_needle")
        bag["tiers"]["tracing_needle"] = 6
        forge.add_metal(bag, "nullsteel", 17)
        forge.add_metal(bag, "tilegold", 4)
        bag["racked"] = "tracing_needle"
        bag["forged"] = 5

        saves.apply_state(conn, state)
        saves.save_to_slot(conn, 1, state, name="the forge")

        sid = saves.slot_id(saves.KIND_MANUAL, 1)
        restored = saves.load_slot(conn, sid)
        back = restored["state"]["forge"]

        # And off the RAW stored payload, before normalize() has touched it.
        # load_slot() merges over engine.DEFAULT_STATE, so a bag reconstructed
        # by that merge would pass the assertions below while the slot on disk
        # held nothing. This is the assertion that says the metal was written.
        stored = saves.read_slot(conn, sid)["state"]["forge"]
        self.assertEqual(17, forge.held(stored, "nullsteel"))
        self.assertEqual(6, forge.owned_tier(stored, "tracing_needle"))

        self.assertEqual(17, forge.held(back, "nullsteel"))
        self.assertEqual(4, forge.held(back, "tilegold"))
        self.assertEqual(6, forge.owned_tier(back, "tracing_needle"))
        self.assertEqual("tracing_needle", back.get("racked"))
        self.assertEqual(5, back.get("forged"))

    def test_a_forge_state_is_json_shaped(self):
        """A save is JSON. A dataclass or a set in here loses the bag silently."""
        import json
        state = forge.new_state()
        forge.add_metal(state, "fieldiron", 3)
        forge.grant_blade(state, "draft_axe")
        self.assertEqual(state, json.loads(json.dumps(state)))

    def test_an_old_save_with_no_forge_block_still_boots(self):
        state = saves.normalize({"level": 3})
        self.assertIn("forge", state)
        self.assertEqual(0, forge.owned_tier(state["forge"], "draft_axe"))

    def test_a_refused_upgrade_never_takes_a_single_bar(self):
        """The bug this pins: upgrade() used to take the direct cost, then
        notice substitution was forbidden, then return an error — leaving the
        player's metal gone and the rung where it was."""
        for blade in forge.BLADES:
            for tier in range(forge.MIN_TIER, forge.MAX_TIER):
                state = forge.new_state()
                forge.grant_blade(state, blade.id)
                state["tiers"][blade.id] = tier
                # Enough top metal to cover by substitution, and some of the
                # rung's own metals, so both spend paths are live.
                forge.add_metal(state, "nullsteel", 500)
                for metal_id in forge.rung(blade.id, tier + 1).cost:
                    forge.add_metal(state, metal_id, 2)
                before = copy.deepcopy(state["metals"])
                result = forge.upgrade(state, blade.id, gold=10 ** 6,
                                       allow_substitution=False)
                if result.get("error"):
                    self.assertEqual(
                        before, state["metals"],
                        f"{blade.id} t{tier}->{tier + 1}: a refusal ate metal")
                    self.assertEqual(
                        tier, forge.owned_tier(state, blade.id),
                        f"{blade.id}: the rung moved on a refusal")

    def test_the_bag_can_never_go_negative(self):
        """The other half of the same bug: substitution planned against the raw
        bag, so a metal on both sides of one bill — Quarterturn Bronze paying its
        own line AND being beaten down into the Marshsilver the player never had
        — was spent twice, and the bag settled at minus seven."""
        rng = random.Random(99)
        for _ in range(4000):
            blade = rng.choice(forge.BLADES)
            tier = rng.randint(forge.MIN_TIER, forge.MAX_TIER - 1)
            state = forge.new_state()
            forge.grant_blade(state, blade.id)
            state["tiers"][blade.id] = tier
            for metal in forge.METALS:
                if rng.random() < 0.6:
                    forge.add_metal(state, metal.id,
                                    rng.choice([1, 4, 9, 20, 45]))
            forge.upgrade(state, blade.id, gold=10 ** 6,
                          allow_substitution=rng.random() < 0.8)
            negative = {k: v for k, v in state["metals"].items() if v < 0}
            self.assertEqual({}, negative, "the bag went negative")

    def test_what_was_spent_equals_what_left_the_bag(self):
        rng = random.Random(1234)
        for _ in range(2000):
            blade = rng.choice(forge.BLADES)
            tier = rng.randint(forge.MIN_TIER, forge.MAX_TIER - 1)
            state = forge.new_state()
            forge.grant_blade(state, blade.id)
            state["tiers"][blade.id] = tier
            for metal in forge.METALS:
                forge.add_metal(state, metal.id, rng.choice([0, 6, 18, 40]))
            before = copy.deepcopy(state["metals"])
            result = forge.upgrade(state, blade.id, gold=10 ** 6)
            if result.get("error"):
                continue
            moved = {k: before.get(k, 0) - state["metals"].get(k, 0)
                     for k in before}
            self.assertEqual(
                {k: v for k, v in moved.items() if v},
                {k: v for k, v in result["spent"].items() if v},
                "the receipt and the bag disagree")

    def test_a_quote_that_says_ready_is_always_payable(self):
        rng = random.Random(555)
        for _ in range(3000):
            blade = rng.choice(forge.BLADES)
            tier = rng.randint(forge.MIN_TIER, forge.MAX_TIER - 1)
            state = forge.new_state()
            forge.grant_blade(state, blade.id)
            state["tiers"][blade.id] = tier
            for metal in forge.METALS:
                if rng.random() < 0.7:
                    forge.add_metal(state, metal.id, rng.randint(0, 40))
            quote = forge.quote(state, blade.id, gold=10 ** 6)
            if not quote.get("ready"):
                continue
            result = forge.upgrade(state, blade.id, gold=10 ** 6)
            self.assertIsNone(
                result.get("error"),
                "the smith quoted an upgrade she then refused to make")
            self.assertEqual(tier + 1, forge.owned_tier(state, blade.id))

    def test_an_upgrade_moves_exactly_one_rung(self):
        state = forge.new_state()
        forge.grant_blade(state, "recall_chain")
        for metal in forge.METALS:
            forge.add_metal(state, metal.id, 10 ** 4)
        for tier in range(forge.MIN_TIER, forge.MAX_TIER):
            result = forge.upgrade(state, "recall_chain", gold=10 ** 7)
            self.assertIsNone(result.get("error"), result.get("error"))
            self.assertEqual(tier + 1, result["tier"])
        self.assertEqual("at_top",
                         forge.upgrade(state, "recall_chain",
                                       gold=10 ** 7).get("error"))

    def test_racking_a_blade_keeps_its_rung(self):
        """A forge does not un-forge anything: trying a found weapon must not
        cost the rungs somebody ground four hundred encounters for."""
        state = forge.new_state()
        forge.grant_blade(state, "boundary_maul")
        state["tiers"]["boundary_maul"] = 7
        forge.rack(state, "boundary_maul")
        self.assertEqual(7, forge.owned_tier(state, "boundary_maul"))
        forge.unrack(state)
        self.assertEqual(7, forge.owned_tier(state, "boundary_maul"))
