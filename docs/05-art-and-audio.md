# Original Art and Audio

Everything here is generated at runtime from source authored for this project.
No third-party game assets, sprites, maps, music or sound effects are used, and
nothing is traced or sampled from an existing game.

## Why procedural

Shipping a 16-bit RPG normally means shipping megabytes of PNGs. Generating the
art from a small authored description instead means: the whole game is a few
hundred kilobytes of text, every region can be re-skinned by changing one palette
entry, and there is no asset-licensing question to answer.

## Sprites

Sprites are authored as **character grids with a per-sprite palette**, rasterised
into offscreen canvases and drawn with nearest-neighbour scaling, so they stay
crisp at integer scale on Retina displays.

```js
slime: [
  '.....oooooo.....',
  '...ooBBBBBBoo...',
  '..oBBBBBBBBBBo..',
  '.oBBwwBBBBwwBBo.',   // o outline · B body · w eye · d shadow
  ...
]
```

| Asset | Detail |
|---|---|
| **Hero** | 12×16, three facings (down/up/side, side mirrored), four-frame walk cycle produced by programmatic leg displacement |
| **Enemies** | Eight archetype silhouettes (slime, wisp, golem, wraith, hydra, dragon, construct, mimic) recoloured per algorithm family, giving 26 visually distinct enemies from eight authored shapes |
| **Bosses** | The same silhouettes at double resolution with an added crown/horn overlay, so a boss reads instantly as a bigger, angrier member of its family |
| **Portraits** | 12×12 mentor faces, seven archetypes |
| **Equipment icons** | 8×8, sixteen shapes, tinted by rarity |

## Tiles

16×16, generated per region from a palette of eight colours plus an explicit
foliage colour.

- **Ground** — four variants per region, speckled and tufted so a field never
  reads as flat colour
- **Water** — four animated frames driven by overlapping sine waves
- **Lava** — four frames, independent phase
- **Stone** — mortar lines with a per-tile random crack
- **Trees** — three variants, canopy built from scattered 2×2 clusters
- **Cliffs, paths, shrines, chests** — authored per palette
- **Buildings** — four tiers, so a village visibly rebuilds as fluency rises:
  boarded and roofless at tier 0, lit windows and warm roof tiles at tier 3

Sixteen palettes: dawn, spring, amber, verdant, stone, moss, slate, ember, royal,
dusk, ash, gold, iron, azure, sun, void.

## Environment

- **Particles** — embers, snow, rain, leaves, magical motes, ash; assigned per
  biome, with sinusoidal drift
- **Day/night** — a real clock tint, gentle at dusk, cooler after 21:00
- **Vignette** — a radial gradient, deliberately light so the pixel art stays readable
- **CRT** — optional scanlines at 10% opacity, defeatable in the menu
- **Region motifs** — each region draws the shape of its own algorithm across the
  terrain: a sliding frame in the Marsh, converging lanterns in the Pass,
  illuminating tiles in the Ruins, a recursive fractal in the Canopy, a node
  lattice in the Wastes, LIFO carts and FIFO lifts in the Mines, floors
  illuminating up the Complexity Tower

## Algorithm visualisations

Sixteen animated visualisers, each stepping through a real algorithm on a real
input with its live state labelled — the step that turns "I have heard of sliding
window" into "I can see what `left`, `right` and `counts` are doing".

sliding window · two pointers · BFS wave · DFS with visible backtracking · stack ·
queue · tree with inherited ranges · hash map vaults · recursion as nested rooms ·
DP tiles lighting from their predecessors · monotonic deque · binary search ·
prefix sums · matrix rotation · array scan.

Each exposes frame stepping, play and stop, with a caption per frame.

## Audio

Original chiptune, synthesised in the browser with the Web Audio API. No samples,
no external files.

Four voices, roughly the palette a 16-bit era composer had: two pulse leads with
variable duty cycle (0.25 for menace, 0.35 for driving, 0.5 otherwise), a
triangle bass, and a filtered noise channel for percussion. A low-pass at 7.2 kHz
takes the glassy edge off raw square waves.

Ten original tracks: town, overworld, dungeon, battle, boss, victory, training
camp, memory shrine, complexity tower, final castle.

**Adaptive intensity.** As a timed practical approaches expiry, `setIntensity()`
raises voice gain and adds a noise hit on the off-beat — the battle track tightens
as the clock runs down. Learning Mode never does this; stress-inducing audio has
no place in a teaching context.

Thirteen sound effects: hit, crit, fail, select, move, spell, level-up, victory,
shrine, unlock, armour repair, tick.

Everything is mutable from the menu.

## Accessibility

Text scaling 0.85×–1.5× · reduced motion (disables animation and transitions) ·
high contrast · colour-blind-safe status indicators (every colour cue is paired
with a glyph or a word) · full mute · keyboard-first navigation throughout ·
advisory-only timers in Adventure Mode.

Timed Practical Mode uses standardised constraints so the measurement stays comparable
between runs.
