/* bossforms.mjs — the measurement the boss-art claim rests on.
 *
 * Three claims are made about every boss, and all three are pixel claims, so
 * none of them is asserted here. They are counted off a real raster:
 *
 *   1. ONE CREATURE, TWO SCALES. The map form and the battle form are the same
 *      animal. Measured by normalising both silhouettes into the same box and
 *      comparing them cell for cell. A number below the floor is drift.
 *   2. FIFTEEN COLOURS. Counted from rendered pixels, not from the palette
 *      object: a palette with fifteen entries that a shading pass turns into
 *      sixteen is over budget and a palette dict cannot see that.
 *   3. THE PHASES ARE VISIBLE. Pixels changed, and silhouette cells changed,
 *      between phase 0 and phases 1 and 2. A phase that moves zero pixels is
 *      a number with a health bar attached.
 *
 * Plus the two smaller ones: the map form outweighs a mob, and the parts move
 * independently (frame-to-frame pixel deltas that are not all equal).
 */
import { installRaster, RASTER, colourCount, frameHash } from './raster.mjs';
installRaster();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const B = await import('../../web/js/bosses.js');
const S = await import('../../web/js/sprites.js');

const ARGS = new Set(process.argv.slice(2));
const JSONOUT = ARGS.has('--json');

/* ---------- raster helpers ---------- */
function bbox(cv) {
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let y = 0; y < cv.height; y++) {
    for (let x = 0; x < cv.width; x++) {
      if (cv.data[(y * cv.width + x) * 4 + 3] === 0) continue;
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  return x1 < 0 ? null : { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}

/* Coverage downsample into an NxN bitmap, normalised on the bounding box so
 * the comparison is about SHAPE and not about how big the thing was drawn.
 * A destination cell is set when at least `thresh` of the source area under it
 * is opaque — the same rule a human uses reading a sprite from across a room. */
function shapeAt(cv, n = 24, thresh = 0.45) {
  const bb = bbox(cv);
  const out = new Uint8Array(n * n);
  if (!bb) return { bits: out, bbox: null, fill: 0 };
  let fill = 0;
  for (let ry = 0; ry < n; ry++) {
    for (let rx = 0; rx < n; rx++) {
      const sx0 = bb.x + (bb.w * rx) / n, sx1 = bb.x + (bb.w * (rx + 1)) / n;
      const sy0 = bb.y + (bb.h * ry) / n, sy1 = bb.y + (bb.h * (ry + 1)) / n;
      let on = 0, tot = 0;
      for (let y = Math.floor(sy0); y < Math.ceil(sy1); y++) {
        for (let x = Math.floor(sx0); x < Math.ceil(sx1); x++) {
          if (x < 0 || y < 0 || x >= cv.width || y >= cv.height) continue;
          tot++;
          if (cv.data[(y * cv.width + x) * 4 + 3] > 0) on++;
        }
      }
      if (tot && on / tot >= thresh) { out[ry * n + rx] = 1; fill++; }
    }
  }
  return { bits: out, bbox: bb, fill };
}

const agree = (a, b) => {
  let same = 0;
  for (let i = 0; i < a.length; i++) if (a[i] === b[i]) same++;
  return (same * 100) / a.length;
};
/* Intersection over union — the harsher of the two, and the one that cannot be
 * inflated by two mostly-empty boxes agreeing about their empty corners. */
const iou = (a, b) => {
  let inter = 0, uni = 0;
  for (let i = 0; i < a.length; i++) { if (a[i] & b[i]) inter++; if (a[i] | b[i]) uni++; }
  return uni ? (inter * 100) / uni : 100;
};

function pxDiff(a, b) {
  let n = 0;
  const len = Math.min(a.data.length, b.data.length);
  for (let i = 0; i < len; i += 4) {
    if (a.data[i] !== b.data[i] || a.data[i+1] !== b.data[i+1]
      || a.data[i+2] !== b.data[i+2] || a.data[i+3] !== b.data[i+3]) n++;
  }
  return n;
}
/* Coverage only, colour discarded. This is the number that separates an
 * element from a recolour: repainting the whole sprite scores zero here. */
function silDiff(a, b) {
  let n = 0;
  const len = Math.min(a.data.length, b.data.length);
  for (let i = 3; i < len; i += 4) if ((a.data[i] > 0) !== (b.data[i] > 0)) n++;
  return n;
}
const opaque = (cv) => { let n = 0; for (let i = 3; i < cv.data.length; i += 4) if (cv.data[i]) n++; return n; };
const rgbAt = (cv, x, y) => {
  const i = (y * cv.width + x) * 4;
  return cv.data[i + 3] ? ((cv.data[i] << 16) | (cv.data[i + 1] << 8) | cv.data[i + 2]) : -1;
};
const hexVal = (h) => parseInt(String(h).slice(1, 7), 16);

/* How heavy the border is, in rings. Ring 1 is every opaque pixel touching
 * transparent; ring 2 is every opaque pixel touching ring 1 and not in it. The
 * percentage of each that is painted in one of the three outline tones is a
 * direct measurement of "a heavier outline": a one-pixel border scores high on
 * ring 1 and low on ring 2, a two-pixel border scores high on both. */
function outlineRings(cv, pal) {
  const dark = new Set([hexVal(pal.o), hexVal(pal.O), hexVal(pal.Q)]);
  const r1 = [], r2 = [];
  const isEdge = (x, y) => rgbAt(cv, x, y) >= 0 && (
    x === 0 || y === 0 || x === cv.width - 1 || y === cv.height - 1
    || rgbAt(cv, x - 1, y) < 0 || rgbAt(cv, x + 1, y) < 0
    || rgbAt(cv, x, y - 1) < 0 || rgbAt(cv, x, y + 1) < 0);
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) if (isEdge(x, y)) r1.push([x, y]);
  const inR1 = new Set(r1.map(([x, y]) => y * cv.width + x));
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) {
    if (rgbAt(cv, x, y) < 0 || inR1.has(y * cv.width + x)) continue;
    if (inR1.has(y * cv.width + x - 1) || inR1.has(y * cv.width + x + 1)
      || inR1.has((y - 1) * cv.width + x) || inR1.has((y + 1) * cv.width + x)) r2.push([x, y]);
  }
  const pct = (list) => list.length ? Math.round((list.filter(([x, y]) => dark.has(rgbAt(cv, x, y))).length * 100) / list.length) : 0;
  return { ring1: pct(r1), ring2: pct(r2) };
}

/* ---------- the roster under test ---------- */
const COLOUR = Object.fromEntries(V.bosses.map(b => [B.bossArtKey(b), b.colour]));
const rows = [];
for (const key of B.BOSS_ARCHETYPES) {
  const colour = COLOUR[key] || undefined;
  rows.push({ key, colour });
}

const hasMap = typeof B.bossMapSprite === 'function';
const BMAPH = B.BOSS_MAP_H || 64;
const report = { mapFormPresent: hasMap, bosses: [], fail: [] };

for (const { key, colour } of rows) {
  const battle = B.bossSprite(key, colour, 0, { phase: 0, beat: 0 });
  const map = hasMap ? B.bossMapSprite(key, colour, 0, { phase: 0 })
                     : battle;      // before the map form existed: same canvas
  const bs = shapeAt(battle), ms = shapeAt(map);

  const r = {
    key,
    battleBox: `${battle.width}x${battle.height}`,
    mapBox: `${map.width}x${map.height}`,
    battlePx: opaque(battle),
    mapPx: opaque(map),
    shapeAgree: +agree(bs.bits, ms.bits).toFixed(1),
    shapeIoU: +iou(bs.bits, ms.bits).toFixed(1),
    coloursBattle: colourCount(battle),
    coloursMap: colourCount(map),
  };

  // phases: pixels and silhouette cells that move
  const p0 = battle;
  for (const ph of [1, 2]) {
    const cv = B.bossSprite(key, colour, 0, { phase: ph, beat: 0 });
    const ss = shapeAt(cv);
    let cells = 0;
    for (let i = 0; i < ss.bits.length; i++) if (ss.bits[i] !== bs.bits[i]) cells++;
    r[`phase${ph}Px`] = pxDiff(p0, cv);
    r[`phase${ph}Cells`] = cells;
    r[`phase${ph}Colours`] = colourCount(cv);
    if (r[`phase${ph}Px`] === 0) report.fail.push(`${key}: phase ${ph} changes zero pixels`);
  }

  // parts move independently: per-beat deltas inside the idle loop
  const beats = [];
  for (let b = 0; b < B.BOSS_BEATS; b++) beats.push(B.bossSprite(key, colour, 0, { phase: 0, beat: b }));
  const deltas = beats.slice(1).map(cv => pxDiff(beats[0], cv));
  r.beatDeltas = deltas;
  r.beatSpread = Math.max(...deltas) - Math.min(...deltas);

  // colour budget, off rendered pixels, every frame x phase x beat
  let worst = 0, worstAt = '';
  for (let f = 0; f < B.BOSS_FRAME_COUNT; f++) {
    for (let ph = 0; ph < 3; ph++) {
      const n = colourCount(B.bossSprite(key, colour, f, { phase: ph, beat: f < 2 ? 3 : 0 }));
      if (n > worst) { worst = n; worstAt = `f${f}p${ph}`; }
    }
  }
  if (hasMap) {
    for (let ph = 0; ph < 3; ph++) {
      const n = colourCount(B.bossMapSprite(key, colour, 0, { phase: ph }));
      if (n > worst) { worst = n; worstAt = `map p${ph}`; }
    }
  }
  r.worstColours = worst; r.worstAt = worstAt;

  /* The element. THREE numbers now, and the middle one is new.
   *
   * This check was written when the element was a remap of light already on the
   * sprite — pure recolour — and it asserted that the colour count could not go
   * up, which for a recolour is true by construction. The element carries
   * GEOMETRY now (bossart.dressGrid: fire sheds, cold accretes, poison sags,
   * brute chips, lightning spans, void subtracts), and a verb that adds pixels
   * can legitimately paint a tone the bare creature never painted. Holding it
   * to delta <= 0 failed the Window Wraith — a nine-colour sprite — for
   * reaching eleven, while passing sprites sitting on the cap.
   *
   * So the assertion moves to the rule that is actually in the brief and in
   * bosses.js rule 1: FIFTEEN COLOURS, absolute, off the raster. The delta is
   * still measured and still printed, because it is the number that shows the
   * theme pass paying for itself — it is negative on four archetypes, where
   * collapsing r/f/R/u/i onto one shared mark ramp buys back more than the
   * geometry spends.
   *
   *   elementPx     it must move pixels, or it is not visible
   *   silhouette    it must move COVERAGE, or it is a recolour wearing a hat
   *   worstColours  it must stay inside fifteen, which is checked above */
  r.element = B.bossElement(key) || 'NEUTRAL';
  if (r.element !== 'NEUTRAL') {
    const plain = B.bossSprite(key, colour, 0, { phase: 2, beat: 0, element: 'NONE' });
    const lit = B.bossSprite(key, colour, 0, { phase: 2, beat: 0 });
    r.elementPx = pxDiff(plain, lit);
    r.elementSilhouette = silDiff(plain, lit);
    r.elementColourDelta = colourCount(lit) - colourCount(plain);
    r.elementColours = colourCount(lit);
    if (r.elementPx === 0) report.fail.push(`${key}: element ${r.element} changes zero pixels`);
    if (r.elementSilhouette === 0) report.fail.push(`${key}: element ${r.element} changes ${r.elementPx} pixels and no coverage — that is a recolour, not an element`);
    if (r.elementColours > 15) report.fail.push(`${key}: element ${r.element} takes the sprite to ${r.elementColours} colours`);
  } else { r.elementPx = 0; r.elementSilhouette = 0; r.elementColourDelta = 0; }

  const pal = B.bossPalette(colour || B.bossInfo(key).lighting.colour, undefined, 0, B.bossElement(key));
  r.mapRings = outlineRings(map, pal);
  r.battleRings = outlineRings(battle, pal);

  r.sheds = B.bossInfo(key).sheds || '-';
  r.grows = B.bossInfo(key).grows.join(',') || '-';
  if (worst > 15) report.fail.push(`${key}: ${worst} colours at ${worstAt} (budget 15)`);
  if (r.shapeIoU < 70) report.fail.push(`${key}: map/battle shape IoU ${r.shapeIoU}% — the forms have drifted`);
  report.bosses.push(r);
}

/* determinism of the map form, cold cache, twice */
if (hasMap) {
  for (const { key, colour } of rows) {
    B.clearBossCache();
    const a = frameHash(B.bossMapSprite(key, colour, 0, { phase: 1 }));
    B.clearBossCache();
    const b = frameHash(B.bossMapSprite(key, colour, 0, { phase: 1 }));
    if (a !== b) report.fail.push(`${key}: map form non-deterministic ${a} vs ${b}`);
  }
}

/* the map form has to outweigh a mob. sprites.ENEMY_SIZE is 24x24. */
report.mobBox = `${S.ENEMY_SIZE}x${S.ENEMY_SIZE}`;
report.heroBox = `${S.HERO_W}x${S.HERO_H}`;

/* What an ORDINARY monster on the same tile grid looks like, by the same
 * measurement. The boss marker has to be a different class of object, and
 * "different class of object" has to mean something countable: it is twice as
 * tall, it carries several times the pixels, and its border is a ring and a
 * half instead of a ring. */
{
  const ring = [], px = [], h = [];
  for (const k of S.ENEMY_ARCHETYPES.slice(0, 12)) {
    const cv = S.enemySprite(k, 'array', 0);
    if (!cv || !cv.width) continue;
    const pal = B.bossPalette('#8a8f9c', undefined, 0, null);
    const r = outlineRings(cv, pal);
    ring.push(r.ring2); px.push(opaque(cv)); h.push(cv.height);
  }
  const mean = (a) => a.length ? Math.round(a.reduce((x, y) => x + y, 0) / a.length) : 0;
  report.mob = { n: ring.length, box: report.mobBox, meanOpaquePx: mean(px) };
  const bossPx = Math.round(report.bosses.reduce((a, r) => a + r.mapPx, 0) / report.bosses.length);
  report.mob.bossMarkerMeanPx = bossPx;
  report.mob.timesTheMass = +(bossPx / Math.max(1, mean(px))).toFixed(1);
  report.mob.timesTheHeight = +(BMAPH / S.ENEMY_SIZE).toFixed(2);
}

/* Working set. Warm every archetype at every phase, both forms, and count the
 * canvases the module actually built. If that exceeds the cache cap the caches
 * thrash and a phase change regenerates sprites inside the render loop. */
if (hasMap) {
  B.clearBossCache();
  RASTER.counting = true; RASTER.canvases = 0;
  let warmed = 0;
  for (const { key, colour } of rows) {
    for (let ph = 0; ph < 3; ph++) { warmed += B.warmBoss(key, colour, ph); warmed += B.warmBossMap(key, colour, ph); }
  }
  const cold = RASTER.canvases;
  RASTER.canvases = 0;
  for (const { key, colour } of rows) {
    for (let ph = 0; ph < 3; ph++) { B.warmBoss(key, colour, ph); B.warmBossMap(key, colour, ph); }
  }
  const warm = RASTER.canvases;
  RASTER.counting = false;
  report.workingSet = { entriesAsked: warmed, canvasesBuiltCold: cold, canvasesBuiltWarm: warm };
  if (warm !== 0) report.fail.push(`whole roster thrashes the cache: ${warm} canvases rebuilt on the second warm`);

  /* And the hot path. Two passes: the first still builds the hit-flash
   * silhouettes, which is a cache warming and not a leak; the second is the
   * steady state and must be exactly zero. Measuring only the second is how
   * you tell a bounded warm-up from a per-frame allocation. */
  const ctx = new (globalThis.OffscreenCanvas)(320, 240).getContext('2d');
  const drawPass = () => {
    for (let i = 0; i < 600; i++) {
      B.drawBoss(ctx, 'demon', 160, 200, { time: i * 16, phase: (i / 200) | 0, flash: (i % 30) / 30 });
      B.drawBoss(ctx, 'titan', 60, 120, { time: i * 16, scale: 1 });
      B.drawBoss(ctx, 'wyrm', 240, 200, { time: i * 16, entrance: (i % 150) / 150 });
    }
  };
  RASTER.counting = true; RASTER.canvases = 0; drawPass();
  report.drawAllocsCold = RASTER.canvases;
  RASTER.canvases = 0; drawPass(); drawPass();
  report.drawAllocs = RASTER.canvases;
  RASTER.counting = false;
  if (report.drawAllocs !== 0) report.fail.push(`drawBoss allocated ${report.drawAllocs} canvases across 3600 steady-state draws`);
}

/* ---------------- the apex roster ----------------
 * gauntlet/hunters.py declares seventeen roaming apexes, each with a `sprite`
 * its author marked as not yet authored and a `sprite_fallback` naming the
 * archetype in bosses.js it should borrow until one exists. This checks that
 * every one of them resolves to the archetype hunters.py NAMED (not to a hash,
 * and not all to the same body), that it carries its own region's element, and
 * that the six archetypes carrying two apexes actually render differently.
 */
const APEX = [
  ['margin_walker', 'wraith', null], ['thresher', 'automaton', null],
  ['storm_ordinal', 'titan', 'LIGHTNING'], ['sporecrown', 'ent', 'POISON'],
  ['zeroth_weight', 'golem', 'BRUTE'], ['fenlight', 'hydra', 'POISON'],
  ['rimewarden', 'colossus', 'COLD'], ['cinder_phoenix', 'dragon', 'FIRE'],
  ['fourth_orientation', 'knight', 'BRUTE'], ['unreturning', 'lich', 'VOID'],
  ['bough_stalker', 'wyrm', null], ['lattice_stag', 'behemoth', 'LIGHTNING'],
  ['relighter', 'necromancer', null], ['slagmother', 'demon', 'FIRE'],
  ['the_doubling', 'automaton', 'COLD'], ['sand_champion', 'titan', null],
  ['the_unnamed', 'colossus', 'VOID'],
];
if (hasMap) {
  const seen = new Map();
  report.apex = [];
  for (const [id, want, element] of APEX) {
    const got = B.resolveBoss(id);
    if (got !== want) report.fail.push(`apex ${id}: hunters.py names ${want}, bosses.js resolves ${got}`);
    const el = B.bossElement(id);
    if (el !== element) report.fail.push(`apex ${id}: element ${el}, hunters.py says ${element}`);
    const battle = B.bossSprite(id, undefined, 0, { phase: 0 });
    const map = B.bossMapSprite(id, undefined, 0, { phase: 0 });
    const row = {
      id, art: got, element: el || 'NEUTRAL',
      shapeIoU: +iou(shapeAt(battle).bits, shapeAt(map).bits).toFixed(1),
      colours: Math.max(colourCount(battle), colourCount(map)),
      hash: frameHash(battle),
    };
    if (row.colours > 15) report.fail.push(`apex ${id}: ${row.colours} colours`);
    /* Two apexes on one body must not be the same picture. */
    const prev = seen.get(got);
    if (prev && prev.hash === row.hash) report.fail.push(`apex ${id} renders identically to ${prev.id}`);
    if (!prev) seen.set(got, row);
    report.apex.push(row);
  }
}

/* The entrance, as the driver will read it. */
report.entrance = {
  durationMs: B.BOSS_ENTRANCE_MS, holdMs: B.BOSS_ENTRANCE_HOLD_MS, tauntAtMs: B.BOSS_TAUNT_AT_MS,
  rimBandsMs: B.BOSS_ENTRANCE_RIM_MS.slice(),
  beats: B.BOSS_ENTRANCE_BEATS.map(b => `${b.fromMs}-${b.toMs}ms ${b.name}: ${b.does}`),
  sampled: [0, 0.14, 0.3, 0.45, 0.6, 0.7, 0.79, 0.9, 1, 1.19]
    .concat([B.BOSS_TAUNT_AT_MS / B.BOSS_ENTRANCE_MS])
    .map(k => { const e = B.bossEntrance('demon', k); return `${String(e.ms).padStart(4)}ms ${e.beat.padEnd(6)} shake ${e.shake.toFixed(1)} flash ${e.flash.toFixed(2)}${e.taunt ? '  <- first line' : ''}`; }),
};

if (JSONOUT) { console.log(JSON.stringify(report, null, 1)); }
else {
  const pad = (s, n) => String(s).padEnd(n);
  console.log(`map form present: ${hasMap}   hero ${report.heroBox}   mob ${report.mobBox}   boss marker ${B.BOSS_MAP_W}x${B.BOSS_MAP_H} (wide ${B.BOSS_MAP_WIDE_W})`);
  if (report.mob) console.log(`  against ${report.mob.n} ordinary monsters: the marker is ${report.mob.timesTheHeight}x the height and ${report.mob.timesTheMass}x the painted mass (${report.mob.bossMarkerMeanPx} px vs ${report.mob.meanOpaquePx})`);
  console.log('');
  console.log('ONE CREATURE, TWO SCALES  — map silhouette vs battle silhouette, both normalised into one 24x24 box');
  console.log(`${pad('archetype', 13)} ${pad('map', 8)} ${pad('battle', 8)} agree%  IoU%   ${pad('cols', 5)} ${pad('element', 10)} ${pad('elem px', 8)} ${pad('elem sil', 9)} ${pad('dcols', 6)}`);
  for (const r of report.bosses) {
    console.log(`${pad(r.key, 13)} ${pad(r.mapBox, 8)} ${pad(r.battleBox, 8)} ${pad(r.shapeAgree, 6)} ${pad(r.shapeIoU, 6)} ${pad(r.worstColours, 5)} ${pad(r.element, 10)} ${pad(r.elementPx, 8)} ${pad(r.elementSilhouette || 0, 9)} ${pad(r.elementColourDelta, 6)}`);
  }
  console.log('');
  console.log('THE MAP FORM IS A BOSS  — % of the silhouette edge painted in an outline tone, ring 1 then ring 2');
  console.log(`${pad('archetype', 13)} ${pad('map r1', 8)} ${pad('map r2', 8)} ${pad('battle r1', 10)} ${pad('battle r2', 10)} ${pad('map px', 8)} battle px`);
  for (const r of report.bosses) {
    console.log(`${pad(r.key, 13)} ${pad(r.mapRings.ring1 + '%', 8)} ${pad(r.mapRings.ring2 + '%', 8)} ${pad(r.battleRings.ring1 + '%', 10)} ${pad(r.battleRings.ring2 + '%', 10)} ${pad(r.mapPx, 8)} ${r.battlePx}`);
  }
  console.log('');
  console.log('PHASES CHANGE THE ART  — pixels moved, and silhouette cells moved, against phase 0');
  console.log(`${pad('archetype', 13)} ${pad('p1 px', 7)} ${pad('p1 cells', 9)} ${pad('p2 px', 7)} ${pad('p2 cells', 9)} ${pad('sheds', 8)} ${pad('grows', 8)} beat spread`);
  for (const r of report.bosses) {
    console.log(`${pad(r.key, 13)} ${pad(r.phase1Px, 7)} ${pad(r.phase1Cells, 9)} ${pad(r.phase2Px, 7)} ${pad(r.phase2Cells, 9)} ${pad(r.sheds, 8)} ${pad(r.grows, 8)} ${r.beatSpread}`);
  }
  console.log('');
  const s = report.bosses;
  const avg = (f) => (s.reduce((a, r) => a + r[f], 0) / s.length).toFixed(1);
  console.log(`mean shape agreement ${avg('shapeAgree')}%   mean IoU ${avg('shapeIoU')}%   worst IoU ${Math.min(...s.map(r => r.shapeIoU))}%`);
  console.log(`colour budget: worst ${Math.max(...s.map(r => r.worstColours))} of 15`);
  if (report.workingSet) console.log(`working set: ${report.workingSet.canvasesBuiltCold} canvases cold, ${report.workingSet.canvasesBuiltWarm} rebuilt warm (cap 832); 1800 draws allocated ${report.drawAllocsCold} cold, ${report.drawAllocs} steady`);
  if (report.apex) {
    console.log('');
    console.log('THE APEX ROSTER  — gauntlet/hunters.py, seventeen roaming monsters borrowing a body until one is authored');
    console.log(`${pad('apex id', 20)} ${pad('body', 13)} ${pad('element', 10)} ${pad('IoU%', 6)} ${pad('cols', 5)} frame hash`);
    for (const a of report.apex) console.log(`${pad(a.id, 20)} ${pad(a.art, 13)} ${pad(a.element, 10)} ${pad(a.shapeIoU, 6)} ${pad(a.colours, 5)} ${a.hash}`);
    const bodies = new Set(report.apex.map(a => a.art));
    console.log(`  ${report.apex.length} apexes over ${bodies.size} bodies; every shared body separated by element and by frame hash`);
  }
  console.log('');
  console.log(`THE ENTRANCE  ${report.entrance.durationMs}ms staged + ${report.entrance.holdMs}ms hold; first line at ${report.entrance.tauntAtMs}ms; rim bands at ${report.entrance.rimBandsMs.join('/')}ms`);
  for (const b of report.entrance.beats) console.log('  ' + b);
  for (const l of report.entrance.sampled) console.log('    ' + l);
  console.log('');
  console.log(report.fail.length ? `FAIL (${report.fail.length}):\n  ` + report.fail.join('\n  ') : 'VERDICT: pass');
}
process.exitCode = report.fail.length ? 1 : 0;
