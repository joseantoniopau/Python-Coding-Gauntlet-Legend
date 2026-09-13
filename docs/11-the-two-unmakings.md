# The two Unmakings

There are two renderers for the Null King's spell. That is deliberate. This
document exists so the next consolidation pass does not delete one of them.

---

## The trap

A pass that greps for duplication finds this and reads it as an obvious mistake:

    web/js/unmakingfx.js     1,294 lines   createUnmaking()
    web/js/spellfx.js        §THE UNMAKING createUnmaking()  ← same name

Same spell, same fourteen dispossessions, same source of truth in
`gauntlet/unmaking.py`, two implementations, one name. Delete one, keep the
better one, move on.

**Do not.** They render the same event at two different scales, in two different
venues, and the game needs both. The name collision is resolved by the
`createUnmakingCinematic` alias that `spellfx.js` exports for exactly this
reason — it is not evidence that one is a stray copy.

---

## The rule

> **`unmakingfx.js` is the world map. `spellfx.js` is the chamber.**

| | `unmakingfx.js` | `spellfx.js` §THE UNMAKING |
|---|---|---|
| Venue | the overworld, where you were standing | the last chamber, once |
| Length | 15.60s | 116.75s unattended, 22.75s floor |
| Words | none | 258, across five acts |
| Paints | the hero's own rig — plates, contour, screen wash | the full frame, its own figure, a title card |
| Blocks input | no, never (`unmakingDebug().blocking` is false) | yes; it is a cutscene |
| Dismissable | nothing to dismiss | after the first dispossession (18.13s) |
| Wired via | `overworld.castUnmaking()`, off a state row | the practical-exam handoff |

The reasoning is already in `unmakingfx.js`'s own source and is worth quoting,
because it is the whole argument in one line:

> *"This module also has to work on the WORLD MAP, where he turns up where you
> already were, does this, and is gone — and where a hundred and fifteen seconds
> is not weather, it is a hostage situation."*

He casts it at you in the field more than once. He casts it *in full*, with his
reasons, exactly once.

---

## They do not contradict each other

Both derive from `gauntlet/unmaking.py`. Both reconcile against
`finalexam.ALL_CRUTCHES` in both directions, with empty diffs, and both are
checked by harnesses (`scripts/verify/unmaking.mjs`, `unmakingfx.mjs`,
`unmakingworld.mjs` — all PASS).

The one apparent disagreement is not one. `unmaking.py` authors **ITEMS** as a
belt going flat and its contents laid out on a table — no sword. `unmakingfx.js`
maps `ITEMS → ['weapon']` and dims the weapon's runework. These agree: a taken
weapon plate is `neutralOf(rgb, -2, WINDOW.weapon)`, which **desaturates the
blade in place rather than removing it**. The sword stays in the hero's hand and
goes grey. The charms and whetstones that were buffing it are what left.

The legendary weapon is never taken by the spell, in either renderer, and should
not be. The player forged it. It is not a crutch.

### Why only four of fourteen show on the sprite

`SPRITE_FOR_CRUTCH` maps four crutches to rig plates — PET, BUILD, ITEMS,
OBLIGING_HAND. The other ten produce a beat that takes nothing visible: green in
the air, the hero unchanged, a held shot of a person while something is removed
from somewhere else.

That is not an incomplete mapping to be finished later. Ten of the fourteen
being invisible **on him** is the point of the scene: most of what he takes was
never on the player's body to begin with.

---

## If you are wiring this

- `beatsFromCinematic(payload)` in the chamber; the standalone `BEATS` table
  everywhere else. Both live in `unmakingfx.js`.
- `spellfx.js` draws the title card and nothing else of the text layer — it
  deliberately does not own the subtitle UI. Render `u.speaking()` yourself.
- Neither module may reach `finalexam.sealed()`. **The spell explains the seal;
  it does not change it.** `gauntlet/unmaking.py` imports nothing from the game
  that could, holds no state, and is proven byte-identical-exam three ways.
- Never play both for one cast.
