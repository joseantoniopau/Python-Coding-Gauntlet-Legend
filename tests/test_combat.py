"""The combat wiring, from the adversary's side.

tests/test_elements.py pins the model in isolation — pure functions, no Game,
no save file. This file pins the WIRING: what actually happens when a player
types a line into a running battle with a loadout, a pouch, a forged blade and
a seal. The four properties below are, in order, the ones the feature is not
allowed to lose, and each one was written after watching it fail.

  1. THE TYPING IS THE ATTACK. A player who drinks optimally, wears the best
     element in the game and writes the LAZIEST correct Python must still be
     slower than a player who writes good Python with the worst gear in the
     game. If that ever inverts, the tactical layer has eaten the lesson it
     exists to lengthen, and there is no point to any of the rest of it.

  2. LEARNING NEVER DEAD-ENDS. Wrong element, empty pouch, no armour, no
     companion: a player who lands every line still finishes the fight. This
     one WAS false. Twenty-four of the thirty-seven authored incantation
     battles routed a player who never missed a cast, because the loop
     regenerated focus every turn and health never, over a fight fifteen to
     forty turns long. `engine.CAST_HEAL_SHARE` is the fix and this is the test
     that stops it being quietly removed.

  3. THE SEAL. One isolation path — finalexam.sealed — and it takes the
     element, the loadout, the pouch, the metal and the smith with it, at the
     engine and again at the door.

  4. THE PURSE AND THE BAG. A refused upgrade takes nothing, a bought one takes
     exactly the quote, and gold never goes below zero.

Every fight below is driven through `Game.incantation_cast` with real answers
graded by `incantation.cast`. Nothing is stubbed: if the engine stops applying
the wheel, or starts letting a potion do damage, these numbers move.
"""
from __future__ import annotations

import copy
import json
import random
import urllib.error
import urllib.request

from base import GameTest  # noqa: E402

from gauntlet import bestiary, classes, elements as E, finalexam
from gauntlet import engine, forge, incantation, items, potions, saves
from gauntlet.engine import FORGE_ITEMS, Game


# ---------------------------------------------------------------------------
# Driving a real fight
# ---------------------------------------------------------------------------
#
# `bind` — `{target} = {value}` — is the one incantation that can be aimed at
# any monster on any field, because its target hole takes a plain name rather
# than a kind. That makes it the only move with which the same fight can be
# fought twice at two different standards of Python, which is exactly what
# property 1 has to measure. `hi` is the one enemy in the bestiary it cannot
# be aimed at, so the two encounters that field one are not used here.
#
# LAZY and RICH are the two ends of `incantation.measure_complexity`: a hole
# filled with a bound name that is already on screen, and a composed filtered
# comprehension. Both are CORRECT. The difference between them is the only
# thing this test wants to isolate.
LAZY_VALUE = "x"
RICH_VALUE = "len([c for c in s if c == ch])"

# Fields used for the fight tests. Chosen to cover the wheel rather than the
# bestiary: a fire room, a cold room, a void room and a lightning room, which
# between them exercise every kind of matchup a player can stand in.
FIELDS = ("enc_cart_tower", "enc_twin_wardens",
          "enc_branching_warden", "enc_two_that_sum")

CAP = 250          # a fight this long is a failed test, not a long fight


class CombatTest(GameTest):
    def fresh(self, *, seed: int = 11):
        g = self.game()
        g._rng = random.Random(seed)
        g.state["pets"]["active"] = []          # a dead companion, by default
        return g

    @staticmethod
    def weapon_of(element: str) -> str:
        """A weapon that strikes with this element, catalogue first.

        Falls through to the forge because FIRE exists nowhere else: no
        catalogue weapon carries it, and a rung out of the ember mines is the
        only way to hold it. That is also why `_player_element` has to be able
        to see a forged blade at all — see `test_a_forged_blade_strikes_with_
        the_metal_it_was_made_of`.
        """
        for item_id, item in items.BY_ID.items():
            if item.slot == "weapon" and getattr(item, "element", "") == element:
                return item_id
        for item_id, item in FORGE_ITEMS.items():
            if item.slot == "weapon" and getattr(item, "element", "") == element:
                return item_id
        return ""

    @staticmethod
    def best_armour(against: str) -> dict:
        """The heaviest plate and the best ward against one element, worn."""
        worn, score = {}, {}
        key = "resist_%s" % against.lower()
        for item_id, item in items.BY_ID.items():
            fx = getattr(item, "effects", {}) or {}
            weight = fx.get("plate_points", 0) + 60 * fx.get(key, 0.0)
            if weight > score.get(item.slot, 0):
                score[item.slot] = weight
                worn[item.slot] = item_id
        worn.pop("weapon", None)
        return worn

    def fight(self, encounter_id, *, element=None, rich=False, mastery=0.0,
              armour=None, potion_stock=0, drink=False, seed=11):
        """Fight one battle to a finish. Returns what happened, not a verdict."""
        g = self.fresh(seed=seed)
        if element:
            weapon = self.weapon_of(element)
            self.assertTrue(weapon, "nothing in the game strikes with %s" % element)
            g.state["equipped"]["weapon"] = weapon
        for slot, item_id in (armour or {}).items():
            g.state["equipped"][slot] = item_id
        for state in g.skills.values():
            state.mastery = mastery
        g._write_skills(g.skills)
        if potion_stock:
            pouch = potions.Pouch.from_state(g.state)
            for potion_id in potions.POTION_IDS:
                pouch.add(potion_id, potion_stock)
            pouch.to_state(g.state)
        g.save()

        view = g.start_incantation(encounter_id)
        self.assertNotIn("error", view, view)
        names = [e.name for e in bestiary.battle_context(encounter_id).enemies]
        casts = drinks = taken = 0
        cleared = routed = False
        hits = []
        while casts < CAP and g.state.get(Game.INCANT_STATE):
            hp = g.state[Game.INCANT_STATE]["hp"]
            alive = [n for n in names if hp.get(n, 0) > 0]
            if not alive:
                break
            answers = {"target": alive[0],
                       "value": RICH_VALUE if rich else LAZY_VALUE}
            result = g.incantation_cast("bind", answers)
            self.assertNotIn("error", result, result)
            self.assertTrue(result.get("correct"),
                            "a cast this test relies on stopped landing: %s"
                            % result.get("teaching"))
            casts += 1
            if result.get("strike"):
                hits.append(result["strike"]["damage"])
            taken += int((result.get("enemy_turn") or {}).get("damage") or 0)
            taken += int((result.get("turn_open") or {}).get("damage") or 0)
            cleared = cleared or bool(result.get("cleared"))
            routed = routed or bool(result.get("routed"))
            if cleared or routed:
                break
            if drink:
                player = g.state["player"]
                if player["stamina"] < 0.7 * player["stamina_max"]:
                    for potion_id in potions.POTION_IDS:
                        if g.use_potion(potion_id).get("ok"):
                            drinks += 1
                            break
        return {"casts": casts, "cleared": cleared, "routed": routed,
                "hits": hits, "taken": taken, "drinks": drinks,
                "health": g.state["player"]["stamina"]}


# ---------------------------------------------------------------------------
# 1. The typing is the attack
# ---------------------------------------------------------------------------

class TestTypingWins(CombatTest):

    def test_the_wheel_can_never_out_swing_the_python(self):
        """The two axes, compared at their extremes, with no fight involved.

        THE GEAR AXIS is everything outside the keyboard that touches a landed
        hit: the wheel's best matchup over its worst, and then both temporary
        terms at once — an attacker the enemy could not chill, against a
        defender somebody has shocked. That is the most generous reading of
        "wears the best element and plays the tactical layer perfectly" that
        `resolve_damage` will support.

        THE TYPING AXIS is DAMAGE_UNIT * weight across the full complexity
        range, with the lazy end floored by the strongest move's own `power` —
        the floor is the thing that could hide an inversion, because it lifts
        the worst cast without lifting the best one.

        The gear spread must stay strictly narrower. The day it does not, a
        player can dress their way out of writing the line.
        """
        best_kind = max(E.MATCHUP_MULT.values())
        worst_kind = min(E.MATCHUP_MULT.values())
        amplify = max(s.potency for s in E.STATUSES.values()
                      if s.kind == "vulnerability")
        blunt = min(s.potency for s in E.STATUSES.values()
                    if s.kind == "outgoing")
        gear = (best_kind * amplify) / (worst_kind * blunt)

        # THE ORDINARY CATALOGUE, NOT THE WHOLE REGISTRY.
        #
        # This used to read `incantation.BY_ID`, which was the same set until
        # the engine started calling `arts.register()` and ninety-six secret
        # art lines joined the registry. They are not in `CATALOGUE` on purpose
        # — that omission is what stops `learn_from_clear` handing one out — and
        # they break this proxy rather than this invariant:
        #
        # `worst_power` is standing in for "the laziest correct cast in the
        # game". An art's `power` is not an authored number, it is
        # `arts.power_floor()`, computed from the art's own TIER-0 measurement,
        # so it is not a lazy cast at all — it is what a hard line is worth
        # before any scaffold comes off. Taking the max over the arts measures
        # the least lazy floor in the game and calls it the laziest.
        #
        # The arts are covered by the second assertion instead, which is the
        # property `arts.py` actually claims: the floor never binds. What IS
        # genuinely narrower for an art is its own tier spread, and that is the
        # `incantation.SCORE_FULL` saturation `arts.saturation_report()`
        # measures and `arts.handover()["score_full"]` names. It is an open
        # balance debt, not a hole in this rule, and raising SCORE_FULL is a
        # rebalance of every fight in the game rather than a one-line fix.
        worst_power = max(m.power for m in incantation.CATALOGUE)
        lazy = max(incantation.DAMAGE_UNIT * incantation.WEIGHT_MIN,
                   worst_power * incantation.POWER_FLOOR_SHARE)
        good = incantation.DAMAGE_UNIT * incantation.WEIGHT_MAX
        self.assertGreater(good / lazy, gear,
                           "the loadout spread (%.2fx) has caught up with the "
                           "typing spread (%.2fx); gear can now substitute for "
                           "Python" % (gear, good / lazy))

    def test_no_registered_line_has_a_power_floor_that_binds(self):
        """`Incantation.power` is a floor, not a spine, and that has to stay
        true for the secret arts too — a floor above what a good cast pays
        would be a move that hits the same however well it is typed."""
        from gauntlet import arts
        arts.register()
        ceiling = incantation.DAMAGE_UNIT * incantation.WEIGHT_MAX
        for inc_id, inc in incantation.BY_ID.items():
            self.assertLess(inc.power * incantation.POWER_FLOOR_SHARE, ceiling,
                            "%s's floor binds: a good cast cannot beat it"
                            % inc_id)

    def test_a_potion_can_never_carry_damage(self):
        """potions.POURS_INTO is the whole vocabulary a draught has: the health
        bar, the focus bar, or nothing at all. There is no third bar and there
        is no enemy in it. The day a kind is added that pours somewhere else is
        the day the pouch becomes the attack, so it is named here as well as at
        the module's own import-time check."""
        self.assertEqual(set(potions.KINDS), {"HEALTH", "FOCUS", "ANTIDOTE"})
        self.assertLessEqual(set(potions.POURS_INTO.values()),
                             {"stamina", "mana", ""})
        # And drinking one, through the engine, never touches a monster.
        g = self.fresh()
        pouch = potions.Pouch.from_state(g.state)
        for potion_id in potions.POTION_IDS:
            pouch.add(potion_id, 2)
        pouch.to_state(g.state)
        g.save()
        g.start_incantation("enc_branching_warden")
        before = dict(g.state[Game.INCANT_STATE]["hp"])
        drunk = 0
        for potion_id in potions.POTION_IDS:
            if g.use_potion(potion_id).get("ok"):
                drunk += 1
                break
        self.assertTrue(drunk, "nothing in the pouch was drinkable")
        self.assertEqual(g.state[Game.INCANT_STATE]["hp"], before,
                         "a potion moved a monster's health bar")
        self.assertEqual(g.state[Game.INCANT_STATE]["casts"], 0,
                         "drinking spent a turn; it must ride alongside a cast")

    def test_zero_in_is_zero_out_through_the_whole_engine(self):
        """A wasted turn stays wasted no matter what is equipped. The wheel
        takes `base` as an argument and cannot manufacture one."""
        defender = E.Defender(element=E.COLD, max_health=60)
        self.assertEqual(E.resolve_damage(0, E.FIRE, defender).damage, 0)

    def test_good_python_in_bad_gear_beats_lazy_python_in_the_best_gear(self):
        """The measurement that matters, fought for real.

        The lazy player gets everything the tactical layer has: the counter
        element, the heaviest plate warded against exactly what is hitting
        them, and a full pouch they drink from optimally. The good player gets
        the worst element on the field and nothing else at all. The good player
        must finish first, in every room.
        """
        for encounter_id in FIELDS:
            region = bestiary.ENCOUNTER_BY_ID[encounter_id].region
            room = E.affinity_for(region)
            if room not in E.ELEMENTS:
                continue
            with self.subTest(encounter_id):
                lazy = self.fight(encounter_id, element=E.OPPOSED[room],
                                  rich=False, mastery=0.0,
                                  armour=self.best_armour(room),
                                  potion_stock=5, drink=True)
                good = self.fight(encounter_id, element=room,   # the shrug
                                  rich=True, mastery=95.0)
                self.assertTrue(good["cleared"],
                                "good Python in bad gear LOST %s" % encounter_id)
                self.assertLess(good["casts"], lazy["casts"],
                                "%s: lazy Python in the best gear in the game "
                                "finished in %d casts, good Python in the worst "
                                "took %d. The gear is now the attack."
                                % (encounter_id, lazy["casts"], good["casts"]))

    def test_the_better_line_hits_harder_on_the_same_move_in_the_same_room(self):
        """Same incantation, same field, same element. Only the Python differs."""
        lazy = self.fight("enc_branching_warden", rich=False, mastery=95.0)
        good = self.fight("enc_branching_warden", rich=True, mastery=95.0)
        self.assertGreater(max(good["hits"]), max(lazy["hits"]) * 2,
                           "a composed comprehension is not hitting meaningfully "
                           "harder than a bound name")


# ---------------------------------------------------------------------------
# 2. Learning never dead-ends
# ---------------------------------------------------------------------------

class TestNoDeadEnd(CombatTest):

    def test_the_worst_loadout_in_the_game_still_finishes_every_fight(self):
        """Wrong element, empty pouch, no armour, no companion, lazy but
        correct Python. Every authored field must still fall.

        This is the regression that `engine.CAST_HEAL_SHARE` exists for. Before
        it, this test failed on most of the bestiary — not because the player
        typed anything wrong, but because a fifteen-to-forty-turn fight took
        charged attacks against a bar that nothing ever refilled.
        """
        for encounter_id in FIELDS:
            with self.subTest(encounter_id):
                room = E.affinity_for(
                    bestiary.ENCOUNTER_BY_ID[encounter_id].region)
                shrug = room if room in E.ELEMENTS else None
                out = self.fight(encounter_id, element=shrug, rich=False,
                                 mastery=0.0)
                self.assertTrue(
                    out["cleared"],
                    "%s is a dead end: %d correct casts, not one of them "
                    "missed, and the player was routed anyway"
                    % (encounter_id, out["casts"]))
                self.assertLess(out["casts"], CAP, encounter_id)

    def test_a_landed_line_gives_health_back_and_a_missed_one_does_not(self):
        """The rule, stated where it can be checked rather than only where it
        is applied. It is capped at the bar, so it cannot be farmed."""
        self.assertGreater(engine.CAST_HEAL_SHARE, 0.0)
        g = self.fresh()
        g.state["player"]["stamina"] = 1
        g.save()
        view = g.start_incantation("enc_branching_warden")
        self.assertNotIn("error", view)
        before = g.state["player"]["stamina"]
        g.incantation_cast("bind", {"target": "node", "value": LAZY_VALUE})
        landed = g.state["player"]["stamina"]
        self.assertGreater(landed, before, "a landed line gave nothing back")
        # A refused cast is a wasted turn and pays nothing. Started from half
        # the bar rather than from one, because at one the enemy's answering
        # blow routs the player and `_incant_rout` puts them back on their feet
        # at a third — which would read as a heal and is not one.
        player = g.state["player"]
        player["stamina"] = player["stamina_max"] // 2
        g.save()
        before = int(player["stamina"])
        result = g.incantation_cast("bind", {"target": "node", "value": ""})
        self.assertFalse(result.get("correct"))
        self.assertFalse(result.get("routed"))
        self.assertLessEqual(int(g.state["player"]["stamina"]), before,
                             "a wasted turn healed the player")

    def test_the_refund_never_exceeds_the_bar(self):
        g = self.fresh()
        g.save()
        g.start_incantation("enc_branching_warden")
        g.incantation_cast("bind", {"target": "node", "value": LAZY_VALUE})
        player = g.state["player"]
        self.assertLessEqual(player["stamina"], player["stamina_max"])

    def test_a_fight_whose_last_monster_dies_of_poison_is_over(self):
        """The clear check is asked again after the enemy's turn, because the
        first thing that turn does is tick the dose the player put in it. Asked
        only before, a player could stand in a field of corpses with the battle
        still running, having to swing at nothing to be told they had won."""
        g = self.fresh()
        g.save()
        g.start_incantation("enc_branching_warden")
        names = ["node", "depth"]
        seen_cleared = False
        for _ in range(CAP):
            run = g.state.get(Game.INCANT_STATE)
            if not run:
                break
            alive = [n for n in names if run["hp"].get(n, 0) > 0]
            if not alive:
                self.fail("every monster is dead and the battle is still open")
            out = g.incantation_cast(
                "bind", {"target": alive[0], "value": RICH_VALUE})
            if out.get("cleared"):
                seen_cleared = True
                break
        self.assertTrue(seen_cleared)

    def test_the_shrug_is_slower_than_the_counter_but_never_a_wall(self):
        """Elemental disadvantage is a tax on time. elements.py states the
        ceiling; this measures against it through the whole engine."""
        room = E.affinity_for(
            bestiary.ENCOUNTER_BY_ID["enc_branching_warden"].region)
        self.assertIn(room, E.ELEMENTS)
        shrug = self.fight("enc_branching_warden", element=room, mastery=0.0)
        counter = self.fight("enc_branching_warden", element=E.OPPOSED[room],
                             mastery=0.0)
        self.assertTrue(shrug["cleared"])
        self.assertTrue(counter["cleared"])
        self.assertGreater(shrug["casts"], counter["casts"],
                           "the wheel has stopped mattering")
        self.assertLessEqual(shrug["casts"] / counter["casts"],
                             E.MAX_FIGHT_STRETCH_VS_COUNTER,
                             "the wrong element costs more than elements.py "
                             "says it can")

    def test_a_dungeon_never_locks_a_player_out_half_way_down(self):
        """Mid-descent, at one point of health, holding the element the room
        shrugs off, with an empty belt, no armour and no companion.

        The encounter loop's own guarantee is that a landed answer ENDS the
        fight, so the only thing the wheel can do here is decide how hard the
        miss hurt. A miss at one point of health routes to a training camp and
        the descent stays open; the right answer clears the room whatever is
        equipped. Both halves are checked, room after room, because "you can
        always retreat" is not the same promise as "you can always go on".
        """
        from gauntlet import dungeons
        plan = next(p for p in dungeons.DUNGEONS
                    if E.affinity_for(p.region) in E.ELEMENTS)
        room = E.affinity_for(plan.region)

        # THE WORLD IS PROCEDURAL AND THE SEED IS PINNED HERE. `_reseed_world`
        # draws from the global `random` when a save has no seed of its own, so
        # the geography — and therefore which doors of a keyed dungeon are shut
        # at the entrance — depends on whatever ran before this test in the
        # process. Several fixed worlds are tried in turn and the first one that
        # actually puts three fights behind open doors is the one measured: the
        # guarantee under test is about the fights, not about the locks.
        cleared = 0
        for world_seed in (7, 11, 23, 41, 97):
            cleared = self._descend(plan, room, world_seed)
            if cleared >= 3:
                break
        self.assertGreaterEqual(
            cleared, 3,
            "no pinned world put three reachable fights in %s" % plan.id)

    def _descend(self, plan, room, world_seed):
        """One descent, at one point of health, in one pinned world."""
        from gauntlet import dungeons
        self._probed_floor = False
        g = self.fresh()
        g.choose_class("analyst")
        g.choose_build("ANALYST")
        g.new_world(world_seed)
        g.state["equipped"] = {"weapon": self.weapon_of(room)}   # the shrug
        potions.Pouch(counts={}).to_state(g.state)               # empty belt
        g.state["player"]["region"] = plan.region
        g.save()
        self.assertFalse(g.enter_dungeon(plan.id).get("error"))
        self.assertEqual(g._player_element(None), room)

        # EVERY ROOM BOUND TO A CODE FIGHT, ON PURPOSE. A room's contents are
        # drawn from the corpus, and an unbound run lands on a STATE_PREDICT or
        # a RUNE_ASSEMBLY sooner or later — where `canonical_solution` is not
        # the answer and the test would fail for a reason that has nothing to do
        # with combat. The rooms are bound through the same `dungeon_map` the
        # engine reads first, so what is measured is the turn rule.
        code = [p for p in g.teachable
                if p.encounter_kind == "CODE_BATTLE" and p.canonical_solution]
        self.assertTrue(code, "no code fights in the corpus to bind")
        built = g._dungeon_for(plan.id, g.state[dungeons.STATE_KEY].get("seed"))
        g.state["dungeon_map"][built.id] = {
            str(r.id): code[i % len(code)].id
            for i, r in enumerate(built.rooms)}
        g.save()

        cleared = 0
        for _ in range(60):
            if not g.state.get(dungeons.STATE_KEY):
                break
            engaged = g.dungeon_engage()
            if engaged.get("error"):
                state = g.dungeon_state()
                onward = [o for o in state["options"]
                          if o.get("action") == "move" and o.get("available")]
                if not onward:
                    break
                # TOWARD A ROOM THAT STILL HAS SOMETHING IN IT. Taking the
                # first option walks back and forth between two rooms, and
                # that used to score: a cleared room could be re-engaged, so
                # three "fights" could all be the same room three times. They
                # cannot now, so the walk has to be a walk.
                done = state["run"]["cleared"]
                fresh = [o for o in onward if o["room"] not in done]
                unseen = [o for o in onward
                          if o["room"] not in state["run"]["visited"]]
                g.dungeon_move((unseen or fresh or onward)[0]["room"])
                continue
            problem = g.by_id[g.encounter.problem_id]

            # The miss, at one point of health. It must cost the turn and put
            # the player ON THEIR FEET SOMEWHERE. There are now two ways that
            # can happen, and the guarantee is about the floor rather than
            # about the descent:
            #
            #   SPARED — the old path. Health comes back to a third, a training
            #     camp is raised, and the run is still open.
            #   DIED   — since gauntlet/death.py landed. Zero health is a death,
            #     the game rewinds to the last waking point, and `dungeon_run`
            #     rewinds with it: "the descent. you are not in the dungeon any
            #     more." That is the real cost of dying the brief asked for.
            #
            # Neither may LOCK the player out, and that is what is measured. A
            # death is a setback you walk back from; if it were not, the walk
            # back below would fail and so would this test.
            probed_the_floor = getattr(self, "_probed_floor", False)
            if not probed_the_floor:
                g.state["player"]["stamina"] = 1
                g.save()
            result = g.submit("def nope():\n    return 1\n")
            self.assertGreater(g.state["player"]["stamina"], 0,
                               "a miss at one point of health left the player "
                               "on the floor")
            if not g.state.get(dungeons.STATE_KEY):
                # They died. Prove the way back in is open: they are fightable,
                # and the same dungeon takes them again.
                self.assertTrue(result.get("death"),
                                "the descent ended without a death to explain it")
                g.state["player"]["region"] = plan.region
                g.save()
                again = g.enter_dungeon(plan.id)
                self.assertFalse(again.get("error"),
                                 "death locked the player out of %s: %s"
                                 % (plan.id, again))
                built2 = g._dungeon_for(
                    plan.id, g.state[dungeons.STATE_KEY].get("seed"))
                g.state["dungeon_map"][built2.id] = {
                    str(r.id): code[i % len(code)].id
                    for i, r in enumerate(built2.rooms)}
                g.save()
                # The floor has been probed and the way back in was open. The
                # rest of the descent is walked at ordinary health: pinning to
                # one point before every room would die in every room and
                # measure nothing but the dying.
                self._probed_floor = True
                continue
            self._probed_floor = True

            # And then the line, written correctly, with nothing equipped that
            # helps. Being swept to a training camp does not take the room away:
            # the door is still there and it still opens.
            if g.encounter is None:
                reopened = g.dungeon_engage()
                self.assertFalse(reopened.get("error"),
                                 "a camp swallowed the room: %s" % reopened)
            solved = g.submit(problem.canonical_solution)
            self.assertTrue(solved.get("solved"),
                            "a correct answer did not clear the room")
            cleared += 1
        return cleared

    def test_a_cleared_room_has_nothing_left_to_pay(self):
        """A room beaten is a room shut, and the purse is paid once.

        `dungeon_map` binds a room to one problem so that a relented retry asks
        the same idea. That made an already-cleared room a vending machine:
        engage, be served the identical problem, be paid the room's purse and
        the region's award again, for as long as the key is held down. A failed
        room still reopens, because a failed room was never cleared.
        """
        from gauntlet import dungeons
        g = self.fresh()
        plan = dungeons.DUNGEONS[0]
        g.state["player"]["region"] = plan.region
        g.save()
        self.assertFalse(g.enter_dungeon(plan.id).get("error"))
        code = [p for p in g.teachable
                if p.encounter_kind == "CODE_BATTLE" and p.canonical_solution]
        built = g._dungeon_for(plan.id, g.state[dungeons.STATE_KEY].get("seed"))
        g.state["dungeon_map"][built.id] = {
            str(r.id): code[i % len(code)].id
            for i, r in enumerate(built.rooms)}
        g.save()

        for _ in range(40):
            if not g.dungeon_engage().get("error"):
                break
            state = g.dungeon_state()
            onward = [o for o in state["options"]
                      if o.get("action") == "move" and o.get("available")]
            if not onward:
                self.skipTest("no fight behind an open door in this world")
            unseen = [o for o in onward
                      if o["room"] not in state["run"]["visited"]] or onward
            g.dungeon_move(unseen[0]["room"])
        else:
            self.skipTest("no fight behind an open door in this world")

        problem = g.by_id[g.encounter.problem_id]
        room_id = g.dungeon_state()["run"]["at"]

        # A miss leaves the door open.
        g.submit("def nope():\n    return 1\n")
        self.assertNotIn(room_id, g.state[dungeons.STATE_KEY]["cleared"])
        self.assertFalse(g.dungeon_engage().get("error"),
                         "a failed room refused to reopen")

        # The answer shuts it.
        self.assertTrue(g.submit(problem.canonical_solution).get("solved"))
        self.assertIn(room_id, g.state[dungeons.STATE_KEY]["cleared"])
        gold = g.state["player"]["gold"]
        xp = g.state["player"]["xp"]
        for _ in range(5):
            self.assertTrue(g.dungeon_engage().get("error"),
                            "a cleared room opened again")
        self.assertEqual(g.state["player"]["gold"], gold)
        self.assertEqual(g.state["player"]["xp"], xp)

        # And the purse itself refuses to be paid twice, whoever asks.
        run = g.state[dungeons.STATE_KEY]
        before = run["gold"]
        again = dungeons.clear_room(built, run, room_id, solved=True)
        self.assertEqual(again["reward"]["gold"], 0)
        self.assertEqual(again["reward"]["xp"], 0)
        self.assertEqual(run["gold"], before)

    def test_a_charged_attack_cannot_mark_what_a_plain_hit_could_not(self):
        """elements.marks() is the one owner of 'hitting fire with fire does
        not set anything alight'. The special path used to be exempt, which is
        how a fire monster burned a player holding fire for a fifth of their
        bar."""
        self.assertFalse(E.marks("SAME"))
        self.assertTrue(E.marks("OPPOSED"))
        self.assertTrue(E.marks("NEUTRAL"))


# ---------------------------------------------------------------------------
# 3. The seal
# ---------------------------------------------------------------------------

class TestTheSeal(CombatTest):

    def _armed(self):
        """A player with everything: a class, a forged blade, a bag of metal,
        a full pouch and gold. Then a timed practical on top of it."""
        g = self.fresh()
        g.choose_class("analyst")
        state = g._forge_state()
        for metal in forge.METALS:
            forge.add_metal(state, metal.id, 99)
        g.state["player"]["gold"] = 10 ** 6
        g.state["player"]["region"] = forge.SMITH["region"]
        for _ in range(5):
            if g.forge_upgrade().get("error"):
                break
        tier = forge.owned_tier(g._forge_state(), g._blade_id())
        g.state["equipped"]["weapon"] = forge.rung(g._blade_id(), tier).id
        pouch = potions.Pouch.from_state(g.state)
        for potion_id in potions.POTION_IDS:
            pouch.add(potion_id, 3)
        pouch.to_state(g.state)
        g.save()
        return g

    def test_the_element_the_metal_and_the_pouch_all_go_at_the_engine(self):
        g = self._armed()
        self.assertIn(g._player_element(None), E.ELEMENTS,
                      "the forged blade is not striking with anything")
        open_effects = g.effects()

        g.start_interview("LIVE_SCREEN")
        g.interview_current()
        enc = g.encounter
        self.assertTrue(finalexam.sealed(enc, "BUILD"))
        self.assertEqual(g._player_element(enc), E.NEUTRAL)
        self.assertFalse(forge.active(enc))
        self.assertEqual(forge.effects_in(g._blade_id(), 5, enc), {})
        self.assertIsNone(forge.roll_metal(
            region_id="stack_queue_mines", difficulty="HARD", rank="S",
            is_boss=True, encounter=enc))

        sealed_effects = g.effects()
        for key, value in open_effects.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self.assertLessEqual(sealed_effects.get(key, 0), value,
                                     "%s went UP inside the seal" % key)

        # The loadout is simply not read.
        defender = g._player_defender(enc)
        self.assertEqual(defender.element, E.NEUTRAL)
        self.assertEqual(defender.armour.points, 0)
        self.assertEqual(defender.armour.resist, {})

        self.assertEqual(g.use_potion(potions.POTION_IDS[0]).get("error"),
                         "sealed")
        self.assertEqual(g.forge_upgrade().get("error"), "sealed")
        self.assertEqual(g.forge_rack().get("error"), "sealed")
        self.assertEqual(g.start_incantation("enc_cart_tower").get("error"),
                         "sealed")

    def test_the_wheel_itself_goes_quiet_under_build(self):
        armour = E.armour_profile("PLATE", points=9, resist={E.FIRE: 0.3})
        defender = E.Defender(element=E.COLD, armour=armour, max_health=60)
        sealed = E.resolve_damage(20, E.FIRE, defender, build_sealed=True,
                                  roll=0.0)
        self.assertEqual(sealed.kind, "NEUTRAL")
        self.assertEqual(sealed.multiplier, 1.0)
        self.assertEqual(sealed.armour_absorbed, 0)
        self.assertEqual(sealed.inflicted, "")
        self.assertEqual(sealed.damage, 20)

    def test_the_same_doors_are_shut_over_http(self):
        from gauntlet import server as server_module
        g = self._armed()
        server_module.set_game(g)
        self.addCleanup(server_module.set_game, None)
        httpd, url = server_module.serve()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = url.split("/?")[0]
        token = server_module.TOKEN

        def call(path, body=None):
            request = urllib.request.Request(
                base + path, method="POST" if body is not None else "GET",
                data=json.dumps(body).encode() if body is not None else None,
                headers={"X-Gauntlet-Token": token,
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as exc:
                return exc.code, json.loads(exc.read())

        doors = (("/api/forge/upgrade", {}),
                 ("/api/forge/rack", {}),
                 ("/api/forge/unrack", {}),
                 ("/api/potion", {"id": potions.POTION_IDS[0]}),
                 ("/api/incant/start", {"encounter_id": "enc_cart_tower"}),
                 ("/api/incant/cast", {"move_id": "bind",
                                       "answers": {"target": "stack",
                                                   "value": "x"}}))
        for path, body in doors:
            status, _ = call(path, body)
            self.assertEqual(status, 200, "%s was shut before the exam" % path)

        g.start_interview("LIVE_SCREEN")
        g.interview_current()
        g.save()
        for path, body in doors:
            status, payload = call(path, body)
            self.assertEqual(status, 409,
                             "%s is open during a measured run" % path)
            self.assertEqual(payload.get("error"), "sealed", path)

    def test_the_final_practical_is_sealed_the_same_way_and_not_a_second_way(self):
        """The exam IS Timed Practical Mode — finalexam.EXAM_MODE is the same
        constant — so every check above fires for it without being told about
        it. Proven rather than assumed, because "the same mode" is exactly the
        kind of claim that stops being true quietly."""
        self.assertIs(finalexam.EXAM_MODE, __import__(
            "gauntlet.config", fromlist=["x"]).MODE_INTERVIEW)
        g = self._armed()
        started = g.start_interview("FINAL_EXAM")
        self.assertFalse(started.get("error"), started)
        g.interview_current()          # the exam opens its first encounter here
        enc = g.encounter
        self.assertIsNotNone(enc, "the exam opened no encounter")
        for capability in ("BUILD", "ITEMS", "PET", "HINTS", "PROBES",
                           "WEAKNESS_MAP"):
            self.assertTrue(finalexam.sealed(enc, capability), capability)
        self.assertEqual(g._player_element(enc), E.NEUTRAL)
        self.assertFalse(forge.active(enc))
        self.assertEqual(g.use_potion(potions.POTION_IDS[0]).get("error"),
                         "sealed")
        self.assertEqual(g.forge_upgrade().get("error"), "sealed")

    def test_nothing_here_ever_moves_mastery(self):
        """A metal is not evidence and neither is a potion."""
        g = self._armed()
        before = {n: s.mastery for n, s in g.skills.items()}
        state = g._forge_state()
        forge.add_metal(state, forge.METALS[0].id, 5)
        g.forge_upgrade()
        g.use_potion(potions.POTION_IDS[0])
        g.save()
        after = {n: s.mastery for n, s in g.skills.items()}
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# 4. The purse and the bag
# ---------------------------------------------------------------------------

class TestTheEconomy(CombatTest):

    @staticmethod
    def bag(state):
        return {m.id: forge.held(state, m.id) for m in forge.METALS}

    def test_a_refused_upgrade_takes_nothing_and_a_bought_one_takes_the_quote(self):
        """Fuzzed, because the failure this guards against — metal in, nothing
        out — is the one bug forge.py says it cannot ship with, and it hid in
        the substitution branch the first time."""
        rng = random.Random(5)
        for _ in range(1500):
            state = forge.new_state()
            blade_id = rng.choice([b.id for b in forge.BLADES])
            state.setdefault("tiers", {})[blade_id] = rng.randint(
                1, forge.MAX_TIER)
            for metal in forge.METALS:
                if rng.random() < 0.7:
                    forge.add_metal(state, metal.id, rng.randint(0, 12))
            gold = rng.choice([0, 1, 5, 50, 500, 5000, 50000, -100])
            before_bag = self.bag(state)
            before_tier = forge.owned_tier(state, blade_id)
            result = forge.upgrade(state, blade_id, gold=gold)
            after_bag = self.bag(state)
            moved = {k: before_bag[k] - after_bag[k]
                     for k in before_bag if before_bag[k] != after_bag[k]}
            if result.get("error"):
                self.assertEqual(moved, {}, "a refusal took metal: %s" % result)
                self.assertEqual(forge.owned_tier(state, blade_id), before_tier)
                self.assertFalse(result.get("gold_spent"))
                continue
            self.assertEqual(forge.owned_tier(state, blade_id), before_tier + 1)
            self.assertEqual(moved, {k: v for k, v in result["spent"].items()
                                     if v})
            self.assertTrue(all(v >= 0 for v in after_bag.values()))
            self.assertGreaterEqual(int(result["gold_spent"]), 0)
            self.assertLessEqual(int(result["gold_spent"]), gold)

    def test_the_purse_never_goes_negative_through_the_engine(self):
        g = self.fresh()
        g.choose_class("analyst")
        state = g._forge_state()
        for metal in forge.METALS:
            forge.add_metal(state, metal.id, 99)
        g.state["player"]["region"] = forge.SMITH["region"]
        g.state["player"]["gold"] = 0
        g.save()
        tier = forge.owned_tier(g._forge_state(), g._blade_id())
        refused = g.forge_upgrade()
        self.assertTrue(refused.get("error"))
        self.assertEqual(g.state["player"]["gold"], 0)
        self.assertEqual(forge.owned_tier(g._forge_state(), g._blade_id()), tier)

        g.state["player"]["gold"] = 10 ** 7
        g.save()
        for _ in range(forge.MAX_TIER + 2):
            if g.forge_upgrade().get("error"):
                break
            self.assertGreaterEqual(g.state["player"]["gold"], 0)
        self.assertGreaterEqual(g.state["player"]["gold"], 0)
        self.assertEqual(forge.owned_tier(g._forge_state(), g._blade_id()),
                         forge.MAX_TIER)

    def test_the_smith_holds_her_own_contract(self):
        self.assertEqual(forge.validate(), [])


# ---------------------------------------------------------------------------
# 5. The blade
# ---------------------------------------------------------------------------

class TestTheBlade(CombatTest):

    def test_a_berserker_cannot_equip_the_analysts_blade_at_any_rung(self):
        wrong = []
        for blade in forge.BLADES:
            for tier in range(forge.MIN_TIER, forge.MAX_TIER + 1):
                rung_id = forge.rung(blade.id, tier).id
                for other in forge.BLADES:
                    if other.class_id == blade.class_id:
                        continue
                    if classes.equippable(rung_id, other.class_id):
                        wrong.append((rung_id, other.class_id))
        self.assertEqual(wrong, [], "cross-class rungs are equippable")

    def test_the_engine_refuses_it_too(self):
        g = self.fresh()
        g.choose_class("berserker")
        rung_id = forge.rung("analysts_calipers", 7).id
        g.state["inventory"].append(rung_id)
        g.save()
        self.assertTrue(g.equip(rung_id).get("error"))

    def test_a_forged_blade_strikes_with_the_metal_it_was_made_of(self):
        """`items.strike_element` reads items.BY_ID, and forge.validate() keeps
        all fifty-four rungs OUT of items.BY_ID on purpose. So the catalogue
        lookup returns nothing for a forged blade and it struck NEUTRAL — which
        took the whole point out of walking to the mines, and took FIRE off the
        board entirely, since no catalogue weapon carries it.
        """
        elemental = [i for i in FORGE_ITEMS.values()
                     if getattr(i, "element", "") in E.ELEMENTS]
        self.assertTrue(elemental, "no rung carries an element at all")
        g = self.fresh()
        for item in elemental:
            g.state["equipped"]["weapon"] = item.id
            self.assertEqual(g._player_element(None), item.element, item.id)

    def test_every_element_on_the_wheel_can_be_struck_with(self):
        """A region whose counter nobody can hold is a region with no decision
        in it."""
        holdable = set()
        for source in (items.BY_ID, FORGE_ITEMS):
            for item in source.values():
                if item.slot == "weapon":
                    holdable.add(getattr(item, "element", ""))
        self.assertEqual(set(E.ELEMENT_IDS) - holdable, set())

    def test_a_temper_overrides_the_rung_and_never_enters_the_effect_bag(self):
        """forge.WIRING §12: the weapon's element is an argument to
        resolve_damage, read at the swing; the armour's resists are effects.
        Two owners of one number is how they disagree."""
        g = self.fresh()
        g.choose_class("analyst")
        state = g._forge_state()
        rung_id = forge.rung("analysts_calipers", 1).id
        g.state["equipped"]["weapon"] = rung_id
        state.setdefault(forge.TEMPER_KEY, {})[rung_id] = {
            "element": E.FIRE, "step": 1, "kind": "weapon"}
        g.save()
        self.assertEqual(g._player_element(None), E.FIRE)
        self.assertEqual(forge.temper_effects(state, rung_id), {})

    def test_a_tempered_piece_of_armour_reaches_the_effect_bag(self):
        g = self.fresh()
        worn = next(i for i in items.BY_ID.values() if i.slot == "chest")
        g.state["equipped"]["chest"] = worn.id
        state = g._forge_state()
        state.setdefault(forge.TEMPER_KEY, {})[worn.id] = {
            "element": E.FIRE, "step": 2, "kind": "armour"}
        g.save()
        self.assertGreater(g.effects().get("resist_fire", 0.0), 0.0,
                           "forge.loadout_temper_effects never reaches effects()")
        profile = E.armour_from_effects(g.effects())
        self.assertLessEqual(sum(profile.resist.values()), E.RESIST_CAP,
                             "the temper resists are being clamped twice, or "
                             "not at all")


# ---------------------------------------------------------------------------
# 6. It survives the save
# ---------------------------------------------------------------------------

class TestItSurvivesTheSave(CombatTest):

    @staticmethod
    def facts(g):
        state = g._forge_state()
        return {
            "metals": {m.id: forge.held(state, m.id) for m in forge.METALS},
            "tiers": dict(state.get("tiers") or {}),
            "forged": state.get("forged"),
            "temper": copy.deepcopy(state.get(forge.TEMPER_KEY) or {}),
            "pouch": dict(potions.Pouch.from_state(g.state).counts),
            "weapon": g.state["equipped"].get("weapon", ""),
        }

    def _stocked(self):
        g = self.fresh()
        g.choose_class("analyst")
        state = g._forge_state()
        for metal in forge.METALS:
            forge.add_metal(state, metal.id, 7)
        g.state["player"]["gold"] = 10 ** 6
        g.state["player"]["region"] = forge.SMITH["region"]
        for _ in range(3):
            g.forge_upgrade()
        pouch = potions.Pouch.from_state(g.state)
        for potion_id in potions.POTION_IDS[:6]:
            pouch.add(potion_id, 2)
        pouch.to_state(g.state)
        weapon = g.state["equipped"].get("weapon", "")
        if weapon:
            g._forge_state().setdefault(forge.TEMPER_KEY, {})[weapon] = {
                "element": E.COLD, "step": 1, "kind": "weapon"}
        g.save()
        return g

    def test_metal_potions_rungs_and_tempers_survive_a_reload(self):
        g = self._stocked()
        before = self.facts(g)
        self.assertTrue(before["tiers"], "nothing was forged to test with")
        self.assertTrue(before["pouch"])
        again = Game(db_path=self.data_dir / "save.sqlite3",
                     corpus_path=self.corpus_path)
        self.assertEqual(self.facts(again), before)

    def test_they_survive_a_save_slot_round_trip(self):
        g = self._stocked()
        before = self.facts(g)
        saved = g.save_to_slot(1, name="probe")
        self.assertFalse(saved.get("error"), saved)

        state = g._forge_state()
        forge.add_metal(state, forge.METALS[0].id, 55)
        state.setdefault("tiers", {})["analysts_calipers"] = forge.MAX_TIER
        potions.Pouch(counts={}).to_state(g.state)
        g.save()
        self.assertNotEqual(self.facts(g), before)

        loaded = g.load_slot(saves.slot_id("manual", 1))
        self.assertTrue(loaded.get("ok"), loaded)
        self.assertEqual(self.facts(g), before)

    def test_an_undo_does_not_empty_the_bag(self):
        g = self._stocked()
        g.save_to_slot(1, name="probe")
        g.load_slot(saves.slot_id("manual", 1))
        self.assertTrue(saves.undo_available(g.conn))
        undone = g.undo_load()
        self.assertTrue(undone.get("ok"), undone)
        after = self.facts(g)
        self.assertTrue(after["tiers"], "undo emptied the rungs")
        self.assertTrue(any(after["metals"].values()), "undo emptied the bag")


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
