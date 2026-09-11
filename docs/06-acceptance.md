# Acceptance Criteria

The twenty criteria from section 80 of the build request, and where each is
proved. Run `python3 tests/run_all.py` to verify all of them.

| # | Criterion | Status | Proved by |
|---|---|---|---|
| 1 | Jose can launch locally | ✅ | `test_01_launches_locally` — boots the server, fetches the page, checks the API. Also the `.app` bundle. |
| 2 | Progress persists | ✅ | `test_02_progress_persists`, `test_progress_persists_across_sessions` |
| 3 | Python executes safely | ✅ | `test_03_python_executes_safely` + all of `test_sandbox.py` (9 tests) |
| 4 | Problems can be solved | ✅ | `test_04_problems_can_be_solved` |
| 5 | Tests evaluate correctly | ✅ | `test_05_tests_evaluate_correctly` |
| 6 | Adventure Mode teaches after failure | ✅ | `test_06_adventure_mode_teaches_after_failure` |
| 7 | Player never permanently dead-ends | ✅ | `test_07_player_never_permanently_dead_ends`, `test_hint_trees_reach_the_worked_solution` |
| 8 | Debugging repairs armour | ✅ | `test_08_debugging_repairs_armor`, `test_armor_is_repaired_only_by_debugging` |
| 9 | Spaced repetition schedules correctly | ✅ | `test_09_spaced_repetition_schedules_correctly`, `test_spaced_repetition_schedules_and_disguises` |
| 10 | Bosses test genuine mastery | ✅ | `test_10_bosses_test_genuine_mastery` — including the teaching phase on failure |
| 11 | Interview Mode disables AI and hints | ✅ | `test_11_interview_mode_disables_assistance` + all of `test_interview_isolation.py` (14 tests) |
| 12 | Skills reflect evidence | ✅ | `test_12_skills_reflect_evidence`, `test_viewing_content_never_raises_mastery` |
| 13 | World progression works | ✅ | `test_13_world_progression_works`, `test_world_unlocks_on_evidence_not_on_time` |
| 14 | Question provenance is retained | ✅ | `test_14_question_provenance_is_retained`, `test_reported_interview_problems_carry_a_disclaimer` |
| 15 | At least 300 validated problems | ✅ | `test_15_at_least_300_validated_problems` — **308**, zero validation errors |
| 16 | practical interview profile works | ✅ | `test_16_practical_interview_profile_works` — including rising difficulty |
| 17 | Game remains fun after the first hour | ✅ | `test_17_game_has_depth_beyond_the_first_hour` — 308 problems, 17 regions, 14 bosses, 44 items, 4 sets, 5 secrets, 9 encounter types |
| 18 | Learning gains can be measured | ✅ | `test_18_learning_gains_are_measurable` — readiness demonstrably rises with evidence |
| 19 | The player voluntarily wants to continue | ✅ | `test_19_the_loop_offers_a_reason_to_continue` — XP, loot, scheduled retests, daily quests, a next encounter that is never a repeat |
| 20 | Final-boss completion requires readiness gates | ✅ | `test_20_final_completion_requires_readiness_gates`, `test_the_interviewer_refuses_an_unready_player` |

## Test suite

```
tests/test_sandbox.py              9   containment, timeouts, classification
tests/test_corpus.py              14   content integrity, provenance, coverage
tests/test_engine.py              23   skills, SRS, armour, camps, persistence
tests/test_interview_isolation.py 14   the sacred separation, enforced server-side
tests/test_tactics_items.py       18   probes, criticals, loot, builds, secrets
tests/test_acceptance.py          20   the criteria above
                                  ───
                                   98   all passing
```

## Criterion 17, in more detail

"Fun after the first hour" resists a single assertion, so it is decomposed into
the things that are actually load-bearing for a long session:

- **Content volume** — 308 problems, so the adaptive engine is never forced to
  repeat itself
- **Encounter variety** — nine kinds, so it is not the same interaction each time
- **Spatial progression** — 17 regions with distinct palettes, biomes, motifs and
  music
- **Vertical progression** — 14 bosses with six phases, rematch tiers and
  per-boss time records
- **Loot economy** — 44 items, 6 rarities, 4 set bonuses, and drop chance scaling
  with difficulty, rank and criticals
- **Build depth** — 3 paths, 5 attributes, 9 slots, respec
- **Discovery** — 5 hidden items with conditions the player must work out
- **Tactical depth** — the probe system, which makes each fight a decision rather
  than a form to fill in

## Criterion 11, in more detail

Interview isolation is the criterion most likely to rot silently, so it has the
most tests. Each one calls the **server**, not the UI:

- pattern name redacted · hint tree empty · hints refused with `sealed` · probes
  refused · items refused · visualisation, complexity and known-failure lists
  withheld · mentor and skill state withheld · loadout and tactics withheld ·
  coach reports unavailable · worked solution never returned · gear clock-grace
  does not apply · and a final control test asserting Adventure Mode still has
  every one of those things.

A guarantee that lives only in the client is not a guarantee.
