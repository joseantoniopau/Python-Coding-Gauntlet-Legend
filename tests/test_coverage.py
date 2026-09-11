"""Does the corpus actually teach the syllabus, and does it teach it gently?

Two lists decide what this game owes a player. The first is the language itself
— the mechanics that have to cost nothing to type under pressure. The second is
the set of archetype families the product spec names as the shapes an interview
keeps returning to. This file checks both, item by item, and then checks the one
property that decides whether any of it lands:

    EVERY TOPIC OPENS AT GUIDED OR TUTORIAL.

That property is why this file exists at all. The complaint that produced most
of the recent content was "the game is too hard", and the cause was not that
individual problems were too hard — it was that thirty-nine topics had no
gentle instance. A player's first encounter with two-dimensional dynamic
programming was edit distance; the only serialise/deserialise problem in the
corpus was a HARD. That is not a difficulty curve, it is a cliff, and a curve
nobody measures becomes one again the next time content ships.

The detectors below are deliberately dumb: they read the text a player reads —
title, statement, canonical solution, runes, choices — plus the family name and
the tags. A topic that is present but that no reasonable search finds is a topic
a player will not find either.

The last section is the playthrough-length estimate. It is computed from the
corpus's own `target_seconds` and from nothing else, and it asserts the numbers
are DERIVED rather than asserting they are good. The honest figure and what
would close the gap are in the report `report_playthrough()` prints.
"""
from __future__ import annotations

import re
import unittest
from collections import Counter, defaultdict

from base import GameTest  # noqa: E402

from gauntlet import curriculum, worldgen
from gauntlet import skills as skillmod
from gauntlet.corpus import _FAMILIES
from gauntlet.corpus.schema import DIFFICULTIES

TIERS = curriculum.TIERS
GENTLE = ("GUIDED", "TUTORIAL")


def tier_index(name: str) -> int:
    return TIERS.index(name)


def searchable(problem) -> str:
    """Everything about a problem a player or a search would actually read."""
    parts = [problem.id, problem.title, problem.problem_statement,
             problem.canonical_solution, problem.starter_code,
             problem.spaced_repetition_family, problem.pattern,
             problem.encounter_kind, " ".join(problem.tags),
             " ".join(problem.secondary_patterns)]
    spec = problem.mcq or {}
    for key in ("code", "flawed_code", "reference_code", "operations", "probe"):
        if isinstance(spec.get(key), str):
            parts.append(spec[key])
    for choice in spec.get("choices") or ():
        parts.append(str(choice))
    for key in ("runes", "snippets"):
        for item in spec.get(key) or ():
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
                parts.append(str(item.get("code", "")))
    return "\n".join(parts)


def by_text(*patterns):
    compiled = [re.compile(p) for p in patterns]
    return lambda p, text: any(c.search(text) for c in compiled)


def by_family(*names):
    wanted = frozenset(names)
    return lambda p, text: p.spaced_repetition_family in wanted


def by_kind(*kinds):
    wanted = frozenset(kinds)
    return lambda p, text: p.encounter_kind in wanted


def either(*tests):
    return lambda p, text: any(t(p, text) for t in tests)


# ---------------------------------------------------------------------------
# (a) The language basics the original spec requires become automatic.
# ---------------------------------------------------------------------------

LANGUAGE_BASICS = (
    ("variables", either(by_family("onboarding_basics"),
                         by_text(r"\bvariable\b", r"\breassign"))),
    ("booleans", by_text(r"\bbool\b|\bboolean|\bTrue\b|\bFalse\b|truthy")),
    ("strings", either(by_family("onboarding_strings", "string_basics",
                                 "text_normalise"),
                       by_text(r"\.upper\(|\.lower\(|\.split\(|\.strip\(|\.join\("))),
    ("lists", either(by_family("onboarding_lists"),
                     by_text(r"\.append\(|\blist\("))),
    ("dict", either(by_family("onboarding_dict"),
                    by_text(r"\bdict\(|\.items\(\)|\.keys\(\)|\.values\(\)|\.get\("))),
    ("sets", either(by_family("onboarding_set", "set_ops", "dedupe"),
                    by_text(r"\bset\("))),
    ("tuples", by_text(r"\btuple\b|\btuple\(")),
    ("loops", either(by_family("onboarding_loops"),
                     by_text(r"\bfor \w+ in |\bwhile "))),
    ("functions", either(by_family("onboarding_functions"), by_text(r"\bdef \w+\("))),
    ("range", by_text(r"\brange\(")),
    ("enumerate", by_text(r"\benumerate\(")),
    ("zip", by_text(r"\bzip\(")),
    ("sorted", by_text(r"\bsorted\(|\.sort\(")),
    ("lambda", by_text(r"\blambda\b")),
    ("Counter", by_text(r"\bCounter\b")),
    ("defaultdict", by_text(r"\bdefaultdict\b")),
    ("deque", by_text(r"\bdeque\b")),
    ("heapq", by_text(r"\bheapq\b|heappush|heappop|nlargest|nsmallest")),
    ("JSON", by_text(r"\bjson\b|\bJSON\b")),
    ("exceptions", by_text(r"\braise \b|\bexcept \b|\btry:|\bException\b")),
    ("classes", by_text(r"\bclass \w+")),
    ("recursion", either(by_family("recursion_basics", "recursion_divide"),
                         by_text(r"\brecurs"))),
    ("slicing", by_text(r"\[[^\]\n]*:[^\]\n]*\]|\bslic")),
    ("list comprehension", by_text(r"\[[^\[\]\n]+ for \w+ in ")),
    ("dict comprehension", by_text(r"\{[^{}\n]+:[^{}\n]+ for \w+ in ")),
)

# ---------------------------------------------------------------------------
# (b) The reported archetype families the spec names.
# ---------------------------------------------------------------------------

ARCHETYPES = (
    ("two sum", either(by_family("two_sum"), by_text(r"two[ _-]?sum"))),
    ("3sum", either(by_family("three_sum"),
                    by_text(r"3[ _-]?sum|three[ _-]?sum"))),
    ("longest substring without repeating",
     either(by_family("window_distinct"),
            by_text(r"without repeating|no repeated character|"
                    r"distinct characters|no character repeats"))),
    ("longest substring with k distinct",
     either(by_family("window_k_distinct"), by_text(r"k distinct|at most k"))),
    ("anagrams", either(by_family("anagrams", "window_anagram"),
                        by_text(r"anagram"))),
    ("group anagrams", by_text(r"group[_ -]?anagram|anagram[_ -]?group|"
                               r"group the anagrams|anagrams together")),
    ("array traversal", either(
        by_family("counting", "frequency", "prefix_sum", "onboarding_lists"),
        by_text(r"single pass|one pass|traverse the (list|array)"))),
    ("sorting and grouping", either(
        by_family("sorting", "stdlib_groupby", "top_k"),
        by_text(r"\bsorted\(|groupby|group by|\bbucket"))),
    ("matrix rotation", by_text(r"rotate.{0,30}(matrix|grid|image|square)|"
                                r"rotat\w+ 90|clockwise")),
    ("matrix traversal", either(by_family("matrix_traverse", "matrix_transform",
                                          "grid_traverse"),
                                by_text(r"spiral|transpose|column of"))),
    ("grid BFS and DFS", either(
        by_family("grid_bfs", "grid_traverse", "graph_traverse", "graph_shortest"),
        by_text(r"flood fill|island|shortest path"))),
    ("validate BST", either(by_family("bst"),
                            by_text(r"valid.{0,25}(BST|binary search tree)"))),
    ("tree path sum", either(by_family("tree_paths"),
                             by_text(r"path sum|root-to-leaf|root to leaf"))),
    ("serialise and deserialise a tree",
     either(by_family("tree_serialize"),
            by_text(r"serialis|serializ|deserial"))),
    ("rolling maximum over a window",
     either(by_family("rolling_max"),
            by_text(r"rolling max|sliding window maximum|largest value in each "
                    r"window|maximum .{0,25}each window"))),
    ("hash-map-like structure",
     by_text(r"class \w*(HashMap|MyHashMap|HashTable)|"
             r"key-value store|implement.{0,40}hash (map|table)")),
    ("text editor undo and redo",
     by_text(r"undo and redo", r"undo/redo",
             r"(?s)undo.{0,400}redo")),
    ("recursive number reduction",
     by_text(r"digital root|sum of (its )?digits|digit_sum|"
             r"reduce.{0,40}(single digit|one digit)")),
    ("find where a pattern breaks",
     either(by_kind("BREAK_IT"),
            by_text(r"where it breaks|counter-?example|input that breaks"))),
    ("OOP stateful design",
     either(by_family("design", "oop_classes", "codebase_class"),
            lambda p, text: p.pattern == "DESIGN")),
    ("debugging existing code",
     either(by_kind("DEBUG_BATTLE", "SPOT_THE_FLAW"), by_family("debugging"))),
    ("optimise a brute force",
     either(by_kind("REFACTOR_QUEST"),
            by_text(r"brute force|too slow|optimis|optimiz"))),
    ("explain complexity",
     either(by_kind("COMPLEXITY_DUEL", "COMPLEXITY_MATCH"), by_family("big_o"))),
    ("edge cases",
     either(by_kind("EDGE_CASE_TRAP"), by_family("edge_cases"),
            lambda p, text: bool(p.edge_cases))),
)


class CoverageTest(GameTest):
    """Shared machinery: index the corpus once, search it many times."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text = {p.id: searchable(p) for p in cls.corpus}

    def matches(self, test):
        return [p for p in self.corpus if test(p, self.text[p.id])]

    def lowest_tier(self, problems):
        return min((tier_index(p.difficulty) for p in problems), default=None)

    def check_list(self, name, spec):
        missing, steep = [], []
        for topic, test in spec:
            found = self.matches(test)
            if not found:
                missing.append(topic)
                continue
            lowest = self.lowest_tier(found)
            if TIERS[lowest] not in GENTLE:
                steep.append(f"{topic} (opens at {TIERS[lowest]}, "
                             f"{len(found)} problems)")
        self.assertEqual(missing, [], f"{name}: nothing in the corpus teaches these")
        self.assertEqual(steep, [], f"{name}: no gentle way in")


class TestTheCorpusItself(CoverageTest):
    def test_the_whole_corpus_validates_with_no_errors_and_no_warnings(self):
        """Every problem carries a reference implementation and an independently
        written canonical solution, and the two must agree on every test. A
        build that finishes IS the proof; this records what it proved."""
        self.assertEqual([f"{i.problem_id}: {i.message}"
                          for i in self.report.errors], [])
        self.assertEqual([f"{i.problem_id}: {i.message}"
                          for i in self.report.warnings], [])
        self.assertGreaterEqual(len(self.corpus), 900)
        self.assertEqual(len(self.corpus), self.report.checked)

    def test_every_registered_family_contributes(self):
        """A family listed in `_FAMILIES` that builds nothing is a module that
        silently stopped being part of the game."""
        self.assertGreaterEqual(len(_FAMILIES), 24)
        import importlib
        for name in _FAMILIES:
            module = importlib.import_module(f"gauntlet.corpus.families.{name}")
            self.assertTrue(module.build(), name)

    def test_every_problem_credits_a_skill_that_exists(self):
        known = set(skillmod.SKILLS)
        for problem in self.corpus:
            skill = skillmod.PATTERN_TO_SKILL.get(problem.pattern)
            self.assertIsNotNone(skill, f"{problem.id}: pattern "
                                        f"{problem.pattern!r} credits nothing")
            self.assertIn(skill, known, problem.id)
            for secondary in problem.secondary_patterns:
                credited = skillmod.PATTERN_TO_SKILL.get(secondary)
                self.assertIn(credited, known,
                              f"{problem.id}: secondary {secondary!r}")

    def test_every_family_the_chapter_ladder_names_has_problems(self):
        """The ladder pulls problems by `spaced_repetition_family`. A chapter
        naming a family nobody authors is a chapter with a hole in it."""
        present = {p.spaced_repetition_family for p in self.corpus}
        for chapter in curriculum.CHAPTERS:
            missing = sorted(set(chapter.families) - present)
            self.assertEqual(missing, [], chapter.id)

    def test_every_test_forge_can_actually_be_won(self):
        """`min_kills` defaults to every Mimic, so one Mimic that behaves
        identically to the honest implementation makes the encounter
        unwinnable. Each Mimic carries the input that proves it is not that."""
        forges = [p for p in self.corpus if p.entry.get("kind") == "test_forge"]
        self.assertGreaterEqual(len(forges), 5)
        for problem in forges:
            witnesses = problem.mcq.get("kill_inputs") or []
            self.assertEqual(len(witnesses), len(problem.mutants), problem.id)
            self.assertLessEqual(problem.mcq["min_kills"], len(problem.mutants))

    def test_a_forge_never_ships_its_answers_to_the_client(self):
        for problem in self.corpus:
            if problem.entry.get("kind") != "test_forge":
                continue
            view = problem.player_view(mode="adventure")
            self.assertNotIn("kill_inputs", view["mcq"], problem.id)
            self.assertNotIn("mutants", view, problem.id)
            self.assertIn("min_kills", view["mcq"], problem.id)

    def test_reported_provenance_disclaims_and_names_nobody(self):
        """REPORTED_INTERVIEW means 'a shape the reporting record keeps
        producing' — a claim we can stand behind. Naming an employer is one we
        cannot, since nobody confirmed any given question was asked anywhere.
        So the disclaimer is the contract and the attribution is refused."""
        for problem in self.corpus:
            if problem.source_type == "REPORTED_INTERVIEW":
                self.assertFalse((problem.reported_company or "").strip(),
                                 problem.id)
            if problem.provenance_note and problem.source_type in (
                    "REPORTED_INTERVIEW", "COMPANY_PATTERN", "GENERAL_INTERVIEW"):
                self.assertIn("not a guarantee",
                              problem.provenance_note.lower(), problem.id)


class TestLanguageCoverage(CoverageTest):
    def test_every_language_basic_is_taught_and_opens_gently(self):
        self.check_list("language basics", LANGUAGE_BASICS)

    # Three of the basics are not village material, and that is the ladder's
    # decision rather than an oversight: recursion is chapter VII in its
    # entirety, classes belong to the OOP ladder and the design work of chapter
    # X, and JSON arrives with the practical test. Each is named here with the
    # family that owns it, and the test below holds them to the property that
    # actually matters — a gentle way in, inside a chapter that claims them.
    LATER_BY_DESIGN = {
        "recursion": "recursion_basics",
        "classes": "oop_classes",
        "JSON": "json_reshape",
    }

    def test_the_village_reaches_every_basic_it_is_meant_to(self):
        """Chapters I-III are the language. If a basic that belongs to the
        language appears only in chapter VII's problems, it is not
        'automatic', it is incidental."""
        early = {f for c in curriculum.CHAPTERS[:3] for f in c.families}
        village = [p for p in self.corpus
                   if p.spaced_repetition_family in early]
        self.assertGreater(len(village), 100)
        text = {p.id: self.text[p.id] for p in village}
        thin = []
        for topic, test in LANGUAGE_BASICS:
            if topic in self.LATER_BY_DESIGN:
                continue
            if not any(test(p, text[p.id]) for p in village):
                thin.append(topic)
        self.assertEqual(thin, [], "taught only after the language chapters")

    def test_the_three_later_basics_still_open_gently_and_have_a_home(self):
        """Arriving later is fine. Arriving without a doorway is not."""
        by_family = defaultdict(list)
        for problem in self.corpus:
            by_family[problem.spaced_repetition_family].append(problem)
        claimed = {f for c in curriculum.CHAPTERS for f in c.families}
        for topic, family in self.LATER_BY_DESIGN.items():
            problems = by_family[family]
            self.assertTrue(problems, f"{topic}: {family} has no problems")
            tiers = {p.difficulty for p in problems}
            self.assertTrue(tiers & set(GENTLE),
                            f"{topic} opens at "
                            f"{TIERS[min(tier_index(t) for t in tiers)]}")
            # Reachable: either a chapter names the family outright, or some
            # chapter permits the pattern it is authored under.
            patterns = {p.pattern for p in problems}
            reachable = family in claimed or any(
                not c.patterns or patterns & set(c.patterns)
                for c in curriculum.CHAPTERS)
            self.assertTrue(reachable, f"{topic}: nothing can select {family}")


class TestArchetypeCoverage(CoverageTest):
    def test_every_reported_archetype_is_present_and_opens_gently(self):
        self.check_list("reported archetypes", ARCHETYPES)

    def test_each_archetype_has_more_than_one_instance(self):
        """One problem is an anecdote. A family a player can practise needs at
        least a second shape of the same idea."""
        thin = []
        for topic, test in ARCHETYPES:
            found = self.matches(test)
            if len(found) < 2:
                thin.append(f"{topic} ({len(found)})")
        self.assertEqual(thin, [])


class TestTheRamp(CoverageTest):
    """The property the whole ramp audit exists to hold."""

    def test_no_topic_first_appears_at_medium_or_above(self):
        steep = []
        for family, problems in self.families().items():
            lowest = TIERS[self.lowest_tier(problems)]
            if tier_index(lowest) >= tier_index("MEDIUM"):
                steep.append(f"{family} opens at {lowest} "
                             f"({len(problems)} problems)")
        self.assertEqual(sorted(steep), [])

    def test_every_topic_has_a_guided_or_tutorial_entry_point(self):
        steep = []
        for family, problems in self.families().items():
            tiers = {p.difficulty for p in problems}
            if not tiers & set(GENTLE):
                steep.append(f"{family} opens at "
                             f"{TIERS[self.lowest_tier(problems)]}")
        self.assertEqual(sorted(steep), [])

    def families(self):
        grouped = defaultdict(list)
        for problem in self.corpus:
            grouped[problem.spaced_repetition_family].append(problem)
        return grouped

    def test_the_gentle_tiers_are_a_real_share_of_the_corpus(self):
        """A single GUIDED problem per topic satisfies the letter of the rule
        and leaves the player with nothing to practise on. Roughly the first
        third of the corpus should be below EASY."""
        counts = Counter(p.difficulty for p in self.corpus)
        gentle = sum(counts[t] for t in GENTLE)
        self.assertGreater(gentle / len(self.corpus), 0.3,
                           f"only {gentle} gentle problems of {len(self.corpus)}")

    def test_a_guided_problem_is_a_scaffold_not_a_blank_screen(self):
        """GUIDED means working code with a hole in it, or a question with
        choices. A GUIDED problem whose starter is `def f(): pass` is a MEDIUM
        wearing a label."""
        blank = []
        for problem in self.corpus:
            if problem.difficulty != "GUIDED":
                continue
            if problem.entry.get("kind") in ("mcq", "test_forge"):
                continue
            if problem.mcq:
                # A puzzle carries its material in `mcq` — the runes to
                # reassemble, the spell to trace, the pair to tell apart — and
                # its `starter_code` is rightly a stub.
                self.assertTrue(
                    any(problem.mcq.get(k) for k in
                        ("runes", "code", "flawed_code", "operations",
                         "snippets")),
                    f"{problem.id} is a GUIDED puzzle with nothing in it")
                continue
            body = [ln for ln in problem.starter_code.splitlines() if ln.strip()]
            if len(body) < 3 and "__BLANK__" not in problem.starter_code:
                blank.append(problem.id)
        self.assertEqual(blank, [])

    def test_every_difficulty_the_schema_offers_is_ordered_the_same_way(self):
        """Two modules rank difficulty. They must rank it identically, or the
        gates and the corpus disagree about what 'harder' means."""
        overlap = [d for d in DIFFICULTIES if d in TIERS]
        self.assertEqual(overlap, [d for d in TIERS if d in DIFFICULTIES])


class TestPlaythroughLength(CoverageTest):
    """How long is all of it, really?

    Computed from the corpus's own authored `target_seconds` and nothing else.
    There is no telemetry in this repository, so every number here is an
    estimate built on authored budgets, and it is labelled as one everywhere it
    surfaces. What is asserted is that the estimate is DERIVED — that the
    timing table the world generator plans against is the corpus's real means,
    not a transcription that drifted three content drops ago.
    """

    def test_the_timing_table_is_the_corpus_and_not_a_stale_copy(self):
        measured = worldgen.measured_corpus_means(self.corpus)
        self.assertTrue(measured)
        for name, row in measured.items():
            self.assertAlmostEqual(
                worldgen.CORPUS_MEAN_TARGET[name], row["mean"], delta=1.0,
                msg=f"worldgen plans {name} at "
                    f"{worldgen.CORPUS_MEAN_TARGET[name]}s; the corpus's "
                    f"{row['count']} {name} problems really average "
                    f"{row['mean']:.1f}s")

    def test_every_problem_carries_a_real_target_time(self):
        for problem in self.corpus:
            self.assertGreater(problem.target_seconds, 0, problem.id)
            self.assertLessEqual(problem.target_seconds, 2400, problem.id)

    def test_the_estimate_is_reported_honestly_rather_than_asserted(self):
        """The target was ~10 hours for a playthrough covering every lesson.
        The three honest readings of that, at the gates the curriculum sets:

            exposure    every chapter and every skill met once, no repetition
            graduation  the curriculum's own `graduate_*` gates satisfied
            scheduled   everything a seeded world actually puts in front of you

        The test asserts only that the three are ordered and finite. The
        numbers themselves are printed, because a number that has to pass a
        test stops being a measurement.
        """
        report = worldgen.self_check(30)
        exposure = report["exposure_hours"]["median"]
        graduation = report["graduation_hours"]["median"]
        scheduled = report["full_hours"]["median"]
        total = sum(p.target_seconds for p in self.corpus) / 3600.0
        print(f"\n  PLAYTHROUGH ESTIMATE (authored target times, no telemetry)"
              f"\n    every lesson met once           {exposure:6.1f} h"
              f"\n    curriculum gates satisfied      {graduation:6.1f} h"
              f"\n    a full seeded world             {scheduled:6.1f} h"
              f"\n    every problem in the corpus     {total:6.1f} h"
              f"\n    target                          {worldgen.TARGET_HOURS:6.1f} h")
        self.assertLess(exposure, graduation)
        self.assertLess(graduation, scheduled)
        self.assertLess(scheduled, total)
        self.assertTrue(report["ok"], report["failures"])

    def test_the_first_hour_is_gentle_in_every_seed(self):
        """Whatever the seed reorders, the opening stays inside the band."""
        report = worldgen.self_check(30)
        self.assertTrue(report["first_hour_gentle_every_seed"])
        hardest = set(report["first_hour_hardest_difficulty"])
        self.assertEqual(hardest - {"GUIDED", "TUTORIAL", "EASY"}, set())
        self.assertGreaterEqual(report["first_hour_encounters"]["min"],
                                worldgen.GENTLE_BAND["min_encounters"])


if __name__ == "__main__":
    unittest.main()
