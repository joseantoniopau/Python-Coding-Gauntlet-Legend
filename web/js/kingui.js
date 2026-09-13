/* The Null King, on your map.
 *
 * THE BRIEF, in the player's words: "make the python dialogue have good
 * graphics and pop up on your world map each time he talks to you".
 *
 * WHAT THIS IS NOT. It is not a dialogue system, it is not a cutscene, and it
 * is not a menu. gauntlet/antagonist.py decides WHEN he speaks and WHAT he
 * says; this file is the half that module cannot do — putting the thing in the
 * field you are standing in, drawing it wrong enough that you know it is not an
 * NPC, and then getting out of the way.
 *
 * HE IS NEVER LOUD. That is the whole direction and it is the easiest one to
 * lose. Everything below is chosen against the same test: a villain who
 * interrupts with a full-screen flourish is a villain you learn to dismiss. So
 *
 *   - he does not arrive with a flash, a sting, a shake or a zoom;
 *   - he does not move once he is there, because a projection does not walk;
 *   - he never covers the player, an exit or a marker — twice over, by where he
 *     is placed and by where he sorts (see PLACEMENT and A below);
 *   - he cannot be waited for: `blocking` is refused if a payload ever sends
 *     it, there is no key he requires, and nothing here touches input;
 *   - and if you walk away he is simply not there any more.
 *
 * GREEN IS HIM. docs/09-story-bible.md §2 VIII: the small green sphere the
 * player has been picking up since Chapter II is a pointer, and everyone who
 * was holding one was being INDEXED. gauntlet/finale.py calls that green
 * #6ee08a and calls it "the only green in here". So the green in this file is
 * not a colour choice. It is the same object, and the player has been seeing it
 * for nine chapters without knowing what it was:
 *
 *   - the rim light on his body is green, where every other body in the game is
 *     lit low-left in amber (sprites.RIM_LIGHT #ffab5e). One lamp in the scene
 *     disagrees with the sun, and it is him;
 *   - the glyph in his visor is an index sphere with a number in it;
 *   - the panel carries the same sphere, with the same number, which is your
 *     entry number rather than a decoration;
 *   - and at the registers where he has started looking at you rather than at
 *     your file, that green lands ON YOUR SPRITE as four corner brackets and a
 *     scan bar. You are the thing the pointer points at.
 *
 * HOW HE IS DRAWN WRONG (B). Five decisions, none of them an alpha value:
 *
 *   1  NO SHADOW. Every body in this world sits on a groundShadow. His ground
 *      point is empty. Nothing else on the screen does that.
 *   2  CUT OFF. The sprite is authored at 24x40 and lower registers keep only
 *      the top N rows, dithered out over the last few. He is a head and a
 *      shoulder line with nothing underneath.
 *   3  SCANLINES. Whole rows of him are absent, on a period that thins as he
 *      escalates, rolling downward one row at a time. A broken raster.
 *   4  THE TILES SHOW THROUGH. One globalAlpha for the whole body, so the grass
 *      reads through him and the colour count does not multiply.
 *   5  HE DOES NOT ANIMATE. No bob, no breath, no idle. Everything else in the
 *      frame is moving and he is not.
 *
 * ESCALATION IS MEASURED, NOT ASSERTED (C). REGISTERS mirrors
 * antagonist.REGISTERS — the same five ids, the same floors, the same hold
 * times, and its `presence` sentence turned into numbers. Painted coverage
 * rises 11 -> 19 -> 26 -> 34 -> 40 rows of a 40-row figure while the scanline
 * gap thins 2 -> 3 -> 4 -> 7, and he closes 6.5 -> 4.5 -> 3.0 -> 2.0 tiles.
 * scripts/verify/kingui.mjs counts the pixels rather than trusting this
 * paragraph.
 *
 * THE PANEL (D). transform.js gives the player's triumph chrome-bevel
 * lettering: a hard drop shadow, a light face over a dark face, an album
 * sleeve. His register is the opposite of a triumph and the panel is the
 * opposite of that treatment — a ruled box, one flat face, a monospaced hand
 * this file draws itself pixel by pixel, an index sphere in the gutter, and no
 * portrait. The villagers' box has a face in it. His never will.
 *
 * NOTHING HERE ALLOCATES PER FRAME. The figure is cached per (register, roll
 * phase), the lettering is typeset once per distinct message, and both caches
 * are capped. With nobody speaking, every path in this file is one null check
 * on the caller's side and this module is never entered at all (F).
 *
 * No Math.random and no Date.now: every varying number is hashed from its
 * inputs or handed in by the caller's clock.
 */
import { RAMPS, OUTLINE, mix } from './palette.js';
import { applyRim, rimLowLeft, normalise, HERO_W, HERO_H } from './sprites.js';

/* ------------------------------------------------------------------ basics */

export const KING_GREEN = '#6ee08a';     // gauntlet/finale.py, the Green Index

/* THE GREEN INDEX, five steps, deep to specular, anchored on that one hex.
 *
 * palette.js has no ramp for it: `venom` is a warm olive authored for poison
 * and reads as slime rather than as glass. These five are authored here and
 * IDENTICALLY in web/js/unmakingfx.js — the spell pass, which is him TAKING
 * where this file is him ARRIVING — so the sphere in his visor, the sphere in
 * this panel, and the green that comes off your armour at the end are all the
 * same object rather than three near misses. Neither file imports the other:
 * the anchor is the shared thing and scripts/verify/unmakingfx.mjs compares
 * INDEX_GREEN_HEX against KING_GREEN live and fails if either ever drifts. */
export const INDEX_RAMP = Object.freeze([
  '#0e1d12', '#22452b', '#428653', '#6ee08a', '#bff1cc',
]);

export const KING_W = 24;
export const KING_H = 40;
const TILE = 16;
const TAU = Math.PI * 2;

/* FNV-1a, the same one overworld.js and sprites.js use. Anything that varies
 * varies off this rather than off a roll, so two runs of the same state draw
 * the same frame. */
function hash(str) {
  let h = 2166136261;
  const s = String(str);
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function hash2(x, y) {
  let h = Math.imul((x | 0) + 0x9e37, 374761393) ^ Math.imul((y | 0) + 0x85eb, 668265263);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

function make(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0);
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

/* Caches are working sets, not archives — sprites.js's rule, same shape. */
function capCache(map, max) {
  while (map.size > max) {
    const oldest = map.keys().next();
    if (oldest.done) break;
    map.delete(oldest.value);
  }
  return map;
}

/* ------------------------------------------------------- the five registers
 *
 * antagonist.REGISTERS, mirrored. `floor`, `ms` and `presence` are that file's
 * own values, copied so a client with no server can still stage him, and
 * adoptPayload() lets the engine overwrite them at runtime — which is what
 * stops a copy from quietly drifting away from the module that owns it.
 *
 * The rest is this file's reading of `presence`, stated as numbers:
 *
 *   rows      how much of the 40-row figure exists, from the top down.
 *             UNCOUNTED is ZERO, because antagonist.py says of it "a line of
 *             text across the top of the frame, unvoiced, NO PORTRAIT". At the
 *             bottom register there is no body on the map at all — the words
 *             arrive and nothing is standing anywhere. That is the quietest
 *             thing in the file and it is the first thing the player meets.
 *   scanGap   one row in every `scanGap` is missing. 2 is half of him.
 *   solidity  the single globalAlpha the whole body is painted at.
 *   tiles     how far from the player he stands.
 *   edge      how hard placement pushes him toward the rim of the frame rather
 *             than toward the player's facing: 1 is "at the edge of the frame",
 *             0 is "in front of you". NOTICED is a silhouette at the edge;
 *             UNQUIET is centred, which is antagonist.py's word.
 *   flat      draw the body with no interior shading — a silhouette. Only
 *             NOTICED, whose presence sentence asks for one in so many words.
 */
export const REGISTERS = {
  UNCOUNTED: { id: 'UNCOUNTED', index: 0, floor: 0,  ms: 3200,
    rows: 0,  scanGap: 0, solidity: 0,    tiles: 0,   edge: 1,    flat: false,
    presence: 'a line of text across the top of the frame, unvoiced, no portrait' },
  NOTICED:   { id: 'NOTICED',   index: 1, floor: 20, ms: 3600,
    rows: 22, scanGap: 2, solidity: 0.30, tiles: 6.5, edge: 1,    flat: true,
    presence: 'a line of text and a silhouette at the edge of the frame' },
  PRECISE:   { id: 'PRECISE',   index: 2, floor: 42, ms: 4200,
    rows: 28, scanGap: 3, solidity: 0.46, tiles: 4.5, edge: 0.6,  flat: false,
    presence: 'a portrait at quarter height, still, while the text runs' },
  ATTENTIVE: { id: 'ATTENTIVE', index: 3, floor: 66, ms: 5000,
    rows: 34, scanGap: 4, solidity: 0.64, tiles: 3.0, edge: 0.25, flat: false,
    presence: 'a portrait at half height, unmoving, holding after the text ends' },
  UNQUIET:   { id: 'UNQUIET',   index: 4, floor: 86, ms: 5600,
    rows: 40, scanGap: 7, solidity: 0.84, tiles: 2.0, edge: 0,    flat: false,
    presence: 'full portrait, centred, no animation at all' },
};

export const REGISTER_IDS = ['UNCOUNTED', 'NOTICED', 'PRECISE', 'ATTENTIVE', 'UNQUIET'];

/* antagonist.register_for, to the letter: monotone, no hysteresis. */
export function registerFor(standing) {
  const n = Number(standing);
  if (!Number.isFinite(n)) return 'UNCOUNTED';
  let chosen = 'UNCOUNTED';
  for (const rid of REGISTER_IDS) if (n >= REGISTERS[rid].floor) chosen = rid;
  return chosen;
}

/* The register at which the green stops being about his body and starts
 * landing on yours. He has begun addressing the person rather than the file. */
const INDEX_FROM = 2;

/* How long the fades are, how far you may walk, how fast he is read out. None
 * of these are tuning knobs the engine gets to move: they are the difference
 * between weather and an interruption. */
const FADE_IN = 0.45;
const FADE_OUT = 0.55;
const LEAVE_FAST = 0.22;         // walked away, or walked into him
const LEASH_PX = TILE * 5;       // move this far from where he found you and he is gone
const CHARS_PER_SECOND = 44;
const SCAN_PHASES = 4;
const SCAN_RATE = 5.5;           // rows per second the missing lines roll down

/* --------------------------------------------------------------- the figure
 *
 * 24x40, authored once. Taller than the hero (16x24), shorter than a boss map
 * form (48x48): he is a person's shape with the proportions slightly wrong,
 * which is the point.
 *
 * A flat bar over the head where a crown would be — a rule, not jewellery. A
 * smooth mask with no features but a slot. In the slot, an index sphere. Below
 * it a mantle with no arms and no hands, tapering, and then not ending: the
 * last eight rows fray into loose pixels and there is nothing at the ground
 * point. He is not standing in a field in the Fields of Syntax.
 *
 * 'B' and 'o' are sprites.applyRim's glyphs and 'R' is sprites.rimLowLeft's, so
 * the body is shaded by the same rig as every other character in the game —
 * and then the rim is handed the wrong colour on purpose.
 */
const KING_GRID = [
  '........................',
  '......oooooooooooo......',
  '......oMMMMMMMMMMo......',
  '.......oMMMMMMMMo.......',
  '.......oMsSSSSsMo.......',
  '.......oMSSSSSSMo.......',
  '.......oVVVVVVVVo.......',
  '.......oVVVVVVVVo.......',
  '.......oVVVVVVVVo.......',
  '.......oMSSSSSSMo.......',
  '.......oMMMMMMMMo.......',
  '........oMMMMMMo........',
  '........oMmmmmMo........',
  '.....ooooMMMMMMoooo.....',
  '....oBBBBBBBBBBBBBBo....',
  '...oBBBBBBBBBBBBBBBBo...',
  '..oBBBBBBBBBBBBBBBBBBo..',
  '..oBBBBBBBBBBBBBBBBBBo..',
  '..oBBBBBBBBBBBBBBBBBBo..',
  '..oBBBBBBBBBBBBBBBBBBo..',
  '...oBBBBBBBBBBBBBBBBo...',
  '...oBBBBBBBBBBBBBBBBo...',
  '...oBBBBBBBBBBBBBBBBo...',
  '...oBBBBBBBBBBBBBBBBo...',
  '...oBBBBBBBBBBBBBBBBo...',
  '....oBBBBBBBBBBBBBBo....',
  '....oBBBBBBBBBBBBBBo....',
  '....oBBBBBBBBBBBBBBo....',
  '....oBBBBBBBBBBBBBBo....',
  '.....oBBBBBBBBBBBBo.....',
  '.....oBBBBBBBBBBBBo.....',
  '.....oBBBBBBBBBBBBo.....',
  '.....oBBBBBBBBBBBBo.....',
  '.....oBB.BBBBBB.BBo.....',
  '.....oB..BBBBBB..Bo.....',
  '......B..BBBBBB..B......',
  '......B...BBBB...B......',
  '..........B..B..........',
  '..........B..B..........',
  '........................',
];

/* Where the index sphere sits inside the visor slot, in figure coordinates. */
const VISOR_X = 8, VISOR_Y = 6;

/* Fifteen colours and transparent, and this palette spends fourteen. Counted
 * off the rendered sprite by scripts/verify/kingui.mjs, not off this object:
 * `d` and `O` deliberately land on the same void step, which is a colour saved
 * rather than a mistake.
 *
 * void for the mantle, because palette.js's void is the darkest material the
 * game has and every step of it can still be seen against the outline.
 * gunmetal for the mask, because a machine's face is machined. And the rim is
 * KING_GREEN where every other sprite in the cast rims in #ffab5e.
 */
const KING_PAL = {
  o: OUTLINE,
  O: RAMPS.void[1],
  B: RAMPS.void[2],
  H: RAMPS.void[4],
  L: RAMPS.void[3],
  D: RAMPS.void[0],
  d: RAMPS.void[1],
  M: RAMPS.gunmetal[2],
  m: RAMPS.gunmetal[1],
  S: RAMPS.gunmetal[3],
  s: RAMPS.gunmetal[4],
  V: INDEX_RAMP[0],
  v: INDEX_RAMP[2],
  G: INDEX_RAMP[1],
  I: KING_GREEN,
  R: KING_GREEN,
  X: INDEX_RAMP[4],
};

/* A silhouette is the same grid with its interior collapsed onto one step. Used
 * by NOTICED, whose presence sentence asks for one. The rim and the index stay:
 * without the green he is a black shape, and with it he is unmistakably the
 * thing the player has been finding since Chapter II. */
const KING_PAL_FLAT = {
  ...KING_PAL,
  O: RAMPS.void[0], B: RAMPS.void[0], H: RAMPS.void[0], L: RAMPS.void[0],
  D: RAMPS.void[0], d: RAMPS.void[0],
  M: RAMPS.void[1], m: RAMPS.void[0], S: RAMPS.void[1], s: RAMPS.void[1],
};

/* The index sphere. 11x11 of glass with a number floating in it — the same
 * object in the visor, in the panel gutter, and in five unrelated side quests
 * the player has already finished. */
const SPHERE = [
  '...ooooo...',
  '..ovvvvvo..',
  '.ovXVVVVvo.',
  'ovVVVVVVVvo',
  'ovVVVVVVVvo',
  'ovVVVVVVVvo',
  'ovVVVVVVVvo',
  'ovVVVVVVVvo',
  '.ovVVVVVvo.',
  '..ovvvvvo..',
  '...ooooo...',
];
const SPHERE_W = 11, SPHERE_H = 11;

/* 3x5 digits, for the number inside the sphere. The panel's own hand is 5x8 and
 * will not fit in nine pixels of glass. */
const TINY_DIGITS = [
  '###/#.#/#.#/#.#/###', '.#./##./.#./.#./###', '###/..#/###/#../###',
  '###/..#/.##/..#/###', '#.#/#.#/###/..#/..#', '###/#../###/..#/###',
  '###/#../###/#.#/###', '###/..#/..#/..#/..#', '###/#.#/###/#.#/###',
  '###/#.#/###/..#/###',
];

const figureCache = new Map();
const FIGURE_CACHE_MAX = 32;
const sphereCache = new Map();
const SPHERE_CACHE_MAX = 16;
const textCache = new Map();
const TEXT_CACHE_MAX = 24;
const STATS = { figures: 0, spheres: 0, texts: 0 };

/* Shade the authored grid the way the rest of the cast is shaded, then hand the
 * rim the wrong colour. Built once per register — applyRim and rimLowLeft are
 * whole-grid passes and neither belongs anywhere near a frame. */
const shadedCache = new Map();
function shadedGrid() {
  // One shaded grid for all five registers: NOTICED's silhouette is the same
  // geometry through a collapsed palette, not a second sprite.
  let g = shadedCache.get('lit');
  if (g) return g;
  const base = normalise(KING_GRID, KING_W);
  // The mask, the visor and the sphere are protected from the rim pass: a face
  // that catches the light on every interior edge stops being a face.
  g = rimLowLeft(applyRim(base), 'R', 'MmSsVvGI');
  shadedCache.set('lit', g);
  return g;
}

/* The figure, cut and scanned, as one canvas.
 *
 * `rows` from the top, the last CUT_FADE of them dithered out on a hash of the
 * pixel so the cut dissolves instead of being sliced; then one row in every
 * `scanGap` dropped, rolling down by `phase`. Everything about him that varies
 * is baked in here, which is why the draw path is a single drawImage at a
 * single alpha — and why the colour count cannot multiply.
 */
const CUT_FADE = 5;
export function kingSprite(registerId, phase = 0, digit = 1) {
  const R = REGISTERS[registerId] || REGISTERS.UNCOUNTED;
  if (!R.rows) return null;
  const ph = ((phase | 0) % SCAN_PHASES + SCAN_PHASES) % SCAN_PHASES;
  const n = clamp(Math.round(Number(digit) || 0), 0, 99);
  const key = `${R.id}|${ph}|${n}`;
  const hit = figureCache.get(key);
  if (hit) return hit;

  const grid = shadedGrid();
  const pal = R.flat ? KING_PAL_FLAT : KING_PAL;
  const { canvas, ctx } = make(KING_W, R.rows);
  STATS.figures++;

  for (let y = 0; y < R.rows; y++) {
    // A missing raster line. The phase shifts the pattern down a row at a time,
    // so the gaps crawl rather than flicker in place.
    if (R.scanGap > 1 && ((y + ph) % R.scanGap) === 0) continue;
    const row = grid[y];
    if (!row) continue;
    // The last rows before the cut thin out rather than ending on a straight
    // edge. A hash of the pixel, so the same register always frays identically.
    const fade = y > R.rows - CUT_FADE ? (R.rows - y) / CUT_FADE : 1;
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      if (ch === '.' || ch === ' ') continue;
      if (fade < 1 && hash2(x * 7 + y, y * 13 + R.index) > fade) continue;
      const colour = pal[ch];
      if (!colour) continue;
      ctx.fillStyle = colour;
      ctx.fillRect(x, y, 1, 1);
    }
  }

  // The sphere in the visor, painted last so nothing shades over it. Two
  // pixels of it are the number, which is the same number the panel shows.
  if (R.rows > VISOR_Y + 3) drawSphereInto(ctx, VISOR_X, VISOR_Y, n, true);

  figureCache.set(key, canvas);
  capCache(figureCache, FIGURE_CACHE_MAX);
  return canvas;
}

/* The sphere, drawn straight into a context. `small` is the 8x3 version that
 * fits a visor slot; the full one is the panel's. */
function drawSphereInto(ctx, ox, oy, n, small) {
  if (small) {
    /* Eight pixels by three is not room for a number, so the visor carries the
     * other half of the same object: the slot the index reads through, and a
     * two-pixel bright core sitting at the position his entry for you happens
     * to occupy. It does not move, because he is not looking around. */
    ctx.fillStyle = INDEX_RAMP[0];
    ctx.fillRect(ox, oy, 8, 3);
    ctx.fillStyle = INDEX_RAMP[2];
    ctx.fillRect(ox, oy + 1, 8, 1);
    ctx.fillStyle = KING_GREEN;
    ctx.fillRect(ox + 1 + (clamp(n, 0, 99) % 6), oy + 1, 2, 1);
    return;
  }
  for (let y = 0; y < SPHERE_H; y++) {
    const row = SPHERE[y];
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      if (ch === '.') continue;
      const colour = KING_PAL[ch];
      if (!colour) continue;
      ctx.fillStyle = colour;
      ctx.fillRect(ox + x, oy + y, 1, 1);
    }
  }
  const text = String(clamp(Math.round(n), 0, 99));
  const w = text.length * 4 - 1;
  const sx = ox + Math.round((SPHERE_W - w) / 2);
  ctx.fillStyle = KING_GREEN;
  for (let i = 0; i < text.length; i++) {
    const glyph = TINY_DIGITS[text.charCodeAt(i) - 48];
    if (!glyph) continue;
    const rows = glyph.split('/');
    for (let y = 0; y < 5; y++) {
      const r = rows[y] || '';
      for (let x = 0; x < r.length; x++) {
        if (r[x] === '#') ctx.fillRect(sx + i * 4 + x, oy + 3 + y, 1, 1);
      }
    }
  }
}

/** The index sphere as its own canvas, cached per number. */
export function indexSphere(n) {
  const key = clamp(Math.round(Number(n) || 0), 0, 99);
  const hit = sphereCache.get(key);
  if (hit) return hit;
  const { canvas, ctx } = make(SPHERE_W, SPHERE_H);
  STATS.spheres++;
  drawSphereInto(ctx, 0, 0, key, false);
  sphereCache.set(key, canvas);
  capCache(sphereCache, SPHERE_CACHE_MAX);
  return canvas;
}

/* ------------------------------------------------------------------ the hand
 *
 * There are no image assets in this game and there never will be, which
 * includes fonts: the villagers' box leans on "Press Start 2P" with a monospace
 * fallback, and a fallback is a different shape on every machine. His panel
 * cannot afford that — the whole read is EXACTNESS — so the letters are drawn
 * here, one fillRect per pixel, into a canvas that is typeset once per message.
 *
 * 5x8 cell: rows 0-6 are cap height, row 7 is the descender. Mixed case on
 * purpose. A machine that speaks in capitals is shouting, and he never shouts.
 */
const GLYPHS = {
  ' ': '...../...../...../...../...../...../...../.....',
  'A': '.###./#...#/#...#/#####/#...#/#...#/#...#/.....',
  'B': '####./#...#/####./#...#/#...#/#...#/####./.....',
  'C': '.###./#...#/#..../#..../#..../#...#/.###./.....',
  'D': '###../#..#./#...#/#...#/#...#/#..#./###../.....',
  'E': '#####/#..../#..../####./#..../#..../#####/.....',
  'F': '#####/#..../#..../####./#..../#..../#..../.....',
  'G': '.###./#...#/#..../#.###/#...#/#...#/.###./.....',
  'H': '#...#/#...#/#...#/#####/#...#/#...#/#...#/.....',
  'I': '.###./..#../..#../..#../..#../..#../.###./.....',
  'J': '..###/...#./...#./...#./...#./#..#./.##../.....',
  'K': '#...#/#..#./#.#../##.../#.#../#..#./#...#/.....',
  'L': '#..../#..../#..../#..../#..../#..../#####/.....',
  'M': '#...#/##.##/#.#.#/#.#.#/#...#/#...#/#...#/.....',
  'N': '#...#/##..#/#.#.#/#.#.#/#..##/#...#/#...#/.....',
  'O': '.###./#...#/#...#/#...#/#...#/#...#/.###./.....',
  'P': '####./#...#/#...#/####./#..../#..../#..../.....',
  'Q': '.###./#...#/#...#/#...#/#.#.#/#..#./.##.#/.....',
  'R': '####./#...#/#...#/####./#.#../#..#./#...#/.....',
  'S': '.####/#..../#..../.###./....#/....#/####./.....',
  'T': '#####/..#../..#../..#../..#../..#../..#../.....',
  'U': '#...#/#...#/#...#/#...#/#...#/#...#/.###./.....',
  'V': '#...#/#...#/#...#/#...#/#...#/.#.#./..#../.....',
  'W': '#...#/#...#/#...#/#.#.#/#.#.#/##.##/#...#/.....',
  'X': '#...#/#...#/.#.#./..#../.#.#./#...#/#...#/.....',
  'Y': '#...#/#...#/.#.#./..#../..#../..#../..#../.....',
  'Z': '#####/....#/...#./..#../.#.../#..../#####/.....',
  'a': '...../...../.###./....#/.####/#...#/.####/.....',
  'b': '#..../#..../####./#...#/#...#/#...#/####./.....',
  'c': '...../...../.###./#..../#..../#..../.###./.....',
  'd': '....#/....#/.####/#...#/#...#/#...#/.####/.....',
  'e': '...../...../.###./#...#/#####/#..../.###./.....',
  'f': '..##./.#.../####./.#.../.#.../.#.../.#.../.....',
  'g': '...../...../.####/#...#/#...#/.####/....#/####.',
  'h': '#..../#..../####./#...#/#...#/#...#/#...#/.....',
  'i': '..#../...../.##../..#../..#../..#../.###./.....',
  'j': '...#./...../..##./...#./...#./...#./...#./###..',
  'k': '#..../#..../#..#./#.#../##.../#.#../#..#./.....',
  'l': '.##../..#../..#../..#../..#../..#../.###./.....',
  'm': '...../...../##.#./#.#.#/#.#.#/#...#/#...#/.....',
  'n': '...../...../####./#...#/#...#/#...#/#...#/.....',
  'o': '...../...../.###./#...#/#...#/#...#/.###./.....',
  'p': '...../...../####./#...#/#...#/####./#..../#....',
  'q': '...../...../.####/#...#/#...#/.####/....#/....#',
  'r': '...../...../#.##./##..#/#..../#..../#..../.....',
  's': '...../...../.####/#..../.###./....#/####./.....',
  't': '.#.../.#.../####./.#.../.#.../.#..#/..##./.....',
  'u': '...../...../#...#/#...#/#...#/#...#/.####/.....',
  'v': '...../...../#...#/#...#/#...#/.#.#./..#../.....',
  'w': '...../...../#...#/#...#/#.#.#/#.#.#/.#.#./.....',
  'x': '...../...../#...#/.#.#./..#../.#.#./#...#/.....',
  'y': '...../...../#...#/#...#/#...#/.####/....#/.###.',
  'z': '...../...../#####/...#./..#../.#.../#####/.....',
  '0': '.###./#...#/#..##/#.#.#/##..#/#...#/.###./.....',
  '1': '..#../.##../..#../..#../..#../..#../.###./.....',
  '2': '.###./#...#/....#/...#./..#../.#.../#####/.....',
  '3': '####./....#/....#/.###./....#/....#/####./.....',
  '4': '...#./..##./.#.#./#..#./#####/...#./...#./.....',
  '5': '#####/#..../####./....#/....#/#...#/.###./.....',
  '6': '..##./.#.../#..../####./#...#/#...#/.###./.....',
  '7': '#####/....#/...#./..#../.#.../.#.../.#.../.....',
  '8': '.###./#...#/#...#/.###./#...#/#...#/.###./.....',
  '9': '.###./#...#/#...#/.####/....#/...#./.##../.....',
  '.': '...../...../...../...../...../...../..#../.....',
  ',': '...../...../...../...../...../..#../..#../.#...',
  ':': '...../...../..#../...../...../..#../...../.....',
  ';': '...../...../..#../...../...../..#../..#../.#...',
  "'": '..#../..#../...../...../...../...../...../.....',
  '"': '.#.#./.#.#./...../...../...../...../...../.....',
  '-': '...../...../...../.###./...../...../...../.....',
  '—': '...../...../...../#####/...../...../...../.....',
  '–': '...../...../...../.###./...../...../...../.....',
  '_': '...../...../...../...../...../...../...../#####',
  '?': '.###./#...#/....#/...#./..#../...../..#../.....',
  '!': '..#../..#../..#../..#../..#../...../..#../.....',
  '(': '...#./..#../.#.../.#.../.#.../..#../...#./.....',
  ')': '.#.../..#../...#./...#./...#./..#../.#.../.....',
  '[': '..##./..#../..#../..#../..#../..#../..##./.....',
  ']': '.##../..#../..#../..#../..#../..#../.##../.....',
  '/': '....#/....#/...#./..#../.#.../#..../#..../.....',
  '\\': '#..../#..../.#.../..#../...#./....#/....#/.....',
  '+': '...../..#../..#../#####/..#../..#../...../.....',
  '=': '...../...../#####/...../#####/...../...../.....',
  '<': '...#./..#../.#.../#..../.#.../..#../...#./.....',
  '>': '.#.../..#../...#./....#/...#./..#../.#.../.....',
  '%': '##..#/##.#./..#../.#.##/#..##/...../...../.....',
  '*': '...../#.#.#/.###./#####/.###./#.#.#/...../.....',
  '#': '.#.#./#####/.#.#./#####/.#.#./...../...../.....',
  '&': '.##../#..#./.##../##.#./#..##/#..#./.##.#/.....',
  '@': '.###./#...#/#.###/#.#.#/#.###/#..../.###./.....',
};
const MISSING = '#####/#...#/#...#/#...#/#...#/#...#/#####/.....';
const GLYPH_W = 5, GLYPH_H = 8;
export const CHAR_ADVANCE = 6;       // 5 wide plus one of air
export const LINE_ADVANCE = 10;      // 8 tall plus two of leading

/* Curly quotes and the non-breaking space land on their straight equivalents:
 * a Python module written by a person will emit them and a box that draws a
 * missing-glyph square for an apostrophe looks broken rather than exact. */
const FOLD = { '‘': "'", '’': "'", '“': '"', '”': '"', ' ': ' ' };

function glyphFor(ch) {
  const c = FOLD[ch] || ch;
  return GLYPHS[c] || GLYPHS[c.toUpperCase()] || MISSING;
}

/* --------------------------------------------------------------- the panel
 *
 * Colours: one flat face, not a bevel. transform.js paints the player's triumph
 * as a hard shadow under a light face over a dark face; his is a single pass of
 * a cool near-white that has had a little of the index green mixed into it, so
 * it belongs to him without ever being bright.
 */
const PANEL_GROUND = '#05070c';
const PANEL_RULE = INDEX_RAMP[1];
const PANEL_TICK = KING_GREEN;
const PANEL_TEXT = mix(RAMPS.chrome[3], KING_GREEN, 0.16);

export const PANEL_TOP = 28;       // screen px; clears apex.js's two rim lanes
export const PANEL_MAX_LINES = 4;
const PANEL_PAD = 5;
const PANEL_GUTTER = 15;           // the sphere lives here
const PANEL_MARGIN = 6;            // panel px of air either side

/* Break a line to a column count without allocating on the draw path — this
 * runs once per distinct message and the result is cached with the canvas. */
function wrap(text, cols, maxLines) {
  const out = [];
  const words = String(text).split(/\s+/);
  let line = '';
  let clipped = false;
  for (const w of words) {
    if (!w) continue;
    if (!line.length) line = w;
    else if (line.length + 1 + w.length <= cols) line += ' ' + w;
    else { out.push(line); line = w; }
    while (line.length > cols) { out.push(line.slice(0, cols)); line = line.slice(cols); }
    if (out.length >= maxLines) { clipped = true; line = ''; break; }
  }
  if (line.length && out.length < maxLines) out.push(line);
  // A window too short to hold everything he said keeps the sentence and marks
  // the cut, rather than silently eating the end of it.
  if (clipped && out.length) {
    const last = out[out.length - 1];
    out[out.length - 1] = (last.length > cols - 1 ? last.slice(0, cols - 1) : last) + '-';
  }
  return out;
}

/* Typeset once. The returned entry owns its canvas, its line strings and the
 * running character count the reveal wipe indexes — all allocated here, none of
 * it on a frame. */
function typeset(text, cols, maxLines) {
  const key = `${cols}|${maxLines}|${text}`;
  const hit = textCache.get(key);
  if (hit) return hit;
  const lines = wrap(text, cols, maxLines);
  const w = Math.max(1, cols * CHAR_ADVANCE);
  const h = Math.max(1, lines.length * LINE_ADVANCE);
  const { canvas, ctx } = make(w, h);
  STATS.texts++;
  ctx.fillStyle = PANEL_TEXT;
  const before = [];
  let running = 0;
  for (let i = 0; i < lines.length; i++) {
    before.push(running);
    running += lines[i].length;
    const oy = i * LINE_ADVANCE;
    for (let c = 0; c < lines[i].length; c++) {
      const rows = glyphFor(lines[i][c]).split('/');
      const ox = c * CHAR_ADVANCE;
      for (let y = 0; y < GLYPH_H; y++) {
        const row = rows[y];
        if (!row) continue;
        for (let x = 0; x < GLYPH_W; x++) if (row[x] === '#') ctx.fillRect(ox + x, oy + y, 1, 1);
      }
    }
  }
  const entry = { canvas, lines, before, total: running, w, h };
  textCache.set(key, entry);
  capCache(textCache, TEXT_CACHE_MAX);
  return entry;
}

function panelCols(viewW, s) {
  return Math.max(8, Math.floor((Math.floor(viewW / s) - PANEL_MARGIN * 2
                                 - PANEL_GUTTER - PANEL_PAD) / CHAR_ADVANCE));
}

/* WHERE THE PANEL IS ALLOWED TO REACH.
 *
 * The camera centres the player, so the top of the hero's sprite is at a height
 * this file can compute exactly rather than guess: viewH/2 plus the eight
 * pixels his feet sit below his tile, less his twenty-four of height, times the
 * world scale. The panel is not permitted past it. That is the same promise the
 * figure makes, kept by the words as well — he does not get to stand in front
 * of you and he does not get to write in front of you either.
 *
 * If what he said will not fit in the band, the hand drops to 1x before
 * anything is cut, and only a genuinely tiny window ever loses a word.
 */
const LAYOUT = { s: 2, cols: 0, maxLines: 0, set: null, innerW: 0, innerH: 0,
                 x0: 0, y0: 0, below: false };

/* THE CAMERA ONLY CENTRES HIM WHEN IT CAN, and the rest of this file was
 * written as though it always did.
 *
 * `viewH / 2 + (8 - 24) * scale` is where the top of the hero's head is while
 * the camera is FREE. At a map edge the camera clamps — that is what stops the
 * frame showing void — and he is then wherever the clamp left him. Standing on
 * the north edge of a 48x34 map he is 24 to 40 pixels down the frame depending
 * on the scale, and PANEL_TOP is 28 with the words running to 88: the panel
 * that is forbidden from standing in front of him was printing across his head
 * at every window size, measured in scripts/verify/field.mjs part C.
 *
 * This is older than the zoom and the zoom did not cause it — but the zoom is
 * what made it findable, because raising the scale is what made the clamped
 * band worth measuring. It gets RARER at FF6 scale, not commoner: the vertical
 * span the camera has to fit shrank from 258..376 world pixels to 206..251, so
 * there is more map above and below the player before the clamp bites.
 *
 * `actualTop` is that measured number when a caller has one. Nobody is required
 * to pass it and the old estimate is what happens when nobody does, so every
 * existing call site keeps the behaviour it was written against. */
export function heroTopOnScreen(viewH, worldScale, actualTop) {
  if (Number.isFinite(actualTop)) return Math.round(actualTop);
  return Math.round(viewH / 2 + (8 - 24) * (worldScale || 3));
}

/* Where the hero's head actually is, off the same world object placement
 * already reads. Returns undefined — not a guess — when the object does not
 * carry a camera, so heroTopOnScreen falls back rather than inventing a number
 * out of half a frame. */
function heroTopFromWorld(w) {
  if (!w || !w.player) return undefined;
  const s = w.scale;
  if (!(s > 0) || !Number.isFinite(w.camY) || !Number.isFinite(w.player.py)) return undefined;
  return (w.player.py + TILE - HERO_H - w.camY) * s;
}

/* WHEN THERE IS NO ROOM ABOVE HIS HEAD, THE WORDS GO UNDER IT.
 *
 * The band above the hero is viewH/2-ish while the camera is free and it is
 * enormous. Standing on the north edge of the map it is TWENTY-FOUR PIXELS,
 * because the camera has clamped and the hero is at the top of the frame — less
 * than PANEL_TOP, which is 28. The loop below has no way to express that: it
 * drops the hand from 2 to 1 and then takes whatever 1 produced, fitting or
 * not, so the panel printed straight across his head at every window size. It
 * is the promise this whole file is built on, broken in the one place a player
 * is guaranteed to stand — the way into every region is an edge.
 *
 * Dropping the hand further is not an answer; there is no hand small enough to
 * fit four lines into twenty-four pixels, and shrinking his voice to escape him
 * is the wrong shape of fix anyway. The band below his feet is 757 pixels in
 * exactly the case the band above is 24, so the panel moves there. He is still
 * not standing in front of you and he is still not writing in front of you; he
 * has just stopped insisting on doing it from the top of the screen.
 *
 * The bottom margin is PANEL_TOP again rather than a new number, because what
 * PANEL_TOP is FOR is clearing apex.js's two rim lanes (7 and 20 plus a 6px
 * mark), and the rim at the bottom of the frame is the same rim. */
function layout(text, viewW, viewH, worldScale, actualTop) {
  const heroTop = heroTopOnScreen(viewH, worldScale, actualTop);
  const ceiling = heroTop - 6;
  /* One line at the smallest hand is the least a panel can be. If the band
   * above cannot hold that, it cannot hold anything. */
  const least = PANEL_PAD * 2 + LINE_ADVANCE;
  const below = (ceiling - PANEL_TOP) < least;
  const top = below
    ? Math.round(heroTop + HERO_H * (worldScale || 3) + 6)
    : PANEL_TOP;
  const band = below ? (viewH - PANEL_TOP) - top : ceiling - top;
  for (const s of [2, 1]) {
    const cols = panelCols(viewW, s);
    const room = Math.floor((band - PANEL_PAD * 2 * s) / (LINE_ADVANCE * s));
    const maxLines = clamp(room, 1, PANEL_MAX_LINES);
    const set = typeset(String(text || ''), cols, maxLines);
    if (set.lines.length <= maxLines || s === 1) {
      LAYOUT.s = s; LAYOUT.cols = cols; LAYOUT.maxLines = maxLines; LAYOUT.set = set;
      LAYOUT.innerW = PANEL_GUTTER + cols * CHAR_ADVANCE + PANEL_PAD;
      LAYOUT.innerH = PANEL_PAD * 2 + set.lines.length * LINE_ADVANCE;
      LAYOUT.x0 = Math.round((viewW - LAYOUT.innerW * s) / 2);
      LAYOUT.y0 = top;
      LAYOUT.below = below;
      return LAYOUT;
    }
  }
  return LAYOUT;
}

/** What a message will measure, without drawing it. `actualTop` is optional and
 * is the hero's measured top on screen; see heroTopOnScreen. */
export function measurePanel(text, viewW, viewH, worldScale, actualTop) {
  const L = layout(text, viewW, viewH, worldScale, actualTop);
  return { scale: L.s, cols: L.cols, maxLines: L.maxLines, lines: L.set.lines.length,
           chars: L.set.total, x: L.x0, y: L.y0,
           w: L.innerW * L.s, h: L.innerH * L.s,
           bottom: L.y0 + L.innerH * L.s,
           below: L.below,
           ceiling: heroTopOnScreen(viewH, worldScale, actualTop) - 6 };
}

/* ------------------------------------------------------------------- state
 *
 * WHAT THIS CODES AGAINST. gauntlet/antagonist.py is being written as this
 * ships: Sections 1-3 exist on disk (the two guards, the occasion table, the
 * five registers) and `speak` does not yet. What that file HAS already fixed is
 * the shape of the thing it will hand over — an occasion id, a register id, a
 * line of prose, a hold in milliseconds, and `blocking: False` stated as a
 * promise in its own header — so this reads those and nothing else.
 *
 *   state.king = {                       // also: null_king, antagonist, king_speech
 *     text | line | say | message,       // string, or an array of strings
 *     register | mood,                   // one of REGISTER_IDS
 *     standing | score,                  // a number, if the register is absent
 *     occasion | occasion_id | id,       // antagonist.OCCASION_IDS
 *     ms | hold_ms | seconds,            // how long he holds. Clamped.
 *     index | entry | count,             // the number in the sphere
 *     region,                            // ignored unless it disagrees
 *     blocking,                          // REFUSED. See below.
 *   }
 *
 * EVERY DEGRADE IS SILENT. No row, a row for another region, a row with no
 * words, a stateSource that throws mid-rewrite: all of them are "he has nothing
 * to say", and the overworld renders exactly as it did before this existed.
 *
 * `blocking` IS REFUSED RATHER THAN HONOURED. antagonist.py's header says
 * `speak` always returns blocking: False and that he blocks nothing, delays
 * nothing and gates nothing. If some later payload ever contradicts that, the
 * client is not the place to find out — the flag is dropped, the refusal is
 * recorded, and he is still weather. There is no code path in this file that
 * can hold the player still.
 */
function pickRow(state, regionId) {
  if (!state || typeof state !== 'object') return null;
  const one = state.king || state.null_king || state.nullKing || state.antagonist
           || state.king_speech || state.kingSpeech;
  if (one && typeof one === 'object' && !Array.isArray(one)) return one;
  const many = state.kings || state.king_lines || state.antagonist_lines
            || (Array.isArray(one) ? one : null);
  if (Array.isArray(many)) {
    for (let i = many.length - 1; i >= 0; i--) {
      const r = many[i];
      if (!r || typeof r !== 'object') continue;
      const rr = r.region || r.region_id || r.regionId;
      if (rr && regionId && String(rr) !== String(regionId)) continue;
      return r;
    }
  }
  return null;
}

function firstString(row, keys) {
  for (const k of keys) {
    const v = row[k];
    if (typeof v === 'string' && v.trim()) return v.trim();
    if (Array.isArray(v)) {
      const joined = v.filter(x => typeof x === 'string').join(' ').trim();
      if (joined) return joined;
    }
  }
  return '';
}

/** Normalised, or null. Refusal is the default. */
export function resolveKing(state, regionId) {
  const row = pickRow(state, regionId);
  if (!row || typeof row !== 'object') return null;
  const rr = row.region || row.region_id || row.regionId;
  if (rr && regionId && String(rr) !== String(regionId)) return null;

  const text = firstString(row, ['text', 'line', 'say', 'message', 'body', 'prose']);
  if (!text) return null;

  let register = String(row.register || row.mood || row.tone || '').toUpperCase();
  if (REGISTER_IDS.indexOf(register) < 0) {
    const standing = Number(row.standing !== undefined ? row.standing : row.score);
    register = Number.isFinite(standing) ? registerFor(standing) : 'UNCOUNTED';
  }
  const R = REGISTERS[register];

  let ms = Number(row.ms !== undefined ? row.ms
    : row.hold_ms !== undefined ? row.hold_ms
    : row.duration_ms !== undefined ? row.duration_ms
    : (Number(row.seconds) * 1000));
  if (!Number.isFinite(ms) || ms <= 0) ms = R.ms;
  // A hold this file will not exceed. He is weather: the longest register in
  // antagonist.py is 5600ms and twice that is already an interruption.
  ms = clamp(ms, 900, 12000);

  const idx = Number(row.index !== undefined ? row.index
    : row.entry !== undefined ? row.entry : row.count);

  const occasion = String(row.occasion || row.occasion_id || row.occasionId
                          || row.id || 'AMBIENT');
  return {
    text,
    register,
    ms,
    occasion,
    label: String(row.label || ''),
    index: Number.isFinite(idx) ? clamp(Math.round(idx), 0, 99) : null,
    regionId: String(regionId || ''),
    // Recorded, never honoured. kingDebug() prints it.
    refusedBlocking: !!(row.blocking || row.modal || row.blocks),
    key: String(row.key || row.seq || row.stamp || ''),
  };
}

/** The identity of one thing said. A new key is a new arrival; the same key
 *  redelivered by the next poll is the same sentence and must not restart it. */
export function stampOf(view) {
  if (!view) return '';
  return view.key
    ? `${view.occasion}|${view.register}|${view.key}`
    : `${view.occasion}|${view.register}|${hash(view.text).toString(16)}`;
}

/** antagonist.REGISTERS, adopted, so the client's copy cannot drift. Returns
 *  what it refused, in adoptPayload's shape. */
export function adoptPayload(payload) {
  const refused = [];
  if (!payload || typeof payload !== 'object') return { adopted: false, refused };
  const table = payload.registers || payload.REGISTERS || payload;
  if (!table || typeof table !== 'object') return { adopted: false, refused };
  for (const rid of REGISTER_IDS) {
    const row = table[rid];
    if (!row || typeof row !== 'object') continue;
    const ms = Number(row.ms);
    if (Number.isFinite(ms) && ms > 0) {
      const held = clamp(ms, 900, 12000);
      if (held !== ms) refused.push({ register: rid, field: 'ms', asked: ms, clamped: held });
      REGISTERS[rid].ms = held;
    }
    const floor = Number(row.floor);
    if (Number.isFinite(floor) && floor >= 0) REGISTERS[rid].floor = floor;
    if (typeof row.presence === 'string' && row.presence) REGISTERS[rid].presence = row.presence;
  }
  return { adopted: true, refused };
}

/* ---------------------------------------------------------------- presence
 *
 * PLACEMENT, which is half of rule A.
 *
 * He arrives at a register-controlled distance from where the player was
 * standing when he opened his mouth, on a bearing chosen deterministically from
 * the occasion, and then a dozen candidate bearings are tried in order until
 * one produces a box that
 *
 *   1  is on the map and not inside rock,
 *   2  is inside the visible frame with a margin,
 *   3  does not intersect the player's box,
 *   4  does not intersect any marker's box — an exit, a chest, a shrine, a
 *      villager, a boss, a building.
 *
 * If none of the twelve is clean he does not appear at all, and the words show
 * up on their own. Failing to absent is the correct failure for a thing whose
 * whole promise is that it will not get in your way — and it is why the second
 * half of rule A, the sort clamp in overworld.js, only ever has to handle the
 * cases geometry cannot: the objects the tilemap put there after he arrived.
 */
const BEARING_ORDER = [0, 3, 9, 2, 10, 4, 8, 1, 11, 5, 7, 6];
const DISTANCE_LADDER = [1, 0.78, 0.6];

export class Presence {
  constructor(view, world) {
    this.view = view;
    this.world = world;
    this.register = view.register;
    this.reg = REGISTERS[view.register] || REGISTERS.UNCOUNTED;
    this.seq = Number(world && world.seq) || 1;
    this.index = view.index === null || view.index === undefined
      ? clamp(this.seq, 1, 99) : view.index;
    this.t = 0;                 // seconds since he arrived
    this.alpha = 0;
    this.state = 'ARRIVING';
    this.leaveIn = FADE_OUT;
    this.ax = 0; this.ay = 0;   // his ground point, world px
    this.placed = false;
    this.bearing = -1;
    this.reach = 1;
    this.tries = 0;
    this.dismissed = false;
    this.hold = view.ms / 1000;
    const p = world && world.player;
    this.originX = p ? p.px : 0;
    this.originY = p ? p.py : 0;
    this.walked = 0;
    this.place();
  }

  /** The same sentence arriving again from the next poll. Nothing restarts. */
  sync(view) {
    if (!view) return;
    this.view = view;
    if (view.index !== null && view.index !== undefined) this.index = view.index;
  }

  get gone() { return this.state === 'GONE'; }

  /* E. Dismissible, and it costs the player nothing to ignore. */
  dismiss() {
    if (this.state === 'GONE') return false;
    this.dismissed = true;
    this.state = 'LEAVING';
    this.leaveIn = LEAVE_FAST;
    return true;
  }

  place() {
    const w = this.world;
    this.placed = false;
    this.tries = 0;
    if (!w || !this.reg.rows) return false;          // UNCOUNTED has no body
    const p = w.player;
    if (!p) return false;
    const dist = this.reg.tiles * TILE;

    /* The bearing he prefers. Late, he is in front of you — antagonist.py's
     * word for UNQUIET is "centred", and the thing you are looking at is the
     * centre of your own frame. Early, it is a hashed direction, which is what
     * puts him at the edge of vision instead of in your path. */
    const facing = FACING_ANGLE[p.facing] !== undefined ? FACING_ANGLE[p.facing] : 1;
    const seed = hash(`${this.view.occasion}|${this.view.regionId}|${this.seq}`) % 12;
    const base = this.reg.edge >= 0.75 ? seed
      : Math.round(facing * (1 - this.reg.edge) + seed * this.reg.edge) % 12;

    /* Twelve bearings at his register's distance, then the same twelve drawn
     * in. A small window, a corner of the map or a crowded village can make
     * every position at six tiles fall outside the frame, and the choice there
     * is between standing closer than his register asks and not being there at
     * all. He stands closer. `reach` says by how much, so nothing has to take
     * the placement on trust. */
    for (let ring = 0; ring < DISTANCE_LADDER.length; ring++) {
      const d = dist * DISTANCE_LADDER[ring];
      for (let k = 0; k < BEARING_ORDER.length; k++) {
        const slot = (base + BEARING_ORDER[k]) % 12;
        const ang = (slot / 12) * TAU;
        // Flattened, because the world is drawn in a shallow plane and a circle
        // of candidate positions in screen space reads as an ellipse in it.
        const ax = p.px + TILE / 2 + Math.cos(ang) * d;
        const ay = p.py + TILE + Math.sin(ang) * d * 0.62;
        this.tries++;
        if (!this._clear(ax, ay)) continue;
        this.ax = ax; this.ay = ay;
        this.bearing = slot;
        this.reach = DISTANCE_LADDER[ring];
        this.placed = true;
        return true;
      }
    }
    return false;
  }

  _clear(ax, ay) {
    const w = this.world;
    const rows = this.reg.rows;
    const bx = ax - KING_W / 2, by = ay - KING_H, bw = KING_W, bh = rows;
    const tx = Math.floor(ax / TILE), ty = Math.floor((ay - 1) / TILE);
    if (tx < 1 || ty < 1 || tx >= (w.mapW || 48) - 1 || ty >= (w.mapH || 34) - 1) return false;
    if (typeof w.solid === 'function' && w.solid(tx, ty)) return false;

    // Inside the frame, with a margin, or he is a rumour rather than a presence.
    if (typeof w.viewW === 'number' && typeof w.camX === 'number') {
      const s = w.scale || 3;
      const left = w.camX + 6, top = w.camY + 6;
      const right = w.camX + w.viewW / s - 6, bottom = w.camY + w.viewH / s - 6;
      if (bx < left || bx + bw > right || by < top || ay > bottom) return false;
    }

    const p = w.player;
    if (hit(bx, by, bw, bh, p.px, p.py + TILE - HERO_H, HERO_W, HERO_H)) return false;

    const markers = w.markers || [];
    for (let i = 0; i < markers.length; i++) {
      const m = markers[i];
      // The same boxes overworld.js sorts against, plus a tile of air: standing
      // shoulder to shoulder with a chest is still standing on it, to a player
      // trying to walk to the chest.
      let mx = m.x * TILE - 8, my = m.y * TILE - 8, mw = TILE + 16, mh = TILE + 16;
      if (m.kind === 'building') { my = m.y * TILE - 8; mw = TILE * 2 + 16; mh = TILE * 2 + 16; }
      else if (m.kind === 'boss') { mx = m.x * TILE + TILE / 2 - 40; my = m.y * TILE + TILE - 72; mw = 80; mh = 80; }
      if (hit(bx, by, bw, bh, mx, my, mw, mh)) return false;
    }
    return true;
  }

  /** dt in seconds, `time` the world clock. Returns 'gone' on the frame he
   *  stops existing, otherwise null. Never returns anything the caller has to
   *  act on. */
  update(dt, time) {
    if (this.state === 'GONE') return null;
    this.t += dt;
    const p = this.world && this.world.player;

    if (p) {
      const dx = p.px - this.originX, dy = p.py - this.originY;
      this.walked = Math.sqrt(dx * dx + dy * dy);
      // E. Walk away and he is not there any more. No line about it, no chase.
      if (this.walked > LEASH_PX && this.state !== 'LEAVING') {
        this.state = 'LEAVING'; this.leaveIn = LEAVE_FAST;
      }
      // A. And if you walk into where he is, he is not there either — he does
      // not occupy space and he is never between you and anything.
      if (this.placed && this.state !== 'LEAVING'
          && hit(this.ax - KING_W / 2, this.ay - KING_H, KING_W, this.reg.rows,
                 p.px, p.py + TILE - HERO_H, HERO_W, HERO_H)) {
        this.state = 'LEAVING'; this.leaveIn = LEAVE_FAST;
      }
    }

    if (this.state === 'ARRIVING') {
      this.alpha = clamp(this.t / FADE_IN, 0, 1);
      if (this.t >= FADE_IN) this.state = 'HOLDING';
    } else if (this.state === 'HOLDING') {
      this.alpha = 1;
      if (this.t >= FADE_IN + this.hold) { this.state = 'LEAVING'; this.leaveIn = FADE_OUT; }
    } else if (this.state === 'LEAVING') {
      this.alpha -= dt / Math.max(0.05, this.leaveIn);
      if (this.alpha <= 0) { this.alpha = 0; this.state = 'GONE'; return 'gone'; }
    }
    return null;
  }

  /** How far his ground point is from the player's, in px. Measured rather than
   *  claimed: scripts/verify/kingui.mjs reads this per register. */
  distancePx() {
    const p = this.world && this.world.player;
    if (!p || !this.placed) return 0;
    const dx = this.ax - (p.px + TILE / 2), dy = this.ay - (p.py + TILE);
    return Math.sqrt(dx * dx + dy * dy);
  }

  debug() {
    return {
      register: this.register, occasion: this.view.occasion,
      state: this.state, alpha: +this.alpha.toFixed(3),
      placed: this.placed, bearingSlot: this.bearing, placementTries: this.tries,
      x: +this.ax.toFixed(1), y: +this.ay.toFixed(1), reach: this.reach,
      distancePx: +this.distancePx().toFixed(1),
      distanceTiles: +(this.distancePx() / TILE).toFixed(2),
      rows: this.reg.rows, scanGap: this.reg.scanGap, solidity: this.reg.solidity,
      index: this.index, holdSeconds: +this.hold.toFixed(2),
      walkedPx: +this.walked.toFixed(1), dismissed: this.dismissed,
      refusedBlocking: !!this.view.refusedBlocking,
      blocking: false,
    };
  }
}

const FACING_ANGLE = { right: 0, down: 3, left: 6, up: 9, side: 0 };

function hit(ax, ay, aw, ah, bx, by, bw, bh) {
  return !(ax >= bx + bw || ax + aw <= bx || ay >= by + bh || ay + ah <= by);
}

/* ------------------------------------------------------------------ drawing
 *
 * World space. Called from overworld.js's y-sorted pass, with the camera
 * transform still on the context, which is the whole of A: he is IN the world
 * rather than painted over it, and he goes behind the tree he is behind.
 */
export function drawKingBody(ctx, pres, time, reducedMotion) {
  if (!pres || !pres.placed || pres.alpha <= 0.004) return 0;
  const R = pres.reg;
  if (!R.rows) return 0;
  const phase = reducedMotion ? 0 : (Math.floor(time * SCAN_RATE) % SCAN_PHASES);
  const img = kingSprite(R.id, phase, pres.index);
  if (!img) return 0;
  const prev = ctx.globalAlpha;
  const a = prev * R.solidity * pres.alpha;
  ctx.globalAlpha = a;
  ctx.drawImage(img, Math.round(pres.ax - KING_W / 2), Math.round(pres.ay - KING_H));
  ctx.globalAlpha = prev;
  /* No ground shadow, on purpose, and this is the only place in the codebase
   * where that sentence is true. Everything else that stands on this map — the
   * hero, the companion, the villagers, the apex, the slimes — is drawn with
   * sprites.drawGroundShadow first. He is not standing on anything. */
  return a;
}

/* The green landing on YOU. Four corner brackets around the hero's box and a
 * single scan row crossing it: the pointer, pointing. It runs only from PRECISE
 * up, because that is where antagonist.py stops reading the file aloud and
 * starts addressing the person holding it.
 *
 * Drawn in world space with the hero, so it moves with him and sorts with him.
 */
export function drawIndexOnPlayer(ctx, pres, px, py, time, reducedMotion) {
  if (!pres || pres.alpha <= 0.004) return 0;
  const R = pres.reg;
  if (R.index < INDEX_FROM) return 0;
  const x = Math.round(px), y = Math.round(py + TILE - HERO_H);
  const w = HERO_W, h = HERO_H;
  const arm = 4;
  const prev = ctx.globalAlpha;
  const lit = prev * pres.alpha * (0.30 + 0.18 * (R.index - INDEX_FROM));
  ctx.globalAlpha = lit;
  ctx.fillStyle = KING_GREEN;
  // corners: two pixels of each bracket, never a box. A box is a UI element.
  ctx.fillRect(x - 2, y - 2, arm, 1);      ctx.fillRect(x - 2, y - 2, 1, arm);
  ctx.fillRect(x + w + 2 - arm, y - 2, arm, 1); ctx.fillRect(x + w + 1, y - 2, 1, arm);
  ctx.fillRect(x - 2, y + h + 1, arm, 1);  ctx.fillRect(x - 2, y + h + 2 - arm, 1, arm);
  ctx.fillRect(x + w + 2 - arm, y + h + 1, arm, 1);
  ctx.fillRect(x + w + 1, y + h + 2 - arm, 1, arm);
  // the read itself: one row, crossing him slowly, top to bottom
  if (!reducedMotion) {
    const row = Math.floor(((time * 9) % (h + 6)) - 3);
    if (row >= 0 && row < h) {
      ctx.globalAlpha = lit * 0.55;
      ctx.fillRect(x, y + row, w, 1);
    }
  }
  ctx.globalAlpha = prev;
  return lit;
}

/* Screen space, after the world transform is gone.
 *
 * ORDER MATTERS AND IT IS THE CALLER'S JOB: overworld.js draws this BEFORE
 * apex.js's telegraph, so a gold chevron pointing at the way out is still
 * painted over the top of him. PANEL_TOP clears both of apex.js's rim lanes
 * anyway, so the two never actually touch — but the ordering is the guarantee
 * and the margin is only the comfort.
 */
export function drawKingPanel(ctx, pres, viewW, viewH, scale, time, reducedMotion) {
  if (!pres || pres.alpha <= 0.004) return 0;
  /* No new argument: the Presence already holds the world object placement was
   * decided against, and the host keeps its camera fresh. A host that does not
   * gets undefined and the centred estimate, exactly as before. */
  const L = layout(pres.view.text, viewW, viewH, scale, heroTopFromWorld(pres.world));
  const s = L.s, set = L.set, innerW = L.innerW, innerH = L.innerH;
  const x0 = L.x0, y0 = L.y0;
  const prev = ctx.globalAlpha;
  const a = pres.alpha;

  /* The ground. Dark, flat, opaque enough to read on grass and not so opaque
   * that the world stops existing behind it. */
  ctx.globalAlpha = prev * a * 0.88;
  ctx.fillStyle = PANEL_GROUND;
  ctx.fillRect(x0, y0, innerW * s, innerH * s);

  /* Two rules and one tick. This is the entire frame — no bevel, no corner
   * ornament, no portrait well. The villagers get a box with a face in it. */
  ctx.globalAlpha = prev * a * 0.9;
  ctx.fillStyle = PANEL_RULE;
  ctx.fillRect(x0, y0, innerW * s, s);
  ctx.fillRect(x0, y0 + innerH * s - s, innerW * s, s);
  ctx.globalAlpha = prev * a;
  ctx.fillStyle = PANEL_TICK;
  ctx.fillRect(x0, y0, 10 * s, s);
  // and one tick at the right end, whose length is the register. Five states of
  // a machine's status light, and the player will read it long before they
  // could tell you what it meant.
  const tick = 2 + pres.reg.index * 2;
  ctx.fillRect(x0 + innerW * s - tick * s, y0 + innerH * s - s, tick * s, s);

  /* The index sphere, in the gutter. The same object as the one in his visor
   * and the same one that has been turning up in side quests since Chapter II. */
  const sphere = indexSphere(pres.index);
  ctx.globalAlpha = prev * a;
  ctx.drawImage(sphere, x0 + 2 * s, y0 + Math.round((innerH - SPHERE_H) / 2) * s,
                SPHERE_W * s, SPHERE_H * s);

  /* The words, revealed left to right as if they were being read out of
   * something rather than spoken. One drawImage per line, source-clipped: no
   * per-character work and no allocation. */
  const revealed = reducedMotion ? set.total
    : Math.floor(Math.max(0, pres.t - FADE_IN * 0.4) * CHARS_PER_SECOND);
  const tx = x0 + PANEL_GUTTER * s;
  const ty = y0 + PANEL_PAD * s;
  for (let i = 0; i < set.lines.length; i++) {
    const n = clamp(revealed - set.before[i], 0, set.lines[i].length);
    if (n <= 0) break;
    const wpx = n * CHAR_ADVANCE;
    ctx.drawImage(set.canvas,
                  0, i * LINE_ADVANCE, wpx, LINE_ADVANCE,
                  tx, ty + i * LINE_ADVANCE * s, wpx * s, LINE_ADVANCE * s);
  }

  /* The cursor: one cell of green at the write head while he is still writing.
   * It stops when the sentence stops, and there is nothing to press. */
  if (revealed < set.total && !reducedMotion) {
    let line = 0, col = revealed;
    for (let i = 0; i < set.lines.length; i++) {
      if (revealed >= set.before[i]) { line = i; col = revealed - set.before[i]; }
    }
    ctx.globalAlpha = prev * a * 0.8;
    ctx.fillStyle = PANEL_TICK;
    ctx.fillRect(tx + col * CHAR_ADVANCE * s, ty + (line * LINE_ADVANCE + GLYPH_H - 1) * s,
                 CHAR_ADVANCE * s, s);
  }
  ctx.globalAlpha = prev;
  return a;
}

/* The frame, very slightly indexed. Capped hard: at ATTENTIVE and UNQUIET the
 * rim of the screen picks up the green, and at the cap it is 0.09 — under a
 * third of apex.js's VIGNETTE_CAP, because the apex is a thing that can kill
 * you and he is a thing that is looking at you.
 */
export const WASH_CAP = 0.09;
export function drawIndexWash(ctx, pres, viewW, viewH, time, reducedMotion) {
  if (!pres || pres.alpha <= 0.004) return 0;
  const R = pres.reg;
  if (R.index < 3) return 0;
  const pulse = reducedMotion ? 0.5 : 0.5 + Math.sin(time * 0.9) * 0.5;
  const peak = Math.min(WASH_CAP, (0.045 + 0.02 * (R.index - 3)) * (0.7 + 0.3 * pulse)
                        * pres.alpha);
  /* Concentric RINGS, not four overlapping strips. apex.js makes the same
   * point about its own wash and for the same reason: two translucent rectangles
   * crossing at a corner compound into something far darker than the cap, and
   * the cap is the whole promise. A ring is four rects that do not touch, so the
   * alpha the player sees at the brightest pixel is exactly the number this
   * function returns. */
  const prev = ctx.globalAlpha;
  ctx.fillStyle = KING_GREEN;
  const bands = 5;
  const span = Math.round(Math.min(viewW, viewH) * 0.10);
  const stepPx = Math.max(1, Math.round(span / bands));
  for (let b = 0; b < bands; b++) {
    const k = 1 - b / bands;
    ctx.globalAlpha = peak * k * k;
    const off = b * stepPx;
    const iw = viewW - off * 2, ih = viewH - off * 2;
    if (iw <= 0 || ih <= 0) break;
    ctx.fillRect(off, off, iw, stepPx);
    ctx.fillRect(off, viewH - off - stepPx, iw, stepPx);
    const midH = ih - stepPx * 2;
    if (midH > 0) {
      ctx.fillRect(off, off + stepPx, stepPx, midH);
      ctx.fillRect(viewW - off - stepPx, off + stepPx, stepPx, midH);
    }
  }
  ctx.globalAlpha = prev;
  return peak;
}

/* --------------------------------------------------------------- harnessing */

export function clearKingCache() {
  figureCache.clear(); sphereCache.clear(); textCache.clear(); shadedCache.clear();
  STATS.figures = 0; STATS.spheres = 0; STATS.texts = 0;
}

export function kingStats() {
  return { figures: figureCache.size, spheres: sphereCache.size, texts: textCache.size,
           built: { ...STATS },
           caps: { figures: FIGURE_CACHE_MAX, spheres: SPHERE_CACHE_MAX, texts: TEXT_CACHE_MAX } };
}

/** The authored grid, shaded, for an art check that wants to count pixels or
 *  print him. Never used on a draw path. */
export function kingGrid() { return shadedGrid(); }
