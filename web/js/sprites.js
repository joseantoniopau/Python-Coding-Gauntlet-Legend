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
 * authored frames each, on the hero at six pixels wide and on the portraits at
 * fourteen. The brow does most of the work in both, which is the one technique
 * worth stealing from the 16-bit era wholesale: a mouth at this resolution has
 * about two shapes in it, and a brow can move a whole row.
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

const HERO_BODY = {
  down: [
    '................',
    '.....oooooo.....',
    '....oHhhhhho....',
    '...oHhhhhhhho...',
    '...ohsssssSho...',
    '...ohsssssSho...',
    '...ohsssssSho...',
    '...ohNssssSho...',
    '....oNssssSo....',
    '..occcccccccco..',
    '.occcccccccccco.',
    '.occttttttttcco.',
    '.octttTTTTtttco.',
    '..octtttttttco..',
    '..ocggggggggco..',
    '...octtttttco...',
    '...occttttcco...',
    '...occcccccco...',
  ],
  up: [
    '................',
    '.....oooooo.....',
    '....oHhhhhho....',
    '...oHhhhhhhho...',
    '...oHhhhhhhho...',
    '...ohhhhhhhho...',
    '...ohhHHHHhho...',
    '...ohhhhhhhho...',
    '....ohhhhhho....',
    '..occcccccccco..',
    '.occcccccccccco.',
    '.occccCCCCcccco.',
    '.occcCCCCCCccco.',
    '..occcccccccco..',
    '..occggggggcco..',
    '...occcccccco...',
    '...occcccccco...',
    '...occcccccco...',
  ],
  left: [
    '................',
    '....oooooo......',
    '...oshhhhho.....',
    '..oNssshhhho....',
    '..oNssshhhho....',
    '..oNssshhhho....',
    '..oNssshhhho....',
    '..oNssshhhSo....',
    '...oNssshho.....',
    '..occcccccccco..',
    '.ottttcccccccco.',
    '.otTTtcccccccco.',
    '.ottttcccccccco.',
    '..oggggcccccco..',
    '..ottttcccccco..',
    '..otttccccccco..',
    '...occccccccco..',
    '...occcccccco...',
  ],
  right: [
    '................',
    '......oooooo....',
    '.....oHhhhhho...',
    '....oHhhhsssso..',
    '....oHhhhsssso..',
    '....oHhhhsssso..',
    '....oHhhhsssso..',
    '....oHhhhsssSo..',
    '.....ohhsssSo...',
    '..occcccccccco..',
    '.occcccccctttto.',
    '.occcccccctTTto.',
    '.occcccccctttto.',
    '..occccccggggo..',
    '..occcccctttto..',
    '..occcccccttto..',
    '..occccccccco...',
    '...occcccccco...',
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
    ['occ..........cc.', 'occ..........cco', 'oss..........cco', '.oo..........sso', '..............oo', '................'],
    ['occ..........cco', 'occ..........cco', 'oss..........sso', '.oo..........oo.', '................', '................'],
    ['.cc..........cco', 'occ..........cco', 'occ..........sso', 'oss..........oo.', '.oo.............', '................'],
    ['occ..........cco', 'occ..........cco', 'oss..........sso', '.oo..........oo.', '................', '................'],
  ],
  up: [
    ['occ..........cc.', 'occ..........cco', 'ovv..........cco', '.oo..........vvo', '..............oo', '................'],
    ['occ..........cco', 'occ..........cco', 'ovv..........vvo', '.oo..........oo.', '................', '................'],
    ['.cc..........cco', 'occ..........cco', 'occ..........vvo', 'ovv..........oo.', '.oo.............', '................'],
    ['occ..........cco', 'occ..........cco', 'ovv..........vvo', '.oo..........oo.', '................', '................'],
  ],
  left: [
    ['occ.............', 'occ.............', 'oss.............', '.oo.............', '................', '................'],
    ['................', 'occ.............', 'occ.............', 'oss.............', '.oo.............', '................'],
    ['.............cco', '.............cco', '.............sso', '.............oo.', '................', '................'],
    ['................', 'occ.............', 'occ.............', 'oss.............', '.oo.............', '................'],
  ],
  right: [
    ['.............cco', '.............cco', '.............sso', '.............oo.', '................', '................'],
    ['................', '.............cco', '.............cco', '.............sso', '.............oo.', '................'],
    ['occ.............', 'occ.............', 'oss.............', '.oo.............', '................', '................'],
    ['................', '.............cco', '.............cco', '.............sso', '.............oo.', '................'],
  ],
};

/* Three rows at y=17, drawn behind the legs and swayed a pixel per frame. */
const HERO_HEM = {
  down: [
    '..occcccccccco..',
    '.occcccccccccco.',
    '..ovvvvvvvvvvo..',
  ],
  up: [
    '..occcccccccco..',
    '.occcccccccccco.',
    '.ovvvvvvvvvvvvo.',
  ],
  left: [
    '..occcccccccco..',
    '.occccccccccco..',
    '..ovvvvvvvvo....',
  ],
  right: [
    '..occcccccccco..',
    '..occccccccccco.',
    '....ovvvvvvvvo..',
  ],
};

/* Arms up, weapon raised, for a CAST. The pose has to read at a glance from the
 * battle panel, so the silhouette breaks the body box on both sides. */
const HERO_CAST_ARMS = {
  down: [
    'occ..........cco',
    'oss..........sso',
    '.oo..........oo.',
    '................',
    '................',
    '................',
  ],
  up: [
    'occ..........cco',
    'ovv..........vvo',
    '.oo..........oo.',
    '................',
    '................',
    '................',
  ],
  left: [
    'occ.............',
    'oss.............',
    '.oo.............',
    '................',
    '................',
    '................',
  ],
  right: [
    '.............cco',
    '.............sso',
    '.............oo.',
    '................',
    '................',
    '................',
  ],
};

/* ---------- the face ----------
 *
 * Five rows stamped over the skull at y=4. The hero's face is six pixels wide;
 * there is no room to be subtle, which is exactly why the BROW has to do the
 * work. Look down these tables in a column: the mouth barely changes between
 * strained and stubborn, and the two poses still read as different states,
 * because one has the brow driven down into the eye and the other has it flat
 * and heavy. That is the whole principle, applied at six pixels.
 *
 * Two frames each, so every emote can breathe: frame 1 is a blink, a squeeze or
 * a jaw-set rather than the same face two pixels brighter. */
const HERO_FACE_FRONT = {
  neutral: [
    ['................', '.....hh..hh.....', '.....wo..ow.....', '................', '.......oo.......'],
    ['................', '.....hh..hh.....', '.....oo..oo.....', '................', '.......oo.......'],
  ],
  pleased: [
    ['.....hh..hh.....', '.....o....o.....', '.....wo..ow.....', '................', '......oooo......'],
    ['.....hh..hh.....', '.....o....o.....', '......o..o......', '................', '......oooo......'],
  ],
  strained: [
    ['................', '.....ho..oh.....', '.....oo..oo.....', '......oooo......', '......wwww......'],
    ['................', '.....oh..ho.....', '.....oo..oo.....', '......oooo......', '......oooo......'],
  ],
  alarmed: [
    ['.....hh..hh.....', '................', '.....ww..ww.....', '.....wo..ow.....', '.......oo.......'],
    ['.....hh..hh.....', '................', '.....wo..ow.....', '.....ww..ww.....', '.......oo.......'],
  ],
  stubborn: [
    ['................', '.....hhhhhh.....', '.....wo..ow.....', '................', '.....oooooo.....'],
    ['................', '.....hhhhhh.....', '.....oo..oo.....', '................', '.....oooooo.....'],
  ],
  delighted: [
    ['.....hh..hh.....', '......o..o......', '.....o....o.....', '.....oooooo.....', '......wwww......'],
    ['.....hh..hh.....', '......o..o......', '.....oo..oo.....', '.....oooooo.....', '......wwww......'],
  ],
  defeated: [
    ['......h..h......', '.....h....h.....', '.....oo..oo.....', '................', '......o..o......'],
    ['......h..h......', '.....h....h.....', '................', '.......oo.......', '......o..o......'],
  ],
};

/* The profile face: one eye and a four-pixel jaw, authored for `left` and
 * mirrored for `right`. The head is the one part of the hero that IS a true
 * mirror between the two side views — the torso is not, which is why the bodies
 * stay authored separately. */
const HERO_FACE_PROFILE = {
  neutral: [
    ['................', '...hhh..........', '....wo..........', '................', '...oo...........'],
    ['................', '...hhh..........', '....oo..........', '................', '...oo...........'],
  ],
  pleased: [
    ['...hhh..........', '...o............', '....wo..........', '................', '...ooo..........'],
    ['...hhh..........', '...o............', '.....o..........', '................', '...ooo..........'],
  ],
  strained: [
    ['................', '...hho..........', '....oo..........', '...oooo.........', '...www..........'],
    ['................', '...ohh..........', '....oo..........', '...oooo.........', '...ooo..........'],
  ],
  alarmed: [
    ['...hhh..........', '................', '....ww..........', '....wo..........', '....oo..........'],
    ['...hhh..........', '................', '....wo..........', '....ww..........', '....oo..........'],
  ],
  stubborn: [
    ['................', '...hhhh.........', '....wo..........', '................', '...oooo.........'],
    ['................', '...hhhh.........', '....oo..........', '................', '...oooo.........'],
  ],
  delighted: [
    ['...hhh..........', '.....o..........', '....o...........', '...oooo.........', '...www..........'],
    ['...hhh..........', '.....o..........', '....oo..........', '...oooo.........', '...www..........'],
  ],
  defeated: [
    ['....hh..........', '...h............', '....oo..........', '................', '...oo...........'],
    ['....hh..........', '...h............', '................', '....oo..........', '...oo...........'],
  ],
};

/* Weapons live in a 6x12 box and are stamped into the lead hand. They are the
 * only part of the hero that equipment changes structurally; everything else
 * equipment touches is a tint. */
const HERO_WEAPONS = {
  sword:  ['..o...', '.oMo..', '.oMo..', '.oMo..', '.oMo..', '.oMo..',
           '.oMo..', 'ogggo.', '..u...', '..u...', '.ouo..', '......'],
  sabers: ['......', '..o...', '.oMo..', '.oMo..', '.oMo..', '.oMo..',
           'ogggo.', '..u...', '.ouo..', '......', '......', '......'],
  dagger: ['......', '......', '..o...', '.oMo..', '.oMo..', '.oMo..',
           'ogggo.', '..u...', '.ouo..', '......', '......', '......'],
  axe:    ['.oooo.', 'oMMgMo', 'oMggMo', '.oMMo.', '..ou..', '..ou..',
           '..ou..', '..ou..', '..ou..', '..ou..', '..oo..', '......'],
  hammer: ['.oooo.', 'oMMMMo', 'oMggMo', 'oMMMMo', '.oouo.', '..ou..',
           '..ou..', '..ou..', '..ou..', '..ou..', '..oo..', '......'],
  spear:  ['..o...', '.oMo..', 'oMMMo.', '.oMo..', '..u...', '..u...',
           '..u...', '..u...', '..u...', '..u...', '..u...', '..o...'],
  lance:  ['..o...', '.oMo..', '.oMo..', 'oMMMo.', '.ogo..', '..u...',
           '..u...', '..u...', '..u...', '..u...', '..u...', '..o...'],
  staff:  ['..o...', '.ogo..', 'ogWgo.', '.ogo..', '..o...', '..u...',
           '..u...', '..u...', '..u...', '..u...', '..u...', '..o...'],
  bow:    ['.oo...', 'og.o..', 'og..o.', 'og..o.', 'og..o.', 'og..o.',
           'og..o.', 'og..o.', 'og..o.', 'og.o..', '.oo...', '......'],
  relic:  ['......', '..oo..', '.ogWo.', 'ogWWgo', 'ogWWgo', '.ogWo.',
           '..oo..', '..u...', '..u...', '..oo..', '......', '......'],
};

/* Where the lead hand is, per facing: [ox, oy] of the weapon box. */
const WEAPON_ANCHOR = {
  down:  [10, 6], up: [1, 5], left: [-1, 6], right: [11, 6],
};

const DEFAULT_HERO = {
  cloak: '#3f6fa8', tunic: '#5a4a6a', skin: '#e8b88a', hair: '#4a3050',
  boot: '#40312c', trim: '#d8b04a', metal: '#c3cbd8', weapon: 'sword',
  emote: 'neutral',
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
  pal.b = pal.v; pal.u = pal.v; pal.d = pal.v;
  pal.m = pal.g; pal.M = pal.w; pal.W = pal.w; pal.r = pal.R;
  pal.L = pal.C; pal.B = pal.c;
  return pal;
}

/* ---------- frames ---------- */

const heroCache = new Map();
const HERO_CACHE_MAX = 512;

const mirrorRow = (r) => r.split('').reverse().join('');
const HERO_FACE_PROFILE_R = {};
for (const k of Object.keys(HERO_FACE_PROFILE)) {
  HERO_FACE_PROFILE_R[k] = HERO_FACE_PROFILE[k].map(f => f.map(mirrorRow));
}

function heroKey(o, facing, frame, pose, emote) {
  return `${facing}:${frame}:${pose}:${emote}:${o.cloak}:${o.tunic}:${o.skin}`
       + `:${o.hair}:${o.boot}:${o.trim}:${o.metal}:${o.weapon}`;
}

/* pose: 'walk' | 'idle' | 'cast'. `opts.emote` picks the face, and the face's
 * own two frames advance with the sprite's, so a hero who is walking is also
 * blinking without the caller having to drive a second clock. */
export function heroFrame(facing = 'down', frame = 0, opts, pose = 'walk') {
  const o = heroOpts(opts);
  const dir = HERO_BODY[facing] ? facing : 'down';
  const emote = emoteKey(o.emote);
  const key = heroKey(o, dir, frame, pose, emote);
  if (heroCache.has(key)) return heroCache.get(key);
  const pal = heroPalette(o);
  const f = ((frame % 4) + 4) % 4;
  const pass = f === 1 || f === 3;

  let body = HERO_BODY[dir];
  let legs = HERO_LEGS[dir][f];
  let arms = pose === 'cast' ? HERO_CAST_ARMS[dir] : HERO_ARMS[dir][f];
  let hem = HERO_HEM[dir];
  let bodyY = 0, armY = 10, weaponY = 0, faceY = 0;
  let faceFrame = (f >> 1) & 1;

  if (pose === 'walk') {
    // The pass frames lift the whole upper body a pixel. Without it the hero
    // glides; with it, he walks.
    if (pass) { bodyY = -1; armY = 9; weaponY = -1; }
    hem = shiftRows(hem, 1, 2, f === 0 ? -1 : f === 2 ? 1 : 0);
  } else if (pose === 'idle') {
    // A breath, not a brightness nudge. On the settled frame the head sinks
    // into the shoulders, the chest widens to take the mass that went
    // somewhere, the cloak hangs a pixel to the left and the weapon drops with
    // the hands; on the other he is back up on the inhale. Feet stay on the
    // contact pose throughout, so he is standing in a stance rather than at
    // attention — which is the difference between a character and a statue.
    legs = HERO_LEGS[dir][0];
    arms = HERO_ARMS[dir][1];
    faceFrame = f & 1;
    if ((f & 1) === 0) {
      body = widenRows(sinkRows(body, 0, 9, 1), 11, 13);
      armY = 11; weaponY = 1; faceY = 1;
      hem = shiftRows(hem, 1, 2, -1);
    } else {
      hem = shiftRows(hem, 1, 2, 1);
    }
  } else if (pose === 'cast') {
    legs = HERO_LEGS[dir][1];
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
  const weapon = o.weapon == null ? null : (HERO_WEAPONS[o.weapon] || HERO_WEAPONS.sword);
  const anchor = WEAPON_ANCHOR[dir];
  const layers = [
    { grid: hem, oy: 17 },
    { grid: legs, oy: 18 },
    { grid: body, oy: bodyY },
  ];
  if (face) layers.push({ grid: face, oy: 4 + bodyY + faceY });
  layers.push({ grid: arms, oy: armY });
  // Facing away, the weapon is behind the body; facing the camera it is in front.
  if (weapon) {
    const weaponLayer = { grid: weapon, ox: anchor[0], oy: anchor[1] + weaponY };
    if (dir === 'up') layers.splice(1, 0, weaponLayer); else layers.push(weaponLayer);
  }

  // One grid, then one light. Merging first is the point: the rim has to run
  // over cloak, arm, boot and blade at once or it stops at a layer boundary and
  // the hero comes apart into the pieces he was built from.
  const grid = rimLowLeft(applyRim(mergeGrids(HERO_W, HERO_H, layers)), 'R', 'wWMe');
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
  const f = ((frame % 4) + 4) % 4;
  const arms = pose === 'cast' ? HERO_CAST_ARMS[dir] : HERO_ARMS[dir][f];
  const weapon = o.weapon == null ? null : (HERO_WEAPONS[o.weapon] || HERO_WEAPONS.sword);
  const anchor = WEAPON_ANCHOR[dir];
  return silhouetteAt(mergeGrids(HERO_W, HERO_H, [
    { grid: HERO_HEM[dir], oy: 17 },
    { grid: HERO_LEGS[dir][f], oy: 18 },
    { grid: HERO_BODY[dir] },
    { grid: arms, oy: 10 },
    weapon ? { grid: weapon, ox: anchor[0], oy: anchor[1] } : null,
  ].filter(Boolean)), 16);
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
  vaultling: 'vault',
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
  vaultling: '#e8a33d',
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
 * 24x24. A shared head carries the anatomy, a brow/eye/mouth overlay carries
 * the EMOTION, and a headwear grid plus a garment grid carry who this is. Two
 * of them (BYTE and the Interviewer) are not human enough to share a face and
 * are authored whole.
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
function portraitPalette(tint) {
  const c = ramp(tint || '#4a5a8a');
  const skin = ramp('#e8b88a');
  const hair = ramp(mix(tint || '#4a5a8a', '#2a2038', 0.55));
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
  const pal = portraitPalette(tint);
  let grid;
  if (PORTRAIT_FULL[key]) {
    const lamp = (PORTRAIT_LAMP[em] || PORTRAIT_LAMP.neutral)[f];
    grid = lampGrid(PORTRAIT_FULL[key], PORTRAIT_LAMP_BAND[key], lamp);
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
    const crown = PORTRAIT_CROWN[key] || PORTRAIT_CROWN.scholar;
    const garb = PORTRAIT_GARB[key] || PORTRAIT_GARB.scholar;
    grid = mergeGrids(PORTRAIT_SIZE, PORTRAIT_SIZE, [
      { grid: PORTRAIT_FACE },
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
    { grid: PORTRAIT_FACE },
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
