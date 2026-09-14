/* Original 16-bit character art, generated at runtime.
 *
 * Nothing here is traced, sampled or derived from any existing game, and no
 * copyrighted character is depicted. Every sprite is an authored character grid
 * plus a per-sprite palette, rasterised into an offscreen canvas and drawn with
 * nearest-neighbour scaling, exactly as pixel.js does for terrain.
 *
 * This module owns CHARACTERS — hero, enemies, bosses, portraits — and leaves
 * tiles to pixel.js. It is self-contained: it imports nothing, so either module
 * may import the other without a cycle.
 *
 * Three conventions carry the whole file:
 *
 *   1. `ramp()` builds a five-value shading ladder in HSL, shifting hue toward
 *      blue-violet in shadow and toward yellow in light. A flat RGB add is what
 *      makes generated art read as plastic; a hue-rotating ramp is what makes it
 *      read as 16-bit.
 *   2. `applyRim()` derives the highlight and shadow pass from the silhouette
 *      itself, so every sprite is lit from the upper left without any of them
 *      being hand-shaded. Authoring stays cheap; light direction stays uniform.
 *   3. Animation frames are authored deformations, not brightness nudges. A
 *      frame that differs by six units of brightness is not a frame.
 *   4. Every character is MERGED into one grid and then lit once —
 *      `mergeGrids()` then `applyRim()` then `rimLowLeft()`. Lighting a stack
 *      of layers separately is how a sprite ends up looking like the pieces it
 *      was assembled from; one silhouette, one light, and the pieces disappear.
 *      The light itself is fixed for the whole cast: a heavy near-black outline
 *      and one hot rim from low-left, inside that outline, always. Consistent
 *      lighting is what makes a cast read as a cast.
 *
 * Faces are the fifth thing and they get their own vocabulary: seven emotes —
 * neutral, pleased, strained, alarmed, stubborn, delighted, defeated — two
 * authored frames each, on the hero at EIGHT pixels wide (§C-2 widened the skin
 * box from six and this line said six for a whole art pass afterwards; see the
 * note above HERO_FACE_FRONT for the columns that actually render, which are
 * narrower still) and on the portraits at fourteen. The brow does most of the
 * work in both, which is the one technique worth stealing from the 16-bit era
 * wholesale: a mouth at this resolution has about two shapes in it, and a brow
 * can move a whole row.
 */

/* ---------- colour ---------- */

function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

/* Accepts #rgb and #rrggbb. Anything longer is a typo (an alpha byte pasted in
 * by hand) and is truncated rather than silently producing a negative int32. */
function parseHex(hex) {
  let h = String(hex || '#888888').replace('#', '');
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  if (h.length > 6) h = h.slice(0, 6);
  if (h.length < 6) h = h.padEnd(6, '0');
  const n = parseInt(h, 16) || 0;
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex(r, g, b) {
  const v = (clamp(Math.round(r), 0, 255) << 16)
          | (clamp(Math.round(g), 0, 255) << 8)
          | clamp(Math.round(b), 0, 255);
  return `#${v.toString(16).padStart(6, '0')}`;
}

function rgbToHsl([r, g, b]) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0));
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return [h * 60, s, l];
}

function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360;
  s = clamp(s, 0, 1); l = clamp(l, 0, 1);
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) { r = c; g = x; }
  else if (h < 120) { r = x; g = c; }
  else if (h < 180) { g = c; b = x; }
  else if (h < 240) { g = x; b = c; }
  else if (h < 300) { r = x; b = c; }
  else { r = c; b = x; }
  return toHex((r + m) * 255, (g + m) * 255, (b + m) * 255);
}

/* Five-step material ladder plus its two outline tones. Shadows rotate toward
 * blue-violet and gain saturation; lights rotate toward yellow and lose it. */
export function ramp(hex) {
  const [h, s, l] = rgbToHsl(parseHex(hex));
  const step = (dl, dh, ds) => hslToHex(h + dh, clamp(s + ds, 0, 1), clamp(l + dl, 0.03, 0.97));
  return {
    shadow2: step(-0.24, 22, 0.12),
    shadow1: step(-0.12, 12, 0.06),
    base: hslToHex(h, s, l),
    light1: step(0.11, -10, -0.05),
    light2: step(0.21, -18, -0.11),
    outline: step(-0.34, 26, 0.14),
    rim: step(-0.20, -6, 0.02),
  };
}

/* Kept for call sites that only want a nudge. Unlike a raw RGB add this routes
 * through the ramp's hue rotation, so a "lighter" pixel does not desaturate. */
export function shade(hex, amount) {
  const [h, s, l] = rgbToHsl(parseHex(hex));
  const f = amount / 255;
  return hslToHex(h + (f > 0 ? -14 : 18) * Math.min(1, Math.abs(f) * 4),
                  clamp(s + (f > 0 ? -0.06 : 0.08) * Math.min(1, Math.abs(f) * 4), 0, 1),
                  clamp(l + f, 0.03, 0.97));
}

export function mix(a, b, t) {
  const A = parseHex(a), B = parseHex(b);
  return toHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t);
}

/* ---------- deterministic noise ---------- */
export function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

export function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < String(str).length; i++) {
    h ^= String(str).charCodeAt(i); h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/* ---------- rasterising ---------- */
function make(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

/* '.' and ' ' are transparent; every other glyph indexes `pal`. Identical
 * contract to pixel.drawGrid, so grids can move between the two modules. */
export function drawGrid(ctx, grid, pal, ox = 0, oy = 0) {
  for (let y = 0; y < grid.length; y++) {
    const row = grid[y];
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      if (ch === '.' || ch === ' ') continue;
      const colour = pal[ch];
      if (!colour) continue;
      ctx.fillStyle = colour;
      ctx.fillRect(ox + x, oy + y, 1, 1);
    }
  }
}

export function gridSprite(grid, pal, w, h) {
  const width = w || Math.max(...grid.map(r => r.length));
  const height = h || grid.length;
  const { canvas, ctx } = make(width, height);
  drawGrid(ctx, grid, pal);
  return canvas;
}

/* Compose several grids into one canvas. Later layers draw over earlier ones,
 * which is how legs, body, arms and a held weapon become a single frame. */
export function composeSprite(w, h, layers, pal) {
  const { canvas, ctx } = make(w, h);
  for (const layer of layers) {
    if (!layer || !layer.grid) continue;
    drawGrid(ctx, layer.grid, layer.pal || pal, layer.ox || 0, layer.oy || 0);
  }
  return canvas;
}

/* ---------- grid surgery ---------- */
const EMPTY = ch => ch === undefined || ch === '.' || ch === ' ';
const EDGE = ch => EMPTY(ch) || ch === 'o' || ch === 'O';

function at(grid, y, x) {
  const row = grid[y];
  return row === undefined ? undefined : row[x];
}

function padRow(row, w) { return row.length >= w ? row.slice(0, w) : row.padEnd(w, '.'); }

export function normalise(grid, w) {
  const width = w || Math.max(...grid.map(r => r.length));
  return grid.map(r => padRow(r, width));
}

/* Shift a row range sideways. Used for cloak sway, neck lean and tail whip. */
export function shiftRows(grid, from, to, dx) {
  const w = Math.max(...grid.map(r => r.length));
  return normalise(grid, w).map((row, y) => {
    if (y < from || y > to || dx === 0) return row;
    return dx > 0 ? padRow('.'.repeat(dx) + row, w)
                  : padRow(row.slice(-dx) + '.'.repeat(-dx), w);
  });
}

/* Move the whole sprite vertically inside its own box: the bob. */
export function bobGrid(grid, dy) {
  const w = Math.max(...grid.map(r => r.length));
  const blank = '.'.repeat(w);
  const g = normalise(grid, w);
  if (dy === 0) return g;
  if (dy < 0) return g.slice(-dy).concat(Array(-dy).fill(blank));
  return Array(dy).fill(blank).concat(g.slice(0, g.length - dy));
}

/* Widen a row range by one pixel each side, reusing the edge glyph. This is the
 * squash half of a squash-and-stretch idle: mass displaced downward has to go
 * somewhere, and it goes sideways. */
export function widenRows(grid, from, to) {
  const w = Math.max(...grid.map(r => r.length));
  return normalise(grid, w).map((row, y) => {
    if (y < from || y > to) return row;
    const cells = row.split('');
    const first = cells.findIndex(c => !EMPTY(c));
    const last = cells.length - 1 - [...cells].reverse().findIndex(c => !EMPTY(c));
    if (first < 1 || last >= w - 1) return row;
    cells[first - 1] = cells[first];
    cells[last + 1] = cells[last];
    return cells.join('');
  });
}

/* Squash: drop one row off the top of the range and duplicate one near the
 * bottom, so the silhouette compresses without changing its footprint. */
export function squashRows(grid, from, to) {
  const w = Math.max(...grid.map(r => r.length));
  const g = normalise(grid, w);
  const out = g.slice();
  for (let y = from; y < to; y++) out[y] = g[y + 1];
  out[to] = g[to];
  return widenRows(out, to - 2, to);
}

/* Derive shading from the silhouette. Only 'B' (undecided body mass) is
 * touched, so an authored feature — an eye, a core, a rune — always survives.
 * Reads are taken from the untouched source, so the pass is order-independent.
 *
 *   upper-left interior edge -> light1 / light2 on a corner
 *   lower-right interior edge -> shadow1
 *   lower edge past mid-height -> shadow2, the grounded underside
 *   outline facing the light -> lit rim rather than flat near-black
 */
export function applyRim(grid) {
  const w = Math.max(...grid.map(r => r.length));
  const src = normalise(grid, w);
  const h = src.length;
  const out = src.map(r => r.split(''));
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ch = src[y][x];
      const up = at(src, y - 1, x), left = at(src, y, x - 1);
      const down = at(src, y + 1, x), right = at(src, y, x + 1);
      if (ch === 'B') {
        if (EDGE(up) && EDGE(left)) out[y][x] = 'H';
        else if (EDGE(up) || EDGE(left)) out[y][x] = 'L';
        else if (EDGE(down) && y > h * 0.58) out[y][x] = 'D';
        else if (EDGE(down) || EDGE(right)) out[y][x] = 'd';
      } else if (ch === 'o') {
        if (EMPTY(up) || EMPTY(left)) out[y][x] = 'O';
      }
    }
  }
  return out.map(r => r.join(''));
}

/* ---------- ground shadow ---------- */
const shadowCache = new Map();

/* A hard-edged two-tone ellipse. Every sprite in the game can sit on one, which
 * is the cheapest depth cue there is: without it everything floats. */
export function groundShadow(rx, ry, alpha = 0.34, colour = '#0b0a12') {
  const key = `${rx}:${ry}:${alpha}:${colour}`;
  if (shadowCache.has(key)) return shadowCache.get(key);
  const w = rx * 2 + 2, h = ry * 2 + 2;
  const { canvas, ctx } = make(w, h);
  const cx = w / 2, cy = h / 2;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry;
      const d = dx * dx + dy * dy;
      if (d > 1) continue;
      ctx.globalAlpha = d > 0.55 ? alpha * 0.55 : alpha;
      ctx.fillStyle = colour;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  ctx.globalAlpha = 1;
  shadowCache.set(key, canvas);
  return canvas;
}

/* Draw a shadow centred on (cx, cy) in the caller's own coordinate space. */
export function drawGroundShadow(ctx, cx, cy, rx, ry, alpha = 0.34) {
  const img = groundShadow(Math.max(1, Math.round(rx)), Math.max(1, Math.round(ry)), alpha);
  ctx.drawImage(img, Math.round(cx - img.width / 2), Math.round(cy - img.height / 2));
}

/* Move a row range down inside the grid. The head settling into the shoulders
 * on a breathing frame is one row of this and nothing else. */
export function sinkRows(grid, from, to, dy) {
  const w = Math.max(...grid.map(r => r.length));
  const g = normalise(grid, w);
  const out = g.slice();
  for (let y = to; y >= from + dy; y--) out[y] = g[y - dy];
  for (let y = from; y < from + dy && y <= to; y++) out[y] = '.'.repeat(w);
  return out;
}

/* ---------- merging, and the one low light ---------- */

/* Overlay several grids into ONE character grid before anything is rasterised.
 * Compositing on the canvas is cheaper and stays available (composeSprite), but
 * a composited canvas cannot be lit: a shading pass has to see the WHOLE
 * silhouette — arms, cloak, blade and all — or the light stops dead at the edge
 * of whichever layer it happened to run on, which is exactly how a sprite ends
 * up looking like four sprites stacked.
 *
 * Later layers win. '.' never erases what is beneath it, so the contract is
 * identical to drawGrid's; offsets may be negative and are clipped. */
export function mergeGrids(w, h, layers) {
  const out = [];
  for (let y = 0; y < h; y++) out.push(new Array(w).fill('.'));
  for (const layer of layers) {
    if (!layer || !layer.grid) continue;
    const g = layer.grid;
    const ox = layer.ox | 0, oy = layer.oy | 0;
    for (let y = 0; y < g.length; y++) {
      const ty = y + oy;
      if (ty < 0 || ty >= h) continue;
      const row = g[y];
      for (let x = 0; x < row.length; x++) {
        const tx = x + ox;
        if (tx < 0 || tx >= w) continue;
        const ch = row[x];
        if (ch === '.' || ch === ' ') continue;
        out[ty][tx] = ch;
      }
    }
  }
  return out.map(r => r.join(''));
}

/* The colour of the key light every character in the cast is lit by: one low,
 * hot source, off to the left. It is never used neat — each material mixes it
 * with its own lightest step — so the rim reads as one lamp falling on
 * different things rather than the same orange decal stuck onto each of them.
 * A cast looks like a cast when the light agrees; that is the whole trick. */
export const RIM_LIGHT = '#ffab5e';

export function rimTone(materialLight, strength = 0.62) {
  return mix(materialLight || '#c0c0c0', RIM_LIGHT, clamp(strength, 0, 1));
}

/* Paint that light onto a grid.
 *
 * applyRim() puts the soft fill on the upper left and is untouched — bosses and
 * loot art depend on its exact output — and this runs afterwards. It works
 * INSIDE the outline, so the heavy black silhouette survives intact and the hot
 * edge sits just within it, which is what stops the rim reading as a glow.
 *
 * A pixel is rimmed when the cell below-left of it is outside the body and it
 * still has a neighbour holding it up. That second test is the important one:
 * without it a one-pixel feature — a spear shaft, a strand of hair, the bridge
 * of a nose — is eaten whole by its own highlight and the sprite loses a
 * detail every time the light moves.
 */
export function rimLowLeft(grid, glyph = 'R', protect = '') {
  const w = Math.max(...grid.map(r => r.length));
  const src = normalise(grid, w);
  const h = src.length;
  // "Outside" is the empty space plus the outline pixels that touch it. An
  // outline INSIDE the body — a mouth, a belt line, the seam between a hand and
  // a hilt — is deliberately not outside, or every interior line in the sprite
  // would start emitting light of its own and the read would collapse.
  const outside = [];
  for (let y = 0; y < h; y++) {
    const row = new Array(w);
    for (let x = 0; x < w; x++) {
      const ch = src[y][x];
      // Left, right and above the box is air. BELOW the bottom row is not: the
      // sprite is standing on something. Without that asymmetry the floor of the
      // box reads as a silhouette edge and the last row of every sprite lights
      // up in a hot bar, which is a box glowing rather than a figure lit.
      row[x] = EMPTY(ch) ? true
        : (ch !== 'o' && ch !== 'O') ? false
        : (EMPTY(at(src, y - 1, x)) || EMPTY(at(src, y, x - 1))
           || EMPTY(at(src, y, x + 1)) || (y + 1 < h && EMPTY(at(src, y + 1, x))));
    }
    outside.push(row);
  }
  const out = src.map(r => r.split(''));
  const off = (y, x) => y >= h ? false : (y < 0 || x < 0 || x >= w) ? true : outside[y][x];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ch = src[y][x];
      if (EDGE(ch) || protect.indexOf(ch) >= 0) continue;
      // Both the cell to the left and the cell below-left must be outside: that
      // is a surface whose normal points down-LEFT, at the light. A flat
      // underside — the bottom of a shoulder line, the sole of a boot — points
      // straight down and gets nothing but the pixel on its left end, which is
      // the difference between a figure that is lit and a box with a hot bar
      // painted along the bottom of it.
      if (!off(y + 1, x - 1) || !off(y, x - 1)) continue;
      if (off(y, x + 1) && off(y - 1, x)) continue;        // a lone pixel: leave it be
      out[y][x] = glyph;
    }
  }
  return out.map(r => r.join(''));
}

/* Caches here are working sets, not archives. Every one of them is a Map keyed
 * by an authored string, so a cap plus oldest-out is enough: the entries a frame
 * actually asks for are re-made once and then live, and nothing grows without
 * bound while a player walks around for an hour. */
function capCache(map, max) {
  while (map.size > max) {
    const oldest = map.keys().next();
    if (oldest.done) break;
    map.delete(oldest.value);
  }
  return map;
}

/* Knock a sprite down to a 16px box and count the pixels that survive. The
 * silhouette is the primary readability channel in pixel art: if a character
 * does not read as itself in a thumbnail, no amount of interior shading will
 * save it. Used by the art checks, cheap enough to call from a debug overlay. */
export function silhouetteAt(grid, box = 16) {
  const w = Math.max(...grid.map(r => r.length)), h = grid.length;
  const g = normalise(grid, w);
  const out = [];
  for (let y = 0; y < box; y++) {
    let row = '';
    for (let x = 0; x < box; x++) {
      const sx0 = Math.floor(x * w / box), sx1 = Math.max(sx0 + 1, Math.floor((x + 1) * w / box));
      const sy0 = Math.floor(y * h / box), sy1 = Math.max(sy0 + 1, Math.floor((y + 1) * h / box));
      let on = 0, total = 0;
      for (let sy = sy0; sy < sy1 && sy < h; sy++) {
        for (let sx = sx0; sx < sx1 && sx < w; sx++) { total++; if (!EMPTY(g[sy][sx])) on++; }
      }
      row += (total && on * 2 >= total) ? '#' : '.';
    }
    out.push(row);
  }
  return out;
}

/* ================================================================
 * HERO
 * ================================================================
 * 16x24. Four facings authored separately — a mirrored side view puts the
 * scabbard on the wrong hip and shifts the silhouette a pixel or two on every
 * turn, which the player reads as a stutter.
 *
 * A frame is composed from four authored layers so the walk carries weight:
 *   hem   cloak, swaying a pixel behind the legs
 *   legs  a real stride — one leg planted low, the other lifted
 *   body  head and torso, raised one pixel on the pass frames
 *   arms  swinging opposite the legs, with the weapon in the lead hand
 */
export const HERO_W = 16;
export const HERO_H = 24;

export const HERO_BODY = {
  down: [
    '................',
    '....oooooooo....',
    '...oHHHhhhhho...',
    '..oHhhHHhhhhho..',
    '..ohssssssssho..',
    '..ohssssssssho..',
    '..ohssssssssho..',
    '..ohNssssssSho..',
    '...oNssssssSo...',
    '..oCCccgcccvvo..',
    '.oCCccvvccccvvo.',
    '.oCctTTtttttcvo.',
    '.occttTTttttvvo.',
    '..octtTtttttvo..',
    '..ocggggggggvo..',
    '...octtttttvo...',
    '...occtttvvvo...',
    '...occccvvvvo...',
  ],
  up: [
    '................',
    '....oooooooo....',
    '...oHHHhhhhho...',
    '..oHhhHHhhhhho..',
    '..oHhhHHhhhhho..',
    '..ohhhhhhhhhho..',
    '..ohhhHHhhhHho..',
    '..ohhhhhhhhhho..',
    '...ohhhhhhhho...',
    '..oCCccgcccvvo..',
    '.oCCccvvccccvvo.',
    '.oCccCCcccvccvo.',
    '.occCCcccvccvvo.',
    '..ocCCccvccvvo..',
    '..ocggggggggvo..',
    '...occCcvccvo...',
    '...occccvvvvo...',
    '...occcvvvvvo...',
  ],
  left: [
    '................',
    '...oooooooo.....',
    '..oHHhhhhhhho...',
    '..ossHHhhhhhho..',
    '..ossssshhhhho..',
    '..ossssshhhhho..',
    '..ossssshhhhho..',
    '..ossssshhhho...',
    '..osssssShho....',
    '..oCcccccccvvo..',
    '.otTTtCccvccvvo.',
    '.otTTtCCcvvvcvo.',
    '.ottttcccCvvcvo.',
    '..oggggcccvcvo..',
    '..ottttcccvcvo..',
    '..otttccccvcvo..',
    '...occcccvccvo..',
    '...occcvvvvco...',
  ],
  right: [
    '................',
    '.....oooooooo...',
    '...ohhhhhhhHHo..',
    '..ohhhhhhHHsso..',
    '..ohhhhhssssso..',
    '..ohhhhhssssso..',
    '..ohhhhhssssso..',
    '...ohhhhssssso..',
    '....ohhSssssso..',
    '..ovvcccccccCo..',
    '.ovvccvccCtTTto.',
    '.ovcvvccCCtTTto.',
    '.ovcvvCccctttto.',
    '..ovcvcccggggo..',
    '..ovcvccctttto..',
    '..ovcvccccttto..',
    '..ovccvccccco...',
    '...ocvvvvccco...',
  ],
};

/* Six rows, drawn at y=18. Frames 0 and 2 are contacts (one boot lands a pixel
 * lower than the other); 1 and 3 are passes with the legs gathered. */
const HERO_LEGS = {
  down: [
    ['...oppppppppo...', '..oppo....oppo..', '..oppo....obbo..',
     '..obbo....okko..', '..okko.....ooo..', '..ooo...........'],
    ['...oppppppppo...', '...oppo..oppo...', '...oppo..obbo...',
     '...obbo..okko...', '...okko...ooo...', '...ooo..........'],
    ['...oppppppppo...', '..oppo....oppo..', '..obbo....oppo..',
     '..okko....obbo..', '..ooo.....okko..', '..........ooo...'],
    ['...oppppppppo...', '...oppo..oppo...', '...obbo..oppo...',
     '...okko..obbo...', '...ooo...okko...', '.........ooo....'],
  ],
  up: [
    ['...oppppppppo...', '..oppo....oppo..', '..oppo....obbo..',
     '..obbo....obbo..', '..obko.....ooo..', '..ooo...........'],
    ['...oppppppppo...', '...oppo..oppo...', '...oppo..obbo...',
     '...obbo..obko...', '...obko...ooo...', '...ooo..........'],
    ['...oppppppppo...', '..oppo....oppo..', '..obbo....oppo..',
     '..obbo....obbo..', '..ooo.....obko..', '..........ooo...'],
    ['...oppppppppo...', '...oppo..oppo...', '...obbo..oppo...',
     '...obko..obbo...', '...ooo...obko...', '.........ooo....'],
  ],
  left: [
    ['...opppppppo....', '..oppo..oppo....', '.oppo....oppo...',
     '.obbo....obbo...', 'okko......okko..', 'ooo........ooo..'],
    ['...opppppppo....', '...oppppppo.....', '...oppoppo......',
     '...obboobo......', '...okkookko.....', '...oooo.ooo.....'],
    ['....opppppppo...', '....oppo..oppo..', '...oppo....oppo.',
     '...obbo....obbo.', '..okko......okko', '..ooo........ooo'],
    ['....opppppppo...', '....oppppppo....', '....oppoppo.....',
     '....obboobo.....', '....okkookko....', '....oooo.ooo....'],
  ],
  right: [
    ['....opppppppo...', '....oppo..oppo..', '...oppo....oppo.',
     '...obbo....obbo.', '..okko......okko', '..ooo........ooo'],
    ['....opppppppo...', '....oppppppo....', '....oppoppo.....',
     '....obboobo.....', '....okkookko....', '....oooo.ooo....'],
    ['...opppppppo....', '..oppo..oppo....', '.oppo....oppo...',
     '.obbo....obbo...', 'okko......okko..', 'ooo........ooo..'],
    ['...opppppppo....', '...oppppppo.....', '...oppoppo......',
     '...obboobo......', '...okkookko.....', '...oooo.ooo.....'],
  ],
};

/* Six rows at y=10. The shoulders are the silhouette: the arms now break the
 * torso box on BOTH sides, so the hero reads as a wedge — wide at the deltoid,
 * narrow at the waist — from across the room and at thumbnail size. They still
 * swing against the legs: on the frame where the left boot is planted, the
 * right hand is forward. */
const HERO_ARMS = {
  down: [
    ['oCco........ocC.', 'oCco........ocCo', 'oss.........ocCo', '.oo..........sso', '..............oo', '................'],
    ['oCco........ocCo', 'oCco........ocCo', 'oss..........sso', '.oo..........oo.', '................', '................'],
    ['.Cco........ocCo', 'oCco........ocCo', 'oCco.........sso', 'oss..........oo.', '.oo.............', '................'],
    ['oCco........ocCo', 'oCco........ocCo', 'oss..........sso', '.oo..........oo.', '................', '................'],
  ],
  up: [
    ['oCco........ocC.', 'oCco........ocCo', 'ovv.........ocCo', '.oo..........vvo', '..............oo', '................'],
    ['oCco........ocCo', 'oCco........ocCo', 'ovv..........vvo', '.oo..........oo.', '................', '................'],
    ['.Cco........ocCo', 'oCco........ocCo', 'oCco.........vvo', 'ovv..........oo.', '.oo.............', '................'],
    ['oCco........ocCo', 'oCco........ocCo', 'ovv..........vvo', '.oo..........oo.', '................', '................'],
  ],
  left: [
    ['oCco............', 'oCco............', 'oss.............', '.oo.............', '................', '................'],
    ['................', 'oCco............', 'oCco............', 'oss.............', '.oo.............', '................'],
    ['............ocCo', '............ocCo', '.............sso', '.............oo.', '................', '................'],
    ['................', 'oCco............', 'oCco............', 'oss.............', '.oo.............', '................'],
  ],
  right: [
    ['............ocCo', '............ocCo', '.............sso', '.............oo.', '................', '................'],
    ['................', '............ocCo', '............ocCo', '.............sso', '.............oo.', '................'],
    ['oCco............', 'oCco............', 'oss.............', '.oo.............', '................', '................'],
    ['................', '............ocCo', '............ocCo', '.............sso', '.............oo.', '................'],
  ],
};

/* Three rows at y=17, drawn behind the legs and swayed a pixel per frame. */
export const HERO_HEM = {
  down: [
    '..oCccvcccvcco..',
    '.oCccvcccvcccco.',
    '..ovvvvvvvvvvo..',
  ],
  up: [
    '..oCccvcccvcco..',
    '.oCccvcccvcccco.',
    '.ovvvvvvvvvvvvo.',
  ],
  left: [
    '..oCccvcccvcco..',
    '.oCccvcccvccco..',
    '..ovvvvvvvvo....',
  ],
  right: [
    '..occvcccvccCo..',
    '..occcvcccvccCo.',
    '....ovvvvvvvvo..',
  ],
};

/* Arms up, weapon raised, for a CAST. The pose has to read at a glance from the
 * battle panel, so the silhouette breaks the body box on both sides. */
const HERO_CAST_ARMS = {
  down: [
    'oCco........ocCo',
    'oss..........sso',
    '.oo..........oo.',
    '................',
    '................',
    '................',
  ],
  up: [
    'oCco........ocCo',
    'ovv..........vvo',
    '.oo..........oo.',
    '................',
    '................',
    '................',
  ],
  left: [
    'oCco............',
    'oss.............',
    '.oo.............',
    '................',
    '................',
    '................',
  ],
  right: [
    '............ocCo',
    '.............sso',
    '.............oo.',
    '................',
    '................',
    '................',
  ],
};

/* ---------- the face ----------
 *
 * Five rows stamped over the skull at y=4. The hero's face is EIGHT pixels wide
 * — §C-2 widened the skin box from six and this comment went on saying six,
 * which is how a new emote gets authored into a box two columns narrower than
 * the one that exists. HERO_BODY.down rows 4..8 put skin at cols 4..11; the
 * profile bodies put it at cols 3..7.
 *
 * THE BOX THAT RENDERS IS SMALLER THAN THE BOX THAT IS AUTHORED, and the
 * difference was measured by flipping one cell at a time, re-rendering in a
 * fresh module instance and counting changed pixels:
 *
 *   front    rows 0..2  cols 4..11   (col 3 is eaten by the low-left rim)
 *            rows 3..4  cols 4..10   (the weapon crosses cols 11..13 there)
 *   profile  row  0     cols 4..7    (col 3 is rim on the left facing)
 *            rows 1..2  cols 3..7
 *            rows 3..4  cols 4..7    (col 3 is rim on the RIGHT facing, whose
 *                                     table is a frozen mirror built below)
 *
 * A cell outside those windows is paid for in the authored strip, counted by
 * the harness, and never seen. Two of them were doing real damage: alarmed's
 * outer lower sclera sat at front col 11 under the blade, and the delighted
 * profile spent one of its four blink cells on the head's own outline column,
 * so the blink rendered three pixels against a law that asks for four. Both
 * moved inward; neither costs a colour.
 *
 * Brows are hair-coloured, so a brow cell that lands on the hair rather than on
 * the skin is invisible even where the probe calls it live: front cols 3 and 12
 * and profile col 8 are hair on rows 0..1. Keep brows inside the skin.
 *
 * The BROW still does the work. Look down these tables in a column: the mouth
 * barely changes between strained and stubborn, and the two poses still read as
 * different states, because one has the brow driven down into the eye and the
 * other has it flat and heavy.
 *
 * Two frames each, so every emote can breathe: frame 1 is a blink, a squeeze or
 * a jaw-set rather than the same face two pixels brighter. */
export const HERO_FACE_FRONT = {
  neutral: [
    ['................', '....hhh..hhh....', '....wwo..oww....', '................', '.......oo.......'],
    ['................', '....hhh..hhh....', '....ooo..ooo....', '................', '.......oo.......'],
  ],
  // ARCHED. The brow lifts toward the middle: the outer end stays on row 1 and
  // the inner half steps up to row 0. It used to put that outer end on cols 3
  // and 12, which are hair, so half of this brow was never drawn.
  pleased: [
    ['.....hh..hh.....', '....h......h....', '....wwo..oww....', '................', '.....owwwwo.....'],
    ['.....hh..hh.....', '....h......h....', '.....oo..oo.....', '.....o....o.....', '.....owwwwo.....'],
  ],
  strained: [
    ['................', '....hho..ohh....', '....ooo..ooo....', '.....w....w.....', '......oooo......'],
    ['................', '....hoo..ooh....', '....ooo..ooo....', '.....w....w.....', '......wwww......'],
  ],
  // RAISED, the whole brow one row up and off the eye. The lower sclera pulls in
  // to cols 5..10: col 11 on row 3 is under the blade and never reached the
  // screen, so the eye that faces.mjs counted as ten cells was rendering nine.
  alarmed: [
    ['....hhh..hhh....', '................', '....www..www....', '.....ow..wo.....', '.......oo.......'],
    ['....hhh..hhh....', '................', '....wow..wow....', '.....ww..ww.....', '.......oo.......'],
  ],
  stubborn: [
    ['................', '....hhhhhhhh....', '....oww..wwo....', '................', '.....oooooo.....'],
    ['................', '....hhhhhhhh....', '....ooo..ooo....', '................', '.....oooooo.....'],
  ],
  delighted: [
    ['....h.h..h.h....', '....o.o..o.o....', '.....oo..oo.....', '................', '....owwwwwo.....'],
    ['....h.h..h.h....', '....o.o..o.o....', '....ooo..ooo....', '.....o....o.....', '....owwwwwo.....'],
  ],
  /* THE ONE FACE THAT HAD NO EYE IN IT.
   *
   * Frame 0 used to be a solid dark lid over a bare sclera row — '....ooo..ooo'
   * above '.....ww..ww' — with no dark cell anywhere inside the white, so there
   * was nothing on the sprite that read as an eyeball. faces.mjs printed
   * "defeated sclera 4 pupil 6" and the six were the LID.
   *
   * It gets a real sclera-pupil-sclera pair, low in the socket so the head still
   * reads as downcast. That does not fit at cols 4..6 / 9..11, because col 11 on
   * row 3 is under the blade, so the eyes move one column closer together — a
   * narrower eye-set, which is the right face for this emote anyway, and it
   * buys separation from every other emote in the table at the same time. */
  defeated: [
    ['......h..h......', '....hh....hh....', '....ooo.ooo.....', '....wow.wow.....', '......o..o......'],
    ['......h..h......', '....hh....hh....', '....ooo.ooo.....', '................', '......o..o......'],
  ],
};

/* The profile face: one eye and a four-pixel jaw, authored for `left` and
 * mirrored for `right`. The head is the one part of the hero that IS a true
 * mirror between the two side views — the torso is not, which is why the bodies
 * stay authored separately.
 *
 * THIS IS THE FACE A FIGHT SHOWS. fx.js draws the battle hero from
 * heroSprites().side, and heroSprites sets side = right, so the profile is the
 * only face on the battle stage and the front face is reachable only on the
 * overworld. That made the weakest of the three views the one the player looks
 * at most: measured in PIXELS off the raster rather than in authored cells, the
 * old table separated its closest pair by 7 on the left facing and 6 on the
 * right, against 9 for the front, and three of its seven emotes carried no
 * pupil at all.
 *
 * So it is re-authored rather than abandoned. Drawing the battle hero
 * front-on was the other option and it is refused: he would face the camera
 * while fighting something to his right, which is a bigger lie than a face two
 * pixels short.
 *
 * THE BOX IS FIVE COLUMNS AND NOT ALL OF THEM RENDER. HERO_BODY puts profile
 * skin at cols 3..7; the low-left rim eats col 3 on row 0 of the LEFT facing
 * and on rows 3..4 of the RIGHT one, because the mirror table below is built
 * from this one and the right body is authored separately. Measured cell by
 * cell, what survives on BOTH facings is:
 *      row 0  cols 4..7      row 1  cols 3..7     row 2  cols 3..7
 *      row 3  cols 4..7      row 4  cols 4..8  (col 8 is the jaw shadow)
 * Every cell below is inside that. The eye is two rows now — sclera across row
 * 2, pupil low in row 3 — which is what buys both the pupil and the separation
 * in a box this small. */
export const HERO_FACE_PROFILE = {
  neutral: [
    ['................', '....hhh.........', '...www..........', '....ow..........', '.....oo.........'],
    ['................', '....hhh.........', '...ooo..........', '................', '.....oo.........'],
  ],
  // ARCHED, and looking away rather than through you: the pupil sits at the
  // BACK of the eye, which is the one thing a profile can say that a front view
  // cannot.
  pleased: [
    ['.....hh.........', '...hh..h........', '...wwo..........', '....ww..........', '....owwo........'],
    ['.....hh.........', '...hh..h........', '...ooo..........', '................', '....owwo........'],
  ],
  // The brow driven down INTO the eye, and teeth bared on the effort. Frame 1
  // clamps the jaw shut on them.
  strained: [
    ['................', '...hhoo.........', '...ooo..........', '....w...........', '....wwwo........'],
    ['................', '...hooo.........', '...ooo..........', '....w...........', '....oooo........'],
  ],
  alarmed: [
    ['....hhhh........', '................', '...wow..........', '....ww..........', '.....ww.........'],
    ['....hhhh........', '................', '...ooo..........', '................', '.....ww.........'],
  ],
  // Half-lidded, and the lid comes from the FRONT: two dark cells with the
  // sclera behind them is a glare, where the same two cells behind the sclera
  // would be a squint.
  stubborn: [
    ['......hh........', '...hhhhh........', '...oow..........', '.....w..........', '....ooooo.......'],
    ['......hh........', '...hhhhh........', '...ooo..........', '................', '.....oo.........'],
  ],
  delighted: [
    ['....h.h.........', '....o.o.........', '...ooo..........', '................', '....owwwo.......'],
    ['....h.h.........', '....ooo.........', '...oooo.........', '....oo..........', '....owwwo.......'],
  ],
  defeated: [
    ['.....h..........', '...h............', '...ooo..........', '....wow.........', '....o..o........'],
    ['.....h..........', '...h............', '...oooo.........', '................', '....o..o........'],
  ],
};

/* ================================================================
 * THE WEAPON LADDER — six rungs of SHAPE, per family
 * ================================================================
 * Weapons live in a 6x12 box and are stamped into the lead hand at
 * WEAPON_ANCHOR, which does not move: lootart.js mirrors it and detaching it
 * would tear every gear overlay off every weapon in the game.
 *
 * WHY THIS IS A TABLE AND NOT A RULE. The ladder used to be one grid per family
 * plus two derived pixels of mass, and it was measured at one outline change
 * across six rungs on half the lines. A player who grinds four hundred and sixty
 * encounters for the top of a blade is owed a different OBJECT, not the same
 * object in a better colour, and an outline is the only part of it that survives
 * the walk across a room. So every rung is drawn: sixty grids over ten families,
 * plus twelve more for the two forged lines that would otherwise be somebody
 * else's weapon in their hand.
 *
 * The rungs are items.ARMOR_TIERS["weapon"]: 0 Rusted, 1 Honed, 2 Tempered,
 * 3 Runed, 4 Legendary, 5 Mythic. forge.RUNG_TO_HERO maps its nine tiers onto
 * these six, so two forge tiers can share a rung and differ only in colour —
 * that is the ladder working as designed, not a gap.
 *
 * They are authored in the metal ramp the armour uses — 'A' shadow, 'm' mid,
 * 'M' light, 'w' specular, 'g' the trim the rarity tier colours, 'u' the grip —
 * because a blade and a pauldron cut from the same steel is the entire argument
 * for sharing ramps. No rung brings a colour of its own, so the fifteen-colour
 * budget is paid for before the ladder starts.
 *
 * Three things every rung is drawn to:
 *   1. it MUST change the alpha mask, or it is a recolour wearing a rung's name;
 *   2. it MUST leave two rows of interior body, or runeBlade() below has nothing
 *      to etch and the Runed rung silently does nothing;
 *   3. it MUST stay inside its band (see WEAPON_BAND) — a line that grows every
 *      rung arrives at rung nine as a rectangle.
 */
const HERO_WEAPON_LADDER = {
  sword: [
    /* 0 pitted and short, the guard a stub, the point ground back */
    ['......', '......', '..o...', '.oAo..', '.oMo..', '.oAo..',
     '.oAo..', '.ogo..', '..u...', '..u...', '..o...', '......'],
    /* 1 full length, a true crossguard, a pommel under the hand */
    ['..o...', '.oMo..', '.oMo..', '.oMo..', '.oMo..', '.oMo..',
     '.oAo..', 'ogggo.', '..uu..', '.ouuo.', '.oggo.', '..oo..'],
    /* 2 a fuller opens the blade to four and the grip takes a second row */
    ['..oo..', '.oMMo.', '.oMMo.', '.oMMo.', '.oMMo.', '.oMMo.',
     '.oAAo.', 'ogggo.', 'o.uu.o', 'o.uu.o', '.oggo.', '..oo..'],
    /* 3 the quillons turn up and the blade runs a row longer */
    ['..o...', '.oMo..', '.oMMo.', 'oMMMMo', 'oMMMMo', '.oMMo.',
     '.oAAo.', 'oggggo', 'og..go', '.ouuo.', '.oggo.', '..oo..'],
    /* 4 a broad blade and a side ring each side of the grip */
    ['.oMMo.', 'oMMMMo', 'oMMMMo', 'oMMMMo', 'oMMMMo', '.oMMo.',
     '.oAAo.', 'oggggo', 'og..go', 'og..go', '.oggo.', '.oooo.'],
    /* 5 a leaf blade at its widest, the guard hung with trim */
    ['oMwwMo', 'oMwwMo', 'oM..Mo', 'oMwwMo', 'oMwwMo', 'oMwwMo',
     'oAwwAo', 'oggggo', 'og..go', 'og..go', 'oggggo', '.oooo.'],
  ],
  sabers: [
    /* 0 one saber, bent, held short */
    ['......', '......', '..o...', '.oAo..', '.oMo..', '.oAo..',
     '.ogo..', '..u...', '..o...', '......', '......', '......'],
    /* 1 one saber, straightened, with a knuckle bar */
    ['......', '..o...', '.oMo..', '.oMo..', '.oMo..', '.oAo..',
     'ogggo.', '..uu..', '.ouo..', '.ogo..', '..oo..', '......'],
    /* 2 the second saber shows behind the first */
    ['...o..', '..oMo.', '.oMoM.', '.oMoM.', '.oMoM.', '.oAoA.',
     'ogggo.', '..uu..', '.ouuo.', '.oggo.', '..oo..', '......'],
    /* 3 both blades full length over a six-wide guard */
    ['..o.o.', '.oMoMo', '.oMoMo', '.oMoMo', '.oMoMo', '.oAoAo',
     'oggggo', 'o.uu.o', '.ouuo.', '.oggo.', '..oo..', '......'],
    /* 4 a doubled guard and a ringed pommel */
    ['oo.ooo', 'oMMoMM', 'oMMoMM', 'oMMoMM', 'oMMoMM', 'oAAoAA',
     'oggggo', 'og..go', 'og..go', 'oggggo', '.oooo.', '......'],
    /* 5 the two blades part into a V that reads at sixteen pixels */
    ['oo..oo', 'oMo.oM', 'oMo.oM', 'oMo.oM', 'oMwwMo', 'oMwwMo',
     'oAwwAo', 'oggggo', 'og..go', 'og..go', 'oggggo', '.oooo.'],
  ],
  dagger: [
    /* 0 drawn thin and set crooked from the last thing it went into */
    ['......', '......', '..o...', '..oA..', '.oMo..', '.oAo..',
     '.ogo..', '..u...', '..o...', '......', '......', '......'],
    /* 1 straightened on a jig, a small four-wide guard */
    ['......', '..o...', '.oMo..', '.oMo..', '.oMo..', '.oAo..',
     '.oggo.', '..uu..', '.ouuo.', '.oggo.', '..oo..', '......'],
    /* 2 a longer shank, a guard and a capped pommel. The guard is four wide
     * and not five on purpose: forge.py grades the Tracing Needle NARROW at
     * tier four, which is the same hero rung tier five reaches at `standard`,
     * and a rung is one drawing. Drawn to the looser of the two grades the
     * tighter one silently loses a column to bandTrim — the left tip of the
     * crossguard, every time a Reading Needle is in the hand. The band is a
     * contract the table keeps, so the table is drawn to the tightest grade any
     * tier on the rung asks for, and the guard gets its fifth column at rung
     * three where the grading allows it. */
    ['..oo..', '.oMo..', '.oMo..', '.oMo..', '.oMo..', '.oMo..',
     '.oAo..', '.oggo.', '..uu..', '.ouuo.', '.oggo.', '.oooo.'],
    /* 3 the quillons sweep down clear of the grip */
    ['..oo..', '.oMMo.', '.oMMo.', '.oMMo.', '.oMMo.', '.oMMo.',
     '.oAAo.', 'ogggo.', '.o..o.', '.ouuo.', '.oggo.', '..oo..'],
    /* 4 the shank steps out toward the guard, each section wider */
    ['..o...', '.oMo..', '.oMMo.', 'oMMMo.', 'oMMMo.', 'oMMMo.',
     '.oAAo.', 'ogggo.', '.o..o.', '.ouuo.', '.oggo.', '.oooo.'],
    /* 5 the point is hollow: nullsteel does not give the room back */
    ['..oo..', '.oMMo.', '.o..o.', 'oMMMo.', 'oMMMo.', 'oMMMo.',
     '.oAAo.', 'ogggo.', '.o..o.', 'o.uuo.', 'ogggo.', '.oooo.'],
  ],
  axe: [
    /* 0 the bit is chipped back a column and the haft is short */
    ['......', '.ooo..', 'oMmAo.', '.ommo.', '.oAo..', '..ou..',
     '..ou..', '..ou..', '..ou..', '..ou..', '..oo..', '......'],
    /* 1 the head is whole and the haft is wrapped */
    ['.oooo.', 'oMmmAo', 'oMmmAo', '.oAAo.', '..ou..', '..ou..',
     '.oguo.', '..ou..', '..ou..', '..ou..', '..oo..', '......'],
    /* 2 the head takes a fourth course and the wrap drops a row */
    ['oooooo', 'oMmmAo', 'oMgmAo', 'oMmmAo', '.oAAo.', '..ou..',
     '..ou..', '.oguo.', '..ou..', '.ouo..', '.oggo.', '..oo..'],
    /* 3 a beard hooks down off the bit */
    ['oo.o.o', 'oMmmAo', 'oMgmAo', 'oMmmAo', 'oMmmAo', 'oMmAo.',
     '.oAo..', '.oguo.', '.ouuo.', '.oggo.', '.oooo.', '......'],
    /* 4 an outer course plates the bit and gold runs the haft */
    ['.oooo.', 'oMmmAo', 'oMgmAo', 'oMmmAo', 'oMmmAo', 'oMmmAo',
     'oMmAo.', '.oAo..', '..og..', 'og..go', 'oggggo', '.ooo..'],
    /* 5 the maker’s row is struck out of the bit and shows as a hole */
    ['oooooo', 'oMmmAo', 'oM..Ao', 'oMmmAo', 'oMmmAo', 'oMmmAo',
     'oMmmAo', 'oMmAo.', '.oAo..', '.oguo.', 'ogggoo', '.oooo.'],
  ],
  hammer: [
    /* 0 the head is split down one cheek */
    ['......', '.ooo..', 'oMmAo.', 'oM.Ao.', 'oMmAo.', '.oouo.',
     '..ou..', '..ou..', '..ou..', '..ou..', '..oo..', '......'],
    /* 1 the split is wire-bound and the head is whole */
    ['.oooo.', 'oMmmAo', 'oMgmAo', 'oMmmAo', '.oouo.', '..ou..',
     '.oguo.', '..ou..', '..ou..', '..ou..', '..oo..', '......'],
    /* 2 the head squares off to the full six and rings both ends */
    ['oooooo', 'oMmmAo', 'oMgmAo', 'oMgmAo', 'oMmmAo', '.oouo.',
     '..ou..', '.oguo.', '..ou..', '.ouo..', '.oggo.', '..oo..'],
    /* 3 a crown of notches opens the top of the head */
    ['o.oo.o', 'oooooo', 'oMmmAo', 'oMgmAo', 'oMgmAo', 'oMmmAo',
     '.oouo.', '.oguo.', '.ouuo.', '.oggo.', 'oggggo', '.oooo.'],
    /* 4 an outer course takes the weight and tapers to a peen */
    ['oo..oo', 'oooooo', 'oMmmAo', 'oMgmAo', 'oMmmAo', 'oMgmAo',
     'oMmmAo', '.oouo.', '.oguo.', '..ou..', 'oggggo', '.ooo..'],
    /* 5 the maker’s row is struck blank through the face */
    ['o.oo.o', 'oooooo', 'oMmmAo', 'oM..Ao', 'oMmmAo', 'oMgmAo',
     'oMmmAo', '.oouo.', '..ou..', '.oguo.', 'oggggo', '.oooo.'],
  ],
  spear: [
    /* 0 a bent head on a short shaft */
    ['......', '......', '..o...', '.oAo..', '.oMo..', '.oAo..',
     '..u...', '..u...', '..u...', '..u...', '..o...', '......'],
    /* 1 a true leaf head */
    ['..o...', '.oMo..', 'oMmAo.', '.oAo..', '..u...', '..u...',
     '..u...', '..u...', '..u...', '..u...', '..u...', '..o...'],
    /* 2 a longer head over a collared socket */
    ['..oo..', '.oMMo.', '.oMMo.', 'oMmAo.', '.oAo..', '.ogo..',
     '..u...', '..u...', '..u...', '..u...', '.ouo..', '..oo..'],
    /* 3 lugs open either side below the head */
    ['..o...', '.oMo..', '.oMMo.', 'oMmmAo', 'oMmAo.', '.oAo..',
     'o.g.o.', '.ogo..', '..u...', '..u...', '.oggo.', '..oo..'],
    /* 4 a longer head, doubled lugs and a bound shaft */
    ['.oMo..', 'oMmMo.', 'oMmmAo', 'oMmmAo', 'oMmAo.', '.oAo..',
     'o.g.o.', '.ogo..', '..ug..', '.ouo..', 'oggggo', '.ooo..'],
    /* 5 the socket is struck blank and the lugs flare */
    ['..o...', '.o.o..', 'oMmMo.', 'oM.Ao.', 'oMmmAo', 'oMmAo.',
     '.oAo..', 'og.go.', '.ogo..', '..ug..', 'oggggo', '.oooo.'],
  ],
  lance: [
    /* 0 bent, and short of the hand */
    ['......', '......', '..o...', '.oAo..', '.oMo..', '.oAo..',
     '..u...', '..u...', '..u...', '..u...', '..o...', '......'],
    /* 1 a true head on a full shaft */
    ['..o...', '.oMo..', '.oMo..', 'oMmAo.', '.ogo..', '..u...',
     '..u...', '..u...', '..u...', '..u...', '..u...', '..o...'],
    /* 2 a longer head and the first turn of a vamplate */
    ['..oo..', '.oMMo.', '.oMMo.', '.oMMo.', 'oMmAo.', '.oAo..',
     '.ogo..', '.oguo.', '..u...', '..u...', '.ouo..', '..oo..'],
    /* 3 the vamplate opens into a cone */
    ['..o...', '.oMo..', '.oMMo.', 'oMmmAo', '.oAAo.', '.oggo.',
     'og..go', '.ouo..', '..u...', '.ouo..', '.oggo.', '..oo..'],
    /* 4 a fluted head over a full vamplate */
    ['.oMo..', 'oMmMo.', 'oMmmAo', 'oMmmAo', '.oAAo.', '.oggo.',
     'oggggo', 'og..go', '.ouo..', '.ouo..', 'oggggo', '.ooo..'],
    /* 5 the shaft carries a blank band under a flared vamplate */
    ['..o...', '.o.o..', 'oMmMo.', 'oM.Ao.', 'oMmmAo', '.oAAo.',
     'oggggo', 'og..go', 'og..go', '.ouo..', 'oggggo', '.oooo.'],
  ],
  staff: [
    /* 0 a plain crook */
    ['......', '..oo..', '.ogo..', '..o...', '..u...', '..u...',
     '..u...', '..u...', '..u...', '..u...', '..o...', '......'],
    /* 1 a ringed head */
    ['..o...', '.ogo..', 'ogwgo.', '.ogo..', '..o...', '..u...',
     '..u...', '..u...', '..u...', '.ouo..', '.ogo..', '..oo..'],
    /* 2 a forked head over a collar ring */
    ['..oo..', '.oggo.', 'ogwwgo', '.oggo.', '..oo..', '.ogo..',
     '..u...', '..u...', '..u...', '..u...', '.ouo..', '..oo..'],
    /* 3 the head opens into a cage */
    ['.oooo.', 'og..go', 'o.ww.o', 'og..go', '.oooo.', '..o...',
     '.ogo..', '..u...', '..u...', '.ouo..', '.oggo.', '..oo..'],
    /* 4 a wider cage around a floating orb */
    ['oo..oo', 'og..go', 'o.ww.o', 'og..go', 'oo..oo', '..og..',
     '.oggo.', '..u...', '..ug..', '.ouo..', 'oggggo', '.ooo..'],
    /* 5 the orb is gone and the ring is broken open */
    ['oo..oo', 'og..go', 'o....o', 'og..go', 'oo..oo', '..og..',
     '.oggo.', '..u...', '..ug..', 'og..go', 'oggggo', '.oooo.'],
  ],
  bow: [
    /* 0 a short bow, barely bent */
    ['......', '.oo...', 'oA.o..', 'om..o.', 'omM.o.', 'om..o.',
     'oA.o..', '.oo...', '......', '......', '......', '......'],
    /* 1 a full bow, strung */
    ['.oo...', 'oA.o..', 'om..o.', 'om..o.', 'omM.o.', 'og..o.',
     'om..o.', 'om..o.', 'om..o.', 'oA.o..', '.oo...', '......'],
    /* 2 longer limbs down the whole box */
    ['.ooo..', 'oA.o..', 'om..o.', 'om..o.', 'om..o.', 'omM.o.',
     'og..o.', 'om..o.', 'om..o.', 'om..o.', 'oA.o..', '.ooo..'],
    /* 3 the tips flick forward into a recurve */
    ['...oo.', '.ooo..', 'oA.o..', 'om..o.', 'omg.o.', 'ogwgo.',
     'omg.o.', 'om..o.', 'om..o.', 'oA.o..', '.ooo..', '...oo.'],
    /* 4 a deeper belly and a riser under the hand */
    ['..oooo', '.ooo..', 'oA..o.', 'om...o', 'omg..o', 'ogwg.o',
     'omg..o', 'om...o', 'oA..o.', '.ooo..', '..oooo', '......'],
    /* 5 twin nocks and a sight window struck through the riser */
    ['.oo.oo', '.ooo..', 'oA..o.', 'om...o', 'omg..o', 'og...o',
     'o.wg.o', 'og...o', 'omg..o', 'om...o', '.oooo.', '.oo.oo'],
  ],
  relic: [
    /* 0 one leg short, the jaws will not close */
    ['......', '....o.', '.o..o.', '.o..o.', '.oAAo.', '.omo..',
     '..go..', '..u...', '..o...', '......', '......', '......'],
    /* 1 both legs true, a brass scale at the pivot */
    ['.o..o.', '.o..o.', '.o..o.', '.o..o.', '.oggo.', '.omo..',
     '..u...', '..u...', '.ouo..', '.oggo.', '..oo..', '......'],
    /* 2 a second scale up the outer arm */
    ['.o.oo.', '.o.oo.', '.o.oo.', '.o.oo.', '.oAggo', '.oggo.',
     '.omo..', '..u...', '..uu..', '.oggo.', '..oo..', '......'],
    /* 3 the jaws hook and the arms take bronze */
    ['oo.oo.', 'o..oo.', 'o..oo.', 'o..oo.', 'oggoo.', '.oggo.',
     '.ogo..', '.omo..', '..uu..', '.ouuo.', '.oggo.', '.oooo.'],
    /* 4 a third arm, read from the far side */
    ['oo.ooo', 'o..o.o', 'o..o.o', 'o..o.o', 'oggggo', '.oggo.',
     '.ogo..', '.omo..', '..ug..', 'og..go', 'oggggo', '.ooo..'],
    /* 5 the pivot is nullsteel and the maker’s row is blank */
    ['oo.o.o', 'o..o.o', 'og.o.o', 'o..o.o', 'oggggo', 'og...o',
     '.oggo.', '.omo..', '..ug..', 'o.oo.o', 'oggggo', '.oooo.'],
  ],
};

/* Two forged lines share a hero key with another forged line — forge.py sends
 * `relic` for both the Calipers and the Chain, and `hammer` for both the Maul
 * and the Spanner — so four blades would arrive as two objects. The Warden and
 * the Artificer do not carry the same tool, and at sixteen pixels that is the
 * cheapest legibility there is. Keyed on the `line` forge.hero_weapon_look()
 * ships; a line with no entry here falls back to its family above, which is why
 * the Calipers and the Maul are not repeated. */
const HERO_WEAPON_LINES = {
  recall_chain: [
    /* 0 two links on a ring, and already too heavy */
    ['......', '..oo..', '.o..o.', '.o..o.', '..oo..', '..u...',
     '..oo..', '.o..o.', '..oo..', '......', '......', '......'],
    /* 1 three links, neater, with a brass collar */
    ['..oo..', '.o..o.', '.o..o.', '..oo..', '..gg..', '..oo..',
     '.o..o.', '.o..o.', '..oo..', '..uu..', '..oo..', '......'],
    /* 2 a weight at the head and a longer span */
    ['.oooo.', '.omgo.', '.oooo.', '..oo..', '.o..o.', '.o..o.',
     '..oo..', '..gg..', '..oo..', '.o..o.', '.oooo.', '..oo..'],
    /* 3 every link now carries a smaller one */
    ['ooooo.', 'omgAo.', 'ooooo.', '.ommo.', '.o..o.', '.ommo.',
     '.ommo.', '.o..o.', '.ommo.', 'o.oo..', '.oooo.', '.o..o.'],
    /* 4 one span doubles and the link is absurd */
    ['oooooo', 'omgAgo', 'oooooo', 'ommmmo', 'om..mo', 'om..mo',
     'om..mo', 'ommmmo', '.oooo.', '.o..o.', '.oooo.', '..oo..'],
    /* 5 one nullsteel link, unmarked, holding all the rest */
    ['oo..oo', '.oooo.', 'oooooo', 'ommmmo', 'om..mo', 'om..mo',
     'om..mo', 'ommmmo', 'oooooo', 'o.oo.o', '.oooo.', '.o..o.'],
  ],
  toolwrights_spanner: [
    /* 0 one jaw, and enough play to round anything off */
    ['......', '.o.o..', '.omo..', '.omo..', '.oAo..', '..u...',
     '..u...', '..u...', '..u...', '..u...', '..o...', '......'],
    /* 1 the jaw is shimmed true and the adjuster takes brass */
    ['.o.o..', '.omo..', '.omo..', '.ogo..', '.oAo..', '..u...',
     '..u...', '..u...', '.ogo..', '.ouo..', '..oo..', '......'],
    /* 2 the fixed jaw appears and the head opens */
    ['o.o.o.', 'omomo.', '.ommo.', '.ogo..', '.oAo..', '..ug..',
     '..u...', '.ogo..', '..uu..', '.ouuo.', '.oggo.', '..oo..'],
    /* 3 a grip inside the grip, and the shank takes runework */
    ['oo.oo.', 'omomo.', '.ommo.', '.oggo.', '.oAo..', '..ug..',
     '.o.o..', '.ouo..', '.o.o..', 'og..o.', '.oggo.', '.oooo.'],
    /* 4 the larger jaw is exactly twice the smaller */
    ['oo.o.o', 'ommomo', '.ommmo', '.oggo.', '.oAo..', '..ug..',
     '.o.o..', '.ouo..', '.o.o..', '.ouuo.', 'oggggo', '.ooo..'],
    /* 5 the head is nullsteel and the stamp is gone */
    ['oo.o.o', 'om.omo', 'oommmo', '.oggo.', '.oAmo.', '..ug..',
     '.o.o..', '.ouo..', '.o.o..', 'og..go', 'oggggo', '.oooo.'],
  ],
};

/* THE HALF STEP.
 *
 * forge.RUNG_TO_HERO maps nine forged tiers onto six hero rungs, so tiers 3, 5
 * and 7 land on a rung their predecessor already drew. Measured, that was three
 * COLOUR-ONLY steps in every blade — tier 2 to tier 3 moved the trim and not one
 * pixel of outline — which is the same failure the rung table above was written
 * to end, just at a finer grain. A player grinding tier 5 is owed something they
 * can see from across a room as much as a player grinding tier 6 is.
 *
 * A half step is NOT a rung and does not get its own drawing. It gets the one
 * detail that tier's `look` sentence already promises, added to the rung below
 * it: a ferrule, a brace, a pin, a band, a second course on a jaw. Three rules,
 * the same three the rungs keep:
 *
 *   1. it must fill at least one transparent cell, or it is a recolour again;
 *   2. it must stay inside the columns the rung already occupies, because every
 *      rung here is drawn to the edge of its band and there is no room to grow
 *      sideways — a half step is a detail, not a promotion;
 *   3. it brings no colour of its own: 'o' outline, 'g' trim, 'm'/'M' metal,
 *      'u' grip, all already on the sprite.
 *
 * Sparse {row: pattern} overlays in the same six-wide space as the grid, '.'
 * keeps what is underneath; a space clears only the weapon cell, never the
 * hero beneath it. The Calipers' closing jaw uses that cutback. Details at the
 * outer heel and pommel remain visible beside the hero, where a tip or an
 * interior pin alone can disappear against the head and shoulder. Only hero rungs 1, 2 and 3 are ever shared, so only
 * those three are drawn; forge.py sends `half` and nothing else can set it, so
 * an unforged weapon never sees one of these.
 *
 * The four families that carry a forged line take their detail from that line's
 * own `look` — the Calipers ride `relic`, the Draft Axe `axe`, the Maul
 * `hammer`, the Needle `dagger` — and the two lines with their own ladder carry
 * their own. The remaining six are drawn to the same vocabulary so that a
 * seventh blade forged onto any of them is not colour-only on day one.
 */
const HALF_STEP = {
  /* the pommel squares off, trim closes the side rings, the point is squared */
  sword:  { 1: { 11: '.o..o.' }, 2: { 9: '.g..g.' }, 3: { 0: '...o..' } },
  /* a ringed pommel, a ring hung under it, then the guard takes an outer course */
  sabers: { 1: { 10: '.o..o.' }, 2: { 11: '.o..o.' }, 3: { 9: 'o....o' } },
  /* the Needle: the loomsteel shank runs a row longer, then it LEANS — the
   * wastes-iron reforge thickens one side of the shank and not the other —
   * then tilegold fills the open quillons and turns the corner of the cap */
  dagger: { 1: { 0: '..o...', 1: '.oMo..', 10: '....o.' }, 2: { 2: '...Mo.', 3: '...Mo.' },
            3: { 8: '..gg..', 11: '....o.' } },
  /* the Draft Axe: the bit welded out to the full head, a second ring on the
   * haft, then the outermost doubling plate closes the crown */
  axe:    { 1: { 0: 'o....o' }, 2: { 9: 'o...o.' }, 3: { 0: '..o.o.' } },
  /* the Maul: a collar under the face, then the same second ring the Draft Axe
   * gets — both tiers are the same heartwood haft on the same row of the same
   * box, and giving them different details to say the same thing would be
   * decoration — then tilegold banding fills the crown */
  hammer: { 1: { 4: 'o....o' }, 2: { 9: 'o...o.' }, 3: { 0: '.g..g.' } },
  /* a butt ferrule, a binding up the shaft, then the butt cap squares */
  spear:  { 1: { 10: '.o.o..' }, 2: { 9: '.o.o..' }, 3: { 11: '.o..o.' } },
  /* a ferrule, a collar under it, then the vamplate takes an outer course */
  lance:  { 1: { 9: '.o.o..' }, 2: { 10: 'o...o.' }, 3: { 4: 'o....o' } },
  /* a collar on the shaft, outer prongs on the head, then the cage closes over */
  staff:  { 1: { 9: 'o...o.' }, 2: { 1: 'o....o' }, 3: { 0: 'o....o' } },
  /* an upper rest, a lower one to match, then a bead in the sight window */
  bow:    { 1: { 2: '..g...' }, 2: { 9: '..gg..' }, 3: { 2: '..w...' } },
  /* the Calipers: a brass brace across the legs so they stop flexing, a flared
   * outer jaw tip, then a wastes-iron pin driven through both arms. The pin is
   * outline and not 'm' on purpose: runeBlade() picks its etch by counting rows
   * of each interior glyph, and two rows of 'm' where there was one is enough
   * to move the runework off the trim it was cut into. A half step adds a
   * detail; it does not get to retarget the rung above it. */
  relic:  { 1: { 2: '..gg..' }, 2: { 0: '.....o', 1: '.....o' },
            3: { 0: '.... .', 2: '.oo...' } },
};
const HALF_STEP_LINES = {
  /* a third link opens below the hand, a small link leans on the middle span,
   * then tilegold at the link either side of the grip */
  recall_chain: { 1: { 11: '.o..o.' }, 2: { 4: '.....o', 5: '.....o' },
                  3: { 9: '.g..g.' } },
  /* a shim ring at the butt, quarterturn bronze packed through the head so it
   * reads square, then a second course down the back of the larger jaw and the
   * grip closing over the doubled shank */
  toolwrights_spanner: { 1: { 11: '.o..o.' }, 2: { 0: '.g.g..', 3: '...go.' },
                         3: { 2: 'o.....', 9: '..uu..' } },
};

/* forge.py grades every rung narrow | standard | broad and it is the one thing
 * the grids cannot derive for themselves: the Needle is still narrow at rung
 * nine and the Maul is already broad at rung one. The band is the maximum
 * COLUMN SPAN the weapon may occupy inside its six-wide box.
 *
 * WEAPON_BAND is the fallback for the families forge.py does not forge — a
 * villager's spear has no rung table behind it — and `_weapon.silhouette`
 * overrides it whenever the data actually carries one. */
const BAND_SPAN = { narrow: 4, standard: 5, broad: 6 };
const WEAPON_BAND = {
  sword:  ['narrow', 'standard', 'broad', 'broad', 'broad', 'broad'],
  sabers: ['narrow', 'standard', 'standard', 'broad', 'broad', 'broad'],
  dagger: ['narrow', 'narrow', 'standard', 'standard', 'standard', 'standard'],
  axe:    ['broad', 'broad', 'broad', 'broad', 'broad', 'broad'],
  hammer: ['broad', 'broad', 'broad', 'broad', 'broad', 'broad'],
  spear:  ['narrow', 'standard', 'standard', 'broad', 'broad', 'broad'],
  lance:  ['narrow', 'standard', 'standard', 'broad', 'broad', 'broad'],
  staff:  ['narrow', 'standard', 'broad', 'broad', 'broad', 'broad'],
  bow:    ['standard', 'standard', 'standard', 'standard', 'broad', 'broad'],
  relic:  ['narrow', 'narrow', 'standard', 'standard', 'broad', 'broad'],
};

/* The grids above are drawn inside their band, and this is the net under them:
 * it trims from whichever edge is carrying less of the weapon, so a future rung
 * that overreaches loses the overreach rather than the silhouette. A no-op on
 * everything authored here, which is the point — the band is a contract the
 * table keeps, not a filter the table is passed through. */
function bandTrim(grid, span) {
  let lo = 6, hi = -1;
  for (let y = 0; y < grid.length; y++) {
    const row = grid[y];
    for (let x = 0; x < row.length; x++) {
      if (row[x] === '.' || row[x] === ' ') continue;
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
  }
  if (hi < 0 || hi - lo + 1 <= span) return grid;
  let left = 0, right = 0;
  for (let y = 0; y < grid.length; y++) {
    if (grid[y][lo] && grid[y][lo] !== '.') left++;
    if (grid[y][hi] && grid[y][hi] !== '.') right++;
  }
  const cut = left <= right ? lo : hi;
  const out = grid.map(r => r.slice(0, cut) + '.' + r.slice(cut + 1));
  return bandTrim(out, span);
}

/* The grid in the hand, for a family at a rung. `line` and `band` come off the
 * `_weapon` dict when the data has them and are ignored when it does not, so a
 * villager holding a bare `weapon: 'spear'` still gets a spear. */
function weaponGrid(key, rung, line, band, half) {
  const useLine = line && HERO_WEAPON_LINES[line];
  const ladder = useLine || HERO_WEAPON_LADDER[key] || HERO_WEAPON_LADDER.sword;
  const r = clamp(rung | 0, 0, ladder.length - 1);
  const span = BAND_SPAN[band] || BAND_SPAN[(WEAPON_BAND[key] || WEAPON_BAND.sword)[r]];
  // The half step lands BEFORE the band net, not after, so a detail that
  // overreaches is trimmed like anything else rather than quietly widening a
  // line that forge.py graded narrow.
  const steps = useLine ? HALF_STEP_LINES[line] : (HALF_STEP[key] || HALF_STEP.sword);
  const strip = half && steps && steps[r];
  return bandTrim(strip ? overlay(ladder[r], strip) : ladder[r], span);
}

/* Rung one of every family, which is what an unforged weapon of no particular
 * rarity is holding. Kept as its own name because HERO_WEAPON_KEYS is mirrored
 * in items.py and a key that stops existing here draws the wrong thing there. */
const HERO_WEAPONS = {};
for (const k in HERO_WEAPON_LADDER) HERO_WEAPONS[k] = HERO_WEAPON_LADDER[k][1];

/* Where the lead hand is, per facing: [ox, oy] of the weapon box. */
const WEAPON_ANCHOR = {
  down:  [10, 6], up: [1, 5], left: [-1, 6], right: [11, 6],
};

/* ================================================================
 * ARMOUR — six pieces, authored as SHAPE
 * ================================================================
 * gauntlet/items.py ARMOR_TIERS grades every piece 0..4 by integrity and the
 * server ships the grade on every state payload inside `_pieces`. A recolour is
 * not loot. A player who finds the Mirrorbright Helm has to SEE a helm — a
 * crest, a different head — or the reward loop has nothing to stand on. So
 * every piece here changes the OUTLINE first and the colour second, and a
 * damaged piece is authored damaged: a notched crown, a caved chest panel, a
 * punched shield boss, a sole parting from its upper. The repair loop only
 * means something if the damage is visible.
 *
 * Each piece is a set of sparse strips overlaid onto the character's OWN grids
 * — helmet and chestplate onto the body, gauntlets onto the arms, greaves onto
 * the legs, the mantle onto the hem — before any of it is merged. That ordering
 * is the entire design. mergeGrids() then applyRim() then rimLowLeft() light ONE
 * silhouette once; a pauldron lit on a layer of its own is a sticker on a
 * shoulder and you can see it from across the room.
 *
 * THE BUDGET. Fifteen colours, and armour does not get to bring its own: it is
 * paid for by the materials it COVERS. A helm hides the hair's lit edge, a
 * backplate hides the lit back of the cloak, a breastplate hides the tunic's lit
 * panel — so H, C and T resolve back to h, c and t the moment armour is worn,
 * and the three slots that frees become metal shadow, metal mid and the boot
 * leather. Fifteen bare, fifteen armoured. The metal is the same ramp the blade
 * is cut from, because items.py hands the whole kit one metal colour on purpose.
 */

export const HERO_ARMOR_PIECES = ['helmet', 'chestplate', 'gauntlets', 'boots', 'shield', 'legendary'];

/* Integrity floors, mirroring ARMOR_TIERS. `at` arrives already snapped to one
 * of these; a raw integrity works too, so a caller may hand us the world's own
 * armour dict without translating it first. */
const ARMOR_AT = [0, 25, 50, 75, 100];
export const HERO_ARMOR_TIERS = ARMOR_AT.length;

function tierOf(at) {
  const v = Number(at);
  if (!(v >= 0)) return 0;
  let i = 0;
  while (i + 1 < ARMOR_AT.length && v >= ARMOR_AT[i + 1]) i++;
  return i;
}

const BARE_ARMOR = {
  helmet: -1, chestplate: -1, gauntlets: -1, boots: -1, shield: -1, legendary: -1,
  any: false, key: '......',
};

/* What the hero is wearing, as six tiers. -1 is "not worn at all", which is a
 * different thing from tier 0, "worn and in pieces". Accepts the server's
 * `_pieces` list or a plain {piece: integrity} dict. */
export function heroArmor(opts) {
  const o = opts || {};
  const pieces = o._pieces || o.pieces;
  const armor = o.armor || o.armour;
  if (!Array.isArray(pieces) && !armor) return BARE_ARMOR;
  const g = { ...BARE_ARMOR };
  if (Array.isArray(pieces)) {
    for (let i = 0; i < pieces.length; i++) {
      const p = pieces[i];
      if (!p || HERO_ARMOR_PIECES.indexOf(p.piece) < 0) continue;
      g[p.piece] = tierOf(p.at);
    }
  }
  if (armor && typeof armor === 'object') {
    for (const piece of HERO_ARMOR_PIECES) {
      if (armor[piece] != null) g[piece] = tierOf(armor[piece]);
    }
  }
  // The Legendary Plate at zero is not damaged, it is UNBUILT — it is still on
  // the Armorer's wall. hero_look() refuses to paint it and so do we: dressing
  // a player in armour they have not earned is worse than showing them nothing.
  if (g.legendary <= 0) g.legendary = -1;
  let any = false, key = '';
  for (const piece of HERO_ARMOR_PIECES) {
    if (g[piece] >= 0) any = true;
    key += g[piece] < 0 ? '.' : String(g[piece]);
  }
  g.any = any; g.key = key;
  return g;
}

/* The blade's rung on its own six-step table. items.py grades the weapon by
 * RARITY rather than by integrity, so it is read separately from the armour. */
const WEAPON_RUNGS = ['Rusted', 'Honed', 'Tempered', 'Runed', 'Legendary', 'Mythic'];

function weaponRung(o) {
  const w = o && o._weapon;
  if (!w) return 1;
  if (Number.isFinite(w.rung)) return clamp(w.rung | 0, 0, WEAPON_RUNGS.length - 1);
  const i = WEAPON_RUNGS.indexOf(String(w.name || ''));
  return i < 0 ? 1 : i;
}

/* Which forged LINE this is, when it is one. forge.hero_weapon_look() ships it
 * because `key` cannot carry it: two blades share `relic` and two share
 * `hammer`, so without this the Chain is the Calipers and the Spanner is the
 * Maul. Anything the line table does not know falls back to the family. */
function weaponLine(o) {
  const w = o && o._weapon;
  const id = w && w.line;
  return typeof id === 'string' && HERO_WEAPON_LINES[id] ? id : '';
}

/* The band the data asked for, if it asked. forge.py grades every rung
 * narrow | standard | broad; items.py does not, and an unforged weapon falls
 * back to WEAPON_BAND for its family. */
function weaponBand(o) {
  const w = o && o._weapon;
  const b = w && w.silhouette;
  return typeof b === 'string' && BAND_SPAN[b] ? b : '';
}

/* Whether this tier is the SECOND forged tier standing on its hero rung.
 * forge.hero_weapon_look() sends it because nothing here can work it out: two
 * tiers arrive with the same `rung` and differ only in `trim`, and without this
 * flag the upper of the two is a recolour of the lower. Absent on anything the
 * forge did not make, which is correct — a villager's spear has no half step. */
function weaponHalf(o) {
  const w = o && o._weapon;
  return w && w.half ? 1 : 0;
}

/* ---------- strip surgery ----------
 *
 * A strip is a sparse {rowIndex: 'row'} overlay in the SAME sixteen-wide space
 * as the grid it lands on, so a helmet strip can be read straight down the
 * column against the body rows it covers. '.' leaves what is underneath — the
 * contract mergeGrids and drawGrid already use — and 'x' is the one addition:
 * it ERASES, which is how a broken crest takes a notch out of the silhouette
 * instead of politely declining to draw over it.
 */
const ERASE = 'x';
const flipRow = (r) => r.split('').reverse().join('');

function overlay(grid, strip) {
  if (!strip) return grid;
  const out = grid.slice();
  for (const k in strip) {
    const y = +k;
    if (y < 0 || y >= out.length) continue;
    out[y] = overlayRow(out[y], strip[k]);
  }
  return out;
}

function overlayRow(under, over) {
  const row = under.split('');
  for (let x = 0; x < over.length && x < row.length; x++) {
    if (over[x] !== '.') row[x] = over[x];
  }
  return row.join('');
}

/* Resolve the erase glyph. Run on the merged grid and BEFORE applyRim, so the
 * shading pass sees the notch as real air and lights the new edge it made. */
function stripErase(grid) {
  for (let y = 0; y < grid.length; y++) {
    if (grid[y].indexOf(ERASE) >= 0) grid[y] = grid[y].split(ERASE).join('.');
  }
  return grid;
}

/* Substitute glyphs inside a column window. Used where a piece changes a
 * MATERIAL rather than a shape — a gauntlet turning a bare hand to steel — and
 * it has to be windowed or a hand substitution repaints the face. */
function swapIn(grid, from, to, x0, x1) {
  const out = grid.slice();
  for (let y = 0; y < out.length; y++) {
    const row = out[y].split('');
    let hit = false;
    for (let x = x0; x <= x1 && x < row.length; x++) {
      const i = from.indexOf(row[x]);
      if (i >= 0) { row[x] = to[i]; hit = true; }
    }
    if (hit) out[y] = row.join('');
  }
  return out;
}

function setCell(grid, y, x, ch) {
  if (y < 0 || y >= grid.length || x < 0 || x >= grid[y].length) return grid;
  const out = grid.slice();
  const row = out[y].split('');
  row[x] = ch;
  out[y] = row.join('');
  return out;
}

/* A piece's tier as a shade of the ONE metal ramp. Damaged metal is dull metal
 * — the same steel, unpolished — so the two lowest tiers walk their authored
 * glyphs one step down the ladder [K, A, m, w] rather than introducing a colour
 * the budget cannot pay for. Works on a grid or on a sparse strip. */
const DULL = { A: 'K', m: 'A', M: 'm', w: 'm' };

function dulled(grid, tier) {
  if (tier > 1) return grid;
  const dullRow = (row) => {
    const cells = row.split('');
    for (let x = 0; x < cells.length; x++) {
      const to = DULL[cells[x]];
      if (to) cells[x] = to;
    }
    return cells.join('');
  };
  if (Array.isArray(grid)) return grid.map(r => (r ? dullRow(r) : r));
  const out = {};
  for (const k in grid) out[k] = dullRow(grid[k]);
  return out;
}

/* ---------- the helmet ----------
 *
 * The head is the most legible part of a sixteen-pixel figure, so this is where
 * a tier-up is felt hardest and where the shape has to do the most work: a
 * notched crown at Split, a wire binding at Bound, a seam at Patched, a real
 * crest at Sound, and at Mirrorbright a crest that clears the top of the box, a
 * nasal bar and cheek guards.
 *
 * The visor deliberately stops at the brow. Seven emotes times two frames are
 * authored into six pixels of face and the brow does most of that work; a full
 * visor would be a better helmet and a dead character, so the top tier gets a
 * T-visor — nasal and cheeks — and the eyes stay in the fight.
 */
const HELM = {
  down: {
    shell: { 2: '..oMmmmmmmmmAo..', 3: '..oMmmmmmmmmAo..', 4: '..oAmmmmmmmmAo..' },
    split: {
      1: '.......x........',
      2: '.......A........',
      3: '.......A........',
      4: '.......A........',
    },
    wire : { 2: '.og..g....g..go.', 3: '.....g....g.....' },
    seam : { 2: '........A.......', 3: '........A.......', 4: '........A.......' },
    cheek: { 5: '...m........m...', 6: '.omm........mmo.', 7: '.omm........mmo.' },
    crest: { 1: '...oggggggggo...' },
    plume: { 0: '......oggo......', 1: '..ooggggggggoo..' },
    nasal: { 5: '.......M........', 6: '.......m........', 7: '.......m........' },
    jaw  : { 8: '....m......m....' },
  },
  up: {
    shell: {
      2: '..oMmmmmmmmmAo..',
      3: '..oMmmmmmmmmAo..',
      4: '..oMmmmmmmmmAo..',
      5: '..ommmmmmmmmmo..',
      6: '..oAmmmmmmmmAo..',
      7: '..oAAmmmmmmAAo..',
    },
    split: {
      1: '.......x........',
      2: '.......A........',
      3: '.......A........',
      4: '.......A........',
    },
    wire : { 2: '.og..g....g..go.', 3: '.....g....g.....' },
    seam : { 2: '........A.......', 3: '........A.......', 4: '........A.......' },
    cheek: { 6: '.omm........mmo.', 7: '.omm........mmo.', 8: '....m......m....' },
    crest: {
      1: '...oggggggggo...',
      2: '.......gg.......',
      3: '.......gg.......',
      4: '.......gg.......',
      5: '.......gg.......',
    },
    plume: {
      0: '......oggo......',
      1: '..ooggggggggoo..',
      2: '.......gg.......',
      3: '.......gg.......',
      4: '.......gg.......',
      5: '.......gg.......',
      6: '.......gg.......',
    },
    nasal: { 8: '...ommmmmmmmo...' },
    jaw  : {},
  },
  left: {
    shell: {
      2: '..oMmmmmmmmmAo..',
      3: '..oMmmmmmmmmAo..',
      4: '..oAmmmmmmmmAo..',
      5: '........mmmmAo..',
      6: '........mmmmAo..',
      7: '........mmmAo...',
    },
    split: { 1: '.......x........', 2: '.......A........', 3: '.......A........' },
    wire : { 2: '.og..g....g..go.', 3: '.....g....g.....' },
    seam : { 2: '.........A......', 3: '.........A......', 4: '.........A......' },
    cheek: { 5: '.om.........mmo.', 6: '.om.........mmo.' },
    crest: { 1: '...oggggggo.....' },
    plume: { 0: '.....oggo.......', 1: '..ooggggggoo....' },
    nasal: { 4: '..om............' },
    jaw  : { 5: '..om............', 7: '...m............' },
  },
};

function mirrorStrip(strip) {
  const out = {};
  for (const k in strip) out[k] = flipRow(strip[k]);
  return out;
}

HELM.right = {};
for (const part in HELM.left) HELM.right[part] = mirrorStrip(HELM.left[part]);

function helmet(body, dir, tier) {
  const H = HELM[dir] || HELM.down;
  let g = overlay(body, dulled(H.shell, tier));
  if (tier === 0) g = overlay(g, H.split);
  if (tier === 1) g = overlay(g, H.wire);
  if (tier === 2) g = overlay(g, H.seam);
  if (tier >= 2) g = overlay(g, H.cheek);
  if (tier === 3) g = overlay(g, H.crest);
  if (tier >= 4) g = overlay(g, H.plume);
  if (tier >= 3) g = overlay(g, H.nasal);
  if (tier >= 4) g = overlay(g, H.jaw);
  return g;
}

/* ---------- the chestplate ----------
 *
 * The pauldrons are the point. A breastplate is interior detail — it changes a
 * shade of the torso and nothing else — but a pauldron changes the WIDTH of the
 * shoulder line, and width is the first thing the eye measures on a figure this
 * small. So the tiers spend outward: no pauldron, a stub, a full cap that
 * reaches the edge of the box, and then gold on the lip of it.
 */
const CHEST = {
  down: {
    plate:  { 10: '...oMmmmmmmAo...', 11: '...oMmmmmmmAo...',
              12: '...oAmmmmmmAo...', 13: '...ooAmmmmAoo...' },
    dent:   { 11: '....AAAA........', 12: '....AAAA........', 13: '...x............' },
    cord:   { 11: '....g..g........', 12: '.....gg.........' },
    // The fauld stands a pixel proud of the hip on each side: a tasset that
    // stops at the body line is a belt, and a belt is not loot.
    tasset: { 15: '..oAmmmmmmmmAo..', 16: '..oAAmmmmmmAAo..' },
    // The gorget: two wings of collar rising BESIDE the neck, into air the
    // bare figure never occupies. The neck itself is left open on purpose —
    // the jaw is half of what the face has to say with.
    cap:    { 8: '..om........mo..' },
    // The finished plate hangs a fauld below the belt, wider than the hem it
    // covers. It is the one thing the top tier adds that the tier below cannot
    // be mistaken for: a chased sunburst is interior detail, and interior detail
    // is invisible at walking pace.
    fauld:  { 17: '.oAmmmmmmmmmmAo.' },
    device: { 10: '.......gg.......', 11: '......gwwg......',
              12: '......g..g......', 13: '.......gg.......' },
  },
  up: {
    plate:  { 10: '...oMmmmmmmAo...', 11: '...oMmmmmmmAo...',
              12: '...oAmmmmmmAo...', 13: '...ooAmmmmAoo...' },
    dent:   { 11: '........AAAA....', 12: '........AAAA....', 13: '............x...' },
    cord:   { 11: '........g..g....', 12: '.........gg.....' },
    tasset: { 15: '..oAmmmmmmmmAo..', 16: '..oAAmmmmmmAAo..' },
    cap:    { 8: '..om........mo..' },
    fauld:  { 17: '.oAmmmmmmmmmmAo.' },
    device: { 11: '.......AA.......', 12: '......AggA......', 13: '.......AA.......' },
  },
  left: {
    plate:  { 10: '.oAmmmmmmmmMo...', 11: '.oAmmmmmmmmMo...',
              12: '.oAmmmmmmmmAo...', 13: '..ooAmmmmmAoo...' },
    // From the side the caved panel has to be caved on the side you can SEE.
    // The front of the ribs is behind the blade on three frames out of four, so
    // the bite is taken out of the back edge where the outline is exposed.
    dent:   { 11: '..AAAA........x.', 12: '..AAAA........x.', 13: '.x..............',
              14: '.............x..' },
    cord:   { 11: '..g..g..........', 12: '...gg...........', 13: '..............g.' },
    tasset: { 15: '..oAmmmmmmmmmAo.', 16: '..oAAmmmmmmmAAo.' },
    // From the side the near shoulder is behind the blade, so the pauldron
    // that can actually be SEEN is the far one, rising over the back of the
    // neck. Authored onto the body rather than onto the arm, because the far
    // arm is not in this frame at all on three frames out of four.
    cap:    { 8: '..........ommo..' },
    fauld:  { 17: '.oAmmmmmmmmmmAo.' },
    device: { 11: '..gg............', 12: '..gw............', 13: '..gg............' },
  },
};
CHEST.right = {};
for (const part in CHEST.left) CHEST.right[part] = mirrorStrip(CHEST.left[part]);

function chestplate(body, dir, tier) {
  const C = CHEST[dir] || CHEST.down;
  let g = overlay(body, dulled(C.plate, tier));
  if (tier <= 1) g = overlay(g, C.dent);
  if (tier === 1) g = overlay(g, C.cord);
  if (tier >= 2) g = overlay(g, dulled(C.cap, tier));
  if (tier >= 3) g = overlay(g, C.tasset);
  if (tier >= 4) g = overlay(g, C.fauld);
  if (tier >= 4) g = overlay(g, C.device);
  return g;
}

/* The shoulder cap. It lands on a layer of its own AFTER the arms so it sits
 * over the deltoid rather than behind it, and it is slid down with whichever
 * arm it caps so it cannot detach on a swing. */
const PAULDRON_H = 5;
const PAULDRON = {
  // The cap row is the one that matters. The bare shoulder line starts two
  // pixels in from the edge of the box, so metal at x0 and x15 on that row is
  // the only place in a sixteen-pixel figure where a pauldron can actually make
  // the hero WIDER rather than merely make him shinier.
  stub: ['.omm........mmo.', '.oAm........mAo.'],
  full: ['ommmo......ommmo', 'oMmmo......ommMo', 'oAmmo......ommAo'],
  lip:  ['.gg..........gg.', '', 'oAggo......oggAo'],
};

/* The first row on which an arm exists inside a column window. The arms swing a
 * row out of phase — HERO_ARMS drops the left hand on frame 0 and the right on
 * frame 2 — so a pauldron authored at a fixed height detaches from its own
 * shoulder twice a cycle. Reading it off the arm grid costs one scan and is
 * right for every facing, frame and pose without a table. */
function armTop(arms, x0, x1) {
  for (let y = 0; y < arms.length; y++) {
    const row = arms[y];
    for (let x = x0; x <= x1 && x < row.length; x++) if (!EMPTY(row[x])) return y;
  }
  return -1;
}

/* Keep columns [x0,x1] of a strip and blank the rest: a side view shows one
 * arm, and on the pass frame it is the FAR one. */
function halfRow(row, x0, x1) {
  let out = '';
  for (let x = 0; x < HERO_W; x++) {
    out += (x >= x0 && x <= x1 && x < row.length) ? row[x] : '.';
  }
  return out;
}

function pauldrons(arms, tier) {
  const shape = tier >= 3 ? PAULDRON.full : PAULDRON.stub;
  const grid = [];
  for (let y = 0; y < PAULDRON_H; y++) grid.push('.'.repeat(HERO_W));
  const sides = [[0, 5, armTop(arms, 0, 4)], [10, 15, armTop(arms, 11, 15)]];
  for (const side of sides) {
    const x0 = side[0], x1 = side[1], top = side[2];
    if (top < 0) continue;
    for (let y = 0; y < shape.length; y++) {
      const ty = y + top;
      if (ty >= PAULDRON_H || !shape[y]) continue;
      grid[ty] = overlayRow(grid[ty], halfRow(shape[y], x0, x1));
      if (tier >= 4 && PAULDRON.lip[y]) {
        grid[ty] = overlayRow(grid[ty], halfRow(PAULDRON.lip[y], x0, x1));
      }
    }
  }
  return dulled(grid, tier);
}

/* ---------- the gauntlets ----------
 *
 * The hand is two pixels. Everything a gauntlet can say has to be said in those
 * two and in the forearm above them, so the tiers say it by MASS: cloth wraps,
 * then a knuckle plate on the outer pixel only, then both, then a bracer up the
 * forearm, and at the top a fist a pixel deeper than a bare hand — which is the
 * one thing on the whole arm that changes the outline.
 */
/* Grow one column DOWNWARD from a hand, pushing its own outline ahead of it.
 * The hands sit hard against the left and right walls of a sixteen-wide box, so
 * down is the only direction a glove has left: every pixel of extra mass a
 * gauntlet claims has to come off the bottom of the fist. */
function growDown(grid, x, row, depth, mat) {
  let g = grid;
  for (let k = 1; k <= depth; k++) {
    const y = row + k;
    if (y >= g.length || x < 0 || x >= HERO_W) break;
    const ch = g[y][x];
    if (!EMPTY(ch) && ch !== 'o') break;      // something solid is already there
    g = setCell(g, y, x, mat);
    if (y + 1 < g.length && (EMPTY(g[y + 1][x]) || g[y + 1][x] === 'o')) {
      g = setCell(g, y + 1, x, 'o');
    }
  }
  return g;
}

/* How far below the knuckles each finger reaches, per tier: [outer, inner].
 * This table IS the gauntlet tier — the colour follows it, not the other way
 * round. Wraps are a soft tail off the palm; a half gauntlet plates the knuckle
 * side only and leaves the fingers open; riveted closes both; fitted carries a
 * cuff a pixel further down the outside; and the Keysmith's is a fist a full
 * two pixels deeper than a bare hand on both sides. */
const GAUNTLET_REACH = [[1, 0], [1, 1], [2, 1], [2, 2], [3, 2]];

function gauntlets(arms, tier) {
  // Bare Wraps are cloth, not plate: the tunic ramp, which is the gambeson the
  // rest of the kit is strapped over. Everything above tier zero is steel.
  const hand = tier === 0 ? 't' : 'm';
  const four = hand + hand + hand + hand;
  let g = swapIn(swapIn(arms, 'sSvV', four, 0, 4), 'sSvV', four, 11, 15);
  const cells = [];
  for (let y = 0; y < g.length; y++) {
    for (let x = 0; x < g[y].length; x++) if (g[y][x] === hand) cells.push([y, x]);
  }
  if (!cells.length) return g;
  const reach = GAUNTLET_REACH[clamp(tier, 0, GAUNTLET_REACH.length - 1)];
  for (const bound of [[0, 7], [8, 15]]) {
    const mine = cells.filter(c => c[1] >= bound[0] && c[1] <= bound[1]);
    if (!mine.length) continue;
    let row = -1;
    for (const c of mine) if (c[0] > row) row = c[0];
    const xs = mine.filter(c => c[0] === row).map(c => c[1]).sort((a, b) => a - b);
    const outer = bound[0] === 0 ? xs[0] : xs[xs.length - 1];
    const inner = bound[0] === 0 ? xs[xs.length - 1] : xs[0];
    // A knuckle plate catches the light; at tier one it is the ONLY plate and
    // the finger side is still open cloth, which is what "knuckle plates only,
    // the fingers left open" looks like at two pixels.
    if (tier >= 1) g = setCell(g, row, outer, 'M');
    if (tier === 1) g = setCell(g, row, inner, 't');
    // A bracer up the forearm. This is where the bulk comes from: the arm stops
    // tapering into the hand and carries plate to the elbow.
    if (tier >= 3) for (const x of xs) if (row - 1 >= 0 && !EMPTY(g[row - 1][x])) g = setCell(g, row - 1, x, 'm');
    if (tier >= 4) {
      for (const x of xs) if (row - 2 >= 0 && !EMPTY(g[row - 2][x])) g = setCell(g, row - 2, x, 'A');
      g = setCell(g, row - 1, inner, 'g');     // the vault-key motif, etched
    }
    // The mass. Every tier grows the fist DOWNWARD by its own amount, so the
    // silhouette of the hand changes at every rung and not just the shade of
    // it: a wrap is one soft pixel off the palm, a Keysmith's fist is two of
    // plate on both fingers.
    g = growDown(g, outer, row, reach[0], tier === 0 ? 't' : 'm');
    g = growDown(g, inner, row, reach[1], tier === 0 ? 't' : (tier >= 3 ? 'm' : 'A'));
    // The outline follows the fist out. Without this the hand grows downward
    // inside an outline that still describes the bare hand, and on the poses
    // where the arm is tucked against the torso — the cast, the side views —
    // the whole gain is hidden behind the body. A heavier hand has a heavier
    // edge; that edge is the part of it the player can see from across a room.
    g = growDown(g, outer + (bound[0] === 0 ? -1 : 1), row, reach[0], 'o');
  }
  return g;
}

/* ---------- the boots ----------
 *
 * Worked off the leg grid's own glyphs rather than off a table, because there
 * are sixteen leg frames and a table would be wrong in at least one of them.
 * 'p' is the trouser, 'b' the boot upper, 'k' the sole: raise the shaft by
 * promoting a trouser row to boot, greave the shin by promoting the row above
 * that to plate, and at the top tier widen the sole so the foot lands heavier.
 */
/* Grow every outer edge of one glyph a pixel further from the centre line,
 * pushing its outline ahead of it. A boot is wider than the leg in it; that is
 * the whole reason a boot is visible at sixteen pixels. */
function flareOut(grid, glyph, mat) {
  const grow = [];
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      if (grid[y][x] !== glyph) continue;
      const step = x < HERO_W / 2 ? -1 : 1;
      const nx = x + step;
      if (nx < 0 || nx >= HERO_W) continue;
      if (grid[y][nx] === glyph) continue;
      grow.push([y, nx, nx + step]);
    }
  }
  let g = grid;
  for (const c of grow) {
    g = setCell(g, c[0], c[1], mat);
    if (c[2] >= 0 && c[2] < HERO_W && EMPTY(g[c[0]][c[2]])) g = setCell(g, c[0], c[2], 'o');
  }
  return g;
}

function boots(legs, tier) {
  let g = legs.slice();
  const is = (y, x, ch) => y >= 0 && y < g.length && x >= 0 && x < g[y].length && g[y][x] === ch;
  const shafts = () => {
    const out = [];
    for (let y = 0; y < g.length; y++) {
      for (let x = 0; x < g[y].length; x++) if (g[y][x] === 'p' && is(y + 1, x, 'b')) out.push([y, x]);
    }
    return out;
  };
  // Taller shaft: a trouser pixel sitting directly on a boot pixel becomes boot.
  if (tier >= 2) for (const c of shafts()) g = setCell(g, c[0], c[1], 'b');
  // Greaved at the shin — and greaved in the metal ramp the rest of the kit is
  // cut from, not in a leather of its own, because there is no slot for one.
  if (tier >= 3) {
    const plate = shafts();
    for (const c of plate) g = setCell(g, c[0], c[1], tier >= 4 ? 'm' : 'A');
    // The greave stands proud of the shin, which is the tier the leg first gets
    // WIDER rather than merely harder.
    g = flareOut(g, tier >= 4 ? 'm' : 'A', tier >= 4 ? 'm' : 'A');
  }
  // A bound boot is a boot with cord round it and it is a size bigger than the
  // bare leg was. Every tier from here carries that bulk; the shaft the tier
  // above raised then carries it further up the calf on its own.
  if (tier >= 1) g = flareOut(g, 'b', 'b');
  // The sole parting from the upper at the toe: a real notch, not a shade.
  if (tier === 0) {
    for (let y = 0; y < g.length; y++) {
      for (let x = 0; x < g[y].length; x++) {
        if (g[y][x] === 'k' && !is(y + 1, x, 'k')) { g = setCell(g, y, x, ERASE); break; }
      }
    }
  }
  // Wrapped at the ankle to keep them together.
  if (tier === 1) {
    for (let y = 0; y < g.length; y++) {
      const x = g[y].indexOf('b');
      if (x >= 0) g = setCell(g, y, x, 'g');
    }
  }
  // A heavier foot: the sole grows a pixel outward and pushes its own outline
  // out with it, so the stance widens instead of the boot merely darkening.
  if (tier >= 4) {
    const grow = [];
    for (let y = 0; y < g.length; y++) {
      for (let x = 0; x < g[y].length; x++) {
        if (g[y][x] !== 'k') continue;
        const step = x < 8 ? -1 : 1;
        if (!is(y, x + step, 'k')) grow.push([y, x + step, x + step + step]);
      }
    }
    for (const c of grow) {
      if (c[1] < 0 || c[1] >= HERO_W) continue;
      g = setCell(g, c[0], c[1], 'k');
      if (c[2] >= 0 && c[2] < HERO_W && EMPTY(g[c[0]][c[2]])) g = setCell(g, c[0], c[2], 'o');
    }
  }
  return g;
}

/* ---------- the shield ----------
 *
 * An actual shield on the off arm, visible from every facing — which means it
 * also has to be OCCLUDED correctly from two of them. The weapon hand is known
 * per facing from WEAPON_ANCHOR, so the shield takes the other one; from the
 * side that other arm is on the far side of the torso, so the shield is spliced
 * in BEHIND the body and reads as a crescent around the shoulder and the hip
 * rather than as a plate stuck on the chest.
 *
 * The hole at tier zero is deep shadow rather than an erase: a punched boss
 * shows the arm behind it, not the sky.
 */
/* The rungs are told apart by HEIGHT before anything else. A Broken Boss is
 * a shield someone has lost a third of; an Aegis covers a man from shoulder to
 * knee. Two shields that differ only in what is engraved on the face are one
 * shield painted twice, and the player upgrading between them sees nothing. */
const SHIELD = [
  ['.oo..', 'ommo.', 'omAoo', 'omKKo', 'ommAo', 'oAmAo', '.ooo.'],
  ['.ooo.', 'ommmo', 'omgmo', 'ogggo', 'omgmo', 'ommAo', 'oAmAo', '.ooo.'],
  ['.ooo.', 'ommmo', 'omMmo', 'omMmo', 'ommmo', 'ommmo', 'ommAo', 'oAmAo', '.ooo.'],
  ['.ooo.', 'ommmo', 'omMmo', 'omgmo', 'omgmo', 'ommmo', 'ommmo', 'ommAo', 'oAmAo', '.ooo.'],
  ['.ooo.', 'ogggo', 'omMmo', 'omgmo', 'omwmo', 'omgmo', 'ommmo', 'ommmo', 'ogggo', 'oAmAo', '.ooo.'],
];

/* Seen from behind: the enarmes, not the face. Authored per rung as well, so
 * turning the hero's back on the camera does not flatten three shields into
 * one. The bottom two rungs are never seen from behind — a shield that small
 * hides entirely behind the shoulder — so they are not authored. */
const SHIELD_BACK = [
  null, null,
  ['.ooo.', 'oAAAo', 'oAgAo', 'ogggo', 'oAgAo', 'oAAAo', 'oAAAo', 'oAAAo', '.ooo.'],
  ['.ooo.', 'oAAAo', 'oAgAo', 'ogggo', 'oAgAo', 'oAAAo', 'oAAAo', 'oAAAo', 'oAAAo', '.ooo.'],
  ['.ooo.', 'oAAAo', 'oAgAo', 'ogggo', 'ogggo', 'oAgAo', 'oAAAo', 'oAAAo', 'oAAAo', 'oAAAo', '.ooo.'],
];

const SHIELD_SIDE = {
  down:  { ox: 0,  front: true },
  up:    { ox: 11, front: true },
  left:  { ox: 11, front: false },
  right: { ox: 0,  front: false },
};

function shieldGrid(dir, tier) {
  const t = clamp(tier, 0, SHIELD.length - 1);
  const back = dir === 'up' ? SHIELD_BACK[t] : null;
  return dulled(back || SHIELD[t], t);
}

/* ---------- the legendary panoply ----------
 *
 * The one piece that changes the figure rather than dressing it: a collar
 * raised beside the jaw, a shoulder line a pixel wider on each side, and a
 * cloak long enough to reach the boots — which then sways on the hem's OWN
 * shift, so the mantle moves because the character moves rather than because
 * something extra is animating it.
 */
const MANTLE = {
  down:  { 8: '..oc........co..', 9: '.occcccccccccco.', 10: 'occcccccccccccco' },
  up:    { 8: '..oc........co..', 9: '.occcccccccccco.', 10: 'occcccccccccccco' },
  left:  { 8: '.oc........co...', 9: '.occcccccccccco.', 10: 'occcccccccccccco' },
};
MANTLE.right = mirrorStrip(MANTLE.left);

const COLLAR = { 9: '.....gggggg.....' };
const COLLAR_MARK = { 9: '.......ww.......' };

/* Finished, the panoply stands its collar UP beside the jaw — two rows of it,
 * outside the line the bare head has ever occupied. Every other thing the top
 * rung adds (the mark on the collar, the brightest metal) is interior, and
 * interior is the half of a sprite a player cannot see moving. */
const HIGH_COLLAR = {
  down: { 6: '..oc........co..', 7: '..oc........co..' },
  up:   { 6: '..oc........co..', 7: '..oc........co..' },
  left: { 6: '.oc.........co..', 7: '.oc.........co..' },
};
HIGH_COLLAR.right = mirrorStrip(HIGH_COLLAR.left);

const CLOAK = {
  down: {
    short: ['..occcccccccco..', '.occcccccccccco.', '.occcccccccccco.', '..ovvvvvvvvvvo..'],
    long:  ['..occcccccccco..', '.occcccccccccco.', 'occcccccccccccco',
            'occcccccccccccco', '.ovvvvvvvvvvvvo.', '..ovvvvvvvvvvo..'],
  },
  up: {
    short: ['..occcccccccco..', '.occcccccccccco.', '.occcccccccccco.', '.ovvvvvvvvvvvvo.'],
    long:  ['..occcccccccco..', '.occcccccccccco.', 'occcccccccccccco',
            'occcccccccccccco', 'occvvvvvvvvvvcco', '.ovvvvvvvvvvvvo.'],
  },
  left: {
    short: ['..occcccccccco..', '.occccccccccco..', '.occccccccccco..', '..ovvvvvvvvo....'],
    long:  ['..occcccccccco..', '.occccccccccco..', 'occcccccccccco..',
            'occcccccccccco..', '.ovvvvvvvvvvo...', '..ovvvvvvvvo....'],
  },
};
CLOAK.right = {
  short: CLOAK.left.short.map(flipRow),
  long: CLOAK.left.long.map(flipRow),
};

/* ---------- one dressed character ----------
 *
 * Everything above lands on the hero's own grids and NOTHING is rasterised
 * here. That is deliberate, and it is the whole reason the armour disappears
 * into the figure: heroFrame() still merges one grid and lights it once, so a
 * pauldron is part of that silhouette by the time the light runs over it.
 */
function armorLayers(dir, gear, parts) {
  let body = parts.body, arms = parts.arms, legs = parts.legs, hem = parts.hem;
  if (gear.legendary >= 0) {
    if (gear.legendary >= 2) body = overlay(body, MANTLE[dir] || MANTLE.down);
    body = overlay(body, COLLAR);
    if (gear.legendary >= 4) {
      body = overlay(body, HIGH_COLLAR[dir] || HIGH_COLLAR.down);
      body = overlay(body, COLLAR_MARK);
    }
    const table = CLOAK[dir] || CLOAK.down;
    hem = gear.legendary >= 3 ? table.long : table.short;
  }
  if (gear.chestplate >= 0) body = chestplate(body, dir, gear.chestplate);
  if (gear.helmet >= 0) body = helmet(body, dir, gear.helmet);
  if (gear.boots >= 0) legs = boots(legs, gear.boots);
  if (gear.gauntlets >= 0) arms = gauntlets(arms, gear.gauntlets);
  const over = gear.chestplate >= 1 ? pauldrons(arms, gear.chestplate) : null;
  return { body: body, arms: arms, legs: legs, hem: hem, over: over };
}

/* Runework along the fuller, lit from inside. items.py starts saying that at
 * the Runed rung and the trim colour it ships with it is the light. */
function runeBlade(grid, rung) {
  /* Which rows have a body worth etching. This used to be 'rows containing M,
   * and give up below three of them', which quietly returned the bare grid for
   * six of the ten families — the dagger, the axe, the spear, the bow, the
   * staff and the relic have one or two rows of 'M' between them, or none at
   * all. Four of the six forged lines hold one of those, so the Runed rung and
   * the two above it changed nothing whatsoever on the weapon in the hand.
   *
   * So the search falls through the interior vocabulary until it finds a body:
   * 'M' is the bright face of a blade, 'm' its shaded side, and 'w'/'g' are the
   * light and the trim on the families that are more fitting than blade. The
   * first of those with something to mark wins. */
  const rowsWith = (ch) => {
    const rows = [];
    for (let y = 0; y < grid.length; y++) if (grid[y].indexOf(ch) >= 0) rows.push(y);
    return rows;
  };
  let mark = 'M';
  let rows = rowsWith('M');
  for (const ch of ['m', 'w', 'g']) {
    if (rows.length >= 2) break;
    const alt = rowsWith(ch);
    if (alt.length > rows.length) { rows = alt; mark = ch; }
  }
  if (rows.length < 2) return grid;
  const out = grid.slice();
  /* One etch colour, chosen to contrast with the body it is being cut into: the
   * trim against metal, and metal light against a body that IS the trim.
   *
   * There is deliberately no SECOND colour for the top rungs, because this
   * palette does not have one to give. heroPalette resolves 'M' and 'w' to the
   * same value, and on an unarmoured hero 'm' collapses into them too, so
   * "trim at Runed, white-hot at Mythic" was two rungs painting the identical
   * pixel — a switch in name only, and invisible on exactly the hero the player
   * spends the early game as. So the Mythic rung escalates in DENSITY instead:
   * every row that can take a mark takes one, tip to tang, rather than every
   * other row between them. That reads in both palettes. */
  const glyph = mark === 'g' ? 'M' : 'g';
  /* Below the top rung the mark skips the tip and the tang — it belongs on the
   * blade, not on the point — and steps every other row. At the top rung it
   * runs the whole body. A two-row body has no tip to skip, so it takes the
   * rows it has; that is the arrangement that leaves one mark rather than none. */
  const whole = rung >= 5 || rows.length <= 2;
  const first = whole ? 0 : 1;
  const last = whole ? rows.length : rows.length - 1;
  const step = whole ? 1 : 2;
  for (let i = first; i < last; i += step) {
    const y = rows[i], x = out[y].indexOf(mark);
    if (x >= 0) out[y] = out[y].slice(0, x) + glyph + out[y].slice(x + 1);
  }
  return out;
}

/* massBlade() used to live here. It widened the heaviest row of the weapon by
 * one pixel of outline at Legendary and a second at Mythic, which was the
 * cheapest way to make a colour-only ladder move at all — and it bought exactly
 * one or two outline changes across six rungs, always in the same place, on
 * every family at once. HERO_WEAPON_LADDER above now draws all six rungs, so a
 * derived pixel of mass would only fight the drawing: it grows from whatever row
 * happens to be widest, which on a narrow-band line is how the Needle ends up
 * as wide as the Maul. The band is a promise the table keeps; bandTrim() is the
 * net under it. Nothing calls massBlade any more and nothing should.
 */

/* The blade leans away from the body on a cast. The grip keeps the anchor —
 * lootart.js mirrors that anchor and moving it would detach every overlay it
 * draws — and only the upper half of the weapon swings, which is what the arm
 * is doing underneath it. */
function tiltWeapon(grid, outward) {
  if (outward > 0) return { grid: shiftRows(grid.map(r => r + '.'), 0, 5, 1), dx: 0 };
  return { grid: shiftRows(grid.map(r => '.' + r), 0, 5, -1), dx: -1 };
}

const DEFAULT_HERO = {
  cloak: '#3f6fa8', tunic: '#5a4a6a', skin: '#e8b88a', hair: '#4a3050',
  boot: '#40312c', trim: '#d8b04a', metal: '#c3cbd8', weapon: 'sword',
  emote: 'neutral',
  // §E. `class_id` takes the server's `sprite` field (classes.py:359, exposed by
  // class_view()). Absent, the generic hero renders exactly as before, which is
  // what every non-class screen in the game still wants.
  class_id: null, body: 'a',
};

/* Equipment tints the hero rather than replacing him: a region palette can be
 * passed straight in and its accent becomes the trim. */
function heroOpts(opts) {
  if (!opts) return { ...DEFAULT_HERO };
  if (opts.sky && opts.ground) return { ...DEFAULT_HERO, trim: opts.accent || DEFAULT_HERO.trim };
  return { ...DEFAULT_HERO, ...opts };
}

/* ---------- the emote vocabulary ----------
 *
 * Seven states, shared by the hero and by every portrait, and chosen to cover
 * what this game actually does to a character rather than to tile a wheel of
 * emotions: a mentor is PLEASED by the solution that lands, STRAINED by the one
 * that nearly worked, ALARMED when the clock bites, STUBBORN when you argue,
 * DELIGHTED when you pass and DEFEATED when you do not. Everything else is
 * NEUTRAL, and neutral still blinks.
 */
export const EMOTE_KEYS = [
  'neutral', 'pleased', 'strained', 'alarmed', 'stubborn', 'delighted', 'defeated',
];

/* Writing does not speak in our seven words, so translate here instead of
 * making every call site remember them. Anything unknown lands on neutral,
 * which is the one failure mode that never looks like a bug. */
export const EMOTE_ALIAS = {
  idle: 'neutral', calm: 'neutral', think: 'neutral', thinking: 'neutral', wait: 'neutral',
  happy: 'pleased', glad: 'pleased', approve: 'pleased', warm: 'pleased', smile: 'pleased',
  hurt: 'strained', pain: 'strained', effort: 'strained', focus: 'strained',
  grim: 'strained', worried: 'strained', doubt: 'strained', wince: 'strained',
  shock: 'alarmed', surprise: 'alarmed', surprised: 'alarmed', fear: 'alarmed',
  afraid: 'alarmed', startled: 'alarmed',
  angry: 'stubborn', anger: 'stubborn', stern: 'stubborn', resolve: 'stubborn',
  determined: 'stubborn', defiant: 'stubborn', scowl: 'stubborn', glare: 'stubborn',
  joy: 'delighted', laugh: 'delighted', triumph: 'delighted', victory: 'delighted',
  proud: 'delighted', win: 'delighted',
  sad: 'defeated', loss: 'defeated', lose: 'defeated', beaten: 'defeated',
  tired: 'defeated', weary: 'defeated', ashamed: 'defeated',
};

export function emoteKey(name) {
  const k = String(name == null ? '' : name).toLowerCase();
  if (EMOTE_KEYS.indexOf(k) >= 0) return k;
  return EMOTE_ALIAS[k] || 'neutral';
}

/* A face holds a frame far longer than a foot does. Faster than this and the
 * two frames read as a flicker rather than as breathing; the settled emotes
 * dwell almost entirely on frame 0 and only dip into frame 1 to blink, while
 * alarm flutters between the two. */
const EMOTE_TIMING = {
  neutral:   { period: 2600, hold: 0.88 },
  pleased:   { period: 1900, hold: 0.64 },
  strained:  { period: 1100, hold: 0.54 },
  alarmed:   { period:  620, hold: 0.50 },
  stubborn:  { period: 2200, hold: 0.80 },
  delighted: { period:  840, hold: 0.50 },
  defeated:  { period: 3200, hold: 0.72 },
};

export const EMOTE_FRAME_COUNT = 2;

/* Which of the two frames a face is on. No wall clock is read in here and
 * nothing is randomised: the same (emote, time, seed) always answers the same,
 * which is what lets the whole thing be tested. The seed only shifts the phase,
 * so two mentors on screen together do not blink in lockstep. */
export function emotePose(emote, timeMs = 0, seed = 0) {
  const key = emoteKey(emote);
  const t = EMOTE_TIMING[key] || EMOTE_TIMING.neutral;
  const phase = (hash(key + ':' + seed) % 1024) / 1024;
  let cycle = ((timeMs / t.period) + phase) % 1;
  if (cycle < 0) cycle += 1;
  return { key, frame: cycle < t.hold ? 0 : 1, cycle };
}

/* ---------- palette ---------- */

/* Fifteen colours, and every one is spoken for:
 *
 *   o  outline          K  deep shadow      R  the rim
 *   s S N  skin, its shadow, and skin in that rim light
 *   h H    hair and its lit edge
 *   c C v  cloak, lit, shadowed
 *   t T    tunic and its lit panel
 *   g      trim          w  specular
 *
 * Everything else the authored grids ask for is an ALIAS onto a colour already
 * paid for. That is the argument for the budget rather than a tax imposed by
 * it: a hard ceiling forces you to decide that deep cloak shadow and dark
 * leather are the same dark, and once you have decided that for the hero you
 * have decided it for the whole cast. Shared ramps are most of why a scene
 * reads as one world; the ceiling is what makes you share them.
 */
export function heroPalette(opts) {
  const o = heroOpts(opts);
  const gear = heroArmor(o);
  const cloak = ramp(o.cloak), tunic = ramp(o.tunic), skin = ramp(o.skin);
  const hair = ramp(o.hair), trim = ramp(o.trim), metal = ramp(o.metal);
  const pal = {
    o: mix(cloak.outline, '#08070e', 0.68),
    K: cloak.shadow2,
    s: skin.base, S: skin.shadow1, N: skin.light1,
    h: hair.base, H: hair.light1,
    c: cloak.base, C: cloak.light1, v: cloak.shadow1,
    t: tunic.base, T: tunic.light1,
    g: trim.base,
    w: mix(metal.light2, '#ffffff', 0.5),
    R: rimTone(trim.light2),
  };
  pal.e = pal.o;                                   // pupils: the outline, not a fourth near-black
  // applyRim() lightens the outline it thinks is facing the light. We do not
  // want that here: the brief is a HEAVY outline with one hot rim inside it, and
  // a lit outline plus a rim just reads as a smeared double edge. So O resolves
  // straight back to the outline and rimLowLeft does all the lighting.
  pal.O = pal.o; pal.D = pal.K; pal.p = pal.K; pal.k = pal.K;
  pal.u = pal.v; pal.d = pal.v;
  pal.M = pal.w; pal.W = pal.w; pal.r = pal.R;
  pal.L = pal.C; pal.B = pal.c;
  // Armour does not get to bring its own colours: it is paid for by the
  // materials it COVERS. A helm hides the hair's lit edge, a backplate hides the
  // lit back of the cloak, a breastplate hides the tunic's lit panel — so H, C
  // and T resolve back to h, c and t, and the three slots that frees become
  // metal shadow, metal mid and the boot leather that `boot` has been naming
  // since the armour tables landed with nothing on the sprite reading it.
  // Fifteen either way, and scripts/verify counts them rather than trusting me.
  if (gear.any) {
    pal.H = pal.h; pal.C = pal.c; pal.T = pal.t; pal.L = pal.c;
    pal.A = metal.shadow1;
    pal.m = metal.base;
    pal.b = ramp(o.boot).base;
  } else {
    // An unarmoured boot still has to be a BOOT and not the shin above it. `v`
    // is a half-step off the trouser's `K` and vanishes at 1x, so bare leather
    // borrows the tunic's entry — already bought, still fifteen.
    pal.A = pal.K; pal.m = pal.w; pal.b = pal.t;
  }
  return pal;
}

/* ================================================================
 * §E. THE CLASS CONTRACT — six silhouettes, two bodies, twelve sprites
 * ================================================================
 * gauntlet/classes.py has carried a `sprite` field since the classes landed and
 * nothing in here ever read it: all six classes rendered the identical hero.
 * These strips are stamped onto the MERGED figure, after the arms and before the
 * erase pass, so a class can cut the silhouette as well as add to it — which is
 * the only way "tell a Berserker from a Seer with the colour off" is winnable.
 *
 * Six shape families, no repeats, because that is what makes the greyscale test
 * pass: rectangle, inverted triangle, bell, slab, asymmetric, point.
 *
 * One strip set serves all four facings. The class tell is a SILHOUETTE event at
 * the edge of the box — a hood peak, a blade tip, a shield edge — and none of
 * those turn with the body the way a torso does.
 */
export const HERO_CLASSES = ['analyst', 'berserker', 'archivist', 'warden', 'artificer', 'seer'];
export const HERO_BODY_TYPES = ['a', 'b'];

const CLASS_RIG = {
  /* RECTANGLE. Straight vertical sides: the arms' break-out is erased, so this
   * is the one class where nothing projects sideways. A thin rod stands over
   * the head — and it stands OFF CENTRE, because the helmet crest at tier 4
   * paints row 0 cols 6..9 and every player wears a helmet at integrity 100
   * from the first frame (engine.py's new-game armour block), so a rod centred
   * on the skull was a tell that one hundred percent of players never saw.
   *
   * It also occupies row 1. The idle-0 pose sinks the head one row
   * (sinkRows(body, 0, 9, 1) in heroFrame) and classShape stamps in UNSUNK
   * grid space, so a rod that lived only on row 0 came away from the skull on
   * four of the twenty-eight views — an 8-connected component count found a
   * 4px bar floating in mid-air on every idle-0 of the bare rig. Row 1 bridges
   * the sink. */
  analyst: {
    0:  '..........oggo..', 1:  '..........oggo..',
    10: 'xo............ox', 11: 'xo............ox',
    12: 'xo.wwwwwwwwww.ox',                      // calipers, held open across the chest
    13: 'xo............ox', 14: 'xo............ox', 15: 'xo............ox',
  },
  // INVERTED TRIANGLE. Widest shoulders in the set, and two blade tips standing
  // above the shoulder line — the only upward double-break in the cast.
  berserker: {
    3:  'ow............wo', 4:  'ow............wo', 5:  'ow............wo',
    6:  'ow............wo', 7:  'ow............wo', 8:  'ow............wo',
    9:  'oCccccccccccccCo', 10: 'oCccccccccccccCo',
  },
  // BELL. Floor-length hem widening below the knee, with a chain off the belt
  // crossing it. Bottom-heavy, and the shoulders are pulled in to say so.
  archivist: {
    10: 'x..............x', 11: 'x..............x', 12: 'x..............x',
    15: '....g...........', 16: '....g...........', 17: '....g...........',
    18: '....g...........',
    19: '..ocgcccccccco..', 20: '.occgccccccccco.',
    21: '.occgccccccccco.', 22: 'occcgcccccccccco', 23: 'occcgcccccccccco',
  },
  /* SLAB. A tower shield fills the off side shoulder to knee: half figure, half
   * wall, and the only class with one straight vertical edge down a whole side.
   *
   * IT USED TO BE THE SHIELD THE PLAYER WAS ALREADY WEARING. The slab sat on
   * rows 9..20 of cols 0..4, which is exactly the box shieldGrid() fills at
   * SHIELD_SIDE[dir].ox — and armour starts at integrity 100, so the tower and
   * the aegis were the same rectangle from the first frame of a new save.
   * Measured on the live /api/state payload, warden against the classless hero
   * came to ZERO alpha cells of 384 in four of the twenty-eight views.
   *
   * So the tower now goes where the aegis does not: up past the shoulder to
   * head height (narrow there, cols 0..2, so it never crosses the face box —
   * front cols 4..11, profile cols 3..7) and down past the shield's bottom edge
   * to the ground line. The rows that buy the silhouette are the ones outside
   * the shield's own 11..21: 3..8 at the top and 22..23 at the foot. */
  warden: {
    3:  'oMo.............', 4:  'oMo.............', 5:  'oMo.............',
    6:  'oMo.............', 7:  'oMo.............', 8:  'oMmo............',
    9:  'oMmmo...........', 10: 'oMmmo...........', 11: 'oMmmo...........',
    12: 'oMmmo...........', 13: 'oMmmo...........', 14: 'oMmmo...........',
    15: 'oMmmo...........', 16: 'oMmmo...........', 17: 'oMmmo...........',
    18: 'oMmmo...........', 19: 'oMmmo...........', 20: 'oMmmo...........',
    21: 'oMmmo...........', 22: 'oMmmo...........', 23: 'oMmmo...........',
  },
  // ASYMMETRIC. A tool rack projects off one shoulder and the other is bare, so
  // the two sides of the outline disagree by three pixels. Nothing else does.
  artificer: {
    6:  '.............oAo', 7:  '.............oAo', 8:  '............oAmo',
    9:  'xxxo........oAmo', 10: 'xxxo........oAmo', 11: 'xxxo........oAmo',
    12: 'xxxo........oAmo', 13: 'xxxo........oAmo',
    14: 'xx..............', 15: 'xx..............',
  },
  /* POINT. The only head in the cast that comes to a point — and the point has
   * to be WIDER than the helm crest rather than taller than it, because row 0
   * is the ceiling of the rig and the crest already owns cols 6..9 of it. The
   * old strip claimed to "clear the skull by two rows" and did not: rows 1..3
   * landed inside the dome the body grid already draws, so only row 0 was above
   * it, and that row was under the crest. Seer against the classless hero
   * measured 1 to 9 alpha cells of 384 across all 28 views.
   *
   * The tell is now the whole GARMENT rather than the peak alone, and it is
   * built out of the three places the dressed rig actually has air: an
   * eight-cell crown standing two columns proud of the crest on each side, a
   * brim at cols 0..1 and 14..15 beside the temple, and a robe hem across rows
   * 19..20 that closes the gap between the legs. Measured against the DEFAULT
   * kit rather than a bare hero, that takes seer-vs-classless from 1 alpha cell
   * of 384 in its worst view to 10, and seer-vs-warden from 4 to 22.
   *
   * The brim stops at row 3 on purpose: rows 4..8 of cols 0..1 and 14..15 are
   * where the berserker's blade tips stand, and two classes spending the same
   * air pocket is how berserker-vs-seer got down to 1 cell the first time this
   * was tried. */
  seer: {
    0:  '....cccccccc....', 1:  '...cccccccccc...',
    2:  'cc............cc', 3:  'cc............cc',
    19: '.occcccccccccco.', 20: '.occcccccccccco.',
  },
};

/* §E-3. The two bodies differ ONLY in the torso and hem grids — shoulder line,
 * waist, hem flare. The head, the face table and every gear anchor are shared,
 * which is the point: twelve sprites that each re-author a face would be twelve
 * chances to break §C. */
const BODY_RIG = {
  a: null,
  b: {
    /* THE SHOULDER, AND THE PIXEL IT USED TO LEAVE BEHIND.
     *
     * This narrowing was authored as '.xo..........ox.' — ERASE at cols 1 and
     * 14 with the new outline at 2 and 13 — which cuts the MIDDLE of the arm
     * and leaves its outermost column standing. Counted on the dressed rig,
     * down/walk0 row 10 came out '#.############.#': a one-pixel vertical
     * sliver at col 0 and another at col 15, each separated from the torso by a
     * one-pixel hole, hanging off the body from row 9 to row 13 and joined to
     * it only where row 13 runs full width. It survived the island check for
     * that reason alone.
     *
     * The erase goes on the OUTER columns now, so the arm loses its outside
     * edge rather than its second one, and row 9 loses both of its own orphan
     * pairs the same way. */
    9:  'xxx..........xxx',
    10: 'xxo..........oxx', 11: 'xxo..........oxx', 12: 'xxo..........oxx',
  },
  /* THE HEM FLARE IS CONDITIONAL, AND IT HAS TO BE.
   *
   * It was three unconditional rows — '.oc..........co.' on 21, 22 and 23 —
   * which is right on a facing whose legs stand under cols 1..14 and wrong on a
   * side-facing stride, where the leg grid is somewhere else entirely and the
   * flare lands on air. An 8-connected component count over 28 views found a
   * detached 2x3 block beside the foot on SIX of them for every body-b rig,
   * the classless hero included: left/walk1, left/walk3, left/cast0,
   * right/walk1, right/walk3 and right/cast0.
   *
   * MANTLE and CLOAK solve the same problem by being authored per facing. This
   * one is solved by asking the grid instead: each flare cell is painted only
   * if the cell one step toward the centre is already filled, worked from the
   * inside out, so the hem can only ever widen a leg that is actually there.
   * `x` cuts air and there has never been a glyph that means "only if
   * touching", which is why this is a rule rather than a row. */
  bFlare: { rows: [21, 22, 23], left: [[2, 'c'], [1, 'o']], right: [[13, 'c'], [14, 'o']] },
};

function classKey(o) {
  const k = String(o.class_id || o.sprite || '');
  return HERO_CLASSES.indexOf(k) >= 0 ? k : '';
}
function bodyKey(o) {
  const b = String(o.body || 'a');
  return HERO_BODY_TYPES.indexOf(b) >= 0 ? b : 'a';
}
/* Stamped on the merged grid, before stripErase, so 'x' cuts real air and the
 * shading pass lights the edge the cut made. */
function classShape(grid, cls, body) {
  let g = grid;
  if (cls && CLASS_RIG[cls]) g = overlay(g, CLASS_RIG[cls]);
  if (BODY_RIG[body]) {
    g = overlay(g, BODY_RIG[body]);
    if (body === 'b') g = hemFlare(g, BODY_RIG.bFlare);
  }
  return g;
}

/* Widen a hem only where there is already a hem to widen. See BODY_RIG.bFlare:
 * the pairs are worked from the inside out, so the outer cell can only land
 * once the inner one has, and a facing whose leg is not under this column gets
 * no flare at all rather than a block of cloak standing in mid-air. */
function hemFlare(grid, spec) {
  if (!spec) return grid;
  let g = grid;
  for (const y of spec.rows) {
    if (y < 0 || y >= g.length) continue;
    for (const side of [spec.left, spec.right]) {
      for (const [x, glyph] of side) {
        const inward = side === spec.left ? x + 1 : x - 1;
        const under = g[y][inward];
        if (under === undefined || under === '.' || under === ' ' || under === ERASE) break;
        g = setCell(g, y, x, glyph);
      }
    }
  }
  return g;
}

/* ---------- frames ---------- */

const heroCache = new Map();
const HERO_CACHE_MAX = 512;

const mirrorRow = (r) => r.split('').reverse().join('');
const HERO_FACE_PROFILE_R = {};
for (const k of Object.keys(HERO_FACE_PROFILE)) {
  HERO_FACE_PROFILE_R[k] = HERO_FACE_PROFILE[k].map(f => f.map(mirrorRow));
}

/* The look is a small dict and the cache is keyed on the whole of it, armour
 * tiers included. A player standing in fixed kit re-renders nothing: the key is
 * identical on every tick and only a repair, an upgrade or a facing change can
 * miss. */
function heroKey(o, facing, frame, pose, emote, gear, rung, line, band, half) {
  return `${facing}:${frame}:${pose}:${emote}:${o.cloak}:${o.tunic}:${o.skin}`
       + `:${o.hair}:${o.boot}:${o.trim}:${o.metal}:${o.weapon}:${gear.key}:${rung}`
       + `:${line}:${band}:${half}:${classKey(o)}:${bodyKey(o)}`;
}

/* pose: 'walk' | 'idle' | 'cast'. `opts.emote` picks the face, and the face's
 * own two frames advance with the sprite's, so a hero who is walking is also
 * blinking without the caller having to drive a second clock. */
export function heroFrame(facing = 'down', frame = 0, opts, pose = 'walk') {
  const o = heroOpts(opts);
  const dir = HERO_BODY[facing] ? facing : 'down';
  const emote = emoteKey(o.emote);
  const gear = heroArmor(o);
  const rung = weaponRung(o);
  const line = weaponLine(o);
  const band = weaponBand(o);
  const half = weaponHalf(o);
  const key = heroKey(o, dir, frame, pose, emote, gear, rung, line, band, half);
  if (heroCache.has(key)) return heroCache.get(key);
  const pal = heroPalette(o);
  const f = ((frame % 4) + 4) % 4;
  const pass = f === 1 || f === 3;

  // Which source frames this pose stands on, decided BEFORE anything is
  // dressed. Armour has to land on the grids that are actually going to be
  // drawn, or an idle hero loses the greaves his walk cycle had.
  const legIdx = pose === 'idle' ? 0 : pose === 'cast' ? 1 : f;
  const armIdx = pose === 'idle' ? 1 : f;

  let body = HERO_BODY[dir];
  let legs = HERO_LEGS[dir][legIdx];
  let arms = pose === 'cast' ? HERO_CAST_ARMS[dir] : HERO_ARMS[dir][armIdx];
  let hem = HERO_HEM[dir];
  let over = null;
  if (gear.any) {
    const dressed = armorLayers(dir, gear, { body, arms, legs, hem });
    body = dressed.body; arms = dressed.arms; legs = dressed.legs;
    hem = dressed.hem; over = dressed.over;
  }
  let bodyY = 0, armY = 10, weaponY = 0, faceY = 0;
  let faceFrame = (f >> 1) & 1;

  if (pose === 'walk') {
    // The pass frames lift the whole upper body a pixel. Without it the hero
    // glides; with it, he walks.
    if (pass) { bodyY = -1; armY = 9; weaponY = -1; }
    // The sway runs to the bottom of the hem whatever length it is, so the
    // Sourceforged cloak moves on the walk the three-row hem already had.
    hem = shiftRows(hem, 1, hem.length - 1, f === 0 ? -1 : f === 2 ? 1 : 0);
  } else if (pose === 'idle') {
    // A breath, not a brightness nudge. On the settled frame the head sinks
    // into the shoulders, the chest widens to take the mass that went
    // somewhere, the cloak hangs a pixel to the left and the weapon drops with
    // the hands; on the other he is back up on the inhale. Feet stay on the
    // contact pose throughout, so he is standing in a stance rather than at
    // attention — which is the difference between a character and a statue.
    faceFrame = f & 1;
    if ((f & 1) === 0) {
      body = widenRows(sinkRows(body, 0, 9, 1), 11, 13);
      armY = 11; weaponY = 1; faceY = 1;
      hem = shiftRows(hem, 1, hem.length - 1, -1);
    } else {
      hem = shiftRows(hem, 1, hem.length - 1, 1);
    }
  } else if (pose === 'cast') {
    bodyY = -1; armY = 8; weaponY = -6;
  }

  const faces = dir === 'up' ? null
    : dir === 'down' ? HERO_FACE_FRONT
    : dir === 'left' ? HERO_FACE_PROFILE
    : HERO_FACE_PROFILE_R;
  const face = faces && (faces[emote] || faces.neutral)[faceFrame];

  // `weapon: null` means unarmed and is honoured: the overworld asks for it when
  // it dresses a villager out of the hero rig, and a townsfolk carrying a
  // longsword to the market is not a stylistic choice.
  let weapon = o.weapon == null ? null : weaponGrid(o.weapon, rung, line, band, half);
  const anchor = WEAPON_ANCHOR[dir];
  let weaponX = anchor[0];
  if (weapon) {
    if (rung >= 3) weapon = runeBlade(weapon, rung);
    if (pose === 'cast') {
      const tilted = tiltWeapon(weapon, anchor[0] > 5 ? 1 : -1);
      weapon = tilted.grid; weaponX += tilted.dx;
    }
  }
  // The off arm, and whether the body is between it and us.
  const side = SHIELD_SIDE[dir];
  const shield = gear.shield >= 0
    ? { grid: shieldGrid(dir, gear.shield), ox: side.ox, oy: armY + 1 } : null;

  const layers = [];
  if (shield && !side.front) layers.push(shield);
  const hemLayer = { grid: hem, oy: 17 };
  layers.push(hemLayer);
  layers.push({ grid: legs, oy: 18 });
  layers.push({ grid: body, oy: bodyY });
  if (face) layers.push({ grid: face, oy: 4 + bodyY + faceY });
  layers.push({ grid: arms, oy: armY });
  // Facing away, the weapon is behind the body; facing the camera it is in front.
  if (weapon) {
    const weaponLayer = { grid: weapon, ox: weaponX, oy: anchor[1] + weaponY };
    if (dir === 'up') layers.splice(layers.indexOf(hemLayer) + 1, 0, weaponLayer);
    else layers.push(weaponLayer);
  }
  // The cap goes on last of the three, because a blade held at the side passes
  // BEHIND the shoulder it is hanging from. Put the pauldron under the weapon
  // and the sword erases the one pixel of widening the box had room for.
  if (over) layers.push({ grid: over, oy: armY - 1 });
  if (shield && side.front) layers.push(shield);

  // One grid, then one light. Merging first is the point: the rim has to run
  // over cloak, arm, boot, pauldron and blade at once or it stops at a layer
  // boundary and the hero comes apart into the pieces he was built from. The
  // erase pass runs in between, so a notched crest is real air by the time the
  // shading sees it and the new edge gets lit like any other edge.
  const shaped = classShape(mergeGrids(HERO_W, HERO_H, layers), classKey(o), bodyKey(o));
  const grid = rimLowLeft(applyRim(stripErase(shaped)), 'R', 'wWMe');
  const canvas = gridSprite(grid, pal, HERO_W, HERO_H);
  heroCache.set(key, canvas);
  capCache(heroCache, HERO_CACHE_MAX);
  return canvas;
}

/* The hero's silhouette at thumbnail size, for the art checks. If the wedge —
 * wide shoulder, narrow waist, planted boot — does not survive down here, no
 * amount of interior shading is going to rescue it up there. */
export function heroSilhouette(facing = 'down', frame = 0, opts, pose = 'walk') {
  const o = heroOpts(opts);
  const dir = HERO_BODY[facing] ? facing : 'down';
  const gear = heroArmor(o);
  const f = ((frame % 4) + 4) % 4;
  let body = HERO_BODY[dir];
  let legs = HERO_LEGS[dir][f];
  let arms = pose === 'cast' ? HERO_CAST_ARMS[dir] : HERO_ARMS[dir][f];
  let hem = HERO_HEM[dir];
  let over = null;
  // Armour is in here because armour is exactly what this check is for: a piece
  // that cannot be told apart down at sixteen pixels has not changed the
  // silhouette, whatever it looks like at full size.
  if (gear.any) {
    const dressed = armorLayers(dir, gear, { body, arms, legs, hem });
    body = dressed.body; arms = dressed.arms; legs = dressed.legs;
    hem = dressed.hem; over = dressed.over;
  }
  // The rung is read here too. This function exists to answer "can a player
  // tell this apart from across a room", and answering it off rung one for a
  // Mythic blade would be answering a question nobody asked.
  const weapon = o.weapon == null ? null
    : weaponGrid(o.weapon, weaponRung(o), weaponLine(o), weaponBand(o), weaponHalf(o));
  const anchor = WEAPON_ANCHOR[dir];
  const side = SHIELD_SIDE[dir];
  return silhouetteAt(stripErase(classShape(mergeGrids(HERO_W, HERO_H, [
    gear.shield >= 0 ? { grid: shieldGrid(dir, gear.shield), ox: side.ox, oy: 11 } : null,
    { grid: hem, oy: 17 },
    { grid: legs, oy: 18 },
    { grid: body },
    { grid: arms, oy: 10 },
    over ? { grid: over, oy: 9 } : null,
    weapon ? { grid: weapon, ox: anchor[0], oy: anchor[1] } : null,
  ].filter(Boolean)), classKey(o), bodyKey(o))), 16);
}

/* Four-frame contact/pass/contact/pass cycle. Drive it from distance travelled,
 * not the wall clock, or the feet slide. */
export const HERO_WALK_ORDER = [0, 1, 2, 3];

/* Drop-in superset of pixel.heroSprites: `side` still resolves, `left` and
 * `right` are authored so nothing needs mirroring, and `idle` is now a real
 * two-frame breath rather than a still frame next to a walk frame. */
export function heroSprites(opts) {
  const out = {};
  for (const facing of ['down', 'up', 'left', 'right']) {
    out[facing] = HERO_WALK_ORDER.map(f => heroFrame(facing, f, opts, 'walk'));
  }
  out.side = out.right;
  out.idle = {};
  out.cast = {};
  for (const facing of ['down', 'up', 'left', 'right']) {
    out.idle[facing] = [heroFrame(facing, 0, opts, 'idle'), heroFrame(facing, 1, opts, 'idle')];
    out.cast[facing] = heroFrame(facing, 0, opts, 'cast');
  }
  out.idle.side = out.idle.right;
  out.cast.side = out.cast.right;
  return out;
}

/* Both frames of one emote, ready to alternate on EMOTE_TIMING. */
export function heroEmoteFrames(facing = 'down', emote = 'neutral', opts, pose = 'idle') {
  const o = { ...heroOpts(opts), emote: emoteKey(emote) };
  return pose === 'idle'
    ? [heroFrame(facing, 0, o, 'idle'), heroFrame(facing, 1, o, 'idle')]
    : [heroFrame(facing, 0, o, pose), heroFrame(facing, 2, o, pose)];
}

export const HERO_WEAPON_KEYS = Object.keys(HERO_WEAPONS);

/* The weapon exactly as it reaches the hand, for scripts/verify.
 *
 * It exists because two of the claims this ladder makes cannot be measured from
 * a rendered frame. "The half step changes the outline" and "runework fires on
 * this family" are both claims about ONE grid against ANOTHER grid that differs
 * from it in exactly one pass, and from outside the module the rung-2 frame and
 * the rung-3 frame are different DRAWINGS — comparing them proves the table was
 * drawn, not that the pass ran. A harness that cannot switch a single pass off
 * ends up reporting `yes` for a family where runeBlade() found nothing to etch,
 * which is the bug that shipped last time.
 *
 * Read-only: it returns a fresh array of strings and nothing in the game calls
 * it. `opts` is {line, band, half, rune} and every field is optional.
 */
export function weaponArt(key, rung, opts = {}) {
  const grid = weaponGrid(key, rung, opts.line || '', opts.band || '',
                          opts.half ? 1 : 0);
  const r = clamp(rung | 0, 0, 5);
  return (opts.rune === false || r < 3) ? grid.slice() : runeBlade(grid, r).slice();
}

/* ================================================================
 * ENEMIES
 * ================================================================
 * Twenty archetypes at 24x24. Silhouette is the primary readability channel in
 * pixel art, so the bounding boxes are deliberately unequal: the slime is wide
 * and low, the wraith is narrow and tall, the golem overflows the box, the wisp
 * is small and sits off-centre. If two of these are unrecognisable from their
 * outline alone, the set has failed.
 *
 * Grids are authored in silhouette and feature only — 'B' is undecided body
 * mass that applyRim() turns into a lit upper-left and a grounded underside.
 */
const ENEMY_SHAPES = {
  slime: [
    '........................', '........................', '........................',
    '........................', '........................', '........................',
    '........................', '........................', '........................',
    '........................',
    '.........oooooo.........',
    '......oooBBBBBBooo......',
    '....ooBBBBBBBBBBBBoo....',
    '...oBBBBBBBBBBBBBBBBo...',
    '..oBBBwwBBBBBBwwBBBBBo..',
    '..oBBBweBBBBBBweBBBBBo..',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '.oBBBBBBBaaaaBBBBBBBBBo.',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '...ooBBBBBBBBBBBBBBoo...',
    '.....oooooooooooooo.....',
    '........................',
  ],
  wisp: [
    '........................',
    '......oooo..............',
    '....ooBBBBoo............',
    '...oBBBBBBBBo...........',
    '..oBBwwBBwwBBo..........',
    '..oBBweBBweBBo..........',
    '..oBBBBBBBBBBo..........',
    '..oBBBaaaaBBBo..........',
    '...oBBBaaBBBo...........',
    '....oBBBBBBo............',
    '.....oBBBBo.............',
    '......oBBo..............',
    '.......oo....oAo........',
    '........o...oABAo.......',
    '............oAAAo.......',
    '.............oAo........',
    '..............o.........',
    '................oAo.....',
    '...............oAAo.....',
    '................oo......',
    '........................', '........................',
    '........................', '........................',
  ],
  wave: [
    '........................',
    '..........oooo..........',
    '.......oooBBBBooo.......',
    '.....ooBBBBBBBBBBoo.....',
    '....oBBBwwBBBBwwBBBo....',
    '....oBBBweBBBBweBBBo....',
    '...oBBBBBBBBBBBBBBBBo...',
    '...oBBBBaaaaaaBBBBBBo...',
    '....oBBBBBBBBBBBBBBo....',
    '.....ooBBBBBBBBBBoo.....',
    '.......oooooooooo.......',
    '..oAo..............oAo..',
    '.oAAAo............oAAAo.',
    '..oAo..............oAo..',
    'oAo..................oAo',
    'oAAo................oAAo',
    'oAo..................oAo',
    '........................',
    '..oAAo............oAAo..',
    '...oo................oo.',
    '........................', '........................',
    '........................', '........................',
  ],
  golem: [
    '........................',
    '.........oooooo.........',
    '........oBBBBBBo........',
    '........oBwewBBo........',
    '........oBBBBBBo........',
    '..oooooooBBBBBBooooooo..',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    'oBBaaBBBBBBBBBBBBBBaaBBo',
    'oBBaaBBBBBBBBBBBBBBaaBBo',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    '.oBBBBBBggggggggBBBBBBo.',
    '.oBBBBBBggggggggBBBBBBo.',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBBBoooooooooBBBBBo..',
    '..oBBBo.........oBBBBo..',
    '..oBBBo.........oBBBBo..',
    '..oBBBo.........oBBBBo..',
    '..oBBBo.........oBBBBo..',
    '..oBBBo.........oBBBBo..',
    '.oBBBBBo.......oBBBBBBo.',
    '.ooooooo.......oooooooo.',
    '........................',
  ],
  wraith: [
    '.........oooo...........',
    '.......ooBBBBoo.........',
    '......oBBBBBBBBo........',
    '......oBBwwBBwwBo.......',
    '......oBBweBBweBo.......',
    '......oBBBBBBBBBo.......',
    '.....oBBBBBBBBBBo.......',
    '.....oBBBaaaaBBBo.......',
    '.....oBBBBBBBBBBo.......',
    '....oBBBBBBBBBBBBo......',
    '....oBBBBBBBBBBBBo......',
    '...oBBBBBBBBBBBBBBo.....',
    '...oBBBBaaaaaaBBBBo.....',
    '...oBBBBBBBBBBBBBBo.....',
    '..oBBBBBBBBBBBBBBBBo....',
    '..oBBBBBBBBBBBBBBBBo....',
    '..oBBBBBBBBBBBBBBBBo....',
    '.oBBBBBBBBBBBBBBBBBBo...',
    '.oBBBBBBBBBBBBBBBBBBo...',
    '.oBBBoBBBBoBBBBoBBBBo...',
    '.oBBo.oBBo.oBBo.oBBBo...',
    '.oBo...oo...oo...oBo....',
    '..o..............o......',
    '........................',
  ],
  hydra: [
    '..oooo.....oooo....oooo.',
    '.oBBBBo...oBBBBo..oBBBBo',
    '.oBweBo...oBweBo..oBweBo',
    '.oBBBBo...oBBBBo..oBBBBo',
    '..oBBo.....oBBo....oBBo.',
    '..oBBo.....oBBo....oBBo.',
    '..oBBo.....oBBo....oBBo.',
    '..oBBoo...ooBBoo..ooBBo.',
    '..oBBBooooBBBBBBooBBBBo.',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    'oBBBaaBBBBBBBBBBBBaaBBBo',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBBoooBBBBBBoooBBBo..',
    '..oBBo...oBBBBo...oBBo..',
    '..oBBo...oBBBBo...oBBo..',
    '..oBBo...oBBBBo...oBBo..',
    '..oooo...oooooo...oooo..',
    '........................',
    '........................',
  ],
  drake: [
    '........................',
    'oo....................oo',
    'oBo..................oBo',
    'oBBo................oBBo',
    'oBBBo.....oooo....oBBBo.',
    'oBBBBo...oBBBBo...oBBBBo',
    'oBBBBBo..oBweBo..oBBBBBo',
    'oBBBBBBo.oBBBBo.oBBBBBBo',
    'oBBBBBBBooBBBBooBBBBBBBo',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '..oBBBBBBBaaaaBBBBBBBo..',
    '...ooBBBBBBBBBBBBBBoo...',
    '.....oBBBBBBBBBBBBo.....',
    '.....oBBBBBBBBBBBBo.....',
    '.....oBBBaaaaaaBBBo.....',
    '.....oBBBBBBBBBBBBo.....',
    '......oBBBBBBBBBBo......',
    '......oBBBBBBBBBBo......',
    '.....oBBBo..oBBBo.......',
    '.....oBBBo..oBBBo.......',
    '....oBBBBBooBBBBBo......',
    '....oooooo..oooooo......',
    '........................',
    '........................',
  ],
  construct: [
    '........................',
    '......oooooooooooo......',
    '......oBBBBBBBBBBo......',
    '......oBwwoooowwBo......',
    '......oBweooooewBo......',
    '......oBBBBBBBBBBo......',
    '......ooooBBBBoooo......',
    '..oooo..oBBBBBBo..oooo..',
    '..oAAo..oBBBBBBo..oAAo..',
    '..oAAo.oBBBBBBBBo.oAAo..',
    '..oooo.oBBBaaBBBo.oooo..',
    '.......oBBBaaBBBo.......',
    '......oBBBBBBBBBBo......',
    '......oBBgggggggBo......',
    '......oBBgggggggBo......',
    '......oBBBBBBBBBBo......',
    '.....ooBBBBBBBBBBoo.....',
    '.....oBBBBoooBBBBBo.....',
    '.....oBBBo...oBBBBo.....',
    '.....oBBBo...oBBBBo.....',
    '....oBBBBBo.oBBBBBBo....',
    '....ooooooo.oooooooo....',
    '........................',
    '........................',
  ],
  mimic: [
    '........................',
    '..oooooooooooooooooooo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBgggggggggggggggBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oooooooooooooooooooo..',
    '...oWoWoWoWoWoWoWoWoo...',
    '..oBWBWBWBWBWBWBWBWBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBBweBBBBBBBBweBBBo..',
    '..oBBBwwBBBBBBBBwwBBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oooooooooooooooooooo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBaaaaBBBBBBaaaaBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBgggggggggggggggBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oooooooooooooooooooo..',
    '...oBo..........oBo.....',
    '...oBo..........oBo.....',
    '...ooo..........ooo.....',
    '........................',
    '........................',
  ],
  crawler: [
    '........................', '........................', '........................',
    '........................', '........................', '........................',
    '..........oooooo........',
    '........ooBBBBBBoo......',
    '.......oBBweBBweBBo.....',
    '.......oBBBBBBBBBBo.....',
    '.oooooooBBBBBBBBBBoooooo',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    'oBBaaBBaaBBaaBBaaBBaaBBo',
    'oBBBBBBBBBBBBBBBBBBBBBBo',
    '.oBBBBBBBBBBBBBBBBBBBBo.',
    '..oooooooooooooooooooo..',
    '.oo..oo..oo..oo..oo..oo.',
    '.oo..oo..oo..oo..oo..oo.',
    'oo....oo..oo..oo....oo..',
    '........................', '........................',
    '........................', '........................',
    '........................',
  ],
  sentinel: [
    '.........oooooo.........',
    '........oBBBBBBo........',
    '.......oBBBBBBBBo.......',
    '......oBBBwwwwBBBo......',
    '......oBBBwkkwBBBo......',
    '......oBBBwwwwBBBo......',
    '.......oBBBBBBBBo.......',
    '........oBBBBBBo........',
    '.......oBBoooBBBo.......',
    '......oBBBo.oBBBBo......',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBaao.oBBaaBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '.....oBBBBo.oBBBBBo.....',
    '....oBBBBBBooBBBBBBo....',
    '....oBBBBBBBBBBBBBBo....',
    '....oooooooooooooooo....',
    '........................',
    '........................',
  ],
  beetle: [
    '..o..................o..',
    '...o................o...',
    '....o..............o....',
    '.....oo..........oo.....',
    '......oooooooooooooo....',
    '.....oBBBBBBBBBBBBBBo...',
    '.....oBBweBBBBBBweBBo...',
    '.....oBBBBBBBBBBBBBBo...',
    '....ooBBBBBBBBBBBBBBoo..',
    '...oBBBBBBBBBBBBBBBBBBo.',
    '..oBBBBBBBBoBBBBBBBBBBo.',
    '..oBBaaBBBBoBBBBaaBBBBo.',
    '..oBBBBBBBBoBBBBBBBBBBo.',
    '..oBBBBBBBBoBBBBBBBBBBo.',
    '..oBBaaBBBBoBBBBaaBBBBo.',
    '..oBBBBBBBBoBBBBBBBBBBo.',
    '...oBBBBBBBoBBBBBBBBBo..',
    '....ooBBBBBoBBBBBBBoo...',
    '......oooooooooooooo....',
    '..oo..o..........o..oo..',
    '.oo....o........o....oo.',
    'oo....................oo',
    '........................',
    '........................',
  ],
  warden: [
    'oo....................oo',
    'oAo..................oAo',
    'oAo......oooo........oAo',
    'oAo.....oBBBBo.......oAo',
    'oAo.....oBweBo.......oAo',
    'oAo.....oBBBBo.......oAo',
    'oAo......oBBo........oAo',
    'oAo...ooooBBoooo.....oAo',
    'oAo...oBBBBBBBBBo....oAo',
    'oAo..oBBBBBBBBBBBo...oAo',
    'oAo..oBBBaaaaaBBBo...oAo',
    'oAo..oBBBBBBBBBBBo...oAo',
    'oAo.ooBBBBBBBBBBBoo..oAo',
    'ooo.oBBBBBBBBBBBBBo..ooo',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBgggggBBBBo.....',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBoooBBBBBBo.....',
    '....oBBBo...oBBBBo......',
    '....oBBBo...oBBBBo......',
    '...oBBBBBo.oBBBBBBo.....',
    '...ooooooo.oooooooo.....',
    '........................',
    '........................',
  ],
  imp: [
    '........................',
    '.............oooooo.....',
    '.............oaaaao.....',
    '............oooooooo....',
    '............oaaaaaao....',
    '...oooooo...oooooooo....',
    '..oBBBBBBo..oaaaaaao....',
    '..oBweBweo..oooooooo....',
    '..oBBBBBBooooooooooo....',
    '..oBBBBBBBBBBBBBBBBo....',
    '.oBBBBBBBBBBBBBBBBBo....',
    '.oBBaaBBBBBBBBBBBBBo....',
    '.oBBBBBBBBBBBBBBBBBo....',
    '.oBBBBBBBBBBBBBBBBo.....',
    '..oBBBBBBBBBBBBBBo......',
    '..oBBBBoooooBBBBBo......',
    '..oBBBo.....oBBBBo......',
    '..oBBBo.....oBBBBo......',
    '.oBBBBBo...oBBBBBBo.....',
    '.ooooooo...oooooooo.....',
    '........................', '........................',
    '........................', '........................',
  ],
  serpent: [
    '........oooooo..........',
    '......ooBBBBBBoo........',
    '.....oBBweBBweBBo.......',
    '.....oBBBBBBBBBBo.......',
    '.....ooBBBBBBBBoo.......',
    '.......oBBBBBBo.........',
    '.......ooBBBBoo.........',
    '.........oBBo...........',
    '........oBBBBo..........',
    '......ooBBBBBBoo........',
    '....ooBBBBaaBBBBoo......',
    '...oBBBBBBaaBBBBBBo.....',
    '...oBBBBBBBBBBBBBBo.....',
    '....ooBBBBBBBBBBoo......',
    '......ooBBBBBBoo........',
    '........oBBBBo..........',
    '.......oBBBBBBo.........',
    '.....ooBBBBBBBBoo.......',
    '...ooBBBBBBBBBBBBoo.....',
    '..oBBBBBBaaaaBBBBBBo....',
    '..oBBBBBBBBBBBBBBBBo....',
    '..ooBBBBBBBBBBBBBBoo....',
    '....oooooooooooooo......',
    '........................',
  ],
  lattice: [
    '........................',
    '..oooooooooooooooooooo..',
    '..oBBBoBBBoBBBoBBBoBBo..',
    '..oBBBoBBBoBBBoBBBoBBo..',
    '..oweBoBBBoBBBoBBBoewo..',
    '..oooooooooooooooooooo..',
    '..oBBBoBBBoaaaoBBBoBBo..',
    '..oBBBoBBBoaaaoBBBoBBo..',
    '..oooooooooooooooooooo..',
    '..oBBBoBBBoBBBoBBBoBBo..',
    '..oBBBoBBBoBBBoBBBoBBo..',
    '..oooooooooooooooooooo..',
    '..oBBBoaaaoBBBoaaaoBBo..',
    '..oBBBoaaaoBBBoaaaoBBo..',
    '..oooooooooooooooooooo..',
    '..oBBBoBBBoBBBoBBBoBBo..',
    '..oBBBoBBBoBBBoBBBoBBo..',
    '..oooooooooooooooooooo..',
    '...oBo....oBo....oBo....',
    '...oBo....oBo....oBo....',
    '...ooo....ooo....ooo....',
    '........................',
    '........................',
    '........................',
  ],
  keeper: [
    '........................',
    '..........oooo..........',
    '.........oBBBBo.........',
    '.........oBweBo.........',
    '.........oBBBBo.........',
    '.......oooooooooo.......',
    '......oBBBBoBBBBBo......',
    '......oBBBBoBBBBBo......',
    '......oBaaBoBBaaBo......',
    '......oBBBBoBBBBBo......',
    '....oooooooooooooooo....',
    '...oBBBBoBBBBBoBBBBBo...',
    '...oBBBBoBBBBBoBBBBBo...',
    '...oBaaBoBBaaBoBBaaBo...',
    '...oBBBBoBBBBBoBBBBBo...',
    '.oooooooooooooooooooooo.',
    'oBBBBBoBBBBBoBBBBBoBBBBo',
    'oBBBBBoBBBBBoBBBBBoBBBBo',
    'oBaaBBoBBaaBoBBaaBoBaaBo',
    'oBBBBBoBBBBBoBBBBBoBBBBo',
    'oooooooooooooooooooooooo',
    '........................',
    '........................',
    '........................',
  ],
  ledger: [
    '........................',
    '....oooooooooooooooo....',
    '...oBBBBBBBBBBBBBBBBo...',
    '...oBBweBBBBBBBBweBBo...',
    '...oBBBBBBBBBBBBBBBBo...',
    '...oooooooooooooooooo...',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBaBaBaBaBaBaBaBaBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBaaaaBBBBBBBBBBBBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBaaaaaaaaBBBBBBBBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBaaaaaaaaaaaaBBBBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBaaaaaaaaaaaaaaaaBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '...oooooooooooooooooo...',
    '...oBBBBBBBBBBBBBBBBo...',
    '...oBBBBBBBBBBBBBBBBo...',
    '....oooooooooooooooo....',
    '.....oo..........oo.....',
    '........................',
    '........................',
  ],
  sorter: [
    '........................',
    '....................oooo',
    '....................oBBo',
    '....................oweo',
    '....................oBBo',
    '...............oooo.oBBo',
    '...............oBBo.oBBo',
    '...............oweo.oBBo',
    '...............oBBo.oBBo',
    '..........oooo.oBBo.oBBo',
    '..........oBBo.oBBo.oBBo',
    '..........oweo.oBBo.oBBo',
    '..........oBBo.oBBo.oBBo',
    '.....oooo.oBBo.oBBo.oBBo',
    '.....oBBo.oBBo.oBBo.oBBo',
    '.....oweo.oBBo.oBBo.oBBo',
    '.....oBBo.oBBo.oBBo.oBBo',
    'oooo.oBBo.oBBo.oBBo.oBBo',
    'oBBo.oBBo.oBBo.oBBo.oBBo',
    'oweo.oBBo.oBBo.oBBo.oBBo',
    'oBBo.oaao.oBBo.oaao.oBBo',
    'oBBo.oBBo.oaao.oBBo.oBBo',
    'oooo.oooo.oooo.oooo.oooo',
    '........................',
  ],
  vault: [
    '........................',
    '...oooooooooooooooooo...',
    '...oBBBBBBBBBBBBBBBBo...',
    '...oBggggggggggggggBo...',
    '...oBgBBBBBBBBBBBBgBo...',
    '...oBgBweBBBBBBweBgBo...',
    '...oBgBBBBBBBBBBBBgBo...',
    '...oBgBBBBooooBBBBgBo...',
    '...oBgBBBoaaaaoBBBgBo...',
    '...oBgBBBoaakaoBBBgBo...',
    '...oBgBBBoaaaaoBBBgBo...',
    '...oBgBBBBooooBBBBgBo...',
    '...oBgBBBBBBBBBBBBgBo...',
    '...oBgBBBBBkkBBBBBgBo...',
    '...oBgBBBBBkkBBBBBgBo...',
    '...oBgggggggggggggBBo...',
    '...oBBBBBBBBBBBBBBBBo...',
    '...oooooooooooooooooo...',
    '....oBBo........oBBo....',
    '....oBBo........oBBo....',
    '....oooo........oooo....',
    '........................',
    '........................',
    '........................',
  ],
};

export const ENEMY_ARCHETYPES = Object.keys(ENEMY_SHAPES);
export const ENEMY_SIZE = 24;

/* Every enemy key the engine can emit, mapped onto an archetype. The engine
 * names one creature per pattern (gauntlet/engine.py ENEMY_SPRITES); bosses
 * carry their own keys and are handled by bossSprite. */
export const ENEMY_SHAPE_FOR = {
  slime: 'slime', marshling: 'slime',
  wisp: 'wisp', echoling: 'wisp',
  lightwave: 'wave',
  hoarder: 'golem',
  linewraith: 'wraith', riddler: 'wraith',
  mirrorspawn: 'hydra',
  branchling: 'drake',
  construct: 'construct', clockwork: 'construct',
  mimic: 'mimic',
  deepcrawler: 'crawler',
  halfling: 'sentinel',
  bugling: 'beetle',
  twinblade: 'warden',
  cartgoblin: 'imp',
  wyrmling: 'serpent',
  gridling: 'lattice',
  pilekeeper: 'keeper',
  ledgerling: 'ledger',
  orderling: 'sorter', indexling: 'sorter', overlapper: 'ledger',
  vaultling: 'vault', runeling: 'imp',
};

/* Species colour. The audit's point stands: colouring a monster by the problem
 * it happens to carry means the same monster is a different colour every time
 * you meet it, and nothing in the bestiary becomes memorable. Body colour is
 * identity; the pattern supplies the ACCENT only. */
export const ENEMY_COLOUR = {
  slime: '#5fbf8f', marshling: '#7f9a5a', wisp: '#7ec8ff', echoling: '#d6a84f',
  lightwave: '#4fb7d6', hoarder: '#bf8f5f', linewraith: '#3f7f9c',
  riddler: '#8f9cd6', mirrorspawn: '#8f6ad6', branchling: '#3f9c5a',
  construct: '#c88fd6', clockwork: '#b08a55', mimic: '#d6c04f',
  deepcrawler: '#4f8f5a', halfling: '#5a9cd6', bugling: '#c43f4f',
  twinblade: '#c4553f', cartgoblin: '#b0763f', wyrmling: '#3f6f9c',
  gridling: '#8a8f9c', pilekeeper: '#d68f4f', ledgerling: '#9c8f4f',
  orderling: '#6a9c8f', indexling: '#6f8fbf', overlapper: '#5f9fbf',
  vaultling: '#e8a33d', runeling: '#b9a86a',
};

/* Pattern colour, used for the accent band and for the battle backdrop tint. */
export const FAMILY_COLOUR = {
  HASH_MAP: '#e8a33d', SET: '#7ec8ff', SLIDING_WINDOW: '#7f6ad6',
  TWO_POINTER: '#c4553f', STACK: '#b0763f', QUEUE: '#3f7f9c',
  BFS: '#4fb7d6', DFS: '#4f8f5a', TREE: '#3f9c5a', RECURSION: '#8f6ad6',
  BINARY_SEARCH: '#5a9cd6', MATRIX: '#8a8f9c', HEAP: '#d68f4f',
  PREFIX_SUM: '#9c8f4f', SORTING: '#6a9c8f', SIMULATION: '#b08a55',
  DP: '#d6a84f', STRING: '#5fbf8f', ARRAY: '#6f8fbf', DESIGN: '#c88fd6',
  DEBUGGING: '#c43f4f', COMPLEXITY: '#3f6f9c', TESTING: '#d6c04f',
  RECOGNITION: '#8f9cd6', GREEDY: '#bf8f5f', INTERVALS: '#5f9fbf',
  LANGUAGE: '#b9a86a',
};

/* Idle motion, exported so the renderer can move a sprite that is standing
 * still. `bob` is peak vertical travel in source pixels, `sway` horizontal,
 * `phase` staggers creatures of the same species so a group never pulses in
 * lockstep, `period` is one full cycle in milliseconds, and `anim` names the
 * deformation used for the second frame. */
export const ENEMY_MOTION = {
  slime:     { bob: 2, sway: 0, phase: 0.00, period: 900,  anim: 'squash' },
  wisp:      { bob: 3, sway: 1, phase: 0.35, period: 1500, anim: 'float' },
  wave:      { bob: 1, sway: 0, phase: 0.10, period: 1100, anim: 'pulse' },
  golem:     { bob: 1, sway: 0, phase: 0.60, period: 2200, anim: 'heavy' },
  wraith:    { bob: 2, sway: 2, phase: 0.20, period: 1800, anim: 'sway' },
  hydra:     { bob: 1, sway: 1, phase: 0.45, period: 1300, anim: 'necks' },
  drake:     { bob: 2, sway: 0, phase: 0.05, period: 1000, anim: 'flap' },
  construct: { bob: 1, sway: 0, phase: 0.70, period: 1600, anim: 'pulse' },
  mimic:     { bob: 1, sway: 0, phase: 0.15, period: 1400, anim: 'squash' },
  crawler:   { bob: 1, sway: 1, phase: 0.50, period: 700,  anim: 'legs' },
  sentinel:  { bob: 1, sway: 0, phase: 0.80, period: 2000, anim: 'float' },
  beetle:    { bob: 1, sway: 1, phase: 0.25, period: 800,  anim: 'legs' },
  warden:    { bob: 1, sway: 0, phase: 0.55, period: 1500, anim: 'heavy' },
  imp:       { bob: 2, sway: 1, phase: 0.40, period: 850,  anim: 'squash' },
  serpent:   { bob: 1, sway: 2, phase: 0.30, period: 1700, anim: 'sway' },
  lattice:   { bob: 1, sway: 0, phase: 0.65, period: 1900, anim: 'pulse' },
  keeper:    { bob: 1, sway: 0, phase: 0.75, period: 2100, anim: 'heavy' },
  ledger:    { bob: 1, sway: 1, phase: 0.85, period: 1600, anim: 'sway' },
  sorter:    { bob: 1, sway: 0, phase: 0.90, period: 1200, anim: 'tick' },
  vault:     { bob: 1, sway: 0, phase: 0.95, period: 2400, anim: 'pulse' },
};

export function enemyMotion(spriteKey) {
  return ENEMY_MOTION[ENEMY_SHAPE_FOR[spriteKey] || spriteKey]
      || ENEMY_MOTION.slime;
}

/* Swap the two accent tones. Used by anything whose second frame is a glow
 * rather than a movement — a rune brightening, a dial turning, a core beating. */
function swapAccent(grid) {
  return grid.map(row => row.replace(/[aA]/g, ch => (ch === 'a' ? 'A' : 'a')));
}

function filledBounds(grid) {
  let top = grid.length, bottom = 0;
  for (let y = 0; y < grid.length; y++) {
    if ([...grid[y]].some(c => !EMPTY(c))) { if (y < top) top = y; bottom = y; }
  }
  return [top === grid.length ? 0 : top, bottom];
}

/* The second frame of every idle. Each of these moves real mass: the audit's
 * complaint about the old set was that its "animation" was a six-unit
 * brightness change on the body, which nobody can see. */
function deform(grid, anim) {
  const [top, bottom] = filledBounds(grid);
  const mid = Math.round((top + bottom) / 2);
  switch (anim) {
    case 'squash': return widenRows(squashRows(grid, top, bottom), bottom - 3, bottom - 1);
    case 'float':  return bobGrid(grid, -1);
    case 'sway':   return shiftRows(grid, top, mid, 1);
    case 'necks':  return shiftRows(shiftRows(grid, top, top + 3, 1), top + 4, top + 7, -1);
    case 'flap':   return sinkRows(grid, top, top + 7, 1);
    case 'legs':   return shiftRows(grid, bottom - 2, bottom, 1);
    case 'heavy':  return sinkRows(grid, top, top + 4, 1);
    case 'tick':   return swapAccent(sinkRows(grid, top, mid, 1));
    case 'pulse':  return swapAccent(widenRows(grid, mid - 1, mid + 1));
    default:       return bobGrid(grid, -1);
  }
}

export function enemyPalette(base, accentHex) {
  const r = ramp(base);
  const a = ramp(accentHex || base);
  return {
    o: mix(r.outline, '#0b0912', 0.45), O: r.rim,
    D: r.shadow2, d: r.shadow1, B: r.base, L: r.light1, H: r.light2,
    a: a.base, A: a.light2, k: '#110e1a',
    e: '#15101f', w: '#f2f6ff', W: '#ffffff',
    g: mix(r.light1, '#c8ccd8', 0.6),
  };
}

const enemyCache = new Map();

/* Same signature as pixel.enemySprite so call sites swap without edits, but the
 * body colour now comes from the species and `pattern` tints the accent. */
export function enemySprite(spriteKey, pattern, frame = 0, override) {
  const shapeKey = ENEMY_SHAPE_FOR[spriteKey] || (ENEMY_SHAPES[spriteKey] ? spriteKey : 'slime');
  const base = override || ENEMY_COLOUR[spriteKey] || FAMILY_COLOUR[pattern] || '#7a8fbf';
  const accent = FAMILY_COLOUR[pattern] || ramp(base).light2;
  const f = frame % 2;
  const key = `e:${shapeKey}:${base}:${accent}:${f}`;
  if (enemyCache.has(key)) return enemyCache.get(key);
  const motion = ENEMY_MOTION[shapeKey] || ENEMY_MOTION.slime;
  const grid = f ? deform(ENEMY_SHAPES[shapeKey], motion.anim) : ENEMY_SHAPES[shapeKey];
  const canvas = gridSprite(applyRim(grid), enemyPalette(base, accent), ENEMY_SIZE, ENEMY_SIZE);
  enemyCache.set(key, canvas);
  return canvas;
}

/* ================================================================
 * BOSSES
 * ================================================================
 * 48x48, authored — not a trash mob run through a 2x upscale. A boss is the
 * biggest moment the game has and it has to survive being looked at.
 *
 * Each is written as its LEFT HALF, 24 columns wide, and mirrored at draw time.
 * Every one of these creatures is bilaterally symmetric, so the mirror costs
 * nothing in fidelity and buys exact symmetry plus half the authoring surface
 * to get wrong. The idle deformation breaks the symmetry again so the pose
 * never reads as a paper cutout.
 */
const BOSS_HALVES = {
  titan: [
    '..........o.....o.......',
    '.........oao...oao......',
    '.........oao...oao......',
    '.......oooooooooooooo...',
    '.......oaaaaaaaaaaaaao..',
    '......ooggggggggggggggo.',
    '.....oBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBwwwwBBBBBBBBBBBBB',
    '....oBBwkkwBBBBBBBBBBBBB',
    '....oBBwwwwBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....ooBBBBBBBBBBBBBBBBB',
    '......oooooBBBBBBBBBBBBB',
    'oooooooooooBBBBBBBBBBBBB',
    'oaaaaaaaaaaBBBBBBBBBBBBB',
    'ogggggggggggBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBaaaaBBBBBBBBBBBBBBBB',
    'oBBBaaaaBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBgggggggggggg',
    '..oBBBBBBBBBgggggggggggg',
    '..oBBBBBBBBBgggggggggggg',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBoooooo',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBaaaaaBBBBo.....',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBBBBBBBBBBo.....',
    '....oBBBBBBBBBBBBBo.....',
    '...oBBBBBBBBBBBBBBBo....',
    '...oBBBBBBBBBBBBBBBo....',
    '..oggggggggggggggggggo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oBBBBBBBBBBBBBBBBBBo..',
    '..oooooooooooooooooooo..',
    '........................',
    '........................',
  ],
  hydra: [
    '........................',
    '..........oooooo........',
    '.........oBBBBBBo.......',
    '.........oBweBBBo.......',
    '.........oBBBBBBo.......',
    '..........oBBBBo........',
    '...oooooo.oBBBBo........',
    '..oBBBBBBo.oBBBo........',
    '..oBweBBBo.oBBBo........',
    '..oBBBBBBo.oBBBo........',
    '...oBBBBo..oBBBo........',
    '...oBBBo...oBBBo...ooooo',
    '...oBBBo...oBBBo..oBBBBB',
    '...oBBBo...oBBBo..oBBBwe',
    '...oBBBo...oBBBo..oBBBBB',
    '...oBBBo...oBBBo..oBBBBB',
    '...oBBBo...oBBBo...ooooo',
    '...oBBBo...oBBBo........',
    '...oBBBo...oBBBo...oBBBB',
    '...oBBBoo.ooBBBo...oBBBB',
    '...oBBBBoooBBBBooooBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBaaaaBBBBBBBBBBBBBBBB',
    'oBBBaaaaBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBaaaaaaaaaaaaaaa',
    '.oBBBBBBBaaaaaaaaaaaaaaa',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBoooooooBBBBBBBB',
    '....oBBBo......oBBBBBBBB',
    '....oBBBo......oBBBBBBBB',
    '....oBBBo......oBBBBBBBB',
    '...oBBBBBo....oBBBBBBBBB',
    '...oBBBBBo....oBBBBBBBBB',
    '..oBBBBBBBo..oBBBBBBBBBB',
    '..ooooooooo..ooooooooooo',
    '........................',
    '........................',
    '........................',
  ],
  wraith: [
    '........................',
    '........................',
    '........................',
    '........................',
    '...............ooooooooo',
    '.............ooBBBBBBBBB',
    '............oBBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '..........oBBBkkkkBBBBBB',
    '..........oBBkwwkBBBBBBB',
    '..........oBBBkkkkBBBBBB',
    '..........oBBBBBBBBBBBBB',
    '.........oBBBBBBBBBBBBBB',
    '........oBBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBBaaaaaaaaaaaa',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBoooooooo',
    '....oBBBBBBBBBBBoaaaaaaa',
    '...oBBBBBBBBBBBBoaaaaaaa',
    '...oBBBBBBBBBBBBBoaaaaaa',
    '...oBBBBBBBBBBBBBBoaaaaa',
    '...oBBBBBBBBBBBBBBoaaaaa',
    '...oBBBBBBBBBBBBBoaaaaaa',
    '..oBBBBBBBBBBBBBBoaaaaaa',
    '..oBBBBBBBBBBBBBBoaaaaaa',
    '..oBBBBBBBBBBBBBBBoooooo',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBaaaaaaaaaaBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBoBBBBBBoBBBBBBBBBBBB',
    'oBBoo.oBBBBooBBBBBBBBBBB',
    'oBo....oBBBo.oBBBBBBBBBB',
    '.o......oBo...oBBBBBBBBB',
    '..............oBBBoBBBBB',
    '...............oBo.oBBBo',
    '...................oBo..',
    '........................',
    '........................',
    '........................',
  ],
  behemoth: [
    '........................',
    '........................',
    '........................',
    '........................',
    '........................',
    '........................',
    '........................',
    '........................',
    '..............ooooooooo.',
    '............ooBBBBBBBBBB',
    '..........ooBBBBBBBBBBBB',
    '.........oBBBBBBBBBBBBBB',
    '........oBBBBaaaaaaaaaaa',
    '.......oBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBoooooooooooo',
    '...oBBBBBBBBoBBBBBBBBBBB',
    '...oBBBBBBBBoBBwwwwBBBBB',
    '...oBBBBBBBBoBBwkkwBBBBB',
    '...oBBBBBBBBoBBwwwwBBBBB',
    '..oBBBBBBBBBoBBBBBBBBBBB',
    '..oBBBBBBBBBoBBBBBBBBBBB',
    'ooBBBBBBBBBBoBBBBBBBBBBB',
    'oaaBBBBBBBBBoBBBBBBBBBBB',
    'oaaoBBBBBBBBoBBBaaaaBBBB',
    '.ooBBBBBBBBBoBBBBBBBBBBB',
    '..oBBBBBBBBBoBBBBBBBBBBB',
    '..oBBBBBBBBBooooBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBoooooBBBBBBBBBBB',
    '...oBBBo.....oBBBBBBBBBB',
    '...oBBBo.....oBBBBBBBBBB',
    '...oBBBo.....oBBBBBBBBBB',
    '...oBBBo.....oBBBBBBBBBB',
    '..oBBBBBo....oBBBBBBBBBB',
    '..oBBBBBo....oBBBBBBBBBB',
    '..oBBBBBo....oBBBooooooo',
    '..oBBBBBo....oBBBo......',
    '.oBBBBBBBo...oBBBBBo....',
    '.oBBBBBBBo...oBBBBBo....',
    '.ooooooooo...ooooooo....',
    '........................',
    '........................',
  ],
  golem: [
    '........................',
    '........................',
    '........................',
    '........................',
    '........................',
    '..............oooooooooo',
    '.............oBBBBBBBBBB',
    '.............oBBwwwwBBBB',
    '.............oBBwkkwBBBB',
    '.............oBBBBBBBBBB',
    '.............ooooooooooo',
    '........................',
    '.....ooooooooooooooooooo',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    'oooo.oBBBBBBBBBBBBBBBBBB',
    'oBBo.oBBBoooooooooooBBBB',
    'oBBo.oBBBoaaaaaaaaaoBBBB',
    'oBBo.oBBBoaaaaaaaaaoBBBB',
    'oooo.oBBBoaaaaaaaaaoBBBB',
    '.....oBBBoaaaaaaaaaoBBBB',
    'oooo.oBBBoaaaaaaaaaoBBBB',
    'oBBo.oBBBoooooooooooBBBB',
    'oBBo.oBBBBBBBBBBBBBBBBBB',
    'oBBo.oBBBBBBBBBBBBBBBBBB',
    'oooo.oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....ooooooooooooooooooo',
    '........................',
    '.......ooooooooooooooooo',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBggggggggggggg',
    '......oBBBBBBBBBBBBBBBBB',
    '......oooooooooooooooooo',
    '........................',
    '.........ooooooooooo....',
    '........oBBBBBBBBBBBo...',
    '........oBBBBBBBBBBBo...',
    '........oBBBBBBBBBBBo...',
    '........oBBBBBBBBBBBo...',
    '........oBBBBBBBBBBBo...',
    '........oBBBBBBBBBBBo...',
    '.......oBBBBBBBBBBBBBo..',
    '.......ooooooooooooooo..',
    '........................',
    '........................',
    '........................',
  ],
};

const BOSS_HALVES_2 = {
  dragon: [
    'oo......................',
    'oBo.....................',
    'oBBo....................',
    'oBBBo...................',
    'oBBBBo..................',
    'oBBBBBo.................',
    'oBBBBBBo................',
    'oBBBBBBBo...............',
    'oBBBBBBBBo..............',
    'oBBBBBBBBBo.............',
    'oBBBBBBBBBBo............',
    'oBBBaBBBBBBBo...........',
    'oBBBaBBBBBBBBo..........',
    'oBBBaaBBBBBBBBo.........',
    'oBBBBaBBBBBBBBBo........',
    'oBBBBaaBBBBBBBBBo.......',
    '.oBBBBaBBBBBBBBBBo......',
    '..oBBBBaaBBBBBBBBBo.....',
    '...oBBBBBBBBBBBBBBo.oooo',
    '....oBBBBBBBBBBBBo.oBBBB',
    '.....oBBBBBBBBBBo.oBBBBB',
    '......oBBBBBBBBo.oBBweBB',
    '.......oBBBBBBo..oBBBBBB',
    '........oBBBBo...oBBBBBB',
    '.........oBBo....oBBBBBB',
    '.........oBBoooooBBBBBBB',
    '.........oBBBBBBBBBBBBBB',
    '........oBBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '......oBBBBaaaaaaaaaaaaa',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBaaaaaaaaaaaaa',
    '.......oBBBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '........oBBBBBBBBBBBBBBB',
    '........oBBBBoooooBBBBBB',
    '.......oBBBBo....oBBBBBB',
    '.......oBBBBo....oBBBBBB',
    '......oBBBBBBo...oBBBBBB',
    '......oBBBBBBo...oBBBooo',
    '.....oBBBBBBBBo..oBBBo..',
    '.....oBaaaaaaBo..oBBBo..',
    '.....ooooooooo...ooooo..',
    '........................',
    '........................',
    '........................',
    '........................',
  ],
  ent: [
    '..............oooo......',
    '...........oooBBBBoooo..',
    '.........ooBBBBBBBBBBBoo',
    '.......ooBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '...ooBBBBBBBBBBBBBBBBBBB',
    '.....oooBBBBBBBBBBBBBBBB',
    '.......ooBBBBBBBBBBBBBBB',
    'oo......oBBBBBBBBBBBBBBB',
    '.ooo....oBBBBBBBBBBBBBBB',
    '...ooo..oBBBwwwwBBBBBBBB',
    '.....oooooBBBwkkwBBBBBBB',
    '.......ooBBBBwwwwBBBBBBB',
    '........oBBBBBBBBBBBBBBB',
    '........oBBBBBBaaaaBBBBB',
    '........oBBBBBBBBBBBBBBB',
    '........oBBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '.......oBBBaaaaaaaaaaaaa',
    '.......oBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBoBBBBBBBBBBBBB',
    '.oBBBBBBoooBBBBBBBBBBBBB',
    'oBBBBBBo..oBBBBBBBBBBBBB',
    'oBBBBo....oBBBBBBoBBBBBB',
    'oBBo......oBBBBoo.oBBBBB',
    'ooo.......oBBBo...oBBBBB',
    '..........ooooo...ooBBBo',
    '.....................ooo',
  ],
  necromancer: [
    '.....................ooo',
    '....................oaaa',
    '..............oo....oaaa',
    '.............oao...ooaaa',
    '.............oao...oaaaa',
    '.............oaoooooaaa.',
    '.............oooooooBBBB',
    '...........ooBBBBBBBBBBB',
    '..........oBBBBBBBBBBBBB',
    '..........oBBkkkkkBBBBBB',
    '..........oBBkwwkkBBBBBB',
    '..........oBBkkkkkBBBBBB',
    '..........oBBBBBBBBBBBBB',
    '.........oBBBBBBBBBBBBBB',
    '........oBBBBBBBBBBBBBBB',
    'ooo.....oBBBBBBBBBBBBBBB',
    'oaao....oBBBBBBBBBBBBBBB',
    'oaao...ooBBBBBBBBBBBBBBB',
    'ooo...ooBBBBBBBBBBBBBBBB',
    '.....ooBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBBBBBBBBBBBB',
    '....oBBBBBBBBaaaaaaaaaaa',
    '....oBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBBBBBBBBBBBBBBBB',
    '...oBBBBBoooooooooBBBBBB',
    '...oBBBBoaaaaaaaaaoBBBBB',
    '...oBBBBoaaaaaaaaaoBBBBB',
    '...oBBBBoaaaaaaaaaoBBBBB',
    '...oBBBBBoooooooooBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '..oBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    '.oBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBaaaaaaaaaaaaaaaaaaa',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBBBBBBBBBBBBBBBBBBBBB',
    'oBBBoBBBBBBoBBBBBBBBBBBB',
    'oBBoo.oBBBBooBBBBBBBBBBB',
    'oBo...oBBBBo.oBBBBBBBBBB',
    'oo.....oBBo...oBBBBBBBBB',
    '........oo....oBBBoBBBBo',
    '..............oo...oBBo.',
    '........................',
    '........................',
  ],
  automaton: [
    '..............oooooooooo',
    '..............oBBBBBBBBB',
    '..............oBggggBBBB',
    '..............oBgwwgBBBB',
    '..............oBggggBBBB',
    '..............oBBBBBBBBB',
    '............oooooooooooo',
    '...........oBBBBBBBBBBBB',
    '...oooo....oBBBBBBBBBBBB',
    '..oaaao....oBBBBBBBBBBBB',
    '..oaoao....oBBBBBBBBBBBB',
    '..oaaao.oooBBBBBBBBBBBBB',
    '...oaoooooBBBBBBBBBBBBBB',
    '....ooo..oBBBBBBBBBBBBBB',
    '.........oBBBBBBBBBBBBBB',
    '........ooBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '.......oBBBooooooooooooo',
    '.......oBBBogggggggggggg',
    '.......oBBBoggkkkkkkkkkk',
    '.......oBBBoggkkkkkkkkkk',
    '.......oBBBogggggggggggg',
    '.......oBBBooooooooooooo',
    '.......oBBBBBBBBBBBBBBBB',
    '.......oBBBBBBBBBBBBBBBB',
    '......oBBBBBBBBBBBBBBBBB',
    '......oBBBBaaaaaaaaaaaaa',
    '......oBBBBBBBBBBBBBBBBB',
    '......oooooooooooooooooo',
    '........................',
    '.......oooooo...oooooooo',
    '......oBBBBBBo..oBBBBBBB',
    '......oBggggBo..oBBBBBBB',
    '......oBBBBBBo..oBBBBBBB',
    '......oBggggBo..oBggggBB',
    '......oBBBBBBo..oBBBBBBB',
    '......oBggggBo..oBggggBB',
    '......oBBBBBBo..oBBBBBBB',
    '.....oBBBBBBBBooBBBBBBBB',
    '.....oBBBBBBBBo.oBBBBBBB',
    '.....oBBBBBBBBo.oBBBBBBB',
    '....oBBBBBBBBBBo.oBBBBBB',
    '....oooooooooooo.ooooooo',
    '........................',
    '........................',
    '........................',
    '........................',
    '........................',
  ],
  demon: [
    'ooo.....................',
    'oBBo....................',
    'oBBBo...................',
    'oBBBBo..............oo..',
    'oBBBBBo............oaao.',
    'oBBBBBBo..........oaaao.',
    'oBBBBBBBo........oaaaoo.',
    'oBBBBBBBBo......ooaaaooo',
    'oBBBBBBBBBo....ooBBBBBBB',
    'oBBBBBBBBBBo..ooBBBBBBBB',
    'oBBBBBBBBBBBooBBBBBBBBBB',
    'oBBBaBBBBBBBoBBrrrrBBBBB',
    'oBBBaBBBBBBBoBBrkkrBBBBB',
    'oBBBaaBBBBBBoBBrrrrBBBBB',
    'oBBBBaBBBBBBoBBBBBBBBBBB',
    '.oBBBaaBBBBBoBBBBBBBBBBB',
    '..oBBBBaBBBBoBBBBBBBBBBB',
    '...oBBBBBBBBooooBBBBBBBB',
    '....oBBBBBBo...oBBBBBBBB',
    '.....oBBBBo....oBBBBBBBB',
    '......oBBo.....oBBBBBBBB',
    '.......oo......oBBBBBBBB',
    '...............oBBBaaaaa',
    '..............oBBBBBBBBB',
    '.............oBBBBBBBBBB',
    '............oBBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '..........oBBBBrrrrrrrrr',
    '..........oBBBBBBBBBBBBB',
    '..........oBBBBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '............oBBBBBBBBBBB',
    '............oBBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '..........oBBBBBBBBBBBBB',
    '.........oBBBBoooooBBBBB',
    '........oBBBBo...oBBBBBB',
    '........oBBBBo...oBBBBBB',
    '.......oBBBBBo...oBBBBBB',
    '.......oBBBBBo...oBBBBBB',
    '......oBBBBBBo...oBBBBBB',
    '.....oBBBBBBBo...oBBBooo',
    '.....oBaaaaaBo...oBBBo..',
    '.....ooooooooo...ooooo..',
    '........................',
    '........................',
    '........................',
  ],
  interviewer: [
    '........................',
    '........................',
    '........................',
    '........................',
    '..............oooooooooo',
    '............ooBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '...........oBBBBBBBBBBBB',
    '...........oBBwwwwwwwwww',
    '...........oBBwwwwwwwwww',
    '...........oBBwwwwwwwwww',
    '...........oBBwwwwwwwwww',
    '...........oBBwwwwwwwwww',
    '...........oBBBBBBBBBBBB',
    '............oBBBBBBBBBBB',
    '.............ooBBBBBBBBB',
    '..............oBBBBBBBBB',
    '.........ooooooBBBBBBBBB',
    '.......ooBBBBBBBBBBBBBBB',
    '......oBBBBBBBBwwwwwwwww',
    '.....oBBBBBBBBBwwaaawwww',
    '.....oBBBBBBBBBwwaaawwww',
    '.....oBBBBBBBBBwwaaawwww',
    '.....oBBBBBBBBBBwaaawwww',
    '.....oBBBBBBBBBBwaaawwww',
    'ooooooBBBBBBBBBBwaaawwww',
    'oaaaoBBBBBBBBBBBwaaawwww',
    'oaaaoBBBBBBBBBBBwaaawwww',
    'oaaaoBBBBBBBBBBBBwaawwww',
    'oaaaoBBBBBBBBBBBBBwawwww',
    'ooooooBBBBBBBBBBBBBBwwww',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBBBBBBBBBB',
    '.....oBBBBBBBBBooooooooo',
    '.....oBBBBBBBBBo........',
    '.....oBBBBBBBBBo........',
    '.....oBBBBBBBBBo........',
    '.....oBBBBBBBBBo........',
    '.....oBBBBBBBBBo........',
    '.....oBBBBBBBBBo........',
    '....oBBBBBBBBBBo........',
    '...oBBBBBBBBBBBo........',
    '...ooooooooooooo........',
    '........................',
    '........................',
  ],
};
Object.assign(BOSS_HALVES, BOSS_HALVES_2);

export const BOSS_SIZE = 48;
export const BOSS_ARCHETYPES = Object.keys(BOSS_HALVES);

/* world.BOSSES keys mapped onto authored art. Two aliases: a wyrm is a dragon
 * that never learned to land, and a lich is a necromancer who stopped waiting.
 * Both carry their own colour from world.py, so they still read apart. */
export const BOSS_SHAPE_FOR = {
  titan: 'titan', hydra: 'hydra', wraith: 'wraith', behemoth: 'behemoth',
  golem: 'golem', dragon: 'dragon', ent: 'ent', necromancer: 'necromancer',
  automaton: 'automaton', demon: 'demon', interviewer: 'interviewer',
  wyrm: 'dragon', lich: 'necromancer',
};

export const BOSS_MOTION = {
  titan:       { bob: 2, sway: 0, phase: 0.00, period: 2600, anim: 'heavy' },
  hydra:       { bob: 2, sway: 1, phase: 0.20, period: 1600, anim: 'necks' },
  wraith:      { bob: 3, sway: 2, phase: 0.40, period: 2200, anim: 'sway' },
  behemoth:    { bob: 2, sway: 0, phase: 0.60, period: 2000, anim: 'heavy' },
  golem:       { bob: 1, sway: 0, phase: 0.10, period: 2800, anim: 'pulse' },
  dragon:      { bob: 3, sway: 0, phase: 0.30, period: 1400, anim: 'flap' },
  ent:         { bob: 1, sway: 2, phase: 0.70, period: 3000, anim: 'sway' },
  necromancer: { bob: 2, sway: 1, phase: 0.50, period: 2400, anim: 'float' },
  automaton:   { bob: 1, sway: 0, phase: 0.80, period: 1800, anim: 'tick' },
  demon:       { bob: 2, sway: 0, phase: 0.15, period: 1500, anim: 'flap' },
  interviewer: { bob: 1, sway: 0, phase: 0.90, period: 3400, anim: 'float' },
};

export function bossMotion(spriteKey) {
  return BOSS_MOTION[BOSS_SHAPE_FOR[spriteKey] || spriteKey] || BOSS_MOTION.titan;
}

/* Left half + its reflection. Every one of these creatures is symmetric, so the
 * mirror is free; the idle deformation is what stops the pose reading flat. */
function mirrorHalf(half) {
  return half.map(row => {
    const r = padRow(row, 24);
    return r + [...r].reverse().join('');
  });
}

const bossCache = new Map();

/* Same signature as pixel.bossSprite. `colour` is the boss's own colour from
 * world.BOSSES, which is identity here, not decoration. */
export function bossSprite(spriteKey, colour, frame = 0) {
  const shapeKey = BOSS_SHAPE_FOR[spriteKey] || (BOSS_HALVES[spriteKey] ? spriteKey : 'titan');
  const base = colour || '#d84a7a';
  const f = frame % 2;
  const key = `b:${shapeKey}:${base}:${f}`;
  if (bossCache.has(key)) return bossCache.get(key);
  const motion = BOSS_MOTION[shapeKey] || BOSS_MOTION.titan;
  let grid = mirrorHalf(BOSS_HALVES[shapeKey]);
  if (f) grid = deform(grid, motion.anim);
  const pal = enemyPalette(base, ramp(base).light2);
  pal.r = '#ff9d4a';                       // ember, used by the demon's mane
  const canvas = gridSprite(applyRim(grid), pal, BOSS_SIZE, BOSS_SIZE);
  bossCache.set(key, canvas);
  return canvas;
}

/* ================================================================
 * PORTRAITS
 * ================================================================
 * 24x24. Each mentor has a jaw, complexion, hair material and facial planes.
 * Shared brow/eye/mouth performances fit over that anatomy. BYTE and the
 * Interviewer have mechanical and porcelain faces authored separately.
 *
 * Seven emotes per character, two frames each. The frames are authored events —
 * a blink, a squeeze, a jaw setting — not the same face at two brightnesses,
 * which is the same rule the walk cycle is held to and for the same reason.
 */
const PORTRAIT_FACE = [
  '........................',
  '........................',
  '.......oooooooooo.......',
  '.....ooossssssSSooo.....',
  '....ooNsssssssssSSoo....',
  '....oNsssssssssssSSo....',
  '....oNsssssssssssSSo....',
  '....oNsssssssssssSSo....',
  '....ossssssssssssSSo....',
  '....ossssssssssssSSo....',
  '....ossssssNSssssSSo....',
  '....osssssssSSsssSSo....',
  '....ossssssssssssSSo....',
  '....ossssssssssssSSo....',
  '....oSssssssssssSSSo....',
  '.....ooSsssssssSSoo.....',
  '.......ooSsssSSoo.......',
  '.........oKKKKo.........',
  '........oNsssSSo........',
  '........................',
  '........................',
  '........................',
  '........................',
  '........................',
];

/* Facial anatomy is independent of profession colour. Jaw coordinates describe
 * rows 10..17; asymmetric cheeks and noses keep these busts from becoming a
 * row of identical faces in different hats. All marks reuse the 15 paid slots.
 * The brow/eye band remains open for every performance. */
const PORTRAIT_PERSON = {
  scholar: { skin: '#c58c65', hair: '#b6a494', jaw: [[4,19],[4,19],[5,18],[5,18],[6,17],[7,16],[8,15],[9,14]], nose: 12,
    marks: [[10,6,'SS'],[10,16,'SS'],[14,7,'Yh'],[14,15,'Yh'],[15,8,'hHHhhh'],[16,9,'hHHh']] },
  mage: { skin: '#b78273', hair: '#221b37', jaw: [[4,19],[5,19],[5,18],[6,18],[6,17],[7,16],[9,14],[10,13]], nose: 11,
    marks: [[10,6,'NN'],[11,15,'SS'],[14,6,'S'],[15,15,'S']] },
  ranger: { skin: '#986949', hair: '#362b25', jaw: [[4,19],[4,18],[4,18],[5,18],[5,17],[6,16],[7,15],[9,14]], nose: 11,
    marks: [[10,15,'S'],[11,15,'N'],[12,15,'S'],[14,7,'S'],[15,8,'SS']] },
  druid: { skin: '#bd966c', hair: '#c8b48e', jaw: [[4,19],[4,19],[5,19],[5,18],[6,18],[7,17],[8,16],[9,15]], nose: 12,
    marks: [[10,6,'SS'],[10,16,'SS'],[14,6,'Yh'],[14,16,'hY'],[15,7,'hHHhhhhhh'],[16,8,'hHHhhhh'],[17,9,'hhhYh']] },
  cartographer: { skin: '#d1aa7c', hair: '#704b32', jaw: [[4,19],[4,19],[4,19],[5,19],[5,18],[6,17],[7,16],[8,15]], nose: 12,
    marks: [[10,5,'N'],[11,17,'S'],[14,7,'N'],[15,14,'SS']] },
  armorer: { skin: '#925e43', hair: '#30272a', jaw: [[4,19],[4,19],[4,19],[4,19],[5,18],[5,18],[6,17],[8,15]], nose: 12,
    marks: [[10,6,'S'],[10,16,'S'],[14,5,'Yhh'],[14,16,'hhY'],[15,6,'hHHhhhhhhh'],[16,7,'hHHhhhh'],[17,9,'YhhY']] },
  oracle: { skin: '#b3a0a0', hair: '#d9d4cc', jaw: [[5,18],[5,18],[6,18],[6,17],[7,17],[8,16],[9,15],[10,13]], nose: 12,
    marks: [[10,7,'N'],[11,15,'SS'],[14,8,'S'],[15,14,'S']] },
  smith: { skin: '#b67753', hair: '#563129', jaw: [[4,19],[4,19],[4,19],[5,19],[5,18],[6,18],[7,17],[8,15]], nose: 11,
    marks: [[10,16,'SS'],[11,6,'S'],[14,6,'Yh'],[14,16,'hY'],[15,7,'hHHhhhhhh'],[16,8,'hhhhhY']] },
  chronomancer: { skin: '#c3a092', hair: '#aba9b8', jaw: [[4,19],[5,19],[5,19],[6,18],[6,18],[7,17],[8,16],[9,14]], nose: 12,
    marks: [[10,6,'SS'],[10,16,'SS'],[11,7,'S'],[11,16,'S'],[14,7,'S'],[15,8,'SS'],[15,15,'S']] },
  scribe: { skin: '#825344', hair: '#181b29', jaw: [[4,19],[5,19],[5,18],[5,18],[6,18],[7,17],[8,16],[9,14]], nose: 11,
    marks: [[10,6,'N'],[11,15,'SS'],[14,7,'N'],[15,14,'S']] },
  architect: { skin: '#bd9272', hair: '#433d46', jaw: [[4,19],[4,19],[5,19],[5,19],[6,18],[6,17],[7,16],[8,15]], nose: 12,
    marks: [[10,6,'SS'],[11,16,'S'],[14,6,'S'],[15,7,'SS'],[16,9,'SSS']] },
};

function portraitAnatomy(kind) {
  const p = PORTRAIT_PERSON[kind] || PORTRAIT_PERSON.scholar;
  const rows = PORTRAIT_FACE.map(r => r.split(''));
  for (let n = 0; n < p.jaw.length; n++) {
    const y = n + 10, [left, right] = p.jaw[n];
    rows[y].fill('.');
    for (let x = left; x <= right; x++) {
      rows[y][x] = x === left || x === right ? 'o'
        : n === 7 ? 'K' : x >= right - 3 ? 'S'
        : x === left + 1 && n < 4 ? 'N' : 's';
    }
  }
  rows[10][p.nose] = 'N'; rows[10][p.nose + 1] = 'S';
  rows[11][p.nose - 1] = 'N'; rows[11][p.nose] = 'N'; rows[11][p.nose + 1] = 'S';
  for (const [y, x, strip] of p.marks) for (let i = 0; i < strip.length; i++) {
    if (rows[y][x + i] !== '.' && rows[y][x + i] !== 'o') rows[y][x + i] = strip[i];
  }
  return rows.map(r => r.join(''));
}

/* Broad fabric planes and swept hair highlights, never random texture. The
 * same construction is used on every crown/garment, but each authored cut,
 * accessory and colour remains the mentor's own. */
function portraitMaterials(grid) {
  return grid.map((row, y) => [...row].map((ch, x) => {
    if (ch === 'h') return x < 8 && y < 5 ? 'H' : x > 15 ? 'Y' : 'h';
    if (ch === 'c') return x > 15 || (x > 10 && x < 13 && y > 1) ? 'v'
      : x < 8 && y < 4 ? 'C' : 'c';
    return ch;
  }).join(''));
}

/* Headwear, drawn over the skull from row 0.
 *
 * Every one of these keeps the band x7..x16 clear from row 6 downward, and that
 * constraint is the single most important line in the section: rows 6 and 7 are
 * where the BROWS live, and the brow is what carries the performance. A hat
 * pulled down over the eyebrows is a hat on a character who can no longer act. */
const PORTRAIT_CROWN = {
  scholar: [
    '........................',
    '.......oooooooooo.......',
    '.....ooohhhhhhhhooo.....',
    '....oohhhhhhhhhhhhoo....',
    '....ohhhhhhhhhhhhhho....',
    '....ohhho......ohhho....',
    '....oh............ho....',
    '....oo............oo....',
  ],
  mage: [
    '...........oo...........',
    '.........oohhoo.........',
    '.......oohhhhhhoo.......',
    '.....oohhhhhhhhhhoo.....',
    '...oohhhhhhhhhhhhhhoo...',
    '..oggggggggggggggggggo..',
    '..oo................oo..',
    '........................',
  ],
  ranger: [
    '......ohho..............',
    '.....ohhhhhhhhhhhho.....',
    '...ohhhhhhhhhhhhhhhho...',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..ohhhho........ohhhho..',
    '..ohhho..........ohhho..',
    '...ohho..........ohho...',
  ],
  druid: [
    '.....oo..........oo.....',
    '....ohho........ohho....',
    '...ohhhooooooooohhho....',
    '...ohhhhhhhhhhhhhhhho...',
    '...ohhhhhhhhhhhhhhhho...',
    '...ohhhg........ghhho...',
    '...ohho..........ohho...',
    '....oo............oo....',
  ],
  cartographer: [
    '........................',
    '......oooooooooooo......',
    '......ohhhhhhhhhho......',
    '.oooooooooooooooooooooo.',
    '.oggggggggggggggggggggo.',
    '.oooooooooooooooooooooo.',
    '........................',
    '........................',
  ],
  armorer: [
    '..........oggo..........',
    '.........oggggo.........',
    '.....oooooooooooooo.....',
    '...ooggggggggggggggoo...',
    '..oggggggggggggggggggo..',
    '..ogggggoooooooogggggo..',
    '..ogggo..........ogggo..',
    '...oggo..........oggo...',
  ],
  oracle: [
    '..........oooo..........',
    '........oohhhhoo........',
    '......oohhhhhhhhoo......',
    '....oohhhhhhhhhhhhoo....',
    '...ohhhhgggggggghhhho...',
    '...ohhho........ohhho...',
    '...ohhh..........hhho...',
    '...ohho..........ohho...',
  ],
  smith: [
    '........................',
    '.....oooooooooooooo.....',
    '...oohhhhhhhhhhhhhhoo...',
    '...ohhhhhhhhhhhhhhhho...',
    '...oooooooooooooooooo...',
    '...occcccccccccccccco...',
    '...oo..............oo...',
    '....o..............o....',
  ],
  chronomancer: [
    '......o....oo....o......',
    '.....ogo..oggo..ogo.....',
    '....oggggggggggggggo....',
    '....oggggggggggggggo....',
    '....ohhhhhhhhhhhhhho....',
    '....ohho........ohho....',
    '....oh............ho....',
    '....oo............oo....',
  ],
  scribe: [
    '........................',
    '.....oooooooooooooo.....',
    '...ooccccccccccccccoo...',
    '..occcccccccccccccccco..',
    '..occcccccccccccccccco..',
    '..occco..........occco..',
    '..occo............occo..',
    '..oo................oo..',
  ],
  architect: [
    '....oho...ohho...oho....',
    '...ohhhhhhhhhhhhhhhho...',
    '...ohhhhhhhhhhhhhhhho...',
    '...ohhhhhhhhhhhhhhhho...',
    '...oggggggggggggggggo...',
    '...ohhho........ohhho...',
    '...ohho..........ohho...',
    '....oh............ho....',
  ],
};

/* Garment, drawn over the neck and shoulders from row 18. Wider at the bottom
 * than the head is anywhere, because the shoulder line is what makes a portrait
 * read as a person rather than a head in a jar. */
const PORTRAIT_GARB = {
  scholar: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'oocccccccccggcccccccccoo',
    'occccccccccggcccccccccco',
    'oooooooooooooooooooooooo',
  ],
  mage: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'ooccccccggggggggccccccoo',
    'occcccccccggggccccccccco',
    'oooooooooooooooooooooooo',
  ],
  ranger: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'ooccccvccccggccccvccccoo',
    'occcccccggggggggccccccco',
    'oooooooooooooooooooooooo',
  ],
  druid: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'oocccccgccggggccgcccccoo',
    'occccccccccggcccccccccco',
    'oooooooooooooooooooooooo',
  ],
  cartographer: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'oocccggggggggggggggcccoo',
    'occcgoooooooooooooogccco',
    'oooooooooooooooooooooooo',
  ],
  armorer: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'ooggggccccccccccccggggoo',
    'ogggggccccccccccccgggggo',
    'oooooooooooooooooooooooo',
  ],
  oracle: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'ooccccccccggggccccccccoo',
    'occccccccccggcccccccccco',
    'oooooooooooooooooooooooo',
  ],
  smith: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'oocccggggccccccggggcccoo',
    'occccggggggggggggggcccco',
    'oooooooooooooooooooooooo',
  ],
  chronomancer: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'ooccccggggggggggggccccoo',
    'occccccgoooooooogcccccco',
    'oooooooooooooooooooooooo',
  ],
  scribe: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'ooccccccccggggccccccccoo',
    'occccccccccggcccccccccco',
    'oooooooooooooooooooooooo',
  ],
  architect: [
    '......oooooooooooo......',
    '....ooCCccccccccccoo....',
    '..ooCCccccccccccccccoo..',
    'oocccggccccccccccggcccoo',
    'occcccgccccccccccgccccco',
    'oooooooooooooooooooooooo',
  ],
};

/* ---------- the seven faces ----------
 *
 * Ten columns wide, landing at x7..x16 over the clean skin the head leaves for
 * them. Left eye is columns 0-2, right eye is columns 7-9, the nose sits
 * between. Rows 6-7 are brow, 8-9 are eye, 12-14 are mouth.
 *
 * Read this table DOWN a column rather than across a row. The mouths of
 * `strained` and `stubborn` are nearly the same six pixels; the faces are not
 * remotely the same face, because one has the inner brow driven down into the
 * eye and the other has a single unbroken bar of brow pressed flat across both.
 * That is the principle worth stealing: the brow sells the emotion and the
 * mouth mostly agrees with it. It is also the cheap one — a brow is three
 * pixels and it can move a whole row, where a mouth at this scale has about two
 * shapes in it.
 *
 * Two frames each, and the second frame is a real event — a blink, a squeeze,
 * a jaw setting, a laugh opening wider — never the first frame a shade lighter.
 */
const PORTRAIT_EMOTE = {
  neutral: [
    [[7, 'hhh....hhh'], [8, 'YYY....YYY'], [9, 'wow....wow'], [12, '...oooo...'], [13, '....SS....']],
    [[7, 'hhh....hhh'], [8, 'YYY....YYY'], [12, '...oooo...'], [13, '....SS....']],
  ],
  pleased: [
    [[6, 'hhh....hhh'], [7, 'o........o'], [8, 'YYY....YYY'], [9, 'owo....owo'], [12, '..o....o..'], [13, '...oooo...']],
    [[6, 'hhh....hhh'], [7, 'o........o'], [8, 'YYY....YYY'], [9, '.o......o.'], [12, '.o......o.'], [13, '..oooooo..']],
  ],
  strained: [
    [[6, 'hh......hh'], [7, '.hhh..hhh.'], [8, 'YYY....YYY'], [9, 'oSo....oSo'], [12, '..oooooo..'], [13, '..owwwwo..']],
    [[6, 'hh......hh'], [7, 'hhhh..hhhh'], [8, 'YYY....YYY'], [9, '.o......o.'], [12, '..oooooo..'], [13, '..oooooo..']],
  ],
  alarmed: [
    [[6, 'hhhh..hhhh'], [8, 'www....www'], [9, 'wow....wow'], [12, '...oooo...'], [13, '...oKKo...'], [14, '....oo....']],
    [[6, 'hhhh..hhhh'], [8, 'www....www'], [9, 'wwo....oww'], [12, '...oooo...'], [13, '...oKKo...'], [14, '...oooo...']],
  ],
  stubborn: [
    [[7, 'hhhhhhhhhh'], [8, 'YYY....YYY'], [9, 'wow....wow'], [12, '..oooooo..'], [13, '..o....o..']],
    [[6, 'hhhhhhhhhh'], [7, 'hhhhhhhhhh'], [8, 'YYY....YYY'], [9, 'wow....wow'], [13, '..oooooo..'], [14, '..o....o..']],
  ],
  delighted: [
    [[6, '.hh....hh.'], [7, 'o..o..o..o'], [8, '.o......o.'], [9, 'o.o....o.o'], [12, '..oooooo..'], [13, '..owwwwo..'], [14, '...oooo...']],
    [[6, 'hhh....hhh'], [7, 'o..o..o..o'], [8, '.o......o.'], [9, 'o.o....o.o'], [12, '.oooooooo.'], [13, '.owwwwwwo.'], [14, '..oooooo..']],
  ],
  defeated: [
    [[6, '..hh..hh..'], [7, 'hh......hh'], [8, 'YYY....YYY'], [9, '.o......o.'], [12, '...oooo...'], [13, '..o....o..']],
    [[6, '..hh..hh..'], [7, 'hh......hh'], [8, 'YYY....YYY'], [12, '...oooo...'], [13, '..o....o..']],
  ],
};


/* Not human enough to borrow the face. */
const PORTRAIT_FULL = {
  automaton_small: [
    '........................',
    '.........oooooo.........',
    '.......ooggggggoo.......',
    '.....oogggggggggggo.....',
    '....ogggggggggggggggo...',
    '....oggoooooooooooggo...',
    '....oggoBBBBBBBBooggo...',
    '....oggoBwwBBwwBooggo...',
    '....oggoBwwBBwwBooggo...',
    '....oggoBBBBBBBBooggo...',
    '....oggoBBBaaBBBooggo...',
    '....oggoBBBBBBBBooggo...',
    '....oggoooooooooooggo...',
    '....ogggggggggggggggo...',
    '.....ooggggggggggggo....',
    '.......oogggggggoo......',
    '.........ooggggoo.......',
    '..........oggggo........',
    '......ooooogggggoooo....',
    '....oogggggggggggggoo...',
    '..oogggggggaaagggggggoo.',
    '..oggggggggaaaggggggggo.',
    '..oooooooooooooooooooo..',
    '........................',
  ],
  interviewer: [
    '........................',
    '.......oooooooooo.......',
    '.....oowwwwwwwwwwoo.....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '....owwwwwwwwwwwwwwo....',
    '.....oowwwwwwwwwwoo.....',
    '.......oowwwwwwoo.......',
    '.........owwwwo.........',
    '.........oBBBBo.........',
    '......oooBBBBBBooo......',
    '....oooBBBwwwwBBBooo....',
    '..ooBBBBBBwaawBBBBBBoo..',
    '..oBBBBBBBwaawBBBBBBBo..',
    '..oBBBBBBBwaawBBBBBBBo..',
    '..oBBBBBBBwwwwBBBBBBBo..',
    '..oooooooooooooooooooo..',
    '........................',
  ],
};

/* Robe colour per mentor, so the cast is legible at a glance in a list. */
const PORTRAIT_TINT = {
  scholar: '#4a5a8a', mage: '#8f6ad6', ranger: '#4f8f5a', druid: '#3f9c5a',
  cartographer: '#5a9cd6', armorer: '#b0763f', oracle: '#d8d8e8',
  smith: '#c4553f', chronomancer: '#d6a84f', scribe: '#6a5a8a',
  architect: '#3f6fa8',
  automaton_small: '#b0763f', interviewer: '#2a2a38',
};

/* Companions reuse a mentor's likeness — they are the same order of being, and
 * the engine only ever needs a face beside a line of dialogue. */
export const PORTRAIT_ALIAS = {
  spirit: 'oracle', messenger: 'ranger', familiar: 'druid',
  hero: 'architect', player: 'architect', you: 'architect',
};

export const PORTRAIT_KEYS = [
  ...Object.keys(PORTRAIT_CROWN), ...Object.keys(PORTRAIT_FULL),
];
export const PORTRAIT_SIZE = 24;

/* The two that are not people get a lamp instead of a face. A machine cannot
 * raise an eyebrow, so its emote lives entirely in the colour and steadiness of
 * its core: warm and even when things are going well, dim and guttering when
 * they are not, hard accent when it disagrees with you. It is a narrower
 * instrument than a brow and it is supposed to be — that difference is most of
 * the characterisation these two get. */
const PORTRAIT_LAMP_BAND = { automaton_small: [6, 11], interviewer: [16, 22] };
const PORTRAIT_LAMP = {
  neutral:   ['w', 'a'], pleased:  ['w', 'C'], strained: ['a', 'v'],
  alarmed:   ['w', 'K'], stubborn: ['a', 'a'], delighted:['w', 'w'],
  defeated:  ['v', 'K'],
};

/* BYTE has no brow, so it was given the mechanical equivalent: a pair of brass
 * shutter plates above the lenses and a vent below them. They move exactly
 * where a brow and a mouth would, in the same seven shapes and on the same two
 * frames, which is why a machine built out of eight pixels of shutter still
 * reads as pleased or as dug-in. Eight columns wide, landing at x8..x15 on the
 * faceplate. */
const AUTOMATON_SHUTTER = {
  neutral:   ['.gg..gg.', '.gg..gg.'],
  pleased:   ['gg....gg', 'gg....gg'],
  strained:  ['..gggg..', '.gggggg.'],
  alarmed:   ['........', '.g....g.'],
  stubborn:  ['gggggggg', 'gggggggg'],
  delighted: ['g.g..g.g', 'gg....gg'],
  defeated:  ['..g..g..', '.gg..gg.'],
};
const AUTOMATON_VENT = {
  neutral:   ['...aa...', '...oo...'],
  pleased:   ['..aaaa..', '.aaaaaa.'],
  strained:  ['.o.aa.o.', '.oo..oo.'],
  alarmed:   ['...oo...', '..oooo..'],
  stubborn:  ['.oooooo.', 'oooooooo'],
  delighted: ['.aaaaaa.', 'aaaaaaaa'],
  defeated:  ['..o..o..', '...oo...'],
};
const AUTOMATON_SHUTTER_Y = 6, AUTOMATON_VENT_Y = 10, AUTOMATON_X = 8;

/* Fifteen colours again, and the same argument as the hero's:
 *
 *   o outline   K deep   R the rim        s S N  skin, shadow, skin in the rim
 *   h H Y  hair, its lit edge, its shadow — which is also the brow, because a
 *          brow is hair and paying twice for that would cost an eye tone
 *   c C v  garment, lit, shadowed         g trim    w specular    a accent
 *
 * R is mixed from the SKIN's lightest step and then used on cloth and metal
 * too. That is deliberate: it is one lamp in the room, not a per-material
 * effect, and a rim that changes hue per surface stops reading as light. */
function portraitPalette(tint, kind) {
  const c = ramp(tint || '#4a5a8a');
  const person = PORTRAIT_PERSON[kind] || (PORTRAIT_FULL[kind] ? null : PORTRAIT_PERSON.scholar);
  const skin = ramp(person ? person.skin : kind === 'interviewer' ? '#b7b6c6' : '#c9a17c');
  const hair = ramp(person ? person.hair : '#302b38');
  const gold = ramp('#d8b04a');
  const pal = {
    o: '#0a0810',
    K: c.shadow2,
    s: skin.base, S: skin.shadow1, N: skin.light1,
    R: rimTone(skin.light2),
    h: hair.base, H: hair.light1, Y: hair.shadow1,
    c: c.base, C: c.light1, v: c.shadow1,
    g: gold.base,
    w: '#f2f4ff',
    a: c.light2,
  };
  pal.e = pal.o; pal.O = pal.o; pal.A = pal.a; pal.B = pal.v;
  pal.L = pal.C; pal.d = pal.v; pal.D = pal.K; pal.k = pal.K;
  return pal;
}

/* Expand one emote frame's sparse rows into a 24-wide overlay. Cached, because
 * the same seven faces are asked for by eleven characters. */
const featureCache = new Map();
function featureGrid(emote, frame) {
  const key = emote + ':' + frame;
  if (featureCache.has(key)) return featureCache.get(key);
  const rows = [];
  for (let y = 0; y < PORTRAIT_SIZE; y++) rows.push('.'.repeat(PORTRAIT_SIZE));
  const spec = (PORTRAIT_EMOTE[emote] || PORTRAIT_EMOTE.neutral)[frame & 1];
  for (const [y, s] of spec) {
    rows[y] = '.'.repeat(7) + s + '.'.repeat(PORTRAIT_SIZE - 7 - s.length);
  }
  featureCache.set(key, rows);
  return rows;
}

/* Brass has a bright bevel and a dark return; porcelain has broad, quiet
 * facets. Keep the authored lamps and expressive strips as the focal points. */
function portraitFullMaterials(kind, grid) {
  return grid.map((row, y) => [...row].map((ch, x) => {
    if (kind === 'automaton_small' && ch === 'g') {
      return x > 15 || y > 19 ? 'v' : x < 8 || y < 5 ? 'C' : 'c';
    }
    if (kind === 'interviewer' && ch === 'w' && y < 15) {
      return x > 14 || y > 11 ? 'S' : x > 10 && y > 3 ? 's' : 'w';
    }
    return ch;
  }).join(''));
}

/* Swap the lamp glyph inside a machine's core band. */
function lampGrid(grid, band, glyph) {
  if (!band || glyph === 'w') return grid;
  return grid.map((row, y) => (y < band[0] || y > band[1]) ? row
    : row.split('').map(ch => ch === 'w' ? glyph : ch).join(''));
}

/* Stamp one eight-character strip over a faceplate row. */
function stampRow(grid, y, x0, strip) {
  if (!strip) return grid;
  return grid.map((row, ry) => {
    if (ry !== y) return row;
    const cells = row.split('');
    for (let i = 0; i < strip.length; i++) {
      if (strip[i] !== '.') cells[x0 + i] = strip[i];
    }
    return cells.join('');
  });
}

/* The Interviewer's mask has no features at all, which is the point of it — so
 * it borrows the human brow and eye strips and nothing else. A blank porcelain
 * face that suddenly has an opinion above the eyes is worth more than any mouth
 * we could have drawn on it. */
function maskFeatures(emote, frame) {
  const src = featureGrid(emote, frame);
  const blank = '.'.repeat(PORTRAIT_SIZE);
  return src.map((row, y) => (y < 6 || y > 9) ? blank
    : row.replace(/h/g, 'K').replace(/w/g, 'v').replace(/S/g, 'v'));
}

const portraitCache = new Map();
const PORTRAIT_CACHE_MAX = 256;

/* One face, one emote, one of its two frames.
 *
 * The order of the merge is the whole argument of the section: the head carries
 * the anatomy, the emote overlay carries the performance, the garment and the
 * headwear carry who this is — and only then, once every layer is in one grid,
 * does the light run over all of it at once. Light applied per layer is how a
 * composited portrait ends up looking assembled rather than drawn. */
export function portraitEmote(kind, emote = 'neutral', frame = 0) {
  const key = PORTRAIT_ALIAS[kind] || kind || 'scholar';
  const em = emoteKey(emote);
  const f = frame & 1;
  const ck = `${key}:${em}:${f}`;
  if (portraitCache.has(ck)) return portraitCache.get(ck);
  const tint = PORTRAIT_TINT[key] || PORTRAIT_TINT.scholar;
  const pal = portraitPalette(tint, key);
  let grid;
  if (PORTRAIT_FULL[key]) {
    const lamp = (PORTRAIT_LAMP[em] || PORTRAIT_LAMP.neutral)[f];
    grid = lampGrid(portraitFullMaterials(key, PORTRAIT_FULL[key]), PORTRAIT_LAMP_BAND[key], lamp);
    if (key === 'automaton_small') {
      grid = stampRow(grid, AUTOMATON_SHUTTER_Y, AUTOMATON_X,
        (AUTOMATON_SHUTTER[em] || AUTOMATON_SHUTTER.neutral)[f]);
      grid = stampRow(grid, AUTOMATON_VENT_Y, AUTOMATON_X,
        (AUTOMATON_VENT[em] || AUTOMATON_VENT.neutral)[f]);
    } else {
      grid = mergeGrids(PORTRAIT_SIZE, PORTRAIT_SIZE,
        [{ grid }, { grid: maskFeatures(em, f) }]);
    }
    // Machines breathe too: the whole chassis settles a pixel on the off frame.
    if (f === 1 && (em === 'alarmed' || em === 'delighted')) grid = bobGrid(grid, -1);
    else if (f === 1 && em === 'defeated') grid = bobGrid(grid, 1);
    grid = normalise(grid, PORTRAIT_SIZE);
  } else {
    const crown = portraitMaterials(PORTRAIT_CROWN[key] || PORTRAIT_CROWN.scholar);
    const garb = portraitMaterials(PORTRAIT_GARB[key] || PORTRAIT_GARB.scholar);
    grid = mergeGrids(PORTRAIT_SIZE, PORTRAIT_SIZE, [
      { grid: portraitAnatomy(key) },
      { grid: featureGrid(em, f) },
      { grid: garb, oy: 18 },
      { grid: crown },
    ]);
  }
  grid = rimLowLeft(applyRim(grid), 'R', 'wWe');
  const canvas = gridSprite(grid, pal, PORTRAIT_SIZE, PORTRAIT_SIZE);
  portraitCache.set(ck, canvas);
  capCache(portraitCache, PORTRAIT_CACHE_MAX);
  return canvas;
}

/* The old single-canvas entry point, unchanged for every caller that just wants
 * a face beside a line of dialogue. */
export function portrait(kind) {
  return portraitEmote(kind, 'neutral', 0);
}

/* Both frames of one emote, in order, ready to alternate on EMOTE_TIMING. */
export function portraitFrames(kind, emote = 'neutral') {
  return [portraitEmote(kind, emote, 0), portraitEmote(kind, emote, 1)];
}

/* The whole set for one character, keyed by emote. Seven states, two frames
 * each: what a dialogue system wants to be handed once and then index. */
export function portraitEmotes(kind) {
  const out = {};
  for (const e of EMOTE_KEYS) out[e] = portraitFrames(kind, e);
  return out;
}

/* The one call a caller actually needs per tick: hand it a mood and the clock
 * and it returns the canvas to draw. Deterministic — the same arguments always
 * answer with the same frame — and the seed only shifts the phase, so two
 * mentors on screen do not blink in lockstep. */
export function portraitAt(kind, emote, timeMs = 0, seed = 0) {
  const pose = emotePose(emote, timeMs, seed);
  return portraitEmote(kind, pose.key, pose.frame);
}

/* A portrait's silhouette at thumbnail size. Faces are the one place where a
 * good silhouette is not enough — two mentors in the same hood are the same
 * shape — so this checks the thing a silhouette CAN prove: that the headwear
 * tells them apart before any pixel of the face is read. */
export function portraitSilhouette(kind) {
  const key = PORTRAIT_ALIAS[kind] || kind || 'scholar';
  if (PORTRAIT_FULL[key]) return silhouetteAt(PORTRAIT_FULL[key], 16);
  return silhouetteAt(mergeGrids(PORTRAIT_SIZE, PORTRAIT_SIZE, [
    { grid: portraitAnatomy(key) },
    { grid: PORTRAIT_GARB[key] || PORTRAIT_GARB.scholar, oy: 18 },
    { grid: PORTRAIT_CROWN[key] || PORTRAIT_CROWN.scholar },
  ]), 16);
}

/* ================================================================
 * DRAWING HELPERS
 * ================================================================ */

const scaleCache = new Map();
let scaleSeq = 0;

/* Pre-scale a sprite by an INTEGER factor once, instead of letting CSS stretch
 * a 48px canvas to 128px — a 2.667x upscale lands source pixels on fractional
 * boundaries and softens the whole sprite despite image-rendering: pixelated. */
export function scaleSprite(img, factor) {
  if (!img || factor <= 1) return img;
  const f = Math.max(1, Math.round(factor));
  if (!img.__spriteId) { img.__spriteId = ++scaleSeq; }
  const key = `${img.__spriteId}:${f}`;
  if (scaleCache.has(key)) return scaleCache.get(key);
  const { canvas, ctx } = make(img.width * f, img.height * f);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, 0, 0, img.width, img.height, 0, 0, img.width * f, img.height * f);
  scaleCache.set(key, canvas);
  return canvas;
}

/* Turn a motion descriptor into this instant's offset and frame. One call per
 * sprite per tick; the caller does not need to know what a phase is.
 *
 *   const m = sprites.enemyMotion(enemy.sprite);
 *   const { dx, dy, frame } = sprites.idlePose(m, performance.now());
 *   ctx.drawImage(sprites.enemySprite(enemy.sprite, pattern, frame), x + dx, y + dy);
 */
export function idlePose(motion, timeMs, seed = 0) {
  const m = motion || ENEMY_MOTION.slime;
  const t = (timeMs / m.period) + m.phase + seed * 0.137;
  const cycle = t - Math.floor(t);
  const wave = Math.sin(cycle * Math.PI * 2);
  return {
    dx: Math.round(Math.cos(cycle * Math.PI * 2) * (m.sway || 0)),
    dy: -Math.round(Math.abs(wave) * (m.bob || 0)),
    frame: cycle < 0.5 ? 0 : 1,
    cycle,
  };
}

/* Shadow size that suits a sprite: wide and shallow, tucked under the feet. */
export function shadowFor(size) {
  const rx = Math.max(2, Math.round(size * 0.34));
  return { rx, ry: Math.max(1, Math.round(rx * 0.38)) };
}
