/* Python Coding Gauntlet Legend — loot and equipment art.
 *
 * Loot used to be an 8x8 glyph flooded with the rarity colour, which meant a
 * Mythic relic and a rusty blade were the same picture in two hues. This module
 * replaces that with authored 24x24 item sprites and, more importantly, with a
 * rarity *treatment* that changes the material and the ornament rather than the
 * tint. Rarity you can only read from a border is rarity the player learns to
 * ignore; rarity carved into the metal is rarity they feel.
 *
 * Nothing here is traced, sampled or derived from any existing game. Every grid
 * is authored pixel by pixel in this file, exactly as sprites.js authors its
 * characters, and rasterised at runtime. There are no image assets.
 *
 * Four conventions carry the file:
 *
 *   1. A shape is authored as MATERIAL, never as colour. A grid says "this is
 *      body metal, this is haft, this is trim, this is gem" and the rarity
 *      supplies what those words mean. That is why a new item added to
 *      gauntlet/items.py tomorrow inherits the whole ladder for free.
 *   2. Rarity is a pipeline of grid transforms — ornament, rim, corruption,
 *      animation — applied in that order. Each stage is a pure function from
 *      grid to grid, so the ladder can be tested and extended without touching
 *      a single shape.
 *   3. Shapes are resolved from SLOT and ICON with keyword hints, never from a
 *      hardcoded item id. The catalogue is being edited by other hands; art
 *      keyed to ids would rot within the hour.
 *   4. Everything is cached by a deterministic key. Nothing allocates a canvas
 *      inside a render loop, and the same item looks the same forever.
 *
 * Wiring is documented at the bottom of the file under INTEGRATION.
 */
import { ramp, mix, rng, hash, applyRim, gridSprite, composeSprite, drawGroundShadow, scaleSprite, HERO_W, HERO_H, HERO_WEAPON_KEYS } from './sprites.js';

export const LOOT_ART_VERSION = '1.0.0';

/* The item box. 24 is the same size sprites.js uses for enemies and portraits,
 * so an item can sit in a battle scene at the same scale without resampling. */
export const ITEM_SIZE = 24;
const N = ITEM_SIZE;

/* Animated tiers run six frames at this cadence. Slow enough that a glint reads
 * as a travelling highlight rather than a flicker, fast enough to feel alive. */
export const FRAME_MS = 110;
const ANIM_FRAMES = 6;

/* ================================================================
 * COLOUR
 * ================================================================
 * sprites.js exports ramp() and mix() but keeps its hex parser private, and a
 * rarity ladder needs desaturation, which mix() alone cannot express. These are
 * the three primitives the ladder needs and nothing more.
 */

function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

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

/* Perceptual grey, not the arithmetic mean. Desaturating iron through the mean
 * turns it faintly green, which is exactly the cheap look this file exists to
 * avoid. */
function desaturate(hex, amount) {
  const [r, g, b] = parseHex(hex);
  const y = r * 0.299 + g * 0.587 + b * 0.114;
  const t = clamp(amount, 0, 1);
  return toHex(r + (y - r) * t, g + (y - g) * t, b + (y - b) * t);
}

function lighten(hex, amount) {
  const [r, g, b] = parseHex(hex);
  const a = amount * 255;
  return toHex(r + a, g + a, b + a);
}

/* Additive screen blend. Used where light sits ON a material rather than
 * replacing it — the violet in an Epic blade, the red in a Mythic fracture. */
function screen(hex, glow, amount) {
  const A = parseHex(hex), B = parseHex(glow);
  const t = clamp(amount, 0, 1);
  return toHex(
    A[0] + (255 - A[0]) * (B[0] / 255) * t,
    A[1] + (255 - A[1]) * (B[1] / 255) * t,
    A[2] + (255 - A[2]) * (B[2] / 255) * t,
  );
}

/* ================================================================
 * MATERIALS
 * ================================================================
 * A shape names its material; the material names a base hex. Rarity then bends
 * that hex. Keeping the two apart is what lets a Legendary cloth robe and a
 * Legendary steel helm read as the same tier without being the same colour.
 */
const MATERIAL = {
  steel:   '#8b93a0',
  iron:    '#70767f',
  cloth:   '#5b4f6e',
  leather: '#6a4a34',
  wood:    '#6b4a2e',
  bone:    '#d6cfba',
  paper:   '#cdc199',
  glass:   '#7fb8d8',
  gold:    '#c99a42',
};

/* ================================================================
 * RARITY
 * ================================================================
 * The brief, restated as engineering:
 *
 *   COMMON     dull iron, muted, no ornament
 *   UNCOMMON   cleaner steel, a bronze fitting, slight sheen
 *   RARE       blued steel, silver inlay, a set gem, cool rim light
 *   EPIC       ornate, violet energy in the material, animated glint
 *   LEGENDARY  gold and blackened steel, runes, a burning aura, animated
 *   MYTHIC     the material is wrong somehow — voids, fracture lines, red light
 *
 * Each tier is expressed as (a) a material transform, (b) an ornament level
 * that adds structure to the grid, and (c) an aura that animates. Because all
 * three are driven off this table alone, an item authored next week inherits
 * the full ladder without anyone editing its shape.
 *
 * `colour` matches RARITIES in gauntlet/items.py exactly. If those drift, the
 * card border and the beam drift with them, which is worse than it sounds:
 * the player learns the colours before they learn the labels.
 */
const RARITY_DEF = {
  COMMON: {
    label: 'Common', colour: '#9b96b8',
    /* Pitted iron. Desaturated hard and pulled down, with the highlight step
     * suppressed so the surface never catches the light. */
    tint: '#2f3138', tintAmt: 0.30, desat: 0.52, lift: -0.05,
    trim: null, gem: null, rune: null, energy: null,
    ornament: 0, sheen: 0, aura: 'none', outlineTint: 0.06,
  },
  UNCOMMON: {
    label: 'Uncommon', colour: '#8fd07a',
    /* Cleaned up and slightly brighter, with one bronze fitting. */
    tint: '#3a4048', tintAmt: 0.12, desat: 0.18, lift: 0.03,
    trim: '#a9712f', gem: '#6f8a52', rune: null, energy: null,
    ornament: 1, sheen: 1, aura: 'none', outlineTint: 0.08,
  },
  RARE: {
    label: 'Rare', colour: '#7ec8ff',
    /* Blued steel: the metal itself is pulled toward cold blue, the inlay is
     * silver, and the rim light is cool rather than the default warm. */
    tint: '#31456e', tintAmt: 0.34, desat: 0.0, lift: 0.02,
    trim: '#c2ccdd', gem: '#7ec8ff', rune: null, energy: '#7ec8ff',
    ornament: 2, sheen: 2, aura: 'none', outlineTint: 0.12,
    rim: '#9fd8ff',
  },
  EPIC: {
    label: 'Epic', colour: '#c8a8ff',
    /* Violet energy IN the material, not on it: the base is screened with
     * violet before shading, so every ramp step carries the light. */
    tint: '#3b2c56', tintAmt: 0.44, desat: 0.10, lift: -0.02,
    glowInto: '#7b4fd0', glowAmt: 0.22,
    trim: '#9a7fd8', gem: '#c8a8ff', rune: '#c8a8ff', energy: '#c8a8ff',
    ornament: 3, sheen: 3, aura: 'glint', outlineTint: 0.14,
  },
  LEGENDARY: {
    label: 'Legendary', colour: '#e8c37d',
    /* Blackened steel and gold. The metal is crushed toward near-black so the
     * gold has somewhere to be bright, and embers drift off the silhouette. */
    tint: '#17141c', tintAmt: 0.52, desat: 0.22, lift: -0.04,
    glowInto: '#c0641e', glowAmt: 0.10,
    trim: '#e8c37d', gem: '#ffd98a', rune: '#ff9d4a', energy: '#ff9d4a',
    ornament: 4, sheen: 3, aura: 'ember', outlineTint: 0.16,
  },
  MYTHIC: {
    label: 'Mythic', colour: '#ff6a7a',
    /* The material is wrong. Voids are punched clean through the body, a
     * fracture runs corner to corner, and red light leaks out of both. This is
     * the only tier that removes matter rather than adding to it. */
    tint: '#180f1c', tintAmt: 0.62, desat: 0.30, lift: -0.06,
    glowInto: '#9a1030', glowAmt: 0.16,
    trim: '#ff6a7a', gem: '#ff4a5f', rune: '#ff6a7a', energy: '#ff6a7a',
    ornament: 5, sheen: 3, aura: 'void', outlineTint: 0.18,
  },
};

export const RARITY_KEYS = Object.keys(RARITY_DEF);
export const RARITY_COLOUR = Object.freeze(
  RARITY_KEYS.reduce((o, k) => { o[k] = RARITY_DEF[k].colour; return o; }, {}));

function normaliseRarity(rarity) {
  const key = String(rarity || 'COMMON').toUpperCase();
  return RARITY_DEF[key] ? key : 'COMMON';
}

const styleCache = new Map();

/* The rarity treatment, as a value. Everything downstream — palette, ornament,
 * corruption, animation, beam, burst, card, gear overlay — reads this and only
 * this, so adding a seventh tier means adding one entry to RARITY_DEF.
 */
export function rarityStyle(rarity) {
  const key = normaliseRarity(rarity);
  if (styleCache.has(key)) return styleCache.get(key);
  const d = RARITY_DEF[key];
  const animated = d.aura !== 'none';
  const style = Object.freeze({
    key,
    label: d.label,
    colour: d.colour,
    index: RARITY_KEYS.indexOf(key),
    ornament: d.ornament,
    sheen: d.sheen,
    aura: d.aura,
    animated,
    frames: animated ? ANIM_FRAMES : 1,
    /* Bend a material hex into this tier. Order matters: tint first so the
     * hue moves, desaturate second so the tint does not smear, lift last so
     * the value lands where the ramp expects it. */
    material(hex) {
      let c = mix(hex, d.tint, d.tintAmt);
      c = desaturate(c, d.desat);
      c = lighten(c, d.lift);
      if (d.glowInto) c = screen(c, d.glowInto, d.glowAmt);
      return c;
    },
    trimHex: d.trim,
    gemHex: d.gem,
    runeHex: d.rune,
    energyHex: d.energy || d.colour,
    rimHex: d.rim || null,
    outlineHex: mix('#07060c', d.colour, d.outlineTint),
    specHex: d.sheen >= 2 ? '#ffffff' : d.sheen === 1 ? '#e9edf4' : null,
    voidHex: '#0a0710',
  });
  styleCache.set(key, style);
  return style;
}

export const RARITY_STYLE = Object.freeze(
  RARITY_KEYS.reduce((o, k) => { o[k] = rarityStyle(k); return o; }, {}));

/* ---------------- palette ----------------
 * Glyph contract, shared by every grid in this file and by the gear overlays:
 *
 *   o O   outline, and the lit rim applyRim() derives from it
 *   B     undecided body mass; applyRim turns it into H L d D
 *   H L   body light2 / light1        d D   body shadow1 / shadow2
 *   s t u haft, hilt, wood, strap: base / light / shadow
 *   g G y trim fitting: base / light / shadow
 *   m M n gem: base / light / shadow
 *   c C v cloth: base / light / shadow
 *   w W   bone or paper, and the pure specular the glint writes
 *   r R   rune: base and its pulsed state
 *   e     void, punched through the material
 *   x X   leaking energy at a void edge, and its pulsed state
 *   p     liquid
 */
export function rarityPalette(material, rarity) {
  const style = rarityStyle(rarity);
  const baseHex = style.material(MATERIAL[material] || MATERIAL.steel);
  const body = ramp(baseHex);
  const haft = ramp(style.material(MATERIAL[material === 'cloth' ? 'leather' : 'wood']));
  const cloth = ramp(style.material(MATERIAL.cloth));
  /* With no trim colour the fittings collapse into the body, which is the
   * point: a Common item has fittings, they are simply the same dull iron. */
  const trim = ramp(style.trimHex || ramp(baseHex).shadow1);
  const gem = ramp(style.gemHex || body.shadow1);
  const spec = style.specHex || body.light1;
  return {
    o: style.outlineHex,
    O: style.rimHex || body.rim,
    B: body.base, b: body.base,
    H: style.sheen === 0 ? body.light1 : body.light2,
    L: body.light1, d: body.shadow1, D: body.shadow2,
    s: haft.base, t: haft.light1, u: haft.shadow1,
    g: trim.base, G: style.sheen === 0 ? trim.light1 : trim.light2, y: trim.shadow1,
    m: gem.base, M: gem.light2, n: gem.shadow1,
    c: cloth.base, C: cloth.light1, v: cloth.shadow1,
    w: style.material(MATERIAL.bone), W: spec,
    r: style.runeHex || body.light1,
    R: style.runeHex ? lighten(style.runeHex, 0.30) : body.light2,
    e: style.voidHex,
    x: style.energyHex,
    X: lighten(style.energyHex, 0.28),
    p: style.gemHex || cloth.base,
  };
}

/* ================================================================
 * GRID AUTHORING
 * ================================================================
 * Three helpers, because counting dots by hand is how a sprite ends up one
 * column off and nobody can see why. `mid` centres a run, `row` stamps runs at
 * explicit columns (later runs win, so a haft can be drawn over an axe beard),
 * and '.' inside a run means "leave what was there".
 */
function blank() { return '.'.repeat(N); }

function row(...runs) {
  const out = new Array(N).fill('.');
  for (let i = 0; i < runs.length; i += 2) {
    const x = runs[i] | 0, s = String(runs[i + 1]);
    for (let k = 0; k < s.length; k++) {
      const ch = s[k], px = x + k;
      if (ch === '.' || px < 0 || px >= N) continue;
      out[px] = ch;
    }
  }
  return out.join('');
}

function mid(s) { return row(Math.floor((N - s.length) / 2), s); }

function rep(ch, n) { return ch.repeat(n); }

/* ================================================================
 * BASE SHAPES
 * ================================================================
 * Thirty-two authored silhouettes. Everything is drawn upright and centred for
 * one unglamorous reason: the ornament pass adds fittings as horizontal bands,
 * and a band across an upright blade reads as an inlay while a band across a
 * diagonal one reads as a mistake. Upright also survives being shown at 24px in
 * an inventory list, which is where most of these will actually be seen.
 *
 * `mat` picks the material the rarity ladder bends. `gem` and `gem2` are where
 * a set stone belongs once the tier is high enough to have earned one; they are
 * per-shape because a gem placed by an algorithm always lands in the wrong hole.
 */
const SHAPES = {
  /* ---- blades ---- */
  sword: {
    mat: 'steel', gem: [11, 15],
    grid: [
      blank(), mid('oo'), mid('oBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('o' + rep('g', 12) + 'o'),
      mid('o' + rep('g', 8) + 'o'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('oggggo'), mid('oggggo'), mid('oooo'),
    ],
  },
  sabers: {
    /* Crossed, because a pair has to read as a pair from the silhouette alone
     * and two parallel blades read as one thick blade. */
    mat: 'steel', gem: [5, 18], gem2: [17, 18],
    grid: [
      blank(), blank(),
      row(4, 'oo', 18, 'oo'),
      row(3, 'oBBo', 18, 'oBBo'),
      row(4, 'oBBo', 17, 'oBBo'),
      row(5, 'oBBo', 16, 'oBBo'),
      row(6, 'oBBo', 15, 'oBBo'),
      row(7, 'oBBo', 14, 'oBBo'),
      row(8, 'oBBo', 13, 'oBBo'),
      row(9, 'oBBoBBo'),
      row(10, 'oBBBo'),
      row(10, 'oBBBo'),
      row(9, 'oBBoBBo'),
      row(8, 'oBBo', 13, 'oBBo'),
      row(7, 'oBBo', 14, 'oBBo'),
      row(6, 'oBBo', 15, 'oBBo'),
      row(5, 'oBBo', 16, 'oBBo'),
      row(4, 'oBBo', 17, 'oBBo'),
      row(3, 'oggo', 17, 'oggo'),
      row(4, 'oso', 17, 'oso'),
      row(4, 'oso', 17, 'oso'),
      row(4, 'ogo', 17, 'ogo'),
      row(5, 'o', 18, 'o'),
      blank(),
    ],
  },
  dagger: {
    mat: 'steel', gem: [11, 15],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('oo'), mid('oBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBo'),
      mid('o' + rep('g', 8) + 'o'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('oggggo'), mid('oggo'),
      blank(), blank(),
    ],
  },
  /* ---- polearms and hafts ---- */
  spear: {
    mat: 'steel', gem: [11, 7],
    grid: [
      mid('oo'), mid('oBBo'), mid('oBBBBo'),
      mid('oBBBBBBo'), mid('oBBBBBBo'),
      mid('oBBBBo'), mid('oBBo'), mid('oggo'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('oo'),
    ],
  },
  lance: {
    mat: 'steel', gem: [11, 9],
    grid: [
      mid('oo'), mid('oBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBBBBBo'), mid('oBBBBBBo'),
      mid('oBBBBBBBBo'), mid('oBBBBBBBBo'),
      mid('oBBBBBBBBBBo'),
      mid('o' + rep('g', 12) + 'o'),
      mid('o' + rep('g', 10) + 'o'),
      mid('oBBBBBBBBo'),
      mid('osssso'), mid('osssso'), mid('osssso'), mid('osssso'),
      mid('osssso'), mid('osssso'), mid('osssso'), mid('osssso'),
      mid('osssso'), mid('osssso'),
      mid('oggggo'), mid('oooo'),
    ],
  },
  staff: {
    mat: 'wood', gem: [10, 3],
    grid: [
      blank(),
      mid('oggo'),
      mid('ogmmgo'),
      row(6, 'og', 8, 'ogmMMmgo', 16, 'go'),
      row(6, 'og', 8, 'ogmmmmgo', 16, 'go'),
      mid('ogmmmmgo'),
      mid('ogmmgo'),
      mid('oggo'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'),
      mid('oggo'), mid('oo'),
    ],
  },
  axe: {
    mat: 'steel', gem: [16, 6],
    grid: [
      mid('oo'),
      mid('osso'),
      row(13, 'oBBBBo', 10, 'osso'),
      row(13, 'oBBBBBBo', 10, 'osso'),
      row(7, 'oBBBo', 13, 'oBBBBBBBo', 10, 'osso'),
      row(6, 'oBBBBo', 13, 'oBBBBBBBBo', 10, 'osso'),
      row(6, 'oBBBBo', 13, 'oBBBBBBBBo', 10, 'osso'),
      row(7, 'oBBBo', 13, 'oBBBBBBBo', 10, 'osso'),
      row(13, 'oBBBBBBo', 10, 'osso'),
      row(13, 'oBBBBo', 10, 'osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('oggo'), mid('oo'),
    ],
  },
  hammer: {
    mat: 'steel', gem: [11, 6],
    grid: [
      blank(),
      row(6, rep('o', 12)),
      row(5, 'o' + rep('B', 12) + 'o'),
      row(5, 'o' + rep('B', 12) + 'o'),
      row(5, 'oBBggBBBBggBBo'),
      row(5, 'oBBggBBBBggBBo'),
      row(5, 'o' + rep('B', 12) + 'o'),
      row(5, 'o' + rep('B', 12) + 'o'),
      row(6, 'o' + rep('B', 10) + 'o'),
      row(7, rep('o', 10)),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('oggo'), mid('oo'),
    ],
  },
  bow: {
    /* Limbs bulge left, string runs straight down the right. The asymmetry is
     * what makes it a bow rather than a bracket. */
    mat: 'wood', gem: [4, 10],
    grid: [
      blank(),
      row(9, 'ogo', 13, 'o'),
      row(8, 'osso', 13, 'w'),
      row(7, 'osso', 13, 'w'),
      row(6, 'osso', 13, 'w'),
      row(5, 'osso', 13, 'w'),
      row(5, 'osso', 13, 'w'),
      row(4, 'osso', 13, 'w'),
      row(4, 'osso', 13, 'w'),
      row(4, 'ogggo', 13, 'w'),
      row(4, 'ogggo', 13, 'w'),
      row(4, 'ogggo', 13, 'w'),
      row(4, 'ogggo', 13, 'w'),
      row(4, 'ogggo', 13, 'w'),
      row(4, 'osso', 13, 'w'),
      row(4, 'osso', 13, 'w'),
      row(5, 'osso', 13, 'w'),
      row(5, 'osso', 13, 'w'),
      row(6, 'osso', 13, 'w'),
      row(7, 'osso', 13, 'w'),
      row(8, 'osso', 13, 'w'),
      row(9, 'ogo', 13, 'o'),
      blank(), blank(),
    ],
  },

  /* ---- offhand ---- */
  shield: {
    /* A heater face with a raised central boss. The boss is authored rather
     * than left to the ornament pass because a Common shield still needs
     * something inside its outline; a flat 14x14 slab reads as a sign. */
    mat: 'steel', gem: [11, 9],
    grid: [
      blank(), blank(),
      mid(rep('o', 16)),
      mid('o' + rep('B', 14) + 'o'),
      row(4, 'o' + rep('B', 14) + 'o', 6, 'd', 17, 'd'),
      mid('o' + rep('B', 14) + 'o'),
      row(4, 'o' + rep('B', 14) + 'o', 9, 'oggo'),
      row(4, 'o' + rep('B', 14) + 'o', 8, 'oggggo'),
      row(4, 'o' + rep('B', 14) + 'o', 8, 'ogmmgo'),
      row(5, 'o' + rep('B', 12) + 'o', 8, 'oggggo'),
      row(5, 'o' + rep('B', 12) + 'o', 9, 'oggo'),
      mid('o' + rep('B', 10) + 'o'),
      row(6, 'o' + rep('B', 10) + 'o', 8, 'd', 15, 'd'),
      mid('o' + rep('B', 8) + 'o'),
      mid('o' + rep('B', 8) + 'o'),
      mid('o' + rep('B', 6) + 'o'),
      mid('oBBBBo'), mid('oBBo'), mid('oo'),
      blank(), blank(), blank(), blank(), blank(),
    ],
  },
  tome: {
    mat: 'paper', gem: [11, 8],
    grid: [
      blank(), blank(), blank(), blank(), blank(),
      row(3, 'o' + rep('c', 16) + 'o', 4, 'vv'),
      row(3, 'o' + rep('c', 16) + 'o', 4, 'vv'),
      row(3, 'o' + rep('c', 5) + rep('g', 6) + rep('c', 5) + 'o', 4, 'vv'),
      row(3, 'o' + rep('c', 5) + 'g' + rep('m', 4) + 'g' + rep('c', 5) + 'o', 4, 'vv', 20, 'g'),
      row(3, 'o' + rep('c', 5) + rep('g', 6) + rep('c', 5) + 'o', 4, 'vv'),
      row(3, 'o' + rep('c', 16) + 'o', 4, 'vv'),
      row(3, 'o' + rep('c', 16) + 'o', 4, 'vv'),
      row(3, 'o' + rep('c', 16) + 'o', 4, 'vv', 20, 'g'),
      row(3, 'o' + rep('c', 16) + 'o', 4, 'vv'),
      row(3, 'o' + rep('w', 16) + 'o', 4, 'vv'),
      row(3, 'o' + rep('w', 16) + 'o', 4, 'vv'),
      row(3, rep('o', 18)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  scroll: {
    mat: 'paper', gem: [11, 10],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('w', 14) + 'o'),
      mid('o' + rep('w', 14) + 'o'),
      mid('ow' + rep('u', 12) + 'wo'),
      mid('o' + rep('w', 14) + 'o'),
      mid('o' + rep('g', 16) + 'o'),
      mid('o' + rep('g', 16) + 'o'),
      mid('o' + rep('w', 14) + 'o'),
      mid('ow' + rep('u', 12) + 'wo'),
      mid('o' + rep('w', 14) + 'o'),
      mid('ow' + rep('u', 12) + 'wo'),
      mid('o' + rep('w', 14) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      blank(), blank(), blank(), blank(), blank(),
    ],
  },
  /* ---- head ---- */
  helm: {
    mat: 'steel', gem: [11, 5],
    grid: [
      blank(), mid('oggo'), mid('oggggo'),
      mid('o' + rep('B', 8) + 'o'),
      mid('o' + rep('B', 10) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('oBeeeBBBBeeeBo'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('oBBBeeeeeeBBBo'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 10) + 'o'),
      mid('o' + rep('B', 8) + 'o'),
      mid(rep('o', 8)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  crown: {
    mat: 'gold', gem: [7, 13], gem2: [15, 13],
    grid: [
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
      row(11, 'oo'),
      row(10, 'oggo'),
      row(5, 'oo', 17, 'oo', 10, 'oggo'),
      row(4, 'oggo', 16, 'oggo', 10, 'oggo'),
      row(4, 'ogggogggggogggo'),
      row(3, 'o' + rep('g', 16) + 'o'),
      row(3, 'ogggmgggmmgggmgggo'),
      row(3, 'o' + rep('g', 16) + 'o'),
      row(3, 'o' + rep('y', 16) + 'o'),
      row(3, rep('o', 18)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  hood: {
    mat: 'cloth', gem: [11, 4],
    grid: [
      blank(), blank(), blank(),
      mid('o' + rep('C', 6) + 'o'),
      mid('o' + rep('C', 8) + 'o'),
      mid('o' + rep('c', 10) + 'o'),
      mid('o' + rep('c', 10) + 'o'),
      mid('occceeeeccco'),
      mid('occeeeeeecco'),
      mid('occeeeeeecco'),
      mid('occceeeeccco'),
      mid('o' + rep('c', 10) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('v', 14) + 'o'),
      mid(rep('o', 16)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  lens: {
    mat: 'glass', gem: [11, 6],
    grid: [
      blank(), blank(), blank(), blank(), blank(),
      mid(rep('o', 12)),
      mid('o' + rep('g', 10) + 'o'),
      mid('og' + rep('B', 8) + 'go'),
      row(6, 'og' + rep('B', 8) + 'go', 8, 'WW'),
      row(6, 'og' + rep('B', 8) + 'go', 8, 'W'),
      mid('og' + rep('B', 8) + 'go'),
      row(6, 'og' + rep('B', 8) + 'go', 18, 'g'),
      mid('og' + rep('B', 8) + 'go'),
      mid('og' + rep('B', 8) + 'go'),
      mid('o' + rep('g', 10) + 'o'),
      mid(rep('o', 12)),
      row(18, 'g'), row(18, 'g'), row(19, 'g'), row(19, 'gg'),
      blank(), blank(), blank(), blank(),
    ],
  },
  /* ---- chest ---- */
  plate: {
    mat: 'steel', gem: [11, 9],
    grid: [
      blank(), blank(), blank(),
      mid('oBBBBo'),
      row(2, 'oBBBo', 16, 'oBBBo', 9, 'oBBBBo'),
      mid('o' + rep('B', 18) + 'o'),
      mid('o' + rep('B', 18) + 'o'),
      mid('o' + rep('B', 16) + 'o'),
      mid('o' + rep('B', 16) + 'o'),
      mid('o' + rep('B', 14) + 'o'),
      mid('o' + rep('B', 6) + 'gg' + rep('B', 6) + 'o'),
      mid('o' + rep('B', 6) + 'gg' + rep('B', 6) + 'o'),
      mid('o' + rep('B', 6) + 'gg' + rep('B', 6) + 'o'),
      mid('o' + rep('B', 14) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 12) + 'o'),
      mid('o' + rep('B', 10) + 'o'),
      mid(rep('o', 12)),
      mid('o' + rep('B', 10) + 'o'),
      mid(rep('o', 12)),
      blank(), blank(), blank(), blank(),
    ],
  },
  chest: {
    mat: 'cloth', gem: [11, 12],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('o' + rep('c', 6) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('g', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('v', 12) + 'o'),
      mid(rep('o', 14)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  robe: {
    mat: 'cloth', gem: [11, 8],
    grid: [
      blank(), blank(),
      mid('o' + rep('C', 4) + 'o'),
      mid('o' + rep('C', 6) + 'o'),
      mid('o' + rep('c', 8) + 'o'),
      mid('o' + rep('c', 8) + 'o'),
      mid('o' + rep('c', 10) + 'o'),
      mid('o' + rep('c', 10) + 'o'),
      mid('o' + rep('c', 3) + rep('g', 4) + rep('c', 3) + 'o'),
      mid('o' + rep('c', 10) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('v', 16) + 'o'),
      mid('o' + rep('v', 16) + 'o'),
      mid(rep('o', 18)),
      blank(), blank(), blank(),
    ],
  },
  cloak: {
    mat: 'cloth', gem: [11, 4],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('o' + rep('g', 6) + 'o'),
      mid('o' + rep('c', 8) + 'o'),
      mid('o' + rep('c', 10) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 12) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 14) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('c', 16) + 'o'),
      mid('o' + rep('v', 16) + 'o'),
      mid(rep('o', 18)),
      blank(), blank(), blank(),
    ],
  },

  /* ---- hands and feet: authored as a PAIR, because one glove is a prop and
   * two gloves are equipment ---- */
  gauntlets: {
    mat: 'steel', gem: [4, 8], gem2: [17, 8],
    grid: [
      blank(), blank(), blank(), blank(), blank(),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(2, 'o' + rep('B', 5) + 'o', 14, 'o' + rep('B', 5) + 'o'),
      row(2, 'o' + rep('B', 5) + 'o', 14, 'o' + rep('B', 5) + 'o'),
      row(2, 'oBggBBo', 14, 'oBBggBo'),
      row(2, 'o' + rep('B', 5) + 'o', 14, 'o' + rep('B', 5) + 'o'),
      row(2, 'o' + rep('B', 5) + 'o', 14, 'o' + rep('B', 5) + 'o', 8, 'oBo', 12, 'oBo'),
      row(2, 'o' + rep('B', 5) + 'o', 14, 'o' + rep('B', 5) + 'o', 8, 'oBo', 12, 'oBo'),
      row(1, 'o' + rep('B', 7) + 'o', 13, 'o' + rep('B', 7) + 'o'),
      row(1, 'o' + rep('B', 7) + 'o', 13, 'o' + rep('B', 7) + 'o'),
      row(1, rep('o', 9), 13, rep('o', 9)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  wraps: {
    mat: 'cloth', gem: [4, 7], gem2: [17, 7],
    grid: [
      blank(), blank(), blank(), blank(), blank(),
      row(3, 'occco', 15, 'occco'),
      row(2, 'o' + rep('c', 5) + 'o', 14, 'o' + rep('c', 5) + 'o'),
      row(2, 'o' + rep('C', 5) + 'o', 14, 'o' + rep('C', 5) + 'o'),
      row(2, 'o' + rep('c', 5) + 'o', 14, 'o' + rep('c', 5) + 'o'),
      row(2, 'o' + rep('C', 5) + 'o', 14, 'o' + rep('C', 5) + 'o'),
      row(2, 'o' + rep('c', 5) + 'o', 14, 'o' + rep('c', 5) + 'o', 8, 'oco', 12, 'oco'),
      row(2, 'o' + rep('C', 5) + 'o', 14, 'o' + rep('C', 5) + 'o', 8, 'oco', 12, 'oco'),
      row(2, 'o' + rep('c', 5) + 'o', 14, 'o' + rep('c', 5) + 'o'),
      row(2, 'o' + rep('v', 5) + 'o', 14, 'o' + rep('v', 5) + 'o'),
      row(2, rep('o', 7), 14, rep('o', 7)),
      row(3, 'oco', 16, 'oco'),
      row(3, 'oco', 16, 'oco'),
      row(4, 'ovo', 15, 'ovo'),
      row(4, 'oo', 16, 'oo'),
      blank(), blank(), blank(), blank(), blank(),
    ],
  },
  boots: {
    mat: 'leather', gem: [4, 6], gem2: [17, 6],
    grid: [
      blank(), blank(), blank(), blank(), blank(), blank(),
      row(2, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(2, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(1, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(1, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(1, rep('o', 8), 14, rep('o', 8)),
      blank(), blank(), blank(), blank(), blank(),
    ],
  },
  greaves: {
    mat: 'steel', gem: [4, 6], gem2: [17, 6],
    grid: [
      blank(), blank(), blank(), blank(), blank(),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(2, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(2, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(2, 'oBBggBBo', 14, 'oBBggBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(3, 'oBBBBo', 15, 'oBBBBo'),
      row(2, 'o' + rep('B', 6) + 'o', 14, 'o' + rep('B', 6) + 'o'),
      row(2, rep('o', 8), 14, rep('o', 8)),
      blank(), blank(), blank(), blank(), blank(),
    ],
  },
  /* ---- accessories ---- */
  ring: {
    mat: 'gold', gem: [11, 4],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('ommo'),
      mid('o' + rep('m', 4) + 'o'),
      mid('o' + rep('g', 6) + 'o'),
      mid('o' + rep('g', 8) + 'o'),
      row(6, 'oggo', 14, 'oggo'),
      row(5, 'oggo', 15, 'oggo'),
      row(5, 'oggo', 15, 'oggo'),
      row(5, 'oggo', 15, 'oggo'),
      row(5, 'oggo', 15, 'oggo'),
      row(6, 'oggo', 14, 'oggo'),
      mid('o' + rep('g', 6) + 'o'),
      mid('o' + rep('g', 4) + 'o'),
      mid(rep('o', 6)),
      blank(), blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  amulet: {
    mat: 'gold', gem: [11, 12],
    grid: [
      blank(), blank(),
      row(7, 'o', 16, 'o'),
      row(7, 'g', 16, 'g'),
      row(8, 'g', 15, 'g'),
      row(8, 'g', 15, 'g'),
      row(9, 'g', 14, 'g'),
      row(9, 'g', 14, 'g'),
      row(10, 'g', 13, 'g'),
      mid('oggggo'),
      mid('o' + rep('g', 8) + 'o'),
      mid('og' + rep('m', 6) + 'go'),
      mid('og' + rep('m', 6) + 'go'),
      mid('og' + rep('m', 6) + 'go'),
      mid('o' + rep('g', 8) + 'o'),
      mid('o' + rep('g', 6) + 'o'),
      mid('o' + rep('g', 4) + 'o'),
      mid('oggo'),
      mid('oo'),
      blank(), blank(), blank(), blank(), blank(),
    ],
  },
  orb: {
    mat: 'glass', gem: [11, 8],
    grid: [
      blank(), blank(), blank(),
      mid(rep('o', 8)),
      mid('o' + rep('m', 8) + 'o'),
      mid('o' + rep('m', 10) + 'o'),
      row(5, 'o' + rep('m', 12) + 'o', 8, 'MM'),
      row(5, 'o' + rep('m', 12) + 'o', 8, 'M'),
      mid('o' + rep('m', 12) + 'o'),
      mid('o' + rep('m', 12) + 'o'),
      mid('o' + rep('m', 12) + 'o'),
      mid('o' + rep('m', 12) + 'o'),
      mid('o' + rep('m', 12) + 'o'),
      mid('o' + rep('m', 10) + 'o'),
      mid('o' + rep('m', 8) + 'o'),
      mid(rep('o', 8)),
      mid('o' + rep('g', 6) + 'o'),
      mid('o' + rep('g', 4) + 'o'),
      mid('o' + rep('g', 8) + 'o'),
      mid('o' + rep('g', 10) + 'o'),
      mid(rep('o', 12)),
      blank(), blank(), blank(),
    ],
  },
  relic: {
    /* The generic sigil. Ten catalogue entries ship with icon="relic", so this
     * one has to hold up as a real object rather than a placeholder. */
    mat: 'gold', gem: [8, 7],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('oo'),
      mid('ommo'),
      mid('o' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 6) + 'o'),
      row(7, 'o' + rep('m', 8) + 'o', 3, 'm'),
      mid('o' + rep('m', 4) + 'ee' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 4) + 'ee' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 4) + 'ee' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 10) + 'o'),
      row(7, 'o' + rep('m', 8) + 'o', 20, 'm'),
      mid('o' + rep('m', 6) + 'o'),
      mid('o' + rep('m', 4) + 'o'),
      mid('ommo'),
      mid('oo'),
      blank(), blank(), blank(), blank(), blank(), blank(),
    ],
  },
  potion: {
    mat: 'glass', gem: [11, 4],
    grid: [
      blank(), blank(), blank(),
      mid('oggo'),
      mid('o' + rep('g', 4) + 'o'),
      mid('o' + rep('B', 4) + 'o'),
      mid('o' + rep('B', 4) + 'o'),
      mid('o' + rep('B', 6) + 'o'),
      mid('o' + rep('B', 8) + 'o'),
      mid('o' + rep('B', 10) + 'o'),
      mid('o' + rep('B', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 10) + 'o'),
      mid('o' + rep('p', 8) + 'o'),
      mid(rep('o', 10)),
      blank(), blank(), blank(), blank(),
    ],
  },
  key: {
    mat: 'gold', gem: [11, 9],
    grid: [
      blank(), blank(), blank(),
      mid(rep('o', 8)),
      mid('o' + rep('g', 6) + 'o'),
      mid('oggeeggo'),
      mid('ogeeeego'),
      mid('oggeeggo'),
      mid('o' + rep('g', 6) + 'o'),
      mid('oggo'), mid('oggo'), mid('oggo'), mid('oggo'),
      mid('oggo'), mid('oggo'), mid('oggo'), mid('oggo'),
      row(10, 'oggo', 13, 'ggo'),
      mid('oggo'),
      row(10, 'oggo', 13, 'ggo'),
      mid('oggo'),
      mid(rep('o', 4)),
      blank(), blank(),
    ],
  },
  hourglass: {
    mat: 'glass', gem: [11, 10],
    grid: [
      blank(), blank(), blank(), blank(),
      mid('o' + rep('g', 14) + 'o'),
      mid('o' + rep('g', 14) + 'o'),
      row(4, 'og', 18, 'go', 6, 'o' + rep('p', 10) + 'o'),
      row(4, 'og', 18, 'go', 7, 'o' + rep('p', 8) + 'o'),
      row(4, 'og', 18, 'go', 8, 'o' + rep('p', 6) + 'o'),
      row(4, 'og', 18, 'go', 9, 'o' + rep('p', 4) + 'o'),
      row(4, 'og', 18, 'go', 10, 'oppo'),
      row(4, 'og', 18, 'go', 10, 'oppo'),
      row(4, 'og', 18, 'go', 10, 'oppo'),
      row(4, 'og', 18, 'go', 9, 'o' + rep('w', 4) + 'o'),
      row(4, 'og', 18, 'go', 8, 'o' + rep('w', 6) + 'o'),
      row(4, 'og', 18, 'go', 7, 'o' + rep('w', 8) + 'o'),
      row(4, 'og', 18, 'go', 6, 'o' + rep('p', 10) + 'o'),
      row(4, 'og', 18, 'go', 6, 'o' + rep('p', 10) + 'o'),
      mid('o' + rep('g', 14) + 'o'),
      mid('o' + rep('g', 14) + 'o'),
      blank(), blank(), blank(), blank(),
    ],
  },
  feather: {
    mat: 'bone', gem: [11, 10],
    grid: [
      blank(), blank(), blank(),
      row(11, 'os'),
      row(10, 'owso'),
      row(9, 'owwso'),
      row(8, 'owwwso'),
      row(7, 'owwwwso'),
      row(7, 'owwwwsWo'),
      row(6, 'owwwwwsWo'),
      row(6, 'owwwwwsWo'),
      row(6, 'owwwwwsWo'),
      row(7, 'owwwwsWo'),
      row(7, 'owwwwso'),
      row(8, 'owwwso'),
      row(9, 'owwso'),
      row(10, 'owso'),
      row(11, 'oso'),
      row(11, 'oso'),
      row(11, 'oso'),
      row(11, 'ooo'),
      blank(), blank(), blank(),
    ],
  },
};

export const SHAPE_KEYS = Object.keys(SHAPES);

/* ================================================================
 * THE RARITY PIPELINE
 * ================================================================
 * ornament -> applyRim -> corrupt -> animate. Each stage takes a grid and
 * returns a grid, which is what makes the ladder extensible: a shape authored
 * next month gets all four stages without knowing they exist.
 */

const BODY = 'B';
/* Glyphs a glint can travel across. Cloth does not catch a specular highlight,
 * and a glint that crosses a robe reads as a rendering bug — cloth items get
 * their sheen off their metal fittings instead, which is how cloth behaves. */
const HARD = new Set(['B', 'H', 'L', 'd', 'D', 'b', 'g', 'G', 'y', 'm', 'M', 'n', 'w']);

/* Grids in this file are 24 wide, but the gear overlays are 6, 10 or 14, and
 * every stage below runs on both. Width therefore comes from the grid, never
 * from N. */
function toCells(grid) {
  const w = Math.max(...grid.map(r => r.length));
  return grid.map(r => r.padEnd(w, '.').split(''));
}
function toRows(cells) { return cells.map(r => r.join('')); }
function widthOf(cells) { return cells[0] ? cells[0].length : 0; }

/* Material a fitting may be banded across, and material a fitting is made of.
 * A band over steel is trim; a band over trim is a set inlay. Without that
 * flip a gold ring at Legendary is a gold ring with gold on it. */
const BANDABLE = new Set(['B', 'c', 'C', 'v', 's', 't', 'u', 'w', 'g', 'G', 'y', 'm', 'M', 'n', 'p']);
const TRIMMY = new Set(['g', 'G', 'y']);
const RUNEABLE = new Set(['B', 'c', 'C', 'g', 'w', 's', 'p']);

/* Vertical extent of the body mass, used to place fittings as a fraction of
 * the object rather than at fixed rows. A band 30% down a boot and a band 30%
 * down a spear are both in the right place; row 7 is only right for one. */
function bodyExtent(cells, glyphs) {
  let top = -1, bot = -1;
  const w = widthOf(cells);
  for (let y = 0; y < cells.length; y++) {
    for (let x = 0; x < w; x++) {
      if (!glyphs.has(cells[y][x])) continue;
      if (top < 0) top = y;
      bot = y;
      break;
    }
  }
  return [top, bot];
}

/* One horizontal fitting, drawn as a band across whatever material it crosses.
 * The run ends are lit and shaded by hand because applyRim only knows about
 * body mass, and an unshaded band reads as a sticker. */
function band(cells, y) {
  if (y < 0 || y >= cells.length) return 0;
  const w = widthOf(cells);
  const runs = [];
  let start = -1;
  for (let x = 0; x <= w; x++) {
    const solid = x < w && BANDABLE.has(cells[y][x]);
    if (solid && start < 0) start = x;
    if (!solid && start >= 0) { runs.push([start, x - 1]); start = -1; }
  }
  for (const [a, b] of runs) {
    /* A single-pixel run still gets a fitting. A chain link and the toe of a
     * hand wrap are one pixel wide, and skipping them was how an Uncommon
     * amulet ended up identical to a Common one. */
    const inlay = TRIMMY.has(cells[y][a]);
    const [base, hi, lo] = inlay ? ['m', 'M', 'n'] : ['g', 'G', 'y'];
    for (let x = a; x <= b; x++) cells[y][x] = base;
    cells[y][a] = hi;
    if (b > a) cells[y][b] = lo;
  }
  return runs.length;
}

/* A 2x2 set stone at an authored anchor. Skipped rather than forced if the
 * anchor is over empty space, which happens when a shape is shared by slots. */
function setStone(cells, anchor) {
  if (!anchor) return;
  const [x, y] = anchor;
  const w = widthOf(cells);
  if (y < 0 || y + 1 >= cells.length || x < 0 || x + 1 >= w) return;
  if (cells[y][x] === '.' || cells[y][x] === 'o') return;
  cells[y][x] = 'M'; cells[y][x + 1] = 'm';
  cells[y + 1][x] = 'm'; cells[y + 1][x + 1] = 'n';
}

/* Runes are cut down the spine of the object, every third row. On a blade that
 * is a runic fuller; on a helm it is a brow inscription; on a ring it is
 * nothing at all, because the spine is the hole, and that is fine. */
function cutRunes(cells, top, bot) {
  const w = widthOf(cells);
  const cx = Math.floor(w / 2) - 1;
  for (let y = top + 2; y <= bot - 2; y += 3) {
    for (const x of [cx, cx + 1]) {
      if (cells[y] && RUNEABLE.has(cells[y][x])) cells[y][x] = 'r';
    }
  }
}

/* Gold filigree: outline pixels beside a fitting become trim, so the ornament
 * wraps the silhouette instead of sitting inside it. Legendary and above only,
 * because at lower tiers a gold outline reads as a selection highlight. */
function gildOutline(cells, rows) {
  const w = widthOf(cells);
  for (const y of rows) {
    for (const dy of [-1, 0, 1]) {
      const r = cells[y + dy];
      if (!r) continue;
      for (let x = 0; x < w; x++) if (r[x] === 'o') r[x] = 'y';
    }
  }
}

/* Ornament level, as authored in RARITY_DEF:
 *   0  nothing. Common is raw material and the shape has to carry itself.
 *   1  one bronze fitting.
 *   2  two fittings and a set stone.
 *   3  three fittings, a stone, and runes cut into the spine.
 *   4  all of the above plus a second stone and gilded outlines.
 *   5  as 4; corruption is applied separately, after the rim pass.
 */
function ornament(grid, shape, style, seed) {
  if (style.ornament <= 0) return grid;
  const cells = toCells(grid);
  const [top, bot] = bodyExtent(cells, BANDABLE);
  if (top < 0) return grid;
  const rand = rng(seed || 1);
  const span = Math.max(1, bot - top);
  const fracs = [0.28, 0.62, 0.86].slice(0, Math.min(3, style.ornament));
  const rows = [];
  for (const f of fracs) {
    /* A pixel of jitter per item, so two Rare boots from the same shape are
     * not the same object twice. */
    const y = Math.round(top + span * f) + (rand() < 0.5 ? 0 : 1);
    /* Shapes with gaps in them — a pair of boots, a chain, a ring — have rows
     * that hold no material at all. Walk outward from the ideal row until a
     * fitting lands, rather than silently dropping it and leaving two tiers
     * looking identical. */
    for (const d of [0, 1, -1, 2, -2, 3, -3]) {
      const yy = Math.max(top, Math.min(bot, y + d));
      if (rows.includes(yy)) continue;
      if (band(cells, yy) > 0) { rows.push(yy); break; }
    }
  }
  if (style.ornament >= 2) setStone(cells, shape.gem);
  if (style.ornament >= 3) cutRunes(cells, top, bot);
  if (style.ornament >= 4) { setStone(cells, shape.gem2); gildOutline(cells, rows); }
  return toRows(cells);
}

/* Mythic only. Matter is removed: voids punched through the body with energy
 * leaking from the edges, and one fracture running the diagonal. Applied after
 * applyRim so the surrounding shading survives and the holes read as holes
 * rather than as unpainted pixels.
 */
const CORRUPTIBLE = new Set(['B', 'H', 'L', 'd', 'D', 'b', 'c', 'C', 'v',
                             's', 't', 'u', 'w', 'm', 'M', 'n', 'g', 'G', 'y', 'p']);

function corrupt(grid, style, seed) {
  if (style.aura !== 'void') return grid;
  const cells = toCells(grid);
  const w = widthOf(cells), h = cells.length;
  const punch = (x, y) => {
    const r = cells[y];
    if (!r || x < 0 || x >= w || !CORRUPTIBLE.has(r[x])) return false;
    r[x] = 'e';
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const q = cells[y + dy];
      if (q && CORRUPTIBLE.has(q[x + dx])) q[x + dx] = 'x';
    }
    return true;
  };
  const rand = rng((seed || 1) ^ 0x5bf03635);
  /* Six voids, rejection-sampled onto actual material so the holes are in the
   * object and not floating beside it. */
  let placed = 0;
  for (let tries = 0; tries < 160 && placed < 6; tries++) {
    if (punch(Math.floor(rand() * w), Math.floor(rand() * h))) placed++;
  }
  /* The fracture. A single stepped diagonal, offset per item. */
  const off = Math.floor(rand() * 6) - 3;
  for (let y = 1; y < h - 1; y++) {
    const x = Math.round(y * 0.75) + off + 3;
    const r = cells[y];
    if (!r || x < 0 || x >= w) continue;
    if (CORRUPTIBLE.has(r[x])) { r[x] = 'e'; if (CORRUPTIBLE.has(r[x + 1])) r[x + 1] = 'x'; }
  }
  return toRows(cells);
}

/* Animation. Epic and above only, six frames, all cached.
 *
 *   glint  a specular band travelling up the diagonal of the object
 *   ember  a glint plus embers lifting off the silhouette
 *   void   a glint plus the leaked energy breathing
 *
 * A frame that differs only in brightness is not a frame — sprites.js says so
 * about characters, and it is just as true here, which is why the glint MOVES
 * and the embers CHANGE POSITION rather than fading in place.
 */
function animate(grid, style, frame, seed) {
  if (!style.animated) return grid;
  const cells = toCells(grid);
  const w = widthOf(cells), h = cells.length;
  const frames = style.frames;
  const f = ((frame % frames) + frames) % frames;
  const rand = rng((seed || 1) ^ 0x9e3779b9);

  /* The glint sweeps u = x - y + h, so it travels up and to the right across
   * an upright object: the direction a hand moves a blade into the light. The
   * sweep is sized off the grid, which is why it works on a 6x12 weapon
   * overlay as well as on a 24x24 icon. */
  let uMin = Infinity, uMax = -Infinity;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!HARD.has(cells[y][x])) continue;
      const u = x - y + h;
      if (u < uMin) uMin = u;
      if (u > uMax) uMax = u;
    }
  }
  /* Fitted to the object rather than to the box. Sweeping a fixed range left
   * the glint off the edge of a small or off-centre shape for half the cycle,
   * which produced six frames of which only three differed. */
  if (uMin <= uMax) {
    const p = uMin - 1.2 + ((f + 0.5) / frames) * ((uMax - uMin) + 2.4);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const ch = cells[y][x];
        if (!HARD.has(ch)) continue;
        const dist = Math.abs((x - y + h) - p);
        if (dist <= 0.8) cells[y][x] = 'W';
        else if (dist <= 2.0 && (ch === 'B' || ch === 'L' || ch === 'd')) cells[y][x] = 'H';
      }
    }
  }

  /* Runes pulse along their own length rather than all at once, so the
   * inscription reads as being run through rather than switched on. */
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (cells[y][x] !== 'r') continue;
      if (((f + (y >> 1)) % frames) < frames / 2) cells[y][x] = 'R';
    }
  }

  if (style.aura === 'ember') {
    /* Four embers rising through transparent space beside the object. Their
     * columns are fixed per item and only their height changes, which is what
     * separates an ember from a twinkle. */
    for (let i = 0; i < 4; i++) {
      const col = 1 + Math.floor(rand() * Math.max(1, w - 2));
      const phase = rand();
      const y = Math.floor(h - 1 - (((f / frames) + phase) % 1) * (h - 1));
      const r = cells[y];
      if (!r || r[col] !== '.') continue;
      r[col] = ((f + i) & 1) ? 'R' : 'r';
    }
  }

  if (style.aura === 'void') {
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (cells[y][x] === 'x' && ((f + x + y) % frames) < frames / 2) cells[y][x] = 'X';
      }
    }
  }

  return toRows(cells);
}

/* The whole treatment, exported so a caller can apply the ladder to a grid this
 * module never authored — a boss trophy, a shop sign, an item another module
 * invents. Pass a shape-like `{gem, gem2}` or nothing at all.
 */
export function applyRarity(grid, rarity, opts = {}) {
  const style = rarityStyle(rarity);
  const shape = opts.shape || { gem: opts.gem || null, gem2: opts.gem2 || null };
  const seed = opts.seed === undefined ? 1 : opts.seed;
  let g = ornament(grid, shape, style, seed);
  g = applyRim(g);
  g = corrupt(g, style, seed);
  g = animate(g, style, opts.frame || 0, seed);
  return g;
}

/* ================================================================
 * RESOLVING AN ITEM TO A SHAPE
 * ================================================================
 * Deliberately not a table of item ids. The catalogue in gauntlet/items.py is
 * being extended while this is written and will be extended again; art keyed to
 * ids goes stale the moment somebody adds a sword. So: keyword hints first
 * (they carry the most intent), then the backend's own icon, then the slot.
 *
 * Every candidate is checked against what the slot can legally wear. That is
 * what stops "Chronomancer's Circlet" becoming an hourglass on the strength of
 * the word "chrono" — head slots wear crowns, not clocks.
 */
const SLOT_ALLOWED = {
  weapon:  ['sword', 'sabers', 'dagger', 'staff', 'spear', 'lance', 'axe', 'hammer', 'bow', 'orb', 'relic', 'key', 'feather'],
  offhand: ['shield', 'tome', 'orb', 'lens', 'relic', 'scroll', 'feather', 'potion'],
  head:    ['helm', 'crown', 'hood', 'lens'],
  chest:   ['plate', 'chest', 'robe', 'cloak'],
  hands:   ['gauntlets', 'wraps'],
  feet:    ['boots', 'greaves'],
  ring:    ['ring', 'relic'],
  trinket: ['amulet', 'relic', 'orb', 'hourglass', 'scroll', 'key', 'potion', 'tome', 'feather', 'lens', 'ring'],
  consumable: ['potion', 'scroll', 'relic', 'tome', 'shield', 'orb'],
};

const SLOT_DEFAULT = {
  weapon: 'sword', offhand: 'shield', head: 'helm', chest: 'chest',
  hands: 'gauntlets', feet: 'boots', ring: 'ring', trinket: 'amulet',
  consumable: 'potion',
};

/* Two passes, because not every word in an item name is equally load-bearing.
 * A STRONG hint is a noun that names the object outright and beats the
 * backend's icon: "Monocle" is a lens whatever icon the catalogue gave it. A
 * WEAK hint is a fragment that merely suggests one, and loses to the icon:
 * "Depthblade" contains "blade", but its icon says dagger, and the icon is
 * right. Getting this order wrong costs real art — it is how a dagger becomes
 * a sword and nobody notices for a month.
 */
const HINTS_STRONG = [
  [/monocle|lens|spectacle|eyeglass/, 'lens'],
  [/circlet|crown|diadem|coronet|tiara/, 'crown'],
  [/hood|cowl/, 'hood'],
  [/mantle|robe|vestment|shroud|gown/, 'robe'],
  [/cloak|cape/, 'cloak'],
  [/plate|cuirass|breastplate|panoply|harness/, 'plate'],
  [/vest|jerkin/, 'chest'],
  [/greave|sabaton|shin/, 'greaves'],
  [/tread|strider|boot|sandal/, 'boots'],
  [/gauntlet|grip|grasp/, 'gauntlets'],
  [/wrap|bandage|binding/, 'wraps'],
  [/codex|tome|grimoire/, 'tome'],
  [/scroll|parchment/, 'scroll'],
  [/potion|elixir|tonic|draught|flask|vial|philtre/, 'potion'],
  [/hourglass|sandglass/, 'hourglass'],
  [/feather|plume|quill/, 'feather'],
  [/\bkey\b|keystone/, 'key'],
  [/amulet|pendant|necklace|locket|talisman|sigil/, 'amulet'],
  [/signet/, 'ring'],
  [/orb|sphere|globe/, 'orb'],
  [/shield|aegis|bulwark|buckler/, 'shield'],
  [/saber|sabre/, 'sabers'],
  [/dagger|knife|dirk|stiletto|shiv/, 'dagger'],
  [/staff|sceptre|scepter|\bwand\b/, 'staff'],
  [/spear|pike|javelin|glaive|halberd/, 'spear'],
  [/lance/, 'lance'],
  [/\baxe\b|hatchet|cleaver|bardiche/, 'axe'],
  [/hammer|maul|mallet|gavel/, 'hammer'],
  [/longbow|shortbow|\bbow\b/, 'bow'],
];

const HINTS_WEAK = [
  [/blade|sword|edge|brand|falchion/, 'sword'],
  [/twin|paired/, 'sabers'],
  [/fang|tooth/, 'dagger'],
  [/\bband\b|\bring\b/, 'ring'],
  [/ward\b|guard\b/, 'shield'],
  [/core|node/, 'orb'],
  [/\bhat\b|\bcap\b/, 'hood'],
  [/glove|mitt/, 'gauntlets'],
  [/shirt|tunic|mail|jacket|coat/, 'chest'],
  [/book|manual|ledger|index/, 'tome'],
  [/page|folio|leaf/, 'scroll'],
  [/\bwing\b/, 'feather'],
  [/\brod\b|cane/, 'staff'],
  [/shoe|step/, 'boots'],
  [/medal|charm/, 'amulet'],
];

/* ring1 and ring2 are both rings; 'ring' is what the art cares about. */
function slotFamily(slot) {
  const s = String(slot || '').toLowerCase();
  if (s.startsWith('ring')) return 'ring';
  return SLOT_ALLOWED[s] ? s : 'trinket';
}

function allows(family, shape) {
  const list = SLOT_ALLOWED[family];
  return !!(shape && SHAPES[shape] && list && list.includes(shape));
}

export function resolveShape(item) {
  const it = item || {};
  const family = slotFamily(it.slot);
  const text = `${it.id || ''} ${it.name || ''}`.toLowerCase();
  for (const [re, shape] of HINTS_STRONG) {
    if (re.test(text) && allows(family, shape)) return shape;
  }
  /* "relic" is the catalogue's catch-all icon and names nothing, so it is not
   * treated as a shape; it resolves by slot at the bottom. */
  const icon = String(it.icon || '').toLowerCase();
  if (icon && icon !== 'relic' && allows(family, icon)) return icon;
  for (const [re, shape] of HINTS_WEAK) {
    if (re.test(text) && allows(family, shape)) return shape;
  }
  if (icon === 'relic') {
    if (family === 'weapon') return 'orb';
    if (family === 'offhand') return 'tome';
    if (family === 'ring') return 'ring';
    if (family === 'trinket') return 'relic';
  }
  return SLOT_DEFAULT[family] || 'relic';
}

/* ================================================================
 * BUILDING AND CACHING
 * ================================================================
 * Every canvas this module hands out comes from one of these caches. Render
 * loops call draw*, which only ever does drawImage.
 */
function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

/* A Map with a ceiling. Unbounded caches are fine until a player opens a vendor
 * with three hundred rolled items and the tab starts swapping. */
function cappedCache(limit) {
  const map = new Map();
  return {
    get(key, build) {
      const hit = map.get(key);
      if (hit !== undefined) return hit;
      const made = build();
      if (map.size >= limit) map.delete(map.keys().next().value);
      map.set(key, made);
      return made;
    },
    clear() { map.clear(); },
    get size() { return map.size; },
  };
}

const gridCache = cappedCache(512);
const spriteCache = cappedCache(512);

/* Per-item seed. Two Rare Testsmith Treads look identical to each other and
 * different from a Rare Nullbane Greave, which is the correct amount of
 * variation: the item is the unit of identity, not the roll. */
function itemSeed(item) {
  const it = item || {};
  return hash(`${it.id || it.name || 'item'}:${it.slot || ''}`) || 1;
}

export function itemFrameCount(itemOrRarity) {
  const rarity = typeof itemOrRarity === 'string'
    ? itemOrRarity : (itemOrRarity && itemOrRarity.rarity);
  return rarityStyle(rarity).frames;
}

export function itemGrid(item, frame = 0) {
  const shapeKey = resolveShape(item);
  const shape = SHAPES[shapeKey] || SHAPES.relic;
  const rarity = normaliseRarity(item && item.rarity);
  const seed = itemSeed(item);
  const frames = rarityStyle(rarity).frames;
  const f = ((frame % frames) + frames) % frames;
  const key = `${shapeKey}:${rarity}:${seed}:${f}`;
  return gridCache.get(key, () =>
    applyRarity(shape.grid, rarity, { shape, seed, frame: f }));
}

/* A finished 24x24 canvas. */
export function itemSprite(item, frame = 0) {
  const shapeKey = resolveShape(item);
  const shape = SHAPES[shapeKey] || SHAPES.relic;
  const rarity = normaliseRarity(item && item.rarity);
  const seed = itemSeed(item);
  const frames = rarityStyle(rarity).frames;
  const f = ((frame % frames) + frames) % frames;
  const key = `${shapeKey}:${rarity}:${seed}:${f}`;
  return spriteCache.get(key, () => gridSprite(
    itemGrid(item, f), rarityPalette(shape.mat, rarity), N, N));
}

export function itemFrames(item) {
  const n = itemFrameCount(item);
  const out = new Array(n);
  for (let i = 0; i < n; i++) out[i] = itemSprite(item, i);
  return out;
}

/* ---------------- reduced motion ----------------
 * A module-level default so a caller that never threads the flag through still
 * honours it, and a per-call override for the cases that do.
 */
let reducedMotionDefault = false;
export function setReducedMotion(v) { reducedMotionDefault = !!v; }
function isReduced(opts) {
  return opts && opts.reducedMotion !== undefined
    ? !!opts.reducedMotion : reducedMotionDefault;
}

/* Which frame an item is on right now. Reduced motion pins frame 0, which is
 * authored to be the readable one: the glint is off the left edge there. */
export function frameFor(item, opts = {}) {
  const frames = itemFrameCount(item);
  if (frames <= 1 || isReduced(opts)) return 0;
  if (opts.frame !== undefined && opts.frame !== null) {
    return ((opts.frame % frames) + frames) % frames;
  }
  if (opts.time !== undefined && opts.time !== null) {
    return Math.floor(opts.time / FRAME_MS) % frames;
  }
  return 0;
}

/* The one call the rest of the game needs.
 *
 *   lootart.drawItem(ctx, item, x, y, { scale: 2, time: performance.now() });
 *
 * `item` is the dict the backend already sends: id, name, slot, rarity, icon,
 * effect_text. Nothing else is required and nothing else is read.
 */
export function drawItem(ctx, item, x, y, opts = {}) {
  const scale = Math.max(1, opts.scale || 1);
  const frame = frameFor(item, opts);
  const img = itemSprite(item, frame);
  const px = Math.round(x), py = Math.round(y);
  if (opts.shadow) {
    drawGroundShadow(ctx, px + (N * scale) / 2, py + N * scale - 2 * scale,
      Math.round(7 * scale), Math.round(3 * scale), 0.36);
  }
  /* Integer scales go through the pre-scaler in sprites.js so source pixels
   * land on pixel boundaries; fractional scales are the caller's problem and
   * are drawn directly. */
  if (Number.isInteger(scale)) {
    ctx.drawImage(scaleSprite(img, scale), px, py);
  } else {
    const smooth = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, px, py, N * scale, N * scale);
    ctx.imageSmoothingEnabled = smooth;
  }
  return img;
}

/* ================================================================
 * DROP PRESENTATION
 * ================================================================
 * A drop is a moment or it is a line of text. These three exports are what
 * turn it into a moment: a beam that says something landed, a burst in the
 * rarity colour that says how much it matters, and a framed card that says
 * look at it.
 *
 * All three are pure fillRect. No gradients, no shadowBlur, no compositing
 * modes — every one of those softens edges, and a soft edge in a 16-bit frame
 * reads as a mistake rather than as polish.
 */
const BEAM_FRAMES = 6;
const BURST_FRAMES = 8;

const beamCache = cappedCache(96);
const burstCache = cappedCache(96);
const cardCache = cappedCache(96);

/* A column of light. Brightest at the base where the item sits, banded with
 * scanline gaps that travel upward, with motes lifting out of the top. */
export function lootBeam(rarity, opts = {}) {
  const style = rarityStyle(rarity);
  const w = Math.max(8, opts.width || 24);
  const h = Math.max(16, opts.height || 48);
  const frames = BEAM_FRAMES;
  const f = ((opts.frame || 0) % frames + frames) % frames;
  const key = `${style.key}:${w}:${h}:${f}`;
  return beamCache.get(key, () => {
    const { canvas, ctx } = makeCanvas(w, h);
    const cx = Math.floor(w / 2);
    const core = mix(style.colour, '#ffffff', 0.62);
    const mid = style.colour;
    const outer = mix(style.colour, '#07060c', 0.42);
    /* Four half-width bands. Anything more and the hard edges stop reading as
     * a beam and start reading as a gradient drawn badly. */
    const bands = [
      { half: 1, colour: core, alpha: 0.95 },
      { half: 2, colour: mid, alpha: 0.72 },
      { half: 4, colour: mid, alpha: 0.38 },
      { half: Math.floor(w / 2), colour: outer, alpha: 0.18 },
    ];
    for (let y = 0; y < h; y++) {
      /* Fade toward the top: the light is coming out of the ground. */
      const fall = 0.35 + 0.65 * (y / h);
      /* Scanline gaps travel up one row per frame, which is the whole reason
       * the beam looks like it is flowing rather than standing still. */
      const gap = ((y + f * 2) % 7) === 0;
      for (const b of bands) {
        const a = b.alpha * fall * (gap ? 0.35 : 1);
        if (a <= 0.02) continue;
        ctx.globalAlpha = a;
        ctx.fillStyle = b.colour;
        ctx.fillRect(cx - b.half, y, b.half * 2, 1);
      }
    }
    /* Motes. Deterministic columns, position driven by the frame. */
    const rand = rng(hash(style.key + w) || 1);
    ctx.globalAlpha = 0.9;
    for (let i = 0; i < 6; i++) {
      const col = cx - 5 + Math.floor(rand() * 11);
      const phase = rand();
      const y = Math.floor((1 - (((f / frames) + phase) % 1)) * (h - 2));
      ctx.fillStyle = (i & 1) ? core : mid;
      ctx.fillRect(col, y, 1, 1);
    }
    ctx.globalAlpha = 1;
    return canvas;
  });
}

export function drawLootBeam(ctx, rarity, cx, baseY, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 1));
  const frame = isReduced(opts) ? 0
    : (opts.frame !== undefined ? opts.frame
      : Math.floor((opts.time || 0) / FRAME_MS));
  const img = lootBeam(rarity, { ...opts, frame });
  const out = scale > 1 ? scaleSprite(img, scale) : img;
  ctx.drawImage(out, Math.round(cx - out.width / 2), Math.round(baseY - out.height));
  return out;
}

/* The rarity burst: spokes fired outward in the rarity colour, hot white at
 * the core early and gone by the last frame. Eight frames is one short beat at
 * FRAME_MS, which is about as long as a reward flash should last.
 */
export function rarityBurst(rarity, opts = {}) {
  const style = rarityStyle(rarity);
  const size = Math.max(16, opts.size || 48);
  const frames = BURST_FRAMES;
  const f = ((opts.frame || 0) % frames + frames) % frames;
  const key = `${style.key}:${size}:${f}`;
  return burstCache.get(key, () => {
    const { canvas, ctx } = makeCanvas(size, size);
    const c = (size - 1) / 2;
    const t = f / (frames - 1);
    const maxR = size / 2 - 1;
    const r = 3 + t * (maxR - 3);
    const fade = 1 - t;
    const hot = mix(style.colour, '#ffffff', 0.7);
    /* More spokes for higher tiers. A Common drop should not get a starburst;
     * it should get a nudge. */
    const spokes = 6 + style.index * 2;
    ctx.fillStyle = style.colour;
    for (let i = 0; i < spokes; i++) {
      const a = (i / spokes) * Math.PI * 2 + (style.index * 0.11);
      const dx = Math.cos(a), dy = Math.sin(a);
      const inner = r * 0.45;
      for (let d = inner; d <= r; d += 0.6) {
        const px = Math.round(c + dx * d), py = Math.round(c + dy * d);
        if (px < 0 || py < 0 || px >= size || py >= size) continue;
        ctx.globalAlpha = fade * (d > r * 0.8 ? 0.55 : 0.95);
        ctx.fillStyle = d < r * 0.65 ? hot : style.colour;
        ctx.fillRect(px, py, 1, 1);
      }
    }
    /* The core: a hard square that collapses as the ring expands. */
    const core = Math.max(0, Math.round((1 - t) * 5));
    if (core > 0) {
      ctx.globalAlpha = fade;
      ctx.fillStyle = hot;
      ctx.fillRect(Math.round(c - core / 2), Math.round(c - core / 2), core, core);
    }
    /* A stippled shock ring for Epic and above, which is where the drop stops
     * being an upgrade and starts being an event. */
    if (style.index >= 3) {
      ctx.globalAlpha = fade * 0.6;
      ctx.fillStyle = style.colour;
      for (let a = 0; a < Math.PI * 2; a += 0.18) {
        const px = Math.round(c + Math.cos(a) * r), py = Math.round(c + Math.sin(a) * r);
        if (px < 0 || py < 0 || px >= size || py >= size) continue;
        ctx.fillRect(px, py, 1, 1);
      }
    }
    ctx.globalAlpha = 1;
    return canvas;
  });
}

export function drawRarityBurst(ctx, rarity, cx, cy, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 1));
  const frame = opts.frame !== undefined ? opts.frame
    : Math.floor((opts.time || 0) / FRAME_MS);
  const img = rarityBurst(rarity, { ...opts, frame });
  const out = scale > 1 ? scaleSprite(img, scale) : img;
  ctx.drawImage(out, Math.round(cx - out.width / 2), Math.round(cy - out.height / 2));
  return out;
}

/* ---------------- the reward card ----------------
 * 56x76 at 1x. Draw it at scale 3 or 4 for a drop modal. The card deliberately
 * carries no text: pixel type at this size is either unreadable or a second
 * font engine, and the name and effects are already DOM, where they can be
 * selected, translated and read by a screen reader. What the card renders is
 * the frame, the item, and the tier — the things that have to be pixels.
 */
export const CARD_W = 56;
export const CARD_H = 76;
export const CARD_ITEM_RECT = Object.freeze({ x: 4, y: 4, w: 48, h: 48 });
export const CARD_TEXT_RECT = Object.freeze({ x: 5, y: 56, w: 46, h: 10 });
export const CARD_PIP_RECT = Object.freeze({ x: 5, y: 68, w: 46, h: 3 });

export function lootCard(item, opts = {}) {
  const rarity = normaliseRarity(item && item.rarity);
  const style = rarityStyle(rarity);
  const frame = frameFor(item, opts);
  const seed = itemSeed(item);
  const key = `${resolveShape(item)}:${rarity}:${seed}:${frame}`;
  return cardCache.get(key, () => {
    const { canvas, ctx } = makeCanvas(CARD_W, CARD_H);
    const dark = '#07060c';
    const plate = mix('#12111a', style.colour, 0.06);
    const chromeHi = '#7b8492';
    const chromeLo = '#1b1b24';

    ctx.fillStyle = dark;
    ctx.fillRect(0, 0, CARD_W, CARD_H);
    /* Chrome bevel: lit from the upper left, same direction as every sprite in
     * the game. Two rects, not a border, because a border cannot be lit. */
    ctx.fillStyle = chromeHi;
    ctx.fillRect(1, 1, CARD_W - 2, 1);
    ctx.fillRect(1, 1, 1, CARD_H - 2);
    ctx.fillStyle = chromeLo;
    ctx.fillRect(1, CARD_H - 2, CARD_W - 2, 1);
    ctx.fillRect(CARD_W - 2, 1, 1, CARD_H - 2);
    ctx.fillStyle = plate;
    ctx.fillRect(2, 2, CARD_W - 4, CARD_H - 4);

    /* The item window: near-black, with a rarity wash stippled into the lower
     * half so the item has something to sit against. */
    const win = CARD_ITEM_RECT;
    ctx.fillStyle = '#0a0910';
    ctx.fillRect(win.x - 1, win.y - 1, win.w + 2, win.h + 2);
    ctx.globalAlpha = 0.16;
    ctx.fillStyle = style.colour;
    for (let y = win.y + win.h / 2; y < win.y + win.h; y++) {
      const a = (y - (win.y + win.h / 2)) / (win.h / 2);
      ctx.globalAlpha = 0.04 + a * 0.16;
      for (let x = win.x; x < win.x + win.w; x++) {
        if (((x + y) & 1) === 0) continue;
        ctx.fillRect(x, y, 1, 1);
      }
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = style.colour;
    ctx.fillStyle = style.colour;
    ctx.fillRect(win.x - 1, win.y - 1, win.w + 2, 1);
    ctx.fillRect(win.x - 1, win.y + win.h, win.w + 2, 1);
    ctx.fillRect(win.x - 1, win.y - 1, 1, win.h + 2);
    ctx.fillRect(win.x + win.w, win.y - 1, 1, win.h + 2);

    /* Rivets. Four of them, because a frame with no fasteners is a rectangle. */
    for (const [rx, ry] of [[win.x, win.y], [win.x + win.w - 2, win.y],
                            [win.x, win.y + win.h - 2], [win.x + win.w - 2, win.y + win.h - 2]]) {
      ctx.fillStyle = chromeHi;
      ctx.fillRect(rx, ry, 2, 2);
      ctx.fillStyle = chromeLo;
      ctx.fillRect(rx + 1, ry + 1, 1, 1);
    }

    ctx.drawImage(scaleSprite(itemSprite(item, frame), 2), win.x, win.y);

    /* The tier bar and its pips. Pips are the only quantity on the card and
     * they are countable at a glance, which is the point. */
    ctx.fillStyle = style.colour;
    ctx.fillRect(win.x - 1, 53, win.w + 2, 2);
    ctx.fillStyle = '#0a0910';
    ctx.fillRect(CARD_TEXT_RECT.x - 1, CARD_TEXT_RECT.y - 1,
      CARD_TEXT_RECT.w + 2, CARD_TEXT_RECT.h + 2);
    const pips = style.index + 1;
    for (let i = 0; i < 6; i++) {
      const px = CARD_PIP_RECT.x + i * 8;
      ctx.fillStyle = i < pips ? style.colour : '#23222e';
      ctx.fillRect(px, CARD_PIP_RECT.y, 5, 3);
      if (i < pips) {
        ctx.fillStyle = mix(style.colour, '#ffffff', 0.45);
        ctx.fillRect(px, CARD_PIP_RECT.y, 5, 1);
      }
    }

    /* Epic and above get a chrome glint travelling the top rail, in step with
     * the item's own glint so the card reads as one object. */
    if (style.animated) {
      const p = Math.floor(((frame + 0.5) / style.frames) * (CARD_W + 12)) - 6;
      ctx.fillStyle = '#ffffff';
      for (let i = 0; i < 5; i++) {
        const x = p + i;
        if (x < 2 || x >= CARD_W - 2) continue;
        ctx.globalAlpha = 0.85 - Math.abs(i - 2) * 0.28;
        ctx.fillRect(x, 1, 1, 1);
      }
      ctx.globalAlpha = 1;
    }
    return canvas;
  });
}

export function drawLootCard(ctx, item, x, y, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 1));
  const img = lootCard(item, opts);
  const out = scale > 1 ? scaleSprite(img, scale) : img;
  ctx.drawImage(out, Math.round(x), Math.round(y));
  return out;
}

/* The whole reward moment in one call. `t` is 0..1 across the drop animation:
 * the burst fires on the first third, the beam holds throughout, the item
 * rises out of the beam and settles into a bob.
 */
export function drawLootDrop(ctx, item, cx, groundY, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 2));
  const rarity = normaliseRarity(item && item.rarity);
  const t = opts.t === undefined ? 1 : clamp(opts.t, 0, 1);
  const time = opts.time || 0;
  const reduced = isReduced(opts);

  drawLootBeam(ctx, rarity, cx, groundY, {
    width: 24, height: 48, scale, time, reducedMotion: reduced,
  });

  /* Rise, then settle. Reduced motion skips the rise and the bob entirely and
   * simply puts the item where it ends up. */
  const rise = reduced ? 0 : (1 - Math.min(1, t / 0.45)) * 14 * scale;
  const bob = reduced ? 0
    : Math.round(Math.sin(time / 380) * 1.5) * scale;
  const size = N * scale;
  const iy = groundY - 30 * scale + rise + bob;
  drawItem(ctx, item, cx - size / 2, iy, { scale, time, reducedMotion: reduced });

  if (!reduced && t < 0.55) {
    const bf = Math.min(BURST_FRAMES - 1, Math.floor((t / 0.55) * BURST_FRAMES));
    drawRarityBurst(ctx, rarity, cx, iy + size / 2, { size: 48, scale, frame: bf });
  }
}

/* ================================================================
 * EQUIPPED GEAR ON THE HERO
 * ================================================================
 * Loot the player cannot see on the character is loot the player stops caring
 * about. These overlays composite onto the 16x24 hero from sprites.js at the
 * same anchors sprites.js uses internally, so a weapon drawn here lands in the
 * hand rather than beside it.
 *
 * sprites.js keeps WEAPON_ANCHOR private, so the values are mirrored here. If
 * that file's anchors move, these move with them — it is four numbers, and the
 * alternative is exporting the hero's skeleton, which is a worse dependency.
 */
export const HERO_WEAPON_ANCHOR = Object.freeze({
  down: [10, 6], up: [1, 5], left: [-1, 6], right: [11, 6],
});
const HERO_SHIELD_ANCHOR = Object.freeze({
  down: [0, 10], up: [10, 10], left: [10, 10], right: [0, 10],
});
const HERO_HELM_ANCHOR = Object.freeze({ down: [3, 1], up: [3, 1], left: [3, 1], right: [3, 1] });
const HERO_CLOAK_ANCHOR = Object.freeze({ down: [1, 10], up: [1, 10], left: [1, 10], right: [1, 10] });

/* Weapon overlays live in the same 6x12 box HERO_WEAPONS uses and share its
 * keys, so `heroWeaponKeyFor()` can also be handed straight to heroFrame() by
 * a caller that does not want an overlay at all. */
const HERO_WEAPON_ART = {
  sword:  ['..o...', '.oBo..', '.oBo..', '.oBo..', '.oBo..', '.oBo..',
           '.oBo..', 'ogggo.', '..s...', '..s...', '.ogo..', '......'],
  sabers: ['......', '..o...', '.oBo..', '.oBo..', '.oBo..', '.oBo..',
           'ogggo.', '..s...', '.ogo..', '......', '......', '......'],
  dagger: ['......', '......', '..o...', '.oBo..', '.oBo..', '.oBo..',
           'ogggo.', '..s...', '.ogo..', '......', '......', '......'],
  axe:    ['.oooo.', 'oBBgBo', 'oBggBo', '.oBBo.', '..os..', '..os..',
           '..os..', '..os..', '..os..', '..os..', '..oo..', '......'],
  hammer: ['.oooo.', 'oBBBBo', 'oBggBo', 'oBBBBo', '.oos..', '..os..',
           '..os..', '..os..', '..os..', '..os..', '..oo..', '......'],
  spear:  ['..o...', '.oBo..', 'oBBBo.', '.oBo..', '..s...', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..s...', '..o...'],
  lance:  ['..o...', '.oBo..', '.oBo..', 'oBBBo.', '.ogo..', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..s...', '..o...'],
  staff:  ['..o...', '.ogo..', 'ogmgo.', '.ogo..', '..o...', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..s...', '..o...'],
  bow:    ['.oo...', 'og.o..', 'og..w.', 'og..w.', 'og..w.', 'og..w.',
           'og..w.', 'og..w.', 'og..w.', 'og.o..', '.oo...', '......'],
  relic:  ['......', '..oo..', '.ogmo.', 'ogmmgo', 'ogmmgo', '.ogmo.',
           '..oo..', '..s...', '..s...', '..oo..', '......', '......'],
};

const HERO_SHIELD_ART = [
  '.oooo.', 'oBBBBo', 'oBmmBo', 'oBmmBo', 'oBBBBo', '.oBBo.', '..oo..', '......',
];

/* Three head silhouettes, because a crown that covers the face is a helm and a
 * helm that shows the hair is a headband. */
const HERO_HEAD_ART = {
  helm: [
    '..oooooo..', '.oBBBBBBo.', 'oBBBBBBBBo', 'oBeeeeeeBo',
    'oBBBBBBBBo', '.oBBBBBBo.', '..oooooo..', '..........', '..........',
  ],
  crown: [
    '..o..o..o.', '.oggggggo.', '.ogmggmgo.', '.oyyyyyyo.',
    '..........', '..........', '..........', '..........', '..........',
  ],
  hood: [
    '..oooooo..', '.occcccco.', 'occcccccco', 'occeeeecco',
    'occeeeecco', 'occcccccco', '.occcccco.', '..oooooo..', '..........',
  ],
};

const HERO_CLOAK_ART = {
  front: [
    'ocCCCCCCCCCCco', 'occcccccccccco', 'oc..........co', 'oc..........co',
    'oc..........co', 'ov..........vo', 'ov..........vo', 'oo..........oo',
    '..............', '..............',
  ],
  back: [
    'ocCCCCCCCCCCco', 'occcccccccccco', 'occcccccccccco', 'occcccccccccco',
    'occcccccccccco', 'occcccccccccco', 'ovvvvvvvvvvvvo', 'ovvvvvvvvvvvvo',
    'oooooooooooooo', '..............',
  ],
};

const SHAPE_TO_HERO_WEAPON = {
  sword: 'sword', sabers: 'sabers', dagger: 'dagger', axe: 'axe',
  hammer: 'hammer', spear: 'spear', lance: 'lance', staff: 'staff',
  bow: 'bow', orb: 'relic', relic: 'relic', key: 'relic', feather: 'relic',
};

/* Useful on its own: a caller that only wants the built-in hero art can pass
 * this into sprites.heroFrame({ weapon: ... }) and skip overlays entirely. */
export function heroWeaponKeyFor(item) {
  const key = SHAPE_TO_HERO_WEAPON[resolveShape(item)] || 'sword';
  return HERO_WEAPON_KEYS.includes(key) ? key : HERO_WEAPON_KEYS[0];
}

function headArtFor(item) {
  const shape = resolveShape(item);
  if (shape === 'crown') return 'crown';
  if (shape === 'hood') return 'hood';
  return 'helm';
}

/* Pose offsets, mirroring heroFrame(). The weapon rises on a cast and settles
 * on an idle; the head sinks a pixel on an idle because the body does. Getting
 * this wrong is not subtle — the sword detaches from the hand. */
function poseOffsets(facing, pose, frame) {
  const f = ((frame % 4) + 4) % 4;
  const pass = f === 1 || f === 3;
  if (pose === 'cast') return { weaponDY: -6, bodyDY: -1 };
  if (pose === 'idle') return { weaponDY: 1, bodyDY: 1 };
  return { weaponDY: pass ? -1 : 0, bodyDY: pass ? -1 : 0 };
}

const overlayCache = cappedCache(384);

/* Overlays get the same rarity ladder as the inventory icon, minus the
 * corruption pass — a 6x12 box does not have room for voids and a fracture
 * without dissolving, and a weapon that dissolves at 16px reads as damage. */
function overlaySprite(art, item, w, h, frame, tag) {
  const shapeKey = resolveShape(item);
  const shape = SHAPES[shapeKey] || SHAPES.relic;
  const rarity = normaliseRarity(item && item.rarity);
  const style = rarityStyle(rarity);
  const seed = itemSeed(item);
  const f = ((frame % style.frames) + style.frames) % style.frames;
  const key = `${tag}:${shapeKey}:${rarity}:${seed}:${f}`;
  return overlayCache.get(key, () => {
    let g = applyRim(art);
    g = animate(g, style, f, seed);
    return gridSprite(g, rarityPalette(shape.mat, rarity), w, h);
  });
}

/* Each of these returns { canvas, ox, oy } in hero-sprite coordinates, so the
 * caller can either composite with sprites.composeSprite or drawImage at
 * (heroX + ox * scale, heroY + oy * scale). */
export function heroWeaponOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_WEAPON_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const art = HERO_WEAPON_ART[heroWeaponKeyFor(item)] || HERO_WEAPON_ART.sword;
  const [ax, ay] = HERO_WEAPON_ANCHOR[facing];
  const { weaponDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  return { canvas: overlaySprite(art, item, 6, 12, frame, 'wpn'), ox: ax, oy: ay + weaponDY };
}

export function heroShieldOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_SHIELD_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const [ax, ay] = HERO_SHIELD_ANCHOR[facing];
  const { bodyDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  return { canvas: overlaySprite(HERO_SHIELD_ART, item, 6, 8, frame, 'shd'), ox: ax, oy: ay + bodyDY };
}

export function heroHelmOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_HELM_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const art = HERO_HEAD_ART[headArtFor(item)];
  const [ax, ay] = HERO_HELM_ANCHOR[facing];
  const { bodyDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  return { canvas: overlaySprite(art, item, 10, 9, frame, 'hlm'), ox: ax, oy: ay + bodyDY };
}

export function heroCloakOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_CLOAK_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const art = HERO_CLOAK_ART[facing === 'up' ? 'back' : 'front'];
  const [ax, ay] = HERO_CLOAK_ANCHOR[facing];
  const { bodyDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  return { canvas: overlaySprite(art, item, 14, 10, frame, 'clk'), ox: ax, oy: ay + bodyDY };
}

export function gearOverlay(kind, item, opts = {}) {
  if (kind === 'weapon') return heroWeaponOverlay(item, opts);
  if (kind === 'offhand' || kind === 'shield') return heroShieldOverlay(item, opts);
  if (kind === 'head' || kind === 'helm') return heroHelmOverlay(item, opts);
  if (kind === 'chest' || kind === 'cloak' || kind === 'back') return heroCloakOverlay(item, opts);
  return null;
}

/* Sorted into the two passes the hero needs. Facing away, the weapon is behind
 * the body and the cloak is the whole back; facing the camera it is the other
 * way round. Same rule sprites.js applies to its own weapon layer.
 */
export function heroGearLayers(gear, opts = {}) {
  const g = gear || {};
  const facing = ['down', 'up', 'left', 'right'].includes(opts.facing) ? opts.facing : 'down';
  const behind = [], front = [];
  const cloak = heroCloakOverlay(g.chest || g.cloak || g.back, { ...opts, facing });
  if (cloak) (facing === 'up' ? front : behind).push(cloak);
  const weapon = heroWeaponOverlay(g.weapon, { ...opts, facing });
  if (weapon) (facing === 'up' ? behind : front).push(weapon);
  const shield = heroShieldOverlay(g.offhand, { ...opts, facing });
  if (shield) (facing === 'up' ? behind : front).push(shield);
  const helm = heroHelmOverlay(g.head, { ...opts, facing });
  if (helm) front.push(helm);
  return { behind, front };
}

/* Draw one pass. Call with `behind` before the hero and `front` after.
 * Coordinates are the hero sprite's top-left in the caller's space.
 *
 * heroGearLayers returns the bundle {behind, front}, not an array, and passing
 * that bundle straight back in is the obvious mistake. Accept it rather than
 * throwing mid-frame: with no hero drawn between the passes, behind-then-front
 * is the correct order anyway. Anything else non-iterable draws nothing.
 */
export function drawHeroGear(ctx, layers, x, y, scale = 1) {
  const s = Math.max(1, Math.round(scale));
  let list = layers;
  if (list && !Array.isArray(list) && typeof list[Symbol.iterator] !== 'function') {
    list = (list.behind || list.front)
      ? [...(list.behind || []), ...(list.front || [])]
      : [];
  }
  for (const layer of list || []) {
    if (!layer || !layer.canvas) continue;
    const img = s > 1 ? scaleSprite(layer.canvas, s) : layer.canvas;
    ctx.drawImage(img, Math.round(x + layer.ox * s), Math.round(y + layer.oy * s));
  }
}

/* Composite gear into a single 16x24 canvas with the hero sprite already drawn.
 * Useful for a paperdoll or a portrait, where one cached canvas beats four
 * drawImage calls a frame. */
export function heroWithGear(heroCanvas, gear, opts = {}) {
  const { canvas, ctx } = makeCanvas(HERO_W, HERO_H);
  const { behind, front } = heroGearLayers(gear, opts);
  drawHeroGear(ctx, behind, 0, 0, 1);
  if (heroCanvas) ctx.drawImage(heroCanvas, 0, 0);
  drawHeroGear(ctx, front, 0, 0, 1);
  return canvas;
}

/* Render a base shape directly, without an item dict. Useful for anything that
 * wants the ladder applied to a known silhouette — a vendor stall, a boss
 * trophy, a set preview — and it is what the art harness renders to prove every
 * shape survives every tier.
 */
export function shapeGrid(shapeKey, rarity, opts = {}) {
  const shape = SHAPES[shapeKey] || SHAPES.relic;
  const style = rarityStyle(rarity);
  const seed = opts.seed === undefined ? (hash(shapeKey) || 1) : opts.seed;
  const f = ((opts.frame || 0) % style.frames + style.frames) % style.frames;
  const key = `shape:${shapeKey}:${style.key}:${seed}:${f}`;
  return gridCache.get(key, () => applyRarity(shape.grid, style.key, { shape, seed, frame: f }));
}

export function shapeSprite(shapeKey, rarity, opts = {}) {
  const shape = SHAPES[shapeKey] || SHAPES.relic;
  const style = rarityStyle(rarity);
  const seed = opts.seed === undefined ? (hash(shapeKey) || 1) : opts.seed;
  const f = ((opts.frame || 0) % style.frames + style.frames) % style.frames;
  const key = `shape:${shapeKey}:${style.key}:${seed}:${f}`;
  return spriteCache.get(key, () => gridSprite(
    shapeGrid(shapeKey, style.key, { seed, frame: f }),
    rarityPalette(shape.mat, style.key), N, N));
}

export function shapeMaterial(shapeKey) {
  return (SHAPES[shapeKey] || SHAPES.relic).mat;
}

/* ================================================================
 * HOUSEKEEPING
 * ================================================================ */
export function clearLootArtCache() {
  gridCache.clear(); spriteCache.clear(); beamCache.clear();
  burstCache.clear(); cardCache.clear(); overlayCache.clear();
}

export function lootArtStats() {
  return {
    shapes: SHAPE_KEYS.length,
    rarities: RARITY_KEYS.length,
    grids: gridCache.size,
    sprites: spriteCache.size,
    overlays: overlayCache.size,
  };
}

/* ================================================================
 * INTEGRATION
 * ================================================================
 * This module writes nothing and owns no canvas. Wiring is four edits.
 *
 * 1) web/js/main.js — replace itemIcon(). The current version rasterises an
 *    8x8 pixel.icon into a canvas sized by CSS. The replacement:
 *
 *      import * as lootart from './lootart.js';
 *
 *      function itemIcon(item, size = 28) {
 *        const scale = Math.max(1, Math.round(size / lootart.ITEM_SIZE));
 *        const px = lootart.ITEM_SIZE * scale;
 *        const canvas = document.createElement('canvas');
 *        canvas.width = px; canvas.height = px;
 *        canvas.style.width = canvas.style.height = size + 'px';
 *        canvas.style.imageRendering = 'pixelated';
 *        const ctx = canvas.getContext('2d');
 *        ctx.imageSmoothingEnabled = false;
 *        lootart.drawItem(ctx, item, 0, 0, { scale });
 *        return canvas;
 *      }
 *
 *    For Epic and above the icon is animated. Either pass `time` from an
 *    existing rAF tick and redraw, or leave it static in list views and animate
 *    only the detail panel. Both are correct; a list of forty animated icons is
 *    not.
 *
 * 2) The drop moment. Wherever a reward is currently announced, give it a
 *    canvas of CARD_W x CARD_H scaled 3x or 4x and call:
 *
 *      lootart.drawLootCard(ctx, item, 0, 0, { scale: 4, time });
 *
 *    Put the item name and effect_text in DOM over CARD_TEXT_RECT scaled to
 *    match. The card renders no text on purpose: pixel type at this size is
 *    either unreadable or a second font engine, and DOM text stays selectable
 *    and readable by a screen reader.
 *
 *    For a drop inside the battle scene instead, fx.js already owns a canvas
 *    and a clock, so one call per frame does the whole moment:
 *
 *      lootart.drawLootDrop(ctx, item, cx, groundY,
 *        { scale: 2, t: dropProgress, time, reducedMotion: this.reducedMotion });
 *
 * 3) Gear on the hero. Wherever heroFrame() is drawn, wrap it:
 *
 *      const layers = lootart.heroGearLayers(G.equipped,
 *        { facing, pose, frameIndex: frame, time });
 *      lootart.drawHeroGear(ctx, layers.behind, x, y, scale);
 *      ctx.drawImage(sprites.scaleSprite(sprites.heroFrame(facing, frame, opts, pose), scale), x, y);
 *      lootart.drawHeroGear(ctx, layers.front, x, y, scale);
 *
 *    `G.equipped` is read for the keys weapon, offhand, head and chest only;
 *    anything else on the object is ignored. A cheaper option that needs no
 *    second pass is to keep sprites.js drawing the weapon and just tell it
 *    which one: `opts.weapon = lootart.heroWeaponKeyFor(G.equipped.weapon)`.
 *
 * 4) Reduced motion. Call `lootart.setReducedMotion(v)` from the same place
 *    that calls `BattleFX.setReducedMotion(v)`. Every animated path here also
 *    takes a per-call `reducedMotion` override, so fx.js can pass its own flag
 *    without the module-level default being set at all.
 *
 * Nothing in this module reads game state, calls the API, or knows what a
 * problem is. It takes the item dict the backend already sends and draws it.
 */
