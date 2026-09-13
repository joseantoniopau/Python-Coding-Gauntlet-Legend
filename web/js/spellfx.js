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
 *   e.draw(ctx)      paint in logical stage units (256x224, ground at 175)
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

export const SPELLFX_VERSION = '1.3.0';   // 1.3: bodies re-scaled to the 256x224 raster

/* Logical stage units. Same numbers as fx.js STAGE; overridable per effect.
 * Moved with the raster to 256x224 (docs/08-art-direction §A). safeTop/safeH
 * are carried so an effect that wants to know where the player can actually see
 * does not have to guess: rows 24..199 are the promise, the rest is overscan. */
export const STAGE_GEOM = Object.freeze({
  w: 256, h: 224, safeTop: 24, safeH: 176, ground: 175, heroX: 64, enemyX: 184,
});

/* ---------------- THE BODY SCALE ----------------
 * The raster move (c8167b9) took the frame from 192x128 to 256x224 and moved
 * the eleven anchors that say WHERE an effect starts and lands. It did not move
 * the geometry that says HOW BIG any of it is, so every effect kept drawing at
 * its old absolute size inside a frame that had grown. Measured on the raster,
 * union bounding box of each subclass's own art with the shared layers off:
 * ORACLE fell from 78.9% of frame height to 62.1%, CODE_FRAGMENT from 63.3% to
 * 41.1%, a plain hit from 29.7% to 17.0%, and the two shared signatures —
 * windup and impact, which every one of the eleven wears — came out 1.00x wide.
 * Not smaller than they should be: not grown at all.
 *
 * THE FACTOR IS 4/3 IN BOTH AXES, AND THE VERTICAL ONE IS NOT 1.75.
 *
 *   width    192 -> 256 is 4/3, and all of it is on screen in both rasters.
 *   height   224/128 is 1.75, and that number is a trap. §A-3 of
 *            docs/08-art-direction.md says the safe area is 256x176, rows
 *            24..199, and that rows 0..23 and 200..223 are overscan where
 *            "nothing load-bearing may live". fitBattleStage() fits the 176.
 *            So the VISIBLE frame went 128 -> 176 rows: 1.375, which is 4/3
 *            within three per cent. An effect scaled 1.75 vertically would be
 *            27% taller than the fraction it used to hold and would put its top
 *            in the overscan the player is not promised. ORACLE is the proof by
 *            arithmetic: it held 78.9% of the old 128 rows, and 78.9% of the
 *            new 224 is 177 rows — one row MORE than the whole safe area.
 *
 * WHERE THE EXTRA ROOM ACTUALLY IS, because it is not spread evenly. The ground
 * line moved 100 -> 175 while the safe top moved 0 -> 24, so the visible
 * headroom above the ground went 100 -> 151 rows: 1.51x, not 1.375x. That
 * surplus belongs to the things that RISE from the ground, and it is spent
 * there and nowhere else — PHOENIX's ignition column at 1.41x, fire's impact
 * plume at 1.5x reach, the lightning strike's ceiling — each still clamped
 * clear of row 24.
 *
 * WHAT DOES NOT SCALE: line weight. The logical pixel did not get finer, the
 * frame got bigger, so a 1px rune outline is still a 1px rune outline and the
 * 3x5 micro-font is still 3x5. Extents scale; detail does not. What the extra
 * 1.9x of area buys instead is STEPS — more quills on the wing, more tongues in
 * a plume, four bands of falloff in a light disc where there were three, ten
 * runes on a bezel where there were eight — because a ring 4/3 longer drawn
 * with the same eight steps is a ring with gaps in it. */
/* Nothing below multiplies by this — every extent in this file is authored at
 * scale rather than computed from a factor, because a file that multiplies at
 * draw time draws on half-pixels and half-pixel art is soft art (see px()).
 * It is exported so the NEXT raster move can find what this one used, instead
 * of having to re-derive it from the commit that broke the last one. */
/* AND 176 IS THE PROMISE, NOT THE DELIVERY — which matters to whoever moves
 * the raster next, because it is the number that looks like it came off the
 * renderer and did not. fx.js fits `px` to safeH but centres the WHOLE 224-row
 * raster (`oy = round((canvasH - STAGE.h * px) / 2)`), so the canvas shows
 * every row that lands on it, not the 176 it was sized for. Measured live, in
 * a browser, at all four window sizes the game actually opens at:
 *
 *   1280x800, 1440x940    canvas 526x366  px 2  oy -41   rows  21..203  183
 *   1600x1000, 1920x1080  canvas 782x542  px 3  oy -65   rows  22..202  181
 *
 * So the band is 181-183 rows and has never once been 176. The art grew 1.333
 * against a window that grew 183/128 = 1.43, which costs every BODY here two
 * to five points of the height fraction it used to hold — measured, worst
 * first: PSEUDOSIGHT -3.0, heal -2.8, resist -1.6, miss -0.9. Against the 176
 * promised rows the same bodies are within a point or two of where they were.
 *
 * THIS IS A COMPOSITION CALL AND IT IS DELIBERATE. 4/3 keeps the art inside the
 * rows the player is PROMISED, and the extra five to seven rows the canvas
 * happens to deliver are overscan that a different window, a different dpr or a
 * different chrome takes straight back. Art placed in them is art that exists
 * on one monitor. Do not re-derive 1.4375 from the delivered band: it would put
 * the top of every rising effect in rows nothing guarantees. */
export const SPELLFX_BODY_SCALE = Object.freeze({
  fromRaster: '192x128', toRaster: '256x224', toSafeArea: '256x176',
  x: 4 / 3,              // 192 -> 256, all of it visible in both
  y: 4 / 3,              // 128 -> 176 PROMISED rows is 1.375; NOT 224/128
  groundRise: 1.51,      // 100 -> 151 visible rows above the ground line
  /* What the canvas actually hands over, measured rather than derived. Here so
   * the next raster move starts from the delivery and not from the promise. */
  deliveredRows: '181-183',
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
 *
 * Speeds and gravities carry the 4/3 of the body scale. A mote's velocity is an
 * extent per second, and under x' = 4/3 x, v' = 4/3 v, g' = 4/3 g the same
 * trajectory comes out at the same times, 4/3 bigger — which is the whole
 * requirement. Lifetimes, spreads and spins are angles and seconds and do not.
 */
export const ELEMENTS = Object.freeze({
  fire: Object.freeze({
    id: 'fire', radial: false, dir: -Math.PI / 2, tangent: 0, spread: 1.5,
    speed: 40, speedVar: 69, gravity: -56, life: 0.52, lifeVar: 0.50,
    spin: 6.5, chunk: 0.22, holdScale: 1.00,
  }),
  frost: Object.freeze({
    id: 'frost', radial: true, dir: 0, tangent: 0, spread: 0.5,
    speed: 61, speedVar: 75, gravity: 307, life: 0.26, lifeVar: 0.20,
    spin: 0, chunk: 0.50, holdScale: 1.25,
  }),
  arcane: Object.freeze({
    id: 'arcane', radial: true, dir: 0, tangent: 1.35, spread: 0.5,
    speed: 27, speedVar: 37, gravity: 8, life: 0.70, lifeVar: 0.55,
    spin: 12, chunk: 0.12, holdScale: 0.95,
  }),
  lightning: Object.freeze({
    id: 'lightning', radial: true, dir: 0, tangent: 0, spread: 0.8,
    speed: 173, speedVar: 173, gravity: 560, life: 0.13, lifeVar: 0.10,
    spin: 0, chunk: 0.22, holdScale: 0.75,
  }),
  force: Object.freeze({
    id: 'force', radial: true, dir: 0, tangent: 0, spread: 0.3,
    speed: 77, speedVar: 67, gravity: 227, life: 0.38, lifeVar: 0.28,
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
    const xlo = -37, xhi = this.bw + 37, ylo = -53, yhi = this.bh + 32;
    for (let i = 0; i < this.cap; i++) {
      if (!this.alive[i]) continue;
      this.t[i] += dt;
      if (this.t[i] >= this.life[i]) { this.alive[i] = 0; continue; }
      this.vy[i] += this.g[i] * dt;
      this.x[i] += this.vx[i] * dt;
      this.y[i] += this.vy[i] * dt;
      if (this.spin[i]) this.vx[i] += Math.sin(this.t[i] * this.spin[i]) * 32 * dt;
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
  /* Four bands now, not three. A wider beam with a hard shoulder reads as a
   * painted stripe; the outer `deep` halo is what turns the same silhouette
   * back into light without spending a sixteenth colour. */
  ctx.fillStyle = rgba(col.deep, alpha * 0.3);
  ctx.fillRect(0, px(-w / 2) - 3, px(len), px(w) + 6);
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
  ctx.arc(px(cx), px(cy), radius - 4, 0, Math.PI * 2);
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
    const segs = 4;                    // one more articulation per arm: a crack
                                       // 4/3 longer at three segments is a bent
                                       // line, at four it is a crack
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
function lightDisc(ctx, cx, cy, radius, colour, alpha, bands = 4) {
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
  for (let i = 3; i >= 1; i--) {
    const w = Math.max(1, px((rx * i) / 3));
    const h = Math.max(1, px((rx * i) / 9));
    ctx.fillStyle = rgba(colour, alpha * (1 - (i - 1) / 3));
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
  const R = (21 + 12 * power) * (1 - easeOut(p) * 0.68);
  ctx.lineWidth = 1;

  if (el.id === 'fire') {
    // Embers spiral UP into the hand on a golden angle, and a tongue licks off
    // it. Nothing in fire falls, and that is the whole tell.
    for (let i = 0; i < 9; i++) {
      const a = i * 2.39996 + (quiet ? 0 : t * 4.2);
      const rr = R * (1 - (i / 9) * 0.5);
      const ex = cx + Math.cos(a) * rr;
      const ey = cy + Math.sin(a) * rr * 0.55 - p * 15 - (i % 3);
      const s = 1 + (i & 1);
      ctx.fillStyle = rgba(i < 4 ? col.hot : i < 6 ? col.key : tn.mid,
        alpha * (0.45 + 0.55 * p));
      ctx.fillRect(px(ex), px(ey), s, s);
    }
    const h = 5 + 17 * p * power;
    for (let i = 0; i < 7; i++) {
      const q = i / 6;
      const w = Math.max(1, px((1 - q) * 7 * power));
      const wob = quiet ? 0 : Math.sin(t * 11 - q * 3) * (1.3 + 2.7 * q);
      ctx.fillStyle = rgba(q < 0.35 ? col.hot : q < 0.8 ? col.key : tn.mid,
        alpha * (1 - q * 0.5));
      ctx.fillRect(px(cx - w / 2 + wob), px(cy - q * h), w, 3);
    }
    return;
  }

  if (el.id === 'frost') {
    // Six spikes grow inward on fixed bearings and then hold dead still. No
    // rotation anywhere: frost is the element that stops.
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI * 2 * i) / 6 + 0.26;
      const dx = Math.cos(a), dy = Math.sin(a);
      for (let s = 0; s < 5; s++) {
        const q = s / 4;
        const rr = lerp(R, R * 0.3, easeOut(p) * q + q * 0.4);
        const w = Math.max(1, px((1 - q) * 4));
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
    runeRing(ctx, cx, cy, Math.max(5, R), 8, spin, col, alpha * 0.85);
    runeRing(ctx, cx, cy, Math.max(4, R * 0.55), 5, -spin * 1.4, col, alpha * 0.5);
    return;
  }

  if (el.id === 'lightning') {
    // A gap-arc that stutters between two contacts. It does not travel, it
    // reappears; the strobe is doing all the work.
    const tick = quiet ? 3 : (t * 22) | 0;
    const on = quiet ? 1 : (tick % 3 === 2 ? 0.18 : 1);
    ctx.strokeStyle = rgba(col.hot, alpha * on);
    boltPath(ctx, cx - R, cy - R * 0.5, cx + R * 0.4, cy + R * 0.35,
      seed + tick, 7 + 5 * power, 7);
    ctx.fillStyle = rgba(col.hot, alpha * on);
    ctx.fillRect(px(cx - R) - 1, px(cy - R * 0.5) - 1, 3, 3);
    ctx.fillRect(px(cx + R * 0.4) - 1, px(cy + R * 0.35) - 1, 3, 3);
    return;
  }

  // force: a compression. A ring closes with eight inward ticks riding it, and
  // the ground under it darkens before anything has been thrown.
  const r = Math.max(2, R);
  shockRing(ctx, cx, cy, r, col.key, alpha * 0.8);
  for (let i = 0; i < 10; i++) {
    const a = (Math.PI * 2 * i) / 10;
    const dx = Math.cos(a), dy = Math.sin(a);
    const rr = r + 7 * (1 - easeOut(p));
    // The tick's own trail, one step down the ramp, so the eye can see which
    // way it is travelling before the ring has finished closing.
    ctx.fillStyle = rgba(tn.mid, alpha * (0.3 + 0.4 * p));
    ctx.fillRect(px(cx + dx * (rr + 4)), px(cy + dy * (rr + 4)), 2, 2);
    ctx.fillStyle = rgba(col.hot, alpha * (0.4 + 0.6 * p));
    ctx.fillRect(px(cx + dx * rr), px(cy + dy * rr), 2, 2);
  }
}

/* ACT TWO INTO ACT THREE. The impact signature: what the element does to the
 * place it landed on, and how that dies down. `fall` is the whole envelope, so
 * a caller that wants nothing drawn passes zero. */
function impactSignature(ctx, el, cx, cy, p, t, col, tn, fall, power, seed, groundY, quiet,
  ceilY) {
  if (!(fall > 0.004)) return;
  ctx.lineWidth = 1;
  const reach = 20 + 32 * power;
  /* The row above which nothing load-bearing may be drawn: the caller passes
   * the stage's own safe top. Lightning is the one branch that reaches for the
   * ceiling, and on the old 128-row frame it clamped at a literal 3. */
  const ceil = ceilY === undefined ? 3 : ceilY;

  if (el.id === 'fire') {
    // Up, and it keeps going up. Tongues climb and narrow; the ring that
    // leaves the point rises off the floor instead of lying on it.
    /* 1.5, not 1.3: fire is the branch that spends the extra ground headroom
     * the raster move opened (100 visible rows above the ground line became
     * 151). It is the only reach in this painter that goes past 4/3. */
    const h = Math.min(reach * 1.5 * easeOut(p), Math.max(8, cy - ceil));
    for (let i = 0; i < 12; i++) {
      const q = i / 11;
      const w = Math.max(1, px((1 - q) * (7 + 12 * power) * (0.6 + 0.4 * noise(seed + i, 3))));
      const wob = quiet ? 0 : Math.sin(q * 7 + t * 10) * (2.7 + 2.7 * q);
      ctx.fillStyle = rgba(q < 0.3 ? col.hot : q < 0.7 ? col.key : tn.mid,
        fall * (1 - q * 0.5));
      ctx.fillRect(px(cx - w / 2 + wob), px(cy - q * h), w, 4);
    }
    shockRing(ctx, cx, cy - h * 0.3, Math.max(1, reach * easeOut(p) * 0.8),
      col.key, fall * 0.7);
    return;
  }

  if (el.id === 'frost') {
    // One stab outward, frozen at a third of the window, then the crust cracks.
    // The stillness in the middle of the effect is the identity.
    const grow = easeOut(clamp(p / 0.34, 0, 1));
    for (let i = 0; i < 10; i++) {
      const a = (Math.PI * 2 * i) / 10 + 0.19;
      const dx = Math.cos(a), dy = Math.sin(a);
      const len = reach * grow * (0.55 + 0.45 * noise(seed + i, 11));
      for (let s = 0; s < 6; s++) {
        const q = s / 5;
        const w = Math.max(1, px((1 - q) * 5));
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
    if (p > 0.34) cracks(ctx, cx, cy, seed + 17, 6, reach * 0.5, col.key, fall * 0.7, 1);
    return;
  }

  if (el.id === 'arcane') {
    // Two rune rings counter-rotate around a diamond that hangs still. The
    // figure turns for as long as it exists and never travels.
    const spin = quiet ? 0 : t * 5.2;
    const open = 0.35 + easeOut(p) * 0.8;
    runeRing(ctx, cx, cy, Math.max(5, reach * 0.42 * open), 8, spin, col, fall * 0.9);
    runeRing(ctx, cx, cy, Math.max(5, reach * 0.8 * open), 5, -spin * 0.65, col, fall * 0.55);
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
    /* 1.5 like fire, and for the same reason, but clamped to the safe top
     * rather than to a literal: a strike whose head is in the overscan is a
     * strike the player is not promised to see arrive. */
    const top = Math.max(ceil, cy - reach * 1.5);
    ctx.strokeStyle = rgba(col.hot, a);
    boltPath(ctx, cx, top, cx, cy, seed + tick, 11 + 7 * power, 9);
    ctx.strokeStyle = rgba(col.key, a * 0.75);
    for (let b = 0; b < 4; b++) {
      const q = 0.26 + b * 0.18;
      const ang = -Math.PI / 2 + (noise(seed + tick, b * 13) - 0.5) * 2.6;
      const sy = lerp(top, cy, q);
      boltPath(ctx, cx, sy, cx + Math.cos(ang) * reach * 0.9,
        sy + Math.sin(ang) * reach * 0.5, seed + tick * 7 + b, 6, 4);
    }
    cracks(ctx, cx, cy, seed + tick, 7, reach * 0.7, col.hot, a * 0.7, 1);
    return;
  }

  // force: one pressure front. Three rings leave on a stagger and the dust
  // stays on the floor, because force pushes out rather than up.
  for (let i = 0; i < 4; i++) {
    const span = Math.max(0.01, 1 - i * 0.16);
    const q = clamp(p - i * 0.16, 0, 1) / span;
    if (q <= 0) continue;
    shockRing(ctx, cx, cy, Math.max(1, reach * 1.5 * easeOut(q)),
      i === 0 ? col.hot : col.key, fall * (1 - q) * (1 - i * 0.22));
  }
  const spread = reach * 1.7 * easeOut(p);
  const gy = px(Math.min(groundY - 1, cy + 5));
  for (let d = 0; d < 2; d++) {
    const dir = d ? 1 : -1;
    for (let i = 0; i < 5; i++) {
      const q = i / 4;
      const x = cx + dir * spread * (0.35 + q * 0.65);
      const w = Math.max(1, px(5 * (1 - q) * power));
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
      safeTop: st.safeTop === undefined ? STAGE_GEOM.safeTop : st.safeTop,
      safeH: st.safeH === undefined ? STAGE_GEOM.safeH : st.safeH,
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
      y: o.from && o.from.y !== undefined ? o.from.y : S.ground - 27,
    };
    this.to = {
      x: o.to && o.to.x !== undefined ? o.to.x : S.enemyX,
      y: o.to && o.to.y !== undefined ? o.to.y : S.ground - 40,
    };
    /* Bounding box of the thing being hit, for a caller that does not pass one
     * — and fx.js does not. The two defaults track what the stage ACTUALLY
     * blits, which is the only thing that makes the hit flash land on the
     * creature rather than beside it:
     *
     *   mob   24x24 rig at FIGURE_SCALE, 3 -> 4 with the raster: 72 -> 96
     *         logical. 36x46 was 50% and 64% of the old blit, so 48x62 is the
     *         same judgement on the new one. Straight 4/3.
     *   boss  64x64 art at BOSS_STAGE_SCALE, 1.5 -> 2: 72 -> 128 logical. That
     *         rung grew 1.78x, not 4/3, so 60x68 at the same 83%/94% of the
     *         blit is 104x120. Scaling this one by 4/3 would have left the box
     *         inside a boss that had outgrown it. */
    const bw = o.targetBox && o.targetBox.w ? o.targetBox.w : (o.boss ? 104 : 48);
    const bh = o.targetBox && o.targetBox.h ? o.targetBox.h : (o.boss ? 120 : 62);
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
        this._emitElement(r, P.x + (r() - 0.5) * 13, P.y + (r() - 0.5) * 16, 1);
      }
    }
    const settle = Math.max(0.06, d.settle);
    if (this.k < a + settle) {
      const q = 1 - (this.k - a) / settle;
      this.drip(dt, 120 * q * q * this.power, this._tailEmit);
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
      this.motes.emitChunk(x, y, Math.cos(a) * sp * 0.7, Math.sin(a) * sp * 0.7 - 19,
        Math.abs(el.gravity) * 1.4 + 67, life * 1.7, 2 + ((r() * 3) | 0), c, el.spin);
    } else {
      /* Sparks are the one place detail DOES move with the raster, and the
       * reason is the screen and not the frame: the launcher's window dropped
       * from scale 3 to scale 2 with the raster, so a 1px spark went from three
       * device pixels to two. The mix shifts toward 2px rather than the size
       * scaling — a 1.33px spark is not a thing this grid can draw. */
      this.motes.emit(x, y, Math.cos(a) * sp, Math.sin(a) * sp, el.gravity, life,
        r() < 0.45 ? 2 : 1, c, el.spin);
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
      this._emitElement(r, this.hitAt.x + (r() - 0.5) * 16,
        this.hitAt.y + (r() - 0.5) * 19, 0.6);
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
    lightDisc(ctx, x, y, (9 + 12 * this.power) * w, this.tone.dim, a * 0.34, 3);
    groundPool(ctx, x, this.stage.ground, (12 + 15 * this.power) * w,
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

    /* The hit flash.
     *
     * THIS USED TO BE A HARD WHITE RECTANGLE, and at the old raster it was a
     * small one. One flat additive fillRect over the target box plus a 1px
     * frame around it drew a pale SQUARE standing on the enemy for five frames
     * of every crit and every spell impact — visible in a contact sheet of the
     * old build too, and 4/3 more visible now the box is bigger. A creature is
     * not a rectangle and neither is the light landing on it.
     *
     * So: a banded additive disc over the middle of the box, which has no
     * corners at all and brightens the creature the way every other light in
     * this file does; and corner ticks instead of a frame, the same survey-
     * bracket idiom VISION's x-ray already uses. The silhouette pop the frame
     * was there for is drawn properly by fx.js, which flashes the enemy's real
     * alpha mask — this never needed to draw a box to do it.
     *
     * Tried first and rejected by looking at it: three inset bands. Nested
     * rectangles with visible steps are still nested rectangles. */
    const hf = this._targetFlashAt(this.k);
    if (hf > 0.01 && d.impactWhere === 'target') {
      const b = this.box;
      ctx.globalCompositeOperation = 'lighter';
      lightDisc(ctx, b.x + b.w / 2, b.y + b.h * 0.46,
        Math.max(b.w, b.h) * 0.52, col.hot, hf * 0.42, 4);
      ctx.globalCompositeOperation = prevOp;
      ctx.fillStyle = rgba(col.hot, hf * 0.9);
      const tick = 7;
      for (let sx = 0; sx < 2; sx++) {
        for (let sy = 0; sy < 2; sy++) {
          const cx = sx ? px(b.x + b.w) - tick : px(b.x) - 1;
          const cy = sy ? px(b.y + b.h) : px(b.y) - 1;
          ctx.fillRect(cx, cy, tick + 1, 1);
          ctx.fillRect(sx ? px(b.x + b.w) : px(b.x) - 1,
            sy ? px(b.y + b.h) - tick : px(b.y) - 1, 1, tick + 1);
        }
      }
    }

    /* Additive light. Not a sprite of a glow: everything already on the canvas
     * under this gets brighter, which is the whole difference. */
    const lit = this._lightAt(this.k);
    if (lit > 0.01) {
      ctx.globalCompositeOperation = 'lighter';
      lightDisc(ctx, P.x, P.y, (16 + 32 * this.power) * (0.5 + p * 0.8),
        col.key, lit * 0.3, 4);
      groundPool(ctx, P.x, this.stage.ground,
        (19 + 35 * this.power) * (0.4 + p), col.key, lit * 0.24);
      if (d.wash > 0) {
        ctx.fillStyle = rgba(tn.dim, lit * d.wash * 0.5);
        ctx.fillRect(0, 0, this.stage.w, this.stage.h);
      }
      ctx.globalCompositeOperation = prevOp;
    }

    impactSignature(ctx, this.element, P.x, P.y, p, this.t, col, tn,
      fall, this.power, this.seed, this.stage.ground, this.reducedMotion,
      this.stage.safeTop + 2);
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
    this.eye = { x: lerp(this.from.x, this.to.x, 0.2), y: S.ground - 104 };
    this.aim = { x: this.to.x, y: this.box.y + this.box.h * 0.42 };
  }

  _step(dt) {
    const charge = this.ph(0.30, 0.52);
    if (charge > 0 && this.k < 0.52) {
      /* Sparks fall inward into the pupil: the eye is drawing the light in
       * before it spends it. */
      this.drip(dt, 60 * charge, (r) => {
        const a = r() * Math.PI * 2;
        const rad = 35 + r() * 19;
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
        const sp = 40 + r() * 93;
        this.motes.emit(this.aim.x + (r() - 0.5) * 13, this.aim.y + (r() - 0.5) * 16,
          Math.cos(a) * sp, Math.sin(a) * sp, 160, 0.5 + r() * 0.4,
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
    /* 34 -> 45 and 23 -> 31. The closed bezel was 11.5% of the old 192 frame
     * and had fallen to 8.6% of 256; 31 puts it back at 12.1%, and the ring is
     * carried on ten runes rather than eight because the same eight on a
     * circumference 4/3 longer left gaps between them. */
    const radius = lerp(45, 31, easeOut(gather)) + this.osc(3.1) * 0.8;
    runeRing(ctx, this.eye.x, this.eye.y, radius, 10,
      this.t * (this.reducedMotion ? 0 : 0.9), col, easeOut(gather) * live);

    // Lid aperture. A closed eye is a flat line; that line is also the wind-up.
    const lid = Math.max(0.04, easeOut(open) * (1 - easeIn(this.ph(0.82, 1))));
    const w = 40, h = 20 * lid;
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
      const irisR = Math.max(2, 7 * lid * (1 + fire * 0.5));
      ctx.fillStyle = rgba(col.key, live);
      ctx.beginPath();
      ctx.arc(px(this.eye.x), px(this.eye.y), irisR, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = rgba(col.ink, live);
      ctx.fillRect(px(this.eye.x) - 1, px(this.eye.y - irisR * 0.8), 2, px(irisR * 1.6));
      ctx.fillStyle = rgba(col.hot, live);
      ctx.fillRect(px(this.eye.x) + 2, px(this.eye.y) - 3, 2, 2);
    }

    // The beam: one shot, snapping wide then settling thin.
    if (this.k > 0.52 && this.k < 0.86) {
      const life = this.ph(0.52, 0.86);
      const wdt = lerp(12, 3, easeOut(Math.min(1, life * 1.8))) * this.power;
      const a = (1 - easeIn(life)) * 0.95;
      beam(ctx, this.eye.x, this.eye.y + 1, this.aim.x, this.aim.y, wdt, col, a);
      // Lens crossbar at the muzzle: the flare that says this is light, not paint.
      const flare = arc(this.ph(0.52, 0.66));
      ctx.fillStyle = rgba(col.hot, flare * 0.9);
      ctx.fillRect(px(this.eye.x - 19), px(this.eye.y), 37, 1);
      ctx.fillRect(px(this.eye.x), px(this.eye.y - 13), 1, 27);
    }

    // Impact: a ring and a bright column standing on the target.
    if (fire > 0) {
      const imp = this.ph(0.54, 0.84);
      shockRing(ctx, this.aim.x, this.aim.y, lerp(3, 40, easeOut(imp)),
        col.key, (1 - imp) * 0.9, 1);
      shockRing(ctx, this.aim.x, this.aim.y, lerp(3, 24, easeOut(imp)),
        col.hot, (1 - imp) * 0.7, 1);
      /* A third ring, inside the other two: three steps of falloff where the
       * old frame only had room to state two. */
      shockRing(ctx, this.aim.x, this.aim.y, lerp(3, 13, easeOut(imp)),
        col.hot, (1 - imp) * 0.45, 1);
      ctx.fillStyle = rgba(col.hot, (1 - imp) * 0.5);
      ctx.fillRect(px(this.aim.x) - 1, px(this.box.y), 3, px(this.box.h));
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
    /* Twelve nodes, not ten: the lattice spans 4/3 further across and 4/3
     * higher, and ten pips over that run is a dotted line rather than a graph.
     * The rows go 24/56 above the ground to 32/75 — the 4/3 that puts the upper
     * row back where it sat in the frame. */
    const n = 12;
    this.nodes = [];
    for (let i = 0; i < n; i++) {
      const p = i / (n - 1);
      /* A jittered two-row lattice rather than a line: a straight run of pips
       * reads as a path, and this spell is about structure. */
      const row = i % 2;
      this.nodes.push({
        x: lerp(this.from.x - 5, this.to.x + 3, p) + (this.rand() - 0.5) * 11,
        y: S.ground - (row ? 75 : 32) - this.rand() * 13,
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
          (r() - 0.5) * 27, -13 - r() * 27, 53, 0.4, 1, this.colour.key);
      });
    }
    if (this.k > 0.66 && this.k < 0.80) {
      this.drip(dt, 130, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 27 + r() * 80;
        this.motes.emit(this.to.x, this.to.y, Math.cos(a) * sp, Math.sin(a) * sp,
          80, 0.5, 1, r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _nodeSprite(ctx, x, y, alpha, hot) {
    const col = this.colour;
    /* 7x7 -> 9x9, and the extra two rows go into a cross with a lit centre
     * rather than a fatter blob: at 9 there is room for an ink frame, a key
     * arm and a hot core, which is the three-tone rule §3 asks of every piece
     * of art in this game and which a 7px pip could only hint at. */
    stamp(ctx, `rp:node9:${hot ? 1 : 0}:${col.key}`, 9, 9, (c) => {
      c.fillStyle = col.ink;
      c.fillRect(3, 0, 3, 9); c.fillRect(0, 3, 9, 3);
      c.fillStyle = col.deep;
      c.fillRect(4, 1, 1, 7); c.fillRect(1, 4, 7, 1);
      c.fillStyle = hot ? col.hot : col.key;
      c.fillRect(4, 2, 1, 5); c.fillRect(2, 4, 5, 1);
      c.fillStyle = col.hot;
      c.fillRect(4, 4, 1, 1);
    }, x - 4, y - 4, alpha);
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
      shockRing(ctx, this.to.x, this.to.y, lerp(5, 45, easeOut(imp)),
        col.key, (1 - imp) * 0.95);
      shockRing(ctx, this.to.x, this.to.y, lerp(5, 27, easeOut(imp)),
        col.hot, (1 - imp) * 0.6);
      const b = this.box, g = lerp(8, 0, easeOut(imp));
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
    this.spine = { x: b.x + b.w / 2, y0: b.y + 5, y1: b.y + b.h - 8 };
    this.ribs = [];
    /* The box grew, so the armature gets more ribs rather than longer gaps
     * between the same number of them. */
    const n = 5 + ((this.rand() * 4) | 0);
    for (let i = 0; i < n; i++) {
      const p = (i + 0.6) / (n + 0.2);
      this.ribs.push({
        y: lerp(this.spine.y0, this.spine.y1, p),
        w: (b.w * 0.22) + this.rand() * b.w * 0.2,
        drop: 1 + ((this.rand() * 4) | 0),
      });
    }
    this.core = { y: lerp(this.spine.y0, this.spine.y1, 0.34), r: 4 + this.rand() * 3 };
  }

  _step(dt) {
    if (this.k > 0.20 && this.k < 0.64) {
      const x = this._sweepX();
      this.drip(dt, 55, (r) => {
        this.motes.emit(x + (r() - 0.5) * 5, this.stage.ground - r() * 94,
          -27 - r() * 40, (r() - 0.5) * 27, 0, 0.45, 1,
          r() < 0.35 ? this.colour.hot : this.colour.key);
      });
    }
  }

  _sweepX() {
    return lerp(this.from.x - 27, this.stage.w + 21, easeInOut(this.ph(0.18, 0.66)));
  }

  _draw(ctx) {
    const col = this.colour;
    const S = this.stage;
    const rise = this.ph(0, 0.20);
    const fade = this.ph(0.84, 1);
    const live = 1 - easeIn(fade);
    const x = this._sweepX();
    const half = lerp(3, 15, easeOut(rise)) * this.power;

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
      for (let y = 0; y < S.h; y += 5) {
        const off = Math.sin((y * 0.4) + this.t * 8) * 2.7 * (this.reducedMotion ? 0 : 1);
        ctx.fillStyle = rgba(col.hot, a * 0.16);
        ctx.fillRect(px(x - half * 3 + off), y, px(half), 3);
        /* A second, fainter slice further back: the wall now has a trailing
         * gradient of two steps instead of one hard edge. */
        ctx.fillStyle = rgba(col.key, a * 0.09);
        ctx.fillRect(px(x - half * 5 - off), y, px(half * 0.7), 3);
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
      const g = 4;
      ctx.fillStyle = rgba(col.key, hold * 0.9);
      for (const sx of [-1, 1]) {
        for (const sy of [-1, 1]) {
          const cx = sx < 0 ? b.x - g : b.x + b.w + g - 1;
          const cy = sy < 0 ? b.y - g : b.y + b.h + g - 1;
          ctx.fillRect(px(cx - (sx < 0 ? 0 : 6)), px(cy), 7, 1);
          ctx.fillRect(px(cx), px(cy - (sy < 0 ? 0 : 6)), 1, 7);
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
    /* 52x58 -> 70x77: the 4/3 that puts the page back at 27% of the frame
     * width and 44% of the safe area's height, where it sat on the 192 frame.
     * The runes inside it stay 3x5. The micro-font is a font — a 4x6.67 glyph
     * is not a thing, and a page that is 4/3 bigger with the same rune size is
     * a page with MORE LINES ON IT, which is what a spellbook page opening
     * should look like anyway. Fourteen rows becomes eighteen. */
    this.page = {
      x: lerp(this.from.x, this.to.x, 0.34) - 35,
      y: S.ground - 112,
      w: 70, h: 77,
    };
    this.rows = [];
    const n = 18;
    for (let i = 0; i < n; i++) {
      this.rows.push({
        indent: (this.rand() * 3) | 0,
        cells: 5 + ((this.rand() * 9) | 0),
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
          (r() - 0.5) * 16, -24 - r() * 29, 0, 0.6, 1,
          r() < 0.3 ? this.colour.hot : this.colour.key);
      });
    }
    if (this.k > 0.70 && this.k < 0.84) {
      this.drip(dt, 110, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 24 + r() * 73;
        this.motes.emit(this.to.x, this.to.y, Math.cos(a) * sp, Math.sin(a) * sp,
          93, 0.5, 1, r() < 0.4 ? this.colour.hot : this.colour.key);
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
    ctx.fillRect(px(P.x + 5), px(y), 1, px(h));

    for (const row of this.rows) {
      // Wrapped scroll, so the page never runs out of text mid-read.
      let ry = y + h - 8 + row.y - scroll;
      while (ry < y - GLYPH_H) ry += this.scrollSpan;
      if (ry > y + h) continue;
      const dist = Math.abs(ry - readY);
      const lit = clamp(1 - dist / 19, 0, 1);
      const a = live * (0.28 + lit * 0.72);
      const rx = P.x + 9 + row.indent * 4;
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
    ctx.fillRect(px(P.x + 9 + cur * (P.w - 20)), px(readY), 2, GLYPH_H);
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
      ctx.fillRect(px(fx - 19), px(fy), 37, 1);
    }
    const imp = this.ph(0.74, 0.96);
    if (imp > 0) {
      shockRing(ctx, this.to.x, this.to.y, lerp(4, 40, easeOut(imp)), col.key, (1 - imp) * 0.9);
      runeRing(ctx, this.to.x, this.to.y, lerp(8, 27, easeOut(imp)), 8,
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
    this.anchor = { x: lerp(this.from.x, this.to.x, 0.42), y: S.ground - 83 };
    this.lines = [];
    /* Six lines at a pitch of 8 rather than five at 7. The block has to hold
     * 4/3 of its old height (39 -> 53) and the runes inside it do not scale, so
     * the height is bought as one more line plus a row of air between them —
     * which is also what makes a stack of runes read as CODE rather than as a
     * paragraph. */
    const n = 6;
    for (let i = 0; i < n; i++) {
      const indent = i === 0 || i === n - 1 ? 0 : 1 + ((this.rand() * 2) | 0);
      const side = this.rand() < 0.5 ? -1 : 1;
      this.lines.push({
        indent,
        cells: 6 + ((this.rand() * 8) | 0),
        seed: (this.seed + i * 7919) >>> 0,
        y: i * 8,
        /* The right-hand start has to clear the frame on the FIRST DRAWN
         * frame, not on paper. A strip is placed at lerp(fx, tx, overshoot(
         * lock)), and overshoot() is already ~0.48 the first time a line is
         * drawn, so the effective entry is roughly 0.52*fx + 0.48*tx plus the
         * strip's own width — not fx. At S.w + 27 that put the first painted
         * frame INSIDE the frame for 38 of 389 seeds, closest at x = 238,
         * seventeen columns in: the strip appeared out of clear air instead of
         * flying in from off-stage. (This is not a regression from the raster
         * move — the old 192-wide frame popped in at the same ~10% rate, 3 of
         * 19 seeds, closest x = 186. It was always wrong; it is only now
         * measured.) S.w + 80 satisfies 0.52*fx + 0.48*tx + stripW >= S.w for
         * every seed: 0 of 389 pop in, closest entry x = 273, eighteen columns
         * clear of the edge. The left start needs no equivalent — its strips
         * enter from -53 and further, and tx is nowhere near it. */
        fx: side < 0 ? -53 - this.rand() * 53 : S.w + 80 + this.rand() * 53,
        fy: S.ground - 147 + this.rand() * 120,
        at: 0.14 + i * 0.055,
      });
    }
    this.blockW = 0;
    for (const l of this.lines) {
      this.blockW = Math.max(this.blockW, 8 + l.indent * 5 + l.cells * GLYPH_ADVANCE);
    }
    this.blockH = n * 8 + 5;
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
            (r() - 0.5) * 80, -27 - r() * 53, 213, 0.4, 1, this.colour.hot);
        }
      }
    }
    if (this.k > 0.60 && this.k < 0.78) {
      this.drip(dt, 160, (r) => {
        const a = -Math.PI * 0.5 + (r() - 0.5) * 3;
        const sp = 40 + r() * 107;
        this.motes.emit(this.to.x + (r() - 0.5) * 16, this.to.y + (r() - 0.5) * 19,
          Math.cos(a) * sp, Math.sin(a) * sp, 227, 0.55,
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
      const tx = x0 + 4 + l.indent * 5;
      const ty = y0 + 3 + l.y;
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
        ctx.fillRect(px(x0 + 4), px(sy), px(l.indent * 5 - 1), GLYPH_H);
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
      ctx.fillRect(px(cx) - 1, px(cy - this.blockH / 2), 3, px(this.blockH));
      shockRing(ctx, this.to.x, this.to.y, lerp(4, 43, easeOut(imp)), col.key, (1 - imp) * 0.9);
      shockRing(ctx, this.to.x, this.to.y, lerp(4, 25, easeOut(imp)), col.hot, (1 - imp) * 0.55);
      cracks(ctx, this.to.x, this.to.y, this.seed + 3, 8, 24, col.hot,
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
    this.nest = { x: this.from.x, y: S.ground - 3 };
    /* The apex goes past 4/3. ground-84 scaled to ground-112 with the anchors;
     * ground-120 is 1.43x, and it is affordable because the VISIBLE headroom
     * above the ground grew 1.51x (100 rows -> 151) while the frame's own
     * height grew 1.75x. At 120 the bird's crest sits at row 55 minus its own
     * 24 rows of glow: 31, still seven clear of the safe top at 24. */
    this.apex = { x: lerp(this.from.x, this.to.x, 0.42), y: S.ground - 120 };
    this.gathers = [];
    for (let i = 0; i < 30; i++) {
      this.gathers.push({
        x: this.rand() * S.w,
        y: S.ground - this.rand() * 129,
        at: this.rand() * 0.2,
      });
    }
    this.feathers = [];
    for (let i = 0; i < 18; i++) {
      this.feathers.push({
        x: this.rand(), y: this.rand(), rot: this.rand() * Math.PI * 2,
        drift: (this.rand() - 0.5) * 35,
      });
    }
  }

  _step(dt) {
    // Ignition column throws embers straight up off the nest.
    if (this.k > 0.30 && this.k < 0.55) {
      this.drip(dt, 220, (r) => {
        this.motes.emit(this.nest.x + (r() - 0.5) * 21, this.nest.y,
          (r() - 0.5) * 35, -93 - r() * 120, 61, 0.7 + r() * 0.5,
          r() < 0.3 ? 2 : 1, r() < 0.45 ? this.colour.hot : this.colour.key);
      });
    }
    // The bird sheds embers along its flight.
    if (this.k > 0.55 && this.k < 0.88) {
      const b = this._birdAt();
      this.drip(dt, 180, (r) => {
        this.motes.emit(b.x + (r() - 0.5) * 32, b.y + (r() - 0.5) * 19,
          (r() - 0.5) * 40, 13 + r() * 53, 40, 0.6 + r() * 0.5, 1,
          r() < 0.4 ? this.colour.hot : this.colour.key);
      });
    }
    if (this.k > 0.80 && this.k < 0.92) {
      this.drip(dt, 200, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 53 + r() * 120;
        this.motes.emit(this.to.x, this.to.y - 8, Math.cos(a) * sp, Math.sin(a) * sp,
          -27, 0.9, r() < 0.3 ? 2 : 1, r() < 0.5 ? this.colour.hot : this.colour.key);
      });
    }
  }

  /* Flight path: straight up off the nest, then a flat sweep onto the target. */
  _birdAt() {
    const rise = easeOut(this.ph(0.46, 0.66));
    const cross = easeInOut(this.ph(0.62, 0.86));
    return {
      x: lerp(lerp(this.nest.x, this.apex.x, rise), this.to.x, cross),
      y: lerp(lerp(this.nest.y - 8, this.apex.y, rise), this.to.y - 13, cross),
      spread: clamp(this.ph(0.48, 0.70), 0, 1),
      flap: this.reducedMotion ? 0.7 : 0.62 + Math.sin(this.t * 9) * 0.38,
    };
  }

  _drawBird(ctx, b, alpha) {
    const col = this.colour, tn = this.tone;
    const open = easeOut(b.spread);
    /* 34 -> 45: a 90-unit wingspan was 47% of the old frame width and had
     * fallen to 35% of 256. Nine quills a side rather than seven, because the
     * wing is a third longer and seven strokes across it left the trailing half
     * of the wing see-through. */
    const span = 45 * open;
    const lift = b.flap;
    ctx.lineWidth = 1;
    // Wings: stacked flame quills swept back, brighter toward the leading edge.
    for (const dir of [-1, 1]) {
      for (let i = 0; i < 9; i++) {
        const p = i / 8;
        const len = span * (0.45 + 0.55 * Math.sin(Math.PI * (0.25 + p * 0.75)));
        const ex = b.x + dir * len;
        const ey = b.y - (1 - p) * 13 * lift + p * 16;
        /* Stepped down the ramp this module already memoises, not mixed here.
         * mix() builds a string, and this line runs nine times a wing, twice a
         * frame, for the length of the flight — the file says in its own words
         * at tonesFor() that that must never happen in a frame, and then did
         * it here and in the tail below. key -> mid -> deep is three steps of
         * the same ramp and costs nothing. */
        ctx.strokeStyle = rgba(i < 3 ? col.hot : i < 6 ? col.key : tn.mid,
          alpha * (0.55 + 0.45 * (1 - p)));
        ctx.beginPath();
        ctx.moveTo(px(b.x + dir * 3), px(b.y - 3 + p * 4));
        ctx.quadraticCurveTo(px(b.x + dir * len * 0.6), px(b.y - 11 * lift + p * 5),
          px(ex), px(ey));
        ctx.stroke();
      }
    }
    // Body, crest and the ember tail streaming behind.
    ctx.fillStyle = rgba(col.ink, alpha * 0.8);
    ctx.fillRect(px(b.x) - 4, px(b.y) - 8, 8, 17);
    ctx.fillStyle = rgba(col.deep, alpha);
    ctx.fillRect(px(b.x) - 3, px(b.y) - 7, 6, 15);
    ctx.fillStyle = rgba(col.key, alpha);
    ctx.fillRect(px(b.x) - 3, px(b.y) - 7, 5, 14);
    ctx.fillStyle = rgba(col.hot, alpha);
    ctx.fillRect(px(b.x) - 2, px(b.y) - 5, 3, 8);
    ctx.fillRect(px(b.x) - 2, px(b.y) - 11, 3, 4);          // head
    ctx.fillStyle = rgba(col.ink, alpha * 0.9);
    ctx.fillRect(px(b.x), px(b.y) - 10, 1, 1);              // eye
    ctx.fillStyle = rgba(col.hot, alpha * 0.9);
    ctx.fillRect(px(b.x) + 1, px(b.y) - 12, 4, 2);          // beak
    for (let i = 0; i < 6; i++) {                            // tail
      const p = i / 5;
      const wob = this.reducedMotion ? 0 : Math.sin(this.t * 7 - p * 3) * 4 * p;
      ctx.fillStyle = rgba(p < 0.34 ? col.key : p < 0.67 ? tn.mid : tn.dim,
        alpha * (1 - p * 0.7));
      ctx.fillRect(px(b.x - 2 + wob), px(b.y + 8 + i * 4), 3, 4);
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
        ctx.fillRect(px(gx), px(gy), p > 0.6 ? 3 : 2, p > 0.6 ? 3 : 2);
      }
      // The ground under the caster heats before anything else happens.
      /* A pool, not a plank. 28x2 was a bar on the floor at the old raster and
       * 50x4 would have been a bigger one; groundPool is the same three-step
       * ellipse every other impact in this file puts its light on the ground
       * with, so the caster's feet heat the way everything else does. */
      const heat = easeOut(gather);
      const prevHeat = ctx.globalCompositeOperation;
      ctx.globalCompositeOperation = 'lighter';
      groundPool(ctx, this.nest.x, S.ground - 1, 34 * heat, col.deep, live * heat * 0.5);
      groundPool(ctx, this.nest.x, S.ground - 1, 20 * heat, col.key, live * heat * 0.45);
      ctx.globalCompositeOperation = prevHeat;
    }

    // Ignition column.
    const ign = this.ph(0.30, 0.58);
    if (ign > 0 && ign < 1) {
      /* 92 -> 130 is 1.41x, past the 4/3 the rest of the file takes, and it is
       * the clearest place to spend the 1.51x of ground headroom: the column
       * tops out at row 42 against a safe top of 24. Twenty steps, not sixteen,
       * or the column comes out as a ladder. */
      const hgt = lerp(0, 130, easeOut(ign));
      const a = live * (1 - easeIn(ign)) * 0.95;
      for (let i = 0; i < 20; i++) {
        const p = i / 19;
        const w = Math.max(1, (1 - p) * 21 * (0.7 + 0.3 * Math.sin(p * 9 + this.t * 12)));
        const wob = this.reducedMotion ? 0 : Math.sin(p * 6 + this.t * 9) * 4;
        ctx.fillStyle = rgba(p < 0.2 ? col.hot : p < 0.55 ? col.key : this.tone.mid,
          a * (1 - p * 0.55));
        ctx.fillRect(px(this.nest.x - w / 2 + wob), px(this.nest.y - p * hgt), px(w), 4);
      }
    }

    // The bird.
    if (this.k > 0.44 && this.k < 0.94) {
      const b = this._birdAt();
      // Warm glow it carries, drawn under the bird so the bird stays crisp.
      /* The warm light the bird carries. This was a 52x36 fillRect — a brown
       * RECTANGLE sitting behind the firebird in every frame of its flight,
       * plainly visible in a contact sheet of the shipped build. A banded light
       * disc is the idiom the rest of this file already uses for light, costs
       * the same colours, and does not have corners. */
      const glow = live * (0.35 + 0.25 * Math.abs(this.osc(6)));
      const prevBird = ctx.globalCompositeOperation;
      ctx.globalCompositeOperation = 'lighter';
      lightDisc(ctx, b.x, b.y, 38, col.deep, glow * 0.42, 4);
      ctx.globalCompositeOperation = prevBird;
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
      shockRing(ctx, this.to.x, this.to.y - 8, lerp(8, 75 * pw, easeOut(imp)), col.hot, a * 0.9);
      shockRing(ctx, this.to.x, this.to.y - 8, lerp(3, 45 * pw, easeOut(imp)), col.key, a);
      shockRing(ctx, this.to.x, this.to.y - 8, lerp(3, 22 * pw, easeOut(imp)), col.hot, a * 0.6);
      // Feathers fall out of the impact and settle.
      for (const f of this.feathers) {
        const fx = this.to.x + (f.x - 0.5) * 93;
        const fy = lerp(this.to.y - 53, S.ground - 3, easeIn(imp)) + f.y * 21;
        stamp(ctx, `ph:feather9:${col.key}`, 9, 5, (c) => {
          c.fillStyle = col.ink; c.fillRect(0, 1, 9, 3);
          c.fillStyle = col.deep; c.fillRect(1, 2, 7, 2);
          c.fillStyle = col.key; c.fillRect(1, 1, 7, 1);
          c.fillStyle = col.hot; c.fillRect(3, 2, 4, 1);
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
      const x = cx + Math.cos(a) * (r - 4), y = cy + Math.sin(a) * (r - 4);
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.closePath();
    c.strokeStyle = col.key; c.stroke();
    /* A third, innermost hex in the mid tone. The plate is 4/3 wider and two
     * concentric outlines around one rune pair left a flat field between them. */
    c.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 2;
      const x = cx + Math.cos(a) * (r - 8), y = cy + Math.sin(a) * (r - 8);
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.closePath();
    c.strokeStyle = col.deep; c.stroke();
    paintGlyph(c, 5, col.hot, Math.round(cx - 5), Math.round(cy - 2));
    paintGlyph(c, 20, col.hot, Math.round(cx + 2), Math.round(cy - 2));
    c.fillStyle = STEEL;
    c.fillRect(Math.round(cx - 4), Math.round(cy - r + 3), 8, 1);
  };
}

/* --- a normal hit: a steel slash and sparks. Fast, legible, cheap. --- */
class HitEffect extends Effect {
  build() {
    this.angle = -0.7 + this.rand() * 0.5;
    this.reach = 35 + this.rand() * 8;
  }

  _step(dt) {
    if (this.k > 0.32 && this.k < 0.6) {
      this.drip(dt, 220, (r) => {
        const a = this.angle + Math.PI / 2 + (r() - 0.5) * 2.2;
        const sp = 53 + r() * 120;
        this.motes.emit(this.to.x + (r() - 0.5) * 11, this.to.y + (r() - 0.5) * 13,
          Math.cos(a) * sp, Math.sin(a) * sp, 293, 0.3 + r() * 0.25, 1,
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
      ctx.arc(px(this.from.x + 11), px(this.from.y), 11, -1.2, 0.4);
      ctx.stroke();
    }
    // The cut: a swept arc that crosses the target box.
    if (cut > 0) {
      const e = easeOut(cut);
      const a = (1 - easeIn(fade)) * 0.95;
      const cx = lerp(this.from.x + 13, this.to.x, e);
      const cy = lerp(this.from.y, this.to.y, e);
      /* The blade is as long as the blow is hard. Same art, scaled: a chip of
       * damage cuts a short arc, a heavy one cuts across the whole box. */
      const reach = this.reach * clamp(this.power, 0.7, 1.5);
      ctx.save();
      ctx.translate(px(cx), px(cy));
      ctx.rotate(this.angle);
      ctx.fillStyle = rgba(col.deep, a * 0.3);
      ctx.fillRect(px(-reach * e), -4, px(reach * 2 * e), 8);
      ctx.fillStyle = rgba(col.ink, a * 0.6);
      ctx.fillRect(px(-reach * e), -3, px(reach * 2 * e), 5);
      ctx.fillStyle = rgba(col.key, a * 0.85);
      ctx.fillRect(px(-reach * e), -1, px(reach * 2 * e), 3);
      ctx.fillStyle = rgba(col.hot, a);
      ctx.fillRect(px(-reach * e), 0, px(reach * 2 * e), 1);
      ctx.restore();
      if (cut >= 1) {
        const imp = this.ph(0.5, 1);
        shockRing(ctx, this.to.x, this.to.y, lerp(3, 21 * this.power, easeOut(imp)),
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
    for (let i = 0; i < 20; i++) {
      const a = (Math.PI * 2 * i) / 20 + this.rand() * 0.4;
      this.shards.push({
        a, sp: 80 + this.rand() * 147, spin: (this.rand() - 0.5) * 14,
        w: 4 + ((this.rand() * 5) | 0), h: 3 + ((this.rand() * 4) | 0),
      });
    }
    this.sigilSize = 36;
    this.hover = { x: this.to.x, y: this.box.y - 19 };
  }

  _step(dt) {
    if (this.k > 0.08 && this.k < 0.34) {
      // Charge: motes drawn up into the sigil as it forms.
      this.drip(dt, 90, (r) => {
        const a = r() * Math.PI * 2;
        const rad = 32 + r() * 21;
        this.motes.emit(this.hover.x + Math.cos(a) * rad, this.hover.y + Math.sin(a) * rad,
          -Math.cos(a) * rad * 2.6, -Math.sin(a) * rad * 2.6, 0, 0.4, 1, this.colour.key);
      });
    }
    if (this.k > 0.36 && this.k < 0.62) {
      this.drip(dt, 240, (r) => {
        const a = r() * Math.PI * 2;
        const sp = 67 + r() * 187;
        this.motes.emit(this.to.x + (r() - 0.5) * 13, this.to.y + (r() - 0.5) * 13,
          Math.cos(a) * sp, Math.sin(a) * sp, 347, 0.45 + r() * 0.45,
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
      runeRing(ctx, this.hover.x, y, lerp(40, 24, easeOut(form)), 8,
        this.reducedMotion ? 0 : this.t * 2.4, col, easeOut(form) * (1 - slam));
      stampRot(ctx, `crit:sigil:${col.key}:${this.sigilSize}`,
        this.sigilSize, this.sigilSize, paintSigil(this.sigilSize, col),
        this.hover.x, y, this.osc(2) * 0.05, easeOut(form), scale);
      /* The shadow the sigil casts on the target: the tell that it is coming.
       * An ellipse, not the 32x3 bar it used to be — a hexagonal plate does not
       * cast a rectangle, and at the new raster the bar was 43x4 of solid ink
       * lying on the floor. */
      groundPool(ctx, this.to.x, this.stage.ground - 1, 30,
        col.ink, easeOut(form) * 0.4);
    }

    // Shatter: cracks, two rings, and the plate blowing apart into shards.
    if (burst > 0) {
      const e = easeOut(burst);
      /* Every dimension of the shatter rides the damage: how far the rings get,
       * how deep the cracks run, how hard the shards are thrown. */
      const pw = clamp(this.power, 0.6, 1.8);
      shockRing(ctx, this.to.x, this.to.y, lerp(5, 69 * pw, e), col.hot, (1 - burst) * live);
      shockRing(ctx, this.to.x, this.to.y, lerp(3, 40 * pw, e), col.key, (1 - burst) * live * 0.9);
      shockRing(ctx, this.to.x, this.to.y, lerp(3, 20 * pw, e), col.hot, (1 - burst) * live * 0.55);
      cracks(ctx, this.to.x, this.to.y, this.seed, 11, 35 * pw, col.hot,
        (1 - burst) * live * 0.95, e);
      /* THE FALL IS SCALED BY THE APRON THAT EXISTS, NOT BY 4/3, AND IT STOPS
       * AT THE LAST PROMISED ROW.
       *
       * Everything else in this file grew 4/3 with the raster and that was
       * right, because the room it grew into grew too. The room UNDER the
       * burst did not. Measured: the old frame put the burst centre at row 60
       * with the last visible row at 127 — 67 rows of fall; the new one puts it
       * at 135 with the last visible row at 199 — 64. The room shrank by three
       * rows and the throw was multiplied by 4/3 anyway, so a third of the
       * shatter went somewhere nobody can see it. Counted over six seeds on an
       * unclipped canvas: the old crit threw 1.85% of its ink past the bottom
       * of the visible frame, which is what an explosion is allowed to do; this
       * one threw 4.65%, two and a half times as much, and 81% of that excess
       * was these shards.
       *
       * Two changes, and they do different jobs. 45 -> 30 is the gravity term
       * re-derived against the apron it falls into (34 x 24/27, the apron that
       * exists rather than the 4/3 that was assumed) — that governs the SHAPE
       * of the arc. The clamp is the backstop, and it is needed because the
       * radial throw alone carries a shard 113 rows from a centre only 64 rows
       * above the floor of the frame: no gravity term can fix that, only a
       * ceiling can. Together they put the discarded ink back at 1.88% against
       * the old 1.85%. The same idiom is already in this file — _paintImpact
       * passes safeTop + 2 to impactSignature as a ceiling. */
      for (const s of this.shards) {
        const d = s.sp * burst * 0.5 * pw;
        const x = this.to.x + Math.cos(s.a) * d;
        const y = Math.min(this.stage.safeTop + this.stage.safeH - 1,
          this.to.y + Math.sin(s.a) * d + burst * burst * 30);
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
        ctx.fillRect(px(b.x - 3), px(b.y - 3), px(b.w + 6), px(b.h + 6));
      }
    }
  }
}

/* --- RESISTED: the blow arrives and visibly bounces. The hex barrier is the
 * reason the player reads it as "wrong tool" rather than "missed". --- */
class ResistEffect extends Effect {
  build() {
    this.wall = { x: this.box.x - 5, y: this.to.y };
    this.facets = [];
    /* Six facets on a box that is 4/3 taller, each one 4/3 across: the barrier
     * has to look like a surface, and five hexes with gaps between them reads
     * as five hexes. */
    for (let i = 0; i < 6; i++) {
      this.facets.push({ y: this.box.y + 8 + i * (this.box.h - 16) / 5, r: 9 + this.rand() * 4 });
    }
  }

  _step(dt) {
    if (this.k > 0.48 && this.k < 0.72) {
      this.drip(dt, 120, (r) => {
        const a = Math.PI + (r() - 0.5) * 1.8;
        const sp = 40 + r() * 93;
        this.motes.emit(this.wall.x, this.wall.y + (r() - 0.5) * 24,
          Math.cos(a) * sp, Math.sin(a) * sp - 27, 280, 0.45, 1, this.colour.key);
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
      const x = lerp(this.from.x + 11, this.wall.x, e);
      const y = lerp(this.from.y, this.wall.y, e);
      ctx.fillStyle = rgba(col.ink, live * 0.7);
      ctx.fillRect(px(x) - 5, px(y) - 3, 12, 7);
      ctx.fillStyle = rgba(col.key, live);
      ctx.fillRect(px(x) - 4, px(y) - 2, 9, 4);
      ctx.fillStyle = rgba(col.hot, live);
      ctx.fillRect(px(x), px(y) - 1, 4, 2);
    } else if (back > 0) {
      const e = easeOut(back);
      const x = lerp(this.wall.x, this.wall.x - 93, e);
      const y = lerp(this.wall.y, this.wall.y - 53, e) + e * e * 61;
      ctx.fillStyle = rgba(col.key, live * (1 - back) * 0.9);
      ctx.fillRect(px(x), px(y), 4, 3);
      ctx.fillStyle = rgba(col.hot, live * (1 - back) * 0.6);
      ctx.fillRect(px(x) + 4, px(y), 3, 2);
    }

    // The barrier: a stack of hex facets lighting on contact, then rippling out.
    if (hitk > 0) {
      const flash = 1 - easeIn(this.ph(0.5, 0.86));
      ctx.lineWidth = 1;
      for (const f of this.facets) {
        const push = easeOut(this.ph(0.5, 0.8)) * 4;
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
      ctx.fillRect(px(this.wall.x) - 1, px(this.wall.y) - 4, 3, 8);
    }
  }
}

/* --- HEAL: warm, upward, and contracting. Damage rings expand; a mend ring
 * closes in, which is what stops it reading as another kind of hit. --- */
class HealEffect extends Effect {
  build() {
    /* rx/ry already carry the 4/3: 16x5 went to 21x7 with the anchors in the
     * raster commit, which is the one piece of body geometry that move did
     * bring with it. Everything else in this effect below did not. */
    this.circle = { x: this.from.x, y: this.stage.ground - 1, rx: 21, ry: 7 };
  }

  _step(dt) {
    if (this.k > 0.2 && this.k < 0.75) {
      this.drip(dt, 70, (r) => {
        const a = r() * Math.PI * 2;
        this.motes.emit(this.circle.x + Math.cos(a) * this.circle.rx,
          this.circle.y + Math.sin(a) * this.circle.ry,
          (r() - 0.5) * 11, -45 - r() * 53, -24, 0.8, r() < 0.4 ? 2 : 1,
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
    for (let i = 0; i < 8; i++) {
      const a = (Math.PI * 2 * i) / 8 + turn;
      drawGlyphStrip(ctx, C.x + Math.cos(a) * C.rx * ins - 1,
        C.y + Math.sin(a) * C.ry * ins - 2, 1, 991 + i * 37, col.key, live * ins * 0.8);
    }

    const col2 = this.ph(0.2, 0.7);
    if (col2 > 0) {
      const hgt = lerp(0, 53, easeOut(col2));
      for (let i = 0; i < 10; i++) {
        const p = i / 9;
        const w = Math.max(1, (1 - p) * 19);
        ctx.fillStyle = rgba(p < 0.4 ? col.hot : col.key, live * (1 - p) * 0.4);
        ctx.fillRect(px(C.x - w / 2), px(C.y - p * hgt), px(w), 4);
      }
    }

    // The mend: a ring that closes on the caster's chest, then a soft plus-free
    // rune flash. No medical iconography; this is a spellbook, not a clinic.
    const mend = this.ph(0.55, 0.86);
    if (mend > 0) {
      const r = lerp(35, 5, easeOut(mend));
      shockRing(ctx, this.from.x, this.from.y - 5, r, col.hot, (1 - mend) * live);
      /* The echo ring closes INSIDE the leading one, not outside it. Outside,
       * at 1.4x, it took the effect to 35.9% of the frame width against the
       * 26.0% it held on the 192 frame — a restore that overshot into a new
       * regression. Inside, the outer extent is still 2r = 27.3%. */
      shockRing(ctx, this.from.x, this.from.y - 5, r * 0.72, col.key, (1 - mend) * live * 0.5);
      const flash = arc(mend);
      drawGlyphStrip(ctx, this.from.x - 8, this.from.y - 10, 4, 4242, col.hot,
        flash * live * 0.95);
    }
  }
}

/* --- MISS: nothing connects. A pale arc passes through the target box and the
 * barrier never even lights. Short, quiet, and unmistakably a nil result. --- */
class MissEffect extends Effect {
  build() { this.lift = 24 + this.rand() * 11; }

  _draw(ctx) {
    const col = this.colour;
    const fly = this.ph(0.1, 0.7);
    const live = 1 - easeIn(this.ph(0.6, 1));
    if (fly <= 0) return;
    const e = easeOut(fly);
    const x = lerp(this.from.x + 11, this.to.x + 53, e);
    const y = lerp(this.from.y, this.to.y - 8, e) - Math.sin(Math.PI * e) * this.lift;
    ctx.fillStyle = rgba(col.key, live * 0.75);
    ctx.fillRect(px(x), px(y), 4, 3);
    ctx.fillStyle = rgba(col.hot, live * 0.5);
    ctx.fillRect(px(x) - 5, px(y), 5, 1);
    // Trail, so the eye can follow a shot that did nothing.
    for (let i = 1; i < 7; i++) {
      const p = clamp(e - i * 0.05, 0, 1);
      const tx = lerp(this.from.x + 11, this.to.x + 53, p);
      const ty = lerp(this.from.y, this.to.y - 8, p) - Math.sin(Math.PI * p) * this.lift;
      ctx.fillStyle = rgba(col.key, live * 0.3 * (1 - i / 7));
      ctx.fillRect(px(tx), px(ty), 3, 2);
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

/* ============================================================================
 * A HARNESS-ONLY RUNG. NOTHING IN THE SHIPPED GAME DRAWS ANY OF THESE FIVE.
 * ============================================================================
 * Read this before spending a pass re-scaling eleven effects: six of them are
 * on screen and five are not.
 *
 * There is exactly ONE call to createEffect() in the whole client —
 * fx.js:1546, inside BattleFX.castSpell() — and its only caller is
 * main.js:3019, which passes `rung.spell`, always one of the six SPELL_IDS. So
 * ORACLE, REVEAL_PATH, VISION, PSEUDOSIGHT, CODE_FRAGMENT and PHOENIX reach a
 * player and hit/crit/resist/heal/miss do not. BattleFX.hit() draws its own
 * primitives instead — a damageNumber, a burst and a _ring — and never touches
 * this module. The only things that exercise the five are
 * scripts/verify/spells2.mjs and steady.mjs, which iterate FX.DAMAGE_KIND
 * directly.
 *
 * WHY THEY ARE NOT WIRED UP, which is the question the next reader will ask.
 * Not an oversight to be tidied away with one line in hit(): these effects are
 * built as single, deliberate, once-per-cast animations, and hit() is not
 * called that way. resolveTrials() fires it once per trial at an interval of
 * 0.09s, so routing it here would put
 *
 *     hit     0.55s / 0.09s  ->   6 live at once
 *     resist  0.75s / 0.09s  ->   8 live at once
 *     crit    1.25s / 0.09s  ->  14 live at once
 *
 * on the stage during one ordinary test run — fourteen simultaneous copies of
 * the biggest non-spell effect in the game, each with twenty shards, three
 * shock rings, a rune ring, a sigil, a ground pool and a white frame over the
 * target. That is a whiteout, not a fight. Wiring them up means first giving
 * hit() a rate limit or a single reusable instance, and that is a combat-feel
 * change, not a rename.
 *
 * So: the five are kept, measured and maintained as a rung that the harnesses
 * hold to the same standard as the six — but a defect in one of them is a
 * defect in art nobody can currently see, and should be priced that way.
 * ============================================================================ */
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
    /* Samples across the whole effect, to touch every cached tile without
     * paying for a full playthrough. Twelve was enough when PSEUDOSIGHT had
     * fourteen rune rows and CODE_FRAGMENT five; at eighteen and six, twelve
     * samples walked past strips that then rasterised on the first real cast.
     * MEASURED, warming and casting the same seed: 12 samples leaves 8 canvases
     * to build during play, 32 leaves 1. (steady.mjs reports 49 either way
     * because it warms the default seed and plays seed 9 — a mismatch in the
     * harness, not a miss in here. The seed a cast will use has to be the seed
     * it was warmed with, and for the six spells it already is: _configure
     * defaults to hash(def.id) and fx.js casts with hash(name), the same
     * string.) */
    for (let i = 0; i <= 32; i++) {
      e.t = (e.duration * i) / 32;
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

/* ======================================================================
 * THE UNMAKING — the picture of gauntlet/unmaking.py, and the mirror of
 * web/js/transform.js
 * ======================================================================
 *
 * transform.js is five acts that BUILD. RAISE puts the arms up. CHARGE crawls
 * fourteen bolts INWARD to the figure over the longest act in the sequence.
 * DISCHARGE whites the screen out on one frame. REVEAL brings the figure back
 * lit from inside, twelve per cent wider, with the earned rank printed in gold
 * under chrome lettering reading "BY THE SOURCE — I NAME IT". HOLD sits on it.
 *
 * This is the same five acts, on the same figure, at the same marks, running
 * the other way. gauntlet/unmaking.py names them and states the mirror itself:
 *
 *     transform.js   here      what changes
 *     RAISE       -> REACH     he raises nothing; one hand opens, palm up, and
 *                              stays open for the whole spell
 *     CHARGE      -> TAKE      fourteen things travel OUTWARD to that hand,
 *                              same count, same attention, reversed flow
 *     DISCHARGE   -> STRIP     black at the white-out's speed, and it does not
 *                              come back up
 *     REVEAL      -> REVEAL    lit by nothing, ordinary width, one word in bone
 *     HOLD        -> HOLD      a blank editor and a cursor. No figure, no
 *                              lettering, no him.
 *
 * WHERE THE AUTHORITY LIVES, WHICH IS NOT HERE
 * --------------------------------------------
 * gauntlet/unmaking.py owns the clock, the fourteen dispossessions, their
 * order, their motifs, their ramps and every word spoken. This module owns
 * pixels. Pass `unmaking.cinematic()` straight through to `begin({cinematic})`
 * and the renderer takes its whole timeline from it — act boundaries, beat
 * starts, `take_seconds` per dispossession, the palette, the lettering. Change
 * a duration in Python and the picture changes with it; nothing has to be
 * edited twice.
 *
 * There is an authored fallback timeline for the case where nothing is passed,
 * so the module is drawable and testable on its own. It is the silent cut: the
 * acts collapse to their animation lengths and every beat gets the default
 * 0.85s. Its act lengths are exactly twice transform.js's, which is the same
 * statement the long version makes at greater length — everything he does takes
 * twice as long as the player's triumph did, because he is not hurrying.
 *
 * THE SPELL EXPLAINS THE SEAL. IT MUST NOT CHANGE IT.
 * ---------------------------------------------------
 * `UNMAKING_ORDER` is finalexam.CRUTCHES, in unmaking.take_ids() order, and
 * `reconcileUnmaking()` reports the two-way difference against whatever list
 * actually arrives. HOLDOUT is deliberately absent: it is a capability in the
 * same vocabulary and it is NOT a crutch, so nothing leaves the screen for it.
 * Nothing here calls anything, reads a save, or touches a capability;
 * finalexam.sealed() stays the one check in the codebase and this file cannot
 * reach it. Nothing here renders problem content: the fourteen fixtures are
 * abstract shapes and the only text drawn is the lettering unmaking.py wrote.
 *
 * LEARNING NEVER DEAD-ENDS, and the last two acts are that in pictures. REVEAL
 * holds the player alone, unlit, un-rimmed, unarmoured, at their ordinary
 * width, for twice as long as the transformation's triumphant hold. HOLD is an
 * empty editor with a cursor in it. He has taken back everything he ever handed
 * over, which is everything he had, and what is left on screen is the two
 * things he never gave.
 *
 * HOW IT IS DRAWN
 * ---------------
 * Opaque, always. No alpha ramps, no gradients: every pixel is one of the
 * fifteen colours unmaking.py's PALETTE names as (ramp, shade) pairs into
 * palette.js, and partial coverage is a 4x4 Bayer dither between two of them,
 * anchored to the screen grid so it does not crawl when a band moves. That is
 * how this art was made on the hardware it is pretending to be from, and it has
 * a second use: the fifteen-colour budget stops being an assertion and becomes
 * a count off the raster. The count FALLS as the beats land, because a ramp
 * retires with the thing it belonged to — and it rises exactly once, at
 * UNLIMITED_TIME, which is the one dispossession that ADDS something.
 *
 * Deterministic: noise() and the sequence's own clock, never Math.random,
 * never a wall clock. Cached: every dither tile is rasterised once and blitted
 * thereafter, so a warm frame is drawImage calls and fillRects and nothing else.
 */
import { RAMPS } from './palette.js';

/* ---------------- the fourteen, in the order the game took them ----------
 * gauntlet/unmaking.py take_ids(), which is finalexam.CRUTCHES sorted by ladder
 * rung: the twelve the bosses took in the order they took them, then the two
 * the exam alone takes, and the Hand last of all — it is the only one he has to
 * ask for rather than simply remove. */
export const UNMAKING_ORDER = Object.freeze([
  'HINTS', 'MENTOR', 'WEAKNESS_MAP', 'PROBES', 'PET', 'VISUALS', 'PATTERN',
  'BUILD', 'COACH', 'UNLIMITED_TIME', 'ITEMS', 'SOLUTION', 'SKILL_STATE',
  'OBLIGING_HAND',
]);

/* Named so that a reader who goes looking for the one that is missing finds a
 * reason instead of an oversight. */
export const UNMAKING_EXCLUDED = Object.freeze({
  HOLDOUT: 'A capability, not a crutch. Nothing is taken from the player by it, '
    + 'so nothing leaves the screen for it.',
});

export const UNMAKING_ACT_IDS = Object.freeze(['REACH', 'TAKE', 'STRIP', 'REVEAL', 'HOLD']);

/* unmaking.py MIRRORS, restated here so the two files can be checked against
 * each other by a harness rather than by a person reading both. */
export const UNMAKING_MIRRORS = Object.freeze({
  REACH: 'RAISE', TAKE: 'CHARGE', STRIP: 'DISCHARGE', REVEAL: 'REVEAL', HOLD: 'HOLD',
});

/* transform.js ACTS, in seconds, for the ratio the fallback timeline holds to. */
const TRANSFORM_ACTS = Object.freeze({
  RAISE: 0.55, CHARGE: 1.15, DISCHARGE: 0.45, REVEAL: 0.95, HOLD: 1.10,
});

/* unmaking.py's motif per crutch. Fourteen motifs for fourteen crutches, no two
 * the same, because a dispossession that looks like another one is not specific
 * to the thing lost. Each is painted by its own function below. */
export const UNMAKING_MOTIFS = Object.freeze({
  HINTS: 'EXTINGUISH', MENTOR: 'ABSENT', WEAKNESS_MAP: 'UNMARK', PROBES: 'SPEND',
  PET: 'VANISH', VISUALS: 'DRAIN', PATTERN: 'BLANK', BUILD: 'UNDRESS',
  COACH: 'REMOVE', UNLIMITED_TIME: 'ADD', ITEMS: 'EMPTY', SOLUTION: 'FACE_DOWN',
  SKILL_STATE: 'REDACT', OBLIGING_HAND: 'LIFT',
});

/* The ramp each dispossession is drawn in, from unmaking.py. */
export const UNMAKING_RAMPS = Object.freeze({
  HINTS: 'gold', MENTOR: 'void', WEAKNESS_MAP: 'frost', PROBES: 'violet',
  PET: 'bone', VISUALS: 'arcane', PATTERN: 'stone', BUILD: 'chrome',
  COACH: 'stone', UNLIMITED_TIME: 'ember', ITEMS: 'chrome', SOLUTION: 'frost',
  SKILL_STATE: 'violet', OBLIGING_HAND: 'blood',
});

/* Given the ids that actually arrived, is the spell taking exactly what the
 * exam takes? Both directions, because one direction is not a proof. */
export function reconcileUnmaking(ids) {
  const theirs = Array.isArray(ids) ? ids.map(String) : [];
  const mine = new Set(UNMAKING_ORDER);
  const them = new Set(theirs);
  return {
    matches: UNMAKING_ORDER.every((id) => them.has(id)) && theirs.every((id) => mine.has(id)),
    missing: UNMAKING_ORDER.filter((id) => !them.has(id)),   // exam takes, spell does not show
    extra: theirs.filter((id) => !mine.has(id)),             // spell takes, exam does not
    count: theirs.length,
  };
}

/* ---------------- fifteen colours ----------------
 * unmaking.py PALETTE, as (ramp, shade) pairs into palette.js. Resolved once at
 * module load and keyed by RAMPSHADE so the art can name a colour the same way
 * the Python does. Nothing in this sequence paints a colour that is not one of
 * these fifteen. */
const PALETTE_SPEC = Object.freeze([
  ['VOID0', 'void', 0], ['VOID2', 'void', 2], ['VOID4', 'void', 4],
  ['VIOLET1', 'violet', 1], ['VIOLET3', 'violet', 3],
  ['ARCANE4', 'arcane', 4],
  ['CHROME1', 'chrome', 1], ['CHROME4', 'chrome', 4],
  ['BONE2', 'bone', 2], ['BONE4', 'bone', 4],
  ['GOLD3', 'gold', 3], ['EMBER3', 'ember', 3], ['FROST3', 'frost', 3],
  ['STONE1', 'stone', 1], ['BLOOD2', 'blood', 2],
]);

export const UNMAKING_PALETTE = Object.freeze(PALETTE_SPEC.reduce((m, [key, ramp, shade]) => {
  m[key] = (RAMPS[ramp] && RAMPS[ramp][shade]) || '#151420';
  return m;
}, {}));

export const UNMAKING_PALETTE_SPEC = Object.freeze(
  PALETTE_SPEC.map(([key, ramp, shade]) => Object.freeze({ key, ramp, shade })));

const PALETTE_KEYS = Object.freeze(PALETTE_SPEC.map((e) => e[0]));

/* One step down. Used twice on purpose: it is how a colour retires when its
 * dispossession completes, and it is how a fixture goes grey while it is still
 * on screen. Two tables would drift; one cannot. */
const RAMP_DOWN = Object.freeze({
  VOID0: 'VOID0', VOID2: 'VOID0', VOID4: 'VOID2',
  VIOLET1: 'VOID2', VIOLET3: 'VIOLET1',
  ARCANE4: 'VIOLET3',
  CHROME1: 'STONE1', CHROME4: 'CHROME1',
  BONE2: 'STONE1', BONE4: 'BONE2',
  GOLD3: 'BONE2', EMBER3: 'BLOOD2', FROST3: 'CHROME1',
  STONE1: 'VOID0', BLOOD2: 'VIOLET1',
});

/* Which beat — or which act — retires which colour. A ramp used by two
 * dispossessions retires on the later of them, because it is still carrying
 * something until then. Ten entries, so fifteen become five. */
const PALETTE_DEATH = Object.freeze({
  GOLD3: 'HINTS',              // the rungs on the wall
  VOID4: 'MENTOR',             // the second shadow
  BONE4: 'PET',                // the last warm thing at the player's feet
  ARCANE4: 'VISUALS',
  CHROME4: 'ITEMS',            // chrome carried the build and then the belt
  FROST3: 'SOLUTION',          // frost carried the tactical read and then the page
  VIOLET3: 'SKILL_STATE',      // your own figures were the last thing that was yours
  BLOOD2: 'OBLIGING_HAND',     // the Hand's own colour goes into his palm with it
  EMBER3: 'STRIP',             // the clock he ADDED outlives every beat and dies with the room
  CHROME1: 'STRIP',            // "the interface chrome goes with it"
});

/* The five still reachable on the last frame. */
export const UNMAKING_SURVIVORS = Object.freeze(
  PALETTE_KEYS.filter((k) => !PALETTE_DEATH[k]));

/* ---------------- the fallback timeline ----------------
 * Only for a caller with no payload. Act lengths are exactly twice
 * transform.js's; TAKE is the sum of its beats at unmaking.py's default
 * `take` of 0.85s, the same way the real one is. */
const FALLBACK_TAKE = 0.85;

function fallbackTimeline(order) {
  const n = Math.max(1, order.length);
  const lens = {
    REACH: TRANSFORM_ACTS.RAISE * 2,
    TAKE: FALLBACK_TAKE * n,
    STRIP: TRANSFORM_ACTS.DISCHARGE * 2,
    REVEAL: TRANSFORM_ACTS.REVEAL * 2,
    HOLD: TRANSFORM_ACTS.HOLD * 2,
  };
  const acts = [];
  let at = 0;
  for (const id of UNMAKING_ACT_IDS) {
    acts.push({ id, at, seconds: lens[id], end: at + lens[id] });
    at += lens[id];
  }
  const take0 = acts[1].at;
  const beats = order.map((crutch, index) => ({
    index, crutch,
    at: take0 + index * FALLBACK_TAKE,
    take: FALLBACK_TAKE,
    end: take0 + (index + 1) * FALLBACK_TAKE,
    motif: UNMAKING_MOTIFS[crutch] || 'EXTINGUISH',
    ramp: UNMAKING_RAMPS[crutch] || 'void',
    shake: 0, flash: 0, line: '',
  }));
  return { acts, beats, total: at, source: 'fallback' };
}

/* unmaking.cinematic() -> the shape this renderer drives from. Everything it
 * reads is optional; a payload missing a field falls back to the authored
 * number for that field rather than to nothing, so a partially wired server
 * still plays something honest. */
function timelineFrom(payload, order) {
  const fb = fallbackTimeline(order);
  if (!payload || typeof payload !== 'object') return fb;
  const rawActs = Array.isArray(payload.acts) ? payload.acts : [];
  const acts = UNMAKING_ACT_IDS.map((id, i) => {
    const a = rawActs.find((x) => x && x.id === id);
    if (!a || !(a.seconds > 0)) return { ...fb.acts[i] };
    const at = Number.isFinite(a.at) ? a.at : fb.acts[i].at;
    return { id, at, seconds: a.seconds, end: at + a.seconds };
  });
  const rawBeats = Array.isArray(payload.beats) ? payload.beats : [];
  const beats = order.map((crutch, index) => {
    const b = rawBeats.find((x) => x && x.crutch === crutch);
    const base = fb.beats[index];
    if (!b) return { ...base };
    return {
      index, crutch,
      at: Number.isFinite(b.at) ? b.at : base.at,
      take: b.take_seconds > 0 ? b.take_seconds : base.take,
      end: Number.isFinite(b.end) ? b.end : base.end,
      motif: b.motif || base.motif,
      ramp: b.ramp || base.ramp,
      shake: Number.isFinite(b.shake) ? b.shake : 0,
      flash: Number.isFinite(b.flash) ? b.flash : 0,
      line: typeof b.line === 'string' ? b.line : '',
    };
  });
  const total = acts[acts.length - 1].end;
  return { acts, beats, total, source: 'cinematic' };
}

/* The lettering. THE WORDS ARE NOT THIS MODULE'S — unmaking.py owns them, for
 * the same reason the transformation's phrase lives in the story bible and not
 * in transform.js's head. `phrase` rides REACH the way "BY THE SOURCE" rides
 * the raise; `oath` lands on REVEAL the way "I NAME IT" does; `title` is where
 * transform.js prints the earned rank in gold, and here it is one word in bone.
 *
 * With nothing supplied the card draws its plate with the lettering absent.
 * That is not a placeholder. It is the correct picture of this moment in a game
 * whose villain erased the nouns, and it is unmistakable in review. */
export const UNMAKING_CARD_FIELDS = Object.freeze(['phrase', 'oath', 'title']);

export function unmakingCardFrom(payload) {
  const src = payload && typeof payload === 'object' ? payload : {};
  const spell = src.spell && typeof src.spell === 'object' ? src.spell : src;
  const pick = (v) => (typeof v === 'string' ? v.trim().toUpperCase() : '');
  return {
    phrase: pick(spell.phrase),
    oath: pick(spell.oath),
    title: pick(spell.title !== undefined ? spell.title : spell.reveal_title),
  };
}

/* ---------------- opaque drawing primitives ----------------
 * fillRect and drawImage and nothing else. No strokes, no arcs, no gradients,
 * no globalAlpha: a canvas that is asked only for rectangles is a canvas whose
 * output can be counted, and the fifteen-colour claim is a count. */

function urect(ctx, col, x, y, w, h) {
  if (!col) return;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)) return;
  const rw = px(w), rh = px(h);
  if (rw < 1 || rh < 1) return;
  ctx.fillStyle = col;
  ctx.fillRect(px(x), px(y), rw, rh);
}

/* 4x4 ordered dither, the hardware's own way of saying "half". Nine levels is
 * every step the eye can pick out at this pixel size and it keeps the tile
 * cache small: 0 and 8 never rasterise anything, they are a plain fill. */
const BAYER4 = Object.freeze([0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]);
const DITHER_TILE = 32;
const DITHER_LEVELS = 8;

function ditherCanvas(a, b, level) {
  return cachedCanvas(`unmk:${a}:${b}:${level}`, DITHER_TILE, DITHER_TILE, (c) => {
    const th = level * 2;
    for (let y = 0; y < DITHER_TILE; y++) {
      for (let x = 0; x < DITHER_TILE; x++) {
        c.fillStyle = BAYER4[(y & 3) * 4 + (x & 3)] < th ? b : a;
        c.fillRect(x, y, 1, 1);
      }
    }
  });
}

const wrap32 = (v) => ((v % DITHER_TILE) + DITHER_TILE) % DITHER_TILE;

/* Screen-aligned, so a band that moves one pixel does not make the whole
 * dither pattern crawl with it. The tile is anchored to the canvas grid and
 * the target rect takes a source sub-rectangle out of it. */
function udither(ctx, a, b, level, x, y, w, h) {
  if (!a || !b) return;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)) return;
  const l = clamp(Math.round(level), 0, DITHER_LEVELS);
  if (l <= 0) return urect(ctx, a, x, y, w, h);
  if (l >= DITHER_LEVELS) return urect(ctx, b, x, y, w, h);
  if (a === b) return urect(ctx, a, x, y, w, h);
  const X = px(x), Y = px(y), W = px(w), H = px(h);
  if (W < 1 || H < 1) return;
  const cv = ditherCanvas(a, b, l);
  if (!cv) return urect(ctx, l < DITHER_LEVELS / 2 ? a : b, X, Y, W, H);
  const ax = X - wrap32(X), ay = Y - wrap32(Y);
  for (let ty = ay; ty < Y + H; ty += DITHER_TILE) {
    const y0 = Math.max(Y, ty), y1 = Math.min(Y + H, ty + DITHER_TILE);
    if (y1 <= y0) continue;
    for (let tx = ax; tx < X + W; tx += DITHER_TILE) {
      const x0 = Math.max(X, tx), x1 = Math.min(X + W, tx + DITHER_TILE);
      if (x1 <= x0) continue;
      ctx.drawImage(cv, x0 - tx, y0 - ty, x1 - x0, y1 - y0, x0, y0, x1 - x0, y1 - y0);
    }
  }
  return undefined;
}

/* A limb as a march of squares rather than a stroke. lineTo would be invisible
 * to the raster harness and soft on a real canvas; this is how the sprite work
 * in this game draws a limb anyway. */
function ulimb(ctx, col, x0, y0, x1, y1, thick) {
  if (!Number.isFinite(x0) || !Number.isFinite(y0) || !Number.isFinite(x1) || !Number.isFinite(y1)) return;
  const t = Math.max(1, px(thick));
  const dx = x1 - x0, dy = y1 - y0;
  const n = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) / Math.max(1, t * 0.5)));
  for (let i = 0; i <= n; i++) {
    const q = i / n;
    urect(ctx, col, x0 + dx * q - t / 2, y0 + dy * q - t / 2, t, t);
  }
}

/* A tapered slab stack: the torso, and anything else that is wider at the top.
 * Rows of whole pixels, which is what makes the edge read as a staircase the
 * way a 16-bit sprite's does instead of as an antialiased ramp. */
function uwedge(ctx, col, cx, yTop, yBot, wTop, wBot, rows) {
  const n = Math.max(1, rows | 0);
  const h = (yBot - yTop) / n;
  if (!(h > 0)) return;
  for (let i = 0; i < n; i++) {
    const q = n === 1 ? 0 : i / (n - 1);
    const ww = lerp(wTop, wBot, q);
    urect(ctx, col, cx - ww / 2, yTop + i * h, ww, h + 1);
  }
}

/* A one-colour dither: only the lit cells are painted, the rest of the tile is
 * left transparent. This is how a thing goes out here — pixels stop being
 * there, in a pattern, rather than a whole shape getting quieter. An alpha ramp
 * would be a fade, and a fade says "a thing happened"; this says "he is taking
 * it". */
function screenCanvas(col, level) {
  return cachedCanvas(`unmks:${col}:${level}`, DITHER_TILE, DITHER_TILE, (c) => {
    const th = level * 2;
    c.fillStyle = col;
    for (let y = 0; y < DITHER_TILE; y++) {
      for (let x = 0; x < DITHER_TILE; x++) {
        if (BAYER4[(y & 3) * 4 + (x & 3)] < th) c.fillRect(x, y, 1, 1);
      }
    }
  });
}

function uscreen(ctx, col, level, x, y, w, h) {
  if (!col) return;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)) return;
  const l = clamp(Math.round(level), 0, DITHER_LEVELS);
  if (l <= 0) return;
  if (l >= DITHER_LEVELS) return urect(ctx, col, x, y, w, h);
  const X = px(x), Y = px(y), W = px(w), H = px(h);
  if (W < 1 || H < 1) return;
  const cv = screenCanvas(col, l);
  if (!cv) return;
  const ax = X - wrap32(X), ay = Y - wrap32(Y);
  for (let ty = ay; ty < Y + H; ty += DITHER_TILE) {
    const y0 = Math.max(Y, ty), y1 = Math.min(Y + H, ty + DITHER_TILE);
    if (y1 <= y0) continue;
    for (let tx = ax; tx < X + W; tx += DITHER_TILE) {
      const x0 = Math.max(X, tx), x1 = Math.min(X + W, tx + DITHER_TILE);
      if (x1 <= x0) continue;
      ctx.drawImage(cv, x0 - tx, y0 - ty, x1 - x0, y1 - y0, x0, y0, x1 - x0, y1 - y0);
    }
  }
  return undefined;
}


/* Cells still lit in a strip of `n` as it drains. Reaches 0 exactly at p = 1
 * and never flickers back on, which a naive round() does at the boundaries. */
function cellsLeft(n, p) {
  if (p <= 0) return n;
  if (p >= 1) return 0;
  return Math.max(0, n - Math.floor(p * n + 1e-6));
}

/* A token crossing the frame: a march of squares, shrinking as it goes, on a
 * path that sags. transform.js crawls its bolts inward to the figure with a
 * hashed jag; this is the same figure with the traffic reversed, which is the
 * single most important thing about the whole sequence. */
function utravel(ctx, col, x0, y0, x1, y1, q, size, seed) {
  const e = easeIn(clamp(q, 0, 1));
  const x = lerp(x0, x1, e);
  const y = lerp(y0, y1, e) - Math.sin(Math.PI * e) * size * 2.2;
  const s = Math.max(1, size * (1 - e * 0.55));
  urect(ctx, col, x - s / 2, y - s / 2, s, s);
  /* three specks of wake, so it reads as travelling rather than as a rect that
   * is somewhere else this frame */
  for (let i = 1; i <= 3; i++) {
    const b = clamp(e - i * 0.07, 0, 1);
    const bx = lerp(x0, x1, b) + (noise(seed, i) - 0.5) * size;
    const by = lerp(y0, y1, b) - Math.sin(Math.PI * b) * size * 2.2;
    urect(ctx, col, bx, by, Math.max(1, s * 0.4), Math.max(1, s * 0.4));
  }
}

export class Unmaking {
  constructor(opts = {}) {
    this.active = false;
    this.t = 0;
    this.order = UNMAKING_ORDER.slice();
    this.card = { phrase: '', oath: '', title: '' };
    this.cardSupplied = false;
    this.gone = new Set();
    this.shakeHint = 0;
    this.flashHint = 0;
    this._live = {};
    this._stage = -1;
    this._fired = new Uint8Array(this.order.length);
    this._actFired = new Uint8Array(UNMAKING_ACT_IDS.length);
    /* One scratch object for geometry, mutated in place. A cinematic that
     * allocates per frame is a cinematic with a hitch in it. */
    this.g = { w: 0, h: 0, cx: 0, ground: 0, u: 1, top: 0, palmX: 0, palmY: 0, open: 0 };
    this.onDeparture = null;
    this.onAct = null;
    this.onDone = null;
    this._configure(opts);
  }

  /* opts:
   *   cinematic     the object gauntlet/unmaking.py cinematic() returns, passed
   *                 through unchanged. Supplies acts, beats, lettering, motion.
   *   crutches      string[] override for the order (defaults to the payload's
   *                 beat order, then to UNMAKING_ORDER)
   *   card          {phrase, oath, title} override
   *   reducedMotion bool override
   *   onDeparture   (crutch, index, beat) => void   at the start of each beat
   *   onAct         (actId, index) => void
   *   onDone        () => void
   */
  begin(opts = {}) {
    this._configure(opts);
    this.active = true;
    this.t = 0;
    this.gone.clear();
    this._fired.fill(0);
    this._actFired.fill(0);
    this._stage = -1;
    this._advance();
    this._fireAct();
    return this;
  }

  update(dt) {
    if (!this.active) return this;
    /* Clamp rather than trust: a backgrounded tab hands back several seconds,
     * and a sequence that skips four dispossessions because the window lost
     * focus has lost the only thing it was for. */
    const d = Number.isFinite(dt) && dt > 0 ? Math.min(dt, 0.1) : 0;
    this.t += d;
    this._advance();
    this._fireAct();
    this._fireBeats();
    if (this.t >= this.total) this.cancel();
    return this;
  }

  /* A point on the clock, without firing anything. For a host that scrubs and
   * for the harness, which looks at forty frames without playing them. */
  seek(seconds) {
    this.t = clamp(Number.isFinite(seconds) ? seconds : 0, 0, this.total);
    this._advance();
    return this;
  }

  cancel() {
    if (!this.active) return this;
    this.active = false;
    const cb = this.onDone;
    this.onDone = null;
    if (cb) { try { cb(); } catch (e) { /* a callback never stalls art */ } }
    return this;
  }

  /* unmaking.py's skip contract: allowed, but only once the first dispossession
   * has finished, so a key that was already down cannot eat the spell. This
   * jumps to the last frame and holds there, still active — the player does not
   * have to watch it, but they do not get to walk in without the picture. */
  get skipAllowedAt() { return this.beats.length ? this.beats[0].end : this.total; }
  canSkip() { return this.t >= this.skipAllowedAt; }

  skipToEnd() {
    this.t = this.total - 1e-4;
    this._advance();
    this._fireAct();
    this._fireBeats();
    return this;
  }

  get progress() { return this.total > 0 ? clamp(this.t / this.total, 0, 1) : 1; }
  get act() { return this.actId; }
  get departed() { return this.order.filter((id) => this.gone.has(id)); }
  get remaining() { return this.order.filter((id) => !this.gone.has(id)); }

  /* What he is saying right now, for a host that renders dialogue in its own
   * UI. This module draws the lettering and nothing else: a cinematic renderer
   * that also owns the subtitle layer is a renderer nobody can restyle, and the
   * game already has a dialogue surface with its own typography.
   *
   * Act lines and beat lines are one list here because they are one list to the
   * player. `final` marks unmaking.py's last line, which is the one the host
   * should let sit before it dismisses. */
  speaking() {
    for (const l of this.lines) {
      if (this.t >= l.at && this.t < l.end) return l;
    }
    for (const b of this.beats) {
      if (this.t >= b.at && this.t < b.end && b.line) {
        return { text: b.line, crutch: b.crutch, act: this.actId, final: false };
      }
    }
    return null;
  }

  /* Distinct colours currently reachable. Fifteen at the start, five at the
   * end; the harness counts the same number off the raster. */
  livePaletteCount() {
    const seen = new Set();
    for (const k of PALETTE_KEYS) seen.add(this._live[k]);
    return seen.size;
  }

  /* --- internals ------------------------------------------------------- */

  _configure(opts = {}) {
    const cine = opts.cinematic && typeof opts.cinematic === 'object' ? opts.cinematic : this.cinematic;
    if (cine) this.cinematic = cine;

    if (Array.isArray(opts.crutches) && opts.crutches.length) {
      this.order = opts.crutches.map(String);
    } else if (cine && Array.isArray(cine.beats) && cine.beats.length) {
      const ids = cine.beats.map((b) => b && b.crutch).filter(Boolean).map(String);
      if (ids.length) this.order = ids;
    }
    this.reconciliation = reconcileUnmaking(this.order);
    if (this._fired.length !== this.order.length) this._fired = new Uint8Array(this.order.length);

    if (opts.reducedMotion !== undefined) this.reducedMotion = !!opts.reducedMotion;
    else if (cine && cine.motion) this.reducedMotion = String(cine.motion).toUpperCase() === 'REDUCED';
    else if (this.reducedMotion === undefined) this.reducedMotion = false;

    const tl = timelineFrom(cine, this.order);
    this.acts = tl.acts;
    this.beats = tl.beats;
    this.total = tl.total;
    this.timelineSource = tl.source;
    /* Spoken lines that belong to an act rather than to a dispossession —
     * REACH's three and REVEAL's six. Flattened once here rather than walked
     * every frame. */
    this.lines = [];
    if (cine && Array.isArray(cine.acts)) {
      for (const a of cine.acts) {
        if (!a || !Array.isArray(a.lines)) continue;
        for (const l of a.lines) {
          if (!l || typeof l.text !== 'string') continue;
          this.lines.push({
            text: l.text, act: a.id, crutch: '',
            at: Number.isFinite(l.at) ? l.at : 0,
            end: Number.isFinite(l.end) ? l.end : 0,
            final: !!l.final,
          });
        }
      }
    }

    if (opts.card !== undefined) this.card = unmakingCardFrom(opts.card);
    else if (cine) this.card = unmakingCardFrom(cine);
    this.cardSupplied = !!(this.card.phrase || this.card.oath || this.card.title);

    if (opts.onDeparture !== undefined) this.onDeparture = typeof opts.onDeparture === 'function' ? opts.onDeparture : null;
    if (opts.onAct !== undefined) this.onAct = typeof opts.onAct === 'function' ? opts.onAct : null;
    if (opts.onDone !== undefined) this.onDone = typeof opts.onDone === 'function' ? opts.onDone : null;
    this._stage = -1;
    this._advance();
  }

  /* The whole world state, recomputed from `t` and nothing else, so a scrubbed
   * frame and a played frame are the same frame. */
  _advance() {
    let idx = 0;
    for (let i = this.acts.length - 1; i >= 0; i--) {
      if (this.t >= this.acts[i].at) { idx = i; break; }
    }
    this.actIndex = idx;
    this.actId = this.acts[idx].id;

    this.gone.clear();
    let shake = 0, flash = 0;
    for (const b of this.beats) {
      const p = clamp((this.t - b.at) / Math.max(0.01, b.take), 0, 1);
      b.p = p;
      if (p >= 1) this.gone.add(b.crutch);
      if (p > 0 && p < 1) {
        /* Advisory, in the manner of the spellfx hints: nothing here reads
         * them, and an effect that is drawn and never read still looks right. */
        const env = arc(p);
        if (b.shake > 0) shake = Math.max(shake, b.shake * env);
        if (b.flash > 0) flash = Math.max(flash, b.flash * env);
      }
    }
    this.shakeHint = this.reducedMotion ? 0 : shake;
    this.flashHint = this.reducedMotion ? 0 : flash;

    /* He reaches over REACH and the hand stays open for the rest of the spell.
     * transform.js's RAISE puts the arms up and leaves them up; this is the
     * same gesture belonging to the other person. */
    const r = this.acts[0];
    this.g.open = clamp((this.t - r.at) / Math.max(0.01, r.seconds), 0, 1);

    const stage = this.gone.size * 8 + this.actIndex;
    if (stage !== this._stage) { this._stage = stage; this._resolveLive(); }
  }

  _resolveLive() {
    for (let i = 0; i < PALETTE_KEYS.length; i++) {
      const k = PALETTE_KEYS[i];
      let key = k;
      for (let n = 0; n < 8 && this._deadColour(key); n++) key = RAMP_DOWN[key];
      this._live[k] = UNMAKING_PALETTE[key];
    }
  }

  _deadColour(key) {
    const trigger = PALETTE_DEATH[key];
    if (!trigger) return false;
    const i = UNMAKING_ACT_IDS.indexOf(trigger);
    if (i >= 0) return this.actIndex >= i;
    return this.gone.has(trigger);
  }

  _col(key) { return this._live[key] || UNMAKING_PALETTE.VOID0; }

  /* n steps further down the ramp, then resolved. */
  _ramp(key, n) {
    let k = key;
    for (let i = 0; i < n && RAMP_DOWN[k]; i++) k = RAMP_DOWN[k];
    return this._col(k);
  }

  _beat(crutch) {
    for (const b of this.beats) if (b.crutch === crutch) return b;
    return null;
  }

  _p(crutch) { const b = this._beat(crutch); return b ? (b.p || 0) : 0; }

  /* Where we are inside an act, 0..1. */
  _phase(id) {
    const a = this.acts[UNMAKING_ACT_IDS.indexOf(id)];
    if (!a) return 0;
    if (this.t <= a.at) return 0;
    if (this.t >= a.end) return 1;
    return (this.t - a.at) / Math.max(0.01, a.seconds);
  }

  _fireAct() {
    const i = this.actIndex;
    if (this._actFired[i]) return;
    this._actFired[i] = 1;
    if (this.onAct) { try { this.onAct(this.actId, i); } catch (e) { /* never stalls art */ } }
  }

  _fireBeats() {
    for (let i = 0; i < this.beats.length; i++) {
      const b = this.beats[i];
      if (this._fired[i] || !(b.p > 0)) continue;
      this._fired[i] = 1;
      if (this.onDeparture) {
        try { this.onDeparture(b.crutch, i, b); } catch (e) { /* never stalls art */ }
      }
    }
  }

  /* --- the frame ------------------------------------------------------- */

  /* transform.js's marks, exactly: unit is h/80, the ground is at 0.78h, the
   * body is 22 units tall and the figure stands at the centre. It has to be the
   * same person at the same size or the two sequences are about two people.
   *
   * The one addition is his hand, at the right edge, at waist height. */
  _geom(w, h) {
    const g = this.g;
    g.w = w; g.h = h; g.cx = w / 2;
    g.u = h * 0.0125;
    g.ground = h * 0.78;
    g.top = g.ground - g.u * 22;
    g.palmX = w - g.u * 8;
    g.palmY = g.ground - g.u * 11;
    /* The light leaves in fourteen steps rather than on a curve: the frame
     * loses a piece of itself each time, and between times nothing happens. */
    const n = Math.max(1, this.beats.length);
    let d = this.gone.size;
    for (const b of this.beats) if (b.p > 0 && b.p < 1) d += b.p;
    g.drain = clamp(d / n, 0, 1);
    return g;
  }

  draw(ctx, w, h) {
    if (!ctx || !(w > 0) || !(h > 0)) return this;
    const g = this._geom(w, h);
    this._room(ctx, g);
    this._beam(ctx, g);

    /* The room, back to front. Every one of these was standing around the
     * player a minute ago. */
    this._fxHints(ctx, g);
    this._fxVisuals(ctx, g);
    this._fxSkillState(ctx, g);
    this._fxBuildBand(ctx, g);
    this._fxPattern(ctx, g);
    this._fxClock(ctx, g);
    this._fxWeakness(ctx, g);
    this._fxSolution(ctx, g);
    this._fxTable(ctx, g);
    this._fxCoach(ctx, g);
    this._fxShadows(ctx, g);
    this._fxProbes(ctx, g);
    this._fxPet(ctx, g);
    this._figure(ctx, g);
    this._palm(ctx, g);
    this._tokens(ctx, g);

    this._strip(ctx, g);
    this._card(ctx, g);
    return this;
  }

  /* --- the room, and the light going the wrong way --------------------- */

  /* transform.js drains the backdrop toward the figure and climbs a beam out of
   * the floor. Here the room is already lit when the sequence opens — it is the
   * light the player won — and it is pulled DOWN into the floor a step at a
   * time. The bands do not fade: their top edge descends, so the dark eats them
   * from above, which is the motion of a tide going out rather than a dimmer. */
  _room(ctx, g) {
    const d = g.drain;
    urect(ctx, this._col('VOID0'), 0, 0, g.w, g.h);

    const lightTop = lerp(g.h * 0.10, g.ground, d);
    const span = g.ground - lightTop;
    if (span > 3) {
      const bh = span / 3;
      udither(ctx, this._col('VOID0'), this._col('VIOLET1'), 2, 0, lightTop, g.w, bh);
      udither(ctx, this._col('VOID0'), this._col('VIOLET1'), 5, 0, lightTop + bh, g.w, bh);
      urect(ctx, this._col('VIOLET1'), 0, lightTop + bh * 2, g.w, span - bh * 2 + 1);
    }

    urect(ctx, this._col('VOID2'), 0, g.ground, g.w, g.h - g.ground);
    urect(ctx, this._col('STONE1'), 0, g.ground, g.w, Math.max(1, g.u * 0.5));

    /* The Source itself, two rows at the ground line: the only genuinely bright
     * thing in the opening frame, and the first thing to narrow. */
    if (this.actIndex <= 1) {
      const srcW = g.w * 0.94 * (1 - d);
      if (srcW > 3) {
        urect(ctx, this._col('VIOLET3'), g.cx - srcW / 2, g.ground - 2, srcW, 2);
        udither(ctx, this._col('VOID2'), this._col('VIOLET3'), 3,
          g.cx - srcW / 2, g.ground, srcW, Math.max(1, g.u * 1.2));
      }
    }
  }

  /* transform.js crawls jagged bolts UP into the figure over its long act. Same
   * column, ticks running DOWN it, narrowing as it goes: the light is being
   * drawn out of the player and into the floor. */
  _beam(ctx, g) {
    if (this.actIndex > 1) return;
    const d = g.drain;
    const lightTop = lerp(g.h * 0.10, g.ground, d);
    const span = g.ground - lightTop;
    const wB = g.w * 0.28 * (1 - d);
    if (span < 4 || wB < 3) return;
    udither(ctx, this._col('VIOLET1'), this._col('VIOLET3'), 3, g.cx - wB / 2, lightTop, wB, span);
    const core = wB * 0.34;
    if (core >= 2) {
      udither(ctx, this._col('VIOLET3'), this._col('ARCANE4'), 3, g.cx - core / 2, lightTop, core, span);
    }
    const travel = this.reducedMotion ? 0 : (this.t * 26) % span;
    const th = Math.max(1, g.u * 0.3);
    for (let i = 0; i < 7; i++) {
      const y = lightTop + (((i / 7) * span + travel) % span);
      urect(ctx, this._col('VIOLET3'), g.cx - wB / 2, y, wB, th);
    }
  }

  /* --- his hand ---------------------------------------------------------
   * "One hand opens, palm up, at waist height, and stays open for the whole
   * spell." He is never shown, never lit and never loud: an arm entering from
   * the edge of the frame in the room's own dark, one value up from the wall,
   * so you can see it without being shown it. Everything that leaves goes here.
   *
   * The gauntlet ends up sitting in it, which is the only time in the sequence
   * that anything is in his hand rather than passing through it. */
  _palm(ctx, g) {
    if (this.actIndex >= 2) return;
    const u = g.u, x = g.palmX, y = g.palmY;
    const open = this.g.open;
    const col = this._col('STONE1');
    urect(ctx, col, x + u * 3, y - u * 0.6, g.w - (x + u * 3), u * 2.4);   // forearm, off-frame
    urect(ctx, col, x - u * 2.6, y, u * 6.0, u * 1.8);                     // palm
    /* Four fingers, spreading over REACH and then held. Nothing about him
     * moves again after this. */
    for (let i = 0; i < 4; i++) {
      const spread = open * u * (1.1 + i * 0.35);
      urect(ctx, col, x - u * 2.6 + i * u * 1.5, y - spread, Math.max(1, u * 1.1), spread + u * 0.6);
    }
    urect(ctx, col, x + u * 3.2, y + u * 0.4, Math.max(1, u * 1.0), u * 1.4);  // thumb
    /* What he is already holding by the end. */
    if (this.gone.has('OBLIGING_HAND')) {
      urect(ctx, this._ramp('BLOOD2', 1), x - u * 1.6, y - u * 1.2, u * 3.4, u * 1.4);
    }
  }

  /* Everything that leaves crosses the frame to that hand. transform.js's
   * fourteen bolts crawl inward over its longest act; these are the same
   * fourteen, outward, over the same act. Two do not travel, and both
   * exceptions are the point: the clock is ADDED, and the belt's contents are
   * laid out on the table by the door rather than taken. */
  _tokens(ctx, g) {
    if (this.actIndex >= 2) return;
    for (const b of this.beats) {
      const p = b.p || 0;
      if (!(p > 0.6) || p >= 1) continue;
      if (b.motif === 'ADD') continue;
      const q = (p - 0.6) / 0.4;
      const home = this._home(b.crutch, g);
      const to = b.motif === 'EMPTY' ? this._home('__TABLE__', g) : { x: g.palmX, y: g.palmY - g.u };
      utravel(ctx, this._rampOf(b, 0), home.x, home.y, to.x, to.y, q, g.u * 1.6, b.index * 31 + 7);
    }
  }

  /* Where each thing stands, so the fixture and its token agree without either
   * of them owning the number. */
  _home(crutch, g) {
    const u = g.u, cx = g.cx, ground = g.ground;
    switch (crutch) {
      case 'HINTS':          return { x: cx - u * 22, y: ground - u * 14 };
      case 'MENTOR':         return { x: cx + u * 8, y: ground - u * 0.5 };
      case 'WEAKNESS_MAP':   return { x: cx + u * 27, y: ground - u * 8 };
      case 'PROBES':         return { x: cx - u * 12, y: ground - u * 13 };
      case 'PET':            return { x: cx - u * 8, y: ground - u * 2 };
      case 'VISUALS':        return { x: cx - u * 13, y: ground - u * 23 };
      case 'PATTERN':        return { x: cx + u * 16, y: ground - u * 22 };
      case 'BUILD':          return { x: cx, y: ground - u * 31 };
      case 'COACH':          return { x: cx - u * 18, y: ground - u * 3 };
      case 'UNLIMITED_TIME': return { x: cx + u * 28, y: ground - u * 24 };
      case 'ITEMS':          return { x: cx + u * 3, y: ground - u * 11 };
      case 'SOLUTION':       return { x: cx + u * 37, y: ground - u * 8 };
      case 'SKILL_STATE':    return { x: cx - u * 17, y: ground - u * 20 };
      case 'OBLIGING_HAND':  return { x: cx - u * 7, y: ground - u * 12 };
      case '__TABLE__':      return { x: cx - u * 27, y: ground - u * 4 };
      default:               return { x: cx, y: ground - u * 11 };
    }
  }

  /* The top of a beat's own ramp, n steps down. A ramp that has retired
   * resolves through the same table everything else does. */
  _rampOf(beat, n) {
    const key = RAMP_TOP[beat.ramp] || 'STONE1';
    return this._ramp(key, n);
  }

  /* --- the fourteen motifs, one each -------------------------------------
   * unmaking.py authors a motif per crutch and audits that no two are alike.
   * These are those fourteen, painted. */

  /* EXTINGUISH — "The five rungs on the chamber wall go out from the top down,
   * one for each, and then the wall they were cut into goes with them." */
  _fxHints(ctx, g) {
    const p = this._p('HINTS');
    const wallP = clamp((p - 0.7) / 0.3, 0, 1);
    if (wallP >= 1) return;
    const u = g.u;
    const x = g.cx - u * 26, y = g.top - u * 2, w = u * 8, h = g.ground - y;
    udither(ctx, this._col('VOID0'), this._col('STONE1'), Math.round(8 * (1 - wallP)), x, y, w, h);
    const lit = cellsLeft(5, clamp(p / 0.7, 0, 1));
    for (let i = 5 - lit; i < 5; i++) {
      urect(ctx, this._col('GOLD3'), x + u, y + u * 3 + i * u * 3.4, w - u * 2, Math.max(1, u * 0.7));
    }
  }

  /* ABSENT — "The second shadow on the floor beside the player's own shortens,
   * finishes, and is not replaced by anything." The player's own shadow stays
   * on the floor for the rest of the sequence, which is what makes the other
   * one's absence a shape rather than a nothing. */
  _fxShadows(ctx, g) {
    const u = g.u;
    urect(ctx, this._col('STONE1'), g.cx - u * 5, g.ground + u * 0.5, u * 10, Math.max(1, u * 0.9));
    const p = this._p('MENTOR');
    if (p >= 1) return;
    const len = u * 9 * (1 - easeIn(p));
    if (len < 1) return;
    urect(ctx, this._col('VOID4'), g.cx + u * 6, g.ground + u * 0.5, len, Math.max(1, u * 0.9));
  }

  /* UNMARK — "The soft places marked on the enemy stop being marked. The
   * outline holds; the thing inside it stops having a shape anybody
   * recognises." The outline is the last thing to go, and while it is still
   * there it is full of noise. */
  _fxWeakness(ctx, g) {
    const p = this._p('WEAKNESS_MAP');
    if (p >= 1) return;
    const u = g.u;
    const x = g.cx + u * 23, y = g.ground - u * 14, w = u * 9, h = u * 12;
    const th = Math.max(1, u * 0.5);
    const col = this._col('FROST3');
    const marks = cellsLeft(5, clamp(p / 0.6, 0, 1));
    /* the thing inside, losing its shape */
    const scramble = clamp((p - 0.2) / 0.5, 0, 1);
    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 4; c++) {
        const on = noise(r * 13 + c, Math.floor(scramble * 6));
        if (on > 0.5 - scramble * 0.25) continue;
        urect(ctx, this._ramp('FROST3', 2), x + u * 1 + c * u * 1.9, y + u * 1 + r * u * 1.8, u * 1.4, u * 1.3);
      }
    }
    for (let i = 0; i < marks; i++) {
      urect(ctx, col, x + u * 1.6 + (i % 3) * u * 2.6, y + u * 2 + Math.floor(i / 3) * u * 4.4, u * 1.6, Math.max(1, u * 0.7));
    }
    /* the outline, which holds */
    const gone = clamp((p - 0.72) / 0.28, 0, 1);
    if (gone < 1) {
      const o = this._ramp('FROST3', Math.floor(gone * 3));
      urect(ctx, o, x, y, w, th); urect(ctx, o, x, y + h - th, w, th);
      urect(ctx, o, x, y, th, h); urect(ctx, o, x + w - th, y, th, h);
    }
  }

  /* SPEND — "The probe tokens on the rail turn over and are gone, spent
   * without having been used on anything." Each token flips: its width goes to
   * nothing, comes back edge-lit, and then it is not there. */
  _fxProbes(ctx, g) {
    const p = this._p('PROBES');
    if (p >= 1) return;
    const u = g.u;
    const x = g.cx - u * 15, y = g.ground - u * 13, w = u * 8;
    const railP = clamp((p - 0.75) / 0.25, 0, 1);
    if (railP < 1) urect(ctx, this._ramp('VIOLET1', 0), x, y, w * (1 - railP), Math.max(1, u * 0.4));
    for (let i = 0; i < 3; i++) {
      const own = clamp((p / 0.75) * 3 - (2 - i), 0, 1);     // the last one bought goes first
      if (own >= 1) continue;
      const flip = Math.abs(Math.cos(own * Math.PI));
      const tw = Math.max(1, u * 1.8 * flip);
      urect(ctx, flip < 0.25 ? this._col('ARCANE4') : this._col('VIOLET3'),
        x + u * 0.9 + i * u * 2.6 - tw / 2, y - u * 1.9, tw, u * 1.8);
    }
  }

  /* VANISH — "The animal is simply not there any more. No sound, no going, no
   * gap left in the air where it was standing." So there is no transition. On
   * one frame there is a companion and on the next there is not, and the rest
   * of the beat is the floor where it was. */
  _fxPet(ctx, g) {
    if (this._p('PET') > 0.18) return;
    const u = g.u;
    const x = g.cx - u * 8, y = g.ground - u * 3.4;
    const col = this._col('BONE4');
    urect(ctx, col, x - u * 2.0, y, u * 4.0, u * 2.0);
    urect(ctx, col, x + u * 1.4, y - u * 1.4, u * 1.8, u * 1.8);
    urect(ctx, col, x + u * 2.9, y - u * 1.9, Math.max(1, u * 0.6), Math.max(1, u * 0.7));
    for (let i = 0; i < 4; i++) {
      urect(ctx, this._ramp('BONE4', 1), x - u * 1.8 + i * u * 1.1, y + u * 2.0, Math.max(1, u * 0.6), u * 1.4);
    }
  }

  /* DRAIN — "The picture of the work running freezes mid-step, drains to the
   * caption rail beneath it, and then the rail drains too." The freeze comes
   * first and it is the worst part: a visualiser that has stopped is harder to
   * look at than an empty panel. */
  _fxVisuals(ctx, g) {
    const p = this._p('VISUALS');
    const railP = clamp((p - 0.6) / 0.4, 0, 1);
    if (railP >= 1) return;
    const u = g.u;
    const x = g.cx - u * 18, y = g.ground - u * 28, w = u * 11, h = u * 9;
    const railY = y + h + u * 0.8;
    const fall = clamp((p - 0.2) / 0.4, 0, 1);
    urect(ctx, this._ramp('VIOLET1', 0), x, y, w, h);
    const frozen = p > 0 || this.reducedMotion;
    const tick = frozen ? 3 : Math.floor(this.t * 5);
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 5; c++) {
        if (noise(r * 17 + c, tick) < 0.42) continue;
        const cy = lerp(y + u * 1 + r * u * 2, railY, easeIn(fall));
        if (cy > railY - u * 0.4) continue;
        urect(ctx, this._col('ARCANE4'), x + u * 1 + c * u * 1.9, cy, u * 1.3, u * 1.2);
      }
    }
    urect(ctx, this._col('ARCANE4'), x, railY, w * (1 - railP), Math.max(1, u * 0.8));
  }

  /* BLANK — "The label over the door blanks. Then the doors stop being over
   * anything, and are only doors." The lintel goes; the posts stay, because a
   * door with nothing written over it is still a door and that is the joke he
   * is making. */
  _fxPattern(ctx, g) {
    /* The posts outlive the label, but they do not outlive the room: STRIP
     * takes everything the player did not personally learn, and it does not
     * come back up. */
    if (this.actIndex >= 2) return;
    const p = this._p('PATTERN');
    const u = g.u;
    const x = g.cx + u * 12, y = g.ground - u * 24, w = u * 9;
    const th = Math.max(1, u * 0.8);
    urect(ctx, this._ramp('STONE1', 0), x, y + u * 3, th, g.ground - y - u * 3);
    urect(ctx, this._ramp('STONE1', 0), x + w - th, y + u * 3, th, g.ground - y - u * 3);
    const lintelP = clamp((p - 0.5) / 0.5, 0, 1);
    if (lintelP < 1) {
      urect(ctx, this._ramp('STONE1', Math.floor(lintelP * 2)), x, y + u * 2, w, th);
      const lit = cellsLeft(5, clamp(p / 0.4, 0, 1));
      for (let i = 0; i < lit; i++) {
        urect(ctx, this._col('BONE4'), x + u * 0.8 + i * u * 1.6, y, u * 1.1, u * 1.4);
      }
    }
  }

  /* UNDRESS — "The gear lights along the status band go out in the order they
   * were earned, so the oldest one the player ever won is the last to go."
   * Newest first, left is oldest. The hero's own armour and the rim light on it
   * are the same beat: see _armour and _rim. */
  _fxBuildBand(ctx, g) {
    const p = this._p('BUILD');
    const bandP = clamp((p - 0.8) / 0.2, 0, 1);
    if (bandP >= 1) return;
    const u = g.u;
    const x = g.cx - u * 20, y = g.ground - u * 32, w = u * 40;
    urect(ctx, this._ramp('CHROME1', Math.floor(bandP * 2)), x, y, w * (1 - bandP), Math.max(1, u * 2.2));
    const lit = cellsLeft(7, clamp(p / 0.8, 0, 1));
    for (let i = 0; i < lit; i++) {
      urect(ctx, this._col('CHROME4'), x + u * 1.5 + i * u * 5.4, y + u * 0.6, u * 3.0, Math.max(1, u * 1.0));
    }
  }

  /* REMOVE — "The chair the debrief is given from is folded and carried out of
   * the frame by nobody." It folds first, then it goes left, and nothing is
   * carrying it. */
  _fxCoach(ctx, g) {
    const p = this._p('COACH');
    if (p >= 1) return;
    const u = g.u;
    const fold = clamp(p / 0.45, 0, 1);
    const slide = easeIn(clamp((p - 0.45) / 0.55, 0, 1)) * (g.cx - u * 18 + u * 10);
    const x = g.cx - u * 18 - slide;
    const col = this._ramp('STONE1', 0);
    const seatY = g.ground - u * 4 + fold * u * 3.2;
    const legH = u * 4 * (1 - fold);
    urect(ctx, col, x - u * 2.6, seatY, u * 5.2, Math.max(1, u * 0.8));
    urect(ctx, col, x - u * 2.6, seatY - u * 5 * (1 - fold), Math.max(1, u * 0.8), u * 5 * (1 - fold));
    if (legH >= 1) {
      urect(ctx, col, x - u * 2.2, seatY, Math.max(1, u * 0.7), legH);
      urect(ctx, col, x + u * 1.6, seatY, Math.max(1, u * 0.7), legH);
    }
  }

  /* ADD — "A clock that was never on that wall is on that wall, already
   * running, already behind." The only thing in the sequence that ARRIVES, the
   * only warm colour in the palette, and the only thing still moving once the
   * beats are done. Nothing travels to his hand for this one. */
  _fxClock(ctx, g) {
    /* It outlives every other fixture on the stage, because it is the only one
     * he put there. It does not outlive STRIP: he takes the room back too. */
    if (this.actIndex >= 2) return;
    const p = this._p('UNLIMITED_TIME');
    if (p <= 0.12) return;
    const u = g.u;
    const x = g.cx + u * 24, y = g.ground - u * 28, s = u * 8;
    urect(ctx, this._ramp('EMBER3', 2), x, y, s, s);
    urect(ctx, this._col('EMBER3'), x, y, s, Math.max(1, u * 0.5));
    urect(ctx, this._col('EMBER3'), x, y + s - Math.max(1, u * 0.5), s, Math.max(1, u * 0.5));
    urect(ctx, this._col('EMBER3'), x, y, Math.max(1, u * 0.5), s);
    urect(ctx, this._col('EMBER3'), x + s - Math.max(1, u * 0.5), y, Math.max(1, u * 0.5), s);
    /* already running, already behind */
    const a = this.reducedMotion ? 2.1 : this.t * 1.9;
    const cxx = x + s / 2, cyy = y + s / 2, r = s * 0.34;
    ulimb(ctx, this._col('EMBER3'), cxx, cyy, cxx + Math.cos(a) * r, cyy + Math.sin(a) * r, u * 0.6);
  }

  /* EMPTY — "The belt goes flat. Everything that was on it is on the table by
   * the door, laid out in a row, tidily, in the order it was bought." The only
   * thing in the sequence that goes somewhere other than his hand, and it is
   * the tidiness that is unpleasant. */
  _fxItems(ctx, g) {
    const p = this._p('ITEMS');
    const u = g.u;
    if (p < 1) {
      const flat = clamp((p - 0.5) / 0.5, 0, 1);
      const h = Math.max(1, u * (1.6 - flat * 1.0));
      urect(ctx, this._ramp('CHROME1', Math.floor(flat * 2)), g.cx - u * 4.6, g.ground - u * 11, u * 9.2, h);
      const lit = cellsLeft(5, clamp(p / 0.5, 0, 1));
      for (let i = 0; i < lit; i++) {
        urect(ctx, this._col('CHROME4'), g.cx - u * 4.0 + i * u * 1.9, g.ground - u * 11.6, u * 1.4, u * 1.6);
      }
    }
  }

  _fxTable(ctx, g) {
    if (this.actIndex >= 2) return;
    const p = this._p('ITEMS');
    const u = g.u;
    const x = g.cx - u * 32, y = g.ground - u * 5, w = u * 11;
    urect(ctx, this._ramp('STONE1', 0), x, y, w, Math.max(1, u * 0.8));
    urect(ctx, this._ramp('STONE1', 0), x + u * 0.6, y, Math.max(1, u * 0.7), u * 5);
    urect(ctx, this._ramp('STONE1', 0), x + w - u * 1.3, y, Math.max(1, u * 0.7), u * 5);
    /* laid out in the order it was bought, one appearing per rung of the drain */
    const laid = 5 - cellsLeft(5, clamp(p / 0.5, 0, 1));
    for (let i = 0; i < laid; i++) {
      urect(ctx, this._col('CHROME4'), x + u * 1.2 + i * u * 1.9, y - u * 1.4, u * 1.4, u * 1.4);
    }
  }

  /* FACE_DOWN — "The page that turns up after a scored attempt turns itself
   * face down, in advance, for a page that has not been dealt yet." It does not
   * go out. It rotates: edge on, and then back to full size with nothing
   * written on it, which is worse. */
  _fxSolution(ctx, g) {
    const p = this._p('SOLUTION');
    if (p >= 1) return;
    const u = g.u;
    const x = g.cx + u * 33, y = g.ground - u * 13, w = u * 8, h = u * 11;
    const turn = clamp(p / 0.7, 0, 1);
    const ww = Math.max(1, w * Math.abs(Math.cos(turn * Math.PI)));
    urect(ctx, this._ramp('FROST3', turn > 0.5 ? 2 : 0), x + (w - ww) / 2, y, ww, h);
    if (turn <= 0.5) {
      for (let i = 0; i < 4; i++) {
        const lw = (ww - u * 2) * (i === 3 ? 0.55 : 1);
        if (lw < 1) continue;
        urect(ctx, this._col('BONE4'), x + (w - ww) / 2 + u, y + u * 1.6 + i * u * 2.2, lw, Math.max(1, u * 0.8));
      }
    }
  }

  /* REDACT — "The player's own figures go blank a field at a time — mastery,
   * stage, dependence — oldest reading last." A field does not vanish: it is
   * replaced by a solid bar the same width, which is what a redaction is. */
  _fxSkillState(ctx, g) {
    const p = this._p('SKILL_STATE');
    const frameP = clamp((p - 0.82) / 0.18, 0, 1);
    if (frameP >= 1) return;
    const u = g.u;
    const x = g.cx - u * 21, y = g.ground - u * 22, w = u * 9;
    urect(ctx, this._ramp('VIOLET1', Math.floor(frameP * 2)), x, y, w, u * 7.4);
    for (let i = 0; i < 3; i++) {
      const yy = y + u * 0.9 + i * u * 2.3;
      const own = clamp((p / 0.82) * 3 - (2 - i), 0, 1);     // oldest reading last
      if (own >= 0.5) {
        urect(ctx, this._ramp('VIOLET3', 1), x + u * 0.8, yy, w - u * 1.6, u * 1.5);
      } else {
        for (let c = 0; c < 4; c++) {
          urect(ctx, this._col('VIOLET3'), x + u * 1.0 + c * u * 1.8, yy, u * 1.2, u * 1.5);
        }
      }
    }
  }

  /* --- the figure ------------------------------------------------------- */

  /* transform.js's silhouette, part for part. The arms run the other way: it
   * starts at lift = 1, because the player walked in having just won, and
   * REACH brings them down — "Hold your hands where I can see them. I will need
   * them empty." The lowered pose extends transform.js's own arm formula past
   * its lift = 0, which is arms-horizontal; that sequence never needed a
   * hanging arm because it only ever went up. */
  _figure(ctx, g) {
    const u = g.u, cx = g.cx, ground = g.ground, top = g.top;
    const hidden = this.actIndex >= 4 ? clamp(this._phase('HOLD') / 0.25, 0, 1) : 0;
    if (hidden >= 1) return;
    const body = this.actIndex >= 3 ? this._col('STONE1') : this._col('VOID2');
    const skin = this._col('BONE2');
    const lift = 1 - easeIn(clamp(this._phase('REACH'), 0, 1));
    const buildP = this._p('BUILD');

    urect(ctx, body, cx - u * 3.2, ground - u * 9, u * 2.4, u * 9);
    urect(ctx, body, cx + u * 0.8, ground - u * 9, u * 2.4, u * 9);
    uwedge(ctx, body, cx, top + u * 5, ground - u * 8, u * 9.2, u * 6.0, 10);
    urect(ctx, body, cx - u * 1.6, top + u * 1.4, u * 3.2, u * 3.6);
    urect(ctx, skin, cx - u * 1.1, top + u * 2.3, u * 2.2, u * 2.0);

    const shy = top + u * 5.6;
    for (const side of [-1, 1]) {
      const shx = cx + side * u * 4.2;
      const hx = shx + side * u * (1.0 + lift * 3.6);
      const hy = shy - lift * u * 9 + (1 - lift) * u * 7;
      ulimb(ctx, body, shx, shy, hx, hy, u * 2.1);
      urect(ctx, skin, hx - u * 0.7, hy - u * 0.7, u * 1.4, u * 1.4);
      if (side < 0) this._fxHand(ctx, g, shx, shy, hx, hy);
    }

    this._armour(ctx, g, buildP);
    this._fxItems(ctx, g);
    this._rim(ctx, g, buildP);

    /* HOLD dithers the figure away rather than cutting it: "No figure, no
     * lettering, no him." */
    if (hidden > 0) {
      uscreen(ctx, this._col('VOID0'), Math.round(DITHER_LEVELS * hidden),
        cx - u * 7, top, u * 14, ground - top + u * 2);
    }
  }

  /* UNDRESS on the body. The trim greys through three steps of the ramp while
   * the plates are still on, and only then do the plates come off. Greying
   * first is the point: the armour stops being lit before it stops being there,
   * so the player watches it become decoration and then watches it go. */
  _armour(ctx, g, p) {
    if (p >= 1) return;
    const u = g.u, cx = g.cx, top = g.top;
    const greyStep = Math.floor(clamp(p / 0.6, 0, 1) * 3);
    const fall = easeIn(clamp((p - 0.6) / 0.4, 0, 1)) * (g.ground - top - u * 3);
    const y0 = top + u * 5.6 + fall;
    if (y0 > g.ground) return;
    const plate = this._ramp('CHROME1', greyStep);
    const trim = this._ramp('CHROME4', greyStep);
    uwedge(ctx, plate, cx, y0, y0 + u * 6.4, u * 8.4, u * 7.2, 5);
    urect(ctx, trim, cx - u * 4.2, y0, u * 8.4, Math.max(1, u * 0.5));
    urect(ctx, trim, cx - u * 3.6, y0 + u * 6.4, u * 7.2, Math.max(1, u * 0.5));
    urect(ctx, plate, cx - u * 5.6, y0 - u * 0.4, u * 2.2, u * 2.0);
    urect(ctx, plate, cx + u * 3.4, y0 - u * 0.4, u * 2.2, u * 2.0);
  }

  /* THE RIM LIGHT FAILING.
   * §8 of the bible: one hot rim from a low source, on everything. transform.js
   * draws it in chrome and turns it UP at the reveal. Here it walks down the
   * ramp in four steps and is then not drawn at all — and because CHROME4 also
   * retires when the belt goes, the top of that ramp is gone underneath it. The
   * rim fails from both ends, and after this nothing in the sequence has an
   * edge light on it again. REVEAL is lit by nothing. */
  _rim(ctx, g, p) {
    const step = Math.floor(clamp(p, 0, 1) * 4);
    if (step >= 4 || this.actIndex >= 2) return;
    const u = g.u, cx = g.cx, top = g.top;
    const rim = this._ramp('CHROME4', step);
    const th = Math.max(1, u * 0.4);
    const rows = 10, y0 = top + u * 5, y1 = g.ground - u * 8;
    const rh = (y1 - y0) / rows;
    for (let i = 0; i < rows; i++) {
      const q = rows === 1 ? 0 : i / (rows - 1);
      const ww = lerp(u * 9.2, u * 6.0, q);
      urect(ctx, rim, cx - ww / 2, y0 + i * rh, th, rh + 1);
    }
    urect(ctx, rim, cx - u * 1.6, top + u * 1.4, th, u * 3.6);
    urect(ctx, rim, cx - u * 3.2, g.ground - u * 9, th, u * 9);
  }

  /* LIFT — "The gauntlet lifts off finger by finger, unhurried, and settles
   * into his palm, which is open, and has been open since the fourth chapter."
   * Five fingers leave one at a time and each one crosses the frame on its own;
   * the cuff goes last. It is the longest take in the spell and it is the only
   * dispossession he has to ask for. */
  _fxHand(ctx, g, shx, shy, hx, hy) {
    const p = this._p('OBLIGING_HAND');
    if (p >= 1) return;
    const u = g.u;
    const gx = lerp(shx, hx, 0.62), gy = lerp(shy, hy, 0.62);
    const cuffP = clamp((p - 0.62) / 0.38, 0, 1);
    if (cuffP < 1) {
      urect(ctx, this._ramp('BLOOD2', Math.floor(cuffP * 2)),
        gx - u * 1.5, gy - u * 1.5, u * 3.0, u * 3.0);
    }
    const fingers = cellsLeft(5, clamp(p / 0.62, 0, 1));
    for (let i = 0; i < fingers; i++) {
      urect(ctx, this._col('BLOOD2'), gx - u * 1.3 + i * u * 0.62, gy - u * 2.5, Math.max(1, u * 0.5), u * 1.1);
    }
    /* each finger crosses on its own, which is what "unhurried" looks like */
    for (let i = 0; i < 5; i++) {
      const own = clamp((p / 0.62) * 5 - i, 0, 1);
      if (!(own > 0) || own >= 1) continue;
      utravel(ctx, this._col('BLOOD2'), gx, gy - u * 2, g.palmX, g.palmY - u, own, u * 1.1, 900 + i * 13);
    }
  }

  /* --- STRIP, REVEAL and HOLD -------------------------------------------
   * transform.js peaks on a full-screen white in the first quarter of its
   * DISCHARGE and falls off it into a lit reveal. This goes to black at the
   * same speed and does not come back up. Not alpha: whole pixels, eight
   * dithered steps, then the room is gone and so is the interface chrome.
   *
   * REVEAL brings the figure back the same way, which is why the player
   * resolves one pixel pattern at a time instead of appearing. */
  _strip(ctx, g) {
    const dark = this._col('VOID0');
    if (this.actIndex === 2) {
      const p = this._phase('STRIP');
      uscreen(ctx, dark, Math.round(DITHER_LEVELS * clamp(p / 0.25, 0, 1)), 0, 0, g.w, g.h);
      return;
    }
    if (this.actIndex === 3) {
      const p = this._phase('REVEAL');
      const level = Math.round(DITHER_LEVELS * (1 - clamp(p / 0.18, 0, 1)));
      uscreen(ctx, dark, level, 0, 0, g.w, g.h);
      return;
    }
    if (this.actIndex === 4) {
      /* "This holds a blank editor and a cursor. No figure, no lettering, no
       * him." The last thing in the game that is still lit is the place the
       * player types. */
      const p = this._phase('HOLD');
      const q = clamp((p - 0.2) / 0.25, 0, 1);
      if (q <= 0) return;
      const x = px(g.w * 0.12), y = px(g.h * 0.20), w = px(g.w * 0.76), h = px(g.h * 0.60);
      uscreen(ctx, this._col('STONE1'), Math.round(DITHER_LEVELS * q), x, y, w, h);
      urect(ctx, this._col('VOID2'), x, y, w, 1);
      urect(ctx, this._col('VOID2'), x, y + h - 1, w, 1);
      const blink = this.reducedMotion ? 1 : (Math.floor(this.t * 1.8) % 2);
      if (q >= 1 && blink) {
        urect(ctx, this._col('BONE2'), x + g.u * 2, y + g.u * 2, Math.max(1, g.u * 0.9), g.u * 2.4);
      }
    }
  }

  /* --- the lettering ----------------------------------------------------
   * Same typeface, same mark on the screen as transform.js, opposite spirit.
   * PHRASE rides REACH the way "BY THE SOURCE" rides the raise, under a chrome
   * bevel that loses a step of the ramp for every four things taken, so by the
   * end of TAKE the lettering is flat. OATH lands on REVEAL the way "I NAME IT"
   * does, and it is drawn with no bevel and no shadow at all: transform.js's
   * card is an object with a light on it, and this one is a statement.
   *
   * Where transform.js prints the earned rank in gold, this prints one word in
   * bone. HOLD prints nothing. */
  _card(ctx, g) {
    if (!ctx.fillText) return;
    const size = Math.max(12, Math.round(g.h * 0.062));
    const step = Math.min(3, Math.floor(this.gone.size / 4));
    const y = g.h * 0.20;
    if (this.actIndex <= 1) {
      this._plate(ctx, g, this.card.phrase, g.cx, y, size, step);
      return;
    }
    if (this.actIndex !== 3) return;
    if (this._phase('REVEAL') < 0.18) return;
    ctx.save();
    ctx.font = `${Math.round(size * 1.05)}px "Press Start 2P", monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    if (this.card.oath) {
      ctx.fillStyle = this._col('BONE2');
      ctx.fillText(this.card.oath, g.cx, y);
    }
    if (this.card.title) {
      ctx.font = `${Math.round(size * 0.42)}px "Press Start 2P", monospace`;
      ctx.fillStyle = this._col('BONE2');
      ctx.fillText(this.card.title, g.cx, y + size * 0.95);
    }
    ctx.restore();
  }

  _plate(ctx, g, text, cx, y, size, step) {
    const face = this._ramp('CHROME4', step);
    const under = this._ramp('CHROME1', step);
    const shadow = this._col('VOID0');
    if (!text) {
      /* The card with its name taken out of it — which is, precisely, what he
       * did to the world, and is also how an unwired payload shows up. */
      const w = Math.min(g.w * 0.62, size * 16), h = size * 1.35;
      urect(ctx, shadow, cx - w / 2 + 4, y - h / 2 + 5, w, h);
      urect(ctx, under, cx - w / 2, y - h / 2, w, h);
      urect(ctx, face, cx - w / 2, y - h / 2, w, Math.max(1, g.u * 0.4));
      return;
    }
    ctx.save();
    ctx.font = `${size}px "Press Start 2P", monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = shadow;
    ctx.fillText(text, cx + 4, y + 5);
    ctx.fillStyle = under;
    ctx.fillText(text, cx, y + 2);
    ctx.fillStyle = face;
    ctx.fillText(text, cx, y);
    ctx.restore();
  }
}

/* The top of each ramp unmaking.py names, in this module's palette keys. */
const RAMP_TOP = Object.freeze({
  void: 'VOID4', violet: 'VIOLET3', arcane: 'ARCANE4', chrome: 'CHROME4',
  bone: 'BONE4', gold: 'GOLD3', ember: 'EMBER3', frost: 'FROST3',
  stone: 'STONE1', blood: 'BLOOD2',
});

/* The one call a host should need: hand it unmaking.cinematic() and drive it.
 *
 * NAME CLASH, ON PURPOSE, AND HOW TO AVOID IT. web/js/unmakingfx.js renders the
 * same spell the other way: in situ, on the player's real sprite, non-blocking,
 * no lettering, the Green Index rather than a palette blowout. It exports a
 * `createUnmaking` of its own. The two are alternatives, not layers — one is
 * the cutscene in transform.js's mould with the title card, the other is
 * weather over the scene the player is already in — and a host that wants both
 * names in scope should import this module namespaced, the way fx.js already
 * does, or use the unambiguous alias below. */
export function createUnmaking(opts = {}) { return new Unmaking(opts); }
export const createUnmakingCinematic = createUnmaking;

/* Rasterise every dither tile the sequence will ask for before the first frame.
 * A cold cache costs a hundred small canvases and the frame it would cost them
 * on is the frame the player is watching. */
export function warmUnmaking(opts = {}) {
  const made = makeCanvas(320, 180);
  if (!made) return 0;
  const before = canvasCache.size;
  const u = new Unmaking(opts);
  const steps = 240;
  for (let i = 0; i <= steps; i++) {
    u.seek((u.total * i) / steps);
    try { u.draw(made.ctx, 320, 180); } catch (e) { /* a cold warm-up is not fatal */ }
  }
  /* Four places take a dither level that moves with the clock rather than a
   * fixed one: the hint wall going, the figure dithering away under HOLD, and
   * the two halves of STRIP. A sweep only warms the levels it happens to land
   * on, so those are built outright. Both colours involved are survivors, so
   * this is twenty-one tiles in total however long the sequence runs. */
  for (let l = 1; l < DITHER_LEVELS; l++) {
    ditherCanvas(u._col('VOID0'), u._col('STONE1'), l);
    screenCanvas(u._col('VOID0'), l);
    screenCanvas(u._col('STONE1'), l);
  }
  return canvasCache.size - before;
}

/* The palette as it stands at a point on the clock, for the harness and for
 * anyone who wants the count without reading pixels. */
export function unmakingPaletteAt(seconds, opts = {}) {
  const u = new Unmaking(opts);
  u.seek(seconds);
  const live = {};
  for (const k of PALETTE_KEYS) live[k] = u._col(k);
  return { act: u.actId, departed: u.departed, count: u.livePaletteCount(), live };
}
