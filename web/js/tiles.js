/* Terrain: a 16-bit tile renderer with real edges.
 *
 * pixel.js draws things. This module draws the ground they stand on, and it
 * exists because a tilemap is not a grid of independent squares — it is a few
 * terrain masses that meet each other, and the meeting is the art. Grass ends in
 * a bank; water answers it with foam; a path wears into the verge it crosses; a
 * cliff has a top you look down from and a face you look at.
 *
 * Everything is generated from a palette and an integer seed, so a region looks
 * the same on every machine and in every session, and nothing here is traced or
 * sampled from any existing game.
 *
 * Six ideas carry the file:
 *
 *   1. Object tiles do not bake ground. A tree is a transparent sprite standing
 *      on grass, not a 16x16 square of almost-the-right green. That is what stops
 *      the world reading as tiles.
 *
 *   2. Colour moves through hue, not just brightness. ramp() shifts shadows
 *      toward blue-violet and lights toward yellow, which is the difference
 *      between pixel art and tinted plastic.
 *
 *   3. Variant selection is hashed, never linear. (x*7+y*3)%4 is a diagonal
 *      stripe wearing a costume.
 *
 *   4. ONE LIGHT, from the upper left, low and hot. Every lit rim, every cast
 *      shadow, every contact shadow and every bottom band in this file agrees
 *      with LIGHT_DX/LIGHT_DY. A scene with two light directions reads as a
 *      collage no matter how good the individual tiles are — this is the single
 *      largest thing separating "pixel art" from "a pile of pixel sprites".
 *
 *   5. Edges interlock, they do not abut. Where two terrains meet, the higher
 *      one reaches into the lower with teeth of varying depth, its trailing edge
 *      lit where it faces the light and shadowed where it faces away, and it
 *      throws ambient occlusion onto the ground it overhangs. Corners are the
 *      whole game: a corner where both cardinals are covered but the diagonal is
 *      not must be CONCAVE — cut back — or the coastline is a checkerboard with
 *      rounded corners, which is the exact failure this rewrite exists to kill.
 *
 *   6. Nothing animated allocates. Every frame of every animation is rasterised
 *      once at scene build and the render loop is drawImage against a cache that
 *      createScene has already warmed from the map's own census of masks, so the
 *      first second of play does not stutter while it builds its own fringes.
 */
import { PALETTES } from './pixel.js';

const TILE = 16;
export const TILE_SIZE = TILE;

/* Codes 0-9 are exactly overworld.js TILES, so a map grid can be handed over
 * untouched. 10+ are emitted by this module's own passes. */
export const TERRAIN = {
  GRASS: 0, PATH: 1, WATER: 2, TREE: 3, CLIFF: 4, STONE: 5,
  BUILDING: 6, SHRINE: 7, CHEST: 8, LAVA: 9,
  BRIDGE: 10, SAND: 11,
};

/* What a code stands ON. A tree, a chest and a house all stand on grass; their
 * bodies live on the object layer, so the ground under them joins the field. */
const GROUND_OF = {
  0: 'grass', 1: 'path', 2: 'water', 3: 'grass', 4: 'cliff', 5: 'stone',
  6: 'grass', 7: 'grass', 8: 'grass', 9: 'lava', 10: 'path', 11: 'sand',
};

/* Who bleeds into whom. Higher priority paints its fringe into the lower one,
 * which is why the shore is grass reaching into water rather than water
 * reaching onto land. Cliff is excluded from fringing entirely — elevation is
 * expressed by a face and a cast shadow, not by a dithered band. */
const PRIORITY = { water: 0, lava: 0, sand: 1, grass: 2, path: 3, stone: 4, cliff: 9 };

/* Anything on this list stands tall enough to occlude the ground beside it and
 * to throw a shadow across it. */
const TALL = new Set([TERRAIN.TREE, TERRAIN.CLIFF, TERRAIN.BUILDING, TERRAIN.SHRINE]);

const WATER_FRAMES = 6;
const FOAM_FRAMES = 4;
const SWAY_FRAMES = 4;
const FLAME_FRAMES = 6;
const FRINGE_VARIANTS = 4;
const DETAIL_VARIANTS = 8;
const GROUND_VARIANTS = 6;

/* THE LIGHT. Upper left, low, hot — docs/09-story-bible.md §8. Everything that
 * casts, occludes or catches a rim in this file reads these two numbers. */
const LIGHT_DX = -1, LIGHT_DY = -1;

/* The one near-black the whole game shares, from palette.js OUTLINE. Contact
 * shadow, cast shadow and the band under every solid are all this colour at
 * different densities, which is most of why they read as the same darkness
 * rather than as four different greys. */
const INK = '#07060c';

/* ---------- determinism ---------- */

export function hashStr(str) {
  let h = 2166136261;
  for (let i = 0; i < String(str).length; i++) {
    h ^= String(str).charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mix32(a) {
  a = a >>> 0;
  a ^= a >>> 16; a = Math.imul(a, 0x7feb352d);
  a ^= a >>> 15; a = Math.imul(a, 0x846ca68b);
  a ^= a >>> 16;
  return a >>> 0;
}

/* A hash, not a linear form. This is the one-line fix for the diagonal
 * checkerboard: neighbouring cells must not have neighbouring variants. */
export function cellRand(seed, x, y, salt = 0) {
  const a = Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1)
          ^ Math.imul(salt | 0, 0x9e3779b1) ^ (seed | 0);
  return mix32(a) / 4294967296;
}

export function rng(seed) {
  let s = (seed >>> 0) || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

/* Smooth hashed noise with an INTEGER PERIOD, cosine-interpolated.
 *
 * White noise makes a coastline look chewed; this makes it look eroded. The
 * period matters as much as the smoothness: a profile that wraps at `period`
 * means the band leaves the right-hand edge of a tile at exactly the height it
 * entered the left-hand edge of the next one, so a run of shore tiles reads as
 * one continuous bank instead of sixteen independent scallops. */
function wave(seed, salt, i, period, span) {
  const s = i / span;
  const i0 = Math.floor(s), f = s - i0;
  const a = cellRand(seed, ((i0 % period) + period) % period, salt, 0x3b);
  const b = cellRand(seed, (((i0 + 1) % period) + period) % period, salt, 0x3b);
  const t = (1 - Math.cos(f * Math.PI)) * 0.5;
  return a + (b - a) * t;
}

/* ---------- colour ---------- */

function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

function parseHex(hex) {
  let h = String(hex || '#000000').replace('#', '');
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  // An eight-digit value carries an alpha byte. Honouring it would punch a
  // translucent hole through an offscreen tile, so it is dropped loudly-in-
  // comment rather than silently in maths (see PALETTES.sun.ground2).
  if (h.length > 6) h = h.slice(0, 6);
  const n = parseInt(h, 16);
  if (!Number.isFinite(n)) return [0, 0, 0];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex(r, g, b) {
  const c = (v) => Math.max(0, Math.min(255, Math.round(v)));
  return `#${((c(r) << 16) | (c(g) << 8) | c(b)).toString(16).padStart(6, '0')}`;
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  const l = (mx + mn) / 2;
  let h = 0, s = 0;
  if (d > 0) {
    s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
    if (mx === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (mx === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return [h, s, l];
}

function hue2rgb(p, q, t) {
  if (t < 0) t += 1;
  if (t > 1) t -= 1;
  if (t < 1 / 6) return p + (q - p) * 6 * t;
  if (t < 1 / 2) return q;
  if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
  return p;
}

function hslToRgb(h, s, l) {
  h = (((h % 360) + 360) % 360) / 360;
  s = clamp01(s); l = clamp01(l);
  if (s <= 0) { const v = l * 255; return [v, v, v]; }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  return [hue2rgb(p, q, h + 1 / 3) * 255, hue2rgb(p, q, h) * 255, hue2rgb(p, q, h - 1 / 3) * 255];
}

/* Nudge a hue along the shortest arc toward `target`, capped at `amt` degrees. */
function towardHue(h, target, amt) {
  const d = ((target - h + 540) % 360) - 180;
  return (h + Math.sign(d) * Math.min(Math.abs(d), amt) + 360) % 360;
}

const SHADOW_HUE = 255;  // blue-violet: what light leaves behind
const LIGHT_HUE = 50;    // warm yellow: what light is made of

/* Five values, darkest first: [shadow2, shadow1, base, light1, light2].
 * Shadows gain saturation and cool; lights lose saturation and warm. A constant
 * added to R, G and B alike — which is what the rest of the codebase does — is
 * the reason every surface currently looks like painted plastic. */
export function ramp(hex) {
  const [r, g, b] = parseHex(hex);
  const [h, s, l] = rgbToHsl(r, g, b);
  const mk = (hh, ss, ll) => toHex(...hslToRgb(hh, ss, ll));
  return [
    mk(towardHue(h, SHADOW_HUE, 22), s * 1.30 + 0.04, l * 0.50),
    mk(towardHue(h, SHADOW_HUE, 12), s * 1.14 + 0.02, l * 0.74),
    toHex(r, g, b),
    mk(towardHue(h, LIGHT_HUE, 10), s * 0.90, l + (1 - l) * 0.26),
    mk(towardHue(h, LIGHT_HUE, 18), s * 0.74, l + (1 - l) * 0.48),
  ];
}

/* Sample a ramp with -2..+2 addressing, clamped. */
export function tone(R, step) {
  const i = Math.max(0, Math.min(4, 2 + Math.round(step)));
  return R[i];
}

export function mixHex(a, b, t) {
  const A = parseHex(a), B = parseHex(b);
  return toHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t);
}

/* Occlusion is not "the same colour, darker". Light that reaches a crevice has
 * bounced, so it is cooler and more saturated as well as dimmer — the same
 * reasoning as ramp(), applied to contact rather than to form. */
function occlude(hex, amount) {
  return mixHex(hex, mixHex(INK, '#1a1230', 0.35), clamp01(amount));
}

/* Recolour toward a hue while keeping the source's value structure. Used to pull
 * a water colour out of a palette that has no water in it. */
function reHue(hex, targetHue, amt, satFloor, lightness) {
  const [r, g, b] = parseHex(hex);
  const [h, s, l] = rgbToHsl(r, g, b);
  return toHex(...hslToRgb(towardHue(h, targetHue, amt), Math.max(s, satFloor),
                           lightness == null ? l : lightness));
}

/* Rock, from whatever a palette happens to have in its middle distance.
 *
 * Stone is the one material that must not take the region's hue at full
 * strength: a palette with a teal middle distance produces a mint-green cliff,
 * which reads as painted plasterboard rather than as the thing the world is
 * built out of. Cool it toward the shadow hue, cut most of the saturation, and
 * keep just enough for the region to still own it. */
function rockFrom(hex) {
  const [r, g, b] = parseHex(hex);
  const [h, s, l] = rgbToHsl(r, g, b);
  return toHex(...hslToRgb(towardHue(h, SHADOW_HUE, 34), s * 0.34 + 0.02, l * 0.94));
}

/* ---------- raster helpers ---------- */

function make(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

function px(ctx, x, y, w, h, colour) {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, w, h);
}

/* Ordered 4x4 dither. Deterministic, so two tiles that share a boundary agree
 * about where the speckle falls and the seam does not shimmer. */
const BAYER = [
  [0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5],
];
function bayer(x, y) { return (BAYER[y & 3][x & 3] + 0.5) / 16; }

function memo(map, key, build) {
  let v = map.get(key);
  if (v === undefined) { v = build(); map.set(key, v); }
  return v;
}

/* A hard-edged ellipse on the pixel grid.
 *
 * ctx.ellipse() + fill() antialiases, and an antialiased edge is a half-pixel —
 * it breaks rule 2 of docs/08-art-direction.md on every single object in the
 * world at once. Scanlines of integer width do not. */
function pxEllipse(ctx, cx, cy, rx, ry, colour, dither = 0) {
  if (rx < 0.5 || ry < 0.5) return;
  ctx.fillStyle = colour;
  const y0 = Math.ceil(cy - ry), y1 = Math.floor(cy + ry);
  for (let y = y0; y <= y1; y++) {
    const dy = (y + 0.5 - cy) / ry;
    const q = 1 - dy * dy;
    if (q <= 0) continue;
    const half = Math.max(0.5, rx * Math.sqrt(q));
    const x0 = Math.round(cx - half), x1 = Math.round(cx + half);
    if (!dither) { ctx.fillRect(x0, y, Math.max(1, x1 - x0), 1); continue; }
    for (let x = x0; x < x1; x++) if (bayer(x, y) >= dither) ctx.fillRect(x, y, 1, 1);
  }
}

/* ---------- the shadow ink ladder ----------
 *
 * Every shadow in the world is ONE ink at a quantised depth, for two reasons
 * that both cost colours. Translucent ink stamped twice composites to a THIRD
 * alpha, so a cast shadow crossing a contact shadow silently invents tones that
 * are in no ramp - the same trap the shore overhang further down is written to
 * avoid. And a `strength` multiplier on a float alpha hands every caller its own
 * private black, which is how one tile ends up with six of them.
 *
 * So shadows accumulate as integer DEPTH into a plate and are painted once, at
 * one of four alphas. The rungs are 1-(1-q)^k - what k coats of the same ink
 * actually composite to - so depth stays physical and the ladder is closed under
 * stacking. Four rungs is the entire vocabulary of darkness on the ground. */
const INK_Q = 0.22;
const INK_DEPTHS = 4;
const INK_STR = [];
const INK_ALPHA = [];
for (let k = 1; k <= INK_DEPTHS; k++) {
  const a = 1 - Math.pow(1 - INK_Q, k);
  INK_ALPHA.push(a);
  INK_STR.push(`rgba(7,6,12,${a.toFixed(3)})`);
}

/* One plate, reused: object sprites are cached, but a fresh mask on every cache
 * miss is still an allocation nobody needs. 64x64 covers every object built
 * here, the largest being the 40x36 building plate. */
const INK_MAX = 64;
const INK_PLATE = new Uint8Array(INK_MAX * INK_MAX);
const COV_PLATE = new Uint8Array(INK_MAX * INK_MAX);
let inkW = 0, inkH = 0, inkOpen = false, inkCap = INK_DEPTHS;

/* `cap` is how many of the four rungs this sprite may spend. A sprite that has
 * already declared a full fifteen can afford exactly one tone of shadow, and
 * says so; everything else gets the whole ladder. */
function inkBegin(w, h, cap) {
  inkW = Math.max(0, Math.min(INK_MAX, w | 0));
  inkH = Math.max(0, Math.min(INK_MAX, h | 0));
  inkCap = Math.max(1, Math.min(INK_DEPTHS, cap || INK_DEPTHS));
  INK_PLATE.fill(0, 0, inkW * inkH);
  inkOpen = true;
}
function inkMark(x, y, depth) {
  if (depth <= 0) return;
  x |= 0; y |= 0;
  if (x < 0 || y < 0 || x >= inkW || y >= inkH) return;
  const i = y * inkW + x;
  const v = INK_PLATE[i] + depth;
  INK_PLATE[i] = v > inkCap ? inkCap : v;
}
/* A continuous alpha, rendered as ordered dither BETWEEN two neighbouring rungs.
 *
 * This is the only honest way to keep a soft gradient on a four-tone ladder, and
 * it is what the hardware this look comes from actually did. A band that fades
 * 0.46 -> 0.06 used to be six literal alphas; it is now two adjacent rungs mixed
 * by a 4x4 Bayer threshold, which reads the same at scale and costs two colours
 * instead of six. Depths ADD where bands overlap, because overlapping shadow IS
 * darker, and saturate at INK_DEPTHS so the count can never run away. */
function inkMarkA(x, y, a) {
  if (!(a > 0)) return;
  let k = 1;
  while (k < inkCap && INK_ALPHA[k - 1] < a) k++;
  const hi = INK_ALPHA[k - 1];
  const lo = k > 1 ? INK_ALPHA[k - 2] : 0;
  const cover = hi <= lo ? 1 : (a - lo) / (hi - lo);
  if (bayer(x, y) < cover) inkMark(x, y, k);
  else if (k > 1) inkMark(x, y, k - 1);
}

/* pxEllipse's scanline walk, writing depth instead of colour. */
function inkEllipse(cx, cy, rx, ry, depth, dither = 0) {
  if (rx < 0.5 || ry < 0.5) return;
  const y0 = Math.ceil(cy - ry), y1 = Math.floor(cy + ry);
  for (let y = y0; y <= y1; y++) {
    const dy = (y + 0.5 - cy) / ry;
    const q = 1 - dy * dy;
    if (q <= 0) continue;
    const half = Math.max(0.5, rx * Math.sqrt(q));
    const x0 = Math.round(cx - half), x1 = Math.round(cx + half);
    if (!dither) { const end = Math.max(x0 + 1, x1); for (let x = x0; x < end; x++) inkMark(x, y, depth); continue; }
    for (let x = x0; x < x1; x++) if (bayer(x, y) >= dither) inkMark(x, y, depth);
  }
}
/* Paint the plate: every pixel once, at most four fillStyle changes. */
function inkFlush(ctx) {
  if (!inkOpen) return;
  for (let d = 1; d <= INK_DEPTHS; d++) {
    let styled = false;
    for (let y = 0; y < inkH; y++) {
      for (let x = 0; x < inkW; x++) {
        if (INK_PLATE[y * inkW + x] !== d) continue;
        if (!styled) { ctx.fillStyle = INK_STR[d - 1]; styled = true; }
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }
  inkOpen = false;
}

/* The dark under a thing that touches the ground.
 *
 * Two parts, because contact is two things: an opaque core right under the mass
 * (ambient occlusion — light physically cannot get in there) and a dithered
 * skirt that falls away from the light (the cast shadow). Drawing only the soft
 * blob, which is the usual shortcut, makes every object look like it is hovering
 * a pixel above the floor. */
function contactShadow(ctx, cx, cy, rx, ry, strength = 1) {
  /* Pairs with castShadow, which opens the plate; this closes it. Called alone
   * it opens its own, so an object with contact but no cast still lands. */
  if (!inkOpen) inkBegin(ctx.canvas ? ctx.canvas.width : INK_MAX,
                         ctx.canvas ? ctx.canvas.height : INK_MAX);
  const deep = strength >= 0.85 ? 2 : 1;     // core: ambient occlusion
  inkEllipse(cx - LIGHT_DX * (rx * 0.22), cy - LIGHT_DY * 0.5,
             rx * 1.14, ry * 1.15, 1, 0.45); // skirt: one coat, dithered
  inkEllipse(cx, cy, rx, ry, deep);
  inkFlush(ctx);
}

/* The band of darkness across the bottom of every solid in the world. One pixel
 * of the object's own deepest tone, then the ground's occlusion under it: this
 * is what makes a rock sit IN the field instead of ON a photograph of it. */
function bottomBand(ctx, x, y, w, colour) {
  px(ctx, x, y, w, 1, colour);
}

/* ---------- blob masks ---------- */
const N = 1, NE = 2, E = 4, SE = 8, S = 16, SW = 32, W = 64, NW = 128;

/* Bit order: 1 N, 2 NE, 4 E, 8 SE, 16 S, 32 SW, 64 W, 128 NW.
 * A diagonal only matters when both of its cardinals agree, which collapses 256
 * neighbourhoods to 82 distinct cases — few enough to generate and memoise, many
 * enough that corners read. It is two per corner more than the classic 47-tile
 * blob set, because a diagonal with neither cardinal earns a tongue here rather
 * than being discarded. */
export function edgeMask(m) {
  let r = m & 0b01010101;
  const keep = (bit, a, b) => {
    const both = (m & a) && (m & b);
    const neither = !(m & a) && !(m & b);
    // Both cardinals: the overlay wraps the corner. Neither: it only touches
    // diagonally, which wants a small tongue rather than a band. One of the two
    // is already covered by that side's band and the diagonal adds nothing.
    if (m & bit && (both || neither)) r |= bit;
  };
  keep(NE, N, E); keep(SE, S, E); keep(SW, S, W); keep(NW, N, W);
  return r;
}

/* Rotate a tile-local (i, k) — distance i along an edge, depth k into the tile —
 * into pixel coordinates for side `dir` (0 N, 1 E, 2 S, 3 W). Every edge routine
 * in this file goes through here, which is the only reason their silhouettes
 * agree at the corners where two of them meet. */
function edgePx(dir, i, k, out) {
  if (dir === 0) { out[0] = i; out[1] = k; }
  else if (dir === 1) { out[0] = TILE - 1 - k; out[1] = i; }
  else if (dir === 2) { out[0] = i; out[1] = TILE - 1 - k; }
  else { out[0] = k; out[1] = i; }
  return out;
}

/* Does side `dir` face the light? N and W do; S and E do not. This one predicate
 * is what gives a whole continent one light direction. */
function sideLit(dir) { return dir === 1 || dir === 2; }

/* ---------- biome character ---------- */

/* The rule this table exists to satisfy: a screenshot of any region must be
 * identifiable as that region with the UI cropped off. Palette alone will not do
 * it — two regions on the same palette with the same tiles are the same place in
 * different lighting. So biome picks the SURFACE (what the ground is made of),
 * the ROCK (how stone fractures), the WATER (what is dissolved in it), the
 * scatter it litters itself with, and whether anything is burning.
 *
 *   surf   meadow wild moss rot scrub gravel ash snow cinder flag bone glass
 *   rock   strata basalt ice brick ore boneRock
 *   water  clear murk ice tar blood
 */
const BIOME_STYLE = {
  village:    { surf: 'meadow', rock: 'strata', water: 'clear',  fire: 'lantern', banner: true,  pine: false, grain: 1.0 },
  grass:      { surf: 'wild',   rock: 'strata', water: 'clear',  fire: null,      banner: false, pine: false, grain: 1.0 },
  forest:     { surf: 'moss',   rock: 'strata', water: 'clear',  fire: null,      banner: false, pine: false, grain: 1.1,
                tint: ['#2c4a22', 0.20] },
  deepforest: { surf: 'moss',   rock: 'strata', water: 'murk',   fire: 'torch',   banner: false, pine: true,  grain: 1.3,
                tint: ['#101a22', 0.34], rockTint: ['#171428', 0.30] },
  canopy:     { surf: 'moss',   rock: 'strata', water: 'clear',  fire: null,      banner: false, pine: true,  grain: 1.2,
                tint: ['#2a5a2c', 0.18] },
  swamp:      { surf: 'rot',    rock: 'strata', water: 'murk',   fire: null,      banner: false, pine: false, grain: 1.3,
                tint: ['#2a3a20', 0.26] },
  cave:       { surf: 'gravel', rock: 'basalt', water: 'tar',    fire: 'torch',   banner: false, pine: false, grain: 0.8,
                tint: ['#14121e', 0.42], rockTint: ['#141220', 0.28] },
  mine:       { surf: 'gravel', rock: 'ore',    water: 'tar',    fire: 'torch',   banner: false, pine: false, grain: 0.9,
                tint: ['#2a1810', 0.30], rockTint: ['#3a1c0c', 0.22] },
  mountain:   { surf: 'snow',   rock: 'ice',    water: 'ice',    fire: null,      banner: false, pine: true,  grain: 0.7,
                tint: ['#9fbcd8', 0.30], rockTint: ['#6f96bc', 0.22] },
  highland:   { surf: 'scrub',  rock: 'strata', water: 'clear',  fire: 'lantern', banner: true,  pine: true,  grain: 1.0,
                tint: ['#6a6a48', 0.16] },
  citadel:    { surf: 'flag',   rock: 'brick',  water: 'clear',  fire: 'brazier', banner: true,  pine: false, grain: 0.6,
                tint: ['#3a2e58', 0.22], rockTint: ['#2e2450', 0.24] },
  ruins:      { surf: 'scrub',  rock: 'brick',  water: 'murk',   fire: 'brazier', banner: false, pine: false, grain: 1.1,
                tint: ['#4a4028', 0.20], rockTint: ['#4a3c1c', 0.16] },
  wastes:     { surf: 'ash',    rock: 'basalt', water: 'tar',    fire: 'pyre',    banner: false, pine: false, grain: 1.2,
                tint: ['#23232c', 0.36], rockTint: ['#1c1c24', 0.30] },
  dungeon:    { surf: 'flag',   rock: 'brick',  water: 'tar',    fire: 'torch',   banner: false, pine: false, grain: 0.7,
                tint: ['#16161e', 0.40], rockTint: ['#181820', 0.30] },
  tower:      { surf: 'glass',  rock: 'brick',  water: 'clear',  fire: 'brazier', banner: true,  pine: false, grain: 0.6,
                tint: ['#1e3a4a', 0.26], rockTint: ['#1a3646', 0.22] },
  arena:      { surf: 'bone',   rock: 'basalt', water: 'blood',  fire: 'pyre',    banner: true,  pine: false, grain: 1.0,
                tint: ['#5a3a20', 0.22] },
  castle:     { surf: 'flag',   rock: 'brick',  water: 'blood',  fire: 'brazier', banner: true,  pine: false, grain: 0.7,
                tint: ['#2a1016', 0.26], rockTint: ['#2a1218', 0.22] },
};

export function biomeStyle(biome) { return BIOME_STYLE[biome] || BIOME_STYLE.grass; }

/* Which surfaces bear plants. Ash, cinder, snow, gravel, bone, glass and a cut
 * stone floor do not — scattering flowers across them is the fastest way to
 * undo everything the biome table just established, because the eye reads a
 * flower as "somewhere things live" before it reads anything else in the frame.
 * Dry stubble is still allowed: something always clings on. */
const BEARING = new Set(['meadow', 'wild', 'moss', 'rot', 'scrub']);

/* What each surface litters itself with, and how often. The weights are the
 * whole reason a wastes screenshot is bone and cracked plate while a canopy
 * screenshot is clover and fallen twigs, on the same eight-slot machinery. */
const SURFACE_SCATTER = {
  meadow: ['tuft', 'tuft', 'clover', 'clover', 'pebble', 'twig', 'divot', 'bloom'],
  wild:   ['tuft', 'tuft', 'thistle', 'pebble', 'twig', 'divot', 'clover', 'stone'],
  moss:   ['moss', 'moss', 'clover', 'twig', 'fungus', 'root', 'tuft', 'stone'],
  rot:    ['pool', 'pool', 'moss', 'bubble', 'reedstub', 'twig', 'fungus', 'bone'],
  scrub:  ['dry', 'dry', 'pebble', 'crack', 'thistle', 'stone', 'twig', 'divot'],
  gravel: ['pebble', 'pebble', 'rubble', 'crack', 'stone', 'grit', 'chip', 'divot'],
  ash:    ['drift', 'drift', 'grit', 'crack', 'bone', 'ember', 'chip', 'rubble'],
  snow:   ['drift', 'dimple', 'drift', 'dimple', 'stone', 'drift', 'dimple', 'drift'],
  cinder: ['crack', 'crack', 'ember', 'rubble', 'grit', 'chip', 'ember', 'stone'],
  flag:   ['crack', 'chip', 'rubble', 'stain', 'grit', 'moss', 'crack', 'divot'],
  bone:   ['bone', 'bone', 'grit', 'chip', 'stain', 'rubble', 'crack', 'pebble'],
  glass:  ['shard', 'shard', 'chip', 'crack', 'glint', 'grit', 'rubble', 'stone'],
};

/* ---------- palette expansion ---------- */

function palOf(palette, style) {
  if (palette && palette.__ramps && !style) return palette;
  if (palette && palette.__ramps) palette = palette.raw;
  const pal = typeof palette === 'string'
    ? (PALETTES[palette] || PALETTES.spring)
    : (palette || PALETTES.spring);
  const st = style || BIOME_STYLE.grass;
  const tintOf = (hex, spec) => spec ? mixHex(hex, spec[0], spec[1]) : hex;

  // Water, dirt, rock, sand and bark are not in the sixteen authored palettes.
  // Deriving them here — rather than reusing `sky` for water, which is why one
  // village lake is indigo and indistinguishable from the void behind the map —
  // keeps regional identity without letting water stop looking like water.
  const waterHue = { clear: 205, murk: 120, ice: 190, tar: 265, blood: 356 }[st.water] || 205;
  const waterSat = { clear: 0.42, murk: 0.34, ice: 0.26, tar: 0.20, blood: 0.52 }[st.water] || 0.42;
  const waterLit = { clear: 0.34, murk: 0.19, ice: 0.52, tar: 0.13, blood: 0.22 }[st.water] || 0.34;
  const waterBase = pal.water || reHue(pal.sky, waterHue, 90, waterSat, waterLit);

  const P = {
    __ramps: true,
    raw: pal,
    style: st,
    ground: ramp(tintOf(pal.ground, st.tint)),
    ground2: ramp(tintOf(pal.ground2, st.tint)),
    mid: ramp(pal.mid),
    far: ramp(pal.far),
    sky: ramp(pal.sky),
    accent: ramp(pal.accent),
    foliage: ramp(tintOf(pal.foliage || pal.mid, st.tint)),
    dark: ramp(pal.dark),
    dirt: ramp(st.tint
      ? mixHex(mixHex(reHue(pal.accent, 32, 180, 0.30, 0.32), pal.ground, 0.30), st.tint[0], st.tint[1] * 0.35)
      : mixHex(reHue(pal.accent, 32, 180, 0.30, 0.32), pal.ground, 0.30)),
    rock: ramp(tintOf(rockFrom(pal.far), st.rockTint)),
    sand: ramp(mixHex(mixHex(pal.accent, '#b5a488', 0.58), pal.ground, 0.26)),
    bark: ramp('#4a3320'),
    water: null,
    wet: null,
  };
  // Five water values from shore to deep: the depth gradient is a ramp of its
  // own so the shelf can be light and the middle genuinely dark.
  const wr = ramp(waterBase);
  P.water = [
    wr[0], wr[1], wr[2], wr[3],
    mixHex(wr[4], '#ffffff', st.water === 'tar' ? 0.34 : 0.62),
  ];
  // Wet sand is not darker sand. It is sand with a thin film of the water lying
  // on it, so it takes the water's hue as well as its value, and it takes a
  // specular the dry beach two pixels away does not have.
  P.wet = ramp(mixHex(mixHex(P.sand[1], P.water[1], 0.44), INK, 0.10));
  P.paved = st.surf === 'flag' || st.surf === 'glass' || st.surf === 'cinder';
  P.road = P.paved ? ramp(mixHex(P.rock[2], P.dirt[2], 0.34)) : P.dirt;
  return P;
}

/* ---------- surface primitives ---------- */
/* Six marks make every ground surface in the game. They all obey the one light:
 * a lit pixel goes up-left of the form, the occlusion goes down-right of it. */

function mottle(ctx, seed, salt, hi, lo, hiT, loT, alt, altT, base, k) {
  // `base` and `k` pull the two speckle tones back toward the surface colour.
  // Grain at full ramp contrast on every pixel is television static; the mosaic
  // effect wants texture you read at arm's length and stop seeing up close.
  const H = base ? mixHex(base, hi, k) : hi;
  const L = base ? mixHex(base, lo, k) : lo;
  const A = alt && base ? mixHex(base, alt, Math.min(1, k + 0.25)) : alt;
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const n = cellRand(seed, x, y, salt);
      if (n > hiT) px(ctx, x, y, 1, 1, H);
      else if (n < loT) px(ctx, x, y, 1, 1, L);
      else if (A && n > altT && bayer(x, y) < 0.42) px(ctx, x, y, 1, 1, A);
    }
  }
}

/* A blade of grass: dark at the foot where it is in its own shade, lit at the
 * tip where it is not, and it leans away from the light like everything else. */
function blade(ctx, x, y, h, dark, lit) {
  for (let k = 0; k < h; k++) px(ctx, x + (k === h - 1 ? -LIGHT_DX * 0 : 0), y + k, 1, 1, dark);
  px(ctx, x, y, 1, 1, lit);
}

/* A pebble, a rubble chip, a bone flake: anything small, hard and lying on the
 * ground. Lit face up-left, occlusion down-right, one pixel each. */
function chip(ctx, x, y, w, R, up = 3, down = 0) {
  px(ctx, x, y, w, 1, R[up]);
  px(ctx, x, y + 1, w, 1, R[1]);
  px(ctx, x + 1, y + 2, w, 1, R[down]);
}

/* A crack. Walks with hashed jitter instead of ruling a line, and carries a
 * lit lip on its upper-left side — a crack is a tiny cliff. */
function crack(ctx, seed, salt, x, y, len, vertical, dark, lip) {
  let a = x, b = y;
  for (let k = 0; k < len; k++) {
    if (a < 0 || b < 0 || a >= TILE || b >= TILE) break;
    px(ctx, a, b, 1, 1, dark);
    if (lip && k % 2 === 0) {
      const lx = a + (vertical ? LIGHT_DX : 0), ly = b + (vertical ? 0 : LIGHT_DY);
      if (lx >= 0 && ly >= 0 && lx < TILE && ly < TILE) px(ctx, lx, ly, 1, 1, lip);
    }
    const j = cellRand(seed, k, salt, 0x2c);
    if (vertical) { b++; if (j > 0.72) a++; else if (j < 0.26) a--; }
    else { a++; if (j > 0.72) b++; else if (j < 0.26) b--; }
  }
}

/* A blob of something growing: moss, scum, lichen. Circular-ish, lit on the
 * upper left, with the ground showing through at the edges. */
function clump(ctx, cx, cy, r, mid, lit, dark) {
  for (let y = cy - r; y <= cy + r; y++) {
    for (let x = cx - r; x <= cx + r; x++) {
      if (x < 0 || y < 0 || x >= TILE || y >= TILE) continue;
      const d = Math.hypot(x - cx, y - cy);
      if (d > r) continue;
      const edge = d > r - 1.1;
      const up = (x - cx) + (y - cy) < -r * 0.4;
      px(ctx, x, y, 1, 1, edge ? dark : up ? lit : mid);
    }
  }
}

/* ---------- ground tiles ---------- */

/* The main walkable surface. One routine, twelve materials, because the parts
 * that must agree — the grain, the light direction, the value range — are the
 * parts that are shared, and the parts that must differ are a dozen lines each. */
function surfaceTile(P, st, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const R = P.ground, R2 = P.ground2, F = P.foliage, Rk = P.rock;
  const D = P.dirt, Sd = P.sand, A = P.accent, Wt = P.water;
  const rand = rng(seed + variant * 7919 + 1);
  const g = st.grain == null ? 1 : st.grain;
  const S = seed + variant * 31;

  switch (st.surf) {

    case 'meadow': {
      px(ctx, 0, 0, TILE, TILE, R[2]);
      mottle(ctx, S, 3, R[3], R[1], 0.88 - 0.06 * g, 0.10 * g, variant >= 2 ? R2[2] : null, 0.62);
      for (let i = 0, n = 4 + Math.floor(rand() * 3); i < n; i++) {
        const x = 1 + Math.floor(rand() * (TILE - 2)), y = 2 + Math.floor(rand() * (TILE - 5));
        blade(ctx, x, y, 3, R[1], R[3]);
        if (rand() < 0.5) px(ctx, x + 1, y + 3, 1, 1, R[0]);
      }
      for (let i = 0; i < 3; i++) {
        const x = Math.floor(rand() * TILE), y = Math.floor(rand() * TILE);
        px(ctx, x, y, 1, 1, F[3]);
      }
      break;
    }

    case 'wild': {
      px(ctx, 0, 0, TILE, TILE, R[2]);
      mottle(ctx, S, 3, R[3], R[1], 0.84, 0.14, R2[2], 0.58);
      if (variant % 3 === 0) clump(ctx, 3 + Math.floor(rand() * 9), 3 + Math.floor(rand() * 9),
                                   3, D[2], D[3], D[1]);
      for (let i = 0, n = 5 + Math.floor(rand() * 3); i < n; i++) {
        const x = 1 + Math.floor(rand() * (TILE - 2)), y = 1 + Math.floor(rand() * (TILE - 6));
        const h = 3 + Math.floor(rand() * 2);
        blade(ctx, x, y, h, R[1], rand() < 0.4 ? mixHex(R[3], A[3], 0.4) : R[3]);
        px(ctx, x + 1, y + h, 1, 1, R[0]);
      }
      break;
    }

    case 'moss': {
      const base = mixHex(R[2], F[2], 0.34);
      px(ctx, 0, 0, TILE, TILE, base);
      mottle(ctx, S, 3, F[3], mixHex(R[0], F[0], 0.5), 0.80, 0.22, F[2], 0.52);
      for (let i = 0, n = 2 + (variant % 2); i < n; i++) {
        clump(ctx, 2 + Math.floor(rand() * 12), 2 + Math.floor(rand() * 12),
              2 + Math.floor(rand() * 2), F[2], F[3], F[0]);
      }
      for (let i = 0; i < 3; i++) {
        const x = 1 + Math.floor(rand() * 14), y = 2 + Math.floor(rand() * 12);
        px(ctx, x, y, 1, 2, F[1]); px(ctx, x, y, 1, 1, F[4]);
      }
      break;
    }

    case 'rot': {
      const base = mixHex(R[1], Wt[1], 0.28);
      px(ctx, 0, 0, TILE, TILE, base);
      mottle(ctx, S, 3, F[2], mixHex(R[0], Wt[0], 0.5), 0.86, 0.30, null, 0);
      // Standing water, and the one specular that says it is water and not mud.
      for (let i = 0, n = 1 + (variant % 2); i < n; i++) {
        const cx = 3 + Math.floor(rand() * 10), cy = 3 + Math.floor(rand() * 10);
        const r = 2 + Math.floor(rand() * 2);
        pxEllipse(ctx, cx, cy, r + 1, r, Wt[1]);
        pxEllipse(ctx, cx, cy, r, r - 0.6, Wt[0]);
        px(ctx, cx - 1, cy - 1, 2, 1, Wt[4]);
      }
      for (let i = 0; i < 4; i++) px(ctx, Math.floor(rand() * TILE), Math.floor(rand() * TILE), 1, 1, F[3]);
      break;
    }

    case 'scrub': {
      const base = mixHex(R[2], D[2], 0.46);
      px(ctx, 0, 0, TILE, TILE, base);
      mottle(ctx, S, 3, D[3], D[1], 0.82, 0.24, R[1], 0.60);
      crack(ctx, S, 7, Math.floor(rand() * TILE), 0, 6 + Math.floor(rand() * 6),
            variant % 2 === 0, D[0], D[3]);
      for (let i = 0, n = 2 + Math.floor(rand() * 2); i < n; i++) {
        const x = 1 + Math.floor(rand() * (TILE - 2)), y = 3 + Math.floor(rand() * (TILE - 6));
        blade(ctx, x, y, 2, mixHex(R[1], D[1], 0.5), mixHex(R[3], A[2], 0.35));
      }
      break;
    }

    case 'gravel': {
      px(ctx, 0, 0, TILE, TILE, Rk[2]);
      mottle(ctx, S, 3, Rk[3], Rk[1], 0.80, 0.26, Rk[0], 0.62, Rk[2], 0.6);
      for (let i = 0, n = 4 + Math.floor(rand() * 3); i < n; i++) {
        chip(ctx, Math.floor(rand() * 13), Math.floor(rand() * 13), 1 + Math.floor(rand() * 2), Rk);
      }
      break;
    }

    case 'ash': {
      const base = mixHex(R[1], '#2a2832', 0.56);
      const Ash = ramp(base);
      px(ctx, 0, 0, TILE, TILE, Ash[2]);
      mottle(ctx, S, 3, Ash[3], Ash[1], 0.82, 0.24, Ash[0], 0.62, Ash[2], 0.55);
      // Drift: ash settles in ridges, and a ridge has a lit windward face.
      for (let i = 0, n = 1 + (variant % 2); i < n; i++) {
        const y = 1 + Math.floor(rand() * 13), len = 6 + Math.floor(rand() * 8);
        const x0 = Math.floor(rand() * (TILE - 4));
        for (let k = 0; k < len && x0 + k < TILE; k++) {
          const yy = y + (cellRand(S, k, i, 0x4a) > 0.7 ? 1 : 0);
          if (yy >= TILE) continue;
          px(ctx, x0 + k, yy, 1, 1, mixHex(Ash[2], Ash[4], 0.7));
          if (yy + 1 < TILE) px(ctx, x0 + k, yy + 1, 1, 1, mixHex(Ash[2], Ash[0], 0.6));
        }
      }
      if (variant % 3 === 0) px(ctx, 4 + Math.floor(rand() * 8), 4 + Math.floor(rand() * 8), 1, 1, '#e8762a');
      break;
    }

    case 'snow': {
      const Sn = ramp(mixHex(R[4], '#dce8ff', 0.62));
      px(ctx, 0, 0, TILE, TILE, Sn[4]);
      // Snow is the one surface that is mostly nothing. Almost all of its read
      // comes from the few dimples and the long shadows other things cast on it.
      mottle(ctx, S, 3, '#ffffff', Sn[3], 0.93, 0.10, null, 0, Sn[4], 0.45);
      // A dimple in snow is a hole: shadowed on the side toward the light,
      // lit on the far rim. Getting this backwards makes snow look like foam.
      for (let i = 0, n = 1 + (variant % 2); i < n; i++) {
        const x = 1 + Math.floor(rand() * 13), y = 1 + Math.floor(rand() * 13);
        px(ctx, x, y, 3, 1, mixHex(Sn[4], Sn[2], 0.6));
        px(ctx, x, y + 1, 3, 1, mixHex(Sn[4], Sn[1], 0.6));
        px(ctx, x - LIGHT_DX, y + 2, 3, 1, '#ffffff');
      }
      if (variant % 3 === 0) {
        const y = 2 + Math.floor(rand() * 11);
        for (let x = 0; x < TILE; x++) {
          const yy = y + Math.round(wave(S, 5, x, 4, 4) * 1.6) - 1;
          if (yy < 0 || yy >= TILE) continue;
          px(ctx, x, yy, 1, 1, '#ffffff');
          if (yy + 1 < TILE) px(ctx, x, yy + 1, 1, 1, mixHex(Sn[4], Sn[2], 0.55));
        }
      }
      break;
    }

    case 'cinder': {
      const Cn = ramp(mixHex(Rk[1], '#1a0e0c', 0.5));
      px(ctx, 0, 0, TILE, TILE, Cn[2]);
      mottle(ctx, S, 3, Cn[3], Cn[0], 0.80, 0.26, null, 0);
      crack(ctx, S, 9, Math.floor(rand() * TILE), 0, TILE, true, '#e8762a', Cn[0]);
      crack(ctx, S, 11, 0, Math.floor(rand() * TILE), TILE, false, '#a83c10', Cn[0]);
      break;
    }

    case 'flag': {
      // A cut floor: two courses, the joint offset per variant, every slab lit
      // on its up-left lip and occluded into its down-right mortar.
      // The floor of a keep is BIG worn slabs — deliberately a size apart from
      // the small dressed blocks stoneTile lays, because both are cut from the
      // same rock and without that contrast a stone platform standing on a
      // stone courtyard is invisible.
      const base = mixHex(Rk[2], P.dark[2], 0.24);
      px(ctx, 0, 0, TILE, TILE, base);
      mottle(ctx, S, 3, Rk[3], Rk[1], 0.92, 0.14, null, 0, base, 0.5);
      // Courses run through the tile, not around it: the vertical origin moves
      // with the variant so the joint does not land on the same row in every
      // cell, which is the single loudest way a paved floor announces its grid.
      const off = [3, 8, 11, 5, 13, 1][variant % 6];
      const y0 = -((off * 3) % 9);
      const mortar = occlude(Rk[0], 0.42);
      const lip = mixHex(base, Rk[3], 0.7);
      for (let cy = y0, c = 0; cy < TILE; cy += 9, c++) {
        const shift = (off + c * 6) % 11;
        if (cy >= 0) px(ctx, 0, cy, TILE, 1, lip);
        const bot = cy + 8;
        if (bot >= 0 && bot < TILE) px(ctx, 0, bot, TILE, 1, mortar);
        const yTop = Math.max(0, cy), yBot = Math.min(TILE, cy + 9);
        for (let x = shift - 11; x < TILE; x += 11) {
          if (x < 0 || yBot <= yTop) continue;
          px(ctx, x, yTop, 1, yBot - yTop, mortar);
          const t2 = Math.max(0, cy + 1), b2 = Math.min(TILE, cy + 8);
          if (x + 1 < TILE && b2 > t2) px(ctx, x + 1, t2, 1, b2 - t2, lip);
        }
      }
      break;
    }

    case 'bone': {
      const Bn = ramp(mixHex(Sd[2], '#cfc4b0', 0.42));
      px(ctx, 0, 0, TILE, TILE, Bn[2]);
      mottle(ctx, S, 3, Bn[4], Bn[1], 0.86, 0.20, Bn[0], 0.66, Bn[2], 0.55);
      for (let i = 0, n = 2 + (variant % 2); i < n; i++) {
        const x = 1 + Math.floor(rand() * 11), y = 3 + Math.floor(rand() * 10);
        const w = 3 + Math.floor(rand() * 3);
        px(ctx, x, y, w, 1, Bn[4]);
        px(ctx, x, y + 1, w, 1, Bn[1]);
        px(ctx, x - 1, y, 1, 2, Bn[3]); px(ctx, x + w, y, 1, 2, Bn[3]);
        px(ctx, x, y + 2, w, 1, occlude(Bn[0], 0.4));
      }
      break;
    }

    case 'glass': {
      const Gl = ramp(mixHex(Rk[1], A[1], 0.45));
      px(ctx, 0, 0, TILE, TILE, Gl[1]);
      mottle(ctx, S, 3, Gl[2], Gl[0], 0.84, 0.24, null, 0, Gl[1], 0.6);
      // Shards: a triangle of facets, one of which catches the light hard. This
      // is the only surface in the game allowed a true specular.
      for (let i = 0, n = 2 + (variant % 2); i < n; i++) {
        const cx = 3 + Math.floor(rand() * 10), cy = 4 + Math.floor(rand() * 9);
        const h = 3 + Math.floor(rand() * 3);
        for (let k = 0; k < h; k++) {
          const w = Math.max(1, h - k);
          px(ctx, cx - (w >> 1), cy - k, w, 1, k > h - 2 ? A[4] : A[2]);
        }
        px(ctx, cx - 1, cy - h + 1, 1, h - 1, A[3]);
        px(ctx, cx + 1, cy, 1, 1, occlude(Gl[0], 0.5));
      }
      break;
    }

    default: {
      px(ctx, 0, 0, TILE, TILE, R[2]);
      mottle(ctx, S, 3, R[3], R[1], 0.86, 0.10, R2[2], 0.62);
    }
  }
  return canvas;
}

function pathTile(P, st, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const D = P.road;
  if (P.paved) {
    // Inside a keep the road is laid, not worn. Cobbles: a lit crown and an
    // occluded joint on every stone, which is the same two marks as a pebble at
    // four times the size.
    px(ctx, 0, 0, TILE, TILE, D[1]);
    const joint = occlude(D[0], 0.45);
    for (let cy = -((variant * 2) % 4); cy < TILE; cy += 4) {
      const row = ((cy + 16) / 4) | 0;
      const shift = (row & 1) ? 2 : 0;
      for (let cx = -4; cx < TILE; cx += 4) {
        const x = cx + shift;
        if (x >= TILE) continue;
        const n = cellRand(seed + variant * 53, x, cy, 5);
        const xs = Math.max(0, x), xw = Math.min(3, TILE - xs);
        const yt = Math.max(0, cy), yh = Math.min(cy + 3, TILE) - yt;
        if (yh <= 0 || xw <= 0) continue;
        px(ctx, xs, yt, xw, yh, n > 0.62 ? D[3] : n < 0.32 ? D[1] : D[2]);
        if (cy >= 0) px(ctx, xs, yt, xw, 1, D[4]);          // the crown, lit
        if (cy + 3 >= 0 && cy + 3 < TILE) px(ctx, xs, cy + 3, Math.min(4, TILE - xs), 1, joint);
        if (x + 3 >= 0 && x + 3 < TILE) px(ctx, x + 3, yt, 1, Math.min(cy + 4, TILE) - yt, joint);
      }
    }
    return canvas;
  }
  px(ctx, 0, 0, TILE, TILE, D[2]);
  mottle(ctx, seed + variant * 53, 5, D[3], D[1], 0.90, 0.22, null, 0, D[2], 0.55);
  // One cart rut, and only on two variants in three. Ruts on every tile at the
  // same height is corduroy, not a road. The rut has a lit lip on its upper
  // side and its own occlusion in the bottom, which is why it reads as sunken.
  const rand = rng(seed + 311 + variant * 13);
  if (variant % 2 === 0) {
    const ry = 1 + (variant % 4) * 3 + Math.floor(rand() * 3);
    for (let x = 0; x < TILE; x++) {
      // Broken hard, and wandering a pixel: an unbroken rut on every tile at the
      // same height is corduroy, and four of them is a ploughed field.
      if (cellRand(seed, x, ry + variant, 9) < 0.45) continue;
      const yy = ry + Math.round(wave(seed, variant * 31, x, 4, 4) * 1.4) - 1;
      if (yy < 0 || yy + 1 >= TILE) continue;
      px(ctx, x, yy, 1, 1, D[3]);
      px(ctx, x, yy + 1, 1, 1, occlude(D[0], 0.3));
    }
  }
  for (let i = 0; i < 3; i++) {
    chip(ctx, 1 + Math.floor(rand() * 13), 1 + Math.floor(rand() * 12), 2, D);
  }
  return canvas;
}

function stoneTile(P, st, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const Rk = P.rock;
  px(ctx, 0, 0, TILE, TILE, Rk[2]);
  mottle(ctx, seed + variant * 17, 11, Rk[3], Rk[1], 0.90, 0.12, null, 0);
  const mortar = occlude(Rk[0], 0.4);
  if (st.rock === 'brick') {
    // Courses of dressed masonry: every block lit along its top and left, every
    // joint occluded. The course origin moves with the variant, or the whole
    // floor is one ruled grid.
    const y0 = -((variant * 2) % 5);
    for (let cy = y0, c = 0; cy < TILE; cy += 5, c++) {
      const shift = ((c + variant) & 1) ? 4 : 0;
      if (cy >= 0) px(ctx, 0, cy, TILE, 1, Rk[3]);
      if (cy + 4 < TILE && cy + 4 >= 0) px(ctx, 0, cy + 4, TILE, 1, mortar);
      const yt = Math.max(0, cy), yb = Math.min(TILE, cy + 5);
      for (let x = shift - 8; x < TILE; x += 8) {
        if (x >= 0 && yb > yt) px(ctx, x, yt, 1, yb - yt, mortar);
        if (x + 1 >= 0 && x + 1 < TILE && cy + 1 >= 0) {
          const t2 = Math.max(0, cy + 1), b2 = Math.min(TILE, cy + 4);
          if (b2 > t2) px(ctx, x + 1, t2, 1, b2 - t2, Rk[3]);
        }
      }
    }
  } else if (st.rock === 'basalt') {
    // Columnar: prisms four or five pixels across, lit on the left face and
    // occluded on the right. Three-pixel columns at full ramp contrast are a
    // barcode; this is a rock face.
    for (let x = -2; x < TILE; ) {
      const w = 4 + (cellRand(seed, x, variant, 0x51) > 0.55 ? 1 : 0);
      const body = cellRand(seed, x, 1, 0x52) > 0.5 ? Rk[2] : mixHex(Rk[2], Rk[1], 0.6);
      if (x >= 0) px(ctx, x, 0, Math.min(w, TILE - x), TILE, body);
      if (x >= 0) px(ctx, x, 0, 1, TILE, mixHex(body, Rk[3], 0.8));
      if (x + w < TILE) px(ctx, x + w, 0, 1, TILE, mortar);
      const brk = Math.floor(cellRand(seed, x + 7, variant, 0x53) * TILE);
      if (x >= 0) px(ctx, x, brk, Math.min(w + 1, TILE - x), 1, mortar);
      x += w + 1;
    }
  } else if (st.rock === 'ice') {
    for (let i = 0, n = 1 + (variant & 1); i < n; i++) {
      crack(ctx, seed + variant, 0x54 + i, Math.floor(cellRand(seed, i, variant, 0x55) * TILE), 0,
            TILE, true, mixHex(Rk[0], '#1e3450', 0.5), mixHex(Rk[3], '#d8ecff', 0.55));
    }
  } else {
    // Sedimentary: courses that run THROUGH the tile. Starting them at y = 0 in
    // every cell lays a perfect grid over the whole floor, which is the thing a
    // tileset most has to avoid announcing.
    const lip = mixHex(Rk[2], Rk[4], 0.55);
    const y0 = -((variant * 3) % 7);
    for (let cy = y0, c = 0; cy < TILE; cy += 7, c++) {
      for (let x = 0; x < TILE; x++) {
        const yy = cy + Math.round(wave(seed + variant, cy + 7, x, 4, 4) * 1.5) - 1;
        if (cellRand(seed, x, cy + variant, 0x59) < 0.18) continue;
        if (yy >= 0 && yy < TILE) px(ctx, x, yy, 1, 1, lip);
        if (yy + 6 >= 0 && yy + 6 < TILE) px(ctx, x, yy + 6, 1, 1, mortar);
      }
      const jx = (variant * 5 + c * 9) % TILE;
      const yt = Math.max(0, cy), yb = Math.min(TILE, cy + 7);
      if (yb > yt) px(ctx, jx, yt, 1, yb - yt, mortar);
    }
  }
  if (st.rock === 'ore') {
    // A vein, in the region's accent, because a mine you can walk through and
    // never see ore in is a corridor.
    const A = P.accent;
    crack(ctx, seed + variant * 5, 0x56, Math.floor(cellRand(seed, variant, 3, 0x57) * TILE),
          Math.floor(cellRand(seed, variant, 4, 0x58) * 6), 9, variant % 2 === 0, A[2], A[4]);
  }
  return canvas;
}

function sandTile(P, st, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const Sd = P.sand;
  px(ctx, 0, 0, TILE, TILE, Sd[2]);
  mottle(ctx, seed + variant * 91, 13, Sd[3], Sd[1], 0.88, 0.12, null, 0);
  // Ripples. A dune ripple is a tiny ridge and takes the same two-pixel light
  // treatment as everything else that stands up off a surface.
  for (let i = 0, n = 2 + (variant % 2); i < n; i++) {
    const y = 1 + Math.floor(cellRand(seed, i, variant, 0x60) * 12);
    for (let x = 0; x < TILE; x++) {
      const yy = y + Math.round((wave(seed, i * 13 + variant, x, 4, 4) - 0.5) * 4.2);
      if (yy < 0 || yy >= TILE - 1) continue;
      // A ripple dies out and picks up again; a continuous one across every tile
      // is a stave, and sixteen of them in a row is sheet music.
      if (cellRand(seed, x, i * 7 + variant, 0x61) < 0.22) continue;
      px(ctx, x, yy, 1, 1, mixHex(Sd[3], Sd[4], 0.6));
      px(ctx, x, yy + 1, 1, 1, mixHex(Sd[2], Sd[1], 0.7));
    }
  }
  return canvas;
}

/* ---------- detail scatter ---------- */
/* A transparent 16x16 overlay dropped on a fraction of cells, indexed by a hash
 * of the cell. It is what gives a field texture that nobody placed, and it costs
 * one cached canvas per variant and one drawImage per decorated tile — never a
 * per-frame allocation and never a random number in a draw path. */

const DETAIL_FOR = {
  path:  ['pebble', 'crack', 'grit', 'chip', 'divot', 'twig', 'stone', 'rubble'],
  stone: ['crack', 'rubble', 'chip', 'moss', 'stain', 'grit', 'pebble', 'crack'],
  sand:  ['drift', 'stone', 'bone', 'grit', 'chip', 'pebble', 'divot', 'shard'],
  cliff: ['rubble', 'crack', 'chip', 'grit', 'stone', 'moss', 'divot', 'pebble'],
};

/* Which ramp a loose mark on this surface is made of. A mark that does not come
 * out of the ground it lies on is the loudest way a scatter layer stops reading
 * as part of the world: a sand-coloured drift on snow, a bone-white flake on a
 * black floor. */
function surfaceRamp(P, st, cls) {
  if (cls === 'stone' || cls === 'cliff') return P.rock;
  if (cls === 'path') return P.road;
  if (cls === 'sand') return P.sand;
  switch (st.surf) {
    case 'snow':   return ramp(mixHex(P.ground[4], '#dce8ff', 0.62));
    case 'ash':    return ramp(mixHex(P.ground[1], '#2a2832', 0.56));
    case 'gravel': case 'flag': case 'glass': case 'cinder': return P.rock;
    case 'bone':   return ramp(mixHex(P.sand[2], '#cfc4b0', 0.42));
    case 'scrub':  return P.dirt;
    case 'moss':   return P.foliage;
    default:       return P.ground;
  }
}

function detailTile(P, st, cls, v, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const list = cls === 'grass' ? (SURFACE_SCATTER[st.surf] || SURFACE_SCATTER.wild)
                               : (DETAIL_FOR[cls] || DETAIL_FOR.path);
  const kind = list[v % list.length];
  const s = seed + v * 1013 + hashStr(cls) * 7;
  const rand = rng(s || 1);
  const G = surfaceRamp(P, st, cls);
  const R = P.ground, F = P.foliage, D = P.dirt, A = P.accent, Wt = P.water;
  // Hard marks take the surface's own ramp pulled toward rock; soft ones take
  // the surface straight. Either way they stay inside the region's fifteen.
  const Rk = G === P.rock ? P.rock : ramp(mixHex(G[2], P.rock[2], 0.38));
  const Sd = G;
  const x = 2 + Math.floor(rand() * 11), y = 3 + Math.floor(rand() * 10);

  switch (kind) {
    case 'tuft':
      for (let i = 0; i < 3; i++) blade(ctx, x + i - 1, y - (i === 1 ? 1 : 0), 3, R[1], R[3]);
      px(ctx, x, y + 3, 2, 1, occlude(R[0], 0.45));
      break;
    case 'dry':
      for (let i = 0; i < 3; i++) blade(ctx, x + i - 1, y, 2, mixHex(R[1], D[1], 0.6), mixHex(R[3], A[2], 0.5));
      break;
    case 'clover':
      for (const [dx, dy] of [[0, 0], [2, 0], [1, 1]]) {
        px(ctx, x + dx, y + dy, 1, 1, F[3]);
        px(ctx, x + dx, y + dy + 1, 1, 1, F[1]);
      }
      break;
    case 'thistle':
      px(ctx, x, y, 1, 5, R[1]); px(ctx, x, y, 1, 1, R[3]);
      px(ctx, x - 1, y - 1, 3, 1, A[2]); px(ctx, x, y - 2, 1, 1, A[4]);
      break;
    case 'bloom':
      px(ctx, x, y, 1, 3, F[1]);
      px(ctx, x - 1, y - 1, 3, 1, A[3]); px(ctx, x, y - 2, 1, 1, A[4]);
      px(ctx, x, y - 1, 1, 1, A[1]);
      break;
    case 'pebble': chip(ctx, x, y, 2, Rk); break;
    case 'stone':  chip(ctx, x, y, 3, Rk); px(ctx, x - 1, y + 1, 1, 1, Rk[1]); break;
    case 'twig':
      for (let k = 0; k < 5; k++) px(ctx, x + k, y + (k >> 1), 1, 1, P.bark[1]);
      px(ctx, x, y, 1, 1, P.bark[3]);
      px(ctx, x + 1, y + 1, 4, 1, occlude(R[0], 0.35));
      break;
    case 'divot':
      // A hollow: dark where the light cannot reach in, lit on the FAR rim.
      px(ctx, x, y, 3, 1, occlude(R[0], 0.42));
      px(ctx, x, y + 1, 3, 1, occlude(R[1], 0.25));
      px(ctx, x - LIGHT_DX, y + 2, 3, 1, R[4]);
      break;
    case 'moss':  clump(ctx, x, y, 2 + (v & 1), F[2], F[3], F[0]); break;
    case 'fungus':
      for (const dx of [0, 3]) {
        px(ctx, x + dx, y + 1, 1, 2, mixHex(G[4], '#e8dcc0', 0.6));
        px(ctx, x + dx - 1, y, 3, 1, A[2]);
        px(ctx, x + dx - 1, y + 1, 3, 1, occlude(A[0], 0.3));
        px(ctx, x + dx - 1, y, 1, 1, A[4]);
      }
      break;
    case 'root':
      for (let k = 0; k < 7; k++) {
        const yy = y + Math.round(Math.sin(k * 0.9) * 1.4);
        px(ctx, x + k - 3, yy, 1, 1, P.bark[1]);
        px(ctx, x + k - 3, yy - 1, 1, 1, P.bark[3]);
      }
      break;
    case 'pool':
      pxEllipse(ctx, x, y, 3, 2, Wt[1]);
      pxEllipse(ctx, x, y, 2, 1.2, Wt[0]);
      px(ctx, x - 1, y - 1, 2, 1, Wt[4]);
      break;
    case 'bubble':
      for (const [dx, dy] of [[0, 0], [3, 2], [-2, 2]]) {
        px(ctx, x + dx, y + dy, 2, 1, Wt[3]);
        px(ctx, x + dx, y + dy + 1, 2, 1, Wt[0]);
      }
      break;
    case 'reedstub':
      for (const dx of [0, 2, 4]) { px(ctx, x + dx, y - 2, 1, 4, F[1]); px(ctx, x + dx, y - 2, 1, 1, F[3]); }
      break;
    case 'bone': {
      const b = mixHex(G[3], '#cfc4b0', 0.55), d = occlude(mixHex(G[1], '#5c5248', 0.4), 0.3);
      px(ctx, x, y, 4, 1, b); px(ctx, x, y + 1, 4, 1, d);
      px(ctx, x - 1, y, 1, 2, b); px(ctx, x + 4, y, 1, 2, b);
      break;
    }
    case 'crack': crack(ctx, s, 0x70, x, y - 3, 7 + (v & 3), (v & 1) === 0, occlude(Rk[0], 0.5), Rk[3]); break;
    case 'rubble':
      chip(ctx, x, y, 2, Rk); chip(ctx, x + 3, y + 2, 1, Rk); chip(ctx, x - 2, y + 3, 2, Rk);
      break;
    case 'grit':
      for (let i = 0; i < 7; i++) {
        const gx = Math.floor(cellRand(s, i, 0, 0x71) * TILE), gy = Math.floor(cellRand(s, i, 1, 0x71) * TILE);
        px(ctx, gx, gy, 1, 1, i & 1 ? Rk[3] : occlude(Rk[0], 0.4));
      }
      break;
    case 'chip':
      // Two flakes, at the surface's own value plus a step. A loose mark two
      // full ramp steps above the ground it lies on reads as a printed glyph,
      // and a field of them reads as text.
      px(ctx, x, y, 2, 1, Rk[3]); px(ctx, x, y + 1, 2, 1, mixHex(Rk[2], Rk[1], 0.5));
      px(ctx, x + 3, y + 2, 2, 1, Rk[2]); px(ctx, x + 3, y + 3, 2, 1, occlude(Rk[1], 0.3));
      break;
    case 'drift':
      for (let k = 0; k < 9; k++) {
        const gx = x + k - 4, gy = y + Math.round(Math.sin(k * 0.7) * 1.2);
        if (gx < 0 || gx >= TILE) continue;
        px(ctx, gx, gy, 1, 1, Sd[4]);
        px(ctx, gx, gy + 1, 1, 1, mixHex(Sd[2], Sd[0], 0.55));
      }
      break;
    case 'dimple':
      px(ctx, x, y, 3, 1, mixHex(G[4], G[2], 0.6)); px(ctx, x, y + 1, 3, 1, mixHex(G[4], G[1], 0.6));
      px(ctx, x - LIGHT_DX, y + 2, 3, 1, G[4]);
      break;
    case 'ember':
      px(ctx, x, y, 1, 1, '#ffd97a'); px(ctx, x + 1, y, 1, 1, '#e8762a');
      px(ctx, x, y + 1, 2, 1, '#a83c10');
      break;
    case 'stain':
      pxEllipse(ctx, x, y, 3.5, 2.2, occlude(Rk[0], 0.45), 0.3);
      pxEllipse(ctx, x, y, 2, 1.2, occlude(Rk[0], 0.6));
      break;
    case 'shard':
      for (let k = 0; k < 4; k++) px(ctx, x - (k >> 1), y - k, Math.max(1, 3 - k), 1, k > 1 ? A[4] : A[2]);
      px(ctx, x + 1, y + 1, 2, 1, occlude(Rk[0], 0.5));
      break;
    case 'glint':
      px(ctx, x, y - 1, 1, 3, A[4]); px(ctx, x - 1, y, 3, 1, A[4]);
      px(ctx, x, y, 1, 1, '#ffffff');
      break;
    default: chip(ctx, x, y, 2, Rk);
  }
  return canvas;
}

/* ---------- water ---------- */

/* Depth 0 is the shallow shelf by the shore, 3 is open water.
 *
 * The wave field uses integer frequencies over the sheet and an integer period
 * in `frame`, so it tiles seamlessly in x and y AND loops in time. A sine in raw
 * pixel coordinates, which is what a naive water tile does, produces a visible
 * seam at every tile boundary. */
function waterSheet(P, st, seed, depth, frame) {
  const S = TILE * 4;
  const { canvas, ctx } = make(S, S);
  const Wt = P.water;
  const t = frame / WATER_FRAMES;
  const mode = st.water || 'clear';
  // Depth is a shelf, the way 16-bit water always was, but the shelves sit close
  // together so the lake reads as one body of water rather than four rings.
  const body = [Wt[3], mixHex(Wt[2], Wt[3], 0.35), Wt[2], Wt[1]][depth];
  // The bright value is a crest, not a body tone: pushing Wt[4] across a whole
  // shallow tile turns every pond into a bank of cloud.
  const hi = depth >= 2 ? Wt[3] : mixHex(Wt[2], Wt[3], 0.7);
  const lo = depth >= 2 ? Wt[1] : mixHex(Wt[1], Wt[2], 0.5);
  px(ctx, 0, 0, S, S, body);

  if (mode === 'ice') {
    // Frozen: plates, not waves. Ice is PALE — a frozen lake is brighter than
    // the water it was and only a little darker than the snow around it. A dark
    // blue sheet here reads as a hole punched in the map.
    const pane = mixHex(Wt[3], '#e8f4ff', depth >= 2 ? 0.34 : 0.56);
    const seam = mixHex(Wt[1], '#8fb4d8', 0.30);
    px(ctx, 0, 0, S, S, pane);
    // Plates, from a wrapped nearest-seed partition. Quantising the value on an
    // eight-pixel block grid — the obvious way to get plates — lays a literal
    // chessboard across the lake, because the blocks line up with the tiles the
    // sheet is cut into.
    const NP = 9;
    const sx = [], sy = [], sv = [];
    for (let i = 0; i < NP; i++) {
      sx.push(cellRand(seed, i, 0, 0x87) * S);
      sy.push(cellRand(seed, i, 1, 0x87) * S);
      sv.push(cellRand(seed, i, 2, 0x87));
    }
    for (let y = 0; y < S; y++) {
      for (let x = 0; x < S; x++) {
        let best = 1e9, second = 1e9, bi = 0;
        for (let i = 0; i < NP; i++) {
          let dx = Math.abs(x - sx[i]); if (dx > S / 2) dx = S - dx;
          let dy = Math.abs(y - sy[i]); if (dy > S / 2) dy = S - dy;
          const d = dx * dx + dy * dy;
          if (d < best) { second = best; best = d; bi = i; }
          else if (d < second) second = d;
        }
        const edge = Math.sqrt(second) - Math.sqrt(best) < 1.4;
        px(ctx, x, y, 1, 1, edge ? seam
          : mixHex(pane, sv[bi] > 0.5 ? '#ffffff' : seam, 0.10 + sv[bi] * 0.16));
        if (cellRand(seed, x, y, 0x86) > 0.982) px(ctx, x, y, 1, 1, '#ffffff');
      }
    }
    // Four fractures, each with a lit lip on its upper-left side and a shimmer
    // that travels the loop — a wholly static tile in a moving world reads as a
    // bug rather than as ice.
    for (let i = 0; i < 4; i++) {
      let fx = Math.floor(cellRand(seed, i, 0, 0x81) * S);
      let fy = Math.floor(cellRand(seed, i, 1, 0x81) * S);
      const vert = cellRand(seed, i, 2, 0x81) > 0.5;
      const litFrame = ((i + frame) % WATER_FRAMES) < 2;
      for (let k = 0; k < 26; k++) {
        px(ctx, fx % S, fy % S, 1, 1, seam);
        px(ctx, (fx + LIGHT_DX + S) % S, (fy + LIGHT_DY + S) % S, 1, 1,
           litFrame ? '#ffffff' : mixHex(pane, '#ffffff', 0.5));
        const j = cellRand(seed, i * 31 + k, 3, 0x81);
        if (vert) { fy++; if (j > 0.78) fx++; else if (j < 0.22) fx += S - 1; }
        else { fx++; if (j > 0.78) fy++; else if (j < 0.22) fy += S - 1; }
        fx = (fx + S) % S; fy = (fy + S) % S;
      }
    }
    return canvas;
  }

  const amp = mode === 'tar' ? 0.7 : 1;
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const u = x / S, v = y / S;
      const w = (Math.sin(2 * Math.PI * (2 * u + 3 * v - t)) * 0.50
               + Math.sin(2 * Math.PI * (5 * u - 2 * v + t * 2)) * 0.30
               + Math.sin(2 * Math.PI * (3 * u + 7 * v + t)) * 0.20) * amp;
      if (w > 0.62) px(ctx, x, y, 1, 1, hi);
      else if (w < -0.70) px(ctx, x, y, 1, 1, lo);
    }
  }

  // The one hot rim light, lying on the water. A slow diagonal band of specular
  // that crosses the sheet once per loop — this is the single clearest signal
  // that a surface is wet rather than merely blue.
  if (mode !== 'tar' || depth <= 1) {
    const glintC = mode === 'tar' ? mixHex(Wt[4], P.accent[3], 0.5) : Wt[4];
    for (let y = 0; y < S; y++) {
      const band = ((y * 0.5 + t * S) % S);
      for (let k = 0; k < 2; k++) {
        const x = Math.floor(band + k * 11) % S;
        const u = x / S, v = y / S;
        const w = Math.sin(2 * Math.PI * (2 * u + 3 * v - t));
        // Tight, broken, and only on the crest of a wave: a specular is a
        // glance off a moving surface, not weather.
        if (w > 0.55 && cellRand(seed, x, y, 0x82) > 0.62) px(ctx, x, y, 1, 1, glintC);
      }
    }
  }

  if (mode === 'murk') {
    // Weed, hanging just under the surface: the reason a swamp pool is not a
    // lake that happens to be green.
    for (let i = 0; i < 14; i++) {
      const wx = Math.floor(cellRand(seed, i, depth, 0x83) * S);
      const wy = Math.floor(cellRand(seed, i, depth + 9, 0x83) * S);
      const len = 4 + Math.floor(cellRand(seed, i, 2, 0x83) * 7);
      for (let k = 0; k < len; k++) {
        const yy = (wy + k) % S;
        const xx = (wx + Math.round(Math.sin((k + t * 6) * 0.6) * 1.6) + S) % S;
        px(ctx, xx, yy, 1, 1, mixHex(P.foliage[1], Wt[1], 0.45));
      }
    }
  }
  if (mode === 'blood') {
    for (let i = 0; i < 8; i++) {
      const cx = Math.floor(cellRand(seed, i, depth, 0x84) * S);
      const cy = Math.floor(cellRand(seed, i, depth + 5, 0x84) * S);
      const r = 2 + ((i + frame) % 3);
      pxEllipse(ctx, cx, cy, r + 1, r, mixHex(Wt[2], '#ff8a94', 0.25), 0.5);
    }
  }

  // Caustics only on the shelf: light reaching the bottom is what tells the eye
  // this edge is shallow and that one is not.
  if (depth <= 1 && mode !== 'tar') {
    for (let i = 0; i < (depth === 0 ? 26 : 14); i++) {
      const cx = Math.floor(cellRand(seed, i, depth, 21) * S);
      const cy = Math.floor(cellRand(seed, i, depth, 22) * S);
      px(ctx, (cx + Math.floor(t * S)) % S, cy, 2, 1, Wt[4]);
    }
  }
  return canvas;
}

function lavaSheet(P, seed, frame) {
  const S = TILE * 4;
  const { canvas, ctx } = make(S, S);
  const crust = '#3a0e06', warm = '#8f2a12', hot = '#d2451a', bright = '#ff8a2a', white = '#ffd97a';
  const t = frame / WATER_FRAMES;
  px(ctx, 0, 0, S, S, hot);
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const u = x / S, v = y / S;
      // Two drifting fields plus a per-pixel break, because a clean sum of two
      // sines is a tartan and lava is a crust tearing over something brighter.
      const w = Math.sin(2 * Math.PI * (2 * u - 3 * v + t)) * 0.40
              + Math.sin(2 * Math.PI * (5 * u + 4 * v - t * 2)) * 0.18
              + (cellRand(seed, x, y, 45) - 0.5) * 0.95;
      if (w > 0.74) px(ctx, x, y, 1, 1, white);
      else if (w > 0.40) px(ctx, x, y, 1, 1, bright);
      else if (w < -0.58) px(ctx, x, y, 1, 1, crust);
      else if (w < -0.22) px(ctx, x, y, 1, 1, warm);
    }
  }
  // Cooled plates riding the current, each with a hot seam on its trailing edge.
  // Uniform molten soup has no scale; plates give it one.
  for (let i = 0; i < 7; i++) {
    const cx = Math.floor((cellRand(seed, i, 0, 0x90) * S + t * S * 0.35) % S);
    const cy = Math.floor((cellRand(seed, i, 1, 0x90) * S + t * S * 0.18) % S);
    const r = 4 + Math.floor(cellRand(seed, i, 2, 0x90) * 6);
    pxEllipse(ctx, cx, cy, r + 2, r, crust);
    pxEllipse(ctx, cx, cy, r, r - 1.2, mixHex(crust, '#1a0a06', 0.5));
    pxEllipse(ctx, cx - LIGHT_DX, cy - LIGHT_DY, r + 2, r, bright, 0.62);
  }
  return canvas;
}

/* Bridge planks, drawn over water where a road crosses it. */
function bridgeTile(P, seed, vertical) {
  const { canvas, ctx } = make(TILE, TILE);
  const D = P.dirt;
  const Pl = ramp(mixHex(D[2], '#6a4a2a', 0.5));
  const dark = occlude(Pl[0], 0.45);
  if (vertical) {
    px(ctx, 1, 0, TILE - 2, TILE, Pl[2]);
    for (let y = 0; y < TILE; y += 4) { px(ctx, 1, y, TILE - 2, 1, Pl[1]); px(ctx, 1, y + 1, TILE - 2, 1, Pl[3]); }
    px(ctx, 1, 0, 1, TILE, Pl[3]);
    px(ctx, TILE - 2, 0, 1, TILE, Pl[0]);
    // The rails, and the dark the deck throws on the water under its right edge.
    px(ctx, 0, 0, 1, TILE, dark);
    px(ctx, TILE - 1, 0, 1, TILE, dark);
  } else {
    px(ctx, 0, 1, TILE, TILE - 2, Pl[2]);
    for (let x = 0; x < TILE; x += 4) { px(ctx, x, 1, 1, TILE - 2, Pl[1]); px(ctx, x + 1, 1, 1, TILE - 2, Pl[3]); }
    px(ctx, 0, 1, TILE, 1, Pl[3]);
    px(ctx, 0, TILE - 2, TILE, 1, Pl[0]);
    px(ctx, 0, 0, TILE, 1, dark);
    px(ctx, 0, TILE - 1, TILE, 1, dark);
  }
  return canvas;
}

/* ---------- cliffs ---------- */
/* Three roles. TOP is plateau you look down at. FACE is wall you look at. CAP is
 * a one-tile-high ridge: a strip of plateau above a short face. Elevation reads
 * because the face has vertical striations and the top does not, because the two
 * are two full ramp steps apart in value, and because the wall throws a shadow
 * across the ground in front of it in the same direction as everything else. */
const CLIFF_TOP = 1, CLIFF_FACE = 2, CLIFF_CAP = 3;

/* Rock grain, shared by the plateau, the wall and the stone floor so a region's
 * geology is one material rather than three. */
function rockGrain(ctx, Rk, st, seed, variant, x0, y0, w, h) {
  const mortar = occlude(Rk[0], 0.42);
  if (st.rock === 'brick') {
    for (let cy = y0; cy < y0 + h; cy += 5) {
      const shift = (((cy - y0) / 5) & 1) ? 4 : 0;
      px(ctx, x0, cy, w, 1, Rk[4]);
      px(ctx, x0, Math.min(y0 + h - 1, cy + 4), w, 1, mortar);
      for (let x = x0 + shift - 8; x < x0 + w; x += 8) {
        if (x >= x0) px(ctx, x, cy, 1, Math.min(5, y0 + h - cy), mortar);
      }
    }
  } else if (st.rock === 'basalt') {
    for (let x = x0; x < x0 + w; x += 3) {
      const cw = 2 + (cellRand(seed, x, variant, 0xa1) > 0.6 ? 1 : 0);
      px(ctx, x, y0, 1, h, Rk[4]);
      px(ctx, Math.min(x0 + w - 1, x + cw), y0, 1, h, mortar);
      const brk = y0 + Math.floor(cellRand(seed, x, variant, 0xa2) * h);
      px(ctx, x, brk, cw + 1, 1, mortar);
    }
  } else if (st.rock === 'ice') {
    // One fracture, with a lip only a little brighter than the rock. Three of
    // them at full white per tile is a row of tally marks.
    for (let i = 0, n = 1 + (variant & 1); i < n; i++) {
      crack(ctx, seed + variant, 0xa3 + i,
            x0 + Math.floor(cellRand(seed, i, variant, 0xa4) * w), y0, h, true,
            mixHex(Rk[0], '#1e3450', 0.45), mixHex(Rk[3], '#e0f0ff', 0.45));
    }
  } else if (st.rock === 'ore') {
    const A = ramp('#e8c37d');
    crack(ctx, seed + variant * 3, 0xa5,
          x0 + Math.floor(cellRand(seed, variant, 1, 0xa6) * w), y0 + 1, h - 2,
          variant % 2 === 0, A[2], A[4]);
  } else {
    // Strata: horizontal beds, each lit along its top and occluded at its base.
    // Broken per pixel and pitched a step, because a full-width bright line
    // every third row is a set of venetian blinds.
    const lip = mixHex(Rk[2], Rk[4], 0.55);
    for (let cy = y0 + 2; cy < y0 + h; cy += 3 + (cellRand(seed, cy, variant, 0xa7) > 0.6 ? 1 : 0)) {
      for (let x = x0; x < x0 + w; x++) {
        const yy = cy + Math.round(wave(seed + variant, cy, x, 4, 4) * 1.6) - 1;
        if (yy < y0 || yy + 1 >= y0 + h) continue;
        if (cellRand(seed, x, cy + variant, 0xa8) < 0.22) continue;
        px(ctx, x, yy, 1, 1, lip);
        px(ctx, x, yy + 1, 1, 1, mortar);
      }
    }
  }
}

function cliffTopTile(P, st, seed, variant, openMask) {
  const { canvas, ctx } = make(TILE, TILE);
  const Rk = P.rock;
  // The top faces the sky, so it is the brightest rock in the region. All of the
  // elevation read comes from this being well clear of the face's value.
  px(ctx, 0, 0, TILE, TILE, Rk[3]);
  mottle(ctx, seed + variant * 7, 31, Rk[4], Rk[2], 0.90, 0.14, null, 0, Rk[3], 0.6);

  // Two broad slabs, close in value to the plateau, each lit along its top and
  // softly occluded at its foot. Three small high-contrast ones with a hard dark
  // return on two sides read as scattered glyphs rather than as rock, which is
  // exactly what the previous tile did.
  const rand = rng(seed + variant * 401 + 1);
  for (let i = 0; i < 2; i++) {
    const cx = Math.floor(rand() * 18) - 1, cy = Math.floor(rand() * 18) - 1;
    const r = 3 + Math.floor(rand() * 3);
    const tint = mixHex(Rk[3], rand() < 0.5 ? Rk[4] : Rk[2], 0.30);
    for (let y = cy - r - 1; y <= cy + r + 1; y++) {
      for (let x = cx - r - 1; x <= cx + r + 1; x++) {
        if (x < 0 || y < 0 || x >= TILE || y >= TILE) continue;
        const wob = r + (wave(seed + variant, i * 37, x * 5 + y * 3, 8, 2) - 0.5) * 2.4;
        const d = Math.hypot(x - cx, y - cy);
        if (d > wob) continue;
        const lift = (x - cx) * LIGHT_DX + (y - cy) * LIGHT_DY;
        const up = lift > wob * 0.62, down = lift < -wob * 0.66;
        px(ctx, x, y, 1, 1,
           up ? mixHex(Rk[3], Rk[4], 0.6) : down ? occlude(Rk[3], 0.18) : tint);
      }
    }
  }
  if (st.rock === 'ore') rockGrain(ctx, Rk, st, seed, variant, 0, 0, TILE, TILE);
  else if (st.rock === 'ice' && variant % 3 === 0) {
    crack(ctx, seed + variant, 0xa9, Math.floor(cellRand(seed, variant, 2, 0xaa) * TILE), 0,
          TILE, true, mixHex(Rk[1], '#1e3450', 0.4), mixHex(Rk[3], '#d8ecff', 0.4));
  }

  // The drop edge, wobbled per pixel. A ruled two-pixel highlight along every
  // open side is a picture frame; a broken one is a cliff you could fall off.
  const rim = (dir) => {
    const p = [0, 0];
    for (let i = 0; i < TILE; i++) {
      const d = 1 + Math.round(wave(seed, dir * 97 + variant * 41, i, 4, 4) * 1.9);
      for (let k = 0; k < d; k++) {
        edgePx(dir, i, k, p);
        px(ctx, p[0], p[1], 1, 1, k === d - 1 && d > 1 ? Rk[3] : Rk[4]);
      }
    }
  };
  // Light from the upper left: the north and west lips catch it, the east lip
  // turns away from it, and the south lip is the edge you are looking over.
  if (openMask & N) rim(0);
  if (openMask & W) rim(3);
  if (openMask & E) {
    const p = [0, 0];
    for (let i = 0; i < TILE; i++) {
      const d = 1 + (wave(seed, 211 + variant, i, 4, 4) > 0.6 ? 1 : 0);
      for (let k = 0; k < d; k++) { edgePx(1, i, k, p); px(ctx, p[0], p[1], 1, 1, Rk[1]); }
    }
  }
  // No occlusion band on a closed side. A plateau is FLAT: darkening the north
  // and west edge of every interior tile to suggest height lays a dark 16-pixel
  // lattice over the whole mass, which is the loudest tell a tileset has. The
  // elevation is carried by the face below and the shadow it throws, which are
  // the two places a height difference actually exists.
  return canvas;
}

function cliffFaceTile(P, st, seed, variant, sideMask, capHeight) {
  const { canvas, ctx } = make(TILE, TILE);
  const Rk = P.rock;
  const top = capHeight | 0;
  if (top > 0) {
    // A strip of plateau catching the sky, then the lip.
    px(ctx, 0, 0, TILE, top, Rk[3]);
    for (let x = 0; x < TILE; x++) {
      if (cellRand(seed, x, variant, 41) > 0.78) px(ctx, x, 0, 1, 1, Rk[4]);
    }
    px(ctx, 0, 0, TILE, 1, Rk[4]);
  }
  const faceTop = top;
  const fh = TILE - faceTop;

  /* FIVE values for the whole wall, held in an array and addressed by index.
   *
   * The obvious way to shade a face — blend the column's tone continuously
   * toward the dark as x increases — produces a different colour in every one of
   * the sixteen columns, and that is thirty-five colours in a tile with a
   * fifteen-colour budget. It also looks worse: a stepped wall reads as rock,
   * a smoothly graded one reads as an airbrush. Quantising is the rule and the
   * rule is right. */
  const face = [
    occlude(Rk[0], 0.6),                 // 0 the deep, at the foot and hard right
    Rk[0],                               // 1
    mixHex(Rk[0], Rk[1], 0.5),           // 2
    Rk[1],                               // 3
    mixHex(Rk[1], Rk[2], 0.55),          // 4 the lit columns, hard left
  ];
  px(ctx, 0, faceTop, TILE, fh, face[2]);

  // Vertical striation: columns of alternating value with jagged breaks. The
  // grain has to run down the wall or the face reads as more floor. On top of
  // that a stepped left-to-right falloff, because the wall is lit from the left
  // and a wall of uniform value is a painted flat.
  for (let x = 0; x < TILE; x++) {
    const c = cellRand(seed + variant * 29, x, 0, 43);
    const grain = c > 0.76 ? 1 : c < 0.34 ? -1 : 0;
    const lean = x < 3 ? 1 : x < 7 ? 0 : x < 11 ? -1 : -2;
    px(ctx, x, faceTop, 1, fh, face[Math.max(0, Math.min(4, 3 + grain + lean))]);
    const brk = faceTop + 3 + Math.floor(cellRand(seed, x, 1, 44) * (fh - 4));
    px(ctx, x, brk, 1, 1 + (c > 0.7 ? 1 : 0), face[0]);
  }
  rockGrain(ctx, Rk, st, seed, variant, 0, faceTop + 1, TILE, fh - 3);

  // The lip catches the same light the plateau does; below it the wall drops
  // two full ramp steps. That gap is the elevation.
  px(ctx, 0, faceTop, TILE, 1, top > 0 ? face[0] : Rk[2]);
  px(ctx, 0, faceTop + 1, TILE, 1, face[1]);

  // Corner returns: an unbroken wall is a flat, so the open sides get a bevel —
  // lit where it turns toward the light, occluded where it turns away.
  if (sideMask & 1) px(ctx, 0, faceTop, 1, fh, face[4]);
  if (sideMask & 2) px(ctx, TILE - 1, faceTop, 1, fh, face[0]);

  // Where the wall meets the ground. Every solid in this game ends in this band.
  bottomBand(ctx, 0, TILE - 2, TILE, face[1]);
  bottomBand(ctx, 0, TILE - 1, TILE, face[0]);
  return canvas;
}

/* The dark a cliff throws onto the ground below it.
 *
 * `mask` says which of the eight neighbours is the wall doing the throwing, so
 * the shadow reaches down AND to the right — one light, one direction — and it
 * turns the corner at the end of a wall instead of stopping dead. */
function cliffShadowTile(mask) {
  const { canvas, ctx } = make(TILE, TILE);
  inkBegin(TILE, TILE);
  const band = (dir, depth, alphas) => {
    const p = [0, 0];
    for (let i = 0; i < TILE; i++) {
      for (let k = 0; k < depth; k++) {
        const a = alphas[k];
        if (a == null) continue;
        edgePx(dir, i, k, p);
        inkMarkA(p[0], p[1], a);
      }
    }
  };
  // A wall to the north throws its full height across this tile; a wall to the
  // west throws across it too, because the light is up AND left. A wall to the
  // south or east is behind the light and only occludes where it touches.
  if (mask & N) band(0, 6, [0.46, 0.34, 0.24, 0.16, 0.10, 0.06]);
  if (mask & W) band(3, 4, [0.30, 0.20, 0.12, 0.07]);
  if (mask & E) band(1, 2, [0.20, 0.10]);
  if (mask & S) band(2, 2, [0.18, 0.09]);
  // The inside corner, where two walls meet, is the darkest place on the map.
  if ((mask & N) && (mask & W)) {
    for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) {
      if (x + y > 5) continue;
      inkMarkA(x, y, 0.22 - (x + y) * 0.03);
    }
  }
  if ((mask & NW) && !(mask & N) && !(mask & W)) {
    for (let y = 0; y < 3; y++) for (let x = 0; x < 3; x++) {
      if (x + y > 2) continue;
      inkMarkA(x, y, 0.26 - (x + y) * 0.07);
    }
  }
  inkFlush(ctx);
  return canvas;
}

/* ---------- ambient occlusion from standing objects ---------- */

/* Trees, houses and shrines sit ON the ground layer, so the ground has to know
 * they are there. This is the contact shading and the cast shadow for every one
 * of them at once: one cached 16x16 per neighbourhood, one drawImage per tile
 * that has a neighbour, and no per-frame cost of any kind. */
function aoTile(mask) {
  const { canvas, ctx } = make(TILE, TILE);
  inkBegin(TILE, TILE);
  const band = (dir, alphas) => {
    const p = [0, 0];
    for (let i = 0; i < TILE; i++) {
      for (let k = 0; k < alphas.length; k++) {
        edgePx(dir, i, k, p);
        inkMarkA(p[0], p[1], alphas[k]);
      }
    }
  };
  // A tree to the north-west throws its shadow across this tile; a tree to the
  // south-east is behind the light and only touches it. Banding all four sides
  // equally boxes every cell next to a wood in grey, which on a pale ground is
  // the most visible artefact this file can produce.
  if (mask & N) band(0, [0.22, 0.14, 0.08, 0.04]);
  if (mask & W) band(3, [0.17, 0.10, 0.05]);
  if (mask & E) band(1, [0.07]);
  if (mask & S) band(2, [0.06]);
  const nub = (cx, cy, sx, sy, a) => {
    for (let y = 0; y < 3; y++) for (let x = 0; x < 3; x++) {
      if (x + y > 2) continue;
      inkMarkA(cx + x * sx, cy + y * sy, a - (x + y) * 0.05);
    }
  };
  if ((mask & NW) && !(mask & N) && !(mask & W)) nub(0, 0, 1, 1, 0.18);
  if ((mask & NE) && !(mask & N) && !(mask & E)) nub(TILE - 1, 0, -1, 1, 0.09);
  inkFlush(ctx);
  return canvas;
}

/* ---------- edge fringes: the interlock ---------- */

/* How deep the overlay reaches into this tile, per pixel along one side.
 *
 * Two octaves of periodic hashed noise plus the occasional tooth or notch. The
 * period is what matters: the profile leaves the right-hand end of the tile at
 * the height it entered the left-hand end, so a run of shore tiles reads as one
 * eroded bank rather than as sixteen separately-scalloped squares — which is
 * the "checkerboard with rounded corners" this whole section exists to kill. */
function fringeProfile(seed, mask, dir, variant, band) {
  const out = new Int8Array(TILE);
  const salt = dir * 131 + mask * 7 + variant * 977;
  for (let i = 0; i < TILE; i++) {
    const swell = wave(seed, salt, i, 4, 4) - 0.5;          // 4px undulation
    const grain = wave(seed, salt + 613, i, 8, 2) - 0.5;    // 2px roughness
    let d = band + Math.round(swell * 3.4 + grain * 2.0);
    const spike = cellRand(seed, i, salt, 0x5f);
    if (spike > 0.935) d += 2;            // a tooth, reaching in
    else if (spike < 0.055) d -= 2;       // a notch, pulling back
    out[i] = Math.max(1, Math.min(8, d));
  }
  return out;
}

function fringeTile(P, cls, mask, variant, seed, host) {
  const { canvas, ctx } = make(TILE, TILE);
  const R = cls === 'path' ? P.road
          : cls === 'stone' ? P.rock
          : cls === 'sand' ? P.sand
          : cls === 'shore' ? P.wet
          : P.ground;
  const band = cls === 'stone' ? 4 : cls === 'grass' ? 4 : 3;
  // Rock does not lap onto grass, it falls onto it: the stone fringe scatters
  // into gravel instead of laying a band.
  const scatter = cls === 'stone' && host !== 'lava';
  const wet = cls === 'shore';

  const lvl = new Uint8Array(TILE * TILE);   // 1 = leading edge, grows inward
  const src = new Uint8Array(TILE * TILE);   // which side laid this pixel, +1
  const prof = [null, null, null, null];
  const p = [0, 0];

  const dirs = [[N, 0], [E, 1], [S, 2], [W, 3]];
  for (const [bit, dir] of dirs) {
    if (!(mask & bit)) continue;
    const d = prof[dir] = fringeProfile(seed, mask, dir, variant, band);
    for (let i = 0; i < TILE; i++) {
      for (let k = 0; k < d[i]; k++) {
        edgePx(dir, i, k, p);
        const idx = p[1] * TILE + p[0];
        const v = d[i] - k;
        if (v > lvl[idx]) { lvl[idx] = v; src[idx] = dir + 1; }
      }
    }
  }

  /* Corners. This is where an autotiler is won or lost.
   *
   *  - both cardinals AND the diagonal: the overlay owns the corner, so round it
   *    convex — a square corner on an organic mass is a tell.
   *  - both cardinals, NO diagonal: the diagonal cell is HOST, so the corner must
   *    be cut back CONCAVE. Leaving it filled is precisely what produces a shore
   *    made of rounded squares: every cell bulges, none of them bite.
   *  - neither cardinal, diagonal only: a tongue, not a band. */
  const setPx = (x, y, v, dir) => {
    if (x < 0 || y < 0 || x >= TILE || y >= TILE) return;
    const idx = y * TILE + x;
    if (v > lvl[idx]) { lvl[idx] = v; src[idx] = dir + 1; }
  };
  // dirA is always the horizontal side (N or S), whose profile is indexed by x;
  // dirB is always the vertical one (E or W), indexed by y. Reading them the
  // other way round takes the depth from the FAR end of each band and the
  // fillet no longer matches the two bands it is supposed to join.
  const corner = (diagBit, bitA, dirA, bitB, dirB, cx, cy) => {
    const both = (mask & bitA) && (mask & bitB);
    const diag = mask & diagBit;
    if (both && diag) {
      const r = Math.max(prof[dirA] ? prof[dirA][cx] : 0,
                         prof[dirB] ? prof[dirB][cy] : 0);
      for (let y = 0; y < TILE; y++) {
        for (let x = 0; x < TILE; x++) {
          const dist = Math.hypot(x - cx, y - cy);
          if (dist > r) continue;
          setPx(x, y, Math.max(1, Math.round(r - dist) + 1), dirA);
        }
      }
    } else if (both && !diag) {
      const rc = 2.4;
      for (let y = 0; y < TILE; y++) {
        for (let x = 0; x < TILE; x++) {
          const dist = Math.hypot(x - cx, y - cy);
          if (dist > rc) continue;
          lvl[y * TILE + x] = 0;
        }
      }
      // Re-lip the bite, so the cut edge is an edge and not a hole.
      for (let y = 0; y < TILE; y++) {
        for (let x = 0; x < TILE; x++) {
          const dist = Math.hypot(x - cx, y - cy);
          if (dist <= rc || dist > rc + 1.3) continue;
          const idx = y * TILE + x;
          // A bite out of a corner is a pocket, and a pocket is in shade
          // whichever way it faces. dirA is N at the two top corners and S at
          // the two bottom ones, which is exactly the right answer for both.
          if (lvl[idx]) { lvl[idx] = 1; src[idx] = dirA + 1; }
        }
      }
    } else if (!both && diag) {
      for (let y = 0; y < TILE; y++) {
        for (let x = 0; x < TILE; x++) {
          const dist = Math.hypot(x - cx, y - cy);
          if (dist > 2.3) continue;
          setPx(x, y, dist > 1.3 ? 1 : 2, dirA);
        }
      }
    }
  };
  corner(NE, N, 0, E, 1, TILE - 1, 0);
  corner(SE, S, 2, E, 1, TILE - 1, TILE - 1);
  corner(SW, S, 2, W, 3, 0, TILE - 1);
  corner(NW, N, 0, W, 3, 0, 0);

  /* Paint. Three values across the band — body, a shoulder, and a leading edge
   * that is LIT where it faces the light and SHADOWED where it faces away. That
   * one rule is what turns a coloured border into a bank with a height. */
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const idx = y * TILE + x;
      const v = lvl[idx];
      if (!v) continue;
      if (scatter && cellRand(seed, x, y * 13 + variant, 57) > 0.42 + v * 0.07) continue;
      const lit = sideLit((src[idx] || 1) - 1);
      let c;
      if (v >= 3) {
        const n = cellRand(seed + variant * 11, x, y, 0x5a);
        c = n > 0.86 ? R[3] : n < 0.16 ? R[1] : R[2];
      } else if (v === 2) c = lit ? R[3] : R[1];
      else c = scatter ? (lit ? R[3] : R[1]) : (lit ? R[4] : R[0]);
      px(ctx, x, y, 1, 1, c);
    }
  }

  /* The eroded transition and the occlusion beyond it. The overlay stands a
   * little proud of the host, so where it faces away from the light it throws
   * shade onto the ground it overhangs — down and to the right, like every other
   * shadow in this file. */
  for (const [bit, dir] of dirs) {
    if (!(mask & bit)) continue;
    const d = prof[dir];
    const lit = sideLit(dir);
    for (let i = 0; i < TILE; i++) {
      edgePx(dir, i, d[i], p);
      if (p[0] >= 0 && p[1] >= 0 && p[0] < TILE && p[1] < TILE
          && !lvl[p[1] * TILE + p[0]] && bayer(i, d[i] + dir * 2) < 0.45) {
        px(ctx, p[0], p[1], 1, 1, lit ? R[2] : R[1]);
      }
      if (lit) continue;
      for (let k = 0; k < 3; k++) {
        edgePx(dir, i, d[i] + k, p);
        if (p[0] < 0 || p[1] < 0 || p[0] >= TILE || p[1] >= TILE) continue;
        // Only onto the HOST. Laying the shadow over the bank's own pixels
        // blends three alpha levels into five body tones and invents fifteen
        // colours that are not in any ramp — the overhang is what casts, and it
        // is not standing in its own shade.
        if (lvl[p[1] * TILE + p[0]]) continue;
        const a = [0.30, 0.17, 0.08][k];
        if (a < 0.12 && bayer(p[0], p[1]) > 0.5) continue;
        px(ctx, p[0], p[1], 1, 1, `rgba(7,6,12,${a})`);
      }
    }
  }

  /* Wet sand keeps a skim of water on it, and a skim of water has a specular.
   * Two pixels of it along the tide line is the whole difference between a
   * beach and a brown stripe. */
  if (wet) {
    for (const [bit, dir] of dirs) {
      if (!(mask & bit)) continue;
      for (let i = 0; i < TILE; i += 2) {
        if (cellRand(seed, i, dir * 7 + variant, 0x5c) < 0.45) continue;
        edgePx(dir, i, 0, p);
        px(ctx, p[0], p[1], 1, 1, P.water[4]);
      }
    }
  }
  return canvas;
}

/* The step between two water depths, dithered out across four pixels. Without
 * it the BFS that assigns depth is plainly visible as a rectangle in the middle
 * of the lake. */
function shelfTile(P, mask, variant, depth, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const Wt = P.water;
  const shallower = [Wt[3], mixHex(Wt[2], Wt[3], 0.35), Wt[2], Wt[1]][Math.max(0, depth - 1)];
  const cover = [0.85, 0.55, 0.30, 0.12];
  const p = [0, 0];
  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    for (let i = 0; i < TILE; i++) {
      // The lip of the shelf wanders, because a lake bed is not a swimming pool.
      const lean = Math.round((wave(seed, dir * 53 + variant * 17, i, 4, 4) - 0.5) * 2);
      for (let k = 0; k < 4; k++) {
        const c = cover[Math.max(0, Math.min(3, k - lean))];
        // Hashed, not ordered: a Bayer gradient here reads as a decorative
        // ric-rac border rather than as the bottom falling away.
        if (cellRand(seed, i, k * 9 + dir * 3 + variant * 51, 63) > c) continue;
        edgePx(dir, i, k, p);
        px(ctx, p[0], p[1], 1, 1, shallower);
      }
    }
  };
  side(N, 0); side(E, 1); side(S, 2); side(W, 3);
  return canvas;
}

/* Foam, on the water side of a shoreline. Four frames: the crest advances, the
 * spray behind it thins and re-forms. Not a sine wave — a wave breaks. */
function foamTile(P, mask, variant, frame, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const Wt = P.water;
  const crest = Wt[4], spray = Wt[3], shade = occlude(Wt[0], 0.35);
  const phase = frame / FOAM_FRAMES;
  const p = [0, 0];
  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    for (let i = 0; i < TILE; i++) {
      // Where the crest sits this frame, along the length of the edge. The
      // hashed term keeps two neighbouring shore tiles from breaking in unison.
      const swell = Math.sin(2 * Math.PI * (i / TILE + phase
                    + wave(seed, dir * 91 + variant * 13, i, 4, 4) * 0.4)) * 0.5 + 0.5;
      const reach = 1 + Math.round(swell * 2);
      // The water directly under the bank is in the bank's shadow.
      if (!sideLit(dir)) { edgePx(dir, i, 0, p); px(ctx, p[0], p[1], 1, 1, shade); }
      for (let k = 0; k < reach; k++) {
        const jitter = cellRand(seed, i, k * 7 + dir * 13 + variant * 101 + frame * 31, 61);
        // A crest that runs the whole edge is a white outline. Breaking it in
        // the troughs is what makes it read as water moving against land.
        if (k === 0 && swell < 0.34) continue;
        if (k === reach - 1 && jitter > 0.5) continue;
        edgePx(dir, i, k, p);
        px(ctx, p[0], p[1], 1, 1, k === 0 ? crest : spray);
      }
      // Spray thrown clear of the crest, one pixel, sometimes.
      if (swell > 0.8 && cellRand(seed, i, frame + variant * 17, 62) > 0.62) {
        edgePx(dir, i, reach + 1, p);
        if (p[0] >= 0 && p[1] >= 0 && p[0] < TILE && p[1] < TILE) px(ctx, p[0], p[1], 1, 1, spray);
      }
    }
  };
  side(N, 0); side(E, 1); side(S, 2); side(W, 3);
  return canvas;
}

/* The same shape, in heat: lava glows where it meets rock, and the rock above
 * it takes the light back. */
function emberTile(mask, variant, frame, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const phase = frame / FOAM_FRAMES;
  const p = [0, 0];
  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    for (let i = 0; i < TILE; i++) {
      const swell = Math.sin(2 * Math.PI * (i / TILE * 2 - phase
                    + wave(seed, dir * 71 + variant * 17, i, 4, 4) * 0.5)) * 0.5 + 0.5;
      const reach = 1 + Math.round(swell * 2.4);
      for (let k = 0; k < reach; k++) {
        // Broken hard at the contact and cooling inward. An unbroken bright line
        // all the way round a lava pool is neon piping, not molten rock.
        const j = cellRand(seed, i, k * 5 + dir * 11 + variant * 31 + frame * 13, 71);
        if (k === 0 && (swell < 0.42 || j > 0.72)) continue;
        if (k > 0 && j > 0.58 - k * 0.12) continue;
        edgePx(dir, i, k, p);
        px(ctx, p[0], p[1], 1, 1, k === 0 ? '#ffd97a' : k === 1 ? '#ff8a2a' : '#a83c10');
      }
      // A crust of cooled skin riding the contact, so the edge is not neon piping.
      if (cellRand(seed, i, dir * 3 + variant + frame * 7, 72) > 0.72) {
        edgePx(dir, i, reach, p);
        if (p[0] >= 0 && p[1] >= 0 && p[0] < TILE && p[1] < TILE) px(ctx, p[0], p[1], 1, 1, '#6a1e08');
      }
    }
  };
  side(N, 0); side(E, 1); side(S, 2); side(W, 3);
  return canvas;
}

/* ---------- object sprites (transparent ground) ---------- */

/* The shadow a standing thing throws.
 *
 * Built as a coverage mask and painted ONCE, because stamping five translucent
 * ellipses on top of each other compounds their alpha at every overlap and
 * produces exactly the blotchy airbrushed smear that a 16-bit frame never has.
 * Direction is LIGHT_DX/LIGHT_DY, length is proportional to height: one sun,
 * low in the sky, for every object in the world. */
function castShadow(ctx, w, h, cx, cy, rx, ry, height, strength = 1, cap = INK_DEPTHS) {
  inkBegin(w, h, cap);
  const cov = COV_PLATE.length >= w * h ? COV_PLATE : new Uint8Array(w * h);
  cov.fill(0, 0, w * h);
  const steps = Math.max(2, Math.round(height));
  for (let s = 0; s <= steps; s++) {
    const t = s / steps;
    const sx = cx - LIGHT_DX * t * height * 0.85;
    const sy = cy - LIGHT_DY * t * height * 0.30;
    const r = rx * (1 - t * 0.45), r2 = ry * (1 - t * 0.35);
    const y0 = Math.max(0, Math.ceil(sy - r2)), y1 = Math.min(h - 1, Math.floor(sy + r2));
    for (let y = y0; y <= y1; y++) {
      const dy = (y + 0.5 - sy) / r2;
      const q = 1 - dy * dy;
      if (q <= 0) continue;
      const half = Math.max(0.5, r * Math.sqrt(q));
      const x0 = Math.max(0, Math.round(sx - half)), x1 = Math.min(w - 1, Math.round(sx + half));
      for (let x = x0; x <= x1; x++) cov[y * w + x] = 1;
    }
  }
  // Two densities: solid near the foot, dithered at the tip where the shadow
  // has spread and softened. That gradient is four pixels wide and it is the
  // only gradient allowed anywhere near this pixel grid.
  const near = strength >= 0.85 ? 2 : 1;
  const far = 1;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!cov[y * w + x]) continue;
      const d = Math.hypot((x - cx) / Math.max(1, height), (y - cy) / Math.max(1, height));
      if (d > 0.62) { if (bayer(x, y) < 0.45) inkMark(x, y, far); }
      else inkMark(x, y, near);
    }
  }
  /* Left open on purpose: contactShadow flushes the pair as one shadow. */
}

/* The hot rim. Frazetta's second light: a low, close source that catches the
 * UNDERSIDE of a mass in the region's own accent, while the key stays up and
 * left. Bone and chrome in the same frame — docs/09-story-bible.md §8. */
function hotRim(ctx, x, y, w, colour, seed, salt) {
  for (let k = 0; k < w; k++) {
    if (cellRand(seed, k, salt, 0xb1) < 0.42) continue;
    px(ctx, x + k, y, 1, 1, colour);
  }
}

function treeMode(st) {
  if (st.surf === 'ash' || st.surf === 'cinder' || st.surf === 'bone') return 'dead';
  if (st.surf === 'rot') return 'hung';
  if (st.surf === 'snow') return 'snow';
  return st.pine ? 'pine' : 'leaf';
}

function treeSprite(P, st, seed, variant) {
  const W = 24, H = 24;
  const { canvas, ctx } = make(W, H);
  const F = P.foliage, Bk = P.bark, A = P.accent;
  const mode = treeMode(st);
  const rand = rng(seed + variant * 613 + 1);

  castShadow(ctx, W, H, 8, H - 3, 5, 2, 11, 1);
  contactShadow(ctx, 8, H - 3, 5, 2, 1);

  const trunk = (x, y, w, h) => {
    px(ctx, x, y, w, h, Bk[1]);
    px(ctx, x, y, 1, h, Bk[3]);                        // lit edge, up-left
    px(ctx, x + w - 1, y, 1, h, occlude(Bk[0], 0.4));  // occluded edge
    for (let k = 2; k < h; k += 3) px(ctx, x + 1, y + k, Math.max(1, w - 2), 1, Bk[0]);
    px(ctx, x - 1, y + h - 2, w + 2, 1, Bk[1]);        // root flare
    bottomBand(ctx, x - 1, y + h - 1, w + 2, occlude(Bk[0], 0.6));
  };

  if (mode === 'pine' || mode === 'snow') {
    trunk(7, H - 9, 2, 8);
    // Four tiers, each wider than the last: a conifer is a stack of skirts, and
    // the lit half of every skirt faces the same way as everything else.
    for (let i = 0; i < 4; i++) {
      const top = 2 + i * 4;
      const wide = 2 + i * 2;
      for (let k = 0; k < 4; k++) {
        const half = Math.max(1, Math.round(wide * (k + 1) / 4));
        px(ctx, 8 - half, top + k, half, 1, F[3]);
        px(ctx, 8, top + k, half, 1, F[1]);
      }
      px(ctx, 8 - wide, top + 3, wide * 2, 1, occlude(F[0], 0.3));
      if (mode === 'snow') {
        px(ctx, 8 - wide, top + 1, wide + 1, 1, '#dce8ff');
        px(ctx, 8 - wide, top + 2, wide, 1, '#a8bcd8');
      }
      hotRim(ctx, 8 - wide, top + 3, wide * 2, mixHex(A[4], F[3], 0.4), seed, i);
    }
    px(ctx, 7, 0, 2, 3, mode === 'snow' ? '#ffffff' : F[3]);

  } else if (mode === 'dead') {
    // Nothing grows in the wastes. A dead tree is a silhouette problem: all the
    // read has to come from the branch angles, so they are hashed but pruned to
    // alternate sides and they thin as they rise.
    trunk(6, 5, 4, H - 6);
    // Four limbs at hashed heights and lengths, each rising as it goes out, each
    // forking once. Alternating stubs every other row is a fish skeleton.
    const used = [];
    for (let i = 0; i < 4; i++) {
      const y = 7 + Math.floor(rand() * 10);
      if (used.some(u => Math.abs(u - y) < 3)) continue;
      used.push(y);
      const dir = rand() < 0.5 ? 1 : -1;
      const len = 4 + Math.floor(rand() * 3);
      let bx = dir > 0 ? 9 : 6, by = y;
      for (let k = 0; k < len; k++) {
        bx += dir;
        if (k % 2 === 0) by--;
        if (bx < 0 || bx > 15 || by < 1) break;
        px(ctx, bx, by, 1, 2, Bk[1]);
        px(ctx, bx, by, 1, 1, Bk[3]);
        if (k === len - 2) { px(ctx, bx, by - 2, 1, 2, Bk[1]); px(ctx, bx, by - 2, 1, 1, Bk[2]); }
      }
    }
    px(ctx, 6, 3, 4, 3, Bk[1]);
    px(ctx, 6, 3, 4, 1, Bk[3]);
    px(ctx, 5, 1, 2, 3, Bk[1]); px(ctx, 9, 0, 2, 4, Bk[1]);
    hotRim(ctx, 5, H - 8, 8, A[3], seed, 3);

  } else {
    trunk(7, H - 11, 3, 10);
    // Canopy. A SOLID crown first, with a wobbled boundary, then clusters on top
    // of it for value. Stamping clusters at random positions and hoping they
    // meet — which is what this used to do — leaves holes punched through the
    // middle of every tree, and a wood full of them reads as lichen.
    const CR = 7.4;
    for (let cy = 0; cy <= 15; cy++) {
      for (let cx = 0; cx < 16; cx++) {
        const dx = (cx - 8) / CR, dy = (cy - 7.6) / (CR * 0.94);
        const d = dx * dx + dy * dy;
        const lobe = 0.92 + (wave(seed + variant, 17, cx * 3 + cy * 5, 8, 2) - 0.5) * 0.55;
        if (d > lobe) continue;
        const l = (cx - 8) * LIGHT_DX + (cy - 8) * LIGHT_DY;
        px(ctx, cx, cy, 1, 1, l > 3 ? F[3] : l < -4 ? F[1] : F[2]);
      }
    }
    // Clusters: the crown is a lot of small masses, and each one turns its own
    // face to the light.
    for (let i = 0; i < 16; i++) {
      const a = rand() * Math.PI * 2, r = Math.sqrt(rand()) * 0.78;
      const cx = 8 + Math.round(Math.cos(a) * r * CR);
      const cy = 8 + Math.round(Math.sin(a) * r * CR * 0.94);
      const l = (cx - 8) * LIGHT_DX + (cy - 8) * LIGHT_DY;
      px(ctx, cx, cy, 2, 2, l > 0 ? F[3] : F[1]);
      if (l > 2) px(ctx, cx, cy, 1, 1, F[4]);
    }
    px(ctx, 4, 13, 8, 2, occlude(F[0], 0.35));   // the shaded underside of the crown
    hotRim(ctx, 3, 14, 10, mixHex(A[4], F[4], 0.45), seed, 5);
    if (mode === 'hung') {
      // Moss hanging out of a swamp canopy: three strands, uneven, dripping off
      // the shaded side because that is where the air does not move.
      for (const hx of [4, 9, 12]) {
        const len = 3 + Math.floor(cellRand(seed, hx, variant, 0xb4) * 5);
        for (let k = 0; k < len; k++) px(ctx, hx, 14 + k, 1, 1, k === len - 1 ? F[0] : F[1]);
      }
    }
  }
  return canvas;
}

function bushSprite(P, st, seed, variant) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const F = P.foliage, A = P.accent;
  const rand = rng(seed + variant * 71 + 1);
  castShadow(ctx, W, H, 8, 14, 5, 2, 5, 0.85);
  contactShadow(ctx, 8, 14, 5, 2, 0.85);
  for (let i = 0; i < 22; i++) {
    const cx = 8 + Math.round((rand() - 0.5) * 10);
    const cy = 10 + Math.round((rand() - 0.5) * 7);
    if (cy > 13 || cy < 4) continue;
    const lit = (cx - 8) * LIGHT_DX + (cy - 9) * LIGHT_DY > 1;
    px(ctx, cx, cy, 2, 2, lit ? F[3] : F[1]);
  }
  px(ctx, 4, 13, 8, 1, occlude(F[0], 0.4));
  bottomBand(ctx, 4, 14, 8, occlude(F[0], 0.6));
  hotRim(ctx, 3, 13, 10, mixHex(A[4], F[4], 0.4), seed, 7);
  if (variant % 3 === 0) { px(ctx, 5, 7, 1, 1, A[3]); px(ctx, 10, 9, 1, 1, A[4]); }
  return canvas;
}

function rockSprite(P, st, seed, variant) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const Rk = P.rock;
  const w = 8 + (variant % 3) * 2;
  const h = 6 + (variant % 2) * 2;
  const x0 = 8 - (w >> 1), y0 = 14 - h;
  castShadow(ctx, W, H, 8, 14, w / 2 + 1, 2, h + 3, 0.9);
  contactShadow(ctx, 8, 14, w / 2 + 1, 2, 0.9);
  // A rounded mass, then three flat facets on it: the lit crown up-left, the
  // body, and the turn-away on the right. A rectangle with a light line on top
  // is a crate.
  for (let yy = y0; yy < 14; yy++) {
    const t = (yy - y0) / Math.max(1, h - 1);
    const half = Math.max(1, Math.round((w / 2) * Math.sqrt(Math.max(0.08, 1 - (1 - t) * (1 - t) * 0.85))));
    const l = 8 - half, r = 8 + half;
    px(ctx, l, yy, r - l, 1, Rk[1]);
    if (t < 0.55) px(ctx, l + 1, yy, Math.max(1, (r - l) - 3), 1, Rk[2]);
    if (t < 0.34) px(ctx, l + 1, yy, Math.max(1, (r - l) - 5), 1, Rk[3]);
    px(ctx, r - 2, yy, 2, 1, occlude(Rk[0], 0.45));
    if (yy === y0 + 1) px(ctx, l + 2, yy, Math.max(1, half - 2), 1, Rk[4]);
  }
  const fr = y0 + 3 + (variant % 2);
  if (fr < 13) px(ctx, 8 - 1, fr, 3, 1, occlude(Rk[0], 0.4));   // a fracture
  if (st.rock === 'ore') px(ctx, x0 + 2, y0 + 2, 1, 2, P.accent[3]);
  bottomBand(ctx, x0, y0 + h - 1, w, occlude(Rk[0], 0.65));
  hotRim(ctx, x0, y0 + h - 2, w, P.accent[3], seed, 9);
  return canvas;
}

function stumpSprite(P, st, seed) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const Bk = P.bark;
  castShadow(ctx, W, H, 8, 14, 4, 2, 5, 0.85);
  contactShadow(ctx, 8, 14, 4, 2, 0.85);
  px(ctx, 5, 9, 6, 5, Bk[1]);
  px(ctx, 5, 9, 1, 5, Bk[2]);
  px(ctx, 5, 8, 6, 2, Bk[2]);
  px(ctx, 6, 8, 4, 1, Bk[3]);
  px(ctx, 7, 8, 2, 1, Bk[1]);                        // the cut rings
  px(ctx, 10, 9, 1, 4, occlude(Bk[0], 0.5));
  bottomBand(ctx, 5, 13, 6, occlude(Bk[0], 0.65));
  return canvas;
}

function crystalSprite(P, st, seed, variant) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const A = P.accent;
  castShadow(ctx, W, H, 8, 14, 3, 1.5, 7, 0.7);
  contactShadow(ctx, 8, 14, 3, 1.5, 0.7);
  const h = 7 + (variant % 3);
  for (let i = 0; i < h; i++) {
    const w = Math.max(1, 4 - Math.floor(i / 2));
    px(ctx, 8 - (w >> 1), 13 - i, w, 1, i > h - 3 ? A[4] : A[2]);
  }
  px(ctx, 7, 13 - h + 2, 1, h - 3, A[4]);            // the lit facet
  px(ctx, 9, 10, 1, 3, occlude(A[0], 0.4));
  if (variant % 2) for (let i = 0; i < 4; i++) px(ctx, 11, 13 - i, 1, 1, i > 2 ? A[4] : A[2]);
  // Its own light spilling onto the ground at its foot: a crystal that lights
  // nothing is a painted rock.
  px(ctx, 6, 13, 5, 1, mixHex(A[4], '#ffffff', 0.2));
  return canvas;
}

function bonesSprite(P, st, seed) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const b = '#cfc4b0', m = '#948878', d = occlude('#5c5248', 0.35);
  castShadow(ctx, W, H, 8, 13, 5, 1.5, 3, 0.7);
  contactShadow(ctx, 8, 13, 5, 1.4, 0.7);
  px(ctx, 3, 11, 8, 1, b); px(ctx, 3, 12, 8, 1, m); px(ctx, 3, 13, 8, 1, d);
  px(ctx, 2, 10, 2, 2, b); px(ctx, 10, 10, 2, 2, b);
  px(ctx, 6, 7, 4, 4, b);
  px(ctx, 6, 7, 4, 1, '#f4ecdc');
  px(ctx, 6, 10, 4, 1, m); px(ctx, 6, 11, 4, 1, d);
  px(ctx, 7, 8, 1, 1, '#1a1620'); px(ctx, 9, 8, 1, 1, '#1a1620');
  return canvas;
}

function mushroomSprite(P, st, seed, variant) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const C = ramp(variant % 2 ? '#c45a4a' : '#8f6ad6');
  castShadow(ctx, W, H, 8, 14, 3, 1.4, 5, 0.7);
  contactShadow(ctx, 8, 14, 3, 1.4, 0.7);
  px(ctx, 7, 10, 2, 4, '#e8dcc0');
  px(ctx, 7, 10, 1, 4, '#f4ecdc');
  px(ctx, 8, 10, 1, 4, '#a89c84');
  px(ctx, 5, 8, 6, 2, C[2]);
  px(ctx, 6, 7, 4, 1, C[3]);
  px(ctx, 6, 7, 2, 1, C[4]);
  px(ctx, 5, 9, 6, 1, occlude(C[0], 0.35));          // the gills, in their own shade
  bottomBand(ctx, 7, 13, 2, occlude(C[0], 0.6));
  return canvas;
}

/* ---------- fire: the shared clock, burning ---------- */

/* A flame is a teardrop whose waist moves. Six frames on the shared clock, each
 * rasterised once — the whole point of doing it this way rather than with a
 * particle system is that a torch costs one drawImage and zero allocation. */
function flame(ctx, cx, base, height, frame, seed, scale = 1) {
  const core = '#fff0b4', hot = '#ffd97a', mid = '#e8762a', edge = '#a83c10';
  const t = frame / FLAME_FRAMES;
  for (let k = 0; k < height; k++) {
    const u = k / height;
    const lean = Math.sin(2 * Math.PI * (t + u * 0.8)) * 1.6 * u;
    const w = Math.max(1, Math.round((1 - u * u) * 3.2 * scale
              + Math.sin(2 * Math.PI * (t * 2 + u * 3)) * 0.8));
    const x = Math.round(cx + lean);
    const y = base - k;
    px(ctx, x - w, y, w * 2, 1, u > 0.72 ? edge : mid);
    if (u < 0.78) px(ctx, x - Math.max(0, w - 1), y, Math.max(1, (w - 1) * 2), 1, hot);
    if (u < 0.42) px(ctx, x, y, 1, 1, core);
  }
  // Sparks leaving the top, hashed per frame so they do not march.
  for (let i = 0; i < 2; i++) {
    if (cellRand(seed, i, frame, 0xc1) < 0.45) continue;
    const sx = Math.round(cx + (cellRand(seed, i, frame, 0xc2) - 0.5) * 5);
    const sy = base - height - 1 - Math.floor(cellRand(seed, i, frame, 0xc3) * 3);
    px(ctx, sx, sy, 1, 1, hot);
  }
}

function fireSprite(P, st, kind, seed, frame) {
  const W = 16, H = 22;
  const { canvas, ctx } = make(W, H);
  const Bk = P.bark, A = P.accent;
  // Gunmetal, because this world is made of it.
  const Ir = ramp('#454956');
  castShadow(ctx, W, H, 8, H - 2, 3, 1.5, 5, 0.8);
  contactShadow(ctx, 8, H - 2, 3, 1.5, 0.9);

  if (kind === 'brazier') {
    // Three legs, a bowl, coals. Gunmetal, because this world is made of it.
    px(ctx, 5, H - 7, 1, 6, Ir[1]); px(ctx, 10, H - 7, 1, 6, Ir[1]);
    px(ctx, 8, H - 7, 1, 6, Ir[0]);
    px(ctx, 4, H - 12, 8, 5, Ir[2]);
    px(ctx, 4, H - 12, 8, 1, Ir[4]);
    px(ctx, 4, H - 12, 1, 5, Ir[3]);
    px(ctx, 11, H - 12, 1, 5, occlude(Ir[0], 0.5));
    bottomBand(ctx, 4, H - 8, 8, occlude(Ir[0], 0.6));
    px(ctx, 5, H - 12, 6, 1, frame % 2 ? '#e8762a' : '#a83c10');
    flame(ctx, 8, H - 12, 9, frame, seed, 1.15);
  } else if (kind === 'pyre') {
    for (let i = 0; i < 4; i++) {
      const y = H - 4 - i;
      px(ctx, 2 + i, y, 12 - i * 2, 1, i % 2 ? Bk[1] : Bk[2]);
      px(ctx, 2 + i, y, 2, 1, Bk[3]);
    }
    px(ctx, 3, H - 3, 10, 1, '#a83c10');
    bottomBand(ctx, 2, H - 2, 12, occlude(Bk[0], 0.6));
    flame(ctx, 8, H - 5, 13, frame, seed, 1.6);
  } else if (kind === 'lantern') {
    px(ctx, 7, H - 14, 2, 13, Bk[1]);
    px(ctx, 7, H - 14, 1, 13, Bk[3]);
    bottomBand(ctx, 6, H - 2, 4, occlude(Bk[0], 0.6));
    px(ctx, 5, H - 18, 6, 6, Ir[1]);
    px(ctx, 6, H - 17, 4, 4, occlude('#2a1e12', 0.2));
    px(ctx, 5, H - 18, 6, 1, Ir[4]);
    px(ctx, 5, H - 13, 6, 1, occlude(Ir[0], 0.5));
    flame(ctx, 8, H - 14, 4, frame, seed, 0.55);
    px(ctx, 6, H - 16, 1, 3, mixHex(A[4], '#ffffff', 0.3));
  } else {
    // torch: a stave, a bound head, a big ragged flame
    px(ctx, 7, H - 13, 2, 12, Bk[1]);
    px(ctx, 7, H - 13, 1, 12, Bk[3]);
    bottomBand(ctx, 6, H - 2, 4, occlude(Bk[0], 0.6));
    px(ctx, 6, H - 15, 4, 3, Ir[1]);
    px(ctx, 6, H - 15, 4, 1, Ir[3]);
    px(ctx, 6, H - 13, 4, 1, occlude(Ir[0], 0.5));
    flame(ctx, 8, H - 15, 10, frame, seed, 1);
  }
  return canvas;
}

/* ---------- banners ---------- */

/* Cloth on a pole, swaying on the shared clock. Album-cover logic: black cloth,
 * a chrome finial, a sigil in the region's accent, and a torn hem — the eleven
 * chapters are the eleven tracks of a double gatefold and the flags agree. */
function bannerSprite(P, st, seed, frame) {
  const W = 16, H = 24;
  const { canvas, ctx } = make(W, H);
  const A = P.accent, Bk = P.bark;
  const Ch = ramp('#8a92a6');
  const Cl = ramp(mixHex(P.dark[2], A[1], 0.25));
  const lean = [0, 1, 2, 1][frame % SWAY_FRAMES];

  castShadow(ctx, W, H, 7, H - 2, 2, 1.2, 6, 0.75);
  contactShadow(ctx, 7, H - 2, 2, 1.2, 0.8);
  px(ctx, 6, 4, 2, H - 5, Bk[1]);
  px(ctx, 6, 4, 1, H - 5, Bk[3]);
  bottomBand(ctx, 5, H - 2, 4, occlude(Bk[0], 0.6));
  // finial
  px(ctx, 5, 2, 4, 2, Ch[3]); px(ctx, 5, 2, 4, 1, Ch[4]);
  px(ctx, 6, 0, 2, 2, Ch[2]);

  for (let y = 0; y < 13; y++) {
    const bow = Math.round(Math.sin((y / 13) * Math.PI) * lean);
    const x = 8 + bow;
    const hem = y > 9 ? (cellRand(seed, y, frame, 0xd1) > 0.5 ? 1 : 0) : 0;
    const wdt = 6 - hem - (y > 10 ? y - 10 : 0);
    if (wdt <= 0) continue;
    px(ctx, x, 5 + y, wdt, 1, y % 4 === 0 ? Cl[1] : Cl[2]);
    px(ctx, x, 5 + y, 1, 1, Cl[3]);                        // lit fold, up-left
    px(ctx, x + wdt - 1, 5 + y, 1, 1, occlude(Cl[0], 0.4)); // shaded fold
  }
  // the sigil
  px(ctx, 9 + (lean >> 1), 8, 4, 1, A[3]);
  px(ctx, 10 + (lean >> 1), 9, 2, 3, A[2]);
  px(ctx, 9 + (lean >> 1), 12, 4, 1, A[4]);
  return canvas;
}

function shrineSprite(P, st, seed) {
  const W = 22, H = 26;
  const { canvas, ctx } = make(W, H);
  const Rk = P.rock, A = P.accent;
  castShadow(ctx, W, H, 8, H - 2, 6, 2, 14, 1);
  contactShadow(ctx, 8, H - 2, 6, 2, 1);
  px(ctx, 3, H - 4, 10, 2, Rk[1]);
  px(ctx, 3, H - 4, 10, 1, Rk[2]);
  bottomBand(ctx, 3, H - 2, 10, occlude(Rk[0], 0.6));
  px(ctx, 4, H - 17, 8, 13, Rk[2]);
  px(ctx, 4, H - 17, 1, 13, Rk[3]);
  px(ctx, 11, H - 17, 1, 13, occlude(Rk[0], 0.45));
  for (let i = 0; i < 4; i++) px(ctx, 5 + i * 2, H - 12, 1, 6, Rk[1]);
  px(ctx, 3, H - 19, 10, 3, Rk[1]);
  px(ctx, 3, H - 19, 10, 1, Rk[4]);
  px(ctx, 3, H - 16, 10, 1, occlude(Rk[0], 0.45));
  px(ctx, 6, H - 16, 4, 4, A[1]);
  px(ctx, 7, H - 15, 2, 2, A[4]);
  px(ctx, 6, H - 22, 4, 3, A[3]);      // the floating sigil
  px(ctx, 7, H - 23, 2, 1, A[4]);
  hotRim(ctx, 4, H - 5, 8, A[3], seed, 11);
  return canvas;
}

function chestSprite(P, st, seed, open) {
  const W = 20, H = 16;
  const { canvas, ctx } = make(W, H);
  const wood = ramp('#7a4f22'), gold = P.accent;
  castShadow(ctx, W, H, 8, 14, 6, 2, 7, 0.9);
  contactShadow(ctx, 8, 14, 6, 2, 0.95);
  px(ctx, 2, 8, 12, 6, wood[1]);
  px(ctx, 2, 8, 12, 1, wood[2]);
  px(ctx, 2, 8, 1, 6, wood[3]);
  px(ctx, 13, 8, 1, 6, occlude(wood[0], 0.5));
  bottomBand(ctx, 2, 13, 12, occlude(wood[0], 0.6));
  if (open) {
    px(ctx, 2, 3, 12, 4, wood[1]);
    px(ctx, 3, 4, 10, 2, occlude('#2a1e12', 0.3));
    px(ctx, 4, 9, 8, 3, gold[4]);
    px(ctx, 4, 9, 8, 1, '#ffffff');
  } else {
    px(ctx, 2, 4, 12, 5, wood[2]);
    px(ctx, 3, 3, 10, 1, wood[3]);
    px(ctx, 2, 8, 12, 1, gold[2]);
    px(ctx, 7, 8, 2, 3, gold[3]);
    px(ctx, 7, 9, 2, 1, occlude(gold[0], 0.4));
  }
  px(ctx, 3, 4, 1, 5, wood[3]);
  px(ctx, 12, 4, 1, 5, occlude(wood[0], 0.5));
  hotRim(ctx, 2, 12, 12, gold[3], seed, 13);
  return canvas;
}

/* ---------- buildings ---------- */
/* 40x36 over a 2x1 footprint, so a house is a building and not a shed, and so
 * there is room to the lower right for the shadow it throws. Four rebuild tiers,
 * because the village visibly recovers as fluency rises and that is the best set
 * piece the design already contains. */
const BUILD_VARIANTS = ['cottage', 'hall', 'forge', 'tower'];
const BUILD_W = 40, BUILD_H = 36;

export function buildingSprite(palette, seed, tier = 2, variant = 0, biome) {
  const st = biomeStyle(biome);
  const P = palOf(palette, biome ? st : null);
  const kind = BUILD_VARIANTS[variant % BUILD_VARIANTS.length];
  const { canvas, ctx } = make(BUILD_W, BUILD_H);
  const rand = rng(seed + variant * 1301 + tier * 17 + 1);
  const wall = ramp(tier >= 2 ? '#c8b492' : tier === 1 ? '#a2907a' : '#7a6f60');
  const roof = tier >= 2 ? P.accent : ramp(mixHex(P.accent[2], '#4a4038', 0.55));
  const Bk = P.bark;

  /* FIFTEEN colours, declared up front, and nothing in the drawing below is
   * allowed to invent a sixteenth.
   *
   * A house is the most complicated object this file draws — walls, roof,
   * timber, glass, trim, four rebuild tiers — and it is exactly the kind of
   * sprite where a shading helper called ad hoc at six different strengths
   * quietly produces thirty-odd tones. Naming the palette first is what makes
   * the timber in the frame the same black as the shadow under the eaves, and
   * that agreement is the whole reason a village reads as one village. */
  const D  = INK;                                    // 0  outline, every deep shadow
  const W0 = wall[0], W1 = wall[1], W2 = wall[2], W3 = wall[3];
  const R0 = roof[0], R1 = roof[1], R2 = roof[2], R3 = roof[3];
  const T0 = Bk[0],  T1 = Bk[1],  T2 = Bk[2];        // timber
  const LIT = tier >= 3 ? '#ffeaa8' : tier === 2 ? '#ffd98a' : '#2e2a1c';
  const GLOW = tier >= 2 ? '#fff4c8' : LIT;
  const TRIM = P.accent[3];

  const tall = kind === 'tower';
  const wide = kind === 'hall';
  const x0 = tall ? 9 : wide ? 1 : 3;
  const x1 = tall ? 23 : wide ? 31 : 29;
  const wallTop = (tall ? 8 : wide ? 13 : 15) + 4;
  const base = 34;

  /* One rung only. The palette above is fifteen colours and this sprite is not
   * allowed a sixteenth, so the house is grounded by a single dithered tone
   * rather than by the full four-step ladder the smaller props can afford. */
  castShadow(ctx, BUILD_W, BUILD_H, (x0 + x1) / 2, base, (x1 - x0) / 2, 2.5, 13, 1, 1);
  contactShadow(ctx, (x0 + x1) / 2, base, (x1 - x0) / 2, 2.5, 1);

  // walls
  px(ctx, x0, wallTop, x1 - x0, base - wallTop, W2);
  px(ctx, x0, wallTop, 1, base - wallTop, W3);
  px(ctx, x1 - 2, wallTop, 1, base - wallTop, W1);
  px(ctx, x1 - 1, wallTop, 1, base - wallTop, D);
  for (let y = wallTop; y < base; y++) {
    for (let x = x0; x < x1; x++) {
      if (cellRand(seed, x, y, 81) > 0.93) px(ctx, x, y, 1, 1, W1);
    }
  }
  // timber framing, which is what makes a wall read as built rather than poured
  if (kind !== 'tower') {
    px(ctx, x0 + 4, wallTop, 1, base - wallTop, T1);
    px(ctx, x0 + 5, wallTop, 1, base - wallTop, T0);
    px(ctx, x1 - 5, wallTop, 1, base - wallTop, T1);
    px(ctx, x0, wallTop + 6, x1 - x0, 1, T1);
    px(ctx, x0, wallTop + 7, x1 - x0, 1, T0);
  }
  // Where the wall meets the ground. Every solid in this game ends in this band.
  bottomBand(ctx, x0, base - 2, x1 - x0, W0);
  bottomBand(ctx, x0, base - 1, x1 - x0, D);

  // roof — a gable stepped one pixel per row, the cheapest honest 16-bit roof
  const roofBase = wallTop + 1;
  const span = x1 - x0 + 4;
  const rows = tall ? 7 : 9;
  for (let i = 0; i < rows; i++) {
    const w = span - i * 2;
    const rx = x0 - 2 + i;
    const y = roofBase - i;
    if (w <= 0) break;
    const holed = tier === 0 && cellRand(seed, i, 0, 82) > 0.55;
    px(ctx, rx, y, w, 1, i % 2 ? R1 : R2);
    // Light gathers at the ridge and runs off the right eave. Splitting the
    // roof down the middle instead — which is the obvious thing to write — puts
    // a seam where a house has none.
    if (i >= rows - 3) px(ctx, rx, y, w, 1, R3);
    px(ctx, rx, y, 2, 1, R3);
    px(ctx, rx + w - 2, y, 2, 1, R0);
    if (holed) {
      const hx = rx + 2 + Math.floor(cellRand(seed, i, 1, 83) * Math.max(1, w - 4));
      ctx.clearRect(hx, y, 2, 1);
    }
  }
  // The eaves throw a hard shadow down the wall. These three rows are most of
  // why a roof reads as overhanging rather than as painted on.
  px(ctx, x0 - 2, roofBase + 1, span, 1, R0);
  px(ctx, x0, roofBase + 2, x1 - x0, 1, D);
  px(ctx, x0, roofBase + 3, x1 - x0, 1, W0);

  // windows
  const winY = wallTop + 9;
  const winXs = tall ? [15] : wide ? [6, 14, 23] : [7, 20];
  const windows = [];
  for (const wx of winXs) {
    if (tier === 0 && cellRand(seed, wx, 2, 84) > 0.5) continue;
    px(ctx, wx - 1, winY - 1, 6, 6, T1);
    px(ctx, wx - 1, winY - 1, 6, 1, T2);
    px(ctx, wx - 1, winY + 4, 6, 1, D);
    px(ctx, wx, winY, 4, 4, LIT);
    if (tier >= 2) {
      px(ctx, wx, winY, 4, 1, GLOW);
      px(ctx, wx + 2, winY, 1, 4, T1);
      px(ctx, wx - 1, winY + 5, 6, 1, W3);   // light spilling onto the sill
      windows.push([wx + 2, winY + 2]);
    } else if (tier === 1) {
      px(ctx, wx - 1, winY + 1, 6, 1, T2);   // boards
      px(ctx, wx - 1, winY + 3, 6, 1, T2);
    }
  }

  // door
  const dx = 14;
  px(ctx, dx, base - 11, 5, 11, T1);
  px(ctx, dx, base - 11, 5, 1, T2);
  px(ctx, dx, base - 11, 1, 11, T2);
  px(ctx, dx + 1, base - 10, 3, 10, tier === 0 ? D : T0);
  px(ctx, dx + 4, base - 11, 1, 11, D);
  if (tier >= 1) px(ctx, dx + 3, base - 6, 1, 1, TRIM);

  // tier flourishes
  if (tier === 0) {
    for (let i = 0; i < 6; i++) {
      const rx = x0 + Math.floor(rand() * (x1 - x0 - 2));
      px(ctx, rx, base - 1, 2, 1, W0);
      px(ctx, rx + Math.floor(rand() * 3) - 1, base, 2, 1, W1);
    }
  }
  if (tier >= 2 && kind === 'forge') {
    px(ctx, x1 - 8, roofBase - rows - 3, 4, 8, W1);
    px(ctx, x1 - 8, roofBase - rows - 3, 4, 1, W3);
    px(ctx, x1 - 5, roofBase - rows - 3, 1, 8, D);
    px(ctx, x1 - 7, roofBase - rows - 4, 2, 1, TRIM);
  }
  if (tier >= 3) {
    px(ctx, x0 + 1, base - 5, 6, 3, T1);          // window box
    px(ctx, x0 + 1, base - 5, 6, 1, T2);
    px(ctx, x0 + 2, base - 6, 1, 1, TRIM);
    px(ctx, x0 + 5, base - 6, 1, 1, TRIM);
    for (let i = 0; i < span; i += 3) px(ctx, x0 - 2 + i, roofBase + 2, 2, 1, TRIM);
  }
  canvas.windows = windows;
  canvas.footY = base;
  return canvas;
}

/* ---------- flora (the swaying overlay) ---------- */

function tuftSprite(P, st, seed, variant, frame) {
  const { canvas, ctx } = make(8, 8);
  const F = variant % 3 === 0 ? P.foliage : P.ground;
  const lean = [0, 1, 0, -1][frame % SWAY_FRAMES];
  const rand = rng(seed + variant * 97 + 1);
  const blades = 3 + Math.floor(rand() * 2);
  px(ctx, 2, 7, 4, 1, 'rgba(7,6,12,0.26)');   // the clump's own contact shadow
  for (let i = 0; i < blades; i++) {
    const bx = 1 + Math.floor(rand() * 5);
    const h = 3 + Math.floor(rand() * 2);
    for (let k = 0; k < h; k++) {
      const t = k / h;
      const x = bx + Math.round(lean * t * 1.6);
      px(ctx, x, 7 - k, 1, 1, k === h - 1 ? F[3] : F[1]);
    }
  }
  return canvas;
}

function flowerSprite(P, st, seed, variant, frame) {
  const { canvas, ctx } = make(8, 8);
  // Five petal colours, every one pulled a third of the way to the region's own
  // accent. Untinted pastels scattered across a dark biome are confetti; a
  // shared pull is what makes them read as this place's flowers.
  const petals = ['#e8e0f0', '#ffd97a', '#e87a9a', '#8fb8ff', '#ffb05a'];
  const c = ramp(mixHex(petals[variant % petals.length], P.accent[3], 0.34));
  const lean = [0, 1, 0, -1][frame % SWAY_FRAMES];
  const F = P.foliage;
  px(ctx, 2, 7, 3, 1, 'rgba(7,6,12,0.22)');
  px(ctx, 3, 5, 1, 3, F[1]);
  px(ctx, 3 + Math.round(lean * 0.5), 4, 1, 1, F[1]);
  const hx = 3 + lean;
  px(ctx, hx, 2, 2, 2, c[2]);
  px(ctx, hx, 2, 1, 1, c[4]);
  px(ctx, hx + 1, 3, 1, 1, occlude(c[0], 0.35));
  px(ctx, hx - 1, 3, 1, 1, c[2]);
  px(ctx, hx + 2, 2, 1, 1, c[2]);
  return canvas;
}

function reedSprite(P, st, seed, variant, frame) {
  const { canvas, ctx } = make(8, 12);
  const F = P.foliage;
  const lean = [0, 1, 2, 1][frame % SWAY_FRAMES];
  const rand = rng(seed + variant * 131 + 1);
  for (let i = 0; i < 3; i++) {
    const bx = 1 + Math.floor(rand() * 5);
    const h = 6 + Math.floor(rand() * 4);
    for (let k = 0; k < h; k++) {
      const t = k / h;
      px(ctx, bx + Math.round(lean * t), 11 - k, 1, 1, k === h - 1 ? F[3] : F[2]);
    }
    if (rand() < 0.5) px(ctx, bx + lean, 11 - h - 1, 1, 2, P.bark[2]);
  }
  return canvas;
}

/* ---------- tileset ---------- */

const setCache = new Map();

/* A region's tileset measures about 1.3 MB of rasterised canvas. Eight resident
 * is roughly ten megabytes, which is a working set, and past that a long session
 * that visits every region in the book would simply accumulate. Eviction is
 * safe: a scene holds its own reference, so an evicted region is only rebuilt
 * the next time it is loaded. */
const SET_CACHE_MAX = 8;
export const TERRAIN_SET_CACHE_MAX = SET_CACHE_MAX;

/* A region's rasterised terrain. Static tiles are built eagerly (there are few);
 * fringes, foam, cliff faces, occlusion and detail are built on first use — but
 * createScene then immediately warms exactly the ones the map actually contains,
 * so the render loop never allocates, not even on its first frame. */
export function terrainSet(regionId, palette, tier = 2, biome = 'grass') {
  const key = `${regionId}:${palette}:${tier}:${biome}`;
  const hit = setCache.get(key);
  if (hit) return hit;
  const st = biomeStyle(biome);
  const P = palOf(palette, st);
  const seed = hashStr(key);

  const fringeCache = new Map();
  const foamCache = new Map();
  const shelfCache = new Map();
  const emberCache = new Map();
  const cliffCache = new Map();
  const shadowCache = new Map();
  const aoCache = new Map();
  const detailCache = new Map();

  const set = {
    id: regionId, seed, tier, biome, P, style: st,
    palette: P.raw,
    ground: Array.from({ length: GROUND_VARIANTS }, (_, v) => surfaceTile(P, st, seed + v * 131, v)),
    path: [0, 1, 2, 3].map(v => pathTile(P, st, seed + v * 149, v)),
    stone: [0, 1, 2].map(v => stoneTile(P, st, seed + v * 167, v)),
    sand: [0, 1, 2].map(v => sandTile(P, st, seed + v * 181, v)),
    // 4x4-tile sheets, sub-rected at draw time. A single 16px water tile is
    // seamless and still repeats visibly every 16 pixels; sixteen is enough.
    water: [0, 1, 2, 3].map(d =>
      Array.from({ length: WATER_FRAMES }, (_, f) => waterSheet(P, st, seed + d * 13, d, f))),
    lava: Array.from({ length: WATER_FRAMES }, (_, f) => lavaSheet(P, seed + 37, f)),
    bridge: [bridgeTile(P, seed, false), bridgeTile(P, seed, true)],
    tree: [0, 1, 2, 3].map(v => treeSprite(P, st, seed + v * 211, v)),
    bush: [0, 1, 2].map(v => bushSprite(P, st, seed + v * 223, v)),
    rock: [0, 1, 2].map(v => rockSprite(P, st, seed + v * 227, v)),
    stump: [stumpSprite(P, st, seed + 229)],
    crystal: [0, 1, 2].map(v => crystalSprite(P, st, seed + v * 233, v)),
    bones: [bonesSprite(P, st, seed + 239)],
    mushroom: [0, 1].map(v => mushroomSprite(P, st, seed + v * 241, v)),
    shrine: shrineSprite(P, st, seed + 251),
    chest: [chestSprite(P, st, seed + 257, false), chestSprite(P, st, seed + 257, true)],
    building: [0, 1, 2, 3].map(t =>
      BUILD_VARIANTS.map((_, v) => buildingSprite(P.raw, seed + 263, Math.min(t, tier), v, biome))),
    banner: [Array.from({ length: SWAY_FRAMES }, (_, f) => bannerSprite(P, st, seed + 269, f))],
    fire: st.fire
      ? [Array.from({ length: FLAME_FRAMES }, (_, f) => fireSprite(P, st, st.fire, seed + 283, f))]
      : null,
    tuft: [0, 1, 2].map(v =>
      Array.from({ length: SWAY_FRAMES }, (_, f) => tuftSprite(P, st, seed + v * 271, v, f))),
    flower: [0, 1, 2, 3, 4].map(v =>
      Array.from({ length: SWAY_FRAMES }, (_, f) => flowerSprite(P, st, seed + v * 277, v, f))),
    reed: [0, 1].map(v =>
      Array.from({ length: SWAY_FRAMES }, (_, f) => reedSprite(P, st, seed + v * 281, v, f))),

    fringe(cls, mask, variant, host) {
      return memo(fringeCache, `${cls}|${mask}|${variant}|${host}`,
                  () => fringeTile(P, cls, mask, variant, seed, host));
    },
    shelf(mask, variant, depth) {
      return memo(shelfCache, `${mask}|${variant}|${depth}`,
                  () => shelfTile(P, mask, variant, depth, seed));
    },
    foam(mask, variant, frame) {
      return memo(foamCache, `${mask}|${variant}|${frame}`,
                  () => foamTile(P, mask, variant, frame, seed));
    },
    ember(mask, variant, frame) {
      return memo(emberCache, `${mask}|${variant}|${frame}`,
                  () => emberTile(mask, variant, frame, seed));
    },
    cliff(role, sides, variant) {
      return memo(cliffCache, `${role}|${sides}|${variant}`, () => {
        if (role === CLIFF_TOP) return cliffTopTile(P, st, seed, variant, sides);
        if (role === CLIFF_CAP) return cliffFaceTile(P, st, seed, variant, sides, 5);
        return cliffFaceTile(P, st, seed, variant, sides, 0);
      });
    },
    cliffShadow(mask) { return memo(shadowCache, mask, () => cliffShadowTile(mask)); },
    ao(mask) { return memo(aoCache, mask, () => aoTile(mask)); },
    detail(cls, v) {
      return memo(detailCache, `${cls}|${v}`, () => detailTile(P, st, cls, v, seed));
    },
    stats() {
      return {
        fringe: fringeCache.size, foam: foamCache.size, shelf: shelfCache.size,
        ember: emberCache.size, cliff: cliffCache.size, shadow: shadowCache.size,
        ao: aoCache.size, detail: detailCache.size,
      };
    },
  };
  setCache.set(key, set);
  while (setCache.size > SET_CACHE_MAX) {
    const oldest = setCache.keys().next().value;
    if (oldest === key) break;
    setCache.delete(oldest);
  }
  return set;
}

/* ---------- terrain shaping (optional, run before createScene) ---------- */

/* Cellular-automaton smoothing. An independent per-tile coin flip produces
 * pepper — isolated single trees with nothing for an edge to attach to — and
 * autotiling pepper looks worse than not autotiling it. Four passes turn the
 * same density into masses with walkable borders.
 *
 * Mutates and returns `grid`. */
export function smoothTerrain(grid, opts = {}) {
  const {
    code = TERRAIN.TREE, base = TERRAIN.GRASS, iterations = 4,
    birth = 5, survive = 4, border = 2, seed = 1,
  } = opts;
  const h = grid.length, w = grid[0].length;
  for (let it = 0; it < iterations; it++) {
    const next = grid.map(r => r.slice());
    for (let y = border; y < h - border; y++) {
      for (let x = border; x < w - border; x++) {
        if (grid[y][x] !== code && grid[y][x] !== base) continue;
        let n = 0;
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            if (!dx && !dy) continue;
            if (grid[y + dy][x + dx] === code) n++;
          }
        }
        if (grid[y][x] === code) next[y][x] = n >= survive ? code : base;
        else next[y][x] = n >= birth ? code : base;
      }
    }
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) grid[y][x] = next[y][x];
  }
  // A lone survivor is still pepper; promote or clear it.
  for (let y = border; y < h - border; y++) {
    for (let x = border; x < w - border; x++) {
      if (grid[y][x] !== code) continue;
      let n = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if ((dx || dy) && grid[y + dy][x + dx] === code) n++;
        }
      }
      if (n === 0 && cellRand(seed, x, y, 91) < 0.65) grid[y][x] = base;
    }
  }
  return grid;
}

/* Grow terrain masses to a target coverage.
 *
 * Cellular smoothing is the usual advice, but it only works from a ~45% seed —
 * run it over the 9% coin-flip scatter this game currently uses and the forest
 * simply dies. Blobs get the same result from the density the map actually
 * wants: round-ish clumps with organic borders, merging where they overlap, and
 * almost no isolated single tiles for an autotiler to render as a lone stump.
 *
 * Mutates and returns `grid`. */
export function growMasses(grid, opts = {}) {
  const {
    code = TERRAIN.TREE, base = TERRAIN.GRASS, coverage = 0.15,
    clumps = null, radius = 2.6, seed = 1, border = 2, squash = 1.25,
  } = opts;
  const h = grid.length, w = grid[0].length;
  const area = Math.max(1, (w - border * 2) * (h - border * 2));
  const target = Math.floor(area * coverage);
  const count = clumps || Math.max(3, Math.round(target / (radius * radius * 4)));
  const rand = rng((seed >>> 0) || 1);
  let placed = 0;
  for (let c = 0; c < count && placed < target; c++) {
    const cx = border + Math.floor(rand() * (w - border * 2));
    const cy = border + Math.floor(rand() * (h - border * 2));
    const r = radius * (0.7 + rand() * 0.9);
    const span = Math.ceil(r) + 1;
    for (let dy = -span; dy <= span; dy++) {
      for (let dx = -span; dx <= span; dx++) {
        const x = cx + dx, y = cy + dy;
        if (x < border || y < border || x >= w - border || y >= h - border) continue;
        if (grid[y][x] !== base) continue;
        const d = Math.hypot(dx / squash, dy);
        // The threshold wobbles per cell, which is what keeps the border from
        // being a circle. Hashed, so the same map grows the same wood every time.
        if (d > r * (0.62 + cellRand(seed, x, y, 55) * 0.70)) continue;
        grid[y][x] = code;
        placed++;
      }
    }
  }
  return grid;
}

/* A road that wanders. A ruled two-pixel line across the middle of every map is
 * the second most obvious tell that the terrain is generated; a biased walk
 * costs nothing and reads as a road someone wore in. Water it crosses becomes a
 * bridge rather than being overwritten. */
export function carvePath(grid, from, to, opts = {}) {
  const { seed = 1, width = 2, code = TERRAIN.PATH, wander = 0.16, leash = 2 } = opts;
  const h = grid.length, w = grid[0].length;
  let x = from.x, y = from.y, step = 0;
  const put = (cx, cy) => {
    if (cx < 1 || cy < 1 || cx >= w - 1 || cy >= h - 1) return;
    const here = grid[cy][cx];
    if (here === TERRAIN.WATER) grid[cy][cx] = TERRAIN.BRIDGE;   // cross it, do not erase it
    else if (here !== TERRAIN.BUILDING && here !== TERRAIN.SHRINE) grid[cy][cx] = code;
  };
  const guard = (Math.abs(to.x - x) + Math.abs(to.y - y)) * 8 + 64;
  while ((x !== to.x || y !== to.y) && step < guard) {
    const horizontal = Math.abs(to.x - x) >= Math.abs(to.y - y);
    // Width is laid across the direction of travel, so a road is wide the way a
    // road is wide rather than square.
    for (let k = 0; k < width; k++) put(horizontal ? x : x + k, horizontal ? y + k : y);
    const dx = Math.sign(to.x - x), dy = Math.sign(to.y - y);
    if (cellRand(seed, x, y, 93 + (step & 31)) < wander) {
      // Sidestep, but on a leash: a road that bends is scenery, a road that
      // rambles is a maze. The offset never exceeds `leash` tiles from the
      // straight line between the two ends.
      const step2 = cellRand(seed, x, y, 94) < 0.5 ? 1 : -1;
      if (horizontal) { if (Math.abs(y + step2 - to.y) <= Math.abs(from.y - to.y) + leash) y += step2; }
      else if (Math.abs(x + step2 - to.x) <= Math.abs(from.x - to.x) + leash) x += step2;
      x = Math.max(2, Math.min(w - 3, x));
      y = Math.max(2, Math.min(h - 3, y));
    } else if (horizontal) x += dx || 1;
    else y += dy || 1;
    step++;
  }
  return grid;
}

/* ---------- scene ---------- */

function groundClass(code) { return GROUND_OF[code] || 'grass'; }

/* Build everything a map needs to draw: per-cell variants, edge descriptors,
 * water depth, cliff roles, cast shadows, ambient occlusion, detail scatter,
 * flora, fire, decoration and lights.
 *
 * Called once per region load. The 60fps loop after that is array lookups and
 * drawImage, which is the only way this stays cheap. */
export function createScene(opts) {
  const {
    regionId = 'region', palette = 'spring', tier = 2, biome = 'grass',
    grid, decorDensity = 0.10, floraDensity = 0.42, detailDensity = 0.26,
    avoid = null,
  } = opts;
  if (!grid || !grid.length) throw new Error('createScene: grid required');
  const h = grid.length, w = grid[0].length;
  const set = terrainSet(regionId, palette, tier, biome);
  const st = set.style;
  const seed = set.seed;
  const blocked = typeof avoid === 'function'
    ? avoid
    : avoid ? (x, y) => avoid.has(`${x},${y}`) : () => false;

  const n = w * h;
  const cls = new Array(n);
  const variant = new Uint8Array(n);
  const depth = new Uint8Array(n);
  const role = new Uint8Array(n);
  const sides = new Uint8Array(n);
  const shadow = new Uint8Array(n);
  const ao = new Uint8Array(n);
  const detail = new Uint8Array(n);
  const crest = new Int16Array(n).fill(-1);
  const shelf = new Int16Array(n).fill(0);
  const crestVar = new Uint8Array(n);
  const edges = new Array(n).fill(null);

  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h) ? null : grid[y][x];

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      cls[i] = groundClass(grid[y][x]);
      variant[i] = Math.floor(cellRand(seed, x, y, 1) * GROUND_VARIANTS);
    }
  }

  // Water depth: distance to the nearest non-water cell, capped at 3. A flat
  // body of one colour is a puddle no matter how large you draw it.
  const queue = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (cls[i] !== 'water') { depth[i] = 0; continue; }
      let shore = false;
      for (const [dx, dy] of [[0, -1], [1, 0], [0, 1], [-1, 0]]) {
        const c = at(x + dx, y + dy);
        if (c === null || groundClass(c) !== 'water') shore = true;
      }
      if (shore) { depth[i] = 0; queue.push(i); } else depth[i] = 255;
    }
  }
  for (let qi = 0; qi < queue.length; qi++) {
    const i = queue[qi];
    const x = i % w, y = (i / w) | 0;
    for (const [dx, dy] of [[0, -1], [1, 0], [0, 1], [-1, 0]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
      const j = ny * w + nx;
      if (cls[j] !== 'water' || depth[j] !== 255) continue;
      depth[j] = Math.min(2, depth[i] + 1);
      queue.push(j);
    }
  }
  for (let i = 0; i < n; i++) if (depth[i] === 255) depth[i] = 2;

  // Cliff roles.
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (cls[i] !== 'cliff') continue;
      const north = at(x, y - 1), south = at(x, y + 1);
      const nCliff = north !== null && groundClass(north) === 'cliff';
      const sCliff = south !== null && groundClass(south) === 'cliff';
      role[i] = sCliff ? CLIFF_TOP : (nCliff ? CLIFF_FACE : CLIFF_CAP);
      const west = at(x - 1, y), east = at(x + 1, y);
      const wCliff = west !== null && groundClass(west) === 'cliff';
      const eCliff = east !== null && groundClass(east) === 'cliff';
      if (role[i] === CLIFF_TOP) {
        let open = 0;
        if (!nCliff) open |= N;
        if (!wCliff) open |= W;
        if (!eCliff) open |= E;
        sides[i] = open;
      } else {
        sides[i] = (wCliff ? 0 : 1) | (eCliff ? 0 : 2);
      }
    }
  }

  const OFFS = [[0, -1, N], [1, -1, NE], [1, 0, E], [1, 1, SE],
                [0, 1, S], [-1, 1, SW], [-1, 0, W], [-1, -1, NW]];

  // What stands up out of the ground, and therefore what the ground has to be
  // occluded by. Cliffs are excluded: a wall gets the longer, harder cast
  // shadow of its own, and adding both would double-darken its foot.
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (cls[i] === 'lava') continue;
      const isCliff = cls[i] === 'cliff';
      const iAmTall = TALL.has(grid[y][x]);
      let aoMask = 0, wallMask = 0;
      for (const [dx, dy, bit] of OFFS) {
        const c = at(x + dx, y + dy);
        if (c === null) continue;
        if (!isCliff && TALL.has(c) && c !== TERRAIN.CLIFF) aoMask |= bit;
        if (!isCliff && c === TERRAIN.CLIFF) wallMask |= bit;
      }
      ao[i] = iAmTall ? 0 : edgeMask(aoMask);
      shadow[i] = edgeMask(wallMask);
    }
  }

  // Edge descriptors: which higher-priority terrains reach into this cell, and
  // from which sides. Reduced to the blob set, then cached per mask.
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const me = cls[i];
      const myP = PRIORITY[me];
      const masks = new Map();
      let landMask = 0;
      for (const [dx, dy, bit] of OFFS) {
        const c = at(x + dx, y + dy);
        const oc = c === null ? me : groundClass(c);
        if ((me === 'water' || me === 'lava') && oc !== me) landMask |= bit;
        if (oc === me || oc === 'cliff') continue;
        if (PRIORITY[oc] <= myP) continue;
        masks.set(oc, (masks.get(oc) || 0) | bit);
      }
      if (masks.size) {
        const list = [...masks.entries()]
          .sort((a, b) => PRIORITY[a[0]] - PRIORITY[b[0]])
          .map(([o, m]) => ({
            cls: o,
            host: me,
            mask: edgeMask(m),
            v: Math.floor(cellRand(seed, x, y, 2) * FRINGE_VARIANTS),
          }))
          .filter(e => e.mask !== 0);
        if (list.length) edges[i] = list;
      }
      if (me === 'water' && depth[i] > 0) {
        let sm = 0;
        for (const [dx, dy, bit] of OFFS) {
          if (bit !== N && bit !== E && bit !== S && bit !== W) continue;
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const j = ny * w + nx;
          if (cls[j] === 'water' && depth[j] < depth[i]) sm |= bit;
        }
        shelf[i] = sm;
      }
      if (landMask) {
        crest[i] = edgeMask(landMask & (N | E | S | W));
        crestVar[i] = Math.floor(cellRand(seed, x, y, 3) * 2);
      }
      // A shore is a beach on the land side and foam on the water side. Running
      // both into the same pixels makes each of them illegible, so the wet sand
      // is added to the LAND tile — outside the ordinary priority rule, because
      // water is the one terrain that marks the ground it does not occupy.
      if (me !== 'water' && me !== 'lava' && me !== 'cliff') {
        let wm = 0;
        for (const [dx, dy, bit] of OFFS) {
          const c = at(x + dx, y + dy);
          if (c !== null && groundClass(c) === 'water') wm |= bit;
        }
        wm = edgeMask(wm);
        if (wm) {
          const shore = { cls: 'shore', host: me, mask: wm,
                          v: Math.floor(cellRand(seed, x, y, 2) * FRINGE_VARIANTS) };
          if (edges[i]) edges[i].push(shore); else edges[i] = [shore];
        }
      }
      // Detail scatter. One hashed lookup per cell at build, one drawImage per
      // decorated cell at draw, and a field stops being four tiles in a trench
      // coat. Skipped where a fringe already owns most of the tile's pixels.
      const wallFace = me === 'cliff' && role[i] !== CLIFF_TOP;
      if (me !== 'water' && me !== 'lava' && !wallFace
          && grid[y][x] !== TERRAIN.BRIDGE) {
        const dr = cellRand(seed, x, y, 26);
        if (dr < detailDensity * (edges[i] ? 0.45 : 1)) {
          detail[i] = 1 + Math.floor(cellRand(seed, x, y, 27) * DETAIL_VARIANTS);
        }
      }
    }
  }

  const layers = { w, h, cls, variant, depth, role, sides, shadow, ao, detail,
                   crest, crestVar, shelf, edges };

  // Object layer: everything that stands on the ground rather than being it.
  const objects = [];
  const consumed = new Set();
  const taken = new Set();
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const code = grid[y][x];
      const i = y * w + x;
      if (consumed.has(i)) continue;
      if (code === TERRAIN.TREE) {
        // Trees planted on exact tile centres read as an orchard. Two pixels of
        // hashed jitter and three canopies is the whole difference.
        objects.push({
          kind: 'tree', x, y,
          ox: Math.floor(cellRand(seed, x, y, 40) * 5) - 2,
          oy: -6 + Math.floor(cellRand(seed, x, y, 41) * 3) - 1,
          sortY: y * TILE + TILE,
          img: set.tree[Math.floor(cellRand(seed, x, y, 4) * set.tree.length)],
        });
      } else if (code === TERRAIN.SHRINE) {
        objects.push({ kind: 'shrine', x, y, ox: -3, oy: -8, sortY: y * TILE + TILE, img: set.shrine });
      } else if (code === TERRAIN.CHEST) {
        objects.push({ kind: 'chest', x, y, ox: -2, oy: 0, sortY: y * TILE + TILE, img: set.chest[0] });
      } else if (code === TERRAIN.BUILDING) {
        // buildMap stamps houses two tiles wide; treat the pair as one structure
        // so the sprite can be 40px and look like somewhere people live.
        const pair = at(x + 1, y) === TERRAIN.BUILDING && !consumed.has(i + 1);
        if (pair) consumed.add(i + 1);
        const v = Math.floor(cellRand(seed, x, y, 5) * BUILD_VARIANTS.length);
        const img = set.building[Math.min(3, tier)][v];
        objects.push({
          kind: 'building', x, y, ox: pair ? 0 : -8, oy: -18,
          sortY: y * TILE + TILE, img, variant: v, tier,
        });
      }
    }
  }

  // Decoration: scattered from a hash, so a region has texture nobody placed.
  const DECOR = decorTable(biome);
  const decor = [];
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const c = cls[i];
      if (c !== 'grass' && c !== 'stone' && c !== 'sand') continue;
      if (grid[y][x] !== TERRAIN.GRASS && grid[y][x] !== TERRAIN.STONE) continue;
      if (blocked(x, y)) continue;
      if (cellRand(seed, x, y, 6) > decorDensity) continue;
      const pick = cellRand(seed, x, y, 7);
      let acc = 0, kind = DECOR[0][0];
      for (const [k, weight] of DECOR) { acc += weight; if (pick <= acc) { kind = k; break; } }
      const bank = set[kind];
      if (!bank) continue;
      const v = Math.floor(cellRand(seed, x, y, 8) * bank.length);
      const img = Array.isArray(bank) ? bank[v] : bank;
      taken.add(i);
      decor.push({
        kind, x, y, variant: v, img,
        ox: Math.floor(cellRand(seed, x, y, 9) * 5) - 2,
        oy: Math.floor(cellRand(seed, x, y, 10) * 3) - 1,
        sortY: y * TILE + TILE,
      });
    }
  }

  // Flora: the swaying overlay, plus anything that is on fire. Tufts and flowers
  // on grass, reeds at the water's edge, torches and banners along the road.
  // Each carries a phase so a field never sways in unison and a colonnade of
  // torches never guts in unison, which is the tell that they are one sprite.
  const flora = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const c = cls[i];
      const code = grid[y][x];
      const walkable = code === TERRAIN.GRASS || code === TERRAIN.STONE || code === TERRAIN.SAND;
      if (!walkable) continue;
      const nearOf = (want) => [[0, -1], [1, 0], [0, 1], [-1, 0]].some(([dx, dy]) => {
        const q = at(x + dx, y + dy);
        return q !== null && groundClass(q) === want;
      });
      const r = cellRand(seed, x, y, 12);

      if (set.fire && !blocked(x, y) && !taken.has(i) && r < 0.055 && nearOf('path')) {
        flora.push({ kind: 'fire', clock: 'flame', x, y, variant: 0, ox: 0, oy: -6,
                     phase: Math.floor(cellRand(seed, x, y, 28) * FLAME_FRAMES) });
        taken.add(i);
        continue;
      }
      if (st.banner && !blocked(x, y) && !taken.has(i) && r >= 0.055 && r < 0.095 && nearOf('path')) {
        flora.push({ kind: 'banner', clock: 'sway', x, y, variant: 0, ox: 2, oy: -8,
                     phase: Math.floor(cellRand(seed, x, y, 11) * SWAY_FRAMES) });
        taken.add(i);
        continue;
      }
      if (c !== 'grass' || code !== TERRAIN.GRASS) continue;
      const bears = BEARING.has(st.surf);
      if (bears && nearOf('water') && r < 0.45) {
        flora.push({ kind: 'reed', clock: 'sway', x, y,
                     variant: Math.floor(cellRand(seed, x, y, 13) * 2),
                     ox: Math.floor(cellRand(seed, x, y, 14) * 8), oy: 4,
                     phase: Math.floor(cellRand(seed, x, y, 15) * SWAY_FRAMES) });
        continue;
      }
      if (r > floraDensity * (bears ? 1 : 0.40)) continue;
      const count = r < floraDensity * 0.35 ? 2 : 1;
      for (let k = 0; k < count; k++) {
        const isFlower = bears && cellRand(seed, x, y, 16 + k) > 0.82;
        flora.push({
          kind: isFlower ? 'flower' : 'tuft', clock: 'sway', x, y,
          variant: Math.floor(cellRand(seed, x, y, 18 + k) * (isFlower ? 5 : 3)),
          ox: Math.floor(cellRand(seed, x, y, 20 + k) * 9),
          oy: Math.floor(cellRand(seed, x, y, 22 + k) * 9),
          phase: Math.floor(cellRand(seed, x, y, 24 + k) * SWAY_FRAMES),
        });
      }
    }
  }

  // Light sources. A flat night tint over a whole screen is the one thing a
  // 16-bit game never does; these are what break it up.
  const lights = [];
  for (const o of objects) {
    if (o.kind === 'building' && tier >= 2 && o.img.windows) {
      for (const [wx, wy] of o.img.windows) {
        lights.push({ x: o.x * TILE + o.ox + wx, y: o.y * TILE + o.oy + wy,
                      r: 18, colour: '255,224,150', flicker: 0.06 });
      }
    } else if (o.kind === 'shrine') {
      lights.push({ x: o.x * TILE + 8, y: o.y * TILE + 2,
                    colour: hexToRgbStr(set.P.accent[3]), r: 22, flicker: 0.18 });
    }
  }
  for (const d of decor) {
    if (d.kind === 'crystal') {
      lights.push({ x: d.x * TILE + 8 + d.ox, y: d.y * TILE + 10 + d.oy,
                    colour: hexToRgbStr(set.P.accent[4]), r: 14, flicker: 0.22 });
    }
  }
  for (const it of flora) {
    if (it.kind !== 'fire') continue;
    lights.push({ x: it.x * TILE + 8, y: it.y * TILE + 4,
                  colour: '255,150,64', r: st.fire === 'pyre' ? 34 : 24, flicker: 0.34 });
  }
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (cls[y * w + x] !== 'lava') continue;
      if ((x + y) % 3) continue;
      lights.push({ x: x * TILE + 8, y: y * TILE + 8, colour: '255,138,42', r: 20, flicker: 0.3 });
    }
  }

  const scene = { regionId, w, h, grid, tier, biome, set, seed, layers,
                  objects, decor, flora, lights };
  warmScene(scene);
  return scene;
}

/* Rasterise every lazily-built tile this particular map will ask for, right now,
 * while the region is loading and nobody is looking.
 *
 * The alternative — and what this file used to do — is to build them on first
 * sight, which means several thousand canvas allocations spread across the first
 * few seconds of walking around. That is not a leak and it does not show up in a
 * steady-state measurement; it shows up as the frame hitching exactly when the
 * player first sees a coastline. */
function warmScene(scene) {
  const { set, layers: L } = scene;
  const n = L.w * L.h;
  for (let i = 0; i < n; i++) {
    const e = L.edges[i];
    if (e) for (let k = 0; k < e.length; k++) set.fringe(e[k].cls, e[k].mask, e[k].v, e[k].host);
    if (L.shelf[i]) set.shelf(L.shelf[i], L.crestVar[i], L.depth[i]);
    if (L.crest[i] > 0) {
      const hot = scene.grid[(i / L.w) | 0][i % L.w] === TERRAIN.LAVA;
      for (let f = 0; f < FOAM_FRAMES; f++) {
        if (hot) set.ember(L.crest[i], L.crestVar[i], f);
        else set.foam(L.crest[i], L.crestVar[i], f);
      }
    }
    if (L.cls[i] === 'cliff') set.cliff(L.role[i], L.sides[i], L.variant[i] % GROUND_VARIANTS);
    if (L.shadow[i]) set.cliffShadow(L.shadow[i]);
    if (L.ao[i]) set.ao(L.ao[i]);
    if (L.detail[i]) set.detail(L.cls[i], L.detail[i] - 1);
  }
  return scene;
}

function hexToRgbStr(hex) {
  const [r, g, b] = parseHex(hex);
  return `${r},${g},${b}`;
}

function decorTable(biome) {
  // Weights sum to 1 per biome; the scatter walks them cumulatively.
  const T = {
    village:    [['bush', 0.40], ['rock', 0.24], ['stump', 0.18], ['mushroom', 0.16], ['bones', 0.02]],
    grass:      [['bush', 0.36], ['rock', 0.30], ['stump', 0.16], ['mushroom', 0.15], ['bones', 0.03]],
    forest:     [['bush', 0.32], ['stump', 0.24], ['mushroom', 0.24], ['rock', 0.14], ['bones', 0.06]],
    deepforest: [['mushroom', 0.30], ['stump', 0.26], ['bush', 0.22], ['crystal', 0.10], ['bones', 0.12]],
    canopy:     [['bush', 0.38], ['stump', 0.22], ['mushroom', 0.24], ['rock', 0.16]],
    swamp:      [['mushroom', 0.32], ['stump', 0.26], ['bush', 0.24], ['bones', 0.18]],
    cave:       [['rock', 0.46], ['crystal', 0.30], ['bones', 0.18], ['mushroom', 0.06]],
    mine:       [['rock', 0.44], ['crystal', 0.34], ['bones', 0.22]],
    mountain:   [['rock', 0.56], ['crystal', 0.16], ['bush', 0.16], ['bones', 0.12]],
    highland:   [['rock', 0.40], ['bush', 0.32], ['stump', 0.16], ['bones', 0.12]],
    citadel:    [['rock', 0.40], ['crystal', 0.24], ['bush', 0.22], ['bones', 0.14]],
    ruins:      [['rock', 0.42], ['bones', 0.26], ['crystal', 0.18], ['bush', 0.14]],
    wastes:     [['bones', 0.40], ['rock', 0.40], ['crystal', 0.20]],
    dungeon:    [['bones', 0.40], ['rock', 0.38], ['crystal', 0.22]],
    tower:      [['crystal', 0.42], ['rock', 0.36], ['bones', 0.22]],
    arena:      [['rock', 0.46], ['bones', 0.30], ['bush', 0.24]],
    castle:     [['bones', 0.36], ['rock', 0.34], ['crystal', 0.30]],
  };
  return T[biome] || T.grass;
}

/* ---------- drawing ---------- */

/* Tile bounds for a camera. Three extra rows top and bottom because trees,
 * buildings and shrines are taller than their tile and must start drawing before
 * their anchor enters the view, and one extra column each side because their
 * cast shadows reach to the right. */
export function viewBounds(scene, camX, camY, viewW, viewH, scale) {
  return {
    x0: Math.max(0, Math.floor(camX / TILE) - 2),
    y0: Math.max(0, Math.floor(camY / TILE) - 3),
    x1: Math.min(scene.w, Math.ceil((camX + viewW / scale) / TILE) + 2),
    y1: Math.min(scene.h, Math.ceil((camY + viewH / scale) / TILE) + 3),
  };
}

/* The shared clock. Every animated thing in the world reads its frame from this
 * one function, which is why the water, the foam, the grass, the banners and
 * the torches are all in step with each other and with the music instead of
 * each keeping its own private time.
 *
 * The modulo is the floored one, not JavaScript's remainder. `-5 % 6` is -5,
 * which indexes a frame array to `undefined`, which draws nothing at all — so a
 * caller that ever hands this a negative or non-finite clock (a paused scene
 * rewinding, a cutscene seeking, a test) silently loses every animated tile. */
function wrap(n, m) {
  const v = Math.floor(n) % m;
  return v < 0 ? v + m : v;
}

export function frames(time) {
  const t = Number.isFinite(time) ? time : 0;
  return {
    water: wrap(t * 5, WATER_FRAMES),
    foam: wrap(t * 4.5, FOAM_FRAMES),
    sway: wrap(t * 2.6, SWAY_FRAMES * 3),
    flame: wrap(t * 11, FLAME_FRAMES),
  };
}

/* Ground pass, in the order depth is built up:
 *   1. the surface itself
 *   2. the shelf, where the bottom of a lake steps
 *   3. the detail scatter this cell happens to have been dealt
 *   4. the fringes of whatever reaches into it, with their lit and shadowed lips
 *   5. the animated crest — foam against land, ember against rock
 *   6. the occlusion that trees, houses and shrines cast onto it
 *   7. the long shadow a cliff throws across it
 *
 * ctx is expected to be in world space already — scaled and translated by the
 * camera, exactly as overworld.js draw() already does. */
export function drawGround(ctx, scene, view, time) {
  const { set, layers: L, grid, w } = scene;
  const f = frames(time);
  for (let y = view.y0; y < view.y1; y++) {
    for (let x = view.x0; x < view.x1; x++) {
      const i = y * w + x;
      const code = grid[y][x];
      const wx = x * TILE, wy = y * TILE;
      const sx = (x & 3) * TILE, sy = (y & 3) * TILE;
      let img;
      switch (code) {
        case TERRAIN.WATER:
          ctx.drawImage(set.water[L.depth[i]][f.water], sx, sy, TILE, TILE, wx, wy, TILE, TILE);
          img = null; break;
        case TERRAIN.LAVA:
          ctx.drawImage(set.lava[f.water], sx, sy, TILE, TILE, wx, wy, TILE, TILE);
          img = null; break;
        case TERRAIN.BRIDGE: {
          ctx.drawImage(set.water[L.depth[i]][f.water], sx, sy, TILE, TILE, wx, wy, TILE, TILE);
          const vertical = groundClassAt(scene, x, y - 1) === 'water'
                        || groundClassAt(scene, x, y + 1) === 'water';
          img = set.bridge[vertical ? 1 : 0];
          break;
        }
        case TERRAIN.PATH:
          img = set.path[L.variant[i] % set.path.length]; break;
        case TERRAIN.STONE:
          img = set.stone[L.variant[i] % set.stone.length]; break;
        case TERRAIN.SAND:
          img = set.sand[L.variant[i] % set.sand.length]; break;
        case TERRAIN.CLIFF:
          img = set.cliff(L.role[i], L.sides[i], L.variant[i] % GROUND_VARIANTS); break;
        default:
          img = set.ground[L.variant[i] % set.ground.length];
      }
      if (img) ctx.drawImage(img, wx, wy);
      if (L.shelf[i]) ctx.drawImage(set.shelf(L.shelf[i], L.crestVar[i], L.depth[i]), wx, wy);
      if (L.detail[i]) ctx.drawImage(set.detail(L.cls[i], L.detail[i] - 1), wx, wy);

      const e = L.edges[i];
      if (e) for (let k = 0; k < e.length; k++) {
        ctx.drawImage(set.fringe(e[k].cls, e[k].mask, e[k].v, e[k].host), wx, wy);
      }
      const cm = L.crest[i];
      if (cm > 0) {
        const hot = code === TERRAIN.LAVA;
        ctx.drawImage(hot ? set.ember(cm, L.crestVar[i], f.foam)
                          : set.foam(cm, L.crestVar[i], f.foam), wx, wy);
      }
      if (L.ao[i]) ctx.drawImage(set.ao(L.ao[i]), wx, wy);
      if (L.shadow[i]) ctx.drawImage(set.cliffShadow(L.shadow[i]), wx, wy);
    }
  }
}

function groundClassAt(scene, x, y) {
  if (x < 0 || y < 0 || x >= scene.w || y >= scene.h) return null;
  return scene.layers.cls[y * scene.w + x];
}

/* Flora pass: sways, burns, sits flat on the ground, needs no sorting. Draw it
 * straight after drawGround and before anything with a shadow. */
export function drawFlora(ctx, scene, view, time) {
  const { set, flora } = scene;
  const f = frames(time);
  for (let k = 0; k < flora.length; k++) {
    const it = flora[k];
    if (it.x < view.x0 || it.x >= view.x1 || it.y < view.y0 || it.y >= view.y1) continue;
    const kindBank = set[it.kind];
    if (!kindBank) continue;
    const bank = kindBank[it.variant % kindBank.length];
    if (!bank || !bank.length) continue;
    const img = bank[(f[it.clock || 'sway'] + it.phase) % bank.length];
    if (img) ctx.drawImage(img, it.x * TILE + it.ox, it.y * TILE + it.oy);
  }
}

/* Everything that should be y-sorted against the hero, the NPCs and the enemy
 * markers. Returns plain descriptors so the caller can merge its own sprites in
 * and sort once — walking behind a tree is the whole point. */
export function collectObjects(scene, view, out = []) {
  const push = (o) => {
    if (o.x < view.x0 - 2 || o.x >= view.x1 + 2) return;
    if (o.y < view.y0 - 2 || o.y >= view.y1 + 2) return;
    out.push(o);
  };
  for (let i = 0; i < scene.objects.length; i++) push(scene.objects[i]);
  for (let i = 0; i < scene.decor.length; i++) push(scene.decor[i]);
  return out;
}

/* Draw a merged, sorted list. Entries need { img, x, y, ox, oy, sortY }; x and y
 * are tile coordinates, ox/oy are pixel offsets, sortY is the world-pixel row
 * the sprite's feet stand on. */
export function drawSorted(ctx, list) {
  list.sort((a, b) => a.sortY - b.sortY || a.x - b.x);
  for (let i = 0; i < list.length; i++) {
    const o = list[i];
    // An entry may draw itself — that is how the hero, NPCs and enemy markers
    // join the same sort without this module knowing anything about them.
    if (o.draw) { o.draw(ctx, o); continue; }
    if (!o.img) continue;
    ctx.drawImage(o.img, o.x * TILE + (o.ox || 0), o.y * TILE + (o.oy || 0));
  }
}

/* Convenience for callers that do not want to merge their own sprites yet. */
export function drawObjects(ctx, scene, view) {
  drawSorted(ctx, collectObjects(scene, view, []));
}

/* Point lights, composited before the day/night tint. `intensity` is the night
 * factor the caller already computes — 0 in daylight, ~1 after dark. */
export function drawLights(ctx, scene, view, time, intensity = 1) {
  if (intensity <= 0.01) return;
  const x0 = view.x0 * TILE, x1 = view.x1 * TILE;
  const y0 = view.y0 * TILE, y1 = view.y1 * TILE;
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < scene.lights.length; i++) {
    const l = scene.lights[i];
    if (l.x < x0 || l.x > x1 || l.y < y0 || l.y > y1) continue;
    // A torch that does not move is a lamp. One pixel of flicker is enough.
    const clock = Number.isFinite(time) ? time : 0;
    const wob = 1 + Math.sin(clock * 6.3 + l.x * 0.7 + l.y * 0.3) * (l.flicker || 0);
    const r = Math.max(1, l.r * wob);
    const g = ctx.createRadialGradient(l.x, l.y, 0, l.x, l.y, r);
    g.addColorStop(0, `rgba(${l.colour},${0.26 * intensity})`);
    g.addColorStop(0.45, `rgba(${l.colour},${0.09 * intensity})`);
    g.addColorStop(1, `rgba(${l.colour},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(l.x - r, l.y - r, r * 2, r * 2);
  }
  ctx.restore();
}

/* Solidity, so the caller does not have to keep its own table in sync with the
 * codes this module understands. BRIDGE is walkable water. */
const SOLID_CODES = new Set([TERRAIN.WATER, TERRAIN.TREE, TERRAIN.CLIFF,
                             TERRAIN.BUILDING, TERRAIN.LAVA]);
export function isSolid(code) { return SOLID_CODES.has(code); }

/* What a built scene actually cost, for the verify harness. */
export function terrainStats(scene) {
  const L = scene && scene.layers;
  if (!L) return null;
  let detail = 0, ao = 0, shadow = 0, fringed = 0;
  for (let i = 0; i < L.w * L.h; i++) {
    if (L.detail[i]) detail++;
    if (L.ao[i]) ao++;
    if (L.shadow[i]) shadow++;
    if (L.edges[i]) fringed++;
  }
  return { cells: L.w * L.h, detail, ao, shadow, fringed,
           flora: scene.flora.length, decor: scene.decor.length,
           objects: scene.objects.length, lights: scene.lights.length,
           cache: scene.set.stats() };
}

export { TILE, CLIFF_TOP, CLIFF_FACE, CLIFF_CAP,
         WATER_FRAMES, FOAM_FRAMES, SWAY_FRAMES, FLAME_FRAMES };
