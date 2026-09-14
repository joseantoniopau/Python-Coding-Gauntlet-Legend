# Gauntlet polish delivery

Baseline: clean `7167613`, Fable's explicit completed integration at 2026-09-13 22:59 UTC. Implementation authorized by the user. No original game assets or restoration patch code were imported.

Research: [FFVI feature map and restoration archive analysis](15-reference-research.md). Product and art contracts: `README.md`, `docs/08-art-direction.md`, `docs/09-story-bible.md`, `docs/13-the-first-lesson.md`, `docs/14-the-ramp.md`. Existing runtime tokens in `web/css/metal.css` remain canonical. Existing `main.js`/`uikit.js` own navigation, notifications and dialogs; `editor.js` owns text input; `palette.js` owns sprite palettes; server grading and seals remain authoritative.

## Delivery sequence

1. Reading comfort and encounter layouts: offline display font, scene-scoped CRT, reversible focus layout, keyboard-operable MCQ choices in the main working area. Verify actual code visibility and input preservation, choice submission and failure recovery in an isolated browser session.
2. Actor identity and art: dedicated battle poses, equipped-character preview, expressive portraits, coherent pixels, regions and bosses. Verify in a real-renderer gallery at multiple sizes.
3. Feedback and world: reconcile Fable's sound and companion changes; improve action pacing, learning-linked feedback, music and visible recovery. Verify events against authoritative results.
4. Learning depth: wire existing tutor, then grimoire, tracing, communication drills, investigations, practice choice, expeditions, rematches, keepsakes and rehearsal. Verify assisted evidence, transfer and sealed assessment boundaries.
5. Integrated verification and packaging: targeted suites plus end-to-end browser flows, performance measurements, playtest protocol and rebuilt app. Never claim human testing without participants.

## Original recommendation checklist

Checked items have integrated implementations or completed verification work,
with evidence below. Human participant testing remains a separate, explicitly
unperformed activity described in the playtest protocol.

- [x] 01 Dedicated battle hero sprite.
- [x] 02 Authored combat poses and equipment attachment consistency.
- [x] 03 CRT restricted to scene artwork; code and reading surfaces remain clear.
- [x] 04 Licensed display font bundled for offline use.
- [x] 05 Reversible coding focus layout with preserved buffer and cursor.
- [x] 06 Encounter-specific MCQ and puzzle layout.
- [x] 07 Full equipped-character preview and cosmetic appearance selection.
- [x] 08 Individual expressive portraits used by actual dialogue callers.
- [x] 09 Consistent pixel density and rendering anchors.
- [x] 10 Quieter terrain and readable landmarks.
- [x] 11 Distinct region architecture and lighting.
- [x] 12 Coherent animated metal fantasy with warm/quiet contrast.
- [x] 13 Boss anatomy and phase transformations.
- [x] 14 Combat effects correspond to grading evidence.
- [x] 15 Fast routine resolution and selective dramatic timing.
- [x] 16 Music identity and adaptive arrangements.
- [x] 17 Persisted rebuilding, rescues and world recovery.
- [x] 18 Resumable 10/20/40-minute practice expeditions.
- [x] 19 First-lesson/tutorial wiring and assistance fading.
- [x] 20 Personal grimoire with attempt history and retention evidence.
- [x] 21 Interactive demonstrations and bounded actual-program traces, clearly distinguished.
- [x] 22 Problem-specific communication/explanation criteria.
- [x] 23 Constraint-changing boss rematches.
- [x] 24 Richer Mini-Repo investigations.
- [x] 25 Companion relationships extending existing systems.
- [x] 26 Player steering of adaptive practice.
- [x] 27 Learning-earned cosmetic keepsakes.
- [x] 28 Interview rehearsal distinct from sealed assessment.
- [x] 29 Real-renderer visual gallery and captured evidence.
- [x] 30 Unified rendering contracts and corrected stale documentation.
- [x] 31 Usability/performance verification and human-playtest protocol.

## Implemented contracts and evidence

| Area | Implementation | Evidence |
|---|---|---|
| Battle actors (01, 02, 07, 09) | Separate 40×48 combat rig, six poses, six classes, two bodies, attached equipment, native field rig and cosmetic colors | 4,320 combat-frame checks; maximum 14 colors. Browser applied repository-earned Workshop Patina with unchanged equipment. |
| Reading and controls (03–06) | Offline OFL font, CRT restricted to artwork, 16px code, focus layout, persistent main-panel MCQ choices, native class/file controls | Browser RUN/CAST; focus increased editor from 224.5 to 411.5px at 1280×800 while preserving selection. Incorrect reading answer, coaching, retry and keyboard-corrected answer completed. |
| Cast and world art (08, 10–13) | Individual expressive faces, 57 authored creature bodies plus three fallback bodies, 16 boss archetypes, 12 companion body plans, 17 regional environments, 15 building families and four reconstruction tiers | Actual pixel grids/contact sheets inspected. Regional raster, creature, companion and boss-palette harnesses pass. 14,140 boss samples stay within their palette budget. |
| Motion and audio (14–16) | Grade-driven impacts, live-body dissolve, 384-particle ceiling, shorter routine victories; existing regional music, casts, cries and adaptive arrangements reconciled | FX lifecycle exercises 480 real boss dissolves plus normal/destroyed sequences. Existing audio/FX harnesses pass; cold spell-cache allocations remain separate from steady-state behavior. |
| Cinematics (09, 12, 17) | Shared scene player, actual script rosters, 480×270 plates, camera bounds, native full-cast framing, pause/skip and separate dialogue region | 296 scene samples and shared-player lifecycle tests. Full 28-person formation inspected; gallery fixtures remain explicitly fictional and cannot award a result or record a rescue. |
| Practice (18, 26, 28) | 10/20/40-minute expeditions/rehearsals, balanced/review/weak-skill/fresh selection, pause/resume/finish/history, bounded active-time lease | Real SQLite/HTTP tests cover idempotence, draft continuity, expired leases and assessment seals. Browser created and paused a rehearsal; companion button opened PYTHON practice. |
| Learning records (19–22) | Wired tutorial, assistance fading, personal grimoire, attempt history, notes, bounded actual-Python trace, problem-specific communication prompts | Browser tutorial, saved note/attempt recall and seven-frame banner execution reviewed. Trace suite: 25 tests each on Python 3.11, 3.12, 3.13, 3.14 with actual sandbox; generator/coroutine suspension, limits and public-example boundaries included. Explanation feedback identifies topic coverage, not semantic correctness. |
| Replay and investigation (23–25, 27) | 14-boss rematch manifest with 19 explicit contracts and five new programs, honest finite-variant exhaustion, Mini-Repo file diffs/notes, companion journey and learning-earned colors | Canonical rematches and wrong solutions tested; lineage guards preserve holdouts. Browser repaired pager arithmetic, inspected a one-line diff, passed all 15 tests and submitted. Notes and cosmetics never grade the answer. |
| Gallery and contracts (29–30) | Real-renderer art room, animation/silhouette/beat controls and PNG export; corrected art documentation; public native-Canvas renderer studies | Gallery export creates the exact current-frame PNG in a visible save link. Public studies use the production renderers with native Canvas, not the path/alpha-limited measurement stub. |

## Corpus and assessment integrity

The final isolated corpus validation accepted **1,018/1,018 problems with zero
errors and 52 warnings**. A hidden cyclic-grid case now rejects no-op visited
sets in the BFS scaffold. The banner's auxiliary-space declaration is corrected
to O(n), including the allocated border string. Five rematch variants explain
the increase from the original 1,013.

The **122 sealed IDs are unchanged**, SHA-256:
`07d2e053cd8323c33e27f7d417bc9de234223a0c6b7a8786978f943fe4c3238e`.
Variant lineages remain related to the practice problem they derive from;
rematches do not manufacture unseen-transfer evidence. Legacy attempts without
recorded assistance remain unknown. Reading, scaffold completion, repository
work and independent whole-function writing remain separate evidence types.

The initial corpus build inside the outer automation sandbox rejected Python
subprocesses and was discarded. Validation was repeated with the game's normal
sandbox permissions. The remaining warnings are 17 weak-blank checks, 31 fallback
rungs and four surviving-neighbor warnings; they are not relabeled as errors or
silently suppressed.

## Test and performance record

- Graphics sweep: 45 harness entries, 42 passing checks and three informational
  diagnostics, zero assertion failures. Later navigation, camera and tracing
  regressions were verified after their respective corrections.
- Real client/server harness: 45 HTTP calls, zero failures, including world/town,
  movement, battle, boss phase, portal and a key-free sealed practical. The stub
  reported zero invalid images, non-finite geometry, bad paint or loop allocations.
  This is client/API integration evidence, not a full browser playthrough.
- First broad Python run: 1,597 tests in 1,904.8 seconds, 12 failures, three skips.
  It exposed stale wiring/count assertions, content-derived timing constants,
  new death-ledger state, and misleading mixed-cohort ramp assertions. Fixes and
  targeted corrections were followed by the complete rerun below.
- Final full Python run: **1,618 tests in 1,949.016 seconds, zero failures or
  errors, three skips**. The two tutorial checks requiring a built corpus then
  passed against the validated 1,018-problem corpus. The remaining case is
  inapplicable because every current region has an apex. [Machine-readable result](verification/python-suite.json).
- Native Canvas benchmark on Apple M5 Max / Node 25.8.2: 6,240 warmed draws.
  Battle p95 0.256–0.292ms; cinematic p95 0.190–0.304ms; zero new Canvas instances
  or pixel readbacks during measurement. Cold imports were 83–98ms. Preparing
  all 17 region scenes took 207.5ms; individual battle setup took 13.4–16.4ms
  and first draws 13.3–25.8ms. These are renderer CPU timings,
  excluding browser layout/compositing, complete FX, audio, grading and frame
  scheduling. They are not a browser-FPS guarantee. The [complete benchmark](verification/render-budget.json)
  records source hashes, case coverage, cold costs and measurement limits.
- Ordinary drafts use serialized server writes plus an immediate local recovery
  copy keyed to the actual encounter identity. Deferred-write and offline tests
  cover acknowledgement order; reconnecting must not silently discard input.

## Browser and save isolation

Browser development uses `/private/tmp/gauntlet-codex-polish-20260913` on port
8897. A separate throwaway save on port 8900 runs the destructive progression
harness that opens a sealed exam. Neither modifies the user's real save. Port
8873 was already occupied and was left alone. Public-site preview uses port 8898.

Browser checks cover guided reading, an incorrect answer and retry, assembling
Python, writing/running/casting Python, focus, real-program trace, journal notes,
practice pause, Mini-Repo repair/diff/submission, keepsake selection and companion
practice. Reload and world-resume preserved both code and explanation, including a just-typed
explanation recovered across reload. At 390×844, the focus editor is 234px high
at 16px text, the compact header is 97px high, and the page has no horizontal
overflow. The mobile world renders a full-width 390×405px map above a 339px
scrollable quest panel. Its canvas matches the viewport instead of cropping a
480px minimum plate. Repository panes remain inside 1280px desktop and 390px mobile widths.
At 390×844, cinematic dialogue ends at 751px and pause/skip controls at 844px;
pause and skip were exercised. Title navigation uses real buttons and native
Tab/Enter focus. Packaging and deployment results are appended below.

The escort fixture uses a third isolated save on port 8901. Traveling the actual
Waking Road triggered Thessaly's Slate handover and all its dialogue lines;
closing it restored the world. Opening the interview confirmation and selecting
NOT YET returned to the entry screen without starting the measured run.
Doorstep captions are covered by the consumer harness; instantaneous automated
key taps did not establish a browser movement check.

Death/save regression follow-up: all 46 death tests and 22 save-point tests pass.
Appearance and lesson history survive defeat. Practice notes/history/evidence and
time survive, the plan pauses, and its stale encounter snapshot is discarded
without inventing a completion, retreat or reward.

## macOS package

The app was rebuilt and installed as version **1.1.0**. All **155 source payload
files** in the installed bundle match the repository, and strict recursive
signature verification passed. Its Python sandbox check reported hardened
execution, blocked networking and enforced timeout. Python 3.11 or newer is
required.

The prior installation is preserved in the dated `Gauntlet Legend Backups`
folder alongside the app. The build script now creates this recovery copy
before replacing an existing installation. Packaging does not modify saves or
terminate an already running game; relaunch the app to use the new bundle.

## Publishing

The user authorized committing and pushing to the existing `main` branch at
`joseantoniopau/Python-Coding-Gauntlet-Legend` and updating GitHub Pages. SSH access
works. The existing Pages build deploys `docs/` from `main`; no additional workflow
is required. Workflow reads use the GitHub connector and pushing uses the
existing SSH remote.

The refreshed site includes two actual 1280×800 browser gameplay captures,
original renderer studies, installation instructions,
practice/assessment boundaries, offline font credits and the reference research.
The repository About website now points directly to GitHub Pages; the README
and site canonical URL use the same address. [Capture provenance](verification/browser-captures.json)
records the untouched browser images and their hashes. No game ROM, restoration
patch code or Final Fantasy media is included.

## Limits that remain explicit

[17-playtest-protocol.md](17-playtest-protocol.md) specifies beginner and
intermediate sessions, delayed recall and voluntary-return measures. **No human
participants have been tested yet.** Automated checks do not establish retained
learning, interview readiness outside the measured tasks, enjoyment, or that this
art surpasses Final Fantasy VI. The real FFVI was researched through its manual
and primary design sources; no original-game playthrough was performed here.
