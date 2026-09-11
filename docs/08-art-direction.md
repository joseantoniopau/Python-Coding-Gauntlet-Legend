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

## The rules we adopted

### 1. Fifteen colours, and they are a ramp

Every sprite is authored against a palette of at most 15 colours plus
transparency. Those colours are not arbitrary: they are organised as **material
ramps** of 3–5 steps (shadow, mid, light, specular) shared between sprites, which
is what makes a scene look like one object family rather than a sticker book.

`web/js/palette.js` enforces this. A sprite that exceeds the budget is a bug, and
`auditPalette()` will say so.

### 2. One pixel grid, everywhere

16x16 terrain, 16x24 characters, 24x24 enemies, 48x64 bosses — every one an
integer multiple of the same grid, scaled by integers only. Nothing is drawn at a
fractional scale, and no UI element sits on a half-pixel. This is the mosaic
effect, and it is the cheapest coherence available to us.

### 3. Hard outline, three tones, one rim

Every sprite gets a near-black outline, a minimum of three body tones, a lit edge
on the upper left, and a single rim light in the creature's own colour so it
separates from a dark stage. This is the shading discipline FFVI's sprite work
runs on and it is what stops procedural art reading as flat.

### 4. Enemies left, party right

The battle stage follows the convention: the player's side stands on the right,
the enemy on the left, the ground line is shared, and the command surface sits
below. We deviate in one way — our "party" is one Architect, because the fight is
against a problem rather than a monster.

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

## Applying it

- `web/js/palette.js` — the shared ramp system and the 15-colour audit
- `web/js/sprites.js` — characters and enemies
- `web/js/bosses.js` — boss art
- `web/js/tiles.js` — terrain and autotiling
- `web/js/battlescene.js` — layered stages
- `web/js/spellfx.js` — spell effects
- `web/js/lootart.js` — item art by rarity
- `web/css/metal.css` — the UI skin

## Sources

- [SNESdev Wiki — Sprites](https://snes.nesdev.org/wiki/Sprites)
- [Megacat Studios — SNES Sprite Engine Design Guidelines](https://megacatstudios.com/blogs/retro-development/snes-sprite-engine-design-guidelines)
- [Fortress of Doors — Doing an HD Remake the Right Way: FFVI Edition](https://www.fortressofdoors.com/doing-an-hd-remake-the-right-way-ffvi-edition/)
- [Game Developer — Doing an HD Remake the Right Way: FFVI Edition](https://www.gamedeveloper.com/business/doing-an-hd-remake-the-right-way-ffvi-edition)
- [Final Fantasy Wiki — Final Fantasy VI battle system](https://finalfantasy.fandom.com/wiki/Final_Fantasy_VI_battle_system)
- [Wikipedia — Active Time Battle](https://en.wikipedia.org/wiki/Active_Time_Battle)
- [Nesdev forums — consolidated pixel-artist info for SNES](https://forums.nesdev.org/viewtopic.php?t=15953)
