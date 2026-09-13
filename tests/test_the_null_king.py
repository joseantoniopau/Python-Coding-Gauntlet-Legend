"""The Null King himself: what he may say, how he changes, and when he is quiet.

antagonist.py is the largest authored voice in the game after banter.py and
until now it had no test file of its own. Every other module that speaks is
held to its rules by a test; he was held to them only by his own `audit`, and a
module that only grades itself is a module that grades itself generously.

Six claims, and the first is the one that would quietly ruin the character:

  1. HE NEVER SUPPLIES AN ANSWER. Not in an authored frame, not in a composed
     line, not through a slot. He may name a skill, a figure, a duration, a
     place, a boss or a chapter — never a Python construct and never a fix.
     THE GUARD IS ALSO TESTED, because a clean sweep from a guard that never
     fires proves nothing at all.
  2. HE ESCALATES, and the escalation is driven by PROOF. Standing moves only
     on graded evidence, it cannot go down, every register on the ladder is
     reachable by a real record, and the structural tells of each register —
     when "you" arrives, when "I" arrives, when he starts asking questions —
     actually hold in the lines he emits.
  3. HE DOES NOT GO STALE across a full playthrough.
  4. HE IS NEVER IN THE WAY. Nothing he returns blocks, gates, delays or
     withholds, and every occasion is sealed inside a measured run.
  5. HE CANNOT LEARN, which is the plot. Nothing he says is conditioned on
     anything except the record he already holds.
  6. HE NEVER TAKES THE GAME DOWN WITH HIM. A junk save, a missing skill table
     and an unknown occasion each get a sentence rather than a traceback.
"""
from base import GameTest  # noqa: E402

from gauntlet import antagonist, curriculum, finalexam, world

SKILL_IDS = ("HASH_MAP", "TWO_POINTER", "SLIDING_WINDOW", "MATRIX", "TREE",
             "BFS", "QUEUE", "DESIGN", "BIG_O", "DEBUGGING", "RECALL")

NOW = 1_760_000_000.0


class TheNullKing(GameTest):

    # -- helpers ----------------------------------------------------------

    def _skills(self, *, attempts=0, clears=0, unaided=0, hints=0,
                mastery=0.0, last_seen=NOW, lean=0.0):
        """A skill table in engine.Game.skills' plain-dict shape."""
        return {name: {"attempts": attempts, "clears": clears,
                       "unaided_clears": unaided, "hints": hints,
                       "mastery": mastery, "last_seen": last_seen,
                       "hint_dependence": lean, "retention": 100.0 - mastery / 2}
                for name in SKILL_IDS}

    def _save(self, *, bosses=0, chapters=0, deaths=0, hints=0, hand=0,
              regions=(), solved=0, **skill_kwargs):
        cleared = [b["id"] for b in world.BOSSES][:bosses]
        return {
            "cleared_bosses": cleared,
            "skills": self._skills(hints=hints, **skill_kwargs),
            "solved_ids": [f"p{i}" for i in range(solved)],
            "stats": {"chapters_graduated": chapters, "hints_total": hints,
                      "deaths": deaths, "sessions": 3 + bosses},
            "hand": {"uses": hand},
            "story": {"regions_entered": list(regions)},
            "player": {"playtime_seconds": 3600.0},
        }

    def _empty(self):
        return self._save()

    def _maxed(self):
        return self._save(bosses=len(world.BOSSES),
                          chapters=len(curriculum.CHAPTERS),
                          attempts=400, clears=300, unaided=40, mastery=95.0,
                          solved=400)

    def _all_occasions(self):
        return [row["id"] for row in antagonist.occasions()]

    def _lines(self, occasion, state, **kwargs):
        said = antagonist.speak(occasion, state, now=NOW, **kwargs)
        return said.get("lines", []), said

    def _detail(self):
        return {"region": "graph_wastes", "boss": "hash_titan",
                "chapter": "ch01", "apex": "apex", "sage": "sage"}

    # -- 1. he never supplies an answer -----------------------------------

    def test_the_guard_itself_catches_advice(self):
        """A clean sweep is only worth what the guard is worth.

        Every line below is the shape he must never produce. If any of them
        stops being caught, every other test in this class starts passing for
        the wrong reason.
        """
        advice = (
            "You should use a dictionary here.",
            "Try a two-pointer sweep.",
            "The fix is memoisation.",
            "Next time, sort the array first.",
            "Focus on recursion.",
            "If you had cached the result it would have worked.",
            "Here's how: iterate backwards.",
            "Instead of a list, hold a set.",
            "Work on your graph traversal.",
            "Read the documentation.",
            "Start by writing the base case.",
            "All you have to do is count them.",
        )
        for line in advice:
            with self.subTest(line=line):
                self.assertFalse(
                    antagonist.clean(line),
                    f"the guard let a remediation through: {line!r}")

    def test_the_guard_does_not_fire_on_what_he_is_allowed_to_say(self):
        """Naming the weakness is the menace. It must not trip the fix guard."""
        allowed = (
            "Four hundred and six hints. I have the number.",
            "You are the third to stand in the Graph Wastes and say nothing.",
            "Nine days. I counted them.",
            "Your weakest column is the search that spreads in rings.",
            "Sixteen finishes in that column, and none of them unaided.",
        )
        for line in allowed:
            with self.subTest(line=line):
                self.assertTrue(
                    antagonist.clean(line),
                    f"the guard refused a line he is allowed: {line!r}")

    def test_no_composed_line_anywhere_names_a_fix_or_a_construct(self):
        """Every occasion, against records chosen to open every move.

        The saturated and empty records between them reach every register and
        every move, including OFFER and SELF, which are the two that talk about
        what he would do for you and are therefore the two most likely to drift
        into being helpful.
        """
        records = {
            "empty": self._empty(),
            "struggling": self._save(bosses=4, chapters=3, deaths=5, hints=180,
                                     hand=2, attempts=40, clears=8, unaided=0,
                                     mastery=22.0, lean=0.8, solved=60),
            "improving": self._save(bosses=9, chapters=7, deaths=6, hints=200,
                                    attempts=200, clears=120, unaided=12,
                                    mastery=64.0, solved=300),
            "maxed": self._maxed(),
        }
        checked = 0
        for label, state in records.items():
            for occasion in self._all_occasions():
                for turn in range(6):    # rotation moves him off his openers
                    lines, _ = self._lines(occasion, dict(state),
                                           detail=self._detail())
                    for line in lines:
                        checked += 1
                        with self.subTest(record=label, occasion=occasion,
                                          turn=turn, line=line):
                            self.assertEqual(
                                antagonist.names_a_fix(line), [],
                                f"he offered a remediation: {line!r}")
                            self.assertEqual(
                                antagonist.names_a_construct(line, strict=False),
                                [], f"he named a construct: {line!r}")
        self.assertGreater(checked, 300,
                           "the sweep did not actually compose anything")

    def test_his_own_audit_is_clean(self):
        """`audit` covers every authored frame and every saturated filling."""
        report = antagonist.audit()
        for key in ("answerish", "fixish", "tone", "slots", "fillings",
                    "unknown_ids", "coverage", "curve", "dead_ends", "seal",
                    "blocking"):
            with self.subTest(check=key):
                self.assertEqual(report[key], [], f"{key}: {report[key]}")
        self.assertGreater(report["lines_audited"], 1000)

    def test_no_slot_ever_renders_a_dangling_plural(self):
        """`uraw` once rendered "no s of them unaided" for every count but one.

        A bare quantity is asked for by frames that supply their own noun, and
        the old spelling of it welded the number to a stray "s". It reads as a
        typo in the mouth of the one character in the game who is never
        careless, so the shape is held here rather than left to a reader.
        """
        for n in (0, 1, 2, 5, 12, 16, 406):
            with self.subTest(n=n):
                bare = antagonist._quantity(n)
                self.assertFalse(bare.endswith(" s"),
                                 f"dangling plural for {n}: {bare!r}")
                self.assertNotIn(" ", bare, f"{n} is not one word: {bare!r}")
        self.assertEqual(antagonist._quantity(0), "none",
                         "zero must read 'none of them' and never 'no of them'")
        # And the trap cannot be re-opened through `_count`.
        self.assertEqual(antagonist._count(0, ""), "none")
        self.assertEqual(antagonist._count(5, ""), "five")

    # -- 2. he escalates, on proof ----------------------------------------

    def test_standing_moves_only_on_graded_evidence(self):
        """Hints, deaths, playtime and time served move it by exactly nothing."""
        base = self._save(bosses=5, chapters=4, attempts=100, clears=50,
                          unaided=6, mastery=50.0)
        start = antagonist.dossier(base, now=NOW).standing
        for label, changed in (
                ("hints", {"stats": {**base["stats"], "hints_total": 9000}}),
                ("deaths", {"stats": {**base["stats"], "deaths": 400}}),
                ("hand", {"hand": {"uses": 50}}),
                ("playtime", {"player": {"playtime_seconds": 9e6}}),
        ):
            with self.subTest(ungraded=label):
                self.assertEqual(
                    antagonist.dossier({**base, **changed}, now=NOW).standing,
                    start, f"{label} moved his standing; it is not evidence")

    def test_standing_never_goes_down(self):
        """He is monotone. A bad week changes pressure, never standing."""
        previous = -1
        for bosses in range(0, len(world.BOSSES) + 1):
            state = self._save(bosses=bosses, chapters=min(bosses, 11),
                               attempts=20 * bosses, clears=12 * bosses,
                               unaided=3 * bosses, mastery=6.0 * bosses)
            standing = antagonist.dossier(state, now=NOW).standing
            self.assertGreaterEqual(standing, previous,
                                    f"standing fell at {bosses} bosses")
            previous = standing

    def test_every_register_on_the_ladder_is_reachable(self):
        """Including the last one.

        UNQUIET is where the character actually pays off — the sentences stop
        finishing and he begins repeating himself. A floor set above what a
        real record can reach would make the whole final act dead code and
        nothing else in the suite would notice.
        """
        ladder = [
            (self._empty(), antagonist.UNCOUNTED),
            (self._save(bosses=3, chapters=2, attempts=40, clears=20,
                        unaided=2, mastery=30.0), antagonist.NOTICED),
            (self._save(bosses=7, chapters=5, attempts=120, clears=70,
                        unaided=6, mastery=55.0), antagonist.PRECISE),
            (self._save(bosses=11, chapters=8, attempts=200, clears=140,
                        unaided=10, mastery=70.0), antagonist.ATTENTIVE),
            (self._maxed(), antagonist.UNQUIET),
        ]
        for state, expected in ladder:
            with self.subTest(register=expected):
                self.assertEqual(antagonist.dossier(state, now=NOW).register,
                                 expected)
        seen = {antagonist.dossier(s, now=NOW).register for s, _ in ladder}
        self.assertEqual(seen, set(antagonist.REGISTER_IDS),
                         "a register on the ladder cannot be reached")

    def test_the_registers_keep_their_structural_promises(self):
        """The tells are structural, not moods, so they can be measured.

        UNCOUNTED is the one that matters most: he is not addressing the player
        at all, and the moment a "you" leaks into it the opening hour stops
        being unsettling and starts being ordinary trash talk.
        """
        cases = (
            (self._empty(), antagonist.UNCOUNTED),
            (self._maxed(), antagonist.UNQUIET),
        )
        for state, register in cases:
            spec = antagonist.REGISTERS[register]
            for occasion in self._all_occasions():
                for _ in range(4):
                    lines, said = self._lines(occasion, dict(state),
                                              detail=self._detail())
                    if said.get("sealed"):
                        continue
                    self.assertEqual(said["register"], register)
                    for line in lines:
                        with self.subTest(register=register, line=line):
                            if not spec.second_person:
                                self.assertIsNone(
                                    antagonist._SECOND_PERSON.search(line),
                                    f"{register} said 'you': {line!r}")
                            if not spec.first_person:
                                self.assertIsNone(
                                    antagonist._FIRST_PERSON.search(line),
                                    f"{register} said 'I': {line!r}")
                            if not spec.asks:
                                self.assertNotIn(
                                    "?", line,
                                    f"{register} asked a question: {line!r}")

    def test_contempt_becomes_attention_and_the_turn_is_earned(self):
        """The curve, read as a player reads it: end to end, in order.

        Early he is not talking to you. Late he is talking about himself, which
        for this character is the loudest thing he can do — and it arrives only
        after the record proves the player did the one thing he cannot.
        """
        early = self._empty()
        late = self._maxed()

        early_reg = antagonist.dossier(early, now=NOW).register
        late_reg = antagonist.dossier(late, now=NOW).register
        self.assertLess(antagonist.REGISTER_INDEX[early_reg],
                        antagonist.REGISTER_INDEX[late_reg])

        # SELF is the move he has no access to until he is paying attention.
        for register in (antagonist.UNCOUNTED, antagonist.NOTICED,
                         antagonist.PRECISE):
            self.assertNotIn(antagonist.SELF, antagonist.REGISTERS[register].moves,
                             f"{register} can talk about itself too early")
        for register in (antagonist.ATTENTIVE, antagonist.UNQUIET):
            self.assertIn(antagonist.SELF, antagonist.REGISTERS[register].moves)

        # And he gets shorter as he gets less certain, which is the tell.
        self.assertGreater(antagonist.REGISTERS[antagonist.UNCOUNTED].max_words,
                           antagonist.REGISTERS[antagonist.UNQUIET].max_words)

    # -- 3. he does not go stale ------------------------------------------

    def test_he_does_not_repeat_himself_across_a_playthrough(self):
        """A full run of occasions against a record that is always moving."""
        block: dict = {}
        seen: list = []
        rotation = self._all_occasions()
        for step in range(1, 211):
            bosses = min(len(world.BOSSES), step // 15)
            state = self._save(bosses=bosses, chapters=min(11, bosses),
                               attempts=step * 11, clears=step * 5,
                               unaided=step * 3, hints=step * 7,
                               deaths=step // 8, mastery=min(99.0, step / 2.2),
                               solved=step * 5)
            state[antagonist.STATE_KEY] = block
            said = antagonist.speak(rotation[step % len(rotation)], state,
                                    detail=self._detail(), now=NOW)
            block = state[antagonist.STATE_KEY]
            seen.extend(said.get("lines", []))

        distinct = len(set(seen))
        self.assertGreater(len(seen), 300, "the playthrough said almost nothing")
        self.assertGreater(
            distinct / len(seen), 0.85,
            f"only {distinct} distinct lines in {len(seen)}; he has gone stale")

    def test_he_never_opens_a_fresh_save_with_the_same_sentence_twice(self):
        block: dict = {}
        state = self._empty()
        state[antagonist.STATE_KEY] = block
        openers = []
        for _ in range(8):
            said = antagonist.speak(antagonist.AMBIENT, state, now=NOW)
            openers.extend(said.get("lines", []))
        self.assertEqual(len(openers), len(set(openers)),
                         f"he repeated himself inside one session: {openers}")

    # -- 4. he is never in the way ----------------------------------------

    def test_nothing_he_returns_ever_blocks(self):
        for state in (self._empty(), self._maxed()):
            for occasion in self._all_occasions():
                said = antagonist.speak(occasion, dict(state), now=NOW,
                                        detail=self._detail())
                with self.subTest(occasion=occasion):
                    self.assertIs(said["blocking"], False)
                    # Nothing that would let a client stall on him.
                    for key in ("gate", "modal", "delay", "requires", "locked",
                                "await", "wait_for"):
                        self.assertNotIn(key, said,
                                         f"{occasion} carried {key!r}")

    def test_he_is_silent_inside_a_measured_run(self):
        """Every occasion, sealed, and each refusal names its capability."""
        seal = finalexam.EXAM_SEAL
        for occasion in self._all_occasions():
            spec = antagonist.OCCASIONS[occasion]
            with self.subTest(occasion=occasion):
                self.assertTrue(
                    seal.blocks(spec.capability),
                    f"{occasion} declares {spec.capability}, which a measured "
                    f"run does not seal; he would speak into a measurement")

    def test_an_unknown_occasion_is_a_sentence_and_not_a_crash(self):
        said = antagonist.speak("no_such_occasion", self._empty(), now=NOW)
        self.assertIs(said["blocking"], False)
        self.assertEqual(said["lines"], [])
        self.assertIn("error", said)

    # -- 5. he cannot learn -----------------------------------------------

    def test_he_only_ever_returns_what_he_already_holds(self):
        """The same record produces the same standing, every time, forever.

        This is the plot stated as a test. He has no term that improves with
        exposure: run the same file past him a hundred times and he arrives at
        the identical reading, because there is nowhere in him for the hundred
        readings to have gone.
        """
        state = self._save(bosses=6, chapters=5, attempts=150, clears=90,
                           unaided=8, mastery=58.0)
        first = antagonist.dossier(state, now=NOW)
        for _ in range(100):
            antagonist.speak(antagonist.AMBIENT, state, now=NOW)
        after = antagonist.dossier(state, now=NOW)
        self.assertEqual((first.standing, first.register),
                         (after.standing, after.register),
                         "something in him moved on exposure alone")

    # -- 6. he never takes the game down with him -------------------------

    def test_a_junk_save_still_gets_a_sentence(self):
        junk = (
            {}, {"skills": None}, {"skills": {}}, {"cleared_bosses": None},
            {"stats": "broken"}, {"skills": {"HASH_MAP": None}},
            {"cleared_bosses": ["not_a_boss"], "stats": {}},
            {"skills": {"HASH_MAP": {"attempts": "many"}}},
        )
        for state in junk:
            for occasion in (antagonist.AMBIENT, antagonist.GAME_STARTED,
                             antagonist.EXAM_VERDICT):
                with self.subTest(state=state, occasion=occasion):
                    said = antagonist.speak(occasion, dict(state), now=NOW)
                    self.assertIs(said["blocking"], False)
                    self.assertTrue(said.get("lines"),
                                    "he had nothing to say at all")

    def test_a_save_of_the_wrong_shape_entirely_still_gets_a_sentence(self):
        """`view` is called WITHOUT a try block by `engine.antagonist_view`.

        `_antagonist` wraps `speak`; the /api/antagonist path does not wrap
        anything. So totality is this module's job rather than its caller's,
        and it has to hold at both entry points or the one that is not wrapped
        turns a restored save into a 500 on a screen he is only ever weather on.
        """
        for state in ("junk", 42, ["a"], None, 0.5):
            with self.subTest(state=state):
                said = antagonist.speak(antagonist.AMBIENT, state, now=NOW)
                self.assertTrue(said.get("lines"))
                self.assertIs(said["blocking"], False)
                # The unwrapped call the HTTP route actually makes.
                self.assertIn(antagonist.view(state, now=NOW)["register"],
                              antagonist.REGISTER_IDS)
                self.assertIn(antagonist.herald(state, now=NOW)["register"],
                              antagonist.REGISTER_IDS)

    def test_he_speaks_with_no_state_at_all(self):
        """MARK is total: no save, no skills, no detail, and still a line."""
        for occasion in self._all_occasions():
            with self.subTest(occasion=occasion):
                said = antagonist.speak(occasion, None, now=NOW)
                self.assertTrue(said.get("lines"),
                                f"{occasion} produced silence from nothing")

    def test_he_checks_himself(self):
        report = antagonist.self_check()
        self.assertTrue(report["ok"], report)


# Runnable on its own. tests/run_all.py discovers this file too, but the
# suite is long enough that it gets killed mid-run on some machines, and a file
# that exits 0 without running anything is worse than one that fails.
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
