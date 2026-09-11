<div align="center">

# PYTHON CODING GAUNTLET LEGEND
### The Algorithm Realms

**A 16-bit RPG that makes you fluent in Python under interview conditions.**

956 validated problems · 17 regions · 14 bosses · 16 dungeons · 74 quests · 6 classes
No accounts. No network. No dependencies. It all runs on your machine.

</div>

---

## The pitch

You are a competent engineer who freezes at a blank editor. That is a *retrieval*
problem, not a knowledge problem, and it is fixed by doing the thing repeatedly
under mild pressure — which happens to be what a good RPG already is.

So this is a real game. It has a story, loot, a skill tree, bosses, secrets and a
soundtrack. Every one of those systems is wired to a learning mechanic underneath:

| The game thing | The learning thing underneath |
|---|---|
| Enemy weaknesses | The problem's actual edge cases |
| Enemy resistances | Its performance ceiling — brute force really does bounce off |
| Spaced-repetition shrines | Retrieval practice over *patterns*, in disguised variants |
| Chapter gates | Evidence you can do the earlier thing unaided |
| Hints | Real help, at a real cost to the rank you can earn |
| The final boss | A timed practical, with every crutch removed |

---

## It teaches the basics first, then ramps

The corpus is deliberately bottom-heavy, because the most common way a learning
game fails is opening at a difficulty that only helps people who don't need it.

```
GUIDED    206  ████████████░░░░░░  fill in one expression
TUTORIAL  210  ████████████░░░░░░  guided, with the shape given
EASY      321  ██████████████████  on your own
MEDIUM    196  ███████████░░░░░░░  real interview weight
HARD       23  █░░░░░░░░░░░░░░░░░  the deep end
```

Every topic enters at GUIDED or TUTORIAL before it is ever asked for cold. The
first thirteen encounters are fill-in-the-blank.

**How long is it?** The test suite computes this from authored target times, so
it is an estimate rather than telemetry:

| | |
|---|---|
| Every lesson met once | ~7 h |
| The curriculum's own gates satisfied | ~25 h |
| A full seeded world | ~42 h |
| Every problem in the corpus | ~104 h |

The gates are deliberately set at more evidence than one clear, because that is
what makes the readiness signal mean anything.

**Coverage** spans the whole practical, not just algorithm puzzles: core language
mechanics (comprehensions, slicing, unpacking, `enumerate`/`zip`/`sorted`),
the standard library you're expected to reach for (`collections`, `itertools`,
`functools`, `heapq`), OOP and dunder methods, generators, decorators, closures
and context managers, exceptions, linked lists, trees, graphs, DP, backtracking,
greedy, bit manipulation — and a **practical** family shaped like the real thing:
here is an existing module, add a feature, fix a bug, keep its tests green.

---

## Run it

You need **Python 3.11+** and a browser. Nothing else — no `pip install`.

**macOS / Linux**
```bash
git clone https://github.com/joseantoniopau/Python-Coding-Gauntlet-Legend.git
cd Python-Coding-Gauntlet-Legend
python3 run.py
```

**Windows** — double-click **`Play on Windows.bat`**, or:
```bat
py -3 run.py
```

> Installing Python on Windows? Tick **"Add python.exe to PATH"** in the installer.

A window opens on a local server bound to `127.0.0.1` with a per-session token.
Nothing is sent anywhere.

**A native macOS app:** `./scripts/build_app.sh` produces a double-clickable
`.app`. It isn't committed here because it's large, platform-specific and
reproducible from that script.

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

`python3 run.py check` verifies all of it and prints what's active.

> **On Windows, layers 1 and 2 do not exist.** There is no seatbelt and no
> `resource` module, so isolation there rests on process separation and the
> wall-clock kill. The code you run is code you wrote, so the threat model is
> "my own infinite loop shouldn't wedge the machine" rather than malware — but
> it is genuinely weaker than the macOS path, and you should know that.

---

## Interview Mode is actually sealed

Adventure Mode teaches. Interview Mode measures. The isolation is enforced
**server-side**, not by hiding buttons: the pattern label is redacted, and hints,
probes, companions, items and the coach are refused at the API. There is a test
suite whose only job is to keep it that way.

The last boss is that mode with the timer on and every crutch gone. The fourteen
bosses before it each remove exactly one, so arriving with nothing is a thing you
were trained for rather than ambushed by.

---

## Development

```bash
python3 tests/run_all.py          # the full suite
python3 run.py check              # verify the sandbox
python3 run.py build-corpus       # rebuild and re-validate every problem
python3 run.py doctor             # diagnose an installation
```

Every problem carries **two independent implementations** — a reference used to
compute expected outputs at build time, and a canonical solution shown to the
player. They must agree on every test, which is how a wrong problem gets caught
before a player ever sees it.

---

## Credits and licence

All art, music and text are **original and generated procedurally** — there are no
image or audio assets in this repository, and nothing is taken from any existing
game. The art direction is documented in `docs/08-art-direction.md` and the story
in `docs/09-story-bible.md`.

Problems tagged as reported interview patterns are **historically reported
shapes, not guaranteed questions**, and name no company.

MIT — see [LICENSE](LICENSE).
