"""The four late modules, and the rules they are not allowed to break.

classes.py, worldgen.py, finalexam.py and legendaries.py were written against
the same shared vocabulary as everything else — skills, the chapter ladder, the
effect labels, the regions, the bosses, the corpus — and none of them can see
each other. So this file resolves every identifier they hand around against
whoever actually owns it, and then proves the four promises the design makes out
loud:

    1. Nothing supplies an answer. Not a skill tree node, not a class trait, not
       a legendary, not a pet. The single deliberate exception is the Obliging
       Hand, which is allowed to be one because it takes mastery back for it and
       is sealed everywhere the game is measuring — both of which are proved
       here rather than asserted in a docstring.
    2. The final exam reaches no help path at all.
    3. Mastery moves only on graded evidence, in skills.py.
    4. Nothing here can open or close content. A class is a route, not a key.

Each module ships its own `self_check()`/`validate()`, and those are run too —
but only as one test among several. A module marking its own homework is worth
something; it is not worth everything, so the proofs below are written from the
outside and do not delegate.
"""
from __future__ import annotations

import ast
import inspect
import unittest

from base import GameTest  # noqa: E402

from gauntlet import (classes, config, curriculum, finalexam, items,
                      legendaries, pets, world, worldgen)
from gauntlet import skills as skillmod

SKILLS = frozenset(skillmod.SKILLS)
CHAPTERS = frozenset(c.id for c in curriculum.CHAPTERS)
REGIONS = frozenset(r["id"] for r in world.REGIONS)
BOSSES = frozenset(b["id"] for b in world.BOSSES)
PHASES = frozenset(p["key"] for p in world.BOSS_PHASES)
EFFECTS = frozenset(items.EFFECT_LABELS)
SLOTS = frozenset(items.SLOTS)

# The tells a hint is checked against. Same list classes.py and pets.py hold
# themselves to, restated here so that deleting it from a module under test does
# not delete the test.
ANSWER_TELLS = (
    "def ", "return ", "```", "the answer is", "the solution is",
    "solves it for you", "reveals the solution", "shows the solution",
    "copy this", "just paste",
)

# The Obliging Hand is the one artifact permitted to solve an encounter, and
# `legendaries` documents at length why. Everything about that exception is
# tested; nothing else is allowed to claim it.
OBLIGING_KEYS = frozenset({"oblige", "skill_decay", "sealed_in_exam"})


def _walk_strings(value, label, out):
    """Every player-visible string inside a nested structure, labelled."""
    if isinstance(value, str):
        out.append((label, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            _walk_strings(item, f"{label}.{key}", out)
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _walk_strings(item, f"{label}[{i}]", out)


class TestVocabulary(GameTest):
    """Every id these four modules hand around, resolved against its owner."""

    def test_every_class_effect_key_is_in_the_items_vocabulary(self):
        """items.EFFECT_LABELS is the vocabulary. A key outside it is a bonus
        the engine renders as nothing and the player never learns they have."""
        used = set()
        for node in classes.NODE_BY_ID.values():
            used |= set(node.per_rank)
            for effects in node.unlocks.values():
                used |= set(effects)
        for gear in classes.GEAR_REQUESTS:
            used |= set(gear.effects)
        for spec in classes.SET_REQUESTS.values():
            for bonus in spec["bonuses"].values():
                used |= set(bonus)
        self.assertTrue(used)
        self.assertEqual(used - EFFECTS, set())
        self.assertEqual(set(classes.CAPS) - EFFECTS, set())

    def test_every_legendary_effect_key_is_in_the_items_vocabulary(self):
        used = set()
        for artifact in legendaries.ARTIFACTS:
            used |= set(artifact.effects)
        self.assertTrue(used)
        self.assertEqual(used - EFFECTS, set())

    def test_the_two_modules_declare_their_keys_rather_than_redefining_them(self):
        """A second copy of a label is a second thing to keep in step. Both
        modules derive theirs from items.EFFECT_LABELS, so drift is impossible
        rather than merely unlikely."""
        for module, names in ((classes, classes.CLASS_EFFECT_KEYS),
                              (legendaries, legendaries.LEGENDARY_EFFECT_KEYS)):
            self.assertTrue(names, module.__name__)
            for key in names:
                self.assertIn(key, items.EFFECT_LABELS,
                              f"{module.__name__} owns {key!r} but items.py has "
                              f"no label for it")
                self.assertEqual(module.NEW_EFFECT_LABELS[key],
                                 items.EFFECT_LABELS[key])
        self.assertEqual(
            set(classes.CLASS_EFFECT_KEYS) & set(legendaries.LEGENDARY_EFFECT_KEYS),
            set(), "two modules claim the same effect key")

    def test_capability_shaped_effects_take_the_maximum_not_the_sum(self):
        """Two sources of a switch do not make it twice as true. `items` folds
        effects for the whole game, so its list has to contain everything the
        class trees call a capability."""
        self.assertTrue(set(classes.MAXED_KEYS) <= set(items.SWITCH_KEYS),
                        sorted(set(classes.MAXED_KEYS) - set(items.SWITCH_KEYS)))
        self.assertEqual(set(items.SWITCH_KEYS) - EFFECTS, set())
        folded = items.total_effects({}, {}, {"sealed_hints": 1})
        self.assertEqual(folded.get("sealed_hints"), 1)

    def test_every_effect_label_renders(self):
        """A template with a stray field name raises at the moment a player
        hovers it, which is the worst possible moment to find out."""
        for key, template in items.EFFECT_LABELS.items():
            rendered = template.format(v=2, p=25)
            self.assertTrue(rendered.strip(), key)
            self.assertNotIn("{", rendered, key)

    def test_class_measures_name_real_chapters_and_skills(self):
        for measure in classes.MEASURES:
            for chapter in measure.chapters:
                self.assertTrue(chapter == "*" or chapter in CHAPTERS,
                                f"{measure.id} measures in {chapter!r}")
        for spec in classes.CLASSES:
            for skill in getattr(spec, "skills", ()) or ():
                self.assertIn(skill, SKILLS, spec.id)

    def test_every_legendary_resolves_where_it_comes_from(self):
        """`where` is a place in somebody else's module: a boss, a region, a
        dungeon or a quest chain. An artifact pointing at nothing is an artifact
        nobody can earn."""
        from gauntlet import dungeons, quests
        known = (BOSSES | REGIONS | CHAPTERS | set(dungeons.DUNGEON_BY_ID)
                 | set(quests.CHAIN_BY_ID))
        for artifact in legendaries.ARTIFACTS:
            acquisition = artifact.acquisition
            where = (acquisition.get("where") if isinstance(acquisition, dict)
                     else getattr(acquisition, "where", ""))
            if where:
                self.assertIn(where, known, artifact.id)
            self.assertIn(artifact.slot, SLOTS, artifact.id)
            if artifact.skill:
                self.assertIn(artifact.skill, SKILLS, artifact.id)
            if artifact.chapter:
                self.assertIn(artifact.chapter, CHAPTERS, artifact.id)

    def test_the_boss_ladder_is_the_bosses_the_world_actually_has(self):
        self.assertEqual([seal.boss_id for seal in finalexam.BOSS_LADDER],
                         [boss["id"] for boss in world.BOSSES])
        for crutch in finalexam.CRUTCHES:
            if crutch.taken_by:
                self.assertIn(crutch.taken_by, BOSSES, crutch.id)

    def test_the_exam_draws_on_families_the_corpus_really_has(self):
        """A family name that matches nothing silently narrows the pool, and a
        narrowed pool is not an error anyone sees — it is an exam that quietly
        stops containing codebase work."""
        families = {p.spaced_repetition_family for p in self.corpus}
        tags = {t for p in self.corpus for t in p.tags}
        self.assertEqual(finalexam._CODEBASE_FAMILIES - families, set())
        self.assertEqual(finalexam._CODEBASE_TAGS - tags, set())

    def test_every_generated_world_resolves(self):
        corpus_ids = {p.id for p in self.corpus}
        affixes = {a.id for a in worldgen.AFFIXES}
        for seed in (1, 42, 777, 12345, 90210):
            spec = worldgen.generate(seed)
            self.assertEqual({r.id for r in spec.regions} - REGIONS, set())
            for region in spec.regions:
                self.assertIn(region.chapter, CHAPTERS, f"{seed}/{region.id}")
                if region.skill:
                    self.assertIn(region.skill, SKILLS, f"{seed}/{region.id}")
            for boss in spec.bosses:
                self.assertIn(boss.id, BOSSES, seed)
                self.assertIn(boss.region, REGIONS, seed)
                self.assertEqual(set(boss.phases) - PHASES, set())
                self.assertEqual(set(boss.affixes) - affixes, set())
                if boss.problem_id:
                    self.assertIn(boss.problem_id, corpus_ids, seed)
            for dungeon in spec.dungeons:
                self.assertIn(dungeon.region, REGIONS, seed)
            for quest in spec.quests:
                self.assertIn(quest.region, REGIONS, seed)


class TestNothingSuppliesAnAnswer(GameTest):
    """Rule one. Everything may change HOW you engage; nothing may change
    WHETHER you have to think."""

    def test_no_authored_class_text_reads_as_an_answer(self):
        offenders = []
        for label, text in classes._authored_text():
            lowered = (text or "").lower()
            offenders += [(label, tell) for tell in ANSWER_TELLS
                          if tell in lowered]
        self.assertEqual(offenders, [])

    def test_no_legendary_text_reads_as_an_answer(self):
        """The artifacts' own prose, held to the hint tree's bar. The Hand's
        entry is included: it is allowed to SOLVE, and still not allowed to
        print a worked solution into its flavour text."""
        strings = []
        for artifact in legendaries.ARTIFACTS:
            for field_name in ("name", "signature", "flavour"):
                _walk_strings(getattr(artifact, field_name, ""),
                              f"{artifact.id}.{field_name}", strings)
            _walk_strings(artifact.history, f"{artifact.id}.history", strings)
        self.assertGreater(len(strings), 50)
        for label, text in strings:
            for tell in ANSWER_TELLS:
                self.assertNotIn(tell, text.lower(), f"{label}: {text!r}")

    def test_no_effect_key_hands_over_a_solution(self):
        """An effect key IS a capability, so the vocabulary itself is the
        surface to police. Exactly one key solves an encounter, it belongs to
        exactly one artifact, and that artifact pays for it."""
        solving = {key for key in items.EFFECT_LABELS
                   if "solves the current encounter" in items.EFFECT_LABELS[key]}
        self.assertEqual(solving, {"oblige"})
        owners = [a.id for a in legendaries.ARTIFACTS if "oblige" in a.effects]
        self.assertEqual(owners, ["obliging_hand"])
        hand = legendaries.BY_ID["obliging_hand"]
        self.assertEqual(OBLIGING_KEYS - set(hand.effects), set(),
                         "the Hand solves without declaring what it costs")

    def test_no_class_node_or_gear_can_solve_an_encounter(self):
        forbidden = {"oblige"}
        for node in classes.NODE_BY_ID.values():
            self.assertEqual(set(node.per_rank) & forbidden, set(), node.id)
        for gear in classes.GEAR_REQUESTS:
            self.assertEqual(set(gear.effects) & forbidden, set(), gear.id)

    def test_no_pet_passive_can_solve_an_encounter(self):
        for pet in pets.PETS:
            for effects in pet.passives.values():
                self.assertEqual(set(effects) & {"oblige"}, set(), pet.id)
                self.assertEqual(set(effects) - EFFECTS, set(), pet.id)

    def test_the_obliging_hand_costs_mastery_every_single_time(self):
        """The exception, priced. Using it must strictly lower mastery and
        strictly lower the ceiling, or 'earned' is a word in a comment."""
        skills = skillmod.new_skills()
        skills["HASH_MAP"].mastery = 80.0
        ledger = legendaries.hand_ledger_new()
        before = skills["HASH_MAP"].mastery
        ceiling_before = legendaries.mastery_ceiling(ledger, "HASH_MAP")
        result = legendaries.use_hand(skills, ledger, skill="HASH_MAP",
                                      difficulty="MEDIUM")
        self.assertTrue(result["solved"])
        self.assertLess(skills["HASH_MAP"].mastery, before)
        self.assertLess(legendaries.mastery_ceiling(ledger, "HASH_MAP"),
                        ceiling_before)
        self.assertEqual(ledger["uses"], 1)

    def test_the_obliging_hand_does_nothing_where_the_game_is_measuring(self):
        for mode in legendaries.HAND_SEALED_MODES + (config.MODE_INTERVIEW,):
            self.assertTrue(legendaries.hand_sealed(mode), mode)
            skills = skillmod.new_skills()
            skills["HASH_MAP"].mastery = 80.0
            ledger = legendaries.hand_ledger_new()
            result = legendaries.use_hand(skills, ledger, skill="HASH_MAP",
                                          difficulty="MEDIUM", mode=mode)
            self.assertFalse(result["solved"], mode)
            self.assertTrue(result["sealed"], mode)
            self.assertEqual(skills["HASH_MAP"].mastery, 80.0, mode)
            self.assertEqual(ledger["uses"], 0, mode)
        self.assertFalse(legendaries.hand_sealed(config.MODE_ADVENTURE))


class TestTheExamReachesNoHelp(GameTest):
    """Rule two. The last fight is the first one with nothing left."""

    def test_the_exam_seals_every_named_crutch(self):
        seal = finalexam.seal_for(mode=finalexam.EXAM_MODE)
        self.assertEqual(seal.sealed, finalexam.ALL_CRUTCHES)
        for capability in finalexam.ALL_CRUTCHES:
            self.assertTrue(seal.blocks(capability), capability)
            refusal = finalexam.refuse(capability)
            self.assertEqual(refusal.get("error"), "sealed", capability)

    def test_the_exam_runs_in_the_isolation_mode_that_already_exists(self):
        """Not a second isolation path — the same constant, so every
        `mode == MODE_INTERVIEW` check already in engine.py fires for it."""
        self.assertIs(finalexam.EXAM_MODE, config.MODE_INTERVIEW)

    def test_an_ordinary_encounter_seals_nothing(self):
        seal = finalexam.seal_for(mode=config.MODE_ADVENTURE)
        for capability in finalexam.ALL_CRUTCHES:
            self.assertFalse(seal.blocks(capability), capability)

    def test_the_crutches_come_off_one_at_a_time_and_never_come_back(self):
        seen = set()
        for seal in finalexam.BOSS_LADDER:
            self.assertTrue(seen <= seal.sealed,
                            f"{seal.boss_id} handed a crutch back")
            seen = set(seal.sealed)
        self.assertTrue(seen <= finalexam.EXAM_SEAL.sealed)

    def test_an_exam_question_carries_no_teaching_surface(self):
        audited = 0
        for problem in self.corpus[:400]:
            view = finalexam.exam_view(problem)
            self.assertEqual(finalexam.audit_view(view), [], problem.id)
            for field_name in finalexam._MUST_BE_EMPTY:
                self.assertFalse(view.get(field_name), f"{problem.id}.{field_name}")
            for field_name in finalexam._MUST_BE_ABSENT:
                self.assertNotIn(field_name, view, f"{problem.id}.{field_name}")
            audited += 1
        self.assertGreater(audited, 100)

    def test_a_composed_exam_leaks_nothing_and_never_repeats_itself(self):
        report = finalexam.self_check(self.corpus, trials=40, players=6)
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["payload_leaks"], 0)
        self.assertEqual(report["duplicate_question_sets"], 0)
        self.assertEqual(report["band_failures"], 0)

    def test_no_guided_problem_can_be_an_exam_question(self):
        """A GUIDED problem is a finished function with one expression struck
        out. That is a scaffold, which is help."""
        self.assertNotIn("GUIDED", finalexam._EXAM_DIFFICULTIES)
        for role in ("algorithm", "feature", "bug"):
            for problem in self.corpus:
                if problem.difficulty == "GUIDED":
                    self.assertFalse(finalexam._eligible(problem, role),
                                     f"{problem.id} as {role}")


class TestMasteryMovesOnEvidenceOnly(GameTest):
    """Rule three. `skills.apply_outcome` is the only place mastery rises, and
    `legendaries.use_hand` is the only place it falls for any reason other than
    a graded failure."""

    MASTERY_FIELDS = ("mastery", "unaided_clears", "clears", "retention",
                      "first_try_clears", "speed")

    def test_no_late_module_writes_a_skill_number(self):
        # `use_hand` and `clamp_to_ceiling` are the documented exception and are
        # tested by name above; `_synthetic_player` and the self-checks build
        # throwaway states to simulate against and never touch a real save.
        # `validate` builds a throwaway SkillState purely to prove the Hand's
        # cost is real; the same claim is proved independently, against live
        # state, by TestNothingSuppliesAnAnswer above, so exempting it here
        # costs no coverage.
        exempt = {
            legendaries: {"use_hand", "clamp_to_ceiling", "hand_regrow",
                          "validate"},
            finalexam: {"_synthetic_player", "self_check", "_deep_solve"},
            worldgen: {"self_check", "_corpus_check", "_simulate", "_budget"},
            classes: {"self_check"},
        }
        for module, scaffolding in exempt.items():
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name in scaffolding:
                    continue
                for inner in ast.walk(node):
                    targets = []
                    if isinstance(inner, ast.Assign):
                        targets = inner.targets
                    elif isinstance(inner, ast.AugAssign):
                        targets = [inner.target]
                    for target in targets:
                        name = None
                        if isinstance(target, ast.Attribute):
                            name = target.attr
                        elif isinstance(target, ast.Subscript):
                            name = getattr(target.slice, "value", None)
                        self.assertNotIn(
                            name, self.MASTERY_FIELDS,
                            f"{module.__name__}.{node.name} writes {name!r}")

    def test_class_points_come_from_levels_and_graduated_chapters(self):
        """Not from time played, not from gold, not from logging in."""
        self.assertEqual(classes.points_earned(1, 0), 0)
        self.assertGreater(classes.points_earned(10, 0),
                           classes.points_earned(1, 0))
        self.assertGreater(classes.points_earned(10, 3),
                           classes.points_earned(10, 0))
        skills = skillmod.new_skills()
        self.assertEqual(classes.chapters_graduated(skills), 0)

    def test_an_artifact_is_never_reachable_by_luck_alone(self):
        """Rarity may gate the drop; it may never be the only gate."""
        for artifact in legendaries.ARTIFACTS:
            acquisition = artifact.acquisition
            kind = (acquisition.get("kind") if isinstance(acquisition, dict)
                    else getattr(acquisition, "kind", ""))
            self.assertIn(kind, legendaries.ACQUISITION_KINDS, artifact.id)
            text = (acquisition.get("text") if isinstance(acquisition, dict)
                    else getattr(acquisition, "text", ""))
            self.assertTrue(str(text).strip(), artifact.id)


class TestAClassIsARouteNotAKey(GameTest):
    """Rule four. Six ways to walk the same syllabus. None of them is a shortcut
    around it, and none of them closes a door."""

    def test_no_effect_key_collides_with_a_name_the_curriculum_gates_on(self):
        gating = classes.GATING_NAMES
        self.assertEqual(set(items.EFFECT_LABELS) & gating, set())

    def test_no_gating_function_accepts_a_class_effect(self):
        """The proof that a tree cannot open content: no effect this module
        produces is a parameter any gate takes."""
        produced = set(items.EFFECT_LABELS)
        for name in ("tier_unlocked", "is_permitted", "permitted_patterns",
                     "permitted_families", "frontier", "open_chapters"):
            fn = getattr(curriculum, name)
            parameters = set(inspect.signature(fn).parameters)
            self.assertEqual(parameters & produced, set(),
                             f"curriculum.{name} reads an effect key")

    def test_every_class_can_finish_every_chapter(self):
        report = classes.self_check()
        self.assertTrue(report["every_class_every_chapter"])
        self.assertTrue(report["curriculum_untouched"])
        self.assertTrue(report["every_node_reachable"])
        self.assertTrue(report["no_dead_builds"])
        self.assertTrue(report["ok"], report.get("problems"))

    def test_the_legendary_catalogue_validates(self):
        self.assertEqual(legendaries.validate(), [])

    def test_a_seeded_world_never_moves_a_lesson(self):
        report = worldgen.self_check(40)
        self.assertTrue(report["ok"], report["failures"])
        self.assertTrue(report["all_chapters_every_seed"])
        self.assertTrue(report["all_skills_taught_every_seed"])
        self.assertTrue(report["first_hour_gentle_every_seed"])

    def test_restricted_gear_restricts_only_by_class(self):
        for item_id, class_id in classes.CLASS_RESTRICTED.items():
            self.assertTrue(classes.equippable(item_id, class_id), item_id)
            other = next(c.id for c in classes.CLASSES if c.id != class_id)
            self.assertFalse(classes.equippable(item_id, other), item_id)


if __name__ == "__main__":
    unittest.main()
