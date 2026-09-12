/* bossseam.mjs — the boss art claim, measured across the seam.
 *
 * bosses.js (staging) and bossart.js (theme) were authored in parallel against
 * an agreed interface. This harness exists because that is exactly the shape of
 * work where both halves pass their own tests and the JOIN is never exercised:
 * every number below is taken over the wired pair, off a real raster, for all
 * thirty-two creatures rather than the fifteen archetypes.
 *
 * It answers the four claims in the brief, in order, and one more the brief
 * leaves unstated and cares about most:
 *
 *   0. SAME CREATURE. Map form vs battle form, both normalised into one box.
 *   1. THEMATIC, AND NOT A RECOLOUR. An element must change the SHAPE. Two
 *      creatures on one body in two elements must not be one drawing twice.
 *   2. EPIC AT MAP SCALE. Bigger and heavier-outlined than a regional mob.
 *   3. FIFTEEN COLOURS, from rendered pixels, worst frame named.
 *   4. DETERMINISM, and no allocation once warm.
 */
import { installRaster, RASTER, colourCount, frameHash, pixelDiff, silhouetteDiff } from './raster.mjs';
installRaster();
const B = await import('../../web/js/bosses.js');
const A = await import('../../web/js/bossart.js');
const S = await import('../../web/js/sprites.js');
let M = null; try { M = await import('../../web/js/monsterart.js'); } catch { /* optional */ }

const pad = (s, n) => String(s).padEnd(n);
const fail = [];
const warn = [];

/* Thirty-two creatures: world.BOSSES, hunters.APEXES, world.FINAL_TRIAL. */
const BOSSES = [
  ['hash_titan', '#e8a33d'], ['three_sum_hydra', '#4fb783'], ['window_wraith', '#7f6ad6'],
  ['twin_behemoth', '#c4553f'], ['matrix_golem', '#8a8f9c'], ['tree_dragon', '#3f9c5a'],
  ['path_sum_ent', '#6b8f3f'], ['graph_necromancer', '#6a4f8f'], ['rolling_titan', '#3f7f9c'],
  ['editor_automaton', '#b0763f'], ['complexity_wyrm', '#3f6f9c'], ['serialization_lich', '#8f3f6f'],
  ['bug_demon', '#c43f4f'], ['the_interviewer', '#d8d8e0'],
];
const APEXES = [
  ['margin_walker', '#c8c4d6'], ['thresher', '#b9a86a'], ['storm_ordinal', '#f2dc6a'],
  ['sporecrown', '#8fd07a'], ['zeroth_weight', '#bf8f4f'], ['fenlight', '#7f9a5a'],
  ['rimewarden', '#7ec8ff'], ['cinder_phoenix', '#e06a3c'], ['fourth_orientation', '#8a8f9c'],
  ['unreturning', '#6a4f8f'], ['bough_stalker', '#6b8f3f'], ['lattice_stag', '#9a8220'],
  ['relighter', '#e0b44a'], ['slagmother', '#c43f4f'], ['the_doubling', '#7ec8ff'],
  ['sand_champion', '#e8c37d'], ['the_unnamed', '#4a4458'],
];
const FINAL = [['the_last_interpreter', '#3f7f5a']];
const ALL = BOSSES.concat(APEXES).concat(FINAL);

/* ---------- shape normalisation ---------- */
function bbox(cv) {
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) {
    if (cv.data[(y * cv.width + x) * 4 + 3] === 0) continue;
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  return x1 < 0 ? null : { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}
function shapeAt(cv, n = 24, thresh = 0.45) {
  const bb = bbox(cv); const out = new Uint8Array(n * n);
  if (!bb) return out;
  for (let ry = 0; ry < n; ry++) for (let rx = 0; rx < n; rx++) {
    const sx0 = bb.x + (bb.w * rx) / n, sx1 = bb.x + (bb.w * (rx + 1)) / n;
    const sy0 = bb.y + (bb.h * ry) / n, sy1 = bb.y + (bb.h * (ry + 1)) / n;
    let on = 0, tot = 0;
    for (let y = Math.floor(sy0); y < Math.ceil(sy1); y++)
      for (let x = Math.floor(sx0); x < Math.ceil(sx1); x++) {
        if (x < 0 || y < 0 || x >= cv.width || y >= cv.height) continue;
        tot++; if (cv.data[(y * cv.width + x) * 4 + 3] > 0) on++;
      }
    if (tot && on / tot >= thresh) out[ry * n + rx] = 1;
  }
  return out;
}
/* Intersection over union, which two mostly-empty boxes cannot inflate by
 * agreeing about their empty corners. */
const iou = (a, b) => {
  let i = 0, u = 0;
  for (let k = 0; k < a.length; k++) { if (a[k] && b[k]) i++; if (a[k] || b[k]) u++; }
  return u ? (100 * i) / u : 100;
};

/* ================= 0. SAME CREATURE, BOTH SCALES ================= */
console.log('0. SAME CREATURE, BOTH SCALES  — map vs battle, normalised into one 24x24 box\n');
console.log(pad('creature', 22), pad('kind', 6), pad('body', 12), pad('element', 10), pad('map', 8), pad('battle', 8), 'IoU%');
const FLOOR = 70;
const rows = [];
for (const [id, colour] of ALL) {
  const kind = BOSSES.some(r => r[0] === id) ? 'boss' : (id === 'the_last_interpreter' ? 'final' : 'apex');
  const battle = B.bossSprite(id, colour, 0);
  const map = B.bossMapSprite(id, colour, 0);
  const v = +iou(shapeAt(battle), shapeAt(map)).toFixed(1);
  rows.push({ id, kind, v, art: B.resolveBoss(id), el: B.bossElement(id) || 'NEUTRAL' });
  console.log(pad(id, 22), pad(kind, 6), pad(B.resolveBoss(id), 12), pad(B.bossElement(id) || 'NEUTRAL', 10),
    pad(map.width + 'x' + map.height, 8), pad(battle.width + 'x' + battle.height, 8), v);
  if (v < FLOOR) fail.push(`${id}: map/battle IoU ${v}% is below the ${FLOOR}% floor — the two forms are not the same creature`);
}
const vals = rows.map(r => r.v);
console.log(`\nmean IoU ${(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)}%   worst ${Math.min(...vals)}% (${rows.find(r => r.v === Math.min(...vals)).id})   floor ${FLOOR}%`);

/* ================= 1. THEMATIC, MEASURED ================= */
console.log('\n\n1. THEMATIC — does the element change the SHAPE, or only the hue?\n');
console.log('   One body, every element, against that body with no element at all.');
console.log('   silh = silhouette cells changed. A recolour scores zero here.\n');
console.log(pad('body', 12), ['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID'].map(e => pad(e, 11)).join(''));
const ELS = ['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID'];
let zeroGeom = 0;
for (const k of B.BOSS_ARCHETYPES) {
  const bare = B.bossSprite(k, '#8a8f9c', 0, { element: 'NEUTRAL' });
  const cells = ELS.map(e => {
    const cv = B.bossSprite(k, '#8a8f9c', 0, { element: e });
    const sd = silhouetteDiff(bare, cv), pd = pixelDiff(bare, cv);
    if (sd === 0) { zeroGeom++; fail.push(`${k}/${e}: element changed ${pd} pixels and 0 silhouette cells — that is a recolour`); }
    return pad(`${sd}/${pd}`, 11);
  });
  console.log(pad(k, 12), cells.join(''));
}
console.log(`\n   elements that moved no geometry: ${zeroGeom} (must be 0)`);
console.log('   verbs: FIRE sheds  COLD accretes  POISON sags  BRUTE chips  LIGHTNING spans  VOID subtracts');

/* Palette separation, not just hue: distinct rendered colours between a fire
 * creature and a cold one on the same body. */
console.log('\n   PALETTE — rendered colours a fire body and a cold body do NOT share:');
console.log('  ', pad('body', 12), pad('fire cols', 10), pad('cold cols', 10), pad('shared', 8), 'disjoint');
for (const k of B.BOSS_ARCHETYPES.slice(0, 6)) {
  const setOf = (cv) => { const s = new Set(); for (let i = 0; i < cv.data.length; i += 4) if (cv.data[i + 3]) s.add((cv.data[i] << 16) | (cv.data[i + 1] << 8) | cv.data[i + 2]); return s; };
  const f = setOf(B.bossSprite(k, '#8a8f9c', 0, { element: 'FIRE' }));
  const c = setOf(B.bossSprite(k, '#8a8f9c', 0, { element: 'COLD' }));
  let sh = 0; for (const v of f) if (c.has(v)) sh++;
  console.log('  ', pad(k, 12), pad(f.size, 10), pad(c.size, 10), pad(sh, 8), (f.size + c.size - 2 * sh));
}

/* Every pair of creatures sharing a body must still be two animals. */
console.log('\n   CLONES — creatures sharing an archetype, silhouette-compared:');
const byArt = new Map();
for (const [id, colour] of ALL) {
  const a = B.resolveBoss(id);
  if (!byArt.has(a)) byArt.set(a, []);
  byArt.get(a).push([id, colour]);
}
let clones = 0, pairs = 0;
for (const [art, members] of byArt) {
  if (members.length < 2) continue;
  for (let i = 0; i < members.length; i++) for (let j = i + 1; j < members.length; j++) {
    const a = B.bossSprite(members[i][0], members[i][1], 0);
    const b = B.bossSprite(members[j][0], members[j][1], 0);
    const sd = silhouetteDiff(a, b); pairs++;
    const tag = sd === 0 ? '  <-- IDENTICAL' : '';
    if (sd === 0) { clones++; fail.push(`${members[i][0]} and ${members[j][0]} share the ${art} body and are byte-identical in silhouette`); }
    console.log('  ', pad(art, 12), pad(members[i][0], 20), pad(members[j][0], 20), pad(sd + ' cells', 11) + tag);
  }
}
console.log(`   ${pairs} pairs share a body; ${clones} are the same creature twice (must be 0)`);

/* ================= 2. EPIC AT MAP SCALE ================= */
console.log('\n\n2. EPIC AT MAP SCALE — the marker against an ordinary monster\n');
const mobs = [];
if (M) {
  for (const n of ['slime', 'rat', 'goblin', 'bat', 'wolf', 'skeleton', 'imp', 'spider']) {
    try { const cv = M.monsterFrame(n, 0); if (cv && cv.width) mobs.push([n, cv]); } catch { /* skip */ }
  }
}
if (!mobs.length) {
  for (const n of ['slime', 'rat', 'goblin', 'bat']) {
    try { const cv = S.enemySprite(n, 0, 0); if (cv && cv.width) mobs.push([n, cv]); } catch { /* skip */ }
  }
}
const mass = (cv) => { let n = 0; for (let i = 3; i < cv.data.length; i += 4) if (cv.data[i]) n++; return n; };
const mobH = mobs.length ? Math.max(...mobs.map(m => m[1].height)) : 24;
const mobMass = mobs.length ? Math.round(mobs.reduce((a, m) => a + mass(m[1]), 0) / mobs.length) : 279;
console.log(`   reference: ${mobs.length ? mobs.map(m => m[0]).join(', ') : '(monsterart unavailable — sprites.enemySprite defaults)'}`);
console.log(`   ordinary monster: ${mobH}px tall, ${mobMass}px of painted mass on average`);
let smallest = 1e9, lightest = 1e9;
for (const [id, colour] of ALL) {
  const cv = B.bossMapSprite(id, colour, 0);
  smallest = Math.min(smallest, cv.height);
  lightest = Math.min(lightest, mass(cv));
}
console.log(`   boss marker:      ${smallest}px tall at its smallest, ${lightest}px of mass at its lightest`);
console.log(`   ratio:            ${(smallest / mobH).toFixed(2)}x the height, ${(lightest / mobMass).toFixed(2)}x the mass`);
if (smallest <= mobH) fail.push(`boss marker ${smallest}px is not taller than a ${mobH}px monster`);
if (lightest <= mobMass) fail.push(`lightest boss marker ${lightest}px does not outweigh a ${mobMass}px monster`);
/* And the outline, which is the tell a player reads before any interior.
 *
 * Measured as THICKNESS, not darkness. A boss's edge is deliberately not dark:
 * applyRim and the contre-jour pass light it, which is the whole look. What
 * separates a boss marker from a mob is that the dark ring is TWO pixels deep
 * where a mob's is one, so the question is how much of ring 2 — one step inside
 * the silhouette boundary — is still outline tone.
 *
 * "Outline tone" is read off each sprite rather than assumed: the darkest
 * colours it actually paints, taking enough of them to cover the edge. That way
 * a mob and a boss are judged by the same rule without either palette being
 * hard-coded here. */
function rgbAt(cv, x, y) {
  if (x < 0 || y < 0 || x >= cv.width || y >= cv.height) return -1;
  const i = (y * cv.width + x) * 4;
  return cv.data[i + 3] ? ((cv.data[i] << 16) | (cv.data[i + 1] << 8) | cv.data[i + 2]) : -1;
}
/* Ring 1 is every opaque pixel touching transparent. Ring 2 is every opaque
 * pixel touching ring 1 and not in it. A one-pixel border leaves ring 2 painted
 * in body tones; a two-pixel border leaves it painted in outline tones, so the
 * share of ring 2 still in an outline tone IS the heavier outline, measured.
 *
 * The outline tones are taken to be the three that dominate ring 1 of the
 * sprite in hand, rather than read out of anybody's palette — that way a mob
 * and a boss are judged by one rule and neither file's colour names have to be
 * known here. */
function rings(cv) {
  const r1 = [], r2 = [];
  const isEdge = (x, y) => rgbAt(cv, x, y) >= 0 && (
    rgbAt(cv, x - 1, y) < 0 || rgbAt(cv, x + 1, y) < 0
    || rgbAt(cv, x, y - 1) < 0 || rgbAt(cv, x, y + 1) < 0);
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) if (isEdge(x, y)) r1.push([x, y]);
  const inR1 = new Set(r1.map(([x, y]) => y * cv.width + x));
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) {
    if (rgbAt(cv, x, y) < 0 || inR1.has(y * cv.width + x)) continue;
    if (inR1.has(y * cv.width + x - 1) || inR1.has(y * cv.width + x + 1)
      || inR1.has((y - 1) * cv.width + x) || inR1.has((y + 1) * cv.width + x)) r2.push([x, y]);
  }
  /* "Outline tone" is near-black, in absolute terms, because that is what the
   * bible asks for and what both palettes actually emit: sprites.enemyPalette
   * puts a mob's outline at luminance 8 and bossPalette puts a boss's at 35.
   * An absolute threshold is the only definition under which the two files can
   * be compared at all without either one's colour names leaking in here. */
  const dark = (x, y) => {
    const v = rgbAt(cv, x, y);
    return v >= 0 && ((((v >> 16) & 255) + ((v >> 8) & 255) + (v & 255)) / 3) < 60;
  };
  const pct = (list) => list.length ? Math.round((list.filter(([x, y]) => dark(x, y)).length * 100) / list.length) : 0;
  return [pct(r1), pct(r2), r1.length, r2.length];
}
const mapR = ALL.map(([id, c]) => rings(B.bossMapSprite(id, c, 0)));
const mapR1 = Math.round(mapR.reduce((a, r) => a + r[0], 0) / mapR.length);
const mapR2 = Math.round(mapR.reduce((a, r) => a + r[1], 0) / mapR.length);
const mobR = mobs.map(m => rings(m[1]));
const mobR1 = mobR.length ? Math.round(mobR.reduce((a, r) => a + r[0], 0) / mobR.length) : 0;
const mobR2 = mobR.length ? Math.round(mobR.reduce((a, r) => a + r[1], 0) / mobR.length) : 0;
console.log(`   outline ring 1 (the boundary itself):   boss marker ${mapR1}%, ordinary monster ${mobR1}%`);
console.log(`   outline ring 2 (one pixel inside it):   boss marker ${mapR2}%, ordinary monster ${mobR2}%   <- the boss tell`);
if (mapR2 <= mobR2) fail.push(`boss marker second outline ring ${mapR2}% is not heavier than a monster's ${mobR2}%`);

/* ================= 3. FIFTEEN COLOURS ================= */
console.log('\n\n3. FIFTEEN COLOURS — counted from rendered pixels, every creature x frame x phase x form\n');
const CAP = 15;
let worst = { n: -1 };
let counted = 0, over = 0;
for (const [id, colour] of ALL) {
  for (let ph = 0; ph < 3; ph++) {
    for (let f = 0; f < B.BOSS_FRAME_COUNT; f++) {
      for (const beat of (f <= 1 ? [0, 1, 2, 3, 4, 5] : [0])) {
        const cv = B.bossSprite(id, colour, f, { phase: ph, beat });
        const n = colourCount(cv); counted++;
        if (n > CAP) { over++; fail.push(`${id} battle f${f} b${beat} p${ph}: ${n} colours`); }
        if (n > worst.n) worst = { n, what: `${id} battle frame ${B.BOSS_FRAME_NAMES[f]} beat ${beat} phase ${ph}` };
      }
      if (f > 1) continue;
      const mv = B.bossMapSprite(id, colour, f, { phase: ph });
      const mn = colourCount(mv); counted++;
      if (mn > CAP) { over++; fail.push(`${id} map f${f} p${ph}: ${mn} colours`); }
      if (mn > worst.n) worst = { n: mn, what: `${id} map frame ${B.BOSS_FRAME_NAMES[f]} phase ${ph}` };
    }
  }
}
console.log(`   ${counted} rendered frames counted, every creature at the element it actually fights as`);
console.log(`   worst frame: ${worst.n} of ${CAP} colours — ${worst.what}`);
console.log(`   frames over budget: ${over}`);

/* The same sweep again with opts.element FORCED to each of the seven, which is
 * a supported override (the forge preview shows a creature in another
 * element's light). No shipped creature is ever drawn this way, so this is a
 * warning rather than a failure — but it is measured, because "the roster is
 * clean" and "the function is clean" are different claims and it is worth
 * knowing which one is being made. */
let xOver = 0, xWorst = { n: -1 };
const xWho = new Set();
for (const [id, colour] of ALL) {
  for (const el of ['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID', 'NEUTRAL']) {
    if (el === (B.bossElement(id) || 'NEUTRAL')) continue;
    for (let ph = 0; ph < 3; ph++) for (let f = 0; f < B.BOSS_FRAME_COUNT; f++) {
      const n = colourCount(B.bossSprite(id, colour, f, { phase: ph, element: el }));
      if (n > CAP) { xOver++; xWho.add(`${id}/${el}`); }
      if (n > xWorst.n) xWorst = { n, what: `${id} forced to ${el} phase ${ph}` };
    }
  }
}
console.log(`   under a FORCED foreign element: worst ${xWorst.n} — ${xWorst.what}, ${xOver} frames over`);
if (xOver) {
  warn.push(`${xOver} frames exceed ${CAP} colours only when opts.element forces an element the creature never fights as`
    + ` (${[...xWho].slice(0, 4).join(', ')}${xWho.size > 4 ? `, +${xWho.size - 4} more` : ''}).`
    + ` No shipped creature renders this way; a forge preview would.`);
}

/* ================= 4. DETERMINISM AND ALLOCATION ================= */
console.log('\n\n4. DETERMINISM AND ALLOCATION\n');
let drift = 0;
const first = new Map();
for (const [id, colour] of ALL) for (let f = 0; f < 5; f++)
  first.set(`${id}|${f}`, frameHash(B.bossSprite(id, colour, f)) + '/' + frameHash(B.bossMapSprite(id, colour, Math.min(f, 1))));
B.clearBossCache(); A.clearBossArtCache();
for (const [id, colour] of ALL) for (let f = 0; f < 5; f++) {
  const h = frameHash(B.bossSprite(id, colour, f)) + '/' + frameHash(B.bossMapSprite(id, colour, Math.min(f, 1)));
  if (h !== first.get(`${id}|${f}`)) { drift++; fail.push(`${id} frame ${f} is not deterministic across a cache clear`); }
}
console.log(`   ${first.size} frame pairs rebuilt from a cleared cache; ${drift} differed (must be 0)`);

B.clearBossCache(); A.clearBossArtCache();
RASTER.counting = true; RASTER.canvases = 0;
let n = 0;
for (const [id, colour] of ALL) { n += B.warmBoss(id, colour, 0); n += B.warmBossMap(id, colour, 0); }
const cold = RASTER.canvases;
RASTER.canvases = 0;
const ctx = (globalThis.document.createElement('canvas')).getContext('2d');
/* One lap to warm everything a draw touches that warmBoss does not — the
 * ground shadows are cached by size in sprites.js and there is one size per
 * creature per form — then a second, identical lap that must allocate nothing.
 * Measuring only the second lap is the difference between "this render loop
 * leaks" and "this render loop had a cold cache once". */
for (let lap = 0; lap < 2; lap++) {
  RASTER.canvases = 0;
  for (let t = 0; t < 1800; t += 16) {
    const [id, colour] = ALL[(t / 16 | 0) % ALL.length];
    B.drawBoss(ctx, id, 200, 200, { time: t, colour, scale: B.BOSS_STAGE_SCALE });
    B.drawBoss(ctx, id, 60, 60, { time: t, colour, map: true });
  }
}
const steady = RASTER.canvases;
RASTER.counting = false;
console.log(`   warming all ${ALL.length} creatures at phase 0: ${n} sprites, ${cold} canvases allocated`);
console.log(`   then ${1800 / 16 * 2} draws per lap, second lap: ${steady} canvases allocated`);
if (steady > 0) warn.push(`${steady} canvases allocated during steady-state drawing`);

/* ================= 5. SIGNATURES AND FALLBACK ================= */
console.log('\n\n5. SIGNATURES AND FALLBACK\n');
/* Exactly what overworld.js, fx.js and apex.js reach for. */
const CALLS = [
  ['drawBoss', () => B.drawBoss(ctx, 'titan', 10, 10, { frame: 1, flash: 0.5, scale: B.BOSS_STAGE_SCALE })],
  ['bossSprite', () => B.bossSprite('titan', '#c43f4f', 0)],
  ['bossMapSprite', () => B.bossMapSprite('titan', '#c43f4f', 0)],
  ['bossFrameAt', () => B.bossFrameAt('titan', 'idle', 500)],
  ['bossPose', () => B.bossPose('titan', 500, 7)],
  ['bossMotion', () => B.bossMotion('titan')],
  ['bossInfo', () => B.bossInfo('titan')],
  ['bossSize', () => B.bossSize('titan')],
  ['bossMapSize', () => B.bossMapSize('titan')],
  ['bossArtKey', () => B.bossArtKey({ id: 'hash_titan', sprite: 'titan' })],
  ['resolveBoss', () => B.resolveBoss('titan')],
  ['bossElement', () => B.bossElement('titan')],
  ['bossPalette', () => B.bossPalette('#c43f4f', '#fff', 0, 'FIRE')],
  ['bossLighting', () => B.bossLighting('titan', '#c43f4f')],
  ['bossEntrance', () => B.bossEntrance('titan', 0.5)],
  ['drawBossEntrance', () => B.drawBossEntrance(ctx, 'titan', 10, 10, 0.5)],
  ['bossFrames', () => B.bossFrames('titan', '#c43f4f')],
  ['warmBoss', () => B.warmBoss('titan', '#c43f4f', 0)],
  ['warmBossMap', () => B.warmBossMap('titan', '#c43f4f', 0)],
  ['bossStageScale', () => B.bossStageScale('titan')],
  ['bossPhase', () => B.bossPhase('cracked')],
  ['frameIndex', () => B.frameIndex('windup')],
  ['phaseIndex', () => B.phaseIndex('core')],
  ['clearBossCache', () => B.clearBossCache()],
];
const NAMES = ['BOSS_ART_VERSION', 'BOSS_H', 'BOSS_W', 'BOSS_WIDE_W', 'BOSS_MAP_H', 'BOSS_MAP_W',
  'BOSS_MAP_WIDE_W', 'BOSS_MAP_RATIO', 'BOSS_GLYPHS', 'BOSS_FRAME', 'BOSS_FRAME_NAMES',
  'BOSS_FRAME_COUNT', 'BOSS_FRAME_TABLE', 'BOSS_PHASE', 'BOSS_PHASE_NAMES', 'BOSS_PHASE_COUNT',
  'BOSS_BEATS', 'BOSS_ARCHETYPES', 'BOSS_SHAPE_FOR', 'BOSS_ART_FOR_ID', 'BOSS_ELEMENT',
  'BOSS_MOTION', 'BOSS_STAGE_SCALE', 'BOSS_PALETTES', 'BOSS_ENTRANCE_MS', 'BOSS_ENTRANCE_HOLD_MS',
  'BOSS_TAUNT_AT_MS', 'BOSS_ENTRANCE_BEATS', 'BOSS_ENTRANCE_RIM_MS'];
let bad = 0;
for (const nm of NAMES) if (B[nm] === undefined) { bad++; fail.push(`export ${nm} is gone`); }
for (const [nm, fn] of CALLS) {
  try { const r = fn(); if (r === undefined && nm !== 'clearBossCache' && nm !== 'drawBoss' && nm !== 'drawBossEntrance') { bad++; fail.push(`${nm}() returned undefined`); } }
  catch (e) { bad++; fail.push(`${nm}() threw: ${e.message}`); }
}
console.log(`   ${NAMES.length} exported names and ${CALLS.length} call shapes checked; ${bad} broken`);
/* BOSS_MOTION is read by key from fx.js and battlescene.js. */
let motionBad = 0;
for (const k of B.BOSS_ARCHETYPES) {
  const m = B.BOSS_MOTION[k];
  for (const f of ['key', 'name', 'bob', 'sway', 'period', 'telegraph', 'scale', 'floats'])
    if (m === undefined || m[f] === undefined) { motionBad++; fail.push(`BOSS_MOTION.${k}.${f} missing`); }
}
console.log(`   BOSS_MOTION: ${B.BOSS_ARCHETYPES.length} archetypes, ${motionBad} missing fields`);

console.log('\n   unknown ids, both forms:');
for (const junk of ['__no_such_boss__', '', null, undefined, 0, 'apex_unnamed', 'titan ', '../../etc']) {
  try {
    const a = B.bossSprite(junk, '#888', 0), m = B.bossMapSprite(junk, '#888', 0);
    const inf = B.bossInfo(junk);
    console.log('  ', pad(JSON.stringify(junk), 22), 'battle', pad(a.width + 'x' + a.height, 8),
      'map', pad(m.width + 'x' + m.height, 8), '->', B.resolveBoss(junk), `(${inf && inf.name})`);
  } catch (e) { fail.push(`unknown id ${JSON.stringify(junk)} threw: ${e.message}`); console.log('  ', pad(JSON.stringify(junk), 22), 'THROW', e.message); }
}

/* bossart's own opinion of the join. */
const sc = A.bossArtSelfCheck(B.BOSS_GLYPHS);
console.log(`\n   bossart self-check against BOSS_GLYPHS: ${sc.ok ? 'ok' : JSON.stringify(sc.problems)}`);
if (!sc.ok) fail.push(`bossart self-check: ${sc.problems.join('; ')}`);

console.log('\n================ VERDICT ================');
for (const w of warn) console.log('WARN', w);
if (!fail.length) console.log('no failures');
else { console.log(`${fail.length} failures`); for (const f of fail.slice(0, 40)) console.log('  -', f); }
process.exit(fail.length ? 1 : 0);
