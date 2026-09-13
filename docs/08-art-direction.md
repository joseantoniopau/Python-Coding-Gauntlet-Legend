# Art Direction — what we took from Final Fantasy VI, and what we did not

The player asked for the look and feel of *Final Fantasy VI* on the SNES. What
follows is the research, the principles we adopted, and the line we do not cross.

## The line

We take **techniques and constraints**, never assets. Nothing in this project is
traced, sampled, recoloured or derived from FFVI or any other game. No character,
sprite, tile, background, logo, melody or name is borrowed. Every pixel is
authored here, in code.

That distinction matters and it is not merely legal hygiene: the interesting part
of FFVI's look is *how it was made under constraint*, and that is exactly the part
that transfers.

## What the research actually said

**Sprites were built to a hardware palette budget.** An SNES sprite uses a
16-colour palette where entry 0 is transparent — so **15 usable colours per
sprite**, chosen from one of 8 palette slots. Sprites are 4bpp tiles, and the
hardware allows 8x8 up to 64x64 plus 16x32 and 32x64 rectangles, with a hard limit
of 32 sprites per scanline.
([SNESdev Wiki](https://snes.nesdev.org/wiki/Sprites),
[Megacat Studios](https://megacatstudios.com/blogs/retro-development/snes-sprite-engine-design-guidelines))

**Low resolution is a unifier, not a limitation.** The most useful observation we
found: "the sheer brutality of low-resolution pixels creates a *mosaic effect*
that tends to unify everything" — inconsistencies between sprite art, tile art and
portrait art become invisible when everything shares the same pixel grain. FFVI's
coherence comes substantially from that shared grain rather than from any single
asset being beautiful.
([Fortress of Doors](https://www.fortressofdoors.com/doing-an-hd-remake-the-right-way-ffvi-edition/))

**The art descended from a single concept.** Yoshitaka Amano's concept work was
interpreted into sprites by Kazuko Shibuya; the sprites read as one world because
they all resolve the same source. The lesson is not "hire Amano" — it is that a
consistent underlying concept is what makes independently-drawn assets agree.
([Fortress of Doors](https://www.fortressofdoors.com/doing-an-hd-remake-the-right-way-ffvi-edition/),
[Game Developer](https://www.gamedeveloper.com/business/doing-an-hd-remake-the-right-way-ffvi-edition))

**Battle was a side-on tableau.** ATB, up to four party members, gauges filling in
real time, a command window, and the party arranged on the **right** facing
enemies on the **left**, against a layered animated backdrop.
([Final Fantasy Wiki](https://finalfantasy.fandom.com/wiki/Final_Fantasy_VI_battle_system),
[Active Time Battle](https://en.wikipedia.org/wiki/Active_Time_Battle))

> **Status.** Sections 1–6 are the principles and are unchanged. Sections A–G are
> the **contract**: the numbers several agents are about to draw against. Every
> figure in them was measured from this repository or computed from a measured
> figure, and §G says how each one is re-proved. Where this document previously
> disagreed with the code, the code won and the disagreement is recorded rather
> than quietly deleted.

## The rules we adopted

These six are unchanged. They were right. What follows them — the contracts —
is new, and exists because a rule that does not carry a number gets a different
answer from every agent that reads it.

### 1. Fifteen colours, and they are a ramp

Every sprite is authored against a palette of at most 15 colours plus
transparency. Those colours are not arbitrary: they are organised as **material
ramps** of 3–5 steps (shadow, mid, light, specular) shared between sprites, which
is what makes a scene look like one object family rather than a sticker book.

`web/js/palette.js` enforces this. A sprite that exceeds the budget is a bug, and
`auditPalette()` will say so.

**The budget is FULL.** `scripts/verify/hero.mjs` counts the raster and reports
`worst frame : 15 colours` over 192,456 sampled frames. There is no headroom.
Every contract below is therefore designed to cost **zero new colours**, and any
proposal that needs a sixteenth must name the fifteenth it is evicting.

### 2. One pixel grid, everywhere

Every sprite is an integer multiple of the 8x8 SNES tile, and is scaled by
integers only. Nothing is drawn at a fractional scale and no UI element sits on
a half-pixel. This is the mosaic effect, and it is the cheapest coherence
available to us. The exact ladder is §B; the sizes that used to be quoted here
were wrong and are the reason §B exists.

### 3. Hard outline, three tones, one rim

Every sprite gets a near-black outline, a minimum of three body tones, a lit edge
on the upper left, and a single rim light in the creature's own colour so it
separates from a dark stage.

**This rule is currently violated by the hero itself.** Counted out of
`HERO_BODY`, the torso spends its cloak cells on exactly one tone:

| facing | cloak cells | `c` base | `C` light | `v` shadow | verdict |
|---|---|---|---|---|---|
| down  | 46 | 46 | 0 | 0 | flat |
| left  | 70 | 70 | 0 | 0 | flat |
| right | 70 | 70 | 0 | 0 | flat |
| up    | 84 | 74 | 10 | 0 | one step |

`v` — cloak shadow — is a paid-for palette entry that renders **zero pixels
anywhere on the hero**. The three tones are already bought. They are simply not
spent. Fixing this costs nothing but authoring.

### 4. The tableau is side-on, and the sides are fixed

FFVI's convention is party **right**, enemies **left**, a shared ground line, and
the command surface below.

**The code ships the mirror of that.** `fx.js` and `battlescene.js` both declare
`heroX: 46, enemyX: 136` on a 192-wide stage — party **left**, enemies **right**.
This document asserted the opposite for as long as it has existed. See §F-7: the
flip is a real decision with a real cost, and it is not made here.

### 5. Backgrounds are layered and alive

Three depth layers minimum, moving at different rates, with one animated element
per biome (drifting fog, falling ash, guttering torchlight, lava glow). A static
backdrop is the single clearest tell of a cheap 16-bit imitation.

### 6. The window is furniture

FFVI's menus are a consistent framed window with a hard border and a readable
bitmap face. Ours are steel frames with rivets and a chrome bevel — a different
material, the same discipline: one window style, used everywhere, never restyled
per screen.

## Where we deliberately differ

FFVI is high-fantasy and warm. This project is **dark 80s metal**: near-black
grounds, gunmetal, blood red, bone white, electric violet, hot orange. The
construction rules above are FFVI's; the palette and subject matter are not.

The reason is that the soundtrack is a metal rig — waveshaper distortion, power
chords, galloping double kick — and a bright pastel world under that music would
read as a mistake. The art and the audio have to agree.

---

# §A. THE RASTER

## A-1. The decision

The stage raster moves **192x128 → 256x224**. 256x224 is SNES native and is what
FFVI shipped. This is decided and is not re-opened.

Art budget per frame, **authored**: 24,576 → 57,344 pixels.

Art budget per frame, **delivered — and this is the number to quote**: the 224
lines are authored, but `fitBattleStage()` fits the 176-line safe area
(`STAGE_LOGICAL.fitH`), so the canvas is never tall enough to hold all of them.
Counted off the live stage at every window size this game opens at — all 256
columns reach the canvas every time:

| window | dpr | px | canvas | rows touched | delivered |
|---|---|---|---|---|---|
| 1280x800 | 1 | 2 | 526x366 | 184 of 224 | 47,104 px |
| 1440x940 | 1 | 2 | 526x366 | 184 of 224 | 47,104 px |
| 1600x1000 | 1 | 3 | 782x542 | 182 of 224 | 46,592 px |
| 1920x1080 | 1 | 3 | 782x542 | 182 of 224 | 46,592 px |
| 1440x940 | 2 | 5 | 1308x908 | 182 of 224 | 46,592 px |
| 1600x1000 | 2 | 6 | 1564x1084 | 182 of 224 | 46,592 px |

**about 46,600–47,100 pixels against the old frame's 24,576 — a 1.90x–1.92x
gain, not 2.33x.** The remaining 40–42 rows are drawn and fall off the canvas as
overscan, which is what §A-3 is for. Quoting 57,344 overstates what the player
sees by a fifth.

## A-2. The trap, stated exactly

FFVI's frame is 8:7 (1.14). The box `fitBattleStage()` produces is 3:2 (1.48) —
wide and short. A taller raster in a wider box loses on the vertical, and the
vertical is the axis that is already starved.

**And the box this ends at is 16:11, not 8:7,** because it is sized to `safeH`
and not to `h`: 256/176 = 1.4545, and the boxes measured live are 526/366 =
1.437 and 782/542 = 1.443 once the border and the gutter are in. That is a
consequence of §A-3, not a miss. An 8:7 box is a box fitted to all 224 lines,
and §A-3 refuses that trade and says what it costs.

But the trap is **not** where it looks. `fitBattleStage()` derives `boxW`/`boxH`
*from* `STAGE_LOGICAL`, so it is already aspect-agnostic: changing the constant
re-derives the box. The claim that a 256x224 raster lands at scale 1 in a
1440x940 window is only true if the box is held at its old 590x398. It is not.

Measured, then computed (dpr 1, all six sizes driven live through a real
encounter):

```
bw = bh = 6      stage border, total across both edges
chromeV = 47     #enemy-strip + 6 + #battle-top padding + bottom rule
chromeH = 28     #battle-top left+right padding
GUTTER  = 8   BAND = 0.62   MAIN_MIN = 200   WIDE = 0.52
```

## A-3. The overscan rule, which is what actually makes it fit

A naive swap to 256x224 costs a scale step at 1280x800 and pushes the editor
*below* its own floor at 1024x640. Buying scale 2 back at 1280x800 with the full
224 lines requires `MAIN_MIN <= 159` and `BAND >= 0.676` — an editor of about
three code lines. The editor is the half of the screen the game is about, so
that price is refused.

The answer is the one the hardware already gave us. NTSC sets cropped the top
and bottom of the frame, so console artists authored 224 lines and **trusted
176**. We do the same:

> **The raster is 256x224. The SAFE AREA is 256x176, rows 24..199 inclusive.**
> `fitBattleStage()` fits the safe area; the canvas renders all 224 lines.
> Rows 0..23 and 200..223 are overscan: atmosphere, parallax sky, foreground
> apron. **Nothing load-bearing may live there** — no sprite the player must
> read, no gauge, no number, no ground line.

## A-4. The arithmetic, worked at the window the launcher opens

1440x940, measured `sh = 893`, `hudH = 116`:

```
bandMax = max(140, 893 - 116 - 200)            = 577
band    = min(893 * 0.62, 577) = min(553.66, 577) = 553.66
artMaxH = max(176, 553.66 - 47 - 6 - 8)        = 492.66
artMaxW = max(256, 1440 * 0.52 - 28 - 6 - 8)   = 706.80
px      = floor(min(492.66/176, 706.80/256))
        = floor(min(2.799, 2.761))              = 2
boxW    = 256 * 2 + 6 + 8 = 526
boxH    = 176 * 2 + 6 + 8 = 366
editor  = 893 - 116 - 366 - 47 = 364           (floor is 200) OK
```

## A-5. Every size, three ways

`s` = integer scale, `ed` = pixels left for the editor column (floor 200).

| window | today 192x128 | naive 256x224 | **safe-area fit (adopt)** |
|---|---|---|---|
| 1024x640  | s1 206x142 ed 263 | s1 270x238 ed **167 FAILS** | s1 270x190 ed 215 |
| 1280x800  | s2 398x270 ed 304 | s1 270x238 ed 336 *(hero halves)* | **s2** 526x366 ed 208 |
| 1440x940  | s3 590x398 ed 332 | s2 526x462 ed 268 | **s2** 526x366 ed 364 |
| 1600x1000 | s4 782x526 ed 264 | s2 526x462 ed 328 | **s3** 782x542 ed 248 |
| 1920x1080 | s4 782x526 ed 344 | s2 526x462 ed 408 | **s3** 782x542 ed 328 |
| 2560x1440 | s6 1166x782 ed 448 | s3 782x686 ed 544 | **s4** 1038x718 ed 512 |

The safe-area column is the only one that holds scale 2 at 1280x800 and the only
one that keeps the editor above its floor at 1024x640.

> **IMPLEMENTATION NOTE, added when §A was built.** The table above is reachable
> only with `MAIN_MIN` at **184**, not the 200 the constants block quotes, and
> the shipped code now says 184. The reason is `hudH`: §A-4 measured 116, but at
> 1280x800 the belt line inside `#combat-hud` wraps to a second row and the HUD
> measures **148**. That makes `bandMax = 753 - 148 - 200 = 405`, so
> `artMaxH = 344` and `344 / 176 = 1.955` — scale 2 needs 352, and 1280x800 fell
> to scale 1 by eight pixels, which is the one failure this whole section
> exists to prevent. At 184 the same window gives `artMaxH = 360`, scale 2, and
> leaves `#battle-main` 192px — which is this table's own "ed 208" measured one
> node further out. Driven live at all six sizes, 184 changes exactly that one
> window and none of the other five comes within 20px of the floor.
> `scripts/verify/stage.mjs` asserts the whole table.

**The honest cost.** A 16x24 field sprite on screen:

| window | today | after |
|---|---|---|
| 1280x800 | 48px | 48px (held) |
| 1440x940 | 72px | 48px |
| 1600x1000 | 96px | 72px |
| 2560x1440 | 144px | 96px |

The figure gets smaller in device pixels at three sizes. That is the real price
of 1.9x the art budget in a box this shape, and it is paid back in §B: the
battle rig moves to 24x32, so the *battle* hero at 1600x1000 is 32x96 device
pixels — the same height it is today, with 2x the pixels inside it.

## A-6. Composition, in raster coordinates

Ratios are preserved from the shipped 192x128 stage so no scene re-composes.

| anchor | today (192x128) | as a fraction | **new (256x224)** |
|---|---|---|---|
| ground line | y = 100 | 78.1% | **y = 175** (78.1%) |
| party foot centre | x = 46 | 24.0% | **x = 64** (25.0%) |
| enemy foot centre | x = 136 | 70.8% | **x = 184** (71.9%) |

`x = 64` and `x = 184` are multiples of 8 and therefore land on the tile grid.

**The ground line at 175 is load-bearing.** A 96x128 apex boss standing on it
spans rows 47..174, which is inside the safe area (24..199) with 23 rows to
spare above. Move the ground line down and the tallest thing in the game gets
its head cropped on a short window.

---

# §B. THE SPRITE LADDER

Every rung is an integer multiple of the 8x8 SNES tile. FFVI's field sprite is
16x24 = 2x3 tiles, and that is the unit the whole ladder is built from.

| rung | logical | tiles | FFVI reference | code today |
|---|---|---|---|---|
| field character | **16x24** | 2x3 | FFVI field/NPC sprite — exact | `HERO_W/HERO_H` sprites.js:479-480 |
| battle hero | **24x32** | 3x4 | FFVI battle sprites are larger than field sprites | **new** |
| ordinary monster | **24x24** | 3x3 | FFVI small enemy (imp/lobo class) | `ENEMY_SIZE` sprites.js:3231, `MON_SIZE` monsterart.js:230 |
| elite | **32x32** | 4x4 | FFVI mid enemy | `ELITE_SIZE` monsterart.js:236 |
| apex | **48x48** | 6x6 | FFVI large enemy | `APEX_SIZE` monsterart.js:247, `APEX_SIZE` apex.js:751, `BOSS_SIZE` sprites.js:3954 |
| boss | **64x64** | 8x8 | FFVI boss | `BOSS_W/H` bosses.js:108-109, `ART_W/H` bossart.js:168-169 |
| wide boss | **96x64** | 12x8 | FFVI wide boss | `BOSS_WIDE_W` bosses.js:110, `ART_WIDE_W` bossart.js:170 |
| final boss | **96x128** | 12x16 | FFVI's big summons (Bahamut, Alexander) | `FINAL_BOSS_W/H` bosses.js:125-126, `ART_FINAL_W/H` bossart.js:177-178 |

Every line reference in the "code today" column is checked by
`scripts/verify/stage.mjs` §2, which now reads `ELITE_SIZE`, `FINAL_BOSS_W/H`
and `ART_FINAL_W/H` as well — the elite and final rungs were outside the
whole-tile check entirely, which is how the table above came to point `elite`
at `APEX_SIZE`.

**The drift this replaces.** This document previously claimed "48x64 bosses".
No such size exists in the code. `sprites.js` has `BOSS_SIZE = 48` (square);
`bosses.js` and `bossart.js` have 64x64 with a 96-wide variant. Two boss rigs at
two sizes, and the spec named a third that was neither. The ladder above is the
code, corrected.

## B-2. The blit factor, which is the half of the ladder that can go wrong

A rig size is only half of what the player sees. The other half is the whole
number the stage blits it at, and the product of that number and the stage's own
`px` is what one authored pixel covers in device pixels. **`blit * px` must be a
whole number at every `px` the fit produces, and `px` is not always even** —
measured live it is 2 at 1280x800 and 1440x940, 3 at 1600x1000 and 1920x1080, 5
at 1440x940 dpr2 and 6 at 1600x1000 dpr2.

| rung | rig | blit | on the stage | whole at every px |
|---|---|---|---|---|
| field character / battle hero | 16x24 | 4 | 64x96 | yes |
| ordinary monster | 24x24 | 4 | 96x96 | yes |
| boss | 64x64 | 2 | 128x128 | yes |
| wide boss | 96x64 | **2** | **192x128** | yes |

**The wide boss used to be blitted at 1.5**, which is whole at even `px` and half
a pixel at 3 and 5 — three of the six configurations. Rendered at 4.5 and
counted, 48 of the dragon's 96 source columns came out 4 device columns wide and
48 came out 5; beside a whole x4 render the teeth are uneven, one horn is a pixel
fatter than the other and the two pupils are different sizes.

**There is no third option.** A 96-cell rig can be 96 logical pixels wide or 192
and nothing between: 144 needs cells 1.5 pixels wide, which is the same half
pixel moved one step earlier in the pipeline. Re-authoring the four wide rigs
into a 72x64 box to reach 144 at blit 2 would cost real drawing — their painted
content spans 81 columns (dragon), 84 (wyrm) and 91 (interpreter), so 72 clips
wing, staff and coil. So 2, and the wide rigs are 192x128 — which is §B's 96x128
rung in logical pixels, at the cost of no art at all.

192 centred on `enemyX` 184 runs 88..280, so each wide archetype carries a
`bias` computed from its painted bounding box rather than guessed:

The bias must absorb the SWAY as well as the pose. `drawBoss` blits at
`left + dx` where `dx = clamp(round(pose.dx * scale), -4, 4)`, applied every
frame forever because the ambient pose is continuous and the frames are not. A
bias derived from a still is half a bias: three of these four sat at exactly
column 255 with zero slack and spent part of every idle cycle over the edge —
the dragon reaching 257, the wyrm and the interpreter 259.

Measured over all six stages x five frames x six beats x every `dx` the clamp
can produce — 540 to 900 sampled frames each, which is the full envelope the
renderer can put on the glass:

| archetype | paints cols | bias | on screen | fills its box | frames outside 0..255 |
|---|---|---|---|---|---|
| dragon | 4..89 | −14 | 80..255 | 90% | 0 of 540 |
| hydra | 21..79 | 0 | 126..251 | **61%** | 0 of 900 |
| wyrm | 0..84 | −6 | 78..255 | 89% | 0 of 900 |
| interpreter | 0..93 | −24 | 60..255 | 98% | 0 of 900 |

Each bias is the LARGEST that clears the edge, so the figures move the two or
four columns they had to and not one more. Do not shrink the `dx` clamp instead
— the ±4 cap is what keeps a 128-wide rig in frame in the first place.

**The hydra does not use the rung it declares.** It asks for 96 columns and
paints 59 of them (21..79) at a density of 19.7%, against 89–100% for the other
three. This is pre-existing — its body grid and every offset are unchanged since
17cccbf — and it is a real art decision, not a flag: re-authoring to 96 means
finding somewhere for the two outer heads to go, and dropping to `wide: false`
means shifting the body `ox`, every part `ox`, both faults and the core left by
21. `stage.mjs` §5 prints the fill fraction for every rig and names this one on
every run until it is settled one way or the other.

The hero stands 32..95, so on the frames where the wyrm's and the interpreter's
coils swing furthest left they reach behind him. **`fx.js` therefore draws the
hero AFTER the enemy.** A creature this size cannot both clear the party and keep
its own tail, and of the two the party is the one that must never be hidden.
`scripts/verify/stage.mjs` §5 asserts every blit and every painted box.

**The final boss, checked against the frame.** 96x128 is 57.1% of the 224-line
frame height and 37.5% of its width; standing on the ground line it fills 72.7%
of the safe area's height. (An earlier note put this at 43% — that is 96/224,
the width against the height, and it is wrong.)

---

# §C. THE FACE CONTRACT

This is the heart of the pass. A face at this size is not drawn, it is
*budgeted*.

## C-1. What is actually wrong, measured

The emote system is real and must be kept: seven `EMOTE_KEYS`, two authored
frames each, and the eyes genuinely change. The head is 8 of 24 rows — a 1:3
super-deformed ratio, which is exactly why an FFVI face reads at this size.
**Keep the ratio and keep the two-frame structure.**

What fails is separation. Diffing the authored strips cell-by-cell (80 cells per
emote), the shipped front face scores:

| closest pairs (front) | cells differing / 80 |
|---|---|
| **neutral vs stubborn** | **6** |
| pleased vs defeated | 8 |
| neutral vs pleased / neutral vs defeated / pleased vs alarmed / strained vs delighted | 10 |

In profile, `neutral vs stubborn` differs by **3 cells out of 80**. Those two
emotes are the same face.

One correction to the brief that matters, because it changes where the effort
goes: **`delighted vs defeated` is not a confusable pair.** It measures 18 cells
front / 11 profile, mid-table. The pairs that actually collapse are
neutral/stubborn and pleased/defeated. The complaint is real; the diagnosis was
aimed one pair over.

The second failure is the blink. Within one emote, frame 0 vs frame 1 differs by
**2 cells** for neutral, pleased, stubborn and delighted. The second frame is
supposed to be an event — a blink, a squeeze, a jaw setting.

## C-2. The geometry, and why the face must get wider

The head is 8 rows of 24 and stays that way. What changes is width:

| measure | today | **contract** |
|---|---|---|
| head outer | 10px (cols 3..12) | **12px (cols 2..13)** |
| head interior | 8px | **10px** |
| face, skin | 6px (cols 5..10) | **8px (cols 4..11)** |
| eye box | 2px each | **3px each** |
| nose gap | 2px | 2px (cols 7,8) |

Left eye = cols 4,5,6. Right eye = cols 9,10,11. Nose = cols 7,8. 3+2+3 = 8, and
that is the entire reason the face is 8 wide rather than 6.

**How a pupil fits in 2px: it does not.** A 2px eye is one sclera pixel and one
pupil pixel, and at 1x the pair reads as a single smudge — that is precisely the
blob that ships today. The minimum that reads as an eye is **3px: two sclera
(`w`) plus one pupil (`o`)**, pupil inboard. Widening the face from 6 to 8 is not
a style preference; it is the smallest change that buys a third eye column.

**The cost, stated before anyone starts.** Widening the head from 10px to 12px
invalidates every strip authored against the old skull. `HELM` (sprites.js:1451)
is authored to a 10px head in all four facings — `'....oMmmmmAo....'` is a
10-wide shell with its cheek flares at cols 2 and 13. All four facings x six
parts (shell, split, wire, seam, cheek, crest, plume, nasal, jaw) must be
re-authored against the 12px skull, and `HERO_BODY` rows 1..8 with them. This is
the single largest piece of work the face contract creates, and it is the reason
§C-2 is stated in columns rather than adjectives: the helm and the head must be
re-authored to the *same* numbers or the helm will float.

**Precedent, in this repo.** `PORTRAIT_EMOTE` at 24x24 already does exactly this:
a 10-column face with the left eye at columns 0-2 and the right at 7-9
(sprites.js:3959-3961). The portrait reads. The field sprite is the one rig that
never got the third column.

**Colour cost: zero.** Sclera is `w` (specular, already paid), pupil is `o`
(outline — `pal.e` is already aliased to it at sprites.js:2143), brow is `h`
(hair). No new entry, and the budget is full.

### C-2b. The box that AUTHORS and the box that RENDERS are two different boxes

The columns above are where the skin is. They are not all reachable. Measured by
flipping one authored cell at a time, re-rendering in a fresh module instance and
counting changed pixels, what actually survives to the screen is:

| table | rows | live columns | what eats the rest |
|---|---|---|---|
| front | 0..2 | 4..11 | the low-left rim takes col 3 |
| front | 3..4 | **4..10** | the blade crosses cols 11..13 there |
| profile | 0 | 4..7 | the rim takes col 3 on the LEFT facing |
| profile | 1..2 | 3..7 | the rim takes col 1 (left) / col 2 (right) |
| profile | 3..4 | **4..7** | the rim takes col 3 on the RIGHT facing |

Brows are hair-coloured, so a brow cell landing on the hair rather than the skin
is invisible even where the probe calls the cell live: front cols 3 and 12 and
profile col 8 are hair on rows 0..1. **Keep brows inside the skin.**

Eighteen of the six hundred and four authored face cells were outside these
windows and had been counted as art by the harness for a whole pass. Two were
doing real damage: `alarmed`'s outer lower sclera sat at front col 11 under the
blade, so the ten-cell eye the report described rendered nine; and the
`delighted` profile spent one of its four blink cells on the head's own outline
column, so that blink rendered three pixels against a law asking for four.

The `right` profile is a **frozen mirror** built at module load
(`HERO_FACE_PROFILE_R`), and the right body is authored separately from the left,
so the two facings lose different columns. A profile emote has to be measured on
both.

### C-2c. What a pupil is, for the purpose of counting one

**A dark cell with a sclera cell beside it IN THE SAME ROW.** Counted any other
way — "an `o` anywhere in the eye rows" — a solid black eyelid scores as pupils,
which is exactly how `HERO_FACE_FRONT.defeated` shipped with no eyeball anywhere
in it under a green line reading `defeated sclera 4 pupil 6`. `strained` and
`delighted` are shut by design and exempt; every other emote must have one.

## C-3. The row budget

Five rows, stamped at body `y = 4`, unchanged from today:

```
r0   hairline / upper brow shadow
r1   BROW        <- carries the emotion
r2   EYE
r3   LOWER LID / CHEEK
r4   MOUTH
```

The brow does the work. At eight pixels a mouth has about two shapes in it; a
brow is three pixels and it can move a whole row. This principle was already
right in the source and is kept verbatim.

## C-4. The separation law

**THE LAW IS COUNTED IN PIXELS, NOT IN CELLS.** It used to be counted on the
authored strip, which is how eighteen cells that never reached the screen were
scored as art, how three profile blinks passed at three rendered pixels against a
four-pixel law, and how a front median printed as 22 was 17 on the frame. Laws 1
and 3 are measured off `heroFrame()` now, in the face band (rig rows 4..8), on
**all three facings** — `right` is a separate frozen mirror and has to be
measured, not assumed.

1. **Every pair of emotes must differ by ≥ 10 px (front) and ≥ 9 px (profile).**
   The profile bar is the front's floor, not half of it: the profile is the face
   a FIGHT shows (`heroSprites().side` is `right`), so it is the one that has to
   survive being looked at.
2. **Every pair must differ on at least TWO of the three channels** (brow, eye,
   mouth). One channel is not a different emotion, it is the same emotion with
   an accessory. Counted on the strip, because that is where a channel exists.
3. **Frame 0 vs frame 2 of one emote must differ by ≥ 4 px, on every facing.**
   A blink is an event.
4. No two emotes may share the same (brow, eye, mouth) token triple.
5. **Every open emote carries a pupil with sclera beside it in the same row**
   (§C-2c), and no authored cell falls outside the live window (§C-2b).

## C-5. The per-emote table

Channel tokens, all seven distinct on ≥ 2 of 3:

| emote | brow | eye | mouth |
|---|---|---|---|
| neutral | flat, 3px over each eye | open: 2 sclera + pupil inboard | 2px dot, centred |
| pleased | raised, broken arc | open, soft | 6px arc, white teeth |
| strained | inner ends driven DOWN into the eye | squeezed shut, 3px solid | 4px grimace bar |
| alarmed | high and clear of the eye, 3px each | wide, 4px sclera, no lid | 2px dot, dropped |
| stubborn | one unbroken 8px bar, pressed flat | narrowed, pupil outboard | 8px flat line, full width |
| delighted | high broken arc, 2px each | closed, upward arcs | 6px open grin, teeth |
| defeated | inner ends lifted (sad), 1px each | half-lidded, 3px lid over pupil | 2px split frown |

The authored strips (16 cols; `h` brow, `w` sclera, `o` pupil/outline, `.` skin):

```
neutral      ................    pleased      ....h......h....
             ....hhh..hhh....                 ...hh.h..h.hh...
             ....wwo..oww....                 ....wwo..oww....
             ................                 ................
             .......oo.......                 .....owwwwo.....

strained     ................    alarmed      ...hhh....hhh...
             ....hho..ohh....                 ................
             ....ooo..ooo....                 ....wwww.wwww...
             ....w......w....                 ....wow..wow....
             ......oooo......                 .......oo.......

stubborn     ................    delighted    ...h.h....h.h...
             ....hhhhhhhh....                 ....o.o..o.o....
             ....oww..wwo....                 .....oo..oo.....
             ................                 ................
             ....oooooooo....                 ...oowwwwwwoo...

defeated     ................
             .....h....h.....
             ....hh....hh....
             ....ooo..ooo....
             ......o..o......
```

**This table is verified, not asserted, and the authored strips live in
`sprites.js` rather than being restated here** — a second copy of a table is a
second opinion about it. What this document keeps is the MEASUREMENT, taken off
the raster by `scripts/verify/faces.mjs`:

| pixels in the face band | before this pass | shipped |
|---|---|---|
| front, minimum pair | 9 | **10** |
| front, median | 17 | **19** |
| left profile, minimum pair | 7 | **9** |
| right profile, minimum pair | **6** | **9** |
| profile median | 10 / 11 | **12** |
| worst blink, front | 4 | 4 |
| worst blink, left profile | **3** (delighted) | **4** |
| worst blink, right profile | **3** (alarmed, delighted) | **4** |
| open emotes with a real pupil, front | 4 of 5 | **5 of 5** |
| open emotes with a real pupil, profile | 3 of 5 | **5 of 5** |

`delighted` vs `defeated` — the pair the player named — is 23 px front and 13 px
profile, rank 4 of 21 on every facing.

**Profile faces** carry one eye and a jaw, authored for `left` and mirrored for
`right`. The head is a true mirror between the side views; the torso is not,
which is why `HERO_BODY` stays authored per facing and the face does not. The eye
is TWO rows — sclera across row 2, pupil low in row 3 — which is what buys both
the pupil and the separation inside a box that is only four or five live columns
wide.

**The direction question, answered rather than dodged.** `fx.js` draws the
battle hero from `heroSprites().side`, and `heroSprites` sets `side = right`, so
the profile is the only face a fight shows and the strong front face is reachable
only on the overworld. The alternative was to draw the battle hero front-on. It
is refused: he would face the camera while fighting something to his right, which
is a bigger lie than a face two pixels short. The profile was re-authored to
clear the front's floor instead.

---

# §D. THE GEAR CONTRACT

## D-1. The failure is the API, not the art

Gear visibility was reported as broken: "there is no helm on the head at all."
**Measured, the art is fine and the call was wrong.**

`heroArmor()` (sprites.js:1273) reads gear from exactly two shapes:

```js
opts._pieces / opts.pieces   // [{piece:'helmet', at:100}, ...]
opts.armor   / opts.armour   // {helmet:100, chestplate:100, ...}
```

Piece names must be drawn from `HERO_ARMOR_PIECES` (sprites.js:1253):
`helmet, chestplate, gauntlets, boots, shield, legendary`.

Anything else is **silently ignored** and returns `BARE_ARMOR` — every slot
`-1`, `any:false`. A harness passing `{helm:'helm', chest:'plate', boots:'boots'}`
renders a naked hero and reports no error. That is what produced the baseline
sheet: `helmet:-1` on every frame.

Driven correctly at tier 4, the same rig renders a helm shell, a gold crest and
plume, a nasal bar, cheek guards, pauldrons, boots and a shield — head pixel
count rises 65 → 76 and the head goes from 8 colours to 10.

> **Contract:** gear is `{piece, at}` where `piece ∈ HERO_ARMOR_PIECES` and `at`
> is an integrity 0..100. `-1` means *not worn*, which is a different thing from
> tier 0, *worn and in pieces*. Any renderer or harness that invents its own key
> names is the bug.

Tiers snap on `ARMOR_AT = [0, 25, 50, 75, 100]` — five rungs, `HERO_ARMOR_TIERS`.

## D-2. Where each slot sits, and what it must change

A tier-up that changes only a colour is a number in a menu. Every rung must
change the **outline**.

| slot | rows (16x24 body) | what it must change | tier ladder |
|---|---|---|---|
| **helmet** | shell r2..r4; crest r1; plume r0..r1; nasal r5..r7; cheek r5..r7 | the head's *silhouette* | 0 notched crown, 1 wire binding closes the crown, 2 seam + cheek guards, 3 crest + nasal, 4 plume clears the box |
| **chestplate** | r9..r13, pauldrons at the box edge | the *shoulder width* | 0 none, 1 stub, 2 full cap to the box edge, 3-4 gold lip |
| **cloak** | r9..r17 + hem r18+ | three tones and a rim (§3) | material, not tiered |
| **boots** | r18..r23 | the *foot* mass and the stride | leather → plate, sole parting at tier 0 |
| **weapon** | 6x12 box at `WEAPON_ANCHOR` | the held *object* | 6 rungs x 10 families, all authored |
| **shield** | off arm, spliced per facing | a real *edge* on the off side | small → kite → aegis (shoulder to knee) |

**How a helm reads on a head 10px wide.** Not by covering it. The cheek guards
flare *past* the skull to columns 2 and 13 — wider than the head itself. That is
the one move available at this size that makes the head a **different shape**
rather than a different colour, and it is why the helm reads at 1x.

**The visor stops at the brow, always.** Seven emotes times two frames are
authored into the face; a full visor is a better helmet and a dead character. The
top tier gets a T-visor — nasal bar and cheeks — and the eyes stay in the fight.

## D-3. How gear survives 15 colours

Armour brings **no colours of its own**. It is paid for by the materials it
covers: a helm hides the hair's lit edge, a backplate hides the lit back of the
cloak, a breastplate hides the tunic's lit panel. So when `gear.any`:

```
H -> h     C -> c     T -> t     L -> c        (three slots freed)
A = metal.shadow1      m = metal.base      b = boot leather
```

Fifteen either way, and `scripts/verify/hero.mjs` counts it from the raster
rather than trusting the table.

**One defect to fix while here.** That collapse sets `pal.C = pal.c`, which
removes the cloak's light tone *whenever armour is worn*. Combined with the flat
cloak measured in §3, an armoured hero has a single-tone torso. **The cloak must
keep three tones in both states** — armoured and bare. It has the entries; §3
shows it is spending zero of them.

---

# §E. THE CLASS CONTRACT

## E-1. Where the classes already exist

`gauntlet/classes.py` is authoritative. Six classes, each with an id, a colour, a
starter weapon, a signature weapon — and already a `sprite` field
(classes.py:359), exposed through `to_dict()` (classes.py:2204).

| id | name | epithet | colour | starter | signature | weapon family |
|---|---|---|---|---|---|---|
| `analyst` | The Analyst | Reads the water before wading in | `#7ec8ff` | `matrix_bow` | `analysts_calipers` | calipers |
| `berserker` | The Berserker | The first draft is a weapon | `#ff6a7a` | `twin_sabers` | `draft_axe` | axe |
| `archivist` | The Archivist | Nothing is learned once | `#a89aff` | `hashblade` | `recall_chain` | chain |
| `warden` | The Warden | Name what breaks it, then write it | `#8fd07a` | `testsmith_shield` | `boundary_maul` | hammer |
| `artificer` | The Artificer | Build it once, properly | `#e8c37d` | `dynamic_relic` | `toolwrights_spanner` | spanner |
| `seer` | The Seer | The bug is already on the screen | `#c8a8ff` | `debuggers_lens` | `tracing_needle` | dagger |

**Two gaps, stated plainly.** `web/js/sprites.js` contains no reference to
`class_id` or `sprite` — all six classes render the identical hero today. And
there is no gender, sex or body-type concept **anywhere** in the repository. The
twelve sprites are greenfield and need a selector; this contract specifies
`{ class_id, body }` with `body ∈ {'a','b'}`, carried on the same `opts` dict
`heroOpts()` already threads.

> **THE THIRD GAP, FOUND AFTERWARDS, AND IT WAS THE ONE THAT MATTERED.**
> `CLASS_RIG` landed and the classes still all rendered the same hero, because
> `engine.py:_hero_look()` — the ONLY sprite-options dict the client ever draws
> the hero from — never put the chosen class on it. `classKey()` reads
> `opts.class_id || opts.sprite`; the payload carried neither, so it returned ''
> and `CLASS_RIG` was never applied. Proved on the live app: `/api/state` hero
> keys were exactly `[boot, metal, trim, tunic, weapon, _weapon, _pieces,
> _gear]`, and after `POST /api/class/choose` the rendered frame was
> byte-identical to the classless hero. The fix is three lines in
> `_hero_look()`; no translation table is needed, because the six
> `CharacterClass.sprite` values are byte-identical to the six ids and to
> `HERO_CLASSES`.
>
> **The body axis is still unreachable and is NOT bodged.** No gender, sex, body
> or body_type field exists anywhere in `gauntlet/` or `web/`, so `bodyKey()`
> always returns `'a'` and six of the twelve sprites cannot be reached. That
> needs a stored field and a character-creation control, and it is a separate
> piece of work.

## E-2. The law

> A player must tell a Berserker from a Seer **with the colour switched off.**

Every class is specified as four things: **silhouette** (the shape at 1x, greyed),
**ramp** (which material dominates), **prop** (the signature object), and **the
tell** (the one feature that survives desaturation). No two classes may share a
silhouette class *and* a prop class.

The shared rig is unchanged: 16x24, head 8 rows, the §C face, the §D gear
anchors. What varies is the outline.

| class | silhouette | ramp | prop | the tell, colour off |
|---|---|---|---|---|
| **Analyst** | narrowest. Straight vertical shoulders, no flare. A 2px antenna-thin rod line above the head | cool steel + glass | calipers, held **open** across the chest | the only class whose outline is a plain rectangle — nothing projects sideways |
| **Berserker** | widest shoulders in the set, 14px, torso tapering hard to the waist. Head sits low, no neck | hide + raw iron | twin sabers, crossed **behind** the shoulders so both blades break the outline at the top corners | two blade tips above the shoulder line — the only upward double-break |
| **Archivist** | tall and narrow, floor-length hem that widens below the knee (a bell) | parchment + dull brass | a chain that hangs from the belt and **swings past the hem** | the hem bell plus a pendant chain crossing it — bottom-heavy |
| **Warden** | squarest. A shield fills the off side from shoulder to knee, so the silhouette is half figure, half slab | plate + oak | tower shield, always presented, never stowed | one straight vertical edge down the whole off side — no other class has a flat side |
| **Artificer** | asymmetric on purpose. One shoulder carries a tool rack that projects 3px; the other is bare | brass + leather + copper | spanner at the hip, rack of three tool stubs on the pack | the only lopsided outline — left and right shoulders differ by 3px |
| **Seer** | hooded. The head silhouette is a **point**, not a dome, and the hood's peak adds 2 rows above the skull | deep cloth + violet glass | a lens on a cord, held at eye height when casting | the pointed hood — the only class whose head is not a dome |

Silhouette classes used: rectangle (Analyst), inverted triangle (Berserker), bell
(Archivist), slab (Warden), asymmetric (Artificer), point (Seer). Six shapes, six
classes, no repeats — which is what makes the greyscale test pass.

### E-2b. Measured on the sprite the game DRAWS, which is a dressed one

`engine.py` starts every armour piece at integrity 100, so the player is in a
full kit from the first frame of a new save. A class tell measured on a bare,
unarmoured, weaponless hero is a class tell measured on a figure the game never
draws — and `scripts/verify/classes.mjs` was doing exactly that, through
`heroSilhouette()`, a second code path with its own layer offsets. It reported a
cross-class minimum of 56 while the shipped frames had the **Warden at ZERO cells
from the classless hero**: its tower slab sat precisely on the box
`shieldGrid()` already fills at `SHIELD_SIDE[dir].ox`.

The law is now: **every class pair differs by ≥ 8 alpha cells of 384 in its WORST
of 28 views, dressed** (four facings x four walk frames + two idle + one cast),
and **no rig may break into more than one 8-connected island in any view.**
Worst-view distances against the classless dressed hero:

| class | before | shipped | what changed |
|---|---|---|---|
| analyst | 9 | **11** | the rod moved off cols 6..9 (100% under the helm crest) and grew a second row to bridge the idle-0 head sink |
| berserker | 10 | 10 | unchanged |
| archivist | 27 | 27 | unchanged |
| warden | **0** | **11** | the tower now runs above the aegis to head height and below it to the ground, narrow at the top so it never crosses the face box |
| artificer | 16 | 16 | unchanged |
| seer | **1** | **10** | crown two columns proud of the crest, a brim at cols 0..1/14..15, and a robe hem closing the leg gap |

Cross-class worst pair: **0 → 10**. Broken silhouettes across all 28 views of all
14 rigs, dressed and bare: **6/28 for every body-b rig and 4/28 for the analyst →
0**.

Two lessons worth keeping. **Air is the scarce resource, not colour.** The
dressed rig fills rows 9..19 edge to edge, so a class tell can only land in the
air at rows 0..8 (the head corners), rows 20..23 (the leg gap) or wherever it
ERASES. **Two classes must not spend the same air pocket** — the first seer
rewrite put its mantle on rows 4..8 of cols 0..1 and 14..15, which is exactly
where the berserker's blade tips stand, and berserker-vs-seer collapsed from 9
cells to 1.

## E-3. The two bodies

Twelve sprites, not six. Body `a` and body `b` share the head rig, the face
table, every gear anchor and the palette. They differ **only** in the torso and
hem grids:

| | body a | body b |
|---|---|---|
| shoulder line | 14px | 12px |
| waist | 10px | 8px |
| hem flare | +0 | +2px below the knee |
| head | shared, identical | shared, identical |

That is a two-grid difference per class, not a second character. The face, gear
and emote contracts are untouched by it — which is the point, because twelve
sprites that each re-author a face is twelve chances to break §C.

**Two rules the first implementation broke, both worth stating.**

*An erase takes the OUTER column.* The shoulder narrowing was authored as
`.xo..........ox.` — ERASE at cols 1 and 14 with the new outline at 2 and 13 —
which cuts the middle of the arm and leaves its outermost column standing.
Counted on the dressed rig, `down/walk0` row 10 came out `#.############.#`: a
one-pixel vertical sliver at col 0 and another at col 15, each separated from the
torso by a one-pixel hole and joined to the body only at row 13. It is
`xxo..........oxx` now.

*A hem flare is CONDITIONAL.* Three unconditional rows of `.oc..........co.` are
right on a facing whose legs stand under cols 1..14 and wrong on a side-facing
stride, where the leg grid is somewhere else and the flare lands on air — a
detached 2x3 block beside the foot on six of twenty-eight views, for every body-b
rig including the classless hero. `MANTLE` and `CLOAK` solve this by being
authored per facing; the hem solves it by asking the grid, painting each flare
cell from the inside out only where the cell one step toward the centre is
already filled. There is no "only if touching" glyph, which is why this is a rule
in `classShape()` rather than a row in a table.

---

# §F. THE MIGRATION LIST

Every constant that hard-codes a size, where it lives, and what moving it costs.

## F-1. The stage raster — BREAKING, and the whole point

| constant | file:line | today | new |
|---|---|---|---|
| `STAGE_LOGICAL` | `web/js/main.js:423` | `{w:192, h:128}` | `{w:256, h:224}` + `{fitH:176}` |
| `STAGE.w/h` | `web/js/fx.js:30-31` | 192 / 128 | 256 / 224 |
| `SCENE_STAGE` | `web/js/battlescene.js:57-60` | duplicate of the above | must move together |

**These are two independent copies of the same geometry.** `fx.js:30` and
`battlescene.js:57` each declare `w/h/ground/heroX/enemyX`. Changing one and not
the other desynchronises the stage from the scene painter. They move in one
commit or not at all.

`fitBattleStage()` must additionally fit **176**, not 224 (§A-3): the `176`
appears in `artMaxH`, in the `px` divisor and in `boxH`, while the canvas is
sized 256x224.

## F-2. Stage anchors — BREAKING

| constant | file:line | today | new |
|---|---|---|---|
| `STAGE.ground` | `fx.js:32`, `battlescene.js:57` | 100 | **175** |
| `STAGE.heroX` | `fx.js:33`, `battlescene.js:58` | 46 | **64** |
| `STAGE.enemyX` | `fx.js:34`, `battlescene.js:59` | 136 | **184** |

`bosses.js:3430` reasons about `STAGE.enemyX = 136` **in a comment and in a 1.75
scale factor** to place the 64-box. It must be re-derived against 184, not
find-replaced.

Also keyed to the old geometry: `battlescene.js:1522 PLATFORM_TOP = 12`,
`1981 APRON_OFF = 20`, `1982 APRON_LIFT = 2`, `bossart.js:173 ART_GROUND = 62`.

## F-3. Sprite sizes — NON-BREAKING (they already match §B)

| constant | file:line | value | verdict |
|---|---|---|---|
| `HERO_W` / `HERO_H` | `sprites.js:476-477` | 16 / 24 | correct, **do not change** |
| `ENEMY_SIZE` | `sprites.js:2922` | 24 | correct |
| `MON_SIZE` | `monsterart.js:168` | 24 | correct |
| `APEX_SIZE` | `monsterart.js:173` | 32 | correct (elite rung) |
| `APEX_SIZE` | `apex.js:751` | 48 | correct (apex rung) |
| `BOSS_W/H` | `bosses.js:97-98` | 64 | correct |
| `BOSS_WIDE_W` | `bosses.js:99` | 96 | correct |
| `ART_W/H`, `ART_WIDE_W` | `bossart.js:168-170` | 64, 96 | correct |
| `PET_W/H` | `petart.js:112-113` | 16 | correct |
| `TILE` | `apex.js:57`, `kingui.js:101` | 16 | correct |

**Two `APEX_SIZE` constants exist with different values** (32 in `monsterart.js`,
48 in `apex.js`). They are different rungs and both are right; the collision is
in the *name*. Renaming is cosmetic and non-breaking within each module, but any
agent importing "APEX_SIZE" must say which.

## F-4. The boss-size drift — DECIDE, then BREAKING

`sprites.js:3645 BOSS_SIZE = 48` is used at exactly one site
(`sprites.js:3700`). It is the apex rung under a boss name, while the real boss
rig is 64 in `bosses.js`/`bossart.js`. Either rename it to `APEX_SIZE` or route
that call at the 64 rig — but the spec must stop claiming a "48x64" that exists
nowhere.

## F-4b. The head widening — BREAKING for every helm strip

§C-2 widens the skull 10px → 12px. `HELM` (`sprites.js:1451`) and `HERO_BODY`
(`sprites.js:479`) are both authored against the 10px head, in four facings.
Re-author them together, in one commit, or the helm floats off the skull.

## F-5. New constants §B requires

| constant | where | value |
|---|---|---|
| `BATTLE_HERO_W/H` | `sprites.js` | 24 / 32 |
| `FINAL_BOSS_W/H` | `bosses.js` | 96 / 128 |
| `SAFE_H`, `SAFE_TOP` | `fx.js` | 176, 24 |

## F-6. Non-breaking, but keyed to the raster

`battlescene.js:64 PAD = 16` and the map rigs
(`bosses.js:106-108 BOSS_MAP_W/H = 48, BOSS_MAP_WIDE_W = 72`) are drawn on the
overworld, not the battle stage, and do not move with §A.

## F-7. The one decision this document does NOT make

Rule 4 says party right, enemies left. `heroX:46 / enemyX:136` says the opposite,
and has for the life of the code.

Flipping it is **not** a constant swap. `fx.js:856` builds travel paths as
`x0 = STAGE.heroX + 4, x1 = STAGE.enemyX + 10`; `fx.js:664/681/794/813` default
effect origins to `enemyX`; `deathfx.js:193` pins `HERO_X`; every spell arc,
camera focus (`fx.js:772`) and knockback vector assumes the current handedness.
Flipping the sides means re-deriving all of it and re-verifying
`scripts/verify/determinism.mjs` and the spell harnesses.

The raster change already touches `heroX`/`enemyX`, so this is the cheapest
moment it will ever be. Both sets of numbers, so whoever decides has them:

| | keep current (party left) | flip to FFVI (party right) |
|---|---|---|
| party foot centre | x = 64 | x = 184 |
| enemy foot centre | x = 184 | x = 64 |

**Do not flip it silently as part of the raster migration.** It is a gameplay-
visible change to every effect trajectory in the game and it deserves its own
commit and its own verification pass.

---

# §H. THE FIELD, AND WHY IT IS NOT THE STAGE'S PROBLEM

§A moved the BATTLE raster onto 256x224 and left the field alone, on the
grounds that the two are different pictures. They are — but the field was the
last screen in the game not drawn on FF6's pixel scale, and it stayed that way
for a whole release because nobody had written its arithmetic down.

## H-1. What was wrong, measured

`tiles.js` has always used **TILE 16**, which is FF6's own terrain tile,
exactly. The tile was never the problem. `overworld.resize()` was:

```js
this.scale = Math.max(2, Math.min(4, Math.floor(Math.min(w / 340, h / 230))));
```

340 and 230 are not FF6's numbers and are not anything else's either. What they
produced, measured live at devicePixelRatio 1 with the field canvas read off the
laid-out page rather than guessed:

| window | field canvas | scale | tiles across | tiles down | hero |
|---|---|---|---|---|---|
| 1280x800  | 950x753   | **2x** | 29.69 | 23.53 | 32x48 |
| 1440x940  | 1110x893  | 3x | 23.13 | 18.60 | 48x72 |
| 1600x1000 | 1270x953  | 3x | 26.46 | 19.85 | 48x72 |
| 1920x1080 | 1590x1033 | 4x | 24.84 | 16.14 | 64x96 |
| *FF6 field* | *256x224* | *1x* | *16.00* | *14.00* | *16x24* |

A 1280x800 window showed **29.7 x 23.5 tiles** against FF6's 16 x 14 — better
than four times the field of view by area — with the hero 48 pixels tall in a
753-pixel frame. That is a strategy map with a walk cycle on it.

> **A NOTE ON HOW THIS WAS FIRST MIS-DIAGNOSED, because the mistake is
> instructive.** The brief this work started from reported the field at **scale
> 1**, showing 69.4 x 55.8 tiles. It was not. The number came from a playwright
> probe that computed `tilesAcross = canvas.width / 16` — dividing the backing
> store by the tile size and never reading `overworld.scale` at all. The field
> was at 3 on that window, not 1, and the hero was 72 pixels tall rather than
> 24. **The complaint was right and every number attached to it was wrong**, and
> the fix designed against those numbers would have been three times too strong.
> Read the property. `overworld.js` exports `fieldScale()` and `fieldView()` now
> so that nobody has to divide anything by hand again.

## H-2. The rule, and the axis it honours

FF6's field is **256x224 world pixels** — 16 tiles by 14. Our field canvas runs
**1.26:1 to 1.54:1**; FF6's screen is 8:7, which is 1.14:1. No integer scale
lands on 16 x 14 in both axes on a canvas that shape, so the rule has to say
which axis it is honouring, and the two candidates are not close:

- **Fit the WIDTH to 256.** At 1920x1080 the canvas is 1590 wide, so `s = 7` and
  the player sees **9.2 rows** — less than two thirds of FF6's vertical field.
  The frame closes over your head.
- **Fit the HEIGHT to 224.** The rows stay at FF6's fourteen at every size, and
  the extra monitor width buys extra COLUMNS, which is what a widescreen version
  of a 4:3 game should spend it on.

> **THE FIELD SCALE IS `round(viewH / 224)`**, floored by a column guard and
> clamped. Round, not floor — floor is what was there, and it is what let the
> view drift to twenty-three tiles across.

```js
const FF6_FIELD_H = 224;   // 14 tiles
const MIN_COLS = 12;       // never a corridor
fieldScale = clamp(min(round(viewH / 224), floor(viewW / (MIN_COLS * 16))), 2, 12)
```

## H-3. Every size, as adopted

| window | field canvas | scale | tile px | cols | rows | hero |
|---|---|---|---|---|---|---|
| 1280x800  | 950x753   | **3x** | 48 | 19.79 | 15.69 | 48x72 |
| 1440x940  | 1110x893  | **4x** | 64 | 17.34 | **13.95** | 64x96 |
| 1600x1000 | 1270x953  | **4x** | 64 | 19.84 | 14.89 | 64x96 |
| 1920x1080 | 1590x1033 | **5x** | 80 | 19.88 | 12.91 | 80x120 |
| *FF6 field* | *256x224* | *1x* | *16* | *16.00* | *14.00* | *16x24* |

Rows land between 12.91 and 15.69 against FF6's 14 — inside two rows at every
size, and the launcher's own window lands on 13.95. Columns run 17.3 to 19.9;
they are **not** held to sixteen and must not be, because the aspect ratio is
the only thing paying for them.

`SCALE_MIN` is **2** and that is not a retreat. Two is the scale 1280x800 was
shipping at, and it is fixed by the height rule asking for 3 there, not by a
floor. A floor of 3 wins against `MIN_COLS` on a 480-wide frame and quietly
hands back ten columns — measured, before it was lowered. `SCALE_MAX` is **12**
for the mirror-image reason: at 8, a 5120x2880 canvas goes straight back to
forty tiles across, and a cap low enough to bite is a cap that reintroduces the
bug on a bigger monitor.

## H-4. What the zoom moved, and what it did not

Raising `s` multiplies everything drawn inside the camera transform and nothing
drawn outside it. Every layer was checked either way; the list is in
`scripts/verify/field.mjs`. Two things were actually wrong:

1. **The King's panel printed across the hero at any map edge.** `kingui.js`
   computed its ceiling as `viewH / 2 + (8 - 24) * scale` — where the hero is
   only while the camera is FREE. At the north edge the camera clamps, the hero
   is 24 to 40 pixels down the frame, and `PANEL_TOP` is 28. Older than the
   zoom; found because raising the scale made the clamped band worth measuring.
   The panel now takes the hero's measured top and, when there is no room above
   his head, prints **below his feet** instead.
2. **The chevron over his head was on a half pixel.** `fillRect(p.px + 6, ...)`
   with a float `p.px` and a float bob — the only primitive in the world layer
   not landing on a whole world pixel, in a layer where the sprite beside it is
   at `Math.round(p.px)`. `imageSmoothingEnabled` does not reach a `fillRect`,
   so it was 4x2 fuzzy pixels at scale 2 and would have been 20x10 at scale 5.

And one latent one, fixed on the way past: the camera clamp `max(0, min(worldW -
spanX, ...))` pins to 0 and shows void when the view is wider than the map. It
cannot happen at these four sizes and is one window-drag away at `SCALE_MIN`.

## H-5. The terrain already has the tones

The obvious next move after a zoom is to deepen the art, and the measurement
says not to. Distinct colours in the base 16x16 ground tile, per biome, counted
off the rendered canvas:

| biome | ground | path | stone | sand | ground luminance span |
|---|---|---|---|---|---|
| wastes | 7 | 7 | 6 | 5 | 106 |
| ruins | 7 | 7 | 4 | 5 | 149 |
| forest | 7 | 7 | 5 | 5 | 123 |
| swamp | 7 | 7 | 5 | 5 | 191 |
| mountain | **5** | 7 | 5 | 5 | **24** |

§3 asks for three tones. Every tile has four to seven, over a luminance span
of a third to three quarters of the range. The tones are there; what the zoom
changed is that they are now legible **as grain** rather than averaging into a
texture. Whether that grain should become structure is an art-direction
decision, not a defect, and it is not made here.

The one measured flat spot is **mountain ground: five colours over a luminance
span of 24** (231..255 — snow). At 80-pixel tiles that is a large near-uniform
white. It is left alone deliberately: §1 says there is no headroom, so
deepening it means taking range from something else, and that trade has to be
made on purpose.

# §G. HOW EACH CONTRACT IS PROVED

No contract here is satisfied because the code stopped throwing. Each has a
measurement:

**A measurement taken on the wrong figure is not a measurement.** Three of the
proofs below were rewritten because they scored something the player never sees:
the face laws scored authored text instead of pixels, the class law scored a bare
hero through a code path the game does not use, and the death harness built its
hero box out of the same constant the drawing code had wrong, so harness and
drawing shared the error. Every row now names the thing it actually renders.

| contract | proof |
|---|---|
| §A raster | `scripts/verify/stage.mjs` §4 — drive a real encounter at all six window sizes; assert integer `px` and `editor >= MAIN_MIN` per the §A-5 table |
| §A safe area | `stage.mjs` §3 — switch each readout on one at a time and assert every pixel it changed lands in rows 24..199 |
| §A budget | count the rows that reach the canvas at each size; quote DELIVERED pixels, never authored ones (§A-1) |
| §B ladder | `stage.mjs` §2 — assert every sprite constant is a multiple of 8 |
| §B blit | `stage.mjs` §5 — assert `blit * px` is whole at px 1..6 for every figure, and that every painted box stays in frame (§B-2) |
| §C face | `scripts/verify/faces.mjs` — diff `heroFrame()` PIXELS pairwise on all three facings; assert min 10 front / 9 profile, frame delta >= 4 everywhere |
| §C eyes | count sclera and pupils inside the eye box; a pupil is a dark cell with sclera beside it IN THE SAME ROW (§C-2c) |
| §C window | assert no authored face cell falls outside the live window (§C-2b) |
| §3 tones | count `c`/`C`/`v` cells per facing; assert all three non-zero |
| §D gear | render each slot at each tier and assert the **outline** changed, not just colour |
| §D budget | `scripts/verify/hero.mjs` — worst frame <= 15 colours |
| §E classes | `scripts/verify/classes.mjs` — greyscale all fourteen rigs through `heroFrame()` on the DEFAULT KIT, 28 views each; assert the worst pair >= 8 cells and that nothing breaks into islands (§E-2b) |
| death screen | `scripts/verify/death.mjs` — assert the words reach the FRAME after `WORDS_AT`, that changing a number in the report moves pixels, and that removing the kept line costs painted pixels |
| weather | `scripts/verify/weather.mjs` — field counts scale with the frame area, so a raster move cannot silently thin a storm |
| §H field scale | `scripts/verify/field.mjs` A — assert an integer scale at all four window sizes and the visible rows within two of FF6's fourteen |
| §H camera | `field.mjs` B — 1360 walked frames per window; assert no void, the player centred whenever the clamp is not biting, and no frame-to-frame jump larger than the walk speed |
| §H panel | `field.mjs` C — the King's words and the hero as two rectangles, at every scale, with the camera clamped at both map edges; assert they do not intersect |
| §H lattice | `field.mjs` D — wrap the context for a drawn frame and assert every world-layer `fillRect`/`drawImage` coordinate is a whole world pixel |
| §H storm | `field.mjs` E2 — count the particles inside the visible rect and the screen area they paint; assert the zoom does not thin the field's weather |
| all | `scripts/verify/determinism.mjs` — no `Math.random()` in a draw path |


## Applying it

- `web/js/palette.js` — the shared ramp system and the 15-colour audit
- `web/js/sprites.js` — characters, the face table (§C), the gear rig (§D)
- `web/js/main.js` — `fitBattleStage()` and `STAGE_LOGICAL` (§A)
- `web/js/fx.js` — `STAGE` geometry: raster, ground line, foot anchors (§A-6)
- `web/js/battlescene.js` — layered stages, and the **second** copy of `STAGE` (§F-1)
- `web/js/monsterart.js`, `web/js/apex.js` — the monster/elite/apex rungs (§B)
- `web/js/bosses.js`, `web/js/bossart.js` — boss art, the 64 and 96 rungs (§B)
- `web/js/tiles.js` — terrain and autotiling
- `web/js/overworld.js` — `fieldScale()`, `fieldView()` and the field camera (§H)
- `web/js/spellfx.js` — spell effects, all keyed to `heroX`/`enemyX` (§F-7)
- `web/js/lootart.js` — item art by rarity, and the per-class weapon families (§E)
- `gauntlet/classes.py` — the six classes, authoritative (§E-1)
- `web/css/metal.css` — the UI skin

## Sources

- [SNESdev Wiki — Sprites](https://snes.nesdev.org/wiki/Sprites)
- [Megacat Studios — SNES Sprite Engine Design Guidelines](https://megacatstudios.com/blogs/retro-development/snes-sprite-engine-design-guidelines)
- [Fortress of Doors — Doing an HD Remake the Right Way: FFVI Edition](https://www.fortressofdoors.com/doing-an-hd-remake-the-right-way-ffvi-edition/)
- [Game Developer — Doing an HD Remake the Right Way: FFVI Edition](https://www.gamedeveloper.com/business/doing-an-hd-remake-the-right-way-ffvi-edition)
- [Final Fantasy Wiki — Final Fantasy VI battle system](https://finalfantasy.fandom.com/wiki/Final_Fantasy_VI_battle_system)
- [Wikipedia — Active Time Battle](https://en.wikipedia.org/wiki/Active_Time_Battle)
- [Nesdev forums — consolidated pixel-artist info for SNES](https://forums.nesdev.org/viewtopic.php?t=15953)
