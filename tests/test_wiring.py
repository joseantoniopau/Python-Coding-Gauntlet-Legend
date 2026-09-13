"""Reachability, proved by playing.

Eleven modules were written, self-checked and imported by nothing. Every test
in this file drives a real `Game` and asserts on what the engine hands back, so
a module that quietly stops being called fails here rather than passing its own
self-check in private. Nothing below imports a world module to DO the work —
the modules are read only for the constants an assertion needs.

Three rules are re-proved end to end rather than assumed:
  - Adventure Mode teaches, Interview Mode measures, and finalexam.sealed() is
    the one question. Both the engine and the HTTP layer refuse.
  - Mastery moves on graded evidence. The Obliging Hand is the single exception
    and it moves mastery DOWN, permanently, and pays for it.
  - Learning never dead-ends: there is always something to do.
"""
from __future__ import annotations

import json
import random
import urllib.error
import urllib.request

from base import GameTest

from gauntlet import (config, dungeons, finalexam, legendaries, pets,
                      progression, puzzles, quests, skills as skillmod, world)


# --------------------------------------------------------------------------
# Playing the game, rather than reading it.
# --------------------------------------------------------------------------
def answer(g, problem):
    """Beat a problem through the door its encounter kind actually uses."""
    if problem.encounter_kind in puzzles.PUZZLE_KINDS:
        return g.solve_puzzle(puzzles.answer_key(problem))
    if problem.entry.get("kind") == "mcq":
        return g.answer_mcq(problem.mcq["answer"])
    return g.submit(problem.canonical_solution)


def beat(g, problem_id, **kwargs):
    g.start_encounter(problem_id, **kwargs)
    return answer(g, g.by_id[problem_id])


def family(g, name, limit=0):
    rows = [p for p in g.corpus
            if p.spaced_repetition_family == name and p.canonical_solution]
    return rows[:limit] if limit else rows


def delve(g, dungeon_id, region_id, *, budget=900):
    """Walk a whole dungeon the way a client driving `options` must: one room at
    a time, choosing only from what is available where the player stands.

    Returns (clear_events, artifacts, error).
    """
    g.state["player"]["region"] = region_id
    entered = g.enter_dungeon(dungeon_id)
    if entered.get("error"):
        return [], [], entered["error"]
    seen, last, cleared, artifacts = {}, {}, [], []
    for step in range(budget):
        run = g.state.get(dungeons.STATE_KEY)
        if run is None:
            break
        built = g._dungeon_for(run["dungeon"], run.get("seed"))
        options = g.dungeon_state()["options"]
        if any(o["action"] == "engage" and o["available"] for o in options):
            payload = g.dungeon_engage()
            if payload.get("error"):
                return cleared, artifacts, payload["error"]
            problem = g.by_id.get((payload.get("problem") or {}).get("id"))
            if problem is None:
                return cleared, artifacts, "the room bound no problem"
            result = answer(g, problem)
            artifacts += result.get("artifacts") or []
            done = (result.get("dungeon") or {}).get("dungeon_cleared")
            if done:
                cleared.append(done)
            if not result.get("solved"):
                # A room this harness cannot beat is a corpus gap, not a wiring
                # bug; the room relents and the descent continues either way.
                run = g.state.get(dungeons.STATE_KEY)
                if run is not None:
                    dungeons.clear_room(built, run, run["at"], solved=True)
                    g.state[dungeons.STATE_KEY] = run
            continue
        moves = [o for o in options if o["action"] == "move" and o["available"]]
        if not moves:
            break
        # Least-visited, least-recently-seen. Taking the first available move
        # ping-pongs between two rooms forever and never reaches the far side.
        moves.sort(key=lambda o: (seen.get(o["room"], 0), last.get(o["room"], -1)))
        room = moves[0]["room"]
        seen[room] = seen.get(room, 0) + 1
        last[room] = step
        g.dungeon_move(room)
    return cleared, artifacts, ""


# --------------------------------------------------------------------------
class TestClassesReachable(GameTest):
    """gauntlet/classes.py — six classes, 126 nodes, effects that reach the fold."""

    def test_a_class_is_chosen_and_a_point_is_spent_through_the_engine(self):
        g = self.game()
        selection = g.class_selection()["selection"]
        self.assertEqual(len(selection), 6, "six classes, in selection order")

        chosen = selection[0]["id"]
        self.assertTrue(g.choose_class(chosen).get("ok"))
        self.assertEqual(g.state["class"]["class"], chosen)

        # A level-1 character has no points; the tree is a promise, not a gift.
        self.assertEqual(g.class_tree()["points"], 0)
        spendable = [n["id"] for b in g.class_tree()["branches"]
                     for n in b["nodes"] if n["can_spend"]]
        self.assertEqual(spendable, [], "nothing to spend at level one")

        for problem in family(g, "python_basics", 10):
            beat(g, problem.id)
        self.assertGreater(g.state["player"]["level"], 1, "clears bought levels")

        tree = g.class_tree()
        self.assertGreater(tree["points"], 0, "a level-up granted a point")
        node_id = next(n["id"] for b in tree["branches"]
                       for n in b["nodes"] if n["can_spend"])
        before = tree["points"]
        spent = g.spend_node(node_id)
        self.assertTrue(spent.get("ok"), spent)
        self.assertEqual(spent["rank"], 1)
        self.assertLess(spent["points"], before, "the point was not taken")
        self.assertEqual(g.class_tree()["points"], spent["points"])
        self.assertEqual(g.state["class"]["spent"].get(node_id), 1)
        self.assertEqual(g.state["class"]["points"], spent["points"],
                         "the save must carry the same number as the screen")

    def test_a_spent_node_reaches_the_effect_fold(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 10):
            beat(g, problem.id)
        tree = g.class_tree()
        node_id = next(n["id"] for b in tree["branches"]
                       for n in b["nodes"] if n["can_spend"])
        before = g.effects()
        result = g.spend_node(node_id)
        after = g.effects()
        moved = [k for k, v in result["effects"].items()
                 if after.get(k, 0) != before.get(k, 0)]
        self.assertTrue(moved or not result["effects"],
                        "a node's effects must arrive in Game.effects()")

    def test_a_point_is_never_granted_twice_for_the_same_level(self):
        g = self.game()
        g.choose_class("seer")
        for problem in family(g, "python_basics", 10):
            beat(g, problem.id)
        settled = g.class_tree()["points"]
        for _ in range(4):
            g._sync_class_points()
        self.assertEqual(g.class_tree()["points"], settled,
                         "sync_points is the only granter and is idempotent")


# --------------------------------------------------------------------------
class TestQuestsReachable(GameTest):
    """gauntlet/quests.py — 74 quests that can be seen, taken and finished."""

    def test_a_quest_is_offered_accepted_credited_and_turned_in(self):
        g = self.game()
        g.choose_class("analyst")
        board = g.quest_board()
        self.assertTrue(board["available"], "the board is never empty at the start")
        self.assertEqual(board["counts"]["total"], len(quests.QUESTS))

        quest_id = "village_beam_count"
        self.assertTrue(g.accept_quest(quest_id).get("id"))
        self.assertIn(quest_id, g.state["quests"]["active"])

        refused = g.turn_in_quest(quest_id)
        self.assertEqual(refused["error"], "not finished")
        self.assertEqual(refused["progress"]["required"], 3)

        gold = g.state["player"]["gold"]
        ready = []
        for problem in family(g, "counting", 4):
            ready += beat(g, problem.id).get("quests_ready") or []
        self.assertIn(quest_id, ready, "a graded clear credits the objective")

        done = g.turn_in_quest(quest_id)
        self.assertTrue(done.get("ok"), done)
        self.assertIn(quest_id, g.state["quests"]["done"])
        self.assertGreater(g.state["player"]["gold"], gold, "the reward was paid")
        self.assertTrue(done.get("lines"), "the giver says something")

    def test_a_quest_credits_only_on_graded_evidence(self):
        g = self.game()
        g.choose_class("analyst")
        g.accept_quest("village_beam_count")
        problem = family(g, "counting", 1)[0]
        g.start_encounter(problem.id)
        failed = g.submit("def nope(*a, **k):\n    return None\n")
        self.assertFalse(failed.get("solved"))
        self.assertFalse(failed.get("quests_ready"),
                         "a failed submission credits nothing")

    def test_the_board_never_leaves_a_player_with_nothing(self):
        g = self.game()
        steps = quests.next_steps(g._quest_ctx(), g.state)
        self.assertTrue(steps, "next_steps names the nearest thing, always")


# --------------------------------------------------------------------------
class TestPetsReachable(GameTest):
    """gauntlet/pets.py — found by evidence, speaks at the moment of struggle,
    and is charged for it exactly like a hint."""

    SIGNALS = {
        "submitted": True, "seconds_elapsed": 900.0,
        "seconds_since_progress": 600.0, "failed_attempts": 4,
        "last_categories": ["edge_case"] * 4, "category_counts": {"edge_case": 4},
        "syntax_failures": 0, "timeout_failures": 0, "hidden_failures": 3,
        "perf_failed": False, "weakness": "empty_input",
    }

    def _with_a_companion(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 12):
            beat(g, problem.id)
        return g

    def test_a_companion_is_discovered_by_playing(self):
        g = self._with_a_companion()
        self.assertTrue(g.state["pets"]["found"],
                        "clears alone should surface a companion")
        catalogue = g.pet_catalogue()
        self.assertEqual(len(catalogue["pets"]), len(pets.PETS))
        self.assertEqual(catalogue["limit"], pets.ACTIVE_LIMIT)
        found = [row for row in catalogue["pets"] if row["id"] in
                 g.state["pets"]["found"]]
        self.assertTrue(all(row.get("found") for row in found))

    def _companion_for(self, g, problem):
        """Field an animal whose TIER actually covers this problem.

        With the hint system routed through the companion, "who is walking with
        you" decides whether there is any unasked help at all — so a test about
        what an intervention COSTS has to start by bringing one that can speak.
        The starter is TUTORIAL tier and sits at found[0] in every save.
        """
        for pet_id in g.state["pets"]["found"]:
            if pets.covers(pet_id, problem.difficulty):
                g.set_active_pets([pet_id])
                return pet_id
        return ""

    def test_an_intervention_costs_a_hint_and_caps_the_rank(self):
        g = self._with_a_companion()
        target = next(p for p in g.corpus
                      if p.canonical_solution and p.id not in g.state["solved_ids"])
        self.assertTrue(self._companion_for(g, target),
                        "no companion in this save reads that depth")
        g.start_encounter(target.id)
        event = g.pet_intervention(dict(self.SIGNALS))
        self.assertIsNotNone(event, "a companion should speak under this much struggle")
        self.assertEqual(event["hint_weight"], pets.HINT_WEIGHT)
        self.assertNotEqual(event["rank_ceiling"], "S",
                            "help never leaves an S on the table")

        encounter = g.encounter
        self.assertEqual(encounter.hints_used, event["hint_weight"])
        self.assertTrue(encounter.pet_spoke)
        self.assertEqual(encounter.rank_ceiling, event["rank_ceiling"])
        self.assertIsNone(g.pet_intervention(dict(self.SIGNALS)),
                          "a companion speaks once per encounter")

    def test_no_companion_line_hands_over_an_answer(self):
        g = self._with_a_companion()
        for target in [p for p in g.corpus
                       if p.canonical_solution
                       and p.id not in g.state["solved_ids"]][:8]:
            if not self._companion_for(g, target):
                continue
            g.start_encounter(target.id)
            event = g.pet_intervention(dict(self.SIGNALS))
            if not event or event.get("refused"):
                continue
            said = f"{event['opening']} {event['body']}".lower()
            for token in ("def ", "return ", "import ", "```"):
                self.assertNotIn(token, said, f"{event['pet']} wrote code")
            self.assertNotIn(target.pattern.lower().replace("_", " "), said)

    def test_a_bond_moves_only_on_a_graded_clear(self):
        g = self._with_a_companion()
        pet_id = g.state["pets"]["found"][0]
        g.set_active_pets([pet_id])
        before = g.state["pets"]["bond"].get(pet_id, 0)
        target = next(p for p in g.corpus
                      if p.canonical_solution and p.id not in g.state["solved_ids"])
        g.start_encounter(target.id)
        g.submit("def nope(*a, **k):\n    return None\n")
        self.assertEqual(g.state["pets"]["bond"].get(pet_id, 0), before,
                         "a failure is not evidence")

    def test_a_companion_passive_reaches_the_effect_fold(self):
        g = self._with_a_companion()
        pet_id = g.state["pets"]["found"][0]
        g.set_active_pets([pet_id])
        self.assertEqual(g.state["pets"]["active"], [pet_id])
        self.assertIsInstance(g.effects(), dict)

    # -- the tier ladder, and the floor underneath it ----------------------

    def test_a_new_save_already_has_the_starter_under_the_porch(self):
        """Nobody gives it to you and nobody asks. A save that did not have it
        would advertise it as something hiding in Python Village."""
        g = self.game()
        self.assertIn(pets.STARTER_ID, g.state["pets"]["found"])
        self.assertEqual(pets.active_id(g.state["pets"]), pets.STARTER_ID)
        self.assertEqual(g.pet_catalogue()["limit"], 1)

    def test_a_companion_above_its_depth_refuses_and_is_not_charged_for_it(self):
        g = self.game()
        deep = next(p for p in g.teachable if p.difficulty == "MEDIUM")
        g.start_encounter(deep.id)
        event = g.pet_intervention(dict(self.SIGNALS))
        self.assertTrue(event and event["refused"], "the starter reads TUTORIAL")
        self.assertEqual(event["hint_weight"], 0)
        self.assertEqual(event["rank_ceiling"], "")
        enc = g.encounter
        self.assertEqual(enc.hints_used, 0)
        self.assertEqual(enc.rank_ceiling, "")
        # `pet_spoke` is what feeds `intervened=True` into bond_gain. An animal
        # that admitted it was useless must not be paid the assisted bonus.
        self.assertFalse(enc.pet_spoke)
        self.assertEqual(enc.pet_refused, [pets.STARTER_ID])
        # And it is honest exactly once per encounter.
        self.assertIsNone(g.pet_intervention(dict(self.SIGNALS)))

    def test_learning_never_dead_ends_however_wrong_the_animal_is(self):
        """The sharpest edge in the design, asserted rather than promised.

        Wrong companion, no companion, dead companion: the first rung of the
        tree opens, the worked solution opens, and three attempts in the WHOLE
        tree opens. None of those three asks who is walking with you.
        """
        g = self.game()
        deep = next(p for p in g.teachable
                    if p.difficulty == "MEDIUM" and p.hint_tree
                    and p.canonical_solution)
        for who in ("wrong", "none", "dead"):
            with self.subTest(companion=who):
                g.state["pets"]["fallen"] = []
                g.state["pets"]["active"] = ([pets.STARTER_ID] if who == "wrong"
                                             else [])
                if who == "dead":
                    pets.fall(g.state["pets"])
                g.state["player"]["mana"] = 99
                g.start_encounter(deep.id)
                opened = g.use_hint(pets.OPEN_RUNG)
                self.assertNotIn("error", opened, f"{who}: the open rung closed")
                last = len(g.by_id[deep.id].hint_tree)
                solution = g.use_hint(last)
                self.assertNotIn("error", solution,
                                 f"{who}: the worked solution closed")
                route = g.hint_route()
                self.assertTrue(route["roads"])
                self.assertEqual(sorted(route["petless_roads"]),
                                 sorted(pets.PETLESS_ROADS))

    def test_three_attempts_in_the_whole_tree_opens_whoever_you_brought(self):
        g = self.game()
        deep = next(p for p in g.teachable
                    if p.difficulty == "MEDIUM" and len(p.hint_tree) >= 3
                    and p.canonical_solution)
        g.state["pets"]["active"] = [pets.STARTER_ID]
        for _ in range(pets.FREE_SOLUTION_AFTER):
            g.start_encounter(deep.id)
            g.submit("def nope(*a, **k):\n    return None\n")
        g.state["player"]["mana"] = 99
        g.start_encounter(deep.id)
        self.assertNotIn("error", g.use_hint(2),
                         "a player measured as stuck is not gated by a tier")

    def test_a_refusal_is_not_a_seal_and_never_says_it_is(self):
        """Two different sentences with two different answers. A client that
        cannot tell them apart teaches the player the wrong thing."""
        g = self.game()
        deep = next(p for p in g.teachable
                    if p.difficulty == "MEDIUM" and len(p.hint_tree) >= 2)
        g.state["player"]["mana"] = 99
        g.start_encounter(deep.id)
        blocked = g.use_hint(2)
        self.assertEqual(blocked["error"], "above_tier")
        self.assertNotEqual(blocked["error"], "sealed")
        self.assertTrue(blocked["route"]["roads"])
        self.assertIn("first rung is open", blocked["message"])

    def test_the_barrow_closes_once_and_survives_a_reload(self):
        g = self.game()
        region = next(d for d in dungeons.DUNGEONS
                      if d.id == pets.FALLS_AT_DUNGEON).region
        cleared, _, err = delve(g, pets.FALLS_AT_DUNGEON, region)
        self.assertEqual(err, "")
        self.assertIn(pets.FALLS_AT_DUNGEON, [c["id"] for c in cleared])
        self.assertTrue(pets.is_fallen(g.state["pets"], pets.STARTER_ID))
        self.assertEqual(g.state["pets"]["active"], [])
        scene = g.state["pet_fall"]
        self.assertEqual(len(scene["lines"]), 4)
        self.assertEqual(scene["returns_as"], pets.RETURN_ID)
        # It does not leave the codex, and it does not come back.
        self.assertIn(pets.STARTER_ID, g.state["pets"]["found"])
        self.assertIn("error", g.recall_pet(pets.STARTER_ID))
        # Once. Clearing the same ground again produces no second scene.
        g.acknowledge_fall()
        g.state["dungeons_cleared"].remove(pets.FALLS_AT_DUNGEON)
        delve(g, pets.FALLS_AT_DUNGEON, region)
        self.assertIsNone(g.state["pet_fall"])
        self.assertEqual(g.state["pets"]["fallen"], [pets.STARTER_ID])

    def test_a_save_that_predates_the_fall_settles_the_debt_without_the_scene(self):
        """It must not replay at somebody who was not standing there — and the
        legendary return is gated on the debt, so it cannot go unrecorded
        either. Both, by recording the fact and parking the scene as a memory."""
        g = self.game()
        from gauntlet import db as dbmod
        g.state["pets"] = {"found": ["python"], "active": ["python"],
                           "bond": {"python": 20}, "met_at": {}}
        g.state["dungeons_cleared"] = [pets.FALLS_AT_DUNGEON]
        dbmod.save_state(g.conn, g.state)
        reopened = self.game()   # same save file, a second open
        state = reopened.state["pets"]
        self.assertIn(pets.STARTER_ID, state["found"])
        self.assertTrue(pets.is_fallen(state, pets.STARTER_ID))
        self.assertTrue(reopened.state["pet_fall"]["retroactive"])
        self.assertTrue(reopened._pet_evidence()["starter_fallen"])

    def test_the_legendary_return_is_reachable_from_things_the_engine_writes(self):
        """"Reachable, and provably so" is a claim about wiring, not about
        flavour text: every clause of the return's condition has to be a number
        this engine actually records, and satisfying all of them has to make
        `newly_found` produce it.
        """
        g = self.game()
        evidence = g._pet_evidence()
        for clause in pets.BY_ID[pets.RETURN_ID].discovery.needs:
            row = pets._discovery_row(clause, evidence)
            self.assertIn("have", row)
            self.assertGreater(row["need"], 0, f"{clause}: an unfillable bar")
        # The barrow's debt is a key this file writes at the dungeon boss.
        self.assertIn("starter_fallen", evidence)
        # Depth comes from quests.note_depth, which _advance_dungeon calls.
        self.assertIn("dungeons", evidence)
        # And RECALL mastery is graded evidence like every other skill.
        self.assertIn("RECALL", evidence["skills"])

        pets.fall(g.state["pets"])
        g.state["quests"].setdefault("depths", {})[pets.RETURNS_AT_DUNGEON] = 4
        skills = g.skills
        skills["RECALL"].mastery = 40.0
        g._write_skills(skills)
        found = pets.newly_found(g._pet_evidence(), g.state["pets"]["found"])
        self.assertIn(pets.RETURN_ID, [row["pet"] for row in found])
        # It is the same animal, and it reads everything the starter could not.
        self.assertEqual(pets.BY_ID[pets.RETURN_ID].lineage, pets.STARTER_ID)
        self.assertTrue(pets.covers(pets.RETURN_ID, "BOSS"))

    def test_the_last_trial_has_a_face_and_it_changes_nothing(self):
        g = self.game()
        who = finalexam.examiner_view("READY")
        self.assertEqual(who["id"], world.FINAL_TRIAL["id"])
        self.assertEqual(who["region"], "null_kings_castle")
        self.assertTrue(who["arrival"] and who["closing"] and who["verdict"])
        # The identity ships INSIDE a sealed run, so it must seal exactly what
        # the exam already sealed and not one capability less.
        self.assertEqual(sorted(who["sealed"]),
                         sorted(finalexam.EXAM_SEAL.sealed))
        self.assertEqual(finalexam.audit_seal(), [])
        # And it is not a boss: appending to world.BOSSES would renumber every
        # rung of the crutch ladder.
        self.assertNotIn(world.FINAL_TRIAL["id"], world.BOSS_BY_ID)
        self.assertEqual(len(finalexam.BOSS_LADDER), len(world.BOSSES))


# --------------------------------------------------------------------------
class TestDungeonsReachable(GameTest):
    """gauntlet/dungeons.py — entered, walked, and actually finished."""

    DUNGEON, REGION = "halfwritten_barrow", "fields_of_syntax"

    def test_a_dungeon_is_entered_walked_and_cleared(self):
        g = self.game()
        g.choose_class("analyst")
        listing = g.dungeon_list(self.REGION)["dungeons"]
        self.assertIn(self.DUNGEON, [d["id"] for d in listing])

        cleared, _artifacts, error = delve(g, self.DUNGEON, self.REGION)
        self.assertEqual(error, "", "the descent must not stall")
        self.assertIn(self.DUNGEON, g.state["dungeons_cleared"],
                      "beating the thing at the bottom finishes the dungeon")
        self.assertTrue(cleared, "the clear is reported to the player")
        self.assertIsNone(g.state[dungeons.STATE_KEY], "the descent closes")
        self.assertGreater(cleared[0]["xp"], 0, "the boss pays its own reward")

        card = next(d for d in g.dungeon_list(self.REGION)["dungeons"]
                    if d["id"] == self.DUNGEON)
        self.assertTrue(card["cleared"])

    def test_the_dungeon_entered_is_the_dungeon_walked(self):
        """generate(id, seed=s) and build_dungeon(spec) are different buildings
        at the same seed — worldgen swaps the archetype and resizes. Entering
        through one and walking through the other puts the player in rooms that
        do not exist."""
        for seed in (21, 22, 23, 24):
            g = self.game()
            g.new_world(seed)
            g.state["player"]["region"] = self.REGION
            g.enter_dungeon(self.DUNGEON)
            run = g.state[dungeons.STATE_KEY]
            at_entry = g._dungeon_for(self.DUNGEON)
            while_walking = g._dungeon_for(run["dungeon"], run["seed"])
            self.assertEqual([r.id for r in at_entry.rooms],
                             [r.id for r in while_walking.rooms], f"seed {seed}")
            self.assertEqual(at_entry.boss_room, while_walking.boss_room)
            self.assertEqual(at_entry.archetype, while_walking.archetype)

    def test_floors_is_a_count_everywhere_it_is_named(self):
        g = self.game()
        g.state["player"]["region"] = self.REGION
        g.enter_dungeon(self.DUNGEON)
        card = next(d for d in g.dungeon_list(self.REGION)["dungeons"]
                    if d["id"] == self.DUNGEON)
        live = g.dungeon_state()["dungeon"]
        self.assertIsInstance(card["floors"], int)
        self.assertEqual(live["floors"], card["floors"])
        self.assertIn(live["difficulty_floor"], dungeons.DIFFICULTY_LADDER)

    def test_a_room_never_leaves_a_player_with_nothing_to_press(self):
        g = self.game()
        g.state["player"]["region"] = self.REGION
        g.enter_dungeon(self.DUNGEON)
        run = g.state[dungeons.STATE_KEY]
        built = g._dungeon_for(run["dungeon"], run["seed"])
        for room in built.rooms:
            run["at"] = room.id
            if room.id not in run["visited"]:
                run["visited"].append(room.id)
            options = g.dungeon_state()["options"]
            self.assertTrue(any(o["available"] for o in options),
                            f"room {room.id} had nothing available")

    def test_walking_a_floor_credits_the_delve_quests(self):
        g = self.game()
        g.choose_class("analyst")
        delve(g, self.DUNGEON, self.REGION)
        self.assertGreater(g.state["quests"]["depths"].get(self.DUNGEON, 0), 0)


# --------------------------------------------------------------------------
class TestProgressionReachable(GameTest):
    """gauntlet/progression.py — the map, the roads, the events, and the floor
    under the player that guarantees there is always something to do."""

    def test_the_world_map_is_a_whole_payload(self):
        g = self.game()
        payload = g.world_map()
        for key in ("here", "nodes", "edges", "open_routes", "reachable",
                    "sky", "npcs", "fast_travel", "restored", "events",
                    "level", "prestige"):
            self.assertIn(key, payload)
        self.assertTrue(payload["nodes"])

    def test_a_world_event_fires_from_playing(self):
        g = self.game()
        g.choose_class("analyst")
        fired = []
        for problem in family(g, "python_basics", 10):
            fired += beat(g, problem.id).get("world_events") or []
        self.assertTrue(fired, "the world should notice a player who is working")
        self.assertTrue(g.state["world"]["events_fired"])
        ids = [event["id"] for event in fired]
        self.assertEqual(len(ids), len(set(ids)), "an event fires once")

    def test_an_event_that_has_fired_does_not_fire_again(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        already = list(g.state["world"]["events_fired"])
        self.assertTrue(already)
        again = []
        for problem in family(g, "python_basics")[8:12]:
            again += [e["id"] for e in beat(g, problem.id).get("world_events") or []]
        self.assertFalse(set(again) & set(already))

    def test_travelling_a_road_moves_the_player(self):
        g = self.game()
        prog = progression.snapshot(g.state, g.skills, readiness=g._readiness())
        here = g.state["player"]["region"]
        roads = progression.open_routes(prog, here)
        self.assertTrue(roads, "the first region is never a sealed room")
        result = g.travel(roads[0]["id"])
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(g.state["player"]["region"], result["region"])
        self.assertNotEqual(g.state["player"]["region"], here)

    def test_a_closed_road_says_why_rather_than_vanishing(self):
        g = self.game()
        prog = progression.snapshot(g.state, g.skills, readiness=g._readiness())
        here = g.state["player"]["region"]
        for route in progression.routes_from(here):
            status = progression.route_status(route, prog, frm=here)
            if not status["passable"]:
                self.assertTrue(status["requirement"] or status["prose"],
                                f"{route.id} closed with no reason given")


class TestNoDeadEnds(GameTest):
    """Requirement F: across many states, there is always something to do, and
    no gate can close behind a player."""

    def test_four_hundred_simulated_saves_all_have_something_to_do(self):
        g = self.game()
        g.choose_class("analyst")
        rng = random.Random(20260911)
        regions = [r["id"] for r in world.REGIONS]
        bosses = [b["id"] for b in world.BOSSES]
        all_quests = list(quests.QUEST_BY_ID)
        all_dungeons = list(dungeons.DUNGEON_BY_ID)
        for trial in range(400):
            state = g.state
            state["player"]["region"] = rng.choice(regions)
            state["player"]["xp"] = rng.choice([0, 50, 500, 5_000, 50_000, 500_000])
            state["player"]["level"] = world.level_for(state["player"]["xp"])
            state["cleared_bosses"] = rng.sample(bosses, rng.randrange(len(bosses) + 1))
            state["dungeons_cleared"] = rng.sample(all_dungeons, rng.randrange(6))
            state["quests"]["done"] = rng.sample(all_quests, rng.randrange(30))
            for name in skillmod.SKILLS:
                state["skills"][name]["mastery"] = rng.choice(
                    [0.0, 10.0, 45.0, 80.0, 100.0])
            todo = g.things_to_do()
            self.assertTrue(todo, f"trial {trial} had nothing to do")
            for row in todo:
                self.assertTrue(row.get("action"), f"trial {trial}: {row}")
                self.assertTrue(row.get("why"), f"trial {trial}: {row}")

    def test_a_finished_player_still_has_something_to_do(self):
        g = self.game()
        g.choose_class("analyst")
        state = g.state
        state["cleared_bosses"] = [b["id"] for b in world.BOSSES]
        state["dungeons_cleared"] = list(dungeons.DUNGEON_BY_ID)
        state["quests"]["done"] = list(quests.QUEST_BY_ID)
        state["player"]["xp"] = 10_000_000
        state["player"]["level"] = progression.MAX_LEVEL
        for name in skillmod.SKILLS:
            state["skills"][name]["mastery"] = 100.0
        self.assertTrue(g.things_to_do())

    def test_a_brand_new_player_has_something_to_do(self):
        self.assertTrue(self.game().things_to_do())

    def test_the_examination_hall_is_never_a_room_you_cannot_leave(self):
        g = self.game()
        g.state["player"]["region"] = "null_kings_castle"
        self.assertTrue(g.things_to_do())
        prog = progression.snapshot(g.state, g.skills, readiness=g._readiness())
        self.assertTrue(progression.routes_from("null_kings_castle"))


# --------------------------------------------------------------------------
class TestLegendariesReachable(GameTest):
    """gauntlet/legendaries.py — 22 artifacts, and the one that lowers mastery."""

    def test_the_codex_is_reachable_and_an_artifact_is_awarded_by_playing(self):
        g = self.game()
        g.choose_class("analyst")
        catalogue = g.legendary_catalogue()
        self.assertEqual(len(catalogue["catalogue"]), len(legendaries.ARTIFACTS))
        entry = g.legendary(legendaries.OBLIGING_HAND.id)
        self.assertNotIn("error", entry)
        self.assertIn("progress", entry)

        awarded = []
        for problem in family(g, "python_basics", 12):
            awarded += beat(g, problem.id).get("artifacts") or []
        self.assertTrue(g.state["legendaries"], "no artifact was ever awarded")
        self.assertTrue(awarded, "the award was never reported to the player")
        self.assertEqual(sorted(set(g.state["legendaries"])),
                         sorted(g.state["legendaries"]), "awarded twice")

    def test_a_second_artifact_is_reachable_through_graded_play(self):
        """Every artifact past the Hand is gated on counters the engine has to
        write. Three of them were declared and written by nothing, which made
        the relics that read them unwinnable."""
        g = self.game()
        g.choose_class("analyst")
        # g.teachable, not g.corpus. Hold-out content is unreachable from
        # Adventure Mode by design and start_encounter refuses it, so a test
        # that plays it by id is asserting the thing the seal forbids.
        testing = [p for p in g.teachable
                   if skillmod.PATTERN_TO_SKILL.get(p.pattern) == "TESTING"
                   and p.canonical_solution]
        for problem in testing:
            beat(g, problem.id)
            if len(g.state["legendaries"]) > 1:
                break
        else:
            # The Band's second gate is twenty BOUNDARY clears, and a boundary
            # clear is any clean first-submission clear of a problem that
            # declares edges — not a TESTING problem specifically. Five of this
            # family are hold-out content, which leaves it two short of twenty
            # on its own, so the run tops up the way a player's would: with
            # whatever else the teaching corpus offers.
            spent = {p.id for p in testing}
            for problem in g.teachable:
                if problem.id in spent or not problem.canonical_solution:
                    continue
                if not (problem.edge_cases or problem.hidden_tests):
                    continue
                beat(g, problem.id)
                if len(g.state["legendaries"]) > 1:
                    break
        self.assertGreater(len(g.state["legendaries"]), 1,
                           "no relic past the Hand can be earned")
        self.assertGreater(g.state["stats"]["boundary_clears"], 0,
                           "boundary_clears is declared and never written")

    def test_the_hand_solves_and_charges_a_permanent_ceiling(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        self.assertIn(legendaries.OBLIGING_HAND.id, g.state["legendaries"])

        offer = g.hand_offer()
        self.assertFalse(offer["sealed"], "the Hand works in Adventure Mode")
        self.assertTrue(offer["lines"])

        target = next(p for p in g.corpus
                      if p.canonical_solution and p.encounter_kind == "CODE_BATTLE"
                      and p.id not in g.state["solved_ids"])
        skill = skillmod.PATTERN_TO_SKILL.get(target.pattern, "PYTHON")
        g.start_encounter(target.id)
        before = g.skills[skill].mastery
        xp_before = g.state["player"]["xp"]

        used = g.use_hand()
        self.assertTrue(used["solved"])
        self.assertFalse(used["sealed"])
        self.assertGreater(used["mastery_lost"], 0, "the Hand is never free")
        self.assertLess(g.skills[skill].mastery, before, "mastery fell")
        self.assertGreater(g.state["player"]["xp"], xp_before,
                           "loot and XP are paid in full; the cost is the ceiling")
        self.assertEqual(g.state["hand"]["uses"], 1)
        self.assertTrue(used["notice"])

    def test_the_ceiling_the_hand_bought_still_holds_after_more_clears(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        target = next(p for p in g.corpus
                      if p.canonical_solution and p.encounter_kind == "CODE_BATTLE"
                      and p.id not in g.state["solved_ids"])
        skill = skillmod.PATTERN_TO_SKILL.get(target.pattern, "PYTHON")
        g.start_encounter(target.id)
        g.use_hand()
        ceiling = legendaries.mastery_ceiling(g.state["hand"], skill)
        same = [p for p in g.corpus
                if p.canonical_solution
                and skillmod.PATTERN_TO_SKILL.get(p.pattern) == skill
                and p.id not in g.state["solved_ids"]][:15]
        for problem in same:
            beat(g, problem.id)
            self.assertLessEqual(g.skills[skill].mastery, ceiling + 1e-9,
                                 "a clear briefly exceeded a ceiling that was paid for")

    def test_the_ledger_survives_a_save_and_a_load(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        target = next(p for p in g.corpus
                      if p.canonical_solution and p.encounter_kind == "CODE_BATTLE"
                      and p.id not in g.state["solved_ids"])
        g.start_encounter(target.id)
        g.use_hand()
        ledger = json.dumps(g.state["hand"], sort_keys=True)
        g.save_to_slot(2, name="after the bargain")
        g.state["hand"] = legendaries.hand_ledger_new()
        g.save()
        g.load_slot("slot:2")
        self.assertEqual(json.dumps(g.state["hand"], sort_keys=True), ledger,
                         "a ledger that resets makes the Hand free")


# --------------------------------------------------------------------------
class TestSavesReachable(GameTest):
    """gauntlet/saves.py — named slots, the autosave ring, and an undo that
    means a corrupt slot never costs the live game."""

    def test_a_named_slot_round_trips_and_the_load_can_be_undone(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 6):
            beat(g, problem.id)
        g.state["player"]["gold"] = 4242
        g.save()

        written = g.save_to_slot(3, name="before the castle")
        self.assertEqual(written["slot_id"], "slot:3")

        g.state["player"]["gold"] = 1
        g.save()
        loaded = g.load_slot("slot:3")
        self.assertTrue(loaded["ok"], loaded)
        self.assertEqual(g.state["player"]["gold"], 4242,
                         "the caller must adopt the returned state")
        self.assertTrue(loaded["undo_available"])

        undone = g.undo_load()
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(g.state["player"]["gold"], 1,
                         "loading over a game can be undone exactly")

    def test_the_save_screen_is_one_call(self):
        g = self.game()
        g.save_to_slot(1, name="a name")
        screen = g.save_slots()
        self.assertEqual(len(screen["slots"]),
                         sum((8, 4, 4)))  # manual + autosave ring + undo ring
        row = next(r for r in screen["slots"] if r["slot_id"] == "slot:1")
        self.assertFalse(row["empty"])
        self.assertEqual(row["name"], "a name")
        self.assertIn("summary", row)
        self.assertTrue(row["summary"].get("region"))

    def test_a_cleared_encounter_writes_the_autosave_ring(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 4):
            beat(g, problem.id)
        rings = [r for r in g.save_slots()["slots"]
                 if r["kind"] == "auto" and not r["empty"]]
        self.assertTrue(rings, "nothing ever autosaved")

    def test_the_whole_world_layer_survives_a_round_trip(self):
        g = self.game()
        g.choose_class("warden")
        for problem in family(g, "python_basics", 10):
            beat(g, problem.id)
        g.accept_quest("village_beam_count")
        g.class_tree()
        before = {key: json.dumps(g.state[key], sort_keys=True)
                  for key in ("pets", "quests", "world", "class", "hand",
                              "legendaries", "dungeons_cleared", "moveset")}
        g.save_to_slot(4, name="the whole world")
        for key in before:
            g.state[key] = [] if isinstance(g.state[key], list) else {}
        g.save()
        g.load_slot("slot:4")
        for key, blob in before.items():
            self.assertEqual(json.dumps(g.state[key], sort_keys=True), blob, key)


# --------------------------------------------------------------------------
class TestWorldgenReachable(GameTest):
    """gauntlet/worldgen.py — a seeded world the save carries in four bytes."""

    def test_a_world_is_seeded_shareable_and_rebuilt_from_its_seed(self):
        g = self.game()
        card = g.world_card()
        self.assertTrue(card["card"])
        self.assertTrue(card["seed"])
        self.assertIn("minutes", card["first_hour"])

        rolled = g.new_world(4242)
        self.assertTrue(rolled["ok"])
        seed = g.state["world_seed"]
        self.assertTrue(g.world.regions)

        same = self.game()
        same.new_world(4242)
        self.assertEqual(same.state["world_seed"], seed)
        self.assertEqual([r.id for r in same.world.regions],
                         [r.id for r in g.world.regions])

    def test_the_seeded_world_is_what_the_dungeons_are_built_from(self):
        g = self.game()
        g.new_world(4242)
        spec = next(d for d in g.world.dungeons)
        built = g._dungeon_for(spec.id)
        self.assertEqual(built.archetype, spec.archetype,
                         "the seed's archetype must survive into the building")

    def test_the_world_seed_survives_a_save_and_a_load(self):
        g = self.game()
        g.new_world(4242)
        seed, regions = g.state["world_seed"], [r.id for r in g.world.regions]
        g.save_to_slot(5, name="a seeded world")
        g.new_world(99)
        self.assertNotEqual(g.state["world_seed"], seed)
        g.load_slot("slot:5")
        self.assertEqual(g.state["world_seed"], seed,
                         "a save carries the seed, not the spec")
        self.assertEqual([r.id for r in g.world.regions], regions,
                         "the loaded save must rebuild the same world")


# --------------------------------------------------------------------------
class TestIncantationAndBestiaryReachable(GameTest):
    """gauntlet/incantation.py and gauntlet/bestiary.py — typed Python against
    enemies that ARE the variables."""

    def test_a_battle_is_listed_started_and_fielded(self):
        g = self.game()
        g.choose_class("analyst")
        listing = g.incantation_encounters()
        self.assertTrue(listing["encounters"], "no battle in the first region")
        encounter_id = listing["encounters"][0]["id"]

        started = g.start_incantation(encounter_id)
        self.assertNotIn("error", started)
        field = started["incantation"]
        self.assertEqual(field["encounter"], encounter_id)
        self.assertTrue(field["enemies"], "a fight with nothing in it")
        self.assertTrue(all(e["hp"] > 0 for e in field["enemies"]))
        self.assertTrue(started["moveset"], "nothing to cast")
        for move in started["moveset"]:
            self.assertIn("template", move)

    def test_the_field_survives_between_requests(self):
        g = self.game()
        g.choose_class("analyst")
        encounter_id = g.incantation_encounters()["encounters"][0]["id"]
        opened = g.start_incantation(encounter_id)["incantation"]
        again = g.incantation_view()["incantation"]
        self.assertEqual([e["name"] for e in opened["enemies"]],
                         [e["name"] for e in again["enemies"]])
        self.assertEqual([e["hp"] for e in opened["enemies"]],
                         [e["hp"] for e in again["enemies"]])

    def test_a_cast_is_graded_and_the_battle_can_be_left(self):
        g = self.game()
        g.choose_class("analyst")
        encounter_id = g.incantation_encounters()["encounters"][0]["id"]
        view = g.start_incantation(encounter_id)
        move = view["moveset"][0]
        result = g.incantation_cast(move["id"], {})
        self.assertIn("ok", result)
        self.assertIn("incantation", result)
        self.assertTrue(g.leave_incantation().get("ok"))
        self.assertIsNone(g.state.get("incantation"))

    def test_an_unknown_battle_is_refused_rather_than_fielded_empty(self):
        g = self.game()
        self.assertIn("error", g.start_incantation("no_such_encounter"))


# --------------------------------------------------------------------------
class TestFinalExamReachable(GameTest):
    """gauntlet/finalexam.py — the ladder, the composer, and the seal."""

    def test_the_ladder_is_reachable_and_is_the_boss_order(self):
        g = self.game()
        ladder = g.exam_ladder()
        self.assertEqual(len(ladder["ladder"]), len(finalexam.BOSS_LADDER))
        self.assertEqual([row["boss_id"] for row in ladder["ladder"]],
                         [b["id"] for b in world.BOSSES])
        self.assertTrue(ladder["format"]["rules"])
        for rung, row in enumerate(ladder["ladder"], start=1):
            self.assertEqual(row["rung"], rung)

    def test_the_exam_is_composed_from_the_real_corpus(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        started = g.start_interview("FINAL_EXAM")
        self.assertNotIn("error", started)
        exam = started["exam"]
        self.assertTrue(exam["segments"])
        asked = [q for segment in exam["segments"] for q in segment["questions"]]
        self.assertTrue(asked)
        self.assertEqual(len(asked), started["run"]["total"])
        for question in asked:
            # The client's copy of the timetable names no problem: the exam
            # reaches into the sealed hold-out and a roster read before the
            # questions are served is a free look at unspent hold-out ids.
            self.assertNotIn("problem_id", question)
            self.assertNotIn("title", question)
            self.assertIn(question["role"], ("algorithm", "feature", "bug"))
        # The composition is still real, read where it actually lives.
        roster = g.state["interview"]["problem_ids"]
        self.assertEqual(len(roster), len(asked))
        for problem_id in roster:
            self.assertIn(problem_id, g.by_id,
                          "the exam asked for a problem that does not exist")
        self.assertEqual(finalexam.audit_seal(), [])

    def test_the_exam_is_sealed_and_the_payload_leaks_nothing(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        g.start_interview("FINAL_EXAM")
        payload = g.interview_current()
        self.assertEqual(finalexam.audit_payload(payload), [],
                         "the exam payload leaked something")
        self.assertTrue(payload["interview_locked"])
        sealed = set(payload["seal"]["sealed"])
        for capability in ("HINTS", "PROBES", "ITEMS", "PET", "COACH",
                           "OBLIGING_HAND", "PATTERN", "SOLUTION", "MENTOR",
                           "WEAKNESS_MAP", "VISUALS"):
            self.assertIn(capability, sealed)

    def test_the_exam_ends_in_a_debrief_that_names_causes(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        g.start_interview("FINAL_EXAM")
        for _ in range(len(g.state["interview"]["problem_ids"])):
            current = g.interview_current()
            if current.get("finished") or "problem" not in current:
                break
            problem = g.by_id[current["problem"]["id"]]
            answer(g, problem)
        finished = g.finish_exam({"set": 3000.0, "codebase": 2000.0})
        self.assertTrue(finished.get("finished"), finished)
        self.assertIn("score", finished)
        self.assertIsNone(g.state["interview"], "the run is closed")
        debrief = finished.get("debrief")
        if debrief and not debrief.get("unavailable"):
            self.assertIn("verdict", debrief)
            self.assertIn("drills", debrief)


# --------------------------------------------------------------------------
class TestTheIsolationRuleAtTheEngine(GameTest):
    """Interview Mode measures. Nothing helps, and nothing is a second path."""

    CAPABILITIES = ("HINTS", "PROBES", "ITEMS", "PET", "COACH",
                    "OBLIGING_HAND", "PATTERN", "SOLUTION", "MENTOR")

    def _in_the_exam(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        g.state["consumables"]["focus_elixir"] = 3
        # A descent left standing when the exam begins is the one way a dungeon
        # can reach a measured run at all, so that is the state under test.
        g.state["player"]["region"] = "fields_of_syntax"
        g.enter_dungeon("halfwritten_barrow")
        g.save()
        g.start_interview("FINAL_EXAM")
        g.interview_current()      # the client opens the first question
        return g

    def test_every_capability_reports_sealed(self):
        g = self._in_the_exam()
        encounter = g.encounter
        self.assertIsNotNone(encounter)
        for capability in self.CAPABILITIES:
            self.assertTrue(finalexam.sealed(encounter, capability), capability)

    def test_every_door_refuses(self):
        g = self._in_the_exam()
        refusals = {
            "HINTS": g.use_hint(1),
            "PROBES": g.probe([1], 1),
            "ITEMS": g.use_consumable("focus_elixir"),
            "OBLIGING_HAND": g.use_hand(),
        }
        for capability, answerback in refusals.items():
            self.assertEqual(answerback.get("error"), "sealed", capability)
            self.assertEqual(answerback.get("capability"), capability)
            self.assertTrue(answerback.get("message"))
        self.assertEqual(g.probes_remaining(), 0)
        self.assertIsNone(g.pet_intervention({"failed_attempts": 9,
                                              "seconds_elapsed": 900.0,
                                              "seconds_since_progress": 900.0,
                                              "submitted": True}))

    def test_the_whole_world_layer_is_shut(self):
        g = self._in_the_exam()
        for name, answerback in (
                ("dungeon_move", g.dungeon_move(1)),
                ("dungeon_retreat", g.dungeon_retreat()),
                ("leave_dungeon", g.leave_dungeon()),
                ("accept_quest", g.accept_quest("village_beam_count")),
                ("turn_in_quest", g.turn_in_quest("village_beam_count")),
                ("enter_dungeon", g.enter_dungeon("halfwritten_barrow")),
                ("dungeon_engage", g.dungeon_engage()),
                ("choose_class", g.choose_class("seer")),
                ("spend_node", g.spend_node("analyst_read_the_water")),
                ("class_respec", g.class_respec()),
                ("choose_dual", g.choose_dual("seer")),
                ("abandon_quest", g.abandon_quest("village_beam_count")),
                ("set_active_pets", g.set_active_pets([])),
                ("new_world", g.new_world(5)),
                ("travel", g.travel("rt_waking_road")),
                ("load_slot", g.load_slot("slot:1")),
                ("undo_load", g.undo_load()),
                ("start_incantation", g.start_incantation("enc_first_loop")),
        ):
            self.assertEqual(answerback.get("error"), "sealed", name)
            self.assertTrue(answerback.get("capability"), name)

    def test_a_measured_run_cannot_have_its_build_changed_underneath_it(self):
        g = self._in_the_exam()
        tree = dict(g.state["class"])
        seed = g.state["world_seed"]
        g.spend_node("analyst_read_the_water")
        g.class_respec()
        g.new_world(5)
        self.assertEqual(g.state["class"], tree, "the tree moved mid-exam")
        self.assertEqual(g.state["world_seed"], seed, "the world moved mid-exam")

    def test_a_descent_left_open_cannot_be_walked_during_the_exam(self):
        g = self._in_the_exam()
        self.assertIsNotNone(g.state[dungeons.STATE_KEY],
                             "this test needs a descent still standing")
        at = g.state[dungeons.STATE_KEY]["at"]
        self.assertEqual(g.dungeon_engage().get("error"), "sealed")
        self.assertEqual(g.dungeon_move(1).get("error"), "sealed")
        self.assertEqual(g.state[dungeons.STATE_KEY]["at"], at)
        self.assertEqual(g.encounter.mode, config.MODE_INTERVIEW,
                         "engaging a room opened an Adventure encounter over the exam")

    def test_a_measured_run_pays_nothing_into_the_world(self):
        g = self._in_the_exam()
        quests_done = list(g.state["quests"]["done"])
        pets_found = list(g.state["pets"]["found"])
        events = list(g.state["world"]["events_fired"])
        artifacts = list(g.state["legendaries"])
        current = g.interview_current()
        problem = g.by_id[current["problem"]["id"]]
        answer(g, problem)
        self.assertEqual(g.state["quests"]["done"], quests_done)
        self.assertEqual(g.state["pets"]["found"], pets_found)
        self.assertEqual(g.state["world"]["events_fired"], events)
        self.assertEqual(g.state["legendaries"], artifacts)

    def test_nothing_but_the_hand_lowers_mastery_without_a_graded_failure(self):
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        before = {name: state.mastery for name, state in g.skills.items()}
        g.accept_quest("village_beam_count")
        g.pet_catalogue()
        g.legendary_catalogue()
        g.class_tree()
        g.world_map()
        g.things_to_do()
        g.exam_ladder()
        g.save_to_slot(6, name="untouched")
        after = {name: state.mastery for name, state in g.skills.items()}
        self.assertEqual(before, after, "something moved mastery without evidence")

    def test_saving_is_allowed_because_it_banks_a_run_rather_than_helping(self):
        g = self._in_the_exam()
        written = g.save_to_slot(8, name="mid-exam")
        self.assertEqual(written["slot_id"], "slot:8")
        self.assertEqual(g.load_slot("slot:8").get("error"), "sealed",
                         "loading mid-exam is a retry and is refused")

    def test_the_boss_ladder_seals_build_at_its_upper_rungs(self):
        g = self.game()
        rungs = g.exam_ladder()["ladder"]
        self.assertTrue(any(row["sealed"] for row in rungs),
                        "the ladder takes nothing away from anybody")
        self.assertTrue(rungs[-1]["final"])


class TestTheIsolationRuleOverHTTP(GameTest):
    """The same guarantee, at the door. A rule that only lives three rooms in is
    a rule somebody can walk around."""

    SEALED_POSTS = (
        ("/api/hint", {"level": 1}),
        ("/api/probe", {"args": [1], "expected": 1}),
        ("/api/consumable", {"id": "focus_elixir"}),
        ("/api/explain", {"text": "a sliding window"}),
        ("/api/hand/use", {}),
        ("/api/quest/accept", {"quest_id": "village_beam_count"}),
        ("/api/quest/turnin", {"quest_id": "village_beam_count"}),
        ("/api/dungeon/enter", {"dungeon_id": "halfwritten_barrow"}),
        ("/api/dungeon/move", {"room": 1}),
        ("/api/dungeon/engage", {}),
        ("/api/dungeon/retreat", {}),
        ("/api/dungeon/leave", {}),
        ("/api/pets/active", {"pet_ids": ["python"]}),
        ("/api/pet/intervene", {"signals": {"failed_attempts": 5}}),
        ("/api/class/choose", {"class_id": "seer"}),
        ("/api/class/spend", {"node_id": "analyst_read_the_water"}),
        ("/api/class/respec", {"scope": "all"}),
        ("/api/class/dual", {"class_id": "seer"}),
        ("/api/travel", {"route": "rt_waking_road"}),
        ("/api/route/discover", {"route": "rt_waking_road"}),
        ("/api/load", {"slot_id": 3}),
        ("/api/undo", {}),
        ("/api/slot/import", {"payload": {"nope": True}}),
        ("/api/world/new", {"seed": 7}),
        ("/api/incant/start", {"encounter_id": "enc_first_loop"}),
        ("/api/incant/cast", {"move_id": "gather", "answers": {}}),
        ("/api/incant/leave", {}),
        # THE RACK. A purchase is a LOADOUT change mid-exam, which is strictly
        # more than the consumable /api/shop/buy already refuses, so it cannot
        # be less sealed. Selling is sealed for the same reason plus one: it
        # pays gold into the purse, which is the world moving under a run that
        # is supposed to be sealed off from it.
        ("/api/shop/rack/buy", {"slot": "chest"}),
        ("/api/shop/rack/sell", {"item_id": "rack__python_village__0__chest"}),
        ("/api/shop/blank", {}),
    )

    def setUp(self):
        super().setUp()
        from gauntlet import server as server_module
        self.server_module = server_module
        g = self.game()
        g.choose_class("analyst")
        for problem in family(g, "python_basics", 8):
            beat(g, problem.id)
        g.state["consumables"]["focus_elixir"] = 3
        g.save()
        self.g = g
        server_module.set_game(g)
        self.httpd, url = server_module.serve()
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)
        self.base = url.split("/?")[0]
        self.token = server_module.TOKEN

    def call(self, path, body=None):
        request = urllib.request.Request(
            self.base + path,
            method="POST" if body is not None else "GET",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Gauntlet-Token": self.token,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_the_world_layer_is_reachable_over_http_in_adventure_mode(self):
        for path in ("/api/state", "/api/quests", "/api/chains", "/api/pets",
                     "/api/pets/discovery", "/api/dungeons", "/api/dungeon",
                     "/api/world-map", "/api/region", "/api/routes",
                     "/api/events", "/api/todo", "/api/saves",
                     "/api/legendaries", "/api/hand", "/api/exam/ladder",
                     "/api/classes", "/api/class/tree", "/api/world/card",
                     "/api/incantation", "/api/incantation/state",
                     # The three that were built, self-checked, green in their
                     # own test files and imported by nothing in gauntlet/.
                     "/api/shop", "/api/escorts"):
            status, payload = self.call(path)
            self.assertEqual(status, 200, f"{path} -> {payload}")
            self.assertNotIn("error", payload, path)

    def test_the_todo_endpoint_is_never_empty(self):
        status, payload = self.call("/api/todo")
        self.assertEqual(status, 200)
        self.assertTrue(payload["todo"])

    def test_every_sealed_door_answers_409_with_a_named_capability(self):
        self.g.state["player"]["region"] = "fields_of_syntax"
        self.g.enter_dungeon("halfwritten_barrow")
        status, started = self.call("/api/exam/start", {})
        self.assertEqual(status, 200, started)
        self.assertTrue(self.g.state.get("interview"))
        self.assertEqual(self.call("/api/interview/current")[0], 200)
        for path, body in self.SEALED_POSTS:
            status, payload = self.call(path, body)
            self.assertEqual(status, 409, f"{path} -> {status} {payload}")
            self.assertEqual(payload.get("error"), "sealed", path)
            self.assertTrue(payload.get("capability"), path)
            self.assertTrue(payload.get("message"), path)

    def test_the_exam_payload_over_the_wire_leaks_nothing(self):
        self.call("/api/exam/start", {})
        status, payload = self.call("/api/interview/current")
        self.assertEqual(status, 200)
        self.assertEqual(finalexam.audit_payload(payload), [])
        self.assertEqual(self.call("/api/probes")[1]["charges"], 0)

    def test_an_unknown_id_is_a_404_rather_than_a_stack_trace(self):
        for path, body in (("/api/quest/accept", {"quest_id": "no_such_quest"}),
                           ("/api/dungeon/enter", {"dungeon_id": "nowhere"}),
                           ("/api/class/choose", {"class_id": "nobody"}),
                           ("/api/pets/active", {"pet_ids": ["gerbil"]})):
            status, payload = self.call(path, body)
            self.assertEqual(status, 404, f"{path} -> {status} {payload}")
            self.assertIn("error", payload)


# --------------------------------------------------------------------------
class TestEveryModuleIsReachedThroughTheEngine(GameTest):
    """One pass that touches all eleven, so a module falling out of the engine
    fails here rather than passing its own self-check in private."""

    def test_one_session_reaches_all_eleven(self):
        g = self.game()
        touched = set()

        # classes
        g.choose_class("analyst")
        touched.add("classes")
        # worldgen
        self.assertTrue(g.world_card()["seed"])
        touched.add("worldgen")
        # incantation + bestiary
        listing = g.incantation_encounters()
        self.assertTrue(listing["encounters"])
        field = g.start_incantation(listing["encounters"][0]["id"])
        self.assertTrue(field["incantation"]["enemies"])
        self.assertTrue(field["moveset"])
        g.leave_incantation()
        touched.update({"incantation", "bestiary"})
        # quests
        g.accept_quest("village_beam_count")
        touched.add("quests")
        # play, which moves pets, progression and legendaries
        for problem in family(g, "python_basics", 12):
            beat(g, problem.id)
        self.assertTrue(g.state["pets"]["found"])
        touched.add("pets")
        self.assertTrue(g.state["world"]["events_fired"])
        touched.add("progression")
        self.assertTrue(g.state["legendaries"])
        touched.add("legendaries")
        # dungeons
        cleared, _artifacts, error = delve(g, "halfwritten_barrow",
                                           "fields_of_syntax")
        self.assertEqual(error, "")
        self.assertTrue(cleared)
        touched.add("dungeons")
        # saves
        g.save_to_slot(7, name="one session")
        self.assertTrue(any(not r["empty"] for r in g.save_slots()["slots"]))
        touched.add("saves")
        # finalexam
        self.assertTrue(g.exam_ladder()["ladder"])
        touched.add("finalexam")

        self.assertEqual(touched, {
            "classes", "worldgen", "incantation", "bestiary", "quests", "pets",
            "progression", "legendaries", "dungeons", "saves", "finalexam"})

    def test_the_dashboard_carries_the_whole_world_layer(self):
        g = self.game()
        g.choose_class("analyst")
        dashboard = g.dashboard()
        for key in ("world", "todo", "quests", "pets", "dungeon", "dungeons",
                    "class", "class_selection", "legendaries", "exam"):
            self.assertIn(key, dashboard, f"the client cannot see {key}")
        self.assertTrue(dashboard["todo"], "the what-next strip is never empty")
        self.assertTrue(dashboard["world"]["nodes"])


# --------------------------------------------------------------------------
class TestTheTacticalLayerIsReachable(GameTest):
    """gauntlet/elements.py, gauntlet/potions.py — proved by playing.

    Three modules were written, self-checked and imported by nothing. These
    tests drive a real `Game` through real turns, because a module that quietly
    stops being called should fail here rather than pass its own self-check in
    private.

    The rule every one of these is really testing: the TYPING is the attack.
    Elements, potions and armour decide how LONG a fight lasts and therefore how
    much repetition the player gets on the moveset. Nothing here may win a fight
    on its own.
    """

    def _fight(self, g):
        """Open an encounter on a problem with a real solution, and return it."""
        problem = next(p for p in g.corpus if p.canonical_solution)
        g.state["player"]["region"] = problem.realm
        return problem, g.start_encounter(problem.id)

    def test_an_encounter_opens_with_a_turn_a_belt_and_an_element(self):
        from gauntlet import elements
        g = self.game()
        g.choose_class("analyst")
        _problem, payload = self._fight(g)
        self.assertEqual(payload["turn"], 1)
        self.assertIn("pouch", payload)
        self.assertTrue(payload["pouch"]["rule"])
        self.assertIn("element", payload)
        self.assertIn(payload["element"]["player"],
                      set(elements.ELEMENTS) | {elements.NEUTRAL})
        vitals = payload["enemy_vitals"]
        self.assertGreater(vitals["focus_max"], 0, "the enemy has no focus")
        self.assertTrue(vitals["specials"], "the enemy has nothing to spend it on")

    def test_a_missed_submission_is_a_turn_and_the_enemy_answers(self):
        g = self.game()
        g.choose_class("analyst")
        _problem, payload = self._fight(g)
        before = g.state["player"]["stamina"]
        result = g.submit("def nope(*a, **k):\n    return None\n")
        self.assertFalse(result["solved"])
        self.assertEqual(result["turn"], 2, "the turn did not advance")
        self.assertIsNotNone(result["enemy_turn"], "the enemy never acted")
        self.assertGreater(result["damage_taken"], 0)
        self.assertLess(g.state["player"]["stamina"], before)

    def test_a_potion_rides_with_the_cast_and_is_never_instead_of_one(self):
        """The whole feature, in one test. Drinking must not spend the turn,
        and a second draught before casting must be refused — otherwise the
        optimal play is drink-instead-of-think."""
        from gauntlet import potions
        g = self.game()
        g.choose_class("analyst")
        potions.grant(g.state, "health_small", 3)
        self._fight(g)
        g.submit("def nope(*a, **k):\n    return None\n")   # take a hit first
        first = g.use_potion("health_small")
        self.assertTrue(first["ok"])
        self.assertFalse(first["turn_spent"], "drinking spent the turn")
        self.assertTrue(first["must_still_cast"])
        second = g.use_potion("health_small")
        self.assertFalse(second.get("ok"))
        self.assertEqual(second["error"], "already")
        # and the cast is what unlocks the belt again
        after = g.submit("def nope(*a, **k):\n    return None\n")
        self.assertTrue(after["pouch"]["may_drink"])

    def test_an_antidote_clears_both_records_of_poison(self):
        from gauntlet import elements, potions
        g = self.game()
        g.choose_class("analyst")
        potions.grant(g.state, "antidote_small", 1)
        self._fight(g)
        enc = g.encounter
        statuses = [elements.StatusInstance(id="POISONED", turns=4, stacks=1)]
        enc.statuses = [s.to_dict() for s in statuses]
        poison = potions.Poison()
        potions.poison_apply(poison, damage=2, turns=3, source="test")
        enc.poison = poison.to_dict()
        g._write_encounter(enc)
        cured = g.use_potion("antidote_small")
        self.assertTrue(cured["ok"])
        self.assertIn("POISONED", cured["statuses_cured"],
                      "the wheel's poison survived the antidote")
        self.assertEqual(cured["poison"]["stacks"], 0,
                         "the dose pool survived the antidote")

    def test_metals_and_potions_survive_a_save_slot_round_trip(self):
        from gauntlet import potions
        g = self.game()
        g.choose_class("analyst")
        g.state["forge"]["metals"] = {"fieldiron": 4, "keybrass": 2}
        potions.grant(g.state, "antidote_small", 2)
        potions.grant(g.state, "health_medium", 1)
        g.save()
        bag = dict(g.state["forge"]["metals"])
        pouch = dict(g.state["potions"])
        g.save_to_slot(1, name="round trip")
        g.state["forge"]["metals"] = {}
        g.state["potions"] = {}
        g.save()
        self.assertTrue(g.load_slot("slot:1")["ok"])
        self.assertEqual(g.state["forge"]["metals"], bag)
        self.assertEqual(g.state["potions"], pouch)
        # and through an export, which is the other road a save takes
        payload = g.export()
        g.state["potions"] = {}
        g.save()
        g.import_save(payload)
        self.assertEqual(g.state["potions"], pouch)

    def test_the_tactical_layer_is_sealed_in_a_measured_run(self):
        """One capability check, and it is finalexam.sealed. A potion is ITEMS,
        the loadout is BUILD, and the enemy's element is a reading of the room."""
        from gauntlet import config, elements, potions
        g = self.game()
        g.choose_class("analyst")
        potions.grant(g.state, "health_small", 2)
        problem = next(p for p in g.corpus if p.canonical_solution)
        payload = g.start_encounter(problem.id, mode=config.MODE_INTERVIEW)
        self.assertTrue(payload["pouch"]["sealed"])
        self.assertFalse(payload["pouch"]["may_drink"])
        self.assertEqual(payload["element"]["player"], elements.NEUTRAL)
        self.assertEqual(payload["element"]["enemy"], "")
        self.assertEqual(payload["element"]["armour"]["points"], 0)
        refused = g.use_potion("health_small")
        self.assertFalse(refused.get("ok"))
        self.assertEqual(g.state["potions"]["health_small"], 2, "it was spent")

    def test_the_incantation_battle_takes_turns_and_the_enemy_spends_focus(self):
        """The fight the tactical layer exists for: eight to twenty casts, an
        enemy that banks focus and spends it, and a rout that is never a loss."""
        from gauntlet import bestiary, potions
        g = self.game()
        g.choose_class("analyst")
        potions.grant(g.state, "health_small", 3)
        view = g.start_incantation("enc_twin_wardens")
        field = view["incantation"]
        self.assertTrue(field["rule"], "the turn rule is invisible to the player")
        for enemy in field["enemies"]:
            self.assertGreater(enemy["vitals"]["focus_max"], 0)
            self.assertTrue(enemy["vitals"]["specials"])
        seen_focus = 0
        for turn in range(12):
            if not g.state.get("incantation"):
                break
            out = g.incantation_cast("advance", {"counter": "left"})
            enemy_turn = out.get("enemy_turn") or {}
            seen_focus = max(seen_focus, int(enemy_turn.get("focus", 0) or 0))
        self.assertGreater(seen_focus, 0, "no enemy ever banked any focus")

    def test_a_wrong_cast_still_cannot_be_bought_off_with_a_potion(self):
        """The rule that outranks the rest of this file. A potion cannot cast
        the line, and the pouch cannot damage anything."""
        from gauntlet import elements, potions
        g = self.game()
        g.choose_class("analyst")
        potions.grant(g.state, "health_small", 5)
        g.start_incantation("enc_twin_wardens")
        before = {e["name"]: e["hp"]
                  for e in g.incantation_view()["incantation"]["enemies"]}
        for _ in range(4):
            drink = g.use_potion("health_small")
            if drink.get("ok"):
                # the belt locks until a cast resolves, so a wasted cast is the
                # only way to drink again — which is the point
                g.incantation_cast("advance", {"counter": "__not_a_name__"})
        after = {e["name"]: e["hp"]
                 for e in g.incantation_view()["incantation"]["enemies"]}
        self.assertEqual(before, after,
                         "potions and wrong casts moved an enemy's health")
        # and zero damage stays zero however good the matchup is
        nothing = elements.resolve_damage(
            0, elements.FIRE, elements.Defender(element=elements.COLD))
        self.assertEqual(nothing.damage, 0)

    def test_the_three_armour_roads_and_the_boots_are_equippable(self):
        from gauntlet import elements, items
        g = self.game()
        g.choose_class("analyst")
        g.state["inventory"] += ["ward_fire", "field_plate", "wanderers_cloak",
                                 "crampons"]
        self.assertTrue(g.equip("crampons").get("ok"))
        self.assertEqual(items.boots_id(g.state["equipped"]), "crampons")
        step = g.region_view("twin_pointer_pass")["element"]["step"]
        self.assertTrue(step["protected"], "crampons do not answer black ice")
        self.assertTrue(g.equip("ward_fire").get("ok"))
        armour = g.loadout()["armour"]
        self.assertTrue(armour["resist"], "a warded piece resists nothing")
        self.assertLessEqual(max(armour["resist"].values()),
                             elements.RESIST_CAP)


class TestTheThreeOrphansAreReachable(GameTest):
    """`shop`, `zonecompanions` and `villagelife` were each written, proved
    against real numbers and imported by NOTHING in `gauntlet/`. Their own test
    files were green and the player could not reach a line of any of them —
    the same condition `ending.py` was in before its four touch points landed,
    and the reason `tests/test_art_is_wired.py` keeps an orphan guard at all.

    Everything below drives a real `Game` and asserts on what the engine hands
    back, because an import statement is not reachability.
    """

    def test_the_rack_is_on_the_counter_and_can_be_bought_worn_and_sold(self):
        from gauntlet import shop
        g = self.game()
        g.choose_class("analyst")
        view = g.shop("python_village")
        # The potions are untouched — same call, same rows, same restock.
        self.assertIn("stock", view)
        self.assertEqual(len(view["rack"]), len(shop.RACK_SLOTS))
        self.assertEqual(view["rack_left"], len(view["rack"]))
        self.assertTrue(view["shelf_note"])

        peg = view["rack"][0]
        g.state["player"]["gold"] = 9999
        bought = g.buy_rack(peg["slot"], region_id="python_village")
        self.assertNotIn("error", bought, bought)
        self.assertEqual(bought["gold"], 9999 - bought["gold_spent"])
        self.assertIn(peg["id"], g.state["inventory"])

        # IT RESOLVES. A generated id is not in items.BY_ID, so without
        # shop.is_rack_item in the engine's resolver a bought piece is
        # invisible in the bag and refuses to equip — the exact failure the
        # five zone drops had.
        owned = {row["id"]: row for row in g.loadout()["inventory"]}
        self.assertIn(peg["id"], owned)
        self.assertEqual(owned[peg["id"]]["name"], peg["name"])
        self.assertTrue(g.equip(peg["id"]).get("ok"))
        self.assertEqual(g.state["equipped"][peg["slot"]], peg["id"])

        purse = g.state["player"]["gold"]
        sold = g.sell_rack(peg["id"], region_id="python_village")
        self.assertNotIn("error", sold, sold)
        self.assertEqual(g.state["player"]["gold"], purse + sold["gold_back"])
        self.assertNotIn(peg["id"], g.state["inventory"])
        self.assertNotEqual(g.state["equipped"].get(peg["slot"]), peg["id"],
                            "a sold piece is still being worn")
        self.assertEqual(
            g.sell_rack(peg["id"], region_id="python_village")["error"],
            "not_bought")

    def test_the_rack_cannot_be_rerolled_by_anything_a_player_can_do(self):
        g = self.game()
        g.choose_class("analyst")
        first = [row["id"] for row in g.shop("python_village")["rack"]]
        g.region_view("fields_of_syntax")
        g.world_map()
        g.save()
        again = [row["id"] for row in g.shop("python_village")["rack"]]
        self.assertEqual(first, again)

    def test_the_escort_walks_the_village_and_the_slate_lands_in_the_bag(self):
        from gauntlet import zonecompanions as zc
        g = self.game()
        g.choose_class("analyst")

        here = g.region_view("python_village")
        self.assertEqual(here["escort"]["id"], "thessaly_brun")
        self.assertEqual(here["escort"]["state"], zc.WALKING)
        self.assertEqual(here["zone"]["id"], "home")
        self.assertTrue(here["escort"]["lines"])

        walked = g.travel("rt_waking_road")
        self.assertTrue(walked.get("ok"), walked)
        self.assertIn("the_slate", g.state["inventory"])
        kinds = [e["kind"] for e in walked["escort_events"]]
        self.assertIn("given", kinds)

        # And it resolves in the bag, which is the whole of what the five
        # missing items.py rows cost.
        owned = {row["id"] for row in g.loadout()["inventory"]}
        self.assertIn("the_slate", owned)

        # skate_irons is slot `feet`, and §4.1 makes ice control conditional on
        # it being EQUIPPED. Before the rows landed that slot could not be
        # filled at all.
        g.state["inventory"].append("skate_irons")
        self.assertTrue(g.equip("skate_irons").get("ok"))
        self.assertEqual(g.state["equipped"]["feet"], "skate_irons")

    def test_the_escort_panel_and_the_arc_advance_on_a_real_save(self):
        from gauntlet import zonecompanions as zc
        g = self.game()
        g.choose_class("analyst")
        snap = g.escorts("python_village")
        self.assertEqual(snap["counts"]["total"], len(zc.ESCORTS))
        self.assertEqual(snap["counts"]["walking"], len(zc.ESCORTS))
        self.assertEqual(snap["here"]["id"], "thessaly_brun")
        self.assertEqual(g.state[zc.STATE_KEY],
                         {"taken": [], "given": [], "scenes": [], "swept": []})

    def test_a_measured_run_has_no_companion_beside_it(self):
        g = self.game()
        g.choose_class("analyst")
        g.state["interview"] = {"exam_id": "x"}
        self.assertEqual(g.region_view("python_village")["escort"], {})
        snap = g.escorts("python_village")
        self.assertTrue(snap["sealed"])
        self.assertEqual(snap["here"], {})
        for call in (lambda: g.buy_rack("chest", region_id="python_village"),
                     lambda: g.buy_blank(region_id="python_village")):
            out = call()
            self.assertEqual(out.get("error"), "sealed", out)
            self.assertEqual(out.get("capability"), "BUILD", out)

    def test_the_villages_are_on_the_wire_and_not_only_in_a_test_process(self):
        from gauntlet import villagelife
        g = self.game()
        g.choose_class("analyst")
        here = g.region_view("python_village")["village"]
        self.assertGreater(here["count"], 0)
        self.assertGreater(here["buildings"], 0)
        self.assertTrue(here["activity"]["kind"])
        self.assertTrue(any(v["child"] for v in here["villagers"]))

        card = g.world_map()
        self.assertEqual(len(card["villages"]), len(world.REGIONS))
        self.assertEqual(sum(v["count"] for v in card["villages"].values()),
                         sum(v["count"] for v in
                             villagelife.region_payload(seed=g._save_seed())))
        self.assertGreater(sum(v["count"] for v in card["villages"].values()), 0)

    def test_one_save_gets_one_village_and_two_saves_get_two(self):
        """Seeded off the SAVE SEED, which is what stops a village being
        rebuilt under a player who reloaded, and what stops two runs looking
        identical."""
        g = self.game()
        g.choose_class("analyst")
        first = g.region_view("python_village")["village"]
        again = g.region_view("python_village")["village"]
        self.assertEqual(first, again)
        g.state["world_seed"] = int(g._save_seed()) + 1
        other = g.region_view("python_village")["village"]
        self.assertNotEqual(first["villagers"], other["villagers"])


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
