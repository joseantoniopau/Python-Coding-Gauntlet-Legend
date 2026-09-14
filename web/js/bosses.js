/* Boss art: sixteen authored creatures, generated at runtime.
 *
 * Nothing here is traced, sampled or derived from any existing game, film or
 * franchise. "Lich, dragon, knight" are archetypes as old as the woodcut; these
 * are drawn fresh as pixel grids and rasterised at load, the same way sprites.js
 * and tiles.js do everything else. There are no image assets and there must not
 * be any.
 *
 * Why this module exists at all: sprites.bossSprite draws a 48x48 mirrored half
 * and gets its animation from one generic deformation. That is fine for a trash
 * mob promoted to a miniboss. It is not fine for the thing the player has spent
 * twenty minutes earning, which is on screen for six phases and is the only
 * moment the game has that the player will describe to someone else afterwards.
 * So the bosses move out of the mob pipeline and get their own:
 *
 *   64x64, or 96x64 for the winged and serpentine ones, DRAWN AT 2 with its
 *     feet under the floor — 128 logical rows against the hero's 96, reaching
 *     from well down the sky through the ground line. A boss the same height as
 *     the thing fighting it is a mob with more health. (This comment said 1.75
 *     and "112 against 72" for a whole migration after the raster moved to
 *     256x224 and BOSS_STAGE_SCALE became 2. Both numbers were the old stage's.
 *     A comment that disagrees with the constant three lines of code away is
 *     worse than no comment: it is a measurement nobody took again.)
 *   AND ONE 96x128, DRAWN AT 1 — the final boss rung of docs/08 §B, and the
 *     Interviewer is the only thing in the game that gets it. Twelve thousand
 *     authored cells against a 64-box boss's four, at one logical pixel each,
 *     so the last creature the player meets is the only one drawn at the
 *     stage's own grain. Standing on the ground line it spans rows 47..174 —
 *     the whole 128, none of it under the floor, which is eighteen more rows of
 *     visible creature than any boss that sinks. See THE FINAL RUNG below.
 *   Five frames — idle, the exhale, a wind-up, the attack, and a hurt pose —
 *     and six BEATS inside the idle loop, which each moving part reads at its
 *     own rate. Uniform motion is the tell of cheap animation, and the fix is
 *     not more frames, it is parts that disagree about where they are.
 *   Six PHASES, and they are the fight's own. gauntlet/bestiary.py advances a
 *     boss phase when a graded submission empties that phase's health pool and
 *     hands over `art_phase`; the armour opens along authored fault lines, the
 *     contour is bitten away, the plate is holed, a limb goes, a core lights
 *     inside and throws its light back onto the creature's own bone and
 *     chrome, and the last form grows.
 *   Separate animated parts: a jaw, a wing, a tail, an orbiting skull, a chain.
 *   A contre-jour rim in the boss's own colour, because the stage is near-black
 *     and a near-black creature on it is a hole, not a silhouette.
 *   An ENTRANCE: six beats, up through the floor, rim first in three staggered
 *     bands, crown last, and then 420ms of nothing before it says anything.
 *
 * And, added since: the other half of the brief, which is that a boss has to be
 * epic in TWO places and be the same animal in both.
 *
 *   A MAP FORM. 48x48 (72x48 wide) against a 24x24 mob and a 16x24 hero on a
 *     16-pixel tile grid — twice the height and four times the painted mass of
 *     anything else out there, with a border a ring and a half thick instead of
 *     a ring. It is not the battle sprite made small. It is DERIVED from the
 *     battle sprite by a reduction that keeps the features, drops the detail
 *     authored for 112 pixels, re-outlines heavily and then re-lights on the
 *     new silhouette. Because it is derived, the two forms cannot drift; and
 *     because "cannot drift" is a claim about pixels, it is measured rather
 *     than asserted. See THE MAP FORM below, and the numbers in
 *     scripts/verify/bossforms.mjs.
 *   AN ELEMENT. gauntlet/elements.py already says what every region is, and
 *     world.py already says which region every boss stands in, so every one of
 *     these creatures has had an element all along and the art did not know.
 *     Now the contre-jour rim, the rune glow and the ember ramp rotate to it.
 *     It costs nothing: a remap of light already on the sprite cannot raise a
 *     colour count, and the harness checks that it does not.
 *   SIX STAGES, EVERY ONE OF WHICH MOVES THE SILHOUETTE. It cracks, it is
 *     chipped off at the edge, the fault lines go through, it LOSES A LIMB —
 *     the dragon a wing, the colossus its maul, the Interpreter its hat; the
 *     hydra, whose opening line is about growing heads, grows one — the core
 *     opens, and the last form puts spines out of its own outline. A phase you
 *     can only see by reading the health bar is a number, and the silhouette
 *     is the only part of a sprite that survives a screen shake, a map scale
 *     and a player who is looking at their own code instead. Measured per
 *     stage AND per stage-to-stage step in scripts/verify/bossforms.mjs, which
 *     fails the roster if any turn moves none.
 *
 * Fifteen colours, and this file now holds to it. The whole bestiary is inside
 * the budget — worst case fifteen exactly — which it was not before: the way
 * a boss carrying steel AND bone AND gold AND a tabard fits is that the dark
 * end of every hard material is ONE tone, the void and the outline are ONE
 * tone, and a chrome specular and a chain highlight are the same pixel. That
 * is rule 1 of docs/08-art-direction.md doing the job it is there to do.
 *
 * It reuses the sprites.js engine rather than reimplementing it. That matters:
 * ramp() is what makes generated art read as 16-bit instead of plastic, and a
 * second copy of it would drift.
 *
 * Determinism: every sprite is keyed on (archetype, colour, frame, phase, beat)
 * and cached. Wear, pitting, the fault lines, the chips and the spines all come
 * from rng(hash(key)), so the Hash Titan has the same scars in every session
 * forever and is bitten in the same places every time it is brought to the same
 * stage. Nothing allocates inside a render loop: one STAGE of a fight is 15
 * canvases, warmBoss() builds one in one call — fx.js calls it on the phase
 * turn, before the flash — and the drawn frames after that cost zero
 * allocations.
 */

/* Single line on purpose: the project's parse check strips /^import.*$/ per
 * line, and a wrapped import statement leaves its own tail behind. */
import { ramp, mix, shade, rng, hash, drawGrid, applyRim, rimLowLeft, normalise, shiftRows, bobGrid, sinkRows, squashRows, widenRows, drawGroundShadow } from './sprites.js';
import { bossLook, dressGrid, elementPalette, wantsRim, ingestHunters, ELEMENT_IDS } from './bossart.js';

export const BOSS_ART_VERSION = 6;   // 6: foreign-element previews share a bounded material palette

/* One box height for every boss, so the battle layer never has to special-case
 * a vertical offset. Width is the only thing that varies: the winged and the
 * serpentine ones need the extra 32 columns or their wings get amputated. */
export const BOSS_H = 64;
export const BOSS_W = 64;
export const BOSS_WIDE_W = 96;

/* The final rung of docs/08 §B — 12x16 tiles, FFVI's own big-summon box — and
 * exactly one creature is authored at it. It is not a bigger box for its own
 * sake: at BOSS_STAGE_SCALE the 64-box rigs already reach §B's tallest 128
 * logical rows, so the only thing left to buy is GRAIN. A 96x128 rig drawn at
 * blit 1 puts one authored cell on one stage pixel, where every other figure in
 * the game spends four (hero, mob) or two (boss). The Interviewer is the only
 * thing the player ever sees at the stage's own resolution.
 *
 * Checked against the frame before a pixel of it was drawn: 128 rows standing
 * on ground 175 with no sink spans 47..174, inside the 24..199 safe area with
 * 23 rows in hand, and 96 columns centred on enemyX 184 runs 136..232, 23
 * columns short of the right edge and 40 clear of the hero's 32..95. It is the
 * one boss that needs no bias at all. */
export const FINAL_BOSS_W = 96;
export const FINAL_BOSS_H = 128;

/* The marker box. Three quarters of the battle box, so a boss is 48 tall
 * against a 24-tall mob and a 24-tall hero on a 16-pixel tile grid: twice the
 * height of anything else that walks around out there, which is the point.
 * See THE MAP FORM, further down, for how it is derived and why it is derived
 * rather than drawn. */
export const BOSS_MAP_H = 48;
export const BOSS_MAP_W = 48;
export const BOSS_MAP_WIDE_W = 72;
/* And the tall rung's marker, at the same three quarters: 72x96, which is four
 * and a half tiles by six on a 16-pixel map against a 24-tall mob. The thing at
 * the end of the game is twice the marker of every other boss out there, which
 * is the overworld saying what the fight is going to say. */
export const BOSS_MAP_FINAL_W = 72;
export const BOSS_MAP_FINAL_H = 96;
/* What the marker box costs against the battle box, used for the sink and the
 * shadow so a boss meets the ground the same way in both places. */
export const BOSS_MAP_RATIO = BOSS_MAP_H / BOSS_H;

/* Three boxes now, so the size stops being an inline ternary repeated in six
 * places. `tall` wins over `wide`: the 96x128 rig is both wider than 64 and
 * taller than 64 and there is no combination of the two flags that means
 * anything else. Every caller that used to write `art.wide ? WIDE : W` reads
 * these instead, which is what makes adding a fourth rung one edit. */
function boxOf(art) {
  if (art && art.tall) return { w: FINAL_BOSS_W, h: FINAL_BOSS_H };
  return { w: art && art.wide ? BOSS_WIDE_W : BOSS_W, h: BOSS_H };
}
function mapBoxOf(art) {
  if (art && art.tall) return { w: BOSS_MAP_FINAL_W, h: BOSS_MAP_FINAL_H };
  return { w: art && art.wide ? BOSS_MAP_WIDE_W : BOSS_MAP_W, h: BOSS_MAP_H };
}
/* What the marker box costs against the battle box FOR THIS CREATURE. The
 * exported constant above is the 64-rung's answer and stays what it was; a
 * 96x128 rig reducing to 72x96 has the same 0.75, but computing it rather than
 * assuming it is what stops the next rung from sinking into the floor. */
function mapRatioOf(art) { return mapBoxOf(art).h / boxOf(art).h; }

/* ---------------- glyph table ----------------
 * Every grid in this file draws from exactly this set. Anything else is a typo,
 * and drawGrid silently skips unknown glyphs, so the harness checks for them.
 *
 *   .    transparent
 *   o    hard outline, near-black bruised toward the body hue
 *   O    lit outline, upper left            (written by applyRim)
 *   Q    contre-jour rim in the boss colour (written by rimPass ->
 *        sprites.rimLowLeft, one low-left source, inside the outline)
 *   B    undecided body mass                (resolved by applyRim)
 *   H L  lit tones, d D shadow tones        (resolved by applyRim, or authored)
 *   a A  accent base / accent light
 *   k    void black: eye sockets, a visor slit, an open maw
 *   e    eye socket rim   w eye white   W hot white
 *   g G n   steel: base / spec / shadow
 *   b C c   bone: base / lit / shadow
 *   t T s   cloth: base / lit / shadow
 *   r R f   ember: mid / hot / deep
 *   u U     rune glow in the boss colour / its white-hot core
 *   x X     blood crimson / its highlight
 *   z Z     gold / its highlight
 *   j J     bark and timber, dark / lit
 *   i       cold cyan: frost, a lens, a judging eye
 *   m M     iron chain, dark / spec
 *   l       leather strap
 */
export const BOSS_GLYPHS = 'oOQBHLdDaAkewWgGnbCctTsrRfuUxXzZjJimMl';

/* The palette is a superset of sprites.enemyPalette's, so a grid can move
 * between the two files without being recoloured. Materials that are not the
 * creature — steel, bone, gold — hold their own hue and do NOT take the boss
 * colour, otherwise every boss becomes a monochrome study and the accent stops
 * meaning anything. Only o/O/Q/u and the body ramp carry identity.
 *
 * `phase` is the third dimension, and it is where a fight stops looking like
 * one drawing with a health bar beside it. See BOSS_PHASE for what the three
 * states mean; here is what they do to the light:
 *
 *   whole    as authored. Cold metal, cold bone.
 *   cracked  the body ramp is scorched — shadows deepen and rotate toward the
 *            void, the rim cools, the tabard goes black with dried blood.
 *   core     something inside is burning and lighting the outside. The body
 *            ramp takes the accent, the contre-jour rim goes hot, and — the
 *            part that matters for the bible — bone and chrome pick that light
 *            up in their speculars while keeping their own hue. Chrome lit by
 *            a furnace is still chrome; chrome tinted the colour of a furnace
 *            is plastic.
 */
/* ---------------- the element ----------------
 * gauntlet/elements.py gives every biome an affinity and gauntlet/world.py puts
 * every boss in a region, so each of these creatures HAS an element whether the
 * art admits it or not. Until now it did not: the Twin Pointer Behemoth guards
 * a COLD mountain pass in hot orange, which quietly tells the player that the
 * game's own type chart is decoration.
 *
 * The fix is deliberately NOT a new material. A material costs a palette slot,
 * and four of these creatures already paint exactly fifteen colours, so the
 * element is carried by ROTATING light that is already on the sprite: the
 * contre-jour rim, the lit outline, the rune glow and the three ember steps.
 * Nothing is added, which means nothing can go over budget — a remap cannot
 * raise a colour count, only collapse one — and the thing a player actually
 * reads from across a ridge, which is what colour the light coming off the
 * creature is, finally agrees with the ground it is standing on.
 *
 * NEUTRAL is not an element — elements.py is explicit about that — and so it
 * is not in this table. A canopy boss is lit exactly as authored, which is the
 * correct answer rather than a missing one.
 *
 * web/js/bossart.js, written alongside this, offers elementPalette() over the
 * same contract — reassigns existing slots, never adds a key. It is a richer
 * answer than this one (it carries materials, not just light) and this is
 * deliberately the shape that can be swapped for it: one function, palette in,
 * same palette out. Wiring it is an integration pass, not this one, because
 * that file is another pass's and is still moving.
 */
const ELEMENT_LIGHT = Object.freeze({
  FIRE:      { rim: '#ff9d4a', glow: '#ffd08a', ember: ['#ff7a24', '#ffd473'], mix: 0.52 },
  COLD:      { rim: '#8fd8ff', glow: '#d8f4ff', ember: ['#5aa8e8', '#cfeeff'], mix: 0.60 },
  LIGHTNING: { rim: '#bcd8ff', glow: '#ffffff', ember: ['#7fb8ff', '#eaf4ff'], mix: 0.56 },
  POISON:    { rim: '#a8dc48', glow: '#e0f89a', ember: ['#8cc22e', '#dcf27a'], mix: 0.58 },
  BRUTE:     { rim: '#e0b070', glow: '#f6dcae', ember: ['#c8873a', '#f0c98a'], mix: 0.32 },
  VOID:      { rim: '#a878e8', glow: '#e2ccff', ember: ['#8a4fd0', '#d8b8ff'], mix: 0.64 },
});

/* Rotate the light, leave the materials alone. `f` — the ember's deep step —
 * is folded onto the body's own deepest shadow rather than given an elemental
 * tone of its own, for the same reason the file already folds steel's shadow
 * onto bone's: in a near-black ambient the bottom of every ramp converges, and
 * paying a slot to disagree about it is what puts a sprite over budget. */
/* One frozen stand-in per element, so the palette overlay can be handed a
 * `look` without bossPalette having to resolve a real one — it is given a
 * colour and an element id and nothing else, and bossart.elementPalette only
 * ever reads `.element` off what it is passed. Frozen and built once: this sits
 * behind a cached sprite build, but a palette that allocates per call is a
 * palette that will eventually be called per frame by somebody. */
const ELEMENT_STUB = Object.freeze(Object.fromEntries(
  ELEMENT_IDS.map(id => [id, Object.freeze({ id: `element:${id}`, element: id, motifs: [] })])));

function elementLight(pal, element, lit) {
  const e = ELEMENT_LIGHT[element];
  if (!e) return pal;
  const t = lit ? Math.min(0.9, e.mix + 0.2) : e.mix;
  /* The rim and the rune glow are LIGHT and take the element almost whole; the
   * lit outline is the creature's own edge catching that light and keeps most
   * of its own hue. Halving the difference instead — a fifty-fifty mix of a
   * red body light and a cold source — lands on grey every time, and a grey
   * contre-jour on a near-black stage is the hole this pass exists to avoid.
   * Which colour the light coming off a creature is IS the thematic claim, so
   * it is allowed to win. The body underneath is still entirely its own. */
  pal.Q = mix(pal.Q, e.rim, Math.min(0.86, t + 0.25));
  pal.O = mix(pal.O, e.rim, t * 0.55);
  pal.u = mix(pal.u, e.glow, Math.min(0.9, t + 0.2));
  pal.i = mix(pal.i, e.glow, t * 0.5);
  pal.r = e.ember[0];
  pal.R = e.ember[1];
  pal.f = pal.D;
  return pal;
}

export function bossPalette(base, accentHex, phase = 0, element = null) {
  const ph = phase | 0;
  const cracked = ph === 1, lit = ph >= 2;
  const src = base || '#8a8f9c';
  const acc = accentHex || ramp(src).light2;
  const r = ramp(lit ? mix(src, acc, 0.22) : src);
  const a = ramp(acc);
  const heat = a.light2;
  const steel = ramp('#8d94a6');
  const bone = ramp('#d6d0bb');
  const cloth = ramp(mix(src, '#171320', cracked ? 0.66 : 0.58));
  const gold = ramp('#d9a63c');
  const blood = ramp('#8e1d28');
  const wood = ramp('#6a4d33');
  /* One knob, used everywhere a material should show that it is standing in
   * the core's light rather than being made of it. */
  const seen = (hex, t) => (lit ? mix(hex, heat, t) : cracked ? mix(hex, '#0c0a14', t * 0.9) : hex);
  /* The shared dark. Every hard material's deepest step collapses onto ONE
   * tone: steel's shadow, bone's shadow and an eye socket's rim are the same
   * pixel value. This is not a shortcut — it is rule 1 of the art direction
   * (docs/08), and it is what keeps a boss carrying steel AND bone AND gold
   * AND a tabard inside the fifteen-colour budget. Collapsing the dark ends is
   * also simply true: in a near-black ambient every material converges. */
  const deep = seen(mix(steel.shadow2, bone.shadow1, 0.5), 0.08);
  const spec = seen(steel.light2, 0.3);
  const pal = {
    o: mix(r.outline, '#08070d', cracked ? 0.74 : 0.62),
    O: lit ? mix(r.rim, heat, 0.45) : r.rim,
    Q: lit ? mix(r.light1, heat, 0.55) : mix(r.light1, src, cracked ? 0.48 : 0.3),
    D: cracked ? mix(r.shadow2, '#07060c', 0.35) : r.shadow2,
    d: cracked ? mix(r.shadow1, '#0b0912', 0.28) : r.shadow1,
    B: r.base, L: r.light1, H: lit ? mix(r.light2, heat, 0.3) : r.light2,
    a: a.base, A: a.light2,
    // The void and the outline are one colour. Every sprite here pays for its
    // outline already; an eye socket, a visor slit, an open maw and a fresh
    // fissure are all the same absence of light, and charging a separate
    // palette slot for each of them is what puts a boss over budget.
    k: mix(r.outline, '#08070d', cracked ? 0.74 : 0.62),
    // e/c/n are one tone; w is bone-white; M is the steel specular. Six glyphs,
    // three colours, and no sprite pays for a distinction it never shows.
    e: deep, n: deep, c: deep,
    w: seen(bone.light2, 0.3), W: '#ffffff',
    g: seen(steel.base, 0.14), G: spec, M: spec,
    b: seen(bone.base, 0.14), C: seen(bone.light2, 0.3),
    t: cloth.base, T: cloth.light1, s: cracked ? mix(r.shadow2, '#07060c', 0.35) : r.shadow2,
    r: '#ff7a24', R: '#ffd473',
    u: lit ? mix(heat, '#ffffff', 0.42) : mix(r.light2, '#ffffff', cracked ? 0.2 : 0.34),
    U: '#ffffff',
    x: cracked ? mix(blood.base, '#140610', 0.3) : blood.base, X: blood.light2,
    f: cracked ? mix(blood.base, '#140610', 0.3) : blood.base,   // ember's deep step is the blood tone
    z: seen(gold.base, 0.18), Z: seen(gold.light2, 0.34),
    j: wood.shadow1, J: wood.light1,
    i: lit ? mix('#7fe6ff', heat, 0.35) : '#7fe6ff',
    m: mix(r.outline, '#08070d', cracked ? 0.74 : 0.62),          // chain shadow is the outline
    l: wood.shadow1,
  };
  /* Two passes, in this order, and the order is the point.
   *
   * elementLight() above rotates the light that is already on the sprite — the
   * cheap, safe half, and the half that keeps a creature reading as LIT.
   * bossart.elementPalette() then overlays what the element is MADE of, and it
   * is allowed to win, because it carries two opinions this file never had:
   *
   *   BRUTE does not glow. Its contre-jour collapses onto the outline, because
   *     rock does not emit. ELEMENT_LIGHT gave it a warm tan rim, which is a
   *     lamp with a rock painted on it.
   *   VOID refuses the rim outright. docs/09 §8 makes one hot low-left rim the
   *     law of this cast, and void is the one thing in the game whose whole
   *     idea is being the exception to it. ELEMENT_LIGHT gave void a purple
   *     rim — a perfectly obedient member of a cast it is supposed to break.
   *
   * It also collapses r/f/R/u/i onto three steps of one shared mark ramp, so
   * the theme pass shares those material tones. Foreign-element geometry can
   * still introduce a previously unused mark glyph, so boundedBossPalette()
   * enforces the final rendered budget after geometry is assembled. */
  return elementPalette(elementLight(pal, element, lit),
    ELEMENT_STUB[element] || ELEMENT_STUB.NEUTRAL, ph);
}

/* Element geometry can introduce a mark on a body that never used that glyph.
 * In previews this used to add up to three colours to the Interviewer. Resolve
 * the palette against the finished grid, keeping the outline, element marks
 * and rim. Only over-budget palettes share their nearest existing material
 * tones; ordinary sprites retain every colour. No new hue, geometry or canvas
 * is created, and this runs only on a sprite-cache miss. */
function boundedBossPalette(grid, palette) {
  const used = new Set([...grid.join('')].map(ch => palette[ch]).filter(Boolean));
  if (used.size <= 15) return palette;
  const out = { ...palette };
  const protectedColours = new Set([...'okmQrRfuiUWw']
    .map(ch => palette[ch]).filter(Boolean));
  const rgb = c => { const n = parseInt(c.slice(1), 16); return [n >> 16, n >> 8 & 255, n & 255]; };
  while (used.size > 15) {
    const colours = [...used].sort();
    let pair = null, nearest = Infinity;
    for (const from of colours) {
      if (protectedColours.has(from)) continue;
      const a = rgb(from);
      for (const to of colours) {
        if (from === to) continue;
        const b = rgb(to);
        const distance = 2 * (a[0] - b[0]) ** 2 + 4 * (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
        if (distance < nearest) { nearest = distance; pair = [from, to]; }
      }
    }
    // At most nine protected tones exist, so an over-budget palette always
    // has a material tone available to share with an existing neighbour.
    const [from, to] = pair;
    for (const glyph of Object.keys(out)) if (out[glyph] === from) out[glyph] = to;
    used.delete(from);
  }
  return out;
}

/* ---------------- grid surgery ----------------
 * sprites.js owns the shared operations. These four are specific to bosses:
 * bosses are assembled from a mirrored body plus independent parts, which mobs
 * never are.
 */
const T = '.';
const HALF = BOSS_W / 2;   // 32 authored columns become 64 drawn ones
const FINAL_HALF = FINAL_BOSS_W / 2;   // 48 authored columns become 96 drawn ones

function blank(w, h) {
  const row = T.repeat(w);
  return Array.from({ length: h }, () => row);
}

function fit(row, w) { return row.length >= w ? row.slice(0, w) : row + T.repeat(w - row.length); }

function rect(grid, w) {
  const width = w || Math.max(...grid.map(r => r.length));
  return grid.map(r => fit(r, width));
}

/* Half-grids are RIGHT-ALIGNED: the last character of a row is the centre seam,
 * and a short row is padded with transparent at the OUTER edge. That one choice
 * is what makes 700 rows of hand-authored art survivable — a row's length is
 * simply that row's half-width, a miscount costs one pixel at the silhouette's
 * edge instead of tearing a hole down the creature's spine, and no leading dots
 * ever have to be typed or counted. */
function padHalf(row, w) {
  return row.length >= w ? row.slice(row.length - w) : T.repeat(w - row.length) + row;
}

function halfRect(grid, w) { return grid.map(r => padHalf(r, w || HALF)); }

/* Left half plus its reflection. Every bilaterally symmetric boss is authored
 * once; the frame deformation is applied to the mirrored result, never before,
 * or a lean to the left comes back as a symmetric bulge outward. */
function mirror(half, hw) {
  const w = hw || HALF;
  return half.map(row => {
    const s = padHalf(row, w);
    return s + [...s].reverse().join('');
  });
}

function flipX(grid) { return grid.map(r => [...r].reverse().join('')); }

/* Draw src into dst at (ox, oy). `under` writes only into transparent cells,
 * which is how a wing sits behind a body without being hand-clipped. */
function stamp(dst, src, ox, oy, under) {
  for (let y = 0; y < src.length; y++) {
    const ty = y + (oy | 0);
    if (ty < 0 || ty >= dst.length) continue;
    const row = src[y];
    const cells = dst[ty].split('');
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      if (ch === T || ch === ' ') continue;
      const tx = x + (ox | 0);
      if (tx < 0 || tx >= cells.length) continue;
      if (under && cells[tx] !== T) continue;
      cells[tx] = ch;
    }
    dst[ty] = cells.join('');
  }
  return dst;
}

function at(grid, y, x) {
  const row = grid[y];
  return row === undefined ? undefined : row[x];
}
const isEmpty = ch => ch === undefined || ch === T || ch === ' ';

/* applyRim lights the upper-left outline. This lights the opposite edge in the
 * boss's own colour. Contre-jour is the cheapest separation there is, and on a
 * stage this dark it is the difference between a silhouette and a hole. */
/* The contre-jour rim.
 *
 * This used to be a local pass that turned an outline pixel into 'Q' wherever
 * the cell BELOW or to the RIGHT of it was empty. Two things were wrong with
 * that, and both of them are visible rather than theoretical:
 *
 *   IT ATE THE OUTLINE. applyRim() already promotes an outline pixel to the lit
 *     'O' wherever the cell above or to the LEFT is empty. Between the two,
 *     every pixel on the silhouette boundary has an empty neighbour on some
 *     side, so every one of them was rewritten and NOT ONE black pixel survived
 *     anywhere on the perimeter. Measured on the Hash Titan's marker: 166 of
 *     166 boundary pixels lit, zero outline. docs/09 §8 opens with "heavy black
 *     outline", an ordinary monster out of sprites.js keeps its black boundary
 *     for exactly that reason, and the bosses were the one cast in the game
 *     that had quietly stopped having one. At map scale, over grass and water,
 *     the outline is the entire read.
 *
 *   IT WAS TWO LIGHTS. Lower-right from here, upper-left from applyRim: a
 *     creature lit from both, which is the specific thing "ONE hot rim light
 *     from a low source" forbids, and which is most of why a boss standing next
 *     to a mob looked like it had been drawn for a different game.
 *
 * sprites.rimLowLeft() is the rig the hero, the mobs and bossart.js all already
 * light with: one source, low and to the left, painted INSIDE the body — it
 * skips edge glyphs entirely, so the black outline survives it. Using it here
 * is not a new idea, it is this file finally using the shared one. The protect
 * set is bossart.js's, plus this file's own material glyphs, so the rim does
 * not paint over an eye, an ember, gold, bone or chrome on its way past. */
const RIM_PROTECT = 'rRuUiWwkaAbCcezZgGMnxXjJmltTsf';

function rimPass(grid) {
  return rimLowLeft(grid, 'Q', RIM_PROTECT);
}

/* Wear is grouped into short chips instead of independently scattered pixels.
 * It is applied to the unposed body, so marks move with the creature and do not
 * crawl across it between idle and attack. Keying on its palette/frame made a
 * boss acquire different scars every time it moved or changed element. */
function patina(grid, seed, amount, glyph) {
  return grid.map((row, y) => {
    const cells = row.split('');
    for (let x = 0; x < cells.length; x++) {
      if (cells[x] !== 'B' || row[x - 1] !== 'B' || row[x + 1] !== 'B') continue;
      const tileX = Math.floor(x / 5), tileY = Math.floor(y / 4);
      const n = hash(`${seed}:${tileX}:${tileY}`) >>> 0;
      if ((n % 1000) / 1000 >= amount) continue;
      if (y % 4 === (n >>> 12) % 3 && x % 5 >= 1 && x % 5 <= 2) cells[x] = glyph;
    }
    return cells.join('');
  });
}

/* Connected material planes for the whole cast. Authored glyph families stay
 * separate: armour uses a narrow specular and a dark return, bone a rounded
 * cheek, cloth long folds, organic bodies a broad shoulder and belly shadow.
 * The pass uses only tones already present in the lit assembly. No added
 * palette entries, silhouette cells, eyes or damage marks. */
const BOSS_SURFACE = {
  lich: 'cloth', dragon: 'scale', knight: 'plate', titan: 'plate',
  colossus: 'plate', hydra: 'scale', wraith: 'cloth', behemoth: 'fur',
  golem: 'stone', ent: 'bark', necromancer: 'cloth', automaton: 'plate',
  demon: 'muscle', wyrm: 'scale', interpreter: 'scale', interviewer: 'plate',
};
function materialPlanes(grid, key) {
  const paid = new Set(grid.join(''));
  const ramps = { B: ['D','d','B','L','H'], g: ['n','n','g','G','G'],
    b: ['c','c','b','C','C'], t: ['s','s','t','T','T'], j: ['j','j','j','J','J'] };
  const families = { B: 'BLHdD', g: 'gGn', b: 'bCc', t: 'tTs', j: 'jJ' };
  const surface = BOSS_SURFACE[key] || 'muscle';
  return grid.map((row, y) => [...row].map((ch, x) => {
    const tones = ramps[ch]; if (!tones) return ch;
    const same = c => c && families[ch].includes(c);
    let l = x, r = x, top = y, bottom = y;
    while (l > 0 && same(row[l - 1])) l--;
    while (r + 1 < row.length && same(row[r + 1])) r++;
    while (top > 0 && same(grid[top - 1][x])) top--;
    while (bottom + 1 < grid.length && same(grid[bottom + 1][x])) bottom++;
    const width = r - l + 1, height = bottom - top + 1;
    if (width < 5 || height < 3) return ch;
    const u = (x - l) / width, v = (y - top) / height;
    let step = u < .3 && v < .63 ? 3 : u > .74 || v > .85 ? 1 : 2;
    if (u > .86 && v > .65) step = 0;
    if (ch === 'g' || ch === 'B' && (surface === 'plate' || surface === 'stone')) {
      step = u < .14 || v < .14 ? 3 : u > .72 || v > .82 ? 1 : 2;
    } else if (ch === 't') {
      const fold = Math.floor((x - l) * 6 / width);
      step = fold === 1 || fold === 4 ? 3 : fold === 2 || fold === 5 ? 1 : 2;
    } else if (ch === 'j' || ch === 'B' && surface === 'bark') {
      step = (x + Math.floor(y / 7)) % 8 < 2 ? 1 : u < .42 ? 3 : 2;
    } else if (ch === 'B' && surface === 'scale' && width > 10 && y % 5 === 2 && (x + (y >> 2) * 2) % 7 < 3) step = 1;
    else if (ch === 'B' && surface === 'fur' && v > .55 && y % 4 === 0 && (x + y) % 7 < 2) step = 1;
    const tone = tones[step];
    return paid.has(tone) ? tone : ch;
  }).join(''));
}

/* ---------------- damage as art ----------------
 * The phase system, at the grid level. The requirement is that a phase change
 * be legible with the health bar covered up: not a tint, but a different
 * object. Three passes do it, and they run in this order because each one
 * reads what the last one wrote.
 */

/* Every glyph that counts as the creature's own mass. Cracks run through these
 * and stop at bone-white teeth, at a lit core, and at the outline — a fissure
 * that crosses an eye socket reads as a drawing mistake, not as damage. */
const MASS = 'BLHdDgGnbCcaAxXzZjJ';   // cloth is not in it: robes tear, they do not crack
const isMass = ch => MASS.indexOf(ch) >= 0;

/* One fissure, walked downward from an anchor with a deterministic wobble.
 * The crack itself is void; the pixel on its lit side takes the glow glyph, so
 * at phase 2 the fissure is a seam of light rather than a black scratch. */
function fissure(cells, ox, oy, len, rand, glow, wide) {
  let x = ox;
  for (let i = 0; i < len; i++) {
    const y = oy + i;
    const row = cells[y];
    if (!row) break;
    if (i > 0) x += rand() < 0.36 ? (rand() < 0.5 ? -1 : 1) : 0;
    if (x < 1 || x >= row.length - 1) break;
    if (!isMass(row[x])) { if (row[x] === T || row[x] === 'o' || row[x] === 'O' || row[x] === 'Q') break; continue; }
    if (isMass(row[x - 1])) row[x - 1] = glow;
    row[x] = 'k';
    if (wide && i % 2 === 0 && isMass(row[x + 1])) row[x + 1] = 'k';
  }
}

/* Cracked armour. `faults` are authored anchors in assembled-grid coordinates:
 * the two or three places on THIS creature where a blow would actually open it
 * — a shoulder seam, a sternum, the join above a haunch. Scattering them by
 * rng instead would put a fissure through a horn. */
function fracture(grid, seed, phase, faults) {
  if (!phase || !faults || !faults.length) return grid;
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  const rand = rng(hash(`${seed}|fault`) || 7);
  const wide = phase >= BOSS_PHASE.BREACHED;
  const glow = phase >= BOSS_PHASE.LIT ? 'U' : 'u';
  for (let i = 0; i < faults.length; i++) {
    const f = faults[i];
    /* Two pixels longer per stage. A fissure that stops growing after stage 1
     * is the reason the interior stopped saying anything: the six stages have
     * to keep spending, and this is the cheapest place to spend. */
    const len = (f[2] || 10) + phase * 2;
    fissure(cells, f[0] | 0, f[1] | 0, len, rand, glow, wide);
    if (wide) fissure(cells, (f[0] | 0) + 2, (f[1] | 0) + 3, Math.round(len * 0.6), rand, glow, false);
  }
  /* Spall: chips knocked off the plate around each fault. Cheap, and it is
   * what stops the cracks reading as drawn-on lines. */
  for (const f of faults) {
    for (let n = 0; n < 3 + phase * 2; n++) {
      const y = (f[1] | 0) + Math.floor(rand() * 12);
      const x = (f[0] | 0) - 3 + Math.floor(rand() * 7);
      const row = cells[y];
      if (!row || x < 1 || x >= row.length - 1) continue;
      if (isMass(row[x])) row[x] = rand() < 0.3 ? 'D' : 'k';
    }
  }
  return cells.map(r => r.join(''));
}

/* BREACHED does not crack the plate, it goes THROUGH it. At the midpoint of
 * each authored fault the mass is burned away to transparent and the rim of
 * the opening is left white-hot, so the stage is visible through the creature.
 *
 * The reason this exists rather than a third round of fissures: a fissure is
 * interior detail, and interior detail is invisible at map scale, invisible
 * under a screen shake, and invisible to anyone not staring at the sprite.
 * A hole changes the SILHOUETTE, and the silhouette is the only part of a
 * sprite that survives every one of those. Measured, not assumed — see
 * scripts/verify/bossforms.mjs, which counts the silhouette cells each phase
 * moves and fails the roster if any of them moves none.
 *
 * Ragged by rng(hash(seed)), so a given creature is holed in exactly the same
 * places in every session, and the same places every time it is brought back
 * to that stage inside one fight. */
function breach(grid, phase, faults, seed) {
  if (phase < BOSS_PHASE.BREACHED || !faults || !faults.length) return grid;
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  const rand = rng(hash(`${seed}|breach`) || 11);
  /* One more fault opens per stage, and the openings widen once the core is
   * lit. Holding it at two would have made stages 3, 4 and 5 identical here,
   * and this pass is the one that moves the most silhouette. */
  const opened = Math.max(1, Math.min(faults.length,
    phase - BOSS_PHASE.BREACHED + 1));
  const bigger = phase >= BOSS_PHASE.LIT ? 1 : 0;
  for (let i = 0; i < opened; i++) {
    const f = faults[i];
    const cx = (f[0] | 0) + 1;
    const cy = (f[1] | 0) + Math.round((f[2] || 10) * 0.55);
    const rh = 3 + bigger, rw = 4 + bigger;
    for (let dy = -rh; dy <= rh; dy++) {
      const row = cells[cy + dy];
      if (!row) continue;
      const span = Math.max(1, Math.round(rw * Math.sqrt(Math.max(0, 1 - (dy * dy) / (rh * rh + 0.5)))
        - (rand() < 0.4 ? 1 : 0)));
      for (let dx = -span; dx <= span; dx++) {
        const x = cx + dx;
        if (x < 1 || x >= row.length - 1) continue;
        if (isMass(row[x]) || row[x] === 'k' || row[x] === 'u' || row[x] === 'U') row[x] = T;
      }
    }
    /* The edge of the opening is where the inside is showing, so it is the
     * hottest thing on the creature. One ring, nothing more: two rings and the
     * hole stops reading as a hole and starts reading as a lamp. */
    for (let dy = -rh - 1; dy <= rh + 1; dy++) {
      const row = cells[cy + dy];
      if (!row) continue;
      for (let dx = -rw - 1; dx <= rw + 1; dx++) {
        const x = cx + dx;
        if (x < 1 || x >= row.length - 1 || !isMass(row[x])) continue;
        const near = (cells[cy + dy - 1] && cells[cy + dy - 1][x] === T)
          || (cells[cy + dy + 1] && cells[cy + dy + 1][x] === T)
          || row[x - 1] === T || row[x + 1] === T;
        if (near) row[x] = rand() < 0.55 ? 'U' : 'u';
      }
    }
  }
  return cells.map(r => r.join(''));
}


/* ---------------- the contour, taken away ----------------
 * The fix for the defect the measurement found: at the old look 1 three of the
 * fifteen archetypes moved ZERO silhouette cells, because look 1 was fissures
 * and a fissure is interior. `breach` solved this for look 2 by holing the
 * plate, and holing the plate is a big, structural, expensive-looking event
 * that should not be the FIRST thing that happens to a boss.
 *
 * So: the stage before the holes bites the EDGE. Pieces come off the contour
 * near the authored fault lines — which is where a blow would actually take
 * them off — and the outline moves without the creature having lost anything
 * it was carrying. Read from the map, from under a screen shake, and by a
 * player looking at their own code, it says the same thing the fissures say to
 * a player staring at the sprite: that is not the thing that walked in.
 *
 * It removes whatever is at the edge, outline included, because removing the
 * mass under an outline and leaving the outline is a drawing of a chip rather
 * than a chip. applyRim runs after every damage pass for exactly this reason
 * and re-lights whatever contour it is given.
 *
 * Deterministic on (seed, stage): the Hash Titan is bitten in the same places
 * in every session, and in the same places every time a fight is brought back
 * to that stage.
 */
function spall(grid, phase, faults, seed) {
  if (phase < BOSS_PHASE.CHIPPED || !faults || !faults.length) return grid;
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  const rand = rng(hash(`${seed}|spall|${phase}`) || 13);
  const mid = w / 2;
  /* Bites per fault, per stage. Five numbers rather than a formula because the
   * jump from 1 to 2 wants to be small — stage 2 is already opening holes —
   * and the jump into 5 wants to be the largest thing on the ladder. */
  const BITES = [0, 5, 7, 9, 11, 14];
  const bites = BITES[Math.min(phase, BITES.length - 1)];
  for (const f of faults) {
    const fx = f[0] | 0, fy = f[1] | 0, len = Math.max(4, (f[2] || 10));
    /* Which way is out. A fault on the left half opens to the left. */
    const dir = fx < mid ? -1 : 1;
    for (let n = 0; n < bites; n++) {
      const y = fy - 2 + Math.floor(rand() * (len + 4));
      const take = 2 + Math.floor(rand() * 3);
      /* TWO rows per bite, not one. A one-row notch is four or five pixels and
       * the silhouette measurement normalises to a 24x24 grid, where five
       * pixels spread over two cells flips neither of them: the pixel count
       * moves and the shape does not, which is exactly the failure mode this
       * pass exists to fix. A notch two rows deep clears the threshold. */
      for (let dy = 0; dy < 2; dy++) {
        const row = cells[y + dy];
        if (!row) continue;
        /* Walk in from the outside of this row until something is there, then
         * take a few of it. Walking in from the FRAME edge rather than from
         * the fault is what makes this a contour operation: whatever is
         * furthest out on this row is what comes off, whether that is plate, a
         * horn or the hem of a robe. */
        let x = dir < 0 ? 0 : row.length - 1;
        let guard = 0;
        while (guard++ < row.length && row[x] === T) x += dir < 0 ? 1 : -1;
        if (guard >= row.length) continue;
        for (let k = 0; k < take; k++) {
          const tx = x + (dir < 0 ? k : -k);
          if (tx < 0 || tx >= row.length) break;
          const ch = row[tx];
          /* An eye, a lit core and a white-hot rim are the creature's identity
           * at every size. Everything else on the edge is expendable. */
          if (ch === 'w' || ch === 'W' || ch === 'k' || ch === 'U') break;
          row[tx] = T;
        }
      }
    }
  }
  /* And a pass that does NOT read the faults, because three of the fifteen
   * archetypes carry their fault anchors deep in the interior — a robe seam, a
   * sternum — and a contour operation anchored on an interior point takes
   * almost nothing off the edge. These bites are spread down the whole body and
   * alternate sides, so every creature loses edge everywhere rather than only
   * where it happens to be authored to crack. */
  const [ftop, fbot] = filledBounds(cells.map(r => r.join('')));
  const span = Math.max(1, fbot - ftop);
  for (let n = 0; n < phase * 3; n++) {
    const y = ftop + Math.floor(rand() * span);
    const dir = (n % 2) ? 1 : -1;
    const take = 2 + Math.floor(rand() * 3);
    for (let dy = 0; dy < 2; dy++) {
      const row = cells[y + dy];
      if (!row) continue;
      let x = dir < 0 ? 0 : row.length - 1;
      let guard = 0;
      while (guard++ < row.length && row[x] === T) x += dir < 0 ? 1 : -1;
      if (guard >= row.length) continue;
      for (let k = 0; k < take; k++) {
        const tx = x + (dir < 0 ? k : -k);
        if (tx < 0 || tx >= row.length) break;
        const ch = row[tx];
        if (ch === 'w' || ch === 'W' || ch === 'k' || ch === 'U') break;
        row[tx] = T;
      }
    }
  }
  return cells.map(r => r.join(''));
}

/* ---------------- the contour, put out ----------------
 * The last stage is the only one that ADDS, and it has to, because five stages
 * of subtraction ends a fight with a boss that is visibly smaller than the one
 * that walked in — which is the opposite of the thing the phase ladder is
 * saying. The final form grows.
 *
 * Two growths, and both are derived from the silhouette rather than authored,
 * so every archetype gets one whether or not it has a `grow` part:
 *
 *   SPINES off the top contour, where there is headroom. The tip is the rune
 *     glow glyph rather than body mass, for two reasons: it is what a creature
 *     lit from the inside would look like putting something out, and 'u' is in
 *     MAP_FEATURE, so a one-cell spine survives the 0.72 reduction into the map
 *     form instead of being averaged away.
 *   SPURS off the widest rows of the upper body, for the creatures with their
 *     heads against the top of the box — a behemoth has no headroom and would
 *     otherwise be the one boss whose last phase adds nothing.
 *
 * Both write only into transparent cells, so nothing that was drawn is
 * overwritten, and both run before applyRim, so what they add is lit as part of
 * the creature rather than pasted onto it.
 */
function crown(grid, phase, seed) {
  if (phase < BOSS_PHASE.CROWNED) return grid;
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  const h = cells.length;
  const rand = rng(hash(`${seed}|crown`) || 17);
  const tops = new Array(w).fill(-1);
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) {
      if (cells[y][x] !== T) { tops[x] = y; break; }
    }
  }
  const filled = tops.map((y, x) => (y >= 0 ? x : -1)).filter(x => x >= 0);
  if (!filled.length) return grid;
  const x0 = filled[0], x1 = filled[filled.length - 1];
  /* The tip glyph, chosen from what this creature ALREADY renders. A spine
   * tipped with a glow the boss does not otherwise carry is one more rendered
   * colour, and four of these archetypes paint exactly fifteen — the budget —
   * so a hard-coded 'u' put the knight over it. Everything in this list is
   * already on the sprite by the time crown() runs. Writing bare 'B' instead
   * looked right and was not: applyRim resolves 'B' into FOUR tones of the
   * body ramp, and a knight that renders ten colours at stage 4 came out of
   * stage 5 at sixteen — one over the whole file's budget — for the sake of a
   * few spines. Two glyphs, both already paid for, cost nothing. */
  const has = (g) => cells.some(r => r.indexOf(g) >= 0);
  const tip = ['U', 'u', 'W', 'H'].find(has) || 'L';
  const stem = ['L', 'H', 'g', 'b', 'B'].find(has) || 'B';

  // 1. spines, every third column across the middle two thirds of the mass
  const from = x0 + Math.round((x1 - x0) * 0.18);
  const to = x1 - Math.round((x1 - x0) * 0.18);
  for (let x = from; x <= to; x += 3) {
    const top = tops[x];
    if (top < 0) continue;
    const room = Math.min(top, 5);
    if (room < 2) continue;
    const len = 2 + Math.floor(rand() * Math.min(3, room - 1));
    for (let i = 1; i <= len; i++) {
      const y = top - i;
      if (y < 0) break;
      if (cells[y][x] !== T) break;
      cells[y][x] = i === len ? tip : stem;
      // A two-wide base, so a spine reads as growing OUT of the shoulder
      // rather than balancing on it.
      if (i === 1 && x + 1 < w && cells[y][x + 1] === T) cells[y][x + 1] = stem;
    }
  }

  // 2. spurs, off the widest rows of the upper half
  const band = Math.max(1, Math.round(h * 0.22));
  for (let n = 0; n < 6; n++) {
    const y = band + Math.floor(rand() * Math.max(1, Math.round(h * 0.34)));
    const row = cells[y];
    if (!row) continue;
    for (const dir of [-1, 1]) {
      let x = dir < 0 ? 0 : w - 1;
      let guard = 0;
      while (guard++ < w && row[x] === T) x += dir < 0 ? 1 : -1;
      if (guard >= w) continue;
      const len = 2 + Math.floor(rand() * 3);
      for (let i = 1; i <= len; i++) {
        const ox = dir < 0 ? x - i : x + i;   // outward, away from the mass
        if (ox < 0 || ox >= w) break;
        if (row[ox] !== T) break;
        row[ox] = i === len ? tip : stem;
      }
    }
  }
  return cells.map(r => r.join(''));
}

/* The core. Most of these creatures already carry one — the titan's vault
 * lock, the golem's furnace, the lich's soul in the ribs — so phase 2 promotes
 * what is there rather than pasting a second one on top: glow becomes core,
 * core becomes white. The ones that were authored cold get an anchor instead,
 * stamped only where there is already mass to burn through. */
const CORE_SEED = [
  '.ouo.',
  'ouUuo',
  'oUWUo',
  'ouUuo',
  '.ouo.',
];
const CORE_OPEN = [
  '..ouuo..',
  '.ouUUuo.',
  'ouUWWUuo',
  'uUWWWWUu',
  'ouUWWUuo',
  '.ouUUuo.',
  '..ouuo..',
];

/* Stamp that writes only over the creature's own mass, so a core opening in
 * the chest never sprays light outside the silhouette. */
function stampMasked(grid, src, ox, oy) {
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  for (let y = 0; y < src.length; y++) {
    const row = cells[y + (oy | 0)];
    if (!row) continue;
    for (let x = 0; x < src[y].length; x++) {
      const ch = src[y][x];
      if (ch === T || ch === ' ') continue;
      const tx = x + (ox | 0);
      if (tx < 0 || tx >= row.length) continue;
      if (!isMass(row[tx]) && row[tx] !== 'k' && row[tx] !== 'u' && row[tx] !== 'U') continue;
      row[tx] = ch;
    }
  }
  return cells.map(r => r.join(''));
}

function ignite(grid, phase, core) {
  if (phase < BOSS_PHASE.LIT) return grid;
  const hot = grid.map(row => row.replace(/U/g, 'W').replace(/u/g, 'U'));
  return core ? stampMasked(hot, CORE_OPEN, core[0] - 3, core[1] - 3) : hot;
}

/* The anchor before the furnace. Stages 1 to 3 carry a seed where the core
 * will open; ignite() takes over at LIT and would only be overwriting it. */
function ember(grid, phase, core) {
  if (phase < BOSS_PHASE.CHIPPED || phase >= BOSS_PHASE.LIT || !core) return grid;
  return stampMasked(grid, CORE_SEED, core[0] - 2, core[1] - 2);
}

/* Lean a row range progressively, one pixel per `every` rows. Necks, tails and
 * chains all bend rather than slide, and a uniform shiftRows cannot do that. */
function skewRows(grid, from, to, total) {
  const w = Math.max(...grid.map(r => r.length));
  const g = normalise(grid, w);
  const span = Math.max(1, to - from);
  const out = g.slice();
  for (let y = from; y <= to && y < g.length; y++) {
    const dx = Math.round(((y - from) / span) * total);
    if (dx === 0) continue;
    const row = g[y];
    out[y] = dx > 0 ? fit(T.repeat(dx) + row, w) : fit(row.slice(-dx) + T.repeat(-dx), w);
  }
  return out;
}

function filledBounds(grid) {
  let top = grid.length, bottom = 0;
  for (let y = 0; y < grid.length; y++) {
    if (/[^. ]/.test(grid[y])) { if (y < top) top = y; bottom = y; }
  }
  if (top > bottom) { top = 0; bottom = grid.length - 1; }
  return [top, bottom];
}

/* ================================================================
 * FRAMES
 * ================================================================
 * Five, not four. The fourth requirement was "idle breathing", and a single
 * idle frame does not breathe — it needs an exhale to breathe against. So the
 * idle loop is 0 <-> 1 and the fight states are 2, 3, 4.
 *
 * A frame that differs by six units of brightness is not a frame. Every pose
 * below moves actual mass: the chest drops, the weight shifts onto the back
 * foot, the whole body crosses three pixels of ground.
 */
export const BOSS_FRAME = Object.freeze({ IDLE: 0, BREATHE: 1, WINDUP: 2, ATTACK: 3, HURT: 4 });
export const BOSS_FRAME_NAMES = Object.freeze(['idle', 'breathe', 'windup', 'attack', 'hurt']);
export const BOSS_FRAME_COUNT = BOSS_FRAME_NAMES.length;

/* The table the battle layer drives. `hold` is in milliseconds; a hold of 0 on
 * windup means "use this boss's own telegraph length", because a lich winding
 * up and a behemoth winding up are not the same amount of warning. `loop` marks
 * the two frames that belong to the ambient idle cycle. */
export const BOSS_FRAME_TABLE = Object.freeze({
  idle:    Object.freeze({ index: 0, hold: 560, next: 'breathe', loop: true }),
  breathe: Object.freeze({ index: 1, hold: 560, next: 'idle', loop: true }),
  windup:  Object.freeze({ index: 2, hold: 0, next: 'attack', loop: false }),
  attack:  Object.freeze({ index: 3, hold: 240, next: 'idle', loop: false }),
  hurt:    Object.freeze({ index: 4, hold: 200, next: 'idle', loop: false }),
});

export function frameIndex(frame) {
  if (typeof frame === 'number') return ((frame | 0) % BOSS_FRAME_COUNT + BOSS_FRAME_COUNT) % BOSS_FRAME_COUNT;
  const row = BOSS_FRAME_TABLE[String(frame || 'idle').toLowerCase()];
  return row ? row.index : 0;
}

/* ================================================================
 * PHASES
 * ================================================================
 * The fight has phases and now they are real. gauntlet/bestiary.py advances
 * one when a phase's health pool empties, which takes a graded submission, and
 * hands the client `art_phase` — the stage below — in the phase-turn beat.
 *
 * This file shipped with THREE looks (whole, cracked, core) and the argument
 * for three was sound: six sprite sets nobody can tell apart is not six
 * phases. But the fold was made against a fight that never turned, so it was
 * never tested, and it had two defects the measurement found the moment a real
 * phase reached it:
 *
 *   1. Two adjacent phases landed on the same look, which means a phase turn
 *      that changes nothing on screen. The flash fires, the boss speaks, the
 *      tell says it got stronger, and the creature is pixel-identical. That is
 *      worse than no phase at all, because it teaches the player that the
 *      banner is decoration.
 *   2. The one look that reads at any size — the SILHOUETTE — only moved at
 *      look 2. Look 1 was fissures, and a fissure is interior detail: invisible
 *      at map scale, invisible under a screen shake, invisible to a player who
 *      is looking at their own code. Three of the fifteen archetypes moved
 *      literally zero silhouette cells at look 1.
 *
 * So: SIX stages, each of which moves the outline, cumulative, and each of
 * which is a different KIND of change rather than more of the last one.
 *
 *   0 whole      intact. This is the thing that walked in.
 *   1 chipped    the plate is fissured AND the contour is bitten: pieces are
 *                gone off the edge near the authored fault lines.
 *   2 breached   the holes go through. The stage is visible through it.
 *   3 shorn      it loses the part it was carrying — a wing, a maul, a hat —
 *                or, for the one creature whose opening line is about growing
 *                heads, it grows one.
 *   4 lit        the core is open, the fissures are seams of light, and a
 *                third fault opens. The creature's own light is on its bone.
 *   5 crowned    the final form: spines out of its own silhouette, everything
 *                it had left to put out, put out.
 *
 * Six stages of GEOMETRY, three of LIGHT. bossPalette and bossart.dressGrid
 * keep the three they were written against — see lightPhase() — because the
 * palette contract is shared with another file and the brief is explicit that
 * colour is not the part that has to move.
 */
export const BOSS_PHASE = Object.freeze({
  WHOLE: 0, CHIPPED: 1, BREACHED: 2, SHORN: 3, LIT: 4, CROWNED: 5,
  /* The two names this file shipped with. Kept, because they are a public seam
   * — scripts/verify/bossseam.mjs calls bossPhase('cracked') and
   * phaseIndex('core') by name — and pointed at the stage that means what they
   * used to mean: cracked was "hurt and not hiding it", core was "burning from
   * the inside". */
  CRACKED: 1, CORE: 4,
});
export const BOSS_PHASE_NAMES = Object.freeze(
  ['whole', 'chipped', 'breached', 'shorn', 'lit', 'crowned']);
export const BOSS_PHASE_COUNT = BOSS_PHASE_NAMES.length;

/* The six fight phases of world.BOSS_PHASES and gauntlet/bestiary.py's boss
 * phase keys, mapped one to one now that there are six of each. A four-phase
 * region boss does not use all six; artStageFor() stretches its four across
 * them, which is the same arithmetic bestiary.art_phase() does server-side. */
export const BOSS_PHASE_FOR_KEY = Object.freeze({
  recognize: 0, explain: 1, implement: 2, edges: 3, complexity: 4, variant: 5,
  // the encounter kinds, for a caller holding those instead
  pattern_encounter: 0, communication: 1, code_battle: 2,
  edge_case_trap: 3, complexity_duel: 4, memory_ambush: 5,
  // the art stage names themselves, and the two legacy ones
  whole: 0, chipped: 1, breached: 2, shorn: 3, lit: 4, crowned: 5,
  cracked: 1, core: 4,
});

export function phaseIndex(phase) {
  if (typeof phase === 'number' && Number.isFinite(phase)) {
    return Math.max(0, Math.min(BOSS_PHASE_COUNT - 1, phase | 0));
  }
  const row = BOSS_PHASE_FOR_KEY[String(phase || '').toLowerCase()];
  return row === undefined ? 0 : row;
}

/* Phase n of a fight with `phases` phases, as an art stage.
 *
 * MUST AGREE WITH gauntlet/bestiary.py art_phase(). Ceiling division, not
 * rounding: both pin phase 0 to stage 0 and the last phase to the last stage,
 * and the ceiling additionally spends a four-phase boss's three turns on the
 * loud stages (breached, lit, crowned) rather than on the quietest one. The
 * result is distinct for every phase at any phase count from two to six, which
 * is the whole claim: every phase turn moves the outline. */
export function artStageFor(phase, phases) {
  const total = phases | 0;
  if (total <= 1) return 0;
  const n = Math.max(0, Math.min(total - 1, phase | 0));
  return Math.ceil((n * (BOSS_PHASE_COUNT - 1)) / (total - 1));
}

/* The LIGHT stage, 0..2. bossPalette() and bossart.dressGrid() were written
 * against three and both clamp to three; the six above are geometry. Splitting
 * them is deliberate rather than lazy — the palette is a shared contract with
 * bossart.js and the requirement is that the OUTLINE move, not the hue. */
export function lightPhase(stage) {
  const st = phaseIndex(stage);
  if (st <= BOSS_PHASE.WHOLE) return 0;
  return st >= BOSS_PHASE.LIT ? 2 : 1;
}

/* Accepts, in order of preference: an explicit art stage; a phase key; a live
 * fight's {phase, phases}; fx's pip count; a health fraction. Anything it
 * cannot read is stage 0, because a boss that arrives already cracked has
 * thrown away the only moment where cracking it means something. */
export function bossPhase(state) {
  if (state === undefined || state === null) return 0;
  if (typeof state === 'number') {
    // A bare number is a fraction of health remaining when it is in (0,1) and
    // not a whole number; otherwise it is an art stage index.
    if (state > 0 && state < 1) {
      return Math.max(0, Math.min(BOSS_PHASE_COUNT - 1,
        Math.round((1 - state) * (BOSS_PHASE_COUNT - 1))));
    }
    return phaseIndex(state);
  }
  if (typeof state === 'string') return phaseIndex(state);
  /* The server's own word for it, in both spellings, and it wins over every
   * inference below. This is the fix for the defect that made all of this
   * dead code: the fight knew its phase, the art knew how to draw one, and
   * nothing ever carried the number from one to the other. */
  if (state.art_phase !== undefined) return phaseIndex(state.art_phase);
  if (state.artPhase !== undefined) return phaseIndex(state.artPhase);
  if (state.phaseKey !== undefined) return phaseIndex(state.phaseKey);
  if (typeof state.phase === 'string') return phaseIndex(state.phase);
  if (Number.isFinite(state.phase) && Number.isFinite(state.phases)) {
    return artStageFor(state.phase, state.phases);
  }
  /* fx's pip row. `pipsLit` counts the phases STILL STANDING (setEnemyHp lights
   * one per remaining phase), so progress is pips - pipsLit. Legacy: fx passes
   * an explicit phase now and nothing should be arriving here. */
  if (Number.isFinite(state.pipsLit) && Number.isFinite(state.pips)) {
    return artStageFor(state.pips - state.pipsLit, state.pips);
  }
  if (Number.isFinite(state.hp) && Number.isFinite(state.hpMax) && state.hpMax > 0) {
    return bossPhase(Math.max(0.0001, Math.min(0.9999, state.hp / state.hpMax)));
  }
  if (Number.isFinite(state.phase)) return phaseIndex(state.phase);
  return 0;
}

/* ---------------- the beat ----------------
 * Six sub-positions inside the idle loop. The five frames carry the POSE; the
 * beat carries the parts, and every part reads it at its own rate — a jaw at
 * 1.0, a wing at 0.5, a tail at 0.75, a chain at 1.5. That is the whole fix
 * for "uniform motion reads as cheap": with one clock and four rates nothing
 * on the creature is ever at the top of its arc at the same time as anything
 * else, and the eye cannot find the loop.
 *
 * Beats are quantised rather than continuous because a frame is a cached
 * canvas, not a transform. Six is the smallest number that still hides the
 * loop at the idle period the creatures run at, and it costs twelve cached
 * idle frames per boss per phase.
 */
export const BOSS_BEATS = 6;
const TAU = Math.PI * 2;

/* Beat 0 is the authored pose exactly — every drift is measured RELATIVE to
 * it. That is what keeps reduced motion, and every existing caller that never
 * passes a beat, looking like the art as drawn. */
function driftAt(d, beat) {
  if (!d || !beat) return [0, 0];
  const at = (b) => Math.sin(TAU * ((d.rate === undefined ? 1 : d.rate) * b / BOSS_BEATS + (d.phase || 0)));
  const k = at(beat) - at(0);
  return [Math.round((d.x || 0) * k), Math.round((d.y || 0) * k)];
}

/* ---------------- pose kit ----------------
 * Six motion styles cover fourteen creatures. Each takes the assembled,
 * already-mirrored body and returns the deformation for one frame. Horizontal
 * work happens here and not on the half, for the reason given at mirror().
 */
const POSES = {
  /* Anything with feet and too much mass to be quick about it. */
  heavy(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(widenRows(g, bottom - 4, bottom - 1), top, top + 5, 1);
    if (f === 2) return shiftRows(bobGrid(g, -1), top, mid + 2, -3);
    if (f === 3) return squashRows(shiftRows(g, top, mid + 4, 4), bottom - 6, bottom - 1);
    if (f === 4) return shiftRows(sinkRows(g, top, top + 3, 1), top, bottom, -3);
    return g;
  },
  /* No feet. The whole body rises and falls, and the lean is from the waist. */
  float(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return bobGrid(g, 1);
    if (f === 2) return shiftRows(bobGrid(g, -3), top, mid, -2);
    if (f === 3) return shiftRows(bobGrid(g, 2), top, mid + 3, 5);
    if (f === 4) return shiftRows(bobGrid(g, 1), top, bottom, -4);
    return g;
  },
  /* Winged. The exhale is a downbeat, the wind-up is a rear back. */
  flap(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(g, top, top + 8, 1);
    if (f === 2) return shiftRows(bobGrid(g, -2), top, mid, -3);
    if (f === 3) return shiftRows(bobGrid(g, 1), top, mid + 2, 6);
    if (f === 4) return shiftRows(bobGrid(g, 1), top, bottom, -4);
    return g;
  },
  /* Serpentine. Everything bends progressively rather than sliding. */
  coil(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return skewRows(g, top, bottom, 2);
    if (f === 2) return skewRows(g, top, mid, -4);
    if (f === 3) return skewRows(g, top, mid, 7);
    if (f === 4) return shiftRows(skewRows(g, top, bottom, -2), top, bottom, -3);
    return g;
  },
  /* Machinery. It does not breathe, it indexes. Motion is stepped and square. */
  tick(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(g, top, mid, 1);
    if (f === 2) return shiftRows(g, top, mid, -2);
    if (f === 3) return shiftRows(g, top, mid, 4);
    if (f === 4) return shiftRows(sinkRows(g, top, mid, 2), top, bottom, -2);
    return g;
  },
  /* Throned. The only pose in the kit with no horizontal work in it at all.
   *
   * That is a constraint, not a style: shiftRows and skewRows DROP the columns
   * they push past the edge, and the tall rung is authored full-bleed to
   * columns 0 and 95. Any of the five poses above would cut three columns off
   * the cape on the wind-up and the hurt frame and nowhere else, which is a
   * silhouette that changes width with the frame. So this one moves mass up and
   * down only — the head settles into the collar, the whole weight gathers, the
   * hem compresses — and nothing ever leaves the frame. It also happens to be
   * exactly right for the creature: a king does not sway. */
  still(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(g, top, mid, 1);
    if (f === 2) return sinkRows(g, top, top + 20, 2);
    if (f === 3) return squashRows(sinkRows(g, top, mid, 2), mid, bottom - 2);
    if (f === 4) return sinkRows(g, top, bottom - 2, 3);
    return g;
  },
  /* Rooted. The base never moves; only the crown answers the wind. */
  root(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return shiftRows(g, top, top + 10, 1);
    if (f === 2) return skewRows(g, top, mid, -4);
    if (f === 3) return skewRows(g, top, mid, 6);
    if (f === 4) return skewRows(shiftRows(g, top, mid, -2), top, mid, -3);
    return g;
  },
};

/* ================================================================
 * THE LICH
 * ================================================================
 * A robed skeletal caster that never touches the ground. The read, in order of
 * how fast the eye gets it: enormous skull, gold circlet, hollow sockets with
 * one point of cold light each, bone pauldrons spiked outward, a robe that
 * narrows to rags. Three independent parts — the staff, the rune it carries,
 * and the hem — so the silhouette is never rigid.
 *
 * Half-grid, right-aligned: the last character of each row is the centre seam.
 */
const LICH_BODY = [
  '',
  'o..o..o',
  'oZo.oZooZ',
  'oCZooCZCoC',
  'oCCCCCCCCC',
  'ozZzZzZzZz',
  'obCCbbbbbb',
  'oCbbbbbbbbb',
  'oCbbbcccbbb',
  'oCbbkkkkbbb',
  'obbkkuukbbk',
  'occbbbbbbkk',
  'ocCbbbbbbbk',
  '..oCbbbbbbk',
  '...obbbkkbb',
  '...obCbCbCb',
  '....obbbbbb',
  '.....occccc',
  '......ooooo',
  'obCb',
  'obzb',
  'obCbb',
  'occbbbbb',
  'oZo....occbbbbb',
  'oZzo...occbbbbbb',
  'oZbzCoocbbbbbbbbb',
  'oczzzzzcbbbbbbbbbb',
  'oooooooootttttttttt',
  'ozzzzzzzzzzzzzzzzzz',
  'ottttttttttttttttt',
  'otttttttzzztttttt',
  'ottttttzZUZzttttt',
  'otttttuuZuutttttt',
  'ottttuUUUUuttttttt',
  'otttttuuZuuttttttt',
  'ottttttzzzttttttt',
  'ottttttttttttttt',
  'osttttttttttttttt',
  'osttttttttttttttt',
  'osstttttttttttttt',
  'osstttttttttttttttt',
  'ossttttttttttttttt',
  'osssttttttttttttttt',
  'osssttttttttttttttt',
  'ossssttttttttttttttt',
  'ossssttttttttttttttt',
  'osssssttttttttttttttt',
  'osssssttttttttttttttt',
  'ossssssttttttttttttttt',
  'ossssssttttttttttttttt',
  'osssssstttttttttttttttt',
  'osssssttttttttttttttttt',
  'oossssttzzzzzzzzzzzzzz',
  'ooooooooooooooooooooo',
];

/* The staff. Bone shaft, a claw at the head, a rune stone in the claw. Drawn
 * whole rather than mirrored because it lives on one side only. */
const LICH_STAFF = [
  '..ouo..',
  '.ouUuo.',
  'ouUUUuo',
  'ouUUUuo',
  '.ouUuo.',
  '..ouo..',
  '.oZoZo.',
  'oZo.oZo',
  'oZbbbZo',
  '.oZbZo.',
  '..ozo..',
  '..obo..',
  '..oCo..',
  '..obo..',
  '..ozo..',
  '..oCo..',
  '..obo..',
  '..obo..',
  '..ozo..',
  '..obo..',
  '..obo..',
  '..oCo..',
  '..ozo..',
  '..obo..',
  '..oCo..',
  '..obo..',
  '..ozo..',
  '..oCo..',
  '..obo..',
  '..obo..',
  '..ozo..',
  '..obo..',
  '..obo..',
  '..ozzo.',
  '..ooo..',
];

/* The rune stone, lit hotter, on the wind-up and the attack. */
const LICH_STAFF_LIT = LICH_STAFF.map((row, y) => (y > 5 ? row
  : row.replace(/u/g, 'U').replace(/o/g, 'u')));

/* Rags. Drawn under the body so the robe's own outline stays the read. */
const LICH_HEM = [
  '..o...oo....o..oo...o....oo..o..',
  '..o...oo....o..oo...o....oo..o..',
  '.os...os....os.os...os...os..os.',
  '.os...os....os.os...os...os..os.',
  '..o....o....os.os...o....os...o.',
  '..o....o.....o.o....o....o....o.',
  '..o.........o.o.....o.........o.',
  '............o.o...............o.',
];

/* An orbiting soul-light. Its own layer, its own path: it is the only thing on
 * the sprite that moves when the body does not. */
const LICH_ORB = [
  '..ouo..',
  '.ouUuo.',
  'ouUWUuo',
  'ouUUUuo',
  '.ouUuo.',
  '..ouo..',
];

/* ================================================================
 * THE DRAGON
 * ================================================================
 * 96x64, side-on, facing the hero. Five layers: a wing behind everything, the
 * tail behind the body, the torso and legs, the neck and skull, and a lower jaw
 * that drops on its own. Assembling it this way rather than as one grid is what
 * lets the neck lash forward on the attack while the haunches stay planted,
 * which is the entire difference between a dragon and a dragon-shaped statue.
 */
const DRAGON_BODY = [
  '.........................oooo...............',
  '....................BooooBBBBoo.............',
  '................BooooBBBBBBBBBBooo..........',
  '.............BoooBBBBBLLLLBBBBBBBBoo........',
  '............ooBBBLLLLLBBBBBBBBBBBBBBoo......',
  '..........ooBBBLLBBBBBBBBBBBBBBBBBBBBBo.....',
  '........BoBBBLLBBBBBBBBBBBBBBBBBBBBBBBo.....',
  '.......ooBBBLBBBBBBBBBBBBBBBooooBBBBBBBo....',
  '......oBBBBBBBBBBBBBBBBBBBooBBBBooooBBBo....',
  '......oBBBBBBBBBBBBBBBBBBoBBBBBBBBBBoBBBo...',
  '.....BoBBBooBBBBBBBBBBBBoBBBBLLLBBBBoBBBo...',
  '.....oBBooaaoBBBBBBBBBooBBBLLBBBLBBBBoBBBo..',
  '.....oBoaaaaaooBBBBBBoBBBBBBBBBBBLLBBBoBBo..',
  '.....oBoaaaaaaaoBBBBoBBBBBBBBBBBBBBLBBoBBBo.',
  '....BoBBoaaaaaaaoBBBoBBBBBBBBBBBBBBLBBBoBBo.',
  '....oBBBoaaaoaaaaooBoBBBBBBBBBBBBBBLBBBoBBo.',
  '....oBBBoadBooddddaooBBBBBBBBBBBBBBLBBBoBBo.',
  '....oooBBoaoBBooaaaaooBBBBBBBBBBBBBLBBBoBBo.',
  '....oddoBoBoBBBBoaaaaoBBdBBBBBBBBBBBBBoBBo..',
  '....odddoBoBBBBodddaaoBBBdBBBBBBBBBBBBoBBo..',
  '....oddddBoBBBBoaaaaaoBBBBdBBBBBBBBBBBoBBo..',
  '...odddddoBBBBoaaaaaaaooBBBddBBBBBBBBBoBBo..',
  '...oddddBoBBBBoddddddaaooBBBBddBBBBBBoBB.o..',
  '...odddBoBBBBoooaaaaaaaoBooBBBBBBBBooBBoo...',
  '...oddooBBBBBo..ooaaaBoooBBoBBBBBBoBB.o.....',
  '..doBoBBBBBBo.....ooooBBBBoBBBBBBoB.oo......',
  '..oooBBBBBB.o.......ooBBBBoBBBBBBooo........',
  '.doBBBBBBBBo..........ooooBBBBBBBBo.........',
  '.ooooooooooo............oBBBBBBBBBo.........',
  'doCooCooCoo............BoBBBBBBBBBoo........',
  'odoCooCooCo............oBBBBBBBBBBBBoooo....',
  'odooooo.oo..............oBBBBoBBBBoBBBBooo..',
  '.ooo..o..o..............oBBBCoooBCoooBCooo..',
  '.........................oBBoCCCooCCCooCCCo.',
  '..........................ooooooooooooooooo.',
];

/* Skull and neck. The neck is authored as a curve so the lash on frame 3 is a
 * skew of something already bent, not a straight rod pivoting. */
const DRAGON_NECK = [
  '.............................oo.............',
  '...........................ooo..............',
  '........................CooCCo..............',
  '......................CooCCCo...............',
  '.....................ooCCCCCo...............',
  '.....................oCCCCCo.......Coo......',
  '.............BooooooCoCCCC.o....ooooo.......',
  '............ooBBBBBBoCCCCCo..CooCCCo........',
  '...........oBBLLLLLLLoCCCo..CoCCCC.o........',
  '.........ooBLLBBBBBBBBooBooCoCCCC.o.........',
  '......BooBBLBBBBddddddBBoBCoCCCC.o..........',
  '....BooBBBBBBBBddoooooBBBBoCCCC.o...........',
  '..BooBBBBBBBBBBddwewBBBBBBoCCC.o............',
  '.BoBkkBBBBBBBBBBBBBBBBBBBBBoCoo.............',
  'BoBBBBBBBBBBBBBBBBBBBBBBBBBoBo..............',
  'oBBBBBBBBBBBBBkkkkBBBBBBBBBBo...............',
  '.okkkCCkkkCCkkBCCBBBBBBBBBBdo...............',
  '...oooooooBBBBBBBBBBBBBBBBBdo...............',
  '..........oooooooBBBBBBBBBd.o...............',
  '................oaBBBBBBB.do................',
  '................oaaaBBBBood.................',
  '................oaddaBBo...d................',
  '................oBaadddBo..d................',
  '................oBaaaaBBo...d...............',
  '................oBaaaaaBBo..dd..............',
  '.................oaadddBBo....dd............',
  '.................oBaaaadddoo....dddd........',
  '..................oBaaaaaBBBooo.....dddd....',
  '..................oBBaaaaaaaBBBoooo.........',
  '...................oBBaadddaaaaBBBBoo.......',
  '....................ooBaaaaddddaaaBBBoo.....',
  '......................ooBaaaaaaaaaaBBBBoo...',
  '........................ooBaaaaaaaaaaBBBBoo.',
  '..........................ooBaaaaaaaaaBBBB.o',
  '............................ooooooooooooooo.',
];

/* The lower jaw is its own layer. On the attack it drops four pixels and the
 * throat behind it lights. */
const DRAGON_JAW = [
  '.oooooooooooooooooo...',
  '.oCCCCCCCCCCCCCCCBBo..',
  '..oBBBBBBBBBBBBBBBBo..',
  '..ooBBBBBBBBBBBBBBB.o.',
  '....odddddddddddB.oo..',
  '......oooooooooooo....',
  '......................',
];

const DRAGON_JAW_OPEN = [
  'ookkkkkkkkkkkkkkoo....',
  'oBBkkkkkkkkkkkkkkBo...',
  '.oBkkkkkkkkkkkkkkkBo..',
  '.oBkkkkkkkkkkCCCCBBBo.',
  '.oBBkkkCCCCCCBBBBBBBBo',
  '..oBCCCBBBBBBBBBBBBBo.',
  '..ooBBBBBBBddddddBB.o.',
  '....oodddddBB.oooooo..',
  '......oooooooo........',
];

/* Membrane wing: four fingers, a clawed thumb at the leading edge, and a
 * membrane that is one tone darker than the body so it reads as translucent. */
const DRAGON_WING = [
  '..............................................ooo.........',
  '...........................................oooDnnnnno.....',
  '........................................DooDDnnDDDDDnnnn..',
  '.....................................DoooDDnnDGGDDDDD.o...',
  '...................................oooDDnnnDGGDDDDDDoo....',
  '................................DooDDDnnDBGGBDDDDD.o......',
  '.............................DoooDDDnnDGGGBBBDDDD.o.......',
  '.................Co........DooDDDDnnDGGBBBBBDDDDoo........',
  '................Coo......DooDDDnnnBGGBBBBBBDDDDo..........',
  '...............CoCo.....ooDDDnnDGGGBBBBBBBDDDDo...........',
  '...............oCCCo..ooDDDnnDGGBBBBBBBBBBDDDo............',
  '...............oCCCoDoDDnnnBGGBBBBBBBBBBBDDD.o............',
  '...............oCCCooDnnDBGGBBBBBBBBBBBBDDDDo.............',
  '................oCConnDGGGBBBBBBBBBBBBBBDDDo..............',
  '................oConBGGBBBBBBBBBBBBBBBBDDDo...............',
  '...............ooooGGBBBBBBBBBBBBBBBBBDDD.o...............',
  '..............DnnnonnnnBBBBBBBBBBBBBBBDDDo................',
  '.............DonndndBBBnnnnnBBBBBBBBBDDD.o................',
  '.............onDnddnddBBBBBBnnnBBBBBDDDDo.................',
  '............oDnGndddndddBBBBBBBnBBBBDDD.o.................',
  '...........DonGdndddndddddBBBBBnBBBDDDDo..................',
  '...........oDnGdnddddnddddddBBBBnBBDDD.o..................',
  '..........oDnGdddnddddnddddddDBBBnDDDDo...................',
  '.........oDDnGdddndddddnddddDDDDBnDDDDo...................',
  '........DoDnGddddnddddddndddDDDDDDnDDo....................',
  '........oDnGdddddnddddddnddDDooDDDDnDo....................',
  '.......DoDnGdddddnddddddndDD.o.oooono.....................',
  '.......oDnGddddddnddddddnDDDo......on.....................',
  '.......oDGdddddddnddDDDDnDD.o.............................',
  '......oDnGdddddddnDDDDDDDnDo..............................',
  '......oDGdddddddnDDDDDDDDnDo..............................',
  '.....DoGdddddddDnDDooDDDDno...............................',
  '.....onGddddddDDnDo..ooDDno...............................',
  '.....oGdddddddDnDo.....oon................................',
  '....onGdddddddDn.o.......n................................',
  '....oGdddddddDnDo.........................................',
  '...DGddddDDDDDno..........................................',
  '...oGDDDDDDDDDn...........................................',
  '...GDDDDDDDDDno...........................................',
  '..onDDD.ooooon............................................',
  '..nooooo..................................................',
  '..........................................................',
  '..........................................................',
];

/* Tail, tapering to a bladed fluke. Skewed per frame, so it trails. */
const DRAGON_TAIL = [
  '....................ooo.....',
  '.................oooBBBoo...',
  'oooo...........ooBBBBBBBBo..',
  'oBBBoo......oooBBBBBBBBBBo..',
  'oBBBBBoooooBBBBBBBBBBBBBo...',
  '.oBBBBBBBBBBBBBBBBBBBBBo....',
  '..oGnGnGnGnGoBBBBBBBBoo.....',
  '...ooooooooooooooooooo......',
];

/* ================================================================
 * THE KNIGHT  —  worn by The Interviewer
 * ================================================================
 * Full plate, a great helm with nothing behind the visor slit but a cold light,
 * a tower shield and a greatsword. The final boss of a game about interviews is
 * a faceless thing in mirror-polished armour holding a rubric, so the shield
 * carries a graded sigil and the tabard is blood over bone.
 *
 * Steel does not take the boss colour — g/G/n hold their own hue. Only the rim,
 * the visor light and the tabard shift with it, which is what keeps chrome
 * reading as chrome instead of as tinted plastic.
 */
const KNIGHT_BODY = [
  '',
  'o..o..o',
  'oCooCCoC',
  'oCCGGGGGG',
  'oGGGGGGGGG',
  'ogggggggggg',
  'ogGGGGGGGGgg',
  'onmMmggggggg',
  'okkkkkkkkkkk',
  'okkiWikkkkkk',
  'onmMmggggggg',
  'onnggggggggg',
  'onngggkikgggg',
  'onnggMMMggggg',
  'onngggkikgggg',
  'onnggggggggggg',
  'onnnggggggggg',
  'ooonggggggg',
  'onnggggg',
  'oGo...onngggggg',
  'oGGGo..onnggMMgggg',
  'oGGGGGoonnggMMggggg',
  'oggggGGGonngggggggggg',
  'ongggggGGGonngggggggggg',
  'onngggggggGGonnggggggggggg',
  'onnnggggggggGonnggggggggggggg',
  'oonnggggggggonnggggggggggggggg',
  'oonnggggggonnxxxxxxxxxxxxxxxx',
  'oonnggggonnxxxxxxxxxxxxxxxxx',
  'oonngggonnxxxxxxxxxxxxxxxxx',
  'oonnggonnxxxxxxxxzzzxxxxxxx',
  'ooooonnxxxxxxxzZZZzxxxxxx',
  'oonnxxxxxxxzZZZzxxxxxx',
  'oonnxxxxxxxxzzzxxxxxxx',
  'oonngxxxxxxxxxxxxxxxxx',
  'oonnggxxxxxxxxxxxxxxxx',
  'oonngggxxxxxxxxxxxxxxx',
  'oonnggggxxxxxxxxxxxxxx',
  'oonngggggxxxxxxxxxxxxx',
  'oonngggggxxxxxxxxxxxxx',
  'oonnggggggxxxxxxxxxxxx',
  'oonggggggxxxxxxxxxxxx',
  'ooggggggxxxxxxxxxxxx',
  'oggggggo..xxxxxxxxxx',
  'ognMMngo..oxxxxxxxxx',
  'ognMMngo...oxxxxxxxx',
  'ognMMngo....oxxxxxxx',
  'ognMMngo.....oxxxxxx',
  'ognMMngo......oxxxxx',
  'ognMMngo.......oxxxx',
  'ognMMngo........oxxo',
  'oggggggo.........oo.',
  'ongggggno...........',
  'onggMMggno..........',
  'onggMMggno..........',
  'onnggggggno.........',
  'oGGGGGGGGGo.........',
  'oggggggggggo........',
  'oooooooooooo........',
];

/* Tower shield. Its own layer so it can be raised into a guard on the hurt
 * frame — a boss that only ever attacks is a punching bag with a health bar. */
const KNIGHT_SHIELD = [
  'oooooooooooooo',
  'oGGGGGGGGGGGGo',
  'ogggggggggggGo',
  'ogzzzzzzzzzzgo',
  'ogzxxxxxxxxzgo',
  'ogzxggggggxzgo',
  'ogzxgooooGxzgo',
  'ogzxgoiWoGxzgo',
  'ogzxgoWioGxzgo',
  'ogzxgooooGxzgo',
  'ogzxgGGGGGxzgo',
  'ogzxxxxxxxxzgo',
  'ogzzzzzzzzzzgo',
  'oggggggggggggo',
  'ogggggggggggGo',
  'oonggggggggGoo',
  '..onnggggGGo..',
  '...onnggGGo...',
  '....onnGGo....',
  '.....oooo.....',
];

/* Greatsword. Point-down in the guard, overhead on the wind-up, driven through
 * the floor on the attack. */
const KNIGHT_SWORD = [
  '..ooo..',
  '.oGGGo.',
  '.ozZzo.',
  '.ozZzo.',
  '.oGGGo.',
  'ooooooo',
  'oGGGGGo',
  '.oggo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '..oGo..',
  '..oo...',
];

/* Same blade, edge lit — the telegraph. A held weapon that does not change
 * value between wind-up and swing reads as a still image with motion lines. */
const KNIGHT_SWORD_LIT = KNIGHT_SWORD.map(row => row.replace(/G/g, 'W').replace(/g/g, 'i'));

/* ================================================================
 * THE TITAN  —  Hash Titan, and the shape the others are measured against
 * ================================================================
 * A walking vault: iron mask with no face behind it, shoulders wider than the
 * head is tall, a ring of keys on a chain that never stops swinging. The chain
 * is a separate layer for exactly that reason.
 */
const TITAN_BODY = [
  '',
  'oGo......oo',
  'oGGo....oGGo',
  'oGGooooGGGo',
  'oGGGGGGGGo',
  'ogggggggggg',
  'ogGGGGGGGGgg',
  'oggggggggggg',
  'okkkkkkkkkkkk',
  'okkuuukkkkkkk',
  'okkkkkkkkkkkk',
  'ogggggggggggg',
  'ogGGGGGGGGGGgg',
  'oggggggggggggg',
  'oooooooooooooo',
  'ozzzzzzzzzz',
  'ozzzzzzzzzz',
  'ooooo..ogggggggg',
  'oGGGGooogGGGGGGggg',
  'oGGGGGGGGggggggggggg',
  'oggggggggggggggggggggg',
  'onggggggggggggggggggggg',
  'onngggggggoBBBBBBBBBBBBB',
  'onnnggggggoBBBBBBBBBBBBBB',
  'onnnggGGggoBBBzzzzzzzzzBBB',
  'onnnggggggoBBBzBBBBBBBzBBB',
  'oonnggggggoBBBzBuuuuBzBBBB',
  'oonnggggggoBBBzuUUUUuzBBBB',
  'ooonnggggoBBBBzBuuuuBzBBBB',
  'oonnggggoBBBBBzBBBBBBzBBBB',
  'oonngggoBBBBBBzzzzzzzzBBBB',
  'oonggggoBBBBBBBBBBBBBBBBBB',
  'oogggggoBBBBBBBBBBBBBBBBBB',
  'ogggggoBBBBBBBBBBBBBBBBBBB',
  'ooooooooBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBB',
  'ozzzzzzzzzzzzzzzzz',
  'ozzzzzzzzzzzzzzzzz',
  'oBBBBBBBBBBBBBBBB',
  'oBBBgggggggggBBBB',
  'oBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBB',
  'ooooooooooooo',
  'oBBBBBBBBo.....',
  'oBBBBBBBBo.....',
  'oggggggggo.....',
  'oBBBBBBBBo.....',
  'oBBBBBBBBo.....',
  'oggggggggo.....',
  'oBBBBBBBBo.....',
  'oBBBBBBBBo.....',
  'oBBBBBBBBBo....',
  'oBBBBBBBBBo....',
  'ozzzzzzzzzo....',
  'oBBBBBBBBBBo...',
  'oBBBBBBBBBBo...',
  'ooooooooooooo..',
];

/* Vault keys on a chain, swinging off the right shoulder. */
const TITAN_CHAIN = [
  'oMo',
  'omo',
  'oMo',
  'omo',
  'oMo',
  'omo',
  'oMo',
  'omo',
  'ozo',
  'ozzo',
  'ozZzo',
  'ozzzzo',
  'ozZzzo',
  '.ozzo.',
  '..ozzo',
  '...ozo',
  '...ozo',
  '..ooo.',
];

/* ================================================================
 * THE COLOSSUS  —  the Rolling Titan
 * ================================================================
 * Two bosses in world.py share the sprite key "titan", and two identical
 * silhouettes in one playthrough is a bug the player sees. This is the second:
 * hunched, asymmetric, a drum of wound cable for a shoulder and a maul it drags
 * rather than carries.
 */
const COLOSSUS_BODY = [
  '',
  '..........oo',
  '.........oGGo',
  '........oGGGGo',
  '.......oggggggo',
  '.......ogkkkkkgo',
  '.......ogkuuukggo',
  '.......ogkkkkkggg',
  '.......oggggggggg',
  '.......oGGGGGGGGG',
  '.......ooggggggggg',
  '.........oooooooooo',
  '............ozzzzzzz',
  'oooo........ozzzzzzz',
  'oMMMoo......oBBBBBBBB',
  'oMmmMMoooooooBBBBBBBBB',
  'oMmmmmMMMMMMMBBBBBBBBBB',
  'oMmmmmMoooooooBBBBBBBBBBB',
  'oMmmmMo......oBBBBBBBBBBBBB',
  'oMMMMo.......oBBBBBBBBBBBBBB',
  '.oooo........oBBBBBBBBBBBBBBB',
  '.............oBBBBuuuuuBBBBBBB',
  '............oBBBuUUUUUuBBBBBBB',
  '............oBBBBuuuuuBBBBBBBB',
  '............oBBBBBBBBBBBBBBBBB',
  '...........oBBBBBBBBBBBBBBBBBB',
  '...........oBBBBBBBBBBBBBBBBBB',
  '..........oBBBBBBBBBBBBBBBBBBB',
  '..........ogggggggggggggggggggg',
  '.........oggggggggggggggggggggg',
  '.........oggggggggggggggggggggg',
  '........oonnggggggggggggggggggg',
  '.......oonnnggggggggggggggggggg',
  '......oonnnngggggggggggggggggg',
  '......onnnnggggggggggggggggg',
  '......onnnggggggggggggggg',
  '......ooogggggggggggggg',
  '........oggggggggggggo',
  '........oooooooooooooo',
  'oggggggggo.....',
  'oggggggggo.....',
  'onnggggggo.....',
  'onnggggggo.....',
  'onnnggggggo....',
  'onnnggggggo....',
  'oGGGGGGGGGo....',
  'oggggggggggo...',
  'ogggggggggggo..',
  'ooooooooooooo..',
];

/* The maul. Dragged on idle, hauled up on the wind-up, through the floor on 3. */
const COLOSSUS_MAUL = [
  '.ooooooooo.',
  'oMMMMMMMMMo',
  'oMnnnnnnnMo',
  'oMnggggGnMo',
  'oMnggggGnMo',
  'oMnnnnnnnMo',
  'oMMMMMMMMMo',
  '.ooonnnooo.',
  '...ongno...',
  '...ongno...',
  '...ongno...',
  '...onGno...',
  '...ongno...',
  '...ongno...',
  '...ongno...',
  '...onnno...',
  '....ooo....',
];

/* ================================================================
 * THE HYDRA  —  96x64
 * ================================================================
 * A low serpentine torso and three necks, each its own layer on its own phase.
 * The whole point of the creature is that the heads are not synchronised: cut
 * the animation down to one rigid grid and it stops being a hydra.
 */
const HYDRA_BODY = [
  '...........................oBBBBBBBBBBBBo...........................',
  '........................oBBBBBBBBBBBBBBBBBBo........................',
  '.....................oBBBBBBBBBBBBBBBBBBBBBBBBo.....................',
  '..................oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo..................',
  '................oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo................',
  '..............oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo..............',
  '............oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo............',
  '..........oBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBo..........',
  '.........oBBBBBBBBBBBBBBBBBBBBddddddddBBBBBBBBBBBBBBBBBBBBo.........',
  '........oBBBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBBBo........',
  '.......oBBBBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBBBBo.......',
  '......oBBBBdBBBBBBBBBBBBBBBBBBddddddddBBBBBBBBBBBBBBBBBBdBBBBo......',
  '.....oBBBBdBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBdBBBBo.....',
  '.....oBBBBdBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBdBBBBo.....',
  '....oBBBBdBBBBBBBBBBBBBBBBBBBBddddddddBBBBBBBBBBBBBBBBBBBBdBBBBo....',
  '....oBBBBdBBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBBdBBBBo....',
  '.....oBBBBdBBBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBBBdBBBBo.....',
  '......oBBBBdBBBBBBBBBBBBBBBBBBddddddddBBBBBBBBBBBBBBBBBBdBBBBo......',
  '.......oBBBBdBBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBBdBBBBo.......',
  '........oBBBBdBBBBBBBBBBBBBBBBAAAaaaaaBBBBBBBBBBBBBBBBdBBBBo........',
  '.........oBBBBdBBBBBBBBBBBBBBBddddddddBBBBBBBBBBBBBBBdBBBBo.........',
  '.........oBBBBdBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBdBBBBo.........',
  '........oBBBBdBBBBBBBBBBooooooooooooooooooooBBBBBBBBBBdBBBBo........',
  '.......oBBBBBBBBBBBBBBBB....................BBBBBBBBBBBBBBBBo.......',
  '......oBBBBBBBBBBBBBBBBB....................BBBBBBBBBBBBBBBBBo......',
  '......oBCBBBCBBBCBBBCBBB....................CBBBCBBBCBBBCBBBCo......',
  '.......ooooooooooooooooo....................ooooooooooooooooo.......',
];

/* One neck. Drawn once, drawn three times, at three offsets and three phases. */
const HYDRA_NECK = [
  '..........o....oo.......',
  '.........oBo..oao.......',
  '....ooooBBBBooBBBo......',
  '...oBBBBwwBBBBBBBBo.....',
  '..oBBBBweBBddBBBBBo.....',
  '.oBBBBBBeBBdBBBBBBo.....',
  '.oCCBCBBBoBBBddBBBo.....',
  '.okkkkkkoBBBBddBBBo.....',
  '..oCBCBBoBBBddBBBo......',
  '...ooooooBBBddBBBo......',
  '........oBBBddBBBo......',
  '........oBBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBBo.....',
  '.........oBBddBBBBo.....',
  '.........oBBddBBBBo.....',
  '.........oBBddBBBBo.....',
  '........oBBBddBBBBo.....',
  '........oBBBadBBBBo.....',
  '........oBBBaaBBBBo.....',
  '........oBBBaaBBBBo.....',
  '........oBBBBaBBBBBo....',
  '........oBBBBaBBBBBo....',
  '........oBBBBBBBBBBo....',
  '........oBBBBBBBBBBo....',
  '........oBBBBBBBBBBo....',
  '........oBBBBBBBBBBo....',
];

const HYDRA_NECK_BITE = [
  '..........o....oo.......',
  '.........oBo..oao.......',
  '....ooooBBBBooBBBo......',
  '...oBBBBwwBBBBBBBBo.....',
  '..oBBBBweBBddBBBBBo.....',
  '.oBBBBBBeBBdBBBBBBo.....',
  '.oCCBCBBBoBBBddBBBo.....',
  '.okkkkkkkkoBBddBBBo.....',
  '.okkkkkkkkoBBddBBBo.....',
  '..oCBCBCBoBBBddBBBo.....',
  '........oBBBddBBBo......',
  '........oBBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBo......',
  '.........oBBddBBBBo.....',
  '.........oBBddBBBBo.....',
  '.........oBBddBBBBo.....',
  '.........oBBddBBBBo.....',
  '........oBBBddBBBBo.....',
  '........oBBBadBBBBo.....',
  '........oBBBaaBBBBo.....',
  '........oBBBaaBBBBo.....',
  '........oBBBBaBBBBBo....',
  '........oBBBBaBBBBBo....',
  '........oBBBBBBBBBBo....',
  '........oBBBBBBBBBBo....',
  '........oBBBBBBBBBBo....',
  '........oBBBBBBBBBBo....',
];

/* ================================================================
 * THE WRAITH
 * ================================================================
 * A hood with nothing in it but two points of light, skeletal hands, and a
 * shroud that never resolves into legs. The shroud tails are separate layers
 * with separate phases, which is what stops it reading as a bell.
 */
const WRAITH_BODY = [
  '',
  '.......ooooo',
  '.....ootttttt',
  '....ottttttttt',
  '...ottttttttttt',
  '..otttsssssttttt',
  '..ottsskkkksstttt',
  '.ottsskkkkkksstttt',
  '.ottskkkkkkkkkstttt',
  '.otsskkkukkkkkkkttt',
  '.otsskkkkkkkkkkkkkt',
  '.ottskkkkkkkkkkkkkt',
  '.ottsskkkkkkkkkkkkt',
  '.otttsskkkkkkkkkkkt',
  '.ottttsskkkkkkkkkkt',
  '.otttttssskkkkkkkkt',
  '.ottttttsssskkkkkkt',
  '.otttttttttsssskkkt',
  '.ottttttttttttssskt',
  '.otttttttttttttttst',
  'oCCo.ottttttttttttt',
  'oCCCo.ottttttttttttt',
  'oCbCCo.ottttttttttttt',
  'oCbbCCo.ottttttttttttt',
  '.oCbbCo..ottttttttttttt',
  '..oCCo....otttttttttttttt',
  '...oo.....ottttttttttttttt',
  '..........ottttttttttttttts',
  '.........ottttttttttttttttts',
  '.........otttttttttttttttttts',
  '........ottttttttttttttttttts',
  '........otttttttttttttttttttt',
  '.......osttttttttttttttttttttt',
  '.......osstttttttttttttttttttt',
  '......ossstttttttttttttttttttt',
  '......ossstttttttttttttttttttt',
  '.....osssstttttttttttttttttttt',
  '.....osssstttttttttttttttttttt',
  '....ossssstttttttttttttttttttt',
  '....osssssstttttttttttttttttt',
  '...osssssssttttttttttttttttt',
  '...ossssssstttttttttttttttt',
  '..osssssssstttttttttttttt',
  '..osssssssstttttttttttt',
  '.ooosssssssttttttttt',
  '...oosssssstttttt',
  '.....oossssttt',
  '.......ooooo',
];

const WRAITH_TAIL = [
  '..o....o.....o..',
  '..o....o.....o..',
  '.os...os....os..',
  '.os...os....os..',
  '.os...os....os..',
  '..o...os.....o..',
  '..o....o.....o..',
  '..o....o........',
  '.......o........',
];

/* ================================================================
 * THE BEHEMOTH
 * ================================================================
 * Front-on quadruped. The head sits LOW, under the shoulder line, with tusks
 * that clear the jaw and a row of plates running up the spine behind it. That
 * one relationship — head below shoulders — is what makes it read as an animal
 * instead of a person in a costume, and it is the only boss in the file built
 * that way.
 */
const BEHEMOTH_BODY = [
  '...............ao............................aoo................',
  '..............ooo...........................ooaoo...............',
  '.............oaaoo.........................oaaaoBo..............',
  '............oaaaoBoo......................aoaaaoBBo.............',
  '...........aoaaaoBBBo..o..................oaaaaoBBBo............',
  '..........BoaaaaaoBBBoaoo................aoaaaBoBBBBo.o.........',
  '.........oooaaaaaoBBBBoao...............ooaaaaoBBBBBooo.........',
  '........oBoaaaaaaoBBBaoaao............oooaaaaaoBBBBBaoao........',
  '.......oBBoaaaaaaoBBBoaaaao.........ooBaoaaaaaoBBBBaoaao........',
  '.......oBaoaaaaaooBBaoaaaaooo.....ooBBBooaaaaaoBBBBoaaaao.......',
  '.......oBoaaaaooBBBBooooooooBoo.ooBBBBBBBooooaoBBBoaaaaao.......',
  '......BoBoaBooBBBBBBBBBBBBBBBBBoBBBBBBBBBBBBBooBBaoaaaaaoo......',
  '......oBoBooBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBaoaaaaaaao......',
  '......oBooBBBBBBLLBBBBBBBBBBBBBBBBBBBBBBBBBBBLLLLLoooooooo......',
  '......oBBBBBBBLLBBLLBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBLBBBBBBBo.....',
  '......oBBBBBBLBBBBBBLLBBBBBBBBBBBBBBBBBBBBBBBBBBBBBLBBBBBBo.....',
  '......oBBBBBLBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBLBBBBBo.....',
  '.....BoBBBBBoBBBBBBBBBoooBBBBBBBBBBBBBBboooBBBBBBBBBBLBBBBo.....',
  '.....oBBBBBboBBBBBBBBobbbooooBBBBBoooooobbboBBBBBBBBBBoBBBBo....',
  '.....oBBBBBoCBBBBBBBobbbbbbbbooooobbbbbbbbboBBBBBBBBBBoooBBo....',
  '.....oBBBBBoCBBooBBobbbbbbbbbbbbbbbbbbbbbbbboBBBBBBBBbobboBo....',
  '.....oBBBBobCooBBobccbbbbbbbbbbbbbbbbbbbbccbboBooBBBBobCboBo....',
  '.....oBBBBobCoBBBbobccccccbbbbbbbbbbbcccccbbbboBBooooobCboBo....',
  '.....oBBooobCoBBbobbccccccccbbbbbbbcccccccbbbboBBBBBBobCboBBo...',
  '.....oBBoBBoCoBBobbbckkkccccbbbbbbbcccckkkbbbbboBBBBBobCboBBo...',
  '.....oBoBBBoCboBobbbbccckrkbbbbbbbbbkrkccbbbbboBBBBBobCboBBBo...',
  '.....oBoBBBobCboBobbbbbbcccbbbbbbbbbcccccbbbbBoBBBBBobCboBB.o...',
  '......BoBBBobCboBobbbbbbbbbbbbbbbbbbbbbbbbbbBoBBBBBBobCbooBo....',
  '......oBBBBBobCbooobbbbbbboooooooooooobbbbbboBBBBLBobbCbooBo....',
  '......oBBBBBobbCbboooobbbcoccccccccccobbbbboBBBBBBobbCbboBoo....',
  '.....oBBLBBBBobCbbbbbbooboccccccccccccobbbooBBBBBbobbCbboBo.....',
  '.....oBBLBBBBBobCbbbbbboboccckccccckccobbbooBBBBbobbCbboBBBo....',
  '.....oBBLBBBBBBobCCbbbbococcckccccckccobbbooBBboobbCbbBoBBBo....',
  '.....oBBLBBBBBBBobbCCbbooccccccccccccccobbooooobbbbCbLoBBBBo....',
  '.....oBLBBBBBBBdBoooobboocccccccccccccboboobbbbbbCCbboLBBBBo....',
  '....BoBLBBBBBBBdBBBBoooobocccccccccccbobbobbbbbCCbbboBLBBBBo....',
  '....oBBLBBBBBBBdBBBBoobbbbookCkkkkkCkobbbBobbCCbbbbBoBLBBBBo....',
  '....oBBLBBBBBBBdBBBoBobbbbbboccccccbobbbBoobbbbbbBooBBBLBBBo....',
  '....oBBLBBBBBBBdBBBoBBoobbbbbooooooobbbBoBBobBooooBBBBBLBBBo....',
  '....oBBLBBBBBBBdBBBoBBBBoobbbbbbbbbbbbBoBBBooooBdBBBBBBBBBBBo...',
  '....oBBBLBBBBBBdBBBoBBBBBBoobbbbbbbbbBoBBBBBBoBBdBBBBBBBBBBBo...',
  '....oBBBLBBBBBBdBBBoooooooooooooooooooBBBBBBBoBBdBBBBBBBBBBBo...',
  '....oBBBLBBBBBBdBBBBodddddo....ooooooooooooooBBBdBBBBBBBBBBBo...',
  '....oBBoBBBBoBBBBoBBoddddddo.........odddddBoBBoBBBBoBBBBoBBo...',
  '....oBCoooBCoooBCoooodddddddo........odddddoBBCoooBCoooBCoooo...',
  '....oBoCBoBoCBoBoCBoodddddddo.......dodddddoBBoCBoBoCBoBoCBoo...',
  '....oCoCoBCoCoBCoCooddd.oooooo......odddddddoCoCoBCoCoBCoCoo....',
  '....oooooooooooooooooooo............ooooooooooooooooooooooo.....',
];

/* Tail, whipping behind the right haunch. */
const BEHEMOTH_TAIL = [
  '...........ooo',
  '.........ooBBo',
  '.......ooBBBo.',
  '.....ooBBBBo..',
  '...ooBBBBo....',
  '.ooBBBBo......',
  'oBBBBo........',
  'oBBBo.........',
  'oaao..........',
  'oao...........',
  'oo............',
];

/* ================================================================
 * THE GOLEM
 * ================================================================
 * Quarried, not grown. Slab head with no face, a core burning between the
 * shoulders, and two rune tablets that orbit on their own layer — the only
 * thing about it that looks alive.
 */
const GOLEM_BODY = [
  '',
  '..........ooooooooooo',
  '.........oBBBBBBBBBBB',
  '.........oBBBDBBBBBBB',
  '.........oBBBBBBBBBBB',
  '.........oBBBBoooooooo',
  '.........oBBBBokkkkkkk',
  '.........oBBBBokuuuuuu',
  '.........oBBBBokkkkkkk',
  '.........oBBBBoooooooo',
  '.........oBBBDBBBBBBBB',
  '.........oBBBBBBBBBBBB',
  '.........ooooooooooooo',
  '............oBBBBBBBBB',
  '............ooooooooooo',
  'oooooo......oBBBBBBBBBBB',
  'oBBBBBooooooBBBDBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBDBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBDBBBBBBB',
  'ooooooBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBoooBBBBBBBBBBBB',
  'oBBBBBBBBBBo.oBBBBooooooooo',
  'oBBBDBBBBBBo.oBBBokuuuuuuuu',
  'oBBBBBBBBBBo.oBBBokuUUUUUUU',
  'oBBBBBBBBBo..oBBBokuUUWWWWW',
  'oooooBBBBBo..oBBBokuUUUUUUU',
  'oBBBBBBBBBo..oBBBokuuuuuuuu',
  'oBBBBBBBBo...oBBBooooooooooo',
  'oBBBBBBBBo...oBBBBBBBBBBBBBB',
  'oBBBDBBBBo...oBBBBBBBBBBBBBB',
  'oBBBBBBBo....oBBBDBBBBBBBBBB',
  'ooooooooo....oBBBBBBBBBBBBBB',
  'oBBBBBBo.....oBBBBBBBBBBBBBB',
  'oBBBBBBo.....ooooooooooooooo',
  'oBBBBBBo.......oBBBBBBBBBBBB',
  'oBBBBBBo.......oBBBDBBBBBBBB',
  'oBBBBBBo.......oBBBBBBBBBBBB',
  'ooooooo........oBBBBBBBBBBBB',
  '...............ooooooooooooo',
  'oBBBBBBBBBBo......',
  'oBBBDBBBBBBo......',
  'oBBBBBBBBBBo......',
  'ooooooooooooo.....',
  'oBBBBBBBBBBBo.....',
  'oBBBBBDBBBBBo.....',
  'oBBBBBBBBBBBBo....',
  'oBBBBBBBBBBBBo....',
  'oBBBBBBBBBBBBBo...',
  'oooooooooooooo....',
];

/* Rune tablets. They orbit; the body does not. */
const GOLEM_RUNE = [
  'oooooo',
  'oBuuBo',
  'ouUUuo',
  'oBuuBo',
  'oBBBBo',
  'oooooo',
];

/* ================================================================
 * THE ENT
 * ================================================================
 * A tree that noticed you. Root legs spread wider than the trunk, a face read
 * out of a knot in the bark, and a canopy that carries the whole silhouette.
 * Rooted motion: the base never moves, only the crown answers.
 */
const ENT_BODY = [
  '',
  '.........oo...oo..oo',
  '......oooaaoooaaooaao',
  '....ooaaaaBaaaaaBaaaao',
  '...oaaaaaaaBaaaaBaaaaao',
  '..oaaaBBaaaaaaaaaaaBBaao',
  '.oaaaBBBaaaaaaaaaaBBBaaa',
  'oaaaaBBaaaaaaBBaaaaBBaaaa',
  'oaaaaaaaaaaaBBBBaaaaaaaaa',
  'oaaBBaaaaaaaaBBaaaaaBBaaa',
  'oaBBBBaaaaaaaaaaaaaBBBBaa',
  'oaaBBaaaaaaBBaaaaaaaBBaaa',
  '.oaaaaaaaaaBBBaaaaaaaaaaa',
  '..oaaaaBBaaaBBaaaaBBaaaaa',
  '...ooaaBBBaaaaaaaaBBaaaaa',
  '.....ooaaBaaaaaaaaaaaaaaa',
  '.......oooaaaaaaaaaaaaaaa',
  '..........ooaaaaBBaaaaaaa',
  '...........oooaaaaaaaaaaa',
  '..............oooaaaaaaaa',
  '................ojjjjjjjj',
  '...............ojjjjjjjjj',
  '..............ojjjjjjjjjj',
  '.............ojjjjjjjjjjj',
  '.............ojjokkojjjjj',
  '............ojjokrrkojjjj',
  '............ojjokkkkojjjj',
  '............ojjjokkojjjjj',
  '...........ojjjjjjjjjjjjj',
  '...........ojjjjjJJjjjjjj',
  '...........ojjjjjjjjjjjjj',
  '..........ojjjooooooooooo',
  '..........ojjokCkCkCkCkCk',
  '..........ojjokkkkkkkkkkk',
  '..........ojjjokCkCkCkCkC',
  '.........ojjjjjooooooooooo',
  '.........ojjjjjjjjjjjjjjjj',
  '........ojjjjJjjjjjjJjjjjj',
  '........ojjjjJjjjjjjJjjjjj',
  '.......ojjjjjJjjjjjjJjjjjj',
  '.......ojjjjjJjjjjjjJjjjjj',
  '......ojjjjjjJjjjjjjJjjjjj',
  '......ojjjjjjJjjjjjjJjjjjj',
  '.....ojjjjjjjJjjjjjjJjjjjj',
  '.....ojjjjjjjJjjjjjjJjjjjj',
  '....ojjjjjjjjJjjjjjjJjjjjj',
  '....ojjjjoojjjjjjjjjjjjjjj',
  '...ojjjjo..ojjjjjjjjjjjjjj',
  '..ojjjjo....ojjjjjjjjjjjjj',
  '..ojjjo......ojjjjjjjjjjjj',
  '.ojjjo........ojjjjjjjjjjj',
  'ojjjo..........ojjjjjjjjjj',
  'ojjo............ojjjjjjjjj',
  'ojo.............ojjjjjjjjj',
  'oo..............ojjjjjjjjj',
  '................ooooooooooo',
];

/* A branch arm, hung off the trunk and swinging on its own period. */
const ENT_BRANCH = [
  'ooo...........',
  'ojo...........',
  'ojjoo.........',
  '.ojjjoo.......',
  '..ojjjjoo.....',
  '...oojjjjoo...',
  '.....oojjjjo..',
  '.......oojjjo.',
  '.........ojjjo',
  '.........oaajo',
  '........oaaao.',
  '........oaao..',
  '.........oo...',
];

/* ================================================================
 * THE NECROMANCER
 * ================================================================
 * The lich's living predecessor: a hood with a face still under it, a grimoire
 * held open, and a summoned skull orbiting the free hand. Deliberately smaller
 * in the shoulders than the lich, so the two read apart at a glance even though
 * they share a robe.
 */
const NECRO_BODY = [
  '',
  '............oooo',
  '..........ootttto',
  '.........otttttttt',
  '........ottttttttt',
  '.......ottttttttttt',
  '.......ottttsssssstt',
  '......ottsskkkkkksst',
  '......ottskkkkkkkkks',
  '......otskkkuukkkkkk',
  '......otskkkkkkkkkkk',
  '......ottskkkkkkkkkk',
  '......ottsskkkkkkkkk',
  '.......ottssskkkkkkk',
  '.......otttssssskkkk',
  '........ottttttsssss',
  '.........ootttttttttt',
  '............ottttttttt',
  '...........otttttttttttt',
  '.........oottttttttttttttt',
  '.......ootttttttttttttttttt',
  '......ottttttttttttttttttttt',
  '.....otttttttttttttttttttttt',
  '.....ottttttttttttttttttttttt',
  'ooo..ottttttttttttttttttttttt',
  'ojjo.ottttttttttttttttttttttt',
  'ojJjooottttttuuuuutttttttttttt',
  'ojJJjooottttuUUUUUuttttttttttt',
  'ojJJJjootttttuuuuutttttttttttt',
  'ojJJjoo.ottttttttttttttttttttt',
  'ojjoo...osttttttttttttttttttttt',
  'ooo.....osstttttttttttttttttttt',
  '........ossstttttttttttttttttttt',
  '.......ossssttttttttttttttttttt',
  '.......osssstttttttttttttttttt',
  '......ossssstttttttttttttttttt',
  '......ossssstttttttttttttttttt',
  '.....osssssstttttttttttttttttt',
  '.....osssssstttttttttttttttttt',
  '....ossssssstttttttttttttttttt',
  '....ossssssstttttttttttttttttt',
  '...osssssssstttttttttttttttttt',
  '...osssssssstttttttttttttttttt',
  '..ossssssssstttttttttttttttttt',
  '..ossssssssstttttttttttttttttt',
  '.osssssssssstttttttttttttttttt',
  '.osssssssssstttttttttttttttttt',
  'ooooooooooooooooooooooooooooo',
];

/* The summoned skull. It orbits the free hand and it is the one thing on the
 * sprite that is not made of cloth. */
const NECRO_SKULL = [
  '.oooooo.',
  'obbbbbbo',
  'obkkbkkb',
  'obkkbkkb',
  'obbbbbbo',
  'obCbCbCo',
  '.oooooo.',
];

/* ================================================================
 * THE AUTOMATON
 * ================================================================
 * Brass, rivets and one cold lens. It does not breathe — the pose kit gives it
 * `tick`, stepped motion with no easing — and the only organic thing about the
 * silhouette is that the gear in its chest never stops turning. The gear and
 * the piston arm are separate layers so they can run at different rates, which
 * is what sells "machine" rather than "robot suit".
 */
const AUTOMATON_BODY = [
  '',
  '..........oooooooo',
  '.........oggggggggo',
  '.........ogGGGGGGGgo',
  '.........ognnnnnnngo',
  '.........ognkkkkkngo',
  '.........ognkiiikngo',
  '.........ognkiWikngo',
  '.........ognkiiikngo',
  '.........ognkkkkkngo',
  '.........ogGGGGGGGgo',
  '.........oggggggggggo',
  '..........oooooooooooo',
  '............omomomomom',
  '............omomomomom',
  '..........ooogggggggggg',
  'ooooo....oogggggggggggggo',
  'oggggoooogggggggggggggggggo',
  'ogGGGggggggggggggggggggggggo',
  'ognnnggggggggggggggggggggggg',
  'ognggggggggggggggggggggggggg',
  'ogggggggggooooooooooggggggggg',
  'ogggggggggo........ogggggggggg',
  'onngggggggo........ogggggggggg',
  'onnggggggo..........ogggggggggg',
  'onnggggggo..........ogggggggggg',
  'onnnggggo...........ogggggggggg',
  'onnnggggo...........ogggggggggg',
  'ooonggggo..........ogggggggggg',
  '..ongggggo.........ogggggggggg',
  '..onggggggoooooooooggggggggggg',
  '..onggggggggggggggggggggggggg',
  '..onnggggggggggggggggggggggg',
  '...onnggggggggggggggggggggg',
  '...oonnnggggggggggggggggggg',
  '.....ooonnggggggggggggggggg',
  '........ooogggggggggggggggg',
  '..........ozzzzzzzzzzzzzzzz',
  '..........ozzzzzzzzzzzzzzzz',
  '..........ogggggggggggggggg',
  '.........oggggggggo....ogggo',
  '.........oggggggggo....ogggo',
  '........oggggggggo.....ogggo',
  '........omomomomo......ogggo',
  '........omomomomo......ogggo',
  '........oggggggggo.....ogggo',
  '.......oggggggggggo....ogggo',
  '.......oggggggggggo....ogggo',
  '.......ogGGGGGGGGgo....ogggo',
  '......ogggggggggggo...oggggo',
  '......oooooooooooo....ooooo',
];

/* A real gear: teeth on the rim, spokes across the bore. Four rotations, one
 * per quarter turn, indexed by frame. Rotating it at draw time would mean a
 * transform per frame; four authored grids mean none. */
const AUTOMATON_GEAR = [
  '..ozo..ozo..',
  '.ozZo.ozZo..',
  'oozzooozzoo.',
  'ozzzzzzzzzzo',
  'ozzooozzozzo',
  'ozzo.ozzo.zo',
  'ozzooozzooZo',
  'ozzzzzzzzzzo',
  'oozzooozzoo.',
  '.ozZo.ozZo..',
  '..ozo..ozo..',
];

const AUTOMATON_GEAR_TURNED = [
  '.ozo..ozo...',
  'ozZoo.ozZo..',
  'ozzzzoozzzo.',
  'oozzzzzzzzoo',
  '.ozzooozzzzo',
  'ozzoo.ozzozo',
  'ozzzoozzzoZo',
  'oozzzzzzzzoo',
  '.ozzzooozzo.',
  '.ozZo.ozZoo.',
  '..ozo..ozo..',
];

/* The piston arm: a rod in a sleeve. Extends four pixels on the attack. */
const AUTOMATON_PISTON = [
  'ooooo',
  'ogGgo',
  'ogngo',
  'ogngo',
  'ooooo',
  '.ono.',
  '.oMo.',
  '.ono.',
  '.oMo.',
  '.ono.',
  '.oMo.',
  'ooooo',
  'ogGgo',
  'ogngo',
  'ooooo',
];

/* ================================================================
 * THE DEMON
 * ================================================================
 * Horns out rather than up, a mane of live ember, a chest built like a ribcage
 * and digitigrade legs ending in hoof. Two wings and a chain flail, all three
 * on their own layers. The ember tones (r/R/f) hold their own hue against the
 * body colour on purpose: fire that takes the creature's tint stops being fire.
 */
const DEMON_BODY = [
  '...................o............................oo..............',
  '..................Coo........................CooCCo.............',
  '..................oCCo.....................CooCCC.o.............',
  '...................oCCoo.................CooCCCC.o..............',
  '...................oCCCCo...............CoCCCCC.o...............',
  '....................oCCCCoo............CoCCCCC.o................',
  '.....................oCCCCCoo.Boooo...CoCCCCC.o.o...............',
  '.....................oCCCCCCCooBBBBooCoCCCCC.o.ro...............',
  '......................ooCCCCCoBBBBBBBoCCCCC.o..oo...............',
  '........................oooCBoBLLLBBBBoCCC.o..roro..............',
  '...................o......oooLLBBBLLBBoCCoo.Boorro..............',
  '...................oo....oBBBBBBBBBBBBBdBoooororro..............',
  '...................oro...oBddBBBBBBBdddBooBBBooooo....ro........',
  '....................oro..oBBkkddBBBddkkBBoBBBBoBBBo.roo.........',
  '....................o.ooooBBBBrkBBBkrdBBoBBBBBoooBBooro.........',
  '...................ooooBBBoBBBBBBBBBBBBBoBBBBoBBBoorro..........',
  '..................oBBBBBBBoBBBBkkkkBBBBBoBBBBoBBoorrro..........',
  '.................BBoBBBBBBoBBBkCkkkCBBBBoLLBBoBBBBoooo..........',
  '.................BoBoBBBBBBoBBBkkkkkBBBoLxxBoBBBBBBBoBo.........',
  '................ooBBBoBBBBBBoBBBBkkBBLoxxxxBoBBBBBBBBBBo........',
  '...............oBBBBBoBBLLLBBoBBBBBBLoxxxxxxBBBBBBBBBBBo........',
  '..............oBBLBBBBoBxxxLLLoooBBooxxxxxxxBBBBBBBBBBBBo.......',
  '.............oBBLBBBBBBxxxxxxxforooooxxxxxxxooBBBBBBBBBBBo......',
  '............BoBBLBBBBBoxxxxxxxofrRrfoxxxxxxBBBooBBBBdBBBBo......',
  '............oBBLBBBBBBoxxxxxxxofrrfoxxxxxxBBBB.oooBBBdBBBBo.....',
  '...........oBBLBBBBBBoBBxxxxxxxoffBoxxxxxBBBBBo...oBBdBBBBo.....',
  '..........oBBLBBBBBB.oBBBxxxxxxoffoxxxxxBBBBB.o...oBBBdBBBBo....',
  '.........BoBBLBBBBB.ooBBBBBBxxxBoBoxxBBBdBBBBo....oBBBdBBBBo....',
  '.........oBBLBBBBB.o..oBBBBdBBBBBoBBBBddBBBBBo....oBBBBdBBBo....',
  '.........oBBLBBBB.o...oBBBBBddBBBBBBddBBBBBBo......oBBBdBBBo....',
  '........oBBLBBBB.o.....oBBBBBBddddddBBBBdBBBo......oBBdBBB.o....',
  '........oBBLBBB.o......oBBBdBBBBBBBBBBddBBBBo......oBBdBBBo.....',
  '........oBBLBB.o........oBBBddBBBBBBddBBBBBo......BoBBdBBBo.....',
  '.......oBBBLBBo.........ooBBBBddddddBBBBdBBo......oBBdBBBBo.....',
  '.......oBBLBBBo........oBBodBBBBBBBBBBddBBo......BoBBdBBCoo.....',
  '.......oBBLBBBo.......BoBBoBddBBBBBBddBBBoBoo....oBBBBCooCo.....',
  '......BoBBLBBBo......BoBBBBoBBddddddBBBBoBBBBo..BoBBBooCCCo.....',
  '......ooBBBBBBo......oBBBBBBoBBBBBBBBBBBoBBBBo..oBBBBBoCCCCo....',
  '......ooBBBBBoo......oBBBBBBBoooooBBBBBoBBBBBBo..oBBCooooCCCo...',
  '......ooBBoBBoo......oBBBBBBBBBo..oooooBBBBBBBBo..oooCoo.oCCo...',
  '.....oCCoCooBoo.......oBBBBBBB.o.....oBBBBBBBBBBo..ooCCo..oCo...',
  '.....oCCooCoooo.......oBBBBBBBo.......ooBBBBBBBBo...oCCo...oo...',
  '....CoCoooCCooCo......oBBBBBB.o.........oBBBBBBBBo...oCCo...oo..',
  '....oC.ooCC.ooCo.....BoBBBBB.o...........oBBBBBBo....oCCo...oo..',
  '....oCo.oCCo.oCo.....oBBBBB.o...........oBBBBBBo......oCo....o..',
  '...Co.o.oCCo..ooo...BoBBBB.o...........BoBBBBB.o.......oo.......',
  '...ooo..oCo.....o...oBBBBBo............oBBBBB.o.........oo......',
  '...o....o.o........BoBBBBBo...........BoBBBBBo...........o......',
  '........oo.........oBBBBBBBo..........oBBBBBBBo.................',
  '........o..........oBCoBBBBoo.........oBBCoBBBBoCo..............',
  '...................oooCooBBBCooo......oBooCooBBCoCo.............',
  '...................oooooooBoooCooo....ooooooooBoooCooo..........',
  '...................oooooooooooooo.....ooooooooooooooo...........',
];

/* Bat-frame wing, drawn once and flipped for the other side. The membrane is
 * two tones under the body so it reads as skin stretched thin. */
const DEMON_WING = [
  '.......................oooo',
  '....................oooDDDo',
  '.................oooDDDDDBo',
  '..............oooDDDDDDDdo.',
  '...........oooDDDDDDDDDdo..',
  '.........ooDDDDDDDDDDDBo...',
  '.......ooDDDDDDDDDDDDBo....',
  '.....ooDDDDDDDDDDDDDBo.....',
  '....oDDDDDDDDDDDDDDBo......',
  '...oDDDDDDDdoDDDDDBo.......',
  '..oDDDDDDDdo.oDDDDBo.......',
  '..oDDDDDDdo..oDDDDBo.......',
  '.oDDDDDDdo...oDDDDBo.......',
  '.oDDDDDDdo...oDDDBo........',
  'oDDDDDDdo....oDDDBo........',
  'oDDDDDdo.....oDDBo.........',
  'oDDDDdo......oDDBo.........',
  'oDDDdo.......oDBo..........',
  'oDDdo........oDBo..........',
  'oDdo.........oBo...........',
  'oddo.........oBo...........',
  'oodo.........oo............',
  '.oo........................',
];

/* Chain and flail head. Swings wide on the wind-up and lands on 3. */
const DEMON_FLAIL = [
  'omo',
  'oCo',
  'omo',
  'oCo',
  'omo',
  'oCo',
  'ooooo',
  'oxXXo',
  'oXrRo',
  'oxXXo',
  'ooooo',
];

/* ================================================================
 * THE WYRM  —  96x64
 * ================================================================
 * No legs, no wings, and therefore no obvious way to read scale except by the
 * coils. So it is built out of coils: one authored ring stamped three times at
 * three offsets, a neck, a frilled skull and a jaw that unhinges. The `coil`
 * pose bends every row progressively, so the whole animal swims.
 */
const WYRM_COIL = [
  '.......oooooooooooo.......',
  '....oooBBBBBBBBBBBBooo....',
  '..ooBBBBBBBBBBBBBBBBBBoo..',
  '.oBBBBBBBBBBBBBBBBBBBBBBo.',
  'oBBBBBBoooooooooooBBBBBBBo',
  'oBBBBBo...........oBBBBBBo',
  'oBBBBo.............oBBBBBo',
  'oBBBBo.............oBBBBBo',
  'oBBBBo.............oBBBBBo',
  'oBBBBBo...........oBBBBBBo',
  'oaaaaaBoooooooooooBaaaaaao',
  'oaaaaaaaaaaaaaaaaaaaaaaaao',
  '.oaaaaaaaaaaaaaaaaaaaaaao.',
  '..ooaaaaaaaaaaaaaaaaaaoo..',
  '....oooaaaaaaaaaaaaooo....',
  '.......oooooooooooo.......',
];

const WYRM_NECK = [
  '....oooooo....',
  '..ooBBBBBBoo..',
  '.oBBBBBBBBBBo.',
  'oBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBo',
  'oaaaaaaaaaaaao',
  'oaaaaaaaaaaaao',
  '.oaaaaaaaaaao.',
  '..oooooooooo..',
];

const WYRM_HEAD = [
  '..........oo.......oo.....',
  '.........oCo......oCo.....',
  '........oCCo.....oCCo.....',
  '.......oCCo.....oCCo......',
  '.oooooCCooooooooCCo.......',
  'oBBBBBBBBBBBBBBBBBoo......',
  'oBBBBBBBBBBBBBBBBBBBo.....',
  'oBBweBBBBBweBBBBBBBBo.....',
  'oweeBBBBBweeBBBBBBBBBo....',
  'oBweBBBBBBweBBBBBBBBBo....',
  'oBBBBBBBBBBBBBBBBBBBBo....',
  'oBBBBBBBBBBBBBBBBBBBBBo...',
  'oCoCoCoCoCoBBBBBBBBBBBo...',
  '.ooooooooooBBBBBBBBBBBBo..',
  '...........oBBBBBBBBBBBBo.',
  '............oaaaaaaaaaaaao',
];

const WYRM_JAW = [
  'ooooooooooo.',
  'oCoCoCoCoBo.',
  'oBBBBBBBBBo.',
  '.ooooooooo..',
];

const WYRM_JAW_OPEN = [
  'ooooooooooo.',
  'okkkkkkkkBo.',
  'oikkkkkkkBo.',
  'oiikkkkkkBBo',
  'oCoCoCoCoBBo',
  'oBBBBBBBBBBo',
  '.ooooooooooo',
];

/* A crest of fins along the spine, the only part of the wyrm that is not the
 * wyrm's own colour. */
const WYRM_FIN = [
  '..o..o...o..',
  '.oio.oio.oio',
  'oiio.oiio.io',
  'oiioooiiooio',
];

/* ================================================================
 * THE LAST INTERPRETER  —  the face of the final practical
 * ================================================================
 * A python at the scale where the room is a consequence of the animal, coiled
 * three turns deep, wearing a hat that was ceremonial once and is now simply
 * very old. Spectacles in gold, because nine hundred years of reading is nine
 * hundred years of reading.
 *
 * It is assembled from the same kit as the wyrm and deliberately NOT from the
 * wyrm's grids: the two would read as the same animal in two colours, and this
 * one is the last thing the player sees. What it borrows is the layering — the
 * coils run a third of a turn apart so the length swims along itself instead of
 * pulsing — and nothing else.
 *
 * The staff is a separate layer behind the body and is never animated with the
 * head. It does not move. That is the characterisation: the creature has been
 * holding it in the same position for nine centuries and the fight is not a
 * reason to change that.
 */
const INTERP_COIL = [
  '.......oooooooooooo.......',
  '....oooBBBBBBBBBBBBooo....',
  '..ooBBBBBBaBBBBaBBBBBBoo..',
  '.oBBBBBBBBBBBBBBBBBBBBBBo.',
  'oBBBBBBoooooooooooBBBBBBBo',
  'oBaBBBo...........oBBBBaBo',
  'oBBBBo.............oBBBBBo',
  'oBaBBo.............oBBBaBo',
  'oBBBBo.............oBBBBBo',
  'oBaBBBo...........oBBBBaBo',
  'oBBBBBBoooooooooooBBBBBBBo',
  'oaBBBBBBBBBBBBBBBBBBBBBBao',
  '.oBBBBBBaBBBBBBaBBBBBBBBo.',
  '..ooBBBBBBBBBBBBBBBBBBoo..',
  '....oooBBBBBBBBBBBBooo....',
  '.......oooooooooooo.......',
];

/* Gold frames, cold lenses. `e` is the shared deep tone the whole file
 * collapses its dark ends onto, so the rims cost no palette slot of their own.
 */
const INTERP_HEAD = [
  '......oooooooooooo......',
  '....ooBBBBBBBBBBBBoo....',
  '..ooBBBBBBBBBBBBBBBBoo..',
  '.oBBBBBBBBBBBBBBBBBBBBo.',
  'oBBBBBBBBBBBBBBBBBBBBBBo',
  'oBaaaaoBBBBoaaaaoBBBBBBo',
  'oaoiiaoBBBBoaoiiaBBBBBBo',
  'oaaiiaaaaaaaaiiaaBBBBBBo',
  'oBaooaBBBBBBaooaBBBBBBBo',
  'oBBBBBBBBBBBBBBBBBBBBBBo',
  'oBaBBBBBBBBBBBBBBBBBBBBo',
  '.oBBBBBBBBBBBBBBBBBBBBo.',
  '..oBBBBBBBBBBBBBBBBBBBo.',
  '...ooooooooooooooooooo..',
  '........................',
  '........................',
];

/* The one length of it that is neither coil nor head, so the animal reads as
 * continuous rather than as a portrait next to some rings. */
const INTERP_NECK = [
  '...oooooooo...',
  '.ooBBBBBBBBoo.',
  'oBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBo',
  'oBaBBBBBBBBaBo',
  'oBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBo',
  '.ooBBBBBBBBoo.',
  '...oooooooo...',
];

const INTERP_JAW = [
  '...ooooooooooooo....',
  '...obobobobobBBo....',
  '...oBBBBBBBBBBBo....',
  '....ooooooooooo.....',
];

/* The one frame where it opens. `i` is the cold lens tone doing double duty as
 * the light coming back up out of the throat, which is the single most
 * unsettling thing available inside the palette budget. */
const INTERP_JAW_OPEN = [
  '...ooooooooooooo....',
  '...okkkkkkkkkkBo....',
  '..okkkkkkkkkkkkBo...',
  '..okkkkkkkkkkkkBBo..',
  '..obobobobobobBBo..',
  '..oBBBBBBBBBBBBBBo..',
  '...oooooooooooooo...',
];

/* Cloth, a gold band, and one rune at the point. The brim is wider than the
 * head by a lot, which is the whole silhouette: seen from the doorway this
 * animal is a circle with a triangle on it. */
const INTERP_HAT = [
  '.............oo.............',
  '............oiao............',
  '............otto............',
  '...........otTTto...........',
  '...........otTTto...........',
  '..........otTTTTto..........',
  '..........otTTTTto..........',
  '.........otTTTTTTto.........',
  '.........otTTTTTTto.........',
  '........otTTTTTTTTto........',
  '.......otTTTTTTTTTTto.......',
  '......oaaaaaaaaaaaaaao......',
  '....oootttttttttttttttooo...',
  '..ootTTTTTTTTTTTTTTTTTTTToo.',
  '.otTTTTTTTTTTTTTTTTTTTTTTTTo',
  '..ooooooooooooooooooooooooo.',
];

const INTERP_STAFF = [
  '..oao...',
  '.oaiao..',
  'oaiiiao.',
  '.oaiao..',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..obo...',
  '..ooo...',
];

/* ================================================================
 * THE INTERVIEWER  —  the Null King, and the only 96x128 in the game
 * ================================================================
 * THE FINAL RUNG. docs/08 §B names a 96x128 final-boss box — FFVI's own
 * big-summon size — and for a whole migration nothing in this tree drew one.
 * The Interviewer is what it is for. It is authored as a 48-column half at 128
 * rows and drawn at scale 1, so ONE authored cell is ONE stage pixel: the hero
 * spends four stage pixels per authored cell and an ordinary boss two, and this
 * is the only creature in the game rendered at the stage's own grain. The box
 * is 12x16 tiles; the painted content fills all 128 rows and all 96 columns,
 * which is deliberate — the geometry in §A-6 that justifies the ground line at
 * 175 is only true if the rig is actually full-bleed.
 *
 * WHY IT IS NARROWER THAN THE BOSS IT REPLACES, AND WHY THAT IS THE POINT.
 * The Interviewer used to be the knight: a 64x64 rig at scale 2, so 128x128
 * logical, sunk nine authored rows into the floor. This is 96x128 at scale 1 —
 * 32 logical columns NARROWER and exactly as tall. Measured that way it looks
 * like a downgrade and it is worth saying why it is not:
 *
 *   IT IS TALLER WHERE IT COUNTS. The knight's bottom eighteen logical rows are
 *     under the ground line and veiled by the floor. This one has a sink of 0,
 *     so all 128 rows stand above the floor: rows 47..174 against the knight's
 *     visible 65..174. Eighteen more rows of creature, and its crown clears the
 *     hero's head by thirty-two.
 *   A VERTICAL SILHOUETTE IS THE BIGGER SHAPE. 96x128 is 3:4. 128x128 is a
 *     square, and a square the height of the frame reads as a wall rather than
 *     as a figure. The two 96-column wide rigs are 192 logical across and read
 *     as big by being broad; this one is the only thing in the cast that reads
 *     as big by being TALL, which is the shape a king is.
 *   IT HAS FOUR TIMES THE DRAWING. 12,288 authored cells against the knight's
 *     4,096, and each of them survives to the screen as itself rather than as a
 *     2x2 block. The crown's notches, the sigil's ring, the caret on the slate
 *     and the nib of the pen are all one and two pixels wide and all of them
 *     are legible, which none of them could be on a rig drawn at 2.
 *
 * WHO IT IS. gauntlet/bestiary.py: the last boss, region null_kings_castle,
 * element VOID. A faceless great helm with NO VISOR SLIT — there is nothing
 * behind it that needs to see out — under a crown of five spires whose band is
 * the top of the head, because on this creature the crown and the skull cannot
 * be told apart and that is the whole complaint. A null sigil on the chest: a
 * gold ring with nothing inside it, and it is the ring's own hole that the core
 * opens through at the LIT stage. Beside it, not held by anything, the rubric —
 * a rectangle of nothing with a caret waiting in the corner — and the pen,
 * which is the length of a spear and whose nib is the brightest pixel on the
 * creature. Everything about this fight is somebody deciding about you with an
 * instrument you never see used.
 *
 * VOID takes the contre-jour away (bossart.wantsRim is false for it), so the
 * separation this one gets from a near-black stage is its own pale nullsteel
 * and the two gold objects, not a rim. That is the element doing its job: the
 * one creature in the cast that refuses the light the whole cast is lit by.
 *
 * It sheds the CROWN at the shorn stage — the largest silhouette change
 * available on a figure this vertical — and at the crowned stage a second crown
 * grows out of the bare head in void and glow, which is the fight's last beat
 * said in geometry: you take the crown off it and it makes another one.
 */
const NULL_BODY = [
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  'oBBBBBGGG',
  'oBBBBBBnGGG',
  'oBBBBBBBBnGGG',
  'oBBBBBBBBBnGGG',
  'oBBBBBBBBBBnGGG',
  'oBBBBBBBBBBBnGGG',
  'oooooooooooooGGG',
  'LLLLLLLLLLLLLGGG',
  'BBBBBBBBBBBBBBBB',
  'oDoooooooooooooo',
  'oDDnnnnnnnnnnnnD',
  'oDDnnnnnnnnnnnnD',
  'oDDnnnnnnnnnnnD',
  'oDDnnnnnnnnnnnD',
  'oDDtttttttttnD',
  'oDDttttttttnD',
  'oDDttttttttnD',
  'oDDttttttttttt',
  'oHLnnnnnnnnnnBBB',
  'oHLDDDDDDDDDDDBBB',
  'oHLBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBB',
  'oHLooooooooooooooooooo',
  'oHLnnnnnnnnnnnnnnnnnnnn',
  'oHLBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBB',
  'oHLooooooooooooooooooooo',
  'oHLnnnnnnnnnnnnnnnnnnnnnn',
  'oHLBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBnBBBnBBBnBBBnBBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLBHBBBHBBBHBBBHBBBmMmMBBBBBBBBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBmMmMmMmBBBBBBBBBB',
  'oHLBBBBBBBBBBBBBBBBBBBBBBBBBBBBMmMmMmMBBB',
  'oHLDDDDDDDDDDDDDDDBBBBBBBBBBBBBBBBBBBBBBB',
  'oHLnnnnnnnnnnnnnnnBBBBBBBBBBBBBBBBBBBBB',
  'oHLnnnnnnnnnnnnnnBBBBBBBBBBBBBBBBBBB',
  'oHBBBBBDno..nDnBBBBBBBBBBBBBBBBBBBB',
  'oHBBBBDno..nDnBBBBBBBBBBBBBBBBBBBB',
  'oooooooo..nDnoooooooooooooooooooo',
  'oHBBDno..nDnHHHHHHHHHHHHHHHHHHHH',
  'oHBDno..nDnoooooooooooooooooooo',
  'oHDno..nDnBBBBBBBBBBBBBBBBZZZZ',
  'oHDno..nDnBBBBBBBBBBBBBBZZZZZZ',
  'oHDno..nDnBBBBBBBBBBBBBZZZZZZZ',
  'oHDno..nDnBBBBBBBBBBBBZZZZkkkk',
  'oHDno..nDnBBBBBBBBBBBZZZZkkkkk',
  'ooooo..nDnBBBBBBBBBBBZZZkkkkkk',
  'oHDno..nDnBBBBBBBBBBZZZZkkkkkk',
  'oHDno..nDnBBBBBBBBBBZZZkkkkkkk',
  'oHDno..nDnBBBBBBBBBBZZZkkkkkkk',
  'oHDno..nDnBBBBBBBBBBzzzkkkkkkk',
  'oHDno..nDnBBBBBBBBBBzzzkkkkkkk',
  'oHDno..nDnBBBBBBBBBBzzzkkkkkkk',
  'oHDno..nDnBBBBBBBBBBzzzzkkkkkk',
  'ooooo..nDnBBBBBBBBBBBzzzkkkkkk',
  'oHDno..nDnBBBBBBBBBBBzzzzkkkkk',
  'oHDno..nDnBBBBBBBBBBBBzzzzkkkk',
  'oHDno..nDnBBBBBBBBBBBBBzzzzzzz',
  'oHDno..nDnBBBBBBBBBBBBBBzzzzzz',
  'oHDno..nDnBBBBBBBBBBBBBBBBzzzz',
  'oHDno..nDnBBBBBBBBBBBBBBBBBBBB',
  'oHDno..nDnBBBBBBBBBBBBBBBBBBBB',
  'ooooo..nDnBBBBBBBBBBBBBBBBBBdd',
  'oHDno..nDnBBBBBBBBBBBBBBBBBBdd',
  'oHDno..nDnBBBBBBBBBBBBBBBBBBdd',
  'oHBDno..nDnBBBBBBBBBBBBBBBBBBdd',
  'oHBDno..nDnBBBBBBBBBBBBBBBBBBdd',
  'oHBDno..ooooooooooooooooooooooo',
  'oHBDno..zzzzzzzzzzzzzzzzzzzzkkk',
  'oHDno..ZZZZZZZZZZZZZZZZZZZZkkk',
  'ooooo..zzzzzzzzzzzzzzzzzzzzkkk',
  'oHDno..nnnnnnnnnnnnnnnnnnnnnnn',
  'oooooooooooooooooooooooo',
  'ooooooooooooooooooooooooo',
  'oTsttTotttttttttTottoTsssss',
  'oTstttTotttttttttTottoTsssss',
  'oTsttttTotttttttttTottoTsssss',
  'oTstttttTotttttttttTottoTsssss',
  'oTsttttttTotttttttttTottoTsssss',
  'oTstttttttTotttttttttTottoTsssss',
  'oTstttttttTotttttttttTottoTsssss',
  'oTsttttttttTotttttttttTottoTsssss',
  'oTstttttttttTotttttttttTottoTsssss',
  'oTstttttttttTotttttttttTottoTsssss',
  'oTsotttttttttTotttttttttTottoTsssss',
  'oTsotttttttttTotttttttttTottoTsssss',
  'oTsTotttttttttTotttttttttTottoTsssss',
  'oTsTotttttttttTotttttttttTottoTsssss',
  'oTstTotttttttttTotttttttttTottoTsssss',
  'oTstTotttttttttTotttttttttTottoTsssss',
  'oTsttTotttttttttTotttttttttTottoTsssss',
  'oTsttTotttttttttTotttttttttTottoTsssss',
  'oTsttTotttttttttTotttttttttTottoTsssss',
  'oTstttTotttttttttTotttttttttTottoTsssss',
  'oTstttTotttttttttTotttttttttTottoTsssss',
  'oTstttTotttttttttTotttttttttTottoTsssss',
  'oTsttttTotttttttttTotttttttttTottoTsssss',
  'oTsttttTotttttttttTottttoooooooooooossss',
  'oTsttttTotttttttttTottttonnnnnnnnnnossss',
  'oTsttttTotttttttttTottttonnnnnnnnnnossss',
  'oTstttttTotttttttttTottttoHBBBBBBBBDossss',
  'oTstttttTotttttttttTottttonnnnnnnnnnossss',
  'oTstttttTotttttttttTottttoHBBBBBBBBDossss',
  'TTTTTTTTTTTTTTTTTTTTTTTTTonnnnnnnnnnoTTTT',
  'sssssssssssssssssssssssssoHBBBBBBBBDossss',
  'ooooooooooooooooooooooooooooooooooooooooo',
];

/* The mantle. Its own layer, and BEHIND the body, so the cape passes behind the
 * shoulders and pools out past the hem instead of being a painted-on border. It
 * is what carries the rig to columns 0 and 95 at the floor. */
const NULL_CAPE = [
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  'oTsso.........................',
  'oTsso.........................',
  'oTsso..........................',
  'oTsso..........................',
  'oTsso...........................',
  'oTsso....................................',
  'oTsso......................................',
  'oTsso.......................................',
  'oTsso.......................................',
  'oTsso......................................',
  'oTsso.......................................',
  'oTsso.......................................',
  'oTsso.....................................',
  'oTsso..................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssso................................',
  'oTsssssssssssssso...........................',
  'oTssssssssssssso............................',
  'oTsssssssssssso.............................',
  'oTssssssssssso..............................',
  'oTsssssssssso...............................',
  'oTssssssssso................................',
  'oTssssssssso................................',
  'oTsssssssso.................................',
  'oTssssssso..................................',
  'oTssssssso..................................',
  'oTsssssso...................................',
  'oTsssssso...................................',
  'oTssssso....................................',
  'oTssssssso....................................',
  'oTsssssso.....................................',
  'oTsssssso.....................................',
  'oTssssso......................................',
  'oTssssso......................................',
  'oTssssso......................................',
  'oTsssso.......................................',
  'oTsssso.......................................',
  'oTsssso.......................................',
  'oTssso........................................',
  'oTssso........................................',
  'oTsssssssTossssssssssssTossssssssssssTosssssssss',
  'oTsssssssTossssssssssssTossssssssssssTosssssssss',
  'oTsssssssTossssssssssssTossssssssssssTosssssssss',
  'oTsssssssTossssssssssssTossssssssssssTosssssssss',
  'oTsssssssTossssssssssssTossssssssssssTosssssssss',
  'oTsssssssTossssssssssssTossssssssssssTosssssssss',
  'tttttttttttttttttttttttttttttttttttttttttttttttt',
  'oooooooooooooooooooooooooooooooooooooooooooooooo',
];

/* The crown. Five spires on a notched band, and the band is where the dome of
 * the helm would be. Shed at the shorn stage. */
const NULL_CROWN = [
  '.............oooooooo.............',
  '.............oZZooZZo.............',
  '.............oZZooZZo.............',
  '.............ozzoozzo.............',
  '.......oooo..ozzoozzo..oooo.......',
  '.......oZZo..ozzoozzo..oZZo.......',
  '.......oZZo..ozzoozzo..oZZo.......',
  '.......ozzo..ozzoozzo..ozzo.......',
  '.......ozzo..ozzoozzo..ozzo.......',
  '.oooo..ozzo..ozzoozzo..ozzo..oooo.',
  '.oZZo..ozzo..ozzoozzo..ozzo..oZZo.',
  '.oZZo..ozzo..ozzoozzo..ozzo..oZZo.',
  '.ozzo..ozzo..ozzoozzo..ozzo..ozzo.',
  '.ozzo..ozzo..ozzoozzo..ozzo..ozzo.',
  '.ozzo..oZZZZZZZZZZZZZZZZZZo..ozzo.',
  '....oZZZZZZZZZZZZZZZZZZZZZZZZo....',
  '..ozzzzzzzzzzzzzzzzzzzzzzzzzzzzo..',
  '.ozkkzzzkkzzzkkzzzkkzzzkkzzzkkzzo.',
  '.ozkkzzzkkzzzkkzzzkkzzzkkzzzkkzzo.',
  '.oooooooooooooooooooooooooooooooo.',
];

/* The rubric: a slate with a void face and a caret in the corner. */
const NULL_RUBRIC = [
  'ooooooooooooooo',
  'oGGGGGGGGGGGGGo',
  'ogggggggggggggo',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkiikkkkkkgno',
  'oGgkiikkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'oGgkkkkkkkkkgno',
  'ogggggggggggggo',
  'onnnnnnnnnnnnno',
  'ooooooooooooooo',
];
/* The same slate with the caret answered. Two frames of telegraph, and the only
 * thing that changes is the one thing on it that was ever going to. */
const NULL_RUBRIC_LIT = NULL_RUBRIC.map(row => row.replace(/i/g, 'W'));

/* The pen. Point down in the guard, and it is the only part of this creature
 * that ever moves fast. */
const NULL_PEN = [
  '.oooooo.',
  '.zzzzzz.',
  '.ZkkkkZ.',
  '.zkkkkz.',
  '.zzzzzz.',
  '.oooooo.',
  '..ozzo..',
  '..oZZo..',
  '..ozzo..',
  '..ozzo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..onno..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..onno..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..onno..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '..oGgo..',
  '...oo...',
  '...WW...',
  '...WW...',
  '...W....',
];
const NULL_PEN_LIT = NULL_PEN.map(row => row.replace(/G/g, 'W').replace(/g/g, 'i'));

/* What grows back at the crowned stage, out of a head you have already taken a
 * crown off: thinner, taller, and made of the absence rather than the gold. */
const NULL_NEWCROWN = [
  '.............uuuu.............',
  '.............uuuu.............',
  '.............uuuu.............',
  '.........uu..uuuu..uu.........',
  '.........uu..uuuu..uu.........',
  '.........uu..uuuu..uu.........',
  '.........uu..uuuu..uu.........',
  '.....uu..uu..uuuu..uu..uu.....',
  '.....uu..uu..uuuu..uu..uu.....',
  '.....uu..uu..uuuu..uu..uu.....',
  '.....uu..uu..uuuu..uu..uu.....',
  '.....uu..uu..uuuu..uu..uu.....',
  '.uu..uu..uu..uuuu..uu..uu..uu.',
  '.uu..uu..uu..uuuu..uu..uu..uu.',
  '.uu..uu..uu..uuuu..uu..uu..uu.',
  '.uu..uu..uu..uuuu..uu..uu..uu.',
  '.uu..uu..uu..uuuu..uu..uu..uu.',
  '.uu..uu..uu..uuuu..uu..uu..uu.',
  '.uuuuuuuuuuuuuuuuuuuuuuuuuuuu.',
  '.kkkkkkkkkkkkkkkkkkkkkkkkkkkk.',
  '.kkkkkkkkkkkkkkkkkkkkkkkkkkkk.',
  '.kkkkkkkkkkkkkkkkkkkkkkkkkkkk.',
];

/* ================================================================
 * REGISTRY
 * ================================================================
 * One entry per archetype. `body` is the authored mass; `parts` are the layers
 * that move independently, each carrying its own five-frame offset table and,
 * where the pose genuinely changes shape rather than position, its own
 * alternate grid. `behind: true` puts a layer under the body.
 *
 * Motion metadata is not decoration. `telegraph` is how long the wind-up frame
 * is held, in milliseconds, and it is per-boss on purpose: a lich that gives
 * 900ms of warning and a demon that gives 320ms are different fights before a
 * single number changes. `scale` is what the battle stage should draw it at.
 */
const ART = {
  lich: {
    name: 'Lich', wide: false, colour: '#8f3f6f', accent: '#c7a6ff', anim: 'float',
    body: { half: LICH_BODY, oy: 1, drift: { x: 0, y: 1, rate: 1, phase: 0.25 } }, wear: 0.05,
    motion: { bob: 3, sway: 2, phase: 0.50, period: 2600, telegraph: 900 },
    stage: { scale: 2, sink: 11, bias: -9 },
    core: null,                                       // the reliquary is authored in the ribs
    faults: [[26, 8, 12], [38, 8, 12], [19, 26, 7], [45, 26, 7]],
    shed: 'soul',                                // shorn: the soul in its orbit goes out
    parts: [
      { name: 'hem', grid: LICH_HEM, ox: 16, oy: 53, behind: true,
        frames: [[0, 0], [0, 1], [-1, -1], [2, 2], [-2, 1]],
        drift: { x: 2, y: 1, rate: 0.5, phase: 0.10 } },
      { name: 'staff', grid: LICH_STAFF, ox: 3, oy: 12,
        frames: [[0, 0], [0, 1], [1, -4], [4, 3], [-3, 2]],
        drift: { x: 1, y: 2, rate: 0.75, phase: 0.30 },
        alt: { 2: LICH_STAFF_LIT, 3: LICH_STAFF_LIT } },
      { name: 'soul', grid: LICH_ORB, ox: 52, oy: 20,
        frames: [[0, 0], [1, 2], [4, -4], [-8, 5], [3, 4]],
        drift: { x: 4, y: 3, rate: 1.5, phase: 0 } },
    ],
  },
  dragon: {
    name: 'Dragon', wide: true, colour: '#3f9c5a', accent: '#d8c07a', anim: 'flap',
    body: { grid: DRAGON_BODY, ox: 36, oy: 29, drift: { x: 0, y: 1, rate: 1, phase: 0.20 } }, wear: 0.04,
    motion: { bob: 3, sway: 1, phase: 0.30, period: 1500, telegraph: 520 },
    stage: { scale: 2, sink: 3, bias: -14 },  // -14, not -12: the sway is part of the box, below
    core: [55, 40],                                   // furnace behind the sternum
    faults: [[30, 26, 12], [52, 34, 14], [60, 46, 10]],
    shed: 'wing',                                // shorn: a wing is torn off at the shoulder
    parts: [
      // The wing is the slowest thing on the creature and the jaw the fastest.
      // One clock, four rates: nothing is ever at the top of its arc twice.
      { name: 'wing', grid: DRAGON_WING, ox: 32, oy: 2, behind: true,
        frames: [[0, 0], [0, 2], [-2, 0], [2, 4], [1, 2]],
        drift: { x: 1, y: 1, rate: 0.5, phase: 0 },
        skew: [0, 1, -2, 3, 0] },
      { name: 'tail', grid: DRAGON_TAIL, ox: 62, oy: 48, behind: true,
        frames: [[0, 0], [0, 1], [2, -1], [-2, 2], [3, 1]],
        drift: { x: 2, y: 1, rate: 0.75, phase: 0.35 },
        skew: [0, 3, -4, 6, -2] },
      { name: 'neck', grid: DRAGON_NECK, ox: 8, oy: 10,
        frames: [[0, 0], [0, 1], [-3, -2], [4, 3], [-4, 2]],
        drift: { x: 1, y: 1, rate: 1, phase: 0.15 },
        skew: [0, 1, -3, 5, -2] },
      { name: 'jaw', grid: DRAGON_JAW, ox: 9, oy: 26,
        frames: [[0, 0], [0, 1], [-3, -1], [4, 6], [-4, 3]],
        drift: { x: 0, y: 1, rate: 1.5, phase: 0.5 },
        alt: { 3: DRAGON_JAW_OPEN } },
    ],
  },
  knight: {
    name: 'Knight', wide: false, colour: '#d8d8e0', accent: '#8e1d28', anim: 'heavy',
    body: { half: KNIGHT_BODY, oy: 4, drift: { x: 0, y: 1, rate: 1, phase: 0 } }, wear: 0.06,
    motion: { bob: 1, sway: 0, phase: 0.90, period: 3000, telegraph: 760 },
    stage: { scale: 2, sink: 9, bias: -9 },
    core: [32, 29],                                   // the reactor under the breastplate
    faults: [[24, 23, 14], [40, 23, 14], [32, 44, 12]],
    shed: 'shield',                                // shorn: the rubric-shield is struck out of its hand
    parts: [
      { name: 'shield', grid: KNIGHT_SHIELD, ox: 1, oy: 29,
        frames: [[0, 0], [0, 1], [-1, -2], [2, 2], [-3, -4]],
        drift: { x: 1, y: 1, rate: 0.5, phase: 0.20 } },
      { name: 'sword', grid: KNIGHT_SWORD, ox: 55, oy: 25,
        frames: [[0, 0], [0, 1], [1, -12], [-3, 6], [4, 3]],
        drift: { x: 1, y: 2, rate: 0.75, phase: 0.60 },
        alt: { 2: KNIGHT_SWORD_LIT, 3: KNIGHT_SWORD_LIT } },
    ],
  },
  titan: {
    name: 'Titan', wide: false, colour: '#e8a33d', accent: '#f0d79a', anim: 'heavy',
    body: { half: TITAN_BODY, oy: 6, drift: { x: 0, y: 1, rate: 1, phase: 0.5 } }, wear: 0.07,
    motion: { bob: 2, sway: 0, phase: 0.00, period: 2800, telegraph: 820 },
    stage: { scale: 2, sink: 10, bias: -9 },
    core: null,
    faults: [[22, 28, 14], [43, 28, 14]],
    shed: 'keys',                                // shorn: the ring of keys snaps off the belt
    parts: [
      { name: 'keys', grid: TITAN_CHAIN, ox: 46, oy: 27,
        frames: [[0, 0], [1, 1], [-2, -1], [3, 3], [-3, 2]],
        drift: { x: 3, y: 2, rate: 1.5, phase: 0 },
        skew: [0, 2, -3, 4, -2] },
    ],
  },
  colossus: {
    name: 'Colossus', wide: false, colour: '#3f7f9c', accent: '#a8c8d8', anim: 'heavy',
    body: { half: COLOSSUS_BODY, oy: 13, drift: { x: 0, y: 1, rate: 1, phase: 0.1 } }, wear: 0.09,
    motion: { bob: 2, sway: 1, phase: 0.62, period: 2200, telegraph: 700 },
    stage: { scale: 2, sink: 10, bias: -9 },
    core: null,
    faults: [[20, 30, 14], [45, 32, 12]],
    shed: 'maul',                                // shorn: it drops the maul
    parts: [
      { name: 'maul', grid: COLOSSUS_MAUL, ox: 1, oy: 44,
        frames: [[0, 0], [0, 1], [2, -18], [6, 4], [-4, 2]],
        drift: { x: 2, y: 2, rate: 0.5, phase: 0.25 } },
    ],
  },
  /* The hydra uses its wide box for three separated heads, a low ribbed
   * thorax and two planted haunches. The growing fourth neck has its own gap.
   * Source dimensions and stage foot anchor remain the shared wide contract. */
  hydra: {
    name: 'Hydra', wide: true, colour: '#4fb783', accent: '#d8e87a', anim: 'coil',
    body: { grid: HYDRA_BODY, ox: 14, oy: 35, drift: { x: 0, y: 1, rate: 1, phase: 0.4 } }, wear: 0.04,
    motion: { bob: 2, sway: 2, phase: 0.20, period: 1700, telegraph: 480 },
    stage: { scale: 2, sink: 3, bias: -20 },
    core: [48, 46],
    faults: [[27, 45, 12], [67, 45, 12]],
    /* The only creature here that GAINS mass where everything else loses it —
     * so `shorn` is where the head comes out rather than where a limb comes
     * off; see partsFor. Everything else in
     * the roster loses a limb; this one's taunt is "for every duplicate you
     * fail to skip, I grow another head", and a boss whose art contradicts its
     * own opening line is worse than one with no art at all. */
    grow: [
      { name: 'neckNew', grid: HYDRA_NECK, ox: 18, oy: 13, behind: true,
        frames: [[0, 0], [-1, 2], [3, -2], [6, 3], [4, 1]],
        drift: { x: 2, y: 2, rate: 1.5, phase: 0.85 },
        skew: [1, 2, 2, 3, 1], alt: { 3: HYDRA_NECK_BITE } },
    ],
    parts: [
      // Three heads on three rates and three phases. Synchronise them and the
      // creature stops being a hydra and becomes a hat rack.
      { name: 'neckL', grid: HYDRA_NECK, ox: 5, oy: 17, behind: true,
        frames: [[0, 0], [1, 1], [-2, -2], [-4, 3], [-3, 2]],
        drift: { x: 2, y: 2, rate: 0.75, phase: 0 },
        skew: [-1, -2, -2, -3, -1], alt: { 3: HYDRA_NECK_BITE } },
      { name: 'neckC', grid: HYDRA_NECK, ox: 34, oy: 10,
        frames: [[0, 0], [-1, 1], [1, -3], [2, 4], [0, 2]],
        drift: { x: 1, y: 2, rate: 1, phase: 0.33 },
        skew: [0, 1, -2, 3, -1], alt: { 3: HYDRA_NECK_BITE } },
      { name: 'neckR', grid: HYDRA_NECK, ox: 61, oy: 17, flip: true, behind: true,
        frames: [[0, 0], [-1, 2], [2, -2], [5, 3], [3, 1]],
        drift: { x: 2, y: 2, rate: 1.25, phase: 0.66 },
        skew: [1, 2, 2, 3, 1], alt: { 3: HYDRA_NECK_BITE } },
    ],
  },
  wraith: {
    name: 'Wraith', wide: false, colour: '#7f6ad6', accent: '#d8d0ff', anim: 'float',
    body: { half: WRAITH_BODY, oy: 8, drift: { x: 1, y: 1, rate: 1, phase: 0.3 } }, wear: 0.03,
    motion: { bob: 4, sway: 3, phase: 0.40, period: 2300, telegraph: 560 },
    stage: { scale: 2, sink: 12, bias: -9 },
    core: null,
    faults: [[16, 30, 10], [46, 30, 10]],
    shed: 'ragR',                                // shorn: half the shroud is torn away
    parts: [
      { name: 'ragL', grid: WRAITH_TAIL, ox: 12, oy: 50, behind: true,
        frames: [[0, 0], [1, 1], [-2, -1], [3, 2], [-2, 1]],
        drift: { x: 2, y: 2, rate: 0.5, phase: 0 } },
      { name: 'ragR', grid: WRAITH_TAIL, ox: 36, oy: 52, behind: true, flip: true,
        frames: [[0, 0], [-1, 2], [2, -1], [-3, 1], [2, 2]],
        drift: { x: 2, y: 2, rate: 0.75, phase: 0.4 } },
    ],
  },
  behemoth: {
    name: 'Behemoth', wide: false, colour: '#c4553f', accent: '#f0a86a', anim: 'heavy',
    body: { grid: BEHEMOTH_BODY, ox: 0, oy: 14, drift: { x: 0, y: 1, rate: 1, phase: 0.15 } }, wear: 0.08,
    motion: { bob: 2, sway: 1, phase: 0.60, period: 2000, telegraph: 600 },
    stage: { scale: 2, sink: 10, bias: -9 },
    core: [32, 30],
    faults: [[14, 24, 14], [50, 24, 14]],
    shed: 'tail',                                // shorn: the tail is severed
    parts: [
      { name: 'tail', grid: BEHEMOTH_TAIL, ox: 0, oy: 34, behind: true,
        frames: [[0, 0], [1, 1], [-2, -2], [3, 2], [-3, 3]],
        drift: { x: 3, y: 2, rate: 0.75, phase: 0.2 },
        skew: [0, 2, -3, 5, -3] },
    ],
  },
  golem: {
    name: 'Golem', wide: false, colour: '#8a8f9c', accent: '#5a9ec4', anim: 'heavy',
    body: { half: GOLEM_BODY, oy: 14, drift: { x: 0, y: 1, rate: 1, phase: 0.5 } }, wear: 0.14,
    motion: { bob: 1, sway: 0, phase: 0.10, period: 3200, telegraph: 980 },
    stage: { scale: 2, sink: 9, bias: -9 },
    core: null,
    faults: [[14, 32, 14], [48, 32, 14]],
    shed: 'runeB',                                // shorn: the second rune goes dark
    parts: [
      { name: 'runeA', grid: GOLEM_RUNE, ox: 5, oy: 21,
        frames: [[0, 0], [0, 2], [2, -4], [-4, 6], [1, 3]],
        drift: { x: 3, y: 3, rate: 1.25, phase: 0 } },
      { name: 'runeB', grid: GOLEM_RUNE, ox: 53, oy: 35,
        frames: [[0, 0], [0, -2], [-2, -5], [5, 4], [2, 2]],
        drift: { x: 3, y: 3, rate: 1.5, phase: 0.5 } },
    ],
  },
  ent: {
    name: 'Ent', wide: false, colour: '#6b8f3f', accent: '#9fd05a', anim: 'root',
    body: { half: ENT_BODY, oy: 8, drift: { x: 1, y: 0, rate: 1, phase: 0.25 } }, wear: 0.10,
    motion: { bob: 1, sway: 2, phase: 0.70, period: 3400, telegraph: 880 },
    stage: { scale: 2, sink: 9, bias: -9 },
    core: [32, 36],
    faults: [[22, 44, 14], [42, 44, 14]],
    shed: 'branch',                                // shorn: a limb comes off — the literal kind
    parts: [
      { name: 'branch', grid: ENT_BRANCH, ox: 4, oy: 34,
        frames: [[0, 0], [1, 1], [-2, -2], [4, 3], [-3, 1]],
        drift: { x: 2, y: 2, rate: 0.5, phase: 0.15 },
        skew: [0, 2, -4, 6, -3] },
    ],
  },
  necromancer: {
    name: 'Necromancer', wide: false, colour: '#6a4f8f', accent: '#b0e0c0', anim: 'float',
    body: { half: NECRO_BODY, oy: 14, drift: { x: 0, y: 1, rate: 1, phase: 0.2 } }, wear: 0.04,
    motion: { bob: 2, sway: 1, phase: 0.50, period: 2500, telegraph: 700 },
    stage: { scale: 2, sink: 10, bias: -9 },
    core: null,
    faults: [[10, 25, 8], [50, 25, 8]],
    shed: 'skullB',                                // shorn: one of the bound skulls breaks up
    parts: [
      { name: 'skullA', grid: NECRO_SKULL, ox: 48, oy: 24,
        frames: [[0, 0], [1, 2], [3, -3], [-7, 4], [2, 3]],
        drift: { x: 3, y: 3, rate: 1.25, phase: 0.1 } },
      { name: 'skullB', grid: NECRO_SKULL, ox: 8, oy: 32,
        frames: [[0, 0], [-1, -2], [-3, -2], [6, 5], [-2, 2]],
        drift: { x: 3, y: 3, rate: 1.5, phase: 0.6 } },
    ],
  },
  automaton: {
    name: 'Automaton', wide: false, colour: '#b0763f', accent: '#7fe6ff', anim: 'tick',
    body: { half: AUTOMATON_BODY, oy: 11, drift: { x: 0, y: 1, rate: 0.5, phase: 0.25 } }, wear: 0.11,
    motion: { bob: 1, sway: 0, phase: 0.80, period: 1800, telegraph: 400 },
    stage: { scale: 2, sink: 9, bias: -9 },
    core: [32, 30],
    faults: [[16, 32, 14], [48, 32, 14]],
    shed: 'piston',                                // shorn: the piston blows out of its housing
    parts: [
      // The gear indexes a quarter turn on every beat, so it keeps turning
      // while the rest of the machine is standing still. That is the whole
      // difference between a machine and a robot suit.
      { name: 'gear', grid: AUTOMATON_GEAR, ox: 26, oy: 35,
        frames: [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
        drift: { x: 1, y: 1, rate: 0.5, phase: 0.6 },
        altBeat: AUTOMATON_GEAR_TURNED,
        alt: { 1: AUTOMATON_GEAR_TURNED, 3: AUTOMATON_GEAR_TURNED } },
      { name: 'piston', grid: AUTOMATON_PISTON, ox: 4, oy: 29,
        frames: [[0, 0], [0, 1], [-2, 0], [6, 2], [-3, 1]],
        drift: { x: 0, y: 3, rate: 0.75, phase: 0.1 } },
    ],
  },
  demon: {
    name: 'Demon', wide: false, colour: '#c43f4f', accent: '#ff9d4a', anim: 'flap',
    body: { grid: DEMON_BODY, ox: 0, oy: 11, drift: { x: 0, y: 1, rate: 1, phase: 0.35 } }, wear: 0.05,
    motion: { bob: 2, sway: 1, phase: 0.15, period: 1500, telegraph: 320 },
    stage: { scale: 2, sink: 10, bias: -9 },
    core: [32, 33],
    faults: [[18, 40, 12], [46, 40, 12]],
    shed: 'wingR',                                // shorn: the right wing is taken off
    parts: [
      // The two wings run at the same rate half a turn apart, so the downbeat
      // of one is the upbeat of the other and the thing never looks pinned.
      { name: 'wingL', grid: DEMON_WING, ox: -6, oy: 7, behind: true,
        frames: [[0, 0], [1, 3], [-2, -3], [2, 5], [1, 2]],
        drift: { x: 3, y: 2, rate: 0.5, phase: 0 },
        skew: [0, 2, -3, 4, 0] },
      { name: 'wingR', grid: DEMON_WING, ox: 43, oy: 7, behind: true, flip: true,
        frames: [[0, 0], [-1, 3], [2, -3], [-2, 5], [-1, 2]],
        drift: { x: 3, y: 2, rate: 0.5, phase: 0.5 },
        skew: [0, -2, 3, -4, 0] },
      { name: 'flail', grid: DEMON_FLAIL, ox: 52, oy: 33,
        frames: [[0, 0], [1, 1], [4, -6], [-8, 8], [3, 3]],
        drift: { x: 4, y: 3, rate: 1.5, phase: 0.25 },
        skew: [0, 1, 4, -5, 2] },
    ],
  },
  wyrm: {
    name: 'Wyrm', wide: true, colour: '#3f6f9c', accent: '#7fe6ff', anim: 'coil',
    body: { grid: WYRM_COIL, ox: 54, oy: 47 }, wear: 0.04,
    motion: { bob: 2, sway: 3, phase: 0.35, period: 1900, telegraph: 540 },
    stage: { scale: 2, sink: 3, bias: -6 },   // -6, not -2: see THE 96-BOX at every stage, below
    core: [62, 44],
    faults: [[50, 38, 12], [64, 52, 12]],
    shed: 'fin',                                // shorn: the dorsal fin shears away
    parts: [
      // The coils run slow and a third of a turn apart, so the animal swims
      // along its own length instead of pulsing like a ring.
      { name: 'coilMid', grid: WYRM_COIL, ox: 45, oy: 33, behind: true,
        frames: [[0, 0], [1, 0], [-2, -1], [3, 1], [-3, 1]],
        drift: { x: 2, y: 1, rate: 0.5, phase: 0 },
        skew: [0, 2, -3, 4, -2] },
      { name: 'coilTop', grid: WYRM_COIL, ox: 34, oy: 21, behind: true,
        frames: [[0, 0], [2, 0], [-3, -1], [5, 1], [-4, 1]],
        drift: { x: 2, y: 1, rate: 0.5, phase: 0.33 },
        skew: [0, 3, -4, 6, -3] },
      { name: 'neck', grid: WYRM_NECK, ox: 24, oy: 19,
        frames: [[0, 0], [1, 1], [-3, -2], [5, 2], [-4, 2]],
        drift: { x: 2, y: 2, rate: 0.75, phase: 0.5 },
        skew: [0, 2, -4, 6, -3] },
      { name: 'fin', grid: WYRM_FIN, ox: 40, oy: 17, behind: true,
        frames: [[0, 0], [1, 1], [-2, -2], [4, 2], [-3, 1]],
        drift: { x: 1, y: 1, rate: 1.25, phase: 0 } },
      { name: 'head', grid: WYRM_HEAD, ox: 4, oy: 13,
        frames: [[0, 0], [1, 1], [-4, -2], [6, 3], [-5, 3]],
        drift: { x: 2, y: 2, rate: 1, phase: 0.15 },
        skew: [0, 1, -3, 4, -2] },
      { name: 'jaw', grid: WYRM_JAW, ox: 4, oy: 25,
        frames: [[0, 0], [1, 1], [-4, -1], [6, 7], [-5, 4]],
        drift: { x: 1, y: 2, rate: 1.5, phase: 0.4 },
        alt: { 3: WYRM_JAW_OPEN } },
    ],
  },
  interpreter: {
    name: 'The Last Interpreter', wide: true, colour: '#3f7f5a',
    accent: '#e8c37d', anim: 'coil',
    body: { grid: INTERP_COIL, ox: 58, oy: 46 }, wear: 0.03,
    // Slow. Nothing about this creature is in a hurry and the telegraph is the
    // longest in the file on purpose: it gives you time, which is the one thing
    // the room it stands in does not.
    motion: { bob: 2, sway: 2, phase: 0.2, period: 2400, telegraph: 720 },
    stage: { scale: 2, sink: 3, bias: -24 },  // -24, not -20: see THE 96-BOX at every stage, below
    core: [66, 43],
    faults: [[54, 37, 12], [68, 51, 12]],
    shed: 'hat',                                // shorn: the hat comes off. It does not pick it up.
    parts: [
      { name: 'staff', grid: INTERP_STAFF, ox: 84, oy: 8, behind: true,
        frames: [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
        drift: { x: 0, y: 0, rate: 0, phase: 0 } },
      { name: 'coilMid', grid: INTERP_COIL, ox: 48, oy: 32, behind: true,
        frames: [[0, 0], [1, 0], [-2, -1], [3, 1], [-3, 1]],
        drift: { x: 2, y: 1, rate: 0.4, phase: 0 },
        skew: [0, 2, -3, 4, -2] },
      { name: 'coilTop', grid: INTERP_COIL, ox: 36, oy: 19, behind: true,
        frames: [[0, 0], [2, 0], [-3, -1], [5, 1], [-4, 1]],
        drift: { x: 2, y: 1, rate: 0.4, phase: 0.33 },
        skew: [0, 3, -4, 6, -3] },
      { name: 'neck', grid: INTERP_NECK, ox: 27, oy: 22,
        frames: [[0, 0], [1, 1], [-3, -2], [4, 2], [-3, 2]],
        drift: { x: 2, y: 2, rate: 0.6, phase: 0.5 },
        skew: [0, 2, -3, 4, -2] },
      { name: 'head', grid: INTERP_HEAD, ox: 6, oy: 16,
        frames: [[0, 0], [1, 1], [-3, -2], [5, 2], [-4, 3]],
        drift: { x: 2, y: 2, rate: 0.8, phase: 0.15 },
        skew: [0, 1, -2, 3, -2] },
      { name: 'jaw', grid: INTERP_JAW, ox: 8, oy: 28,
        frames: [[0, 0], [1, 1], [-3, -1], [5, 6], [-4, 4]],
        drift: { x: 1, y: 2, rate: 1.2, phase: 0.4 },
        alt: { 3: INTERP_JAW_OPEN } },
      { name: 'hat', grid: INTERP_HAT, ox: 2, oy: 2,
        frames: [[0, 0], [1, 1], [-3, -3], [5, 1], [-4, 4]],
        drift: { x: 2, y: 1, rate: 0.8, phase: 0.15 },
        skew: [0, 1, -2, 3, -2] },
    ],
  },
  interviewer: {
    name: 'The Interviewer', wide: false, tall: true,
    colour: '#d8d8e0', accent: '#8f7ad8', anim: 'still',
    body: { half: NULL_BODY, oy: 0, drift: { x: 0, y: 1, rate: 0.5, phase: 0 } }, wear: 0.01,
    /* The slowest clock and the longest telegraph in the file. It is not being
     * generous: it is giving you time to answer, which is the thing the room
     * this stands in is for. */
    motion: { bob: 1, sway: 1, phase: 0.75, period: 3600, telegraph: 940 },
    /* Scale 1 and sink 0, and both are the whole argument of THE FINAL RUNG
     * above: one authored cell per stage pixel, and not one row of it under the
     * floor. bias 0 because 96 centred on enemyX 184 is already 23 columns
     * clear of the frame at both ends — the only boss in the roster that needs
     * no correction at all. */
    stage: { scale: 1, sink: 0, bias: 0 },
    core: [48, 72],                                   // the hole in the null sigil
    /* FIVE fault anchors, not three, and the count is a measurement rather than
     * a taste. spall() takes five contour bites per fault at the chipped stage,
     * each two rows deep and two to four pixels wide; on a 64-box rig that is
     * plenty, and on this one — three and a half times the painted mass —
     * fifteen bites moved FIVE cells of the 24x24 normalised silhouette
     * bossforms.mjs scores, the weakest first turn in the roster. Two more
     * anchors on the pauldron and cape edges, where the contour is longest,
     * take the same stage to a number that reads. */
    faults: [[20, 62, 30], [76, 62, 30], [34, 104, 22], [10, 46, 20], [86, 46, 20]],
    shed: 'crown',                               // shorn: the crown comes off the head
    grow: [
      { name: 'nullcrown', grid: NULL_NEWCROWN, ox: 33, oy: 0,
        frames: [[0, 0], [0, 1], [0, -2], [0, 2], [0, 1]],
        drift: { x: 1, y: 1, rate: 0.5, phase: 0.2 } },
    ],
    parts: [
      { name: 'cape', grid: NULL_CAPE, ox: 0, oy: 0, behind: true,
        frames: [[0, 0], [0, 1], [-1, -1], [1, 2], [-1, 1]],
        drift: { x: 1, y: 1, rate: 0.4, phase: 0.1 } },
      { name: 'crown', grid: NULL_CROWN, ox: 31, oy: 0,
        frames: [[0, 0], [0, 1], [0, -2], [0, 3], [0, 2]],
        drift: { x: 0, y: 1, rate: 0.75, phase: 0.35 } },
      { name: 'rubric', grid: NULL_RUBRIC, ox: 0, oy: 66,
        frames: [[0, 0], [0, 1], [-2, -3], [3, 4], [-3, 2]],
        drift: { x: 2, y: 2, rate: 1.5, phase: 0 },
        alt: { 2: NULL_RUBRIC_LIT, 3: NULL_RUBRIC_LIT } },
      { name: 'pen', grid: NULL_PEN, ox: 88, oy: 16,
        frames: [[0, 0], [0, 1], [-1, -6], [-4, 9], [2, 3]],
        drift: { x: 1, y: 2, rate: 1, phase: 0.5 },
        skew: [0, 0, -2, 3, -1],
        alt: { 2: NULL_PEN_LIT, 3: NULL_PEN_LIT } },
    ],
  },
};

/* ---------------- key resolution ----------------
 * world.py names a sprite per boss. Two notes on the mapping:
 *   - "interviewer" used to resolve to the knight, on the argument that the
 *     final boss of a game about interviews is a faceless thing in mirror
 *     armour holding a rubric and that the knight already was one. It still is
 *     one; it is simply no longer the LAST one. The Interviewer has its own
 *     96x128 rig now (THE FINAL RUNG, above) and the knight keeps the 64-box
 *     body, which is still reachable — it is what an unknown castle key hashes
 *     onto, and it is the region's ordinary armoured thing.
 *   - two entries in world.BOSSES share the key "titan", and two identical
 *     silhouettes in one playthrough is a defect the player can see. BOSS_ART_FOR_ID
 *     sends the Rolling Titan to the colossus instead. Art-only override; nothing
 *     about the fight changes.
 */
export const BOSS_ARCHETYPES = Object.freeze(Object.keys(ART));

export const BOSS_SHAPE_FOR = Object.freeze({
  titan: 'titan', hydra: 'hydra', wraith: 'wraith', behemoth: 'behemoth',
  golem: 'golem', dragon: 'dragon', ent: 'ent', necromancer: 'necromancer',
  automaton: 'automaton', lich: 'lich', demon: 'demon', wyrm: 'wyrm',
  interviewer: 'interviewer', knight: 'knight', colossus: 'colossus',
  // world.FINAL_TRIAL. Not a boss and not in world.BOSSES — the practical is
  // measured rather than fought — but it has a face now and the face has to
  // resolve from the same table as everything else with one.
  interpreter: 'interpreter', the_last_interpreter: 'interpreter',
  python_wizard: 'interpreter', serpent: 'interpreter',
});

export const BOSS_ART_FOR_ID = Object.freeze({
  /* ---- world.BOSSES, by id ----
   * Every row's `sprite` already resolves through BOSS_SHAPE_FOR, so for a
   * caller that passes the sprite key these are redundant. For a caller that
   * passes the ID they are not, and until now they were missing: resolveBoss()
   * fell through to the hash and 'three_sum_hydra' came back as a wyrm. That is
   * the worst failure mode in this file — not a throw, not a blank sprite, but
   * a confidently drawn wrong animal — and it went unnoticed because the one
   * harness that checked ids went through bossArtKey(), which reads .sprite.
   * Two bosses share the titan sprite, so rolling_titan is listed with the
   * others rather than apart from them: the id is what separates them. */
  hash_titan: 'titan',            three_sum_hydra: 'hydra',
  window_wraith: 'wraith',        twin_behemoth: 'behemoth',
  matrix_golem: 'golem',          tree_dragon: 'dragon',
  path_sum_ent: 'ent',            graph_necromancer: 'necromancer',
  rolling_titan: 'colossus',      editor_automaton: 'automaton',
  complexity_wyrm: 'wyrm',        serialization_lich: 'lich',
  bug_demon: 'demon',             the_interviewer: 'interviewer',

  /* ---- gauntlet/hunters.py, the seventeen roaming apexes ----
   * Transcribed from hunters.APEXES: each row's `sprite` is a key its author
   * marked as NOT YET AUTHORED, and its `sprite_fallback` is the archetype in
   * this file they meant it to borrow until it is. Honouring that is the whole
   * point of the field — resolving these by hash instead would give every apex
   * a silhouette its own designer did not choose.
   *
   * Six archetypes carry two apexes each (or an apex and a boss). They are not
   * twins: an apex also carries its region's ELEMENT, which rotates the rim,
   * the glow and the embers, so the Rimewarden comes off a cold pass in cold
   * light and the Unnamed comes out of the castle in void light on the same
   * body. See BOSS_ELEMENT directly below.
   *
   * They get everything a boss gets: both forms, three phases, the shed limb,
   * the entrance. An apex that hunts you across a region and then turns out to
   * be a recoloured mob is a worse encounter than no apex at all. */
  margin_walker: 'wraith',       thresher: 'automaton',
  storm_ordinal: 'titan',        sporecrown: 'ent',
  zeroth_weight: 'golem',        fenlight: 'hydra',
  rimewarden: 'colossus',        cinder_phoenix: 'dragon',
  fourth_orientation: 'knight',  unreturning: 'lich',
  bough_stalker: 'wyrm',         lattice_stag: 'behemoth',
  relighter: 'necromancer',      slagmother: 'demon',
  the_doubling: 'automaton',     sand_champion: 'titan',
  the_unnamed: 'colossus',
});

/* ---------------- element per creature ----------------
 * TRANSCRIBED, not invented. Each row is
 *     world.BOSSES[i].region -> world.REGION_BY_ID[...].biome
 *                            -> elements.BIOME_AFFINITY[biome]
 * with the region's PRIMARY affinity taken, which is the first entry of
 * elements.REGION_AFFINITIES. Two of them come out NEUTRAL because the canopy
 * is neutral; that is the world's answer and it is left alone rather than
 * dressed up. The Interpreter stands in world.FINAL_TRIAL, under the castle,
 * which is VOID.
 *
 * Keyed by ART key rather than boss id because that is all a caller has: fx.js
 * passes enemy.sprite and nothing else. Where two bosses share an archetype the
 * colour still separates them, and their regions agree anyway.
 */
export const BOSS_ELEMENT = Object.freeze({
  titan: 'LIGHTNING',       // hashmap_highlands / highland
  hydra: 'BRUTE',           // array_caverns / cave
  wraith: 'POISON',         // sliding_window_marsh / swamp
  behemoth: 'COLD',         // twin_pointer_pass / mountain
  golem: 'BRUTE',           // matrix_citadel / citadel
  dragon: 'NEUTRAL',        // binary_tree_canopy / canopy
  ent: 'NEUTRAL',           // binary_tree_canopy / canopy
  necromancer: 'LIGHTNING', // graph_wastes / wastes
  colossus: 'POISON',       // rolling_titan, sliding_window_marsh / swamp
  automaton: 'BRUTE',       // matrix_citadel / citadel
  wyrm: 'COLD',             // complexity_tower / tower
  lich: 'VOID',             // recursive_forest / deepforest
  demon: 'FIRE',            // debugging_dungeon / dungeon
  knight: 'VOID',           // null_kings_castle / castle
  interviewer: 'VOID',      // the_interviewer, null_kings_castle / castle
  interpreter: 'VOID',      // FINAL_TRIAL, under null_kings_castle

  /* The same fourteen again, by ID. The archetype rows above answer a caller
   * holding enemy.sprite; these answer one holding the world.py row's id, and
   * they are not the same answer wherever two bosses share a sprite. The
   * Rolling Titan stands in the marsh and is POISON; the Hash Titan stands in
   * the highlands and is LIGHTNING. Both are 'titan'. Keying only by archetype
   * gave them one element and quietly made the marsh boss a highland one. */
  hash_titan: 'LIGHTNING',       three_sum_hydra: 'BRUTE',
  window_wraith: 'POISON',       twin_behemoth: 'COLD',
  matrix_golem: 'BRUTE',         tree_dragon: 'NEUTRAL',
  path_sum_ent: 'NEUTRAL',       graph_necromancer: 'LIGHTNING',
  rolling_titan: 'POISON',       editor_automaton: 'BRUTE',
  complexity_wyrm: 'COLD',       serialization_lich: 'VOID',
  bug_demon: 'FIRE',             the_interviewer: 'VOID',
  the_last_interpreter: 'VOID',

  /* The apexes, by id, from hunters.APEXES[].element. Keyed by ID rather than
   * by archetype on purpose: six archetypes carry two of these, and the
   * element is the thing that keeps them apart. The Doubling is a cold
   * automaton in the tower and the Thresher is a neutral one in the fields;
   * same body, two different animals coming at you. */
  margin_walker: 'NEUTRAL',      thresher: 'NEUTRAL',
  storm_ordinal: 'LIGHTNING',    sporecrown: 'POISON',
  zeroth_weight: 'BRUTE',        fenlight: 'POISON',
  rimewarden: 'COLD',            cinder_phoenix: 'FIRE',
  fourth_orientation: 'BRUTE',   unreturning: 'VOID',
  bough_stalker: 'NEUTRAL',      lattice_stag: 'LIGHTNING',
  relighter: 'NEUTRAL',          slagmother: 'FIRE',
  the_doubling: 'COLD',          sand_champion: 'NEUTRAL',
  the_unnamed: 'VOID',
});

/* The element a given key fights as. The RAW key is tried first so an apex
 * keeps its own region's light instead of inheriting the element of whichever
 * archetype it borrows a body from. NEUTRAL and anything unknown return null,
 * which is the signal to light the creature exactly as authored. */
export function bossElement(key) {
  const raw = String(key || '');
  const e = BOSS_ELEMENT[raw] || BOSS_ELEMENT[resolveBoss(raw)];
  return e && e !== 'NEUTRAL' ? e : null;
}

/* What element to light a given call with. A caller may override — the forge
 * preview wants to see a creature in another element's light — and passing
 * anything unknown, or 'NEUTRAL', means "as authored". */
function elementFor(rawKey, opts) {
  if (opts && opts.element !== undefined && opts.element !== null) {
    const e = String(opts.element).toUpperCase();
    return ELEMENT_LIGHT[e] ? e : null;
  }
  return bossElement(rawKey);
}

/* ================================================================
 * THE THEME LAYER — web/js/bossart.js, wired
 * ================================================================
 * This file is the STAGING: boxes, frames, beats, phases, caches, the draw
 * call, the entrance. bossart.js is the THEME: what a fire boss is made of and
 * what a void boss does to the light. They were authored in parallel against an
 * agreed interface and then never connected to each other, which is the one
 * failure two parallel passes reliably produce — both halves complete, both
 * halves passing their own harness, and no import between them. Everything
 * below is that import.
 *
 * What the theme actually buys, and why it was worth wiring rather than
 * declaring done:
 *
 *   THE ELEMENT BECOMES GEOMETRY. Until now the element was ELEMENT_LIGHT, and
 *     ELEMENT_LIGHT is a recolour: it rotates the rim, the glow and the embers
 *     and touches not one pixel of coverage. Measured, a FIRE titan and a COLD
 *     titan differed in 245 pixels and in ZERO silhouette cells — the same
 *     shape in two colours, which is the one thing the brief names as a
 *     failure. bossart.dressGrid() makes each element a different verb done to
 *     the contour: fire SHEDS upward, cold ACCRETES 45-degree spurs away from
 *     the key light, poison SAGS into pendant drops, brute CHIPS mass out,
 *     lightning SPANS a filament between two points of the contour, void
 *     SUBTRACTS — holes inward and the outline itself missing along the lower
 *     left, exactly where every other creature in this game is brightest.
 *     NEUTRAL is not an element and gets no treatment; five regions are neutral
 *     on purpose and they are the control group.
 *
 *   THE APEXES STOP BEING CLONES. Three pairs of the seventeen shared an
 *     archetype and, with the element carrying no geometry, were byte-identical
 *     in silhouette: the Thresher and the Doubling, the Storm Ordinal and the
 *     Sand Champion, the Rimewarden and the Unnamed. They are separated now by
 *     the element verb rather than by hue.
 *
 * What is deliberately NOT wired is bossart.motifsFor(). Its stamps — the Hash
 * Titan's keyring, the Wraith's empty frame, the Ent's single arm — are the
 * right idea and this file already has them, authored as real parts that shed
 * on a phase change (ART.titan's 'keys', ART.wraith's 'ragR', ART.ent's
 * 'branch'). Stamping the motif on top would give the Hash Titan two keyrings.
 * The vocabulary is taken; the duplicate identity is not.
 */

/* gauntlet/hunters.py APEXES — id, name and region, which is all
 * bossart.ingestHunters() reads. bossart.js was written before hunters.py
 * existed and stands up seventeen placeholder ids of its own ('apex_unnamed',
 * 'apex_half_formed', ...) against the right seventeen REGIONS; handing it
 * these rows re-keys that authored art onto the ids the server actually uses.
 * Without this call every apex resolved to bossart's unknown fallback and the
 * theme layer had nothing to say about any of them.
 *
 * The regions are the load-bearing column and they are transcribed, not
 * invented: each apex's element comes out of elements.region_affinities() for
 * the region named here, which is why this table carries no element of its own
 * to disagree with BOSS_ELEMENT above. */
const APEX_ROSTER = Object.freeze([
  { id: 'margin_walker',      name: 'The Margin-Walker',    region: 'python_village' },
  { id: 'thresher',           name: 'The Thresher',         region: 'fields_of_syntax' },
  { id: 'storm_ordinal',      name: 'The Storm Ordinal',    region: 'hashmap_highlands' },
  { id: 'sporecrown',         name: 'The Sporecrown',       region: 'stringwood_labyrinth' },
  { id: 'zeroth_weight',      name: 'The Zeroth Weight',    region: 'array_caverns' },
  { id: 'fenlight',           name: 'The Fenlight',         region: 'sliding_window_marsh' },
  { id: 'rimewarden',         name: 'The Rimewarden',       region: 'twin_pointer_pass' },
  { id: 'cinder_phoenix',     name: 'The Cinder Phoenix',   region: 'stack_queue_mines' },
  { id: 'fourth_orientation', name: 'The Fourth Orientation', region: 'matrix_citadel' },
  { id: 'unreturning',        name: 'The Unreturning',      region: 'recursive_forest' },
  { id: 'bough_stalker',      name: 'The Bough Stalker',    region: 'binary_tree_canopy' },
  { id: 'lattice_stag',       name: 'The Lattice Stag',     region: 'graph_wastes' },
  { id: 'relighter',          name: 'The Relighter',        region: 'dp_ruins' },
  { id: 'slagmother',         name: 'The Slagmother',       region: 'debugging_dungeon' },
  { id: 'the_doubling',       name: 'The Doubling',         region: 'complexity_tower' },
  { id: 'sand_champion',      name: 'The Sand Champion',    region: 'coding_coliseum' },
  { id: 'the_unnamed',        name: 'The Unnamed',          region: 'null_kings_castle' },
]);

/* Taken once, at module load, before anything can resolve a look and cache the
 * fallback it would have got. Returns how many rows it took; a mismatch is a
 * roster drift between this file and bossart.js and bossArtSelfCheck reports
 * it, so it is recorded rather than asserted — a boss file that refuses to load
 * because an art roster moved is a worse failure than a plain-looking apex. */
const APEX_INGESTED = ingestHunters(APEX_ROSTER);

/* Which region a key stands in, for the one case where the sprite key alone is
 * ambiguous: 'titan' is both the Hash Titan in the highlands and the Rolling
 * Titan in the marsh, and bossart.bossLook() disambiguates on a region hint.
 * Frozen hint objects rather than an object literal per call — this is behind a
 * cache today and should not become an allocation if it ever stops being. */
const REGION_HINT = Object.freeze(Object.fromEntries(Object.entries({
  titan: 'hashmap_highlands',        hash_titan: 'hashmap_highlands',
  colossus: 'sliding_window_marsh',  rolling_titan: 'sliding_window_marsh',
  hydra: 'array_caverns',            three_sum_hydra: 'array_caverns',
  wraith: 'sliding_window_marsh',    window_wraith: 'sliding_window_marsh',
  behemoth: 'twin_pointer_pass',     twin_behemoth: 'twin_pointer_pass',
  golem: 'matrix_citadel',           matrix_golem: 'matrix_citadel',
  dragon: 'binary_tree_canopy',      tree_dragon: 'binary_tree_canopy',
  ent: 'binary_tree_canopy',         path_sum_ent: 'binary_tree_canopy',
  necromancer: 'graph_wastes',       graph_necromancer: 'graph_wastes',
  automaton: 'matrix_citadel',       editor_automaton: 'matrix_citadel',
  wyrm: 'complexity_tower',          complexity_wyrm: 'complexity_tower',
  lich: 'recursive_forest',          serialization_lich: 'recursive_forest',
  demon: 'debugging_dungeon',        bug_demon: 'debugging_dungeon',
  knight: 'null_kings_castle',       the_interviewer: 'null_kings_castle',
  interpreter: 'null_kings_castle',  the_last_interpreter: 'null_kings_castle',
}).map(([k, v]) => [k, Object.freeze({ region: v })])));

/* A look, plus the element the CALL is actually being lit as — which is not
 * always the look's own, because callers may override (the forge preview shows
 * a creature in another element's light, and a preview whose geometry disagreed
 * with its palette would be showing something that cannot exist).
 *
 * Both maps are bounded by the number of distinct keys anything ever asks for,
 * not by frames drawn: ~50 real keys x 7 elements worst case. They are cleared
 * rather than evicted at the cap because a theme lookup is cheap to rebuild and
 * an LRU here would be machinery guarding nothing. */
const lookCache = new Map();
const themeCache = new Map();
const LOOK_CAP = 256;

function lookOf(rawKey) {
  const k = String(rawKey || '');
  const hit = lookCache.get(k);
  if (hit !== undefined) return hit;
  const look = bossLook(k, REGION_HINT[k]);
  if (lookCache.size >= LOOK_CAP) lookCache.clear();
  lookCache.set(k, look);
  return look;
}

/* The look the geometry pass should run under. `element` has already been
 * through elementFor(), so it is either a real element id or null meaning
 * "as authored"; null resolves to the look's own, and a look whose element
 * already agrees is returned untouched rather than copied. */
function themeOf(rawKey, element) {
  const look = lookOf(rawKey);
  const el = element || look.element || 'NEUTRAL';
  if (look.element === el) return look;
  const ck = `${look.id}|${el}`;
  const hit = themeCache.get(ck);
  if (hit !== undefined) return hit;
  const out = Object.freeze(Object.assign({}, look, { element: el }));
  if (themeCache.size >= LOOK_CAP) themeCache.clear();
  themeCache.set(ck, out);
  return out;
}

/* The geometry half of the element, run at BATTLE scale in both forms.
 *
 * That is the decision the "same creature" claim rests on, and it is worth
 * stating plainly: the map form dresses before it reduces, not after. Dressing
 * a 48-pixel marker separately would draw a second, smaller set of spurs from a
 * different seed, and the two forms would carry different decoration at the one
 * scale the player compares them across. Dressing first and reducing after
 * means the marker's spurs are literally the battle form's spurs, box-sampled.
 * The promise the map silhouette makes is the one the fight keeps. */
function dress(grid, rawKey, element, frame, beat, phase) {
  if (!element) return grid;   // NEUTRAL and unknown: the control group, untouched
  return budgetGuard(grid, dressGrid(grid, themeOf(rawKey, element),
    { frame: frame | 0, beat: beat | 0, phase: phase | 0 }));
}

/* Glyphs the element is ALLOWED to introduce, because they cost nothing.
 *
 *   . o      transparent and the hard outline. Every sprite pays for both.
 *   r R f    the element's own mark ramp. bossart.elementPalette collapses all
 *            three onto three steps of ONE shared ramp, so an element's marks
 *            are three colours whether it paints one of them or all of them.
 *   u i      folded onto that same ramp's specular by the same pass — one more
 *            slot, already spent by whichever of r/R/f the verb also used.
 *   k        the void black, which this file defines as the same value as the
 *            outline. An eye socket, a visor slit and a hole punched by the
 *            void verb are one absence of light and one palette entry.
 *   U W      white. Every boss in this cast has a white already.
 */
const DRESS_FREE = new Set(['.', 'o', 'r', 'R', 'f', 'u', 'i', 'k', 'U', 'W']);
/* Where a disallowed glyph goes instead: a light one onto the mark ramp's hot
 * step, anything else onto its mid step. */
const DRESS_LIGHT = new Set(['A', 'C', 'H', 'L', 'T', 'G', 'Z', 'X', 'J', 'M']);

/* Keep the theme pass budget-neutral, which is a rule this file already states
 * and the theme pass quietly broke on exactly one element.
 *
 * Five of the six verbs write only into slots elementPalette has already
 * collapsed onto a single shared mark ramp, so they cost nothing: measured,
 * FIRE, COLD, BRUTE, LIGHTNING and VOID all add zero rendered colours. POISON
 * does not. Its pendant drops are authored as 'a' and 'A' — the CREATURE'S
 * accent, not the element's mark — and on a boss that never painted its accent
 * those are two brand-new colours. That is how the Rolling Titan and the
 * Sporecrown came out at sixteen: not a palette with sixteen entries, but
 * fourteen pixels of accent base and fourteen of accent light appearing on a
 * sprite that had been paying for neither.
 *
 * So: a cell the element CHANGED may only hold a glyph the creature was
 * already painting, or one of the free set above. Anything else folds onto the
 * mark ramp. Cells the element did not touch are left exactly as authored,
 * which is what keeps this a guard rather than a second art pass — the Rolling
 * Titan's own accent pixels are still its own accent.
 *
 * Runs once per cached sprite build, never on a draw path, and allocates one
 * row array per row it actually rewrites. A grid the guard has nothing to say
 * about is returned by reference. */
function budgetGuard(before, after) {
  if (!after || after.length !== before.length) return after;
  /* What the creature already pays for. Built off the pre-dress grid, so the
   * element cannot authorise its own new colour by being the thing that
   * introduced it. */
  let paid = null;
  let out = after;
  for (let y = 0; y < after.length; y++) {
    const a = after[y], b = before[y];
    if (a === b) continue;
    let row = null;
    for (let x = 0; x < a.length; x++) {
      const ch = a[x];
      if (ch === b[x] || DRESS_FREE.has(ch)) continue;
      if (paid === null) {
        paid = new Set();
        for (let i = 0; i < before.length; i++) {
          const r = before[i];
          for (let j = 0; j < r.length; j++) paid.add(r[j]);
        }
      }
      if (paid.has(ch)) continue;
      if (row === null) row = a.split('');
      row[x] = DRESS_LIGHT.has(ch) ? 'R' : 'r';
    }
    if (row !== null) {
      if (out === after) out = after.slice();
      out[y] = row.join('');
    }
  }
  return out;
}

/* An unknown key used to collapse to the titan. That was fine while the only
 * callers were the fourteen rows of world.BOSSES, and it stops being fine the
 * moment something else wants boss-grade art — gauntlet/hunters.py is being
 * written with seventeen roaming apex monsters in it, one per region, and
 * seventeen identical titans is a worse answer than seventeen wrong ones.
 *
 * So an unrecognised key is HASHED onto the roster instead: stable forever for
 * a given name, spread across the fifteen silhouettes, and still deterministic.
 * A nullish key keeps the old answer, because "no key" is a bug in the caller
 * and should look like the same bug every time. */
export function resolveBoss(spriteKeyOrId) {
  const k = String(spriteKeyOrId || '');
  if (!k) return 'titan';
  return BOSS_ART_FOR_ID[k] || BOSS_SHAPE_FOR[k] || (ART[k] ? k
    : BOSS_ARCHETYPES[hash(k) % BOSS_ARCHETYPES.length]);
}

/* Art for a world.BOSSES row: the id override wins, then the sprite key. */
export function bossArtKey(boss) {
  if (!boss) return 'titan';
  if (typeof boss === 'string') return resolveBoss(boss);
  return BOSS_ART_FOR_ID[boss.id] || resolveBoss(boss.sprite);
}

export function bossSize(key) {
  return boxOf(ART[resolveBoss(key)]);
}

/* ---------------- motion metadata ----------------
 * Everything the battle scene needs to drive the fight without reaching into
 * the art: how far it bobs, how long the telegraph runs, what to draw it at,
 * how wide its shadow is, and whether it touches the ground at all.
 */
export const BOSS_MOTION = Object.freeze(Object.fromEntries(
  BOSS_ARCHETYPES.map(k => {
    const art = ART[k];
    const floats = art.anim === 'float';
    return [k, Object.freeze({
      key: k,
      name: art.name,
      bob: art.motion.bob,
      sway: art.motion.sway,
      phase: art.motion.phase,
      period: art.motion.period,
      telegraph: art.motion.telegraph,
      anim: art.anim,
      wide: !!art.wide,
      /* The third rung, exposed for the same reason `wide` is: a caller sizing
       * a card, a codex cell or a preview needs to know which box it is getting
       * without calling bossSize() and without inferring it from the scale. */
      tall: !!art.tall,
      w: boxOf(art).w,
      h: boxOf(art).h,
      floats,
      /* What the battle stage should draw it at, and how far its feet go under
       * the floor. A 64-box boss at 2 stands 128 tall against a 96-tall hero
       * and fills the stage from well down the sky through the ground line —
       * which is the whole point, and is why `sink` exists: the feet are meant
       * to be under the floor, not standing on a shelf. 128 is also §B's
       * tallest rung, so the biggest thing in the game and the biggest box the
       * ladder allows are now the same height. */
      scale: (art.stage && art.stage.scale) || 1.5,
      sink: (art.stage && art.stage.sink) || 0,
      bias: (art.stage && art.stage.bias) || 0,
      parts: (art.parts || []).length,
      /* What it loses, and what it puts out, when the fight turns. Null for
       * neither. A driver that wants to punctuate a phase change — a camera
       * kick, a sound, a line — reads this rather than diffing two sprites. */
      sheds: art.shed || null,
      grows: (art.grow || []).map(p => p.name),
      phases: BOSS_PHASE_COUNT,
      /* The element it is lit by, from BOSS_ELEMENT. Null means NEUTRAL and
       * means the palette is left exactly as authored. */
      element: BOSS_ELEMENT[k] && BOSS_ELEMENT[k] !== 'NEUTRAL' ? BOSS_ELEMENT[k] : null,
      /* The marker. Same creature, 0.75 of the box, its own outline weight. */
      mapW: mapBoxOf(art).w,
      mapH: mapBoxOf(art).h,
      mapSink: Math.round(((art.stage && art.stage.sink) || 0) * mapRatioOf(art)),
      mapRatio: mapRatioOf(art),
      /* The ground shadow's half-width, in the units drawBoss multiplies by the
       * archetype's own scale: `shadow * scale * 0.5` is the ellipse's rx. A
       * 64-box boss at 2 gets 30 -> 60 device-logical pixels of shadow under a
       * 128-wide creature, so the shadow is 47% of the width it stands in. The
       * tall rung is drawn at 1 and is 96 wide, so 60 keeps that same fraction
       * rather than inheriting a number written for a different scale. */
      shadow: art.tall ? 60 : art.wide ? 44 : 30,
      colour: art.colour,
      accent: art.accent,
    })];
  }),
));

export function bossMotion(key) {
  return BOSS_MOTION[resolveBoss(key)] || BOSS_MOTION.titan;
}

/* The stage default, and the value fx.js passes. It is deliberately still 1.5:
 * a caller that asks for "the stage scale" gets a number that is safe for any
 * box, and drawBoss then refines it per archetype (BOSS_MOTION[key].scale) so
 * a 64-box creature is drawn at 2 and a 96-box one stays at 1.5. Passing a
 * scale that is NOT this constant means the caller has its own opinion — the
 * overworld draws bosses at 1 on a 16px tile map — and is honoured verbatim.
 *
 * WHY 2 FOR THE 64-BOX, RE-DERIVED AGAINST THE 256x224 RASTER. The old 1.75
 * came from one measurement: 64 * 1.75 = 112, and 112 is exactly twice the
 * 192 - 136 = 56 the creature had to the right of STAGE.enemyX, so it filled
 * the frame to its edge. On the new stage that same sum gives 2 * (256 - 184)
 * / 64 = 2.25 — and 2.25 is refused for two reasons. It is not a whole number,
 * which puts a half source pixel across every row of a 144-tall creature; and
 * 64 * 2.25 = 144 plus a 12-pixel sink lands the feet on row 199, the last row
 * of the safe area, with nothing in hand.
 *
 * 2 is the whole number under it. 64 * 2 = 128, which is §B's tallest rung —
 * the same 96x128 the final boss is authored at — so the largest creature the
 * ladder allows and the largest one the stage draws are one height. Standing
 * on the ground line at 175 with a sink of 9..12 it spans roughly rows 65..195,
 * inside the 24..199 safe area at both ends, and 128 wide centred on 184 it
 * runs 120..248 with 8 columns to spare at the frame edge. Against the hero's
 * 96 it is a third again as tall, which is what a boss has to be.
 *
 * THE 96-BOX WIDE RIGS USED TO KEEP 1.5, AND 1.5 IS NOT A WHOLE NUMBER EITHER.
 *
 * The comment above rejects 1.75 because it "is not a whole number"; 1.5 fails
 * the same test and shipped anyway. The stage is drawn under
 * ctx.setTransform(px, ...), so a grid cell lands on `scale * px` device
 * pixels, and that product has to be an integer at EVERY px the fit produces.
 * Driven live and counted, px is not always even:
 *   1280x800  dpr1  px 2  -> 1.5 * 2 = 3      whole
 *   1440x940  dpr1  px 2  -> 3                whole
 *   1600x1000 dpr1  px 3  -> 4.5              HALF A PIXEL
 *   1920x1080 dpr1  px 3  -> 4.5              HALF A PIXEL
 *   1440x940  dpr2  px 5  -> 7.5              HALF A PIXEL
 *   1600x1000 dpr2  px 6  -> 9                whole
 * Rendered at 4.5 and counted: 48 of the dragon's 96 source columns come out 4
 * device columns wide and 48 come out 5, and 32 of its 64 rows come out 4 rows
 * tall against 32 at 5. Put beside a whole x4 render of the same head the
 * teeth are uneven, one horn is a pixel fatter than the other and the two
 * pupils are different sizes. Three of the six configurations this game opens
 * at are on that grid.
 *
 * THE ARITHMETIC ALLOWS EXACTLY TWO ANSWERS AND ONLY ONE OF THEM IS A BOSS.
 * A cell must land on a whole number of logical pixels, so a 96-cell rig can be
 * 96 logical wide (scale 1) or 192 (scale 2) and nothing in between. 144 is not
 * reachable from 96 cells: rasterising the rig "at its final stage size" of
 * 144x96 would need cells 1.5 canvas pixels wide, which is the same half pixel
 * moved one step earlier in the pipeline, and re-authoring the four rigs into a
 * 72x64 box to reach 144 at scale 2 would cost real drawing — measured across
 * every frame and phase, the painted content spans 81 columns for the dragon,
 * 84 for the wyrm and 91 for the interpreter, so 72 clips wing, staff and coil.
 *
 * So 2, and the wide rigs are 192x128 on the stage. That is §B's 96x128 rung in
 * logical pixels, which is precisely what the old note here asked for ("the rung
 * wants... promoting to §B's 96x128 final-boss box"), and it costs no art: every
 * authored pixel survives, drawn twice as big.
 *
 * WHAT 192 COSTS, MEASURED, AND WHY IT IS PAID. 192 centred on enemyX 184 runs
 * 88..280, so each wide archetype carries a `bias` that pulls its PAINTED box
 * back inside the frame — computed from the painted bounding box, not guessed.
 *
 * THE 96-BOX AT EVERY STAGE, WHICH IS WHERE THE FIRST SET OF BIASES CAME FROM.
 * The numbers this comment used to carry were measured over stages 0..2 and
 * frames 0..4 with no beat, which is what scripts/verify/stage.mjs §5 samples.
 * The last two stages are the ones that ADD — spall bites the contour, and
 * crown() puts spines out of it — so the widest the creature ever gets is at a
 * stage nobody was measuring. Re-measured over all six stages, all five frames
 * and all six beats:
 *   dragon       bias -12, on screen  84..255   widest at stage 0
 *   hydra        bias   0, on screen 130..247   widest at stage 5
 *   wyrm         bias  -2, on screen  86..255   widest at stage 4  (was 0: 257)
 *   interpreter  bias -20, on screen  68..255   widest at stage 5  (was -14: 261)
 * Two of the four ran off the right edge of a 256-wide frame at their last
 * stage — the wyrm by 2 columns, the interpreter by 6 — so the spines the final
 * form is FOR were the pixels being clipped.
 *
 * AND THEN THE SWAY, WHICH THAT MEASUREMENT STILL LEFT OUT. Every line above is
 * a STILL: it places the sprite at `left = round(x + bias - w/2)` and stops.
 * drawBoss does not stop there — it adds `dx = clamp(round(pose.dx * scale),
 * -4, 4)` on top, every frame, forever, because the ambient pose is continuous
 * and the frames are not. So three of the four rigs above, sitting at exactly
 * 255 with zero slack, spent part of every idle cycle over the edge:
 *   dragon       sway 1 -> dx +-2   right edge 257   2 columns of tail cut
 *   wyrm         sway 3 -> dx +-4   right edge 259   4 columns of the 3rd coil
 *   interpreter  sway 2 -> dx +-4   right edge 259   4 columns, and it is the staff
 * A bias derived from a still is not a bias, it is half of one. Re-derived over
 * all six stages x five frames x six beats x every dx the clamp can produce —
 * the full envelope the renderer can actually put on the glass:
 *   dragon       bias -14, on screen  80..255   0 of 540 frames outside
 *   hydra        bias   0, on screen 126..251   0 of 900 frames outside
 *   wyrm         bias  -6, on screen  78..255   0 of 900 frames outside
 *   interpreter  bias -24, on screen  60..255   0 of 900 frames outside
 * Each is the LARGEST bias that clears the edge, so the figures move the two
 * or four columns they had to and not one more: the composition is off-centre
 * by as little as the frame allows. Do not shrink the dx clamp instead — the
 * +-4 cap is what keeps the 128-wide rigs in frame in the first place.
 * scripts/verify/stage.mjs §5 now sweeps the same envelope, sway included, so
 * a still-derived bias cannot pass again. docs/08 §B-2 carries this table.
 *
 * The hero stands 32..95. So on the frames where the wyrm's and the
 * interpreter's coils swing furthest left they reach BEHIND him — which is why
 * fx.js now draws the hero after the enemy rather than before it. A creature
 * this size cannot both clear the party and keep its own tail, and of the two
 * the party is the one that must never be hidden.
 *
 * COULD THE WIDE RUNG BE 96x96 SO IT IS GENUINELY TALLER? No, and the frame is
 * what says so rather than taste. A wide rig is drawn at 2, so 96 authored rows
 * are 192 logical ones; standing on ground 175 with the sink of 3 the feet land
 * at 178 and the top at 178 - 192 = -14, so 38 of the creature's rows are off
 * the canvas or in the overscan before a pixel of it is redrawn. The ceiling is
 * the safe area: 175 - 24 = 151 rows above the ground line, plus the sink, so
 * the tallest whole-blit rig that fits at scale 2 is 96x72 -> 192x144, spanning
 * rows 34..177. That is 16 logical rows taller than today and it costs
 * re-authoring four rigs and every part offset, fault and core inside them; it
 * is written down here rather than done because the rung that actually needed
 * drawing was the one nothing in the tree had at all, which is FINAL_BOSS_H.
 *
 * AND THE FINAL RUNG, WHICH IS NOT SUBJECT TO ANY OF THIS. 96x128 at blit 1 is
 * 96 logical columns centred on 184: cols 136..231, twenty-four clear of the
 * right edge and forty clear of the hero. It is the only boss whose `bias` is
 * 0 because it is the only one that never needed one.
 *
 * `sink` drops from 4 to 3 so the feet keep the same 6 logical rows under the
 * ground line they had at 1.5.
 *
 * Destination coordinates must be rounded or the half-pixel lands between two
 * source rows.
 */
export const BOSS_STAGE_SCALE = 2;

/* The scale a given archetype actually wants on the battle stage. */
export function bossStageScale(key) {
  return (BOSS_MOTION[resolveBoss(key)] || BOSS_MOTION.titan).scale;
}

/* Lighting for the scene, so the stage can be tinted to the creature standing
 * on it. Returned as plain hex strings; fx.js can drop them straight into a
 * gradient or a withAlpha(). */
export function bossLighting(key, colour, element) {
  const art = ART[resolveBoss(key)];
  const base = colour || art.colour;
  const r = ramp(base);
  const a = ramp(art.accent);
  /* The stage is lit by the creature standing on it, and the creature is lit
   * by its region's element, so the stage inherits the element too. Without
   * this the sprite would carry a cold rim while the fog behind it stayed the
   * colour it was before — which reads as a recoloured sprite on somebody
   * else's background, the exact thing the rim is there to prevent. */
  const el = ELEMENT_LIGHT[element === undefined ? BOSS_ELEMENT[resolveBoss(key)] : element];
  const tone = (hex, to, t) => (el ? mix(hex, to, t) : hex);
  return {
    key: resolveBoss(key),
    colour: base,
    element: el ? (element === undefined ? BOSS_ELEMENT[resolveBoss(key)] : element) : null,
    accent: art.accent,
    rim: tone(r.light1, el && el.rim, 0.78),
    glow: tone(mix(r.light2, '#ffffff', 0.3), el && el.glow, 0.6),
    ember: tone(a.light1, el && el.ember[1], 0.55),
    ambient: mix(r.shadow2, '#0a0910', 0.55),
    fog: mix(r.shadow1, '#0e0c16', 0.72),
    floor: mix(r.shadow2, '#141220', 0.6),
    tint: shade(base, -40),
  };
}

export const BOSS_PALETTES = Object.freeze(Object.fromEntries(
  BOSS_ARCHETYPES.map(k => [k, Object.freeze(bossLighting(k, ART[k].colour))]),
));

/* ================================================================
 * ASSEMBLY
 * ================================================================
 * Layers go down in one order and one order only: parts marked `behind`, the
 * posed body, then the parts in front. The whole stack is merged into a single
 * character grid BEFORE shading, which is the point — applyRim derives light
 * from the silhouette, and a wing shaded separately from the body it overlaps
 * would be lit as if the body were not there.
 */
function partGrid(part, frame, beat) {
  let g = (part.alt && part.alt[frame])
    || (part.altBeat && (beat & 1) ? part.altBeat : null)
    || part.grid;
  if (part.flip) g = flipX(g);
  if (part.skew && part.skew[frame]) {
    const [top, bottom] = filledBounds(g);
    g = skewRows(g, top, bottom, part.skew[frame]);
  }
  return g;
}

function partOffset(part, frame, beat) {
  const f = (part.frames && part.frames[frame]) || [0, 0];
  const [dx, dy] = driftAt(part.drift, beat);
  return [(part.ox | 0) + (f[0] | 0) + dx, (part.oy | 0) + (f[1] | 0) + dy];
}

/* The parts THIS stage has, and the two stages that change them.
 *
 *   SHORN   it loses the part it was carrying: a wing torn off at the
 *           shoulder, the colossus's maul, the Interpreter's hat. For the one
 *           archetype authored with a `grow` and no `shed` — the hydra, whose
 *           opening line is about growing heads — this is where the head comes
 *           out instead, which is the same event said the other way round.
 *   CROWNED both: whatever it had left to lose is gone and whatever it had to
 *           put out is out.
 *
 * A limb is the largest silhouette change available and it costs nothing to
 * draw, because the part was already authored — it is simply not stamped. */
function partsFor(art, phase) {
  const base = art.parts || [];
  if (phase < BOSS_PHASE.SHORN) return base;
  if (phase < BOSS_PHASE.CROWNED) {
    if (art.shed) return base.filter(p => p.name !== art.shed);
    return art.grow ? base.concat(art.grow) : base;
  }
  const kept = art.shed ? base.filter(p => p.name !== art.shed) : base;
  return art.grow ? kept.concat(art.grow) : kept;
}

/* A hydra's heads lash independently, but their roots remain attached to the
 * thorax. Build the short muscular bridge behind the body from the actual
 * posed neck root; a fixed neck offset detached on the attack extreme. */
function hydraRootBridge(dst, neck, ox, oy, chestX, chestY) {
  let y = neck.length - 1;
  while (y >= 0 && !/[^. ]/.test(neck[y])) y--;
  if (y < 0) return;
  let first = neck[y].search(/[^. ]/), last = neck[y].length - 1;
  while (last > first && (neck[y][last] === '.' || neck[y][last] === ' ')) last--;
  const x0 = ox + (first + last) / 2, y0 = oy + y - 1;
  const mask = new Set(), w = dst[0].length, h = dst.length;
  const length = Math.max(1, Math.ceil(Math.hypot(chestX - x0, chestY - y0)));
  for (let i = 0; i <= length; i++) {
    const t = i / length, cx = Math.round(x0 + (chestX - x0) * t);
    const cy = Math.round(y0 + (chestY - y0) * t), radius = 3 + Math.floor(t * 2);
    for (let dy = -radius; dy <= radius; dy++) for (let dx = -radius; dx <= radius; dx++) {
      if (dx * dx + dy * dy > radius * radius) continue;
      const x = cx + dx, y = cy + dy;
      if (x >= 0 && x < w && y >= 0 && y < h) mask.add(y * w + x);
    }
  }
  const rows = dst.map(r => r.split(''));
  for (const at of mask) {
    const y = Math.floor(at / w), x = at % w;
    rows[y][x] = mask.has(at - 1) && mask.has(at + 1) && mask.has(at - w) && mask.has(at + w) ? 'B' : 'o';
  }
  for (let y = 0; y < h; y++) dst[y] = rows[y].join('');
}

function assemble(key, frame, beat, phase = 0) {
  const art = ART[key];
  const box = boxOf(art);
  const canvasGrid = blank(box.w, box.h);
  const half = art.tall ? FINAL_HALF : HALF;

  let body = art.body.half
    ? mirror(halfRect(art.body.half, half), half)
    : rect(art.body.grid);
  if (art.wear) body = patina(body, `${key}:body`, art.wear + phase * 0.012, 'd');
  body = (POSES[art.anim] || POSES.heavy)(body, frame);
  /* The body gets a beat too, one pixel of it, so the parts are not drifting
   * against something nailed down. It is the smallest amount of motion that
   * still reads, which is the point: the parts are the performance. */
  const bd = driftAt(art.body.drift, beat);

  const parts = partsFor(art, phase);
  if (key === 'hydra') for (const p of parts) {
    if (!p.name.startsWith('neck')) continue;
    const [ox, oy] = partOffset(p, frame, beat);
    hydraRootBridge(canvasGrid, partGrid(p, frame, beat), ox, oy, 48 + bd[0], 49 + bd[1]);
  }
  for (const p of parts) {
    if (!p.behind) continue;
    const [ox, oy] = partOffset(p, frame, beat);
    stamp(canvasGrid, partGrid(p, frame, beat), ox, oy);
  }
  stamp(canvasGrid, body, (art.body.ox | 0) + bd[0], (art.body.oy | 0) + bd[1]);
  for (const p of parts) {
    if (p.behind) continue;
    const [ox, oy] = partOffset(p, frame, beat);
    stamp(canvasGrid, partGrid(p, frame, beat), ox, oy);
  }
  return canvasGrid;
}

/* ================================================================
 * THE MAP FORM
 * ================================================================
 * The same creature, standing on a 16-pixel tile grid next to a 16x24 hero.
 *
 * Until now the overworld drew the BATTLE sprite at 1:1 and called that the map
 * form. That is not a map form, it is a battle sprite that has been made small,
 * and the two fail differently. At 1.75 on a near-black stage a one-pixel
 * outline and a dusting of patina are detail; at 1:1 over grass, ruins and
 * water they are noise, and the first thing noise costs you is the silhouette
 * — which at marker scale is the ONLY thing the player has. A boss you cannot
 * name from the far side of a ridge is a coloured blob with a health bar
 * waiting inside it.
 *
 * So the map form is authored, and it is authored FROM the battle form rather
 * than beside it. One pipeline, four passes:
 *
 *   1. REDUCE.  The assembled character grid — body, parts, damage and all —
 *      is box-sampled 0.72:1 into a smaller grid. A destination cell is filled
 *      when 40% of the source under it was, which keeps the mass and drops the
 *      hairlines. The winning glyph is a WEIGHTED vote, not a majority: an eye
 *      socket, a lit core, an ember and a specular count 2.4x, ordinary mass
 *      1x, and the old outline 0.3x. Plain majority loses the eyes first, and
 *      a reduced sprite without its eyes is not the same creature any more.
 *   2. DESPECKLE. A single cell of one tone marooned in another is resampling
 *      noise at this size, so it is absorbed. Features are exempt: a one-cell
 *      eye at map scale IS the eye.
 *   3. OUTLINE, HEAVILY. One full ring of hard outline dilated around the
 *      whole silhouette. That is the boss tell and it is deliberately a thing
 *      no ordinary monster on the tile grid has: mobs are 24x24 with a one-
 *      pixel edge, this is 48 tall with two, and the difference is legible
 *      before any of the interior is.
 *   4. RE-LIGHT. applyRim and the contre-jour pass run on the REDUCED
 *      silhouette, not on a resampled copy of the big one's lighting. The
 *      light is derived at the size it will be seen at, which is the whole
 *      difference between authoring small and shrinking large.
 *
 * What it does NOT do is as deliberate. No patina — pitting authored for 112
 * pixels is dirt at 48. No beats — a part drifting one pixel is the thing that
 * makes the battle form feel alive and is entirely invisible on a tile map, and
 * paying six cache entries per phase for it would be paying for nothing. The
 * map form breathes on the frame flip and bobs on the pose, and that is all it
 * needs to not look nailed down.
 *
 * Because it is derived rather than drawn, the two forms cannot drift apart.
 * That is a claim about pixels, so it is measured rather than asserted:
 * scripts/verify/bossforms.mjs normalises both silhouettes into one box and
 * reports the per-boss agreement and intersection-over-union.
 */
const MAP_INSET = 1;                 // room for the heavy outline to grow into
const MAP_FILL = 0.52;               // more than half the source under a cell

/* Glyphs that ARE the creature's identity and must survive a 0.72 reduction. */
const MAP_FEATURE = 'kwWuUiedrRXZGM';
/* The old outline, which is about to be replaced by a heavier one and should
 * not be allowed to win cells on the way there. */
const MAP_OUTLINE = 'oOQ';
/* Features are also exempt from the despeckle: a one-cell eye is the eye. */
const MAP_KEEP = 'kwWuUierR';

function reduceGrid(grid, nw, nh) {
  const h = grid.length;
  const w = Math.max(...grid.map(r => r.length));
  const src = normalise(grid, w);
  const out = [];
  for (let ry = 0; ry < nh; ry++) {
    const y0 = Math.floor((ry * h) / nh);
    const y1 = Math.max(y0 + 1, Math.floor(((ry + 1) * h) / nh));
    const row = new Array(nw);
    for (let rx = 0; rx < nw; rx++) {
      const x0 = Math.floor((rx * w) / nw);
      const x1 = Math.max(x0 + 1, Math.floor(((rx + 1) * w) / nw));
      let total = 0, on = 0;
      const score = new Map();
      for (let y = y0; y < y1; y++) {
        const line = src[y];
        if (line === undefined) continue;
        for (let x = x0; x < x1; x++) {
          total++;
          const ch = line[x];
          if (isEmpty(ch)) continue;
          on++;
          const weight = MAP_FEATURE.indexOf(ch) >= 0 ? 2.4
            : MAP_OUTLINE.indexOf(ch) >= 0 ? 0.3 : 1;
          score.set(ch, (score.get(ch) || 0) + weight);
        }
      }
      if (!total || on / total < MAP_FILL) { row[rx] = T; continue; }
      /* Argmax with a glyph-order tie-break, so the answer does not depend on
       * the order the source happened to be walked in. */
      let best = 'B', bestV = -1;
      for (const [ch, v] of score) {
        if (v > bestV || (v === bestV && ch < best)) { best = ch; bestV = v; }
      }
      row[rx] = best;
    }
    out.push(row.join(''));
  }
  return out;
}

function despeckle(grid) {
  const w = Math.max(...grid.map(r => r.length));
  const src = normalise(grid, w);
  const out = src.map(r => r.split(''));
  for (let y = 0; y < src.length; y++) {
    for (let x = 0; x < w; x++) {
      const ch = src[y][x];
      if (isEmpty(ch) || MAP_KEEP.indexOf(ch) >= 0) continue;
      const up = at(src, y - 1, x), down = at(src, y + 1, x);
      const left = at(src, y, x - 1), right = at(src, y, x + 1);
      if (isEmpty(up) || up !== down || up !== left || up !== right || up === ch) continue;
      out[y][x] = up;
    }
  }
  return out.map(r => r.join(''));
}

/* One ring of hard outline dilated around everything. Where the reduction
 * happened to keep a cell of the old outline this lands on top of it and the
 * edge reads two deep; where it did not, this is the edge. Either way the
 * creature carries a heavier border than anything else on the tile grid. */
function heavyOutline(grid) {
  const w = Math.max(...grid.map(r => r.length));
  const src = normalise(grid, w);
  const out = src.map(r => r.split(''));
  for (let y = 0; y < src.length; y++) {
    for (let x = 0; x < w; x++) {
      if (!isEmpty(src[y][x])) continue;
      if (!isEmpty(at(src, y - 1, x)) || !isEmpty(at(src, y + 1, x))
        || !isEmpty(at(src, y, x - 1)) || !isEmpty(at(src, y, x + 1))) out[y][x] = 'o';
    }
  }
  return out.map(r => r.join(''));
}

function assembleMap(key, frame, phase, rawKey, element) {
  const art = ART[key];
  const mbox = mapBoxOf(art);
  const boxW = mbox.w;
  let grid = assemble(key, frame, 0, phase);
  /* The same damage passes, in the same order, BEFORE the reduction. A crack
   * opened after the reduction would be a crack drawn at the wrong scale; a
   * limb shed after it would be a limb the reduction had already merged into
   * the torso. The creature is damaged and then made small, in that order,
   * which is also the order it happens to it. */
  grid = fracture(grid, `${key}:${frame}:${phase}`, phase, art.faults);
  grid = spall(grid, phase, art.faults, `${key}:${frame}`);
  grid = breach(grid, phase, art.faults, `${key}:${phase}`);
  grid = ember(grid, phase, art.core);
  grid = ignite(grid, phase, art.core);
  grid = crown(grid, phase, `${key}:${frame}`);
  /* Dressed at battle scale and THEN reduced — see dress() for why this is the
   * order the "same creature" claim depends on. */
  grid = dress(grid, rawKey, element, frame, 0, lightPhase(phase));
  grid = despeckle(reduceGrid(grid, boxW - MAP_INSET * 2, mbox.h - MAP_INSET * 2));
  const box = blank(boxW, mbox.h);
  stamp(box, grid, MAP_INSET, MAP_INSET);
  /* Same rule as the battle form, and for the same measured reason: an element
   * that refuses the contre-jour must refuse it in BOTH forms or the marker and
   * the fight disagree about what the creature is made of — and the marker is
   * the one that was still spending a palette slot on it. */
  const lit = materialPlanes(applyRim(heavyOutline(box)), key);
  return (!element || wantsRim(ELEMENT_STUB[element])) ? rimPass(lit) : lit;
}

export function bossMapSize(key) {
  const art = ART[resolveBoss(key)];
  return mapBoxOf(art);
}

/* The overworld form. Two frames, three phases, no beats — see above for why.
 * Same cache, same eviction, same determinism guarantee as the battle form. */
export function bossMapSprite(spriteKey, colour, frame = 0, opts = {}) {
  const key = resolveBoss(spriteKey);
  const art = ART[key];
  const base = colour || art.colour;
  const f = Math.min(frameIndex(frame), BOSS_FRAME.BREATHE);
  opts = optsOf(opts);
  const ph = bossPhase(opts.phase !== undefined ? opts.phase : 0);
  const el = elementFor(spriteKey, opts);
  const cacheKey = `M|${key}|${lookOf(spriteKey).id}|${base}|${f}|${ph}|${el || '-'}`;
  const hit = cacheGet(cacheKey);
  if (hit) return hit;
  const mbox = mapBoxOf(art);
  const { canvas, ctx } = offscreen(mbox.w, mbox.h);
  const grid = assembleMap(key, f, ph, spriteKey, el);
  drawGrid(ctx, grid, boundedBossPalette(grid,
    bossPalette(base, art.accent, lightPhase(ph), el)));
  return cachePut(cacheKey, canvas);
}

/* Both map frames of one boss at one phase. Two canvases; call it when a
 * region loads and the overworld never generates inside its own draw. */
export function warmBossMap(spriteKey, colour, phase = 0) {
  bossMapSprite(spriteKey, colour, BOSS_FRAME.IDLE, { phase });
  bossMapSprite(spriteKey, colour, BOSS_FRAME.BREATHE, { phase });
  return 2;
}

/* ---------------- rasterising ---------------- */
function offscreen(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

const spriteCache = new Map();

/* One shared cache for both forms — map entries are prefixed 'M|' — because
 * they are the same creature and a caller crossing between them should not pay
 * twice for the crossing.
 *
 * A fight's working set is ONE creature: two idle frames x six beats, plus the
 * three action frames = 15 canvases per stage, and a fight that runs its whole
 * phase ladder touches all six stages, so 90. A region marker is two frames x
 * six stages = 12. Both doubled when the phase ladder went from three stages to
 * six, and the cap went with them.
 *
 * The bound that CANNOT be covered, and it is worth saying so rather than
 * quietly missing it, is a caller warming every look at every stage:
 *
 *   battle  32 looks x 6 stages x 15  = 2880
 *   map     32 looks x 6 stages x  2  =  384
 *                                       ----
 *                                       3264   ~52MB of RGBA
 *
 * That is a codex screen warming the entire bestiary, and paying fifty
 * megabytes of resident canvas so it never regenerates is the wrong trade. It
 * evicts, and what it evicts costs a regeneration rather than a defect. The
 * LRU below is what makes that safe: the entries a live fight is touching stay
 * hot, so the screen that thrashes is the one nobody is fighting on.
 *
 * (It was 640 against a set of 675 — one archetype was added to the roster
 * after the number was written, and the arithmetic was not redone. Then it was
 * 832 against 15 ARCHETYPES, and the unit changed under it: the theme layer
 * keys on the LOOK, so the fourteen named bosses, the seventeen apexes and the
 * final trial are thirty-two distinct entries where there used to be fifteen.
 * scripts/verify/bossforms.mjs warms the whole ARCHETYPE roster at every stage
 * — 16 x 6 x 17 = 1632, inside this cap — and counts rebuilds, so the next time
 * the unit changes it is a failing harness rather than a slow frame nobody
 * attributes to this.) */
const CACHE_CAP = 2048;
/* Exported so the harness can print the real number instead of a copy of it.
 * bossforms.mjs was reporting "cap 832" against a cap that had been 1792 for
 * two passes, which is exactly the kind of stale literal this whole file spends
 * its comments arguing against. */
export const BOSS_CACHE_CAP = CACHE_CAP;

/* True LRU rather than insertion order, and with six stages in play it is
 * doing more work than it was with three: the oldest INSERTED entry is
 * frequently the current stage's idle frame, and evicting that would
 * regenerate a sprite every time the idle loop came round. */
function cacheGet(key) {
  const hit = spriteCache.get(key);
  if (hit === undefined) return undefined;
  spriteCache.delete(key);
  spriteCache.set(key, hit);
  return hit;
}

function cachePut(key, value) {
  if (spriteCache.size >= CACHE_CAP) {
    const coldest = spriteCache.keys().next().value;
    spriteCache.delete(coldest);
  }
  spriteCache.set(key, value);
  return value;
}

/* The fourth argument is an options bag, and half the callers in the tree pass
 * a bare phase number there instead — scripts/verify/apex.mjs has been passing
 * `p` positionally and silently getting stage 0 for every one of its six
 * stages. Accepting the number costs one line and turns a whole verification
 * loop from a no-op into a measurement. A string is a phase key for the same
 * reason. */
function optsOf(opts) {
  if (opts === null || opts === undefined) return {};
  const t = typeof opts;
  if (t === 'number' || t === 'string') return { phase: opts };
  return opts;
}

/* One boss, one frame, one colour. Deterministic and cached forever: the same
 * Hash Titan carries the same pitting in every session. */
export function bossSprite(spriteKey, colour, frame = 0, opts = {}) {
  const key = resolveBoss(spriteKey);
  const art = ART[key];
  const base = colour || art.colour;
  const f = frameIndex(frame);
  opts = optsOf(opts);
  const ph = bossPhase(opts.phase !== undefined ? opts.phase : 0);
  /* Beats only run on the two idle frames. The action frames already move
   * every part to an authored extreme, and giving them a sub-beat would
   * multiply the cache to hide a difference nobody can see in 240ms. */
  const beat = (f <= BOSS_FRAME.BREATHE && opts && opts.beat)
    ? (((opts.beat | 0) % BOSS_BEATS) + BOSS_BEATS) % BOSS_BEATS : 0;
  const el = elementFor(spriteKey, opts);
  /* The LOOK id, not just the archetype. Two creatures can share a body and an
   * element and still be different animals — the Slagmother and the Bug Demon
   * are both FIRE demons — and the theme pass seeds its geometry on the look
   * id, so leaving it out of the key made the second one a cache hit on the
   * first and handed back a byte-identical sprite. The id is coarser than the
   * raw key on purpose: 'titan' and 'hash_titan' resolve to one look and should
   * share one entry. */
  const lid = lookOf(spriteKey).id;
  const cacheKey = `${key}|${lid}|${base}|${f}|${ph}|${beat}|${el || '-'}`;
  const hit = cacheGet(cacheKey);
  if (hit) return hit;

  let grid = assemble(key, f, beat, ph);

  /* Damage before shading: applyRim derives light from the silhouette, and a
   * fissure opened after the fact would be lit as if the plate were still shut.
   *
   * The order inside the damage block is the order of the stages, because each
   * pass reads what the last one wrote: cracks, then the contour bitten off
   * around them, then holes through what is left, then the light behind the
   * holes, then whatever the thing puts out at the end. */
  grid = fracture(grid, `${key}:${f}:${ph}`, ph, art.faults);
  grid = spall(grid, ph, art.faults, `${key}:${f}`);
  grid = breach(grid, ph, art.faults, `${key}:${ph}`);
  grid = ember(grid, ph, art.core);
  grid = ignite(grid, ph, art.core);
  grid = crown(grid, ph, `${key}:${f}`);
  /* The element, as geometry, before the light. Same reason the damage passes
   * run before it: applyRim derives the light from the silhouette, and a spur
   * grown after the fact would be an unlit spur on a lit creature. */
  grid = dress(grid, spriteKey, el, f, beat, lightPhase(ph));
  /* The contre-jour, and the one cast that does not get it.
   *
   * bossart.wantsRim() has said since it was written that VOID and BRUTE refuse
   * the low-left rim — void because being the exception to the cast's one light
   * IS void, stone because rock does not emit — and this file imported the
   * function and never called it. The rim was painted on every creature and the
   * palette was then asked to hide it, which it does badly: measured on the
   * Interviewer, 'Q' lands at #231c2e against an outline of #362b46 and renders
   * 50 pixels of a SIXTEENTH colour on a sprite that is otherwise exactly at
   * fifteen. Not painting it is both the cheaper answer and the one the rule
   * already asked for. 'Q' is written inside the body, never on the boundary,
   * so no silhouette moves; what changes is that four VOID and three BRUTE
   * archetypes each give a palette slot back. */
  grid = materialPlanes(applyRim(grid), key);
  if (!el || wantsRim(ELEMENT_STUB[el])) grid = rimPass(grid);

  const box = boxOf(art);
  const { canvas, ctx } = offscreen(box.w, box.h);
  drawGrid(ctx, grid, boundedBossPalette(grid,
    bossPalette(base, art.accent, lightPhase(ph), el)));
  return cachePut(cacheKey, canvas);
}

/* All five frames of one boss, in table order. Call once at fight start and the
 * render loop never touches the generator again. */
export function bossFrames(spriteKey, colour, opts = {}) {
  return BOSS_FRAME_NAMES.map((_, i) => bossSprite(spriteKey, colour, i, opts));
}

/* Every canvas one phase of one fight can ask for, built in one go. A caller
 * that warms this at phase change never generates inside the render loop. */
export function warmBoss(spriteKey, colour, phase = 0) {
  let n = 0;
  for (let f = 0; f < BOSS_FRAME_COUNT; f++) {
    const beats = f <= BOSS_FRAME.BREATHE ? BOSS_BEATS : 1;
    for (let b = 0; b < beats; b++) { bossSprite(spriteKey, colour, f, { phase, beat: b }); n++; }
  }
  return n;
}

export function clearBossCache() { spriteCache.clear(); flashCache = new WeakMap(); }

/* Flat-colour silhouette for the hit flash, keyed on the source canvas in a
 * WeakMap so it dies with the sprite and a long session cannot accumulate one
 * flash canvas per frame drawn. */
let flashCache = new WeakMap();
function silhouette(img, colour) {
  let byColour = flashCache.get(img);
  if (!byColour) { byColour = new Map(); flashCache.set(img, byColour); }
  const hit = byColour.get(colour);
  if (hit) return hit;
  const { canvas, ctx } = offscreen(img.width, img.height);
  ctx.drawImage(img, 0, 0);
  ctx.globalCompositeOperation = 'source-atop';
  ctx.fillStyle = colour;
  ctx.fillRect(0, 0, img.width, img.height);
  byColour.set(colour, canvas);
  return canvas;
}

/* ---------------- ambient pose ----------------
 * Same contract as sprites.idlePose, so a caller that already drives mobs needs
 * no new vocabulary: dx/dy in sprite pixels, plus which idle frame to hold.
 */
export function bossPose(spriteKey, timeMs, seed = 0) {
  const m = bossMotion(spriteKey);
  const t = (timeMs / m.period) + m.phase + seed * 0.137;
  const cycle = t - Math.floor(t);
  const wave = Math.sin(cycle * Math.PI * 2);
  return {
    dx: Math.round(Math.cos(cycle * Math.PI * 2) * m.sway),
    dy: -Math.round(Math.abs(wave) * m.bob),
    frame: cycle < 0.5 ? BOSS_FRAME.IDLE : BOSS_FRAME.BREATHE,
    /* The sub-position inside the idle loop. The frame flips twice per period;
     * the beat advances BOSS_BEATS times, and each part reads it at its own
     * rate. This is the field that makes the parts stop marching in step. */
    beat: Math.floor(cycle * BOSS_BEATS) % BOSS_BEATS,
    cycle,
  };
}

/* Which frame a state machine should be showing, given when the state started.
 * Returns the frame index and whether the state has run out, so the caller can
 * advance without duplicating the table. */
export function bossFrameAt(spriteKey, state, elapsedMs) {
  const row = BOSS_FRAME_TABLE[String(state || 'idle').toLowerCase()];
  if (!row) return { index: 0, done: true, next: 'idle' };
  const hold = row.hold || bossMotion(spriteKey).telegraph;
  return { index: row.index, done: elapsedMs >= hold, next: row.next, hold };
}

/* ================================================================
 * DRAW
 * ================================================================
 * x is the horizontal centre, y is the ground line — feet, not sprite origin,
 * matching how fx.js places the hero. A floating boss is authored with its own
 * gap above the baseline, so the same call site works for both without a flag.
 */
/* The floor eats the last few rows. A boss is drawn with its feet BELOW the
 * ground line — see `sink` — and without this it reads as a sprite whose legs
 * were cut off rather than as a creature standing in front of, and partly
 * inside, the floor. Four hard bands, darkening downward, in the stage's own
 * near-black: the same trick as an aerial-perspective haze, run vertically. */
function floorVeil(ctx, left, right, groundY, depth, tone) {
  if (depth <= 0) return;
  const bands = 4;
  for (let i = 0; i < bands; i++) {
    const y0 = groundY + Math.round((depth * i) / bands);
    const y1 = groundY + Math.round((depth * (i + 1)) / bands);
    if (y1 <= y0) continue;
    ctx.globalAlpha = 0.3 + 0.7 * ((i + 1) / bands);
    ctx.fillStyle = tone;
    ctx.fillRect(left, y0, right - left, y1 - y0);
  }
  ctx.globalAlpha = 1;
}

export function drawBoss(ctx, key, x, y, opts = {}) {
  const artKey = resolveBoss(key);
  const m = BOSS_MOTION[artKey];
  const art = ART[artKey];
  const colour = opts.colour || art.colour;
  const reduced = !!opts.reducedMotion;
  const time = opts.time || 0;

  /* An entrance is a different animal: it owns the staging, the reveal and the
   * light. One number turns this call into that one. */
  if (opts.entrance !== undefined && opts.entrance !== null && opts.entrance < 1) {
    return drawBossEntrance(ctx, artKey, x, y, opts.entrance, opts);
  }

  const pose = reduced ? { dx: 0, dy: 0, frame: BOSS_FRAME.IDLE, beat: 0 }
    : bossPose(artKey, time, opts.seed || 0);

  let frame = opts.frame;
  if (frame === undefined || frame === null) frame = pose.frame;
  const phase = bossPhase(opts.phase);
  const beat = reduced ? 0 : (opts.beat === undefined ? pose.beat : opts.beat);

  /* Scale. A caller that passes nothing, or that passes the stage default,
   * is asking for "however big this creature should be on the battle stage"
   * and gets the per-archetype answer. A caller with its own number — the
   * overworld map, at 1 — is taken at its word and nothing is applied on top.
   *
   * And a caller asking for 1:1 or smaller is not asking for a small battle
   * sprite, it is asking for the MAP FORM, so that is what it gets. This is
   * the one branch that decides which of the two bodies of work a call lands
   * in, and it is deliberately inferred rather than demanded: overworld.js
   * already passes `scale: 1` and is not this pass's file to edit. `map: true`
   * or `map: false` overrides it either way for anything that wants to be
   * explicit — a bestiary page showing both forms side by side needs to. */
  const staged = opts.scale === undefined || opts.scale === BOSS_STAGE_SCALE;
  const asked = opts.scale === undefined ? 1 : opts.scale;
  const mapped = opts.map !== undefined ? !!opts.map : (!staged && asked <= 1.05);

  /* The element travels on the CALLER'S key, not the resolved archetype: two
   * apexes sharing a body are told apart by their region's light and would be
   * identical if this passed artKey through. */
  const element = opts.element === undefined ? bossElement(key) : opts.element;
  /* And so does the KEY. The line above already worked this out for the
   * element and then handed the resolved archetype to the sprite builders
   * anyway, which threw the distinction away again one line later: the builders
   * key their cache and seed their theme geometry on the look, and the look of
   * 'colossus' is the Rolling Titan whichever apex asked for it. Passing the
   * caller's key through costs nothing — both builders resolve internally — and
   * it is the difference between the Rimewarden and the Unnamed being two
   * creatures on one body and being one creature drawn twice.
   *
   * It also stops drawBoss missing the cache that warmBoss just filled: a
   * caller that warms by id and draws by archetype was building every frame
   * twice under two different keys. */
  const img = mapped
    ? bossMapSprite(key, colour, frame, { phase, element })
    : bossSprite(key, colour, frame, { phase, beat, element });
  if (!img) return null;

  const scale = staged ? m.scale : opts.scale;
  /* The map form keeps the battle form's relationship with the ground — the
   * feet go the same fraction of the body under the floor — so a creature that
   * is planted in its stage is planted on its tile too. Scaled by the ratio of
   * the two boxes rather than copied, or a 48-tall marker would sink eleven
   * pixels and stand in a hole. */
  const sink = mapped ? (opts.sink === undefined ? m.mapSink : opts.sink)
    : staged ? (opts.sink === undefined ? m.sink : opts.sink) : 0;
  const bias = mapped ? 0 : staged ? (opts.bias === undefined ? m.bias : opts.bias) : 0;
  const spread = mapped ? m.shadow * m.mapRatio : m.shadow;

  const w = Math.round(img.width * scale);
  const h = Math.round(img.height * scale);

  // The ambient bob is applied here rather than baked into a frame: it is
  // continuous, the frames are not, and a boss that only moved on frame change
  // would step rather than drift. The horizontal half is capped: something
  // this heavy does not slide five pixels sideways, and the cap is also what
  // keeps a 128-wide creature inside a 256-wide stage at every phase of it —
  // 184 + 64 + 4 = 252, four columns short of the edge at full sway.
  const dx = Math.max(-4, Math.min(4, Math.round(pose.dx * scale)));
  const dy = Math.round(pose.dy * scale);
  const foot = Math.round(y + sink * scale);
  const left = Math.round(x + bias - w / 2) + dx;
  const top = foot - h + dy;

  if (opts.shadow !== false) {
    const squeeze = m.floats ? 0.7 : 1;
    drawGroundShadow(ctx, Math.round(x + bias + dx * 0.4), Math.round(y + 1),
      Math.round(spread * scale * 0.5 * squeeze),
      Math.round(spread * scale * 0.17 * squeeze),
      m.floats ? 0.22 : 0.36);
  }

  const alpha = opts.alpha === undefined ? 1 : opts.alpha;
  if (alpha !== 1) { ctx.save(); ctx.globalAlpha = alpha; }
  ctx.drawImage(img, left, top, w, h);
  const flash = opts.flash || 0;
  if (flash > 0.01) {
    const sil = silhouette(img, opts.flashColour || '#ffffff');
    const prev = ctx.globalAlpha;
    ctx.globalAlpha = alpha * Math.min(1, flash);
    ctx.drawImage(sil, left, top, w, h);
    ctx.globalAlpha = prev;
  }
  if (alpha !== 1) ctx.restore();

  // Everything below the ground line goes into the floor.
  const below = top + h - Math.round(y);
  if (opts.occlude !== false && !mapped && sink > 0 && below > 0) {
    const light = bossLighting(artKey, colour, element);
    floorVeil(ctx, left, left + w, Math.round(y), below,
      opts.floorTone || light.floor);
  }

  return { x: left, y: top, w, h, frame, phase, beat, key: artKey, map: mapped };
}

/* ================================================================
 * THE ENTRANCE
 * ================================================================
 * A boss that fades up at 40% opacity is a creature that was always there and
 * that the renderer got around to. This is four beats, and the creature is not
 * whole until the last one:
 *
 * The timings below are the contract. Another pass drives this — fx.js owns the
 * camera, the letterbox and the taunt card — so every number a driver needs is
 * a millisecond, exported, and not left as a fraction for someone to guess at.
 *
 *   0     - 616 ms   THE FLOOR ANSWERS. Nothing of the creature is visible.
 *                    The ground gives way: a scar widening under the feet and
 *                    chips thrown off it. Camera shake ramps 2 -> 3.7.
 *   484   - 1364 ms  THE RISE, STAGGERED. It comes up through that scar,
 *                    clipped at the ground line, so it is genuinely emerging
 *                    rather than sliding in from off-frame. The rim arrives
 *                    ahead of the body in THREE bands as each clears the
 *                    floor — feet at ~790 ms, torso at ~1058 ms, crown at
 *                    ~1364 ms. One reveal is a wipe; three is a creature
 *                    coming out of the ground a piece at a time.
 *   1210  - 1760 ms  THE CROWN LIGHTS. A wash in the creature's own colour
 *                    over the whole silhouette — the contre-jour finding the
 *                    tallest thing on the stage. Stage flash ramps to 0.66.
 *   1716  - 1892 ms  THE IMPACT. It lands. Shake spikes to 9, stage flash to
 *                    0.85, dust comes back off the floor.
 *   1892  - 2200 ms  THE SETTLE. Shadow hardens in, dust falls, shake decays
 *                    to 1. The creature is whole and holding still.
 *   2200  - 2620 ms  THE HOLD. Nothing moves but the idle loop. This beat is
 *                    the one that is always cut and is the reason an entrance
 *                    reads as an event rather than a transition: the room is
 *                    finished, the thing is standing in it, and nobody has
 *                    said anything yet.
 *   2620 ms          THE FIRST LINE. bossEntrance().taunt goes true here.
 *
 * Deterministic in k: same progress, same frame, forever. Allocates nothing —
 * the only canvases are the cached sprite and its cached silhouette.
 */
export const BOSS_ENTRANCE_MS = 2200;
/* The beat between the settle and the taunt. Held separately from the animated
 * duration so a driver can shorten the silence without restaging the arrival. */
export const BOSS_ENTRANCE_HOLD_MS = 420;
export const BOSS_TAUNT_AT_MS = BOSS_ENTRANCE_MS + BOSS_ENTRANCE_HOLD_MS;

/* The same table as data, for a driver that would rather read it than parse a
 * comment. `from`/`to` are fractions of BOSS_ENTRANCE_MS; ms are absolute from
 * the start of the arrival. */
export const BOSS_ENTRANCE_BEATS = Object.freeze([
  { name: 'floor',  from: 0,    to: 0.28, fromMs: 0,    toMs: 616,  does: 'ground opens, no creature yet' },
  { name: 'rise',   from: 0.22, to: 0.62, fromMs: 484,  toMs: 1364, does: 'emerges through the floor, rim first, in three bands' },
  { name: 'crown',  from: 0.55, to: 0.80, fromMs: 1210, toMs: 1760, does: 'contre-jour wash over the whole silhouette' },
  { name: 'impact', from: 0.78, to: 0.86, fromMs: 1716, toMs: 1892, does: 'lands; shake 9, flash 0.85, dust' },
  { name: 'settle', from: 0.86, to: 1,    fromMs: 1892, toMs: 2200, does: 'shadow hardens, dust falls, shake decays' },
  { name: 'hold',   from: 1,    to: 1.19, fromMs: 2200, toMs: 2620, does: 'nothing. This is the beat before the line.' },
]);

/* Where the three rim bands clear the ground, as fractions of the whole
 * arrival. Derived from the smoothstep on the rise rather than typed twice. */
export const BOSS_ENTRANCE_RIM_MS = Object.freeze([790, 1058, 1364]);

/* Where the clock stops. Derived from the two constants rather than typed, so
 * shortening the hold moves the line and nothing else. */
const ENTRANCE_END_T = 1 + BOSS_ENTRANCE_HOLD_MS / BOSS_ENTRANCE_MS;

/* What the entrance wants from the caller at a given progress: how hard to
 * shake, how hard to flash the stage, and whether the impact has landed yet.
 * A caller drives its camera from this rather than guessing at the timing. */
export function bossEntrance(key, k = 0) {
  /* k runs past 1 through the hold. Clamped at the top of the hold rather than
   * at the settle, so a driver can feed it one clock all the way to the line. */
  const t = Math.max(0, Math.min(ENTRANCE_END_T, k));
  const impact = 0.78;
  const hit = t >= impact && t < impact + 0.08;
  const held = t >= 1;
  return {
    key: resolveBoss(key),
    duration: BOSS_ENTRANCE_MS,
    hold: BOSS_ENTRANCE_HOLD_MS,
    tauntAt: BOSS_TAUNT_AT_MS,
    t,
    ms: Math.round(t * BOSS_ENTRANCE_MS),
    beat: held ? 'hold' : hit ? 'impact' : t < 0.28 ? 'floor'
      : t < 0.62 ? 'rise' : t < 0.8 ? 'crown' : 'settle',
    impactAt: impact,
    landed: t >= impact,
    /* True for exactly one thing: the frame on which the boss is allowed to
     * speak. Everything before it is staging and should not be interrupted. */
    taunt: t >= ENTRANCE_END_T,
    shake: held ? 0 : hit ? 9 : t < 0.28 ? 2 + t * 6 : t < 0.62 ? 3 : 1,
    flash: held ? 0 : hit ? 0.85 : t > 0.55 && t < impact ? (t - 0.55) * 1.2 : 0,
  };
}

/* Three. Two is a wipe with a pause in it and four is a staircase. */
const ENTRANCE_BANDS = 3;

function dustRing(ctx, cx, groundY, spread, rise, a, colour) {
  // Twelve hard chips on a fixed lattice. No rng in a draw path, ever.
  for (let i = 0; i < 12; i++) {
    const s = (i % 2 ? 1 : -1) * (0.25 + (i % 6) * 0.15);
    const px = Math.round(cx + s * spread);
    const py = Math.round(groundY - rise * (0.3 + ((i * 7) % 10) * 0.07));
    const size = i % 3 === 0 ? 2 : 1;
    ctx.globalAlpha = a * (i % 3 === 0 ? 0.9 : 0.55);
    ctx.fillStyle = colour;
    ctx.fillRect(px, py, size, size);
  }
  ctx.globalAlpha = 1;
}

export function drawBossEntrance(ctx, key, x, y, k, opts = {}) {
  const artKey = resolveBoss(key);
  const m = BOSS_MOTION[artKey];
  const colour = opts.colour || ART[artKey].colour;
  const light = bossLighting(artKey, colour);
  const beat = bossEntrance(artKey, k);
  const t = beat.t;
  const reduced = !!opts.reducedMotion;

  const staged = opts.scale === undefined || opts.scale === BOSS_STAGE_SCALE;
  const scale = staged ? m.scale : opts.scale;
  const sink = staged ? m.sink : 0;
  const bias = staged ? m.bias : 0;

  /* Phase during an entrance is always whole: the thing has not been hit yet,
   * and a boss that arrives already cracked has thrown away the one moment
   * where cracking it means anything. */
  const img = bossSprite(artKey, colour, t < beat.impactAt ? BOSS_FRAME.WINDUP : BOSS_FRAME.IDLE, { phase: 0, beat: 0 });
  if (!img) return null;
  const w = Math.round(img.width * scale);
  const h = Math.round(img.height * scale);
  const groundY = Math.round(y);
  const foot = Math.round(y + sink * scale);
  const left = Math.round(x + bias - w / 2);

  // 1. the floor answers — a scar opening under the feet
  const scar = Math.min(1, t / 0.28);
  if (scar > 0) {
    const half = Math.round(m.shadow * scale * 0.5 * scar);
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = light.ambient;
    ctx.fillRect(x + bias - half, groundY - 1, half * 2, 3);
    ctx.globalAlpha = 0.5 + 0.4 * scar;
    ctx.fillStyle = light.glow;
    ctx.fillRect(x + bias - Math.round(half * 0.7), groundY, Math.round(half * 1.4), 1);
    ctx.globalAlpha = 1;
    if (!reduced) dustRing(ctx, x + bias, groundY, half * 1.4, 10 * scar, 0.5 * scar, light.ember);
  }

  // 2. the rise — clipped at the ground line so it comes UP through the floor
  const rise = Math.max(0, Math.min(1, (t - 0.22) / 0.4));
  if (rise > 0) {
    const lift = Math.round((1 - (rise * rise * (3 - 2 * rise))) * h);   // smoothstep
    const top = foot - h + lift;
    ctx.save();
    ctx.beginPath();
    ctx.rect(left - 8, top, w + 16, Math.max(0, (foot - top) - (t < beat.impactAt ? 0 : 0)));
    ctx.clip();
    ctx.globalAlpha = Math.min(1, 0.35 + rise * 0.75);
    ctx.drawImage(img, left, top, w, h);
    /* Its own rim arrives before the body does, and it arrives in pieces. Each
     * third of the creature flares as it clears the floor, so what the player
     * sees is feet, then torso, then crown, rather than one sprite sliding up
     * behind one wipe. Same canvas, same cached silhouette, three clips — the
     * stagger costs nothing but the clip rects. */
    if (rise < 1 && !reduced) {
      const sil = silhouette(img, light.rim);
      const sm = rise * rise * (3 - 2 * rise);
      for (let i = 0; i < ENTRANCE_BANDS; i++) {
        const emerge = (i + 1) / ENTRANCE_BANDS;
        const d = sm - emerge;
        if (d < -0.02 || d > 0.34) continue;
        const y0 = top + Math.round(h * (1 - emerge));
        const y1 = top + Math.round(h * (1 - i / ENTRANCE_BANDS));
        if (y1 <= y0) continue;
        ctx.save();
        ctx.beginPath();
        ctx.rect(left - 8, y0, w + 16, y1 - y0);
        ctx.clip();
        ctx.globalAlpha = Math.max(0, 1 - Math.max(0, d) / 0.34) * 0.9;
        ctx.drawImage(sil, left, top, w, h);
        ctx.restore();
      }
      ctx.globalAlpha = (1 - rise) * 0.45;
      ctx.drawImage(sil, left, top, w, h);
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  // 3. the crown lights — a wash in the creature's own colour, hottest at the top
  const crown = Math.max(0, Math.min(1, (t - 0.55) / 0.25));
  if (crown > 0 && crown < 1 && !reduced) {
    const sil = silhouette(img, light.glow);
    const top = foot - h;
    ctx.globalAlpha = Math.sin(crown * Math.PI) * 0.7;
    ctx.drawImage(sil, left, top, w, h);
    ctx.globalAlpha = 1;
  }

  // 4. the settle — shadow snaps in, dust comes back off the impact
  if (t >= beat.impactAt) {
    const s = Math.min(1, (t - beat.impactAt) / (1 - beat.impactAt));
    const squeeze = m.floats ? 0.7 : 1;
    drawGroundShadow(ctx, Math.round(x + bias), groundY + 1,
      Math.round(m.shadow * scale * 0.5 * squeeze),
      Math.round(m.shadow * scale * 0.17 * squeeze),
      (m.floats ? 0.22 : 0.36) * s);
    if (!reduced) {
      dustRing(ctx, x + bias, groundY, m.shadow * scale * (0.5 + s * 0.9),
        18 * (1 - s), (1 - s) * 0.8, light.ember);
    }
    const below = foot - groundY;
    if (sink > 0 && below > 0) floorVeil(ctx, left, left + w, groundY, below, light.floor);
  }

  return { x: left, y: foot - h, w, h, frame: BOSS_FRAME.IDLE, phase: 0, beat: 0,
           key: artKey, entrance: beat };
}

/* Everything a caller needs about one archetype in a single object, for a
 * bestiary screen or a debug overlay. */
export function bossInfo(key) {
  const artKey = resolveBoss(key);
  const art = ART[artKey];
  return {
    key: artKey,
    name: art.name,
    size: bossSize(artKey),
    mapSize: bossMapSize(artKey),
    motion: BOSS_MOTION[artKey],
    lighting: BOSS_PALETTES[artKey],
    element: bossElement(artKey),
    parts: (art.parts || []).map(p => p.name),
    sheds: art.shed || null,
    shedsAt: BOSS_PHASE_NAMES[art.shed ? BOSS_PHASE.SHORN : BOSS_PHASE.CROWNED],
    grows: (art.grow || []).map(p => p.name),
    /* The one archetype authored with a grow and no shed loses nothing at
     * SHORN and grows there instead — see partsFor. Reported, rather than left
     * for a reader to work out from two nulls. */
    growsAt: BOSS_PHASE_NAMES[(art.grow && !art.shed)
      ? BOSS_PHASE.SHORN : BOSS_PHASE.CROWNED],
    frames: BOSS_FRAME_NAMES.slice(),
    phases: BOSS_PHASE_NAMES.slice(),
    beats: BOSS_BEATS,
    core: art.core ? art.core.slice() : null,
    faults: (art.faults || []).length,
    entrance: BOSS_ENTRANCE_MS,
    hold: BOSS_ENTRANCE_HOLD_MS,
    tauntAt: BOSS_TAUNT_AT_MS,
    entranceBeats: BOSS_ENTRANCE_BEATS,
  };
}
