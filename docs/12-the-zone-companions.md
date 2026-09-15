# The Zone Companions

The design for enterable buildings, living villages, and the five people who
walk a zone with you until the thing that owns it takes them.

This document DECIDES. It is written so that six agents building from it
produce one game. Where a number is stated, it is the number. Where a choice
was close, the losing option is named and the reason it lost is given, so a
later pass re-opens the argument on purpose rather than by accident.

**Nothing in this document is implemented.** `web/js/overworld.js` and
`web/js/tiles.js` are owned by a concurrent pass. §8 is the work list for them.

---

## 0. What already exists, and what this must not duplicate

Scouted, not assumed. Every number below was read out of the file named.

| Fact | Source | Consequence for this design |
|---|---|---|
| 17 regions, 14 named bosses, 16 dungeons (one per region except Python Village) | `world.REGIONS`, `world.BOSSES`, `dungeons.DUNGEONS` | Six regions have **no** named boss: `python_village`, `fields_of_syntax`, `stringwood_labyrinth`, `stack_queue_mines`, `dp_ruins`, `coding_coliseum` |
| `finalexam.BOSS_LADDER` rung N **is** the Nth entry of `world.BOSSES` | `world.py` §"The last trial" | **Adding a boss renumbers every crutch in the game.** No new bosses. Ever. |
| 14 keys, one per boss; the Standing Portal wants all 14 | `world.KEYS`, `progression.PORTAL_NEED` | Same conclusion, second lock |
| 25 captives across 14 holdings; `free(state, boss_id)` is the **only** rescue path and it pays through `quests.reward_for` | `captives.py` | The companion arc hangs off `captives.free`. No second reward path. |
| `Captive.home` ≠ `Captive.held_in` is already supported (Thessaly Brun: home `python_village`, held in `null_kings_castle`) | `captives.Captive.held_in` | A companion may be taken by a boss from a neighbouring region |
| `Captive.gift` already means "the item they hand you when freed" | `captives.py` | The rescue gift is **already built**. Only the capture drop is new. |
| `overworld.this.companion` is the **pet** (`pets.py`), and `hunters.COMPANION_CREDIT` scores it | `overworld.js` §companion | **`companion` is a taken word in code.** The human follower is `escort` everywhere in source. This document's title is the player's word; the code's word is `escort`. |
| "ambush" already means an SRS retest (`items.EFFECT_LABELS: retest_charges`, `classes.py`) | 20+ sites | **The rainforest thing is a PACK, never an ambush.** |
| `incantation.make_context([a,b,c,d])` already fields several enemies at once | `incantation.py:394` | The pack reuses this. No second combat system. |
| Buildings are 2×2-tile markers, sprite 40×36, four per settlement, only in five biomes | `overworld.js:478-513`, `tiles.buildingSprite` | Interiors are new; the marker is not |
| Tile 16px; hero 16×24; walk speed **112 px/s** → **0.1428 s per tile**; map 48×34 | `tiles.TILE=16`, `sprites.HERO_W/H`, `overworld.js:870`, `MAP_W/MAP_H` | Every timing in §4 is derived from these |
| `TERRAIN` has codes 0–11. `LAVA` is 9. There is no ICE. | `tiles.TERRAIN` | ICE = 12, SLUICE = 13, DOOR = 14 are the new codes |
| The vendor sells **potions only**; blades come from `forge.py` at `GOLD_SHAPE` prices (rung 2 = 40g … rung 9 = 1500g) | `economy.stock_list`, `forge.GOLD_SHAPE` | §6 adds a rack for armour and must not build a second weapon curve |
| `banter.SPEAKERS` is 47 voices, 34 of them villagers, 2 per region (3 in Python Village), with a `CHILD` register already in it | `banter.py` | Village life costs **zero new writing** |
| The hero rig already draws villagers (`weapon: null`) and has two body types | `sprites.js:2569`, `HERO_BODY_TYPES` | Male and female villagers cost **zero new art** |

---

## 1. The companions

### 1.1 Five, not seventeen. The reason.

Seventeen regions with seventeen mechanics is seventeen tutorials. This game
already asks a player to hold six puzzle kinds, six elements, three opposed
pairs, a nine-rung forge, four potion strengths, armour integrity, a pet, and
weather — before it asks them a question about Python. A mechanic per region
would be the largest thing in the game and it would be the thing the game is
least about.

**Five zones carry a companion.** The player named five and the five they named
are the five that earn it: each one is a *verb the player performs*, not a stat.
Slide. See. Cross. Thin the pack. Read the road.

Every other region keeps exactly what it has: a captive who goes home, a boon
that changes the village, and a gift. That is already a reward, it is already
built, and it already works.

### 1.2 A ZONE is a cluster, not a region

Seventeen regions, five zones. A zone is named here and nowhere else:

| Zone | Regions | Element | Companion |
|---|---|---|---|
| **HOME** | `python_village`, `fields_of_syntax` | NEUTRAL | Thessaly Brun |
| **THE DARK** | `array_caverns` | BRUTE | Josa Fell |
| **THE SNOW** | `twin_pointer_pass` | COLD | Hessa Dunmar |
| **THE GREEN** | `stringwood_labyrinth`, `recursive_forest`, `binary_tree_canopy` | POISON / VOID / NEUTRAL | Halla Vane |
| **THE FIRE** | `stack_queue_mines` | FIRE | Greave |

Regions in no zone: `hashmap_highlands`, `sliding_window_marsh`,
`matrix_citadel`, `graph_wastes`, `dp_ruins`, `debugging_dungeon`,
`complexity_tower`, `coding_coliseum`, `null_kings_castle`. They get no escort
and no zone mechanic, by the argument in §1.1.

### 1.3 The roster

Three of the five are existing `captives.py` captives, unchanged. Two are
existing **`banter.py` villagers promoted into `captives.CAPTIVES`** — one new
row each, no new cast, no new boss, no new key.

---

#### HOME — **Thessaly Brun**, village schoolteacher

*Existing captive. `home=python_village`, `boss=the_interviewer`, `sprite=scholar`, `boon=the_square_drill`.*

- **Mechanic while free:** the tour guide. She walks Python Village and the
  Fields of Syntax. Standing on a building's door tile with her escorting
  prints, once per building, what that building is and what its sign means
  (§5.4). Standing at a route head prints where that road goes and what it
  costs (`progression.Route.need`, rendered as the existing `need_status` text).
  She never says anything about a *problem*; she says things about *places*.
- **Item:** **THE SLATE** (`the_slate`, trinket). She hands it over the first
  time you walk `rt_waking_road` — **not** on capture. See §1.5.
- **Capture:** she is the **exception**, and she is the arc's proof. Python
  Village has no boss and no dungeon; there is nothing there to take her. She is
  taken at the finale, by the Examiner, alongside Yoren Halt and Ivo Brannt
  — which is already exactly what `captives.py` says happens. The player's own
  line, "the last boss captures all of these known villagers", lands hardest on
  the one you have known since minute one.
- **What is lost when she goes:** the building and route captions stop. The
  Slate keeps working. You have already read the signs.
- **Rescue gift:** none authored (`gift=""`). Her boon `the_square_drill`
  (`srs_preview`) is the reward and it is already built.

---

#### THE DARK — **Josa Fell**, lamp-runner of the Array Caverns

*Existing captive. `home=array_caverns`, `boss=three_sum_hydra` (ladder rung 2), `sprite=runner`, `boon=lamps_both_ends`.*

- Twenty-four. Runs a lamp line twice a shift. Her twin ran the other half of
  the same line. Her boon is already *"The Caverns are lit from both ends, so
  nothing waits in the dark for a runner."* This companion was already written;
  it only needed a mechanic attached.
- **Mechanic while free:** she carries the lamp. Sight radius **6 tiles**, and
  the lit disc is **offset 2 tiles in your facing direction** — she walks ahead
  on the path, so you see round a corner before you turn it. (§4.2)
- **Item on capture:** **THE LAMP** (`the_lamp`, trinket). Sight radius
  **5 tiles**, centred on you, **no offset**.
- **How the item is weaker:** one tile of radius, and the offset. The offset is
  the real loss: with the lamp you must walk into a junction to see it. With
  Josa you saw it from a tile back. Every blind corner in the Sunken Index was
  designed against her offset and is now a corner you take on faith.
- **Rescue gift:** none authored. Her boon lights the whole region permanently,
  which is the thank-you.

---

#### THE SNOW — **Hessa Dunmar**, span-rigger of the Pass

*Existing captive. `home=twin_pointer_pass`, `boss=twin_behemoth` (rung 4), `sprite=climber`, `gift=ward_cold`, `boon=the_rigged_span`.*

- Forty, harness still buckled over a frost-white pass coat, *"the flat mountain
  squint of somebody who has spent her life judging distances in bad light."*
  She rigs spans from both ends and meets in the middle. She has opinions about
  where the error collects.
- **Torv Bael** is taken in the same scene and is already her co-captive on the
  same boss. He does **not** walk with you — he is at the far end of the pass
  rigging the other half, which is why `the_rigged_span` is a boon they share
  and why they are taken together. One escort sprite, two people freed.
- **Mechanic while free:** she rigs a hand line across ice. Stepping onto ICE
  **does not commit you** — you keep tile-by-tile control. She also **calls the
  exit**: on approaching a patch she names, in one line, which edge of it is
  walkable. (§4.1)
- **Item on capture:** **SKATE IRONS** (`skate_irons`, feet). Control on ice is
  restored *and* movement on ICE is **1.35× speed** (151 px/s, 0.106 s/tile).
- **How the item is different:** the skates give control and speed. They never
  call the exit. After Hessa, you read the patch yourself — which is the whole
  point of putting ice on the critical path.
- **Rescue gift:** `ward_cold` — Rimeward Hauberk, RARE, chest, `resist_cold
  0.15`. Already authored. The next zone in the ladder after the Behemoth is the
  Citadel; the hauberk is for the pass you are about to leave and the tower you
  will climb, and she says so.

---

#### THE GREEN — **Halla Vane**, forester

*NEW captive row. `home=recursive_forest`, `boss=tree_dragon` (rung 6, so `held_in=binary_tree_canopy`), `sprite=forester`, `register=RANGER`.*

- She is **not a new character.** `banter.SPEAKERS` already carries
  `halla → {name: "Halla Vane", role: "forester", region: "recursive_forest",
  register: "RANGER", sprite: "forester"}`. And `captives.CAPTIVES` already
  mentions her by name in someone else's bearing: Corr Vane wears *"the Vane
  family's canvas with the shoulder patch Halla sews on all of them."* She is
  kin to a captive who is already in the file. Promoting her costs one row.
- **She is the player's "female jaguar warrior."** She is a forester who works
  both sides of the Branch Ladder, she moves through the canopy, and she carries
  an axe because her family does. Do not redraw her as a cat. The sprite is
  `forester`; the *jaguar* is how she moves and how the packs react to her.
- **Mechanic while free:** the **PACK**. In the three Green regions, an
  `encounter` marker has a **22%** chance of fielding 3–5 enemies instead of one.
  With Halla escorting, she drops all but one before the first turn. (§4.4)
- **Item on capture:** **THE POISON DART** (`the_dart`, trinket, **2 charges**).
  Spending a charge at the top of a pack drops all but one — identically to
  Halla. Charges refill **+1 per dungeon boss cleared**, cap 2.
- **How the item is weaker:** Halla did it every time, for free, forever. The
  dart does it twice. A pack with no charges left is a full pack, and a full
  pack is a legal, winnable, already-balanced multi-enemy incantation battle. It
  is harder. It is not a wall.
- **The dart's toxin comes from the Stringwood.** `elements.BIOME_AFFINITY`
  makes `forest` (Stringwood Labyrinth) POISON and calls it *"the rainforest of
  the brief"* in its own comment. That reading is preserved: Stringwood is the
  humid, spore-shedding half of the Green, it is where the toxin is gathered,
  and Moss Arden the forager is already standing in it. The **capture** happens
  one route deeper because Stringwood has no boss.
- **Rescue gift:** `wayfarers` (Wayfarer's Boots, RARE) is currently Oskar
  Lind's. Give Halla **`lanternshoes`** (Lantern Shoes, UNCOMMON, feet,
  `mana_max 3`) and move nothing: it is currently Wilmot Tace's, in the
  Recursive Forest, which is her home region, and two people in one family
  handing over the same kind of boot is a village, not a bug. *Open choice:*
  if a later pass wants her gift unique, mint one. Not worth a new item today.

---

#### THE FIRE — **Greave**, lift engineer of the Mines

*NEW captive row. `home=stack_queue_mines`, `boss=graph_necromancer` (rung 8, so `held_in=graph_wastes`), `sprite=engineer`, `register=LABOURER`.*

- Also not a new character: `banter.SPEAKERS` already has
  `greave → {name: "Greave", role: "lift engineer", region: "stack_queue_mines"}`.
- **Why the Graph Necromancer and not a Mines boss.** The Mines have no boss
  row and cannot be given one (§0, two independent locks). The choice was
  between three bosses:

  | Candidate | Ladder rung | Verdict |
  |---|---|---|
  | `bug_demon` (Debugging Dungeon, same `faultsteel`, same FIRE) | **13** | **Rejected.** Rung 13 is the second-to-last boss. Greave would be freed and re-taken (§2.5) within minutes. |
  | A generated `dungeons.assemble_boss()` boss of The Ninth Cart | — | **Rejected.** Per-run, re-seeded, unnamed. `captives.free` keys off `world.BOSS_BY_ID`; wiring a rescue to a boss that is different every descent needs a second rescue path, which `captives.py` refuses in its own docstring. |
  | `graph_necromancer` (Graph Wastes) | **8** | **Chosen.** |

  `world.REGIONS` makes `graph_wastes` unlock **from** `stack_queue_mines`: the
  Wastes are strictly downstream of the Mines, so rung 8 lands after a player has
  worked the Mines and before the late ladder. And the fiction is exact: the
  Wastes are *"a broken land where every ruin connects to several others"* — a
  lattice — and the Mines are cart lines. The Necromancer came up the ore line
  and took the man who runs the lift.

- **Mechanic while free:** he works the sluices. A lava channel that crosses a
  route has a sluice beside it; Greave cranks it. Drain **1.5 s**, the channel
  holds open **20 s**, then refills. (§4.3)
- **Item on capture:** **THE MECHANICAL GEAR** (`the_gear`, trinket). You crank
  the sluice yourself. Drain **4.0 s**, holds open **8.0 s**.
- **How the item is weaker:** 2.5 s slower to open and 12 s less margin. With
  Greave you crossed when you felt like it. With the gear you stand at the lip,
  crank, and go. A six-tile channel takes 0.86 s to cross; the gear gives you
  eight seconds to find that crossing, and Greave gave you twenty.
- **Rescue gift:** `earthed_sabatons` is Jessamy Roke's, in the same holding.
  Give Greave **`cinder_greaves`** (Cinder Greaves, UNCOMMON, feet,
  `stamina_max 3`) — currently Hedda Ferrin's, and thematically a Mines item
  sitting in the wrong region. *Recommended:* move `cinder_greaves` to Greave
  and give Hedda Ferrin a minted `forge_apron`. Hedda is the plate-smith; greaves
  were never her signature.

### 1.4 Summary table

| Zone | Escort | Existing? | Boss | Rung | Capture dungeon | Capture drop | Rescue gift |
|---|---|---|---|---|---|---|---|
| HOME | Thessaly Brun | captive | `the_interviewer` | 14 | — (finale only) | THE SLATE *(given early)* | — (boon) |
| THE DARK | Josa Fell | captive | `three_sum_hydra` | 2 | `sunken_index` | `the_lamp` | — (boon) |
| THE SNOW | Hessa Dunmar | captive | `twin_behemoth` | 4 | `converging_span` | `skate_irons` | `ward_cold` |
| THE GREEN | Halla Vane | **new row** (banter NPC) | `tree_dragon` | 6 | `anagram_deeps` | `the_dart` | `lanternshoes` |
| THE FIRE | Greave | **new row** (banter NPC) | `graph_necromancer` | 8 | `ninth_cart` | `the_gear` | `cinder_greaves` |

Ladder order 2 → 4 → 6 → 8 → 14. Evenly spaced by construction, and none of it
was arranged: it fell out of which boss each zone's people were already assigned
to.

### 1.5 The Slate, and why it is given rather than dropped

The map is the one zone item the player must have **before** anything is taken,
because it is the thing that tells them where the zones are. Thessaly hands it
over the first time you walk the Waking Road. It is a schoolteacher's slate and
it is blank.

It has two stages, and the second one is already in the game:

- **Stage 1 — Thessaly's slate.** Regions you have entered, drawn as nodes.
  Routes you have walked, drawn as edges. Everything else fogged. Data:
  `world.REGIONS` + `progression.ROUTES` + the save's own visited set. No new
  server call; `worldui.js` already renders this graph.
- **Stage 2 — the marked line.** `captives.BOONS["the_marked_line"]` already
  exists, belongs to **Jessamy Roke**, road-scout and sign-cutter of the Graph
  Wastes, and already reads *"Cut marks from the waystation to the Ruins,
  shorter way on the left stone."* Freeing her upgrades the Slate: open quest
  markers (`quests.py`), and a **where-next pointer** computed as
  `progression.routes_from(here)`, filtered to routes whose `Need` is currently
  met, sorted by `danger` ascending, top three.

**The Slate never gates anything.** Everything on it is also on the existing
world screen. It is a convenience that happens to be a character.

---

## 2. The arc

One shape, stated once, five instances.

### 2.1 The beats and where each one hooks

| # | Beat | Hook, precisely |
|---|---|---|
| 1 | **They join you.** | On first entering any region in the zone with `captives.is_freed(state, id) == False` and the zone not yet captured. Server sets `state["escort"] = {"id": ..., "zone": ..., "taken": false}`. Client: `overworld.setEscort(row)`. |
| 2 | **They do their thing.** | §4. Every mechanic reads `state.escort.id` and nothing else. |
| 3 | **They are taken.** | Fires on the **transition of `dungeons.progress(d, run)["seal"]["met"]` to true** in the zone's capture dungeon (§1.4), **resolved on the player's return to the overworld** so the scene has ground to play on. One-shot, latched on `state["escort_taken"][zone]`. |
| 4 | **The item drops.** | In the same transaction as beat 3, the drop id is appended to `state["inventory"]` — the same one-line path `engine.py` already uses everywhere it hands over gear (`if item_id not in self.state["inventory"]: append`). There is no `items.grant()`; do not invent one. **The grant is unconditional** — not a roll, not in a chest, impossible to miss. A zone mechanic a player can lose access to is a dead end. |
| 5 | **You free them.** | `captives.free(state, boss_id)` — the existing call, unchanged. It already opens every cage that boss holds, pays through `quests.reward_for`, banks the boon and the route, and returns `{pay, story, world}`. |
| 6 | **Thank you, keep it, here is the next thing.** | The keep-it line is authored into `Captive.lines`. The next-zone reward is `Captive.gift`, which `captives._extras_for` already hands over inside `free()`. **Nothing new is needed for beat 6.** |
| 7 | **The Examiner takes them all.** | On clearing ladder **rung 13** (`bug_demon`) — the second-to-last boss. §2.5. |
| 8 | **Everyone out.** | `captives.final_release(state)`, the existing single call the finale makes. |

### 2.2 Beat 3, in detail: the scene

Eight seconds. Not a cutscene; the player keeps the keys.

1. The escort stops walking and turns to face the boss's bearing (east, toward
   the boss marker at `MAP_W-7`).
2. Three lines, in the escort's own voice, in the existing overworld dialogue
   box. They are about *their own life*, per `captives.py` rule 1 — not about
   your quest.
3. The boss's colour (`world.BOSS_BY_ID[boss]["colour"]`) washes the frame at
   0.35 alpha for 1.2 s.
4. The escort sprite is gone. The item is **already in the inventory** by this
   point (beat 4 ran in the same transaction). What is on the ground where
   they stood is a **two-second decorative glint, not a pickup** — there is
   nothing to collect and nothing to walk back for. A dropped item the
   player has to remember to pick up is the same dead end as a locked door,
   arrived at from the other side.
5. One line of narrator. `captives.HOLDINGS[boss].chamber` already holds the
   text for what the room looks like; the **capture** needs one new authored
   line per companion, five lines total, in `captives.py`.

**It never blocks input and it is never longer than eight seconds.** The house
precedent is `unmakingfx.js`, which makes exactly this argument in its own
source: on the world map, a hundred and fifteen seconds is not weather, it is a
hostage situation.

### 2.3 Beat 5, in detail: what `free()` already does

`captives.free(state, "twin_behemoth")` today returns the `{pay, story, world}`
split, frees Hessa **and** Torv, banks `the_rigged_span`, and opens
`cap_rigged_span` (the road to the Coliseum). The only addition this design
makes to that call is one line:

```
state["escort"] = None   # they are home; they do not walk with you again
```

They do not re-join. The village they go home to is changed
(`Captive.change`), they are standing in it, and the walking is over. That is
the shape `captives.py` already committed to and it is the right one.

### 2.4 The gap, and why it is the right length

Between beat 3 and beat 5 is one dungeon: the zone's capture dungeon's seal is
met, you come up, they are taken, and the boss is at the bottom of the region's
own delve. The item is what makes that stretch survivable, and it is
deliberately *worse* than the person. **That is the design.** The item is not a
replacement; it is a coping strategy, and the length of the gap is how long the
player has to feel the difference.

### 2.5 Beat 7: the Examiner takes all of them

The player's words: *"the last boss captures all of these known villagers after
the second-to-last boss is defeated."* The second-to-last boss is
`finalexam.BOSS_LADDER` rung 13, `bug_demon`.

New call, `captives.retake(state) -> dict`:

- Moves every id in `state["captives"]["freed"]` that belongs to one of the five
  zone companions **plus** everyone the Examiner already holds into a new
  list `state["captives"]["retaken"]`.
- **Suspends their boons** — `captives.boon_effects(state)` skips a retaken
  person's boon. This is a real, felt, reversible loss.
- **Does NOT touch items.** You keep the skates, the lamp, the dart, the gear
  and the Slate. Taking a mechanic away at rung 13 would put the last two
  bosses behind a wall built out of a cutscene.
- `roll_call(state)` renders retaken people struck through with the date they
  were taken back. The player watched that list grow for the whole game; the
  finale's weight is entirely in watching it shorten.
- `final_release(state)` clears `retaken`, restores the boons, and returns
  everyone. It already exists and already returns the honest remainder.

---

## 3. What is *not* a companion, and stays exactly as it is

Nine regions. They keep their captives, boons, gifts and village changes. Two
of them are worth naming because they look like companions and are not:

- **Jessamy Roke** (Graph Wastes, road-scout) upgrades the Slate (§1.5). She
  does not walk with you. Her boon already opens a road.
- **Perrin Oake** (Marsh, reed-cutter) already rethatches every crossing hut in
  the marsh. That is a zone change without a zone mechanic, and it is enough.

---

## 4. The mechanics

Each is specified to the number. All four read `state.escort` and the item
inventory, and nothing else.

### 4.1 Ice

**Where.** `TERRAIN.ICE = 12`, `isSolid(ICE) === false`. Generated **only** in
`twin_pointer_pass`. (Complexity Tower is also COLD in
`elements.BIOME_AFFINITY`, and gets **frost as decoration only** — no slide. One
zone, one mechanic.)

**How much.**

- **4–7 random patches** per map, each an ellipse of **3–9 tiles**, seeded from
  the region seed, placed by the existing `free(x,y)` predicate.
- **1 scripted patch on the critical path:** a band **5 tiles wide × 3 tiles
  deep** immediately west of the **`boss` marker at `(MAP_W-7, midY)`**. This
  is the one the player must solve.

  **THERE IS NO DUNGEON ENTRANCE MARKER, AND THIS USED TO SAY THERE WAS.**
  Measured across all seventeen maps built by the real `placeMarkers()`, the
  only marker kinds emitted are `building` (20), `npc` (20), `shrine` (34),
  `chest` (51), `encounter` (136), `elite` (34), `boss` (11) and `exit` (34).
  A dungeon is entered from the WORLD PANEL, not from a tile —
  `engine.enter_dungeon` and `server.py`'s `/api/dungeon/enter` take a dungeon
  id and check neither region nor position — so an implementer honouring the
  old anchor would have had to invent a marker first, and would have anchored
  the one patch the player must solve to something that does not exist.

  `boss` is 11 rather than 17 because a region with no boss row no longer gets
  a boss tile. **`twin_pointer_pass` is one of the eleven that does**, its boss
  marker is at `(41, 17)` on a walkable tile, and the two `exit` markers at
  `(45, 17)` and `(2, 17)` are the fixtures every map has. Anchor to the boss
  marker here; the east `exit` is the fallback for any region that has no boss,
  and §4.3's region — `stack_queue_mines` — is one of the six.

**Sliding.** The overworld moves tile-to-tile (`p.x, p.y` integers,
`p.px, p.py` interpolated at 112 px/s). Sliding is:

```
on arriving at tile (x,y):
  if grid[y][x] === ICE and not controlled:
      next = (x + lastDx, y + lastDy)
      if solid(next):  stop here, no damage, facing unchanged
      else:            commit to next; repeat
```

- **Input during a slide is buffered, not applied.** The buffered direction is
  applied at the first non-ICE tile you arrive on.
- **Stopping into a solid costs nothing.** No damage, no knockback. Ice is a
  puzzle, not a hazard. There is no hazard in this game that a wrong answer to a
  Python question does not already own.
- A slide that would leave the map stops at the edge tile.

**"Controlled"** is true when either: the escort is Hessa Dunmar, **or**
`skate_irons` is equipped in the feet slot.

**Skates:** controlled movement **and** ICE tiles move at **1.35× = 151.2 px/s**
(0.106 s/tile). Hessa gives control at normal speed.

**Hessa's tell, which the skates never give:** on the player entering the
5-tile approach box of any patch, one line names the walkable exit edge — *"the
north lip holds; the west one drops."* One line per patch, once.

**THE NO-DEAD-END INVARIANT, and it is a generation rule, not a hope:**

> For every ice patch, there exists at least one entry tile whose slide
> terminates on a walkable tile that is still connected to **a walkable tile
> orthogonally adjacent to the region `exit` marker** — the same rule
> `interact()` uses.

**WHY IT IS THE ADJACENT TILE AND NOT THE MARKER, AND WHY THE DUNGEON IS NOT
IN THE SET.** A marker can sit on a SOLID tile and routinely does: measured on
the real generator, `python_village`'s east `exit` at `(45,17)` sits on a
`TREE` and works perfectly well — `overworld.js`'s `interact()`
reads the tile the player is STANDING ON *and the tile they are FACING*, so a
marker on a tree is reached by standing next to it. A literal flood-fill to the
marker's own tile would therefore report a dead end on a map that is fine, and
an implementer trying to satisfy it would carve a hole in a good map to reach
something nobody has to stand on. It is **1 of the 34 `exit` markers** today
and that is the only reason nobody has noticed; nothing stops it being any of
them after the next change to the mass generator, which is why the invariant is
written against the adjacent tile rather than patched per map.

The **dungeon entrance is not in the protected set because it is not a tile.**
See the anchor note above: a dungeon is entered from the world panel and has no
position on the map, so it cannot be cut off by terrain and cannot be flood-
filled to.

Generation flood-fills to check this, and **re-rolls the patch up to 12 times**
before shrinking it to 3 tiles, which trivially satisfies it. **O16 owes a
`scripts/verify` harness that asserts this exhaustively over the seventeen
maps** (see §8.2: there is no seed axis, so one map that fails fails for every
player for ever). The zone is completable with bare feet, from the
first frame, and the skates buy speed, control and dignity — never access. This
game's whole rule is that the measurement is never behind a locked door, and a
sheet of ice is a door.

### 4.2 Darkness

**Where.** `array_caverns` overworld. **The overworld only**, which is what
§8.2's O9 has always said and what this line used to contradict.

`sunken_index` is a DUNGEON, and a dungeon in this game is a node-graph panel
— `web/js/worldui.js`, `api.dungeonMove`, `view.exit_path` — with no tile grid
and no player `x`/`y`. A radius in tiles with a facing offset has nothing to
apply to in there. An implementer who honoured the old clause by hiding room
options would have hidden `exit_path`, which is the way out, and built the
exact dead end this document forbids.

**"Two sprites ahead", in tiles.** A hero is `HERO_W = 16` px wide and the tile
is 16 px. Two sprites is **32 px = 2 tiles.** That is the unlit radius.

| State | Full-bright radius | Falloff ring | Offset |
|---|---|---|---|
| Unlit | **2 tiles** (32 px) | 1 tile to black | none |
| Josa Fell escorting | **6 tiles** (96 px) | 2 tiles | **+2 tiles in facing direction** |
| `the_lamp` held | **5 tiles** (80 px) | 2 tiles | none |

**Draw.** One offscreen 128×128 canvas holding a radial gradient, built once per
radius (three of them, ever). Each frame: draw the world, then fill the viewport
with `rgba(4,3,10,0.94)` through that gradient used as a `destination-out` mask,
scaled to the current `this.scale`. **One extra composite per frame.** No
per-tile work, no shadow-casting, no light polygons.

Markers inside the dark are drawn at the alpha the mask leaves them. **Every
INTERACTABLE marker kind is exempt at 0.25 alpha minimum** — `boss`, `exit`,
`chest`, `encounter`, `elite`, `shrine`, and the `door` and `sluice` kinds
§5.3 and §4.3 add — so nothing a player has to reach can be invisible until
they are standing on it. The exit-glow precedent is already in `overworld.js`
and already brightens while something is hunting.

**ONLY DECORATIVE MARKERS GO DARK:** `npc`, `villager`, and the activity
particles of §7.4. They are atmosphere; losing them to the dark is the
mechanic working.

The old list was boss, exit and chest alone, and it left out everything the
region is actually FOR. Measured, `array_caverns` carries 8 `encounter`, 2
`elite` and 2 `shrine` markers, plus the 2 `door` markers §5.3 puts there — 14
interactables against the 3 that were exempt. At the unlit 2-tile radius the
other 14 are invisible until the player walks onto them, which turns a
lighting mechanic into a search of the whole map and removes the region's
entire reward curve while the lamp is the thing that is supposed to buy it
back.

### 4.3 Lava diversion

**Where.** `stack_queue_mines`. `TERRAIN.LAVA = 9` already exists and already
refuses to be built on.

**A channel** is a 1-tile-wide run of LAVA, **3–6 tiles long**, crossing a path.
Stepping on LAVA is refused (it is already solid to the player in practice);
a channel is a wall until it is drained.

**A sluice** is `TERRAIN.SLUICE = 13`, a walkable tile adjacent to the channel's
head, carrying a `kind:'sluice'` marker so `interact()` finds it through the
existing `this.onEnter(m)` dispatch. Interacting:

| Cranked by | Drain | Open | Refill |
|---|---|---|---|
| Greave escorting | **1.5 s** | **20.0 s** | 1.5 s |
| `the_gear` held | **4.0 s** | **8.0 s** | 1.5 s |
| Neither | refused, with a line: *"the gate is seized. It wants a gear and a pair of hands."* | | |

While open, the channel's LAVA tiles are drawn and treated as `TERRAIN.STONE`.
Crossing a 6-tile channel costs `6 × 0.1428 = 0.86 s`, so the gear's 8-second
window is ample if you are standing there and impossible if you are not.

**THE NO-DEAD-END INVARIANT:**

> No lava channel may be the only route to a walkable tile **orthogonally
> adjacent to** the region `exit` markers, the `boss` marker **where the region
> has one**, or any `encounter` or `elite` marker.

Same two corrections as §4.1, for the same two reasons. **Adjacent, not on**:
a marker can sit on a solid tile and `interact()` reads the FACED tile, so a
flood-fill to the marker's own square would fail on maps that are fine.
**The dungeon entrance is not in the set**: it is not a tile, it is a button on
the world panel, and terrain cannot reach it.

**AND `stack_queue_mines` HAS NO BOSS MARKER.** A boss tile is only emitted for
a region with a boss row, and six of the seventeen have none —
`python_village`, `fields_of_syntax`, `stringwood_labyrinth`,
`stack_queue_mines`, `dp_ruins`, `coding_coliseum`. So on this region's map the
protected set is the two `exit` markers and the ten `encounter`/`elite`
markers, and a check written to require a boss marker would either throw or
silently pass on the one region §4.3 is about.

**`encounter` and `elite` ARE in the set**, and that is an addition rather than
a correction. `array_caverns`-shaped region counts are 8 encounters and 2
elites; a channel that isolates a region's fights does not gate a bonus, it
removes that region's whole reward curve — the xp, the gold, the drops and the
restock credit the rack turns on — which is a dead end with a lava flow in
front of it.

Channels gate **chests, shrines, and one shortcut**. Every one of them has a
walk-around on the same map before the gear exists, and generation asserts it
by the same flood-fill §4.1 uses. **O16 owes a `scripts/verify` harness that
asserts this exhaustively over the seventeen maps.**

### 4.4 The Pack

**Never call it an ambush.** `ambush` means an SRS retest in ~20 places across
`classes.py`, `forge.py`, `items.py` and `finalexam.py`.

**Where.** The three Green regions: `stringwood_labyrinth`, `recursive_forest`,
`binary_tree_canopy`.

**Trigger.** On entering an `encounter` marker in those regions,
**P(pack) = 0.22**, rolled from `hash(save_seed, marker.id)` so it is fixed per
marker per save and cannot be reload-scummed. `elite` markers are never packs —
an elite is already the hard thing.

**It reuses the existing battle.** `incantation.make_context()` takes a list and
its own docstring says so: *"Battles are meant to be LONG and MIXED: several
enemies of different kinds standing at once."* A pack is:

```python
ctx = incantation.make_context([a, b, c, d])   # 3-5 archetypes, existing
```

That is the entire combat implementation. There is no second combat system, no
new battle screen, no new grading path. `battlescene.js` already draws several
enemies.

**Thinning, with Halla or with the dart.** Before turn 1:

```python
for e in ctx.enemies[:-1]:
    e.hp = 0
```

- `ctx.living()` now returns **one** enemy. Correct.
- `ctx.bindings()` still holds the dead names, so they are **still in scope and
  still typeable**. That is not a leak, it is the lesson: a dead `set` is still
  a variable, and naming it is still legal Python. Leave it.
- `ctx.kinds()` already filters to living, so the game will not demand a `deque`
  idiom of a dead deque.
- Four narration lines: one per drop, in Halla's voice or as the dart's
  description.

**Halla:** every pack, forever, free.
**`the_dart`:** 2 charges, `+1` per dungeon boss cleared, cap 2. Spent
explicitly by the player from the battle's item menu, before turn 1 only.
**No charges:** the pack stands. It is a legal multi-enemy incantation battle
that the engine already balances and already rewards. Harder, never a wall.

### 4.5 The Slate

Specified in §1.5. Two stages, both drawn from data that already exists, never a
gate.

---

## 5. The buildings

### 5.1 Doorways and separate interiors

This project uses 16×16 terrain tiles. The proposed interior model keeps that
grid: stepping on a door tile opens a separate furnished room with tables,
chairs, stoves and armour racks. Exterior landmarks and interior details should
make the building's purpose recognizable.

Use a clear door-to-interior transition and original furniture artwork,
generated by the game's existing renderers.

### 5.2 The decision: the panel stays, and it is the fast path

`web/js/townui.js` is a panel with five tabs (THE MENDER, FERRO, THE SHELF,
ORIN TALLOW, THE VOICES, plus THE PORTAL in Python Village). It is also the one
screen in this game where nothing is trying to kill you, and its own source
argues that health is free *because health gates attempts, and charging for
attempts steepens the learning curve exactly where it should flatten.*

Putting a 60-second walk between a player and their next attempt is the same
mistake with a different currency.

> **THE RULE: the panel is canonical and always one key away. Interiors are
> walkable rooms that open the panel's own tab at the counter.**

They merge at exactly one point — the counter — and diverge everywhere else:

| | The panel | The interior |
|---|---|---|
| Reached by | one key, anywhere in a town region | walking to a door tile |
| Owns | every transaction, every price, every refusal | the room, the people in it, the props |
| Decides | nothing (`townui.js`: *"NOTHING HERE DECIDES ANYTHING"*) | nothing |
| Adds | speed | people, rebuild tiers you can see, and the puzzle house |
| Duplicated logic | — | **none.** Standing at Ferro's anvil calls `paintTown('smith')`. |

So a player in a hurry never leaves the panel, and a player who wants to be
somewhere walks in and finds Hedda Ferrin's scorched apron hanging on a nail.

### 5.3 How many buildings, and where

`overworld.js` currently builds settlements only for biomes
`['village','highland','arena','citadel','castle']` — five regions out of
seventeen — while `economy.VENDORS` has **seventeen vendors, one per region.**
Twelve vendors have no building. Fix that.

| Regions | Count | Buildings each |
|---|---|---|
| `python_village` | 1 | **5** |
| `hashmap_highlands`, `matrix_citadel`, `coding_coliseum` — the other town-shaped biomes (`highland`, `citadel`, `arena`) | 3 | **4** |
| the other twelve vendor regions | 12 | **2** — a mender's hut and a shelf. A waystation, which is what a deep region should have. |
| `null_kings_castle` | 1 | **0.** Nothing is labelled and nothing is lit. It is the one place that gets no settlement, and the absence is the point — even though `castle` is on the current townly list. Remove it. |

Total: 5 + 12 + 24 + 0 = **41 buildings**, up from the 20 the five currently-townly
regions produce.

Footprint stays 2×2 tiles with the existing 40×36 sprite and the existing
four rebuild tiers. Nothing about `buildingSprite`'s signature changes.

**Roles**, by `variant`, which the generator already assigns `i % 4`:

| variant | `BUILD_VARIANTS` | Role | Counter opens |
|---|---|---|---|
| 0 | `cottage` | **The Mender's house** — Margit Orr | `paintTown('mender')` |
| 1 | `hall` | **The Shelf** — the region's vendor, and the Rack (§6) | `paintTown('shelf')` |
| 2 | `forge` | **Ferro's forge** | `paintTown('smith')` |
| 3 | `tower` | **Orin Tallow's room** — the assayer | `paintTown('broker')` |
| 4 | `cottage` (5th, Python Village only) | **The Puzzle House** — §5.5 | no panel; it is its own thing |

A 2-building region gets variants 0 and 1: somewhere to be mended and somewhere
to buy a potion. That is a waystation, which is what a deep region should have.

### 5.4 The door, and the interior

- **The door tile is the lower-left tile of the footprint: `(bx, by+1)`.**
  `TERRAIN.DOOR = 14`, walkable, carrying a `kind:'door'` marker with
  `{building, role, variant, tier}`. `interact()` already finds markers on the
  tile you are standing on and on the tile you face, and already calls
  `this.onEnter(m)`. **The entire entry path is one new marker kind.**
- **Interiors are a fixed 14 × 10 tiles = 224 × 160 px.** One room, no camera,
  no scrolling: at the minimum scale of 3 that is 672 × 480, which fits every
  supported canvas. Keeping the camera out of interiors is worth more than a
  big room.
- **Generated, like everything else**, from `hash(building.id)` + role + tier.
  Floor, walls, one window wall, a door tile on the south edge at x=7, and a
  **prop list per role**:

| Role | Props (all procedural, all ≤ 24×24) | People |
|---|---|---|
| Mender | 2 cots, a brazier, a shelf of bandages, a stool | Margit Orr at the cot |
| Shelf | a counter, 3 shelf units, 4 crates, a hanging scale | the region's `economy.Vendor`, plus **the Rack** (§6) on the east wall |
| Forge | anvil, hearth (animated, reuses `tiles.lavaSheet` frames), quench barrel, **an armour stand per equipped piece, drawn at that piece's current integrity tier** | Ferro at the anvil |
| Tower | a desk, a ledger, 2 chairs, a window | Orin Tallow |
| Puzzle house | table, 3 stools, a slate on the wall | one `banter.SPEAKERS` villager of this region |

The forge's armour stands are the single best thing interiors buy: `items.ARMOR_TIERS`
already authors five visual states per piece (*"a hairline crack from brow to
crest"* → *"a polish that throws the torchlight back"*), and right now a player
only ever sees them on their own body. On a rack, at a distance, in a room, they
read as progress.

- **Tier drives the furniture.** The building sprite already has four rebuild
  tiers and the village *"visibly recovers as fluency rises."* Interiors carry
  that inside: tier 0 rooms have a bare floor and a cold hearth, tier 3 rooms
  have rugs, a lit hearth and a full shelf. Same seed, more props.
- **Exit** is the door tile. Stepping on it from inside returns you to the
  overworld at `(bx, by+2)`, facing down — **but only after that tile has been
  proved walkable.** Two ways, either of them one line, and O1/O2 owes one:

  1. Add `&& !tiles.isSolid((grid[by + 2] || [])[bx])` to the generator's own
     `dry(bx, by)` predicate, so a footprint whose doorstep is inside a rock is
     never accepted in the first place; **or**
  2. have `exitInterior()` place the player on the nearest non-solid tile to
     `(bx, by+2)` and fall back to the door tile itself.

  **WHY THIS IS OWED AND NOT ASSUMED.** `dry()` (overworld.js:482) checks only
  the 2×2 footprint, and only for `WATER`, `LAVA`, `BRIDGE` and `CLIFF`. It
  never looks at row `by+2` at all. Measured over every footprint `dry()`
  accepts inside the generator's own placement window (`bx` 4–15, `by`
  4–`MAP_H-6`) across all seventeen maps: **144 of 4,537 (3.2%) put `(bx,
  by+2)` inside a solid tile**, and a further **30 (0.7%) leave it walkable but
  with no walking route back to the spawn component once the 2×2 building
  itself is stamped**. It is harmless today only because `(bx, by+2)` carries
  nothing but a decorative `npc` marker. **This section makes it a TELEPORT
  TARGET** and §5.3 raises the building count from 20 to 41, which is the
  moment a 3.2% chance of landing the player inside a rock stops being
  cosmetic.

### 5.5 The puzzle house

The player asked for *"random buildings with puzzles from characters for
verifying rewards."* `gauntlet/puzzles.py` already has six graded puzzle kinds —
`RUNE_ASSEMBLY`, `TRACE`, `SPOT_THE_FLAW`, `STATE_PREDICT`, `BREAK_IT`,
`COMPLEXITY_MATCH` — every one of them graded by running real Python in the
sandbox or by exact structural match. None of them is a quiz.

- One puzzle house per **Python Village** (variant 4). Optionally one more in
  each 4-building region; **recommended: Python Village only at first.**
- The villager inside is drawn from `banter.SPEAKERS` for that region and offers
  **one** puzzle at a time, of a kind chosen by `puzzles.PUZZLE_SKILL` against
  the player's weakest skill.
- **The reward is paid through `quests.reward_for` at the region's band** — the
  same call `captives.reward_for` makes. No new currency, no off-curve payout.
- **It refreshes on the same clock as the vendor:** one new puzzle per
  `economy.RESTOCK_EVERY = 6` cleared encounters. It is not a faucet.
- It is the one building with no panel tab, because there is nothing to buy in
  it. `puzzleui.js` already exists and already renders all six kinds.

---

## 6. The shop

The player asked for *"randomized armor stats with rare stats being low and same
with swords for gold as well as level specific potions."*

### 6.1 What already ships, and must not be rebuilt

- **Potions by level band: done, correct, change nothing.**
  `economy.stock_list(region)` returns `potions.available_at(area_band(region))`
  — the whole band, thimbles included. Prices `POTION_PRICE = {minor 12, small
  24, medium 80, hefty 140}` × `POTION_KIND_PRICE` (antidote 0.8). Stock cap
  `VENDOR_STOCK = {minor 5, small 4, medium 3, hefty 2}`, refilled by
  `restock()` every `RESTOCK_EVERY = 6` **cleared** encounters. The interior
  renders this; it does not re-decide it.
- **Swords for gold: done.** `forge.GOLD_SHAPE` prices blades at rung 2 = 40g
  through rung 9 = 1500g, on a nine-rung ladder that is this game's progression
  spine. **Do not build a second weapon curve.** A parallel sword economy would
  desynchronise `forge.RARITY_BY_RUNG`, `RUNG_TO_HERO`, the temper system and
  `hunters.RUNG_CREDIT` in one commit.

### 6.2 THE RACK — the new thing, and the only new thing

An **armour** counter on the east wall of every Shelf interior. Randomised,
generated, priced in gold.

**What it carries.** One item per slot, for the eight non-weapon slots in
`items.SLOTS` (`offhand, head, chest, hands, feet, ring1, ring2, trinket`), plus
**at most one blade blank** (§6.6). Eight to nine items, never more.

**What generates a stat roll.** Three rolls, in order:

**(a) Rarity.** The **same weights the drops use** — `items.RARITIES` — so the
rack can never be richer than the world:

| Rarity | Weight | Raw P |
|---|---|---|
| COMMON | 100 | 57.1% |
| UNCOMMON | 46 | 26.3% |
| RARE | 20 | 11.4% |
| EPIC | 7 | 4.0% |
| LEGENDARY | 2 | 1.1% |
| MYTHIC | 0 | **0%** — mythic is secret-only and the rack never sells one |

Then clamped by the region's `economy.AREA_DEPTH`:

| depth | floor | ceiling |
|---|---|---|
| 0–2 | COMMON | RARE |
| 3–5 | UNCOMMON | EPIC |
| 6–7 | RARE | LEGENDARY |

So **Python Village can never sell a legendary** and the Graph Wastes never sell
junk. Effective P(LEGENDARY) at depth 6–7 is 1.1% per slot per restock — about
one legendary per **eleven restocks**, which is 66 cleared encounters.

**(b) Budget.**

```
budget = round(BASE[rarity] * (1 + 0.08 * AREA_DEPTH[region]))
BASE = {COMMON: 2, UNCOMMON: 4, RARE: 7, EPIC: 11, LEGENDARY: 16}
```

**(c) Effects.** Line count by rarity: COMMON 1, UNCOMMON 1, RARE 2, EPIC 2,
LEGENDARY 3. Keys drawn from a **RACK_EFFECTS allowlist** — the same discipline
`captives.BOON_EFFECTS_ALLOWED` uses, and for the same reason:

```
armour_points, armour_cap, stamina_max, stamina_regen,
mana_max, mana_regen, loot_luck, xp_bonus,
resist_fire, resist_cold, resist_poison,
resist_lightning, resist_void, resist_brute
```

**Nothing that reads a problem, names a weakness, discounts a hint, grants a
probe, or stretches a clock.** A `_no_rack_item_supplies_an_answer()` check,
modelled on `captives._no_boon_supplies_an_answer()`, runs in `self_check()` and
fails by name at import.

Magnitude: `value = max(1, round(budget * share / RACK_COST[key]))`, budget
split evenly across the lines.

| key | RACK_COST (budget points per unit) |
|---|---|
| `armour_points` | 1.0 |
| `stamina_max`, `mana_max` | 0.5 |
| `stamina_regen`, `mana_regen` | 2.0 |
| `resist_*` | 20.0 (per 1.00 = 100%; so 3 budget → 0.15) |
| `armour_cap` | 15.0 |
| `loot_luck` | 40.0 |
| `xp_bonus` | 30.0 |

**Rare stats are rare, by rule and not by rounding:** `loot_luck` and
`armour_cap` are **locked behind RARE+**, and `xp_bonus` behind EPIC+. A COMMON
rack item is `armour_points` or a single stat point. Every time.

### 6.3 Price

```
price = round_to_5( ARMOUR_FEE[rarity]
                    * (1 + 0.10 * AREA_DEPTH[region])
                    * (1 + 0.60 * budget_used / budget_max) )
```

`ARMOUR_FEE` already exists: COMMON 20, UNCOMMON 45, RARE 100, EPIC 220,
LEGENDARY 450. A RARE item in the Graph Wastes (depth 6) at a full roll costs
`100 × 1.60 × 1.60 = 256` → **255g**.

**Sell-back is 25% of the buy price, flat, to the vendor who sold it, once.**

### 6.4 How it cannot be farmed

This project's economy has been broken by farming twice. Five locks, each one
closing a specific hole:

1. **The rack is a pure function of `(save_seed, region, restock_index)`.**
   Not of anything the player does inside the shop. Leaving the building,
   leaving the region, reloading the save, quitting to title, or reopening the
   panel **does not reroll it**. Reload-scumming for a legendary is arithmetically
   impossible, not merely discouraged.
2. **`restock_index` only advances through `economy.restock()`,** which is
   already credited **per CLEARED encounter** and already steps every
   `RESTOCK_EVERY = 6`. A fresh rack costs six cleared encounters, and a failed
   encounter buys nothing — that rule is already in `restock()`'s docstring.
3. **One item per slot per restock, and a bought slot stays empty until the next
   restock.** The shelf is finite by construction. Eight items, then nothing.
4. **Gold income is already tapered** — `economy.TAPER_RATIO = 0.55`,
   `TAPER_FLOOR = 0.15`, forgiving over `TAPER_FORGIVE_DAYS = 10`. Grinding
   encounters to fund the rack pays 55% less each repeat, floored at 15%. The
   rack does not need its own taper; it needs to **not bypass this one**.
   Therefore: rack purchases are recorded in the same `_economy(state)` bucket,
   and **the rack does not accept `vendor_credit`** — credit stays potions-only,
   because credit is a quest reward and quest rewards are already curved.
5. **Sell-back at 25% makes buy→sell a 75% loss.** There is no laundering loop
   and no arbitrage between two regions' racks.

**And one ceiling check, asserted at import:**

> For every rarity, the maximum total effect magnitude a rack roll can produce
> is ≤ the maximum an *authored* `items.CATALOGUE` item of that rarity carries.

A generated item can never beat a written one. Written items are what bosses
drop, and a boss drop must stay the best thing that happened to you today.

### 6.5 Levels, and what "level specific" means

The player said *"level specific potions."* The game bands by **region depth**,
not character level — `economy.area_band(region)` → `potions.available_at(band)`
— and that is the better axis, because it means a strong player walking into a
shallow region does not find deep stock and a weak player in a deep region is
not sold something useless. **Keep the region band. Do not add a level gate.**
Say so in the shop UI: the shelf is what *this place* can brew.

### 6.6 The blade blank, so "swords for gold" is honoured without a second curve

Each restock, the Shelf may carry **one un-tempered blade blank**, at
`forge.GOLD_SHAPE[rung] × 1.25`, at a rung `≤ forge.METAL_RUNGS` allows for that
region's own metal (`forge.REGION_METAL`). P(carried) = 0.35.

It is the **same blade the forge makes, at the same rung, bought instead of
forged** — you pay a 25% premium to skip gathering the metal. It tempers,
switches and upgrades through `forge.py` exactly like a forged one. No new
ladder, no new rarity mapping, no new art.

---

## 7. Village life

The player asked for lively villages: both sexes, children, and something
thematic happening. This is a **draw path**. It must be cheap.

### 7.1 How many people

```
villagers = min(12, 2 * buildings)
children  = floor(villagers / 3)
```

Python Village: 5 buildings → **10 villagers, 3 children.** A 2-building
waystation: **4 villagers, 1 child.**

### 7.2 Who they are, for free

- **Named villagers** come from `banter.SPEAKERS` for that region — 2 per
  region, 3 in Python Village, 34 in total, every one already written with a
  name, a role, a sprite key and a register. They talk;
  `townui.talkOnTheOverworld(regionId)` already exists.
- **Everyone else is unnamed and silent.** They walk, they pause, they emote
  (`sprites.EMOTE_KEYS` already exists). They never open a dialogue box. Zero
  new writing.
- **Both sexes cost nothing.** `sprites.heroFrame` already draws a villager out
  of the hero rig with `weapon: null` — its own comment says so — and
  `HERO_BODY_TYPES = ['a','b']` already exists. Body type is `hash(id) & 1`.
  Palette comes from the role. **No new sprite work at all.**

### 7.3 How they move

Each villager owns a **5×5-tile home box** centred on a building. Four
waypoints inside it, deterministic from `hash(id)`, walked at **40 px/s**
(0.40 s/tile — 0.357× the hero's pace, so they read as ambling rather than as
slowed-down heroes), pausing **1.5–4.0 s** at each.
They are markers in the existing y-sort pass. They do not collide with the
player, do not block a tile, and are not in `solid()` or `checkTile()` — the
precedent is the King, whose source says the strongest form of "must not be
annoying" is not being in the simulation at all.

### 7.4 The activity, per biome

One per biome. Every one of them is a handful of pixels on a fixed path, not a
new sprite system.

| biome | Region(s) | Activity | Cost |
|---|---|---|---|
| `village` | Python Village | children chase **butterflies** | 3 × 4×4 px, sine paths |
| `grass` | Fields of Syntax | children chase **butterflies** | same |
| `highland` | Hashmap Highlands | a **kite** on a string | 1 × 8×10 px + a 1px line |
| `forest` | Stringwood | children chase **spelling-beetles** across a fallen letter | 4 × 3×3 px |
| `cave` | Array Caverns | children float **paper lamps** upward | 3 × 4×6 px, +8 px/s drift |
| `swamp` | Sliding Window Marsh | **reed boats** raced in a ditch | 2 × 6×3 px |
| `mountain` | **Twin Pointer Pass** | **a snowball fight** | 2 children + 1 × 3×3 px snowball on a 6-frame arc |
| `mine` | **Stack & Queue Mines** | **fireworks**, one launch every 8–14 s | 12 sparks, 1.4 s life |
| `citadel` | Matrix Citadel | children drill in a square, badly | pose only |
| `deepforest` | **Recursive Forest** | children follow an **ant column** | 8 × 2×2 px on a fixed spline |
| `canopy` | Binary Tree Canopy | a child swings on a **spliced rope** | 1 rope, 1 swinging pose |
| `wastes` | Graph Wastes | a **pennant** flown off a ruin | 1 × 6×10 px |
| `ruins` | DP Ruins | children hop the **lit tiles** | pose only |
| `dungeon` | Debugging Dungeon | apprentices **quench** hot metal | 6 steam puffs |
| `tower` | Complexity Tower | children **count floors** out loud | pose only |
| `arena` | Coliseum | children **spar with sticks** | pose only |
| `castle` | Null King's | **none.** Nobody plays here. | — |

The player named butterflies, a snowball fight in the snow, fireworks in the
volcano and ants in the rainforest. All four are above, in the regions this
document assigns those zones to.

### 7.5 The draw budget, stated as a limit

- **≤ 12 activity particles alive per village.**
- Updated at **12 Hz**, not per frame; positions interpolated between ticks.
- Drawn inside the **existing y-sort pass**, as entries in the same `out` array
  the trees, buildings, NPCs and hero already go into. No second canvas, no
  second `requestAnimationFrame`, no new compositing.
- All of it is suppressed when `this.reducedMotion` is set, which the file
  already threads through every animated path.

---

## 8. BLOCKED — the work list for `overworld.js` and `tiles.js`

Both files are owned by a concurrent pass and are **not touched by this run**.
This is the list the next run works from. Nothing below needs re-reading the
design; each row names the file, the site, and the change.

### 8.1 `web/js/tiles.js`

| # | Site | Work |
|---|---|---|
| T1 | `TERRAIN` (line 52) | Add `ICE: 12, SLUICE: 13, DOOR: 14` |
| T2 | `GROUND_OF` (line 60) | `12:'ice', 13:'stone', 14:'path'` |
| T3 | `PRIORITY` (line 69) | `ice: 1` — ice fringes under grass and path, over water |
| T4 | `isSolid` | ICE, SLUICE and DOOR are all **walkable** |
| T5 | new | `iceTile(P, st, seed, variant)` — 4 variants; a pale surface, 2 scratch marks, a 1px specular. Cache like `stone`. |
| T6 | new | `sluiceTile(P, seed, open)` — 2 states, a cast-iron gate over a cut channel |
| T7 | new | `doorTile(P, st, seed, tier)` — 4 tiers, matching `buildingSprite`'s existing `LIT`/`GLOW` lamp colours |
| T8 | `terrainSet()` (line 2665) | Add `ice`, `sluice`, `door` to the eager/warm sets |
| T9 | new | `interiorSet(seed, role, tier)` — floor, wall, window-wall, and the prop list from §5.4. Fixed 14×10 room. |
| T10 | new | `propSprite(kind, P, seed)` — anvil, hearth, quench barrel, cot, brazier, counter, shelf, crate, scale, desk, ledger, chair, stool, table, armour stand. All ≤ 24×24. |
| T11 | `buildingSprite` | **No signature change.** The door is a separate tile at `(bx, by+1)`; the sprite is untouched. |
| T12 | new | `lightMask(radius)` — one 128×128 radial-gradient canvas per radius. Three ever: 2, 5, 6 tiles. |
| T13 | new | `activitySprite(kind, P, frame)` — butterfly, beetle, paper lamp, kite, reed boat, snowball, firework spark, ant, pennant, steam puff. Ten sprites, none larger than 8×10. |

### 8.2 `web/js/overworld.js`

| # | Site | Work |
|---|---|---|
| O1 | `buildMarkers` townly gate (line 478) | Replace the 5-biome list with the §5.3 table: 5 buildings in Python Village, 4 in the four town biomes, 2 in every other vendor region, 0 in `null_kings_castle`. **And add `&& !tiles.isSolid((grid[by + 2] \|\| [])[bx])` to `dry()`** — see §5.4: the doorstep becomes a teleport target and 3.2% of the footprints `dry()` accepts today put it inside a solid. |
| O2 | `buildMarkers` (line 508) | Emit a `kind:'door'` marker at `(bx, by+1)` with `{building, role, variant, tier}`, and set `grid[by+1][bx] = TERRAIN.DOOR` |
| O3 | new, in `buildMarkers` | **Ice generation** for `twin_pointer_pass`: 4–7 patches of 3–9 tiles + the scripted 5×3 band west of the **`boss` marker at `(MAP_W-7, midY)`** — there is no dungeon entrance marker; see §4.1. **Plus the §4.1 flood-fill invariant (to a walkable tile orthogonally adjacent to the `exit` marker) with 12 re-rolls then shrink-to-3.** |
| O4 | new, in `buildMarkers` | **Lava channels** for `stack_queue_mines`: 2–4 channels of 3–6 LAVA tiles, each with a `kind:'sluice'` marker adjacent. **Plus the §4.3 invariant: never the only route to a walkable tile adjacent to the region's `exit` markers or to any `encounter`/`elite` marker.** No dungeon entrance in the set (it is not a tile) and no boss marker on this map (`stack_queue_mines` has no boss row, so none is emitted). **BLOCKED on the preconditions in §8.2.1 — `the_gear` is the only other way to crank a sluice.** |
| O5 | new, in `buildMarkers` | **Villagers**: `min(12, 2*buildings)` `kind:'villager'` markers, `floor(n/3)` flagged `child`, each with a 5×5 home box and 4 seeded waypoints |
| O6 | new, in `buildMarkers` | **Activity emitters**: one per village, kind from the §7.4 biome table, capped at 12 particles |
| O7 | `update()` (line 866) | **BLOCKED on §8.2.1.** **The slide.** On tile arrival, if `grid[y][x] === ICE` and not controlled, commit to `(x+lastDx, y+lastDy)`; stop into a solid with no damage; buffer input and apply it at the first non-ICE arrival. |
| O8 | `update()` speed (line 870) | `speed` becomes `112`, or `151.2` when on ICE **with** `skate_irons`. It is currently a hard-coded local. |
| O9 | `draw()`, after the world, before screen space | **BLOCKED on §8.2.1.** **The darkness composite.** `array_caverns` only — the overworld, never a dungeon panel; §4.2 now says the same. `destination-out` through `tiles.lightMask(r)` at the §4.2 radii, with the facing offset when the escort is Josa Fell. **Every interactable marker floored at 0.25 alpha** — `boss`, `exit`, `chest`, `encounter`, `elite`, `shrine`, `door`, `sluice` — and only `npc`, `villager` and the activity particles go dark. |
| O10 | `_drawables()` / the y-sort `out` array (line ~2100) | Draw cases for `villager`, `door`, `sluice`, and the activity particles. All join the **existing** sort — the companion's own comment explains why that matters. |
| O11 | new, beside `setCompanion` (line 1043) | **`setEscort(row)` / `_syncEscort()`** — the human follower. **Do not extend the pet path.** `companion` is `pets.py`; the escort walks at `COMPANION_LAG` behind on the same trail ring buffer, uses the villager rig, and is drawn in the same y-sort with the same over-hero clamp. |
| O12 | `interact()` (line 1017) | Already dispatches any marker through `this.onEnter(m)`. **No change needed** — `door` and `sluice` arrive for free. Verify only. |
| O13 | new | **The interior mode.** `enterInterior(doorMarker)` swaps `this.scene` for `tiles.interiorSet(...)`, fixes the camera (14×10 needs none), and `exitInterior()` returns the player to `(bx, by+2)` facing down. |
| O14 | new | **The counter.** A `kind:'counter'` marker in each interior; standing on it and pressing the interact key calls `townui.paintTown(role)`. This is the whole merge point between the panel and the rooms. |
| O15 | new | **The capture scene**, §2.2: eight seconds, three lines, a 1.2 s colour wash at 0.35 alpha, the escort sprite removed, a two-second glint where they stood (decorative — the item is already granted server-side). **Never blocks input.** |
| O16 | `scripts/verify` | Assert the §4.1 and §4.3 no-dead-end invariants **exhaustively over the seventeen maps — there is no seed axis to sample.** `buildGrid` seeds from `hash(region.id)` alone (overworld.js:406) and `placeMarkers` from `hash(region.id) + 99` (overworld.js:455), so every region rebuilds a byte-identical grid and marker list on every load: measured 17/17 identical across reloads and across tier 0 vs tier 3, 0 differing. **The consequence is the whole reason this row exists: a generation invariant that fails does not fail for one player in two hundred, it fails permanently, for every player, on that map, for ever.** Seventeen maps is the entire population, so the harness can prove it rather than sample it. |

### 8.2.1 PRECONDITIONS — the order is a requirement, not a suggestion

**O4, O7 and O9 MUST NOT LAND BEFORE THE PYTHON SIDE IS WIRED.** This is the
one ordering hazard in the whole design that can seize a gate permanently, and
it is stated as a table row rather than as advice because that is what somebody
reads.

| Owed first | Where | Why it blocks |
|---|---|---|
| `engine.DEFAULT_STATE` gains the `"escorts"` key | `zonecompanions.new_escort_state()` | Without it there is no latch; the derivation still answers, but nothing records a scene. |
| `zonecompanions.advance(self.state)` is called on region entry | `Game.travel`, `Game.move` | **This is the only thing that grants the drops.** Nothing else in the codebase writes them. |
| the five rows exist in `items.CATALOGUE` | `the_slate, the_lamp, skate_irons, the_dart, the_gear` | A granted id the catalogue has never heard of is invisible in the loadout and refuses to equip — which makes `skate_irons`, slot `feet`, a slot that can never be filled, and §4.1 makes ice control conditional on it being EQUIPPED. |

**The sweep needs the LADDER, not one boss id.** `zonecompanions.SWEEP_AFTER_BOSS`
is `bug_demon`, and `bug_demon` is the ONE boss a brand new save can reach:
`rt_armorers_stair` runs `python_village -> debugging_dungeon` on
`Need(kind='none')`, and walking the route graph from the village square using
only roads that need nothing reaches exactly three regions — `python_village`,
`fields_of_syntax`, `debugging_dungeon` — with exactly one boss standing in
them. So `sweep_fired()` requires that boss **and** at least
`len(world.BOSSES) - 2` rungs down, or a player who takes the stair under the
forge on their first afternoon loses Thessaly Brun before she has given the
tutorial she exists to give.

**What happens if O4 ships first.** Greave's `without` column is
`{"drain": 0.0, "open": 0.0, "refill": 0.0, "crankable": False}` — a flat
refusal, and the only hard gate in this design. `the_gear` is the only other
way to crank a sluice, `advance()` is the only thing that grants `the_gear`,
and nothing outside `tests/` imported `zonecompanions` at all. So every sluice
in `stack_queue_mines` would be shut, permanently, for a player who had already
lost Greave.

Measured by enumerating the two facts the arc derives from — capture dungeon
cleared, boss beaten — across the four dungeon companions, 1,024 save shapes in
all, and asking of each companion whether the player has the PERSON walking or
the THING in the bag:

| | carries the escort or the item | carries neither |
|---|---|---|
| `advance()` called per tick | **1024 of 1024** | 0 |
| `advance()` never called | 256 of 1024 | **768** — 512 of them FREED, 256 TAKEN |

The FREED half is the worse one: the player went and beat the boss, the person
went home, and the thing they left never arrived.

**What happens if O7 or O9 ships first.** Ice without `skate_irons` and
darkness without `the_lamp` are both survivable — §4.1's flood-fill invariant
and §4.2's exempt-marker floor exist precisely so the zone is completable
without the item — but the player loses the item's half of the arc with no way
to earn it back, and the loss the design is built around stops being a loss and
becomes a bug.

*(As of this revision all three preconditions are met: `engine.py` imports
`zonecompanions`, `DEFAULT_STATE` carries `"escorts"`, `_advance_escorts()` runs
on both region-change sites and in `_resolve_boss`, and the five rows are in
`items.CATALOGUE`. The row stays because the next agent needs to know the
dependency exists, not because it is still open.)*

### 8.3 Not blocked — buildable now, in this run or the next

`gauntlet/captives.py` (two new rows, five capture lines, `retake()`),
`gauntlet/items.py` (five zone items, the RACK_EFFECTS allowlist, the rack
generator and its `self_check`), `gauntlet/economy.py` (the rack's restock
binding and the credit refusal), `gauntlet/incantation.py` (nothing — the pack
already works), `web/js/townui.js` (a Rack section under the `shelf` tab),
`web/js/puzzleui.js` (nothing — it already renders all six kinds).

### 8.4 LANDED — what is wired and reachable as of this revision

Everything in this row was built, green in its own test file, and imported by
nothing in `gauntlet/`. A module nobody imports is a module the player cannot
reach, however green its own tests are, which is what
`tests/test_art_is_wired.py`'s orphan guard exists to say.

| Module | Where it lands | Reachable at |
|---|---|---|
| `gauntlet/zonecompanions.py` | `engine.DEFAULT_STATE["escorts"]`; `Game._advance_escorts()` in `travel`, `move`, `region_view`, `world_map` and `_resolve_boss`; `zonecompanions.capture()` beside the `cleared_bosses` append | `GET /api/escorts`, and `escort` / `zone` on `GET /api/region` |
| `gauntlet/villagelife.py` | `Game.region_view` (one village) and `Game.world_map` (all seventeen), seeded off `state["world_seed"]` | `village` on `GET /api/region`, `villages` on `GET /api/world-map` |
| `gauntlet/shop.py` | `Game.shop` is now `shop.counter(...)`, which calls `economy.vendor_view` itself and adds the rack; `Game.buy_rack` / `sell_rack` / `buy_blank` apply the spend, the bag and the forge grant | `GET /api/shop` (`rack`, `rack_left`, `blank`), `POST /api/shop/rack/buy`, `/rack/sell`, `/blank`, all three sealed at BUILD |
| `gauntlet/items.py` | the five drop rows, `source="quest"` so `roll_drop` can never offer one | the bag, the loadout panel, and `feet` for `skate_irons` |

The rack is drawn by `paintShelf` in `web/js/townui.js` under THE RACK, which
closes §8.3's row for that file. The five §4 terrain mechanics are still owed
and still blocked — see §8.2.1.

---

## 9. Open questions, with the recommendation

| # | Question | Recommendation | Reason |
|---|---|---|---|
| 1 | Is the Green zone's rainforest the Stringwood (POISON, and `elements.py`'s own comment calls it *"the rainforest of the brief"*) or the Canopy? | **Both, as one zone.** Halla walks all three forest regions; the capture dungeon is `anagram_deeps` in the Stringwood; the boss is the Tree Dragon in the Canopy. | Stringwood has no boss. Splitting the zone across the Inward Trail and the Branch Ladder is the only shape that keeps `elements.py` honest *and* hangs the rescue on a real boss. |
| 2 | Greave is taken by a boss from a different region. Does that break "the zone boss takes them"? | **Accept it, and say it in the scene.** The Necromancer came up the ore line. | Every alternative was worse (§1.3 table). `Captive.home ≠ held_in` is already supported and already used by Thessaly Brun. |
| 3 | The lantern's radius: bigger or smaller than Josa's? | **Smaller — 5 vs her 6 — and it loses the facing offset.** | The player wrote "increased radius", which reads as increased *over the dark* (2 → 5). The brief's rule that the loss must be felt outranks the ambiguity, and the offset is a cleaner loss than a number. |
| 4 | 5 companions, or a 6th in the late game? | **Five.** | §1.1. If a sixth is ever added, `graph_wastes` / Jessamy Roke is the candidate, because her boon is already half a companion. |
| 5 | Puzzle houses everywhere, or Python Village only? | **Python Village only, first.** | It is a new reward faucet. Prove it does not distort the curve in one region before adding twelve more. |
| 6 | `cinder_greaves` moved from Hedda Ferrin to Greave, `lanternshoes` shared between Wilmot Tace and Halla Vane | **Do both**, and mint `forge_apron` for Hedda | Greaves are a Mines item; a plate-smith's signature is an apron. Two people in one family handing over the same boot is a village. |
| 7 | Does the interior need a camera? | **No.** 14×10 tiles at scale 3 is 672×480. | Keeping the camera out of interiors is worth more than a bigger room. |

---

## 10. The one-line summary, for the next agent

> Five people walk five zones and do one verb each. After the zone's capture
> dungeon they are taken, they always leave the item, the item is always worse
> than they were, and you get them back by beating the boss that took them —
> through `captives.free`, which already exists. Buildings get doors and
> fourteen-by-ten rooms; the town panel stays and is the fast path, and the room
> opens the panel at the counter. The rack sells generated armour on the drops'
> own rarity table and is reseeded only by six cleared encounters. Villages hold
> up to twelve people and twelve particles. Nothing is ever behind a locked
> door.
