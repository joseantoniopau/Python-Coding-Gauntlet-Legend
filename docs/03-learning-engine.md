# The Learning Engine

Two rules govern everything in this document:

1. **Difficulty rises on evidence, never on time spent playing.**
2. **Nobody ever dead-ends.** If a player cannot progress, the engine's job is to
   find the prerequisite they are actually missing and route them to it.

## The skill model

Thirty skills, each carrying:

| Field | Meaning |
|---|---|
| `mastery` | 0–100, evidence-weighted |
| `confidence` | how sure we are that the mastery number is real — `100·(1 − e^(−attempts/6))` |
| `speed` | performance against target time |
| `retention` | survival of delayed retests |
| `recency` | decays as `100·e^(−days/12)` |
| `error_rate`, `hint_dependence` | measured, not assumed |
| `median_solve_seconds`, `pattern_recognition_ms`, `debugging_seconds` | timings |
| `stage` | UNKNOWN → EXPOSED → UNDERSTOOD → ASSISTED → INDEPENDENT → RETAINED → FAST → MASTERED |

`skills.apply_outcome` is the **only** function that moves mastery, and it is
only ever called from a graded attempt. Viewing a hint, watching a
visualisation, or reading a worked solution moves nothing — `test_viewing_content_never_raises_mastery`
locks that down.

Mastery gain is `7.5 × difficulty_weight × assistance_discount`, where assistance
is `1/(1 + 0.55·hints)`. A solve with four hints is still evidence, just weaker
evidence. Delayed recall is the strongest evidence collected: a retest multiplies
the gain by `1.4 + min(days,30)/60`.

Failure costs about a third of what success pays. The system must never make the
player feel that attempting was a mistake.

## The learning graph

`PREREQUISITES` encodes what each skill stands on:

```
SLIDING_WINDOW → HASH_MAP, PYTHON      BFS  → QUEUE, SET
TWO_POINTER    → ARRAY, PYTHON         DFS  → RECURSION, SET
DP             → RECURSION, ARRAY      TREE → RECURSION
PREFIX_SUM     → ARRAY, HASH_MAP       DESIGN → HASH_MAP, QUEUE
```

When a player fails a sliding-window problem, `training_camp()` walks *down* this
graph. If `HASH_MAP` mastery is below 55, the camp is **Hashmap Training Camp**,
not more sliding window:

> "You did not fail because of sliding window. You failed because hash map is not
> yet automatic — and that pattern is built on top of it."

That is the difference between a game that repeats the wall and one that removes
it.

## Failure analysis

Every failed attempt is classified into one of eighteen categories, and the
engine reports the **first causal failure**, not the last symptom.

The worked example from the specification: a brute-force Two Sum passes every
correctness trial and fails only the 60,000-element performance trial. A naive
system reports "timeout". This one reports:

```
root cause: INEFFICIENT_ALGORITHM
"Every correctness trial passed. Only the large input defeated you —
 the algorithm is right, its cost is not."
```

and routes to Complexity Tower rather than to more array practice.

Classification sources, in priority order: syntax phase → top-level exception →
all-performance failure → per-test exception type → all-edge failure → nothing
passed at all (the approach is wrong, not a detail) → few failures (off-by-one).
A mismatch between the player's declared pattern and the real one promotes
`PATTERN_NOT_RECOGNIZED` to the root cause, because that choice sent the
implementation down the wrong road before the first line was written.

## Combat feedback

Incorrect solutions never display "WRONG". Hidden trials never reveal their
expected value — only the **category** of input that broke the spell:

> "Your spell breaks when duplicate values appear."
> "The enemy survives when the input is empty."
> "Your attack works, but it is too slow."

This tells the player what kind of thing went wrong while leaving them something
to debug.

## Spaced repetition

Scheduling is over **patterns**, not problems. Intervals are 1, 3, 7, 14, 30, 60
days, multiplied by an earned ease factor (0.6–2.2).

- Unaided clear → stage +1, ease +0.1
- Clear with 1–2 spells → stage +1, ease unchanged
- Heavy assistance → counts as a clear, but the interval does not grow
- Failure → stage −2, ease −0.2, and it returns within half a day

A retest never repeats the identical prompt. `pick_disguised()` scores candidates
in the same family by how *different* their surface is: unseen problems, tagged
disguises, generated variants and security skins all score higher, and later
stages deserve harder disguises. The specification's own example is implemented
end to end:

```
Day 1   longest substring with ≤2 distinct characters
Day 3   longest subarray with ≤K categories        (element type changed)
Day 7   longest authentication window with ≤K identities   (domain changed)
Day 14  "two baskets of fruit"                     (vocabulary removed entirely)
```

Retests take priority over fresh content in `select_next()`, because a due
pattern is the highest-value thing the engine can show.

## Encounter selection

`score_problem()` is the whole policy, and it is deliberately readable:

```
+ 4.0 × profile weight for this pattern
+ 2.0 × the problem's own profile weight
− 5.0 × distance from the target difficulty for this skill
+ (100 − mastery)×0.06 + error_rate×0.04 + hint_dependence×0.03   [if attempted]
+ 6.0                                                             [if never attempted]
− 45   if already solved         − 60   if played recently
+ 12   if in the current region  − 25   if a boss (entered deliberately)
```

Target difficulty is a function of mastery alone: under 18 → TUTORIAL, under 42 →
EASY, under 68 → MEDIUM, under 85 → HARD, else ELITE. **Time played appears
nowhere in this function.**

## Remediation

After *every* failure the engine produces three things, never nothing:

1. **Now** — a micro-drill on the skill that actually broke
2. **Next** — the same pattern one rung easier
3. **In 3 days** — the same algorithm in disguise

## Cognitive stamina

HP is cognitive stamina. Wrong answers cost 2 (1 for a syntax slip). Reaching
zero is **not** a failure state: stamina is restored to a third of maximum and
Training Camp activates. The player is never locked out.

## Readiness

Ten dimensions, each discounted by confidence so mastery we have little evidence
for cannot inflate the headline number:

```
score = mastery × (0.55 + 0.45 × confidence/100)
```

The overall figure is **not an average**:

```
overall = min(average, 40 + weakest × 0.7) × (0.4 + 0.6 × gates_passed/gates_total)
```

The weakest dimension caps the result and the gates scale it, so a strong
average cannot hide a weak prerequisite.

### The thirteen gates

No Python syntax weakness · Easy problems solved independently · Mediums solved
independently · hash map automatic · sliding window recognised · two pointers
recognised · BFS and DFS functional · tree traversal functional · Big-O explained
· edge-case tests produced · debugging under pressure · performs with a timer ·
retains patterns after several days.

**The Null King's Castle requires eight bosses, 60 mastery across its
prerequisite regions, and ten of the thirteen gates.** The Examiner refuses an
unready player outright, with the specific requirements shown:

> "The Examiner will not see you yet. This is not a difficulty wall — it is
> the readiness bar the whole game exists to move you past."

## Post-attempt coach

Socratic first. For a timeout it asks, in order:

1. What constraint in the problem makes your current approach expensive?
2. Which operation are you repeating that you have already computed once?
3. What structure would make that repeated lookup constant-time?
4. Could you avoid restarting the scan from every position?

It separates **knowledge failure** from **implementation failure** from **time
failure**, and the timed practical report breaks the run down along exactly those three
axes. The full solution is offered only after three attempts — and a Learning
Clear still advances the story while scheduling a mandatory rematch.
