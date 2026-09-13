/* The green that takes everything — the Unmaking, rendered.
 *
 * WHAT THIS IS
 * ------------
 * transform.js is the player's sequence: raise, charge, discharge, reveal,
 * hold, four point two seconds, a white-out, chrome lettering, a title. It is
 * an ACHIEVEMENT, and it is shaped like one — anticipation, then a bang.
 *
 * This is its mirror, and mirroring it properly meant inverting every single
 * decision in it rather than recolouring the same beats green:
 *
 *   transform.js                    unmakingfx.js
 *   ------------------------------  ------------------------------------------
 *   4.20s                           15.60s. Slower than anyone expects, because
 *                                   he is not casting at you, he is processing
 *                                   a return. Impatience is the intended feeling.
 *   the CHARGE is the long act       there is no charge. It is already happening
 *                                   when you notice it.
 *   a white-out on the discharge     nothing ever flashes. Not once. The peak
 *                                   screen alpha in this file is 0.30.
 *   everything arrives at once       one thing leaves at a time, each with its
 *                                   own small departure.
 *   the figure is lit from inside    the figure stops being lit at all.
 *   ends on a title card             ends on a man with nothing on him.
 *
 * HE IS NEVER LOUD. docs/09-story-bible.md §1 and gauntlet/antagonist.py: the
 * most dangerous thing in the game does not shout. So there is no modal here,
 * no letterbox, no full-screen flourish, no lettering, and no beat that covers
 * the player's own sprite. He arrives where you already were. Everything below
 * is weather: `blocking` is a property on the effect and it is false, forever,
 * and nothing in this module reads input or can be waited on.
 *
 * GREEN IS THE INDEX
 * ------------------
 * §6.2 and §2.VIII: the small green glass sphere with a number floating in it
 * that has been turning up in unrelated quests since Chapter II is a POINTER,
 * and every story it touches is about somebody being found. So the green in
 * this file is not a colour choice. It is him, and the player has been looking
 * at it for nine chapters.
 *
 * palette.js has no ramp for it, and `venom` is the wrong green — a warm olive
 * authored for poison, and none of this may read as a status effect. So the
 * ramp is DEFINED HERE.
 *
 * The base step is NOT invented. gauntlet/finale.py line 137 spells the Green
 * Index #6ee08a and calls it "the only green in here"; web/js/kingui.js quotes
 * the same hex as KING_GREEN and rims his body in it where every other body in
 * the cast rims in sprites.RIM_LIGHT #ffab5e. INDEX_GREEN[3] is that value
 * exactly, and the other four steps are it taken down toward black and up
 * toward white, so the arc on the hero's shoulder and the sphere on the shelf
 * in the ending are the same object at different exposures. The agreement is a
 * MEASUREMENT rather than a promise: scripts/verify/unmakingfx.mjs asserts
 * INDEX_GREEN_HEX against kingui.KING_GREEN and fails if either pass ever
 * touches its own copy.
 *
 * If palette.js later grows an `index` ramp, this becomes a re-export of it and
 * nothing else in the file changes.
 *
 * THE BEATS
 * ---------
 * gauntlet/unmaking.py does not exist yet. When it does, it owns this order and
 * these words, and the intended integration is `createUnmaking({ beats })` with
 * its table passed straight in — BEATS below is the fallback, authored to the
 * brief's own ordering, and `beatsFrom()` is the adapter. The order is not
 * arbitrary and the last two entries are the argument:
 *
 *   NOTICE     nothing is taken. The edges go green.
 *   COMPANION  the animal's shape goes out.
 *   RUNEWORK   the weapon's runework dims.
 *   TRIM       the armour's trim goes grey.
 *   COLOUR     the cloak and the tunic follow it.
 *   RIM        the rim light fails. LAST, because the rim light is the thing
 *              that has made the hero look lit since the first frame of the
 *              first chapter, and taking it is the only step a player will
 *              feel without being able to name.
 *   PLAIN      the green goes out of the air and he stands there with
 *              nothing on him. gauntlet/unmaking.py's last two acts are "the
 *              figure is lit by nothing" and "no figure, no him", so the final
 *              frame of this sequence is the plain hero in an ordinary field:
 *              no gear tint, no rim, no arcs, no wash. He does not linger.
 *
 * HOW THE SPRITE ACTUALLY CHANGES, and why it is measurable
 * ---------------------------------------------------------
 * Not a tint and not an alpha fade. sprites.heroPalette() hands back the exact
 * hex for every glyph the hero rig paints, so each dispossession is an EXACT
 * COLOUR SUBSTITUTION over the rendered frame: the pixels that were the trim
 * become neutral, the pixels that were the rim become the body around them,
 * and every other pixel is untouched, byte for byte. That makes "the armour's
 * trim goes grey" a number — scripts/verify/unmaking.mjs counts it off the
 * raster — instead of a claim, and it guarantees the alpha mask never moves, so
 * the hero's silhouette is the one thing the King does not get.
 *
 * The neutrals are a five-step ramp shared by every step, so the substitutions
 * COLLAPSE colours over the sequence: the plain frame paints strictly fewer
 * distinct values than the dressed one — measured, 9 against 14.
 *
 * It is not monotone, and saying so would be easier than saying what actually
 * happens. ONE step can cost a colour before it saves several: a substitution
 * whose neutral is not yet anywhere on the sprite adds that step while removing
 * a hex that some other glyph is still using, so RUNEWORK goes 14 -> 15 on the
 * bare look before TRIM and COLOUR take it down to 9. Fifteen is the budget and
 * fifteen is the measured ceiling, on the worst of 1152 plates — the margin at
 * that one beat is zero rather than one, which is worth knowing before anyone
 * adds a sixteenth hex to the hero rig. scripts/verify/unmakingfx.mjs and
 * scripts/verify/unmakingworld.mjs both count it off rendered pixels.
 *
 * RULES OBSERVED
 * --------------
 * No Math.random and no Date.now anywhere: every varying quantity is hashed
 * from an integer. No allocation in a draw path: contours, masks and plates are
 * capped Maps built by prewarm(), the arc state is one preallocated Float32Array
 * and every paint is a fillRect. prefers-reduced-motion is honoured by freezing
 * every time-varying term to its mid-beat value, which keeps the DISPOSSESSION
 * — the content — and drops the motion.
 *
 * Nothing in here is imported by spellfx.js, transform.js or bosses.js, and it
 * changes no exported signature anywhere. It only reads sprites.js.
 *
 * WHAT THIS IS NOT: web/js/kingui.js
 * ---------------------------------
 * They are two halves of the same brief and neither is the other.
 *
 *   kingui.js is HIM ARRIVING. His sprite, his panel, his words, his index
 *   sphere, and a green wash capped at WASH_CAP = 0.09 that says something is
 *   looking at you. It fires on progression, all game, dozens of times.
 *
 *   This file is HIM TAKING. It fires once. No sprite of his, no words, no
 *   panel, nothing to read and nothing to dismiss — and the screen layer is
 *   capped at 0.30, which is 3.3x his presence wash and still 0.62 of what
 *   transform.js spends on its white-out alone.
 *
 * That ratio is the whole relationship: the thing that has been quietly
 * watching for nine chapters gets meaningfully louder exactly once, and even
 * then stays under the apex hunter's telegraph for four of its seven beats.
 * Both files spell the Green Index #6ee08a and the harness proves it.
 */
/* NO IMPORTS, deliberately.
 *
 * sprites.js is the rig and this file needs it — heroFrame() to render, and
 * heroPalette() to know which hex is the trim. It is passed IN, at call time,
 * by the host that already holds it. That buys three things: this module cannot
 * be half of an import cycle with anything (spellfx.js mirrors fx.js's geometry
 * for exactly that reason and says so), a harness can hand it a stub rig, and
 * there is no way for this file to quietly become a second owner of the hero. */

export const UNMAKING_VERSION = '1.0.0';

/* ------------------------------------------------------------------ colour */

/* THE GREEN INDEX. Five steps, deep to specular, anchored on the one hex the
 * rest of the game already spells.
 *
 *   [3] is gauntlet/finale.py's #6ee08a — THE SPHERE. Not a near miss, not an
 *       eyedropped screenshot, the same six characters. Anything drawing the
 *       Green Index as an object should use INDEX_GREEN_HEX and nothing else.
 *   [4] is that taken toward white, so a one-pixel arc on a 16px sprite still
 *       reads at 3x scale, which is the only scale this is ever seen at.
 *   [0..2] are it taken toward black, for the screen layer, which has to sit
 *       under a night tint and a vignette and still be green rather than grey.
 */
export const INDEX_GREEN = Object.freeze([
  '#0e1d12', '#22452b', '#428653', '#6ee08a', '#bff1cc',
]);

/* The sphere itself, named, so nothing has to remember an index. Identical to
 * web/js/kingui.js KING_GREEN and to gauntlet/finale.py's "accent" by
 * construction; the harness proves it rather than trusting this comment. */
export const INDEX_GREEN_HEX = INDEX_GREEN[3];

/* What the gear becomes. Five cold neutrals on the ambient fill hue rather than
 * true grey, because a pure grey sitting in a world lit at palette.KEY_HUE 65
 * reads as a rendering fault and the last frame has to look DELIBERATE. Every
 * dispossession lands on this same ramp, which is what makes the colour count
 * fall instead of rise. */
export const PLAIN = Object.freeze([
  '#131319', '#292930', '#47474f', '#70707a', '#a4a4ae',
]);

/* ------------------------------------------------------------------- beats */

/* Seconds. Long on purpose — see the header table. The three middle takings are
 * the same length as each other so the sequence reads as a procedure being
 * worked through rather than as a build. RIM is longer than the takings before
 * it, and PLAIN is the longest thing in the file. */
/* THE STANDALONE TABLE, and when it is the right one.
 *
 * unmaking.py's spell is cast once, in the last chamber, and runs for nearly
 * two minutes. This module also has to work on the WORLD MAP, where he turns up
 * where you already were, does this, and is gone — and where a hundred and
 * fifteen seconds is not weather, it is a hostage situation. So BEATS is the
 * short form: the same dispossessions in the order the sprite can show them,
 * fifteen point six seconds, no words, nothing to dismiss.
 *
 * It is still three point seven times transform.js and it is still slower than
 * anyone expects, which is the instruction. Use beatsFromCinematic() in the
 * chamber and this everywhere else. */
export const BEATS = Object.freeze([
  Object.freeze({ id: 'NOTICE',    span: 2.20, takes: Object.freeze([]),            note: 'the edges go green' }),
  Object.freeze({ id: 'COMPANION', span: 2.20, takes: Object.freeze(['companion']), note: "the companion's shape goes out" }),
  Object.freeze({ id: 'RUNEWORK',  span: 2.20, takes: Object.freeze(['weapon']),    note: "the weapon's runework dims" }),
  Object.freeze({ id: 'TRIM',      span: 2.20, takes: Object.freeze(['trim']),      note: 'the armour trim goes grey' }),
  Object.freeze({ id: 'COLOUR',    span: 2.20, takes: Object.freeze(['garb']),      note: 'the cloak and tunic follow' }),
  Object.freeze({ id: 'RIM',       span: 2.60, takes: Object.freeze(['rim']),       note: 'the rim light fails' }),
  Object.freeze({ id: 'PLAIN',     span: 2.00, takes: Object.freeze([]),            note: 'he stands there' }),
]);

export const UNMAKING_SECONDS = BEATS.reduce((s, b) => s + b.span, 0);   // 15.60

/* Cumulative start time of each beat, precomputed so nothing divides in draw. */
const BEAT_AT = (() => {
  const out = new Float64Array(BEATS.length + 1);
  for (let i = 0; i < BEATS.length; i++) out[i + 1] = out[i] + BEATS[i].span;
  return out;
})();

/* Which beat a clock is in, and how far through it. Returns the shared object:
 * this is called every frame and a fresh {beat,k} per frame is exactly what
 * scripts/verify/cap.mjs is built to catch. */
const _WHERE = { beat: 0, k: 0, id: 'NOTICE' };
export function beatAt(t) {
  let i = 0;
  while (i < BEATS.length - 1 && t >= BEAT_AT[i + 1]) i++;
  _WHERE.beat = i;
  _WHERE.k = clamp((t - BEAT_AT[i]) / BEATS[i].span, 0, 1);
  _WHERE.id = BEATS[i].id;
  return _WHERE;
}

/* gauntlet/unmaking.py's table, when it lands, in this module's shape. It is
 * allowed to name fewer beats, more beats, or different spans; the only thing
 * this adapter insists on is that `takes` is one of the five things the sprite
 * knows how to lose, because a beat that takes something the rig cannot show is
 * a beat the player does not see happen. */
const TAKEABLE = { companion: 1, weapon: 1, trim: 1, garb: 1, rim: 1 };

/* `takes` is a string, an array of strings, or nothing. An array because
 * gauntlet/unmaking.py's BUILD beat takes "the armour, the class, the numbers
 * you bought with gold" in ONE beat, and splitting it into two on this side
 * would put the sprite half a beat out of step with the words he is saying
 * while it happens. Normalised to a frozen array here so nothing downstream has
 * to ask which of the three shapes it was handed. */
function normaliseTakes(v) {
  const list = Array.isArray(v) ? v : (v ? [v] : []);
  const out = [];
  for (const t of list) if (TAKEABLE[t] && out.indexOf(t) < 0) out.push(t);
  return Object.freeze(out);
}

export function beatsFrom(rows) {
  if (!Array.isArray(rows) || !rows.length) return BEATS;
  const out = [];
  for (const r of rows) {
    if (!r) continue;
    const span = Number.isFinite(+r.span) && +r.span > 0 ? +r.span : 2.2;
    out.push(Object.freeze({
      id: String(r.id || `BEAT_${out.length}`).toUpperCase(),
      span, takes: normaliseTakes(r.takes),
      note: typeof r.note === 'string' ? r.note : '',
      crutch: r.crutch || null,
    }));
  }
  return out.length ? Object.freeze(out) : BEATS;
}

/* ------------------------------------------- driven by gauntlet/unmaking.py
 *
 * THIS IS THE PATH THAT SHOULD BE USED IN THE LAST CHAMBER. unmaking.py owns
 * the spell — what is taken, in what order, in how many seconds, and the words
 * said over each one — and it says so in its own header: fourteen crutches out
 * of finalexam.CRUTCHES, ladder rung ascending, the Hand last because it is the
 * only one he asks for rather than removes. None of that is re-decided here.
 *
 * Four of its fourteen takes have something to remove from the HERO'S SPRITE,
 * and the rest happen on the interface, which other modules own. The mapping is
 * data rather than a branch so it can be read, and each entry is justified out
 * of unmaking.py's own `leaves` text:
 *
 *   PET            "The animal is simply not there any more."
 *   BUILD          "The armour, the class, the numbers you bought with gold.
 *                   What is underneath is what I came for."  -> trim, then the
 *                   cloth under it, which is what "underneath" means on a
 *                   sixteen-pixel sprite.
 *   ITEMS          "Charms and whetstones... bought rather than learned." The
 *                   whetstone is the thing that kept the edge, so what goes is
 *                   the blade's runework, not the blade.
 *   OBLIGING_HAND  the gauntlet lifting off finger by finger, last, unhurried.
 *                   The rim light goes with it, and the rim light is the thing
 *                   that has made this character look lit since Chapter I.
 *
 * Everything else contributes a beat with nothing taken from the sprite: the
 * green is in the air, the hero is unchanged, and the frame is a held shot of a
 * person while something is removed from somewhere else. That is not filler.
 * Ten of the fourteen takings being invisible ON HIM is the point of the scene.
 */
export const SPRITE_FOR_CRUTCH = Object.freeze({
  PET: Object.freeze(['companion']),
  BUILD: Object.freeze(['trim', 'garb']),
  ITEMS: Object.freeze(['weapon']),
  OBLIGING_HAND: Object.freeze(['rim']),
});

/* `cin` is gauntlet/unmaking.cinematic() as JSON, or just its `beats` array.
 * Its `at` and `seconds` are used verbatim, including the long REACH before the
 * first take and the whole of STRIP + REVEAL + HOLD after the last one, which
 * become the opening NOTICE and the closing PLAIN. Measured against the real
 * table: 14 takes, first at 13.37s, last ending at 84.50s, 115.29s in total. */
export function beatsFromCinematic(cin) {
  const rows = Array.isArray(cin) ? cin : (cin && Array.isArray(cin.beats) ? cin.beats : null);
  if (!rows || !rows.length) return BEATS;
  const total = (cin && cin.timing && +cin.timing.unattended_seconds) || 0;
  const out = [];
  const first = +rows[0].at || 0;
  if (first > 0.05) {
    out.push({ id: 'NOTICE', span: first, takes: null,
               note: 'he reaches; the edges go green; nothing is taken yet' });
  }
  let end = first;
  for (const r of rows) {
    const span = +r.seconds > 0 ? +r.seconds
      : (+r.take_seconds || 0) + (+r.read_seconds || 0) || 2.2;
    out.push({ id: String(r.crutch || `TAKE_${out.length}`), span,
               takes: SPRITE_FOR_CRUTCH[r.crutch] || null,
               crutch: r.crutch || null,
               note: r.leaves || r.motif || '' });
    end = (+r.end > 0 ? +r.end : end + span);
  }
  const tail = total > end ? total - end : 2.0;
  out.push({ id: 'PLAIN', span: tail, takes: null,
             note: 'strip, reveal, silence. He stands there and the green is still in the air' });
  return beatsFrom(out);
}

/* --------------------------------------------------------------- utilities */

function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

/* transform.js's integer hash, same constants, so the two sequences scatter
 * their detail the same way and the world looks like one hand made it. */
function hash(n) {
  let h = (n * 374761393 + 668265263) >>> 0;
  h = (h ^ (h >>> 13)) >>> 0;
  h = (h * 1274126177) >>> 0;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

const easeIn = t => t * t;
const easeOut = t => 1 - (1 - t) * (1 - t);

function parseHex(hex) {
  const h = String(hex || '#000000').replace('#', '');
  const n = parseInt(h.length === 3
    ? h[0] + h[0] + h[1] + h[1] + h[2] + h[2] : h.slice(0, 6), 16);
  return Number.isFinite(n) ? n >>> 0 : 0;
}

/* Rec.709. The gear collapses onto the neutral of matching brightness, which is
 * why a dark cloak does not turn into a light grey and give the player a
 * completely different figure at the moment they are supposed to recognise the
 * same one. */
function lumaOf(rgb) {
  return (0.2126 * ((rgb >> 16) & 255) + 0.7152 * ((rgb >> 8) & 255)
        + 0.0722 * (rgb & 255)) / 255;
}

const PLAIN_RGB = PLAIN.map(parseHex);

/* Each taking lands inside its own WINDOW of the neutral ramp, and the windows
 * are not a style choice — they are the colour budget.
 *
 * Fifteen colours is counted off the RENDERED FRAME, which means it has to hold
 * in the middle of the sequence and not just at the ends. A dressed hero paints
 * fourteen. The first taking therefore has a budget of one: if dimming the
 * weapon frees one value and introduces three, the frame is at sixteen and the
 * rule is broken by a transition that lasts two seconds and that nobody thought
 * to measure. Measured, at first attempt, it was exactly that: seventeen.
 *
 * So RUNEWORK is allowed two neutrals and no more, and every window afterwards
 * is a subset of the ones before plus at most one new step, which makes the
 * count MONOTONICALLY FALLING from the second beat on. The rim gets a single
 * value, because a rim light that fails into three different greys is a rim
 * light that is still describing a surface.
 */
const WINDOW = {
  /* ONE value, and the budget chose it rather than taste.
   *
   * Measured: a dressed hero in full plate with a Runed blade paints fourteen
   * distinct colours, and the blade is cut from the SAME metal as the pauldron,
   * so dimming it frees nothing — every colour it gives up is still being used
   * somewhere else on the sprite. That leaves a headroom of exactly one, and a
   * two-value window took the frame to sixteen on 18 of 336 plates.
   *
   * It turns out to be the right read anyway. Runework is the bright marking on
   * a blade; a blade that drops to a single flat value is a blade that has
   * stopped catching anything, which is the thing the beat is called. */
  weapon: [1, 1],
  trim:   [1, 3],
  garb:   [0, 2],
  rim:    [2, 2],     // one value. It stops being an edge.
};

function neutralOf(rgb, bias, window) {
  let q = Math.round(lumaOf(rgb) * 4.35 - 0.18) + (bias | 0);
  const w = window || [0, 4];
  return PLAIN_RGB[clamp(q, w[0], w[1])];
}

/* ------------------------------------------------------------------ caches
 *
 * Working sets, not archives — sprites.js's own rule, same shape. A hero on a
 * map asks for at most a couple of dozen of these (four facings, four walk
 * frames, seven beats) and a cap plus oldest-out keeps an hour of play flat. */
function capCache(map, max) {
  while (map.size > max) {
    const oldest = map.keys().next();
    if (oldest.done) break;
    map.delete(oldest.value);
  }
  return map;
}
const contourCache = new Map();   const CONTOUR_MAX = 96;
const plateCache = new Map();     const PLATE_MAX = 320;
const maskCache = new Map();      const MASK_MAX = 96;

export function clearUnmakingCache() {
  contourCache.clear(); plateCache.clear(); maskCache.clear();
}
export function unmakingStats() {
  return { contours: contourCache.size, plates: plateCache.size,
           masks: maskCache.size, CONTOUR_MAX, PLATE_MAX, MASK_MAX,
           version: UNMAKING_VERSION };
}

function make(w, h) {
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  return { canvas, ctx };
}

/* Read a sprite's pixels once. Returns null rather than throwing when the host
 * cannot give them back — a tainted canvas, a zero-size image, or a harness
 * that records calls instead of pixels. Every caller below treats null as "draw
 * the original sprite, unchanged", so the worst case for a browser that refuses
 * is that the hero keeps his gear and the screen layer still plays. */
function pixelsOf(img) {
  if (!img || !img.width || !img.height) return null;
  try {
    const { ctx } = make(img.width, img.height);
    ctx.drawImage(img, 0, 0);
    const d = ctx.getImageData(0, 0, img.width, img.height);
    return (d && d.data && d.data.length === img.width * img.height * 4) ? d : null;
  } catch (e) { return null; }
}

/* ------------------------------------------------------------------ masks
 *
 * Which pixels belong to which thing, decided by EXACT COLOUR against the
 * palette the rig itself used. sprites.heroPalette() is the single source; this
 * module never guesses a hex.
 *
 * Priority matters and it is the one place the beat order shows up in the
 * pixels: RIM WINS OVER EVERYTHING. A lit edge on the blade is part of the rim
 * and not part of the weapon, so it survives the runework dimming and fails at
 * the end with every other lit edge in the sprite. That is the difference
 * between the rim light failing as an EVENT and it dribbling away across four
 * separate steps where nobody notices it.
 *
 * `pal` is whatever shape sprites.heroPalette returns; missing keys are simply
 * absent from the lookup, so a rig change that drops a glyph degrades to "that
 * material is not taken" instead of to a crash.
 */
const ROLE = { none: 0, rim: 1, weapon: 2, trim: 3, garb: 4 };

const ROLE_GLYPHS = {
  rim:    ['R', 'r'],
  trim:   ['g', 'A', 'm', 'w', 'M', 'W'],
  garb:   ['c', 'C', 'v', 'L', 'B', 'u', 'd', 'K', 't', 'T', 'b'],
};

/* The weapon's footprint is the one thing colour cannot answer, because the
 * blade is painted out of the same metal as the pauldron. So it is measured:
 * render the same hero with `weapon: null` and take the pixels that differ.
 * That is a true footprint rather than a guess, it costs one cached render, and
 * it is the same technique scripts/verify/hero.mjs uses to prove a helm is a
 * helm and not a recolour. */
function weaponFootprint(sprites, opts, facing, frame, pose, base) {
  if (!base || opts.weapon == null) return null;
  let bare;
  try {
    bare = sprites.heroFrame(facing, frame, { ...opts, weapon: null }, pose);
  } catch (e) { return null; }
  const bp = pixelsOf(bare);
  if (!bp || bp.width !== base.width || bp.height !== base.height) return null;
  const n = base.width * base.height;
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const k = i * 4;
    if (base.data[k] !== bp.data[k] || base.data[k + 1] !== bp.data[k + 1]
      || base.data[k + 2] !== bp.data[k + 2] || base.data[k + 3] !== bp.data[k + 3]) out[i] = 1;
  }
  return out;
}

/* One byte per pixel saying which dispossession owns it. */
function roleMap(sprites, img, opts, facing, frame, pose, key) {
  const ck = `${key}|roles`;
  if (maskCache.has(ck)) return maskCache.get(ck);
  const px = pixelsOf(img);
  let built = null;
  if (px) {
    let pal = null;
    try { pal = sprites.heroPalette(opts); } catch (e) { pal = null; }
    const colourRole = new Map();
    if (pal) {
      // Lowest priority first, so a hex shared by two roles ends up owned by
      // the one that must survive longest.
      for (const role of ['garb', 'trim', 'rim']) {
        for (const glyph of ROLE_GLYPHS[role]) {
          const hex = pal[glyph];
          if (typeof hex !== 'string') continue;
          colourRole.set(parseHex(hex), ROLE[role]);
        }
      }
      // The outline and the person are never taken. He keeps his face.
      for (const glyph of ['o', 'O', 'e', 's', 'S', 'N', 'h', 'H']) {
        const hex = pal[glyph];
        if (typeof hex === 'string') colourRole.set(parseHex(hex), ROLE.none);
      }
    }
    const wf = weaponFootprint(sprites, opts, facing, frame, pose, px);
    const n = img.width * img.height;
    built = { w: img.width, h: img.height, role: new Uint8Array(n),
              alpha: new Uint8Array(n), counts: [0, 0, 0, 0, 0] };
    for (let i = 0; i < n; i++) {
      const k = i * 4;
      if (!px.data[k + 3]) continue;
      built.alpha[i] = 1;
      const rgb = (px.data[k] << 16) | (px.data[k + 1] << 8) | px.data[k + 2];
      let role = colourRole.has(rgb) ? colourRole.get(rgb) : ROLE.none;
      if (role !== ROLE.rim && wf && wf[i]) role = ROLE.weapon;
      built.role[i] = role;
      built.counts[role]++;
    }
  }
  maskCache.set(ck, built);
  capCache(maskCache, MASK_MAX);
  return built;
}

/* ------------------------------------------------------------------ plates
 *
 * The hero at a given stage of dispossession, as a canvas the caller draws
 * INSTEAD of the sprite it already had. Same size, same alpha, same silhouette
 * — only the paint is different, which is the whole point: what he loses is
 * what he was wearing and what was lighting him, never his shape. */
const TAKE_BIT = { companion: 0, weapon: 1, trim: 2, garb: 4, rim: 8 };

/* The set of things taken by the end of beat `b`, as a bitmask. Everything is
 * cumulative and nothing ever comes back. */
function bitsOf(takes) {
  let mask = 0;
  if (!takes) return 0;
  if (typeof takes === 'string') return TAKE_BIT[takes] || 0;
  for (const t of takes) if (TAKE_BIT[t] !== undefined) mask |= TAKE_BIT[t];
  return mask;
}
function takenAt(beats, b) {
  let mask = 0;
  for (let i = 0; i <= b && i < beats.length; i++) mask |= bitsOf(beats[i].takes);
  return mask;
}
function beatTakes(beat) {
  const t = beat.takes;
  return typeof t === 'string' ? !!t : !!(t && t.length);
}

export function heroPlate(sprites, img, opts, facing, frame, pose, key, taken) {
  if (!img || !taken) return img;
  const ck = `${key}|${taken}`;
  if (plateCache.has(ck)) return plateCache.get(ck);
  const roles = roleMap(sprites, img, opts, facing, frame, pose, key);
  const px = roles ? pixelsOf(img) : null;
  if (!roles || !px) { plateCache.set(ck, img); capCache(plateCache, PLATE_MAX); return img; }

  const n = img.width * img.height;
  for (let i = 0; i < n; i++) {
    const k = i * 4;
    if (!px.data[k + 3]) continue;
    const role = roles.role[i];
    let out = -1;
    const rgb = (px.data[k] << 16) | (px.data[k + 1] << 8) | px.data[k + 2];
    if (role === ROLE.rim && (taken & TAKE_BIT.rim)) {
      // The rim does not go grey, it goes OUT. A rim pixel is the lit face of
      // the body underneath it, so it becomes the body: one step down the
      // neutral ramp from where its own brightness sits, which is the value the
      // unlit side of the same surface already has.
      out = neutralOf(rgb, -1, WINDOW.rim);
    } else if (role === ROLE.weapon && (taken & TAKE_BIT.weapon)) {
      // Dimmed, not greyed. Runework stops answering before the metal stops
      // being metal, and two steps is the smallest drop that survives being
      // looked at on a 16px sprite at 3x.
      out = neutralOf(rgb, -2, WINDOW.weapon);
    } else if (role === ROLE.trim && (taken & TAKE_BIT.trim)) {
      out = neutralOf(rgb, 0, WINDOW.trim);
    } else if (role === ROLE.garb && (taken & TAKE_BIT.garb)) {
      out = neutralOf(rgb, 0, WINDOW.garb);
    }
    if (out >= 0) {
      px.data[k] = (out >> 16) & 255;
      px.data[k + 1] = (out >> 8) & 255;
      px.data[k + 2] = out & 255;
    }
  }
  const { canvas, ctx } = make(img.width, img.height);
  ctx.putImageData(px, 0, 0);
  plateCache.set(ck, canvas);
  capCache(plateCache, PLATE_MAX);
  return canvas;
}

/* ---------------------------------------------------------------- contours
 *
 * The arcs have to FOLLOW the silhouette, not be drawn across it, so they need
 * the outline as an ordered walk rather than as a set of edge pixels. This is a
 * Moore-neighbour trace over the alpha mask: start at the first boundary pixel
 * in raster order, step to the next boundary pixel clockwise from the direction
 * we arrived from, and keep going until the walk closes or dead-ends. Multiple
 * contours come out of it — a hero with a gap between his legs has three — and
 * they are kept in descending length, because an arc should spend most of its
 * time on the body and some of it on the blade, and never all of it on a
 * four-pixel hole between two boots.
 *
 * Deterministic by construction: no randomness, and raster order breaks every
 * tie the same way on every machine.
 */
const N8X = [1, 1, 0, -1, -1, -1, 0, 1];
const N8Y = [0, 1, 1, 1, 0, -1, -1, -1];

export function spriteContour(img, key) {
  const ck = `${key}|contour`;
  if (contourCache.has(ck)) return contourCache.get(ck);
  const px = pixelsOf(img);
  let built = null;
  if (px) {
    const w = px.width, h = px.height, n = w * h;
    const solid = new Uint8Array(n);
    for (let i = 0; i < n; i++) solid[i] = px.data[i * 4 + 3] ? 1 : 0;
    const edge = new Uint8Array(n);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        if (!solid[i]) continue;
        if (x === 0 || y === 0 || x === w - 1 || y === h - 1
          || !solid[i - 1] || !solid[i + 1] || !solid[i - w] || !solid[i + w]) edge[i] = 1;
      }
    }
    let edges = 0;
    for (let i = 0; i < n; i++) edges += edge[i];
    const seen = new Uint8Array(n);
    const loops = [];
    for (let start = 0; start < n; start++) {
      if (!edge[start] || seen[start]) continue;
      const xs = [], ys = [];
      let cur = start, dir = 0;
      for (let guard = 0; guard < n * 4; guard++) {
        seen[cur] = 1;
        xs.push(cur % w); ys.push((cur / w) | 0);
        let next = -1;
        const cx = cur % w, cy = (cur / w) | 0;
        for (let s = 0; s < 8; s++) {
          const d = (dir + 5 + s) & 7;
          const nx = cx + N8X[d], ny = cy + N8Y[d];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const ni = ny * w + nx;
          if (!edge[ni] || seen[ni]) continue;
          next = ni; dir = d; break;
        }
        if (next < 0) break;
        cur = next;
      }
      if (xs.length >= 4) {
        const pts = new Int16Array(xs.length * 2);
        for (let i = 0; i < xs.length; i++) { pts[i * 2] = xs[i]; pts[i * 2 + 1] = ys[i]; }
        loops.push(pts);
      }
    }
    loops.sort((a, b) => b.length - a.length);
    /* `covered` against `edges` is the honest number: a Moore walk closes when
     * it returns to a pixel it has already stood on, so a shape with a notch in
     * it yields a main loop plus stubs, and the stubs are kept (down to four
     * cells) rather than thrown away, because the notch in a hero's silhouette
     * is the gap between his boots and an arc that never crosses it is an arc
     * that has noticed where the sprite is easy to draw. */
    built = loops.length ? {
      loops, total: loops.reduce((s, l) => s + l.length / 2, 0), edges,
    } : null;
  }
  contourCache.set(ck, built);
  capCache(contourCache, CONTOUR_MAX);
  return built;
}

/* ----------------------------------------------------------------- the arcs
 *
 * Six of them, and six is the number because seven starts to look like a ring
 * and five leaves a side of the sprite dark. Each is a short run of contiguous
 * contour cells that slides along the outline: a hot core, a shoulder either
 * side, and then nothing. They are not lightning bolts — nothing forks, nothing
 * strikes, nothing arrives from off-screen. They crawl, which is a much worse
 * thing for something to do on a person.
 *
 * State lives in one preallocated Float32Array on the effect and is written by
 * step(); draw() only reads it. Nothing here allocates.
 */
const ARCS = 6;
const ARC_STRIDE = 3;    // [ phase, length, speed ]

function seedArcs(out, salt) {
  for (let i = 0; i < ARCS; i++) {
    const o = i * ARC_STRIDE;
    out[o] = hash(salt + i * 97);                       // phase along the contour
    out[o + 1] = 0.045 + hash(salt + i * 131) * 0.075;  // how much of it it covers
    out[o + 2] = 0.028 + hash(salt + i * 271) * 0.055;  // contours per second
  }
}

/* ------------------------------------------------------------- the effect */

/* How much index green is in the air at time t, 0..1. It comes up over NOTICE,
 * holds flat through every taking — he does not get louder as he takes more,
 * that is the character — and then, over the last beat, it LEAVES.
 *
 * The release is not a softening, it is the ending, and gauntlet/unmaking.py is
 * the module that says so rather than this one. Its REVEAL act: "the figure is
 * lit by nothing". Its HOLD act: "No lettering, no figure, no him." A last
 * frame that kept the green in it would be him lingering, and the one thing
 * every other decision in this file is built around is that he does not linger
 * — he arrives where you already were, takes what he came for, and is gone.
 *
 * So the final frame is the plain hero standing in an ordinary field: no gear
 * tint, no rim, no arcs on the silhouette and no wash on the screen. Both draw
 * paths gate on `air`, so this one function is the whole of that guarantee, and
 * scripts/verify/unmakingfx.mjs measures the last frame rather than believing
 * the paragraph. */
function airAt(beat, k, last) {
  if (beat === 0) return easeOut(k) * 0.86;
  // The release runs a little past the end of the beat's own curve so the last
  // tenth of it is flatly zero rather than one pixel of green on the final
  // frame: `air` reaches 0 at k = 0.9 and stays there.
  if (beat >= last) return 0.86 * (1 - easeIn(clamp(k / 0.9, 0, 1)));
  return 0.86;
}

class Unmaking {
  /* opts:
   *   sprites        the sprites.js module object. Passed in rather than bound
   *                  at import so a caller can hand over a stub and so this
   *                  file cannot accidentally become a second owner of the rig.
   *   look           the heroSprites() opts dict the hero is currently wearing.
   *   beats          gauntlet/unmaking.py's table, via beatsFrom().
   *   reducedMotion  freeze every time-varying term; keep every taking.
   */
  constructor(opts = {}) {
    const o = opts || {};
    this.sprites = o.sprites || null;
    this.look = o.look || {};
    this.beats = Array.isArray(o.beats) && o.beats.length ? o.beats : BEATS;
    this.reducedMotion = !!o.reducedMotion;
    this.duration = this.beats.reduce((s, b) => s + b.span, 0);
    this._at = new Float64Array(this.beats.length + 1);
    for (let i = 0; i < this.beats.length; i++) {
      this._at[i + 1] = this._at[i] + this.beats[i].span;
    }
    this.t = 0;
    this.beat = 0;
    this.beatId = this.beats[0].id;
    this.k = 0;
    this.done = false;
    /* HE MUST NEVER BLOCK. This is read by the host and it is a constant.
     * There is no branch below that sets it, no input path, and no promise a
     * caller can await: the sequence is weather and the player keeps walking
     * through it. */
    this.blocking = false;
    this.taken = 0;
    this._arcs = new Float32Array(ARCS * ARC_STRIDE);
    seedArcs(this._arcs, 17);
    this._phase = 0;
    this._plateKey = '';
    this._plateMask = -1;
    this._plate = null;
    this._warmed = false;
    this._where = { beat: 0, k: 0, id: this.beats[0].id };
  }

  /* Build every plate, mask and contour the sequence will ask for, before the
   * first frame. Canvas allocation inside a render loop is the thing
   * scripts/verify/cap.mjs exists to catch, and the only allocation this module
   * can possibly do is here. A caller that skips it still gets correct output —
   * it just pays for one canvas on each beat boundary instead of none. */
  prewarm(img, key, facing = 'down', frame = 0, pose = 'idle') {
    if (!this.sprites || !img) return 0;
    let built = 0;
    spriteContour(img, key);
    roleMap(this.sprites, img, this.look, facing, frame, pose, key);
    let mask = 0;
    for (let b = 0; b < this.beats.length; b++) {
      mask |= bitsOf(this.beats[b].takes);
      if (!mask) continue;
      const before = plateCache.size;
      heroPlate(this.sprites, img, this.look, facing, frame, pose, key, mask);
      if (plateCache.size !== before) built++;
    }
    this._warmed = true;
    return built;
  }

  /* Any OTHER sprite the sequence will trace — the companion, a mount, an NPC
   * the host decides to include. One call, before the first frame, for the same
   * reason prewarm exists: tracing a contour reads pixels, reading pixels needs
   * a scratch canvas, and a scratch canvas inside a render loop is the one
   * thing scripts/verify/cap.mjs is built to catch. Measured: without this the
   * 1200-frame loop allocated exactly one canvas, on the frame the companion
   * first had green on it. */
  prewarmSprite(img, key) {
    if (!img) return false;
    return !!spriteContour(img, key);
  }

  seek(seconds) {
    this.t = clamp(seconds, 0, this.duration);
    this._sync();
    return this;
  }

  step(dt) {
    if (this.done) return true;
    const d = Number.isFinite(dt) ? clamp(dt, 0, 0.25) : 0;
    this.t += d;
    if (!this.reducedMotion) this._phase += d;
    if (this.t >= this.duration) { this.t = this.duration; this.done = true; }
    this._sync();
    return this.done;
  }

  cancel() { this.done = true; this.t = this.duration; this._sync(); }

  _sync() {
    let i = 0;
    while (i < this.beats.length - 1 && this.t >= this._at[i + 1]) i++;
    this.beat = i;
    this.beatId = this.beats[i].id;
    this.taken = takenAt(this.beats, i);
    /* prefers-reduced-motion, and the whole of it.
     *
     * The clock still runs and the beats still arrive — the DISPOSSESSION is
     * the content and removing it would be removing the event, not the motion.
     * What is removed is everything continuous: `k` is pinned to the midpoint,
     * so every frame inside a beat is byte-identical to every other frame
     * inside it and the sequence becomes seven stills that cut from one to the
     * next. A player who cannot take the motion still watches him take the
     * companion, then the runework, then the trim, then the colour, then the
     * light, and is still left looking at a plain man.
     *
     * The midpoint rather than the end: it is the frame where the thing being
     * taken has gone AND the green is still gathered on the place it was, which
     * is the one frame of each beat that says what happened. */
    /* The last beat is the exception, and it is the only one. Its content is
     * not a taking, it is the ABSENCE that is left — the plain man, with the
     * green gone out of the air (gauntlet/unmaking.py's HOLD: "no figure, no
     * him"). Pinning that beat to its midpoint would leave a reduced-motion
     * player looking at a final still with green still on it, which is the one
     * frame in the sequence that must not have any. So the last beat's still is
     * its END state. Still exactly one still per beat, and the one that says
     * what happened. */
    this.k = !this.reducedMotion
      ? clamp((this.t - this._at[i]) / this.beats[i].span, 0, 1)
      : (i >= this.beats.length - 1 ? 1 : 0.5);
  }

  /* A taking reads as a DEPARTURE rather than a cut: green gathers on the thing
   * for the first half of its beat and the thing is simply not there for the
   * second. This returns how far through that departure we are, 0..1, for the
   * thing being taken right now. Under reduced motion it is pinned at 1 and the
   * substitution lands on the beat boundary, so the event still happens and
   * nothing moves. */
  departure() {
    if (this.reducedMotion) return 1;
    return easeOut(clamp(this.k * 1.9, 0, 1));
  }

  /* ------------------------------------------------------------ the sprite */

  /* Swap this in for the frame the caller was about to draw. Returns the very
   * same object it was given until something has actually been taken, so the
   * common case is a pointer comparison and nothing else. */
  heroImage(img, key, facing = 'down', frame = 0, pose = 'walk') {
    if (!img || !this.sprites) return img;
    // The take lands at the midpoint of its own beat, after the green has
    // gathered. Before that the hero still has the thing.
    let mask = this.taken;
    // The take lands at the midpoint of its own beat, after the green has
    // gathered. Under reduced motion `k` is pinned there, so the still is
    // always the frame after the taking — no branch needed.
    if (this.k < 0.5) mask &= ~bitsOf(this.beats[this.beat].takes);
    if (!mask) return img;
    // The steady state is the whole cost of this call, so it is two comparisons
    // and a return. Building `${key}|${mask}` here would allocate a string on
    // every frame of a fifteen-second sequence for no reason; the two halves of
    // the key are kept apart and compared apart.
    if (mask === this._plateMask && key === this._plateKey && this._plate) return this._plate;
    const plate = heroPlate(this.sprites, img, this.look, facing, frame, pose, key, mask);
    this._plateKey = key; this._plateMask = mask; this._plate = plate;
    return plate;
  }

  /* A. GREEN LIGHTNING ON THE SPRITE — arcs crawling over the hero's own
   * silhouette, following the outline. Call it immediately AFTER the sprite has
   * been drawn, at the same x/y the sprite was drawn at, inside whatever camera
   * transform the sprite went through. It paints single pixels on the sprite's
   * own grid, so it lands on the pixel lattice at any integer scale. */
  drawSprite(ctx, img, x, y, key) {
    if (!ctx || !img) return 0;
    const c = spriteContour(img, key);
    if (!c) return 0;
    const air = airAt(this.beat, this.k, this.beats.length - 1);
    if (air <= 0.01) return 0;
    // The arcs thicken on the beat that is taking something and thin back out
    // once it is gone. That is the only place in the file where the green does
    // anything at all, and it is worth five per cent of an alpha.
    const gather = beatTakes(this.beats[this.beat]) ? (1 - Math.abs(this.k * 2 - 1)) : 0;
    const strength = clamp(air * (0.62 + gather * 0.38), 0, 1);
    const phase = this.reducedMotion ? 0.5 : this._phase;
    const ox = Math.round(x), oy = Math.round(y);
    const prev = ctx.globalAlpha;
    let painted = 0;
    for (let li = 0; li < c.loops.length; li++) {
      const pts = c.loops[li];
      const len = pts.length >> 1;
      if (len < 6) continue;
      // Arcs are dealt across the loops rather than all onto the biggest one,
      // so the blade and the gap between the boots get their turn.
      for (let a = li; a < ARCS; a += c.loops.length) {
        const o = a * ARC_STRIDE;
        const run = Math.max(2, Math.round(len * this._arcs[o + 1]));
        const head = Math.floor(
          (this._arcs[o] + phase * this._arcs[o + 2] * (1 + (a & 1) * 0.6)) * len
        ) % len;
        for (let j = 0; j < run; j++) {
          const idx = (((head + j) % len) + len) % len;
          // Hot in the middle of the run, cold at both ends: a travelling
          // brightness rather than a lit segment with hard ends.
          const f = 1 - Math.abs((j / (run - 1 || 1)) * 2 - 1);
          const tone = f > 0.72 ? 4 : f > 0.34 ? 3 : 2;
          const alpha = strength * (0.30 + f * 0.70);
          if (alpha <= 0.02) continue;
          ctx.globalAlpha = prev * alpha;
          ctx.fillStyle = INDEX_GREEN[tone];
          ctx.fillRect(ox + pts[idx * 2], oy + pts[idx * 2 + 1], 1, 1);
          painted++;
        }
      }
    }
    ctx.globalAlpha = prev;
    return painted;
  }

  /* C, first taking. The companion's shape goes out. The host keeps drawing the
   * animal and multiplies its alpha by this; once it is zero the host stops
   * drawing it at all and it does not come back. Before its beat this is 1, so
   * a host that applies it unconditionally is correct all the way through. */
  companionAlpha() {
    const i = this._takeIndex('companion');
    if (i < 0 || this.beat < i) return 1;
    if (this.beat > i) return 0;
    if (this.reducedMotion) return this.k < 0.5 ? 1 : 0;
    return clamp(1 - easeIn(clamp(this.k * 1.35, 0, 1)), 0, 1);
  }

  /* The animal's own outline, lit and contracting, on the beat it leaves. Same
   * call shape as drawSprite: after the sprite, at the sprite's x/y. */
  drawCompanion(ctx, img, x, y, key) {
    const i = this._takeIndex('companion');
    if (i < 0 || this.beat !== i || !ctx || !img) return 0;
    const c = spriteContour(img, key);
    if (!c) return 0;
    const pts = c.loops[0];
    const len = pts.length >> 1;
    const k = this.reducedMotion ? 0.5 : this.k;
    // The lit arc is the WHOLE outline at the start of the beat and a single
    // cell at the end of it. The shape goes out; it does not fade out.
    const run = Math.max(1, Math.round(len * (1 - easeIn(k))));
    const head = Math.floor(this._arcs[0] * len);
    const prev = ctx.globalAlpha;
    const ox = Math.round(x), oy = Math.round(y);
    for (let j = 0; j < run; j++) {
      const idx = (head + j) % len;
      const f = j / (run || 1);
      ctx.globalAlpha = prev * clamp(0.35 + (1 - f) * 0.6, 0, 1);
      ctx.fillStyle = INDEX_GREEN[f < 0.25 ? 4 : 3];
      ctx.fillRect(ox + pts[idx * 2], oy + pts[idx * 2 + 1], 1, 1);
    }
    ctx.globalAlpha = prev;
    return run;
  }

  _takeIndex(what) {
    for (let i = 0; i < this.beats.length; i++) {
      const t = this.beats[i].takes;
      if (t === what) return i;
      if (t && t.length !== undefined && typeof t !== 'string' && t.indexOf(what) >= 0) return i;
    }
    return -1;
  }

  /* ------------------------------------------------------------ the screen
   *
   * A. THE SECOND LAYER. Three things, in this order, and all three of them are
   * fillRects — no gradient objects, because a gradient is an allocation per
   * frame and because banded light is what a 16-bit frame buffer would actually
   * have done.
   *
   *   1 THE EDGES GO GREEN. All four, inward, quiet. apex.js caps its telegraph
   *     at 0.26 and this sits just above it at 0.30, because the apex is a
   *     thing in the room and he is the room.
   *   2 THE GROUND LIGHTS FROM THE WRONG DIRECTION. Every character in this
   *     game is lit from low-left — sprites.RIM_LIGHT, one hot source, §8 — so
   *     the wrong direction is high-right, and a counter-shade is laid into the
   *     low-left where the light has always come from. Nothing about the scene
   *     changed. The lighting did, and the player will feel it before they work
   *     out what it was.
   *   3 THE CAST. A flat wash of the deep index green over the whole frame. It
   *     is the smallest of the three and it is the one that does the work: it
   *     takes the frame's midtones somewhere they have never been.
   *
   * Call it LAST, after the host's own vignette and night tint, with the camera
   * transform already restored — same place overworld.js calls
   * _drawApexOverlay, and for the same reason.
   */
  drawScreen(ctx, w, h) {
    if (!ctx || !(w > 0) || !(h > 0)) return 0;
    const air = airAt(this.beat, this.k, this.beats.length - 1);
    if (air <= 0.005) return 0;
    const pulse = this.reducedMotion ? 0.5
      : 0.5 + Math.sin(this._phase * 0.9) * 0.5;
    const prevAlpha = ctx.globalAlpha;

    // 1 — the edges.
    const BANDS = 8;
    const peak = Math.min(0.30, air * 0.30 * (0.82 + 0.18 * pulse));
    const insetX = Math.max(1, Math.round(w * 0.16 / BANDS));
    const insetY = Math.max(1, Math.round(h * 0.16 / BANDS));
    ctx.fillStyle = INDEX_GREEN[1];
    for (let b = 0; b < BANDS; b++) {
      const f = 1 - b / BANDS;
      ctx.globalAlpha = prevAlpha * peak * f * f;
      ctx.fillRect(0, b * insetY, w, insetY);
      ctx.fillRect(0, h - (b + 1) * insetY, w, insetY);
      ctx.fillRect(b * insetX, 0, insetX, h);
      ctx.fillRect(w - (b + 1) * insetX, 0, insetX, h);
    }

    // 2 — the wrong direction. A staircase of light down from the top-right,
    // and a counter-shade rising out of the bottom-left.
    const STEPS = 7;
    const stepW = Math.max(1, Math.round(w / (STEPS * 2)));
    const stepH = Math.max(1, Math.round(h / STEPS));
    ctx.fillStyle = INDEX_GREEN[2];
    for (let s = 0; s < STEPS; s++) {
      const f = 1 - s / STEPS;
      ctx.globalAlpha = prevAlpha * air * 0.085 * f;
      ctx.fillRect(w - stepW * (STEPS - s), 0, stepW * (STEPS - s), stepH * (s + 1));
    }
    ctx.fillStyle = INDEX_GREEN[0];
    for (let s = 0; s < STEPS; s++) {
      const f = 1 - s / STEPS;
      ctx.globalAlpha = prevAlpha * air * 0.075 * f;
      ctx.fillRect(0, h - stepH * (s + 1), stepW * (STEPS - s), stepH * (s + 1));
    }

    // 3 — the cast.
    ctx.globalAlpha = prevAlpha * air * 0.13;
    ctx.fillStyle = INDEX_GREEN[1];
    ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = prevAlpha * air * 0.05;
    ctx.fillStyle = INDEX_GREEN[3];
    ctx.fillRect(0, 0, w, h);

    ctx.globalAlpha = prevAlpha;
    return peak;
  }
}

/* The one constructor. Mirrors spellfx.createEffect's contract closely enough
 * that a host already driving spells has nothing new to learn: step(dt) returns
 * done, cancel() ends it, duration is in seconds and already honours reduced
 * motion by being the same length with nothing moving inside it. */
export function createUnmaking(opts = {}) {
  return new Unmaking(opts);
}

/* ------------------------------------------------------------- measurement
 *
 * C says MEASURE IT, so the measurement is an export rather than a line in a
 * harness: anyone can ask this module what each step actually costs the sprite,
 * including a debug overlay in the running game.
 *
 * Two numbers per beat, and they say different things on purpose:
 *
 *   pixelsChanged      RGBA cells that differ from the beat before. This is the
 *                      taking.
 *   silhouetteChanged  16x16 coverage cells that differ — colour thrown away,
 *                      sprites.js's own silhouetteAt test. For every beat that
 *                      touches the HERO this is zero, and it is SUPPOSED to be
 *                      zero: he loses his gear's colour and his light, and he
 *                      keeps his outline. The number that is not zero is the
 *                      companion's, because the companion is the one thing that
 *                      actually leaves.
 *   contourLit         silhouette cells the green is standing on that beat —
 *                      the outline measurement that is not zero for the hero.
 *   coloursAfter       distinct opaque RGB painted, off the raster. Falls over
 *                      the sequence — 14 to 9 — but not monotonically: see the
 *                      header on why RUNEWORK can cost one before TRIM and
 *                      COLOUR save five. The ceiling is fifteen and it is
 *                      measured, not assumed.
 */
export function measureUnmaking(sprites, img, opts = {}) {
  const o = opts || {};
  const look = o.look || {};
  const key = o.key || 'measure';
  const facing = o.facing || 'down';
  const frame = o.frame | 0;
  const pose = o.pose || 'idle';
  const beats = Array.isArray(o.beats) && o.beats.length ? o.beats : BEATS;
  const out = [];
  const px = pixelsOf(img);
  if (!px) return out;

  const count = (d) => {
    const seen = new Set();
    for (let i = 0; i < d.data.length; i += 4) {
      if (!d.data[i + 3]) continue;
      seen.add((d.data[i] << 16) | (d.data[i + 1] << 8) | d.data[i + 2]);
    }
    return seen.size;
  };
  const diff = (a, b) => {
    let n = 0;
    for (let i = 0; i < a.data.length; i += 4) {
      if (a.data[i] !== b.data[i] || a.data[i + 1] !== b.data[i + 1]
        || a.data[i + 2] !== b.data[i + 2] || a.data[i + 3] !== b.data[i + 3]) n++;
    }
    return n;
  };
  const cover = (d) => {
    const box = 16, w = d.width, h = d.height, g = new Uint8Array(box * box);
    for (let y = 0; y < box; y++) {
      for (let x = 0; x < box; x++) {
        const x0 = Math.floor(x * w / box), x1 = Math.max(x0 + 1, Math.floor((x + 1) * w / box));
        const y0 = Math.floor(y * h / box), y1 = Math.max(y0 + 1, Math.floor((y + 1) * h / box));
        let on = 0, tot = 0;
        for (let sy = y0; sy < y1 && sy < h; sy++) {
          for (let sx = x0; sx < x1 && sx < w; sx++) { tot++; if (d.data[(sy * w + sx) * 4 + 3]) on++; }
        }
        g[y * box + x] = (tot && on * 2 >= tot) ? 1 : 0;
      }
    }
    return g;
  };
  const coverDiff = (a, b) => { let n = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) n++; return n; };

  const contour = spriteContour(img, key);
  const contourCells = contour ? contour.total : 0;
  let prev = px, prevCover = cover(px), mask = 0;
  const roles = roleMap(sprites, img, look, facing, frame, pose, key);

  for (let b = 0; b < beats.length; b++) {
    const takes = beats[b].takes;
    mask |= bitsOf(takes);
    const plate = mask ? heroPlate(sprites, img, look, facing, frame, pose, key, mask) : img;
    const now = pixelsOf(plate) || px;
    const nowCover = cover(now);
    // How much of the outline the arcs are standing on at the midpoint of this
    // beat: the six runs, at their authored lengths, over this contour.
    let lit = 0;
    if (contour) {
      for (let a = 0; a < ARCS; a++) {
        const loop = contour.loops[a % contour.loops.length];
        lit += Math.max(2, Math.round((loop.length >> 1) * (0.045 + hash(17 + a * 131) * 0.075)));
      }
    }
    out.push({
      beat: b, id: beats[b].id,
      takes: (typeof takes === 'string' ? [takes] : (takes || [])).slice(),
      note: beats[b].note,
      seconds: +(beats[b].span).toFixed(2),
      pixelsChanged: diff(prev, now),
      silhouetteChanged: coverDiff(prevCover, nowCover),
      contourCells, contourLit: lit,
      coloursAfter: count(now),
    });
    prev = now; prevCover = nowCover;
  }
  if (roles) {
    out.roleCounts = { rim: roles.counts[ROLE.rim], weapon: roles.counts[ROLE.weapon],
                       trim: roles.counts[ROLE.trim], garb: roles.counts[ROLE.garb],
                       untouched: roles.counts[ROLE.none],
                       opaque: roles.counts.reduce((s, v) => s + v, 0) };
  }
  return out;
}

/* The neutral a given colour collapses to, exported so a harness or a debug
 * overlay can check the ramp without re-deriving the luma rule. */
export function plainFor(hex, bias = 0, what = null) {
  const v = neutralOf(parseHex(hex), bias, what ? WINDOW[what] : null);
  return '#' + v.toString(16).padStart(6, '0');
}

/* ==========================================================================
 * INTEGRATION — for whoever mounts this in overworld.js
 * ==========================================================================
 * This module draws. It owns no state in the world, reads no input, fetches
 * nothing, and cannot be waited on. `e.blocking` is false and there is no code
 * path that sets it.
 *
 * ONE-TIME, when the King begins:
 *
 *   import * as unmaking from './unmakingfx.js';
 *   this.unmaking = unmaking.createUnmaking({
 *     sprites,                        // the sprites.js module object
 *     look: this._heroLook,           // the same opts dict setEquipment() was given
 *     // IN THE LAST CHAMBER: hand over gauntlet/unmaking.cinematic() as JSON
 *     // and the whole sequence runs on ITS order and ITS timings — fourteen
 *     // takes, the first at 13.37s, the last ending at 84.50s, 115.29s total.
 *     beats: unmaking.beatsFromCinematic(await api.unmakingCinematic()),
 *     // ON THE WORLD MAP: omit `beats` entirely. The standalone table is the
 *     // same dispossessions in 15.60s with no words and nothing to dismiss.
 *     reducedMotion: this.reducedMotion,
 *   });
 *   // Warm every plate and contour BEFORE the first frame. Without this the
 *   // sequence still renders correctly and allocates one canvas per beat
 *   // boundary inside the draw loop, which is the thing cap.mjs fails on.
 *   for (const facing of ['down','up','left','right'])
 *     for (let f = 0; f < 4; f++)
 *       for (const pose of ['walk','idle'])
 *         this.unmaking.prewarm(heroFrameFor(facing,f,pose),
 *                               `hero|${facing}|${f}|${pose}`, facing, f, pose);
 *   if (companionImage) this.unmaking.prewarmSprite(companionImage, companionKey);
 *
 * PER FRAME, in update():      this.unmaking.step(dt);        // returns done
 *                              if (this.unmaking.done) this.unmaking = null;
 *
 * IN _gatherObjects(), the hero entry — swap the image, then paint the arcs at
 * the same coordinates the sprite was drawn at, inside the camera transform:
 *
 *   const key = `hero|${facing}|${p.frame % 4}|${p.moving ? 'walk' : 'idle'}`;
 *   const shown = u ? u.heroImage(img, key, facing, p.frame % 4,
 *                                 p.moving ? 'walk' : 'idle') : img;
 *   ctx.drawImage(shown, Math.round(p.px), Math.round(p.py + T - sprites.HERO_H));
 *   if (u) u.drawSprite(ctx, shown, Math.round(p.px),
 *                       Math.round(p.py + T - sprites.HERO_H), key);
 *
 * IN the companion entry, in the same place:
 *
 *   const a = u ? u.companionAlpha() : 1;
 *   if (a > 0) { ctx.globalAlpha = prev * a; ctx.drawImage(cimg, cx, cy);
 *                ctx.globalAlpha = prev; }
 *   if (u) u.drawCompanion(ctx, cimg, cx, cy, companionKey);
 *
 * AT THE END OF draw(), after the vignette and the night tint and after
 * ctx.restore(), in the same place and for the same reason as
 * _drawApexOverlay — screen space, camera already unwound, globalAlpha pinned:
 *
 *   if (this.unmaking) {
 *     const prev = ctx.globalAlpha; ctx.globalAlpha = 1;
 *     this.unmaking.drawScreen(ctx, this.viewW, this.viewH);
 *     ctx.globalAlpha = prev;
 *   }
 *
 * KEYS. `key` identifies a sprite to the caches and must be stable for a given
 * rendered image and different for different ones. The hero's is facing, walk
 * frame and pose; if the player can re-equip mid-sequence, put the look's
 * cache key in it too. A wrong key shows the wrong plate; it cannot crash.
 *
 * REDUCED MOTION is a construction-time flag. If the host's media query can
 * flip mid-sequence, rebuild the effect and `seek()` to the old `t`.
 *
 * THINGS THIS MODULE WILL NOT DO, on purpose: letterbox, dim the HUD, pause the
 * world, consume a key, show text, or draw over the player. If the sequence
 * needs words, they belong to gauntlet/antagonist.py and to whatever chrome
 * already renders his lines — he says one exact thing and is gone, and this
 * file is only the weather he says it in.
 */
