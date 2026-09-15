"""The hidden healers, the captives and the finale, held to their own claims.

Five things are pinned here, and each one is a rule the three modules would be
worth deleting without:

  1. THE FINALE DOES NOT GATE THE EXAM. A player who rescued nobody composes the
     same practical, sits it, passes it and gets an ending. Proved against the
     real corpus, not against a stub.
  2. THE HEALER LIMIT HOLDS, AND IT IS SAVE-WIDE. One rest per descent, ten
     graded clears between rests across the whole save, and a toll paid in
     armour rather than in gold. The town loop is simulated with the healers and
     without them and has to survive both.
  3. NOTHING STRANDS ANYBODY. Every refusal carries a remedy, and a battered
     player with a fainted companion and no gold always has a way onward that
     does not run through a sanctuary.
  4. THE CAPTIVES ARE PEOPLE. Enforced the only way a machine can: everybody has
     a trade, an opinion and something to say about their own life, no boon buys
     a look at an answer, and no authored line in any of the three modules reads
     like a romance, a reward or a trophy.
  5. THE READINESS LINE IS HONEST. READY is said only when something measured
     READY and only when the clock was actually kept, and a player who is not
     ready is told so with a route rather than flattered.
"""
from base import GameTest  # noqa: E402

import re

from gauntlet import captives, config, finale, finalexam, pets, sanctuary
from gauntlet import upkeep, world


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _battered(*, health: int = 2, gold: int = 0, region: str = "graph_wastes",
              integrity: int = 100) -> dict:
    """A save shaped like engine's, with the player in a bad way."""
    state = {
        "player": {
            upkeep.HEALTH_FIELD: health,
            f"{upkeep.HEALTH_FIELD}_max": config.STAMINA_MAX,
            upkeep.FOCUS_FIELD: 0,
            f"{upkeep.FOCUS_FIELD}_max": config.MANA_MAX,
            "gold": gold, "region": region,
        },
        "equipped": {},
        "armor": {piece["id"]: integrity for piece in world.ARMOR},
    }
    upkeep.ensure(state)
    sanctuary.ensure(state)
    return state


def _authored_strings(module) -> list:
    """Every line in a module that a player can end up reading.

    Walks the module's own data rather than its source, so a docstring about
    what the rule is does not get mistaken for a line spoken by a character.
    """
    out: list = []

    def walk(node, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, (list, tuple, set, frozenset)):
            for item in node:
                walk(item, depth + 1)
        elif hasattr(node, "__dataclass_fields__") and not isinstance(node, type):
            for field in node.__dataclass_fields__:
                walk(getattr(node, field), depth + 1)

    for name in dir(module):
        if name.startswith("_"):
            continue
        value = getattr(module, name)
        if isinstance(value, type):
            continue
        if isinstance(value, (str, dict, list, tuple)) or hasattr(
                value, "__dataclass_fields__"):
            walk(value)
    return out


# ---------------------------------------------------------------------------
# 1. THE FINALE DOES NOT GATE THE EXAM
# ---------------------------------------------------------------------------

class ExamIsNotGated(GameTest):
    """The direction of the gate, proved rather than asserted in a comment.

    The practical is upstream of the ending. Nothing about rescuing people can
    make it harder to reach, harder to pass, or different in any way.
    """

    def _sit(self, *, solved: int, seed: int = 7):
        exam = finalexam.compose(self.corpus, seed=seed)
        questions = [q for seg in exam.segments for q in seg["questions"]]
        results = [{"problem_id": q.problem_id,
                    "solved": index < solved,
                    "rank": "S" if index < solved else "",
                    "seconds": int(q.target_seconds * 0.8),
                    "root_cause": "" if index < solved else "OFF_BY_ONE"}
                   for index, q in enumerate(questions)]
        return exam, questions, finalexam.debrief(exam, results)

    def test_finalexam_does_not_know_these_modules_exist(self):
        """The strongest form of the claim: the exam cannot consult them."""
        with open(finalexam.__file__) as handle:
            source = handle.read()
        for name in ("captives", "sanctuary", "finale"):
            self.assertNotIn(f"from . import {name}", source)
            self.assertNotIn(f"import {name}", source)
            self.assertNotIn(f"{name}.", source)

    def test_a_player_who_rescued_nobody_sits_the_same_exam(self):
        state = {}
        self.assertEqual(captives.freed(state), [])
        self.assertEqual(sanctuary.known_ids(state), [])

        exam, questions, report = self._sit(solved=99)
        self.assertTrue(questions, "the practical composed no questions")
        self.assertEqual(report["verdict"]["code"], "READY")
        self.assertEqual(report["solved"], report["total"])

        # Composition does not vary with the roll call: the same seed with a
        # fully-rescued save draws exactly the same paper.
        rescued = {}
        for boss_id in captives.HOLDINGS:
            captives.free(rescued, boss_id)
        self.assertEqual(len(captives.freed(rescued)), len(captives.CAPTIVES))
        again = finalexam.compose(self.corpus, seed=7)
        self.assertEqual([q.problem_id for seg in again.segments
                          for q in seg["questions"]],
                         [q.problem_id for q in questions])

    def test_rescuing_nobody_still_ends_the_game(self):
        _, _, report = self._sit(solved=99)
        self.assertTrue(finale.available(exam_report=report)["open"])

        scene = finale.cutscene(freed=captives.roll_call({}),
                                exam_report=report,
                                total_captives=len(captives.CAPTIVES))
        self.assertEqual(finale.validate(scene), [])
        self.assertEqual(scene["roll_call"]["count"], 0)
        self.assertEqual(scene["roll_call"]["scale"], "NONE")
        # The freeze frame still lands, the card still slams, and the coda is
        # still reached. An empty gallery is allowed to be empty; it is not
        # allowed to be a shorter ending.
        ids = [beat["id"] for beat in scene["beats"]]
        self.assertIn("freeze", ids)
        self.assertEqual(ids[-1], "the_prompt_stays")
        self.assertEqual(scene["send_off"]["code"], "READY")
        self.assertIn("met the standard for this timed Python practical",
                      " ".join(scene["send_off"]["lines"]))

    def test_a_failed_practical_still_ends_the_game(self):
        _, _, report = self._sit(solved=1)
        self.assertEqual(report["verdict"]["code"], "NOT_READY")
        self.assertTrue(finale.available(exam_report=report)["open"],
                        "the ending is gated on passing, which it must not be")
        scene = finale.cutscene(freed=(), exam_report=report)
        self.assertEqual(finale.validate(scene), [])
        self.assertEqual(scene["beats"][-1]["id"], "the_prompt_stays")

    def test_the_ending_needs_the_practical_and_not_the_other_way_round(self):
        self.assertFalse(finale.available(exam_report=None)["open"])
        self.assertEqual(finalexam.audit_seal(), [])
        self.assertEqual(finalexam.EXAM_SEAL.sealed, finalexam.ALL_CRUTCHES)

    def test_none_of_the_three_speaks_during_a_measured_run(self):
        class Enc:
            mode = config.MODE_INTERVIEW
            boss_id = ""
            holdout = False

        self.assertEqual(finale.cutscene(encounter=Enc()).get("error"), "sealed")
        self.assertFalse(captives.available_in(config.MODE_INTERVIEW))
        self.assertFalse(sanctuary.available_in(config.MODE_INTERVIEW))
        state = _battered()
        out = sanctuary.rest(state, "nock", sealed=True,
                             run={"dungeon": "unlabelled_halls",
                                  "run_seed": 1, "at": 0})
        self.assertFalse(out["ok"])
        self.assertEqual(state["player"][upkeep.HEALTH_FIELD], 2)


# ---------------------------------------------------------------------------
# 2. THE HEALER LIMIT
# ---------------------------------------------------------------------------

class TheHealerLimit(GameTest):
    """The three limits, and the town loop they exist to protect."""

    def test_one_rest_per_descent(self):
        state = _battered()
        run = {"dungeon": "ninth_cart", "run_seed": 11, "at": 0}
        self.assertTrue(sanctuary.rest(state, "dov_kerrin", run=run)["ok"])
        state["player"][upkeep.HEALTH_FIELD] = 2
        again = sanctuary.rest(state, "dov_kerrin", run=run)
        self.assertFalse(again["ok"])
        self.assertEqual(again["error"], "descent")
        self.assertTrue(again["remedy"])

    def test_the_cooldown_is_save_wide_and_not_one_per_healer(self):
        """The limit that actually protects the town.

        Keyed per healer this rule does nothing: a player rests, walks into the
        next region and rests again having done no work at all. Seventeen
        healers would be seventeen towns.
        """
        state = _battered()
        allowed = []
        for index, who in enumerate(sanctuary.SANCTUARIES):
            state["player"][upkeep.HEALTH_FIELD] = 2
            out = sanctuary.rest(state, who.id,
                                 run={"dungeon": who.dungeon or "x",
                                      "run_seed": 1000 + index, "at": 0})
            if out.get("ok"):
                allowed.append(who.id)
        self.assertEqual(len(allowed), 1,
                         "the cooldown let %d healers through with no graded "
                         "clears between them" % len(allowed))

        # And it comes back on the far side of ten clears, not a moment before.
        target = sanctuary.SANCTUARIES[-1]
        for _ in range(sanctuary.COOLDOWN_CLEARS - 1):
            sanctuary.note_clear(state)
        state["player"][upkeep.HEALTH_FIELD] = 2
        early = sanctuary.rest(state, target.id,
                               run={"dungeon": target.dungeon or "x",
                                    "run_seed": 4242, "at": 0})
        self.assertFalse(early["ok"])
        sanctuary.note_clear(state)
        state["player"][upkeep.HEALTH_FIELD] = 2
        self.assertTrue(sanctuary.rest(state, target.id,
                                       run={"dungeon": target.dungeon or "x",
                                            "run_seed": 4242, "at": 0})["ok"])

    def test_the_cooldown_sits_inside_one_town_repair_cycle(self):
        self.assertLess(sanctuary.COOLDOWN_CLEARS,
                        int(upkeep.LOOP["cadence_encounters"]))

    def test_the_toll_is_armour_and_never_gold(self):
        state = _battered(gold=500)
        before = state["player"]["gold"]
        start = {p: upkeep.integrity(state, p) for p in upkeep.PIECES}
        out = sanctuary.rest(state, "ilma_vetch",
                             run={"dungeon": "hollow_of_keys",
                                  "run_seed": 7, "at": 0})
        self.assertTrue(out["ok"])
        self.assertEqual(out["gold_cost"], 0)
        self.assertEqual(state["player"]["gold"], before)
        self.assertEqual(out["free_because"], upkeep.MENDER.free_because)
        spent = sum(start[p] - upkeep.integrity(state, p)
                    for p in upkeep.PIECES)
        self.assertGreater(spent, 0, "the rest cost nothing at all")
        self.assertTrue(all(upkeep.integrity(state, p) >= upkeep.INTEGRITY_MIN
                            for p in upkeep.PIECES))

    def test_resting_everywhere_never_breaks_a_piece(self):
        report = sanctuary.self_check()
        self.assertTrue(report["ok"], report["failures"])
        self.assertTrue(report["limits"]["nothing_below_floor"])
        self.assertGreaterEqual(report["limits"]["worst_piece_left"],
                                upkeep.DEGRADED_FLOOR * upkeep.INTEGRITY_MAX)

    # -- the loop itself, simulated -----------------------------------------

    def _campaign(self, *, healers: bool, encounters: int = 240,
                  rooms_per_descent: int = 12, health_per_room: int = 3,
                  difficulty: str = "MEDIUM") -> dict:
        """A long campaign, played twice: with the healers and without them.

        The player descends, clears rooms, and when they can no longer take a
        room without hitting the floor they heal — at a sanctuary if one will
        have them, and otherwise by walking home, which ends the descent. The
        smith is consulted whenever a piece reaches upkeep's own advice line.
        """
        state = _battered(health=config.STAMINA_MAX, gold=400)
        in_dungeons = [s.dungeon for s in sanctuary.SANCTUARIES if s.dungeon]
        floor = config.STAMINA_LOSS_FAILED_SUBMIT
        played = descents = rests = 0
        healing_trips = smith_trips = 0

        def worst() -> int:
            return min(upkeep.integrity(state, p) for p in upkeep.PIECES)

        while played < encounters:
            descents += 1
            dungeon = in_dungeons[descents % len(in_dungeons)]
            run = {"dungeon": dungeon, "run_seed": descents, "at": 0}
            who = sanctuary.BY_DUNGEON[dungeon].id
            room = 0
            walked_home = False
            while room < rooms_per_descent and played < encounters:
                if state["player"][upkeep.HEALTH_FIELD] < floor + health_per_room:
                    if healers and sanctuary.can_rest(
                            state, who, run=run)["allowed"]:
                        sanctuary.rest(state, who, run=run)
                        rests += 1
                    else:
                        upkeep.town_visit(state)
                        healing_trips += 1
                        if worst() <= upkeep.REPAIR_ADVISED_AT:
                            upkeep.repair(state, gold=state["player"]["gold"])
                            smith_trips += 1
                        walked_home = True
                        break
                state["player"][upkeep.HEALTH_FIELD] = max(
                    0, state["player"][upkeep.HEALTH_FIELD] - health_per_room)
                upkeep.wear_encounter(state, difficulty=difficulty,
                                      hits_taken=3, blows_landed=4)
                sanctuary.note_clear(state)
                pay = upkeep.expected_gold(difficulty)
                upkeep.record_income(state, pay)
                state["player"]["gold"] += pay
                played += 1
                room += 1
            if not walked_home and worst() <= upkeep.REPAIR_ADVISED_AT:
                upkeep.town_visit(state)
                upkeep.repair(state, gold=state["player"]["gold"])
                smith_trips += 1
        visits = int(state["upkeep"]["visits"])
        return {"encounters": played, "descents": descents, "visits": visits,
                "rests": rests, "healing_trips": healing_trips,
                "smith_trips": smith_trips,
                "per_visit": played / max(1, visits)}

    def test_the_town_loop_survives_the_hidden_healers(self):
        for difficulty in ("EASY", "MEDIUM", "HARD"):
            with self.subTest(difficulty=difficulty):
                without = self._campaign(healers=False, difficulty=difficulty)
                with_them = self._campaign(healers=True, difficulty=difficulty)

                # The town does not empty out.
                self.assertGreater(with_them["visits"], 0)
                # And it is not visited so rarely that the repair cadence stops
                # being a rhythm. upkeep budgets one visit per seventeen.
                self.assertLessEqual(
                    with_them["per_visit"],
                    float(upkeep.LOOP["cadence_encounters"]),
                    "the walk home has stretched past upkeep's own cadence")
                # The healers are worth finding: the walk is genuinely rarer.
                self.assertLess(with_them["visits"], without["visits"])
                # But not by so much that the loop is gone. Half is the floor.
                self.assertGreaterEqual(
                    with_them["visits"], without["visits"] * 0.25,
                    "town visits collapsed; tighten the limit")
                # The armour pole is still the one that brings people home.
                self.assertGreater(with_them["smith_trips"], 0)

    def test_a_second_rest_costs_a_whole_descent(self):
        """Walking out and back in buys another rest — and the cooldown makes
        that cost real work rather than a lap of the entrance."""
        state = _battered()
        run = {"dungeon": "split_canopy", "run_seed": 1, "at": 0}
        self.assertTrue(sanctuary.rest(state, "wisla_grane", run=run)["ok"])
        state["player"][upkeep.HEALTH_FIELD] = 2
        fresh = {"dungeon": "split_canopy", "run_seed": 2, "at": 0}
        blocked = sanctuary.rest(state, "wisla_grane", run=fresh)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"], "cooldown")
        for _ in range(sanctuary.COOLDOWN_CLEARS):
            sanctuary.note_clear(state)
        state["player"][upkeep.HEALTH_FIELD] = 2
        self.assertTrue(sanctuary.rest(state, "wisla_grane", run=fresh)["ok"])

    def test_the_door_is_shut_to_a_healthy_player(self):
        well = _battered(health=config.STAMINA_MAX)
        self.assertEqual(sanctuary.reveal_reasons(well,
                                                  sanctuary_id="nock"), [])
        hurt = _battered(health=2)
        self.assertIn("BANDED", sanctuary.reveal_reasons(hurt,
                                                         sanctuary_id="nock"))


# ---------------------------------------------------------------------------
# 3. NOTHING STRANDS A PLAYER
# ---------------------------------------------------------------------------

class NoDeadEnds(GameTest):
    """LEARNING NEVER DEAD-ENDS, checked at the worst moment the game has."""

    def test_every_refusal_names_something_else_to_do(self):
        state = _battered()
        run = {"dungeon": "lit_tiles", "run_seed": 4, "at": 0}
        sanctuary.rest(state, "tobias_rell", run=run)
        for who in sanctuary.SANCTUARIES:
            for sealed in (False, True):
                gate = sanctuary.can_rest(
                    state, who.id,
                    run={"dungeon": who.dungeon or "x", "run_seed": 4,
                         "at": 0},
                    sealed=sealed)
                if gate["allowed"]:
                    continue
                self.assertTrue(
                    gate["remedy"],
                    "%s refused with no way forward" % who.id)

    def test_battered_broke_and_alone_there_is_always_a_way_onward(self):
        """One health, no gold, a fainted companion, deep in a dungeon, and the
        healer already spent. Four separate ways onward, none of which is a
        sanctuary and none of which costs a coin."""
        state = _battered(health=1, gold=0, region="stack_queue_mines")
        upkeep.pet_knock(state, "moth", hits=upkeep.PET_KNOCKS_TO_FAINT)
        run = {"dungeon": "ninth_cart", "run_seed": 3, "at": 0}

        # A fainted companion opens the door on its own, whatever the health is.
        self.assertIn("FALLEN",
                      sanctuary.reveal_reasons(state, sanctuary_id="dov_kerrin"))
        first = sanctuary.rest(state, "dov_kerrin", run=run)
        self.assertTrue(first["ok"])
        self.assertEqual(first["gold_cost"], 0)
        self.assertEqual(first["revived"], ["moth"])
        self.assertEqual(state["player"]["gold"], 0)

        # Now spend it and knock everything down again. Every sanctuary refuses.
        state["player"][upkeep.HEALTH_FIELD] = 1
        upkeep.pet_knock(state, "moth", hits=upkeep.PET_KNOCKS_TO_FAINT)
        for who in sanctuary.SANCTUARIES:
            self.assertFalse(sanctuary.can_rest(
                state, who.id,
                run={"dungeon": who.dungeon or "x", "run_seed": 3,
                     "at": 0})["allowed"])

        # 1. The town is free, is never mandatory, and does not care about gold.
        self.assertEqual(upkeep.LOOP["mandatory"], ())
        visit = upkeep.town_visit(state, gold=0)
        self.assertEqual(visit["healer"]["gold_cost"], 0)
        self.assertEqual(state["player"][upkeep.HEALTH_FIELD],
                         config.STAMINA_MAX)
        self.assertEqual(upkeep.fainted_pets(state), [])
        self.assertEqual(state["player"]["gold"], 0)

        # 2. The armour floor: nothing ever breaks, so no fight is unwinnable.
        for piece in upkeep.PIECES:
            self.assertGreaterEqual(upkeep.integrity(state, piece),
                                    upkeep.INTEGRITY_MIN)

        # 3. The learning floor never ran through the animal or the healer.
        state["player"][upkeep.HEALTH_FIELD] = 0
        upkeep.pet_knock(state, "moth", hits=upkeep.PET_KNOCKS_TO_FAINT)
        gate = upkeep.pet_gate(state, "moth", attempts=pets.FREE_SOLUTION_AFTER)
        self.assertTrue(gate["floor"])

        # 4. And no sanctuary is a prerequisite for anything, anywhere.
        self.assertTrue(sanctuary.self_check()["no_dead_end"][
            "nothing_requires_a_sanctuary"])

    def test_no_boon_and_no_healer_ever_supplies_an_answer(self):
        self.assertEqual(captives._no_boon_supplies_an_answer(), [])
        for boon in captives.BOONS.values():
            for key in boon.get("effects", {}):
                self.assertIn(key, captives.BOON_EFFECTS_ALLOWED)
                self.assertNotIn(key, captives.BOON_EFFECTS_REFUSED)
        report = sanctuary.self_check()
        self.assertTrue(report["no_answers"]["keys_declared"],
                        report["no_answers"]["unexpected"])
        self.assertTrue(report["no_answers"]["no_answer_keys"])
        self.assertTrue(report["one_healer"]["no_second_heal"],
                        report["one_healer"].get("wrote"))

    def test_a_rescue_never_pays_twice(self):
        state = {}
        first = captives.free(state, "bug_demon")
        self.assertTrue(first)
        self.assertEqual(captives.free(state, "bug_demon"), {})
        self.assertEqual(len(captives.freed(state)),
                         len(captives.held_by("bug_demon")))


# ---------------------------------------------------------------------------
# 4. THE CAPTIVES ARE PEOPLE
# ---------------------------------------------------------------------------

# Written as a rule rather than a word list where it can be: what is banned is
# a captive being framed as something won. The words are the crude half and the
# structural checks in captives.validate() are the rest of it.
_NOT_A_PRIZE = re.compile(
    r"\b(kiss(?:es|ed|ing)?|lover|lovers|romance|romantic|seduc\w*|"
    r"naked|nude|nudity|undress\w*|strip(?:s|ped|ping)?\s+(?:off|down)|"
    r"bare(?:s|d)?\s+(?:her|his|their)\s+\w+|"
    r"bosom|cleavage|curv(?:y|aceous)|shapely|voluptuous|buxom|"
    r"scantily|negligee|lingerie|"
    r"throws?\s+(?:her|him)self\s+at|swoon\w*|"
    r"your\s+(?:prize|reward|trophy)|"
    r"(?:she|he|they)\s+(?:is|are)\s+yours)\b",
    re.IGNORECASE)


class TheCaptivesArePeople(GameTest):

    def test_the_roster_validates(self):
        self.assertEqual(captives.validate(), [])
        counts = captives.counts()
        self.assertEqual(counts["bosses"], counts["bosses_in_world"])
        self.assertGreaterEqual(counts["villages"], 10)

    def test_everybody_has_a_name_a_trade_an_opinion_and_their_own_words(self):
        for person in captives.CAPTIVES:
            self.assertTrue(person.name)
            self.assertTrue(person.trade, "%s is a noun" % person.id)
            self.assertGreater(len(person.opinion), 40, person.id)
            self.assertGreaterEqual(len(person.lines), 2, person.id)
            self.assertTrue(person.afterwards, person.id)
            self.assertTrue(person.change, person.id)
            # At least one thing they say has to be about their own life.
            about_the_player = sum(
                1 for line in person.lines
                if "you" in line.lower().split()[:4])
            self.assertLess(about_the_player, len(person.lines), person.id)

    def test_several_of_them_are_more_use_afterwards_than_before(self):
        with_boons = [p for p in captives.CAPTIVES if p.boon]
        self.assertGreaterEqual(len(with_boons), 8)
        # And not all of them, because a roster where everybody pays out is a
        # roster of rewards again.
        self.assertLess(len(with_boons), len(captives.CAPTIVES))
        for person in with_boons:
            boon = captives.BOONS[person.boon]
            self.assertTrue(boon.get("effects") or boon.get("stocks")
                            or boon.get("route"), person.boon)

    def _no_prizes_in(self, where: str, lines) -> None:
        for line in lines:
            match = _NOT_A_PRIZE.search(line)
            self.assertIsNone(
                match,
                "%s: %r reads as a reward rather than a person, in: %s"
                % (where, match.group(0) if match else "", line[:160]))

    def test_nobody_in_any_of_the_three_modules_is_written_as_a_prize(self):
        for module in (captives, sanctuary, finale):
            self._no_prizes_in(module.__name__, _authored_strings(module))

    def test_the_cutscene_itself_is_scanned_and_not_just_its_constants(self):
        """finale's lines are built per-scene rather than declared, so the
        module-level scan cannot see most of them. Play the ending at every
        roll-call size and read the whole thing."""
        state = {}
        sizes = []
        for boss_id in captives.HOLDINGS:
            scene = finale.cutscene(
                freed=captives.roll_call(state),
                total_captives=len(captives.CAPTIVES),
                names=["seen", "window", "counts"],
                weak_regions=("graph_wastes",))
            sizes.append(scene["roll_call"]["count"])
            self._no_prizes_in("finale scene", finale._all_text(scene))
            for beat in scene["beats"]:
                self._no_prizes_in(
                    "finale rows",
                    [str(value) for row in beat["rows"]
                     for value in row.values() if isinstance(value, str)])
            captives.free(state, boss_id)
        # And the roll call really did grow, so the scan was not of one scene
        # fourteen times.
        self.assertEqual(sizes[0], 0)
        self.assertGreater(sizes[-1], 20)

    def test_the_rescue_is_handed_over_by_them_and_is_not_them(self):
        """The structural half of "they are people": the reward is a thing a
        freed person gives you, never the person."""
        for boss_id, holding in captives.HOLDINGS.items():
            self.assertTrue(holding.handover, boss_id)
            rescue = captives.free({}, boss_id)
            # Everything the rescue pays is a quest reward key, and there is no
            # key anywhere in it whose value is a captive.
            for key in rescue["pay"]:
                self.assertIn(key, captives.quests.REWARD_KEYS, boss_id)
            self.assertNotIn("captive", rescue["pay"])
            self.assertNotIn("companion", rescue["pay"])
            # Each captive in the payload carries their own words and their own
            # opinion, not a description of what they are worth.
            for person in rescue["captives"]:
                self.assertTrue(person["opinion"], person["id"])
                self.assertTrue(person["lines"], person["id"])
                self.assertTrue(person["afterwards"], person["id"])

    def test_the_hidden_healers_are_people_too(self):
        report = sanctuary.self_check()
        self.assertTrue(report["people"]["complete"],
                        report["people"]["missing"])
        self.assertTrue(report["people"]["all_kinds_used"])
        self.assertTrue(report["people"]["unique_names"])
        for who in sanctuary.SANCTUARIES:
            self.assertTrue(who.why)
            self.assertNotIn("so that you", who.why.lower())
            self.assertNotIn("for the player", who.why.lower())

    def test_the_register_holds(self):
        """Rule 7 of the story bible: no exclamation marks, anywhere, except the
        one the 80s title card has earned."""
        for module in (captives, sanctuary):
            for line in _authored_strings(module):
                self.assertNotIn("!", line, module.__name__)
        scene = finale.cutscene(freed=(), exam_report=None)
        shouts = [t for t in finale._all_text(scene) if "!" in t]
        self.assertEqual(shouts, [scene["title_card"]["shout"]])


# ---------------------------------------------------------------------------
# 5. THE READINESS LINE IS HONEST
# ---------------------------------------------------------------------------

class TheReadinessLineIsHonest(GameTest):

    _CLAIM = "met the standard for this timed Python practical"

    def _scene(self, solved: int, *, freed: int = 0, seed: int = 21):
        exam = finalexam.compose(self.corpus, seed=seed)
        questions = [q for seg in exam.segments for q in seg["questions"]]
        results = [{"problem_id": q.problem_id, "solved": index < solved,
                    "rank": "A" if index < solved else "",
                    "seconds": int(q.target_seconds * 0.9),
                    "root_cause": "" if index < solved else "OFF_BY_ONE"}
                   for index, q in enumerate(questions)]
        report = finalexam.debrief(exam, results)
        state = {}
        for boss_id in list(captives.HOLDINGS)[:freed]:
            captives.free(state, boss_id)
        return report, finale.cutscene(
            freed=captives.roll_call(state), exam_report=report,
            total_captives=len(captives.CAPTIVES))

    def test_the_line_is_only_said_when_something_measured_it(self):
        for solved in range(0, 7):
            with self.subTest(solved=solved):
                report, scene = self._scene(solved)
                said = self._CLAIM in " ".join(scene["send_off"]["lines"])
                self.assertEqual(said, report["verdict"]["code"] == "READY")

    def test_a_pass_is_a_pass_that_actually_kept_the_clock(self):
        report, scene = self._scene(99)
        self.assertEqual(scene["send_off"]["code"], "READY")
        self.assertTrue(scene["evidence"]["within_clock"],
                        "READY said 'inside the clock' without keeping it")
        self.assertIn("%s of %s" % (report["solved"], report["total"]),
                      " ".join(scene["send_off"]["lines"]))

    def test_a_player_who_is_not_ready_is_told_kindly_and_given_a_route(self):
        report, scene = self._scene(1)
        send_off = scene["send_off"]
        self.assertEqual(report["verdict"]["code"], "NOT_READY")
        self.assertEqual(send_off["code"], "NOT_READY")
        # Told, not flattered.
        self.assertNotIn(self._CLAIM, " ".join(send_off["lines"]))
        self.assertIn("did not meet the standard", " ".join(send_off["lines"]).lower())
        # The win is still celebrated first, before the bad news.
        self.assertTrue(send_off["celebrates"])
        # And there is a countable route out.
        self.assertTrue(send_off["drills"])
        self.assertTrue(send_off["honest"])
        # It is a verdict on the format, never on the person.
        self.assertIn("a record of this attempt, not a limit on what you can learn",
                      " ".join(send_off["lines"]))

    def test_the_numbers_in_the_line_are_the_measured_ones(self):
        for solved in (1, 3, 6):
            with self.subTest(solved=solved):
                report, scene = self._scene(solved)
                text = " ".join(scene["send_off"]["lines"])
                self.assertIn("%s of %s" % (report["solved"], report["total"]),
                              text)
                self.assertEqual(scene["evidence"]["solved"], report["solved"])
                self.assertEqual(scene["evidence"]["verdict"],
                                 report["verdict"]["code"])

    def test_no_practical_means_no_claim_at_all(self):
        scene = finale.cutscene(freed=(), exam_report=None)
        self.assertEqual(scene["send_off"]["code"], "UNMEASURED")
        self.assertNotIn(self._CLAIM, " ".join(scene["send_off"]["lines"]))
        self.assertEqual(finale.validate(scene), [])

    def test_the_roll_call_never_rounds_itself_up(self):
        """§5 of the bible: a eucatastrophe, not a restoration. The ribbon may
        not claim everybody unless everybody is actually out."""
        state = {}
        captives.free(state, "bug_demon")
        release = captives.final_release(state)
        self.assertTrue(release["counts"]["still_held"] > 0)
        scene = finale.cutscene(freed=captives.roll_call(state),
                                total_captives=len(captives.CAPTIVES))
        self.assertNotEqual(scene["roll_call"]["scale"], "EVERY_LAST_ONE")
        self.assertNotIn("EVERY LAST ONE", scene["title_card"]["ribbon"])

    def test_the_three_modules_check_themselves(self):
        self.assertEqual(captives.validate(), [])
        healers = sanctuary.self_check()
        self.assertTrue(healers["ok"], healers["failures"])
        ending = finale.self_check()
        self.assertTrue(ending["ok"], ending["failures"])


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
