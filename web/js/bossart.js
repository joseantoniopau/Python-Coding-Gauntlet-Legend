/* Boss art VOCABULARY: what a region looks like, and who each boss is.
 *
 * bosses.js is the STAGING — boxes, frames, beats, phases, caches, the draw
 * call, the entrance. This file is the THEME — what a fire boss is made of,
 * what a void boss does to the light, why the Hash Titan is not the Rolling
 * Titan wearing a different hex code. The two are separated because they change
 * for different reasons: staging changes when the battle screen changes, theme
 * changes when the world does.
 *
 * Nothing here is traced, sampled or derived from any existing game. Every grid,
 * profile and curve below was authored for this file. There are no image assets.
 *
 * ============================================================================
 * THE INTERFACE — what bosses.js may call, and what it is promised
 * ============================================================================
 *
 * Resolution. Never throws, never returns null, never silently claims to be a
 * boss it is not.
 *
 *   bossLook(idOrKey, opts?)    -> Look. Any string. A world.BOSSES id, a
 *                                  sprite key, an apex id, a region id, or
 *                                  nonsense. Nonsense gets a look that is
 *                                  plausible for its region and is flagged
 *                                  `fallback: true` with `resolvedFrom` saying
 *                                  what it actually was.
 *   lookFor(id)                 -> Look or null. The strict form, for callers
 *                                  that want to know whether an id is authored.
 *   apexFor(regionId)           -> Look. The region's apex.
 *   ingestHunters(rows)         -> number. gauntlet/hunters.py does not exist
 *                                  yet. When it lands, hand its rows to this
 *                                  and the seventeen apexes below take their
 *                                  ids, names and regions from it. Until then
 *                                  the authored roster stands on its own.
 *
 * Vocabulary, for bosses.js to run over its OWN authored creatures:
 *
 *   dressGrid(grid, look, opts) -> grid. The element pass. Adds or removes
 *                                  pixels at the silhouette in the way that
 *                                  element does it. Pure, deterministic in
 *                                  (look.id, element, frame, beat, phase, seed).
 *                                  Emits only glyphs already in ART_GLYPHS, so
 *                                  it can never cost a palette slot.
 *   motifsFor(look)             -> [{grid, ox, oy, slot, note}]. The identity
 *                                  stamps: the Hash Titan's keyring, the
 *                                  Wraith's empty frame, the Ent's single arm.
 *                                  Merge them with the body BEFORE lighting.
 *   elementPalette(pal, look, phase) -> a NEW palette dict. Overlays element
 *                                  materials onto bosses.bossPalette()'s
 *                                  output. Reassigns existing slots only —
 *                                  never adds a key — so the colour budget
 *                                  cannot grow from a theme pass.
 *   wantsRim(look)              -> bool. False for VOID. The one hot low-left
 *                                  rim is the law of this cast (docs/09 §8) and
 *                                  void is the one thing that refuses it, which
 *                                  is the whole reason void reads as absence.
 *   lookMotion(look)            -> {bob, sway, period, telegraph, anim, floats}
 *   lookLighting(look)          -> hex fields for the stage
 *
 * Self-contained rendering, for the things nobody else draws — the seventeen
 * apexes, the last interpreter, and any fallback:
 *
 *   lookSprite(look, opts)      -> a cached canvas, 64x64 (96x64 if wide)
 *   lookSilhouette(look, opts)  -> the readability check, colour discarded
 *   warmLook(look, phase)       -> build one phase's working set in one call
 *   clearBossArtCache(), bossArtStats()
 *
 * A named boss rendered through lookSprite() is a STUDY — the region body
 * wearing that boss's motifs. It is there so every look is renderable and
 * measurable. The creature the player fights is bosses.js's authored animal
 * with dressGrid() and motifsFor() run over it.
 *
 * ============================================================================
 * THE RULES THIS FILE IS HELD TO
 * ============================================================================
 *
 *  1. Fifteen colours plus transparent, counted off the RASTER with
 *     scripts/verify/raster.mjs, never off the palette dict.
 *  2. ART_GLYPHS only. It is the same table as bosses.BOSS_GLYPHS, asserted at
 *     module load. drawGrid skips an unknown glyph silently, which means a typo
 *     renders as a transparent hole and nobody finds out; so the set is closed
 *     and the harness checks every grid against it.
 *  3. No Math.random and no Date.now anywhere on a draw path. Every variation
 *     is rng(hash(authored string)).
 *  4. No per-frame allocation in a hot loop. One capped Map, oldest-out.
 *  5. Merge, then light, once — mergeGrids -> applyRim -> rimLowLeft, borrowed
 *     from sprites.js rather than reimplemented.
 *  6. Material ramps are shared. Bone and chrome come out of palette.RAMPS, so
 *     a boss's bone is the same bone as the armour's and the pets'.
 *
 * ============================================================================
 * A. THE SIX ELEMENTS, AS SIX DIFFERENT GEOMETRIC VERBS
 * ============================================================================
 *
 * gauntlet/elements.py gives every region an element, derived from its biome.
 * The temptation is to express that as six hues, and six hues is a recolour.
 * So each element is a different thing DONE TO THE SILHOUETTE — a different
 * verb, legible with the colour thrown away:
 *
 *   FIRE       SHEDS.      Tongues climb off the upper contour. Mass leaves
 *                          upward. The underside takes an ember bounce, so it
 *                          is the one element lit from below as well as beside.
 *   COLD       ACCRETES.   Straight 45-degree spurs grow out of the lower right
 *                          — away from the key light, where frost survives. The
 *                          lit edge takes rime. Nothing is organic; every angle
 *                          is the same angle.
 *   POISON     SAGS.       Pendant drops hang off the lower contour and the
 *                          highlights break into isolated wet points instead of
 *                          a continuous rim. Wet things highlight in dots.
 *   BRUTE      CHIPS.      The only element that REMOVES pixels. Bites out of
 *                          the right contour, re-outlined where the stone broke.
 *                          No glow of any kind: the contre-jour goes to near
 *                          outline, because rock does not emit.
 *   LIGHTNING  SPANS.      A filament leaps between two points of the contour,
 *                          arcing outside the body. It is the only element whose
 *                          decoration is not attached to the creature at one
 *                          end, and it strobes on the beat.
 *   VOID       SUBTRACTS.  Holes open in the interior, denser toward the core,
 *                          and the outline itself goes missing along the lower
 *                          left — exactly where every other creature in this
 *                          game is brightest. Void is the refusal of the rim.
 *   NEUTRAL    nothing.    Five regions are neutral on purpose (elements.py is
 *                          explicit about it). They are the control group, and
 *                          the control group does not get a treatment.
 *
 * ============================================================================
 * D. THE LAST INTERPRETER
 * ============================================================================
 *
 * docs/09 §5 and world.FINAL_TRIAL: a python at the scale where the room is a
 * consequence of the animal, which is also a wizard, and which speaks one
 * language. Four things are true of it and of nothing else in the game:
 *
 *   THE SCALES ARE INDENTATION. The coil's scale seams start at a margin four
 *     columns further in than the seam above, then four more, then four more,
 *     then return. An indent stack, made of snake. That is "speaks only in
 *     Python" argued in geometry rather than printed on a label. Phase two
 *     makes the indentation inconsistent — some rows out by one, which is a
 *     tab among spaces. Phase three collapses every row to the margin and the
 *     whole animal lights: the block ended.
 *   IT IS LIT FROM ITS OWN MOUTH. Every other character in this cast takes one
 *     hot rim from a low left source and that agreement is most of why they
 *     look like one cast. This one is lit by the prompt it is holding. A player
 *     could never say why the last thing they fight looks wrong, and that is
 *     the intended effect.
 *   THE PROMPT WINS. Three pixels, white, in front of the head, and they are
 *     the brightest thing in the frame — brighter than the core, brighter than
 *     the rim, brighter than a creature ninety-six pixels wide. A vast serpent
 *     and three small pixels, and the three pixels are what you read first.
 *   IT DOES NOT FIT. The coil is authored past the left and bottom edges of its
 *     own box. Every other boss in the game fits its frame. This one is cut by
 *     it, because the room is a consequence of the animal.
 */

/* Single line on purpose: the project's parse check strips /^import.*$/ per
 * line, and a wrapped import statement leaves its own tail behind. */
import { ramp, mix, hash, rng, gridSprite, mergeGrids, applyRim, rimLowLeft, normalise, silhouetteAt, rimTone } from './sprites.js';
import { RAMPS, SHADE, OUTLINE, MAX_COLOURS } from './palette.js';

export const BOSSART_VERSION = 1;

/* ================================================================
 * §0  BOX AND GLYPHS
 * ================================================================ */

/* The same box bosses.js uses. Stated here rather than imported so this module
 * has no dependency on the one that depends on it. bossArtSelfCheck() compares
 * them if a caller hands the other file's constants over. */
export const ART_W = 64;
export const ART_H = 64;
export const ART_WIDE_W = 96;
/* And the final rung of docs/08 §B, 12x16 tiles, which bosses.js authors one
 * creature at (the Examiner). Nothing in THIS file draws at it: an apex is a
 * width profile 64 rows long and the seventeen of them are a cast, not a
 * finale. The constants are here so the two files' idea of the ladder cannot
 * drift silently — bossArtSelfCheck() compares them when a caller hands
 * bosses.js's over. */
export const ART_FINAL_W = 96;
export const ART_FINAL_H = 128;

/* The row an apex plants its feet on. Void apexes deliberately stop short. */
export const ART_GROUND = 62;

/* Byte-identical to bosses.BOSS_GLYPHS, and that is load-bearing: a grid this
 * file produces is rasterised with a palette that file built, and a glyph the
 * palette has never heard of paints nothing at all. Closed set, checked. */
export const ART_GLYPHS = 'oOQBHLdDaAkewWgGnbCctTsrRfuUxXzZjJimMl';

const GLYPH_SET = new Set(ART_GLYPHS.split('').concat(['.', ' ']));

/** Every character in a grid is in the table. Used by the harness, and cheap
 *  enough to call from a debug overlay. Returns the offenders, not a boolean,
 *  because "which one" is the only useful answer. */
export function strayGlyphs(grid) {
  const bad = new Set();
  for (const row of grid || []) {
    for (const ch of String(row)) if (!GLYPH_SET.has(ch)) bad.add(ch);
  }
  return [...bad];
}

const T = '.';
const isEmpty = (ch) => ch === undefined || ch === '.' || ch === ' ';
const isEdge = (ch) => isEmpty(ch) || ch === 'o' || ch === 'O';

/* ================================================================
 * §1  THE ELEMENT VOCABULARY
 * ================================================================
 * Colours are the six from gauntlet/elements.py ELEMENTS, so a boss agrees with
 * the damage number that appears next to it and with the element rune in the
 * UI. Materials are named RAMPS entries, so a boss's steel is the armour's
 * steel. `verb` is the geometry; everything else is how that verb is lit.
 */

export const ELEMENT_IDS = ['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID', 'NEUTRAL'];

export const ELEMENT_LOOK = Object.freeze({
  FIRE: Object.freeze({
    id: 'FIRE',
    name: 'Fire',
    colour: '#e06a3c',           // elements.py ELEMENTS[FIRE].colour
    dark: '#8f3a1e',
    body: 'ember',               // palette.RAMPS
    hard: 'rust',                // the metal this element leaves behind
    mark: 'ember',               // the ramp the element's own marks are drawn in
    verb: 'shed',
    amp: 3,
    /* Up. Fire is the only element whose decoration fights gravity, which is
     * why it is the only one authored off the TOP contour. */
    habit: 'ragged upward, mass high, base narrower than the shoulders',
    light: Object.freeze({ rim: true, bounce: true, sharp: false, strobe: false }),
    motion: Object.freeze({ bob: 3, sway: 1, period: 1500, telegraph: 420, anim: 'flare' }),
    note: 'Rises, spends itself, and leaves the wound still burning.',
  }),
  COLD: Object.freeze({
    id: 'COLD',
    name: 'Cold',
    colour: '#7ec8ff',
    dark: '#2f6d9e',
    body: 'frost',
    hard: 'silver',
    mark: 'cyan',
    verb: 'spur',
    amp: 3,
    habit: 'faceted, widening downward, every angle the same angle',
    /* Sharp: a hard one-pixel specular with no falloff. Ice does not have a
     * soft edge and giving it one is how frost ends up reading as fur. */
    light: Object.freeze({ rim: true, bounce: false, sharp: true, strobe: false }),
    motion: Object.freeze({ bob: 1, sway: 1, period: 3000, telegraph: 620, anim: 'creep' }),
    note: 'Settles, and makes everything it touches slower to swing.',
  }),
  POISON: Object.freeze({
    id: 'POISON',
    name: 'Poison',
    colour: '#8fd07a',
    dark: '#3f7a3a',
    body: 'venom',
    hard: 'bronze',
    mark: 'venom',
    verb: 'drip',
    amp: 3,
    habit: 'sagging, bulbous through the middle, mass low and wet',
    light: Object.freeze({ rim: true, bounce: false, sharp: false, strobe: false, points: true }),
    motion: Object.freeze({ bob: 2, sway: 2, period: 2600, telegraph: 560, anim: 'seethe' }),
    note: 'Patient. It does not care how the fight is going right now.',
  }),
  BRUTE: Object.freeze({
    id: 'BRUTE',
    name: 'Brute Force',
    colour: '#bf8f4f',
    dark: '#6f4f28',
    body: 'stone',
    hard: 'iron',
    mark: 'earth',
    verb: 'chip',
    amp: 2,
    habit: 'blocky, weight forward, wider at the base than anywhere else',
    /* No glow. The contre-jour goes almost to outline, because the one thing
     * that separates rock from every other material in this game is that rock
     * does not emit and is not translucent. */
    light: Object.freeze({ rim: false, bounce: false, sharp: false, strobe: false, dull: true }),
    motion: Object.freeze({ bob: 1, sway: 0, period: 3200, telegraph: 700, anim: 'heavy' }),
    note: 'No cleverness at all. It simply arrives, and plate stops mattering.',
  }),
  LIGHTNING: Object.freeze({
    id: 'LIGHTNING',
    name: 'Lightning',
    colour: '#f2dc6a',
    dark: '#9a8220',
    body: 'chrome',
    hard: 'chrome',
    mark: 'gold',
    verb: 'arc',
    amp: 5,
    habit: 'thin extremities, high centre of mass, nothing rounded',
    light: Object.freeze({ rim: true, bounce: false, sharp: true, strobe: true }),
    motion: Object.freeze({ bob: 2, sway: 0, period: 1100, telegraph: 300, anim: 'snap' }),
    note: 'One instant of contact, and everything after it conducts.',
  }),
  VOID: Object.freeze({
    id: 'VOID',
    name: 'Void',
    colour: '#6a4f8f',
    dark: '#2f2445',
    body: 'void',
    hard: 'gunmetal',
    mark: 'violet',
    verb: 'hollow',
    amp: 4,
    habit: 'incomplete, interrupted, tapering into nothing before the floor',
    /* rim: false is the entire idea. Everything in this cast is lit from one
     * low left source. This is the thing that is not. */
    light: Object.freeze({ rim: false, bounce: false, sharp: false, strobe: false, negative: true }),
    motion: Object.freeze({ bob: 3, sway: 2, period: 3600, telegraph: 660, anim: 'float' }),
    note: 'Not a force. An absence, arriving where a force was expected.',
  }),
  NEUTRAL: Object.freeze({
    id: 'NEUTRAL',
    name: 'Neutral',
    colour: '#9aa0b4',
    dark: '#3b3f4e',
    body: 'iron',
    hard: 'steel',
    mark: 'bone',
    verb: 'none',
    amp: 0,
    habit: 'plain bulk. The baseline every other area is felt against',
    light: Object.freeze({ rim: true, bounce: false, sharp: false, strobe: false }),
    motion: Object.freeze({ bob: 2, sway: 1, period: 2400, telegraph: 520, anim: 'idle' }),
    note: 'Weather in a town is just weather.',
  }),
});

export function elementLook(element) {
  return ELEMENT_LOOK[String(element || '').toUpperCase()] || ELEMENT_LOOK.NEUTRAL;
}

/* ================================================================
 * §2  THE SEVENTEEN REGIONS
 * ================================================================
 * element is NOT invented here. It is gauntlet/elements.py BIOME_AFFINITY,
 * transcribed by biome, which is why the table below carries the biome as well:
 * if world.py ever moves a region to a different biome, the element that comes
 * out of this table moves with it and the mismatch is one grep away.
 *
 * `texture` is what the region does to its own boss on top of the element —
 * the thing that makes Hashmap Highlands and Graph Wastes, both LIGHTNING, not
 * the same picture.
 */
export const REGION_LOOK = Object.freeze({
  python_village: Object.freeze({
    region: 'python_village', biome: 'village', element: 'NEUTRAL',
    accent: '#c8a878', texture: 'timber and whitewash, half of it fallen in',
    note: 'Nothing here has been named recently enough to have weather.' }),
  fields_of_syntax: Object.freeze({
    region: 'fields_of_syntax', biome: 'grass', element: 'NEUTRAL',
    accent: '#97c057', texture: 'grass stems and half-formed lettering',
    note: 'The first fields. Nothing should push back yet.' }),
  hashmap_highlands: Object.freeze({
    region: 'hashmap_highlands', biome: 'highland', element: 'LIGHTNING',
    accent: '#e8a33d', texture: 'keyed vault plate, brass, one lock lit at a time',
    note: 'The only tall metal for a day’s walk, and the storms have noticed.' }),
  stringwood_labyrinth: Object.freeze({
    region: 'stringwood_labyrinth', biome: 'forest', element: 'POISON',
    accent: '#6fae63', texture: 'bark carved with letters, spores between them',
    note: 'Living, humid, and shedding between the letters.' }),
  array_caverns: Object.freeze({
    region: 'array_caverns', biome: 'cave', element: 'BRUTE',
    accent: '#9d979b', texture: 'numbered alcove stone, the weight above it',
    note: 'Indexed from zero, and the last is always one short of the count.' }),
  sliding_window_marsh: Object.freeze({
    region: 'sliding_window_marsh', biome: 'swamp', element: 'POISON',
    accent: '#77a05a', texture: 'standing water, gas, reed and a sliding frame',
    note: 'It widens right and shrinks left, and it never starts over.' }),
  twin_pointer_pass: Object.freeze({
    region: 'twin_pointer_pass', biome: 'mountain', element: 'COLD',
    accent: '#b7d4f8', texture: 'snow line granite and two lanterns above cloud',
    note: 'The only region in the game with real ice in it.' }),
  stack_queue_mines: Object.freeze({
    region: 'stack_queue_mines', biome: 'mine', element: 'FIRE',
    accent: '#e8762a', texture: 'ember seam, cart iron, props that gave way',
    note: 'The heat is already in the region’s own colours.' }),
  matrix_citadel: Object.freeze({
    region: 'matrix_citadel', biome: 'citadel', element: 'BRUTE',
    accent: '#8f67d1', texture: 'dressed ashlar in perfect rows and columns',
    note: 'The floor plan is a golem, which makes it a floor plan with a temper.' }),
  recursive_forest: Object.freeze({
    region: 'recursive_forest', biome: 'deepforest', element: 'VOID',
    accent: '#55446a', texture: 'each clearing a smaller copy, and one that did not return',
    note: 'A recursion that does not return is the nearest thing to an absence.' }),
  binary_tree_canopy: Object.freeze({
    region: 'binary_tree_canopy', biome: 'canopy', element: 'NEUTRAL',
    accent: '#688c36', texture: 'open air, and branches that fork twice and never rejoin',
    note: 'Above the Recursive Forest’s dark, which is why it is not void.' }),
  graph_wastes: Object.freeze({
    region: 'graph_wastes', biome: 'wastes', element: 'LIGHTNING',
    accent: '#9f969d', texture: 'broken lattice, conducting, ash on everything',
    note: 'A lattice of ruins is a lattice of conductors.' }),
  dp_ruins: Object.freeze({
    region: 'dp_ruins', biome: 'ruins', element: 'NEUTRAL',
    accent: '#e8c37d', texture: 'solved tiles that stay lit, and the unsolved ones that do not',
    note: 'What is remarkable here is the light already on the floor.' }),
  debugging_dungeon: Object.freeze({
    region: 'debugging_dungeon', biome: 'dungeon', element: 'FIRE',
    accent: '#c43f4f', texture: 'forge heat, cracked plate hung on every wall',
    note: 'The Armorer’s forge, and the cells where broken programs are kept.' }),
  complexity_tower: Object.freeze({
    region: 'complexity_tower', biome: 'tower', element: 'COLD',
    accent: '#3fadd0', texture: 'azure stair, each floor costlier and colder than the last',
    note: 'The top floor is unreachable by brute force.' }),
  coding_coliseum: Object.freeze({
    region: 'coding_coliseum', biome: 'arena', element: 'NEUTRAL',
    accent: '#ffc26a', texture: 'sand, a clock, and no hints',
    note: 'Giving this one weather would be contradicting the region.' }),
  null_kings_castle: Object.freeze({
    region: 'null_kings_castle', biome: 'castle', element: 'VOID',
    accent: '#755f8c', texture: 'unlabelled stone, unlit, nothing to read',
    note: 'Nothing is labelled and nothing is lit.' }),
});

export const REGION_IDS = Object.freeze(Object.keys(REGION_LOOK));

export function regionLook(regionId) {
  return REGION_LOOK[String(regionId || '')] || null;
}

export function elementForRegion(regionId) {
  const r = REGION_LOOK[String(regionId || '')];
  return r ? r.element : 'NEUTRAL';
}

/* ================================================================
 * §3  GEOMETRY
 * ================================================================ */

function cellsOf(grid, w) {
  const width = w || Math.max(...grid.map(r => r.length));
  return normalise(grid, width).map(r => r.split(''));
}
function gridOf(cells) { return cells.map(r => r.join('')); }

function blankCells(w, h) {
  const out = new Array(h);
  for (let y = 0; y < h; y++) out[y] = new Array(w).fill(T);
  return out;
}

function cellAt(cells, y, x) {
  const row = cells[y];
  return row === undefined ? undefined : row[x];
}

/* Topmost / bottommost filled row per column, leftmost / rightmost filled
 * column per row. Four arrays, one pass each, reused by every element verb. */
function topContour(cells, w, h) {
  const out = new Int16Array(w).fill(-1);
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) if (!isEmpty(cells[y][x])) { out[x] = y; break; }
  }
  return out;
}
function bottomContour(cells, w, h) {
  const out = new Int16Array(w).fill(-1);
  for (let x = 0; x < w; x++) {
    for (let y = h - 1; y >= 0; y--) if (!isEmpty(cells[y][x])) { out[x] = y; break; }
  }
  return out;
}
function rightContour(cells, w, h) {
  const out = new Int16Array(h).fill(-1);
  for (let y = 0; y < h; y++) {
    for (let x = w - 1; x >= 0; x--) if (!isEmpty(cells[y][x])) { out[y] = x; break; }
  }
  return out;
}
function leftContour(cells, w, h) {
  const out = new Int16Array(h).fill(-1);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) if (!isEmpty(cells[y][x])) { out[y] = x; break; }
  }
  return out;
}

/* A heavy black outline derived from the silhouette rather than authored. Every
 * body mass pixel with an empty orthogonal neighbour becomes 'o'. `openEdge`
 * says whether running off the box counts as empty: for everything but the last
 * interpreter it does, because a creature that ends at the frame edge without
 * an outline reads as a sprite that was cropped. The interpreter WANTS to read
 * as cropped, so it passes false. */
function outlinePass(cells, w, h, openEdge = true) {
  const src = cells.map(r => r.slice());
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (src[y][x] !== 'B') continue;
      const n = [[y - 1, x], [y + 1, x], [y, x - 1], [y, x + 1]];
      for (const [ny, nx] of n) {
        const out = ny < 0 || ny >= h || nx < 0 || nx >= w;
        if (out ? openEdge : isEmpty(src[ny][nx])) { cells[y][x] = 'o'; break; }
      }
    }
  }
  return cells;
}

/* Stamp a small authored grid into a cell buffer. '.' never erases, which is
 * mergeGrids' contract and the one every layer in this project follows. */
function stampCells(cells, w, h, src, ox, oy) {
  for (let y = 0; y < src.length; y++) {
    const ty = y + oy;
    if (ty < 0 || ty >= h) continue;
    const row = src[y];
    for (let x = 0; x < row.length; x++) {
      const tx = x + ox;
      if (tx < 0 || tx >= w) continue;
      const ch = row[x];
      if (ch === '.' || ch === ' ') continue;
      cells[ty][tx] = ch;
    }
  }
  return cells;
}

/* ================================================================
 * §4  THE SIX VERBS
 * ================================================================
 * Each mutates a cell buffer in place and returns the number of pixels it
 * touched, so the harness can prove the pass did something rather than take
 * this file's word for it. None of them allocates beyond the four contour
 * arrays, and none of them calls Math.random.
 */

/* FIRE — sheds. Tongues off the top contour, ember bounce underneath. */
function vShed(cells, w, h, rand, amp) {
  let touched = 0;
  const top = topContour(cells, w, h);
  for (let x = 1; x < w - 1; x++) {
    const ty = top[x];
    if (ty < 1 || ty > h * 0.72) continue;
    if (rand() > 0.34) continue;
    const len = 1 + ((rand() * amp) | 0);
    for (let i = 1; i <= len; i++) {
      const y = ty - i;
      if (y < 0) break;
      if (!isEmpty(cells[y][x])) break;
      cells[y][x] = (i === len) ? 'R' : 'r';
      touched++;
    }
  }
  /* The bounce. Fire is the one element that lights its own underside, so the
   * down-facing edges below the waist take the ember mid instead of the body's
   * deepest shadow. Without this a burning creature reads as a creature with
   * flames stuck on the top of it. */
  for (let y = (h * 0.42) | 0; y < h; y++) {
    for (let x = 1; x < w - 1; x++) {
      const ch = cells[y][x];
      if (ch !== 'B' && ch !== 'o') continue;
      if (!isEmpty(cellAt(cells, y + 1, x))) continue;
      if (rand() > 0.30) continue;
      cells[y][x] = 'r';
      touched++;
    }
  }
  return touched;
}

/* COLD — accretes. 45-degree spurs off the lower right, rime on the lit edge. */
function vSpur(cells, w, h, rand, amp) {
  let touched = 0;
  const right = rightContour(cells, w, h);
  const left = leftContour(cells, w, h);
  for (let y = (h * 0.26) | 0; y < h - 1; y++) {
    const rx = right[y];
    if (rx < 1) continue;
    if (rand() > 0.24) continue;
    const len = 1 + ((rand() * amp) | 0);
    for (let i = 1; i <= len; i++) {
      const xx = rx + i, yy = y + i;
      if (xx >= w || yy >= h) break;
      if (!isEmpty(cells[yy][xx])) break;
      cells[yy][xx] = (i === len) ? 'C' : 'i';
      touched++;
    }
  }
  /* Rime. The upper-left contour is where the key light lands, and frost on a
   * lit edge is the one place ice is actually white. */
  for (let y = 1; y < (h * 0.8) | 0; y++) {
    const lx = left[y];
    if (lx < 0 || lx >= w) continue;
    if (rand() > 0.26) continue;
    if (isEmpty(cells[y][lx])) continue;
    cells[y][lx] = 'i';
    touched++;
  }
  return touched;
}

/* POISON — sags. Drops off the bottom contour, wet points on the upper mass. */
function vDrip(cells, w, h, rand, amp) {
  let touched = 0;
  const bottom = bottomContour(cells, w, h);
  for (let x = 1; x < w - 1; x++) {
    const by = bottom[x];
    if (by < 0 || by >= h - 1) continue;
    if (rand() > 0.28) continue;
    const len = 1 + ((rand() * amp) | 0);
    for (let i = 1; i <= len; i++) {
      const y = by + i;
      if (y >= h) break;
      if (!isEmpty(cells[y][x])) break;
      cells[y][x] = (i === len) ? 'A' : 'a';
      touched++;
    }
  }
  /* Wet specular. Isolated single pixels, never a run: a continuous highlight
   * is a polished surface and a broken one is a wet surface, and that is the
   * whole difference between poison and chrome. */
  for (let y = 2; y < h - 2; y++) {
    for (let x = 2; x < w - 2; x++) {
      if (cells[y][x] !== 'B') continue;
      if (!isEmpty(cellAt(cells, y - 1, x)) && !isEmpty(cellAt(cells, y, x - 1))) {
        if (rand() > 0.045) continue;
        if (cellAt(cells, y, x - 1) === 'H' || cellAt(cells, y - 1, x) === 'H') continue;
        cells[y][x] = 'H';
        touched++;
      }
    }
  }
  return touched;
}

/* BRUTE — chips. The only verb that removes. */
function vChip(cells, w, h, rand, amp) {
  let touched = 0;
  const right = rightContour(cells, w, h);
  /* A cap, and a low one. A silhouette is the primary read at this size and a
   * verb that can eat an arbitrary amount of it is a verb that can destroy the
   * creature on an unlucky seed. Two per cent of a 64-box, and never more. */
  let budget = Math.max(6, Math.round(w * h * 0.012));
  const cut = [];
  for (let y = (h * 0.12) | 0; y < h && budget > 0; y++) {
    const rx = right[y];
    if (rx < 2) continue;
    if (rand() > 0.20) continue;
    const depth = 1 + ((rand() * amp) | 0);
    for (let i = 0; i < depth && budget > 0; i++) {
      const xx = rx - i;
      if (xx < 1) break;
      if (isEmpty(cells[y][xx])) break;
      cells[y][xx] = T;
      cut.push(y, xx);
      budget--; touched++;
    }
  }
  /* Re-outline. A bite that exposes raw body mass reads as a hole in the paint
   * rather than as broken stone, so whatever the chip uncovered gets an edge. */
  for (let i = 0; i < cut.length; i += 2) {
    const y = cut[i], x = cut[i + 1];
    const n = [[y - 1, x], [y + 1, x], [y, x - 1], [y, x + 1]];
    for (const [ny, nx] of n) {
      if (ny < 0 || ny >= h || nx < 0 || nx >= w) continue;
      if (cells[ny][nx] === 'B' || cells[ny][nx] === 'L' || cells[ny][nx] === 'H') {
        cells[ny][nx] = 'o';
        touched++;
      }
    }
  }
  return touched;
}

/* LIGHTNING — spans. A filament leaping between two points of the contour,
 * arcing outside the body. Strobes: on the off beats there is no discharge at
 * all, which is what makes lightning the only element with real inter-frame
 * silhouette change rather than a brightness wobble. */
function vArc(cells, w, h, rand, amp, beat) {
  if ((beat & 1) === 1) return 0;                    // the off half of the strobe
  let touched = 0;
  const top = topContour(cells, w, h);
  const anchors = [];
  for (let x = 2; x < w - 2; x++) if (top[x] >= 1 && top[x] < h * 0.6) anchors.push(x);
  if (anchors.length < 4) return 0;
  const bolts = 2 + ((rand() * 2) | 0);
  for (let b = 0; b < bolts; b++) {
    const i0 = (rand() * anchors.length) | 0;
    let i1 = (rand() * anchors.length) | 0;
    if (Math.abs(i1 - i0) < 4) i1 = (i0 + 5 + ((rand() * 7) | 0)) % anchors.length;
    const x0 = Math.min(anchors[i0], anchors[i1]);
    const x1 = Math.max(anchors[i0], anchors[i1]);
    if (x1 - x0 < 3) continue;
    const y0 = top[x0], y1 = top[x1];
    let ridge = Math.min(y0, y1);
    for (let x = x0; x <= x1; x++) if (top[x] >= 0 && top[x] < ridge) ridge = top[x];
    const peak = Math.max(0, ridge - (2 + ((rand() * amp) | 0)));
    /* Two straight legs through a peak, jittered one pixel per step. A smooth
     * curve would be a rainbow; a discharge is a sequence of bad decisions.
     *
     * Every step is clamped to sit at least one row ABOVE the local top
     * contour. Without that the filament spends most of its length inside the
     * creature, where it is not drawn, and what reaches the screen is six
     * pixels of confetti instead of a bolt. The clamp is what makes the arc a
     * span rather than a decoration: it is in free air for its whole length. */
    let px = x0, py = y0;
    const step = (tx, ty) => {
      const span = Math.max(1, Math.abs(tx - px));
      for (let s = 1; s <= span; s++) {
        const nx = px + Math.sign(tx - px) * s;
        if (nx < 0 || nx >= w) break;
        let ny = Math.round(py + (ty - py) * (s / span)) + ((rand() < 0.34) ? (rand() < 0.5 ? -1 : 1) : 0);
        const ceil = top[nx] >= 0 ? top[nx] - 1 : h - 1;
        ny = Math.max(0, Math.min(h - 1, Math.min(ny, ceil)));
        if (isEmpty(cells[ny][nx])) { cells[ny][nx] = 'u'; touched++; }
      }
      px = tx; py = ty;
    };
    const mx = (x0 + x1) >> 1;
    step(mx, peak);
    step(x1, y1);
    if (peak >= 0 && peak < h && isEmpty(cells[peak][mx])) { cells[peak][mx] = 'U'; touched++; }
  }
  return touched;
}

/* VOID — subtracts. Holes inward, outline missing outward. */
function vHollow(cells, w, h, rand, amp, beat, core) {
  let touched = 0;
  const cx = core ? core[0] : (w >> 1);
  const cy = core ? core[1] : (h >> 1);
  // A few connected absences read as the material failing. Independent black
  // dots over a pale 96x128 breastplate read as compression noise and conceal
  // the sigil. The cuts remain inside undecorated body mass.
  const cuts = 2 + Math.min(3, amp);
  for (let n = 0; n < cuts; n++) {
    const startX = Math.round(cx + (rand() - .5) * w * .48);
    const startY = Math.max(1, Math.round(cy - h * .2 + (rand() - .5) * h * .3));
    const length = Math.round(h * .12 + amp * 2 + rand() * 5);
    const lean = rand() < .5 ? -1 : 1;
    for (let step = 0; step < length; step++) {
      const y = startY + step;
      const x = startX + lean * Math.floor(step / 5);
      if (y < 1 || y >= h - 1 || x < 1 || x >= w - 2) continue;
      const thickness = step > 2 && step < length - 3 ? 2 : 1;
      for (let dx = 0; dx < thickness; dx++) {
        const px = x + dx;
        if (cells[y][px] !== 'B') continue;
        if (isEmpty(cells[y - 1][px]) || isEmpty(cells[y + 1][px])
          || isEmpty(cells[y][px - 1]) || isEmpty(cells[y][px + 1])) continue;
        cells[y][px] = 'k'; touched++;
      }
    }
  }
  // Sparse contiguous gaps interrupt the lower-left outline, where other
  // creatures take their rim. Keep broad unbroken contours between them.
  for (let band = 0; band < 3; band++) {
    const startY = Math.floor(h * (.48 + band * .15) + rand() * 3);
    for (let y = startY; y < Math.min(h, startY + 2 + amp); y++) {
      for (let x = 0; x < Math.floor(w * .55); x++) {
        if (cells[y][x] !== 'o') continue;
        cells[y][x] = T; touched++; break;
      }
    }
  }
  return touched;
}

/* The dispatcher. Deterministic in everything it is handed and nothing else. */
export function dressGrid(grid, look, opts = {}) {
  if (!grid || !grid.length) return grid;
  const lk = look || FALLBACK_LOOK;
  const el = elementLook(lk.element);
  const w = Math.max(...grid.map(r => r.length));
  const h = grid.length;
  if (el.verb === 'none') {
    // The control group leaves no trace, and says so rather than leaving the
    // previous element's numbers standing where a harness will read them.
    LAST_DRESS.verb = 'none'; LAST_DRESS.touched = 0;
    return normalise(grid, w);
  }

  const frame = opts.frame | 0;
  const beat = opts.beat | 0;
  const phase = Math.max(0, Math.min(2, opts.phase | 0));
  const seedStr = `ba1|${lk.id}|${el.id}|${frame}|${beat}|${phase}|${opts.seed | 0}`;
  const rand = rng(hash(seedStr));
  /* Phase escalates the verb rather than repainting it: the same fire, more of
   * it. bosses.js already darkens and ignites through bossPalette; this is the
   * geometry half of the same escalation. */
  const amp = Math.max(1, Math.round(el.amp * (1 + phase * 0.4)));

  const cells = cellsOf(grid, w);
  let touched = 0;
  switch (el.verb) {
    case 'shed':   touched = vShed(cells, w, h, rand, amp); break;
    case 'spur':   touched = vSpur(cells, w, h, rand, amp); break;
    case 'drip':   touched = vDrip(cells, w, h, rand, amp); break;
    case 'chip':   touched = vChip(cells, w, h, rand, amp); break;
    case 'arc':    touched = vArc(cells, w, h, rand, amp, beat); break;
    case 'hollow': touched = vHollow(cells, w, h, rand, amp, beat, lk.core); break;
    default: break;
  }
  LAST_DRESS.touched = touched;
  LAST_DRESS.verb = el.verb;
  return gridOf(cells);
}

/* What the last dressGrid() call actually did. For the harness and a debug
 * overlay; never read on a draw path. */
export const LAST_DRESS = { verb: 'none', touched: 0 };

/** Whether this look takes the cast's one hot low-left rim. VOID and BRUTE do
 *  not, for opposite reasons: void refuses light and stone does not carry it. */
export function wantsRim(look) {
  return elementLook((look || FALLBACK_LOOK).element).light.rim !== false;
}

/* ================================================================
 * §5  PALETTE
 * ================================================================ */

/* Fifteen slots for thirty-eight glyphs, and which glyph collapses onto which
 * is a decision rather than a shortcut: in a near-black ambient every material's
 * deepest step converges, which is rule 1 of docs/08 and also simply true.
 *
 *   1  INK        o k m n e c    outline, void, eye socket, chain shadow
 *   2  RIM        O              the lit outline, upper left
 *   3  EDGE       Q              contre-jour, in the creature's own colour
 *   4  SHADE2     D s            body's deepest, and cloth's
 *   5  SHADE1     d j l          body's shadow, bark, leather
 *   6  BASE       B t            body, cloth
 *   7  LIGHT      L T J H        body's lit steps
 *   8  ACC        a x            the accent, and blood
 *   9  ACCLIT     A z Z          the accent's light, and gold
 *  10  MARK       r f            the element's own mark
 *  11  MARKHOT    R u i          its hot tip. Only one element uses any of these
 *  12  BONE       b
 *  13  BONELIT    C w
 *  14  CHROME     g
 *  15  SPEC       G M W U        chrome's specular is the white. One pixel.
 *
 * Bone at 12-13 and chrome at 14-15, in the same frame, which is docs/09 §8.
 */
export function lookPalette(look, phase = 0) {
  const lk = look || FALLBACK_LOOK;
  const el = elementLook(lk.element);
  const ph = Math.max(0, Math.min(2, phase | 0));
  const cracked = ph === 1, lit = ph >= 2;

  const bodyRamp = RAMPS[el.body] || RAMPS.iron;
  const markRamp = RAMPS[el.mark] || RAMPS.ember;
  const hardRamp = RAMPS[el.hard] || RAMPS.steel;
  const bone = RAMPS.bone;
  const chrome = RAMPS.chrome;

  const src = lk.colour || el.colour;
  const acc = lk.accent || el.dark;
  const r = ramp(lit ? mix(src, acc, 0.22) : src);
  const a = ramp(acc);
  const heat = markRamp[SHADE.SPEC];
  /* One knob for "this material is standing in the core's light rather than
   * being made of it". Chrome lit by a furnace is still chrome. */
  const seen = (hex, t) => (lit ? mix(hex, heat, t) : cracked ? mix(hex, '#0c0a14', t * 0.9) : hex);

  const ink = mix(OUTLINE, r.outline, cracked || lit ? 0.18 : 0.30);
  /* The contre-jour. Brute has none — stone does not emit — and void's is
   * NEGATIVE: it goes darker than the outline, so the edge eats its own light. */
  const edge = el.light.dull ? mix(ink, r.shadow2, 0.45)
    : el.light.negative ? mix(ink, '#000000', 0.35)
    : lit ? mix(r.light1, heat, 0.55) : mix(r.light1, src, cracked ? 0.48 : 0.26);

  const pal = {
    o: ink, k: ink, m: ink, n: ink, e: ink, c: ink,
    O: el.light.negative ? ink : (lit ? mix(r.rim, heat, 0.45) : r.rim),
    Q: edge,
    D: cracked ? mix(bodyRamp[SHADE.DEEP], '#07060c', 0.35) : bodyRamp[SHADE.DEEP],
    s: cracked ? mix(bodyRamp[SHADE.DEEP], '#07060c', 0.35) : bodyRamp[SHADE.DEEP],
    d: mix(bodyRamp[SHADE.DARK], r.shadow1, 0.35),
    j: mix(bodyRamp[SHADE.DARK], r.shadow1, 0.35),
    l: mix(bodyRamp[SHADE.DARK], r.shadow1, 0.35),
    B: mix(bodyRamp[SHADE.MID], r.base, 0.45),
    t: mix(bodyRamp[SHADE.MID], r.base, 0.45),
    L: mix(bodyRamp[SHADE.LIGHT], r.light1, 0.45),
    T: mix(bodyRamp[SHADE.LIGHT], r.light1, 0.45),
    J: mix(bodyRamp[SHADE.LIGHT], r.light1, 0.45),
    H: mix(bodyRamp[SHADE.LIGHT], r.light1, 0.45),
    a: a.base, x: a.base,
    A: a.light2, X: a.light2, z: a.light2, Z: a.light2,
    r: markRamp[SHADE.LIGHT], f: markRamp[SHADE.LIGHT],
    R: markRamp[SHADE.SPEC], u: markRamp[SHADE.SPEC], i: markRamp[SHADE.SPEC],
    b: seen(bone[SHADE.MID], 0.14),
    C: seen(bone[SHADE.LIGHT], 0.28), w: seen(bone[SHADE.LIGHT], 0.28),
    g: seen(mix(chrome[SHADE.MID], hardRamp[SHADE.MID], 0.5), 0.14),
    G: seen(chrome[SHADE.SPEC], 0.30), M: seen(chrome[SHADE.SPEC], 0.30),
    U: seen(chrome[SHADE.SPEC], 0.30),
    /* The one pure white, and the only glyph in the file that is not a step of
     * some material's ramp. It is spent on exactly one thing — the prompt in
     * front of the last interpreter's mouth — which is why the last boss's
     * three brightest pixels are brighter than anything else in the game. */
    W: '#ffffff',
  };
  return pal;
}

/** Distinct hex values a palette dict would actually paint. The dict-side
 *  budget check; the raster-side one lives in the harness and is the one that
 *  counts. */
export function paletteColours(pal) {
  const seen = new Set();
  for (const k of Object.keys(pal)) if (pal[k]) seen.add(String(pal[k]).toLowerCase());
  return seen.size;
}

/* Overlay the element's materials onto a palette somebody else built —
 * bosses.bossPalette(). Reassigns slots, never adds one, so a theme pass can
 * change what a boss is made of and cannot change what it costs.
 *
 * The body ramp is deliberately NOT touched: bosses.js derives it from the
 * boss's own colour out of world.py, and that colour is identity. What changes
 * is the element's marks, the contre-jour, and whether there is a rim at all. */
export function elementPalette(pal, look, phase = 0) {
  const lk = look || FALLBACK_LOOK;
  const el = elementLook(lk.element);
  const out = Object.assign({}, pal || {});
  if (el.verb === 'none') return out;

  const markRamp = RAMPS[el.mark] || RAMPS.ember;
  const ph = Math.max(0, Math.min(2, phase | 0));
  const lit = ph >= 2;

  // The element's own marks, whichever glyphs its verb emits.
  out.r = markRamp[SHADE.LIGHT];
  out.f = markRamp[SHADE.MID];
  out.R = markRamp[SHADE.SPEC];
  out.u = markRamp[SHADE.SPEC];
  out.i = markRamp[SHADE.SPEC];
  out.a = out.a || markRamp[SHADE.MID];
  out.A = out.A || markRamp[SHADE.SPEC];

  if (el.light.dull) {
    // Stone does not emit. The contre-jour collapses onto the outline, which is
    // what makes a brute-force boss read as a mass rather than as a lamp.
    out.Q = mix(out.Q || out.o || OUTLINE, out.o || OUTLINE, 0.72);
  } else if (el.light.negative) {
    // Void goes further: the rim and the lit outline become the outline itself.
    out.Q = mix(out.o || OUTLINE, '#000000', 0.35);
    out.O = out.o || OUTLINE;
  } else if (el.light.sharp) {
    // Ice and chrome: one hard step, no falloff.
    out.Q = mix(out.Q || markRamp[SHADE.LIGHT], markRamp[SHADE.SPEC], 0.55);
  } else if (el.light.bounce) {
    out.Q = mix(out.Q || markRamp[SHADE.LIGHT], markRamp[SHADE.SPEC], lit ? 0.5 : 0.3);
  }
  return out;
}

/* ================================================================
 * §6  BODIES
 * ================================================================
 * An apex is authored as a WIDTH PROFILE — one half-width per row of the box —
 * plus a few spans for limbs and a few stamped features. Sixty-four small
 * integers describe a silhouette precisely, they can be read at a glance, and
 * they can be modulated per apex (taper, swell, lean) to give seventeen
 * measurably different shapes out of seven archetypes. A hand-authored 64x64
 * grid per apex would be four hundred lines of ASCII that nobody would ever
 * edit again.
 *
 * Each is the element made a body with no creature underneath it, which is the
 * rule that separates an apex from the region's named boss: the boss is an
 * animal wearing an element, the apex IS the element and has no second idea.
 */

/* Rows 0..63, half-width in columns. 0 means the row is empty. */
const PROFILE = Object.freeze({
  /* FIRE: an inverted teardrop. Wide at the shoulders, tapering to a point that
   * does not quite reach the floor, because flame does not stand on anything. */
  fire: Object.freeze([
    0, 0, 2, 4, 6, 8, 9, 11, 12, 13, 14, 15, 16, 16, 17, 17,
    18, 18, 18, 18, 17, 17, 17, 16, 16, 15, 15, 14, 14, 13, 13, 12,
    12, 11, 11, 10, 10, 9, 9, 9, 8, 8, 8, 7, 7, 7, 6, 6,
    6, 5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 1, 1, 0,
  ]),
  /* COLD: a shard head on a shoulder break, then straight facets to a base
   * wider than anything else in the roster. Every edge is the same gradient. */
  cold: Object.freeze([
    0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7,
    8, 8, 13, 13, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18, 19, 19,
    19, 20, 20, 21, 21, 22, 22, 22, 23, 23, 23, 24, 24, 24, 25, 25,
    25, 26, 26, 26, 27, 27, 27, 28, 28, 28, 29, 29, 29, 29, 29, 0,
  ]),
  /* POISON: a sagging sac. Thin neck, the mass low and swollen, thin legs that
   * look inadequate to it, which is the point. */
  poison: Object.freeze([
    0, 0, 0, 3, 5, 6, 7, 7, 7, 6, 5, 5, 6, 8, 10, 12,
    14, 16, 17, 18, 19, 20, 21, 22, 22, 23, 23, 24, 24, 24, 25, 25,
    25, 25, 25, 24, 24, 23, 23, 22, 21, 20, 19, 17, 15, 13, 11, 9,
    7, 6, 5, 5, 5, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 0,
  ]),
  /* BRUTE: a slab. Flat top, near-constant width, flared at the base. Nothing
   * about it tapers, because nothing about it is trying. */
  brute: Object.freeze([
    0, 0, 0, 0, 0, 0, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12,
    20, 21, 22, 22, 23, 23, 23, 23, 23, 23, 23, 23, 22, 22, 22, 22,
    22, 22, 22, 22, 21, 21, 21, 21, 21, 21, 21, 21, 22, 22, 22, 22,
    23, 23, 23, 23, 24, 24, 24, 24, 25, 25, 26, 26, 27, 27, 27, 0,
  ]),
  /* LIGHTNING: thin, tall, a high centre of mass and almost no base. The arms
   * are spans rather than profile, so the body itself stays a filament. */
  lightning: Object.freeze([
    0, 3, 5, 6, 7, 8, 8, 9, 9, 9, 8, 7, 6, 5, 5, 6,
    7, 8, 9, 10, 11, 11, 12, 12, 12, 12, 11, 11, 11, 10, 10, 10,
    9, 9, 9, 8, 8, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5, 5,
    4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 0,
  ]),
  /* VOID: a hood over a shroud that stops. Rows 57 down are empty on purpose —
   * this is the only body in the roster that never reaches the ground line. */
  void: Object.freeze([
    0, 0, 4, 7, 9, 10, 11, 12, 12, 13, 13, 14, 14, 15, 15, 16,
    16, 17, 17, 18, 18, 19, 19, 20, 20, 20, 21, 21, 21, 21, 21, 21,
    20, 20, 20, 19, 19, 18, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9,
    8, 7, 6, 5, 4, 3, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0,
  ]),
  /* NEUTRAL: plain bipedal bulk. The control group, and it looks like it. */
  neutral: Object.freeze([
    0, 0, 0, 0, 5, 7, 8, 9, 9, 9, 8, 7, 8, 11, 14, 16,
    17, 18, 18, 19, 19, 19, 19, 18, 18, 18, 17, 17, 17, 16, 16, 16,
    16, 16, 16, 16, 15, 15, 15, 14, 14, 13, 13, 12, 12, 12, 13, 13,
    14, 14, 14, 14, 14, 14, 15, 15, 15, 16, 16, 17, 17, 18, 18, 0,
  ]),
});

/* Limbs, horns and crowns, as row ranges and column offsets from the centre.
 * Mirrored unless the entry says otherwise. [y0, y1, x0, x1]. */
const SPANS = Object.freeze({
  fire: Object.freeze([[10, 14, 16, 24], [18, 22, 17, 26]]),
  cold: Object.freeze([[20, 24, 15, 26], [34, 38, 20, 30]]),
  poison: Object.freeze([[20, 24, 21, 29], [44, 50, 8, 13]]),
  brute: Object.freeze([[18, 30, 22, 29], [30, 36, 20, 27]]),
  lightning: Object.freeze([[14, 16, 9, 28], [17, 18, 22, 30], [24, 26, 11, 24]]),
  void: Object.freeze([[22, 28, 19, 27]]),
  neutral: Object.freeze([[18, 32, 18, 25], [44, 52, 12, 18]]),
});

/* Where the element's core sits, which is where void hollows from and where
 * bosses.js would ignite. */
const CORES = Object.freeze({
  fire: [32, 20], cold: [32, 30], poison: [32, 30], brute: [32, 28],
  lightning: [32, 20], void: [32, 26], neutral: [32, 26],
});

/* The face. Seven of them, because an apex with the same eyes as the next one
 * is an apex that is a recolour after all. Authored small and stamped. */
const FACES = Object.freeze({
  fire: Object.freeze([
    '.k...k.',
    'kRk.kRk',
    '.k...k.',
  ]),
  cold: Object.freeze([
    'C.....C',
    '.i...i.',
    '..C.C..',
  ]),
  poison: Object.freeze([
    'kkk.kkk',
    'kAk.kAk',
    '.k...k.',
  ]),
  brute: Object.freeze([
    'ooooooo',
    'okkokko',
    'ooooooo',
  ]),
  lightning: Object.freeze([
    '..UUU..',
    '.UkkkU.',
    '..UUU..',
  ]),
  void: Object.freeze([
    'kkkkkkk',
    'kkkkkkk',
    'kkkkkkk',
  ]),
  /* Bone-white, not pure white: #ffffff is spent on the last interpreter's
   * prompt and on nothing else in the game, which is the only reason the three
   * brightest pixels of the last fight are the three that matter. */
  neutral: Object.freeze([
    '.o...o.',
    'owo.owo',
    '.o...o.',
  ]),
});

/* THE RIG — bone and chrome in the same frame, which is docs/09 §8 and rule E.
 *
 * Every study body in this file carries a skeleton and a piece of hard metal,
 * out of palette.RAMPS.bone and palette.RAMPS.chrome, so a boss's bone is the
 * same bone as the armour's and the pets'. It is also what stops an apex being
 * a monotone blob: an elemental with nothing hard in it has no scale reference
 * and reads as a shape rather than as a creature the size of a house.
 *
 * Seven of them, one per archetype, because a shared rig would put the same
 * collar on a flame and a slab.
 */
const RIGS = Object.freeze({
  /* Fire leaves metal behind. A gorget that survived, over ribs that did not. */
  fire: Object.freeze({ ox: -4, oy: 4, grid: Object.freeze([
    'gGGGGGg',
    'oGgggGo',
    '.ooooo.',
    '.b.C.b.',
    '.b.C.b.',
    'b.C.C.b',
  ]) }),
  /* Cold: a bone spine standing clear of the facets, pinned with chrome. */
  cold: Object.freeze({ ox: -3, oy: 5, grid: Object.freeze([
    '.gGg.',
    '.oCo.',
    '..b..',
    '.CbC.',
    '..b..',
    '.CbC.',
    '..b..',
  ]) }),
  /* Poison: a collar holding a head the body is too soft to hold up itself. */
  poison: Object.freeze({ ox: -5, oy: 3, grid: Object.freeze([
    'ggGGGgg',
    'oGgggGo',
    'b.ooo.b',
    'Cb...bC',
    '.C...C.',
  ]) }),
  /* Brute: plate, and knuckles. Nothing about it is articulated. */
  brute: Object.freeze({ ox: -6, oy: 6, grid: Object.freeze([
    'gGGGGGGGg',
    'gGgggggGg',
    'ooooooooo',
    'bCb...bCb',
    'bCb...bCb',
    'ooo...ooo',
  ]) }),
  /* Lightning: a conducting rod through bone insulators. */
  lightning: Object.freeze({ ox: -2, oy: 4, grid: Object.freeze([
    'bGb',
    '.G.',
    'CGC',
    '.G.',
    'bGb',
    '.G.',
    'CGC',
  ]) }),
  /* Void: the chrome is nearly gone and the bone is showing through, which is
   * the only way to tell how much of this one is missing. */
  void: Object.freeze({ ox: -3, oy: 6, grid: Object.freeze([
    '.gGg.',
    'bkkkb',
    'CkkkC',
    'bkkkb',
    '.kkk.',
    '.C.C.',
  ]) }),
  /* Neutral: a plain plate and a plain spine. The control group again. */
  neutral: Object.freeze({ ox: -4, oy: 5, grid: Object.freeze([
    'gGGGGGg',
    'oGgggGo',
    '..ooo..',
    '..bCb..',
    '..bCb..',
    '..bCb..',
  ]) }),
});

/* Build a body from a profile. `mod` is how one apex differs from the next
 * inside the same archetype: a taper, a swell over a band, a lean. All three
 * are integer operations on the profile, so the silhouette stays on the grid.
 */
function bodyCells(archetype, mod, w, h) {
  const prof = PROFILE[archetype] || PROFILE.neutral;
  const cells = blankCells(w, h);
  const cx = w >> 1;
  const taper = (mod && mod.taper) || 0;          // -n narrows downward, +n widens
  const swell = (mod && mod.swell) || null;       // [y0, y1, amount]
  const leanA = (mod && mod.lean) || 0;
  const leanK = (mod && mod.leanK) || 1;
  const scale = (mod && mod.scale) || 1;

  for (let y = 0; y < h && y < prof.length; y++) {
    let hw = prof[y];
    if (!hw) continue;
    hw = Math.round(hw * scale);
    hw += Math.round(taper * (y / h));
    if (swell && y >= swell[0] && y <= swell[1]) hw += swell[2];
    if (hw < 1) continue;
    const lean = leanA ? Math.round(leanA * Math.sin((y / h) * Math.PI * leanK)) : 0;
    const x0 = Math.max(0, cx + lean - hw);
    const x1 = Math.min(w - 1, cx + lean + hw);
    for (let x = x0; x <= x1; x++) cells[y][x] = 'B';
  }

  const spans = SPANS[archetype] || SPANS.neutral;
  for (const [y0, y1, sx0, sx1] of spans) {
    for (let y = y0; y <= y1 && y < h; y++) {
      const lean = leanA ? Math.round(leanA * Math.sin((y / h) * Math.PI * leanK)) : 0;
      for (let x = sx0; x <= sx1; x++) {
        const rx = cx + lean + Math.round(x * scale);
        const lx = cx + lean - Math.round(x * scale);
        if (rx >= 0 && rx < w) cells[y][rx] = 'B';
        if (!(mod && mod.asym) && lx >= 0 && lx < w) cells[y][lx] = 'B';
      }
    }
  }
  return cells;
}

/* Where the face goes: the widest point of the top third, which is the head on
 * every one of the seven profiles. Computed rather than authored so a modulated
 * profile keeps its eyes in the right place. */
function faceAnchor(cells, w, h) {
  let best = -1, bestY = 6;
  for (let y = 2; y < h * 0.45; y++) {
    let n = 0;
    for (let x = 0; x < w; x++) if (!isEmpty(cells[y][x])) n++;
    if (n > best) { best = n; bestY = y; }
  }
  return [w >> 1, Math.max(3, bestY)];
}

/* ================================================================
 * §7  THE FOURTEEN NAMED BOSSES
 * ================================================================
 * Each is a Python concept made flesh — bestiary.py says what the concept is
 * and the motif has to argue it, not label it. The grids below are stamped onto
 * bosses.js's own authored creature, merged BEFORE lighting so the motif is lit
 * as part of the animal rather than as a sticker on top of one.
 *
 * `slot` is where bosses.js should put it: 'brow', 'chest', 'back', 'flank',
 * 'crown', 'trail'. Offsets are a suggestion in a 64-box and the staging is
 * free to move them; the grid is the part that matters.
 */

/* The Hash Titan: a dict the size of a hill. A row of vault keys across the
 * brow, each a different length, and exactly one of them lit — membership is
 * one key and one vault, and a set that answers everything answers nothing. */
const M_KEYRING = Object.freeze([
  'z.z.Z.z.z.z',
  'z.z.Z.z.z.z',
  'o.z.Z.z.z.o',
  '..o.Z.o.o..',
  '....Z......',
  '....o......',
]);

/* The Three-Sum Hydra: three heads when it is sorted, and the cauterised stumps
 * of the ones you already skipped. The stumps are the dedupe. */
const M_STUMPS = Object.freeze([
  'b.b...b.b',
  'ob.b.b.bo',
  '.oxo.oxo.',
  '..o...o..',
]);

/* The Window Wraith: an empty rectangle where the torso should be — you can see
 * the marsh through it. The right edge is solid because the right edge only
 * ever advances; the left edge is broken because the left edge shrinks. */
const M_FRAME = Object.freeze([
  'ouuuuuuuuuu',
  '.kkkkkkkkku',
  'o.kkkkkkkku',
  '.kkkkkkkkku',
  'o.kkkkkkkku',
  '.kkkkkkkkku',
  'ouuuuuuuuuu',
]);

/* The Twin Pointer Behemoth: two horns of unequal height with a measured span
 * strung between their tips. The SHORTER horn is the lit one, because the
 * shorter wall is the one holding you back. */
const M_HORNS = Object.freeze([
  'C........',
  'C....o...',
  'C.uuu.o..',
  'b.....o.o',
  'b.......o',
  'o.......o',
]);

/* The Matrix Golem: plates in rows and columns with the seams showing, and one
 * plate sitting off the diagonal — transposed, and not put back. */
const M_GRID = Object.freeze([
  'gGgogGgogGg',
  'ooooooooooo',
  'gGgogagogGg',
  'ooooooooooo',
  'gGgogGgogGg',
  'ooooooooooo',
  'gGgogGgogGg',
]);

/* The Tree Dragon: a wing that is a branch forking exactly twice and never
 * rejoining, and two eyes at different heights — the inherited lo and hi. */
const M_FORK = Object.freeze([
  'j.......j',
  '.j.....j.',
  '..j...j..',
  '...j.j...',
  '....J....',
  '....J....',
  '....J....',
]);

/* The Path-Sum Ent: one arm. Insistently, deliberately one arm, because a node
 * with one child is not a leaf and this is that sentence with bark on it. */
const M_ONEARM = Object.freeze([
  'jJ.......',
  'jJ.......',
  '.jJ......',
  '..jJ.....',
  '...jj....',
  '....j....',
]);

/* The Graph Necromancer: skulls at fixed radii, not scattered. A frontier
 * expands evenly, and the outermost ring is already marked. */
const M_RINGS = Object.freeze([
  '..b.....b..',
  '.....C.....',
  'b..C...C..b',
  '.....u.....',
  'b..C...C..b',
  '.....C.....',
  '..b.....b..',
]);

/* The Rolling Titan: shoulder plates in strictly descending height, left to
 * right. A monotonic deque with a body around it. The front one is tallest and
 * is the only one lit, because the front of the deque is the answer. */
const M_MONOTONE = Object.freeze([
  'G..........',
  'Gg.........',
  'Ggg........',
  'Gggg.......',
  'Gggggg.....',
  'Gggggggg...',
  'ooooooooooo',
]);

/* The Editor Automaton: two stacked columns on its back, one tall and one
 * short, and a sentinel plate at the bottom of the short one — the guard you
 * did not write. */
const M_STACKS = Object.freeze([
  'ggg...',
  'ooo...',
  'ggg...',
  'ooo...',
  'gggggg',
  'oooooo',
  'gggggg',
  'oooCoo',
]);

/* The Complexity Wyrm: segments that double. The head is O(1) and by the fourth
 * segment the tail is the whole rest of the frame. */
const M_DOUBLING = Object.freeze([
  'i.................',
  'ii................',
  'iiii..............',
  'iiiiiiii..........',
  'iiiiiiiiiiiiiiii..',
  'oooooooooooooooooo',
]);

/* The Serialization Lich: a ribbon of tokens unspooling from the ribcage, with
 * the gaps in it. The gaps are the null markers, they are the same tone as the
 * void, and without them you cannot say which tree it was. */
const M_RIBBON = Object.freeze([
  'bCb.k.bCb.k.k.bCb',
  'ooo...ooo.....ooo',
]);

/* The Bug Demon: one horn, one wing, one leg a pixel short. It is the only
 * entry in this file that refuses the mirror, and it refuses it on purpose:
 * an off-by-one made flesh is not symmetric and cannot be. */
const M_ASYM = Object.freeze([
  '..x......',
  '.xX......',
  '.xx....x.',
  '.o.....xo',
  '.......o.',
]);

/* The Examiner: a visor with no slit in it at all, and a clipboard that is a
 * rectangle of nothing. The only boss in the game with no lit edge anywhere. */
const M_BLANK = Object.freeze([
  'ooooooooo',
  'okkkkkkko',
  'okkkkkkko',
  'okkkkkkko',
  'ooooooooo',
]);

/* The roster. The first field is the world.BOSSES id and is the key everything
 * resolves through; `sprite` is world.py's own sprite name, kept so a caller
 * holding a boss row rather than an id still lands here.
 *
 * [id, name, region, sprite, colour, note, motifs, mod] */
const NAMED_ROWS = [
  ['hash_titan', 'The Hash Titan', 'hashmap_highlands', 'titan', '#e8a33d',
    'A dict the size of a hill, and only one of its questions is answered by a set.',
    [['brow', M_KEYRING, 26, 8]], { scale: 1.12, taper: 4 }],
  ['three_sum_hydra', 'The Three-Sum Hydra', 'array_caverns', 'hydra', '#4fb783',
    'Unsorted it has infinite heads. Sorted it has three, and the rest are scars.',
    [['crown', M_STUMPS, 27, 6]], { swell: [4, 14, 6], taper: -3 }],
  ['window_wraith', 'The Window Wraith', 'sliding_window_marsh', 'wraith', '#7f6ad6',
    'A frame with nothing in it. The right edge advances; the left edge is broken.',
    [['chest', M_FRAME, 26, 24]], { taper: -5, swell: [22, 34, 3] }],
  ['twin_behemoth', 'The Twin Pointer Behemoth', 'twin_pointer_pass', 'behemoth', '#c4553f',
    'Two horns of unequal height and a measured span between them.',
    [['crown', M_HORNS, 28, 7]], { lean: 4, leanK: 2, taper: 2 }],
  ['matrix_golem', 'The Matrix Golem', 'matrix_citadel', 'golem', '#8a8f9c',
    'Rows, columns, visible seams, and one plate transposed and never put back.',
    [['chest', M_GRID, 26, 22]], { scale: 1.05, swell: [16, 44, 2] }],
  ['tree_dragon', 'The Tree Dragon', 'binary_tree_canopy', 'dragon', '#3f9c5a',
    'Wings that fork exactly twice and never rejoin. Two eyes at two heights.',
    [['flank', M_FORK, 40, 18], ['flank', M_FORK, 15, 18]], { swell: [10, 22, 6], taper: -4 }],
  ['path_sum_ent', 'The Path-Sum Ent', 'binary_tree_canopy', 'ent', '#6b8f3f',
    'One arm. A node with one child is not a leaf, and it will not let that go.',
    [['flank', M_ONEARM, 38, 20]], { asym: true, taper: 3, lean: -2, leanK: 1 }],
  ['graph_necromancer', 'The Graph Necromancer', 'graph_wastes', 'necromancer', '#6a4f8f',
    'Skulls at fixed radii. A frontier expands evenly or it is not a frontier.',
    [['chest', M_RINGS, 26, 20]], { scale: 0.95, taper: -2, swell: [20, 30, 4] }],
  ['rolling_titan', 'The Rolling Titan', 'sliding_window_marsh', 'titan', '#3f7f9c',
    'Shoulder plates in strictly descending height. The front one is the answer.',
    [['back', M_MONOTONE, 25, 16]], { lean: 3, leanK: 1, taper: 5 }],
  ['editor_automaton', 'The Editor Automaton', 'matrix_citadel', 'automaton', '#b0763f',
    'Two stacks on its back, and a sentinel plate under the short one.',
    [['back', M_STACKS, 34, 18]], { scale: 0.98, taper: -1, swell: [12, 24, 5] }],
  ['complexity_wyrm', 'The Complexity Wyrm', 'complexity_tower', 'wyrm', '#3f6f9c',
    'Segments that double. The head is constant; by the fourth the tail is the room.',
    [['trail', M_DOUBLING, 24, 40]], { scale: 0.90, taper: 8 }],
  ['serialization_lich', 'The Serialization Lich', 'recursive_forest', 'lich', '#8f3f6f',
    'A ribbon of tokens with the gaps left in. The gaps are half the information.',
    [['chest', M_RIBBON, 23, 28]], { scale: 1.02, swell: [16, 30, 7], taper: -7, lean: 5, leanK: 2 }],
  ['bug_demon', 'The Bug Demon', 'debugging_dungeon', 'demon', '#c43f4f',
    'One horn, one wing, one leg a pixel short. The only thing here that refuses the mirror.',
    [['crown', M_ASYM, 30, 8]], { asym: true, lean: 3, leanK: 2 }],
  ['the_interviewer', 'The Examiner', 'null_kings_castle', 'interviewer', '#d8d8e0',
    'A crown whose band is the top of the skull, a visor with no slit, and a clipboard that is a rectangle of nothing.',
    [['brow', M_BLANK, 28, 12]], { scale: 1.00, taper: 10, swell: [6, 16, 4] }],
];

/* ================================================================
 * §8  THE SEVENTEEN APEXES
 * ================================================================
 * gauntlet/hunters.py is not in the tree yet. These are authored to the brief —
 * one roaming apex per region, thematic to that region's element — and they
 * carry their own ids. If hunters.py lands with different ids, ingestHunters()
 * re-keys them; if it lands with different regions, the element follows the
 * region, because the element always follows the region.
 *
 * An apex is NOT the region's named boss with the serial numbers filed off. The
 * boss is a creature wearing an element; the apex is the element in a body with
 * nothing else going on. That is why every one of them takes its archetype
 * straight from its element and takes its DIFFERENCE from a profile modulation
 * rather than from a motif: an apex has no second idea to express.
 *
 * [id, name, region, mod]
 */
const APEX_ROWS = [
  ['apex_unnamed', 'The Unnamed', 'python_village',
    { taper: 2, lean: 1, leanK: 1 },
    'A shape the erasure went past. It has not been called anything yet.'],
  ['apex_half_formed', 'The Half-Formed', 'fields_of_syntax',
    { taper: -3, swell: [20, 30, 2], lean: 2, leanK: 2 },
    'A sentence that got as far as a body and stopped there.'],
  ['apex_one_key', 'The Keeper of One Key', 'hashmap_highlands',
    { scale: 1.1, taper: 2 },
    'It carries every key and can only ever be holding one.'],
  ['apex_anagram', 'The Anagram', 'stringwood_labyrinth',
    { swell: [16, 26, 4], taper: -4, lean: 3, leanK: 3 },
    'Its limbs are in the wrong order. It has made no difference to it.'],
  ['apex_zeroth', 'The Zeroth', 'array_caverns',
    { taper: -2, swell: [30, 44, 2] },
    'It counts from nothing and it is always one short at the end.'],
  ['apex_frame', 'The Frame', 'sliding_window_marsh',
    { swell: [24, 38, 5], taper: 1 },
    'It widens to the right and shrinks from the left, and never starts again.'],
  ['apex_convergence', 'The Convergence', 'twin_pointer_pass',
    { taper: -6, lean: 3, leanK: 2 },
    'Two of it set out from opposite ends. This is where they met.'],
  ['apex_last_in', 'The Last In', 'stack_queue_mines',
    { scale: 1.08, swell: [8, 20, 3] },
    'Whatever went in most recently is what burns first.'],
  ['apex_quarter_turn', 'The Quarter Turn', 'matrix_citadel',
    { taper: -4, lean: 4, leanK: 1 },
    'It is the floor plan. It has turned ninety degrees and has not told anyone.'],
  ['apex_no_return', 'The Call That Did Not Return', 'recursive_forest',
    { scale: 1.05, taper: -3 },
    'It descended. That is the entire account of it.'],
  ['apex_fork', 'The Fork', 'binary_tree_canopy',
    { swell: [12, 22, 5], taper: -5, lean: 2, leanK: 2 },
    'It goes left and it goes right and the two never speak again.'],
  ['apex_lattice', 'The Lattice', 'graph_wastes',
    { scale: 1.12, swell: [18, 30, 3] },
    'Every part of it is connected to several others, and some of the routes are pointless.'],
  ['apex_already_solved', 'The Already Solved', 'dp_ruins',
    { taper: 6, swell: [34, 48, 6], lean: -3, leanK: 2 },
    'It glows wherever you have already been, and it is free to walk again.'],
  ['apex_repro', 'The Repro', 'debugging_dungeon',
    { taper: -2, swell: [26, 40, 4] },
    'It happens every time, which is the only good thing anyone can say about it.'],
  ['apex_next_floor', 'The Next Floor', 'complexity_tower',
    { scale: 0.94, taper: 6 },
    'Twice the last one. It has not got tired of that yet.'],
  ['apex_clock', 'The Clock', 'coding_coliseum',
    { taper: -4, swell: [10, 18, 4], lean: 2, leanK: 3 },
    'Sand, and a clock, and it is not going to explain the question.'],
  ['apex_unlabelled', 'The Unlabelled', 'null_kings_castle',
    { scale: 1.1, swell: [20, 34, 2] },
    'Nothing on it says what it is. That is not an oversight.'],
];

/* ================================================================
 * §9  THE LAST INTERPRETER
 * ================================================================
 * world.FINAL_TRIAL. See the module header for why this one is different; what
 * follows is how.
 *
 * The coil is GENERATED, not authored, and that is the right call rather than a
 * cheap one: a vast serpent is a curve with a thickness function, ninety-six
 * columns of authored ASCII would be a curve drawn badly by hand, and a curve
 * in code can be cut by the frame edge on purpose.
 */

/* Where the animal goes. The path leaves the box on the left and at the bottom,
 * which no other boss in this game does. */
const COIL = Object.freeze({
  turns: 1.75,        // how many times it crosses the box on the way down
  amp: 30,            // horizontal reach of the coil, in pixels
  top: 12,            // where the body starts
  bottom: 70,         // past the floor of the 64-box. Deliberate: it does not fit
  thick: 11,          // half-thickness at the fattest point
  /* Samples along the path. At the bottom of the box the curve is moving fast
   * sideways, and 150 samples left visible gaps between consecutive discs —
   * the tail read as dust rather than as an animal. 260 closes them. */
  steps: 260,
});

/* The indent stack, in four-column steps, one entry per scale band. This is the
 * sentence "speaks only in Python" written as geometry: each band's seam starts
 * four columns further in than the one above, then four more, then returns to
 * the margin, exactly the way a block opens and closes.
 *
 * PHASE_INDENT[1] is the same stack with three bands out by one — a tab among
 * spaces, which is the most Python way for something to be going wrong.
 * PHASE_INDENT[2] is every band at the margin: the block ended. */
const PHASE_INDENT = Object.freeze([
  Object.freeze([0, 1, 2, 3, 3, 2, 3, 3, 2, 1, 2, 3, 3, 2, 1, 0, 1, 1, 0, 0]),
  Object.freeze([0, 1, 2, 3, 4, 2, 3, 2, 2, 1, 3, 3, 4, 2, 1, 0, 2, 1, 0, 0]),
  Object.freeze([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
]);

const INDENT_STEP = 4;
const BAND_ROWS = 3;

/* The hat. Broad brim, and it is made of the same scale material as the body —
 * it grew, it was not put on. Bone at the brim edge, void underneath, and
 * nothing of the face visible under it but the eye. */
const INTERP_HAT = Object.freeze([
  '..........ooooo..........',
  '.........oBBBBBo.........',
  '........oBBBBBBBo........',
  '.......oBBBBBBBBBo.......',
  '......oBBBBBBBBBBBo......',
  '.....oBBBBBBBBBBBBBo.....',
  '....oBBBBBBBBBBBBBBBo....',
  '..ooBBBBBBBBBBBBBBBBBoo..',
  '.oBBBBBBBBBBBBBBBBBBBBBo.',
  'oCCCCCCCCCCCCCCCCCCCCCCCo',
  'okkkkkkkkkkkkkkkkkkkkkkko',
  '.ooooooooooooooooooooooo.',
]);

/* The head. No nostrils, no brow, no expression: it is not a face that is going
 * to help you. One eye lit, and it is lit by the prompt rather than by the sun
 * this world has. */
const INTERP_HEAD = Object.freeze([
  '...oooooooooo...',
  '..oBBBBBBBBBBo..',
  '.oBBBBBBBBBBBBo.',
  'oBBBBBBBBBBBBBBo',
  'oBBBkUkBBBBBBBBo',
  'oBBkUUUkBBBBBBBo',
  'oBBBkUkBBBBBBBBo',
  '.oBBBBBBBBBBBBo.',
  '..oBBBBBBBBBBo..',
  '...oooooooooo...',
]);

/* The jaw, shut and open. Open is not a roar — it is a prompt being issued. */
const INTERP_JAW = Object.freeze([
  'oBBBBBBBBBBo',
  'oCCCCCCCCCCo',
  '.oooooooooo.',
]);

const INTERP_JAW_OPEN = Object.freeze([
  'oBBBBBBBBBBo',
  'okkkkkkkkkko',
  'okCkCkCkCkCo',
  'okkkkkkkkkko',
  'oCCCCCCCCCCo',
  '.oooooooooo.',
]);

/* The prompt. Three pixels and a chevron each, white, and the brightest thing
 * in a ninety-six pixel frame. Everything else in this module is trying to be
 * large; this is trying to be read. */
const INTERP_PROMPT = Object.freeze([
  'W.W.W..',
  '.W.W.W.',
  'W.W.W..',
  '.......',
  'WWWWWW.',
]);

/* The staff. It is not held — it is grown out of the coil, which is why it is
 * the body's material and not wood. */
const INTERP_STAFF = Object.freeze([
  '..U..',
  '.UUU.',
  'UUuUU',
  '.UUU.',
  '..U..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
  '..g..',
]);

/* Draw the animal. Deterministic in (frame, beat, phase) and nothing else — no
 * rng is used anywhere in here, because a serpent's body is a curve and a curve
 * does not need noise to be interesting. */
function interpreterCells(frame, beat, phase) {
  const w = ART_WIDE_W, h = ART_H;
  const cells = blankCells(w, h);
  const ph = Math.max(0, Math.min(2, phase | 0));

  /* One breath of motion per beat, and the head leads the tail by a third of a
   * cycle — a serpent that moves all at once is a rope. */
  const t0 = (beat % 6) / 6;
  const wob = Math.sin(t0 * Math.PI * 2);
  const lead = Math.sin((t0 + 0.33) * Math.PI * 2);
  const reach = frame === 3 ? 11 : frame === 2 ? -7 : frame === 4 ? -9 : 0;
  /* The coil answers the head rather than following it: on the wind-up the
   * whole animal gathers back and down, on the strike it unloads forward. A
   * telegraph the player can read from across the room is most of what makes
   * the last fight survivable. */
  const gather = frame === 2 ? 3 : frame === 3 ? -4 : frame === 4 ? 2 : 0;

  /* The path. x sweeps across the box and past its left edge; y descends past
   * the bottom. Thickness peaks a third of the way down and tapers to the tail,
   * which is how a real snake is shaped and not how a tube is. */
  const cx = w * 0.52;
  for (let s = 0; s <= COIL.steps; s++) {
    const t = s / COIL.steps;
    const y = COIL.top + t * (COIL.bottom - COIL.top);
    const swing = Math.sin(t * Math.PI * COIL.turns * 2 + wob * 0.25 + gather * 0.06);
    const x = cx + swing * COIL.amp * (0.45 + 0.75 * t) + lead * 2 * (1 - t)
      + gather * 1.6 * (1 - t * 0.5);
    const th = Math.max(3, Math.round(COIL.thick * Math.sin(Math.PI * Math.min(1, 0.18 + t * 0.92))));
    for (let dy = -th; dy <= th; dy++) {
      for (let dx = -th; dx <= th; dx++) {
        if (dx * dx + dy * dy > th * th) continue;
        const px = Math.round(x + dx), py = Math.round(y + dy);
        if (px < 0 || px >= w || py < 0 || py >= h) continue;   // cut by the frame
        cells[py][px] = 'B';
      }
    }
  }

  /* THE SCALES ARE INDENTATION. Every BAND_ROWS rows, a seam, and the seam
   * starts INDENT_STEP columns in for each level of the stack. Read down the
   * left edge of the animal and you are reading a block structure. */
  const stack = PHASE_INDENT[ph];
  const left = leftContour(cells, w, h);
  const right = rightContour(cells, w, h);
  for (let band = 0, y = COIL.top + 2; y < h; y += BAND_ROWS, band++) {
    const lvl = stack[band % stack.length];
    const l = left[y], r = right[y];
    if (l < 0 || r <= l) continue;
    /* The margin mark first. One bone pixel at the true left edge of every
     * band, so the indentation has something to be measured against — the way
     * a ruler down the gutter of a listing is what makes nesting visible at
     * all. The seam then starts at MARGIN + 2 + four per level, which is why
     * it can never land on the mark and erase the thing it is measured from.
     * That collision is exactly what made phase three's collapse invisible the
     * first time this was measured. */
    if (l + 1 < w && cells[y][l + 1] === 'B') cells[y][l + 1] = 'b';
    const x0 = Math.min(r - 1, l + 2 + lvl * INDENT_STEP);
    for (let x = x0; x <= r - 1; x++) {
      if (cells[y][x] === 'B') cells[y][x] = (x === x0) ? 'd' : 'D';
    }
  }

  /* Phase three: the block ended and the whole animal lights from inside. */
  if (ph >= 2) {
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (cells[y][x] === 'D' && ((x + y) & 3) === 0) cells[y][x] = 'u';
      }
    }
  }

  outlinePass(cells, w, h, false);   // false: the frame edge does NOT get an outline

  /* The wizard half, laid on last and in front of the coil. */
  const hx = 4 + reach, hy = 14 + Math.round(lead);
  stampCells(cells, w, h, INTERP_HEAD, hx, hy);
  stampCells(cells, w, h, frame === 3 ? INTERP_JAW_OPEN : INTERP_JAW, hx + 2, hy + 9);
  stampCells(cells, w, h, INTERP_HAT, hx - 5, hy - 11);
  stampCells(cells, w, h, INTERP_STAFF, w - 12, 6 + Math.round(wob));

  /* And the three pixels that win. Placed in front of the mouth, never behind
   * anything, and always the last thing written. */
  stampCells(cells, w, h, INTERP_PROMPT, hx + 17, hy + 8 + (frame === 3 ? 2 : 0));

  return cells;
}

/* ================================================================
 * §10  RESOLUTION, AND THE FALLBACK THAT DOES NOT LIE
 * ================================================================ */

function makeLook(row) { return Object.freeze(row); }

const LOOKS = {};

/* Named bosses. */
for (const [id, name, region, sprite, colour, note, motifs, mod] of NAMED_ROWS) {
  const reg = REGION_LOOK[region];
  LOOKS[id] = makeLook({
    id, name, kind: 'named', region,
    element: reg ? reg.element : 'NEUTRAL',
    archetype: archetypeFor(reg ? reg.element : 'NEUTRAL'),
    sprite, colour,
    /* The accent is what phase three mixes into the body to light it from
     * inside, so an accent equal to the boss's own colour is a boss whose
     * final phase does nothing. Four of the fourteen had exactly that — the
     * region accent in world.py is sometimes the boss colour — so the element
     * leads and the region is the fallback, not the other way round. */
    accent: accentFor(colour, reg ? reg.element : 'NEUTRAL', reg),
    core: CORES[archetypeFor(reg ? reg.element : 'NEUTRAL')] || CORES.neutral,
    /* Every named boss carries its own profile modulation, so no two of the
     * fourteen share a study body even where they share a region and an
     * element — the Tree Dragon and the Path-Sum Ent both live in the canopy
     * and both are neutral, and two identical silhouettes in one playthrough
     * is a defect the player can see. */
    mod: Object.freeze(mod || { taper: 0 }),
    motifs: Object.freeze(motifs.map(([slot, grid, ox, oy]) =>
      Object.freeze({ slot, grid, ox, oy }))),
    note, wide: false, fallback: false, resolvedFrom: id,
  });
}

/* Apexes. */
for (const [id, name, region, mod, note] of APEX_ROWS) {
  const reg = REGION_LOOK[region];
  const element = reg ? reg.element : 'NEUTRAL';
  LOOKS[id] = makeLook({
    id, name, kind: 'apex', region, element,
    archetype: archetypeFor(element),
    sprite: 'apex',
    colour: (reg && reg.accent) || ELEMENT_LOOK[element].colour,
    accent: ELEMENT_LOOK[element].colour,
    core: CORES[archetypeFor(element)] || CORES.neutral,
    mod: Object.freeze(mod),
    motifs: Object.freeze([]),
    note, wide: false, fallback: false, resolvedFrom: id,
  });
}

/* The last interpreter. Its own kind, because nothing about it shares a path
 * with the rest of the roster. */
LOOKS.the_last_interpreter = makeLook({
  id: 'the_last_interpreter',
  name: 'THE LAST INTERPRETER',
  kind: 'final',
  region: 'null_kings_castle',
  /* VOID by region, and it takes void's refusal of the rim — but not void's
   * hollow verb, because this one is not an absence. It is extremely present.
   * The verb is suppressed by `dress: false` and the light law is kept. */
  element: 'VOID',
  archetype: 'interpreter',
  sprite: 'interpreter',
  colour: '#3f7f5a',              // world.FINAL_TRIAL.colour
  accent: '#e8c37d',              // world.FINAL_TRIAL.accent
  core: [30, 24],
  mod: Object.freeze({}),
  motifs: Object.freeze([]),
  dress: false,
  note: 'A python at the scale where the room is a consequence of the animal. '
      + 'It is also, without any apparent contradiction, a wizard.',
  wide: true, fallback: false, resolvedFrom: 'the_last_interpreter',
});

/* Pick an accent that is actually a contrast with the body colour. */
function accentFor(colour, element, reg) {
  const el = ELEMENT_LOOK[element] || ELEMENT_LOOK.NEUTRAL;
  const same = (a, b) => String(a).toLowerCase() === String(b).toLowerCase();
  if (!same(el.colour, colour)) return el.colour;
  if (reg && !same(reg.accent, colour)) return reg.accent;
  return el.dark;
}

function archetypeFor(element) {
  switch (String(element || '').toUpperCase()) {
    case 'FIRE': return 'fire';
    case 'COLD': return 'cold';
    case 'POISON': return 'poison';
    case 'BRUTE': return 'brute';
    case 'LIGHTNING': return 'lightning';
    case 'VOID': return 'void';
    default: return 'neutral';
  }
}

/* Region looks are looks too: they are what an unknown id in a known region
 * becomes, and they are named after the REGION rather than after any boss, so
 * a fallback can never be mistaken for a specific creature. */
for (const rid of REGION_IDS) {
  const reg = REGION_LOOK[rid];
  LOOKS[`region:${rid}`] = makeLook({
    id: `region:${rid}`,
    name: `Something in ${rid.replace(/_/g, ' ')}`,
    kind: 'region', region: rid, element: reg.element,
    archetype: archetypeFor(reg.element),
    sprite: 'region',
    colour: reg.accent, accent: ELEMENT_LOOK[reg.element].colour,
    core: CORES[archetypeFor(reg.element)] || CORES.neutral,
    mod: Object.freeze({ taper: 0 }),
    motifs: Object.freeze([]),
    note: reg.note, wide: false, fallback: true, resolvedFrom: rid,
  });
}

/* The last resort: no id, no region, nothing. Neutral, plain, and honest about
 * being a placeholder. It is never returned for an id that HAS a region. */
export const FALLBACK_LOOK = makeLook({
  id: 'unknown', name: 'Unidentified', kind: 'region', region: '',
  element: 'NEUTRAL', archetype: 'neutral', sprite: 'region',
  colour: ELEMENT_LOOK.NEUTRAL.colour, accent: ELEMENT_LOOK.NEUTRAL.dark,
  core: CORES.neutral, mod: Object.freeze({ taper: 0 }), motifs: Object.freeze([]),
  note: 'Nothing in world.py answers to this name.',
  wide: false, fallback: true, resolvedFrom: '',
});

/* Aliases. world.py's sprite keys, bosses.js's archetype keys, and the handful
 * of names the story bible uses for the final trial all land somewhere. Where a
 * sprite key is shared by two bosses — "titan" is both the Hash Titan and the
 * Rolling Titan — the alias points at the FIRST and the caller is expected to
 * pass the id, which is why bossLook takes a region hint. */
export const ART_ALIAS = Object.freeze({
  titan: 'hash_titan', hydra: 'three_sum_hydra', wraith: 'window_wraith',
  behemoth: 'twin_behemoth', golem: 'matrix_golem', dragon: 'tree_dragon',
  ent: 'path_sum_ent', necromancer: 'graph_necromancer',
  automaton: 'editor_automaton', wyrm: 'complexity_wyrm',
  lich: 'serialization_lich', demon: 'bug_demon',
  interviewer: 'the_interviewer', knight: 'the_interviewer',
  colossus: 'rolling_titan',
  interpreter: 'the_last_interpreter', python_wizard: 'the_last_interpreter',
  serpent: 'the_last_interpreter', last_interpreter: 'the_last_interpreter',
});

export const NAMED_IDS = Object.freeze(NAMED_ROWS.map(r => r[0]));
export const APEX_IDS = Object.freeze(APEX_ROWS.map(r => r[0]));
export const FINAL_ID = 'the_last_interpreter';
export const ART_KINDS = Object.freeze(['named', 'apex', 'final', 'region']);

/** The strict form: is this an authored look. */
export function lookFor(id) {
  const k = String(id || '');
  return LOOKS[k] || LOOKS[ART_ALIAS[k]] || null;
}

/** The region's apex. Always returns something. */
export function apexFor(regionId) {
  const rid = String(regionId || '');
  for (const row of APEX_ROWS) if (row[2] === rid) return LOOKS[row[0]];
  return LOOKS[`region:${rid}`] || FALLBACK_LOOK;
}

/**
 * Resolve anything to a look. Never throws.
 *
 * The order matters and is the whole of rule F. An exact id wins. An alias
 * wins next. Then — and only then — a REGION, either handed in by the caller
 * or read off the id itself if the id happens to be a region. What is
 * deliberately absent is any kind of fuzzy match onto a named boss: an
 * unrecognised string must never come back as the Hash Titan, because a fight
 * that silently draws the wrong boss is worse than one that draws a shape.
 *
 * Everything that comes back from the fallback path carries fallback: true and
 * resolvedFrom, so a caller that wants to complain has something to say.
 */
export function bossLook(idOrKey, opts = {}) {
  const k = String(idOrKey || '');
  const exact = LOOKS[k];
  if (exact) return exact;
  const aliased = LOOKS[ART_ALIAS[k]];
  if (aliased) {
    // An alias plus a region hint disambiguates the shared sprite keys.
    const hint = String(opts.region || '');
    if (hint && aliased.region !== hint) {
      for (const row of NAMED_ROWS) {
        if (row[3] === k && row[2] === hint) return LOOKS[row[0]];
      }
    }
    return aliased;
  }
  const region = String(opts.region || '');
  if (REGION_LOOK[region]) {
    const l = LOOKS[`region:${region}`];
    return l ? Object.freeze(Object.assign({}, l, { resolvedFrom: k || region })) : FALLBACK_LOOK;
  }
  if (REGION_LOOK[k]) return LOOKS[`region:${k}`];
  return FALLBACK_LOOK;
}

/** Every authored look, in roster order. Named, then apexes, then the final. */
export function allLooks() {
  return NAMED_IDS.map(id => LOOKS[id])
    .concat(APEX_IDS.map(id => LOOKS[id]))
    .concat([LOOKS[FINAL_ID]]);
}

/** Motif stamps for a look. Always an array, possibly empty — a fallback has
 *  none, on purpose: it does not get to claim an identity it does not have. */
export function motifsFor(look) {
  return (look && look.motifs) || [];
}

/**
 * Take the roster from gauntlet/hunters.py when that file lands.
 *
 * Accepts anything array-like of {id, name, region}. Rows whose region this
 * module knows are re-keyed onto the authored apex for that region — the art
 * stays, the identity becomes the server's. Rows for a region that already has
 * its apex claimed are added as their own look rather than overwriting one, and
 * rows with no usable region are ignored rather than guessed at.
 *
 * Returns how many rows were taken. Never throws on a malformed row.
 */
export function ingestHunters(rows) {
  if (!rows || typeof rows.length !== 'number') return 0;
  let taken = 0;
  const claimed = new Set();
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    if (!row || typeof row !== 'object') continue;
    const id = String(row.id || '');
    const region = String(row.region || '');
    if (!id || !REGION_LOOK[region]) continue;
    const base = claimed.has(region) ? LOOKS[`region:${region}`] : apexFor(region);
    claimed.add(region);
    LOOKS[id] = makeLook(Object.assign({}, base, {
      id, name: String(row.name || base.name), kind: 'apex',
      region, fallback: false, resolvedFrom: id,
      note: String(row.note || row.blurb || base.note),
    }));
    taken++;
  }
  if (taken) clearBossArtCache();
  return taken;
}

/* ================================================================
 * §11  RENDERING
 * ================================================================ */

/* The working set a fight actually has is one creature at one phase: five
 * frames, six beats on the two idle ones, sixteen canvases. The cap is sized
 * for the pathological case instead — the entire roster at one phase, which is
 * what a codex screen or an art harness asks for — because a cache that thrashes
 * under the widest legitimate call is a cache that will thrash in front of
 * somebody eventually. 32 looks x 16 = 512. */
const CACHE_MAX = 512;
const spriteCache = new Map();

function cacheGet(key) {
  const hit = spriteCache.get(key);
  if (hit === undefined) return null;
  // Touch: most-recently-used goes to the back, so the eviction below takes the
  // coldest entry rather than the oldest-created one.
  spriteCache.delete(key);
  spriteCache.set(key, hit);
  return hit;
}

function cachePut(key, value) {
  spriteCache.set(key, value);
  while (spriteCache.size > CACHE_MAX) {
    const coldest = spriteCache.keys().next();
    if (coldest.done) break;
    spriteCache.delete(coldest.value);
  }
  return value;
}

export function clearBossArtCache() { spriteCache.clear(); }

export function bossArtStats() {
  return {
    version: BOSSART_VERSION,
    cache: spriteCache.size,
    cap: CACHE_MAX,
    /* `authored` is creatures; `total` also counts the seventeen region looks,
     * which exist only so an unknown id has somewhere plausible to land. */
    authored: NAMED_IDS.length + APEX_IDS.length + 1,
    total: Object.keys(LOOKS).length,
    named: NAMED_IDS.length,
    apexes: APEX_IDS.length,
    regions: REGION_IDS.length,
    glyphs: ART_GLYPHS.length,
    maxColours: MAX_COLOURS,
  };
}

/* The grid for one look at one frame/phase/beat, before rasterising. Exported
 * because the harness measures grids as well as pixels, and because bosses.js
 * may want the grid rather than the canvas. */
export function lookGrid(look, opts = {}) {
  const lk = look || FALLBACK_LOOK;
  const frame = Math.max(0, Math.min(4, opts.frame | 0));
  const beat = ((opts.beat | 0) % 6 + 6) % 6;
  const phase = Math.max(0, Math.min(2, opts.phase | 0));

  if (lk.archetype === 'interpreter') {
    return gridOf(interpreterCells(frame, beat, phase));
  }

  const w = lk.wide ? ART_WIDE_W : ART_W;
  const h = ART_H;
  let cells = bodyCells(lk.archetype, lk.mod, w, h);

  /* The action frames are authored as deformations of the same body rather than
   * as second drawings: the wind-up leans back and compresses, the attack leans
   * forward and extends. A frame that differs by a few units of brightness is
   * not a frame, which is the rule petart.js is held to and the same one here. */
  if (frame === 2 || frame === 3 || frame === 4) {
    const lean = frame === 2 ? -3 : frame === 3 ? 4 : -2;
    const sink = frame === 2 ? 1 : frame === 3 ? -2 : 2;
    const out = blankCells(w, h);
    for (let y = 0; y < h; y++) {
      const k = 1 - (y / h);
      const dx = Math.round(lean * k * k);
      const dy = Math.round(sink * k);
      for (let x = 0; x < w; x++) {
        if (isEmpty(cells[y][x])) continue;
        const tx = x + dx, ty = y + dy;
        if (tx < 0 || tx >= w || ty < 0 || ty >= h) continue;
        out[ty][tx] = cells[y][x];
      }
    }
    cells = out;
  }

  // The idle beat: one row of breath through the upper mass, and nothing else.
  if (frame <= 1) {
    const rise = (beat === 1 || beat === 2) ? 1 : (beat === 4 || beat === 5) ? -1 : 0;
    if (rise) {
      const out = blankCells(w, h);
      for (let y = 0; y < h; y++) {
        const ty = y < h * 0.5 ? Math.max(0, Math.min(h - 1, y - rise)) : y;
        for (let x = 0; x < w; x++) if (!isEmpty(cells[y][x])) out[ty][x] = cells[y][x];
      }
      cells = out;
    }
  }

  outlinePass(cells, w, h, true);

  // The face, and then the motifs, merged before anything is lit.
  const face = FACES[lk.archetype] || FACES.neutral;
  const [fx, fy] = faceAnchor(cells, w, h);
  stampCells(cells, w, h, face, fx - 3, fy + 2);
  const rig = RIGS[lk.archetype] || RIGS.neutral;
  stampCells(cells, w, h, rig.grid, fx + rig.ox, fy + 6 + rig.oy);
  for (const m of motifsFor(lk)) stampCells(cells, w, h, m.grid, m.ox, m.oy);

  let grid = gridOf(cells);
  if (lk.dress !== false) grid = dressGrid(grid, lk, { frame, beat, phase, seed: 0 });
  return grid;
}

/**
 * One look, one frame, one phase, one beat, as a canvas. Cached under a cap and
 * deterministic forever: the same apex carries the same spurs in every session.
 */
export function lookSprite(lookOrId, opts = {}) {
  const lk = (lookOrId && typeof lookOrId === 'object') ? lookOrId : bossLook(lookOrId, opts);
  const frame = Math.max(0, Math.min(4, opts.frame | 0));
  const beat = ((opts.beat | 0) % 6 + 6) % 6;
  const phase = Math.max(0, Math.min(2, opts.phase | 0));
  const key = `${lk.id}|${frame}|${phase}|${beat}|${opts.colour || ''}`;
  const hit = cacheGet(key);
  if (hit) return hit;

  const w = lk.wide ? ART_WIDE_W : ART_W;
  let grid = lookGrid(lk, { frame, beat, phase });

  /* Merge, then light, once. applyRim resolves the undecided body mass from the
   * silhouette; rimLowLeft then paints the cast's one hot low source INSIDE the
   * outline — unless this look refuses it, which void and the interpreter do.
   *
   * The protect string is the point of the second argument: the element's own
   * marks, the prompt, the eyes and the bone are already the brightest things
   * they are going to be, and a rim pass that overwrote them would delete a
   * feature every time the light moved. */
  grid = applyRim(normalise(grid, w));
  if (wantsRim(lk) && lk.archetype !== 'interpreter') {
    grid = rimLowLeft(grid, 'Q', 'rRuUiWkaAbCzZGM');
  }

  const pal = lookPalette(lk.colour ? Object.assign({}, lk, { colour: opts.colour || lk.colour }) : lk, phase);
  const canvas = gridSprite(grid, pal, w, ART_H);
  return cachePut(key, canvas);
}

/** Every canvas one phase of one look can ask for, in one call. A caller that
 *  warms this at phase change never generates inside the render loop. */
export function warmLook(lookOrId, phase = 0) {
  const lk = (lookOrId && typeof lookOrId === 'object') ? lookOrId : bossLook(lookOrId);
  let n = 0;
  for (let f = 0; f < 5; f++) {
    const beats = f <= 1 ? 6 : 1;
    for (let b = 0; b < beats; b++) { lookSprite(lk, { frame: f, beat: b, phase }); n++; }
  }
  return n;
}

/** The readability check, colour discarded. If it does not read at 16px it does
 *  not read, and no amount of interior shading will save it. */
export function lookSilhouette(lookOrId, opts = {}) {
  const lk = (lookOrId && typeof lookOrId === 'object') ? lookOrId : bossLook(lookOrId, opts);
  return silhouetteAt(lookGrid(lk, opts), opts.box || 16);
}

/* ================================================================
 * §12  METADATA FOR THE STAGING
 * ================================================================ */

/** How this thing moves. Element sets the register; kind sets the weight. An
 *  apex is the element and moves like it; a named boss is an animal and is
 *  slower; the final is slower than anything. */
export function lookMotion(lookOrId) {
  const lk = (lookOrId && typeof lookOrId === 'object') ? lookOrId : bossLook(lookOrId);
  const m = elementLook(lk.element).motion;
  const heavy = lk.kind === 'named' ? 1.25 : lk.kind === 'final' ? 1.9 : 1;
  return Object.freeze({
    key: lk.id,
    bob: Math.max(1, Math.round(m.bob / (lk.kind === 'final' ? 1.5 : 1))),
    sway: m.sway,
    period: Math.round(m.period * heavy),
    telegraph: Math.round(m.telegraph * heavy),
    anim: lk.kind === 'final' ? 'coil' : m.anim,
    floats: lk.element === 'VOID',
    wide: !!lk.wide,
    phase: (hash(lk.id) % 100) / 100,     // a stable, id-derived offset, never a clock
  });
}

/** Stage lighting in the look's own colours. Plain hex, ready for a gradient. */
export function lookLighting(lookOrId, colour) {
  const lk = (lookOrId && typeof lookOrId === 'object') ? lookOrId : bossLook(lookOrId);
  const el = elementLook(lk.element);
  const base = colour || lk.colour || el.colour;
  const r = ramp(base);
  const mark = RAMPS[el.mark] || RAMPS.ember;
  return Object.freeze({
    key: lk.id,
    element: el.id,
    colour: base,
    accent: lk.accent || el.dark,
    /* Void gets no rim and no glow, and the fields still exist so a caller does
     * not have to branch: they are simply the ambient, which is the honest
     * answer to "what colour is the light coming off this". */
    rim: el.light.rim ? rimTone(r.light2, 0.5) : mix(r.shadow2, '#0a0910', 0.5),
    glow: el.light.rim ? mix(r.light2, '#ffffff', 0.3) : mix(r.shadow1, '#0b0a12', 0.6),
    ember: mark[SHADE.LIGHT],
    ambient: mix(r.shadow2, '#0a0910', 0.55),
    fog: mix(r.shadow1, '#0e0c16', 0.72),
    floor: mix(r.shadow2, '#141220', 0.6),
  });
}

/** One dry line about what the player is looking at. Used by the codex and the
 *  boss title card; never used to make an art decision. */
export function describe(lookOrId) {
  const lk = (lookOrId && typeof lookOrId === 'object') ? lookOrId : bossLook(lookOrId);
  const el = elementLook(lk.element);
  const reg = REGION_LOOK[lk.region];
  return {
    id: lk.id, name: lk.name, kind: lk.kind,
    element: el.id, elementName: el.name,
    region: lk.region, regionTexture: reg ? reg.texture : '',
    habit: el.habit, verb: el.verb,
    note: lk.note,
    fallback: !!lk.fallback,
  };
}

/* ================================================================
 * SELF CHECK
 * ================================================================
 * Cheap enough to run at module load in a dev build and by the harness always.
 * It answers the questions this file can answer about itself; the ones about
 * pixels belong to scripts/verify/bossart.mjs, which rasterises.
 */
export function bossArtSelfCheck(bossGlyphs, boxes) {
  const problems = [];

  if (bossGlyphs && String(bossGlyphs) !== ART_GLYPHS) {
    problems.push(`glyph table drift: bosses.js has ${bossGlyphs}`);
  }
  /* The ladder, if the caller hands it over. Optional because the check is
   * older than the third rung and every existing caller passes one argument. */
  if (boxes) {
    const want = { w: ART_W, h: ART_H, wide: ART_WIDE_W, finalW: ART_FINAL_W, finalH: ART_FINAL_H };
    for (const k of Object.keys(want)) {
      if (boxes[k] !== undefined && boxes[k] !== want[k]) {
        problems.push(`box drift: ${k} is ${boxes[k]} in bosses.js, ${want[k]} here`);
      }
    }
  }
  if (REGION_IDS.length !== 17) problems.push(`regions: ${REGION_IDS.length}, expected 17`);
  if (NAMED_IDS.length !== 14) problems.push(`named bosses: ${NAMED_IDS.length}, expected 14`);
  if (APEX_IDS.length !== 17) problems.push(`apexes: ${APEX_IDS.length}, expected 17`);

  // Every region has exactly one apex.
  const byRegion = {};
  for (const row of APEX_ROWS) byRegion[row[2]] = (byRegion[row[2]] || 0) + 1;
  for (const rid of REGION_IDS) {
    if (byRegion[rid] !== 1) problems.push(`region ${rid} has ${byRegion[rid] || 0} apexes`);
  }
  // Every named boss sits in a region this module knows.
  for (const row of NAMED_ROWS) {
    if (!REGION_LOOK[row[2]]) problems.push(`boss ${row[0]} in unknown region ${row[2]}`);
  }
  // Every profile is exactly one box tall.
  for (const k of Object.keys(PROFILE)) {
    if (PROFILE[k].length !== ART_H) problems.push(`profile ${k} is ${PROFILE[k].length} rows`);
  }
  // Every authored grid in the file uses only the shared glyph table.
  const grids = [M_KEYRING, M_STUMPS, M_FRAME, M_HORNS, M_GRID, M_FORK, M_ONEARM,
    M_RINGS, M_MONOTONE, M_STACKS, M_DOUBLING, M_RIBBON, M_ASYM, M_BLANK,
    INTERP_HAT, INTERP_HEAD, INTERP_JAW, INTERP_JAW_OPEN, INTERP_PROMPT, INTERP_STAFF]
    .concat(Object.keys(FACES).map(k => FACES[k]))
    .concat(Object.keys(RIGS).map(k => RIGS[k].grid));
  for (const g of grids) {
    const stray = strayGlyphs(g);
    if (stray.length) problems.push(`stray glyphs ${JSON.stringify(stray)}`);
  }
  /* Every glyph in the table has a colour. This is the check that matters most
   * in this file: drawGrid skips an unknown glyph SILENTLY, so a missing entry
   * does not throw, it renders a transparent hole that nobody notices until a
   * player sees through a boss. 'X' was missing when this check was written. */
  {
    const pal = lookPalette(allLooks()[0], 0);
    for (const ch of ART_GLYPHS) if (!pal[ch]) problems.push(`palette has no colour for '${ch}'`);
  }
  /* The dict-side budget is a REPORT, not the gate. Fifteen colours is a rule
   * about a rendered sprite (docs/08 rule 1), and a palette is not a sprite —
   * bosses.bossPalette carries thirty-eight keys and well over fifteen values
   * and is inside budget, because no single creature paints all of them. The
   * gate is scripts/verify/bossart.mjs, which counts off the raster. What is
   * checked here is only that the dict has not run away entirely. */
  for (const lk of allLooks()) {
    for (let ph = 0; ph < 3; ph++) {
      const n = paletteColours(lookPalette(lk, ph));
      if (n > MAX_COLOURS + 5) problems.push(`${lk.id} phase ${ph}: ${n} palette colours`);
    }
  }
  // The fallback must not be a named boss.
  const junk = bossLook('__no_such_thing__');
  if (!junk.fallback) problems.push('unknown id did not come back flagged');
  if (NAMED_IDS.includes(junk.id)) problems.push('unknown id resolved to a named boss');

  return { ok: problems.length === 0, problems };
}
