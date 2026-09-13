# What a measured run may see

One rule, the reasoning behind it, and every view in the game listed against it.

This document exists because the line was being drawn six times by hand. During
a measured run `/api/hunt` is refused and `/api/town` is not; `/api/regalia` is
refused and `/api/forge` is not; `/api/sage` is refused and `/api/arts` is not.
Every one of those calls was argued correctly in a comment above the line that
made it, and every one of those comments makes a *different* argument. Six
arguments will not survive the next ten features. One rule might.

---

## 0. What this rule is not about

**The practical exam is a measurement, not a reward.** A player must be able to
sit it at any time, from the menu, with nothing unlocked and nothing earned.
That is the entire point of the game and nothing in this document narrows it.

This rule governs one thing only: **what a run may READ while it is open.** It
says nothing about who may start one, and it must never be quoted in an argument
about who may start one.

---

## 1. The rule

> **A measured run may see the WORLD. It may not see the PROBLEM.**
>
> The **world** is everything that is true whether or not a run is open: where
> you are, what you own, what you have done, what things cost, and the rules
> everybody plays by.
>
> The **problem** is the question currently on the screen, anything derived from
> it, anything that advises what to do about it, and any number the seal has
> already switched off.

### The three questions

A view is **open** only when all three answers are *no*.

1. **The swap test.** If the question on the screen were swapped for a different
   one, would this view answer differently? If yes, it is about the problem.
2. **The in-force test.** Does this view report a number the seal has suspended —
   a gear effect, a class bonus, a readiness score computed from a build that is
   not in play? If yes, it is reporting something that is not true right now.
3. **The spend test.** Does reading this view consume or disclose hold-out
   content? If yes, reading it is spending the one finite thing in the corpus.

### The write clause

A GET is a view. A view that changes the save, grants a resource, or moves
mastery is not a view, and this rule does not license it. That question is
`Game._pays_into_the_world` and it is asked separately.

### The gap clause

**Ask the RUN, not the encounter.** `finalexam.sealed(encounter, capability)`
is the one capability check and it is the right question — but it is asked of
an ENCOUNTER, and **between two questions of a measured run there is not one.**
Every door that asked it with `self.encounter` therefore answered *not sealed*
in the gap. The town's doors are doors that pay:

```
POST /api/exam/start        # the run is open; no question served yet
POST /api/heal              # stamina 1 -> 20, free, mid-exam
```

`Game._sealed_for(capability)` is the fix and `Game._run_is_open()` is the
predicate underneath it: a run is open or it is not, and that does not depend
on whether a question happens to be on the screen this second. A hold-out
problem served in Adventure Mode is untouched, which is the distinction
`_pays_into_the_world` exists to protect.

### The three outcomes

A view that fails a question has three honest answers, in order of preference:

| Outcome | When | Precedent |
|---|---|---|
| **DEGRADE** | The view has a world half and a problem half. Serve the world half; zero the other and say so. | `regalia.view(sealed=)`, `forge.effects_in`, `minirepo.player_view`, `finalexam.suspended(capability)`, 200 |
| **REFUSE** | The whole view is the problem. | `finalexam.refuse(capability)`, named capability, 409 |
| **OPEN** | All three answers are no. | most of the map |

**A degrade must not answer 409.** `server._reply` turns any payload carrying
`error: "sealed"` into a 409, which tells the client there is no answer — so a
view that carefully served its world half and then splatted
`finalexam.refuse()` on top had that half thrown away at the door.
`finalexam.suspended(capability)` is the same capability and the same sentence
without the key that does it, and it is the shape a DEGRADE returns.

Degrading beats refusing wherever it is available, because a screen that refuses
to show a player their own game is a refusal with no rule behind it — and
because a refusal teaches the player nothing while a zeroed number teaches them
exactly what the seal took.

---

## 2. Why this is the right line

**Why the world is safe.** The measurement asks one question: can you write
Python, unaided, under time. Knowing that you own a cloak, that the Marsh runs
on poison, that a hefty draught costs forty gold, or that ninety-eight people
are still held in the Castle does not help you write the function. Refusing it
costs the player the ability to see their own game and buys the measurement
nothing. A seal that takes more than it needs is a seal players learn to resent,
and a resented seal is one somebody eventually turns off.

**Why the problem is not.** Read `finalexam.CRUTCHES` from the top. HINTS,
MENTOR, WEAKNESS_MAP, PROBES, PET, VISUALS, PATTERN, COACH, SOLUTION — every
rung on that ladder is a different way of knowing something about the question
in front of you that you did not work out yourself. The crutch ladder is already
the complete enumeration of what a measured run must not see; this rule is that
list, restated as a property so that a view invented next year is covered by it
without anybody having to remember to add a fourteenth crutch.

**Why the in-force test is separate.** This is the one that is not obvious, and
it is the one that produced most of the existing seals. `SKILL_STATE` is on the
ladder because *your own numbers, shown beside the question, tell you what is
being tested*. The same defect appears wherever a screen reports a bonus the
seal has switched off: the number is not a hint, but it is **false**, and it is
false in the player's favour. A wrong number is worse than no number, because
the player will plan against it. `regalia.view` and `forge.effects_in` were both
written to answer exactly this, and both answer it by returning empty rather
than reduced — a half-working legendary is worse than an honest nothing.

**Why the spend test is separate.** Hold-out problems are the only finite
resource in this game. A sealed problem is spent when it is **served**, so any
view that leaks an id, a title or a lineage lets a player collect the hold-out
for free and study it. `Game.run_view` already documents this defect and its
fix — and it is separate from the swap test precisely because a roster is not
*about* the question on the screen, so the swap test would wave it through.
Finding 4.H was that exact case. It is closed: `Game.export` redacts `state["interview"]` and `state["exam"]` on every export, run or no run.

---

## 3. Every view, against the rule

Status is what the code does **today**, after the keys-and-phases pass closed
all eight findings in section 4. No view is on the wrong side of the rule as
this is written; section 4 is kept as the record of what was wrong and why.

### The world — open, and correctly

| View | Endpoint | Shows | Why open |
|---|---|---|---|
| Dashboard | `/api/state` | Player, skills, regions, bosses, stats, retests due | What you have done. The pattern of the question is not named anywhere in it, and the pairing is what would leak, not the table. |
| World tables | `/api/world` | Regions, bosses, mentors, items, the seed | Static geography. Identical for every player and every run. |
| World map | `/api/world-map` | Map, unlock state, region affinities | Where you are. |
| Region card | `/api/region` | Geography, hazard, ground element, step cost | World. `step` and `boots` are null mid-run — 4.D, fixed. |
| Routes / events / todo | `/api/routes`, `/api/events`, `/api/todo` | Roads out, open gates, the no-dead-end list | Where you may go. `things_to_do` is never empty and must not become empty during a run. |
| Town square | `/api/town` | The Mender, the Armorer, the loop report | DEGRADES. Prices are not a hint and the shelf stays readable; the MENDING half is in-force and is zeroed with the seal — see 4b.II, and `upkeep.loop_report(sealed=)`. |
| Shop and broker | `/api/shop`, `/api/broker` | Stock and prices; the trial board | Reading the shelf is world. *Spending* is a POST and is sealed there. |
| The forge | `/api/forge`, `/api/forge/technique`, `/api/forge/swap`, `/api/forge/metals` | The bench, the rack, where each metal drops | What you own and where things come from. The blade's live NUMBERS are removed inside the engine by `forge.effects_in`. |
| The wheel | `/api/wheel` | Elements, statuses, hazards, boots, potions, matchup table | The rulebook. A rulebook the player cannot read is a mechanic they conclude is broken. Which element the thing in front of them is made of lives behind `WEAKNESS_MAP`, where it belongs. |
| Companions | `/api/pets`, `/api/pets/discovery`, `/api/pets/tiers` | Roster, discovery progress, the tier ladder | Who you have and what you are short of. No companion may speak during a run; `PET` handles that. |
| Sanctuaries | `/api/sanctuaries` | People found by being hurt in the right place | A log of what you have done. |
| Roll call | `/api/rollcall` | The captives, freed and still held | The story's ledger. It has never seen a question. |
| Arts | `/api/arts` | The arts this playthrough knows | What you own. Unlearned arts are named but their lines are not rendered. |
| Quests | `/api/quests`, `/api/quest`, `/api/chains` | The board, one offer, the chains | Where you are in the story. |
| Classes | `/api/classes`, `/api/class/tree` | The discipline roster and the tree | What you own. *Spending* a node is a POST and is sealed. |
| Dungeons | `/api/dungeons`, `/api/dungeon` | The list; the run you are in | Geography. An apex does not enter one and neither does a measured run. |
| Legendaries | `/api/legendaries`, `/api/legendary`, `/api/hand` | The codex; the Hand's offer | The codex is lore. `/api/hand` reports `sealed: true` rather than hiding — the honest shape. |
| Saves | `/api/saves` | Slots and undo | Saving mid-run banks the run; it does not help with it. |
| Exam ladder | `/api/exam/ladder` | Which boss takes which crutch | The rules of the measurement, which the measurement is entitled to state. |
| Transfer report | `/api/transfer` | Whether any of it transfers | A measure of you, not of the question. |
| Curriculum | `/api/curriculum` | The chapter ladder and the next objective | Your position on the ladder. It names families, never the question's family. |
| Story log | `/api/story` | Quest log, session script, honorific | What has happened to you. |
| Diagnostic | `/api/diagnostic` | The placement trials | Its own measurement, and a separate one. |
| World card | `/api/world/card` | The seed and the shape of this run | Static per playthrough. |
| Incantation | `/api/incantation`, `/api/incantation/state` | The encounter list; an open cast-fight | A run cannot start one — `start_incantation` seals — so the live view is unreachable inside a run. |
| Mini-repo board | `/api/repos` | The index cards and which are cleared | What you have done. The fight itself degrades through `minirepo.player_view`. |
| Probes left | `/api/probes` | A charge count | Open **by accident and correctly**: `probes_remaining` returns 0 under `sealed(enc, "PROBES")`. See 4.C. |
| Ping / sandbox | `/api/ping`, `/api/sandbox/check` | Liveness; the sandbox proof | Infrastructure. Neither has ever seen a question. |
| Save export | `/api/export` | The save, minus two keys | Looks like infrastructure; was not. `interview` and `exam` are redacted always — 4.H, fixed. |

### The problem — sealed, and correctly

| View | Endpoint | Capability | Which test it fails |
|---|---|---|---|
| Repair desk | `/api/town/quote` | `UPKEEP` | In-force. Armour integrity is BUILD and a measured run is build sealed, so a quote for kit that is not being worn is a price for nothing. It is a REFUSE rather than a DEGRADE because there is no world half left once the kit is out of play — the whole view is one number about a suspended thing — and `upkeep.repair_quote(sealed=True)` says exactly that in a sentence. `/api/town` beside it now agrees; it did not, which was 4b.II. |
| Regalia | `/api/regalia` | `PET` | In-force. `regalia.view` takes `mode=`/`sealed=` and zeroes the schedule; `Game.regalia_view()` passes neither, so the screen would report a threshold and an intervention count that are not in force. |
| The sages | `/api/sage` | `MENTOR` | Swap + capability. A sage is a named teacher with a line about the pattern. `sages.available_in` already refuses, but it refuses from the encounter, and between problems there is not one. |
| The antagonist | `/api/antagonist` | `MENTOR` | Swap. He has a line about how you are doing, which is a mentor with a grudge. DEGRADES: standing and pressure are graded evidence and stay; `lines` and `moves` empty. He speaks through `finalexam.suspended` at 200 rather than `refuse` at 409 — see 4b.III — and the seal is asked of the RUN, not of an encounter that does not exist between two questions. |
| The hunt | `/api/hunt` | — | DEGRADES rather than refusing — 4.F, fixed. The pace is world and is served whole; readiness is computed with `build_sealed=True` and labelled. |
| Hint route | `/api/hint/route` | `HINTS`/`PET` | Swap. It reads the encounter in front of you. Already correct: it refuses when both capabilities are shut and it is pure either way. |
| Mini-repo view | `/api/repo` | several | Swap. `_repo_payload` builds a capability set through `finalexam.sealed` and degrades field by field. The model answer for the DEGRADE outcome. |
| Current question | `/api/interview/current` | — | This *is* the problem, served through `player_view(mode="interview")`, which redacts the pattern, the hints and the visualisation. It is the run itself, not a side door onto it. |

### Fixed in the keys-and-phases pass

Every row below was on the wrong side of the rule when this document was
written. All seven are closed, and each is tested by name in
`tests/test_keys_and_seal.py::TheSealedRule`.

| View | Endpoint | Failed | Outcome now |
|---|---|---|---|
| **Problem lookup** | `/api/problem` | Swap — 4.A | `Game.problem` DERIVES the mode; the parameter can only make the answer stricter |
| Attempt history | `/api/history` | Swap — 4.B | DEGRADE: aggregates served, `problem: []` while a run is open, with the reason named |
| Loadout | `/api/loadout` | In-force — 4.E | DEGRADE: what you own stays; `effects`, `effect_text`, `armour`, `probe_charges`, `strike_element` are zeroed and marked `suspended` |
| Region card (`step` only) | `/api/region` | In-force — 4.D | DEGRADE: `step` and `boots` are null mid-run; the geography stays |
| **Save export** | `/api/export` | Spend — 4.H | `state["interview"]` and `state["exam"]` are redacted ALWAYS — a reload re-derives both |
| Shrine | `/api/shrine/answer` | Write clause — 4.G | The riddle is still answered and graded; the PAYMENT is refused, through `_pays_into_the_world` |
| The hunt | `/api/hunt` | Over-refuses — 4.F | DEGRADE: `pace_for` is served in full, readiness is computed with `build_sealed=True`, and a line says which half is which |

One more was found while applying the rule and is fixed with them:

| View | Endpoint | Failed | Outcome now |
|---|---|---|---|
| **Start a boss** | `/api/boss/start` | Write clause | REFUSE. `start_encounter` writes `state["encounter"]`, so opening a boss during a measured run replaced the question being measured. A player could destroy their own exam by pressing the wrong thing, and the practical is the one screen in this game that must never be losable by accident. |

---

## 4. The findings

### A. `/api/problem` hands over the whole crutch ladder for the question on the screen — CRITICAL

`Game.problem(problem_id, mode=...)` takes the mode **from the query string** and
passes it straight to `Problem.player_view(mode=mode)`. That method redacts the
pattern, the hint tree, the visualisation, the common failures and the optimal
complexity **only when the string is exactly `"interview"`**.

The problem id is in the encounter payload the run itself hands the client —
it has to be, or the client cannot submit. So during a measured run:

```
GET /api/problem?id=<the id on the screen>&mode=adventure
```

returns `pattern`, the full `hint_tree`, `visualization`, `common_failures`,
`optimal_complexity`, `variants` and `prerequisites` for the question being
measured. That is `PATTERN`, `HINTS`, `VISUALS` and most of `WEAKNESS_MAP`,
through one GET, with no capability consulted anywhere on the path.

Hold-out problems are safe — `Game.problem` refuses `corpusmod.is_sealed(p)`.
But `start_interview` falls back to `self.teachable` whenever the hold-out has
nothing left at a rung, and every one of those falls through.

**Fix (engine.py, not mine to make):** the mode of a lookup is not the client's
to declare. `Game.problem` should derive it — `config.MODE_INTERVIEW` whenever
`self.state.get("interview")` or the open encounter is a measured one — and
ignore the parameter in that case. One line, and the door closes.

### B. `/api/history?problem_id=` names the family — HIGH

`db.attempts_for` is `SELECT *`, and the `attempts` table stores `pattern`,
`family`, `declared_pattern` and `root_cause`. Ask it for the id on the screen
and prior attempts answer with the family name. Same leak as A, one hop further
round, and it survives fixing A.

**Fix:** while a run is open, serve the aggregate keys (`recent`, `stats`,
`bosses`, `interviews` — all world) and return `problem: []`, or refuse
`problem_id` when it is in the open run's roster.

### C. `/api/probes` is right for the wrong reason — RECORD ONLY

`probes_remaining()` returns 0 under `finalexam.sealed(enc, "PROBES")`, so the
endpoint passes the in-force test. It passes because the *method* holds the
line, not because the door does. Nothing to change; this entry exists so that
whoever next edits `probes_remaining` knows what it is holding up.

### D. `/api/region` quotes a step cost that is not in force — LOW

`region_view` computes `elements.hazard_step(region_id, boots, roll=1.0)` from
the boots actually equipped. Boots are `BUILD`, and `_player_defender` passes
`build_sealed=True` into `elements`, so the quoted cost is not the cost. Narrow
and real: the rest of the row is geography and stays.

**Fix:** pass the seal into `region_view`, or drop `step` while a run is open.

### E. `/api/loadout` reports a suspended build at full strength — HIGH

`Game.loadout()` ships `effects`, `effect_text`, `armour`, `probe_charges` and
`strike_element`, all computed from `self.effects()`. In a measured run
`_player_defender` hands `build_sealed=True` to `elements`, so none of them are
in force. Half the screen already knows this — `forge.effects_in` returns empty
under the seal, so the blade's contribution is correctly absent — and the other
half does not, which makes the screen internally inconsistent as well as wrong.
This is the `regalia` defect wearing a third hat.

**Fix:** DEGRADE. Keep `slots`, `equipped`, `inventory`, `consumables`, `pouch`,
`sets`, `rarities`, `secrets`, `attributes`, `build` — all *what you own*. Zero
`effects`, `effect_text`, `armour` and `probe_charges` and mark them suspended,
the way `regalia.view(sealed=True)` already does. `equip`/`unequip` return
`loadout()` too, so the same fix covers both.

### F. `/api/hunt` should degrade rather than refuse — LOW, and newly cheap

The seal is correct: `hunt_view` calls `_readiness_for(region)` with `sealed`
at its default and would report a preparation score counting bonuses that are
not in play. But `hunters.readiness_from_game` **already takes `build_sealed=`**,
and since the chapter ramp landed, everything else on that screen is
player-independent: `hunters.pace_for(region)` returns the cast band, the strike
multiplier and the teaching stance from `curriculum.CHAPTERS` and the region id
alone. The chapter says how big the place is; readiness says where in it you
land. Only the second half is sealed.

**Fix:** pass `sealed=True` down and serve the view. A run then sees where the
creature is and how long its fight is — both world, both now provably
independent of the player — with the readiness readout at zero and a line saying
why. Strictly better than a 409, and it is the DEGRADE outcome on a screen that
can now support it.

### G. `/api/shrine` is a GET that pays — MEDIUM, write clause

`Game.shrine()` rolls a question, writes `state["_shrine"]` and calls `save()`.
`Game.shrine_answer()` grants stamina, mana and XP and calls
`skillmod.apply_outcome` on two skills. Neither consults `finalexam.sealed` nor
`_pays_into_the_world`, so a measured run can heal and move mastery off trivia
between questions. Not a view leak — a payment leak, on a door that looks like a
view, which is exactly why the write clause is part of the rule.

**Fix:** `_pays_into_the_world` at the top of `shrine_answer`; a run may read the
riddle and may not be paid for it.

### H. `/api/export` hands over the unserved hold-out roster — CRITICAL, spend test

`Game.run_view` was fixed once already, and its docstring says why better than
this document can: a measured run reaches for the hold-out first, so
`run["problem_ids"]` is *a list of sealed problems the player has not been served
yet*, and a sealed problem is spent when it is **served** — so reading the list
costs nothing and buys the player the ability to go and study exactly the
questions the selector likes best. `run_view` now returns `total` instead.

`db.export_save` returns `load_state(conn)` whole, and `state["interview"]` is
in the save with `problem_ids` intact. Reproduced against a fresh game:

```
POST /api/interview/start            -> run_view: no problem_ids  (correct)
GET  /api/export  -> state.interview.problem_ids
                     ['ll-nth-from-end', 'tp-merge-sorted',
                      'sw-distinct-windows', 'll-reorder']
                     of which three are sealed hold-out ids, none yet served
```

The final practical is worse. `Game._start_exam` writes `self.state["exam"] =
exam.to_dict()`, and the engine's own comment two lines below says that dict
"carries every question's problem_id and title" — which is why the response uses
`exam.player_view()` instead. The save keeps the other one, and `/api/export`
ships the save.

This is the same defect as `run_view`, through a door nobody re-checked, and it
is why the spend test is a question in its own right rather than a footnote to
the swap test: the roster is not *about* the question on the screen, so the swap
test does not catch it.

**Fix:** `export_save` should redact `state["interview"]["problem_ids"]` and
`state["exam"]` while a run is open — or, better, always, since neither is
needed to restore a save that a reload will re-derive. The `attempts` and
`transfer_encounters` tables are fine: those name problems that have already
been spent.

---

## 4b. The adversarial pass: four more, found by playing

Section 4 was written by reading. These four were found by opening a measured
run and calling every door in the game to see which ones answered.

### I. Everything the town pays, paid in the gap — CRITICAL, write clause

`Game.heal`, `Game.repair`, `Game.repair_quote` and `Game.sanctuary_rest` all
asked `finalexam.sealed(self.encounter, UPKEEP_CAPABILITY)`. Correct question,
wrong subject: **between two questions of a measured run `self.encounter` is
None**, and `finalexam.sealed(None, ...)` is False. Reproduced against a fresh
game:

```
start_interview("FINAL_EXAM")     # run open, no question served
heal()                            # {"ok": true} — stamina 1 -> 20
```

`Game._antagonist` already carried this exact paragraph for its own case and
already fixed it. Nothing generalised the fix. **Fixed:** `Game._sealed_for`
and `Game._run_is_open`, and the gap clause in section 1 says so as a rule
rather than as four call sites.

### II. The town square contradicted its own repair desk — HIGH, in-force

`Game.town` passed the seal into `town_visit` and `repair_quote` and **not**
into `loop_report`, which sits on the same payload. So a measured run got
`quote: {"error": "sealed", "message": "Nothing is being worn in here…"}` two
keys away from `loop: {"quote_now": 33, "line": "Your chestplate wants Ferro
now. 33 gold puts the whole kit right…"}`. Finding 4.E's defect — a number that
is not a hint and is still false — through a door nobody re-checked.

**Fixed:** `upkeep.loop_report(sealed=)` DEGRADES. The mending half is zeroed
and named in `suspended`; income, the third-of-income ceiling, the escape hatch
and the free list are world and stay.

### III. A degraded view shipped under a refusal — MEDIUM

`Game.antagonist_view` degrades correctly — standing and pressure served, lines
emptied — and then splatted `**finalexam.refuse("MENTOR")`. That carries
`error: "sealed"`, `server._reply` reads it and answers **409**, and the client
throws away the half that was served. A DEGRADE that announces itself as a
REFUSE is a REFUSE.

**Fixed:** `finalexam.suspended(capability)` — same capability, same sentence,
no `error` key — and the outcome table in section 1 now names the shape.

### IV. The placement could be farmed for unaided clears — CRITICAL

Not a seal finding. A rule finding, and the rule is *mastery moves only on
graded evidence*.

`diagnostic.seed_skills` is, by its own docstring, "the one place mastery moves
without a graded attempt", bounded so it stays weak evidence: mastery caps at
35, confidence at 18. It is not bounded against being **called twice**.
`state.mastery + gain` accumulates and the writing trial books
`attempts += 1; clears += 1; unaided_clears += 1` every call, and
`diagnostic_finish` never read the `done` flag it had just written:

```
50 x POST /api/diagnostic/finish
  -> PYTHON mastery 35.0, clears 50, unaided_clears 50, attempts 50
     with no code run anywhere
```

Unaided clears are what `adaptive.readiness` and the castle gate are counted
in. **Fixed:** a placement is taken once. A repeat returns the placement
already taken — with `already: true` and the next objective, not an error,
because a client retrying a dropped response must not be handed a dead end —
and the door is sealed in a measured run like every other door that pays.

Four more doors were sealed for consistency while closing I: `respec` (spends
gold), `allocate` (spends a point `respec` charges gold to get back), and
`equip` / `unequip` (rearranging a build the run has already suspended — the
same shape as `set_active_pets`, which already refused). A sweep of 37 engine
doors in the gap now reports zero that pay.

---

## 4a. What the keys and the portal are, against this rule

Three views arrived with the boss-key pass and all three are **open**, checked
against all three questions rather than waved through:

| View | Endpoint | Swap | In-force | Spend |
|---|---|---|---|---|
| The keyring | `/api/keys` | no — a key is a boss you beat | no — derived from `cleared_bosses`, which no seal suspends | no — names bosses and roads |
| The Standing Portal | `/api/portal` | no | no | no |
| The town square | `/api/town` | no | no | no — it now carries `portal` in one region |

Stepping THROUGH the portal (`POST /api/portal/enter`) is sealed, because it
changes the world. That is the write clause and not the view rule.

**And the thing this document said in section 0, now said with a route number.**
The portal gates the story climax. It does not gate `/api/interview/start`,
which reads no key, no boss and no road — `finalexam.py` is checked for those
strings by a test rather than trusted. A player at level one holding nothing can
sit the practical, and every payload that counts keys carries
`practical: {open: true, requires_keys: false}` so the screen that counts them
is also the screen that says so.

---

## 5. Applying this to something new

When a new view is added, write one line in its docstring naming which of the
three questions it was checked against and what the answer was. That is the
whole process. If the answer to any of them is yes, prefer DEGRADE, name the
capability from `finalexam.CRUTCHES`, and return `finalexam.refuse(capability)`
only when there is no world half left to serve.

There is one capability check in this game and it is `finalexam.sealed`. This
document adds no second one. It is a rule for deciding **what to ask it about**.
