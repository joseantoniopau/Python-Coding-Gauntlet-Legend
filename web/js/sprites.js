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
    '....ohhhhhho....',
    '...ohhhhhhhho...',
    '...ohhsssshho...',
    '...oswessweso...',
    '...osssssssso...',
    '...osssSSssso...',
    '....osssssso....',
    '...occcccccco...',
    '..occcccccccco..',
    '..octtttttttco..',
    '..octtTTTTttco..',
    '..octtttttttco..',
    '..ocggggggggco..',
    '..octtttttttco..',
    '..occttttttcco..',
    '...occcccccco...',
  ],
  up: [
    '................',
    '.....oooooo.....',
    '....ohhhhhho....',
    '...ohhhhhhhho...',
    '...ohhhhhhhho...',
    '...ohhhhhhhho...',
    '...ohhhHhhhho...',
    '...ohhhhhhhho...',
    '....ohhhhhho....',
    '...occcccccco...',
    '..occcccccccco..',
    '..occcCCCCccco..',
    '..occcCCCCccco..',
    '..occcccccccco..',
    '..occggggggcco..',
    '..occcccccccco..',
    '..occcccccccco..',
    '...occcccccco...',
  ],
  left: [
    '................',
    '....oooooo......',
    '...ohhhhhho.....',
    '..ohhhhhhhho....',
    '..ohsssshhho....',
    '..oswesshhho....',
    '..ossssshhho....',
    '..osSssshhho....',
    '...osssshho.....',
    '..occcccccco....',
    '..ottttccccco...',
    '..otTTtcccccco..',
    '..ottttcccccco..',
    '..oggggcccccco..',
    '..ottttcccccco..',
    '..otttccccccco..',
    '..occcccccccco..',
    '...occcccccco...',
  ],
  right: [
    '................',
    '......oooooo....',
    '.....ohhhhhho...',
    '....ohhhhhhhho..',
    '....ohhhssssho..',
    '....ohhhssweso..',
    '....ohhhssssso..',
    '....ohhhsssSso..',
    '.....ohhsssso...',
    '....occcccccco..',
    '...occccctttto..',
    '..occccccttTTo..',
    '..occcccctttto..',
    '..occccccggggo..',
    '..occcccctttto..',
    '..occcccccttto..',
    '..occcccccccco..',
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

/* Six rows, drawn at y=10, over the body. Arms swing against the legs: on the
 * frame where the left boot is planted, the right hand is forward. */
const HERO_ARMS = {
  down: [
    ['.occ........cc..', '.occ........cco.', '.oss........cco.',
     '..oo........sso.', '............oo..', '................'],
    ['.occ........cco.', '.occ........cco.', '.oss........sso.',
     '..oo........oo..', '................', '................'],
    ['..cc........cco.', '.occ........cco.', '.occ........sso.',
     '.oss........oo..', '..oo............', '................'],
    ['.occ........cco.', '.occ........cco.', '.oss........sso.',
     '..oo........oo..', '................', '................'],
  ],
  up: [
    ['.occ........cc..', '.occ........cco.', '.ovc........cco.',
     '..oo........vco.', '............oo..', '................'],
    ['.occ........cco.', '.occ........cco.', '.ovc........cvo.',
     '..oo........oo..', '................', '................'],
    ['..cc........cco.', '.occ........cco.', '.occ........cvo.',
     '.ovc........oo..', '..oo............', '................'],
    ['.occ........cco.', '.occ........cco.', '.ovc........cvo.',
     '..oo........oo..', '................', '................'],
  ],
  left: [
    ['.occ............', '.occ............', '.oss............',
     '..oo............', '................', '................'],
    ['................', '.occ............', '.occ............',
     '.oss............', '..oo............', '................'],
    ['............cco.', '............cco.', '............sso.',
     '............oo..', '................', '................'],
    ['................', '.occ............', '.occ............',
     '.oss............', '..oo............', '................'],
  ],
  right: [
    ['............cco.', '............cco.', '............sso.',
     '............oo..', '................', '................'],
    ['................', '............cco.', '............cco.',
     '............sso.', '............oo..', '................'],
    ['.occ............', '.occ............', '.oss............',
     '..oo............', '................', '................'],
    ['................', '............cco.', '............cco.',
     '............sso.', '............oo..', '................'],
  ],
};

/* Three rows at y=17, drawn behind the legs and swayed a pixel per frame. */
const HERO_HEM = {
  down:  ['..occcccccccco..', '..ovccccccccvo..', '...ovvvvvvvvo...'],
  up:    ['..occcccccccco..', '..ovccccccccvo..', '..ovvvvvvvvvvo..'],
  left:  ['..occcccccccco..', '...occcccccccvo.', '....ovvvvvvvvo..'],
  right: ['..occcccccccco..', '.ovccccccccco...', '..ovvvvvvvvo....'],
};

/* Arms up, weapon raised, for a CAST. The pose has to read at a glance from the
 * battle panel, so the silhouette breaks the body box on both sides. */
const HERO_CAST_ARMS = {
  down: ['occ..........cco', 'oss..........sso', '.oo..........oo.',
         '................', '................', '................'],
  up:   ['occ..........cco', 'ovc..........cvo', '.oo..........oo.',
         '................', '................', '................'],
  left: ['occ.............', 'oss.............', '.oo.............',
         '................', '................', '................'],
  right:['.............cco', '.............sso', '.............oo.',
         '................', '................', '................'],
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
};

/* Equipment tints the hero rather than replacing him: a region palette can be
 * passed straight in and its accent becomes the trim. */
function heroOpts(opts) {
  if (!opts) return { ...DEFAULT_HERO };
  if (opts.sky && opts.ground) return { ...DEFAULT_HERO, trim: opts.accent || DEFAULT_HERO.trim };
  return { ...DEFAULT_HERO, ...opts };
}

export function heroPalette(opts) {
  const o = heroOpts(opts);
  const cloak = ramp(o.cloak), tunic = ramp(o.tunic), skin = ramp(o.skin);
  const hair = ramp(o.hair), boot = ramp(o.boot), trim = ramp(o.trim), metal = ramp(o.metal);
  return {
    o: mix(cloak.outline, '#0c0a14', 0.6), O: cloak.shadow2,
    h: hair.base, H: hair.light1,
    s: skin.base, S: skin.shadow1, w: '#fdfdff', e: '#1d1628',
    c: cloak.base, C: cloak.light1, v: cloak.shadow1,
    t: tunic.base, T: tunic.light1, u: tunic.shadow1,
    p: tunic.shadow2, b: boot.base, k: boot.light1,
    g: trim.base, m: metal.base, M: metal.light1, W: '#f4f8ff',
    r: trim.light2,
  };
}

const heroCache = new Map();

function heroKey(o, facing, frame, pose) {
  return `${facing}:${frame}:${pose}:${o.cloak}:${o.tunic}:${o.skin}:${o.hair}:${o.boot}:${o.trim}:${o.weapon}`;
}

/* pose: 'walk' | 'idle' | 'cast'. Frame is ignored for 'cast'. */
export function heroFrame(facing = 'down', frame = 0, opts, pose = 'walk') {
  const o = heroOpts(opts);
  const dir = HERO_BODY[facing] ? facing : 'down';
  const key = heroKey(o, dir, frame, pose);
  if (heroCache.has(key)) return heroCache.get(key);
  const pal = heroPalette(o);
  const f = ((frame % 4) + 4) % 4;
  const pass = f === 1 || f === 3;

  let body = HERO_BODY[dir];
  let legs = HERO_LEGS[dir][f];
  let arms = pose === 'cast' ? HERO_CAST_ARMS[dir] : HERO_ARMS[dir][f];
  let hem = HERO_HEM[dir];
  let bodyY = 0, armY = 10, weaponY = 0;

  if (pose === 'walk') {
    // The pass frames lift the whole upper body a pixel. Without it the hero
    // glides; with it, he walks.
    if (pass) { bodyY = -1; armY = 9; weaponY = -1; }
    hem = shiftRows(hem, 1, 2, f === 0 ? -1 : f === 2 ? 1 : 0);
  } else if (pose === 'idle') {
    legs = HERO_LEGS[dir][1];
    arms = HERO_ARMS[dir][1];
    // Breathing: the head settles into the shoulders and the chest widens.
    body = widenRows(sinkRows(body, 0, 9, 1), 11, 13);
    bodyY = 0; armY = 11; weaponY = 1;
  } else if (pose === 'cast') {
    legs = HERO_LEGS[dir][1];
    bodyY = -1; armY = 8; weaponY = -6;
  }

  const weapon = HERO_WEAPONS[o.weapon] || HERO_WEAPONS.sword;
  const anchor = WEAPON_ANCHOR[dir];
  const layers = [
    { grid: hem, oy: 17 },
    { grid: legs, oy: 18 },
    { grid: applyRim(body), oy: bodyY },
    { grid: arms, oy: armY },
  ];
  // Facing away, the weapon is behind the body; facing the camera it is in front.
  const weaponLayer = { grid: weapon, ox: anchor[0], oy: anchor[1] + weaponY };
  if (dir === 'up') layers.splice(1, 0, weaponLayer); else layers.push(weaponLayer);

  const canvas = composeSprite(HERO_W, HERO_H, layers, pal);
  heroCache.set(key, canvas);
  return canvas;
}

/* Four-frame contact/pass/contact/pass cycle. Drive it from distance travelled,
 * not the wall clock, or the feet slide. */
export const HERO_WALK_ORDER = [0, 1, 2, 3];

/* Drop-in superset of pixel.heroSprites: `side` still resolves, but `left` and
 * `right` are authored, so nothing needs mirroring. */
export function heroSprites(opts) {
  const out = {};
  for (const facing of ['down', 'up', 'left', 'right']) {
    out[facing] = HERO_WALK_ORDER.map(f => heroFrame(facing, f, opts, 'walk'));
  }
  out.side = out.right;
  out.idle = {};
  out.cast = {};
  for (const facing of ['down', 'up', 'left', 'right']) {
    out.idle[facing] = [heroFrame(facing, 1, opts, 'idle'), heroFrame(facing, 3, opts, 'walk')];
    out.cast[facing] = heroFrame(facing, 0, opts, 'cast');
  }
  out.idle.side = out.idle.right;
  out.cast.side = out.cast.right;
  return out;
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
 * 24x24, up from 12x12 — at that size a face is four pixels and every mentor
 * is the same person in a different hat.
 *
 * A shared face carries the anatomy; a headwear grid and a garment grid carry
 * the character. Two of them (BYTE and the Interviewer) are not human enough
 * to share a face and are authored whole.
 */
const PORTRAIT_FACE = [
  '........................',
  '........................',
  '.......oooooooooo.......',
  '.....ooossssssssooo.....',
  '....oossssssssssssoo....',
  '....osssssssssssssso....',
  '....osssssssssssssso....',
  '....osssssssssssssso....',
  '....osswesssssswesso....',
  '....osseesssssseesso....',
  '....osssssssssssssso....',
  '....osssSssssssSssso....',
  '....osssssssssssssso....',
  '....osssssSSSSssssso....',
  '....osssssssssssssso....',
  '.....oossssssssssoo.....',
  '.......oossssssoo.......',
  '.........oSSSSo.........',
  '........osssssso........',
  '........................',
  '........................',
  '........................',
  '........................',
  '........................',
];

/* Headwear, drawn over the skull. Eight rows is enough for a hood, a hat brim,
 * a helm crest or a bare hairline. */
const PORTRAIT_CROWN = {
  scholar: [
    '........................',
    '......oooooooooooo......',
    '....oohhhhhhhhhhhhoo....',
    '...ohhhhhhhhhhhhhhhho...',
    '...ohhhhhhhhhhhhhhhho...',
    '...ohhhh........hhhho...',
    '...ohho..........ohho...',
    '...oo..............oo...',
  ],
  mage: [
    '...........oo...........',
    '.........oohhoo.........',
    '.......oohhhhhhoo.......',
    '.....oohhhhhhhhhhoo.....',
    '...oohhhhhhhhhhhhhhoo...',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..ogggggggggggggggggggo.',
    '..oo..................oo',
  ],
  ranger: [
    '........................',
    '.....oooooooooooooo.....',
    '...oohhhhhhhhhhhhhhoo...',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..ohhhhhhhhhhhhhhhhhho..',
    '...ohhhhh......hhhhho...',
    '....ohho........ohho....',
    '.....oo..........oo.....',
  ],
  druid: [
    '.....oo..........oo.....',
    '....ohho........ohho....',
    '...ohhhhoooooohhhhho....',
    '..ohhhhhhhhhhhhhhhhho...',
    '..ohhhhhhhhhhhhhhhhho...',
    '..ohhhhg......ghhhhho...',
    '...ohho........ohho.....',
    '....oo..........oo......',
  ],
  cartographer: [
    '........................',
    '..oooooooooooooooooooo..',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..oooooooooooooooooooo..',
    '....ohhhhhhhhhhhhhho....',
    '....ohhhhhhhhhhhhhho....',
    '....ohhhh........hhho...',
    '.....oo............oo...',
  ],
  armorer: [
    '.......oooooooooo.......',
    '.....oogggggggggggoo....',
    '....ogggggggggggggggo...',
    '....ogggggggggggggggo...',
    '....oggo..........oggo..',
    '....oggo..........oggo..',
    '.....oo............oo...',
    '........................',
  ],
  oracle: [
    '..........oooo..........',
    '........oowwwwoo........',
    '......oowwwwwwwwoo......',
    '....oowwwwwwwwwwwwoo....',
    '...owwwwwwwwwwwwwwwwo...',
    '...owwwwg......gwwwwo...',
    '....owwo........owwo....',
    '.....oo..........oo.....',
  ],
  smith: [
    '........................',
    '....oooooooooooooooo....',
    '...ohhhhhhhhhhhhhhhho...',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..oggggggggggggggggggo..',
    '..oggo............oggo..',
    '...oo..............oo...',
    '........................',
  ],
  chronomancer: [
    '..........oooo..........',
    '........oohhhhoo........',
    '......oohhhhhhhhoo......',
    '....oohhhhggggghhhhoo...',
    '...ohhhhgggggggghhhho...',
    '...ohhhhg......ghhhho...',
    '....ohho........ohho....',
    '.....oo..........oo.....',
  ],
  scribe: [
    '........................',
    '.....oooooooooooooo.....',
    '...oohhhhhhhhhhhhhhoo...',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..ohhhhhhhhhhhhhhhhhho..',
    '..ohhhoo........oohhho..',
    '...ohho..........ohho...',
    '....oo............oo....',
  ],
};

/* Garment, drawn over the neck and shoulders. */
const PORTRAIT_GARB = {
  scholar: [
    '......oooooooooooo......',
    '....ooccccccccccccoo....',
    '..ooccccccccccccccccoo..',
    '..occcccccgcccccccccco..',
    '..occcccccgcccccccccco..',
    '..oooooooooooooooooooo..',
  ],
  mage: [
    '......oooooooooooo......',
    '....ooccccccccccccoo....',
    '..oocccccgggggcccccoo...',
    '..occcccgggggggcccccco..',
    '..occcccccgggcccccccco..',
    '..oooooooooooooooooooo..',
  ],
  ranger: [
    '.....ooooooooooooo......',
    '...oocccccccccccccoo....',
    '..occccccgccccccccccco..',
    '..occccccgccccccccccco..',
    '..occccccgggccccccccco..',
    '..oooooooooooooooooooo..',
  ],
  druid: [
    '......oooooooooooo......',
    '....ooccccccccccccoo....',
    '..occcccgggggggccccco...',
    '..occcccccgggcccccccco..',
    '..occcccccccccccccccco..',
    '..oooooooooooooooooooo..',
  ],
  cartographer: [
    '......oooooooooooo......',
    '....ooccccccccccccoo....',
    '..oocccccccccccccccoo...',
    '..occcgggggggggggcccco..',
    '..occcgooooooooogcccco..',
    '..oooooooooooooooooooo..',
  ],
  armorer: [
    '.....ooooooooooooo......',
    '...oogggggggggggggoo....',
    '..oggggcccccccggggggo...',
    '..oggggcccccccggggggo...',
    '..ogggggggggggggggggo...',
    '..oooooooooooooooooooo..',
  ],
  oracle: [
    '......oooooooooooo......',
    '....oowwwwwwwwwwwwoo....',
    '..oowwwwwwgwwwwwwwwwoo..',
    '..owwwwwwwgwwwwwwwwwwo..',
    '..owwwwwwwwwwwwwwwwwwo..',
    '..oooooooooooooooooooo..',
  ],
  smith: [
    '.....ooooooooooooo......',
    '...oocccccccccccccoo....',
    '..occcggggggggggccccco..',
    '..occcgoooooooogccccco..',
    '..occcccccccccccccccco..',
    '..oooooooooooooooooooo..',
  ],
  chronomancer: [
    '......oooooooooooo......',
    '....ooccccccccccccoo....',
    '..ooccccgggggggcccccoo..',
    '..occcccgoooooogccccco..',
    '..occcccggggggggccccco..',
    '..oooooooooooooooooooo..',
  ],
  scribe: [
    '......oooooooooooo......',
    '....ooccccccccccccoo....',
    '..oocccccccccccccccoo...',
    '..occcccccgggcccccccco..',
    '..occcccccccccccccccco..',
    '..oooooooooooooooooooo..',
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
  automaton_small: '#b0763f', interviewer: '#2a2a38',
};

/* Companions reuse a mentor's likeness — they are the same order of being, and
 * the engine only ever needs a face beside a line of dialogue. */
export const PORTRAIT_ALIAS = {
  spirit: 'oracle', messenger: 'ranger', familiar: 'druid',
};

export const PORTRAIT_KEYS = [
  ...Object.keys(PORTRAIT_CROWN), ...Object.keys(PORTRAIT_FULL),
];
export const PORTRAIT_SIZE = 24;

function portraitPalette(tint) {
  const c = ramp(tint || '#4a5a8a');
  const skin = ramp('#e8b88a');
  const hair = ramp(mix(tint || '#4a5a8a', '#2a2038', 0.55));
  const gold = ramp('#d8b04a');
  return {
    o: '#100d1a', O: c.shadow2,
    s: skin.base, S: skin.shadow1, w: '#f2f2fa', e: '#1d1628',
    h: hair.base, H: hair.light1,
    c: c.base, C: c.light1, v: c.shadow1,
    g: gold.base, a: c.light2, A: c.light2,
    B: c.shadow1, L: c.base, d: c.shadow2, D: c.shadow2, k: '#0d0a14',
  };
}

const portraitCache = new Map();

export function portrait(kind) {
  const key = PORTRAIT_ALIAS[kind] || kind || 'scholar';
  if (portraitCache.has(key)) return portraitCache.get(key);
  const tint = PORTRAIT_TINT[key] || PORTRAIT_TINT.scholar;
  const pal = portraitPalette(tint);
  let canvas;
  if (PORTRAIT_FULL[key]) {
    canvas = gridSprite(PORTRAIT_FULL[key], pal, PORTRAIT_SIZE, PORTRAIT_SIZE);
  } else {
    const crown = PORTRAIT_CROWN[key] || PORTRAIT_CROWN.scholar;
    const garb = PORTRAIT_GARB[key] || PORTRAIT_GARB.scholar;
    canvas = composeSprite(PORTRAIT_SIZE, PORTRAIT_SIZE, [
      { grid: PORTRAIT_FACE },
      { grid: garb, oy: 18 },
      { grid: crown, oy: 1 },
    ], pal);
  }
  portraitCache.set(key, canvas);
  return canvas;
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
