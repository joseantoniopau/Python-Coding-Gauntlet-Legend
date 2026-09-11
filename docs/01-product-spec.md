# Product Specification

## What this is

A 16-bit RPG whose combat system is a Python coding-interview trainer, built for
one named player: a senior security engineer with strong systems judgement,
strong incident response and detection engineering, who reads code well and
reasons about it well — but who cannot yet produce Python quickly from a blank
screen, and has limited exposure to algorithmic interview patterns.

The product exists to convert:

> "I understand what needs to happen but cannot always produce the Python quickly."

into:

> "I recognise the pattern, select the data structure, explain the algorithm,
> implement it cleanly, debug it, test it, explain its complexity, and do all of
> that under interview time pressure."

The promise: **if you beat the full game under mastery conditions, you should be
genuinely ready for a demanding Python coding interview.**

## The two priorities, held equally

**Make me want to play.** Not LeetCode with pixel graphics. Not a corporate
dashboard with swords. Not flashcards in a wizard hat. A real game, where a
planned twenty-minute session becomes ninety because you want to continue.

**Engagement must serve learning.** No loot boxes, no streak anxiety, no
artificial scarcity, no monetisation, no reward that bypasses learning. The
addictive quality comes from the honest loop:

```
CHALLENGE → LEARNING → IMPROVEMENT → MASTERY → REWARD → NEW CHALLENGE
```

## Design rules that are never violated

1. **Adventure Mode teaches. Interview Mode measures.** They are never confused,
   and the separation is enforced server-side.
2. **Learning never dead-ends.** Every problem's hint tree bottoms out in a
   complete worked solution. A Learning Clear still advances the story.
3. **Mastery is never granted for exposure.** Only graded attempts move a skill.
4. **No item, spell or upgrade supplies an answer.** Gear changes what a fight
   costs and what it pays. It never writes Python.
5. **Failure is navigation, not punishment.** Every failure produces a root
   cause, a training camp targeting the *prerequisite*, and three remediation
   steps.
6. **Provenance is honest.** Reported patterns are labelled as historical
   patterns with an explicit disclaimer. Generated content never names a company.

## The world

The ancient **Source** governed the realm until it was shattered by the **Null
King**; its fragments became the fundamental patterns of computation. The player
is **the Security Architect** — already strong defensively, unable to restore the
Source without mastering the old language, Python.

Sixteen regions plus the final castle, each physically embodying its algorithm.
The Marsh is crossed by a glowing frame that widens right and shrinks left. The
Pass has two lanterns converging from opposite ends. The Ruins light up tiles you
have already solved. The Canopy branches and never rejoins. Villages visibly
rebuild as your fluency returns, in four tiers.

Fourteen bosses, each with six phases — recognise, explain, implement, survive
the hidden trials, name the cost, then a disguised rematch. Failing a boss never
ends anything: it enters its **teaching phase**, a mentor arrives, and the
complexity ladder steps down until the concept holds.

## The combat model

Enemy HP is test coverage; each passing trial deals damage.

**Weaknesses are the problem's real edge cases**, derived from its hidden tests:
empty input, lone element, duplicates, negatives, zero, exact boundary, scale,
all-identical, adverse order. **Resistances** are the ceilings it enforces — an
enemy carrying a performance trial literally resists brute force.

**The Probe** is the strategy layer. Spend a charge to assert that on a chosen
input, the correct answer is a specific value:

- **Right** → you understood the spec. The weakness is exposed, and when your
  solution passes that hidden trial it strikes critically — up to double XP and
  a better loot roll.
- **Wrong** → you have caught a broken mental model *before* spending twenty
  minutes implementing it, and the Testsmith skill is credited either way.

This is the same skill an interviewer watches for: predicting how code breaks.

## Progression

- **Levels** award three attribute points each across LOGIC, FOCUS, VIGOR,
  INSIGHT and HASTE.
- **Three builds** — Analyst, Duelist, Archivist — each with a favoured equipment
  set, respeccable at the Armorer for gold.
- **Nine equipment slots**, 44 items, six rarities, four set bonuses.
- **Five hidden items** with genuine discovery conditions, including one awarded
  only for failing a problem on performance alone and then clearing it — the
  "I turned my quadratic into a line" achievement, as an object.
- **Weapons evolve through demonstrated mastery**, not purchase: Hashblade I at
  three easy hash clears, Legendary at a Hash Titan kill, unaided, under time.
- **Armour is repaired only by debugging.** The cracked piece matches the root
  cause of the failure that cracked it.
- **Titles** from Python Apprentice to Legend of the Source.

## Sessions

| Length | Shape |
|---|---|
| 10–15 min | Quick session: drills, a shrine, one encounter |
| 30 min | Standard quest: a region, a retest, an armour repair |
| 60 min | Training session: a weakness focus plus a boss attempt |
| 90+ min | Adventure session: region clearing, elites, loot |
| 45–70 min | Interview simulation: Live Screen or the Gauntlet |

## Interview profiles

`QUORA` (the immediate objective), `GENERAL_SWE`, `SECURITY_ENGINEERING`,
`CUSTOM`. Profiles change question weighting, difficulty, timing and the problem
mix. The Quora profile weights arrays, strings, hash maps, sets, sorting, sliding
window, two pointers, matrices, trees, recursion, BFS/DFS, design, debugging,
Big-O and testing — the publicly reported emphasis, presented as historical
pattern rather than prophecy.

Two formats: **Live Screen** (50 minutes, 2 problems) and **The Gauntlet** (65
minutes, 4 problems rising in difficulty, family never named).

## Success metrics

Time to pattern recognition · Python generation speed · test pass rate ·
debugging speed · Medium completion · Big-O accuracy · edge-case identification ·
retention across intervals · interview simulation score. Plus voluntary session
duration, return frequency, boss replay rate, and reduction in hint dependence.

Engagement is never optimised at the expense of learning.
