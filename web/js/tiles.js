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
 * Three ideas carry the file:
 *   1. Object tiles do not bake ground. A tree is a transparent sprite standing
 *      on grass, not a 16x16 square of almost-the-right green. That is what stops
 *      the world reading as tiles.
 *   2. Colour moves through hue, not just brightness. ramp() shifts shadows
 *      toward blue-violet and lights toward yellow, which is the difference
 *      between pixel art and tinted plastic.
 *   3. Variant selection is hashed, never linear. (x*7+y*3)%4 is a diagonal
 *      stripe wearing a costume.
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

const WATER_FRAMES = 6;
const FOAM_FRAMES = 4;
const SWAY_FRAMES = 4;
const FRINGE_VARIANTS = 3;

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

/* Recolour toward a hue while keeping the source's value structure. Used to pull
 * a water colour out of a palette that has no water in it. */
function reHue(hex, targetHue, amt, satFloor, lightness) {
  const [r, g, b] = parseHex(hex);
  const [h, s, l] = rgbToHsl(r, g, b);
  return toHex(...hslToRgb(towardHue(h, targetHue, amt), Math.max(s, satFloor),
                           lightness == null ? l : lightness));
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

/* A per-side thickness profile so a coastline is not a ruler. Depends on the
 * mask and a small variant index, and the variant is chosen per world cell, so
 * the same mask does not repeat identically along a straight shore. */
function profile(seed, mask, side, variant) {
  const out = new Array(TILE);
  for (let i = 0; i < TILE; i++) {
    const r = cellRand(seed, i, side * 131 + mask * 7 + variant * 977, 0x5e);
    out[i] = r < 0.30 ? -1 : r > 0.74 ? 1 : 0;
  }
  return out;
}

/* ---------- ground tiles ---------- */

function grassTile(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const R = P.ground, R2 = P.ground2;
  px(ctx, 0, 0, TILE, TILE, R[2]);
  const rand = rng(seed + variant * 7919);
  // Broad, low-contrast patches keep a field from reading as flat colour without
  // introducing a second tone strong enough to show the tile grid.
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const n = cellRand(seed + variant * 31, x, y, 3);
      if (n > 0.86) px(ctx, x, y, 1, 1, R[3]);
      else if (n < 0.10) px(ctx, x, y, 1, 1, R[1]);
      else if (variant >= 2 && n > 0.62 && bayer(x, y) < 0.42) px(ctx, x, y, 1, 1, R2[2]);
    }
  }
  // Blades: two pixels up, a lit tip, a shadow at the foot. Static; the swaying
  // ones live on the flora layer where they can be animated cheaply.
  const blades = 2 + Math.floor(rand() * 3);
  for (let i = 0; i < blades; i++) {
    const x = 1 + Math.floor(rand() * (TILE - 2));
    const y = 2 + Math.floor(rand() * (TILE - 5));
    px(ctx, x, y + 1, 1, 2, R[1]);
    px(ctx, x, y, 1, 1, R[3]);
    if (rand() < 0.5) px(ctx, x + 1, y + 2, 1, 1, R[1]);
  }
  return canvas;
}

function pathTile(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const D = P.dirt;
  px(ctx, 0, 0, TILE, TILE, D[2]);
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const n = cellRand(seed + variant * 53, x, y, 5);
      if (n > 0.96) px(ctx, x, y, 1, 1, D[3]);
      else if (n < 0.26) px(ctx, x, y, 1, 1, D[1]);
    }
  }
  // One cart rut, and only on two variants in three. Ruts on every tile at the
  // same height is corduroy, not a road.
  const rand = rng(seed + 311 + variant * 13);
  if (variant !== 1) {
    const ry = 2 + variant * 5 + Math.floor(rand() * 3);
    for (let x = 0; x < TILE; x++) {
      if (cellRand(seed, x, ry + variant, 9) < 0.34) continue;
      px(ctx, x, ry, 1, 1, D[1]);
    }
  }
  // Pebbles: lit on top, shadowed underneath, so the surface has a light source.
  for (let i = 0; i < 3; i++) {
    const x = 1 + Math.floor(rand() * (TILE - 3));
    const y = 1 + Math.floor(rand() * (TILE - 3));
    px(ctx, x, y, 2, 1, D[3]);
    px(ctx, x, y + 1, 2, 1, D[0]);
  }
  return canvas;
}

function stoneTile(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const Rk = P.rock;
  px(ctx, 0, 0, TILE, TILE, Rk[2]);
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const n = cellRand(seed + variant * 17, x, y, 11);
      if (n > 0.90) px(ctx, x, y, 1, 1, Rk[3]);
      else if (n < 0.12) px(ctx, x, y, 1, 1, Rk[1]);
    }
  }
  // Flagstones: two courses, offset per variant so a paved floor does not grid.
  const off = variant % 2 ? 8 : 3;
  const seam = (x, y, w, h) => {
    px(ctx, x, y, w, 1, Rk[4]);            // lit top lip
    px(ctx, x, y + h - 1, w, 1, Rk[0]);    // mortar shadow
  };
  seam(0, 0, TILE, 8);
  seam(0, 8, TILE, 8);
  px(ctx, off, 0, 1, 8, Rk[0]);
  px(ctx, (off + 9) % TILE, 8, 1, 8, Rk[0]);
  return canvas;
}

function sandTile(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const Sd = P.sand;
  px(ctx, 0, 0, TILE, TILE, Sd[2]);
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const n = cellRand(seed + variant * 91, x, y, 13);
      if (n > 0.88) px(ctx, x, y, 1, 1, Sd[3]);
      else if (n < 0.12) px(ctx, x, y, 1, 1, Sd[1]);
    }
  }
  return canvas;
}

/* Water. Depth 0 is the shallow shelf by the shore, 3 is open water.
 *
 * The wave field uses integer frequencies over the 16px tile and an integer
 * period in `frame`, so it tiles seamlessly in x and y AND loops in time. A sine
 * in raw pixel coordinates, which is what the old tile did, produces a visible
 * seam at every tile boundary. */
function waterSheet(P, seed, depth, frame) {
  const S = TILE * 4;
  const { canvas, ctx } = make(S, S);
  const Wt = P.water;
  const t = frame / WATER_FRAMES;
  // Depth is a shelf, the way 16-bit water always was, but the shelves sit close
  // together so the lake reads as one body of water rather than four rings.
  const body = [Wt[3], mixHex(Wt[2], Wt[3], 0.35), Wt[2], Wt[1]][depth];
  const hi = depth >= 2 ? Wt[3] : Wt[4];
  const lo = depth >= 2 ? Wt[1] : mixHex(Wt[1], Wt[2], 0.5);
  px(ctx, 0, 0, S, S, body);
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const u = x / S, v = y / S;
      const w = Math.sin(2 * Math.PI * (2 * u + 3 * v - t)) * 0.50
              + Math.sin(2 * Math.PI * (5 * u - 2 * v + t * 2)) * 0.30
              + Math.sin(2 * Math.PI * (3 * u + 7 * v + t)) * 0.20;
      if (w > 0.62) px(ctx, x, y, 1, 1, hi);
      else if (w < -0.70) px(ctx, x, y, 1, 1, lo);
    }
  }
  // Caustics only on the shelf: light reaching the bottom is what tells the eye
  // this edge is shallow and that one is not.
  if (depth <= 1) {
    for (let i = 0; i < (depth === 0 ? 26 : 14); i++) {
      const x = Math.floor(cellRand(seed, i, depth, 21) * S);
      const y = Math.floor(cellRand(seed, i, depth, 22) * S);
      px(ctx, (x + Math.floor(t * S)) % S, y, 2, 1, Wt[4]);
    }
  }
  return canvas;
}

function lavaSheet(seed, frame) {
  const S = TILE * 4;
  const { canvas, ctx } = make(S, S);
  const crust = '#4a1208', warm = '#8f2a12', hot = '#d2451a', bright = '#ff8a2a', white = '#ffd97a';
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
  return canvas;
}

/* Bridge planks, drawn over water where a road crosses it. */
function bridgeTile(P, seed, vertical) {
  const { canvas, ctx } = make(TILE, TILE);
  const D = P.dirt;
  const plank = mixHex(D[2], '#6a4a2a', 0.5);
  const Pl = ramp(plank);
  if (vertical) {
    px(ctx, 1, 0, TILE - 2, TILE, Pl[2]);
    for (let y = 0; y < TILE; y += 4) px(ctx, 1, y, TILE - 2, 1, Pl[1]);
    px(ctx, 1, 0, 1, TILE, Pl[3]);
    px(ctx, TILE - 2, 0, 1, TILE, Pl[0]);
  } else {
    px(ctx, 0, 1, TILE, TILE - 2, Pl[2]);
    for (let x = 0; x < TILE; x += 4) px(ctx, x, 1, 1, TILE - 2, Pl[1]);
    px(ctx, 0, 1, TILE, 1, Pl[3]);
    px(ctx, 0, TILE - 2, TILE, 1, Pl[0]);
  }
  return canvas;
}

/* ---------- cliffs ---------- */
/* Three roles. TOP is plateau you look down at. FACE is wall you look at. CAP is
 * a one-tile-high ridge: a strip of plateau above a short face. Elevation reads
 * because the face has vertical striations and the top does not. */
const CLIFF_TOP = 1, CLIFF_FACE = 2, CLIFF_CAP = 3;

function cliffTopTile(P, seed, variant, openMask) {
  const { canvas, ctx } = make(TILE, TILE);
  const Rk = P.rock;
  // The top faces the sky, so it is the brightest rock in the region. All of the
  // elevation read comes from this being well clear of the face's value.
  px(ctx, 0, 0, TILE, TILE, Rk[3]);
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const n = cellRand(seed + variant * 7, x, y, 31);
      if (n > 0.88) px(ctx, x, y, 1, 1, Rk[4]);
      else if (n < 0.14) px(ctx, x, y, 1, 1, Rk[2]);
    }
  }
  // Slabs, so the plateau has structure at a distance.
  const rand = rng(seed + variant * 401);
  for (let i = 0; i < 3; i++) {
    const x = Math.floor(rand() * 11), y = Math.floor(rand() * 11);
    const w = 3 + Math.floor(rand() * 4), h = 2 + Math.floor(rand() * 3);
    px(ctx, x, y, w, h, Rk[rand() < 0.5 ? 4 : 2]);
    px(ctx, x, y, w, 1, Rk[4]);
  }
  // Rim light on every open side. This is the edge of the drop, and it is the
  // only thing that says "you are looking at the top of something".
  if (openMask & N) { px(ctx, 0, 0, TILE, 2, Rk[4]); px(ctx, 0, 2, TILE, 1, Rk[3]); }
  if (openMask & W) px(ctx, 0, 0, 1, TILE, Rk[4]);
  if (openMask & E) px(ctx, TILE - 1, 0, 1, TILE, Rk[1]);
  return canvas;
}

function cliffFaceTile(P, seed, variant, sideMask, capHeight) {
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
  px(ctx, 0, faceTop, TILE, TILE - faceTop, Rk[1]);
  // Vertical striation: columns of alternating value with jagged breaks. The
  // grain has to run down the wall or the face reads as more floor.
  for (let x = 0; x < TILE; x++) {
    const c = cellRand(seed + variant * 29, x, 0, 43);
    const shade = c > 0.76 ? Rk[1] : c < 0.34 ? Rk[0] : mixHex(Rk[0], Rk[1], 0.5);
    px(ctx, x, faceTop, 1, TILE - faceTop, shade);
    const brk = faceTop + 3 + Math.floor(cellRand(seed, x, 1, 44) * (TILE - faceTop - 4));
    px(ctx, x, brk, 1, 1 + (c > 0.7 ? 1 : 0), Rk[0]);
  }
  // The lip catches the same light the plateau does; below it the wall drops
  // two full ramp steps. That gap is the elevation.
  px(ctx, 0, faceTop, TILE, 1, Rk[2]);
  if (top > 0) px(ctx, 0, faceTop, TILE, 1, Rk[0]);  // the lip's own shadow
  // Corner returns: an unbroken wall is a flat, so the open sides get a bevel.
  if (sideMask & 1) { px(ctx, 0, faceTop, 1, TILE - faceTop, Rk[2]); }
  if (sideMask & 2) { px(ctx, TILE - 1, faceTop, 1, TILE - faceTop, Rk[0]); }
  px(ctx, 0, TILE - 2, TILE, 2, Rk[0]);  // where the wall meets the ground
  return canvas;
}

/* The dark a cliff throws onto the tile below it. Baked, because a translucent
 * fill per tile per frame is not worth the state changes. */
function cliffShadowTile() {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = 'rgba(10,8,22,0.42)';
  ctx.fillRect(0, 0, TILE, 2);
  ctx.fillStyle = 'rgba(10,8,22,0.26)';
  ctx.fillRect(0, 2, TILE, 2);
  ctx.fillStyle = 'rgba(10,8,22,0.12)';
  for (let x = 0; x < TILE; x++) if (bayer(x, 4) < 0.5) ctx.fillRect(x, 4, 1, 1);
  return canvas;
}

/* ---------- edge fringes ---------- */
/* The overlay terrain reaching into this tile. `mask` is already reduced. */
function fringeTile(P, cls, mask, variant, seed, host) {
  const { canvas, ctx } = make(TILE, TILE);
  const R = cls === 'path' ? P.dirt
          : cls === 'stone' ? P.rock
          : cls === 'sand' ? P.sand
          : P.ground;
  const band = cls === 'sand' ? 3 : cls === 'path' ? 3 : 4;
  // Rock does not lap onto grass, it falls onto it: the stone fringe scatters
  // into gravel instead of laying a band.
  const scatter = cls === 'stone' && host !== 'lava';
  const body = R[2], lip = R[1];

  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    const prof = profile(seed, mask, dir, variant);
    for (let i = 0; i < TILE; i++) {
      const d = Math.max(2, band + prof[i]);
      for (let k = 0; k < d; k++) {
        const solid = k < d - 1;
        // Only the outermost pixel dithers into the host terrain. Dithering two
        // rows leaves a dotted line where a band was wanted.
        if (!solid && bayer(i, k + dir * 2) > 0.55) continue;
        if (scatter && cellRand(seed, i, k * 13 + dir * 7 + variant, 57) > 0.42) continue;
        let x, y;
        if (dir === 0) { x = i; y = k; }
        else if (dir === 1) { x = TILE - 1 - k; y = i; }
        else if (dir === 2) { x = i; y = TILE - 1 - k; }
        else { x = k; y = i; }
        px(ctx, x, y, 1, 1, solid ? body : lip);
      }
    }
  };
  side(N, 0); side(E, 1); side(S, 2); side(W, 3);

  // Diagonal-only contact: a small tongue at the corner, nothing more.
  const corner = (bit, cx, cy) => {
    if (!(mask & bit)) return;
    px(ctx, cx, cy, 2, 2, body);
    px(ctx, cx + (cx ? -1 : 2), cy, 1, 1, lip);
    px(ctx, cx, cy + (cy ? -1 : 2), 1, 1, lip);
  };
  if (!(mask & N) && !(mask & E)) corner(NE, TILE - 2, 0);
  if (!(mask & S) && !(mask & E)) corner(SE, TILE - 2, TILE - 2);
  if (!(mask & S) && !(mask & W)) corner(SW, 0, TILE - 2);
  if (!(mask & N) && !(mask & W)) corner(NW, 0, 0);
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
  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    for (let i = 0; i < TILE; i++) {
      for (let k = 0; k < 4; k++) {
        // Hashed, not ordered: a Bayer gradient here reads as a decorative
        // ric-rac border rather than as the bottom falling away.
        if (cellRand(seed, i, k * 9 + dir * 3 + variant * 51, 63) > cover[k]) continue;
        let x, y;
        if (dir === 0) { x = i; y = k; }
        else if (dir === 1) { x = TILE - 1 - k; y = i; }
        else if (dir === 2) { x = i; y = TILE - 1 - k; }
        else { x = k; y = i; }
        px(ctx, x, y, 1, 1, shallower);
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
  const crest = Wt[4], spray = Wt[3];
  const phase = frame / FOAM_FRAMES;
  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    for (let i = 0; i < TILE; i++) {
      // Where the crest sits this frame, along the length of the edge.
      const swell = Math.sin(2 * Math.PI * (i / TILE + phase)) * 0.5 + 0.5;
      const reach = 1 + Math.round(swell * 2);
      for (let k = 0; k < reach; k++) {
        const jitter = cellRand(seed, i, k * 7 + dir * 13 + variant * 101 + frame * 31, 61);
        // A crest that runs the whole edge is a white outline. Breaking it in
        // the troughs is what makes it read as water moving against land.
        if (k === 0 && swell < 0.34) continue;
        if (k === reach - 1 && jitter > 0.5) continue;
        let x, y;
        if (dir === 0) { x = i; y = k; }
        else if (dir === 1) { x = TILE - 1 - k; y = i; }
        else if (dir === 2) { x = i; y = TILE - 1 - k; }
        else { x = k; y = i; }
        px(ctx, x, y, 1, 1, k === 0 ? crest : spray);
      }
      // Spray thrown clear of the crest, one pixel, sometimes.
      if (swell > 0.8 && cellRand(seed, i, frame + variant * 17, 62) > 0.62) {
        const k = reach + 1;
        let x, y;
        if (dir === 0) { x = i; y = k; }
        else if (dir === 1) { x = TILE - 1 - k; y = i; }
        else if (dir === 2) { x = i; y = TILE - 1 - k; }
        else { x = k; y = i; }
        if (x >= 0 && y >= 0 && x < TILE && y < TILE) px(ctx, x, y, 1, 1, spray);
      }
    }
  };
  side(N, 0); side(E, 1); side(S, 2); side(W, 3);
  return canvas;
}

/* The same shape, in heat: lava glows where it meets rock. */
function emberTile(mask, variant, frame, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const phase = frame / FOAM_FRAMES;
  const side = (bit, dir) => {
    if (!(mask & bit)) return;
    for (let i = 0; i < TILE; i++) {
      const swell = Math.sin(2 * Math.PI * (i / TILE * 2 - phase)) * 0.5 + 0.5;
      const reach = 1 + Math.round(swell * 2);
      for (let k = 0; k < reach; k++) {
        if (cellRand(seed, i, k * 5 + dir * 11 + variant * 31, 71) > 0.86) continue;
        let x, y;
        if (dir === 0) { x = i; y = k; }
        else if (dir === 1) { x = TILE - 1 - k; y = i; }
        else if (dir === 2) { x = i; y = TILE - 1 - k; }
        else { x = k; y = i; }
        px(ctx, x, y, 1, 1, k === 0 ? '#ffd97a' : '#ff8a2a');
      }
    }
  };
  side(N, 0); side(E, 1); side(S, 2); side(W, 3);
  return canvas;
}

/* ---------- object sprites (transparent ground) ---------- */

function ellipseShadow(ctx, cx, cy, rx, ry, alpha = 0.3) {
  ctx.save();
  ctx.fillStyle = `rgba(8,6,18,${alpha})`;
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function treeSprite(P, seed, variant, pine) {
  const H = 24;
  const { canvas, ctx } = make(TILE, H);
  const F = P.foliage, Bk = P.bark;
  const rand = rng(seed + variant * 613);
  ellipseShadow(ctx, 8, H - 3, 5, 2);
  if (pine) {
    px(ctx, 7, H - 9, 2, 8, Bk[1]);
    px(ctx, 7, H - 9, 1, 8, Bk[2]);
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
      px(ctx, 8 - wide, top + 3, wide * 2, 1, F[0]);
    }
    px(ctx, 7, 0, 2, 3, F[3]);
  } else {
    px(ctx, 7, H - 10, 3, 9, Bk[1]);
    px(ctx, 7, H - 10, 1, 9, Bk[2]);
    px(ctx, 9, H - 10, 1, 9, Bk[0]);
    // Canopy: clusters, lit from the upper left, dark on the underside.
    for (let i = 0; i < 54; i++) {
      const a = rand() * Math.PI * 2, r = Math.sqrt(rand());
      const cx = 8 + Math.round(Math.cos(a) * r * 7.5);
      const cy = 8 + Math.round(Math.sin(a) * r * 6.8);
      if (cy > 15) continue;
      const lit = (cx - 8) + (cy - 8) < -3;
      const dark = (cx - 8) + (cy - 8) > 4;
      px(ctx, cx, cy, 2, 2, lit ? F[3] : dark ? F[1] : F[2]);
    }
    for (let i = 0; i < 5; i++) {
      const x = 3 + Math.floor(rand() * 9), y = 2 + Math.floor(rand() * 5);
      px(ctx, x, y, 1, 1, F[4]);
    }
    px(ctx, 4, 13, 8, 2, F[0]);   // the shaded underside of the crown
  }
  return canvas;
}

function bushSprite(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const F = P.foliage;
  const rand = rng(seed + variant * 71);
  ellipseShadow(ctx, 8, 14, 5, 2, 0.26);
  for (let i = 0; i < 18; i++) {
    const cx = 8 + Math.round((rand() - 0.5) * 10);
    const cy = 10 + Math.round((rand() - 0.5) * 7);
    if (cy > 13 || cy < 4) continue;
    px(ctx, cx, cy, 2, 2, cx + cy < 15 ? F[3] : F[1]);
  }
  px(ctx, 4, 13, 8, 1, F[0]);
  if (variant % 3 === 0) {
    px(ctx, 5, 7, 1, 1, P.accent[3]);
    px(ctx, 10, 9, 1, 1, P.accent[3]);
  }
  return canvas;
}

function rockSprite(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const Rk = P.rock;
  const w = 6 + (variant % 3) * 2;
  const h = 4 + (variant % 2) * 2;
  const x0 = 8 - (w >> 1), y0 = 14 - h;
  ellipseShadow(ctx, 8, 14, w / 2 + 1, 2, 0.3);
  px(ctx, x0, y0 + 1, w, h - 1, Rk[1]);
  px(ctx, x0 + 1, y0, w - 2, 1, Rk[2]);
  px(ctx, x0 + 1, y0, Math.max(1, w - 4), 1, Rk[3]);
  px(ctx, x0, y0 + h - 1, w, 1, Rk[0]);
  px(ctx, x0 + w - 2, y0 + 1, 1, h - 2, Rk[0]);
  return canvas;
}

function stumpSprite(P, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const Bk = P.bark;
  ellipseShadow(ctx, 8, 14, 5, 2, 0.28);
  px(ctx, 5, 9, 6, 5, Bk[1]);
  px(ctx, 5, 8, 6, 2, Bk[2]);
  px(ctx, 6, 8, 4, 1, Bk[3]);
  px(ctx, 7, 8, 2, 1, Bk[1]);      // the cut rings
  px(ctx, 5, 13, 6, 1, Bk[0]);
  px(ctx, 10, 9, 1, 4, Bk[0]);
  return canvas;
}

function crystalSprite(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const A = P.accent;
  ellipseShadow(ctx, 8, 14, 4, 2, 0.24);
  const h = 7 + (variant % 3);
  for (let i = 0; i < h; i++) {
    const w = Math.max(1, 4 - Math.floor(i / 2));
    px(ctx, 8 - (w >> 1), 13 - i, w, 1, i > h - 3 ? A[4] : A[2]);
  }
  px(ctx, 7, 13 - h + 2, 1, h - 3, A[4]);
  px(ctx, 9, 10, 1, 3, A[1]);
  if (variant % 2) {
    for (let i = 0; i < 4; i++) px(ctx, 11, 13 - i, 1, 1, i > 2 ? A[4] : A[2]);
  }
  return canvas;
}

function bonesSprite(P, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const b = '#d8d2c0', d = '#8a8472';
  ellipseShadow(ctx, 8, 13, 5, 1, 0.2);
  px(ctx, 3, 11, 8, 1, b);
  px(ctx, 3, 12, 8, 1, d);
  px(ctx, 2, 10, 2, 2, b);
  px(ctx, 10, 10, 2, 2, b);
  px(ctx, 6, 7, 4, 4, b);
  px(ctx, 6, 10, 4, 1, d);
  px(ctx, 7, 8, 1, 1, '#2a2620');
  px(ctx, 9, 8, 1, 1, '#2a2620');
  return canvas;
}

function mushroomSprite(P, seed, variant) {
  const { canvas, ctx } = make(TILE, TILE);
  const cap = variant % 2 ? '#c45a4a' : '#8f6ad6';
  const C = ramp(cap);
  ellipseShadow(ctx, 8, 14, 3, 1, 0.22);
  px(ctx, 7, 10, 2, 4, '#e8dcc0');
  px(ctx, 7, 10, 1, 4, '#c0b498');
  px(ctx, 5, 8, 6, 2, C[2]);
  px(ctx, 6, 7, 4, 1, C[3]);
  px(ctx, 5, 9, 6, 1, C[0]);
  px(ctx, 6, 8, 1, 1, C[4]);
  return canvas;
}

function bannerSprite(P, seed, sway) {
  const { canvas, ctx } = make(TILE, 22);
  const A = P.accent, Bk = P.bark;
  px(ctx, 7, 4, 1, 18, Bk[1]);
  const lean = sway;
  for (let y = 0; y < 11; y++) {
    const x = 8 + Math.round(Math.sin((y / 11) * Math.PI) * lean);
    px(ctx, x, 5 + y, 5, 1, y % 4 === 0 ? A[1] : A[2]);
    px(ctx, x, 5 + y, 1, 1, A[3]);
  }
  px(ctx, 6, 3, 3, 1, A[4]);
  return canvas;
}

function shrineSprite(P, seed) {
  const { canvas, ctx } = make(TILE, 24);
  const Rk = P.rock, A = P.accent;
  ellipseShadow(ctx, 8, 22, 6, 2, 0.3);
  px(ctx, 3, 20, 10, 2, Rk[1]);
  px(ctx, 3, 20, 10, 1, Rk[2]);
  px(ctx, 4, 7, 8, 13, Rk[2]);
  px(ctx, 4, 7, 1, 13, Rk[3]);
  px(ctx, 11, 7, 1, 13, Rk[0]);
  for (let i = 0; i < 4; i++) px(ctx, 5 + i * 2, 12, 1, 6, Rk[1]);
  px(ctx, 3, 5, 10, 3, Rk[1]);
  px(ctx, 3, 5, 10, 1, Rk[3]);
  px(ctx, 6, 8, 4, 4, A[1]);
  px(ctx, 7, 9, 2, 2, A[4]);
  px(ctx, 6, 2, 4, 3, A[3]);      // the floating sigil
  px(ctx, 7, 1, 2, 1, A[4]);
  return canvas;
}

function chestSprite(P, seed, open) {
  const { canvas, ctx } = make(TILE, TILE);
  const wood = ramp('#7a4f22'), gold = P.accent;
  ellipseShadow(ctx, 8, 14, 6, 2, 0.3);
  px(ctx, 2, 8, 12, 6, wood[1]);
  px(ctx, 2, 8, 12, 1, wood[2]);
  px(ctx, 2, 13, 12, 1, wood[0]);
  if (open) {
    px(ctx, 2, 3, 12, 4, wood[1]);
    px(ctx, 3, 4, 10, 2, '#2a1e12');
    px(ctx, 4, 9, 8, 3, gold[4]);
  } else {
    px(ctx, 2, 4, 12, 5, wood[2]);
    px(ctx, 3, 3, 10, 1, wood[3]);
    px(ctx, 2, 8, 12, 1, gold[2]);
    px(ctx, 7, 8, 2, 3, gold[3]);
    px(ctx, 7, 9, 2, 1, gold[0]);
  }
  px(ctx, 3, 4, 1, 5, wood[3]);
  px(ctx, 12, 4, 1, 5, wood[0]);
  return canvas;
}

/* ---------- buildings ---------- */
/* 32x32 over a 2x1 footprint, so a house is a building and not a shed. Four
 * rebuild tiers, because the village visibly recovers as fluency rises and that
 * is the best set piece the design already contains. */
const BUILD_VARIANTS = ['cottage', 'hall', 'forge', 'tower'];

export function buildingSprite(palette, seed, tier = 2, variant = 0) {
  const P = palOf(palette);
  const kind = BUILD_VARIANTS[variant % BUILD_VARIANTS.length];
  const { canvas, ctx } = make(32, 32);
  const rand = rng(seed + variant * 1301 + tier * 17);
  const wall = ramp(tier >= 2 ? '#c8b492' : tier === 1 ? '#a2907a' : '#7a6f60');
  const roof = tier >= 2 ? P.accent : ramp(mixHex(P.accent[2], '#4a4038', 0.55));
  const Bk = P.bark;
  const lit = tier >= 3 ? '#ffeaa8' : tier === 2 ? '#ffd98a' : '#2e2a1c';

  const tall = kind === 'tower';
  const wide = kind === 'hall';
  const x0 = tall ? 9 : wide ? 1 : 3;
  const x1 = tall ? 23 : wide ? 31 : 29;
  const wallTop = tall ? 8 : wide ? 13 : 15;
  const base = 30;

  ellipseShadow(ctx, 16, base + 1, (x1 - x0) / 2, 2, 0.32);

  // walls
  px(ctx, x0, wallTop, x1 - x0, base - wallTop, wall[2]);
  px(ctx, x0, wallTop, 1, base - wallTop, wall[3]);
  px(ctx, x1 - 1, wallTop, 1, base - wallTop, wall[1]);
  px(ctx, x0, base - 1, x1 - x0, 1, wall[0]);
  for (let y = wallTop; y < base; y++) {
    for (let x = x0; x < x1; x++) {
      if (cellRand(seed, x, y, 81) > 0.93) px(ctx, x, y, 1, 1, wall[1]);
    }
  }
  // timber framing, which is what makes a wall read as built rather than poured
  if (kind !== 'tower') {
    px(ctx, x0 + 4, wallTop, 1, base - wallTop, Bk[1]);
    px(ctx, x1 - 5, wallTop, 1, base - wallTop, Bk[1]);
    px(ctx, x0, wallTop + 6, x1 - x0, 1, Bk[1]);
  }

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
    px(ctx, rx, y, w, 1, i % 2 ? roof[1] : roof[2]);
    // Light gathers at the ridge and runs off the right eave. Splitting the
    // roof down the middle instead — which is the obvious thing to write — puts
    // a seam where a house has none.
    if (i >= rows - 3) px(ctx, rx, y, w, 1, roof[3]);
    px(ctx, rx, y, 2, 1, roof[3]);
    px(ctx, rx + w - 2, y, 2, 1, roof[0]);
    if (holed) {
      const hx = rx + 2 + Math.floor(cellRand(seed, i, 1, 83) * Math.max(1, w - 4));
      ctx.clearRect(hx, y, 2, 1);
    }
  }
  px(ctx, x0 - 2, roofBase + 1, span, 1, roof[0]);   // eaves shadow

  // windows
  const winY = wallTop + 8;
  const winXs = tall ? [15] : wide ? [6, 14, 23] : [7, 20];
  const windows = [];
  for (const wx of winXs) {
    if (tier === 0 && cellRand(seed, wx, 2, 84) > 0.5) continue;
    px(ctx, wx - 1, winY - 1, 6, 6, Bk[1]);
    px(ctx, wx, winY, 4, 4, lit);
    if (tier >= 2) {
      px(ctx, wx, winY, 4, 1, '#fff4c8');
      px(ctx, wx + 2, winY, 1, 4, Bk[1]);
      windows.push([wx + 2, winY + 2]);
    } else if (tier === 1) {
      px(ctx, wx - 1, winY + 1, 6, 1, Bk[2]);   // boards
      px(ctx, wx - 1, winY + 3, 6, 1, Bk[2]);
    }
  }

  // door
  const dx = tall ? 14 : 14;
  px(ctx, dx, base - 9, 5, 9, Bk[1]);
  px(ctx, dx, base - 9, 5, 1, Bk[2]);
  px(ctx, dx + 1, base - 9, 3, 8, tier === 0 ? 'rgba(0,0,0,0.55)' : Bk[0]);
  if (tier >= 1) px(ctx, dx + 3, base - 5, 1, 1, P.accent[3]);

  // tier flourishes
  if (tier === 0) {
    for (let i = 0; i < 6; i++) {
      const rx = x0 + Math.floor(rand() * (x1 - x0 - 2));
      px(ctx, rx, base - 1, 2, 1, wall[0]);
      px(ctx, rx + Math.floor(rand() * 3) - 1, base, 2, 1, wall[1]);
    }
  }
  if (tier >= 2 && kind === 'forge') {
    px(ctx, x1 - 8, roofBase - rows - 3, 4, 8, wall[1]);
    px(ctx, x1 - 8, roofBase - rows - 3, 4, 1, wall[3]);
  }
  if (tier >= 3) {
    px(ctx, x0 + 1, base - 4, 6, 3, P.foliage[2]);     // window box
    px(ctx, x0 + 2, base - 5, 1, 1, P.accent[4]);
    px(ctx, x0 + 5, base - 5, 1, 1, P.accent[4]);
    for (let i = 0; i < span; i += 3) px(ctx, x0 - 2 + i, roofBase + 2, 2, 1, P.accent[2]);
  }
  canvas.windows = windows;
  return canvas;
}

/* ---------- flora (the swaying overlay) ---------- */

function tuftSprite(P, seed, variant, frame) {
  const { canvas, ctx } = make(8, 8);
  const F = variant % 3 === 0 ? P.foliage : P.ground;
  const lean = [0, 1, 0, -1][frame];
  const rand = rng(seed + variant * 97);
  const blades = 3 + Math.floor(rand() * 2);
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

function flowerSprite(P, seed, variant, frame) {
  const { canvas, ctx } = make(8, 8);
  const petals = ['#e8e0f0', '#ffd97a', '#e87a9a', '#8fb8ff', '#ffb05a'];
  const c = ramp(petals[variant % petals.length]);
  const lean = [0, 1, 0, -1][frame];
  const F = P.foliage;
  px(ctx, 3, 5, 1, 3, F[1]);
  px(ctx, 3 + Math.round(lean * 0.5), 4, 1, 1, F[1]);
  const hx = 3 + lean;
  px(ctx, hx, 2, 2, 2, c[2]);
  px(ctx, hx, 2, 1, 1, c[4]);
  px(ctx, hx + 1, 3, 1, 1, c[1]);
  px(ctx, hx - 1, 3, 1, 1, c[2]);
  px(ctx, hx + 2, 2, 1, 1, c[2]);
  return canvas;
}

function reedSprite(P, seed, variant, frame) {
  const { canvas, ctx } = make(8, 12);
  const F = P.foliage;
  const lean = [0, 1, 2, 1][frame];
  const rand = rng(seed + variant * 131);
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

/* ---------- palette expansion ---------- */

function palOf(palette) {
  if (palette && palette.__ramps) return palette;
  const pal = typeof palette === 'string'
    ? (PALETTES[palette] || PALETTES.spring)
    : (palette || PALETTES.spring);
  // Water, dirt, rock, sand and bark are not in the sixteen authored palettes.
  // Deriving them here — rather than reusing `sky` for water, which is why one
  // village lake is indigo and indistinguishable from the void behind the map —
  // keeps regional identity without letting water stop looking like water.
  const waterBase = pal.water || reHue(pal.sky, 205, 55, 0.42, 0.34);
  const P = {
    __ramps: true,
    raw: pal,
    ground: ramp(pal.ground),
    ground2: ramp(pal.ground2),
    mid: ramp(pal.mid),
    far: ramp(pal.far),
    sky: ramp(pal.sky),
    accent: ramp(pal.accent),
    foliage: ramp(pal.foliage || pal.mid),
    dark: ramp(pal.dark),
    dirt: ramp(mixHex(reHue(pal.accent, 30, 18, 0.18, 0.31), pal.ground, 0.42)),
    rock: ramp(reHue(pal.far, 250, 0, 0, null)),
    sand: ramp(mixHex(mixHex(pal.accent, '#b5a488', 0.58), pal.ground, 0.26)),
    bark: ramp('#4a3320'),
    water: null,
  };
  // Five water values from shore to deep: the depth gradient is a ramp of its
  // own so the shelf can be light and the middle genuinely dark.
  const wr = ramp(waterBase);
  P.water = [
    wr[0], wr[1], wr[2], wr[3],
    mixHex(wr[4], '#ffffff', 0.62),
  ];
  return P;
}

/* ---------- tileset ---------- */

const setCache = new Map();

/* A region's rasterised terrain. Static tiles are built eagerly (there are few);
 * fringes, foam and cliff faces are built on first use, because only a handful
 * of the 47 masks actually occur in any given map. */
export function terrainSet(regionId, palette, tier = 2, biome = 'grass') {
  const key = `${regionId}:${palette}:${tier}:${biome}`;
  const hit = setCache.get(key);
  if (hit) return hit;
  const P = palOf(palette);
  const seed = hashStr(key);
  const pine = ['mountain', 'deepforest', 'canopy', 'highland'].includes(biome);

  const fringeCache = new Map();
  const foamCache = new Map();
  const shelfCache = new Map();
  const emberCache = new Map();
  const cliffCache = new Map();

  const set = {
    id: regionId, seed, tier, biome, P,
    palette: P.raw,
    ground: [0, 1, 2, 3].map(v => grassTile(P, seed + v * 131, v)),
    path: [0, 1, 2].map(v => pathTile(P, seed + v * 149, v)),
    stone: [0, 1, 2].map(v => stoneTile(P, seed + v * 167, v)),
    sand: [0, 1].map(v => sandTile(P, seed + v * 181, v)),
    // 4x4-tile sheets, sub-rected at draw time. A single 16px water tile is
    // seamless and still repeats visibly every 16 pixels; sixteen is enough.
    water: [0, 1, 2, 3].map(d =>
      Array.from({ length: WATER_FRAMES }, (_, f) => waterSheet(P, seed + d * 13, d, f))),
    lava: Array.from({ length: WATER_FRAMES }, (_, f) => lavaSheet(seed + 37, f)),
    bridge: [bridgeTile(P, seed, false), bridgeTile(P, seed, true)],
    cliffShadow: cliffShadowTile(),
    tree: [0, 1, 2].map(v => treeSprite(P, seed + v * 211, v, pine)),
    bush: [0, 1, 2].map(v => bushSprite(P, seed + v * 223, v)),
    rock: [0, 1, 2].map(v => rockSprite(P, seed + v * 227, v)),
    stump: [stumpSprite(P, seed + 229)],
    crystal: [0, 1, 2].map(v => crystalSprite(P, seed + v * 233, v)),
    bones: [bonesSprite(P, seed + 239)],
    mushroom: [0, 1].map(v => mushroomSprite(P, seed + v * 241, v)),
    shrine: shrineSprite(P, seed + 251),
    chest: [chestSprite(P, seed + 257, false), chestSprite(P, seed + 257, true)],
    building: [0, 1, 2, 3].map(t =>
      BUILD_VARIANTS.map((_, v) => buildingSprite(P, seed + 263, Math.min(t, tier), v))),
    banner: [Array.from({ length: SWAY_FRAMES }, (_, f) =>
      bannerSprite(P, seed + 269, [0, 1, 2, 1][f]))],
    tuft: [0, 1, 2].map(v =>
      Array.from({ length: SWAY_FRAMES }, (_, f) => tuftSprite(P, seed + v * 271, v, f))),
    flower: [0, 1, 2, 3, 4].map(v =>
      Array.from({ length: SWAY_FRAMES }, (_, f) => flowerSprite(P, seed + v * 277, v, f))),
    reed: [0, 1].map(v =>
      Array.from({ length: SWAY_FRAMES }, (_, f) => reedSprite(P, seed + v * 281, v, f))),

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
        if (role === CLIFF_TOP) return cliffTopTile(P, seed, variant, sides);
        if (role === CLIFF_CAP) return cliffFaceTile(P, seed, variant, sides, 5);
        return cliffFaceTile(P, seed, variant, sides, 0);
      });
    },
  };
  setCache.set(key, set);
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
 * water depth, cliff roles, cast shadows, flora, decoration and lights.
 *
 * Called once per region load. The 60fps loop after that is array lookups and
 * drawImage, which is the only way this stays cheap. */
export function createScene(opts) {
  const {
    regionId = 'region', palette = 'spring', tier = 2, biome = 'grass',
    grid, decorDensity = 0.10, floraDensity = 0.42, avoid = null,
  } = opts;
  if (!grid || !grid.length) throw new Error('createScene: grid required');
  const h = grid.length, w = grid[0].length;
  const set = terrainSet(regionId, palette, tier, biome);
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
  const crest = new Int16Array(n).fill(-1);
  const shelf = new Int16Array(n).fill(0);
  const crestVar = new Uint8Array(n);
  const edges = new Array(n).fill(null);

  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h) ? null : grid[y][x];

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      cls[i] = groundClass(grid[y][x]);
      variant[i] = Math.floor(cellRand(seed, x, y, 1) * 4);
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

  // Cliff roles and the shadow they throw.
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (cls[i] !== 'cliff') continue;
      const north = at(x, y - 1), south = at(x, y + 1);
      const nCliff = north !== null && groundClass(north) === 'cliff';
      const sCliff = south !== null && groundClass(south) === 'cliff';
      role[i] = sCliff ? CLIFF_TOP : (nCliff ? CLIFF_FACE : CLIFF_CAP);
      if (role[i] === CLIFF_TOP) {
        let open = 0;
        if (!nCliff) open |= N;
        const west = at(x - 1, y), east = at(x + 1, y);
        if (west === null || groundClass(west) !== 'cliff') open |= W;
        if (east === null || groundClass(east) !== 'cliff') open |= E;
        sides[i] = open;
      } else {
        const west = at(x - 1, y), east = at(x + 1, y);
        let s = 0;
        if (west === null || groundClass(west) !== 'cliff') s |= 1;
        if (east === null || groundClass(east) !== 'cliff') s |= 2;
        sides[i] = s;
        if (y + 1 < h && groundClass(grid[y + 1][x]) !== 'cliff') shadow[(y + 1) * w + x] = 1;
      }
    }
  }

  // Edge descriptors: which higher-priority terrains reach into this cell, and
  // from which sides. Reduced to the 47-case blob, then cached per mask.
  const OFFS = [[0, -1, N], [1, -1, NE], [1, 0, E], [1, 1, SE],
                [0, 1, S], [-1, 1, SW], [-1, 0, W], [-1, -1, NW]];
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
          const shore = { cls: 'sand', host: me, mask: wm,
                          v: Math.floor(cellRand(seed, x, y, 2) * FRINGE_VARIANTS) };
          if (edges[i]) edges[i].push(shore); else edges[i] = [shore];
        }
      }
    }
  }

  const layers = { w, h, cls, variant, depth, role, sides, shadow, crest, crestVar, shelf, edges };

  // Object layer: everything that stands on the ground rather than being it.
  const objects = [];
  const consumed = new Set();
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
          oy: -8 + Math.floor(cellRand(seed, x, y, 41) * 3) - 1,
          sortY: y * TILE + TILE,
          img: set.tree[Math.floor(cellRand(seed, x, y, 4) * set.tree.length)],
        });
      } else if (code === TERRAIN.SHRINE) {
        objects.push({ kind: 'shrine', x, y, ox: 0, oy: -8, sortY: y * TILE + TILE, img: set.shrine });
      } else if (code === TERRAIN.CHEST) {
        objects.push({ kind: 'chest', x, y, ox: 0, oy: 0, sortY: y * TILE + TILE, img: set.chest[0] });
      } else if (code === TERRAIN.BUILDING) {
        // buildMap stamps houses two tiles wide; treat the pair as one structure
        // so the sprite can be 32px and look like somewhere people live.
        const pair = at(x + 1, y) === TERRAIN.BUILDING && !consumed.has(i + 1);
        if (pair) consumed.add(i + 1);
        const v = Math.floor(cellRand(seed, x, y, 5) * BUILD_VARIANTS.length);
        const img = set.building[Math.min(3, tier)][v];
        objects.push({
          kind: 'building', x, y, ox: pair ? 0 : -8, oy: -16,
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
      decor.push({
        kind, x, y, variant: v, img,
        ox: Math.floor(cellRand(seed, x, y, 9) * 5) - 2,
        oy: Math.floor(cellRand(seed, x, y, 10) * 3) - 1,
        sortY: y * TILE + TILE,
      });
    }
  }

  // Flora: the swaying overlay. Tufts and flowers on grass, reeds at the water's
  // edge. Each carries a phase so a field never sways in unison.
  const flora = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (cls[i] !== 'grass') continue;
      if (grid[y][x] !== TERRAIN.GRASS) continue;
      const nearWater = [[0, -1], [1, 0], [0, 1], [-1, 0]].some(([dx, dy]) => {
        const c = at(x + dx, y + dy);
        return c !== null && groundClass(c) === 'water';
      });
      const r = cellRand(seed, x, y, 12);
      if (BANNER_BIOMES.has(biome) && !blocked(x, y) && r < 0.05) {
        const nearPath = [[0, -1], [1, 0], [0, 1], [-1, 0]].some(([dx, dy]) => {
          const c = at(x + dx, y + dy);
          return c !== null && groundClass(c) === 'path';
        });
        if (nearPath) {
          flora.push({ kind: 'banner', x, y, variant: 0, ox: 4, oy: -6,
                       phase: Math.floor(cellRand(seed, x, y, 11) * SWAY_FRAMES) });
          continue;
        }
      }
      if (nearWater && r < 0.45) {
        flora.push({ kind: 'reed', x, y, variant: Math.floor(cellRand(seed, x, y, 13) * 2),
                     ox: Math.floor(cellRand(seed, x, y, 14) * 8), oy: 4,
                     phase: Math.floor(cellRand(seed, x, y, 15) * SWAY_FRAMES) });
        continue;
      }
      if (r > floraDensity) continue;
      const count = r < floraDensity * 0.35 ? 2 : 1;
      for (let k = 0; k < count; k++) {
        const isFlower = cellRand(seed, x, y, 16 + k) > 0.82;
        flora.push({
          kind: isFlower ? 'flower' : 'tuft', x, y,
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
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (cls[y * w + x] !== 'lava') continue;
      if ((x + y) % 3) continue;
      lights.push({ x: x * TILE + 8, y: y * TILE + 8, colour: '255,138,42', r: 20, flicker: 0.3 });
    }
  }

  return { regionId, w, h, grid, tier, biome, set, seed, layers, objects, decor, flora, lights };
}

function hexToRgbStr(hex) {
  const [r, g, b] = parseHex(hex);
  return `${r},${g},${b}`;
}

const BANNER_BIOMES = new Set(['village', 'citadel', 'castle', 'arena', 'highland', 'tower']);

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

/* Tile bounds for a camera. Two extra rows top and bottom because trees,
 * buildings and shrines are taller than their tile and must start drawing before
 * their anchor enters the view. */
export function viewBounds(scene, camX, camY, viewW, viewH, scale) {
  return {
    x0: Math.max(0, Math.floor(camX / TILE) - 1),
    y0: Math.max(0, Math.floor(camY / TILE) - 3),
    x1: Math.min(scene.w, Math.ceil((camX + viewW / scale) / TILE) + 1),
    y1: Math.min(scene.h, Math.ceil((camY + viewH / scale) / TILE) + 3),
  };
}

export function frames(time) {
  return {
    water: Math.floor(time * 5) % WATER_FRAMES,
    foam: Math.floor(time * 4.5) % FOAM_FRAMES,
    sway: Math.floor(time * 2.6),
  };
}

/* Ground pass: base terrain, then fringes, then animated crests, then the dark
 * cliffs throw. ctx is expected to be in world space already — scaled and
 * translated by the camera, exactly as overworld.js draw() already does. */
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
          img = set.cliff(L.role[i], L.sides[i], L.variant[i] % 3); break;
        default:
          img = set.ground[L.variant[i]];
      }
      if (img) ctx.drawImage(img, wx, wy);
      if (L.shelf[i]) ctx.drawImage(set.shelf(L.shelf[i], L.crestVar[i], L.depth[i]), wx, wy);

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
      if (L.shadow[i]) ctx.drawImage(set.cliffShadow, wx, wy);
    }
  }
}

function groundClassAt(scene, x, y) {
  if (x < 0 || y < 0 || x >= scene.w || y >= scene.h) return null;
  return scene.layers.cls[y * scene.w + x];
}

/* Flora pass: sways, sits flat on the ground, needs no sorting. Draw it straight
 * after drawGround and before anything with a shadow. */
export function drawFlora(ctx, scene, view, time) {
  const { set, flora } = scene;
  const f = frames(time);
  for (let k = 0; k < flora.length; k++) {
    const it = flora[k];
    if (it.x < view.x0 || it.x >= view.x1 || it.y < view.y0 || it.y >= view.y1) continue;
    const bank = set[it.kind][it.variant % set[it.kind].length];
    const img = bank[(f.sway + it.phase) % SWAY_FRAMES];
    ctx.drawImage(img, it.x * TILE + it.ox, it.y * TILE + it.oy);
  }
}

/* Everything that should be y-sorted against the hero, the NPCs and the enemy
 * markers. Returns plain descriptors so the caller can merge its own sprites in
 * and sort once — walking behind a tree is the whole point. */
export function collectObjects(scene, view, out = []) {
  const push = (o) => {
    if (o.x < view.x0 - 1 || o.x >= view.x1 + 1) return;
    if (o.y < view.y0 - 1 || o.y >= view.y1 + 2) return;
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
    const wob = 1 + Math.sin(time * 6.3 + l.x * 0.7 + l.y * 0.3) * (l.flicker || 0);
    const r = l.r * wob;
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

export { TILE, CLIFF_TOP, CLIFF_FACE, CLIFF_CAP, WATER_FRAMES, FOAM_FRAMES, SWAY_FRAMES };
