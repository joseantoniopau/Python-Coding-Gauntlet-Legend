# The Ramp

> "i like the ramp up of multiple choice to complete the arguement and then fill
> in the blank slowly as repetition kicks in so the user slowly is trained to
> write the code for all. make this ramp more prevalent in the lower level and
> slowly tapper as diffculty increases."

This document decides the target curve. It authors no problems.

Everything numbered here was measured against the shipped corpus
(`corpus.json`, 1,013 problems, fingerprint `34066dccf57ec0ea`), not estimated.
The scripts are throwaway; the numbers are reproducible from the definitions
given in each section.

---

## 0. The ladder, and which axis it lives on

Four rungs, in the player's words:

| rung | name | what the player supplies |
|---|---|---|
| 1 | **PICK** | chooses the token that completes the line |
| 2 | **ONE BLANK** | writes one expression — the one that carries the idea |
| 3 | **MANY BLANKS** | writes several pieces of a given skeleton |
| 4 | **WRITE IT ALL** | the whole function, from nothing |

**The first correction this document makes: rung 1 does not exist in the
corpus.**

The brief measured rung 1 as `entry.kind == 'mcq'` and found 149. Those 149 are
real, but they are not this ladder. Broken out by encounter kind:

| encounter kind | count | what it asks |
|---|---|---|
| CODE_READING | 36 | read this code, say what it does |
| TRACE | 25 | what is this variable after line 4 |
| PATTERN_ENCOUNTER | 24 | which pattern is this |
| COMPLEXITY_DUEL | 17 | what is the complexity |
| SPOT_THE_FLAW | 14 | which line is wrong |
| STATE_PREDICT | 12 | what is the state after these operations |
| EDGE_CASE_TRAP | 11 | which input breaks this |
| COMPLEXITY_MATCH | 10 | match snippet to complexity |

Every one of them asks the player to **read and judge** code. Not one asks them
to **complete** a line. They are a genuine and valuable second axis — the
adaptive selector already calls them "spice, not the main course" and lifts that
penalty only at the bottom of the ramp — but they teach recognition, not
production, and counting them as the first rung of a production ladder is what
makes the ramp look non-monotone when it is merely mis-measured.

So the ladder is measured on the **write-code axis**: the 858 problems where
`entry.kind` is `function` or `class_ops` and the player types Python into an
editor. Rungs 2 and 3 are `starter_code.count('__BLANK__')` — exactly 1, or 2+.

### Where the ramp actually stands

Counting mcqs (the brief's table — reproduced exactly):

| band | pick | one blank | many | write all | total | scaffolded |
|---|---|---|---|---|---|---|
| GUIDED | 58 | 123 | 63 | 14 | 258 | 94.6% |
| TUTORIAL | 13 | 2 | 5 | 195 | 215 | 9.3% |
| EASY | 49 | 0 | 21 | 251 | 321 | 21.8% |
| MEDIUM | 28 | 0 | 0 | 168 | 196 | 14.3% |
| HARD | 1 | 0 | 0 | 22 | 23 | 4.3% |

On the write-code axis alone — the only axis the player's sentence is about:

| band | one blank | many | write all | total | **scaffolded** |
|---|---|---|---|---|---|
| GUIDED | 123 | 63 | 13 | 199 | **93.5%** |
| TUTORIAL | 2 | 5 | 195 | 202 | **3.5%** |
| EASY | 0 | 21 | 250 | 271 | **7.7%** |
| MEDIUM | 0 | 0 | 164 | 164 | **0.0%** |
| HARD | 0 | 0 | 22 | 22 | **0.0%** |

The cliff is **worse** than reported: 93.5 → 3.5, a 90-point drop in one step.
The monotonicity violation is **real but small** — 3.5 → 7.7, twenty-one EASY
problems — and it was inflated to "21.8%, and it RISES" by the 49 reasoning
MCQs. Aiming the fix at EASY on that reading would have been aiming it at the
wrong band. **TUTORIAL is the whole job.**

### The sentence that explains the cliff

`curriculum.py`, the comment above `SCAFFOLD_LADDER`:

> GUIDED hands the player complete code with one blank in it. TUTORIAL hands
> them a skeleton and asks for the body. EASY is a blank screen. Those are three
> different acts, and only the third one is what an interview asks for.

Measured, TUTORIAL is 195 of 202 write-it-all — **96.5% blank screen**.
TUTORIAL and EASY are the same act. The engine believes in a three-step band and
the corpus supplies a two-step one, so the middle rung of the ramp is a rung the
code reserves space for and the content never fills.

---

## 1. The target curve

Two numbers per band, because "how much scaffolding" is two different questions.

### 1a. The floor — the most help a band may ever offer

A hard, structural, monotone rule. It cannot be violated by content drift
because it is a property of the serving code, not of any problem record.

| band | lowest rung servable | meaning |
|---|---|---|
| GUIDED | 1 | a pick is allowed; the line is always shown |
| TUTORIAL | 2 | never a pick; at minimum, one expression is written |
| EASY | 3 | never a single hand-held blank; at minimum, several pieces |
| MEDIUM | 4 | write it all |
| HARD | 4 | write it all |
| practical / interview / hold-out | 4 | write it all, no exceptions, ever |

Monotone by construction: `1 ≤ 2 ≤ 3 ≤ 4 ≤ 4`. Today's EASY violation is
excluded at the floor — an EASY problem may be served at rung 3, never rung 2.

### 1b. The expected mix — what an audit measures

For a player entering the band at the competence the band assumes:

| band | pick | one blank | many | write all | **scaffolded** | today |
|---|---|---|---|---|---|---|
| GUIDED | 25% | 45% | 25% | 5% | **95%** | 93.5% |
| TUTORIAL | 10% | 30% | 30% | 30% | **70%** | 3.5% |
| EASY | 0% | 10% | 25% | 65% | **35%** | 7.7% |
| MEDIUM | 0% | 0% | 10% | 90% | **10%** | 0.0% |
| HARD | 0% | 0% | 0% | 100% | **0%** | 0.0% |

**95 → 70 → 35 → 10 → 0.** Strictly decreasing, which is the requirement.

The reasoning, band by band:

- **GUIDED 95%** is already true (93.5%) and stays. This is the band where a
  player cannot type yet. The change here is not quantity but shape: a quarter
  of it becomes rung 1, which is the rung the player explicitly asked for and
  the corpus has none of.
- **TUTORIAL 70%** is the entire fix. The player said "slowly as repetition
  kicks in"; today the repetition never happens, because the step from GUIDED
  lands on a blank screen. 70% also finally makes the code's own description of
  TUTORIAL true.
- **EASY 35%** is the first band where writing it all is the majority act (65%).
  This is deliberate and it is the answer to "the taper must actually reach
  write-it-all well before HARD". A player leaving EASY has produced whole
  functions more often than not.
- **MEDIUM 10%** is not a teaching rung. It is a **recovery** rung: the only way
  to be served a scaffold at MEDIUM is to have just lapsed on that skill. A
  player in good standing sees 100% write-it-all at MEDIUM.
- **HARD 0%**, with no mechanism to reach anything else. By HARD the game has
  nothing left to say about scaffolding.

This is a game about writing Python cold. The taper is finished — as a teaching
device — one full band before HARD, and the last two bands exist to prove it
took.

#### HARD's "no mechanism" is now a mechanism, not an accident

That sentence was written as a structural guarantee and shipped as a content
coincidence. `curriculum.lapse_floor` returned `max(PICK, floor - 1)`, which is
**3 for HARD, ELITE and BOSS** exactly as it is for MEDIUM — so a lapsed review
of a HARD problem carrying two declared spans would have been served two blanks.
The only thing preventing it was that 0 of the 20 HARD editor problems happen to
declare any. One declaration authored at HARD would have turned this paragraph
into a lie, silently. `lapse_floor` now returns `WRITE_IT_ALL` for HARD, ELITE
and BOSS (`curriculum.NO_LAPSE_SCAFFOLD`), and MEDIUM's recovery rung is the one
documented exception it was always meant to be.

### 1c. What the live selector actually serves

§1b's table is about *a player entering the band at the competence the band
assumes*. That sentence names a situation, not a protocol, and the first attempt
to test it built a protocol that does not occur: one fresh `SkillState` per
band, walked through that band's own pool in alphabetical order. It was
order-sensitive — over 400 random orders of the same pools GUIDED came out mean
82.0% (min 72.6) and TUTORIAL mean 69.9% (max 83.1) — and it reported 95.2 /
69.5 / 37.3, green, while the live selector was serving **79.0 / 100.0 / 66.7**:
a rise, exactly where the whole document says there must be a fall.

Measured on `Game.next_encounter` over a 400-encounter career, after the second
spans and the re-sized `RUNG_EVIDENCE`:

| window | GUIDED | TUTORIAL | EASY | MEDIUM | HARD |
|---|---|---|---|---|---|
| first 200 encounters | 90.9% | 82.1% | 61.0% | 0.0% | 0.0% |
| full 400 encounters | 61.3% | 71.2% | 49.3% | 0.0% | 0.0% |

**A whole-career band aggregate is not a measurement of the taper, and the full
400-encounter row is the proof.** It confounds three things:

- **the band**, which is what we want to measure;
- **the skill**, because evidence is filed per skill — TWO_POINTER's GUIDED
  problems arrive after that skill already holds 23 rung-4 clears, while TREE's
  TUTORIAL problems arrive when it holds three;
- **the phase of the career**, because the selector keeps serving GUIDED
  problems at encounter 350, by which point PYTHON is fluent and a GUIDED
  fill-in-the-blank would be an insult. 14 of the 62 GUIDED encounters in a
  400-encounter career are PYTHON, served at 0% scaffolded.

The claim survives in its exact form, and it is stronger than the aggregate:
**for every one of the 241 editor encounters in that career, taking the skill
state in the player's hand and asking all five bands how much help they would
give produces a non-decreasing sequence.** Zero inversions. That is monotone by
construction — `rung_for` starts the climb at the band's floor, so a band with a
lower floor has strictly more gates to pass — and it is asserted per encounter
in `tests/test_the_ramp_rungs.py::TestTheCurve`, where no averaging can hide it.

EASY sitting above its 35% is a **floor**, not a climb: rung 3 is EASY's own
floor, so an EASY encounter is scaffolded exactly when the skill has not yet
reached rung 4, and 111 of EASY's 164 editor problems can render two blanks.
Moving it would be a decision about `FLOOR["EASY"]`, taken in §1a, not a number
to tune in `RUNG_EVIDENCE`.

---

## 2. What it costs

**Zero new problems.** The cost is one declaration per problem, and it is paid
in three uneven instalments.

### The declaration

A problem needs to say **which span of its canonical solution carries the
idea**. Call it `scaffold_spans`: an ordered list, best blank first, each naming
a line and a span within the canonical solution plus the one-line gloss that
becomes the numbered trailing comment.

One declaration generates every scaffolded rung:

- **rung 3** blanks the first 2–3 spans
- **rung 2** blanks span #1 only
- **rung 1** blanks span #1 and offers four choices — the canonical token and
  three distractors

Rung 1 is *nearly* free once rung 2 exists — see §4, "Rung 1 must have something
to pick between". That matters, because rung 1 is the rung the corpus has zero
of and the rung the player named first.

**And rung 3 needs a second span, which is not free.** 120 of the 184 GUIDED
declarations and 75 of the 178 TUTORIAL ones carried exactly one, so
`available_rungs` returned `(1, 2, 4)` and `servable` fell a player who had
*earned* rung 3 straight up to rung 4 — a blank screen at the easiest band in
the game. Measured on the live selector, all 13 of the 62 GUIDED encounters
served at rung 4 were one-span problems; that single fact was the monotonicity
failure, dragging GUIDED to 79.0% while TUTORIAL above it carried a blank on
100.0% of its encounters.

`servable` names it in its own comment and declines to paper over it, because
falling DOWN the ladder was measured and costs the invariant that makes rung
evidence mean anything. So it is closed where content gaps are closed: a second
span for each of the 73 GUIDED and 19 TUTORIAL one-span problems that has a
second idea in the body, which took GUIDED from 79.0% to 88.7% on the same
replay. The 47 left alone are genuine one-line, one-idea functions —
`def area(width, height): return width * height` has one idea, and asking for
two blanks over it would be inventing a second one.

### How many declarations

To reach the mix in §1b, each band needs declared problems in at least the
scaffolded share of its write-code population:

| band | write-code problems | mix target | declarations needed | already have | **to author** |
|---|---|---|---|---|---|
| GUIDED | 199 | 95% | 190 | 186 | **4** |
| TUTORIAL | 202 | 70% | 142 | 7 | **135** |
| EASY | 271 | 35% | 95 | 21 | **74** |
| MEDIUM | 164 | 10% | 17 | 0 | **17** |
| HARD | 22 | 0% | 0 | 0 | **0** |
| | | | | | **230** |

**230 hand-authored declarations. 214 mechanically converted. 0 new problems.**

Be honest about 230: it is a real content pass, roughly a fifth of the corpus,
and 135 of it lands in one band. It is not a weekend. But it is 230 *judgements
about existing validated code*, not 230 new problems — no reference
implementation, no test derivation, no validation run, no lineage question, no
hold-out disturbance. The difference in kind matters more than the count.

### The 214 that convert mechanically

Every problem that already carries `__BLANK__` is already a declaration, written
in the wrong place. Measured across all 214:

- **214/214** have starter and canonical with identical line counts
- **214/214** have every un-blanked line byte-identical to the canonical

There are no exceptions. `starter_code` for a scaffolded problem is, today,
without a single deviation, the canonical solution with spans struck out by
hand. The conversion is a script, not an authoring pass.

### Coverage, if 230 is too many at once

The cheap version buys the ramp's *shape* before its *density*: one declared
problem per `spaced_repetition_family` per band, so that whatever family a
struggling player is in, a scaffolded rung exists there.

| band | families | families with ≥1 scaffold | **families needing one** |
|---|---|---|---|
| GUIDED | 138 | 134 | **4** |
| TUTORIAL | 107 | 7 | **100** |
| EASY | 108 | 19 | **89** |
| MEDIUM | 80 | 0 | **80** |

That is 273 to cover everything, which is worse — but **TUTORIAL alone is 100**,
and TUTORIAL alone removes the cliff. If only one instalment is ever paid, pay
that one.

---

## 3. Where the scaffolds come from

**Render-time transformation of the existing problem. Not new problems.**

### The precedent is already shipped, and it is this exact design

`gauntlet/incantation.py` already implements this ladder, correctly, for combat
spell lines:

```
tier 0  the whole line, with every hole but one already filled
tier 1  the whole line, every hole blank
tier 2  the shape only — keywords and punctuation survive, names do not
tier 3  the incantation's NAME, and nothing else
```

`TIER_NAMES = ("GUIDED", "PROMPTED", "SHAPED", "RECALLED")`. Tier 0 is
"complete the argument", exactly: `render_template` keeps `inc.target_hole`
editable, prefills every other hole, and prompts *"One blank. Name it."* The
tier is chosen by `tier_for(skill_state, stats)` from measured evidence and
nothing else. There is one source of truth — the template — and the rungs are
presentations of it.

The corpus does the opposite: a separate problem record per rung, with the rung
frozen into it and no competence input. Adopting the incantation design for the
corpus is not a new idea; it is the corpus catching up with a mechanism this
codebase already built, named, and shipped.

### Why not new problems in the same lineage

The obvious objection to new siblings is that they might not join the parent's
lineage. **Measured, that objection is mostly wrong, and the real reason is
different.** Adding 229 scaffolded siblings whose canonical solution is copied
verbatim and re-running `assign_lineage`:

```
siblings that did NOT join their parent's lineage: 0/229
```

The structural signal is reliable — *when the canonical solution is copied
byte-for-byte*. The problem is that the one family which authored scaffolds by
hand did not do that. `sc-group-anagrams` and `ah-group-anagrams` are the same
exercise and sit in **different lineages**, because the scaffolds author wrote a
new solution instead of blanking the existing one:

```python
# sc-group-anagrams  (EASY)          # ah-group-anagrams  (MEDIUM)
groups.setdefault(key, []).append(word)   buckets[key].append(word)
return [groups[key] for key in sorted(groups)]
                                     return [sorted(g) for g in buckets.values()]
```

Different algorithm, different output ordering, genuinely different functions.
12 of the 40 `sc-` problems sit alone in their lineage. So "author the sibling
from the same canonical solution" is a **convention that shipped content has
already broken**, and the brief's requirement is that the constraint be
*structurally true rather than a convention somebody remembers*.

Render-time makes it structurally true by construction: there is one problem,
one id, one canonical solution, one lineage. A rung is a way of displaying it.
There is no second record that could drift, so there is nothing to remember.

### The measured cost of the new-problems path

Adding 229 siblings and re-running `seal_holdout`:

```
corpus 1013 -> 1242
sealed      122 -> 149
of the original 1013:
  still sealed that was sealed : 122
  NEWLY sealed (was teachable) :  19
  UNSEALED (was hold-out)      :   0
```

The good news, and it corrects an assumption worth correcting: **no existing
hold-out measurement is voided.** All 122 stay sealed. The cost is the other
direction — **19 problems the teaching side can currently use are sealed away**
as collateral, because `goal = round(total × 0.12)` scales with a corpus that
grew 23% without gaining a single new idea.

Under render-time transformation the input to `seal_holdout` is unchanged, so
the output is unchanged. Verified directly: re-running `assign_lineage` and
`seal_holdout` on the shipped set reproduces **the identical 122 ids**.

### The three other things render-time buys

1. **Validation is inherited, not repeated.** The scaffold is derived from the
   canonical solution that an independent reference already agreed with. A new
   sibling would need its own reference implementation and its own validation.
2. **`starter_code` stops being unchecked duplicated data.** `validate.py`
   checks `starter_code` for exactly two things: that it is non-empty, and that
   a DEBUG_BATTLE's version fails. There is **no check at all** that a blank is
   well-formed, that blanks match their numbered comments, or that filling them
   yields the canonical solution. 214 hand-maintained copies with no check on
   them is how `pt-class-latest` became a `CODE_BATTLE` carrying a `__BLANK__`.
3. **The rung becomes something the selector can ask for**, which is what §5
   needs and what a per-problem frozen rung can never provide.

---

## 4. Which token to blank

> the blank should be the piece that carries the IDEA

### The rule, in priority order

1. **The accumulator's update** — the right-hand side of `+=`, or of
   `x = x + …`
2. **The comparison in the condition** — the test of an `if` or a `while`
3. **The index expression** — what goes inside `[…]`
4. **The state mutation** — the argument to `.append()`, `.add()`, `.popleft()`
5. **The returned expression**, when it is not a bare name

### Never blank

- **a parameter name the body already uses.** `fs-parameter-name` blanks
  `def bill(__BLANK__)` and its own hint reads *"the name the body is already
  using"* — which is the admission. That is a lookup, not an idea.
- **a builtin's name.** `ob-text-length` blanks `len` in `return __BLANK__(text)`.
  Vocabulary recall, not the idea.
- **punctuation, a keyword, or a colon.**
- **a literal the problem statement already gives.** `fs-return-a-constant`
  blanks the `8` in `return 8`, and the statement says 8.

These four are defensible at GUIDED, where naming the part is genuinely the
lesson. None of them is defensible above it, and they are listed because the
corpus contains them and they will be copied if nobody says not to.

### Good blanks, all from the shipped corpus

```python
counts[ch] = __BLANK__   # 1. build the tally for this character
```
`sc-first-unique-char` — the accumulator update. Rule 1.

```python
key = __BLANK__   # 1. a signature every anagram of this word shares, and no other word does
```
`sc-group-anagrams` — the entire idea of the problem in one expression.

```python
while __BLANK__:  # 1. the window is illegal: the incoming character is already inside it
```
`sc-window-no-repeat` — the loop guard, which is the hard part of sliding window
and the part a player who has copied three window problems still cannot write.

```python
return __BLANK__   # 1. what is left of the capacity
```
`fs-two-parameters` — `capacity - used`. Rule 5.

### Do not auto-generate this

The rule above was implemented as an AST pass and scored against all 214 human
choices:

```
rule's #1 line is a line the author blanked:  107/214 = 50%
rule's top-k overlaps the author's choice:    138/214 = 64%
```

**50% is the measured reason to keep a human in the loop.** A scaffold that
blanks the wrong token teaches the wrong thing, and is worse than no scaffold —
it spends the player's attention on the part that did not matter. The rule
*proposes*; a person *confirms*; the declaration is *stored*. It is a labour
saver, not an oracle.

### The objective test, which validation should enforce

A declared span carries the idea if **filling it with a plausible neighbour
makes the tests fail.** A blank that can be filled wrongly and still pass is
decoration.

This is not a new mechanism. `Problem.mutants` and `validate._verify_forge`
already do exactly this for TEST_FORGE: generate wrong implementations, require
that a test kills them. The same machinery, pointed at a span instead of a whole
function, turns "carries the idea" from a matter of taste into a build-time
check — and it is the check `starter_code` has never had.

#### It runs over every span a rung can strike, not just the first

`_verify_scaffold` judged `spans[0]` and stopped. **Rung 3 strikes spans 1
through `MANY_SPAN_COUNT`, and rung 3 is EASY's floor**, so every span past the
first was served to players and checked by nothing. Re-run across all 813 spans
it found four more poor blanks (`ob-repeat-text` #2 `times`, `ob-bigger` #2 `b`,
`ob-dict-store` #2 `price`, `ob-comprehension-first` #2 `nums` — all four the
parameter-name case this section already names) and five more decorative ones
(`py-defaultdict-index`, `oopl-except-order-tutorial`, `oopl-bare-except-tutorial`,
`pt-time-elapsed`, `rp-window-time`). The check now loops to
`MANY_SPAN_COUNT`, reports the span index, and keeps the GUIDED-warn /
above-GUIDED-error split.

Two consequences worth writing down:

- **A mutant is not a validated solution.** Swapping `!=` for `==` in a `while`
  condition is precisely the kind of neighbour this check is meant to try, and
  precisely the kind that never terminates. `_kills` now runs each mutant under
  the same line-event budget `corpus._call_bounded` uses, and treats the budget
  expiring as a disagreement — a canonical solution that stops has disagreed
  with a mutant that does not. A build that hangs is a game that will not start.
- **Undetermined is still not a failure.** A span the neighbour generator has no
  move against is unjudged, not passed; `scaffold_audit` counts those separately
  so the number stays visible.

#### A span may not strike inside a longer name

`resolve_targets` located a declared span with a bare `row.find()`. `ob-dict-store`
declared `("price", …)` and got column 15 — the `price` inside `prices` — so rung
3 rendered `def dict_store(__BLANK__s, __BLANK__, price):`. **`round_trip`
cannot see this**: refilling the hole reproduces `prices` byte for byte, so the
one check written to catch a declaration that describes some other version of
the answer is structurally blind to it. `scaffold._boundary_clean` now rejects a
candidate column when an identifier-shaped span has a word character on either
side of it, keeps scanning, and raises if no boundary-clean occurrence exists.

#### Rung 1 must have something to pick between

`available_rungs` granted PICK on span count alone, but `choices_for` returns
nothing when the neighbour generator has no move against the first span. 55 of
the 498 declared problems rendered `{"rung": 1, "name": "PICK", "choices": []}`
— an ordinary one-blank, byte-identical to the rung-2 render, with the clear
filed at rung 1. Rung-1 evidence does not count toward leaving rung 2
(`curriculum._unaided_at_or_below`), so **the player did rung-2 work and was
credited less than they earned**; and 34 of the 55 are GUIDED, whose floor IS
rung 1, so for those the bottom rung of the ladder did not exist at all.

PICK is now withheld in `available_rungs` — not patched inside `render` — so
`servable` cannot select it, the serving falls UP to rung 2, and `enc.rung`
records the 2 that was shown. `_verify_scaffold` warns when a band whose floor
is PICK cannot render it, which is a content gap worth seeing: 31 GUIDED
problems are in it today.

#### The gloss is the only sentence beside a blank

`annotate` stripped the struck line's own trailing comment and left the
comment-only lines above it standing. 64 problems rendered a canonical comment
within three lines of a blank and several of those comments *were* the answer:
`lang-sortkey-tutorial` kept "`key=len`, not `key=len(words)`. The key is the
function itself." directly over the blank that wants `sorted(words, key=len)`.
`annotate` now drops the contiguous run of comment-only lines above each struck
line — the same walk `_gloss_above` makes in the other direction. And
`_gloss_above` now strips the `N. ` the author had already written, which
`annotate` was numbering a second time: 21 `py-*-guided` glosses rendered as
`# 1. 1. Counter counts whatever you iterate.`

#### Rung 4 is ours too

The rung-parses check skipped `WRITE_IT_ALL` as "the authored starter, which is
not ours". That reasoning predates render-time rungs: `skeleton()` passes the
authored starter through for 533 of the 746 editor-axis problems, so it **is**
ours, and the blanket exemption is what let `oopl-except-order-tutorial` ship a
rung 4 raising `SyntaxError: expected 'except' or 'finally' block` at column one
— through a build reporting zero errors, into MEDIUM, HARD, Interview Mode, the
practical and the hold-out, all of which serve rung 4 unconditionally. The skip
is now narrowed to `not scaffold.scaffoldable(p)`: a DEBUG_BATTLE's broken
starter IS the question, and `db-syntax-colon` stays correctly exempt.

---

## 5. How the player moves up the rungs

> "slowly as repetition kicks in"

**The rung comes from the player's measured competence on that skill, never from
the problem.** A problem that is always rung 2 is a problem the player can never
graduate from, which is the thing the player is asking not to have.

### There is already a correct implementation to copy

`incantation.tier_for` decides the scaffold tier and does every part of this
right:

- it **rises** on accumulated correct casts that are also getting faster
- it **falls one rung per consecutive miss** — a slip costs a little help, a
  collapse costs all of it, with no announcement and no penalty
- it **decays with time away** — 1 rung at 5 days, 2 at 14. The spacing effect
  as a mechanic rather than a lecture
- it is **capped by mastery** of the underlying skill: "typing speed cannot
  outrun comprehension"

The corpus needs the same function over the same kind of evidence. The answer to
*"if a player has cleared six one-blank problems on accumulators, should the
seventh be full code?"* is **no — the seventh is rung 3, and rung 4 comes
after that.** One rung at a time, per skill, on evidence. Six one-blank clears
are six pieces of evidence about writing one expression, and none about writing
a function.

### What curriculum.py already has, and the one line that is wrong

`SkillState` already records evidence at the right grain, and the comment says
why:

> `clears` alone cannot answer "has the scaffolding come off?", because eight
> fill-in-the-blanks and eight blank screens are the same number.

`tier_clears` and `tier_unaided` exist for exactly this. But they are keyed by
**difficulty band**, and the band is not the rung. That single conflation is a
live defect:

```python
def has_produced_code(state) -> bool:
    """Has this skill ever been cleared, unaided, without a scaffold?"""
    return unaided_at_or_above(state, PRODUCTION_TIER) >= 1   # PRODUCTION_TIER = "EASY"
```

Run against a fresh player who clears **one** EASY problem unaided:

```
after ONE unaided EASY clear (a 2-blank MISSING_RUNE):
  tier_unaided          : {'EASY': 1}
  has_produced_code     : True
  scaffold_target       : None      <- the scaffold band is over
  scaffold_cleared      : True
```

The corpus contains **21 EASY problems with 2–3 blanks**. Clearing any one of
them ends the scaffold band outright and satisfies the `scaffold` clause on
every `TIER_GATE` above it. The escape hatch was designed to fire only for a
player who "produced working code on a blank screen"; it fires for filling in
two blanks. This is the mastery-farm the brief warns about, and it is live
today, not a risk introduced by this plan.

**The fix, which is also what makes the lineage rule structurally true:** record
the rung alongside the tier, and make `has_produced_code` require rung 4.

```
rung_unaided : {4: 1}   ->  has_produced_code
rung_unaided : {2: 6}   ->  not produced code, no matter how many
```

Once evidence is filed by rung, a scaffolded serving **cannot** produce rung-4
evidence, because the rung is recorded from what the player was actually shown.
Not a convention — an arithmetic impossibility. `SCAFFOLD_LADDER`'s existing
shape (8 unaided at GUIDED, 6 at TUTORIAL) is the right grain and should stay;
it is the *predicate underneath it* that is measuring the wrong thing.

#### "Recorded from what the player was shown" needs the record to survive a reload

`_encounter_payload` assigned `enc.rung` and called `_write_encounter`, which
only puts the encounter into `self.state`. `start_encounter` calls `save()`
**before** the payload is built. So the served rung lived in memory and nowhere
else. Measured: serve rung 3, reconstruct the `Game` on the same database, and
`enc.rung` comes back 0 — the clear is then filed with no rung at all,
`untracked_production` goes to 1, and `has_produced_code` answers **True** to a
two-blank fill-in. The other half of the same bug: `Game.problem` replays
`enc.rung`, so the resumed player loses the scaffold they were handed and gets a
blank screen instead. `save()` now runs in the same breath as the rung is
decided.

#### Two more ways the arithmetic leaked

**Non-editor clears minted "untracked production".** `production_seen` was
incremented inside `if rung:` while `tier_unaided` was incremented
unconditionally, and `engine` deliberately passes `rung=0` for every non-editor
encounter. So every unaided EASY-or-harder clear of an mcq, a RUNE_ASSEMBLY, a
DEBUG_BATTLE, a BREAK_IT, a REFACTOR_QUEST or a TEST_FORGE grew one side of
`curriculum.untracked_production` and not the other, and the difference — whose
docstring says it counts clears from a save written *before* rungs were recorded
— was read as legacy production. Measured on a fresh save: one correct answer to
`cr-mutable-default`, an EASY CODE_READING multiple choice, flipped
`has_produced_code` False→True, `scaffold_cleared` False→True, and moved the
difficulty target from GUIDED to EASY. `production_seen` now counts every
unaided EASY-or-harder clear, which is what the tally it is differenced against
counts.

**And the placement's writing trial now says so in the same vocabulary.**
`diagnostic.py` recorded the trial as a `tier_unaided` clear only, so it reached
`has_produced_code` through the pre-rung exemption — a fresh save claiming to be
an old one. It sets `production_seen` and `production_unaided` directly, because
the writing trial genuinely is an unaided rung-4 EASY clear.

#### The thresholds are sized to one skill, not to a band

`RUNG_EVIDENCE` was 21 / 24 / 30, solved against the measured length of a band
in a real career — 62 GUIDED editor encounters, 59 TUTORIAL, 75 EASY. The
arithmetic was right for a question nobody was asking: **evidence is filed per
skill.** Those 241 editor encounters spread over eighteen skills at a median of
fifteen apiece, and only HASH_MAP (32) and TWO_POINTER (31) ever reached 24. So
no skill climbed off TUTORIAL's or EASY's floor in an entire career, and the mix
the game served was not measured competence at all — it was declaration coverage
clamped by the floor: TUTORIAL 100.0% scaffolded against its 70%, EASY 66.7%
against its 35%.

Re-solved against what one skill actually accumulates: **8 / 9 / 11**.

**Order matters and is not optional.** A faster climb is only safe once a GUIDED
problem can actually serve rung 3. While 120 of the 184 GUIDED declarations
carried a single span, climbing faster pushed more of them into `servable`'s
fall-up to rung 4 and took GUIDED *down* to 53.2%. The second spans come first;
the numbers come after.

### The SRS schedule

`srs.py` schedules over **families**, not problems, and knows nothing about
rungs. Three rules:

1. **A review is served at rung 4 by default.** A review exists to measure
   retention. A retained skill delivered with the answer half-written measures
   nothing, and `schedule_after` would grow the interval on it.
2. **A lapse drops the review one rung, not to the bottom.** `schedule_after`
   already halves the stage and the ease on a lapse; the rung should move with
   it, by one. This is the only route to a scaffold at MEDIUM (§1b), and it is
   why MEDIUM's 10% is a recovery rung rather than a teaching one.
3. **Time away returns support before the player notices** — `tier_for`'s
   existing 5-day and 14-day steps, which is the same spacing signal
   `SRS_INTERVALS_DAYS` already encodes, expressed as help rather than as a due
   date.

`pick_disguised` needs one addition: a rung-2 serving must not count as that
family's review. It already refuses sealed candidates as a last line of defence;
this is the same shape of guard.

#### "A scaffolded serving is not a review" has to be asked of the entry

The guard shipped as `MIN_REVIEW_RUNG = 3` with `counts_as_review(rung)` asking
only `rung >= 3`, and its own comment justified the 3 solely by rule 2 above —
the lapsed recovery serving. But **rung 3 is also EASY's own floor**, so
`rung >= 3` said yes to every ordinary EASY encounter at the bottom of the ramp.
Measured: a non-lapsed rung-3 serving of `ob-keep-long-words` took the family
from stage 0 to stage 1, ease 1.00 to 1.10, next sighting 3.3 days out; four
such clears reached stage 4, ease 1.40 and **+42.0 days** — six weeks of
interval bought with fill-in-the-blanks. 18 of the 36 EASY servings in a live
120-encounter career were rung 3.

`counts_as_review(rung, *, recovering=False)` now asks the ENTRY, which is the
thing that knows whether this serving is a recovery.

**The consequence is deliberate and is stated rather than discovered:** a family
whose servings never reach rung 4 never acquires a `due_at`, so it never enters
`srs.due()`. That is the correct reading — a review measures retention of
something the player can produce, and until an ordinary serving of that family
has been the whole function there is nothing to measure retention *of*. Measured
over a live 400-encounter career it costs almost nothing: **62 of 71 families
still acquire a due date** (66 before), and what changes is the inflation — 22
families at stage 5 rather than 30. Non-editor encounters pass `rung=0` and are
unaffected; a multiple choice is answered whole or not at all.

---

## 6. What must not change

### The 122 sealed problems

Render-time transformation adds no problems, so `seal_holdout` receives an
identical input and produces an identical output. **Verified**: re-running
`assign_lineage` + `seal_holdout` on the shipped corpus reproduces the same 122
ids exactly.

This is the assertion to write into `tests/`: rebuild, and the sealed id set is
byte-identical to the 122 shipped. It is cheap, it is exact, and it is the
tripwire for anyone who later decides a few new sibling problems would be
simpler.

### The whole-lineage rule

Unchanged, and unchangeable by this work: no problems are created, so no lineage
changes membership. There are 0 partially-sealed lineages today and this plan
cannot produce one.

**A sealed problem is never served at any rung.** A rung is a presentation of a
problem, so the seal — which is a property of the problem — covers every rung of
it. The existing refusals (`srs.pick_disguised`, the selector, `sever_references`)
continue to hold unmodified, because they filter problems and there are still
only problems.

### Independent-reference validation

Strengthened rather than threatened. The scaffold is *derived from* the
canonical solution that a reference implementation already agreed with, so it
inherits that validation instead of needing its own. Two additions:

- **Round-trip**: filling every declared span with its canonical text must
  reproduce the canonical solution exactly. Today, nothing checks this.
- **The mutant check** from §4: a plausible wrong filling must fail the tests.

### The practical

`finalexam.py` restricts exam questions to `CODE_BATTLE`, `REFACTOR_QUEST` and
`DEBUG_BATTLE`, and excludes GUIDED outright:

> A GUIDED problem is a finished function with one expression struck out. That
> is a scaffold, which is help, which is the one thing this exam does not have.

Measured, the practical is clean today: **0 of 580 exam-eligible problems carry
a blank.**

But it is clean by two coincidences. `MISSING_RUNE` is excluded by encounter
kind, and the one `CODE_BATTLE` that carries a blank — `pt-class-latest` — is
excluded by being GUIDED. **Under render-time rungs both coincidences
evaporate**, because any `CODE_BATTLE` becomes servable at rung 2.

So the practical's guard must move from *encounter kind* to *rung*, explicitly:
**the practical serves rung 4 and asserts it.** Same for Interview Mode, same
for the hold-out. The practical is always the whole function with nothing to
lean on, and after this change it says so in the one vocabulary that can still
be true.

`pt-class-latest` should also be fixed on its own account: a `CODE_BATTLE` with
a `__BLANK__` in it is mis-filed, and only survived because nothing validates
blanks.

---

## 7. Risks

1. **Fixing `has_produced_code` demotes existing saves.** A player whose save
   records an unaided EASY clear that was really a fill-in-the-blank currently
   counts as having finished the scaffold band. Correcting the predicate takes
   that away. `curriculum._tier_record_missing` already documents this exact
   trap — a returning player thrown back to the bottom of the ramp, "sixteen of
   their next twenty encounters were fill-in-the-blanks" — and its rule applies
   unchanged: **absent evidence is not evidence of absence.** Saves with no rung
   record must fall through to the old behaviour, not be re-judged under the new
   one.

2. **230 declarations is a real content pass**, and 135 of it is one band. The
   staged answer is TUTORIAL first; it is 59% of the work and 100% of the cliff.

3. **Auto-derivation is 50% accurate and will be trusted anyway.** The number is
   in §4 so that the next pass has to argue with a measurement rather than with
   an opinion.

4. **`starter_code` becomes derived data**, and 214 hand-written copies must be
   converted. The alignment is exact (214/214), so the conversion is safe — but
   it must fail loudly on any problem that does not round-trip, because
   `pt-class-latest` proves at least one is already mis-filed.

5. **The mcq conflation will come back.** "Scaffolded share" counted on
   `entry.kind == 'mcq'` says EASY is 21.8% and rising; counted on the
   write-code axis it says 7.7%. Any future audit must state which axis it is on
   or it will re-diagnose the wrong band.

6. **Rung 1 is new client work.** It costs no authoring beyond rung 2's
   declaration, but nothing in the corpus renders "pick the token that completes
   this line" today, and it is the rung the player named first.

7. **The scaffold is in `player_view`.** Whatever carries the rung must go
   through the same redaction discipline as `mcq`: the client needs the blanked
   text and must not receive the canonical spans that fill it. `redact_mcq` is
   the model, and `player_view` already pops `sealed` and `lineage_id` for the
   same class of reason.

---

## 8. Self-check

**Measured, reproducible, and re-derived from the shipped corpus:**

- both ramp tables, including the brief's — reproduced exactly, 1,013 problems
- the write-code-axis table (858 problems), and the mcq breakdown by encounter
  kind that justifies separating the axes
- 214/214 starter/canonical line alignment, with every un-blanked line identical
- the AST rule's agreement with human blank choices: 50% top-1, 64% top-k
- `has_produced_code` returning `True` after one unaided EASY clear — executed,
  not reasoned
- `seal_holdout` reproducing the identical 122 ids on the shipped set
- the 229-sibling experiment: 122 stay sealed, 19 newly sealed, 0 unsealed,
  0/229 lineage failures
- 0 of 580 exam-eligible problems carry a blank
- per-band family counts behind the coverage table

**An assumption I held that the measurement corrected.** I inferred from
`sc-group-anagrams` and `ah-group-anagrams` landing in different lineages that
scaffolded siblings do not reliably join their parent's lineage. Tested
directly, siblings built from a verbatim canonical solution joined **0/229
failures**. The split is an authoring deviation, not a mechanism failure, and
§3 says so. The case against new problems rests on the measured 19 collateral
seals and on the convention having already been broken in shipped content — not
on the lineage mechanism being unreliable, which it is not.

**Read but not executed:** `web/js/editor.js` and `incantui.js` rendering,
`finalexam` exam composition, the adaptive selector's scoring path.

**Not verified, and load-bearing:**

- The §1b mix percentages are a **design decision, not a measurement.** They are
  argued, monotone, and consistent with the floors in §1a; they are not derived
  from player data, because none exists yet. The first cohort through TUTORIAL
  is what should revise them. §1c records what the live selector serves against
  them, and where it does not agree it says why rather than tuning.

**As instructed, no problems were authored and no owned file was touched.**

---

## 9. The audit pass, and what it changed

Everything above §9 is the plan as written. This section records what a build
and a live career had to say about it, because several claims in the plan turned
out to be true only by accident.

**Run, not reasoned:** `python3 run.py build-corpus` (1,013 problems, 0 errors);
`tests/test_the_ramp_rungs.py`, `test_ramp.py`, `test_coverage.py`,
`test_corpus.py`, `test_acceptance.py`, `test_engine.py`, `test_wiring.py`,
`test_keys_and_seal.py`, `test_seal_enumeration.py`, `test_interview_isolation.py`,
`test_transfer.py`, `test_first_steps.py`; and a deterministic 400-encounter
career driven through `Game.next_encounter` with the rung read off the payload
the client is actually sent.

**Corrected, each with its measurement:**

| what | where | §
|---|---|---|
| 120 GUIDED / 75 TUTORIAL declarations carried one span, so rung 3 fell up to rung 4 | `corpus/scaffolding.py` | §2 |
| `RUNG_EVIDENCE` sized to band length, not to per-skill evidence | `curriculum.py` | §5 |
| `lapse_floor` served rung 3 at HARD, ELITE and BOSS | `curriculum.py` | §1b |
| rung 1 rendered with an empty choices list for 55 problems | `scaffold.py`, `validate.py` | §4 |
| a span could strike inside a longer name, invisibly to `round_trip` | `scaffold.py` | §4 |
| the span judgement checked only `spans[0]` | `validate.py` | §4 |
| the rung-parses check exempted rung 4 for problems whose rung 4 it generates | `validate.py` | §4 |
| a canonical comment above a blank survived into the render | `scaffold.py` | §4 |
| derived glosses were numbered twice | `scaffold.py` | §4 |
| the served rung was never saved | `engine.py` | §5 |
| non-editor clears minted "untracked production" | `skills.py`, `diagnostic.py` | §5 |
| an ordinary rung-3 EASY serving counted as a spaced-repetition review | `srs.py` | §5 |
| the taper was measured by a protocol that does not occur in play | `tests/` | §1c |

**The one thing the audit disputed rather than fixed.** The brief asked for the
live 400-encounter band aggregate to be non-increasing. It is not, and it should
not be asserted: 61.3 / 71.2 / 49.3 confounds band with skill and with career
phase, and every point of the GUIDED–TUTORIAL gap is composition. §1c gives the
measurement and the stronger claim that replaces it — zero inversions across
241 live encounters, asserted per encounter.
