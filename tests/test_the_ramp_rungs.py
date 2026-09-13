"""The ramp, as four rungs of one problem.

The player asked for multiple choice, then complete-the-argument, then fill-in-
the-blanks, then write it all — heaviest at the bottom and tapering as the
difficulty rises. Measured before this, the corpus went 93.5% scaffolded at
GUIDED to 3.5% at TUTORIAL: a ninety-point cliff in one step, with the middle
rung — "complete the argument" — existing 123 times at GUIDED and zero times in
every band above it.

The fix is not new problems. A rung is a way of DISPLAYING a problem, generated
from one declaration of which span of its own canonical solution carries the
idea. These tests hold the two properties that buys, because both of them are
properties somebody could quietly lose:

    THE HOLD-OUT DOES NOT MOVE. Nothing was created, so `seal_holdout` receives
    the same input and produces the same 122 ids.

    A SCAFFOLDED CLEAR IS NOT EVIDENCE OF MASTERY. Not by convention — by
    arithmetic, because the rung is recorded from what the player was shown.
"""
from __future__ import annotations

import ast
import unittest

import base
from gauntlet import curriculum, scaffold, skills as skillmod, srs as srsmod


class TestTheDeclarations(base.GameTest):

    def test_every_declaration_describes_its_own_canonical_solution(self):
        """The check `starter_code` never had.

        214 hand-maintained blanked starters shipped with nothing verifying that
        filling the blanks back in reproduced the answer. Here it is verified.
        """
        for problem in self.corpus:
            if not problem.scaffold_spans:
                continue
            spans = scaffold.normalise(problem.scaffold_spans,
                                       problem.canonical_solution)
            self.assertTrue(
                scaffold.round_trip(problem, spans),
                f"{problem.id}: filling every declared span with its own text "
                f"does not reproduce the canonical solution")

    def test_every_blank_has_a_sentence_beside_it(self):
        """The numbered comments are the teaching, not decoration around it."""
        for problem in self.corpus:
            for index, span in enumerate(problem.scaffold_spans or ()):
                self.assertTrue(
                    (span.get("gloss") or "").strip(),
                    f"{problem.id} span {index} ({span.get('text')!r}) has no "
                    f"gloss; a blank with no sentence beside it is a guessing "
                    f"game, not a teaching step")

    def test_the_hold_out_carries_no_scaffolding_at_all(self):
        """A sealed problem is never served by the teaching side at any rung, so
        a declaration on it is inert — and an inert declaration is the kind of
        thing that later gets tidied into a served one. Eight sealed problems
        shipped with a hand-blanked starter; the build now strips them."""
        for problem in self.corpus:
            if problem.sealed:
                self.assertEqual(
                    problem.scaffold_spans, [],
                    f"sealed problem {problem.id} carries a scaffold declaration")

    def test_no_declaration_lands_on_a_sealed_lineage(self):
        """A new variant of a sealed problem's lineage would be a leak of a
        sealed problem. No variant exists — but the hand-authored table is the
        one place somebody could later add one, so it is checked by name."""
        sealed = {p.lineage_id for p in self.corpus if p.sealed}
        for problem in self.corpus:
            if not problem.scaffold_spans:
                continue
            self.assertNotIn(
                problem.lineage_id, sealed,
                f"{problem.id} carries a scaffold on a sealed lineage")

    def test_every_rendered_rung_is_still_python(self):
        """`__BLANK__` is a bare name on purpose: a player who runs the starter
        untouched gets a NameError naming the rune they still owe, not a
        SyntaxError pointing at column one."""
        for problem in self.corpus:
            if not problem.scaffold_spans:
                continue
            for rung in scaffold.available_rungs(problem):
                # RUNG 4 INCLUDED, for a scaffoldable problem. It used to be
                # skipped as "the authored starter, which is not ours" — but
                # `skeleton()` passes the authored starter straight through for
                # 533 of the 746 editor-axis problems, so it IS ours, and that
                # exemption is what let `oopl-except-order-tutorial` ship a
                # rung 4 raising "expected 'except' or 'finally' block" at
                # column one. Rung 4 is what MEDIUM, HARD, Interview Mode, the
                # practical and the hold-out serve unconditionally.
                rendered = scaffold.render(problem, rung)
                try:
                    ast.parse(rendered["starter_code"])
                except SyntaxError as exc:
                    self.fail(f"{problem.id} at rung {rung} does not parse: {exc}"
                              f"\n{rendered['starter_code']}")

    def test_rung_one_offers_the_right_answer_and_three_wrong_ones(self):
        """`or not rendered["choices"]` used to sit in this guard, and it skipped
        on exactly the condition that IS the failure: the 55 problems whose rung
        1 rendered `{"rung": 1, "name": "PICK", "choices": []}` were stepped over
        in silence, which is why that shipped inside a green suite. The rung
        check is a legitimate skip — a problem that cannot render rung 1 falls UP
        to rung 2 and says so. An empty choices list is not."""
        for problem in self.corpus:
            if not problem.scaffold_spans:
                continue
            rendered = scaffold.render(problem, scaffold.PICK)
            if rendered["rung"] != scaffold.PICK:
                self.assertNotIn(
                    scaffold.PICK, scaffold.available_rungs(problem),
                    f"{problem.id}: render fell off rung 1 but available_rungs "
                    f"still offers it, so servable() can still select it")
                continue
            right = scaffold.normalise(problem.scaffold_spans,
                                       problem.canonical_solution)[0]["text"].strip()
            self.assertGreaterEqual(
                len(rendered["choices"]), 2,
                f"{problem.id}: rung 1 rendered a multiple choice with "
                f"{len(rendered['choices'])} options")
            self.assertIn(right, rendered["choices"],
                          f"{problem.id}: rung 1 does not offer the right token")

    def test_a_rung_the_ladder_offers_is_a_rung_it_can_render(self):
        """The ladder must tell the truth about what it can render, because
        `servable` reads `available_rungs` and `skills.apply_outcome` files the
        clear under the rung `servable` returned. 55 problems offered PICK on
        span count alone while `choices_for` had nothing to offer, so the player
        was shown an ordinary one-blank — byte-identical to the rung-2 render —
        and credited at rung 1, which does not count toward leaving rung 2."""
        for problem in self.corpus:
            for rung in scaffold.available_rungs(problem):
                rendered = scaffold.render(problem, rung)
                self.assertEqual(
                    rendered["rung"], rung,
                    f"{problem.id}: available_rungs offers rung {rung} and "
                    f"render serves rung {rendered['rung']} instead")
                if rung == scaffold.PICK:
                    self.assertGreaterEqual(len(rendered["choices"]), 2,
                                            f"{problem.id}: a pick with nothing "
                                            f"to pick between")

    def test_the_gloss_is_the_only_sentence_beside_a_blank(self):
        """A comment the author wrote to explain the worked solution, standing
        over a hole cut out of that same solution, hands the answer over.
        `annotate` stripped the struck line's own trailing comment and left the
        comment-only lines above it: `lang-sortkey-tutorial` kept "`key=len`,
        not `key=len(words)`" directly above the blank that wants
        `sorted(words, key=len)`."""
        for problem in self.corpus:
            if not problem.scaffold_spans:
                continue
            for rung in scaffold.available_rungs(problem):
                if rung == scaffold.WRITE_IT_ALL:
                    continue
                rows = scaffold.render(problem, rung)["starter_code"].split("\n")
                for index, row in enumerate(rows):
                    if scaffold.MARKER not in row or index == 0:
                        continue
                    above = rows[index - 1].strip()
                    self.assertFalse(
                        above.startswith("#"),
                        f"{problem.id} rung {rung}: {above!r} is left standing "
                        f"over a blank")

    def test_no_gloss_is_numbered_twice(self):
        """`_gloss_above` read a comment line back into a declaration without
        taking off the numbering the author had already written, and `annotate`
        prepended a second one: "# 1. 1. Counter counts whatever you iterate."
        All 21 were the py-*-guided stdlib block."""
        numbered = __import__("re").compile(r"^\d+\.\s")
        for problem in self.corpus:
            for index, span in enumerate(problem.scaffold_spans or ()):
                self.assertIsNone(
                    numbered.match((span.get("gloss") or "").strip()),
                    f"{problem.id} span {index} stores a pre-numbered gloss "
                    f"{span.get('gloss')!r}; annotate will number it again")

    def test_a_span_never_strikes_inside_a_longer_name(self):
        """`ob-dict-store` declared `price` and `row.find` handed back the
        `price` inside `prices`, so rung 3 rendered
        `def dict_store(__BLANK__s, ...)`. `round_trip` returns True on that —
        refilling the hole reproduces `prices` — so the one check written to
        catch a stale declaration is structurally unable to see this one."""
        for problem in self.corpus:
            for span in scaffold.normalise(problem.scaffold_spans or [],
                                           problem.canonical_solution):
                row = problem.canonical_solution.split("\n")[span["line"]]
                self.assertTrue(
                    scaffold._boundary_clean(row, span["col"], span["text"]),
                    f"{problem.id}: the span {span['text']!r} was resolved to "
                    f"column {span['col']} of {row!r}, inside a longer name")

    def test_the_choices_do_not_move_when_the_page_is_reloaded(self):
        """A multiple choice reshuffled on every request is a free answer to
        anyone who reloads twice and watches which option moves."""
        for problem in self.corpus[:200]:
            if not problem.scaffold_spans:
                continue
            first = scaffold.render(problem, scaffold.PICK)["choices"]
            second = scaffold.render(problem, scaffold.PICK)["choices"]
            self.assertEqual(first, second, f"{problem.id}: choices reshuffled")


class TestTheFloor(base.GameTest):

    def test_the_floor_is_monotone(self):
        floors = [scaffold.floor_for(band) for band in
                  ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD")]
        self.assertEqual(floors, sorted(floors),
                         "the most help a band offers must never rise with "
                         "difficulty; that is the whole complaint")
        self.assertEqual(floors, [1, 2, 3, 4, 4])

    def test_no_band_is_ever_served_below_its_floor(self):
        for problem in self.corpus:
            floor = scaffold.floor_for(problem.difficulty)
            for desired in scaffold.RUNGS:
                served = scaffold.servable(problem, problem.difficulty, desired)
                self.assertGreaterEqual(
                    served, floor,
                    f"{problem.id} ({problem.difficulty}) served at rung "
                    f"{served}, below its floor of {floor}")

    def test_easy_is_never_served_one_hand_held_blank(self):
        """The live monotonicity violation, excluded structurally: 21 EASY
        problems shipped a scaffold while TUTORIAL above them was a blank
        screen, so the ramp rose exactly where it should have fallen."""
        for problem in self.corpus:
            if problem.difficulty != "EASY":
                continue
            for desired in scaffold.RUNGS:
                self.assertNotEqual(
                    scaffold.servable(problem, "EASY", desired), scaffold.ONE_BLANK,
                    f"{problem.id} is EASY and was served a single blank")

    def test_a_sealed_problem_is_never_served_at_any_rung(self):
        """A rung is a presentation OF a problem, so the seal — which is a
        property of the problem — covers every rung of it."""
        state = skillmod.SkillState(name="PYTHON")
        for problem in self.corpus:
            if not problem.sealed:
                continue
            self.assertEqual(
                curriculum.servable_rung(problem, state), scaffold.WRITE_IT_ALL,
                f"sealed problem {problem.id} was offered a scaffold")

    def test_a_measured_mode_is_always_the_whole_function(self):
        state = skillmod.SkillState(name="PYTHON")
        for problem in self.corpus[:300]:
            for mode in sorted(scaffold.UNSCAFFOLDED_MODES):
                self.assertEqual(
                    curriculum.servable_rung(problem, state, mode=mode),
                    scaffold.WRITE_IT_ALL,
                    f"{problem.id} carried a scaffold into {mode}")


class TestTheEvidence(base.GameTest):
    """A scaffolded clear must not be countable as having written a function."""

    def _state(self, **kw):
        state = skillmod.SkillState(name="PYTHON")
        for key, value in kw.items():
            setattr(state, key, value)
        return state

    def test_filling_in_blanks_forever_never_ends_the_scaffold_band(self):
        state = self._state(clears=40, tier_clears={"TUTORIAL": 40},
                            tier_unaided={"TUTORIAL": 40},
                            rung_clears={"2": 40}, rung_unaided={"2": 40},
                            production_seen=0)
        self.assertFalse(
            curriculum.has_produced_code(state),
            "forty one-blank clears were counted as having written a function")

    def test_one_scaffolded_easy_clear_does_not_end_the_band(self):
        """The live defect this replaces: `tier_unaided == {'EASY': 1}` earned
        by a two-blank MISSING_RUNE ended the scaffold band outright, and the
        corpus contains 21 EASY problems shaped exactly like that."""
        state = self._state(clears=1, tier_clears={"EASY": 1},
                            tier_unaided={"EASY": 1},
                            rung_clears={"3": 1}, rung_unaided={"3": 1},
                            production_seen=1)
        self.assertFalse(curriculum.has_produced_code(state))
        self.assertIsNotNone(curriculum.scaffold_target(state))

    def test_one_blank_screen_clear_at_easy_does_end_it(self):
        state = self._state(clears=1, tier_clears={"EASY": 1},
                            tier_unaided={"EASY": 1},
                            rung_clears={"4": 1}, rung_unaided={"4": 1},
                            production_seen=1, production_unaided=1)
        self.assertTrue(curriculum.has_produced_code(state))

    def test_a_whole_function_at_guided_is_not_the_escape_hatch(self):
        """Rung 4 alone is not the claim. A GUIDED one-liner with no declaration
        is served whole, and counting that as "produced working code on a blank
        screen" put a beginner past the band on encounter two — measured, and
        the first-steps chain went from twelve rungs in forty encounters to
        five before this was separated out."""
        state = self._state(clears=6, tier_clears={"GUIDED": 6},
                            tier_unaided={"GUIDED": 6},
                            rung_clears={"4": 6}, rung_unaided={"4": 6})
        self.assertFalse(curriculum.has_produced_code(state))

    def test_the_exemption_does_not_end_on_the_next_encounter(self):
        """THE QUESTION IS "ARE THERE CLEARS OUTSIDE THE RECORD", NOT "IS THE
        RECORD EMPTY". Measured: asking the second question sent a fluent player
        who had skipped the beginner chain back into six rungs of it as soon as
        their first scaffolded clear was filed."""
        state = self._state(clears=2, tier_clears={"EASY": 1, "GUIDED": 1},
                            tier_unaided={"EASY": 1, "GUIDED": 1},
                            rung_clears={"1": 1}, rung_unaided={"1": 1},
                            production_seen=0)
        self.assertTrue(curriculum.has_produced_code(state))

    def test_answering_a_multiple_choice_is_not_producing_code(self):
        """`production_seen` was incremented inside `if rung:` while
        `tier_unaided` was incremented unconditionally, and `engine` passes
        rung=0 for every non-editor encounter — so every unaided EASY-or-harder
        clear of an mcq, a RUNE_ASSEMBLY, a DEBUG_BATTLE, a BREAK_IT, a
        REFACTOR_QUEST or a TEST_FORGE grew one side of
        `curriculum.untracked_production` and not the other, and the difference
        was read as evidence from a pre-rung save.

        Measured live: one correct answer to `cr-mutable-default`, an EASY
        CODE_READING multiple choice, flipped `has_produced_code` False -> True
        and moved the difficulty target from GUIDED to EASY."""
        state = skillmod.SkillState(name="ARRAY")
        skillmod.apply_outcome(
            state, solved=True, difficulty="EASY", hints_used=0, seconds=5,
            target_seconds=60, first_try=True, is_retest=False, rung=0)
        self.assertEqual(curriculum.untracked_production(state), 0,
                         "a multiple choice was filed as a pre-rung save's "
                         "worth of untracked production")
        self.assertFalse(curriculum.has_produced_code(state))
        self.assertFalse(curriculum.scaffold_cleared(state))

    def test_a_blank_screen_clear_still_is(self):
        state = skillmod.SkillState(name="ARRAY")
        skillmod.apply_outcome(
            state, solved=True, difficulty="EASY", hints_used=0, seconds=5,
            target_seconds=60, first_try=True, is_retest=False,
            rung=scaffold.WRITE_IT_ALL)
        self.assertTrue(curriculum.has_produced_code(state))

    def test_a_save_with_no_rung_record_is_not_re_judged(self):
        """Absent evidence is not evidence of absence. A player who was
        mid-ramp when this shipped has real clears and no rung record of them,
        and re-judging those would throw them back to the bottom."""
        state = self._state(clears=1, tier_clears={"EASY": 1},
                            tier_unaided={"EASY": 1})
        self.assertTrue(curriculum.has_produced_code(state),
                        "a save from before rungs were recorded was re-judged")

    def test_one_blank_clears_buy_the_next_rung_and_only_the_next(self):
        """Evidence about writing one expression is evidence about writing one
        expression, and none at all about writing a function. The counts come
        from `curriculum.RUNG_EVIDENCE`, which is the curve."""
        import time
        need = curriculum.RUNG_EVIDENCE
        state = self._state(rung_unaided={"2": need[scaffold.ONE_BLANK] - 1},
                            mastery=40, last_seen=time.time())
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL"),
                         scaffold.ONE_BLANK, "one short and it still moved")
        state.rung_unaided = {"2": need[scaffold.ONE_BLANK]}
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL"),
                         scaffold.MANY_BLANKS)
        state.rung_unaided = {"2": need[scaffold.ONE_BLANK],
                              "3": need[scaffold.MANY_BLANKS]}
        state.mastery = 70
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL"),
                         scaffold.WRITE_IT_ALL)

    def test_support_comes_back_one_rung_per_miss_in_a_row(self):
        import time
        need = curriculum.RUNG_EVIDENCE
        state = self._state(rung_unaided={"2": need[2], "3": need[3]}, mastery=70,
                            last_seen=time.time())
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL"), 4)
        state.miss_streak = 1
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL"), 3)
        state.miss_streak = 2
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL"), 2)

    def test_time_away_returns_support_before_the_player_notices(self):
        import time
        now = time.time()
        need = curriculum.RUNG_EVIDENCE
        state = self._state(rung_unaided={"2": need[2], "3": need[3]}, mastery=70,
                            last_seen=now - 6 * 86400)
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL", now=now), 3)
        state.last_seen = now - 20 * 86400
        self.assertEqual(curriculum.rung_for(state, "TUTORIAL", now=now), 2)

    def test_typing_speed_cannot_outrun_comprehension(self):
        import time
        state = self._state(rung_unaided={"2": 99, "3": 99}, mastery=10,
                            last_seen=time.time())
        self.assertLessEqual(curriculum.rung_for(state, "TUTORIAL"),
                             scaffold.ONE_BLANK)


class TestTheBandFloors(base.GameTest):
    """The floors: how much help a band forces onto a player who has earned
    nothing in it.

    This class used to be called TestTheCurve and it used to be the only
    measurement of the taper, which is why the live selector could rise
    79.0 -> 100.0 while the suite stayed green. Its protocol was UNREACHABLE IN
    PLAY — one fresh SkillState per band, walked through that band's own pool in
    sorted-by-id order, accumulating evidence as it went — and it was
    order-sensitive: over 400 random orders of the same pools GUIDED came out
    mean 82.0% (min 72.6) and TUTORIAL mean 69.9% (max 83.1), so the 95.2% it
    reported depended on the pool being walked alphabetically. It also was not
    measuring a floor at all: 62 clears on ONE skill carry that skill off the
    ramp entirely, so most of what it counted was the climb.

    What is kept is the question the protocol can honestly answer, asked without
    the accumulation: given zero evidence, what does each band serve? That is
    the floor, it is monotone by construction, and content drift cannot reach
    it. The curve is measured on the real selector, in TestTheCurve below.
    """

    def _at_the_floor(self, band):
        import collections
        import time
        now = time.time()
        state = skillmod.SkillState(name="PYTHON")
        state.last_seen = now
        counts = collections.Counter()
        for problem in self.corpus:
            if problem.difficulty != band or problem.sealed:
                continue
            if not scaffold.scaffoldable(problem):
                continue
            counts[curriculum.servable_rung(problem, state, now=now)] += 1
        total = sum(counts.values())
        return 100.0 * (counts[1] + counts[2] + counts[3]) / max(1, total), counts

    def test_the_two_bottom_bands_cannot_serve_a_blank_screen_at_the_floor(self):
        """GUIDED and TUTORIAL exist so that a player who cannot type yet is
        never handed nothing. At the floor that is not a target, it is an
        arithmetic consequence of FLOOR — unless the problem's own declaration
        cannot reach the floor, which is the content gap the second spans in
        `corpus/scaffolding.py` closed."""
        for band, least in (("GUIDED", 70.0), ("TUTORIAL", 60.0)):
            share, counts = self._at_the_floor(band)
            self.assertGreater(
                share, least,
                f"{band} hands a blank screen to {100 - share:.1f}% of a player "
                f"who has earned nothing; rungs {dict(counts)}")

    def test_the_floor_falls_band_by_band(self):
        """The whole complaint, asked of the floors alone. 1 <= 2 <= 3 <= 4 <= 4
        is a property of the serving code, so what this measures is whether the
        CONTENT can reach each floor — which is the half that drifts."""
        shares = [self._at_the_floor(band)[0]
                  for band in ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD")]
        for earlier, later in zip(shares, shares[1:]):
            self.assertGreaterEqual(
                earlier, later,
                f"the floors rise: {[round(v, 1) for v in shares]}")
        self.assertEqual(shares[-2:], [0.0, 0.0],
                         "MEDIUM or HARD served a scaffold with no lapse")

    def test_the_middle_rung_exists_outside_guided(self):
        """Rung 2 — "complete the argument" — existed 123 times at GUIDED and
        zero times in every band above it. That absence is the finding this
        whole pass exists to answer."""
        for band in ("TUTORIAL", "EASY", "MEDIUM"):
            servable = [p for p in self.corpus
                        if p.difficulty == band and scaffold.scaffoldable(p)
                        and scaffold.ONE_BLANK in scaffold.available_rungs(p)]
            self.assertGreater(
                len(servable), 0,
                f"{band} has no problem that can be served one blank")


class TestTheCurve(base.GameTest):
    """The taper, measured where the player meets it: the real selector.

    `Game.next_encounter` for 400 encounters on a fresh save, with the rung read
    off the encounter payload the client is actually sent. Nothing is modelled.
    The walk is deterministic and is done once for the class, because it is the
    expensive part and every assertion below is a different question asked of
    the same career.

    WHAT A WHOLE-CAREER BAND AGGREGATE CAN AND CANNOT SAY. Bucketing 400
    encounters by the problem's own band confounds three things: the band, the
    SKILL (evidence is filed per skill, and TWO_POINTER's GUIDED problems arrive
    after it already holds 23 rung-4 clears while TREE's TUTORIAL problems
    arrive when it holds three), and the PHASE OF THE CAREER (the selector keeps
    serving GUIDED problems at encounter 350, by which point PYTHON is fluent
    and a GUIDED fill-in-the-blank would be an insult). Measured over the full
    400 that aggregate reads 61.3 / 71.2 / 49.3 / 0.0 / 0.0 — GUIDED below
    TUTORIAL — and every point of that gap is composition, not ramp: within a
    single skill at a single moment the rung served is NON-DECREASING in
    difficulty for every one of the 241 editor encounters in the career, which
    is what `test_the_taper_never_rises_for_one_player_at_one_moment` asserts
    and is the strongest true form of the claim.

    So the taper is asserted twice, on the same live career: once per encounter,
    where it is exact, and once as a band aggregate over the stretch in which a
    fresh player is being taught the ramp, which is the situation §1b's sentence
    is about ("a player entering the band at the competence the band assumes").
    """

    WALK = 400
    TEACHING_WINDOW = 200
    BANDS = ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD")
    TARGET = {"GUIDED": 95, "TUTORIAL": 70, "EASY": 35, "MEDIUM": 0, "HARD": 0}

    _CAREER = None

    def _career(self):
        """One live career: (index, band, served rung, rungs at every band)."""
        if TestTheCurve._CAREER is not None:
            return TestTheCurve._CAREER
        from gauntlet import puzzles, skills as skills_module
        game = self.game()
        by_id = {p.id: p for p in self.corpus}
        rows = []
        for index in range(self.WALK):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            if scaffold.scaffoldable(problem) and not problem.sealed:
                served = (enc["problem"].get("scaffold") or {}).get("rung")
                skill = skills_module.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
                state = game.skills.get(skill)
                # THE SAME PROBLEM AND THE SAME STATE, JUDGED AT EVERY BAND.
                # Composition-free: one player, one moment, one skill, five
                # answers to "how much help would this band give me".
                at_band = tuple(
                    scaffold.servable(problem, band,
                                      curriculum.rung_for(state, band))
                    for band in self.BANDS)
                rows.append((index, problem.difficulty, served, at_band))
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)
        TestTheCurve._CAREER = rows
        return rows

    @staticmethod
    def _share(rungs):
        rungs = list(rungs)
        return 100.0 * sum(1 for r in rungs if r and r < scaffold.WRITE_IT_ALL) / \
            max(1, len(rungs))

    def _by_band(self, rows):
        return {band: [r[2] for r in rows if r[1] == band] for band in self.BANDS}

    def test_the_taper_never_rises_for_one_player_at_one_moment(self):
        """The taper, stated so that no composition effect can hide it.

        For every editor encounter in a live career, take the skill state in the
        player's hand and ask all five bands how much help they would give. The
        answers must never fall as the difficulty rises. This is the property
        the player asked for — "more prevalent in the lower level, tapering as
        difficulty increases" — and it is exact rather than averaged.
        """
        rows = self._career()
        self.assertGreater(len(rows), 200, "the career served almost no editors")
        for index, band, served, at_band in rows:
            self.assertEqual(
                list(at_band), sorted(at_band),
                f"encounter {index} ({band}): the same player at the same "
                f"moment would be served {dict(zip(self.BANDS, at_band))} — "
                f"the ramp rises")
        shares = [self._share([r[3][i] for r in rows])
                  for i in range(len(self.BANDS))]
        for earlier, later in zip(shares, shares[1:]):
            self.assertGreaterEqual(
                earlier, later,
                f"the ramp rises: {[round(v, 1) for v in shares]}")

    def test_the_taper_never_rises_across_the_bands_as_they_are_taught(self):
        """The band aggregate, over the stretch of a live career in which a
        fresh player is actually being taught the ramp. Measured: 90.9 / 82.1 /
        61.0 / 0.0 / 0.0. Before this pass the same measurement read 100.0 /
        100.0 / 69.2 at 120 encounters and 79.0 / 100.0 / 66.7 over the full
        career — a rise, while the retired per-band model reported 95.2 / 69.5 /
        37.3 and stayed green."""
        rows = [r for r in self._career() if r[0] < self.TEACHING_WINDOW]
        served = self._by_band(rows)
        shares = [self._share(served[band]) for band in self.BANDS if served[band]]
        for earlier, later in zip(shares, shares[1:]):
            self.assertGreaterEqual(
                earlier, later,
                f"the ramp rises: "
                f"{ {b: round(self._share(served[b]), 1) for b in self.BANDS if served[b]} }")

    def test_the_taper_reaches_the_declared_curve(self):
        """§1b's numbers, against the live selector rather than a model.

        The tolerance is wide and says so. §1b names 95 / 70 / 35 / 10 / 0 for
        "a player entering the band at the competence the band assumes"; a live
        400-encounter career is a different population, and the two bands that
        miss do so for reasons that are named rather than tuned away: GUIDED
        because the selector keeps serving it to a player who has outgrown it,
        and EASY because rung 3 is EASY's own floor, so its share is bounded by
        how many of its problems can render two blanks rather than by any climb.
        """
        served = self._by_band(self._career())
        measured = {band: self._share(served[band])
                    for band in self.BANDS if served[band]}
        for band in ("MEDIUM", "HARD"):
            self.assertEqual(
                measured.get(band, 0.0), 0.0,
                f"{band} served a scaffold outside a lapsed review: {measured}")
        self.assertGreater(measured["GUIDED"], 50.0, measured)
        self.assertAlmostEqual(measured["TUTORIAL"], self.TARGET["TUTORIAL"],
                               delta=10, msg=str(measured))
        self.assertLess(measured["EASY"], measured["TUTORIAL"], str(measured))

    def test_writing_it_all_is_the_majority_act_by_easy(self):
        """The taper finishes as a teaching device a full band before HARD. Read
        off the second half of a live career's EASY encounters, because "a
        player LEAVING easy" is a claim about the end of the band and not about
        its average."""
        easy = [r[2] for r in self._career() if r[1] == "EASY"]
        self.assertGreater(len(easy), 20, "too few EASY encounters to judge")
        leaving = easy[len(easy) // 2:]
        whole = sum(1 for r in leaving if r == scaffold.WRITE_IT_ALL)
        self.assertGreater(
            whole, len(leaving) / 2,
            f"a player leaving EASY has not produced whole functions more often "
            f"than not: {whole}/{len(leaving)}")

    def test_every_rung_one_serving_is_a_real_multiple_choice(self):
        """Six of the 42 rung-1 servings in a live career came back
        `{"rung": 1, "name": "PICK", "choices": []}` — an ordinary one-blank,
        filed as a pick, and rung-1 evidence does not count toward leaving rung
        2. Asserted on the payload the client is actually sent."""
        from gauntlet import puzzles
        game = self.game()
        by_id = {p.id: p for p in self.corpus}
        picks = 0
        for _ in range(120):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            card = enc["problem"].get("scaffold") or {}
            if card.get("rung") == scaffold.PICK:
                picks += 1
                self.assertGreaterEqual(
                    len(card.get("choices") or []), 2,
                    f"{problem.id} was served rung 1 with "
                    f"{card.get('choices')!r} to pick between")
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)
        self.assertGreater(picks, 0, "no rung-1 serving in 120 encounters")


class TestTheSchedule(base.GameTest):

    def test_a_review_is_the_whole_function(self):
        """A review measures retention. A retained skill delivered with the
        answer half written measures nothing, and `schedule_after` would grow
        the interval on the strength of it."""
        self.assertEqual(curriculum.review_rung(), scaffold.WRITE_IT_ALL)

    def test_a_lapse_drops_one_rung_and_only_one(self):
        self.assertEqual(curriculum.review_rung(lapsed=True), scaffold.MANY_BLANKS)

    def test_a_scaffolded_serving_is_not_that_family_s_review(self):
        entry = srsmod.ScheduleEntry(family="dedupe", stage=3, ease=1.4)
        before = (entry.stage, entry.ease, entry.due_at, entry.reviews)
        srsmod.schedule_after(entry, solved=True, hints_used=0,
                              rung=scaffold.ONE_BLANK)
        self.assertEqual((entry.stage, entry.ease, entry.due_at, entry.reviews),
                         before,
                         "a one-blank serving grew the interval on the strength "
                         "of the player having filled in one blank")

    def test_an_ordinary_easy_serving_is_not_a_review(self):
        """MIN_REVIEW_RUNG was 3, justified in its own comment solely by the
        LAPSED recovery serving — but rung 3 is also EASY's own floor, so
        `rung >= 3` said yes to every ordinary EASY encounter at the bottom of
        the ramp. Measured: four non-lapsed rung-3 clears took a family to stage
        4, ease 1.40 and a next sighting 42 days out. 18 of the 36 EASY servings
        in a live 120-encounter career were rung 3."""
        entry = srsmod.ScheduleEntry(family="dedupe")
        before = (entry.stage, entry.ease, entry.due_at, entry.reviews)
        for _ in range(4):
            srsmod.schedule_after(entry, solved=True, hints_used=0,
                                  rung=scaffold.MANY_BLANKS)
        self.assertEqual((entry.stage, entry.ease, entry.due_at, entry.reviews),
                         before,
                         "four fill-in-the-blanks bought six weeks of interval")
        self.assertEqual(entry.due_at, 0.0,
                         "a family whose servings never reached rung 4 acquired "
                         "a due date anyway")

    def test_the_recovery_serving_at_rung_three_still_counts(self):
        """The case rung 3 was admitted for, kept — asked of the ENTRY, which is
        the thing that knows whether this serving is a recovery."""
        entry = srsmod.ScheduleEntry(family="dedupe", stage=3)
        srsmod.schedule_after(entry, solved=False, hints_used=0,
                              rung=scaffold.WRITE_IT_ALL)
        self.assertTrue(entry.recovering)
        reviews = entry.reviews
        srsmod.schedule_after(entry, solved=True, hints_used=0,
                              rung=scaffold.MANY_BLANKS)
        self.assertEqual(entry.reviews, reviews + 1,
                         "the recovery review did not count")
        self.assertFalse(entry.recovering)
        # And the next ordinary rung-3 serving does not.
        reviews = entry.reviews
        srsmod.schedule_after(entry, solved=True, hints_used=0,
                              rung=scaffold.MANY_BLANKS)
        self.assertEqual(entry.reviews, reviews)

    def test_the_lapse_exception_belongs_only_to_the_bands_that_have_one(self):
        """docs/14-the-ramp.md §1b says HARD is "0%, with no mechanism to reach
        anything else". `lapse_floor` returned 3 for HARD, ELITE and BOSS
        exactly as for MEDIUM, and the only thing stopping a lapsed HARD review
        from carrying two blanks was that 0 of the 20 HARD editor problems
        happen to declare spans. One declaration authored at HARD would have
        turned a documented guarantee into a bug."""
        self.assertEqual(curriculum.lapse_floor("MEDIUM"), scaffold.MANY_BLANKS)
        for band in ("HARD", "ELITE", "BOSS"):
            self.assertEqual(curriculum.lapse_floor(band), scaffold.WRITE_IT_ALL,
                             f"{band} can be served a scaffold on a lapse")
        state = skillmod.SkillState(name="PYTHON")
        for problem in self.corpus:
            if problem.difficulty not in ("HARD", "ELITE", "BOSS"):
                continue
            self.assertEqual(
                curriculum.servable_rung(problem, state, lapsed=True),
                scaffold.WRITE_IT_ALL,
                f"{problem.id} ({problem.difficulty}) carried a scaffold into a "
                f"lapsed review")

    def test_a_lapse_arms_the_recovery_rung_and_a_clear_disarms_it(self):
        entry = srsmod.ScheduleEntry(family="dedupe", stage=3)
        srsmod.schedule_after(entry, solved=False, hints_used=0,
                              rung=scaffold.WRITE_IT_ALL)
        self.assertTrue(entry.recovering)
        self.assertEqual(curriculum.review_rung(lapsed=entry.recovering),
                         scaffold.MANY_BLANKS)
        srsmod.schedule_after(entry, solved=True, hints_used=0,
                              rung=scaffold.MANY_BLANKS)
        self.assertFalse(entry.recovering)


class TestTheRungSurvivesAReload(base.GameTest):
    """The rung is decided when the encounter is served and read back when the
    clear is filed. If it only ever lived in memory, a reload mid-fight filed
    the clear with no rung at all."""

    def _serve_until_scaffolded(self, game):
        from gauntlet import puzzles
        by_id = {p.id: p for p in self.corpus}
        for _ in range(60):
            enc = game.next_encounter()
            problem = by_id[enc["problem"]["id"]]
            card = enc["problem"].get("scaffold") or {}
            if card.get("rung") in (scaffold.ONE_BLANK, scaffold.MANY_BLANKS):
                return problem, card
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                game.solve_puzzle(puzzles.answer_key(problem))
            elif problem.entry.get("kind") == "mcq":
                game.answer_mcq(problem.mcq.get("answer"))
            elif problem.entry.get("kind") == "test_forge":
                game.submit(problem.starter_code)
            else:
                game.submit(problem.canonical_solution)
        self.fail("no scaffolded serving in 60 encounters")

    def test_the_served_rung_is_persisted_in_the_same_breath_as_it_is_decided(self):
        """`_encounter_payload` assigned `enc.rung` and called
        `_write_encounter`, which only writes `self.state`; `start_encounter`
        calls `save()` BEFORE the payload is built. Measured: serve rung 3,
        reconstruct the Game on the same db, and `enc.rung` came back 0 — so the
        clear was filed with no rung, `untracked_production` went to 1 and
        `has_produced_code` answered True to a two-blank fill-in."""
        from gauntlet.engine import Game
        db = self.data_dir / "save.sqlite3"
        game = Game(db_path=db, corpus_path=self.corpus_path)
        problem, card = self._serve_until_scaffolded(game)

        resumed = Game(db_path=db, corpus_path=self.corpus_path)
        self.assertIsNotNone(resumed.encounter)
        self.assertEqual(resumed.encounter.problem_id, problem.id)
        self.assertEqual(
            resumed.encounter.rung, card["rung"],
            f"{problem.id} was served rung {card['rung']} and came back "
            f"{resumed.encounter.rung} after a reload")

    def test_a_resumed_player_keeps_the_scaffold_they_were_handed(self):
        """The other half of the same bug: `Game.problem` replays `enc.rung`, so
        a rung that did not survive the reload became a blank screen."""
        from gauntlet.engine import Game
        db = self.data_dir / "save.sqlite3"
        game = Game(db_path=db, corpus_path=self.corpus_path)
        problem, card = self._serve_until_scaffolded(game)

        resumed = Game(db_path=db, corpus_path=self.corpus_path)
        view = resumed.problem(problem.id)
        self.assertEqual(view["scaffold"]["rung"], card["rung"])
        self.assertIn(scaffold.MARKER, view["starter_code"],
                      f"{problem.id} was resumed without the blanks it was "
                      f"served with")


class TestTheHoldOutDoesNotMove(base.GameTest):
    """The tripwire for anyone who later decides a few new sibling problems
    would be simpler. Adding 229 of them was measured to seal 19 problems the
    teaching side can currently use, because `goal = round(total * 0.12)` scales
    with a corpus that grew 23% without gaining a single new idea."""

    def test_the_sealed_set_is_still_exactly_one_hundred_and_twenty_two(self):
        sealed = [p.id for p in self.corpus if p.sealed]
        self.assertEqual(len(sealed), 122)

    def test_no_lineage_is_sealed_in_part(self):
        groups: dict = {}
        for problem in self.corpus:
            groups.setdefault(problem.lineage_id, []).append(problem)
        for lineage_id, group in groups.items():
            marked = [p for p in group if p.sealed]
            self.assertIn(len(marked), (0, len(group)),
                          f"lineage {lineage_id} is sealed in part")

    def test_the_ramp_created_no_problems(self):
        self.assertEqual(len(self.corpus), 1013)

    def test_the_declaration_never_reaches_the_client(self):
        """`scaffold_spans[0]['text']` IS the expression the blank is asking
        for. `redact_mcq` is the precedent; this is the same class of leak."""
        for problem in self.corpus[:300]:
            for mode in ("adventure", "interview"):
                self.assertNotIn("scaffold_spans", problem.player_view(mode=mode))


if __name__ == "__main__":
    unittest.main()
