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
 * Six conventions carry the file:
 *
 *   1. A shape is authored as MATERIAL, never as colour. A grid says "this is
 *      body metal, this is haft, this is trim, this is gem" and the rarity
 *      supplies what those words mean. That is why a new item added to
 *      gauntlet/items.py tomorrow inherits the whole ladder for free.
 *   2. Rarity is a pipeline of grid transforms — silhouette, ornament, rim,
 *      corruption, animation — applied in that order. Each stage is a pure
 *      function from grid to grid, so the ladder can be tested and extended
 *      without touching a single shape.
 *   3. RARITY IS READ FROM THE OUTLINE FIRST. This is the rule the rest of the
 *      file serves. A tier that changes only hue is a tier the player learns to
 *      ignore, because in a dark frame at 24px hue is the weakest channel there
 *      is. So the silhouette stage GROWS the object: a Common sword has a plain
 *      straight guard, a Rare one has quillons, an Epic one has swept wings, a
 *      Legendary one has horned wings, a pennant and a faceted crystal. You can
 *      name the tier of a Legendary from across the room with the colour turned
 *      off, and the art harness proves it — see silhouetteSpread().
 *   4. A Legendary has a HISTORY. Symmetry is what makes procedural art look
 *      procedural, so every Legendary and above takes one seeded, one-sided
 *      mark: a chip out of the edge, a repair binding wrapped over the haft at
 *      a slightly wrong place, a pennant on one side only.
 *   5. Shapes are resolved from SLOT and ICON with keyword hints, never from a
 *      hardcoded item id. The catalogue is being edited by other hands; art
 *      keyed to ids would rot within the hour.
 *   6. Everything is cached by a deterministic key. Nothing allocates a canvas
 *      inside a render loop, and the same item looks the same forever.
 *
 * Wiring is documented at the bottom of the file under INTEGRATION.
 */
import { ramp, mix, rng, hash, applyRim, gridSprite, composeSprite, drawGroundShadow, scaleSprite, heroFrame, HERO_W, HERO_H, HERO_WEAPON_KEYS } from './sprites.js';

export const LOOT_ART_VERSION = '1.1.0';

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
 *   COMMON     plain iron. Bare silhouette, no ornament, no light.
 *   UNCOMMON   cleaner steel, one bronze fitting, the shape squares up
 *   RARE       blued steel, silver inlay, a set gem, the shape grows guards
 *   EPIC       swept and winged, violet energy IN the material, animated glint
 *   LEGENDARY  horned and crowned, gold on blackened steel, engraving, a
 *              faceted crystal, a torn pennant, one scar, embers
 *   MYTHIC     all of that, then the material fails — voids punched through,
 *              a fracture corner to corner, red light leaking out of both
 *
 * Each tier is expressed as (a) a material transform, (b) a SILHOUETTE level
 * that grows the outline, (c) an ornament level that adds structure inside it,
 * and (d) an aura that animates. Because all four are driven off this table
 * alone, an item authored next week inherits the full ladder without anyone
 * editing its shape.
 *
 * `grow` is the one that matters. Everything else on this table is a surface
 * treatment and surface treatments do not survive a dark room, a small icon or
 * a colour-blind player. The outline does.
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
    grow: 0, ornament: 0, sheen: 0, aura: 'none', outlineTint: 0.06,
  },
  UNCOMMON: {
    label: 'Uncommon', colour: '#8fd07a',
    /* Cleaned up and slightly brighter, with one bronze fitting. */
    tint: '#3a4048', tintAmt: 0.12, desat: 0.18, lift: 0.03,
    trim: '#a9712f', gem: '#6f8a52', rune: null, energy: null,
    grow: 1, ornament: 1, sheen: 1, aura: 'none', outlineTint: 0.08,
  },
  RARE: {
    label: 'Rare', colour: '#7ec8ff',
    /* Blued steel: the metal itself is pulled toward cold blue, the inlay is
     * silver, and the rim light is cool rather than the default warm. */
    tint: '#31456e', tintAmt: 0.34, desat: 0.0, lift: 0.02,
    trim: '#c2ccdd', gem: '#7ec8ff', rune: null, energy: '#7ec8ff',
    grow: 2, ornament: 2, sheen: 2, aura: 'none', outlineTint: 0.12,
    rim: '#9fd8ff',
  },
  EPIC: {
    label: 'Epic', colour: '#c8a8ff',
    /* Violet energy IN the material, not on it: the base is screened with
     * violet before shading, so every ramp step carries the light. */
    tint: '#3b2c56', tintAmt: 0.44, desat: 0.10, lift: -0.02,
    glowInto: '#7b4fd0', glowAmt: 0.22,
    trim: '#9a7fd8', gem: '#c8a8ff', rune: '#c8a8ff', energy: '#c8a8ff',
    grow: 3, ornament: 3, sheen: 3, aura: 'glint', outlineTint: 0.14,
  },
  LEGENDARY: {
    label: 'Legendary', colour: '#e8c37d',
    /* Blackened steel and gold. The metal is crushed toward near-black so the
     * gold has somewhere to be bright, and embers drift off the silhouette. */
    tint: '#17141c', tintAmt: 0.52, desat: 0.22, lift: -0.04,
    glowInto: '#c0641e', glowAmt: 0.10,
    trim: '#e8c37d', gem: '#ffd98a', rune: '#ff9d4a', energy: '#ff9d4a',
    grow: 4, ornament: 4, sheen: 3, aura: 'ember', outlineTint: 0.16,
  },
  MYTHIC: {
    label: 'Mythic', colour: '#ff6a7a',
    /* The material is wrong. Voids are punched clean through the body, a
     * fracture runs corner to corner, and red light leaks out of both. This is
     * the only tier that removes matter rather than adding to it. */
    tint: '#180f1c', tintAmt: 0.62, desat: 0.30, lift: -0.06,
    glowInto: '#9a1030', glowAmt: 0.16,
    trim: '#ff6a7a', gem: '#ff4a5f', rune: '#ff6a7a', energy: '#ff6a7a',
    grow: 5, ornament: 5, sheen: 3, aura: 'void', outlineTint: 0.18,
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
    /* How far the outline is allowed to grow. Read by silhouette(). */
    grow: d.grow,
    ornament: d.ornament,
    sheen: d.sheen,
    aura: d.aura,
    animated,
    frames: animated ? ANIM_FRAMES : 1,
    /* The three treatments that make a drop feel authored rather than rolled.
     * Deriving them from the ornament level rather than listing them again
     * means a seventh tier inherits them without a second edit. */
    crystal: d.ornament >= 4,
    pennant: d.ornament >= 4,
    engrave: d.ornament >= 4,
    history: d.ornament >= 4,
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
/* ---------------- the fifteen-colour budget ----------------
 * docs/08-art-direction.md is not decoration: fifteen colours plus transparent,
 * per sprite, and a sprite over budget is a bug. The glyph contract above names
 * twenty-eight slots, and while no single sprite uses all of them, a Legendary
 * pair of sabres used seventeen — body ramp, haft ramp, trim ramp, gem ramp,
 * bone, specular, rune and its pulse — which is over.
 *
 * The fix is not to delete a glyph, because then a shape that needs it renders
 * a hole. It is to MERGE the two nearest colours until the budget is met, which
 * is exactly what an artist does when they run out of palette entries: the two
 * steps that were nearly the same become the same, the ramps get shorter, and
 * the sprite gets more coherent rather than less.
 *
 * Outline and specular are exempt. Those two are the whole readability of a
 * sprite — merge the outline into the shadow and the silhouette dissolves — so
 * they are pinned and everything else negotiates around them.
 */
const BUDGET = 15;
const PINNED = ['o', 'W'];

/* Redmean: cheap, and markedly better than raw RGB distance at not merging a
 * dark blue into a dark red, which is the one merge that would be visible. */
function colourDist(a, b) {
  const A = parseHex(a), B = parseHex(b);
  const rm = (A[0] + B[0]) / 2;
  const dr = A[0] - B[0], dg = A[1] - B[1], db = A[2] - B[2];
  return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db;
}

function fitPalette(pal) {
  const glyphs = Object.keys(pal);
  const uniq = [];
  for (const g of glyphs) if (pal[g] && !uniq.includes(pal[g])) uniq.push(pal[g]);
  if (uniq.length <= BUDGET) return pal;
  const pinnedHex = new Set(PINNED.map(g => pal[g]).filter(Boolean));
  /* How many glyphs point at each colour, so a merge keeps the colour that is
   * carrying more of the sprite and retires the one that is carrying less. */
  const weight = new Map();
  for (const g of glyphs) if (pal[g]) weight.set(pal[g], (weight.get(pal[g]) || 0) + 1);
  const live = uniq.slice();
  const remap = new Map();
  while (live.length > BUDGET) {
    let best = Infinity, bi = -1, bj = -1;
    for (let i = 0; i < live.length; i++) {
      for (let j = i + 1; j < live.length; j++) {
        if (pinnedHex.has(live[i]) && pinnedHex.has(live[j])) continue;
        const d = colourDist(live[i], live[j]);
        if (d < best) { best = d; bi = i; bj = j; }
      }
    }
    if (bi < 0) break;
    /* Survivor: whichever is pinned, else whichever more glyphs depend on. */
    let keep = live[bi], drop = live[bj];
    if (pinnedHex.has(drop) || (!pinnedHex.has(keep)
        && (weight.get(drop) || 0) > (weight.get(keep) || 0))) {
      keep = live[bj]; drop = live[bi];
    }
    remap.set(drop, keep);
    weight.set(keep, (weight.get(keep) || 0) + (weight.get(drop) || 0));
    live.splice(live.indexOf(drop), 1);
  }
  const resolve = (c) => { let v = c; const seen = new Set(); while (remap.has(v) && !seen.has(v)) { seen.add(v); v = remap.get(v); } return v; };
  const out = {};
  for (const g of glyphs) out[g] = pal[g] ? resolve(pal[g]) : pal[g];
  return out;
}

const paletteCache = new Map();

export function rarityPalette(material, rarity) {
  const key = `${material}:${normaliseRarity(rarity)}`;
  const hit = paletteCache.get(key);
  if (hit) return hit;
  const built = fitPalette(buildRarityPalette(material, rarity));
  if (paletteCache.size >= 256) paletteCache.delete(paletteCache.keys().next().value);
  paletteCache.set(key, built);
  return built;
}

/* How many distinct colours a given material/rarity pair actually spends.
 * The harness reads this; so should anyone adding a glyph. */
export function paletteBudget(material, rarity) {
  const pal = rarityPalette(material, rarity);
  const uniq = new Set(Object.values(pal).filter(Boolean));
  return { used: uniq.size, budget: BUDGET, ok: uniq.size <= BUDGET };
}

function buildRarityPalette(material, rarity) {
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
    /* Authored PLAIN. A Common sword is a bar of iron with a straight guard and
     * nothing else, because the growth table below has to have somewhere to go:
     * if the base silhouette already has wings then Legendary has no move left
     * except turning yellow, which is the failure this file exists to fix. */
    mat: 'steel', gem: [11, 15],
    grid: [
      blank(), mid('oo'), mid('oBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'), mid('oBBBBo'),
      mid('o' + rep('g', 8) + 'o'),
      mid('o' + rep('g', 4) + 'o'),
      mid('osso'), mid('osso'), mid('osso'), mid('osso'),
      mid('oggggo'), mid('oggo'), mid('oo'),
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
      row(7, 'o' + rep('m', 8) + 'o'),
      mid('o' + rep('m', 4) + 'ee' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 4) + 'ee' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 4) + 'ee' + rep('m', 4) + 'o'),
      mid('o' + rep('m', 10) + 'o'),
      row(7, 'o' + rep('m', 8) + 'o'),
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
 * SILHOUETTE GROWTH
 * ================================================================
 * The headline of this pass, and the thing the brief actually asked for:
 * rarity must be readable before the name is. Colour cannot carry that. In a
 * near-black frame at 24px, against a palette that is deliberately desaturated,
 * hue is the weakest channel we have — and it is the channel a colour-blind
 * player does not have at all. The outline is the strong one.
 *
 * So each tier GROWS the object. The stamps below are authored per shape and
 * are cumulative: a Legendary applies levels 1 through 4 in order, so the
 * quillons a Rare grew are still there under the wings a Legendary adds. That
 * is what makes the ladder read as one object maturing rather than as five
 * unrelated drawings.
 *
 * A stamp is [y, x, run]; '.' inside a run means "leave what was there", the
 * same contract row() uses. Stamps are applied to the RAW grid, before rim and
 * before ornament, so added matter gets shaded by exactly the same pass as
 * authored matter and there is no seam where the growth starts.
 *
 * Shapes with no entry fall through to growGeneric(), which derives a pair of
 * mirrored shoulder tabs and a crest from the silhouette itself. It is less
 * characterful than an authored entry and it is meant to be: it exists so a
 * shape added next week is never stuck at Common-shaped.
 */
const GROWTH = {
  /* A Common sword is a bar with a straight guard. Then: the guard widens,
   * the quillons sweep up, wings and horns grow off them. Four silhouettes
   * you can tell apart in a thumbnail with the colour turned off. */
  sword: {
    2: [[15, 5, 'ogg'], [15, 16, 'ggo'], [16, 7, 'ogg'], [16, 14, 'ggo']],
    3: [[13, 4, 'ooo'], [14, 4, 'ogg'], [15, 4, 'oggg'],
        [13, 17, 'ooo'], [14, 16, 'ggo'], [15, 16, 'gggo'],
        [22, 9, 'oggggo'], [23, 10, 'oooo']],
    4: [[10, 3, 'oo'], [11, 3, 'ogo'], [12, 3, 'ogo'],
        [10, 19, 'oo'], [11, 18, 'ogo'], [12, 18, 'ogo'],
        [12, 8, 'oBBBBBBo'], [13, 8, 'oBBBBBBo']],
    5: [[8, 2, 'oo'], [9, 2, 'ogo'], [10, 2, 'ogo'],
        [8, 20, 'oo'], [9, 19, 'ogo'], [10, 19, 'ogo']],
  },
  dagger: {
    2: [[15, 5, 'ogg'], [15, 16, 'ggo']],
    3: [[16, 7, 'ogo'], [16, 14, 'ogo']],
    4: [[12, 7, 'oo'], [13, 7, 'oB'], [12, 15, 'oo'], [13, 15, 'Bo'],
        [21, 9, 'oggggo'], [22, 10, 'oooo']],
    5: [[3, 11, 'oo'], [2, 11, 'oo']],
  },
  sabers: {
    2: [[18, 2, 'oggggo'], [18, 16, 'oggggo']],
    3: [[1, 4, 'oo'], [1, 18, 'oo']],
    4: [[22, 3, 'oggo'], [22, 17, 'oggo'], [23, 4, 'oo'], [23, 18, 'oo']],
    5: [[0, 4, 'oo'], [0, 18, 'oo']],
  },
  spear: {
    2: [[3, 7, 'oB'], [3, 16, 'Bo'], [4, 7, 'oB'], [4, 16, 'Bo']],
    3: [[7, 6, 'oggggggggggo']],
    4: [[6, 6, 'og'], [6, 16, 'go'], [5, 6, 'o'], [5, 17, 'o']],
    5: [[5, 5, 'og'], [5, 17, 'go'], [4, 5, 'o'], [4, 18, 'o']],
  },
  lance: {
    2: [[9, 3, 'ogg'], [9, 18, 'ggo'], [10, 4, 'ogg'], [10, 17, 'ggo']],
    3: [[8, 4, 'oB'], [8, 18, 'Bo']],
    4: [[11, 4, 'ogg'], [11, 17, 'ggo'], [12, 4, 'o'], [12, 19, 'o']],
    5: [[7, 5, 'oB'], [7, 17, 'Bo'], [6, 6, 'o'], [6, 17, 'o']],
  },
  /* The axe is the one shape that is asymmetric by construction, so it grows
   * asymmetrically too: the bit deepens first, and only at Epic does the
   * second bit appear on the back of the head. */
  axe: {
    2: [[2, 14, 'BBBBBo'], [9, 14, 'BBBBBo']],
    3: [[4, 5, 'oBBBB'], [5, 4, 'oBBBBB'], [6, 4, 'oBBBBB'], [7, 5, 'oBBBB'],
        [8, 5, 'oBBo']],
    4: [[1, 16, 'oo'], [0, 17, 'oo'], [10, 15, 'oo'], [11, 16, 'oo']],
    5: [[0, 19, 'oo'], [1, 18, 'ogo'], [12, 17, 'oo'], [13, 18, 'oo']],
  },
  hammer: {
    2: [[0, 6, 'oooooooooooo'], [1, 5, 'oBBBBBBBBBBBBo']],
    3: [[3, 3, 'ooo'], [4, 3, 'oBB'], [5, 3, 'oBB'], [6, 3, 'ooo'],
        [3, 18, 'ooo'], [4, 18, 'BBo'], [5, 18, 'BBo'], [6, 18, 'ooo']],
    4: [[0, 3, 'ooo'], [1, 3, 'oB'], [0, 18, 'ooo'], [1, 19, 'Bo'],
        [9, 5, 'oo'], [9, 17, 'oo']],
    5: [[1, 2, 'ooo'], [2, 2, 'oBB'], [3, 2, 'oBB'], [4, 2, 'oo'],
        [1, 19, 'ooo'], [2, 19, 'BBo'], [3, 19, 'BBo'], [4, 20, 'oo']],
  },
  staff: {
    2: [[2, 5, 'og'], [2, 17, 'go']],
    3: [[1, 5, 'o'], [1, 18, 'o'], [5, 6, 'og'], [5, 16, 'go']],
    4: [[0, 7, 'oo'], [0, 15, 'oo'], [1, 7, 'og'], [1, 15, 'go']],
    5: [[6, 5, 'og'], [6, 17, 'go'], [7, 4, 'o'], [7, 19, 'o']],
  },
  bow: {
    2: [[0, 9, 'oso'], [0, 13, 'o'], [1, 13, 'w'],
        [22, 9, 'oso'], [22, 13, 'o'], [21, 13, 'w']],
    3: [[3, 6, 'os'], [4, 5, 'os'], [5, 4, 'os'],
        [18, 5, 'os'], [19, 6, 'os'], [20, 7, 'os'],
        [9, 3, 'og'], [10, 3, 'og'], [11, 3, 'og'], [12, 3, 'og'], [13, 3, 'og']],
    /* An arrow on the string. It is the one detail that makes a bow read as a
     * bow at 24px, it is asymmetric, and it is the sort of thing you only put
     * on the weapon you actually carry. */
    4: [[11, 14, 'sssgggo'], [10, 17, 'ooo'], [12, 17, 'ooo'],
        [10, 14, 'o'], [12, 14, 'o'],
        [1, 8, 'og'], [21, 8, 'og'], [8, 3, 'o'], [14, 3, 'o']],
    5: [[7, 3, 'og'], [15, 3, 'og'], [6, 3, 'o'], [16, 3, 'o'],
        [2, 5, 'os'], [20, 5, 'os']],
  },
  shield: {
    2: [[2, 3, 'o'], [3, 3, 'oB'], [2, 20, 'o'], [3, 19, 'Bo']],
    3: [[1, 4, 'oooooooooooooooo'], [2, 3, 'oBBBBBBBBBBBBBBBBo']],
    4: [[0, 6, 'oggo'], [0, 14, 'oggo'], [1, 6, 'oggo'], [1, 14, 'oggo'],
        [18, 10, 'oBBo'], [19, 11, 'oo']],
    5: [[4, 2, 'oB'], [5, 2, 'oB'], [4, 20, 'Bo'], [5, 20, 'Bo']],
  },
  helm: {
    2: [[2, 8, 'oggggggo'], [1, 9, 'oggggo']],
    3: [[0, 10, 'oggo'], [1, 5, 'ogo'], [1, 16, 'ogo'], [2, 5, 'og'], [2, 16, 'go']],
    4: [[0, 4, 'oo'], [1, 3, 'ogo'], [2, 3, 'ogo'], [3, 4, 'oo'],
        [0, 18, 'oo'], [1, 18, 'ogo'], [2, 18, 'ogo'], [3, 18, 'oo'],
        [16, 8, 'oggggggo'], [17, 9, 'ooooo']],
    5: [[0, 2, 'oo'], [1, 1, 'ogo'], [0, 20, 'oo'], [1, 20, 'ogo']],
  },
  crown: {
    2: [[9, 7, 'OO'], [10, 6, 'OggO'], [9, 15, 'OO'], [10, 15, 'OggO']],
    3: [[5, 11, 'oo'], [6, 10, 'oggo'], [7, 10, 'oggo'],
        [7, 5, 'oo'], [8, 4, 'oggo'], [7, 17, 'oo'], [8, 17, 'oggo']],
    4: [[3, 11, 'oo'], [4, 10, 'oggo'], [5, 10, 'oggo'],
        [6, 3, 'oo'], [7, 2, 'ogo'], [6, 19, 'oo'], [7, 19, 'ogo'],
        [16, 3, 'oyyyyyyyyyyyyyyyyo'], [17, 3, 'oooooooooooooooooo']],
    5: [[1, 11, 'oo'], [2, 10, 'oggo'], [4, 2, 'oo'], [5, 1, 'ogo'],
        [4, 20, 'oo'], [5, 20, 'ogo']],
  },
  /* Armour grows the way armour actually grows: a plain cuirass gains
   * pauldrons, then a gorget, then a fauld and a high collar. All of it lands
   * on the hero overlay too, which is the point of doing it here. */
  plate: {
    2: [[4, 1, 'oBBo'], [4, 19, 'oBBo'], [5, 1, 'oB'], [5, 21, 'Bo'],
        [6, 1, 'oB'], [6, 21, 'Bo']],
    3: [[3, 0, 'oooo'], [4, 0, 'oBB'], [5, 0, 'oB'], [6, 0, 'oB'], [7, 0, 'oo'],
        [3, 20, 'oooo'], [4, 21, 'BBo'], [5, 22, 'Bo'], [6, 22, 'Bo'], [7, 22, 'oo'],
        [2, 9, 'oBBBBo'], [3, 8, 'oBBBBBBo']],
    4: [[2, 0, 'oooo'], [3, 0, 'ogg'], [2, 20, 'oooo'], [3, 21, 'ggo'],
        [1, 9, 'oggo'], [20, 6, 'oggggggggggo'], [21, 7, 'ooooooooo']],
    5: [[0, 10, 'oo'], [1, 0, 'ooo'], [1, 21, 'ooo']],
  },
  greaves: {
    2: [[4, 3, 'ooooo'], [5, 2, 'oBBBBBo'], [4, 15, 'ooooo'], [5, 14, 'oBBBBBo']],
    3: [[3, 4, 'ooo'], [4, 2, 'oBo'], [3, 16, 'ooo'], [4, 17, 'oBo'],
        [19, 2, 'oggggggo'], [19, 14, 'oggggggo']],
    4: [[2, 4, 'oo'], [3, 2, 'ogo'], [2, 16, 'oo'], [3, 17, 'ogo'],
        [20, 3, 'oggggo'], [20, 15, 'oggggo'], [21, 4, 'oooo'], [21, 16, 'oooo']],
    5: [[1, 3, 'oo'], [2, 2, 'ogo'], [1, 17, 'oo'], [2, 17, 'ogo']],
  },
  boots: {
    2: [[5, 2, 'oBBBBBBo'], [5, 14, 'oBBBBBBo']],
    3: [[4, 3, 'oBBBBo'], [4, 15, 'oBBBBo'], [3, 4, 'oooo'], [3, 16, 'oooo'],
        [19, 1, 'oBBBBBBBo'], [19, 13, 'oBBBBBBBo'], [20, 1, 'ooooooooo'], [20, 13, 'ooooooooo']],
    4: [[2, 4, 'oo'], [3, 3, 'ogo'], [2, 16, 'oo'], [3, 16, 'ogo'],
        [18, 0, 'oBBBBBBBBBo'], [19, 0, 'oggggggggo'], [18, 12, 'oBBBBBBBBBo'], [19, 12, 'oggggggggo']],
    5: [[1, 3, 'oo'], [2, 2, 'ogo'], [1, 17, 'oo'], [2, 17, 'ogo']],
  },
  gauntlets: {
    2: [[4, 2, 'ooooooo'], [4, 14, 'ooooooo']],
    3: [[3, 3, 'ooooo'], [4, 1, 'oBBBBBBBo'], [3, 15, 'ooooo'], [4, 13, 'oBBBBBBBo'],
        [15, 1, 'ooooooooo'], [15, 13, 'ooooooooo']],
    4: [[2, 3, 'oo'], [3, 2, 'ogo'], [2, 16, 'oo'], [3, 16, 'ogo'],
        [15, 1, 'oggggggo'], [15, 13, 'oggggggo'], [16, 2, 'ooooo'], [16, 14, 'ooooo']],
    5: [[1, 2, 'oo'], [2, 1, 'ogo'], [1, 17, 'oo'], [2, 17, 'ogo']],
  },
  /* Cloth hand wraps: the generic fallback could not separate Rare from Epic
   * here, because the widest row of a PAIR of things has a gap down the middle
   * and the level-3 tabs land on top of the level-1 nubs. Authored instead. */
  wraps: {
    2: [[4, 3, 'occco'], [4, 15, 'occco']],
    3: [[3, 4, 'occo'], [3, 16, 'occo']],
    4: [[2, 5, 'oo'], [2, 17, 'oo'],
        [19, 3, 'occo'], [19, 15, 'occo'], [20, 4, 'oo'], [20, 16, 'oo']],
    5: [[1, 5, 'oo'], [1, 17, 'oo'], [21, 4, 'oo'], [21, 16, 'oo']],
  },
  hood: {
    2: [[2, 8, 'oCCCCo'], [12, 4, 'oCCCCCCCCCCCCCCo']],
    3: [[1, 9, 'oCCo'], [13, 3, 'oCCCCCCCCCCCCCCCCo'], [14, 3, 'oc'], [14, 20, 'co']],
    4: [[0, 10, 'oo'], [1, 4, 'oo'], [1, 18, 'oo'], [2, 3, 'ogo'], [2, 18, 'ogo'],
        [17, 4, 'ovvvvvvvvvvvvvvo'], [18, 5, 'oooooooooooo']],
    5: [[0, 3, 'oo'], [0, 19, 'oo'], [1, 2, 'ogo'], [1, 19, 'ogo']],
  },
  robe: {
    2: [[1, 9, 'oCCCCo'], [20, 2, 'ovvvvvvvvvvvvvvvvvvo']],
    3: [[0, 10, 'oCCo'], [21, 2, 'oooooooooooooooooooo'],
        [5, 5, 'oc'], [5, 17, 'co'], [6, 4, 'oc'], [6, 18, 'co']],
    4: [[7, 3, 'oc'], [7, 19, 'co'], [8, 3, 'og'], [8, 19, 'go'],
        [21, 1, 'ovvvvvvvvvvvvvvvvvvvvo'], [22, 2, 'oooooooooooooooooooo']],
    5: [[9, 2, 'oc'], [9, 20, 'co'], [10, 2, 'oo'], [10, 21, 'oo']],
  },
  cloak: {
    2: [[3, 8, 'oggggggo'], [20, 2, 'ovvvvvvvvvvvvvvvvvvo']],
    3: [[2, 9, 'oggggo'], [21, 2, 'oooooooooooooooooooo'],
        [6, 4, 'oc'], [6, 18, 'co']],
    4: [[1, 10, 'oggo'], [7, 3, 'oc'], [7, 19, 'co'], [8, 3, 'og'], [8, 19, 'go'],
        [21, 1, 'ovvvvvvvvvvvvvvvvvvvvo'], [22, 2, 'oooooooooooooooooooo']],
    5: [[0, 11, 'oo'], [9, 2, 'oc'], [9, 20, 'co'], [10, 2, 'oo'], [10, 21, 'oo']],
  },
  chest: {
    2: [[3, 8, 'occcccco'], [17, 4, 'ovvvvvvvvvvvvvvo']],
    3: [[2, 9, 'occcco'], [18, 5, 'oooooooooooo'],
        [5, 2, 'oc'], [5, 20, 'co']],
    4: [[1, 10, 'occo'], [4, 2, 'oc'], [4, 20, 'co'], [5, 1, 'og'], [5, 21, 'go'],
        [18, 4, 'ovvvvvvvvvvvvvvo'], [19, 5, 'oooooooooooo']],
    5: [[0, 11, 'oo'], [3, 1, 'oc'], [3, 21, 'co'], [6, 1, 'oo'], [6, 22, 'oo']],
  },
  /* Jewellery cannot grow outward much before it stops being jewellery, so it
   * grows UPWARD into a setting: a claw mount, then a spire, then wings. */
  ring: {
    2: [[3, 10, 'oggo'], [6, 6, 'og'], [6, 16, 'go']],
    3: [[2, 11, 'oo'], [3, 9, 'ogggo'], [5, 7, 'og'], [5, 16, 'go'],
        [7, 5, 'og'], [7, 17, 'go']],
    4: [[0, 11, 'oo'], [1, 10, 'ogo'], [2, 10, 'ogo'],
        [4, 6, 'og'], [4, 17, 'go'], [3, 5, 'oo'], [3, 18, 'oo'],
        [16, 8, 'oggggggo'], [17, 9, 'ooooo']],
    5: [[1, 7, 'oo'], [2, 6, 'ogo'], [1, 16, 'oo'], [2, 16, 'ogo']],
  },
  amulet: {
    2: [[9, 7, 'oggggggo'], [15, 7, 'oggggggo']],
    3: [[8, 6, 'oggggggggo'], [16, 8, 'oggggo'], [10, 5, 'og'], [10, 17, 'go']],
    4: [[7, 5, 'og'], [7, 17, 'go'], [8, 4, 'og'], [8, 18, 'go'],
        [9, 4, 'oo'], [9, 18, 'oo'], [17, 9, 'oggggo'], [18, 10, 'oooo']],
    5: [[6, 3, 'og'], [6, 19, 'go'], [7, 2, 'oo'], [7, 20, 'oo']],
  },
  orb: {
    2: [[18, 5, 'oggggggggggggo'], [19, 5, 'oggggggggggggo']],
    3: [[16, 6, 'oggggggggo'], [17, 7, 'oggggggo'],
        [8, 3, 'og'], [8, 18, 'go'], [9, 3, 'og'], [9, 18, 'go']],
    4: [[7, 2, 'og'], [7, 19, 'go'], [10, 2, 'og'], [10, 19, 'go'],
        [6, 3, 'oo'], [6, 19, 'oo'], [11, 3, 'oo'], [11, 19, 'oo'],
        [20, 4, 'oggggggggggggggo'], [21, 5, 'ooooooooooooo']],
    5: [[5, 1, 'oo'], [12, 1, 'oo'], [5, 21, 'oo'], [12, 21, 'oo']],
  },
  relic: {
    /* The two loose motes used to be authored into the base grid, which meant
     * a Common relic shipped with two unexplained pixels floating beside it.
     * They belong to the tier, not to the shape. */
    2: [[8, 6, 'ommmmmmmmmmo'], [13, 6, 'ommmmmmmmmmo'], [8, 3, 'm'], [13, 20, 'm']],
    3: [[7, 5, 'ommmmmmmmmmmmo'], [14, 5, 'ommmmmmmmmmmmo'],
        [3, 11, 'oo'], [18, 11, 'oo']],
    4: [[6, 3, 'oo'], [7, 2, 'omo'], [8, 2, 'omo'], [9, 3, 'oo'],
        [6, 19, 'oo'], [7, 19, 'omo'], [8, 19, 'omo'], [9, 19, 'oo'],
        [2, 11, 'oo'], [19, 11, 'oo']],
    5: [[12, 2, 'oo'], [13, 1, 'omo'], [12, 19, 'oo'], [13, 19, 'omo']],
  },
  tome: {
    2: [[4, 3, 'oooooooooooooooooo'], [17, 3, 'oooooooooooooooooo']],
    3: [[3, 4, 'oooooooooooooooo'], [4, 2, 'ovvcccccccccccccccco'],
        [18, 3, 'oggggggggggggggggo'], [19, 4, 'oooooooooooooooo']],
    4: [[2, 5, 'oggggggggggggo'], [3, 3, 'oggggggggggggggggo'],
        [20, 4, 'oggggggggggggggo'], [21, 5, 'oooooooooooooo'],
        [8, 21, 'og'], [12, 21, 'og']],
    5: [[1, 6, 'oo'], [1, 16, 'oo'], [2, 2, 'oo'], [2, 20, 'oo']],
  },
};

/* Stamp a list of [y, x, run] onto a cell grid. '.' leaves the cell alone. */
function stamp(cells, list) {
  if (!list) return;
  const h = cells.length, w = widthOf(cells);
  for (const [y, x, run] of list) {
    if (y < 0 || y >= h) continue;
    const r = cells[y];
    for (let k = 0; k < run.length; k++) {
      const ch = run[k], px = x + k;
      if (ch === '.' || px < 0 || px >= w) continue;
      r[px] = ch;
    }
  }
}

/* Where the object is widest, and where its crown is. Both derived from the
 * silhouette rather than from a table, so they are correct for an off-centre
 * shape — a bow, an axe — as well as for a symmetrical one. */
function silhouetteExtents(cells) {
  const h = cells.length, w = widthOf(cells);
  let wideY = -1, wideA = -1, wideB = -1, topY = -1, topA = -1, topB = -1;
  for (let y = 0; y < h; y++) {
    let a = -1, b = -1;
    for (let x = 0; x < w; x++) {
      if (cells[y][x] === '.' || cells[y][x] === ' ') continue;
      if (a < 0) a = x;
      b = x;
    }
    if (a < 0) continue;
    if (topY < 0) { topY = y; topA = a; topB = b; }
    if (b - a > wideB - wideA) { wideY = y; wideA = a; wideB = b; }
  }
  return { wideY, wideA, wideB, topY, topA, topB };
}

/* Level 1, and it runs on EVERY shape, authored table or not.
 *
 * Uncommon has to be separable from Common by outline alone or the bottom of
 * the ladder is two rungs painted the same, which is where this file started.
 * The move is the smallest one available: a single pixel of fitting at each
 * end of the widest row, so the shape squares up without acquiring character
 * it has not earned yet. Four pixels. It is enough — at 24px four pixels on
 * the widest axis is a visible change of outline.
 */
function growNubs(cells) {
  const w = widthOf(cells);
  const { wideY, wideA, wideB } = silhouetteExtents(cells);
  if (wideY < 0) return;
  if (wideA >= 1) cells[wideY][wideA - 1] = 'o';
  if (wideB <= w - 2) cells[wideY][wideB + 1] = 'o';
  const above = cells[wideY - 1];
  if (above) {
    if (wideA >= 1 && above[wideA - 1] === '.') above[wideA - 1] = 'o';
    if (wideB <= w - 2 && above[wideB + 1] === '.') above[wideB + 1] = 'o';
  }
}

/* The fallback. A shape with no authored growth still has to escalate, or an
 * item added to the catalogue next week is stuck looking Common at Legendary —
 * which is precisely the failure mode this pass exists to prevent.
 *
 * Three moves, all derived from the silhouette rather than from a table:
 * shoulder tabs just outside the widest row, a crest of spikes above the
 * crown, and a pair of outer horns. Less characterful than an authored entry
 * and meant to be — it is a floor, not a ceiling.
 */
function growGeneric(cells, level) {
  if (level < 2) return;
  const h = cells.length, w = widthOf(cells);
  const { wideY, wideA, wideB, topY, topA, topB } = silhouetteExtents(cells);
  if (wideY < 0) return;
  /* Level 2: the nubs become a rail — the same pixel repeated on the row
   * under the widest one, which squares the shoulder off rather than leaving
   * two dots sticking out of a curve. */
  if (level >= 2) {
    const below = cells[wideY + 1];
    if (below) {
      if (wideA >= 1 && below[wideA - 1] === '.') below[wideA - 1] = 'o';
      if (wideB <= w - 2 && below[wideB + 1] === '.') below[wideB + 1] = 'o';
    }
  }
  if (level < 3) return;
  /* Shoulder tabs. Only where there is room — a shape that already fills the
   * box does not get a tab pushed off the edge and silently clipped. */
  if (wideA >= 2 && wideB <= w - 3) {
    stamp(cells, [
      [wideY, wideA - 2, 'og'], [wideY, wideB + 1, 'go'],
      [wideY - 1, wideA - 2, 'oo'], [wideY - 1, wideB + 1, 'oo'],
      [wideY + 1, wideA - 2, 'oo'], [wideY + 1, wideB + 1, 'oo'],
    ]);
  }
  if (level < 4 || topY < 1) return;
  /* A crest of three spikes above the crown of the shape — but only on columns
   * that have matter directly under them. A spike over a gap is not a spike,
   * it is one loose pixel, and one loose pixel beside a sprite is the single
   * most common way procedural pixel art gives itself away. */
  const cx = Math.round((topA + topB) / 2);
  for (const x of [cx - 3, cx, cx + 3]) {
    if (x < 0 || x >= w) continue;
    const under = cells[topY][x];
    if (under === '.' || under === ' ') continue;
    cells[topY - 1][x] = 'o';
  }
  if (level < 5) return;
  /* Mythic: the tabs become horns that reach past the shape entirely. */
  let horned = false;
  if (wideA >= 4 && wideB <= w - 5 && wideY >= 2) {
    stamp(cells, [
      [wideY, wideA - 4, 'og'], [wideY, wideB + 3, 'go'],
      [wideY - 1, wideA - 4, 'og'], [wideY - 1, wideB + 3, 'go'],
      [wideY - 2, wideA - 4, 'oo'], [wideY - 2, wideB + 3, 'oo'],
    ]);
    horned = true;
  }
  /* A shape already filling its box has no room for horns, and must still be
   * separable from the tier below it. It grows UPWARD instead: the crest's
   * centre spike doubles in height and the crown grows a pair of ticks. */
  if (!horned && topY >= 2) {
    const cx = Math.round((topA + topB) / 2);
    if (cells[topY][cx] !== '.' && cells[topY][cx] !== ' ') {
      cells[topY - 1][cx] = 'o';
      cells[topY - 2][cx] = 'o';
    }
    for (const x of [topA, topB]) {
      if (x < 0 || x >= w) continue;
      if (cells[topY][x] === '.' || cells[topY][x] === ' ') continue;
      cells[topY - 1][x] = 'o';
    }
  }
}

/* The stage. Cumulative, lowest level first, so the ladder reads as one object
 * maturing rather than five separate drawings. */
function silhouette(grid, shapeKey, style) {
  if (style.grow <= 0) return grid;
  const table = GROWTH[shapeKey];
  const cells = toCells(grid);
  /* Nubs first, always, so an authored level-2 stamp can bury them if it wants
   * the room. */
  growNubs(cells);
  if (!table) { growGeneric(cells, style.grow); return toRows(cells); }
  for (let lv = 2; lv <= style.grow; lv++) stamp(cells, table[lv]);
  return toRows(cells);
}

/* What the ladder actually costs in outline, per shape, as pixels of binary
 * silhouette changed between adjacent tiers. Exported because "rarity is
 * legible before the name is read" is a claim, and a claim about pixels is
 * one a harness can check rather than one an artist can assert. A zero in
 * this list is a bug: it means two tiers of that shape have the same outline.
 */
export function silhouetteSpread(shapeKey) {
  const mask = (r) => shapeGrid(shapeKey, r, { frame: 0 })
    .map(row => row.padEnd(N, '.').split('')
      .map(c => (c === '.' || c === ' ' || c === 'r' || c === 'R') ? 0 : 1).join('')).join('');
  const masks = RARITY_KEYS.map(mask);
  const steps = [];
  for (let i = 0; i + 1 < masks.length; i++) {
    let d = 0;
    for (let k = 0; k < masks[i].length; k++) if (masks[i][k] !== masks[i + 1][k]) d++;
    steps.push(d);
  }
  return { shape: shapeKey, steps, min: Math.min(...steps), total: steps.reduce((a, b) => a + b, 0) };
}

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

/* ---------------- the legendary treatments ----------------
 * A 2x2 stone and a band of trim is what a Rare gets. A Legendary has to look
 * like somebody MADE it, and then like somebody CARRIED it for a while. That
 * is four separate passes and they are deliberately not merged: engraving is
 * craft, the crystal is wealth, the pennant is allegiance, and the scar is
 * history. An item that has all four reads as an object with a past, and an
 * object with a past is the thing the player wants to keep.
 */

/* A faceted crystal, not a flat chip. Four tones in a 4x4 so it reads as a cut
 * stone with a table and a girdle rather than as a coloured square: specular
 * on the upper-left facet, base across the table, shadow under the girdle, and
 * a hard outline pixel on the lower-right where the facet turns away. */
function crystal(cells, anchor) {
  if (!anchor) return false;
  const w = widthOf(cells), h = cells.length;
  let [x, y] = anchor;
  x -= 1; y -= 1;
  if (y < 0 || x < 0 || y + 3 >= h || x + 3 >= w) return false;
  /* Refuse to float. If the anchor's own pixel is empty the shape does not
   * have a socket there, and a gem in mid-air is worse than no gem. */
  if (cells[y + 1][x + 1] === '.' || cells[y + 1][x + 1] === 'o') return false;
  const face = [
    '.mm.',
    'mMMn',
    'mMnn',
    '.nn.',
  ];
  for (let dy = 0; dy < 4; dy++) {
    for (let dx = 0; dx < 4; dx++) {
      const ch = face[dy][dx];
      if (ch === '.') continue;
      cells[y + dy][x + dx] = ch;
    }
  }
  /* The girdle: one outline pixel each side, which is what separates a set
   * stone from a painted-on one. */
  if (x - 1 >= 0) cells[y + 1][x - 1] = 'o';
  if (x + 4 < w) cells[y + 2][x + 4] = 'o';
  return true;
}

/* Chased engraving: a fine repeating chevron cut down the trim, offset row by
 * row so it reads as tooling rather than as a dotted line. Only ever cuts INTO
 * trim, never into body — engraving on bare steel at this size is noise. */
function engrave(cells, seed) {
  const w = widthOf(cells), h = cells.length;
  const rand = rng((seed || 1) ^ 0x1b873593);
  const phase = Math.floor(rand() * 3);
  let cut = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (cells[y][x] !== 'g') continue;
      if (((x + y * 2 + phase) % 3) !== 0) continue;
      cells[y][x] = 'y';
      cut++;
    }
  }
  return cut;
}

/* A pennant: a short cloth streamer hanging off the object, with a torn notch
 * in its lower edge. It hangs on ONE side only, and which side is seeded, so
 * two Legendaries of the same shape are not the same drawing mirrored.
 *
 * The anchor is found rather than authored: the longest run of trim on the
 * object is its guard, collar or crossbar, and that is where a banner is tied
 * in every century that had banners. Ties go to the LOWER row, because on a
 * weapon the fitting nearest the hand is the one you tie to and the one an
 * ornament band higher up the blade is not.
 */
function pennant(cells, seed, frame, frames) {
  const w = widthOf(cells), h = cells.length;
  /* Every trim run on the object is a candidate tie point, ranked longest
   * first and, within a length, lowest first. One candidate is not enough:
   * across thirty-two shapes the widest fitting is regularly boxed in on both
   * sides, and a pennant that gives up there is a Legendary that looks Rare.
   * Leave six rows of hang below the anchor, or the banner is a stub. */
  const cands = [];
  for (let y = 1; y < h - 6; y++) {
    let a = -1, b = -1;
    const push = () => { if (a >= 0 && b - a >= 2) cands.push([y, a, b]); };
    for (let x = 0; x < w; x++) {
      const ch = cells[y][x];
      if (ch !== 'g' && ch !== 'G' && ch !== 'y') { push(); a = -1; b = -1; continue; }
      if (a < 0) a = x;
      b = x;
    }
    push();
  }
  if (!cands.length) return false;
  cands.sort((p, q) => (q[2] - q[1]) - (p[2] - p[1]) || q[0] - p[0]);

  const rand = rng((seed || 1) ^ 0x27d4eb2f);
  const wantLeft = rand() < 0.5;
  /* The sway. Two columns of travel across the cycle, which is a real shape
   * change per frame rather than a brightness change — the rule sprites.js
   * states for characters and which holds just as hard for a banner. */
  const swayTable = [0, 0, 1, 1, 0, -1];
  const sway = frames > 1 ? swayTable[frame % swayTable.length] : 0;
  const torn = 2 + Math.floor(rand() * 3);

  /* Plan, then commit. A streamer drawn straight into the grid leaves one or
   * two orphan pixels wherever the object happens to be in the way, and two
   * orphan pixels beside a sprite read as dirt on the screen rather than as
   * cloth. So the whole banner is laid out first and written only if it comes
   * out whole: contiguous from the anchor down, and long enough to read as a
   * banner rather than as a tag. */
  function hang(top, a, b, left) {
    const x0 = left ? a - 4 : b + 1;
    /* One column of slack each side is required, not optional: the streamer
     * sways a pixel per frame, and a sway that clips against the box edge
     * stops being a sway and becomes a flicker. */
    if (x0 < 1 || x0 + 3 >= w) return null;
    const bottom = Math.min(h - 2, top + 7);
    const plan = [];
    for (let y = top; y <= bottom; y++) {
      const d = y - top;
      const bend = Math.round(sway * (d / Math.max(1, bottom - top)));
      /* The torn corner: the streamer loses its lower outer pixel from `torn`
       * rows down, so the tip is a ragged point and not a rectangle. */
      const width = d >= bottom - top - torn ? 2 : 3;
      const rowPlan = [];
      let ok = true;
      for (let k = 0; k < width; k++) {
        const px = x0 + k + bend;
        if (px < 0 || px >= w || cells[y][px] !== '.') { ok = false; break; }
        rowPlan.push([px, d === 0 ? 'C' : (k === (left ? 0 : width - 1) ? 'v' : 'c')]);
      }
      if (!ok) break;
      const edge = x0 + (left ? -1 : width) + bend;
      if (edge >= 0 && edge < w && cells[y][edge] === '.') rowPlan.push([edge, 'o']);
      plan.push(rowPlan.map(e => [y, e[0], e[1]]));
    }
    return plan.length >= 5 ? plan : null;
  }

  for (const [y, a, b] of cands.slice(0, 6)) {
    for (const left of [wantLeft, !wantLeft]) {
      const plan = hang(y, a, b, left);
      if (!plan) continue;
      for (const rowPlan of plan) for (const [py, px, ch] of rowPlan) cells[py][px] = ch;
      return true;
    }
  }
  return false;
}

/* One seeded, one-sided mark. Symmetry is what makes procedural art look
 * procedural; a single asymmetric flaw is what makes a weapon look owned.
 *
 *   a chip   one body pixel bitten out of an edge, with the edge behind it
 *            turned to deep shadow so the notch has depth
 *   a repair a two-row leather binding wrapped over the haft, deliberately
 *            not centred on any fitting, because a field repair never is
 */
function history(cells, seed) {
  const w = widthOf(cells), h = cells.length;
  const rand = rng((seed || 1) ^ 0x85ebca6b);
  /* The chip. Walk the left edge of the body from a seeded row and take the
   * first outline pixel with body behind it.
   *
   * The band is deliberately the middle of the object. A notch taken out of
   * the point of a blade does not read as a chip, it reads as a blunt sword —
   * and a notch in the bottom row reads as a rendering error. */
  const lo = Math.max(1, Math.round(h * 0.25));
  const hi = Math.min(h - 2, Math.round(h * 0.80));
  const span = Math.max(1, hi - lo);
  const start = lo + Math.floor(rand() * span);
  let chipped = false;
  for (let i = 0; i < span && !chipped; i++) {
    const y = lo + ((start - lo + i) % span);
    for (let x = 1; x < w - 2; x++) {
      const ch = cells[y][x];
      if (ch !== 'o' && ch !== 'O') continue;
      const next = cells[y][x + 1];
      if (next !== 'B' && next !== 'H' && next !== 'L') break;
      cells[y][x + 1] = 'o';
      if (cells[y][x + 2] === 'B') cells[y][x + 2] = 'D';
      chipped = true;
      break;
    }
  }
  /* The repair. Find the haft — a run of 's' glyphs — and bind two rows of it
   * with leather at a seeded offset. */
  const hafts = [];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (cells[y][x] === 's') { hafts.push(y); break; }
  if (hafts.length >= 4) {
    const y0 = hafts[2 + Math.floor(rand() * (hafts.length - 3))];
    for (const y of [y0, y0 + 1]) {
      if (y < 0 || y >= h) continue;
      for (let x = 0; x < w; x++) if (cells[y][x] === 's' || cells[y][x] === 't') cells[y][x] = 'u';
    }
    /* The knot, on one side only. */
    const side = rand() < 0.5 ? -1 : 1;
    for (let x = 0; x < w; x++) {
      if (cells[y0][x] !== 'u') continue;
      const px = side < 0 ? x - 1 : x + 2;
      if (px >= 0 && px < w && cells[y0][px] === '.') cells[y0][px] = 'u';
      break;
    }
  }
  return chipped;
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
 *   4  all of the above, plus a second stone, gilded outlines, chased
 *      engraving, a faceted crystal in place of the flat one, a torn pennant
 *      and one seeded scar.
 *   5  as 4; corruption is applied separately, after the rim pass.
 */
function ornament(grid, shape, style, seed, frame) {
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
  if (style.ornament >= 4) {
    setStone(cells, shape.gem2);
    gildOutline(cells, rows);
    /* Order is load-bearing. Engraving first, so it cuts the trim the bands
     * just laid down and the gilding just widened. The pennant second, while
     * the guard is still an unbroken run of trim it can find. The crystal
     * third, so the engraving does not tool across the stone and the stone
     * does not split the guard before the pennant looks at it. The scar last,
     * because damage happens to a finished object. */
    if (style.engrave) engrave(cells, seed);
    if (style.pennant) pennant(cells, seed, frame | 0, style.frames);
    if (style.crystal && !crystal(cells, shape.gem)) crystal(cells, shape.gem2);
    if (style.history) history(cells, seed);
  }
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

  /* The stone is lit from INSIDE. A gem that only catches the surface glint is
   * a shiny pebble; a gem with a spark travelling through its facets is a gem.
   * The wave runs on x + 2y so it descends through the crystal rather than
   * sliding across it, which is what separates subsurface light from polish.
   * Confined to gem glyphs, so it never touches the body ramp. */
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ch = cells[y][x];
      if (ch !== 'm' && ch !== 'M' && ch !== 'n') continue;
      if (((x + y * 2 + f * 2) % 8) >= 2) continue;
      cells[y][x] = ch === 'M' ? 'W' : ch === 'm' ? 'M' : 'm';
    }
  }

  /* Motes rising through transparent space beside the object. Columns are
   * fixed per item and only the height changes, which is what separates an
   * ember from a twinkle — a particle that appears in a new place each frame
   * is noise, a particle that climbs is a fire.
   *
   * Epic gets three cold ones drifting; Legendary gets six and they are hot,
   * lift from the lower half where the light source is, and carry a one-pixel
   * tail. Spawning in the lower half matters: docs/09-story-bible.md §8 puts
   * the key light low, and embers that fall out of the top of the frame
   * contradict it. */
  if (style.aura === 'ember' || style.aura === 'glint') {
    const hot = style.aura === 'ember';
    const count = hot ? 6 : 3;
    const lift = hot ? h - 1 : Math.floor(h * 0.75);
    for (let i = 0; i < count; i++) {
      const col = 1 + Math.floor(rand() * Math.max(1, w - 2));
      const phase = rand();
      const t = ((f / frames) + phase) % 1;
      const y = Math.floor((h - 1) - t * lift);
      const r = cells[y];
      if (!r || r[col] !== '.') continue;
      r[col] = ((f + i) & 1) ? 'R' : 'r';
      /* The tail. One pixel of where the ember just was, dimmer, so the mote
       * has a direction of travel instead of merely a position. */
      const tail = cells[y + 1];
      if (hot && tail && tail[col] === '.') tail[col] = 'r';
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
  const frame = opts.frame || 0;
  /* silhouette -> ornament -> rim -> corrupt -> animate. The order is the
   * whole design: grow the outline before anything reads it, decorate the
   * grown outline, shade what is there, then take matter away, then move the
   * light. Reversing any two of those produces a visible artefact — ornament
   * before growth leaves fittings floating where the old edge used to be, and
   * rim before ornament leaves every fitting unlit. */
  let g = silhouette(grid, opts.shapeKey || '', style);
  g = ornament(g, shape, style, seed, frame);
  g = applyRim(g);
  g = corrupt(g, style, seed);
  g = animate(g, style, frame, seed);
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
    applyRarity(shape.grid, rarity, { shape, shapeKey, seed, frame: f }));
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
      /* The base flare. The last sixth of the column widens as it meets the
       * floor, because a beam that hits the ground and does not spread is a
       * drawn rectangle, and the eye knows it. */
      const toFloor = (h - 1 - y) / Math.max(1, h / 6);
      const flare = toFloor < 1 ? Math.round((1 - toFloor) * 3) : 0;
      /* Scanline gaps travel up one row per frame, which is the whole reason
       * the beam looks like it is flowing rather than standing still. */
      const gap = ((y + f * 2) % 7) === 0;
      for (const b of bands) {
        const a = b.alpha * fall * (gap ? 0.35 : 1);
        if (a <= 0.02) continue;
        const half = Math.min(Math.floor(w / 2), b.half + flare);
        ctx.globalAlpha = a;
        ctx.fillStyle = b.colour;
        ctx.fillRect(cx - half, y, half * 2, 1);
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

/* ---------------- the landing ----------------
 * A drop that fades up is a notification. A drop that ARRIVES is an event, and
 * arriving is three separate beats the eye can count: the fall, the moment the
 * thing hits the floor, and the settle afterwards. The two cached pieces below
 * are the middle beat — the ring the impact throws along the ground and the
 * pool of light it leaves behind.
 *
 * Both are hard-edged fillRect like everything else in this section. A soft
 * shockwave in a 16-bit frame reads as a mistake rather than as polish.
 */
const IMPACT_FRAMES = 8;
const POOL_FRAMES = 4;
const impactCache = cappedCache(96);
const poolCache = cappedCache(96);

/* The shock ring, drawn in ground perspective: an ellipse three times wider
 * than it is tall, because the floor is being seen at an angle and a circle
 * would read as a hoop standing on its edge. Higher tiers throw shards. */
export function lootImpact(rarity, opts = {}) {
  const style = rarityStyle(rarity);
  const w = Math.max(16, Math.round(opts.width || 44));
  const h = Math.max(6, Math.round(opts.height || 16));
  const frames = IMPACT_FRAMES;
  const f = ((opts.frame || 0) % frames + frames) % frames;
  const key = `${style.key}:${w}:${h}:${f}`;
  return impactCache.get(key, () => {
    const { canvas, ctx } = makeCanvas(w, h);
    const cx = (w - 1) / 2, cy = h - 3;
    const t = f / (frames - 1);
    const fade = 1 - t;
    const hot = mix(style.colour, '#ffffff', 0.75);
    const rx = 2 + t * (w / 2 - 3);
    const ry = Math.max(1, rx * 0.34);
    /* The ring itself, stepped around the ellipse at a pitch fine enough that
     * it closes at every radius and coarse enough that it stays stippled. */
    ctx.globalAlpha = Math.max(0, fade * 0.9);
    for (let a = 0; a < Math.PI * 2; a += 0.11) {
      const px = Math.round(cx + Math.cos(a) * rx);
      const py = Math.round(cy + Math.sin(a) * ry);
      if (px < 0 || py < 0 || px >= w || py >= h) continue;
      ctx.fillStyle = (Math.sin(a) > 0) ? style.colour : mix(style.colour, '#07060c', 0.35);
      ctx.fillRect(px, py, 1, 1);
    }
    /* A second, faster ring for Epic and above. Two rings travelling at
     * different speeds is the cheapest way to make an impact feel like it had
     * force behind it rather than a radius. */
    if (style.index >= 3) {
      const r2 = 1 + Math.min(1, t * 1.7) * (w / 2 - 2);
      ctx.globalAlpha = Math.max(0, (1 - Math.min(1, t * 1.7)) * 0.7);
      ctx.fillStyle = hot;
      for (let a = 0; a < Math.PI * 2; a += 0.16) {
        const px = Math.round(cx + Math.cos(a) * r2);
        const py = Math.round(cy + Math.sin(a) * r2 * 0.34);
        if (px < 0 || py < 0 || px >= w || py >= h) continue;
        ctx.fillRect(px, py, 1, 1);
      }
    }
    /* Dust. Deterministic columns, thrown outward and settling — they rise for
     * the first half of the beat and fall back for the second, which is what
     * dust does and what a particle that only rises does not. */
    const rand = rng(hash(`${style.key}:impact:${w}`) || 1);
    const motes = 4 + style.index;
    ctx.fillStyle = style.colour;
    for (let i = 0; i < motes; i++) {
      const dir = rand() < 0.5 ? -1 : 1;
      const speed = 0.5 + rand() * 0.8;
      const px = Math.round(cx + dir * speed * t * (w / 2));
      const lift = Math.sin(Math.min(1, t * 1.2) * Math.PI) * (h * 0.55);
      const py = Math.round(cy - lift);
      if (px < 0 || py < 0 || px >= w || py >= h) continue;
      ctx.globalAlpha = fade * 0.85;
      ctx.fillStyle = (i & 1) ? hot : style.colour;
      ctx.fillRect(px, py, 1, 1);
    }
    ctx.globalAlpha = 1;
    return canvas;
  });
}

export function drawLootImpact(ctx, rarity, cx, groundY, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 1));
  const img = lootImpact(rarity, opts);
  const out = scale > 1 ? scaleSprite(img, scale) : img;
  ctx.drawImage(out, Math.round(cx - out.width / 2), Math.round(groundY - out.height + 2 * scale));
  return out;
}

/* The pool the beam leaves on the floor. Stippled rather than solid so it sits
 * on the same grain as everything else, and it breathes on a four-frame cycle
 * one beat slower than the beam so the two do not lock into a throb. */
export function lootPool(rarity, opts = {}) {
  const style = rarityStyle(rarity);
  const w = Math.max(12, Math.round(opts.width || 30));
  const h = Math.max(5, Math.round(opts.height || 11));
  const f = ((opts.frame || 0) % POOL_FRAMES + POOL_FRAMES) % POOL_FRAMES;
  const key = `${style.key}:${w}:${h}:${f}`;
  return poolCache.get(key, () => {
    const { canvas, ctx } = makeCanvas(w, h);
    const cx = (w - 1) / 2, cy = (h - 1) / 2;
    const breathe = 0.9 + 0.1 * (f === 1 || f === 2 ? 1 : 0);
    const rx = (w / 2 - 1) * breathe, ry = (h / 2 - 1) * breathe;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const dx = (x - cx) / rx, dy = (y - cy) / ry;
        const d = dx * dx + dy * dy;
        if (d > 1) continue;
        /* Stipple on the checker, denser toward the middle. The gap is what
         * keeps it reading as light on a floor rather than as a painted disc. */
        if (((x + y + f) & 1) === 1 && d > 0.28) continue;
        ctx.globalAlpha = (1 - d) * 0.5;
        ctx.fillStyle = d < 0.22 ? mix(style.colour, '#ffffff', 0.5) : style.colour;
        ctx.fillRect(x, y, 1, 1);
      }
    }
    ctx.globalAlpha = 1;
    return canvas;
  });
}

export function drawLootPool(ctx, rarity, cx, groundY, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 1));
  const img = lootPool(rarity, opts);
  const out = scale > 1 ? scaleSprite(img, scale) : img;
  ctx.drawImage(out, Math.round(cx - out.width / 2), Math.round(groundY - out.height / 2));
  return out;
}

/* The whole reward moment in one call. `t` is 0..1 across the drop animation.
 *
 * Three beats, and they are deliberately unequal, because an evenly-paced
 * arrival has no accent in it:
 *
 *   0.00 - 0.30   FALL     the item comes down the beam, fast and accelerating,
 *                          with the pool already lit under where it will land
 *   0.30          LAND     the impact ring, the dust and the rarity burst all
 *                          fire on the same frame; the item squashes
 *   0.30 - 0.52   SETTLE   the squash springs out into a small overshoot and
 *                          damps, which is the beat that makes the object feel
 *                          like it has weight
 *   0.52 - 1.00   HOLD     the idle bob, the beam flowing, the aura running
 *
 * Reduced motion collapses all of it to the held frame. That is not a lesser
 * version of the same thing — it is the same picture without the arrival.
 */
const LAND_T = 0.30;
const SETTLE_T = 0.52;

export function drawLootDrop(ctx, item, cx, groundY, opts = {}) {
  const scale = Math.max(1, Math.round(opts.scale || 2));
  const rarity = normaliseRarity(item && item.rarity);
  const style = rarityStyle(rarity);
  const t = opts.t === undefined ? 1 : clamp(opts.t, 0, 1);
  const time = opts.time || 0;
  const reduced = isReduced(opts);
  const size = N * scale;
  const restY = groundY - 30 * scale;

  /* The pool goes down first, under everything, and grows into the landing so
   * the floor is already committed to the event before the object arrives. */
  /* Quantised to four steps rather than to t. The pool is a cached canvas and
   * a canvas keyed on a continuous value is a cache that never hits — the
   * steady-state allocation harness catches exactly this, and it is the one
   * mistake that turns a nice effect into a stutter on a slow machine. */
  const poolStep = reduced ? 3 : Math.min(3, Math.floor((t / LAND_T) * 4));
  const poolGrow = 0.55 + poolStep * 0.15;
  drawLootPool(ctx, rarity, cx, groundY, {
    width: Math.round(30 * poolGrow), height: Math.round(11 * poolGrow),
    scale, frame: reduced ? 0 : Math.floor(time / (FRAME_MS * 2)),
  });

  drawLootBeam(ctx, rarity, cx, groundY, {
    width: 24, height: 48, scale, time, reducedMotion: reduced,
  });

  /* Fall, land, settle, bob. The fall is quadratic so the item accelerates
   * into the floor instead of drifting onto it; the settle is a damped
   * overshoot rather than a linear return, because a linear return reads as a
   * lift rather than as a landing. */
  let dy = 0;
  if (!reduced) {
    if (t < LAND_T) {
      const k = 1 - (t / LAND_T);
      dy = -k * k * 34 * scale;
    } else if (t < SETTLE_T) {
      const k = (t - LAND_T) / (SETTLE_T - LAND_T);
      dy = Math.sin(k * Math.PI * 1.5) * (1 - k) * 3 * scale;
    } else {
      dy = Math.round(Math.sin(time / 380) * 1.5) * scale;
    }
  }
  const iy = restY + dy;

  drawItem(ctx, item, cx - size / 2, iy, { scale, time, reducedMotion: reduced });

  if (reduced) return;

  /* The landing beat. Ring and burst fire together and are gone inside a third
   * of a second — a reward flash that outstays that stops being a punctuation
   * mark and becomes a wait. */
  if (t >= LAND_T && t < LAND_T + 0.30) {
    const k = (t - LAND_T) / 0.30;
    drawLootImpact(ctx, rarity, cx, groundY, {
      width: 32 + style.index * 4, height: 16, scale,
      frame: Math.min(IMPACT_FRAMES - 1, Math.floor(k * IMPACT_FRAMES)),
    });
    drawRarityBurst(ctx, rarity, cx, iy + size / 2, {
      size: 48, scale, frame: Math.min(BURST_FRAMES - 1, Math.floor(k * BURST_FRAMES)),
    });
  }
}

/* ================================================================
 * EQUIPPED GEAR ON THE HERO
 * ================================================================
 * Loot the player cannot see on the character is loot the player stops caring
 * about, and the reward loop of this whole game is "solve a problem, look
 * different". So this section is not an accessory to the item icons; it is the
 * payoff, and everything above it exists to feed it.
 *
 * There are two ways gear reaches the hero, and both are used, because
 * sprites.js already parameterises half the character and re-drawing that half
 * as an overlay would be worse art at twice the cost:
 *
 *   TINT     heroFrame() takes cloak, tunic, boot, trim, metal and weapon.
 *            Chest, feet, hands and weapon choice go through those, which is
 *            why a new pair of boots changes a 4-pixel foot correctly instead
 *            of having a 4-pixel foot pasted over it one pixel off.
 *            -> heroEquipOpts()
 *
 *   OVERLAY  A helm, a cuirass with pauldrons, bracers, a shield and the held
 *            weapon are SHAPE, and shape cannot be tinted on. Those composite
 *            over the 16x24 frame at the anchors below.
 *            -> heroGearLayers() / equippedHeroFrame()
 *
 * The single call that does both is equippedHeroSprites(), which returns
 * exactly the structure sprites.heroSprites() returns and can be assigned
 * straight over it. See INTEGRATION at the bottom.
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
const HERO_HELM_ANCHOR = Object.freeze({ down: [3, 1], up: [3, 1], left: [2, 1], right: [4, 1] });
/* The torso runs y9..y17 and spans x2..x13 on every facing, so one anchor
 * serves all four and the cuirass never needs to be re-registered. */
const HERO_CLOAK_ANCHOR = Object.freeze({ down: [1, 9], up: [1, 9], left: [1, 9], right: [1, 9] });
const HERO_BRACER_ANCHOR = Object.freeze({ left: [0, 11], right: [11, 11] });

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

/* The held weapon gets its own growth table, because the 24x24 one would not
 * fit and because the hero's hand is where the player sees the weapon MOST —
 * a Legendary that is unmistakable in the inventory and identical to an iron
 * one in the field has put its effort in the wrong place. Six pixels of extra
 * guard at 16px is a lot of guard. */
const HERO_WEAPON_GROWTH = {
  sword:  { 2: [[7, 0, 'ogggo']], 3: [[6, 0, 'o'], [6, 4, 'o'], [10, 0, 'ogggo']],
            4: [[5, 0, 'o'], [5, 4, 'o'], [11, 1, 'ooo']], 5: [[4, 0, 'o'], [4, 4, 'o']] },
  sabers: { 2: [[6, 0, 'ogggo']], 3: [[5, 0, 'o'], [5, 4, 'o']],
            4: [[8, 0, 'ogggo'], [9, 1, 'ooo']], 5: [[4, 0, 'o'], [4, 4, 'o']] },
  dagger: { 2: [[6, 0, 'ogggo']], 3: [[5, 0, 'o'], [5, 4, 'o']],
            4: [[8, 0, 'ogggo'], [9, 1, 'ooo']], 5: [[4, 0, 'o'], [4, 4, 'o']] },
  axe:    { 2: [[0, 0, 'oooooo'], [1, 0, 'oBBgBo']], 3: [[4, 0, 'oo'], [4, 4, 'oo']],
            4: [[0, 5, 'o'], [3, 0, 'oBBBBo']], 5: [[2, 0, 'o'], [2, 5, 'o']] },
  hammer: { 2: [[0, 0, 'oooooo']], 3: [[1, 0, 'oBBBBo'], [4, 0, 'oo'], [4, 4, 'oo']],
            4: [[4, 0, 'oBBBBo']], 5: [[5, 0, 'o'], [5, 5, 'o']] },
  spear:  { 2: [[2, 0, 'oBBBo']], 3: [[3, 0, 'ogggo']], 4: [[1, 0, 'o'], [1, 4, 'o']],
            5: [[4, 0, 'o'], [4, 4, 'o']] },
  lance:  { 2: [[3, 0, 'oBBBo']], 3: [[4, 0, 'ogggo']], 4: [[5, 0, 'o'], [5, 4, 'o']],
            5: [[2, 0, 'o'], [2, 4, 'o']] },
  staff:  { 2: [[2, 0, 'ogmgo']], 3: [[1, 0, 'ogggo'], [3, 0, 'ogggo']],
            4: [[0, 1, 'ooo'], [4, 1, 'ooo']], 5: [[0, 0, 'o'], [0, 4, 'o']] },
  bow:    { 2: [[0, 0, 'ooo']], 3: [[10, 0, 'ooo']], 4: [[5, 4, 'w'], [6, 4, 'w']],
            5: [[4, 0, 'og'], [7, 0, 'og']] },
  relic:  { 2: [[2, 0, 'ogmmo'], [5, 0, 'ogmmo']], 3: [[1, 1, 'oooo']],
            4: [[0, 2, 'oo'], [6, 1, 'oooo']], 5: [[1, 0, 'o'], [1, 5, 'o']] },
};

/* Shields are held, so they turn with the body: face-on when the hero faces
 * the camera, edge-on from the side. Two silhouettes, not one rotated. */
const HERO_SHIELD_ART = {
  face: ['.oooo.', 'oBBBBo', 'oBmmBo', 'oBmmBo', 'oBBBBo', '.oBBo.', '..oo..', '......'],
  edge: ['..oo..', '.oBBo.', '.oBBo.', '.oBmo.', '.oBBo.', '.oBBo.', '..oo..', '......'],
};

/* Three head silhouettes, because a crown that covers the face is a helm and a
 * helm that shows the hair is a headband — and each of the three gets a back
 * and a side, because a visor slit drawn on the back of a head is the kind of
 * mistake that makes a whole character look wrong without the player being
 * able to say why. 10x9 at [3,1]; the head occupies y1..y8. */
const HERO_HEAD_ART = {
  helm: {
    down: ['..oooooo..', '.oBBBBBBo.', 'oBBBBBBBBo', 'oBeeeeeeBo',
           'oBBBBBBBBo', 'oBBBBBBBBo', '.oBBBBBBo.', '..oooooo..', '..........'],
    up:   ['..oooooo..', '.oBBBBBBo.', 'oBBBBBBBBo', 'oBBBBBBBBo',
           'oBBggggBBo', 'oBBBBBBBBo', '.oBBBBBBo.', '..oooooo..', '..........'],
    side: ['..oooooo..', '.oBBBBBBo.', 'oBBBBBBBBo', 'oBBBeeeBBo',
           'oBBBBBBBBo', 'oBBBBBBBBo', '.oBBBBBBo.', '..oooooo..', '..........'],
  },
  crown: {
    down: ['..o..o..o.', '.oggggggo.', '.ogmggmgo.', '.oyyyyyyo.',
           '..........', '..........', '..........', '..........', '..........'],
    up:   ['..o..o..o.', '.oggggggo.', '.oggggggo.', '.oyyyyyyo.',
           '..........', '..........', '..........', '..........', '..........'],
    side: ['..o..o....', '.oggggo...', '.ogmggo...', '.oyyyyo...',
           '..........', '..........', '..........', '..........', '..........'],
  },
  hood: {
    down: ['..oooooo..', '.occcccco.', 'occcccccco', 'occeeeecco',
           'occeeeecco', 'occcccccco', '.occcccco.', '..oooooo..', '..........'],
    up:   ['..oooooo..', '.occcccco.', 'occcccccco', 'occcccccco',
           'occcvvccco', 'occcccccco', '.occcccco.', '..oooooo..', '..........'],
    side: ['..oooooo..', '.occcccco.', 'occcccccco', 'occceeecco',
           'occcccccco', 'occcccccco', '.occcccco.', '..oooooo..', '..........'],
  },
};

/* Body armour. 14 wide at x1, so it reaches one pixel past the torso on each
 * side — which is exactly what a pauldron is. Four kinds, because a cuirass, a
 * gambeson, a robe and a cloak are four different silhouettes and picking the
 * wrong one is the difference between a knight and a wizard.
 */
const HERO_BODY_ART = {
  /* A cuirass: pauldrons across the shoulder line at y10-y11 where a real
   * pauldron sits, and a breastplate down the middle from y12 that stops
   * short of the arms so the walk cycle still reads. Armour that covers the
   * arms is armour that deletes the animation. */
  plate: {
    down: ['..oBBBBBBBBo..', 'oBBBBBBBBBBBBo', 'oBBBBBBBBBBBBo', '...oBBggBBo...',
           '...oBBggBBo...', '...oggggggo...', '...oBBBBBBo...', '...oBBBBBBo...',
           '....oooooo....'],
    up:   ['..oBBBBBBBBo..', 'oBBBBBBBBBBBBo', 'oBBBBBBBBBBBBo', '...oBBBBBBo...',
           '...oBggggBo...', '...oBggggBo...', '...oBBBBBBo...', '...oBBBBBBo...',
           '....oooooo....'],
    side: ['..oBBBBBBBBo..', '.oBBBBBBBBBBo.', '.oBBBBBBBBBBo.', '...oBggBBBo...',
           '...oBBBBBBo...', '...oggggggo...', '...oBBBBBBo...', '...oBBBBBBo...',
           '....oooooo....'],
  },
  /* A gambeson: no shoulder, just a padded jerkin. The difference from plate
   * has to be in the OUTLINE — same reason the item icons grow. */
  mail: {
    down: ['..............', '...occcccco...', '...occcccco...', '...occggcco...',
           '...occcccco...', '...occcccco...', '...occcccco...', '...oooooooo...',
           '..............'],
    up:   ['..............', '...occcccco...', '...occcccco...', '...occcccco...',
           '...occggcco...', '...occcccco...', '...occcccco...', '...oooooooo...',
           '..............'],
    side: ['..............', '...occcccco...', '...occcccco...', '...occggcco...',
           '...occcccco...', '...occcccco...', '...occcccco...', '...oooooooo...',
           '..............'],
  },
  /* A robe reaches the floor and hides the walk cycle. That is not a bug: a
   * robed caster gliding is the read we want, and it is the single clearest
   * signal the chest slot has changed at all. */
  robe: {
    down: ['..occcccccco..', '..occcccccco..', '..occcccccco..', '..occcggccco..',
           '..occcccccco..', '..occcccccco..', '..occcccccco..', '..occcccccco..',
           '..occcccccco..', '..occcccccco..', '.occcccccccco.', '.occcccccccco.',
           'occcccccccccco', 'ovvvvvvvvvvvvo', 'oooooooooooooo'],
    up:   ['..occcccccco..', '..occcccccco..', '..occcccccco..', '..occcccccco..',
           '..occcggccco..', '..occcccccco..', '..occcccccco..', '..occcccccco..',
           '..occcccccco..', '..occcccccco..', '.occcccccccco.', '.occcccccccco.',
           'occcccccccccco', 'ovvvvvvvvvvvvo', 'oooooooooooooo'],
    side: ['..occcccccco..', '..occcccccco..', '..occcccccco..', '..occggcccco..',
           '..occcccccco..', '..occcccccco..', '..occcccccco..', '..occcccccco..',
           '..occcccccco..', '..occcccccco..', '.occcccccccco.', '.occcccccccco.',
           'occcccccccccco', 'ovvvvvvvvvvvvo', 'oooooooooooooo'],
  },
  /* Facing away the cloak is the whole back; facing the camera it hangs behind
   * the body and only its collar and its two front edges are visible. */
  cloak: {
    down: ['ocCCCCCCCCCCco', 'occcccccccccco', 'oc..........co', 'oc..........co',
           'oc..........co', 'ov..........vo', 'ov..........vo', 'oo..........oo',
           '..............', '..............'],
    up:   ['ocCCCCCCCCCCco', 'occcccccccccco', 'occcccccccccco', 'occcccccccccco',
           'occcccccccccco', 'occcccccccccco', 'occcccccccccco', 'occcccccccccco',
           '.occcccccccco.', '.occcccccccco.', '.ovvvvvvvvvvo.', '..oooooooooo..',
           '..............'],
    side: ['ocCCCCCCCCCco.', 'occccccccccco.', 'occ.......cco.', 'occ.......cco.',
           'occ.......cco.', 'ovv.......vvo.', 'ovv.......vvo.', 'ooo.......ooo.',
           '..............', '..............'],
  },
};

/* Bracers. Authored per arm rather than as one strip, because the two arms
 * swing out of phase and a single strip would leave one cuff floating a pixel
 * off the wrist on half the walk cycle. */
const HERO_BRACER_ART = {
  plate: {
    left:  ['.oBBo', '.oBBo', '.oggo', '..oo.'],
    right: ['oBBo.', 'oBBo.', 'oggo.', '.oo..'],
  },
  cloth: {
    left:  ['.occo', '.occo', '.ovvo', '..oo.'],
    right: ['occo.', 'occo.', 'ovvo.', '.oo..'],
  },
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

/* Which body silhouette a chest item wears. Driven off the resolved shape, so
 * a robe from the catalogue and a robe invented tomorrow agree. */
function bodyArtFor(item) {
  const shape = resolveShape(item);
  if (shape === 'plate' || shape === 'greaves' || shape === 'gauntlets') return 'plate';
  if (shape === 'robe') return 'robe';
  if (shape === 'cloak') return 'cloak';
  return 'mail';
}

function bracerArtFor(item) {
  return resolveShape(item) === 'wraps' ? 'cloth' : 'plate';
}

/* Down and up are authored; left and right share one side drawing, because a
 * torso seen from either side is the same torso. */
function facingArt(table, facing) {
  if (!table) return null;
  if (facing === 'up') return table.up || table.down;
  if (facing === 'left' || facing === 'right') return table.side || table.down;
  return table.down;
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

/* The arms swing out of phase by a row: on frame 0 the right hand is dropped,
 * on frame 2 the left one is. HERO_ARMS in sprites.js says so, and a cuff that
 * ignores it floats. Idle and cast hold both arms level. */
function armOffsets(pose, frame) {
  if (pose !== 'walk') return { left: pose === 'idle' ? 1 : -2, right: pose === 'idle' ? 1 : -2 };
  const f = ((frame % 4) + 4) % 4;
  return { left: f === 2 ? 1 : 0, right: f === 0 ? 1 : 0 };
}

const overlayCache = cappedCache(512);

/* Overlays get the same rarity ladder as the inventory icon, minus the passes
 * that need room: a 6x12 box cannot hold voids and a fracture without
 * dissolving, and a weapon that dissolves at 16px reads as damage rather than
 * as Mythic. Growth, fittings, runes, gilding and the animated glint all
 * survive the small box and all of them are visible at 3x, which is the scale
 * the overworld actually draws at.
 */
function overlaySprite(art, item, w, h, frame, tag, growth) {
  const shapeKey = resolveShape(item);
  const shape = SHAPES[shapeKey] || SHAPES.relic;
  const rarity = normaliseRarity(item && item.rarity);
  const style = rarityStyle(rarity);
  const seed = itemSeed(item);
  const f = ((frame % style.frames) + style.frames) % style.frames;
  const key = `${tag}:${shapeKey}:${rarity}:${seed}:${f}`;
  return overlayCache.get(key, () => {
    let g = art;
    if (style.grow > 0 && growth) {
      const cells = toCells(g);
      for (let lv = 2; lv <= style.grow; lv++) stamp(cells, growth[lv]);
      g = toRows(cells);
    }
    g = ornament(g, { gem: null, gem2: null }, compactStyle(style), seed, f);
    g = applyRim(g);
    g = animate(g, style, f, seed);
    return gridSprite(g, rarityPalette(shape.mat, rarity), w, h);
  });
}

/* The ornament level a small box can carry. Bands, a stone and runes read at
 * 6x12; a faceted crystal, a pennant and a scar do not — they turn into three
 * loose pixels. Clamping here rather than at the call site keeps the rule in
 * one place. */
const compactCache = new Map();
function compactStyle(style) {
  if (compactCache.has(style.key)) return compactCache.get(style.key);
  const out = Object.freeze({
    ...style,
    ornament: Math.min(3, style.ornament),
    crystal: false, pennant: false, engrave: false, history: false,
  });
  compactCache.set(style.key, out);
  return out;
}

/* Each of these returns { canvas, ox, oy } in hero-sprite coordinates, so the
 * caller can either composite with sprites.composeSprite or drawImage at
 * (heroX + ox * scale, heroY + oy * scale). */
export function heroWeaponOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_WEAPON_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const key = heroWeaponKeyFor(item);
  const art = HERO_WEAPON_ART[key] || HERO_WEAPON_ART.sword;
  const [ax, ay] = HERO_WEAPON_ANCHOR[facing];
  const { weaponDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  return {
    canvas: overlaySprite(art, item, 6, 12, frame, 'wpn', HERO_WEAPON_GROWTH[key]),
    ox: ax, oy: ay + weaponDY,
  };
}

export function heroShieldOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_SHIELD_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const [ax, ay] = HERO_SHIELD_ANCHOR[facing];
  const { bodyDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  const edge = facing === 'left' || facing === 'right';
  const art = edge ? HERO_SHIELD_ART.edge : HERO_SHIELD_ART.face;
  return {
    canvas: overlaySprite(art, item, 6, 8, frame, edge ? 'shdE' : 'shdF'),
    ox: ax, oy: ay + bodyDY,
  };
}

export function heroHelmOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_HELM_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frame = frameFor(item, opts);
  const kind = headArtFor(item);
  const art = facingArt(HERO_HEAD_ART[kind], facing);
  const [ax, ay] = HERO_HELM_ANCHOR[facing];
  const { bodyDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  return {
    canvas: overlaySprite(art, item, 10, 9, frame, `hlm${kind}${facing === 'up' ? 'U' : facing === 'down' ? 'D' : 'S'}`),
    ox: ax, oy: ay + bodyDY,
  };
}

/* The chest slot, and the one the audit was really about: a cuirass with
 * pauldrons, a gambeson, a robe to the floor or a cloak, chosen by shape and
 * sized to the torso rather than pasted near it. */
export function heroChestOverlay(item, opts = {}) {
  if (!item) return null;
  const facing = HERO_CLOAK_ANCHOR[opts.facing] ? opts.facing : 'down';
  const kind = bodyArtFor(item);
  const art = facingArt(HERO_BODY_ART[kind], facing);
  if (!art) return null;
  const frame = frameFor(item, opts);
  const [ax, ay] = HERO_CLOAK_ANCHOR[facing];
  const { bodyDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  const tag = `bdy${kind}${facing === 'up' ? 'U' : facing === 'down' ? 'D' : 'S'}`;
  return {
    canvas: overlaySprite(art, item, 14, art.length, frame, tag),
    ox: ax, oy: ay + bodyDY,
  };
}

/* Kept because it is exported and other code may hold a reference. A cloak is
 * one of the four body silhouettes now, so this is the chest overlay with the
 * kind forced. */
export function heroCloakOverlay(item, opts = {}) {
  return heroChestOverlay(item, opts);
}

/* Bracers, as two layers. See armOffsets(): the arms swing a row out of phase
 * and one strip cannot follow both. */
export function heroHandsOverlays(item, opts = {}) {
  if (!item) return [];
  const facing = ['down', 'up', 'left', 'right'].includes(opts.facing) ? opts.facing : 'down';
  const kind = bracerArtFor(item);
  const frame = frameFor(item, opts);
  const pose = opts.pose || 'walk';
  const { bodyDY } = poseOffsets(facing, pose, opts.frameIndex || 0);
  const swing = armOffsets(pose, opts.frameIndex || 0);
  const out = [];
  for (const side of ['left', 'right']) {
    /* Facing sideways only the near arm is drawn by sprites.js, so only the
     * near bracer is drawn here. A cuff hanging in space behind the shoulder
     * is the exact artefact this whole file is trying to avoid. */
    if (facing === 'left' && side === 'right') continue;
    if (facing === 'right' && side === 'left') continue;
    const [ax, ay] = HERO_BRACER_ANCHOR[side];
    out.push({
      canvas: overlaySprite(HERO_BRACER_ART[kind][side], item, 5, 4, frame, `brc${kind}${side}`),
      ox: ax, oy: ay + bodyDY + swing[side],
    });
  }
  return out;
}

export function heroHandsOverlay(item, opts = {}) {
  return heroHandsOverlays(item, opts)[0] || null;
}

export function gearOverlay(kind, item, opts = {}) {
  if (kind === 'weapon') return heroWeaponOverlay(item, opts);
  if (kind === 'offhand' || kind === 'shield') return heroShieldOverlay(item, opts);
  if (kind === 'head' || kind === 'helm') return heroHelmOverlay(item, opts);
  if (kind === 'chest' || kind === 'cloak' || kind === 'back') return heroChestOverlay(item, opts);
  if (kind === 'hands') return heroHandsOverlay(item, opts);
  return null;
}

/* Sorted into the two passes the hero needs. Facing away, the weapon is behind
 * the body and the cloak is the whole back; facing the camera it is the other
 * way round. Same rule sprites.js applies to its own weapon layer.
 */
export function heroGearLayers(gear, opts = {}) {
  const g = gear || {};
  const facing = ['down', 'up', 'left', 'right'].includes(opts.facing) ? opts.facing : 'down';
  const o = { ...opts, facing };
  const behind = [], front = [];
  /* A cloak is worn BEHIND the body when the hero faces the camera and IS the
   * body when they face away; a cuirass, a jerkin and a robe are worn OVER the
   * body from every angle. Getting that backwards is why the audit found the
   * payoff dead: the armour was being drawn and then painted over by the hero
   * it was supposed to be on. */
  const back = g.back || g.cloak;
  if (back && back !== g.chest) {
    const layer = heroChestOverlay(back, o);
    if (layer) (facing === 'up' ? front : behind).push(layer);
  }
  const chest = heroChestOverlay(g.chest, o);
  if (chest) {
    const isCloak = bodyArtFor(g.chest) === 'cloak';
    (isCloak && facing !== 'up' ? behind : front).push(chest);
  }
  const weapon = heroWeaponOverlay(g.weapon, o);
  if (weapon) (facing === 'up' ? behind : front).push(weapon);
  const shield = heroShieldOverlay(g.offhand, o);
  if (shield) (facing === 'up' ? behind : front).push(shield);
  for (const b of heroHandsOverlays(g.hands, o)) front.push(b);
  const helm = heroHelmOverlay(g.head, o);
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

/* ---------------- the tint half ----------------
 * The half of the character sprites.js already parameterises. Everything here
 * returns an opts object for heroFrame()/heroSprites(); nothing here draws.
 */

/* The best thing the player is wearing. Used for the trim, which is the one
 * accent colour that runs across the whole character — so the hero picks up
 * the colour of their proudest piece rather than of whatever the chest slot
 * happens to hold. */
export function gearRarity(gear) {
  const g = gear || {};
  let best = 'COMMON';
  for (const k of ['weapon', 'offhand', 'head', 'chest', 'hands', 'feet', 'back', 'cloak']) {
    const it = g[k];
    if (!it) continue;
    const r = normaliseRarity(it.rarity);
    if (rarityStyle(r).index > rarityStyle(best).index) best = r;
  }
  return best;
}

function materialFor(item, fallback) {
  const st = rarityStyle(item && item.rarity);
  const mat = MATERIAL[shapeMaterial(resolveShape(item))] || MATERIAL[fallback];
  return st.material(mat);
}

/* Equipment as heroFrame() options. This is the cheap half of the payoff and
 * the half that needs no second draw pass: boots recolour the boot, a chest
 * recolours the tunic and cloak, gauntlets recolour the metal, and the trim
 * takes the colour of the best piece worn. Pass `base` to keep a region or
 * NPC palette underneath.
 */
export function heroEquipOpts(gear, base) {
  const g = gear || {};
  /* heroOpts() in sprites.js treats an object carrying `sky` and `ground` as a
   * REGION PALETTE and throws the rest of it away, keeping only `accent` as
   * the trim. Spreading a region palette in here and then writing cloak and
   * boot onto it would therefore silently lose every one of them — the gear
   * would be equipped and invisible, which is the exact bug this whole section
   * exists to fix. Translate it instead. */
  const isPalette = base && base.sky && base.ground;
  const out = isPalette ? (base.accent ? { trim: base.accent } : {}) : { ...(base || {}) };
  const chest = g.chest || g.back || g.cloak;
  if (chest) {
    out.cloak = materialFor(chest, 'cloth');
    out.tunic = materialFor(chest, 'cloth');
  }
  if (g.feet) out.boot = materialFor(g.feet, 'leather');
  if (g.hands) out.metal = materialFor(g.hands, 'steel');
  if (g.weapon) out.weapon = heroWeaponKeyFor(g.weapon);
  const best = gearRarity(g);
  if (best !== 'COMMON') out.trim = rarityStyle(best).colour;
  return out;
}

/* ---------------- the whole character, in one call ----------------
 * A drop-in for sprites.heroFrame() and sprites.heroSprites(). Same arguments,
 * same return shapes, gear composited in. This is deliberately a superset
 * rather than a new API: the wiring in main.js and overworld.js is then one
 * assignment rather than a restructuring of every draw site, and the fewer
 * lines a payoff needs the more likely it is to actually get wired up.
 */
const equippedCache = cappedCache(256);

function equipKey(gear, opts, facing, frame, pose) {
  const g = gear || {};
  let k = `${facing}:${frame}:${pose}`;
  for (const slot of ['weapon', 'offhand', 'head', 'chest', 'hands', 'feet', 'back', 'cloak']) {
    const it = g[slot];
    k += `|${it ? `${it.id || it.name || '?'}:${normaliseRarity(it.rarity)}` : ''}`;
  }
  const o = opts || {};
  k += `|${o.cloak || ''}${o.tunic || ''}${o.skin || ''}${o.hair || ''}${o.boot || ''}${o.trim || ''}${o.metal || ''}`;
  return k;
}

export function equippedHeroFrame(facing = 'down', frame = 0, gear = null, opts = null, pose = 'walk') {
  const dir = ['down', 'up', 'left', 'right'].includes(facing) ? facing : 'down';
  const f = ((frame % 4) + 4) % 4;
  const tint = heroEquipOpts(gear, opts);
  const key = equipKey(gear, tint, dir, f, pose);
  return equippedCache.get(key, () => heroWithGear(
    heroFrame(dir, f, tint, pose), gear,
    /* Frame 0 of the item animation: an overworld hero at 3x is not the place
     * for a drifting specular, and pinning it keeps the cache key finite. */
    { facing: dir, pose, frameIndex: f, frame: 0 }));
}

/* Identical in shape to sprites.heroSprites(), so it can be assigned straight
 * over it:  this.hero = lootart.equippedHeroSprites(G.equipped, palette); */
export function equippedHeroSprites(gear, opts) {
  const out = {};
  for (const facing of ['down', 'up', 'left', 'right']) {
    out[facing] = [0, 1, 2, 3].map(f => equippedHeroFrame(facing, f, gear, opts, 'walk'));
  }
  out.side = out.right;
  out.idle = {};
  out.cast = {};
  for (const facing of ['down', 'up', 'left', 'right']) {
    out.idle[facing] = [equippedHeroFrame(facing, 1, gear, opts, 'idle'),
                        equippedHeroFrame(facing, 3, gear, opts, 'walk')];
    out.cast[facing] = equippedHeroFrame(facing, 0, gear, opts, 'cast');
  }
  out.idle.side = out.idle.right;
  out.cast.side = out.cast.right;
  return out;
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
  return gridCache.get(key, () => applyRarity(shape.grid, style.key, { shape, shapeKey, seed, frame: f }));
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
  impactCache.clear(); poolCache.clear(); equippedCache.clear();
  paletteCache.clear();
}

export function lootArtStats() {
  return {
    shapes: SHAPE_KEYS.length,
    rarities: RARITY_KEYS.length,
    grids: gridCache.size,
    sprites: spriteCache.size,
    overlays: overlayCache.size,
    heroes: equippedCache.size,
    drop: beamCache.size + burstCache.size + impactCache.size + poolCache.size,
  };
}

/* ================================================================
 * INTEGRATION
 * ================================================================
 * This module writes nothing and owns no canvas. Wiring is four edits, and the
 * third one is the one that matters.
 *
 * 1) web/js/main.js — itemIcon(). Already wired. For Epic and above the icon is
 *    animated: either pass `time` from an existing rAF tick and redraw, or
 *    leave it static in list views and animate only the detail panel. Both are
 *    correct; a list of forty animated icons is not.
 *
 *      lootart.drawItem(ctx, item, 0, 0, { scale, time: performance.now() });
 *
 * 2) The drop moment. Already wired through drawLootDrop(). `t` is 0..1 across
 *    the arrival and the three beats now land at fixed times — fall to 0.30,
 *    impact at 0.30, settle to 0.52, hold after. Drive it from a real clock:
 *
 *      lootart.drawLootDrop(ctx, item, cx, groundY,
 *        { scale: 2, t: dropProgress, time, reducedMotion: this.reducedMotion });
 *
 *    For a modal instead of an in-scene drop, the framed card is unchanged:
 *
 *      lootart.drawLootCard(ctx, item, 0, 0, { scale: 4, time });
 *
 *    Put the item name and effect_text in DOM over CARD_TEXT_RECT scaled to
 *    match. The card renders no text on purpose: pixel type at this size is
 *    either unreadable or a second font engine, and DOM text stays selectable
 *    and readable by a screen reader.
 *
 * 3) GEAR ON THE HERO — the payoff, and currently the only part not wired.
 *    Everything above it exists to feed this, and it is ONE assignment:
 *
 *      // web/js/main.js, wherever equipment changes:
 *      G.overworld.hero = lootart.equippedHeroSprites(G.equipped);
 *
 *    equippedHeroSprites() returns exactly what sprites.heroSprites() returns —
 *    { down, up, left, right, side, idle, cast } — with the helm, cuirass,
 *    bracers, shield and weapon composited in and the boot, tunic, cloak, metal
 *    and trim colours taken from what is worn. Nothing downstream changes.
 *
 *    Overworld already has the seam for it; it currently calls heroSprites()
 *    directly and nobody calls it:
 *
 *      // web/js/overworld.js — setEquipment(), one line:
 *      setEquipment(gear) { this.hero = lootart.equippedHeroSprites(gear); }
 *      // web/js/main.js — after equip/unequip and after loading a save:
 *      G.overworld.setEquipment(G.equipped);
 *
 *    In the battle scene, fx.js builds its hero the same way at line ~430:
 *
 *      this.hero = lootart.equippedHeroSprites(gear, pixel.PALETTES[heroPalette]);
 *
 *    `G.equipped` is read for weapon, offhand, head, chest, hands, feet and
 *    back only; anything else on the object is ignored, and a missing slot is
 *    simply not drawn.
 *
 *    Two cheaper options exist and both are strictly worse, but both are one
 *    line and neither needs a second draw pass, so they are listed:
 *      - tint only:    sprites.heroSprites(lootart.heroEquipOpts(G.equipped))
 *      - weapon only:  opts.weapon = lootart.heroWeaponKeyFor(G.equipped.weapon)
 *
 *    For a paperdoll in the GEAR panel, heroWithGear() composites onto a hero
 *    canvas you already have, and equippedHeroFrame() builds the whole thing:
 *
 *      const img = lootart.equippedHeroFrame('down', 1, G.equipped, null, 'idle');
 *      ctx.drawImage(sprites.scaleSprite(img, 4), x, y);
 *
 * 4) Reduced motion. Call `lootart.setReducedMotion(v)` from the same place
 *    that calls `BattleFX.setReducedMotion(v)`. Every animated path here also
 *    takes a per-call `reducedMotion` override, so fx.js can pass its own flag
 *    without the module-level default being set at all.
 *
 * Caches: everything is keyed and capped. equippedHeroSprites() builds 20
 * canvases per distinct loadout and caches them, so calling it on every equip
 * is free after the first; calling it every frame is not, and there is no
 * reason to.
 *
 * Nothing in this module reads game state, calls the API, or knows what a
 * problem is. It takes the item dict the backend already sends and draws it.
 */
