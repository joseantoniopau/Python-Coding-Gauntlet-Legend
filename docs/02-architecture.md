# System Architecture

## Technology choice, and why

The specification asked for a practical local-first architecture and named Tauri
+ React or Electron as candidates, requiring an explicit evaluation.

| Option | Verdict |
|---|---|
| **Tauri + React/TypeScript** | Excellent runtime, but needs a Rust toolchain, a Node toolchain and a multi-minute build. A Python sandbox would still have to be shelled out to. The build chain is a permanent tax on a single-player local tool. |
| **Electron** | Ships a ~150MB Chromium per copy for a game that renders 16×16 tiles. Not justified. |
| **Native SwiftUI / AppKit** | Best window integration, but reimplements a code editor, a syntax highlighter and a Python sandbox in a language the content pipeline is not written in. |
| **Chosen: stdlib Python service + vanilla ES-module frontend, wrapped in a macOS `.app`** | Zero dependencies, so it cannot rot. Instant start. The Python sandbox is first-class rather than shelled out to. The whole thing is one `rsync` to install. Renders crisply at integer scale. |

The decisive argument: this program's hardest requirement is **safely executing
untrusted Python with hard resource limits**. Every other stack solves that by
shelling out to Python anyway. Building the app *in* Python makes the
safety-critical path the native path, and costs nothing the product needed.

The frontend is ES modules with no build step: `<script type="module">` loads
`main.js`, which imports the rest. Edit a file, reload, done.

```
┌─────────────────────────────────────────────────────────────┐
│  Python Coding Gauntlet Legend.app                          │
│  ├── MacOS/GauntletLegend      resolves python3, execs      │
│  └── Resources/app/            a self-contained copy        │
└──────────────────────────┬──────────────────────────────────┘
                           │
      ┌────────────────────▼────────────────────┐
      │  gauntlet.launcher                      │
      │  build corpus → serve → open window     │
      └────────────────────┬────────────────────┘
                           │
   ┌───────────────────────▼───────────────────────┐
   │  gauntlet.server   127.0.0.1 only             │
   │  token + origin guard, static files, JSON API │
   └───────┬───────────────────────────┬───────────┘
           │                           │
   ┌───────▼────────┐          ┌───────▼─────────────────────┐
   │ gauntlet.engine│          │ web/  (ES modules, canvas)  │
   │ the game       │          │ overworld · battle · viz    │
   └───┬────────┬───┘          │ editor · pixel art · audio  │
       │        │              └─────────────────────────────┘
  ┌────▼───┐ ┌──▼──────────────┐
  │ db     │ │ sandbox         │
  │ sqlite │ │ seatbelt+rlimit │
  └────────┘ └─────────────────┘
```

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | Paths, tuning constants, mode names. The only place magic numbers live. |
| `sandbox.py` | Safe execution of player code. Four containment layers. Returns a structured report. |
| `_harness.py` | Runs *inside* the child. Never imports the package. Compiles, executes, runs tests, writes JSON. |
| `corpus/` | Problem schema, family builders, the generator, the validator. |
| `skills.py` | The skill model. The only place mastery moves. |
| `srs.py` | Spaced repetition over patterns, with disguised variant selection. |
| `grading.py` | Failure classification, ranks, XP, combat feedback language. |
| `adaptive.py` | Encounter selection, training camps, remediation, daily quests, readiness. |
| `tactics.py` | Enemy weaknesses/resistances, the Probe, damage resolution. |
| `items.py` | Loot, equipment, sets, attributes, builds, secrets. |
| `world.py` | Regions, bosses, mentors, companions, weapons, armour, titles, achievements. |
| `coach.py` | Post-attempt Socratic coaching. Refuses to exist in Timed Practical Mode. |
| `db.py` | SQLite persistence. Hybrid: JSON blob for live state, tables for history. |
| `engine.py` | The game. Every client action passes through here so invariants live in one place. |
| `server.py` | Local HTTP. Token + origin guard. |
| `launcher.py` / `cli.py` | Entry points. |

## Data model

A deliberate hybrid.

**`state` table** holds one JSON blob: player, skills, SRS schedule, inventory,
equipment, attributes, armour, achievements, settings. Single-player local state
with no concurrent writers does not need normalising, and a blob means adding a
field never requires a migration — `_merge` folds a newer default structure over
an older save.

**Normalised tables** hold what genuinely needs querying:

- `attempts` — every submission: problem, pattern, family, difficulty, mode, rank,
  hints, seconds, runs, syntax errors, tests passed, first-try, retest, root
  cause, declared pattern, time-to-first-code, and the submitted source.
- `boss_records` — per-boss attempt history, for the "first battle 22:31 / now
  11:48" progression view.
- `interview_runs` — scored timed practicals.
- `sessions` — session bookkeeping.

WAL mode, `synchronous=NORMAL`, and an atomic upsert on every action. Export and
import produce a single portable JSON file.

## The sandbox, in detail

```
parent (gauntlet.sandbox)
  └── sandbox-exec -f profile.sb          ← layer 1: seatbelt
        └── python3 -I -S -B harness.py   ← isolated, no site-packages, no PYTHONPATH
              ├── rlimits applied in preexec_fn   ← layer 2
              │     RLIMIT_CPU, RLIMIT_AS, RLIMIT_FSIZE, RLIMIT_NPROC
              ├── parent-side subprocess timeout  ← layer 3
              └── per-test signal.setitimer       ← layer 4
```

The seatbelt profile denies everything by default, then allows process
exec/fork, sysctl reads, all file reads, and writes **only** inside the run's
scratch directory. It explicitly denies `network*` and writes anywhere under the
real home directory. Subpaths are resolved with `os.path.realpath` because
seatbelt matches physical paths, not the `/var` symlink.

The environment is scrubbed: `HOME` and `TMPDIR` point at the scratch directory,
`PATH` is `/usr/bin:/bin`, `PYTHONHASHSEED=0` for determinism.

Results are written to a file rather than stdout, so the player's own `print()`
output stays pristine and can be shown verbatim in the battle log.

**Adapters.** Tree problems hand the player a real linked `TreeNode` so the
encounter tests actual node relationships. Tests travel as level-order
lists; the harness converts them using the `TreeNode` class defined in the
problem's own preamble, so `isinstance` and identity behave correctly.

**Type preservation.** JSON turns integer dict keys into strings. Dicts with
non-string keys are tagged as `{"__map__": [[k, v], …]}` at build time and
rebuilt in the child, because `{1: 'a'}` silently becoming `{'1': 'a'}` would
make every such test quietly wrong. This was caught by corpus validation, not by
inspection.

## HTTP API

Bound to `127.0.0.1` only. Every `/api/*` call requires the `X-Gauntlet-Token`
header, whose value is generated per process and injected into `index.html` at
serve time. Cross-origin requests are refused. Static file serving resolves and
range-checks every path against the web root.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Full dashboard: player, skills, regions, bosses, readiness, loadout, quests |
| GET | `/api/world` | Static world data |
| GET | `/api/loadout` | Equipment, inventory, attributes, set bonuses, secrets |
| GET | `/api/history` | Attempt, boss and timed practical history |
| GET | `/api/sandbox/check` | Live sandbox verification |
| POST | `/api/encounter/next` | Adaptive selection (retests take priority) |
| POST | `/api/encounter/start` | Start a specific problem |
| POST | `/api/run` | Visible trials only, ungraded |
| POST | `/api/submit` | Graded submission |
| POST | `/api/mcq` | Answer a recognition / complexity / reading encounter |
| POST | `/api/probe` | Spend a probe charge |
| POST | `/api/hint` | Cast a learning spell |
| POST | `/api/explain` | Score a typed approach explanation |
| POST | `/api/equip` · `/api/unequip` · `/api/allocate` · `/api/build` · `/api/respec` · `/api/consumable` | Loadout |
| POST | `/api/boss/start` · `/api/boss/ladder` | Boss flow |
| POST | `/api/interview/start` · GET `/api/interview/current` · POST `/api/interview/finish` | Timed Practical Mode |
| POST | `/api/search` | Hunt for a hidden location |
| GET/POST | `/api/export` · `/api/import` | Save portability |

## AI architecture

AI is an optional accelerant and never a dependency. Core gameplay, code
execution, deterministic scoring and offline problem solving never call a
provider. `coach.provider_name()` reports whether one is configured; with none,
the Socratic coach still works from the failure classification, the test
evidence and the player's own history.

`coach.available_in(mode)` returns `False` for Timed Practical Mode. The provider is
not merely unused there — the code path is not entered.
