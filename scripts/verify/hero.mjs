/* The hero, measured in pixels.
 *
 * Every other harness in here asks whether the art code SURVIVES — no throws,
 * no null images, no allocation in a draw loop. This one asks whether the art
 * is TRUE, and it only exists because the equipment claim cannot be checked any
 * other way. "The gear shows on the sprite" is a statement about what a player
 * can see, and a recolour satisfies every structural test ever written while
 * failing the only thing anybody asked for. So the checks here are:
 *
 *   1. SHAPE.  Bare hero, then each armour piece alone at each tier, then the
 *      full kit. Each must change the rendered frame, and each must change the
 *      ALPHA MASK — the outline with colour thrown away. A piece that moves
 *      pixel colours and leaves the mask alone is a recolour and is reported as
 *      a failure, not as a pass with a small number.
 *   2. BUDGET. Fifteen colours plus transparent, counted off the raster rather
 *      than off the palette dict, swept over every piece, tier, weapon, emote,
 *      facing, pose and frame.
 *   3. DETERMINISM. The same look renders byte-identically, from a cold cache
 *      and from a warm one, in any build order.
 *   4. SURFACE. Every export the rest of the game calls still exists, and the
 *      armour vocabulary still agrees with gauntlet/items.py.
 *   5. STEADY STATE. A player standing still in fixed kit allocates nothing.
 */

import { installRaster, RASTER, pixelDiff, silhouetteDiff, colourCount, frameHash } from './raster.mjs';
installRaster();

const S = await import('../../web/js/sprites.js');

/* ---------------- the server's vocabulary ----------------
 *
 * Mirrors gauntlet/items.py ARMOR_TIERS: the six pieces, five integrity floors
 * each, and the colours the server actually ships for them. Checked in rather
 * than shelled out for, exactly like vocab.json, and asserted against
 * sprites.js's own view of the same vocabulary below — so the two drifting
 * apart is itself a test failure. */
const PIECES = ['helmet', 'chestplate', 'gauntlets', 'boots', 'shield', 'legendary'];
const AT = [0, 25, 50, 75, 100];
const TIERS = {
  helmet: [{ metal: '#4a4450', trim: '#3c3846' }, { metal: '#6b6470', trim: '#7a6a4a' },
           { metal: '#8a8494', trim: '#a08a52' }, { metal: '#b0aabd', trim: '#c9a05a' },
           { metal: '#e2dcf0', trim: '#e8c37d' }],
  chestplate: [{ tunic: '#4e4258', metal: '#4a4450' }, { tunic: '#5d5068', metal: '#6b6470' },
               { tunic: '#6e5f7d', metal: '#8a8494' }, { tunic: '#7d6b90', metal: '#b0aabd' },
               { tunic: '#9a7fd0', metal: '#e2dcf0' }],
  gauntlets: [{ metal: '#5a4f46' }, { metal: '#75675a' }, { metal: '#96887a' },
              { metal: '#b8a893' }, { metal: '#e6d2ae' }],
  boots: [{ boot: '#3e3228' }, { boot: '#4e3f31' }, { boot: '#5f4c3a' },
          { boot: '#715b45' }, { boot: '#8c7050' }],
  shield: [{ metal: '#4a4450', trim: '#3c3846' }, { metal: '#6b6470', trim: '#5a4f38' },
           { metal: '#8a8494', trim: '#7f6a44' }, { metal: '#b0aabd', trim: '#a08a52' },
           { metal: '#e2dcf0', trim: '#e8c37d' }],
  legendary: [{ cloak: '#2f2a3c', metal: '#4a4450', trim: '#3c3846' },
              { cloak: '#39304a', metal: '#6b6470', trim: '#5a4f38' },
              { cloak: '#443a5c', metal: '#8a8494', trim: '#7f6a44' },
              { cloak: '#52456e', metal: '#b0aabd', trim: '#a08a52' },
              { cloak: '#6a4fb0', metal: '#e2dcf0', trim: '#e8c37d' }],
};
/* hero_look() grades the blade by rarity on its own six-rung table. */
const WEAPON_RUNGS = [
  { name: 'Rusted', metal: '#7a6f5a', trim: '#4a4236' },
  { name: 'Honed', metal: '#9a9384', trim: '#6a5f46' },
  { name: 'Tempered', metal: '#b8b6c4', trim: '#8a7a52' },
  { name: 'Runed', metal: '#cfd2e8', trim: '#a89aff' },
  { name: 'Legendary', metal: '#eadfae', trim: '#e8c37d' },
  { name: 'Mythic', metal: '#ffd9df', trim: '#ff6a7a' },
];

/* The shape hero_look() ships: worst piece first so the Legendary Plate wins,
 * a `_pieces` list of {piece, at} and a `_weapon` with its own rung. */
function look(worn, weapon = 'sword', rung = 0, emote = 'neutral') {
  const w = WEAPON_RUNGS[rung];
  const out = { weapon, emote, metal: w.metal, _weapon: { key: weapon, ...w } };
  const pieces = [];
  for (const piece of ['boots', 'gauntlets', 'shield', 'helmet', 'chestplate', 'legendary']) {
    const t = worn[piece];
    if (t === undefined || t < 0) continue;
    pieces.push({ piece, at: AT[t] });
    if (piece === 'legendary' && AT[t] <= 0) continue;
    Object.assign(out, TIERS[piece][t]);
  }
  out.metal = w.metal;                 // the blade sets the metal ramp, as items.py does
  out._pieces = pieces.sort((a, b) => PIECES.indexOf(a.piece) - PIECES.indexOf(b.piece));
  return out;
}
const BARE = look({});

/* Every frame the game can actually put on screen for one look. */
const VIEWS = [];
for (const facing of ['down', 'up', 'left', 'right']) {
  for (const pose of ['walk', 'idle', 'cast']) {
    for (const frame of (pose === 'cast' ? [0] : [0, 1, 2, 3])) VIEWS.push([facing, frame, pose]);
  }
}
const render = (o) => VIEWS.map(v => S.heroFrame(v[0], v[1], o, v[2]));

const fail = [];
const rows = [];

/* ---------------- 1. every piece changes the sprite AND the silhouette ------- */

const bareFrames = render(BARE);

function measure(label, o) {
  const got = render(o);
  let pix = 0, sil = 0, minPix = Infinity, minSil = Infinity, worstPix = '', worstSil = '';
  for (let i = 0; i < got.length; i++) {
    const p = pixelDiff(bareFrames[i], got[i]), s = silhouetteDiff(bareFrames[i], got[i]);
    pix += p; sil += s;
    if (p < minPix) { minPix = p; worstPix = VIEWS[i].join('/'); }
    if (s < minSil) { minSil = s; worstSil = VIEWS[i].join('/'); }
  }
  const row = { label, pix, sil, minPix, minSil, worstPix, worstSil };
  rows.push(row);
  if (pix === 0) fail.push(`${label}: changes NOTHING — the piece is not drawn at all`);
  if (sil === 0) fail.push(`${label}: RECOLOUR ONLY — no pixel of the outline moves`);
  if (minPix === 0) fail.push(`${label}: invisible in ${worstPix}`);
  if (minSil === 0) fail.push(`${label}: recolour only in ${worstSil}`);
  return row;
}

for (const piece of PIECES) {
  for (let t = 0; t < AT.length; t++) {
    // The Legendary Plate at zero is unbuilt, not damaged: hero_look() refuses
    // to paint it and so does heroArmor(). Nothing to measure.
    if (piece === 'legendary' && t === 0) continue;
    measure(`${piece}@${t}`, look({ [piece]: t }));
  }
}
const kitted = {}; for (const p of PIECES) kitted[p] = 4;
measure('FULL KIT', look(kitted, 'relic', 5));
const wrecked = {}; for (const p of PIECES) wrecked[p] = 0;
measure('FULL KIT, wrecked', look(wrecked));

/* Every piece must also be told apart from the piece one rung below it, or a
 * repair is a number in a menu and nothing on the character. */
for (const piece of PIECES) {
  const start = piece === 'legendary' ? 1 : 0;
  for (let t = start + 1; t < AT.length; t++) {
    const a = render(look({ [piece]: t - 1 })), b = render(look({ [piece]: t }));
    let sil = 0, pix = 0;
    for (let i = 0; i < a.length; i++) { sil += silhouetteDiff(a[i], b[i]); pix += pixelDiff(a[i], b[i]); }
    if (pix === 0) fail.push(`${piece} tier ${t - 1} -> ${t}: identical frames, the upgrade is invisible`);
    else if (sil === 0) fail.push(`${piece} tier ${t - 1} -> ${t}: recolour only, the upgrade never changes the outline`);
  }
}

/* ---------------- 2. fifteen colours, counted off the raster ---------------- */

let worst = { n: 0 };
let sampled = 0;
const lattice = [];
for (let i = 0; i < PIECES.length; i++) {
  for (let t = -1; t < AT.length; t++) { const a = {}; PIECES.forEach((p, j) => { a[p] = j === i ? t : -1; }); lattice.push(a); }
}
for (let t = -1; t < AT.length; t++) { const a = {}; for (const p of PIECES) a[p] = t; lattice.push(a); }
// A deterministic spread of mixed kit: a real save is never uniform.
for (let k = 0; k < 120; k++) {
  let h = Math.imul(k + 1, 2654435761) >>> 0;
  const a = {};
  for (const p of PIECES) { h = (Math.imul(h, 1664525) + 1013904223) >>> 0; a[p] = (h % (AT.length + 1)) - 1; }
  lattice.push(a);
}
const WEAPONS = S.HERO_WEAPON_KEYS.concat([null]);
for (const worn of lattice) {
  for (let wi = 0; wi < WEAPONS.length; wi++) {
    const rung = wi % WEAPON_RUNGS.length;
    for (const emote of [S.EMOTE_KEYS[0], S.EMOTE_KEYS[3], S.EMOTE_KEYS[6]]) {
      const o = look(worn, WEAPONS[wi], rung, emote);
      for (const v of VIEWS) {
        const n = colourCount(S.heroFrame(v[0], v[1], o, v[2]));
        sampled++;
        if (n > worst.n) {
          worst = { n, view: v.join('/'), weapon: String(WEAPONS[wi]), rung: WEAPON_RUNGS[rung].name,
                    emote, wearing: PIECES.map(p => `${p}:${worn[p] < 0 ? '-' : worn[p]}`).join(' ') };
        }
      }
    }
  }
}
if (worst.n > 15) fail.push(`colour budget blown: ${worst.n} in ${worst.view} wearing ${worst.wearing}`);

/* ---------------- 3. determinism ---------------- */

const detLooks = [BARE, look(kitted, 'relic', 5), look(wrecked), look({ helmet: 4, boots: 2 }, 'axe', 3)];
const sig = (o) => VIEWS.map(v => frameHash(S.heroFrame(v[0], v[1], o, v[2]))).join(',');
const first = detLooks.map(sig);
// Again warm.
detLooks.forEach((o, i) => { if (sig(o) !== first[i]) fail.push(`look ${i}: warm cache differs from cold`); });
// Again in the opposite build order, from a cache that has since seen the whole
// sweep above: order of construction must not reach the pixels.
for (let i = detLooks.length - 1; i >= 0; i--) {
  if (sig(detLooks[i]) !== first[i]) fail.push(`look ${i}: differs when built in reverse order`);
}
const detDigest = frameHashList(first);
function frameHashList(list) {
  let h = 2166136261 >>> 0;
  const s = list.join('|');
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0).toString(16);
}

/* ---------------- 4. surface ---------------- */

const REQUIRED = ['ramp', 'shade', 'mix', 'rng', 'hash', 'drawGrid', 'gridSprite', 'composeSprite',
  'normalise', 'shiftRows', 'bobGrid', 'widenRows', 'squashRows', 'applyRim', 'groundShadow',
  'drawGroundShadow', 'sinkRows', 'mergeGrids', 'RIM_LIGHT', 'rimTone', 'rimLowLeft', 'silhouetteAt',
  'HERO_W', 'HERO_H', 'HERO_ARMOR_PIECES', 'HERO_ARMOR_TIERS', 'heroArmor', 'EMOTE_KEYS',
  'EMOTE_ALIAS', 'emoteKey', 'EMOTE_FRAME_COUNT', 'emotePose', 'heroPalette', 'heroFrame',
  'heroSilhouette', 'HERO_WALK_ORDER', 'heroSprites', 'heroEmoteFrames', 'HERO_WEAPON_KEYS',
  'ENEMY_ARCHETYPES', 'ENEMY_SIZE', 'ENEMY_SHAPE_FOR', 'ENEMY_COLOUR', 'FAMILY_COLOUR',
  'ENEMY_MOTION', 'enemyMotion', 'enemyPalette', 'enemySprite', 'BOSS_SIZE', 'BOSS_ARCHETYPES',
  'BOSS_SHAPE_FOR', 'BOSS_MOTION', 'bossMotion', 'bossSprite', 'PORTRAIT_ALIAS', 'PORTRAIT_KEYS',
  'PORTRAIT_SIZE', 'portraitEmote', 'portrait', 'portraitFrames', 'portraitEmotes', 'portraitAt',
  'portraitSilhouette', 'scaleSprite', 'idlePose', 'shadowFor'];
for (const name of REQUIRED) if (S[name] === undefined) fail.push(`export MISSING: sprites.${name}`);

if (S.HERO_ARMOR_PIECES.join(',') !== PIECES.join(',')) {
  fail.push(`armour vocabulary drifted from items.py: ${S.HERO_ARMOR_PIECES.join(',')}`);
}
if (S.HERO_ARMOR_TIERS !== AT.length) fail.push(`tier count drifted: ${S.HERO_ARMOR_TIERS} vs ${AT.length}`);
for (const key of S.HERO_WEAPON_KEYS) {
  if (!S.heroFrame('down', 0, { ...BARE, weapon: key })) fail.push(`weapon ${key} produced no frame`);
}
// Garbage in, a hero out. This runs on the render path of a live game.
for (const bad of [null, undefined, {}, { weapon: '__nope__' }, { _pieces: 'not a list' },
  { _pieces: [{ piece: '__nope__', at: 999 }] }, { armor: { helmet: -5 } }, { emote: '__nope__' }]) {
  try {
    if (!S.heroFrame('sideways', 9, bad, 'flailing')) fail.push(`garbage look produced no frame: ${JSON.stringify(bad)}`);
  } catch (e) { fail.push(`THROW on garbage look ${JSON.stringify(bad)}: ${e.message}`); }
}

/* ---------------- 5. steady state ---------------- */

const kit = look(kitted, 'relic', 5);
S.heroSprites(kit);                       // warm
RASTER.counting = true; RASTER.canvases = 0;
for (let i = 0; i < 240; i++) S.heroSprites(kit);
const warmAllocs = RASTER.canvases;
RASTER.canvases = 0;
// A whole overworld's worth of distinct looks — the player plus the villager
// variants — then the same set again. The second pass must cost nothing.
const session = [BARE, kit, look({ helmet: 2 }), look({ legendary: 4 }),
  ...[0, 1, 2, 3].map(i => ({ ...BARE, cloak: ['#3f6fa8', '#6a4fb0', '#4e4258', '#2f2a3c'][i], weapon: null }))];
for (const o of session) S.heroSprites(o);
const sessionCold = RASTER.canvases;
RASTER.canvases = 0;
for (let r = 0; r < 4; r++) for (const o of session) S.heroSprites(o);
const sessionWarm = RASTER.canvases;
RASTER.counting = false;
if (warmAllocs !== 0) fail.push(`hero cache thrashes: ${warmAllocs} canvases for 240 redraws of one fixed look`);
if (sessionWarm !== 0) fail.push(`hero cache thrashes: ${sessionWarm} canvases re-rendering a settled working set`);

/* ---------------- report ---------------- */

const pad = (s, n) => String(s).padEnd(n);
const lpad = (s, n) => String(s).padStart(n);
console.log('EQUIPMENT, MEASURED AGAINST THE BARE HERO');
console.log(`${pad('piece@tier', 20)}${lpad('px', 8)}${lpad('outline', 9)}${lpad('px/min', 8)}${lpad('out/min', 9)}  thinnest view`);
for (const r of rows) {
  console.log(pad(r.label, 20) + lpad(r.pix, 8) + lpad(r.sil, 9)
    + lpad(r.minPix, 8) + lpad(r.minSil, 9) + '  ' + r.worstSil);
}
console.log(`\n${VIEWS.length} views per look (4 facings x walk 0-3, idle 0-3, cast).`);
console.log('\nCOLOUR BUDGET (counted from the raster, 15 + transparent)');
console.log(`  frames sampled : ${sampled}`);
console.log(`  worst frame    : ${worst.n} colours, ${worst.view}`);
console.log(`  wearing        : ${worst.wearing}`);
console.log(`  holding        : ${worst.weapon} (${worst.rung}), face ${worst.emote}`);
console.log('\nDETERMINISM');
console.log(`  digest over ${detLooks.length} looks x ${VIEWS.length} views: ${detDigest}`);
console.log('\nSTEADY STATE');
console.log(`  240 redraws of one fixed look : ${warmAllocs} canvases`);
console.log(`  ${session.length} looks, cold / then 4 more passes : ${sessionCold} / ${sessionWarm} canvases`);
console.log('\n' + (fail.length ? `FAIL (${fail.length})\n  ` + fail.join('\n  ') : 'PASS — every piece changes the outline, budget held, deterministic.'));
process.exitCode = fail.length ? 1 : 0;
