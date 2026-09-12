"""The companion IS the hint system, so these are the rules that hold it up.

Six claims, each of them load-bearing and each of them proved by driving a real
`Game` rather than by reading `gauntlet/pets.py` back to itself:

  1. THE TIER GATE. A companion never helps above its own depth, by any path —
     the line it volunteers, the middle of the hint tree it reads out, and the
     passives that are an opinion about the problem rather than a bigger bag.
  2. THE SEAL. `finalexam.sealed(encounter, "PET")` is the one authority, and
     from the rung that takes the companion onward no animal of any tier gives
     anything: not the hidden one, not the legendary return, and not quietly
     through the effect fold.
  3. ONE AT A TIME. Reversibly, and with nothing lost by choosing.
  4. THE BARROW. The fall happens once, survives a reload, and a save that beat
     that boss before the fall existed does not have the animal it is actually
     walking with taken away.
  5. NO DEAD ENDS. The sharpest edge in the design. Wrong companion, no
     companion, dead companion — the roads out are the SAME roads, which is the
     only way to prove that the ladder is not what stands between a stuck player
     and getting unstuck.
  6. NO ANSWER TELLS, across the whole roster, at a bar at least as strict as
     the one the rest of the suite holds the gear and the class trees to.

Where a claim is about "every companion" it is written as a loop over
`pets.PETS` rather than a spot check, because the roster is authored data and
the next animal added is exactly the one that would have slipped through.
"""
from __future__ import annotations

from base import GameTest

from gauntlet import config, curriculum, dungeons, finalexam, items, pets
from gauntlet import db as dbmod


# Every measured signal a trigger reads, all true at once, so that the answer to
# "did it speak" is about the TIER and never about whether the player happened
# to be stuck in the one way this animal watches for. Key names are `_fires()`'s.
LOUD = {
    "submitted": True, "seconds_elapsed": 1200.0,
    "seconds_since_progress": 900.0, "failed_attempts": 9,
    "last_categories": ["OFF_BY_ONE"] * 6,
    "category_counts": {c: 9 for c in
                        ("PATTERN_NOT_RECOGNIZED", "SYNTAX", "OFF_BY_ONE",
                         "EMPTY_INPUT", "WRONG_STRUCTURE", "TIMEOUT",
                         "PYTHON_RECALL", "WRONG_ALGORITHM")},
    "syntax_failures": 9, "timeout_failures": 9, "hidden_failures": 9,
    "perf_failed": True, "weakness": "empty_input",
}

# The rung of the boss ladder that takes the companion away. Read from the
# ladder rather than written down, so a reordering of world.BOSSES moves this
# test with it instead of quietly aiming it at the wrong fight.
PET_RUNG = next(seal.rung for seal in finalexam.BOSS_LADDER
                if "PET" in seal.takes)


def _stock(g, bond=400):
    """Give the save the whole roster at STORIED bond, so that every assertion
    below is about the ladder and never about a passive that had not unlocked."""
    state = g.state["pets"]
    state["found"] = [pet.id for pet in pets.PETS]
    state["bond"] = {pet.id: bond for pet in pets.PETS}
    state["fallen"] = []
    state["active"] = []
    return state


def _deepest(g, difficulty, *, rungs=2):
    """A real problem of this depth with a hint tree worth gating."""
    return next(p for p in g.teachable
                if p.difficulty == difficulty and len(p.hint_tree) >= rungs
                and p.canonical_solution)


# --------------------------------------------------------------------------
class TestTheTierGate(GameTest):
    """A companion helps to its depth and not one tier past it, by any path."""

    def test_no_companion_speaks_about_anything_deeper_than_its_own_tier(self):
        """The module's own contract, exercised over the whole ladder. A
        companion above its depth must not return a thinner hint — it must
        return a refusal, because help that degrades gracefully teaches the
        player that the tier does not matter."""
        for pet in pets.PETS:
            depth_of = curriculum.tier_index(pets.TIER_BY_KEY[pet.tier].depth)
            for difficulty in curriculum.TIERS:
                event = pets.intervention(
                    pet.id, bond=400, mode=config.MODE_ADVENTURE,
                    signals=dict(LOUD), difficulty=difficulty)
                self.assertIsNotNone(event, f"{pet.id} said nothing at all")
                above = curriculum.tier_index(difficulty) > depth_of
                self.assertEqual(
                    bool(event["refused"]), above,
                    f"{pet.id} ({pet.tier}) on {difficulty}")
                if above:
                    # A refusal is not a cheap hint. It charges nothing, clamps
                    # nothing, and carries the map out instead.
                    self.assertEqual(event["hint_weight"], 0)
                    self.assertEqual(event["rank_ceiling"], "")
                    self.assertTrue(event["route"]["roads"])

    def test_the_middle_of_the_hint_tree_is_gated_at_the_same_depth(self):
        """The companion reads the tree out. An animal that cannot read this
        room cannot read the rungs in it either — and the refusal must say
        `above_tier`, never `sealed`, because those are two different sentences
        with two different answers."""
        g = self.game()
        _stock(g)
        problem = _deepest(g, "HARD")
        for pet in pets.PETS:
            g.state["pets"]["active"] = [pet.id]
            g.state["player"]["mana"] = 999
            g.start_encounter(problem.id)
            got = g.use_hint(2)
            if pets.covers(pet.id, problem.difficulty):
                self.assertNotIn("error", got, f"{pet.id} reads {problem.difficulty}")
            else:
                self.assertEqual(got["error"], "above_tier", pet.id)
                self.assertNotEqual(got["error"], "sealed")
                self.assertEqual(got["helps_through"],
                                 pets.TIER_BY_KEY[pet.tier].depth)

    def test_a_passive_that_reads_the_room_is_gated_like_the_spoken_line(self):
        """The leak this test exists to keep closed: SICKLE covers MEDIUM and
        carries probe charges, so without the gate an ADEPT animal handed the
        player extra questions to ask about a HARD problem it had just refused
        to discuss. A tier gate that holds on the sentence and leaks through the
        probe charge is not a gate."""
        g = self.game()
        _stock(g)
        shallow, deep = _deepest(g, "MEDIUM"), _deepest(g, "HARD")

        g.state["pets"]["active"] = []
        g.start_encounter(deep.id)
        base = g.probes_remaining()

        g.state["pets"]["active"] = ["velociraptor"]
        g.start_encounter(shallow.id)
        self.assertGreater(g.probes_remaining(), base,
                           "an ADEPT animal pays out at its own depth")
        g.start_encounter(deep.id)
        self.assertEqual(g.probes_remaining(), base,
                         "and pays out nothing above it")
        for key in ("probe_reveal_value", "reveal_category"):
            self.assertFalse(g.effects().get(key), key)

    def test_bond_never_buys_depth_and_economy_passives_never_move(self):
        """Bond buys the animal speaking earlier and more often. It does not buy
        a tier, and the passives it does buy outright must not evaporate when the
        room gets harder — a stamina ceiling that moved mid-run would take the
        bar off a player for a reason they could not see."""
        for pet in pets.PETS:
            for difficulty in curriculum.TIERS:
                self.assertEqual(pets.covers(pet.id, difficulty),
                                 pets.covers_tier(pet.tier, difficulty),
                                 f"{pet.id} at bond 400 on {difficulty}")
        g = self.game()
        _stock(g)
        g.state["pets"]["active"] = ["llama"]      # BEGINNER, +6 stamina_max
        g.start_encounter(_deepest(g, "EASY").id)
        shallow = g.effects().get("stamina_max", 0)
        g.start_encounter(_deepest(g, "HARD").id)
        self.assertEqual(g.effects().get("stamina_max", 0), shallow,
                         "a cap is economy and is not gated by depth")

    def test_the_roster_carries_no_ungated_reader_of_the_room(self):
        """Stated as data so the next animal added is checked by import rather
        than by review."""
        report = pets.self_check()
        self.assertEqual(report["ungated_room_readers"], [])
        self.assertTrue(report["tier_gate_covers_passives"])
        for key in pets.DEPTH_GATED_EFFECTS:
            self.assertIn(key, items.EFFECT_LABELS, key)


# --------------------------------------------------------------------------
class TestTheSeal(GameTest):
    """`finalexam.sealed(enc, "PET")` is the one isolation path, and there is no
    second one."""

    def test_no_companion_of_any_tier_speaks_in_a_measured_run(self):
        for pet in pets.PETS:
            self.assertIsNone(pets.intervention(
                pet.id, bond=400, mode=config.MODE_INTERVIEW,
                signals=dict(LOUD), difficulty="EASY"))
            self.assertIsNone(pets.intervention(
                pet.id, bond=400, mode=config.MODE_ADVENTURE,
                signals=dict(LOUD), difficulty="EASY", sealed=True))
            self.assertEqual(
                pets.party_effects([pet.id], {pet.id: 400},
                                   mode=config.MODE_INTERVIEW), {})

    def test_the_hidden_one_and_the_legend_are_refused_like_everything_else(self):
        """These two read every depth there is, which is exactly why they are
        the two worth naming. Covering BOSS is not a licence to be in the room."""
        g = self.game()
        _stock(g)
        problem = _deepest(g, "MEDIUM")
        for pet_id in (pets.HIDDEN_ID, pets.RETURN_ID):
            self.assertTrue(pets.covers(pet_id, "BOSS"), pet_id)
            g.state["pets"]["active"] = [pet_id]
            g.start_encounter(problem.id, mode=config.MODE_INTERVIEW)
            self.assertTrue(finalexam.sealed(g.encounter, "PET"))
            self.assertIsNone(g.pet_intervention(dict(LOUD)), pet_id)
            self.assertEqual(g.dismiss_pet()["error"], "sealed", pet_id)
            self.assertEqual(g.set_active_pets([pet_id])["error"], "sealed")
            payload = g._encounter_payload(problem, g.encounter)
            self.assertEqual(payload["companions"], [], pet_id)

    def test_a_crutch_the_ladder_has_taken_is_taken_quietly_as_well(self):
        """The regression this test was written for: the seal reached the spoken
        line and not the effect fold, so from the rung that takes the companion
        onward — every remaining boss, and the final trial — the animal went on
        quietly paying out probe charges and rank grace to a player who had been
        told it was outside."""
        g = self.game()
        _stock(g)
        problem = _deepest(g, "MEDIUM")
        for seal in finalexam.BOSS_LADDER:
            for pet_id in ("velociraptor", pets.RETURN_ID, pets.HIDDEN_ID):
                g.state["pets"]["active"] = [pet_id]
                g.start_encounter(problem.id, mode=config.MODE_ADVENTURE,
                                  boss_id=seal.boss_id, reason="BOSS")
                with_pet = g.effects()
                g.state["pets"]["active"] = []
                without = g.effects()
                contributed = {k: v for k, v in with_pet.items()
                               if without.get(k, 0) != v}
                if seal.rung >= PET_RUNG:
                    self.assertEqual(contributed, {},
                                     f"{pet_id} at rung {seal.rung}")
                    self.assertIsNone(g.pet_intervention(dict(LOUD)))

    def test_a_companion_cannot_read_out_a_crutch_an_earlier_rung_removed(self):
        """The seal takes the tactical read two rungs before it takes the
        companion. For those two fights the enemy's weaknesses are stripped from
        the payload and the tactical brief is gone — and the hidden animal,
        which becomes whichever companion the room called for, would put on the
        raptor and name the edge class straight back out. The redacted view a
        companion reads has to be redacted by the same seal that redacts the
        payload, or the ladder has a side door with fur on it."""
        g = self.game()
        _stock(g)
        problem = _deepest(g, "MEDIUM")
        # No graded failure yet, so the mirror falls past `category` and reaches
        # for the weakness — which is the case that leaked.
        quiet = dict(LOUD, failed_attempts=0, last_categories=[],
                     category_counts={}, submitted=False, weakness="")
        checked = 0
        for seal in finalexam.BOSS_LADDER:
            if seal.blocks("PET"):
                continue
            for pet_id in (pets.HIDDEN_ID, pets.RETURN_ID, "velociraptor", "crow"):
                g.state["pets"]["active"] = [pet_id]
                g.start_encounter(problem.id, mode=config.MODE_ADVENTURE,
                                  boss_id=seal.boss_id, reason="BOSS")
                context = g._pet_context(problem, dict(quiet))
                if seal.blocks("WEAKNESS_MAP"):
                    self.assertEqual(context["weakness"], "",
                                     f"{pet_id} at rung {seal.rung}")
                    checked += 1
                if seal.blocks("PATTERN"):
                    self.assertEqual(context["pattern"], "")
                event = g.pet_intervention(dict(quiet))
                if not event or event.get("refused"):
                    continue
                if seal.blocks("WEAKNESS_MAP"):
                    self.assertNotEqual(
                        event.get("mirrored", ""), "velociraptor",
                        "the mirror put on the animal whose read was sealed")
                    self.assertNotIn(
                        event["body"],
                        list(pets.BY_ID["velociraptor"].hints.values()),
                        "a sealed edge class was read out anyway")
        self.assertGreater(checked, 0,
                           "no rung takes the tactical read before the companion")

    def test_the_module_never_forms_a_second_opinion_about_the_seal(self):
        """`available_in` takes the verdict as an argument. It is allowed to
        refuse MORE than finalexam refuses — two regions promise that nothing
        helps you there — and never less."""
        self.assertFalse(pets.available_in(config.MODE_ADVENTURE,
                                           "python_village", sealed=True))
        for region in pets.SILENCED_REGIONS:
            self.assertFalse(pets.available_in(config.MODE_ADVENTURE, region))
        self.assertTrue(pets.available_in(config.MODE_ADVENTURE,
                                          "python_village", sealed=False))


# --------------------------------------------------------------------------
class TestOneAtATime(GameTest):
    """The decision this whole design exists to create: which animal you walk in
    with. It is only a decision because you cannot bring two, and it is only
    survivable because it can be taken back."""

    def test_the_field_never_holds_more_than_one(self):
        g = self.game()
        _stock(g)
        self.assertEqual(pets.ACTIVE_LIMIT, 1)
        chosen = g.set_active_pets([p.id for p in pets.PETS])["active"]
        self.assertEqual(len(chosen), 1)
        self.assertEqual(len(g.state["pets"]["active"]), 1)
        self.assertEqual(g.pet_catalogue()["limit"], 1)
        self.assertEqual(
            len([row for row in g.pet_catalogue()["pets"] if row["active"]]), 1)

    def test_an_old_save_carrying_two_is_brought_down_to_one(self):
        """ACTIVE_LIMIT used to be two. A save that still lists two would read as
        "one of one" on the screen while quietly folding in both animals'
        passives."""
        g = self.game()
        g.state["pets"] = {"found": ["python", "llama"],
                           "active": ["python", "llama"],
                           "bond": {"python": 400, "llama": 400}, "met_at": {},
                           "fallen": [], "dismissed_at": {}}
        dbmod.save_state(g.conn, g.state)
        reopened = self.game()
        self.assertEqual(reopened.state["pets"]["active"], ["python"])
        self.assertIn("llama", reopened.state["pets"]["found"])
        self.assertEqual(reopened.state["pets"]["bond"]["llama"], 400)

    def test_choosing_another_gives_the_first_one_back_whenever_you_want_it(self):
        """Dismissal is the only friction here and it is reversible on purpose.
        A permanent mistake made at level three is a reason to stop playing."""
        g = self.game()
        _stock(g)
        g.set_active_pets(["python"])
        out = g.recall_pet("llama")
        self.assertTrue(out["active"])
        self.assertEqual(out["stepped_down"], "python")
        self.assertEqual(g.state["pets"]["active"], ["llama"])
        self.assertIn("python", g.state["pets"]["found"])
        self.assertEqual(g.state["pets"]["bond"]["python"], 400)
        self.assertTrue(g.dismiss_pet()["reversible"])
        self.assertEqual(g.state["pets"]["active"], [])
        self.assertTrue(g.recall_pet("python")["active"])

    def test_a_new_companion_never_benches_the_one_you_chose(self):
        """Finding something must not overrule a decision the game has spent an
        hour teaching the player to make."""
        g = self.game()
        _stock(g)
        g.set_active_pets(["jaguar"])
        state = g.state["pets"]
        state["found"].remove("crow")
        self.assertTrue(pets.grant(state, "crow"))
        self.assertEqual(state["active"], ["jaguar"])


# --------------------------------------------------------------------------
class TestTheBarrow(GameTest):
    """It dies once. That is the whole of the contract, and every part of it is
    a thing a reload can get wrong."""

    def _barrow(self):
        return dungeons.DUNGEON_BY_ID[pets.FALLS_AT_DUNGEON]

    def test_a_fresh_save_walks_in_with_the_starter_and_it_helps_at_its_depth(self):
        g = self.game()
        self.assertEqual(pets.active_id(g.state["pets"]), pets.STARTER_ID)
        self.assertEqual(pets.tier_of(pets.STARTER_ID).key, "TUTORIAL")
        guided = _deepest(g, "GUIDED")
        g.start_encounter(guided.id)
        event = g.pet_intervention(dict(LOUD))
        self.assertTrue(event and not event["refused"], "the starter reads GUIDED")
        self.assertEqual(event["hint_weight"], pets.HINT_WEIGHT)
        self.assertEqual(g.encounter.hints_used, pets.HINT_WEIGHT)

    def test_the_fall_fires_exactly_once_and_survives_the_reload_as_a_death(self):
        g = self.game()
        first = g._companion_falls(self._barrow())
        self.assertTrue(first["fell"])
        self.assertEqual(first["returns_as"], pets.RETURN_ID)
        self.assertIsNone(g._companion_falls(self._barrow()),
                          "the barrow does not close twice")
        self.assertEqual(g.state["pets"]["fallen"], [pets.STARTER_ID])
        self.assertEqual(g.state["pets"]["active"], [])
        # It leaves the field and not the codex, because the return is gated on
        # the save remembering this happened.
        self.assertIn(pets.STARTER_ID, g.state["pets"]["found"])
        self.assertIn("error", g.recall_pet(pets.STARTER_ID))
        g.save()

        reopened = self.game()
        self.assertEqual(reopened.state["pets"]["fallen"], [pets.STARTER_ID])
        self.assertTrue(reopened._pet_evidence()["starter_fallen"])
        self.assertIsNone(reopened._companion_falls(self._barrow()))
        self.assertIn("error", reopened.recall_pet(pets.STARTER_ID))

    def test_a_dead_companion_cannot_be_fielded_and_says_nothing_if_it_is(self):
        """Two locks, because one of them is a UI call and the other is the
        fight. `set_active` will not put it back, and an encounter that somehow
        holds it — a hand-edited save, a client that kept a stale list — gets
        silence rather than a tutorial hint from something in a barrow."""
        g = self.game()
        g._companion_falls(self._barrow())
        g.state["pets"]["bond"][pets.STARTER_ID] = 400
        self.assertEqual(pets.set_active(g.state["pets"], [pets.STARTER_ID]), [])
        self.assertIn("error", g.recall_pet(pets.STARTER_ID))

        g.state["pets"]["active"] = [pets.STARTER_ID]   # only a corrupt save can
        guided = _deepest(g, "GUIDED")
        g.start_encounter(guided.id)
        self.assertIsNone(g.pet_intervention(dict(LOUD)))
        self.assertEqual(g.encounter.hints_used, 0)
        # And the roads out are the ones a player with nothing at all has.
        g.state["player"]["mana"] = 999
        self.assertNotIn("error", g.use_hint(pets.OPEN_RUNG))
        self.assertNotIn("error", g.use_hint(len(guided.hint_tree)))

    def test_an_old_save_keeps_the_animal_it_is_actually_walking_with(self):
        """A save written before the fall existed can have that dungeon already
        cleared. Two things must both be true: the debt is recorded, or the
        legendary return is unreachable forever for everybody who played the
        chapter early; and the scene is a memory rather than an event, and the
        companion in the field is not touched, because that player is not in
        that fight and has not been for weeks."""
        g = self.game()
        g.state["pets"] = {"found": ["python", "jaguar"], "active": ["jaguar"],
                           "bond": {"jaguar": 120}, "met_at": {}}
        g.state["dungeons_cleared"] = [pets.FALLS_AT_DUNGEON]
        dbmod.save_state(g.conn, g.state)

        reopened = self.game()
        state = reopened.state["pets"]
        self.assertEqual(state["active"], ["jaguar"],
                         "the animal they were walking with was taken from them")
        self.assertEqual(state["bond"]["jaguar"], 120)
        self.assertTrue(pets.is_fallen(state, pets.STARTER_ID))
        self.assertTrue(reopened.state["pet_fall"]["retroactive"])
        self.assertTrue(reopened._pet_evidence()["starter_fallen"])

    def test_an_old_save_that_never_reached_that_boss_keeps_its_starter(self):
        g = self.game()
        g.state["pets"] = {"found": ["python"], "active": ["python"],
                           "bond": {}, "met_at": {}}
        g.state["dungeons_cleared"] = []
        dbmod.save_state(g.conn, g.state)
        reopened = self.game()
        self.assertEqual(reopened.state["pets"]["fallen"], [])
        self.assertEqual(reopened.state["pets"]["active"], ["python"])

    def test_the_return_is_the_same_animal_and_cannot_arrive_before_the_loss(self):
        g = self.game()
        returned = pets.BY_ID[pets.RETURN_ID]
        self.assertEqual(returned.species, pets.BY_ID[pets.STARTER_ID].species)
        self.assertEqual(returned.lineage, pets.STARTER_ID)
        self.assertTrue(pets.covers(pets.RETURN_ID, "BOSS"))
        self.assertIn("starter_fallen",
                      [c.get("kind") for c in returned.discovery.needs])
        # Every clause has to be a number this engine records, or the codex
        # draws a bar that can never fill.
        evidence = g._pet_evidence()
        for clause in returned.discovery.needs:
            row = pets._discovery_row(clause, evidence)
            self.assertGreater(row["need"], 0, str(clause))
        self.assertFalse(pets.discovery_progress(pets.RETURN_ID, evidence)["met"])


# --------------------------------------------------------------------------
class TestNoDeadEnds(GameTest):
    """The sharpest edge in this design. If the only unasked help is a companion,
    then a player with the wrong one, none, or a dead one has to still be able to
    get unstuck — and the proof is that the roads out do not change."""

    #: The roads that have never asked who was walking with the player.
    OPEN = ("OPEN_RUNG", "SOLUTION", "COACH")

    def _roads_out(self, g, problem):
        """What is actually open, asked of the engine rather than of the module."""
        g.state["player"]["mana"] = 999
        g.start_encounter(problem.id)
        open_now = []
        if "error" not in g.use_hint(pets.OPEN_RUNG):
            open_now.append("OPEN_RUNG")
        if "error" not in g.use_hint(len(problem.hint_tree)):
            open_now.append("SOLUTION")
        if not finalexam.sealed(g.encounter, "COACH"):
            open_now.append("COACH")
        return open_now, g.hint_route()

    def test_every_companion_no_companion_and_a_dead_one_get_the_same_roads(self):
        g = self.game()
        _stock(g)
        states = [(pet.id, [pet.id]) for pet in pets.PETS]
        states += [("none", []), ("dead", [pets.STARTER_ID])]
        for difficulty in ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD"):
            problem = _deepest(g, difficulty)
            for label, active in states:
                with self.subTest(companion=label, difficulty=difficulty):
                    g.state["pets"]["fallen"] = []
                    g.state["pets"]["active"] = active
                    if label == "dead":
                        pets.fall(g.state["pets"])
                    roads, route = self._roads_out(g, problem)
                    self.assertEqual(tuple(roads), self.OPEN)
                    self.assertTrue(route["roads"])
                    self.assertEqual(sorted(route["petless_roads"]),
                                     sorted(pets.PETLESS_ROADS))
                    # And the refusal is never the last word: it names who could
                    # have read this, where they are, and what the deed is.
                    if not pets.covers(active[0] if active else "", difficulty):
                        self.assertTrue(route["companions"])
                        for row in route["companions"]:
                            self.assertTrue(row["where"] and row["how"])

    def test_three_attempts_opens_the_whole_tree_whoever_you_brought(self):
        """A player who has failed three times is stuck by measurement rather
        than by assertion. Gating the cheap rungs of a tree whose most expensive
        rung is already free would be a rule that only ever made things worse."""
        g = self.game()
        problem = _deepest(g, "HARD", rungs=3)
        g.state["pets"]["active"] = [pets.STARTER_ID]     # TUTORIAL, at HARD
        g.start_encounter(problem.id)
        self.assertEqual(g.use_hint(2)["error"], "above_tier")
        for _ in range(pets.FREE_SOLUTION_AFTER):
            g.start_encounter(problem.id)
            g.submit("def nope(*a, **k):\n    return None\n")
        g.state["player"]["mana"] = 999
        g.start_encounter(problem.id)
        self.assertNotIn("error", g.use_hint(2))
        self.assertNotIn("error", g.use_hint(len(problem.hint_tree)))

    def test_a_lost_boss_is_a_ladder_rather_than_a_wall(self):
        """Mid-boss is the one place the roads DO close, because that is what the
        crutch ladder is — and it closes identically for every companion and for
        none. The road out of a boss room is to lose it: the fight steps back and
        hands over the same algorithm one step simpler, on ground where the first
        rung, the coach and the worked solution are all open again."""
        g = self.game()
        _stock(g)
        for seal in finalexam.BOSS_LADDER:
            ladder = g.boss_ladder(seal.boss_id).get("ladder") or []
            self.assertTrue(ladder, f"{seal.boss_id} has nothing to climb back up")
            for row in ladder[:2]:
                rung = g.by_id[row["id"]]
                if not rung.hint_tree:
                    continue
                g.state["player"]["mana"] = 999
                g.start_encounter(rung.id)
                self.assertNotIn("error", g.use_hint(pets.OPEN_RUNG),
                                 f"{seal.boss_id}: the way back up is closed")

    def test_the_module_and_the_engine_agree_about_what_is_never_gated(self):
        """Two modules, one floor. `pets.PETLESS_ROADS` is the module's claim and
        `use_hint` is where it either holds or does not."""
        g = self.game()
        self.assertEqual(sorted(pets.PETLESS_ROADS),
                         sorted(("OPEN_RUNG", "COACH", "SOLUTION")))
        for road in pets.PETLESS_ROADS:
            self.assertIn(road, pets.ROAD_BY_ID)
        problem = _deepest(g, "HARD")
        g.state["pets"]["active"] = []
        g.state["player"]["mana"] = 999
        g.start_encounter(problem.id)
        # The first rung and the worked solution, with nothing walking alongside.
        opened = g.use_hint(pets.OPEN_RUNG)
        self.assertTrue(opened["read_by"]["open"])
        self.assertTrue(opened["read_by"]["why"])
        self.assertNotIn("error", g.use_hint(len(problem.hint_tree)))

    def test_every_depth_the_corpus_serves_has_a_companion_that_reads_it(self):
        """Not a road out — the tier ladder working. A depth with no animal in
        front of it would be a stretch of the game with no unasked help at all."""
        g = self.game()
        for difficulty in sorted({p.difficulty for p in g.corpus}):
            readers = [p.id for p in pets.PETS if pets.covers(p.id, difficulty)]
            self.assertTrue(readers, difficulty)
            self.assertTrue(pets.tiers_covering(difficulty), difficulty)


# --------------------------------------------------------------------------
class TestNoAnswerTells(GameTest):
    """A pet intervention IS a hint, and a hint that states the answer is a cheat
    with a tail."""

    def test_no_authored_string_in_the_roster_reads_as_an_answer(self):
        report = pets.self_check()
        self.assertEqual(report["lines_reading_as_answers"], [])
        self.assertGreater(report["authored_strings"], 400,
                           "the scan has to be over the whole roster")

    def test_the_rosters_bar_is_at_least_the_bar_the_rest_of_the_suite_uses(self):
        """`tests/test_classes.py` holds the class trees and the artifacts to a
        list of tells. The roster is the place a worked solution would most
        naturally hide, so its own list may be stricter and may not be looser."""
        from test_classes import ANSWER_TELLS
        self.assertEqual(set(ANSWER_TELLS) - set(pets._ANSWER_TELLS), set())
        # An import statement is a line of somebody's file. IDIOM is allowed to
        # name `heapq`; it is not allowed to write the top of the module.
        self.assertIn("import ", pets._ANSWER_TELLS)

    def test_nothing_a_companion_actually_says_in_play_hands_over_code(self):
        """The authored strings are scanned above. This scans what comes OUT —
        the opening, the body, and whichever donor the hidden one turned into."""
        g = self.game()
        _stock(g)
        seen = 0
        for pet in pets.PETS:
            g.state["pets"]["active"] = [pet.id]
            for difficulty in ("GUIDED", "EASY", "MEDIUM", "HARD"):
                if not pets.covers(pet.id, difficulty):
                    continue
                problem = _deepest(g, difficulty)
                g.start_encounter(problem.id)
                event = g.pet_intervention(dict(LOUD))
                if not event or event.get("refused"):
                    continue
                seen += 1
                said = f"{event['opening']} {event['body']}".lower()
                for tell in pets._ANSWER_TELLS:
                    self.assertNotIn(tell, said, f"{pet.id}/{difficulty}: {said!r}")
        self.assertGreater(seen, 20, "the scan barely spoke to anybody")

    def test_a_companion_costs_exactly_what_a_hint_rung_costs(self):
        """The rule that keeps the whole thing honest: an intervention is not
        cheaper for having been unasked. Bond buys the animal more chances to
        speak; it does not buy any of them for free."""
        g = self.game()
        _stock(g, bond=0)
        problem = _deepest(g, "MEDIUM")
        g.state["pets"]["active"] = ["jaguar"]
        g.start_encounter(problem.id)
        before = g.state["stats"]["hints_total"]
        event = g.pet_intervention(dict(LOUD))
        self.assertTrue(event and not event["refused"])
        self.assertEqual(event["hint_weight"], pets.HINT_WEIGHT)
        self.assertEqual(g.encounter.hints_used, pets.HINT_WEIGHT)
        self.assertEqual(g.encounter.rank_ceiling, event["rank_ceiling"])
        self.assertNotEqual(event["rank_ceiling"], "S")
        self.assertEqual(g.state["stats"]["hints_total"], before + 1)
        # WARY is one intervention per encounter, so the second call is silence
        # rather than a second free line.
        self.assertEqual(pets.bond_rank(0).interventions, 1)
        self.assertIsNone(g.pet_intervention(dict(LOUD)))

        # And at the top of the bond ladder, where it may speak three times,
        # every one of those three is billed.
        g.state["pets"]["bond"]["jaguar"] = 400
        allowance = pets.bond_rank(400).interventions
        self.assertGreater(allowance, 1)
        g.start_encounter(problem.id)
        spoke = 0
        while g.pet_intervention(dict(LOUD)):
            spoke += 1
            self.assertEqual(g.encounter.hints_used, spoke * pets.HINT_WEIGHT)
        self.assertEqual(spoke, allowance)
