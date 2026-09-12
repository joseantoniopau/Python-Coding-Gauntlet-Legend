<div align="center">

# PYTHON CODING GAUNTLET LEGEND
### The Algorithm Realms

**A 16-bit RPG that makes you fluent in Python under interview conditions.**

1,013 validated problems · 17 regions · 14 bosses · 16 dungeons · 74 quests · 6 classes
No accounts. No network. No dependencies. It all runs on your machine.

</div>

---

## The pitch

You are a competent engineer who freezes at a blank editor. That is a *retrieval*
problem, not a knowledge problem, and it is fixed by doing the thing repeatedly
under mild pressure — which happens to be what a good RPG already is.

So this is a real game, and every system in it is wired to a learning mechanic:

| The game thing | The learning thing underneath |
|---|---|
| Your attack | Python you type. Damage scales with how much the cast actually demanded |
| Enemy weaknesses | The problem's real edge cases |
| Enemy resistances | Its performance ceiling — brute force genuinely bounces off |
| Your companion | The hint system. Its tier caps how deep a hint can go |
| Memory shrines | Spaced repetition over *patterns*, in disguised variants |
| Chapter gates | Evidence you can do the earlier thing unaided |
| Gold | Paid for graded Python. The best-paying loop in the game is fresh problems |
| The last boss | A timed practical, sealed, with every crutch removed |

---

## It teaches the basics first, then ramps

The corpus is deliberately bottom-heavy, because the most common way a learning
game fails is opening at a difficulty that only helps people who don't need it.

```
GUIDED    258  ██████████████░░░░  fill in one expression
TUTORIAL  215  ████████████░░░░░░  guided, with the shape given
EASY      321  ██████████████████  on your own
MEDIUM    196  ███████████░░░░░░░  real interview weight
HARD       23  █░░░░░░░░░░░░░░░░░  the deep end
```

**Encounter one is "what does `print(10 - 4)` show?"** — four choices, no function,
no indentation, no `return`. The first twenty-two problems contain no function at
all. Seven of your first twenty encounters are rungs on a 57-step chain that
introduces one idea at a time, and no concept is used before it is taught.

If you already write Python, the diagnostic knows: ace its writing trial and you
start at chapter IV with eight EASY and three MEDIUM problems in your first
twenty instead.

**Coverage** spans the whole practical: comprehensions, slicing, unpacking, the
standard library you're expected to reach for, OOP and dunder methods,
generators, decorators, closures, context managers, exceptions, linked lists,
trees, graphs, DP, backtracking, greedy and bit manipulation — plus **Mini-Repo
Battles**, which hand you a 3–8 file project with tests and deliberately mediocre
code and ask you to add a feature or fix a bug without breaking anything.

---

## Transfer Readiness

Ordinary RPG mastery measures familiarity with material you were taught. That is
a number that flatters you.

So **122 of the 1,013 problems are sealed** — held out permanently, whole
lineages at a time, so no sealed problem has a teachable sibling. Adventure Mode,
hints, spaced repetition and the coach can never reach them. They appear only in
measured runs, cold.

**Transfer Readiness** is computed only from sealed problems, met unaided, the
first time that lineage was ever attempted. It refuses to print a percentage
until it has ten samples, and shows its confidence band. Attempting a sealed
problem spends it, pass or fail — the hold-out is finite by design.

---

## Run it

You need **Python 3.11+** and a browser. Nothing else — no `pip install`.

**macOS / Linux**
```bash
git clone https://github.com/joseantoniopau/Python-Coding-Gauntlet-Legend.git
cd Python-Coding-Gauntlet-Legend
python3 run.py
```

**Windows** — double-click **`Play on Windows.bat`**, or `py -3 run.py`.

> Installing Python on Windows? Tick **"Add python.exe to PATH"**.

A window opens on a local server bound to `127.0.0.1` with a per-session token.
Nothing is sent anywhere. `./scripts/build_app.sh` produces a double-clickable
macOS `.app`.

### Where your save lives

| macOS | `~/Library/Application Support/GauntletLegend` |
| Windows | `%APPDATA%\GauntletLegend` |
| Linux | `~/.local/share/gauntlet-legend` |

---

## Running your code safely

Your solutions run in a separate process behind four independent layers:

1. **`sandbox-exec` seatbelt** (macOS) — denies all network, denies writes outside a scratch dir
2. **POSIX resource limits** — CPU seconds, address space, file size, process count
3. **A parent wall-clock kill** — for anything that gets past the first two
4. **A per-test timeout** — so one runaway test doesn't take the batch with it

`python3 run.py check` verifies all of it.

> **On Windows, layers 1 and 2 do not exist.** There is no seatbelt and no
> `resource` module, so isolation there rests on process separation and the
> wall-clock kill. The code you run is code you wrote, so the threat model is
> "my own infinite loop shouldn't wedge the machine" — but it is genuinely weaker
> than the macOS path, and you should know that.

---

## Interview Mode is actually sealed

Adventure Mode teaches. Interview Mode measures. The isolation is enforced
**server-side**: the pattern label is redacted, and hints, probes, companions,
items, the smith, the coach and every one of the 142 endpoints that could help
are refused with a `409` naming the capability. A test suite scans thousands of
payloads to keep it that way.

The final practical is that mode with the clock on and every crutch gone. The
fourteen bosses before it each remove exactly one, so arriving with nothing is
something you were trained for rather than ambushed by.

---

## What's in it

| | |
|---|---|
| Problems | 1,013 validated · 891 teachable · 122 sealed |
| World | 17 regions · 16 dungeons · 16 Mini-Repos · 14 bosses · 17 roaming apex monsters |
| People | 34 quest NPCs · 12 mentors · 17 vendors · 16 sages · a healer, a smith and a broker |
| Progression | 6 classes · 126 skill nodes · 6 signature blades × 9 rungs · 11 metals · 96 secret arts |
| Companions | 12, tiered, one at a time · 31 pieces of regalia |
| Combat | Turn-based · 6 elements in 3 opposed pairs · 12 potions · status effects · durability |
| Content | 74 quests in 17 chains · 121 items · 22 artifacts |

---

## Development

```bash
python3 run.py check           # verify the sandbox
python3 run.py build-corpus    # rebuild and re-validate every problem
python3 run.py doctor          # diagnose an installation
```

**983 tests across 27 files.** `tests/run_all.py` runs them all, but takes ~45
minutes and may be killed by a process limit; run files individually if so.

Every problem carries **two independent implementations** — a reference used to
compute expected outputs at build time, and a canonical solution shown to the
player. They must agree on every test, which is how a wrong problem gets caught
before a player ever sees it.

---

## Credits and licence

All art is **original and generated procedurally at runtime** — there are no
image assets in this repository, and nothing is taken from any existing game. Art
direction is in `docs/08-art-direction.md`, the story in `docs/09-story-bible.md`.

Music is six licence-clear tracks from [Pixabay](https://pixabay.com/music/)
under the Pixabay Content License — nickpanek, alec_koff, Alex Morgan and
myshoun, credited in `web/audio/music/CREDITS.md`. The game synthesises its own
soundtrack as a fallback if they are absent.

Problems tagged as reported interview patterns are **historically reported
shapes, not guaranteed questions**, and name no company.

MIT — see [LICENSE](LICENSE).
