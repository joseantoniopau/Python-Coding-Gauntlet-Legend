/* Original 16-bit pixel art, generated at runtime.
 *
 * Nothing here is traced, sampled or derived from any existing game. Sprites are
 * authored as small character grids with a per-sprite palette, then rasterised
 * into offscreen canvases and drawn with nearest-neighbour scaling so they stay
 * crisp on Retina displays.
 */
export const PALETTES = {
  dawn:     { sky: '#3a3968', far: '#6a5f96', mid: '#8a7aa8', ground: '#9fb562', ground2: '#8aa053', accent: '#ffd98a', foliage: '#5f8a4a', dark: '#1a1830' },
  spring:   { sky: '#4a72ad', far: '#5f9480', mid: '#75a865', ground: '#8abd5f', ground2: '#78a852', accent: '#ffe98a', foliage: '#4f9440', dark: '#1c2a1c' },
  amber:    { sky: '#6e5a46', far: '#a67f52', mid: '#c2935a', ground: '#d4a768', ground2: '#bc8f58', accent: '#ffbb52', foliage: '#7a8a3f', dark: '#2a1e14' },
  verdant:  { sky: '#2a5240', far: '#3c6d4c', mid: '#4a8a5e', ground: '#57a46b', ground2: '#4a8f5c', accent: '#a8e890', foliage: '#357f47', dark: '#12200f' },
  stone:    { sky: '#31343f', far: '#4e525f', mid: '#686d80', ground: '#7a8093', ground2: '#666b7d', accent: '#b6c0d8', foliage: '#4a6a52', dark: '#141519' },
  moss:     { sky: '#3a5044', far: '#4f6a4e', mid: '#62805c', ground: '#719363', ground2: '#5f7d52', accent: '#c0e8a2', foliage: '#4f7a45', dark: '#161f18' },
  slate:    { sky: '#3a4250', far: '#525c6e', mid: '#6a7488', ground: '#7c869c', ground2: '#6a7488', accent: '#cdd6ea', foliage: '#55705e', dark: '#1c2028' },
  ember:    { sky: '#2a1418', far: '#4a2020', mid: '#6a2f24', ground: '#7c3d28', ground2: '#68321f', accent: '#ff9d4a', foliage: '#6a4a2a', dark: '#170a0c' },
  royal:    { sky: '#251e40', far: '#3a2f60', mid: '#4e4080', ground: '#5c4d95', ground2: '#4a3e7c', accent: '#c8a8ff', foliage: '#4a6a58', dark: '#120e22' },
  dusk:     { sky: '#1a1a2e', far: '#2a2a44', mid: '#3a3a5c', ground: '#44445f', ground2: '#38384f', accent: '#a89aff', foliage: '#3a5a45', dark: '#0e0e18' },
  ash:      { sky: '#33323a', far: '#484650', mid: '#5c5a66', ground: '#6a6874', ground2: '#585663', accent: '#b8b4c4', foliage: '#55604f', dark: '#1a1a1f' },
  gold:     { sky: '#3a3018', far: '#5c4a22', mid: '#7c6430', ground: '#96793a', ground2: '#7f6631', accent: '#ffd97a', foliage: '#7a7a3a', dark: '#1e1809' },
  iron:     { sky: '#20222a', far: '#32353f', mid: '#454955', ground: '#525665', ground2: '#434754', accent: '#8fa8c8', foliage: '#40604a', dark: '#111216' },
  azure:    { sky: '#16263e', far: '#223a5c', mid: '#2f5080', ground: '#3a629c', ground2: '#305285', accent: '#7ec8ff', foliage: '#3a6a5a', dark: '#0b1420' },
  /* `ground2` carried an eight-digit hex, '#b8955180', for as long as this
   * table has existed. Two things went wrong with it and both were invisible
   * in the source: canvas read the trailing '80' as 50% alpha and painted the
   * Arena's ground half-transparent, so the layer behind it bled through and
   * broke the one-grain rule for that whole region; and shade() parses with
   * parseInt(hex.slice(1), 16), which on eight digits overflows the top byte
   * out of range and returns '#955180' — so every speckle and tuft on Arena
   * ground was drawn purple instead of amber. Six digits, opaque. */
  sun:      { sky: '#4a3a22', far: '#7c6234', mid: '#a88a48', ground: '#c8a55c', ground2: '#b89551', accent: '#ffe08a', foliage: '#7f8a3a', dark: '#241a0e' },
  void:     { sky: '#0c0a14', far: '#191426', mid: '#261e38', ground: '#2e2444', ground2: '#241c36', accent: '#d84a7a', foliage: '#2a3a35', dark: '#050408' },
};

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

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function make(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

/* Draw a character grid. '.' is transparent; every other glyph indexes `pal`. */
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

export function gridSprite(grid, pal) {
  const w = Math.max(...grid.map(r => r.length));
  const h = grid.length;
  const { canvas, ctx } = make(w, h);
  drawGrid(ctx, grid, pal);
  return canvas;
}

/* ---------- terrain tiles ---------- */
const TILE = 16;

/* Every tile colour in this module goes through here, so this is the one place
 * a malformed palette entry can quietly poison a whole region's art — which is
 * exactly what '#b8955180' did above. Normalise the shapes a hex can arrive in
 * instead of trusting six digits; a six-digit input is byte-identical to what
 * this returned before. */
function shade(hex, amount) {
  if (typeof hex !== 'string') return '#000000';
  let h = hex.charCodeAt(0) === 35 ? hex.slice(1) : hex;
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  else if (h.length > 6) h = h.slice(0, 6);          // drop alpha; we do not use it
  const n = parseInt(h, 16);
  if (!Number.isFinite(n)) return '#000000';
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  r = Math.max(0, Math.min(255, r + amount));
  g = Math.max(0, Math.min(255, g + amount));
  b = Math.max(0, Math.min(255, b + amount));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

/* Blend two hexes. Used where a tint has to stay on the pixel grid's own colour
 * set rather than being applied as a translucent overlay — an alpha pass over a
 * sprite produces colours nobody authored and is the fastest way to break a
 * fifteen-colour budget. */
function mixHex(a, b, t) {
  const pa = parseInt(shade(a, 0).slice(1), 16), pb = parseInt(shade(b, 0).slice(1), 16);
  const k = Math.max(0, Math.min(1, t));
  const r = Math.round(((pa >> 16) & 255) + (((pb >> 16) & 255) - ((pa >> 16) & 255)) * k);
  const g = Math.round(((pa >> 8) & 255) + (((pb >> 8) & 255) - ((pa >> 8) & 255)) * k);
  const c = Math.round((pa & 255) + ((pb & 255) - (pa & 255)) * k);
  return `#${((r << 16) | (g << 8) | c).toString(16).padStart(6, '0')}`;
}

function speckle(ctx, base, seed, density, amount) {
  const rand = rng(seed);
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      if (rand() < density) {
        ctx.fillStyle = shade(base, rand() < 0.5 ? amount : -amount);
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }
}

export function groundTile(pal, seed, variant = 0) {
  const { canvas, ctx } = make(TILE, TILE);
  const base = variant % 2 ? pal.ground2 : pal.ground;
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, TILE, TILE);
  speckle(ctx, base, seed, 0.2, 18);
  const rand = rng(seed + 77);
  // sparse tufts so a field never reads as flat colour
  for (let i = 0; i < 3; i++) {
    const x = Math.floor(rand() * 14) + 1, y = Math.floor(rand() * 13) + 2;
    ctx.fillStyle = shade(base, 22);
    ctx.fillRect(x, y, 1, 2);
    ctx.fillRect(x - 1, y + 1, 1, 1);
    ctx.fillRect(x + 1, y + 1, 1, 1);
  }
  return canvas;
}

export function waterTile(pal, seed, frame = 0) {
  const { canvas, ctx } = make(TILE, TILE);
  const deep = shade(pal.sky, -18);
  ctx.fillStyle = deep;
  ctx.fillRect(0, 0, TILE, TILE);
  const rand = rng(seed);
  for (let y = 0; y < TILE; y++) {
    const wave = Math.sin((y * 0.9) + frame * 0.9) * 2;
    for (let x = 0; x < TILE; x++) {
      const v = Math.sin((x + wave) * 0.55 + y * 0.4 + frame) * 0.5 + 0.5;
      if (v > 0.72) { ctx.fillStyle = shade(deep, 34); ctx.fillRect(x, y, 1, 1); }
      else if (v > 0.55) { ctx.fillStyle = shade(deep, 16); ctx.fillRect(x, y, 1, 1); }
      else if (rand() < 0.04) { ctx.fillStyle = shade(deep, -10); ctx.fillRect(x, y, 1, 1); }
    }
  }
  return canvas;
}

export function lavaTile(seed, frame = 0) {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = '#6a1c10';
  ctx.fillRect(0, 0, TILE, TILE);
  /* `seed` was accepted and never read, so every lava tile in the game was the
   * same two sine waves and a field of them tiled into a visible plaid. It is a
   * per-tile phase offset now: hashed from the seed, so still deterministic. */
  const px = ((seed | 0) % 97) * 0.0647;
  const py = (((seed | 0) >> 5) % 89) * 0.0706;
  for (let y = 0; y < TILE; y++) {
    for (let x = 0; x < TILE; x++) {
      const v = Math.sin(x * 0.7 + px + frame * 1.3) * Math.cos(y * 0.6 + py - frame) * 0.5 + 0.5;
      if (v > 0.78) { ctx.fillStyle = '#ffcc4a'; ctx.fillRect(x, y, 1, 1); }
      else if (v > 0.62) { ctx.fillStyle = '#ff8a2a'; ctx.fillRect(x, y, 1, 1); }
      else if (v > 0.45) { ctx.fillStyle = '#d2451a'; ctx.fillRect(x, y, 1, 1); }
    }
  }
  return canvas;
}

export function stoneTile(pal, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = pal.mid;
  ctx.fillRect(0, 0, TILE, TILE);
  speckle(ctx, pal.mid, seed, 0.2, 14);
  ctx.fillStyle = shade(pal.mid, -26);
  ctx.fillRect(0, 7, TILE, 1);
  ctx.fillRect(0, 15, TILE, 1);
  const rand = rng(seed);
  const a = Math.floor(rand() * 12) + 2, b = Math.floor(rand() * 12) + 2;
  ctx.fillRect(a, 0, 1, 8);
  ctx.fillRect(b, 8, 1, 8);
  ctx.fillStyle = shade(pal.mid, 20);
  ctx.fillRect(0, 8, TILE, 1);
  ctx.fillRect(a + 1, 1, 1, 6);
  return canvas;
}

export function pathTile(pal, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const base = shade(pal.accent, -58);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, TILE, TILE);
  speckle(ctx, base, seed, 0.24, 16);
  return canvas;
}

export function treeTile(pal, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  const rand = rng(seed);
  ctx.fillStyle = pal.ground2;
  ctx.fillRect(0, 0, TILE, TILE);
  speckle(ctx, pal.ground2, seed, 0.12, 10);
  ctx.fillStyle = '#4a3320';
  ctx.fillRect(7, 10, 2, 6);
  const canopy = pal.foliage || shade(pal.mid, 10);
  for (let i = 0; i < 34; i++) {
    const cx = 8 + Math.round((rand() - 0.5) * 11);
    const cy = 6 + Math.round((rand() - 0.5) * 9);
    if (cy > 12) continue;
    ctx.fillStyle = rand() < 0.35 ? shade(canopy, 22) : canopy;
    ctx.fillRect(cx, cy, 2, 2);
  }
  ctx.fillStyle = shade(canopy, -30);
  ctx.fillRect(4, 10, 8, 2);
  return canvas;
}

export function cliffTile(pal, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = shade(pal.far, -10);
  ctx.fillRect(0, 0, TILE, TILE);
  const rand = rng(seed);
  for (let i = 0; i < 5; i++) {
    const x = Math.floor(rand() * 12), y = Math.floor(rand() * 12);
    ctx.fillStyle = shade(pal.far, rand() < 0.5 ? 24 : -24);
    ctx.fillRect(x, y, 3 + Math.floor(rand() * 3), 2 + Math.floor(rand() * 2));
  }
  ctx.fillStyle = shade(pal.far, 30);
  ctx.fillRect(0, 0, TILE, 1);
  ctx.fillStyle = shade(pal.far, -40);
  ctx.fillRect(0, 14, TILE, 2);
  return canvas;
}

export function buildingTile(pal, seed, tier = 2) {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = pal.ground2;
  ctx.fillRect(0, 0, TILE, TILE);
  const wall = tier >= 2 ? '#c8b492' : '#7a6f60';
  const roof = tier >= 2 ? pal.accent : shade(pal.accent, -50);
  ctx.fillStyle = wall;
  ctx.fillRect(2, 6, 12, 10);
  ctx.fillStyle = shade(wall, -34);
  ctx.fillRect(2, 15, 12, 1);
  ctx.fillStyle = roof;
  for (let i = 0; i < 6; i++) ctx.fillRect(1 + i, 6 - i, 14 - i * 2, 1);
  if (tier >= 1) {
    ctx.fillStyle = tier >= 2 ? '#ffe8a0' : '#3a3020';
    ctx.fillRect(4, 9, 3, 3);
    ctx.fillRect(9, 9, 3, 3);
  }
  ctx.fillStyle = '#4a3320';
  ctx.fillRect(6, 12, 4, 4);
  if (tier === 0) { // ruined
    ctx.clearRect(10, 6, 4, 5);
    ctx.fillStyle = shade(wall, -40);
    ctx.fillRect(9, 10, 2, 2);
  }
  return canvas;
}

export function shrineTile(pal, seed) {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = pal.ground;
  ctx.fillRect(0, 0, TILE, TILE);
  ctx.fillStyle = shade(pal.far, 18);
  ctx.fillRect(4, 4, 8, 11);
  ctx.fillStyle = shade(pal.far, 40);
  ctx.fillRect(4, 4, 8, 1);
  ctx.fillStyle = pal.accent;
  ctx.fillRect(7, 7, 2, 2);
  ctx.fillStyle = shade(pal.accent, 40);
  ctx.fillRect(7, 6, 2, 1);
  ctx.fillRect(6, 7, 1, 2);
  ctx.fillRect(9, 7, 1, 2);
  ctx.fillStyle = shade(pal.far, -30);
  ctx.fillRect(3, 15, 10, 1);
  return canvas;
}

export function chestTile(pal) {
  const { canvas, ctx } = make(TILE, TILE);
  ctx.fillStyle = pal.ground;
  ctx.fillRect(0, 0, TILE, TILE);
  ctx.fillStyle = '#6a4520';
  ctx.fillRect(3, 7, 10, 7);
  ctx.fillStyle = '#8a5c2a';
  ctx.fillRect(3, 5, 10, 3);
  ctx.fillStyle = '#e8c37d';
  ctx.fillRect(3, 8, 10, 1);
  ctx.fillRect(7, 8, 2, 3);
  ctx.fillStyle = '#3a2410';
  ctx.fillRect(3, 13, 10, 1);
  return canvas;
}

/* ---------- hero ---------- */
const HERO_PAL = {
  o: '#141020', s: '#e8b88a', h: '#3a2a4a', c: '#3f6fa8', C: '#5a8fd0',
  m: '#8fa8c8', b: '#2a2438', g: '#c8a33d', w: '#e8e8f0',
};

/* 12x16, drawn once per facing. Legs are swapped programmatically per frame. */
const HERO = {
  down: [
    '....oooo....',
    '...ohhhho...',
    '..ohhhhhho..',
    '..ohsssho...',
    '..oss.s.so..',
    '..osssssso..',
    '...osssso...',
    '..occcccco..',
    '.ocCcccCco..',
    '.ocCcccCco..',
    '.osccccccso.',
    '..occcccco..',
    '..obb.bbo...',
    '..obb.bbo...',
    '..ooo.ooo...',
    '............',
  ],
  up: [
    '....oooo....',
    '...ohhhho...',
    '..ohhhhhho..',
    '..ohhhhhho..',
    '..ohhhhhho..',
    '..ohhhhhho..',
    '...ohhhho...',
    '..occcccco..',
    '.ocCcccCco..',
    '.ocCcccCco..',
    '.occccccco..',
    '..occcccco..',
    '..obb.bbo...',
    '..obb.bbo...',
    '..ooo.ooo...',
    '............',
  ],
  side: [
    '...oooo.....',
    '..ohhhho....',
    '.ohhhhhho...',
    '.ohsssho....',
    '.oss.so.....',
    '.ossssso....',
    '..osssso....',
    '..occcco.g..',
    '.ocCccco.g..',
    '.ocCccco.g..',
    '.osccccso...',
    '..occcco....',
    '..obbbo.....',
    '..obbo......',
    '..ooo.......',
    '............',
  ],
};

function legSwap(grid, phase) {
  const out = grid.map(r => r.split(''));
  const legRows = [12, 13, 14];
  for (const y of legRows) {
    if (!out[y]) continue;
    if (phase === 1) { out[y].unshift('.'); out[y].pop(); }
    else if (phase === 2) { out[y].push('.'); out[y].shift(); }
  }
  return out.map(r => r.join(''));
}

export function heroSprites(pal) {
  /* The tunic used to be picked with `pal.accent ? HERO_PAL.c : HERO_PAL.c`,
   * which is the same colour on both arms of the branch — the parameter was read
   * and then thrown away. It tints properly now: an accent shifts the tunic and
   * its lit face together, so a palette actually reaches the sprite. */
  const accent = pal && typeof pal.accent === 'string' ? pal.accent : null;
  const p = accent
    ? { ...HERO_PAL, c: mixHex(HERO_PAL.c, accent, 0.3), C: mixHex(HERO_PAL.C, accent, 0.3) }
    : { ...HERO_PAL };
  const out = {};
  for (const facing of ['down', 'up', 'side']) {
    out[facing] = [0, 1, 0, 2].map(phase =>
      gridSprite(legSwap(HERO[facing], phase), p));
  }
  return out;
}

/* ---------- enemies ---------- */
/* Eight archetype silhouettes, recoloured per algorithm family. Sixteen pixels
 * square, two animation frames produced by a vertical bob plus a shifted
 * highlight so they never read as static. */
const ENEMY_SHAPES = {
  slime: [
    '................',
    '................',
    '.....oooooo.....',
    '...ooBBBBBBoo...',
    '..oBBBBBBBBBBo..',
    '.oBBwwBBBBwwBBo.',
    '.oBBwwBBBBwwBBo.',
    '.oBBBBBBBBBBBBo.',
    '.oBBBBddBBBBBBo.',
    '.oBBBBBBBBBBBBo.',
    '.oBBBBBBBBBBBBo.',
    '..oBBBBBBBBBBo..',
    '...ooBBBBBBoo...',
    '.....oooooo.....',
    '................',
    '................',
  ],
  wisp: [
    '................',
    '.......oo.......',
    '.....ooWWoo.....',
    '....oWWBBWWo....',
    '...oWBBBBBBWo...',
    '...oBBwwwwBBo...',
    '..oBBwwddwwBBo..',
    '..oBBwwwwwwBBo..',
    '...oBBBBBBBBo...',
    '...oWBBBBBBWo...',
    '....oWWBBWWo....',
    '.....ooWWoo.....',
    '.......oo.......',
    '................',
    '................',
    '................',
  ],
  golem: [
    '................',
    '..oooo....oooo..',
    '..oBBo....oBBo..',
    '..oBBooooooBBo..',
    '..oBBBBBBBBBBo..',
    '.oBBwwBBBBwwBBo.',
    '.oBBwwBBBBwwBBo.',
    '.oBBBBBddBBBBBo.',
    '.oBBBBBBBBBBBBo.',
    '.oBBdBBBBBBdBBo.',
    '.oBBBBBBBBBBBBo.',
    '..oBBBBBBBBBBo..',
    '..oBBo....oBBo..',
    '..oBBo....oBBo..',
    '..oooo....oooo..',
    '................',
  ],
  wraith: [
    '................',
    '.....oooooo.....',
    '...ooBBBBBBoo...',
    '..oBBBBBBBBBBo..',
    '..oBwwBBBBwwBo..',
    '..oBwdBBBBdwBo..',
    '..oBBBBBBBBBBo..',
    '..oBBBBddBBBBo..',
    '...oBBBBBBBBo...',
    '...oBWBBBBWBo...',
    '..oBWBBWWBBWBo..',
    '..oBBBWBBWBBBo..',
    '...oBBBBBBBBo...',
    '....oBBoooBBo...',
    '.....oo...oo....',
    '................',
  ],
  hydra: [
    '................',
    '..oo........oo..',
    '.oBBo......oBBo.',
    '.oBwo.oooo.oBwo.',
    '.oBBooBBBBooBBo.',
    '..oBBBBwwBBBBo..',
    '...oBBBwwBBBo...',
    '....oBBBBBBo....',
    '...oBBBBBBBBo...',
    '..oBBBddddBBBo..',
    '..oBBBBBBBBBBo..',
    '..oBBBBBBBBBBo..',
    '...oBBBBBBBBo...',
    '....oooooooo....',
    '................',
    '................',
  ],
  dragon: [
    '................',
    '.o............o.',
    '.oo..oooooo..oo.',
    '.oBo.oBBBBo.oBo.',
    '.oBBooBwwBooBBo.',
    '..oBBBBwwBBBBo..',
    '..oBBBBddBBBBo..',
    '...oBBBBBBBBo...',
    '..oBBBWWWWBBBo..',
    '..oBBWBBBBWBBo..',
    '..oBBBBBBBBBBo..',
    '...oBBBBBBBBo...',
    '....oBBooBBo....',
    '.....oo..oo.....',
    '................',
    '................',
  ],
  construct: [
    '................',
    '...oooooooooo...',
    '...oBBBBBBBBo...',
    '...oBwwoowwBo...',
    '...oBwdoodwBo...',
    '...oBBBooBBBo...',
    '...oBBBBBBBBo...',
    '..ooBBBBBBBBoo..',
    '..oBBBddddBBBo..',
    '..oBBBBBBBBBBo..',
    '..oBBoooooo BBo.',
    '...oBBBBBBBBo...',
    '...oBBo..oBBo...',
    '...oooo..oooo...',
    '................',
    '................',
  ],
  mimic: [
    '................',
    '................',
    '..oooooooooooo..',
    '..oBBBBBBBBBBo..',
    '..odBBBBBBBBdo..',
    '..oBBBBBBBBBBo..',
    '..oooooooooooo..',
    '..oBwBwBwBwBwo..',
    '..oBBBBBBBBBBo..',
    '..oBBddBBddBBo..',
    '..oBBBBBBBBBBo..',
    '..oBBBBBBBBBBo..',
    '..oooooooooooo..',
    '................',
    '................',
    '................',
  ],
};

const SHAPE_FOR = {
  vaultling: 'construct', wisp: 'wisp', marshling: 'slime', twinblade: 'wraith',
  cartgoblin: 'golem', linewraith: 'wraith', lightwave: 'wisp',
  deepcrawler: 'hydra', branchling: 'dragon', mirrorspawn: 'wisp',
  halfling: 'construct', gridling: 'golem', pilekeeper: 'golem',
  ledgerling: 'construct', orderling: 'construct', clockwork: 'construct',
  echoling: 'wisp', slime: 'slime', indexling: 'slime', construct: 'construct',
  bugling: 'hydra', wyrmling: 'dragon', mimic: 'mimic', riddler: 'wraith',
  hoarder: 'golem', overlapper: 'slime', runeling: 'golem',
  titan: 'golem', hydra: 'hydra', behemoth: 'golem', dragon: 'dragon',
  ent: 'dragon', necromancer: 'wraith', automaton: 'construct', lich: 'wraith',
  demon: 'hydra', interviewer: 'construct', wyrm: 'dragon',
};

const FAMILY_COLOUR = {
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

export function enemySprite(spriteKey, pattern, frame = 0, override) {
  const shape = ENEMY_SHAPES[SHAPE_FOR[spriteKey] || 'slime'];
  const base = override || FAMILY_COLOUR[pattern] || '#7a8fbf';
  const pal = {
    o: '#0d0b14',
    B: frame % 2 ? shade(base, 6) : base,
    W: shade(base, 34),
    w: '#f4f4ff',
    d: shade(base, -46),
  };
  const sprite = gridSprite(shape, pal);
  return sprite;
}

export function bossSprite(spriteKey, colour, frame = 0) {
  // Bosses are the same silhouettes rendered at double resolution with an outline
  // glow, so they read as a bigger, angrier version of the family they represent.
  const small = enemySprite(spriteKey, null, frame, colour);
  const { canvas, ctx } = make(48, 48);
  ctx.imageSmoothingEnabled = false;
  ctx.save();
  ctx.shadowColor = colour || '#ffffff';
  ctx.shadowBlur = 0;
  ctx.drawImage(small, 0, 0, 16, 16, 8, 8, 32, 32);
  ctx.restore();
  // horns / crown so a boss is instantly distinguishable from a trash enemy
  ctx.fillStyle = shade(colour || '#ffffff', 40);
  ctx.fillRect(12, 4, 3, 6);
  ctx.fillRect(33, 4, 3, 6);
  ctx.fillRect(15, 7, 3, 3);
  ctx.fillRect(30, 7, 3, 3);
  ctx.fillStyle = '#0d0b14';
  ctx.fillRect(12, 3, 3, 1);
  ctx.fillRect(33, 3, 3, 1);
  return canvas;
}

/* ---------- portraits ---------- */
const PORTRAIT_PAL = {
  o: '#0f0c18', s: '#e8b88a', S: '#c99a70', h: '#3a2a4a', H: '#5a4a6a',
  r: '#8a4a3a', b: '#2a3a5a', B: '#4a5a8a', g: '#c8a33d', w: '#f0f0f8',
  e: '#1a1a2a', G: '#7ec8a8', p: '#8f6ad6',
};

const PORTRAITS = {
  automaton_small: [
    '..oooooooo..', '.oBBBBBBBBo.', 'oBBwwBBwwBBo', 'oBBwwBBwwBBo',
    'oBBBBBBBBBBo', 'oBBBggggBBBo', 'oBBBBBBBBBBo', '.oBBBBBBBBo.',
    '..oooooooo..', '...oBBBBo...', '..oBBBBBBo..', '..oo....oo..',
  ],
  scholar: [
    '..oooooooo..', '.ohhhhhhhho.', 'ohhssssssho.', 'ohsswwsswwso',
    'ohsseesseeso', 'ohssssssssso', 'ohsssrrrssso', '.ohsssssso..',
    '..oBBBBBBo..', '.oBBgBBgBBo.', '.oBBBBBBBBo.', '..oo....oo..',
  ],
  mage: [
    '....oooo....', '..oopppppo..', '.oppppppppo.', 'oppsssssspo.',
    'opsswwsswwso', 'opsseesseeso', 'opssssssssso', '.opsssssspo.',
    '..oppppppo..', '.oppgpppgppo', '.opppppppppo', '..oo....oo..',
  ],
  ranger: [
    '..oooooooo..', '.oGGGGGGGGo.', 'oGGssssssGo.', 'oGsswwsswwso',
    'oGsseesseeso', 'oGssssssssso', 'oGsssrrrssso', '.oGssssssGo.',
    '..oGGGGGGo..', '.oGGgGGgGGo.', '.oGGGGGGGGo.', '..oo....oo..',
  ],
  armorer: [
    '..oooooooo..', '.oHHHHHHHHo.', 'oHHssssssHo.', 'oHsswwsswwso',
    'oHsseesseeso', 'oHssssssssso', 'oHsrrrrrssso', '.oHssssssHo.',
    '..oHHHHHHo..', '.oHHgHHgHHo.', '.oHHHHHHHHo.', '..oo....oo..',
  ],
  oracle: [
    '....oooo....', '..oowwwwoo..', '.owwwwwwwwo.', 'owwssssssswo',
    'owsswwsswwso', 'owsseesseeso', 'owssssssssso', '.owsssssswo.',
    '..owwwwwwo..', '.owwgwwgwwo.', '.owwwwwwwwo.', '..oo....oo..',
  ],
  interviewer: [
    '..oooooooo..', '.oeeeeeeeeo.', 'oeessssssseo', 'oesswwsswwso',
    'oesseesseeso', 'oessssssssso', 'oessssssssso', '.oessssssoo.',
    '..oeeeeeeo..', '.oeewwweeeo.', '.oeeeeeeeeo.', '..oo....oo..',
  ],
};

export function portrait(kind) {
  const grid = PORTRAITS[kind] || PORTRAITS.scholar;
  return gridSprite(grid, PORTRAIT_PAL);
}

/* ---------- equipment icons ---------- */
const ICONS = {
  sword:  ['....gg..', '...ggg..', '..ggg...', '.ggg....', 'ggg..w..', 'g..wwww.', '..w..w..', '.......' ],
  sabers: ['..g..g..', '.gg..gg.', 'gg....gg', 'g..ww..g', '..wwww..', '.w....w.', '........', '........'],
  staff:  ['...cc...', '..cccc..', '...cc...', '...ww...', '...ww...', '...ww...', '...ww...', '...ww...'],
  spear:  ['...g....', '..ggg...', '...g....', '...w....', '...w....', '...w....', '...w....', '...w....'],
  lance:  ['..g.....', '.gg.....', 'ggg.....', '.www....', '..www...', '...www..', '....ww..', '.....w..'],
  dagger: ['...g....', '..ggg...', '..ggg...', '...w....', '..www...', '...w....', '...w....', '........'],
  axe:    ['.gggg...', 'gg..gg..', 'gg..gg..', '.gggw...', '....w...', '....w...', '....w...', '....w...'],
  hammer: ['.gggg...', 'gggggg..', 'gggggg..', '..ww....', '..ww....', '..ww....', '..ww....', '..ww....'],
  bow:    ['..gg....', '.g..g...', 'g....g..', 'g....g..', 'g....g..', '.g..g...', '..gg....', '........'],
  relic:  ['..cccc..', '.cccccc.', 'ccwwwwcc', 'ccwggwcc', 'ccwggwcc', 'ccwwwwcc', '.cccccc.', '..cccc..'],
  helm:   ['..cccc..', '.cccccc.', 'cc.cc.cc', 'cccccccc', 'cc.cc.cc', '.cccccc.', '..c..c..', '........'],
  chest:  ['.cc..cc.', 'cccccccc', 'cccccccc', 'ccc..ccc', 'cccccccc', 'cccccccc', '.cccccc.', '..cccc..'],
  gauntlets: ['cc....cc', 'cccc.ccc', 'cccc.ccc', '.cc...cc', '.cc...cc', '........', '........', '........'],
  boots:  ['.cc..cc.', '.cc..cc.', '.cc..cc.', '.cc..cc.', 'cccc.ccc', 'cccc.ccc', '........', '........'],
  shield: ['.cccccc.', 'cccccccc', 'ccggggcc', 'ccggggcc', 'cccccccc', '.cccccc.', '..cccc..', '...cc...'],
  plate:  ['cccccccc', 'cgggggc.', 'cgwwwgc.', 'cgwggwgc', 'cgwwwgc.', 'cgggggc.', 'cccccccc', '.cccccc.'],
};

export function icon(kind, colour = '#e8c37d') {
  const grid = ICONS[kind] || ICONS.sword;
  return gridSprite(grid, { g: colour, w: '#c8ccd8', c: colour, o: '#0d0b14' });
}

/* ---------- particles ---------- */

/* Weather and ambient motes. Three screens run this every frame — the overworld,
 * the battle stage and the title — so it is the hottest loop in this module, and
 * both rules in the brief bite here: nothing in a draw path may call
 * Math.random() or Date.now(), and nothing may allocate per frame.
 *
 * Each particle carries its own 32-bit state and advances it with a small LCG
 * when it needs a number. That is deterministic from the list's seed, costs no
 * allocation, and survives a reload: the same region produces the same weather
 * twice, which is what makes a scene feel authored rather than sprayed.
 */

/** Advance one particle's own noise stream. Deterministic, allocation-free. */
function nextRand(p) {
  // A list built by hand rather than by makeParticles has no seed; give it one
  // derived from where it currently is, so it still never reaches for entropy.
  let s = p.seed;
  if (!Number.isFinite(s)) s = (Math.imul((p.x | 0) + 1, 2654435761) ^ ((p.y | 0) * 40503)) >>> 0;
  s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
  p.seed = s;
  return s / 4294967296;
}

export function makeParticles(kind, width, height, count = 40) {
  const base = hash(kind + width);
  const rand = rng(base);
  const list = [];
  for (let i = 0; i < count; i++) {
    list.push({
      x: rand() * width, y: rand() * height,
      vx: (rand() - 0.5) * 0.3, vy: 0.15 + rand() * 0.5,
      size: kind === 'snow' ? 2 : 1,
      life: rand(),
      drift: rand() * Math.PI * 2,
      // Its own stream, so respawning one particle cannot shift another's.
      seed: (base ^ Math.imul(i + 1, 2654435761)) >>> 0,
    });
  }
  return list;
}

/* `colour` is the near tone and `dim` the far one. Depth used to be expressed
 * purely as alpha, which meant a particle's real colour depended on whatever it
 * happened to be floating over — an unbounded set of blends, off every ramp in
 * the game. Two authored tones, picked per particle, keep the drift readable and
 * keep the emitted colour count finite. */
export const PARTICLE_STYLE = {
  ember:  { colour: '#ff9d4a', dim: '#a8502a', up: true },
  snow:   { colour: '#e8f0ff', dim: '#8c9ab8', up: false },
  rain:   { colour: '#8fb8e8', dim: '#4a6a96', up: false, streak: true },
  leaves: { colour: '#8fd07a', dim: '#4e7a4a', up: false },
  motes:  { colour: '#c8a8ff', dim: '#6f5aa8', up: true },
  ash:    { colour: '#b8b4c4', dim: '#6e6a7c', up: false },
};

export function stepParticles(list, style, width, height, dt) {
  for (const p of list) {
    p.drift += dt * 0.9;
    p.x += p.vx + Math.sin(p.drift) * 0.35;
    p.y += style.up ? -p.vy * (style.streak ? 3 : 1.4) : p.vy * (style.streak ? 4 : 1);
    /* Respawn used to read Math.random(), which put a live entropy source in a
     * draw path: the same region's weather differed run to run and nothing that
     * depended on it could be reproduced. Same behaviour, from the particle's
     * own deterministic stream. */
    if (p.y > height + 4) { p.y = -4; p.x = nextRand(p) * width; }
    if (p.y < -4) { p.y = height + 4; p.x = nextRand(p) * width; }
    if (p.x > width + 4) p.x = -4;
    if (p.x < -4) p.x = width + 4;
  }
}

export function drawParticles(ctx, list, style, alpha = 0.65) {
  ctx.save();
  /* Quantised to eighths. A free-floating alpha multiplies every particle colour
   * into a continuum of blends; eight steps keeps the result a small, repeatable
   * set that sits on the same grain as everything else. */
  ctx.globalAlpha = Math.max(0, Math.min(1, Math.round(alpha * 8) / 8));
  const near = style.colour;
  const far = style.dim || style.colour;
  /* Two passes so fillStyle is assigned twice per frame instead of once per
   * particle, and so the near tone paints over the far one. */
  for (let pass = 0; pass < 2; pass++) {
    ctx.fillStyle = pass === 0 ? far : near;
    for (const p of list) {
      if ((p.life < 0.5) !== (pass === 0)) continue;
      /* Math.floor, not `| 0`. Truncation rounds toward zero, so every particle
       * drifting through x in (-1, 0) snapped to column 0 instead of to -1: a
       * one-pixel stall at the seam, on the one grid the whole scene shares. */
      const x = Math.floor(p.x), y = Math.floor(p.y);
      if (style.streak) ctx.fillRect(x, y, 1, 4);
      else ctx.fillRect(x, y, p.size, p.size);
    }
  }
  ctx.restore();
}

/* ---------- tileset cache ---------- */

/* A tileset is thirteen canvases, so an unbounded map of them is an unbounded
 * amount of texture memory. Eleven regions times four tiers is the real working
 * set; the cap is well above it and evicts oldest-first, so a long session
 * cannot grow this without bound. */
const TILESET_CACHE_MAX = 64;
const cache = new Map();

export function tilesetCacheStats() {
  return { size: cache.size, cap: TILESET_CACHE_MAX };
}

export function tileset(regionId, palette, tier = 2) {
  const key = `${regionId}:${tier}`;
  if (cache.has(key)) return cache.get(key);
  const pal = PALETTES[palette] || PALETTES.spring;
  const seed = hash(regionId);
  const set = {
    ground: [0, 1, 2, 3].map(v => groundTile(pal, seed + v * 13, v)),
    path: pathTile(pal, seed + 91),
    stone: stoneTile(pal, seed + 41),
    tree: [0, 1, 2].map(v => treeTile(pal, seed + 57 + v * 211)),
    cliff: cliffTile(pal, seed + 63),
    building: [0, 1, 2, 3].map(t => buildingTile(pal, seed + 71, Math.min(t, tier))),
    shrine: shrineTile(pal, seed + 83),
    chest: chestTile(pal),
    water: [0, 1, 2, 3].map(f => waterTile(pal, seed + 29, f * 1.6)),
    lava: [0, 1, 2, 3].map(f => lavaTile(seed + 37, f * 1.6)),
    palette: pal,
  };
  if (cache.size >= TILESET_CACHE_MAX) cache.delete(cache.keys().next().value);
  cache.set(key, set);
  return set;
}

export const TILE_SIZE = TILE;
export { shade };
