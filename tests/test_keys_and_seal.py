"""The four things the audit flagged and deliberately did not fix, tested.

Each of the four was a DESIGN decision rather than a defect, the decisions have
now been made, and this file is where they stop being prose:

  1. BOSS PHASES advance, buff the boss, and reach the client.
  2. KEYS drop, persist, survive a round trip, and open their roads.
  3. THE PORTAL counts fourteen keys and gates the STORY — and the practical
     stays reachable with none of them. Both halves, both directions.
  4. THE SEALED RULE from docs/10-sealed-views.md, applied uniformly.

The order below is the order of the brief, and every claim in it is made by
playing rather than by reading a constant.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import GameTest  # noqa: E402

from gauntlet import antagonist, bestiary, config, finalexam, progression, puzzles, world  # noqa: E402


def answer(game, problem):
    """Clear one problem however its entry kind is cleared.

    A boss ladder draws a different KIND of problem per phase — name the
    family, state the approach, write it, name its cost — so a test that only
    knew how to type Python would stall on the phase that asks for a choice.
    """
    if problem.encounter_kind in puzzles.PUZZLE_KINDS:
        return game.solve_puzzle(puzzles.answer_key(problem))
    if problem.entry.get("kind") == "mcq":
        return game.answer_mcq(problem.mcq.get("answer"))
    return game.submit(problem.canonical_solution)


def open_boss(test, game, boss_id):
    """Stand where the boss lives, then open the fight.

    `Game.start_boss` refuses a boss the player is not in front of, which is
    what makes `story._places_proved` true rather than hopeful. The walk is the
    player's and so it is the test's. A no-op when already there, so it is safe
    to call on re-entry as well as on the first approach.
    """
    test.stand_where(game, boss_id)
    return game.start_boss(boss_id)


def clear_boss(test, game, boss_id, *, limit=12):
    """Fight one boss all the way down. Returns the final boss event."""
    test.stand_where(game, boss_id)
    game.start_boss(boss_id)
    last = None
    for _ in range(limit):
        if game.encounter is None:
            game.start_boss(boss_id)
        out = answer(game, game.by_id[game.encounter.problem_id])
        last = out.get("boss") or {}
        if last.get("defeated"):
            return last
    test.fail(f"{boss_id} did not go down in {limit} graded answers")


class TheBossIsALadder(GameTest):
    """A region boss used to die to ONE solved problem, and `boss_phase` was
    declared and never incremented by anything. Four to six graded solves now,
    and every turn changes a number the player can feel."""

    BOSS = "hash_titan"

    def test_a_phase_turn_buffs_the_boss_and_carries_its_own_beat(self):
        g = self.game()
        payload = open_boss(self, g, self.BOSS)
        fight = payload["boss"]["fight"]
        self.assertEqual(fight["phase"], 0)
        self.assertGreaterEqual(fight["phases"], 4)
        self.assertEqual(fight["art_phase"], 0, "a boss walks in whole")

        seen = []
        for _ in range(fight["phases"] + 3):
            if g.encounter is None:
                open_boss(self, g, self.BOSS)
            event = (answer(g, g.by_id[g.encounter.problem_id])
                     .get("boss") or {})
            if event.get("beat"):
                seen.append(event["beat"])
            if event.get("defeated"):
                break

        self.assertEqual(len(seen), fight["phases"] - 1)
        # THE ART MOVES. Every turn lands on a different stage, which is the
        # whole of "even show graphically different" — the art existed, was
        # measured, and was never once on screen because nothing carried the
        # number from the fight to the sprite builder.
        stages = [b["art_phase"] for b in seen]
        self.assertEqual(len(set(stages)), len(stages), f"art repeated: {stages}")
        self.assertEqual(stages[-1], bestiary.ART_STAGES - 1,
                         "the last phase is the final form")
        # AND IT GETS STRONGER, cumulatively, rung by rung.
        blows = [b["state"]["blow"] for b in seen]
        self.assertEqual(blows, sorted(blows), f"the blow went backwards: {blows}")
        self.assertGreater(blows[-1], 1.0)
        kinds = [len(b["state"]["kinds"]) for b in seen]
        self.assertEqual(kinds, sorted(kinds))
        for beat in seen:
            self.assertTrue(beat["herald"], "the boss speaks on the turn")
            self.assertTrue(beat["tell"], "and one sentence says what changed")

    def test_only_graded_evidence_takes_a_phase_down(self):
        """A near miss chips. It can never finish. The floor is the rule."""
        g = self.game()
        open_boss(self, g, self.BOSS)
        fight = g.state["boss_fight"]
        enc = g.encounter
        pool = fight["hp_max"]
        landed = g._land_on_boss(enc, fight, solved=False, passed=4, total=5)
        self.assertGreater(landed["damage"], 0, "being close moves the bar")
        self.assertLess(fight["hp"], pool)
        for _ in range(200):
            g._land_on_boss(enc, fight, solved=False, passed=5, total=5)
        self.assertEqual(fight["hp"], bestiary.CAST_FLOOR_HP)
        self.assertEqual(fight["phase"], 0)
        self.assertFalse(fight["cleared"])
        self.assertEqual(g.state["cleared_bosses"], [])
        turn = g._land_on_boss(enc, fight, solved=True, passed=5, total=5)
        self.assertTrue(turn["turned"], "and the solve is what turns it")

    def test_nothing_scores_zero_lands_nothing(self):
        """A submission that passed no trial landed no blow. This function
        cannot manufacture a hit, which is the rule the whole game rests on."""
        g = self.game()
        open_boss(self, g, self.BOSS)
        fight = g.state["boss_fight"]
        before = fight["hp"]
        g._land_on_boss(g.encounter, fight, solved=False, passed=0, total=5)
        self.assertEqual(fight["hp"], before)

    def test_the_fight_survives_a_reload_mid_ladder(self):
        g = self.game()
        open_boss(self, g, self.BOSS)
        answer(g, g.by_id[g.encounter.problem_id])
        mid = dict(g.state["boss_fight"])
        self.assertEqual(mid["phase"], 1)
        g.save()
        again = self.game()
        self.assertEqual(again.state["boss_fight"]["phase"], mid["phase"])
        resumed = open_boss(self, again, self.BOSS)["boss"]["fight"]
        self.assertEqual(resumed["phase"], mid["phase"],
                         "walking back in resumes rather than restarts")

    def test_a_cleared_fight_comes_down_so_a_rematch_is_not_pre_won(self):
        g = self.game()
        clear_boss(self, g, self.BOSS)
        self.assertIsNone(g.state["boss_fight"])
        again = open_boss(self, g, self.BOSS)["boss"]["fight"]
        self.assertEqual(again["phase"], 0)

    def test_a_boss_records_one_win_per_kill_and_not_one_per_phase(self):
        from gauntlet import db
        g = self.game()
        clear_boss(self, g, self.BOSS)
        wins = [r for r in db.boss_history(g.conn, self.BOSS) if r["defeated"]]
        self.assertEqual(len(wins), 1)


class TheKeys(GameTest):
    """Fourteen bosses, fourteen keys, fourteen roads. Nothing is stored."""

    def test_there_is_no_key_ledger_to_fall_out_of_step(self):
        g = self.game()
        self.assertNotIn("keys", g.state, "a key is derived, never stored")
        self.assertEqual(world.keys_held(g.state["cleared_bosses"]), [])
        g.state["cleared_bosses"].append("hash_titan")
        self.assertEqual(world.keys_held(g.state["cleared_bosses"]),
                         ["key_one_rune"])

    def test_no_key_is_an_item_and_no_drop_can_roll_one(self):
        from gauntlet import items
        for key in world.KEYS:
            self.assertNotIn(key["id"], items.BY_ID)
        rows = items.keyring_rows(["hash_titan"])
        self.assertEqual(len(rows), len(world.KEYS))
        self.assertTrue(rows[0]["held"])
        for row in rows:
            self.assertNotIn("rarity", row, "a key is not loot")

    def test_the_key_drops_when_the_last_phase_falls_and_not_before(self):
        g = self.game()
        open_boss(self, g, "hash_titan")
        first = (answer(g, g.by_id[g.encounter.problem_id]).get("boss") or {})
        self.assertTrue(first.get("advanced"))
        self.assertEqual(world.keys_held(g.state["cleared_bosses"]), [])
        event = clear_boss(self, g, "hash_titan")
        self.assertEqual(event["key"]["id"], "key_one_rune")
        self.assertTrue(event["key"]["held"])
        self.assertIn("key_one_rune", world.keys_held(g.state["cleared_bosses"]))

    def test_a_key_survives_a_save_a_load_and_a_slot_round_trip(self):
        from gauntlet import saves
        g = self.game()
        g.state["cleared_bosses"] = ["hash_titan", "three_sum_hydra"]
        g.save()
        saves.save_to_slot(g.conn, 1, g.state, name="keys")
        reloaded = self.game()
        self.assertEqual(len(world.keys_held(reloaded.state["cleared_bosses"])), 2)
        reloaded.state["cleared_bosses"] = []
        reloaded.save()
        slot = next(s for s in saves.list_slots(reloaded.conn)
                    if s["slot_id"] == "slot:1")
        reloaded.load_slot(slot["slot_id"])
        self.assertEqual(len(world.keys_held(reloaded.state["cleared_bosses"])), 2)

    def test_every_key_opens_a_real_road_and_the_road_opens(self):
        g = self.game()
        for key in world.KEYS:
            route = progression.ROUTE_BY_ID.get(key["opens"])
            self.assertIsNotNone(route, f"{key['id']} opens nothing")
            g.state["cleared_bosses"] = []
            prog = progression.snapshot(g.state, g.skills)
            self.assertFalse(progression.route_status(route, prog)["passable"],
                             f"{route.id} was open with no key")
            g.state["cleared_bosses"] = [key["boss"]]
            prog = progression.snapshot(g.state, g.skills)
            self.assertTrue(progression.route_status(route, prog)["passable"],
                            f"{key['id']} did not open {route.id}")

    def test_the_key_is_named_at_the_door_not_on_the_corpse(self):
        g = self.game()
        card = open_boss(self, g, "hash_titan")["boss"]["key"]
        self.assertEqual(card["id"], "key_one_rune")
        self.assertFalse(card["held"])
        self.assertTrue(card["opens_name"])


class ThePortalAndTheMeasurement(GameTest):
    """The sharpest edge in the build. Both halves, and both are tested."""

    def test_the_portal_stands_in_the_first_village(self):
        self.assertEqual(world.THE_STANDING_PORTAL["region"], "python_village")
        self.assertEqual(world.PORTAL_KEY_REQUIREMENT, len(world.KEYS))
        g = self.game()
        town = g.town()
        self.assertEqual(town["region"], "python_village")
        self.assertIsNotNone(town["portal"], "it stands in the square")

    def test_the_portal_counts_and_refuses_without_stranding_anyone(self):
        g = self.game()
        shut = g.enter_portal()
        self.assertFalse(shut["ok"])
        self.assertEqual(len(shut["missing"]), len(world.KEYS))
        # A refusal that did not also say this would be the one that ruins the
        # game: a player who reads "0 / 14" must not conclude the exam is
        # eleven boss fights away.
        self.assertTrue(shut["practical"]["open"])
        self.assertFalse(shut["practical"]["requires_keys"])

    def test_thirteen_keys_is_not_enough_and_fourteen_is(self):
        g = self.game()
        g.state["cleared_bosses"] = [k["boss"] for k in world.KEYS][:-1]
        self.assertFalse(g.portal()["open"])
        self.assertFalse(g.enter_portal()["ok"])
        g.state["cleared_bosses"] = [k["boss"] for k in world.KEYS]
        self.assertTrue(g.portal()["open"])
        opened = g.enter_portal()
        self.assertTrue(opened["ok"])
        self.assertEqual(opened["trial"]["id"], world.FINAL_TRIAL["id"])

    def test_the_practical_is_sittable_at_level_one_holding_nothing(self):
        g = self.game()
        self.assertEqual(g.state["cleared_bosses"], [])
        self.assertEqual(g.state["player"]["level"], 1)
        exam = g.start_interview("FINAL_EXAM")
        self.assertNotIn("error", exam)
        self.assertTrue(g.state.get("exam") or g.state.get("interview"))

    def test_nothing_measured_is_ever_behind_the_portal(self):
        for name in (world.PORTAL_NEVER_GATES
                     + finalexam.PRACTICAL_NEVER_REQUIRES
                     + ("something_nobody_has_thought_of_yet",)):
            self.assertFalse(world.portal_gates(name))
            self.assertFalse(progression.portal_blocks(name))
        self.assertTrue(finalexam.PRACTICAL_IS_NEVER_GATED)
        self.assertEqual(list(finalexam.PRACTICAL_REQUIREMENTS),
                         ["the player asked"])

    def test_the_exam_reads_no_key_no_boss_and_no_route(self):
        """Not an opinion: the source of the module is read."""
        source = Path(finalexam.__file__).read_text(encoding="utf-8")
        body = source[source.index("EXAM_MODE = "):]
        for banned in ("cleared_bosses", "keys_held", "portal_open",
                       "KEY_BY_", "THE_STANDING_PORTAL", "route_status"):
            self.assertNotIn(banned, body,
                             f"finalexam.py must never read {banned}")


class TheGeographyClause(GameTest):
    """A chain used to fire on mastery alone, so a fast player got a Coliseum
    NPC commenting on their times while standing in Python Village at six."""

    def test_the_engine_records_where_the_player_has_stood(self):
        g = self.game()
        self.assertEqual(g.story_context()["regions_entered"],
                         {"python_village"})
        g.move("graph_wastes", 4, 4)
        self.assertIn("graph_wastes", g.state["story"]["regions_entered"])
        self.assertIn("graph_wastes", g.story_context()["regions_entered"])

    def test_travelling_a_road_records_arrival_too(self):
        g = self.game()
        g.state["cleared_bosses"].append("hash_titan")
        route = progression.ROUTE_BY_ID["rt_indexed_road"]
        g.state["player"]["region"] = route.frm
        g.save()
        self.assertTrue(g.travel(route.id)["ok"])
        self.assertIn(route.to, g.state["story"]["regions_entered"])

    def test_a_chain_from_a_region_never_visited_does_not_fire(self):
        from gauntlet import story
        g = self.game()
        chain = next(c for c in story.SIDE_CHAINS
                     if c.region == "coding_coliseum")
        skills = g.skills
        for state in skills.values():
            state.mastery, state.clears, state.unaided_clears = 100.0, 60, 40
            state.attempts, state.retention, state.speed = 60, 95.0, 95.0
            state.stage = "MASTERED"
        g._write_skills(skills)
        g.state["player"].update({"level": 40, "xp": 99999})
        g.state["solved_ids"] = [p.id for p in g.teachable[:400]]
        g.save()
        steps = {s.id for s in chain.steps}
        pending = {e["id"] for e in story.pending(g.story_context(),
                                                  g.state["story"])}
        self.assertFalse(pending & steps,
                         "mastery alone summoned somebody from a place the "
                         "player has never stood in")
        g.move("coding_coliseum", 10, 10)
        opened = {e["id"] for e in story.pending(g.story_context(),
                                                 g.state["story"])}
        self.assertTrue(opened & steps, "and standing there opens it")

    def test_a_boss_cannot_be_fought_from_four_regions_away(self):
        """The hole under this whole class.

        `story._places_proved` says clearing a boss proves the player stood in
        that boss's region, and `build_context` folds it in on that strength.
        Both were resting on a door that never asked: `start_boss` checked the
        seal and the final-boss readiness bar and never once checked WHERE THE
        PLAYER WAS. So the gate above was real and its evidence was not.
        """
        g = self.game()
        self.assertEqual(g.state["player"]["region"], "python_village")
        refusal = g.start_boss("graph_necromancer")
        self.assertEqual(refusal["error"], "not there")
        self.assertIn("Graph Wastes", refusal["message"])
        self.assertEqual(refusal["travel"]["region"], "graph_wastes")
        self.assertTrue(refusal["travel"]["road_open"])
        self.assertTrue(refusal["travel"]["path"])
        self.assertEqual(g.state["cleared_bosses"], [])
        # A refusal in this game never leaves the player holding nothing, and
        # it is never about the one door that is always open.
        self.assertTrue(refusal["things_to_do"])
        self.assertTrue(refusal["practical"]["open"])

    def test_the_road_the_refusal_names_is_the_road_that_works(self):
        g = self.game()
        refusal = g.start_boss("graph_necromancer")
        for route_id in refusal["travel"]["path"]:
            self.assertNotIn("error", g.travel(route_id))
        self.assertEqual(g.state["player"]["region"], "graph_wastes")
        self.assertIn("graph_wastes", g.state["story"]["regions_entered"])
        self.assertIn("boss", g.start_boss("graph_necromancer"))

    def test_every_region_boss_is_walkable_to_from_the_first_village(self):
        """NO DEAD END, for the gate above. `verify_no_orphans` proves the
        sixteen mortal regions stay connected with every wall deleted; this
        asserts the consequence the player actually needs — that the region
        every key is in can be reached on foot from the start, holding nothing.
        """
        g = self.game()
        prog = progression.snapshot(g.state, g.skills, readiness=g._readiness())
        for key in world.KEYS:
            boss = world.BOSS_BY_ID[key["boss"]]
            if boss.get("final"):
                continue        # the Castle is an event wall; see the next test
            path = progression.path_between(prog, "python_village",
                                            boss["region"])
            self.assertTrue(path or boss["region"] == "python_village",
                            f'{boss["id"]} lives somewhere unreachable: '
                            f'{boss["region"]}')

    def test_the_readiness_bar_speaks_before_the_map_does(self):
        """Order matters on the final boss and only there. The Castle opens on
        an event rather than a road, so a player who is not ready must hear the
        thing they can act on — not be sent to walk somewhere still sealed."""
        g = self.game()
        refusal = g.start_boss("the_interviewer")
        self.assertEqual(refusal["error"], "not ready")

    def test_an_old_save_with_no_arrival_list_is_not_stranded(self):
        """A geography gate that locked existing saves out of eleven mentor
        chains would be a worse bug than the one it fixed. Beating a boss and
        holding its key are both proof of presence."""
        from gauntlet import story
        g = self.game()
        g.state["story"].pop("regions_entered", None)
        g.state["cleared_bosses"] = ["graph_necromancer"]
        entered = story.build_context(g.state, g.skills)["regions_entered"]
        self.assertIn("graph_wastes", entered)


class TheSealedRule(GameTest):
    """docs/10-sealed-views.md, section 4, finding by finding.

    A measured run may see the WORLD. It may not see the PROBLEM.
    """

    def measured(self):
        g = self.game()
        g.start_interview("LIVE_SCREEN")
        return g

    def test_nothing_pays_in_the_gap_between_two_questions(self):
        """THE HOLE UNDER THE WRITE CLAUSE.

        `finalexam.sealed(encounter, capability)` is the one capability check
        and it is the right question — asked of an ENCOUNTER. Between two
        questions of a measured run there is not one, so every door that asked
        it with `self.encounter` answered "not sealed" in the gap. The town's
        doors are doors that pay:

            start_interview("FINAL_EXAM")   # the run is open, no question yet
            heal()                          # stamina 1 -> 20, free, mid-exam

        `Game._antagonist` already carried this paragraph for its own case.
        `_sealed_for` is it, named, so the next door does not rediscover it.
        """
        from gauntlet import upkeep
        g = self.game()
        g.state["player"]["stamina"] = 1
        g.state["player"]["gold"] = 500
        upkeep.ensure(g.state)
        for piece in upkeep.PIECES:
            upkeep._set_integrity(g.state, piece, 40)
        g.save()
        g.start_interview("FINAL_EXAM")
        self.assertIsNone(g.encounter, "this test is about the gap")
        for label, out in (("heal", g.heal()),
                           ("repair", g.repair()),
                           ("repair_quote", g.repair_quote()),
                           ("sanctuary_rest", g.sanctuary_rest("")),
                           ("respec", g.respec()),
                           ("allocate", g.allocate("HASTE", 1)),
                           ("equip", g.equip("rusty_blade")),
                           ("unequip", g.unequip("weapon")),
                           ("diagnostic_finish", g.diagnostic_finish({}))):
            self.assertEqual(out.get("error"), "sealed",
                             f"{label} paid into the world in the gap")
        self.assertEqual(g.state["player"]["stamina"], 1)
        self.assertEqual(g.state["player"]["gold"], 500)
        self.assertEqual([upkeep.integrity(g.state, p) for p in upkeep.PIECES],
                         [40] * len(upkeep.PIECES))

    def test_the_placement_is_taken_once_and_cannot_be_farmed(self):
        """MASTERY MOVES ONLY ON GRADED EVIDENCE, and this was the exception.

        `diagnostic.seed_skills` is the one place mastery moves without a
        graded attempt, bounded so it stays weak evidence. It was not bounded
        against being called twice: mastery ADDS, and the writing trial books
        an attempt, a clear and an UNAIDED clear every time. Fifty POSTs bought
        fifty unaided clears with no code run anywhere, and unaided clears are
        what the readiness model and the castle gate are counted in.
        """
        g = self.game()
        answers = {t: {"correct": True} for t in
                   ("t1-read", "t2-write", "t3-structure", "t4-pattern",
                    "t5-complexity")}
        first = g.diagnostic_finish(answers)
        self.assertFalse(first.get("already"))
        python = g.skills["PYTHON"]
        once = (python.mastery, python.clears, python.unaided_clears,
                python.attempts)
        for _ in range(30):
            again = g.diagnostic_finish(answers)
        python = g.skills["PYTHON"]
        self.assertEqual((python.mastery, python.clears, python.unaided_clears,
                          python.attempts), once,
                         "the placement was farmed for unaided clears")
        self.assertEqual(python.unaided_clears, 1)
        # And a repeat is answered rather than refused: a client retrying a
        # dropped response must not be left with nothing.
        self.assertTrue(again.get("already"))
        self.assertTrue(again.get("chapter"))
        self.assertNotIn("error", again)

    def test_the_town_square_does_not_contradict_its_own_repair_desk(self):
        """One number, two doors, two answers.

        `repair_quote(sealed=True)` says nothing is being worn in here. The
        `loop` block beside it on the SAME payload was built without the seal
        and quoted a mending bill, the piece that wanted it and the share of
        income it came to. Finding 4.E's defect — a number that is not a hint
        and is still false — through a door nobody re-checked.
        """
        g = self.game()
        free = g.town()
        self.assertFalse(free["loop"]["sealed"])
        g.start_interview("LIVE_SCREEN")
        town = g.town()
        self.assertEqual(town["quote"].get("error"), "sealed")
        self.assertTrue(town["loop"]["sealed"], "and the loop block agrees")
        self.assertEqual(town["loop"]["quote_now"], 0)
        self.assertEqual(town["loop"]["next_repair"], {})
        self.assertEqual(town["loop"]["upkeep_per_encounter"], 0.0)
        self.assertIn("quote_now", town["loop"]["suspended"])
        # DEGRADE, not refuse: the world half is still served.
        self.assertTrue(town["loop"]["income_per_encounter"])
        self.assertTrue(town["loop"]["escape_hatch"])
        self.assertTrue(town["loop"]["free"])

    def test_a_degraded_view_is_not_shipped_under_a_refusal(self):
        """`server._reply` answers 409 to anything carrying `error: "sealed"`.

        `antagonist_view` degrades — it keeps the standing and the pressure and
        empties the lines — and then splatted `finalexam.refuse()` on top, so
        the half it had carefully served arrived under a status code meaning
        there was no answer. `finalexam.suspended` is the same sentence without
        the key that turns a served view into a refusal.
        """
        g = self.measured()
        view = g.antagonist_view()
        self.assertNotIn("error", view, "a degrade must not answer 409")
        self.assertTrue(view["sealed"])
        self.assertEqual(view["capability"], "MENTOR")
        self.assertTrue(view["message"])
        self.assertEqual(view["lines"], [], "and he still says nothing")
        # The world half: his standing is graded evidence and survives.
        self.assertTrue(any(view.get(k) is not None
                            for k in ("standing", "register", "pressure")),
                        f"nothing of the herald survived: {sorted(view)}")
        # The two shapes are deliberately different and stay different.
        self.assertEqual(finalexam.refuse("MENTOR")["error"], "sealed")
        self.assertNotIn("error", finalexam.suspended("MENTOR"))
        self.assertEqual(finalexam.suspended("MENTOR")["message"],
                         finalexam.refuse("MENTOR")["message"])

    def test_the_hunt_note_describes_the_number_it_is_standing_next_to(self):
        """The note said the readiness score reads zero. It reads nine.

        A sealed readiness is every BUILD term zeroed, not the whole score:
        the rung term is where the player stands on the ladder and no seal
        suspends that. A line that overstates what the seal took is the same
        defect as a number that overstates what the build gives.
        """
        g = self.game()
        free = g.hunt_view("python_village")["readiness"]["score"]
        g.start_interview("LIVE_SCREEN")
        view = g.hunt_view("python_village")
        self.assertTrue(view["sealed"])
        self.assertLess(view["readiness"]["score"], free)
        self.assertGreater(view["readiness"]["score"], 0,
                           "a sealed readiness is the build zeroed, not the "
                           "whole score")
        self.assertIn("not simply absent", view["seal_note"])
        self.assertIn("where you are on the ladder", view["seal_note"])
        # And the world half is served whole and provably player-independent.
        self.assertEqual(view["pace"], g.hunt_view("python_village")["pace"])
        self.assertTrue(view["pace"])

    def test_a_the_problem_lookup_cannot_be_told_which_mode_to_use(self):
        g = self.game()
        # Out of a run the lookup is the full teaching view, and stays so.
        teachable = g.teachable[0].id
        self.assertTrue(g.problem(teachable)["pattern"])
        g.start_interview("LIVE_SCREEN")
        served = g.interview_current()["problem"]["id"]
        leaked = g.problem(served, mode=config.MODE_ADVENTURE)
        # Every rung of the crutch ladder the lookup used to hand over for the
        # question on the screen, asked for by name. `player_view("interview")`
        # drops the keys rather than emptying them, so `falsy` is the check.
        for crutch in ("hint_tree", "pattern", "visualization",
                       "common_failures", "optimal_complexity", "variants",
                       "prerequisites"):
            self.assertFalse(leaked.get(crutch),
                             f"{crutch} leaked through /api/problem mid-run")
        # And it is not only the served question: while a run is open, every
        # lookup is the interview view. The rule is a property of the RUN, not
        # a list of ids somebody has to keep up to date.
        self.assertEqual(g.problem(teachable).get("pattern"), "REDACTED")

    def test_b_prior_attempts_no_longer_name_the_family_mid_run(self):
        g = self.game()
        problem = g.teachable[0]
        g.start_encounter(problem.id)
        g.submit("def nope():\n    return None\n")
        self.assertTrue(g.performance_history(problem.id)["problem"])
        g.start_interview("LIVE_SCREEN")
        sealed = g.performance_history(problem.id)
        self.assertEqual(sealed["problem"], [])
        self.assertTrue(sealed["sealed"])
        self.assertTrue(sealed["recent"] is not None, "the totals stay")

    def test_d_the_region_card_stops_quoting_a_step_that_is_not_in_force(self):
        g = self.game()
        self.assertIsNotNone(g.region_view("python_village")["element"]["step"])
        g.start_interview("LIVE_SCREEN")
        card = g.region_view("python_village")
        self.assertIsNone(card["element"]["step"])
        self.assertTrue(card["element"]["sealed"])
        self.assertTrue(card["name"], "the geography stays")

    def test_e_the_loadout_degrades_instead_of_lying(self):
        g = self.measured()
        kit = g.loadout()
        self.assertTrue(kit["sealed"])
        self.assertEqual(kit["effects"], {})
        self.assertEqual(kit["probe_charges"], 0)
        self.assertEqual(kit["strike_element"], "")
        self.assertTrue(kit["seal_note"])
        # What you OWN is still yours to read.
        self.assertEqual(kit["slots"], __import__(
            "gauntlet.items", fromlist=["SLOTS"]).SLOTS)
        self.assertIn("inventory", kit)
        self.assertIn("attributes", kit)

    def test_f_the_hunt_degrades_rather_than_refusing(self):
        from gauntlet import hunters
        g = self.measured()
        view = g.hunt_view("hashmap_highlands")
        self.assertNotIn("error", view)
        self.assertTrue(view["sealed"])
        self.assertTrue(view["seal_note"])
        # The readiness half is computed WITHOUT the build, which is the only
        # honest number available while the build is suspended. A run must
        # never be handed a preparation score that counts gear it cannot use.
        self.assertEqual(
            view["readiness"]["score"],
            g._readiness_for("hashmap_highlands", sealed=True).score)
        self.assertLessEqual(
            view["readiness"]["score"],
            g._readiness_for("hashmap_highlands", sealed=False).score)
        # The half that is provably player-independent is served in full.
        self.assertEqual(view["pace"], hunters.pace_for("hashmap_highlands"))
        self.assertTrue(view["apex"])

    def test_f_the_pace_ramps_by_chapter_rather_than_being_flat(self):
        from gauntlet import hunters
        early = hunters.pace_for("python_village")
        late = hunters.pace_for("coding_coliseum")
        self.assertLess(early["casts_ready"], late["casts_ready"])
        self.assertLess(early["strike_unready"], late["strike_unready"])
        self.assertEqual(early["stance"], hunters.TEACHES)
        self.assertEqual(late["stance"], hunters.TESTS)

    def test_g_a_measured_run_may_read_the_shrine_and_is_not_paid_for_it(self):
        g = self.measured()
        g.shrine()
        before = dict(g.state["player"])
        before_skills = {k: v.mastery for k, v in g.skills.items()}
        out = g.shrine_answer(g.state["_shrine"]["answers"][0])
        self.assertFalse(out["paid"])
        self.assertEqual(out["xp"], 0)
        self.assertEqual(g.state["player"]["stamina"], before["stamina"])
        self.assertEqual({k: v.mastery for k, v in g.skills.items()},
                         before_skills)

    def test_h_the_save_export_no_longer_ships_the_unserved_holdout(self):
        g = self.measured()
        self.assertTrue(g.state["interview"]["problem_ids"])
        blob = g.export()
        self.assertEqual(blob.get("error"), "sealed")
        self.assertNotIn("state", blob, "a refusal must not look like a partial save")
        self.assertNotIn("attempts", blob)

    def test_h_the_practical_roster_is_redacted_too(self):
        g = self.game()
        g.start_interview("FINAL_EXAM")
        self.assertTrue(g.state.get("exam"))
        blob = g.export()
        self.assertEqual(blob.get("error"), "sealed")
        self.assertNotIn("state", blob)

    def test_the_world_half_stays_readable_throughout(self):
        """A seal that takes more than it needs is one players turn off."""
        g = self.measured()
        for name, call in (
            ("town", lambda: g.town()),
            ("portal", lambda: g.portal()),
            ("keyring", lambda: g.keyring()),
            ("rollcall", lambda: g.roll_call()),
            ("world_map", lambda: g.world_map()),
            ("todo", lambda: g.things_to_do()),
        ):
            out = call()
            self.assertTrue(out, f"{name} came back empty during a run")
            if isinstance(out, dict):
                self.assertNotIn("error", out, f"{name} refused")


class TheOneWhoIsWatching(GameTest):
    """gauntlet/antagonist.py was written and then imported by nothing.

    An orphan module in a codebase whose own README claims zero of them is a
    defect on its own, and this one is the brief's "he antagonizes the player
    at each boss, each progression". It is wired to the three occasions this
    pass created — a boss down, a key taken, the fourteenth ward lit — plus
    arrival in a region, and to one GET.
    """

    def test_he_reads_a_line_over_a_kill_and_over_its_key(self):
        g = self.game()
        event = clear_boss(self, g, "hash_titan")
        said = {row["occasion"] for row in (event.get("watching") or [])}
        self.assertIn(antagonist.BOSS_FELLED, said)
        self.assertIn(antagonist.KEY_TAKEN, said)
        for row in event["watching"]:
            self.assertFalse(row["blocking"], "he is weather, never a modal")
            self.assertTrue(row["lines"])

    def test_he_notices_an_arrival_once_and_not_every_step(self):
        g = self.game()
        first = g.move("graph_wastes", 4, 4)
        self.assertTrue(first["arrived"])
        self.assertTrue(first["watching"])
        again = g.move("graph_wastes", 5, 5)
        self.assertFalse(again["arrived"])
        self.assertIsNone(again["watching"])

    def test_he_does_not_speak_into_a_measurement(self):
        """The seal is asked of the RUN, not of an encounter that may not exist
        between two questions of one — which is how he would have spoken into
        the gaps."""
        g = self.game()
        self.assertTrue(g.antagonist_view()["lines"])
        g.start_interview("LIVE_SCREEN")
        sealed = g.antagonist_view()
        self.assertEqual(sealed["lines"], [])
        self.assertTrue(sealed["sealed"])
        self.assertIsNone(g.move("graph_wastes", 4, 4)["watching"])

    def test_the_module_audits_itself(self):
        self.assertTrue(antagonist.self_check()["ok"],
                        antagonist.self_check())


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
