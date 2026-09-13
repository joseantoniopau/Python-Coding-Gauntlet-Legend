/* Three beats and the black.
 *
 * THE BRIEF, in the player's words: "when the player reaches 0 health points hp,
 * the screen goes black a heartbeat noise slowly does 1 then 2 then 3
 * progressively slower beats and blacks out."
 *
 * THE ONE LINE THIS FILE IS BUILT AROUND
 * --------------------------------------
 * DEATH REWINDS THE GAME. IT NEVER REWINDS THE PLAYER. gauntlet/saves.py says
 * it in those words about loading a slot, and gauntlet/db.py keeps the transfer
 * ledger monotone for the same reason. Gold, position, inventory, loot and the
 * minutes since the last save are all fair to lose, and losing them is the
 * whole threat. The graded record is not. So the most important thing on this
 * screen is not the animation — it is the line at the end that says the record
 * did not move, and deathLines() below puts it there every single time.
 *
 * IT IS THE SAME HEART
 * --------------------
 * upkeep.py has spent the entire fight speeding this heart UP: BPM_ONSET 72 at
 * the moment it starts to matter, BPM_MAX 132 on the floor, and `pulse_hz` is
 * literally `bpm / 60` so the red on the sprite and the thump underneath it are
 * one clock. Death is the inversion. The heart the player has been listening to
 * climb now falls: 132, 72, 39, and then it does not come back.
 *
 * audio.js owns those tempos (DEATH_BEAT_BPM / _MS / _AT) and derives every one
 * of them from upkeep's own two constants. This file imports that table rather
 * than restating it, and every visual phase below is exactly one beat gap long,
 * so the picture and the sound are one clock here too. That is not decoration:
 * a fade whose length was chosen independently of the beats reads as a fade
 * playing OVER a heartbeat rather than as a heart stopping.
 *
 *   t = 0       beat one, 132 BPM. The alarm's next beat. The seam is inaudible.
 *   0 -> 833    DRAIN. The frame loses its COLOUR. The dark red the alarm has
 *               been pulsing goes grey. The light does not change.
 *   t = 833     beat two, 72 BPM — the floor of upkeep's ramp. Rest.
 *   833 -> 2371 FALL. Now the light goes. The lit area closes inward on the
 *               hero, slow then fast, the way vision narrows.
 *   t = 2371    beat three, 39 BPM. Low, long, and with no DUB to close it.
 *               Only the hero is lit.
 *   2371 -> 2884 LAST. The hero goes out. 513ms, one third of the final gap.
 *   2884 -> 3909 BLACK. A full second of nothing, which is most of the silence,
 *               because a black that is shorter than the fade is a transition
 *               rather than a black.
 *   t = 3909    the words. The end of the silence lands on the fourth beat that
 *               did not come.
 *
 * COLOUR BEFORE LIGHT, and the hero last. The order is the point. Losing colour
 * first is what a body does — it greys out before it goes dark — and it means
 * the player has a full beat to register that something has changed before they
 * lose the ability to see. The hero is last because he is the only thing on
 * this screen that is them.
 *
 * FIFTEEN COLOURS, and that constraint is what makes this pixel art instead of
 * a CSS filter. There is no alpha fade over the live frame here and no radial
 * gradient: a continuous fade over a rendered game frame is tens of thousands
 * of colours and would fail the count on its first frame. Instead the screen is
 * RE-RENDERED through an authored 14-stage ramp — three field tones and a
 * five-step plate for the hero, eight paints on the busiest frame — and the
 * iris is scanline fillRects, the only drawing primitive sprites.js has ever
 * used. The ramps are built once at module load. Nothing allocates per frame.
 *
 * IT MUST NOT TRAP. This module reads no input, installs no listener and owns
 * no timer. It draws when it is asked to draw and it answers questions about
 * where it is. skip() lands on the end state from any t, skipArmedAt() says
 * when the host should let the player use it, and deathLines() always returns
 * at least one action. A player who dies ten times in an hour can get out of
 * this screen ten times in an hour, and the tenth is faster than the first.
 */
import { heroFrame, HERO_W, HERO_H } from './sprites.js';
import { THEME, OUTLINE, MAX_COLOURS, mix, parseHex, toHex } from './palette.js';
import { STAGE, FIGURE_SCALE } from './fx.js';
import {
  DEATH_BEAT_BPM, DEATH_BEAT_MS, DEATH_BEAT_AT, DEATH_SILENCE_MS,
} from './audio.js';

export const DEATHFX_VERSION = '1.0.0';

/* Re-exported so a host wiring the screen has one import, and so the harness
 * can prove this file and audio.js are reading the same table. */
export { DEATH_BEAT_BPM, DEATH_BEAT_MS, DEATH_BEAT_AT, DEATH_SILENCE_MS };

/* ------------------------------------------------------------- the timeline
 *
 * Every boundary below is a beat time or a beat gap. Not one is a round number
 * somebody liked the feel of, and that is deliberate: the numbers a player
 * actually perceives here are the GAPS between thumps, and a fade that ends
 * halfway through a gap makes the two channels feel unrelated.
 */
export const DRAIN_FROM = DEATH_BEAT_AT[0];                 // 0
export const FALL_FROM = DEATH_BEAT_AT[1];                  // 833
export const LAST_FROM = DEATH_BEAT_AT[2];                  // 2371
/* One third of the final gap. The hero has to be gone before the words, and a
 * third leaves two thirds of the silence as true, empty black. */
export const LAST_MS = Math.round(DEATH_SILENCE_MS / 3);    // 513
export const BLACK_FROM = LAST_FROM + LAST_MS;              // 2884
export const WORDS_AT = LAST_FROM + DEATH_SILENCE_MS;       // 3909
export const DEATH_MS = WORDS_AT;

export const PHASES = Object.freeze([
  Object.freeze({ id: 'DRAIN', from: DRAIN_FROM, to: FALL_FROM,
                  what: 'the frame loses its colour' }),
  Object.freeze({ id: 'FALL', from: FALL_FROM, to: LAST_FROM,
                  what: 'the frame loses its light' }),
  Object.freeze({ id: 'LAST', from: LAST_FROM, to: BLACK_FROM,
                  what: 'the hero goes out' }),
  Object.freeze({ id: 'BLACK', from: BLACK_FROM, to: WORDS_AT,
                  what: 'nothing' }),
  Object.freeze({ id: 'WORDS', from: WORDS_AT, to: Infinity,
                  what: 'where you woke and what it cost' }),
]);

export function phaseAt(t) {
  const ms = clamp(num(t, 0), 0, Infinity);
  for (const p of PHASES) if (ms < p.to) return p;
  return PHASES[PHASES.length - 1];
}

/** How many of the three beats have sounded by `t`. The host does not need
 *  this to play them — audio.heartbeatStop() schedules all three in one call —
 *  but a debug overlay and the harness both do. */
export function beatsBy(t) {
  const ms = num(t, 0);
  let n = 0;
  for (const at of DEATH_BEAT_AT) if (ms >= at) n++;
  return n;
}

/* ------------------------------------------------------------------ colour
 *
 * upkeep.py's DIRE band is #ff3b46 and that is the colour that has been
 * pulsing on the sprite for the last few submissions. It is the one colour on
 * this screen at t=0 and it is the colour that leaves, which is why the drain
 * reads as continuous with the alarm rather than as a new effect starting.
 *
 * The hex below is a FALLBACK, not a second copy of upkeep's constant: the host
 * passes `alarmColour` straight off the server's last alarm row (main.js keeps
 * it as G.alarm.colour) and this value is only used when there is no row to
 * read — a player killed by something that never lit the alarm. The harness
 * reads gauntlet/upkeep.py's ALARM_BANDS and fails if the two drift, which
 * makes the agreement a measurement instead of a promise.
 */
export const DIRE_FALLBACK = '#ff3b46';

const VOID = THEME.void;                     // #06060a
/* The field the hero stands in: not black, or the fade has nowhere to go, and
 * not bright, or a death screen reads as a lit room. */
const FIELD_LIT = mix(VOID, THEME.inkFaint, 0.62);
/* The hero's own five steps, neutral. The plate maps his sprite into these by
 * luminance rank, so a hero in full plate and a hero in a shirt both keep their
 * internal shading and both come out inside the budget. */
const PLATE_STEPS = 5;
const GREY = Object.freeze([
  OUTLINE,
  mix(OUTLINE, THEME.bone, 0.26),
  mix(OUTLINE, THEME.bone, 0.52),
  mix(OUTLINE, THEME.bone, 0.78),
  THEME.bone,
]);

/* How much of the alarm's red the field and the figure carry at full
 * saturation. The field takes more than the figure because the field is what is
 * supposed to be draining — a hero who starts out scarlet reads as on fire. */
const FIELD_TINT = 0.55;
const PLATE_TINT = 0.30;

/* Stage counts. The colour is quantised and the geometry is not: a stepped ramp
 * is how a 16-bit game fades and it keeps the palette countable, while a
 * stepped iris would just look broken. */
const DRAIN_STAGES = 4;    // 208ms a step across the first gap
const FALL_STAGES = 6;     // 256ms a step across the second
const LAST_STAGES = 3;     // 171ms a step
const STAGE_COUNT = DRAIN_STAGES + FALL_STAGES + LAST_STAGES + 1;   // 14

/* The iris, in STAGE space (256x224), centred on the HERO rather than on the
 * screen — he is at x=64 of 256, well left of centre, and a circle of light
 * that closed on the middle of the frame and then slid sideways to find him
 * would be the one moment in this sequence that looked like an effect.
 *
 * R_OPEN is the frame's own half-diagonal. Off-centre as it is, that does NOT
 * clear the far corners, and it is not meant to: from the first frame the
 * player is already standing in a pool of light with the edges of the world
 * darker than he is. The iris does not arrive at beat two, it closes.
 *
 * R_SHUT is the hero's own half-diagonal, so the circle stops exactly when it
 * is him and nothing else. */
const R_OPEN = Math.ceil(Math.hypot(STAGE.w, STAGE.h) / 2) + 8;     // 178 at 256x224

/* THE SIZE HE IS ACTUALLY DRAWN AT, and every number below is derived from it.
 *
 * They used to be derived from HERO_W and HERO_H — the RIG box, 16x24 — while
 * fx.js blitted the same rig at FIGURE_SCALE into 64x96 of the same 256x224
 * frame. drawPlate emitted fillRect(ox + x, oy + y, run, 1), so the figure the
 * death screen drew was ONE QUARTER the size of the one the fight had been
 * showing a frame earlier, on the exact cut this file's header promises will
 * be seamless ("the hero lands on the exact pixel he was already standing
 * on"). Counted: 24 rows of 224 = 10.7% of the frame against the fight's 96 of
 * 224 = 42.9%, a 4.0x discontinuity. Confirmed in a live death at 1440x940 — a
 * 64x96 device-pixel speck inside a 1024x896 blit.
 *
 * scripts/verify/death.mjs could not see it because litStats built its hero box
 * out of the same HERO_W/HERO_H, so the harness and the drawing shared the
 * error. That is why DRAWN_W/DRAWN_H are PUBLISHED on DEATH_STAGE below. */
const DRAWN_W = HERO_W * FIGURE_SCALE;                              // 64
const DRAWN_H = HERO_H * FIGURE_SCALE;                              // 96

/* R_SHUT is the hero's own half-diagonal AS DRAWN, so the circle stops exactly
 * when it is him and nothing else. At the rig size it closed to radius 15
 * around a point 36 rows below the figure's true centre. */
const R_SHUT = Math.ceil(Math.hypot(DRAWN_W, DRAWN_H) / 2);         // 58
const RING = 0.62;         // the inner ring, as a fraction of the outer

/* The hero stands where fx.js already had him, so nothing jumps when the
 * overlay takes the screen. STAGE.heroX is a foot centre, STAGE.ground is where
 * feet land. */
const HERO_X = STAGE.heroX;
const HERO_FOOT = STAGE.ground;
const HERO_CX = HERO_X;
const HERO_CY = HERO_FOOT - Math.round(DRAWN_H / 2);

/* THE GEOMETRY THIS SCREEN IS COMPOSED IN, PUBLISHED.
 *
 * scripts/verify/death.mjs used to carry its own copy of these four numbers —
 * `46`, `100`, `192`, `128` — to work out where on the host canvas the hero's
 * box lands, which meant the harness went on measuring the OLD stage for one
 * whole raster migration and reported 1216 lit pixels that were "neither the
 * hero nor his shadow" when in fact it was looking at the wrong part of the
 * frame. A second copy of a geometry is a second opinion about it. There is
 * exactly one here, and anything that needs to know asks. */
export const DEATH_STAGE = Object.freeze({
  w: STAGE.w,
  h: STAGE.h,
  heroX: HERO_X,
  ground: HERO_FOOT,
  // The RIG box, which is what the sprite is authored in...
  rigW: HERO_W,
  rigH: HERO_H,
  scale: FIGURE_SCALE,
  // ...and the box it occupies on the frame, which is what a harness measuring
  // this screen has to draw its window from. Publishing only the first pair is
  // what let death.mjs share this file's own bug for a whole raster migration.
  heroW: DRAWN_W,
  heroH: DRAWN_H,
  // The shadow he stands in, published for the same reason: it is three rows of
  // the rig, so it is 3 * FIGURE_SCALE of the frame, and it starts one rig row
  // above the ground line. A harness that assumed three raw rows would report
  // two thirds of it as "neither the hero nor his shadow".
  shadowH: 3 * FIGURE_SCALE,
  shadowRise: FIGURE_SCALE,
});

/* ---------------------------------------------------------------- utilities */
function num(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}
const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

/* Rec.601 on 0..255, integer weights, so every ramp this file builds is
 * bit-identical from one run to the next. */
function lumOf(hex) {
  const [r, g, b] = parseHex(hex);
  return (r * 299 + g * 587 + b * 114) / 1000;
}

/** `hex` rescaled to carry `target`'s luminance. The tool that lets the drain
 *  take colour away without taking light with it. */
function keepLum(target, hex) {
  const want = lumOf(target), have = lumOf(hex);
  if (!(have > 0)) return hex;
  const k = want / have;
  const [r, g, b] = parseHex(hex);
  return toHex([clamp(Math.round(r * k), 0, 255),
                clamp(Math.round(g * k), 0, 255),
                clamp(Math.round(b * k), 0, 255)]);
}

/* Working sets, not archives — the same rule sprites.js and unmakingfx.js use.
 * A death screen asks for one plate per look, and a player only has one look at
 * a time, so this never grows past a handful. */
function capCache(map, max) {
  while (map.size > max) {
    const oldest = map.keys().next();
    if (oldest.done) break;
    map.delete(oldest.value);
  }
  return map;
}

/* ------------------------------------------------------------------ stages
 *
 * Three scalars, one per thing that can leave, and they leave in order:
 *
 *   sat    the alarm's red. 1 at the start, 0 by beat two. Nothing else moves
 *          while this is moving, which is what makes it legible.
 *   field  the light in the frame. 1 until beat two, 0 at the black.
 *   plate  the light on the hero. 1 until beat THREE — he keeps his light for
 *          the whole of the fall, which is the only reason he is the last
 *          thing visible — then out across LAST.
 *
 * Built once, frozen, and indexed by stage. Fourteen entries of eight hexes.
 */
function buildStages(alarmColour) {
  const red = typeof alarmColour === 'string' && /^#[0-9a-fA-F]{6}$/.test(alarmColour)
    ? alarmColour : DIRE_FALLBACK;
  const out = [];
  for (let k = 0; k < STAGE_COUNT; k++) {
    // sat   1 -> 0 across DRAIN. Hits zero ON beat two and stays there.
    // field 1 -> 0 across FALL. Hits zero ON beat three, which is what makes
    //       the hero the only lit thing in the frame at that moment rather
    //       than merely the brightest.
    // plate 1 until beat three, then out across LAST. He keeps his light for
    //       the whole of the fall. That is the entire reason he is last.
    const sat = k < DRAIN_STAGES ? (DRAIN_STAGES - k) / DRAIN_STAGES : 0;
    const fieldK = k < DRAIN_STAGES ? 1
      : Math.max(0, (DRAIN_STAGES + FALL_STAGES - k) / FALL_STAGES);
    const plateK = k < DRAIN_STAGES + FALL_STAGES ? 1
      : (STAGE_COUNT - 1 - k) / LAST_STAGES;

    // Colour first, light second, and the two must not interfere — which they
    // do by default, because mixing a dark grey toward #ff3b46 makes it
    // BRIGHTER, so a drain that only lerped the hue would dim the frame by a
    // quarter before the fall had started and the ordering claim would be a
    // lie. keepLum pulls the tinted value back to the luminance it had before
    // the tint, so DRAIN moves chroma and nothing else. Measured: chroma falls
    // to 23% across the first gap while mean luminance holds.
    const tint = (hex, amount) => keepLum(hex, mix(hex, red, sat * amount));
    const dim = (hex, lum) => mix(VOID, hex, clamp(lum, 0, 1));

    const lit = tint(FIELD_LIT, FIELD_TINT);
    out.push(Object.freeze({
      stage: k,
      sat: Math.round(sat * 1000) / 1000,
      field: Math.round(fieldK * 1000) / 1000,
      plate: Math.round(plateK * 1000) / 1000,
      // Three field tones, brightest at the middle where the hero is.
      inner: dim(lit, fieldK),
      middle: dim(lit, fieldK * 0.66),
      outer: dim(lit, fieldK * 0.34),
      plateRamp: Object.freeze(GREY.map(hex => dim(tint(hex, PLATE_TINT), plateK))),
    }));
  }
  return Object.freeze(out);
}

const stageCache = new Map();
const STAGE_CACHE_MAX = 8;

export function stagesFor(alarmColour = DIRE_FALLBACK) {
  const key = String(alarmColour || DIRE_FALLBACK);
  let rows = stageCache.get(key);
  if (!rows) { rows = buildStages(key); capCache(stageCache.set(key, rows), STAGE_CACHE_MAX); }
  return rows;
}

/** Which of the fourteen stages `t` is on.
 *
 * REDUCED MOTION gets four of them instead of fourteen, on the beats, and the
 * iris is not drawn at all. The event still reads — the colour goes, then the
 * light goes, then the hero goes, then nothing — but nothing moves between
 * states and nothing flashes, which is the thing the setting exists to answer.
 * The beats are untouched: a heartbeat is sound, not motion, and it is the
 * whole of what the player was asked for. */
const REDUCED_STAGES = Object.freeze([0, DRAIN_STAGES + 4, STAGE_COUNT - 2, STAGE_COUNT - 1]);

export function stageAt(t, reduced = false) {
  const ms = clamp(num(t, 0), 0, Infinity);
  if (reduced) {
    if (ms < FALL_FROM) return REDUCED_STAGES[0];
    if (ms < LAST_FROM) return REDUCED_STAGES[1];
    if (ms < BLACK_FROM) return REDUCED_STAGES[2];
    return REDUCED_STAGES[3];
  }
  if (ms < FALL_FROM) {
    return clamp(Math.floor((ms - DRAIN_FROM) / (FALL_FROM - DRAIN_FROM) * DRAIN_STAGES),
                 0, DRAIN_STAGES - 1);
  }
  if (ms < LAST_FROM) {
    return DRAIN_STAGES + clamp(
      Math.floor((ms - FALL_FROM) / (LAST_FROM - FALL_FROM) * FALL_STAGES),
      0, FALL_STAGES - 1);
  }
  if (ms < BLACK_FROM) {
    return DRAIN_STAGES + FALL_STAGES + clamp(
      Math.floor((ms - LAST_FROM) / LAST_MS * LAST_STAGES), 0, LAST_STAGES - 1);
  }
  return STAGE_COUNT - 1;
}

export function paletteAt(t, { reduced = false, alarmColour = DIRE_FALLBACK } = {}) {
  return stagesFor(alarmColour)[stageAt(t, reduced)];
}

/** The iris radius in STAGE space. Continuous, because geometry is not what the
 *  fifteen-colour budget is about, and `u*u` because vision narrows slowly and
 *  then all at once. Open before the fall, shut after it. */
export function irisAt(t, reduced = false) {
  if (reduced) return R_OPEN;
  const ms = num(t, 0);
  if (ms <= FALL_FROM) return R_OPEN;
  if (ms >= LAST_FROM) return R_SHUT;
  const u = (ms - FALL_FROM) / (LAST_FROM - FALL_FROM);
  return Math.round(R_OPEN + (R_SHUT - R_OPEN) * (u * u));
}

/* -------------------------------------------------------------- the plate
 *
 * The hero, re-rendered into five tones by LUMINANCE RANK rather than by fixed
 * thresholds. Rank, because a hero in black plate and a hero in a pale shirt
 * occupy completely different parts of the luminance scale and fixed cuts would
 * flatten one of them to a silhouette. Ranking the distinct tones he actually
 * has and spreading those across the five steps keeps his internal shading — a
 * lit shoulder stays lighter than a shadowed one — at every kit in the game,
 * and it still cannot produce a sixth colour.
 *
 * Computed once per look and kept. It is an index mask, not an image: nothing
 * here is redrawn when the stage changes, only repainted through a new ramp.
 */
const plateCache = new Map();
const PLATE_CACHE_MAX = 32;

function plateFor(img, key) {
  if (!img || !img.width || !img.height) return null;
  const cached = plateCache.get(key);
  if (cached) return cached;

  let data = null;
  try {
    const ctx = img.getContext && img.getContext('2d');
    data = ctx && ctx.getImageData(0, 0, img.width, img.height);
  } catch (e) { data = null; }
  if (!data || !data.data) return null;

  const w = img.width, h = img.height;
  const px = data.data;
  const lum = new Int32Array(w * h).fill(-1);
  const seen = new Set();
  for (let i = 0, p = 0; i < px.length; i += 4, p++) {
    if (!px[i + 3]) continue;
    // Rec.601 on 0..255, integer, so the ranking is bit-identical run to run.
    const L = (px[i] * 299 + px[i + 1] * 587 + px[i + 2] * 114) / 1000 | 0;
    lum[p] = L;
    seen.add(L);
  }
  const tones = Array.from(seen).sort((a, b) => a - b);
  const rank = new Map();
  tones.forEach((L, i) => rank.set(L, tones.length < 2
    ? PLATE_STEPS - 1
    : Math.round((i / (tones.length - 1)) * (PLATE_STEPS - 1))));

  const idx = new Uint8Array(w * h).fill(255);   // 255 = nothing here
  let opaque = 0;
  for (let p = 0; p < lum.length; p++) {
    if (lum[p] < 0) continue;
    idx[p] = rank.get(lum[p]);
    opaque++;
  }
  const plate = { w, h, idx, opaque, tones: tones.length };
  capCache(plateCache.set(key, plate), PLATE_CACHE_MAX);
  return plate;
}

/** The hero this screen is about. `look` is the same dict the overworld and the
 *  battle stage already pass to sprites.heroFrame, so he is wearing what he
 *  died in. Facing down: the last thing the player sees is their own character
 *  looking back at them. */
export function heroFor(look) {
  return heroFrame('down', 0, look || { weapon: 'sword', emote: 'neutral' }, 'idle');
}

/* Keyed by object identity as well as by content. The host hands the same look
 * object in on every frame of the sequence, and rebuilding a fourteen-part
 * string 240 times to look up a cache entry that has not moved is the kind of
 * garbage that only shows up on the machine of the person who cannot afford a
 * better one. */
const keyCache = new WeakMap();

function lookKey(look) {
  if (!look || typeof look !== 'object') return 'down|0|idle|none';
  const hit = keyCache.get(look);
  if (hit) return hit;
  const o = look;
  const key = ['down', 0, 'idle', o.weapon, o.emote, o.cloak, o.tunic, o.skin, o.hair,
               o.boot, o.trim, o.metal,
               Array.isArray(o._pieces) ? o._pieces.map(p => `${p && p.piece}${p && p.at}`).join(',') : '',
               o._weapon ? `${o._weapon.key}${o._weapon.rung}` : ''].join('|');
  keyCache.set(look, key);
  return key;
}

/* ------------------------------------------------------------------ drawing
 *
 * Into a 256x224 buffer — fx.js's own stage space — and then blitted to the
 * host canvas at a whole-number scale. Two reasons, and neither is nostalgia:
 * the hero lands on the exact pixel he was already standing on, and the colour
 * count is a property of the buffer rather than of whatever size the player's
 * window happens to be.
 *
 * fillRect only. raster.mjs accepts arc/ellipse/fill and ignores them on
 * purpose — "a stub that pretended to implement them would be lying about
 * coverage" — so an iris drawn with ctx.arc would be a circle no harness in
 * this project can see. Scanline spans are also simply what the machine this
 * game is pretending to be would have done.
 */
let buffer = null;

/** Allocate the buffer and build the plate BEFORE a render loop starts.
 *  stub.mjs records any canvas allocated inside enterLoop(), and it is right
 *  to: a death screen that allocates on its first frame stutters on the frame
 *  the player is paying the most attention to. */
function ensureBuffer() {
  if (buffer) return buffer;
  const canvas = document.createElement('canvas');
  canvas.width = STAGE.w; canvas.height = STAGE.h;
  const ctx = canvas.getContext('2d');
  if (ctx) ctx.imageSmoothingEnabled = false;
  buffer = { canvas, ctx };
  return buffer;
}

export function warmDeath({ look = null, alarmColour = DIRE_FALLBACK } = {}) {
  ensureBuffer();
  stagesFor(alarmColour);
  if (look) plateFor(heroFor(look), lookKey(look));
  return buffer;
}

/** One filled circle, as horizontal spans. */
function disc(ctx, cx, cy, r, colour) {
  if (!(r > 0)) return;
  ctx.fillStyle = colour;
  const y0 = Math.max(0, Math.ceil(cy - r));
  const y1 = Math.min(STAGE.h - 1, Math.floor(cy + r));
  for (let y = y0; y <= y1; y++) {
    const dy = y - cy;
    const half = Math.floor(Math.sqrt(Math.max(0, r * r - dy * dy)));
    const x0 = Math.max(0, cx - half);
    const x1 = Math.min(STAGE.w - 1, cx + half);
    if (x1 >= x0) ctx.fillRect(x0, y, x1 - x0 + 1, 1);
  }
}

/** The figure, painted through the stage's five-step ramp. Runs of equal index
 *  on a row are one fillRect, which turns a 16x24 sprite into a few dozen
 *  rects instead of 384. */
function drawPlate(ctx, plate, ramp, ox, oy, scale = FIGURE_SCALE) {
  if (!plate || !plate.opaque) return 0;
  const S = Math.max(1, scale | 0);
  let rects = 0;
  for (let y = 0; y < plate.h; y++) {
    let x = 0;
    while (x < plate.w) {
      const v = plate.idx[y * plate.w + x];
      if (v === 255) { x++; continue; }
      let run = 1;
      while (x + run < plate.w && plate.idx[y * plate.w + x + run] === v) run++;
      ctx.fillStyle = ramp[v];
      // One source pixel is an S x S square of the buffer, the same whole
      // number fx.js blits the rig at. A run is one rect however long it is.
      ctx.fillRect(ox + x * S, oy + y * S, run * S, S);
      rects++;
      x += run;
    }
  }
  return rects;
}

/** The shadow he is standing in. Three rows, painted in the plate's own darkest
 *  step so it costs nothing from the budget, and it leaves with him. */
const SHADOW_ROWS = Object.freeze([11, 15, 11].map(n => n * FIGURE_SCALE));

function drawShadow(ctx, ramp) {
  ctx.fillStyle = ramp[0];
  for (let i = 0; i < SHADOW_ROWS.length; i++) {
    const half = SHADOW_ROWS[i] >> 1;
    ctx.fillRect(HERO_CX - half, HERO_FOOT - FIGURE_SCALE + i * FIGURE_SCALE,
                 half * 2 + 1, FIGURE_SCALE);
  }
}

/* ------------------------------------------------------------- the letters
 *
 * A 3x5 uppercase face, authored here because there is no shared one and
 * because this file draws with fillRect and nothing else. That is not a
 * stylistic tic: raster.mjs accepts fillText and paints nothing, so a death
 * screen whose words went through ctx.fillText would be words no harness in
 * this project can count — and the words are the point of the screen.
 *
 * 3x5 on a 256-wide frame is 4 pixels of advance and 56 characters to a line
 * inside a 16-pixel margin, which is what the wrap below is built on. At the
 * shipped stage scales that is 8 to 12 device pixels per capital.
 */
const GLYPH_W = 3, GLYPH_H = 5, ADVANCE = 4, LINE_H = 8;
const FONT = {
  A: ['###', '#.#', '###', '#.#', '#.#'], B: ['##.', '#.#', '##.', '#.#', '##.'],
  C: ['###', '#..', '#..', '#..', '###'], D: ['##.', '#.#', '#.#', '#.#', '##.'],
  E: ['###', '#..', '##.', '#..', '###'], F: ['###', '#..', '##.', '#..', '#..'],
  G: ['###', '#..', '#.#', '#.#', '###'], H: ['#.#', '#.#', '###', '#.#', '#.#'],
  I: ['###', '.#.', '.#.', '.#.', '###'], J: ['..#', '..#', '..#', '#.#', '###'],
  K: ['#.#', '#.#', '##.', '#.#', '#.#'], L: ['#..', '#..', '#..', '#..', '###'],
  M: ['#.#', '###', '###', '#.#', '#.#'], N: ['##.', '#.#', '#.#', '#.#', '#.#'],
  O: ['###', '#.#', '#.#', '#.#', '###'], P: ['###', '#.#', '###', '#..', '#..'],
  Q: ['###', '#.#', '#.#', '###', '..#'], R: ['###', '#.#', '##.', '#.#', '#.#'],
  S: ['###', '#..', '###', '..#', '###'], T: ['###', '.#.', '.#.', '.#.', '.#.'],
  U: ['#.#', '#.#', '#.#', '#.#', '###'], V: ['#.#', '#.#', '#.#', '#.#', '.#.'],
  W: ['#.#', '#.#', '###', '###', '#.#'], X: ['#.#', '#.#', '.#.', '#.#', '#.#'],
  Y: ['#.#', '#.#', '.#.', '.#.', '.#.'], Z: ['###', '..#', '.#.', '#..', '###'],
  0: ['###', '#.#', '#.#', '#.#', '###'], 1: ['.#.', '##.', '.#.', '.#.', '###'],
  2: ['###', '..#', '###', '#..', '###'], 3: ['###', '..#', '###', '..#', '###'],
  4: ['#.#', '#.#', '###', '..#', '..#'], 5: ['###', '#..', '###', '..#', '###'],
  6: ['###', '#..', '###', '#.#', '###'], 7: ['###', '..#', '..#', '..#', '..#'],
  8: ['###', '#.#', '###', '#.#', '###'], 9: ['###', '#.#', '###', '..#', '###'],
  ' ': ['...', '...', '...', '...', '...'],
  '.': ['...', '...', '...', '...', '.#.'], ',': ['...', '...', '...', '.#.', '#..'],
  "'": ['.#.', '.#.', '...', '...', '...'], '-': ['...', '...', '###', '...', '...'],
  '%': ['#.#', '..#', '.#.', '#..', '#.#'], ':': ['...', '.#.', '...', '.#.', '...'],
  '?': ['###', '..#', '.#.', '...', '.#.'], '!': ['.#.', '.#.', '.#.', '...', '.#.'],
  '(': ['.#.', '#..', '#..', '#..', '.#.'], ')': ['.#.', '..#', '..#', '..#', '.#.'],
  '/': ['..#', '..#', '.#.', '#..', '#..'], '+': ['...', '.#.', '###', '.#.', '...'],
};
const MISSING = FONT['?'];

/** One line of text, left edge at x, top at y. Runs of set cells on a row
 *  become one fillRect, the same way drawPlate works. */
function drawText(ctx, text, x, y, colour) {
  ctx.fillStyle = colour;
  const s = String(text).toUpperCase();
  let painted = 0;
  for (let i = 0; i < s.length; i++) {
    const g = FONT[s[i]] || MISSING;
    const gx = x + i * ADVANCE;
    for (let r = 0; r < GLYPH_H; r++) {
      const row = g[r];
      let c = 0;
      while (c < GLYPH_W) {
        if (row[c] !== '#') { c++; continue; }
        let run = 1;
        while (c + run < GLYPH_W && row[c + run] === '#') run++;
        ctx.fillRect(gx + c, y + r, run, 1);
        painted += run;
        c += run;
      }
    }
  }
  return painted;
}

const textWidth = (s) => String(s).length * ADVANCE - 1;

/** Greedy word wrap to `cols` characters. */
function wrap(text, cols) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const out = [];
  let line = '';
  for (const w of words) {
    if (!line) { line = w; continue; }
    if (line.length + 1 + w.length <= cols) line += ' ' + w;
    else { out.push(line); line = w; }
  }
  if (line) out.push(line);
  return out.length ? out : [''];
}

/* THE WORDS, PAINTED.
 *
 * renderDeath has always TAKEN opts.words — main.js has been passing seq.words
 * on every frame since the screen was written — and never read them. Nothing in
 * web/ consumed deathLines(), KEPT_LINE or NO_SAVE_LINE either, so the sequence
 * ended on an empty frame: 0 non-void pixels at t = 3000, 3910, 5000 and 9000,
 * and a real death at 1440x940 held on pure black until the player pressed a
 * key. The KEPT_LINE — which the note above calls the point of the screen, and
 * the one honest reassurance it can offer — never reached anybody.
 *
 * Painted into the 256x224 buffer rather than onto the host canvas, so the text
 * inherits the colour budget and the whole-number blit like everything else.
 * MARGIN keeps it inside the safe area at both ends. */
const WORD_MARGIN = 16;
const WORD_COLS = Math.floor((STAGE.w - WORD_MARGIN * 2 + 1) / ADVANCE);   // 56

function drawWords(ctx, words) {
  if (!words || typeof words !== 'object') return 0;
  const title = str(words.title);
  const lines = Array.isArray(words.lines) ? words.lines : [];
  /* Lay the whole block out first so it can be centred vertically inside the
   * safe area rather than starting at a number somebody liked. */
  const block = [];
  if (title) block.push({ text: title, colour: GREY[4], gap: LINE_H });
  for (const entry of lines) {
    const text = str(entry && entry.text);
    if (!text) continue;
    for (const row of wrap(text, WORD_COLS)) block.push({ text: row, colour: GREY[3], gap: 0 });
    block.push({ text: '', colour: GREY[3], gap: 0 });      // one blank between entries
  }
  if (str(words.skipHint)) block.push({ text: str(words.skipHint), colour: GREY[2], gap: LINE_H });
  if (!block.length) return 0;

  let h = 0;
  for (const row of block) h += LINE_H + row.gap;
  const top = Math.max(STAGE.safeTop + 4,
                       Math.round(STAGE.safeTop + (STAGE.safeH - h) / 2));
  let y = top, painted = 0;
  for (const row of block) {
    y += row.gap;
    if (row.text) {
      const x = Math.round((STAGE.w - textWidth(row.text)) / 2);
      painted += drawText(ctx, row.text, x, y, row.colour);
    }
    y += LINE_H;
  }
  return painted;
}

/** Paint one frame of the sequence into the STAGE-sized (256x224) buffer. */
export function renderDeath(t, opts = {}) {
  const ms = clamp(num(t, 0), 0, Infinity);
  const reduced = !!opts.reduced;
  const rows = stagesFor(opts.alarmColour);
  const st = rows[stageAt(t, reduced)];
  const buf = ensureBuffer();
  const ctx = buf && buf.ctx;
  if (!ctx) return null;

  // The field. In reduced motion there is no iris, so the whole frame is the
  // one tone and the stepping alone carries the event.
  ctx.fillStyle = reduced ? st.inner : st.outer;
  ctx.fillRect(0, 0, STAGE.w, STAGE.h);
  if (!reduced) {
    const r = irisAt(t, reduced);
    disc(ctx, HERO_CX, HERO_CY, r, st.middle);
    disc(ctx, HERO_CX, HERO_CY, Math.round(r * RING), st.inner);
  }

  // The hero, on top, and last to go.
  let plate = null;
  if (st.plate > 0 && opts.look) {
    plate = plateFor(heroFor(opts.look), lookKey(opts.look));
    // The shadow belongs to the figure. No figure, no shadow: a shadow under
    // nothing is the kind of thing that survives a whole project.
    if (plate && plate.opaque) {
      drawShadow(ctx, st.plateRamp);
      drawPlate(ctx, plate, st.plateRamp,
                HERO_CX - Math.round(plate.w * FIGURE_SCALE / 2),
                HERO_FOOT - plate.h * FIGURE_SCALE);
    }
  }

  // And then the words, which is what the whole three beats were for.
  let words = 0;
  if (ms >= WORDS_AT && opts.words) words = drawWords(ctx, opts.words);
  return { stage: st, plate, reduced, words };
}

/** Blit the buffer to the host canvas at a whole-number scale, letterboxed in
 *  the field's own outermost tone so the screen reads as one surface rather
 *  than as a picture with a border. */
export function blitDeath(ctx, w, h, st) {
  if (!ctx || !buffer || !buffer.canvas) return false;
  const W = Math.max(1, Math.round(num(w, STAGE.w)));
  const H = Math.max(1, Math.round(num(h, STAGE.h)));
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = (st && st.outer) || VOID;
  ctx.fillRect(0, 0, W, H);
  const scale = Math.max(1, Math.floor(Math.min(W / STAGE.w, H / STAGE.h)));
  const dw = STAGE.w * scale, dh = STAGE.h * scale;
  ctx.drawImage(buffer.canvas, Math.round((W - dw) / 2), Math.round((H - dh) / 2), dw, dh);
  return true;
}

/* --------------------------------------------------------------- the words
 *
 * D: tell them plainly where they are waking and what it cost, and one line
 * about what they kept.
 *
 * NOT ONE NUMBER IN HERE IS INVENTED. Every figure on this screen comes out of
 * the `report` gauntlet/death.py hands over; a field that is absent removes its
 * clause, and a clause with nothing left in it removes its line. A death screen
 * that guesses at what an afternoon was worth is worse than one that stays
 * quiet about it, because the player will believe it. Anything that needs a
 * unit — a duration, a percentage — arrives from Python already formatted, so
 * that this file never has to decide what "61" means.
 *
 * THE KEPT LINE IS THE POINT OF THE SCREEN and it is unconditional. It carries
 * no numbers precisely so that nothing can take it away: it is true whether or
 * not death.py answered, whether or not there was a save to wake at, and it is
 * the one reassurance this screen can offer that is completely honest.
 *
 * It says nothing about readiness, nothing about the hold-out set and nothing
 * about any problem. finalexam.sealed() is the one capability check in this
 * game and a death screen is not a second one.
 */
export const KEPT_LINE =
  'Your record did not move. Attempts, skills, mastery and the review schedule '
  + 'are where you left them. Dying costs you the afternoon, never the evidence.';

export const NO_SAVE_LINE =
  'There is no save behind you yet, so you start from the beginning — with '
  + 'everything you have already learned.';

function joinClauses(parts) {
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0];
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '');

/* THE REPORT, which gauntlet/death.py owns and this file only renders.
 *
 *   {
 *     wake: {                      // null, or absent, if there is no save yet
 *       slot:   'auto3',           // saves.slot_id — never shown to the player
 *       label:  'Entered the Sunken Vault',   // saves.describe().name
 *       region: 'Sunken Vault',
 *       reason: 'region_entered',  // one of saves.AUTOSAVE_EVENTS
 *       saved_at: 1757600000.0,
 *     },
 *     cost: {                      // everything death is allowed to take
 *       playtime: '12m 22s',       // PREFORMATTED — saves.format_playtime()
 *       gold: 340, items: 3, levels: 0,
 *     },
 *     kept: {                      // everything it is not
 *       attempts: 1841, skills: 26,
 *       mastery: '61%',            // PREFORMATTED — this file must not decide
 *                                  //  what a bare 61 means
 *       due: 12,
 *     },
 *   }
 *
 * Anything carrying a unit arrives already formatted, so that the only thing
 * this file ever does with a number is print it. Anything missing removes its
 * clause; a line with no clauses left does not appear. `name` is accepted
 * wherever `label` is, because that is what saves.py calls the column.
 *
 * `kept` must never carry anything derived from the sealed hold-out set beyond
 * these counts. finalexam.sealed() is the one capability check in this game and
 * a death screen is not a second one.
 */
export function deathLines(report) {
  const r = report && typeof report === 'object' ? report : {};
  const wake = r.wake && typeof r.wake === 'object' ? r.wake : null;
  const cost = r.cost && typeof r.cost === 'object' ? r.cost : {};
  const kept = r.kept && typeof r.kept === 'object' ? r.kept : {};
  const lines = [];

  // WHERE. Two short sentences rather than one long one, because the save
  // point's own label is a sentence already — saves.py names an autosave after
  // the event that made it, "Entered the Sunken Vault" — and folding that into
  // a clause produces "you wake at entered the Sunken Vault". Kept apart, any
  // label death.py can hand over reads correctly, including a name the player
  // typed themselves into a manual slot. `label` is the field; `name` is
  // accepted as an alias because that is what saves.py calls its own column.
  const label = str(wake && (wake.label || wake.name));
  const region = str(wake && wake.region);
  if (region && label) lines.push({ id: 'where', text: `You wake in ${region}. Last save: ${label}.` });
  else if (region) lines.push({ id: 'where', text: `You wake in ${region}.` });
  else if (label) lines.push({ id: 'where', text: `You wake at your last save: ${label}.` });
  else lines.push({ id: 'where', text: NO_SAVE_LINE });

  // WHAT IT COST. Only what was actually handed over.
  const spent = [];
  if (typeof cost.playtime === 'string' && cost.playtime) spent.push(cost.playtime + ' of play');
  if (Number.isFinite(cost.gold) && cost.gold > 0) spent.push(`${cost.gold} gold`);
  if (Number.isFinite(cost.items) && cost.items > 0) spent.push(plural(cost.items, 'item', 'items'));
  if (Number.isFinite(cost.levels) && cost.levels > 0) spent.push(plural(cost.levels, 'level', 'levels'));
  if (spent.length) lines.push({ id: 'cost', text: `It cost you ${joinClauses(spent)}.` });

  // WHAT YOU KEPT. The prose is unconditional; the counts underneath it are not.
  lines.push({ id: 'kept', text: KEPT_LINE });
  const held = [];
  if (Number.isFinite(kept.attempts)) held.push(plural(kept.attempts, 'attempt', 'attempts'));
  if (Number.isFinite(kept.skills)) held.push(plural(kept.skills, 'skill', 'skills'));
  if (typeof kept.mastery === 'string' && kept.mastery) held.push(`mastery ${kept.mastery}`);
  if (Number.isFinite(kept.due)) held.push(plural(kept.due, 'card due', 'cards due'));
  if (held.length) lines.push({ id: 'record', text: `${joinClauses(held)}. Still yours.` });

  return {
    title: 'YOU GET BACK UP',
    lines,
    // E. There is always a way out of this screen, and it never depends on
    // there having been a save, on death.py having answered, or on the player
    // having watched the animation.
    actions: Object.freeze([Object.freeze({ id: 'wake', label: 'GET UP', primary: true })]),
    skipHint: 'Any key skips.',
  };
}

/* ------------------------------------------------------------------- skip
 *
 * "No animation they cannot skip after the first time." Read exactly: the first
 * death in a playthrough plays its three beats, because a beat the player is
 * allowed to dismiss before hearing it is a beat that never lands and this one
 * has to land once. From the second death on, the skip is live from the first
 * frame.
 *
 * INPUT IS NEVER SWALLOWED, even on that first death. The skip is armed the
 * moment the third beat has sounded, so the longest a key press can go
 * unanswered is the 2.4 seconds of the beats themselves — and the host should
 * acknowledge a press before then by showing the hint, never by ignoring it.
 * `seen` is the host's count out of saved state, not a flag hidden in here: a
 * module that remembered how many times you had died would be keeping a second
 * copy of something the save file owns.
 */
export function skipArmedAt(seen = 0) {
  return num(seen, 0) >= 1 ? 0 : DEATH_BEAT_AT[DEATH_BEAT_AT.length - 1];
}

/* ----------------------------------------------------------------- effect */

class Death {
  constructor(opts = {}) {
    this.opts = opts || {};
    this.reduced = !!this.opts.reduced;
    this.look = this.opts.look || null;
    this.alarmColour = this.opts.alarmColour || DIRE_FALLBACK;
    this.seen = num(this.opts.seen, 0);
    this.report = this.opts.report || null;
    this.words = deathLines(this.report);
    this.total = DEATH_MS;
    this.t = 0;
    this.active = false;
    this.skipped = false;
    // `blocking` means PAUSE THE GAME UNDER THIS, and nothing else. It is not a
    // claim about input, and the flag beside it says so out loud, because a
    // host reading `blocking` and deciding to stop listening to the keyboard is
    // exactly the bug rule E exists to prevent. This module installs no
    // listener, owns no timer and cannot swallow a key; the host keeps the
    // keyboard and asks `canSkip` what a press should do.
    this.blocking = true;
    this.capturesInput = false;
  }

  begin(opts = {}) {
    Object.assign(this.opts, opts || {});
    if (opts && 'reduced' in opts) this.reduced = !!opts.reduced;
    if (opts && opts.look) this.look = opts.look;
    if (opts && opts.alarmColour) this.alarmColour = opts.alarmColour;
    if (opts && 'seen' in opts) this.seen = num(opts.seen, 0);
    if (opts && 'report' in opts) { this.report = opts.report; this.words = deathLines(this.report); }
    warmDeath({ look: this.look, alarmColour: this.alarmColour });
    this.t = 0;
    this.active = true;
    this.skipped = false;
    return this;
  }

  update(dt) {
    if (!this.active) return this;
    // A frame clock produces NaN, negatives and six-figure jumps after a tab
    // wakes up. None of them may move this backwards or off the end.
    const step = clamp(num(dt, 0), 0, 0.25) * 1000;
    this.t = clamp(this.t + step, 0, this.total);
    if (this.t >= this.total) this.active = false;
    return this;
  }

  /** Land on an arbitrary t. Used by a scrubber, and by a host that drives
   *  from an absolute timestamp rather than a frame delta.
   *
   *  It settles `active` on exactly the same condition `update` does, and that
   *  is not tidiness. `active` is the flag the host loops on, so a seek that
   *  landed on the end state while still claiming to be running is a host loop
   *  that never exits — the screen finished, the words are up, and the game
   *  underneath it never comes back. Seeking BACKWARDS does not restart it: a
   *  cancelled or finished screen stays stopped, and only begin() starts one. */
  seek(ms) {
    this.t = clamp(num(ms, 0), 0, this.total);
    if (this.t >= this.total) this.active = false;
    return this;
  }

  /** Land on the end state from any t. Idempotent, and safe to call before the
   *  skip is armed — arming is the host's policy question, answered by
   *  skipArmedAt(), and refusing here would be a second place deciding it. */
  skip() {
    this.t = this.total;
    this.active = false;
    this.skipped = true;
    return this;
  }

  cancel() { this.active = false; return this; }

  get phase() { return phaseAt(this.t).id; }
  get beats() { return beatsBy(this.t); }
  get showWords() { return this.t >= WORDS_AT; }
  /** Whether a keypress should skip. The arming delay is a policy about the
   *  FIRST death — the three beats have to land once — but it is measured in a
   *  clock, and a screen that is no longer running has no clock left to wait
   *  for. Refusing to release a stopped screen is indefensible however it
   *  stopped, so `!active` releases unconditionally.
   *
   *  This is advice to the host, not a gate: `skip()` itself is ungated and
   *  works from any state, which is the guarantee rule E actually rests on. */
  get canSkip() { return !this.active || this.t >= skipArmedAt(this.seen); }
  get palette() { return paletteAt(this.t, { reduced: this.reduced, alarmColour: this.alarmColour }); }

  draw(ctx, w, h) {
    if (!ctx) return false;
    const out = renderDeath(this.t, {
      reduced: this.reduced, look: this.look, alarmColour: this.alarmColour,
    });
    return blitDeath(ctx, w, h, out && out.stage);
  }
}

export function createDeath(opts = {}) { return new Death(opts); }

/* ------------------------------------------------------------ housekeeping */

export function clearDeathCache() {
  stageCache.clear();
  plateCache.clear();
  buffer = null;
}

export function deathStats() {
  return {
    version: DEATHFX_VERSION,
    stages: stageCache.size, STAGE_CACHE_MAX,
    plates: plateCache.size, PLATE_CACHE_MAX,
    buffer: buffer ? `${STAGE.w}x${STAGE.h}` : null,
    stageCount: STAGE_COUNT,
    maxColours: MAX_COLOURS,
  };
}

/* ------------------------------------------------------------ measurement
 *
 * The claims this file makes about itself, as numbers anybody can recount off a
 * real raster: how many distinct colours each phase paints, how much of the
 * frame is still lit, and how much of what is left is the hero. The ordering
 * claim — colour before light — is the `sat` and `field` columns, and it is
 * only true if `sat` reaches zero while `field` is still one.
 */
export function measureDeath({ look = null, reduced = false,
                               alarmColour = DIRE_FALLBACK, samples = 40 } = {}) {
  const rows = [];
  const marks = [];
  for (let i = 0; i <= samples; i++) marks.push(Math.round((DEATH_MS * i) / samples));
  for (const at of DEATH_BEAT_AT) marks.push(at);
  marks.push(FALL_FROM - 1, LAST_FROM - 1, BLACK_FROM, WORDS_AT);
  const seen = new Set();
  for (const t of marks.sort((a, b) => a - b)) {
    if (seen.has(t)) continue;
    seen.add(t);
    const out = renderDeath(t, { look, reduced, alarmColour });
    if (!out) continue;
    rows.push({
      t,
      phase: phaseAt(t).id,
      beats: beatsBy(t),
      stage: out.stage.stage,
      sat: out.stage.sat,
      field: out.stage.field,
      plate: out.stage.plate,
      iris: irisAt(t, reduced),
    });
  }
  return rows;
}
