"""Typed combat: the catalogue, the three failure layers, the scaffold, and the
promise that a wrong cast costs the turn and nothing else.

These tests do not build the corpus, so they subclass TestCase directly and lean
on base.py only for the repo path. Casting is real — every semantic check below
runs the line in the sandbox, because a test that stubbed that out would be
testing the stub.
"""
from __future__ import annotations

import base  # noqa: F401  - puts the repo on sys.path
import re
import unittest
from pathlib import Path

from gauntlet import arts, bestiary, incantation

REPO = Path(__file__).resolve().parent.parent


# One winning cast per chapter, lifted from a sweep of every authored fight and
# pinned here so winnability is proved by CASTING rather than by a table lookup.
# (encounter id, [(enemy, incantation, answers)])
WINNING_CASTS = (
    ("enc_first_loop", [
        ("items", "gather", {"store": "items", "item": "word"}),
        ("total", "toll", {"total": "total", "seq": "items", "index": "i"}),
    ]),
    ("enc_hollow_set", [
        ("seen", "mark", {"store": "seen", "item": "x"}),
        ("items", "gather", {"store": "items", "item": "word"}),
    ]),
    ("enc_tally_wraith", [
        ("counts", "tally", {"book": "counts", "key": "ch"}),
        ("seen", "mark", {"store": "seen", "item": "x"}),
    ]),
    ("enc_two_that_sum", [
        ("target", "bind", {"target": "target", "value": "len(nums)"}),
        ("seen", "mark", {"store": "seen", "item": "x"}),
    ]),
    ("enc_twin_wardens", [
        ("left", "advance", {"counter": "left"}),
        ("right", "advance", {"counter": "right"}),
    ]),
    ("enc_cart_tower", [
        ("stack", "gather", {"store": "stack", "item": "word"}),
        ("i", "advance", {"counter": "i"}),
    ]),
    ("enc_branching_warden", [
        ("node", "branch", {"node": "node", "side": "left"}),
        ("depth", "floor", {"n": "depth"}),
    ]),
    ("enc_ash_ward", [
        ("grid", "cell", {"value": "out", "grid": "grid", "r": "i", "c": "i"}),
        ("visited", "mark", {"store": "visited", "item": "x"}),
    ]),
    ("enc_paid_once", [
        ("memo", "enshrine", {"memo": "memo", "key": "n", "result": "x"}),
        ("depth", "floor", {"n": "depth"}),
    ]),
    ("enc_unchecked_argument", [
        ("off_by_one", "narrow", {"left": "off_by_one", "mid": "hi"}),
        ("hi", "halve", {"mid": "out", "left": "hi", "right": "off_by_one"}),
    ]),
    ("enc_nothing_labelled", [
        ("answer", "bind", {"target": "answer", "value": "len(nums)"}),
        ("seen", "mark", {"store": "seen", "item": "x"}),
    ]),
)


class TestCatalogue(unittest.TestCase):
    """The catalogue has to be internally true before anything else matters."""

    def test_every_incantation_passes_its_own_self_test(self):
        report = incantation.self_test_all()
        self.assertEqual(report["failed"], 0,
                         "incantations that cannot cast their own example: %s"
                         % report["detail"])
        self.assertGreaterEqual(report["total"], 60)

    def test_ids_are_unique_and_holes_are_declared(self):
        ids = [i.id for i in incantation.CATALOGUE]
        self.assertEqual(len(ids), len(set(ids)), "duplicate incantation id")
        for inc in incantation.CATALOGUE:
            declared = {h.name for h in inc.holes}
            self.assertEqual(declared, set(incantation.holes_in(inc.template)),
                             "%s declares holes its template does not have" % inc.id)
            for hole in inc.holes:
                self.assertIn(hole.kind, incantation.HOLE_KINDS)
                self.assertTrue(hole.role, "%s.%s has no role" % (inc.id, hole.name))

    def test_every_incantation_has_an_example_for_every_hole(self):
        for inc in incantation.CATALOGUE:
            for hole in inc.holes:
                self.assertIn(hole.name, inc.example,
                              "%s has no example fill for {%s}" % (inc.id, hole.name))

    def test_member_holes_declare_what_is_allowed(self):
        for inc in incantation.CATALOGUE:
            for hole in inc.holes:
                if hole.kind == incantation.MEMBER:
                    self.assertTrue(hole.allowed,
                                    "%s.%s is a member hole with no shortlist"
                                    % (inc.id, hole.name))


class TestBestiaryAgreement(unittest.TestCase):
    """bestiary.py mirrors the catalogue. The mirror must not have drifted."""

    def test_bestiary_verifies(self):
        report = bestiary.verify()
        self.assertTrue(report["ok"], "bestiary problems: %s" % report["problems"])

    def test_every_referenced_incantation_exists(self):
        missing = sorted(bestiary.referenced_incantations() - set(incantation.BY_ID))
        self.assertEqual(missing, [], "referenced but not in the catalogue")

    def test_contract_mirror_has_not_drifted(self):
        for inc_id, row in bestiary.EXPECTED_INCANTATIONS.items():
            inc = incantation.BY_ID.get(inc_id)
            self.assertIsNotNone(inc, "%s is in the contract, not the catalogue" % inc_id)
            self.assertEqual(row[2], inc.template, "%s template drifted" % inc_id)
            self.assertEqual(bestiary.chapter_rank(row[0]), inc.chapter,
                             "%s chapter drifted" % inc_id)
            self.assertEqual(row[1], inc.skill, "%s skill drifted" % inc_id)
        # MINUS THE SECRET ARTS, and this is the edit arts.handover() asked for
        # by name. `incantation.BY_ID` is a REGISTRY and `bestiary`'s mirror is
        # a contract about the ORDINARY catalogue: engine.py calls
        # arts.register() at import, which puts ninety-six art lines into BY_ID
        # and deliberately not into `incantation.CATALOGUE`, so nothing can ever
        # hand one out as a clear reward. This assertion is still the drift
        # guard it always was — it just names the one registry that is allowed
        # to be wider than the catalogue.
        self.assertEqual(set(bestiary.EXPECTED_INCANTATIONS),
                         set(incantation.BY_ID) - arts.ART_IDS,
                         "the two catalogues do not hold the same ids")

    def test_every_enemy_name_is_a_python_identifier(self):
        for enemy in bestiary.ENEMIES:
            self.assertTrue(enemy.id.isidentifier(), enemy.id)

    def test_battle_context_builds_for_every_fight(self):
        for enc in bestiary.ENCOUNTERS:
            ctx = bestiary.battle_context(enc)
            self.assertTrue(ctx.enemies, "%s fielded nothing" % enc.id)
            for enemy in ctx.enemies:
                self.assertIn(enemy.name, ctx.names())
                self.assertTrue(enemy.binding, "%s has no binding" % enemy.name)
        for boss in bestiary.BOSSES:
            for phase in boss.phases:
                self.assertTrue(bestiary.battle_context(phase).enemies)

    def test_the_client_template_agrees_with_the_holes(self):
        """web/js/incantui.js parses {{name}} holes and shares one slot per NAME.

        The count it arrives at has to be the number of answers cast() wants,
        or a repeated variable becomes several blanks that mean nothing.
        """
        named = re.compile(r"\{\{([^}]*)\}\}")
        for inc in incantation.CATALOGUE:
            slots = []
            for name in named.findall(incantation.client_template(inc.template)):
                if name not in slots:
                    slots.append(name)
            self.assertEqual(slots, [h.name for h in inc.holes],
                             "%s renders different holes than it grades" % inc.id)


class TestFailureLayers(unittest.TestCase):
    """Three ways to be wrong, and the player is always told which one."""

    def field(self):
        return bestiary.battle_context("enc_hollow_set")

    def test_syntax_failure_names_the_parse_and_not_the_answer(self):
        result = incantation.cast("mark", {"store": "seen", "item": "(5"}, self.field())
        self.assertFalse(result.correct)
        self.assertEqual(result.layer, "syntax")
        self.assertTrue(result.teaching)
        self.assertNotIn("seen.add", result.teaching)

    def test_binding_failure_names_the_unbound_name(self):
        result = incantation.cast("mark", {"store": "ghost", "item": "x"}, self.field())
        self.assertFalse(result.correct)
        self.assertEqual(result.layer, "binding")
        self.assertIn("ghost", result.teaching)
        self.assertNotIn("seen.add", result.teaching)

    def test_semantic_failure_names_what_broke_when_it_ran(self):
        """Real Python, real names, wrong structure: a list has no .add."""
        result = incantation.cast("mark", {"store": "items", "item": "x"}, self.field())
        self.assertFalse(result.correct)
        self.assertEqual(result.layer, "semantics")
        self.assertTrue(result.teaching)
        self.assertNotIn("seen.add", result.teaching)

    def test_a_blank_is_not_a_cast(self):
        result = incantation.cast("mark", {"store": "seen", "item": ""}, self.field())
        self.assertFalse(result.correct)
        self.assertEqual(result.layer, "blank")

    def test_no_failure_line_ever_contains_the_correct_line(self):
        ctx = self.field()
        answer = incantation.assemble("mark", {"store": "seen", "item": "x"})
        for answers in ({"store": "seen", "item": "(5"},
                        {"store": "ghost", "item": "x"},
                        {"store": "items", "item": "x"}):
            result = incantation.cast("mark", answers, ctx)
            self.assertFalse(result.correct)
            self.assertNotIn(answer, result.teaching)
            self.assertNotIn(answer, result.detail)

    def test_interview_mode_withholds_the_teaching(self):
        """Adventure teaches, Timed Practical measures. The layer is still named."""
        ctx = bestiary.battle_context("enc_hollow_set", mode="interview")
        result = incantation.cast("mark", {"store": "ghost", "item": "x"}, ctx)
        self.assertFalse(result.correct)
        self.assertEqual(result.layer, "binding")
        self.assertTrue(result.teaching_withheld)
        self.assertNotIn("ghost", result.detail)


class TestWastedTurn(unittest.TestCase):
    """The Blitz rule: a wrong sequence wastes the turn. It costs nothing more."""

    def test_a_wrong_cast_deals_no_damage_and_leaves_every_enemy_standing(self):
        ctx = bestiary.battle_context("enc_hollow_set")
        before = {e.name: e.hp for e in ctx.enemies}
        result = incantation.cast("mark", {"store": "items", "item": "x"}, ctx)
        self.assertFalse(result.correct)
        self.assertTrue(result.turn_wasted)
        self.assertEqual(result.damage, 0)
        self.assertEqual({e.name: e.hp for e in ctx.enemies}, before,
                         "a failed cast changed the battlefield")

    def test_a_wrong_cast_does_not_change_the_vocabulary(self):
        ctx = bestiary.battle_context("enc_hollow_set")
        before = ctx.bindings()
        incantation.cast("mark", {"store": "ghost", "item": "x"}, ctx)
        self.assertEqual(ctx.bindings(), before)

    def test_a_wrong_cast_is_never_free_and_never_fatal(self):
        """It costs the turn. It does not cost HP, items or progress."""
        ctx = bestiary.battle_context("enc_hollow_set")
        result = incantation.cast("mark", {"store": "items", "item": "x"}, ctx)
        self.assertTrue(result.turn_wasted)
        self.assertEqual(result.damage, 0)
        self.assertLessEqual(min(result.skill_deltas.values(), default=0), 0)
        self.assertTrue(result.teaching, "a wasted turn must still teach")

    def test_a_correct_cast_costs_the_turn_nothing(self):
        ctx = bestiary.battle_context("enc_hollow_set")
        result = incantation.cast("mark", {"store": "seen", "item": "x"}, ctx)
        self.assertTrue(result.correct, result.teaching)
        self.assertFalse(result.turn_wasted)
        self.assertGreater(result.damage, 0)


class TestScaffoldFade(unittest.TestCase):
    """The scaffold is a dial moved by evidence, and it turns BOTH ways."""

    NOW = 1_700_000_000.0

    def stats(self, **kw):
        kw.setdefault("last_correct_at", self.NOW)
        return incantation.CastStats(incantation="mark", **kw)

    def tier(self, stats, mastery=80):
        return incantation.tier_for({"mastery": mastery}, stats,
                                    now=self.NOW, par_seconds=20.0)

    def test_a_cold_move_gets_the_whole_line(self):
        self.assertEqual(self.tier(self.stats(casts=0)), 0)
        self.assertEqual(incantation.tier_for({"mastery": 80}, None), 0)

    def test_the_scaffold_rises_with_demonstrated_fluency(self):
        rungs = [
            self.tier(self.stats(casts=2, correct=2, streak=2, best_streak=2,
                                 seconds=[10, 10])),
            self.tier(self.stats(casts=5, correct=5, streak=4, best_streak=4,
                                 seconds=[12] * 5)),
            self.tier(self.stats(casts=9, correct=9, streak=6, best_streak=6,
                                 seconds=[18] * 8)),
        ]
        self.assertEqual(rungs, [1, 2, 3])

    def test_being_correct_but_slow_does_not_buy_the_top_rung(self):
        """Fluency is correctness AND speed; the timer is evidence, not a gate."""
        slow = self.tier(self.stats(casts=9, correct=9, streak=6, best_streak=6,
                                    seconds=[40] * 8))
        self.assertLess(slow, 3)

    def test_the_scaffold_falls_one_rung_for_every_miss_in_a_row(self):
        fluent = dict(casts=9, correct=9, best_streak=6, seconds=[18] * 8)
        fallen = [self.tier(self.stats(**fluent, miss_streak=n)) for n in range(4)]
        self.assertEqual(fallen, [3, 2, 1, 0])
        for earlier, later in zip(fallen, fallen[1:]):
            self.assertLessEqual(later, earlier)

    def test_the_scaffold_falls_as_the_memory_ages(self):
        fluent = dict(casts=9, correct=9, streak=6, best_streak=6, seconds=[18] * 8)
        fresh = self.tier(self.stats(**fluent))
        week = self.tier(self.stats(**dict(fluent,
                                           last_correct_at=self.NOW - 6 * 86400)))
        month = self.tier(self.stats(**dict(fluent,
                                            last_correct_at=self.NOW - 30 * 86400)))
        self.assertEqual(fresh, 3)
        self.assertLess(week, fresh)
        self.assertLess(month, week)

    def test_typing_speed_cannot_outrun_comprehension(self):
        drilled = self.stats(casts=20, correct=20, streak=12, best_streak=12,
                             seconds=[8] * 8)
        self.assertLessEqual(self.tier(drilled, mastery=10), 1)
        self.assertLessEqual(self.tier(drilled, mastery=40), 2)
        self.assertEqual(self.tier(drilled, mastery=90), 3)

    def test_recorded_misses_actually_move_the_dial_back(self):
        """The same object, driven through success and then failure."""
        stats = incantation.CastStats(incantation="mark")
        for _ in range(9):
            stats.record(correct=True, seconds=12.0, now=self.NOW)
        risen = self.tier(stats)
        self.assertGreaterEqual(risen, 2)
        stats.record(correct=False, layer="semantics", now=self.NOW)
        stats.record(correct=False, layer="semantics", now=self.NOW)
        self.assertLess(self.tier(stats), risen)

    def test_every_tier_renders_something_the_player_can_act_on(self):
        ctx = bestiary.battle_context("enc_hollow_set")
        for tier in range(incantation.MAX_TIER + 1):
            view = incantation.render_template("mark", tier, context=ctx)
            self.assertEqual(view["tier"], tier)
            self.assertTrue(view["prompt"])
            self.assertTrue(view["template"], "the client was sent nothing to draw")
            if tier < incantation.MAX_TIER:
                self.assertTrue(view["ghost"])
            else:
                self.assertTrue(view["free_text"])


class TestWinnable(unittest.TestCase):
    """Every authored fight can actually be won with the moveset it assumes."""

    def test_every_enemy_has_a_weakness_the_chapter_has_taught(self):
        for enc in bestiary.ENCOUNTERS:
            available = bestiary.incantations_available(enc.chapter)
            for eid in enc.enemies:
                weak = set(bestiary.ENEMY_BY_ID[eid].weak_to) & available
                self.assertTrue(weak, "%s: %s has no taught weakness"
                                % (enc.id, eid))

    def test_every_weakness_can_be_cast_where_the_enemy_stands(self):
        """Arity and type, not just the weakness table.

        NARROW names two enemies and wants two NUMBERS: listing it against a
        creature standing alone beside a list is a fight that cannot be won.
        """
        for enc in bestiary.ENCOUNTERS:
            problems: list = []
            bestiary._check_strikes(problems, enc.id, list(enc.enemies),
                                    bestiary.incantations_available(enc.chapter))
            self.assertEqual(problems, [])
        for boss in bestiary.BOSSES:
            for phase in boss.phases:
                problems = []
                bestiary._check_strikes(
                    problems, "%s/%s" % (boss.id, phase.key), list(phase.enemies),
                    bestiary.incantations_available(boss.chapter))
                self.assertEqual(problems, [])

    def test_a_real_cast_lands_on_every_chapter(self):
        """One fight per chapter, cast for real through the sandbox."""
        for enc_id, rows in WINNING_CASTS:
            for enemy_id, move, answers in rows:
                ctx = bestiary.battle_context(enc_id)
                self.assertIn(move, bestiary.incantations_available(
                    bestiary.ENCOUNTER_BY_ID[enc_id].chapter),
                    "%s is not taught by %s" % (move, enc_id))
                result = incantation.cast(move, answers, ctx)
                self.assertTrue(result.correct,
                                "%s/%s: %s failed at %s — %s"
                                % (enc_id, enemy_id, move, result.layer,
                                   result.teaching))
                self.assertEqual(result.target, enemy_id)
                self.assertGreater(result.damage, 0)

    def test_a_fight_can_be_driven_to_zero(self):
        """Repetition is the mechanic: the same cast, until the thing falls."""
        ctx = bestiary.battle_context("enc_hollow_set")
        seen = ctx.enemy("seen")
        casts = 0
        while seen.alive and casts < 60:
            result = incantation.cast("mark", {"store": "seen", "item": "x"}, ctx)
            self.assertTrue(result.correct, result.teaching)
            casts += 1
        self.assertFalse(seen.alive, "seen never fell")
        self.assertGreaterEqual(casts, 2, "a battle that short teaches nothing")

    def test_fights_are_long_enough_to_rehearse_and_short_enough_to_finish(self):
        for enc in bestiary.ENCOUNTERS:
            budget = bestiary.cast_budget(enc)
            self.assertGreaterEqual(budget["slow"], bestiary.MIN_CASTS, enc.id)
            self.assertLessEqual(budget["slow"], bestiary.MAX_CASTS, enc.id)

    def test_fights_field_several_kinds_at_once(self):
        """Interleaving is the point: discriminate, then execute."""
        for enc in bestiary.ENCOUNTERS:
            types = {bestiary.ENEMY_BY_ID[e].type for e in enc.enemies}
            self.assertGreaterEqual(len(enc.enemies), 2, enc.id)
            self.assertGreaterEqual(len(types), 2, enc.id)


class TestSandboxOnly(unittest.TestCase):
    """Player text runs in one place. This is the finding that would be a defect."""

    SOURCES = ("gauntlet/incantation.py", "gauntlet/bestiary.py")

    def test_no_module_executes_player_text_in_process(self):
        banned = re.compile(r"(?<![\w.])(exec|eval)\s*\(")
        for name in self.SOURCES:
            source = (REPO / name).read_text(encoding="utf-8")
            code = "\n".join(line for line in source.splitlines()
                             if not line.lstrip().startswith("#"))
            hits = banned.findall(code)
            self.assertEqual(hits, [], "%s calls %s on live code" % (name, hits))

    def test_compile_is_never_used_on_a_cast(self):
        """re.compile is fine. compile() of player text is not."""
        for name in self.SOURCES:
            source = (REPO / name).read_text(encoding="utf-8")
            for number, line in enumerate(source.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for match in re.finditer(r"(?<![\w.])compile\s*\(", line):
                    prefix = line[:match.start()]
                    self.assertTrue(prefix.rstrip().endswith("re."),
                                    "%s:%d compiles something that is not a "
                                    "regex" % (name, number))

    def test_the_semantic_layer_goes_through_the_sandbox(self):
        import gauntlet.sandbox as sandbox
        calls = []
        original = sandbox.run_tests

        def spy(*args, **kw):
            calls.append(args[0])
            return original(*args, **kw)

        sandbox.run_tests = spy
        try:
            ctx = bestiary.battle_context("enc_hollow_set")
            incantation.cast("mark", {"store": "seen", "item": "x"}, ctx)
        finally:
            sandbox.run_tests = original
        self.assertEqual(len(calls), 1, "a cast did not reach the sandbox")
        self.assertIn("seen.add(x)", calls[0])

    def test_ast_parsing_never_evaluates(self):
        """Layers 1 and 2 read the line as a tree. Reading is not running."""
        ctx = bestiary.battle_context("enc_hollow_set")
        marker = REPO / "tests" / "__incantation_side_effect__"
        line = "__import__('pathlib').Path(%r).write_text('x')" % str(marker)
        result = incantation.cast("mark", {"store": "seen", "item": line}, ctx)
        self.addCleanup(lambda: marker.exists() and marker.unlink())
        self.assertFalse(result.correct)
        self.assertFalse(marker.exists(),
                         "a cast reached the real filesystem from this process")


if __name__ == "__main__":
    unittest.main(verbosity=2)
