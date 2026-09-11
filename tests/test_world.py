"""The world layer: pets, dungeons, quests, progression, saves.

Five modules were written in parallel by people who could not see each other
work, so the failure this file is built to catch is not "does it run" but "do
they mean the same thing by the same word". Every id one module hands another is
resolved here against whoever actually owns it:

    region      world.REGIONS          boss        world.BOSSES
    chapter     curriculum.CHAPTERS    skill       skills.SKILLS
    item        items.BY_ID            effect      items.EFFECT_LABELS
    consumable  items.CONSUMABLES      puzzle      puzzles.PUZZLE_KINDS
    dungeon     dungeons.DUNGEON_BY_ID pet         pets.PET_IDS
    quest       quests.QUEST_BY_ID     family      the corpus

The other three groups are the promises the design makes out loud: learning
never dead-ends, the rules of the game are not negotiable, and a save is either
loaded whole or not loaded at all. Those are simulated rather than asserted —
a property nobody has tried to break is a property nobody knows they have.
"""
from __future__ import annotations

import copy
import random
import unittest
from collections import Counter

from base import GameTest  # noqa: E402

from gauntlet import config, curriculum, items, puzzles, story, world
from gauntlet import skills as skillmod
from gauntlet import dungeons, pets, progression, quests, saves

REGIONS = {r["id"] for r in world.REGIONS}
BOSSES = {b["id"] for b in world.BOSSES}
CHAPTERS = set(curriculum.CHAPTER_BY_ID)
SKILLS = set(skillmod.SKILLS)
ITEMS = set(items.BY_ID)
CONSUMABLES = set(items.CONSUMABLES)
EFFECTS = set(items.EFFECT_LABELS)
PUZZLE_KINDS = set(puzzles.PUZZLE_KINDS)
MENTORS = set(world.MENTORS)
CARDS = set(story.GRIMOIRE_CARDS)
CODEX = set(story.CODEX)

# How hard the randomised parts get hammered. Generation is cheap — the whole
# file runs in a couple of seconds — so there is no reason to sample thinly.
SEEDS_PER_DUNGEON = 12
PROGRESSION_STATES = 400


def _flatten(gate):
    """Every leaf of a story.Trigger tree, including all_of/any_of children."""
    out = []
    if gate is None:
        return out
    if isinstance(gate, (list, tuple)):
        for part in gate:
            out += _flatten(part)
        return out
    out.append(gate)
    for part in getattr(gate, "parts", None) or ():
        out += _flatten(part)
    return out


def _needs(need):
    out = []
    if need is None:
        return out
    out.append(need)
    for part in getattr(need, "parts", None) or ():
        out += _needs(part)
    return out


# ---------------------------------------------------------------------------
# 1. The modules agree with the backend and with each other
# ---------------------------------------------------------------------------

class TestCrossModuleAgreement(GameTest):
    def setUp(self):
        super().setUp()
        self.families = Counter(p.spaced_repetition_family for p in self.corpus)

    # -- pets ---------------------------------------------------------------

    def test_pets_name_real_skills_regions_and_effects(self):
        for pet in pets.PETS:
            self.assertIn(pet.skill, SKILLS, pet.id)
            self.assertIn(pet.hint_kind, pets.HINT_KINDS, pet.id)
            self.assertIn(pet.discovery.region, REGIONS, pet.id)
            for rank, effects in pet.passives.items():
                self.assertIsInstance(rank, int, f"{pet.id}: {rank!r}")
                for key in effects:
                    self.assertIn(key, EFFECTS, f"{pet.id}: {key}")
            for trigger in pet.triggers:
                self.assertIn(trigger.kind, pets.TRIGGER_KINDS, pet.id)

    def test_pet_discovery_deeds_name_things_that_exist(self):
        """The deed is data, not just prose, so its ids have to resolve — this
        is where a region id sitting in a `dungeon` slot gets caught."""
        for pet in pets.PETS:
            for need in pet.discovery.needs:
                where = f"{pet.id}:{need.get('kind')}"
                self.assertIn(need.get("kind"), pets.DISCOVERY_CHECKS, where)
                if need.get("skill"):
                    self.assertIn(need["skill"], SKILLS, where)
                if need.get("boss"):
                    self.assertIn(need["boss"], BOSSES, where)
                if need.get("region"):
                    self.assertIn(need["region"], REGIONS, where)
                if need.get("dungeon"):
                    self.assertIn(need["dungeon"], dungeons.DUNGEON_BY_ID, where)
                if need.get("family"):
                    self.assertIn(need["family"], self.families, where)

    # -- dungeons -----------------------------------------------------------

    def test_dungeon_plans_name_real_regions_chapters_and_patterns(self):
        for plan in dungeons.DUNGEONS:
            self.assertIn(plan.region, REGIONS, plan.id)
            self.assertIn(plan.chapter, CHAPTERS, plan.id)
            self.assertIn(plan.archetype, dungeons.LAYOUT_BUILDERS, plan.id)
            self.assertIn(plan.rule, dungeons.LAYOUT_RULES, plan.id)
            self.assertIn(plan.floor, dungeons.DIFFICULTY_LADDER, plan.id)
            self.assertGreaterEqual(plan.floors, 1, plan.id)
            for codex in plan.codex:
                self.assertIn(codex, CODEX, plan.id)

    def test_generated_rooms_only_use_known_vocabulary(self):
        for plan in dungeons.DUNGEONS:
            for salt in range(4):
                built = dungeons.generate(
                    plan.id, seed=dungeons.dungeon_seed(plan.id, salt))
                for room in built.rooms:
                    where = f"{plan.id}#{salt}.{room.id}"
                    self.assertIn(room.kind, dungeons.ROOM_KINDS, where)
                    if room.shrine_skill:
                        self.assertIn(room.shrine_skill, SKILLS, where)
                    kind = (room.encounter or {}).get("puzzle_kind")
                    if kind:
                        self.assertIn(kind, PUZZLE_KINDS, where)

    def test_every_dungeon_sits_in_a_region_that_has_problems_to_serve(self):
        realms = {p.realm for p in self.corpus}
        for plan in dungeons.DUNGEONS:
            if plan.patterns:
                self.assertIn(plan.region, realms | {"coding_coliseum",
                                                     "null_kings_castle"}, plan.id)

    def test_rolled_treasure_never_invents_an_effect_or_an_item(self):
        rng = random.Random(11)
        for plan in dungeons.DUNGEONS:
            built = dungeons.generate(plan.id)
            for room in built.rooms:
                if not room.treasure:
                    continue
                drop = dungeons.roll_room_treasure(built, room, luck=0.5, rng=rng)
                if not drop:
                    continue
                if drop.get("id"):
                    self.assertIn(drop["id"], ITEMS | CONSUMABLES, plan.id)
                for key in drop.get("effects") or {}:
                    self.assertIn(key, EFFECTS, plan.id)

    # -- quests -------------------------------------------------------------

    def test_quests_name_real_regions_givers_and_chains(self):
        for quest in quests.QUESTS:
            self.assertIn(quest.region, REGIONS, quest.id)
            self.assertIn(quest.kind, quests.KINDS, quest.id)
            self.assertIn(quest.giver, set(quests.NPCS) | MENTORS, quest.id)
            if quest.chain:
                self.assertIn(quest.chain, quests.CHAIN_BY_ID, quest.id)

    def test_quest_objectives_resolve(self):
        for quest in quests.QUESTS:
            obj, where = quest.objective, quest.id
            if obj.get("family"):
                self.assertIn(obj["family"], self.families, where)
            if obj.get("skill"):
                self.assertIn(obj["skill"], SKILLS, where)
            if obj.get("puzzle"):
                self.assertIn(obj["puzzle"], PUZZLE_KINDS, where)
            if obj.get("dungeon"):
                self.assertIn(obj["dungeon"], dungeons.DUNGEON_BY_ID, where)

    def test_quest_rewards_resolve(self):
        for quest in quests.QUESTS:
            extras, where = quest.extras or {}, quest.id
            if extras.get("card"):
                self.assertIn(extras["card"], CARDS, where)
            if extras.get("codex"):
                self.assertIn(extras["codex"], CODEX, where)
            if extras.get("set_item"):
                self.assertIn(extras["set_item"], ITEMS, where)
            if extras.get("consumable"):
                self.assertIn(extras["consumable"]["id"], CONSUMABLES, where)
            if extras.get("pet"):
                self.assertIn(extras["pet"], quests.PET_DISCOVERIES, where)
            if extras.get("shortcut"):
                self.assertIn(extras["shortcut"], quests.SHORTCUTS, where)
            if extras.get("town_upgrade"):
                self.assertIn(extras["town_upgrade"], quests.TOWN_UPGRADES, where)
            if extras.get("incantation"):
                self.assertIn(extras["incantation"], quests.INCANTATION_GRANTS, where)
            if extras.get("favor"):
                self.assertIn(extras["favor"]["mentor"],
                              MENTORS | set(quests.NPCS), where)

    def test_quest_gates_resolve(self):
        for quest in quests.QUESTS:
            for gate in _flatten(quest.requires):
                where = f"{quest.id}:{gate.kind}"
                if gate.kind == "region_open":
                    self.assertIn(gate.key, REGIONS, where)
                elif gate.kind == "quest_done":
                    self.assertIn(gate.key, quests.QUEST_BY_ID, where)
                elif gate.kind in ("skill_mastery", "skill_clears", "skill_unaided"):
                    self.assertIn(gate.key, SKILLS, where)
                elif gate.kind == "chapter":
                    self.assertIn(gate.key, CHAPTERS, where)
                elif gate.kind == "dungeon_depth":
                    self.assertIn(gate.key, dungeons.DUNGEON_BY_ID, where)
                elif gate.kind == "pet_found":
                    self.assertIn(gate.key, quests.PET_DISCOVERIES, where)
                elif gate.kind == "puzzle_clears":
                    self.assertIn(gate.key, PUZZLE_KINDS, where)
                elif gate.kind == "stat":
                    self.assertIn(gate.key, quests._KNOWN_STATS, where)

    def test_town_upgrades_only_grant_effects_the_item_layer_knows(self):
        for uid, upgrade in quests.TOWN_UPGRADES.items():
            self.assertIn(upgrade["region"], REGIONS, uid)
            for key in upgrade.get("effects") or {}:
                self.assertIn(key, EFFECTS, uid)

    # -- progression --------------------------------------------------------

    def test_routes_and_events_name_real_places(self):
        for route in progression.ROUTES:
            self.assertIn(route.frm, REGIONS, route.id)
            self.assertIn(route.to, REGIONS, route.id)
            self._check_need(route.id, route.need)
        for event in progression.WORLD_EVENTS:
            self._check_need(event.id, event.need)
            for change in event.changes:
                where = f"{event.id}:{change.kind}"
                if change.kind == "region_state":
                    self.assertIn(change.target, REGIONS, where)
                elif change.kind == "dungeon":
                    self.assertIn(change.target, dungeons.DUNGEON_BY_ID, where)
                elif change.kind == "route_open":
                    self.assertIn(change.target, progression.ROUTE_BY_ID, where)
                elif change.kind == "boss":
                    self.assertIn(change.target, BOSSES, where)

    def _check_need(self, where, need):
        for part in _needs(need):
            if part.kind == "region":
                self.assertIn(part.key, REGIONS, where)
            elif part.kind == "boss":
                self.assertIn(part.key, BOSSES, where)
            elif part.kind == "chapter":
                self.assertIn(part.key, CHAPTERS, where)
            elif part.kind == "mastery":
                self.assertIn(part.key, SKILLS, where)
            elif part.kind == "dungeon":
                self.assertIn(part.key, dungeons.DUNGEON_BY_ID, where)
            elif part.kind == "event":
                self.assertIn(part.key, progression.EVENT_BY_ID, where)
            elif part.kind == "pet":
                self.assertIn(part.key, set(pets.PET_IDS), where)
            elif part.kind == "quest":
                self.assertIn(part.key, quests.QUEST_BY_ID, where)
            elif part.kind == "item":
                self.assertIn(part.key, ITEMS, where)

    def test_level_rewards_resolve(self):
        for level, grant in progression.LEVEL_MILESTONES.items():
            for key in grant.get("effects") or {}:
                self.assertIn(key, EFFECTS, str(level))
            if grant.get("item"):
                self.assertIn(grant["item"], ITEMS | CONSUMABLES, str(level))
        for cid in progression.CONSUMABLE_CYCLE:
            self.assertIn(cid, CONSUMABLES, cid)

    # -- the three views of the same thing ----------------------------------

    def test_there_is_exactly_one_dungeon_namespace(self):
        """Three modules used to keep three lists of dungeons with three sets of
        ids and three sets of names. The generator owns them; the other two hold
        views, and a view that disagrees with its source is the bug."""
        for plan in dungeons.DUNGEONS:
            quest_row = quests.DUNGEONS.get(plan.id)
            self.assertIsNotNone(quest_row, plan.id)
            self.assertEqual(quest_row["region"], plan.region, plan.id)
            self.assertEqual(quest_row["floors"], plan.floors, plan.id)
            self.assertEqual(quest_row["name"], plan.name, plan.id)
            world_row = progression.DUNGEON_BY_ID.get(plan.id)
            self.assertIsNotNone(world_row, plan.id)
            self.assertEqual(world_row["region"], plan.region, plan.id)
            self.assertEqual(world_row["floors"], plan.floors, plan.id)
            self.assertEqual(world_row["name"], plan.name, plan.id)
        self.assertEqual(set(quests.DUNGEONS), set(dungeons.DUNGEON_BY_ID))
        self.assertEqual(set(progression.DUNGEON_BY_ID), set(dungeons.DUNGEON_BY_ID))

    def test_there_is_exactly_one_pet_namespace(self):
        """Same story for the animals: quests and the map layer used to disagree
        with the pet system about which region four of them were hiding in."""
        for pet in pets.PETS:
            row = quests.PET_DISCOVERIES.get(f"pet_{pet.id}")
            self.assertIsNotNone(row, pet.id)
            self.assertEqual(row["pet"], pet.id)
            self.assertEqual(row["region"], pet.discovery.region, pet.id)
            self.assertEqual(row["condition"], pet.discovery.how, pet.id)
            world_row = progression.PET_BY_ID.get(pet.id)
            self.assertIsNotNone(world_row, pet.id)
            self.assertEqual(world_row["region"], pet.discovery.region, pet.id)
        self.assertEqual({r["pet"] for r in quests.PET_DISCOVERIES.values()},
                         set(pets.PET_IDS))

    def test_every_region_with_a_dungeon_is_a_region_that_exists(self):
        self.assertEqual(set(dungeons.DUNGEONS_BY_REGION) - REGIONS, set())

    def test_the_map_reads_the_state_the_other_modules_write(self):
        """Agreement about ids is half of it. The other half is agreeing about
        the SHAPE of the save: `pets.new_state()` is a dict with a `found` list
        in it, and quests keep their own ledger. A map screen that quietly shows
        no companions is what a shape disagreement looks like from the couch."""
        state = {
            "player": {"level": 5, "xp": 1000}, "skills": {},
            "cleared_bosses": [], "stats": {}, "unspent_points": 0,
            "story": {"fired": [], "chains": {}},
            "pets": pets.new_state(), "quests": quests.new_quest_state(),
            "dungeons_cleared": [], "world": progression.new_world_state(),
        }
        pets.grant(state["pets"], "jaguar")
        pets.grant(state["pets"], "crow")
        state["quests"]["done"] = ["village_beam_count", "fields_first_weeds"]
        snapshot = progression.snapshot(state)
        self.assertEqual(snapshot["pets"], {"jaguar", "crow"})
        self.assertEqual(snapshot["quests_done"], 2)
        # the older shapes a save may still be carrying
        self.assertEqual(progression.snapshot({**state, "pets": ["llama"]})["pets"],
                         {"llama"})
        self.assertEqual(
            progression.snapshot({**state,
                                  "pets": [{"id": "python", "found": True}]})["pets"],
            {"python"})

    def test_a_dungeon_run_drops_straight_into_a_save(self):
        """The run state is stored verbatim, so it has to be plain JSON."""
        import json
        built = dungeons.generate("ninth_cart")
        run = dungeons.enter(built, run_seed=5)
        dungeons.move(built, run, dungeons.options(built, run)[0]["room"])
        dungeons.clear_room(built, run, solved=True)
        restored = json.loads(json.dumps(run))
        self.assertEqual(restored, run)
        self.assertEqual(dungeons.STATE_KEY, "dungeon_run")
        rebuilt = dungeons.generate(run["dungeon"], seed=run["seed"])
        self.assertEqual(dungeons.progress(rebuilt, restored)["rooms"],
                         len(built.rooms))

    def test_the_modules_own_self_checks_still_pass(self):
        self.assertTrue(pets.self_check()["ok"])
        self.assertEqual(quests.validate(self.corpus), [])
        self.assertEqual(progression.verify_no_orphans()["orphans"], [])
        for plan in dungeons.DUNGEONS:
            self.assertTrue(dungeons.audit(dungeons.generate(plan.id))["ok"], plan.id)
        report = dungeons.self_check(runs=64)
        self.assertTrue(report["all_checks_passed"], report["failures"])
        self.assertEqual(report["regions_covered"], len(dungeons.DUNGEONS_BY_REGION))


# ---------------------------------------------------------------------------
# 2. Learning never dead-ends, proven by simulation
# ---------------------------------------------------------------------------

class TestNoDeadEnds(GameTest):
    def setUp(self):
        super().setUp()
        self.families = Counter(p.spaced_repetition_family for p in self.corpus)

    # -- the overworld ------------------------------------------------------

    def test_progression_always_offers_something_to_do(self):
        rng = random.Random(20260911)
        fewest = 99
        for index in range(PROGRESSION_STATES):
            state = progression._random_state(rng)
            progression.advance(state)
            todo = progression.things_to_do(state, due_retests=rng.randint(0, 3),
                                            limit=99)
            fewest = min(fewest, len(todo))
            self.assertTrue(todo, f"state {index}: nothing to do")
        self.assertGreaterEqual(fewest, 3)

    def test_the_two_states_random_sampling_never_reaches(self):
        """A brand new save and a finished one are the states most likely to
        have nothing left, and least likely to be drawn at random."""
        for state in (self._blank_state(), self._finished_state()):
            progression.advance(state)
            self.assertTrue(progression.things_to_do(state, limit=99))

    def _blank_state(self):
        return {"player": {"level": 1, "xp": 0}, "skills": {},
                "cleared_bosses": [], "quests_completed": [], "pets": [],
                "dungeons_cleared": [], "region": "python_village", "stats": {},
                "unspent_points": 0, "story": {"fired": [], "chains": {}},
                "world": progression.new_world_state()}

    def _finished_state(self):
        state = self._blank_state()
        state["player"] = {"level": 99, "xp": progression.total_xp_for(99)}
        state["cleared_bosses"] = [b["id"] for b in world.BOSSES]
        state["quests_completed"] = [q.id for q in quests.QUESTS]
        state["pets"] = [p.id for p in pets.PETS]
        state["dungeons_cleared"] = [d.id for d in dungeons.DUNGEONS]
        state["skills"] = {n: {"mastery": 100.0, "retention": 100.0,
                               "speed": 100.0, "clears": 999,
                               "unaided_clears": 999, "attempts": 999,
                               "stage": "MASTERED"} for n in SKILLS}
        return state

    def test_the_world_stays_connected_and_has_a_road_out(self):
        report = progression.self_check(trials=PROGRESSION_STATES)
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["min_mortal_regions_reachable"],
                         report["mortal_regions"])
        self.assertGreaterEqual(report["min_open_routes"], 1)

    # -- the quest board ----------------------------------------------------

    def test_every_quest_is_reachable_by_playing_forward(self):
        """Not "is there a state where this is available" — anyone can write
        that context. Start from an empty save, take whatever is offered, get a
        little stronger, and see whether all seventy-four ever come up."""
        ctx = self._empty_context()
        offered_at_least_once = set()
        for _ in range(60):
            fresh = [row["id"] for row in quests.available(ctx)
                     if row["id"] not in ctx["quests_done"]]
            offered_at_least_once |= set(fresh)
            for qid in fresh:
                ctx["quests_done"].add(qid)
                extras = quests.QUEST_BY_ID[qid].extras or {}
                for key, bucket in (("pet", "pets_found"),
                                    ("shortcut", "shortcuts"),
                                    ("town_upgrade", "town_upgrades")):
                    if extras.get(key):
                        ctx[bucket].add(extras[key])
            self._play_on(ctx)
        missed = {q.id for q in quests.QUESTS} - offered_at_least_once
        self.assertEqual(missed, set(), f"never offered: {sorted(missed)}")

    def test_no_quest_gate_can_close_behind_the_player(self):
        """Monotone play: nothing the player does makes them weaker, so no gate
        that was open may shut. A lock that can re-close is a dead end that
        happens later."""
        rng = random.Random(7)
        ctx = self._empty_context()
        was = {}
        closed = []
        for _ in range(25):
            for quest in quests.QUESTS:
                met = all(quests.need_met(gate, ctx) for gate in quest.requires)
                if was.get(quest.id) and not met:
                    closed.append(quest.id)
                was[quest.id] = met
            self._play_on(ctx, rng)
        self.assertEqual(closed, [])

    def test_no_quest_asks_for_more_than_the_world_contains(self):
        for quest in quests.QUESTS:
            obj = quest.objective
            if obj.get("dungeon"):
                plan = dungeons.DUNGEON_BY_ID[obj["dungeon"]]
                self.assertLessEqual(int(obj.get("depth", 0)), plan.floors,
                                     f"{quest.id}: no such floor")
                self.assertEqual(plan.region, quest.region, quest.id)
            if obj.get("family"):
                self.assertGreaterEqual(self.families[obj["family"]],
                                        int(obj.get("count", 1)), quest.id)

    def test_no_pet_deed_asks_for_more_than_the_world_contains(self):
        for pet in pets.PETS:
            for need in pet.discovery.needs:
                if need.get("kind") == "family_unaided":
                    self.assertGreaterEqual(self.families[need["family"]],
                                            need["count"], pet.id)
                if need.get("kind") == "dungeon_depth":
                    plan = dungeons.DUNGEON_BY_ID[need["dungeon"]]
                    self.assertLessEqual(need["depth"], plan.floors, pet.id)

    def _empty_context(self):
        return {
            "skills": {n: {"mastery": 0.0, "clears": 0, "unaided_clears": 0,
                           "attempts": 0, "retention": 0.0, "speed": 0.0,
                           "stage": "NOVICE"} for n in SKILLS},
            "regions_open": {"python_village"},
            "regions_entered": {"python_village"},
            "cleared_bosses": set(), "solved_count": 0, "level": 1,
            "stats": {k: 0 for k in quests._KNOWN_STATS},
            "gates_passed": 0, "gates_total": 13, "chapter_index": 0,
            "flags": set(), "events": set(),
            "favor": {m: 0 for m in MENTORS},
            "quests_done": set(), "quests_active": set(),
            "dungeon_depth": {}, "puzzle_clears": {}, "pets_found": set(),
            "shortcuts": set(), "town_upgrades": set(), "secrets_found": set(),
        }

    def _play_on(self, ctx, rng=None):
        """One session's worth of getting better at Python. Everything here only
        ever goes up, which is what makes the monotonicity test mean anything."""
        step = rng.randint(1, 3) if rng else 2
        ctx["level"] = min(99, ctx["level"] + step)
        ctx["solved_count"] += 25
        ctx["chapter_index"] = min(len(curriculum.CHAPTERS) - 1,
                                   ctx["chapter_index"] + 1)
        ctx["gates_passed"] = min(ctx["gates_total"], ctx["gates_passed"] + 1)
        for data in ctx["skills"].values():
            for key in ("mastery", "retention", "speed"):
                data[key] = min(100.0, data[key] + 6)
            data["clears"] += 3
            data["unaided_clears"] += 2
        for key in ctx["stats"]:
            ctx["stats"][key] += 3
        for mentor in ctx["favor"]:
            ctx["favor"][mentor] += 2
        ctx["puzzle_clears"] = {k: ctx["puzzle_clears"].get(k, 0) + 2
                                for k in PUZZLE_KINDS}
        ctx["dungeon_depth"] = {d.id: min(d.floors,
                                          ctx["dungeon_depth"].get(d.id, 0) + 2)
                                for d in dungeons.DUNGEONS}
        ctx["cleared_bosses"] |= {b["id"] for b in world.BOSSES
                                  if b["region"] in ctx["regions_open"]}
        ctx["regions_open"] |= set(world.unlocked_regions(
            quests._shim_skills(ctx), set(ctx["cleared_bosses"])))
        ctx["regions_entered"] |= ctx["regions_open"]

    # -- dungeons -----------------------------------------------------------

    def test_every_dungeon_holds_its_structural_promises(self):
        checked = 0
        for plan in dungeons.DUNGEONS:
            for salt in range(SEEDS_PER_DUNGEON):
                built = dungeons.generate(
                    plan.id, seed=dungeons.dungeon_seed(plan.id, salt))
                report = dungeons.audit(built)
                checked += 1
                self.assertTrue(report["checks"]["boss_path_exists"],
                                f"{plan.id}#{salt}")
                self.assertTrue(report["checks"]["boss_path_clearable"],
                                f"{plan.id}#{salt}")
                self.assertTrue(report["checks"]["exit_from_every_room"],
                                f"{plan.id}#{salt}")
                self.assertTrue(report["checks"]["keys_obtainable"],
                                f"{plan.id}#{salt}")
                self.assertTrue(report["checks"]["seal_satisfiable"],
                                f"{plan.id}#{salt}")
                self.assertTrue(report["ok"], f"{plan.id}#{salt}")
        self.assertEqual(checked, len(dungeons.DUNGEONS) * SEEDS_PER_DUNGEON)

    def test_a_dungeon_is_never_shallower_than_a_quest_may_demand(self):
        """`floors` is a promise other modules build objectives on, so it has to
        survive the layout dice rather than usually survive them."""
        for plan in dungeons.DUNGEONS:
            for salt in range(SEEDS_PER_DUNGEON * 2):
                built = dungeons.generate(
                    plan.id, seed=dungeons.dungeon_seed(plan.id, salt))
                self.assertGreaterEqual(built.max_depth, plan.floors,
                                        f"{plan.id}#{salt}")

    def test_a_dungeon_can_be_rebuilt_from_the_seed_it_reports(self):
        """A save stores the seed. If generation quietly used a different one the
        player would come back tomorrow to a different building."""
        for plan in dungeons.DUNGEONS:
            asked = dungeons.dungeon_seed(plan.id, 3)
            built = dungeons.generate(plan.id, seed=asked)
            self.assertEqual(built.seed, asked, plan.id)
            again = dungeons.generate(plan.id, seed=built.seed)
            self.assertEqual([r.name for r in again.rooms],
                             [r.name for r in built.rooms], plan.id)
            self.assertEqual(again.boss_room, built.boss_room, plan.id)

    def test_a_descent_reaches_the_boss_and_can_always_walk_back_out(self):
        for plan in dungeons.DUNGEONS:
            for salt in range(4):
                built = dungeons.generate(
                    plan.id, seed=dungeons.dungeon_seed(plan.id, salt))
                run = dungeons.simulate(built, run_seed=salt, fail_each=2)
                self.assertTrue(run["boss_reached"], f"{plan.id}#{salt}")
                self.assertGreaterEqual(run["exit_len"], 1, f"{plan.id}#{salt}")
                state = self._descend(built, salt)
                self.assertTrue(self._walk_out(built, state),
                                f"{plan.id}#{salt}: no legal way out")

    def test_a_room_never_offers_nothing(self):
        for plan in dungeons.DUNGEONS:
            built = dungeons.generate(plan.id)
            state = dungeons.enter(built)
            for room in built.rooms:
                state["at"] = room.id
                available = [o for o in dungeons.options(built, state)
                             if o["available"]]
                self.assertTrue(available, f"{plan.id}.{room.id}")

    def test_every_room_that_demands_solving_gets_a_real_problem(self):
        """A room that asks for something the corpus cannot serve is a wall with
        a story on it."""
        by_id = {p.id: p for p in self.corpus}
        for plan in dungeons.DUNGEONS:
            for salt in range(3):
                built = dungeons.generate(
                    plan.id, seed=dungeons.dungeon_seed(plan.id, salt))
                bound = dungeons.populate(built, self.corpus, skills=None)
                for room in built.rooms:
                    if not room.demands_solving or room.kind == "BOSS":
                        continue
                    where = f"{plan.id}#{salt}.{room.id}({room.kind})"
                    self.assertIn(str(room.id), bound, where)
                    self.assertIn(bound[str(room.id)], by_id, where)

    def _descend(self, built, salt):
        state = dungeons.enter(built, run_seed=salt)
        guard = len(built.rooms) * 8
        while guard > 0:
            guard -= 1
            room = built.rooms[state["at"]]
            if room.demands_solving and state["at"] not in state["cleared"] \
                    and room.kind != "BOSS":
                dungeons.clear_room(built, state, solved=True)
            elif not room.demands_solving and state["at"] not in state["cleared"]:
                state["cleared"].append(state["at"])
            onward = [o for o in dungeons.options(built, state)
                      if o["action"] == "move" and o["available"]
                      and o["room"] not in state["visited"]]
            if not onward:
                break
            dungeons.move(built, state, max(onward, key=lambda o: o["depth"])["room"])
        return state

    def _walk_out(self, built, state):
        for _ in range(len(built.rooms) * 8):
            if state["at"] == built.entrance:
                return True
            steps = [o for o in dungeons.options(built, state)
                     if o["action"] == "move" and o["available"]]
            if not steps:
                return False
            dungeons.move(built, state,
                          min(steps, key=lambda o: (o["depth"], o["room"]))["room"])
        return state["at"] == built.entrance


# ---------------------------------------------------------------------------
# 3. The rules, which are not negotiable
# ---------------------------------------------------------------------------

class TestTheRules(GameTest):
    def test_no_pet_line_contains_an_answer(self):
        """A pet intervention IS a hint, and a hint that states the answer is a
        cheat with a tail. Every authored line is checked against the same tells
        the hint tree is checked against."""
        report = pets.self_check()
        self.assertEqual(report["lines_reading_as_answers"], [])
        self.assertTrue(report["no_literal_answers"])
        # An EXACT_SYNTAX pet is allowed to show syntax — that is its whole
        # licence — so the bar is the pet module's own list of tells, which is
        # the same bar the hint tree is held to: no function header, no return
        # statement, no fenced block, nothing that says "the answer is".
        for pet in pets.PETS:
            for line in list(pet.hints.values()) + [pet.fallback]:
                for text in (line if isinstance(line, (list, tuple)) else [line]):
                    low = str(text).lower()
                    for tell in pets._ANSWER_TELLS:
                        self.assertNotIn(tell, low, f"{pet.id}: {text!r}")

    # Every measured signal a trigger can read, all shouting at once, so that
    # every pet has something to fire on. Key names are _fires()'s, not the
    # trigger kinds' — getting that wrong is how you write a test that passes
    # by returning None.
    LOUD = {
        "submitted": False, "seconds_elapsed": 900.0,
        "seconds_since_progress": 900.0, "failed_attempts": 9,
        "last_categories": ["OFF_BY_ONE"] * 6,
        "category_counts": {c: 9 for c in
                            ("PATTERN_NOT_RECOGNIZED", "SYNTAX", "OFF_BY_ONE",
                             "EMPTY_INPUT", "WRONG_STRUCTURE", "TIMEOUT")},
        "syntax_failures": 9, "timeout_failures": 9, "hidden_failures": 9,
        "perf_failed": True, "weakness": "empty_input",
    }

    def test_an_intervention_costs_rank_like_any_other_hint(self):
        spoke = 0
        for pet in pets.PETS:
            result = pets.intervention(
                pet.id, bond=40, mode=config.MODE_ADVENTURE,
                signals=dict(self.LOUD),
                context={"pattern": "HASH_MAP", "family": "two_sum"})
            if result is None:
                continue
            spoke += 1
            self.assertEqual(result["hint_weight"], pets.HINT_WEIGHT)
            self.assertIn(result["rank_ceiling"], ("A", "B", "C", "D"))
            self.assertTrue(result["body"])
        self.assertGreaterEqual(spoke, 4, "no pet fired on a maximal signal set")

    def test_a_pet_is_capped_at_one_word_per_encounter_and_two_in_the_field(self):
        """It arrives at the moment of struggle, not every ninety seconds."""
        first = pets.intervention("python", bond=40, signals=dict(self.LOUD))
        self.assertIsNotNone(first)
        self.assertEqual(first["remaining"], 0)
        self.assertIsNone(pets.intervention("python", bond=40,
                                            signals=dict(self.LOUD),
                                            spoken=first["spoken"]))
        self.assertEqual(len(pets.set_active(pets.new_state(),
                                             list(pets.PET_IDS))),
                         0)  # none are found yet, so none may be fielded

    def test_nothing_in_the_world_layer_works_in_interview_mode(self):
        for module in (pets, dungeons, quests, progression):
            self.assertTrue(module.available_in(config.MODE_ADVENTURE),
                            module.__name__)
            self.assertFalse(module.available_in(config.MODE_INTERVIEW),
                             module.__name__)

    def test_a_pet_says_nothing_in_interview_mode(self):
        for pet in pets.PETS:
            self.assertIsNone(pets.intervention(
                pet.id, bond=9, mode=config.MODE_INTERVIEW,
                signals=dict(self.LOUD)))
        # and it contributes no passives either, the way gear does not
        best = [p.id for p in pets.PETS[:pets.ACTIVE_LIMIT]]
        bonds = {pid: 400 for pid in best}   # STORIED, so passives exist
        self.assertEqual(
            pets.party_effects(best, bonds, mode=config.MODE_INTERVIEW), {})
        self.assertTrue(
            pets.party_effects(best, bonds, mode=config.MODE_ADVENTURE))

    def test_a_pet_says_nothing_where_the_region_says_nothing_helps(self):
        for region in pets.SILENCED_REGIONS:
            self.assertFalse(pets.available_in(config.MODE_ADVENTURE, region))
        self.assertTrue(pets.available_in(config.MODE_ADVENTURE, "python_village"))

    def test_a_dungeon_cannot_be_entered_during_a_measured_run(self):
        built = dungeons.generate("hollow_of_keys")
        with self.assertRaises(ValueError):
            dungeons.enter(built, mode=config.MODE_INTERVIEW)
        self.assertEqual(dungeons.enter(built)["mode"], config.MODE_ADVENTURE)

    def test_no_reward_anywhere_invents_an_effect(self):
        """One list of effect keys, and it lives in items.py. A pet, a treasure
        or a town hall that grants something outside it is granting nothing the
        engine can apply."""
        seen = set()
        for pet in pets.PETS:
            for effects in pet.passives.values():
                seen |= set(effects)
        for upgrade in quests.TOWN_UPGRADES.values():
            seen |= set(upgrade.get("effects") or {})
        for grant in progression.LEVEL_MILESTONES.values():
            seen |= set(grant.get("effects") or {})
        self.assertEqual(seen - EFFECTS, set())
        self.assertTrue(seen)

    def test_nothing_here_awards_mastery(self):
        """Mastery moves on graded evidence, in skills.py, and nowhere else. A
        quest reward that nudged a skill would be paying for time spent."""
        for reward in quests.REWARD_TIERS.values():
            self.assertNotIn("mastery", reward)
            self.assertNotIn("skill", reward)
        for grant in progression.LEVEL_MILESTONES.values():
            self.assertNotIn("mastery", grant)
        for quest in quests.QUESTS:
            self.assertNotIn("mastery", quest.extras or {})
        import ast
        import inspect
        # `_upgrade` exists only to build a strictly-stronger save for the
        # monotonicity proof; it is test scaffolding that happens to live in the
        # module, so it is named here rather than matched by accident.
        scaffolding = {"_upgrade", "_random_state", "self_check"}
        for module in (pets, dungeons, quests, progression):
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
                        if not isinstance(target, ast.Subscript):
                            continue
                        key = getattr(target.slice, "value", None)
                        self.assertNotIn(
                            key, ("mastery", "unaided_clears", "clears",
                                  "retention"),
                            f"{module.__name__}.{node.name} writes {key!r}")

    def test_a_pet_bond_only_moves_on_a_graded_clear(self):
        pet = pets.PETS[0]
        self.assertEqual(pets.bond_gain(pet.id, skill=pet.skill, cleared=False), 0)
        self.assertGreater(pets.bond_gain(pet.id, skill=pet.skill, cleared=True,
                                          rank="A"), 0)
        self.assertLessEqual(
            pets.bond_gain(pet.id, skill=pet.skill, cleared=True, rank="S",
                           hints_used=0, is_retest=True),
            pets.BOND_MAX_PER_ENCOUNTER)
        # carrying it around is not evidence, and neither is a different skill
        self.assertEqual(pets.bond_gain(pet.id, skill=pet.skill, cleared=True,
                                        rank="A", in_field=False), 0)
        other = next(p for p in pets.PETS if p.skill != pet.skill)
        self.assertEqual(pets.bond_gain(pet.id, skill=other.skill, cleared=True,
                                        rank="S"), 0)

    def test_no_reward_is_a_loot_box_or_a_streak(self):
        """No dark patterns: rewards are named up front, and nothing counts days
        in a row."""
        for quest in quests.QUESTS:
            summary = quests.reward_summary(
                quests.reward_for(quest.tier, quest.extras))
            self.assertTrue(summary, quest.id)
            for line in summary:
                self.assertNotIn("chance", line.lower(), quest.id)
                self.assertNotIn("random", line.lower(), quest.id)
        for quest in quests.QUESTS:
            for gate in _flatten(quest.requires):
                self.assertNotIn("streak", gate.kind, quest.id)
                self.assertNotIn("days", gate.kind, quest.id)
                self.assertNotIn("login", gate.kind, quest.id)


# ---------------------------------------------------------------------------
# 4. A save is loaded whole, or not at all
# ---------------------------------------------------------------------------

class TestSaveSafety(GameTest):
    def setUp(self):
        super().setUp()
        self.conn = saves.connect(self.data_dir / "save.sqlite3")
        self.alive = saves.normalize({"level": 7, "xp": 4321, "gold": 99,
                                      "region": "graph_wastes", "name": "ALIVE"})
        self.other = saves.normalize({"level": 2, "xp": 10, "gold": 1,
                                      "region": "python_village", "name": "OTHER"})
        saves.apply_state(self.conn, self.alive)

    def _live(self):
        from gauntlet import db
        return db.load_state(self.conn)

    def _damage(self, ordinal, sql, params=()):
        saves.save_to_slot(self.conn, ordinal, self.other, name=f"slot {ordinal}")
        sid = saves.slot_id(saves.KIND_MANUAL, ordinal)
        self.conn.execute(sql, tuple(params) + (sid,))
        self.conn.commit()
        return sid

    def _refuses(self, sid):
        """The three things that must be true of a refused load: it raised, the
        live game is untouched, and no undo was spent pretending otherwise."""
        before = copy.deepcopy(self._live())
        undo_before = saves.undo_available(self.conn)
        with self.assertRaises(saves.SaveCorrupt):
            saves.load_slot(self.conn, sid, current_state=self.alive)
        self.assertEqual(self._live(), before)
        self.assertEqual(saves.undo_available(self.conn), undo_before)
        report = saves.verify_slot(self.conn, sid)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "corrupt")
        self.assertTrue(report["message"])

    def test_a_flipped_byte_on_disk_is_refused(self):
        sid = self._damage(1, "UPDATE save_slots SET body = body WHERE slot_id = ?")
        row = self.conn.execute(
            "SELECT body FROM save_slots WHERE slot_id = ?", (sid,)).fetchone()
        blob = bytearray(row["body"])
        blob[len(blob) // 2] ^= 0xFF
        self.conn.execute("UPDATE save_slots SET body = ? WHERE slot_id = ?",
                          (bytes(blob), sid))
        self.conn.commit()
        self._refuses(sid)

    def test_a_slot_whose_checksum_no_longer_matches_is_refused(self):
        self._refuses(self._damage(
            2, "UPDATE save_slots SET body_sha = ? WHERE slot_id = ?", ("0" * 64,)))

    def test_a_truncated_slot_is_refused(self):
        self._refuses(self._damage(
            3, "UPDATE save_slots SET body_len = ? WHERE slot_id = ?", (999999,)))

    def test_a_slot_from_a_newer_build_is_refused_rather_than_guessed_at(self):
        self._refuses(self._damage(
            4, "UPDATE save_slots SET schema_version = ? WHERE slot_id = ?", (99,)))

    def test_an_empty_slot_body_is_refused(self):
        self._refuses(self._damage(
            5, "UPDATE save_slots SET body = X'' WHERE slot_id = ?"))

    def test_an_unknown_codec_is_refused(self):
        self._refuses(self._damage(
            6, "UPDATE save_slots SET codec = ? WHERE slot_id = ?", ("rot13",)))

    def test_a_missing_slot_raises_rather_than_returning_half_a_game(self):
        with self.assertRaises(saves.SlotNotFound):
            saves.load_slot(self.conn, "slot:8", current_state=self.alive)
        self.assertEqual(self._live()["name"], "ALIVE")

    def test_loading_over_a_game_can_be_undone_exactly(self):
        saves.save_to_slot(self.conn, 7, self.other, name="the other game")
        result = saves.load_slot(self.conn, "slot:7", current_state=self.alive)
        self.assertEqual(self._live()["name"], "OTHER")
        self.assertTrue(result["undo_available"])

        undone = saves.undo_load(self.conn, current_state=result["state"])
        self.assertEqual(undone["state"]["name"], "ALIVE")
        self.assertEqual(self._live(), self.alive)

    def test_the_undo_can_itself_be_undone(self):
        saves.save_to_slot(self.conn, 7, self.other, name="the other game")
        loaded = saves.load_slot(self.conn, "slot:7", current_state=self.alive)
        undone = saves.undo_load(self.conn, current_state=loaded["state"])
        redone = saves.undo_load(self.conn, current_state=undone["state"])
        self.assertEqual(redone["state"]["name"], "OTHER")
        self.assertEqual(self._live()["name"], "OTHER")

    def test_verify_all_reports_damage_without_raising(self):
        self._damage(1, "UPDATE save_slots SET body_sha = ? WHERE slot_id = ?",
                     ("0" * 64,))
        saves.save_to_slot(self.conn, 2, self.other, name="fine")
        report = {row["slot_id"]: row for row in saves.verify_all(self.conn)}
        self.assertFalse(report["slot:1"]["ok"])
        self.assertTrue(report["slot:2"]["ok"])

    def test_a_round_trip_through_a_file_survives(self):
        saves.save_to_slot(self.conn, 1, self.alive, name="mine")
        exported = saves.export_slot(self.conn, "slot:1",
                                     self.data_dir / "out.gauntlet")
        saves.delete_slot(self.conn, "slot:1")
        saves.import_slot(self.conn, exported["path"], ordinal=1)
        self.assertEqual(saves.read_slot(self.conn, "slot:1")["state"]["name"],
                         "ALIVE")

    def test_a_tampered_export_file_is_refused(self):
        import json
        saves.save_to_slot(self.conn, 1, self.alive, name="mine")
        path = saves.export_slot(self.conn, "slot:1",
                                 self.data_dir / "out.gauntlet")["path"]
        with open(path) as handle:
            envelope = json.load(handle)
        envelope["payload"]["state"]["gold"] = 999999
        with open(path, "w") as handle:
            json.dump(envelope, handle)
        with self.assertRaises(saves.SaveError):
            saves.import_slot(self.conn, path, ordinal=2)

    def test_an_autosave_ring_cannot_eat_the_good_save(self):
        for index in range(saves.AUTOSAVE_RING * 3):
            state = saves.normalize({"level": index + 1, "name": f"auto{index}"})
            saves.autosave(self.conn, state, "boss_cleared")
        rows = saves.list_slots(self.conn, kinds=(saves.KIND_AUTO,))
        self.assertEqual(len(rows), saves.AUTOSAVE_RING)
        self.assertTrue(all(row["ok"] for row in rows if row.get("used")))


if __name__ == "__main__":
    unittest.main()
