"""THE SPELL EXPLAINS THE SEAL. IT MUST NOT CHANGE IT.

gauntlet/unmaking.py is the Null King's last act, written as data: fourteen
dispossessions, one for every crutch `finalexam.CRUTCHES` names, in the order
the bosses took them. It exists to give the final practical a cause. It exists
to give it a cause and NOTHING ELSE, and that second half is the part a test
has to hold down, because it is the half that rots quietly.

Four things are on trial here and the first two are the whole point.

1. THE TAKE-LIST EQUALS THE SEAL, IN BOTH DIRECTIONS. A spell that strips
   something the exam does not have made the exam harder in an audit nobody
   asked for. A spell that misses one has made the story a lie. Neither
   direction is checked by the other, so both are checked here, as sets, as
   multisets, and per capability.

2. IT CHANGES NOTHING MECHANICAL. A real exam is composed — four seeds, the
   whole question set, the clock, the sealed capability answers for every
   capability at every rung, the refusals, the ladder, the engine hooks — and
   the same exam is composed again in a world where the spell has been
   imported. The two are compared as bytes. `test_the_exam_is_the_same_exam`
   then does it the hard way: a subprocess with the module deleted from the
   tree entirely, against a subprocess that imports it first. Byte-identical or
   it does not ship.

3. THE PLAYER KEEPS THE LANGUAGE. The editor, the interpreter, the question and
   what she already knows are not capabilities in finalexam's vocabulary, which
   is precisely why he cannot hold them. Nothing in the spell imports the
   grader, the sandbox, the engine or the database; no corpus content reaches
   its payload; and the module holds no state, so it cannot develop an opinion
   about a particular player.

4. HE IS NEVER LOUD. No exclamation marks, no remediation, no answer smuggled
   into a threat, and — the one this file adds over `audit()` — no line that
   dares the player to try something and fail in front of him. That is a lesser
   villain's move and it reads as gloating.
"""
from base import GameTest  # noqa: E402

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from gauntlet import config, finalexam, unmaking, world

REPO = Path(__file__).resolve().parent.parent


class _Enc:
    """The three attributes `finalexam.encounter_seal` actually reads."""

    def __init__(self, mode=config.MODE_ADVENTURE, boss_id="", holdout=False):
        self.mode, self.boss_id, self.holdout = mode, boss_id, holdout


# ===========================================================================
# 1. THE TAKE-LIST EQUALS THE SEAL
# ===========================================================================

class TheTakeListEqualsTheSeal(GameTest):
    """The one question, asked every way it can be asked."""

    def test_the_two_lists_are_equal_in_both_directions(self):
        taken = set(unmaking.take_ids())
        extra = sorted(taken - finalexam.ALL_CRUTCHES)
        missing = sorted(finalexam.ALL_CRUTCHES - taken)
        self.assertEqual(extra, [], "the spell takes what the exam does not, "
                                    "which makes the exam harder than it is")
        self.assertEqual(missing, [], "the exam takes what the spell does not, "
                                      "which makes the story a lie")
        self.assertEqual(taken, set(finalexam.ALL_CRUTCHES))

    def test_no_crutch_is_taken_twice(self):
        ids = list(unmaking.take_ids())
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), len(finalexam.CRUTCHES))

    def test_every_crutch_has_its_own_line(self):
        for crutch in finalexam.CRUTCHES:
            d = unmaking.dispossession(crutch.id)
            self.assertIsNotNone(d, f"{crutch.id} has no dispossession")
            self.assertTrue(d.line.strip(), f"{crutch.id} is taken in silence")
            self.assertTrue(d.leaves.strip(), f"{crutch.id} shows nothing leave")

    def test_the_holdout_is_not_in_the_spell(self):
        """It is a capability, not a crutch. Nothing is taken from the player by
        it, so nothing may leave the screen for it."""
        self.assertNotIn(finalexam.HOLDOUT, unmaking.take_ids())
        self.assertNotIn(finalexam.HOLDOUT, [k for k, _ in unmaking.KEPT])

    def test_the_ids_are_quoted_from_finalexam_not_retyped(self):
        for d in unmaking.TAKE_ORDER:
            self.assertIn(d.crutch, finalexam.CRUTCH_BY_ID)

    def test_the_order_is_the_order_the_game_took_them(self):
        rungs = [unmaking._rung_of(finalexam.CRUTCH_BY_ID[i])
                 for i in unmaking.take_ids()]
        self.assertEqual(rungs, sorted(rungs))
        self.assertEqual(unmaking.take_ids()[-1], "OBLIGING_HAND")

    def test_verify_raises_rather_than_drifting(self):
        unmaking.verify()                      # must not raise
        real = unmaking.TAKE_ORDER
        try:
            unmaking.TAKE_ORDER = real[:-1]    # lose the Hand
            with self.assertRaises(unmaking.UnmakingDrift):
                unmaking.verify()
        finally:
            unmaking.TAKE_ORDER = real
        unmaking.verify()

    def test_every_form_and_motion_takes_the_same_fourteen(self):
        for form in unmaking.FORMS:
            for motion in unmaking.MOTIONS:
                view = unmaking.cinematic(form=form, motion=motion)
                got = [b["crutch"] for b in view["beats"]]
                self.assertEqual(got, list(unmaking.take_ids()), f"{form}/{motion}")
                self.assertEqual(sorted(set(got)), sorted(finalexam.ALL_CRUTCHES))
                self.assertTrue(view["seal"]["matches_exam"])

    def test_the_modules_own_audit_agrees(self):
        self.assertEqual(unmaking.audit(), [])


# ===========================================================================
# 2. IT CHANGES NOTHING MECHANICAL
# ===========================================================================

def _fingerprint(corpus):
    """Everything about the exam that a player could feel, as one JSON blob.

    Deliberately wide: the composed question sets at fixed seeds, the clock on
    every question, the sealed view's digest, the capability answers at every
    rung, the refusals, the ladder and the engine hooks. If the spell moved any
    of it, this changes.
    """
    import hashlib
    from dataclasses import asdict

    by_id = {p.id: p for p in corpus}
    caps = sorted(finalexam.ALL_CRUTCHES | {finalexam.HOLDOUT})
    exam_enc = _Enc(finalexam.EXAM_MODE)

    exams = []
    for seed in (1, 7, 1234, 99991):
        ex = finalexam.compose(corpus, seed=seed)
        questions = []
        for q in ex.questions:
            p = by_id[q.problem_id]
            view = finalexam.exam_view(p)
            questions.append({
                "problem_id": q.problem_id,
                "clock": finalexam.clock_for(p, finalexam.EXAM_SEAL),
                "target_seconds": p.target_seconds,
                "view_sealed": view["sealed"],
                "view_leaks": finalexam.audit_view(view),
                "view_digest": hashlib.sha256(json.dumps(
                    view, sort_keys=True, default=str).encode()).hexdigest(),
            })
        exams.append({"seed": seed, "format_id": ex.format_id,
                      "minutes": finalexam.FORMATS[ex.format_id].minutes,
                      "questions": questions})

    return json.dumps({
        "crutch_order": [c.id for c in finalexam.CRUTCHES],
        "crutches": [asdict(c) for c in finalexam.CRUTCHES],
        "all_crutches": sorted(finalexam.ALL_CRUTCHES),
        "exam_seal": finalexam.EXAM_SEAL.to_dict(),
        "ladder": finalexam.ladder_view(),
        "interview_format": finalexam.interview_format(),
        "engine_hooks": list(finalexam.ENGINE_HOOKS),
        "audit_seal": finalexam.audit_seal(),
        "practical_gate": finalexam.practical_gate(),
        "sealed_in_exam": {c: finalexam.sealed(exam_enc, c) for c in caps},
        "sealed_open": {c: finalexam.sealed(_Enc(), c) for c in caps},
        "sealed_by_rung": {
            s.boss_id: {c: finalexam.sealed(_Enc(boss_id=s.boss_id), c)
                        for c in caps}
            for s in finalexam.BOSS_LADDER},
        "refusals": {c: finalexam.refuse(c) for c in caps},
        "exams": exams,
    }, sort_keys=True, default=str, indent=1)


# Run in a subprocess against a COPY of the package, once with the module on
# disk and once without it. The point is a world where the spell does not
# exist, which no amount of not importing it inside this process can honestly
# produce — and a copy rather than the working tree, because a test that
# deletes a source file from the repo it is testing has one bad afternoon and
# takes the file with it.
_PROBE = """
import os, sys
sys.path.insert(0, %(repo)r)
os.environ["GAUNTLET_DATA_DIR"] = %(data)r
if %(with_spell)r:
    from gauntlet import unmaking          # the spell exists and is loaded
from gauntlet import config, finalexam
from gauntlet import corpus as corpusmod
from pathlib import Path
import json


class _Enc:
    def __init__(self, mode=config.MODE_ADVENTURE, boss_id="", holdout=False):
        self.mode, self.boss_id, self.holdout = mode, boss_id, holdout


%(fingerprint)s

print(_fingerprint(corpusmod.load(Path(%(corpus)r))), end="")
"""


class ItChangesNothingMechanical(GameTest):
    """The spell is narration over a rule that already existed."""

    def _tree(self, *, with_spell):
        """A throwaway copy of the package, with or without the spell in it."""
        import shutil
        root = self.data_dir / ("with" if with_spell else "without")
        shutil.copytree(REPO / "gauntlet", root / "gauntlet",
                        ignore=shutil.ignore_patterns("__pycache__"))
        spell = root / "gauntlet" / "unmaking.py"
        if with_spell:
            self.assertTrue(spell.exists())
        else:
            spell.unlink()
            self.assertFalse(spell.exists())
        return root

    def _probe(self, *, with_spell):
        import inspect
        root = self._tree(with_spell=with_spell)
        src = _PROBE % {"repo": str(root), "data": str(self.data_dir),
                        "with_spell": with_spell,
                        "corpus": str(self.corpus_path),
                        "fingerprint": textwrap.dedent(
                            inspect.getsource(_fingerprint))}
        out = subprocess.run([sys.executable, "-c", src],
                             capture_output=True, text=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(out.returncode, 0, out.stderr[-3000:])
        return out.stdout

    def test_the_exam_is_the_same_exam(self):
        """Composed in a tree where the spell does not exist, against one where
        it is imported before anything else. Byte-identical or it does not ship."""
        absent = self._probe(with_spell=False)
        present = self._probe(with_spell=True)
        self.assertTrue(absent)
        self.assertEqual(absent, present,
                         "the spell moved something in the exam")
        # The working tree was never touched.
        self.assertTrue((REPO / "gauntlet" / "unmaking.py").exists())
        self.assertTrue(unmaking.matches_exam())

    def test_importing_the_spell_moves_nothing_in_this_process(self):
        before = _fingerprint(self.corpus)
        import importlib
        importlib.reload(unmaking)
        after = _fingerprint(self.corpus)
        self.assertEqual(before, after)

    def test_the_sealed_capabilities_are_unchanged(self):
        enc = _Enc(finalexam.EXAM_MODE)
        for cap in sorted(finalexam.ALL_CRUTCHES):
            self.assertTrue(finalexam.sealed(enc, cap), cap)
        self.assertEqual(sorted(finalexam.EXAM_SEAL.sealed),
                         sorted(finalexam.ALL_CRUTCHES))
        self.assertEqual(finalexam.EXAM_SEAL.remaining(), ())
        self.assertEqual(finalexam.audit_seal(), [])

    def test_the_clock_is_the_problems_own_target(self):
        exam = finalexam.compose(self.corpus, seed=4242)
        by_id = {p.id: p for p in self.corpus}
        for q in exam.questions:
            p = by_id[q.problem_id]
            self.assertEqual(finalexam.clock_for(p, finalexam.EXAM_SEAL),
                             float(p.target_seconds))

    def test_the_spell_never_writes_to_finalexam(self):
        source = (REPO / "gauntlet" / "unmaking.py").read_text()
        for line in source.splitlines():
            code = line.split("#", 1)[0]
            self.assertNotIn("finalexam.", code.split("=")[0]
                             if "=" in code and "==" not in code else "",
                             f"the spell assigns into finalexam: {line!r}")

    def test_nothing_in_the_game_imports_the_spell(self):
        """The blast radius is the exam preamble and nothing else. If a future
        pass wires it in, that is fine — but it should be a deliberate edit to
        this test rather than a surprise."""
        importers = []
        for path in sorted((REPO / "gauntlet").glob("*.py")):
            if path.name == "unmaking.py":
                continue
            for line in path.read_text().splitlines():
                code = line.split("#", 1)[0]
                if "import unmaking" in code or "from .unmaking" in code:
                    importers.append(path.name)
        self.assertEqual(importers, [])


# ===========================================================================
# 3. THE PLAYER KEEPS THE LANGUAGE
# ===========================================================================

class ThePlayerKeepsTheLanguage(GameTest):
    """Learning never dead-ends. She can still type and still be graded."""

    FORBIDDEN = ("grading", "sandbox", "engine", "server", "saves", "db",
                 "progression", "adaptive", "srs", "corpus")

    def test_the_spell_imports_nothing_that_could_stop_her_typing(self):
        import ast
        tree = ast.parse((REPO / "gauntlet" / "unmaking.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
        self.assertEqual(imported & set(self.FORBIDDEN), set(),
                         f"the spell reaches the machinery: {imported}")
        self.assertLessEqual(
            {"finalexam", "world", "antagonist", "banter"} | {"dataclass", "json"},
            imported | {"dataclass", "json"})

    def test_what_he_leaves_is_not_something_he_could_hold(self):
        kept = {k for k, _ in unmaking.KEPT}
        self.assertEqual(kept & (finalexam.ALL_CRUTCHES | {finalexam.HOLDOUT}),
                         set(), "he leaves something the exam seals")
        self.assertIn("LANGUAGE", kept)
        self.assertIn("EDITOR", kept)
        self.assertIn("INTERPRETER", kept)
        for cap in kept:
            self.assertNotIn(cap, finalexam.CAPABILITY_NAMES,
                             f"{cap} is a capability, so he could take it")

    def test_the_editor_and_the_grader_are_never_named_as_taken(self):
        """The four surfaces the player needs are advisory client tokens for
        things that GO. None of them may be one of the things that stays."""
        surfaces = {d.surface for d in unmaking.TAKE_ORDER}
        for needed in ("editor", "submit", "run", "tests", "console",
                       "interpreter", "grader"):
            self.assertNotIn(needed, surfaces)
            for s in surfaces:
                self.assertNotIn(needed, s.split("-"),
                                 f"the spell takes {s}, which is the {needed}")

    def test_no_corpus_content_reaches_the_payload(self):
        """The spend test. No problem id, statement, solution or pattern may
        pass through this file — the strings are authored and the ids come from
        finalexam.CRUTCHES."""
        payload = json.dumps(unmaking.cinematic(), sort_keys=True)
        for p in self.corpus:
            self.assertNotIn(p.id, payload, f"{p.id} leaked into the spell")
            for attr in ("statement", "canonical_solution", "pattern"):
                v = getattr(p, attr, None)
                if isinstance(v, str) and len(v) > 24:
                    self.assertNotIn(v, payload, f"{p.id}.{attr} leaked")

    def test_the_spell_holds_no_state_and_answers_the_same_forever(self):
        for form in unmaking.FORMS:
            for motion in unmaking.MOTIONS:
                calls = {json.dumps(unmaking.cinematic(form=form, motion=motion),
                                    sort_keys=True) for _ in range(4)}
                self.assertEqual(len(calls), 1, f"{form}/{motion} is not pure")
        self.assertEqual(json.dumps(unmaking.ladder_echo(), sort_keys=True),
                         json.dumps(unmaking.ladder_echo(), sort_keys=True))

    def test_the_spell_never_asks_who_the_player_is(self):
        """No clock, no randomness, no database, no save, no environment.

        Checked against the parsed tree rather than the text, because the file
        is mostly prose and the prose is allowed to say "no Math.random in a
        draw path" without that counting as a use of one.
        """
        import ast
        tree = ast.parse((REPO / "gauntlet" / "unmaking.py").read_text())
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                used.update(a.name.split(".")[0] for a in node.names)
        forbidden = {"random", "time", "datetime", "sqlite3", "os", "open",
                     "input", "db", "saves", "getenv", "environ"}
        self.assertEqual(used & forbidden, set(),
                         f"the spell reaches outside itself: {used & forbidden}")


# ===========================================================================
# 4. HE IS NEVER LOUD
# ===========================================================================

class HeIsNeverLoud(GameTest):
    """Dry, exact, certain. The guards live in antagonist.py and banter.py and
    are borrowed rather than re-spelled; this adds the one they cannot see."""

    # A dare is an imperative aimed at the player that exists so she will try it
    # and fail while he watches. It is the move of a boss, not of him.
    DARES = ("go on", "try it", "try me", "let us see", "let's see",
             "i will wait", "i am waiting", "say where", "tell me where",
             "show me", "if you can", "watch me", "i dare")

    def test_he_never_raises_his_voice(self):
        for text in unmaking.authored_strings():
            self.assertNotIn("!", text, f"he shouted: {text[:60]!r}")

    def test_he_never_coaches_and_never_hands_over_an_answer(self):
        for text in unmaking.authored_strings():
            self.assertEqual(unmaking.names_a_fix(text), [],
                             f"that is advice, not menace: {text[:60]!r}")
            self.assertEqual(unmaking.names_a_construct(text), [],
                             f"that hands over an answer: {text[:60]!r}")

    def test_the_guard_that_ran_is_a_real_guard(self):
        self.assertNotEqual(unmaking.self_check()["guard"], "NONE")

    def test_he_never_dares_the_player_to_try_something(self):
        for text in unmaking.spoken_lines():
            low = text.lower()
            for dare in self.DARES:
                self.assertNotIn(dare, low,
                                 f"that gloats: {text[:70]!r} ({dare!r})")

    def test_the_last_thing_he_says_is_the_thing_he_is_wrong_about(self):
        reveal = unmaking.ACT_BY_ID[unmaking.ACT_REVEAL]
        self.assertEqual(reveal.lines[-1], unmaking.FINAL_LINE)
        self.assertEqual(unmaking.spoken_lines()[-1], unmaking.FINAL_LINE)
        # It is a claim about his own completeness, not a threat about hers.
        self.assertIn("I have read", unmaking.FINAL_LINE)
        self.assertNotIn("you will fail", unmaking.FINAL_LINE.lower())
        beats = unmaking.cinematic()["beats"]
        self.assertEqual([b for b in beats if b.get("final")], [])
        finals = [l for a in unmaking.cinematic()["acts"]
                  for l in a["lines"] if l["final"]]
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0]["text"], unmaking.FINAL_LINE)

    def test_the_inversion_is_never_said_out_loud(self):
        """He does not know he is arming her, and nothing on screen may say so.
        The author's note in the module docstring is the only place it is
        written down, and it is not an authored string."""
        for text in unmaking.authored_strings():
            low = text.lower()
            for tell in ("you can learn", "you will learn", "only ground",
                         "i cannot win", "my mistake", "disarm"):
                self.assertNotIn(tell, low, f"the game explained itself: {text!r}")

    def test_the_hold_is_silent(self):
        hold = unmaking.ACT_BY_ID[unmaking.ACT_HOLD]
        self.assertTrue(hold.silent)
        self.assertEqual(hold.lines, ())
        self.assertGreater(unmaking.SILENCE_SECONDS, 1.10)   # transform.js holds 1.10

    def test_no_line_is_clipped_by_its_own_cap(self):
        for text in unmaking.spoken_lines():
            natural = (unmaking.READ_SETTLE_SECONDS
                       + len(text) / unmaking.READ_CHARS_PER_SECOND)
            self.assertLessEqual(natural, unmaking.MAX_READ_SECONDS,
                                 f"unreadable in time: {text[:60]!r}")


# ===========================================================================
# 5. THE SHAPE, AND THE FIFTEEN COLOURS
# ===========================================================================

class TheShape(GameTest):
    """The spell is transform.js inverted, and the art budget is fifteen."""

    def test_the_acts_mirror_the_transformation(self):
        self.assertEqual(tuple(a.id for a in unmaking.ACTS), unmaking.ACT_IDS)
        self.assertEqual(
            tuple(unmaking.MIRRORS[a] for a in unmaking.ACT_IDS),
            ("RAISE", "CHARGE", "DISCHARGE", "REVEAL", "HOLD"))

    def test_the_renderer_is_told_the_same_five_acts(self):
        js = (REPO / "web" / "js" / "spellfx.js").read_text()
        for act in unmaking.ACT_IDS:
            self.assertIn(act, js)
        for crutch in unmaking.take_ids():
            self.assertIn(crutch, js, f"{crutch} has no picture")
        for d in unmaking.TAKE_ORDER:
            self.assertIn(d.motif, js, f"{d.crutch}'s motif is not drawn")

    def test_fifteen_colours(self):
        self.assertEqual(len(unmaking.PALETTE), 15)
        self.assertEqual(len(set(unmaking.PALETTE)), 15)
        ramps = {r for r, _ in unmaking.PALETTE}
        for d in unmaking.TAKE_ORDER:
            self.assertIn(d.ramp, ramps, f"{d.crutch} draws outside the fifteen")

    def test_the_ramps_named_here_exist_in_the_palette_module(self):
        js = (REPO / "web" / "js" / "palette.js").read_text()
        for ramp, _ in unmaking.PALETTE:
            self.assertIn(ramp, js, f"{ramp} is not a ramp in palette.js")

    def test_blood_is_reserved_for_the_hand(self):
        bleeding = [d.crutch for d in unmaking.TAKE_ORDER if d.ramp == "blood"]
        self.assertEqual(bleeding, ["OBLIGING_HAND"])

    def test_each_loss_looks_like_the_thing_lost(self):
        for field in ("motif", "surface", "leaves", "line"):
            values = [getattr(d, field) for d in unmaking.TAKE_ORDER]
            self.assertEqual(len(set(values)), len(values),
                             f"two dispossessions share a {field}")

    def test_the_renderer_is_given_a_seed_rather_than_a_random_number(self):
        beats = unmaking.cinematic()["beats"]
        seeds = [b["seed"] for b in beats]
        self.assertEqual(len(set(seeds)), len(seeds))
        for b in beats:
            self.assertIsInstance(b["seed"], int)

    def test_reduced_motion_keeps_every_beat_and_every_word(self):
        full = unmaking.cinematic(motion=unmaking.MOTION_FULL)
        red = unmaking.cinematic(motion=unmaking.MOTION_REDUCED)
        self.assertEqual([b["crutch"] for b in full["beats"]],
                         [b["crutch"] for b in red["beats"]])
        self.assertEqual([b["line"] for b in full["beats"]],
                         [b["line"] for b in red["beats"]])
        self.assertEqual([b["seconds"] for b in full["beats"]],
                         [b["seconds"] for b in red["beats"]])
        self.assertTrue(all(not b["shake"] and not b["flash"]
                            for b in red["beats"]))

    def test_the_short_form_drops_words_and_never_a_dispossession(self):
        short = unmaking.cinematic(form=unmaking.FORM_SHORT)
        self.assertEqual([b["crutch"] for b in short["beats"]],
                         list(unmaking.take_ids()))
        self.assertTrue(all(b["take_seconds"] > 0 for b in short["beats"]))
        self.assertLess(short["timing"]["unattended_seconds"],
                        unmaking.cinematic()["timing"]["unattended_seconds"])

    def test_the_timeline_is_monotonic_and_nothing_overlaps(self):
        for form in unmaking.FORMS:
            view = unmaking.cinematic(form=form)
            cursor = 0.0
            for act in view["acts"]:
                self.assertAlmostEqual(act["at"], cursor, places=2)
                cursor = act["end"]
            self.assertAlmostEqual(cursor, view["timing"]["unattended_seconds"],
                                   places=2)
            for beat in view["beats"]:
                self.assertLessEqual(beat["at"], beat["input_at"])
                self.assertLessEqual(beat["input_at"], beat["end"])

    def test_the_skip_cannot_eat_the_spell(self):
        view = unmaking.cinematic()
        self.assertEqual(view["skip"]["after_act"], unmaking.ACT_TAKE)
        self.assertGreaterEqual(view["skip"]["at"], view["beats"][0]["end"])

    def test_every_beat_names_a_boss_the_world_actually_has(self):
        for beat in unmaking.cinematic()["beats"]:
            if beat["taken_by"]:
                self.assertIn(beat["taken_by"], world.BOSS_BY_ID)
                self.assertEqual(beat["boss"],
                                 world.BOSS_BY_ID[beat["taken_by"]]["name"])
            self.assertLessEqual(beat["rung"], len(finalexam.BOSS_LADDER))

    def test_the_ladder_echo_matches_the_ladder(self):
        rows = unmaking.ladder_echo()
        self.assertEqual([r["crutch"] for r in rows], list(unmaking.take_ids()))
        for row in rows:
            crutch = finalexam.CRUTCH_BY_ID[row["crutch"]]
            self.assertEqual(row["name"], crutch.name)
            self.assertEqual(row["first_herald"], crutch.herald)

    def test_it_imports_cleanly_on_its_own(self):
        out = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {str(REPO)!r}); "
             "from gauntlet import unmaking; "
             "print(unmaking.self_check()['problems'])"],
            check=True, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "[]")


if __name__ == "__main__":
    import unittest
    unittest.main()
