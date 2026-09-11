/* Python Coding Gauntlet Legend — spell and attack graphics.
 *
 * The six hint spells are the core of the learning loop. A spell is what the
 * player spends rank on when they are stuck, so the cast has to *read* as the
 * thing it does: ORACLE names a family, so it opens an eye and points a beam;
 * REVEAL_PATH names a structure, so a lattice draws itself; PHOENIX hands over
 * the whole solution, so a firebird gets up off the floor. The animation is the
 * player teaching themselves what the spell is before they read a word of it.
 *
 * Nothing here renders hint *content*. Every glyph on screen is an abstract
 * rune from the micro-font below, never text from the corpus. That rule is the
 * same one fx.js holds: the stage shows that a spell was cast, the spells panel
 * shows what it said.
 *
 * Everything is drawn, nothing is sampled. All art is fillRects and arcs over a
 * procedural layout seeded from a key, so the same cast looks the same forever.
 *
 * Contract, per effect:
 *   e.start(state)   bind to a stage/caster/target, reset the clock
 *   e.step(dt)       advance; returns e.done
 *   e.draw(ctx)      paint in logical stage units (192x128, ground at 100)
 *   e.done           true once the effect has fully dissipated
 *   e.duration       seconds, already adjusted for reduced motion
 *   e.impactAt       0..1 — the beat the caller should sync a hit or sfx to
 *   e.element        'fire' | 'frost' | 'arcane' | 'lightning' | 'force'
 *   e.power          damage-scaled strength; 1 is a plain blow, ~1.5 a crit
 *
 * Advisory per frame, for a host that wants to move the camera and wash the
 * screen in step with the art. An effect that is drawn and never read still
 * looks right; it just does not shove the stage around.
 *
 *   e.shakeHint      logical units of screen shake to apply this frame
 *   e.flashHint      0..1 white flash the host owns
 *   e.lightHint      0..1 how lit the stage is; decays slower than the flash
 *   e.targetFlashHint 0..1 hard flash on the target sprite, two frames wide
 *
 * Geometry is mirrored from fx.js STAGE rather than imported. fx.js is the
 * module that will import this one, and a two-way import is a cycle waiting to
 * bite at module-eval time. Callers pass their own STAGE through opts.stage,
 * which is what keeps the two honest.
 */
import { rng, hash, shade, mix } from './sprites.js';

export const SPELLFX_VERSION = '1.1.0';

/* Logical stage units. Same numbers as fx.js STAGE; overridable per effect. */
export const STAGE_GEOM = Object.freeze({
  w: 192, h: 128, ground: 100, heroX: 46, enemyX: 136,
});

/* Mirrored from fx.js DAMAGE_KIND so ATTACK_ANIMATIONS can be keyed by it
 * without importing fx.js. The string values are the contract, not this object. */
export const DAMAGE_KIND = Object.freeze({
  HIT: 'hit', CRIT: 'crit', RESIST: 'resist', HEAL: 'heal', MISS: 'miss',
});

export const SPELL_IDS = Object.freeze([
  'ORACLE', 'REVEAL_PATH', 'VISION', 'PSEUDOSIGHT', 'CODE_FRAGMENT', 'PHOENIX',
]);

/* Colour identity per effect. Four roles each: `key` carries the spell, `hot`
 * is the specular core that sells the light, `deep` is the shadow the key sits
 * on, `ink` is the near-black outline every piece of art in this game wears. */
const INK = '#0b0a12';

export const SPELL_COLOURS = Object.freeze({
  ORACLE:        { key: '#ffe8a0', hot: '#fffbe8', deep: '#6b4e12', ink: INK },
  REVEAL_PATH:   { key: '#5ad8ff', hot: '#e6fbff', deep: '#123a52', ink: INK },
  VISION:        { key: '#c8b4ff', hot: '#f2ecff', deep: '#2a1f4a', ink: INK },
  PSEUDOSIGHT:   { key: '#a26bff', hot: '#e4d2ff', deep: '#241040', ink: INK },
  CODE_FRAGMENT: { key: '#78e86a', hot: '#dcffd0', deep: '#123f1a', ink: INK },
  PHOENIX:       { key: '#ff7a1a', hot: '#ffe8a0', deep: '#7a1c0c', ink: INK },
});

export const ATTACK_COLOURS = Object.freeze({
  hit:    { key: '#ffe8a0', hot: '#fffdf0', deep: '#3a2a10', ink: INK },
  crit:   { key: '#ffd97a', hot: '#fffbe8', deep: '#4a2a00', ink: INK },
  resist: { key: '#9b96b8', hot: '#d8d4e8', deep: '#14121f', ink: INK },
  heal:   { key: '#8fd07a', hot: '#e8ffd8', deep: '#132a10', ink: INK },
  miss:   { key: '#7ec8ff', hot: '#e0f2ff', deep: '#0b1a2a', ink: INK },
});

/* ---------------- elements ----------------
 * The brief that matters most here: fire, frost, arcane, lightning and force
 * have to be told apart *from their motion alone, with the colour turned off*.
 * Colour is the first thing a player stops seeing when three trials resolve in
 * a row, so identity cannot live there.
 *
 * So each element is a motion law, and the law is applied in three places: the
 * wind-up figure at the caster, the impact signature on the target, and the
 * velocity, gravity and lifetime every spark and chunk is emitted with.
 *
 *   fire       buoyant. Rises, licks, never settles. Gravity is negative.
 *   frost      brittle. Stabs out once, stops dead, then falls in pieces.
 *   arcane     orbital. Nothing travels straight; rings counter-rotate.
 *   lightning  instantaneous. Full speed on frame one, gone three frames later,
 *              re-seeded on a strobe clock so it snaps rather than slides.
 *   force      radial. One pressure front, dust that stays low, no rise at all.
 *
 * `holdScale` stretches or shortens that element's hold frame: frost and force
 * land heavier than lightning, which is over before it is seen.
 */
export const ELEMENTS = Object.freeze({
  fire: Object.freeze({
    id: 'fire', radial: false, dir: -Math.PI / 2, tangent: 0, spread: 1.5,
    speed: 30, speedVar: 52, gravity: -42, life: 0.52, lifeVar: 0.50,
    spin: 6.5, chunk: 0.22, holdScale: 1.00,
  }),
  frost: Object.freeze({
    id: 'frost', radial: true, dir: 0, tangent: 0, spread: 0.5,
    speed: 46, speedVar: 56, gravity: 230, life: 0.26, lifeVar: 0.20,
    spin: 0, chunk: 0.50, holdScale: 1.25,
  }),
  arcane: Object.freeze({
    id: 'arcane', radial: true, dir: 0, tangent: 1.35, spread: 0.5,
    speed: 20, speedVar: 28, gravity: 6, life: 0.70, lifeVar: 0.55,
    spin: 12, chunk: 0.12, holdScale: 0.95,
  }),
  lightning: Object.freeze({
    id: 'lightning', radial: true, dir: 0, tangent: 0, spread: 0.8,
    speed: 130, speedVar: 130, gravity: 420, life: 0.13, lifeVar: 0.10,
    spin: 0, chunk: 0.22, holdScale: 0.75,
  }),
  force: Object.freeze({
    id: 'force', radial: true, dir: 0, tangent: 0, spread: 0.3,
    speed: 58, speedVar: 50, gravity: 170, life: 0.38, lifeVar: 0.28,
    spin: 0, chunk: 0.42, holdScale: 1.15,
  }),
});

export const ELEMENT_IDS = Object.freeze(Object.keys(ELEMENTS));

/* Cold steel. Weapons, bezels and chrome bevels are not tinted by the spell —
 * keeping the metal neutral is what makes the coloured light look like light. */
const STEEL = '#cdd6e0';
const STEEL_DARK = '#5a6472';

/* ---------------- small helpers ---------------- */

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
const lerp = (a, b, k) => a + (b - a) * k;
const easeOut = (k) => 1 - (1 - k) * (1 - k);
const easeIn = (k) => k * k;
const easeInOut = (k) => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
/* Lands with weight rather than gliding to a stop. Same curve fx.js uses. */
const overshoot = (k) => { const t = k - 1; return t * t * (2.70158 * t + 1.70158) + 1; };
/* 0 at both ends, 1 in the middle: the envelope every flash and flare rides. */
const arc = (k) => Math.sin(Math.PI * clamp(k, 0, 1));
/* Snaps to a whole logical pixel. Half-pixel art is soft art. */
const px = Math.round;
/* The reference blow. With no damage numbers to go on an effect is played at
 * the strength of one ordinary hit, which is what `power === 1` means. */
const REFERENCE_BLOW = 0.18;

/* Deterministic pseudo-noise with no closure allocated. rng() hands back a
 * function, which is fine in build() and wrong in a draw path that runs sixty
 * times a second; every jag and flicker added below uses this instead. */
function noise(a, b) {
  let h = (Math.imul(a | 0, 374761393) + Math.imul(b | 0, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177) | 0;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

/* Two derived tones per effect colour, so a plume or a chunk of debris has a
 * step between the key and the shadow instead of banding straight to black.
 * Six colours per effect all in — ink, deep, dim, mid, key, hot — plus the two
 * neutral steels, which leaves the fifteen-colour budget with room to spare.
 * Memoised because mix() builds strings and this must never run in a frame. */
const TONE_MAX = 64;
const toneCache = new Map();

function tonesFor(col) {
  const id = `${col.key}|${col.deep}`;
  let t = toneCache.get(id);
  if (t === undefined) {
    if (toneCache.size >= TONE_MAX) toneCache.clear();
    t = Object.freeze({
      mid: mix(col.key, col.deep, 0.45),
      dim: mix(col.deep, col.ink, 0.35),
    });
    toneCache.set(id, t);
  }
  return t;
}

/* Alpha-blended colour strings, quantised and cached per hex.
 *
 * Building `rgba(...)` per draw call allocates a string every frame, and at
 * sixty frames with a few hundred draws that is exactly the garbage this module
 * is not allowed to produce. Alpha is quantised to 1/64, which is finer than
 * anyone can see, and the resulting strings are memoised in a dense array per
 * colour so a cache hit allocates nothing at all. */
const ALPHA_STEPS = 64;
const NOTHING = 'rgba(0,0,0,0)';
const alphaCache = new Map();

function rgba(hex, a) {
  if (!(a > 0)) return NOTHING;
  let arr = alphaCache.get(hex);
  if (arr === undefined) { arr = new Array(ALPHA_STEPS + 1); alphaCache.set(hex, arr); }
  const i = a >= 1 ? ALPHA_STEPS : ((a * ALPHA_STEPS + 0.5) | 0);
  let s = arr[i];
  if (s === undefined) {
    const n = parseInt(String(hex).replace('#', '').slice(0, 6), 16) || 0;
    s = `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${(i / ALPHA_STEPS).toFixed(3)})`;
    arr[i] = s;
  }
  return s;
}

/* ---------------- canvas cache ----------------
 * Anything drawn from more than a handful of rects gets rasterised once and
 * blitted thereafter. The cache is keyed by content, so a warm cache means a
 * frame costs drawImage calls and nothing else.
 *
 * `stamp` falls back to painting straight into the target when there is no
 * document to make a canvas from. That keeps the module importable and testable
 * headless, and means a hostile embedding cannot break rendering outright. */
const CACHE_MAX = 512;
const canvasCache = new Map();

function makeCanvas(w, h) {
  if (typeof document === 'undefined' || !document.createElement) return null;
  try {
    const c = document.createElement('canvas');
    c.width = Math.max(1, w | 0);
    c.height = Math.max(1, h | 0);
    const x = c.getContext('2d');
    if (!x) return null;
    x.imageSmoothingEnabled = false;
    return { canvas: c, ctx: x };
  } catch (e) {
    return null;                       // exotic host, no raster: fall back below
  }
}

function cachedCanvas(key, w, h, paint) {
  if (canvasCache.has(key)) return canvasCache.get(key);
  /* A flat clear beats an LRU here: entries are cheap to rebuild and the working
   * set is one battle's worth of effects, so thrashing is not a real risk. */
  if (canvasCache.size >= CACHE_MAX) canvasCache.clear();
  const made = makeCanvas(w, h);
  if (made) { try { paint(made.ctx); } catch (e) { /* keep the blank tile */ } }
  const entry = made ? made.canvas : null;
  canvasCache.set(key, entry);
  return entry;
}

function stamp(ctx, key, w, h, paint, x, y, alpha = 1) {
  if (!(alpha > 0)) return;
  const c = cachedCanvas(key, w, h, paint);
  const prev = ctx.globalAlpha;
  ctx.globalAlpha = prev * clamp(alpha, 0, 1);
  if (c) ctx.drawImage(c, px(x), px(y));
  else {
    ctx.save();
    ctx.translate(px(x), px(y));
    paint(ctx);
    ctx.restore();
  }
  ctx.globalAlpha = prev;
}

export function clearCache() { canvasCache.clear(); alphaCache.clear(); toneCache.clear(); }

/* ---------------- the rune micro-font ----------------
 * Twenty-four 3x5 runes, authored by hand. They are deliberately not an
 * alphabet: a player must never be able to read a hint off the stage, and
 * abstract glyphs also let a row of "pseudocode" scroll past without claiming
 * to be Python. */
const GLYPH_ROWS = [
  ['111', '010', '010', '010', '111'], ['101', '101', '111', '101', '101'],
  ['110', '101', '110', '100', '100'], ['011', '100', '010', '001', '110'],
  ['111', '100', '110', '100', '111'], ['010', '111', '010', '111', '010'],
  ['101', '111', '010', '111', '101'], ['100', '100', '100', '100', '111'],
  ['111', '001', '111', '100', '111'], ['010', '101', '101', '101', '010'],
  ['110', '101', '110', '101', '110'], ['111', '010', '010', '010', '010'],
  ['101', '101', '101', '101', '111'], ['011', '010', '010', '010', '110'],
  ['111', '001', '010', '100', '111'], ['101', '010', '111', '010', '101'],
  ['110', '100', '111', '001', '011'], ['001', '011', '111', '011', '001'],
  ['100', '110', '111', '110', '100'], ['111', '101', '101', '101', '111'],
  ['010', '010', '111', '010', '010'], ['111', '000', '111', '000', '111'],
  ['101', '000', '010', '000', '101'], ['011', '101', '110', '101', '011'],
];
const GLYPH_N = GLYPH_ROWS.length;
const GLYPH_W = 3, GLYPH_H = 5, GLYPH_ADVANCE = 4;

function paintGlyph(ctx, index, colour, ox = 0, oy = 0) {
  const g = GLYPH_ROWS[((index % GLYPH_N) + GLYPH_N) % GLYPH_N];
  ctx.fillStyle = colour;
  for (let r = 0; r < GLYPH_H; r++) {
    const row = g[r];
    for (let c = 0; c < GLYPH_W; c++) {
      if (row.charCodeAt(c) === 49) ctx.fillRect(ox + c, oy + r, 1, 1);
    }
  }
}

/* A whole row of runes rasterised as one tile. PSEUDOSIGHT puts fourteen rows on
 * screen at once; cached this way that is fourteen blits a frame instead of six
 * hundred rects. Rows are seeded, so a given row is the same glyphs forever. */
function glyphStripKey(colour, seed, cells) { return `strip:${colour}:${seed}:${cells}`; }

function drawGlyphStrip(ctx, x, y, cells, seed, colour, alpha) {
  if (cells <= 0) return;
  const key = glyphStripKey(colour, seed, cells);
  stamp(ctx, key, cells * GLYPH_ADVANCE, GLYPH_H, (c) => {
    const r = rng((seed >>> 0) || 1);
    for (let i = 0; i < cells; i++) {
      paintGlyph(c, (r() * GLYPH_N) | 0, colour, i * GLYPH_ADVANCE, 0);
    }
  }, x, y, alpha);
}

/* ---------------- particles ----------------
 * One fixed pool per effect, allocated when the effect is constructed and never
 * grown. Emitting past the end recycles the oldest mote, which is correct: the
 * newest spark is always the one worth keeping. */
class Motes {
  constructor(capacity) {
    this.cap = Math.max(0, capacity | 0);
    this.x = new Float32Array(this.cap);
    this.y = new Float32Array(this.cap);
    this.vx = new Float32Array(this.cap);
    this.vy = new Float32Array(this.cap);
    this.g = new Float32Array(this.cap);
    this.t = new Float32Array(this.cap);
    this.life = new Float32Array(this.cap);
    this.size = new Float32Array(this.cap);
    this.spin = new Float32Array(this.cap);
    /* 0 is a spark, 1 is a chunk of debris. Same pool, same step, different
     * paint — an impact that throws only sparks reads as a sparkle, and an
     * impact that throws pieces of something reads as damage. */
    this.shape = new Uint8Array(this.cap);
    this.colour = new Array(this.cap).fill(INK);
    this.alive = new Uint8Array(this.cap);
    this.head = 0;
    this.quiet = false;                 // reduced motion mutes emission
    /* The stage, so a mote that has left it can stop costing anything. Measured
     * before this was here: VISION's debris was still being filled a hundred
     * and thirty units below a 128-unit stage, one clipped fillRect each. */
    this.bw = 1e6;
    this.bh = 1e6;
  }

  setBounds(w, h) {
    this.bw = w > 0 ? w : 1e6;
    this.bh = h > 0 ? h : 1e6;
    return this;
  }

  reset() { this.alive.fill(0); this.shape.fill(0); this.head = 0; }

  emit(x, y, vx, vy, g, life, size, colour, spin = 0) {
    if (this.quiet || this.cap === 0) return;
    const i = this.head;
    this.head = (this.head + 1) % this.cap;
    this.x[i] = x; this.y[i] = y; this.vx[i] = vx; this.vy[i] = vy;
    this.g[i] = g; this.t[i] = 0; this.life[i] = life; this.size[i] = size;
    this.colour[i] = colour; this.spin[i] = spin; this.alive[i] = 1;
    this.shape[i] = 0;
  }

  /* Debris. Heavier, slower, longer-lived, and painted as a solid piece. */
  emitChunk(x, y, vx, vy, g, life, size, colour, spin = 0) {
    if (this.quiet || this.cap === 0) return;
    const i = this.head;
    this.emit(x, y, vx, vy, g, life, size, colour, spin);
    this.shape[i] = 1;
  }

  step(dt) {
    const xlo = -28, xhi = this.bw + 28, ylo = -40, yhi = this.bh + 24;
    for (let i = 0; i < this.cap; i++) {
      if (!this.alive[i]) continue;
      this.t[i] += dt;
      if (this.t[i] >= this.life[i]) { this.alive[i] = 0; continue; }
      this.vy[i] += this.g[i] * dt;
      this.x[i] += this.vx[i] * dt;
      this.y[i] += this.vy[i] * dt;
      if (this.spin[i]) this.vx[i] += Math.sin(this.t[i] * this.spin[i]) * 24 * dt;
      /* Gone for good: retire it rather than carry it. This is not only a draw
       * saved, it hands the slot back to the pool, so a dense impact stops
       * starving its own sparks to feed debris that left the frame. */
      const x = this.x[i], y = this.y[i];
      if (y > yhi || x < xlo || x > xhi || (y < ylo && this.vy[i] <= 0)) this.alive[i] = 0;
    }
  }

  draw(ctx, fade = 1) {
    for (let i = 0; i < this.cap; i++) {
      if (!this.alive[i]) continue;
      const k = 1 - this.t[i] / this.life[i];
      const a = clamp(k * k * fade, 0, 1);
      if (!(a > 0)) continue;
      const x = px(this.x[i]), y = px(this.y[i]);
      if (x < -4 || y < -6 || x > this.bw + 4 || y > this.bh + 4) continue;
      if (this.shape[i]) {
        /* A chunk tumbles by flipping its long axis on a whole-frame clock
         * rather than by rotating: a rotated rect on this grid is a blurred
         * rect, and nothing in this game is allowed to blur. */
        const s = Math.max(2, px(this.size[i]));
        const turn = ((this.t[i] * (7 + this.spin[i])) | 0) & 1;
        const w = turn ? s : s + 1, h = turn ? s + 1 : s;
        ctx.fillStyle = rgba(INK, a * 0.85);
        ctx.fillRect(x - 1, y - 1, w + 2, h + 2);
        ctx.fillStyle = rgba(this.colour[i], a * 0.8);
        ctx.fillRect(x, y, w, h);
        ctx.fillStyle = rgba(this.colour[i], a);   // the one lit edge, up-left
        ctx.fillRect(x, y, w, 1);
        continue;
      }
      const s = Math.max(1, px(this.size[i] * (0.4 + k * 0.6)));
      ctx.fillStyle = rgba(this.colour[i], a);
      ctx.fillRect(x, y, s, s);
    }
  }

  get liveCount() {
    let n = 0;
    for (let i = 0; i < this.cap; i++) if (this.alive[i]) n++;
    return n;
  }
}

/* ---------------- shared painters ---------------- */

/* A hard-edged beam between two points: near-black shoulder, coloured body,
 * white-hot core. Three bands, no gradient — a gradient would read as airbrush
 * and this game is 16-bit. */
function beam(ctx, x0, y0, x1, y1, width, col, alpha) {
  const dx = x1 - x0, dy = y1 - y0;
  const len = Math.hypot(dx, dy);
  if (len < 0.5 || !(alpha > 0)) return;
  ctx.save();
  ctx.translate(x0, y0);
  ctx.rotate(Math.atan2(dy, dx));
  const w = Math.max(1, width);
  ctx.fillStyle = rgba(col.ink, alpha * 0.55);
  ctx.fillRect(0, px(-w / 2) - 1, px(len), px(w) + 2);
  ctx.fillStyle = rgba(col.key, alpha * 0.9);
  ctx.fillRect(0, px(-w / 2), px(len), px(w));
  const core = Math.max(1, px(w * 0.34));
  ctx.fillStyle = rgba(col.hot, alpha);
  ctx.fillRect(0, px(-core / 2), px(len), core);
  ctx.restore();
}

/* Expanding shock ring, drawn as two concentric strokes so it has a rim rather
 * than being a hairline. */
function shockRing(ctx, cx, cy, r, colour, alpha, thick = 1) {
  if (!(alpha > 0) || r < 0.5) return;
  ctx.lineWidth = thick;
  ctx.strokeStyle = rgba(colour, alpha);
  ctx.beginPath();
  ctx.arc(px(cx), px(cy), Math.max(0.5, r), 0, Math.PI * 2);
  ctx.stroke();
}

/* A ring of runes on a bezel: the frame ORACLE's eye opens inside, and the
 * chassis a CRIT sigil is stamped from. */
function runeRing(ctx, cx, cy, radius, count, spin, col, alpha) {
  if (!(alpha > 0)) return;
  ctx.lineWidth = 1;
  ctx.strokeStyle = rgba(col.deep, alpha * 0.8);
  ctx.beginPath();
  ctx.arc(px(cx), px(cy), radius, 0, Math.PI * 2);
  ctx.stroke();
  ctx.strokeStyle = rgba(col.key, alpha * 0.45);
  ctx.beginPath();
  ctx.arc(px(cx), px(cy), radius - 3, 0, Math.PI * 2);
  ctx.stroke();
  for (let i = 0; i < count; i++) {
    const a = spin + (Math.PI * 2 * i) / count;
    const gx = cx + Math.cos(a) * radius - GLYPH_W / 2;
    const gy = cy + Math.sin(a) * radius - GLYPH_H / 2;
    const lit = 0.5 + 0.5 * Math.sin(a * 3 + spin * 2);
    drawGlyphStrip(ctx, gx, gy, 1, 7717 + i * 131, col.key, alpha * (0.45 + lit * 0.55));
  }
}

/* Jagged cracks radiating from a point. Deterministic per seed so a crit on the
 * same trial shatters the same way twice. */
function cracks(ctx, cx, cy, seed, count, length, colour, alpha, grow) {
  if (!(alpha > 0)) return;
  const r = rng((seed >>> 0) || 1);
  ctx.lineWidth = 1;
  ctx.strokeStyle = rgba(colour, alpha);
  ctx.beginPath();
  for (let i = 0; i < count; i++) {
    const a0 = (Math.PI * 2 * i) / count + r() * 0.5;
    let x = cx, y = cy, a = a0;
    ctx.moveTo(px(x), px(y));
    const segs = 3;
    for (let s = 0; s < segs; s++) {
      a += (r() - 0.5) * 0.9;
      const seg = (length / segs) * grow * (0.6 + r() * 0.8);
      x += Math.cos(a) * seg;
      y += Math.sin(a) * seg;
      ctx.lineTo(px(x), px(y));
    }
  }
  ctx.stroke();
}

/* A chrome-bevelled plate: the chassis under code shards and sigils. Bright
 * top-left, dark bottom-right, hard ink outline. */
function bevelPlate(ctx, x, y, w, h, col, alpha, lit = 1) {
  if (!(alpha > 0) || w < 1 || h < 1) return;
  ctx.fillStyle = rgba(col.ink, alpha * 0.85);
  ctx.fillRect(px(x) - 1, px(y) - 1, px(w) + 2, px(h) + 2);
  ctx.fillStyle = rgba(col.deep, alpha);
  ctx.fillRect(px(x), px(y), px(w), px(h));
  ctx.fillStyle = rgba(STEEL, alpha * 0.55 * lit);
  ctx.fillRect(px(x), px(y), px(w), 1);
  ctx.fillStyle = rgba(STEEL_DARK, alpha * 0.7);
  ctx.fillRect(px(x), px(y + h) - 1, px(w), 1);
}

/* ---------------- additive light ----------------
 * The difference between a spell that lights the stage and a sprite pasted on
 * top of it is one property. Under 'lighter' the backdrop, the hero and the
 * enemy all get brighter where the light falls, because everything underneath
 * is already on the canvas by the time an effect draws (fx.js paints the
 * backdrop, the hero and the enemy, and only then the effects).
 *
 * It is still banded, not blurred. Three or four hard steps of a quantised
 * radius is light on this grid; a radial gradient is an airbrush, and an
 * airbrush belongs to a different decade than this game does.
 */
function lightDisc(ctx, cx, cy, radius, colour, alpha, bands = 3) {
  if (!(alpha > 0) || !(radius > 1)) return;
  for (let i = bands; i >= 1; i--) {
    const r = Math.max(1, px((radius * i) / bands));
    ctx.fillStyle = rgba(colour, alpha * (1 - (i - 1) / bands));
    ctx.beginPath();
    ctx.arc(px(cx), px(cy), r, 0, Math.PI * 2);
    ctx.fill();
  }
}

/* The one hot rim light in this game comes from a low source, so every impact
 * also puts a pool of it on the floor. This is the cheapest thing in the file
 * and it does more for "the light is real" than anything else in it. */
function groundPool(ctx, cx, groundY, rx, colour, alpha) {
  if (!(alpha > 0) || !(rx > 1)) return;
  for (let i = 2; i >= 1; i--) {
    const w = Math.max(1, px((rx * i) / 2));
    const h = Math.max(1, px((rx * i) / 6));
    ctx.fillStyle = rgba(colour, alpha * (1 - (i - 1) / 2));
    ctx.beginPath();
    ctx.ellipse(px(cx), px(groundY), w, h, 0, 0, Math.PI * 2);
    ctx.fill();
  }
}

/* A jagged polyline between two points, seeded so a given strobe tick always
 * draws the same bolt. Allocation-free: noise() rather than rng(). */
function boltPath(ctx, x0, y0, x1, y1, seed, jag, segs) {
  ctx.beginPath();
  ctx.moveTo(px(x0), px(y0));
  for (let i = 1; i <= segs; i++) {
    const q = i / segs;
    const taper = 1 - Math.abs(q - 0.5) * 1.4;
    const nx = lerp(x0, x1, q) + (noise(seed, i) - 0.5) * jag * taper;
    const ny = lerp(y0, y1, q) + (noise(seed, i + 97) - 0.5) * jag * taper * 0.6;
    ctx.lineTo(px(nx), px(ny));
  }
  ctx.stroke();
}

/* ---------------- element signatures ----------------
 * Act one and act three, in the element's own motion. Both painters are pure
 * functions of their arguments so that a replay is identical, and both take
 * `quiet` so that reduced motion really does hold still — `this.t` keeps
 * running in that mode even while `k` is pinned, so anything driven by time
 * has to be gated here rather than trusted.
 */

/* ACT ONE. Anticipation at the caster. This is the beat an effect without one
 * skips, and skipping it is exactly what makes a hit read as a flash. */
function windupSignature(ctx, el, cx, cy, p, t, col, tn, alpha, power, seed, quiet) {
  if (!(alpha > 0)) return;
  const R = (16 + 9 * power) * (1 - easeOut(p) * 0.68);
  ctx.lineWidth = 1;

  if (el.id === 'fire') {
    // Embers spiral UP into the hand on a golden angle, and a tongue licks off
    // it. Nothing in fire falls, and that is the whole tell.
    for (let i = 0; i < 7; i++) {
      const a = i * 2.39996 + (quiet ? 0 : t * 4.2);
      const rr = R * (1 - (i / 7) * 0.5);
      const ex = cx + Math.cos(a) * rr;
      const ey = cy + Math.sin(a) * rr * 0.55 - p * 11 - (i % 3);
      const s = 1 + (i & 1);
      ctx.fillStyle = rgba(i < 3 ? col.hot : i < 5 ? col.key : tn.mid,
        alpha * (0.45 + 0.55 * p));
      ctx.fillRect(px(ex), px(ey), s, s);
    }
    const h = 4 + 13 * p * power;
    for (let i = 0; i < 5; i++) {
      const q = i / 4;
      const w = Math.max(1, px((1 - q) * 5 * power));
      const wob = quiet ? 0 : Math.sin(t * 11 - q * 3) * (1 + 2 * q);
      ctx.fillStyle = rgba(q < 0.35 ? col.hot : q < 0.8 ? col.key : tn.mid,
        alpha * (1 - q * 0.5));
      ctx.fillRect(px(cx - w / 2 + wob), px(cy - q * h), w, 2);
    }
    return;
  }

  if (el.id === 'frost') {
    // Six spikes grow inward on fixed bearings and then hold dead still. No
    // rotation anywhere: frost is the element that stops.
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI * 2 * i) / 6 + 0.26;
      const dx = Math.cos(a), dy = Math.sin(a);
      for (let s = 0; s < 4; s++) {
        const q = s / 3;
        const rr = lerp(R, R * 0.3, easeOut(p) * q + q * 0.4);
        const w = Math.max(1, px((1 - q) * 3));
        ctx.fillStyle = rgba(q > 0.6 ? col.hot : col.key, alpha * (0.4 + 0.6 * q));
        ctx.fillRect(px(cx + dx * rr), px(cy + dy * rr), w, w);
      }
    }
    return;
  }

  if (el.id === 'arcane') {
    // Two rings close on the point, counter-rotating. Arcane is the only
    // element whose wind-up keeps turning after it has arrived.
    const spin = quiet ? 0 : t * 4;
    runeRing(ctx, cx, cy, Math.max(4, R), 6, spin, col, alpha * 0.85);
    runeRing(ctx, cx, cy, Math.max(3, R * 0.55), 4, -spin * 1.4, col, alpha * 0.5);
    return;
  }

  if (el.id === 'lightning') {
    // A gap-arc that stutters between two contacts. It does not travel, it
    // reappears; the strobe is doing all the work.
    const tick = quiet ? 3 : (t * 22) | 0;
    const on = quiet ? 1 : (tick % 3 === 2 ? 0.18 : 1);
    ctx.strokeStyle = rgba(col.hot, alpha * on);
    boltPath(ctx, cx - R, cy - R * 0.5, cx + R * 0.4, cy + R * 0.35,
      seed + tick, 5 + 4 * power, 5);
    ctx.fillStyle = rgba(col.hot, alpha * on);
    ctx.fillRect(px(cx - R) - 1, px(cy - R * 0.5) - 1, 3, 3);
    ctx.fillRect(px(cx + R * 0.4) - 1, px(cy + R * 0.35) - 1, 3, 3);
    return;
  }

  // force: a compression. A ring closes with eight inward ticks riding it, and
  // the ground under it darkens before anything has been thrown.
  const r = Math.max(2, R);
  shockRing(ctx, cx, cy, r, col.key, alpha * 0.8);
  for (let i = 0; i < 8; i++) {
    const a = (Math.PI * 2 * i) / 8;
    const dx = Math.cos(a), dy = Math.sin(a);
    const rr = r + 5 * (1 - easeOut(p));
    // The tick's own trail, one step down the ramp, so the eye can see which
    // way it is travelling before the ring has finished closing.
    ctx.fillStyle = rgba(tn.mid, alpha * (0.3 + 0.4 * p));
    ctx.fillRect(px(cx + dx * (rr + 3)), px(cy + dy * (rr + 3)), 2, 2);
    ctx.fillStyle = rgba(col.hot, alpha * (0.4 + 0.6 * p));
    ctx.fillRect(px(cx + dx * rr), px(cy + dy * rr), 2, 2);
  }
}

/* ACT TWO INTO ACT THREE. The impact signature: what the element does to the
 * place it landed on, and how that dies down. `fall` is the whole envelope, so
 * a caller that wants nothing drawn passes zero. */
function impactSignature(ctx, el, cx, cy, p, t, col, tn, fall, power, seed, groundY, quiet) {
  if (!(fall > 0.004)) return;
  ctx.lineWidth = 1;
  const reach = 15 + 24 * power;

  if (el.id === 'fire') {
    // Up, and it keeps going up. Tongues climb and narrow; the ring that
    // leaves the point rises off the floor instead of lying on it.
    const h = reach * 1.3 * easeOut(p);
    for (let i = 0; i < 9; i++) {
      const q = i / 8;
      const w = Math.max(1, px((1 - q) * (5 + 9 * power) * (0.6 + 0.4 * noise(seed + i, 3))));
      const wob = quiet ? 0 : Math.sin(q * 7 + t * 10) * (2 + 2 * q);
      ctx.fillStyle = rgba(q < 0.3 ? col.hot : q < 0.7 ? col.key : tn.mid,
        fall * (1 - q * 0.5));
      ctx.fillRect(px(cx - w / 2 + wob), px(cy - q * h), w, 3);
    }
    shockRing(ctx, cx, cy - h * 0.3, Math.max(1, reach * easeOut(p) * 0.8),
      col.key, fall * 0.7);
    return;
  }

  if (el.id === 'frost') {
    // One stab outward, frozen at a third of the window, then the crust cracks.
    // The stillness in the middle of the effect is the identity.
    const grow = easeOut(clamp(p / 0.34, 0, 1));
    for (let i = 0; i < 8; i++) {
      const a = (Math.PI * 2 * i) / 8 + 0.19;
      const dx = Math.cos(a), dy = Math.sin(a);
      const len = reach * grow * (0.55 + 0.45 * noise(seed + i, 11));
      for (let s = 0; s < 5; s++) {
        const q = s / 4;
        const w = Math.max(1, px((1 - q) * 4));
        ctx.fillStyle = rgba(q < 0.35 ? col.hot : col.key, fall * (1 - q * 0.35));
        ctx.fillRect(px(cx + dx * len * q), px(cy + dy * len * q), w, w);
      }
    }
    const r = Math.max(2, reach * 0.6 * grow);
    ctx.strokeStyle = rgba(col.hot, fall * 0.85);
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i;
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(px(x), px(y)); else ctx.lineTo(px(x), px(y));
    }
    ctx.closePath();
    ctx.stroke();
    if (p > 0.34) cracks(ctx, cx, cy, seed + 17, 5, reach * 0.5, col.key, fall * 0.7, 1);
    return;
  }

  if (el.id === 'arcane') {
    // Two rune rings counter-rotate around a diamond that hangs still. The
    // figure turns for as long as it exists and never travels.
    const spin = quiet ? 0 : t * 5.2;
    const open = 0.35 + easeOut(p) * 0.8;
    runeRing(ctx, cx, cy, Math.max(4, reach * 0.42 * open), 6, spin, col, fall * 0.9);
    runeRing(ctx, cx, cy, Math.max(4, reach * 0.8 * open), 4, -spin * 0.65, col, fall * 0.55);
    const d = Math.max(1, px(reach * 0.18 * (1 - p)));
    ctx.fillStyle = rgba(col.hot, fall);
    ctx.beginPath();
    ctx.moveTo(px(cx), px(cy - d));
    ctx.lineTo(px(cx + d), px(cy));
    ctx.lineTo(px(cx), px(cy + d));
    ctx.lineTo(px(cx - d), px(cy));
    ctx.closePath();
    ctx.fill();
    return;
  }

  if (el.id === 'lightning') {
    // Already there when it appears, gone between frames. Re-seeded on a strobe
    // clock so it snaps to a new shape rather than sliding into one. No easing
    // is applied anywhere in this branch, deliberately.
    const tick = quiet ? 4 : (t * 26) | 0;
    const on = quiet ? 1 : (tick % 3 === 2 ? 0.2 : 1);
    const a = fall * on;
    const top = Math.max(3, cy - reach * 1.3);
    ctx.strokeStyle = rgba(col.hot, a);
    boltPath(ctx, cx, top, cx, cy, seed + tick, 8 + 5 * power, 7);
    ctx.strokeStyle = rgba(col.key, a * 0.75);
    for (let b = 0; b < 3; b++) {
      const q = 0.3 + b * 0.22;
      const ang = -Math.PI / 2 + (noise(seed + tick, b * 13) - 0.5) * 2.6;
      const sy = lerp(top, cy, q);
      boltPath(ctx, cx, sy, cx + Math.cos(ang) * reach * 0.9,
        sy + Math.sin(ang) * reach * 0.5, seed + tick * 7 + b, 6, 4);
    }
    cracks(ctx, cx, cy, seed + tick, 5, reach * 0.7, col.hot, a * 0.7, 1);
    return;
  }

  // force: one pressure front. Three rings leave on a stagger and the dust
  // stays on the floor, because force pushes out rather than up.
  for (let i = 0; i < 3; i++) {
    const span = Math.max(0.01, 1 - i * 0.16);
    const q = clamp(p - i * 0.16, 0, 1) / span;
    if (q <= 0) continue;
    shockRing(ctx, cx, cy, Math.max(1, reach * 1.5 * easeOut(q)),
      i === 0 ? col.hot : col.key, fall * (1 - q) * (1 - i * 0.22));
  }
  const spread = reach * 1.7 * easeOut(p);
  const gy = px(Math.min(groundY - 1, cy + 4));
  for (let d = 0; d < 2; d++) {
    const dir = d ? 1 : -1;
    for (let i = 0; i < 4; i++) {
      const q = i / 3;
      const x = cx + dir * spread * (0.35 + q * 0.65);
      const w = Math.max(1, px(4 * (1 - q) * power));
      ctx.fillStyle = rgba(i < 2 ? col.key : tn.mid, fall * (1 - q) * 0.8);
      ctx.fillRect(px(x), gy - (i & 1), w, 2);
    }
  }
}

/* ---------------- the animator base ----------------
 * Every effect is the same three-act shape: a wind-up at the caster, a strike
 * on the target, and a dissipation. The base owns the clock, the seed, the
 * particle pool and the beat callbacks; subclasses own the art in the middle.
 *
 * The base also owns all three acts' *shared* layer, and that is the point: an
 * effect whose bespoke art forgot to anticipate still gets a wind-up, and an
 * effect that lands still gets the hit flash, the debris, the additive light
 * and the hold frame. Consistency across eleven effects is not something a
 * per-effect renderer can be trusted to keep.
 *
 * The hold frame deserves its own note, because it is the thing amateur effects
 * skip. `duration` is a contract — the battle loop awaits it — so the hold is
 * not bought by running longer. It is bought by remapping the clock: real time
 * advances as it always did, and the effect's own `k` stalls for a few frames
 * at the impact and then plays the dissipation back a hair faster to pay for
 * it. Weight comes from the stall, not from the extra art.
 *
 * Reduced motion is not "the same thing, faster". The still frame is posed at
 * the impact beat and cross-faded, because the job of the animation in that
 * mode is to state what happened, not to perform it. */
class Effect {
  constructor(def, opts = {}) {
    this.def = def;
    this.id = def.id;
    this.family = def.family;             // 'spell' | 'attack'
    this.motes = new Motes(def.motes || 0);
    this.beats = (def.beats || []).map((b) => ({ k: b.k, name: b.name, fired: false }));
    this.t = 0;
    this.k = 0;
    this.done = false;
    this.started = false;
    /* Hints the host may read each frame to drive screen shake and a white
     * flash it owns. Advisory: an effect that is drawn and never read still
     * looks right, it just does not move the camera. */
    this.shakeHint = 0;
    this.flashHint = 0;
    this.lightHint = 0;
    this.targetFlashHint = 0;
    this.power = 1;
    this.rawK = 0;
    this._configure(opts);
    this._layout();
  }

  /* Bind to a stage and a pair of points, then rewind. Safe to call again to
   * replay the same effect object; nothing here allocates per frame. */
  start(state = {}) {
    this._configure(state);
    this.t = 0;
    this.k = 0;
    this.rawK = 0;
    this.done = false;
    this.started = true;
    this.shakeHint = 0;
    this.flashHint = 0;
    this.lightHint = 0;
    this.targetFlashHint = 0;
    this.motes.reset();
    for (const b of this.beats) b.fired = false;
    this._layout();
    return this;
  }

  step(dt) {
    if (this.done) return true;
    if (!this.started) this.start();
    const d = Number.isFinite(dt) && dt > 0 ? dt : 0;
    this.t += d;
    this.rawK = clamp(this.t / this.duration, 0, 1);
    this.k = this._warp(this.rawK);
    this._fireBeats();
    this._hints();
    this._step(d);
    this._impactStep(d);
    this.motes.step(d);
    if (this.t >= this.duration) { this.k = 1; this.rawK = 1; this.done = true; }
    return this.done;
  }

  draw(ctx) {
    if (!ctx) return this;
    const alpha0 = ctx.globalAlpha;
    ctx.save();
    if (this.reducedMotion) {
      /* Hold the pose that reads, fade it in and out. No travel, no jitter. */
      const held = this.k;
      ctx.globalAlpha = alpha0 * clamp(arc(Math.min(1, this.k * 1.02)) * 1.5, 0, 1);
      this.k = this.poseAt;
      try { this._paint(ctx); } finally { this.k = held; }
    } else {
      this._paint(ctx);
      this.motes.draw(ctx);
    }
    ctx.restore();
    ctx.globalAlpha = alpha0;
    return this;
  }

  /* Jump to the end without drawing another frame. For a torn-down stage. */
  cancel() {
    this.done = true;
    this.k = 1;
    this.rawK = 1;
    this.shakeHint = 0;
    this.flashHint = 0;
    this.lightHint = 0;
    this.targetFlashHint = 0;
    this.motes.reset();
    return this;
  }

  /* ---- internals ---- */

  /* Options are sticky. start() with no arguments replays the effect exactly as
   * it was configured, and start({seed}) changes only the seed — anything else
   * would make a replay quietly lose its target box or its colour override. */
  _configure(patch = {}) {
    const o = this.opts ? Object.assign(this.opts, patch) : (this.opts = { ...patch });
    const st = o.stage || this.stage || STAGE_GEOM;
    this.stage = {
      w: st.w || STAGE_GEOM.w, h: st.h || STAGE_GEOM.h,
      ground: st.ground === undefined ? STAGE_GEOM.ground : st.ground,
      heroX: st.heroX === undefined ? STAGE_GEOM.heroX : st.heroX,
      enemyX: st.enemyX === undefined ? STAGE_GEOM.enemyX : st.enemyX,
    };
    const S = this.stage;
    if (o.reducedMotion !== undefined) this.reducedMotion = !!o.reducedMotion;
    else if (this.reducedMotion === undefined) this.reducedMotion = false;
    this.motes.quiet = this.reducedMotion;

    const seed = o.seed !== undefined ? o.seed : this.id;
    this.seed = (typeof seed === 'number' ? (seed >>> 0) : hash(String(seed))) || 1;

    this.colour = resolveColour(this.def.colour, o.colour);
    this.from = {
      x: o.from && o.from.x !== undefined ? o.from.x : S.heroX,
      y: o.from && o.from.y !== undefined ? o.from.y : S.ground - 20,
    };
    this.to = {
      x: o.to && o.to.x !== undefined ? o.to.x : S.enemyX,
      y: o.to && o.to.y !== undefined ? o.to.y : S.ground - 30,
    };
    /* Bounding box of the thing being hit. Bosses are 48 logical units and mobs
     * 24 at their draw scale, so the caller passes the real one when it knows. */
    const bw = o.targetBox && o.targetBox.w ? o.targetBox.w : (o.boss ? 60 : 36);
    const bh = o.targetBox && o.targetBox.h ? o.targetBox.h : (o.boss ? 68 : 46);
    this.box = {
      x: o.targetBox && o.targetBox.x !== undefined ? o.targetBox.x : this.to.x - bw / 2,
      y: o.targetBox && o.targetBox.y !== undefined ? o.targetBox.y : S.ground - bh,
      w: bw, h: bh,
    };
    this.duration = o.duration > 0
      ? o.duration
      : (this.reducedMotion ? this.def.reducedDuration : this.def.duration);
    this.impactAt = this.def.impactAt;
    this.poseAt = this.def.poseAt;
    this.onImpact = typeof o.onImpact === 'function' ? o.onImpact : null;
    this.onBeat = typeof o.onBeat === 'function' ? o.onBeat : null;
    this.intensity = o.intensity > 0 ? o.intensity : 1;

    /* Damage-scaled strength. A critical has to LOOK like a critical, and the
     * honest way to get that is one number that drives every dial at once:
     * shake, flash, debris count, ring reach, plume height and the length of
     * the hold frame. Callers that know the numbers pass `damage` with `hpMax`
     * (or a `damageRatio` outright); callers that do not get the reference
     * blow, which is calibrated so that `power === 1`.
     *
     * The curve is a square root, because damage in this game spans two orders
     * of magnitude and a linear map would make every ordinary hit invisible
     * next to a boss-killer. */
    const ratio = o.damageRatio !== undefined
      ? clamp(o.damageRatio, 0, 1)
      : (o.damage > 0 && o.hpMax > 0 ? clamp(o.damage / o.hpMax, 0, 1) : REFERENCE_BLOW);
    this.damageRatio = ratio;
    this.power = clamp(this.intensity * (0.62 + 0.9 * Math.sqrt(ratio)), 0.45, 2);

    this.element = ELEMENTS[String(o.element || this.def.element || 'force').toLowerCase()]
      || ELEMENTS.force;
    this.tone = tonesFor(this.colour);

    /* Where the clock stalls, and for how long. Reduced motion never holds:
     * that mode already shows one still frame and a second stall inside it
     * would read as a dropped frame rather than as weight. */
    this.holdAt = this.def.holdAt;
    const holdSec = this.reducedMotion
      ? 0
      : (this.def.hold || 0) * this.element.holdScale * clamp(this.power, 0.6, 1.6);
    this.holdK = clamp(holdSec / Math.max(0.05, this.duration), 0,
      (1 - this.holdAt) * 0.55);
  }

  /* Piecewise-linear clock remap. Identity up to the hold so the impact beat
   * and the caller's damage number still land on the frame they always did,
   * flat across the hold, compressed after it. Monotone, continuous, w(1) === 1
   * exactly, and a pure function of t — a replay is still identical. */
  _warp(k) {
    const a = this.holdAt, h = this.holdK;
    if (!(h > 0) || k <= a) return k;
    if (k <= a + h) return a;
    return a + (k - a - h) * ((1 - a) / (1 - a - h));
  }

  /* The impact envelope, as a function of a point on the timeline and nothing
   * else. Every dial the hit drives — hint or pixel — reads from these three,
   * which is what lets the reduced-motion path pin k to the pose frame and get
   * a pose that genuinely holds still. Read a stored hint inside a draw and the
   * still frame starts breathing on the wall clock.
   *
   * Nothing, then everything on the frame of the hit, then a squared decay. The
   * two-hundredth ramp in front of the impact is there so a host reading
   * shakeHint does not get a discontinuity it has to smooth away. */
  _env(k) {
    const a = this.holdAt;
    const rise = clamp((k - a + 0.02) / 0.02, 0, 1);
    const decay = 1 - clamp((k - a) / Math.max(0.06, this.def.settle), 0, 1);
    return rise * decay * decay;
  }

  /* Light outlives the flash. A white frame is an event; a lit stage is a
   * consequence, and the consequence is what sells the event as real. */
  _lightAt(k) {
    if (k < this.holdAt - 0.02) return 0;
    const settle = Math.max(0.06, this.def.settle);
    const tail = 1 - clamp((k - this.holdAt) / Math.max(0.08, settle * 1.5), 0, 1);
    return clamp((this._env(k) * 0.55 + tail * tail * 0.4)
      * clamp(this.power, 0.4, 1.6), 0, 1);
  }

  /* Two frames wide at sixty, and not one frame later than the hit. */
  _targetFlashAt(k) {
    const a = this.holdAt;
    const rise = clamp((k - a + 0.02) / 0.02, 0, 1);
    return clamp(rise * (1 - clamp((k - a) / 0.05, 0, 1)) * this.power, 0, 1);
  }

  /* The advisory hints, recomputed every frame for every effect rather than by
   * whichever subclass remembered to. */
  _hints() {
    const d = this.def;
    if (d.impactWhere === 'none') {
      this.shakeHint = 0; this.flashHint = 0;
      this.lightHint = 0; this.targetFlashHint = 0;
      return;
    }
    const env = this._env(this.k);
    const p = this.power;
    this.shakeHint = env * d.shake * p;
    this.flashHint = clamp(env * d.flash * p, 0, 1);
    this.lightHint = this._lightAt(this.k);
    this.targetFlashHint = this._targetFlashAt(this.k);
  }

  /* The debris throw, once, on the frame of the hit, plus the tail of element
   * motes that carries the dissipation. */
  _impactStep(dt) {
    const d = this.def;
    if (d.impactWhere === 'none' || this.reducedMotion) return;
    const a = this.holdAt;
    if (this.k < a) return;
    const P = this.hitAt;
    if (!this._burst) {
      this._burst = true;
      const n = Math.round(d.debris * clamp(this.power, 0.5, 1.9));
      const r = this.prand;
      for (let i = 0; i < n; i++) {
        this._emitElement(r, P.x + (r() - 0.5) * 10, P.y + (r() - 0.5) * 12, 1);
      }
    }
    const settle = Math.max(0.06, d.settle);
    if (this.k < a + settle) {
      const q = 1 - (this.k - a) / settle;
      this.drip(dt, 90 * q * q * this.power, this._tailEmit);
    }
  }

  /* One spark or one chunk, launched by the element's motion law. This is the
   * third place an element is expressed, and the one the eye reads longest. */
  _emitElement(r, x, y, strength) {
    const el = this.element;
    const base = el.radial ? r() * Math.PI * 2 : el.dir;
    const a = base + el.tangent + (r() - 0.5) * el.spread;
    const sp = (el.speed + r() * el.speedVar) * strength * clamp(this.power, 0.6, 1.7);
    const life = el.life + r() * el.lifeVar;
    const c = r() < 0.42 ? this.colour.hot : (r() < 0.75 ? this.colour.key : this.tone.mid);
    if (r() < el.chunk) {
      /* Debris always falls, even fire's: a burning chunk of something is still
       * a chunk of something, and watching it drop is what says "that broke". */
      this.motes.emitChunk(x, y, Math.cos(a) * sp * 0.7, Math.sin(a) * sp * 0.7 - 14,
        Math.abs(el.gravity) * 1.4 + 50, life * 1.7, 2 + ((r() * 2) | 0), c, el.spin);
    } else {
      this.motes.emit(x, y, Math.cos(a) * sp, Math.sin(a) * sp, el.gravity, life,
        r() < 0.28 ? 2 : 1, c, el.spin);
    }
  }

  _layout() {
    /* Two streams: `rand` lays the effect out and must be identical every
     * replay; `prand` feeds runtime sparks, where only the look matters. */
    this.rand = rng(this.seed);
    this.prand = rng((this.seed ^ 0x9e3779b9) >>> 0 || 7);
    this.emitAcc = 0;
    this._burst = false;
    this.motes.setBounds(this.stage.w, this.stage.h);
    /* Where the blow actually lands. A heal resolves on the caster and a resist
     * resolves a few pixels in front of the target's barrier, and both of those
     * reading as a hit on the enemy would be a lie about what happened. */
    const where = this.def.impactWhere;
    this.hitAt = where === 'caster'
      ? { x: this.from.x, y: this.from.y - 4 }
      : where === 'wall'
        ? { x: this.box.x - 4, y: this.to.y }
        : { x: this.to.x, y: this.to.y };
    /* Bound once per cast. drip() takes a callback and the impact tail emits on
     * most frames of the dissipation, so building this arrow here rather than
     * inside the loop is the difference between zero garbage and a closure a
     * frame for a third of a second. */
    this._tailEmit = (r) => {
      this._emitElement(r, this.hitAt.x + (r() - 0.5) * 12,
        this.hitAt.y + (r() - 0.5) * 14, 0.6);
    };
    this.build();
  }

  build() {}
  _step() {}
  _draw() {}

  /* The full frame: act one, the subclass's own art, act two and three. Kept
   * separate from draw() so the reduced-motion pose runs through exactly the
   * same path as the animated one. */
  _paint(ctx) {
    this._paintWindup(ctx);
    this._draw(ctx);
    this._paintImpact(ctx);
  }

  /* ACT ONE — anticipation at the caster, in the element's own motion. */
  _paintWindup(ctx) {
    const d = this.def;
    if (d.impactWhere === 'none' || !(d.wind > 0)) return;
    const w = this.ph(0, d.windTo);
    if (w <= 0 || w >= 1) return;
    const a = arc(w) * 0.85 * d.wind;
    if (!(a > 0.01)) return;
    const x = this.from.x + d.windDx, y = this.from.y;
    const prevOp = ctx.globalCompositeOperation;
    ctx.globalCompositeOperation = 'lighter';
    lightDisc(ctx, x, y, (7 + 9 * this.power) * w, this.tone.dim, a * 0.34, 2);
    groundPool(ctx, x, this.stage.ground, (9 + 11 * this.power) * w,
      this.tone.dim, a * 0.3);
    ctx.globalCompositeOperation = prevOp;
    windupSignature(ctx, this.element, x, y, w, this.t, this.colour, this.tone,
      a, this.power, this.seed, this.reducedMotion);
  }

  /* ACT TWO into ACT THREE — the strike, and the dissipation after it.
   *
   * Order matters and it is the order a real hit happens in: the target lights
   * up, the stage lights up, and only then does the debris start to fall. */
  _paintImpact(ctx) {
    const d = this.def;
    if (d.impactWhere === 'none') return;
    const a = this.holdAt;
    if (this.k < a) return;
    const settle = Math.max(0.06, d.settle);
    const p = clamp((this.k - a) / settle, 0, 1);
    if (p >= 1) return;
    const P = this.hitAt;
    const col = this.colour, tn = this.tone;
    const fall = (1 - p) * (1 - p);
    const prevOp = ctx.globalCompositeOperation;

    /* The hit flash. Hard light over the whole target box on the frame of the
     * hit, plus a one-pixel frame so the silhouette pops off the backdrop. */
    const hf = this._targetFlashAt(this.k);
    if (hf > 0.01 && d.impactWhere === 'target') {
      const b = this.box;
      ctx.globalCompositeOperation = 'lighter';
      ctx.fillStyle = rgba(col.hot, hf * 0.5);
      ctx.fillRect(px(b.x), px(b.y), px(b.w), px(b.h));
      ctx.globalCompositeOperation = prevOp;
      ctx.fillStyle = rgba(col.hot, hf * 0.9);
      ctx.fillRect(px(b.x) - 1, px(b.y) - 1, px(b.w) + 2, 1);
      ctx.fillRect(px(b.x) - 1, px(b.y + b.h), px(b.w) + 2, 1);
      ctx.fillRect(px(b.x) - 1, px(b.y), 1, px(b.h));
      ctx.fillRect(px(b.x + b.w), px(b.y), 1, px(b.h));
    }

    /* Additive light. Not a sprite of a glow: everything already on the canvas
     * under this gets brighter, which is the whole difference. */
    const lit = this._lightAt(this.k);
    if (lit > 0.01) {
      ctx.globalCompositeOperation = 'lighter';
      lightDisc(ctx, P.x, P.y, (12 + 24 * this.power) * (0.5 + p * 0.8),
        col.key, lit * 0.3, 3);
      groundPool(ctx, P.x, this.stage.ground,
        (14 + 26 * this.power) * (0.4 + p), col.key, lit * 0.24);
      if (d.wash > 0) {
        ctx.fillStyle = rgba(tn.dim, lit * d.wash * 0.5);
        ctx.fillRect(0, 0, this.stage.w, this.stage.h);
      }
      ctx.globalCompositeOperation = prevOp;
    }

    impactSignature(ctx, this.element, P.x, P.y, p, this.t, col, tn,
      fall, this.power, this.seed, this.stage.ground, this.reducedMotion);
  }

  _fireBeats() {
    for (const b of this.beats) {
      if (b.fired || this.k < b.k) continue;
      b.fired = true;
      if (b.name === 'impact' && this.onImpact) {
        try { this.onImpact(this); } catch (e) { /* a callback never stalls art */ }
      }
      if (this.onBeat) {
        try { this.onBeat(b.name, this); } catch (e) { /* ditto */ }
      }
    }
  }

  /* Phase-local 0..1 between two fractions of the whole effect. */
  ph(a, b) {
    if (this.k <= a) return 0;
    if (this.k >= b) return 1;
    return (this.k - a) / (b - a);
  }

  /* Oscillation for wobble and flicker. Flat in reduced motion, so a held pose
   * really is held. */
  osc(freq, phase = 0) {
    return this.reducedMotion ? 0 : Math.sin(this.t * freq + phase);
  }

  /* Emit `perSecond` motes without allocating an emitter object per frame. */
  drip(dt, perSecond, fn) {
    if (this.reducedMotion || perSecond <= 0) return;
    this.emitAcc += dt * perSecond;
    let n = 0;
    while (this.emitAcc >= 1 && n < 24) { this.emitAcc -= 1; n++; fn(this.prand); }
  }
}

/* A caller-supplied colour replaces the key and re-derives the rest, so a CRIT
 * in a boss's weakness colour still has a hot core and a shadow that belong to
 * it rather than to the default gold. */
function resolveColour(base, override) {
  if (!override) return base;
  if (typeof override === 'object') return { ...base, ...override };
  const key = String(override);
  return { key, hot: mix(key, '#ffffff', 0.62), deep: shade(key, -74), ink: base.ink };
}

/* ---------------- ORACLE ----------------
 * Names the algorithm family. A ring of runes contracts, a single eye opens
 * inside it, and it puts one hard beam on the enemy. The read is authority:
 * something older than the fight looked at the problem and told you what it is. */
class OracleEffect extends Effect {
  build() {
    const S = this.stage;
    this.eye = { x: lerp(this.from.x, this.to.x, 0.2), y: S.ground - 78 };
    this.aim = { x: this.to.x, y: this.box.y + this.box.h * 0.42 };
  }

  _step(dt) {
    const charge = this.ph(0.30, 0.52);
    if (charge > 0 && this.k < 0.52) {
      /* Sparks fall inward into the pupil: the eye is drawing the light in
       * before it spends it. */
      this.drip(dt, 60 * charge, (r) => {
        const a = r() * Math.PI * 2;
        const rad = 26 + r() * 14;
        this.motes.emit(
          this.eye.x + Math.cos(a) * rad, this.eye.y + Math.sin(a) * rad,
          -Math.cos(a) * rad * 2.4, -Math.sin(a) * rad * 2.4,
          0, 0.42, 1, r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
    const hit = this.ph(0.52, 0.68);
    if (hit > 0 && this.k < 0.70) {
      this.drip(dt, 150, (r) => {
        const a = -Math.PI / 2 + (r() - 0.5) * 2.6;
        const sp = 30 + r() * 70;
        this.motes.emit(this.aim.x + (r() - 0.5) * 10, this.aim.y + (r() - 0.5) * 12,
          Math.cos(a) * sp, Math.sin(a) * sp, 120, 0.5 + r() * 0.4,
          r() < 0.3 ? 2 : 1, r() < 0.5 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const gather = this.ph(0, 0.30);
    const open = this.ph(0.26, 0.48);
    const fire = this.ph(0.52, 0.62);
    const fade = this.ph(0.78, 1);
    const live = 1 - fade;

    // The bezel: contracts as it gathers, so the ring reads as closing on the eye.
    const radius = lerp(34, 23, easeOut(gather)) + this.osc(3.1) * 0.6;
    runeRing(ctx, this.eye.x, this.eye.y, radius, 8,
      this.t * (this.reducedMotion ? 0 : 0.9), col, easeOut(gather) * live);

    // Lid aperture. A closed eye is a flat line; that line is also the wind-up.
    const lid = Math.max(0.04, easeOut(open) * (1 - easeIn(this.ph(0.82, 1))));
    const w = 30, h = 15 * lid;
    ctx.lineWidth = 1;
    ctx.fillStyle = rgba(col.deep, live * 0.95);
    ctx.beginPath();
    ctx.moveTo(this.eye.x - w / 2, this.eye.y);
    ctx.quadraticCurveTo(this.eye.x, this.eye.y - h, this.eye.x + w / 2, this.eye.y);
    ctx.quadraticCurveTo(this.eye.x, this.eye.y + h, this.eye.x - w / 2, this.eye.y);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = rgba(col.ink, live);
    ctx.stroke();
    ctx.strokeStyle = rgba(col.key, live * 0.9);
    ctx.beginPath();
    ctx.moveTo(this.eye.x - w / 2, this.eye.y);
    ctx.quadraticCurveTo(this.eye.x, this.eye.y - h, this.eye.x + w / 2, this.eye.y);
    ctx.stroke();

    if (lid > 0.25) {
      const irisR = Math.max(1, 5 * lid * (1 + fire * 0.5));
      ctx.fillStyle = rgba(col.key, live);
      ctx.beginPath();
      ctx.arc(px(this.eye.x), px(this.eye.y), irisR, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = rgba(col.ink, live);
      ctx.fillRect(px(this.eye.x) - 1, px(this.eye.y - irisR * 0.8), 2, px(irisR * 1.6));
      ctx.fillStyle = rgba(col.hot, live);
      ctx.fillRect(px(this.eye.x) + 1, px(this.eye.y) - 2, 1, 1);
    }

    // The beam: one shot, snapping wide then settling thin.
    if (this.k > 0.52 && this.k < 0.86) {
      const life = this.ph(0.52, 0.86);
      const wdt = lerp(9, 2, easeOut(Math.min(1, life * 1.8))) * this.power;
      const a = (1 - easeIn(life)) * 0.95;
      beam(ctx, this.eye.x, this.eye.y + 1, this.aim.x, this.aim.y, wdt, col, a);
      // Lens crossbar at the muzzle: the flare that says this is light, not paint.
      const flare = arc(this.ph(0.52, 0.66));
      ctx.fillStyle = rgba(col.hot, flare * 0.9);
      ctx.fillRect(px(this.eye.x - 14), px(this.eye.y), 28, 1);
      ctx.fillRect(px(this.eye.x), px(this.eye.y - 10), 1, 20);
    }

    // Impact: a ring and a bright column standing on the target.
    if (fire > 0) {
      const imp = this.ph(0.54, 0.84);
      shockRing(ctx, this.aim.x, this.aim.y, lerp(2, 30, easeOut(imp)),
        col.key, (1 - imp) * 0.9, 1);
      shockRing(ctx, this.aim.x, this.aim.y, lerp(2, 18, easeOut(imp)),
        col.hot, (1 - imp) * 0.7, 1);
      ctx.fillStyle = rgba(col.hot, (1 - imp) * 0.5);
      ctx.fillRect(px(this.aim.x) - 1, px(this.box.y), 2, px(this.box.h));
    }
  }
}

/* ---------------- REVEAL_PATH ----------------
 * Names the data structure. A lattice draws itself across the stage: nodes pop
 * in, then edges *snap* between them one at a time, and the finished graph
 * collapses onto the enemy. Edges snapping in sequence is the whole point —
 * a structure is a set of relationships, and the player watches them form. */
class RevealPathEffect extends Effect {
  build() {
    const S = this.stage;
    const n = 10;
    this.nodes = [];
    for (let i = 0; i < n; i++) {
      const p = i / (n - 1);
      /* A jittered two-row lattice rather than a line: a straight run of pips
       * reads as a path, and this spell is about structure. */
      const row = i % 2;
      this.nodes.push({
        x: lerp(this.from.x - 4, this.to.x + 2, p) + (this.rand() - 0.5) * 8,
        y: S.ground - (row ? 56 : 24) - this.rand() * 10,
        pop: p * 0.22,
      });
    }
    this.edges = [];
    for (let i = 0; i < n - 1; i++) this.edges.push({ a: i, b: i + 1 });
    for (let i = 0; i < n - 2; i++) if (this.rand() < 0.55) this.edges.push({ a: i, b: i + 2 });
    const span = 0.60 - 0.24;
    this.edges.forEach((e, i) => { e.at = 0.24 + span * (i / this.edges.length); });
  }

  _step(dt) {
    if (this.k > 0.24 && this.k < 0.62) {
      this.drip(dt, 40, (r) => {
        const e = this.edges[(r() * this.edges.length) | 0];
        if (!e) return;
        const a = this.nodes[e.a], b = this.nodes[e.b];
        const p = r();
        this.motes.emit(lerp(a.x, b.x, p), lerp(a.y, b.y, p),
          (r() - 0.5) * 20, -10 - r() * 20, 40, 0.4, 1, this.colour.key);
      });
    }
    if (this.k > 0.66 && this.k < 0.80) {
      this.drip(dt, 130, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 20 + r() * 60;
        this.motes.emit(this.to.x, this.to.y, Math.cos(a) * sp, Math.sin(a) * sp,
          60, 0.5, 1, r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _nodeSprite(ctx, x, y, alpha, hot) {
    const col = this.colour;
    stamp(ctx, `rp:node:${hot ? 1 : 0}:${col.key}`, 7, 7, (c) => {
      c.fillStyle = col.ink;
      c.fillRect(2, 0, 3, 7); c.fillRect(0, 2, 7, 3);
      c.fillStyle = hot ? col.hot : col.key;
      c.fillRect(3, 1, 1, 5); c.fillRect(1, 3, 5, 1);
      c.fillStyle = col.hot;
      c.fillRect(3, 3, 1, 1);
    }, x - 3, y - 3, alpha);
  }

  _draw(ctx) {
    const col = this.colour;
    const collapse = this.ph(0.62, 0.78);
    const fade = this.ph(0.80, 1);
    const live = 1 - easeIn(fade);
    const pull = easeOut(collapse);

    ctx.lineWidth = 1;
    // Edges. Each one draws itself from a to b over its own short window, and
    // the leading end carries a bright head so the snap has a direction.
    for (const e of this.edges) {
      const grow = clamp((this.k - e.at) / 0.06, 0, 1);
      if (grow <= 0) continue;
      const a = this.nodes[e.a], b = this.nodes[e.b];
      const ax = lerp(a.x, this.to.x, pull), ay = lerp(a.y, this.to.y, pull);
      const bx = lerp(b.x, this.to.x, pull), by = lerp(b.y, this.to.y, pull);
      const ex = lerp(ax, bx, easeOut(grow)), ey = lerp(ay, by, easeOut(grow));
      ctx.strokeStyle = rgba(col.ink, live * 0.5);
      ctx.beginPath();
      ctx.moveTo(px(ax), px(ay) + 1); ctx.lineTo(px(ex), px(ey) + 1); ctx.stroke();
      ctx.strokeStyle = rgba(col.key, live * (0.45 + 0.55 * grow));
      ctx.beginPath();
      ctx.moveTo(px(ax), px(ay)); ctx.lineTo(px(ex), px(ey)); ctx.stroke();
      if (grow < 1) {
        ctx.fillStyle = rgba(col.hot, live);
        ctx.fillRect(px(ex) - 1, px(ey) - 1, 3, 3);
      }
    }

    for (let i = 0; i < this.nodes.length; i++) {
      const nd = this.nodes[i];
      const pop = clamp((this.k - nd.pop) / 0.05, 0, 1);
      if (pop <= 0) continue;
      const x = lerp(nd.x, this.to.x, pull);
      const y = lerp(nd.y, this.to.y, pull);
      this._nodeSprite(ctx, x, y, live * pop, pop < 1 || collapse > 0);
    }

    // The lattice lands: a hard ring and a square bracket around the target.
    if (collapse > 0) {
      const imp = this.ph(0.66, 0.92);
      shockRing(ctx, this.to.x, this.to.y, lerp(4, 34, easeOut(imp)),
        col.key, (1 - imp) * 0.95);
      const b = this.box, g = lerp(6, 0, easeOut(imp));
      ctx.strokeStyle = rgba(col.hot, (1 - imp) * 0.8);
      ctx.strokeRect(px(b.x - g) + 0.5, px(b.y - g) + 0.5, px(b.w + g * 2), px(b.h + g * 2));
    }
  }
}

/* ---------------- VISION ----------------
 * The full animated explanation. A wall of light sweeps the stage, and inside
 * the sweep the enemy is x-rayed: the armature under the sprite is shown, held,
 * and released. The sweep is the only effect that touches the whole stage,
 * because this is the spell that explains the whole problem. */
class VisionEffect extends Effect {
  build() {
    const b = this.box;
    /* The armature: a spine with ribs and a core. Procedural from the seed, so
     * every enemy reads as having its own insides without any of them being a
     * drawn creature. */
    this.spine = { x: b.x + b.w / 2, y0: b.y + 4, y1: b.y + b.h - 6 };
    this.ribs = [];
    const n = 4 + ((this.rand() * 3) | 0);
    for (let i = 0; i < n; i++) {
      const p = (i + 0.6) / (n + 0.2);
      this.ribs.push({
        y: lerp(this.spine.y0, this.spine.y1, p),
        w: (b.w * 0.22) + this.rand() * b.w * 0.2,
        drop: 1 + ((this.rand() * 3) | 0),
      });
    }
    this.core = { y: lerp(this.spine.y0, this.spine.y1, 0.34), r: 3 + this.rand() * 2 };
  }

  _step(dt) {
    if (this.k > 0.20 && this.k < 0.64) {
      const x = this._sweepX();
      this.drip(dt, 55, (r) => {
        this.motes.emit(x + (r() - 0.5) * 4, this.stage.ground - r() * 70,
          -20 - r() * 30, (r() - 0.5) * 20, 0, 0.45, 1,
          r() < 0.35 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _sweepX() {
    return lerp(this.from.x - 20, this.stage.w + 16, easeInOut(this.ph(0.18, 0.66)));
  }

  _draw(ctx) {
    const col = this.colour;
    const S = this.stage;
    const rise = this.ph(0, 0.20);
    const fade = this.ph(0.84, 1);
    const live = 1 - easeIn(fade);
    const x = this._sweepX();
    const half = lerp(2, 11, easeOut(rise)) * this.power;

    // The wall of light. Banded, not blurred: three hard columns and a core.
    if (this.k < 0.72) {
      const a = live * (0.75 - 0.25 * easeIn(this.ph(0.62, 0.72)));
      ctx.fillStyle = rgba(col.deep, a * 0.5);
      ctx.fillRect(px(x - half * 2), 0, px(half * 4), S.h);
      ctx.fillStyle = rgba(col.key, a * 0.45);
      ctx.fillRect(px(x - half), 0, px(half * 2), S.h);
      ctx.fillStyle = rgba(col.hot, a);
      ctx.fillRect(px(x) - 1, 0, 2, S.h);
      /* Refraction: the trailing edge is drawn as offset slices rather than a
       * pixel read-back, which keeps this at one fillRect per band instead of a
       * getImageData per frame. */
      for (let y = 0; y < S.h; y += 4) {
        const off = Math.sin((y * 0.4) + this.t * 8) * 2 * (this.reducedMotion ? 0 : 1);
        ctx.fillStyle = rgba(col.hot, a * 0.16);
        ctx.fillRect(px(x - half * 3 + off), y, px(half), 2);
      }
    }

    // The x-ray. Lit once the sweep has reached the target and held after.
    const reached = clamp((x - this.box.x) / Math.max(1, this.box.w * 0.5), 0, 1);
    const hold = live * reached * (1 - easeIn(this.ph(0.80, 1)));
    if (hold > 0.01) {
      const b = this.box;
      ctx.fillStyle = rgba(col.deep, hold * 0.42);
      ctx.fillRect(px(b.x), px(b.y), px(b.w), px(b.h));

      ctx.fillStyle = rgba(col.hot, hold * 0.95);
      ctx.fillRect(px(this.spine.x), px(this.spine.y0), 1, px(this.spine.y1 - this.spine.y0));
      for (const rib of this.ribs) {
        ctx.fillStyle = rgba(col.key, hold * 0.85);
        ctx.fillRect(px(this.spine.x - rib.w), px(rib.y), px(rib.w * 2), 1);
        ctx.fillRect(px(this.spine.x - rib.w), px(rib.y), 1, rib.drop);
        ctx.fillRect(px(this.spine.x + rib.w) - 1, px(rib.y), 1, rib.drop);
      }
      const beat = 1 + (this.reducedMotion ? 0 : Math.sin(this.t * 9) * 0.18);
      const r = this.core.r * beat;
      ctx.fillStyle = rgba(col.hot, hold);
      ctx.beginPath();
      ctx.moveTo(px(this.spine.x), px(this.core.y - r));
      ctx.lineTo(px(this.spine.x + r), px(this.core.y));
      ctx.lineTo(px(this.spine.x), px(this.core.y + r));
      ctx.lineTo(px(this.spine.x - r), px(this.core.y));
      ctx.closePath();
      ctx.fill();

      // Survey brackets: corner ticks, the way a diagram frames its subject.
      const g = 3;
      ctx.fillStyle = rgba(col.key, hold * 0.9);
      for (const sx of [-1, 1]) {
        for (const sy of [-1, 1]) {
          const cx = sx < 0 ? b.x - g : b.x + b.w + g - 1;
          const cy = sy < 0 ? b.y - g : b.y + b.h + g - 1;
          ctx.fillRect(px(cx - (sx < 0 ? 0 : 4)), px(cy), 5, 1);
          ctx.fillRect(px(cx), px(cy - (sy < 0 ? 0 : 4)), 1, 5);
        }
      }
    }
  }
}

/* ---------------- PSEUDOSIGHT ----------------
 * Pseudocode. A spellbook page unfolds in the air and its rune-rows scroll
 * upward past a reading line, one row lighting as it is read. The last row
 * tears off the page and stamps itself on the enemy. Rows are abstract runes:
 * the page shows that something is being read aloud, never what it says. */
class PseudosightEffect extends Effect {
  build() {
    const S = this.stage;
    this.page = {
      x: lerp(this.from.x, this.to.x, 0.34) - 26,
      y: S.ground - 84,
      w: 52, h: 58,
    };
    this.rows = [];
    const n = 14;
    for (let i = 0; i < n; i++) {
      this.rows.push({
        indent: (this.rand() * 3) | 0,
        cells: 4 + ((this.rand() * 7) | 0),
        seed: (this.seed + i * 2657) >>> 0,
        y: i * 7,
      });
    }
    this.scrollSpan = n * 7;
  }

  _step(dt) {
    if (this.k > 0.18 && this.k < 0.66) {
      this.drip(dt, 30, (r) => {
        this.motes.emit(this.page.x + r() * this.page.w, this.page.y + this.page.h * 0.6,
          (r() - 0.5) * 12, -18 - r() * 22, 0, 0.6, 1,
          r() < 0.3 ? this.colour.hot : this.colour.key);
      });
    }
    if (this.k > 0.70 && this.k < 0.84) {
      this.drip(dt, 110, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 18 + r() * 55;
        this.motes.emit(this.to.x, this.to.y, Math.cos(a) * sp, Math.sin(a) * sp,
          70, 0.5, 1, r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const P = this.page;
    const unfold = easeOut(this.ph(0, 0.18));
    const close = easeIn(this.ph(0.84, 1));
    const live = 1 - close;
    if (live <= 0.01) return;

    // The page opens from a lit seam, vertically, like a book held open edge-on.
    const h = P.h * unfold;
    const y = P.y + (P.h - h) / 2;
    bevelPlate(ctx, P.x, y, P.w, h, col, live * 0.95);
    ctx.fillStyle = rgba(col.ink, live * 0.8);
    ctx.fillRect(px(P.x + 1), px(y + 1), px(P.w - 2), px(Math.max(0, h - 2)));
    if (unfold < 1) {
      ctx.fillStyle = rgba(col.hot, live);
      ctx.fillRect(px(P.x), px(P.y + P.h / 2), px(P.w), 1);
      return;
    }

    const readY = y + h * 0.62;
    const scroll = easeInOut(this.ph(0.18, 0.68)) * this.scrollSpan;

    ctx.save();
    ctx.beginPath();
    ctx.rect(px(P.x + 2), px(y + 2), px(P.w - 4), px(h - 4));
    ctx.clip();

    // Spine rule down the left margin: the page has an edge, not just rows.
    ctx.fillStyle = rgba(col.deep, live);
    ctx.fillRect(px(P.x + 4), px(y), 1, px(h));

    for (const row of this.rows) {
      // Wrapped scroll, so the page never runs out of text mid-read.
      let ry = y + h - 6 + row.y - scroll;
      while (ry < y - GLYPH_H) ry += this.scrollSpan;
      if (ry > y + h) continue;
      const dist = Math.abs(ry - readY);
      const lit = clamp(1 - dist / 14, 0, 1);
      const a = live * (0.28 + lit * 0.72);
      const rx = P.x + 7 + row.indent * 4;
      drawGlyphStrip(ctx, rx, ry, row.cells, row.seed,
        lit > 0.75 ? col.hot : col.key, a);
      if (lit > 0.75) {
        ctx.fillStyle = rgba(col.key, live * 0.22);
        ctx.fillRect(px(P.x + 2), px(ry) - 1, px(P.w - 4), GLYPH_H + 2);
      }
    }

    // The reading line and the cursor block that walks along it.
    ctx.fillStyle = rgba(col.hot, live * 0.75);
    ctx.fillRect(px(P.x + 2), px(readY) + GLYPH_H + 1, px(P.w - 4), 1);
    const cur = (this.reducedMotion ? 0.5 : (this.t * 2.2) % 1);
    ctx.fillStyle = rgba(col.hot, live * (this.reducedMotion ? 0.9 : (cur < 0.5 ? 1 : 0.35)));
    ctx.fillRect(px(P.x + 7 + cur * (P.w - 16)), px(readY), 2, GLYPH_H);
    ctx.restore();

    // The torn row flies out and stamps on the target.
    const fly = this.ph(0.68, 0.80);
    if (fly > 0) {
      const e = easeIn(fly);
      const fx = lerp(P.x + P.w / 2, this.to.x, e);
      const fy = lerp(readY, this.to.y, e);
      const row = this.rows[3];
      drawGlyphStrip(ctx, fx - row.cells * 2, fy - 2, row.cells, row.seed,
        col.hot, live * (1 - e * 0.4));
      ctx.fillStyle = rgba(col.key, live * (1 - e) * 0.5);
      ctx.fillRect(px(fx - 14), px(fy), 28, 1);
    }
    const imp = this.ph(0.74, 0.96);
    if (imp > 0) {
      shockRing(ctx, this.to.x, this.to.y, lerp(3, 30, easeOut(imp)), col.key, (1 - imp) * 0.9);
      runeRing(ctx, this.to.x, this.to.y, lerp(6, 20, easeOut(imp)), 6,
        this.reducedMotion ? 0 : this.t * 2, col, (1 - imp) * 0.8);
    }
  }
}

/* ---------------- CODE_FRAGMENT ----------------
 * A small real implementation fragment. Shards fly in from off-stage, lock into
 * a stacked block with a chrome bevel, then the whole block turns edge-on and
 * strikes. The lock-in per shard is what makes it feel like assembly rather
 * than an appearing rectangle. */
class CodeFragmentEffect extends Effect {
  build() {
    const S = this.stage;
    this.anchor = { x: lerp(this.from.x, this.to.x, 0.42), y: S.ground - 62 };
    this.lines = [];
    const n = 5;
    for (let i = 0; i < n; i++) {
      const indent = i === 0 || i === n - 1 ? 0 : 1 + ((this.rand() * 2) | 0);
      const side = this.rand() < 0.5 ? -1 : 1;
      this.lines.push({
        indent,
        cells: 5 + ((this.rand() * 6) | 0),
        seed: (this.seed + i * 7919) >>> 0,
        y: i * 7,
        fx: side < 0 ? -40 - this.rand() * 40 : S.w + 20 + this.rand() * 40,
        fy: S.ground - 110 + this.rand() * 90,
        at: 0.14 + i * 0.055,
      });
    }
    this.blockW = 0;
    for (const l of this.lines) {
      this.blockW = Math.max(this.blockW, 6 + l.indent * 4 + l.cells * GLYPH_ADVANCE);
    }
    this.blockH = n * 7 + 4;
  }

  _step(dt) {
    for (const l of this.lines) {
      const lock = (this.k - l.at) / 0.06;
      if (lock > 0 && lock < 1.2 && !l.sparked) {
        l.sparked = true;
        for (let i = 0; i < 6; i++) {
          const r = this.prand;
          this.motes.emit(this.anchor.x - this.blockW / 2 + r() * this.blockW,
            this.anchor.y - this.blockH / 2 + l.y,
            (r() - 0.5) * 60, -20 - r() * 40, 160, 0.4, 1, this.colour.hot);
        }
      }
    }
    if (this.k > 0.60 && this.k < 0.78) {
      this.drip(dt, 160, (r) => {
        const a = -Math.PI * 0.5 + (r() - 0.5) * 3;
        const sp = 30 + r() * 80;
        this.motes.emit(this.to.x + (r() - 0.5) * 12, this.to.y + (r() - 0.5) * 14,
          Math.cos(a) * sp, Math.sin(a) * sp, 170, 0.55,
          r() < 0.25 ? 2 : 1, r() < 0.5 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const strike = this.ph(0.56, 0.70);
    const fade = this.ph(0.82, 1);
    const live = 1 - easeIn(fade);
    const e = easeIn(strike);
    // The assembled block travels as one object once it has locked.
    const cx = lerp(this.anchor.x, this.to.x, e);
    const cy = lerp(this.anchor.y, this.to.y, e);
    // Turning edge-on: the block narrows to a blade as it commits.
    const squash = 1 - easeIn(this.ph(0.58, 0.72)) * 0.85;
    const x0 = cx - this.blockW / 2;
    const y0 = cy - this.blockH / 2;

    if (this.k > 0.16 && squash > 0.2) {
      ctx.save();
      ctx.translate(px(cx), px(cy));
      ctx.scale(squash, 1);
      ctx.translate(-px(cx), -px(cy));
      bevelPlate(ctx, x0, y0, this.blockW, this.blockH, col,
        live * clamp(this.ph(0.16, 0.30), 0, 1) * 0.9);
      ctx.restore();
    }

    for (const l of this.lines) {
      const lock = clamp((this.k - l.at) / 0.06, 0, 1);
      if (lock <= 0) continue;
      const tx = x0 + 3 + l.indent * 4;
      const ty = y0 + 2 + l.y;
      const sx = lerp(l.fx, tx, overshoot(lock));
      const sy = lerp(l.fy, ty, overshoot(lock));
      const a = live * (0.5 + 0.5 * lock);
      ctx.save();
      if (lock >= 1 && squash < 1) {
        ctx.translate(px(cx), px(cy));
        ctx.scale(squash, 1);
        ctx.translate(-px(cx), -px(cy));
      }
      // Indent rule: the thing that makes a stack of runes read as code.
      if (l.indent) {
        ctx.fillStyle = rgba(col.deep, a * 0.9);
        ctx.fillRect(px(x0 + 3), px(sy), px(l.indent * 4 - 1), GLYPH_H);
      }
      drawGlyphStrip(ctx, sx, sy, l.cells, l.seed, lock < 1 ? col.hot : col.key, a);
      if (lock > 0 && lock < 1) {
        // In-flight shards trail a hard leading edge.
        ctx.fillStyle = rgba(col.hot, a * 0.8);
        ctx.fillRect(px(sx) - 2, px(sy) - 1, 1, GLYPH_H + 2);
      }
      ctx.restore();
    }

    // The lock flash: every shard home, the block reads as one piece for a beat.
    const seated = arc(this.ph(0.42, 0.58));
    if (seated > 0) {
      ctx.strokeStyle = rgba(col.hot, seated * live * 0.9);
      ctx.lineWidth = 1;
      ctx.strokeRect(px(x0) - 1.5, px(y0) - 1.5, px(this.blockW) + 3, px(this.blockH) + 3);
    }

    // The strike itself: a blade edge and a shatter ring on the target.
    if (strike > 0) {
      const imp = this.ph(0.62, 0.90);
      ctx.fillStyle = rgba(col.hot, (1 - imp) * live);
      ctx.fillRect(px(cx) - 1, px(cy - this.blockH / 2), 2, px(this.blockH));
      shockRing(ctx, this.to.x, this.to.y, lerp(3, 32, easeOut(imp)), col.key, (1 - imp) * 0.9);
      cracks(ctx, this.to.x, this.to.y, this.seed + 3, 6, 18, col.hot,
        (1 - imp) * 0.85, easeOut(imp));
    }
  }
}

/* ---------------- PHOENIX ----------------
 * The complete worked solution, granted after repeated failure. This is the
 * biggest effect in the game and the only warm one: embers gather at the
 * player's feet, a column ignites, a firebird forms and sweeps the stage, and
 * the light it leaves is gold rather than red. The player has just failed
 * several times; the game answers with a rescue, not a punishment. */
class PhoenixEffect extends Effect {
  build() {
    const S = this.stage;
    this.nest = { x: this.from.x, y: S.ground - 2 };
    this.apex = { x: lerp(this.from.x, this.to.x, 0.42), y: S.ground - 84 };
    this.gathers = [];
    for (let i = 0; i < 22; i++) {
      this.gathers.push({
        x: this.rand() * S.w,
        y: S.ground - this.rand() * 96,
        at: this.rand() * 0.2,
      });
    }
    this.feathers = [];
    for (let i = 0; i < 14; i++) {
      this.feathers.push({
        x: this.rand(), y: this.rand(), rot: this.rand() * Math.PI * 2,
        drift: (this.rand() - 0.5) * 26,
      });
    }
  }

  _step(dt) {
    // Ignition column throws embers straight up off the nest.
    if (this.k > 0.30 && this.k < 0.55) {
      this.drip(dt, 220, (r) => {
        this.motes.emit(this.nest.x + (r() - 0.5) * 16, this.nest.y,
          (r() - 0.5) * 26, -70 - r() * 90, 46, 0.7 + r() * 0.5,
          r() < 0.3 ? 2 : 1, r() < 0.45 ? this.colour.hot : this.colour.key);
      });
    }
    // The bird sheds embers along its flight.
    if (this.k > 0.55 && this.k < 0.88) {
      const b = this._birdAt();
      this.drip(dt, 180, (r) => {
        this.motes.emit(b.x + (r() - 0.5) * 24, b.y + (r() - 0.5) * 14,
          (r() - 0.5) * 30, 10 + r() * 40, 30, 0.6 + r() * 0.5, 1,
          r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
    if (this.k > 0.80 && this.k < 0.92) {
      this.drip(dt, 200, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 40 + r() * 90;
        this.motes.emit(this.to.x, this.to.y - 6, Math.cos(a) * sp, Math.sin(a) * sp,
          -20, 0.9, r() < 0.3 ? 2 : 1, r() < 0.5 ? this.colour.hot : this.colour.key);
      });
    }
  }

  /* Flight path: straight up off the nest, then a flat sweep onto the target. */
  _birdAt() {
    const rise = easeOut(this.ph(0.46, 0.66));
    const cross = easeInOut(this.ph(0.62, 0.86));
    return {
      x: lerp(lerp(this.nest.x, this.apex.x, rise), this.to.x, cross),
      y: lerp(lerp(this.nest.y - 6, this.apex.y, rise), this.to.y - 10, cross),
      spread: clamp(this.ph(0.48, 0.70), 0, 1),
      flap: this.reducedMotion ? 0.7 : 0.62 + Math.sin(this.t * 9) * 0.38,
    };
  }

  _drawBird(ctx, b, alpha) {
    const col = this.colour;
    const open = easeOut(b.spread);
    const span = 34 * open;
    const lift = b.flap;
    ctx.lineWidth = 1;
    // Wings: stacked flame quills swept back, brighter toward the leading edge.
    for (const dir of [-1, 1]) {
      for (let i = 0; i < 7; i++) {
        const p = i / 6;
        const len = span * (0.45 + 0.55 * Math.sin(Math.PI * (0.25 + p * 0.75)));
        const ex = b.x + dir * len;
        const ey = b.y - (1 - p) * 10 * lift + p * 12;
        ctx.strokeStyle = rgba(i < 2 ? col.hot : mix(col.key, col.deep, p * 0.5),
          alpha * (0.55 + 0.45 * (1 - p)));
        ctx.beginPath();
        ctx.moveTo(px(b.x + dir * 2), px(b.y - 2 + p * 3));
        ctx.quadraticCurveTo(px(b.x + dir * len * 0.6), px(b.y - 8 * lift + p * 4),
          px(ex), px(ey));
        ctx.stroke();
      }
    }
    // Body, crest and the ember tail streaming behind.
    ctx.fillStyle = rgba(col.ink, alpha * 0.8);
    ctx.fillRect(px(b.x) - 3, px(b.y) - 6, 6, 13);
    ctx.fillStyle = rgba(col.key, alpha);
    ctx.fillRect(px(b.x) - 2, px(b.y) - 5, 4, 11);
    ctx.fillStyle = rgba(col.hot, alpha);
    ctx.fillRect(px(b.x) - 1, px(b.y) - 4, 2, 6);
    ctx.fillRect(px(b.x) - 1, px(b.y) - 8, 2, 3);           // head
    ctx.fillStyle = rgba(col.hot, alpha * 0.9);
    ctx.fillRect(px(b.x) + 1, px(b.y) - 9, 3, 1);           // beak
    for (let i = 0; i < 5; i++) {                            // tail
      const p = i / 4;
      const wob = this.reducedMotion ? 0 : Math.sin(this.t * 7 - p * 3) * 3 * p;
      ctx.fillStyle = rgba(mix(col.key, col.deep, p), alpha * (1 - p * 0.7));
      ctx.fillRect(px(b.x - 1 + wob), px(b.y + 6 + i * 3), 2, 3);
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const S = this.stage;
    const fade = this.ph(0.92, 1);
    const live = 1 - easeIn(fade);

    // Gather: embers slide in across the whole stage toward the nest.
    const gather = this.ph(0, 0.42);
    if (gather < 1) {
      for (const g of this.gathers) {
        const p = clamp((this.k - g.at) / 0.34, 0, 1);
        if (p <= 0) continue;
        const e = easeIn(p);
        const gx = lerp(g.x, this.nest.x, e);
        const gy = lerp(g.y, this.nest.y - 4, e);
        ctx.fillStyle = rgba(p > 0.7 ? col.hot : col.key, live * (1 - p * 0.5) * 0.9);
        ctx.fillRect(px(gx), px(gy), p > 0.6 ? 2 : 1, p > 0.6 ? 2 : 1);
      }
      // The ground under the caster heats before anything else happens.
      const heat = easeOut(gather);
      ctx.fillStyle = rgba(col.key, live * heat * 0.4);
      ctx.fillRect(px(this.nest.x - 14 * heat), px(S.ground - 2), px(28 * heat), 2);
    }

    // Ignition column.
    const ign = this.ph(0.30, 0.58);
    if (ign > 0 && ign < 1) {
      const hgt = lerp(0, 92, easeOut(ign));
      const a = live * (1 - easeIn(ign)) * 0.95;
      for (let i = 0; i < 16; i++) {
        const p = i / 15;
        const w = Math.max(1, (1 - p) * 16 * (0.7 + 0.3 * Math.sin(p * 9 + this.t * 12)));
        const wob = this.reducedMotion ? 0 : Math.sin(p * 6 + this.t * 9) * 3;
        ctx.fillStyle = rgba(p < 0.35 ? col.hot : col.key, a * (1 - p * 0.55));
        ctx.fillRect(px(this.nest.x - w / 2 + wob), px(this.nest.y - p * hgt), px(w), 3);
      }
    }

    // The bird.
    if (this.k > 0.44 && this.k < 0.94) {
      const b = this._birdAt();
      // Warm glow it carries, drawn under the bird so the bird stays crisp.
      const glow = live * (0.35 + 0.25 * Math.abs(this.osc(6)));
      ctx.fillStyle = rgba(col.deep, glow * 0.5);
      ctx.fillRect(px(b.x - 26), px(b.y - 18), 52, 36);
      this._drawBird(ctx, b, live * clamp(this.ph(0.44, 0.52), 0, 1));
    }

    // Impact: a warm wash and an expanding double ring. Gold, never red.
    const imp = this.ph(0.80, 0.98);
    if (imp > 0) {
      const a = (1 - imp) * live;
      const pw = clamp(this.power, 0.6, 1.8);
      /* Additive, so the backdrop and both fighters brighten under it. A flat
       * alpha wash would have greyed the stage out instead of lighting it. */
      const prevOp = ctx.globalCompositeOperation;
      ctx.globalCompositeOperation = 'lighter';
      ctx.fillStyle = rgba(col.hot, a * 0.16);
      ctx.fillRect(0, 0, S.w, S.h);
      ctx.globalCompositeOperation = prevOp;
      shockRing(ctx, this.to.x, this.to.y - 6, lerp(6, 56 * pw, easeOut(imp)), col.hot, a * 0.9);
      shockRing(ctx, this.to.x, this.to.y - 6, lerp(2, 34 * pw, easeOut(imp)), col.key, a);
      // Feathers fall out of the impact and settle.
      for (const f of this.feathers) {
        const fx = this.to.x + (f.x - 0.5) * 70;
        const fy = lerp(this.to.y - 30, S.ground - 2, easeIn(imp)) + f.y * 12;
        stamp(ctx, `ph:feather:${col.key}`, 7, 4, (c) => {
          c.fillStyle = col.ink; c.fillRect(0, 1, 7, 2);
          c.fillStyle = col.key; c.fillRect(1, 1, 5, 1);
          c.fillStyle = col.hot; c.fillRect(2, 2, 3, 1);
        }, fx + f.drift * imp, fy, a * 1.1);
      }
    }
  }
}

/* ---------------- attack effects ----------------
 * Four graded outcomes the battle has to tell apart at a glance, mid-sequence,
 * while several resolve in a row. They are deliberately shorter than the spells:
 * trials resolve about ten frames apart, and a one-second normal hit would turn
 * a clean pass into mush. CRIT is the exception and is allowed to take the
 * stage, because a weakness strike is the rarest thing the player will see. */

/* Rotatable blit. Same cache-or-paint contract as stamp(). */
function stampRot(ctx, key, w, h, paint, cx, cy, rot, alpha = 1, scale = 1) {
  if (!(alpha > 0)) return;
  const c = cachedCanvas(key, w, h, paint);
  const prev = ctx.globalAlpha;
  ctx.save();
  ctx.globalAlpha = prev * clamp(alpha, 0, 1);
  ctx.translate(px(cx), px(cy));
  if (rot) ctx.rotate(rot);
  if (scale !== 1) ctx.scale(scale, scale);
  if (c) ctx.drawImage(c, -(w >> 1), -(h >> 1));
  else { ctx.translate(-(w >> 1), -(h >> 1)); paint(ctx); }
  ctx.restore();
  ctx.globalAlpha = prev;
}

/* The weakness sigil: a hexagonal plate with a rune locked in it. Cached per
 * colour, because a crit in the same weakness colour recurs all fight. */
function paintSigil(size, col) {
  return (c) => {
    const r = size / 2 - 1;
    const cx = size / 2, cy = size / 2;
    c.lineWidth = 1;
    c.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 2;
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.closePath();
    c.fillStyle = col.deep; c.fill();
    c.strokeStyle = col.ink; c.stroke();
    c.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 2;
      const x = cx + Math.cos(a) * (r - 3), y = cy + Math.sin(a) * (r - 3);
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.closePath();
    c.strokeStyle = col.key; c.stroke();
    paintGlyph(c, 5, col.hot, Math.round(cx - 5), Math.round(cy - 2));
    paintGlyph(c, 20, col.hot, Math.round(cx + 2), Math.round(cy - 2));
    c.fillStyle = STEEL;
    c.fillRect(Math.round(cx - 3), Math.round(cy - r + 2), 6, 1);
  };
}

/* --- a normal hit: a steel slash and sparks. Fast, legible, cheap. --- */
class HitEffect extends Effect {
  build() {
    this.angle = -0.7 + this.rand() * 0.5;
    this.reach = 26 + this.rand() * 6;
  }

  _step(dt) {
    if (this.k > 0.32 && this.k < 0.6) {
      this.drip(dt, 220, (r) => {
        const a = this.angle + Math.PI / 2 + (r() - 0.5) * 2.2;
        const sp = 40 + r() * 90;
        this.motes.emit(this.to.x + (r() - 0.5) * 8, this.to.y + (r() - 0.5) * 10,
          Math.cos(a) * sp, Math.sin(a) * sp, 220, 0.3 + r() * 0.25, 1,
          r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const wind = this.ph(0, 0.3);
    const cut = this.ph(0.3, 0.52);
    const fade = this.ph(0.52, 1);

    // Wind-up: the blade gathers at the caster as a short bright chevron.
    if (wind > 0 && wind < 1) {
      const a = arc(wind) * 0.9;
      ctx.strokeStyle = rgba(col.hot, a);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(px(this.from.x + 8), px(this.from.y), 8, -1.2, 0.4);
      ctx.stroke();
    }
    // The cut: a swept arc that crosses the target box.
    if (cut > 0) {
      const e = easeOut(cut);
      const a = (1 - easeIn(fade)) * 0.95;
      const cx = lerp(this.from.x + 10, this.to.x, e);
      const cy = lerp(this.from.y, this.to.y, e);
      /* The blade is as long as the blow is hard. Same art, scaled: a chip of
       * damage cuts a short arc, a heavy one cuts across the whole box. */
      const reach = this.reach * clamp(this.power, 0.7, 1.5);
      ctx.save();
      ctx.translate(px(cx), px(cy));
      ctx.rotate(this.angle);
      ctx.fillStyle = rgba(col.ink, a * 0.6);
      ctx.fillRect(px(-reach * e), -2, px(reach * 2 * e), 4);
      ctx.fillStyle = rgba(col.key, a * 0.85);
      ctx.fillRect(px(-reach * e), -1, px(reach * 2 * e), 2);
      ctx.fillStyle = rgba(col.hot, a);
      ctx.fillRect(px(-reach * e), 0, px(reach * 2 * e), 1);
      ctx.restore();
      if (cut >= 1) {
        const imp = this.ph(0.5, 1);
        shockRing(ctx, this.to.x, this.to.y, lerp(2, 16 * this.power, easeOut(imp)),
          col.hot, (1 - imp) * 0.8);
      }
    }
  }
}

/* --- CRITICAL: the weakness strike. The sigil forms, slams, and shatters.
 * This is the biggest non-spell effect in the game and it is allowed to be. --- */
class CritEffect extends Effect {
  build() {
    this.shards = [];
    for (let i = 0; i < 16; i++) {
      const a = (Math.PI * 2 * i) / 16 + this.rand() * 0.4;
      this.shards.push({
        a, sp: 60 + this.rand() * 110, spin: (this.rand() - 0.5) * 14,
        w: 3 + ((this.rand() * 4) | 0), h: 2 + ((this.rand() * 3) | 0),
      });
    }
    this.sigilSize = 26;
    this.hover = { x: this.to.x, y: this.box.y - 14 };
  }

  _step(dt) {
    if (this.k > 0.08 && this.k < 0.34) {
      // Charge: motes drawn up into the sigil as it forms.
      this.drip(dt, 90, (r) => {
        const a = r() * Math.PI * 2;
        const rad = 24 + r() * 16;
        this.motes.emit(this.hover.x + Math.cos(a) * rad, this.hover.y + Math.sin(a) * rad,
          -Math.cos(a) * rad * 2.6, -Math.sin(a) * rad * 2.6, 0, 0.4, 1, this.colour.key);
      });
    }
    if (this.k > 0.36 && this.k < 0.62) {
      this.drip(dt, 240, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 50 + r() * 140;
        this.motes.emit(this.to.x + (r() - 0.5) * 10, this.to.y + (r() - 0.5) * 10,
          Math.cos(a) * sp, Math.sin(a) * sp, 260, 0.45 + r() * 0.45,
          r() < 0.3 ? 2 : 1, r() < 0.5 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const form = this.ph(0, 0.3);
    const slam = this.ph(0.3, 0.4);
    const burst = this.ph(0.4, 0.74);
    const fade = this.ph(0.74, 1);
    const live = 1 - easeIn(fade);

    // Forming: the ring first, the plate inside it.
    if (form > 0 && slam < 1) {
      const y = lerp(this.hover.y, this.to.y, easeIn(slam));
      const scale = lerp(1.8, 1, easeOut(form)) * lerp(1, 1.25, slam);
      runeRing(ctx, this.hover.x, y, lerp(30, 18, easeOut(form)), 6,
        this.reducedMotion ? 0 : this.t * 2.4, col, easeOut(form) * (1 - slam));
      stampRot(ctx, `crit:sigil:${col.key}:${this.sigilSize}`,
        this.sigilSize, this.sigilSize, paintSigil(this.sigilSize, col),
        this.hover.x, y, this.osc(2) * 0.05, easeOut(form), scale);
      // The shadow the sigil casts on the target: the tell that it is coming.
      ctx.fillStyle = rgba(col.ink, easeOut(form) * 0.35);
      ctx.fillRect(px(this.to.x - 12), px(this.stage.ground - 2), 24, 2);
    }

    // Shatter: cracks, two rings, and the plate blowing apart into shards.
    if (burst > 0) {
      const e = easeOut(burst);
      /* Every dimension of the shatter rides the damage: how far the rings get,
       * how deep the cracks run, how hard the shards are thrown. */
      const pw = clamp(this.power, 0.6, 1.8);
      shockRing(ctx, this.to.x, this.to.y, lerp(4, 52 * pw, e), col.hot, (1 - burst) * live);
      shockRing(ctx, this.to.x, this.to.y, lerp(2, 30 * pw, e), col.key, (1 - burst) * live * 0.9);
      cracks(ctx, this.to.x, this.to.y, this.seed, 9, 26 * pw, col.hot,
        (1 - burst) * live * 0.95, e);
      for (const s of this.shards) {
        const d = s.sp * burst * 0.5 * pw;
        const x = this.to.x + Math.cos(s.a) * d;
        const y = this.to.y + Math.sin(s.a) * d + burst * burst * 34;
        stampRot(ctx, `crit:shard:${col.key}:${s.w}:${s.h}`, s.w + 2, s.h + 2, (c) => {
          c.fillStyle = col.ink; c.fillRect(0, 0, s.w + 2, s.h + 2);
          c.fillStyle = col.key; c.fillRect(1, 1, s.w, s.h);
          c.fillStyle = col.hot; c.fillRect(1, 1, s.w, 1);
        }, x, y, s.a + burst * s.spin, (1 - burst) * live);
      }
      // A hard white frame on the target for two frames: the impact itself.
      if (burst < 0.2) {
        const b = this.box;
        ctx.fillStyle = rgba(col.hot, (1 - burst / 0.2) * 0.5);
        ctx.fillRect(px(b.x - 2), px(b.y - 2), px(b.w + 4), px(b.h + 4));
      }
    }
  }
}

/* --- RESISTED: the blow arrives and visibly bounces. The hex barrier is the
 * reason the player reads it as "wrong tool" rather than "missed". --- */
class ResistEffect extends Effect {
  build() {
    this.wall = { x: this.box.x - 4, y: this.to.y };
    this.facets = [];
    for (let i = 0; i < 5; i++) {
      this.facets.push({ y: this.box.y + 6 + i * (this.box.h - 12) / 4, r: 7 + this.rand() * 3 });
    }
  }

  _step(dt) {
    if (this.k > 0.48 && this.k < 0.72) {
      this.drip(dt, 120, (r) => {
        const a = Math.PI + (r() - 0.5) * 1.8;
        const sp = 30 + r() * 70;
        this.motes.emit(this.wall.x, this.wall.y + (r() - 0.5) * 18,
          Math.cos(a) * sp, Math.sin(a) * sp - 20, 210, 0.45, 1, this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const fly = this.ph(0.12, 0.48);
    const hitk = this.ph(0.48, 0.62);
    const back = this.ph(0.56, 0.92);
    const live = 1 - easeIn(this.ph(0.82, 1));

    // Outbound bolt, then the same bolt thrown back over the caster's shoulder.
    if (fly > 0 && back <= 0) {
      const e = easeOut(fly);
      const x = lerp(this.from.x + 8, this.wall.x, e);
      const y = lerp(this.from.y, this.wall.y, e);
      ctx.fillStyle = rgba(col.ink, live * 0.7);
      ctx.fillRect(px(x) - 4, px(y) - 2, 9, 5);
      ctx.fillStyle = rgba(col.key, live);
      ctx.fillRect(px(x) - 3, px(y) - 1, 7, 3);
      ctx.fillStyle = rgba(col.hot, live);
      ctx.fillRect(px(x), px(y), 3, 1);
    } else if (back > 0) {
      const e = easeOut(back);
      const x = lerp(this.wall.x, this.wall.x - 70, e);
      const y = lerp(this.wall.y, this.wall.y - 40, e) + e * e * 46;
      ctx.fillStyle = rgba(col.key, live * (1 - back) * 0.9);
      ctx.fillRect(px(x), px(y), 3, 2);
      ctx.fillStyle = rgba(col.hot, live * (1 - back) * 0.6);
      ctx.fillRect(px(x) + 3, px(y), 2, 1);
    }

    // The barrier: a stack of hex facets lighting on contact, then rippling out.
    if (hitk > 0) {
      const flash = 1 - easeIn(this.ph(0.5, 0.86));
      ctx.lineWidth = 1;
      for (const f of this.facets) {
        const push = easeOut(this.ph(0.5, 0.8)) * 3;
        ctx.strokeStyle = rgba(col.hot, flash * live * 0.9);
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const a = (Math.PI / 3) * i;
          const x = this.wall.x - push + Math.cos(a) * f.r;
          const y = f.y + Math.sin(a) * f.r;
          if (i === 0) ctx.moveTo(px(x), px(y)); else ctx.lineTo(px(x), px(y));
        }
        ctx.closePath();
        ctx.stroke();
        ctx.fillStyle = rgba(col.deep, flash * live * 0.45);
        ctx.fill();
      }
      // A dull chip mark: the hit happened, it just did not get through.
      ctx.fillStyle = rgba(STEEL, flash * live * 0.7);
      ctx.fillRect(px(this.wall.x) - 1, px(this.wall.y) - 3, 2, 6);
    }
  }
}

/* --- HEAL: warm, upward, and contracting. Damage rings expand; a mend ring
 * closes in, which is what stops it reading as another kind of hit. --- */
class HealEffect extends Effect {
  build() {
    this.circle = { x: this.from.x, y: this.stage.ground - 1, rx: 16, ry: 5 };
  }

  _step(dt) {
    if (this.k > 0.2 && this.k < 0.75) {
      this.drip(dt, 70, (r) => {
        const a = r() * Math.PI * 2;
        this.motes.emit(this.circle.x + Math.cos(a) * this.circle.rx,
          this.circle.y + Math.sin(a) * this.circle.ry,
          (r() - 0.5) * 8, -34 - r() * 40, -18, 0.8, r() < 0.25 ? 2 : 1,
          r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _draw(ctx) {
    const col = this.colour;
    const ins = easeOut(this.ph(0, 0.26));
    const live = 1 - easeIn(this.ph(0.78, 1));
    const C = this.circle;

    // A rune circle inscribes itself on the ground, then feeds the column.
    ctx.lineWidth = 1;
    ctx.strokeStyle = rgba(col.key, live * ins * 0.9);
    ctx.beginPath();
    ctx.ellipse(px(C.x), px(C.y), C.rx * ins, C.ry * ins, 0, 0, Math.PI * 2);
    ctx.stroke();
    const turn = this.reducedMotion ? 0 : this.t * 0.8;
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI * 2 * i) / 6 + turn;
      drawGlyphStrip(ctx, C.x + Math.cos(a) * C.rx * ins - 1,
        C.y + Math.sin(a) * C.ry * ins - 2, 1, 991 + i * 37, col.key, live * ins * 0.8);
    }

    const col2 = this.ph(0.2, 0.7);
    if (col2 > 0) {
      const hgt = lerp(0, 40, easeOut(col2));
      for (let i = 0; i < 8; i++) {
        const p = i / 7;
        const w = Math.max(1, (1 - p) * 14);
        ctx.fillStyle = rgba(p < 0.4 ? col.hot : col.key, live * (1 - p) * 0.4);
        ctx.fillRect(px(C.x - w / 2), px(C.y - p * hgt), px(w), 3);
      }
    }

    // The mend: a ring that closes on the caster's chest, then a soft plus-free
    // rune flash. No medical iconography; this is a spellbook, not a clinic.
    const mend = this.ph(0.55, 0.86);
    if (mend > 0) {
      const r = lerp(26, 4, easeOut(mend));
      shockRing(ctx, this.from.x, this.from.y - 4, r, col.hot, (1 - mend) * live);
      const flash = arc(mend);
      drawGlyphStrip(ctx, this.from.x - 6, this.from.y - 8, 3, 4242, col.hot,
        flash * live * 0.95);
    }
  }
}

/* --- MISS: nothing connects. A pale arc passes through the target box and the
 * barrier never even lights. Short, quiet, and unmistakably a nil result. --- */
class MissEffect extends Effect {
  build() { this.lift = 18 + this.rand() * 8; }

  _draw(ctx) {
    const col = this.colour;
    const fly = this.ph(0.1, 0.7);
    const live = 1 - easeIn(this.ph(0.6, 1));
    if (fly <= 0) return;
    const e = easeOut(fly);
    const x = lerp(this.from.x + 8, this.to.x + 40, e);
    const y = lerp(this.from.y, this.to.y - 6, e) - Math.sin(Math.PI * e) * this.lift;
    ctx.fillStyle = rgba(col.key, live * 0.75);
    ctx.fillRect(px(x), px(y), 3, 2);
    ctx.fillStyle = rgba(col.hot, live * 0.5);
    ctx.fillRect(px(x) - 4, px(y), 4, 1);
    // Trail, so the eye can follow a shot that did nothing.
    for (let i = 1; i < 5; i++) {
      const p = clamp(e - i * 0.06, 0, 1);
      const tx = lerp(this.from.x + 8, this.to.x + 40, p);
      const ty = lerp(this.from.y, this.to.y - 6, p) - Math.sin(Math.PI * p) * this.lift;
      ctx.fillStyle = rgba(col.key, live * 0.3 * (1 - i / 5));
      ctx.fillRect(px(tx), px(ty), 2, 1);
    }
  }
}

/* ---------------- definitions and registry ----------------
 * Durations are the contract with the battle loop: the caller awaits them, and
 * `impactAt` is where it should apply the damage number and the sfx so the
 * numbers land on the hit rather than after it.
 *
 * Reduced-motion durations are shorter but never collapse to nothing — the
 * still frame still has to be on screen long enough to be seen. */

function defineEffect(spec, Ctor) {
  const def = {
    id: spec.id,
    family: spec.family,
    label: spec.label,
    colour: spec.colour,
    duration: spec.duration,
    reducedDuration: spec.reducedDuration,
    impactAt: spec.impactAt,
    /* --- the impact contract, shared by every effect ---
     * element      which motion law act one and act three are written in
     * shake/flash  magnitude of the advisory hints at the peak
     * hold         seconds the clock stalls on the hit; the weight of the blow
     * settle       fraction of the timeline the dissipation gets
     * debris       chunks and sparks thrown at reference power
     * wash         how much of the stage the additive light reaches
     * wind         strength of the shared wind-up, 0 for effects that are all
     *              wind-up already (PHOENIX gathers for nearly half a second)
     * impactWhere  'target' | 'caster' | 'wall' | 'none' */
    element: spec.element || 'force',
    shake: spec.shake === undefined ? 4 : spec.shake,
    flash: spec.flash === undefined ? 0.5 : spec.flash,
    hold: spec.hold === undefined ? 0.05 : spec.hold,
    settle: spec.settle === undefined ? 0.28 : spec.settle,
    holdAt: spec.holdAt === undefined ? spec.impactAt : spec.holdAt,
    debris: spec.debris === undefined ? 10 : spec.debris,
    wash: spec.wash === undefined ? 0.18 : spec.wash,
    wind: spec.wind === undefined ? 1 : spec.wind,
    windTo: spec.windTo === undefined ? spec.impactAt * 0.62 : spec.windTo,
    windDx: spec.windDx === undefined ? 10 : spec.windDx,
    impactWhere: spec.impactWhere || 'target',
    /* The frame the reduced-motion still holds. Usually the impact, but a slash
     * reads better a hair after it, once the arc is fully extended. */
    poseAt: spec.poseAt === undefined ? spec.impactAt : spec.poseAt,
    motes: spec.motes,
    sfx: spec.sfx,
    beats: [
      { k: 0, name: 'cast' },
      { k: spec.travelAt === undefined ? spec.impactAt * 0.55 : spec.travelAt, name: 'travel' },
      { k: spec.impactAt, name: 'impact' },
      { k: 1, name: 'end' },
    ],
  };
  return Object.freeze({
    id: def.id,
    family: def.family,
    label: def.label,
    colour: def.colour,
    element: def.element,
    duration: def.duration,
    reducedDuration: def.reducedDuration,
    impactAt: def.impactAt,
    sfx: def.sfx,
    /* opts: { stage, seed, colour, from, to, targetBox, boss, reducedMotion,
     *         duration, intensity, onImpact, onBeat } */
    create(opts = {}) { return new Ctor(def, opts); },
  });
}

export const SPELL_ANIMATIONS = Object.freeze({
  ORACLE: defineEffect({
    id: 'ORACLE', family: 'spell', label: 'ORACLE',
    colour: SPELL_COLOURS.ORACLE,
    duration: 1.5, reducedDuration: 0.8, impactAt: 0.56, poseAt: 0.6,
    motes: 84, sfx: { cast: 'spell', impact: 'crit' },
    /* An eye in a turning bezel, so: arcane. The wind-up is offset high and
     * forward because the eye, not the caster's hand, is where it gathers. */
    element: 'arcane', shake: 5, flash: 0.55, hold: 0.055, settle: 0.3,
    debris: 9, wash: 0.16, windDx: 14, windTo: 0.3,
  }, OracleEffect),

  REVEAL_PATH: defineEffect({
    id: 'REVEAL_PATH', family: 'spell', label: 'REVEAL PATH',
    colour: SPELL_COLOURS.REVEAL_PATH,
    duration: 1.6, reducedDuration: 0.85, impactAt: 0.66, poseAt: 0.72,
    motes: 76, sfx: { cast: 'spell', impact: 'unlock' },
    /* A lattice is a crystal. Frost's snap-then-stop is the same motion the
     * edges already make, which is why this one agrees with itself. */
    element: 'frost', shake: 5, flash: 0.5, hold: 0.06, settle: 0.3,
    debris: 14, wash: 0.14, windTo: 0.22,
  }, RevealPathEffect),

  VISION: defineEffect({
    id: 'VISION', family: 'spell', label: 'VISION',
    colour: SPELL_COLOURS.VISION,
    duration: 1.9, reducedDuration: 0.9, impactAt: 0.52, poseAt: 0.7,
    motes: 64, sfx: { cast: 'spell', impact: 'shrine' },
    /* A wall of light crossing the whole stage is a pressure front, so force:
     * staggered rings and dust that stays low. It lands softer than the rest
     * because VISION explains rather than punishes. */
    element: 'force', shake: 4, flash: 0.4, hold: 0.05, settle: 0.34,
    debris: 8, wash: 0.22, wind: 0.7, windTo: 0.18,
  }, VisionEffect),

  PSEUDOSIGHT: defineEffect({
    id: 'PSEUDOSIGHT', family: 'spell', label: 'PSEUDOSIGHT',
    colour: SPELL_COLOURS.PSEUDOSIGHT,
    duration: 1.7, reducedDuration: 0.9, impactAt: 0.74, poseAt: 0.5,
    motes: 72, sfx: { cast: 'spell', impact: 'unlock' },
    /* Rune rows read off a page: arcane, and the counter-rotating rings at the
     * impact are the same figure the page's margin runes belong to. */
    element: 'arcane', shake: 5, flash: 0.5, hold: 0.055, settle: 0.26,
    debris: 10, wash: 0.15, wind: 0.8, windTo: 0.2,
  }, PseudosightEffect),

  CODE_FRAGMENT: defineEffect({
    id: 'CODE_FRAGMENT', family: 'spell', label: 'CODE FRAGMENT',
    colour: SPELL_COLOURS.CODE_FRAGMENT,
    duration: 1.6, reducedDuration: 0.85, impactAt: 0.62, poseAt: 0.5,
    motes: 96, sfx: { cast: 'spell', impact: 'crit' },
    /* Shards that are simply *there* on the frame they arrive: lightning. The
     * strobe on the impact is the same beat the shards lock in on. */
    element: 'lightning', shake: 7, flash: 0.6, hold: 0.05, settle: 0.3,
    debris: 16, wash: 0.18, windTo: 0.16,
  }, CodeFragmentEffect),

  PHOENIX: defineEffect({
    id: 'PHOENIX', family: 'spell', label: 'PHOENIX',
    colour: SPELL_COLOURS.PHOENIX,
    duration: 3.0, reducedDuration: 1.2, impactAt: 0.82, poseAt: 0.74,
    travelAt: 0.46, motes: 208, sfx: { cast: 'levelup', impact: 'victory' },
    /* The only warm effect in the game, and the heaviest thing in it: the
     * longest hold, the widest wash, the most debris. Its own gather already
     * runs for the best part of a second, so the shared wind-up only tops it
     * up rather than competing with it. */
    element: 'fire', shake: 11, flash: 0.85, hold: 0.11, settle: 0.2,
    debris: 22, wash: 0.34, wind: 0.4, windDx: 0, windTo: 0.3,
  }, PhoenixEffect),
});

export const ATTACK_ANIMATIONS = Object.freeze({
  [DAMAGE_KIND.HIT]: defineEffect({
    id: 'hit', family: 'attack', label: 'HIT',
    colour: ATTACK_COLOURS.hit,
    duration: 0.55, reducedDuration: 0.3, impactAt: 0.38, poseAt: 0.5,
    motes: 48, sfx: { cast: null, impact: 'hit' },
    /* Kinetic and cheap. A three-frame hold is enough to feel and short enough
     * that ten of these in a row still resolve as ten separate events. */
    element: 'force', shake: 3, flash: 0.5, hold: 0.035, settle: 0.5,
    debris: 6, wash: 0.08, windTo: 0.24,
  }, HitEffect),

  [DAMAGE_KIND.CRIT]: defineEffect({
    id: 'crit', family: 'attack', label: 'CRITICAL',
    colour: ATTACK_COLOURS.crit,
    duration: 1.25, reducedDuration: 0.55, impactAt: 0.4, poseAt: 0.46,
    motes: 120, sfx: { cast: 'tick', impact: 'crit' },
    /* The rarest thing the player sees, so it gets the second-longest hold in
     * the game and a full-strength flash. Lightning because a weakness strike
     * should arrive already finished. */
    element: 'lightning', shake: 10, flash: 0.7, hold: 0.1, settle: 0.45,
    debris: 20, wash: 0.3, windTo: 0.2,
  }, CritEffect),

  [DAMAGE_KIND.RESIST]: defineEffect({
    id: 'resist', family: 'attack', label: 'RESIST',
    colour: ATTACK_COLOURS.resist,
    duration: 0.75, reducedDuration: 0.4, impactAt: 0.5, poseAt: 0.58,
    motes: 40, sfx: { cast: null, impact: 'tick' },
    /* Lands on the barrier, not on the enemy, and barely shakes the camera:
     * the whole message is that nothing got through. Frost's dead stop is
     * exactly the right motion for a blow that stops. */
    element: 'frost', shake: 1.5, flash: 0.22, hold: 0.045, settle: 0.34,
    debris: 7, wash: 0.05, impactWhere: 'wall', windTo: 0.24,
  }, ResistEffect),

  [DAMAGE_KIND.HEAL]: defineEffect({
    id: 'heal', family: 'attack', label: 'HEAL',
    colour: ATTACK_COLOURS.heal,
    duration: 0.95, reducedDuration: 0.45, impactAt: 0.6, poseAt: 0.68,
    motes: 56, sfx: { cast: null, impact: 'unlock' },
    /* Resolves on the caster and never shakes the camera. No hold either — a
     * hold frame says "that hurt", and this is the one effect that must not. */
    element: 'arcane', shake: 0, flash: 0.3, hold: 0, settle: 0.3,
    debris: 6, wash: 0.12, impactWhere: 'caster', wind: 0.55, windDx: 0,
    windTo: 0.2,
  }, HealEffect),

  [DAMAGE_KIND.MISS]: defineEffect({
    id: 'miss', family: 'attack', label: 'MISS',
    colour: ATTACK_COLOURS.miss,
    duration: 0.6, reducedDuration: 0.3, impactAt: 0.4, poseAt: 0.45,
    motes: 0, sfx: { cast: null, impact: 'tick' },
    /* Nothing connected, so nothing lands: no wind-up figure, no flash, no
     * shake, no light, no debris. The absence is the information. */
    element: 'force', shake: 0, flash: 0, hold: 0, debris: 0, wash: 0,
    wind: 0, impactWhere: 'none',
  }, MissEffect),
});

/* Every effect in one map, for tooling and for the effect gallery. */
export const EFFECT_INDEX = Object.freeze({
  ...SPELL_ANIMATIONS, ...ATTACK_ANIMATIONS,
});

/* The one call sites should use. `kind` is a spell id ('ORACLE') or a damage
 * kind ('crit'), in any case. An unknown kind returns a normal hit flagged
 * `fallback`, because a battle that throws mid-sequence is worse than a battle
 * that shows the wrong sparkle. */
export function createEffect(kind, opts = {}) {
  const raw = kind === null || kind === undefined ? '' : String(kind);
  const spell = SPELL_ANIMATIONS[raw.toUpperCase()];
  if (spell) return spell.create(opts);
  const attack = ATTACK_ANIMATIONS[raw.toLowerCase()];
  if (attack) return attack.create(opts);
  const fallback = ATTACK_ANIMATIONS[DAMAGE_KIND.HIT].create(opts);
  fallback.fallback = true;
  return fallback;
}

/* How long a kind runs, without building it. For callers that schedule the
 * damage number or the next trial against the clock. */
export function effectDuration(kind, { reducedMotion = false } = {}) {
  const raw = kind === null || kind === undefined ? '' : String(kind);
  const def = SPELL_ANIMATIONS[raw.toUpperCase()]
    || ATTACK_ANIMATIONS[raw.toLowerCase()]
    || ATTACK_ANIMATIONS[DAMAGE_KIND.HIT];
  return reducedMotion ? def.reducedDuration : def.duration;
}

/* Which motion law a kind is drawn in, without building it. For a caller that
 * wants to pick an sfx or a damage-number colour that agrees with the art. */
export function elementOf(kind) {
  const raw = kind === null || kind === undefined ? '' : String(kind);
  const def = SPELL_ANIMATIONS[raw.toUpperCase()]
    || ATTACK_ANIMATIONS[raw.toLowerCase()];
  return def ? def.element : ATTACK_ANIMATIONS[DAMAGE_KIND.HIT].element;
}

/* Rasterise everything an effect will need before the fight starts. A cold
 * cache costs a few canvases on the first cast, which is exactly the frame the
 * player is watching; this moves that cost to the loading beat. */
export function warmCache(kinds, opts = {}) {
  const list = Array.isArray(kinds) && kinds.length
    ? kinds
    : Object.keys(EFFECT_INDEX);
  const made = makeCanvas(STAGE_GEOM.w, STAGE_GEOM.h);
  if (!made) return 0;
  const before = canvasCache.size;
  for (const kind of list) {
    const e = createEffect(kind, opts);
    /* Twelve samples across the whole effect touches every cached tile without
     * paying for a full playthrough. */
    for (let i = 0; i <= 12; i++) {
      e.t = (e.duration * i) / 12;
      e.rawK = clamp(e.t / e.duration, 0, 1);
      e.k = e._warp(e.rawK);
      /* _paint, not _draw: the shared wind-up and impact layer rasterise rune
       * tiles of their own, and warming only the subclass art would leave the
       * frame of the hit — the one frame the player is actually watching —
       * paying for its canvases at the worst possible moment. */
      try { e._paint(made.ctx); } catch (err) { /* a cold warm-up is not fatal */ }
    }
    e.cancel();
  }
  return canvasCache.size - before;
}

/* ---------------- fx.js adapter ----------------
 * BattleFX keeps its effects in one array and drives them with
 *
 *     e.t += dt;  if (e.t >= e.dur) drop;   ...   e.draw(ctx, k, e.t)
 *
 * so an animator only has to look like that from the outside. The accessor
 * turns the `t += dt` the loop already does into the step() this module wants,
 * which means BattleFX needs no change to its update or draw pass at all.
 *
 *     this.effects.push(toFxEffect(createEffect('ORACLE', { ... })));
 */
export function toFxEffect(effect) {
  return {
    effect,
    dur: effect.duration,
    get t() { return effect.t; },
    set t(v) { effect.step(Math.max(0, v - effect.t)); },
    draw(ctx) { effect.draw(ctx); },
  };
}
