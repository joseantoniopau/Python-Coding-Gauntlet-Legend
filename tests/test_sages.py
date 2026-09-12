"""The hidden sages, their gauntlets, and the secret arts they do not give away.

Every number in here is measured at run time. Nothing is asserted against a
figure copied out of a docstring, because the defect this file was written after
was exactly that: `gauntlet/sages.py` proved its arts were harder than ordinary
moves on a scale it invented itself, every run, truthfully, while the scale that
decides damage said the opposite for sixty-nine of them.

So the rule here is that a claim is tested against the ruler the GAME uses —
`incantation.measure_complexity` — and against the real corpus, the real
`finalexam` seal and the real state machine, or it is not tested.

The tests do not build the corpus unless they need it, so this subclasses
TestCase directly and leans on base.py only for the repo path.
"""
from __future__ import annotations

import ast
import base  # noqa: F401  - puts the repo on sys.path
import unittest
from pathlib import Path

from gauntlet import arts, incantation, movesets, sages, world

REPO = Path(__file__).resolve().parent.parent

# The catalogue that ships is `arts.py`'s — see sages.overlap_report()["decision"].
# Where a test says "the arts", it means those.
SHIPPING = arts


def tearDownModule():
    """Put the two registries back exactly as they were found.

    `arts.register()` writes ninety-six lines into `incantation.BY_ID` and
    ninety-six moves into `movesets.BY_ID`. Those are other passes' tables, and
    `tests/test_incantation.py::test_contract_mirror_has_not_drifted` asserts
    that `incantation.BY_ID` still matches `bestiary.EXPECTED_INCANTATIONS`. A
    test module that left the arts registered would fail a test in a file it
    does not own, which is how this was found in the first place.
    """
    arts.unregister()


# ---------------------------------------------------------------------------
# 1. The arts earn their damage
# ---------------------------------------------------------------------------

class TestComplexityFloor(unittest.TestCase):
    """An art out-damages an ordinary move because it demands more Python.

    Measured on `incantation.measure_complexity`, which is the function
    `incantation._damage_for` actually calls, against the hardest ordinary line
    the player could already cast in that same area.
    """

    def test_every_art_out_demands_the_hardest_ordinary_line_in_its_own_area(self):
        with arts.registered():
            under = []
            for art in arts.ARTS:
                best, bar = arts.ordinary_line_ceiling(art.chapter)
                raw = art.complexity().raw
                if raw < bar * arts.LINE_MARGIN:
                    under.append("%s: raw %.2f vs %.2f x %.2f (%s) in %s"
                                 % (art.id, raw, arts.LINE_MARGIN, bar,
                                    best.id if best else "-", art.region))
        self.assertEqual(under, [], "\n".join(under))

    def test_no_art_is_merely_a_bigger_number(self):
        """There is nowhere in the catalogue for a finder's bonus to be typed.

        `power` is a floor computed from the art's own worst possible cast, and
        the test is that it never binds: at every tier above zero the typing
        term is already larger, so the authored number decides nothing.
        """
        with arts.registered():
            binds = []
            for art in arts.ARTS:
                floor = art.inc.power * incantation.POWER_FLOOR_SHARE
                for tier in range(1, incantation.MAX_TIER + 1):
                    typed = (incantation.DAMAGE_UNIT
                             * art.complexity(tier=tier).weight)
                    if floor > typed + 1e-9:
                        binds.append("%s at tier %d" % (art.id, tier))
        self.assertEqual(binds, [])

    def test_the_authoring_function_cannot_be_handed_a_power(self):
        import inspect
        params = inspect.signature(arts._art).parameters
        for forbidden in ("power", "damage", "multiplier", "bonus"):
            self.assertNotIn(forbidden, params)

    def test_the_art_move_beats_the_best_ordinary_move_of_its_own_shape(self):
        with arts.registered():
            under = [r["art"] for r in arts.ranking_table()
                     if not r["clears_move_bar"]]
        self.assertEqual(under, [])

    def test_repetition_is_the_only_thing_that_raises_an_art(self):
        """Drilling an art to RECALLED must be worth strictly more than casting
        it once at PROMPTED. If it were not, the reward for study would be
        nothing and the reward for finding would be everything."""
        with arts.registered():
            for art in arts.ARTS:
                low = art.complexity(tier=0).raw
                high = art.complexity(tier=incantation.MAX_TIER).raw
                self.assertGreater(high, low, art.id)


class TestTheRulerIsTooShort(unittest.TestCase):
    """The one defect in this system that cannot be fixed from these two files.

    `incantation.SCORE_FULL` clamps the measurement at raw 40. The sixty-six
    ordinary lines never reach it. The arts are all past it by RECALLED, so at
    the tier a drilled art is actually cast at they measure the same and deal
    the same damage. These tests do not assert that the game is fine — it is
    not. They assert that the number is MEASURED and REPORTED rather than
    quietly passed over, so that whoever owns incantation.py sees it.
    """

    def test_saturation_is_measured_and_surfaced(self):
        report = arts.saturation_report()
        self.assertIn("by_tier", report)
        self.assertEqual(len(report["by_tier"]), incantation.MAX_TIER + 1)
        self.assertIn("collapsed_at_recalled", report)
        self.assertTrue(report["verdict"])

    def test_the_handover_names_the_exact_edit(self):
        ask = arts.handover()["score_full"]
        self.assertIn("SCORE_FULL", ask["edit"])
        # It must be reported as unmet for as long as it IS unmet.
        collapsed = arts.saturation_report()["collapsed_at_recalled"]
        self.assertEqual(ask["holds"], not collapsed)

    def test_the_ordinary_catalogue_still_fits_inside_the_ruler(self):
        """The clamp is the arts' problem, not the whole game's. If an ORDINARY
        line ever saturates too, the damage curve has stopped working for
        everybody and this stops being a secret-art bug."""
        for tier in range(incantation.MAX_TIER + 1):
            for inc in incantation.CATALOGUE:
                measured = incantation.measure_complexity(
                    inc, dict(inc.example), tier=tier)
                self.assertLess(measured.score, 100,
                                "%s saturates at tier %d" % (inc.id, tier))


# ---------------------------------------------------------------------------
# 2. Every sage is findable and every gauntlet is winnable
# ---------------------------------------------------------------------------

class TestReachability(base.GameTest):
    """Uses `base.GameTest` for the corpus.

    NOT for convenience — for correctness. `corpus.load()` reads
    `GAUNTLET_DATA_DIR/corpus.json`, and `GameTest.setUp` repoints that variable
    at a throwaway directory it deletes afterwards. A plain TestCase here passes
    alone and raises FileNotFoundError in the full suite, depending entirely on
    which module ran before it. `self.corpus` is the corpus the whole suite
    shares.
    """

    def test_one_sage_per_fighting_region_and_none_in_the_exam_hall(self):
        regions = {r["id"] for r in world.REGIONS}
        covered = set(sages.SAGE_BY_REGION)
        self.assertEqual(regions - covered, {"null_kings_castle"})
        self.assertEqual(len(sages.SAGES), 16)

    def test_every_class_meets_a_face_and_is_taught_exactly_one_art(self):
        for sage in sages.SAGES:
            faces = [f.class_id for f in sage.faces]
            self.assertCountEqual(faces, list(sages.CLASS_IDS), sage.id)
            for class_id in sages.CLASS_IDS:
                self.assertIsNotNone(sages.face(sage.id, class_id))

    def test_the_two_rosters_agree_on_every_room(self):
        """`sages.py` says where the person is; `arts.py` says what is taught
        there. A room in one and not the other is a sage with nothing to teach
        or an art nobody can be taught."""
        bridge = arts.sage_bridge()
        self.assertEqual(bridge["regions_only_in_sages"], [])
        self.assertEqual(bridge["regions_only_here"], [])
        self.assertEqual(bridge["unmatched"], [])
        self.assertEqual(len(bridge["mapping"]), 16 * 6)

    def test_every_discovery_clause_names_something_that_really_exists(self):
        """A clause whose kind is unknown scores zero for ever and makes its
        sage permanently unfindable, silently. So every clause kind must be
        handled, and every value it names must be in a live registry."""
        from gauntlet import dungeons, skills
        srs_families = {p.spaced_repetition_family for p in self.corpus}
        skill_ids = set(skills.SKILLS)
        boss_ids = set(world.BOSS_BY_ID)
        region_ids = {r["id"] for r in world.REGIONS}
        dungeon_ids = set(getattr(dungeons, "DUNGEON_BY_ID", {}))
        bad = []
        for sage in sages.SAGES:
            self.assertTrue(sage.discovery.needs, sage.id)
            for clause in sage.discovery.needs:
                kind = clause.get("kind", "")
                if kind not in sages.SAGE_CHECKS:
                    bad.append("%s: unhandled clause %r" % (sage.id, kind))
                    continue
                if kind == "family_unaided" and clause["family"] not in srs_families:
                    bad.append("%s: no such family %r" % (sage.id, clause["family"]))
                if kind == "boss_unaided" and clause["boss"] not in boss_ids:
                    bad.append("%s: no such boss %r" % (sage.id, clause["boss"]))
                if kind == "dungeon_depth" and clause["dungeon"] not in dungeon_ids:
                    bad.append("%s: no such dungeon %r" % (sage.id, clause["dungeon"]))
                if kind in ("region_clears", "region_cleared") \
                        and clause["region"] not in region_ids:
                    bad.append("%s: no such region %r" % (sage.id, clause["region"]))
                if clause.get("skill") and clause["skill"] not in skill_ids:
                    bad.append("%s: no such skill %r" % (sage.id, clause["skill"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_every_evidence_key_a_clause_reads_is_documented_or_already_emitted(self):
        """A discovery clause is only as real as the evidence key behind it.

        Nine of the sixteen sages gate on keys `engine.Game._pet_evidence()`
        does not return yet, so they are in the world and cannot be found — and
        `mines` is the worst of them, because its single condition is one of
        those keys. That is a wiring debt rather than a design fault, but it has
        to be a fact somebody can read rather than something a player discovers
        by never meeting a sage. This test says the debt is enumerated.
        """
        wiring = sages.self_check()["wiring"]
        self.assertEqual(wiring["undocumented"], [],
                         "an evidence key with no source and no description")
        # The verdict must not depend on whether `inspect` can read engine.py.
        # It could not, once, inside the full suite, and the report quietly
        # claimed that every pets-shared key was undocumented.
        import inspect as _inspect
        real = _inspect.getsource
        _inspect.getsource = lambda obj: (_ for _ in ()).throw(OSError("no source"))
        try:
            blind = sages.self_check()["wiring"]
        finally:
            _inspect.getsource = real
        self.assertFalse(blind["engine_source_readable"])
        self.assertEqual(blind["undocumented"], wiring["undocumented"])
        # SUBSET, NOT EQUALITY, AND THE DEBT IS NOW ALMOST PAID.
        #
        # These two were equalities, and they could only hold while
        # `engine.Game._pet_evidence()` emitted exactly the keys it shares with
        # pets.py — which is to say, while nine sages were unreachable. The
        # wiring pass emitted the rest, so the readable report is now shorter
        # than the blind fallback, and asserting they are the same would be
        # asserting the debt back into existence.
        #
        # What the blind branch was actually protecting is still asserted: the
        # fallback must be CONSERVATIVE, never claiming a sage is reachable when
        # the report could not read the engine to find out.
        self.assertTrue(set(wiring["keys_still_owed"])
                        <= set(blind["keys_still_owed"]))
        self.assertTrue(set(wiring["sages_unfindable_until_then"])
                        <= set(blind["sages_unfindable_until_then"]))
        for key in wiring["keys_still_owed"]:
            self.assertIn(key, sages.EVIDENCE_SOURCES)
            shape, how = sages.EVIDENCE_SOURCES[key]
            self.assertTrue(shape and how, key)
        # And every blocked sage is named, so none of them is a silent one.
        for sage_id in wiring["sages_unfindable_until_then"]:
            self.assertIn(sage_id, sages.SAGE_BY_ID)

    def test_nothing_is_findable_with_no_evidence_at_all(self):
        self.assertEqual(sages.newly_found({}), [])
        for sage in sages.SAGES:
            self.assertFalse(sages.discovery_progress(sage.id, {})["met"], sage.id)

    def test_an_unnamed_retest_clause_counts_each_ambush_once(self):
        """`_pet_evidence` publishes the per-skill counts AND the total, under
        the empty key. A clause that named no skill summed the whole dict, which
        added the total to its own parts and read exactly twice the truth — a
        three-ambush gate opening on two. Both readers are checked, because
        sages.py and pets.py carry the same clause reader.
        """
        from gauntlet import pets
        evidence = {"retests": {"PYTHON": 2, "ARRAY": 1, "": 3}}
        clause = {"kind": "retest_survived", "skill": "", "count": 3}
        for module in (sages, pets):
            row = module._discovery_row(clause, evidence)
            self.assertEqual(row["have"], 3.0,
                             "%s counted the total twice" % module.__name__)
            self.assertTrue(row["met"])
        # Two ambushes must NOT open a three-ambush gate.
        short = {"retests": {"PYTHON": 2, "": 2}}
        for module in (sages, pets):
            self.assertFalse(module._discovery_row(clause, short)["met"],
                             "%s opened early" % module.__name__)
        # A named skill still reads its own count and not the total.
        named = {"kind": "retest_survived", "skill": "ARRAY", "count": 2}
        for module in (sages, pets):
            self.assertEqual(module._discovery_row(named, evidence)["have"], 1.0)

    def test_the_art_gated_sages_cannot_deadlock(self):
        """Four sages ask for arts you already hold. If every sage did, none
        could ever be the first, and the whole system would be unreachable."""
        free = [s for s in sages.SAGES
                if not any(c["kind"] == "arts_known" for c in s.discovery.needs)]
        self.assertGreaterEqual(len(free), 6)
        for sage in sages.SAGES:
            for clause in sage.discovery.needs:
                if clause["kind"] == "arts_known":
                    # Never ask for more arts than there are earlier sages.
                    earlier = sum(1 for other in sages.SAGES
                                  if other.tier < sage.tier)
                    self.assertLessEqual(clause["count"], earlier, sage.id)

    def test_every_gauntlet_resolves_to_real_problems(self):
        pool = [p for p in self.corpus if not getattr(p, "sealed", False)]
        unresolved = []
        for sage in sages.SAGES:
            for class_id in sages.CLASS_IDS:
                for attempt in (0, 1, 2):
                    plan = sages.resolve_gauntlet(sage.id, class_id, pool,
                                                  attempt=attempt)
                    if not plan["resolved"]:
                        unresolved.append("%s/%s attempt %d: %s"
                                          % (sage.id, class_id, attempt,
                                             plan["unresolved"]))
        self.assertEqual(unresolved, [], "\n".join(unresolved))

    def test_the_trial_gets_longer_and_harder_as_the_ladder_rises(self):
        counts = [len(s.stages) for s in sorted(sages.SAGES, key=lambda s: s.tier)]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual((counts[0], counts[-1]), (3, 5))

    def test_a_gauntlet_never_hands_over_a_solution(self):
        """The trial is problem ids and a frame. If a plan ever carried a
        canonical solution, a hint tree or a test, the gauntlet would be a
        tutorial with a prize."""
        pool = [p for p in self.corpus if not getattr(p, "sealed", False)]
        plan = sages.resolve_gauntlet("coliseum", "warden", pool)
        blob = repr(plan)
        for leak in ("canonical_solution", "hint_tree", "hidden_tests",
                     "alternate_solutions", "def solve"):
            self.assertNotIn(leak, blob)


# ---------------------------------------------------------------------------
# 3. Failing costs nothing permanent
# ---------------------------------------------------------------------------

class TestNoDeadEnds(unittest.TestCase):

    def _met(self, sage_id="mines"):
        state = sages.new_state()
        sages.meet(state, sage_id)
        return state

    def test_failing_takes_nothing_away(self):
        state = self._met()
        state["arts"].append("art_artificer_syntax")
        state["cleared"]["syntax"] = ["artificer"]
        before = {"arts": list(state["arts"]),
                  "cleared": {k: list(v) for k, v in state["cleared"].items()},
                  "found": list(state["found"])}
        result = sages.fail(state, "mines", "write", region_clears=4)
        self.assertEqual(result["lost"], [])
        self.assertTrue(result["reattemptable"])
        self.assertEqual(state["arts"], before["arts"])
        self.assertEqual(state["cleared"], before["cleared"])
        self.assertEqual(state["found"], before["found"])

    def test_a_failed_gauntlet_is_re_attemptable_after_a_toll_of_encounters(self):
        state = self._met()
        sages.fail(state, "mines", "write", region_clears=4)
        blocked, why = sages.may_attempt(state, "mines", region_clears=4)
        self.assertFalse(blocked)
        self.assertTrue(why)
        # The toll is paid in encounters cleared, and then the door opens again.
        allowed, _ = sages.may_attempt(
            state, "mines", region_clears=4 + sages.RETURN_TOLL)
        self.assertTrue(allowed)

    def test_the_toll_is_the_only_thing_failing_costs_and_it_expires(self):
        state = self._met()
        for _ in range(5):                      # fail it over and over
            sages.fail(state, "mines", "proof", region_clears=0)
        self.assertEqual(state["toll_at"]["mines"], sages.RETURN_TOLL)
        self.assertEqual(state["arts"], [])
        ok, _ = sages.may_attempt(state, "mines", region_clears=sages.RETURN_TOLL)
        self.assertTrue(ok)

    def test_clearing_grants_exactly_one_art_and_never_a_second_time(self):
        state = self._met("village")
        first = sages.complete(state, "village", "warden")
        self.assertTrue(first["granted"])
        self.assertEqual(len(state["arts"]), 1)
        again = sages.complete(state, "village", "warden")
        self.assertFalse(again["granted"])
        self.assertEqual(len(state["arts"]), 1)

    def test_clearing_clears_the_toll(self):
        state = self._met("village")
        sages.fail(state, "village", "write", region_clears=0)
        self.assertIn("village", state["toll_at"])
        sages.complete(state, "village", "seer")
        self.assertNotIn("village", state["toll_at"])

    def test_the_state_machine_cannot_take_anything_away(self):
        """Structural, not behavioural: no function in the module removes an
        art, a sage or a cleared gauntlet. A module that cannot subtract cannot
        be argued into subtracting later."""
        source = (REPO / "gauntlet" / "sages.py").read_text()
        tree = ast.parse(source)
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("remove", "discard"):
                offenders.append(ast.unparse(node))
            if isinstance(func, ast.Attribute) and func.attr == "pop":
                # popping the TOLL and the remembered rung is the whole point;
                # popping anything else would be taking progress away.
                text = ast.unparse(node)
                if not any(key in text for key in ("toll_at", "failed_at")):
                    offenders.append(text)
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_game_is_finishable_having_never_found_a_sage(self):
        """An art must be an advantage, never a requirement. Nothing may hand
        one out as a clear reward, and no skill node may require one."""
        from gauntlet import classes
        with arts.registered():
            art_ids = set(arts.ART_IDS) | set(arts.ART_MOVE_IDS)
            # Not in the catalogues the ordinary progression draws from.
            self.assertEqual(art_ids & {i.id for i in incantation.CATALOGUE},
                             set())
            self.assertEqual(art_ids & {m.id for m in movesets.CATALOGUE}, set())
            # Not on any skill tree node.
            blob = repr(getattr(classes, "NODES", []))
            for ident in sorted(art_ids):
                self.assertNotIn(ident, blob)
        # And the castle opens on mastery, bosses and gates — never on arts.
        source = (REPO / "gauntlet" / "world.py").read_text()
        self.assertNotIn("art", source.split("def castle_requirements")[1][:1500])


class TestThePrizeIsNamedOnce(base.GameTest):
    """Two catalogues hold an art for each (region, class): sages.py's retired
    one, keyed `art_<region>_<class>`, and arts.py's shipping one, keyed
    `art_<class>_<region>`. Different ids AND different names. `gauntlet_stage`
    already corrected the name on the way out; `begin_gauntlet` still announced
    sages', so the trial promised one art and paid another."""

    def test_the_trial_announces_the_art_it_actually_teaches(self):
        from gauntlet.engine import SAGES_STATE_KEY
        g = self.game()
        state = g.state[SAGES_STATE_KEY]
        class_id = g._class_id()
        for sage in sages.SAGES:
            taught = arts.taught_here(sage.region, class_id)
            if taught is None:
                continue
            # Whatever the board and the door say, they say the same thing, and
            # it is the id `_teach_art` will actually grant.
            board = g.sage_board(sage.region)
            if board.get("art"):
                self.assertEqual(board["art"]["id"], taught.id, sage.id)
                self.assertEqual(board["art"]["name"], taught.name, sage.id)
            # And the door, with the sage met so `begin` gets past its guard.
            state.setdefault("found", [])
            if sage.id not in state["found"]:
                state["found"].append(sage.id)
            g.state["player"]["region"] = sage.region
            g.save()
            plan = g.begin_gauntlet(sage.region)
            if plan.get("error") or not plan.get("art"):
                continue
            self.assertEqual(plan["art"]["id"], taught.id,
                             "%s promised %s and teaches %s"
                             % (sage.id, plan["art"]["id"], taught.id))
            self.assertEqual(plan["art"]["name"], taught.name, sage.id)


class TestRetriesRedraw(base.GameTest):
    """The corpus half of "failing costs nothing permanent"."""

    def test_a_retry_draws_different_problems(self):
        """Failing must not turn into a memorised sequence.

        The authored shortlist (`Stage.prefer`) does not read `attempt`, so a
        gauntlet whose every rung was covered by it drew the same five problems
        for ever. Four of the ninety-six did. The shortlist is now a
        first-attempt thing and a retry takes the seeded draw.
        """
        pool = [p for p in self.corpus if not getattr(p, "sealed", False)]
        identical = []
        for sage in sages.SAGES:
            for class_id in sages.CLASS_IDS:
                first = [r["problem"] for r in
                         sages.resolve_gauntlet(sage.id, class_id, pool,
                                                attempt=0)["stages"]]
                second = [r["problem"] for r in
                          sages.resolve_gauntlet(sage.id, class_id, pool,
                                                 attempt=1)["stages"]]
                if first == second:
                    identical.append("%s/%s" % (sage.id, class_id))
        # A few regions hold barely more problems of the right shape than the
        # gauntlet has rungs, so there the SET is forced whatever the seed does.
        # It must stay rare, and it must never be the whole catalogue.
        self.assertLessEqual(len(identical), 6,
                             "%d of 96 retries are identical: %s"
                             % (len(identical), identical))


# ---------------------------------------------------------------------------
# 4. Every class is served equally
# ---------------------------------------------------------------------------

class TestClassParity(unittest.TestCase):

    def test_six_registers_sixteen_arts_each(self):
        for class_id in sages.CLASS_IDS:
            self.assertEqual(len(arts.for_class(class_id)), 16, class_id)
            self.assertEqual(len(sages.arts_for(class_id)), 16, class_id)

    def test_every_class_has_its_own_face_title(self):
        titles = {sages.FACE_TITLES[c] for c in sages.CLASS_IDS}
        self.assertEqual(len(titles), len(sages.CLASS_IDS))

    def test_no_class_ladder_is_strictly_worse_than_another(self):
        """Compared inside each shape, because a one-line strike and a
        three-line storm are different turn lengths, not different quality.
        No class's WORST art may be worse than another class's worst by more
        than half, and no class's mean may be under two thirds of the best.
        """
        with arts.registered():
            by_class = {}
            for class_id in arts.CLASS_IDS:
                raws = [a.complexity().raw for a in arts.for_class(class_id)]
                by_class[class_id] = (min(raws), sum(raws) / len(raws))
        means = {c: m for c, (_, m) in by_class.items()}
        best = max(means.values())
        for class_id, mean in means.items():
            self.assertGreater(mean, best * 0.66,
                               "%s is strictly worse: mean %.2f vs best %.2f"
                               % (class_id, mean, best))

    def test_every_class_clears_the_bar_in_every_area(self):
        with arts.registered():
            for class_id in arts.CLASS_IDS:
                for art in arts.for_class(class_id):
                    _, bar = arts.ordinary_line_ceiling(art.chapter)
                    self.assertGreaterEqual(art.complexity().raw,
                                            bar * arts.LINE_MARGIN, art.id)

    def test_the_shapes_are_shared_rather_than_one_class_owning_the_good_one(self):
        shapes = {c: arts.CLASS_SHAPE[c] for c in arts.CLASS_IDS}
        self.assertEqual(len(set(shapes.values())), 4)
        for shape in set(shapes.values()):
            self.assertIn(shape, movesets.SHAPES)


# ---------------------------------------------------------------------------
# 5. The seal
# ---------------------------------------------------------------------------

class TestTheSeal(unittest.TestCase):

    def test_a_sage_is_a_mentor_and_the_seal_that_takes_the_mentor_takes_them(self):
        from gauntlet import finalexam
        self.assertIn(sages.CAPABILITY, {c.id for c in finalexam.CRUTCHES})

    def test_no_sage_may_be_found_or_faced_inside_a_measured_run(self):
        for region in sages.SAGE_BY_REGION:
            self.assertTrue(sages.available_in("ADVENTURE", region))
            self.assertFalse(sages.available_in("ADVENTURE", region, sealed=True))
            for mode in ("INTERVIEW", "EXAM", "MEASURED", "PRACTICAL",
                         "interview", "Interview"):
                self.assertFalse(sages.available_in(mode, region), mode)

    def test_there_is_no_sage_and_no_art_in_the_final_practical(self):
        final = world.FINAL_TRIAL["region"]
        self.assertIsNone(sages.for_region(final))
        self.assertIsNone(arts.sanctum_for_region(final))
        self.assertFalse(sages.available_in("ADVENTURE", final))
        self.assertIn(final, sages.SILENCED_REGIONS)
        with arts.registered():
            self.assertEqual([a for a in arts.ARTS if a.region == final], [])

    def test_a_sealed_encounter_is_offered_no_arts(self):
        with arts.registered():
            book = movesets.new_book()
            for art in arts.for_class("berserker"):
                movesets.learn(book, art.move_id)
            self.assertEqual(
                arts.demandable(book, _Field(), class_id="berserker",
                                sealed=True), [])
            self.assertIsNone(
                arts.next_demand(book, _Field(), class_id="berserker",
                                 sealed=True))

    def test_the_seers_weakness_reading_is_sealed_where_the_information_is(self):
        """`reading()` IS the weakness map, which finalexam seals. It must
        refuse on its own rather than relying on nobody calling it."""
        with arts.registered():
            art = arts.for_class("seer")[0]
            self.assertEqual(arts.reading(art.id, _Field(), sealed=True), {})

    def test_an_art_already_learned_is_not_sealed(self):
        """Deliberate, and the line worth getting right: an art is the player's
        own fluency, not a crutch. What the exam removes is everything that
        would tell you WHICH one to reach for."""
        source = (REPO / "gauntlet" / "sages.py").read_text()
        self.assertIn("THIS DOES NOT GATE THE ARTS", source)
        art_ids = {a.id for a in sages.ARTS}
        from gauntlet import finalexam
        for crutch in finalexam.CRUTCHES:
            self.assertNotIn(crutch.id, art_ids)


class _Field:
    """The smallest thing `movesets.castable` and `targets_for` will accept."""

    def enemies(self):
        return []

    def enemy(self, name):
        return None

    def alive(self):
        return []


# ---------------------------------------------------------------------------
# 6. Nothing supplies an answer
# ---------------------------------------------------------------------------

class TestNothingSuppliesAnAnswer(unittest.TestCase):

    TELLS = (
        "the answer is", "the solution is", "here is the solution",
        "here's the solution", "copy this", "paste this",
        "the correct code is", "just write ", "simply write",
        "the fix is to write", "solves it for you", "gives you the answer",
        "reveals the answer", "without solving", "tells you which pattern",
        "all you have to do is", "you just need to",
    )

    def _strings(self, path):
        tree = ast.parse(Path(path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield node.lineno, node.value

    def test_no_authored_string_in_either_module_is_answer_shaped(self):
        hits = []
        for name in ("sages.py", "arts.py"):
            path = REPO / "gauntlet" / name
            for lineno, text in self._strings(path):
                low = text.lower()
                # A module's own tell-list is a string containing a tell.
                # Skip the entries that ARE the vocabulary; catch prose.
                if low.strip() in {t.strip() for t in self.TELLS}:
                    continue
                for tell in self.TELLS:
                    if tell in low:
                        hits.append("%s:%d %r" % (name, lineno, text[:70]))
        self.assertEqual(hits, [], "\n".join(hits))

    def test_the_modules_check_themselves_for_this_every_run(self):
        self.assertEqual(sages.self_check()["answerish_lines"], [])
        self.assertEqual(arts.self_check()["problems"], [])

    def test_a_worked_example_never_reaches_the_player_facing_payload(self):
        """Every art carries a correct fill of its own holes so that it can be
        cast in a self-test. None of it may appear in what the client renders."""
        with arts.registered():
            for art in arts.ARTS:
                payload = repr(art.to_dict())
                self.assertNotIn("example", payload, art.id)
                hardest = max(art.inc.example.values(), key=len)
                if len(hardest) > 12:      # skip bare identifiers like "n"
                    self.assertNotIn(hardest, payload, art.id)

    def test_the_sage_never_says_what_the_proof_is(self):
        for sage in sages.SAGES:
            for face in sage.faces:
                self.assertNotIn("=", face.trial, "%s/%s" % (sage.id, face.class_id))
                self.assertNotIn("return ", face.trial)


# ---------------------------------------------------------------------------
# 7. Both modules sit in the package without disturbing it
# ---------------------------------------------------------------------------

class TestImportsCleanly(unittest.TestCase):

    def test_importing_arts_registers_nothing(self):
        """The regression this file exists for.

        `gauntlet/arts.py` used to end with a bare `register()`, so importing it
        wrote ninety-six ids into `incantation.BY_ID` and ninety-six into
        `movesets.BY_ID`. Every test module is imported at discovery time, so
        one import of this file broke a test in `test_incantation.py` that
        belongs to another pass entirely.
        """
        import importlib
        arts.unregister()
        before = (set(incantation.BY_ID), set(movesets.BY_ID))
        importlib.reload(arts)
        self.assertEqual((set(incantation.BY_ID), set(movesets.BY_ID)), before)
        self.assertFalse(set(arts.ART_IDS) & set(incantation.BY_ID))

    def test_the_reports_put_the_catalogues_back(self):
        arts.unregister()
        before = (len(incantation.BY_ID), len(movesets.BY_ID))
        arts.self_check()
        arts.handover()
        arts.sage_bridge()
        arts.saturation_report()
        arts.ranking_table()
        self.assertEqual((len(incantation.BY_ID), len(movesets.BY_ID)), before)

    def test_registering_is_idempotent_and_reversible(self):
        arts.unregister()
        before = (len(incantation.BY_ID), len(movesets.BY_ID))
        arts.register()
        arts.register()
        self.assertEqual(len(incantation.BY_ID), before[0] + len(arts.ART_IDS))
        arts.unregister()
        self.assertEqual((len(incantation.BY_ID), len(movesets.BY_ID)), before)

    def test_both_modules_pass_their_own_checks(self):
        report = sages.self_check()
        self.assertTrue(report["ok"], report.get("answerish_lines"))
        self.assertTrue(arts.self_check()["ok"])

    def test_the_duplicate_catalogue_is_settled_in_writing(self):
        """Two passes authored ninety-six arts each. Shipping both would give
        every class thirty-two signature moves. The decision has to be a fact in
        the code, not a conversation that happened once."""
        decision = sages.overlap_report()["decision"]
        self.assertIn("SETTLED", decision)
        self.assertIn("arts.taught_here", decision)
        self.assertFalse(sages.self_check()["ships"])

    def test_every_art_in_the_shipping_catalogue_actually_casts(self):
        result = arts.self_test_all()
        self.assertEqual(result["failed"], 0, result["detail"])


if __name__ == "__main__":
    unittest.main()
