"""The corpus is content, and content that lies is worse than no content."""
from base import GameTest  # noqa: E402
import unittest


class TestCorpus(GameTest):
    def test_seed_content_requirement(self):
        """Spec: at least 300 validated problems ship with the build."""
        self.assertGreaterEqual(len(self.corpus), 300,
                                f"only {len(self.corpus)} validated problems")

    def test_every_canonical_solution_passes_its_own_tests(self):
        self.assertEqual(self.report.errors, [],
                         "\n".join(f"{i.problem_id}: {i.message}"
                                   for i in self.report.errors))

    def test_ids_are_unique(self):
        ids = [p.id for p in self.corpus]
        self.assertEqual(len(ids), len(set(ids)))

    def test_reported_interview_problems_carry_a_disclaimer(self):
        """Never claim a generated question was actually asked by a company."""
        for p in self.corpus:
            if p.source_type == "REPORTED_INTERVIEW":
                self.assertTrue(p.provenance_note.strip(),
                                f"{p.id} claims reported provenance with no note")
                note = p.provenance_note.lower()
                self.assertTrue("pattern" in note or "archetype" in note,
                                f"{p.id} must describe itself as a pattern, "
                                "not a question")
                self.assertIn("not a guarantee", note,
                              f"{p.id} must disclaim that it is a guaranteed question")
            if p.source_type == "GENERATED_VARIANT":
                self.assertEqual(p.reported_company, "",
                                 f"{p.id} is generated but names a company")

    def test_practical_profile_covers_its_declared_emphasis(self):
        wanted = {"ARRAY", "STRING", "HASH_MAP", "SET", "SORTING", "SLIDING_WINDOW",
                  "TWO_POINTER", "MATRIX", "TREE", "RECURSION", "BFS", "DFS",
                  "DESIGN", "DEBUGGING", "COMPLEXITY", "TESTING"}
        present = {p.pattern for p in self.corpus}
        missing = wanted - present
        self.assertEqual(missing, set(), f"profile emphasis not covered: {missing}")

    def test_every_family_the_spec_names_has_content(self):
        required = [
            "two_sum", "three_sum", "window_distinct", "window_k_distinct",
            "anagrams", "rolling_max", "bst", "tree_paths", "tree_serialize",
            "grid_bfs", "grid_traverse", "design", "debugging", "testing",
            "big_o", "pattern_recognition", "prefix_sum", "binary_search",
        ]
        families = {p.spaced_repetition_family for p in self.corpus}
        for name in required:
            self.assertIn(name, families, f"no content for family {name!r}")

    def test_code_problems_have_hidden_and_edge_coverage(self):
        thin = []
        for p in self.corpus:
            if p.entry.get("kind") not in ("function", "class_ops"):
                continue
            if p.encounter_kind == "DEBUG_BATTLE":
                continue
            if len(p.hidden_tests) < 2 or not p.edge_cases:
                thin.append(p.id)
        self.assertEqual(thin, [], f"problems with thin hidden coverage: {thin[:8]}")

    def test_hint_trees_reach_the_worked_solution(self):
        for p in self.corpus:
            if p.entry.get("kind") in ("mcq",):
                continue
            spells = [rung["spell"] for rung in p.hint_tree]
            self.assertIn("PHOENIX", spells,
                          f"{p.id} can dead-end: no worked solution rung")

    def test_debug_encounters_actually_contain_a_bug(self):
        """A DEBUG_BATTLE whose starter code already passes teaches nothing."""
        broken = [p.id for p in self.corpus
                  if p.encounter_kind == "DEBUG_BATTLE"
                  and p.starter_code.strip() == p.canonical_solution.strip()]
        self.assertEqual(broken, [])

    def test_player_view_never_leaks_the_solution(self):
        for p in self.corpus[:80]:
            view = p.player_view(mode="adventure")
            self.assertNotIn("canonical_solution", view)
            self.assertNotIn("hidden_tests", view)
            self.assertNotIn("edge_cases", view)
            self.assertNotIn("mutants", view)

    def test_security_variants_are_a_minority_of_the_corpus(self):
        """Spec: 70% general software engineering, 30% security transfer."""
        security = sum(1 for p in self.corpus if p.security_variant)
        ratio = security / len(self.corpus)
        self.assertLess(ratio, 0.35,
                        f"security variants are {ratio:.0%} of the corpus")

    def test_difficulty_spread_supports_a_full_progression(self):
        from collections import Counter
        counts = Counter(p.difficulty for p in self.corpus)
        for tier in ("TUTORIAL", "EASY", "MEDIUM", "HARD"):
            self.assertGreaterEqual(counts[tier], 10,
                                    f"only {counts[tier]} problems at {tier}")

    def test_every_boss_points_at_a_real_problem(self):
        from gauntlet import world
        ids = {p.id for p in self.corpus}
        for boss in world.BOSSES:
            self.assertIn(boss["problem_id"], ids,
                          f"boss {boss['id']} points at a missing problem")

    def test_the_rune_pile_is_never_the_solution_in_order(self):
        """docs/13 §7.9 X6 — THE TRIPWIRE under the `rune` cue.

        `gauntlet/tutorial.py`'s CUE_CONTROLS is allowed to point an arrow at
        the head of a RUNE_ASSEMBLY pile for one reason and one reason only:

            The `rune` control is legal ONLY because the RUNE_ASSEMBLY pile is
            mcq.shuffle and position in a shuffle carries no information. If
            shuffle is ever sorted, seeded to put distractors last, ordered by
            difficulty or otherwise made meaningful, DELETE the `rune` control
            the same day: it becomes a leak.

        `corpus/validate.py` checks only that `len(shuffle) == len(runes)`, so
        an identity permutation — the pile in authored order, which is SOLUTION
        order — passes validation. `puzzleui.js` then renders the answer down
        the tray in the right sequence with a violet arrow on line one. That is
        why this assertion is written on purpose rather than inherited.

        Measured on the shipped corpus: 42 RUNE_ASSEMBLY problems, shuffle
        present 42/42, identity 0/42, sorted 0/42.
        """
        piles = [p for p in self.corpus if p.encounter_kind == "RUNE_ASSEMBLY"]
        self.assertGreaterEqual(len(piles), 20,
                                "no rune assemblies left to check")
        for p in piles:
            with self.subTest(problem=p.id):
                shuffle = list((p.mcq or {}).get("shuffle") or [])
                runes = list((p.mcq or {}).get("runes") or [])
                self.assertTrue(shuffle, f"{p.id}: no shuffle at all — "
                                         f"puzzleui renders the pile in "
                                         f"authored order, which is solution "
                                         f"order")
                self.assertEqual(sorted(shuffle), list(range(len(runes))),
                                 f"{p.id}: the shuffle is not a permutation "
                                 f"of every rune index")
                self.assertNotEqual(shuffle, list(range(len(runes))),
                                    f"{p.id}: the pile IS the solution in "
                                    f"order. Delete the `rune` control in "
                                    f"gauntlet/tutorial.py the same day this "
                                    f"is allowed to ship.")
                self.assertNotEqual(shuffle, sorted(shuffle),
                                    f"{p.id}: the pile is sorted, so position "
                                    f"in it carries ordering information and "
                                    f"the `rune` cue becomes a leak.")

    def test_generated_variants_are_validated_like_authored_ones(self):
        generated = [p for p in self.corpus if "generated" in p.tags]
        self.assertGreaterEqual(len(generated), 20)
        for p in generated:
            self.assertTrue(p.canonical_solution.strip())
            self.assertTrue(p.visible_tests and p.hidden_tests)
            self.assertIn("Authored variant", p.provenance_note)


if __name__ == "__main__":
    unittest.main()
