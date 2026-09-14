# The first lesson

The violet cue in a battle, and the schoolteacher who walks you round the game
once so that every later zone is a place you already know how to stand in.

Two things the player asked for, in their own words:

> "the ui should have that purple arrow on what to click next thats subtle but
> shows the user what their options are in a battle. the first companion should
> walk the user through all the features and how to use them as well as town
> folks and how to repair armor upgrade purchase etc so the user will know how
> to use them going forward into new areas"

This document DECIDES. Where a number is stated it is the number. Where a choice
was close the losing option is named and the reason it lost is given, so that a
later pass re-opens the argument on purpose rather than by accident.

**Nothing in this document is implemented.** §7 is the work list, and it names
files that are owned by concurrent passes rather than editing them.

---

## 0. What already exists, scouted rather than assumed

Every row was read out of the file named. **Line numbers drift**: `main.js`
grew by ten lines between the first and the second reading of it during this
pass, because a concurrent pass owns it. Every citation therefore carries a
symbol or a `grep` anchor, and **the anchor is the authority; the number is a
convenience.** Numbers are as of `main.js` 8,507 lines, `game.css` 894,
`metal.css` 1,313.

| Fact | Source | Consequence |
|---|---|---|
| `--violet: #a89aff` | `web/css/game.css:15` | The colour the player asked for is already a token |
| **`metal.css` overrides it to `#b06cff`** and loads second | `web/css/metal.css:40`, `web/index.html:9` | **The shipped violet is `#b06cff`, not `#a89aff`.** Use `var(--violet)` and the cue follows the skin. Never hard-code either. |
| `.btn.primary` is already `#3b2f66` with a violet border; under metal it is a `#4a2f8c → #150c28` gradient with a `--violet` border | `game.css:73`, `metal.css:302` | **A violet cue at low opacity vanishes on the CAST button.** §2.2 solves this with a black keyline rather than a second colour. |
| `.btn::after` is TAKEN — a specular skim on every button | `metal.css:269` · `.btn::after` | **The cue may not be a `::after` on its target.** It is a real element. |
| `.btn.small { padding: 7px 9px }` — **unscaled**, while only `font-size` multiplies by `--scale` | `game.css:76` · `.btn.small` | **The cue is in device pixels and never multiplies by `--scale`.** The padding it lives in does not. |
| `.list-item { padding: 9px 10px }`, `#battle-side-body { padding: 12px }` | `game.css:537` · `.list-item`, `game.css:390` · `#battle-side-body` | A 1px overhang outside a list item lands in the panel's own padding |
| `#battle-side-tabs button { padding: 9px 2px }`, five across 360px | `game.css:384` | **There is no horizontal room inside a tab.** The tab cue uses the bottom padding — §2.1, placement UNDER. |
| `body.reduced-motion *, *::before, *::after { animation: none !important }` | `metal.css:1215`, `game.css:590` | **The cue must be legible with every animation dead.** Motion is decoration, never the signal. |
| `#editor-caption` already points DOWN at the editor and names the CAST button, driven from the same string as the button | `index.html` · `#editor-caption`, `main.js:249` · `setEditorMode` | **The cue never points at the editor.** That box already has a label and two labels on one box is worse than one. |
| `#answer-here .ah-arrow i` is already a violet `▶` animating `translateX(7px)` over `1.3s` | `game.css:373-378` · `#answer-here .ah-arrow` | The MCQ pane already has an arrow. §4 retunes it rather than adding a second one. |
| `explainBlank()` — say it once, latch it, never again | `main.js:1389` · `explainBlank` | The house pattern for "a lesson taught is taught" already exists |
| `setEditorMode(mode, verb)` switches `code` / `puzzle` / `mcq` / `incant` by showing and hiding `#editor-caption`, `#answer-here`, `#btn-run`, `#btn-submit` | `main.js:249-264` · `setEditorMode` | **The screen already knows which kind of encounter it is.** The cue reads the DOM and needs no argument. |
| `document.body.classList.toggle('interview-mode', payload.mode === 'interview')` | `main.js:1231` · `enterBattle` | A measured run is one class on `<body>` |
| MCQ answer keys in the shipped corpus: **`answer=0` seven times, `answer=1` twice** | `grep -rhoE 'answer=[0-9]+' gauntlet/corpus/families/` | **DECISIVE. The cue may never point at a choice.** §4. |
| `p.mcq["answer"]` is an authored index and `api.mcq(i)` posts an index, so the order the client renders is the order the corpus authored | `corpus/validate.py:178`, `main.js:2784` | The choice list is not shuffled per serve. The bias above is a bias the player would see. |
| Six puzzle kinds, each with its own DOM: `.rune-tray .rune`, `.trace-row input`, `.code-pick .cl`, `input.puzzle-input`, the six BREAK_IT quick buttons, the COMPLEXITY_MATCH option buttons | `puzzleui.js` · the six `BUILDERS` | §4 decides each one separately, and refuses three of them |
| `finalexam.CRUTCHES` — **fourteen** named capabilities, `HINTS`, `MENTOR`, `PET`, `WEAKNESS_MAP`, `PATTERN`, `COACH` among them | `finalexam.py:135` · `CRUTCHES` | The complete enumeration of what a measured run must not see |
| `Game._run_is_open()`, `Game._sealed_for(cap)`, `Game._pays_into_the_world(enc)` | `engine.py:2341`, `2348`, `2321` | The gap clause. Ask the RUN, never the encounter. |
| `captives.available_in(mode)` → `mode != MODE_INTERVIEW`; `zonecompanions.available_in` defers to it | `captives.py:1597`, `zonecompanions.py:640` | **Thessaly already does not exist in a measured run.** The gate is built. |
| `zonecompanions.py` is **already written** — 1,500 lines, `ESCORTS`, `state_of`, `advance`, `capture`, `hand_over_early`, `snapshot`, `sweep_fired` | `gauntlet/zonecompanions.py` | Thessaly Brun is row one. Her `walking`, `capture`, `narrator`, `loss_line`, `thanks`, `handover` and `retaken_line` are authored. **This document does not rewrite one word of them.** |
| Thessaly's own `verb`: building captions and route captions, *"She never says anything about a problem; she says things about places."* | `zonecompanions.ESCORTS[0].verb` | The curriculum is the same person keeping the same promise, extended from places to interfaces |
| `sweep_fired` needs `bug_demon` **and** twelve of fourteen rungs, because `rt_armorers_stair` is one hop from the village square at `Need(kind='none')` | `zonecompanions.py:680-698` · `SWEEP_MIN_RUNGS`, `sweep_fired` | She cannot be swept away during the tutorial. The curriculum has room to finish. |
| `death.py`: dying costs gold, position, inventory, loot and the minutes since the last save, and never touches attempts, skills, mastery, the schedule or the records — `restore_history=False` | `gauntlet/death.py:1-40` | Beat 9 says this in her words, and it is true |
| `set_setting(key, value)` writes any key into `state["settings"]` and saves | `engine.py:9591` · `set_setting` | A new setting costs one default and one checkbox |
| `startTimer()` already runs a 500 ms interval for the whole of a battle | `main.js:2791` · `startTimer` | **The cue needs no interval of its own.** A second interval is a second interval to leak. |
| **`body.interview-mode` already desaturates the token**: `--violet: #8a90a8` in `game.css`, `#7e8496` in `metal.css` | `game.css:571`, `metal.css:1109` | **A third, accidental lock.** Even if a cue leaked into a measured run it would render grey — the measured run is already deliberately drained of the tutorial palette. Found while re-verifying line numbers, not by design. |
| `body.high-contrast` raises the same token instead: `--violet: #cfa2ff` | `metal.css:136` | §2.4 pins the cue's inner opacity to 1.0 under high contrast, which is the same direction |

**There is no tutorial or onboarding system of any kind in this project.** This
is greenfield, and that is why it is worth writing the rule down before the
code exists rather than after six call sites have each decided it separately.

---

## 1. THE CUE

### 1.1 What it is

One violet triangle, six pixels wide, sitting on the left edge of the single
control the player should press next. There is exactly **one** of them in the
document, ever. It moves; it is never cloned.

It is called **the cue** in code — `web/js/tutor.js`, class `.cue`, host class
`.has-cue`. It is not called a hint, a tip, a coach or a pointer, because three
of those four are names of things `finalexam.CRUTCHES` switches off and the
fifth would be mistaken for one inside a year.

### 1.2 The player asked for the options, plural. They get one arrow. Why.

Five arrows is a Christmas tree, and a Christmas tree is not a next action — it
is the same screen with more on it. The brief already resolved this correctly
("a SUBTLE NEXT-ACTION ARROW"), and the half of the request that the singular
drops is paid back somewhere better:

- **The options are named once, in words, by Thessaly**, at the mouth of the
  first encounter — beats 3 and 4, §5. Two breaths, and no control named
  before the screen that holds it exists.
- **The keys are already on the screen, permanently**, in `#editor-caption`'s
  `.ec-keys` strip: `CTRL/⌘+↵ RUN · SHIFT+CTRL/⌘+↵ CAST · ESC LEAVES THE BOX`.
- **The cue then points at one of them at a time**, which is what "what to click
  next" literally asks for.

### 1.3 The hard part: interface, or problem?

`docs/10-sealed-views.md` is the rule this has to live under:

> A measured run may see the WORLD. It may not see the PROBLEM.

An arrow is not a view, so doc 10's three questions do not apply to it word for
word. But its *reason* applies exactly, and the reason is the swap test:

> **The swap test, for a cue.** If the question on the screen were swapped for a
> different one, would the cue point somewhere else, or appear at a different
> moment? If yes, the cue is about the problem.

That single question decides every row below.

#### The table

Every state the cue could point in. **Verdict** is INTERFACE (allowed) or
PROBLEM (refused, forever, in every mode).

| # | State the cue would fire in | It would point at | Verdict | Why |
|---|---|---|---|---|
| 1 | A code fight is open and the player has not pressed RUN yet | `#btn-run` | **INTERFACE** | "There is a button that tries your code." True of every code fight ever served. Swap the question: identical. |
| 2 | A code fight is open and the player has pressed RUN at least once | `#btn-submit` | **INTERFACE** | "There is a button that answers the question." *That* you ran is a fact about the control. *What happened when you ran* is not read. |
| 3 | The visible trials all passed and the player has not cast | `#btn-submit` | **PROBLEM** | Reads the run report. This is "your solution looks right, submit it" — `COACH` wearing an arrow. Swap the question: different answer. |
| 4 | A visible trial failed | the TRIALS tab, or the failing line | **PROBLEM** | Pure `WEAKNESS_MAP` and `COACH`. The single most tempting cue in the game and the most clearly refused. |
| 5 | A hidden trial failed | anything | **PROBLEM** | Worse than 4: the hidden trials exist precisely to withhold this. |
| 6 | The player has been idle for a long time and is doing badly | `#btn-flee`, SPELLS, the Mender | **PROBLEM** | "You are losing, go and get help" is `MENTOR` plus a judgement of the attempt. |
| 7 | The clock is past `target_seconds` | anything | **PROBLEM** | `UNLIMITED_TIME` is rung 10 of the ladder. An arrow that appears because time passed is a clock crutch. |
| 8 | The starter code holds a `__BLANK__` slot | the slot | **INTERFACE**, but **refused anyway** | `explainBlank()` (`main.js:1389` · `explainBlank`) already says this once, in words, better. Two explanations of one thing is worse than one. |
| 9 | An MCQ is open and the choices are on screen | the first `.list-item` | **PROBLEM — measured** | **Seven of nine shipped MCQ answer keys are index 0.** An arrow on the first choice is right 78% of the time in the corpus that exists today. Refused on evidence, not on principle. |
| 10 | An MCQ is open and the player has switched off the TRIALS tab | the TRIALS tab button | **INTERFACE** | "The answers live in that panel." Geography of the screen. Points at a container, never at a member of it. |
| 11 | A RUNE_ASSEMBLY puzzle is open | the first rune in THE PILE | **INTERFACE**, conditionally — see §4.3 | The pile is `mcq.shuffle`. Position in a shuffle carries no ordering information. **This is the one row with a tripwire.** |
| 12 | A SPOT_THE_FLAW puzzle is open | the first code line | **PROBLEM** | The question is *which line*. An arrow on a line is the answer with a triangle in front of it. |
| 13 | A COMPLEXITY_MATCH puzzle is open | the first option button | **PROBLEM** | The question is *which option*. Same shape as 12. |
| 14 | A BREAK_IT puzzle is open | one of the six quick-input buttons (`empty`, `duplicates`, `negatives`…) | **PROBLEM** | Those buttons are named edge cases. Pointing at one is `WEAKNESS_MAP` delivered as a suggestion. |
| 15 | Any puzzle, once `ready()` has enabled the submit button | `#btn-submit` | **INTERFACE** | "There is a button that answers." Reads `disabled`, which is a property of the control. |
| 16 | The editor is empty and unfocused | `#editor-host` | **INTERFACE**, but **refused anyway** | `#editor-caption` owns this box and has since the "I can't tell where to type" pass. See §2.3 — the cue never covers text. |
| 17 | Health is low and a potion is on the belt | a `.chud-belt` slot | **INTERFACE** by the swap test | …and still refused in a fight. Moved to Thessaly, beat 21 (§5), because the belt's lesson is *"this is the one thing that does not end your turn"* and that is a sentence, not an arrow. |
| 18 | A result modal is open with one way forward | the modal's own button | **INTERFACE** | The modal is chrome. Out of scope for this pass; listed so the next contributor knows it was considered and not forgotten. |
| 19 | An incantation fight is open | `.inc-cast` | **INTERFACE** | Same shape as row 2. `IncantationUI` owns the pane and carries its own cast control (`incantui.js:315`). |
| 20 | A measured run — any of the above | anything | **REFUSED**, unconditionally | §1.5. |

#### The four facts, and there is no fifth

The reason rows 3–7 are easy to get wrong is that a cue implemented as "watch
everything and decide" has no boundary. So the boundary is a *diet*, stated as
a list, and the list is the enforcement:

> **The cue may read exactly four things:**
>
> 1. **KIND** — which of `code` / `mcq` / `puzzle` / `incant` the screen is in.
>    Read from the DOM (`#editor-caption`, `#answer-here`, `#puzzle-host`
>    visibility), never passed in.
> 2. **ELIGIBILITY** — for each control in the registry: is it in the document,
>    not disabled, and actually rendered.
> 3. **USE** — how many times the player has pressed each control, in this
>    encounter and in this save. A count of presses. Never an outcome.
> 4. **IDLE** — milliseconds since the last keystroke, click or key in this
>    encounter.
>
> It may not read the problem, the statement, the pattern, the starter code, the
> run report, the trial results, the grade, the score, the timer, the enemy, the
> player's skills, the hint tree, or anything derived from any of them.

`idle` is the one that carries weight and it is the one that is safe: a
millisecond count cannot encode anything about a Python question. It is also
the right trigger for the thing the player actually described — the cue appears
when you have *stopped*, which is when you are looking for the button, and it
never appears while you are typing, which is when it would be a distraction.

#### The sentence a future contributor cannot misread

> **The cue may point at a control because of what the control IS, and never
> because of what the last attempt DID.**

Checkable in one step. If the trigger you are about to write reads a report, a
grade, a test, a hint, a pattern, a skill number, a clock or the problem body,
it is refused, whatever else is true about it.

The second sentence, for the case the first does not obviously cover:

> **The cue points at containers, never at members of a set the player is being
> asked to choose from.** A tab, yes. A choice, a code line, a complexity, an
> input case: never.

### 1.4 The losing arguments, named

**"The failed-trial arrow is the most useful arrow in the game."** It is. It is
also `WEAKNESS_MAP` and `COACH`, the two crutches the ladder takes at rungs 3
and 9, delivered through a channel nobody thought to seal. Rejected.

**"Seal it per-capability instead of switching it off."** That means thirteen
capability checks in a renderer, re-derived every time somebody adds a control,
and it is exactly the six-arguments-for-one-line problem `docs/10` was written
to end. Rejected in favour of one diet and one off switch.

**"Let the arrow be smart when the run is not measured."** This is the real
temptation, because outside a run there is nothing to violate. It is rejected on
a different ground: a cue whose rules change between modes is a cue with two
behaviours, and the second one is the one nobody tests. One behaviour, one diet.

### 1.5 OFF in a measured run, and there are two independent reasons

`body.interview-mode` is on the document whenever `payload.mode === 'interview'`
(`main.js:1231` · `enterBattle`). While it is on, **`tutor.js` places nothing and
the CSS hides the node anyway.** Two mechanisms, either sufficient — and a third
that was already there before this design: `body.interview-mode` redefines
`--violet` to `#8a90a8` in `game.css:571` and `#7e8496` in `metal.css:1109`, so a
cue that got past both locks would render grey. The measured run was drained of
the tutorial palette by somebody else, which is some evidence that the split
below is the one this project already believed in.

**But `interview-mode` is the wrong signal to gate on, and all three of those
locks have the same hole.** It goes on in `enterBattle` and comes off in
`returnToWorld()`, at `document.body.classList.remove('interview-mode')` —
`main.js:3858` as of this writing, and the **anchor** is the authority because a
concurrent pass is moving that file — which RETREAT reaches **while the run is
still open server-side**, and `docs/10` §4b.I establishes that the player is on
the overworld *between two questions* of a measured run. `G.interview = null` is
two lines below it, so both client signals are absent for the whole of that
gap — which is precisely where §7.4 M13 hangs five `tutor.beat()` calls.

So the seal is carried from the server instead. `Game._run_is_open()` is the
engine's own answer — true for `state["interview"]`, `state["exam"]` and an
encounter opened in Interview Mode, open question or not — and it reaches the
client twice over:

- **the lessons** need no client check at all: `/api/lesson` returns `{}` while
  the run is open, and `gauntlet/tutorial.py` defaults `run_open` to `True`, so
  the server refuses a client that forgot to ask;
- **the cue**, which has no round-trip per frame, reads `run_open` off
  `/api/state` and `main.js` mirrors it onto the body as its own class,
  `body.run-open` (`tutorial.CUE_POLICY["sealed_body_class"]`), set and cleared
  from that boolean alone. `game.css` hides `.cue` under **both** classes.

`interview-mode` keeps its rule because it is free and true while a question is
up. `run-open` is the one that closes the gap.

**Reason one — comparability, and this is the stronger one.** The MENU already
says it: *"Interview Mode uses standardised constraints so the measurement stays
comparable."* A cue that is present for a player on their third fight and
retired for a player on their fortieth is a difference between two runs that
were supposed to be the same measurement. The only setting that is the same for
everybody is *absent*.

**Reason two — the cheapest correct answer to "is this hint sealed?" is to not
have the hint there at all.** The brief's position, and it is right. An arrow
that is off cannot be argued about, cannot leak through a diet somebody widened
in 2027, and cannot be the fourteenth crutch nobody added to the list.

**And the objection has to be answered, because it is real.** A player may sit
the practical as the first thing they ever do — `finalexam.py` says so in
capitals and `PRACTICAL_IS_NEVER_GATED` exists so that changing it means
deleting a constant that says not to. Turning the cue off removes interface help
from exactly the player who has never seen the interface.

It is answered by the fact that **the interface help a measured run needs is the
static kind, and it is already there and already always on**:

- `#editor-caption` is hidden only by `mode !== 'code'`, never by the seal — it
  is on the screen in a measured run, saying `WRITE YOUR PYTHON HERE ▾` and
  `THEN PRESS CAST ✦`, with the keyboard strip beside it.
- `#answer-here` is on for every measured MCQ, saying where the answers are.
- The editor's focus ring and its placeholder are unconditioned.

So the measured run keeps every label and loses the animated, stateful layer.
That is the correct split: **labels are furniture, cues are tuition, and a
measurement furnishes the room without tutoring the candidate.**

---

## 2. SUBTLE, numerically

### 2.1 The numbers

All lengths are **device pixels and do not multiply by `--scale`**, because the
paddings the cue lives in do not either — `.btn.small` is `padding: 7px 9px`
with no `calc()`. At a text scale of 1.5 the cue therefore becomes *smaller*
relative to the type around it, which is the correct direction for a thing whose
whole job is to not be loud.

| Property | Value | Why this number |
|---|---|---|
| Glyph | a CSS `clip-path` triangle, not a font character | `Press Start 2P` is loaded via `local()` only and does not carry `▶`; a clip-path renders identically on every machine and stays crisp under `image-rendering: pixelated` |
| Outer size (EDGE) | **7 × 9 px** | Smaller than a capital in the 10px button face beside it |
| Inner size (EDGE) | **5 × 7 px**, offset 1px | Leaves a 1px dark keyline on all three sides — §2.2 |
| Offset | `left: -3px`, `top: 50%` | Sits across the host's 2px border: 3px inside the padding, 1px outside the box |
| Worst-case clearance to text | **5 px** on `.btn.small`, 6px on `.list-item`, 10px on `.btn` | `* { box-sizing: border-box }` is global, so content starts at border + padding: 2+9, 2+10, 2+14. The cue's peak reaches x=6 from the border-box edge. |
| Colour | `var(--violet)` | `#b06cff` shipped, `#a89aff` if `metal.css` is absent. **Never hard-coded.** |
| Keyline | `#04030a`, opaque | The CAST button is violet-on-violet — §2.2 |
| Opacity, inner, at rest | **0.55** | Reads on `--panel-2` (`#14141d`) without competing with the gold button faces |
| Opacity, inner, at peak | **0.85** | The whole of the "breathing" |
| Opacity, outer keyline | **1.0, never animated** | So the shape is legible on any ground at every point in the cycle |
| Period | **2.4 s** (0.42 Hz) | See below |
| Amplitude, EDGE | **2 px** rightward | Half a character width. Visible as presence, not as travel. |
| Amplitude, UNDER | **1 px** upward | 2px would put the peak 1px inside the tab's content box. 1px lands the peak exactly flush with it. |
| Easing | `ease-in-out` | No sudden edge anywhere in the cycle |
| Layout cost | **zero** — `position: absolute`, `pointer-events: none` | §2.3 |
| Reduced motion | animations dead, inner opacity pinned to **0.78** | `body.reduced-motion *` kills animation with `!important`; the cue must still read |
| High contrast | inner opacity **1.0** | `metal.css` flattens decoration under `.high-contrast`; the cue is not decoration |
| Count on screen | **exactly one** | One node, moved |

**Why 2.4 s.** The existing `ah-nudge` is 1.3 s and 7 px. That was written for a
one-off explainer box on a screen with nothing to type on; on a screen where the
player is writing Python it is too fast and too far. 2.4 s is 0.42 Hz. The eye's
sensitivity to motion peaks roughly an order of magnitude above that, in the
4–20 Hz band, which is why a slow drift reads as *something is there* rather
than as *something moved*. A full cycle is also longer than the pause between
two keystrokes at any normal typing cadence, so the movement is never adjacent
to a keypress. Combined with the 2 px amplitude, the cue is the slowest and
smallest animated thing on the battle screen by a wide margin — `ec-blink` is
1.1 s, `ah-nudge` is 1.3 s, the health alarm is faster than both.

**`ah-nudge` is retuned to 2.4 s / 3 px in the same pass**, so the battle screen
speaks one motion vocabulary instead of two. That is the only change this design
makes to a thing that already exists.

### 2.2 Two placements, and the keyline that makes the CAST button work

**Placement EDGE** — the default, and the Final Fantasy menu cursor the player
was describing. The cue sits on the host's left edge pointing right, into the
thing you press. Used for `.btn`, `.btn.small`, `.list-item`, `.rune`,
`.inc-cast`.

**Placement RIM** — added after §2.4 was written, for a panel edge rather than
a control. `left: 0` puts the cue on the panel's own border instead of 3px
outside it. **A RIM host must not be a scroll container.** `.has-cue` makes its
host `position: relative`, so the cue's containing block is that host's padding
box — and if the host scrolls, the cue scrolls with the content. The host is
`#battle-side`, not `#battle-side-body`: the body computes `overflow: auto`, and
measured at 1440x940 with a fourteen-row trials list (scrollHeight 682,
clientHeight 403) a cue on it moves 279px at scrollTop 279, ending 81.8px above
the panel's own top edge and clipped out of view. `#battle-side`'s padding box
starts at x=1083 — the identical pixel — it is `overflow: hidden` and
non-scrollable, and the cue does not move at all when the list scrolls.

**Placement UNDER** — for a host with no horizontal room. The cue sits in the
host's bottom padding, centred, pointing up. Used for exactly one target: a
`#battle-side-tabs button`, where five tabs share 360px at `padding: 9px 2px`
and there is no left padding to live in. The 9px bottom padding holds a 7px cue
at `bottom: 1px` with 1px of travel and lands flush with the content box, never
inside it.

**The one measurement the wiring pass should confirm rather than trust.** The
cue overhangs its host's left edge by 3px. Every target measured here has
somewhere for that to go — `#editor-toolbar` has 12px of padding and an 8px gap
between buttons, `#battle-side-body` has 12px — but `.inc-cast` lives inside
`IncantationUI`'s own `this.actions` row, which this pass did not measure. If it
overhangs a sibling there, move that one target to UNDER rather than changing
the global offset.

**Why the cue is a real element and not a `::after`.** `metal.css:269` · `.btn::after` gives
every `.btn` a specular skim on `::after`. A pseudo-element has exactly one box:
a cue written as `[data-cue]::after` would delete the skim from whichever button
it pointed at, and the button would visibly change material while cued. So the
cue is a single `<i class="cue">` appended as the last child of its host, with
`z-index: 2` so it paints above the skim rather than under it.

**Why the keyline.** Under `metal.css` the CAST button is
`linear-gradient(#4a2f8c, #2a1a4d, #150c28)` with a `--violet` border. A violet
triangle at 55% opacity on that ground is close to invisible, and CAST is the
single most important thing the cue ever points at. The answer is the 16-bit
answer: the sprite gets a dark keyline. `.cue` is an opaque near-black triangle;
`.cue::after` is the violet triangle inset by 1px inside it. The violet then
reads against black on every ground in the game, and only the inner triangle
breathes.

**And the keyline was not enough on CAST, which is the placement it was written
for.** Colour independence is not legibility: the keyline guarantees the cue's
rendered colour does not depend on the ground, and it delivers that — measured,
the inner triangle renders the same rgb on all six EDGE grounds. What it does
not fix is that on `.btn.primary` the cue's own violet sits *on the button's
own violet border*. Rendered at 12x and looked at, it reads as a dark **notch
cut into the keyline** rather than as an arrow. The numbers, 1440x940, `body.crt`
on, animation pinned at the peak of the breathe: the cue's violet is
`rgb(151,91,215)` against a border rendering `rgb(175,108,248)` — **1.32:1** —
and **3.51:1** against the local ground, the lowest of the six EDGE placements
(panel RIM 4.47, `.list-item` 3.89, RETREAT 3.71, RESET 3.62, RUN 2.86).

One rule fixes it with a token `metal.css:41` already defines:

```css
.btn.primary .cue::after { background: var(--violet-hi); }   /* #dcb4ff */
```

That lifts the CAST cue to `rgb(186,149,215)` and **6.13:1** against the same
ground, leaves every other placement byte-identical (re-measured after
shipping it: RUN, RESET, RETREAT, `.list-item`, RIM and UNDER all unchanged to
the pixel), and touches exactly the two controls it is for — `#btn-submit` and
`.inc-cast` are the `.btn.primary`s the cue policy names. **The keyline stays.**
It is doing a different job and it is doing it correctly.

### 2.3 What it must NEVER do

These are prohibitions, not preferences.

1. **Never cover text.** It lives inside the host's existing padding, with a
   measured minimum of 3px clear at the peak of its travel. It never enters
   `#editor-host`, any `<textarea>`, any `<input>`, `#problem-statement`,
   `#problem-examples` or `.spell-body`. `tutor.js` refuses any host that
   `closest('#editor-host')` matches, and the registry lists selectors rather
   than accepting arbitrary nodes. Worst measured clearance is **5px**, on a
   `.btn.small`, at the peak of the drift.
2. **Never move layout.** `position: absolute` inside a `position: relative`
   host, `pointer-events: none`, no margin, no padding, no width contribution.
   The host gains one class (`.has-cue`, which sets `position: relative` and
   nothing else) and one child. Adding and removing the cue must produce a
   byte-identical layout.
3. **Never animate fast enough to catch peripheral vision.** 0.42 Hz, 2px, one
   axis, `ease-in-out`. No flash, no blink, no colour change, no scale, no
   rotation, no shadow pulse. Only `transform` and `opacity` animate — the rule
   `metal.css` states for the whole skin, because the battle canvas needs the
   frame budget.
4. **Never be the only signal.** Everything the cue points at is also named in
   words somewhere on the same screen or in Thessaly's curriculum. A player who
   cannot see violet loses nothing.
5. **Never make a sound.** There is an `audio.sfx()` in scope at every call
   site. A cue that dings is a nag with a speaker.
6. **Never appear on a disabled or hidden control.** §4.1.
7. **Never appear more than once on screen.** One node exists.
8. **Never appear in a measured run.** §1.5.

### 2.4 The CSS, ready to paste

Insertion point: `web/css/game.css`, immediately after the `#answer-here` block
(currently ending at the `@keyframes ah-nudge` on line 378) and before
`#battle-side`. It belongs there because it is the third member of the family
that block already contains — the caption that names the editor, the box that
says where the answers are, and the triangle that points at the button.

```css
/* ---------- THE CUE ----------
 *
 * One violet triangle on the left edge of the one control the player should
 * press next. See docs/13-the-first-lesson.md; the rule in one sentence is
 * that the cue may point at a control because of what the control IS, and
 * never because of what the last attempt DID.
 *
 * THREE THINGS THAT LOOK ARBITRARY AND ARE NOT:
 *
 *  - It is a real element, not a ::after. metal.css:269 puts the button's
 *    specular skim on .btn::after, and a pseudo-element has one box: a cue
 *    written as ::after would strip the skim off whichever button it pointed
 *    at, so the button would change material while cued.
 *
 *  - The sizes are device pixels and do NOT multiply by --scale. The paddings
 *    it lives in do not either — .btn.small is `padding: 7px 9px` with no
 *    calc() — so a scaled cue would eat its own clearance at text_scale 1.5.
 *    Worst case, at the peak of the drift: 5px clear of the label on a
 *    .btn.small (border 2 + padding 9 = content at 11; the cue peaks at 6).
 *
 *  - The dark keyline is opaque and only the violet inside it breathes. Under
 *    metal.css the CAST button is a #4a2f8c→#150c28 gradient with a --violet
 *    border, and a violet triangle at 55% on that ground is invisible. The
 *    16-bit answer is a keyline, not a second colour.
 */
.has-cue { position: relative; }

.cue {
  position: absolute;
  width: 7px; height: 9px;
  background: #04030a;
  clip-path: polygon(0 0, 100% 50%, 0 100%);
  pointer-events: none;
  z-index: 2;                     /* above metal.css's .btn::after skim */
  left: -3px; top: 50%;
  transform: translate(0, -50%);
  animation: cue-drift 2.4s ease-in-out infinite;
}
.cue::after {
  content: '';
  position: absolute;
  left: 1px; top: 1px;
  width: 5px; height: 7px;
  background: var(--violet);
  clip-path: polygon(0 0, 100% 50%, 0 100%);
  opacity: .55;
  animation: cue-breathe 2.4s ease-in-out infinite;
}

/* UNDER: the only target with no horizontal room is a side tab —
 * #battle-side-tabs button is `padding: 9px 2px` with five across 360px. The
 * 9px bottom padding is clear of the 8px label. */
.cue.under {
  width: 9px; height: 7px;
  clip-path: polygon(50% 0, 100% 100%, 0 100%);
  left: 50%; top: auto; bottom: 1px;
  transform: translate(-50%, 0);
  /* 1px, not 2. The tab's bottom padding is 9px and the cue is 7px tall at
   * bottom:1px, so 2px of travel would put the peak 1px inside the content
   * box. 1px lands it exactly flush. */
  animation-name: cue-drift-up;
}
.cue.under::after {
  width: 7px; height: 5px;
  clip-path: polygon(50% 0, 100% 100%, 0 100%);
}

@keyframes cue-drift {
  0%, 100% { transform: translate(0, -50%) }
  50%      { transform: translate(2px, -50%) }
}
@keyframes cue-drift-up {
  0%, 100% { transform: translate(-50%, 0) }
  50%      { transform: translate(-50%, -1px) }
}
@keyframes cue-breathe {
  0%, 100% { opacity: .55 }
  50%      { opacity: .85 }
}

/* Motion is decoration; the cue is the signal. body.reduced-motion kills every
 * animation in the document with !important, so the rest state has to read on
 * its own — it is pinned brighter, because a still triangle at .55 is dimmer
 * than a breathing one that spends half its life at .85. */
body.reduced-motion .cue::after { opacity: .78; }
/* metal.css flattens decoration under .high-contrast and hides .btn::after
 * outright. The cue is not decoration. */
body.high-contrast .cue::after { opacity: 1; }
/* MENU → GUIDANCE → "Show the guide arrow". tutor.js also stops placing it;
 * this is the second of the two locks. */
body.no-cues .cue { display: none; }
/* A measurement furnishes the room without tutoring the candidate. */
body.interview-mode .cue { display: none; }

/* ONE MOTION VOCABULARY. #answer-here's arrow predates the cue and was tuned
 * for a screen with nothing to type on: 1.3s and 7px is too fast and too far
 * beside a 2.4s, 2px cue. Same period, same register. */
@keyframes ah-nudge { 0%, 100% { transform: translateX(0) } 50% { transform: translateX(3px) } }
```

The last block **replaces** the existing `@keyframes ah-nudge` at
`game.css:378`; it is not added beside it.

---

## 3. WHEN IT FADES

A tutorial that never stops is a nag. Three retirements, a per-encounter ceiling,
and one way back on.

### 3.1 The rule

> **Three times pointed at, or three times done, whichever comes first — and
> then that control is never cued again for the life of this save.**

Two counters per control, both in `state["lessons"]["cue"]`:

| Counter | Incremented | Retires at |
|---|---|---|
| `shown[id]` | every time the cue is drawn on that control | **3** |
| `used[id]` | every time the player presses that control, cue up or not | **3** |

A control is cueable while both are under 3. A player who finds RUN on their own
never sees an arrow on it: the third press retires it with `shown` still at
zero, which is the competence signal, and it costs no extra machinery to get.

### 3.2 The per-encounter ceiling

- **At most two cue appearances in one encounter.** After the second, the
  encounter is cue-free until it ends.
- **A control already used in this encounter is not cued again in this
  encounter.** This is what makes the code fight walk RUN → CAST rather than
  sitting on RUN: the player runs, the run is counted, and the next idle finds
  CAST. Note precisely what is read — *that* a run happened, never what came
  back from it.

Two appearances is the ceiling because a third arrow is not help. A player who
is still stuck after two needs the hint ladder, the Mender, or a walk, and none
of those is an arrow's business.

### 3.3 The dwell

The cue appears only after the player has **stopped**.

| Kind | Idle before the cue appears | Why |
|---|---|---|
| `code` | **8000 ms** | 4 s of stillness in a code fight is thinking, not searching. 8 s is looking for a button. |
| `puzzle` | **8000 ms** | Same. |
| `incant` | **8000 ms** | Same. |
| `mcq`, off the TRIALS tab | **2000 ms** | The screen is showing the player nothing they can act on, which reads as broken rather than as a pause. Two seconds is long enough to be a navigation, short enough not to be a dead end. |

Any keystroke, click or key press hides the cue immediately and restarts the
dwell. **The cue is never up while the player is typing.**

### 3.4 The way back on

`MENU` grows one section. `state["settings"]["cues"]` defaults to `true`;
`set_setting` already accepts any key (`engine.py:9591` · `set_setting`), so this is a default
and a checkbox.

```
GUIDANCE
  [x] Show the guide arrow
  [ TEACH ME AGAIN ]
  The arrow points at one control at a time and retires each one after three.
  Teaching again clears what the arrow has retired and what the schoolteacher
  has already told you.
```

**TEACH ME AGAIN** clears `state["lessons"]` entirely — both the cue counters
and the curriculum latch. One button, two effects, because they are one idea:
the player is saying *I would like to be shown this again*, and there is no
sensible reading in which that means the arrow and not the teacher.

Unchecking the box sets `body.no-cues` and stops `tutor.js` placing. Nothing is
forgotten; the counters stand where they were.

---

## 4. THE THREE ENCOUNTER KINDS

### 4.1 The eligibility check, which is what makes "never point at a hidden control" true rather than hoped

Stated as code, because a prose version of this gets re-derived wrongly:

```js
function eligible(node) {
  return !!node
    && node.isConnected
    && !node.disabled
    && node.offsetParent !== null        // display:none on it or any ancestor
    && node.getClientRects().length      // visibility / zero box
    && !node.closest('#editor-host');    // never over code
}
```

`offsetParent === null` is the load-bearing line: it is false for a node whose
own `display` is `none` **and** for a node inside a hidden ancestor, which is
exactly how this screen hides things — `$('#btn-submit').style.display = 'none'`
on an MCQ (`main.js:2769`), `$('#btn-run').style.display = 'none'` on a puzzle
(`main.js:2740`). One check covers every case the screen actually uses.

**The caveat, stated so nobody trips on it later:** `offsetParent` is also `null`
for a `position: fixed` element. No cue target is fixed today. If one ever is,
this check will silently refuse it, and the symptom will be "the cue never
appears" rather than a crash.

**The cue reads the KIND from the DOM, not from an argument:**

| Kind | How it is recognised | Source of truth |
|---|---|---|
| `code` | `#editor-caption` is visible | `setEditorMode('code')` |
| `mcq` | `#answer-here` is visible | `setEditorMode('mcq')` |
| `puzzle` | `#puzzle-host` is visible | `renderPuzzle` |
| `incant` | `#editor-pane .inc-cast` exists | `IncantationUI._build`, `incantui.js:315` |

This is deliberate and it is worth one sentence: a cue that took the kind as an
argument could disagree with the screen. A cue that reads the screen cannot.
It also means `tutor.cue()` takes no arguments at all, which is most of why the
work list in §7 is six lines of `main.js` rather than sixty.

### 4.2 A code fight

**Present:** `#btn-run`, `#btn-submit` (labelled `CAST ✦`, or `FORGE ✦` on a
`test_forge` — `main.js:1309`), `#btn-reset`, `#btn-flee`, the editor, the
caption, five side tabs, the belt.

| Priority | id | Target | Placement | Cued when |
|---|---|---|---|---|
| 10 | `run` | `#btn-run` | EDGE | not yet used in this encounter |
| 20 | `cast` | `#btn-submit` | EDGE | `run` has been used in this encounter, or is not eligible |

**Never cued in a code fight:** `#btn-reset` and `#btn-flee` (they are exits, and
a tutorial that points at RETREAT teaches quitting), the five side tabs (no
horizontal room, and the two that matter are `HINTS` and `PROBES` capabilities),
the belt (moved to Thessaly, beat 21), the editor (`#editor-caption` owns it).

### 4.3 A puzzle

`renderPuzzle` hides the editor and `#btn-run`, shows `#puzzle-host`, relabels
`#btn-submit` from `puzzleui.PUZZLE_VERB` (`ASSEMBLE ✦`, `DECLARE ✦`, `ACCUSE ✦`,
`STRIKE ✦`, `PRICE ✦`) and **sets `disabled = !G.puzzle.ready()`**. The
eligibility check refuses a disabled button, so the submit cue arrives exactly
when the puzzle becomes answerable, and never a moment before.

| Kind | First interactive element | Cued? | Verdict |
|---|---|---|---|
| `RUNE_ASSEMBLY` | `#puzzle-host .rune-tray .rune` | **yes**, priority 10 | The pile is `mcq.shuffle`. Pointing at its head says *these are draggable*. |
| `TRACE` | `#puzzle-host .trace-row input` | no | A text field. The cue never points at one — it has a caret, a placeholder and a `<label>` of its own. |
| `SPOT_THE_FLAW` | `#puzzle-host .code-pick .cl` | **no — refused** | The question is *which line*. |
| `STATE_PREDICT` | `#puzzle-host input.puzzle-input` | no | Text field. |
| `BREAK_IT` | `#puzzle-host input.puzzle-input`, plus six named quick cases | **no — refused** | The quick buttons are named edge cases. |
| `COMPLEXITY_MATCH` | the first option `.btn.small` | **no — refused** | The question is *which option*. |

So on five of six puzzle kinds the only cueable control is `#btn-submit`, at
priority 20. That is correct and it is not a gap: on those five the answer is
typed or chosen and the thing a new player genuinely cannot find is the button
that commits it.

> **THE TRIPWIRE, and it is the one condition in this document that a future
> pass can break by accident.** The RUNE_ASSEMBLY cue is legal only because
> `mcq.shuffle` is a shuffle, so position in the pile carries no information
> about the solution. **If `shuffle` is ever sorted, seeded to put distractors
> last, ordered by difficulty, or otherwise made meaningful, the `rune` cue must
> be deleted the same day.**
>
> `corpus/validate.py` checks the shuffle's **length** and nothing else —
> `len(spec.get("shuffle", [])) != len(spec["runes"])` — so `[0,1,2,…]` passes
> it, and `[0,1,2,…]` is the runes in authored order, which is the canonical
> solution in order. Two things now stand between that and a violet arrow on
> line one of the answer, and neither existed when this paragraph was first
> written:
>
> - `tests/test_corpus.py::TestCorpus::test_the_rune_pile_is_never_the_solution_in_order`
>   (§7.9 X6) asserts, for every RUNE_ASSEMBLY in the corpus, that the shuffle
>   is a permutation of every rune index and is neither the identity nor
>   sorted. Measured on the shipped corpus: 42 assemblies, shuffle present
>   42/42, identity 0/42, sorted 0/42 — and 4/42 happen to have the first
>   solution line at the head of the pile, which is what a shuffle does and is
>   why the cue points at the *pile* rather than at a rune it chose.
> - `puzzleui.js`'s fallback for a missing shuffle was `runes.map((_, i) => i)`
>   — the identity, i.e. the answer in order. It is `[]` now: an empty pile,
>   which is a visible bug somebody fixes in an hour rather than a silent leak
>   nobody sees. Both were rendered in a browser to confirm which is which.
>
> If `validate.py` ever grows an ordering clause, this cue is still a leak and
> still has to go.

### 4.4 An MCQ

`renderMcq` hides the editor, hides `#btn-run`, **hides `#btn-submit`**, shows
`#answer-here`, and puts the choices in the TRIALS tab as `.list-item` nodes
(`main.js:2776`). `enterBattle` forces `setTab('trials')` for an MCQ
(`main.js:1330`), so the choices are on screen when the fight opens.

| Priority | id | Target | Placement | Cued when |
|---|---|---|---|---|
| 5 | `trials_tab` | `#battle-side-tabs button[data-tab="trials"]` | **UNDER** | the kind is `mcq` **and** `#battle-side-body` holds no `.list-item` |
| — | — | any `.list-item` | — | **never** |

**The choices are never cued, and the reason is measured rather than
principled.** Seven of the nine authored MCQ answer keys in
`gauntlet/corpus/families/` are `answer=0`, and the client posts the index it
rendered, so the order is the order the corpus wrote. An arrow on the first
choice would be an arrow on the correct answer 78% of the time in the corpus
that ships today. Even if a later pass shuffles per serve, this stays refused
under the container rule in §1.3: **the cue points at containers, never at
members of a set the player is being asked to choose from.**

What the MCQ gets instead is the arrow it already has. `#answer-here` says, in
words, `PICK YOUR ANSWER OVER THERE ▶`, in `var(--violet)`, with an animated
glyph — and §2.4 retunes that glyph to the cue's own 2.4 s / 3 px so the two
speak the same language. The only new thing on an MCQ is the tab cue, for the
one state where the screen is genuinely showing the player nothing they can act
on: they navigated off TRIALS, and the answers went with it.

### 4.5 An incantation

`IncantationUI` owns `#editor-pane` and carries its own `.inc-cast` button
(`incantui.js:315`), its own `.inc-move` moveset and its own `.inc-hole` slots.

| Priority | id | Target | Placement | Cued when |
|---|---|---|---|---|
| 20 | `inc_cast` | `#editor-pane .inc-cast` | EDGE | eligible and not yet used in this encounter |

**Never cued:** `.inc-move` (choosing a move is the encounter), `.inc-enemy`
(choosing a target is the encounter), `.inc-hole` (they are inputs). Same
container rule, third application.

---

## 5. THE CURRICULUM

### 5.1 Who is teaching, and under which rules

**Thessaly Brun**, village schoolteacher, nineteen years in the square. She is
`captives.CAPTIVES` row `thessaly_brun` and `zonecompanions.ESCORTS` row one,
`zone="home"`, `sprite="scholar"`, `boon="the_square_drill"`, taken by
`the_interviewer` at the sweep. Her `walking`, `capture`, `narrator`,
`loss_line`, `thanks`, `handover` and `retaken_line` are already authored and
**this document does not change one word of them.**

Her existing `verb` is the promise the curriculum extends:

> Standing on a building's door tile prints, once per building, what that
> building is and what its sign means. Standing at a route head prints where
> that road goes and what it costs. **She never says anything about a problem;
> she says things about places.**

The curriculum is the same sentence with one word added: *places and screens*.

**Three rules govern her, and only three.**

1. **She is silent in a measured run.** `zonecompanions.available_in` defers to
   `captives.available_in`, which is `mode != MODE_INTERVIEW`. The gate exists
   and is already correct.
2. **She never speaks inside a battle.** `finalexam.CRUTCHES` rung 5 is `PET` —
   *"A companion volunteering the one line you had forgotten."* A person talking
   in a fight is that shape, and the cheapest way never to be mistaken for it is
   never to be there. Every battle lesson is therefore taught **before** the
   first battle or **after** it, which is what a teacher does anyway.
3. **A lesson taught is taught.** One latch per beat in
   `state["lessons"]["beats"]`, forward-filled on load. The precedent is
   `explainBlank()` (`main.js:1389` · `explainBlank`) and the shape is `zonecompanions`' own
   `_latch`.

**And `docs/10-sealed-views.md` has nothing to say about her**, which is worth
stating plainly so nobody argues it later. Doc 10 governs *what a measured run
may read*. Thessaly does not exist in a measured run. She is a `MENTOR`-shaped
thing and that is exactly why rule 1 is the first rule rather than a caveat.

**The voice.** Plain, unhurried, dry. She has taught in one square for nineteen
years and is not impressed by monsters. She does not exclaim, does not say
"great job", does not say "let's", and never uses two sentences where one will
do. She is a schoolteacher, not a tutorial mascot.

### 5.2 The shape of a beat

```python
@dataclass(frozen=True)
class Beat:
    id: str          # the latch key
    order: int       # the order they are authored in; ties break by order
    teaches: str     # one phrase, for the panel and for self_check
    trigger: str     # prose, for the wiring pass — §7 names the call site
    channel: str     # "say" (dialogue box, portrait) or "toast"
    lines: tuple     # 1-3 for say; exactly 1 for toast
    board: str       # the one chalk line the Slate carries if she never got here
```

`board` is one line, not a speech, because a board holds a line. §6.

### 5.3 The beats

Thirty numbered entries: **twenty-four beats she speaks**, and six handoffs to
prose that already exists somewhere else on the screen. One idea each.

**Why the numbering moved.** It ran to twenty-one in the first draft of this
document and the data was written against it. Five lessons were then found
missing against the screens — the editor half of beat 3, the fifth town
counter, the shrine, the disciplines, the fourteen keys — a sixth mechanic
(the Armorer's forge) was folded into the beat that already owned its subject,
and four surfaces that carry most of a new player's first hour turned out to
explain themselves already and needed recording rather than re-teaching. Numbers are a
cross-reference and nothing else, so they were re-run 1..30 in narrative order
rather than appended out of sequence: `Beat.order` is this section's number and
`tutorial.ORDER` sorts by it, so an appended number would have put the editor
lesson after her goodbye.

#### PART ONE — THE FIELD

**1 · `the_square`** — *teaches: moving and interacting*
Trigger: the first frame of overworld control on a new save, in `python_village`.
Channel: say.
> You will want to know where things are before you want to know anything else.
> I am Thessaly Brun and I have taught in this square for nineteen years.
>
> Walk with the arrows or with W, A, S and D. Stand on a thing and press space,
> and the thing will answer you.
>
> That is the whole of it. Everything else in this village is a door.

`board:` *Arrows or WASD to walk. Space to speak to whatever you are standing on.*

---

**2 · `the_doors` and `the_roads`** — **HANDED OFF.**
These are `zonecompanions.ESCORTS[0].verb` — `ESCORTS` is a tuple and
`thessaly_brun` is row one; `zonecompanions.BY_ID` is the mapping — and they
are already designed, already written and already owed to `overworld.js` by
`docs/12-the-zone-companions.md` §8.2. The curriculum does not re-implement
them and must not print a second caption over the top of one.

**Field captions are connected.** `region.escort` and movement/travel snapshots
feed `Overworld.setEscort`; the current doorstep or exit calls
`main.showEscortCaption`. The sidebar uses the server's mentor identity,
region description and correctly oriented route destinations and requirements.
Each location speaks once per visit, only while the server says she is walking
and no measured run is open. Today's houses all open the mentor interaction:
distinct mender/smith signs and enterable interiors from `docs/12` remain
separate work. The caption does not pretend those service doors already exist.

---

**3 · `the_fight`** — *teaches: what an encounter is*
Trigger: the mouth of the **first** encounter — in `onNodeEnter`, before the
encounter is started, queued so the fight opens when she stops.
Channel: say.
> That is a question wearing a monster. It will ask you for Python and it will
> not take anything else.
>
> Some of them want a spell written out. Some want one line taken from a list,
> or a pile of them put in order. The screen says which as it opens, and it says
> it where the writing would have gone.
>
> Nothing in this village dies of a wrong answer. Go on.

`board:` *A monster is a question. The screen says which kind as it opens. A wrong answer is not fatal here.*

**Kind-neutral, and that is the whole design of this beat.** `onNodeEnter` has a
marker and not a problem, so every sentence here has to be true of all four
encounter kinds. The half that needs to know the kind is beat 4, which fires
where the kind is known. Between them they pay back the plural in "what their
options are" — and neither of them names a control that is not on the screen.

---

**4 · `the_code_fight`** — *teaches: RUN costs nothing and only CAST is scored*
Trigger: the first encounter that opens **with an editor in it** — in
`enterBattle`, on the `else` branch that has just chosen the editor over a
puzzle or a question, on the frame the screen is built. On a clean save that is
the **third** encounter, not the first.
Channel: say.
> The caption over that box tells you where to type and which button casts. It
> does not tell you what either one costs you, and that is the part worth
> knowing.
>
> RUN is free. Press it as often as you like. Nothing is spent, nothing is
> recorded, and nobody is counting.
>
> CAST answers the question. That one is scored, and it is the only one that is.

`board:` *RUN is free and unrecorded. CAST is the one that is scored.*

**This is the half of old beat 3 that needed a kind.** `onNodeEnter` has a
marker and not a problem — `startNext()` only learns the encounter kind inside
`enterBattle` — so the old single beat named the editor, RUN and CAST at the
mouth of an encounter that, measured on a fresh save, is `fs-see-a-value`:
CODE_READING, `entry.kind` **mcq**, chosen by the ramp. `renderMcq` sets
`#editor-host`, `#btn-run` and `#btn-submit` to `display:none` and prints
NOTHING TO TYPE ON THIS ONE in their place. All three objects she named were
hidden while she named them, in the one lesson a new player is guaranteed to
get. Encounter two is also `mcq`; the first editor fight is encounter three.

**And it says only what `#editor-caption` does not.** The caption is permanent
and already carries WRITE YOUR PYTHON HERE ▾, THEN PRESS CAST ✦ ABOVE and both
keystrokes. §1.3 row 12 refuses to point an arrow at that box for exactly that
reason. What the caption does not carry is the price of either button.

---

**5 · `the_question`** — **HANDED OFF.** `web/index.html` `#answer-here`, put up
by `setEditorMode('mcq')`. The MCQ pane already says NOTHING TO TYPE ON THIS
ONE, then where the answers are and that clicking one casts it. Ten of the
first fourteen selections on a fresh save are `entry.kind=mcq`, measured, so
this is most of a new player's first hour and a beat would be the loudest
possible duplicate.

---

**6 · `the_pile`** — **HANDED OFF.** `web/js/puzzleui.js` `.puzzle-help`, six
of them, one per puzzle kind. Each tray opens with its own sentence — drag or
click the runes, depth is meaning in Python, some do not belong at all. A beat
would be a seventh explanation of six things that explain themselves at the
moment they are used.

---

**7 · `the_blanks`** — **HANDED OFF.** `web/js/main.js` `explainBlank()`.
MISSING_RUNE's blanks are explained in words, in place — which is also why
§1.3 row 11 refuses to point an arrow at one. Four of the first fourteen
selections on a fresh save are MISSING_RUNE, measured.

---

**8 · `the_trials`** — *teaches: the trials list, and what a locked trial will not tell you*
Trigger: the next visible battle trials tab after the first encounter, whatever
the result. Not on the world screen or the MCQ answer pane.
Channel: say.
> The list on the right is the trials. The open ones show you what goes in and
> what should come out.
>
> The locked ones do not. They will name the shape of what broke and never the
> value, which is the same courtesy an examiner extends.

`board:` *The trials are on the right. A locked trial names the shape of a failure, never the value.*

---

**9 · `the_tabs`** — *teaches: the five side panels, and why three of them get taken away*
Trigger: a visible battle after two encounters. Not on the world screen.
Channel: say.
> Five panels on the right and you are owed all five today. TRIALS, TACTICS,
> SPELLS, APPROACH, VISION.
>
> TACTICS reads the creature. SPELLS is the ladder of hints. APPROACH is a box
> you write in BEFORE you write any Python — your plan, the structure, what it
> costs — and what you put in it is scored. VISION draws the working.
>
> The fourteen will take three of them off you, one at a time, in a fixed order.
> That is not a cruelty. It is the measurement arriving slowly enough for you to
> survive it.

`board:` *SPELLS goes first, then TACTICS, then VISION. TRIALS and APPROACH are yours to the end.*

**Three go and two stay**, read off `main.js`'s `TAB_SEAL`, which is
`{ spells: HINTS, tactics: PROBES, vision: VISUALS }`. TRIALS and APPROACH have
no entry, `applySeal()` hides a tab only where `TAB_SEAL` has one, and `main.js`
says *"TRIALS is never sealed"* in its own comment. The order is
`finalexam._rung_of`: HINTS at rung 3, PROBES at 6, VISUALS at 8. Three of the
fourteen rungs touch a tab and the other eleven do not.

**And APPROACH is not a restatement of the question.** `paintApproach` draws a
textarea with `SCORE MY EXPLANATION` under it and *"Interviewers score this as
heavily as the code"* over it, and it is the **default tab in a measured run**.
The plain statement of the problem is `#problem-statement` in `#battle-brief`,
which is not a tab at all. A player told otherwise never types in the one panel
that teaches interview communication.

---

**10 · `saving`** — *teaches: it saves itself*
Trigger: queued behind beat 8.
Channel: toast. `SHE WRITES IT DOWN`
> It writes itself down after everything you do, on this machine, without being
> asked. You will not lose an afternoon in here.

`board:` *It saves itself after everything, on this machine.*

---

**11 · `stamina`** — *teaches: what the health bar is for*
Trigger: the first return to the overworld below full stamina.
Channel: toast. `WHAT THE BAR IS`
> Stamina is not your life. It is how many more questions you get to be wrong
> about today.

`board:` *Stamina is how many more questions you get to be wrong about today.*

---

**12 · `the_fall`** — *teaches: losing an encounter*
Trigger: the first encounter that ends unsolved.
Channel: say.
> Now you know what that costs. Stamina, and the walk back.
>
> It does not cost you the question. That family will come round again wearing a
> different face, and you will have had a fortnight's more practice when it does.

`board:` *A wrong answer costs stamina and a walk. It never costs the question.*

---

**13 · `the_dying`** — *teaches: what dying takes and what it cannot take*
Trigger: the first death, after the death screen is dismissed.
Channel: say.
> You lost gold, and ground, and whatever you were carrying. That is what dying
> is for. If it took nothing from you it would mean nothing.
>
> It did not touch what you can do. Your attempts, your skills, the schedule,
> the records — none of that was on you when you fell. It is in the book, and I
> keep the book.

`board:` *Dying costs gold, ground and carry. It never costs a skill, an attempt or a record.*

Checked against `gauntlet/death.py`: *"DEATH REWINDS THE GAME. IT NEVER REWINDS
THE PLAYER"*, and `restore_history=False` is the line expressed as a keyword
argument. She is describing what the code does.

---

#### PART TWO — THE TOWN, AND WHAT YOU KEEP

**14 · `the_square_panel`** — *teaches: the town panel, and how many counters are in it*
Trigger: the first time the town panel is opened.
Channel: say.
> THE TOWN SQUARE is a button, in the ACTIONS list on the world screen. Every
> region has a square and the button is always in the same place.
>
> Six counters in this one and five in every other. I will introduce you to each
> as you reach it.
>
> Nothing in there is trying to kill you. It is the only screen in the realms I
> can say that about.

`board:` *THE TOWN SQUARE is a button in the ACTIONS list. Six counters here, five in every other square.*

**No key opens this.** The only global `keydown` handler binds `n`, `f`,
`Escape` and `Space`; `overworld.js` binds the arrows, WASD, `Escape` and
`Space`/`Enter`. The single way in is `btnTown.onclick = () => go('town')` in
the world screen's ACTIONS list — `go('town')` appears **once** in the whole of
`web/js`, and `doTodo` has no `town` action kind, so there is not a second door
either. "One key, from anywhere in a town" named a key that does not exist, in
the first sentence she says about the town.

**And the count is six here.** `tabsHere()` returns `townui.TABS` — mender,
smith, shelf, broker, voices — plus `PORTAL_TAB` wherever the server sends a
portal, which is `python_village` and nowhere else. A new save starts in
`python_village`, so the square this beat first fires in always has six. The
promise to introduce each is now kept: five counter beats, and the portal is
beat 27.

---

**15 · `town_mender`** — *teaches: THE MENDER, free, and why*
Trigger: the first `paintBody()` with `TAB === 'mender'`.
Channel: say.
> Margit Orr. She charges nothing and she will tell you why before you ask her.
>
> Health decides how many attempts you get. Charging a learner for attempts is
> charging them for learning, and Margit will not do it.

`board:` *Margit Orr mends for free. Health is attempts, and attempts are not for sale.*

---

**16 · `town_smith`** — *teaches: FERRO, armour integrity, and the two ways it comes back*
Trigger: first `paintBody()` with `TAB === 'smith'`.
Channel: say.
> Ferro. Armour has integrity, integrity wears down every time you are wrong,
> and he sells it back by the point.
>
> If you cannot pay for all of it he mends the cheapest piece first. That is not
> generosity. It is the most points for your gold, and he assumes you can do the
> sum.
>
> There is a second price and it is not gold. ARMORER'S FORGE on the world
> screen hands you a broken program instead; mend that and the piece it was
> tagged for mends with it.

`board:` *Ferro sells armour integrity by the point. ARMORER'S FORGE mends a piece for a fixed program instead of for gold.*

**The third line is a whole mechanic that had no lesson.** `ARMORER'S FORGE` is
`startNext({ kind: 'DEBUG_BATTLE' })`, and `engine.py` repairs the piece the
problem is tagged for — 20 to 60 points by difficulty — the moment the debug
battle is solved. Failing any encounter cracks a piece chosen by root cause. It
sits on the world screen's ACTIONS list on the first frame of play, it is not
Ferro and not his building, and it belongs in this beat because the idea is one
idea: *how armour integrity comes back*. There are two prices for it and only
one of them was taught.

---

**17 · `town_shelf`** — *teaches: the vendor, the region band and the restock clock*
Trigger: first `paintBody()` with `TAB === 'shelf'`.
Channel: say.
> The vendor. Potions are brewed to what this place can reach, not to what you
> have grown into — so a shallow region sells shallow however grand you have
> become.
>
> The shelf refills every sixth encounter you actually clear. Losing buys
> nothing.

`board:` *The shelf is banded by the region, not by your level. It refills every sixth cleared encounter.*

---

**18 · `town_broker`** — *teaches: ORIN TALLOW, one trial at a time, quoted before the work*
Trigger: first `paintBody()` with `TAB === 'broker'`.
Channel: say.
> Orin Tallow, the assayer. One trial open at a time, and he quotes it before
> the work rather than after it.
>
> Read the quote. He is honest and he is not generous, and those are different
> things.

`board:` *Orin Tallow: one trial at a time, quoted before the work.*

---

**19 · `town_voices`** — *teaches: THE VOICES, and what the people here have noticed*
Trigger: first `paintBody()` with `TAB === 'voices'`.
Channel: say.
> The voices. Whoever is standing in this square, and what they have noticed
> about the place, about your armour, and about what is one road away.
>
> They are not a menu and they are not a service. They are people who live here,
> and they say something else when your kit changes.

`board:` *The voices are whoever is standing in the square, reading the place and your kit.*

**The fifth counter, which had no lesson** while beat 14 promised one for every
counter in the square. `banter.SPEAKERS` is forty-seven people and the tab is
ONE call for all of them, which is why what they say agrees with itself.

---

**20 · `the_forge`** — *teaches: the nine rungs and the region metals*
Trigger: the first time the forge panel is drawn on the GEAR screen.
Channel: say.
> Nine rungs. A blade climbs them on metal the creatures leave behind — eleven
> metals over sixteen regions, five of them shared by two, and not one of them
> from this village.
>
> You do not buy that ladder. You walk it, and the blade you finish with is the
> one you signed.

`board:` *Nine rungs. Region metals climb the blade. You walk that ladder; you do not buy it.*

Nine rungs is `forge.MAX_TIER`. The metal clause was wrong twice and wrong about
the ground under her feet: `forge.METALS` is eleven, `forge.REGION_METAL` is
sixteen entries drawn from those eleven — so keybrass, marshsilver, faultsteel,
heartwood_iron and doubling_steel each serve two regions — and
`forge.NO_METAL_REGIONS` is `('python_village',)`, the square she is standing in
while she says it.

---

**21 · `the_belt`** — *teaches: potions and the belt*
Trigger: the first time a potion enters the pouch, on the overworld.
Channel: toast. `SOMETHING FOR THE BELT`
> A potion goes on your belt, and the belt is the one thing in a fight that does
> not end your turn.

`board:` *The belt is the one thing in a fight that does not end your turn.*

---

**22 · `gear`** — *teaches: slots, rarity, elements and resists*
Trigger: the first item equipped.
Channel: say.
> Slots, a rarity, and an element each. A resist is worth more than a number on
> the day the ground is on fire.
>
> Read an item's lines, not its colour. The colour only tells you how rare it
> was to find.

`board:` *Read an item's lines, not its colour. Resists matter on the ground they are for.*

---

**23 · `the_companion`** — *teaches: the companion that walks with you*
Trigger: the first pet found (`partyui.showPetFound`'s `onClose`).
Channel: say.
> Something has decided to come with you. It will speak in a fight, until the
> ladder takes that away from you as well.
>
> Pay it some attention. It is the only thing in the realms that gets better
> without being graded.

`board:` *A companion speaks in a fight until the ladder takes it. Rung seven.*

Rung **seven**. PET is the fifth ROW of `finalexam.CRUTCHES` and the seventh
RUNG of the ladder: `_rung_of` maps a crutch to the boss that takes it, and
PET's is `path_sum_ent`, `world.BOSSES` index 7. This line said rung five, which
is the tuple index wearing the ladder's name.

---

**24 · `the_shrine`** — *teaches: the roadside shrine and what a riddle pays*
Trigger: the first press of `MEMORY SHRINE` on the world screen, before the
stone is drawn.
Channel: say.
> A shrine is a stone with a question on it. Twenty seconds, one line, and WALK
> ON is always there if you would rather not.
>
> Right pays you stamina, focus and experience, and it moves two of the records
> I keep. Wrong costs you nothing but the twenty seconds.

`board:` *A shrine is a stone, twenty seconds and one line. Right pays; wrong costs nothing.*

**And it is not the spaced-repetition schedule**, which is what its button name
suggests and what a reviewer of this document assumed. `Game.shrine` draws a
riddle from `world.SHRINE_QUESTIONS`; `shrine_answer` pays three stamina, six
focus and twelve experience for a right one and moves `RECALL` plus the
question's own skill. The schedule and the records beat 13 promises death
cannot take are `srs.py`, and they move on graded evidence — which a roadside
riddle is not, and which is exactly why a measured run may read the stone and
may not be paid for reading it. The modal itself says none of this: it prints
the question and a clock.

---

**25 · `the_disciplines`** — *teaches: the six disciplines and the tree under one*
Trigger: the first time the party screen is painted with no class chosen.
Channel: say.
> Six disciplines, and you may take one now. Nothing is holding them back and
> nothing will prompt you — the way in is a button on the party screen that says
> THE SIX DISCIPLINES.
>
> Under each is a tree of three branches, bought with the points a level hands
> you. The first change of mind is free, so taking one early costs you nothing
> you cannot undo.

`board:` *Six disciplines, offered from level one, behind the THE SIX DISCIPLINES button. The first change of mind is free.*

**Offered from level one and prompted by nothing.** `classes.CLASSES` is six,
each with three branches; `Game.choose_class` refuses a class already taken and
never a level; and the way in is a `THE SIX DISCIPLINES` button inside
`partyui.js` that one ledger line mentions in passing. A system with no gate and
no prompt is a system most players never open, which makes it the cheapest
lesson in the set to have been missing.

---

#### PART THREE — THE ROAD

**26 · `the_slate`** — **HANDED OFF.** `zonecompanions.hand_over_early(state)`
already gives the Slate on `rt_waking_road` and already carries her prose. The
curriculum adds nothing and must not print a second speech over it. **Connected:**
`consumeEscortResponse` retains the original `escort_events` from movement and
both travel paths, then `drainEscortNotices` presents the server's lines and
Slate description on the free world screen. It waits behind existing dialogue
and modals, never grants an item or acknowledges a lesson, and refuses measured
contexts. These pending presentation notices last for the browser session; the
server's grant remains durable if the page closes before the speech appears.

---

**27 · `the_keys`** — *teaches: the fourteen bosses, their keys, and the door they open*
Trigger: whichever comes first — the first boss marker entered on the overworld,
or the first press of `CHALLENGE BOSS`.
Channel: say.
> Fourteen of them are out there. Twelve take something off you when they go
> down, all fourteen leave a key, and every key opens a road you could not walk
> before.
>
> All fourteen keys together open the door standing in this village. That door is
> what you are walking towards, and it is the end of the story rather than the
> measure of you.

`board:` *Fourteen bosses, fourteen keys, fourteen roads. All fourteen keys open the door in this village.*

**The win condition, which had no lesson at all.** A player could walk the whole
curriculum without once being told what they were trying to do. `world.BOSSES`
is fourteen, `world.KEYS` is fourteen, `finalexam.BOSS_LADDER` is those same
fourteen in order, and `progression.PORTAL_NEED` is all of them — so the
fourteen who take your panels in beat 9 and the fourteen who leave the keys here
are ONE set of fourteen, not two. Twelve of the rungs take a capability; rungs
one and two take none, which is why this beat says twelve and beat 9 says three.
Every key opens a road. The portal stands in `python_village` and its own
payload reports `practical_requires_keys: False`, which is the sentence beat 29
exists for — said here first, so the two never disagree.

---

**28 · `the_incantation`** — **HANDED OFF.** `web/js/main.js`
`showIncantList()`'s modal. A second complete mode of combat, reachable from
`SPEAK AN INCANTATION` in the world screen's ACTIONS list on the first frame of
play — and the modal that opens it carries its own explanation at the top:
every enemy is a bound name, you attack by writing one line of Python that
really does something to it, and a wrong line costs the turn and says which of
the three layers it broke at. That is the lesson, already written, on the screen
you have to open to play one. This row is the decision, recorded, so that a
reader counting combat modes against beats finds an answer instead of a hole.

---

**29 · `the_practical`** — *teaches: the INTERVIEW door is always open*
Trigger: whichever comes first — the first road walked (queued behind the Slate
handover), or the first press of the `INTERVIEW` nav button.
Channel: say.
> There is a door on the menu marked INTERVIEW. It is open now. It was open
> before you arrived and it will be open when all this is finished.
>
> Nothing you do out here opens it and nothing closes it. Not the keys, and not
> the door the keys open. It is a measurement, not a prize, and the only honest
> thing to do with a measurement is take it whenever you want to know.

`board:` *The INTERVIEW door on the menu is always open. Nothing here opens or closes it, keys included.*

This beat exists because it is the single most misreadable thing in the game —
`finalexam.py` devotes its longest docstring passage to it and
`townui.js`'s portal tab prints it on the panel. A player who concludes the exam
is behind fourteen bosses has been sold the opposite of what was advertised, and
the cheapest place to prevent that is a schoolteacher on the first road.

---

**30 · `the_last_lesson`** — *teaches: what is left on the board when she goes* — §6.

### 5.4 Ordering, and the promise not to repeat

- **Order is authored, not emergent.** `order` breaks ties when two triggers fire
  on the same frame. The only pair that realistically collides is 8 and 10, and
  10 is deliberately a toast queued behind 8's dialogue.
- **Authored order is not chronological order.** Beat 4 fires on the third
  encounter of a clean save and beats 8 to 11 fire before it; beat 24 is
  reachable on the first frame of play. `order` is the order the curriculum was
  designed in and the order the board lists what is left — not a schedule.
- **One beat at a time.** `say()` owns one dialogue queue (`main.js:193`) and a
  second `say()` on top of an open one replaces it. The player function takes a
  beat only when `#dialogue` is not showing; otherwise it queues behind
  `G.afterStory`, which is the path `mentorTalk()` already uses.
- **A beat fires once, ever.** The latch is in the save, not in `localStorage`,
  so it survives an import, a new browser and a different machine — and so that
  the panel can show what is left. `TEACH ME AGAIN` (§3.4) is the only thing that
  clears it.
- **Nothing she says is ever repeated by anything else.** Beats 2 and 26 are
  handoffs precisely because `zonecompanions.py` already owns that prose, and
  beats 5, 6, 7 and 28 are handoffs because the screen that needs explaining
  explains itself at the moment it is used. Six handoffs and twenty-four beats
  is thirty numbered entries, which is what §5.3 lists.
- **Check the actual consumer.** Beats 2 and 26 are connected through
  `main.js`, `overworld.js` and the `WorldUI` travel-response hook. The focused
  `scripts/verify/escort-handoffs.mjs` check executes those response handlers,
  including stale movement, navigation, dialogue and measured-run guards.
  This does not certify the separate human-follower or interior designs.

---

## 6. WHEN SHE IS TAKEN

### 6.1 What is already decided

`zonecompanions.py` settles the mechanics and this document changes none of
them. Thessaly's `capture_kind` is `"sweep"`: she is taken by the Interviewer
when `bug_demon` is down **and** twelve of the fourteen rungs are cleared
(`sweep_fired`, `SWEEP_MIN_RUNGS`). `captives.retake` suspends her boon and
never touches items, so **the Slate keeps working**. Her `loss_line` is already
written and it is the right sentence:

> The captions stop. The Slate keeps working. You have already read the signs.

### 6.2 The unfinished curriculum, and what happens to it

By the sweep the player is twelve rungs deep and almost every beat has fired.
But not necessarily all of them: a player can reach rung 13 without ever
equipping an item, without ever finding a pet, without ever opening Orin
Tallow's counter. A design that drops those lessons on the floor teaches the
player that the game forgets, and a design that dumps them all at once as she
leaves is a wall of text at the most serious moment in the story.

> **THE DECISION: a lesson she never reached is not lost and is not dumped. It
> moves to THE BOARD.**

The board is already in her own capture lines, three times, in her own voice:

> *"Get the board in off the wall. The list for tomorrow is on it and if it
> rains on that list the whole square will claim they never saw it."*
>
> *"The square is the same square. The board is still on the wall, the list for
> tomorrow is still on the board, and there is nobody standing in front of it."*

So at the sweep, every unfired beat **keeps its trigger and its latch and
changes its speaker and its channel**:

| | Before the sweep | After the sweep |
|---|---|---|
| Speaker | `THESSALY BRUN` | `THE BOARD` |
| Portrait | `scholar` | none |
| Channel | `say` or `toast`, as authored | **always toast** |
| Text | `Beat.lines` — one to three | `Beat.board` — **exactly one chalk line** |
| Trigger | unchanged | unchanged |
| Latch | unchanged | unchanged |

This costs one field on the beat and one derived speaker. It needs no new art,
no new prop, no new state, and no new writing beyond the `board` line each beat
already carries. And it says the thing the player asked for — *"so the user will
know how to use them going forward into new areas"* — in the strongest available
form: **the curriculum survives its teacher.**

`captives.final_release(state)` clears `retaken`, she comes home, and any beat
still unfired goes back to her voice on the next trigger. One derived speaker,
two transitions, no extra bookkeeping.

### 6.3 Beat 30 · `the_last_lesson`

Fires once, at the sweep, immediately after the capture scene
(`zonecompanions.scene("thessaly_brun")`) has played out. Two variants, chosen by
counting how many beats are still unfired.

**If every beat has fired** — channel: say.
> There is nothing left on that board. You have been through every door on this
> square and asked every question in it, and the man at the gate does not know
> that yet.
>
> Go and finish it. I will not be here to mark it, which is how it should be —
> a thing you can only do while somebody is watching is not a thing you can do.

**If anything is unfired** — channel: say. The count is stated, never the list,
because a list is the wall of text this design exists to avoid. **`{n}` is the
one interpolation in the whole curriculum** — `len(firstlesson.pending(state))`
minus this beat — and it is spelled out here so that nobody hard-codes a number
into authored prose:
> There is still a list on that board. {n} things, I think, that we never got
> round to.
>
> It stays on the wall. Read it where you stand, when you reach the thing it is
> about. Chalk is not a worse teacher than I am; it is only a slower one.

`firstlesson.self_check()` asserts that `{n}` appears in exactly this one line
and nowhere else in `BEATS`, and that the singular reads *"1 thing"* rather than
*"1 things"* — the smallest possible amount of grammar, because a schoolteacher
who cannot count is the one character in this game who may not have that bug.

`board:` — none. This beat is the one that cannot move to the board, and if the
player somehow arrives at the sweep with `the_last_lesson` unfired it is simply
not shown. It is the only beat in the curriculum with no chalk line, on purpose.

---

## 7. THE WORK LIST

Nothing below is edited by this run. `main.js`, `townui.js`, `incantui.js`,
`worldui.js`, `fx.js`, `overworld.js` and `tiles.js` are owned by concurrent
passes. Each row names the file, the site, and the argument, so the wiring pass
works from this table rather than re-reading the design.

### 7.1 NEW — `gauntlet/firstlesson.py`

The curriculum data, the latch and the resolution. Pure, stdlib, no imports from
`engine`. Modelled on `zonecompanions.py`, which is the closest existing thing.

| # | Symbol | Contract |
|---|---|---|
| F1 | `LESSON_KEY = "lessons"` | the save key |
| F2 | `new_lesson_state() -> dict` | `{"beats": [], "cue": {"shown": {}, "used": {}}}` — lists and dicts only, so a hand-edited save heals on the next write, the way `zonecompanions._write_bucket` does |
| F3 | `Beat` dataclass, `BEATS` tuple | §5.2, §5.3. **Nineteen rows**, `the_last_lesson` among them. Entries 2 and 19 are handoffs and carry no row. |
| F4 | `BY_ID`, `ORDER` | derived, like `zonecompanions.BY_ID` |
| F5 | `available_in(mode) -> bool` | `return captives.available_in(mode)`. One line, one gate, no second opinion. |
| F6 | `speaker(state) -> str` | `"thessaly"` while `zonecompanions.state_of(state,"thessaly_brun")` is `WALKING` or after `final_release`; `"board"` once `zonecompanions.sweep_fired(state)` |
| F7 | `taught(state, beat_id) -> bool` | pure, total, `False` for an unknown id |
| F8 | `pending(state) -> list` | ids not yet taught, in `order` |
| F9 | `teach(state, beat_id) -> dict` | **the only writer.** `{}` if already taught or unknown. Otherwise latches and returns `{"id", "speaker", "who", "portrait", "channel", "lines"}` — `lines` is `Beat.lines` for `thessaly`, `[Beat.board]` for `board`, and `channel` is forced to `"toast"` for `board` |
| F10 | `cue_state(state) -> dict` / `cue_note(state, kind, id) -> dict` | the two counters, §3.1. `kind` is `"shown"` or `"used"`. Retirement is `shown >= 3 or used >= 3` and lives here, not in JS, so the client cannot drift from it. |
| F11 | `forget(state) -> dict` | TEACH ME AGAIN. Resets F2 wholesale. |
| F12 | `self_check() -> dict` | every `Beat.board` non-empty except `the_last_lesson`; `lines` 1–3 for `say`, exactly 1 for `toast`; no beat id collides with a `zonecompanions` scene id; **and `_no_beat_names_a_problem()`** — modelled on `captives._no_boon_supplies_an_answer`, refusing any beat text containing a problem id, a `corpus` family name or a `finalexam.CRUTCHES` id used as advice. Fails by name at import. |

### 7.2 NEW — `web/js/tutor.js`

The cue engine and the beat player. Owned by nobody; created by this design.

| # | Export | Contract |
|---|---|---|
| J1 | `REGISTRY` | the control table from §4: `{id, selector, placement, priority, kinds}`. The only list of things that may be cued. |
| J2 | `cue()` | Decide and place. **Takes no arguments** — reads the kind and the eligibility from the DOM (§4.1). Idempotent. **Eligible excludes `:disabled`.** A `.cue` is a child of its host, so a disabled host composites it at `opacity: .3` (`metal.css:292`) — measured on `#btn-submit` during a RUNE_ASSEMBLY, the cue renders `rgb(76,65,91)` where the same cue on the same enabled button renders `rgb(186,149,215)` — 1.75:1 against the ground instead of 6.13:1 — and its colour goes back to depending on the ground, which is the one thing the keyline exists to prevent. `cast`'s `kinds` includes `puzzle`, so the policy actively invites that placement and this check is what refuses it. `game.css` carries the same paragraph beside `.has-cue`. |
| J3 | `tick()` | Called from the existing 500 ms battle interval. Advances the dwell, re-asserts the node if a repaint stole it, hides on `body.no-cues`. **Starts no interval of its own.** |
| J3b | **the seal** | **Never gate on `body.interview-mode` or on `G.interview` alone** — `body.run-open` is the one that holds. Both are cleared by `returnToWorld()` — `classList.remove('interview-mode')` then `G.interview = null`, `main.js:3858`/`3860` at time of writing — while the measured run is still open server-side — RETREAT reaches it mid-run, and `docs/10` §4b.I establishes that the player can be on the overworld *between two questions*. That is exactly the gap where §7.4 M13 hangs five `tutor.beat()` calls, so a tutor gated on either signal is blind in it. **Gate on the server's answer instead:** `{}` from `/api/lesson` is authoritative and needs no local check at all, and `gauntlet/tutorial.py` refuses on `run_open` with a default of `True`, so the server cannot be talked into a lesson by a client that has forgotten. For the cue, which has no server round-trip per frame, carry a `run_open` boolean on `/api/state` (from `Game._run_is_open()`) and mirror it onto the body as **its own class**, set and cleared independently of the encounter — `interview-mode` also drives the palette drain, so reusing it is the larger change. |
| J4 | `used(id)` | Record a press. Posts `cue_note(…, "used", id)` and clears the cue if it is on that control. |
| J5 | `enterEncounter()` / `leaveEncounter()` | Reset the per-encounter counters and the two-appearance ceiling. |
| J6 | `beat(id)` | `POST /api/lesson {id}`; `{}` means already taught or sealed — do nothing. Otherwise dispatch to `say()` or `toast()` through injected hooks, so `tutor.js` imports nothing from `main.js`. |
| J7 | `configure({say, toast, api})` | the injection point, matching `partyui.configure` (`partyui.js:69`) |

### 7.3 `web/css/game.css` — MINE, not owned elsewhere

| # | Site | Work |
|---|---|---|
| C1 | after `@keyframes ah-nudge`, line 369 | **DONE.** §2.4 is pasted and has since been extended in place — RIM, `.cue.rim.top` and the `.btn.primary` rule are in `game.css` and not in §2.4. **`game.css` is the authority now; do not re-paste §2.4 over it.** |
| C2 | line 369 | **DONE.** `@keyframes ah-nudge` replaced with the 2.4 s / 3 px version. |
| C3 | `.cue.rim`, and the comment above it | **DONE.** The RIM host is `#battle-side`, never `#battle-side-body`: a RIM host must not be a scroll container, or the cue scrolls out of the panel with the list. Measured numbers are in the comment. `tutor.js` adds `.has-cue` to `#battle-side` when it places a RIM cue. |
| C4 | `.has-cue` | **DONE.** The comment above it carries the one constraint neither the CSS nor `tutorial.py` could express as code: a cue is never placed inside a `:disabled` host, because the host's `opacity` composites the cue with it. `tutor.js`'s eligibility check enforces it — §7.2 J2. |
| C5 | `.cue::after` | **DONE.** `.btn.primary .cue::after { background: var(--violet-hi) }` — §2.2 carries the measurement. |

### 7.4 `web/js/main.js` — OWNED ELSEWHERE

Eight lines of wiring plus the beats. **`main.js` grew by ten lines while this
document was being written** — a concurrent pass owns it — so every row below
carries the `grep` anchor as well as the number, and the anchor is the
authority. Numbers are as of `main.js` at 8,507 lines.

| # | Symbol / `grep` anchor | Line | Change |
|---|---|---|---|
| M1 | `G.overworld.onEnter = onNodeEnter` | 8309 | beside it: `tutor.configure({ say, toast, api })` |
| M2 | `function startTimer` → the `setInterval` body | 2791 | add `tutor.tick()`. **Reuse this interval; do not add one.** |
| M3 | `setTab(G.mcq ? 'trials'` — the last statement of `enterBattle` before `show('battle')` | 1330 | after it: `tutor.enterEncounter(); tutor.cue();` |
| M4 | `function setTab(tab)` — end of the function | 2867 | `tutor.cue();` |
| M5 | `$('#btn-submit').disabled = !G.puzzle.ready();` — **both** occurrences in `renderPuzzle` | 2745, 2749 | `tutor.cue();` after each, so the cue arrives the moment `ready()` flips |
| M6 | `function paintMcq(body)` — end of the function | 2776 | `tutor.cue();` |
| M7 | `$('#btn-run').onclick = doRun;` | 3849 | `→ () => { tutor.used('run'); doRun(); }` |
| M8 | `$('#btn-submit').onclick = doSubmit;` | 3850 | `→ () => { tutor.used('cast'); doSubmit(); }` |
| M9 | every `classList.remove('interview-mode')` and `function returnToWorld` | 3817 and the four `remove` sites | `tutor.leaveEncounter()` |
| M10 | `document.body.classList.toggle('reduced-motion', !!s.reduced_motion)` | 707 | beside it: `document.body.classList.toggle('no-cues', s.cues === false)` |
| M10b | wherever `/api/state` is applied (the same place `G.seal` is taken off the payload) | — | `document.body.classList.toggle('run-open', !!payload.run_open)` — **from the payload boolean only**, never from `G.encounter` or `G.interview`, and cleared by the same toggle. `run_open` is `Game._run_is_open()` (§7.8 E7). This is the class `tutorial.CUE_POLICY["sealed_body_class"]` names and the one `game.css` hides `.cue` under; see §1.5 for why `interview-mode` cannot do this job. |
| M11 | `function paintSettings()` | 6703 | Add the `GUIDANCE` block from §3.4: a `data-setting="cues"` checkbox — the existing `document.querySelectorAll('[data-setting]')` handler posts it with no further work — and a `#s-teach-again` button calling `api.lessonsForget()` then `refresh()` |
| M12 | `function onNodeEnter(marker)` | 1095 | before `startNext(...)`: `await tutor.beat('the_fight')` — beat 3. **Kind-neutral only.** The kind is unknowable here: `startNext()` learns it inside `enterBattle`. |
| M12b | `enterBattle`, the `else` branch of `if (puzzleui.isPuzzle(...)) … else if (p.entry.kind === 'mcq') … else` | 1313-1321 | inside the `else`, after `setEditorMode('code', verb)`: `tutor.beat('the_code_fight')` — beat 4. This branch is the only place in the client that knows the fight has an editor in it. |
| M13 | `function returnToWorld()` | 3817 | `offerLessons()` for `saving`, `stamina`, `the_fall` — beats 10, 11, 12. Beats 8/9 (`the_trials`, `the_tabs`) are now offered by battle entry and the visible trials tab so they never describe a battle panel from the world screen. Each is latched server-side, so the call site needs no counting of its own. **`returnToWorld` removes `body.interview-mode` and nulls `G.interview` while the run is still open server-side** (RETREAT reaches it mid-run), so `tutor.js` must not gate on either — see §7.2 J3. |
| M14 | `partyui.showTheFall(scene, { onClose: ... })` | 3643 | `tutor.beat('the_dying')` inside `onClose` — beat 13 |
| M15 | `partyui.showPetFound(row, { onClose: ... })` | 3649 | `tutor.beat('the_companion')` inside `onClose` — beat 23 |
| M16 | `function paintCharacter()` / `const forgeHost = $('#forge-panel-host')` | 5932 / 6039 | `tutor.beat('gear')` when an item is equipped; `tutor.beat('the_forge')` when the forge panel first paints — beats 22, 20 |
| M17 | `show('world'); G.overworld.start();` — the boot path only | 8373-8374 | on a **new** save: `tutor.beat('the_square')` — beat 1. Not the two deep-link copies at 8383-8384. |
| M18 | the `data-nav="interview"` handler | `b.dataset.nav = entry.id`, 7968 | `tutor.beat('the_practical')` — beat 29 |
| M19 | `async function doShrine()` | 4648 | first statement, before `api.shrine()`: `tutor.beat('the_shrine')` — beat 24 |
| M20 | `btnBoss.onclick = () => showBossList();` and the `marker.kind === 'boss'` branch of `onNodeEnter` | 820 / 1101 | `tutor.beat('the_keys')` at both — beat 27. Latched server-side, so both call sites are unconditional and the second one is free. |

### 7.5 `web/js/townui.js` — OWNED ELSEWHERE

**One line covers all five counter beats.**

| # | Symbol / `grep` anchor | Line | Change |
|---|---|---|---|
| T1 | `async function paintBody()` | 208 | first statement: `tutor.beat('town_' + TAB)` for `TAB` in `mender / smith / shelf / broker / voices`. All five beat ids are spelled to match the existing `TABS` ids exactly, so this is a concatenation and not a lookup table — and `TABS` has five entries, not four. |
| T2 | `export async function paintTown(tab)` | 81 | after `await paintBody()`: `tutor.beat('the_square_panel')` — beat 14 |

### 7.5b `web/js/partyui.js` — owned by nobody

One beat. `partyui.js` already has a `configure()` injection point
(`partyui.js:69`), so it gains no import.

| # | Symbol / `grep` anchor | Line | Change |
|---|---|---|---|
| P1 | `paintSkillTree()`, the `if (tree.error === 'no class chosen')` branch | 1093 | before `paintClassSelection()`: `tutor.beat('the_disciplines')` — beat 25. This is where a player who has never chosen actually lands. |
| P2 | `bind('[data-pt-classes]', () => paintClassSelection());` | 1185 | the same unconditional `tutor.beat('the_disciplines')`. Latched server-side, so the second call returns `{}` and this costs nothing. |

### 7.6 `web/js/incantui.js` — OWNED ELSEWHERE

| # | Symbol / `grep` anchor | Line | Change |
|---|---|---|---|
| I1 | `this._on(this.castBtn, 'click', () => this.cast());` | 345 | `→ () => { opts.onControlUsed && opts.onControlUsed('inc_cast'); this.cast(); }` — one optional hook defaulting to a no-op, so the file gains no import |
| I2 | `this.castBtn = node('button', 'btn primary inc-cast', 'CAST ✦');` | 315 | **nothing.** `.inc-cast` is found by `tutor.cue()`'s own selector. This row exists so that nobody adds a call here. |

### 7.7 `web/js/worldui.js`, `web/js/fx.js`, `web/js/overworld.js`, `web/js/tiles.js` — OWNED ELSEWHERE

| # | File | Change |
|---|---|---|
| W1 | `worldui.js` | **None.** The region card and the road list are already prose and the cue does not enter the world screen. This row exists so the wiring pass does not go looking. |
| W2 | `fx.js` | **None.** The cue is DOM and CSS. It is not a battle effect, it does not touch the canvas, and it must not acquire a particle. |
| W3 | `main.js`, `overworld.js`, `worldui.js` | **Connected.** Server walking flags enable current doorstep/exit captions; original move and both travel responses deliver the Slate via the existing dialogue shell. No duplicate grant or lesson acknowledgement. Measured runs and stale region responses cannot enable captions. Current houses expose mentor dialogue; distinct service signs, the human follower and enterable interiors remain separate `docs/12` work. |
| W4 | `tiles.js` | **None.** |

### 7.8 `gauntlet/engine.py` and `gauntlet/server.py` — OWNED ELSEWHERE

| # | Site | Change |
|---|---|---|
| E1 | `DEFAULT_STATE`, line 469 area | `"lessons": firstlesson.new_lesson_state()`, beside `"pets"` and the other module sub-states. `_merge` forward-fills, so an existing save gains the key on load with nothing taught. |
| E2 | `Game`, new | `def lesson(self, beat_id)` → `return tutorial.teach(self.state, beat_id, run_open=self._run_is_open())`, then `self.save()` if the return is non-empty. **Pass `run_open` and do not write the bare call.** The arguments are keyword-only and `run_open` **defaults to `True`**, so the bare call returns `{}` and writes nothing: a forgotten argument is a missing lesson, never a lesson taught into a measurement. `mode` is **not** passed — there is no `Game.mode` (`hasattr(Game(), 'mode')` is `False`, and `engine.py` says so itself beside `_advance_escorts`) and it does not need to be: the gate refuses on `run_open` alone, and `_run_is_open()` is `True` for `state["interview"]`, `state["exam"]` and an encounter opened in Interview Mode. **Do not also flip `mode`'s default to a measured run** — the gate is a disjunction, `run_open` already holds it closed, and a closed `mode` default would make this exact call return `{}` for every beat forever. |
| E3 | `Game`, new | `def lesson_note(self, kind, control_id)` → `tutorial.cue_note(self.state, kind, control_id, run_open=self._run_is_open())`; `def lessons_forget(self)` → `tutorial.forget(self.state, run_open=self._run_is_open())`. Both + `self.save()`. **All three writers are gated identically.** `cue_note` writes `state['lessons']['cue']` and `forget` clears the whole block, so both are `docs/10` write-clause writes even though neither leaks help; two of three gated and one ungated is how the ungated one survives a review. `def lessons(self)` → `tutorial.snapshot(self.state)`, no mode argument. |
| E4 | `server.py`, the POST block around line 510 | `POST /api/lesson {id}`, `POST /api/lesson/note {kind,id}`, `POST /api/lesson/forget {}` |
| E5 | `settings` default, line 469 | add `"cues": True` |
| E6 | `api.js` | `lesson: (id) => softPost('/api/lesson', { id })`, `lessonNote`, `lessonsForget` — `softPost` so a dropped teaching request never breaks a fight |
| E7 | `server.py` / `Game`, the `/api/state` payload | one more field: `view[tutorial.RUN_OPEN_FIELD] = self._run_is_open()` — i.e. `"run_open": bool`. It is the **only** thing this design asks of the state payload, and it exists because the two client signals for a measured run (`body.interview-mode`, `G.interview`) are both cleared by `returnToWorld()` while the run is still open. It leaks nothing: it is one boolean the player could work out by looking at the menu. |

**Why `POST` and not `GET`.** `docs/10-sealed-views.md`'s write clause: a GET
that changes the save is not a view. `/api/lesson` latches a beat, so it is a
POST. And `E2` refuses while a run is open — not because a beat leaks anything,
but because `firstlesson.available_in` is the same gate `captives` and
`zonecompanions` already stand behind, and three modules answering the same
question three ways is what `docs/10` §0 was written about. It returns `{}`, not
a 409: there is nothing to teach, which is an answer, not a refusal.

### 7.9 Tests

| # | File | Assert |
|---|---|---|
| X1 | `tests/test_firstlesson.py` | `self_check()` clean; `teach` is idempotent; `teach` returns `{}` for an unknown id; `pending` shrinks by exactly one per `teach` |
| X2 | same | **the board handover**: with `sweep_fired` true, `speaker` is `"board"`, `channel` is `"toast"` and `lines` is exactly `[Beat.board]` for every unfired beat |
| X3 | same | after `captives.final_release`, `speaker` is `"thessaly"` again |
| X4 | `tests/test_keys_and_seal.py::TheSealedRule` | `POST /api/lesson` during an open measured run returns `{}` and **writes nothing** — the latch is byte-identical before and after |
| X5 | same | `firstlesson.available_in(config.MODE_INTERVIEW)` is `False`, checked by string rather than trusted, the way `PRACTICAL_IS_NEVER_GATED` is |
| X6 | `tests/test_corpus.py::TestCorpus::test_the_rune_pile_is_never_the_solution_in_order` | **WRITTEN.** The §4.3 tripwire: for every `RUNE_ASSEMBLY` in the corpus, `mcq["shuffle"]` is neither the identity permutation nor sorted, and it is a permutation of every rune index. Measured on the shipped corpus: 42 RUNE_ASSEMBLY problems, shuffle present 42/42, identity 0/42, sorted 0/42. `validate.py` only checks the shuffle's **length**, so `[0,1,2,…]` would pass it — this is the assertion that catches the day the pile becomes the answer in order. `puzzleui.js`'s fallback for a missing shuffle was `runes.map((_, i) => i)`, which rendered the canonical solution down the tray in order; it is now `[]`, an empty pile, which is a visible bug rather than a silent leak. Both were rendered in a browser to check which is which. |
| X7 | `tests/test_tutorial.py::TheGatesFailClosed` | every gated entry point called with **no keyword arguments** returns `{}` / `False` and leaves the save byte-identical: `teach`, `cue_note`, `forget`, `cueable`. A default that has to be remembered is not a gate. |

Run from `tests/`: `cd tests && python3 -m unittest test_firstlesson`.

---

## 8. Open questions, with the recommendation

| # | Question | Recommendation | Reason |
|---|---|---|---|
| 1 | Should the cue be off in a measured run, given a player can sit the practical first? | **Off.** | Two independent reasons (§1.5) and the static labels stay on. Comparability is the stronger of the two and it is the one to quote. |
| 2 | Should the cue ever point at a failing trial? | **Never, in any mode.** | `WEAKNESS_MAP` and `COACH` with a triangle in front. The single most tempting row in the table. |
| 3 | One arrow or several? | **One.** | §1.2. The plural is paid back in words by beats 3 and 4. |
| 4 | RUNE_ASSEMBLY's pile — cue it or not? | **Cue it, with the tripwire in §4.3 written into a test.** | Position in a shuffle is noise. The day it stops being a shuffle it is signal, and X6 is how anybody finds out. |
| 5 | Latch in `localStorage`, like `explainBlank`, or in the save? | **In the save.** | It has to survive an import and a different machine, and the panel needs to be able to count what is left. `explainBlank` is one sentence; this is two dozen. |
| 6 | Does Thessaly ever speak inside a battle? | **No, ever.** | Rung 5 of the crutch ladder is a companion speaking in a fight. The cheapest way not to be mistaken for `PET` is not to be there. |
| 7 | What happens to unfinished lessons at the sweep? | **The board.** §6.2. | It is already her prop, in her own capture lines, three times. Costs one field. |
| 8 | Should the belt be cued in a fight? | **No — it is beat 21 instead.** | The belt's lesson is *"the one thing that does not end your turn"*, and that is a sentence, not an arrow. |
| 9 | Dwell of 8 s — too long, or too short? | **8 s, and revisit with a real player.** | 4 s is thinking; 8 s is searching. This is the one number in §2–§3 that is a judgement rather than a measurement, and it is flagged as such. |
| 10 | Does the cue need an `aria-live` announcement? | **No, and it must not have one.** | It is a decoration over a control that is already focusable and already labelled. Announcing it would make a screen reader read the triangle instead of the button. `pointer-events: none` and no ARIA. |

---

## 9. The one-line summary, for the next agent

> One violet triangle, six pixels of it, on the left edge of one control at a
> time — and it may point at a control because of what the control IS, never
> because of what the last attempt DID. It reads four facts, is off in a
> measured run for two independent reasons, and retires each control after three
> shows or three uses. Thessaly Brun teaches twenty-four things once each, never
> inside a battle and never in a measured run, and whatever she has not reached
> by the time the Interviewer takes her is chalked onto the board on the wall
> and delivered one line at a time by a square with nobody standing in it.
