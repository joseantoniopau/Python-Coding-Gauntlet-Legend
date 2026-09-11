/* The shared palette system: fifteen colours and a transparent slot.
 *
 * An SNES sprite draws from a 16-entry palette whose first entry is transparent,
 * so fifteen usable colours. We hold ourselves to that budget deliberately. It is
 * not nostalgia: a hard colour budget forces material ramps to be SHARED between
 * sprites, and shared ramps are most of why a 16-bit scene reads as one world
 * rather than as a pile of separately-drawn things.
 *
 * The other rule that matters is the mosaic effect — everything sits on the same
 * pixel grid at integer scale, so the eye reads one grain across terrain,
 * characters, enemies and UI. See docs/08-art-direction.md.
 *
 * Nothing here is taken from any existing game. These are our own colours,
 * organised the way the hardware would have forced us to organise them.
 */

/* ---------------------------------------------------------------- ramps */

/* A material is a 5-step ramp: deepest shadow, shadow, mid, light, specular.
 * Authoring against ramps rather than against loose hex values is what keeps the
 * total count inside the budget when sprites are composed together. */
export const RAMPS = {
  // --- metals, which this game is mostly made of
  iron:      ['#14141c', '#2a2c38', '#454956', '#6a6f80', '#9aa0b4'],
  steel:     ['#161a22', '#2e3644', '#4e5a6e', '#78879e', '#b3c1d6'],
  gunmetal:  ['#101016', '#22242e', '#383c4a', '#565c6e', '#848ca2'],
  chrome:    ['#1a1c24', '#4a5060', '#8a92a6', '#c4ccdc', '#f2f6ff'],
  gold:      ['#2a1c08', '#6a4a12', '#a8811f', '#e8c37d', '#fff0b4'],
  bronze:    ['#241608', '#5a3a14', '#8f6226', '#c99a52', '#efd09a'],
  rust:      ['#1c0e08', '#4a2414', '#7a3e20', '#a86038', '#d18f60'],

  // --- flesh, cloth, organics
  skin:      ['#2a1610', '#6a3a28', '#a8674a', '#e8b88a', '#ffe0c0'],
  bone:      ['#241f1a', '#5c5248', '#948878', '#cfc4b0', '#f4ecdc'],
  leather:   ['#180f0a', '#3a2418', '#5e3c26', '#8a5c3c', '#b58558'],
  cloth:     ['#14121c', '#2e2a3e', '#4c4662', '#6e678c', '#9a92b8'],

  // --- magic and elements
  violet:    ['#1a1030', '#34205c', '#543490', '#8f6ad6', '#c8a8ff'],
  arcane:    ['#140c28', '#2c1a56', '#4a2e8e', '#7a52cc', '#b490ff'],
  cyan:      ['#08202c', '#125064', '#1e7f9c', '#4fb7d6', '#9ae4f6'],
  ember:     ['#2a0c04', '#6a1e08', '#a83c10', '#e8762a', '#ffc26a'],
  blood:     ['#200409', '#5a0c18', '#8f1828', '#c43f4f', '#ff8a94'],
  venom:     ['#0a1c0e', '#18421f', '#2a6a33', '#4f9c50', '#8ad07a'],
  frost:     ['#0e1a28', '#1e3450', '#365a80', '#6a96bc', '#b4d8f0'],
  void:      ['#050408', '#120e1c', '#241c34', '#3c2e52', '#5c4a7c'],

  // --- world
  grass:     ['#141e10', '#2a3c1c', '#456028', '#6a8f3c', '#9fc25c'],
  earth:     ['#160f0a', '#32211a', '#4e372a', '#74543e', '#9c7a5c'],
  stone:     ['#12131a', '#262a34', '#40454f', '#5f6570', '#8a9098'],
  water:     ['#06141f', '#0e2c42', '#1a4c68', '#2f7a9c', '#6fb4d0'],
  wood:      ['#140c06', '#2e1c0e', '#4a2f18', '#6e4826', '#94683c'],
};

/* Ramp step names, so a sprite grid can read as intent rather than as indices. */
export const SHADE = { DEEP: 0, DARK: 1, MID: 2, LIGHT: 3, SPEC: 4 };

export function step(rampName, index) {
  const ramp = RAMPS[rampName] || RAMPS.iron;
  return ramp[Math.max(0, Math.min(ramp.length - 1, index))];
}

/* The one colour every sprite shares: the outline. A single near-black used
 * everywhere is a large part of why a scene reads as one set of objects. */
export const OUTLINE = '#07060c';
export const TRANSPARENT = null;

/* ---------------------------------------------------------------- budget */

export const MAX_COLOURS = 15;

/** Build a 16-slot palette: transparent, then up to fifteen colours.
 *  Pass material names or literal hex; duplicates collapse, which is how two
 *  sprites sharing a ramp cost less than two sprites that do not. */
export function buildPalette(entries) {
  const seen = [];
  for (const entry of entries) {
    const colours = Array.isArray(entry) ? entry
      : RAMPS[entry] ? RAMPS[entry] : [entry];
    for (const colour of colours) {
      if (colour && !seen.includes(colour)) seen.push(colour);
    }
  }
  if (!seen.includes(OUTLINE)) seen.unshift(OUTLINE);
  return seen.slice(0, MAX_COLOURS);
}

/** Report whether a sprite palette respects the budget. Used by the art tests;
 *  a sprite over budget is a bug, not a style choice. */
export function auditPalette(palette, label = 'sprite') {
  const colours = Object.values(palette || {})
    .filter(v => typeof v === 'string' && v !== TRANSPARENT);
  const unique = [...new Set(colours)];
  return {
    label,
    used: unique.length,
    budget: MAX_COLOURS,
    ok: unique.length <= MAX_COLOURS,
    over: Math.max(0, unique.length - MAX_COLOURS),
    colours: unique,
  };
}

/* ---------------------------------------------------------------- theme */

/* The dark 80s metal ground the whole game sits on. FFVI's construction rules,
 * deliberately not FFVI's palette: the soundtrack here is a distorted guitar and
 * a pastel world underneath it would read as a mistake. */
export const THEME = {
  void:      '#06060a',
  ground:    '#0b0b12',
  panel:     '#12131b',
  panelHigh: '#1c1e29',
  edge:      '#2e3242',
  edgeHigh:  '#4a5064',
  ink:       '#e6e8f2',
  inkDim:    '#98a0b4',
  inkFaint:  '#5e6577',
  gold:      '#e8c37d',
  goldHigh:  '#fff0b4',
  blood:     '#c43f4f',
  bone:      '#cfc4b0',
  arcane:    '#8f6ad6',
  arcaneHigh:'#c8a8ff',
  cyan:      '#4fb7d6',
  ember:     '#e8762a',
  venom:     '#4f9c50',
};

/* Rarity, which must be legible at a glance and must agree with
 * gauntlet/items.py RARITIES. */
export const RARITY = {
  COMMON:    { base: 'iron',    accent: '#9aa0b4', glow: null,       label: 'Common' },
  UNCOMMON:  { base: 'steel',   accent: '#8ad07a', glow: null,       label: 'Uncommon' },
  RARE:      { base: 'steel',   accent: '#4fb7d6', glow: '#1e7f9c',  label: 'Rare' },
  EPIC:      { base: 'arcane',  accent: '#c8a8ff', glow: '#7a52cc',  label: 'Epic' },
  LEGENDARY: { base: 'gold',    accent: '#fff0b4', glow: '#e8c37d',  label: 'Legendary' },
  MYTHIC:    { base: 'blood',   accent: '#ff8a94', glow: '#c43f4f',  label: 'Mythic' },
};

/* Per-region ground tone, so every biome shares the metal register while still
 * being told apart. */
export const BIOME_RAMP = {
  village: 'grass', grass: 'grass', highland: 'earth', forest: 'venom',
  deepforest: 'void', canopy: 'venom', swamp: 'venom', cave: 'stone',
  mine: 'ember', mountain: 'frost', citadel: 'arcane', wastes: 'gunmetal',
  ruins: 'gold', dungeon: 'iron', tower: 'cyan', arena: 'ember', castle: 'blood',
};

/* ---------------------------------------------------------------- helpers */

export function parseHex(hex) {
  if (!hex || typeof hex !== 'string') return [0, 0, 0];
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  if (h.length === 8) h = h.slice(0, 6);           // drop alpha; we do not use it
  const n = parseInt(h, 16);
  return Number.isFinite(n) ? [(n >> 16) & 255, (n >> 8) & 255, n & 255] : [0, 0, 0];
}

export function toHex([r, g, b]) {
  const clamp = (v) => Math.max(0, Math.min(255, Math.round(v)));
  return '#' + ((clamp(r) << 16) | (clamp(g) << 8) | clamp(b))
    .toString(16).padStart(6, '0');
}

export function shade(hex, amount) {
  const [r, g, b] = parseHex(hex);
  return toHex([r + amount, g + amount, b + amount]);
}

export function mix(a, b, t) {
  const [r1, g1, b1] = parseHex(a);
  const [r2, g2, b2] = parseHex(b);
  return toHex([r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t]);
}

/** Tint a whole ramp toward a colour — how one creature's palette is derived
 *  from a shared material without leaving the budget. */
export function tintRamp(rampName, colour, strength = 0.45) {
  const ramp = RAMPS[rampName] || RAMPS.iron;
  return ramp.map((c, i) => mix(c, colour, strength * (i / (ramp.length - 1))));
}

/** The standard four-part sprite palette: outline, three body tones, one rim.
 *  Every creature in the game is built from this shape, which is rule 3 in
 *  docs/08-art-direction.md. */
export function creaturePalette(rampName, rimColour) {
  const ramp = RAMPS[rampName] || RAMPS.iron;
  return {
    o: OUTLINE,
    d: ramp[SHADE.DARK],
    b: ramp[SHADE.MID],
    l: ramp[SHADE.LIGHT],
    s: ramp[SHADE.SPEC],
    r: rimColour || ramp[SHADE.SPEC],
    w: '#f4f6ff',
    k: ramp[SHADE.DEEP],
  };
}
