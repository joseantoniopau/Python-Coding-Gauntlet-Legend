# The Content Pipeline

## The bar

A problem earns its place in the corpus only if its **canonical solution passes
every one of its own tests inside the real sandbox**.

This is stronger than it sounds, because expected values and canonical solutions
come from two independent implementations:

- A **reference implementation** — a live Python callable, executed at build time,
  that produces every expected value.
- A **canonical solution** — the source text shown to the player as the worked
  solution, executed in the sandbox against those values.

Two independent implementations agreeing is what earns the problem its place.
Anything else is rejected, not shipped.

This caught real defects during the build:

- `min_subarray_len` walked `left` past `right` when the target was zero — a
  genuine bug in both the reference and the canonical text.
- `triage_buffer` popped an empty deque at capacity zero.
- `product_except_self` had a performance test whose answer was a 15,052-digit
  integer, which JSON refused to serialise.
- Every test with an integer dict key was silently wrong, because JSON stringifies
  keys. Now tagged and rebuilt.

None of these would have been found by reading.

## Problem schema

Thirty-two fields per problem, including: `id`, `title`, `realm`, `pattern`,
`secondary_patterns`, `difficulty`, `source_type`, `reported_company`,
`provenance_note`, `problem_statement`, `examples`, `constraints`,
`starter_code`, `visible_tests`, `hidden_tests`, `edge_cases`, `perf_tests`,
`canonical_solution`, `alternate_solutions`, `optimal_complexity`,
`common_failures`, `hint_tree`, `visualization`, `variants`, `security_variant`,
`spaced_repetition_family`, `prerequisites`, `estimated_seconds`,
`target_seconds`, `boss_eligible`, `profile_weight`, `mutants`.

`player_view(mode)` is the only path to the client. It strips the canonical
solution, hidden tests, edge cases, performance tests and mutants — and in
Timed Practical Mode additionally redacts the pattern, the hint tree, the
visualisation, the complexity and the known failure modes.

## Entry kinds

| Kind | How it is graded |
|---|---|
| `function` | Call the named function with the test's arguments |
| `class_ops` | Instantiate, then replay an operation trace; compare the return sequence |
| `mcq` | Recognition, complexity duel, code reading, edge-case trap |
| `test_forge` | The player writes tests. Their suite must accept the honest implementation and reject every mutant |

Comparators: `exact`, `set`, `sorted`, `nested_set`, `float`, `float_list`,
`bool`, `any_of` — so "return the triplets in any order" is expressible without
forcing an arbitrary ordering on the player.

## Composition

308 validated problems.

| Family file | Content |
|---|---|
| `arrays_hashing.py` | two sum family, three sum, anagrams, frequency, prefix sums, intervals, set ops |
| `sliding_window.py` | distinct windows, K-distinct, minimum window, rolling maximum, replacement, anagram windows |
| `two_pointers.py` | palindromes, converging pairs, fast/slow, merge, trapping water |
| `stacks_queues.py` | matching, evaluation, monotonic stacks, nesting, simulation, queues |
| `trees.py` | traversal, BST validation, path sums, level order, LCA, diameter, serialize/deserialize |
| `matrix_graphs.py` | rotation, spiral, grid BFS/DFS, components, cycles, topological order |
| `recursion_dp.py` | recursion, backtracking, linear/grid/2-D/knapsack DP |
| `python_village.py` | 41 fluency drills — the stated bottleneck, drilled hardest |
| `binary_search.py` | classic, boundaries, rotated, binary search on the answer |
| `design_oop.py` | text editor, min stack, LRU, hash map from scratch, time map, undo/redo, rate limiter |
| `debugging.py` | 36 broken programs across 20 defect classes |
| `meta.py` | 55 recognition, complexity, code-reading, edge-case-trap and test-forge encounters |
| `generator.py` | 40 auto-generated, auto-validated disguised variants |

Security transfer variants are 30% of the corpus at most — they reinforce, never
replace, generic software-engineering competence.

## The generation system

A template family is a *shape* plus a set of *skins*. A skin changes the surface
story, the element type, the output format **and at least one constraint** —
never just the variable names, because renaming does not exercise recognition.

Five template families (fixed window, complement pair, K-distinct, frequency
ranking, best contiguous run) × five skins (telemetry, market, sensors, guild,
caravan) × three output modes each. Every generated problem carries a canonical
solution, reference-derived tests and complexity expectations, and runs through
the same validator as authored content.

Generated problems retain their provenance note.

## Provenance

`with_disclaimer()` appends the disclaimer **structurally** rather than leaving
it to whoever authored the entry. Any problem marked `REPORTED_INTERVIEW` and
lacking a note is a hard validation error.

The label "historically reported pattern" describes a problem's source, not a
promise about a future task. `test_reported_interview_problems_carry_a_disclaimer`
checks that the disclaimer is present.

## Hint trees

Five rungs on every coding problem, escalating:

| Rung | Spell | Cost | Rank ceiling |
|---|---|---|---|
| 1 | **Oracle** — names the algorithm family | 3 focus | A |
| 2 | **Reveal Path** — names the data structure, describes the picture | 4 | A |
| 3 | **Pseudosight** — pseudocode | 6 | B |
| 4 | **Code Fragment** — the first few real lines | 8 | C |
| 5 | **Phoenix** — the complete worked solution | 12 | LEARNING CLEAR |

`test_hint_trees_reach_the_worked_solution` asserts every problem has a Phoenix
rung. That assertion is what makes "the player never dead-ends" a structural
property rather than an aspiration.
