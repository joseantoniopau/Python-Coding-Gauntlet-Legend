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
/* The forge section below builds its metals out of the shared five-step ramps
 * rather than out of loose hex, which is the only way a Quarterturn Bronze
 * blade and a bronze pauldron end up the same bronze. palette.js is a leaf
 * module — it imports nothing — so this costs no cycle. */
import { RAMPS, SHADE, OUTLINE, rampFrom as deriveRamp, rimFor } from './palette.js';

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

function fitPalette(pal, budget = BUDGET) {
  const glyphs = Object.keys(pal);
  const uniq = [];
  for (const g of glyphs) if (pal[g] && !uniq.includes(pal[g])) uniq.push(pal[g]);
  if (uniq.length <= budget) return pal;
  const pinnedHex = new Set(PINNED.map(g => pal[g]).filter(Boolean));
  /* How many glyphs point at each colour, so a merge keeps the colour that is
   * carrying more of the sprite and retires the one that is carrying less. */
  const weight = new Map();
  for (const g of glyphs) if (pal[g]) weight.set(pal[g], (weight.get(pal[g]) || 0) + 1);
  const live = uniq.slice();
  const remap = new Map();
  while (live.length > budget) {
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
    i: '#8fd07a',
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
  /* The motif and aura passes gauntlet/legendaries.py asked for, in the two
   * places its brief specifies: the mark is cut in before the rim lights it,
   * the aura is drawn outside the silhouette after the light has moved. Both
   * are opt-in and default off, so every existing item renders byte-identically
   * to how it did before they existed. */
  if (opts.motif) g = applyMotif(g, opts.motif, { tier: opts.tier || style.index + 1, seed, frame });
  g = applyRim(g);
  g = corrupt(g, style, seed);
  g = animate(g, style, frame, seed);
  if (opts.aura) g = applyAura(g, opts.aura, { tier: opts.tier || style.index + 1, seed, frame });
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
  /* A forged weapon is a different object drawn from a different table, and
   * every call site in the game already goes through here. Routing it at the
   * top means the smith's work shows up in the inventory, the loot card and
   * the battle scene without any of them learning a second call. Detection is
   * strict — see forgeOf() — so nothing in the existing catalogue is caught. */
  const forged = forgeOf(item);
  if (forged) return drawForgeWeapon(ctx, forged, x, y, opts);
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
  const forged = forgeOf(item);
  if (forged) return forgeWeaponOverlay(forged, opts);
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
    if (!it) { k += '|'; continue; }
    /* The forge state has to be in the key. It was not, and the result was the
     * worst kind of bug this module can have: the smith took the metal, the
     * rung went up, the inventory icon changed — and the blade in the player's
     * hand was served from cache and never moved. */
    const f = forgeOf(it);
    k += `|${it.id || it.name || '?'}:${normaliseRarity(it.rarity)}${f ? `:${f.key}` : ''}`;
  }
  const o = opts || {};
  k += `|${o.cloak || ''}${o.tunic || ''}${o.skin || ''}${o.hair || ''}${o.boot || ''}${o.trim || ''}${o.metal || ''}`;
  return k;
}

export function equippedHeroFrame(facing = 'down', frame = 0, gear = null, opts = null, pose = 'walk') {
  const dir = ['down', 'up', 'left', 'right'].includes(facing) ? facing : 'down';
  const f = ((frame % 4) + 4) % 4;
  const tint = heroEquipOpts(gear, opts);
  /* Two weapons at one anchor is one weapon too many. heroEquipOpts() sets
   * `weapon` because the cheap tint-only path needs it — that caller composites
   * nothing and would otherwise get an unarmed hero — but THIS path draws the
   * real overlay on top, and leaving sprites.js's own blade underneath it means
   * the silhouette the player sees is whichever of the two is bigger.
   *
   * That was not a cosmetic problem. It was hiding the ladder: a forged rung
   * that grew two pixels of guard grew them inside an outline the underlying
   * weapon was already filling, so the upgrade measured as a change to the
   * overlay and as nothing at all on the hero. */
  /* Deleting the key is not disarming. heroOpts() merges DEFAULT_HERO over
   * anything it is handed, and DEFAULT_HERO.weapon is 'sword' — so a deleted
   * `weapon` came back as a sword under the overlay, which is the exact double
   * blade the paragraph above says it is removing. `null` is the value
   * sprites.js documents as unarmed and the only one it honours. */
  if (gear && gear.weapon) tint.weapon = null;
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
 * THE FORGE
 * ================================================================
 * A class weapon is not loot. Loot is rolled, shown once and replaced; a forged
 * weapon is the same object for fifty hours, carried into every fight, and the
 * player watches it change. That is a different art problem and it gets a
 * different pipeline rather than a seventh rarity tier.
 *
 * gauntlet/forge.py owns the fifty-four objects — six lines, nine rungs each —
 * and its art brief states the problem this section was written to fix in
 * numbers rather than as an aspiration: across the hero rungs the old weapon
 * ladder produced six distinct frames and ZERO changes to the alpha mask.
 * "A rung-nine weapon that is a rung-one weapon in a different grey is the
 * single biggest gap between this feature and the word the player used, which
 * was epic."
 *
 * Four rules, and they are the whole section:
 *
 *   1. NINE RUNGS MEANS NINE OBJECTS. Not one object under nine filters. Every
 *      rung moves the OUTLINE — a longer fuller is the one interior detail
 *      allowed to be interior, and it is paid for by a crossguard that grows
 *      teeth, a pommel that grows a stone, wings, horns, and at the top a
 *      blade that stops being straight. forgeSpread() measures it and
 *      scripts/verify/forge.mjs fails the build on a rung that does not move.
 *   2. SIX LINES MEANS SIX SILHOUETTES. forge.py ships the six blades as four
 *      shapes — the Calipers and the Chain are both `relic`, the Maul and the
 *      Spanner are both `hammer` — and its brief calls fixing that "the
 *      cheapest legibility win available here". FORGE_BLADES fixes it: each
 *      line gets its own grid in the icon and its own pose in the hand.
 *   3. THE MATERIAL CHOOSES THE RAMP. Not a tint over one grey ladder — the
 *      actual five-step materials out of palette.js, so a Quarterturn Bronze
 *      blade is made of the same bronze as a bronze pauldron and belongs in
 *      the same frame. Material and metal are separate inputs, because they
 *      are separate facts: "steel" is how finished the object is, and
 *      "marshsilver" is what the player carried out of the marsh.
 *   4. TIME IS A RUNG. Rungs 1-4 do not move at all, which is what makes rung
 *      5 landing feel like something happened. Above that the light drifts
 *      along the edge, motes lift off the metal, the inlay pulses and the
 *      stone lights from inside — all of it precomputed into cached frames,
 *      none of it recomputed per frame, no Math.random anywhere in the path.
 *
 * This section owns no game rules. It does not know what a metal costs, what a
 * technique does, or whether you may upgrade. It takes forge.art_at()'s dict
 * and draws it, and an input it has never heard of falls back rather than
 * throwing — see forgeWeaponKey() and forgeMetalKey(). That contract is
 * deliberate: art that throws on an unknown key takes the screen with it.
 */

/* Bigger than ITEM_SIZE on purpose. 24 is the right box for an inventory icon
 * and it is the wrong box for the object this ladder has to escalate inside:
 * by rung 6 a sword has wings, and wings in a 24 box means clipping the wings
 * or never growing them. 32 leaves the top rungs somewhere to go and is still
 * a power of two, so an integer scale lands on pixel boundaries at every size
 * the game draws at. */
/* Bigger than ITEM_SIZE on purpose. 24 is the right box for an inventory icon
 * and it is the wrong box for the object this ladder has to escalate inside:
 * by rung 6 a blade has wings, and wings in a 24 box means clipping the wings
 * or never growing them. 32 leaves the top rungs somewhere to go and is still
 * a power of two, so an integer scale lands on pixel boundaries at every size
 * the game draws at. */
export const FORGE_SIZE = 32;
const FN = FORGE_SIZE;

/* Nine rungs, which is gauntlet/forge.py's number — MAX_TIER — not a number
 * chosen here. Six blades times nine rungs is the fifty-four objects that file
 * says exist, and if it ever moves this constant is the only place art has to
 * follow it. */
export const FORGE_TIER_COUNT = 9;

/* One frame count for every animated rung, and twelve rather than eight for a
 * specific reason: the auras below run at their own periods — the ember fall
 * is a four, the quench plume is a six, the glint is the full cycle — and a
 * cached frame table can only hold periods that divide it. Twelve holds four
 * and six; eight holds neither. At FRAME_MS that is 1.3s for a highlight to
 * travel a blade, which is slow enough to read as light moving rather than as
 * a flicker. */
export const FORGE_FRAMES = 12;

/* Grid helpers at forge width. Deliberately a second pair rather than a
 * widening of row()/mid(): those two are called by every shape above and by
 * the gear overlays, and changing a signature used in forty places to save ten
 * lines here is how a file this size acquires a bug nobody can find. */
function frow(...runs) {
  const out = new Array(FN).fill('.');
  for (let i = 0; i < runs.length; i += 2) {
    const x = runs[i] | 0, s = String(runs[i + 1]);
    for (let k = 0; k < s.length; k++) {
      const ch = s[k], px = x + k;
      if (ch === '.' || px < 0 || px >= FN) continue;
      out[px] = ch;
    }
  }
  return out.join('');
}
function fmid(s) { return frow(Math.floor((FN - s.length) / 2), s); }
function fblank() { return '.'.repeat(FN); }
function frepeat(rowStr, n) { return new Array(n).fill(rowStr); }

/* ---------------- metals ----------------
 * These are gauntlet/forge.py's METALS, by id, with the region each one drops
 * in. Nothing here invents a metal: the ids, the rungs and the regions are
 * that file's, and forgeVocabulary() exists so a test over there can prove the
 * two lists have not drifted.
 *
 * What IS decided here is the only thing art gets to decide — which of the
 * shared five-step materials in palette.js each metal is made of. That is the
 * whole of rule B: Quarterturn Bronze is made of the same bronze as a bronze
 * pauldron, so the two belong in one frame, and a blade carried out of the
 * Matrix Citadel looks like the place it came from rather than like a hue.
 *
 * `colour` is the metal's own hex as forge.py ships it, kept for captions and
 * as the derivation source if this table ever falls behind that one.
 */
const FORGE_METALS = {
  fieldiron: {
    rung: 1, label: 'Fieldiron', region: 'fields_of_syntax', colour: '#8a7f6a',
    ramp: 'iron', trim: 'rust', grip: 'leather', energy: null,
  },
  keybrass: {
    rung: 2, label: 'Keybrass', region: 'hashmap_highlands', colour: '#c9a05a',
    ramp: 'gold', trim: 'bronze', grip: 'leather', energy: null,
  },
  loomsteel: {
    rung: 2, label: 'Loomsteel', region: 'stringwood_labyrinth', colour: '#9aa4b8',
    ramp: 'steel', trim: 'bronze', grip: 'leather', energy: null,
  },
  marshsilver: {
    rung: 3, label: 'Marshsilver', region: 'sliding_window_marsh', colour: '#b9c8c0',
    ramp: 'silver', trim: 'frost', grip: 'leather', energy: '#b7d4f8',
  },
  faultsteel: {
    rung: 3, label: 'Faultsteel', region: 'stack_queue_mines', colour: '#7e6f66',
    ramp: 'gunmetal', trim: 'rust', grip: 'hide', energy: null,
  },
  quarterturn: {
    rung: 4, label: 'Quarterturn Bronze', region: 'matrix_citadel', colour: '#b07a45',
    ramp: 'bronze', trim: 'goldleaf', grip: 'hide', energy: null,
  },
  heartwood_iron: {
    rung: 4, label: 'Heartwood Iron', region: 'recursive_forest', colour: '#6f7a55',
    ramp: 'iron', trim: 'venom', grip: 'wood', energy: '#85d07c',
  },
  wastes_iron: {
    rung: 4, label: 'Wastes-iron', region: 'graph_wastes', colour: '#6a6470',
    ramp: 'stone', trim: 'void', grip: 'hide', energy: '#755f8c',
  },
  tilegold: {
    rung: 5, label: 'Tilegold', region: 'dp_ruins', colour: '#e0b44a',
    ramp: 'goldleaf', trim: 'ember', grip: 'leather', energy: '#ffc26a',
  },
  doubling_steel: {
    rung: 5, label: 'Doubling Steel', region: 'complexity_tower', colour: '#8fa8c8',
    ramp: 'chrome', trim: 'frost', grip: 'velvet', energy: '#b7d4f8',
  },
  nullsteel: {
    rung: 6, label: 'Nullsteel', region: 'null_kings_castle', colour: '#4a4458',
    ramp: 'void', trim: 'arcane', grip: 'velvet', energy: '#bd91f9',
  },
};

export const FORGE_METAL_KEYS = Object.keys(FORGE_METALS);

/* The metal a rung is mostly made of, read off the `cost` tables in
 * gauntlet/forge.py rather than interpolated. It is what a caller gets when it
 * asks for a rung and does not say what it was forged with, and it is what an
 * unrecognised metal name falls back to — so an unknown metal at rung 7 comes
 * back as doubling steel rather than as field iron. */
const TIER_METAL = [
  'fieldiron', 'fieldiron', 'fieldiron', 'keybrass', 'marshsilver',
  'quarterturn', 'wastes_iron', 'doubling_steel', 'tilegold', 'nullsteel',
];

/* Every spelling the rest of the world might send, including the bare material
 * nouns, because a blade that renders as the wrong metal because two files
 * disagreed about a noun is a bug the player sees and we would not. */
const METAL_ALIAS = {
  iron: 'fieldiron', field_iron: 'fieldiron', slag: 'fieldiron', scrap: 'fieldiron',
  brass: 'keybrass', key_brass: 'keybrass',
  steel: 'loomsteel', loom: 'loomsteel', truesteel: 'loomsteel',
  silver: 'marshsilver', marsh: 'marshsilver', marsh_silver: 'marshsilver',
  fault: 'faultsteel', gunmetal: 'faultsteel', fault_steel: 'faultsteel',
  bronze: 'quarterturn', quarter: 'quarterturn', quarterturn_bronze: 'quarterturn',
  heartwood: 'heartwood_iron', heart: 'heartwood_iron',
  wastes: 'wastes_iron', waste: 'wastes_iron', wasteiron: 'wastes_iron',
  gold: 'tilegold', tile: 'tilegold', goldleaf: 'tilegold',
  doubling: 'doubling_steel', chrome: 'doubling_steel', adamant: 'doubling_steel',
  null: 'nullsteel', null_steel: 'nullsteel', void: 'nullsteel',
  source: 'nullsteel', sourceforged: 'nullsteel',
};

/* Lowercase, strip everything that is not a letter or a digit. "Wastes-iron",
 * "wastes_iron" and "Wastes Iron" are one metal; pretending otherwise is how a
 * lookup table acquires six rows that mean the same thing. */
function slug(v) { return String(v == null ? '' : v).toLowerCase().replace(/[^a-z0-9]+/g, ''); }

const metalKeyCache = new Map();

/* Resolve anything to a metal. Exact key, then alias, then a containment scan
 * over the keys, labels and ramp names, then the rung's own metal. It cannot
 * fail and it never throws — which is the entire point of rule D. */
export function forgeMetalKey(metal, tier = 1) {
  const t = clampTier(tier);
  if (metal && FORGE_METALS[metal]) return metal;
  const s = slug(metal);
  if (!s) return TIER_METAL[t];
  const cacheKey = `${s}:${t}`;
  const hit = metalKeyCache.get(cacheKey);
  if (hit) return hit;
  let found = '';
  if (METAL_ALIAS[s]) found = METAL_ALIAS[s];
  if (!found) {
    for (const k of FORGE_METAL_KEYS) {
      const ks = slug(k), ls = slug(FORGE_METALS[k].label);
      if (s === ks || s === ls || s.includes(ks) || ks.includes(s) || s.includes(ls)) { found = k; break; }
    }
  }
  if (!found) found = TIER_METAL[t];
  if (metalKeyCache.size >= 256) metalKeyCache.delete(metalKeyCache.keys().next().value);
  metalKeyCache.set(cacheKey, found);
  return found;
}

export function forgeMetal(metal, tier = 1) {
  return FORGE_METALS[forgeMetalKey(metal, tier)];
}

/* ---------------- the rungs ----------------
 * Read this table as a smith's worklist rather than as a stat block. Each row
 * says what she did to the weapon this time, and every row does something the
 * SILHOUETTE can carry — which is the whole reason this section exists. The
 * art brief in gauntlet/forge.py states the problem it was written to fix in
 * numbers: across the six hero rungs the old ladder produced six distinct
 * frames and ZERO changes to the alpha mask. Six greys is not nine objects.
 *
 *   1 Unworked    stock. A bar with an edge on it and nothing else.
 *   2 Trued       squared up: the guard gains a fitting at each end and the
 *                 counterweight gets a proper cap.
 *   3 Fullered    the body is broadened and a groove cut down it.
 *   4 Quenched    the guard widens again and drops lugs; a stone is set.
 *   5 Inlaid      the quillons turn up, trim runs the length of the body, and
 *                 the pommel swells into the grip.
 *   6 Runed       broader again, a rune cut into the groove, a faceted stone.
 *   7 Chased      the quillons fork and the crown grows over the crest.
 *   8 Crowned     wings, claws around the stone, and the body stops being
 *                 straight.
 *   9 Unlabelled  a deeper sweep, teeth under the guard, and — see the aura of
 *                 the same name — the row that would carry a maker's mark is
 *                 left empty. On a shelf of animated legendaries a deliberate
 *                 absence is the loudest thing there.
 *
 * `polish` withholds the specular step at the bottom of the ladder, which is
 * what makes rungs 1-2 read as raw stock: unfinished metal does not catch the
 * light, and handing it a highlight anyway is the single fastest way to make
 * nine rungs look like one weapon in nine hues.
 */
const FORGE_RUNGS = [
  null,
  { rung: 1, name: 'Unworked',   widen: 0, fuller: 0, teeth: 0, inlay: 0, stone: 0, crest: 0, curve: 0, polish: 0, motion: 'still' },
  { rung: 2, name: 'Trued',      widen: 0, fuller: 0, teeth: 1, inlay: 0, stone: 1, crest: 0, curve: 0, polish: 1, motion: 'still' },
  { rung: 3, name: 'Fullered',   widen: 1, fuller: 1, teeth: 1, inlay: 0, stone: 1, crest: 0, curve: 0, polish: 1, motion: 'still' },
  { rung: 4, name: 'Quenched',   widen: 1, fuller: 2, teeth: 2, inlay: 1, stone: 2, crest: 0, curve: 0, polish: 2, motion: 'still' },
  { rung: 5, name: 'Inlaid',     widen: 1, fuller: 2, teeth: 3, inlay: 2, stone: 2, crest: 1, curve: 0, polish: 2, motion: 'a specular drifts along the edge' },
  { rung: 6, name: 'Runed',      widen: 2, fuller: 3, teeth: 3, inlay: 2, stone: 3, crest: 2, curve: 0, polish: 2, motion: 'and motes lift off the metal' },
  { rung: 7, name: 'Chased',     widen: 2, fuller: 3, teeth: 4, inlay: 3, stone: 3, crest: 3, curve: 0, polish: 2, motion: 'and the inlay pulses along its length' },
  { rung: 8, name: 'Crowned',    widen: 2, fuller: 3, teeth: 4, inlay: 3, stone: 4, crest: 4, curve: 1, polish: 2, motion: 'and the stone is lit from inside' },
  { rung: 9, name: 'Unlabelled', widen: 2, fuller: 3, teeth: 5, inlay: 3, stone: 4, crest: 4, curve: 2, polish: 2, motion: 'and the maker’s row is left empty' },
];

export function clampTier(tier) {
  const t = Math.round(Number(tier));
  if (!Number.isFinite(t)) return 1;
  return t < 1 ? 1 : t > FORGE_TIER_COUNT ? FORGE_TIER_COUNT : t;
}

export function forgeRung(tier) { return FORGE_RUNGS[clampTier(tier)]; }

export function forgeTierName(tier) { return forgeRung(tier).name; }

/* Rung 5 is where the ladder starts moving, and it is the ONLY place that
 * number is written down: forgeAnimate(), forgeInfo() and the vocabulary all
 * read it from here rather than each carrying their own copy of the rule. */
export const FORGE_FIRST_ANIMATED = 5;

/* Which rungs move. Two things can pin a rung that would otherwise animate:
 * `frames: 1` on the art dict, which gauntlet/forge.py documents as the
 * override legendaries asked for, and the `stillness` aura — an aura whose
 * whole content is that a weapon which ought to be moving is not. */
export function forgeFrameCount(tier, art) {
  if (art && art.frames === 1) return 1;
  if (art && art.aura === 'stillness') return 1;
  return forgeRung(tier).rung >= FORGE_FIRST_ANIMATED ? FORGE_FRAMES : 1;
}

/* ---------------- the weapons ----------------
 * Ten families, authored at rung 1 and authored DELIBERATELY PLAIN. A rung-1
 * sword is a bar of stock with a straight guard, no fuller, no inlay and a
 * cap where a pommel stone will go, because a ladder whose bottom rung already
 * has wings has nowhere to climb and ends up escalating in hue — which is the
 * failure the whole of this file exists to avoid.
 *
 * Every family declares its ANATOMY rather than leaving the passes below to
 * guess it. A guess is wrong exactly once per family and then it is wrong
 * forever: a fuller cut down the middle of a bow, a pommel stone set in the
 * butt-spike of a spear. Naming the parts costs six numbers and buys the
 * parametric passes the right to be simple.
 *
 *   blade   [y0,y1]  the working mass — what gets broadened, grooved, curved
 *   guard   y        where quillons and teeth grow, or null for a weapon with
 *                    no guard, in which case the widest row stands in
 *   grip    [y0,y1]  wrapped, never decorated; a decorated grip is a blister
 *   pommel  y        the counterweight
 *   stones  [{y,x}]  where a set stone belongs. x is the LEFT column of a six
 *                    wide setting, because a stone placed by an algorithm
 *                    always lands in the wrong hole
 *   crest   {y,x,dir} 'up' grows spikes above (x is the centre column);
 *                    'pommel' grows the pommel upward into the grip (x is the
 *                    left column of a six wide flare)
 *   axis    x        the long centreline, for inlay and motes
 *   kind    blade | haft | head | bow | focus — how the passes interpret it
 *   curve   whether the blade may be swept at the top rungs. A crossed pair
 *           and an axe head cannot be, and shearing them anyway produces the
 *           one artefact that makes procedural art look procedural
 */
const FORGE_WEAPONS = {
  /* The archivist's Hashblade and every straight sword the smith will ever be
   * handed. This is the family the ladder was designed on. */
  sword: {
    label: 'blade', kind: 'blade', axis: 16, curve: true,
    blade: [1, 20], guard: 21, guard2: 22, grip: [23, 27], pommel: 28,
    stones: [{ y: 28, x: 13 }], crest: { y: 28, x: 13, dir: 'pommel' },
    grid: [
      fblank(), fmid('oo'), fmid('oBBo'), fmid('oBBo'),
      ...frepeat(fmid('oBBBBo'), 17),
      fmid('oggggggo'), fmid('oggggo'),
      ...frepeat(fmid('osso'), 5),
      fmid('oggggo'), fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      /* Langets: two straps of trim running up off the guard onto the blade.
       * The first thing a real smith adds to a blade he intends to keep. */
      5: [[20, 13, 'g'], [20, 18, 'g'], [19, 13, 'g'], [19, 18, 'g'],
          [22, 12, 'oggggggo']],
      /* The grip gains a risered wrap. Four pixels on each side of the hand,
       * which at 32px is the difference between a tool and a weapon. */
      6: [[24, 13, 'og'], [24, 18, 'go'], [26, 13, 'og'], [26, 18, 'go']],
      /* A ricasso — the blade squares out where the hand would choke up on it.
       * Authored at widen 2 columns, which is what rung 6 is drawn at. */
      7: [[19, 11, 'oB'], [19, 20, 'Bo'], [20, 11, 'oB'], [20, 20, 'Bo']],
      /* Swept wings. They start exactly where the quillon ticks the teeth pass
       * grew end, so guard and wing are one continuous sweep rather than two
       * features that happen to be near each other. */
      8: [[18, 8, 'ogg'], [17, 7, 'ogg'], [16, 7, 'oo'],
          [18, 21, 'ggo'], [17, 22, 'ggo'], [16, 23, 'oo']],
      /* And at the last rung they reach past the width of the guard. Note the
       * row the wing capped at is re-cut as trim rather than left as outline:
       * a cap buried inside a longer wing is a black line across it. */
      9: [[16, 6, 'ogg'], [15, 5, 'ogg'], [14, 4, 'ogg'], [13, 4, 'oo'],
          [16, 23, 'ggo'], [15, 24, 'ggo'], [14, 25, 'ggo'], [13, 26, 'oo']],
    },
  },

  /* The berserker's pair. Crossed rather than parallel, because two parallel
   * blades at 32px read as one thick blade and the whole point of a pair is
   * that you can tell it is a pair from the outline. */
  sabers: {
    label: 'pair', kind: 'blade', axis: 16, curve: false,
    blade: [2, 24], guard: 25, grip: [26, 27], pommel: 28,
    stones: [{ y: 28, x: 2 }, { y: 28, x: 24 }],
    crest: { y: 28, x: 2, dir: 'pommel' },
    crest2: { y: 28, x: 24, dir: 'pommel' },
    grid: [
      fblank(), fblank(),
      frow(4, 'oo', 26, 'oo'),
      frow(3, 'oBBo', 25, 'oBBo'), frow(4, 'oBBo', 24, 'oBBo'),
      frow(5, 'oBBo', 23, 'oBBo'), frow(6, 'oBBo', 22, 'oBBo'),
      frow(7, 'oBBo', 21, 'oBBo'), frow(8, 'oBBo', 20, 'oBBo'),
      frow(9, 'oBBo', 19, 'oBBo'), frow(10, 'oBBo', 18, 'oBBo'),
      frow(11, 'oBBo', 17, 'oBBo'), frow(12, 'oBBo', 16, 'oBBo'),
      frow(13, 'oBBo', 15, 'oBBo'), frow(13, 'oBBBBo'),
      frow(15, 'oBBo', 13, 'oBBo'), frow(16, 'oBBo', 12, 'oBBo'),
      frow(17, 'oBBo', 11, 'oBBo'), frow(18, 'oBBo', 10, 'oBBo'),
      frow(19, 'oBBo', 9, 'oBBo'), frow(20, 'oBBo', 8, 'oBBo'),
      frow(21, 'oBBo', 7, 'oBBo'), frow(22, 'oBBo', 6, 'oBBo'),
      frow(23, 'oBBo', 5, 'oBBo'), frow(24, 'oBBo', 4, 'oBBo'),
      frow(2, 'oggggo', 24, 'oggggo'),
      frow(3, 'osso', 25, 'osso'), frow(3, 'osso', 25, 'osso'),
      frow(3, 'oggo', 25, 'oggo'), frow(4, 'oo', 26, 'oo'),
      fblank(), fblank(),
    ],
    growth: {
      5: [[24, 2, 'og'], [24, 27, 'go'], [23, 3, 'og'], [23, 26, 'go']],
      6: [[26, 2, 'og'], [26, 29, 'go'], [27, 2, 'og'], [27, 29, 'go']],
      /* Ricasso squares on both blades, at the rows where they cross. */
      7: [[16, 9, 'oB'], [16, 20, 'Bo'], [17, 8, 'oB'], [17, 21, 'Bo']],
      /* Recurve hooks at the tips — the move a straight blade cannot make and
       * the reason this family does not take the shear. */
      8: [[3, 1, 'oo'], [4, 1, 'og'], [3, 28, 'oo'], [4, 29, 'go']],
      9: [[2, 1, 'og'], [5, 0, 'oo'], [2, 28, 'go'], [5, 30, 'oo'],
          [6, 3, 'oo'], [6, 26, 'oo']],
    },
  },

  /* The seer's Tracing Needle, and anything short. A dagger is mostly grip, so
   * it escalates at the hilt where a sword escalates at the blade. */
  dagger: {
    label: 'knife', kind: 'blade', axis: 16, curve: true,
    blade: [5, 18], guard: 19, guard2: 20, grip: [21, 25], pommel: 26,
    stones: [{ y: 26, x: 13 }], crest: { y: 26, x: 13, dir: 'pommel' },
    grid: [
      ...frepeat(fblank(), 5),
      fmid('oo'), fmid('oBBo'), fmid('oBBo'),
      ...frepeat(fmid('oBBBBo'), 11),
      fmid('oggggggo'), fmid('oggggo'),
      ...frepeat(fmid('osso'), 5),
      fmid('oggggo'), fmid('oggo'),
      ...frepeat(fblank(), 4),
    ],
    growth: {
      5: [[18, 13, 'g'], [18, 18, 'g'], [20, 12, 'oggggggo']],
      6: [[22, 13, 'og'], [22, 18, 'go'], [24, 13, 'og'], [24, 18, 'go']],
      7: [[17, 11, 'oB'], [17, 20, 'Bo'], [18, 11, 'oB'], [18, 20, 'Bo']],
      8: [[16, 8, 'ogg'], [15, 7, 'ogg'], [14, 7, 'oo'],
          [16, 21, 'ggo'], [15, 22, 'ggo'], [14, 23, 'oo']],
      9: [[14, 6, 'ogg'], [13, 5, 'ogg'], [12, 4, 'ogg'], [11, 4, 'oo'],
          [14, 23, 'ggo'], [13, 24, 'ggo'], [12, 25, 'ggo'], [11, 26, 'oo']],
    },
  },

  /* Recursion Spear. A haft weapon escalates at the head and at the butt, and
   * never in the middle: a spear with decoration halfway down the shaft is a
   * spear nobody can hold. */
  spear: {
    label: 'polearm', kind: 'haft', axis: 16, curve: true,
    blade: [5, 11], guard: 12, grip: [13, 28], pommel: 29,
    stones: [{ y: 29, x: 13 }], crest: { y: 5, x: 16, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 5),
      fmid('oo'), fmid('oBBo'), fmid('oBBBBo'),
      fmid('oBBBBBBo'), fmid('oBBBBBBo'), fmid('oBBBBo'), fmid('oBBo'),
      fmid('oggo'),
      ...frepeat(fmid('osso'), 16),
      fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      5: [[12, 12, 'oggggggo'], [13, 13, 'og'], [13, 18, 'go']],
      6: [[11, 13, 'og'], [11, 18, 'go'], [28, 13, 'og'], [28, 18, 'go']],
      /* Wings behind the head — a boar spear's crossbar, the detail that says
       * this is a weapon for something that pushes back. */
      7: [[11, 11, 'oB'], [11, 20, 'Bo'], [10, 11, 'oo'], [10, 20, 'oo']],
      8: [[11, 7, 'ogg'], [10, 7, 'oo'], [11, 22, 'ggo'], [10, 23, 'oo']],
      9: [[9, 5, 'ogg'], [8, 5, 'oo'], [9, 24, 'ggo'], [8, 25, 'oo']],
    },
  },

  /* Queue Lance. Heavier than the spear and it shows it at the vamplate, which
   * is the one silhouette a lance has that nothing else does. */
  lance: {
    label: 'lance', kind: 'haft', axis: 16, curve: false,
    blade: [4, 11], guard: 12, guard2: 13, grip: [15, 27], pommel: 28,
    stones: [{ y: 28, x: 13 }], crest: { y: 4, x: 16, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 4),
      fmid('oo'), fmid('oBBo'), fmid('oBBBBo'), fmid('oBBBBo'),
      fmid('oBBBBBBo'), fmid('oBBBBBBo'),
      fmid('oBBBBBBBBo'), fmid('oBBBBBBBBo'),
      fmid('oggggggggggo'), fmid('oggggggggo'), fmid('oBBBBo'),
      ...frepeat(fmid('osso'), 13),
      fmid('oggggo'), fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      5: [[12, 9, 'og'], [12, 22, 'go'], [13, 10, 'og'], [13, 21, 'go']],
      6: [[14, 13, 'og'], [14, 18, 'go'], [26, 13, 'og'], [26, 18, 'go']],
      7: [[11, 10, 'oB'], [11, 21, 'Bo']],
      /* The grip gains a wrap rather than the vamplate gaining more width.
       * A lance is already the widest thing in this section at rung 6 and
       * pushing it further just fills the box with fitting. */
      8: [[15, 13, 'og'], [15, 18, 'go'], [16, 13, 'og'], [16, 18, 'go']],
      9: [[10, 7, 'ogg'], [9, 7, 'oo'], [10, 22, 'ggo'], [9, 23, 'oo']],
    },
  },

  /* Tree Axe and the berserker's Draft Axe. The one family that is asymmetric
   * by construction, so it escalates asymmetrically: the bit deepens and only
   * at the top does a back-spike appear. Symmetry is what makes procedural art
   * look procedural, and an axe is the family that gets to say so. */
  axe: {
    label: 'axe', kind: 'head', axis: 20, curve: false, mass: 'B',
    blade: [5, 14], guard: 15, grip: [16, 28], pommel: 29,
    stones: [{ y: 29, x: 11 }], crest: { y: 4, x: 13, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 4),
      frow(12, 'oooo'),
      frow(12, 'osso', 16, 'oooo'),
      frow(12, 'osso', 16, 'BBBBo'),
      frow(12, 'osso', 16, 'BBBBBBo'),
      frow(12, 'osso', 16, 'BBBBBBBo'),
      frow(12, 'osso', 16, 'BBBBBBBBo'),
      frow(12, 'osso', 16, 'BBBBBBBBo'),
      frow(12, 'osso', 16, 'BBBBBBBo'),
      frow(12, 'osso', 16, 'BBBBBBo'),
      frow(12, 'osso', 16, 'BBBBo'),
      frow(12, 'osso', 16, 'oooo'),
      frow(12, 'oggo'),
      ...frepeat(frow(12, 'osso'), 13),
      frow(12, 'oggo'), frow(13, 'oo'), fblank(),
    ],
    growth: {
      /* The bit deepens forward. Authored one column outside the rung-3
       * geometry rather than on top of it: a stamp that lands where the widen
       * pass has already been measures as a change to nothing at all. */
      5: [[8, 24, 'Bo'], [9, 25, 'Bo'], [10, 25, 'Bo'], [11, 24, 'Bo']],
      /* A beard: the bit hooks back under, toward the hand. The cheapest way
       * to make an axe read as a weapon rather than as a tool. */
      6: [[14, 16, 'BBBBo'], [15, 16, 'BBo']],
      /* The top of the head squares up and reaches forward over the bit. */
      7: [[4, 16, 'oooo'], [5, 16, 'BBBBo'], [6, 20, 'BBo'], [7, 22, 'BBo']],
      /* The back-spike. Nothing at all on the far side of the haft until now,
       * which is what makes rung 7 the rung the shape changes character. */
      8: [[8, 9, 'ogo'], [9, 8, 'ogo'], [10, 8, 'ogo'], [11, 9, 'ogo'],
          [7, 10, 'oo'], [12, 10, 'oo']],
      9: [[9, 5, 'ogg'], [10, 5, 'ogg'], [8, 6, 'oo'], [11, 6, 'oo']],
    },
  },

  /* Heap Hammer and the warden's Boundary Maul. A head weapon has nothing to
   * sharpen, so it escalates by growing MASS: the head squares up, gains
   * flanges, then a crown of spikes. */
  hammer: {
    label: 'maul', kind: 'head', axis: 16, curve: false,
    blade: [4, 10], guard: 11, grip: [12, 28], pommel: 29,
    stones: [{ y: 29, x: 13 }], crest: { y: 4, x: 16, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 4),
      fmid('oooooooooooo'),
      ...frepeat(fmid('oBBBBBBBBBBo'), 5),
      fmid('oooooooooooo'),
      fmid('oggo'),
      ...frepeat(fmid('osso'), 17),
      fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      5: [[5, 8, 'oB'], [5, 23, 'Bo'], [6, 8, 'oB'], [6, 23, 'Bo'],
          [7, 8, 'oB'], [7, 23, 'Bo']],
      6: [[4, 8, 'oo'], [4, 23, 'oo'], [8, 8, 'oo'], [8, 23, 'oo'],
          [9, 9, 'oo'], [9, 22, 'oo']],
      /* Flanges: the faces of the head step out into ribs. */
      7: [[6, 6, 'oBB'], [6, 24, 'BBo'], [7, 6, 'oBB'], [7, 24, 'BBo'],
          [5, 7, 'oo'], [5, 24, 'oo'], [8, 7, 'oo'], [8, 24, 'oo']],
      8: [[6, 3, 'ogo'], [7, 3, 'ogo'], [5, 4, 'oo'], [8, 4, 'oo'],
          [6, 27, 'ogo'], [7, 27, 'ogo'], [5, 27, 'oo'], [8, 27, 'oo']],
      /* A flange under the head rather than another row on top of it: the
       * crest ladder owns everything above the crown, and two passes adding
       * rows to the same edge is how a head ends up with its outline buried
       * one row inside itself. */
      9: [[9, 6, 'oo'], [9, 24, 'oo'],
          [11, 10, 'oggggggggggo'], [12, 12, 'oggggggo']],
    },
  },

  /* Window Staff. No guard and no edge, so every move it has is at the head —
   * which is why the crest ladder does the heavy lifting here and the teeth
   * pass falls back to the widest row. */
  staff: {
    label: 'staff', kind: 'focus', axis: 16, curve: false,
    blade: [4, 9], guard: 9, grip: [10, 28], pommel: 29,
    stones: [{ y: 29, x: 13 }], crest: { y: 4, x: 16, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 4),
      fmid('oggo'), fmid('ogmmgo'), fmid('ogmmmmgo'),
      fmid('ogmmmmgo'), fmid('ogmmgo'), fmid('oggo'),
      ...frepeat(fmid('osso'), 19),
      fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      /* Bindings down the shaft. Authored as rings rather than as prongs off
       * the head because the head is already carrying four parametric passes,
       * and a fifth thing up there stops being a weapon and becomes a pile.
       * A staff that gains fittings along its length is also simply what a
       * worked staff looks like. */
      5: [[10, 13, 'oggggo'], [11, 13, 'oggggo']],
      6: [[26, 13, 'oggggo'], [27, 13, 'oggggo']],
      7: [[12, 13, 'oggggo'], [13, 14, 'oggo']],
      8: [[19, 13, 'oggggo'], [20, 13, 'oggggo']],
      9: [[15, 13, 'oggggo'], [16, 12, 'oggggggo'], [17, 13, 'oggggo']],
    },
  },

  /* Matrix Bow. Everything about a bow is the limb, so the limb is what grows:
   * it deepens, it recurves, and at the top it carries a second string. */
  bow: {
    label: 'bow', kind: 'bow', axis: 8, curve: false, teethWidth: 10,
    blade: [4, 29], guard: 14, guard2: 13, grip: [15, 18], pommel: null,
    stones: [{ y: 16, x: 5 }], crest: { y: 4, x: 19, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 4),
      frow(18, 'oooo'),
      frow(16, 'osso', 21, 'w'), frow(14, 'osso', 21, 'w'),
      frow(12, 'osso', 21, 'w'), frow(11, 'osso', 21, 'w'),
      frow(10, 'osso', 21, 'w'), frow(9, 'osso', 21, 'w'),
      frow(8, 'osso', 21, 'w'), frow(7, 'osso', 21, 'w'),
      frow(7, 'osso', 21, 'w'), frow(6, 'osso', 21, 'w'),
      frow(5, 'osssso', 21, 'w'), frow(5, 'osssso', 21, 'w'),
      frow(5, 'osssso', 21, 'w'), frow(5, 'osssso', 21, 'w'),
      frow(6, 'osso', 21, 'w'), frow(7, 'osso', 21, 'w'),
      frow(7, 'osso', 21, 'w'), frow(8, 'osso', 21, 'w'),
      frow(9, 'osso', 21, 'w'), frow(10, 'osso', 21, 'w'),
      frow(11, 'osso', 21, 'w'), frow(12, 'osso', 21, 'w'),
      frow(14, 'osso', 21, 'w'), frow(16, 'osso', 21, 'w'),
      frow(18, 'oooo'),
      fblank(), fblank(),
    ],
    growth: {
      /* The belly deepens, away from the riser — which the teeth pass has
       * already taken as far as a riser is allowed to go, so a bow is the one
       * family whose middle rungs have to be authored rather than grown. */
      4: [[8, 10, 'os'], [9, 9, 'os'], [24, 9, 'os'], [25, 10, 'os']],
      5: [[11, 7, 'os'], [12, 6, 'os'], [21, 6, 'os'], [22, 7, 'os']],
      6: [[14, 5, 'og'], [19, 5, 'og'], [15, 11, 'go'], [18, 11, 'go']],
      /* Recurve: the tips bend back against the string. */
      7: [[5, 20, 'oo'], [6, 19, 'og'], [28, 20, 'oo'], [27, 19, 'og'],
          [4, 17, 'oo'], [29, 17, 'oo']],
      /* A nocked arrow. The one detail that makes a bow read as a bow, and it
       * is asymmetric, which is the sort of thing you only put on the weapon
       * you actually carry. */
      8: [[16, 22, 'ssssssgo'], [15, 28, 'ooo'], [17, 28, 'ooo'],
          [15, 22, 'o'], [17, 22, 'o']],
      9: [[8, 22, 'og'], [9, 23, 'og'], [24, 22, 'og'], [23, 23, 'og'],
          [3, 18, 'oooo'], [30, 18, 'oooo']],
    },
  },

  /* The artificer's Dynamic Relic, the analyst's Calipers, the archivist's
   * Recall Chain: a held focus rather than a weapon. It has no edge to sharpen
   * so the core itself is what the smith works — it is cut, faceted, and
   * finally caged. */
  focus: {
    label: 'focus', kind: 'focus', axis: 16, curve: false,
    blade: [4, 13], guard: 14, guard2: 15, grip: [16, 26], pommel: 27,
    stones: [{ y: 27, x: 13 }], crest: { y: 4, x: 16, dir: 'up' },
    grid: [
      ...frepeat(fblank(), 4),
      fmid('oo'), fmid('ommo'), fmid('ommmmo'), fmid('ommmmmmo'),
      fmid('ommmmmmmmo'), fmid('ommmmmmmmo'),
      fmid('ommmmmmo'), fmid('ommmmo'), fmid('ommo'), fmid('oo'),
      fmid('oggggo'), fmid('oggo'),
      ...frepeat(fmid('osso'), 11),
      fmid('oggggo'), fmid('oggo'), fmid('oo'),
      fblank(), fblank(),
    ],
    growth: {
      5: [[14, 11, 'og'], [14, 20, 'go'], [15, 12, 'og'], [15, 19, 'go']],
      /* A cage. Two arms of trim reaching up around the core, which is what
       * separates a relic somebody forged from a rock somebody found. */
      6: [[13, 10, 'og'], [13, 21, 'go'], [12, 10, 'og'], [12, 21, 'go'],
          [11, 10, 'oo'], [11, 21, 'oo']],
      7: [[10, 9, 'og'], [10, 22, 'go'], [9, 9, 'og'], [9, 22, 'go'],
          [8, 9, 'oo'], [8, 22, 'oo']],
      8: [[7, 8, 'ogo'], [6, 8, 'ogo'], [5, 9, 'oo'],
          [7, 21, 'ogo'], [6, 21, 'ogo'], [5, 21, 'oo']],
      9: [[9, 5, 'ogo'], [8, 5, 'oo'], [10, 5, 'oo'],
          [9, 24, 'ogo'], [8, 24, 'oo'], [10, 24, 'oo'],
          [3, 14, 'oggo'], [2, 15, 'oo']],
    },
  },

  /* ---- the three that gauntlet/forge.py's art brief asked for by name ----
   * Six signature blades were sharing four grids: the Calipers and the Chain
   * were both `relic`, the Maul and the Spanner were both `hammer`. The brief
   * calls six distinct hand poses "the cheapest legibility win available
   * here", and it is right — two lines that share a silhouette are two lines
   * the player cannot tell apart at the one moment it matters, which is when
   * somebody else is holding one.
   */

  /* The Analyst's Calipers. Two arms on a pivot, open at the top, and no edge
   * anywhere on it — the only weapon in the game that has never cut anything.
   * The gap between the jaws is the point of the object, so the growth table
   * is careful never to close it: this line escalates at the pivot and along
   * the outside of the arms, never inward. */
  calipers: {
    label: 'calipers', kind: 'blade', axis: 16, curve: false, mass: 'B',
    teethWidth: 16, keepGap: [15, 16],
    blade: [4, 15], guard: 16, guard2: 17, grip: [19, 27], pommel: 28,
    stones: [{ y: 28, x: 13 }], crest: { y: 28, x: 13, dir: 'pommel' },
    grid: [
      ...frepeat(fblank(), 4),
      frow(9, 'ooooo', 18, 'ooooo'),
      ...frepeat(frow(9, 'oBBBo', 18, 'oBBBo'), 3),
      ...frepeat(frow(10, 'oBBBo', 17, 'oBBBo'), 6),
      ...frepeat(frow(10, 'oBBBBBBBBBBo'), 2),
      frow(12, 'ogmmmmgo'), fmid('oggggo'), fmid('oggo'),
      ...frepeat(fmid('osso'), 9),
      fmid('oggggo'), fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      5: [[16, 10, 'og'], [16, 19, 'go'], [17, 12, 'og'], [17, 17, 'go']],
      6: [[3, 9, 'ooooo'], [3, 18, 'ooooo']],
      7: [[8, 8, 'og'], [9, 8, 'og'], [8, 21, 'go'], [9, 21, 'go'],
          [7, 9, 'oo'], [7, 21, 'oo'], [10, 9, 'oo'], [10, 21, 'oo']],
      8: [[5, 7, 'og'], [6, 7, 'og'], [4, 8, 'oo'], [7, 8, 'oo'],
          [5, 22, 'go'], [6, 22, 'go'], [4, 21, 'oo'], [7, 21, 'oo']],
      9: [[11, 7, 'og'], [12, 7, 'og'], [10, 8, 'oo'], [13, 8, 'oo'],
          [11, 22, 'go'], [12, 22, 'go'], [10, 21, 'oo'], [13, 21, 'oo']],
    },
  },

  /* The Recall Chain. Three heavy links and the narrow joins between them,
   * which is a silhouette nothing else in the game has. The rings themselves
   * are the `link` and `chain` motifs' job — the grid supplies the mass and
   * the motif pass cuts the holes, which is the division of labour the whole
   * motif vocabulary exists for. */
  chain: {
    label: 'chain', kind: 'focus', axis: 16, curve: false, mass: 'B',
    blade: [4, 18], guard: 19, guard2: 20, grip: [21, 27], pommel: 28,
    stones: [{ y: 28, x: 13 }], crest: { y: 28, x: 13, dir: 'pommel' },
    grid: [
      ...frepeat(fblank(), 4),
      fmid('oooo'), fmid('oBBBBo'), fmid('oBBBBo'), fmid('oooo'),
      fmid('oBBo'),
      fmid('oooo'), fmid('oBBBBo'), fmid('oBBBBo'), fmid('oooo'),
      fmid('oBBo'),
      fmid('oooo'), fmid('oBBBBo'), fmid('oBBBBo'), fmid('oooo'),
      fmid('oBBo'), fmid('oggo'), fmid('oggggo'),
      ...frepeat(fmid('osso'), 7),
      fmid('oggggo'), fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      5: [[19, 13, 'og'], [19, 18, 'go'], [20, 12, 'og'], [20, 19, 'go']],
      6: [[8, 13, 'og'], [8, 18, 'go'], [13, 13, 'og'], [13, 18, 'go'],
          [18, 13, 'og'], [18, 18, 'go']],
      7: [[4, 12, 'oooooooo'], [7, 12, 'oooooooo'], [9, 12, 'oooooooo'],
          [12, 12, 'oooooooo'], [14, 12, 'oooooooo'], [17, 12, 'oooooooo']],
      8: [[5, 10, 'og'], [6, 10, 'og'], [4, 10, 'oo'], [7, 10, 'oo'],
          [5, 20, 'go'], [6, 20, 'go'], [4, 20, 'oo'], [7, 20, 'oo']],
      9: [[15, 10, 'og'], [16, 10, 'og'], [14, 10, 'oo'], [17, 10, 'oo'],
          [15, 20, 'go'], [16, 20, 'go'], [14, 20, 'oo'], [17, 20, 'oo']],
    },
  },

  /* The Toolwright's Spanner. An open jaw and a throat, which is a hammer that
   * is unmistakably not a hammer — and it is the only head in the section with
   * a HOLE in it, so it reads at any size. */
  spanner: {
    label: 'spanner', kind: 'head', axis: 16, curve: false, mass: 'B',
    teethWidth: 20, keepGap: [14, 17],
    blade: [4, 11], guard: 12, guard2: 13, grip: [13, 27], pommel: 28,
    stones: [{ y: 28, x: 13 }], crest: { y: 28, x: 13, dir: 'pommel' },
    grid: [
      ...frepeat(fblank(), 4),
      frow(9, 'oooo', 19, 'oooo'),
      frow(9, 'oBBo', 19, 'oBBo'), frow(9, 'oBBo', 19, 'oBBo'),
      frow(10, 'oBBo', 18, 'oBBo'),
      frow(10, 'oBBBBBBBBBBo'), frow(10, 'oBBBBBBBBBBo'),
      frow(11, 'oBBBBBBBBo'), frow(12, 'oBBBBBBo'),
      fmid('oggggo'),
      ...frepeat(fmid('osso'), 15),
      fmid('oggggo'), fmid('oggo'), fmid('oo'), fblank(),
    ],
    growth: {
      5: [[12, 11, 'oggggggggo']],
      6: [[3, 9, 'oooo'], [3, 19, 'oooo']],
      7: [[5, 7, 'og'], [6, 7, 'og'], [4, 8, 'oo'], [7, 8, 'oo'],
          [5, 23, 'go'], [6, 23, 'go'], [4, 22, 'oo'], [7, 22, 'oo']],
      8: [[10, 8, 'og'], [10, 22, 'go'], [11, 9, 'og'], [11, 21, 'go']],
      9: [[8, 6, 'og'], [9, 6, 'og'], [7, 7, 'oo'], [10, 7, 'oo'],
          [8, 24, 'go'], [9, 24, 'go'], [7, 23, 'oo'], [10, 23, 'oo']],
    },
  },
};

export const FORGE_WEAPON_KEYS = Object.keys(FORGE_WEAPONS);

/* Every name the rest of the game might hand us for a weapon: the six class
 * ids, the six signature weapon ids out of gauntlet/classes.py, the ten ids in
 * world.WEAPONS, the icon vocabulary items.py already ships, and the ordinary
 * English words a designer will type into a JSON file at four in the morning.
 *
 * This table is the cheap half of rule D. The expensive half is that missing
 * from it is not an error: forgeWeaponKey() falls through to a substring scan
 * and then to `sword`, because a blade nobody has heard of is still a blade
 * and a screen with a blade on it beats a screen with a stack trace on it. */
/* The six lines gauntlet/forge.py ships, by id, each with its own silhouette.
 * That last part is the point: forge.py's own art brief calls two lines
 * sharing a grid "the cheapest legibility win available here", and it was
 * right — the Calipers and the Chain were both `relic`, the Maul and the
 * Spanner were both `hammer`, and a player cannot tell apart two weapons that
 * are the same picture. `tint` is the class colour that file carries; it is
 * the fallback accent when a caller gives a blade and a rung but no art. */
const FORGE_BLADES = {
  analysts_calipers:   { family: 'calipers', tint: '#7ec8ff' },
  draft_axe:           { family: 'axe',      tint: '#ff7a4a' },
  recall_chain:        { family: 'chain',    tint: '#c8a8ff' },
  boundary_maul:       { family: 'hammer',   tint: '#8fd07a' },
  toolwrights_spanner: { family: 'spanner',  tint: '#e8c37d' },
  tracing_needle:      { family: 'dagger',   tint: '#ff6a7a' },
};

export const FORGE_BLADE_KEYS = Object.keys(FORGE_BLADES);

const WEAPON_ALIAS = {
  /* classes */
  archivist: 'chain', berserker: 'axe', seer: 'dagger',
  analyst: 'calipers', warden: 'hammer', artificer: 'spanner',
  /* the six signature lines */
  recallchain: 'chain', draftaxe: 'axe', tracingneedle: 'dagger',
  analystscalipers: 'calipers', boundarymaul: 'hammer',
  toolwrightsspanner: 'spanner',
  caliper: 'calipers', wrench: 'spanner', maul: 'hammer',
  /* world.WEAPONS */
  hashblade: 'sword', twinsabers: 'sabers', windowstaff: 'staff',
  recursionspear: 'spear', queuelance: 'lance', depthblade: 'dagger',
  treeaxe: 'axe', heaphammer: 'hammer', matrixbow: 'bow',
  dynamicrelic: 'focus',
  /* icons and plain words */
  blade: 'sword', longsword: 'sword', greatsword: 'sword', claymore: 'sword',
  saber: 'sabers', sabre: 'sabers', sabres: 'sabers', twinblades: 'sabers',
  knife: 'dagger', dirk: 'dagger', needle: 'dagger', stiletto: 'dagger',
  polearm: 'spear', glaive: 'spear', halberd: 'spear', pike: 'lance',
  hatchet: 'axe', cleaver: 'axe', mace: 'hammer', warhammer: 'hammer',
  rod: 'staff', wand: 'staff', cane: 'staff', scepter: 'staff',
  sceptre: 'staff', crozier: 'staff',
  crossbow: 'bow', longbow: 'bow', shortbow: 'bow',
  relic: 'focus', orb: 'focus', lens: 'focus', prism: 'focus',
  core: 'focus', tome: 'focus', talisman: 'focus',
};

const weaponKeyCache = new Map();

/* Resolve anything at all to a family. Never throws, never returns undefined.
 * Order is intent first: an explicit family key beats an alias beats a
 * substring, because "recursion_spear" contains "sword" in nobody's spelling
 * but "greatsword_of_the_spearwright" contains both. */
export function forgeWeaponKey(weapon) {
  if (weapon && FORGE_WEAPONS[weapon]) return weapon;
  if (weapon && FORGE_BLADES[weapon]) return FORGE_BLADES[weapon].family;
  const raw = weapon && typeof weapon === 'object'
    ? (weapon.weapon || weapon.family || weapon.id || weapon.icon || weapon.name)
    : weapon;
  const s = slug(raw);
  if (!s) return 'sword';
  if (FORGE_WEAPONS[s]) return s;
  for (const id of FORGE_BLADE_KEYS) if (slug(id) === s) return FORGE_BLADES[id].family;
  const hit = weaponKeyCache.get(s);
  if (hit) return hit;
  let found = WEAPON_ALIAS[s] || '';
  if (!found) {
    for (const k of FORGE_WEAPON_KEYS) if (s.includes(k)) { found = k; break; }
  }
  if (!found) {
    for (const a of Object.keys(WEAPON_ALIAS)) if (s.includes(a)) { found = WEAPON_ALIAS[a]; break; }
  }
  if (!found) found = 'sword';
  if (weaponKeyCache.size >= 256) weaponKeyCache.delete(weaponKeyCache.keys().next().value);
  weaponKeyCache.set(s, found);
  return found;
}

export function forgeWeapon(weapon) { return FORGE_WEAPONS[forgeWeaponKey(weapon)]; }

/* ---------------- geometry the passes share ----------------
 * Every pass below reads the grid it was handed rather than the table the grid
 * came from. That is not purity for its own sake: the passes run in sequence,
 * each one moves the edges, and a pass that used the AUTHORED column numbers
 * would decorate where the object used to be. Teeth grown on a guard that the
 * widen pass already pushed out is the whole difference between a weapon and
 * a weapon with its fittings floating beside it.
 */

/* Contiguous spans of non-empty cells on one row. A crossed pair has two per
 * row for most of its height and one where the blades meet, and every pass
 * that assumes exactly one of them is wrong for the berserker. */
function runsAt(cells, y) {
  const r = cells[y];
  if (!r) return [];
  const out = [];
  let a = -1;
  for (let x = 0; x < r.length; x++) {
    const solid = r[x] !== '.' && r[x] !== ' ';
    if (solid && a < 0) a = x;
    if (!solid && a >= 0) { out.push([a, x - 1]); a = -1; }
  }
  if (a >= 0) out.push([a, r.length - 1]);
  return out;
}

/* The run this family considers its working mass. `mass` names the interior
 * glyph a family cares about, which is how the axe's bit is worked and its
 * haft is left alone — a haft that broadens with the bit is a club. */
/* EVERY span of working material on this row, not just the widest one. A
 * crossed pair has two, a pair of caliper arms has two, and a pass that took
 * only the widest grooved one sabre of two and left the other blank — which
 * looks less like a design decision and more like a bug, because it was. */
function massRuns(cells, y, fam) {
  if (fam.mass) {
    const r = cells[y];
    const out = [];
    let a = -1;
    for (let x = 0; x <= r.length; x++) {
      const hit = x < r.length && r[x] === fam.mass;
      if (hit && a < 0) a = x;
      if (!hit && a >= 0) { if (x - 1 - a >= 1) out.push([a - 1, x]); a = -1; }
    }
    return out;
  }
  return runsAt(cells, y).filter(([a, b]) => b - a >= 2);
}

function massRun(cells, y, fam) {
  if (fam.mass) {
    /* An axe's bit and its haft are one unbroken run — they are joined, that
     * is what a socket is — so "the widest run" finds the whole thing and
     * grooves the handle. Name the material instead and take the span of it,
     * bounded by whatever sits either side. */
    const r = cells[y];
    let bestA = -1, bestB = -2, a = -1;
    for (let x = 0; x <= r.length; x++) {
      const hit = x < r.length && r[x] === fam.mass;
      if (hit && a < 0) a = x;
      if (!hit && a >= 0) { if (x - 1 - a > bestB - bestA) { bestA = a; bestB = x - 1; } a = -1; }
    }
    if (bestA < 0) return null;
    return [bestA - 1, bestB + 1];
  }
  let best = null;
  for (const [a, b] of runsAt(cells, y)) {
    if (b - a < 2) continue;
    if (!best || (b - a) > (best[1] - best[0])) best = [a, b];
  }
  return best;
}

function widestRowIn(cells, range) {
  let bestY = -1, bestW = -1;
  for (let y = range[0]; y <= range[1]; y++) {
    for (const [a, b] of runsAt(cells, y)) {
      if (b - a > bestW) { bestW = b - a; bestY = y; }
    }
  }
  return bestY;
}

const inBox = (y, x) => y >= 0 && y < FN && x >= 0 && x < FN;
/* Write only into empty space. Used by everything that reaches AROUND the
 * object — claws, crest spikes, teeth — because a claw that overwrites the
 * thing it is gripping is a hole. */
function soft(cells, y, x, ch) {
  if (!inBox(y, x)) return;
  if (cells[y][x] === '.' || cells[y][x] === ' ') cells[y][x] = ch;
}
function hard(cells, y, x, ch) { if (inBox(y, x)) cells[y][x] = ch; }

/* Which shadow glyph a groove cut into this material should be. A groove in
 * steel is body shadow; a groove in a grip is leather shadow; a groove in a
 * gem is gem shadow. One map, because a fuller drawn in body shadow down a
 * wooden haft is a stripe of grey paint. */
const GROOVE = {
  B: 'd', H: 'd', L: 'd', d: 'D', b: 'd',
  s: 'u', t: 'u', u: 'u', w: 'u',
  m: 'n', M: 'n', n: 'n',
  g: 'y', G: 'y', y: 'y',
  c: 'v', C: 'v',
};

/* ---------------- 1. broaden ----------------
 * The first thing the smith does that the player can see from across the room.
 * Only rows in the blade grow, only runs wide enough to have an interior, and
 * a row that has nearly tapered to a point grows less than the body does — so
 * the blade gets broader without the tip going blunt. */
function forgeWiden(cells, fam, extra) {
  if (!extra) return;
  const [y0, y1] = fam.blade;
  for (let y = y0; y <= y1; y++) {
    for (const [a, b] of runsAt(cells, y)) {
      const width = b - a - 1;
      if (width < 2) continue;
      if (cells[y][a] !== 'o' || cells[y][b] !== 'o') continue;
      /* Each edge grows in the material that is actually behind it. An axe row
       * is haft, then bit, in one run: broadening both ends with one glyph
       * either turns the handle into a club or puts wood on the cutting edge.
       * A row that is nothing but outline — the top and bottom cap of a hammer
       * head — grows not at all, or the cap becomes a black bar. */
      const li = cells[y][a + 1], ri = cells[y][b - 1];
      const addFor = (inner) => {
        if (inner === 'o' || inner === 'O' || inner === '.' || inner === ' ') return 0;
        if (fam.mass && inner !== fam.mass) return 0;
        /* Three interior pixels is a body; two is a taper. Widening a taper
         * as hard as a body blunts the point, and NOT widening a three-wide
         * arm leaves an instrument like the Calipers with no rung-3 move at
         * all — which is the failure this whole ladder exists to prevent. */
        return width >= 3 ? extra : Math.max(0, extra - 1);
      };
      let la = addFor(li), ra = addFor(ri);
      /* Some objects ARE their gap. The Calipers measure with the space
       * between two arms and the Spanner grips with the space between two
       * jaws; broadening those arms until they meet does not make a better
       * instrument, it makes a club. A family that has a gap says where it is
       * and the widen pass stops at the edge of it. */
      const gap = fam.keepGap;
      if (gap) {
        if (b < gap[0]) ra = Math.max(0, Math.min(ra, gap[0] - 1 - b));
        if (a > gap[1]) la = Math.max(0, Math.min(la, a - gap[1] - 1));
      }
      if (la && a - la >= 0) {
        cells[y][a] = li;
        for (let k = 1; k < la; k++) cells[y][a - k] = li;
        cells[y][a - la] = 'o';
      }
      if (ra && b + ra < FN) {
        cells[y][b] = ri;
        for (let k = 1; k < ra; k++) cells[y][b + k] = ri;
        cells[y][b + ra] = 'o';
      }
    }
  }
}

/* ---------------- 2. the fuller ----------------
 * A groove down the blade, and the one escalation in this whole section that
 * is allowed to be interior rather than outline — because a fuller IS
 * interior, and faking it as a notch in the edge would be drawing a saw.
 * It pays its way by getting LONGER: at rung 3 it is a short groove near the
 * shoulder, at rung 8 it runs the length of the blade with a rune cut into it.
 */
function fullerRows(fam, level) {
  const [y0, y1] = fam.blade;
  const len = y1 - y0 + 1;
  const frac = [0, 0.45, 0.70, 0.92][Math.min(3, level)];
  const out = [];
  /* A bow and a held focus have no shoulder and no point, so their groove is
   * a laminate line that grows outward from the middle instead of downward
   * from the tip. Same pass, honest about two different objects. */
  if (fam.kind === 'bow' || fam.kind === 'focus') {
    const mid = (y0 + y1) >> 1, half = Math.max(1, Math.round(len * frac / 2));
    for (let y = mid - half; y <= mid + half; y++) if (y >= y0 && y <= y1) out.push(y);
  } else {
    const end = y0 + Math.round(len * frac);
    for (let y = y0 + 2; y <= Math.min(end, y1); y++) out.push(y);
  }
  /* Never across the hand. A bow's blade range is the whole limb and the riser
   * is in the middle of it; a groove cut through the grip is a groove through
   * the part of the weapon that is wrapped. */
  if (!fam.grip) return out;
  return out.filter(y => y < fam.grip[0] || y > fam.grip[1]);
}

/* The two columns the centreline falls on. A blade an even number of pixels
 * wide has no middle column, and rounding to one of them puts the groove
 * visibly off-centre down the whole length — which at 32px is the single most
 * obvious way to make a symmetrical object look hand-placed by a machine. */
function centreCols(a, b) {
  const inner = b - a - 1;
  if (inner % 2 === 0) { const c = a + inner / 2; return [c, c + 1]; }
  return [a + (inner + 1) / 2, a + (inner + 1) / 2];
}

function forgeFuller(cells, fam, def, tier) {
  if (!def.fuller) return;
  const rows = fullerRows(fam, def.fuller);
  for (const y of rows) {
    for (const [a, b] of massRuns(cells, y, fam)) {
    if (b - a < 4) continue;
    const [c0, c1] = centreCols(a, b);
    const cut = (x, ch) => {
      if (x <= a || x >= b) return;
      const g = GROOVE[cells[y][x]];
      if (g) cells[y][x] = ch === null ? g : ch;
    };
    /* From rung 6 a rune is cut INTO the groove rather than painted beside it.
     * Every third row, so the inscription reads as intermittent marks rather
     * than as a light-up strip. */
    cut(c0, (tier >= 6 && y % 3 === 0) ? 'r' : null);
    if (c1 === c0) { continue; }
    /* At full depth the groove has two walls: the far one catches the light
     * the near one loses, which is what makes it read as a cut rather than as
     * a pencil line. Below that it is simply a wide groove. */
    if (def.fuller >= 3 && b - a >= 6) cut(c1, 'L');
    else cut(c1, null);
    }
  }
}

/* ---------------- 3. teeth ----------------
 * The crossguard, and the brief's own example. Five steps: it widens, it
 * widens again and drops lugs, the quillons turn up, they become horns, and
 * finally the underside grows actual teeth.
 *
 * A family with no guard — a staff, a bow — falls back to its widest row,
 * which is the same move the rarity ladder makes for an unauthored shape. It
 * is a floor, not a ceiling: a staff's head prongs out instead of a guard
 * growing quillons, and that is the right answer for a staff anyway.
 */
/* Runs a fitting may be grown on. A bowstring is one pixel wide and it is a
 * run like any other, so without this the teeth pass grows quillons on the
 * string — which is both funny and exactly the sort of thing a parametric
 * pass does when nobody measures it. */
function fittable(cells, y) { return runsAt(cells, y).filter(([a, b]) => b - a >= 2); }

function extendRuns(cells, y, fill, limit = 22) {
  if (y < 0 || y >= FN) return;
  for (const [a, b] of fittable(cells, y)) {
    if (b - a + 1 >= limit) continue;
    if (a >= 1 && (cells[y][a - 1] === '.' || cells[y][a - 1] === ' ')) {
      cells[y][a] = fill; cells[y][a - 1] = 'o';
    }
    if (b <= FN - 2 && (cells[y][b + 1] === '.' || cells[y][b + 1] === ' ')) {
      cells[y][b] = fill; cells[y][b + 1] = 'o';
    }
  }
}

function forgeTeeth(cells, fam, level, silhouette) {
  if (!level) return;
  const gy = fam.guard != null ? fam.guard : widestRowIn(cells, fam.blade);
  if (gy < 0 || gy >= FN) return;
  const fill = fam.guard != null ? 'g' : (cells[gy][(runsAt(cells, gy)[0] || [0, 0])[0] + 1] || 'g');
  /* Two pixels each side at the first step, not one. One pixel is four pixels
   * of silhouette across the whole object, which measures as a change and does
   * not read as one — and rung 2 is the rung a player buys to find out whether
   * upgrading is worth doing at all. */
  /* Every family says how big its fitting is allowed to get. A lance is meant
   * to have a vamplate the width of the box; a bow riser that grows to the
   * same width has stopped being a riser and become a plank across the bow. */
  const cap = (fam.teethWidth || 22)
    + (silhouette === 'broad' ? 4 : silhouette === 'narrow' ? -4 : 0);
  extendRuns(cells, gy, fill, cap);
  extendRuns(cells, gy, fill, cap);
  /* The second guard row goes with it where a family has one, so the fitting
   * reads as thicker rather than as a wider plate on top of the same block. */
  if (fam.guard2 != null) extendRuns(cells, fam.guard2, fill, cap);
  if (level >= 2) {
    /* Two more, not one. Rung 4 is the rung where the guard stops being a
     * fitting and starts being a guard, and one pixel a side measured as a
     * change without reading as one — which is the same mistake rung 2 made
     * before it was counted. */
    extendRuns(cells, gy, fill, cap);
    extendRuns(cells, gy, fill, cap);
    for (const [a, b] of fittable(cells, gy)) { soft(cells, gy + 1, a, 'o'); soft(cells, gy + 1, b, 'o'); }
  }
  if (level >= 3) {
    for (const [a, b] of fittable(cells, gy)) {
      soft(cells, gy - 1, a, 'o'); soft(cells, gy - 2, a, 'o');
      soft(cells, gy - 1, b, 'o'); soft(cells, gy - 2, b, 'o');
    }
  }
  if (level >= 4) {
    /* The quillon tip forks. Deliberately NOT a taller spike: the authored
     * wings at the top rungs climb from exactly here, and two passes both
     * growing upward out of the same four pixels is how a swept guard turns
     * into a handful of loose dots. */
    for (const [a, b] of fittable(cells, gy)) {
      soft(cells, gy - 1, a - 1, 'o'); soft(cells, gy + 1, a - 1, 'o');
      soft(cells, gy - 1, b + 1, 'o'); soft(cells, gy + 1, b + 1, 'o');
    }
  }
  if (level >= 5) {
    /* Teeth hang off the underside — and only where there is something
     * directly above for them to hang off. A tooth under a gap is not a tooth,
     * it is one loose pixel, and one loose pixel beside a sprite is the single
     * most common way procedural art gives itself away. */
    for (const [a, b] of fittable(cells, gy)) {
      for (let x = a; x <= b; x += 2) {
        const above = cells[gy + 1] && cells[gy + 1][x];
        if (!above || above === '.' || above === ' ') continue;
        soft(cells, gy + 2, x, 'o');
      }
    }
  }
}

/* ---------------- 4. inlay ----------------
 * Trim run down the blade beside the fuller. Dashed, then close, then
 * continuous with set pips — the ladder a real inlay actually climbs, and the
 * reason rung 5 is called Inlaid.
 */
function forgeInlay(cells, fam, level) {
  if (!level) return;
  /* Trim laid into a blade is inlay; trim laid down a bow limb is a sticker,
   * and trim laid inside a crystal core is a scratch. The families that have
   * no worked flat to inlay escalate at the crest and the setting instead. */
  if (fam.kind === 'bow' || fam.kind === 'focus') return;
  const [y0, y1] = fam.blade;
  const stride = level >= 3 ? 1 : level >= 2 ? 2 : 4;
  for (let y = y0 + 3; y <= y1 - 1; y += stride) {
    for (const [a, b] of massRuns(cells, y, fam)) {
    if (b - a < 5) continue;
    const [c0, c1] = centreCols(a, b);
    const put = (x, ch) => {
      if (x <= a || x >= b) return;
      const c = cells[y][x];
      if (c === '.' || c === 'o' || c === 'O' || c === 'r') return;
      cells[y][x] = ch;
    };
    put(c0 - 1, 'g'); put(c1 + 1, 'g');
    if (level >= 3 && y % 5 === 0) { put(c0 - 1, 'm'); put(c1 + 1, 'm'); }
    }
  }
}

/* ---------------- 5. the stone ----------------
 * A cap, then a stone, then a faceted stone that hangs below the pommel, then
 * one held in claws. Placed from the family table rather than derived, because
 * a stone placed by an algorithm always lands in the wrong hole.
 */
function forgeStone(cells, seat, level) {
  if (!level || !seat) return;
  const { y, x } = seat;
  if (!inBox(y, x) || x + 5 >= FN) return;
  if (level >= 1) {
    /* Rung 2 fits a proper cap: the counterweight squares up to the full width
     * of the setting the smith is eventually going to put a stone in. On a
     * family whose pommel is already that wide this does nothing and the rung
     * is carried by the guard instead — which is why every family also
     * declares a second fitting row. */
    for (let k = 1; k <= 4; k++) soft(cells, y, x + k, 'g');
    const edge = (cx) => {
      if (!inBox(y, cx)) return;
      const c = cells[y][cx];
      if (c === '.' || c === ' ') cells[y][cx] = 'o';
    };
    edge(x); edge(x + 5);
  }
  if (level >= 2) {
    for (let k = 1; k <= 4; k++) hard(cells, y, x + k, k === 2 || k === 3 ? 'M' : 'm');
  }
  if (level >= 3 && y + 2 < FN) {
    hard(cells, y, x, 'o'); hard(cells, y, x + 5, 'o');
    hard(cells, y + 1, x, 'o'); hard(cells, y + 1, x + 5, 'o');
    for (let k = 1; k <= 4; k++) hard(cells, y + 1, x + k, k === 2 || k === 3 ? 'M' : 'm');
    /* The bottom edge closes the stone, but only across space it can have:
     * this seat may be halfway up a bow riser rather than hanging in air. */
    hard(cells, y + 2, x, 'o'); hard(cells, y + 2, x + 5, 'o');
    for (let k = 1; k <= 4; k++) soft(cells, y + 2, x + k, 'o');
  }
  if (level >= 4) {
    soft(cells, y - 1, x + 1, 'o'); soft(cells, y - 1, x + 2, 'g');
    soft(cells, y - 1, x + 3, 'g'); soft(cells, y - 1, x + 4, 'o');
    soft(cells, y, x - 1, 'o'); soft(cells, y, x + 6, 'o');
    soft(cells, y + 1, x - 1, 'o'); soft(cells, y + 1, x + 6, 'o');
    soft(cells, y + 3, x + 2, 'o'); soft(cells, y + 3, x + 3, 'o');
    /* Once claws wrap the setting from outside, the setting's own edge is no
     * longer an edge — and leaving it as outline puts two near-black columns
     * side by side, which at 32px reads as a crack down the middle of the
     * mount rather than as metal holding a stone. */
    for (const ry of [y, y + 1]) {
      for (const cx of [x, x + 5]) {
        if (inBox(ry, cx) && (cells[ry][cx] === 'o' || cells[ry][cx] === 'O')) cells[ry][cx] = 'g';
      }
    }
  }
}

/* ---------------- 6. the crest ----------------
 * Where a weapon grows a crown. Two directions, because half these families
 * crown at the head and half crown at the pommel, and a spike above the point
 * of a sword is not a crest, it is a second sword.
 */
function forgeCrest(cells, seat, level) {
  if (!level || !seat) return;
  const { y, x, dir } = seat;
  if (dir === 'pommel') {
    /* The pommel swells upward into the grip: the rows above it widen to the
     * setting's own width, then flare past it. */
    for (let k = 1; k <= Math.min(level, 4); k++) {
      const ry = y - k;
      if (ry < 0) break;
      if (k <= 2 || level >= 3) { hard(cells, ry, x, 'o'); hard(cells, ry, x + 5, 'o'); }
      /* The grip's own edge is now INSIDE the flare, so it stops being an edge.
       * Leaving it as outline puts two near-black columns side by side down the
       * middle of the fitting, which reads as a crack rather than as a swell. */
      for (let i = 1; i <= 4; i++) {
        const c = cells[ry][x + i];
        if (c === '.' || c === ' ' || c === 'o' || c === 'O') cells[ry][x + i] = 'g';
      }
      if (level >= 3 && k <= 2) { soft(cells, ry, x - 1, 'o'); soft(cells, ry, x + 6, 'o'); }
    }
    return;
  }
  /* Nearest run rather than the run containing x: by the time the crest is
   * placed the crown may have been broadened and sheared out from under the
   * authored column, and a crest that silently declines to appear is worse
   * than one that lands a pixel off. */
  let run = null, bestD = Infinity;
  for (const r of runsAt(cells, y)) {
    const d = Math.abs(((r[0] + r[1]) / 2) - x);
    if (d < bestD) { bestD = d; run = r; }
  }
  if (!run) return;
  const [a, b] = run;
  const c0 = (a + b) >> 1, c1 = (a + b + 1) >> 1;
  soft(cells, y - 1, c0, 'o'); soft(cells, y - 1, c1, 'o');
  if (level >= 2) { soft(cells, y - 1, a, 'o'); soft(cells, y - 1, b, 'o'); }
  if (level >= 3) {
    soft(cells, y - 2, c0, 'o'); soft(cells, y - 2, c1, 'o');
    soft(cells, y - 1, a - 1, 'o'); soft(cells, y - 1, b + 1, 'o');
    for (let x2 = a; x2 <= b; x2++) soft(cells, y - 1, x2, 'g');
  }
  if (level >= 4) {
    soft(cells, y - 3, c0, 'o'); soft(cells, y - 3, c1, 'o');
    soft(cells, y - 2, a, 'o'); soft(cells, y - 2, b, 'o');
    soft(cells, y - 2, a - 1, 'o'); soft(cells, y - 2, b + 1, 'o');
  }
}

/* ---------------- 7. the curve ----------------
 * The brief's last silhouette move, and the strongest one: at the top rungs
 * the blade stops being straight.
 *
 * Done as a per-row integer shear, which is how a pixel artist draws a curved
 * blade — the stair-step IS the curve at this resolution, and anything smoother
 * would need antialiasing the rest of the game does not have. The profile is
 * zero at the shoulder and maximum at the point, so the hilt stays where the
 * hand is and only the steel sweeps. Families whose geometry cannot take it
 * say so in their table: shearing a crossed pair opens the X, and shearing an
 * axe head detaches it from the haft.
 */
function forgeCurve(cells, fam, amountIn) {
  if (!amountIn || !fam.curve) return;
  const [y0, y1] = fam.blade;
  const span = Math.max(1, y1 - y0);
  /* Scaled to the length being bent. Two pixels of sweep across twenty rows of
   * longsword is a curve; the same two pixels across a seven-row spear head is
   * a bent spear, and a bent weapon reads as a broken one. */
  const amount = Math.min(amountIn, Math.max(1, Math.round((span + 1) / 8)));
  for (let y = y0; y <= y1; y++) {
    /* 1.25 rather than a straight ramp: the sweep has to be zero for several
     * rows above the guard or the hilt visibly detaches from the hand, and it
     * has to reach its full offset well before the point or the "curve" is two
     * pixels at the tip and nothing anywhere else. */
    const t = (y1 - y) / span;
    const dx = Math.round(amount * Math.pow(t, 1.25));
    if (!dx) continue;
    const src = cells[y].slice();
    let clipped = false;
    for (let x = 0; x < FN; x++) {
      if (src[x] === '.' || src[x] === ' ') continue;
      if (x + dx >= FN) { clipped = true; break; }
    }
    if (clipped) continue;
    for (let x = 0; x < FN; x++) cells[y][x] = '.';
    for (let x = 0; x < FN; x++) {
      if (src[x] === '.' || src[x] === ' ') continue;
      cells[y][x + dx] = src[x];
    }
  }
}


/* ================================================================
 * MOTIFS AND AURAS
 * ================================================================
 * gauntlet/legendaries.py asked for twelve motifs and six auras; forge.py adds
 * six and six more and ships the two MERGED tables as ART_MOTIFS and
 * ART_AURAS. This is the one implementation of both, and forgeVocabulary()
 * publishes the key list so a test over there can prove nothing has drifted.
 *
 * The two passes sit in different places for a reason the art brief is explicit
 * about, and getting it wrong is visible:
 *
 *   A MOTIF is cut INTO the object, between ornament and applyRim, so the rim
 *   pass lights the mark the same way it lights everything else. A motif added
 *   after the rim is a sticker.
 *
 *   An AURA is drawn OUTSIDE the silhouette, after animate, because it is not
 *   part of the object — it is what the object is doing to the air around it.
 *   An aura drawn before the rim gets shaded like metal and stops reading as
 *   light.
 *
 * Every motif is deterministic in (tier, seed). Every aura is deterministic in
 * (frame, seed). Neither ever calls Math.random, and both are evaluated once
 * per cached frame and never in a draw path.
 */

/* The object's own extent, which is what every mark below is placed against.
 * Placing marks against the 32-box instead would put a tally on a dagger in
 * the air beside it. */
function bodyBox(cells) {
  let x0 = FN, y0 = FN, x1 = -1, y1 = -1;
  for (let y = 0; y < cells.length; y++) {
    for (let x = 0; x < FN; x++) {
      const c = cells[y][x];
      if (c === '.' || c === ' ') continue;
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  return x1 < 0 ? null : { x0, y0, x1, y1 };
}

/* Glyphs a mark may be cut into: body, trim and stone, never outline and never
 * empty space. A motif that overwrites the outline punches a hole in the
 * silhouette, which is the one thing this whole section is built to protect. */
const MARKABLE = new Set(['B', 'b', 'H', 'L', 'd', 'D', 's', 't', 'u', 'g', 'G', 'y', 'm', 'M', 'n', 'w', 'c', 'C', 'v']);

function markable(cells, y, x) {
  return inBox(y, x) && MARKABLE.has(cells[y][x]);
}
function mark(cells, y, x, ch) {
  if (markable(cells, y, x)) cells[y][x] = ch;
}
/* Cut a pixel OUT of the object — used by keyward and by the unlabelled aura.
 * Interior only: taking an outline pixel severs the shape. */
function unmark(cells, y, x) {
  if (!inBox(y, x)) return;
  const c = cells[y][x];
  if (c === 'o' || c === 'O' || c === '.' || c === ' ') return;
  cells[y][x] = '.';
}

/* The column with the most body in it, which is where a mark down the long
 * axis belongs. Derived rather than taken from fam.axis so a sheared blade
 * carries its marks with it. */
function densestColumn(cells, box) {
  let best = box.x0, bestN = -1;
  for (let x = box.x0; x <= box.x1; x++) {
    let n = 0;
    for (let y = box.y0; y <= box.y1; y++) if (markable(cells, y, x)) n++;
    if (n > bestN) { bestN = n; best = x; }
  }
  return best;
}

/* The widest fully-marked row, for the motifs that want to sit across the
 * object rather than down it. */
function widestMarkRow(cells, box) {
  let best = box.y0, bestN = -1;
  for (let y = box.y0; y <= box.y1; y++) {
    let n = 0;
    for (let x = box.x0; x <= box.x1; x++) if (markable(cells, y, x)) n++;
    if (n > bestN) { bestN = n; best = y; }
  }
  return best;
}

function markSpan(cells, y, box) {
  let a = -1, b = -1;
  for (let x = box.x0; x <= box.x1; x++) {
    if (!markable(cells, y, x)) continue;
    if (a < 0) a = x;
    b = x;
  }
  return a < 0 ? null : [a, b];
}

/* ---------------- the eighteen motifs ----------------
 * Each one is the sentence gauntlet/forge.py's ART_MOTIFS writes about it,
 * turned into pixels. Where that text says "one pixel per rung" or "along its
 * long axis", the code does exactly that and not something near it — the point
 * of shipping the descriptions with the data was that they be drawable.
 */
const FORGE_MOTIFS = {
  /* four upright scratches and a fifth struck through them */
  tally(cells, box, c) {
    const cx = densestColumn(cells, box);
    const top = box.y0 + Math.round((box.y1 - box.y0) * 0.35);
    const len = Math.max(3, Math.round((box.y1 - box.y0) * 0.22));
    for (let i = 0; i < 4; i++) {
      const x = cx - 3 + i * 2;
      for (let y = top; y < top + len; y++) mark(cells, y, x, 'g');
    }
    for (let i = 0; i < 5; i++) mark(cells, top + Math.floor(len / 2) + (i > 2 ? 1 : 0), cx - 4 + i * 2, 'G');
  },

  /* a single-pixel spiral wound inward from the widest point, one arm per
   * frame at animated tiers */
  spiral(cells, box, c) {
    const y = widestMarkRow(cells, box);
    const span = markSpan(cells, y, box);
    if (!span) return;
    const cx = (span[0] + span[1]) >> 1;
    const arms = c.animated ? 1 + (c.frame % 6) : 6;
    let x = span[0], yy = y, dx = 1, dy = 0, run = Math.min(5, span[1] - span[0]);
    for (let arm = 0; arm < arms && run > 0; arm++) {
      for (let k = 0; k < run; k++) { mark(cells, yy, x, 'g'); x += dx; yy += dy; }
      const t = dx; dx = -dy; dy = t;
      if (arm % 2 === 1) run -= 1;
    }
    mark(cells, y, cx, 'G');
  },

  /* two interlocked links where the body meets its haft or band */
  chain(cells, box, c) {
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.62);
    const span = markSpan(cells, y, box);
    if (!span) return;
    const cx = (span[0] + span[1]) >> 1;
    for (const [ox, oy] of [[-2, 0], [1, 1]]) {
      mark(cells, y + oy, cx + ox, 'g'); mark(cells, y + oy, cx + ox + 1, 'g');
      mark(cells, y + oy + 1, cx + ox, 'g'); mark(cells, y + oy + 1, cx + ox + 1, 'g');
      mark(cells, y + oy, cx + ox, 'y');
    }
  },

  /* a palm, fingers spread, filling the body */
  open_hand(cells, box, c) {
    const cx = densestColumn(cells, box);
    const cy = Math.round(box.y0 + (box.y1 - box.y0) * 0.45);
    for (let x = cx - 1; x <= cx + 1; x++) for (let y = cy; y <= cy + 2; y++) mark(cells, y, x, 'g');
    for (const [dx, dy] of [[-3, -1], [-2, -2], [0, -3], [2, -2], [3, 0]]) {
      mark(cells, cy + dy, cx + dx, 'g');
      mark(cells, cy + dy + 1, cx + dx, 'y');
    }
  },

  /* a lidless circle with a single dark pixel at its centre, set high */
  eye(cells, box, c) {
    const cy = box.y0 + Math.max(2, Math.round((box.y1 - box.y0) * 0.22));
    const span = markSpan(cells, cy, box);
    if (!span) return;
    const cx = (span[0] + span[1]) >> 1;
    for (const [dx, dy] of [[-1, -1], [0, -1], [1, -1], [-2, 0], [2, 0], [-1, 1], [0, 1], [1, 1]]) {
      mark(cells, cy + dy, cx + dx, 'g');
    }
    mark(cells, cy, cx, 'D');
  },

  /* a branching hairline crack from one edge */
  fracture(cells, box, c) {
    const rand = rng(c.seed ^ 0x1d3b);
    let x = box.x0 + 1 + Math.floor(rand() * 2);
    let y = Math.round(box.y0 + (box.y1 - box.y0) * 0.3);
    const steps = Math.max(4, Math.round((box.y1 - box.y0) * 0.45));
    for (let i = 0; i < steps; i++) {
      mark(cells, y, x, 'D');
      y += 1;
      if (rand() > 0.55) x += rand() > 0.5 ? 1 : -1;
      if (i === Math.floor(steps / 2)) {
        let bx = x + 1, by = y;
        for (let k = 0; k < 3; k++) { mark(cells, by, bx, 'D'); bx += 1; by += 1; }
      }
    }
  },

  /* a welded join across the body, brighter than the metal, corner to corner */
  seam(cells, box, c) {
    const w = box.x1 - box.x0, h = box.y1 - box.y0;
    const n = Math.max(w, h);
    for (let i = 0; i <= n; i++) {
      const x = box.x0 + Math.round((i / n) * w);
      const y = box.y0 + Math.round((i / n) * h);
      mark(cells, y, x, 'W');
      mark(cells, y, x + 1, 'G');
    }
  },

  /* one pixel of accent at each extreme end of the body and nothing between */
  boundary(cells, box, c) {
    for (const y of [box.y0, box.y1]) {
      const span = markSpan(cells, y, box);
      if (!span) continue;
      const cx = (span[0] + span[1]) >> 1;
      mark(cells, y, cx, 'r');
      mark(cells, y, cx + ((span[1] - span[0]) > 2 ? 1 : 0), 'r');
    }
  },

  /* three barbs raked backward along one edge */
  thorn(cells, box, c) {
    const step = Math.max(2, Math.round((box.y1 - box.y0) / 5));
    for (let i = 0; i < 3; i++) {
      const y = box.y0 + Math.round((box.y1 - box.y0) * 0.3) + i * step;
      const span = markSpan(cells, y, box);
      if (!span) continue;
      soft(cells, y, span[0] - 1, 'o');
      soft(cells, y + 1, span[0] - 1, 'o');
      mark(cells, y, span[0], 'g');
    }
  },

  /* a band of accent across the lower third, lightening what is above it and
   * leaving what is below it dark */
  dawn_line(cells, box, c) {
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.66);
    for (let x = box.x0; x <= box.x1; x++) mark(cells, y, x, 'g');
    for (let yy = box.y0; yy < y; yy++) {
      for (let x = box.x0; x <= box.x1; x++) {
        const ch = cells[yy][x];
        if (ch === 'B' || ch === 'd') cells[yy][x] = 'L';
      }
    }
    for (let yy = y + 1; yy <= box.y1; yy++) {
      for (let x = box.x0; x <= box.x1; x++) {
        const ch = cells[yy][x];
        if (ch === 'B' || ch === 'L' || ch === 'H') cells[yy][x] = 'd';
      }
    }
  },

  /* a single green pixel, off-centre, that does not move when the glint does.
   * 'i' is its own glyph precisely so the glint cannot claim it — see HARD. */
  index_dot(cells, box, c) {
    const cx = densestColumn(cells, box);
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.38);
    if (!markable(cells, y, cx + 1)) mark(cells, y, cx, 'i');
    else mark(cells, y, cx + 1, 'i');
  },

  /* three ward-teeth cut into the lower edge, unevenly spaced */
  keyward(cells, box, c) {
    const y = box.y1 - 1;
    const span = markSpan(cells, y, box);
    if (!span) return;
    for (const dx of [1, 3, 6]) {
      unmark(cells, y, span[0] + dx);
      unmark(cells, y - 1, span[0] + dx);
    }
  },

  /* two opposed arms closing on the body, the gap narrowing one pixel a rung */
  caliper_jaw(cells, box, c) {
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.45);
    const span = markSpan(cells, y, box);
    if (!span) return;
    const cx = (span[0] + span[1]) >> 1;
    const gap = Math.max(1, 6 - Math.floor(c.tier / 2));
    for (const dir of [-1, 1]) {
      const from = cx + dir * Math.ceil(gap / 2);
      for (let k = 0; k < 3; k++) mark(cells, y, from + dir * k, 'g');
      mark(cells, y - 1, from, 'y');
      mark(cells, y + 1, from, 'y');
    }
  },

  /* evenly spaced ticks along one edge, every fifth one a pixel longer */
  rule_marks(cells, box, c) {
    let i = 0;
    for (let y = box.y0 + 2; y <= box.y1 - 2; y += 2, i++) {
      const span = markSpan(cells, y, box);
      if (!span) continue;
      mark(cells, y, span[0], 'g');
      if (i % 5 === 4) mark(cells, y, span[0] + 1, 'g');
    }
  },

  /* the temper line: a hard boundary where the metal changes shade, drawn
   * rather than shaded */
  quench_line(cells, box, c) {
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.45);
    for (let x = box.x0; x <= box.x1; x++) {
      if (markable(cells, y, x)) cells[y][x] = 'G';
      for (let yy = y + 1; yy <= box.y1; yy++) {
        const ch = cells[yy][x];
        if (ch === 'B' || ch === 'L' || ch === 'H') cells[yy][x] = 'd';
      }
    }
  },

  /* the smith's stamp: three struck pips in a triangle, slightly off square */
  forge_mark(cells, box, c) {
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.72);
    const span = markSpan(cells, y, box);
    if (!span) return;
    const cx = (span[0] + span[1]) >> 1;
    mark(cells, y, cx, 'd');
    mark(cells, y + 1, cx - 2, 'd');
    mark(cells, y + 1, cx + 1, 'd');
  },

  /* one closed ring of accent, and a second behind it drawn only where the
   * first does not cover it */
  link(cells, box, c) {
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.4);
    const span = markSpan(cells, y, box);
    if (!span) return;
    const cx = (span[0] + span[1]) >> 1;
    const ring = (ox, oy, ch) => {
      for (const [dx, dy] of [[-1, -1], [0, -1], [-1, 1], [0, 1], [-2, 0], [1, 0]]) {
        const py = y + oy + dy, px = cx + ox + dx;
        if (ch === 'y' && cells[py] && (cells[py][px] === 'g')) continue;
        mark(cells, py, px, ch);
      }
    };
    ring(2, 2, 'y');
    ring(0, 0, 'g');
  },

  /* a single-pixel fault running WITH the long axis, and it does not branch */
  hairline(cells, box, c) {
    const cx = densestColumn(cells, box) + 1;
    /* Short. A fault that runs the whole length of an object stops reading as
     * a fault and starts reading as a seam, which is a different motif and is
     * three entries up this table. */
    const from = box.y0 + Math.round((box.y1 - box.y0) * 0.28);
    const to = box.y0 + Math.round((box.y1 - box.y0) * 0.58);
    for (let y = from; y <= to; y++) mark(cells, y, cx, 'D');
  },
};

export const FORGE_MOTIF_KEYS = Object.keys(FORGE_MOTIFS);

/* ---------------- the twelve auras ----------------
 * Drawn outside the silhouette, after the light has moved. `x` and `X` are the
 * accent and its lit state; neither is in HARD, so the travelling specular
 * cannot claim an aura pixel and make it look like part of the metal.
 */
const FORGE_AURAS = {
  /* sparks detach from the lower edge and fall two pixels before fading */
  emberfall(cells, box, c) {
    const rand = rng(c.seed ^ 0x3ab1);
    const phase = c.frame % 4;
    for (let i = 0; i < 4; i++) {
      const x = box.x0 + Math.floor(rand() * Math.max(1, box.x1 - box.x0 + 1));
      let y = box.y1;
      while (y >= 0 && cells[y] && cells[y][x] === '.') y--;
      for (let s = 0; s < 3; s++) {
        const fall = ((phase + i) % 4);
        if (fall > 2) continue;
        soft(cells, y + 2 + fall, x, fall === 0 ? 'X' : 'x');
        break;
      }
    }
  },

  /* a one-pixel halo that brightens and dims WITHOUT travelling */
  coldlight(cells, box, c) {
    const lit = (c.frame % 4) < 2;
    for (let y = box.y0 - 1; y <= box.y1 + 1; y++) {
      for (let x = box.x0 - 1; x <= box.x1 + 1; x++) {
        if (!inBox(y, x) || cells[y][x] !== '.') continue;
        /* Sparse on purpose. A pixel at every point on the outline is not a
         * halo, it is a second outline in a brighter colour, and at 32px it
         * fills the space around the object with noise. */
        if (((x * 3 + y * 5) % 7) !== 0) continue;
        let touching = false;
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const c2 = cells[y + dy] && cells[y + dy][x + dx];
          if (c2 && c2 !== '.' && c2 !== ' ') touching = true;
        }
        if (touching) cells[y][x] = lit ? 'X' : 'x';
      }
    }
  },

  /* pixels of the silhouette go missing and return; never more than three at
   * once, never the same three twice */
  voidbite(cells, box, c) {
    const rand = rng((c.seed ^ 0x77d9) + c.frame * 2654435761);
    let bitten = 0, tries = 0;
    while (bitten < 3 && tries++ < 60) {
      const x = box.x0 + Math.floor(rand() * (box.x1 - box.x0 + 1));
      const y = box.y0 + Math.floor(rand() * (box.y1 - box.y0 + 1));
      const ch = inBox(y, x) ? cells[y][x] : '.';
      if (ch === '.' || ch === ' ' || ch === 'o' || ch === 'O') continue;
      cells[y][x] = '.';
      bitten++;
    }
  },

  /* accent wicks down the blade and off the point, one pixel per frame */
  slowbleed(cells, box, c) {
    const cx = densestColumn(cells, box);
    const y = box.y1 + 1 + (c.frame % Math.max(1, FN - box.y1 - 2));
    soft(cells, y, cx, 'X');
    soft(cells, y + 1, cx, 'x');
  },

  /* no animation at all, at a rung that normally animates. forgeFrameCount()
   * pins the frame; there is nothing left for this to draw, and that is the
   * entire content of it. */
  stillness() {},

  /* a second, offset shadow that does not match the room's light */
  handshadow(cells, box, c) {
    const src = cells.map(r => r.slice());
    for (let y = box.y0; y <= box.y1; y++) {
      for (let x = box.x0; x <= box.x1; x++) {
        const ch = src[y][x];
        if (ch === '.' || ch === ' ') continue;
        soft(cells, y + 1, x + 2, 'x');
      }
    }
  },

  /* a two-pixel plume off the upper edge that rises, thins and vanishes. Its
   * period is six against the glint's twelve, so the two coincide once a cycle
   * instead of on every plume — which is as close to the brief's "never sync"
   * as a cached frame table can honestly get. */
  quenchsteam(cells, box, c) {
    const cx = densestColumn(cells, box);
    const t = c.frame % 6;
    const top = box.y0 - 1;
    if (t >= 5) return;
    soft(cells, top - t, cx, t < 2 ? 'X' : 'x');
    if (t < 3) soft(cells, top - t, cx + 1, 'x');
    if (t >= 1 && t < 4) soft(cells, top - t + 1, cx, 'x');
  },

  /* the lowest third of the body cycles one step up its ramp and back */
  heatglow(cells, box, c) {
    const up = (c.frame % 4) < 2;
    if (!up) return;
    const from = Math.round(box.y0 + (box.y1 - box.y0) * 0.66);
    const step = { D: 'd', d: 'B', B: 'L', L: 'H', u: 's', s: 't', y: 'g', g: 'G' };
    for (let y = from; y <= box.y1; y++) {
      for (let x = box.x0; x <= box.x1; x++) {
        const n = step[cells[y][x]];
        if (n) cells[y][x] = n;
      }
    }
  },

  /* a single accent pixel travelling the long axis end to end, one a frame —
   * the only aura that reads as an instrument rather than as power */
  measure(cells, box, c) {
    const h = box.y1 - box.y0;
    const y = box.y0 + (c.frame % Math.max(1, h + 1));
    soft(cells, y, box.x1 + 1, 'X');
    soft(cells, y, box.x0 - 1, 'x');
  },

  /* one accent pixel lights per frame along a row of marks until the row is
   * full, then all of them go dark at once */
  tallylight(cells, box, c) {
    const n = 6;
    const lit = c.frame % (n + 2);
    if (lit > n) return;
    const y = box.y1 + 1;
    for (let i = 0; i < lit; i++) soft(cells, y, box.x0 + i * 2, i === lit - 1 ? 'X' : 'x');
  },

  /* three accent pixels outside the silhouette, arranged as a bent path, that
   * swap which of them is brightest */
  roadglow(cells, box, c) {
    const pts = [[box.y1 + 1, box.x0 - 2], [box.y1 - 1, box.x0 - 3], [box.y1 - 4, box.x0 - 3]];
    const hot = Math.floor(c.frame / 4) % 3;
    pts.forEach(([y, x], i) => soft(cells, y, x, i === hot ? 'X' : 'x'));
  },

  /* the aura draws, and then the row that would carry a maker's mark is left
   * empty. Interior only — taking the outline would sever the object — so what
   * is left is a punched slot rather than a break, which is the difference
   * between a statement and damage. */
  unlabelled(cells, box, c) {
    FORGE_AURAS.coldlight(cells, box, { ...c, frame: 0 });
    const y = Math.round(box.y0 + (box.y1 - box.y0) * 0.78);
    const span = markSpan(cells, y, box);
    if (!span) return;
    for (let x = span[0]; x <= span[1]; x++) unmark(cells, y, x);
  },
};

export const FORGE_AURA_KEYS = Object.keys(FORGE_AURAS);

/* Cut a motif into a grid. Exported because gauntlet/legendaries.py asked for
 * the same vocabulary on artifacts that are not forged, and a second
 * implementation of eighteen marks is eighteen chances to disagree. */
export function applyMotif(grid, motifKey, opts = {}) {
  const fn = FORGE_MOTIFS[motifKey];
  if (!fn) return grid;
  const cells = toCells(grid);
  const box = bodyBox(cells);
  if (!box) return grid;
  fn(cells, box, {
    tier: clampTier(opts.tier || 1), seed: opts.seed || 1,
    frame: opts.frame || 0, animated: !!opts.animated,
  });
  return toRows(cells);
}

export function applyAura(grid, auraKey, opts = {}) {
  const fn = FORGE_AURAS[auraKey];
  if (!fn) return grid;
  const cells = toCells(grid);
  const box = bodyBox(cells);
  if (!box) return grid;
  fn(cells, box, {
    tier: clampTier(opts.tier || 1), seed: opts.seed || 1,
    frame: opts.frame || 0,
  });
  return toRows(cells);
}

/* ---------------- the metal, as a palette ----------------
 * Built out of palette.js ramps and nothing else, which is the whole of rule B:
 * a Quarterturn Bronze blade is the same five bronzes as a bronze pauldron,
 * so the two belong in one frame. The rung contributes exactly one thing to
 * colour — POLISH — and it is a subtraction: at the bottom of the ladder the
 * specular step is withheld and the metal never catches the light, which is
 * what raw stock looks like and what makes rung 5 landing feel earned.
 *
 * Everything then goes through fitPalette(), the same fifteen-colour merge the
 * rarity ladder uses. Eight materials' worth of ramps is nineteen colours and
 * the budget is fifteen; merging the two nearest until it fits is what an
 * artist does when they run out of palette entries, and it is measured off the
 * RASTER in scripts/verify/forge.mjs rather than trusted here.
 */
const forgePaletteCache = new Map();

/* lootart's own MATERIAL vocabulary — the nine names gauntlet/forge.py's art
 * dict is allowed to send — mapped onto the shared five-step ramps. One line
 * each, and the mapping is the whole of rule B for the callers that send a
 * material rather than a metal. */
const MATERIAL_RAMP = {
  steel: 'steel', iron: 'iron', gold: 'goldleaf', cloth: 'cloth',
  leather: 'leather', wood: 'wood', bone: 'bone', paper: 'bone', glass: 'frost',
};

/* The one colour in the file that is not derived from anything: the index
 * dot's green. It is a SIGNAL rather than a material — the motif's whole
 * content is "this pixel means something and it never moves" — so it does not
 * belong to the metal and does not shift with it. It is also the colour
 * items.py already uses for Uncommon, so it is not a new green in the game. */
const INDEX_GREEN = '#8fd07a';

function buildForgePalette(metalKey, tier, material, accent) {
  const m = FORGE_METALS[metalKey] || FORGE_METALS.fieldiron;
  const def = forgeRung(tier);
  /* An explicit metal wins, because a metal is a THING the player carried back
   * from somewhere; a material is the art dict's shorthand for how finished
   * the object is. When only the material is named — which is what
   * forge.art_at() sends — it picks the ramp. */
  const bodyRamp = metalKey ? m.ramp : (MATERIAL_RAMP[material] || m.ramp);
  const body = RAMPS[bodyRamp] || RAMPS.iron;
  /* The accent is given per rung so nine rungs do not become one object in
   * nine golds. Derived through palette.js rather than used raw, so the
   * fitting has a shadow and a specular and reads as metal. */
  const trim = accent ? deriveRamp(accent, 'metal', SHADE.LIGHT) : (RAMPS[m.trim] || RAMPS.bronze);
  const grip = RAMPS[m.grip] || RAMPS.leather;
  const bone = RAMPS.bone;
  /* A gem only exists once the smith has set one. Below that the gem glyphs
   * point at trim, which costs the palette nothing and leaves the merge pass
   * more room where it matters — at the top, where there is actually a stone. */
  const gemHex = m.energy || accent;
  const gem = def.stone >= 2
    ? (gemHex ? deriveRamp(gemHex, 'magic', SHADE.SPEC) : trim)
    : trim;
  const lit = def.polish >= 2;
  const spec = lit ? body[SHADE.SPEC] : body[SHADE.LIGHT];
  /* Runes exist from rung 6. Before that r/R are spare and are pointed at
   * trim, for the same reason. */
  const runeHex = tier >= 6 ? (m.energy || accent || trim[SHADE.SPEC]) : trim[SHADE.LIGHT];
  const runeLit = tier >= 6 ? mix(runeHex, '#ffffff', 0.35) : trim[SHADE.SPEC];
  return {
    /* At the top the outline stops being neutral: a nullsteel blade carries
     * its own colour right out to its edge. Two rungs only, and at 18% — any
     * more and the shared near-black that makes the whole game read as one set
     * of objects stops being shared. */
    o: tier >= 8 && m.energy ? mix(OUTLINE, m.energy, 0.18) : OUTLINE,
    O: lit ? rimFor(bodyRamp) : body[SHADE.LIGHT],
    B: body[SHADE.MID], b: body[SHADE.MID],
    H: lit ? body[SHADE.SPEC] : body[SHADE.LIGHT],
    L: body[SHADE.LIGHT], d: body[SHADE.DARK], D: body[SHADE.DEEP],
    s: grip[SHADE.MID], t: grip[SHADE.LIGHT], u: grip[SHADE.DARK],
    g: trim[SHADE.MID], G: lit ? trim[SHADE.SPEC] : trim[SHADE.LIGHT], y: trim[SHADE.DARK],
    m: gem[SHADE.MID], M: gem[SHADE.SPEC], n: gem[SHADE.DARK],
    w: bone[SHADE.LIGHT],
    W: spec,
    r: runeHex, R: runeLit,
    x: accent || runeHex, X: mix(accent || runeLit, '#ffffff', 0.3),
    i: INDEX_GREEN,
  };
}

/* `metal` may be null: that is the normal case when the caller is handing over
 * an art dict from forge.art_at(), which names a material and an accent and
 * says nothing about what the thing was forged out of. */
/* The held weapon gets a HARDER budget than the icon, and not for tidiness.
 * Fifteen colours is a per-sprite rule, and a hero with a weapon in hand is
 * two sprites composited: the character costs fourteen on its own, so a
 * weapon that spends its full fifteen puts the finished frame over. Seven is
 * what a 6x12 object can actually use — measured, not guessed — and it keeps
 * the composite at or under what the rarity ladder already costs, which is the
 * number that matters because that is the bar the game currently meets. */
const HAND_BUDGET = 7;

export function forgePalette(metal, tier, material, accent, budget) {
  const t = clampTier(tier);
  const key = `${metal ? forgeMetalKey(metal, t) : ''}:${t}:${material || ''}:${accent || ''}:${budget || ''}`;
  const hit = forgePaletteCache.get(key);
  if (hit) return hit;
  const built = fitPalette(buildForgePalette(
    metal ? forgeMetalKey(metal, t) : '', t, material, accent), budget || BUDGET);
  if (forgePaletteCache.size >= 256) forgePaletteCache.delete(forgePaletteCache.keys().next().value);
  forgePaletteCache.set(key, built);
  return built;
}

/* What a given look actually costs in colours. The harness reads this; so
 * should anyone adding a glyph. */
export function forgePaletteBudget(metal, tier, material, accent) {
  const pal = forgePalette(metal, tier, material, accent);
  const uniq = new Set(Object.values(pal).filter(Boolean));
  return { used: uniq.size, budget: BUDGET, ok: uniq.size <= BUDGET };
}

/* ---------------- motion ----------------
 * Rungs 1-4 do not move. That is a decision rather than an omission: if
 * everything drifts then nothing does, and the moment the smith hands back a
 * weapon that has started breathing has to be a moment.
 *
 *   5  a specular drifts ALONG THE EDGE, hilt to point. Not a diagonal sweep
 *      across the body — this is a blade, and light runs down a blade.
 *   6  motes lift off the metal. Fixed columns, only the height changes: a
 *      particle that appears somewhere new each frame is noise, a particle
 *      that climbs is heat.
 *   7  the inlay pulses, running along its own length rather than switching
 *      on, so the inscription reads as being run THROUGH.
 *   8  and the stone is lit from inside.
 *
 * Every frame of this is precomputed and cached. Nothing here is evaluated in
 * a draw path, and the only randomness is rng() seeded off the weapon and its
 * metal, so the same blade looks the same forever.
 */
function forgeAnimate(grid, def, frame, seed, hasAura) {
  if (def.rung < FORGE_FIRST_ANIMATED) return grid;
  const cells = toCells(grid);
  const f = ((frame % FORGE_FRAMES) + FORGE_FRAMES) % FORGE_FRAMES;
  const rand = rng((seed || 1) ^ 0x5bf03635);

  /* The lit edge: body that has empty space or outline up and to the left,
   * which is where the key light in docs/09-story-bible.md §8 actually falls.
   * Ordered bottom to top so the highlight travels hilt to point. */
  const edge = [];
  for (let y = FN - 1; y >= 0; y--) {
    for (let x = 0; x < FN; x++) {
      const ch = cells[y][x];
      if (!HARD.has(ch)) continue;
      const up = y > 0 ? cells[y - 1][x] : '.';
      const left = x > 0 ? cells[y][x - 1] : '.';
      const bare = (c) => c === '.' || c === ' ' || c === 'o' || c === 'O';
      if (bare(up) || bare(left)) edge.push([y, x]);
    }
  }
  if (edge.length) {
    /* The band runs off both ends of the list rather than wrapping, so there
     * is a frame where the blade is quiet. A highlight that never leaves is a
     * highlight the eye stops seeing. */
    /* The band is sized to the edge it is travelling, not fixed. Eight frames
     * over sixty pixels of edge with a three-pixel band puts a gap between
     * every frame and the next, and a highlight that teleports in steps reads
     * as a flicker rather than as light moving. Half a frame's travel of
     * overlap is what makes it slide.
     *
     * Frame 0 is authored to be the quiet one — the band is off the end of the
     * blade there — because that is the frame every still context uses:
     * reduced motion, an inventory list, a screenshot, the smith's preview. */
    const core = Math.max(1.6, edge.length / (FORGE_FRAMES * 2));
    const halo = core * 2.2;
    const p = -halo - 1 + (f / FORGE_FRAMES) * (edge.length + 2 * halo + 2);
    for (let i = 0; i < edge.length; i++) {
      const dist = Math.abs(i - p);
      const [y, x] = edge[i];
      if (dist <= core) cells[y][x] = 'W';
      else if (dist <= halo && cells[y][x] !== 'W') {
        const c = cells[y][x];
        if (c === 'B' || c === 'L' || c === 'd') cells[y][x] = 'H';
      }
    }
  }

  /* The built-in motes stand down when the rung carries an authored aura. Both
   * of them are things happening in the air beside the object, and two lots of
   * that at once is not twice the atmosphere, it is noise — which at 32px
   * reads as dirt on the screen rather than as heat off metal. */
  if (def.rung >= 6 && !hasAura) {
    /* Motes. Hot at rung 8, cooler below; six of them, lifting from the lower
     * half where the light source is. Embers that fall out of the top of the
     * frame contradict a low key light, so they climb and stop. */
    const hot = def.rung >= 8;
    const count = hot ? 7 : 4;
    const lift = hot ? FN - 2 : Math.floor(FN * 0.7);
    /* Motes belong to the object, so they spawn in the columns the object
     * occupies plus three either side. Scattered across the whole box they
     * stop reading as heat coming off metal and start reading as dust on the
     * screen — and a bow, which lives in the left third of its box, had embers
     * rising out of empty space on the right. */
    let bx0 = FN, bx1 = -1;
    for (let y = 0; y < FN; y++) {
      for (let x = 0; x < FN; x++) {
        if (cells[y][x] === '.' || cells[y][x] === ' ') continue;
        if (x < bx0) bx0 = x;
        if (x > bx1) bx1 = x;
      }
    }
    if (bx1 < 0) { bx0 = 2; bx1 = FN - 3; }
    const lo = Math.max(1, bx0 - 3), span = Math.max(1, Math.min(FN - 2, bx1 + 3) - lo);
    for (let i = 0; i < count; i++) {
      const col = lo + Math.floor(rand() * span);
      const phase = rand();
      const t = ((f / FORGE_FRAMES) + phase) % 1;
      const y = Math.floor((FN - 2) - t * lift);
      if (!inBox(y, col) || cells[y][col] !== '.') continue;
      cells[y][col] = ((f + i) & 1) ? 'R' : 'r';
      if (hot && inBox(y + 1, col) && cells[y + 1][col] === '.') cells[y + 1][col] = 'r';
    }
  }

  if (def.rung >= 7) {
    /* The inlay pulses along its own length: phase by row, so the light runs
     * up the inscription instead of the whole thing blinking. */
    for (let y = 0; y < FN; y++) {
      for (let x = 0; x < FN; x++) {
        if (cells[y][x] !== 'r') continue;
        if (((f + (y >> 1)) % FORGE_FRAMES) < FORGE_FRAMES / 2) cells[y][x] = 'R';
      }
    }
  }

  if (def.rung >= 8) {
    /* Subsurface: a spark descending through the facets. A gem that only
     * catches the surface highlight is a shiny pebble. */
    for (let y = 0; y < FN; y++) {
      for (let x = 0; x < FN; x++) {
        const ch = cells[y][x];
        if (ch !== 'm' && ch !== 'M' && ch !== 'n') continue;
        if (((x + y * 2 + f * 2) % 10) >= 3) continue;
        cells[y][x] = ch === 'M' ? 'W' : ch === 'm' ? 'M' : 'm';
      }
    }
  }
  return toRows(cells);
}

/* ---------------- the spec, and the pipeline ----------------
 * One normalised value in, one grid out. forgeSpec() is where every spelling
 * the backend might use is flattened, and it is the only place that needs to
 * change when gauntlet/forge.py settles on its field names.
 */
/* How far the grow stage is allowed to go, given the hint. `narrow | standard
 * | broad` is gauntlet/forge.py's word for the shape of the LINE rather than
 * of the rung: the Tracing Needle stays narrow at rung nine and the Boundary
 * Maul is broad at rung one, because — the art brief's words — "a line that
 * gets wider every rung ends as a rectangle".
 *
 * Note what it does NOT do: narrow never reduces a widen of one to zero. A
 * hint that removed a rung's only move would trade one failure for another,
 * and forgeSpread() would catch it, so it is easier to not do it. */
function widenFor(def, silhouette) {
  if (silhouette === 'broad') return Math.min(3, def.widen + 1);
  if (silhouette === 'narrow') return def.widen > 1 ? def.widen - 1 : def.widen;
  return def.widen;
}

export function forgeSpec(spec) {
  let s = (spec && typeof spec === 'object') ? spec : {};
  /* An item dict carries its forge state in a nested object. Reading through
   * it here rather than only in forgeOf() means forgeInfo(item) and
   * forgeSprite(item) answer about the item the caller actually holds, instead
   * of quietly answering about a rung-1 blade. */
  if (s.forge && typeof s.forge === 'object') {
    const f = s.forge;
    s = {
      weapon: f.weapon || f.family || f.blade || f.shape || s.icon || s.id,
      blade: f.blade || s.id,
      tier: f.tier != null ? f.tier : f.rung,
      metal: f.metal,
      /* forge.art_at()'s dict, passed through whole when it is there. */
      material: f.material, accent: f.accent, motif: f.motif,
      aura: f.aura, silhouette: f.silhouette, frames: f.frames,
    };
  } else if (s.forge_tier != null || s.forgeTier != null) {
    s = {
      weapon: s.forge_weapon || s.weapon || s.icon || s.id,
      tier: s.forge_tier != null ? s.forge_tier : s.forgeTier,
      metal: s.forge_metal || s.metal,
    };
  }
  const rawTier = s.tier != null ? s.tier
    : s.rung != null ? s.rung
    : s.level != null ? s.level
    : s.forge_tier != null ? s.forge_tier : 1;
  const tier = clampTier(rawTier);
  /* Order is intent first. A blade id names one of the six lines and beats
   * everything else; `shape` is the art dict's word and beats an icon, which
   * is the catalogue's. Reading `shape` before `id` is what stops the
   * Calipers' art dict — which says relic — being resolved off a field nobody
   * filled in and coming back a sword. */
  const weapon = forgeWeaponKey(
    (s.blade != null && FORGE_BLADES[s.blade]) ? s.blade
    : (s.id != null && FORGE_BLADES[s.id]) ? s.id
    : s.weapon != null ? s.weapon
    : s.family != null ? s.family
    : s.shape != null ? s.shape
    : s.icon != null ? s.icon
    : s.id != null ? s.id
    : spec);
  /* `material` is deliberately NOT read as a metal. forge.art_at() sends both
   * words and they mean different things — "steel" is how finished the object
   * is, "marshsilver" is what the player carried out of the marsh — and
   * collapsing the two would silently repaint every rung. */
  const metalRaw = s.metal != null ? s.metal : (s.ore != null ? s.ore : null);
  const metal = metalRaw == null ? '' : forgeMetalKey(metalRaw, tier);
  const blade = (s.blade && FORGE_BLADES[s.blade]) ? s.blade
    : (s.id && FORGE_BLADES[s.id]) ? s.id : '';
  const material = typeof s.material === 'string' ? s.material : '';
  const accent = typeof s.accent === 'string' ? s.accent
    : (blade ? FORGE_BLADES[blade].tint : '');
  const motif = (typeof s.motif === 'string' && FORGE_MOTIFS[s.motif]) ? s.motif : '';
  const aura = (typeof s.aura === 'string' && FORGE_AURAS[s.aura]) ? s.aura : '';
  const sil = (s.silhouette === 'narrow' || s.silhouette === 'broad') ? s.silhouette : 'standard';
  const frames = s.frames === 1 ? 1 : 0;
  return {
    weapon, tier, metal, blade, material, accent, motif, aura,
    silhouette: sil, frames,
    key: `${weapon}:${tier}:${metal}:${material}:${accent}:${motif}:${aura}:${sil}:${frames}`,
  };
}

/* Everything the smith's UI needs to caption a blade, with no game rules in
 * it: what it is, what rung it is on, what it is made of, and whether the
 * upgrade the player is about to pay for will make it move. */
export function forgeInfo(spec) {
  const s = forgeSpec(spec);
  const def = forgeRung(s.tier);
  const m = s.metal ? FORGE_METALS[s.metal] : null;
  const frames = forgeFrameCount(s.tier, s);
  return {
    blade: s.blade, weapon: s.weapon, family: FORGE_WEAPONS[s.weapon].label,
    tier: s.tier, rung: def.name,
    material: s.material, accent: s.accent || (m ? (m.energy || RAMPS[m.trim][SHADE.SPEC]) : ''),
    motif: s.motif, aura: s.aura, silhouette: s.silhouette,
    metal: s.metal, metalLabel: m ? m.label : '', metalRung: m ? m.rung : 0,
    region: m ? m.region : '', ramp: m ? m.ramp : (MATERIAL_RAMP[s.material] || ''),
    animated: frames > 1, motion: frames > 1 ? def.motion : 'still', frames,
  };
}

const forgeGridCache = cappedCache(768);
const forgeSpriteCache = cappedCache(768);

function buildForgeGrid(s, f) {
  const fam = FORGE_WEAPONS[s.weapon];
  const def = forgeRung(s.tier);
  const seed = hash(`${s.weapon}:${s.metal}:${s.blade}:${s.motif}`) || 1;
  const cells = toCells(fam.grid);
  /* Order is the design, and every pair of these is wrong the other way round:
   * broaden before grooving or the groove is cut where the blade used to be;
   * authored character before teeth so the teeth grow on the guard the
   * character left; stones and crest before the shear so they ride the sweep;
   * rim after all of it so added matter is lit by the same pass as authored
   * matter and there is no seam where the growth starts. */
  forgeWiden(cells, fam, widenFor(def, s.silhouette));
  if (fam.growth) for (let lv = 2; lv <= s.tier; lv++) stamp(cells, fam.growth[lv]);
  forgeFuller(cells, fam, def, s.tier);
  forgeTeeth(cells, fam, def.teeth, s.silhouette);
  forgeInlay(cells, fam, def.inlay);
  /* A family that did not author a seat still gets one, centred on its own
   * axis at its own counterweight. The authored list exists because a stone
   * placed by an algorithm always lands in the wrong hole — not because the
   * algorithm is allowed to decline. */
  const seats = fam.stones
    || (fam.pommel != null ? [{ y: fam.pommel, x: fam.axis - 3 }] : []);
  for (const seat of seats) forgeStone(cells, seat, def.stone);
  /* The shear runs BEFORE the crest, not after. A crest is placed off the
   * crown row, and a crown row that has just moved two columns leaves the
   * crest behind in mid-air — which is exactly what a spear did until the
   * order was swapped. */
  forgeCurve(cells, fam, def.curve);
  forgeCrest(cells, fam.crest, def.crest);
  forgeCrest(cells, fam.crest2, def.crest);
  /* motif -> rim -> animate -> aura. The first two are the order the art brief
   * specifies and the reason is visible either way round: a mark cut before
   * the rim is lit like the metal it is cut into, and a mark added after it is
   * a sticker. The aura comes last because it is not part of the object. */
  const animated = forgeFrameCount(s.tier, s) > 1;
  let g = toRows(cells);
  if (s.motif) g = applyMotif(g, s.motif, { tier: s.tier, seed, frame: f, animated });
  g = applyRim(g);
  g = forgeAnimate(g, def, f, seed, !!s.aura);
  if (s.aura) g = applyAura(g, s.aura, { tier: s.tier, seed, frame: f });
  return g;
}

export function forgeGrid(spec, frame = 0) {
  const s = forgeSpec(spec);
  const frames = forgeFrameCount(s.tier, s);
  const f = ((frame % frames) + frames) % frames;
  return forgeGridCache.get(`${s.key}:${f}`, () => buildForgeGrid(s, f));
}

/* A finished 32x32 canvas. */
export function forgeSprite(spec, frame = 0) {
  const s = forgeSpec(spec);
  const frames = forgeFrameCount(s.tier, s);
  const f = ((frame % frames) + frames) % frames;
  return forgeSpriteCache.get(`${s.key}:${f}`, () => gridSprite(
    forgeGrid(s, f), forgePalette(s.metal, s.tier, s.material, s.accent), FN, FN));
}

export function forgeFrames(spec) {
  const s = forgeSpec(spec);
  const n = forgeFrameCount(s.tier, s);
  const out = new Array(n);
  for (let i = 0; i < n; i++) out[i] = forgeSprite(s, i);
  return out;
}

export function forgeFrameFor(spec, opts = {}) {
  const s = forgeSpec(spec);
  const frames = forgeFrameCount(s.tier, s);
  if (frames <= 1 || isReduced(opts)) return 0;
  if (opts.frame !== undefined && opts.frame !== null) {
    return ((opts.frame % frames) + frames) % frames;
  }
  if (opts.time !== undefined && opts.time !== null) {
    return Math.floor(opts.time / FRAME_MS) % frames;
  }
  return 0;
}

/* The one call the smith screen, the battle scene and the inventory need.
 *
 *   lootart.drawForgeWeapon(ctx, { blade: 'recall_chain', tier: 6, metal: 'nullsteel' },
 *                           x, y, { scale: 3, time: performance.now() });
 */
export function drawForgeWeapon(ctx, spec, x, y, opts = {}) {
  const scale = Math.max(1, opts.scale || 1);
  const img = forgeSprite(spec, forgeFrameFor(spec, opts));
  const px = Math.round(x), py = Math.round(y);
  if (opts.shadow) {
    drawGroundShadow(ctx, px + (FN * scale) / 2, py + FN * scale - 2 * scale,
      Math.round(8 * scale), Math.round(3 * scale), 0.36);
  }
  if (Number.isInteger(scale)) {
    ctx.drawImage(scaleSprite(img, scale), px, py);
  } else {
    const smooth = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, px, py, FN * scale, FN * scale);
    ctx.imageSmoothingEnabled = smooth;
  }
  return img;
}

/* ---------------- the measurement ----------------
 * "You can name the rung from across the room" is a claim about pixels, so it
 * is measured rather than asserted. Two numbers per step, both off the binary
 * mask with colour thrown away entirely:
 *
 *   steps   pixels of silhouette that differ between rung N and rung N+1
 *   total   between rung 1 and rung 8
 *
 * A zero anywhere in `steps` is a bug and scripts/verify/forge.mjs fails on
 * it: it means two rungs of that family have the same outline, and an upgrade
 * the player cannot see is an upgrade they did not get.
 */
export function forgeSpread(weapon, metal) {
  const key = forgeWeaponKey(weapon);
  const mask = (t) => forgeGrid({ weapon: key, tier: t, metal }, 0)
    .map(r => r.padEnd(FN, '.').split('')
      .map(c => (c === '.' || c === ' ' || c === 'r' || c === 'R') ? 0 : 1).join('')).join('');
  const masks = [];
  for (let t = 1; t <= FORGE_TIER_COUNT; t++) masks.push(mask(t));
  const steps = [];
  for (let i = 0; i + 1 < masks.length; i++) {
    let d = 0;
    for (let k = 0; k < masks[i].length; k++) if (masks[i][k] !== masks[i + 1][k]) d++;
    steps.push(d);
  }
  let total = 0;
  for (let k = 0; k < masks[0].length; k++) if (masks[0][k] !== masks[masks.length - 1][k]) total++;
  const ink = (s) => { let n = 0; for (const c of s) if (c === '1') n++; return n; };
  return {
    weapon: key, steps, min: Math.min(...steps), total,
    ink: masks.map(ink),
  };
}

/* The whole vocabulary, as data. gauntlet/forge.py can diff its own lists
 * against this in a test rather than the two files drifting for a week and the
 * player finding out. */
export function forgeVocabulary() {
  return {
    size: FN, tiers: FORGE_TIER_COUNT, frames: FORGE_FRAMES,
    firstAnimated: FORGE_FIRST_ANIMATED,
    rungs: FORGE_RUNGS.slice(1).map(r => ({
      tier: r.rung, name: r.name, motion: r.motion,
      animated: r.rung >= FORGE_FIRST_ANIMATED,
    })),
    blades: FORGE_BLADE_KEYS.map(k => ({ id: k, family: FORGE_BLADES[k].family, tint: FORGE_BLADES[k].tint })),
    weapons: FORGE_WEAPON_KEYS.map(k => ({ key: k, label: FORGE_WEAPONS[k].label, kind: FORGE_WEAPONS[k].kind })),
    metals: FORGE_METAL_KEYS.map(k => ({
      key: k, label: FORGE_METALS[k].label, rung: FORGE_METALS[k].rung,
      region: FORGE_METALS[k].region, ramp: FORGE_METALS[k].ramp,
      colour: FORGE_METALS[k].colour,
    })),
    motifs: FORGE_MOTIF_KEYS,
    auras: FORGE_AURA_KEYS,
    materials: Object.keys(MATERIAL_RAMP),
    silhouettes: ['narrow', 'standard', 'broad'],
    aliases: { weapons: Object.keys(WEAPON_ALIAS).length, metals: Object.keys(METAL_ALIAS).length },
  };
}

/* ---------------- reading a forged item off the backend ----------------
 * Strict on purpose. An item is forge art only if it SAYS it is: a `forge`
 * object, or a forge_tier/forgeTier alongside a weapon slot. Sniffing for a
 * metal-sounding word would repaint half the existing catalogue the first time
 * somebody names an item "Iron Circlet".
 */
export function forgeOf(item) {
  if (!item || typeof item !== 'object') return null;
  const declared = (item.forge && typeof item.forge === 'object')
    || item.forge_tier != null || item.forgeTier != null;
  return declared ? forgeSpec(item) : null;
}

export function isForged(item) { return forgeOf(item) !== null; }

/* ---------------- the blade in the hand ----------------
 * The inventory icon is where a weapon is ADMIRED; the hero's hand is where it
 * is SEEN, for fifty hours, at 3x, in every frame of the overworld. A forge
 * ladder that is unmistakable in a 32-pixel icon and identical to slag iron in
 * the field has put its effort in exactly the wrong place.
 *
 * So the ladder is authored a second time inside the 6x12 box HERO_WEAPONS
 * uses, at the anchor sprites.js already publishes — which is not moved, not
 * mirrored and not re-registered here. Six pixels of extra guard at 16px is a
 * lot of guard.
 *
 * Eight rungs in seventy-two pixels is tight and the table below is what
 * honesty about that looks like: every rung moves at least two pixels of
 * outline, and scripts/verify/forge.mjs counts them rather than taking my word
 * for it. The metal carries the rest, and the metal is the half of the
 * escalation that survives being small.
 */
const FORGE_HAND_ART = {
  sword: ['..o...', '.oBo..', '.oBo..', '.oBo..', '.oBo..', '.oBo..',
          '.oBo..', '.oBo..', '.oggo.', '..s...', '..s...', '..o...'],
  sabers: ['......', '..o...', '.oBo..', '.oBo..', '.oBo..', '.oBo..',
           '.oBo..', '.oggo.', '..s...', '..o...', '......', '......'],
  dagger: ['......', '......', '..o...', '.oBo..', '.oBo..', '.oBo..',
           '.oBo..', '.oggo.', '..s...', '..s...', '..o...', '......'],
  axe:    ['..oo..', '.oBBo.', '.oBBo.', '..oo..', '.oso..', '.oso..',
           '.oso..', '.oso..', '.oso..', '.oso..', '.ooo..', '......'],
  hammer: ['..oo..', '.oBBo.', '.oBBo.', '..oo..', '..os..', '..os..',
           '..os..', '..os..', '..os..', '..os..', '..oo..', '......'],
  spear:  ['..o...', '.oBo..', '.oBo..', '..o...', '..s...', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..s...', '..o...'],
  lance:  ['..o...', '.oBo..', '.oBo..', '.oBo..', '.oggo.', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..s...', '..o...'],
  staff:  ['..o...', '.omo..', '.omo..', '..o...', '..s...', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..s...', '..o...'],
  bow:    ['..o...', '.os...', '.os.w.', '.os.w.', '.os.w.', '.os.w.',
           '.os.w.', '.os.w.', '.os.w.', '.os...', '..o...', '......'],
  focus:  ['......', '..oo..', '.ommo.', '.ommo.', '..oo..', '..s...',
           '..s...', '..s...', '..s...', '..s...', '..o...', '......'],
  /* The three the art brief asked for by name. In six columns the Calipers are
   * the only thing in the game with a hole down the middle of them, which is
   * all the legibility they need. */
  calipers: ['.o..o.', '.g..g.', '.g..g.', '.g..g.', '.g..g.', '.oggo.',
             '.ommo.', '.oggo.', '..s...', '..s...', '..o...', '......'],
  chain:   ['.oooo.', '.oBBo.', '.oooo.', '..oo..', '.oooo.', '.oBBo.',
            '.oooo.', '..gg..', '..s...', '..s...', '..o...', '......'],
  spanner: ['oo..oo', 'oB..Bo', 'oBBBBo', '.oBBo.', '..oo..', '..s...',
            '..s...', '..s...', '..s...', '..s...', '..o...', '......'],
};

/* Read alongside the map of what is actually VISIBLE. A weapon held in front
 * of a 16x24 body is, for most of its length, INSIDE that body's outline: of
 * the seventy-two cells in this box, nineteen are transparent on the bare hero
 * facing the camera and as few as four facing left. So a rung that grows only
 * on the inboard side measures as a change to the weapon sprite and changes
 * nothing the player can see once it is in a hand.
 *
 * Every step below therefore also touches the outboard band — the top-right
 * and bottom-right corners of the box — and scripts/verify/forge.mjs checks
 * the composited hero rather than the overlay, at every facing, because that
 * is where the claim actually has to hold. */
const FORGE_HAND_GROWTH = {
  sword: {
    2: [[8, 0, 'og'], [8, 4, 'go']],
    3: [[3, 1, 'oBBo'], [4, 1, 'oBBo'], [5, 1, 'oBBo'], [6, 1, 'oBBo'], [7, 1, 'oBBo']],
    4: [[11, 1, 'oggo']],
    5: [[7, 0, 'o'], [7, 5, 'o']],
    6: [[6, 0, 'o'], [6, 5, 'o'], [10, 1, 'o'], [10, 4, 'o']],
    7: [[5, 0, 'o'], [5, 5, 'o'], [9, 1, 'o'], [9, 4, 'o']],
    8: [[0, 1, 'o'], [0, 3, 'o'], [0, 4, 'o'], [4, 0, 'o'], [4, 5, 'o']],
    9: [[2, 1, 'oBBo'], [1, 1, 'oBBo'], [3, 0, 'o'], [3, 5, 'o']],
  },
  sabers: {
    2: [[7, 0, 'og'], [7, 4, 'go']],
    3: [[3, 1, 'oBBo'], [4, 1, 'oBBo'], [5, 1, 'oBBo'], [6, 1, 'oBBo']],
    4: [[9, 1, 'oggo']],
    5: [[6, 0, 'o'], [6, 5, 'o'], [2, 4, 'o']],
    6: [[5, 0, 'o'], [5, 5, 'o'], [8, 1, 'o'], [8, 4, 'o']],
    7: [[1, 1, 'o'], [1, 3, 'o'], [1, 4, 'o'], [10, 2, 'oo']],
    8: [[0, 2, 'oo'], [0, 4, 'o'], [4, 0, 'o'], [4, 5, 'o']],
    9: [[3, 0, 'o'], [3, 5, 'o'], [9, 2, 'oo']],
  },
  dagger: {
    2: [[7, 0, 'og'], [7, 4, 'go']],
    3: [[3, 1, 'oBBo'], [4, 1, 'oBBo'], [5, 1, 'oBBo'], [6, 1, 'oBBo']],
    4: [[10, 1, 'oggo']],
    5: [[6, 0, 'o'], [6, 5, 'o'], [2, 4, 'o']],
    6: [[5, 0, 'o'], [5, 5, 'o'], [9, 1, 'o'], [9, 4, 'o']],
    7: [[2, 1, 'o'], [2, 3, 'o'], [11, 2, 'oo']],
    8: [[1, 2, 'oo'], [4, 0, 'o'], [4, 5, 'o'], [10, 5, 'o']],
    9: [[3, 0, 'o'], [3, 5, 'o'], [8, 1, 'o'], [8, 4, 'o']],
  },
  axe: {
    2: [[0, 4, 'o'], [1, 4, 'Bo'], [2, 4, 'Bo'], [3, 4, 'o']],
    3: [[0, 0, 'o'], [1, 0, 'oB'], [2, 0, 'oB'], [3, 0, 'o'], [0, 5, 'o']],
    4: [[4, 0, 'o'], [4, 4, 'o'], [8, 0, 'o']],
    5: [[3, 1, 'oBBBo'], [4, 2, 'oo'], [9, 0, 'o']],
    6: [[10, 1, 'oggo'], [11, 2, 'oo']],
    7: [[0, 0, 'oooooo'], [10, 5, 'o']],
    8: [[5, 0, 'o'], [5, 5, 'o'], [9, 1, 'o'], [9, 4, 'o']],
    9: [[11, 2, 'oo'], [10, 0, 'o'], [10, 5, 'o']],
  },
  hammer: {
    2: [[1, 0, 'oB'], [1, 4, 'Bo'], [2, 0, 'oB'], [2, 4, 'Bo']],
    3: [[0, 1, 'oooo'], [3, 1, 'oooo']],
    4: [[4, 1, 'o'], [4, 4, 'o'], [8, 1, 'o']],
    5: [[0, 0, 'o'], [0, 5, 'o'], [3, 0, 'o'], [3, 5, 'o']],
    6: [[10, 1, 'oggo'], [11, 2, 'oo']],
    7: [[5, 1, 'o'], [5, 4, 'o'], [9, 1, 'o'], [9, 4, 'o']],
    8: [[6, 1, 'o'], [6, 4, 'o'], [8, 1, 'o'], [8, 4, 'o']],
    9: [[11, 2, 'oo'], [9, 0, 'o'], [9, 5, 'o']],
  },
  spear: {
    2: [[3, 1, 'oggo']],
    3: [[1, 1, 'oBBo'], [2, 1, 'oBBo']],
    4: [[3, 0, 'o'], [3, 5, 'o']],
    5: [[0, 1, 'o'], [0, 3, 'o'], [0, 4, 'o']],
    6: [[2, 0, 'o'], [2, 5, 'o']],
    7: [[11, 1, 'ogo'], [11, 3, 'go']],
    8: [[1, 0, 'o'], [1, 5, 'o'], [4, 1, 'o'], [4, 4, 'o']],
    9: [[10, 1, 'o'], [10, 4, 'o'], [0, 0, 'o'], [0, 4, 'o']],
  },
  lance: {
    2: [[4, 0, 'og'], [4, 4, 'go'], [3, 4, 'o']],
    3: [[2, 1, 'oBBo'], [3, 1, 'oBBo']],
    4: [[5, 1, 'o'], [5, 4, 'o'], [1, 4, 'o']],
    5: [[3, 0, 'o'], [3, 5, 'o']],
    6: [[11, 1, 'oggo']],
    7: [[0, 1, 'o'], [0, 3, 'o'], [2, 0, 'o'], [2, 5, 'o']],
    8: [[1, 0, 'o'], [1, 5, 'o'], [10, 1, 'o'], [10, 4, 'o']],
    9: [[0, 0, 'o'], [0, 4, 'o'], [9, 1, 'o'], [9, 4, 'o']],
  },
  staff: {
    2: [[1, 1, 'ommo'], [2, 1, 'ommo']],
    3: [[0, 1, 'ogo'], [0, 4, 'o'], [3, 1, 'ogo']],
    4: [[1, 0, 'o'], [1, 5, 'o']],
    5: [[2, 0, 'o'], [2, 5, 'o']],
    6: [[0, 0, 'o'], [0, 5, 'o'], [3, 0, 'o'], [3, 5, 'o']],
    7: [[11, 1, 'oggo']],
    8: [[4, 1, 'o'], [4, 4, 'o'], [10, 1, 'o'], [10, 4, 'o']],
    9: [[5, 1, 'o'], [5, 4, 'o'], [9, 1, 'o'], [9, 4, 'o']],
  },
  bow: {
    2: [[0, 1, 'oo'], [10, 1, 'oo'], [0, 3, 'o']],
    3: [[4, 0, 'os'], [5, 0, 'os'], [6, 0, 'os'], [1, 4, 'w']],
    4: [[3, 0, 'os'], [7, 0, 'os'], [9, 4, 'w']],
    5: [[2, 0, 'o'], [8, 0, 'o'], [0, 4, 'o']],
    6: [[11, 2, 'oo'], [11, 3, 'o']],
    7: [[4, 5, 'o'], [5, 5, 'o'], [6, 5, 'o'], [10, 4, 'o']],
    8: [[1, 0, 'o'], [9, 0, 'o'], [0, 0, 'o'], [10, 0, 'o'], [2, 5, 'o']],
    9: [[3, 5, 'o'], [7, 5, 'o'], [11, 1, 'o']],
  },
  focus: {
    2: [[2, 0, 'om'], [3, 0, 'om'], [2, 4, 'mo'], [3, 4, 'mo']],
    3: [[1, 1, 'oooo'], [4, 1, 'oooo']],
    4: [[1, 0, 'o'], [4, 0, 'o'], [1, 5, 'o'], [4, 5, 'o']],
    5: [[0, 2, 'oo'], [0, 4, 'o'], [5, 1, 'o'], [5, 4, 'o']],
    6: [[10, 1, 'oggo']],
    7: [[6, 1, 'o'], [6, 4, 'o'], [9, 1, 'o'], [9, 4, 'o']],
    8: [[0, 1, 'o'], [0, 4, 'o'], [11, 2, 'oo']],
    9: [[7, 1, 'o'], [7, 4, 'o'], [8, 1, 'o'], [8, 4, 'o']],
  },
  calipers: {
    2: [[5, 0, 'oggggo'], [0, 5, 'o']],
    3: [[0, 0, 'o'], [1, 5, 'o']],
    4: [[10, 1, 'oggo']],
    5: [[6, 0, 'o'], [6, 5, 'o'], [7, 5, 'o']],
    6: [[7, 0, 'o'], [7, 5, 'o'], [9, 1, 'o'], [9, 4, 'o']],
    7: [[1, 0, 'o'], [2, 5, 'o']],
    8: [[2, 0, 'o'], [3, 5, 'o'], [11, 2, 'oo']],
    9: [[3, 0, 'o'], [3, 5, 'o'], [8, 1, 'o'], [8, 4, 'o']],
  },
  chain: {
    2: [[7, 1, 'oggo'], [7, 5, 'o']],
    3: [[0, 0, 'oooooo'], [1, 0, 'oBBBBo'], [2, 0, 'oooooo']],
    4: [[10, 1, 'oggo']],
    5: [[4, 0, 'oooooo'], [5, 0, 'oBBBBo'], [6, 0, 'oooooo'], [3, 4, 'o']],
    6: [[3, 1, 'oooo'], [3, 5, 'o'], [8, 1, 'o']],
    7: [[8, 1, 'o'], [8, 4, 'o']],
    8: [[9, 1, 'o'], [9, 4, 'o'], [11, 2, 'oo']],
    9: [[3, 0, 'o'], [7, 0, 'o'], [9, 5, 'o']],
  },
  spanner: {
    2: [[4, 1, 'oggo'], [7, 1, 'o']],
    3: [[3, 0, 'oBBBBo']],
    4: [[10, 1, 'oggo']],
    5: [[5, 1, 'o'], [5, 4, 'o'], [10, 5, 'o']],
    6: [[9, 1, 'o'], [9, 4, 'o'], [11, 2, 'oo']],
    7: [[6, 1, 'o'], [6, 4, 'o'], [9, 5, 'o']],
    8: [[8, 1, 'o'], [8, 4, 'o']],
    9: [[7, 1, 'o'], [7, 4, 'o'], [4, 0, 'o'], [4, 5, 'o'], [11, 5, 'o']],
  },
};

const forgeHandCache = cappedCache(512);

/* The compact motion. A drifting specular survives seventy-two pixels; motes
 * beside a 6-wide sprite do not — at 3x they land on the hero's arm and read
 * as damage. So the hand keeps the glint and the rune pulse and drops the
 * rest, which is the same clamp compactStyle() applies to the rarity ladder
 * and for the same reason. */
function forgeHandAnimate(grid, def, frame) {
  if (def.rung < FORGE_FIRST_ANIMATED) return grid;
  const cells = toCells(grid);
  const h = cells.length, w = widthOf(cells);
  const f = ((frame % FORGE_FRAMES) + FORGE_FRAMES) % FORGE_FRAMES;
  const edge = [];
  for (let y = h - 1; y >= 0; y--) {
    for (let x = 0; x < w; x++) {
      if (!HARD.has(cells[y][x])) continue;
      const up = y > 0 ? cells[y - 1][x] : '.';
      const left = x > 0 ? cells[y][x - 1] : '.';
      const bare = (c) => c === '.' || c === ' ' || c === 'o' || c === 'O';
      if (bare(up) || bare(left)) edge.push([y, x]);
    }
  }
  if (edge.length) {
    const core = Math.max(1.1, edge.length / (FORGE_FRAMES * 2));
    const p = -core - 1 + (f / FORGE_FRAMES) * (edge.length + 2 * core + 2);
    for (let i = 0; i < edge.length; i++) {
      if (Math.abs(i - p) > core) continue;
      const [y, x] = edge[i];
      cells[y][x] = 'W';
    }
  }
  if (def.rung >= 7) {
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (cells[y][x] !== 'm') continue;
        if (((f + y) % FORGE_FRAMES) < FORGE_FRAMES / 2) cells[y][x] = 'M';
      }
    }
  }
  return toRows(cells);
}

/* { canvas, ox, oy } in hero-sprite coordinates, exactly like the rarity
 * overlays, so heroGearLayers() can treat a forged weapon and a rolled one the
 * same way and no call site downstream learns a new shape. */
export function forgeWeaponOverlay(spec, opts = {}) {
  const s = forgeSpec(spec);
  const facing = HERO_WEAPON_ANCHOR[opts.facing] ? opts.facing : 'down';
  const frames = forgeFrameCount(s.tier, s);
  const frame = isReduced(opts) ? 0 : forgeFrameFor(s, opts);
  const f = ((frame % frames) + frames) % frames;
  const [ax, ay] = HERO_WEAPON_ANCHOR[facing];
  const { weaponDY } = poseOffsets(facing, opts.pose || 'walk', opts.frameIndex || 0);
  const key = `${s.key}:${f}`;
  const canvas = forgeHandCache.get(key, () => {
    const art = FORGE_HAND_ART[s.weapon] || FORGE_HAND_ART.sword;
    const growth = FORGE_HAND_GROWTH[s.weapon] || FORGE_HAND_GROWTH.sword;
    const def = forgeRung(s.tier);
    const cells = toCells(art);
    for (let lv = 2; lv <= s.tier; lv++) stamp(cells, growth[lv]);
    return gridSprite(forgeHandAnimate(applyRim(toRows(cells)), def, f),
      forgePalette(s.metal, s.tier, s.material, s.accent, HAND_BUDGET), 6, 12);
  });
  return { canvas, ox: ax, oy: ay + weaponDY };
}

/* The same measurement as forgeSpread(), on the hand art. Reported separately
 * and deliberately: seventy-two pixels is a smaller budget than a thousand and
 * a number that looks thin here is thin honestly rather than by being averaged
 * into the icon's. */
export function forgeHandSpread(weapon) {
  const key = forgeWeaponKey(weapon);
  const art = FORGE_HAND_ART[key] || FORGE_HAND_ART.sword;
  const growth = FORGE_HAND_GROWTH[key] || FORGE_HAND_GROWTH.sword;
  const mask = (t) => {
    const cells = toCells(art);
    for (let lv = 2; lv <= t; lv++) stamp(cells, growth[lv]);
    return toRows(cells).map(r => r.padEnd(6, '.').split('')
      .map(c => (c === '.' || c === ' ') ? 0 : 1).join('')).join('');
  };
  const masks = [];
  for (let t = 1; t <= FORGE_TIER_COUNT; t++) masks.push(mask(t));
  const steps = [];
  for (let i = 0; i + 1 < masks.length; i++) {
    let d = 0;
    for (let k = 0; k < masks[i].length; k++) if (masks[i][k] !== masks[i + 1][k]) d++;
    steps.push(d);
  }
  let total = 0;
  for (let k = 0; k < masks[0].length; k++) if (masks[0][k] !== masks[masks.length - 1][k]) total++;
  return { weapon: key, steps, min: Math.min(...steps), total };
}

/* ================================================================
 * HOUSEKEEPING
 * ================================================================ */
export function clearLootArtCache() {
  gridCache.clear(); spriteCache.clear(); beamCache.clear();
  burstCache.clear(); cardCache.clear(); overlayCache.clear();
  impactCache.clear(); poolCache.clear(); equippedCache.clear();
  paletteCache.clear();
  forgeGridCache.clear(); forgeSpriteCache.clear(); forgeHandCache.clear();
  forgePaletteCache.clear();
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
    forgeWeapons: FORGE_WEAPON_KEYS.length,
    forgeMetals: FORGE_METAL_KEYS.length,
    forgeTiers: FORGE_TIER_COUNT,
    forgeGrids: forgeGridCache.size,
    forgeSprites: forgeSpriteCache.size + forgeHandCache.size,
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
 * 3b) THE FORGE. gauntlet/forge.py ships six lines of nine rungs, and the art
 *    side needs exactly two values from it per rung: the blade id and
 *    `forge.art_at(blade_id, tier)`. Three ways in, all one line:
 *
 *    a) The smith's screen, the upgrade preview, anywhere a rung is shown:
 *
 *         const art = artFromServer;            // forge.art_at(id, tier)
 *         lootart.drawForgeWeapon(ctx, { blade: 'recall_chain', tier: 7, ...art },
 *                                 x, y, { scale: 3, time: performance.now() });
 *
 *       32x32, not 24 — `lootart.FORGE_SIZE`. Rungs 1-4 are still and cost one
 *       canvas; 5-9 run `lootart.FORGE_FRAMES` frames at FRAME_MS and are
 *       cached, so passing `time` every frame allocates nothing after the first
 *       cycle. The art dict's `frames: 1` and the `stillness` aura both pin a
 *       rung that would otherwise move, which is the override the brief asked
 *       for. `lootart.forgeInfo(spec)` returns the caption: rung name, family,
 *       material, accent, motif, aura, and whether this rung moves.
 *
 *    b) The inventory, the loot card, the battle scene: NOTHING TO WIRE. Put
 *       the art dict on the item under `forge` and drawItem() routes itself:
 *
 *         { id: 'recall_chain', name: '...', slot: 'weapon', rarity: 'EPIC',
 *           forge: { tier: 7, ...forge.art_at('recall_chain', 7) } }
 *
 *       `forge_tier` / `forge_metal` as flat fields work too. Detection is
 *       strict — see forgeOf() — so an item without those fields is drawn by
 *       the rarity ladder exactly as before, and every existing sprite in the
 *       catalogue is byte-identical to what it was.
 *
 *    c) In the hand. Also nothing to wire: heroWeaponOverlay() checks the same
 *       field, so `equippedHeroSprites(G.equipped)` puts the forged blade at
 *       the rung the player has earned, at the anchor sprites.js publishes.
 *       HERO_WEAPON_ANCHOR is not moved and sprites.js is not touched.
 *
 *    THE METAL is optional and separate from the material. Pass `metal` (any
 *    of forge.py's eleven ids, or the noun a designer typed) and the body ramp
 *    becomes that metal's; leave it out and the art dict's `material` picks
 *    the ramp. Both paths are inside the colour budget.
 *
 *    MOTIFS AND AURAS. FORGE_MOTIF_KEYS and FORGE_AURA_KEYS are the merged
 *    tables legendaries.py and forge.py both asked for, implemented once.
 *    applyMotif() and applyAura() are exported so an artifact that was never
 *    forged can carry the same marks, and applyRarity() takes `motif` and
 *    `aura` in its options for exactly that.
 *
 *    `lootart.forgeVocabulary()` returns the whole art-side vocabulary — nine
 *    rungs, six lines, eleven metals with the region each drops in, eighteen
 *    motifs, twelve auras, three silhouette hints — so a test in forge.py can
 *    assert against it rather than the two files drifting for a week and the
 *    player finding out. scripts/verify/forge.mjs already does that from this
 *    side, against a forgeart.json generated from that module.
 *
 *    ONE THING THIS MODULE CANNOT FIX, for whoever owns sprites.js.
 *    scripts/verify/forgehero.mjs measures the OTHER hero path — heroFrame()'s
 *    own HERO_WEAPONS grid, driven by forge.hero_weapon_look() — and reports
 *    zero outline changes across the six hero rungs on every line. That is
 *    still true and it is not fixed here, because sprites.js is not this
 *    module's file and HERO_WEAPON_ANCHOR must not move. What IS fixed is the
 *    path the three call sites above actually use: through
 *    equippedHeroSprites(), every one of the nine rungs moves the composited
 *    hero's outline on every line, measured in scripts/verify/forge.mjs §6b.
 *    Wiring item 3 is therefore also the fix for that finding, and the two
 *    harnesses disagreeing is the two paths disagreeing, not a flaky number.
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
