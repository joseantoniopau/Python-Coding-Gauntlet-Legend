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

/* ------------------------------------------------------------ light model */

/* Every ramp below was built against ONE lighting setup, and that is the reason
 * a scene made of them looks lit rather than tinted.
 *
 *   Key light:  low, hot, torch-coloured — CIELAB hue 65 deg (amber).
 *   Fill light: the cold ambient the key is not reaching — hue 275 deg (blue).
 *
 * docs/09-story-bible.md §8 asks for "one hot rim light from a low source, bone
 * and chrome in the same shot". A single hot key is what that means in colour:
 * the highlight steps of a ramp rotate TOWARD amber and the shadow steps rotate
 * TOWARD blue, while the mid step keeps the material's own local colour. The eye
 * reads that rotation as a light source. A ramp that only gets darker — same hue,
 * less lightness — reads as a flat object someone tinted, and that single missing
 * rotation is the cheapest, largest difference between pixel art that looks
 * painted and pixel art that looks recoloured.
 *
 * The rotation is applied as a vector in CIELAB a/b, weighted per step, so a
 * near-neutral material (iron, stone, bone) shows the light's colour strongly
 * while a saturated one (ember, venom) only leans into it. That is how real
 * surfaces behave and it keeps the saturated ramps from turning muddy.
 *
 * Measured on the ramps as authored: on every lit material the specular step's
 * projection onto the amber axis is higher than the deepest shadow's, by between
 * 2.6 (silver, a deliberately cool polish) and 40.5 (rust) CIELAB units. The six
 * exceptions are listed with the ramps and are exceptions on purpose.
 */
export const KEY_HUE = 65;      // hot low key light, CIELAB hue in degrees
export const FILL_HUE = 275;    // cold ambient fill

/* How far each of the five steps is pushed along the key/fill axis. Negative is
 * toward the cold fill, positive toward the hot key, zero is the material's own
 * unlit local colour. Exported because a sprite that builds its own ramp at
 * runtime must shade it the same way or it will not belong in the scene. */
export const LIGHT_WEIGHT = [-1, -0.5, 0, 0.6, 1];

/* ---------------------------------------------------------------- ramps */

/* A material is a 5-step ramp: deepest shadow, shadow, mid, light, specular.
 * Authoring against ramps rather than against loose hex values is what keeps the
 * total count inside the budget when sprites are composed together.
 *
 * Three properties were measured and held while these were tuned:
 *
 *  1. DARK-END SEPARATION. OUTLINE is L* 1.8. A shadow step sitting on top of
 *     that is a shadow the heavy outline eats, and the sprite loses a tone it
 *     paid for. Every ramp's deepest step is now at least L* 5.0 clear of the
 *     outline (the old table had eleven ramps under 5.0 and `void` was 0.6
 *     BELOW the outline, i.e. its darkest colour was invisible against its own
 *     edge).
 *
 *  2. THE FIVE STEPS ARE EVENLY FELT — for matte materials. Organics, cloth,
 *     world surfaces and the magic ramps climb in even L* steps, so no step is
 *     doing all the work and none is wasted.
 *
 *  3. METAL DOES NOT CLIMB EVENLY, AND THAT IS WHAT MAKES IT METAL. A metal's
 *     shadow/mid/light sit in a compressed dark band and then the specular jumps
 *     clear of it: steel climbs 12, 13, 15 and then 30 L*. The old metals did
 *     the opposite — iron climbed 11.7, 12.8, 15.8, 19.0, an expanding ramp,
 *     which is the profile of matte plastic. `lacquer` is the extreme case of
 *     the rule (9, 10, 12, then 48) and glass or wet enamel is meant to.
 */
export const RAMPS = {
  // --- metals, which this game is mostly made of.
  // Compressed body, hard specular, near-neutral mid so the key light's colour
  // shows: shadows go blue, highlights go amber.
  iron:      ['#131928', '#2c303d', '#4a4b53', '#6e696d', '#ada3a6'],
  steel:     ['#0d1c2e', '#283648', '#495362', '#76767f', '#cec4c2'],
  gunmetal:  ['#111824', '#252a36', '#3d3f4a', '#5c585f', '#9f969d'],
  chrome:    ['#111e30', '#394255', '#69707e', '#a9a4a9', '#fff4ef'],
  // silver is the one polish that stays cool at the top — a mirror reflects the
  // sky, not the torch. It is the armour metal: its specular is the colour the
  // server sends for a finished Mirrorbright Helm or Sunplate.
  silver:    ['#1a1f2c', '#414757', '#6c7284', '#a7aabd', '#dfdeed'],
  // gold keeps the game's signature #e8c37d / #fff0b4 at light and specular —
  // those two are the UI's gold and are spoken by web/css as well.
  gold:      ['#271e15', '#604715', '#a77d1f', '#e8c37d', '#fff0b4'],
  // gold leaf is gilding rather than solid gold: a richer body under a hard
  // white specular, which is how a gilded crest or a chased trim reads.
  goldleaf:  ['#1f1a1d', '#543804', '#8c6301', '#d39c3e', '#fff5eb'],
  bronze:    ['#231a14', '#573a17', '#8e6125', '#cf954d', '#ffce9b'],
  rust:      ['#1f1516', '#4b2718', '#793d1f', '#aa5e35', '#de8c61'],
  // lacquered enamel over metal: a dark body and a specular that jumps 48 L*
  // clear of it. Use it for a painted shield face or a japanned pauldron.
  lacquer:   ['#211017', '#491620', '#731e2d', '#9e3441', '#e6d3ce'],

  // --- flesh, cloth, organics. Matte: even steps.
  skin:      ['#271717', '#633627', '#9c5d40', '#d78f6d', '#ffd4be'],
  bone:      ['#1d1d22', '#4a433e', '#7c7061', '#baa58e', '#f7dec6'],
  leather:   ['#1c1617', '#402c22', '#66432d', '#95613e', '#c8875c'],
  // hide is leather's raw cousin: redder, coarser, for pelts and unworked straps.
  hide:      ['#221619', '#4a2a24', '#764233', '#a7634d', '#d7937a'],
  cloth:     ['#11172a', '#2e2e48', '#4d4864', '#776783', '#a892a4'],
  // velvet is dyed cloth rather than the undyed grey of `cloth` — the Sourceforged
  // cloak and anything else with a colour someone paid for.
  velvet:    ['#151432', '#39295d', '#604186', '#9062a9', '#c194c5'],

  // --- magic and elements.
  // These six are the deliberate exceptions to the warm-highlight rule: they are
  // emissive or they reflect a cold sky, so their own colour IS the light and
  // their highlights stay cool. Everything else in the game warms at the top.
  violet:    ['#1a1234', '#372562', '#593b98', '#8f67d1', '#c8a8ff'],
  arcane:    ['#18102f', '#342163', '#563899', '#8459d2', '#bd91f9'],
  cyan:      ['#0b2026', '#084859', '#077792', '#3fadd0', '#a3e3ff'],
  ember:     ['#2c1208', '#682207', '#a93e11', '#e8762a', '#ffc26a'],
  blood:     ['#250f12', '#5d0f1c', '#90162a', '#c43f4f', '#ff918e'],
  venom:     ['#0d1d13', '#19411f', '#2e6b33', '#519c4f', '#85d07c'],
  frost:     ['#161c25', '#203b54', '#346084', '#638fba', '#b7d4f8'],
  // void used to bottom out BELOW the outline, which made its shadow step a hole
  // rather than a colour. It is still the darkest material we have, but every
  // step of it can now be seen against its own edge.
  void:      ['#151420', '#262136', '#39304d', '#55446a', '#755f8c'],

  // --- world
  grass:     ['#151e15', '#2c3b1f', '#445f27', '#688c36', '#97c057'],
  earth:     ['#1b1619', '#3b2b25', '#5d4335', '#875f47', '#b78668'],
  stone:     ['#111825', '#282e3c', '#454954', '#6b6a71', '#9d979b'],
  water:     ['#10191f', '#103143', '#184e69', '#2b769e', '#77b2db'],
  wood:      ['#191416', '#37261c', '#593c24', '#815430', '#b07748'],
};

/* Ramp step names, so a sprite grid can read as intent rather than as indices. */
export const SHADE = { DEEP: 0, DARK: 1, MID: 2, LIGHT: 3, SPEC: 4 };

export function step(rampName, index) {
  const ramp = RAMPS[rampName] || RAMPS.iron;
  return ramp[Math.max(0, Math.min(ramp.length - 1, index))];
}

/* What each ramp IS, so a sprite can pick material by behaviour instead of by
 * memorising which of twenty-nine names happens to look right.
 *
 *   family  'metal' | 'organic' | 'cloth' | 'magic' | 'world'
 *   spec    how the top step behaves: 'hard' (a small bright specular that jumps
 *           clear of the body — metal, glass, enamel), 'soft' (a broad highlight
 *           — flesh, dyed cloth), 'matte' (barely a highlight at all — bone,
 *           stone, cloth), 'glow' (emissive; the material is its own light).
 *   warm    true if the highlight rotates toward the key light. False marks the
 *           six deliberate exceptions.
 */
export const MATERIALS = {
  iron:     { family: 'metal',   spec: 'hard',  warm: true },
  steel:    { family: 'metal',   spec: 'hard',  warm: true },
  gunmetal: { family: 'metal',   spec: 'hard',  warm: true },
  chrome:   { family: 'metal',   spec: 'hard',  warm: true },
  silver:   { family: 'metal',   spec: 'hard',  warm: true },
  gold:     { family: 'metal',   spec: 'soft',  warm: true },
  goldleaf: { family: 'metal',   spec: 'hard',  warm: true },
  bronze:   { family: 'metal',   spec: 'soft',  warm: true },
  rust:     { family: 'metal',   spec: 'matte', warm: true },
  lacquer:  { family: 'metal',   spec: 'hard',  warm: true },
  skin:     { family: 'organic', spec: 'soft',  warm: true },
  bone:     { family: 'organic', spec: 'matte', warm: true },
  leather:  { family: 'organic', spec: 'soft',  warm: true },
  hide:     { family: 'organic', spec: 'matte', warm: true },
  cloth:    { family: 'cloth',   spec: 'matte', warm: true },
  velvet:   { family: 'cloth',   spec: 'soft',  warm: true },
  violet:   { family: 'magic',   spec: 'glow',  warm: false },
  arcane:   { family: 'magic',   spec: 'glow',  warm: false },
  cyan:     { family: 'magic',   spec: 'glow',  warm: false },
  ember:    { family: 'magic',   spec: 'glow',  warm: true },
  blood:    { family: 'magic',   spec: 'glow',  warm: true },
  venom:    { family: 'magic',   spec: 'glow',  warm: true },
  frost:    { family: 'magic',   spec: 'glow',  warm: false },
  void:     { family: 'magic',   spec: 'matte', warm: false },
  grass:    { family: 'world',   spec: 'matte', warm: true },
  earth:    { family: 'world',   spec: 'matte', warm: true },
  stone:    { family: 'world',   spec: 'matte', warm: true },
  water:    { family: 'world',   spec: 'hard',  warm: false },
  wood:     { family: 'world',   spec: 'matte', warm: true },
};

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

/* ------------------------------------------------------- perceptual space */

/* CIELAB, because the three questions that matter about a ramp — is this step
 * evenly spaced from the last one, is it clear of the outline, is the highlight
 * warmer than the shadow — are all questions about perception, and answering
 * them in sRGB gives the wrong answer. Plain arithmetic, no allocation beyond
 * the returned triple, safe to call while building a sprite.
 */
function srgbToLinear(c) {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function linearToSrgb(c) {
  return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

/** [L*, a, b] for a hex colour. L* is 0 (black) to 100 (white). */
export function labOf(hex) {
  const [r8, g8, b8] = parseHex(hex);
  const r = srgbToLinear(r8), g = srgbToLinear(g8), b = srgbToLinear(b8);
  const X = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047;
  const Y = (r * 0.2126729 + g * 0.7151522 + b * 0.0721750);
  const Z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883;
  const f = (t) => t > 0.008856 ? Math.cbrt(t) : (7.787 * t + 16 / 116);
  const fx = f(X), fy = f(Y), fz = f(Z);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

/** Hex for a CIELAB triple. Out-of-gamut colours walk their chroma down rather
 *  than clipping a channel, which is what keeps a generated ramp's hue honest
 *  at the bright end instead of letting it slide toward whatever channel
 *  saturated first. */
export function labHex(L, a, b) {
  let ca = a, cb = b;
  const LL = Math.max(0, Math.min(100, L));
  for (let i = 0; i < 64; i++) {
    const fy = (LL + 16) / 116, fx = fy + ca / 500, fz = fy - cb / 200;
    const g = (t) => { const t3 = t * t * t; return t3 > 0.008856 ? t3 : (t - 16 / 116) / 7.787; };
    const X = g(fx) * 0.95047, Y = g(fy), Z = g(fz) * 1.08883;
    const r = linearToSrgb(X * 3.2404542 + Y * -1.5371385 + Z * -0.4985314);
    const gg = linearToSrgb(X * -0.9692660 + Y * 1.8760108 + Z * 0.0415560);
    const bb = linearToSrgb(X * 0.0556434 + Y * -0.2040259 + Z * 1.0572252);
    if (r >= -0.003 && r <= 1.003 && gg >= -0.003 && gg <= 1.003 && bb >= -0.003 && bb <= 1.003) {
      return toHex([r * 255, gg * 255, bb * 255]);
    }
    ca *= 0.94; cb *= 0.94;
    if (Math.abs(ca) < 0.05 && Math.abs(cb) < 0.05) {
      const v = LL / 100;
      const s = linearToSrgb(v <= 0.08 ? v / 9.033 : Math.pow((v + 0.16) / 1.16, 3)) * 255;
      return toHex([s, s, s]);
    }
  }
  return OUTLINE;
}

/** Push a colour `amount` CIELAB units toward the hot key light. Negative pushes
 *  toward the cold fill instead — that is all `cooler` is. Lightness is
 *  untouched, so this changes the temperature of a tone without changing which
 *  step of the ramp it reads as. */
export function warmer(hex, amount = 4) {
  const [L, a, b] = labOf(hex);
  const h = (amount >= 0 ? KEY_HUE : FILL_HUE) * Math.PI / 180;
  const m = Math.abs(amount);
  return labHex(L, a + m * Math.cos(h), b + m * Math.sin(h));
}
export function cooler(hex, amount = 4) { return warmer(hex, -amount); }

/* --------------------------------------------------- derived ramps */

/* The server sends single colours, not ramps: gauntlet/items.py hero_look()
 * hands over `metal: '#e2dcf0'` for a finished helm and `tunic`, `cloak`, `boot`
 * and `trim` beside it. A single colour painted flat across a sprite is the
 * recolour problem — what a piece of armour needs is a five-step material with
 * the same light on it as everything else in the scene.
 *
 * `rampFrom` is that conversion. It keeps the colour the server chose, puts it
 * at the step you name, and builds the other four around it using the family's
 * own lightness profile and the one key light. The result belongs in the scene
 * because it was lit by the same lamp as the authored ramps above.
 */

/* Per-family lightness ladders, in absolute L*, taken off the authored ramps
 * above: metal's body is compressed with the specular jumping clear of it, the
 * matte families climb evenly. `C` is how much chroma each step carries relative
 * to the mid, and `temp` is how hard the key light pushes this family around.
 *
 * `shift` is the part that stops a derived ramp washing out. Moving the ladder to
 * put the server's colour on the step you asked for must NOT drag the shadow
 * with it one-for-one: a bright polished helm and a dull one have nearly the
 * same darkest tone, because that tone is mostly ambient fill rather than the
 * object's own colour. So the shift is applied at 18% strength at the deepest
 * step and at full strength from the anchor up. Without this a Mirrorbright
 * Helm's "shadow" came out at L* 48 — a light grey, no shadow at all.
 */
const FAMILY_SHAPE = {
  metal:   { L: [10, 24, 38, 55, 85], C: [0.5, 0.9, 1, 0.9, 0.35], temp: 8 },
  organic: { L: [10, 27, 45, 65, 87], C: [0.35, 0.8, 1, 1.0, 0.6], temp: 6 },
  cloth:   { L: [8, 21, 34, 48, 66],  C: [0.45, 0.85, 1, 1.0, 0.8], temp: 7 },
  world:   { L: [8, 20, 32, 46, 64],  C: [0.35, 0.7, 1, 1.2, 1.3], temp: 5 },
  magic:   { L: [8, 21, 35, 52, 76],  C: [0.4, 0.75, 1, 1.15, 0.95], temp: 2 },
};
const SHIFT_WEIGHT = [0.18, 0.42, 0.8, 1, 1];

/* Derived ramps are cached: an equipped hero re-derives the same five materials
 * on every frame otherwise, and that is per-frame allocation in a draw path. The
 * cap keeps a long session from growing the map without bound; eviction is
 * oldest-first, which is right because gear changes rarely and the working set
 * is a handful of pieces. */
const RAMP_CACHE_MAX = 256;
const rampCache = new Map();

/** A five-step material built from one colour.
 *
 *  @param hex     the colour to keep, e.g. what the server sent for this piece
 *  @param family  'metal' | 'organic' | 'cloth' | 'world' | 'magic'
 *  @param anchor  which step `hex` becomes; defaults to LIGHT, because the
 *                 colours the server sends read as a lit surface, not a shadow
 *  @returns a frozen array of five hex strings, deep to specular. It is the
 *           cached instance, shared with every other caller asking for the same
 *           material, and frozen for that reason — copy it with slice() before
 *           changing anything, or you would be editing everyone's copy.
 */
export function rampFrom(hex, family = 'metal', anchor = SHADE.LIGHT) {
  const shape = FAMILY_SHAPE[family] || FAMILY_SHAPE.metal;
  const at = Math.max(0, Math.min(4, anchor | 0));
  const key = `${hex}|${family}|${at}`;
  const hit = rampCache.get(key);
  if (hit) return hit;

  const [L0, a0, b0] = labOf(hex);
  const c0 = Math.hypot(a0, b0);
  const h0 = Math.atan2(b0, a0);
  // Undo the anchor step's own share of chroma so the colour the server picked
  // lands exactly on the step asked for rather than near it.
  const baseC = c0 / (shape.C[at] || 1);
  const shift = L0 - shape.L[at];
  const kx = Math.cos(KEY_HUE * Math.PI / 180), ky = Math.sin(KEY_HUE * Math.PI / 180);
  const fx = Math.cos(FILL_HUE * Math.PI / 180), fy = Math.sin(FILL_HUE * Math.PI / 180);

  const out = new Array(5);
  for (let i = 0; i < 5; i++) {
    if (i === at) { out[i] = typeof hex === 'string' ? toHex(parseHex(hex)) : OUTLINE; continue; }
    const c = baseC * shape.C[i];
    let a = c * Math.cos(h0), b = c * Math.sin(h0);
    const w = LIGHT_WEIGHT[i] * shape.temp;
    if (w < 0) { a += -w * fx; b += -w * fy; } else { a += w * kx; b += w * ky; }
    // Never let a derived shadow sink into the outline: the whole point of the
    // dark-end audit above is that a tone you cannot see is a tone you wasted.
    // And never run off the top of the scale — L* has an end, and a specular
    // that asks for 118 is a specular with no colour left in it.
    const L = Math.max(OUTLINE_L + MIN_OUTLINE_GAP,
      Math.min(98, shape.L[i] + shift * (i >= at ? 1 : SHIFT_WEIGHT[i])));
    out[i] = labHex(L, a, b);
  }
  const frozen = Object.freeze(out);
  if (rampCache.size >= RAMP_CACHE_MAX) rampCache.delete(rampCache.keys().next().value);
  rampCache.set(key, frozen);
  return frozen;
}

/** Lightness of the shared outline, and the clearance a shadow step needs from
 *  it to stay visible. Measured, not guessed: at less than five L* apart the
 *  heavy outline and the deepest shadow read as one shape at 16px. */
export const OUTLINE_L = 1.8;
export const MIN_OUTLINE_GAP = 5;

/** Name of the shared ramp closest to a colour, compared at its mid step in
 *  CIELAB. Snapping an arbitrary server colour onto a shared material is how a
 *  new piece of gear joins the world's palette instead of adding to it — which
 *  matters, because the budget is fifteen. Pass a `family` to restrict the
 *  search to materials that behave the right way. */
export function nearestRamp(hex, family = null) {
  const [L, a, b] = labOf(hex);
  let best = 'iron', bestD = Infinity;
  for (const name in RAMPS) {
    if (family && (MATERIALS[name] || {}).family !== family) continue;
    const [L2, a2, b2] = labOf(RAMPS[name][SHADE.MID]);
    // Chroma and hue carry the material's identity; lightness mostly carries
    // which step you happened to sample, so it is weighted down.
    const d = (L - L2) * (L - L2) * 0.35 + (a - a2) * (a - a2) + (b - b2) * (b - b2);
    if (d < bestD) { bestD = d; best = name; }
  }
  return best;
}

/** A material for anything: a ramp name passes through, a hex is derived. The
 *  one call a sprite can make on a server value without knowing which it got. */
export function rampFor(value, family = 'metal', anchor = SHADE.LIGHT) {
  if (typeof value === 'string' && RAMPS[value]) return RAMPS[value];
  if (Array.isArray(value) && value.length >= 5) return value;
  if (typeof value === 'string' && value.charAt(0) === '#') return rampFrom(value, family, anchor);
  return RAMPS.iron;
}

/** The single hot rim from the low source in docs/09-story-bible.md §8. It is
 *  the material's own specular pushed hard toward the key, so the rim belongs to
 *  the object rather than being a white line stuck on its edge. */
export function rimFor(value, family = 'metal') {
  const ramp = rampFor(value, family);
  return warmer(ramp[SHADE.SPEC], 10);
}

/** Introspection for the verify harnesses: how much the derived-ramp cache holds
 *  and whether it is at its cap. */
export function rampCacheStats() {
  return { size: rampCache.size, cap: RAMP_CACHE_MAX, full: rampCache.size >= RAMP_CACHE_MAX };
}
export function clearRampCache() { rampCache.clear(); }

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

/* ---------------------------------------------------------------- theme */

/* The dark 80s metal ground the whole game sits on. Shared material ramps
 * establish the game's palette identity, with cool shadows and warm accents
 * supporting the guitar-led soundtrack.
 *
 * The material entries are READ OFF the ramps rather than written out again. A
 * UI painted in colours that are merely near the sprites' colours is the same
 * incoherence the shared-ramp rule exists to prevent, and a second copy of a hex
 * is a second thing to forget to update. The greys and inks below are furniture
 * and belong to the UI alone, so they stay literal. */
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
  gold:      RAMPS.gold[SHADE.LIGHT],
  goldHigh:  RAMPS.gold[SHADE.SPEC],
  blood:     RAMPS.blood[SHADE.LIGHT],
  bone:      RAMPS.bone[SHADE.LIGHT],
  arcane:    RAMPS.violet[SHADE.LIGHT],
  arcaneHigh:RAMPS.violet[SHADE.SPEC],
  cyan:      RAMPS.cyan[SHADE.LIGHT],
  ember:     RAMPS.ember[SHADE.LIGHT],
  venom:     RAMPS.venom[SHADE.LIGHT],
};

/* Rarity, which must be legible at a glance and must agree with
 * gauntlet/items.py RARITIES. Same rule as THEME: the accents and glows are ramp
 * steps, named, so a rarity is a material rather than a loose swatch. */
export const RARITY = {
  COMMON:    { base: 'iron',    accent: RAMPS.iron[SHADE.SPEC],   glow: null,                      label: 'Common' },
  UNCOMMON:  { base: 'steel',   accent: RAMPS.venom[SHADE.SPEC],  glow: null,                      label: 'Uncommon' },
  RARE:      { base: 'steel',   accent: RAMPS.cyan[SHADE.LIGHT],  glow: RAMPS.cyan[SHADE.MID],     label: 'Rare' },
  EPIC:      { base: 'arcane',  accent: RAMPS.violet[SHADE.SPEC], glow: RAMPS.arcane[SHADE.LIGHT], label: 'Epic' },
  LEGENDARY: { base: 'gold',    accent: RAMPS.gold[SHADE.SPEC],   glow: RAMPS.gold[SHADE.LIGHT],   label: 'Legendary' },
  MYTHIC:    { base: 'blood',   accent: RAMPS.blood[SHADE.SPEC],  glow: RAMPS.blood[SHADE.LIGHT],  label: 'Mythic' },
};

/* Per-region ground tone, so every biome shares the metal register while still
 * being told apart. */
export const BIOME_RAMP = {
  village: 'grass', grass: 'grass', highland: 'earth', forest: 'venom',
  deepforest: 'void', canopy: 'venom', swamp: 'venom', cave: 'stone',
  mine: 'ember', mountain: 'frost', citadel: 'arcane', wastes: 'gunmetal',
  ruins: 'gold', dungeon: 'iron', tower: 'cyan', arena: 'ember', castle: 'blood',
};
