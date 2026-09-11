# Python Coding Gauntlet Legend
### The Algorithm Realms

A 16-bit RPG that happens to teach Python coding interviews. Built end to end
from the master specification: sixteen regions, fourteen bosses, 308 validated
problems, a real sandboxed Python execution environment, an adaptive learning
engine, spaced repetition, a loot-and-build system, and an Interview Mode that
is provably isolated from every form of assistance.

Runs entirely on your machine. No network, no accounts, no dependencies beyond
Python 3.9+.

---

## Run it

**Double-click** `dist/Python Coding Gauntlet Legend.app`
(a copy is installed in `~/Applications`).

From the terminal:

```bash
python3 -m gauntlet.cli play          # launch the app window
python3 -m gauntlet.cli serve         # server only, open the printed URL
python3 -m gauntlet.cli check         # verify the execution sandbox
python3 -m gauntlet.cli stats         # your progress, in the terminal
python3 -m gauntlet.cli doctor        # diagnose the installation
python3 -m gauntlet.cli build-corpus  # rebuild + revalidate all 308 problems
python3 tests/run_all.py              # the full test suite (98 tests)
```

Saves live in `~/Library/Application Support/GauntletLegend/`.
Logs: `~/Library/Logs/GauntletLegend/launch.log`.

---

## The two modes, which are never confused

**Adventure Mode teaches.** Five escalating hint spells, animated algorithm
visualisations, a Socratic coach, training camps that route you to the
prerequisite you are actually missing, and a worked solution at the bottom of
every hint tree. You can never permanently dead-end.

**Interview Mode measures.** The pattern name is redacted, the hint tree is
empty, probes and items are refused, the coach returns a refusal, and gear grace
does not apply. All of that is enforced **server-side** — `tests/test_interview_isolation.py`
exists to prove it stays that way.

---

## How a fight actually works

Enemy HP is your test coverage. Each passing trial deals damage.

An enemy's **weaknesses are the problem's real edge cases** — empty input,
duplicates, negatives, exact boundaries, scale — derived from its hidden tests.
Its **resistances** are the ceilings it enforces: an enemy with a performance
trial literally resists brute force.

Before you write anything you can spend a **probe**: assert that on *this* input
the correct answer is *that*. Get it right and you expose the weakness — when
your solution then passes that hidden trial it strikes **critically**, for up to
double XP and better loot. Get it wrong and you have caught a broken mental
model before spending twenty minutes implementing it.

That is the strategy layer, and it is the same skill an interviewer is watching
for: predicting how code breaks.

---

## Builds, loot and secrets

Three paths, chosen at the start and respeccable at the Armorer:

| Build | Wins by | Favours |
|---|---|---|
| **The Analyst** | predicting how code breaks | LOGIC, INSIGHT — more probes, sharper feedback |
| **The Duelist** | the clock | HASTE, VIGOR — clock grace, combo shields |
| **The Archivist** | knowing | FOCUS, INSIGHT — cheap spells, retest bonuses |

Five attributes, three points per level. Nine equipment slots, 44 items, four
set bonuses, six rarities, and five hidden items with real discovery conditions
— including one awarded only for turning a quadratic solution into a linear one,
knowingly.

**Every item obeys one rule:** it may change what a fight *costs* and what it
*pays*. No item supplies an answer, names a pattern, or survives into Interview
Mode. `test_no_item_can_supply_an_answer` enforces this structurally.

---

## Armour is repaired by debugging

Failed casts crack the armour piece matching the root cause — syntax cracks your
helm, off-by-ones dent your boots, performance failures melt your shield. You
repair it at the Armorer's Forge by fixing genuinely broken Python. Thirty-six
debugging encounters span syntax, off-by-one, mutation during iteration, mutable
defaults, recursion base cases, state management, wrong axis, bounds checks and
performance.

---

## What is in the box

| | |
|---|---|
| Validated problems | **308** (every canonical solution passes every one of its own tests, in the real sandbox) |
| Regions | 16 + the Null King's Castle |
| Bosses | 14, each with six phases and a teaching phase on failure |
| Encounter types | code battle, debug battle, pattern encounter, complexity duel, code reading, edge-case trap, test forge, memory ambush, boss |
| Skills tracked | 30, each with mastery / confidence / speed / retention / recency / error rate / hint dependence |
| Items | 44 across 6 rarities, 4 sets, 5 secrets |
| Tests | 98, including all 20 acceptance criteria |

---

## Safety

Player code runs under four layers of containment: a macOS `sandbox-exec`
seatbelt profile (network denied, writes confined to a scratch directory), POSIX
resource limits (CPU, address space, file size, process count), a parent-side
wall-clock kill switch, and per-test `SIGALRM` timers. The child runs with `-I -S`
and a scrubbed environment.

`python3 -m gauntlet.cli check` verifies all of it, and the game surfaces the
result in the MENU panel.

---

## Documentation

- [`docs/01-product-spec.md`](docs/01-product-spec.md) — the product, its design rules
- [`docs/02-architecture.md`](docs/02-architecture.md) — system, modules, data model, API
- [`docs/03-learning-engine.md`](docs/03-learning-engine.md) — skills, SRS, adaptation, readiness
- [`docs/04-content-pipeline.md`](docs/04-content-pipeline.md) — the corpus and how it is validated
- [`docs/05-art-and-audio.md`](docs/05-art-and-audio.md) — the original asset pipeline
- [`docs/06-acceptance.md`](docs/06-acceptance.md) — the 20 criteria and where each is proved

---

All art, music and text are original to this project. No third-party game assets
are used. Reported-interview problems are labelled as historical patterns and
carry an explicit disclaimer that they are not guaranteed questions.
